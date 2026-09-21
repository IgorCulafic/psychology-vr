"""Create a private listening page and Unity replay from prepared sentence clips."""
import html
import json
from pathlib import Path
import shutil
import uuid
import wave

ROOT=Path(__file__).resolve().parents[1]
source=ROOT/'services/.runtime/sentence-review/replies.json'
report=json.loads(source.read_text(encoding='utf-8'))
out=ROOT/'docs/generated/fish-local/delivery-review';out.mkdir(parents=True,exist_ok=True)
replay={'turns':[]};cards=[]
for turn in report['turns']:
    segments=turn['reply']['segments'];combined=[]
    for index in range(0,len(segments),2):
        pair=segments[index:index+2];first=pair[0];frames=[];cues=[];offset=0.
        for segment in pair:
            path=ROOT/'services/.runtime'/Path(segment['audio_url']).name
            with wave.open(str(path)) as audio:
                rate=audio.getframerate();channels=audio.getnchannels();width=audio.getsampwidth()
                assert (rate,channels,width)==(24000,1,2)
                raw=audio.readframes(audio.getnframes());frames.append(raw)
                for cue in segment.get('mouth_cues',[]):cues.append(dict(cue,start=cue['start']+offset,end=cue['end']+offset))
                offset+=audio.getnframes()/rate
            frames.append(bytes(int(rate*.2)*width));offset+=.2
        name=uuid.uuid4().hex+'.wav';runtime=ROOT/'services/.runtime'/name
        with wave.open(str(runtime),'wb') as audio:
            audio.setparams((channels,width,rate,0,'NONE','not compressed'));audio.writeframes(b''.join(frames))
        listening=first['emotion']+'.wav';shutil.copyfile(runtime,out/listening)
        merged=dict(first,text=' '.join(s['text'] for s in pair),segment_id='review-'+first['emotion'],
                    audio_url='/audio/'+name,mouth_cues=cues,audio_duration_seconds=offset)
        combined.append(merged)
        capture=source.parent/('performance-beat-'+str(len(cards)+1)+'.png')
        portrait=''
        if capture.is_file():
            image_name=first['emotion']+'.png';shutil.copyfile(capture,out/image_name)
            portrait='<a href="'+image_name+'"><div class="portrait"><img alt="'+html.escape(first['emotion'])+' in Unity" src="'+image_name+'"></div></a>'
        cards.append('<article><h2>'+html.escape(first['emotion'])+' · '+str(round(first['intensity']*100))+'%</h2>'+portrait+'<p>'+html.escape(merged['text'])+'</p><audio controls preload="none" src="'+listening+'"></audio></article>')
    replay['turns'].append(dict(name=turn['name'],source='authored-bf16-emotion-comparison',reply=dict(segments=combined)))
reference=ROOT/'docs/generated/fish-local/references/clone-test-1.wav'
shutil.copyfile(reference,out/'reference.wav')
(source.parent/'emotion-replay.json').write_text(json.dumps(replay,ensure_ascii=False,indent=2),encoding='utf-8')
(out/'index.html').write_text('''<!doctype html><meta charset="utf-8"><title>16-bit delivery review</title>
<style>body{font:18px/1.6 system-ui;background:#17211f;color:#edf0e8;max-width:960px;margin:48px auto;padding:0 24px}h1{line-height:1.2}main{display:grid;grid-template-columns:1fr 1fr;gap:20px}article{background:#25332e;padding:22px;border-radius:16px}audio{width:100%}.portrait{aspect-ratio:1.5;overflow:hidden;border-radius:10px}.portrait img{width:100%;height:100%;object-fit:cover;transform:scale(2.5);transform-origin:50% 60%}small{color:#bccdc4}@media(max-width:650px){main{grid-template-columns:1fr}}</style>
<h1>16-bit emotional delivery</h1><p>Same full reference, BF16 Higgs, seed 42 and temperature 0.70. These are authored comparison lines, not spontaneous model responses.</p>
<p>Compare restrained frustration with confrontation, sadness with withdrawal, and unease with present fear. Listen for a consistent speaker and clear č / ć / š / ž sounds.</p>
<h2>Your reference</h2><audio controls preload="none" src="reference.wav"></audio><main>'''+''.join(cards)+'''</main><p><small>Each comparison joins two generated sentences with a short pause for convenient listening. This page does not reproduce real-time generation gaps. Pronunciation and identity still require your judgement.</small></p>''',encoding='utf-8')
print(out/'index.html')
