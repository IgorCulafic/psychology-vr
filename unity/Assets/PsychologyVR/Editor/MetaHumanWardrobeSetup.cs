using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;

namespace PsychologyVR.Editor
{
    // Native Blender garments share the body bones; there is no second animated skeleton.
    public static class MetaHumanWardrobeSetup
    {
        const string Root="Assets/PsychologyVR/Art/MetaHumans/";
        static readonly string[] Characters={"alex","nikola","stefan"};
        static readonly string[] Parts={"Tailored_Trousers","Leather_Shoes"};
        static readonly string[][] Slots={new[]{"Trouser","Stitching"},new[]{"Leather","Sole","Laces","Stitching"}};
        [Serializable] public sealed class Fabric {public string name;public float[] color;public float roughness;public string texture;public string normal;}
        [Serializable] public sealed class Delivery
        {
            public IvanWardrobeSetup.Part[] meshes;
            public Fabric[] materials;
            public MetaHumanSeatedIdleSetup.NativeBone[] rest;
            public Check[] checks;
        }
        [Serializable] public sealed class Check {public float time;public MeshCheck[] meshes;}
        [Serializable] public sealed class MeshCheck {public string name;public int[] indices;public Vector3[] positions;}

        public static void Import()
        {
            string source=Argument("--wardrobe-source");
            foreach(string id in SelectedCharacters())
            {
                var data=JsonUtility.FromJson<Delivery>(File.ReadAllText(Path.Combine(source,id,"wardrobe.json")));
                var parts=data.meshes.Where(p=>Parts.Contains(p.name)).ToArray();
                string folder=Root+id+"/wardrobe/";
                var actor=PrefabUtility.LoadPrefabContents(Root+id+"/Character.prefab");
                try
                {
                    var rig=actor.GetComponent<MetaHumanJointRig>();
                    var bones=rig.bodyObject.GetComponentsInChildren<Transform>().GroupBy(t=>t.name).ToDictionary(g=>g.Key,g=>g.First());
                    foreach(var pose in data.rest)
                        if(!bones.TryGetValue(pose.name,out var bone)||Vector3.Distance(actor.transform.InverseTransformPoint(bone.position),pose.p)>.0002f)
                            throw new InvalidOperationException(id+": Blender rest skeleton differs at "+pose.name+". Export the current character before fitting clothing.");
                    foreach(var part in parts)
                    {
                        string[] missing=part.weights.SelectMany(w=>w.names).Distinct().Where(n=>!bones.ContainsKey(n)).ToArray();
                        if(missing.Length>0)throw new InvalidOperationException(id+": unknown garment bones: "+string.Join(", ",missing));
                    }
                    if(!AssetDatabase.IsValidFolder(folder.TrimEnd('/')))AssetDatabase.CreateFolder((Root+id).TrimEnd('/'),"wardrobe");
                    foreach(var fabric in data.materials.Where(f=>Slots.Any(slot=>slot.Contains(f.name))))
                    {
                        bool cloth=fabric.name=="Trouser";
                        string path=folder+fabric.name+".mat";
                        var material=AssetDatabase.LoadAssetAtPath<Material>(path);
                        if(!material){material=new Material(Shader.Find(cloth?"PsychologyVR/Cloth Lit":"Universal Render Pipeline/Lit"));AssetDatabase.CreateAsset(material,path);}
                        material.name=fabric.name;
                        material.SetColor("_BaseColor",new Color(fabric.color[0],fabric.color[1],fabric.color[2]));
                        material.SetFloat("_Smoothness",1-fabric.roughness);material.SetFloat("_Metallic",0);material.SetFloat("_Cull",2);
                        if(!string.IsNullOrEmpty(fabric.texture))
                        {
                            material.SetTexture("_BaseMap",ImportTexture(source,id,folder,fabric.texture,false));
                            material.SetTextureScale("_BaseMap",Vector2.one);
                        }
                        else if(fabric.name=="Trouser")
                        {
                            material.SetTexture("_BaseMap",AssetDatabase.LoadAssetAtPath<Texture2D>(Root+"Materials/FabricWeave.png"));
                            material.SetTextureScale("_BaseMap",new Vector2(12,12));
                        }
                        if(!string.IsNullOrEmpty(fabric.normal))
                        {
                            material.SetTexture("_BumpMap",ImportTexture(source,id,folder,fabric.normal,true));
                            material.SetFloat("_BumpScale",1);material.EnableKeyword("_NORMALMAP");
                        }
                        EditorUtility.SetDirty(material);
                    }
                    foreach(var part in parts)
                    {
                        var names=part.weights.SelectMany(w=>w.names).Distinct().ToArray();
                        var indices=names.Select((n,i)=>(n,i)).ToDictionary(x=>x.n,x=>x.i);
                        var mesh=new Mesh{name=part.name,indexFormat=IndexFormat.UInt32,vertices=part.vertices,uv=part.uv};
                        mesh.boneWeights=part.weights.Select(w=>
                        {
                            var result=new BoneWeight();
                            for(int i=0;i<w.names.Length;i++)
                            {
                                int b=indices[w.names[i]];float value=w.values[i];
                                switch(i){case 0:result.boneIndex0=b;result.weight0=value;break;case 1:result.boneIndex1=b;result.weight1=value;break;case 2:result.boneIndex2=b;result.weight2=value;break;case 3:result.boneIndex3=b;result.weight3=value;break;}
                            }
                            return result;
                        }).ToArray();
                        mesh.bindposes=names.Select(n=>bones[n].worldToLocalMatrix*actor.transform.localToWorldMatrix).ToArray();
                        mesh.subMeshCount=part.materials.Length;
                        for(int i=0;i<part.materials.Length;i++)mesh.SetTriangles(part.triangles.Where(t=>t.material==i).SelectMany(t=>t.indices).ToArray(),i);
                        if(part.normals!=null&&part.normals.Length==part.vertices.Length)mesh.normals=part.normals;
                        else mesh.RecalculateNormals();
                        mesh.RecalculateTangents();mesh.RecalculateBounds();
                        SaveGarment(mesh,folder+part.name+".asset");
                    }
                    AttachPrepared(actor,id,parts.ToDictionary(p=>p.name,p=>p.weights.SelectMany(w=>w.names).Distinct().ToArray()));
                    PrefabUtility.SaveAsPrefabAsset(actor,Root+id+"/Character.prefab");
                    Debug.Log("CAST_WARDROBE_IMPORTED "+id+" vertices="+parts.Sum(m=>m.vertices.Length));
                }
                finally{PrefabUtility.UnloadPrefabContents(actor);}
            }
            AssetDatabase.SaveAssets();
            if(Array.IndexOf(Environment.GetCommandLineArgs(),"--wardrobe-preview")>=0)Validate();
        }

