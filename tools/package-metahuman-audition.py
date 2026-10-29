"""Package and verify the rendered MetaHuman clips alongside original footage."""
import json
from pathlib import Path
import subprocess
import sys
import cv2
import imageio_ffmpeg

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'experiments/metahuman'
REVIEW = ROOT / 'docs/generated/face-library-review'
NECK = '--neck' in sys.argv
OUT = REVIEW / ('metahuman-neck' if NECK else 'metahuman')

def main():
    report = json.loads((WORK / ('reaction-render-report.json' if NECK else 'render-report.json')).read_text())
    if report['status'] != 'rendered' or report.get('preview_only'):
        raise RuntimeError('Complete the full renders before packaging the review')
    OUT.mkdir(parents=True, exist_ok=True)
    results = []
    for name, old, slate in [('afraid', '04-afraid', 4), ('crying', '07-crying', 7), ('angry', '08-angry', 8)]:
        destination = OUT / name
        destination.mkdir(exist_ok=True)
        count = len(json.loads((WORK / 'media' / name / 'metahuman-curves.json').read_text())['frames'])
        render_folder = 'neck-render' if NECK else 'render'
        frames = sorted((WORK / 'media' / name / render_folder).glob('*.png'))
        if len(frames) != count:
            raise RuntimeError(f'{name}: expected {count} rendered frames, got {len(frames)}')
        if [int(f.stem) for f in frames] != list(range(count)):
            raise RuntimeError(f'{name}: render numbering is not contiguous from frame zero')
        output = destination / 'comparison.mp4'
        command = [imageio_ffmpeg.get_ffmpeg_exe(), '-y', '-v', 'error',
            '-framerate', '30', '-i', str(REVIEW / old / 'face/%05d.jpg'),
            '-framerate', '30', '-i', str(WORK / 'media' / name / 'render/%06d.png') if NECK else str(REVIEW / old / 'unity-frames/%05d.jpg'),
            '-framerate', '30', '-i', str(WORK / 'media' / name / render_folder / '%06d.png'),
            '-i', str(ROOT / f'livelink/recordings/recordings_all/MySlate_{slate}/front-1-wide.mp4')]
        labels = ['Your recording', 'MetaHuman / face only', 'MetaHuman / face and neck'] if NECK else ['Your recording', 'Jumper / previous tracking', 'MetaHuman / Animator mono']
        filters = [f"[{i}:v]scale=512:512,pad=512:550:0:38:color=0x151a20,drawtext=fontfile=arial.ttf:text='{label}':fontcolor=white:fontsize=21:x=12:y=9[v{i}]" for i, label in enumerate(labels)]
        filters.append('[v0][v1][v2]hstack=inputs=3[v]')
        command += ['-filter_complex', ';'.join(filters), '-map', '[v]', '-map', '3:a:0?',
                    '-c:v', 'libx264', '-crf', '19', '-pix_fmt', 'yuv420p', '-c:a', 'aac',
                    '-t', str(count / 30), '-movflags', '+faststart', str(output)]
        subprocess.run(command, check=True, cwd='C:/Windows/Fonts', timeout=300)
        capture = cv2.VideoCapture(str(output))
        decoded = 0
        peak = json.loads((REVIEW / old / 'verification.json').read_text())['peak_frame']
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            assert frame.shape[:2] == (550, 1536)
            if decoded == peak:
                cv2.imwrite(str(destination / 'poster.jpg'), frame)
            decoded += 1
        capture.release()
        assert decoded == count, (name, decoded, count)
        results.append({'take': name, 'frames': count, 'duration_seconds': count / 30,
                        'source_audio': 'Original recording; no generated speech',
                        'method': 'MetaHuman Animator mono video on Dominic-derived audition character',
                        'neck': 'Smoothed recorded orientation baked to neck/head bones; fixed local translations' if NECK else 'No added neck movement'})
    (OUT / 'verification.json').write_text(json.dumps(results, indent=2))
    cards = ''.join(f'<article id="{r["take"]}"><h2>{r["take"].capitalize()}</h2><video controls preload="none" poster="{r["take"]}/poster.jpg" src="{r["take"]}/comparison.mp4"></video></article>' for r in results)
    (OUT / 'index.html').write_text('''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>MetaHuman expression audition</title><style>body{background:#141b23;color:#edf1f4;font:17px system-ui;margin:32px}main{max-width:1550px;margin:auto}p{line-height:1.6}article{margin:32px 0;padding:18px;background:#222c36;border-radius:12px}video{width:100%;max-height:80vh}a{color:#9cddff}</style><main><h1>MetaHuman expression audition</h1><p>Original recording → previous Jumper transfer → MetaHuman Animator transfer. Each clip uses the same recording and original audio at 30 fps.</p><p>The MetaHuman uses a new facial solver as well as a different rig, so this compares the complete transfer workflows. Body and arm acting, tears and skin redness are not added in this facial test. The character is an initial Dominic preset audition, not the final cast design.</p>''' + cards + '<p><a href="../candidates/audition/">Earlier four-character audition</a></p></main></html>', encoding='utf-8')
    if NECK:
        page=OUT/'index.html'
        html=page.read_text(encoding='utf-8')
        html=html.replace('MetaHuman expression audition','MetaHuman neck reaction test').replace('Original recording → previous Jumper transfer → MetaHuman Animator transfer.','Original recording → MetaHuman face only → MetaHuman face and neck.')
        html=html.replace('The MetaHuman uses a new facial solver as well as a different rig, so this compares the complete transfer workflows.','The right view plays baked facial animation and gently smoothed recorded rotation across the neck and head bones. Local bone translations are held still; torso and hand performances come later.')
        html=html.replace('Body and arm acting, tears and skin redness are not added in this facial test.','Torso and hand acting are held still. These are full recorded takes; trimming and transition blending for chaining come later.')
        page.write_text(html,encoding='utf-8')
    print(json.dumps(results, indent=2))

if __name__ == '__main__':
    main()
