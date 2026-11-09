# v0.6.0 — student sessions, merged branches and post-merge fixes

This complete Windows package contains the built game, services, character
profiles and voice packs. No older release or patch folder is required, and
Unity Editor and Unreal Engine are not needed to run it. Initial setup still
downloads the AI models.

## New

- **Student names.** At launch the game asks for the student's name, then opens
  the character menu. The name is stored in the session log and in exported logs.
- **Change student.** A button in the menu header switches to the next student.
  The current conversation's log is never relabelled; the new name applies to the
  next conversation. Each later conversation asks for a name again.
- **Session log export.** "Export session log" on the Session page saves a named
  ZIP in `logs/exports/`.
- **Seated gestures and fitted wardrobe** for the MetaHuman cast (gesture bank
  currently prepared for Ivan only).
- **Hardware profiles, recorded-speech reuse and benchmark tools** from the
  latency work (**Hardware Profiles.cmd**, **Benchmark Responses.cmd**,
  **Check GPU Memory.cmd**). Existing installations keep their current settings.

## Fixes

- Patients no longer overreact. `llm_stable_prefix` moved the relationship state
  into the student's turn; it is now off in every hardware profile.
- Setup no longer merges a hardware profile into an existing configuration
  without one, which had silently enabled latency options.
- Speech recognition uses **Bosnian** for Montenegrin conversations (previously
  Serbian). Existing installations are migrated automatically on first start.
- Stray non-Latin characters in replies (e.g. `u量 posla`) are retried, then
  removed if the model repeats them.
- Stefan's voice was about 12 dB quieter than the other patients; his voice
  references are now level-matched.
- Alex, Nikola and Stefan use the Oct 21 seated idle again, fixing seat clipping
  and positioning introduced by the Oct 29 clip update. Ivan keeps the new clip.
- Fixed the garbled "is speaking…" status text.

## Verification

236 service regression tests and 15 Unity EditMode tests pass. The built player
passed the `--student-name-check` self-check end to end (launch name, character
menu, named session, log export, reset, reconnect and Change student). An A/B run
against the same model confirmed dialogue quality matches v0.5.1 with the new
code. Checks used the RTX 5090 development PC in desktop mode; they do not
qualify VR frame timing or response latency on the target RTX 4090.

## Known limitations

- A reply takes roughly 20 seconds; about three quarters of that is speech
  synthesis, not dialogue.
- Patients do not know family names, parents or work history: those details are
  not authored in `characters/*/profile.json` yet.
- Seated gestures are prepared for Ivan only.

## Upgrade and test

Close the game and run **Stop Services.cmd**. Merge the ZIP's complete
`PsychologyVR` folder into the existing installation, replacing matching files.
Keep `.cache`, `services/config.local.json` and all `logs/`. Launch with
**Start Desktop.cmd** or **Start VR.cmd**; the first start refreshes the Python
environment, which takes a few minutes.

After a test, double-click **Export Diagnostics.cmd** and send the ZIP from
`diagnostics/` for resource/timing review. Conversations are saved separately in
`logs/sessions/`. Diagnostics exclude conversation text, recordings and
credentials. No data uploads automatically.
