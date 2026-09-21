# Automatic session logs

Text conversations and VR conversations use the same automatic logging in the
local bridge. Students do not need to export or end a session to save it.

## Location and contents

Normal sessions are saved under `logs/sessions/YYYY-MM-DD/`, relative to the
project folder. Each session has a unique filename containing its UTC start time,
character scenario and archive ID, with two companions:

- `.txt`: readable student/patient dialogue, emotional cues, relationship metrics,
  timings and interruptions.
- `.jsonl`: structured events, including full validated response segments,
  emotional/animation controls, relationship state, memory diagnostics and timings.

The student utterance is saved when a turn is accepted, before generation. Each
completed response is saved before it is returned to the client. Files are flushed
to disk after every event. Failed and cancelled requests retain the accepted input
and an error category; raw provider errors and hidden prompts are not archived.
Invalid or rejected requests are not conversation turns and are not logged.

Resetting or replacing a conversation creates a new archive and preserves the old
one. Logs are not limited by the model's context window or its 96-exchange memory.
There is no automatic deletion. The server's live conversation state still resets
on restart; logs are not automatically replayed into a new conversation.

## What is and is not recorded

Records include a session ID, character, language, text/VR source and UTC event
timestamps. They do not collect a student name or provide attendance tracking.
VR input is the accepted speech-recognition text, not an archived microphone
recording. Generated audio files are not copied into this archive; any audio URL
in a response points to temporary runtime output and may later stop working.

A completed response means generation finished, not that the student heard every
word. The updated Unity player separately reports completed sentences and the
current audio clock; `playback_finished` identifies the confirmed played prefix.
Partial-sentence words are not inferred. Legacy clients have no such playback
confirmation. See [sentence playback](SENTENCE_PLAYBACK.md). Closing a browser/game
or a crash may leave no explicit end event; all
previously flushed events remain. A turn with no completion/failure event may have
been in progress when the service stopped. `session_log.read_records` can recover
complete events when a crash leaves the final JSONL line incomplete.

Logs stay on this computer and `logs/sessions/` is excluded from Git. No automatic
upload is implemented. Browser **Export transcript** remains available separately.
An unwritable log directory or full disk causes a visible request error rather
than allowing the conversation to continue silently without saving.

## Configuration and activation

`session_log_dir` can override the folder in the service configuration, using a
project-relative or absolute path. The scripted `config.example.json` uses
`services/.runtime/demo-session-logs` to separate test conversations from student
sessions. If choosing another folder, exclude it from version control as well.

Restart existing bridge/text services after installing this change and start a
fresh conversation. Earlier unsaved conversations cannot be recovered by it.
No Unity rebuild is required.

Validation: 87 service tests pass, including Unicode, immediate persistence,
reset/replacement, generation failure, cancellation during reset, write failure,
truncated-tail recovery and retention beyond the context/memory limits.
