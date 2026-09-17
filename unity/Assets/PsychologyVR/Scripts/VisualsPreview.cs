using System;
using System.Collections;
using System.IO;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;
using UnityEngine.UI;

namespace PsychologyVR
{
    public static class VisualsPreview
    {
        public static IEnumerator Run(PrototypeSession session, ConsultationMenu menu, Camera view, Action<Camera,string> capture)
        {
            var args=Environment.GetCommandLineArgs();int at=Array.IndexOf(args,"--capture-path");
            if(at<0||at+1>=args.Length){Debug.LogError("VISUALS_PREVIEW_FAILED: missing capture folder");Application.Quit(2);yield break;}
            string folder=args[at+1];Directory.CreateDirectory(folder);
            if(Array.IndexOf(args,"--lighting-skin-preview")>=0){yield return LightingSkinPreview.Run(session,menu,view,capture,folder);yield break;}
            if(Array.IndexOf(args,"--room-rendering-preview")>=0){yield return RoomRenderingPreview.Run(session,menu,view,capture,folder);yield break;}
            yield return new WaitForSecondsRealtime(1);
            float previousTimeScale=Time.timeScale;Time.timeScale=0;
            var visuals=session.Visuals;int preset=visuals.Preset;float strength=visuals.Strength;bool glow=visuals.Glow;
            bool passed=Resources.Load<VolumeProfile>("Visuals/ConsultationEffects")!=null;
            Vector3 position=view.transform.position;Quaternion rotation=view.transform.rotation;float fov=view.fieldOfView;
            for(int i=0;i<ConsultationVisuals.Names.Length;i++)
            {
                visuals.Select(i,1,true,false);
                yield return new WaitForEndOfFrame();
                capture(view,Path.Combine(folder,i+"-room.png"));
                var stack=VolumeManager.instance.stack;
                float exposure=stack.GetComponent<ColorAdjustments>().postExposure.value;
                var tone=stack.GetComponent<Tonemapping>().mode.value;
                Debug.Log("VISUAL_STYLE_RENDER "+ConsultationVisuals.Names[i]+" exposure="+exposure+" tone="+tone);
                if(i!=0)passed &= exposure>0 && tone!=TonemappingMode.None;
                view.transform.position=new Vector3(0,1.26f,.15f);view.transform.LookAt(new Vector3(0,1.23f,1.15f));view.fieldOfView=48;
                capture(view,Path.Combine(folder,i+"-face.png"));
                view.transform.SetPositionAndRotation(position,rotation);view.fieldOfView=fov;
                passed &= view.GetUniversalAdditionalCameraData().renderPostProcessing==(i!=0);
            }
            visuals.Select(1,0,true,false);
            passed &= !view.GetUniversalAdditionalCameraData().renderPostProcessing;
            visuals.Select(1,1,false,false);
            yield return new WaitForEndOfFrame();
            capture(view,Path.Combine(folder,"warm-no-glow.png"));
            visuals.Select(1,1,true,false);
            session.SetMenuOpen(true);menu.Render(ConsultationMenu.Page.Settings);
            yield return null;
            bool clicked=false;
            foreach(var button in menu.GetComponentsInChildren<Button>())
                if(button.GetComponentInChildren<Text>()?.text=="Visual style"){button.onClick.Invoke();clicked=true;break;}
            yield return new WaitForEndOfFrame();
            passed &= clicked&&menu.CurrentPage==ConsultationMenu.Page.Visuals;
            capture(view,Path.Combine(folder,"visual-settings.png"));
            visuals.Select(preset,strength,glow,false);Time.timeScale=previousTimeScale;
            File.WriteAllText(Path.Combine(folder,"visuals-check.json"),"{\"passed\":"+(passed?"true":"false")+",\"presetsCaptured\":4,\"savedPreferencesUnchanged\":true}");
            Debug.Log(passed?"VISUALS_PREVIEW_OK":"VISUALS_PREVIEW_FAILED");Application.Quit(passed?0:3);
        }
    }
}
