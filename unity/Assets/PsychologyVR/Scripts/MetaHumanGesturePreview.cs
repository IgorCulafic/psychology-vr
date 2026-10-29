using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEngine;

namespace PsychologyVR
{
    // Explicit offline scene check. No service requests or generated speech.
    public static class MetaHumanGesturePreview
    {
        [Serializable] public sealed class Take {public string id,emotion;public float start,duration,maxWristStep,worstTime;}
        [Serializable] public sealed class Report
        {
            public bool passed,audioPlayed,speechGestureDuringAudio,interrupted,overlapRejected;
            public int clips,frames;public float legPositionError,legAngleError,pauseDrift,pauseAngle,actorDrift,maxWristStep,footMotion;
            public string worstGesture;public float worstTime,worstDeltaTime;
            public Take[] takes;
        }
        public static IEnumerator Run(PrototypeSession session,PerformanceDriver performance,FacialPerformance face,AudioSource voice,Action<Camera,string> capture,string folder)
        {
            var rig=performance.GetComponent<MetaHumanJointRig>();
            if(!rig.gestureLibrary||rig.gestureLibrary.gestures.Length==0)throw new InvalidOperationException("The selected patient has no prepared gesture bank.");
            rig.AutomaticGestures=false;
            var body=rig.bodyObject.GetComponentsInChildren<Transform>().ToDictionary(t=>t.name);
            var check=UnityEngine.Object.Instantiate(rig.bodyObject);check.SetActive(false);
            var reference=check.GetComponentsInChildren<Transform>().ToDictionary(t=>t.name);
            string[] lower={"pelvis","thigh_l","calf_l","foot_l","ball_l","thigh_r","calf_r","foot_r","ball_r"};
            var actorStart=rig.transform.position;var footStart=body["foot_r"].position;
            var report=new Report();var takes=new List<Take>();
            var cameras=new[]{new GameObject("Gesture front").AddComponent<Camera>(),new GameObject("Gesture side").AddComponent<Camera>()};
            var focus=rig.transform.TransformPoint(new Vector3(0,1.02f,0));
            for(int i=0;i<cameras.Length;i++)
            {
                var c=cameras[i];c.enabled=false;c.nearClipPlane=.02f;
                c.transform.position=focus+(i==0?rig.transform.forward:(rig.transform.right+rig.transform.forward*.3f).normalized)*2.15f;
                c.transform.LookAt(focus);
            }
            bool record=Array.IndexOf(Environment.GetCommandLineArgs(),"--gesture-recording")>=0;
            var target=new RenderTexture(768,768,24);var pixels=new Texture2D(768,768,TextureFormat.RGB24,false);
            Directory.CreateDirectory(Path.Combine(folder,"frames"));Directory.CreateDirectory(Path.Combine(folder,"side-frames"));
            Time.captureFramerate=30;
            float movieTime=0;int movieFrame=0;
            bool pauseChecked=false;
            foreach(var gesture in rig.gestureLibrary.gestures)
            {
                string emotion=gesture.id=="neck_touch"?"afraid":gesture.kind==MetaHumanGestureLibrary.Kind.Tension?"anxious":gesture.kind==MetaHumanGestureLibrary.Kind.Thoughtful?"sad":"neutral";
                performance.Apply(emotion,.45f,"none",true);
                if(!rig.PlayGesture(gesture.id))throw new InvalidOperationException("Gesture did not start: "+gesture.id);
                var take=new Take{id=gesture.id,emotion=emotion,start=movieTime,duration=gesture.clip.length+.7f};takes.Add(take);
                Debug.Log("SEATED_GESTURE_PREVIEW "+gesture.id);
                var lastLeft=body["hand_l"].position;var lastRight=body["hand_r"].position;
                int frames=Mathf.CeilToInt((gesture.clip.length+.7f)*30);
                for(int frame=0;frame<frames;frame++)
                {
                    yield return new WaitForEndOfFrame();report.frames++;movieTime+=Time.deltaTime;
                    rig.seatedIdle.SampleAnimation(check,rig.IdleTime);
                    foreach(string n in lower)
                    {
                        report.legPositionError=Mathf.Max(report.legPositionError,Vector3.Distance(body[n].localPosition,reference[n].localPosition));
                        report.legAngleError=Mathf.Max(report.legAngleError,Quaternion.Angle(body[n].localRotation,reference[n].localRotation));
                    }
                    float step=Mathf.Max(Vector3.Distance(lastLeft,body["hand_l"].position),Vector3.Distance(lastRight,body["hand_r"].position));
                    if(step>take.maxWristStep){take.maxWristStep=step;take.worstTime=frame/30f;}
                    if(step>report.maxWristStep){report.maxWristStep=step;report.worstGesture=gesture.id;report.worstTime=frame/30f;report.worstDeltaTime=Time.deltaTime;}
                    lastLeft=body["hand_l"].position;lastRight=body["hand_r"].position;
                    report.actorDrift=Mathf.Max(report.actorDrift,Vector3.Distance(actorStart,rig.transform.position));
                    report.footMotion=Mathf.Max(report.footMotion,Vector3.Distance(footStart,body["foot_r"].position));
                    if(frame==frames/2)
                    {
                        capture(cameras[0],Path.Combine(folder,gesture.id+"-front.png"));capture(cameras[1],Path.Combine(folder,gesture.id+"-side.png"));
                    }
                    if(record&&frame%2==0)
                    {
                        Record(cameras[0],target,pixels,Path.Combine(folder,"frames",movieFrame.ToString("D6")+".jpg"));
                        Record(cameras[1],target,pixels,Path.Combine(folder,"side-frames",movieFrame.ToString("D6")+".jpg"));movieFrame++;
                    }
                    if(!pauseChecked&&gesture.id=="fold_arms"&&frame==45)
                    {
                        session.SetMenuOpen(true);var all=rig.bodyObject.GetComponentsInChildren<Transform>();
                        var p=all.Select(t=>t.position).ToArray();var q=all.Select(t=>t.rotation).ToArray();
                        for(int k=0;k<20;k++)
                        {
                            yield return new WaitForEndOfFrame();
                            for(int j=0;j<all.Length;j++)
                            {
                                report.pauseDrift=Mathf.Max(report.pauseDrift,Vector3.Distance(p[j],all[j].position));
                                report.pauseAngle=Mathf.Max(report.pauseAngle,Quaternion.Angle(q[j],all[j].rotation));
                            }
                        }
                        session.SetMenuOpen(false);pauseChecked=true;
                    }
                }
                report.clips++;
            }
            // Real AudioSource playback checks automatic speech scheduling separately
            // from fixed-frame movie capture; no preview speaking override is used.
            Time.captureFramerate=0;rig.AutomaticGestures=true;
            performance.Apply("neutral",0,"none",true);
            voice.clip=Resources.Load<AudioClip>("FaceDemo/speech");
            if(!voice.clip)throw new InvalidOperationException("The offline speech recording is missing.");
            voice.loop=true;face.BeginSpeech(voice,null);voice.Play();
            float elapsed=0;
            while(elapsed<14)
            {
                yield return null;elapsed+=Time.deltaTime;
                report.audioPlayed|=voice.isPlaying;
                if(voice.isPlaying&&rig.ActiveGesture.StartsWith("speech_"))report.speechGestureDuringAudio=true;
                if(report.speechGestureDuringAudio&&rig.GestureTime>.9f)break;
            }
            bool hadActive=rig.ActiveGesture!="";string speechGesture=rig.ActiveGesture;
            report.overlapRejected=!rig.PlayGesture("temple_touch")&&rig.ActiveGesture==speechGesture;
            rig.AutomaticGestures=false;
            voice.Stop();voice.loop=false;face.StopSpeech();performance.StopGesture(true);
            yield return new WaitForSeconds(1);
            report.interrupted=hadActive&&rig.ActiveGesture=="";
            report.takes=takes.ToArray();
            report.passed=report.clips==rig.gestureLibrary.gestures.Length&&report.legPositionError<.00001f&&report.legAngleError<.1f&&report.actorDrift<.00001f&&report.pauseDrift<.00001f&&report.pauseAngle<.1f&&report.footMotion>.01f&&report.maxWristStep<.065f&&report.audioPlayed&&report.speechGestureDuringAudio&&report.interrupted&&report.overlapRejected;
            File.WriteAllText(Path.Combine(folder,"gesture-report.json"),JsonUtility.ToJson(report,true));
            Debug.Log("SEATED_GESTURES_CHECK "+JsonUtility.ToJson(report));
            foreach(var camera in cameras)UnityEngine.Object.Destroy(camera.gameObject);
            UnityEngine.Object.Destroy(check);target.Release();UnityEngine.Object.Destroy(target);UnityEngine.Object.Destroy(pixels);
            if(!report.passed)Application.Quit(2);
        }
        static void Record(Camera camera,RenderTexture target,Texture2D pixels,string path)
        {
            float aspect=camera.aspect;camera.aspect=1;
            UnityEngine.Rendering.RenderPipeline.SubmitRenderRequest(camera,new UnityEngine.Rendering.RenderPipeline.StandardRequest{destination=target});
            var previous=RenderTexture.active;RenderTexture.active=target;
            pixels.ReadPixels(new Rect(0,0,768,768),0,0);pixels.Apply();File.WriteAllBytes(path,pixels.EncodeToJPG(85));
            RenderTexture.active=previous;camera.aspect=aspect;
        }
    }
}
