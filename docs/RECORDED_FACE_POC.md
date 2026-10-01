# Acted face animation in Unity

This isolated proof of concept uses the supplied MySlate_1 recording to animate
the existing Jumper character. Open `Preview Recorded Face.cmd` for a side-by-side
player with play/pause, restart, scrubbing, facial intensity (0 to 1.5), and
head-motion strength (0 to 1). Head rotation follows the same take. The player is
silent; the comparison MP4 preserves the original recording's audio when present.
No AI services or headset are required. The consultation scene is unchanged.

Verified in the proof of concept: successful Unity player build, 53 mapped CC
controls across 222 mesh curves plus jaw and head rotation, baked-clip sample check with
zero blendshape error, and 296 rendered/comparison frames decoded successfully.
The desktop player's pause, time scrubbing and intensity-to-zero controls were
also exercised through its actual UI. The smile and mouth tension transfer;
eye nuance and subtler brow motion still need calibration before production use.

## What was supplied

`livelink/LiveLinkFace_20260929_MySlate_1_iPhone/20260929_MySlate_1/` contains a MOV,
take metadata, a thumbnail, and `frame_log.csv`. That CSV contains video/audio
timestamps, not ARKit blendshape coefficients. There is no depth payload in this
export. Its metadata reports 589 frames and approximately 9.85 seconds.

The proof of concept therefore **estimates** facial movement from the video using
Google's MediaPipe Face Landmarker, locally. It does not recover the phone's
original tracking or use MetaHuman Animator. No personal recording is uploaded.
The media is resampled by presentation timestamps to 30 fps. All 296 sampled
frames were detected. There are 52 model outputs, including its neutral category;
these are not 52 independently validated character controls.

## Outputs (local, excluded from Git)

- `docs/generated/livelink-poc/acted-face-unity-comparison.mp4`: source face crop
  beside the Unity-rendered character, at matching times.
- `docs/generated/livelink-poc/performance.json`: estimated coefficients and
  valid-frame markers, with source/method description.
- `docs/generated/livelink-poc/extraction-report.json`: detection coverage,
  software version, source/model hashes and peak values.
- `unity/Assets/PsychologyVR/Generated/LiveLink/MySlate_1_Face.anim`: reusable
  animation for the JumperCandidate hierarchy, including facial meshes and jaw.
- `unity/Assets/PsychologyVR/Generated/LiveLink/RecordedFacePreview.unity`: isolated
  audition scene. Use **Psychology VR > Play the currently open scene** to bypass
  the project's normal consultation startup.
- `unity/Builds/LiveLinkPreview/LiveLinkPreview.exe`: desktop audition player.

## Reproduce

1. Install `tools/livelink-requirements.txt` into an isolated Python environment
   such as `.tools/livelink-venv`. The consultation Python environment is separate.
2. Download the model linked from Google's documentation to
   `.cache/livelink/face_landmarker.task`. The extraction report records its hash.
3. Run `tools/extract-livelink-video.py` with the MOV path as its argument, using
   that environment's Python. It writes reference frames and performance data.
4. In Unity 6000.6.0f1, choose **Psychology VR > Build recorded facial performance
   preview**, or run `PsychologyVR.Editor.RecordedFaceSetup.Build` in batch mode.
   This validates mapped controls, exports and sample-checks the baked clip, and
   builds the separate player.
5. Run the player with `--data D:/AI/Psychology_VR/docs/generated/livelink-poc
   --render` to render all frames and exit. Run `tools/encode-livelink-preview.py`
   to encode the comparison and decode-check every output frame.

## Scope and limitations

Head rotations are estimated from MediaPipe's facial transform matrices. Scale
is removed, rotations receive a three-frame centered smoothing filter, and camera
coordinates are converted into the character's axes. The first valid smoothed
frame establishes the reference orientation. This take has 296 valid head poses
and reaches approximately 20.8 degrees from that reference. The data contains
unit quaternions, interpolated without accumulating rotation while scrubbing.
The baked clip and the preview use the same head-bone binding. The camera remains
fixed so the motion is visible. This is rotational capture (nod/turn/tilt), not
calibrated head translation or body capture. Moving the camera during recording
would also affect the inferred head motion.

The mapping transfers continuous facial motion rather than classifying emotion.
It maps brows, eyelids, cheeks, nose, lips and jaw to existing CC
controls. The mapping is approximate and needs artistic calibration. The
body and hands stay fixed, and gaze stays at the character's rest pose in this
first pass. A video-derived estimate can miss subtle motion and eye detail,
particularly through reflective glasses. Detection coverage is not an accuracy
score. The source begins in an expression, so no assumed neutral pose is subtracted.

The baked animation is specific to JumperCandidate's hierarchy. Other characters
need matching mesh paths/control names or a fresh bake against their own rig.
It must not play on top of the current `FacialPerformance` component without an
ownership/blending layer: that component writes the same controls every frame.
For later generated speech, preserve the captured upper-face performance while
giving lip sync priority over speech-related mouth controls. This POC does not
integrate that blending into the consultation application yet.

References:
- https://developers.google.com/edge/mediapipe/solutions/vision/face_landmarker/python
- https://dev.epicgames.com/documentation/en-us/unreal-engine/recording-face-animation-on-ios-device-in-unreal-engine
