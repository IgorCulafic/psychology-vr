using UnityEngine;
namespace PsychologyVR
{
    public static class CandidateSeatedPose
    {
        static Transform Bone(GameObject actor,string name)
        {foreach(var b in actor.GetComponentsInChildren<Transform>())if(b.name=="CC_Base_"+name)return b;throw new System.Exception("Missing CC bone "+name);}
        public static void Apply(GameObject actor)
        {
            var root=actor.transform;var hip=Bone(actor,"Hip");
            // Move the skeleton rather than the actor frame, keeping metre-based hand targets.
            hip.position+=root.up*(.57f-root.InverseTransformPoint(hip.position).y);
            foreach(string side in new[]{"L","R"})
            {
                var thigh=Bone(actor,side+"_Thigh");var calf=Bone(actor,side+"_Calf");var foot=Bone(actor,side+"_Foot");
                Quaternion footRest=foot.rotation;
                thigh.rotation=Quaternion.FromToRotation(calf.position-thigh.position,root.forward+Vector3.down*.12f)*thigh.rotation;
                calf.rotation=Quaternion.FromToRotation(foot.position-calf.position,Vector3.down)*calf.rotation;foot.rotation=footRest;
                var arm=Bone(actor,side+"_Upperarm");var fore=Bone(actor,side+"_Forearm");var hand=Bone(actor,side+"_Hand");
                var middle=Bone(actor,side+"_Mid1");var index=Bone(actor,side+"_Index1");var pinky=Bone(actor,side+"_Pinky1");
                Vector3 finger=hand.InverseTransformDirection((middle.position-hand.position).normalized);
                Vector3 normal=Vector3.Cross(index.position-hand.position,pinky.position-hand.position).normalized;
                // Original CC palm faces forward in its A-pose.
                if(Vector3.Dot(normal,root.forward)<0)normal=-normal;
                Vector3 palm=hand.InverseTransformDirection(normal);
                float sign=Mathf.Sign(root.InverseTransformPoint(arm.position).x);
                Vector3 elbow=root.TransformPoint(new Vector3(sign*.27f,.85f,.07f));
                arm.rotation=Quaternion.FromToRotation(fore.position-arm.position,elbow-arm.position)*arm.rotation;
                fore.rotation=Quaternion.FromToRotation(hand.position-fore.position,root.TransformPoint(new Vector3(sign*.18f,.73f,.30f))-fore.position)*fore.rotation;
                hand.rotation=Quaternion.LookRotation(root.forward,Vector3.down)*Quaternion.Inverse(Quaternion.LookRotation(finger,palm));
            }
        }
    }
}
