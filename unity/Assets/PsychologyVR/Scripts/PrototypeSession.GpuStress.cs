using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using UnityEngine;
using UnityEngine.Rendering.Universal;

namespace PsychologyVR
{
    // Explicit diagnostic flag only; normal desktop/VR rendering is unchanged.
    public partial class PrototypeSession
    {
        void ConfigureHeadsetFreeStress()
        {
            var args=Environment.GetCommandLineArgs();
            if(Array.IndexOf(args,"--headset-free-stress")<0)return;
            int at=Array.IndexOf(args,"--stress-bridge");
            if(at>=0&&at+1<args.Length&&Uri.TryCreate(args[at+1],UriKind.Absolute,out var url)&&url.Scheme=="http"&&url.Host=="127.0.0.1")serviceUrl=args[at+1];
        }
        [Serializable] class GpuStressReport
        {
            public string mode="Synthetic dual-view rendering; no OpenXR/Quest Link compositor",status;
            public int eyeWidth=3000,eyeHeight=3000,requestedMsaa=4,buffersPerEye=3,completedTurns;
            public int actualMsaa; public float firstFrameTime,p50FrameMs,p95FrameMs;
            public bool passed;
            public List<float> firstAudioSeconds=new List<float>(),turnSeconds=new List<float>();
            public List<string> errors=new List<string>();
        }
        IEnumerator HeadsetFreeStress()
        {
            var args=Environment.GetCommandLineArgs();int at=Array.IndexOf(args,"--stress-report");
            if(at<0||at+1>=args.Length){Debug.LogError("GPU_STRESS missing report path");Application.Quit(2);yield break;}
            string output=Path.GetFullPath(args[at+1]);var report=new GpuStressReport();
            int sizeAt=Array.IndexOf(args,"--stress-eye-size");
            if(sizeAt>=0&&sizeAt+1<args.Length&&int.TryParse(args[sizeAt+1],out int size))report.eyeWidth=report.eyeHeight=Mathf.Clamp(size,1024,3500);
            float deadline=Time.realtimeSinceStartup+40;
            while(!CanSubmit&&Time.realtimeSinceStartup<deadline)yield return null;
            if(!CanSubmit){report.status="Service connection failed: "+Status;File.WriteAllText(output,JsonUtility.ToJson(report,true));Application.Quit(3);yield break;}
            SetMenuOpen(false);voice.volume=0; // Exercise actual playback/acknowledgements quietly; do not change saved volume.
            QualitySettings.vSyncCount=0;Application.targetFrameRate=90;
            var load=gameObject.AddComponent<SyntheticEyeLoad>();load.Initialize(view,report.eyeWidth,report.eyeHeight,report.buffersPerEye);
            report.actualMsaa=load.ActualMsaa;
            yield return new WaitForSecondsRealtime(12);
            Debug.Log("GPU_STRESS_RENDER_READY "+report.eyeWidth+"x"+report.eyeHeight+"x2 msaa="+report.actualMsaa);
            load.Measure=true;
            string[] prompts={
                "Dobar dan. Kako se osjećaš danas?",
                "Kako je izgledao tvoj dan prije dolaska ovdje? Možeš li mi dati nekoliko konkretnih detalja?",
                "Šta obično voliš da jedeš i da li nešto sam spremaš?",
                "Spomenuo si da ti nije lako. Šta te u posljednje vrijeme najviše naljuti?",
                "Razumijem. Da li je bilo i nekog malog, prijatnog trenutka ove sedmice?",
                "Možemo polako. Šta bi volio da ja bolje razumijem o tvom svakodnevnom životu?"
            };
            int turns=prompts.Length,turnAt=Array.IndexOf(args,"--stress-turns");
            if(turnAt>=0&&turnAt+1<args.Length&&int.TryParse(args[turnAt+1],out int requested))turns=Mathf.Clamp(requested,1,prompts.Length);
            for(int turn=0;turn<turns;turn++)
            {
                string prompt=prompts[turn];
                float began=Time.realtimeSinceStartup,first=-1;Submit(prompt);deadline=began+240;
                while(busy&&Time.realtimeSinceStartup<deadline)
                {
                    if(voice.isPlaying&&first<0)first=Time.realtimeSinceStartup-began;
                    yield return null;
                }
                if(busy||first<0||Status.StartsWith("Reply preparation stopped")||Status.Contains("error"))
                {report.errors.Add("Turn "+report.completedTurns+": "+Status);if(busy)Interrupt(false);break;}
                report.completedTurns++;report.firstAudioSeconds.Add(first);report.turnSeconds.Add(Time.realtimeSinceStartup-began);
                Debug.Log("GPU_STRESS_TURN "+report.completedTurns+" firstAudio="+first+" total="+(Time.realtimeSinceStartup-began));
                yield return new WaitForSecondsRealtime(2);
            }
            yield return new WaitForSecondsRealtime(8);load.Measure=false;
            load.FrameTimes.Sort();
            if(load.FrameTimes.Count>0){report.p50FrameMs=load.FrameTimes[load.FrameTimes.Count/2];report.p95FrameMs=load.FrameTimes[Mathf.Min(load.FrameTimes.Count-1,(int)(load.FrameTimes.Count*.95f))];}
            report.passed=report.completedTurns==turns&&report.errors.Count==0;report.status=Status;
            File.WriteAllText(output,JsonUtility.ToJson(report,true));Debug.Log(report.passed?"GPU_STRESS_OK":"GPU_STRESS_FAILED");
            Application.Quit(report.passed?0:4);
        }
    }