        public static void AttachPrepared(GameObject actor,string id,Dictionary<string,string[]> bindings=null)
        {
            if(!Characters.Contains(id))return;
            string folder=Root+id+"/wardrobe/";
            if(!AssetDatabase.LoadAssetAtPath<Mesh>(folder+Parts[0]+".asset"))return;
            if(bindings==null)
            {
                var prepared=AssetDatabase.LoadAssetAtPath<GameObject>(Root+id+"/Character.prefab").GetComponent<MetaHumanJointRig>();
                bindings=prepared.clothingObject.GetComponentsInChildren<SkinnedMeshRenderer>().ToDictionary(s=>s.name,s=>s.bones.Select(b=>b.name).ToArray());
            }
            var rig=actor.GetComponent<MetaHumanJointRig>();
            var bones=rig.bodyObject.GetComponentsInChildren<Transform>().GroupBy(t=>t.name).ToDictionary(g=>g.Key,g=>g.First());
            var old=rig.clothingObject;if(old)UnityEngine.Object.DestroyImmediate(old);
            var wardrobe=new GameObject("Tailored wardrobe");wardrobe.transform.SetParent(actor.transform,false);rig.clothingObject=wardrobe;
            SkinnedMeshRenderer trousers=null;
            for(int i=0;i<Parts.Length;i++)
            {
                var obj=new GameObject(Parts[i]);obj.transform.SetParent(wardrobe.transform,false);
                var skin=obj.AddComponent<SkinnedMeshRenderer>();var mesh=AssetDatabase.LoadAssetAtPath<Mesh>(folder+Parts[i]+".asset");
                skin.bones=bindings[Parts[i]].Select(n=>bones[n]).ToArray();
                skin.sharedMesh=mesh;skin.rootBone=bones["pelvis"];skin.quality=SkinQuality.Bone4;
                skin.sharedMaterials=Slots[i].Select(name=>AssetDatabase.LoadAssetAtPath<Material>(folder+name+".mat")).ToArray();
                skin.localBounds=new Bounds(new Vector3(0,.8f,0),new Vector3(2,2,2));
                if(i==0)trousers=skin;
            }
            AttachOriginalTop(actor,id);
            var cloth=actor.GetComponent<SeatedTrouserDeformation>()??actor.AddComponent<SeatedTrouserDeformation>();cloth.trousers=trousers;
            cloth.leftThigh=bones["thigh_l"];cloth.leftKnee=bones["calf_l"];cloth.leftFoot=bones["foot_l"];cloth.leftHand=bones["hand_l"];cloth.leftMiddle=bones["middle_01_l"];
            cloth.rightThigh=bones["thigh_r"];cloth.rightKnee=bones["calf_r"];cloth.rightFoot=bones["foot_r"];cloth.rightHand=bones["hand_r"];cloth.rightMiddle=bones["middle_01_r"];
        }
        public static void RestoreOriginalTops()
        {
            foreach(string id in SelectedCharacters())
            {
                var actor=PrefabUtility.LoadPrefabContents(Root+id+"/Character.prefab");
                try
                {
                    var rig=actor.GetComponent<MetaHumanJointRig>();
                    var rejected=rig.clothingObject.transform.Find("Tailored_Top");
                    if(rejected)UnityEngine.Object.DestroyImmediate(rejected.gameObject);
                    AttachOriginalTop(actor,id);
                    PrefabUtility.SaveAsPrefabAsset(actor,Root+id+"/Character.prefab");
                    Debug.Log("CAST_ORIGINAL_TOP_RESTORED "+id);
                }
                finally{PrefabUtility.UnloadPrefabContents(actor);}
            }
            AssetDatabase.SaveAssets();
            if(Array.IndexOf(Environment.GetCommandLineArgs(),"--wardrobe-preview")>=0)Validate();
        }
        public static void ImportShoeWeights()
        {
            string source=Argument("--wardrobe-source");
            foreach(string id in SelectedCharacters())
            {
                var data=JsonUtility.FromJson<Delivery>(File.ReadAllText(Path.Combine(source,id,"wardrobe.json")));
                var part=data.meshes.Single(m=>m.name=="Leather_Shoes");
                var actor=AssetDatabase.LoadAssetAtPath<GameObject>(Root+id+"/Character.prefab");
                var skin=actor.GetComponent<MetaHumanJointRig>().clothingObject.GetComponentsInChildren<SkinnedMeshRenderer>().Single(s=>s.name==part.name);
                var mesh=skin.sharedMesh;var vertices=mesh.vertices;
                if(vertices.Length!=part.vertices.Length||vertices.Where((v,i)=>Vector3.Distance(v,part.vertices[i])>.000001f).Any())
                    throw new InvalidOperationException(id+": shoe geometry changed; weights-only import requires the existing vertex order.");
                var indices=skin.bones.Select((b,i)=>(b.name,i)).ToDictionary(b=>b.name,b=>b.i);
                mesh.boneWeights=part.weights.Select(w=>
                {
                    var result=new BoneWeight();
                    for(int i=0;i<w.names.Length;i++)
                    {
                        int index=indices[w.names[i]];float value=w.values[i];
                        switch(i){case 0:result.boneIndex0=index;result.weight0=value;break;case 1:result.boneIndex1=index;result.weight1=value;break;case 2:result.boneIndex2=index;result.weight2=value;break;case 3:result.boneIndex3=index;result.weight3=value;break;}
                    }
                    return result;
                }).ToArray();
                EditorUtility.SetDirty(mesh);Debug.Log("CAST_SHOE_WEIGHTS_IMPORTED "+id);
            }
            AssetDatabase.SaveAssets();
            if(Array.IndexOf(Environment.GetCommandLineArgs(),"--wardrobe-preview")>=0)Validate();
        }
        static void AttachOriginalTop(GameObject actor,string id)
        {
            var rig=actor.GetComponent<MetaHumanJointRig>();
            var existing=rig.clothingObject.transform.Find("Original_Top");
            if(existing)UnityEngine.Object.DestroyImmediate(existing.gameObject);
            var model=UnityEngine.Object.Instantiate(AssetDatabase.LoadAssetAtPath<GameObject>(Root+id+"/models/Outfit.fbx"),actor.transform,false);
            try
            {
                var groups=model.GetComponentsInChildren<LODGroup>();
                var renderers=groups.Length>0?groups.SelectMany(g=>g.GetLODs()[0].renderers).OfType<SkinnedMeshRenderer>().Distinct():model.GetComponentsInChildren<SkinnedMeshRenderer>();
                var source=renderers.Single(s=>s.sharedMaterials.Any(m=>m&&m.name.Contains("Shirt")));
                var bones=rig.bodyObject.GetComponentsInChildren<Transform>().GroupBy(t=>t.name).ToDictionary(g=>g.Key,g=>g.First());
                var mesh=UnityEngine.Object.Instantiate(source.sharedMesh);mesh.name="Original_Top";
                var toActor=actor.transform.worldToLocalMatrix*source.transform.localToWorldMatrix;
                mesh.vertices=mesh.vertices.Select(toActor.MultiplyPoint3x4).ToArray();
                var normalMatrix=toActor.inverse.transpose;
                mesh.normals=mesh.normals.Select(n=>normalMatrix.MultiplyVector(n).normalized).ToArray();
                mesh.bindposes=mesh.bindposes.Select(b=>b*toActor.inverse).ToArray();
                var triangles=new List<int>();
                for(int i=0;i<source.sharedMaterials.Length;i++)
                    if(source.sharedMaterials[i]&&source.sharedMaterials[i].name.Contains("Shirt"))triangles.AddRange(mesh.GetTriangles(i));
                if(toActor.determinant<0)
                    for(int i=0;i<triangles.Count;i+=3){int first=triangles[i];triangles[i]=triangles[i+2];triangles[i+2]=first;}
                mesh.subMeshCount=1;mesh.SetTriangles(triangles,0);mesh.RecalculateTangents();mesh.RecalculateBounds();
                string path=Root+id+"/wardrobe/Original_Top.asset";SaveGarment(mesh,path);
                var top=new GameObject("Original_Top");top.transform.SetParent(rig.clothingObject.transform,false);
                var skin=top.AddComponent<SkinnedMeshRenderer>();skin.sharedMesh=AssetDatabase.LoadAssetAtPath<Mesh>(path);
                skin.bones=source.bones.Select(b=>bones[b.name]).ToArray();skin.rootBone=bones["pelvis"];
                skin.sharedMaterial=AssetDatabase.LoadAssetAtPath<Material>(Root+id+"/Casual_shirt.mat");
                skin.quality=SkinQuality.Bone4;skin.localBounds=new Bounds(new Vector3(0,.8f,0),new Vector3(2,2,2));
                rig.bodyObject.GetComponentInChildren<SkinnedMeshRenderer>().sharedMesh=AssetDatabase.LoadAssetAtPath<Mesh>(Root+id+"/ClothedBody.asset");
                rig.skin.sharedMesh=AssetDatabase.LoadAssetAtPath<GameObject>(Root+id+"/models/Face.fbx").GetComponentsInChildren<SkinnedMeshRenderer>().Single(s=>s.name==rig.skin.name).sharedMesh;
                Debug.Log("CAST_ORIGINAL_TOP_SOURCE "+id+" renderer="+source.name+" triangles="+triangles.Count/3);
            }
            finally{UnityEngine.Object.DestroyImmediate(model);}
        }
        public static void Validate()
        {
            string source=Argument("--wardrobe-source"),output=Argument("--wardrobe-preview");Directory.CreateDirectory(output);
            EditorSceneManager.OpenScene(BounceLightingSetup.ScenePath);
            LightProbes.Tetrahedralize();
            foreach(string id in SelectedCharacters())
            {
                var data=JsonUtility.FromJson<Delivery>(File.ReadAllText(Path.Combine(source,id,"wardrobe.json")));
                var actor=UnityEngine.Object.Instantiate(Resources.Load<GameObject>("MetaHumans/"+id));
                var baked=new Mesh();
                var camera=new GameObject("Wardrobe check "+id).AddComponent<Camera>();camera.enabled=false;camera.nearClipPlane=.02f;
                try
                {
                    actor.transform.SetPositionAndRotation(new Vector3(0,0,1.15f),Quaternion.Euler(0,180,0));
                    actor.AddComponent<AvatarSkinRendering>().Initialize(true);
                    var rig=actor.GetComponent<MetaHumanJointRig>();rig.Initialize();
                    foreach(var skin in actor.GetComponentsInChildren<SkinnedMeshRenderer>())
                    {skin.forceMatrixRecalculationPerRender=true;skin.updateWhenOffscreen=true;}
                    var bones=rig.bodyObject.GetComponentsInChildren<Transform>().GroupBy(t=>t.name).ToDictionary(g=>g.Key,g=>g.First());
                    var face=rig.faceObject.GetComponentsInChildren<Transform>().Where(t=>bones.ContainsKey(t.name)).ToArray();
                    var skins=rig.clothingObject.GetComponentsInChildren<SkinnedMeshRenderer>();
                    if(skins.Length!=3||actor.transform.Find("SkeletalMesh"))throw new InvalidOperationException(id+": old outfit was not replaced completely.");
                    float maximum=0;
                    foreach(var check in data.checks)
                    {
                        rig.seatedIdle.SampleAnimation(rig.bodyObject,check.time);
                        foreach(var bone in face)bone.SetPositionAndRotation(bones[bone.name].position,bones[bone.name].rotation);
                        foreach(var sample in check.meshes)
                        {
                            if(!Parts.Contains(sample.name))continue;
                            var skin=skins.Single(s=>s.name==sample.name);skin.BakeMesh(baked);var points=baked.vertices;
                            if(skin.bones.Any(b=>!b)||skin.sharedMaterials.Any(m=>!m||!m.shader.isSupported))throw new InvalidOperationException(id+": missing clothing binding or unsupported shader.");
                            float partMaximum=0;int worst=0;
                            for(int k=0;k<sample.indices.Length;k++)
                            {
                                var p=actor.transform.InverseTransformPoint(skin.transform.TransformPoint(points[sample.indices[k]]));
                                float error=Vector3.Distance(p,sample.positions[k]);
                                if(error>partMaximum){partMaximum=error;worst=sample.indices[k];}
                                maximum=Mathf.Max(maximum,error);
                            }
                            Debug.Log("CAST_WARDROBE_SKINNING "+id+" time="+check.time+" part="+sample.name+" error="+partMaximum+" vertex="+worst);
                        }
                        actor.GetComponent<SeatedTrouserDeformation>().ApplyPose(0);
                        foreach(bool side in new[]{false,true})
                        {
                            var focus=actor.transform.TransformPoint(new Vector3(0,.85f,.08f));
                            camera.fieldOfView=48;
                            camera.transform.position=focus+(side?actor.transform.right*1.85f:actor.transform.forward*1.85f)+Vector3.up*.06f;camera.transform.LookAt(focus);
                            Capture(camera,Path.Combine(output,id+"-"+(side?"side-":"front-")+check.time.ToString("0",System.Globalization.CultureInfo.InvariantCulture)+".png"));
                        }
                        if(Array.IndexOf(Environment.GetCommandLineArgs(),"--wardrobe-feet")>=0)
                        {
                            var foot=bones["foot_l"];var toe=bones["ball_l"];
                            var focus=(foot.position+toe.position)*.5f+Vector3.up*.035f;
                            camera.fieldOfView=45;camera.transform.position=focus-actor.transform.right*.65f+Vector3.up*.07f;camera.transform.LookAt(focus);
                            string stamp=check.time.ToString("0",System.Globalization.CultureInfo.InvariantCulture);
                            Capture(camera,Path.Combine(output,id+"-foot-"+stamp+".png"));
                            var body=rig.bodyObject.GetComponentInChildren<SkinnedMeshRenderer>();var covered=body.sharedMesh;
                            body.sharedMesh=AssetDatabase.LoadAssetAtPath<GameObject>(Root+id+"/models/Body.fbx").GetComponentsInChildren<SkinnedMeshRenderer>().Single(s=>s.name==body.name).sharedMesh;
                            foreach(var skin in skins)skin.enabled=false;
                            Capture(camera,Path.Combine(output,id+"-bare-foot-"+stamp+".png"));
                            body.sharedMesh=covered;foreach(var skin in skins)skin.enabled=true;
                            Debug.Log("CAST_FOOT_POSE "+id+" time="+check.time+" ankleAngle="+Vector3.Angle(bones["calf_l"].position-foot.position,toe.position-foot.position));
                        }
                    }
                    if(maximum>.006f)throw new InvalidOperationException(id+": Unity clothing differs from Blender by "+maximum+" m.");
                    Debug.Log("CAST_WARDROBE_VALIDATED "+id+" poses="+data.checks.Length+" nativeSkinningError="+maximum+" oldRenderers=0");
                    if(Array.IndexOf(Environment.GetCommandLineArgs(),"--wardrobe-ffmpeg")>=0)
                        Record(rig,bones,face,camera,Path.Combine(output,id+"-wardrobe.mp4"));
                }
                finally{UnityEngine.Object.DestroyImmediate(camera.gameObject);UnityEngine.Object.DestroyImmediate(baked);UnityEngine.Object.DestroyImmediate(actor);}
            }
        }
        static void Capture(Camera camera,string path)
        {
            var target=new RenderTexture(800,1000,24);var pixels=new Texture2D(800,1000,TextureFormat.RGB24,false);var previous=RenderTexture.active;
            try
            {
                camera.aspect=.8f;RenderPipeline.SubmitRenderRequest(camera,new RenderPipeline.StandardRequest{destination=target});
                RenderPipeline.SubmitRenderRequest(camera,new RenderPipeline.StandardRequest{destination=target});
                RenderTexture.active=target;pixels.ReadPixels(new Rect(0,0,800,1000),0,0);pixels.Apply();File.WriteAllBytes(path,pixels.EncodeToPNG());
            }
            finally{RenderTexture.active=previous;target.Release();UnityEngine.Object.DestroyImmediate(target);UnityEngine.Object.DestroyImmediate(pixels);}
        }
        static void Record(MetaHumanJointRig rig,Dictionary<string,Transform> bones,Transform[] face,Camera camera,string path)
        {
            // Stream a short inspection directly to the encoder: no image sequence
            // or full-length idle recording is written to the user's disk.
            const int width=480,height=600,fps=15;
            var start=new System.Diagnostics.ProcessStartInfo
            {
                FileName=Argument("--wardrobe-ffmpeg"),UseShellExecute=false,CreateNoWindow=true,
                RedirectStandardInput=true,RedirectStandardError=true,
                Arguments="-y -loglevel error -f rawvideo -pixel_format rgb24 -video_size 480x600 -framerate 15 -i pipe:0 -vf vflip -c:v libx264 -preset fast -crf 20 -pix_fmt yuv420p \""+path+"\""
            };
            using(var encoder=System.Diagnostics.Process.Start(start))
            {
                var errors=encoder.StandardError.ReadToEndAsync();
                var target=new RenderTexture(width,height,24);var pixels=new Texture2D(width,height,TextureFormat.RGB24,false);
                var previous=RenderTexture.active;
                try
                {
                    for(int frame=0;frame<fps*6;frame++)
                    {
                        bool side=frame>=fps*3;
                        float time=side?81+(frame-fps*3)/(float)fps:10+frame/(float)fps;
                        rig.seatedIdle.SampleAnimation(rig.bodyObject,time);
                        foreach(var bone in face)bone.SetPositionAndRotation(bones[bone.name].position,bones[bone.name].rotation);
                        rig.GetComponent<SeatedTrouserDeformation>().ApplyPose(0);
                        var focus=rig.transform.TransformPoint(new Vector3(0,.85f,.08f));
                        camera.transform.position=focus+(side?rig.transform.right:rig.transform.forward)*1.85f+Vector3.up*.06f;
                        camera.transform.LookAt(focus);camera.aspect=width/(float)height;
                        RenderPipeline.SubmitRenderRequest(camera,new RenderPipeline.StandardRequest{destination=target});
                        RenderPipeline.SubmitRenderRequest(camera,new RenderPipeline.StandardRequest{destination=target});
                        RenderTexture.active=target;pixels.ReadPixels(new Rect(0,0,width,height),0,0);pixels.Apply();
                        var bytes=pixels.GetRawTextureData<byte>().ToArray();encoder.StandardInput.BaseStream.Write(bytes,0,bytes.Length);
                        if(frame%fps==0)Debug.Log("CAST_WARDROBE_VIDEO "+rig.name+" frame="+frame);
                    }
                }
                finally
                {
                    encoder.StandardInput.Close();RenderTexture.active=previous;target.Release();
                    UnityEngine.Object.DestroyImmediate(target);UnityEngine.Object.DestroyImmediate(pixels);
                }
                encoder.WaitForExit();
                if(encoder.ExitCode!=0)throw new InvalidOperationException("Wardrobe video encoding failed: "+errors.Result);
            }
        }
        static string Argument(string name)
        {var args=Environment.GetCommandLineArgs();int at=Array.IndexOf(args,name);if(at<0||at+1>=args.Length)throw new ArgumentException(name+" requires a directory.");return args[at+1];}
        static IEnumerable<string> SelectedCharacters()
        {
            var args=Environment.GetCommandLineArgs();int at=Array.IndexOf(args,"--character-id");
            if(at<0)return Characters;
            if(at+1>=args.Length||!Characters.Contains(args[at+1]))throw new ArgumentException("--character-id must be alex, nikola or stefan.");
            return new[]{args[at+1]};
        }
        static Texture2D ImportTexture(string source,string id,string folder,string file,bool normal)
        {
            string path=folder+Path.GetFileName(file);
            File.Copy(Path.Combine(source,id,file),path,true);AssetDatabase.ImportAsset(path);
            var importer=(TextureImporter)AssetImporter.GetAtPath(path);
            importer.textureType=normal?TextureImporterType.NormalMap:TextureImporterType.Default;
            importer.sRGBTexture=!normal;importer.maxTextureSize=1024;importer.SaveAndReimport();
            return AssetDatabase.LoadAssetAtPath<Texture2D>(path);
        }
        static void SaveGarment(Mesh value,string path)
        {
            var old=AssetDatabase.LoadAssetAtPath<Mesh>(path);
            if(!old){AssetDatabase.CreateAsset(value,path);return;}
            old.Clear();old.indexFormat=value.indexFormat;old.vertices=value.vertices;old.normals=value.normals;
            old.tangents=value.tangents;old.uv=value.uv;old.boneWeights=value.boneWeights;old.bindposes=value.bindposes;
            old.subMeshCount=value.subMeshCount;
            for(int i=0;i<value.subMeshCount;i++)old.SetTriangles(value.GetTriangles(i),i);
            old.bounds=value.bounds;EditorUtility.SetDirty(old);UnityEngine.Object.DestroyImmediate(value);
        }
    }
}
