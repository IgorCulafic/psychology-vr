# Furnished consultation room

Direction selected by the user: warm, realistic materials and furniture. Expressive TTS is deferred to a separate pass.

The new room is saved as `unity/Assets/PsychologyVR/Prefabs/ConsultationRoom.prefab` and referenced by the consultation scene. It can be opened in Unity's Prefab Mode for layout edits. Original downloaded sources remain in `.cache/assets/polyhaven`; converted models and materials live in `unity/Assets/PsychologyVR/Art/Environment`.

## Free assets selected

Eight models and two texture sets were downloaded from [Poly Haven](https://polyhaven.com/models/furniture), under its [CC0 asset license](https://polyhaven.com/license). Seven models are used in the final room. Potted Plant 01 remains a source candidate because its leaf mesh produced empty bounds in the Unity player; the final room uses Potted Plant 02 in two sizes. Individual links and changes are in `../ASSET_CREDITS.md`. Download metadata and checksums are recorded in `generated/room-asset-sources.json`; mesh counts and dimensions in `generated/room-asset-audit.json`.

Also reviewed: [Kenney Furniture Kit](https://kenney.nl/assets/furniture-kit) and [Quaternius Ultimate Furniture](https://quaternius.com/packs/ultimatefurniture.html). Their simpler shapes suit a stylized room, so they were not imported for this direction. A [CC0 tissue box by plaggy](https://sketchfab.com/3d-models/cc0-tissue-box-7816311752144a7cb3e2390743f3443d) is another candidate; the current tissue box is an original model with beveled edges, a recessed dispenser slot, and folded paper, made to fit the room.

## Layout and player area

- Patient remains seated in front of the player, with tissues on a reachable side table.
- Player has a wooden desk, open notebook, pencil, cup, and session controls above the desk surface.
- A separate player chair supplies environmental context; it is not a tracked body avatar.
- Window, curtains, plaster walls, wood trim, botanical reliefs, plants, shelf, ceiling light, and rug establish the room.
- Props are static. Grabbing tissues, writing in the notebook, and hand/body representation are subsequent interaction work.

## Rebuilding

```powershell
python tools/download-room-assets.py
& 'C:/Program Files/Blender Foundation/Blender 5.2/blender.exe' -b --python tools/prepare-room-assets.py
& 'C:/Program Files/Blender Foundation/Blender 5.2/blender.exe' -b --python tools/model-room-details.py
```

In Unity, use **Psychology VR → Rebuild furnished room**, followed by **Build Windows prototype**. Rebuilding overwrites the generated room prefab, material settings, and scene reference; save custom layout variants under a different prefab name first.

The runtime also supports `--desktop --environment-preview --capture-path <absolute.png>` for a silent environment render without starting the AI services. It writes a seated view and an overview, then exits.

## Performance and verification limits

The Windows build succeeded and the silent player check reported `ENVIRONMENT_PREVIEW_OK`. Both the seated view (`generated/furnished-room.png`) and overview (`generated/furnished-room-overview.png`) were visually inspected. The final room contains **91,197 triangles**, excluding Alex, and the replacement foliage has nonzero renderer bounds. Furniture import transforms are preserved inside placement parents so metre-scale positioning does not overwrite FBX unit conversion.

Maps are limited to 1K with mipmaps. Plants were reduced to about 18K triangles each; the notebook to about 6K. This is a first visual pass, not a target-device performance claim. Headset eye height, desk clearance, controller access, lighting, and sustained VR frame timing still require a Quest playtest. The supplied Alex model and animation clips are retained; the subsequent [facial performance pass](ALEX_PERFORMANCE.md) adds expressions, blinking, gaze, and lip sync.
