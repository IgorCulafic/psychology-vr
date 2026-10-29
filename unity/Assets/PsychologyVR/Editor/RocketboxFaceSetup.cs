using System;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;

namespace PsychologyVR.Editor
{
    public static class RocketboxFaceSetup
    {
        const string Root="Assets/PsychologyVR/Generated/LiveLink/Rocketbox";
        public static void Build()
        {
            Directory.CreateDirectory(Root); AssetDatabase.Refresh();
            for(int n=1;n<=4;n++)
            {
                string name="Male_Adult_"+n.ToString("D2");
                string original=Path.GetFullPath("../Assets/CharacterCandidates/Microsoft-Rocketbox/Assets/Avatars/Adults/"+name);
                string dest=Root+"/"+name; Directory.CreateDirectory(dest);
                File.Copy(original+"/Export/"+name+"_facial.fbx",dest+"/"+name+".fbx",true);
                foreach(string file in Directory.GetFiles(original+"/Textures","*.tga")) File.Copy(file,dest+"/"+Path.GetFileName(file),true);
            }
            AssetDatabase.Refresh();
            var scene=EditorSceneManager.NewScene(NewSceneSetup.EmptyScene,NewSceneMode.Single);
            var preview=new GameObject("Rocketbox candidate comparison").AddComponent<RocketboxFacePreview>();
            preview.candidates=new GameObject[4];
            for(int n=1;n<=4;n++)
            {
                string name="Male_Adult_"+n.ToString("D2"), dest=Root+"/"+name;
                var importer=(ModelImporter)AssetImporter.GetAtPath(dest+"/"+name+".fbx");
                importer.importBlendShapes=true; importer.importAnimation=false; importer.animationType=ModelImporterAnimationType.Generic;
                importer.SaveAndReimport();
                var model=AssetDatabase.LoadAssetAtPath<GameObject>(dest+"/"+name+".fbx");
                var actor=(GameObject)PrefabUtility.InstantiatePrefab(model);
                preview.candidates[n-1]=actor;
                foreach(var mesh in actor.GetComponentsInChildren<SkinnedMeshRenderer>())
                {
                    var materials=mesh.sharedMaterials;
                    for(int m=0;m<materials.Length;m++)
                    {
                        string old=materials[m]?materials[m].name:"unknown";
                        Debug.Log("ROCKETBOX_MATERIAL "+name+" "+m+" "+old);
                        string part=old.ToLowerInvariant().Contains("head")?"head":old.ToLowerInvariant().Contains("body")?"body":"opacity";
                        string color=Directory.GetFiles(dest,"*"+part+"_color.tga").Single();
                        var mat=new Material(Shader.Find("Universal Render Pipeline/Lit"));
                        mat.name=name+"_"+part;
                        mat.SetTexture("_BaseMap",AssetDatabase.LoadAssetAtPath<Texture2D>(color));
                        mat.SetColor("_BaseColor",Color.white); mat.SetFloat("_Smoothness",.25f);
                        string normal=Directory.GetFiles(dest,"*"+part+"_normal.tga").FirstOrDefault();
                        if(normal!=null)
                        {
                            var ti=(TextureImporter)AssetImporter.GetAtPath(normal); ti.textureType=TextureImporterType.NormalMap; ti.SaveAndReimport();
                            mat.SetTexture("_BumpMap",AssetDatabase.LoadAssetAtPath<Texture2D>(normal)); mat.EnableKeyword("_NORMALMAP");
                        }
                        if(part=="opacity")
                        {
                            var ti=(TextureImporter)AssetImporter.GetAtPath(color);
                            ti.alphaIsTransparency=true; ti.SaveAndReimport();
                            mat.SetFloat("_Surface",1); mat.SetFloat("_AlphaClip",0);
                            mat.SetFloat("_SrcBlend",(float)BlendMode.SrcAlpha);
                            mat.SetFloat("_DstBlend",(float)BlendMode.OneMinusSrcAlpha);
                            mat.SetFloat("_SrcBlendAlpha",(float)BlendMode.One);
                            mat.SetFloat("_DstBlendAlpha",(float)BlendMode.OneMinusSrcAlpha);
                            mat.SetFloat("_ZWrite",0); mat.SetFloat("_Cull",2);
                            mat.SetFloat("_SpecularHighlights",0);mat.SetFloat("_EnvironmentReflections",0);
                            mat.EnableKeyword("_SURFACE_TYPE_TRANSPARENT");mat.EnableKeyword("_SPECULARHIGHLIGHTS_OFF");
                            mat.EnableKeyword("_ENVIRONMENTREFLECTIONS_OFF");mat.DisableKeyword("_ALPHATEST_ON");
                            mat.SetOverrideTag("RenderType","Transparent");mat.renderQueue=3000;
                        }
                        string path=dest+"/material-"+m+".mat";
                        var existing=AssetDatabase.LoadAssetAtPath<Material>(path);
                        if(existing){EditorUtility.CopySerialized(mat,existing);UnityEngine.Object.DestroyImmediate(mat);mat=existing;}
                        else AssetDatabase.CreateAsset(mat,path);
                        materials[m]=mat;
                    }
                    mesh.sharedMaterials=materials; mesh.updateWhenOffscreen=true;
                }
                actor.SetActive(false);
            }
            var camera=new GameObject("Portrait").AddComponent<Camera>();preview.view=camera;
            camera.nearClipPlane=.01f; camera.farClipPlane=1000;
            camera.clearFlags=CameraClearFlags.SolidColor;camera.backgroundColor=new Color(.10f,.13f,.16f);
            RenderSettings.ambientMode=AmbientMode.Flat;RenderSettings.ambientLight=new Color(.48f,.48f,.48f);
            foreach(var spec in new[]{new Vector4(30,-25,0,1.5f),new Vector4(20,145,0,.65f)})
            {var light=new GameObject("Light").AddComponent<Light>();light.type=LightType.Directional;light.intensity=spec.w;light.transform.rotation=Quaternion.Euler(spec.x,spec.y,spec.z);}
            string scenePath=Root+"/RocketboxFacePreview.unity";
            EditorSceneManager.SaveScene(scene,scenePath);AssetDatabase.SaveAssets();
            var result=BuildPipeline.BuildPlayer(new BuildPlayerOptions{scenes=new[]{scenePath},locationPathName="Builds/RocketboxPreview/RocketboxPreview.exe",target=BuildTarget.StandaloneWindows64,options=BuildOptions.Development});
            if(result.summary.result!=UnityEditor.Build.Reporting.BuildResult.Succeeded) throw new Exception("Candidate preview build failed");
            Debug.Log("ROCKETBOX_BUILD_OK");
        }
    }
}
