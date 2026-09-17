# Psychology VR — Alex prototype

Unity 6000.6.0f1, Windows PCVR, Meta Quest 3. One seated character with local speech recognition, Qwen dialogue, Kokoro voice, facial expressions, gaze, timed lip sync, and structured body cues.

![Furnished consultation room](docs/generated/furnished-room.png)

## Clone and open

Install Git LFS before cloning so the character and room art download correctly:

```powershell
git lfs install
git clone https://github.com/IgorCulafic/psychology-vr.git
cd psychology-vr
git lfs pull
```

In Unity Hub, add **the `unity` subfolder**, use Unity **6000.6.0f1**, and open `Assets/PsychologyVR/Scenes/Consultation.unity`. The converted character, furniture, textures, prefabs and baked lighting are included. No original download packs are needed to open the scene. Follow the environment setup below before running live dialogue; build the Windows player from Unity before using the launcher.

This repository contains the game, original model packs, local service, asset preparation tools, and speech research. Download the existing Windows game and character-preview builds from [Releases](https://github.com/IgorCulafic/psychology-vr/releases). Personal reference recordings, generated voice clones, model weights and import caches stay on the development machine. See [repository contents and setup notes](docs/REPOSITORY.md).

## Speech research status

The game currently uses **Kokoro**. **Higgs TTS 3** is the leading expressive-voice candidate after local Fish, OmniVoice and Higgs auditions; it is not integrated into the live game yet. The preferred anger sample uses the full reference, temperature **0.70**, top-p **0.95**, top-k **50**, seed **42**. Temperature 0.60 was closer to the source voice but less angry. See [listening results](docs/ALTERNATIVE_TTS_AUDITIONS.md) and [speech research](docs/SPEECH_RESEARCH.md).

## Run on this computer

From PowerShell in this folder:

```powershell
./tools/launch.ps1 -Desktop
```

For Quest Link, connect the headset, make Meta Horizon Link the active OpenXR runtime, and run:

```powershell
./tools/launch.ps1
```

The launcher starts project-local model and speech services. The initial Qwen load and first Kokoro/STT use take longer than subsequent requests. The first run is not a latency benchmark.

Controls:

- **Menu:** opens at startup. **Escape / right B** toggles it and pauses/resumes speech. Use the mouse or the right-controller ray and trigger to select buttons.
- **Characters & situations:** choose a profile and appearance, then **Start new conversation**. Currently Alex's earthquake situation is available, with jumper and original Alex appearances. Starting again clears the previous history and plays the selected profile's opening.
- **Hide descriptions:** student view hides backstories, teaching focus and revealing situation titles, including the Session heading. Show descriptions restores them; this preference persists.
- **Desktop:** type and Send in the Session menu, or return to the room and hold Space to record; release to transcribe/send. Right mouse drag looks around when the menu is closed.
- **Quest:** hold right **A** to record and release to send. **Left X** recenters. Grip and trigger animate the player's fingers; headset and controller poses drive the torso and arms. Select the intended microphone in Settings; headset routing requires an on-device test.
- **Session → Stop reply:** interrupt playback and invalidate pending responses. **Begin/Restart conversation** starts fresh.
- **Settings:** speech volume, subtitles, microphone, recenter, reconnect and Quit. Volume, subtitles and microphone preferences persist.
- **Settings → Character preview:** test face/body emotions independently of the model.
- **Settings → Visual style:** compare Original, Warm natural, Soft film (default) and Clear daylight; adjust filter strength and soft glow. **Room detail** switches between original and enhanced materials, shadows and reflections independently of the colour preset. Preferences persist. See `docs/VISUAL_STYLES.md`.
- **Visual style → Lighting and skin:** compare baked bounced lighting and natural skin shading independently. Both default on; bounced lighting requires Enhanced room detail. See `docs/BOUNCED_LIGHTING_AND_SKIN.md`.

The desk console and permanent options overlay have been removed. See `docs/MENU.md` for behavior and `characters/README.md` for adding characters and situations.

Close the game, then free GPU memory with:

```powershell
./tools/stop-services.ps1
```

The stop script only stops processes recorded by this project's launcher. If manually running the service/model in a terminal, stop them in that terminal.

## Open and build in Unity

Add the `unity` folder to Unity Hub and use **6000.6.0f1**. Open `Assets/PsychologyVR/Scenes/Consultation.unity` and press Play. The bootstrap loads the baked `ConsultationLighting` room scene, then creates the live jumper character, headless seated player and menu. The furnished `ConsultationRoom.prefab` remains the editable source and fallback. After changing the room layout, regenerate its lighting scene as described in `docs/BOUNCED_LIGHTING_AND_SKIN.md`. See `docs/ENVIRONMENT_ASSETS.md` for asset sources and `docs/PLAYER_AVATAR.md` for tracking details.

The editor opens Consultation automatically when starting from a clean blank scene, and the normal Play button starts Consultation. You can also choose **Psychology VR → Open consultation scene**. Existing unsaved scenes are preserved. To run another scene, such as the character audition, choose **Psychology VR → Play the currently open scene**.

Start the local services without launching the game using `./tools/launch.ps1 -NoGame`.

Unity menu **Psychology VR → Build Windows prototype** writes `unity/Builds/Windows/AlexPrototype.exe`. **Create prototype scene** regenerates the prototype scene and character materials; save any custom scene work under another name before rerunning it.

## Current features and limits

The live configuration is `services/config.local.json`: Qwen IQ4_XS through llama.cpp on port 8087, Kokoro on CPU, and faster-whisper `small.en` on CPU. The bridge binds only to 127.0.0.1:8765. Thinking is disabled both in the model startup configuration and each dialogue request.

`services/config.example.json` is explicitly **scripted test mode** with Windows' built-in voice and no STT. It exists for transport and animation testing; its responses are not AI. To use it, stop live services and run `./tools/launch.ps1 -Scripted -Desktop`.

Alex has 20 configurable delivery states, including crying, fear, panic, disgust, anger, happiness, surprise, shame, confusion, and emotional numbness. Try them in Settings → Character preview, with adjustable intensity. Local Rhubarb analysis generates timed mouth shapes from each synthesized WAV; Unity uses the audio playback clock, including pause/resume and interruption. Providers without alignment use an audio-envelope fallback. See `docs/ALEX_PERFORMANCE.md` for the full catalog, reproduction steps, and verification.

The live character now uses the supplied jumper rig, with its authored facial controls, tears, flushing, eye/jaw bones and seated body poses. Crying includes face-in-hands and sobbing motion; anger uses clenched hands and emphatic beats. The `wipe_tear` cue has a short right-hand reach. The headless player has a blue-green sweater, seated legs, headset-driven upper body and controller-driven arms/fingers. See `docs/PLAYER_AVATAR.md` for controls and limitations. Kokoro still uses a consistent voice and does not produce sobbing or arbitrary emotional voice styles; expressive voice and further hand polish are deferred. Props remain static.

Replies are fully generated and synthesized before playback. Sentence streaming and hands-free turn detection are next steps. Stop/reset suppress stale results and queued playback; the local inference request may finish in the background. History currently includes a generated reply even if the player interrupts halfway through hearing it; tracking which segments were actually heard is a follow-up.

Desktop tests cannot verify headset comfort, controller mappings, microphone routing, or sustained 90 Hz. Those require a Quest playtest. This development machine reported an RTX 5090/32 GB; performance must also be checked on the intended RTX 4090 target.

## Reproduce the local environment

The core bridge uses Python's standard library. Neural speech dependencies are pinned in `services/requirements-lock.txt`.

```powershell
uv venv --python 3.11 .venv
uv pip install --python .venv/Scripts/python.exe -r services/requirements-lock.txt
Copy-Item services/config.live.example.json services/config.local.json
./.venv/Scripts/python.exe tools/download-runtime.py
./.venv/Scripts/python.exe tools/download-lipsync.py
```

Download the selected model with the current Hugging Face CLI:

```powershell
./.venv/Scripts/hf.exe download HauhauCS/Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-MTP-GGUF Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-IQ4_XS.gguf --revision 993a5971fda8f30dd1b7eb2654792ba4415c7460 --local-dir .cache/models/qwen
./.venv/Scripts/hf.exe download Systran/faster-whisper-small.en --local-dir .cache/whisper/small.en
```

Put `kokoro-v1.0.onnx` and `voices-v1.0.bin` from the [kokoro-onnx model-files-v1.1 release](https://github.com/thewh1teagle/kokoro-onnx/releases/tag/model-files-v1.1) into `.cache/kokoro/`.

Standalone terminals for debugging:

```powershell
python tools/start-model.py
./tools/start-service.ps1
```

## Verification

```powershell
./.venv/Scripts/python.exe -m unittest discover -s services -v
```

The suite covers response validation, reasoning separation, reset, late responses, HTTP boundaries, and the model request contract. Generated evidence is in `docs/generated/`. See `docs/BUILD_STATUS.md` for the latest verified results and remaining work.

The AI model weights, virtual environments, downloaded runtimes, audio auditions, local configuration and Unity build/import caches are excluded from Git. Source character descriptions, original 3D model packs and converted Unity assets are included. Compiled builds are distributed separately through GitHub Releases. See `ASSET_CREDITS.md` for attribution. No blanket license is granted over the bundled third-party assets.
