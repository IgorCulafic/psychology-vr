using UnityEngine;

namespace PsychologyVR
{
    // CMU 13_05 supplies small recorded motion; the existing rig owns contacts.
    internal sealed class SeatedMocapOverlay
    {
        const float Crossfade=.6f;
        // The intervening portions of the recording contain standing and walking.
        static readonly Vector2[] SeatedRanges={new Vector2(5.5f,10f),new Vector2(16.5f,23.25f),new Vector2(29.5f,36.5f)};
        internal struct ArmMotion
        {
            public Vector3 wrist;
            public Quaternion elbow,hand;
            internal static ArmMotion Rest=>new ArmMotion{elbow=Quaternion.identity,hand=Quaternion.identity};
        }
        struct ArmPose {public Vector3 wrist,elbow;public Quaternion hand;}
        struct ArmBones
        {
            public Transform shoulder,elbow,hand,middle,index,pinky;
            public float length;
            public bool Valid=>shoulder&&elbow&&hand&&middle&&index&&pinky;
        }
        struct Motion {public Vector3 hip;public Quaternion abdomen,chest,head;public ArmPose left,right;}
        readonly Transform actor,abdomen,chest,head,hip,neck;
        readonly GameObject source;
        readonly AnimationClip clip;
        readonly ArmBones left,right;
        readonly Motion[] origins;
        readonly float loopDuration;
        float time,weight;
        Vector3 offset,offsetVelocity;
        Quaternion abdomenMotion=Quaternion.identity,chestMotion=Quaternion.identity,headMotion=Quaternion.identity;
        ArmMotion idleLeft=ArmMotion.Rest,idleRight=ArmMotion.Rest;

        internal ArmMotion IdleArm(bool isLeft)=>isLeft?idleLeft:idleRight;

        internal SeatedMocapOverlay(Transform actor)
        {
            this.actor=actor;
            const string path="JumperMocap/13_05";
            var prefab=Resources.Load<GameObject>(path);
            foreach(var candidate in Resources.LoadAll<AnimationClip>(path))
                if(!candidate.name.StartsWith("__preview__")){clip=candidate;break;}
            if(!prefab || !clip || clip.length<SeatedRanges[SeatedRanges.Length-1].y)
            {
                Debug.LogError("Jumper seated mocap is missing or too short: Resources/"+path+".fbx",actor);
                return;
            }
            source=Object.Instantiate(prefab);
            source.name="Jumper seated mocap source";
            source.hideFlags=HideFlags.HideInHierarchy;
            // Generic clips require an Animator on the sampled root in a Player.
            if(!source.GetComponent<Animator>())source.AddComponent<Animator>();
            var bones=source.GetComponentsInChildren<Transform>();
            abdomen=Find(bones,"abdomen");chest=Find(bones,"chest");head=Find(bones,"head");hip=Find(bones,"hip");neck=Find(bones,"neck");
            left=FindArm(bones,"l");right=FindArm(bones,"r");
            if(!abdomen || !chest || !head || !hip || !neck || !left.Valid || !right.Valid)
            {
                Debug.LogError("Jumper seated mocap has an unexpected skeleton",actor);
                Object.Destroy(source);
                source=null;
                return;
            }
            origins=new Motion[SeatedRanges.Length];
            for(int i=0;i<SeatedRanges.Length;i++)
            {
                origins[i]=Capture(SeatedRanges[i].x);
                loopDuration+=SeatedRanges[i].y-SeatedRanges[i].x-Crossfade;
            }
        }

        static Transform Find(Transform[] bones,string boneName)
        {
            foreach(var bone in bones)
                if(bone.name==boneName)return bone;
            return null;
        }

        static ArmBones FindArm(Transform[] bones,string side)
        {
            var arm=new ArmBones{shoulder=Find(bones,side+"Shldr"),elbow=Find(bones,side+"ForeArm"),
                hand=Find(bones,side+"Hand"),middle=Find(bones,side+"Mid1"),index=Find(bones,side+"Index1"),pinky=Find(bones,side+"Pinky1")};
            if(arm.Valid)arm.length=Vector3.Distance(arm.shoulder.position,arm.elbow.position)+Vector3.Distance(arm.elbow.position,arm.hand.position);
            return arm;
        }

        static Quaternion BodyFrame(ArmBones left,ArmBones right,Transform hip,Transform neck)
        {
            Vector3 across=(right.shoulder.position-left.shoulder.position).normalized,up=(neck.position-hip.position).normalized;
            return Quaternion.LookRotation(Vector3.Cross(across,up),up);
        }

        static ArmPose CaptureArm(ArmBones arm,Quaternion frame)
        {
            var inverse=Quaternion.Inverse(frame);
            Vector3 fingers=(arm.middle.position-arm.hand.position).normalized;
            Vector3 palm=Vector3.Cross(arm.index.position-arm.hand.position,arm.pinky.position-arm.hand.position).normalized;
            return new ArmPose{wrist=inverse*(arm.hand.position-arm.shoulder.position)/arm.length,
                elbow=inverse*(arm.elbow.position-arm.shoulder.position).normalized,hand=inverse*Quaternion.LookRotation(fingers,palm)};
        }

