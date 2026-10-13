using System;
using System.Collections.Generic;
using UnityEngine;

namespace PsychologyVR
{
    // Character Creator controls, composed with the shared audio-clock performer.
    public sealed class CCFacialRig
    {
        struct Binding { public SkinnedMeshRenderer mesh; public int index; public string name; }
        readonly List<Binding> bindings=new List<Binding>();
        readonly Dictionary<string,float> targets=new Dictionary<string,float>();
        readonly Transform root,head,jaw,leftEye,rightEye;
        readonly Quaternion jawRest,leftRest,rightRest;
        readonly Vector3 jawAxis,leftForward,rightForward;
        float jawAmount,started; string previous;
        public int BindingCount=>bindings.Count;
        public float JawWeight=>jawAmount;
        public SkinnedMeshRenderer Skin {get;private set;}
        public float EyeHeight {get;private set;}
        public CCFacialRig(GameObject actor,Transform headBone)
        {
            root=actor.transform;head=headBone;
            foreach(var t in actor.GetComponentsInChildren<Transform>())
            {
                if(t.name=="CC_Base_JawRoot")jaw=t;
                if(t.name=="CC_Base_L_Eye")leftEye=t;
                if(t.name=="CC_Base_R_Eye")rightEye=t;
            }
            jawRest=jaw.localRotation;jawAxis=jaw.InverseTransformDirection(root.right);
            leftRest=leftEye.localRotation;rightRest=rightEye.localRotation;
            leftForward=leftEye.InverseTransformDirection(root.forward);rightForward=rightEye.InverseTransformDirection(root.forward);
            EyeHeight=Vector3.Dot((leftEye.position+rightEye.position)*.5f-head.position,root.up);
            foreach(var mesh in actor.GetComponentsInChildren<SkinnedMeshRenderer>())
            {
                if(mesh.name=="CC_Base_Body")Skin=mesh;
                if(!mesh.sharedMesh)continue;
                for(int i=0;i<mesh.sharedMesh.blendShapeCount;i++)
                {
                    string n=mesh.sharedMesh.GetBlendShapeName(i);int dot=n.LastIndexOf('.');if(dot>=0)n=n.Substring(dot+1);
                    bindings.Add(new Binding{mesh=mesh,index=i,name=n});
                }
            }
        }
        void Set(string n,float v)=>targets[n]=v;
        void Pair(string n,float v){Set(n+"_L",v);Set(n+"_R",v);}
        public void Apply(string emotion,float intensity,Dictionary<string,float> common,bool speech,string cue,bool suppress,float transition=.65f)
        {
            if(previous!=emotion){previous=emotion;started=Time.time;}
            float age=Time.time-started;
            targets.Clear();
            switch(emotion)
            {
                case "calm":Pair("Mouth_Smile",.15f);Pair("Eye_Squint",.1f);break;
                case "anxious":Pair("Brow_Raise_Inner",.65f);Pair("Brow_Compress",.2f);Pair("Mouth_Press",.45f);break;
                case "happy":Pair("Mouth_Smile",.8f);Pair("Cheek_Raise",.45f);Pair("Eye_Squint",.25f);break;
                case "relieved":Pair("Mouth_Smile",.22f);Pair("Eye_Squint",.2f);Pair("Brow_Raise_Inner",.12f);break;
                case "hopeful":Pair("Mouth_Smile",.35f);Pair("Brow_Raise_Inner",.45f);Pair("Eye_Wide",.15f);break;
                case "sad":Pair("Brow_Raise_Inner",.9f);Pair("Brow_Drop",.2f);Pair("Mouth_Frown",.75f);Set("Mouth_Shrug_Lower",.3f);break;
                case "angry":Pair("Brow_Drop",1);Pair("Brow_Compress",1);Pair("Eye_Squint",.72f);Pair("Mouth_Press",.6f);Pair("Mouth_Tighten",.2f);Pair("Mouth_Frown",.4f);Pair("Nose_Nostril_Dilate",.45f);Set("Jaw_Open",.015f+(suppress?0:PerformanceDriver.AngerBeat(age)*.055f));break;
                case "afraid":Pair("Brow_Raise_Inner",.9f);Pair("Brow_Raise_Outer",.5f);Pair("Eye_Wide",.8f);Pair("Mouth_Stretch",.5f);Set("Jaw_Open",.25f);break;
                case "panicked":Pair("Brow_Raise_Inner",1);Pair("Brow_Raise_Outer",.8f);Pair("Eye_Wide",1);Pair("Mouth_Stretch",.6f);Set("Jaw_Open",.35f);break;
                case "disgusted":Pair("Nose_Sneer",.9f);Pair("Nose_Crease",.5f);Pair("Mouth_Up_Upper",.6f);Pair("Eye_Squint",.45f);Pair("Brow_Drop",.4f);break;
                case "crying":Pair("Brow_Raise_Inner",1);Pair("Mouth_Frown",.8f);Pair("Eye_Squint",.65f);Pair("Eye_Blink",.4f);Set("Jaw_Open",suppress?0:.12f+Mathf.Pow(Mathf.Max(0,Mathf.Sin(age*7)),3)*.17f);break;
                case "surprised":float recovery=1-Mathf.SmoothStep(0,1,(age-1.2f)/2.5f);Pair("Brow_Raise_Outer",.25f+.65f*recovery);Pair("Brow_Raise_Inner",.2f+.5f*recovery);Pair("Eye_Wide",.15f+.55f*recovery);Set("Jaw_Open",.35f*recovery);break;
                case "despondent":Pair("Brow_Raise_Inner",.2f);Pair("Mouth_Frown",.5f);Pair("Eye_Blink",.45f);Set("Jaw_Open",.035f);break;
                case "frustrated":Pair("Brow_Compress",.35f);Set("Brow_Raise_Inner_L",.5f);Set("Brow_Raise_Outer_L",.65f);Pair("Mouth_Press",.5f);Set("Mouth_L",.2f);break;
                case "ashamed":Pair("Brow_Raise_Inner",.65f);Pair("Eye_Blink",.35f);Pair("Mouth_Press",.5f);Pair("Mouth_Frown",.3f);break;
                case "guilty":Pair("Brow_Raise_Inner",.55f);Pair("Brow_Compress",.4f);Pair("Mouth_Frown",.4f);Set("Mouth_L",.2f);break;
                case "confused":Set("Brow_Raise_Outer_L",.55f);Pair("Brow_Raise_Inner",.3f);Pair("Eye_Wide",.2f);Set("Jaw_Open",.08f);break;
                case "skeptical":Set("Brow_Raise_Outer_L",.85f);Set("Brow_Drop_R",.4f);Set("Eye_Squint_R",.45f);Set("Mouth_L",.3f);Pair("Mouth_Press",.35f);break;
                case "numb":Pair("Eye_Squint",.15f);break;
            }
            foreach(var key in new List<string>(targets.Keys))targets[key]*=intensity;
            float blink=Mathf.Max(common["BlinkLeft"],Value("Eye_Blink_L"));Pair("Eye_Blink",blink);
            Pair("Eye_Wide",Value("Eye_Wide_L")*(1-blink));
            if(speech)
            {
                // Speech owns closures; emotional mouth tension must not mask consonants.
                foreach(var key in new List<string>(targets.Keys))if(key.StartsWith("Mouth_"))targets[key]*=.25f;
                Set("Jaw_Open",common["JawOpen"]*.75f);
                Pair("Mouth_Press",common["MouthPress"]);
                Pair("Mouth_Pucker_Up",common["MouthPucker"]);Pair("Mouth_Pucker_Down",common["MouthPucker"]);
                Set("V_Wide",common["MouthWide"]*.6f);
                if(cue=="A")Set("V_Explosive",.65f);
                if(cue=="G")Set("V_Dental_Lip",.65f);
                if(cue=="H")Set("V_Lip_Open",.4f);
            }
            float mouth=Value("Jaw_Open");
            Pair("Mouth_Smile",Value("Mouth_Smile_L")*(1-mouth*.7f));Pair("Mouth_Frown",Value("Mouth_Frown_L")*(1-mouth*.7f));
            jawAmount=Mathf.Lerp(jawAmount,mouth,1-Mathf.Exp(-22*Time.deltaTime));
            jaw.localRotation=jawRest*Quaternion.AngleAxis(jawAmount*25,jawAxis);
            foreach(var b in bindings)
            {
                float goal=Value(b.name);
                if((b.mesh.name.Contains("Mustache")||b.mesh.name.Contains("Soul_Patch"))&&(b.name=="Jaw_Open"||b.name=="V_Open"))goal=0;
                bool speechShape=b.name.StartsWith("Mouth")||b.name.StartsWith("V_")||b.name=="Jaw_Open";
                float rate=b.name.StartsWith("Eye_Blink")?70:speech&&speechShape?22:3/Mathf.Clamp(transition,.15f,2);
                b.mesh.SetBlendShapeWeight(b.index,Mathf.Lerp(b.mesh.GetBlendShapeWeight(b.index),goal*100,1-Mathf.Exp(-rate*Time.deltaTime)));
            }
            float yaw=(common["EyeLookRight"]-common["EyeLookLeft"])*9.7f;
            float pitch=(common["EyeLookUp"]-common["EyeLookDown"])*6.9f;
            if(emotion=="despondent")pitch=-12*intensity;
            Look(leftEye,leftRest,leftForward,yaw,pitch);Look(rightEye,rightRest,rightForward,yaw,pitch);
        }
        void Look(Transform eye,Quaternion rest,Vector3 forward,float yaw,float pitch)
        {
            eye.localRotation=rest;
            Vector3 direction=Quaternion.AngleAxis(yaw,root.up)*Quaternion.AngleAxis(-pitch,root.right)*eye.TransformDirection(forward);
            eye.rotation=Quaternion.FromToRotation(eye.TransformDirection(forward),direction)*eye.rotation;
        }
        float Value(string n)=>targets.TryGetValue(n,out float v)?v:0;
        public void Clear(){foreach(var b in bindings)if(b.mesh)b.mesh.SetBlendShapeWeight(b.index,0);if(jaw)jaw.localRotation=jawRest;}
    }
}
