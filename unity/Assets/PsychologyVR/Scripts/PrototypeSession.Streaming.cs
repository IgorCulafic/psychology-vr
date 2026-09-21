using System;
using System.Collections;
using UnityEngine;

namespace PsychologyVR
{
    public partial class PrototypeSession
    {
        bool supportsStreaming;
        string streamTurnId;
        int streamCompleted;
        int sessionGeneration;
        float streamPartialSeconds;

        RequestBody PlaybackRequest()=>new RequestBody{session_id=sessionId,turn_id=streamTurnId,
            completed_count=streamCompleted,partial_seconds=streamPartialSeconds};

        IEnumerator TrackPlayback(int token,string turn)
        {
            while(token==version && streamTurnId==turn)
            {
                // Persist the audio clock during a sentence, including paused playback.
                // At most one heartbeat request is outstanding; stale updates are ignored.
                yield return new WaitForSecondsRealtime(1);
                if(token!=version || streamTurnId!=turn)yield break;
                yield return Post("/playback",PlaybackRequest(),raw=>{},false,false);
            }
        }

        // Opt-in regression check through the actual HTTP, audio and menu path.
        IEnumerator CheckStreamingPlayback()
        {
            float deadline=Time.realtimeSinceStartup+35;
            while((string.IsNullOrEmpty(sessionId)||IsSwitching)&&Time.realtimeSinceStartup<deadline)yield return null;
            if(!supportsStreaming || string.IsNullOrEmpty(sessionId)){Debug.LogError("STREAM_CHECK_FAILED connection");Application.Quit(2);yield break;}
            Submit("",true);
            deadline=Time.realtimeSinceStartup+90;
            while(!voice.isPlaying && busy && Time.realtimeSinceStartup<deadline)yield return null;
            if(!voice.isPlaying){Debug.LogError("STREAM_CHECK_FAILED first audio "+Status);Application.Quit(3);yield break;}
            yield return new WaitForSecondsRealtime(.3f);
            SetMenuOpen(true);float before=voice.time;
            yield return new WaitForSecondsRealtime(.4f);
            bool pauseHeld=Mathf.Abs(voice.time-before)<.05f;SetMenuOpen(false);
            deadline=Time.realtimeSinceStartup+90;
            while((streamCompleted<1 || !voice.isPlaying || voice.time<.25f) && busy && Time.realtimeSinceStartup<deadline)yield return null;
            bool partial=streamCompleted>=1 && voice.isPlaying && voice.time>=.25f;
            string checkedTurn=streamTurnId;
            Debug.Log("STREAM_CHECK_PREFIX count="+streamCompleted+" partial="+streamPartialSeconds+" turn="+checkedTurn+" session="+sessionId);
            Interrupt(false);
            deadline=Time.realtimeSinceStartup+20;
            while(busy&&Time.realtimeSinceStartup<deadline)yield return null;
            yield return new WaitForSecondsRealtime(3);
            bool stopped=!voice.isPlaying && !busy && activeBeat==null && string.IsNullOrEmpty(streamTurnId);
            Debug.Log(pauseHeld&&partial&&stopped?"STREAM_CHECK_OK":"STREAM_CHECK_FAILED pause="+pauseHeld+" partial="+partial+" stopped="+stopped);
            Application.Quit(pauseHeld&&partial&&stopped?0:4);
        }

        IEnumerator FinishStream(bool interrupted)
        {
            var body=PlaybackRequest();body.interrupted=interrupted;
            bool success=false;
            yield return Post("/turn/finish",body,raw=>{
                var result=JsonUtility.FromJson<Reply>(raw);Relationship=result.relationship;sessionGeneration=result.generation;success=true;
            },false);
            if(success){streamTurnId=null;streamCompleted=0;streamPartialSeconds=0;}
        }

        IEnumerator StreamedTurn(string text,bool opening)
        {
            busy=true;int token=version;
            Status=CurrentScenario.character_name+" is preparing a reply…";
            Reply started=null;
            yield return Post("/turn/start",new RequestBody{session_id=sessionId,text=text,opening=opening,expected_generation=sessionGeneration},
                raw=>started=JsonUtility.FromJson<Reply>(raw));
            if(token!=version)yield break;
            if(started==null){busy=false;yield break;}
            streamTurnId=started.turn_id;streamCompleted=0;streamPartialSeconds=0;
            StartCoroutine(TrackPlayback(token,streamTurnId));
            float began=Time.realtimeSinceStartup,lastProgress=began;
            bool failed=false;string failure=null;
            while(token==version)
            {
                Reply batch=null;
                yield return Post("/turn/poll",PlaybackRequest(),raw=>batch=JsonUtility.FromJson<Reply>(raw));
                if(token!=version)yield break;
                if(batch==null || batch.closed){failed=true;failure="Reply connection was lost. Stop/reconnect to retry.";break;}
                if(batch.segments!=null && streamCompleted<batch.segments.Length)
                {
                    var segment=batch.segments[streamCompleted];streamPartialSeconds=0;
                    // Server synthesis continues while this existing playback routine runs.
                    if(streamCompleted==0)Debug.Log("STREAM_FIRST_PLAYBACK_MS "+Mathf.RoundToInt((Time.realtimeSinceStartup-began)*1000));
                    yield return PlayReply(new Reply{segments=new[]{segment}},token,true);
                    if(token!=version)yield break;
                    if(!busy){failed=true;failure="Speech audio could not be played.";break;}
                    bool acknowledged=false;
                    yield return Post("/playback",PlaybackRequest(),raw=>acknowledged=true);
                    if(token!=version)yield break;
                    if(!acknowledged){failed=true;failure="Playback could not be saved. Reconnect before continuing.";break;}
                    lastProgress=Time.realtimeSinceStartup;
                    continue;
                }
                if(batch.done){failed=!string.IsNullOrEmpty(batch.error);failure=batch.error;break;}
                if(Time.realtimeSinceStartup-lastProgress>180){failed=true;failure="Speech preparation timed out.";break;}
                Status=streamCompleted>0?"Preparing the next sentence…":CurrentScenario.character_name+" is preparing a reply…";
                yield return new WaitForSecondsRealtime(.12f);
            }
            if(token!=version)yield break;
            yield return FinishStream(failed);
            if(token!=version)yield break;
            if(!string.IsNullOrEmpty(streamTurnId))
            {Status="Playback could not be saved. Use Stop reply or Reconnect before continuing.";yield break;}
            busy=false;activeBeat=null;performance?.StopGesture();
            Status=failed?failure:SessionEnded?"The patient ended the session. Open the menu to start a new conversation.":"Ready. Hold Space / right A to speak.";
            Debug.Log("STREAM_PLAYBACK_FINISHED interrupted="+failed);
        }
    }
}
