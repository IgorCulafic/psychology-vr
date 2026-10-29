# Speaking with pre-recorded emotion

Review: <http://127.0.0.1:8798/metahuman-speaking/>

This offline audition uses approved Person 3 BF16 Higgs samples for fear,
crying and anger. No new voice recipe is selected. The manifest under
`speaking/manifest.json` records the source preset, original WAV hash, exact
text, duration and selected recording window. The original audio is preserved;
the solver receives a mono PCM WAV copy.

The left view uses MetaHuman Animator's offline mouth-only audio solve. The
right view uses identical mouth, jaw and tongue controls, with 26 upper-face
channels blended 80% toward the corresponding recorded emotion. These include
brows, eyelids, cheek raise and nose controls. The neck/head rotations come
from a continuous slice of the same recording at its original 30 fps, with
the previously approved smoothing and 30/30/40 joint distribution.

The lip solver returns complete 30 fps samples; the final fractional audio
frame is held to fill the ceiling-rounded video duration. There is no global
speed change or arbitrary audio offset. Matching face/body clips are baked
into native assets under `/Game/Audition/Speaking/<emotion>`. The original
non-speaking reaction assets and Unity game are unchanged.

This tests visual delivery, not real-time processing or response latency.
Review mouth timing, emotional readability, eyelid closure during speech,
and whether the recorded neck movement fits the spoken phrase. The exact
phonetic fit still needs listening review. Tears, torso and hand acting are
not part of this pass.

## Rebuild

1. Run `tools/prepare-metahuman-speaking.py` in the livelink Python environment.
2. Run `tools/metahuman-speaking-solve.py` with UnrealEditor's
   `-ExecutePythonScript` argument. It imports WAVs, solves mouth movement and
   saves editable sequence copies. Let the editor close.
3. In a fresh editor process, run `tools/metahuman-speaking-build.py`. The
   `LS_Control_*` sequences retain editable controls; `LS_*` playback sequences
   use baked clips with explicit custom animation playback. The first audition
   predates the retained-control copies; re-running step 2 creates them.
4. Run `tools/metahuman-audition-render.py` with the extra `-mhSpeaking` flag.
5. Run `tools/package-metahuman-speaking.py` in the livelink environment.

Reports remain in `speaking/`: `solve-report.json`, `build-report.json`, and
`render-report.json`. The packaged review has decoded video frame counts and
audio stream checks in `verification.json`. Generated WAVs, solver curves,
renders and reports in `speaking/` stay local, alongside the ignored native
Unreal Content assets.

## Anger mouth follow-up

Review: <http://127.0.0.1:8798/metahuman-anger-blend/>. This keeps the same
approved angry audio and compares the original upper-face-only blend with
two lower-face blends. It changes the animation, not the vocal performance.

The recorded jaw opening, upper-lip raise, lower-lip depression, mouth stretch
and sharp-corner pull can add to the speech pose. Speech jaw opening gates the
addition; lip-together/press controls suppress it, and funnel/purse controls
reduce it. Closure, funnel, purse and tongue controls themselves stay driven
by speech. This is a control-based approximation of articulation protection,
not phoneme-labelled alignment; subjective lip-sync review remains necessary.

Balanced uses 0.40 jaw and 0.28 lip weights; stronger uses 0.78 and 0.60. Values
are bounded at 1.0. The same recorded window, upper-face weight and neck motion
are used for both. At initial bake, peak jaw control was 0.485 / 0.709 versus
0.327 in the speech input, and extra movement was exactly zero on 22 fully
gated frames. The original three speaking tests remain available unchanged.

Run `metahuman-anger-blend-prepare.py` in Unreal, then in a fresh editor run
`metahuman-speaking-build.py -mhAngerBlend`, followed by
`metahuman-audition-render.py -mhAngerBlend`. Package with
`package-metahuman-anger-blend.py` in the livelink Python environment.
Generated reports and renders are under ignored `anger-blend/`; native assets
are under `/Game/Audition/AngerBlend`.