    public class SyntheticEyeLoad:MonoBehaviour
    {
        Camera source; readonly List<Camera> eyes=new List<Camera>();readonly List<RenderTexture[]> buffers=new List<RenderTexture[]>();int frame;
        public bool Measure;public int ActualMsaa;public readonly List<float> FrameTimes=new List<float>();
        public void Initialize(Camera camera,int width,int height,int count)
        {
            source=camera;
            for(int side=0;side<2;side++)
            {
                var eye=new GameObject("Synthetic eye "+side).AddComponent<Camera>();eye.CopyFrom(camera);eye.stereoTargetEye=StereoTargetEyeMask.None;eye.depth=camera.depth-2+side;
                eye.allowHDR=true;eye.allowMSAA=true;eye.fieldOfView=100;
                var data=eye.GetUniversalAdditionalCameraData();data.renderPostProcessing=true;data.volumeLayerMask=camera.GetUniversalAdditionalCameraData().volumeLayerMask;data.volumeTrigger=eye.transform;
                eye.SetVolumeFrameworkUpdateMode(VolumeFrameworkUpdateMode.EveryFrame);
                var ring=new RenderTexture[count];
                for(int i=0;i<count;i++)
                {
                    ring[i]=new RenderTexture(width,height,24,RenderTextureFormat.ARGBHalf){antiAliasing=4,name="Stress eye "+side+" buffer "+i};
                    if(!ring[i].Create())throw new InvalidOperationException("Could not create synthetic eye buffer");
                    ActualMsaa=ring[i].antiAliasing;
                }
                eyes.Add(eye);buffers.Add(ring);eye.targetTexture=ring[0];
            }
        }
        void LateUpdate()
        {
            for(int i=0;i<eyes.Count;i++)
            {
                eyes[i].transform.SetPositionAndRotation(source.transform.position+source.transform.right*(i==0?-.032f:.032f),source.transform.rotation*Quaternion.Euler(0,Mathf.Sin(Time.unscaledTime*.12f)*12,0));
                eyes[i].targetTexture=buffers[i][frame%buffers[i].Length];
            }
            frame++;if(Measure)FrameTimes.Add(Time.unscaledDeltaTime*1000);
        }
        void OnDestroy()
        {
            foreach(var eye in eyes)if(eye)Destroy(eye.gameObject);
            foreach(var ring in buffers)foreach(var target in ring){target.Release();Destroy(target);}
        }
    }
}
