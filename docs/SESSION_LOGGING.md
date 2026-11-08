# Automatic session logs

Text conversations and VR conversations use the same automatic logging in the
local bridge. Students do not need to export or end a session to save it.

## Location and contents

Normal sessions are saved under `logs/sessions/YYYY-MM-DD/`, relative to the
project folder. Each session has a unique filename containing its UTC start time,
character scenario, a safe student-name fragment when supplied, and archive ID,
with two companions:

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

The Unity game asks for the student's name at launch, before the first patient
reply, and asks again for each new conversation. Text chat asks when starting a
conversation. Desktop/VR
provides a controller keyboard as well as physical keyboard input; text chat uses
a name dialog. Cancelling keeps the previous conversation and its student name.
Names are not saved as an application preference or supplied to the patient model.

Records include the entered student name, session ID, character, language,
text/VR source and UTC event timestamps. The name appears in the readable header
and structured `session_started` event. Reset keeps the current student identity;
a new conversation asks for a name again. Older sessions and automation clients
that omit a name remain readable. This is a supplied label, not verified attendance.
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
upload is implemented. Browser **Export transcript** includes `student_name` in
the downloaded JSON and the student name in its filename. The separate resource
and timing diagnostics export continues to exclude names and conversation text.
In the Unity game's **Session** menu, **Export session log** saves a named ZIP in
`logs/exports/`. It contains the current session's readable TXT and structured
JSONL log, including the full student name. The export is a consistent snapshot;
it does not end or reset the conversation. Exporting again creates a new ZIP.
An unwritable log directory or full disk causes a visible request error rather
than allowing the conversation to continue silently without saving.

## Configuration and activation

`session_log_dir` can override the folder in the service configuration, using a
project-relative or absolute path. The scripted `config.example.json` uses
`services/.runtime/demo-session-logs` to separate test conversations from student
sessions. If choosing another folder, exclude it from version control as well.

Restart existing bridge/text services after installing this change and start a
fresh conversation. Earlier unsaved conversations cannot be recovered by it.
The desktop/VR name prompt requires the updated player scripts. The local Windows
player combines the v0.5.1 release assets with those compiled scripts. A normal
Unity Editor build also includes the prompt. The `--student-name-check` player
check exercises the actual prompt, validation, cancellation and session API.

Service tests cover Unicode names, validation before replacing an existing
session, reset/replacement, immediate persistence, write failures, crash recovery
and retention beyond the model's memory limits. Browser flow tests cover export
identity and cancelled or failed conversation switches.
