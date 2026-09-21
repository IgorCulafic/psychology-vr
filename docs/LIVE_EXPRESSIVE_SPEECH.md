# Live expressive conversation

21 September 2026: after listening to the same anger line in BF16 and NF4, the user chose **16-bit BF16** for its stronger emotional delivery. Both the local configuration and expressive example now default to `higgs_quantization: "bf16"`. The full reference and temperature 0.70 are unchanged. Local Qwen offload returns to the previously tested 48-layer setting to make room for the larger voice model; full-pipeline latency can therefore increase by more than the roughly 1.7-second synthesis-only difference. Services were stopped at the time of this change; the next normal launch loads BF16.

Implementation started 20 September 2026 after the user confirmed Quest microphone input, Montenegrin recognition, facial previews and the recorded Higgs comparison. These observations do not establish acceptance of the new live pipeline.

## Start and stop

The local configuration now selects live Qwen dialogue, resident Higgs speech and multilingual Whisper on CPU. `tools/launch.ps1 -NoGame` starts all three workers; omit `-NoGame` to open the player. `tools/stop-services.ps1` stops registered project workers, including the speech worker. `-BridgeOnly` preserves loaded models and `-ModelOnly` preserves speech. After a bridge restart, use Settings → Reconnect in the player.

For a new machine, use `services/config.expressive.example.json` as a template for ignored `services/config.local.json`. Do not overwrite an existing personal configuration without preserving it. The old English/Kokoro setup remains in `config.live.example.json`. Never select English-only `small.en` with regional STT language codes.

The example's reference WAV and sibling JSON `{ "text": "exact reference transcript" }` are **private local prerequisites**, not included in Git. Supply a recording you are authorized to use at that path or change `higgs_reference`. Existing auditions use the full 25.45-second reference. Keep recordings, generated speech and transcripts in ignored directories.

## Pinned speech dependencies

The bridge uses `.venv` (Python 3.11). Higgs runs in `.tools/alternative-tts-venv` (Python 3.12) with the existing `experiments/tts/requirements-alternative-lock.txt`; the environments remain separate.

```powershell
uv venv --python 3.12 .tools/alternative-tts-venv
uv pip install --python .tools/alternative-tts-venv/Scripts/python.exe -r experiments/tts/requirements-alternative-lock.txt
./.tools/alternative-tts-venv/Scripts/hf.exe download multimodalart/higgs-audio-v3-tts-4b-transformers --revision 30f01593ee6a12efa586c92455afe4b76e45095d --local-dir .cache/higgs-transformers
./.tools/alternative-tts-venv/Scripts/hf.exe download bosonai/higgs-audio-v2-tokenizer --local-dir .cache/higgs-audio-v2-tokenizer
./.tools/alternative-tts-venv/Scripts/hf.exe download dropbox-dash/faster-whisper-large-v3-turbo --revision 0a363e9161cbc7ed1431c9597a8ceaf0c4f78fcf --local-dir .cache/whisper/large-v3-turbo
```

Higgs uses the previously auditioned community Transformers port, not SGLang. It loads only local files, keeps the model and encoded reference resident, and resets seed 42 for each request. Temperature 0.70, top-p 0.95 and top-k 50 preserve the preferred anger sampling settings; 0.60 remains an optional local setting. The selected voice uses BF16 weights/compute and the FP32 audio codec. The previous NF4 candidate used bitsandbytes 0.50.2 and was rejected by the user for weaker emotional delivery. Quantized modes remain optional experiments, requiring `services/requirements-higgs-quantized.txt`, and are not selected by default. The adapter explicitly restores and checks tied audio-head weights after loading.

The worker binds only to `127.0.0.1:8766`. `/synthesize` accepts one validated segment and returns mono PCM16 WAV. It rejects browser origins, arbitrary reference paths, user-supplied tags and concurrent synthesis requests. The bridge binds to port 8765. No external speech API is used.

## Response and performance contract

The [emotional performance check](EMOTIONAL_PERFORMANCE.md) now captures actual model replies and replays them through Unity's shared live playback path, including a separately labelled two-beat mechanical fixture. It checks tears, timed gestures, lip movement, menu pause/resume and cancellation.

`services/performance_contract.py` defines the shared direction fields. The LLM supplies text, emotion, intensity, one supported gesture, voice style, gaze and timing. Every beat starts its emotional transition before its optional reaction pause; audio then starts and the gesture fires at `gesture_at × audio duration`. This is segment timing, not word alignment. Lip timing still comes from analysis of the generated audio, never invented model timestamps.

