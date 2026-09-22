# Prototype build status

## Fast dialogue option — 22 September 2026

PC Settings option 4 runs Qwen3.5 9B Q6 entirely on the GPU while preserving BF16
voice. The local 5090 full-player check passed: 2.494 s dialogue/appraisal,
13.131 s first audio, 30.944 s all speech ready, 20.9 GiB total GPU peak. 111 tests
pass. A progressive length-retry fix prevents repeating the same failed short
response request. Fast remains opt-in due to observed language and character
weaknesses; Auto and the 27B options are unchanged. See [GPU presets](GPU_PRESETS.md).

## Automatic GPU presets — 22 September 2026

The optional PC Settings menu exposes Auto, University / RTX 4090 and Original
quality. Auto defaults to IQ3_M / 32 GPU layers for 24 GB cards and IQ4_XS / 48 for
32 GB+ cards. BF16 speech is preserved. 110 tests pass; live playback with the
conservative preset passed on the 5090 with a 20.8 GiB total GPU peak and 67.224 s
to first playback. A university 4090/Quest acceptance check remains necessary.
See [GPU presets](GPU_PRESETS.md) for deployment instructions and limitations.

## Downloadable Windows package — 21 September 2026

The standalone release includes the built game, four patient profiles, services,
approved reference voice and double-click launchers. First launch installs a
private Python environment and checksum-verified pinned model/runtime downloads.
102 tests pass; fresh-environment setup, the actual CMD launcher, streamed
pause/interruption and live Qwen/BF16 playback were verified in an extracted
folder with spaces. See [release packaging](PORTABLE_RELEASE.md)
and [user instructions](../START%20HERE.md). This is separate from the source ZIP.

## Sentence playback and delivery refinement — 21 September 2026

BF16 speech now publishes sentences as they finish, with Unity playback overlapping later synthesis. Confirmed playback prefixes drive history/memory after interruption. Facial transitions and gesture repetition are refined; the reference voice and preferred anger settings remain. 99 service tests and the Unity build pass. A built-player pause/interrupt check confirms one played sentence and a 0.256-second partial second sentence in the journal. Real BF16 authored comparisons produced their first sentence in 3.7–5.0 seconds versus 15.5–17.6 seconds to prepare all four. These exclude Qwen generation; a full Qwen/BF16 smoke test passed with 39.64 seconds to first playback. Six emotional comparison playbacks and rendered-pose inspection passed. See [implementation, measurements and review](SENTENCE_PLAYBACK.md).

## Automatic session logging — 21 September 2026

The shared bridge now saves accepted dialogue, validated emotional performance, relationship state, memory diagnostics and timings after each turn, with readable TXT and structured JSONL companions in `logs/sessions/`. Reset and character replacement preserve old archives. Failures and interruptions are recorded; logs do not claim speech was heard or archive audio. All 87 service tests pass. See [logging details](SESSION_LOGGING.md). No Unity rebuild is needed; running services must reload the backend.

## Conversation refinement and memory — 21 September 2026

All four patients now use the shared conversational/relationship policy, including Alex. Session-local, attributed excerpts provide bounded recall beyond the recent dialogue window, with tokenizer-aware pruning and atomic reset/cancellation behaviour. Text exports include memory diagnostics. A 37-reply local conversation screen, focused recall rechecks and 78 service tests are documented in [conversation memory](CONVERSATION_MEMORY.md). This is a backend/profile update; no new Unity player was built in this pass.

## Three adult patient cases — 21 September 2026

Nikola (bereavement), Stefan (fire witness) and Ivan (work exhaustion) join the picker alongside Alex, whose profile was left unchanged in this pass. The new policy encourages short replies, relevant gradual disclosure, independent views and limited clinical insight. Instructor notes are excluded from patient prompts. All three reuse the current avatar/voice. The 49-test backend suite, Unity build and description-hiding menu preview pass; language and occasional consistency limitations remain. See [adult case notes](../characters/ADULT_CASES.md).

## Model-directed emotional performance — 21 September 2026

