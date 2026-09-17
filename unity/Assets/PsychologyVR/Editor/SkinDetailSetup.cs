using System.Collections.Generic;
using UnityEditor;
using UnityEngine;

namespace PsychologyVR.Editor
{
    public static class SkinDetailSetup
    {
        public static void Prepare()
        {
            const string source="Assets/PsychologyVR/Art/Characters/Candidates/Jumper/Materials/";
            const string target="Assets/PsychologyVR/Art/Characters/SkinDetail/";
            AssetDatabase.Refresh();var entries=new List<RoomSurfaceLibrary.Entry>();
            foreach(var part in new[]{"Head","Body","Arm","Leg"})
            {
                string name="Std_Skin_"+part,path=target+name+"_spec_smooth.png";
                var importer=(TextureImporter)AssetImporter.GetAtPath(path);
                importer.sRGBTexture=false;importer.alphaSource=TextureImporterAlphaSource.FromInput;importer.alphaIsTransparency=false;
                importer.maxTextureSize=1024;importer.mipmapEnabled=true;importer.SaveAndReimport();
                var original=AssetDatabase.LoadAssetAtPath<Material>(source+name+".mat");
                var material=AssetDatabase.LoadAssetAtPath<Material>(target+name+".mat");
                if(!material){material=new Material(original);AssetDatabase.CreateAsset(material,target+name+".mat");}else material.CopyPropertiesFromMaterial(original);
                material.SetFloat("_WorkflowMode",0);material.EnableKeyword("_SPECULAR_SETUP");material.EnableKeyword("_METALLICSPECGLOSSMAP");
                material.SetTexture("_SpecGlossMap",AssetDatabase.LoadAssetAtPath<Texture2D>(path));material.SetFloat("_Smoothness",1);
                material.SetFloat("_BumpScale",.7f);material.SetFloat("_SmoothnessTextureChannel",0);
                EditorUtility.SetDirty(material);entries.Add(new RoomSurfaceLibrary.Entry{original=original,enhanced=material});
            }
            const string libraryPath="Assets/PsychologyVR/Resources/Visuals/SkinSurfaces.asset";
            var library=AssetDatabase.LoadAssetAtPath<RoomSurfaceLibrary>(libraryPath);
            if(!library){library=ScriptableObject.CreateInstance<RoomSurfaceLibrary>();AssetDatabase.CreateAsset(library,libraryPath);}
            library.entries=entries.ToArray();EditorUtility.SetDirty(library);AssetDatabase.SaveAssets();
        }
        public static void Build()
        {
            Prepare();
            var scene=UnityEditor.SceneManagement.EditorSceneManager.OpenScene(BounceLightingSetup.ScenePath);
            var probes=LightProbes.GetSharedLightProbesForScene(scene);
            Debug.Log("BOUNCE_RELOAD lightmaps="+LightmapSettings.lightmaps.Length+" probes="+(LightmapSettings.lightProbes?LightmapSettings.lightProbes.count:0)+" sceneProbes="+(probes?probes.countSelf:0));
            if(LightmapSettings.lightmaps.Length==0||!probes||probes.countSelf==0)
                throw new System.InvalidOperationException("Bake the consultation lighting before building this graphics pass.");
            ProjectSetup.ConfigureAndBuild();Debug.Log("LIGHTING_SKIN_BUILD_OK");
        }
    }
}
