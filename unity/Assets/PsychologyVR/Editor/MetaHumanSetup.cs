using System;
using System.IO;
using System.Linq;
using System.Collections.Generic;
using UnityEngine;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine.Rendering;

namespace PsychologyVR.Editor
{
    public class MetaHumanImporter : AssetPostprocessor
    {
        void OnPreprocessModel()
        {
            if(!assetPath.Contains("/MetaHumans/"))return;
            var m=(ModelImporter)assetImporter;
            m.animationType=ModelImporterAnimationType.Legacy;m.importAnimation=assetPath.Contains("/animations/");
            m.optimizeGameObjects=false;m.isReadable=true;m.importBlendShapes=false;
            var manifest=JsonUtility.FromJson<MetaHumanSetup.Manifest>(File.ReadAllText("Assets/PsychologyVR/Art/MetaHumans/manifest.json"));
            var spec=manifest.characters.SelectMany(c=>c.meshes).FirstOrDefault(s=>assetPath.EndsWith("/"+s.file));
            m.swapUVChannels=spec!=null&&spec.uvChannel==1;
            m.animationCompression=ModelImporterAnimationCompression.Off;
            m.materialImportMode=ModelImporterMaterialImportMode.ImportStandard;
        }
        void OnPreprocessTexture()
        {
            if(!assetPath.Contains("/MetaHumans/"))return;
            var t=(TextureImporter)assetImporter;t.maxTextureSize=2048;
            if(assetPath.Contains("_N_")||assetPath.Contains("_Normal_")||assetPath.Contains("_Normalmap_"))
            {t.textureType=TextureImporterType.NormalMap;t.flipGreenChannel=true;}
            if(assetPath.Contains("_RGBA"))t.alphaIsTransparency=true;
        }
    }
    public static class MetaHumanSetup
    {
        const string Root="Assets/PsychologyVR/Art/MetaHumans";
        [Serializable] public class Manifest {public Character[] characters;public MaterialSpec[] materials;}
        [Serializable] public class Character {public string id,label,scenario,voice;public MeshSpec[] meshes;public ClipSpec[] clips;public string[] poses;}
        [Serializable] public class MeshSpec {public string name,file,type,hairMap;public string[] materials;public int uvChannel;}
        [Serializable] public class ClipSpec {public string name,file;public int frames;}
        [Serializable] public class MaterialSpec {public string key,id,name,colorMap,normalMap,mode;public float[] color;public float smoothness;}
        static Dictionary<string,Material> materials;
        public static void BuildAll(){BuildPreview();MenuSetup.Build();}
        public static void InspectPrepared()
        {
            foreach(string id in new[]{"ivan","stefan","nikola","alex"})
            {
                var actor=(GameObject)PrefabUtility.InstantiatePrefab(AssetDatabase.LoadAssetAtPath<GameObject>(Root+"/"+id+"/Character.prefab"));
                var rig=actor.GetComponent<MetaHumanJointRig>();rig.Initialize();rig.Apply("neutral",0,new Dictionary<string,float>(),false,"X",false,.65f);
                Debug.Log("MH_DIAG_HEAD "+id+" "+rig.Head.position);
                foreach(var r in actor.GetComponentsInChildren<Renderer>())
                {
                    Debug.Log("MH_DIAG "+id+" "+r.name+" bounds="+r.bounds+" material="+r.sharedMaterial.name+" texture="+r.sharedMaterial.GetTexture("_BaseMap")+" scale="+r.transform.lossyScale);
                    if(r is SkinnedMeshRenderer s&&r.name.Contains("cards"))
                    {var mesh=new Mesh();s.BakeMesh(mesh);mesh.RecalculateBounds();Debug.Log("MH_HAIR_BAKED "+id+" "+r.name+" "+mesh.bounds+" worldCenter="+r.transform.TransformPoint(mesh.bounds.center));UnityEngine.Object.DestroyImmediate(mesh);}
                }
                UnityEngine.Object.DestroyImmediate(actor);
            }
        }
        public static void ImportAudit()
        {
            AssetDatabase.Refresh();
            var m=JsonUtility.FromJson<Manifest>(File.ReadAllText(Root+"/manifest.json"));
            materials=m.materials.ToDictionary(x=>x.key,CreateMaterial);
            foreach(var c in m.characters)
            {
                var actor=Assemble(c);
                foreach(var r in actor.GetComponentsInChildren<Renderer>())Debug.Log("MH_MESH "+c.id+" "+r.name+" "+r.bounds+" scale "+r.transform.lossyScale+" mats "+string.Join(",",r.sharedMaterials.Select(x=>x.name)));
                foreach(var t in actor.GetComponentsInChildren<Transform>())if(new[]{"root","pelvis","spine_01","head","FACIAL_L_Eye","FACIAL_R_Eye","thigh_l","calf_l","upperarm_l","lowerarm_l","hand_l"}.Contains(t.name))Debug.Log("MH_BONE "+c.id+" "+AnimationUtility.CalculateTransformPath(t,actor.transform)+" "+t.position+" rot "+t.rotation.eulerAngles);
                PrefabUtility.SaveAsPrefabAsset(actor,Root+"/"+c.id+"/Character.prefab");UnityEngine.Object.DestroyImmediate(actor);
            }
            AssetDatabase.SaveAssets();Debug.Log("MH_IMPORT_OK");
        }
        [MenuItem("Psychology VR/MetaHuman/Build desktop validation")]
        public static void BuildPreview()
        {
            AssetDatabase.Refresh();var m=JsonUtility.FromJson<Manifest>(File.ReadAllText(Root+"/manifest.json"));
            materials=m.materials.ToDictionary(x=>x.key,CreateMaterial);
            var scene=EditorSceneManager.NewScene(NewSceneSetup.EmptyScene,NewSceneMode.Single);
            var demo=new GameObject("MetaHuman validation").AddComponent<MetaHumanPreview>();demo.characters=new GameObject[m.characters.Length];
            demo.angryVoices=new AudioClip[m.characters.Length];demo.angryCues=new TextAsset[m.characters.Length];
            int index=0;
            foreach(var c in m.characters)
            {
                if(c.clips.Length!=4)throw new Exception("Incomplete animation export: "+c.id);
                var actor=Assemble(c);var face=actor.transform.Find("Face").gameObject;
                var faceSkin=face.GetComponentInChildren<SkinnedMeshRenderer>();
                BindFacialHair(actor,faceSkin,c.id);
                var restHead=face.GetComponentsInChildren<Transform>().First(t=>t.name=="head");
                foreach(var hair in actor.GetComponentsInChildren<MeshRenderer>())if(hair.name.Contains("_cards_"))hair.transform.SetParent(restHead,true);
                var transforms=face.GetComponentsInChildren<Transform>().Where(t=>t.name.StartsWith("FACIAL_")||new[]{"neck_01","neck_02","head"}.Contains(t.name)).ToArray();
                var data=ScriptableObject.CreateInstance<MetaHumanPoseLibrary>();data.bones=transforms.Select(t=>t.name).ToArray();
                AnimationClip poseClip=Clip(c,"poses");data.poses=new MetaHumanPoseLibrary.Pose[c.poses.Length];
                for(int i=0;i<c.poses.Length;i++)
                {
                    poseClip.SampleAnimation(face,i/30f);
                    data.poses[i]=new MetaHumanPoseLibrary.Pose{name=c.poses[i],positions=transforms.Select(t=>t.localPosition).ToArray(),rotations=transforms.Select(t=>t.localRotation).ToArray()};
                }
                poseClip.SampleAnimation(face,0);
                data.afraid=Clip(c,"afraid");data.crying=Clip(c,"crying");data.angry=Clip(c,"angry");
                string dataPath=Root+"/"+c.id+"/FacialPoses.asset";var old=AssetDatabase.LoadAssetAtPath<MetaHumanPoseLibrary>(dataPath);
                if(old){EditorUtility.CopySerialized(data,old);UnityEngine.Object.DestroyImmediate(data);data=old;}else AssetDatabase.CreateAsset(data,dataPath);
                float maxJaw=data.poses[1].positions.Zip(data.poses[0].positions,(a,b)=>(a-b).magnitude).Max();
                float maxRot=data.poses[1].rotations.Zip(data.poses[0].rotations,(a,b)=>Quaternion.Angle(a,b)).Max();
                Debug.Log("MH_POSE_VALIDATION "+c.id+" jawTranslation="+maxJaw+" rotation="+maxRot+" bones="+transforms.Length);
                if(maxJaw<.00001f&&maxRot<.1f)throw new Exception("Speech pose bank is static: "+c.id);
                var rig=actor.AddComponent<MetaHumanJointRig>();rig.library=data;rig.faceObject=face;rig.bodyObject=actor.transform.Find("Body").gameObject;
                rig.clothingObject=actor.transform.Find("SkeletalMesh").gameObject;rig.skin=face.GetComponentInChildren<SkinnedMeshRenderer>();
                if(c.id=="ivan")rig.seatedIdle=AssetDatabase.LoadAssetAtPath<AnimationClip>(Root+"/ivan/animations/SeatedVideo5799.anim");
                PrefabUtility.SaveAsPrefabAsset(actor,Root+"/"+c.id+"/Character.prefab");
                demo.angryVoices[index]=AssetDatabase.LoadAssetAtPath<AudioClip>(Root+"/"+c.id+"/audio/anger.wav");
                demo.angryCues[index]=AssetDatabase.LoadAssetAtPath<TextAsset>(Root+"/"+c.id+"/audio/anger.json");
                demo.characters[index++]=actor;actor.SetActive(false);
            }
            var camera=new GameObject("Portrait").AddComponent<Camera>();demo.view=camera;camera.nearClipPlane=.01f;camera.farClipPlane=50;
            camera.gameObject.AddComponent<AudioListener>();
            camera.clearFlags=CameraClearFlags.SolidColor;camera.backgroundColor=new Color(.10f,.13f,.16f);
            RenderSettings.ambientMode=AmbientMode.Flat;RenderSettings.ambientLight=new Color(.48f,.48f,.48f);
            foreach(var spec in new[]{new Vector4(30,-25,0,1.3f),new Vector4(20,145,0,.65f)})
            {var light=new GameObject("Light").AddComponent<Light>();light.type=LightType.Directional;light.intensity=spec.w;light.transform.rotation=Quaternion.Euler(spec.x,spec.y,spec.z);}
            string scenePath=Root+"/MetaHumanPreview.unity";EditorSceneManager.SaveScene(scene,scenePath);AssetDatabase.SaveAssets();
            BuildSavedPreview();
        }
        public static void RefreshPreviewAndMenu(){BuildSavedPreview();MenuSetup.Build();}
        public static void BuildSavedPreview()
        {
            string scenePath=Root+"/MetaHumanPreview.unity";
            var result=BuildPipeline.BuildPlayer(new BuildPlayerOptions{scenes=new[]{scenePath},locationPathName="Builds/MetaHumanPreview/MetaHumanPreview.exe",target=BuildTarget.StandaloneWindows64,options=BuildOptions.Development});
            if(result.summary.result!=UnityEditor.Build.Reporting.BuildResult.Succeeded)throw new Exception("MetaHuman preview build failed");
            Debug.Log("MH_PREVIEW_BUILD_OK");
        }
        static AnimationClip Clip(Character c,string name)
        {
            var spec=c.clips.Single(x=>x.name==name);
            var clip=AssetDatabase.LoadAllAssetsAtPath(Root+"/"+spec.file).OfType<AnimationClip>().First(x=>!x.name.StartsWith("__preview__"));
            return clip;
        }
        static void BindFacialHair(GameObject actor,SkinnedMeshRenderer face,string id)
        {
            var vertices=face.sharedMesh.vertices;var weights=face.sharedMesh.boneWeights;
            var surface=new GameObject("Temporary facial hair fitting surface");surface.transform.SetPositionAndRotation(face.transform.position,face.transform.rotation);surface.transform.localScale=face.transform.lossyScale;
            var collider=surface.AddComponent<MeshCollider>();collider.sharedMesh=face.sharedMesh;Physics.SyncTransforms();
            foreach(var mr in actor.GetComponentsInChildren<MeshRenderer>())
            {
                var node=mr.name.Contains("_cards_")?mr.transform:mr.transform.parent;
                if(!new[]{"Eyebrows","Beard","Mustache"}.Any(x=>node.name.StartsWith(x)))continue;
                var mf=mr.GetComponent<MeshFilter>();var mesh=UnityEngine.Object.Instantiate(mf.sharedMesh);var hair=mesh.vertices;var bw=new BoneWeight[hair.Length];
                var toActor=actor.transform.worldToLocalMatrix*mr.transform.localToWorldMatrix;
                var normals=mesh.normals;
                for(int i=0;i<hair.Length;i++){hair[i]=toActor.MultiplyPoint3x4(hair[i]);normals[i]=toActor.MultiplyVector(normals[i]).normalized;}
                // Grooms are fitted by Unreal at runtime. Project their thin facial cards
                // onto this identity's rest skin before deriving the portable skin weights.
                for(int i=0;i<hair.Length;i++)
                {
                    var ray=new Ray(actor.transform.TransformPoint(hair[i])+actor.transform.forward,-actor.transform.forward);
                    if(collider.Raycast(ray,out var hit,2f))
                    {hair[i]=actor.transform.InverseTransformPoint(hit.point+hit.normal*.0009f);normals[i]=actor.transform.InverseTransformDirection(hit.normal);}
                }
                mesh.vertices=hair;mesh.normals=normals;mesh.RecalculateBounds();
                mr.transform.SetParent(actor.transform,false);mr.transform.localPosition=Vector3.zero;mr.transform.localRotation=Quaternion.identity;mr.transform.localScale=Vector3.one;
                for(int i=0;i<hair.Length;i++)
                {
                    Vector3 p=face.transform.InverseTransformPoint(mr.transform.TransformPoint(hair[i]));float best=float.MaxValue;int nearest=0;
                    for(int j=0;j<vertices.Length;j++){float d=(vertices[j]-p).sqrMagnitude;if(d<best){best=d;nearest=j;}}
                    bw[i]=weights[nearest];
                }
                mesh.boneWeights=bw;mesh.bindposes=face.bones.Select(b=>b.worldToLocalMatrix*mr.transform.localToWorldMatrix).ToArray();
                string path=Root+"/"+id+"/"+node.name+"_skinned.asset";var old=AssetDatabase.LoadAssetAtPath<Mesh>(path);
                if(old){EditorUtility.CopySerialized(mesh,old);UnityEngine.Object.DestroyImmediate(mesh);mesh=old;}else AssetDatabase.CreateAsset(mesh,path);
                var go=mr.gameObject;var mats=mr.sharedMaterials;UnityEngine.Object.DestroyImmediate(mr);UnityEngine.Object.DestroyImmediate(mf);
                var skin=go.AddComponent<SkinnedMeshRenderer>();skin.sharedMesh=mesh;skin.sharedMaterials=mats;skin.bones=face.bones;skin.rootBone=face.rootBone;skin.updateWhenOffscreen=true;
                skin.localBounds=new Bounds(new Vector3(0,1,0),new Vector3(2,2.5f,2));
            }
            UnityEngine.Object.DestroyImmediate(surface);
        }
        static Material CreateMaterial(MaterialSpec s)
        {
            Directory.CreateDirectory(Root+"/Materials");string path=Root+"/Materials/"+s.id+".mat";
            var mat=AssetDatabase.LoadAssetAtPath<Material>(path);
            if(!mat){mat=new Material(Shader.Find("Universal Render Pipeline/Lit"));AssetDatabase.CreateAsset(mat,path);}
            mat.name=s.name;mat.SetColor("_BaseColor",new Color(s.color[0],s.color[1],s.color[2],s.mode=="hidden"?0:1));mat.SetFloat("_Smoothness",s.smoothness);
            mat.SetTexture("_BaseMap",string.IsNullOrEmpty(s.colorMap)?null:AssetDatabase.LoadAssetAtPath<Texture2D>(Root+"/"+s.colorMap));
            if(!string.IsNullOrEmpty(s.normalMap))
            {mat.SetTexture("_BumpMap",AssetDatabase.LoadAssetAtPath<Texture2D>(Root+"/"+s.normalMap));mat.SetFloat("_BumpScale",.65f);mat.EnableKeyword("_NORMALMAP");}
            if(s.mode=="hidden"){mat.SetFloat("_AlphaClip",1);mat.SetFloat("_Cutoff",.5f);mat.EnableKeyword("_ALPHATEST_ON");mat.renderQueue=2450;}
            EditorUtility.SetDirty(mat);return mat;
        }
        static GameObject Assemble(Character c)
        {
            var actor=new GameObject(c.label);
            foreach(var spec in c.meshes)
            {
                string modelPath=spec.name=="SkeletalMesh"?c.id+"/models/Outfit.fbx":spec.file;
                var model=AssetDatabase.LoadAssetAtPath<GameObject>(Root+"/"+modelPath);if(!model)throw new Exception(modelPath);
                var part=(GameObject)PrefabUtility.InstantiatePrefab(model);PrefabUtility.UnpackPrefabInstance(part,PrefabUnpackMode.Completely,InteractionMode.AutomatedAction);
                part.name=spec.name;part.transform.SetParent(actor.transform,false);
                foreach(var anim in part.GetComponentsInChildren<Animation>())UnityEngine.Object.DestroyImmediate(anim);
                foreach(var r in part.GetComponentsInChildren<Renderer>())
                {
                    var mats=r.sharedMaterials;
                    Debug.Log("MH_SOURCE_MATERIALS "+c.id+" "+spec.name+" "+string.Join(",",mats.Select(x=>x?x.name:"null")));
                    for(int i=0;i<mats.Length;i++)
                    {
                        if(spec.type=="hair_cards")
                        {
                            string path=Root+"/"+c.id+"/"+spec.name+".mat";var mat=AssetDatabase.LoadAssetAtPath<Material>(path);
                            if(!mat){mat=new Material(Shader.Find("Universal Render Pipeline/Lit"));AssetDatabase.CreateAsset(mat,path);}
                            mat.SetTexture("_BaseMap",AssetDatabase.LoadAssetAtPath<Texture2D>(Root+"/"+spec.hairMap));mat.SetColor("_BaseColor",Color.white);
                            mat.SetFloat("_Cull",0);mat.SetFloat("_Smoothness",.25f);mat.SetFloat("_AlphaClip",1);mat.SetFloat("_Cutoff",.25f);mat.EnableKeyword("_ALPHATEST_ON");mat.renderQueue=2450;mats[i]=mat;
                            mat.SetFloat("_Cutoff",.15f);mat.SetFloat("_SpecularHighlights",0);mat.EnableKeyword("_SPECULARHIGHLIGHTS_OFF");
                            mat.SetFloat("_EnvironmentReflections",0);mat.EnableKeyword("_ENVIRONMENTREFLECTIONS_OFF");EditorUtility.SetDirty(mat);
                            if(!spec.name.StartsWith("Hair_"))
                            {
                                // Fine facial strands need fractional coverage; a hard alpha
                                // threshold otherwise turns eyebrows and stubble into dots.
                                mat.SetFloat("_Surface",1);mat.SetFloat("_SrcBlend",5);mat.SetFloat("_DstBlend",10);mat.SetFloat("_ZWrite",0);
                                mat.SetFloat("_Cutoff",.02f);mat.EnableKeyword("_SURFACE_TYPE_TRANSPARENT");mat.SetOverrideTag("RenderType","Transparent");mat.renderQueue=3000;
                            }
                        }
                    }
                    if(spec.type!="hair_cards")for(int i=0;i<mats.Length;i++)
                    {
                        if(spec.name=="SkeletalMesh")
                        {
                            string materialName=mats[i]?mats[i].name:"";
                            mats[i]=WardrobeMaterial(c.id,materialName.Contains("Shirt")?"shirt":materialName.Contains("Short")?"trousers":materialName.Contains("Sole")?"sole":"shoes");continue;
                        }
                        // UE's FBX exporter writes the global material table but LOD0 section
                        // indices are compacted. Restore the MetaHuman face's LOD0 section map.
                        if(spec.name=="Face")
                        {
                            int[] lod0={8,0,1,2,3,4,5,6,7};
                            if(mats.Length!=lod0.Length)throw new Exception("Unexpected MetaHuman face sections: "+mats.Length);
                            mats[i]=materials[spec.materials[lod0[i]]];continue;
                        }
                        string n=mats[i]?mats[i].name:"";
                        string key=spec.materials.FirstOrDefault(k=>materials[k].name==n);
                        if(key==null&&i<spec.materials.Length)key=spec.materials[i];
                        if(key!=null)mats[i]=materials[key];
                    }
                    r.sharedMaterials=mats;
                    if(r is SkinnedMeshRenderer skin){skin.updateWhenOffscreen=true;skin.quality=SkinQuality.Bone4;}
                    if(spec.name=="Body"&&c.id!="ivan"&&r is SkinnedMeshRenderer bodySkin)HideCoveredLegs(bodySkin,c.id);
                    if(spec.name=="Body"&&c.id=="ivan"&&r is SkinnedMeshRenderer ivanBody)
                    {
                        var restored=AssetDatabase.LoadAssetAtPath<Mesh>(Root+"/ivan/RestoredBody.asset");
                        if(restored)ivanBody.sharedMesh=restored;
                    }
                    if(spec.name=="SkeletalMesh"&&c.id=="ivan"&&r is SkinnedMeshRenderer outfitSkin)RemoveTrouserSection(outfitSkin);
                }
            }
            return actor;
        }
        public static void RemoveIvanTrousers()
        {
            const string folder=Root+"/ivan/";
            var actor=PrefabUtility.LoadPrefabContents(folder+"Character.prefab");
            try
            {
                var rig=actor.GetComponent<MetaHumanJointRig>();
                var original=AssetDatabase.LoadAssetAtPath<GameObject>(folder+"models/Body.fbx").GetComponentsInChildren<SkinnedMeshRenderer>().ToDictionary(r=>r.name,r=>r.sharedMesh);
                var restored=AssetDatabase.LoadAssetAtPath<Mesh>(folder+"RestoredBody.asset");
                foreach(var skin in rig.bodyObject.GetComponentsInChildren<SkinnedMeshRenderer>())skin.sharedMesh=restored?restored:original[skin.name];
                foreach(var skin in rig.clothingObject.GetComponentsInChildren<SkinnedMeshRenderer>())RemoveTrouserSection(skin);
                PrefabUtility.SaveAsPrefabAsset(actor,folder+"Character.prefab");AssetDatabase.SaveAssets();
                Debug.Log("METAHUMAN_IVAN_TROUSERS_REMOVED: original leg mesh restored; shirt and shoes retained.");
            }
            finally{PrefabUtility.UnloadPrefabContents(actor);}
        }
        public static void HideIvanFeetUnderShoes()
        {
            const string folder=Root+"/ivan/";
            var actor=PrefabUtility.LoadPrefabContents(folder+"Character.prefab");
            try
            {
                var rig=actor.GetComponent<MetaHumanJointRig>();
                var skin=rig.bodyObject.GetComponentInChildren<SkinnedMeshRenderer>();
                var original=AssetDatabase.LoadAssetAtPath<Mesh>(folder+"RestoredBody.asset");
                if(skin.sharedMesh!=original)throw new InvalidOperationException("Ivan's restored body is not assigned.");
                var mesh=UnityEngine.Object.Instantiate(original);var weights=mesh.boneWeights;
                var feet=skin.bones.Where(b=>b.name=="foot_l"||b.name=="foot_r").ToArray();
                var covered=skin.bones.Select(b=>feet.Any(foot=>b.IsChildOf(foot))).ToArray();
                bool UnderShoe(int vertex)
                {
                    var w=weights[vertex];
                    return (covered[w.boneIndex0]?w.weight0:0)+(covered[w.boneIndex1]?w.weight1:0)+(covered[w.boneIndex2]?w.weight2:0)+(covered[w.boneIndex3]?w.weight3:0)>.5f;
                }
                int removed=0;
                for(int sub=0;sub<mesh.subMeshCount;sub++)
                {
                    var triangles=mesh.GetTriangles(sub);var kept=new List<int>();
                    for(int i=0;i<triangles.Length;i+=3)
                        if(UnderShoe(triangles[i])&&UnderShoe(triangles[i+1])&&UnderShoe(triangles[i+2]))removed++;
                        else {kept.Add(triangles[i]);kept.Add(triangles[i+1]);kept.Add(triangles[i+2]);}
                    mesh.SetTriangles(kept,sub);
                }
                EditorUtility.CopySerialized(mesh,original);UnityEngine.Object.DestroyImmediate(mesh);
                AssetDatabase.SaveAssets();Debug.Log("METAHUMAN_SHOE_COVERAGE removedHiddenTriangles="+removed);
            }
            finally{PrefabUtility.UnloadPrefabContents(actor);}
        }
        public static void RestoreIvanBody()
        {
            var args=Environment.GetCommandLineArgs();int at=Array.IndexOf(args,"--body-source");
            if(at<0||at+1>=args.Length)throw new ArgumentException("--body-source requires the complete body FBX.");
            const string folder=Root+"/ivan/";
            const string importPath=folder+"models/RestorationSource.fbx";
            if(File.Exists(importPath))throw new InvalidOperationException("Temporary body import path is already occupied.");
            GameObject actor=null,source=null;
            try
            {
                File.Copy(Path.GetFullPath(args[at+1]),importPath);
                AssetDatabase.ImportAsset(importPath,ImportAssetOptions.ForceSynchronousImport);
                var importer=(ModelImporter)AssetImporter.GetAtPath(importPath);
                importer.bakeAxisConversion=true;importer.SaveAndReimport();
                source=UnityEngine.Object.Instantiate(AssetDatabase.LoadAssetAtPath<GameObject>(importPath));
                actor=PrefabUtility.LoadPrefabContents(folder+"Character.prefab");
                var rig=actor.GetComponent<MetaHumanJointRig>();
                var target=rig.bodyObject.GetComponentInChildren<SkinnedMeshRenderer>();
                var original=source.GetComponentInChildren<SkinnedMeshRenderer>();
                var targetIndices=target.bones.Select((b,i)=>new{b.name,index=i}).ToDictionary(b=>b.name,b=>b.index);
                var mapping=original.bones.Select(b=>targetIndices[b.name]).ToArray();
                var alignment=Matrix4x4.Rotate(Quaternion.Euler(0,180,0));
                float restError=original.bones.Select((b,i)=>Vector3.Distance(alignment.MultiplyPoint3x4(b.position),target.bones[mapping[i]].position)).Max();
                if(restError>.0001f)throw new InvalidOperationException("Complete body skeleton does not match Ivan: "+restError+" m.");
                var mesh=UnityEngine.Object.Instantiate(original.sharedMesh);mesh.name="Ivan complete body";
                var matrix=target.transform.worldToLocalMatrix*alignment*original.transform.localToWorldMatrix;
                mesh.vertices=mesh.vertices.Select(v=>matrix.MultiplyPoint3x4(v)).ToArray();
                mesh.normals=mesh.normals.Select(n=>matrix.inverse.transpose.MultiplyVector(n).normalized).ToArray();
                mesh.tangents=mesh.tangents.Select(t=>{var v=matrix.MultiplyVector(new Vector3(t.x,t.y,t.z)).normalized;return new Vector4(v.x,v.y,v.z,t.w);}).ToArray();
                var weights=mesh.boneWeights;
                for(int i=0;i<weights.Length;i++)
                {
                    var w=weights[i];w.boneIndex0=mapping[w.boneIndex0];w.boneIndex1=mapping[w.boneIndex1];
                    w.boneIndex2=mapping[w.boneIndex2];w.boneIndex3=mapping[w.boneIndex3];weights[i]=w;
                }
                mesh.boneWeights=weights;mesh.bindposes=target.bones.Select(b=>b.worldToLocalMatrix*target.transform.localToWorldMatrix).ToArray();mesh.RecalculateBounds();
                // The restored pelvis must remain visible, but the torso is covered
                // by the retained shirt and would otherwise penetrate its surface.
                var torso=target.bones.Select(b=>b.name.StartsWith("spine_")||b.name.StartsWith("neck_")||b.name.StartsWith("clavicle_")).ToArray();
                bool UnderShirt(int vertex)
                {
                    var w=weights[vertex];
                    return (torso[w.boneIndex0]?w.weight0:0)+(torso[w.boneIndex1]?w.weight1:0)+(torso[w.boneIndex2]?w.weight2:0)+(torso[w.boneIndex3]?w.weight3:0)>.5f;
                }
                for(int sub=0;sub<mesh.subMeshCount;sub++)
                {
                    var triangles=mesh.GetTriangles(sub);var kept=new List<int>();
                    for(int i=0;i<triangles.Length;i+=3)
                        if(!UnderShirt(triangles[i])||!UnderShirt(triangles[i+1])||!UnderShirt(triangles[i+2]))
                        {kept.Add(triangles[i]);kept.Add(triangles[i+1]);kept.Add(triangles[i+2]);}
                    mesh.SetTriangles(kept,sub);
                }
                string path=folder+"RestoredBody.asset";var existing=AssetDatabase.LoadAssetAtPath<Mesh>(path);
                if(existing){EditorUtility.CopySerialized(mesh,existing);UnityEngine.Object.DestroyImmediate(mesh);mesh=existing;}
                else AssetDatabase.CreateAsset(mesh,path);
                target.sharedMesh=mesh;
                PrefabUtility.SaveAsPrefabAsset(actor,folder+"Character.prefab");AssetDatabase.SaveAssets();
                Debug.Log("METAHUMAN_BODY_RESTORED vertices="+mesh.vertexCount+" restError="+restError+" bones="+mapping.Length);
            }
            finally
            {
                if(actor)PrefabUtility.UnloadPrefabContents(actor);
                if(source)UnityEngine.Object.DestroyImmediate(source);
                AssetDatabase.DeleteAsset(importPath);
            }
        }
        static void RemoveTrouserSection(SkinnedMeshRenderer skin)
        {
            var slots=skin.sharedMaterials.Select((m,i)=>new{material=m,index=i}).Where(s=>s.material.name=="Casual_trousers").Select(s=>s.index).ToArray();
            if(slots.Length==0)return;
            var mesh=UnityEngine.Object.Instantiate(skin.sharedMesh);
            int removed=0;
            foreach(int slot in slots){removed+=mesh.GetTriangles(slot).Length/3;mesh.SetTriangles(Array.Empty<int>(),slot);}
            const string path=Root+"/ivan/OutfitWithoutTrousers.asset";
            var existing=AssetDatabase.LoadAssetAtPath<Mesh>(path);
            if(existing){EditorUtility.CopySerialized(mesh,existing);UnityEngine.Object.DestroyImmediate(mesh);mesh=existing;}
            else AssetDatabase.CreateAsset(mesh,path);
            skin.sharedMesh=mesh;
            Debug.Log("METAHUMAN_TROUSER_SECTION removedTriangles="+removed+" remainingTriangles="+mesh.triangles.Length/3);
        }
        static Material WardrobeMaterial(string id,string part)
        {
            string path=Root+"/"+id+"/Casual_"+part+".mat";
            var mat=AssetDatabase.LoadAssetAtPath<Material>(path);
            if(!mat){mat=new Material(Shader.Find("Universal Render Pipeline/Lit"));AssetDatabase.CreateAsset(mat,path);}
            Color shirt=id=="ivan"?new Color(.12f,.28f,.28f):id=="stefan"?new Color(.34f,.13f,.12f):id=="nikola"?new Color(.15f,.21f,.32f):new Color(.28f,.30f,.17f);
            Color color=part=="shirt"?shirt:part=="trousers"?new Color(.10f,.13f,.17f):part=="sole"?new Color(.54f,.53f,.49f):new Color(.075f,.060f,.05f);
            mat.SetColor("_BaseColor",color);mat.SetFloat("_Smoothness",part=="shoes"?.28f:.12f);
            mat.SetFloat("_Cull",0);mat.SetFloat("_Metallic",0);
            string texturePath=Root+"/Materials/FabricWeave.png";
            if(!File.Exists(texturePath))
            {
                var texture=new Texture2D(128,128,TextureFormat.RGB24,false);
                for(int y=0;y<128;y++)for(int x=0;x<128;x++)
                {float v=.90f+.06f*Mathf.Sin(x*Mathf.PI*.5f)*Mathf.Sin(y*Mathf.PI*.5f)+.04f*Mathf.PerlinNoise(x*.27f,y*.27f);texture.SetPixel(x,y,new Color(v,v,v));}
                texture.Apply();File.WriteAllBytes(texturePath,texture.EncodeToPNG());UnityEngine.Object.DestroyImmediate(texture);AssetDatabase.ImportAsset(texturePath);
            }
            if(part=="shirt"||part=="trousers")
            {mat.SetTexture("_BaseMap",AssetDatabase.LoadAssetAtPath<Texture2D>(texturePath));mat.SetTextureScale("_BaseMap",new Vector2(12,12));}
            EditorUtility.SetDirty(mat);return mat;
        }
        static void HideCoveredLegs(SkinnedMeshRenderer skin,string id)
        {
            var mesh=UnityEngine.Object.Instantiate(skin.sharedMesh);var weights=mesh.boneWeights;
            var legs=skin.bones.Select(b=>new[]{"thigh","calf","foot","ball","toe"}.Any(n=>b.name.IndexOf(n,StringComparison.OrdinalIgnoreCase)>=0)).ToArray();
            bool Covered(int i)
            {
                var w=weights[i];float v=(legs[w.boneIndex0]?w.weight0:0)+(legs[w.boneIndex1]?w.weight1:0)+(legs[w.boneIndex2]?w.weight2:0)+(legs[w.boneIndex3]?w.weight3:0);
                return v>.5f;
            }
            // The body export contains arms and exposed legs. Trousers and shoes
            // completely cover the legs, so remove those triangles instead of z-fighting.
            for(int sub=0;sub<mesh.subMeshCount;sub++)
            {
                var tris=mesh.GetTriangles(sub);var kept=new List<int>();
                for(int i=0;i<tris.Length;i+=3)
                    if(Enumerable.Range(0,3).Any(j=>!Covered(tris[i+j])))
                    {kept.Add(tris[i]);kept.Add(tris[i+1]);kept.Add(tris[i+2]);}
                mesh.SetTriangles(kept,sub);
            }
            string path=Root+"/"+id+"/ClothedBody.asset";var old=AssetDatabase.LoadAssetAtPath<Mesh>(path);
            if(old){EditorUtility.CopySerialized(mesh,old);UnityEngine.Object.DestroyImmediate(mesh);mesh=old;}else AssetDatabase.CreateAsset(mesh,path);
            skin.sharedMesh=mesh;
        }
    }
}
