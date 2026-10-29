using System.Collections.Generic;
using UnityEngine;

namespace PsychologyVR
{
    // One upper-body insert over the recorded idle. Pelvis/legs are never sampled here.
    internal sealed class MetaHumanSeatedGestures
    {
        sealed class Binding
        {
            public MetaHumanGestureLibrary.Gesture gesture;
            public Transform[] bones;
            public Quaternion[] idle;
        }
        readonly GameObject body;
        readonly Binding[] bindings;
        Binding active;
        string previous="";
        float time,weight,release=-1,releaseWeight;
        float idleWait=16,speechWait,headWait=35,cooldown;
        bool wasSpeaking;
        public bool Automatic=true;
        public string Active=>active==null?"":active.gesture.id;
        public float Time=>time;
        public float HeadContactWeight=>active!=null&&active.gesture.headContact?weight:0;

        public MetaHumanSeatedGestures(GameObject body,MetaHumanGestureLibrary library,Dictionary<string,Transform> bones)
        {
            this.body=body;bindings=new Binding[library.gestures.Length];
            for(int i=0;i<bindings.Length;i++)
            {
                var gesture=library.gestures[i];var targets=new Transform[gesture.bones.Length];
                for(int k=0;k<targets.Length;k++)targets[k]=bones[gesture.bones[k]];
                bindings[i]=new Binding{gesture=gesture,bones=targets,idle=new Quaternion[targets.Length]};
            }
        }

        public bool Play(string id)
        {
            if(active!=null)return false;
            foreach(var binding in bindings)if(binding.gesture.id==id){Start(binding);return true;}
            return false;
        }
        void Start(Binding binding)
        {
            active=binding;previous=binding.gesture.id;time=weight=0;release=-1;
            idleWait=Random.Range(16f,28f);cooldown=7;
            if(binding.gesture.headContact)headWait=Random.Range(55f,85f);
        }
        public void Stop(bool interrupt)
        {
            if(active!=null&&(interrupt||active.gesture.kind==MetaHumanGestureLibrary.Kind.Speech)&&release<0)
            {release=0;releaseWeight=weight;}
        }
        bool Choose(MetaHumanGestureLibrary.Kind kind)
        {
            Binding choice=null,repeat=null;int count=0;
            foreach(var binding in bindings)
            {
                var g=binding.gesture;
                if(g.kind!=kind||(g.headContact&&headWait>0))continue;
                if(g.id==previous){repeat=binding;continue;}
                if(Random.Range(0,++count)==0)choice=binding;
            }
            if(choice==null)choice=repeat;
            if(choice==null)return false;
            Start(choice);return true;
        }
        public void Apply(string emotion,float intensity,bool speaking,float dt)
        {
            headWait-=dt;cooldown-=dt;
            bool strong=(emotion=="crying"||emotion=="panicked"||emotion=="angry"||emotion=="numb")&&intensity>.6f;
            if(speaking&&!wasSpeaking)speechWait=Random.value<.6f?Random.Range(.65f,1.3f):9;
            if(!speaking&&wasSpeaking)Stop(false);
            wasSpeaking=speaking;
            if(Automatic&&active==null&&!strong)
            {
                if(speaking)
                {
                    speechWait-=dt;
                    if(speechWait<=0&&cooldown<=0)
                    {Choose(MetaHumanGestureLibrary.Kind.Speech);speechWait=Random.Range(10f,17f);}
                }
                else
                {
                    idleWait-=dt;
                    if(idleWait<=0)
                    {
                        var kind=emotion=="anxious"||emotion=="afraid"?MetaHumanGestureLibrary.Kind.Tension:
                            emotion=="sad"?MetaHumanGestureLibrary.Kind.Thoughtful:MetaHumanGestureLibrary.Kind.Idle;
                        if(!Choose(kind))Choose(MetaHumanGestureLibrary.Kind.Idle);
                        idleWait=Random.Range(16f,28f);
                    }
                }
            }
            if(active==null)return;
            time+=dt;
            var clip=active.gesture.clip;
            bool large=active.gesture.headContact||active.gesture.id=="fold_arms";
            weight=Mathf.SmoothStep(0,1,time/(large?1f:.8f))*Mathf.SmoothStep(0,1,(clip.length-time)/(large?.95f:.8f));
            if(release>=0)
            {
                release+=dt;weight=Mathf.Min(weight,releaseWeight*(1-Mathf.SmoothStep(0,1,release/.75f)));
            }
            if(time>=clip.length||(release>=.75f))
            {active=null;weight=0;return;}
            for(int i=0;i<active.bones.Length;i++)active.idle[i]=active.bones[i].localRotation;
            clip.SampleAnimation(body,time);
            for(int i=0;i<active.bones.Length;i++)
            {
                var target=active.bones[i];var q=target.localRotation;
                if(active.gesture.additive)q=active.idle[i]*q;
                target.localRotation=Quaternion.Slerp(active.idle[i],q,weight);
            }
        }
    }
}
