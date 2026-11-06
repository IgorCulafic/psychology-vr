using System;
using System.Collections;
using System.IO;
using System.Linq;
using System.Reflection;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.TestTools;
using Object = UnityEngine.Object;

namespace PsychologyVR.Editor
{
    public class PrototypeSessionCaptureTests
    {
        GameObject cameraObject;
        Camera camera;
        RenderTexture previous,originalActive;
        Texture2D decoded;
        Object[] originalResources;
        string folder;

        static Object[] CaptureResources()=>Resources.FindObjectsOfTypeAll<Object>().Where(o=>
            o is RenderTexture rt&&rt.width==1600&&rt.height==1000||
            o is Texture2D tex&&tex.width==1600&&tex.height==1000).ToArray();

        static void Capture(Camera camera,string path)=>typeof(PrototypeSession)
            .GetMethod("Capture",BindingFlags.Static|BindingFlags.NonPublic)
            .Invoke(null,new object[]{camera,path});

        [UnitySetUp]
        public IEnumerator SetUp()
        {
            yield return new EnterPlayMode();
            if(SystemInfo.graphicsDeviceType==UnityEngine.Rendering.GraphicsDeviceType.Null)
                Assert.Ignore("Capture needs a graphics-enabled Unity Editor.");
            originalActive=RenderTexture.active;
            originalResources=CaptureResources();
            folder=Path.Combine(Path.GetTempPath(),"psychology-vr-capture-"+Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(folder);
            cameraObject=new GameObject("Capture test camera");
            camera=cameraObject.AddComponent<Camera>();camera.enabled=false;
            camera.cullingMask=0;camera.clearFlags=CameraClearFlags.SolidColor;
            camera.backgroundColor=new Color(.2f,.4f,.6f);camera.aspect=1.73f;
            previous=new RenderTexture(16,16,0);
            yield return null;
            // Exclude URP's first-render texture pool from Capture's owned resources.
            Capture(camera,Path.Combine(folder,"warmup.png"));
            yield return null;
            originalResources=CaptureResources();
        }

        [UnityTearDown]
        public IEnumerator TearDown()
        {
            RenderTexture.active=originalActive;
            if(originalResources!=null)
                foreach(var resource in CaptureResources().Except(originalResources).ToArray())
                {
                    if(resource is RenderTexture target)target.Release();
                    if(resource)Object.Destroy(resource);
                }
            if(previous)previous.Release();
            foreach(var resource in new Object[]{cameraObject,previous,decoded})
                if(resource)Object.Destroy(resource);
            if(!string.IsNullOrEmpty(folder)&&Directory.Exists(folder))Directory.Delete(folder,true);
            yield return null;
            yield return new ExitPlayMode();
        }

        void AssertCaptureReleased(bool activeRestored)
        {
            var remaining=CaptureResources().Except(originalResources).ToArray();
            Assert.That(remaining,Is.Empty,"Capture textures leaked: "+string.Join(", ",remaining.Select(o=>o.GetType().Name+" "+o.name)));
            Assert.That(activeRestored,Is.True,"Capture must restore the caller's active target before returning.");
            Assert.That(camera.aspect,Is.EqualTo(1.73f).Within(.0001f));
        }

        [UnityTest]
        public IEnumerator CaptureWriteFailureReleasesTexturesAndRestoresTarget()
        {
            RenderTexture.active=previous;
            var error=Assert.Throws<TargetInvocationException>(()=>
                Capture(camera,Path.Combine(folder,"missing","frame.png")));
            Assert.That(error.InnerException,Is.TypeOf<DirectoryNotFoundException>());
            bool activeRestored=RenderTexture.active==previous;
            yield return null;
            AssertCaptureReleased(activeRestored);
        }

        [UnityTest]
        public IEnumerator SuccessfulCaptureWritesPngAndReleasesTextures()
        {
            string path=Path.Combine(folder,"frame.png");
            RenderTexture.active=previous;
            Capture(camera,path);
            bool activeRestored=RenderTexture.active==previous;
            yield return null;
            AssertCaptureReleased(activeRestored);
            var bytes=File.ReadAllBytes(path);
            Assert.That(bytes.Take(8),Is.EqualTo(new byte[]{137,80,78,71,13,10,26,10}));
            decoded=new Texture2D(2,2);
            Assert.That(decoded.LoadImage(bytes),Is.True);
            Assert.That(decoded.width,Is.EqualTo(1600));
            Assert.That(decoded.height,Is.EqualTo(1000));
        }
    }
}
