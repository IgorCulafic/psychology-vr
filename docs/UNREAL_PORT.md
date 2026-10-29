# Unreal Engine port

This separate C++ Unreal 5.8 project lives in `unreal/`. Both clients use the same
local patient service, prompts, STT, sentence-streamed speech, configured voice
precision and automatic session journals. Unreal launchers reuse the existing
backend configuration; they do not change dialogue models or quantization.

## Status on 28 September 2026

Both game and editor targets compiled on UE 5.8.3. The required .NET Framework
SDK is now installed. Blender converted Jumper with 101 bones and 780 facial
shape keys, including a seated breathing animation. The room and character were
imported and a rendered desktop capture checked. An isolated test played two PCM16
audio segments through Unreal and verified that both reached conversation history.
This is a development port, not a finished replacement for the Unity release.
Live AI speech, microphone input and Quest Link operation still need acceptance
testing in Unreal; the playback test uses generated tones, not the speech model.

The client implements sessions, streamed replies, playback acknowledgements,
desktop text input, selectable microphone capture, subtitles, patient selection,
hidden case descriptions, facial blending and Blueprint performance events. The
room builder reuses tracked furniture and textures. Profiles share the Jumper
visual model initially.

Unity's body gestures, finger/contact solver, tears, skin redness, walking out,
and player hand/body meshes are not ported. The default body animation is seated
idle. A patient's decision to end a session stops conversation but does not yet
animate a physical exit. The animation events below are integration points for
Control Rig and the tools you choose.

## Setup

1. Install Unreal Engine **5.8** through Epic Games Launcher (developed on 5.8.3).
   Discovery checks `C:\Program Files\Epic Games\UE_5.8`; set `UE_ROOT` elsewhere.
2. Install Visual Studio Build Tools 2022 with C++ development tools, MSVC v143 and
   Windows SDK. Under Individual components install **.NET Framework 4.8 SDK** and
   **.NET Framework 4.8 targeting pack**. Unreal's editor requires these even though
   it bundles a newer .NET runtime.
3. Fetch art with `git lfs pull`. Install Blender for the first character conversion.
   Set `BLENDER_EXE` if it is outside the default Blender 5.2 installation. Conversion
   writes to `.cache/unreal` and leaves source art intact.
4. Run **Build Unreal.cmd** to compile, convert the character, import materials and
   furniture, and save `/Game/Psychology/Consultation`. Existing assets/maps are
   preserved. Logs: `services/.runtime/unreal-build.log` and `unreal-import.log`.
5. Use the launchers below. AI setup still uses the existing **Setup.cmd** workflow.
   Unreal is not yet bundled into the downloadable Windows release.

Close this Unreal project before rebuilding its module. If an import fails, inspect
the log before retrying. Setup deliberately preserves existing consultation maps.

| Launcher | Purpose |
|---|---|
| Open Unreal Editor.cmd | Open the room for development, without starting AI services |
| Start Unreal Desktop.cmd | Start/reuse AI services and launch the desktop client |
| Start Unreal VR.cmd | Start/reuse services and launch OpenXR; enter Quest Link first |
| Build Unreal.cmd | Compile and prepare the room and character |

Launchers prepare missing modules/maps automatically. They use the installed
editor's standalone game mode, not a cooked redistributable build. To inspect the
room without AI services:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools/launch-unreal.ps1 -Mode Desktop -NoServices
```

Close Unity before testing Unreal to avoid competing microphone/VR sessions. Shared
ports remain 8765 (bridge), 8766 (Higgs), and 8087 (dialogue). No second set of GPU
models is started. An independently managed test bridge can be selected with
`-NoServices -BridgeUrl http://127.0.0.1:PORT`. Use **Stop Services.cmd** afterward
when the models are no longer needed.

## Controls

Choose a patient and select **New conversation**. Select **Return to room** before
speaking. Hold **Space/right A** to record, release to send. **Escape/right B** opens
the menu. **R/left X** recenters. Right trigger activates the menu pointer. Desktop
also supports typed replies, mouse look in the room and **Backspace** to stop a
reply. Select the Quest microphone in the menu if Windows defaults elsewhere.
Headset mappings still require on-device verification.

Stopping speech acknowledges completed sentences and a conservative partial audio
duration. It does not guess words from an unfinished sentence. Partial duration
uses queued PCM playback and elapsed time with a buffering allowance; it is not
a measurement of the headset's physical output latency.

## Animation integration

Create a Blueprint subclass of `PsychologyPatient`, place it in the map, and override:

- **Perform(Beat)**: emotion/intensity, gesture, gaze, voice style, transition time,
  gesture duration, gesture start fraction and audio duration for this beat.
- **SpeechClock(Seconds, MouthCue)**: playback-aligned Rhubarb mouth cue; `X` is rest.
- **StopPerformance()**: stop transient gestures/lip sync on interruption or segment
  completion. Retain emotional pose while listening.

`GestureAt * AudioDurationSeconds` gives gesture start time. Default facial blending
uses existing CC morph names. Set **UseDefaultFace=false** when another animation
system owns those curves. Control Rig is enabled; third-party plugins have not
been installed. `PsychologySession` exposes `OnPerformance`, `OnSpeechClock` and
`OnPerformanceStopped` for other actor implementations. Provider-specific voice
tags and character prompts remain in the shared service.

## Remaining checks

The menu now offers installed dialogue models through the shared bridge. Select a model and press Apply between replies; conversation state and BF16 voice remain intact. See [model switching](MODEL_SWITCHING.md).

The desktop launcher waits for AI services before opening Unreal. It now prints each stage, watches for the room-ready marker, and prevents duplicate launches of the same mode. Logs are separate: `services/.runtime/unreal-desktop.log`, `unreal-vr.log`, and `unreal-editor.log`; the previous run is kept as `.log.previous`. On 28 September the reported startup crash could not be reproduced: both the automated menu test and the normal desktop launcher reached the room successfully. A delayed window opening was observed by the user; no definitive crash cause was established.

- Review facial deformation and the full range of emotions in rendered play.
- Verify live speech, interruption, patient changes, service reconnection
  and microphone selection against the live backend.
- Test Quest Link controls, audio routing, seated height and frame time with models
  loaded. Forward shading/MSAA are the starting VR renderer settings.
- Integrate and review the chosen animation tools before claiming Unity parity.

Run `python tools/test-unreal-client.py` to repeat the verified isolated playback
test. It uses an ephemeral localhost port, checks the committed history, and writes
`docs/generated/unreal-smoke.json` and `unreal-room.png`. Allow extra time for the
first shader compilation. Runtime flag `-PsychologySmoke -nohmd` starts an opening,
waits for confirmed playback, logs `PSYCHOLOGY_SMOKE_OK` and exits. Optional
`-PsychologyCapture=ABSOLUTE_PATH.png` saves a timed screenshot; in editor builds it
waits for material compilation before beginning the capture.