Normal Qwen replies drive per-segment emotion, intensity, gaze, gesture timing and expressive BF16 speech. Delivery guidance now distinguishes frustration/anger, sadness/crying and partial relief, and allows meaningful changes within a reply. Captured real conversation selected anxiety → frustration → relief. The player diagnostic shares the live playback routine and separately labels its authored crying-to-relief timing fixture. See [emotional performance checks](EMOTIONAL_PERFORMANCE.md) for replay commands, evidence and limits.

## Montenegrin recognition and conversation — 21 September 2026

The expressive setup now uses Whisper large-v3-turbo on CPU with a generic regional language hint and Latin-script output. On one 25.45-second recording, word error fell from 18.5% to 5.6%; the same-recording crop improved from 14.3% to 7.1%, but was slower. Dialogue prompting now prioritizes direct answers, clarification and authored facts. Real STT-to-Qwen HTTP verification passed; native grammar and invented symptom descriptions remain limitations. See [measurements and next headset checks](MONTENEGRIN_CONVERSATION.md). These backend changes use the existing Unity build and preserve BF16 speech.

## Voice selection — 21 September 2026

The user preferred the original 16-bit BF16 Higgs voice over NF4 because its emotional delivery was substantially better. BF16 is restored in the local and example expressive configurations, retaining the full reference and temperature 0.70. Qwen offload returns to 48 GPU layers for memory headroom. The NF4 timings below remain historical measurements, not current BF16 performance guarantees.

## Live expressive speech and model-directed performance — 20 September 2026

The user confirmed microphone/controller input, Montenegrin command recognition, facial expressions and recorded expressive playback in Quest 3. The live successor now combines Qwen, a resident Higgs worker, Whisper medium on CPU and audio-driven lip timing. Character prompts request Montenegrin speech, bounded emotional continuity and per-beat gaze, pauses, transitions and timed gestures. See [setup and measurements](LIVE_EXPRESSIVE_SPEECH.md).

Python verification passes 38 tests, including malformed controls, timing bounds, compatibility with old segments, localized prompting, microphone language selection, scenario changes and interruption during synthesis. Unity 6000.6.0f1 builds successfully (`services/.runtime/expressive-build.log`: `PSYCHOLOGY_VR_BUILD_OK`). Desktop live playback passes (`expressive-smoke.log`: `SMOKE_PLAYBACK_OK`, `SMOKE_OK`), with jaw movement reaching 0.297 and an audio-timed hand fidget firing at 3.008 seconds. The captured room/subtitles were visually inspected. OpenXR reported no headset available during this desktop run; it was not a new Quest acceptance test. A four-turn BF16 conversation and three-turn NF4 conversation completed through real Qwen/Higgs, with changing emotional states. The BF16 test exposed an invented relative; the prompt was tightened, but broad character consistency is not established by this short run.

The selected local candidate uses NF4 Higgs (~3,539 MiB allocated) and full-GPU Qwen on the 5090. Three replies took 10.86–19.88 seconds, excluding STT/playback. This is an improvement over the initial 30.83–41.24-second partial-offload run, but speech synthesis remains too slow for effortless turn-taking. The previous full-precision voice remains selectable. Native assessment of voice identity, accent and emotional contrast, plus physical headset timing/performance and interruption, remains necessary. No new GitHub release has been published.

## Forearm deformation fix — 15 September 2026

Repeated body-contact solves reused the forearm skinning helpers' already-adjusted local rotations. The hand and elbow remained within their limits while the sleeve accumulated extra twist. `ArmJointMotion` now restores calibrated helper rotations in parent-to-child order before every solve. Contact corrections retain their behavior and do not advance the animation clock.

The failure was reproduced on both arms of the imported jumper rig at three targets, repeating each frozen solve 16 times. Before the fix, helper rotation drift reached 178.16 degrees and baked skinned vertices moved 11.95 cm while the wrist remained stationary (`generated/forearm-regression-before.json`, `forearm-before.log`). With the fix, helper angle drift is zero and maximum vertex drift is 0.00086 mm (`generated/forearm-regression.json`). The regression, contact geometry tests and Windows build pass (`generated/forearm-fix-build.log`: `FOREARM_REGRESSION_OK`, `BODY_CONTACT_GEOMETRY_OK`, `PSYCHOLOGY_VR_BUILD_OK`).

