using System.Collections;
using System.Collections.Generic;
using NUnit.Framework;
using UnityEditor;
using UnityEngine;
using UnityEngine.TestTools;
using Object=UnityEngine.Object;

namespace PsychologyVR.Editor
{
    public class MetaHumanSeatedPelvisTests
    {
        static MetaHumanJointRig CreateRig(string name,AnimationClip idle,MetaHumanPoseLibrary library,bool stabilize,out Transform pelvis)
        {
            var actor=new GameObject(name);actor.transform.rotation=Quaternion.Euler(0,37,0);
            var rig=actor.AddComponent<MetaHumanJointRig>();
            rig.library=library;rig.seatedIdle=idle;
            rig.bodyObject=new GameObject("Body");rig.bodyObject.transform.SetParent(actor.transform,false);
            pelvis=new GameObject("pelvis").transform;pelvis.SetParent(rig.bodyObject.transform,false);
            rig.faceObject=new GameObject("Face");rig.faceObject.transform.SetParent(actor.transform,false);
            new GameObject("head").transform.SetParent(rig.faceObject.transform,false);
            var serialized=new SerializedObject(rig);serialized.FindProperty("stabilizeSeatedPelvis").boolValue=stabilize;serialized.ApplyModifiedPropertiesWithoutUndo();
            rig.Initialize();return rig;
        }

        [UnityTest]
        public IEnumerator StabilizationKeepsSeatPositionWithoutFreezingHeightOrOtherRigs()
        {
            yield return new EnterPlayMode();
            int oldFramerate=Time.captureFramerate;Time.captureFramerate=20;
            var idle=new AnimationClip{legacy=true};
            idle.SetCurve("pelvis",typeof(Transform),"localPosition.x",AnimationCurve.Linear(0,0,1,.4f));
            idle.SetCurve("pelvis",typeof(Transform),"localPosition.y",AnimationCurve.Linear(0,0,1,.2f));
            idle.SetCurve("pelvis",typeof(Transform),"localPosition.z",AnimationCurve.Linear(0,0,1,.3f));
            var library=ScriptableObject.CreateInstance<MetaHumanPoseLibrary>();
            library.bones=new[]{"head"};library.poses=new[]{new MetaHumanPoseLibrary.Pose{name="neutral",positions=new[]{Vector3.zero},rotations=new[]{Quaternion.identity}}};
            var anchored=CreateRig("anchored",idle,library,true,out var anchoredPelvis);
            var unmodified=CreateRig("unmodified",idle,library,false,out var originalPelvis);
            var start=anchored.transform.InverseTransformPoint(anchoredPelvis.position);
            try
            {
                var weights=new Dictionary<string,float>();
                for(int i=0;i<8;i++)
                {
                    yield return null;
                    anchored.Apply("neutral",0,weights,false,"",false,.65f);
                    unmodified.Apply("neutral",0,weights,false,"",false,.65f);
                }
                var stable=anchored.transform.InverseTransformPoint(anchoredPelvis.position);
                var animated=unmodified.transform.InverseTransformPoint(originalPelvis.position);
                Assert.That(stable.x,Is.EqualTo(start.x).Within(.0001f));
                Assert.That(stable.z,Is.EqualTo(start.z).Within(.0001f));
                Assert.That(stable.y,Is.GreaterThan(start.y+.02f));
                Assert.That(animated.x,Is.GreaterThan(.04f));
                Assert.That(animated.z,Is.GreaterThan(.03f));
            }
            finally
            {
                Time.captureFramerate=oldFramerate;
                Object.Destroy(anchored.gameObject);Object.Destroy(unmodified.gameObject);Object.Destroy(idle);Object.Destroy(library);
            }
            yield return null;
            yield return new ExitPlayMode();
        }
    }
}
