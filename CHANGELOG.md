# Psychology VR changelog

This log records the local RTX 3080 desktop setup and changes made during this session. It is not a complete history of the upstream application or a published release.

## 2026-10-11 — 72 FPS application limit

### Changed

- Changed NVIDIA Control Panel's per-application **Max Frame Rate** setting from **60 FPS to 72 FPS** for `C:\vr psych\PsychologyVR\unity\Builds\Windows\AlexPrototype.exe`, matching the requested 72 Hz Quest 3 use case.
- Applied the setting and verified that the saved program profile displays **72 FPS**.

### Application notes

- Restart the application for the updated limit to take effect.
- This is a driver setting on this PC, associated with the executable above. It is not embedded in the Unity build and does not automatically transfer to another PC.
- Desktop mode remains the selected launch mode. The headset refresh rate was not changed, and sustained 72 FPS or Quest 3 operation has not been measured in this session.

## 2026-10-10 — Gemma desktop configuration and faster replies

### Added

- Installed **Qwen3.5 9B Q4_K_M** as another desktop option, retaining the previously installed **Qwen2.5 7B Q4_K_M** and **Gemma 4 12B QAT Q4** models.
- Added the Qwen 9B entry to the model catalog and pinned its download in the portable setup manifest.
- Added a dedicated Qwen 9B launch profile, used by **Start Desktop Best.cmd**. **Start Desktop Gemma.cmd** selects Gemma; **Start Desktop 7B.cmd** selects Qwen 7B.
- Added four focused tests for compact response directions, compatibility with the full response format, reuse of the warmed speech engine, and rejection of an unavailable voice.

### Changed

- Selected **Gemma 4 12B QAT Q4** for the active desktop configuration on the **RTX 3080 with 10 GB VRAM**.
- Set Gemma to **40 GPU layers**, with the remaining layers using the CPU, to leave memory for the running game. Configured a 4,096-token context, a batch size of 64 and a microbatch size of 32.
- Enabled compact response directions: the model supplies text, emotion, intensity, gesture, voice style and gaze. The service calculates delivery timings locally and retains the existing semantic refinement of expressions and gestures.
- Preloaded and warmed the **Kokoro `am_michael` voice** at service startup. Speech generation reuses that loaded engine and verifies that the selected voice exists in the bundled voice bank.
- Added health information for the configured voice, loaded voice and available bundled voices. An unavailable voice produces an explicit error instead of silently substituting another voice.
- Kept speech recognition on the CPU using **faster-whisper small.en**, and retained **Rhubarb** lip-sync generation.
- Prevented the launcher from opening a duplicate instance of the same game executable. It reports when that application is already running.

### Verification

- Previously completed targeted checks: **41 tests passed**, covering fast delivery, streaming, performance behavior, patient relationships and model selection.
- In a small warmed generation comparison, compact directions reduced generation time from **4.652 seconds to 3.035 seconds**, a **34.8% reduction**. This measures generation only, not the complete spoken reply.
- With Gemma at 40 GPU layers and the game capped at **60 FPS**, two complete reply-generation checks, including speech and lip-sync preparation, took **23.88 seconds** and **25.17 seconds**. Peak memory across the whole GPU was **9,123 MiB**, approximately **8.9 GiB**.
- These timings were recorded before the change to 72 FPS. Performance at the new cap has not been benchmarked.

### Speech behavior

Gemma generates the dialogue text and response directions. Kokoro supplies the audible voice from its loaded voice bank; the voice is not part of the Gemma language model. The current desktop configuration uses `am_michael`.

## 2026-10-01 — Initial RTX 3080 desktop setup

- Added both the source folder and `C:\vr psych\PsychologyVR` to **PsychologyVR.code-workspace**.
- Configured desktop launchers to use the existing Windows build at `C:\vr psych\PsychologyVR\unity\Builds\Windows\AlexPrototype.exe` with the project-local AI services.
- Prepared desktop profiles for Qwen 7B and Gemma. The existing Windows player was used; no Unity rebuild was performed.

## Local verification records

- Compact response comparison: `services/.runtime/gemma-delivery-benchmark.json`.
- Complete reply timings and GPU memory samples: `services/.runtime/gemma-desktop-check.json`.
- Active configuration: `services/config.local.json`.
- Gemma desktop profile: `services/.runtime/config-desktopgemma.json`.

These records and profiles belong to this local installation; runtime files may be replaced by later runs.
