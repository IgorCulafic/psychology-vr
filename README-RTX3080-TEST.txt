RTX 3080 PERFORMANCE TEST KIT - v0.5.4

For the complete PsychologyVR Windows application. Supports 3080 10 GB / 12 GB.
This small overlay includes the v0.5.3 service updates. It does NOT contain the
game, Python runtime, GGUF/Higgs/Whisper weights or the full cloned-voice packs.
Your services/config.local.json is not included or replaced.

1. Close the game and run Stop Services.cmd in the existing application.
2. Merge this PsychologyVR folder's contents into the application folder.
3. Double-click Test RTX 3080.cmd and select 1 (quick test).
4. Read REPORT.txt in the timestamped folder printed on screen.

Read docs/RTX3080_TEST_GUIDE.md for every test, measured baselines and tweaks.
Results: services/.runtime/rtx3080-tests/<timestamp>/
Missing model assets are reported as skipped; nothing is downloaded automatically.

Quick test measures QAT Q4 dialogue, BF16 cloned speech and CPU STT SEPARATELY.
The primary Q8 model and active application settings are preserved.
Menu 8 explicitly opts into an experimental NF4 voice-quality comparison.

The measured 3080 10 GB baseline showed ~3.5 s warm QAT dialogue, compared with
~21.5 s for partially offloaded Q8 (dialogue only). BF16 cloned speech used
~8.35 GiB resident allocated memory, leaving very little headroom on a 10 GB GPU.
Full GPU dialogue plus BF16 speech does not comfortably fit 10 GB or 12 GB.

No <=14 s audible result is promised. Verify end-of-user-speech to first audible
reply and later gaps in the real game using the included 20-turn CSV sheet.
No driver/power/clock settings are changed and no reports are uploaded automatically.
