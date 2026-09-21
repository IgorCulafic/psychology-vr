# Model-directed emotional performance

21 September 2026. Normal conversation selects the performance; students do not need to say emotion commands. The existing response-to-animation connection is now backed by clearer delivery guidance and a repeatable check using the same Unity playback routine as live conversation.

## One reply, coordinated cues

Qwen returns validated JSON containing one or more spoken segments. Each segment has its own text, emotion, intensity, gaze, gesture, transition, pauses and gesture timing. The prompt usually requests one short segment; a meaningful emotional change can produce two. It distinguishes frustration/anger, sadness/crying, numbness and partial relief, calibrates intensity, and discourages extra hand gestures during intense crying or panic.

Unity applies the emotion at the start of the segment, allows its reaction pause, then plays speech and lip timing. The gesture runs at `gesture_at × clip duration`; the final expression persists while listening. The emotional preset drives the face, posture, arms, fingers and, when appropriate, tears/redness. Existing joint/contact constraints remain active. Speech owns mouth articulation so emotional mouth shapes do not obscure it.

Higgs receives trusted categorical emotion tokens derived from the validated segment. Raw stage directions, reasoning and trigger tags never become spoken text. **BF16 remains selected**, with the full reference and temperature 0.70. Intensity is continuous for the visual performance; Higgs has no verified equivalent continuous emotion-strength control. Its supported emotion tokens, plus the existing hesitant/numb prosody adjustments, determine voice delivery. Gesture timestamps are relative to the audio, not exact word alignment.

Stop/reset cancels queued playback and clears transient actions/subtitles. Opening the menu pauses audio and performance. Multi-segment replies preserve each segment's cues and retain the final emotional state in the bridge's bounded history.

## Repeatable checks

```powershell
./tools/launch.ps1 -NoGame
$env:PYTHONIOENCODING='utf-8'
./.venv/Scripts/python.exe tools/capture_performance_replies.py
./unity/Builds/Windows/AlexPrototype.exe --desktop --performance-replay D:/AI/Psychology_VR/services/.runtime/performance/replies.json
```

Use the absolute path for your own checkout. Capture requests three **real Qwen + Higgs** conversational turns, then adds a separately labelled authored two-segment crying-to-relief fixture. The fixture exercises tears and a timed nod even if the natural conversation does not warrant crying. It must not be represented as a model-selected emotional response. The local bridge serves the captured audio; leave it running for replay.

The replay uses `PlayReply`, the live Unity routine, and checks segment order/emotions, audio playback, jaw activity, tears, gesture timing, pause/resume and cancellation before a queued second segment. It writes screenshots and `performance-playback-report.json` alongside the capture, then exits with a failing code on assertion failure. Private cloned speech and detailed dialogue stay under ignored `services/.runtime`; a nonprivate summary is in `docs/generated/emotional-performance-validation.json`.

The backend suite additionally checks per-segment controls reaching speech, final-state continuity, cancellation during synthesis, and that an emotion word in speech does not itself become an animation or voice command.

Verification on this host: **46 Python tests passed**, the Unity Windows build succeeded, and the five-segment desktop replay passed. The three real model replies selected anxious (0.65), frustrated (0.55) and relieved (0.40). The authored crying fixture reached tear wetness 0.95 and near-full face covering; frame captures were inspected after animation/IK completed, rather than during the restored base pose. Pause/resume and interruption-before-the-next-segment passed. Detailed measured values are in the JSON summary. OpenXR reported no available headset; this run used desktop mode.

This desktop verification does not replace the next Quest listening/visual check. Facial cues may still overlap, voice intensity is categorical, and prompts cannot guarantee the most appropriate emotional interpretation of every exchange. Character biography and grammar limitations from [the language pass](MONTENEGRIN_CONVERSATION.md) also remain.
