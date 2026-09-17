using System;
using System.Collections.Generic;
using UnityEngine;

namespace PsychologyVR
{
    [Serializable] public class MouthCue {public float start,end;public string value;}

    // Runs after the seated animation and body overlays. AudioSource.time is the
    // clock for all mouth cues, so pause/stop never leave a separate timer running.
    [DefaultExecutionOrder(100)]
    public class FacialPerformance : MonoBehaviour
    {
        public PerformanceDriver body;
        public Transform conversationTarget;
        public bool automaticGaze=true;
        public bool gazeAversion=true;
        public float blinkOverride=-1,jawOverride=-1,puckerOverride=-1;
        public int ShapeBindingCount {get;private set;}
        public float JawWeight {get;private set;}
        public string CurrentMouthCue {get;private set;}="X";
        public bool IsSpeaking=>speaking&&!paused&&speech&&speech.isPlaying;
        public Transform Head=>head;
        public float EyeYaw {get;private set;}
        public FaceTears Tears {get;private set;}
        struct Binding {public SkinnedMeshRenderer renderer;public int index;public string name;}
        readonly List<Binding> bindings=new List<Binding>();
        readonly Dictionary<string,float> weights=new Dictionary<string,float>();
        readonly Dictionary<string,float> targets=new Dictionary<string,float>();
        static readonly string[] Shapes={"JawOpen","MouthPucker","MouthWide","MouthPress","MouthSmile","MouthFrown",
            "BrowWorry","BrowTense","BrowRaise","BlinkLeft","BlinkRight","EyeSquint","EyeLookLeft","EyeLookRight","EyeLookUp","EyeLookDown",
            "BrowRaiseLeft","EyeWide","NoseWrinkle","UpperLipRaise"};
        Transform head; Vector3 localForward,localUp,gazeOffset,smoothedDirection;
        float nextBlink,blinkStart=-10,nextGaze;
        SkinnedMeshRenderer faceSkin;
        MaterialPropertyBlock flushBlock;
        float flush;
        CCFacialRig ccRig;
        AudioSource speech; MouthCue[] cues; float[] envelope; float envelopeStep;bool speaking,paused;

        void Awake()
        {
            foreach(string shape in Shapes) {weights[shape]=0;targets[shape]=0;}
            foreach(var renderer in GetComponentsInChildren<SkinnedMeshRenderer>())
            {
                if(!renderer.sharedMesh)continue;
                for(int i=0;i<renderer.sharedMesh.blendShapeCount;i++)
                    foreach(string shape in Shapes)
                        if(renderer.sharedMesh.GetBlendShapeName(i).EndsWith(shape,StringComparison.Ordinal))
                            bindings.Add(new Binding{renderer=renderer,index=i,name=shape});
            }
            ShapeBindingCount=bindings.Count;
            foreach(var bone in GetComponentsInChildren<Transform>()) if(bone.name.EndsWith("mixamorig:Head") || bone.name=="CC_Base_Head") {head=bone;break;}
            if(head) {localForward=head.InverseTransformDirection(transform.forward);localUp=head.InverseTransformDirection(transform.up);}
            if(head && head.name=="CC_Base_Head")
            {
                ccRig=new CCFacialRig(gameObject,head);ShapeBindingCount=ccRig.BindingCount;
                faceSkin=ccRig.Skin;flushBlock=new MaterialPropertyBlock();Tears=gameObject.AddComponent<FaceTears>();
                Tears.startHeight=ccRig.EyeHeight-.012f;Tears.endHeight=Tears.startHeight-.085f;Tears.startWidth=.026f;Tears.endWidth=.040f;
                Tears.Initialize(head,faceSkin);
            }
            foreach(var binding in bindings)if(binding.name=="NoseWrinkle" && head)
            {faceSkin=binding.renderer;flushBlock=new MaterialPropertyBlock();Tears=gameObject.AddComponent<FaceTears>();Tears.Initialize(head,binding.renderer);break;}
            nextBlink=Time.time+UnityEngine.Random.Range(1.5f,3.5f);
        }

