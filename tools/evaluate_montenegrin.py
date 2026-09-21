"""Local diagnostics, not a population benchmark. Private results stay in .runtime.

STT: --stt --reference path.wav --transcript path.txt --output services/.runtime/stt.json
Dialogue: --dialogue --output services/.runtime/dialogue.json
Run with the project's .venv Python. No TTS is generated and no audio is uploaded.
"""
import argparse
import gc
import json
from pathlib import Path
import re
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'services'))

from speech_language import latin_script


def words(text):
    # Do not conflate č/ć, diacritics or ijekavian/ekavian wording.
    return re.findall(r'\w+', latin_script(text).lower())


def wer(expected, actual):
    ref, hyp = words(expected), words(actual)
    row = list(range(len(hyp) + 1))
    for i, a in enumerate(ref, 1):
        new = [i]
        for j, b in enumerate(hyp, 1):
            new.append(min(new[-1]+1, row[j]+1, row[j-1]+(a != b)))
        row = new
    return round(row[-1] / max(1, len(ref)), 4)


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def stt(args):
    import numpy as np
    from faster_whisper import WhisperModel
    from faster_whisper.audio import decode_audio
    audio = decode_audio(str(args.reference), sampling_rate=16000)
    expected = Path(args.transcript).read_text(encoding='utf-8').strip()
    results = []
    for name in ('medium', 'large-v3-turbo'):
        model = WhisperModel(str(ROOT / '.cache/whisper' / name), device='cpu',
                             compute_type='int8', cpu_threads=8)
        # Warm up outside timing. Always exhaust the lazy generator.
        list(model.transcribe(audio[:32000], language='sr')[0])
        variants = [('baseline', {})] if name == 'medium' else [
            ('baseline', {}),
            ('independent-latin', dict(condition_on_previous_text=False,
                initial_prompt='Razgovor na crnogorskom jeziku, latinicom.')),
            ('independent-latin-beam1', dict(beam_size=1, condition_on_previous_text=False,
                initial_prompt='Razgovor na crnogorskom jeziku, latinicom.'))]
        for variant, extra in variants:
            start = time.perf_counter()
            segments, _ = model.transcribe(audio, language='sr', task='transcribe',
                                            vad_filter=True, **extra)
            transcript = ' '.join(s.text.strip() for s in segments)
            result = dict(model=name, variant=variant, seconds=round(time.perf_counter()-start, 3),
                          duration=round(len(audio)/16000, 3), wer=wer(expected, transcript), text=transcript)
            results.append(result)
            print(json.dumps(result, ensure_ascii=False), flush=True)
            save(args.output, results)
        silent = list(model.transcribe(np.zeros(48000, dtype=np.float32), language='sr', vad_filter=True)[0])
        print(name, 'silence:', [s.text for s in silent], flush=True)
        del model
        gc.collect()


CASES = [
    ('conversation', 'Dobar dan, Alex. Šta vam je sada najteže?'),
    ('conversation', 'Da li vas leđa bole i dok sjedite ili samo kad ustanete?'),
    ('conversation', 'Ne morate da ustajete. Možemo da ostanemo ovako i malo usporimo.'),
    ('conversation', 'Samo polako udahnite, pa izdahnite. Je li sad makar malo lakše?'),
    ('conversation', 'Pa dobro, svi ste živi. Nema razloga da toliko dramite.'),
    ('conversation', 'Izvinite, to je bilo grubo. Ne želim da umanjujem ono što ste prošli.'),
    ('family', 'Da li je neko od vaših poginuo u zemljotresu?'),
    ('family', 'Kako se zove osoba koja je s vama u smještaju?'),
    ('pronouns', 'Moja porodica je daleko. A vaša, jeste li zajedno?'),
    ('unclear', 'Jeste li ono sa tamo ne prije poslije?'),
]


def dialogue(args):
    from alex_service import Bridge
    config = json.loads((ROOT / 'services/config.local.json').read_text(encoding='utf-8'))
    bridge = Bridge(config)
    original_post = bridge.post_json
    bridge.post_json = lambda url, body, timeout: original_post(url, {**body, 'seed': 42}, timeout)
    profile = bridge.profiles[bridge.catalog['default_scenario_id']]
    histories, states, results = {}, {}, []
    for group, text in CASES:
        history = histories.setdefault(group, [])
        state = states.setdefault(group, dict(profile['initial_state']))
        start = time.perf_counter()
        segments = bridge.generate(text, history, False, state, profile)
        result = dict(group=group, input=text, seconds=round(time.perf_counter()-start, 3), segments=segments)
        results.append(result)
        history.extend([dict(role='user', content=text),
                        dict(role='assistant', content=json.dumps(dict(segments=segments), ensure_ascii=False))])
        state.update({k: segments[-1][k] for k in ('emotion', 'intensity')})
        print(json.dumps(result, ensure_ascii=False), flush=True)
        save(args.output, results)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--stt', action='store_true')
    mode.add_argument('--dialogue', action='store_true')
    parser.add_argument('--reference', type=Path)
    parser.add_argument('--transcript', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.stt and (not args.reference or not args.transcript):
        parser.error('--stt requires --reference and --transcript')
    stt(args) if args.stt else dialogue(args)
