# Four adult male facial-rig candidates

Acquired 2026-10-04 from Microsoft's official Rocketbox repository, revision
`0943055db6ec570bcef9f2c8b41c9e5467c808f9`. MIT license is preserved in LICENSE.md.
These are comparison candidates, not replacements integrated into the consultation.
An isolated Unity audition is now available at
`http://127.0.0.1:8798/candidates/audition/` while the local review server runs.
It compares neutral, afraid, crying, angry and happy recordings with the current
Jumper and all four candidates at once. Original recording audio is retained.
The MP4s are under `docs/generated/face-library-review/candidates/audition/`.
The upstream repository is archived; these are older assets, not a maintained modern character platform.

| Model | Appearance in supplied preview | Facial mesh triangles |
| --- | --- | ---: |
| Male_Adult_01 | Striped polo, shorts, brown hair | 7,440 |
| Male_Adult_02 | Beige sweater, dark trousers, dark hair | 7,312 |
| Male_Adult_03 | Older man, grey jacket, burgundy shirt | 7,200 |
| Male_Adult_04 | Dark jacket, blue shirt, curly hair | 8,684 |

All four facial FBX files imported successfully into Blender 5.2.1. Each contains
80 bones and 175 facial shape keys beyond Basis: 173 deform geometry; the two
intentionally neutral keys (`AA_VI_00_Sil` and `_Neutral`) do not. All 52 `AK_`
ARKit shapes have nonzero deformation. The remaining controls include FACS,
visemes and other facial tracking conventions. These sets overlap: 175 keys do
not mean 175 independent muscles or that every set should be applied together.

Use `Export/*_facial.fbx` for facial animation, not the plain body FBX.
Textures and original previews are retained. `acquisition.json` records every
source URL, byte count, Git blob SHA and SHA-256; all 44 downloaded files were
verified against the pinned Git tree. `rig-audit.json` records geometry and keys.
The source import helper is retained for reference, not activated in Unity.

## What this does and does not establish

The direct ARKit set is useful for comparing transfer quality without our current
CC-name approximation. Their mesh detail is lower than a modern realistic human.
No claim of better expression fidelity or VR performance has been established
by the import checks. The first Unity audition is a raw facial comparison;
body motion and live headset evaluation remain outstanding.

The existing recording preview uses estimated face weights and relative head
rotation. It does not transfer torso motion, head translation or eye gaze. A new
rig alone cannot restore leaning back in fear. Crying/anger can also receive
large smile coefficients from tracking, so capture calibration needs comparison
alongside the models.

Suggested evaluation: neutral, anger, crying, fear and happiness on the current
character versus these candidates; then add controlled torso/spine motion and
test gaze and speech blending. Reuse one shared performance library across the
four patients, with per-rig calibration.

Rebuild the isolated player using
`PsychologyVR.Editor.RocketboxFaceSetup.Build` in Unity batch mode, then run
`tools/render-rocketbox-audition.py` with `.tools/livelink-venv/Scripts/python.exe`.
The runtime uses 43 available expression channels: 52 ARKit names minus eight
gaze channels and tongueOut (not present in the tracking data). It zeros the
overlapping FACS/viseme channels and lets the jaw shape drive jaw motion without
adding a second bone rotation. Head rotation uses the existing calibrated basis.
All candidate footage is generated in Unity; the poster frames come from the
encoded comparison videos. Video decoding checks frame counts and dimensions.

## Other researched options

- [Reallusion free CC3+ bases](https://www.reallusion.com/character-creator/free-3d-character-base.html): 150+ facial morphs and rigged FBX; downloadable bases are free, CC5 software is a separate trial. Not four finished male characters; clothes and finishing required. Current Jumper already uses a CC-family rig, so superiority is unproven.
- [MetaHuman](https://www.metahuman.com/license): usable outside Unreal under current terms; [Epic lists educators/schools as free](https://www.unrealengine.com/license). Strong realism candidate, but full facial rig/shader/hair conversion into Unity requires substantial work and VR optimization. Not downloaded in this pass.
- [MakeHuman/MPFB](https://static.makehumancommunity.org/mpfb/docs/exporting/export_copy.html): customizable characters and exportable ARKit face units; useful free authoring route, but needs character creation, appearance work and validation. Not downloaded in this pass.

Source: https://github.com/microsoft/Microsoft-Rocketbox
