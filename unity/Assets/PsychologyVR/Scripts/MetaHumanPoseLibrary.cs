using System;
using UnityEngine;
namespace PsychologyVR
{
    public class MetaHumanPoseLibrary : ScriptableObject
    {
        [Serializable] public class Pose {public string name;public Vector3[] positions;public Quaternion[] rotations;}
        public string[] bones;
        public Pose[] poses;
        public AnimationClip afraid,crying,angry;
    }
}
