using System;
using UnityEngine;

namespace PsychologyVR
{
    public class RoomSurfaceLibrary : ScriptableObject
    {
        [Serializable] public struct Entry { public Material original, enhanced; }
        public Entry[] entries;
    }
}
