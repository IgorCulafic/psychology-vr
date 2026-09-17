using System;
using System.IO;
using System.Linq;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEditor;
using UnityEditor.SceneManagement;

namespace PsychologyVR.Editor
{
    public class EnvironmentImporter : AssetPostprocessor
    {
        void OnPreprocessModel()
        {
            if(!assetPath.Contains("/Art/Environment/Models/")) return;
            var importer=(ModelImporter)assetImporter;
            importer.importAnimation=false; importer.materialImportMode=ModelImporterMaterialImportMode.ImportStandard;
            importer.importCameras=false; importer.importLights=false; importer.isReadable=false;
            importer.generateSecondaryUV=true;
        }
        void OnPreprocessTexture()
        {
            if(!assetPath.Contains("/Art/Environment/Textures/")) return;
            var importer=(TextureImporter)assetImporter; importer.maxTextureSize=1024; importer.mipmapEnabled=true; importer.anisoLevel=4;
            if(assetPath.Contains("nor_gl")) importer.textureType=TextureImporterType.NormalMap;
            if(assetPath.Contains("metal_smooth") || assetPath.Contains("_rough")) importer.sRGBTexture=false;
        }
        void OnPostprocessModel(GameObject root)
        {
            if(!assetPath.Contains("/Art/Environment/Models/")) return;
            foreach(var filter in root.GetComponentsInChildren<MeshFilter>()) filter.sharedMesh.RecalculateBounds();
        }
    }
    [Serializable] class RoomMaterialList { public RoomMaterial[] materials; }
    [Serializable] class RoomBindingList {public RoomBinding[] bindings;}
    [Serializable] class RoomBinding {public string asset,renderer;public string[] materials;}
    [Serializable] class RoomMaterial
    {
        public string name,baseMap,normalMap,metalMap; public float[] color;
        public float smoothness,metallic; public bool cutout,doubleSided;
    }
    public static class EnvironmentSetup
    {
        const string Art="Assets/PsychologyVR/Art/Environment";
        const string Prefab="Assets/PsychologyVR/Prefabs/ConsultationRoom.prefab";
        static Dictionary<string,Material> materials;
        static Dictionary<string,string[]> bindings;

