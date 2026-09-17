# Supplied character rig audit

Current integration: the jumper now represents Alex in the main consultation scene. A derived headless copy represents the seated player. See `PLAYER_AVATAR.md`; the audition notes below document the preceding visual iterations.

Inspected every FBX in both supplied folders using Blender 5.2.1. Originals are unchanged.

| Candidate | Body facial shapes with nonzero deformation | Total triangles | Skeleton bones |
|---|---:|---:|---:|
| Ex wife's new husband | 148 | 117,048 | 101 |
| CC3_Base_Plus | 148 | 35,366 | 101 |
| Neutral_F | 148 | 35,366 | 101 |
| Neutral_M | 148 | 35,366 | 101 |
| Toon Neutral_F | 148 | 43,482 | 101 |
| Toon Neutral_M | 148 | 43,482 | 101 |

All six have 148 nonempty body facial controls: left/right eyebrows, lids, squint/widen, nose, cheeks, smile/frown, lip compression/rounding, jaw and speech shapes. Counts on eye occlusion, tear lines, facial hair and other meshes are additional bindings, not hundreds of independent emotions. These rigs also contain eye, jaw, teeth and tongue bones.

## Selection

Jumper is the first candidate: it is already clothed and has hair, and contains the same core facial control set as the base characters. The five base characters are useful alternatives, but need styling and clothing for the consultation room. The supplied jumper includes a long TempMotion animation; the audition deliberately disables it to test the underlying controls in isolation.

The audition uses the source shapes, not the approximate morphs made for the old Alex. The runtime audition scene and prefab are separate from Consultation.unity and Alex.prefab. Body motion has not been retargeted: the current performer expects Mixamo names while these use CC_Base bones. Full replacement also needs calibrated gaze, jaw/teeth coordination, new tear anchors, and performance measurement with the game.

## Expression transfer

All supplied body meshes have 14,164 vertices and the same named facial controls. Each already has its own fitted expressions. A random expression shape cannot be directly copied onto the old Alex: shape deltas depend on vertex correspondence and anatomy. A fitting/retargeting workflow would be needed; using a supplied expression-ready rig avoids that work.

## Provenance

User supplied both folders and identified Sketchfab as their source, for a personal project. Exact pages, author names and license text were not provided in these folders; no broader redistribution rights have been asserted.

## Unity audition

`Assets/PsychologyVR/Scenes/JumperFacialAudition.unity` and `Assets/PsychologyVR/Prefabs/JumperCandidate.prefab` contain the imported candidate with URP materials. Diffuse/opacity textures were combined for hair, facial hair, eyelashes and eye surfaces; normals are imported as normal maps. The candidate imports with 780 blendshape bindings across all meshes (148 on the body).

`CandidateExpressionPreview` demonstrates neutral, happiness, sadness, anger, fear, disgust, crying facial muscles, blinking and three speech mouth shapes. Speech shapes coordinate the jaw bone with the facial morphs. This is a silent facial capability test: no body acting, streamed speech, falling tears or flushed-face effect is included in this audition.

Rebuild using `PsychologyVR.Editor.CandidateSetup.Build`, then launch `unity/Builds/CandidatePreview/JumperPreview.exe --output D:/AI/Psychology_VR/docs/generated/candidate-preview`. It exits after recording. Encode with `tools/encode-animation-previews.py --source docs/generated/candidate-preview --output docs/generated/candidate-preview/video --label-python <Python with Pillow>`.

The original Alex scene and Windows game build remain available. These faces are a better technical foundation, but the jumper still needs appearance/material polish, eyebrow styling, and a calibrated performance adapter before becoming the in-game Alex.

Verified: Unity build succeeded with all 780 bindings; the built audition completed 720 frames, and the MP4 encoder decoded and checked all 720 frames (30 seconds, silent). Neutral, happiness, sadness, anger, fear, disgust, blink, crying face and open-mouth samples were inspected. Jaw opening works, though extreme speech poses expose facial-hair attachment/shape coordination that needs calibration. Eye-surface appearance also needs polish. The audition establishes viable controls, not a finished in-game performance.

## Jumper emotion and body preview

The newer `generated/jumper-emotions/video/jumper-emotions-full.mp4` adds crying tear tracks and moving beads, gradual head-material redness, jaw pulses, and seated body performances. It includes neutral, crying, anger, fear, panic, disgust, happiness, sadness, surprise, despondency and numbness, followed by wide shots of intense crying and anger. The silent recording is 65 seconds; full-body crying starts at 46 seconds and anger at 55 seconds.

`CandidateSeatedPose` prepares a seated CC skeleton. `PerformanceDriver` now resolves both Mixamo and CC bone names and can use an explicitly prepared static seated pose; existing Alex animation initialization remains the default. CC left/right mapping follows actual bone positions so the hand targets remain consistent. FaceTears now accepts per-rig cheek calibration while preserving Alex's defaults. All 72 jumper tear anchors resolve. The maximum unreachable IK target distance observed was 4.5 cm; the solver clamps limb reach rather than stretching bones.

This preview is separate from the live consultation scene. Deep elbow bends still expose sleeve clipping, and jaw/facial-hair coordination and eye materials need further polish. It is a visual prototype, not a headset performance measurement or complete live speech integration.

## Distinct emotion cues revision

`generated/jumper-contrast/video/jumper-emotion-contrast.mp4` is a focused 67-second comparison. Each emotional state is shown first at a fixed wider framing, then in a face close-up. Launch the candidate build with `--contrast-preview --output D:/AI/Psychology_VR/docs/generated/jumper-contrast` to regenerate.

- Anger: forward torso, lowered brow, compressed lips, nostril tension, folded thumbs, and a forceful unilateral fist beat followed by a tense hold. Continuous conversational arm waving and repeated mouth opening were removed from this state.
- Frustration: open palms up, an asymmetric brow, and a short head shake. It avoids anger's fist and forward glare.
- Sadness: worried face and modestly lowered gaze while remaining comparatively upright.
- Despondency: a slower, deeper collapse, head hanging down, heavy eyelids and downward gaze, with limp hands between the knees. Breathing movement is slower and smaller.
- Numbness: upright, level head and still forward stare, distinct from despondency's collapsed silhouette.
- Fear holds its protective pose; panic remains animated; surprise visibly settles after the initial startle rather than holding a fear-like pose indefinitely.

Crying and the broader expression range remain available through the ordinary candidate recording mode. This is still a candidate preview, not a replacement of the live consultation character. Existing sleeve-contact limitations remain.

## Hand articulation revision

`HandArticulation.cs` replaces the shared world-space curl and thumb-to-knuckle aiming with local rest-frame hinges for each finger joint. Each digit has its own relaxed, open, cupped and closed target angles. The thumb has separate opposition, knuckle and tip controls. Opening and closing interpolate continuously at different rates. Anger anticipates its first arm beat by closing the hand first.

The source audit (`generated/jumper-hand-rig.json`, reproduced by `tools/audit-jumper-hands.py`) confirms three finger joints and three thumb joints per digit chain on both sides. A dedicated `--hand-preview` recording mode follows the hands and adjusts framing for their separation. The 36-second `generated/jumper-hands/video/jumper-hand-refinement.mp4` shows relaxed hands, anger/fists, release, open palms, limp hands and cupped crying hands. Run the candidate executable with `--hand-preview --output D:/AI/Psychology_VR/docs/generated/jumper-hands` and encode with the normal preview encoder.

These are authored hand shapes with bounded flexion, not collision-driven finger contact. Sleeve and prop-contact polish remain separate limitations.
