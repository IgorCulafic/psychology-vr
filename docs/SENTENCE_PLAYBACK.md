# Sentence playback and delivery refinement

21 September 2026. The Windows player uses sentence delivery when the bridge
advertises `sentence_streaming`. The existing text tester and recorded auditions
keep their compatible whole-response endpoint.

## Less waiting with BF16 speech

The bridge still validates the complete Qwen reply, including language, disclosure
length and performance controls, before any of it is spoken. It then splits the
validated beats into sentences. The first sentence becomes available as soon as
its Higgs WAV and mouth cues are ready. Unity plays it while the worker prepares
later sentences. This is sentence-level speech pipelining, not partial-JSON model
token streaming or streaming samples out of the Higgs vocoder.

The full private reference, seed 42, temperature 0.70 and **BF16** weights remain
selected. No quantization, pitch shifting or faster speech was introduced.
Generation can still be slower than playback, so pauses between sentences remain
possible. A single-sentence response gets little benefit from this pipeline.

Three authored four-sentence comparisons through the real BF16 speech service:

| Comparison | First sentence ready | All sentences ready | Audio duration |
|---|---:|---:|---:|
| Frustration / anger | 4.99 s | 16.88 s | 9.56 s |
| Sadness / despondency | 3.74 s | 17.59 s | 10.80 s |
| Anxiety / fear | 4.49 s | 15.49 s | 9.84 s |

These times exclude Qwen because the comparison lines are authored. They compare
readiness within the same sentence-generation run, not a benchmark against a
single combined-paragraph TTS request. In the built desktop player's authored
opening check, first playback began after 3.14 seconds. Hardware here is the
development machine; these are not Quest or RTX 4090 acceptance measurements.

A full desktop Qwen-to-Higgs smoke test also passed, including complete playback
and lip movement. Its first playback took **39.64 seconds**, including appraisal
and reply generation. This cold-context example makes the remaining model delay
visible; speech-only numbers above should not be presented as conversation latency.

## What enters history

Unity reports a monotonically increasing count of fully played sentences, plus
the audio clock within the current sentence. It sends progress about once a second
and confirms completion at sentence boundaries. Pause time does not advance this
clock. The server commits dialogue and extractive memory when playback finishes
or is interrupted, using the confirmed sentence prefix only.

If stopped halfway through a sentence, history gets an interruption marker;
unplayed sentences and the uncertain fragment are not added to patient memory.
The fragment's elapsed time is logged without guessing which words were heard.
The student's accepted utterance remains. Relationship appraisal may reflect that
utterance even if the reply was interrupted. Facial delivery state follows the
last fully played sentence.

Audio playback acknowledgements establish what the client played, not proof a
human heard it (for example if their device was muted). Word-level alignment is
not available, so unfinished sentence words cannot be reconstructed precisely.
After a crash, progress survives in the journal but live context is not restored.

Duplicate or late acknowledgements cannot move the prefix backwards. Old turn IDs
cannot affect a newer turn. The updated client supplies an expected generation
when starting a reply, preventing a delayed start request from reviving work after
an interrupt. Interrupt/reset/replacement invalidate further output;
an already executing GPU call may finish, but its unpublished audio is discarded.
A later synthesis failure preserves the already played prefix. The game stops
accepting another turn if its final playback save fails, with Stop/Reconnect
available for recovery.

API: `/turn/start`, `/turn/poll`, `/playback`, `/turn/finish`. `/interrupt` and
`/reset` accept a final playback snapshot. Legacy `/turn` still commits generated
text on success; external clients must adopt acknowledgements to get these audio
history semantics. New log events are `segment_ready`, `playback_progress` and
`playback_finished`; see [session logging](SESSION_LOGGING.md).

## Emotional delivery

- Sentence boundaries no longer restart emotional body loops.
- Emotional face controls, including the Character Creator rig, respect the
  requested transition duration while speech mouth closures remain responsive.
- Recovery/withdrawal has a longer minimum blend than confrontation. Emotion
  choices remain model driven; the adapter does not invent different feelings.
- Recent repeated gestures are suppressed, with a second short cooldown in the
  player. Crying/panic/withdrawal avoid conflicting extra gestures. A gesture
  requested for a multi-sentence beat appears once, not on every sentence.
- Confusion now uses questioning raised brows and open eyes, distinct from the
  skeptical side-squint/pressed mouth. Relief has a smaller smile than happiness.
- Mild anxiety no longer forces Higgs's stronger fear tag. Preferred anger keeps
  its single auditioned anger token and original reference/settings.
- TTS text is Unicode-normalized without dropping regional diacritics. Optional
  `higgs_pronunciation` in the speech configuration maps explicit whole words or
  phrases to auditioned pronunciations, leaving the transcript unchanged. No
  speculative corrections are enabled by default. Restart speech after edits.

Pronunciation and voice identity remain listening judgements. These controls do
not guarantee native accent or identical timbre across emotional samples.

## Reproduce and review

```powershell
./.venv/Scripts/python.exe -m unittest discover -s services
./tools/launch.ps1 -NoGame
./.venv/Scripts/python.exe tools/check_sentence_delivery.py
./.venv/Scripts/python.exe tools/build_delivery_review.py
./unity/Builds/Windows/AlexPrototype.exe --desktop --streaming-check
./unity/Builds/Windows/AlexPrototype.exe --desktop --performance-replay D:/AI/Psychology_VR/services/.runtime/sentence-review/emotion-replay.json
```

The private listening page is `docs/generated/fish-local/delivery-review/index.html`
(served locally at port 8793). Six examples compare your reference against the
emotion pairs above; generated sentences are joined for convenient listening,
without simulating actual generation gaps. Audio and references stay Git-ignored.

99 service tests pass. Unity builds successfully. The built player's streaming
check passed first playback, pause/resume, one complete sentence followed by a
partial second sentence, interruption and suppression of later playback. Its
journal confirmed exactly `Ne mogu da se smirim.` and recorded 0.256 seconds of the
unfinished next sentence. This is desktop verification, not a new headset test.
Six BF16 emotional comparisons also passed the built player's audio, lip movement,
cue matching, pause/resume and interruption checks. Captured poses were visually
inspected and included in the private listening page. Audio identity/pronunciation
still need the user's native-speaker listening assessment.
