using System;
using System.Collections.Generic;
using System.IO;
using UnityEngine;

namespace PsychologyVR
{
    [Serializable] public sealed class RecordedFaceFrame
    {
        public float time;
        public bool valid;
        public float[] weights;
        public bool headValid;
        public float[] headRotation;
    }

    [Serializable] public sealed class RecordedFaceTake
    {
        public string source, method;
        public float fps, duration;
        public int headPoseVersion;
        public string[] names;
        public RecordedFaceFrame[] frames;

        public static RecordedFaceTake Load(string path)
        {
            var take = JsonUtility.FromJson<RecordedFaceTake>(File.ReadAllText(path));
            if (take == null || take.fps <= 0 || take.duration <= 0 || take.names == null ||
                take.frames == null || take.frames.Length < 2)
                throw new InvalidDataException("Invalid face take: " + path);
            for (int i = 0; i < take.frames.Length; i++)
            {
                var frame = take.frames[i];
                if (frame.weights == null || frame.weights.Length != take.names.Length ||
                    Mathf.Abs(frame.time - i / take.fps) > .001f)
                    throw new InvalidDataException("Face take has invalid channel counts or timestamps.");
                foreach (float v in frame.weights)
                    if (float.IsNaN(v) || float.IsInfinity(v) || v < 0 || v > 1)
                        throw new InvalidDataException("Invalid face coefficient.");
                if (take.headPoseVersion > 0)
                {
                    if (frame.headRotation == null || frame.headRotation.Length != 4)
                        throw new InvalidDataException("Missing head quaternion.");
                    float norm = 0;
                    foreach (float v in frame.headRotation) norm += v * v;
                    if (float.IsNaN(norm) || Mathf.Abs(norm - 1) > .001f)
                        throw new InvalidDataException("Head quaternion is not normalized.");
                }
            }
            return take;
        }

        public void Sample(float seconds, Dictionary<string, float> values)
        {
            float index = Mathf.Clamp(seconds * fps, 0, frames.Length - 1);
            int a = Mathf.FloorToInt(index), b = Mathf.Min(a + 1, frames.Length - 1);
            for (int i = 0; i < names.Length; i++)
                values[names[i]] = Mathf.Lerp(frames[a].valid ? frames[a].weights[i] : 0,
                    frames[b].valid ? frames[b].weights[i] : 0, index - a);
        }

        public Quaternion SampleHead(float seconds, float strength = 1)
        {
            if (headPoseVersion == 0) return Quaternion.identity;
            float index = Mathf.Clamp(seconds * fps, 0, frames.Length - 1);
            int a = Mathf.FloorToInt(index), b = Mathf.Min(a + 1, frames.Length - 1);
            Quaternion q = Quaternion.Slerp(HeadQuaternion(frames[a]), HeadQuaternion(frames[b]), index - a);
            return Quaternion.Slerp(Quaternion.identity, q, Mathf.Clamp01(strength));
        }
        static Quaternion HeadQuaternion(RecordedFaceFrame frame)
        {
            if (!frame.headValid) return Quaternion.identity;
            var q = frame.headRotation;
            return new Quaternion(q[0], q[1], q[2], q[3]);
        }
    }

    // Bind once in the rest pose. Pure sampling supports scrubbing without accumulating rotation.
    public sealed class RecordedHeadBinding
    {
        public readonly Transform head;
        public readonly Quaternion rest;
        readonly Quaternion basis;
        public RecordedHeadBinding(Transform headBone, Vector3 characterForward)
        {
            head = headBone; rest = head.localRotation;
            basis = Quaternion.Inverse(head.parent.rotation) * Quaternion.LookRotation(characterForward, Vector3.up);
        }
        public Quaternion Rotation(Quaternion motion) => basis * motion * Quaternion.Inverse(basis) * rest;
        public void Apply(Quaternion motion) { head.localRotation = Rotation(motion); }
    }

