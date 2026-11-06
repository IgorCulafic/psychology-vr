using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.TestTools;
using Object = UnityEngine.Object;

namespace PsychologyVR.Editor
{
    public class MetaHumanGesturePreviewTests
    {
        GameObject actor,body,sessionObject,voiceObject;
        MetaHumanJointRig rig;
        PerformanceDriver performance;
        PrototypeSession session;
        FacialPerformance face;
        AudioSource voice;
        MetaHumanGestureLibrary library;
        AnimationClip clip;
        object scheduler;
        IEnumerator preview;
        string folder;
        int originalFramerate;
        Object[] originalResources;

        static FieldInfo Field(Type type,string name)=>type.GetField(name,BindingFlags.Instance|BindingFlags.NonPublic);
        bool Automatic
        {
            get=>(bool)scheduler.GetType().GetField("Automatic").GetValue(scheduler);
            set=>scheduler.GetType().GetField("Automatic").SetValue(scheduler,value);
        }
        static Object[] PreviewResources()=>Resources.FindObjectsOfTypeAll<Object>().Where(o=>
            o is GameObject go&&(go.name=="Gesture front"||go.name=="Gesture side"||go.name=="Preview test body(Clone)")||
            o is RenderTexture rt&&rt.width==768&&rt.height==768||
            o is Texture2D tex&&tex.width==768&&tex.height==768).ToArray();

