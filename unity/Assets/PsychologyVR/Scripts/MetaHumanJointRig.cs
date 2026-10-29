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
        MetaHumanSeatedGestures gestures;
        internal string ActiveGesture=>gestures?.Active??"";
        internal float GestureTime=>gestures?.Time??0;
        internal float IdleTime=>idleTime;
        internal bool AutomaticGestures {set{if(gestures!=null)gestures.Automatic=value;}}
        internal bool PlayGesture(string id)=>gestures!=null&&gestures.Play(id);
        internal void StopGesture(bool interrupt)=>gestures?.Stop(interrupt);
        public Transform Head {get;private set;}
        public int BindingCount=>bones==null?0:bones.Length;
        internal void RestartSeatedIdle()
        {
            idleTime=0;
            if(!seatedIdle)return;
            seatedIdle.SampleAnimation(bodyObject,0);CorrectSeatedFeet();SyncBase();
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
        float clock,idleTime;string previousEmotion="";
        bool initialized;
        SeatedTrouserDeformation trouserDeformation;
        public void Initialize()
        {
            if(initialized||!library)return;
            faceBones=faceObject.GetComponentsInChildren<Transform>().GroupBy(t=>t.name).ToDictionary(g=>g.Key,g=>g.First());
            bodyBones=bodyObject.GetComponentsInChildren<Transform>().GroupBy(t=>t.name).ToDictionary(g=>g.Key,g=>g.First());
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
                if(seatedIdle){seatedIdle.SampleAnimation(bodyObject,0);CorrectSeatedFeet();}
                else SeatBody();
            }
            SyncBase();
            if(trouserDeformation)trouserDeformation.ApplyPose(0);
            if(seated&&seatedIdle&&gestureLibrary)gestures=new MetaHumanSeatedGestures(bodyObject,gestureLibrary,bodyBones);
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
                CorrectSeatedFeet();
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
