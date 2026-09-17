using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using UnityEngine;
using UnityEngine.Rendering.Universal;

namespace PsychologyVR
{
    // Offline capture of the actual runtime performance components. It does not
    // connect to the dialogue service or change normal gameplay timing.
    public static class AlexAnimationRecorder
    {
        const int Fps=24,Width=960,Height=720;
        [Serializable] public class Chapter {public int start,end;public string label;}
        [Serializable] public class Clip {public string name;public int frames;public List<Chapter> chapters=new List<Chapter>();}
        [Serializable] public class Manifest {public int fps=Fps,width=Width,height=Height;public List<Clip> clips=new List<Clip>();}
        [Serializable] public class MotionSample {public string emotion;public float leftSpan,rightSpan,headSpan,faceCover,reachError;public float[] heldFingerMotion;}
        [Serializable] public class MotionReport {public List<MotionSample> samples=new List<MotionSample>();public bool passed;public float peakHandSpeed,peakWristStep,maxWristBend,maxWristTwist,minElbowBend,maxElbowBend,maxHingeError,maxForearmRoll;public float[] fingerTravel;
            public float contactBefore,contactAfter,maxContactOffset,handPairAfter,peakForearmHelperStep;public int bodyBoundaries,contactCorrections,fingerCorrections,handPairCorrections,forearmHelpers;public int[] regionContacts;}
        static FacialPerformance actor;
        static MotionReport motionReport;
        static Camera camera;
        static RenderTexture target;
        static Texture2D pixels;
        static string directory;
        static bool havePrevious;static Vector3 previousLeft,previousRight;static Quaternion previousLeftRotation,previousRightRotation;
        static bool fingerPreview;static Transform[] fingerBones;static Quaternion[] fingerRest;
        static Transform[] forearmHelpers;static Quaternion[] previousHelperRotations;

