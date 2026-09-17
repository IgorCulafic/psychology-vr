# Fish S2 Pro: installed and auditioned locally

Date: 15 September 2026. This is an isolated speech audition setup. The Unity game still uses its existing speech configuration.

## Serbian anger-intensity experiment

Serbian-only test: `generated/fish-local/serbian-anger/index.html`, served at `http://127.0.0.1:8793/serbian-anger/`.

Six prompts compare `[sr]` and `[serbian]`, each at normal delivery, `[angry]`, and `[angry] [shouting]` with exclamation marks. They use the same Serbian words, `[male voice]`, seed 42 and temperature 0.55, without an English reference. Increased anger is requested through performance cues and punctuation, not by boosting the saved waveform's volume. No native accent or perceived emotion rating is implied by successful generation.

```powershell
$env:PYTHONUTF8='1'
& .tools/fish-speech/.venv/Scripts/python.exe -u tools/audition_fish_local.py `
  --case-file docs/generated/fish-local/serbian-anger-cases.json `
  --output docs/generated/fish-local/serbian-anger `
  --no-reference --temperature 0.55 --top-p 0.7
```

## Bosnian language-tag experiment

Latest Bosnian-only test: `generated/fish-local/bosnian-tags/index.html`, served at `http://127.0.0.1:8793/bosnian-tags/`.

Four clips use the same Bosnian text: `[bs]` normal/angry, and `[bosnian]` normal/angry. Each also requests `[male voice]`. All were generated without a reference recording, removing the English reference from conditioning. These language labels are experimental inline text cues, not a supported TTS `language` API parameter. With no reference, voice identity is not guaranteed to remain fixed across prompts, even with seed 42.

Reproduce:

```powershell
$env:PYTHONUTF8='1'
& .tools/fish-speech/.venv/Scripts/python.exe -u tools/audition_fish_local.py `
  --case-file docs/generated/fish-local/bosnian-tag-cases.json `
  --output docs/generated/fish-local/bosnian-tags `
  --no-reference --temperature 0.55 --top-p 0.7
```

Multilingual Whisper Small was added at `.cache/whisper/small` for automatic checks. Its `language='bs'` option applies to transcription only; it does not set Fish's generation language. Transcriptions are saved with the audio and need to be distinguished from native pronunciation judgments.

## Clear male voice revision

The current audition set is `generated/fish-local/clear-male/index.html`, served at `http://127.0.0.1:8793/clear-male/`. It replaces the earlier breathy Fish-reference examples for review.

- Fresh synthetic male reference: Kokoro `bm_george`, `en-gb`, speed 0.93; reference text is neutral conversation. The recording and provenance are in `generated/fish-local/references/george-neutral.wav` and `.json`.
- Five newly generated Fish samples: neutral, sadness, anger, anxiety, and Croatian/Bosnian wording. Full paragraphs replace the short repeated sentence. Sobbing, crying, whisper and trembling cues were removed; emotional directions are single tags.
- Sampling temperature 0.55, top-p 0.7, seed 42. Reference identity and sampling settings are consistent across this set.
- All four English paragraphs matched their intended words in the local transcription check, after ignoring punctuation and case. This does not establish perceived voice quality or pronunciation in the regional-language sample.

Reproduce this set from the project root:

```powershell
$env:PYTHONUTF8='1'
& .tools/fish-speech/.venv/Scripts/python.exe -u tools/audition_fish_local.py `
  --case-file docs/generated/fish-local/clear-male-cases.json `
  --output docs/generated/fish-local/clear-male `
  --reference docs/generated/fish-local/references/george-neutral.wav `
  --temperature 0.55 --top-p 0.7
```

## Installation

- Official model: `fishaudio/s2-pro`, revision `1de9996b6be38b745688de084d87a5633f714e4e`.
- Weights, tokenizer and codec: `.cache/fish-s2-pro` (about 11 GB). All 12 downloaded files passed the Hugging Face checksum check. The optional `overview.png` was excluded; local download metadata explains the verifier's extra-file warning.
- Official source: `.tools/fish-speech`, commit `befe4001745417f8c42131739d862b8a6fdbd15a`.
- Isolated interpreter: `.tools/fish-speech/.venv/Scripts/python.exe`.
- Python 3.12.13, PyTorch 2.8.0+cu128, torchaudio 2.8.0+cu128. Complete environment in `generated/fish-local/environment.txt`.
- Native Windows inference, BF16 weights, compilation disabled. The harness uses the official model loader's `max_length=4096` option to bound context/cache memory for these short auditions; the downloaded checkpoint is unchanged.
- Audition code: `tools/audition_fish_local.py`. It loads locally, sets Hugging Face offline mode, and makes no speech API calls.

