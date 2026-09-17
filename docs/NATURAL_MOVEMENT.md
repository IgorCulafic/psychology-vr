# Alex's seated movement

## Body contact

The runtime now checks palms and finger segments against bone-following thigh, torso and head boundaries, then separates the two hands where necessary. Contact corrections resolve through the existing wrist/elbow solver after gaze animation, with a gradual release and an independent blocked-finger fallback. The earlier fixed lap lift remains gesture preparation; it is no longer the only protection against penetration. See `BODY_CONTACT.md` for geometry, verification and limits.

## Individual fingers and thumbs

Finger roots have a calibrated spread axis as well as their curl hinges. The index and little fingers spread farther than the middle fingers in open gestures; closed hands reduce the spread. Three-joint curl and release rates vary by digit, with separate thumb base, knuckle and tip motion.

The latest pass adds actions that repeat with pauses while the same emotion is held: anxious fingers curl and release in sequence with thumb flexion; presenting hands partly close and reopen; angry fists release some tension and squeeze again; crying hands make small clutching motions. Raising a presenting hand unfurls the digits in sequence. Quiet resting movements are much smaller, and frozen fear/numbness suppress these motions. Controller grip continues to use its existing targets without the NPC action layer.

Lap gestures anticipate the curl with a small wrist lift, and finger activity is gated by hand elevation. Body-contact constraints subsequently check the resulting palm and finger geometry against the moving body boundaries.

Run the recorder with `--desktop --record-alex --finger-motion --record-dir <folder>` for the close-up preview. The current `generated/active-fingers/alex-active-fingers.mp4` contains 888 frames at 24 fps (37 seconds): eight seconds each of anxiety, frustration, anger and crying, and five seconds of neutral rest. Capture uses a fixed 1/24-second simulation step and the encoder uses the same frame rate; no speed-up is applied. The older `generated/finger-movement/` preview records the preceding spread/pose pass.

The regression now measures each finger middle joint and each thumb tip after two seconds within each held emotion. Switching between an open pose and a fist no longer suffices to pass. Anxiety, frustration, anger and crying must each show more than 10 degrees of motion per finger and 6 degrees per thumb. Neutral remains a stability check. The recorded cases pass alongside the wrist/elbow bounds; representative lap, presenting, fist and crying frames were inspected.

## Wrist and elbow correction

The earlier pass still assigned a world-space hand quaternion after positioning the arm. Smoothness and travel checks passed even when the wrist took an anatomically implausible rotation. That approach is now replaced by `ArmJointMotion`.

The upper arm and forearm are oriented against one calibrated elbow plane. Elbow bend stays between 8 and 145 degrees. Palm-down/palm-up orientation is expressed as forearm rotation about its long axis, through a thumb-up neutral frame, limited to ±85 degrees. The CC forearm twist helpers share this rotation along the sleeve, and the elbow share bone retains the unrolled elbow frame. Clavicle motion accompanies a raised/reaching arm.

The contact solver exposed a defect in how those skinning helpers were updated: additional arm solves in the same frame reused their already-adjusted rotations, accumulating twist despite a stable wrist. `ArmJointMotion` now restores cached helper local rotations in parent-to-child order before every solve. `ForearmRegression` exercises both arms on the imported character at three targets, repeats each frozen solve 16 times, and checks helper transforms and baked skinned vertices. The runtime recorder also checks frame-to-frame rotation of all six forearm/elbow helper bones.

The hand is constructed from wrist flexion (−35 to +50 degrees) and side deviation (±18 degrees), with joint-angle speed limits. These are authored animation limits, not an anatomical simulation. There is no independent 180-degree hand roll. Crying uses closer elbow hints and wider hand spacing so that the constrained wrists can cover the face without crossing fingers.

The recorded regression now measures the resulting finger direction relative to the forearm, residual wrist twist, elbow bend and deviation from the calibrated hinge plane on every frame, including transitions. Those checks supplement the earlier travel/smoothness checks. The current preview is `generated/joint-movement/alex-joint-movement.mp4`; the earlier natural-movement recording is retained for comparison.

## Resting and gesture timing

This pass adjusts the existing procedural performance layer. Resting wrist positions are derived from each thigh and knee, with an offset for the trouser surface and palm thickness. The hands stay in the actor frame rather than inheriting every upper-body lean. A small left/right offset and gentler relaxed finger curl reduce the matching mannequin pose. The tracked player's controller finger poses are unchanged.

Wrist positions use velocity-preserving damped motion with slower settling on the left arm. Elbow bend directions become wider as the hands rise; small clavicle rotations accompany reaching. Wrist orientation blends from palm-down support into the raised gesture and back. These controls use two-bone IK followed by body-contact constraints; they are not motion capture.

Happy, frustrated and confused gestures have preparation, a short hold, a longer release and a rest interval. The two hands do not start together. Anxious movement uses small intermittent adjustments instead of rapid oscillation. Breathing and a restrained torso weight shift continue with supported hands; numb and frozen fear retain their deliberate stillness. Anger, face-covering crying and despondency keep their distinct silhouettes. Despondency settles the hands on the inner thighs instead of putting down-pointing fingers through the trousers.

Small conversational right-hand beats run during actual voice playback in neutral, calm, anxious and hopeful states. They fade when playback pauses or stops, and stronger emotional performances take precedence. Facial blendshapes, gaze and lip-sync timing remain in the facial layer.

To reproduce the motion preview after building Windows:

```powershell
./unity/Builds/Windows/AlexPrototype.exe --desktop --record-alex --natural-motion --record-dir "$PWD/.cache/natural-motion" -logFile "$PWD/docs/generated/natural-motion-runtime.log"
```

The recorder covers rest, anxiety, happiness, frustration, anger, crying, despondency and return to rest. It records hand travel and wrist rotation across transitions, checks supported-hand stability, and writes a manifest for `tools/encode-animation-previews.py`. Offline capture uses a fixed 24 fps clock; it is not a headset performance measurement. Sleeve deformation and exact hand/body contact still depend on the supplied mesh and skin weights.
