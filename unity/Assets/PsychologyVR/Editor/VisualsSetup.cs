using System.IO;
using UnityEditor;
using UnityEditor.Build;
using UnityEditor.Build.Reporting;
using UnityEngine;
using UnityEngine.Rendering;

namespace PsychologyVR.Editor
{
    [InitializeOnLoad]
    public class VisualsSetup : IPreprocessBuildWithReport
    {
        const string Path = "Assets/PsychologyVR/Resources/Visuals/ConsultationEffects.asset";
        static VisualsSetup() { EditorApplication.delayCall += EnsureProfile; }
        public int callbackOrder => -100;
        public void OnPreprocessBuild(BuildReport report) => EnsureProfile();

        public static void EnsureProfile()
        {
            if (AssetDatabase.LoadAssetAtPath<VolumeProfile>(Path)) return;
            Directory.CreateDirectory(System.IO.Path.GetDirectoryName(Path));
            var profile = ScriptableObject.CreateInstance<VolumeProfile>();
            profile.name = "ConsultationEffects";
            ConsultationVisuals.Configure(profile, 1, 1, true);
            AssetDatabase.CreateAsset(profile, Path);
            foreach (var effect in profile.components) AssetDatabase.AddObjectToAsset(effect, profile);
            EditorUtility.SetDirty(profile);
            AssetDatabase.SaveAssets();
        }

        public static void Build()
        {
            EnsureProfile();
            ProjectSetup.ConfigureAndBuild();
            Debug.Log("VISUALS_BUILD_OK");
        }
    }
}