Sources: [official repository](https://github.com/fishaudio/fish-speech), [model](https://huggingface.co/fishaudio/s2-pro), [installation](https://speech.fish.audio/install/). Fish's license permits free research/noncommercial use. The official installation guide recommends Linux/WSL; native Windows without compilation worked for this audition.

## Results

14 WAV files generated successfully, all 44.1 kHz mono PCM16:

1. **Existing Alex/Kokoro synthetic reference:** neutral, sadness, anger, crying, fear, disgust; Serbian Latin sadness; Serbian Cyrillic anger; shared Croatian/Bosnian Ijekavian wording; experimental Montenegrin wording.
2. **Earlier Fish-generated synthetic reference:** sadness, anger, crying, and the same Ijekavian line. This provides a reference-voice comparison without cloning a real person. The earlier reference was generated on the public demo; all 14 new samples were generated on this PC.

Listen using `generated/fish-local/index.html` and `generated/fish-local/fish-reference/index.html`. Both pages link to the other set and include their reference recording. A loopback-only preview is available at `http://127.0.0.1:8793/` while its Python preview server is running. Preview server PID is recorded in `.cache/fish-preview.pid`; it serves audio files and does not keep Fish loaded on the GPU.

The same English sentence and seed were used across emotions. All **nine English outputs** passed a local Whisper transcription check for the intended words after punctuation/case normalization. No emotion-tag words appeared in those transcripts. This verifies basic intelligibility, not the quality or strength of an emotion. The Balkan-language clips have not been independently transcribed or rated by a native listener. A shared Ijekavian sentence is not proof of separate regional accents; Montenegrin remains experimental.

### Actual measurements

Hardware detected: **RTX 5090, 32 GB**, driver 610.88. These are not 4090 measurements. The dialogue LLM was not loaded alongside Fish for these measurements.

| Measurement | Existing Alex reference, 10 clips | Earlier Fish reference, 4 clips |
| --- | ---: | ---: |
| Model load plus reference encoding | 41.77 s | 41.25 s |
| Total generated audio | 39.15 s | 20.11 s |
| Total generation time, excluding loading | 85.83 s | 44.87 s |
| Generation time / audio duration | 2.19× | 2.23× |
| Peak PyTorch allocated GPU memory | 13,622.5 MiB | 13,646.2 MiB |
| Peak PyTorch reserved GPU memory | 13,918 MiB | 14,086 MiB |

Whole-device usage was approximately 18–19 GB including the desktop and other applications; it returned to about 4 GB after inference exited. These timings measure complete-file generation, including codec decoding, not streaming time-to-first-audio. First samples include cache/warm-up costs. Per-clip measurements, source revisions, seeds, reference hashes and sampling settings are in each page's adjacent `results.json`.

This Windows baseline is **slower than real time**, so it is not yet suitable for responsive live conversation. The next performance experiment would be a supported accelerated Linux/WSL backend, followed by a joint VR + dialogue + TTS memory/latency test. Do not extrapolate the 5090 results directly to a 4090 or claim enough memory remains for the large dialogue model.

## Re-run

From `D:\AI\Psychology_VR`:

```powershell
.\tools\run-fish-auditions.ps1
# Or select a smaller set:
.\tools\run-fish-auditions.ps1 -Cases 'en-sad,en-angry,en-crying'
```

These commands regenerate the selected files and the results manifest in `docs/generated/fish-local`. They do not launch the game or change its provider.

To reproduce the second voice-reference comparison:

```powershell
$env:PYTHONUTF8='1'
& .tools/fish-speech/.venv/Scripts/python.exe -u tools/audition_fish_local.py `
  --cases en-sad,en-angry,en-crying,hr-bs-sad `
  --output docs/generated/fish-local/fish-reference `
  --reference docs/generated/speech-research/fish-en-sad.wav `
  --reference-text 'I thought I was safe here. I still wake up when I hear a loud noise.'
```

To serve the listening pages again, without loading the model:

```powershell
& .venv/Scripts/python.exe -m http.server 8793 --bind 127.0.0.1 --directory docs/generated/fish-local
```

Environment recreation uses the official repository at the recorded commit and `uv sync --python 3.12 --extra cu128 --no-dev` from its folder. The official `uv.lock` and saved environment list record the installed dependencies. Use `hf download fishaudio/s2-pro --revision 1de9996b6be38b745688de084d87a5633f714e4e --local-dir .cache/fish-s2-pro --exclude overview.png` from the project root if weights need downloading again.
