using System;
using System.Collections;
using System.IO;
using System.Linq;
using UnityEngine;

namespace PsychologyVR
{
    // Explicit, service-free check in Consultation; captures stay outside Assets.
    public static class MetaHumanIdlePreview
    {
        [Serializable] public sealed class Report
        {
            public float duration,pelvisDrift,handMotion,footMotion,emotionHandMotion,pausePositionDrift,pauseAngleDrift,loopSeamAngle,headSeamDistance,shoulderSeamDistance,shoulderSeamAngle;
            public float actorDrift,loopSeamPosition;
            public int frames,loops,faceBindings;
            public int recordedFrames;
            public bool passed;
        }

        public static IEnumerator Run(PrototypeSession session,PerformanceDriver performance,FacialPerformance face,Action<Camera,string> capture,string folder)
        {
            var rig=performance.GetComponent<MetaHumanJointRig>();
            rig.AutomaticGestures=false;
            bool baseline=Array.IndexOf(Environment.GetCommandLineArgs(),"--idle-baseline")>=0;
            if(!baseline&&!rig.seatedIdle)throw new InvalidOperationException(rig.name+" has no recorded seated idle.");
            bool record=Array.IndexOf(Environment.GetCommandLineArgs(),"--idle-recording")>=0;
            if(record)Time.captureFramerate=30;
            performance.PausePerformance(true);
            rig.RestartSeatedIdle();
            // Let the renderer refresh its skinned buffers before capturing pose zero.
            yield return null;
            var body=rig.bodyObject.GetComponentsInChildren<Transform>().ToDictionary(t=>t.name);
            var shoulders=rig.faceObject.GetComponentsInChildren<Transform>().Where(t=>body.ContainsKey(t.name)&&(t.name.StartsWith("clavicle_")||t.name.StartsWith("upperarm_"))).ToArray();
            var hip=body["pelvis"];var hand=body["hand_r"];var foot=body["foot_r"];
            var report=new Report{duration=rig.seatedIdle?rig.seatedIdle.length:0,faceBindings=face.ShapeBindingCount};
            var pelvis=hip.position;var firstHand=hand.position;var firstFoot=foot.position;
            var actorPosition=rig.transform.position;
            var front=new GameObject("Idle preview front").AddComponent<Camera>();front.enabled=false;front.nearClipPlane=.02f;
            var side=new GameObject("Idle preview side").AddComponent<Camera>();side.enabled=false;side.nearClipPlane=.02f;
            var focus=hip.position+Vector3.up*.32f;
            front.transform.position=focus+rig.transform.forward*2.1f+Vector3.up*.10f;front.transform.LookAt(focus);
            side.transform.position=focus+rig.transform.right*2.1f+Vector3.up*.10f;side.transform.LookAt(focus);
            capture(front,Path.Combine(folder,"idle-front.png"));capture(side,Path.Combine(folder,"idle-side.png"));
            if(baseline)
            {
                UnityEngine.Object.Destroy(front.gameObject);UnityEngine.Object.Destroy(side.gameObject);
                File.WriteAllText(Path.Combine(folder,"baseline-complete.txt"),"Consultation static seating captured; no idle test run.");
                yield break;
            }
            RenderTexture movieTarget=null;Texture2D moviePixels=null;
            if(record)
            {
                Directory.CreateDirectory(Path.Combine(folder,"frames"));
                Directory.CreateDirectory(Path.Combine(folder,"side-frames"));
                movieTarget=new RenderTexture(960,960,24);moviePixels=new Texture2D(960,960,TextureFormat.RGB24,false);
                RecordFrame(front,movieTarget,moviePixels,Path.Combine(folder,"frames","000000.jpg"));report.recordedFrames++;
                RecordFrame(side,movieTarget,moviePixels,Path.Combine(folder,"side-frames","000000.jpg"));
            }
            performance.PausePerformance(false);
            float elapsed=0,pauseElapsed=0,nextProgress=15;bool pauseStarted=false,pauseFinished=false;
            Vector3[] pausedP=null;Quaternion[] pausedQ=null;
            var transforms=rig.bodyObject.GetComponentsInChildren<Transform>().Concat(rig.faceObject.GetComponentsInChildren<Transform>()).ToArray();
            var emotionStart=hand.position;
            float[] beatTimes={10,16,22,34};string[] emotions={"angry","afraid","crying","neutral"};
            while(elapsed<report.duration*2+2)
            {
                yield return null;report.frames++;
                if(elapsed>=(record?report.duration+28:28)&&!pauseFinished)
                {
                    if(!pauseStarted)
                    {
                        session.SetMenuOpen(true);pauseStarted=true;
                        pausedP=transforms.Select(t=>t.position).ToArray();pausedQ=transforms.Select(t=>t.rotation).ToArray();
                    }
                    else
                    {
                        for(int i=0;i<transforms.Length;i++)
                        {
                            report.pausePositionDrift=Mathf.Max(report.pausePositionDrift,Vector3.Distance(pausedP[i],transforms[i].position));
                            report.pauseAngleDrift=Mathf.Max(report.pauseAngleDrift,Quaternion.Angle(pausedQ[i],transforms[i].rotation));
                        }
                        pauseElapsed+=Time.unscaledDeltaTime;
                        if(pauseElapsed>=1){session.SetMenuOpen(false);pauseFinished=true;}
                    }
                    continue;
                }
                float previous=elapsed;elapsed+=Time.deltaTime;
                if(record&&elapsed<report.duration&&report.frames%2==0)
                {
                    RecordFrame(front,movieTarget,moviePixels,Path.Combine(folder,"frames",report.recordedFrames.ToString("D6")+".jpg"));
                    RecordFrame(side,movieTarget,moviePixels,Path.Combine(folder,"side-frames",report.recordedFrames.ToString("D6")+".jpg"));
                    report.recordedFrames++;
                }
                if(previous<15&&elapsed>=15)
                {capture(front,Path.Combine(folder,"idle-mid-front.png"));capture(side,Path.Combine(folder,"idle-mid-side.png"));}
                if(previous<83&&elapsed>=83)
                {capture(front,Path.Combine(folder,"idle-gesture-front.png"));capture(side,Path.Combine(folder,"idle-gesture-side.png"));}
                if(previous<125&&elapsed>=125)
                {capture(front,Path.Combine(folder,"idle-feet-front.png"));capture(side,Path.Combine(folder,"idle-feet-side.png"));}
                if(elapsed>=nextProgress){Debug.Log("METAHUMAN_IDLE_PROGRESS seconds="+elapsed+" frames="+report.frames);nextProgress+=15;}
                for(int i=0;i<beatTimes.Length;i++)
                    if(previous<beatTimes[i]+(record?report.duration:0)&&elapsed>=beatTimes[i]+(record?report.duration:0)){performance.Apply(emotions[i],emotions[i]=="neutral"?0:1,"none",true);emotionStart=hand.position;}
                report.pelvisDrift=Mathf.Max(report.pelvisDrift,Vector3.Distance(pelvis,hip.position));
                report.actorDrift=Mathf.Max(report.actorDrift,Vector3.Distance(actorPosition,rig.transform.position));
                report.handMotion=Mathf.Max(report.handMotion,Vector3.Distance(firstHand,hand.position));
                report.footMotion=Mathf.Max(report.footMotion,Vector3.Distance(firstFoot,foot.position));
                if(performance.Emotion!="neutral")report.emotionHandMotion=Mathf.Max(report.emotionHandMotion,Vector3.Distance(emotionStart,hand.position));
                report.headSeamDistance=Mathf.Max(report.headSeamDistance,Vector3.Distance(rig.Head.position,body["head"].position));
                foreach(var shoulder in shoulders)
                {
                    report.shoulderSeamDistance=Mathf.Max(report.shoulderSeamDistance,Vector3.Distance(shoulder.position,body[shoulder.name].position));
                    report.shoulderSeamAngle=Mathf.Max(report.shoulderSeamAngle,Quaternion.Angle(shoulder.rotation,body[shoulder.name].rotation));
                }
            }
            // The same body clip is sampled on both sides of the loop boundary.
            var check=UnityEngine.Object.Instantiate(rig.bodyObject);check.SetActive(false);rig.seatedIdle.SampleAnimation(check,0);
            var checkBones=check.GetComponentsInChildren<Transform>();var firstQ=checkBones.Select(t=>t.localRotation).ToArray();
            var firstP=checkBones.Select(t=>t.localPosition).ToArray();
            rig.seatedIdle.SampleAnimation(check,report.duration);
            for(int i=0;i<checkBones.Length;i++)report.loopSeamAngle=Mathf.Max(report.loopSeamAngle,Quaternion.Angle(firstQ[i],checkBones[i].localRotation));
            for(int i=0;i<checkBones.Length;i++)report.loopSeamPosition=Mathf.Max(report.loopSeamPosition,Vector3.Distance(firstP[i],checkBones[i].localPosition));
            UnityEngine.Object.Destroy(check);report.loops=2;
            report.passed=report.pelvisDrift>.001f&&report.pelvisDrift<.055f&&report.actorDrift<.001f&&report.loopSeamPosition<.0001f&&report.handMotion>.03f&&report.footMotion>.03f&&report.emotionHandMotion>.02f&&report.pausePositionDrift<.001f&&report.pauseAngleDrift<.1f&&report.loopSeamAngle<.1f&&report.headSeamDistance<.01f&&report.shoulderSeamDistance<.0001f&&report.shoulderSeamAngle<.1f&&report.faceBindings>=800;
            capture(front,Path.Combine(folder,"idle-end-front.png"));
            UnityEngine.Object.Destroy(front.gameObject);UnityEngine.Object.Destroy(side.gameObject);
            if(movieTarget){movieTarget.Release();UnityEngine.Object.Destroy(movieTarget);UnityEngine.Object.Destroy(moviePixels);Time.captureFramerate=0;}
            File.WriteAllText(Path.Combine(folder,"idle-report.json"),JsonUtility.ToJson(report,true));
            Debug.Log("METAHUMAN_IDLE_PREVIEW "+JsonUtility.ToJson(report));
            if(!report.passed)Application.Quit(2);
        }

        static void RecordFrame(Camera camera,RenderTexture target,Texture2D pixels,string path)
        {
            float aspect=camera.aspect;camera.aspect=1;
            UnityEngine.Rendering.RenderPipeline.SubmitRenderRequest(camera,new UnityEngine.Rendering.RenderPipeline.StandardRequest{destination=target});
            var previous=RenderTexture.active;RenderTexture.active=target;
            pixels.ReadPixels(new Rect(0,0,960,960),0,0);pixels.Apply();File.WriteAllBytes(path,pixels.EncodeToJPG(85));
            RenderTexture.active=previous;camera.aspect=aspect;
        }
    }
}
