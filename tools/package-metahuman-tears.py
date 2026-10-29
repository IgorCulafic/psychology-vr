"""Encode and decode-check the unchanged-audio native tear comparison."""
import json,subprocess,html
from pathlib import Path
import cv2,imageio_ffmpeg
ROOT=Path(__file__).resolve().parents[1];WORK=ROOT/'experiments/metahuman'
OUT=ROOT/'docs/generated/face-library-review/metahuman-tears';OUT.mkdir(exist_ok=True)
assert json.loads((WORK/'tears/render-report.json').read_text())['status']=='rendered'
take=next(t for t in json.loads((WORK/'speaking/manifest.json').read_text(encoding='utf-8')) if t['name']=='crying');count=take['frames']
folders=[WORK/'speaking/crying-emotion/render',WORK/'tears/crying-tears/render']
cmd=[imageio_ffmpeg.get_ffmpeg_exe(),'-y','-v','error']
for folder in folders:
    assert [int(p.stem) for p in sorted(folder.glob('*.png'))]==list(range(count))
    cmd+=['-framerate','30','-i',str(folder/'%06d.png')]
cmd+=['-i',take['audio']]
filters=[f"[{i}:v]pad=720:764:0:44:color=0x151a20,drawtext=fontfile=arial.ttf:text='{label}':fontcolor=white:fontsize=24:x=16:y=10[v{i}]" for i,label in enumerate(['Original crying','Wet cheeks and tear droplets'])]
filters.append('[v0][v1]hstack=inputs=2[v]')
cmd+=['-filter_complex',';'.join(filters),'-map','[v]','-map','2:a:0','-c:v','libx264','-crf','18','-pix_fmt','yuv420p','-c:a','aac','-t',str(count/30),'-movflags','+faststart',str(OUT/'comparison.mp4')]
subprocess.run(cmd,check=True,cwd='C:/Windows/Fonts')
cap=cv2.VideoCapture(str(OUT/'comparison.mp4'));frames=0
while True:
    ok,frame=cap.read()
    if not ok:break
    assert frame.shape[:2]==(764,1440)
    if frames==120:cv2.imwrite(str(OUT/'poster.jpg'),frame)
    frames+=1
cap.release();assert frames==count
subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-v','error','-i',str(OUT/'comparison.mp4'),'-map','0:a:0','-f','null','-'],check=True,capture_output=True)
(OUT/'verification.json').write_text(json.dumps({'frames':frames,'audio_decoded':True,'audio_source_sha256':take['source_sha256'],'effect':'native Unreal projected wet-film material, head-following transform keys'},indent=2))
(OUT/'index.html').write_text('''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Crying tear preview</title><style>body{background:#141b23;color:#edf1f4;font:17px system-ui;margin:28px}main{max-width:1440px;margin:auto}p{line-height:1.6}video{width:100%;border-radius:12px}a{color:#9cddff}</style><main><h1>Crying with tears</h1><p>Left: the approved speaking reaction. Right: the same animation and audio with glossy tear trails and moving droplets. The effect fades in, holds while he speaks, then fades out.</p><p>These are native 3D effects that follow the baked head movement, not marks added to the video. The projection adapts to the rendered skin surface; extreme expressions may still need placement adjustments.</p><video controls preload="metadata" src="comparison.mp4" poster="poster.jpg"></video><p>'''+html.escape(take['text'])+'''</p><p><a href="../metahuman-cast/">Review all four character models</a></p><p>This first tear placement is calibrated on Alex. Applying the effect to the other faces and integrating it into Unity are separate steps.</p></main></html>''',encoding='utf-8')
print(json.dumps({'frames':frames,'review':str(OUT)}))
