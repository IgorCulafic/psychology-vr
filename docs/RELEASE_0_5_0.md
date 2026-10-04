# v0.5.0 — MetaHuman cast, approved voices and diagnostics

This is a complete Windows application ZIP. Extract the whole `PsychologyVR`
folder; no previous release or patch folders are required. Initial setup still
downloads the local AI models. Unity Editor and Unreal Engine are not needed to play.

## Included

- Four clothed MetaHumans in the consultation game: Alex/Dominic, Ivan/Bruce,
  Stefan/Mateo and Nikola/Victor. Baked facial reactions, neck movement, tears
  and speech/emotion blending are integrated. Torso/hand animation is deferred.
- Scenario voice assignments: Igor for burnout, Person 1 for fire, Person 2 for
  bereavement and Person 3 for earthquake. Runtime packs contain the selected
  references, transcripts, hashes and emotional synthesis settings. Person 1
  uses the approved mono references with background noise and reverb reduced.
- BF16 Higgs quality retained. Whole emotional beats keep their approved delivery
  instead of being forcibly split into sentences. Presets specifically approved
  with sentence pauses keep those pauses. Interrupted unfinished speech is not
  assumed to have been heard in full.
- Prepared voice references and cached fixed opening lines; fresh replies still
  require generation. No student conversations are cached as stock answers.
- Gemma remains the default. Patient prompts distinguish personal experience
  from expert explanation; simple questions no longer trigger a forced minimum
  length rewrite. Requested detail remains possible.
- Desktop borderless fullscreen/windowed settings and adjustable larger subtitles.
- Automatic resource samples every two seconds: GPU utilization, dedicated VRAM,
  GPU temperature and system RAM. **Export Diagnostics.cmd** creates a local ZIP
  of the last seven days of resources and reply timings, with a readable summary.
  Cached opening lines are reported separately. Dialogue, recordings, credentials
  and raw service logs are excluded; there is no automatic upload.
- Existing text conversation tester, automatic session journals, offline voice
  previews and standalone facial/head-motion preview tools are retained.

## Upgrade

Close the game and run **Stop Services.cmd**. Merge the complete ZIP's
`PsychologyVR` contents into your existing installation, replacing matching files.
Keep `.cache`, `services/config.local.json` and all `logs/`. Use the normal
**Start Desktop.cmd** or **Start VR.cmd** launcher afterward. A full service
restart is necessary to load the updated speech, dialogue and diagnostics code.

Fresh installations default to Gemma 4 12B QAT Q4, BF16 Higgs and CPU Whisper.
Existing configuration is preserved; use **PC Settings.cmd** if it selects an
older model. The release does not bundle model weights, local configuration,
student sessions, raw face-capture footage, Unreal builds or editor caches.

## Known limitations and verification

Gemma can still produce malformed regional-language words and awkward grammar.
The latest prompt/length changes are a partial improvement, not a fluency fix.
Person 1 and Person 2 have no approved sadness/happiness runtime recipes yet;
these emotions retain that speaker's neutral voice rather than inventing a preset.
Headset stability, VR frame rate and RTX 4090 performance still need university
testing. GPU measurements cover the whole PC, and two-second samples can miss
shorter peaks. First-audio readiness excludes microphone/STT time and does not
prove the listener heard the audio.

The existing final Unity Windows build passed before packaging. The full Python
service suite passes 165 tests. The diagnostics recorder was exercised against
the local NVIDIA GPU and its ZIP exporter. Package validation checks required
assets, offline voice references and archive CRCs. The release manifest records
the source commit and file hashes; SHA256SUMS covers the ZIP and manifest.
