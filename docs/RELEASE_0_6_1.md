# v0.6.1 — fresh installs use the Higgs Montenegrin voices again

Fixes a setup regression in v0.6.0. Everything else is unchanged from v0.6.0
(see `RELEASE_0_6_0.md`).

## Fix

v0.6.0 set up every **new** installation with the RTX 3080 development profile:
the small English **Kokoro** voice, English conversation and English speech
recognition, even on 24 GB cards. On those PCs the patients spoke English with a
generic voice, or setup failed with a Kokoro error.

- New installations now choose by GPU memory. **24 GB or more** (the university
  RTX 4090) gets the Higgs cloned voices, Montenegrin conversation and Bosnian
  speech recognition, as in v0.5.1. Smaller cards keep the RTX 3080 profile,
  because Higgs needs 24 GB.
- PCs already set up with v0.6.0 are repaired automatically on the next start:
  on a 24 GB+ card, the RTX 3080 Kokoro configuration is replaced with the Higgs
  Montenegrin settings. The previous file is kept in
  `services/.runtime/config-backups/`.

## Verification

238 service regression tests pass, including fresh-install and repair cases for
10 GB and 24 GB cards. The release ZIP was extracted into an empty folder and set
up from scratch on the RTX 5090 development PC: setup selected Higgs, Montenegrin
and Bosnian speech recognition, and the packaged game passed the full
`--student-name-check` self-check against services started from that folder.

## Upgrade

Close the game and run **Stop Services.cmd**. Merge the ZIP's `PsychologyVR`
folder into the existing installation, replacing matching files. Keep `.cache`,
`services/config.local.json` and `logs/`. The next **Start Desktop.cmd** or
**Start VR.cmd** reruns setup once (a few minutes), which applies the repair and
downloads the Higgs voice model if that PC never had it.