        static ArmMotion Difference(ArmPose pose,ArmPose origin)
        {return new ArmMotion{wrist=pose.wrist-origin.wrist,elbow=Quaternion.FromToRotation(origin.elbow,pose.elbow),hand=pose.hand*Quaternion.Inverse(origin.hand)};}

        static ArmMotion Blend(ArmMotion from,ArmMotion to,float t)
        {return new ArmMotion{wrist=Vector3.Lerp(from.wrist,to.wrist,t),elbow=Quaternion.Slerp(from.elbow,to.elbow,t),hand=Quaternion.Slerp(from.hand,to.hand,t)};}

        Motion Capture(float at)
        {
            clip.SampleAnimation(source,at);
            var frame=BodyFrame(left,right,hip,neck);
            return new Motion{hip=hip.position,abdomen=abdomen.rotation,chest=chest.rotation,head=head.rotation,
                left=CaptureArm(left,frame),right=CaptureArm(right,frame)};
        }

        Motion Read(int segment,float at)
        {
            Motion pose=Capture(at),origin=origins[segment];
            return new Motion{hip=pose.hip-origin.hip,
                abdomen=pose.abdomen*Quaternion.Inverse(origin.abdomen),
                chest=pose.chest*Quaternion.Inverse(origin.chest),
                head=pose.head*Quaternion.Inverse(origin.head),left=pose.left,right=pose.right};
        }

        internal Vector3 Tick(float delta,bool active)
        {
            if(!source)return Vector3.zero;
            time=Mathf.Repeat(time+delta,loopDuration);
            weight=Mathf.MoveTowards(weight,active?1:0,delta*2);
            float local=time;int segment=0;
            while(segment<SeatedRanges.Length-1)
            {
                float length=SeatedRanges[segment].y-SeatedRanges[segment].x-Crossfade;
                if(local<length)break;
                local-=length;segment++;
            }
            Motion motion=Read(segment,SeatedRanges[segment].x+local);
            ArmMotion l=Difference(motion.left,origins[segment].left),r=Difference(motion.right,origins[segment].right);
            if(local<Crossfade)
            {
                int previous=(segment+SeatedRanges.Length-1)%SeatedRanges.Length;
                Motion outgoing=Read(previous,SeatedRanges[previous].y-Crossfade+local);
                float blend=Mathf.SmoothStep(0,1,local/Crossfade);
                motion.hip=Vector3.Lerp(outgoing.hip,motion.hip,blend);
                motion.abdomen=Quaternion.Slerp(outgoing.abdomen,motion.abdomen,blend);
                motion.chest=Quaternion.Slerp(outgoing.chest,motion.chest,blend);
                motion.head=Quaternion.Slerp(outgoing.head,motion.head,blend);
                l=Blend(Difference(outgoing.left,origins[previous].left),l,blend);
                r=Blend(Difference(outgoing.right,origins[previous].right),r,blend);
            }
            // This FBX stores the CMU positions in centimetres. Smooth recorded
            // pelvis noise before the fixed-foot leg IK sees it.
            Vector3 desired=motion.hip*.01f*weight;
            desired=new Vector3(Mathf.Clamp(desired.x,-.008f,.008f),
                Mathf.Clamp(desired.y,-.006f,.006f),Mathf.Clamp(desired.z,-.008f,.008f));
            offset=Vector3.SmoothDamp(offset,desired,ref offsetVelocity,.22f,Mathf.Infinity,delta);
            float smoothing=1-Mathf.Exp(-delta/.18f);
            abdomenMotion=Quaternion.Slerp(abdomenMotion,Limited(motion.abdomen,3f),smoothing);
            chestMotion=Quaternion.Slerp(chestMotion,Limited(motion.chest,2f),smoothing);
            headMotion=Quaternion.Slerp(headMotion,Limited(motion.head,2.5f),smoothing);
            float armSmoothing=1-Mathf.Exp(-delta/.12f);
            idleLeft=Blend(idleLeft,Blend(ArmMotion.Rest,l,weight),armSmoothing);
            idleRight=Blend(idleRight,Blend(ArmMotion.Rest,r,weight),armSmoothing);
            return offset;
        }

        Quaternion Limited(Quaternion rotation,float degrees)
        {return Quaternion.Slerp(Quaternion.identity,Quaternion.RotateTowards(Quaternion.identity,rotation,degrees),weight);}

        internal void Apply(Transform targetAbdomen,Transform targetChest,Transform targetHead)
        {
            if(!source)return;
            Rotate(targetAbdomen,abdomenMotion);
            Rotate(targetChest,Quaternion.Inverse(abdomenMotion)*chestMotion);
            Rotate(targetHead,Quaternion.Inverse(chestMotion)*headMotion);
        }

        void Rotate(Transform target,Quaternion delta)
        {
            if(!target)return;
            Quaternion basis=actor.rotation;
            target.rotation=basis*delta*Quaternion.Inverse(basis)*target.rotation;
        }

        internal void Dispose(){if(source)Object.Destroy(source);}
    }
}