        [MenuItem("Psychology VR/Rebuild furnished room")]
        public static void Rebuild()
        {
            Directory.CreateDirectory(Art+"/Materials"); AssetDatabase.Refresh();
            materials=new Dictionary<string,Material>();
            bindings=new Dictionary<string,string[]>();
            foreach(var file in new[]{"bindings.json","custom-bindings.json"})
                foreach(var binding in JsonUtility.FromJson<RoomBindingList>(File.ReadAllText(Art+"/"+file)).bindings)
                    bindings[binding.asset+"/"+binding.renderer]=binding.materials;
            foreach(var file in new[]{"materials.json","custom-materials.json"})
            foreach(var spec in JsonUtility.FromJson<RoomMaterialList>(File.ReadAllText(Art+"/"+file)).materials)
            {
                string path=Art+"/Materials/"+spec.name+".mat";
                var mat=AssetDatabase.LoadAssetAtPath<Material>(path);
                if(!mat) {mat=new Material(Shader.Find("Universal Render Pipeline/Lit"));AssetDatabase.CreateAsset(mat,path);}
                mat.name=spec.name;
                mat.SetColor("_BaseColor",new Color(spec.color[0],spec.color[1],spec.color[2],spec.color[3]));
                mat.SetTexture("_BaseMap",Load(spec.baseMap));
                mat.SetFloat("_Smoothness",spec.smoothness); mat.SetFloat("_Metallic",spec.metallic);
                mat.SetFloat("_Cull",spec.doubleSided?0:2);
                var normal=Load(spec.normalMap);mat.SetTexture("_BumpMap",normal);
                if(normal) {mat.EnableKeyword("_NORMALMAP");mat.SetFloat("_BumpScale",spec.name.StartsWith("Room_")?.12f:1);}
                var metal=Load(spec.metalMap);mat.SetTexture("_MetallicGlossMap",metal);
                if(metal) {mat.EnableKeyword("_METALLICSPECGLOSSMAP");mat.SetFloat("_Smoothness",1);}
                mat.SetFloat("_AlphaClip",spec.cutout?1:0);
                if(spec.cutout) {mat.EnableKeyword("_ALPHATEST_ON");mat.SetFloat("_Cutoff",.4f);mat.renderQueue=2450;}
                if(spec.name=="Room_WindowLight") {mat.EnableKeyword("_EMISSION");mat.SetColor("_EmissionColor",new Color(.55f,.7f,.8f));}
                EditorUtility.SetDirty(mat);materials[spec.name]=mat;
            }
            var root=new GameObject("Consultation room — furnished");root.AddComponent<RoomLighting>();
            Place(root,"consultation_architecture",Vector3.zero,0,Vector3.one);
            // The patient's pose is still the supplied seated animation.
            Place(root,"modern_arm_chair_01",new Vector3(0,0,1.32f),180,Vector3.one);
            Place(root,"modern_arm_chair_01",new Vector3(0,0,-1.67f),0,Vector3.one);
            Place(root,"side_table_01",new Vector3(.95f,0,1.15f),-12,Vector3.one);
            Place(root,"tissue_box",new Vector3(.94f,.553f,1.10f),-12,Vector3.one);
            Place(root,"small_wooden_table_01",new Vector3(0,0,-.68f),0,new Vector3(1.48f,1.39f,1.45f));
            Place(root,"binder_notebook",new Vector3(.03f,.745f,-.84f),-9,Vector3.one*.72f);
            Place(root,"pencil",new Vector3(.15f,.75f,-.70f),-10,Vector3.one);
            Place(root,"water_cup",new Vector3(.44f,.742f,-.56f),0,Vector3.one);
            Place(root,"modern_coffee_table_01",new Vector3(-1.94f,0,1.20f),90,Vector3.one);
            // This foliage mesh survives Unity import reliably at the reduced budget.
            Place(root,"potted_plant_02",new Vector3(2.12f,0,2.30f),-30,Vector3.one*1.55f);
            Place(root,"potted_plant_02",new Vector3(-2.05f,.39f,1.40f),0,Vector3.one*.60f);
            Place(root,"modern_ceiling_lamp_01",new Vector3(0,1.99f,.45f),0,Vector3.one);
            var sun=Light(root,"Window daylight",LightType.Directional,new Vector3(-2,2,0),1.0f,new Color(1,.93f,.81f));
            sun.transform.rotation=Quaternion.Euler(38,-95,0);sun.shadows=LightShadows.Soft;
            var fill=Light(root,"Ceiling warm fill",LightType.Point,new Vector3(0,2.45f,.4f),2.7f,new Color(1,.84f,.65f));fill.range=6;
            var window=Light(root,"Window soft fill",LightType.Point,new Vector3(2.35f,1.9f,.6f),3.2f,new Color(.84f,.92f,1));window.range=6;
            var front=Light(root,"Reflected room light",LightType.Point,new Vector3(0,2,-1.8f),1.0f,new Color(1,.94f,.86f));front.range=5;
            var probe=new GameObject("Room reflection probe").AddComponent<ReflectionProbe>();probe.transform.SetParent(root.transform);
            probe.transform.localPosition=new Vector3(0,1.4f,0);probe.size=new Vector3(6,3,6);probe.resolution=128;
            probe.mode=ReflectionProbeMode.Realtime;probe.refreshMode=ReflectionProbeRefreshMode.OnAwake;probe.boxProjection=true;
            probe.clearFlags=ReflectionProbeClearFlags.SolidColor;probe.backgroundColor=new Color(.3f,.34f,.35f);
            var prefab=PrefabUtility.SaveAsPrefabAsset(root,Prefab);
            int triangles=root.GetComponentsInChildren<MeshFilter>().Sum(m=>m.sharedMesh?m.sharedMesh.triangles.Length/3:0);
            UnityEngine.Object.DestroyImmediate(root);
            EditorSceneManager.OpenScene("Assets/PsychologyVR/Scenes/Consultation.unity");
            var session=UnityEngine.Object.FindFirstObjectByType<PrototypeSession>();session.environmentPrefab=prefab;
            EditorUtility.SetDirty(session);EditorSceneManager.MarkSceneDirty(session.gameObject.scene);EditorSceneManager.SaveOpenScenes();
            AssetDatabase.SaveAssets();
            File.WriteAllText("../docs/generated/room-build.txt","Furnished room triangles (all instances): "+triangles+"\nSource maps: 1K, normal maps + metallic/smoothness conversion.\n");
            Debug.Log("FURNISHED_ROOM_OK triangles="+triangles);
        }
        static Texture2D Load(string path)=>string.IsNullOrEmpty(path)?null:AssetDatabase.LoadAssetAtPath<Texture2D>(path);
        static GameObject Place(GameObject root,string name,Vector3 p,float yaw,Vector3 scale)
        {
            var source=AssetDatabase.LoadAssetAtPath<GameObject>(Art+"/Models/"+name+".fbx");
            if(!source) throw new InvalidOperationException("Missing room model: "+name);
            // Preserve FBX root rotation/scale (including centimetre conversion).
            // Scene placement belongs on a wrapper, never on the imported root.
            var obj=new GameObject(name);obj.transform.SetParent(root.transform,false);
            var model=(GameObject)PrefabUtility.InstantiatePrefab(source);
            model.transform.SetParent(obj.transform,false);
            obj.transform.localPosition=p;obj.transform.localRotation=Quaternion.Euler(0,yaw,0);obj.transform.localScale=scale;
            foreach(var renderer in obj.GetComponentsInChildren<Renderer>())
            {
                var mapped=renderer.sharedMaterials;
                if(!bindings.TryGetValue(name+"/"+renderer.name,out var materialNames))
                {
                    var single=bindings.Where(b=>b.Key.StartsWith(name+"/",StringComparison.Ordinal)).ToArray();
                    if(single.Length==1) materialNames=single[0].Value;
                    else throw new InvalidOperationException("Missing material binding: "+name+"/"+renderer.name);
                }
                if(mapped.Length!=materialNames.Length) throw new InvalidOperationException("Material slot count changed: "+name+"/"+renderer.name);
                for(int i=0;i<mapped.Length;i++)
                {
                    string key=materialNames[i];
                    if(materials.TryGetValue(key,out var mat)) mapped[i]=mat;
                    else throw new InvalidOperationException("Unmapped room material: "+key+" on "+name+"/"+renderer.name+" path="+AssetDatabase.GetAssetPath(mapped[i]));
                }
                renderer.sharedMaterials=mapped;
            }
            // Static props get simple colliders; detailed meshes are reserved for visuals.
            if(name!="consultation_architecture")
            {
                var collider=obj.AddComponent<BoxCollider>();var bounds=new Bounds(Vector3.zero,Vector3.zero);
                foreach(var filter in obj.GetComponentsInChildren<MeshFilter>())
                {
                    var b=filter.sharedMesh.bounds;
                    for(int n=0;n<8;n++) bounds.Encapsulate(obj.transform.InverseTransformPoint(filter.transform.TransformPoint(b.center+Vector3.Scale(b.extents,new Vector3((n&1)==0?-1:1,(n&2)==0?-1:1,(n&4)==0?-1:1)))));
                }
                collider.center=bounds.center;collider.size=bounds.size;
            }
            return obj;
        }
        static Light Light(GameObject root,string name,LightType type,Vector3 p,float intensity,Color color)
        {
            var light=new GameObject(name).AddComponent<Light>();light.transform.SetParent(root.transform,false);light.transform.localPosition=p;
            light.type=type;light.intensity=intensity;light.color=color;return light;
        }
        public static void RebuildAndBuild() {Rebuild();ProjectSetup.ConfigureAndBuild();}
    }
}