    // Explicit approximate ARKit-style -> supplied CC rig mapping. Not a MetaHuman solve.
    public static class RecordedFaceMapping
    {
        public struct Channel
        {
            public string source, target;
            public float gain;
            public Channel(string s, string t, float g = 1) { source = s; target = t; gain = g; }
        }
        public static readonly List<Channel> Channels = Create();
        static List<Channel> Create()
        {
            var channels = new List<Channel>();
            foreach (string side in new[] { "Left", "Right" })
            {
                string suffix = side == "Left" ? "_L" : "_R";
                string[] sources = { "browDown", "browOuterUp", "eyeBlink", "eyeSquint", "eyeWide",
                    "cheekSquint", "noseSneer", "mouthSmile", "mouthFrown", "mouthDimple",
                    "mouthStretch", "mouthPress", "mouthLowerDown", "mouthUpperUp" };
                string[] targets = { "Brow_Drop", "Brow_Raise_Outer", "Eye_Blink", "Eye_Squint", "Eye_Wide",
                    "Cheek_Raise", "Nose_Sneer", "Mouth_Smile", "Mouth_Frown", "Mouth_Dimple",
                    "Mouth_Stretch", "Mouth_Press", "Mouth_Down_Lower", "Mouth_Up_Upper" };
                // CC squint is stronger than the video model's corresponding coefficient.
                for (int i = 0; i < sources.Length; i++) channels.Add(new Channel(sources[i] + side, targets[i] + suffix, sources[i] == "eyeSquint" ? .5f : 1));
                channels.Add(new Channel("browInnerUp", "Brow_Raise_Inner" + suffix));
                channels.Add(new Channel("cheekPuff", "Cheek_Puff" + suffix));
                channels.Add(new Channel("mouthPucker", "Mouth_Pucker_Up" + suffix));
                channels.Add(new Channel("mouthPucker", "Mouth_Pucker_Down" + suffix));
                channels.Add(new Channel("mouthFunnel", "Mouth_Funnel_Up" + suffix));
                channels.Add(new Channel("mouthFunnel", "Mouth_Funnel_Down" + suffix));
                channels.Add(new Channel("mouthRollUpper", "Mouth_Roll_In_Upper" + suffix));
                channels.Add(new Channel("mouthRollLower", "Mouth_Roll_In_Lower" + suffix));
                // Gaze requires coordinated eye bones and eyelids; keep both at rest in this face-only POC.
            }
            channels.Add(new Channel("jawOpen", "Jaw_Open"));
            channels.Add(new Channel("jawForward", "Jaw_Forward"));
            channels.Add(new Channel("jawLeft", "Jaw_L"));
            channels.Add(new Channel("jawRight", "Jaw_R"));
            channels.Add(new Channel("mouthLeft", "Mouth_L"));
            channels.Add(new Channel("mouthRight", "Mouth_R"));
            channels.Add(new Channel("mouthClose", "Mouth_Close"));
            channels.Add(new Channel("mouthShrugUpper", "Mouth_Shrug_Upper"));
            channels.Add(new Channel("mouthShrugLower", "Mouth_Shrug_Lower"));
            return channels;
        }
        public static string ShapeName(string name)
        {
            int dot = name.LastIndexOf('.');
            return dot < 0 ? name : name.Substring(dot + 1);
        }
        public static float MeshValue(string mesh, string shape, Dictionary<string, float> targets)
        {
            if ((mesh.Contains("Mustache") || mesh.Contains("Soul_Patch")) && shape == "Jaw_Open") return 0;
            return targets.TryGetValue(shape, out float v) ? v * 100 : 0;
        }
        public static void Map(Dictionary<string, float> source, Dictionary<string, float> targets, float gain)
        {
            targets.Clear();
            foreach (var c in Channels)
                if (source.TryGetValue(c.source, out float v)) targets[c.target] = Mathf.Clamp01(v * c.gain * gain);
        }
    }
}
