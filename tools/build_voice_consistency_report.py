"""Build the identity-drift listening test from saved local generation results."""
from pathlib import Path
import html
import json
import shutil
import urllib.request
import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'docs/generated/fish-local/voice-consistency'
PREVIOUS = OUT.parent/'alternatives'
models = ['omnivoice','higgs']
reports = {m:json.loads((OUT/m/'results.json').read_text(encoding='utf-8')) for m in models}
old = {m:json.loads((PREVIOUS/m/'results.json').read_text(encoding='utf-8')) for m in models}
for m in models:
    assert len(reports[m]['samples'])==3
    for row in reports[m]['samples']:
        a,sr=sf.read(OUT/m/row['file'])
        assert sr==24000 and a.ndim==1 and len(a)>0 and np.isfinite(a).all()
        assert abs(len(a)/sr-row['duration_seconds'])<.002
        if row['reference']=='short':assert row['reference_sha256']==old[m]['reference_sha256']
shutil.copy2(ROOT/'docs/generated/fish-local/references/clone-test-1-short.wav',OUT/'reference.wav')
for m, source, destination in [('omnivoice','neutral-sr','original'),('higgs','neutral','original-neutral'),('higgs','angry','original-angry')]:
    shutil.copy2(PREVIOUS/m/(source+'.wav'),OUT/m/(destination+'.wav'))
groups = {
 'omnivoice': [('Original','original'),('Higher guidance','guidance-3'),('More decoding steps','steps-64'),('Sentence by sentence','sentence-reset')],
 'higgs': [('Original neutral','original-neutral'),('Original angry','original-angry'),('Full-reference neutral','full-neutral'),('Full-reference angry','full-angry')]
}
timings={};cards=[]
for m,entries in groups.items():
    parts=[];cursor=0;timing=[]
    cards.append('<section><h2>'+('OmniVoice' if m=='omnivoice' else 'Higgs TTS 3')+' · individual samples</h2><div class="grid">')
    for label,stem in entries:
        a,sr=sf.read(OUT/m/(stem+'.wav'))
        if parts:parts.append(np.zeros(sr));cursor+=1
        timing.append(dict(label=label,start_seconds=round(cursor,3),duration_seconds=round(len(a)/sr,3)))
        parts.append(a);cursor+=len(a)/sr
        cards.append(f'<article><h3>{html.escape(label)}</h3><audio controls preload="none" src="{m}/{stem}.wav"></audio></article>')
    cards.append('</div></section>')
    sf.write(OUT/(m+'-comparison.wav'),np.concatenate(parts),24000,subtype='PCM_16')
    timings[m]=timing
(OUT/'comparison-sections.json').write_text(json.dumps(timings,indent=2),encoding='utf-8')
page='''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Voice consistency · OmniVoice and Higgs</title>
<style>body{font:17px system-ui;max-width:1100px;margin:40px auto;padding:0 24px;background:#f6f1e9;color:#302b27}h1{font-size:34px}h2{font-size:24px;margin-top:32px}h3{font-size:18px}p{line-height:1.55}article,.reel{background:white;border:1px solid #ded4c7;border-radius:14px;padding:20px;margin:16px 0}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(290px,1fr));gap:18px}audio{width:100%;margin:12px 0}a{color:#285b49}details{margin:24px 0}.order{font-weight:650}</style></head><body>
<h1>Does the same speaker stay present?</h1><p>OmniVoice was preferred for the voice, but changed speaker partway through the Serbian passage. Higgs emotions were effective, but anger changed the speaker too much. These tests target those two problems. None is marked as a verified fix.</p>
<details><summary>Original voice reference</summary><audio controls preload="none" src="reference.wav"></audio><p>The short reference used in the first audition. Higgs's full-reference tests use the complete 25-second recording.</p></details>
<p><b>Same text throughout:</b> Nisam očekivao da ćete to reći. Toliko toga želim da vam kažem. Dajte mi samo trenutak da saberem misli.</p>
<div class="reel"><h2>OmniVoice · watch for the change at “Toliko…”</h2><p class="order">Original → higher guidance → more decoding steps → sentence by sentence</p><audio controls preload="metadata" src="omnivoice-comparison.wav"></audio><p>The last test generates each sentence separately with the same reference. It may affect the pauses and natural flow, so judge those as well as the voice.</p></div>
<div class="reel"><h2>Higgs · can anger keep the speaker?</h2><p class="order">Original neutral → original angry → full-reference neutral → full-reference angry</p><audio controls preload="none" src="higgs-comparison.wav"></audio><p>Compare both neutral/angry pairs. Judge whether anger remains clear without sounding like another person.</p></div>
CARDS
<details><summary>Excluded experiment: lower-temperature anger</summary><p>Temperature 0.45 produced 24.84 seconds for this short passage, and automatic transcription recovered only the first sentence. Excluded from the main comparison for intelligibility review; retained here for inspection.</p><audio controls preload="none" src="higgs/lower-temp-angry.wav"></audio></details>
<details><summary>Experiment settings</summary><p>OmniVoice: original guidance 2 / 32 steps; test guidance 3 / 32 steps; test guidance 2 / 64 steps; sentence reset uses guidance 2 / 32 steps, reusing reference and seed 42 for each sentence, with 120 ms added between separately generated clips. All use Serbian language selection.</p><p>Higgs: original and full-reference tests use temperature 0.7, top-p 0.95 and top-k 50; excluded lower-temperature anger uses 0.45. Seed 42 throughout. Local community Transformers port. No pitch shifting or time stretching. One-second gaps between complete variants.</p><p>Transcription checks cannot establish speaker identity or emotion quality. Listening assessment remains necessary.</p></details><p><a href="../alternatives/index.html">Back to the original three-model comparison</a></p></body></html>'''.replace('CARDS',''.join(cards))
(OUT/'index.html').write_text(page,encoding='utf-8')
for file in ['index.html','reference.wav','omnivoice-comparison.wav','higgs-comparison.wav']:
    with urllib.request.urlopen('http://127.0.0.1:8793/voice-consistency/'+file,timeout=5) as response:assert response.status==200
(OUT/'verification.json').write_text(json.dumps(dict(new_samples=6,excluded_from_main=['higgs/lower-temp-angry.wav'],originals_preserved=True,audio_checked=True,identity_assessment='pending'),indent=2),encoding='utf-8')
print('Verified six new samples, three original controls, and two comparison reels.')
