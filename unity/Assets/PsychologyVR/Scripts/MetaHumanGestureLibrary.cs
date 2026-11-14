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
            // Some additive upper-body gestures provide authored local finger poses.
            public bool absoluteFingerPose;
            public bool useForSeatedHandPose;
        }
        public bool promptSpeechGestures;
        public bool restingHandsOnThighs;
        public Vector2 restingPalmHeight,restingPalmRoll,restingElbowRotation;
        public Vector2 restingHandForwardOffset,restingElbowSpread;
        public Gesture[] gestures;
    }
}
