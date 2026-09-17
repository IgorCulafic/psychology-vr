using System;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEditor.XR.Management;
using UnityEditor.XR.Management.Metadata;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.XR.Management;
using UnityEngine.XR.OpenXR;
using UnityEngine.XR.OpenXR.Features.Interactions;

namespace PsychologyVR.Editor
{
    public class CharacterImporter : AssetPostprocessor
    {
        void OnPreprocessModel()
        {
            if(!assetPath.EndsWith("/Alex.fbx")) return;
            var importer=(ModelImporter)assetImporter;
            importer.animationType=ModelImporterAnimationType.Legacy;
            importer.importAnimation=true;
            importer.importBlendShapes=true;
            importer.importBlendShapeNormals=ModelImporterNormals.Calculate;
            importer.materialImportMode=ModelImporterMaterialImportMode.ImportStandard;
            importer.useFileScale=true;
        }

        void OnPostprocessMaterial(Material material)
        {
            if(!assetPath.EndsWith("/Alex.fbx")) return;
            Texture texture=material.mainTexture;
            material.shader=Shader.Find("Universal Render Pipeline/Lit");
            if(texture) material.SetTexture("_BaseMap",texture);
            material.SetFloat("_Smoothness",.2f);
            material.SetFloat("_Cull",0);
        }
    }

    public static class ProjectSetup
    {
        const string Root="Assets/PsychologyVR";
        const string Model=Root+"/Art/Characters/Alex/Alex.fbx";
        const string Scene=Root+"/Scenes/Consultation.unity";

        [MenuItem("Psychology VR/Create prototype scene")]
        public static void CreatePrototype()
        {
            Directory.CreateDirectory(Root+"/Resources");
            string tearPath=Root+"/Resources/AlexTearFilm.mat";
            var tear=AssetDatabase.LoadAssetAtPath<Material>(tearPath);
            if(!tear){tear=new Material(Shader.Find("Universal Render Pipeline/Lit"));AssetDatabase.CreateAsset(tear,tearPath);}
            tear.SetFloat("_Surface",1);tear.SetFloat("_SrcBlend",(float)BlendMode.SrcAlpha);tear.SetFloat("_DstBlend",(float)BlendMode.OneMinusSrcAlpha);
            tear.SetFloat("_ZWrite",0);tear.SetFloat("_Cull",0);tear.SetFloat("_Smoothness",.98f);
            tear.SetColor("_BaseColor",new Color(.68f,.8f,.88f,.48f));tear.EnableKeyword("_SURFACE_TYPE_TRANSPARENT");tear.renderQueue=3000;
            EditorUtility.SetDirty(tear);
            Directory.CreateDirectory(Root+"/Scenes"); Directory.CreateDirectory(Root+"/Settings");
            Directory.CreateDirectory(Root+"/Art/Materials"); Directory.CreateDirectory(Root+"/Prefabs");
            AssetDatabase.Refresh();
            var model=AssetDatabase.LoadAssetAtPath<GameObject>(Model);
            if(!model) throw new InvalidOperationException("The converted Alex.fbx was not imported.");
            var instance=(GameObject)PrefabUtility.InstantiatePrefab(model);
            // Explicit mapping retains the original glTF base-color assignments.
            string[] names={"Skin","Teeth","Body","Outfit_Bottom","Outfit_Footwear","Outfit_Top","Hair","Glasses","Eye"};
            string[] images={"Image_1","Image_2","Image_4","Image_5","Image_8","Image_11","Image_14","Image_16","Image_0"};
            foreach(var renderer in instance.GetComponentsInChildren<Renderer>())
            {
                var mats=renderer.sharedMaterials;
                for(int j=0;j<mats.Length;j++)
                {
                    string source=mats[j]?mats[j].name:"";
                    for(int i=0;i<names.Length;i++) if(source.StartsWith("Wolf3D_"+names[i]+"."))
                    {
                        string path=Root+"/Art/Materials/Alex_"+names[i]+".mat";
                        var mat=AssetDatabase.LoadAssetAtPath<Material>(path);
                        if(!mat) { mat=new Material(Shader.Find("Universal Render Pipeline/Lit")); AssetDatabase.CreateAsset(mat,path); }
                        mat.SetTexture("_BaseMap",AssetDatabase.LoadAssetAtPath<Texture2D>(Root+"/Art/Characters/Alex/"+images[i]+".png"));
                        mat.SetColor("_BaseColor",Color.white); mat.SetFloat("_Smoothness",.2f); mat.SetFloat("_Cull",0);
                        EditorUtility.SetDirty(mat); mats[j]=mat; break;
                    }
                }
                renderer.sharedMaterials=mats;
            }
            var originalAnimation=instance.GetComponent<Animation>(); if(originalAnimation) UnityEngine.Object.DestroyImmediate(originalAnimation);
            var prefab=PrefabUtility.SaveAsPrefabAsset(instance,Root+"/Prefabs/Alex.prefab"); UnityEngine.Object.DestroyImmediate(instance);
            var clips=AssetDatabase.LoadAllAssetsAtPath(Model).OfType<AnimationClip>().Where(c=>!c.name.StartsWith("__preview__")).ToArray();
            var sit=clips.FirstOrDefault(c=>c.name.ToLowerInvariant().EndsWith("sit"));
            if(!sit) throw new InvalidOperationException("No sit clip found. Clips: "+string.Join(", ",clips.Select(c=>c.name)));
            var scene=EditorSceneManager.NewScene(NewSceneSetup.EmptyScene,NewSceneMode.Single);
            var root=new GameObject("Psychology VR"); var session=root.AddComponent<PrototypeSession>();
            session.characterPrefab=prefab; session.seatedClip=sit;
            var jumper=AssetDatabase.LoadAssetAtPath<GameObject>(Root+"/Prefabs/JumperCandidate.prefab");
            if(jumper){session.characterPrefab=jumper;session.seatedClip=null;}
            session.playerPrefab=AssetDatabase.LoadAssetAtPath<GameObject>(Root+"/Prefabs/SeatedPlayer.prefab");
            MenuSetup.AssignAppearances(session);
            session.environmentPrefab=AssetDatabase.LoadAssetAtPath<GameObject>(Root+"/Prefabs/ConsultationRoom.prefab");
            EditorSceneManager.SaveScene(scene,Scene);
            EditorBuildSettings.scenes=File.Exists(BounceLightingSetup.ScenePath)
                ?new[]{new EditorBuildSettingsScene(Scene,true),new EditorBuildSettingsScene(BounceLightingSetup.ScenePath,true)}
                :new[]{new EditorBuildSettingsScene(Scene,true)};
            PlayerSettings.companyName="Psychology VR"; PlayerSettings.productName="Alex - Conversation Prototype";
            PlayerSettings.defaultScreenWidth=1440; PlayerSettings.defaultScreenHeight=900;
            PlayerSettings.fullScreenMode=FullScreenMode.Windowed;
            PlayerSettings.runInBackground=true;
            PlayerSettings.colorSpace=ColorSpace.Linear;
            GraphicsSettings.defaultRenderPipeline=AssetDatabase.LoadAssetAtPath<UnityEngine.Rendering.Universal.UniversalRenderPipelineAsset>("Assets/Settings/PC_RPAsset.asset");
            QualitySettings.renderPipeline=GraphicsSettings.defaultRenderPipeline;
            ConfigureXR();
            AssetDatabase.SaveAssets();
            Directory.CreateDirectory("../docs/generated");
            File.WriteAllText("../docs/generated/unity-import.txt", "Unity "+Application.unityVersion+"\nClips: "+string.Join(", ",clips.Select(c=>c.name))+"\nSeated: "+sit.name+"\n");
            Debug.Log("PSYCHOLOGY_VR_SETUP_OK");
        }

