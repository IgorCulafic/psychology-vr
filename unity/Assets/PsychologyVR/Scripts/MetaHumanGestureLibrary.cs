using System;
using UnityEngine;

namespace PsychologyVR
{
    public sealed class MetaHumanGestureLibrary : ScriptableObject
    {
        public enum Kind { Idle, Thoughtful, Tension, Speech }
        [Serializable] public sealed class Gesture
        {
            public string id;
            public Kind kind;
            public AnimationClip clip;
            public string[] bones;
            public bool additive,headContact;
        }
        public Gesture[] gestures;
    }
}
