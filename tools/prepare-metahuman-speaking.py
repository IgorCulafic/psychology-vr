"""Reuse approved BF16 auditions for a controlled lip-sync comparison."""
import json, math, hashlib, wave, subprocess
from pathlib import Path
import imageio_ffmpeg
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'experiments/metahuman/speaking'
OUT.mkdir(parents=True,exist_ok=True)
results=json.loads((ROOT/'voices/igor_2026-10-03/emotion-validation/results.json').read_text(encoding='utf-8'))
manifest=[]
for emotion,preset in [('afraid','afraid'),('crying','crying'),('angry','anger')]:
    pref=json.loads((ROOT/f'voices/person_03/prepared/preferred_{preset}.json').read_text(encoding='utf-8'))
    if emotion=='angry':
        candidate=pref['approved_candidates'][0]
        # Repair presets retain the selected examples under a separate field.
        if 'text' not in candidate:
            candidates=pref.get('auditions',pref.get('examples',[]))
            candidate=next((x for x in candidates if x.get('variant')==pref.get('default_variant')),candidate)
        audio=candidate.get('audio',candidate.get('file'))
        text=candidate.get('text','')
    else:
        audio=pref['audition_audio'];text=''
    source=ROOT/audio
    if not text:
        matches=[r for r in results if str(r.get('audio',r.get('file',''))).replace('\\','/').endswith(source.name) and (r.get('speaker',r.get('person'))=='person_03' or 'person_03' in str(r))]
        if matches:text=matches[0].get('text','')
    target=OUT/(emotion+'.wav')
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-y','-v','error','-i',str(source),'-ac','1','-c:a','pcm_s16le',str(target)],check=True)
    with wave.open(str(target)) as wav: duration=wav.getnframes()/wav.getframerate()
    peak=json.loads((ROOT/f'docs/generated/face-library-review/{dict(afraid="04-afraid",crying="07-crying",angry="08-angry")[emotion]}/verification.json').read_text())['peak_frame']
    frames=math.ceil(duration*30)
    source_frames=json.loads((ROOT/f'experiments/metahuman/media/{emotion}/metahuman-curves.json').read_text())['frames']
    start=max(0,min(peak-frames//2,len(source_frames)-frames))
    manifest.append({'name':emotion,'speaker':'person_03','precision':'bf16','source_audio':str(source.relative_to(ROOT)),
        'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'audio':str(target),'text':text,
        'seconds':duration,'frames':frames,'fps':30,'reaction_start_frame':start,'reaction_frames':len(source_frames),
        'upper_face_weight':0.8,'source_preset':str((ROOT/f'voices/person_03/prepared/preferred_{preset}.json').relative_to(ROOT))})
(OUT/'manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False),encoding='utf-8')
print(json.dumps(manifest,indent=2,ensure_ascii=True))
