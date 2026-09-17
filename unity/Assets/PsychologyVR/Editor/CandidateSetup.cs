using System;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;
namespace PsychologyVR.Editor
{
    public class CandidateImporter:AssetPostprocessor
    {
        void OnPreprocessModel()
        {
            if(!assetPath.Contains("/Candidates/"))return;
            var m=(ModelImporter)assetImporter;m.importAnimation=false;m.animationType=ModelImporterAnimationType.Generic;
            m.importBlendShapes=true;m.importBlendShapeNormals=ModelImporterNormals.Calculate;m.materialImportMode=ModelImporterMaterialImportMode.ImportStandard;
        }
        void OnPreprocessTexture()
        {
            if(!assetPath.Contains("/Candidates/"))return;
            var t=(TextureImporter)assetImporter;t.maxTextureSize=2048;
            if(assetPath.Contains("_Normal"))t.textureType=TextureImporterType.NormalMap;
            if(assetPath.Contains("_RGBA"))t.alphaIsTransparency=true;
        }
    }
    public static class CandidateSetup
    {
        const string Root="Assets/PsychologyVR/Art/Characters/Candidates/Jumper";
        [MenuItem("Psychology VR/Build jumper facial audition")]
        public static void Build()
        {
            AssetDatabase.Refresh();Directory.CreateDirectory(Root+"/Materials");
            var scene=EditorSceneManager.NewScene(NewSceneSetup.EmptyScene,NewSceneMode.Single);
            var model=AssetDatabase.LoadAssetAtPath<GameObject>(Root+"/Jumper.fbx");var instance=(GameObject)PrefabUtility.InstantiatePrefab(model);
            var files=Directory.GetFiles(Root+"/textures");
            int count=0;var names=new System.Collections.Generic.HashSet<string>();
            foreach(var renderer in instance.GetComponentsInChildren<SkinnedMeshRenderer>())
            {
                count+=renderer.sharedMesh.blendShapeCount;
                for(int i=0;i<renderer.sharedMesh.blendShapeCount;i++)names.Add(renderer.sharedMesh.GetBlendShapeName(i));
                var mats=renderer.sharedMaterials;
                for(int i=0;i<mats.Length;i++)
                {
                    string n=mats[i].name,prefix=n.Replace(".001","");
                    string suffix=n.EndsWith(".001")?"_0001":"";
                    string rgba=files.FirstOrDefault(f=>Path.GetFileNameWithoutExtension(f)==prefix+"_RGBA"+suffix);
                    string diffuse=rgba??files.FirstOrDefault(f=>Path.GetFileNameWithoutExtension(f)==prefix+"_Diffuse"+suffix);
                    string normal=files.FirstOrDefault(f=>Path.GetFileNameWithoutExtension(f)==prefix+"_Normal");
                    string path=Root+"/Materials/"+n+".mat";
                    var mat=AssetDatabase.LoadAssetAtPath<Material>(path);if(!mat){mat=new Material(Shader.Find("Universal Render Pipeline/Lit"));AssetDatabase.CreateAsset(mat,path);}
                    mat.SetColor("_BaseColor",Color.white);mat.SetFloat("_Smoothness",n.Contains("Eye")||n.Contains("Cornea")?.6f:.25f);mat.SetFloat("_Cull",0);
                    if(diffuse!=null)mat.SetTexture("_BaseMap",AssetDatabase.LoadAssetAtPath<Texture2D>(diffuse.Replace('\\','/')));
                    if(normal!=null){mat.SetTexture("_BumpMap",AssetDatabase.LoadAssetAtPath<Texture2D>(normal.Replace('\\','/')));mat.SetFloat("_BumpScale",.5f);mat.EnableKeyword("_NORMALMAP");}
                    if(rgba!=null)
                    {
                        bool film=n.Contains("Cornea")||n.Contains("Occlusion")||n.Contains("Tearline");
                        if(film){mat.SetFloat("_Surface",1);mat.SetFloat("_SrcBlend",5);mat.SetFloat("_DstBlend",10);mat.SetFloat("_ZWrite",0);mat.EnableKeyword("_SURFACE_TYPE_TRANSPARENT");mat.renderQueue=3000;}
                        else{mat.SetFloat("_AlphaClip",1);mat.SetFloat("_Cutoff",.35f);mat.EnableKeyword("_ALPHATEST_ON");mat.renderQueue=2450;}
                    }
                    EditorUtility.SetDirty(mat);mats[i]=mat;
                }
                renderer.sharedMaterials=mats;
            }
            PrefabUtility.SaveAsPrefabAsset(instance,"Assets/PsychologyVR/Prefabs/JumperCandidate.prefab");
            var go=new GameObject("Facial rig audition");var demo=go.AddComponent<CandidateExpressionPreview>();demo.character=instance;
            var cam=new GameObject("Audition camera").AddComponent<Camera>();cam.nearClipPlane=.03f;cam.clearFlags=CameraClearFlags.SolidColor;cam.backgroundColor=new Color(.11f,.14f,.15f);demo.view=cam;
            RenderSettings.ambientMode=AmbientMode.Flat;RenderSettings.ambientLight=new Color(.48f,.48f,.48f);
            var key=new GameObject("Key").AddComponent<Light>();key.type=LightType.Directional;key.intensity=1.5f;key.transform.rotation=Quaternion.Euler(30,-25,0);
            var fill=new GameObject("Fill").AddComponent<Light>();fill.type=LightType.Directional;fill.intensity=.65f;fill.transform.rotation=Quaternion.Euler(20,145,0);
            string scenePath="Assets/PsychologyVR/Scenes/JumperFacialAudition.unity";EditorSceneManager.SaveScene(scene,scenePath);AssetDatabase.SaveAssets();
            File.WriteAllText("../docs/generated/candidate-unity-import.json",JsonUtility.ToJson(new ImportReport{bindings=count,shapes=names.ToArray()},true));
            if(count<700)throw new Exception("Candidate facial shapes did not survive import: "+count);
            var result=BuildPipeline.BuildPlayer(new BuildPlayerOptions{scenes=new[]{scenePath},locationPathName="Builds/CandidatePreview/JumperPreview.exe",target=BuildTarget.StandaloneWindows64,options=BuildOptions.Development});
            if(result.summary.result!=UnityEditor.Build.Reporting.BuildResult.Succeeded)throw new Exception("Candidate build failed");
            Debug.Log("CANDIDATE_BUILD_OK "+count);
        }
        [Serializable] class ImportReport{public int bindings;public string[] shapes;}
    }
}
