using UnityEngine;

namespace PsychologyVR
{
    // CMU 13_05 supplies small recorded motion; the existing rig owns contacts.
    internal sealed class SeatedMocapOverlay
    {
        const float Crossfade=.6f;
        // The intervening portions of the recording contain standing and walking.
        static readonly Vector2[] SeatedRanges={new Vector2(5.5f,10f),new Vector2(16.5f,23.25f),new Vector2(29.5f,36.5f)};
        struct Motion {public Vector3 hip;public Quaternion abdomen,chest,head;}
        readonly Transform actor,abdomen,chest,head,hip;
        readonly GameObject source;
        readonly AnimationClip clip;
        readonly Motion[] origins;
        readonly float loopDuration;
        float time,weight;
        Vector3 offset,offsetVelocity;
        Quaternion abdomenMotion=Quaternion.identity,chestMotion=Quaternion.identity,headMotion=Quaternion.identity;

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
            abdomen=Find("abdomen");chest=Find("chest");head=Find("head");hip=Find("hip");
            if(!abdomen || !chest || !head || !hip)
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

        Transform Find(string boneName)
        {
            foreach(var bone in source.GetComponentsInChildren<Transform>())
                if(bone.name==boneName)return bone;
            return null;
        }

        Motion Capture(float at)
        {
            clip.SampleAnimation(source,at);
            return new Motion{hip=hip.position,abdomen=abdomen.rotation,chest=chest.rotation,head=head.rotation};
        }

        Motion Read(int segment,float at)
        {
            Motion pose=Capture(at),origin=origins[segment];
            return new Motion{hip=pose.hip-origin.hip,
                abdomen=pose.abdomen*Quaternion.Inverse(origin.abdomen),
                chest=pose.chest*Quaternion.Inverse(origin.chest),
                head=pose.head*Quaternion.Inverse(origin.head)};
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
            if(local<Crossfade)
            {
                int previous=(segment+SeatedRanges.Length-1)%SeatedRanges.Length;
                Motion outgoing=Read(previous,SeatedRanges[previous].y-Crossfade+local);
                float blend=Mathf.SmoothStep(0,1,local/Crossfade);
                motion.hip=Vector3.Lerp(outgoing.hip,motion.hip,blend);
                motion.abdomen=Quaternion.Slerp(outgoing.abdomen,motion.abdomen,blend);
                motion.chest=Quaternion.Slerp(outgoing.chest,motion.chest,blend);
                motion.head=Quaternion.Slerp(outgoing.head,motion.head,blend);
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