        static void ConfigureXR()
        {
            string path=Root+"/Settings/XRGeneralSettings.asset";
            var perTarget=AssetDatabase.LoadAssetAtPath<XRGeneralSettingsPerBuildTarget>(path);
            if(!perTarget) { perTarget=ScriptableObject.CreateInstance<XRGeneralSettingsPerBuildTarget>(); AssetDatabase.CreateAsset(perTarget,path); }
            EditorBuildSettings.AddConfigObject(XRGeneralSettings.k_SettingsKey,perTarget,true);
            if(!perTarget.HasSettingsForBuildTarget(BuildTargetGroup.Standalone)) perTarget.CreateDefaultSettingsForBuildTarget(BuildTargetGroup.Standalone);
            if(!perTarget.HasManagerSettingsForBuildTarget(BuildTargetGroup.Standalone)) perTarget.CreateDefaultManagerSettingsForBuildTarget(BuildTargetGroup.Standalone);
            var settings=perTarget.SettingsForBuildTarget(BuildTargetGroup.Standalone);
            // Runtime starts XR explicitly, allowing --desktop to skip initialization.
            settings.InitManagerOnStart=false;
            if(!XRPackageMetadataStore.AssignLoader(settings.Manager,"UnityEngine.XR.OpenXR.OpenXRLoader",BuildTargetGroup.Standalone))
                throw new InvalidOperationException("Could not assign the OpenXR loader.");
            var openxr=OpenXRSettings.GetSettingsForBuildTargetGroup(BuildTargetGroup.Standalone);
            if(openxr)
            {
                var touch=openxr.GetFeature<OculusTouchControllerProfile>(); if(touch) touch.enabled=true;
                EditorUtility.SetDirty(openxr);
            }
            EditorUtility.SetDirty(settings); EditorUtility.SetDirty(perTarget);
        }

