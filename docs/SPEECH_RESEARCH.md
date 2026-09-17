# Expressive speech research — 15 September 2026

16 September follow-up: [completed local OmniVoice / Higgs / Fish comparison](ALTERNATIVE_TTS_AUDITIONS.md), including playable pronunciation and emotion samples. Fish remains usable per user feedback; accent quality needs improvement. The earlier recommendations below are research history, not a listening-test winner.

Priority: audible emotion first; Serbian, Croatian, Bosnian or Montenegrin second. Target deployment is the existing Unity PCVR game alongside a local dialogue model on an RTX 4090 with 24 GB VRAM.

Local follow-up: Fish S2 Pro has since been installed and tested on the detected RTX 5090, producing 14 local auditions. See [local setup and measurements](FISH_LOCAL_SETUP.md). The public-demo results below describe the earlier research stage.

## Recommendation

Audition **Fish Audio S2 Pro** first for a local voice. Compare **Higgs TTS 3** for its explicit emotion controls. Use **Gemini Flash TTS** as the first free-tier API comparison, with **Eleven v3** as another candidate covering Bosnian too. Replace the English-only STT checkpoint with multilingual **Whisper large-v3-turbo**, then compare large-v3 on recordings from the intended speakers.

These are candidates based on documented capabilities, not a claim that one has won a listening comparison. At the initial research stage, only one English Fish sample had been generated. The linked local follow-up adds GPU measurements and language samples; native-listener assessment is still pending.

## Local TTS shortlist

