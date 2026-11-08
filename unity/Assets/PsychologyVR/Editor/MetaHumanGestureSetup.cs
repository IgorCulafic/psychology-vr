using System;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEngine;

namespace PsychologyVR.Editor
{
    public static class MetaHumanGestureSetup
    {
        [Serializable] sealed class Source
        {
            public string id,kind;
            public bool additive,headContact;
            public float fps;
            public MetaHumanSeatedIdleSetup.Frame[] frames;
        }
        public static void Import()
        {
            var args=Environment.GetCommandLineArgs();int at=Array.IndexOf(args,"--native-gesture-source");
            if(at<0||at+1>=args.Length)throw new ArgumentException("--native-gesture-source must name the prepared gesture directory.");
            const string root="Assets/PsychologyVR/Art/MetaHumans/ivan/";
            var sources=Directory.GetFiles(args[at+1],"*.json").Where(p=>Path.GetFileName(p)!="manifest.json")
                .OrderBy(p=>p).Select(p=>JsonUtility.FromJson<Source>(File.ReadAllText(p)))
                .Where(s=>s.id!="lap_adjust"&&s.id!="listening_shift").ToArray();
            var actor=PrefabUtility.LoadPrefabContents(root+"Character.prefab");
            try
            {
                var rig=actor.GetComponent<MetaHumanJointRig>();
                var bones=rig.bodyObject.GetComponentsInChildren<Transform>().ToDictionary(t=>t.name);
                var allowed=new[]{"spine_","neck_","head","clavicle_","upperarm_","lowerarm_","hand_","thumb_","index_","middle_","ring_","pinky_"};
                foreach(var source in sources)
                    if(source.frames==null||source.frames.Length<2||source.frames.Any(f=>f.bones.Any(b=>!bones.ContainsKey(b.name)||!allowed.Any(prefix=>b.name.StartsWith(prefix,StringComparison.Ordinal)))))
                        throw new InvalidDataException("Invalid upper-body recording: "+source.id);
                string folder=root+"animations/Gestures";
                if(!AssetDatabase.IsValidFolder(folder))AssetDatabase.CreateFolder(root+"animations","Gestures");
                var entries=new MetaHumanGestureLibrary.Gesture[sources.Length];
                for(int s=0;s<sources.Length;s++)
                {
                    var source=sources[s];var clip=new AnimationClip{name=source.id,legacy=true,frameRate=source.fps,wrapMode=WrapMode.Once};
                    var selected=source.frames[0].bones.Select(b=>b.name).ToArray();
                    for(int i=0;i<selected.Length;i++)
                    {
                        string path=AnimationUtility.CalculateTransformPath(bones[selected[i]],rig.bodyObject.transform);
                        var values=source.frames.Select(f=>f.bones[i].q.normalized).ToArray();
                        for(int k=1;k<values.Length;k++)if(Quaternion.Dot(values[k-1],values[k])<0)
                            values[k]=new Quaternion(-values[k].x,-values[k].y,-values[k].z,-values[k].w);
                        for(int axis=0;axis<4;axis++)
                        {
                            var curve=new AnimationCurve(Enumerable.Range(0,values.Length).Select(k=>new Keyframe(source.frames[k].time,values[k][axis])).ToArray());
                            MetaHumanSeatedIdleSetup.LinearTangents(curve);
                            clip.SetCurve(path,typeof(Transform),"localRotation."+"xyzw"[axis],curve);
                        }
                    }
                    string asset=folder+"/"+source.id+".anim";
                    var existing=AssetDatabase.LoadAssetAtPath<AnimationClip>(asset);
                    if(existing){EditorUtility.CopySerialized(clip,existing);UnityEngine.Object.DestroyImmediate(clip);clip=existing;}
                    else AssetDatabase.CreateAsset(clip,asset);
                    entries[s]=new MetaHumanGestureLibrary.Gesture{id=source.id,clip=clip,bones=selected,additive=source.additive,headContact=source.headContact,
                        kind=(MetaHumanGestureLibrary.Kind)Enum.Parse(typeof(MetaHumanGestureLibrary.Kind),source.kind)};
                    Debug.Log("SEATED_GESTURE_IMPORTED "+source.id+" seconds="+clip.length+" bones="+selected.Length);
                }
                string bankPath=root+"animations/SeatedGestures.asset";
                var bank=AssetDatabase.LoadAssetAtPath<MetaHumanGestureLibrary>(bankPath);
                if(!bank){bank=ScriptableObject.CreateInstance<MetaHumanGestureLibrary>();AssetDatabase.CreateAsset(bank,bankPath);}
                bank.gestures=entries;EditorUtility.SetDirty(bank);rig.gestureLibrary=bank;
                PrefabUtility.SaveAsPrefabAsset(actor,root+"Character.prefab");AssetDatabase.SaveAssets();
                Debug.Log("SEATED_GESTURES_READY count="+entries.Length);
            }
            finally{PrefabUtility.UnloadPrefabContents(actor);}
            if(Array.IndexOf(args,"--seated-gesture-check")>=0)MetaHumanSeatedIdleSetup.Preview();
        }
    }
}
