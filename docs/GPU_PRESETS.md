# GPU presets

The university has three separate PCs, each with one RTX 4090 and 64 GB DDR5 RAM.
Their GPU memory is not pooled. The deployment setting is `hardware_preset` in
`services/config.local.json`; **PC Settings.cmd** exposes it without editing JSON.

| Setting | Selected dialogue file | GPU layers | Speech |
| --- | --- | --- | --- |
| Auto, 24 GB class device | IQ3_M | 32 | Existing BF16 voice |
| Auto, 32 GB+ class device | IQ4_XS | 48 | Existing BF16 voice |
| University / RTX 4090 (`rtx4090`) | IQ3_M | 32 | Unchanged |
| Original quality (`quality`) | IQ4_XS | 48 | Unchanged |

The original model remains available. Auto reads total memory from CUDA device 0:
less than 23 GiB is unsupported, 23 to below 30 GiB selects the 24 GB preset,
and 30 GiB or more selects original quality. Thresholds allow for driver-reported
capacity being slightly below the nominal card size. Automatic settings are
capacity-based, not a measurement of headset frame rate or a promise that other
GPU applications can remain open. Manual quality on a 24 GB card may still be
too heavy.

Only dialogue file selection and layer offload are managed by this setting.
Character prompts, emotion control, temperature, language, session logs, voice
reference and speech precision are preserved. STT remains on CPU. GPU layers are
fixed per preset; 4096-token context and the existing batch settings remain.
The CPU handles the other model layers, so reply latency can increase. An IQ3
quant may also affect language/character behavior; it needs colleague review.

The IQ3_M file is 12,789,303,424 bytes versus 15,705,860,224 for IQ4_XS. Both use
the same pinned upstream revision. `portable-manifest.json` records both hashes,
but setup chooses one dialogue entry before downloading or validating files.
It never requires both quants for one selected preset. Existing quants are kept
when switching; shared voice, tokenizer and Whisper files are reused.

## Installation and switching

For new PCs, use the full Windows release ZIP and run a Start launcher; Auto is
the default. For an existing installation, merge **pc-settings-update.zip** into
its root, close the game, run **PC Settings.cmd**, then choose **1 Auto**.
The small update omits the voice/game, which must already be present.

The settings menu stops only services recorded by this installation. Switching
downloads the selected quant if absent and saves configuration backups under
`services/.runtime/config-backups/`. The launcher records the loaded model path
and GPU layer count, and rejects reusing a model from an old/different preset.
If another installation owns the port, stop that installation first.

## Verification and limits

110 service/helper tests pass, including GPU thresholds, manual overrides,
download selection and preservation of voice/language preferences. The actual
PC Settings CMD menu was exercised in an extracted folder containing spaces.

The initial 40-layer IQ3_M trial passed built-player dialogue/speech/lip movement,
but total GPU use peaked at 22,654 MiB (22.1 GiB), leaving too little margin for
Quest Link. The shipping preset therefore uses 32 layers. All local memory and
latency checks use an RTX 5090 and include other GPU applications on that host;
they are not a 4090 or headset acceptance test.

The 32-layer preset then passed the full Qwen-to-BF16 built-player check, including
audible playback and lip movement. Peak total GPU memory was 21,299 MiB (20.8 GiB).
First playback took 67.224 seconds in that run, versus 49.760 seconds in the
40-layer trial. These runs generated different replies, so they are not a
controlled quantization/layer-count speed comparison. This is a memory-saving
preset, not an established low-latency solution. No further speech quantization
was applied.

A four-prompt regional-language screen returned valid emotion segments for all
four characters. Alex described anxiety, Ivan followed a cooking topic, Nikola
returned frustration, and Stefan rejected the false premise that he had burns
and lost his apartment. Dialogue-only requests took 26.54-45.46 seconds. Quality
limitations remain: Stefan's reply contained a grammatical error, and Nikola's
reply to dismissal was still quite accommodating. This small screen does not
establish parity with IQ4_XS or resolve the existing character-behavior concerns.
Auto was also exercised on the actual 32 GB host, and the launcher correctly
refused to reuse the still-running service from the different preset.

Before using all three PCs with students, check one university PC with Quest Link
active: confirm Auto resolves to `rtx4090`, talk through several turns, interrupt
speech and change characters. Confirm stable headset rendering, no memory errors
and acceptable response time. Review Montenegrin and emotional behavior with a
colleague. If this remains too slow or memory constrained, the next candidate is
a smaller-parameter dialogue model while preserving BF16 speech.
