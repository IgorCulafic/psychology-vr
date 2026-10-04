# Baked facial and neck reactions

This is a content-authoring experiment for the Unity project. The desired runtime
output is a skinned character and baked animation clips; the video solver runs
offline. Torso and hand performances are deferred.

## Assets

The complete native audition character is
`Content/MetaHumans/AuditionMale/BP_AuditionMale.uasset`, with dependencies in
`Content/MetaHumans/Common`. This document describes the original Dominic-derived
baseline. The subsequent four-character Unity port and its reproducible workflow
are documented in `CAST.md`; its complete exports are under `exports/unity`.

Sequences and baked face/body AnimSequences are in `Content/Audition/Reactions`.
Independent FBX files are under `exports/reactions`:

- `face_model.fbx` and `body_model.fbx`: skinned core meshes.
- `afraid_face.fbx` / `afraid_body.fbx`: MySlate_4, 406 source frames.
- `crying_face.fbx` / `crying_body.fbx`: MySlate_7, 588 source frames.
- `angry_face.fbx` / `angry_body.fbx`: MySlate_8, 670 source frames.

Play the matching face/body pair together at 30 fps. These are absolute poses,
not additive clips. The face mesh has its own neck hierarchy; do not apply the
same body rotation a second time through a head attachment or retargeting layer.
Unreal's FBX exporter adds an endpoint sample: Blender imports frames 1 through
N+1 for N source frames. Use frames 1 through N for source-aligned playback.

Recorded roll, pitch and yaw receive a five-frame weighted smoothing filter.
The final pass writes local rotations directly to the two neck bones and head
with 30/30/40 percent shares. Local bone translations retain the reference pose.
The final sequences play the baked clips without Control Rig; the rig-based
attempts cancelled head orientation and were rejected during visual QA.
The facial post-process animation blueprint is disabled on the baked preview
tracks to avoid solving the already-baked facial joints a second time. The body
keeps its character-proportion post-process, and each clip uses its matching
mesh as retarget source. Both animation tracks force custom playback; this
setting must be explicitly saved or the face's idle blueprint takes priority.

These absolute facial-bone clips belong to this audition character. For the
remaining three identities, reuse the captured facial controls and bake against
each identity's rig; copying absolute facial-joint translations blindly can
change the face shape.

The exported optimized meshes use joints, with no morph targets. The face mesh
contains 19,283 vertices and 34,514 triangles; the body has 25,328 vertices and
47,392 triangles. These figures exclude clothing, hair, eyes and accessories.
FBX files here do not reproduce the full rendered character appearance: hair,
clothes, textures, Unreal materials and wrinkle shading still need a separate
Unity-compatible assembly. The native Unreal character retains those assets.
For the first Unity import, preserve the full bone hierarchy and use Generic
animation. Humanoid retargeting alone cannot retain the hundreds of facial
joint tracks. Validate the matching face/body playback before reducing bones,
resampling curves, or enabling aggressive keyframe compression.

## Review and validation

Open <http://127.0.0.1:8798/metahuman-neck/> while the existing review server is
running. Each video compares the original recording, the face-only render, and
the face-and-neck render. Audio is from the original recording.

`reactions-report.json` records source frame counts, rotation ranges, baked
animation paths and bone-motion checks. `exports/reactions/fbx-validation.json`
records independent Blender import checks. The review's `verification.json`
records decoded frame counts. `media/manifest.json` retains source hashes.

These are full recorded takes. They still need reaction boundaries, neutral
entry/exit poses, crossfades and animation compression before they form a
chainable runtime library. There is no Unity/VR performance measurement yet.

## Rebuild after the initial face audition

Run each Unreal Python script using the project's normal Editor executable with
`-ExecutePythonScript=<absolute script path>`, one process at a time:

1. `tools/metahuman-neck-probe.py` extracts recorded head-motion curves.
2. `tools/metahuman-build-reactions.py` keys the rig and bakes/exports reactions.
   On its first run it saves duplicate sequences and reports
   `copies_saved_restart_required`; run it again in a fresh editor process.
3. `tools/metahuman-bake-neck-direct.py` writes captured rotation directly to the
   neck/head bones and creates the final `LS_Baked_*` playback sequences.
4. `tools/metahuman-configure-baked-playback.py` persists playback settings,
   applies character-specific retarget sources, and refreshes the FBX exports.
5. `tools/metahuman-audition-render.py -mhReactions` renders the baked clips.
6. Run `tools/audit-metahuman-fbx.py` in background Blender to read back FBXs.
7. Run `tools/package-metahuman-audition.py --neck` with the livelink Python
   environment to encode and verify the comparison videos.

Generated Content, media and FBX exports stay local and are excluded from Git.
