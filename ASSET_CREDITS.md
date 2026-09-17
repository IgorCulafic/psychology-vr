# Asset and model credits

- **Cool Man**, by **ardhanaputra**: [original Sketchfab model](https://sketchfab.com/3d-models/cool-man-ad14b71697dd4ea7836c1f06c75e5f72). Licensed under [Creative Commons Attribution 4.0](https://creativecommons.org/licenses/by/4.0/). Changes for this prototype: glTF-to-FBX conversion, Unity material assignments, seated playback, procedural body overlays, and original facial blendshapes for expressions, eyelids, eye direction, and speech. Original source is retained in `man/`. License metadata was retrieved from Sketchfab's public API on 11 September 2026 and is recorded in `docs/generated/character-source.json`.
- **Furnished consultation room:** uses the Poly Haven assets below, all [CC0](https://polyhaven.com/license). Changes: glTF-to-FBX conversion, 1K texture selection, conversion of metallic/roughness maps for Unity URP, scale/placement, and mesh reduction for plants and notebook. The original download URLs and checksums are retained in `docs/generated/room-asset-sources.json`.
  - [Modern Arm Chair 01](https://polyhaven.com/a/modern_arm_chair_01) — patient and player chairs.
  - [Side Table 01](https://polyhaven.com/a/side_table_01) — patient tissue table.
  - [Small Wooden Table 01](https://polyhaven.com/a/small_wooden_table_01) — resized for the player's desk.
  - [Modern Coffee Table 01](https://polyhaven.com/a/modern_coffee_table_01) — window-side table.
  - [Potted Plant 02](https://polyhaven.com/a/potted_plant_02) — room greenery in two sizes. [Potted Plant 01](https://polyhaven.com/a/potted_plant_01) was downloaded and converted for evaluation but is not placed in the final room.
  - [Binder Notebook](https://polyhaven.com/a/binder_notebook) — player's open notebook.
  - [Modern Ceiling Lamp 01](https://polyhaven.com/a/modern_ceiling_lamp_01) — overhead fixture.
  - [Wood Floor](https://polyhaven.com/a/wood_floor), [White Plaster 02](https://polyhaven.com/a/white_plaster_02) — architectural materials.
- **Original modeled additions:** room shell, window/door trim, curtains, rug, framed botanical reliefs, shelf/books, tissue box and folded tissue, cup, pencil, and desk session console. Created for this project with `tools/model-room-details.py` and Unity code. No external art was used for the botanical reliefs. The original primitive blockout remains a fallback in `PrototypeRoom.cs`.
- **Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-MTP-GGUF:** [HauhauCS release](https://huggingface.co/HauhauCS/Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-MTP-GGUF), based on Qwen; repository lists Apache 2.0. Selected file: IQ4_XS. Downloaded weights remain outside version control.
- **Kokoro-82M:** [hexgrad](https://huggingface.co/hexgrad/Kokoro-82M), Apache 2.0 model. Local ONNX conversion and runtime from [thewh1teagle/kokoro-onnx](https://github.com/thewh1teagle/kokoro-onnx); runtime MIT. Voice: `am_michael`.
- **faster-whisper:** [SYSTRAN](https://github.com/SYSTRAN/faster-whisper), MIT; local `small.en` conversion of Whisper.
- **llama.cpp:** [ggml-org](https://github.com/ggml-org/llama.cpp), MIT; Windows CUDA runtime b10909.
- **Rhubarb Lip Sync 1.14.0:** [Daniel Wolf](https://github.com/DanielSWolf/rhubarb-lip-sync), MIT, with third-party notices retained in the downloaded runtime's `LICENSE.md`. Used locally to analyze speech into mouth timings; release URL and archive SHA-256 are recorded in `docs/generated/rhubarb-runtime.json`.
- **Emotion presets and tear tracks:** original project code/data. Twenty editable performance presets share the generated Alex facial controls; tear geometry follows the skin surface. No third-party facial animation or tear texture pack was added.

Include this credit file when sharing the prototype. Preserve the individual dependency license notices with redistributed software/models.

## User-supplied candidate audition

Repository packaging: original download folders (`man/`, `jumper_man/`, `Characters_with_expressions/`) and their converted Unity assets are preserved in the private project through Git LFS. Asset-specific rights still apply; this repository does not relicense third-party work.

- `jumper_man/source/Ex wife's new husband.fbx` and `Characters_with_expressions/FBX/`: supplied by the user, who identified Sketchfab as their source. Exact author/source/license records were not included; this entry does not assert redistribution permission.
- `JumperCandidate.prefab`, audition scene, facial cue combinations, URP material conversion and combined opacity textures: project integration work derived from the supplied jumper asset. Originals remain in their supplied folders. The jumper now represents Alex in the main consultation scene as well as in the separate audition.
- `SeatedPlayer.prefab`, `HeadlessBody.asset` and tinted sweater materials: derived from the same supplied jumper for the local player. Head/facial geometry is removed from this copy; controller/headset posing is original project code.
