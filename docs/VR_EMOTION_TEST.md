# Quest emotion and recorded-speech audition

The recorded test below is retained for comparisons. The active development path is now [live expressive speech](LIVE_EXPRESSIVE_SPEECH.md), including multilingual recognition and model-directed performance; it requires different services and a fresh player connection.

20 September 2026: the user tested facial expressions in Quest 3 and reported that they work well. Some expressions remain too similar; differentiation is deferred. This feedback does not establish expressive TTS quality, lip sync or headset performance across all states.

## Visual test

Use B → Settings → Character preview. Compare Neutral, Angry, Sad, Crying and Afraid around 80% intensity. Observe hands, face readability, skin/tears, clipping and transitions from the usual seated position. The existing live service can remain running during visual previews.

## Recorded Higgs speech comparison

`services/emotion_audition.py` uses the normal Unity service protocol to replay three private local clips with the matching body/face cues and phonetic Rhubarb lip sync:

1. **neutral**: full-reference neutral, temperature 0.70.
2. **angry**: preferred full-reference anger, temperature 0.70 / top-p 0.95.
3. **closer**: full-reference anger at temperature 0.60 / top-p 0.95; previously judged closer to the source speaker but less angry.

All use the same words, full reference, top-k 50 and seed 42. Both anger clips use identical body/face intensity (80%). `voice_style` distinguishes the saved variants in the harness; it does not modify their sound. There is no pitch, speed or loudness processing. These clips speak the existing regional-language passage; input recognition is configured separately.

The manifest is `experiments/tts/vr-audition.json`. Audio is excluded from Git; recreate it using the prior local audition workflow before running on a new machine. Alignment uses Rhubarb's phonetic recognizer and should be judged visually, not assumed to be linguistically exact.

Validate all audio and prepare mouth timings without changing the running service:

```powershell
./.venv/Scripts/python.exe services/emotion_audition.py --check
```

To switch, pause the game with B and stop only the live bridge with `./tools/stop-services.ps1 -BridgeOnly`. Run this in a terminal:

```powershell
./.venv/Scripts/python.exe services/emotion_audition.py
```

In the updated game, use Settings → Reconnect, then Session → **Neutral**, **Angry**, **Milder anger**, or **Compare all**. Select with the right trigger. These buttons close the menu and start the chosen clip directly, without depending on microphone recognition. Compare all plays all three in that order. Wait for playback to finish before another selection; Stop reply interrupts.

Voice commands remain available: close the menu, hold A and say **neutral**, **angry**, **closer**, or **compare**, then release A. The in-room status shows recording state and whether a microphone signal is present. Silent, too-short and failed recordings get explicit feedback. Recording blocked by playback, menus or connection state is logged as `MIC_BLOCKED`; captures log duration/peak/RMS (not raw audio). The private audition service log includes recognized command text and waveform peak to diagnose recognition separately from controller input. Do not publish these local logs.

Unknown commands produce an audition-mode instruction, not a fabricated conversation. B pauses/resumes. Reconnecting starts a fresh conversation session. The previous player hid errors outside the menu; therefore no visible reaction did not establish a recognizer failure. Physical microphone/controller behavior still needs to be checked using the new visible feedback.

This is prerecorded playback, not live Higgs inference or a synthesis-latency benchmark. The LLM stays out of the audition request path. At the start of this test the GPU was already using about 24 GB of its 32 GB, so the harness avoids loading another speech model alongside VR and Qwen.

To return to normal conversation, stop the audition process (Ctrl+C if running in a terminal, or `./tools/stop-services.ps1 -BridgeOnly` for a registered background process), run `./tools/launch.ps1 -NoGame`, and choose Settings → Reconnect. The audition overrides dialogue/TTS providers in memory; STT uses the saved configuration. Processes launched by the test operator should be recorded in the existing bridge PID file if using the stop-services helper.

## Montenegrin input trial

The user confirmed that recording feedback works and approved those additions. English recognition sometimes missed "compare". Previously STT loaded `small.en` and hardcoded English; it now reads `stt_language` (defaults to `en`; `auto` enables language detection) and explicitly transcribes rather than translates.

For this local trial, `services/config.local.json` uses `stt_model: ".cache/whisper/small"`, `stt_language: "sr"`, and CPU int8. The previous config is backed up privately in `services/.runtime/config-before-multilingual.json`. The installed Whisper tokenizer supports `sr`, `hr`, and `bs`, but has no separate Montenegrin code. `sr` is a recognition workaround, not a claim that the model accurately handles every Montenegrin accent. English-only models are rejected when a different language is requested.

An unprompted check of the user's 25.45-second local reference using all three codes preserved much of the passage but made several word/spelling errors. The outputs were very similar; no accuracy advantage for one code was established. This was one recording, not a recognition benchmark. Recordings/transcripts stay local and ignored by Git.

After restarting the bridge, choose Settings → Reconnect, close the menu, hold A, speak, then release A. Trial commands: **"Uporedi"** (all three), **"Neutralno"**, **"Ljutito"**, and **"Blaže"** (milder anger). Latin diacritics and Cyrillic command forms are supported. The menu buttons remain available. A successful text-command unit test does not establish successful headset recognition; judge that in VR.

This trial changes speech input only. The active audition still replays fixed clips and rejects ordinary conversation. Live Montenegrin replies, expressive synthesis and their latency need a separate end-to-end test; the saved normal TTS backend is still English Kokoro.

Record listening judgments separately: emotional contrast, source-voice similarity, voice/body agreement, lip sync and loudness. Further model generation is not implied by a successful audio download or playback.
