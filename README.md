# Psychology VR

Psychology VR is a working prototype of a training tool where psychology students can practise counselling conversations with simulated patients. Students speak to an AI character who listens, responds, and expresses emotions through its voice, facial expressions and body language. The experience works in a VR headset or on a desktop, with speech recognition, dialogue and voice generation running locally on a single PC.

The project brings together character design, local AI, expressive speech and interactive 3D development. It is being developed for psychology training, with limited early testing so far and broader student testing planned for **November 2026**.

![Alex speaking in the virtual consultation room, with a Montenegrin subtitle](docs/images/consultation-speaking.png)

*The consultation prototype in action: Alex speaks in the furnished room, with subtitles accompanying his voice.*

## What works today

- **Spoken conversations:** talk through a microphone and hear the character reply, with text input and subtitles also available.
- **Four fictional patient profiles:** Alex, Nikola, Stefan and Ivan have distinct backstories and conversation guidance. Session memory helps retain earlier disclosures and corrections, and case descriptions can be hidden during practice.
- **Expressive characters:** facial expressions, gaze, tears, seated gestures and lip sync accompany speech. The live character currently uses procedural animation.
- **Voice cloning:** all three contributed voices have been cloned, with generated samples and selected emotional delivery presets available in an offline listening library. Assigning the voices to individual patients is still pending.
- **Reviewable sessions:** conversations are saved locally as readable transcripts and structured records for later review.

| Choose a patient and scenario | Practise with the case details hidden |
| --- | --- |
| ![Patient selection showing Alex's scenario and the four available profiles](docs/images/patient-selection.png) | ![Student view hides the patient's backstory and revealing scenario title](docs/images/student-view.png) |