        public void BeginSpeech(AudioSource source,MouthCue[] mouthCues)
        {
            speech=source;cues=mouthCues;speaking=true;paused=false;envelope=null;
            var clip=source.clip;if(!clip)return;
            // Also supports providers without alignment. The envelope is read
            // from decoded PCM, not speaker output, so muting does not break sync.
            var samples=new float[clip.samples*clip.channels];
            if(!clip.GetData(samples,0))return;
            int block=Mathf.Max(1,clip.frequency/50);envelopeStep=(float)block/clip.frequency;
            envelope=new float[(clip.samples+block-1)/block];
            for(int i=0;i<envelope.Length;i++)
            {
                double sum=0;int start=i*block*clip.channels,end=Math.Min(samples.Length,start+block*clip.channels);
                for(int j=start;j<end;j++)sum+=samples[j]*samples[j];
                envelope[i]=Mathf.Clamp01((Mathf.Sqrt((float)(sum/Math.Max(1,end-start)))-.008f)*14);
            }
        }
        public void PauseSpeech(bool value) {paused=value;}
        public void StopSpeech() {speaking=false;paused=false;cues=null;envelope=null;speech=null;CurrentMouthCue="X";}
        public void BlinkNow() {blinkStart=Time.time;nextBlink=Time.time+UnityEngine.Random.Range(2.5f,5.0f)*EmotionLibrary.Find(body?body.Emotion:"neutral").blinkInterval;}

