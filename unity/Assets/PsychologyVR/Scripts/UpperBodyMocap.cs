using System.Collections.Generic;
using UnityEngine;

namespace PsychologyVR
{
    // These clips are retargeted to Jumper and contain rotation curves only
    // above the waist. The seated foundation remains owned by PerformanceDriver.
    internal sealed class UpperBodyMocap
    {
        sealed class Bone
        {
            public Transform target,sample;
            public Quaternion rotation;
            public int arm;
        }
        readonly GameObject source;
        readonly List<Bone> bones=new List<Bone>();
        readonly AnimationClip talk,sad,frustrated;
        AnimationClip active;
        string previousEmotion;
        float time,weight,nextAction;
        bool finishing;
        readonly Transform leftSampleHand,rightSampleHand;
        readonly Transform leftSampleForearm,rightSampleForearm;
        readonly bool leftIsCCLeft;
        internal float Weight=>weight;

        internal UpperBodyMocap(Transform actor,Transform leftHand,Transform rightHand)
        {
            leftIsCCLeft=leftHand.name.Contains("_L_");
            talk=Resources.Load<AnimationClip>("JumperMocap/UpperBody/Talk");
            sad=Resources.Load<AnimationClip>("JumperMocap/UpperBody/Sad");
            frustrated=Resources.Load<AnimationClip>("JumperMocap/UpperBody/Frustrated");
            if(!talk||!sad||!frustrated)
            {Debug.LogError("Jumper upper-body clips are missing from Resources/JumperMocap/UpperBody",actor);return;}
            source=new GameObject("Jumper upper-body sampler");source.hideFlags=HideFlags.HideInHierarchy;
            Copy(actor,source.transform,false,0);
            foreach(var bone in bones)
            {
                if(bone.target==leftHand)leftSampleHand=bone.sample;
                if(bone.target==rightHand)rightSampleHand=bone.sample;
                if(bone.target==leftHand.parent)leftSampleForearm=bone.sample;
                if(bone.target==rightHand.parent)rightSampleForearm=bone.sample;
            }
            source.AddComponent<Animator>();
        }
        void Copy(Transform target,Transform sample,bool upper,int arm)
        {
            upper|=target.name=="CC_Base_Waist";
            if(target.name.EndsWith("_Clavicle"))arm=target.name.Contains("_L_")==leftIsCCLeft?1:2;
            if(upper && target.name.StartsWith("CC_Base_") && !target.name.Contains("Eye") &&
                !target.name.Contains("Jaw") && !target.name.Contains("Tongue"))
                bones.Add(new Bone{target=target,sample=sample,rotation=target.localRotation,arm=arm});
            foreach(Transform child in target)
            {
                // Copy transforms only; no mesh, rig, renderer or behaviour runs here.
                if(!child.name.StartsWith("CC_Base_"))continue;
                var copy=new GameObject(child.name).transform;copy.SetParent(sample,false);
                copy.localPosition=child.localPosition;copy.localRotation=child.localRotation;copy.localScale=child.localScale;
                Copy(child,copy,upper,arm);
            }
        }

        internal void Tick(float delta,string emotion,float intensity,bool speaking,bool suppressed,float brace,Vector3 leftRest,Vector3 rightRest)
        {
            if(!source)return;
            if(previousEmotion!=emotion)
            {previousEmotion=emotion;nextAction=0;finishing=true;}
            AnimationClip requested=suppressed?null:
                emotion=="sad"||emotion=="despondent"?sad:
                emotion=="angry"||emotion=="frustrated"?frustrated:
                speaking && (emotion=="neutral"||emotion=="calm"||emotion=="hopeful"||emotion=="happy"||emotion=="confused"||emotion=="anxious")?talk:null;
            nextAction-=delta;
            if(active && (active!=requested||brace>0))finishing=true;
            if(!active && requested && nextAction<=0 && brace==0)
            {active=requested;time=0;finishing=false;}
            if(active)
            {
                time=Mathf.Min(time+delta,active.length);
                if(time>=active.length-.7f)finishing=true;
                float desired=finishing?0:active==talk?1:Mathf.Lerp(.65f,1,intensity);
                weight=Mathf.MoveTowards(weight,desired,delta/.65f);
                active.SampleAnimation(source,time);
                BendForSeat(leftSampleForearm,leftSampleHand,leftRest);
                BendForSeat(rightSampleForearm,rightSampleHand,rightRest);
                float smoothing=1-Mathf.Exp(-delta/.07f);
                foreach(var bone in bones)bone.rotation=Quaternion.Slerp(bone.rotation,bone.sample.localRotation,smoothing);
                if(finishing && weight==0)
                {
                    nextAction=active!=requested||active==talk?0:Random.Range(18f,30f);
                    active=null;
                }
            }
        }
        static void BendForSeat(Transform forearm,Transform hand,Vector3 support)
        {
            float blend=1-Mathf.SmoothStep(0,1,(hand.position.y-support.y+.03f)/.09f);
            // Bend the elbow in FK to replace the standing arms-down baseline.
            // Elevated gestures keep the recording, including wrist/finger motion.
            Quaternion correction=Quaternion.FromToRotation(hand.position-forearm.position,support-forearm.position);
            forearm.rotation=Quaternion.Slerp(Quaternion.identity,correction,blend)*forearm.rotation;
        }
        internal void ApplyTorso()
        {
            if(weight==0)return;
            foreach(var bone in bones)if(bone.arm==0)
                bone.target.localRotation=Quaternion.Slerp(bone.target.localRotation,bone.rotation,weight);
        }
        internal void ApplyArms(float availability)
        {
            if(!source)return;
            foreach(var bone in bones)if(bone.arm!=0)
                bone.target.localRotation=Quaternion.Slerp(bone.target.localRotation,bone.rotation,weight*availability);
        }
        internal void Dispose(){if(source)Object.Destroy(source);}
    }
}