The 78-second runtime recording passes (`generated/forearm-fixed-runtime.log`: `NATURAL_MOTION_OK`), including a new frame-to-frame check on all six forearm/elbow helpers: maximum step 9.37 degrees at 24 fps. Body/hand contact remains below 0.3 mm against the padded proxies; wrist/elbow limits, resting stability and active fingers also pass. Representative gesture, crying and side-view frames were compared with the previous recording.

Current preview and metrics: `generated/forearm-fixed/alex-body-contact.mp4` and `motion-checks.json`. Encoding verified all 1,872 frames at 24 fps, with no speed-up. The prior body-contact preview is retained as the pre-fix version. Final integration passes simulated player tracking/controller grip and facial expressions, tears, gaze, lip sync and pause/resume (`generated/forearm-fixed-integration.log`: `PLAYER_TRACKING_PREVIEW_OK`, `ALEX_PREVIEW_OK`).

## Body and hand contact constraints — 15 September 2026

Alex now checks palm/finger capsules against bone-following thigh, torso and head boundaries after facial/gaze animation. The existing joint solver moves blocked hands clear, retains corrections with gradual release, and can reduce a blocked digit's curl if reach limits prevent translation. Hand-to-hand separation also prevents crossing fingers in poses such as despondency. The prior finger performance and authored rest/face-covering targets remain active. See `BODY_CONTACT.md` for implementation, reproduction and scope.

Geometry checks and the Windows build pass (`generated/body-contact-build.log`: `BODY_CONTACT_GEOMETRY_OK`, `PSYCHOLOGY_VR_BUILD_OK`). Checks include deliberate obstruction, parallel/crossing segments, a moving head boundary, blocked-finger release and crossing-hand separation.

The final 78-second recording passes (`generated/body-contact-runtime.log`: `NATURAL_MOTION_OK`), covering resting, anxiety, frustration, anger, crying, fear, panic, disgust, despondency and tear wiping. Body contact engaged for all three boundary regions; maximum remaining overlap against the padded body proxies was 0.298 mm, and between hand proxies 0.296 mm. Maximum corrective wrist offset was 5.81 cm. Wrist/elbow limits, hand speed, resting stability and continuing finger motion also pass. Front and side frames were inspected for lap, fist, face-covering and wiping contact.

The preview is `generated/body-contact/alex-body-contact.mp4`, verified at 1,872 frames and 24 fps with normal game timing. Metrics, manifest and side-view stills are alongside it. These measurements describe the approximate contact geometry, not per-triangle skin/clothing collision; sleeve, furniture and same-hand finger collisions remain outside this pass.

Final integration passes simulated player tracking/controller grip, 20 facial expressions, tears, gaze, lip sync and pause/resume (`generated/body-contact-integration.log`: `PLAYER_TRACKING_PREVIEW_OK`, `ALEX_PREVIEW_OK`). Physical headset performance remains unverified.

## Active finger performance — 15 September 2026

The preceding spread/pose pass still looked static to the user. NPC fingers now perform staggered curl-and-release actions during held emotions: anxious fidgets and thumb flexion, partly closing/reopening presenting hands, loosening/reclenching angry fists, and small clutching motions during crying. Resting actions are restrained; frozen fear and numbness retain stillness. A small anticipatory wrist lift and elevation gate provide room for curling above the lap. The wrist/elbow solver and player controller poses are retained. See `NATURAL_MOVEMENT.md`.

The Windows build passes (`generated/active-fingers-build.log`). The revised close-up capture passes (`generated/active-fingers-runtime.log`, `NATURAL_MOTION_OK`), including a stronger check for finger motion after two seconds in each held emotion, rather than counting only transitions between poses. All eight measured finger middle joints and both thumb tips pass in anxiety, frustration, anger and crying. Joint bounds and resting-hand stability also pass. Representative lap, presenting, fist and face-covering frames were visually inspected after correcting the initial lap-clearance issue. This is authored clearance, not collision-based contact.