        void LateUpdate()
        {
            foreach(string key in Shapes)targets[key]=0;
            string emotion=body?body.Emotion:"neutral";float intensity=body?body.Intensity:0;
            var preset=EmotionLibrary.Find(emotion);
            foreach(var shape in preset.shapes)if(targets.ContainsKey(shape.name))targets[shape.name]=shape.weight*intensity;
            float redness=emotion=="crying"?.8f:emotion=="angry"?.65f:emotion=="ashamed"?.35f:emotion=="panicked"?.2f:0;
            flush=Mathf.MoveTowards(flush,redness*intensity,Time.deltaTime*.4f);
            if(faceSkin){faceSkin.GetPropertyBlock(flushBlock,0);flushBlock.SetColor("_BaseColor",Color.Lerp(Color.white,new Color(1,.76f,.70f),flush));faceSkin.SetPropertyBlock(flushBlock,0);}
            if(Tears)Tears.SetIntensity(body && body.TransientsSuppressed?0:preset.tears*intensity);
            if(emotion=="crying" && body && !body.TransientsSuppressed)
                targets["JawOpen"]=(.15f+Mathf.Pow(Mathf.Max(0,Mathf.Sin(Time.time*7f)),2)*.4f)*intensity;
            if(Time.time>=nextBlink)BlinkNow();
            float age=Time.time-blinkStart;
            float blink=age<.075f?Mathf.Clamp01(age/.075f):age<.18f?1-Mathf.Clamp01((age-.075f)/.105f):0;
            if(blinkOverride>=0)blink=blinkOverride;
            blink=Mathf.Max(blink,Mathf.Max(targets["BlinkLeft"],targets["BlinkRight"]));
            targets["BlinkLeft"]=targets["BlinkRight"]=blink;
            targets["EyeWide"]*=1-blink;
            UpdateGaze(emotion);
            UpdateMouth();
            if(jawOverride>=0)targets["JawOpen"]=jawOverride;
            if(puckerOverride>=0)targets["MouthPucker"]=puckerOverride;
            float mouth=targets["JawOpen"];
            targets["MouthSmile"]*=1-.7f*mouth;targets["MouthFrown"]*=1-.7f*mouth;
            foreach(string shape in Shapes)
            {
                float rate=shape.StartsWith("Blink")?70:shape.StartsWith("Mouth")||shape=="JawOpen"?22:5;
                weights[shape]=Mathf.Lerp(weights[shape],Mathf.Clamp01(targets[shape]),1-Mathf.Exp(-rate*Time.deltaTime));
            }
            foreach(var binding in bindings)binding.renderer.SetBlendShapeWeight(binding.index,weights[binding.name]*ShapeGain(binding.name)*100);
            ccRig?.Apply(emotion,intensity,weights,speaking,CurrentMouthCue,body && body.TransientsSuppressed);
            JawWeight=ccRig!=null?ccRig.JawWeight:weights["JawOpen"];
        }
        static float ShapeGain(string name)
        {
            switch(name)
            {
                case "MouthSmile":return 2.1f;
                case "MouthFrown":return 1.8f;
                case "BrowWorry":return 1.5f;
                case "BrowTense":return 1.5f;
                case "UpperLipRaise":return 1.3f;
                default:return 1;
            }
        }
        void UpdateMouth()
        {
            CurrentMouthCue="X";
            if(!speaking || !speech || !speech.clip || (!speech.isPlaying&&!paused))return;
            targets["JawOpen"]=targets["MouthPucker"]=targets["MouthWide"]=targets["MouthPress"]=0;
            float time=speech.time;
            float level=envelope!=null&&envelope.Length>0?envelope[Mathf.Clamp((int)(time/envelopeStep),0,envelope.Length-1)]:.5f;
            if(cues==null || cues.Length==0) {targets["JawOpen"]=level*.62f;return;}
            foreach(var cue in cues)if(time>=cue.start && time<cue.end) {CurrentMouthCue=cue.value;break;}
            switch(CurrentMouthCue)
            {
                case "A":targets["MouthPress"]=.35f;break;
                case "B":targets["JawOpen"]=.13f;targets["MouthWide"]=.4f;break;
                case "C":targets["JawOpen"]=.46f;targets["MouthWide"]=.14f;break;
                case "D":targets["JawOpen"]=.72f;break;
                case "E":targets["JawOpen"]=.38f;targets["MouthPucker"]=.42f;break;
                case "F":targets["JawOpen"]=.22f;targets["MouthPucker"]=.82f;break;
                case "G":targets["JawOpen"]=.1f;break;
                case "H":targets["JawOpen"]=.2f;break;
            }
            // Preserve closures and consonants while softening very quiet vowels.
            targets["JawOpen"]*=Mathf.Lerp(.6f,1,level);
            targets["UpperLipRaise"]*=CurrentMouthCue=="A"?.1f:.5f;
        }
        void UpdateGaze(string emotion)
        {
            if(!automaticGaze || !head || !conversationTarget || (body && body.GazeWeight<.01f))return;
            if(Time.time>=nextGaze)
            {
                nextGaze=Time.time+UnityEngine.Random.Range(2.2f,4.5f);
                float away=EmotionLibrary.Find(emotion).lookAwayChance;
                gazeOffset=gazeAversion && UnityEngine.Random.value<away?transform.right*UnityEngine.Random.Range(-.65f,.65f)+Vector3.down*.35f:Vector3.zero;
            }
            Vector3 forward=head.TransformDirection(localForward),up=head.TransformDirection(localUp);
            Vector3 direction=(conversationTarget.position+gazeOffset-(head.position+up*.10f)).normalized;
            if(Vector3.Dot(direction,transform.forward)<.25f)return;
            if(smoothedDirection==Vector3.zero)smoothedDirection=forward;
            smoothedDirection=Vector3.Slerp(smoothedDirection,direction,1-Mathf.Exp(-5*Time.deltaTime));
            direction=smoothedDirection;
            // Animation remains the base. Restrained tracking leaves room for
            // gaze aversion, head gestures and the character's emotional posture.
            Quaternion correction=Quaternion.FromToRotation(forward,direction);
            if(body && (body.useStaticSeatedPose || (body.seatedAnimation && body.seatedAnimation.isPlaying)))
                head.rotation=Quaternion.Slerp(Quaternion.identity,Quaternion.RotateTowards(Quaternion.identity,correction,25),.65f*body.GazeWeight)*head.rotation;
            forward=head.TransformDirection(localForward);up=head.TransformDirection(localUp);
            Vector3 right=Vector3.Cross(up,forward).normalized;
            float yaw=Mathf.Atan2(Vector3.Dot(direction,right),Vector3.Dot(direction,forward))*Mathf.Rad2Deg;
            EyeYaw=yaw;
            float pitch=Mathf.Asin(Mathf.Clamp(Vector3.Dot(direction,up),-1,1))*Mathf.Rad2Deg;
            targets["EyeLookLeft"]=Mathf.Clamp01(-yaw/9.7f);targets["EyeLookRight"]=Mathf.Clamp01(yaw/9.7f);
            targets["EyeLookUp"]=Mathf.Clamp01(pitch/6.9f);targets["EyeLookDown"]=Mathf.Clamp01(-pitch/6.9f);
        }
        void OnDisable()
        {
            if(Tears)Tears.SetIntensity(0);
            StopSpeech();foreach(var binding in bindings)if(binding.renderer)binding.renderer.SetBlendShapeWeight(binding.index,0);
            ccRig?.Clear();
        }
    }
}
