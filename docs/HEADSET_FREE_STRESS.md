# Headset-free rendering and AI stress check

The opt-in `--headset-free-stress` Unity diagnostic renders two independent eye-like views plus a desktop mirror. Each eye rotates through three HDR render textures with depth and requested 4× MSAA. Views pan slightly to exercise visibility. It uses the existing room, post-processing and characters.

This is a synthetic memory/rendering workload. It does not emulate an OpenXR headset, single-pass stereo, the Quest Link compositor/encoder, controller tracking, or the speed and memory behaviour of a different GPU.

`tools/test-headset-free-vram.py` starts a separate loopback conversation bridge using the already-running Gemma and BF16 Higgs services. It sends conversation prompts through the real Unity streaming/playback/emotion path, with the test player's volume muted without changing saved volume. It also transcribes two 25-second mono PCM16 samples on CPU. Test session logs stay under `services/.runtime/headset-free-stress-sessions`, separate from student sessions. The user's reference recording is read locally, not copied into the report.

Run with the configured bridge Python after building the Unity player:

```powershell
.tools/portable-env/Scripts/python.exe tools/test-headset-free-vram.py
.tools/portable-env/Scripts/python.exe tools/test-headset-free-vram.py --eye-size 2400 --turns 2 --output docs/generated/headset-free-stress-2400
.tools/portable-env/Scripts/python.exe tools/test-headset-free-vram.py --eye-size 2000 --turns 1 --output docs/generated/headset-free-stress-2000
```

The first command requests six conversation turns with two 3000×3000 views; the others are shorter resolution comparisons. The runner closes only the test player it started, retains the shared AI services, and saves raw NVIDIA VRAM samples, Unity frame intervals and turn results. Ordinary game launches do not create these extra cameras or buffers and do not change their graphics settings.

Reports include whole-device memory, so Windows and other running applications contribute to the total. Sampling is approximately every half-second and can miss brief peaks. Unity frame intervals under this synthetic workload are not headset frame-time measurements.

## Results, 28 September 2026

All runs used Gemma 4 12B QAT Q4, a 4096-token context, BF16 Higgs and CPU faster-whisper on the development RTX 5090. Other desktop applications remained open.

| Synthetic resolution per view | Spoken turns | Peak whole-device VRAM | Arithmetic margin below 24 GiB |
| --- | ---: | ---: | ---: |
| 3000×3000 | 6 | 24.32 GiB | **0.32 GiB over** |
| 2400×2400 | 2 | 22.93 GiB | 1.07 GiB |
| 2000×2000 | 1 | 22.22 GiB | 1.78 GiB |

Nine generated replies completed through Unity's real streaming audio/performance path. CPU STT recognized both 25-second samples at each resolution. No game crashes or sustained VRAM growth were observed. The six-turn run used roughly 24.26 GiB steadily; GPU usage returned to about 20.06 GiB after closing each test player. Median frame intervals were about 11.11 ms and p95 about 11.13–11.14 ms at the diagnostic's 90 FPS cap on the 5090; this is not a 4090 performance result.

The first high-resolution run's automatic STT attempt rejected the original reference recording because it was not PCM16. The fixture was corrected, then both STT checks were repeated successfully against that same isolated bridge while the high-resolution game was still running. The raw report retains its initial `passed: false` and records `stt_recovery` plus `recovered_checks_passed: true`; the two later runs include the corrected fixture and passed normally.

These results support keeping Gemma and BF16 speech while budgeting graphics conservatively. The heavy 3000×3000 synthetic configuration exceeds a nominal 24 GiB budget on this desktop; the lower settings leave some room. Because Quest Link is absent and this is a different GPU, neither the arithmetic margin nor the observed frame rate certifies the university 4090 setup. Actual stereo rendering can use different buffers and render passes, and the Link compositor/encoder needs additional resources.

Saved evidence:

- [Comparison](generated/headset-free-stress-comparison.json)
- [3000×3000 raw run](generated/headset-free-stress/report.json)
- [2400×2400 raw run](generated/headset-free-stress-2400/report.json)
- [2000×2000 raw run](generated/headset-free-stress-2000/report.json)
