# Visual styles

In the game, open **Settings → Visual style**. Changes are immediate; use **View room** to close the menu and inspect the face and furniture. The choice, filter strength and soft glow preference persist across launches.

- **Original:** disables camera post-processing and retains the existing room lighting/materials/ambient occlusion.
- **Warm natural:** neutral tone mapping, slight warmth and contrast, modest exposure lift, restrained bloom.
- **Soft film** (default): ACES tone mapping, stronger contrast and less saturation. Existing saved choices remain available.
- **Clear daylight:** neutral tone mapping with cooler whites and clearer contrast.

Strength scales exposure, contrast, saturation, white balance and bloom. Tone mapping is selected per preset; at zero strength, post-processing is fully disabled. Soft glow independently switches bloom off. These filters do not change character emotion, animation or dialogue.

**Room detail: Enhanced / Original** switches the material and lighting pass independently of the colour preset. Enhanced is the default. It restores source ambient-occlusion data on the furniture, uses the supplied roughness maps for wood and plaster, increases the floor normal-map response, replaces the window fill with a shadowed spotlight, and slightly reduces uniform ambient fill. The reflection probe captures at 256 pixels per face (128 in Original), uses box projection, and refreshes only after the room setting changes. It captures layer 8, `RoomGeometry`, so people and menu panels are excluded. The toggle saves its own preference.

Original material assets are preserved. `tools/prepare-surface-maps.py` repacks existing source images into R=metallic, G=occlusion, A=smoothness; grayscale roughness-only sources receive white occlusion. `SurfaceDetailSetup.Prepare` creates alternate materials and the `RoomSurfaces` resource library. After rebuilding source room assets, rerun the map tool and `PsychologyVR.Editor.SurfaceDetailSetup.Build` to refresh alternate materials. Both paths use the existing downloaded assets.

The first room-detail pass adds one shadow view and captures the cubemap on setup or a detail toggle, rather than every frame. **Lighting and skin** now provides a separate baked-indirect-lighting and skin-material pass; see `BOUNCED_LIGHTING_AND_SKIN.md`. Ray tracing, skin subsurface scattering and geometric displacement are not implemented.

The PC quality profile now enables realtime reflection probes; it previously disabled them despite the room containing a probe. Runtime initialization also enables the setting. Both detail modes benefit from that fix. A low-intensity local fill near the window keeps its frame and curtains visible alongside the shadowed spotlight. Reflection refreshes have a bounded timeout rather than waiting indefinitely on an unsupported device.

Use `--desktop --visuals-preview --room-rendering-preview --capture-path <output-folder>` for the room-detail comparison. Keep this game window visible: Windows can skip reflection rendering in a hidden/minimized preview. The final verified captures are in `docs/generated/room-detail-visible/`. If a reflection refresh timed out while hidden, restore the window and switch Room detail to request a fresh capture.

The effects use the installed URP 17.6 volume system. `ConsultationVisuals` configures the player camera and owns its runtime profile. The saved `Resources/Visuals/ConsultationEffects.asset` retains required post-processing variants in player builds; `VisualsSetup` creates it if missing. The original room materials use URP Lit, and the existing PC renderer already provides screen-space ambient occlusion and soft shadows.

There is no motion blur, depth-of-field blur, chromatic aberration, film grain or lens distortion. Bloom uses low-quality filtering and four iterations. Unity's [URP post-processing guidance](https://docs.unity3d.com/6000.0/Documentation/Manual/urp/integration-with-post-processing.html) covers VR effects and cost. Performance and comfort still require a physical Quest 3 PCVR test; desktop captures do not establish headset frame rate.

Rebuild with `Psychology VR → Build Windows prototype`. For repeatable desktop comparison, launch the executable with `--desktop --visuals-preview --capture-path <output-folder>`. It captures all four styles, face close-ups, glow off and the settings page without starting model services or changing saved preferences.
