using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using UnityEngine;
namespace PsychologyVR
{
    // Isolated audition of the supplied CC facial rig. No generated Alex morphs.
    [DefaultExecutionOrder(100)]
    public class CandidateExpressionPreview : MonoBehaviour
    {
        public GameObject character;
        public Camera view;
        readonly Dictionary<string,float> targets=new Dictionary<string,float>();
        SkinnedMeshRenderer[] meshes;
        Transform jaw,head;Quaternion jawRest;Vector3 jawAxis;float jawAmount;
        PerformanceDriver body;FaceTears tears;SkinnedMeshRenderer skin;MaterialPropertyBlock flushBlock;
        string currentMood="Neutral";float moodStarted,flush;Vector3 forward;bool closeView=true;bool handView;
        float intensity=1;
        void Set(string name,float value){targets[name]=value;}
        void Pair(string name,float value){Set(name+"_L",value);Set(name+"_R",value);}
        void Mood(string mood)
        {
            targets.Clear();currentMood=mood;moodStarted=Time.time;
            string canonical=mood=="Happiness"?"happy":mood=="Sadness"?"sad":mood=="Anger"?"angry":mood=="Fear"?"afraid":mood=="Panic"?"panicked":mood=="Disgust"?"disgusted":mood=="Crying"?"crying":mood=="Surprise"?"surprised":mood=="Despondency"?"despondent":mood=="Numbness"?"numb":mood=="Frustration"?"frustrated":"neutral";
            if(body)body.Apply(canonical,mood=="Neutral"?0:intensity,"none");
            switch(mood)
            {
                case "Happiness":Pair("Mouth_Smile",.8f);Pair("Cheek_Raise",.45f);Pair("Eye_Squint",.25f);break;
                case "Sadness":Pair("Brow_Raise_Inner",.9f);Pair("Brow_Drop",.2f);Pair("Mouth_Frown",.75f);Set("Mouth_Shrug_Lower",.3f);break;
                case "Anger":Pair("Brow_Drop",1);Pair("Brow_Compress",1);Pair("Eye_Squint",.72f);Pair("Mouth_Press",.60f);Pair("Mouth_Tighten",.2f);Pair("Mouth_Frown",.4f);Pair("Nose_Nostril_Dilate",.45f);break;
                case "Fear":Pair("Brow_Raise_Inner",.9f);Pair("Brow_Raise_Outer",.5f);Pair("Eye_Wide",.8f);Pair("Mouth_Stretch",.5f);Set("Jaw_Open",.25f);break;
                case "Disgust":Pair("Nose_Sneer",.9f);Pair("Nose_Crease",.5f);Pair("Mouth_Up_Upper",.6f);Pair("Eye_Squint",.45f);Pair("Brow_Drop",.4f);break;
                case "Crying":Pair("Brow_Raise_Inner",1);Pair("Mouth_Frown",.8f);Pair("Eye_Squint",.65f);Pair("Eye_Blink",.4f);Set("Jaw_Open",.25f);break;
                case "Panic":Pair("Brow_Raise_Inner",1);Pair("Brow_Raise_Outer",.8f);Pair("Eye_Wide",1);Pair("Mouth_Stretch",.6f);Set("Jaw_Open",.35f);break;
                case "Surprise":Pair("Brow_Raise_Outer",.9f);Pair("Brow_Raise_Inner",.7f);Pair("Eye_Wide",.7f);Set("Jaw_Open",.35f);break;
                case "Despondency":Pair("Brow_Raise_Inner",.2f);Pair("Mouth_Frown",.5f);Pair("Eye_Blink",.45f);Set("Eye_L_Look_Down",.9f);Set("Eye_R_Look_Down",.9f);Set("Jaw_Open",.035f);break;
                case "Frustration":Pair("Brow_Compress",.35f);Set("Brow_Raise_Inner_L",.5f);Set("Brow_Raise_Outer_L",.65f);Pair("Mouth_Press",.5f);Set("Mouth_L",.2f);break;
                case "Numbness":Pair("Eye_Squint",.15f);break;
                case "Blink":Pair("Eye_Blink",1);break;
                case "Speech shapes":Set("V_Open",.65f);break;
            }
        }
        void LateUpdate()
        {
            if(meshes==null)return;
            float age=Time.time-moodStarted;
            if(currentMood=="Crying")Set("Jaw_Open",.12f+Mathf.Pow(Mathf.Max(0,Mathf.Sin(age*7)),3)*.17f);
            if(currentMood=="Anger")Set("Jaw_Open",.015f+PerformanceDriver.AngerBeat(age)*.055f);
            if(currentMood=="Surprise")
            {
                float recovery=1-Mathf.SmoothStep(0,1,(age-1.2f)/2.5f);
                Pair("Brow_Raise_Outer",.25f+.65f*recovery);Pair("Brow_Raise_Inner",.2f+.5f*recovery);Pair("Eye_Wide",.15f+.55f*recovery);Set("Jaw_Open",.35f*recovery);
            }
            if(tears)tears.SetIntensity(currentMood=="Crying"?1:0);
            flush=Mathf.MoveTowards(flush,currentMood=="Crying"?.8f:currentMood=="Anger"?.55f:0,Time.deltaTime*.45f);
            if(skin){skin.GetPropertyBlock(flushBlock,0);flushBlock.SetColor("_BaseColor",Color.Lerp(Color.white,new Color(1,.76f,.70f),flush));skin.SetPropertyBlock(flushBlock,0);}
            if(closeView && head){Vector3 focus=head.position+Vector3.up*.035f;view.transform.position=focus+forward*.82f;view.transform.LookAt(focus);view.fieldOfView=36;}
            if(handView && body)
            {
                Vector3 center=(body.LeftWrist.position+body.RightWrist.position)*.5f;
                Vector3 right=Vector3.Cross(Vector3.up,forward);
                float distance=.68f+Vector3.Distance(body.LeftWrist.position,body.RightWrist.position)*.45f;
                view.transform.position=center+forward*distance+right*.15f+Vector3.up*.27f;
                view.transform.LookAt(center);view.fieldOfView=49;
            }
            float opening=0;
            if(targets.TryGetValue("Jaw_Open",out float j))opening=Mathf.Max(opening,j);
            if(targets.TryGetValue("V_Open",out float v))opening=Mathf.Max(opening,v);
            if(targets.TryGetValue("V_Tight_O",out float o))opening=Mathf.Max(opening,o*.5f);
            jawAmount=Mathf.Lerp(jawAmount,opening,1-Mathf.Exp(-8*Time.deltaTime));
            if(jaw)jaw.localRotation=jawRest*Quaternion.AngleAxis(jawAmount*25,jawAxis);
            foreach(var m in meshes)for(int i=0;i<m.sharedMesh.blendShapeCount;i++)
            {
                string n=m.sharedMesh.GetBlendShapeName(i);int dot=n.LastIndexOf('.');if(dot>=0)n=n.Substring(dot+1);
                targets.TryGetValue(n,out float goal);
                if((m.name.Contains("Mustache") || m.name.Contains("Soul_Patch")) && (n=="Jaw_Open" || n=="V_Open"))goal=0;
                m.SetBlendShapeWeight(i,Mathf.Lerp(m.GetBlendShapeWeight(i),goal*100,1-Mathf.Exp(-8*Time.deltaTime)));
            }
        }
        IEnumerator Start()
        {
            meshes=character.GetComponentsInChildren<SkinnedMeshRenderer>();
            CandidateSeatedPose.Apply(character);
            body=character.AddComponent<PerformanceDriver>();body.useStaticSeatedPose=true;body.Apply("neutral",0,"none",true);
            foreach(var a in character.GetComponentsInChildren<Animator>())a.enabled=false;
            yield return null;yield return new WaitForEndOfFrame();
            Transform leftEye=null,rightEye=null;
            foreach(var t in character.GetComponentsInChildren<Transform>())
            {if(t.name=="CC_Base_JawRoot")jaw=t;if(t.name=="CC_Base_Head")head=t;if(t.name=="CC_Base_L_Eye")leftEye=t;if(t.name=="CC_Base_R_Eye")rightEye=t;}
            Vector3 eyes=(leftEye.position+rightEye.position)*.5f;
            forward=eyes-head.position;forward.y=0;forward.Normalize();
            jawRest=jaw.localRotation;jawAxis=jaw.InverseTransformDirection(Vector3.Cross(Vector3.up,forward));
            foreach(var m in meshes)if(m.name=="CC_Base_Body")skin=m;
            flushBlock=new MaterialPropertyBlock();tears=character.AddComponent<FaceTears>();
            tears.startHeight=eyes.y-head.position.y-.012f;tears.endHeight=tears.startHeight-.085f;tears.startWidth=.026f;tears.endWidth=.040f;
            tears.Initialize(head,skin);
            yield return null;yield return new WaitForEndOfFrame();
            Vector3 focus=eyes-Vector3.up*.035f;
            view.transform.position=focus+forward*.70f;view.transform.LookAt(focus);view.fieldOfView=35;
            Debug.Log("CANDIDATE_CAMERA head="+head.position+" eyes="+eyes+" forward="+forward);
            string folder=Path.GetFullPath(Path.Combine(Application.dataPath,"../../../../docs/generated/candidate-preview"));Directory.CreateDirectory(folder);
            var args=Environment.GetCommandLineArgs();int at=Array.IndexOf(args,"--output");if(at>=0){folder=args[at+1];Directory.CreateDirectory(folder);}
            var rt=new RenderTexture(960,720,24);var pixels=new Texture2D(960,720,TextureFormat.RGB24,false);
            Time.captureFramerate=24;int frame=0;
            bool contrast=Array.IndexOf(args,"--contrast-preview")>=0;handView=Array.IndexOf(args,"--hand-preview")>=0;
            var manifest=new AlexAnimationRecorder.Manifest();var clip=new AlexAnimationRecorder.Clip{name=handView?"jumper-hand-refinement":contrast?"jumper-emotion-contrast":"jumper-emotions-full"};manifest.clips.Add(clip);
            string frames=Path.Combine(folder,clip.name);Directory.CreateDirectory(frames);
            var moods=handView?new[]{"Neutral","Anger","Neutral","Frustration","Despondency","Crying body","Neutral"}:contrast?new[]{"Neutral","Anger","Frustration","Sadness","Despondency","Numbness","Fear","Panic","Surprise"}:new[]{"Neutral","Crying","Anger","Fear","Panic","Disgust","Happiness","Sadness","Surprise","Despondency","Numbness","Crying body","Anger body","Neutral"};
            foreach(var mood in moods)
            {
                closeView=!handView && !contrast && !mood.EndsWith("body");intensity=mood=="Crying"?.5f:1;
                if(!closeView){view.transform.position=new Vector3(0,1.02f,0)+forward*1.65f;view.transform.LookAt(new Vector3(0,1.02f,0));view.fieldOfView=43;}
                Mood(mood.Replace(" body",""));
                int duration=handView?(mood=="Neutral"?72:mood=="Crying body"?216:144):contrast?(mood=="Neutral"?72:192):mood=="Crying body"?216:mood=="Crying"?144:mood=="Anger body"?144:96;
                clip.chapters.Add(new AlexAnimationRecorder.Chapter{start=frame,end=frame+duration,label=mood=="Crying body"?"Intense crying - face in hands":mood=="Anger body"?"Anger - body performance":mood});
                for(int i=0;i<duration;i++)
                {
                    if(contrast)closeView=i>=120;
                    if(mood=="Speech shapes")
                    {targets.Clear();Set(i<24?"V_Open":i<48?"V_Tight_O":"V_Explosive",.9f);}
                    yield return new WaitForEndOfFrame();
                    UnityEngine.Rendering.RenderPipeline.SubmitRenderRequest(view,new UnityEngine.Rendering.Universal.UniversalRenderPipeline.SingleCameraRequest{destination=rt});
                    RenderTexture.active=rt;pixels.ReadPixels(new Rect(0,0,960,720),0,0);pixels.Apply();RenderTexture.active=null;
                    File.WriteAllBytes(Path.Combine(frames,frame.ToString("D5")+".jpg"),pixels.EncodeToJPG(92));
                    if(i==108)File.WriteAllBytes(Path.Combine(folder,mood.Replace(' ','-')+"-posture.png"),pixels.EncodeToPNG());
                    if(i==duration-12)File.WriteAllBytes(Path.Combine(folder,mood.Replace(' ','-')+".png"),pixels.EncodeToPNG());frame++;
                }
            }
            clip.frames=frame;File.WriteAllText(Path.Combine(folder,"manifest.json"),JsonUtility.ToJson(manifest,true));
            Debug.Log("JUMPER_PERFORMANCE_CHECK anchors="+tears.AnchorCount+" reachError="+body.MaxReachError);
            Time.captureFramerate=0;Debug.Log("CANDIDATE_PREVIEW_OK "+frame);Application.Quit(0);
        }
    }
}