The current preview is `generated/active-fingers/alex-active-fingers.mp4`: 888 verified frames at 24 fps, 37 seconds at normal game timing. The manifest and `motion-checks.json` are alongside it. Final integration passes simulated player tracking/controller grip, all 20 facial expressions, tears, gaze, lip sync and pause/resume (`generated/active-fingers-integration.log`: `PLAYER_TRACKING_PREVIEW_OK`, `ALEX_PREVIEW_OK`).

## Finger separation and movement — 15 September 2026

NPC hands now spread at the finger roots using mirrored, calibrated axes; individual curl/release rates differ by digit. Open poses include wider thumb opposition, while fists reduce spread. Anxiety and explicit fidgets make small intermittent finger/thumb adjustments with different phases for each hand. The player controller path retains its existing targets without the NPC spread/fidget layer. See `NATURAL_MOVEMENT.md`.

The Windows build succeeds (`generated/finger-motion-build.log`). The close-up recording passes joint bounds and measures movement in all eight finger middle joints and both thumb tips (`generated/finger-motion-runtime.log`, `NATURAL_MOTION_OK`; `generated/finger-movement/motion-checks.json`). Open, resting, closed and crying hand poses were visually inspected. The encoded preview is `generated/finger-movement/alex-finger-movement.mp4`: 744 verified frames at 24 fps, 31 seconds at normal game timing.

Final integration passes simulated player tracking/controller grip, 20 expressions, tears, gaze, lip sync and pause/resume (`generated/finger-motion-integration.log`: `PLAYER_TRACKING_PREVIEW_OK`, `ALEX_PREVIEW_OK`). These remain procedural poses with no finger collision/contact solver.

## Wrist, forearm and elbow correction — 15 September 2026

The previous movement pass still allowed implausible hand orientation because it assigned a world-space wrist quaternion after IK. Its smoothness checks did not catch that defect. `ArmJointMotion` replaces that path with a calibrated elbow plane, bounded elbow flexion, forearm pronation/supination through a thumb-up neutral frame, and bounded wrist flexion/deviation. CC forearm twist helpers distribute the rotation; the elbow share bone retains the unrolled frame. Clavicle motion is increased modestly. Crying elbow hints and hand spacing were adjusted for the constrained wrists. See `NATURAL_MOVEMENT.md` and the source-rig audit `generated/arm-joint-rig.json`.

The Windows build succeeds (`generated/joint-motion-build.log`). The 53-second recorded regression passes (`generated/joint-motion-runtime.log`, `NATURAL_MOTION_OK`), now checking actual bone geometry through transitions: maximum wrist bend 52.31°, residual wrist twist 8.93°, elbow bend 8.00–137.89°, and hinge-plane error under 0.03°. The recording includes palms-up frustration/confusion, anger, face-covering crying, fear, panic, disgust, despondency and rest. The video decodes to 1,272 frames: `generated/joint-movement/alex-joint-movement.mp4`; metrics are alongside it in `motion-checks.json`. Representative resting, raised-palm, stop-hand and crying poses were visually inspected. This validates the recorded cases and authored limits, not every possible anatomical/contact configuration.

The final integration rerun passes simulated player tracking, all 20 facial expressions, tears, gaze and prerecorded speech lip sync/pause/resume (`generated/joint-motion-integration.log`: `PLAYER_TRACKING_PREVIEW_OK`, `ALEX_PREVIEW_OK`). Physical headset testing remains separate.

## More natural seated movement — 15 September 2026

Alex now uses thigh-relative supported hands, gentler resting finger curl, velocity-preserving arm transitions, elevation-dependent elbow directions, and small clavicle follow-through. Happy/frustrated/confused gestures release back to rest at different times on each arm. Rapid anxiety oscillation is replaced by smaller intermittent fidgets. Low-key speech beats follow actual playback in suitable emotional states. Despondency retains its collapsed posture with hands supported on the thighs. See `NATURAL_MOVEMENT.md`.

