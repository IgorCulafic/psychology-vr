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
least 24 GB VRAM, and preferably 64 GB system RAM. The development checks use an
RTX 5090. The 24 GB/RTX 4090 target still needs a separate hardware acceptance
test. Speech stays BF16; reducing speech quality is not part of setup.

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
  release's **setup-fix.zip**, extract it into the existing application folder
  (replace `tools/setup-portable.py`), and run **Setup.cmd** again. Keep your
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
