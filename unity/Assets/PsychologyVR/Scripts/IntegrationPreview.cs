using System;
using System.Collections;
using System.IO;
using UnityEngine;

namespace PsychologyVR
{
    public static class IntegrationPreview
    {
        [Serializable] class PlayerReport
        {
            public float leftReachError,rightReachError,lostTrackingReachError,headLeanDegrees,fingerMovementDegrees;
            public bool hiddenHead,finiteUnreachablePose,passed;
        }
        public static IEnumerator Run(FacialPerformance face,AudioSource voice,Camera view,SeatedPlayerAvatar player,Action<Camera,string> capture)
        {
            var args=Environment.GetCommandLineArgs();int at=Array.IndexOf(args,"--capture-path");
            if(!player || !face || at<0){Debug.LogError("INTEGRATION_FAILED: missing actor, player or output");Application.Quit(2);yield break;}
            string directory=Path.GetDirectoryName(args[at+1]);Directory.CreateDirectory(directory);
            yield return null;yield return new WaitForEndOfFrame();
            face.body.Apply("calm",.5f,"none",true);
            yield return new WaitForSeconds(1);
            capture(view,Path.Combine(directory,"consultation-seated.png"));
            var report=new PlayerReport{hiddenHead=true};
            foreach(var mesh in player.GetComponentsInChildren<SkinnedMeshRenderer>())
            {
                if(mesh.name=="CC_Base_Body")
                    for(int s=0;s<mesh.sharedMaterials.Length;s++)if(mesh.sharedMaterials[s].name.Contains("Skin_Head")&&mesh.sharedMesh.GetIndexCount(s)>0)report.hiddenHead=false;
                if(mesh.name.Contains("Eye")||mesh.name.Contains("Hair")||mesh.name.Contains("Teeth"))report.hiddenHead=false;
            }
            Transform finger=null,spine=null;
            foreach(var t in player.GetComponentsInChildren<Transform>()){if(t.name=="CC_Base_L_Index2")finger=t;if(t.name=="CC_Base_Waist")spine=t;}
            player.SetDiagnosticPose(SeatedPlayerAvatar.SeatedEyes,Quaternion.identity,new Vector3(-.28f,.94f,.36f),Quaternion.identity,new Vector3(.28f,.94f,.36f),Quaternion.identity);
            yield return new WaitForSeconds(.5f);Quaternion open=finger.localRotation,rest=spine.rotation;
            report.leftReachError=player.LeftReachError;report.rightReachError=player.RightReachError;
            view.transform.localRotation=Quaternion.Euler(28,0,0);yield return new WaitForEndOfFrame();capture(view,Path.Combine(directory,"player-first-person.png"));
            var overview=new GameObject("Integration overview").AddComponent<Camera>();overview.enabled=false;overview.nearClipPlane=.05f;
            overview.transform.position=new Vector3(2.5f,1.65f,-2.9f);overview.transform.LookAt(new Vector3(0,.95f,-.35f));overview.fieldOfView=60;
            capture(overview,Path.Combine(directory,"consultation-both-avatars.png"));
            player.SetDiagnosticPose(SeatedPlayerAvatar.SeatedEyes+new Vector3(.12f,0,.10f),Quaternion.Euler(0,25,0),new Vector3(-.28f,.94f,.36f),Quaternion.identity,new Vector3(.28f,.94f,.36f),Quaternion.identity,1);
            yield return new WaitForSeconds(.5f);report.fingerMovementDegrees=Quaternion.Angle(open,finger.localRotation);report.headLeanDegrees=Quaternion.Angle(rest,spine.rotation);
            player.SetDiagnosticPose(SeatedPlayerAvatar.SeatedEyes,Quaternion.identity,new Vector3(-3,3,3),Quaternion.identity,new Vector3(3,3,3),Quaternion.identity);
            yield return null;yield return new WaitForEndOfFrame();
            report.finiteUnreachablePose=float.IsFinite(player.LeftWrist.position.x)&&float.IsFinite(player.RightWrist.position.y)&&Vector3.Distance(player.LeftWrist.position,player.transform.position)<2;
            player.SetDiagnosticPose(SeatedPlayerAvatar.SeatedEyes,Quaternion.identity,Vector3.zero,Quaternion.identity,Vector3.zero,Quaternion.identity,0,false);
            yield return new WaitForSeconds(.4f);report.lostTrackingReachError=Mathf.Max(player.LeftReachError,player.RightReachError);
            report.passed=report.hiddenHead && report.leftReachError<.04f && report.rightReachError<.04f && report.lostTrackingReachError<.04f && report.fingerMovementDegrees>20 && report.headLeanDegrees>5 && report.finiteUnreachablePose;
            File.WriteAllText(Path.Combine(directory,"player-tracking-check.json"),JsonUtility.ToJson(report,true));
            if(!report.passed){Debug.LogError("PLAYER_TRACKING_PREVIEW_FAILED");Application.Quit(5);yield break;}
            Debug.Log("PLAYER_TRACKING_PREVIEW_OK");
            yield return AlexPerformancePreview.Run(face,voice,view,capture);
        }
    }
}
