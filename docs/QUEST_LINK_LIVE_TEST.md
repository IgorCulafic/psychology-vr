# Quest Link live check — 2026-09-28

Status: **headset freeze reported; not a successful VR stability test**. The desktop game remained responsive. No model or graphics settings were changed to address this incident.

Hardware: RTX 5090 (32 GB), Meta Quest 3. Software: Unity Windows player, Gemma 4 12B QAT Q4, BF16 Higgs speech, CPU Whisper STT. This is not a measurement on the university RTX 4090.

Unity's OpenXR session was focused from 21:58:42.328 to 21:59:51.331 local time (UTC+2), using single-pass instanced rendering and two 1824 × 1968 submitted eye buffers. In that interval, 64 whole-GPU samples ranged from 22,787 to **22,939 MiB (22.40 GiB)**, including 16 samples during speech generation. One reply completed, with first playback logged at 7,567 ms. OpenXR focus and desktop playback do not prove successful headset presentation.

Meta's 21:59:06 aggregate statistics identify a **USB2** transport, 72 Hz reported rate and 100 Mbps bitrate. That window includes time before the game became focused, so its dropped-frame counters are not a game-specific benchmark.

At 21:59:51.212 the Meta runtime reported proximity off / headset unmounted; USB channel discovery then returned no device. Unity's session transitioned to STOPPING and IDLE at 21:59:51.331. Meta subsequently logged `ovrError_XRStreamingUSBIssue`. This sequence does not establish the original freeze cause: taking off or disconnecting the headset after a freeze could account for it. The user subsequently attributed the freeze to an NVIDIA driver issue; that diagnosis has not been independently verified by these logs.

The sampled memory peak leaves approximately 9.44 GiB of reported capacity on this 5090. There was no observed memory-exhaustion error. A nominal 24 GiB card would have only about 1.60 GiB remaining at the same allocation; its actual runtime overhead and performance still need measurement.

Next diagnostic: re-establish Quest Link, verify that the Link environment itself updates with head movement, then retry the game. Inspect the USB connection if it freezes or disconnects again. Keep Gemma and BF16 speech unchanged until the failure is isolated.

Raw measurements and interval annotations: [quest-link-live-vram.json](generated/quest-link-live-vram.json). Samples before focus (including an initial launch that could not access the Meta runtime) and after the session stopped are excluded from the figures above. Full private runtime logs remain under `services/.runtime` and the local Meta log directory.
