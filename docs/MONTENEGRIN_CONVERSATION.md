# Montenegrin recognition and conversation

21 September 2026. The expressive configuration selects **Whisper large-v3-turbo**, CPU int8, eight threads, `sr`, VAD and the default beam size of five. Whisper has no Montenegrin token: `sr` is a regional approximation. The bridge also accepts `cnr`/`me` configuration aliases and maps them to `sr`.

The selected hint is `Razgovor na crnogorskom jeziku, latinicom.` No expected transcript or character biography is passed to the recognizer. `stt_condition_on_previous_text: false` disables conditioning on prior decoded windows within a recording; it does not change dialogue memory. `stt_output_script: "latin"` transliterates Serbian Cyrillic, preserving wording, negation, numbers and č/ć. It does **not** repair words or convert ekavian into ijekavian. Configurations without these options retain previous behavior.

## Setup

Use the bridge environment from the README and the HF CLI from [live speech setup](LIVE_EXPRESSIVE_SPEECH.md). Download the complete conversion, including tokenizer/vocabulary files:

```powershell
./.tools/alternative-tts-venv/Scripts/hf.exe download dropbox-dash/faster-whisper-large-v3-turbo --revision 0a363e9161cbc7ed1431c9597a8ceaf0c4f78fcf --local-dir .cache/whisper/large-v3-turbo
```

Model source: [CTranslate2 conversion](https://huggingface.co/dropbox-dash/faster-whisper-large-v3-turbo); runtime: [faster-whisper](https://github.com/SYSTRAN/faster-whisper). Weights are already downloaded on this machine and remain outside Git.

Both the expressive example and this machine's ignored local configuration select the new recognizer. Higgs remains **BF16**, temperature 0.70, full reference; live Qwen offload remains 48 layers. Recognition stays on CPU. The existing Unity build supports these backend changes. Restart the bridge after code/config/profile changes; normal `tools/launch.ps1` loads the new setup. Settings → Reconnect reconnects an open player.

## Measurements

One real user recording (25.45 seconds) was compared with its prepared script. A 6.5-second crop of that recording is **not an independent sample**; its cut endpoint may affect the final word. Word error rate normalizes punctuation, case and Cyrillic/Latin script, retaining diacritics and regional word forms. The reference was previously prepared using the script and Whisper-assisted confirmation, not blinded human annotation.

Runs used CPU int8, eight threads, warm models and sequential variants. Each setting was measured once. Qwen was resident for separate dialogue tests; this was not a full VR workload benchmark.

| Setting | Full WER | Full processing | Crop WER | Crop processing |
|---|---:|---:|---:|---:|
| Previous medium / beam 5 | 18.5% | 8.05 s | 14.3% | 3.46 s |
| Turbo / beam 5, default decoding | 5.6% | 5.76 s | 14.3% | 4.31 s |
| **Turbo / beam 5, hint, independent windows** | **5.6%** | **5.59 s** | **7.1%** | **4.42 s** |
| Turbo / beam 1, hint, independent windows | 7.4% | 4.85 s | 14.3% | 4.27 s |

The selected setting improved this accuracy check but was slower on the crop. Both models returned empty text for three seconds of digital silence with VAD; this does not establish room-noise robustness. Word endings and regional forms still sometimes fail.

An HTTP smoke check passed real `/transcribe` → `/session` → `/turn` with the selected settings and local Qwen, plus an empty silence transcript. Cold transcription took 7.97 seconds including loading. TTS was disabled; this is not a new voice/headset latency measurement.

## Conversational behavior

The prompt selects authored Montenegrin facts, removes the opening from the ongoing reply template, and requests short direct answers, clarification of unclear speech, attention to negation/corrections, and fewer stock phrases or metaphors. Other characters retain their own facts and identity. Emotion/animation fields remain validated English enums; only dialogue is spoken.

Ten fixed prompts were compared before/after with seed 42: a six-turn sequence covering concern, pain, pacing, grounding, dismissiveness and apology, plus family, pronouns and unclear questions. Final responses passed the performance contract. Garbled speech changed from invented agreement to asking for repetition; an unnamed-person question changed from an invented neighbour to declining private details.

Six extra prompts exposed invented children/ages and a new symptom. Explicit unauthored-detail guidance fixed the children/ages question on recheck, but another answer still invented chest tightness. Some awkward wording and ekavian forms remain. **Prompt improvements do not guarantee biography consistency or native phrasing.** Cases became development cases after inspection, not an independent benchmark.

Dialogue tests ran Qwen fully on GPU with Higgs stopped. Their 2–3-second generation times are not the live BF16 pipeline's latency. Memory remains four recent exchanges; no persistent clinical history was added.

## Repeat and extend

```powershell
$env:PYTHONIOENCODING='utf-8'
./.venv/Scripts/python.exe -m unittest discover -s services
./.venv/Scripts/python.exe tools/evaluate_montenegrin.py --stt --reference path/to/recording.wav --transcript path/to/human-transcript.txt --output services/.runtime/stt-check.json
./.venv/Scripts/python.exe tools/evaluate_montenegrin.py --dialogue --output services/.runtime/dialogue-check.json
```

STT comparison requires medium and turbo downloaded; dialogue requires Qwen on port 8087. Keep recordings/transcripts in ignored folders. A nonprivate summary is in `docs/generated/montenegrin-validation.json`.

Next Quest check: new ordinary questions, quiet speech, names, negation (“Ne morate da ustanete”), corrections, unclear questions and interruptions. Assess recognized words separately from replies. Collect fresh recordings with human transcripts before tuning; native listening remains necessary for phrasing and TTS pronunciation.
