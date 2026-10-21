using System;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEngine;
using UnityEngine.Rendering;

namespace PsychologyVR.Editor
{
    // Imports native, weighted Blender geometry onto Ivan's existing skeleton.
    public static class IvanWardrobeSetup
    {
        const string Root="Assets/PsychologyVR/Art/MetaHumans/ivan/";
        const string Folder=Root+"wardrobe/";
        [Serializable] public class Delivery{public Part[] meshes;}
        [Serializable] public class Part{public string name;public Vector3[] vertices;public Vector2[] uv;public Weight[] weights;public string[] materials;public Triangle[] triangles;}
        [Serializable] public class Weight{public string[] names;public float[] values;}
        [Serializable] public class Triangle{public int material;public int[] indices;}
        public static void Import()
        {
            var args=Environment.GetCommandLineArgs();int at=Array.IndexOf(args,"--wardrobe-source");
            if(at<0||at+1>=args.Length)throw new ArgumentException("--wardrobe-source requires the exported native Blender geometry.");
            var data=JsonUtility.FromJson<Delivery>(File.ReadAllText(args[at+1]));
            if(!AssetDatabase.IsValidFolder(Folder.TrimEnd('/')))AssetDatabase.CreateFolder(Root.TrimEnd('/'),"wardrobe");
            var actor=PrefabUtility.LoadPrefabContents(Root+"Character.prefab");
            try
            {
                var rig=actor.GetComponent<MetaHumanJointRig>();
                var bones=rig.bodyObject.GetComponentsInChildren<Transform>().GroupBy(t=>t.name).ToDictionary(g=>g.Key,g=>g.First());
                var alignment=Quaternion.identity;
                if(Vector3.Distance(alignment*new Vector3(0,.9986789f,.02712446f),bones["pelvis"].position)>.0001f)
                    throw new InvalidOperationException("Wardrobe requires Ivan's native rest pose: pelvis="+bones["pelvis"].position.ToString("F5")+" actor="+actor.transform.position.ToString("F5")+" rotation="+actor.transform.rotation.eulerAngles);
                var existing=actor.transform.Find("Tailored wardrobe");if(existing)UnityEngine.Object.DestroyImmediate(existing.gameObject);
                var wardrobe=new GameObject("Tailored wardrobe");wardrobe.transform.SetParent(actor.transform,false);
                SkinnedMeshRenderer trousers=null;
                foreach(var part in data.meshes)
                {
                    var obj=new GameObject(part.name);obj.transform.SetParent(wardrobe.transform,false);
                    var skin=obj.AddComponent<SkinnedMeshRenderer>();
                    var names=part.weights.SelectMany(w=>w.names).Distinct().ToArray();
                    var target=names.Select(n=>bones[n]).ToArray();var index=names.Select((n,i)=>(n,i)).ToDictionary(x=>x.n,x=>x.i);
                    var mesh=new Mesh{name=part.name,indexFormat=IndexFormat.UInt32};
                    mesh.vertices=part.vertices.Select(p=>obj.transform.InverseTransformPoint(alignment*p)).ToArray();mesh.uv=part.uv;
                    mesh.boneWeights=part.weights.Select(w=>
                    {
                        var b=new BoneWeight();for(int i=0;i<w.names.Length;i++)
                        {int n=index[w.names[i]];float v=w.values[i];switch(i){case 0:b.boneIndex0=n;b.weight0=v;break;case 1:b.boneIndex1=n;b.weight1=v;break;case 2:b.boneIndex2=n;b.weight2=v;break;case 3:b.boneIndex3=n;b.weight3=v;break;}}
                        return b;
                    }).ToArray();
                    mesh.bindposes=target.Select(b=>b.worldToLocalMatrix*skin.transform.localToWorldMatrix).ToArray();
                    mesh.subMeshCount=part.materials.Length;
                    for(int i=0;i<part.materials.Length;i++)mesh.SetTriangles(part.triangles.Where(t=>t.material==i).SelectMany(t=>t.indices).ToArray(),i);
                    mesh.RecalculateNormals();mesh.RecalculateTangents();mesh.RecalculateBounds();Save(mesh,Folder+part.name+".asset");
                    skin.sharedMesh=AssetDatabase.LoadAssetAtPath<Mesh>(Folder+part.name+".asset");skin.bones=target;skin.rootBone=bones["pelvis"];skin.quality=SkinQuality.Bone4;
                    skin.localBounds=new Bounds(new Vector3(0,.72f,0),new Vector3(1.8f,1.8f,1.8f));skin.updateWhenOffscreen=false;
                    skin.sharedMaterials=part.materials.Select(MaterialFor).ToArray();
                    if(part.name=="Ivan_Trousers")trousers=skin;
                }
                // Preserve source geometry. Only this actor's new covered-body copy loses hidden triangles.
                foreach(var skin in rig.bodyObject.GetComponentsInChildren<SkinnedMeshRenderer>())
                {
                    var source=AssetDatabase.LoadAssetAtPath<Mesh>(Root+"RestoredBody.asset");
                    var copy=UnityEngine.Object.Instantiate(source);copy.name="Body under tailored trousers";
                    var p=copy.vertices.Select(v=>Quaternion.Inverse(alignment)*skin.transform.TransformPoint(v)).ToArray();
                    for(int s=0;s<copy.subMeshCount;s++)
                    {
                        var tri=copy.GetTriangles(s);var kept=Enumerable.Range(0,tri.Length/3).Where(i=>!Enumerable.Range(0,3).All(k=>p[tri[i*3+k]].y<1.086f&&Mathf.Abs(p[tri[i*3+k]].x)<.30f)).SelectMany(i=>tri.Skip(i*3).Take(3)).ToArray();copy.SetTriangles(kept,s);
                    }
                    Save(copy,Folder+"CoveredBody.asset");skin.sharedMesh=AssetDatabase.LoadAssetAtPath<Mesh>(Folder+"CoveredBody.asset");
                }
                foreach(var skin in rig.clothingObject.GetComponentsInChildren<SkinnedMeshRenderer>())
                {
                    if(!skin.sharedMaterials.Any(m=>m.name=="Casual_shirt")){skin.enabled=false;continue;}
                    var source=AssetDatabase.LoadAssetAtPath<Mesh>(Root+"OutfitWithoutTrousers.asset");var copy=UnityEngine.Object.Instantiate(source);copy.name="Retained shirt";
                    for(int s=0;s<copy.subMeshCount;s++)if(skin.sharedMaterials[s].name!="Casual_shirt")copy.SetTriangles(Array.Empty<int>(),s);
                    Save(copy,Folder+"ShirtOnly.asset");skin.sharedMesh=AssetDatabase.LoadAssetAtPath<Mesh>(Folder+"ShirtOnly.asset");
                }
                var deformation=actor.GetComponent<SeatedTrouserDeformation>()??actor.AddComponent<SeatedTrouserDeformation>();deformation.trousers=trousers;
                deformation.leftThigh=bones["thigh_l"];deformation.leftKnee=bones["calf_l"];deformation.leftFoot=bones["foot_l"];deformation.leftHand=bones["hand_l"];deformation.leftMiddle=bones["middle_01_l"];
                deformation.rightThigh=bones["thigh_r"];deformation.rightKnee=bones["calf_r"];deformation.rightFoot=bones["foot_r"];deformation.rightHand=bones["hand_r"];deformation.rightMiddle=bones["middle_01_r"];
                PrefabUtility.SaveAsPrefabAsset(actor,Root+"Character.prefab");AssetDatabase.SaveAssets();
                foreach(var shader in new[]{Shader.Find("PsychologyVR/Cloth Lit")})
                {
                    var errors=ShaderUtil.GetShaderMessages(shader).Where(m=>m.severity==UnityEditor.Rendering.ShaderCompilerMessageSeverity.Error).ToArray();
                    if(errors.Length>0)throw new InvalidOperationException(string.Join("\n",errors.Select(e=>e.message)));
                }
                Debug.Log("IVAN_WARDROBE_IMPORTED vertices="+data.meshes.Sum(m=>m.vertices.Length));
            }
            finally{PrefabUtility.UnloadPrefabContents(actor);}
        }
        static void Save(UnityEngine.Object value,string path)
        {
            var old=AssetDatabase.LoadAssetAtPath<UnityEngine.Object>(path);
            if(old){EditorUtility.CopySerialized(value,old);UnityEngine.Object.DestroyImmediate(value);}else AssetDatabase.CreateAsset(value,path);
        }
        static Material MaterialFor(string name)
        {
            string path=Folder+name.Replace(' ','_')+".mat";var m=AssetDatabase.LoadAssetAtPath<Material>(path);if(m)return m;
            bool fabric=name=="Charcoal woven trousers";m=new Material(Shader.Find(fabric?"PsychologyVR/Cloth Lit":"Universal Render Pipeline/Lit")){name=name};
            Color color;float smooth;
            switch(name){case "Charcoal woven trousers":color=new Color(.16f,.18f,.20f);smooth=.10f;break;case "Tonal stitching":color=new Color(.20f,.21f,.22f);smooth=.10f;break;case "Warm grey rubber":color=new Color(.35f,.34f,.32f);smooth=.10f;break;case "Dark woven laces":color=new Color(.10f,.09f,.08f);smooth=.10f;break;default:color=new Color(.09f,.065f,.048f);smooth=.32f;break;}
            m.SetColor("_BaseColor",color);m.SetFloat("_Smoothness",smooth);m.SetFloat("_Metallic",0);m.SetFloat("_Cull",2);
            if(fabric){m.SetTexture("_BaseMap",AssetDatabase.LoadAssetAtPath<Texture2D>("Assets/PsychologyVR/Art/MetaHumans/Materials/FabricWeave.png"));m.SetTextureScale("_BaseMap",new Vector2(10,10));}
            AssetDatabase.CreateAsset(m,path);return m;
        }
        public static void Validate()
        {
            if(!EditorApplication.isPlaying)UnityEditor.SceneManagement.EditorSceneManager.OpenScene("Assets/PsychologyVR/Scenes/Consultation.unity");
            var actor=UnityEngine.Object.Instantiate(AssetDatabase.LoadAssetAtPath<GameObject>(Root+"Character.prefab"));
            var baked=new Mesh();
            try
            {
                var rig=actor.GetComponent<MetaHumanJointRig>();rig.Initialize();
                var cloth=actor.GetComponent<SeatedTrouserDeformation>();var fabric=cloth.trousers.material;
                var shader=fabric.shader;
                for(int pass=0;pass<fabric.passCount;pass++)ShaderUtil.CompilePass(fabric,pass,true);
                var camera=new GameObject("Wardrobe shader check").AddComponent<Camera>();camera.enabled=false;
                camera.transform.position=new Vector3(0,.9f,2);camera.transform.LookAt(new Vector3(0,.8f,0));
                var render=new RenderTexture(128,128,24);
                RenderPipeline.SubmitRenderRequest(camera,new RenderPipeline.StandardRequest{destination=render});
                UnityEngine.Object.DestroyImmediate(camera.gameObject);render.Release();UnityEngine.Object.DestroyImmediate(render);
                var methods=typeof(ShaderUtil).GetMethods(System.Reflection.BindingFlags.Static|System.Reflection.BindingFlags.Public|System.Reflection.BindingFlags.NonPublic);
                var compatibility=methods.First(m=>m.Name=="GetSRPBatcherCompatibilityCode");
                object[] parameters=compatibility.GetParameters().Select(p=>p.ParameterType==typeof(Shader)?(object)shader:0).ToArray();
                int code=(int)compatibility.Invoke(null,parameters);
                if(code!=0)
                {
                    var reason=methods.First(m=>m.Name=="GetSRPBatcherCompatibilityIssueReason");
                    var values=reason.GetParameters().Select(p=>p.ParameterType==typeof(Shader)?(object)shader:p.Name.IndexOf("sub",StringComparison.OrdinalIgnoreCase)>=0?0:code).ToArray();
                    throw new InvalidOperationException("Cloth shader SRP Batcher code="+code+": "+reason.Invoke(null,values));
                }
                var shoes=actor.GetComponentsInChildren<SkinnedMeshRenderer>().Single(s=>s.name=="Ivan_Leather_Sneakers");
                float minimumFloor=float.MaxValue,minBend=1,maxBend=0,minContact=1,maxContact=0,minPalmDistance=1,maxPalmDistance=0;
                int frames=Mathf.RoundToInt(rig.seatedIdle.length*30)+1;
                for(int i=0;i<frames;i++)
                {
                    rig.seatedIdle.SampleAnimation(rig.bodyObject,i/30f);cloth.ApplyPose(0f);
                    shoes.BakeMesh(baked);
                    minimumFloor=Mathf.Min(minimumFloor,baked.vertices.Min(p=>shoes.transform.TransformPoint(p).y-.02f));
                    var knee=fabric.GetVector("_ClothKneeR");var palm=fabric.GetVector("_ClothHandR");
                    var p=Vector3.Lerp(cloth.rightHand.position,cloth.rightMiddle.position,.55f);var segment=cloth.rightKnee.position-cloth.rightThigh.position;
                    var nearest=cloth.rightThigh.position+segment*Mathf.Clamp01(Vector3.Dot(p-cloth.rightThigh.position,segment)/segment.sqrMagnitude);
                    float distance=Vector3.Distance(p,nearest);minPalmDistance=Mathf.Min(minPalmDistance,distance);maxPalmDistance=Mathf.Max(maxPalmDistance,distance);
                    minBend=Mathf.Min(minBend,knee.w);maxBend=Mathf.Max(maxBend,knee.w);minContact=Mathf.Min(minContact,palm.w);maxContact=Mathf.Max(maxContact,palm.w);
                }
                var before=fabric.GetVector("_ClothHandR");
                rig.Apply("neutral",0,new System.Collections.Generic.Dictionary<string,float>(),false,"none",true,.65f);
                if(before!=fabric.GetVector("_ClothHandR"))throw new InvalidOperationException("Paused cloth contacts moved.");
                if(minimumFloor<-.003f)throw new InvalidOperationException("New shoe penetrates floor: "+minimumFloor+" m.");
                if(maxBend-minBend<.01f||maxContact-minContact<.1f)throw new InvalidOperationException("Cloth is not responding: bend="+minBend+".."+maxBend+" contact="+minContact+".."+maxContact+" palmDistance="+minPalmDistance+".."+maxPalmDistance);
                Debug.Log("IVAN_WARDROBE_VALIDATED frames="+frames+" srpBatcherCode="+code+" floorMin="+minimumFloor+" bend="+minBend+".."+maxBend+" palmContact="+minContact+".."+maxContact+" pauseDrift=0");
            }
            finally{UnityEngine.Object.DestroyImmediate(baked);UnityEngine.Object.DestroyImmediate(actor);}
        }
    }
}
