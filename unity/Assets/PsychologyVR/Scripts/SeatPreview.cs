using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using Unity.Profiling;
using UnityEngine;

namespace PsychologyVR
{
    // Opt-in, service-free capture of the seated actor in the real consultation room.
    public static class SeatPreview
    {
        [Serializable] sealed class Sample
        {
            public float time;
            public string phase,emotion;
            public Vector3 pelvisOffset;
            public float leftFootDrift,rightFootDrift,leftKneeReach,rightKneeReach,leftSupportError,rightSupportError,bodyPenetration;
            public bool supportsReady;
        }

        [Serializable] sealed class BracePose
        {
            public float time,leftTargetReach,leftMaxArmReach,rightTargetReach,rightMaxArmReach;
            public Vector3 leftWristLocal,rightWristLocal,leftSupportLocal,rightSupportLocal;
            public Vector3 leftErrorLocal,rightErrorLocal;
            public float contactCorrection,contactPenetration;
            public int contactCorrections;
        }

        [Serializable] sealed class Report
        {
            public Vector3 baselinePelvis;
            public bool fidgetSeen,driftSeen,braceSeen,cancelledBeforeRise,riseSeen,firstCycleCompleted,repeatSeen,repeatCompleted;
            public bool supportBeforeRise,pauseFrozen,changedEmotionCompleted,passed;
            public float elapsedSeconds,fidgetLateralShift,pausedPelvisDrift,maxLeftFootDrift,maxRightFootDrift;
            public float maxLeftFootAngle,maxRightFootAngle,maxKneeDistanceAtRise,maxBodyPenetration,maxHandOverlap;
            public float maxSupportErrorAtRise,maxSupportErrorDuringReseat,maxPelvisSpeed,maxPelvisStepAtNormalFrame,minPelvisWorldHeight=100;
            public float minSide=100,maxSide=-100,minHeight=100,maxHeight=-100,minForward=100,maxForward=-100;
            public bool chairIntersectionRequiresVisualReview=true;
            public bool rigProfilerAvailable,contactProfilerAvailable,gcProfilerAvailable;
            public int profiledFrames;
            public long meanRigNanoseconds,meanContactNanoseconds,maxGcBytesNormalFrame;
            public BracePose braceFirst,braceLast;
            public List<Sample> samples=new List<Sample>();
        }

        static Transform FindBone(Transform root,string name)
        {
            foreach(var bone in root.GetComponentsInChildren<Transform>())if(bone.name==name)return bone;
            return null;
        }

        static Vector3 KneeWristSupport(Transform anchor)
        {return anchor.position;}

        static float MaxArmReach(Transform upper,Transform forearm,Transform wrist)
        {
            float a=Vector3.Distance(upper.position,forearm.position),b=Vector3.Distance(forearm.position,wrist.position);
            return Mathf.Sqrt(a*a+b*b+2*a*b*Mathf.Cos(8*Mathf.Deg2Rad));
        }

        static Camera Camera(string name,Vector3 position,Vector3 lookAt)
        {
            var camera=new GameObject(name).AddComponent<Camera>();camera.enabled=false;
            camera.nearClipPlane=.05f;camera.fieldOfView=49;
            camera.transform.position=position;camera.transform.LookAt(lookAt);
            return camera;
        }

