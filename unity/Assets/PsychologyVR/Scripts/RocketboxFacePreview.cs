using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;

namespace PsychologyVR
{
    // Isolated candidate audition. Does not change the consultation controller.
    public sealed class RocketboxFacePreview : MonoBehaviour
    {
        public GameObject[] candidates;
        public Camera view;
        IEnumerator Start()
        {
            var args = Environment.GetCommandLineArgs();
            string Arg(string key, string fallback) { int i = Array.IndexOf(args, key); return i >= 0 && i+1 < args.Length ? args[i+1] : fallback; }
            string folder = Arg("--data", ""), output = Arg("--output", "");
            int candidate = int.Parse(Arg("--candidate", "1"))-1;
            int limit = int.Parse(Arg("--frames", "0"));
            var take = RecordedFaceTake.Load(Path.Combine(folder, "performance.json"));
            for (int i=0;i<candidates.Length;i++) candidates[i].SetActive(i==candidate);
            var actor = candidates[candidate];
            foreach (var animator in actor.GetComponentsInChildren<Animator>()) animator.enabled=false;
            var meshes = actor.GetComponentsInChildren<SkinnedMeshRenderer>();
            Transform head=null, left=null, right=null;
            foreach(var t in actor.GetComponentsInChildren<Transform>())
            {
                if(t.name=="Bip01 Head") head=t;
                if(t.name=="Bip01 LEye") left=t;
                if(t.name=="Bip01 REye") right=t;
            }
            if(!head || !left || !right) throw new InvalidDataException("Missing Rocketbox head/eyes");
            var bounds=meshes[0].bounds; foreach(var mesh in meshes) bounds.Encapsulate(mesh.bounds);
            actor.transform.localScale *= 1.8f / bounds.size.y;
            Vector3 eyes=(left.position+right.position)*.5f;
            Vector3 forward=eyes-head.position; forward.y=0; forward.Normalize();
            var binding=new RecordedHeadBinding(head,forward);
            var focus=eyes-Vector3.up*.035f;
            view.transform.position=focus+forward*.60f;
            view.transform.LookAt(focus); view.fieldOfView=33;
            var source=new Dictionary<string,float>();
            var channels=new List<(SkinnedMeshRenderer mesh,int index,string source)>();
            foreach(var mesh in meshes)
                for(int i=0;i<mesh.sharedMesh.blendShapeCount;i++)
                {
                    mesh.SetBlendShapeWeight(i,0);
                    string key=RecordedFaceMapping.ShapeName(mesh.sharedMesh.GetBlendShapeName(i));
                    if(!key.StartsWith("AK_")) continue;
                    key=key.Substring(6); key=char.ToLowerInvariant(key[0])+key.Substring(1);
                    // Match the existing baseline: gaze remains at rest for this comparison.
                    if(key.StartsWith("eyeLook")) continue;
                    if(Array.IndexOf(take.names,key)>=0) channels.Add((mesh,i,key));
                }
            if(channels.Count<40) throw new InvalidDataException("Insufficient mapped face shapes: "+channels.Count);
            Directory.CreateDirectory(output);
            var rt=new RenderTexture(400,400,24);
            var pixels=new Texture2D(400,400,TextureFormat.RGB24,false);
            view.targetTexture=rt;
            int count=limit>0?Math.Min(limit,take.frames.Length):take.frames.Length;
            for(int frame=0;frame<count;frame++)
            {
                float time=frame/take.fps;
                take.Sample(time,source);
                foreach(var channel in channels)
                    channel.mesh.SetBlendShapeWeight(channel.index, source.TryGetValue(channel.source,out float value)?value*100:0);
                // Jaw is already included in AK_JawOpen. Do not rotate it a second time.
                binding.Apply(take.SampleHead(time));
                yield return new WaitForEndOfFrame();
                RenderPipeline.SubmitRenderRequest(view,new UniversalRenderPipeline.SingleCameraRequest{destination=rt});
                RenderTexture.active=rt; pixels.ReadPixels(new Rect(0,0,400,400),0,0); pixels.Apply(); RenderTexture.active=null;
                File.WriteAllBytes(Path.Combine(output,frame.ToString("D5")+".jpg"),pixels.EncodeToJPG(94));
            }
            Debug.Log("ROCKETBOX_RENDER_OK candidate="+(candidate+1)+" frames="+count+" channels="+channels.Count);
            rt.Release(); Destroy(pixels); Application.Quit();
        }
    }
}
