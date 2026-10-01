# Standalone Windows release

The `v0.2.4-complete-package` release separates the runnable application from the
Unity development repository. `psychology-vr-windows.zip` contains the complete
player, services, four patient profiles, reference voice approved by its owner,
CMD launchers and a checksum-pinned portable uv installer. It excludes session
logs, local configuration, credentials, Python environments and model caches.

First launch installs Python 3.12.13 locally, creates `.tools/portable-env`, and
installs the 65 pinned packages in `services/requirements-portable.txt`. It then
downloads four exact Hugging Face revisions and the pinned llama.cpp CUDA/Rhubarb
runtimes from `services/portable-manifest.json`. Model contents and runtime ZIPs
are SHA-256 checked. Model downloads total 19.11 GB for Fast dialogue,
24.54 GB for the 4090 preset or 27.45 GB
for original quality; allow approximately 45 GB free
space for libraries, download caches and the game. Existing verified files are
reused, and Setup checks/repairs missing or damaged model files.

The selected speech remains BF16 and uses the approved full reference at
temperature 0.70. The packager requires `--include-approved-voice` to add the shared reference.
The contributed person_01/person_02/person_03 packs are versioned separately and
added with `--include-voice-packs`. This repository and its releases are public;
the contributed voices are included as requested by the project owner. Personal
facial-capture data and student logs are not packaged or uploaded.

The v0.4.0 package also includes the voice listening page, contributed packs and
standalone recorded-face preview player. The latter requires a separately prepared
take; no personal capture data is included. The Unreal prototype stays in the
source repository. See [current release details](RELEASE_0_4_0.md).

## Build and package

Build the Windows player using Unity's `PsychologyVR.Editor.ProjectSetup.BuildWindows`.
Regenerate the model manifest only when intentionally changing tested revisions.
The official uv ZIP and its MIT/Apache notices are cached under `.cache/releases/`.

```powershell
./.venv/Scripts/python.exe -m unittest discover -s services
./.venv/Scripts/python.exe tools/create-portable-manifest.py
./.venv/Scripts/python.exe tools/build-voice-index.py
./.venv/Scripts/python.exe tools/package-portable.py --include-approved-voice --include-voice-packs --include-recorded-preview --tag v0.4.0-voices-animation
```

Package after committing the source: the release manifest records that commit,
each included file's size and hash, the archive hash, and whether the approved
voice is included. Publish the ZIP, `release-manifest.json`, and `SHA256SUMS.txt`
as GitHub release assets. Publish one complete application ZIP each time;
do not create incremental patch ZIPs. Users can install it independently or merge
the full package into an existing installation to retain models, settings and logs.
The source ZIP alone is not the runnable game.

## Verification scope

111 standard-library service/release-helper tests pass, including extraction path
checks and configuration preservation. A separate extracted folder containing
spaces installed a fresh Python runtime and all required libraries. Large model
weights were reused from the verified development cache rather than downloaded
again; the installer verified their hashes and extracted its runtime archives.
The actual Setup CMD launcher was exercised through `cmd.exe`, including a retry.

From that extracted copy, the built game passed its streamed pause/resume and
interruption check (`STREAM_CHECK_OK`). A full Qwen-to-BF16 conversation also
passed (`SMOKE_PLAYBACK_OK`, `SMOKE_OK`), including audible playback, lip movement
and a rendered room inspection. First playback took 33.225 seconds in that single
full-model check; the authored streaming fixture took 3.039 seconds. These are
smoke-test observations, not a performance guarantee. Whisper loaded and returned
empty text for a silent WAV, and the packaged text tester returned healthy.

That test found two issues which were fixed before packaging: the approved WAV
uses floating-point audio, and a development shell's inherited module path can
confuse Windows PowerShell launched via CMD. The check now uses SoundFile, and
CMD launchers isolate the child PowerShell module path and preserve failure exit
codes. Python environments are checkpointed separately so a later download failure
does not require reinstalling completed dependencies.

This is a same-PC extracted-package test, not a clean Windows VM, another GPU,
or another Quest headset acceptance test. NVIDIA drivers, Meta Quest Link and
the Windows Visual C++ runtime remain system prerequisites. See
[START HERE](../START%20HERE.md) for the end-user steps.

## Setup configuration fix — v0.2.1

The previous installer assumed every existing `config.local.json` already had
`higgs_reference`, causing a KeyError with partial/older configurations. Setup now
merges missing expressive and portable-runtime defaults, preserves explicit user
choices, validates the reference and writes the upgraded configuration atomically.
It saves the original bytes under `.runtime/config-backups/` before an upgrade.
Invalid JSON and missing voice files produce actionable errors without changing
the original configuration. Four regression tests cover migration, custom voice
preservation, missing references and malformed configuration. That release provided a small
`setup-fix.zip` lets existing installations replace only the helper and reuse their
downloaded dependencies and models. The extracted test installation was retested
with all three portable path keys removed; the upgrade and runtime check passed
(`PORTABLE_READY`) without downloading models or starting a new conversation.

## Automatic GPU presets — v0.2.2

`PC Settings.cmd` exposes Auto, University / RTX 4090 and Original quality. Auto
selects IQ3_M / 32 GPU layers on 24 GB cards and IQ4_XS / 48 on 32 GB+ cards.
Only one dialogue quant is downloaded; both remain pinned in the manifest.
BF16 speech and character settings are unchanged. That release provided a small
`pc-settings-update.zip` contains all required settings/helper/manifest changes
for existing installations. See [GPU presets](GPU_PRESETS.md) for measured memory,
the latency tradeoff and outstanding university hardware acceptance.

## Opt-in fast dialogue — v0.2.3

Option 4 selects the pinned 9B Q6 model with full GPU offload. That release also
provided a settings patch carrying `services/alex_service.py` for the progressive length-retry
fix discovered in testing. Auto and both 27B options are unchanged. The local
first-playback observation was 13.131 seconds, with 20.9 GiB total peak GPU use.
The smaller model has known language/character weaknesses; see GPU_PRESETS.md
before choosing it for students. The test is not a 4090 headset acceptance run.

## Complete packages — v0.2.4 onward

Each release is a standalone full application ZIP with every previous fix.
Patch packaging has been removed. The v0.2.4 change is packaging and instructions
only: the tested game, dialogue options, BF16 voice and service behavior are
unchanged from v0.2.3. First-time model and runtime downloads still occur through
Setup. See START HERE.md for fresh installation and preservation of existing data.
