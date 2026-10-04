"""Package synchronized lip-only/emotional speaking comparisons."""
import html,json,subprocess,shutil
from pathlib import Path
import cv2,imageio_ffmpeg
ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'experiments/metahuman/speaking'
OUT=ROOT/'docs/generated/face-library-review/metahuman-speaking'
def main():
    status=json.loads((WORK/'render-report.json').read_text())
    if status.get('status')!='rendered' or not status.get('success'):raise RuntimeError('Complete speaking renders first')
    OUT.mkdir(parents=True,exist_ok=True)
    records=[]
    for take in json.loads((WORK/'manifest.json').read_text(encoding='utf-8')):
        name=take['name'];count=take['frames'];folder=OUT/name;folder.mkdir(exist_ok=True)
        for variant in ['lips','emotion']:
            files=sorted((WORK/(name+'-'+variant)/'render').glob('*.png'))
            if [int(f.stem) for f in files]!=list(range(count)):raise RuntimeError('Missing or stale frames: '+name+'-'+variant)
        command=[imageio_ffmpeg.get_ffmpeg_exe(),'-y','-v','error']
        for variant in ['lips','emotion']:command+=['-framerate','30','-i',str(WORK/(name+'-'+variant)/'render/%06d.png')]
        command+=['-i',take['audio'],'-filter_complex',
            "[0:v]pad=720:764:0:44:color=0x151a20,drawtext=fontfile=arial.ttf:text='Speech only':fontcolor=white:fontsize=23:x=16:y=10[a];[1:v]pad=720:764:0:44:color=0x151a20,drawtext=fontfile=arial.ttf:text='Speech + recorded emotion and neck':fontcolor=white:fontsize=23:x=16:y=10[b];[a][b]hstack=inputs=2[v]",
            '-map','[v]','-map','2:a:0','-c:v','libx264','-crf','19','-pix_fmt','yuv420p','-c:a','aac','-t',str(count/30),'-movflags','+faststart',str(folder/'comparison.mp4')]
        subprocess.run(command,cwd='C:/Windows/Fonts',check=True,timeout=180)
        capture=cv2.VideoCapture(str(folder/'comparison.mp4'));frames=0
        while True:
            ok,frame=capture.read()
            if not ok:break
            assert frame.shape[:2]==(764,1440)
            if frames==count//2:cv2.imwrite(str(folder/'poster.jpg'),frame)
            frames+=1
        capture.release()
        if frames!=count:raise RuntimeError((name,frames,count))
        subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-v','error','-i',str(folder/'comparison.mp4'),'-map','0:a:0','-f','null','-'],check=True,capture_output=True)
        shutil.copyfile(take['audio'],folder/'voice.wav')
        records.append({'name':name,'frames':frames,'seconds':count/30,'text':take['text'],'voice':'Approved Person 3 BF16 Higgs sample','source_sha256':take['source_sha256'],'audio_decoded':True})
    cards=''.join(f'''<article id="{r['name']}"><h2>{r['name'].capitalize()}</h2><p class="line">{html.escape(r['text'])}</p><video controls preload="metadata" poster="{r['name']}/poster.jpg" src="{r['name']}/comparison.mp4"></video><p><a href="{r['name']}/voice.wav">Listen to the voice alone</a></p></article>''' for r in records)
    (OUT/'index.html').write_text('''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>MetaHuman speaking test</title><style>body{background:#141b23;color:#edf1f4;font:17px system-ui;margin:32px}main{max-width:1450px;margin:auto}p{line-height:1.6}article{margin:28px 0;padding:20px;background:#222c36;border-radius:12px}video{width:100%;max-height:80vh}a{color:#9cddff}.line{font-size:20px}</style><main><h1>Speaking with emotion</h1><p>The same approved Person 3 voice plays once for both views. Left: audio-driven lip sync. Right: the same lip sync with recorded brow, eyelid and nose expression at 80% strength, plus recorded neck movement.</p><p>Jaw, lips and tongue follow the new speech rather than the original recording. The reaction uses a continuous slice at its original speed. Torso and hand acting are deferred.</p><p>Listen for clear syllables and watch whether the mouth, expression and voice agree. This is an offline animation audition, not a live conversation or a runtime latency test.</p>'''+cards+'<p><a href="../metahuman-neck/">Previous face and neck comparison</a></p></main></html>',encoding='utf-8')
    (OUT/'verification.json').write_text(json.dumps(records,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps(records,indent=2,ensure_ascii=True))
if __name__=='__main__':main()
