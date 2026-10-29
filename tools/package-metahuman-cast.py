"""Package verified local cast clips. The shared audio isolates facial retargeting."""
import json,subprocess,html
from pathlib import Path
import cv2,imageio_ffmpeg
ROOT=Path(__file__).resolve().parents[1];WORK=ROOT/'experiments/metahuman'
OUT=ROOT/'docs/generated/face-library-review/metahuman-cast';OUT.mkdir(exist_ok=True)
ffmpeg=imageio_ffmpeg.get_ffmpeg_exe()
assert json.loads((WORK/'cast/render-report.json').read_text())['status']=='rendered'
cast=json.loads((WORK/'cast.json').read_text())['characters']
takes=json.loads((WORK/'speaking/manifest.json').read_text(encoding='utf-8'))
report=[];cards=[]
for char in cast:
    clips=[]
    for take in takes:
        mood=take['name'];count=take['frames'];name=char['id']+'-'+mood
        variant='shout' if mood=='angry' else 'emotion'
        folder=WORK/'cast'/(char['id']+'-'+mood+'-'+variant)/'render'
        if char['id']=='alex':
            folder=WORK/('anger-blend/angry-shout/render' if mood=='angry' else 'speaking/'+mood+'-emotion/render')
        assert [int(p.stem) for p in sorted(folder.glob('*.png'))]==list(range(count)),str(folder)
        output=OUT/(name+'.mp4')
        subprocess.run([ffmpeg,'-y','-v','error','-framerate','30','-i',str(folder/'%06d.png'),'-i',take['audio'],'-map','0:v','-map','1:a','-c:v','libx264','-crf','18','-pix_fmt','yuv420p','-c:a','aac','-t',str(count/30),'-movflags','+faststart',str(output)],check=True)
        cap=cv2.VideoCapture(str(output));frames=0
        while True:
            ok,frame=cap.read()
            if not ok:break
            assert frame.shape[:2]==(720,720)
            if frames==count//3:cv2.imwrite(str(OUT/(name+'.jpg')),frame)
            frames+=1
        cap.release();assert frames==count
        subprocess.run([ffmpeg,'-v','error','-i',str(output),'-map','0:a:0','-f','null','-'],check=True,capture_output=True)
        report.append({'name':name,'frames':frames,'audio_decoded':True,'audio_source':take['audio'],'preset':char['preset']})
        clips.append(f'<option value="{name}">{mood.title()}</option>')
    initial=char['id']+'-afraid'
    cards.append(f'''<article><h2>{char['label']} <small>{char['scenario']}</small></h2><p>{char['preset']} preset · assigned voice: {html.escape(char['voice'])}</p><select aria-label="Emotion for {char['label']}">{''.join(clips)}</select><video controls preload="metadata" src="{initial}.mp4" poster="{initial}.jpg"></video></article>''')
(OUT/'index.html').write_text('''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Four MetaHuman characters</title><style>body{background:#141b23;color:#edf1f4;font:17px system-ui;margin:28px}main{max-width:1520px;margin:auto}p{line-height:1.6}section{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:20px}article{background:#222c36;padding:18px;border-radius:12px}video{width:100%;margin-top:12px}small{font-size:17px;font-weight:400;color:#b1c6d7}select{font:inherit;padding:8px;color:white;background:#141b23}a{color:#9cddff}@media(max-width:800px){section{grid-template-columns:1fr}}</style><main><h1>Four male MetaHuman auditions</h1><p>Choose fear, crying or anger on each character. Each identity has its own baked face and neck animation. Hands and torso are held still.</p><p><strong>Shared test audio:</strong> these comparisons deliberately reuse the same Person 3 audio and lip-sync, so appearance is the only change. The assigned production voices are preserved in the cast configuration; this page does not switch to those voices.</p><p><a href="../metahuman-tears/">Crying with tears comparison</a> · <a href="../metahuman-anger-blend/">Anger blend comparison</a></p><section>'''+''.join(cards)+'''</section><p>Local authoring previews; not yet integrated into Unity. Clothing and hair are the initial Epic preset choices.</p></main><script>document.querySelectorAll('select').forEach(s=>s.onchange=()=>{const v=s.closest('article').querySelector('video');v.pause();v.src=s.value+'.mp4';v.poster=s.value+'.jpg';v.load()});document.querySelectorAll('video').forEach(v=>v.addEventListener('play',()=>document.querySelectorAll('video').forEach(o=>{if(o!==v)o.pause()})));</script></html>''',encoding='utf-8')
(OUT/'verification.json').write_text(json.dumps(report,indent=2))
print(json.dumps({'clips':len(report),'review':str(OUT)}))
