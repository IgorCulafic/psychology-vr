# v0.4.0 - Voice library and acted-animation tools

This is a complete Windows application package, including the previous Gemma
Unity release and the new voice and animation development tools. Extract the
whole `PsychologyVR` folder. For an upgrade, stop the application and services,
then merge the complete folder into the existing installation, keeping your
model cache, local configuration and session logs.

## Included

- Unity consultation player with Gemma 4 12B QAT Q4 as the fresh-install default,
  BF16 Higgs speech, CPU Whisper and sentence-based speech playback.
- All three contributed voice packs: original recordings, prepared WAVs,
  transcripts, source hashes, selected generated samples and preset settings.
- `Preview Voices.cmd`: an offline listening page that works without AI setup.
  Person 1 and person 2 have selected anger presets. Person 3 has selected anger
  (bitterness), sadness (restrained delivery) and happiness (longer reference
  plus enthusiasm). The samples demonstrate settings that can generate new text.
- Standalone facial/head-motion preview player and MediaPipe extraction tools.
  `Preview Recorded Face.cmd` accepts a prepared take folder dragged onto it.
  Personal capture videos, face crops and extracted take data are not bundled.
  See `RECORDED_FACE_POC.md` for preparing your own take in a separate environment.
- Voice preparation/audition tools, recording script, Montenegrin one-page project
  overview (`PROJECT_OVERVIEW_CG.pdf` in the ZIP) and the generated statistics-line
  sample in WAV/MP3 format under `output/audio/`.
- Unreal C++ prototype source, launchers and development notes in the GitHub
  repository. The Windows ZIP contains its status document, not an Unreal build.

## Integration still pending

The new voice packs are not automatically assigned to patients. The consultation
player continues using its configured shared voice reference. The facial preview
is a separate proof of concept; acted animations have not replaced the live
consultation's procedural gestures. Full-body capture/rotoscoping, further voice
review, sustained build/VR stability testing and target RTX 4090 acceptance remain.

The three new packs are also available in the source repository through Git LFS.
Model weights, local configuration, credentials and student session logs are not
included. Large AI downloads still happen during first setup.

## Release verification

The release manifest records the source commit and every packaged file's hash.
`SHA256SUMS.txt` covers the complete ZIP and manifest. Build and test results are
listed in the GitHub release notes; they do not establish headset stability.
