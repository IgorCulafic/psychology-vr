# Four-character MetaHuman audition

The cast mapping is `cast.json`. The model choices are initial appearances for
review, independent of the characters' fictional biographies:

| Character | Scenario | Epic preset | Voice |
|---|---|---|---|
| Ivan | Burnout | Bruce | Igor |
| Stefan | Fire | Mateo | Person 1 |
| Nikola | Bereavement | Victor | Person 2 |
| Alex | Earthquake | Dominic (existing AuditionMale) | Person 3 |

Ivan uses the distinct Bruce preset at the user's request.
The replacement has its own face, body, skin materials and facial rig; its
authoring asset is `IvanBruce`, with animation packages under `ivan-bruce`.
The previous Mikel authoring asset is preserved. Igor remains Ivan's voice.

The replacement's 846 facial/neck joints and all twenty moving speech/expression
poses passed `tools/validate-metahuman-poses.py ivan`. Its original exports were
archived under `exports/unity/archive/ivan-mikel`. To rebuild a replacement,
use `tools/run-metahuman-ivan-replacement.ps1` after assembling the cast.

`voices/cast.json` remains the production voice mapping. This audition uses the
same approved Person 3 speech across all models to isolate the facial transfer;
it does not replace the production voice assignments.

## Authoring and verification

Use the normal Unreal Editor with `-ExecutePythonScript`, one stage at a time:

1. `tools/metahuman-cast-assemble.py`: duplicate installed Epic presets into
   project character assets, request their own rigs/textures, assemble Optimized
   High, and check that each Blueprint compiles. Existing assemblies are reused.
2. `tools/metahuman-cast-prepare.py`: export each solved facial performance
   onto each identity's Control Rig. Restart before editing exported channels.
3. `tools/metahuman-speaking-build.py -mhCast`: bake speech and recorded emotion
   onto each identity's own face/body meshes. Fear and crying preserve speech
   mouth controls; anger uses the stronger, provisionally accepted mouth blend.
4. `tools/metahuman-cast-frame.py`: center the cameras using each identity's
   lower-eyelid height; save explicit camera transform tracks for playback.
5. `tools/metahuman-audition-render.py -mhCast`: render the nine new clips.
6. `tools/package-metahuman-cast.py`: encode and decode-check twelve review
   clips, including the three existing Alex clips.

The review URL is `http://127.0.0.1:8798/metahuman-cast/`.
Detailed results are generated in `cast/`, including assembly, preparation,
baking and rendering reports. The packaged review contains `verification.json`.

Native models are in `Content/MetaHumans/<identity>` with shared assets in
`Content/MetaHumans/Common`. Editable sequences and identity-specific baked
face/body AnimSequences are in `Content/Audition/Cast/<character>/<emotion>`.
These generated files remain local, as do the existing MetaHuman assets.

## Scope

The Unity port now assembles all four identities from exported meshes and baked
facial joints. Each scenario selects its own appearance and retains the voice
mapping above. Unity loads the selected prefab through Resources and releases
unused assets after a switch. Older appearances remain in the appearance picker.

The new runtime uses recorded fear, crying and anger clips with neck movement;
other emotions and live speech use twenty identity-specific joint poses. Speech
uses the existing audio-clock phonemes, while the recorded upper face continues.
Reaction loops fade at their boundaries and changes are smoothed. Tears use skin
surface anchors. Seated body and resting hands are a static starting pose;
torso and hand acting remain deferred.

This is a URP material conversion, not Unreal's renderer. Portable hair cards
replace exported grooms; missing card versions (some stubble and strand
eyelashes) are not reproduced. Animated wrinkle materials and Unreal skin
scattering are not yet ported. Desktop checks do not establish Quest frame rate
or the combined GPU budget with inference. Test that separately on the 4090.

## Unity reproduction and checks

1. Run `tools/run-metahuman-unity-export.ps1` with Unreal 5.8 installed. It exports
   meshes/material inputs and bakes each identity separately. The final reports
   in `exports/unity` must say `exported`.
2. Run `tools/audit-metahuman-hair-uv.py` in Blender. Exported card meshes differ
   in UV ordering; the audit chooses their texture UV instead of lightmap UV.
3. Run `tools/stage-metahuman-unity.py` and `tools/stage-metahuman-voice-check.py`
   with the local Python environment. These retain original sources and stage
   portable assets plus the already-approved assigned speech auditions.
4. Run `tools/build-metahuman-clothes.py` in Blender to derive full-length trousers
   from the supplied garments and add simple shoes. The source FBXs stay intact.
5. In Unity, execute `PsychologyVR.Editor.MetaHumanSetup.BuildAll`. This creates
   identity-specific pose libraries, fits facial hair in the original bind pose,
   builds the isolated preview and updates/builds the consultation scene.

Builds are `unity/Builds/MetaHumanPreview/MetaHumanPreview.exe` and
`unity/Builds/Windows/AlexPrototype.exe`. The preview has emotion buttons and
assigned-voice playback. `--capture` writes its visual checks to `unity-review`.
`--outfit-check` writes seated clothing stills to `outfit-review`. `--movies`
records normal-speed, 30 fps frames to `unity-movies`: four seconds of the outfit,
five of fear, six of crying, then the complete approved angry spoken line. Run
`tools/package-metahuman-unity-movies.py` to encode the MP4s and local review page.
The movie capture explicitly advances the speech preview clock; production
conversations continue to follow the real AudioSource clock. Audio is muxed from
the byte-verified approved WAV at exactly 15 seconds, without new synthesis.

Casual clothing uses individual shirt colours, dark trousers and simple laced
shoes. Covered leg geometry is removed in derived meshes to prevent skin poking
through the trousers. This is skinned clothing without cloth simulation.

For the room check, run the consultation executable with `--desktop
--metahuman-check --capture-path <absolute-output-directory>`. This checks all four
seated characters, facial control bindings, jaw movement and tear anchors without
starting inference or recording a student session. Normal launch still connects
to the existing local conversation service.

On 4 October 2026, all four consultation scenarios passed the desktop check:
846 facial/neck bindings and 72 valid tear anchors each, with a moving jaw after
the expression smoothing settled. All twenty speech/expression poses per identity
were checked for finite, normalized and non-static data. The assigned audition
audio was byte-checked against the approved sources. Results are recorded in
`exports/unity/validation.json`. Live inference and headset performance were not
rerun during this port; the offline check uses the existing speech playback path.

The anger blend was accepted as serviceable on 4 October 2026; fuller angry
acting can be refined later without blocking cast preparation.
