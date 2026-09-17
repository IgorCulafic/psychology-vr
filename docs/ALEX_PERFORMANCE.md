# Alex facial performance

The original Cool Man character is preserved in `man/`. The generated Unity FBX now contains 27 blendshape bindings across the skin, teeth, and two eyes, using 20 control names. All six source animation clips remain available. A sampled seated pose is the stable body foundation; the original repeating head and arm scans no longer dominate every emotion.

## Runtime behavior

- Twenty delivery states share one catalog: **neutral, calm, anxious, afraid, panicked, sad, crying, angry, frustrated, disgusted, happy, relieved, surprised, ashamed, guilty, confused, skeptical, hopeful, despondent, and numb**. Face, posture, trembling, blink spacing, and gaze avoidance vary with the preset and segment intensity.
- Fear and panic use widened eyes and tense/open lips. Disgust uses a nose wrinkle and upper-lip lift. Confusion and skepticism use asymmetric brows. Positive states use distinct smile strengths; withdrawn states reduce visible expressiveness. These are artistic performance choices, not diagnostic categories.
- Crying adds facial flushing, visible cheek tracks and moving tear beads, a larger sobbing mouth motion, and shoulder pulses. Above roughly 55% intensity, both hands increasingly cover the bowed face; hands periodically lower to reveal the wet face. Tears build and fade gradually. Stop suppresses sob pulses and fades tears. This is an authored wetness effect, not fluid simulation.
- Anger leans forward with alternating broad arm sweeps and finger curls. Fear freezes into a defensive pose; numbness holds a withdrawn pose without body idle movement. Panic raises protective hands with shaking; disgust recoils and wards away; happiness opens the arms; despondency slumps. Hand targets use two-bone IK with constrained reach, smoothed targets, and outward elbow poles. All performances remain seated.
- Blinks occur at irregular intervals. Gaze follows the player's head with restrained head movement and eye rotation; each state has an adjustable chance of glancing away. Gaze direction changes are smoothed.
- The bridge passes only validated dialogue text to TTS. After synthesis, local Rhubarb Lip Sync 1.14.0 analyzes the WAV with its English recognizer and transcript hint. Timings are attached as `mouth_cues`; the LLM does not generate them and they are excluded from character memory.
- Unity maps six basic speech shapes plus rest onto jaw, lip width, closure, and rounding controls. The clock is `AudioSource.time`, so pause/resume and interruption use the same timing as playback. A decoded PCM envelope softens quiet syllables.
- If alignment is disabled, unavailable, invalid, or exceeds its 15-second limit, speech still plays using an amplitude-based jaw fallback. Analysis is local CPU work using two threads. It currently adds preparation time before each reply plays.

`FacialPerformance.cs` runs after `PerformanceDriver.cs` and the seated animation. The body layer restores a stable sampled seated pose before applying emotional posture and hand IK. Gaze yields to bowed, frozen and turned-away poses, instead of pulling the head back toward the player. Original animation clips remain intact. Procedural rotations are restored before the next animation evaluation to avoid accumulating on unkeyed bones. Desktop **Manual face + body cues** buttons allow inspection without an LLM reply.

## Extending the range

Edit `unity/Assets/PsychologyVR/Resources/EmotionCatalog.json`. Both the Python bridge's model schema and Unity's preview buttons read it; this avoids a separate hardcoded list in each system. Each entry has a dialogue description, facial shape weights, posture, tremble/tear levels, blink timing, and gaze avoidance. The inspector-compatible C# types are in `EmotionLibrary.cs`. Rebuild Unity and restart the bridge after catalog changes. `tools/create-emotion-catalog.py` recreates the initial 20 presets and overwrites manual catalog edits, so it is not part of the regular build.

Common labels such as `fear`, `disgust`, and `anger` map to canonical cues. `depressed` maps to the artistic `despondent` delivery state; it does not assign Alex a diagnosis. The prompt encourages context-driven variety and gradual transitions rather than cycling through the catalog. Vocal performance still uses the existing Kokoro baseline: the new crying cue does **not** produce audible sobbing.

