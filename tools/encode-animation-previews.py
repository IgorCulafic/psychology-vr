"""Encode Unity's recorded frames. Labels use Pillow; video uses PyAV.

Pass --label-python when Pillow is available in a separate Python environment.
The speaking clip muxes the original prerecorded WAV, not newly generated speech.
"""
import argparse,json,subprocess,sys
from pathlib import Path
from fractions import Fraction
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--label-python');parser.add_argument('--labels-only',action='store_true');parser.add_argument('--clip');parser.add_argument('--source');parser.add_argument('--output')
args=parser.parse_args()
source=Path(args.source).resolve() if args.source else ROOT/'.cache/animation-recording';manifest=json.loads((source/'manifest.json').read_text(encoding='utf-8'))
label_dir=source/'labels';label_dir.mkdir(exist_ok=True)
if args.labels_only:
    from PIL import Image,ImageDraw,ImageFont
    font=ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf',27)
    small=ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf',14)
    for clip in manifest['clips']:
        for index,chapter in enumerate(clip['chapters']):
            label=Image.new('RGB',(manifest['width'],88),'#162522');draw=ImageDraw.Draw(label)
            draw.text((26,9),'ALEX / UNITY ANIMATION PREVIEW',font=small,fill='#b7c8b9')
            draw.text((24,31),chapter['label'].capitalize() if clip['name']=='alex-gestures' else chapter['label'],font=font,fill='#f3eadb')
            draw.text((manifest['width']-125,46),f'{index+1} / {len(clip["chapters"])}',font=small,fill='#b7c8b9')
            label.save(label_dir/f'{clip["name"]}-{index}.png')
    sys.exit(0)
subprocess.run([args.label_python or sys.executable,str(Path(__file__).resolve()),'--labels-only','--source',str(source)],check=True)
import av,numpy as np
output=Path(args.output).resolve() if args.output else ROOT/'docs/generated/animations';output.mkdir(parents=True,exist_ok=True)
reports=json.loads((output/'verification.json').read_text()) if args.clip and (output/'verification.json').exists() else []
def read_image(path):
    with av.open(str(path)) as image:return next(image.decode(video=0)).to_ndarray(format='rgb24')
for clip in manifest['clips']:
    if args.clip and clip['name']!=args.clip:continue
    path=output/(clip['name']+'.mp4');fps=manifest['fps'];height=manifest['height']+88;width=manifest['width']
    container=av.open(str(path),'w',options={'movflags':'+faststart'})
    video=container.add_stream('libx264',rate=fps);video.width=width;video.height=height;video.pix_fmt='yuv420p'
    video.options={'crf':'20','preset':'fast'}
    voice=None;audio_stream=None
    if clip['name']=='alex-speaking':
        voice=av.open(str(ROOT/'unity/Assets/PsychologyVR/Resources/FaceDemo/speech.wav'))
        audio_stream=container.add_stream('aac',rate=24000);audio_stream.layout='mono';audio_stream.bit_rate=96000
    labels=[read_image(label_dir/f'{clip["name"]}-{i}.png') for i in range(len(clip['chapters']))]
    canvas=np.empty((height,width,3),dtype=np.uint8);chapter=0
    for number in range(clip['frames']):
        while chapter+1<len(clip['chapters']) and number>=clip['chapters'][chapter]['end']:chapter+=1
        canvas[:88]=labels[chapter]
        canvas[88:]=read_image(source/clip['name']/f'{number:05}.jpg')
        frame=av.VideoFrame.from_ndarray(canvas,format='rgb24');frame.pts=number;frame.time_base=Fraction(1,fps)
        for packet in video.encode(frame):container.mux(packet)
    for packet in video.encode():container.mux(packet)
    if voice:
        for frame in voice.decode(audio=0):
            for packet in audio_stream.encode(frame):container.mux(packet)
        for packet in audio_stream.encode():container.mux(packet)
        voice.close()
    container.close()
    with av.open(str(path)) as check:
        count=0;poster_at={'alex-emotions':504,'alex-gestures':270,'alex-speaking':60,'alex-expressive-v2':220}.get(clip['name'],110)
        for frame in check.decode(video=0):
            if count==poster_at:
                png=av.CodecContext.create('png','w');png.width=width;png.height=height;png.pix_fmt='rgb24';png.time_base=Fraction(1,fps)
                still=av.VideoFrame.from_ndarray(frame.to_ndarray(format='rgb24'),format='rgb24')
                path.with_suffix('.png').write_bytes(b''.join(bytes(p) for p in list(png.encode(still))+list(png.encode())))
            count+=1
        if count!=clip['frames']:raise RuntimeError(f'Frame count mismatch: {path}')
    if audio_stream:
        with av.open(str(path)) as check:
            peaks=[float(np.max(np.abs(frame.to_ndarray()))) for frame in check.decode(audio=0)]
            if not peaks or max(peaks)<.001:raise RuntimeError('Missing or silent speaking audio')
    reports=[r for r in reports if r['path']!=str(path.relative_to(ROOT))]
    reports.append({'path':str(path.relative_to(ROOT)),'frames':count,'seconds':count/fps,'audio':audio_stream is not None,'bytes':path.stat().st_size})
    print('ENCODED',path.name,count,flush=True)
(output/'verification.json').write_text(json.dumps(reports,indent=2))
