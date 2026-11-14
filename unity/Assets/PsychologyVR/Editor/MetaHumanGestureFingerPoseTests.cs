using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using NUnit.Framework;
using UnityEditor;
using UnityEngine;
using Object=UnityEngine.Object;

namespace PsychologyVR.Editor
{
    public class MetaHumanGestureFingerPoseTests
    {
        [TestCase("alex")]
        [TestCase("nikola")]
        [TestCase("stefan")]
        public void SeatedCharactersKeepTheirRestingFingersWhileSpeakingWithoutGestures(string character)
        {
            string path="Assets/PsychologyVR/Art/MetaHumans/"+character+"/Character.prefab";
            var actor=PrefabUtility.LoadPrefabContents(path);
            try
            {
                var rig=actor.GetComponent<MetaHumanJointRig>();
                var bones=rig.bodyObject.GetComponentsInChildren<Transform>(true).GroupBy(t=>t.name).ToDictionary(g=>g.Key,g=>g.First());
                var type=typeof(MetaHumanJointRig).Assembly.GetType("PsychologyVR.MetaHumanSeatedGestures");
                var scheduler=Activator.CreateInstance(type,BindingFlags.Instance|BindingFlags.Public|BindingFlags.NonPublic,null,
                    new object[]{rig.bodyObject,rig.gestureLibrary,bones},null);
                type.GetMethod("ApplySeatedHands").Invoke(scheduler,null);
                var finger=bones["index_01_l"];
                var restingRotation=finger.localRotation;
                var apply=type.GetMethod("Apply");
                for(int i=0;i<600;i++)apply.Invoke(scheduler,new object[]{"neutral",0f,true,.1f});
                Assert.That(type.GetProperty("Active").GetValue(scheduler),Is.EqualTo(""));
                Assert.That(Quaternion.Angle(finger.localRotation,restingRotation),Is.LessThan(.1f));
                Assert.That((bool)type.GetMethod("Play").Invoke(scheduler,new object[]{"hand_fidget"}),Is.False);
                Assert.That((bool)type.GetMethod("Play").Invoke(scheduler,new object[]{"speech_explain_left"}),Is.False);
            }
            finally {PrefabUtility.UnloadPrefabContents(actor);}
        }

        static void RotationCurve(AnimationClip clip,string path,Quaternion rotation)
        {
            const string components="xyzw";
            for(int i=0;i<4;i++)
                clip.SetCurve(path,typeof(Transform),"localRotation."+components[i],AnimationCurve.Constant(0,2.5f,rotation[i]));
        }

        [TestCase(false)]
        [TestCase(true)]
        public void FingerPoseCanBeAbsoluteWhileArmsRemainAdditive(bool absoluteFingers)
        {
            var body=new GameObject("Body");
            var finger=new GameObject("index_01_l").transform;finger.SetParent(body.transform,false);
            var arm=new GameObject("upperarm_l").transform;arm.SetParent(body.transform,false);
            var fingerIdle=Quaternion.Euler(10,35,5);var armIdle=Quaternion.Euler(15,10,0);
            var fingerPose=Quaternion.Euler(35,0,20);var armDelta=Quaternion.Euler(0,0,30);
            finger.localRotation=fingerIdle;arm.localRotation=armIdle;
            var clip=new AnimationClip{legacy=true};
            RotationCurve(clip,"index_01_l",fingerPose);RotationCurve(clip,"upperarm_l",armDelta);
            var library=ScriptableObject.CreateInstance<MetaHumanGestureLibrary>();
            library.gestures=new[]{new MetaHumanGestureLibrary.Gesture{id="test",clip=clip,bones=new[]{"index_01_l","upperarm_l"},additive=true,absoluteFingerPose=absoluteFingers}};
            try
            {
                var type=typeof(MetaHumanJointRig).Assembly.GetType("PsychologyVR.MetaHumanSeatedGestures");
                var scheduler=Activator.CreateInstance(type,BindingFlags.Instance|BindingFlags.Public|BindingFlags.NonPublic,null,
                    new object[]{body,library,new Dictionary<string,Transform>{{"index_01_l",finger},{"upperarm_l",arm}}},null);
                type.GetField("Automatic").SetValue(scheduler,false);
                Assert.That((bool)type.GetMethod("Play").Invoke(scheduler,new object[]{"test"}),Is.True);
                type.GetMethod("Apply").Invoke(scheduler,new object[]{"neutral",0f,false,1f});
                var expected=absoluteFingers?fingerPose:fingerIdle*fingerPose;
                Assert.That(Quaternion.Angle(finger.localRotation,expected),Is.LessThan(.1f));
                Assert.That(Quaternion.Angle(arm.localRotation,armIdle*armDelta),Is.LessThan(.1f));
            }
            finally
            {
                Object.DestroyImmediate(body);Object.DestroyImmediate(clip);Object.DestroyImmediate(library);
            }
        }

