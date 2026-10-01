# Repository guide

## What is included

| Folder | Contents |
| --- | --- |
| `unity/` | Unity 6000.6.0f1 project, consultation scenes, art, baked lighting, NPC/player rigs, menus and C# code |
| `services/` | Local dialogue/speech bridge, example configuration, dependency pins and tests |
| `characters/` | Fictional character profiles, scenario descriptions and emotion data |
| `tools/` | Launchers, downloads, asset conversion, rig inspection and TTS audition scripts |
| `experiments/tts/` | Shareable audition inputs and alternative-TTS environment snapshot |
| `docs/` | Execution notes, controls, implementation reports, speech research and listening decisions |
| `man/`, `jumper_man/`, `Characters_with_expressions/` | Original supplied 3D model packs, textures and available source formats, preserved through Git LFS |

Large art files use Git LFS. A ZIP download or clone made without LFS may contain pointer files in place of models/textures. Run `git lfs install` and `git lfs pull` before opening Unity. Unity `.meta` files, package locks and project settings are versioned.

## Local-only material

The following remain on the development machine and are ignored by Git:

- `.cache/`, `.tools/`, `.venv/`: downloaded weights, runtimes and environments.
- `services/config.local.json`, `.env*`, and service runtime output.
- `docs/generated/fish-local/` and other generated audition folders: personal voice references, cloned speech, listening pages and per-run records.
- Unity import caches, editor preferences, preview videos and most screenshots.
- Working build folders stay outside Git history; packaged Windows builds are available from GitHub Releases.
- Session logs and personal facial capture data stay outside source history. The three contributed voice packs and selected audition material are tracked through Git LFS; the complete release also contains the approved shared reference voice.

The documentation retains historical local-preview URLs and file paths. Those links describe development evidence, not hosted repository content. Small top-level audit/provenance JSON files and the room screenshot are included. Asset source URLs and credits are in `ASSET_CREDITS.md`.

The asset-conversion/audit scripts can read the original download packs after cloning with Git LFS. They also need their documented tools, such as Blender. Source checkouts omit personal recordings; auditions need a locally provided recording and its exact transcript. The private Windows release separately includes the approved reference for running the game.

## Prebuilt Windows downloads

[GitHub Releases](https://github.com/IgorCulafic/psychology-vr/releases/latest) provides a standalone `psychology-vr-windows.zip`. Extract its complete `PsychologyVR` folder and use the Start VR/Desktop/Text Chat CMD launchers. The package includes the current player, character profiles, bridge code, approved voice and portable installer. It downloads pinned AI dependencies on first launch. No source clone, Unity, Git, Python installation or API key is required. See [START HERE](../START%20HERE.md).

The older v0.1 release remains an archive of earlier development players. Its instructions about extracting into a cloned repository do not apply to the standalone v0.2 package. The separate candidate preview is an old character audition, not the current game.

Build archives exclude Unity debug backup folders, session logs, local machine configuration and model caches. Release assets include SHA-256 checksums and a per-file manifest. The v0.2 archive includes the explicitly approved voice; model weights download directly from their pinned upstream sources. Those sources retain their own terms and notices.

## Fresh-machine setup

For running the game, use the release workflow above. For development:

1. Clone with Git LFS and open the `unity` subfolder in Unity 6000.6.0f1.
2. Follow the root README to create the Python environment and download the selected local runtimes/models.
3. Copy `services/config.live.example.json` to `services/config.local.json`. Keep machine-specific edits in the latter. Do not overwrite an existing local configuration when updating.
4. Build from **Psychology VR → Build Windows prototype** in Unity.
5. Launch with `tools/launch.ps1 -Desktop`, or connect Quest Link and launch without `-Desktop`.

For a lightweight transport/animation check without downloaded models, use `tools/launch.ps1 -Scripted -Desktop` after creating `.venv` and building the player. This uses Windows speech and scripted dialogue. It does not test AI responses or STT.

## Speech experiments

The expressive game now uses BF16 Higgs with sentence playback. Kokoro remains an optional older configuration; OmniVoice and Fish remain comparison experiments. See `ALTERNATIVE_TTS_AUDITIONS.md` for historical auditions and `SENTENCE_PLAYBACK.md` for current behavior.

The alternative-TTS environment is separate from the game's Python 3.11 environment. Its Python 3.12 package snapshot is `experiments/tts/requirements-alternative-lock.txt`. Install with the PyTorch CUDA wheel index available:

```powershell
uv venv --python 3.12 .tools/alternative-tts-venv
uv pip install --python .tools/alternative-tts-venv/Scripts/python.exe --extra-index-url https://download.pytorch.org/whl/cu128 -r experiments/tts/requirements-alternative-lock.txt
```

This is a snapshot of the tested Windows CUDA environment, not a portable lock for all operating systems. The OmniVoice source is pinned to its tested commit. Download the pinned models into the paths in the audition report; the scripts load them offline. The Higgs community port executes model Python code via `trust_remote_code=True`, so retain the inspected revision.

The existing audition scripts expect these local inputs under `docs/generated/fish-local/references/`:

- `clone-test-1.wav`: the complete reference recording.
- `clone-test-1-short.wav`: a shorter complete-sentence excerpt.
- A matching `.json` beside each WAV, containing `{"text": "The exact words spoken in this file."}`.

Use the same speaker for both files. Substitute your own transcript; the filenames are historical harness conventions. Copy `experiments/tts/fish-cases.json` to `docs/generated/fish-local/alternatives/fish-cases.json` before running the Fish baseline command in the report. The output parent folders may need to be created first. Listening-page builders require the preceding audition runs to have completed; old samples are not part of the repository.

## Verification

`python -m unittest discover -s services -v` runs the bridge and release-helper tests using the standard library. GitHub Actions runs this suite on Windows without downloading model weights or art through LFS. It does not build Unity or validate headset performance, pronunciation or emotional delivery. Release setup is also exercised in a separate extracted folder with a fresh Python environment; cached model weights are reused for that check.

This is a private prototype repository. No repository-wide open-source license is assigned over third-party art or models; their individual terms and attributions remain applicable.
