using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;

namespace PsychologyVR
{
    public class ConsultationVisuals : MonoBehaviour
    {
        public static readonly string[] Names = { "Original", "Warm natural", "Soft film", "Clear daylight" };
        public static readonly string[] Descriptions = {
            "The original room lighting and colours, with filters off.",
            "Warm wood, gentle contrast and soft highlights. A welcoming consultation room.",
            "Richer shadows and restrained colour, with a softer highlight roll-off.",
            "Cooler whites and clearer contrast for a fresh daytime feel."
        };
        public int Preset { get; private set; }
        public float Strength { get; private set; }
        public bool Glow { get; private set; }
        Volume volume;
        VolumeProfile ownedProfile;
        UniversalAdditionalCameraData cameraData;

        public void Initialize(Camera camera)
        {
            camera.allowHDR = true;
            cameraData = camera.GetUniversalAdditionalCameraData();
            cameraData.volumeLayerMask = 1; // Default layer, separate from the menu's UI layer.
            cameraData.volumeTrigger = camera.transform;
            camera.SetVolumeFrameworkUpdateMode(VolumeFrameworkUpdateMode.EveryFrame);
            var obj = new GameObject("Consultation colour and highlights");
            obj.transform.SetParent(transform, false);
            volume = obj.AddComponent<Volume>();
            volume.isGlobal = true;
            volume.priority = 20;
            var source = Resources.Load<VolumeProfile>("Visuals/ConsultationEffects");
            if (source) { volume.sharedProfile = source; ownedProfile = volume.profile; }
            else { ownedProfile = ScriptableObject.CreateInstance<VolumeProfile>(); volume.profile = ownedProfile; }
            Select(PlayerPrefs.GetInt("VisualPreset", 2), PlayerPrefs.GetFloat("VisualStrength", 1), PlayerPrefs.GetInt("VisualGlow", 1) == 1, false);
        }

        public void Select(int preset, float strength, bool glow, bool save = true)
        {
            Preset = Mathf.Clamp(preset, 0, Names.Length - 1);
            Strength = Mathf.Clamp01(strength);
            Glow = glow;
            Configure(ownedProfile, Preset, Strength, Glow);
            cameraData.renderPostProcessing = Preset != 0 && Strength > 0;
            if (!save) return;
            PlayerPrefs.SetInt("VisualPreset", Preset);
            PlayerPrefs.SetFloat("VisualStrength", Strength);
            PlayerPrefs.SetInt("VisualGlow", Glow ? 1 : 0);
            PlayerPrefs.Save();
        }

        static T Effect<T>(VolumeProfile profile) where T : VolumeComponent
        {
            return profile.TryGet<T>(out var effect) ? effect : profile.Add<T>(true);
        }

        // Also used to create the saved profile so player builds retain these effect shaders.
        public static void Configure(VolumeProfile profile, int preset, float strength, bool glow)
        {
            float amount = preset == 0 ? 0 : Mathf.Clamp01(strength);
            var tone = Effect<Tonemapping>(profile);
            tone.mode.Override(amount == 0 ? TonemappingMode.None : preset == 2 ? TonemappingMode.ACES : TonemappingMode.Neutral);
            var colour = Effect<ColorAdjustments>(profile);
            colour.postExposure.Override((preset == 2 ? .30f : preset == 3 ? .08f : .12f) * amount);
            colour.contrast.Override((preset == 2 ? 12 : preset == 3 ? 8 : 5) * amount);
            colour.saturation.Override((preset == 2 ? -9 : preset == 3 ? -2 : 3) * amount);
            colour.colorFilter.Override(Color.white);
            var balance = Effect<WhiteBalance>(profile);
            balance.temperature.Override((preset == 3 ? -7 : preset == 2 ? 3 : 7) * amount);
            balance.tint.Override(1 * amount);
            var bloom = Effect<Bloom>(profile);
            bloom.intensity.Override(glow ? (preset == 2 ? .16f : .10f) * amount : 0);
            bloom.threshold.Override(1.15f);
            bloom.scatter.Override(.55f);
            bloom.highQualityFiltering.Override(false);
            bloom.maxIterations.Override(4);
        }

        void OnDestroy()
        {
            if (!ownedProfile) return;
            foreach (var component in ownedProfile.components) if (component) Destroy(component);
            Destroy(ownedProfile);
        }
    }
}
