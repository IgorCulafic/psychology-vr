"""Compare reference identity and gentler Higgs cues without changing the game.

Run with the alternative-TTS Python; specify a prepared person ID and a new output
directory. Existing comparisons and preferred performances are preserved.
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
    ('sad-A', 'Sad A: recorded sadness only', 'sad', ''),
    ('sad-B', 'Sad B: neutral voice + sadness cue', 'neutral', '<|emotion:sadness|>'),
    ('sad-C', 'Sad C: recorded sadness + restrained delivery', 'sad', '<|prosody:expressive_low|>'),
    ('happy-A', 'Happy A: recorded happiness only', 'happy', ''),
    ('happy-B', 'Happy B: recorded happiness + contentment', 'happy', '<|emotion:contentment|>'),
    ('happy-C', 'Happy C: neutral voice + contentment', 'neutral', '<|emotion:contentment|>'),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('person')
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--happiness', action='store_true', help='Compare stronger happiness using upbeat text and a longer acted reference')
    args = parser.parse_args()
    if not re.fullmatch(r'person_\d+', args.person):
        parser.error('Expected an anonymous speaker ID')
    out = args.out.resolve()
    if out.exists() and any(out.iterdir()):
        parser.error('Use a new directory to preserve previous listening comparisons')
    folder = ROOT / 'voices' / args.person / 'prepared'
    jobs = JOBS
    text = TEXT
    reference_names = ['neutral', 'sad', 'happy']
    groups = [('sad', 'Sadness'), ('happy', 'Happiness')]
    title = 'sadness and happiness'
    intro = 'Anger C is saved as preferred. The earlier sadness sample was rejected for voice identity, and happiness needs improvement. Compare these new candidates for the right voice first, then the emotion.'
    explanation = 'A removes the explicit emotion cue. Sad B changes the reference to neutral; sad C replaces the sadness cue with restrained delivery. Happy B replaces elation with contentment; happy C also changes the reference to neutral.'
    if args.happiness:
        jobs = [
            ('happy-A', 'A: short happy reference + enthusiasm', 'happy', '<|emotion:enthusiasm|>'),
            ('happy-B', 'B: longer happy performance, no cue', 'happy_long', ''),
            ('happy-C', 'C: longer happy performance + enthusiasm', 'happy_long', '<|emotion:enthusiasm|>'),
            ('happy-D', 'D: longer happy performance + elation and high expression', 'happy_long', '<|emotion:elation|><|prosody:expressive_high|>'),
        ]
        text = 'Baš mi je drago što ste došli! Jedva čekam da vam ispričam šta se dogodilo. Sve je ispalo bolje nego što sam očekivao!'
        reference_names = ['happy', 'happy_long']
        groups = [('happy', 'Happiness')]
        title = 'clearer happiness'
        intro = 'The previous happiness candidates were not happy enough. These four generated samples use a cheerful new sentence. Compare the strength of the happiness and whether the voice still sounds like the same person.'
        explanation = 'A uses the earlier short happy reference with enthusiasm. B uses the longer acted happiness reference without a cue. C adds enthusiasm to that longer reference. D uses elation with high expression. The sentence differs from the earlier round, so this is not a controlled comparison against those older samples.'
    refs = {}
    for emotion in reference_names:
        path = folder / f'reference_{emotion}.wav'
        metadata = json.loads(path.with_suffix('.json').read_text(encoding='utf-8'))
        if not metadata.get('text', '').strip():
            raise ValueError(f'Empty reference transcript: {path}')
        refs[emotion] = dict(path=path, text=metadata['text'],
                             sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    out.mkdir(parents=True, exist_ok=True)
    for ref in refs.values():
        shutil.copyfile(ref['path'], out / ref['path'].name)
        shutil.copyfile(ref['path'].with_suffix('.json'), out / ref['path'].with_suffix('.json').name)
    config = json.loads((ROOT / 'services/config.local.json').read_text(encoding='utf-8-sig'))
    config.update(higgs_quantization='bf16', higgs_temperature=.6,
                  higgs_reference=str(refs[reference_names[0]]['path'].relative_to(ROOT)))
    voice = HiggsVoice(config)
    for ref in refs.values():
        audio, rate = sf.read(ref['path'], dtype='float32')
        with voice.torch.inference_mode():
            ref['codes'] = voice.model._encode_reference(voice.torch.from_numpy(audio), rate)
    report = dict(person=args.person, model='Higgs TTS 3', precision='bf16', temperature=.6,
                  top_p=.95, top_k=50, seed=42, text=text, samples=[],
                  listening_assessment='pending', active_in_game=False,
                  hypothesis='Separate reference identity from emotion-token effects; not a confirmed diagnosis.')
    for name, sample_title, emotion, cue in jobs:
        ref = refs[emotion]
        voice.torch.manual_seed(42)
        voice.torch.cuda.manual_seed_all(42)
        started = time.perf_counter()
        with voice.torch.inference_mode():
            audio = voice.model.generate_speech(cue + text, voice.tokenizer,
                reference_codes=ref['codes'], reference_text=ref['text'],
                temperature=.6, top_p=.95, top_k=50, max_new_tokens=900).numpy()
        audio = np.asarray(audio, dtype='float32').reshape(-1)
        if not np.isfinite(audio).all() or not voice.rate < len(audio) < 35 * voice.rate:
            raise ValueError(f'Invalid generated audio: {name}')
        gain = min(1., .98 / max(float(np.abs(audio).max()), 1e-8))
        sf.write(out / (name + '.wav'), audio * gain, voice.rate, subtype='PCM_16')
        row = dict(id=name, title=sample_title, reference_emotion=emotion, reference_sha256=ref['sha256'],
                   reference_text=ref['text'], cue=cue, file=name+'.wav',
                   duration_seconds=round(len(audio)/voice.rate, 3),
                   generation_seconds=round(time.perf_counter()-started, 3), output_gain=gain)
        report['samples'].append(row)
        (out / 'results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        print(json.dumps(row, ensure_ascii=True), flush=True)
    sections = []
    for emotion, group_title in groups:
        samples = [s for s in report['samples'] if s['id'].startswith(emotion + '-')]
        parts = []
        for sample in samples:
            audio, rate = sf.read(out / sample['file'], dtype='float32')
            if parts:
                parts.append(np.zeros(rate, dtype='float32'))
            parts.append(audio)
        letters = ''.join(s['id'].split('-')[-1] for s in samples)
        combined_name = emotion + '-' + letters + '.wav'
        sf.write(out / combined_name, np.concatenate(parts), voice.rate, subtype='PCM_16')
        cards = ''.join(f'<article><h3>{html.escape(s["title"])}</h3><audio controls preload="none" src="{s["file"]}"></audio></article>' for s in samples)
        sections.append(f'<section><h2>{group_title}: {" → ".join(letters)}</h2><audio controls preload="metadata" src="{combined_name}"></audio><div class="grid">{cards}</div></section>')
    ref_labels = {'happy': 'Short recorded happiness', 'happy_long': 'Longer recorded happiness',
                  'sad': 'Recorded sadness', 'neutral': 'Recorded neutral voice'}
    ref_cards = ''.join(f'<article><h3>{ref_labels[emotion]}</h3><audio controls preload="none" src="reference_{emotion}.wav"></audio></article>' for emotion in refs)
    page = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>PERSON - TITLE</title><style>body{font:17px/1.6 system-ui;max-width:1120px;margin:36px auto;padding:0 24px;background:#f5f1e9;color:#263b36}section{background:#fff;padding:24px;border-radius:16px;margin:24px 0;border:1px solid #ddd}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:22px}audio{width:100%}h3{font-size:17px}blockquote{border-left:4px solid #48766a;padding-left:20px;margin-left:0}a{color:#286b59}</style>
<h1>PERSON - TITLE</h1><p>INTRO</p>
<blockquote>TEXT</blockquote>SECTIONS<section><h2>Recorded references</h2><div class="grid">REFS</div></section>
<p>BF16, temperature 0.60, top-p 0.95, top-k 50, seed 42. Same words and sampling settings across candidates. EXPLANATION These are listening candidates, not approved fixes. No pitch shifting or game settings changes.</p></html>'''
    page = page.replace('PERSON', html.escape(args.person)).replace('TITLE', html.escape(title)).replace('INTRO', html.escape(intro)).replace('EXPLANATION', html.escape(explanation)).replace('TEXT', html.escape(text)).replace('SECTIONS', ''.join(sections)).replace('REFS', ref_cards)
    (out / 'index.html').write_text(page, encoding='utf-8')
    print('VOICE_REFINEMENT_COMPLETE', flush=True)


if __name__ == '__main__':
    main()
