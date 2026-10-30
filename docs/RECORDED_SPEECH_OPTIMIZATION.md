# Recorded speech and exact audio reuse

This optional patch retains the chosen dialogue model, GPU layer count, voice
precision, references and character behavior. It replays an approved recording
only when the generated text, selected scenario and emotion match exactly.
Words, punctuation and capitalization remain significant; repeated whitespace
and Unicode composition are normalized. There is no semantic nearest-clip
selection and no unsolicited filler while a reply is loading.

## Install on the existing RTX 4090 package

1. Close the game and run **Stop Services.cmd**.
2. Extract the recorded-speech patch into the existing **PsychologyVR** directory,
   merging `services`, `tools`, `docs` and `voices`. The patch contains no
   `config.local.json`; current GPU layers and sentence-mode voice manifests stay.
3. Run **Enable Recorded Speech.cmd**, then **Start Desktop.cmd** or **Start VR.cmd**.

The enable command saves a configuration backup under
`services/.runtime/config-backups/` and adds only these fields:

```json
"speech_cache_enabled": true,
"recorded_speech_enabled": true,
"speech_cache_max_mib": 256
```

To disable, stop the game/services and set both enabled fields to `false`.
Restore the saved configuration to undo all three fields. Restart normally.

## What becomes faster

Approved clips are indexed by speaker/scenario, exact words and emotion. A
matching full clip stays intact even in sentence mode because it is already
ready. The first playback calculates lip sync if needed; subsequent uses reuse
the WAV and validated mouth cues. The library contains selected, already
approved generated auditions. Voice-reference passages and rejected variants
are not automatically used as patient answers. The model is not instructed to
repeat library phrases or restricted to a script.

Successful newly generated speech is also cached locally. Its key includes the
speaker recipe, reference identity/transcript, text, emotion, voice style,
intensity, precision/permission, pronunciation and synthesis implementation/model
identity. Precision, reference or recipe changes invalidate the corresponding
entry. Lip-sync configuration changes reuse the audio but calculate new cues.
Broken audio and transient aligner failures fall back to normal work.
Fixed opening audio is saved during startup preparation and reused on subsequent
launches. The speech model still loads; this does not free its GPU memory or
make the first new, uncached response a warm synthesis benchmark.

Cache entries contain WAV audio and timing metadata and are kept inside the
Git-ignored `services/.runtime/speech-cache/` directory. The default limit is
256 MiB and 512 entries, with least-recently-used eviction. These are local
generated audio files; they are not bundled into releases or diagnostics.
Only the explicitly approved library is distributed.

## Limits and measurement

This is a speech-stage optimization. Appraisal, dialogue generation and
transcription still run. A never-before-generated answer still needs live Higgs
synthesis; the long gaps between new sentences may remain. Replaying recordings
does not turn arbitrary new text into existing audio. The under-15-second
release-to-audible target is still unverified on the RTX 4090.

Compare the same generated sentence twice with unchanged emotion/recipe, then
restart and repeat. Session segment records include `speech_source` as
`recorded`, `cache` or `generated`; stage timings remain available through
**Export Diagnostics.cmd**. Startup, cached openings, ordinary new replies and
cache hits should be reported separately.

Development: `tools/build-recorded-speech-library.py` copies only approved,
checksum-verified candidates from the existing voice preparation metadata.
Their actual words and emotions are retained in `voices/recorded/manifest.json`.