        public static IEnumerator Run(FacialPerformance face,AudioSource voice)
        {
            yield return null;yield return new WaitForEndOfFrame();
            var args=Environment.GetCommandLineArgs();int at=Array.IndexOf(args,"--record-dir");
            if(!face || at<0 || at+1>=args.Length){Debug.LogError("ALEX_RECORD_FAILED: missing rig/path");Application.Quit(2);yield break;}
            directory=args[at+1];Directory.CreateDirectory(directory);
            Time.captureFramerate=Fps;var manifest=new Manifest();actor=face;motionReport=new MotionReport();
            var helpers=new List<Transform>();
            foreach(var bone in face.GetComponentsInChildren<Transform>())
                if(bone.name.EndsWith("ForearmTwist01")||bone.name.EndsWith("ForearmTwist02")||bone.name.EndsWith("ElbowShareBone"))helpers.Add(bone);
            forearmHelpers=helpers.ToArray();previousHelperRotations=new Quaternion[helpers.Count];motionReport.forearmHelpers=helpers.Count;
            camera=new GameObject("Animation recording camera").AddComponent<Camera>();camera.enabled=false;camera.nearClipPlane=.05f;
            target=new RenderTexture(Width,Height,24);pixels=new Texture2D(Width,Height,TextureFormat.RGB24,false);
            Vector3 focus=face.Head.position+Vector3.up*.085f;
            camera.transform.position=focus+face.transform.forward*.85f;camera.transform.LookAt(focus);camera.fieldOfView=37;
            face.conversationTarget=camera.transform;face.automaticGaze=true;face.gazeAversion=true;
            face.body.Apply("neutral",0,"none",true);face.blinkOverride=-1;
            fingerPreview=Array.IndexOf(args,"--finger-motion")>=0;
            if(Array.IndexOf(args,"--natural-motion")>=0||fingerPreview)
            {
                var data=camera.GetUniversalAdditionalCameraData();data.renderPostProcessing=Camera.main.GetUniversalAdditionalCameraData().renderPostProcessing;
                data.volumeLayerMask=1;data.volumeTrigger=camera.transform;camera.allowHDR=true;
                camera.SetVolumeFrameworkUpdateMode(VolumeFrameworkUpdateMode.EveryFrame);
                focus=face.transform.TransformPoint(new Vector3(0,.98f,.12f));
                camera.transform.position=focus+face.transform.forward*1.85f+face.transform.right*.32f;
                camera.transform.LookAt(focus);camera.fieldOfView=48;
                if(fingerPreview)
                {
                    var bones=new List<Transform>();
                    foreach(string side in new[]{"L","R"})foreach(string digit in new[]{"Index2","Mid2","Ring2","Pinky2","Thumb3"})
                        foreach(var bone in face.GetComponentsInChildren<Transform>())if(bone.name=="CC_Base_"+side+"_"+digit)bones.Add(bone);
                    fingerBones=bones.ToArray();fingerRest=new Quaternion[bones.Count];motionReport.fingerTravel=new float[bones.Count];
                    for(int i=0;i<bones.Count;i++)fingerRest[i]=bones[i].localRotation;
                }
                bool contactPreview=Array.IndexOf(args,"--body-contact")>=0;
                var natural=new Clip{name=contactPreview?"alex-body-contact":fingerPreview?"alex-active-fingers":"alex-joint-movement"};manifest.clips.Add(natural);
                var moods=contactPreview?new[]{"neutral","anxious","frustrated","angry","crying","afraid","panicked","disgusted","despondent","neutral"}:fingerPreview?new[]{"anxious","frustrated","angry","neutral","crying"}:new[]{"neutral","frustrated","confused","angry","crying","afraid","panicked","disgusted","despondent","neutral"};
                foreach(var mood in moods)
                {
                    face.body.Apply(mood,mood=="neutral"?0:.9f,"none");
                    yield return Frames(natural,mood=="neutral"?"Resting and settling":EmotionLibrary.Find(mood).label,mood=="crying"||fingerPreview&&mood!="neutral"?8:5);
                }
                if(contactPreview)
                {
                    face.body.Apply("sad",.7f,"wipe_tear");
                    yield return Frames(natural,"Wiping a tear",4);
                }
                motionReport.maxWristBend=face.body.MaxWristBend;motionReport.minElbowBend=face.body.MinElbowBend;
                motionReport.maxElbowBend=face.body.MaxElbowBend;motionReport.maxHingeError=face.body.MaxHingeError;motionReport.maxForearmRoll=face.body.MaxForearmRoll;
                motionReport.maxWristTwist=face.body.MaxWristTwist;
                var contacts=face.body.BodyContacts;
                if(contacts)
                {
                    motionReport.contactBefore=contacts.MaxBefore;motionReport.contactAfter=contacts.MaxAfter;
                    motionReport.maxContactOffset=contacts.MaxCorrection;motionReport.bodyBoundaries=contacts.BoundaryCount;
                    motionReport.contactCorrections=contacts.Corrections;motionReport.fingerCorrections=contacts.FingerCorrections;
                    motionReport.regionContacts=contacts.RegionContacts;
                    motionReport.handPairAfter=contacts.MaxHandPairAfter;motionReport.handPairCorrections=contacts.HandPairCorrections;
                }
                motionReport.passed=face.body.MaxReachError<.08f&&motionReport.peakHandSpeed<1.8f&&motionReport.peakWristStep<35
                    &&motionReport.maxWristBend<55&&motionReport.maxWristTwist<10&&motionReport.minElbowBend>7.8f&&motionReport.maxElbowBend<145.2f&&motionReport.maxHingeError<.2f;
                motionReport.passed &= contacts&&motionReport.bodyBoundaries==4&&motionReport.contactAfter<.002f&&motionReport.handPairAfter<.002f;
                motionReport.passed &= forearmHelpers.Length==6&&motionReport.peakForearmHelperStep<35;
                if(contactPreview)motionReport.passed &= motionReport.contactCorrections>0&&motionReport.contactBefore>.001f;
                foreach(var sample in motionReport.samples)
                    if(sample.emotion=="neutral"&&(sample.leftSpan>.025f||sample.rightSpan>.025f))motionReport.passed=false;
                if(fingerPreview)
                {
                    motionReport.passed &= fingerBones.Length==10;
                    foreach(float travel in motionReport.fingerTravel)motionReport.passed &= travel>10;
                    // A pose change alone must not pass the finger-animation test.
                    // Require motion after two seconds of holding the SAME emotion.
                    foreach(var sample in motionReport.samples)if(sample.emotion=="anxious"||sample.emotion=="frustrated"||sample.emotion=="angry"||sample.emotion=="crying")
                        for(int f=0;f<sample.heldFingerMotion.Length;f++)
                            motionReport.passed &= sample.heldFingerMotion[f]>(f%5==4?6:10);
                }
                File.WriteAllText(Path.Combine(directory,"manifest.json"),JsonUtility.ToJson(manifest,true));
                File.WriteAllText(Path.Combine(directory,"motion-checks.json"),JsonUtility.ToJson(motionReport,true));
                Time.captureFramerate=0;target.Release();UnityEngine.Object.Destroy(target);UnityEngine.Object.Destroy(pixels);
                Debug.Log(motionReport.passed?"NATURAL_MOTION_OK":"NATURAL_MOTION_FAILED");Application.Quit(motionReport.passed?0:5);yield break;
            }
            var expressions=new Clip{name="alex-expressive-v2"};manifest.clips.Add(expressions);
            focus=new Vector3(face.transform.position.x,1.0f,face.transform.position.z);
            camera.transform.position=focus+face.transform.forward*1.65f;
            camera.transform.LookAt(focus);camera.fieldOfView=48;
            foreach(var name in new[]{"neutral","crying","angry","afraid","panicked","disgusted","happy","despondent","numb"})
            {
                face.body.Apply(name,name=="neutral"?0:1,"none");
                yield return Frames(expressions,EmotionLibrary.Find(name).label,name=="crying"?10:5);
            }
            face.body.Apply("neutral",0,"none");face.body.StopGesture(true);
            yield return Frames(expressions,"Returning to neutral",3);
            File.WriteAllText(Path.Combine(directory,"manifest.json"),JsonUtility.ToJson(manifest,true));
            Debug.Log("PERFORMANCE_REACH_ERROR "+face.body.MaxReachError);
            motionReport.passed=true;
            foreach(var m in motionReport.samples)
            {
                if(m.emotion=="angry" && Mathf.Max(m.leftSpan,m.rightSpan)<.15f)motionReport.passed=false;
                if((m.emotion=="numb" || m.emotion=="afraid") && m.headSpan>.003f)motionReport.passed=false;
                if(m.emotion=="crying" && m.faceCover<.95f)motionReport.passed=false;
            }
            File.WriteAllText(Path.Combine(directory,"motion-checks.json"),JsonUtility.ToJson(motionReport,true));
            Debug.Log("PERFORMANCE_MOTION_CHECKS "+motionReport.passed);
            if(Array.IndexOf(args,"--expressive-only")>=0){Time.captureFramerate=0;Debug.Log("ALEX_RECORD_OK");Application.Quit(0);yield break;}

            var gestures=new Clip{name="alex-gestures"};manifest.clips.Add(gestures);
            focus=face.Head.position-Vector3.up*.22f;
            camera.transform.position=focus+face.transform.forward*1.35f+face.transform.right*.12f;camera.transform.LookAt(focus);camera.fieldOfView=50;
            face.gazeAversion=false;face.body.Apply("neutral",.3f,"none",true);
            var lookTarget=new GameObject("Recorded gaze target").transform;face.conversationTarget=lookTarget;
            lookTarget.position=camera.transform.position+face.transform.right*.7f;
            yield return Frames(gestures,"Following your position",3);
            lookTarget.position=camera.transform.position-face.transform.right*.7f;
            yield return Frames(gestures,"Following your position",3);
            face.conversationTarget=camera.transform;
            foreach(var gesture in new[]{"nod","hand_fidget","glance_away","wince"})
            {
                face.body.Apply(gesture=="hand_fidget"?"anxious":"neutral",.7f,gesture);
                yield return Frames(gestures,gesture.Replace('_',' '),3.5f);
            }
            face.body.StopGesture(true);
            File.WriteAllText(Path.Combine(directory,"manifest.json"),JsonUtility.ToJson(manifest,true));

            var speech=new Clip{name="alex-speaking"};manifest.clips.Add(speech);
            focus=face.Head.position+Vector3.up*.085f;
            camera.transform.position=focus+face.transform.forward*.85f;camera.transform.LookAt(focus);camera.fieldOfView=37;
            var segment=JsonUtility.FromJson<SpeechSegment>(Resources.Load<TextAsset>("FaceDemo/speech").text);
            voice.clip=Resources.Load<AudioClip>("FaceDemo/speech");voice.volume=0;
            face.body.Apply("anxious",.5f,"none",true);face.BeginSpeech(voice,segment.mouth_cues);
            voice.Play();voice.Pause();face.PauseSpeech(true);
            int count=Mathf.CeilToInt(voice.clip.length*Fps);
            speech.chapters.Add(new Chapter{start=0,end=count,label="Speaking · current Kokoro voice"});
            for(int frame=0;frame<count;frame++)
            {
                // Frame-accurate audio clock while capture may run slower than real time.
                voice.timeSamples=Mathf.Min(voice.clip.samples-1,Mathf.RoundToInt(frame*voice.clip.frequency/(float)Fps));
                yield return new WaitForEndOfFrame();Save(speech);
            }
            voice.Stop();face.StopSpeech();yield return Frames(speech,"Speaking · current Kokoro voice",1);
            File.WriteAllText(Path.Combine(directory,"manifest.json"),JsonUtility.ToJson(manifest,true));
            Time.captureFramerate=0;target.Release();UnityEngine.Object.Destroy(target);UnityEngine.Object.Destroy(pixels);
            Debug.Log("ALEX_RECORD_OK");Application.Quit(0);
        }
        static IEnumerator Frames(Clip clip,string label,float seconds)
        {
            int count=Mathf.RoundToInt(seconds*Fps);clip.chapters.Add(new Chapter{start=clip.frames,end=clip.frames+count,label=label});
            var sample=new MotionSample{emotion=actor.body.Emotion};
            Quaternion[] heldFingerStart=fingerPreview?new Quaternion[fingerBones.Length]:null;
            if(fingerPreview)sample.heldFingerMotion=new float[fingerBones.Length];
            Bounds leftBounds=new Bounds(),rightBounds=new Bounds(),headBounds=new Bounds();bool began=false;
            for(int i=0;i<count;i++)
            {
                yield return new WaitForEndOfFrame();
                if(fingerPreview)
                {
                    Vector3 focus=(actor.body.LeftWrist.position+actor.body.RightWrist.position)*.5f+actor.transform.forward*.065f;
                    camera.transform.position=focus+actor.transform.forward*.83f+Vector3.up*.40f;
                    camera.transform.LookAt(focus);camera.fieldOfView=49;
                    for(int f=0;f<fingerBones.Length;f++)motionReport.fingerTravel[f]=Mathf.Max(motionReport.fingerTravel[f],Quaternion.Angle(fingerRest[f],fingerBones[f].localRotation));
                }
                Save(clip);
                if(clip.name=="alex-body-contact"&&(i==Fps*4||sample.emotion=="sad"&&i==Fps))
                {
                    Vector3 savedPosition=camera.transform.position;Quaternion savedRotation=camera.transform.rotation;
                    Vector3 focus=(actor.body.LeftWrist.position+actor.body.RightWrist.position)*.5f;
                    camera.transform.position=focus+actor.transform.forward*.60f+actor.transform.right*.65f+Vector3.up*.28f;
                    camera.transform.LookAt(focus);Save(new Clip{name="contact-side-"+sample.emotion});
                    camera.transform.SetPositionAndRotation(savedPosition,savedRotation);
                }
                if(havePrevious)
                {
                    motionReport.peakHandSpeed=Mathf.Max(motionReport.peakHandSpeed,Vector3.Distance(previousLeft,actor.body.LeftWrist.position)*Fps,Vector3.Distance(previousRight,actor.body.RightWrist.position)*Fps);
                    motionReport.peakWristStep=Mathf.Max(motionReport.peakWristStep,Quaternion.Angle(previousLeftRotation,actor.body.LeftWrist.rotation),Quaternion.Angle(previousRightRotation,actor.body.RightWrist.rotation));
                    for(int helper=0;helper<forearmHelpers.Length;helper++)motionReport.peakForearmHelperStep=Mathf.Max(motionReport.peakForearmHelperStep,Quaternion.Angle(previousHelperRotations[helper],forearmHelpers[helper].rotation));
                }
                for(int helper=0;helper<forearmHelpers.Length;helper++)previousHelperRotations[helper]=forearmHelpers[helper].rotation;
                previousLeft=actor.body.LeftWrist.position;previousRight=actor.body.RightWrist.position;
                previousLeftRotation=actor.body.LeftWrist.rotation;previousRightRotation=actor.body.RightWrist.rotation;havePrevious=true;
                if(i<Fps*2)continue;
                if(fingerPreview)for(int f=0;f<fingerBones.Length;f++)
                {
                    if(i==Fps*2)heldFingerStart[f]=fingerBones[f].localRotation;
                    sample.heldFingerMotion[f]=Mathf.Max(sample.heldFingerMotion[f],Quaternion.Angle(heldFingerStart[f],fingerBones[f].localRotation));
                }
                Vector3 l=actor.body.LeftWrist.position,r=actor.body.RightWrist.position,h=actor.Head.position;
                if(!began){leftBounds=new Bounds(l,Vector3.zero);rightBounds=new Bounds(r,Vector3.zero);headBounds=new Bounds(h,Vector3.zero);began=true;}
                leftBounds.Encapsulate(l);rightBounds.Encapsulate(r);headBounds.Encapsulate(h);
                sample.faceCover=Mathf.Max(sample.faceCover,actor.body.FaceCover);
            }
            sample.leftSpan=leftBounds.size.magnitude;sample.rightSpan=rightBounds.size.magnitude;sample.headSpan=headBounds.size.magnitude;
            sample.reachError=actor.body.MaxReachError;motionReport.samples.Add(sample);
            if(clip.name=="alex-expressive-v2" && Camera.main)
            {
                // Verify readability at the real player camera, without changing gameplay.
                Vector3 savedPosition=camera.transform.position;Quaternion savedRotation=camera.transform.rotation;float savedFov=camera.fieldOfView;
                camera.transform.SetPositionAndRotation(Camera.main.transform.position,Camera.main.transform.rotation);camera.fieldOfView=Camera.main.fieldOfView;
                var seated=new Clip{name="player-view-"+sample.emotion};Save(seated);
                camera.transform.SetPositionAndRotation(savedPosition,savedRotation);camera.fieldOfView=savedFov;
            }
        }
        static void Save(Clip clip)
        {
            string folder=Path.Combine(directory,clip.name);Directory.CreateDirectory(folder);
            UnityEngine.Rendering.RenderPipeline.SubmitRenderRequest(camera,new UnityEngine.Rendering.RenderPipeline.StandardRequest{destination=target});
            RenderTexture.active=target;pixels.ReadPixels(new Rect(0,0,Width,Height),0,0);pixels.Apply();RenderTexture.active=null;
            File.WriteAllBytes(Path.Combine(folder,clip.frames.ToString("D5")+".jpg"),pixels.EncodeToJPG(92));clip.frames++;
        }
    }
}