For a quick look, see the [one-page project overview in Montenegrin](output/pdf/Psychology_VR_pregled_projekta_CG.pdf). The [latest Windows release](https://github.com/IgorCulafic/psychology-vr/releases/latest) also includes **Preview Voices.cmd**, which plays selected voice samples without loading the AI models.

## Development and model testing

Development has covered the Unity consultation environment, the local AI services, patient behaviour and memory, voice preparation, animation tools, model comparisons and Windows release packaging. The main engineering challenge is making speech recognition, dialogue, expressive voice generation and VR rendering work together on one PC.

| Part | Current choice | Why it was selected |
| --- | --- | --- |
| Dialogue | **Gemma 4 12B QAT Q4** | Preferred in conversational testing, with a smaller memory footprint that leaves more room for speech and VR. Tests also examined recall, character consistency and regional language quality. |
| Speech recognition | **Whisper large-v3-turbo**, through faster-whisper | Improved recognition in the project's Montenegrin speech checks. It runs on the CPU to leave GPU capacity for dialogue, voice and rendering. |
| Voice generation | **Higgs TTS 3 in BF16** | Selected through listening comparisons for expressive delivery and voice similarity. The higher-precision voice model was retained after testing lighter alternatives. |

Optimisation includes keeping the speech model loaded between replies, preparing voice references in advance, controlling dialogue context and GPU memory use, and playing completed sentences while later speech is being generated. Lip sync follows the audio playback clock so it stays aligned through pauses and interruptions.

These are development results, with language accuracy, character consistency and response delay still under review. See the [dialogue comparison](docs/GEMMA_VS_ORIGINAL.md), [speech recognition checks](docs/MONTENEGRIN_CONVERSATION.md), [voice listening tests](docs/ALTERNATIVE_TTS_AUDITIONS.md) and [sentence playback work](docs/SENTENCE_PLAYBACK.md) for measurements and their limits. Historical reports retain the models and settings used at the time; **Gemma is the current default**.

## Current status and next steps

The project is in active development. Some early testing has taken place; broader use with psychology students is planned for November 2026. It is not yet a fully implemented or validated training programme.

Current work focuses on **acted animations and video-based motion extraction (rotoscoping)**. A separate proof of concept transfers recorded facial expressions and head rotation onto the 3D character. Integrating these performances into live conversations, developing body animations, and assigning the cloned voices to patients are the next steps. See the [facial and head-motion prototype](docs/RECORDED_FACE_POC.md) and [voice library](voices/README.md).

Build stability and longer stress tests remain essential before student sessions. In the latest Quest Link test, the headset froze while the desktop game continued. The RTX 5090 test reached **22.40 GiB of total GPU memory use**; it does not establish stability on the intended RTX 4090 university PCs. Headset controls, microphone routing and sustained VR performance still need on-device checks. See the [Quest test report](docs/QUEST_LINK_LIVE_TEST.md), [memory breakdown](docs/GEMMA_VRAM.md) and [stress-test results](docs/HEADSET_FREE_STRESS.md).

## Download and run

For testing, download **psychology-vr-windows.zip** from the [latest release](https://github.com/IgorCulafic/psychology-vr/releases/latest), extract it, and double-click **Start VR.cmd**, **Start Desktop.cmd**, or **Start Text Chat.cmd**. The built game and approved voice are included. First launch automatically downloads the pinned local AI models and installs its private runtime; no Unity, Git or Python installation is needed. Allow about 45 GB free disk space and internet for first setup. Subsequent launches run locally. See [START HERE](START%20HERE.md) for hardware, Quest Link and controls.

Every release is a complete application package with all previous updates; no patch ZIPs are needed. See the **Updating** section in [START HERE](START%20HERE.md) to keep existing downloads, settings and session logs.

Use the release asset above, not GitHub's **Source code.zip**. The source repository is for development; the instructions below describe that workflow. The three contributed voice packs are tracked through Git LFS and included in the release. Use **Preview Voices.cmd** to hear selected samples; assigning these voices to patient characters is still pending.

Fresh setup selects **Gemma 4 12B QAT Q4**, **BF16 Higgs speech** and **CPU Whisper**. On an existing installation, **PC Settings.cmd → 6 Gemma** installs/selects the current default. In Unity, **Settings → Dialogue model** switches between installed alternatives between replies, preserving the conversation and voice settings. Older PC Settings presets remain available for comparisons; see [model switching](docs/MODEL_SWITCHING.md) before changing them.

## Voice and animation update

The v0.4.0 complete package adds an offline voice listening library, person 3's selected emotion presets, and the standalone facial/head-motion preview player.
The Unreal prototype remains source-only. See [release details](docs/RELEASE_0_4_0.md)
for the contents, capture setup and remaining integration work.

## Clone and open

Install Git LFS before cloning so the character and room art download correctly:

```powershell
git lfs install
git clone https://github.com/IgorCulafic/psychology-vr.git
cd psychology-vr
git lfs pull
```

In Unity Hub, add **the `unity` subfolder**, use Unity **6000.6.0f1**, and open `Assets/PsychologyVR/Scenes/Consultation.unity`. The converted character, furniture, textures, prefabs and baked lighting are included. No original download packs are needed to open the scene. Follow the environment setup below before running live dialogue; build the Windows player from Unity before using the launcher.

This repository contains the game, original model packs, local service, asset preparation tools, and speech research. Download Windows builds from [Releases](https://github.com/IgorCulafic/psychology-vr/releases). The three contributed voice packs and selected audition material are versioned; personal facial-capture footage, other local auditions, model weights and import caches stay out of Git. The runnable release also includes the approved shared reference voice. See [repository contents and setup notes](docs/REPOSITORY.md).

## Speech research status

The expressive game configuration uses **Higgs TTS 3 in BF16** after local Fish, OmniVoice and Higgs auditions. The preferred anger sample uses the full reference, temperature **0.70**, top-p **0.95**, top-k **50**, seed **42**. Temperature 0.60 was closer to the source voice but less angry. Kokoro remains available in the older lightweight configuration. See [live setup](docs/LIVE_EXPRESSIVE_SPEECH.md), [listening results](docs/ALTERNATIVE_TTS_AUDITIONS.md) and [speech research](docs/SPEECH_RESEARCH.md).

## Run on this computer

For **text-only character conversations**, run `./tools/launch-text-chat.ps1` and open http://127.0.0.1:8794/. Choose Alex, Nikola, Stefan or Ivan, hide/show their case descriptions, switch between Montenegrin and English, inspect emotional cues, and export a transcript. No headset or voice generation is needed. See [text testing instructions](docs/TEXT_CONVERSATIONS.md).

All four patients now have [bounded session memory and refined conversation guidance](docs/CONVERSATION_MEMORY.md), including recall of earlier preferences, disclosures and corrections beyond the recent dialogue window.

Text and VR sessions are [saved automatically](docs/SESSION_LOGGING.md) in `logs/sessions/`, with readable transcripts and detailed JSONL records. Students do not need to export; reset and character changes preserve earlier logs. These local logs are excluded from Git.

From PowerShell in this folder:

```powershell
./tools/launch.ps1 -Desktop
```

For Quest Link, connect the headset, make Meta Horizon Link the active OpenXR runtime, and run:

```powershell
./tools/launch.ps1
```

The launcher starts project-local model and speech services. Initial model loading and the first speech/STT requests take longer than subsequent requests. The first run is not a latency benchmark.

Controls:

- **Menu:** opens at startup. **Escape / right B** toggles it and pauses/resumes speech. Use the mouse or the right-controller ray and trigger to select buttons.
- **Characters & situations:** choose Alex, Ivan, Nikola or Stefan and an appearance, then **Start new conversation**. The cases currently share the existing avatar and reference voice. Starting again creates a fresh session, preserves the earlier journal and plays the selected profile's opening.
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

The local configuration is `services/config.local.json`. The current expressive setup uses **Gemma 4 12B QAT Q4** through llama.cpp on port 8087, resident **Higgs TTS 3 BF16** on port 8766, and **Whisper large-v3-turbo** through faster-whisper on CPU. `services/dialogue-models.json` records the selectable dialogue models. `config.live.example.json` retains the older English/Kokoro baseline; `config.expressive.example.json` describes the expressive pipeline. Use **Setup.cmd** for the current pinned runtime and machine-specific configuration. The bridge binds only to 127.0.0.1:8765. Thinking is disabled both in the model startup configuration and each dialogue request.

`services/config.example.json` is explicitly **scripted test mode** with Windows' built-in voice and no STT. It exists for transport and animation testing; its responses are not AI. To use it, stop live services and run `./tools/launch.ps1 -Scripted -Desktop`.

Alex has 20 configurable delivery states, including crying, fear, panic, disgust, anger, happiness, surprise, shame, confusion, and emotional numbness. Try them in Settings → Character preview, with adjustable intensity. Local Rhubarb analysis generates timed mouth shapes from each synthesized WAV; Unity uses the audio playback clock, including pause/resume and interruption. Providers without alignment use an audio-envelope fallback. See `docs/ALEX_PERFORMANCE.md` for the full catalog, reproduction steps, and verification.

The live character uses the supplied jumper rig, with authored facial controls, tears, flushing, eye/jaw bones and seated body poses. Crying includes face-in-hands and sobbing motion; anger uses clenched hands and emphatic beats. The `wipe_tear` cue has a short right-hand reach. Model replies can now direct gaze, transitions, pauses and timed gestures. Higgs maps validated emotion cues into expressive speech; voice identity and pronunciation still need listening tests. The headless player has a blue-green sweater, seated legs, headset-driven upper body and controller-driven arms/fingers. See `docs/PLAYER_AVATAR.md` for controls and limitations. Props remain static.

The player now [plays completed sentences while later speech is being prepared](docs/SENTENCE_PLAYBACK.md), keeping BF16 Higgs. The complete model reply is validated first. Playback acknowledgements keep unheard sentences out of history after interruption; unfinished sentence words are marked as unknown. Stop/reset suppress stale results and queued playback, although a running GPU call may finish in the background. The legacy text endpoint still returns a complete reply. Hands-free turn detection remains a follow-up.

Desktop tests cannot verify headset comfort, controller mappings, microphone routing, or sustained 90 Hz. Those require a Quest playtest. This development machine reported an RTX 5090/32 GB; performance must also be checked on the intended RTX 4090 target.

## Reproduce the local environment

Use the same pinned installer as the Windows release. In a source checkout, first supply `voices/reference.wav` and `voices/reference.json` with its matching `text` transcript, or configure an existing prepared reference as described in the [voice setup notes](voices/README.md#runtime-status). The release already supplies its shared reference.

```powershell
./Setup.cmd
```

The installer prepares a private Python environment, downloads the selected dialogue model, Higgs, Whisper and lip-sync tools, and writes the local configuration. Fresh installations select Gemma; existing configurations are preserved. To move an older setup to Gemma, use **PC Settings.cmd → 6 Gemma**. Build the Unity Windows player before using the game launcher, or use `./tools/launch.ps1 -NoGame` to start the services for the editor.

See [START HERE](START%20HERE.md) for setup requirements and troubleshooting, and [portable release setup](docs/PORTABLE_RELEASE.md) for packaging details. Neural speech dependencies are pinned in `services/requirements-lock.txt`.

## Verification

For repeatable model comparisons, use the [terminal runner](docs/MODEL_LAB.md#running-a-comparison).
The [six-model comparison report](docs/MODEL_COMPARISON_2026-09-27.md) includes actual
local test results and saved replies. **Start Model Lab.cmd** retains the optional
browser interface with side-by-side review. Both workflows share 16 multi-turn
scenarios, separate patient and reasoning tracks, repeated seeds and automatic
evidence exports, without changing game settings.

```powershell
./.venv/Scripts/python.exe -m unittest discover -s services -v
```

The suite covers response validation, reasoning separation, reset, late responses, HTTP boundaries, and the model request contract. Generated evidence is in `docs/generated/`. See `docs/BUILD_STATUS.md` for the latest verified results and remaining work.

The AI model weights, virtual environments, downloaded runtimes, personal facial-capture footage, local configuration, session logs and Unity build/import caches are excluded from Git. Source character descriptions, original 3D model packs, converted Unity assets and the three contributed voice packs with selected auditions are included. Compiled builds are distributed separately through GitHub Releases. See `ASSET_CREDITS.md` for attribution. No blanket license is granted over the bundled third-party assets.