The Windows build succeeds (`generated/natural-motion-build.log`). The 43-second recorded sequence passes motion checks (`NATURAL_MOTION_OK`): maximum hand speed 0.97 m/s, peak wrist change 14.35 degrees per captured frame at 24 fps, and maximum clamped reach discrepancy 1.75 cm. Resting-hand stability is checked after transitions. Video and report: `generated/natural-movement/alex-natural-movement.mp4` and `motion-checks.json`. Rest, raised gestures, face-covering crying and despondent hand placement were visually reviewed; the video decodes to all 1,032 expected frames.

The final integration rerun passes simulated player tracking and all 20 expressions, tears, gaze, speech lip sync, pause/resume and stop (`generated/natural-motion-integration.log`: `PLAYER_TRACKING_PREVIEW_OK`, `ALEX_PREVIEW_OK`). This remains procedural IK rather than motion capture or collision-based contact. Sleeve deformation remains limited by the supplied skin weights; Quest comfort/performance is not established by offline recording.

## Baked room lighting and skin — 15 September 2026

Enhanced detail and Soft film remain the defaults. The furnished room now loads from a baked scene with one directional lightmap, 76 mapped renderers and 180 light probes. Existing lights retain realtime direct illumination/shadows; a broad baked window emitter supplies soft daylight, and the room's indirect contribution is precomputed. Startup activates the lighting scene before using its probe data. Both animated avatars receive interpolated room lighting. The old approximate window fill is disabled when baked lighting is enabled.

Alternate jumper skin materials reduce uniform specular shine and strengthen normal detail slightly, preserving the source textures, facial flush and tears. This is a subtle URP Lit treatment, not subsurface scattering. Settings → Visual style → Lighting and skin exposes independent, persistent switches; both default on. See `BOUNCED_LIGHTING_AND_SKIN.md` for the bake workflow and limitations.

The Windows build passes (`generated/lighting-skin-build.log`, `LIGHTING_SKIN_BUILD_OK`). The visible desktop comparison passes (`generated/lighting-skin-runtime.log`, `LIGHTING_SKIN_OK`): baked lightmap switching, reflection refreshes, eight skin bindings across both avatars, and tears. Room, original/natural skin, angry, afraid, crying, happy and menu captures are in `generated/lighting-skin-preview/`. The integration rerun also passes simulated player tracking plus 20 expressions, 72 tear anchors, gaze, and prerecorded speech lip sync/pause/resume (`generated/lighting-skin-integration.log`, `PLAYER_TRACKING_PREVIEW_OK` and `ALEX_PREVIEW_OK`). Moving room furniture requires a rebake. Physical Quest rendering and performance remain unverified.

## Object rendering and Soft film default — 15 September 2026

Soft film is now the fallback preset for new preferences; existing saved choices are respected. Settings → Visual style → Room detail switches enhanced materials and lighting on/off independently of the filter. Sixteen alternate material assets provide 34 bindings in the furnished room: source ARM crevice shading restored, wood/plaster roughness maps connected, and stronger floor normal response. A shadowed window spotlight and a small local fill replace the broad unshadowed window fill in Enhanced mode. Original material assets are preserved.

The PC quality profile had disabled realtime reflection probes. They are now enabled. A room-only layer prevents people/menu panels from appearing in its cubemap; the probe uses box projection and captures 256 pixels per face in Enhanced mode, 128 in Original, on setup or changes only. Captures have a bounded timeout.

Build: `generated/room-detail-build.log`, `SURFACE_DETAIL_BUILD_OK`. Final desktop verification: `generated/room-detail-visible.log`, `ROOM_DETAIL_OK`; report and inspected before/after room, furniture, face, crying and menu captures are in `generated/room-detail-visible/`. Both reflection refreshes completed, 34 bindings were found, and tears remained visible. Hidden/minimized Windows previews did not process reflection captures, so final verification used a visible game window. The older hidden-preview failure logs remain for diagnosis. Quest rendering/comfort/frame time remain untested.

## Visual styles — 15 September 2026

Settings now includes Visual style: Original, Warm natural (default), Soft film and Clear daylight, with persistent strength and soft glow controls. The player camera uses URP colour adjustments, white balance, tone mapping and restrained bloom. Existing room materials, ambient occlusion and shadows remain in place. See `VISUAL_STYLES.md`.

