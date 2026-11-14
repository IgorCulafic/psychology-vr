using System;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;
namespace PsychologyVR
{
    // The exported joint poses preserve each identity; only the active patient is instantiated.
    public class MetaHumanJointRig : MonoBehaviour
    {
        public MetaHumanPoseLibrary library;
        public GameObject faceObject,bodyObject,clothingObject;
        public SkinnedMeshRenderer skin;
        public bool seated=true;
        public AnimationClip seatedIdle;
        public MetaHumanGestureLibrary gestureLibrary;
        [SerializeField,HideInInspector] Vector2 seatedFootOffset;
        [SerializeField,HideInInspector] bool stabilizeSeatedPelvis;
        Vector3 seatedPelvisAnchor;
        MetaHumanSeatedGestures gestures;
        sealed class RestingHand
        {
            public string side;
            public Transform thigh,upper,lower,hand;
            public Transform[] fingers,fingerNext;
            public Vector3 target,normal,direction,finger,palm;
            public float elbowRotation,elbowSpread,palmRoll;
        }
        RestingHand[] restingHands=Array.Empty<RestingHand>();
        internal string ActiveGesture=>gestures?.Active??"";
        internal float GestureTime=>gestures?.Time??0;
        internal float IdleTime=>idleTime;
        internal bool AutomaticGestures {get=>gestures?.Automatic??true;set{if(gestures!=null)gestures.Automatic=value;}}
        internal bool PlayGesture(string id)=>gestures!=null&&gestures.Play(id);
        internal void StopGesture(bool interrupt)=>gestures?.Stop(interrupt);
        public Transform Head {get;private set;}
        public int BindingCount=>bones==null?0:bones.Length;
        internal void RestartSeatedIdle()
        {
            idleTime=0;
            if(!seatedIdle)return;
            seatedIdle.SampleAnimation(bodyObject,0);CorrectSeatedPelvis();CorrectSeatedFeet();gestures?.ApplySeatedHands();CorrectRestingHands();SyncBase();
            foreach(string n in new[]{"neck_01","neck_02","head"})
                if(bodyBones.TryGetValue(n,out var b)&&faceBones.TryGetValue(n,out var f))f.SetPositionAndRotation(b.position,b.rotation);
            for(int i=0;i<clothTargets.Length;i++)clothTargets[i].SetPositionAndRotation(clothSources[i].position,clothSources[i].rotation);
            if(trouserDeformation)trouserDeformation.ApplyPose(0);
        }
        Transform[] bones;
        Dictionary<string,Transform> bodyBones,faceBones;
        readonly Dictionary<string,MetaHumanPoseLibrary.Pose> poses=new Dictionary<string,MetaHumanPoseLibrary.Pose>();
        Vector3[] neutralP,filteredP;Quaternion[] neutralQ,filteredQ;
        bool[] mouth;
        Transform[] clothTargets,clothSources,faceBaseTargets,faceBaseSources;
        float clock,idleTime,anxiousFingerTime,anxiousFingerWeight;string previousEmotion="";
        bool initialized;
        PerformanceDriver performance;
        SeatedTrouserDeformation trouserDeformation;
        public void Initialize()
        {
            if(initialized||!library)return;
            performance=GetComponent<PerformanceDriver>();
            faceBones=faceObject.GetComponentsInChildren<Transform>().GroupBy(t=>t.name).ToDictionary(g=>g.Key,g=>g.First());
            bodyBones=bodyObject.GetComponentsInChildren<Transform>().GroupBy(t=>t.name).ToDictionary(g=>g.Key,g=>g.First());
            var restFingers=gestureLibrary&&gestureLibrary.restingHandsOnThighs?bodyBones.ToDictionary(p=>p.Key,p=>p.Value.localRotation):null;
            trouserDeformation=GetComponent<SeatedTrouserDeformation>();
            clothTargets=clothingObject?clothingObject.GetComponentsInChildren<Transform>().Where(t=>bodyBones.ContainsKey(t.name)).ToArray():Array.Empty<Transform>();
            clothSources=clothTargets.Select(t=>bodyBones[t.name]).ToArray();
            Head=faceBones["head"];
            bones=library.bones.Select(n=>faceBones[n]).ToArray();
            // Face.fbx also contains skinned shoulders. The body owns their pose;
            // only the facial bank's neck/head and facial joints act independently.
            faceBaseTargets=faceObject.GetComponentsInChildren<Transform>().Where(t=>bodyBones.ContainsKey(t.name)&&!library.bones.Contains(t.name)).ToArray();
            faceBaseSources=faceBaseTargets.Select(t=>bodyBones[t.name]).ToArray();
            foreach(var p in library.poses)poses[p.name]=p;
            neutralP=poses["neutral"].positions;neutralQ=poses["neutral"].rotations;
            filteredP=(Vector3[])neutralP.Clone();filteredQ=(Quaternion[])neutralQ.Clone();
            mouth=bones.Select(b=>new[]{"Jaw","Lip","Mouth","Chin","Teeth","Tongue"}.Any(x=>b.name.IndexOf(x,StringComparison.OrdinalIgnoreCase)>=0)).ToArray();
            RestoreNeutral();
            foreach(var part in GetComponentsInChildren<MeshRenderer>())
            {
                var node=part.transform.name.Contains("_cards_")?part.transform:part.transform.parent;
                if(node && node.name.Contains("_cards_"))node.SetParent(Head,true);
            }
            if(seated)
            {
                if(seatedIdle)
                {
                    seatedIdle.SampleAnimation(bodyObject,0);
                    if(stabilizeSeatedPelvis)seatedPelvisAnchor=transform.InverseTransformPoint(bodyBones["pelvis"].position);
                    CorrectSeatedFeet();
                }
                else SeatBody();
            }
            SyncBase();
            if(trouserDeformation)trouserDeformation.ApplyPose(0);
            if(seated&&seatedIdle&&gestureLibrary)
            {
                gestures=new MetaHumanSeatedGestures(bodyObject,gestureLibrary,bodyBones);
                if(restFingers!=null)
                {
                    gestures.RelaxSeatedFingers(restFingers);
                    // Keep these characters in their resting pose during speech.
                    gestures.Automatic=false;
                }
                gestures.ApplySeatedHands();
                if(restFingers!=null)PrepareRestingHands();
            }
            initialized=true;
        }
        void Awake(){Initialize();}
        void RestoreNeutral(){for(int i=0;i<bones.Length;i++){bones[i].localPosition=neutralP[i];bones[i].localRotation=neutralQ[i];}}
        void SeatBody()
        {
            var hip=bodyBones["pelvis"];hip.position+=transform.up*(.57f-transform.InverseTransformPoint(hip.position).y);
            foreach(string s in new[]{"l","r"})
            {
                var thigh=bodyBones["thigh_"+s];var calf=bodyBones["calf_"+s];var foot=bodyBones["foot_"+s];var rest=foot.rotation;
                thigh.rotation=Quaternion.FromToRotation(calf.position-thigh.position,transform.forward-transform.up*.12f)*thigh.rotation;
                calf.rotation=Quaternion.FromToRotation(foot.position-calf.position,-transform.up)*calf.rotation;foot.rotation=rest;
                var upper=bodyBones["upperarm_"+s];var lower=bodyBones["lowerarm_"+s];var hand=bodyBones["hand_"+s];
                float side=Mathf.Sign(transform.InverseTransformPoint(upper.position).x);
                var elbow=transform.TransformPoint(new Vector3(side*.25f,.84f,.08f));
                var target=transform.TransformPoint(new Vector3(side*.17f,.65f,.29f));
                float a=Vector3.Distance(upper.position,lower.position),b=Vector3.Distance(lower.position,hand.position);
                var direction=(target-upper.position).normalized;float distance=Mathf.Clamp(Vector3.Distance(target,upper.position),Mathf.Abs(a-b)+.001f,a+b-.001f);
                float along=(a*a-b*b+distance*distance)/(2*distance);
                var pole=Vector3.ProjectOnPlane(elbow-upper.position,direction).normalized;
                elbow=upper.position+direction*along+pole*Mathf.Sqrt(Mathf.Max(0,a*a-along*along));
                upper.rotation=Quaternion.FromToRotation(lower.position-upper.position,elbow-upper.position)*upper.rotation;
                lower.rotation=Quaternion.FromToRotation(hand.position-lower.position,target-lower.position)*lower.rotation;
                if(bodyBones.TryGetValue("middle_01_"+s,out var middle)&&bodyBones.TryGetValue("index_01_"+s,out var index)&&bodyBones.TryGetValue("pinky_01_"+s,out var pinky))
                {
                    var finger=hand.InverseTransformDirection(middle.position-hand.position);
                    var palm=hand.InverseTransformDirection(Vector3.Cross(index.position-hand.position,pinky.position-hand.position).normalized);
                    if(s=="r")palm=-palm;
                    hand.rotation=Quaternion.LookRotation(transform.forward,-transform.up)*Quaternion.Inverse(Quaternion.LookRotation(finger,palm));
                }
            }
        }
        void SyncBase()
        {
            for(int i=0;i<faceBaseTargets.Length;i++)faceBaseTargets[i].SetPositionAndRotation(faceBaseSources[i].position,faceBaseSources[i].rotation);
        }
        void CorrectSeatedFeet()
        {
            // Keep the animation's movement and rotation; compensate for each body's leg length.
            if(Mathf.Abs(seatedFootOffset.x)>=.0001f)CorrectSeatedFoot(bodyBones["thigh_l"],bodyBones["calf_l"],bodyBones["foot_l"],seatedFootOffset.x);
            if(Mathf.Abs(seatedFootOffset.y)>=.0001f)CorrectSeatedFoot(bodyBones["thigh_r"],bodyBones["calf_r"],bodyBones["foot_r"],seatedFootOffset.y);
        }
        void PrepareRestingHands()
        {
            if(!trouserDeformation||!trouserDeformation.trousers)return;
            var trousers=trouserDeformation.trousers;var mesh=new Mesh();trousers.BakeMesh(mesh);
            var probe=new GameObject("Temporary resting hand calibration");
            probe.transform.SetPositionAndRotation(trousers.transform.position,trousers.transform.rotation);
            probe.transform.localScale=trousers.transform.lossyScale;
            var collider=probe.AddComponent<MeshCollider>();collider.sharedMesh=mesh;Physics.SyncTransforms();
            var hands=new List<RestingHand>();
            foreach(string side in new[]{"l","r"})
            {
                var thigh=bodyBones["thigh_"+side];var knee=bodyBones["calf_"+side];var hand=bodyBones["hand_"+side];
                float sideSign=Mathf.Sign(transform.InverseTransformPoint(hand.position).x);
                float forwardOffset=side=="l"?gestureLibrary.restingHandForwardOffset.x:gestureLibrary.restingHandForwardOffset.y;
                var alongThigh=Vector3.ProjectOnPlane(knee.position-thigh.position,transform.up).normalized;
                var rayOrigin=hand.position-transform.right*sideSign*.01f+alongThigh*forwardOffset+transform.up*.5f;
                if(!collider.Raycast(new Ray(rayOrigin,-transform.up),out var hit,1f))
                {Debug.LogWarning("Could not calibrate resting hand on trousers: "+side,this);continue;}
                var finger=hand.InverseTransformDirection(bodyBones["middle_01_"+side].position-hand.position);
                var palm=hand.InverseTransformDirection(Vector3.Cross(bodyBones["index_01_"+side].position-hand.position,bodyBones["pinky_01_"+side].position-hand.position).normalized);
                if(side=="r")palm=-palm;
                var direction=Vector3.ProjectOnPlane(knee.position-thigh.position,hit.normal).normalized;
                float height=side=="l"?gestureLibrary.restingPalmHeight.x:gestureLibrary.restingPalmHeight.y;
                float elbow=side=="l"?gestureLibrary.restingElbowRotation.x:gestureLibrary.restingElbowRotation.y;
                float spread=side=="l"?gestureLibrary.restingElbowSpread.x:gestureLibrary.restingElbowSpread.y;
                float roll=side=="l"?gestureLibrary.restingPalmRoll.x:gestureLibrary.restingPalmRoll.y;
                hands.Add(new RestingHand{side=side,thigh=thigh,upper=bodyBones["upperarm_"+side],lower=bodyBones["lowerarm_"+side],hand=hand,
                    fingers=new[]{bodyBones["index_01_"+side],bodyBones["middle_01_"+side],bodyBones["ring_01_"+side]},
                    fingerNext=new[]{bodyBones["index_02_"+side],bodyBones["middle_02_"+side],bodyBones["ring_02_"+side]},
                    target=thigh.InverseTransformPoint(hit.point+hit.normal*(.025f+height)),normal=thigh.InverseTransformDirection(hit.normal),
                    direction=thigh.InverseTransformDirection(direction),finger=finger,palm=palm,elbowRotation=elbow,elbowSpread=spread,palmRoll=roll});
            }
            restingHands=hands.ToArray();CorrectRestingHands();FitRestingFingers(collider);gestures.CaptureSeatedFingers();collider.enabled=false;
            if(Application.isPlaying){Destroy(probe);Destroy(mesh);}else{DestroyImmediate(probe);DestroyImmediate(mesh);}
        }
        void FitRestingFingers(MeshCollider collider)
        {
            foreach(var pose in restingHands)foreach(string name in new[]{"thumb","index","middle","ring","pinky"})
            {
                var first=bodyBones[name+"_01_"+pose.side];var second=bodyBones[name+"_02_"+pose.side];var last=bodyBones[name+"_03_"+pose.side];
                var tip=last.position+(last.position-second.position)*.65f;
                if(!collider.Raycast(new Ray(tip+transform.up*.25f,-transform.up),out var hit,.5f))continue;
                var target=hit.point+hit.normal*(name=="thumb"?.03f:name=="pinky"?.013f:.009f);var localTip=last.InverseTransformPoint(tip);
                for(int iteration=0;iteration<(name=="thumb"?4:2);iteration++)foreach(var joint in new[]{last,second,first})
                {
                    var current=last.TransformPoint(localTip);
                    var delta=Quaternion.FromToRotation(current-joint.position,target-joint.position);
                    joint.rotation=Quaternion.RotateTowards(joint.rotation,delta*joint.rotation,7f);
                }
            }
        }
        void CorrectRestingHands()
        {
            foreach(var pose in restingHands)
            {
                var shoulder=pose.upper.position;var elbow=pose.lower.position;var wrist=pose.hand.position;
                var target=pose.thigh.TransformPoint(pose.target);
                float a=Vector3.Distance(shoulder,elbow),b=Vector3.Distance(elbow,wrist);
                var direction=(target-shoulder).normalized;float distance=Mathf.Clamp(Vector3.Distance(target,shoulder),Mathf.Abs(a-b)+.001f,a+b-.001f);
                float along=(a*a-b*b+distance*distance)/(2*distance);
                var pole=Vector3.ProjectOnPlane(elbow-shoulder,direction).normalized;
                var desired=shoulder+direction*along+pole*Mathf.Sqrt(Mathf.Max(0,a*a-along*along));
                pose.upper.rotation=Quaternion.FromToRotation(pose.lower.position-shoulder,desired-shoulder)*pose.upper.rotation;
                pose.lower.rotation=Quaternion.FromToRotation(pose.hand.position-pose.lower.position,target-pose.lower.position)*pose.lower.rotation;
                pose.upper.rotation=Quaternion.AngleAxis(pose.elbowRotation,(pose.hand.position-shoulder).normalized)*pose.upper.rotation;
                pose.upper.rotation=Quaternion.AngleAxis(pose.elbowSpread,(pose.hand.position-shoulder).normalized)*pose.upper.rotation;
                var normal=pose.thigh.TransformDirection(pose.normal);
                var forearm=Vector3.ProjectOnPlane(pose.hand.position-pose.lower.position,normal).normalized;
                var forward=Vector3.Slerp(pose.thigh.TransformDirection(pose.direction),forearm,.5f).normalized;
                pose.hand.rotation=Quaternion.AngleAxis(pose.palmRoll,forward)*Quaternion.LookRotation(forward,-normal)*Quaternion.Inverse(Quaternion.LookRotation(pose.finger,pose.palm));
            }
        }
        void ApplyAnxiousFingers(string emotion,float intensity,float dt)
        {
            if(restingHands.Length==0)return;
            float wanted=emotion=="anxious"&&(!performance||!performance.TransientsSuppressed)?Mathf.Clamp01(intensity):0;
            anxiousFingerWeight=Mathf.MoveTowards(anxiousFingerWeight,wanted,dt/1.5f);
            if(anxiousFingerWeight<=0)return;
            anxiousFingerTime+=dt;
            foreach(var pose in restingHands)
            {
                var normal=pose.thigh.TransformDirection(pose.normal).normalized;
                for(int i=0;i<pose.fingers.Length;i++)
                {
                    float phase=Mathf.Repeat(anxiousFingerTime+(pose.side=="l"?0:1.6f)-i*.3f,4.6f);
                    if(phase>=1.3f)continue;
                    float pulse=Mathf.Sin(Mathf.PI*phase/1.3f);pulse*=pulse;
                    var axis=Vector3.Cross(pose.fingerNext[i].position-pose.fingers[i].position,normal).normalized;
                    // Lift slightly away from the supporting fabric, never curl into it.
                    pose.fingers[i].rotation=Quaternion.AngleAxis(4f*anxiousFingerWeight*pulse,axis)*pose.fingers[i].rotation;
                }
            }
        }
        void CorrectSeatedPelvis()
        {
            if(!stabilizeSeatedPelvis)return;
            // Keep the captured height and rotation, but stop planar drift across the chair.
            var pelvis=bodyBones["pelvis"];
            var position=transform.InverseTransformPoint(pelvis.position);
            position.x=seatedPelvisAnchor.x;position.z=seatedPelvisAnchor.z;
            pelvis.position=transform.TransformPoint(position);
        }
        void CorrectSeatedFoot(Transform thigh,Transform calf,Transform foot,float offset)
        {
            var hip=thigh.position;var knee=calf.position;var ankle=foot.position;var rotation=foot.rotation;
            var target=ankle+transform.up*offset;float upper=Vector3.Distance(hip,knee),lower=Vector3.Distance(knee,ankle);
            var direction=(target-hip).normalized;float distance=Mathf.Clamp(Vector3.Distance(target,hip),Mathf.Abs(upper-lower)+.0001f,upper+lower-.0001f);
            float along=(upper*upper-lower*lower+distance*distance)/(2*distance);
            var pole=Vector3.ProjectOnPlane(knee-hip,direction).normalized;
            var desiredKnee=hip+direction*along+pole*Mathf.Sqrt(Mathf.Max(0,upper*upper-along*along));
            thigh.rotation=Quaternion.FromToRotation(knee-hip,desiredKnee-hip)*thigh.rotation;
            calf.rotation=Quaternion.FromToRotation(foot.position-calf.position,target-calf.position)*calf.rotation;
            foot.rotation=rotation;
        }
        public void Apply(string emotion,float intensity,Dictionary<string,float> weights,bool speaking,string cue,bool paused,float transition)
        {
            Initialize();if(!initialized||paused)return;
            if(seated&&seatedIdle)
            {
                idleTime=Mathf.Repeat(idleTime+Time.deltaTime,seatedIdle.length);
                seatedIdle.SampleAnimation(bodyObject,idleTime);
                CorrectSeatedPelvis();
                CorrectSeatedFeet();
                gestures?.ApplySeatedHands();
                if(gestures==null||gestures.Active=="")
                {
                    CorrectRestingHands();
                    ApplyAnxiousFingers(emotion,intensity,Time.deltaTime);
                }
            }
            gestures?.Apply(emotion,intensity,speaking,Time.deltaTime);
            if(emotion!=previousEmotion){clock=0;previousEmotion=emotion;}else clock+=Time.deltaTime;
            RestoreNeutral();
            AnimationClip clip=emotion=="angry"?library.angry:emotion=="crying"?library.crying:(emotion=="afraid"||emotion=="panicked")?library.afraid:null;
            float recorded=clip?intensity:0;
            if(clip)
            {
                float duration=Mathf.Max(.1f,clip.length),time=Mathf.Repeat(clock,duration);
                // Return to neutral at the seam instead of snapping back to the first frame.
                recorded*=Mathf.SmoothStep(0,1,Mathf.Min(time/.35f,(duration-time)/.45f));
                clip.SampleAnimation(faceObject,time);
            }
            float rate=1-Mathf.Exp(-Time.deltaTime*(speaking?20:7/Mathf.Max(.3f,transition)));
            for(int i=0;i<bones.Length;i++)
            {
                var b=bones[i];bool speechMouth=speaking&&mouth[i];
                var p=Vector3.Lerp(neutralP[i],b.localPosition,speechMouth?0:recorded);
                var q=Quaternion.Slerp(neutralQ[i],b.localRotation,speechMouth?0:recorded);
                foreach(var entry in weights)
                {
                    if(!poses.TryGetValue(entry.Key,out var pose)||entry.Value<.001f)continue;
                    bool blink=entry.Key.StartsWith("Blink"),eye=entry.Key.StartsWith("EyeLook");
                    // Captured acting owns the face; live phonemes own the mouth while speaking.
                    float w=entry.Value*((clip&&!blink&&!eye&&!speechMouth)?1-recorded:1);
                    if(clip&&speaking&&!mouth[i]&&!blink&&!eye)w*=1-recorded;
                    if(w<.001f)continue;
                    if(blink)
                    {
                        if((pose.positions[i]-neutralP[i]).sqrMagnitude>1e-10f||Quaternion.Angle(neutralQ[i],pose.rotations[i])>.001f)
                        {p=Vector3.Lerp(p,pose.positions[i],w);q=Quaternion.Slerp(q,pose.rotations[i],w);}
                        continue;
                    }
                    p+=(pose.positions[i]-neutralP[i])*w;
                    q=q*Quaternion.Slerp(Quaternion.identity,Quaternion.Inverse(neutralQ[i])*pose.rotations[i],w);
                }
                filteredP[i]=Vector3.Lerp(filteredP[i],p,rate);filteredQ[i]=Quaternion.Slerp(filteredQ[i],q,rate);
                b.localPosition=filteredP[i];b.localRotation=filteredQ[i];
            }
            SyncBase();
            foreach(string n in new[]{"neck_01","neck_02","head"})if(bodyBones.TryGetValue(n,out var b)&&faceBones.TryGetValue(n,out var f))
            {
                // Captured facial neck/head acting is a delta over the recorded
                // body, not a replacement for its idle motion.
                if(seated&&seatedIdle)
                {
                    int i=Array.IndexOf(bones,f);
                    float headActing=1-(gestures?.HeadContactWeight??0);
                    f.rotation=b.rotation*Quaternion.Slerp(Quaternion.identity,Quaternion.Inverse(neutralQ[i])*filteredQ[i],headActing);
                }
                b.rotation=f.rotation;
            }
            for(int i=0;i<clothTargets.Length;i++)clothTargets[i].SetPositionAndRotation(clothSources[i].position,clothSources[i].rotation);
            if(trouserDeformation)trouserDeformation.ApplyPose(Time.deltaTime);
        }
    }
}
