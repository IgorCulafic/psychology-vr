"""Package an unchanged-audio anger mouth-blend comparison."""
import json,subprocess,html
from pathlib import Path
import cv2,imageio_ffmpeg
ROOT=Path(__file__).resolve().parents[1];WORK=ROOT/'experiments/metahuman/anger-blend'
OUT=ROOT/'docs/generated/face-library-review/metahuman-anger-blend'
assert json.loads((WORK/'render-report.json').read_text())['status']=='rendered'
take=json.loads((WORK/'manifest.json').read_text(encoding='utf-8'))[0];count=take['frames']
OUT.mkdir(parents=True,exist_ok=True)
folders=[ROOT/'experiments/metahuman/speaking/angry-emotion/render',WORK/'angry-balanced/render',WORK/'angry-shout/render']
cmd=[imageio_ffmpeg.get_ffmpeg_exe(),'-y','-v','error']
for folder in folders:
    assert [int(p.stem) for p in sorted(folder.glob('*.png'))]==list(range(count)),str(folder)
    cmd+=['-framerate','30','-i',str(folder/'%06d.png')]
cmd+=['-i',take['audio']]
labels=['Previous blend','A - expressive anger','B - yelling-style blend']
filters=[f"[{i}:v]scale=600:600,pad=600:642:0:42:color=0x151a20,drawtext=fontfile=arial.ttf:text='{label}':fontcolor=white:fontsize=22:x=14:y=10[v{i}]" for i,label in enumerate(labels)]
filters.append('[v0][v1][v2]hstack=inputs=3[v]')
cmd+=['-filter_complex',';'.join(filters),'-map','[v]','-map','3:a:0','-c:v','libx264','-crf','18','-pix_fmt','yuv420p','-c:a','aac','-t',str(count/30),'-movflags','+faststart',str(OUT/'comparison.mp4')]
subprocess.run(cmd,check=True,cwd='C:/Windows/Fonts')
capture=cv2.VideoCapture(str(OUT/'comparison.mp4'));decoded=0
while True:
    ok,frame=capture.read()
    if not ok:break
    assert frame.shape[:2]==(642,1800)
    if decoded==count//3:cv2.imwrite(str(OUT/'poster.jpg'),frame)
    decoded+=1
capture.release();assert decoded==count
subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-v','error','-i',str(OUT/'comparison.mp4'),'-map','0:a:0','-f','null','-'],check=True,capture_output=True)
(OUT/'index.html').write_text('''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Anger mouth blend</title><style>body{background:#141b23;color:#edf1f4;font:17px system-ui;margin:32px}main{max-width:1800px;margin:auto}p{line-height:1.6}video{width:100%;max-height:80vh;background:#000;border-radius:12px}a{color:#9cddff}.line{font-size:21px}</style><main><h1>Anger while speaking</h1><p>Left: previous blend. Middle: restrained angry mouth. Right: stronger yelling-style mouth.</p><p>The same approved Person 3 audio plays for all three views. The stronger versions bring back recorded jaw opening, upper-lip raise, lower-lip depression and mouth tension. Added movement eases off when the speech asks for closure or a rounded mouth. The brow and neck motion stay the same.</p><p class="line">'''+html.escape(take['text'])+'''</p><video controls preload="metadata" src="comparison.mp4" poster="poster.jpg"></video><p>This isolates the animation change. The voice has not been made louder or changed into a shout. Listen for whether consonants remain readable and watch for a mouth that stays open too long.</p><p><a href="../metahuman-speaking/">Previous speaking tests</a></p></main></html>''',encoding='utf-8')
verification={'frames':decoded,'fps':30,'audio_decoded':True,'source_audio_sha256':take['source_sha256'],'audio_changed':False,'variants':json.loads((WORK/'build-report.json').read_text())['sequences']}
(OUT/'verification.json').write_text(json.dumps(verification,indent=2))
print(json.dumps({'frames':decoded,'audio_decoded':True,'review':str(OUT)}))