The Windows build passes (`generated/visuals-build.log`, `VISUALS_BUILD_OK`). The desktop comparison verifies the loaded volume profile, active exposure/tone mapping for all styles, Original/zero-strength bypass and the Settings → Visual style button (`generated/visual-styles/visuals-check.json`, `VISUALS_PREVIEW_OK`). Room and face captures show distinct output for each look; the menu was visually inspected. Diagnostic captures now use the full URP camera render so the volume stack is updated. Saved user preferences were not changed by the diagnostic. Physical headset rendering, comfort and frame time remain unverified.

## Student description visibility

The character picker now includes Hide descriptions / Show descriptions. Student view omits summaries and teaching focus and uses neutral case numbers in the picker and Session heading. The choice persists across launches. The Windows build succeeds; the focused runtime check passes hiding, reopening, Session-page concealment, saved preference and restoration (`generated/student-menu/description-check.json`). Screenshots are in that directory. No dialogue/profile behavior changed.

## Menu and character library — 12 September 2026

Game controls now live in a world-space menu with Session, Characters & situations, Settings and a character-preview subpage. Escape/right B toggles it and pauses/resumes speech. It supports desktop clicks and the right-controller ray, persistent speech volume/subtitles/microphone selection, recentering, and fresh scenario starts. The desk console and permanent desktop options panel are removed.

`characters/catalog.json` currently contains Alex's earthquake situation. Both existing visual appearances are selectable, with matching portraits. The bridge loads each session's selected profile and starting state; switching invalidates old work and clears history. No additional fictional patient/scenario has been authored. See `MENU.md` and `../characters/README.md`.

The 22 service tests pass, including catalog selection, independent profile prompts/openings/reset state, invalid IDs, repeated switching and cancellation during generation. Menu screenshots and interaction checks are in `generated/menu/`; build/runtime logs are `generated/menu-build.log` and `generated/menu-runtime.log`. Physical Quest menu interaction and comfort remain to be checked.

The built menu passed desktop UI raycasting, simulated controller selection, both visual appearances, new-session switching, pause/resume and settings persistence (`MENU_PREVIEW_OK`). A complete live Qwen/Kokoro reply also passed (`SMOKE_PLAYBACK_OK`, `SMOKE_OK`; `generated/menu-live-runtime.log`). Scenario replacement retires the old session ID, so delayed messages or Stop requests cannot affect the new conversation. Test services are stopped after verification.

## Live jumper and seated player — 12 September 2026

The main consultation scene and Windows executable now use the jumper as Alex and a derived headless, blue-green-sweater player avatar. The audition remains separate. All 20 facial states compose with audio-clock speech, jaw/eye bones, blinking, gaze, flushing and 72 skin-following tear anchors. Spatial speech originates at Alex's head.

The player has headset-driven torso lean/yaw, controller-driven arm IK, grip/trigger finger poses, tracking-loss rest poses, bounded arm reach, and automatic or left-X seated recentering. The first-person camera was moved above and forward of the collar after screenshot review. See `PLAYER_AVATAR.md` for controls and limitations.

Verification: successful Unity build; 18 Python service tests; main-scene desktop diagnostics passed for all 20 states, tears, audio cue playback, pause/resume, interruption and gaze. Player diagnostics passed head removal, reachable targets, unreachable-target stability, finger movement, torso response and tracking loss. Reports and screenshots: `generated/consultation-integration/`. Build and runtime logs: `generated/consultation-final-build.log`, `generated/consultation-integration-runtime.log`, `generated/consultation-live-runtime.log`.

The final build also completed a live Qwen/Kokoro reply through the bridge, with jaw movement and head-positioned audio (`SMOKE_PLAYBACK_OK`, `SMOKE_OK`). The test services were shut down afterward. Speech recognition code was unchanged; this run did not exercise a physical microphone.

Quest 3 hardware validation remains: controller wrist offsets, microphone/audio routing, comfort, tracking recovery and sustained frame time. The body infers shoulders from head/controller poses and keeps the legs seated; it is not optical hand tracking or full-body tracking. Detailed hand/clothing polish and expressive TTS remain deferred.

