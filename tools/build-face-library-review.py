"""Extract the 20 shared facial takes and render isolated Unity comparisons."""
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import cv2
import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/generated/face-library-review'
SOURCE=ROOT/'livelink/recordings/recordings_all'
EMOTIONS=['neutral','calm','anxious','afraid','panicked','sad','crying','angry','frustrated','disgusted','happy','relieved','surprised','ashamed','guilty','confused','skeptical','hopeful','despondent','numb']

def process(index):
    emotion=EMOTIONS[index-1];folder=OUT/f'{index:02d}-{emotion}';folder.mkdir(parents=True,exist_ok=True)
    video=SOURCE/f'MySlate_{index}'/'front-1-wide.mp4'
    env=dict(os.environ,MPLCONFIGDIR=str(ROOT/'.cache/matplotlib'))
    if not (folder/'extraction-report.json').exists():
        with (folder/'extraction.log').open('w') as log:
            subprocess.run([sys.executable,str(ROOT/'tools/extract-livelink-video.py'),str(video),'--output',str(folder)],env=env,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
    report=json.loads((folder/'extraction-report.json').read_text())
    assert report['source_sha256']==hashlib.sha256(video.read_bytes()).hexdigest()
    take=json.loads((folder/'performance.json').read_text())
    logpath=folder/'unity-render.log'
    if not logpath.exists() or 'RECORDED_FACE_RENDER_OK' not in logpath.read_text(errors='replace'):
        startup=subprocess.STARTUPINFO();startup.dwFlags|=subprocess.STARTF_USESHOWWINDOW;startup.wShowWindow=0
        subprocess.run([str(ROOT/'unity/Builds/LiveLinkPreview/LiveLinkPreview.exe'),'--data',str(folder),'--render','-screen-width','800','-screen-height','600','-screen-fullscreen','0','-logFile',str(logpath)],startupinfo=startup,check=True,timeout=240)
    assert 'RECORDED_FACE_RENDER_OK' in logpath.read_text(errors='replace')
    assert len(list((folder/'unity-frames').glob('*.jpg')))==len(take['frames'])
    movie=folder/'comparison.mp4'
    if not movie.exists():
        subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-y','-v','error','-framerate','30','-i',str(folder/'face/%05d.jpg'),'-framerate','30','-i',str(folder/'unity-frames/%05d.jpg'),'-i',str(video),'-filter_complex','[0:v][1:v]hstack=inputs=2[v]','-map','[v]','-map','2:a:0?','-c:v','libx264','-threads','2','-crf','20','-pix_fmt','yuv420p','-c:a','aac','-t',str(take['duration']),'-movflags','+faststart',str(movie)],check=True,timeout=180)
    cap=cv2.VideoCapture(str(movie));count=0
    while True:
        ok,frame=cap.read()
        if not ok:break
        assert frame.shape[:2]==(600,1200)
        count+=1
    cap.release();assert count==len(take['frames']),(index,count,len(take['frames']))
    values=np.array([f['weights'] for f in take['frames']]);valid=np.array([f['valid'] for f in take['frames']])
    names=take['names'];use=[j for j,n in enumerate(names) if n!='_neutral' and not n.startswith('eyeLook')]
    baseline=np.median(values[:min(30,len(values))],axis=0)
    # Representative motion, not an automatic emotion/acting score.
    activity=np.mean(np.abs(values[:,use]-baseline[use]),axis=1)
    peak=int(np.argmax(np.where(valid,activity,0)))
    indices=sorted(set([min(30,count-1),count//3,peak,2*count//3,max(0,count-31)]))
    contact=Image.new('RGB',(1200,630*len(indices)),(20,28,36));draw=ImageDraw.Draw(contact)
    for row,n in enumerate(indices):
        contact.paste(Image.open(folder/'face'/f'{n:05d}.jpg'),(0,row*630+30))
        contact.paste(Image.open(folder/'unity-frames'/f'{n:05d}.jpg'),(600,row*630+30))
        draw.text((10,row*630+8),f'{index:02d} {emotion} | {n/30:.2f}s | source left / Unity right',fill='white')
    contact.save(folder/'contact.jpg')
    row={'index':index,'emotion':emotion,'folder':folder.name,'source':str(video.relative_to(ROOT)).replace('\\','/'),
         'duration':take['duration'],'frames':count,'detected_frames':report['detected_frames'],
         'tracking_percent':round(100*report['detected_frames']/count,2),'head_rotation_max_degrees':round(report['head_rotation_max_degrees'],1),
         'peak_frame':peak,'peak_time':round(peak/30,2),'method':take['method'],
         'source_sha256':report['source_sha256'],'review_status':'needs_listening_and_visual_review'}
    (folder/'verification.json').write_text(json.dumps(row,indent=2))
    return row

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    rows=[]
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs={pool.submit(process,i):i for i in range(1,21)}
        for job in as_completed(jobs):
            row=job.result();rows.append(row);rows.sort(key=lambda r:r['index'])
            (OUT/'results.json').write_text(json.dumps(rows,indent=2))
            print(json.dumps({'completed':len(rows),**row}),flush=True)
    print('ALL_FACE_COMPARISONS_VERIFIED',flush=True)

if __name__=='__main__':main()
