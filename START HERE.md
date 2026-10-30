# Run Psychology VR

## This updated local installation

Use **Start Desktop.cmd** or **Start VR.cmd** in this folder. The Unity game asks
for the student's name at launch, before the first patient reply. Enter it with a
physical keyboard or the controller keyboard, then choose **Start conversation**.
New conversations ask for a name again; cancelling keeps the existing session.
Saved session logs and exported transcripts include the student name.
In the game's **Session** menu, choose **Export session log** to save a named ZIP
in `logs/exports/`, containing the readable and structured logs.

The default is **RTX 3080 10 GB / English / Kokoro / Gemma QAT Q4**. Open
**Hardware Profiles.cmd** to choose the separate **RTX 4090 / Montenegrin /
BF16 cloned voices / Gemma Q8** profile. Close the game before switching.
Profiles retain compact responses, cached prompts, model warmup and exact speech
reuse where the voice provider supports it. Other optimization choices remain
optional in **Optimization Settings.cmd**. Previous configurations are backed up.

The requirements and historical release defaults below describe the original
university cloned-voice package. The local 3080 profile uses its smaller English
voice and transcription models instead.

## Original release installation

Download **psychology-vr-windows.zip** from this repository's latest
[GitHub Release](https://github.com/IgorCulafic/psychology-vr/releases/latest).
Extract the complete `PsychologyVR` folder to a writable location, such as
`D:\PsychologyVR`. Do not run the game inside the ZIP or move only the EXE.
GitHub's **Source code.zip** is for development and does not contain the player.

Double-click **Start Desktop.cmd** for mouse/keyboard, **Start VR.cmd** for Quest
Link, or **Start Text Chat.cmd** for the conversation tester. The first launch
automatically installs a private Python environment and downloads the pinned AI
models and runtimes. Leave its setup window open. Internet and approximately
45 GB free disk space are required for setup; later launches use local files.
There is no Unity, Git, Python, API key or paid speech service setup to perform.

In the current project build, desktop starts in borderless fullscreen. Press
**F11** or use **Settings → Display & subtitles** to switch to windowed mode.
The same menu changes desktop subtitle size; dialogue appears in a readable
panel at the bottom of the screen. These preferences persist between launches.

Requirements: Windows 10/11 x64, a current NVIDIA driver, an NVIDIA GPU with at
least 24 GB VRAM, and preferably 64 GB system RAM. The university's RTX 4090 / 64 GB
PCs are the target hardware. Development checks use an RTX 5090;
the current combination still needs a full Quest session on an actual university PC.

**Default model:** Setup selects **Gemma 4 12B QAT Q4**, fully on the GPU, with
**BF16 (16-bit) Higgs speech** and CPU speech recognition. Voice precision is
unchanged. Gemma was preferred in conversational testing; Bonsai is faster but
lost coherence in longer conversations. In-game **Settings → Dialogue model**
switches between installed alternatives after the current reply has finished.

**Legacy GPU setting:** Explicitly choosing **Auto-detect GPU** in PC Settings
selects the older Qwen presets. A 24 GB card selects
IQ3_M dialogue with 32 GPU layers; a 32 GB or larger card selects the original
IQ4_XS dialogue with 48 GPU layers. The remaining dialogue layers use system RAM
and the CPU. Speech stays BF16 in both presets; this setting never reduces voice
precision. Auto uses the capacity of CUDA device 0, not combined GPU memory.

To change the setting, close the game and double-click **PC Settings.cmd**:
choose **1 Auto**, **2 University / RTX 4090**, **3 Original quality**, or
**4 Fast dialogue (9B Q6)**, **5 Bonsai**, or **6 Gemma**. Choose **6 Gemma** to
install it or return to the current default. Fast keeps the smaller dialogue model fully on the
GPU and preserves BF16 speech. It is opt-in: review language and character
consistency before teaching. Auto continues selecting the existing 27B presets.
This stops this installation's AI services, backs up configuration changes and
prepares the selected model. Then use Start VR/Desktop/Text Chat normally.
New installations download only the selected dialogue quant: about 25 GB total
models for the 4090 preset versus 28 GB for original quality. Switching from the
old installation requires a one-time 12.8 GB IQ3_M download; the previous model is
kept for switching back. More CPU offload can increase reply latency.
Fast dialogue needs a one-time 7.4 GB download, or approximately 19.1 GB total
models on a fresh installation. See `docs/GPU_PRESETS.md` for measured timing and
known quality tradeoffs. Existing models remain available when switching back.
Gemma requires a roughly 7 GB dialogue download, plus the shared speech models
and runtimes. Only the selected dialogue model is downloaded during setup.
See `docs/MODEL_SWITCHING.md` for model switching and current test limitations.

For VR, install Meta Quest Link, connect the Quest 3 to this PC, and enter its
PC Link environment before starting. This is a Windows PCVR game, not a Quest APK.
Use **right A** to record speech and release it to send; **right B** opens the
menu; **left X** recenters. Desktop: hold **Space** to record, **Escape** opens the
menu, or type in the session menu. Select the intended microphone in Settings.

Choose Alex, Ivan, Nikola or Stefan in the menu. Case descriptions can be hidden
from students. The text tester opens in your browser at `http://127.0.0.1:8794/`.
Sessions save automatically as TXT and JSONL in `logs/sessions/`. Keep this folder
when upgrading. Do not send student logs to GitHub.

Resource logging is automatic while the updated conversation service is running.
`logs/performance/` records GPU load, dedicated VRAM usage, temperature and system
RAM approximately every two seconds, with UTC timestamps and selected model settings.
Measurements cover all applications on the PC. They do not measure headset FPS,
and brief spikes between samples can be missed. GPU load (%) and VRAM (MiB) are
separate measurements; missing readings are reported as unavailable.

After testing, double-click **Export Diagnostics.cmd**. Send the resulting ZIP from
`diagnostics/` back for review. It includes the last seven days of resource samples,
response preparation timings, playback progress and a readable `SUMMARY.txt`.
Cached opening lines are summarized separately from normal conversation replies.
First audio ready measures server preparation after accepted text, not the full
delay from releasing the microphone. Conversation text, recordings, credentials
and raw service logs are excluded from this export; nothing is uploaded automatically.
The original conversation logs remain in `logs/sessions/` for separate dialogue review.
No model downloads or Unity Editor are required to export after initial setup.

The release includes the approved shared reference voice and transcript, plus
three contributed speaker packs in `voices/`. **Preview Voices.cmd** opens their
selected generated samples without starting AI services. The current project
build assigns Igor to Ivan (burnout), Person 1 to Stefan (fire), Person 2 to
Nikola (bereavement), and Person 3 to Alex (earthquake). Each scenario selects
its clothed MetaHuman and approved emotion-specific voice settings automatically;
Ivan uses the Bruce model with a recorded seated idle and responsive wardrobe.
Facial reactions, neck movement, tears and live lip sync follow the conversation.
Other patients retain their existing body poses. See `docs/RELEASE_0_5_1.md` for
the merged animation update and `docs/BRANCH_INTEGRATION_2026_10_21.md` for the
performance handoff and tests still required on the university RTX 4090.
Source checkouts contain the contributed packs through Git LFS;
for initial setup, supply `voices/reference.wav` and its matching JSON transcript
or explicitly configure another prepared reference. See `voices/README.md`.

**Preview Recorded Face.cmd** opens the separate facial/head-motion player with
a prepared take folder dragged onto the launcher. Personal capture data is not
bundled. See `docs/RECORDED_FACE_POC.md` for extraction, and
`docs/RELEASE_0_4_0.md` for what is included and what remains unfinished.

After closing the game/browser, double-click **Stop Services.cmd** to release GPU
memory. Closing the browser alone does not stop the AI models.

## Updating

Every release is a complete application ZIP, including all previous fixes. No
patch ZIPs or older release downloads are required. For a fresh installation,
extract the complete folder and use a Start launcher as above.

To upgrade in place, close the game and run **Stop Services.cmd** first. Extract
**psychology-vr-windows.zip** into the parent of your existing `PsychologyVR`
folder and replace matching files. If you renamed your application folder, copy
all contents of the ZIP's `PsychologyVR` folder into that folder instead. Avoid
creating a second `PsychologyVR` folder inside the first one. Keep your existing
folder: merging the complete package preserves `.cache`, installed environments,
`services/config.local.json` and `logs/sessions/`, which the ZIP does not contain.
Then use your normal Start launcher. It reuses verified model downloads.

## If setup or launch fails

- Keep `services/.runtime/setup-latest.log`; service logs are in the same folder.
- If a download was interrupted, run **Setup.cmd** again. Completed downloads are
  reused. Setup preserves existing configuration choices, adds missing settings,
  and backs up any configuration it upgrades in `services/.runtime/config-backups/`.
- If an older installer reports `KeyError: 'higgs_reference'`, download the latest
  complete **psychology-vr-windows.zip**, follow **Updating** above, and run
  **Setup.cmd** again.
- If model files were removed or damaged after setup, run **Setup.cmd** again to
  check and repair the pinned downloads.
- If Windows reports a missing Visual C++ runtime/DLL, install Microsoft's
  [current x64 Visual C++ runtime](https://aka.ms/vs/17/release/vc_redist.x64.exe).
- Do not run two copies from different folders at once: the local AI service ports
  are shared. Stop the previous copy's services before switching installations.
- Moving the extracted folder causes setup to recreate its disposable Python
  environment. Models, voice, configuration and session logs remain intact.

Downloads retain their upstream terms and notices. Higgs is a research and
non-commercial model; asset credits are in `ASSET_CREDITS.md`. The package does not
grant additional redistribution rights over third-party assets or the voice.