## Earlier implementation and verification history

Environment update: a furnished room now replaces the primitive blockout. It uses seven free Poly Haven models, wood/plaster textures, and original architecture, curtains, tissue box, and desk details. The room prefab contains 91,197 triangles across all placed instances, excluding Alex. See [environment assets](ENVIRONMENT_ASSETS.md). Expressive TTS remains deferred at the user's request.

The Windows development build is at `unity/Builds/Windows/AlexPrototype.exe`. Start it with `tools/launch.ps1 -Desktop` from the project root. The launcher manages the local inference and speech services. Use `tools/stop-services.ps1` after closing the game.

## Expressive body revision

The previous subtle preview was rejected. The current build replaces the repeating seated motion with a stable seated foundation and distinct upper-body performances. Intense crying covers the face with both palms and pulses the shoulders; anger uses alternating arm sweeps and curled fingers; fear/numbness hold still; disgust recoils and raises a warding hand. Facial gains, gradual flushing, wider tear tracks and moving beads improve visibility. The 53-second `generated/animations/alex-expressive-v2.mp4` shows the revised runtime. The new Windows build and facial playback diagnostic pass, alongside all 18 service tests. Recorded motion checks measure about 29 cm of angry hand sweep and less than 0.1 mm of settled head motion in fear/numbness. All 72 tear anchors resolve. See `generated/animations/expressive-motion-checks.json`; the video encoder verified all 1,272 frames. Actual player-camera stills were inspected separately from the closer comparison camera.

## Implemented and checked

- Unity **6000.6.0f1** imports the supplied character, preserves six animation clips, and successfully builds the Windows player. The runtime scene contains a furnished consultation room, the seated Alex, subtitles, session controls, and head/torso/hand overlays.
- The built executable creates a bridge session, receives a real Qwen reply, loads Kokoro WAV audio, starts speech playback and matching body cues, and produces `SMOKE_OK`. Its offscreen render was inspected for character materials, seating, and text layout. See `generated/runtime-preview.png`.
- The preferred **Qwen3.8 27B IQ4_XS** runs through pinned **llama.cpp b10909**, with a 4K context and thinking disabled. `generated/model-manifest.json` records the revision and verified SHA-256. No MTP speculation is enabled.
- **Kokoro ONNX**, voice `am_michael`, runs locally on CPU. **faster-whisper small.en**, CPU int8, transcribed a generated WAV through the bridge. This checks the speech path using synthetic audio; it does not establish live microphone quality.
- All **18 service tests pass**, covering structured output, reasoning separation, invalid control syntax, cancellation, reset, HTTP boundaries, the model request format, mouth timing validation/fallback/history separation, and all 20 emotions plus common aliases.
- Alex's generated FBX now has **27 facial shape bindings** and retains all six source animation clips. A shared, editable catalog supplies **20 delivery states**, including crying, fear, panic, disgust, anger, happiness, surprise, shame, confusion, hope, despondency, and numbness. Expressions, irregular blinking, gaze tracking/aversion, and speech mouth shapes compose with his seated body motion. See [Alex performance](ALEX_PERFORMANCE.md).
- A real Kokoro/Rhubarb HTTP round trip delivered a WAV and 32 validated mouth cues in 4.554 seconds, including cold speech setup, using scripted dialogue. This isolates the new speech/performance path from inference; it is not a new Qwen benchmark. Evidence: `generated/facial-service-check.json`.
- The Windows facial diagnostic passes with **27 active bindings and all 20 catalog states rendered**. All 72 tear-surface anchors resolve; tears appear during crying, fade after a different state, and clear after interruption. The prerecorded speech fixture still produces six observed mouth cue types, zero playback-clock drift while paused, successful resume, mouth closure after interruption, and opposite eye yaw for left/right targets. Expression and gaze portraits are in `generated/alex-unity-*.png`; numerical evidence is in `generated/unity-facial-playback.json`. Playback was muted and used no LLM.
- The launcher was tested from stopped services, then used for the executable smoke test. The stop script shut down both bridge and inference server; both health endpoints were confirmed unavailable afterward. Temporary services are stopped, so the next run starts them afresh.
- Character source metadata confirms **Cool Man by ardhanaputra, CC BY 4.0**. See `../ASSET_CREDITS.md`.

