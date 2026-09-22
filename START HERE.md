# Run Psychology VR

Download **psychology-vr-windows.zip** from this private repository's latest
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

Requirements: Windows 10/11 x64, a current NVIDIA driver, an NVIDIA GPU with at
least 24 GB VRAM, and preferably 64 GB system RAM. The university's RTX 4090 / 64 GB
PCs are the target of the lighter preset. Development checks use an RTX 5090;
the preset still needs a full Quest session on an actual university PC.

**GPU setting:** Setup defaults to **Auto-detect GPU**. A 24 GB card selects
IQ3_M dialogue with 32 GPU layers; a 32 GB or larger card selects the original
IQ4_XS dialogue with 48 GPU layers. The remaining dialogue layers use system RAM
and the CPU. Speech stays BF16 in both presets; this setting never reduces voice
precision. Auto uses the capacity of CUDA device 0, not combined GPU memory.

To change the setting, close the game and double-click **PC Settings.cmd**:
choose **1 Auto**, **2 University / RTX 4090**, **3 Original quality**, or
**4 Fast dialogue (9B Q6)**. Fast keeps the smaller dialogue model fully on the
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

For VR, install Meta Quest Link, connect the Quest 3 to this PC, and enter its
PC Link environment before starting. This is a Windows PCVR game, not a Quest APK.
Use **right A** to record speech and release it to send; **right B** opens the
menu; **left X** recenters. Desktop: hold **Space** to record, **Escape** opens the
menu, or type in the session menu. Select the intended microphone in Settings.

Choose Alex, Ivan, Nikola or Stefan in the menu. Case descriptions can be hidden
from students. The text tester opens in your browser at `http://127.0.0.1:8794/`.
Sessions save automatically as TXT and JSONL in `logs/sessions/`. Keep this folder
when upgrading. Do not send student logs to GitHub.

The private release includes the owner's approved reference voice and transcript
in `voices/`. Keep that material within the intended testing group. Source-only
checkouts omit it: supply `voices/reference.wav` and `voices/reference.json`
containing `{"text":"The exact words in the recording."}` before setup.

After closing the game/browser, double-click **Stop Services.cmd** to release GPU
memory. Closing the browser alone does not stop the AI models.

## If setup or launch fails

- Keep `services/.runtime/setup-latest.log`; service logs are in the same folder.
- If a download was interrupted, run **Setup.cmd** again. Completed downloads are
  reused. Setup preserves existing configuration choices, adds missing settings,
  and backs up any configuration it upgrades in `services/.runtime/config-backups/`.
- If an older installer reports `KeyError: 'higgs_reference'`, download the latest
  release's **pc-settings-update.zip**, extract it into the existing application
  folder (replace matching files), and run **Setup.cmd** again. Keep your
  existing `.tools`, `.cache`, `voices` and `logs` folders.
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