The desktop preview panel includes every preset and a 0–100% intensity slider. Labels and descriptions are for testing; only spoken `text` goes to TTS and subtitles. Intensity controls performance strength, including the transition from visible crying to face-in-hands sobbing. Select an intensity that fits the exchange; the animation range intentionally supports very readable extremes.

## Rebuild and inspect

From the project root, with Blender and Unity installed:

```powershell
python tools/download-lipsync.py
& 'C:/Program Files/Blender Foundation/Blender 5.2/blender.exe' --background --python tools/prepare_character.py
./.venv/Scripts/python.exe tools/prepare-facial-demo.py
& 'C:/Program Files/Unity/Hub/Editor/6000.6.0f1/Editor/Unity.exe' -batchmode -quit -projectPath "$PWD/unity" -executeMethod PsychologyVR.Editor.ProjectSetup.BuildAlex -logFile "$PWD/docs/generated/unity-alex-build.log"
```

`BuildAlex` regenerates the character prefab and prototype scene, checks that facial shapes survived FBX import, and builds the Windows player. Save custom scene edits separately before regeneration. Wait for `PSYCHOLOGY_VR_BUILD_OK` in the log before starting the player.

The diagnostic uses a prerecorded Kokoro line with real Rhubarb timings, muted playback, and no inference/bridge service:

```powershell
./unity/Builds/Windows/AlexPrototype.exe --desktop --alex-preview --capture-path "$PWD/docs/generated/alex-unity.png" -logFile "$PWD/docs/generated/alex-preview.log"
```

It writes portraits for every catalog entry plus `generated/unity-facial-playback.json`, checking shape bindings, expression count, tear surface anchors, tear appearance/fade, observed mouth cues, pause/resume, and interrupted mouth closure. It exits after capture. `tools/preview-face-shapes.py` offers separate Blender previews of the authored shape extremes.

`./.venv/Scripts/python.exe tools/check-facial-service.py` separately exercises the local HTTP bridge with scripted dialogue and real Kokoro/Rhubarb processing, retrieves the generated WAV, validates its mouth timings, and resets the test session. It shuts down its temporary server afterward.

## Recorded demonstrations

`docs/generated/animations/alex-expressive-v2.mp4` supersedes the earlier subtle demo. It shows nine contrasting performances from a fixed, wider seated view (53 seconds). Run the recorder with `--expressive-only` to capture just this comparison. The same components run in ordinary gameplay.

Earlier reference recordings in `docs/generated/animations/` include: all 20 emotions (65 seconds), gaze and existing body gestures (20 seconds), and a prerecorded speaking sample with the current Kokoro audio (7.25 seconds). They show the actual runtime components. Offline capture uses a fixed 24 fps simulation clock, so these videos are not a VR performance benchmark.

To regenerate, build the current player, run it with `--desktop --record-alex --record-dir "$PWD/.cache/animation-recording"`, and wait for `ALEX_RECORD_OK` in its log. Then run `tools/encode-animation-previews.py` with the project Python. It needs PyAV and Pillow; `--label-python` can point to a separate Python with Pillow installed. The speech fixture is reused, with no live inference. Normal gameplay timing is unaffected by this explicit recording mode.

## Limits

These are approximate authored controls on the supplied low-poly character, not a scanned facial rig or full phoneme set. The current body pass intentionally exaggerates the silhouettes and motion for readability across the room. Glasses partly obscure the eyelids and brows, and extreme close-ups reveal the original mesh's limits. Rhubarb is configured for English speech.

A short right-hand wipe cue is available. Audible sobbing/expressive TTS, standing/leaving the room, and the tracked player avatar remain separate work. This facial pass does not establish headset frame rate or microphone quality. The voice is still the existing Kokoro baseline. Natural selection and pacing of the expanded states require longer conversation playtests; schema support alone does not establish nuanced model behavior.
