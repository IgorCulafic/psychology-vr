"""Prepare original-resolution mono image sequences for local MetaHuman processing."""
import hashlib
import json
from pathlib import Path
import subprocess
import imageio_ffmpeg

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'experiments/metahuman/media'
rows=[]
for number,name in [(4,'afraid'),(7,'crying'),(8,'angry')]:
    source=ROOT/f'livelink/recordings/recordings_all/MySlate_{number}/front-1-wide.mp4'
    dest=OUT/name;dest.mkdir(parents=True,exist_ok=True)
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-y','-v','error','-i',str(source),'-vf','fps=30',
                    '-q:v','2','-start_number','0',str(dest/'%06d.jpg')],check=True)
    rows.append({'name':name,'video':str(source),'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
                 'frames_folder':str(dest),'frames':len(list(dest.glob('*.jpg'))),'fps':30,
                 'method':'Original-resolution video resampled to 30fps; no MediaPipe weights; no depth; local processing'})
(OUT/'manifest.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
print(json.dumps(rows,indent=2))