## Initial measurements

These are individual service samples on this development host, which reported an **RTX 5090 / 32 GB**, not a statistical benchmark or a headset test.

| Sample | Time |
|---|---:|
| First model generation | 2.089 s |
| First model reply plus cold voice synthesis | 13.458 s |
| Subsequent model generation | 1.069 s |
| Subsequent reply plus voice synthesis | 2.044 s |
| First speech transcription of the generated sample | 2.939 s |

The transcription measurement and reply measurements are separate stages. These values exclude player speech duration, headset transport, and most playback/UI overhead. Evidence: `generated/first-local-reply.json` and `generated/local-roundtrip.json`.

## Remaining work, in order

1. **Quest Link playtest:** select the Meta OpenXR runtime; verify seated height, head tracking, right A push-to-talk, controller ray buttons, headset microphone and audio routing. Measure sustained frame times alongside inference on the intended RTX 4090 configuration. No headset was available to the automated test; OpenXR logged `XR_ERROR_FORM_FACTOR_UNAVAILABLE` and the desktop path continued.
2. **Further character performance:** refine hand contact and gesture timing through playtests, then evaluate expressive voices. Facial controls, timed lip sync, an expanded emotion catalog, prototype tear tracks, blinking, and gaze are implemented. Kokoro currently uses one voice and does not apply arbitrary emotional voice styles or audible sobbing. `wipe_tear` now has a short right-hand reach; contact polish remains. Longer conversations must establish that model-selected emotions are appropriately varied and paced. The seated player avatar is implemented; physical headset validation remains.
3. **Conversation robustness:** run a ten-minute scenario evaluation. The initial exchange retained the safe-family fact but invented a sister detail, so biography consistency needs evaluation and tighter prompting if that detail is undesirable. Track heard segments in history when playback is interrupted; currently generated replies enter history before they finish playing.
4. **Latency and usability:** synthesize/play sentence segments progressively, add speech endpoint detection after push-to-talk is reliable, and measure median/tail response latency including lip alignment. Validate the furnished room's scale and comfort in the headset.

This is the first integration prototype. It does not yet satisfy every acceptance check in `../EXECUTION_PLAN.md`, and no claim of 90 Hz headset performance has been established.

## Jumper candidate emotional performance

A separate Unity candidate build now demonstrates CC facial controls with visible crying, facial flushing, seated upper-body gestures and held fear/numb poses. See `generated/jumper-emotions/video/jumper-emotions-full.mp4` and `CHARACTER_CANDIDATES.md`. The jumper is now also the live conversation character; the original Alex source/prefab remains available. Sleeve contact at deep elbow bends remains rough.

### Distinct emotion cues

The latest jumper comparison is `generated/jumper-contrast/video/jumper-emotion-contrast.mp4` (67 seconds). Anger now uses a forward glare, compressed lips and a discrete fist beat with a tense hold; frustration uses open palms and head shaking. Despondency collapses slowly with hanging hands, sadness stays more upright, and numbness holds a level stare. Surprise recovers after its startle. The candidate Unity build succeeds and its runtime completes 1,608 recorded frames; visual review includes both the wide poses and face close-ups. Tear anchors remain 72/72, and the largest clamped hand-target discrepancy observed is about 3.4 cm. See `CHARACTER_CANDIDATES.md` for the full comparison notes.

### Hand refinement

The candidate hand layer now uses individual local joint hinges, digit-specific relaxed/open/cupped/fist poses, separately controlled thumb joints and smooth release. The first anger beat waits for the hand to close. The source rig was audited, and the final Unity build and hand recording completed successfully with 864 frames (36 seconds). Both open palms fit the adjusted preview framing; fists, relaxed hands and crying hand poses were visually inspected. Preview: `generated/jumper-hands/video/jumper-hand-refinement.mp4`. This does not add collision-based finger placement.

