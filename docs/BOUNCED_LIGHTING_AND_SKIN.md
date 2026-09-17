# Bounced lighting and skin shading

The consultation loads `ConsultationLighting.unity` additively before creating its camera, character and menu. That scene contains the furnished room and its baked lighting data. Startup makes it the active scene before reading probes, then retetrahedralizes them. Without that active-scene switch, Unity 6000.6 exposed the empty bootstrap scene's probe set instead. The original prefab remains the fallback if the lighting scene is unavailable.

The existing lights use Unity Baked Indirect mixed lighting: their direct illumination and shadows remain realtime, while indirect light is precomputed in a directional lightmap and 180 light probes. A separate broad rectangular window emitter is fully baked, supplying soft daylight that the opaque window artwork cannot transmit. The room bake uses four bounces, 16 texels per metre and 256 indirect samples. Thin foliage, stems and the ceiling lamp receive baked lighting from probes because their imported secondary UVs are degenerate. Other static room surfaces use the lightmap. The animated character and player use interpolated probes. See Unity's [mixed lighting modes](https://docs.unity3d.com/6000.0/Documentation/ScriptReference/MixedLightingMode.html) for the distinction between direct and indirect contributions.

In **Settings → Visual style → Lighting and skin**, Bounced lighting and Skin shading have independent persistent switches. Bounced lighting requires Enhanced room detail. Disabling it removes lightmap indices and probe usage for comparison with the previous ambient fill. The approximate window-bounce fill from the previous pass is disabled when baked indirect lighting is active. Real room reflections are refreshed after toggling.

The natural skin option affects the supplied jumper's head, arms, torso and legs, including matching player-avatar skin materials. It preserves the original diffuse/normal textures, facial blendshapes, per-face redness property block and tear geometry. Alternate URP Lit materials use a specular workflow with lower dielectric reflectance, restrained smoothness variation derived from existing normal-map detail, and slightly stronger normal mapping. This is an authored roughness treatment, not a measured roughness scan or subsurface-scattering shader. Hair, eyes, mouth and clothes retain their existing materials; the original Alex model's unrelated materials are unchanged.

Reproduction:

1. Run `tools/prepare-skin-shading.py` with Python, Pillow and NumPy.
2. Execute `PsychologyVR.Editor.BounceLightingSetup.Bake` in Unity batch mode to regenerate the lighting scene. The bake keeps original room materials/light parameters serialized for runtime comparisons, after using enhanced materials during precomputation.
3. Execute `PsychologyVR.Editor.SkinDetailSetup.Build` to create alternate skin materials and build both scenes.
4. Run the game visibly with `--desktop --visuals-preview --lighting-skin-preview --capture-path <folder>` for comparison captures and assertions. Keep the window visible so Unity processes realtime reflection refreshes.

Moving or replacing room furniture requires rebaking. Quest stereo rendering, comfort and sustained frame rate still require hardware verification.
