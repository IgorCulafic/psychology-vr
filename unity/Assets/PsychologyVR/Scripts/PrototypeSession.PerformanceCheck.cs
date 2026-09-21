using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using UnityEngine;

namespace PsychologyVR
{
    public partial class PrototypeSession
    {
        [Serializable] class PerformanceReplay { public ReplayTurn[] turns; }
        [Serializable] class ReplayTurn { public string name,source; public Reply reply; }
        [Serializable] class BeatCheck
        {
            public string name,source,emotion,gesture;
            public bool emotionMatched=true,audioPlayed,captured,gestureSeen;
            public float maximumJaw,maximumWetness,maximumCover,gestureTimingError,handToHeadAtCapture;
        }
        [Serializable] class PlaybackCheck
        {
            public List<BeatCheck> beats=new List<BeatCheck>();
            public bool completed,paused,resumed,interrupted,noLateBeat,passed;
        }

        // Opt-in development diagnostic. Replays captured model replies through PlayReply;
        // it never changes cues or generates an alternative animation-only playback path.
        IEnumerator CheckPerformancePlayback()
        {
            var args=Environment.GetCommandLineArgs();int index=Array.IndexOf(args,"--performance-replay");
            if(index<0||index+1>=args.Length)yield break;
            string path=Path.GetFullPath(args[index+1]),folder=Path.GetDirectoryName(path);
            var replay=JsonUtility.FromJson<PerformanceReplay>(File.ReadAllText(path));
            var report=new PlaybackCheck();
            float deadline=Time.realtimeSinceStartup+30;
            while((string.IsNullOrEmpty(sessionId)||IsSwitching)&&Time.realtimeSinceStartup<deadline)yield return null;
            if(string.IsNullOrEmpty(sessionId)||replay.turns==null||replay.turns.Length==0)
            {Debug.LogError("PERFORMANCE_REPLAY_FAILED: connection or fixture");Application.Quit(2);yield break;}
            foreach(var turn in replay.turns)
            {
                busy=true;StartCoroutine(PlayReply(turn.reply,version));
                deadline=Time.realtimeSinceStartup+120;
                SpeechSegment observed=null;BeatCheck sample=null;
                while(busy&&Time.realtimeSinceStartup<deadline)
                {
                    if(activeBeat!=null)
                    {
                        if(activeBeat!=observed)
                        {
                            observed=activeBeat;
                            sample=new BeatCheck{name=turn.name,source=turn.source,emotion=observed.emotion,gesture=observed.gesture};
                            report.beats.Add(sample);
                        }
                        sample.emotionMatched&=performance.Emotion==observed.emotion;
                        sample.audioPlayed|=voice.isPlaying;
                        sample.maximumJaw=Mathf.Max(sample.maximumJaw,face.JawWeight);
                        sample.maximumWetness=Mathf.Max(sample.maximumWetness,face.Tears?face.Tears.Wetness:0);
                        sample.maximumCover=Mathf.Max(sample.maximumCover,performance.FaceCover);
                        if(!sample.gestureSeen&&observed.gesture!="none"&&voice.isPlaying&&performance.Gesture==observed.gesture)
                        {
                            sample.gestureSeen=true;
                            sample.gestureTimingError=Mathf.Abs(voice.time-Mathf.Clamp(observed.gesture_at,0,.85f)*voice.clip.length);
                        }
                        // The crying preset deliberately raises its hands gradually;
                        // capture the full action, not its early chest-height transition.
                        bool captureReady=voice.isPlaying&&voice.clip&&(observed.emotion=="crying"?performance.FaceCover>.95f:voice.time>1.5f);
                        if(voice.isPlaying&&captureReady&&!sample.captured)
                        {
                            // Update restores the base rig; capture only after LateUpdate
                            // has applied IK and facial controls, as the headset sees it.
                            yield return new WaitForEndOfFrame();
                            sample.handToHeadAtCapture=Mathf.Max(Vector3.Distance(performance.LeftWrist.position,face.Head.position),
                                Vector3.Distance(performance.RightWrist.position,face.Head.position));
                            Capture(view,Path.Combine(folder,"performance-beat-"+report.beats.Count+".png"));sample.captured=true;
                        }
                        if(voice.isPlaying&&voice.time>.5f&&!report.paused)
                        {
                            float before=voice.time;SetMenuOpen(true);
                            yield return new WaitForSecondsRealtime(.4f);
                            report.paused=Mathf.Abs(voice.time-before)<.03f;
                            SetMenuOpen(false);yield return new WaitForSecondsRealtime(.25f);
                            report.resumed=voice.isPlaying&&voice.time>before+.1f;
                        }
                    }
                    yield return null;
                }
                if(busy){CancelLocal();Debug.LogError("PERFORMANCE_REPLAY_FAILED: timeout");Application.Quit(3);yield break;}
            }
            int expected=0;foreach(var turn in replay.turns)expected+=turn.reply.segments.Length;
            report.completed=report.beats.Count==expected;
            // Cancel a two-beat queue during its first audio clip. Neither the second
            // beat nor the old coroutine may restore speech, cues or subtitles.
            var first=replay.turns[0].reply.segments[0];
            var queued=new Reply{segments=new[]{first,first}};
            busy=true;int token=version;StartCoroutine(PlayReply(queued,token));
            deadline=Time.realtimeSinceStartup+20;
            while(!voice.isPlaying&&busy&&Time.realtimeSinceStartup<deadline)yield return null;
            bool started=voice.isPlaying;CancelLocal();
            yield return new WaitForSecondsRealtime(2.5f);
            report.interrupted=started&&!voice.isPlaying&&!face.IsSpeaking&&face.JawWeight<.03f;
            report.noLateBeat=activeBeat==null&&Subtitle==""&&performance.Gesture=="none"&&!busy;
            report.passed=report.completed&&report.paused&&report.resumed&&report.interrupted&&report.noLateBeat;
            foreach(var beat in report.beats)
            {
                report.passed&=beat.emotionMatched&&beat.audioPlayed&&beat.maximumJaw>.02f&&beat.captured;
                if(beat.gesture!="none")report.passed&=beat.gestureSeen&&beat.gestureTimingError<.3f;
                if(beat.emotion=="crying")report.passed&=beat.maximumWetness>.3f&&beat.maximumCover>.8f&&beat.handToHeadAtCapture<.4f;
            }
            File.WriteAllText(Path.Combine(folder,"performance-playback-report.json"),JsonUtility.ToJson(report,true));
            Debug.Log(report.passed?"PERFORMANCE_REPLAY_OK":"PERFORMANCE_REPLAY_FAILED: assertions");
            Application.Quit(report.passed?0:4);
        }
    }
}
