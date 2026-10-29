"""Encode and verify the local side-by-side comparison after the Unity render."""
import json
import subprocess
from pathlib import Path
import cv2
import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/generated/livelink-poc"
take = json.loads((OUT / "performance.json").read_text())
report = json.loads((OUT / "extraction-report.json").read_text())
output = OUT / "comparison-frames"
output.mkdir(exist_ok=True)
font = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 23)
small = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 18)
for i in range(len(take["frames"])):
    canvas = Image.new("RGB", (1200, 690), (19, 26, 34))
    canvas.paste(Image.open(OUT / "face" / f"{i:05d}.jpg"), (0, 50))
    canvas.paste(Image.open(OUT / "unity-frames" / f"{i:05d}.jpg"), (600, 50))
    draw = ImageDraw.Draw(canvas)
    draw.text((20, 10), "Your acted performance", font=font, fill="white")
    draw.text((620, 10), "Jumper in Unity", font=font, fill="white")
    draw.text((20, 660), f"{i/30:04.1f} s   |   Video-derived face + head rotation   |   Body fixed   |   Proof of concept", font=small, fill=(180, 197, 210))
    canvas.save(output / f"{i:05d}.jpg", quality=94)
ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
movie = OUT / "acted-face-unity-comparison.mp4"
subprocess.run([ffmpeg, "-y", "-v", "error", "-framerate", "30", "-i", str(output / "%05d.jpg"),
                "-i", report["source"], "-map", "0:v:0", "-map", "1:a:0?", "-c:v", "libx264",
                "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", "-t", str(take["duration"]),
                "-movflags", "+faststart", str(movie)], check=True)
cap = cv2.VideoCapture(str(movie))
count = 0
while True:
    ok, frame = cap.read()
    if not ok:
        break
    if frame.shape[:2] != (690, 1200):
        raise RuntimeError("Unexpected video dimensions")
    count += 1
cap.release()
if count != len(take["frames"]):
    raise RuntimeError(f"Decoded {count} frames, expected {len(take['frames'])}")
sheet = Image.new("RGB", (1200, 690 * 3))
for row, index in enumerate([0, 110, 275]):
    sheet.paste(Image.open(output / f"{index:05d}.jpg"), (0, row * 690))
sheet.save(OUT / "comparison-contact.jpg", quality=94)
(OUT / "video-verification.json").write_text(json.dumps({"decoded_frames": count, "width": 1200,
    "height": 690, "fps": 30, "video": str(movie)}, indent=2))
print(f"COMPARISON_VERIFIED {count} frames: {movie}")
