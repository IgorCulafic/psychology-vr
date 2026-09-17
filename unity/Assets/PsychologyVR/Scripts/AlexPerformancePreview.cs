using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using UnityEngine;

namespace PsychologyVR
{
    // Explicit command-line diagnostic. Uses a prerecorded fixture and no services.
    public static class AlexPerformancePreview
    {
        [Serializable] class Report
        {
            public int shapeBindings;
            public int expressionCount,tearAnchors;
            public float cryingWetness,clearedWetness;
            public float interruptedWetness;
            public bool tearsVisible;
            public string[] mouthCues;
            public float maximumJaw,pausedTimeDrift,resumedTimeAdvance,stoppedJaw;
            public float rightGazeYaw,leftGazeYaw;
            public bool passed;
        }
        public static IEnumerator Run(FacialPerformance face,AudioSource voice,Camera view,Action<Camera,string> capture)
        {
            yield return null;yield return null;
            var args=Environment.GetCommandLineArgs();int at=Array.IndexOf(args,"--capture-path");
            if(!face || !face.Head || face.ShapeBindingCount<27 || at<0 || at+1>=args.Length)
            {Debug.LogError("ALEX_PREVIEW_FAILED: missing facial rig or capture path");Application.Quit(2);yield break;}
            string directory=Path.GetDirectoryName(args[at+1]);Directory.CreateDirectory(directory);
            view=new GameObject("Alex portrait camera").AddComponent<Camera>();view.enabled=false;view.nearClipPlane=.05f;
            face.automaticGaze=false;face.blinkOverride=0;
            if(face.body.seatedAnimation)face.body.seatedAnimation.Stop();
            var focus=face.Head.position+Vector3.up*.09f;
            view.transform.position=focus+face.transform.forward*.8f;
            view.transform.LookAt(focus);view.fieldOfView=35;
            var report=new Report{shapeBindings=face.ShapeBindingCount};
            foreach(var preset in EmotionLibrary.Catalog.emotions)
            {
                string mood=preset.name;
                face.body.Apply(mood,.9f,"none",true);
                yield return new WaitForSeconds(mood=="crying"?1.8f:.8f);
                yield return new WaitForEndOfFrame();
                if(mood=="crying"){report.cryingWetness=face.Tears?face.Tears.Wetness:0;report.tearAnchors=face.Tears?face.Tears.AnchorCount:0;report.tearsVisible=face.Tears && face.Tears.Visible;}
                capture(view,Path.Combine(directory,"alex-unity-"+mood+".png"));
                report.expressionCount++;
            }
            face.body.Apply("neutral",0,"none",true);face.blinkOverride=1;
            yield return new WaitForSeconds(.3f);yield return new WaitForEndOfFrame();capture(view,Path.Combine(directory,"alex-unity-blink.png"));
            face.blinkOverride=0;
            var data=Resources.Load<TextAsset>("FaceDemo/speech");
            voice.clip=Resources.Load<AudioClip>("FaceDemo/speech");
            if(!data || !voice.clip){Debug.LogError("ALEX_PREVIEW_FAILED: missing speech fixture");Application.Quit(3);yield break;}
            var segment=JsonUtility.FromJson<SpeechSegment>(data.text);
            voice.volume=0;face.BeginSpeech(voice,segment.mouth_cues);voice.Play();
            report.clearedWetness=face.Tears?face.Tears.Wetness:1;var seen=new HashSet<string>();
            float deadline=Time.realtimeSinceStartup+voice.clip.length+3;bool captured=false,didPause=false;
            while(voice.isPlaying && Time.realtimeSinceStartup<deadline)
            {
                yield return null;seen.Add(face.CurrentMouthCue);report.maximumJaw=Mathf.Max(report.maximumJaw,face.JawWeight);
                if(!captured && face.JawWeight>.25f)
                {yield return new WaitForEndOfFrame();capture(view,Path.Combine(directory,"alex-unity-speaking.png"));captured=true;}
                if(!didPause && voice.time>1)
                {
                    voice.Pause();face.PauseSpeech(true);float pausedTime=voice.time;
                    yield return new WaitForSecondsRealtime(.3f);
                    report.pausedTimeDrift=Mathf.Abs(voice.time-pausedTime);
                    voice.UnPause();face.PauseSpeech(false);
                    yield return new WaitForSecondsRealtime(.3f);
                    report.resumedTimeAdvance=voice.time-pausedTime;didPause=true;
                }
            }
            // Restart and interrupt mid-vowel to verify closure on cancellation.
            voice.time=.5f;face.BeginSpeech(voice,segment.mouth_cues);voice.Play();
            yield return new WaitForSeconds(.4f);voice.Stop();face.StopSpeech();
            yield return new WaitForSeconds(.3f);report.stoppedJaw=face.JawWeight;
            if(face.body.seatedAnimation)face.body.seatedAnimation.Play("Seated");face.automaticGaze=true;face.gazeAversion=false;
            var gazeTarget=new GameObject("Gaze test target").transform;face.conversationTarget=gazeTarget;
            gazeTarget.position=focus+face.transform.forward+face.transform.right*.3f;
            yield return new WaitForSeconds(1.2f);yield return new WaitForEndOfFrame();report.rightGazeYaw=face.EyeYaw;
            capture(view,Path.Combine(directory,"alex-unity-gaze-right.png"));
            gazeTarget.position=focus+face.transform.forward-face.transform.right*.3f;
            yield return new WaitForSeconds(1.2f);yield return new WaitForEndOfFrame();report.leftGazeYaw=face.EyeYaw;
            capture(view,Path.Combine(directory,"alex-unity-gaze-left.png"));
            face.body.Apply("crying",.9f,"none",true);
            yield return new WaitForSeconds(1.8f);yield return new WaitForEndOfFrame();
            capture(view,Path.Combine(directory,"alex-unity-crying-body.png"));
            face.body.StopGesture(true);yield return new WaitForSeconds(2.2f);
            report.interruptedWetness=face.Tears?face.Tears.Wetness:1;
            report.mouthCues=new List<string>(seen).ToArray();
            report.passed=seen.Count>=4 && report.maximumJaw>.2f && didPause && report.pausedTimeDrift<.03f && report.resumedTimeAdvance>.15f && report.stoppedJaw<.02f && report.rightGazeYaw>2 && report.leftGazeYaw<-2
                && report.expressionCount==EmotionLibrary.Catalog.emotions.Length && report.cryingWetness>.5f && report.clearedWetness<.01f && report.tearAnchors==72 && report.tearsVisible && report.interruptedWetness<.01f;
            File.WriteAllText(Path.Combine(directory,"unity-facial-playback.json"),JsonUtility.ToJson(report,true));
            Debug.Log(report.passed?"ALEX_PREVIEW_OK":"ALEX_PREVIEW_FAILED: playback assertions");
            Application.Quit(report.passed?0:4);
        }
    }
}
