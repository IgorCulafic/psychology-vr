"""Render matched source/current/four-candidate Unity facial comparisons."""
from concurrent.futures import ThreadPoolExecutor
import json
import subprocess
from pathlib import Path
import cv2
import imageio_ffmpeg
import hashlib

ROOT=Path(__file__).resolve().parents[1]
REVIEW=ROOT/'docs/generated/face-library-review'
OUT=REVIEW/'candidates/audition'
TAKES=['01-neutral','04-afraid','07-crying','08-angry','11-happy']
EXE=ROOT/'unity/Builds/RocketboxPreview/RocketboxPreview.exe'
BUILD_ID=hashlib.sha256(b''.join((EXE.parent/'RocketboxPreview_Data'/file).read_bytes()
    for file in ['Managed/Assembly-CSharp.dll','level0','sharedassets0.assets'])).hexdigest()

def render(job):
    take,n=job
    dest=OUT/take/f'candidate-{n}'
    dest.mkdir(parents=True,exist_ok=True)
    log=dest/'render.log'
    data=json.loads((REVIEW/take/'performance.json').read_text())
    expected=len(data['frames'])
    stamp=dest/'build-id.txt'
    if not(log.exists() and stamp.exists() and stamp.read_text()==BUILD_ID and 'ROCKETBOX_RENDER_OK' in log.read_text(errors='replace') and len(list(dest.glob('*.jpg')))==expected):
        startup=subprocess.STARTUPINFO();startup.dwFlags|=subprocess.STARTF_USESHOWWINDOW;startup.wShowWindow=0
        subprocess.run([str(EXE),'--data',str(REVIEW/take),'--candidate',str(n),'--output',str(dest),
                        '-screen-width','400','-screen-height','400','-screen-fullscreen','0','-logFile',str(log)],
                       startupinfo=startup,check=True,timeout=240)
    assert 'ROCKETBOX_RENDER_OK' in log.read_text(errors='replace'),str(log)
    assert len(list(dest.glob('*.jpg')))==expected
    stamp.write_text(BUILD_ID)
    print('RENDERED',take,n,expected,flush=True)

def encode(take):
    folder=OUT/take;data=json.loads((REVIEW/take/'performance.json').read_text())
    movie=folder/'comparison.mp4'
    inputs=[REVIEW/take/'face',REVIEW/take/'unity-frames']+[folder/f'candidate-{n}' for n in range(1,5)]
    cmd=[imageio_ffmpeg.get_ffmpeg_exe(),'-y','-v','error']
    for path in inputs:cmd+=['-framerate','30','-i',str(path/'%05d.jpg')]
    cmd+=['-i',str(ROOT/f'livelink/recordings/recordings_all/MySlate_{int(take[:2])}/front-1-wide.mp4')]
    labels=['Your recording','Current Jumper','Male 01 - striped polo','Male 02 - beige sweater','Male 03 - grey jacket','Male 04 - dark jacket']
    filters=[]
    for i,label in enumerate(labels):
        filters.append(f'[{i}:v]scale=400:400,pad=400:432:0:32:color=0x151a20,drawtext=fontfile=arial.ttf:text=\'{label}\':fontcolor=white:fontsize=17:x=12:y=8[v{i}]')
    filters.append('[v0][v1][v2][v3][v4][v5]xstack=inputs=6:layout=0_0|400_0|800_0|0_432|400_432|800_432[v]')
    cmd+=['-filter_complex',';'.join(filters),'-map','[v]','-map','6:a:0?','-c:v','libx264','-threads','4','-crf','20','-pix_fmt','yuv420p','-c:a','aac','-t',str(data['duration']),'-movflags','+faststart',str(movie)]
    subprocess.run(cmd,check=True,timeout=240,cwd='C:/Windows/Fonts')
    cap=cv2.VideoCapture(str(movie));count=0
    while True:
        ok,frame=cap.read()
        if not ok:break
        assert frame.shape[:2]==(864,1200)
        count+=1
    cap.release();assert count==len(data['frames']),(take,count,len(data['frames']))
    # Preserve an actual rendered frame for inspection and the video poster.
    peak=json.loads((REVIEW/take/'verification.json').read_text())['peak_frame']
    cap=cv2.VideoCapture(str(movie));cap.set(cv2.CAP_PROP_POS_FRAMES,peak);ok,frame=cap.read();cap.release()
    assert ok;cv2.imwrite(str(folder/'poster.jpg'),frame)
    result={'take':take,'frames':count,'duration':data['duration'],'candidate_count':4,'comparison':'Same extracted face weights; baseline approximate CC mapping vs candidate direct ARKit; head rotation on, gaze and body motion off.'}
    (folder/'verification.json').write_text(json.dumps(result,indent=2))
    print('VERIFIED',take,count,flush=True)
    return result

if __name__=='__main__':
    OUT.mkdir(parents=True,exist_ok=True)
    with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(render,[(take,n) for take in TAKES for n in range(1,5)]))
    results=[encode(take) for take in TAKES]
    (OUT/'results.json').write_text(json.dumps(results,indent=2))
    cards=''.join(f'<article id="{r["take"]}"><h2>{r["take"][3:].capitalize()}</h2><video controls preload="none" poster="{r["take"]}/poster.jpg" src="{r["take"]}/comparison.mp4"></video></article>' for r in results)
    (OUT/'index.html').write_text('''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Four character facial audition</title><style>body{background:#141b23;color:#edf1f4;font:17px system-ui;margin:32px}main{max-width:1250px;margin:auto}p{line-height:1.6}article{margin:32px 0;padding:18px;background:#222c36;border-radius:12px}video{width:100%;max-height:80vh}a{color:#9cddff}</style><main><h1>Four character facial audition</h1><p>Same recording, same timing. Top row: your recording, current Jumper, male 01. Bottom row: male 02, male 03, male 04. Audio is your original recording.</p><p>Direct ARKit transfer on the four candidates, approximate CC mapping on Jumper. Head rotation is included. Torso movement, head translation and gaze remain off in every character for this controlled comparison. These are raw transfers; tracking mistakes can affect all models.</p>'''+cards+'<p><a href="../">Candidate details</a> · Rocketbox assets: Copyright (c) 2020 Microsoft, MIT.</p></main></html>',encoding='utf-8')
    entry=OUT.parent/'index.html'
    if entry.exists():
        html=entry.read_text(encoding='utf-8')
        if 'audition/' not in html:
            entry.write_text(html.replace('<section>','<p><a href="audition/">Watch the five facial animation comparisons</a></p><section>',1),encoding='utf-8')
    print('AUDITION_COMPLETE',flush=True)
