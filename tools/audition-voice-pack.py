"""Generate a controlled Higgs BF16 listening comparison from a prepared voice pack.

Requires reference_neutral/angry/sad/happy WAV+JSON pairs in the prepared folder.
Run using .tools/alternative-tts-venv/Scripts/python.exe. Does not edit game settings.
"""
import argparse
import hashlib
import html
import json
from pathlib import Path
import re
import shutil
import sys
import time

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'services'))
from higgs_service import HiggsVoice

TEXT = 'Nije mi lako da govorim o ovome. Molim vas, pustite me da završim, pa ću vam objasniti šta se dogodilo.'
JOBS = [
    ('neutral', 'Neutral', 'neutral', ''),
    ('anger-A', 'Anger A: acted reference, no tag', 'angry', ''),
    ('anger-B', 'Anger B: anger cue', 'angry', '<|emotion:anger|>'),
    ('anger-C', 'Anger C: bitterness cue', 'angry', '<|emotion:bitterness|>'),
    ('sad', 'Sadness', 'sad', '<|emotion:sadness|>'),
    ('happy', 'Happiness', 'happy', '<|emotion:elation|>'),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('person')
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--resume', action='store_true', help='Reuse matching completed samples after an interruption')
    args = parser.parse_args()
    if not re.fullmatch(r'person_\d+', args.person):
        parser.error('Expected an anonymous speaker ID')
    folder = ROOT / 'voices' / args.person / 'prepared'
    out = args.out.resolve()
    if out.exists() and any(out.iterdir()) and not args.resume:
        parser.error('Output directory must be empty to preserve earlier auditions')
    out.mkdir(parents=True, exist_ok=True)
    references = {}
    for emotion in ['neutral', 'angry', 'sad', 'happy']:
        path = folder / f'reference_{emotion}.wav'
        metadata = json.loads(path.with_suffix('.json').read_text(encoding='utf-8'))
        if not metadata.get('text', '').strip():
            raise ValueError(f'Empty reference transcript: {path}')
        references[emotion] = dict(path=path, metadata=metadata,
            sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        shutil.copyfile(path, out / path.name)
        shutil.copyfile(path.with_suffix('.json'), out / path.with_suffix('.json').name)
    config = json.loads((ROOT / 'services/config.local.json').read_text(encoding='utf-8-sig'))
    config.update(higgs_quantization='bf16', higgs_temperature=.6,
                  higgs_reference=str(references['neutral']['path'].relative_to(ROOT)))
    voice = HiggsVoice(config)
    report = dict(person=args.person, model='Higgs TTS 3', precision='bf16', temperature=.6,
                  top_p=.95, top_k=50, seed=42, text=TEXT, samples=[],
                  listening_assessment='pending', active_in_game=False)
    if args.resume and (out / 'results.json').exists():
        previous = json.loads((out / 'results.json').read_text(encoding='utf-8'))
        for key in ['person', 'model', 'precision', 'temperature', 'top_p', 'top_k', 'seed', 'text']:
            if previous.get(key) != report[key]:
                raise ValueError(f'Cannot resume an audition with changed {key}')
        report = previous
    parts = []
    for name, title, emotion, tag in JOBS:
        ref = references[emotion]
        completed = next((s for s in report['samples'] if s['id'] == name), None)
        if completed:
            if completed['emotion_tag'] != tag or completed['reference_sha256'] != ref['sha256'] or completed['reference_text'] != ref['metadata']['text']:
                raise ValueError(f'Cannot overwrite a changed audition: {name}')
            audio, rate = sf.read(out / completed['file'], dtype='float32')
            if rate != voice.rate or not np.isfinite(audio).all():
                raise ValueError(f'Invalid completed audio: {name}')
            if parts:
                parts.append(np.zeros(voice.rate, dtype='float32'))
            parts.append(audio)
            continue
        audio, rate = sf.read(ref['path'], dtype='float32')
        with voice.torch.inference_mode():
            voice.reference_codes = voice.model._encode_reference(voice.torch.from_numpy(audio), rate)
        voice.reference_text = ref['metadata']['text']
        voice.torch.manual_seed(42)
        voice.torch.cuda.manual_seed_all(42)
        started = time.perf_counter()
        with voice.torch.inference_mode():
            audio = voice.model.generate_speech(tag + TEXT, voice.tokenizer,
                reference_codes=voice.reference_codes, reference_text=voice.reference_text,
                temperature=.6, top_p=.95, top_k=50, max_new_tokens=900).numpy()
        audio = np.asarray(audio, dtype='float32').reshape(-1)
        if not np.isfinite(audio).all() or not voice.rate < len(audio) < 35*voice.rate:
            raise ValueError(f'Invalid generated audio for {name}')
        gain = min(1., .98/max(float(np.abs(audio).max()), 1e-8))
        audio *= gain
        sf.write(out / (name + '.wav'), audio, voice.rate, subtype='PCM_16')
        if parts:
            parts.append(np.zeros(voice.rate, dtype='float32'))
        parts.append(audio)
        row = dict(id=name, title=title, reference_emotion=emotion, reference_sha256=ref['sha256'],
                   reference_text=voice.reference_text, emotion_tag=tag, file=name+'.wav',
                   duration_seconds=round(len(audio)/voice.rate, 3),
                   generation_seconds=round(time.perf_counter()-started, 3), output_gain=gain)
        report['samples'].append(row)
        (out / 'results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        print(json.dumps(row, ensure_ascii=True), flush=True)
    sf.write(out / 'comparison.wav', np.concatenate(parts), voice.rate, subtype='PCM_16')
    cards = ''.join(f'<article><h3>{html.escape(s["title"])}</h3><audio controls preload="none" src="{s["file"]}"></audio></article>'
                    for s in report['samples'])
    reference_cards = ''.join(f'<article><h3>Recorded {emotion}</h3><audio controls preload="none" src="reference_{emotion}.wav"></audio></article>'
                              for emotion in references)
    page = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>PERSON - voice comparison</title><style>body{font:17px/1.6 system-ui;max-width:1100px;margin:40px auto;padding:0 24px;background:#f5f1e9;color:#263b36}section{background:#fff;padding:24px;border-radius:16px;margin:24px 0;border:1px solid #ddd}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:22px}audio{width:100%}h3{font-size:17px}blockquote{border-left:4px solid #48766a;padding-left:20px;margin-left:0}</style>
<h1>PERSON - voice comparison</h1><p>Compare the recorded voice with the generated samples. Which anger option keeps the right person while conveying the emotion?</p>
<blockquote>TEXT</blockquote><section><h2>All samples</h2><p>Neutral → anger A → anger B → anger C → sad → happy. One-second gaps.</p><audio controls preload="metadata" src="comparison.wav"></audio><div class="grid">CARDS</div></section>
<section><h2>Original voice references</h2><div class="grid">REFERENCES</div></section>
<p>Higgs BF16, temperature 0.60, seed 42. Each emotion uses that person's corresponding acted reference. A has no emotion tag; B uses anger; C uses bitterness. Only constant gain and boundary trimming were applied to the references. Transcript corrections remain provisional pending listening review. Voice likeness and emotional quality need your assessment. No character assignment has been made.</p></html>'''
    page = page.replace('PERSON', html.escape(args.person)).replace('TEXT', html.escape(TEXT)).replace('CARDS', cards).replace('REFERENCES', reference_cards)
    (out / 'index.html').write_text(page, encoding='utf-8')
    print('VOICE_AUDITION_COMPLETE', flush=True)


if __name__ == '__main__':
    main()