        public static IEnumerator Run(PrototypeSession session,PerformanceDriver body,Action<Camera,string> capture)
        {
            var args=Environment.GetCommandLineArgs();int at=Array.IndexOf(args,"--capture-path");
            if(!body || !body.proceduralSeat || session.ActiveAppearance!="jumper" || at<0 || at+1>=args.Length)
            {Debug.LogError("SEAT_PREVIEW_FAILED: Jumper and --capture-path outside the project are required");Application.Quit(2);yield break;}
            string output=Path.GetFullPath(args[at+1]);string directory=Path.GetDirectoryName(output);
            string workspace=Path.GetDirectoryName(Application.dataPath);
            workspace=Path.GetDirectoryName(workspace);
            if(string.IsNullOrEmpty(directory) || directory.Equals(workspace,StringComparison.OrdinalIgnoreCase) ||
                directory.StartsWith(workspace+Path.DirectorySeparatorChar,StringComparison.OrdinalIgnoreCase))
            {Debug.LogError("SEAT_PREVIEW_FAILED: output must be outside the repository");Application.Quit(2);yield break;}
            Directory.CreateDirectory(directory);
            if(Array.IndexOf(args,"--arms-preview")>=0)
            {yield return RunArms(session,body,capture,directory,Array.IndexOf(args,"--capture-frames")>=0);yield break;}
            yield return null;yield return new WaitForEndOfFrame();
            var actor=body.transform;
            var hip=FindBone(actor,"CC_Base_Hip");
            var leftFoot=FindBone(actor,"CC_Base_L_Foot");var rightFoot=FindBone(actor,"CC_Base_R_Foot");
            var leftKnee=FindBone(actor,"CC_Base_L_Calf");var rightKnee=FindBone(actor,"CC_Base_R_Calf");
            var leftAnchor=FindBone(actor,"Left Knee Palm Anchor");var rightAnchor=FindBone(actor,"Right Knee Palm Anchor");
            var leftUpper=FindBone(actor,"CC_Base_L_Upperarm");var rightUpper=FindBone(actor,"CC_Base_R_Upperarm");
            var leftForearm=FindBone(actor,"CC_Base_L_Forearm");var rightForearm=FindBone(actor,"CC_Base_R_Forearm");
            if(!hip || !leftFoot || !rightFoot || !leftKnee || !rightKnee || !leftAnchor || !rightAnchor ||
                !leftUpper || !rightUpper || !leftForearm || !rightForearm || !body.LeftWrist || !body.RightWrist)
            {Debug.LogError("SEAT_PREVIEW_FAILED: required Jumper bones are missing");Application.Quit(2);yield break;}
            body.Apply("calm",.5f,"none",true);
            yield return new WaitForEndOfFrame();
            var report=new Report{baselinePelvis=actor.InverseTransformPoint(hip.position)};
            Vector3 leftFootStart=leftFoot.position,rightFootStart=rightFoot.position;
            Quaternion leftFootRotation=leftFoot.rotation,rightFootRotation=rightFoot.rotation;
            float started=Time.time,lastSample=started,firstFinished=0;
            bool pauseTried=false,emotionChanged=false,restarted=false,repeatRisen=false;
            Vector3 previousHip=hip.position;
            Vector3 focus=hip.position+actor.up*.28f;
            var front=Camera("Seat preview front",focus+actor.forward*1.8f+actor.up*.32f,focus);
            var side=Camera("Seat preview side",focus+actor.right*1.7f+actor.up*.24f+actor.forward*.14f,focus);
            void CaptureViews(string stage)
            {
                capture(front,Path.Combine(directory,"seat-"+stage+"-front.png"));
                capture(side,Path.Combine(directory,"seat-"+stage+"-side.png"));
            }
            CaptureViews("baseline");
            body.TriggerGesture("hand_fidget",2.5f);
            using(var rigRecorder=ProfilerRecorder.StartNew(ProfilerCategory.Scripts,"Seat.RigEvaluate",128))
            using(var contactRecorder=ProfilerRecorder.StartNew(ProfilerCategory.Scripts,"Seat.BodyContacts",128))
            using(var gcRecorder=ProfilerRecorder.StartNew(ProfilerCategory.Memory,"GC Allocated In Frame",128))
            {
                report.rigProfilerAvailable=rigRecorder.Valid;
                report.contactProfilerAvailable=contactRecorder.Valid;
                report.gcProfilerAvailable=gcRecorder.Valid;
                float hardDeadline=Time.realtimeSinceStartup+390;
                while(Time.time-started<230 && Time.realtimeSinceStartup<hardDeadline && !report.repeatCompleted)
                {
                    yield return new WaitForEndOfFrame();
                    Vector3 offset=actor.InverseTransformPoint(hip.position)-report.baselinePelvis;
                    float leftDrift=Vector3.Distance(leftFoot.position,leftFootStart);
                    float rightDrift=Vector3.Distance(rightFoot.position,rightFootStart);
                    float leftKneeDistance=Vector3.Distance(body.LeftWrist.position,leftKnee.position);
                    float rightKneeDistance=Vector3.Distance(body.RightWrist.position,rightKnee.position);
                    Vector3 lSupport=KneeWristSupport(leftAnchor),rSupport=KneeWristSupport(rightAnchor);
                    float direct=Vector3.Distance(body.LeftWrist.position,lSupport)+Vector3.Distance(body.RightWrist.position,rSupport);
                    float crossed=Vector3.Distance(body.LeftWrist.position,rSupport)+Vector3.Distance(body.RightWrist.position,lSupport);
                    float leftSupportError=Vector3.Distance(body.LeftWrist.position,direct<=crossed?lSupport:rSupport);
                    float rightSupportError=Vector3.Distance(body.RightWrist.position,direct<=crossed?rSupport:lSupport);
                    string phase=body.SeatPhaseName;
                    if(phase=="Brace")
                    {
                        // Use bone identity, not left/right labels: Jumper's arm naming may be mirrored.
                        bool leftOnL=body.LeftWrist.name=="CC_Base_L_Hand";
                        bool rightOnL=body.RightWrist.name=="CC_Base_L_Hand";
                        Vector3 leftGoal=leftOnL?lSupport:rSupport,rightGoal=rightOnL?lSupport:rSupport;
                        Transform lUpper=leftOnL?leftUpper:rightUpper,lFore=leftOnL?leftForearm:rightForearm;
                        Transform rUpper=rightOnL?leftUpper:rightUpper,rFore=rightOnL?leftForearm:rightForearm;
                        var brace=new BracePose
                        {
                            time=Time.time-started,
                            leftWristLocal=actor.InverseTransformPoint(body.LeftWrist.position),
                            rightWristLocal=actor.InverseTransformPoint(body.RightWrist.position),
                            leftSupportLocal=actor.InverseTransformPoint(leftGoal),
                            rightSupportLocal=actor.InverseTransformPoint(rightGoal),
                            leftErrorLocal=actor.InverseTransformVector(leftGoal-body.LeftWrist.position),
                            rightErrorLocal=actor.InverseTransformVector(rightGoal-body.RightWrist.position),
                            leftTargetReach=Vector3.Distance(lUpper.position,leftGoal),
                            rightTargetReach=Vector3.Distance(rUpper.position,rightGoal),
                            leftMaxArmReach=MaxArmReach(lUpper,lFore,body.LeftWrist),
                            rightMaxArmReach=MaxArmReach(rUpper,rFore,body.RightWrist),
                            contactCorrection=body.BodyContacts?body.BodyContacts.MaxCorrection:0,
                            contactPenetration=body.BodyContacts?body.BodyContacts.CurrentPenetration:0,
                            contactCorrections=body.BodyContacts?body.BodyContacts.Corrections:0
                        };
                        if(report.braceFirst==null){report.braceFirst=brace;CaptureViews("brace");}
                        report.braceLast=brace;
                    }
                    if(phase=="Lift" || phase=="Return" || phase=="Lower")
                        report.maxSupportErrorDuringReseat=Mathf.Max(report.maxSupportErrorDuringReseat,Mathf.Max(leftSupportError,rightSupportError));
                    float hipStep=Vector3.Distance(previousHip,hip.position);previousHip=hip.position;
                    if(Time.deltaTime>0 && Time.deltaTime<.05f)
                    {
                        report.maxPelvisSpeed=Mathf.Max(report.maxPelvisSpeed,hipStep/Time.deltaTime);
                        report.maxPelvisStepAtNormalFrame=Mathf.Max(report.maxPelvisStepAtNormalFrame,hipStep);
                        report.profiledFrames++;
                        if(rigRecorder.Valid)report.meanRigNanoseconds+=rigRecorder.LastValue;
                        if(contactRecorder.Valid)report.meanContactNanoseconds+=contactRecorder.LastValue;
                        if(gcRecorder.Valid)report.maxGcBytesNormalFrame=Math.Max(report.maxGcBytesNormalFrame,gcRecorder.LastValue);
                    }
                    report.minPelvisWorldHeight=Mathf.Min(report.minPelvisWorldHeight,hip.position.y);
                    report.minSide=Mathf.Min(report.minSide,offset.x);report.maxSide=Mathf.Max(report.maxSide,offset.x);
                    report.minHeight=Mathf.Min(report.minHeight,offset.y);report.maxHeight=Mathf.Max(report.maxHeight,offset.y);
                    report.minForward=Mathf.Min(report.minForward,offset.z);report.maxForward=Mathf.Max(report.maxForward,offset.z);
                    report.maxLeftFootDrift=Mathf.Max(report.maxLeftFootDrift,leftDrift);
                    report.maxRightFootDrift=Mathf.Max(report.maxRightFootDrift,rightDrift);
                    report.maxLeftFootAngle=Mathf.Max(report.maxLeftFootAngle,Quaternion.Angle(leftFootRotation,leftFoot.rotation));
                    report.maxRightFootAngle=Mathf.Max(report.maxRightFootAngle,Quaternion.Angle(rightFootRotation,rightFoot.rotation));
                    if(body.BodyContacts)
                    {
                        report.maxBodyPenetration=Mathf.Max(report.maxBodyPenetration,body.BodyContacts.CurrentPenetration);
                        report.maxHandOverlap=Mathf.Max(report.maxHandOverlap,body.BodyContacts.MaxHandPairAfter);
                    }
                    float elapsed=Time.time-started;
                    if(elapsed<3.5f)
                    {
                        report.fidgetLateralShift=Mathf.Max(report.fidgetLateralShift,Mathf.Abs(offset.x));
                        if(!report.fidgetSeen && Mathf.Abs(offset.x)>.008f)
                        {report.fidgetSeen=true;CaptureViews("fidget");}
                    }
                    if(Time.time-lastSample>=1)
                    {
                        report.samples.Add(new Sample{time=elapsed,phase=phase,emotion=body.Emotion,
                            pelvisOffset=offset,leftFootDrift=leftDrift,rightFootDrift=rightDrift,
                            leftKneeReach=leftKneeDistance,rightKneeReach=rightKneeDistance,
                            leftSupportError=leftSupportError,rightSupportError=rightSupportError,
                            bodyPenetration=body.BodyContacts?body.BodyContacts.CurrentPenetration:0,
                            supportsReady=body.SeatSupportReady});
                        lastSample=Time.time;
                    }
                    if(offset.z>.03f && !report.driftSeen){report.driftSeen=true;CaptureViews("drift");}
                    if(body.SeatSupportReady && !report.braceSeen){report.braceSeen=true;CaptureViews("knees");}
                    if(offset.y>.014f && !report.riseSeen)
                    {
                        report.riseSeen=true;report.supportBeforeRise=body.SeatSupportReady;
                        report.maxKneeDistanceAtRise=Mathf.Max(leftKneeDistance,rightKneeDistance);
                        report.maxSupportErrorAtRise=Mathf.Max(leftSupportError,rightSupportError);
                        CaptureViews("rise");
                    }
                    if(report.riseSeen && !pauseTried && offset.y>.014f)
                    {
                        pauseTried=true;Vector3 before=hip.position;session.SetMenuOpen(true);
                        yield return new WaitForSecondsRealtime(.4f);
                        report.pausedPelvisDrift=Vector3.Distance(before,hip.position);
                        report.pauseFrozen=report.pausedPelvisDrift<.002f;
                        session.SetMenuOpen(false);
                        body.Apply("afraid",.8f,"none");emotionChanged=true;
                    }
                    if(emotionChanged && !report.firstCycleCompleted && offset.y<.005f && offset.z<.012f && elapsed>65)
                    {report.firstCycleCompleted=true;report.changedEmotionCompleted=body.Emotion=="afraid";firstFinished=Time.time;CaptureViews("settled");}
                    if(report.firstCycleCompleted && !restarted && Time.time-firstFinished>6)
                    {body.Apply("calm",.5f,"none");restarted=true;}
                    if(restarted && !report.repeatSeen && offset.z>.03f)
                    {report.repeatSeen=true;CaptureViews("repeat-drift");}
                    if(report.repeatSeen && offset.y>.014f)repeatRisen=true;
                    if(repeatRisen && offset.y<.005f && offset.z<.012f)
                    {report.repeatCompleted=true;CaptureViews("repeat-settled");}
                    if(phase=="Cancel" && !report.riseSeen)
                    {report.cancelledBeforeRise=true;CaptureViews("cancel");break;}
                }
            }
            report.elapsedSeconds=Time.time-started;
            if(report.profiledFrames>0)
            {report.meanRigNanoseconds/=report.profiledFrames;report.meanContactNanoseconds/=report.profiledFrames;}
            report.passed=report.fidgetSeen && report.fidgetLateralShift<=.021f &&
                report.driftSeen && report.braceSeen && report.riseSeen && report.firstCycleCompleted &&
                report.repeatSeen && report.repeatCompleted && report.supportBeforeRise && report.pauseFrozen &&
                report.changedEmotionCompleted && report.minSide>=-.051f && report.maxSide<=.051f &&
                report.minForward>=-.031f && report.maxForward<=.111f && report.minHeight>=-.006f &&
                report.maxHeight<=.041f && report.maxLeftFootDrift<.015f && report.maxRightFootDrift<.015f &&
                report.maxLeftFootAngle<6 && report.maxRightFootAngle<6 && report.maxSupportErrorAtRise<.04f &&
                report.maxSupportErrorDuringReseat<.08f &&
                report.maxPelvisSpeed<.35f && report.maxPelvisStepAtNormalFrame<.015f &&
                report.maxBodyPenetration<.002f && report.maxHandOverlap<.002f;
            File.WriteAllText(Path.Combine(directory,"seat-preview-report.json"),JsonUtility.ToJson(report,true));
            Debug.Log(report.passed?"SEAT_PREVIEW_OK":"SEAT_PREVIEW_FAILED: see seat-preview-report.json");
            UnityEngine.Object.Destroy(front.gameObject);UnityEngine.Object.Destroy(side.gameObject);
            Application.Quit(report.passed?0:5);
        }