        [UnitySetUp]
        public IEnumerator SetUp()
        {
            yield return new EnterPlayMode();
            originalFramerate=Time.captureFramerate;
            originalResources=PreviewResources();
            folder=Path.Combine(Path.GetTempPath(),"psychology-vr-gesture-preview-"+Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(folder);
            actor=new GameObject("Preview test actor");actor.SetActive(false);
            rig=actor.AddComponent<MetaHumanJointRig>();
            performance=actor.AddComponent<PerformanceDriver>();
            face=actor.AddComponent<FacialPerformance>();
            Field(typeof(PerformanceDriver),"metaRig").SetValue(performance,rig);
            body=new GameObject("Preview test body");rig.bodyObject=body;
            var bones=new Dictionary<string,Transform>();
            foreach(string name in new[]{"pelvis","thigh_l","calf_l","foot_l","ball_l","thigh_r","calf_r","foot_r","ball_r","hand_l","hand_r"})
            {
                var bone=new GameObject(name).transform;bone.SetParent(body.transform,false);bones.Add(name,bone);
            }
            clip=new AnimationClip{legacy=true};
            clip.SetCurve("hand_l",typeof(Transform),"localPosition.x",AnimationCurve.Constant(0,3,0));
            rig.seatedIdle=clip;
            library=ScriptableObject.CreateInstance<MetaHumanGestureLibrary>();
            library.gestures=new[]{new MetaHumanGestureLibrary.Gesture{id="fold_arms",clip=clip,bones=Array.Empty<string>()}};
            rig.gestureLibrary=library;
            var schedulerType=typeof(MetaHumanJointRig).Assembly.GetType("PsychologyVR.MetaHumanSeatedGestures");
            scheduler=Activator.CreateInstance(schedulerType,body,library,bones);
            Field(typeof(MetaHumanJointRig),"gestures").SetValue(rig,scheduler);
            sessionObject=new GameObject("Preview test session");sessionObject.SetActive(false);
            session=sessionObject.AddComponent<PrototypeSession>();
            voiceObject=new GameObject("Preview test voice");voice=voiceObject.AddComponent<AudioSource>();
            voice.volume=0;
            Field(typeof(PrototypeSession),"performance").SetValue(session,performance);
            Field(typeof(PrototypeSession),"face").SetValue(session,face);
            Field(typeof(PrototypeSession),"voice").SetValue(session,voice);
        }

        [UnityTearDown]
        public IEnumerator TearDown()
        {
            (preview as IDisposable)?.Dispose();
            Time.captureFramerate=originalFramerate;
            foreach(var resource in PreviewResources().Except(originalResources).ToArray())
                if(resource)Object.Destroy(resource);
            foreach(var resource in new Object[]{actor,body,sessionObject,voiceObject,clip,library})
                if(resource)Object.Destroy(resource);
            if(Directory.Exists(folder))Directory.Delete(folder,true);
            yield return null;
            yield return new ExitPlayMode();
        }

        void StartPreview(Action<Camera,string> capture=null,string output=null)
        {
            preview=MetaHumanGesturePreview.Run(session,performance,face,voice,capture??((camera,path)=>{}),output??folder);
        }
        void AssertRestored(bool automatic,bool menuOpen,bool paused)
        {
            Assert.That(Time.captureFramerate,Is.EqualTo(60));
            Assert.That(Automatic,Is.EqualTo(automatic));
            Assert.That(session.MenuOpen,Is.EqualTo(menuOpen));
            Assert.That(performance.IsPaused,Is.EqualTo(paused));
            Assert.That(PreviewResources().Except(originalResources).Any(),Is.False,"Preview resources leaked.");
        }

        [UnityTest]
        public IEnumerator RejectedGestureRestoresStateAndResources()
        {
            Time.captureFramerate=60;
            scheduler.GetType().GetMethod("Play").Invoke(scheduler,new object[]{"fold_arms"});
            StartPreview();
            var error=Assert.Throws<InvalidOperationException>(()=>preview.MoveNext());
            Assert.That(error.Message,Does.Contain("Gesture did not start"));
            yield return null;
            AssertRestored(true,false,false);
        }

        [UnityTest]
        public IEnumerator SetupFailureReleasesPartiallyCreatedResources()
        {
            Time.captureFramerate=60;Automatic=false;
            string blocked=Path.Combine(folder,"not-a-directory");File.WriteAllText(blocked,"test");
            StartPreview(output:blocked);
            Assert.Throws<IOException>(()=>preview.MoveNext());
            yield return null;
            AssertRestored(false,false,false);
        }

        [UnityTest]
        public IEnumerator CaptureFailureRestoresStateAndPropagatesOriginalError()
        {
            Time.captureFramerate=60;
            var expected=new IOException("Injected capture failure");
            StartPreview((camera,path)=>throw expected);
            Exception observed=null;
            for(int step=0;step<200;step++)
            {
                try{if(!preview.MoveNext())break;}
                catch(IOException error){observed=error;break;}
            }
            Assert.That(observed,Is.SameAs(expected));
            yield return null;
            AssertRestored(true,false,false);
        }

        [UnityTest]
        public IEnumerator DisposalDuringPauseRestoresBothInitialPauseStates()
        {
            foreach(bool initiallyPaused in new[]{false,true})
            {
                Time.captureFramerate=60;Automatic=initiallyPaused;
                session.SetMenuOpen(initiallyPaused);performance.PausePerformance(!initiallyPaused);
                // Advance the actual scheduler so the previous cancelled take no longer owns a gesture.
                scheduler.GetType().GetMethod("Apply").Invoke(scheduler,new object[]{"neutral",0f,false,10f});
                StartPreview();
                for(int step=0;step<47;step++)Assert.That(preview.MoveNext(),Is.True);
                Assert.That(session.MenuOpen,Is.True,"The pause checkpoint was not reached.");
                ((IDisposable)preview).Dispose();
                yield return null;
                AssertRestored(initiallyPaused,initiallyPaused,!initiallyPaused);
            }
        }

        [UnityTest]
        public IEnumerator CompletedPreviewWritesPassingReportAndRestoresState()=>CompletePreview(false);

        [UnityTest]
        public IEnumerator ReportWriteFailureStillCleansUpSpeechAndResources()=>CompletePreview(true);

        IEnumerator CompletePreview(bool failReport)
        {
            Time.captureFramerate=60;Automatic=false;voice.loop=true;
            library.gestures[0].id="speech_test";library.gestures[0].kind=MetaHumanGestureLibrary.Kind.Speech;
            string reportPath=Path.Combine(folder,"gesture-report.json");
            if(failReport)Directory.CreateDirectory(reportPath);
            int captures=0;StartPreview((camera,path)=>captures++);
            Exception failure=null;bool completed=false;
            for(int step=0;step<1000;step++)
            {
                bool next;
                try{next=preview.MoveNext();}
                catch(UnauthorizedAccessException error){failure=error;break;}
                if(!next){completed=true;break;}
                // Drive the real scheduler over a tiny native skeleton. Only its root
                // moves: local leg poses still match the sampled reference animation.
                float dt=preview.Current is WaitForSeconds?1:1/30f;
                scheduler.GetType().GetMethod("Apply").Invoke(scheduler,new object[]{"neutral",0f,voice.isPlaying,dt});
                body.transform.position=Vector3.right*.02f;
                Time.captureFramerate=30;
                yield return null;
            }
            yield return null;
            AssertRestored(false,false,false);
            Assert.That(voice.isPlaying,Is.False);Assert.That(face.IsSpeaking,Is.False);
            Assert.That(voice.clip,Is.Null);Assert.That(voice.loop,Is.True);
            Assert.That(captures,Is.EqualTo(2));
            if(failReport)Assert.That(failure,Is.Not.Null);
            else
            {
                Assert.That(completed,Is.True);
                var report=JsonUtility.FromJson<MetaHumanGesturePreview.Report>(File.ReadAllText(reportPath));
                Assert.That(report.passed,Is.True,File.ReadAllText(reportPath));
                Assert.That(report.clips,Is.EqualTo(1));Assert.That(report.frames,Is.GreaterThan(0));
                Assert.That(report.takes.Single().id,Is.EqualTo("speech_test"));
            }
        }

        [UnityTest]
        public IEnumerator RecordingRestoresRenderStateOnSuccessAndWriteFailure()
        {
            if(SystemInfo.graphicsDeviceType==UnityEngine.Rendering.GraphicsDeviceType.Null)
                Assert.Ignore("Recording needs a graphics-enabled Unity Editor.");
            var cameraObject=new GameObject("Recording test camera");
            var camera=cameraObject.AddComponent<Camera>();camera.aspect=1.73f;
            var target=new RenderTexture(768,768,24);
            var pixels=new Texture2D(768,768,TextureFormat.RGB24,false);
            var previous=new RenderTexture(16,16,0);var active=RenderTexture.active;
            try
            {
                yield return null;
                RenderTexture.active=previous;
                var record=typeof(MetaHumanGesturePreview).GetMethod("Record",BindingFlags.Static|BindingFlags.NonPublic);
                string path=Path.Combine(folder,"frame.jpg");
                record.Invoke(null,new object[]{camera,target,pixels,path});
                Assert.That(File.ReadAllBytes(path).Take(2),Is.EqualTo(new byte[]{0xff,0xd8}));
                Assert.That(camera.aspect,Is.EqualTo(1.73f).Within(.0001f));Assert.That(RenderTexture.active,Is.SameAs(previous));
                var error=Assert.Throws<TargetInvocationException>(()=>record.Invoke(null,new object[]{camera,target,pixels,Path.Combine(folder,"missing","frame.jpg")}));
                Assert.That(error.InnerException,Is.TypeOf<DirectoryNotFoundException>());
                Assert.That(camera.aspect,Is.EqualTo(1.73f).Within(.0001f));Assert.That(RenderTexture.active,Is.SameAs(previous));
            }
            finally
            {
                RenderTexture.active=active;target.Release();previous.Release();
                foreach(var resource in new Object[]{cameraObject,target,pixels,previous})Object.Destroy(resource);
            }
        }
    }
}
