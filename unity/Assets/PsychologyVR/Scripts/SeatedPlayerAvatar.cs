using System.Collections.Generic;
using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.XR;
using CommonUsages=UnityEngine.XR.CommonUsages;

namespace PsychologyVR
{
    // A fixed seated lower body with inferred shoulders and controller-driven arms.
    // Head/controller tracking share one calibration offset; the camera is never IK-clamped.
    [DefaultExecutionOrder(-50)]
    public class SeatedPlayerAvatar:MonoBehaviour
    {
        public Transform trackingOrigin;
        public Camera view;
        public Vector3 wristOffset=new Vector3(0,-.025f,-.055f);
        public static readonly Vector3 SeatedEyes=new Vector3(0,1.30f,.08f);
        public bool DiagnosticInput {get;set;}
        public bool AllowDesktopLook=true;
        public System.Action Recentered;
        public bool HeadTracked {get;private set;}
        public bool LeftTracked {get;private set;}
        public bool RightTracked {get;private set;}
        public float LeftReachError {get;private set;}
        public float RightReachError {get;private set;}
        public Vector3 LeftTarget {get;private set;}
        public Vector3 RightTarget {get;private set;}
        public Transform LeftWrist=>left.hand;
        public Transform RightWrist=>right.hand;
        public int HiddenHeadTriangles {get;set;}
        public string TrackingStatus=>HeadTracked?"Headset tracked | "+(LeftTracked?"L":"L lost")+" / "+(RightTracked?"R":"R lost"):"Desktop preview";
        struct Pose {public Transform bone;public Quaternion rotation;public Vector3 position;}
        class Arm {public Transform upper,lower,hand;public Quaternion handBasis;public Vector3 rest;public HandArticulation fingers;}
        readonly List<Pose> rest=new List<Pose>();
        Arm left,right;Transform spine,chest;Quaternion seatRotation;
        Vector3 calibration,leftPosition,rightPosition;
        Quaternion leftRotation=Quaternion.identity,rightRotation=Quaternion.identity;
        float leftGrip,rightGrip,leftTrigger,rightTrigger;bool calibrated,recenterHeld,ready;
        Transform Bone(string n){foreach(var t in GetComponentsInChildren<Transform>())if(t.name=="CC_Base_"+n)return t;throw new System.InvalidOperationException("Player bone missing: "+n);}
        public void Initialize(Transform origin,Camera camera)
        {
            trackingOrigin=origin;view=camera;seatRotation=transform.rotation;
            foreach(var a in GetComponentsInChildren<Animator>())a.enabled=false;
            CandidateSeatedPose.Apply(gameObject);
            foreach(var b in GetComponentsInChildren<Transform>())if(b.name.StartsWith("CC_Base_"))rest.Add(new Pose{bone=b,rotation=b.localRotation,position=b.localPosition});
            spine=Bone("Waist");chest=Bone("Spine02");
            bool reversed=transform.InverseTransformPoint(Bone("L_Upperarm").position).x>0;
            left=MakeArm(reversed?"R":"L");right=MakeArm(reversed?"L":"R");
            ready=true;view.transform.localPosition=SeatedEyes;
        }
        Arm MakeArm(string side)
        {
            var a=new Arm{upper=Bone(side+"_Upperarm"),lower=Bone(side+"_Forearm"),hand=Bone(side+"_Hand")};
            Vector3 fingers=(Bone(side+"_Mid1").position-a.hand.position).normalized;
            Vector3 palm=Vector3.Cross(Bone(side+"_Index1").position-a.hand.position,Bone(side+"_Pinky1").position-a.hand.position).normalized;
            if(Vector3.Dot(palm,transform.up)>0)palm=-palm;
            a.handBasis=Quaternion.Inverse(Quaternion.LookRotation(a.hand.InverseTransformDirection(fingers),a.hand.InverseTransformDirection(palm)));
            a.rest=transform.InverseTransformPoint(a.hand.position);
            string[] names={"Index","Mid","Ring","Pinky"};var digits=new Transform[4][];var thumbs=new Transform[3];
            for(int f=0;f<4;f++){digits[f]=new Transform[3];for(int j=0;j<3;j++)digits[f][j]=Bone(side+"_"+names[f]+(j+1));}
            for(int j=0;j<3;j++)thumbs[j]=Bone(side+"_Thumb"+(j+1));
            a.fingers=new HandArticulation(digits,thumbs,palm);return a;
        }
        static bool ReadPose(XRNode node,out Vector3 p,out Quaternion q)
        {
            p=Vector3.zero;q=Quaternion.identity;var device=InputDevices.GetDeviceAtXRNode(node);
            return device.isValid && device.TryGetFeatureValue(CommonUsages.isTracked,out bool tracked) && tracked && device.TryGetFeatureValue(CommonUsages.devicePosition,out p) && device.TryGetFeatureValue(CommonUsages.deviceRotation,out q);
        }
        public void Recenter()
        {
            if(ReadPose(XRNode.Head,out var p,out var q))
            {
                // Face the consultation chair regardless of the room's tracking-space heading.
                float yaw=q.eulerAngles.y;trackingOrigin.rotation=Quaternion.Euler(0,-yaw,0);
                calibration=Quaternion.Inverse(trackingOrigin.rotation)*SeatedEyes-p;
                calibrated=true;
                view.transform.localPosition=p+calibration;view.transform.localRotation=q;
                Recentered?.Invoke();
            }
            else if(ready)
            {
                trackingOrigin.rotation=Quaternion.identity;calibration=Vector3.zero;
                view.transform.localPosition=SeatedEyes;view.transform.localRotation=Quaternion.identity;
                Recentered?.Invoke();
            }
        }
        void Update()
        {
            if(!ready || DiagnosticInput)return;
            HeadTracked=ReadPose(XRNode.Head,out var hp,out var hq);
            if(HeadTracked)
            {
                var device=InputDevices.GetDeviceAtXRNode(XRNode.LeftHand);device.TryGetFeatureValue(CommonUsages.primaryButton,out bool pressed);
                if(!calibrated || (pressed&&!recenterHeld) || (Keyboard.current!=null&&Keyboard.current.rKey.wasPressedThisFrame))Recenter();
                recenterHeld=pressed;view.transform.localPosition=hp+calibration;view.transform.localRotation=hq;
            }
            else
            {
                view.transform.position=transform.TransformPoint(SeatedEyes);
                if(AllowDesktopLook&&Mouse.current!=null&&Mouse.current.rightButton.isPressed){var d=Mouse.current.delta.ReadValue();view.transform.Rotate(-d.y*.08f,d.x*.08f,0);}
            }
            LeftTracked=ReadPose(XRNode.LeftHand,out leftPosition,out leftRotation);
            RightTracked=ReadPose(XRNode.RightHand,out rightPosition,out rightRotation);
            var l=InputDevices.GetDeviceAtXRNode(XRNode.LeftHand);var r=InputDevices.GetDeviceAtXRNode(XRNode.RightHand);
            l.TryGetFeatureValue(CommonUsages.grip,out leftGrip);r.TryGetFeatureValue(CommonUsages.grip,out rightGrip);
            l.TryGetFeatureValue(CommonUsages.trigger,out leftTrigger);r.TryGetFeatureValue(CommonUsages.trigger,out rightTrigger);
        }
        public bool RightPointer(out Vector3 position,out Vector3 direction)
        {
            position=trackingOrigin.TransformPoint(rightPosition+calibration);direction=trackingOrigin.TransformDirection(rightRotation*Vector3.forward);return RightTracked;
        }
        void LateUpdate()
        {
            if(!ready)return;
            foreach(var p in rest){p.bone.localPosition=p.position;p.bone.localRotation=p.rotation;}
            Vector3 offset=Quaternion.Inverse(seatRotation)*(view.transform.position-transform.TransformPoint(SeatedEyes));
            float yaw=Mathf.Clamp(Mathf.DeltaAngle(seatRotation.eulerAngles.y,view.transform.eulerAngles.y),-35,35);
            Quaternion lean=seatRotation*Quaternion.Euler(Mathf.Clamp(offset.z*60,-14,18),yaw*.5f,Mathf.Clamp(-offset.x*60,-15,15))*Quaternion.Inverse(seatRotation);
            spine.rotation=lean*spine.rotation;
            LeftTarget=Target(left,LeftTracked,leftPosition,leftRotation);RightTarget=Target(right,RightTracked,rightPosition,rightRotation);
            LeftReachError=Solve(left,LeftTarget,LeftTracked,leftRotation,-1,leftGrip,leftTrigger);
            RightReachError=Solve(right,RightTarget,RightTracked,rightRotation,1,rightGrip,rightTrigger);
        }
        Vector3 Target(Arm arm,bool tracked,Vector3 position,Quaternion rotation)=>tracked?trackingOrigin.TransformPoint(position+calibration+rotation*wristOffset):transform.TransformPoint(arm.rest);
        float Solve(Arm a,Vector3 target,bool tracked,Quaternion rotation,float side,float grip,float trigger)
        {
            Vector3 shoulder=a.upper.position,delta=target-shoulder;float u=Vector3.Distance(shoulder,a.lower.position),v=Vector3.Distance(a.lower.position,a.hand.position);
            float distance=Mathf.Clamp(delta.magnitude,Mathf.Abs(u-v)+.002f,u+v-.002f);
            Vector3 axis=delta.sqrMagnitude>.000001f?delta.normalized:transform.forward;
            Vector3 pole=transform.right*side*.7f-transform.up*.8f+transform.forward*.15f;
            Vector3 perpendicular=Vector3.ProjectOnPlane(pole,axis).normalized;
            if(perpendicular.sqrMagnitude<.01f)perpendicular=Vector3.ProjectOnPlane(transform.forward,axis).normalized;
            float along=(u*u-v*v+distance*distance)/(2*distance);
            Vector3 elbow=shoulder+axis*along+perpendicular*Mathf.Sqrt(Mathf.Max(0,u*u-along*along));
            a.upper.rotation=Quaternion.FromToRotation(a.lower.position-shoulder,elbow-shoulder)*a.upper.rotation;
            a.lower.rotation=Quaternion.FromToRotation(a.hand.position-a.lower.position,shoulder+axis*distance-a.lower.position)*a.lower.rotation;
            Quaternion world=tracked?trackingOrigin.rotation*rotation:transform.rotation;
            a.hand.rotation=Quaternion.LookRotation(world*Vector3.forward,world*Vector3.down)*a.handBasis;
            if(tracked)a.fingers.ApplyController(grip,trigger,Time.deltaTime);else a.fingers.Apply("neutral",0,0,Time.deltaTime);
            return Vector3.Distance(a.hand.position,target);
        }
        public void SetDiagnosticPose(Vector3 headPosition,Quaternion headRotation,Vector3 l,Quaternion lq,Vector3 r,Quaternion rq,float grip=0,bool tracked=true)
        {
            DiagnosticInput=true;HeadTracked=true;LeftTracked=RightTracked=tracked;
            view.transform.localPosition=headPosition;view.transform.localRotation=headRotation;
            leftPosition=l;rightPosition=r;leftRotation=lq;rightRotation=rq;leftGrip=rightGrip=leftTrigger=rightTrigger=grip;
        }
        void OnEnable(){Application.onBeforeRender+=RefreshHead;}
        void OnDisable(){Application.onBeforeRender-=RefreshHead;}
        void RefreshHead()
        {
            if(ready && calibrated && !DiagnosticInput && ReadPose(XRNode.Head,out var p,out var q))
            {view.transform.localPosition=p+calibration;view.transform.localRotation=q;}
        }
    }
}
