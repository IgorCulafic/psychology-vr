"""Build the saved local three-model listening comparison after auditions finish."""
from pathlib import Path
import hashlib
import html
import json
import math
import shutil
import urllib.request

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/generated/fish-local/alternatives'
NAMES = {'fish': 'Fish S2 Pro', 'omnivoice': 'OmniVoice', 'higgs': 'Higgs TTS 3 · Transformers port'}
reports = {name: json.loads((OUT / name / 'results.json').read_text(encoding='utf-8')) for name in NAMES}
assert len({r['reference_sha256'] for r in reports.values()}) == 1
assert [len(reports[n]['samples']) for n in NAMES] == [3, 5, 6]
for name, report in reports.items():
    for sample in report['samples']:
        assert sample.get('status', 'generated') == 'generated'
        a, sr = sf.read(OUT / name / sample['file'])
        assert a.ndim == 1 and len(a) > 0 and np.isfinite(a).all()
        assert abs(len(a) / sr - sample['duration_seconds']) < .002

timings = {}


def reel(filename, clips):
    parts, sections, cursor = [], [], 0
    for label, path in clips:
        a, sr = sf.read(path)
        if sr != 24000:
            divisor = math.gcd(sr, 24000)
            a = resample_poly(a, 24000 // divisor, sr // divisor)
        if parts:
            parts.append(np.zeros(24000))
            cursor += 1
        sections.append(dict(label=label, start_seconds=round(cursor, 3), duration_seconds=round(len(a)/24000, 3)))
        parts.append(a)
        cursor += len(a)/24000
    joined = np.concatenate(parts)
    gain = min(1.0, .98 / max(float(np.abs(joined).max()), 1e-8))
    sf.write(OUT / filename, joined * gain, 24000, subtype='PCM_16')
    timings[filename] = dict(sections=sections, gain=gain, note='24 kHz playback reel with one-second gaps; original files untouched.')


for stem in ['short', 'neutral', 'diagnostic']:
    reel(stem + '-comparison.wav', [(NAMES[n], OUT/n/(stem + ('-sr' if n == 'omnivoice' else '') + '.wav')) for n in NAMES])
reel('higgs-emotions.wav', [(label, OUT/'higgs'/(case+'.wav')) for case, label in [('neutral','Neutral'),('angry','Angry'),('sad','Sad'),('happy','Happy')]])
reel('omnivoice-languages.wav', [(lang, OUT/'omnivoice'/('neutral-'+lang+'.wav')) for lang in ['sr','hr','bs']])
(OUT/'comparison-sections.json').write_text(json.dumps(timings, ensure_ascii=False, indent=2), encoding='utf-8')
shutil.copy2(ROOT/'docs/generated/fish-local/references/clone-test-1-short.wav', OUT/'reference.wav')
cards = []
for name, report in reports.items():
    cards.append('<section><h2>'+html.escape(NAMES[name])+'</h2><p>'+html.escape(report.get('note', report.get('description','')))+'</p><div class="grid">')
    for sample in report['samples']:
        cards.append(f'<article><h3>{html.escape(sample["label"])}</h3><p>{html.escape(sample["text"])}</p><audio controls preload="none" src="{name}/{sample["file"]}"></audio><small>{sample["duration_seconds"]:.2f}s speech · {sample["generation_seconds"]:.2f}s generation</small></article>')
    cards.append('</div></section>')
page = '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Voice auditions · Fish / OmniVoice / Higgs</title>
<style>body{font:17px system-ui;background:#f6f1e9;color:#302b27;max-width:1120px;margin:40px auto;padding:0 24px}h1{font-size:36px}h2{font-size:25px;margin-top:32px}h3{font-size:19px}p{line-height:1.55}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:18px}article,.reel{background:#fff;border:1px solid #ded4c7;border-radius:14px;padding:20px;margin-bottom:18px}audio{width:100%;margin:10px 0}small{color:#655e57}a{color:#285b49}.intro{max-width:850px}.order{font-weight:650;color:#285b49}details{margin:20px 0}</style></head><body>
<header><h1>Three voices, the same words</h1><p class="intro">Fish stays in the comparison. OmniVoice and Higgs are local alternatives, all using the same 6.5-second excerpt from your recording. Listen for the accent, <b>č / ć</b>, and the final vowel in <b>reći</b>. Automatic transcripts cannot judge those reliably.</p>
<details><summary>Your shared voice reference</summary><audio controls preload="none" src="reference.wav"></audio><p>Dobar dan. Danas sam došao malo ranije, pa sam usput prošetao i kupio kafu.</p></details></header>
<section><h2>Compare pronunciation</h2><p class="order">Every reel: Fish → OmniVoice (sr) → Higgs</p>
<div class="reel"><h3>Ovo je na mom kompjuteru.</h3><audio controls preload="metadata" src="short-comparison.wav"></audio></div>
<div class="reel"><h3>The original passage</h3><p>Nisam očekivao da ćete to reći. Toliko toga želim da vam kažem. Dajte mi samo trenutak da saberem misli.</p><audio controls preload="none" src="neutral-comparison.wav"></audio></div>
<div class="reel"><h3>Pronunciation test</h3><p>Očekivao sam da ćete mi reći šta se dogodilo. Hoću da čujem cijelu priču. Ovo je na mom kompjuteru.</p><audio controls preload="none" src="diagnostic-comparison.wav"></audio></div></section>
<section><h2>Expression and language controls</h2><div class="grid"><article><h3>Higgs: neutral → angry → sad → happy</h3><p>The same words with Higgs emotion tokens.</p><audio controls preload="none" src="higgs-emotions.wav"></audio></article><article><h3>OmniVoice: sr → hr → bs</h3><p>The same words with explicit language settings. This is a neutral voice-cloning test, not an anger/sadness test.</p><audio controls preload="none" src="omnivoice-languages.wav"></audio></article></div></section>
<details><summary>How these were made</summary><p>All generated locally using your reference and seed 42. OmniVoice uses its official Python runtime and 32 diffusion steps. Higgs uses a community Transformers port; this does not benchmark the official SGLang server. Fish uses our current 0.55 temperature / 0.7 top-p settings, with plain text and no experimental language cue. Each model uses its own supported controls.</p><p>Reels are resampled to 24 kHz with one-second pauses; no pitch or speed changes. Individual files retain their original sample rates. Generation timings exclude model loading and are not streaming latency. Voice similarity, accent and emotion quality need your assessment.</p><p><a href="https://github.com/k2-fsa/OmniVoice">OmniVoice documentation</a> · <a href="https://huggingface.co/bosonai/higgs-tts-3-4b">Higgs documentation</a> · <a href="../../clone-test-1-serbian/index.html">Earlier Fish samples</a></p></details>
CARDS</body></html>'''.replace('CARDS',''.join(cards)).replace('../../clone-test-1-serbian/','../clone-test-1-serbian/')
(OUT/'index.html').write_text(page, encoding='utf-8')
verification = dict(models=list(NAMES), samples=14, same_reference=True,
                    reference_sha256=next(iter(reports.values()))['reference_sha256'],
                    human_pronunciation_assessment='pending')
for filename in ['index.html','reference.wav']+list(timings):
    with urllib.request.urlopen('http://127.0.0.1:8793/alternatives/'+filename,timeout=5) as response:
        assert response.status == 200
(OUT/'verification.json').write_text(json.dumps(verification,indent=2),encoding='utf-8')
print('Verified 14 individual samples, 5 comparison reels and shared reference. Page: '+str(OUT/'index.html'))
