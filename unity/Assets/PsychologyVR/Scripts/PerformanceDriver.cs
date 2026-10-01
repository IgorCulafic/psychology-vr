using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Animations.Rigging;
using UnityEngine.Playables;
using Unity.Profiling;
namespace PsychologyVR
{
    // Actor-space hand targets use two-bone IK over a stable seated foundation.
    public class PerformanceDriver : MonoBehaviour
    {
        public Animation seatedAnimation;
        public bool useStaticSeatedPose;
        internal bool proceduralSeat;
        internal string SeatPhaseName=>seatPhase.ToString();
        internal Vector3 SeatOffsetLocal=>seatOffsetLocal;
        internal bool SeatSupportReady=>seatSupportReady;
        public string Emotion {get;private set;}="anxious";
        public string Gesture {get;private set;}="none";
        public float Intensity {get;private set;}=.3f;
        public bool TransientsSuppressed {get;private set;}
        public float GazeWeight {get;private set;}=1;
        public float TransitionSeconds {get;private set;}=.65f;
        string directedGaze="automatic";float gestureStarted,gestureDuration=2.5f;
        string lastDirectedGesture="none";float lastDirectedGestureAt=-100;
        bool performancePaused;float pausedAt;
        internal bool PerformancePaused=>performancePaused;
        internal float EmotionAge=>(performancePaused?pausedAt:Time.time)-started;
        internal float EmotionMotion {get;private set;}
        float nextMotion=.55f,motionStarted=-100,motionDuration=1,motionStrength=1;
        float nextCryRelease=12,cryReleaseStarted=-100,cryReleaseDuration=3;
        public void PausePerformance(bool value)
        {
            if(value==performancePaused)return;
            if(value)pausedAt=Time.time;
            else {float delay=Time.time-pausedAt;started+=delay;gestureStarted+=delay;}
            performancePaused=value;
        }
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
        class Arm {public Transform shoulder,upper,lower,hand,middle,ikTarget,ikHint;public Vector3 fingerAxis,palmAxis;public HandArticulation articulation;public ArmJointMotion joints;public TwoBoneIKConstraint ik;public float upperLength,lowerLength;public Vector3 rest,velocity;
            public BodyContactConstraints.Hand contact;public Vector3 target,pole,fingers,palm;public float side,weight;
            public Quaternion recordedElbow=Quaternion.identity,recordedHand=Quaternion.identity;public Vector3 palmContact;public float mocapWeight;}
        class Leg {public Transform thigh,knee,foot,ikTarget,ikHint,palmAnchor;public TwoBoneIKConstraint ik;}
        enum SeatPhase { Idle, Drift, Brace, Load, Lift, Return, Lower, Release, Cancel }
        readonly List<Pose> poses=new List<Pose>();
        Transform head,spine,chest,hip; Arm left,right;Leg leftLeg,rightLeg;RigBuilder rigBuilder;Avatar runtimeAvatar;
        float targetIntensity=.3f,started;
        Vector3 headAngles,torsoAngles,leftTarget,rightTarget;
        bool initialized;Vector3 headUp,headForward;FacialPerformance facePerformance;float speechWeight;
        bool seatEnabled,seatSupportReady;SeatPhase seatPhase;SeatedMocapOverlay seatedMocap;UpperBodyMocap upperBodyMocap;
        float seatPhaseTime,relaxedSeconds,nextSeatCycle=60,seatForward,seatHeight,seatBraceWeight,seatLean;
        float seatCancelForward,seatCancelBrace,seatCancelLean;
        Vector3 seatOffsetLocal,mocapOffsetLocal;
        static readonly ProfilerMarker RigEvaluateMarker=new ProfilerMarker("Seat.RigEvaluate");
        void OnDestroy(){seatedMocap?.Dispose();upperBodyMocap?.Dispose();if(runtimeAvatar)Destroy(runtimeAvatar);}
        Transform Bone(string name)
        {
            var bones=GetComponentsInChildren<Transform>();
            foreach(var b in bones)if(b.name.EndsWith("mixamorig:"+name))return b;
            string mapped=name=="Head"?"Head":name=="Spine"?"Waist":name=="Spine2"?"Spine02":name=="Hips"?"Hip":null;
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
        Leg FindLeg(string s)=>new Leg{thigh=Bone(s+"UpLeg"),knee=Bone(s+"Leg"),foot=Bone(s+"Foot")};
        void Awake(){head=Bone("Head");spine=Bone("Spine");chest=Bone("Spine2");hip=Bone("Hips");left=FindArm("Left");right=FindArm("Right");leftLeg=FindLeg("Left");rightLeg=FindLeg("Right");}
        public void Apply(string emotion,float intensity,string gesture,bool immediate=false)
        {
            string next=EmotionLibrary.Find(emotion).name;
            // Sentence boundaries and one-shot cues must not restart emotional loops.
            if(next!=Emotion)
            {
                started=Time.time;nextMotion=Random.Range(.6f,1.5f);motionStarted=-100;
                nextCryRelease=Random.Range(10f,17f);cryReleaseStarted=-100;EmotionMotion=0;
            }
            Emotion=next;Gesture=gesture;targetIntensity=Mathf.Clamp01(intensity);
            gestureStarted=Time.time;gestureDuration=2.5f;directedGaze="automatic";TransitionSeconds=.65f;
            TransientsSuppressed=false;if(immediate)Intensity=targetIntensity;
        }
        public void BeginBeat(SpeechSegment segment)
        {
            Apply(segment.emotion,segment.intensity,"none");
            directedGaze=segment.gaze??"automatic";
            TransitionSeconds=Mathf.Clamp(segment.transition_seconds>0?segment.transition_seconds:.65f,.15f,2);
        }
        public void TriggerGesture(string gesture,float duration)
        {
            if(string.IsNullOrEmpty(gesture)||gesture=="none")return;
            float gap=Time.time-lastDirectedGestureAt;
            if(gap<3 || (gesture==lastDirectedGesture && gap<10))return;
            if((Emotion=="crying"||Emotion=="panicked"||Emotion=="numb") && Intensity>.65f)return;
            Gesture=gesture;lastDirectedGesture=gesture;lastDirectedGestureAt=gestureStarted=Time.time;
            gestureDuration=Mathf.Clamp(duration>0?duration:2.5f,.3f,4);
        }
        public void StopGesture(bool interrupt=false){Gesture="none";if(interrupt){TransientsSuppressed=true;directedGaze="automatic";}}
        void Restore(){foreach(var p in poses){p.bone.localRotation=p.rotation;p.bone.localPosition=p.position;}}
        void Update(){if(initialized && !performancePaused && !useStaticSeatedPose)Restore();}
        Vector3 Local(Vector3 p)=>transform.InverseTransformPoint(p);
        void Rotate(Transform b,Vector3 angles){if(b)b.rotation=transform.rotation*Quaternion.Euler(angles)*Quaternion.Inverse(transform.rotation)*b.rotation;}
        void LateUpdate()
        {
            if(performancePaused)return;
            if(!head || !left.hand || !right.hand)return;
            if(!initialized)
            {
                if(!useStaticSeatedPose && (!seatedAnimation || !seatedAnimation.isPlaying))return;
                foreach(var b in GetComponentsInChildren<Transform>())if(b.name.Contains("mixamorig:") || b.name.StartsWith("CC_Base_"))poses.Add(new Pose{bone=b,rotation=b.localRotation,position=b.localPosition});
                InitializeArmRig();
                seatEnabled=proceduralSeat && hip && leftLeg.ik && rightLeg.ik && rigBuilder;
                if(proceduralSeat && !seatEnabled)Debug.LogError("Procedural seat needs a pelvis and two Animation Rigging leg constraints on "+name,this);
                if(seatEnabled){seatedMocap=new SeatedMocapOverlay(transform);upperBodyMocap=new UpperBodyMocap(transform,left.hand,right.hand);}
                BodyContacts=gameObject.AddComponent<BodyContactConstraints>();
                BodyContacts.Initialize(this,Bone("LeftUpLeg"),Bone("LeftLeg"),Bone("RightUpLeg"),Bone("RightLeg"),spine,chest,head);
                foreach(var a in new[]{left,right})
                {
                    a.fingerAxis=a.hand.InverseTransformDirection((a.middle.position-a.hand.position).normalized);
                    a.upperLength=Vector3.Distance(a.upper.position,a.lower.position);a.lowerLength=Vector3.Distance(a.lower.position,a.hand.position);
                    string side=a==left?"Left":"Right";
                    Vector3 normal=Vector3.Cross(Bone(side+"HandIndex1").position-a.hand.position,Bone(side+"HandPinky1").position-a.hand.position).normalized;
                    if(Vector3.Dot(normal,transform.up)>0)normal=-normal;
                    a.palmAxis=a.hand.InverseTransformDirection(normal);
                    a.palmContact=a.hand.InverseTransformPoint(Vector3.Lerp(a.hand.position,
                        (Bone(side+"HandIndex1").position+Bone(side+"HandPinky1").position)*.5f,.6f));
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
                left.rest=SupportedWrist(leftLeg,leftTarget,.64f);
                right.rest=SupportedWrist(rightLeg,rightTarget,.55f);
                facePerformance=GetComponent<FacialPerformance>();
                if(facePerformance && facePerformance.HasFaceSupports)
                    BodyContacts.FitHeadToFace(facePerformance.FaceSupport(-1),facePerformance.FaceSupport(1));
                initialized=true;
                Debug.Log("PERFORMANCE_BASE head="+Local(head.position)+" left="+leftTarget+" right="+rightTarget);
            }
            Restore();
            Intensity=Mathf.MoveTowards(Intensity,targetIntensity,Time.deltaTime/TransitionSeconds);
            mocapOffsetLocal=seatedMocap!=null?seatedMocap.Tick(Time.deltaTime,
                seatPhase==SeatPhase.Idle):Vector3.zero;
            UpdateSeat(Time.deltaTime);
            upperBodyMocap?.Tick(Time.deltaTime,Emotion,Intensity,facePerformance&&facePerformance.IsSpeaking,
                TransientsSuppressed,seatBraceWeight,left.rest,right.rest);
            if(seatEnabled)
            {
                left.rest=SupportedWrist(leftLeg,leftTarget,.64f);
                right.rest=SupportedWrist(rightLeg,rightTarget,.55f);
            }
            float t=EmotionAge,k=Intensity;
            UpdateEmotionMotion(t);
            float poseRate=Emotion=="despondent"?1.35f:Emotion=="sad"?2.5f:5;
            float dt=1-Mathf.Exp(-Mathf.Min(poseRate,3/TransitionSeconds)*Time.deltaTime);
            var p=EmotionLibrary.Find(Emotion);
            Vector3 h=new Vector3(p.headPitch*1.5f,p.headYaw*1.7f,0)*k,torso=new Vector3(p.torsoPitch*2,0,0)*k;
            Vector3 l=left.rest,r=right.rest;
            float motion=TransientsSuppressed?0:1,sob=EmotionMotion*motion;
            float cover=0,arms=1;bool upright=false;GazeWeight=.75f;
            switch(Emotion)
            {
                case "crying":
                    cover=Mathf.SmoothStep(0,1,(k-.55f)/.25f)*Mathf.SmoothStep(0,1,(t-1.5f)/1.1f);
                    if(t>=nextCryRelease)
                    {cryReleaseStarted=t;cryReleaseDuration=Random.Range(2.8f,4.5f);nextCryRelease=t+cryReleaseDuration+Random.Range(10f,17f);}
                    float releaseAge=(t-cryReleaseStarted)/cryReleaseDuration;
                    float release=releaseAge<1?Mathf.Sin(Mathf.PI*Mathf.Clamp01(releaseAge)):0;
                    cover*=1-.85f*release*release;
                    torso.x=(14+sob*4)*k;h.x=(19+cover*15+sob*3)*k;GazeWeight=0;arms=1;upright=true;break;
                case "angry":
                    // A forceful beat followed by a tense hold, rather than continuous waving.
                    float attack=EmotionMotion*motion;
                    torso=new Vector3(17+attack*4,-attack*4,0)*k;
                    h=new Vector3(-10,attack*3,0)*k;
                    l=left.rest+new Vector3(0,.012f,.015f);
                    r=Vector3.Lerp(right.rest,new Vector3(.24f,1.01f,.43f),attack);
                    arms=k;upright=true;GazeWeight=0;break;
                case "afraid":
                    float guard=1-Mathf.SmoothStep(0,1,t/5);
                    torso.x=-9*k;h=new Vector3(-8,0,0)*k;
                    l=Vector3.Lerp(left.rest,new Vector3(-.12f,1.03f,.23f),.35f+.65f*guard);
                    r=Vector3.Lerp(right.rest,new Vector3(.18f,.99f,.27f),.55f+.45f*guard);arms=k;upright=true;GazeWeight=0;break;
                case "panicked":
                    torso.x=(-7+sob*2)*k;h=new Vector3(-9,(Mathf.PerlinNoise(t*.7f,3.8f)-.5f)*10*motion,0)*k;
                    float panicGuard=.6f+.4f*(1-Mathf.SmoothStep(0,1,t/4));
                    l=Vector3.Lerp(left.rest,new Vector3(-.23f,1.18f+sob*.025f,.25f),panicGuard);
                    r=Vector3.Lerp(right.rest,new Vector3(.20f,1.12f+sob*.018f,.28f),panicGuard);arms=k;upright=true;GazeWeight=0;break;
                case "disgusted":
                    torso=new Vector3(-10,-9,0)*k;h=new Vector3(8,27,-8)*k;r=new Vector3(.27f,1.12f,.38f);arms=k;upright=true;GazeWeight=0;break;
                case "frustrated":
                    float shake=(Mathf.PerlinNoise(t*1.1f,7.2f)-.5f)*12*EmotionMotion*motion;
                    torso.x=-3*k;h=new Vector3(-3,shake,-4)*k;
                    if(!seatEnabled){l=Vector3.Lerp(left.rest,new Vector3(-.29f,.89f,.38f),Stroke(t-.35f,5.7f));
                        r=Vector3.Lerp(right.rest,new Vector3(.31f,.96f,.41f),Stroke(t,5.7f));}arms=k;GazeWeight=0;break;
                case "happy":
                    torso.x=-5*k;h=new Vector3(-5,Mathf.Sin(t*1.6f)*3,3)*k;
                    if(!seatEnabled){l=Vector3.Lerp(left.rest,new Vector3(-.28f,.82f,.35f),Stroke(t-.7f,7.1f)*.55f);
                        r=Vector3.Lerp(right.rest,new Vector3(.29f,.88f,.40f),Stroke(t,7.1f));}arms=k;break;
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
                case "confused":h=new Vector3(0,-9,-15)*k;if(!seatEnabled)r=Vector3.Lerp(right.rest,new Vector3(.27f,.91f,.40f),Stroke(t,6.3f));arms=k;GazeWeight=.2f;break;
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
            torso.x=torso.x*(1-seatBraceWeight)+seatLean;
            // Small speech beats only while audio is actually playing; listening
            // retains supported hands. Strong emotional actions keep precedence.
            speechWeight=Mathf.MoveTowards(speechWeight,facePerformance&&facePerformance.IsSpeaking&&!TransientsSuppressed?1:0,Time.deltaTime*2);
            if(Emotion=="neutral"||Emotion=="calm"||Emotion=="anxious"||Emotion=="hopeful")
            {
                float beat=Stroke(t+.4f,5.9f)*speechWeight;
                if(!seatEnabled)r=Vector3.Lerp(r,right.rest+new Vector3(.045f,.11f,.09f),beat);
                torso.y-=beat*1.2f;h.x+=beat*1.4f;
            }
            float gestureTime=Time.time-gestureStarted;
            if(gestureTime>=gestureDuration)Gesture="none";
            float envelope=Mathf.Sin(Mathf.Clamp01(gestureTime/gestureDuration)*Mathf.PI);
            if(directedGaze=="down"){h.x=Mathf.Max(h.x,18);GazeWeight=0;}
            else if(directedGaze=="away"){h.y+=22;GazeWeight=0;}
            else if(directedGaze=="listener" && cover<.2f && Emotion!="crying" && Emotion!="panicked")GazeWeight=1;
            if(Gesture=="nod")h.x+=Mathf.Sin(gestureTime*6)*envelope*13;
            if(Gesture=="look_down")h.x+=envelope*18;
            if(Gesture=="glance_away")h.y+=envelope*30;
            if(Gesture=="wince")torso.x+=envelope*8;
            if(Gesture=="hand_fidget"){l+=new Vector3(.013f,.006f,-.01f)*envelope;r.z+=Mathf.Sin(gestureTime*3)*envelope*.007f;arms=1;}
            headAngles=Vector3.Lerp(headAngles,h,dt);torsoAngles=Vector3.Lerp(torsoAngles,torso,dt);
            Rotate(spine,torsoAngles*.55f);Rotate(chest,torsoAngles*.45f);Rotate(head,headAngles);
            seatedMocap?.Apply(spine,chest,head);
            upperBodyMocap?.ApplyTorso();
            if(upperBodyMocap!=null)GazeWeight*=1-upperBodyMocap.Weight;
            FaceCover=Mathf.Lerp(FaceCover,cover,dt);
            if(Emotion=="crying")
            {
                l=Vector3.Lerp(left.rest,FaceSupportWrist(left,-1),FaceCover);
                r=Vector3.Lerp(right.rest,FaceSupportWrist(right,1),FaceCover);
            }
            if(Gesture=="wipe_tear"){r=Vector3.Lerp(r,Local(head.position)+new Vector3(.065f,.04f,.15f),envelope);arms=1;upright=true;}
            l=Vector3.Lerp(left.rest,l,arms);r=Vector3.Lerp(right.rest,r,arms);
            if(seatedMocap!=null)
            {
                Vector3 up=(chest.position-spine.position).normalized,across=(right.upper.position-left.upper.position).normalized;
                var bodyFrame=Quaternion.LookRotation(Vector3.Cross(across,up),up);
                ShapeRecordedArm(left,true,bodyFrame,ref l);
                ShapeRecordedArm(right,false,bodyFrame,ref r);
            }
            // A reseat keeps both hands on their supports even if the emotion changes.
            if(seatBraceWeight>0)
            {
                l=Vector3.Lerp(l,KneeSupportWrist(leftLeg,left.rest),seatBraceWeight);
                r=Vector3.Lerp(r,KneeSupportWrist(rightLeg,right.rest),seatBraceWeight);
            }
            // A brief fidget lifts a resting palm so the fingers can actually curl
            // above the lap. This uses the previous frame's anticipated action.
            l.y=Mathf.Max(l.y,left.rest.y+left.articulation.LiftClearance*(1-seatBraceWeight));
            r.y=Mathf.Max(r.y,right.rest.y+right.articulation.LiftClearance*(1-seatBraceWeight));
            float smooth=seatBraceWeight>0?.10f:Emotion=="despondent"?.65f:Emotion=="angry"?.20f:.32f;
            // Critically damped targets preserve velocity through retargeting and
            // decelerate into hand contact instead of stopping on a pose boundary.
            leftTarget=Vector3.SmoothDamp(leftTarget,l,ref left.velocity,smooth*1.12f,1.4f,Time.deltaTime);
            rightTarget=Vector3.SmoothDamp(rightTarget,r,ref right.velocity,smooth,1.4f,Time.deltaTime);
            ShoulderFollow(left,leftTarget,-1);ShoulderFollow(right,rightTarget,1);
            if(upperBodyMocap==null || upperBodyMocap.Weight<1 || seatBraceWeight>0)
            {
                Solve(left,transform.TransformPoint(leftTarget),-1,upright);
                Solve(right,transform.TransformPoint(rightTarget),1,upright);
            }
            upperBodyMocap?.ApplyArms(1-seatBraceWeight);
            CaptureMocapArm(left);CaptureMocapArm(right);
        }
        void CaptureMocapArm(Arm arm)
        {
            bool wasRecorded=arm.mocapWeight>0;
            arm.mocapWeight=upperBodyMocap!=null?upperBodyMocap.Weight*(1-seatBraceWeight):0;
            // A contact correction belongs to its current target. Do not carry
            // a face/torso offset into the lap when control returns from a clip.
            if(wasRecorded!=(arm.mocapWeight>0))arm.contact.offset=Vector3.zero;
            if(arm.mocapWeight>0)
            {
                arm.target=arm.hand.position;
                arm.joints.DistributeRecordedRoll();
                Measure(arm,arm.target);
                // Free FK motion keeps its recorded elbow, wrist and fingers.
                // IK is enabled again only if a contact actually needs correction.
                arm.ik.weight=0;
            }
        }

        void ShapeRecordedArm(Arm arm,bool isLeft,Quaternion bodyFrame,ref Vector3 target)
        {
            var idle=seatedMocap.IdleArm(isLeft);
            float movement=TransientsSuppressed?0:Emotion=="numb"?.1f:Emotion=="afraid"?.2f:1;
            float available=movement*(1-seatBraceWeight),length=arm.upperLength+arm.lowerLength;
            var toLocal=Quaternion.Inverse(transform.rotation)*bodyFrame;
            float free=Mathf.SmoothStep(0,1,(target.y-arm.rest.y)/.08f);
            Vector3 small=toLocal*idle.wrist*length*(Emotion=="anxious"?.065f:.035f)*available;
            small=Vector3.ClampMagnitude(small,.012f);
            small.y*=free; // A supported palm may shift along the leg, not float above it.
            target+=small;
            Quaternion elbow=Quaternion.RotateTowards(Quaternion.identity,idle.elbow,3);
            Quaternion hand=Quaternion.RotateTowards(Quaternion.identity,idle.hand,3);
            arm.recordedElbow=bodyFrame*Quaternion.Slerp(Quaternion.identity,elbow,available)*Quaternion.Inverse(bodyFrame);
            arm.recordedHand=bodyFrame*Quaternion.Slerp(Quaternion.identity,hand,available*free*(1-FaceCover))*Quaternion.Inverse(bodyFrame);
        }
        void UpdateEmotionMotion(float age)
        {
            if(age>=nextMotion)
            {
                motionStarted=age;
                motionDuration=Random.Range(Emotion=="crying"?.65f:1.1f,Emotion=="crying"?1.25f:2.1f);
                motionStrength=Random.Range(.55f,1);
                nextMotion=age+motionDuration+Random.Range(Emotion=="crying"?.35f:2,Emotion=="crying"?2.4f:5.5f);
            }
            float phase=(age-motionStarted)/motionDuration;
            EmotionMotion=phase>=0 && phase<1?Mathf.Sin(phase*Mathf.PI)*motionStrength:0;
        }
        Vector3 FaceSupportWrist(Arm arm,float side)
        {
            if(facePerformance && facePerformance.HasFaceSupports)
            {
                var rotation=Quaternion.LookRotation(head.TransformDirection(headUp),-head.TransformDirection(headForward))*
                    Quaternion.Inverse(Quaternion.LookRotation(arm.fingerAxis,arm.palmAxis));
                return Local(facePerformance.FaceSupport(side)-rotation*arm.palmContact);
            }
            return Local(head.position+head.TransformDirection(headUp)*-.035f+head.TransformDirection(headForward)*.145f)+new Vector3(side*.06f,0,0);
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
        void StartSeatPhase(SeatPhase next)
        {
            if(next==SeatPhase.Cancel){seatCancelForward=seatForward;seatCancelBrace=seatBraceWeight;seatCancelLean=seatLean;seatSupportReady=false;}
            if(next==SeatPhase.Brace)seatSupportReady=false;
            if(next==SeatPhase.Idle){relaxedSeconds=0;nextSeatCycle=Random.Range(45f,90f);seatSupportReady=false;}
            seatPhase=next;seatPhaseTime=0;
        }
        void UpdateSeat(float delta)
        {
            if(!seatEnabled)return;
            bool relaxed=Emotion=="neutral"||Emotion=="calm";
            if(seatPhase==SeatPhase.Idle)
            {
                relaxedSeconds=relaxed?relaxedSeconds+delta:0;
                if(relaxedSeconds>=nextSeatCycle)StartSeatPhase(SeatPhase.Drift);
            }
            else seatPhaseTime+=delta;
            seatForward=0;seatHeight=0;seatBraceWeight=0;seatLean=0;
            switch(seatPhase)
            {
                case SeatPhase.Drift:
                    seatForward=.11f*Mathf.SmoothStep(0,1,seatPhaseTime/12f);
                    seatLean=-2*Mathf.SmoothStep(0,1,seatPhaseTime/12f);
                    if(seatPhaseTime>=12f)StartSeatPhase(SeatPhase.Brace);
                    break;
                case SeatPhase.Brace:
                    seatForward=.11f;seatBraceWeight=Mathf.SmoothStep(0,1,seatPhaseTime/.8f);
                    seatLean=Mathf.Lerp(-2,25,Mathf.SmoothStep(0,1,seatPhaseTime/.8f));
                    break;
                case SeatPhase.Load:
                    seatForward=.11f;seatBraceWeight=1;
                    seatLean=Mathf.Lerp(25,30,Mathf.SmoothStep(0,1,seatPhaseTime/.35f));
                    if(seatPhaseTime>=.35f)StartSeatPhase(SeatPhase.Lift);
                    break;
                case SeatPhase.Lift:
                    seatForward=.11f;seatBraceWeight=1;
                    seatHeight=.035f*Mathf.SmoothStep(0,1,seatPhaseTime/.65f);
                    seatLean=Mathf.Lerp(30,24,Mathf.SmoothStep(0,1,seatPhaseTime/.65f));
                    if(seatPhaseTime>=.65f)StartSeatPhase(SeatPhase.Return);
                    break;
                case SeatPhase.Return:
                    seatForward=.11f*(1-Mathf.SmoothStep(0,1,seatPhaseTime/1.2f));
                    seatHeight=.035f;seatBraceWeight=1;
                    seatLean=Mathf.Lerp(24,16,Mathf.SmoothStep(0,1,seatPhaseTime/1.2f));
                    if(seatPhaseTime>=1.2f)StartSeatPhase(SeatPhase.Lower);
                    break;
                case SeatPhase.Lower:
                    seatHeight=.035f*(1-Mathf.SmoothStep(0,1,seatPhaseTime/.7f));
                    seatBraceWeight=1;seatLean=Mathf.Lerp(16,9,Mathf.SmoothStep(0,1,seatPhaseTime/.7f));
                    if(seatPhaseTime>=.7f)StartSeatPhase(SeatPhase.Release);
                    break;
                case SeatPhase.Release:
                    seatBraceWeight=1-Mathf.SmoothStep(0,1,seatPhaseTime/.75f);
                    seatLean=9*seatBraceWeight;
                    if(seatPhaseTime>=.75f)StartSeatPhase(SeatPhase.Idle);
                    break;
                case SeatPhase.Cancel:
                    seatForward=seatCancelForward*(1-Mathf.SmoothStep(0,1,seatPhaseTime/1.2f));
                    seatBraceWeight=seatCancelBrace*(1-Mathf.SmoothStep(0,1,seatPhaseTime/.6f));
                    seatLean=seatCancelLean*(1-Mathf.SmoothStep(0,1,seatPhaseTime/1.2f));
                    if(seatPhaseTime>=1.2f)StartSeatPhase(SeatPhase.Idle);
                    break;
            }
            float fidget=0;
            if(Gesture=="hand_fidget" && Emotion!="numb" && Emotion!="afraid" && seatPhase==SeatPhase.Idle)
            {
                float phase=Mathf.Clamp01((Time.time-gestureStarted)/gestureDuration);
                fidget=.02f*Mathf.Sin(phase*Mathf.PI)*Mathf.Sin(phase*Mathf.PI*2);
            }
            seatOffsetLocal=new Vector3(Mathf.Clamp(fidget+mocapOffsetLocal.x,-.05f,.05f),
                Mathf.Clamp(seatHeight+mocapOffsetLocal.y,0,.041f),
                Mathf.Clamp(seatForward+mocapOffsetLocal.z,-.03f,.11f));
            hip.position+=transform.TransformVector(seatOffsetLocal);
            if(seatOffsetLocal.sqrMagnitude>.00000001f)SolveLegs();
        }
        Vector3 SupportedWrist(Leg leg,Vector3 fallback,float alongThigh)
        {
            if(leg.thigh==null||leg.knee==null)return fallback;
            Vector3 support=Vector3.Lerp(Local(leg.thigh.position),Local(leg.knee.position),alongThigh);
            // Thigh centre to trouser surface, then allow for palm thickness.
            // The wrist sits behind the supported palm, with fingers toward the knee.
            support+=new Vector3(0,.115f,-.055f);
            return support;
        }
        Vector3 KneeSupportWrist(Leg leg,Vector3 fallback)
        {return leg.palmAnchor?Local(leg.palmAnchor.position):fallback;}
        void SolveLegs()
        {
            left.ik.weight=0;right.ik.weight=0;
            leftLeg.ik.weight=1;rightLeg.ik.weight=1;
            using(RigEvaluateMarker.Auto())rigBuilder.Evaluate(0);
            left.ik.weight=1;right.ik.weight=1;
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
            pole=a.recordedElbow*pole;
            Vector3 fingers=Emotion=="crying"?Vector3.Slerp(transform.up,head.TransformDirection(headUp),FaceCover):transform.up;
            Vector3 palm=Emotion=="crying"?-head.TransformDirection(headForward):Emotion=="angry"?-transform.forward:transform.forward;
            if(Emotion=="disgusted" && side<0)upright=false;
            if(Emotion=="frustrated" || Emotion=="confused" || (seatEnabled && Emotion=="happy")){fingers=transform.forward;palm=transform.up;upright=true;}
            if(Emotion=="despondent")upright=false;
            if(Emotion=="angry"){fingers=Vector3.Lerp(transform.forward,transform.up,EmotionMotion*.55f);palm=-transform.up;}
            fingers=a.recordedHand*fingers;palm=a.recordedHand*palm;
            if(seatBraceWeight>0){fingers=Vector3.Slerp(fingers,transform.forward,seatBraceWeight);palm=Vector3.Slerp(palm,-transform.up,seatBraceWeight);}
            a.target=target;a.pole=pole;a.fingers=fingers;a.palm=palm;a.side=side;a.weight=Mathf.Max(upright?Mathf.SmoothStep(0,1,raised*2):0,seatBraceWeight);
            SolveArm(a,target,pole,Time.deltaTime);
            Measure(a,target);
            float fingerActivity=TransientsSuppressed||seatBraceWeight>0?0:Gesture=="hand_fidget"?1:Emotion=="anxious"?Intensity:Emotion=="neutral"||Emotion=="calm"?speechWeight*.4f:0;
            float action=Gesture=="hand_fidget"?Mathf.Sin(Mathf.Clamp01((Time.time-gestureStarted)/gestureDuration)*Mathf.PI):
                facePerformance && facePerformance.IsSpeaking?Mathf.Clamp01(facePerformance.JawWeight*2):EmotionMotion;
            a.articulation.Apply(seatBraceWeight>0?"neutral":Emotion,Intensity,FaceCover,Time.deltaTime,fingerActivity,raised,TransientsSuppressed||seatBraceWeight>0,seatEnabled && raised<.07f,action);
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
            if(a.mocapWeight>0 && rigBuilder && a.ik)
            {
                var other=a==left?right:left;
                a.ikTarget.position=ClampReach(a,target);a.ikTarget.rotation=a.hand.rotation;
                a.ikHint.position=a.lower.position;
                var data=a.ik.data;data.targetRotationWeight=1;a.ik.data=data;
                a.ik.weight=1;if(other.ik)other.ik.weight=0;
                using(RigEvaluateMarker.Auto())rigBuilder.Evaluate(0);
                data.targetRotationWeight=0;a.ik.data=data;a.ik.weight=0;
                a.joints.DistributeRecordedRoll();return;
            }
            SolveArm(a,target,a.pole,0);
        }
        void SolveArm(Arm a,Vector3 target,Vector3 pole,float deltaTime)
        {
            if(!rigBuilder || !a.ik)
            {
                a.joints.Solve(target,pole,transform.forward+transform.right*a.side*.08f,-transform.up,
                    a.fingers,a.palm,a.weight,deltaTime);
                return;
            }
            Arm other=a==left?right:left;
            a.ikTarget.position=ClampReach(a,target);
            a.ikHint.position=a.upper.position+pole;
            a.ik.weight=1;
            if(other.ik)other.ik.weight=0;
            using(RigEvaluateMarker.Auto())rigBuilder.Evaluate(0);
            a.joints.ApplyWristPose(transform.forward+transform.right*a.side*.08f,-transform.up,
                a.fingers,a.palm,a.weight,deltaTime);
            a.ik.weight=1;
            if(other.ik)other.ik.weight=1;
        }
        Vector3 ClampReach(Arm arm,Vector3 target)
        {
            Vector3 delta=target-arm.upper.position;
            float distance=delta.magnitude;
            float min=Mathf.Sqrt(arm.upperLength*arm.upperLength+arm.lowerLength*arm.lowerLength+
                2*arm.upperLength*arm.lowerLength*Mathf.Cos(145*Mathf.Deg2Rad));
            float max=Mathf.Sqrt(arm.upperLength*arm.upperLength+arm.lowerLength*arm.lowerLength+
                2*arm.upperLength*arm.lowerLength*Mathf.Cos(8*Mathf.Deg2Rad));
            Vector3 direction=distance>.0001f?delta/distance:arm.upper.forward;
            return arm.upper.position+direction*Mathf.Clamp(distance,min,max);
        }
        void InitializeArmRig()
        {
            Animator animator=null;
            foreach(var candidate in GetComponentsInChildren<Animator>())
            {animator=candidate;break;}
            if(!animator && !useStaticSeatedPose)return;
            if(!animator)animator=gameObject.AddComponent<Animator>();
            if(!animator.avatar || !animator.avatar.isValid)
            {
                if(!useStaticSeatedPose)return;
                runtimeAvatar=AvatarBuilder.BuildGenericAvatar(animator.gameObject,string.Empty);
                if(!runtimeAvatar || !runtimeAvatar.isValid)
                {
                    Debug.LogError("Could not create a Generic Avatar for the procedural arm rig on "+name,this);
                    return;
                }
                animator.avatar=runtimeAvatar;
            }

            animator.enabled=true;
            foreach(var pose in poses)
                if(!pose.bone.GetComponent<RigTransform>())pose.bone.gameObject.AddComponent<RigTransform>();

            var rigObject=new GameObject("Procedural Arm Rig");
            rigObject.transform.SetParent(animator.transform,false);
            var rig=rigObject.AddComponent<Rig>();
            SetupArmConstraint(rigObject.transform,left,"Left");
            SetupArmConstraint(rigObject.transform,right,"Right");
            if(proceduralSeat && hip && leftLeg.thigh && leftLeg.knee && leftLeg.foot &&
                rightLeg.thigh && rightLeg.knee && rightLeg.foot)
            {
                SetupLegConstraint(rigObject.transform,leftLeg,"Left");
                SetupLegConstraint(rigObject.transform,rightLeg,"Right");
            }

            rigBuilder=animator.GetComponent<RigBuilder>();
            if(!rigBuilder)rigBuilder=animator.gameObject.AddComponent<RigBuilder>();
            rigBuilder.enabled=false;
            rigBuilder.layers.Add(new RigLayer(rig));
            if(!rigBuilder.Build())
            {
                Debug.LogError("Could not build the procedural arm rig for "+name,this);
                rigBuilder=null;
                return;
            }
            rigBuilder.graph.SetTimeUpdateMode(DirectorUpdateMode.Manual);
            Restore();
        }
        void SetupArmConstraint(Transform rigRoot,Arm arm,string side)
        {
            var targetObject=new GameObject(side+" Hand Target");
            arm.ikTarget=targetObject.transform;arm.ikTarget.SetParent(rigRoot,false);arm.ikTarget.position=arm.hand.position;
            var hintObject=new GameObject(side+" Elbow Hint");
            arm.ikHint=hintObject.transform;arm.ikHint.SetParent(rigRoot,false);
            arm.ikHint.position=arm.upper.position-transform.up;
            var constraintObject=new GameObject(side+" Two Bone IK");
            constraintObject.transform.SetParent(rigRoot,false);
            arm.ik=constraintObject.AddComponent<TwoBoneIKConstraint>();
            arm.ik.data=new TwoBoneIKConstraintData
            {
                root=arm.upper,mid=arm.lower,tip=arm.hand,target=arm.ikTarget,hint=arm.ikHint,
                targetPositionWeight=1,targetRotationWeight=0,hintWeight=1,
                maintainTargetPositionOffset=false,maintainTargetRotationOffset=false
            };
        }
        void SetupLegConstraint(Transform rigRoot,Leg leg,string side)
        {
            var palmAnchor=new GameObject(side+" Knee Palm Anchor").transform;
            palmAnchor.position=Vector3.Lerp(leg.thigh.position,leg.knee.position,.78f)+
                transform.TransformVector(new Vector3(0,.105f,-.055f));
            palmAnchor.SetParent(leg.thigh,true);
            leg.palmAnchor=palmAnchor;
            var target=new GameObject(side+" Foot Target").transform;
            target.SetParent(rigRoot,false);target.SetPositionAndRotation(leg.foot.position,leg.foot.rotation);
            leg.ikTarget=target;
            var hint=new GameObject(side+" Knee Hint").transform;
            hint.SetParent(rigRoot,false);hint.position=leg.knee.position+transform.forward*.35f;
            leg.ikHint=hint;
            var constraint=new GameObject(side+" Leg Two Bone IK").transform;
            constraint.SetParent(rigRoot,false);
            leg.ik=constraint.gameObject.AddComponent<TwoBoneIKConstraint>();
            leg.ik.data=new TwoBoneIKConstraintData
            {
                root=leg.thigh,mid=leg.knee,tip=leg.foot,target=leg.ikTarget,hint=leg.ikHint,
                targetPositionWeight=1,targetRotationWeight=1,hintWeight=1,
                maintainTargetPositionOffset=false,maintainTargetRotationOffset=false
            };
            leg.ik.weight=0;
        }
        public void ResolveBodyContacts()
        {
            if(!initialized || performancePaused)return;
            if(seatEnabled)BodyContacts.SetThighRadius(Mathf.Lerp(.093f,.073f,seatBraceWeight));
            BodyContacts.Resolve(left.contact,left.target,Time.deltaTime,left.mocapWeight>0);
            BodyContacts.Resolve(right.contact,right.target,Time.deltaTime,right.mocapWeight>0);
            BodyContacts.SeparateHands(left.contact,left.target,right.contact,right.target);
            if(seatPhase==SeatPhase.Brace && seatPhaseTime>=.8f)
            {
                Vector3 leftSupport=transform.TransformPoint(KneeSupportWrist(leftLeg,left.rest));
                Vector3 rightSupport=transform.TransformPoint(KneeSupportWrist(rightLeg,right.rest));
                seatSupportReady=Vector3.Distance(left.hand.position,leftSupport)<.025f &&
                    Vector3.Distance(right.hand.position,rightSupport)<.025f;
                if(seatSupportReady)StartSeatPhase(SeatPhase.Load);
                else if(seatPhaseTime>1.8f)StartSeatPhase(SeatPhase.Cancel);
            }
            // Record final geometry as well as the uncorrected animation geometry.
            Measure(left,left.contact.target);Measure(right,right.contact.target);
        }
    }
}