        [Test]
        public void SeatedHandsStayRelaxedAndSpeechAutomaticallyStartsAndStopsGesture()
        {
            var body=new GameObject("Body");
            var finger=new GameObject("index_01_l").transform;finger.SetParent(body.transform,false);
            var arm=new GameObject("upperarm_l").transform;arm.SetParent(body.transform,false);
            var initialFinger=Quaternion.Euler(10,35,5);var initialArm=Quaternion.Euler(15,10,0);
            var relaxedFinger=Quaternion.Euler(35,0,20);var armDelta=Quaternion.Euler(0,0,30);
            finger.localRotation=initialFinger;arm.localRotation=initialArm;
            var clip=new AnimationClip{legacy=true};
            RotationCurve(clip,"index_01_l",relaxedFinger);RotationCurve(clip,"upperarm_l",armDelta);
            var library=ScriptableObject.CreateInstance<MetaHumanGestureLibrary>();
            library.promptSpeechGestures=true;
            library.restingFingerPose=new AnimationClip{legacy=true};
            RotationCurve(library.restingFingerPose,"index_01_l",relaxedFinger);
            library.restingFingerBones=new[]{"index_01_l"};
            library.gestures=new[]{new MetaHumanGestureLibrary.Gesture{id="test",clip=clip,bones=new[]{"index_01_l","upperarm_l"},kind=MetaHumanGestureLibrary.Kind.Speech,additive=true,absoluteFingerPose=true}};
            try
            {
                var type=typeof(MetaHumanJointRig).Assembly.GetType("PsychologyVR.MetaHumanSeatedGestures");
                var scheduler=Activator.CreateInstance(type,BindingFlags.Instance|BindingFlags.Public|BindingFlags.NonPublic,null,
                    new object[]{body,library,new Dictionary<string,Transform>{{"index_01_l",finger},{"upperarm_l",arm}}},null);
                Assert.That(Quaternion.Angle(finger.localRotation,initialFinger),Is.LessThan(.1f));
                Assert.That(Quaternion.Angle(arm.localRotation,initialArm),Is.LessThan(.1f));
                type.GetMethod("ApplySeatedHands").Invoke(scheduler,null);
                Assert.That(Quaternion.Angle(finger.localRotation,relaxedFinger),Is.LessThan(.1f));
                Assert.That(Quaternion.Angle(arm.localRotation,initialArm),Is.LessThan(.1f));
                var apply=type.GetMethod("Apply");var active=type.GetProperty("Active");
                for(int i=0;i<10;i++)apply.Invoke(scheduler,new object[]{"neutral",0f,false,.1f});
                Assert.That(active.GetValue(scheduler),Is.EqualTo(""));
                for(int i=0;i<10&&(string)active.GetValue(scheduler)=="";i++)
                    apply.Invoke(scheduler,new object[]{"neutral",0f,true,.1f});
                Assert.That(active.GetValue(scheduler),Is.EqualTo("test"));
                for(int i=0;i<10;i++)apply.Invoke(scheduler,new object[]{"neutral",0f,false,.1f});
                Assert.That(active.GetValue(scheduler),Is.EqualTo(""));
            }
            finally {Object.DestroyImmediate(body);Object.DestroyImmediate(clip);Object.DestroyImmediate(library.restingFingerPose);Object.DestroyImmediate(library);}
        }
    }
}
