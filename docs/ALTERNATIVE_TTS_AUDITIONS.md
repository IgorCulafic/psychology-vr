# Local voice comparison — 16 September 2026

Fish remains a usable candidate according to the user's listening assessment, with accent and word-pronunciation problems. This comparison adds two local alternatives; no game speech provider was changed.

Listening page: http://127.0.0.1:8793/alternatives/index.html

## User feedback and voice consistency follow-up

The user preferred OmniVoice overall but reported a different speaker starting at “Toliko toga...” in its Serbian clip. Higgs had strong emotions, but its angry voice sounded like a different person from the reference. These are native-listener findings; automatic transcripts had not detected those identity issues.

Follow-up listening page: http://127.0.0.1:8793/voice-consistency/index.html

Three new OmniVoice variants preserve the text, Serbian setting, reference and seed: guidance 3 instead of 2; 64 decoding steps instead of 32; and separate per-sentence synthesis using the same reference and seed for each sentence. The sentence variant adds 120 ms between outputs, which can affect conversational flow. Guidance is a general conditioning parameter, not a guaranteed speaker-identity lock.

Higgs now has a neutral/angry pair conditioned on the complete 25-second reference rather than the earlier 6.5-second excerpt. An additional temperature-0.45 anger test generated 24.84 seconds, while Whisper recovered only the first sentence; it is retained for inspection but excluded from the main comparison. No variant is claimed to fix identity drift yet.

Reproduce using `tools/audition_voice_consistency.py omnivoice`, then `tools/audition_voice_consistency.py higgs`, then `tools/build_voice_consistency_report.py` in `.tools/alternative-tts-venv/Scripts/python.exe`. All previous samples remain unchanged. No Unity or live speech provider changes were made.

Further user feedback: the 64-step OmniVoice setting appears to cause the speaker change. Do not promote it as a fix. Full-reference Higgs anger was closer to the source speaker, but still needed improvement; the user valued Higgs's emotions highly. Higgs is therefore the leading candidate for the emotion-driven character, pending voice consistency assessment.

OmniVoice's documented voice-design attributes include whispering but not named anger/sadness/happiness controls comparable to Higgs's emotion tokens. It also supports nonverbal cues such as laughter and sighs and can follow reference style. This is a difference in documented control capabilities, not a claim that OmniVoice can never sound emotional.

Two additional Higgs samples retain the full reference: temperature 0.60 / top-p 0.95, and temperature 0.70 / top-p 0.85, against the earlier 0.70 / 0.95 baseline. Generation command: `tools/audition_voice_consistency.py higgs --higgs-refine`. Listening page: http://127.0.0.1:8793/higgs-refinement/index.html . Both complete passages were broadly recovered by ASR, with some word differences; voice similarity and emotional quality remain for user assessment. The local port exposes no dedicated reference-strength slider, and these sampling changes do not guarantee stronger speaker similarity.

Latest listening decision: the user reports that adjustment A (temperature 0.60 / top-p 0.95) is closest to the source voice, but less angry. The previous full-reference anger (temperature 0.70 / top-p 0.95, top-k 50, seed 42) remains preferred overall. Keep that full-reference baseline as the leading anger audition; do not promote A or B as a better overall result. This is an audition selection, not a change to the game's live speech provider.

## Completed samples

- **OmniVoice:** the short computer sentence, the original neutral passage with explicit `sr`, `hr`, and `bs` language settings, and the pronunciation passage in Serbian. Official Python runtime, 32 diffusion steps. Discrete anger/sadness controls were not tested or assumed to work with voice cloning.
- **Higgs TTS 3:** short, neutral and pronunciation passages, plus anger, sadness and happiness using its documented emotion tokens. Runs locally through the community Transformers port rather than the official SGLang server.
- **Fish S2 Pro:** fresh short, neutral and pronunciation samples using our current sampling settings, with plain text and no experimental language cue.

Every model received the same 6.5-second excerpt from `clone_test_1.wav`, containing the first complete passage, and the same transcript. The original recording is preserved. The crop ends at 6.5 seconds, after the word-timestamp estimate for “kafu” at 6.32 seconds and before “Napolju” at 6.7 seconds. This shorter reference follows OmniVoice's reference-duration guidance. All use seed 42; generation settings are model-specific.

The comparison reels resample to 24 kHz and insert one-second pauses. Individual WAVs retain their original sample rates. No pitch or speed alteration is applied to the saved comparison audio.

## Measured neutral-passage performance

RTX 5090, native Windows, one model at a time. Generation excludes model loading and is not first-audio latency. Memory figures are peak PyTorch allocated memory, not total GPU use.

| Model/runtime | Audio duration | Generation | Peak allocated memory |
| --- | ---: | ---: | ---: |
| Fish local harness | 8.41 s | 17.09 s | 13,782.5 MiB |
| OmniVoice official Python | 7.08 s | 1.15 s | 2,077.4 MiB |
| Higgs Transformers port | 7.60 s | 8.84 s | 8,736.8 MiB |

These are single audition measurements, without the dialogue LLM or VR benchmark running. Do not generalize them into simultaneous game performance guarantees.

## Verification and limitations

All 14 files were checked for nonempty, finite mono audio and duration consistency. Reference hashes match across the three runs. Local Whisper Small transcripts are saved for OmniVoice and Higgs as broad intelligibility checks only. They do not establish native accent, č/ć distinctions, correct vowel endings, or emotional quality. Some transcription differences remain. Native listening assessment is pending.

Gemini was not called: neither `GEMINI_API_KEY` nor `GOOGLE_API_KEY` is configured. No recording was uploaded to a hosted TTS service. ElevenLabs remains excluded per the user's earlier preference.

## Reproduce

The isolated environment is `.tools/alternative-tts-venv`, using CUDA PyTorch 2.8.0 and Transformers 5.17.0. The complete installed package snapshot is `.cache/alternative-tts/environment.txt`.

```powershell
& .tools/alternative-tts-venv/Scripts/python.exe -u tools/audition_alternative_tts.py omnivoice
& .tools/alternative-tts-venv/Scripts/python.exe -u tools/audition_alternative_tts.py higgs
& .tools/fish-speech/.venv/Scripts/python.exe -u tools/audition_fish_local.py --case-file docs/generated/fish-local/alternatives/fish-cases.json --output docs/generated/fish-local/alternatives/fish --reference docs/generated/fish-local/references/clone-test-1-short.wav --temperature 0.55 --top-p 0.7
& .tools/alternative-tts-venv/Scripts/python.exe tools/build_tts_comparison.py
```

Weights and source:

- [OmniVoice](https://github.com/k2-fsa/OmniVoice): source commit `08be0b4ccbac3e13e374e86fbfead4b4cac343e2`; model `k2-fsa/OmniVoice` revision `c5fdb5ccb189668d56333f77ba2629f4cd7535f4` in `.cache/omnivoice`.
- [Higgs official model and prompting documentation](https://huggingface.co/bosonai/higgs-tts-3-4b); [Transformers port](https://huggingface.co/multimodalart/higgs-audio-v3-tts-4b-transformers) revision `30f01593ee6a12efa586c92455afe4b76e45095d` in `.cache/higgs-transformers`, with `bosonai/higgs-audio-v2-tokenizer` in `.cache/higgs-audio-v2-tokenizer`. The port's Python files were inspected before execution; runtime loading uses local paths in offline mode.

Per-run texts, settings, timing, memory and reference hashes are saved in each model's `results.json` under `docs/generated/fish-local/alternatives`.
