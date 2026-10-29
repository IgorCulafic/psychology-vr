"""Encode the Unity frame-clock auditions with their exact approved audio tracks."""
import hashlib,html,json,subprocess
from pathlib import Path
import cv2
ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'experiments/metahuman/unity-movies'
OUT=ROOT/'docs/generated/face-library-review/metahuman-unity-videos'
FFMPEG=ROOT/'.tools/dereverb-deps/bin/ffmpeg.exe'
OUT.mkdir(parents=True,exist_ok=True)
cast=json.loads((ROOT/'experiments/metahuman/cast.json').read_text())['characters']
rows=[]
for person in cast:
 cid=person['id'];src=WORK/cid;take=json.loads((src/'take.json').read_text())
 frames=take['frames'];fps=take['fps'];duration=frames/fps
 files=sorted(src.glob('*.jpg'))
 assert [int(p.stem) for p in files]==list(range(frames)),f'Missing/stale frames: {cid}'
 assert take['jawRange']>.1,f'Static speech: {cid}'
 voice=ROOT/f'unity/Assets/PsychologyVR/Art/MetaHumans/{cid}/audio/anger.wav'
 provenance=json.loads((voice.parent/'provenance.json').read_text())
 assert hashlib.sha256(voice.read_bytes()).digest()==hashlib.sha256((ROOT/provenance['source']).read_bytes()).digest()
 dst=OUT/cid;dst.mkdir(exist_ok=True)
 labels=[('Outfit / resting pose',0,4),('Fear / recorded face and neck',4,9),('Crying / tears',9,15),('Anger / assigned voice',15,duration)]
 filters=[f"drawtext=fontfile=arial.ttf:text='{person['label']} - {label}':fontcolor=white:fontsize=23:box=1:boxcolor=black@0.65:boxborderw=12:x=24:y=24:enable='gte(t,{a})*lt(t,{b})'" for label,a,b in labels]
 delay=round(take['speechStart']*1000)
 subprocess.run([str(FFMPEG),'-y','-v','error','-framerate',str(fps),'-i',str(src/'%05d.jpg'),'-i',str(voice),
  '-filter_complex',f"[0:v]{','.join(filters)}[v];[1:a]adelay={delay}:all=1,apad[a]",'-map','[v]','-map','[a]',
  '-t',str(duration),'-c:v','libx264','-crf','19','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k','-movflags','+faststart',str(dst/'preview.mp4')],cwd='C:/Windows/Fonts',check=True)
 cap=cv2.VideoCapture(str(dst/'preview.mp4'));count=0
 while True:
  ok,frame=cap.read()
  if not ok:break
  assert frame.shape[:2]==(960,960)
  if count==2*fps:cv2.imwrite(str(dst/'outfit.jpg'),frame)
  if count==18*fps:cv2.imwrite(str(dst/'poster.jpg'),frame)
  count+=1
 cap.release();assert count==frames,(cid,count,frames)
 subprocess.run([str(FFMPEG),'-v','error','-i',str(dst/'preview.mp4'),'-map','0:a:0','-f','null','-'],check=True,capture_output=True)
 revision=hashlib.sha256((dst/'preview.mp4').read_bytes()).hexdigest()[:12]
 rows.append(dict(person,seconds=round(duration,2),frames=count,audio_source=provenance['source'],audio_delay_seconds=take['speechStart'],jaw_range=take['jawRange'],audio_decoded=True,revision=revision))
 print(cid,count,round(duration,2),flush=True)
cards=''.join(f'''<article id="{r['id']}"><h2>{html.escape(r['label'])} <span>{html.escape(r['scenario'])} · {r['seconds']} seconds</span></h2><video controls playsinline preload="metadata" poster="{r['id']}/poster.jpg?v={r['revision']}" src="{r['id']}/preview.mp4?v={r['revision']}"></video><nav><button data-time="0">Outfit</button><button data-time="4">Fear</button><button data-time="9">Crying</button><button data-time="15">Speaking</button><a href="{r['id']}/preview.mp4?v={r['revision']}" download>Download video</a></nav></article>''' for r in rows)
(OUT/'index.html').write_text('''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Clothed MetaHumans · animation and speech</title><style>body{background:#121b20;color:#eef3f1;font:17px system-ui;max-width:1300px;margin:40px auto;padding:0 24px}h1{font-size:36px}p{color:#bdcbc9;line-height:1.6}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(440px,1fr));gap:24px}article{background:#1c292f;border:1px solid #33444b;border-radius:14px;overflow:hidden}h2{margin:20px;font-size:25px}h2 span{display:block;font-size:15px;color:#b6c9c5;font-weight:400;margin-top:6px}video{display:block;width:100%}nav{display:flex;flex-wrap:wrap;gap:10px;padding:18px}button,a{font:inherit;color:#bce8df}button{background:#2b4544;border:1px solid #48716b;border-radius:6px;padding:7px 10px;cursor:pointer}a{align-self:center;margin-left:auto}@media(max-width:540px){main{display:block}article{margin-bottom:20px}}</style><h1>Clothes, expressions and speech</h1><p>Four short videos captured in Unity at normal animation speed. Each starts with the seated outfit, then shows fear, crying with tears, and an angry spoken line using that character's approved voice.</p><p>The first 15 seconds are silent facial acting. Speech starts at 0:15. These use existing approved audio, so they test animation and lip sync rather than new speech generation. Torso and hands remain in their resting pose.</p><main>'''+cards+'''</main><script>document.querySelectorAll('button').forEach(b=>b.onclick=()=>{const v=b.closest('article').querySelector('video');document.querySelectorAll('video').forEach(x=>{if(x!==v)x.pause()});v.currentTime=Number(b.dataset.time);v.play()});document.querySelectorAll('video').forEach(v=>v.addEventListener('play',()=>document.querySelectorAll('video').forEach(x=>{if(x!==v)x.pause()})))</script></html>''',encoding='utf-8')
(OUT/'verification.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
print('http://127.0.0.1:8798/metahuman-unity-videos/')
