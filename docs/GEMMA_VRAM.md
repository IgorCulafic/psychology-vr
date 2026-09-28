# Unity + Gemma GPU memory check — 28 September 2026

Measured on the development RTX 5090, with Gemma 4 12B QAT Q4 fully on GPU (4096 context), BF16 Higgs, CPU faster-whisper, and the Unity Windows player at 1600×1000. Speech was already warmed up by prior conversations. No Unreal process or active Quest Link rendering was included.

| Component | Approximate dedicated VRAM |
| --- | ---: |
| Gemma / llama.cpp, including its runtime buffers | 7.47 GiB |
| BF16 Higgs, including warmed-up runtime/cache | 10.18 GiB |
| Unity room, desktop | 0.47 GiB |
| Project subtotal | 18.13 GiB |
| Windows and other desktop applications, residual | 2.45 GiB |
| Whole device with Unity idle | 20.58 GiB |
| Whole device sampled maximum while generating a spoken reply | 20.59 GiB |

STT is configured with `stt_device: cpu`; Rhubarb lip alignment also runs on CPU. These do not require another GPU model allocation.

The whole-device readings come from NVIDIA memory-used samples approximately every half-second. Project process figures come from Windows dedicated GPU memory counters, identifying the Unity player, Gemma server and Higgs Python process. Unity's contribution is also consistent with the approximately 490 MiB increase when its room loaded. GPU counters and device totals are approximate and need not sum exactly.

The test generated three speech segments through the live bridge while Unity's room remained loaded; the game did not play that test audio. This is not a worst-case stress test. Headset eye buffers, Quest Link and varying conversation/speech lengths may require additional memory. Against a nominal 24 GiB budget, this desktop measurement leaves roughly 3.4 GiB; verify the university RTX 4090 machines with Quest Link before treating that as guaranteed headroom.

Raw samples, configuration and method notes: [measurement JSON](generated/gemma-unity-vram.json).

Follow-up: the [headset-free dual-view stress test](HEADSET_FREE_STRESS.md) exercises much larger rendering buffers alongside live conversation and CPU STT. Its graphics memory is substantially higher than this desktop figure; use that comparison when estimating headset headroom.
