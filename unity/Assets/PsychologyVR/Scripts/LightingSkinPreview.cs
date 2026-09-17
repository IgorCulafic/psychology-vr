using System;
using System.Collections;
using System.IO;
using UnityEngine;
using UnityEngine.Rendering;

namespace PsychologyVR
{
    public static class LightingSkinPreview
    {
        public static IEnumerator Run(PrototypeSession session,ConsultationMenu menu,Camera view,Action<Camera,string> capture,string folder)
        {
            Directory.CreateDirectory(folder);
            if(!session.Bounce||!session.Bounce.Available){Debug.LogError("LIGHTING_SKIN_FAILED: baked lighting unavailable bounce="+(bool)session.Bounce+" mapped="+(session.Bounce?session.Bounce.MappedRenderers:0)+" lightmaps="+LightmapSettings.lightmaps.Length+" probes="+(LightmapSettings.lightProbes?LightmapSettings.lightProbes.count:0));Application.Quit(3);yield break;}
            var face=UnityEngine.Object.FindFirstObjectByType<FacialPerformance>();
            bool savedBounce=session.Bounce.Requested,savedSkin=session.NaturalSkin,savedRoom=session.Room.Enhanced;
            int savedPreset=session.Visuals.Preset;float savedStrength=session.Visuals.Strength;bool savedGlow=session.Visuals.Glow;
            session.Room.SetEnhanced(true,false);session.Visuals.Select(2,1,true,false);session.SetNaturalSkin(false,false);
            face.automaticGaze=false;face.blinkOverride=0;session.PreviewEmotion("neutral");
            yield return new WaitForSecondsRealtime(1);
            Vector3 position=view.transform.position;Quaternion rotation=view.transform.rotation;float fov=view.fieldOfView;
            bool passed=true;
            for(int i=0;i<2;i++)
            {
                session.Bounce.SetRequested(i==1,false);
                yield return WaitForReflection(session.Room);
                passed &= session.Room.ReflectionsReady;
                yield return new WaitForEndOfFrame();
                capture(view,Path.Combine(folder,i==0?"before-room.png":"bounced-room.png"));
                int mapped=0;foreach(var renderer in session.Room.GetComponentsInChildren<Renderer>())if(renderer.lightmapIndex>=0&&renderer.lightmapIndex<LightmapSettings.lightmaps.Length)mapped++;
                passed &= i==0?mapped==0:mapped>=50;
                Debug.Log("BOUNCE_RUNTIME active="+session.Bounce.Active+" mapped="+mapped+" probes="+LightmapSettings.lightProbes.count);
            }
            float scale=Time.timeScale;Time.timeScale=0;
            for(int i=0;i<2;i++)
            {
                session.SetNaturalSkin(i==1,false);yield return new WaitForEndOfFrame();
                Portrait(view,face);capture(view,Path.Combine(folder,i==0?"original-skin.png":"natural-skin.png"));
                view.transform.SetPositionAndRotation(position,rotation);view.fieldOfView=fov;
            }
            Time.timeScale=scale;
            int bindings=0;foreach(var skin in UnityEngine.Object.FindObjectsByType<AvatarSkinRendering>())bindings+=skin.SkinBindings;
            passed &= bindings>=4;
            bool tears=false;
            foreach(var emotion in new[]{"angry","afraid","crying","happy"})
            {
                session.PreviewEmotion(emotion);yield return new WaitForSecondsRealtime(emotion=="crying"?2:1);
                yield return new WaitForEndOfFrame();Portrait(view,face);capture(view,Path.Combine(folder,emotion+"-skin.png"));
                view.transform.SetPositionAndRotation(position,rotation);view.fieldOfView=fov;
                if(emotion=="crying")tears=face.Tears&&face.Tears.Visible&&face.Tears.Wetness>.5f;
            }
            passed &= tears;
            session.SetMenuOpen(true);menu.Render(ConsultationMenu.Page.Rendering);
            yield return new WaitForEndOfFrame();capture(view,Path.Combine(folder,"lighting-skin-menu.png"));
            session.Bounce.SetRequested(savedBounce,false);session.SetNaturalSkin(savedSkin,false);session.Room.SetEnhanced(savedRoom,false);session.Visuals.Select(savedPreset,savedStrength,savedGlow,false);
            File.WriteAllText(Path.Combine(folder,"lighting-skin-check.json"),"{\"passed\":"+(passed?"true":"false")+",\"lightmaps\":"+LightmapSettings.lightmaps.Length+",\"probes\":"+LightmapSettings.lightProbes.count+",\"skinBindings\":"+bindings+",\"tearsVisible\":"+(tears?"true":"false")+"}");
            Debug.Log(passed?"LIGHTING_SKIN_OK":"LIGHTING_SKIN_FAILED");Application.Quit(passed?0:4);
        }
        static IEnumerator WaitForReflection(RoomRendering room)
        {
            float deadline=Time.realtimeSinceStartup+12;
            while(!room.ReflectionsReady&&Time.realtimeSinceStartup<deadline)yield return null;
        }
        static void Portrait(Camera view,FacialPerformance face)
        {
            Vector3 focus=face.Head.position+Vector3.up*.065f;
            view.transform.position=focus+face.transform.forward*.75f;view.transform.LookAt(focus);view.fieldOfView=38;
        }
    }
}