| Model | Emotional performance controls | Requested languages explicitly listed | Fit for this project |
| --- | --- | --- | --- |
| [Fish Audio S2 Pro](https://huggingface.co/fishaudio/s2-pro) | Inline natural-language tags for sadness, anger, whispering, shouting, sighing and other delivery instructions. | Serbian, Croatian, Bosnian. These sit outside its main language tiers. | First local audition candidate. Free research/noncommercial weights under Fish's license. Approximately 4B slow decoder plus 400M fast decoder; runtime and codec add memory. |
| [Higgs TTS 3 4B](https://huggingface.co/bosonai/higgs-tts-3-4b) | Explicit sadness, anger, fear, disgust, shame, helplessness, relief, etc.; separate crying, sniff and sigh sounds, plus pace and whisper controls. | Serbian, Croatian, Bosnian. | Particularly close to our animation vocabulary. Free research evaluation; its model card separately restricts product/application embedding and hosted services. Do not assume the creator-content grant covers shipping the game. |
| [IndexTTS 2.5](https://huggingface.co/IndexTeam/IndexTTS-2.5) | Emotion reference, text direction and an eight-component emotion vector; speed control. | None of the four. English, Chinese, Japanese, Spanish and Arabic are listed. | Strong English emotion benchmark, but not our multilingual solution. Custom model license. |
| [Chatterbox](https://github.com/resemble-ai/chatterbox) | Original model has emotion exaggeration; Turbo adds paralinguistic tags. These are different variants, not interchangeable features. | None of the four in the documented multilingual release. | Smaller English fallback with MIT licensing. Exaggeration alone does not give independent control of every emotion. |
| [Qwen3-TTS 1.7B CustomVoice](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice) | Natural-language directions for emotional delivery and speaking style. | None of the four among its ten supported languages. | Another smaller English comparison; Apache 2.0. Do not choose it on the assumption that Qwen's text-language coverage also applies to its TTS. |

Higgs token examples: `<|emotion:fear|>`, `<|emotion:helplessness|>`, `<|style:whispering|>`. Its sound-effect tokens have their own prompting rules, including accompanying vocalization text; blindly substituting our animation tags would be insufficient. [Higgs prompting guide](https://huggingface.co/bosonai/higgs-tts-3-4b/blob/main/PROMPTING.md)

Montenegrin is not explicitly listed by either shortlisted local TTS model. Ijekavian wording and regional accent prompts are experiments, not verified Montenegrin support. [AlfaNum](https://www.alfanum.co.rs/en/an-sintetizator/) explicitly offers Montenegrin as well as Serbian and Croatian, but I did not establish a free API or comparable emotion controls; it is a pronunciation benchmark rather than the leading expressive option.

## Local STT

The project currently selects `faster-whisper` with `.cache/whisper/small.en` on CPU. That checkpoint is English-only. Speech recognition transcribes the student's words; the dialogue model must also handle the resulting language. STT does not itself produce an emotional character voice.

1. **Whisper large-v3-turbo through faster-whisper:** first multilingual baseline, balancing speed and accuracy. Use transcription rather than translation. Choose `sr`, `hr` or `bs` explicitly for a selected scenario and compare with automatic detection on longer samples. The [Whisper language table](https://github.com/openai/whisper/blob/main/whisper/tokenizer.py) contains all three, but not a separate Montenegrin code.
2. **Whisper large-v3:** comparison for difficult accents, quiet speech and distressed delivery. Do not assume turbo and full large-v3 have identical accuracy. [Turbo model card](https://huggingface.co/openai/whisper-large-v3-turbo), [faster-whisper](https://github.com/SYSTRAN/faster-whisper).
3. **Meta Omnilingual ASR v2:** reserve alternative if Whisper struggles. Its [published language list](https://github.com/facebookresearch/omnilingual-asr/blob/main/src/omnilingual_asr/models/wav2vec2_llama/lang_ids.py) includes `bos_Latn`, `hrv_Latn` and `srp_Cyrl`, without `cnr`. It requires a different runtime/integration. [Repository and model families](https://github.com/facebookresearch/omnilingual-asr).

For Montenegrin, compare the existing supported recognizer language settings against human transcripts. Check names, negation, Ijekavian forms, script, and quiet or interrupted speech. Do not treat a successful synthetic-speech round trip as evidence of recognition accuracy for real students.

## Free API possibilities

| Service | Useful capability | Free offering and limits | Language fit |
| --- | --- | --- | --- |
| **Gemini 3.1 Flash TTS Preview** | Natural-language performance direction; crying, trembling, panicked, sighing and whisper tags. | Official pricing lists free input and output on the standard free tier. Requires an eligible account/key; actual quotas are account-dependent. | Serbian and Croatian explicitly listed; Bosnian and Montenegrin not listed. |
| **Eleven v3** | Expressive TTS and audio tags; separate conversational variant also exists. | API pricing currently lists 10,000 v3 characters, roughly 10 minutes, included in its Free / Pay as you go column. Check the account's remaining allowance before tests; additional use is not necessarily free. | Serbian, Croatian and Bosnian explicitly listed for v3. Montenegrin not listed. |
| **Groq Whisper** | Hosted large-v3 / large-v3-turbo STT, saving local GPU memory. | Published free-plan table: 20 requests/minute, 2,000/day, 7,200 audio seconds/hour and 28,800/day; organization limits may differ. Key required. | Whisper multilingual recognition. Groq's listed Orpheus TTS options are English/Arabic, so they do not solve Balkan-language speech output. |

Sources: [Gemini speech guide](https://ai.google.dev/gemini-api/docs/speech-generation), [Gemini pricing](https://ai.google.dev/gemini-api/docs/pricing), [ElevenLabs models](https://elevenlabs.io/docs/overview/models), [ElevenLabs API pricing](https://elevenlabs.io/pricing/api), [Groq STT](https://console.groq.com/docs/speech-to-text), [Groq limits](https://console.groq.com/docs/rate-limits).

Google's pricing page marks free-tier content as usable for product improvement. The auditions here use fictional lines, not student recordings. Public Hugging Face demos are useful for auditions but have shared queues/quotas and are not dependable game backends. No API keys for these providers were present in the checked environment; no authenticated provider test was performed.

## What was actually tried

- **Fish S2 Pro public community demo:** generated `generated/speech-research/fish-en-sad.wav`, 6.13 seconds, 44.1 kHz. Input: `[sad] I thought I was safe here. I still wake up when I hear a loud noise.` No real person's reference voice was supplied.
- The existing local Whisper model recovered all spoken words, apart from punctuation differences. This is an intelligibility sanity check, not a rating of sadness or naturalness. Listen to the sample before deciding.
- The next Fish request, for anger, was rejected by the demo's free ZeroGPU quota: 270 seconds requested versus 260 remaining. The script stopped; crying and Balkan-language requests were not submitted afterward.
- **Higgs community Transformers-port demo:** an English sadness request returned `RuntimeError`. The script stopped before its Serbian request. This is a demo/runtime failure, not evidence that Higgs cannot speak the language or emotion.
- No paid API requests, model-weight downloads, or Unity/service configuration changes were made.

Artifacts: `generated/speech-research/fish-first-result.json`, `fish-en-sad-check.json`, `fish-audition-results.json`, `higgs-audition-results.json`, and endpoint schemas. The reusable `tools/audition_speech_demos.py` records results and stops on failure, with no automatic retries. The isolated client environment is `.cache/speech-research/venv`.

## Next evaluation and integration

Use one consistent synthetic or consented male reference voice per model and the same sentences across neutral, sadness, crying, anger, fear, disgust and relief. Score emotion clarity, naturalness, identity stability, pronunciation, and whether tags leak into speech. Use separate native-speaker recordings to score STT. Add both Serbian scripts and appropriate regional wording; the prepared Ijekavian sentence alone cannot distinguish Croatian, Bosnian and Montenegrin pronunciation.

On the target PC, measure first-audio delay, sustained generation speed, GPU memory and VR frame time while the actual dialogue model runs. Roughly 4–5B BF16 speech weights alone suggest about 8–10 GB before runtime overhead; this is an estimate, not a measured requirement. If the dialogue model already occupies around 16 GB, it leaves insufficient headroom for those full-precision weights plus Unity on a 24 GB card. Evaluate supported quantization/offloading or hosted TTS before promising simultaneous real-time operation. The Fish card's H200 latency is not a 4090 benchmark.

Keep the character's emotion/intensity/gesture representation provider-independent. The TTS adapter should render supported vocal directions, while clean text goes to subtitles and the same emotional state drives facial/body motion. Distinguish silent crying animation, sobbing sounds and speech through tears. Cache nonverbal sounds where useful, preserve interruptibility, and verify lip-sync timing against generated audio.