        [MenuItem("Psychology VR/Build Windows prototype")]
        public static void BuildWindows()
        {
            MenuSetup.SyncCatalog();
            if(!File.Exists(Scene)) CreatePrototype();
            var report=BuildPipeline.BuildPlayer(new BuildPlayerOptions {
                scenes=File.Exists(BounceLightingSetup.ScenePath)?new[]{Scene,BounceLightingSetup.ScenePath}:new[]{Scene},locationPathName="Builds/Windows/AlexPrototype.exe",
                target=BuildTarget.StandaloneWindows64,options=BuildOptions.Development});
            if(report.summary.result!=UnityEditor.Build.Reporting.BuildResult.Succeeded)
                throw new InvalidOperationException("Build failed: "+report.summary.result);
            Debug.Log("PSYCHOLOGY_VR_BUILD_OK");
        }

        public static void BuildAndPreview()
        {
            CapturePreview();
            EditorSceneManager.OpenScene(Scene);
            BuildWindows();
        }

        public static void ConfigureAndBuild()
        {
            ConfigureXR();
            GraphicsSettings.defaultRenderPipeline=AssetDatabase.LoadAssetAtPath<UnityEngine.Rendering.Universal.UniversalRenderPipelineAsset>("Assets/Settings/PC_RPAsset.asset");
            QualitySettings.renderPipeline=GraphicsSettings.defaultRenderPipeline;
            AssetDatabase.SaveAssets();
            BuildWindows();
        }

        public static void BuildAlex()
        {
            CreatePrototype();
            var meshes=AssetDatabase.LoadAllAssetsAtPath(Model).OfType<Mesh>().ToArray();
            var report=string.Join("\n",meshes.Select(m=>m.name+": "+string.Join(", ",Enumerable.Range(0,m.blendShapeCount).Select(m.GetBlendShapeName))));
            File.WriteAllText("../docs/generated/unity-facial-import.txt",report);
            if(meshes.Sum(m=>m.blendShapeCount)<27) throw new InvalidOperationException("Alex facial shapes did not survive import.");
            var shapes=meshes.SelectMany(m=>Enumerable.Range(0,m.blendShapeCount).Select(m.GetBlendShapeName)).ToArray();
            foreach(var emotion in EmotionLibrary.Catalog.emotions)foreach(var shape in emotion.shapes)
                if(!shapes.Any(n=>n.EndsWith(shape.name,StringComparison.Ordinal)))throw new InvalidOperationException("Missing facial control: "+shape.name);
            ConfigureAndBuild();
        }

        [MenuItem("Psychology VR/Capture room preview")]
        public static void CapturePreview()
        {
            EditorSceneManager.OpenScene(Scene);
            var session=UnityEngine.Object.FindFirstObjectByType<PrototypeSession>();
            // Exercise the exact runtime room and actor creation without networking.
            var room=new GameObject("Preview room"); PrototypeRoom.Build(room.transform);
            var actor=UnityEngine.Object.Instantiate(session.characterPrefab,new Vector3(0,0,1.15f),Quaternion.Euler(0,180,0));
            if(session.seatedClip)session.seatedClip.SampleAnimation(actor,session.seatedClip.length*.5f);else CandidateSeatedPose.Apply(actor);
            var cam=new GameObject("Preview camera").AddComponent<Camera>();
            cam.transform.position=new Vector3(.7f,1.25f,-2.3f); cam.transform.LookAt(new Vector3(0,.95f,1.15f));
            cam.nearClipPlane=.05f; cam.fieldOfView=55; cam.clearFlags=CameraClearFlags.SolidColor; cam.backgroundColor=new Color(.25f,.3f,.3f);
            var target=new RenderTexture(1440,900,24); cam.targetTexture=target;
            RenderPipeline.SubmitRenderRequest(cam,new UnityEngine.Rendering.Universal.UniversalRenderPipeline.SingleCameraRequest{destination=target});
            RenderTexture.active=target;
            var image=new Texture2D(1440,900,TextureFormat.RGB24,false); image.ReadPixels(new Rect(0,0,1440,900),0,0); image.Apply();
            File.WriteAllBytes("../docs/generated/unity-room-preview.png",image.EncodeToPNG());
            cam.targetTexture=null; RenderTexture.active=null; target.Release();
            UnityEngine.Object.DestroyImmediate(image); UnityEngine.Object.DestroyImmediate(target);
            UnityEngine.Object.DestroyImmediate(room); UnityEngine.Object.DestroyImmediate(actor); UnityEngine.Object.DestroyImmediate(cam.gameObject);
            // Do not save temporary preview objects into the playable scene.
            Debug.Log("PSYCHOLOGY_VR_PREVIEW_OK");
        }
    }
}