| Direction | Allowed range / behavior |
|---|---|
| `gaze` | automatic, listener, down, away; face-covering/panic can override listener gaze |
| `transition_seconds` | 0.15–2; blends intensity, body targeting and facial expression |
| `pause_before_seconds` | 0–1.5; silent reaction before this beat |
| `gesture_at` | 0–0.85; fraction of audio duration |
| `gesture_duration_seconds` | 0.3–4; gesture also ends when the beat finishes |
| `hold_after_seconds` | 0–1.5; brief pause; final emotion persists into listening |

Older segments receive defaults. Nonfinite/invalid numeric directions fail validation; out-of-range finite values are clamped. Unity also bounds received timing. Menu pause freezes the gesture clock; explicit character preview remains interactive. Stop/reset cancels queued playback and suppresses late responses. No directions or reasoning are read aloud.

Alex's profile remains authoritative for biography. The prompt encourages one concise beat, gradual emotional changes, meaningful rather than constant gestures, and Montenegrin Latin-script ijekavian speech when `conversation_language` is `cnr`. Explicit factual-boundary examples discourage invented relatives/amnesia and distinguish the counsellor's family from Alex's; both targeted questions produced appropriate boundaries in a subsequent direct-model check, which does not prove general consistency. Up to four recent exchanges and the last emotional state are passed into the model; this is bounded conversation memory, not durable clinical history.

Higgs tags are produced exclusively by the trusted adapter. Supported body emotions map to documented Higgs emotions; for example angry→anger, crying→sadness, afraid→fear, happy→elation. There is no verified continuous emotion-strength parameter: intensity drives the face/body, while speech uses categorical delivery. No automatic shouting, pitch changes or synthetic sobbing are added. `hesitant` requests slower prosody and `numb` lower expressiveness; other styles principally rely on emotion and wording. This avoids claiming that every voice-style enum has an independent control.

Sources: [Higgs control tokens](https://huggingface.co/bosonai/higgs-tts-3-4b#control-tokens), [Whisper medium conversion](https://huggingface.co/Systran/faster-whisper-medium).

## Recognition and latency

**21 September update:** large-v3-turbo replaces medium in the expressive setup. A generic Montenegrin hint, independent-window decoding and Latin-script normalization are selected. See [recognition/conversation results](MONTENEGRIN_CONVERSATION.md) for the controlled comparison, short-clip tradeoff, prompt changes and remaining errors. The medium measurements below are historical.

Whisper has no Montenegrin-specific language token. The local trial uses `sr`, a multilingual model and transcription rather than translation. On the single user reference, normalized word error fell from 25.9% for small/beam 5 to 18.5% for medium/beam 5 against the prepared transcript. CPU times were 3.59 s and 9.32 s for 25.45 seconds of audio. This is a small diagnostic, not a population benchmark; spelling and pronunciation errors remain. Medium/beam 1 also changed script and introduced errors, so it was not selected.

The first live request took 38.35 s: 26.26 s dialogue and about 11.17 s synthesis for 5.24 s of audio, plus alignment/transport. With NF4 speech and full-GPU Qwen, three subsequent live turns took **10.86, 12.39 and 19.88 seconds**, excluding microphone recording/transcription and playback. Dialogue was 1.93–2.75 s, synthesis 7.78–16.26 s, and alignment 0.71–0.86 s. These different replies are an observed operating range, not a controlled same-text speed ratio. Responses still finish synthesis before playback; streaming and stopping neural inference mid-request remain follow-ups. The new `generation_ms`, `speech_ms`, `alignment_ms` and `total_ms` response fields expose the remaining bottleneck.

A controlled 58-character anger line took 9.07 s in BF16, 25.25 s in int8, and 7.41 s in NF4. Generated durations varied (4.08 s BF16 vs 3.84 s int8), so generation speed alone does not prove equal audio quality. The recognizer recovered the intended sentence from BF16 and NF4 with small spelling differences; this is a rough intelligibility check, not native accent/voice evaluation. Private samples are in `.runtime/live-angry*.wav`.

Qwen and Higgs compete with Unity and other applications for VRAM. `llm_gpu_layers` makes offload configurable; both the example and this host now use 48 with BF16 speech. The earlier NF4 test used 99 (all layers), with Higgs reporting about 3,539 MiB allocated, vs 5,030 MiB in int8. Total system VRAM use before launching the player in that NF4 test was about 26.2 GiB; other active applications contribute to that number. The intended 4090/24 GB target remains unverified. Do not blindly increase offload while the GPU is nearly full.

## Verification

Run `./.venv/Scripts/python.exe -m unittest discover -s services`. Tests cover direction bounds, backward compatibility, language prompting, speech-token isolation, history, HTTP limits, scenario changes and cancellation. A successful build or desktop smoke test does not establish natural voice identity, Montenegrin pronunciation or sustained headset frame rate; verify those with the next focused Quest session.
