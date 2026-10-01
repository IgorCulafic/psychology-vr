"""Local video-to-face POC. Estimates coefficients; does not recover ARKit data.

Run with .tools/livelink-venv/Scripts/python.exe. Originals are never modified.
Dependencies: mediapipe, opencv-contrib-python, imageio-ffmpeg, numpy.
"""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

import cv2
import imageio_ffmpeg
import mediapipe as mp
import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def rigid_rotation(matrix):
    """Remove numerical scale/shear while preserving a proper rotation."""
    u, _, vt = np.linalg.svd(np.asarray(matrix, dtype=float)[:3, :3])
    correction = np.diag([1., 1., np.linalg.det(u @ vt)])
    return u @ correction @ vt


def head_rotations(matrices):
    """Unity xyzw quaternions in avatar right/up/forward coordinates.

    MediaPipe camera is right-handed: screen right, up, toward camera.
    A front-facing Unity avatar's right axis points toward screen left.
    Reflection on both sides changes basis without mirroring the performance.
    Rotations are relative to the first valid, lightly smoothed pose.
    """
    rotations = [None if m is None else rigid_rotation(m) for m in matrices]
    if not any(r is not None for r in rotations):
        return [[0., 0., 0., 1.] for _ in matrices]
    smooth = []
    for i, rotation in enumerate(rotations):
        if rotation is None:
            smooth.append(None)
            continue
        neighbors = [(rotations[j], 2 if j == i else 1) for j in range(max(0, i-1), min(len(rotations), i+2)) if rotations[j] is not None]
        smooth.append(rigid_rotation(sum(r * weight for r, weight in neighbors)))
    rest = next(r for r in smooth if r is not None)
    basis = np.diag([-1., 1., 1.])
    result, previous = [], np.array([0., 0., 0., 1.])
    for rotation in smooth:
        if rotation is None:
            q = np.array([0., 0., 0., 1.])
        else:
            converted = basis @ rotation @ rest.T @ basis
            axis_angle = cv2.Rodrigues(converted)[0].ravel()
            angle = np.linalg.norm(axis_angle)
            q = np.r_[axis_angle / angle * np.sin(angle/2), np.cos(angle/2)] if angle > 1e-8 else np.array([0., 0., 0., 1.])
        if np.dot(previous, q) < 0:
            q = -q
        result.append(q.tolist())
        previous = q
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "docs/generated/livelink-poc")
    parser.add_argument("--model", type=Path, default=ROOT / ".cache/livelink/face_landmarker.task")
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    frames_dir = out / "reference"
    frames_dir.mkdir(exist_ok=True)
    # Resample using media timestamps, including MOV rotation, not frame_log row count.
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    subprocess.run([ffmpeg, "-y", "-v", "error", "-i", str(args.video), "-vf",
                    "fps=30,scale=-2:960", "-q:v", "2", "-start_number", "0",
                    str(frames_dir / "%05d.jpg")], check=True)
    options = mp.tasks.vision.FaceLandmarkerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=str(args.model)),
        running_mode=mp.tasks.vision.RunningMode.VIDEO, num_faces=1,
        output_face_blendshapes=True, output_facial_transformation_matrixes=True)
    frames, names = [], None
    matrices = []
    boxes = []
    with mp.tasks.vision.FaceLandmarker.create_from_options(options) as tracker:
        for i, file in enumerate(sorted(frames_dir.glob("*.jpg"))):
            rgb = cv2.cvtColor(cv2.imread(str(file)), cv2.COLOR_BGR2RGB)
            result = tracker.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), round(i * 1000 / 30))
            found = bool(result.face_blendshapes)
            scores = {c.category_name: c.score for c in result.face_blendshapes[0]} if found else {}
            if found and names is None:
                names = list(scores)
            frames.append({"time": round(i / 30, 6), "valid": found, "scores": scores})
            matrix = result.facial_transformation_matrixes[0].tolist() if found and result.facial_transformation_matrixes else None
            matrices.append(matrix)
            if found:
                landmarks = result.face_landmarks[0]
                xs, ys = [p.x for p in landmarks], [p.y for p in landmarks]
                boxes.append([min(xs), min(ys), max(xs), max(ys)])
            if i % 60 == 0:
                print(f"Tracked {i} frames", flush=True)
    if names is None:
        raise RuntimeError("No face detected. No animation produced.")
    # Preserve missing-frame markers and use neutral fallback, never fabricated motion.
    for frame in frames:
        scores = frame.pop("scores")
        frame["weights"] = [round(float(scores.get(name, 0)), 6) for name in names]
    rotations = head_rotations(matrices)
    for frame, rotation, matrix in zip(frames, rotations, matrices):
        frame["headRotation"] = [round(v, 8) for v in rotation]
        frame["headValid"] = matrix is not None
    data = {"source": args.video.name, "method": "MediaPipe video estimate; not recorded ARKit curves",
            "headPoseVersion": 1, "headReference": "first valid smoothed frame; rotation only",
            "fps": 30, "duration": len(frames) / 30, "names": names, "frames": frames}
    (out / "performance.json").write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
    # Fixed crop covering the face throughout the take; full images remain alongside it.
    b = np.array(boxes)
    x0, y0, x1, y1 = b[:, 0].min(), b[:, 1].min(), b[:, 2].max(), b[:, 3].max()
    h, w = cv2.imread(str(frames_dir / "00000.jpg")).shape[:2]
    cx, cy = (x0+x1)*w/2, (y0+y1)*h/2
    size = min(w, h, max((x1-x0)*w, (y1-y0)*h)*1.6)
    left = int(np.clip(cx-size/2, 0, w-size))
    top = int(np.clip(cy-size/2, 0, h-size))
    size = int(size)
    (out / "face").mkdir(exist_ok=True)
    for file in sorted(frames_dir.glob("*.jpg")):
        img = cv2.imread(str(file))[top:top+size, left:left+size]
        cv2.imwrite(str(out / "face" / file.name), cv2.resize(img, (600, 600)))
    values = np.array([f["weights"] for f in frames])
    report = {"source": str(args.video.resolve()), "source_sha256": hashlib.sha256(args.video.read_bytes()).hexdigest(),
              "model_sha256": hashlib.sha256(args.model.read_bytes()).hexdigest(),
              "mediapipe_version": mp.__version__, "method": data["method"], "frames": len(frames),
              "detected_frames": sum(f["valid"] for f in frames), "duration": data["duration"],
              "channels": len(names), "face_crop": [left, top, size],
              "head_pose_frames": sum(m is not None for m in matrices),
              "head_rotation_max_degrees": float(max(2*np.degrees(np.arccos(np.clip(abs(q[3]), 0, 1))) for q in rotations)),
              "peak_coefficients": dict(sorted(zip(names, values.max(axis=0).tolist()), key=lambda p: -p[1]))}
    (out / "extraction-report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (out / "head-pose-matrices.json").write_text(json.dumps(matrices), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ["frames", "detected_frames", "duration", "channels"]}))


if __name__ == "__main__":
    main()
