using System.Collections.Generic;
using UnityEngine;
namespace PsychologyVR
{
    // Actor-space hand targets use two-bone IK over a stable seated foundation.
    public class PerformanceDriver : MonoBehaviour
    {
        public Animation seatedAnimation;
        public bool useStaticSeatedPose;
        public string Emotion {get;private set;}="anxious";
        public string Gesture {get;private set;}="none";
        public float Intensity {get;private set;}=.3f;
        public bool TransientsSuppressed {get;private set;}
        public float GazeWeight {get;private set;}=1;
        public float FaceCover {get;private set;}
        public float MaxReachError {get;private set;}
        public float MaxWristBend {get;private set;}
        public float MinElbowBend {get;private set;}=180;
        public float MaxElbowBend {get;private set;}
        public float MaxHingeError {get;private set;}
        public float MaxForearmRoll {get;private set;}
        public float MaxWristTwist {get;private set;}
        public Transform LeftWrist=>left.hand;
        public Transform RightWrist=>right.hand;
        public BodyContactConstraints BodyContacts {get;private set;}
        class Pose {public Transform bone;public Quaternion rotation;public Vector3 position;}
        class Arm {public Transform shoulder,upper,lower,hand,middle;public Vector3 fingerAxis,palmAxis;public HandArticulation articulation;public ArmJointMotion joints;public Vector3 rest,velocity;
            public BodyContactConstraints.Hand contact;public Vector3 target,pole,fingers,palm;public float side,weight;}
        readonly List<Pose> poses=new List<Pose>();
        Transform head,spine,chest; Arm left,right;
        float targetIntensity=.3f,started;
        Vector3 headAngles,torsoAngles,leftTarget,rightTarget;
        bool initialized;Vector3 headUp,headForward;FacialPerformance facePerformance;float speechWeight;
        Transform Bone(string name)
        {
            var bones=GetComponentsInChildren<Transform>();
            foreach(var b in bones)if(b.name.EndsWith("mixamorig:"+name))return b;
            string mapped=name=="Head"?"Head":name=="Spine"?"Waist":name=="Spine2"?"Spine02":null;
            if(name.StartsWith("Left") || name.StartsWith("Right"))
            {
                bool left=name.StartsWith("Left");string part=name.Substring(left?4:5);
                Transform sourceLeft=null;foreach(var b in bones)if(b.name=="CC_Base_L_Upperarm")sourceLeft=b;
                bool reversed=sourceLeft && transform.InverseTransformPoint(sourceLeft.position).x>0;
                string side=(left!=reversed)?"L_":"R_";
                if(part=="Arm")part="Upperarm";else if(part=="ForeArm")part="Forearm";else if(part=="Shoulder")part="Clavicle";
                else if(part=="UpLeg")part="Thigh";else if(part=="Leg")part="Calf";
                else if(part.StartsWith("Hand") && part.Length>4)part=part.Substring(4).Replace("Middle","Mid");
                mapped=side+part;
            }
            foreach(var b in bones)if(b.name=="CC_Base_"+mapped)return b;return null;
        }
        Arm FindArm(string s)=>new Arm{shoulder=Bone(s+"Shoulder"),upper=Bone(s+"Arm"),lower=Bone(s+"ForeArm"),hand=Bone(s+"Hand"),middle=Bone(s+"HandMiddle1")};
        void Awake(){head=Bone("Head");spine=Bone("Spine");chest=Bone("Spine2");left=FindArm("Left");right=FindArm("Right");}
        public void Apply(string emotion,float intensity,string gesture,bool immediate=false)
        {
            string next=EmotionLibrary.Find(emotion).name;
            if(next!=Emotion || gesture!=Gesture)started=Time.time;
            Emotion=next;Gesture=gesture;targetIntensity=Mathf.Clamp01(intensity);
            TransientsSuppressed=false;if(immediate)Intensity=targetIntensity;
        }
        public void StopGesture(bool interrupt=false){Gesture="none";if(interrupt)TransientsSuppressed=true;}
        void Restore(){foreach(var p in poses){p.bone.localRotation=p.rotation;p.bone.localPosition=p.position;}}
        void Update(){if(initialized)Restore();}
        Vector3 Local(Vector3 p)=>transform.InverseTransformPoint(p);
        void Rotate(Transform b,Vector3 angles){if(b)b.rotation=transform.rotation*Quaternion.Euler(angles)*Quaternion.Inverse(transform.rotation)*b.rotation;}
        void LateUpdate()
        {
            if(!head || !left.hand || !right.hand)return;
            if(!initialized)
            {
                if(!useStaticSeatedPose && (!seatedAnimation || !seatedAnimation.isPlaying))return;
                foreach(var b in GetComponentsInChildren<Transform>())if(b.name.Contains("mixamorig:") || b.name.StartsWith("CC_Base_"))poses.Add(new Pose{bone=b,rotation=b.localRotation,position=b.localPosition});
                BodyContacts=gameObject.AddComponent<BodyContactConstraints>();
                BodyContacts.Initialize(this,Bone("LeftUpLeg"),Bone("LeftLeg"),Bone("RightUpLeg"),Bone("RightLeg"),spine,chest,head);
                foreach(var a in new[]{left,right})
                {
                    a.fingerAxis=a.hand.InverseTransformDirection((a.middle.position-a.hand.position).normalized);
                    string side=a==left?"Left":"Right";
                    Vector3 normal=Vector3.Cross(Bone(side+"HandIndex1").position-a.hand.position,Bone(side+"HandPinky1").position-a.hand.position).normalized;
                    if(Vector3.Dot(normal,transform.up)>0)normal=-normal;
                    a.palmAxis=a.hand.InverseTransformDirection(normal);
                    a.joints=new ArmJointMotion(a.upper,a.lower,a.hand,a.fingerAxis,a.palmAxis,a==left?-1:1);
                    var digits=new Transform[4][];string[] digitNames={"Index","Middle","Ring","Pinky"};
                    for(int f=0;f<4;f++)
                    {digits[f]=new Transform[3];for(int j=0;j<3;j++)digits[f][j]=Bone(side+"Hand"+digitNames[f]+(j+1));}
                    var thumbs=new Transform[3];for(int j=0;j<3;j++)thumbs[j]=Bone(side+"HandThumb"+(j+1));
                    a.articulation=new HandArticulation(digits,thumbs,normal,a==left?0:2.7f);
                    a.contact=BodyContacts.Register(a.hand,digits,thumbs,a.articulation,target=>SolveContact(a,target));
                }
                headUp=head.InverseTransformDirection(transform.up);headForward=head.InverseTransformDirection(transform.forward);
                leftTarget=Local(left.hand.position);rightTarget=Local(right.hand.position);
                // Support the wrists over the thighs in the actor frame, independently
                // of breathing/leaning in the upper body. Keep a small left/right offset.
                left.rest=SupportedWrist("Left",leftTarget,.64f);
                right.rest=SupportedWrist("Right",rightTarget,.55f);
                facePerformance=GetComponent<FacialPerformance>();
                initialized=true;
                Debug.Log("PERFORMANCE_BASE head="+Local(head.position)+" left="+leftTarget+" right="+rightTarget);
            }
            Restore();
            Intensity=Mathf.MoveTowards(Intensity,targetIntensity,Time.deltaTime*.9f);
            float t=Time.time-started,k=Intensity;
            float poseRate=Emotion=="despondent"?1.35f:Emotion=="sad"?2.5f:5;
            float dt=1-Mathf.Exp(-poseRate*Time.deltaTime);
            var p=EmotionLibrary.Find(Emotion);
            Vector3 h=new Vector3(p.headPitch*1.5f,p.headYaw*1.7f,0)*k,torso=new Vector3(p.torsoPitch*2,0,0)*k;
            Vector3 l=left.rest,r=right.rest;
            float motion=TransientsSuppressed?0:1,sob=Mathf.Pow(Mathf.Max(0,Mathf.Sin(t*7)),3)*motion;
            float cover=0,arms=1;bool upright=false;GazeWeight=.75f;
            switch(Emotion)
            {
                case "crying":
                    cover=Mathf.SmoothStep(0,1,(k-.55f)/.3f)*Mathf.SmoothStep(0,1,(t-1.5f)/1.1f);
                    cover*=1-.85f*Mathf.SmoothStep(0,1,(t%9-6.5f)/1.2f);
                    torso.x=(14+sob*4)*k;h.x=(19+cover*15+sob*3)*k;GazeWeight=0;arms=1;upright=true;break;
                case "angry":
                    // A forceful beat followed by a tense hold, rather than continuous waving.
                    float attack=AngerBeat(t)*motion;
                    torso=new Vector3(17+attack*4,-attack*4,0)*k;
                    h=new Vector3(-10,attack*3,0)*k;
                    l=left.rest+new Vector3(0,.012f,.015f);
                    r=Vector3.Lerp(right.rest,new Vector3(.24f,1.01f,.43f),attack);
                    arms=k;upright=true;GazeWeight=0;break;
                case "afraid":
                    torso.x=-9*k;h=new Vector3(-8,0,0)*k;l=new Vector3(-.12f,1.03f,.23f);r=new Vector3(.12f,1.03f,.23f);arms=k;upright=true;GazeWeight=0;break;
                case "panicked":
                    torso.x=(-7+Mathf.Sin(t*10)*2*motion)*k;h=new Vector3(-9,Mathf.Sin(t*4)*7*motion,0)*k;
                    l=new Vector3(-.23f,1.18f+sob*.025f,.25f);r=new Vector3(.23f,1.18f+sob*.025f,.25f);arms=k;upright=true;GazeWeight=0;break;
                case "disgusted":
                    torso=new Vector3(-10,-9,0)*k;h=new Vector3(8,27,-8)*k;r=new Vector3(.27f,1.12f,.38f);arms=k;upright=true;GazeWeight=0;break;
                case "frustrated":
                    float shake=t%5<1.8f?Mathf.Sin(t*7)*7*motion:0;
                    torso.x=-3*k;h=new Vector3(-3,shake,-4)*k;
                    l=Vector3.Lerp(left.rest,new Vector3(-.29f,.89f,.38f),Stroke(t-.35f,5.7f));
                    r=Vector3.Lerp(right.rest,new Vector3(.31f,.96f,.41f),Stroke(t,5.7f));arms=k;GazeWeight=0;break;
                case "happy":
                    torso.x=-5*k;h=new Vector3(-5,Mathf.Sin(t*1.6f)*3,3)*k;
                    l=Vector3.Lerp(left.rest,new Vector3(-.28f,.82f,.35f),Stroke(t-.7f,7.1f)*.55f);
                    r=Vector3.Lerp(right.rest,new Vector3(.29f,.88f,.40f),Stroke(t,7.1f));arms=k;break;
                case "surprised":
                    float startle=1-Mathf.SmoothStep(0,1,(t-1.2f)/2.5f);
                    torso.x=-11*k*startle;h.x=-13*k*startle;
                    l=new Vector3(-.25f,1,.36f);r=new Vector3(.25f,1,.36f);arms=k*startle;upright=true;GazeWeight=0;break;
                case "ashamed":h=new Vector3(32,22,6)*k;torso.x=13*k;GazeWeight=0;break;
                case "despondent":
                    h=new Vector3(33,0,7)*k;torso=new Vector3(27,0,-3)*k;
                    l=left.rest+new Vector3(.012f,.005f,.025f);r=right.rest+new Vector3(-.012f,.005f,.018f);arms=k;GazeWeight=0;break;
                case "sad":h=new Vector3(15,-7,0)*k;torso.x=6*k;GazeWeight=0;break;
                case "numb":h=new Vector3(0,0,0)*k;torso.x=0;GazeWeight=0;break;
                case "confused":h=new Vector3(0,-9,-15)*k;r=Vector3.Lerp(right.rest,new Vector3(.27f,.91f,.40f),Stroke(t,6.3f));arms=k;GazeWeight=.2f;break;
                case "skeptical":h=new Vector3(-5,18,10)*k;GazeWeight=.15f;break;
                case "guilty":h=new Vector3(20,-17,0)*k;torso.x=8*k;GazeWeight=0;break;
                case "anxious":
                    float fidget=Stroke(t,6.7f)*k*motion;
                    l+=new Vector3(.012f,.004f,-.013f)*fidget;
                    r+=new Vector3(-.006f,.003f,.009f)*Stroke(t-1.6f,8.1f)*k*motion;break;
            }
            bool still=Emotion=="numb"||Emotion=="afraid";
            if(!still)
            {
                float breath=Mathf.Sin(Time.time*(Emotion=="despondent"?.65f:1.35f));
                torso.x+=breath*(Emotion=="despondent"?.18f:.45f);
                torso.y+=Mathf.Sin(Time.time*.43f)*.35f;
                torso.z+=Mathf.Sin(Time.time*.61f+.8f)*.22f;
            }
            // Small speech beats only while audio is actually playing; listening
            // retains supported hands. Strong emotional actions keep precedence.
            speechWeight=Mathf.MoveTowards(speechWeight,facePerformance&&facePerformance.IsSpeaking&&!TransientsSuppressed?1:0,Time.deltaTime*2);
            if(Emotion=="neutral"||Emotion=="calm"||Emotion=="anxious"||Emotion=="hopeful")
            {
                float beat=Stroke(t+.4f,5.9f)*speechWeight;
                r=Vector3.Lerp(r,right.rest+new Vector3(.045f,.11f,.09f),beat);
                torso.y-=beat*1.2f;h.x+=beat*1.4f;
            }
            float envelope=Mathf.Sin(Mathf.Clamp01(t/3)*Mathf.PI);
            if(Gesture=="nod")h.x+=Mathf.Sin(t*6)*envelope*13;
            if(Gesture=="look_down")h.x+=envelope*18;
            if(Gesture=="glance_away")h.y+=envelope*30;
            if(Gesture=="wince")torso.x+=envelope*8;
            if(Gesture=="hand_fidget"){l+=new Vector3(.013f,.006f,-.01f)*envelope;r.z+=Mathf.Sin(t*3)*envelope*.007f;arms=1;}
            headAngles=Vector3.Lerp(headAngles,h,dt);torsoAngles=Vector3.Lerp(torsoAngles,torso,dt);
            Rotate(spine,torsoAngles*.55f);Rotate(chest,torsoAngles*.45f);Rotate(head,headAngles);
            FaceCover=Mathf.Lerp(FaceCover,cover,dt);
            if(Emotion=="crying")
            {
                Vector3 face=Local(head.position+head.TransformDirection(headUp)*-.035f+head.TransformDirection(headForward)*.145f);
                l=Vector3.Lerp(new Vector3(-.18f,.80f,.32f),face+new Vector3(-.060f,0,0),FaceCover);
                r=Vector3.Lerp(new Vector3(.18f,.80f,.32f),face+new Vector3(.060f,0,0),FaceCover);
            }
            if(Gesture=="wipe_tear" && t<3){r=Vector3.Lerp(r,Local(head.position)+new Vector3(.065f,.04f,.15f),envelope);arms=1;upright=true;}
            l=Vector3.Lerp(left.rest,l,arms);r=Vector3.Lerp(right.rest,r,arms);
            // A brief fidget lifts a resting palm so the fingers can actually curl
            // above the lap. This uses the previous frame's anticipated action.
            l.y=Mathf.Max(l.y,left.rest.y+left.articulation.LiftClearance);
            r.y=Mathf.Max(r.y,right.rest.y+right.articulation.LiftClearance);
            float smooth=Emotion=="despondent"?.65f:Emotion=="angry"?.20f:.32f;
            // Critically damped targets preserve velocity through retargeting and
            // decelerate into hand contact instead of stopping on a pose boundary.
            leftTarget=Vector3.SmoothDamp(leftTarget,l,ref left.velocity,smooth*1.12f,1.4f,Time.deltaTime);
            rightTarget=Vector3.SmoothDamp(rightTarget,r,ref right.velocity,smooth,1.4f,Time.deltaTime);
            ShoulderFollow(left,leftTarget,-1);ShoulderFollow(right,rightTarget,1);
            Solve(left,transform.TransformPoint(leftTarget),-1,upright);
            Solve(right,transform.TransformPoint(rightTarget),1,upright);
        }
        public static float AngerBeat(float time)
        {
            // Let the hand close before the first emphatic arm beat.
            if(time<.55f)return 0;
            float phase=Mathf.Repeat(time-.55f,4.8f);
            if(phase<.55f)return Mathf.SmoothStep(0,1,phase/.55f);
            if(phase<.95f)return 1;
            if(phase<1.45f)return 1-Mathf.SmoothStep(0,1,(phase-.95f)/.5f);
            return 0;
        }
        static float Stroke(float time,float period)
        {
            if(time<0)return 0;
            float phase=Mathf.Repeat(time,period);
            if(phase<.9f)return Mathf.SmoothStep(0,1,phase/.9f);
            if(phase<1.35f)return 1;
            if(phase<2.8f)return 1-Mathf.SmoothStep(0,1,(phase-1.35f)/1.45f);
            return 0;
        }
        Vector3 SupportedWrist(string side,Vector3 fallback,float alongThigh)
        {
            var thigh=Bone(side+"UpLeg");var knee=Bone(side+"Leg");
            if(!thigh||!knee)return fallback;
            Vector3 support=Vector3.Lerp(Local(thigh.position),Local(knee.position),alongThigh);
            // Thigh centre to trouser surface, then allow for palm thickness.
            // The wrist sits behind the supported palm, with fingers toward the knee.
            support+=new Vector3(0,.115f,-.055f);
            Debug.Log("HAND_SUPPORT "+side+" thigh="+Local(thigh.position)+" knee="+Local(knee.position)+" wrist="+support);
            return support;
        }
        void ShoulderFollow(Arm arm,Vector3 target,float side)
        {
            float lift=Mathf.Clamp01((target.y-arm.rest.y)/.45f);
            float reach=Mathf.Clamp((target.z-arm.rest.z)/.3f,-.3f,1);
            Rotate(arm.shoulder,new Vector3(lift*2,-side*reach*6,-side*lift*8));
        }
        void Solve(Arm a,Vector3 target,float side,bool upright)
        {
            float raised=Mathf.Clamp01((Local(target).y-a.rest.y)/.45f);
            Vector3 pole=transform.right*side*Mathf.Lerp(.32f,.58f,raised)-transform.up*.95f+transform.forward*.12f;
            if(Emotion=="crying")pole=Vector3.Lerp(pole,transform.right*side*.12f-transform.up+transform.forward*.35f,FaceCover);
            Vector3 fingers=Emotion=="crying"?Vector3.Slerp(transform.up,head.TransformDirection(headUp),FaceCover):transform.up;
            Vector3 palm=Emotion=="crying"?-head.TransformDirection(headForward):Emotion=="angry"?-transform.forward:transform.forward;
            if(Emotion=="disgusted" && side<0)upright=false;
            if(Emotion=="frustrated" || Emotion=="confused"){fingers=transform.forward;palm=transform.up;upright=true;}
            if(Emotion=="despondent")upright=false;
            if(Emotion=="angry"){fingers=Vector3.Lerp(transform.forward,transform.up,AngerBeat(Time.time-started)*.55f);palm=-transform.up;}
            a.joints.Solve(target,pole,transform.forward+transform.right*side*.08f,-transform.up,fingers,palm,upright?Mathf.SmoothStep(0,1,raised*2):0,Time.deltaTime);
            a.target=target;a.pole=pole;a.fingers=fingers;a.palm=palm;a.side=side;a.weight=upright?Mathf.SmoothStep(0,1,raised*2):0;
            Measure(a,target);
            float fingerActivity=TransientsSuppressed?0:Gesture=="hand_fidget"?1:Emotion=="anxious"?Intensity:Emotion=="neutral"||Emotion=="calm"?speechWeight*.4f:0;
            a.articulation.Apply(Emotion,Intensity,FaceCover,Time.deltaTime,fingerActivity,raised,TransientsSuppressed);
        }
        void Measure(Arm a,Vector3 target)
        {
            MaxWristBend=Mathf.Max(MaxWristBend,a.joints.WristBend);
            MinElbowBend=Mathf.Min(MinElbowBend,a.joints.ElbowBend);
            MaxElbowBend=Mathf.Max(MaxElbowBend,a.joints.ElbowBend);
            MaxHingeError=Mathf.Max(MaxHingeError,a.joints.HingeError);
            MaxForearmRoll=Mathf.Max(MaxForearmRoll,Mathf.Abs(a.joints.ForearmRoll));
            MaxWristTwist=Mathf.Max(MaxWristTwist,a.joints.WristTwist);
            MaxReachError=Mathf.Max(MaxReachError,Vector3.Distance(a.hand.position,target));
        }
        void SolveContact(Arm a,Vector3 target)
        {
            a.joints.Solve(target,a.pole,transform.forward+transform.right*a.side*.08f,-transform.up,
                a.fingers,a.palm,a.weight,0);
        }
        public void ResolveBodyContacts()
        {
            if(!initialized)return;
            BodyContacts.Resolve(left.contact,left.target,Time.deltaTime);
            BodyContacts.Resolve(right.contact,right.target,Time.deltaTime);
            BodyContacts.SeparateHands(left.contact,left.target,right.contact,right.target);
            // Record final geometry as well as the uncorrected animation geometry.
            Measure(left,left.contact.target);Measure(right,right.contact.target);
        }
    }
}