        [Serializable] sealed class ArmReport
        {
            public bool pauseFrozen,passed;
            public float pausedHandDrift,maxFootDrift,maxBodyPenetration,maxReachError,maxWristBend,maxWristTwist,maxElbowBend;
            public List<string> emotions=new List<string>();
        }

        static IEnumerator RunArms(PrototypeSession session,PerformanceDriver body,Action<Camera,string> capture,string directory,bool record)
        {
            yield return null;yield return new WaitForEndOfFrame();
            var actor=body.transform;var hip=FindBone(actor,"CC_Base_Hip");
            var leftFoot=FindBone(actor,"CC_Base_L_Foot");var rightFoot=FindBone(actor,"CC_Base_R_Foot");
            Vector3 footL=leftFoot.position,footR=rightFoot.position,focus=hip.position+actor.up*.28f;
            var front=Camera("Arm preview front",focus+actor.forward*1.9f+actor.up*.32f,focus);
            var side=Camera("Arm preview side",focus+actor.right*1.7f+actor.up*.24f+actor.forward*.14f,focus);
            var report=new ArmReport();
            string[] emotions={"neutral","calm","anxious","frustrated","confused","happy","crying","angry","panicked","afraid","numb"};
            var render=record?new RenderTexture(640,720,24):null;
            var frame=record?new Texture2D(1280,720,TextureFormat.RGB24,false):null;
            string frames=Path.Combine(directory,"frames");if(record)Directory.CreateDirectory(frames);
            int frameIndex=0;float nextCapture=Time.time;
            foreach(string emotion in emotions)
            {
                body.Apply(emotion,emotion=="neutral"||emotion=="calm"?.5f:.8f,"none",true);
                report.emotions.Add(emotion);
                float started=Time.time;bool captured=false;
                while(Time.time-started<6)
                {
                    yield return new WaitForEndOfFrame();
                    report.maxFootDrift=Mathf.Max(report.maxFootDrift,Vector3.Distance(footL,leftFoot.position),Vector3.Distance(footR,rightFoot.position));
                    report.maxBodyPenetration=Mathf.Max(report.maxBodyPenetration,body.BodyContacts.CurrentPenetration);
                    if(!captured && Time.time-started>3)
                    {
                        captured=true;
                        capture(front,Path.Combine(directory,"arms-"+emotion+"-front.png"));
                        capture(side,Path.Combine(directory,"arms-"+emotion+"-side.png"));
                    }
                    if(record && Time.time>=nextCapture)
                    {
                        nextCapture+=.1f;
                        var previous=RenderTexture.active;
                        UnityEngine.Rendering.RenderPipeline.SubmitRenderRequest(front,new UnityEngine.Rendering.RenderPipeline.StandardRequest{destination=render});
                        RenderTexture.active=render;frame.ReadPixels(new Rect(0,0,640,720),0,0);
                        UnityEngine.Rendering.RenderPipeline.SubmitRenderRequest(side,new UnityEngine.Rendering.RenderPipeline.StandardRequest{destination=render});
                        RenderTexture.active=render;frame.ReadPixels(new Rect(0,0,640,720),640,0);
                        RenderTexture.active=previous;
                        File.WriteAllBytes(Path.Combine(frames,(frameIndex++).ToString("D5")+".png"),frame.EncodeToPNG());
                    }
                    if(emotion=="anxious" && !report.pauseFrozen && Time.time-started>4)
                    {
                        Vector3 l=body.LeftWrist.position,r=body.RightWrist.position;session.SetMenuOpen(true);
                        yield return new WaitForSecondsRealtime(.4f);
                        report.pausedHandDrift=Mathf.Max(Vector3.Distance(l,body.LeftWrist.position),Vector3.Distance(r,body.RightWrist.position));
                        report.pauseFrozen=report.pausedHandDrift<.002f;session.SetMenuOpen(false);
                        nextCapture=Time.time;
                    }
                }
            }
            report.maxReachError=body.MaxReachError;report.maxWristBend=body.MaxWristBend;
            report.maxWristTwist=body.MaxWristTwist;report.maxElbowBend=body.MaxElbowBend;
            report.passed=report.pauseFrozen && report.maxFootDrift<.015f && report.maxBodyPenetration<.002f &&
                report.maxReachError<.08f && report.maxWristBend<58 && report.maxWristTwist<15 && report.maxElbowBend<146;
            File.WriteAllText(Path.Combine(directory,"arms-preview-report.json"),JsonUtility.ToJson(report,true));
            if(render){render.Release();UnityEngine.Object.Destroy(render);UnityEngine.Object.Destroy(frame);}
            UnityEngine.Object.Destroy(front.gameObject);UnityEngine.Object.Destroy(side.gameObject);
            Debug.Log(report.passed?"ARMS_PREVIEW_OK":"ARMS_PREVIEW_FAILED: see arms-preview-report.json");
            Application.Quit(report.passed?0:5);
        }
    }
}
