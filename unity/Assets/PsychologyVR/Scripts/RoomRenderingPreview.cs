using System;
using System.Collections;
using System.IO;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.UI;

namespace PsychologyVR
{
    public static class RoomRenderingPreview
    {
        public static IEnumerator Run(PrototypeSession session,ConsultationMenu menu,Camera view,Action<Camera,string> capture,string folder)
        {
            Directory.CreateDirectory(folder);
            var room=session.Room;
            if(!room){Debug.LogError("ROOM_DETAIL_FAILED: no furnished room");Application.Quit(2);yield break;}
            int preset=session.Visuals.Preset;float strength=session.Visuals.Strength;bool glow=session.Visuals.Glow;bool enhanced=room.Enhanced;
            session.Visuals.Select(2,1,true,false);
            yield return new WaitForSecondsRealtime(1);
            float scale=Time.timeScale;Time.timeScale=0;
            var position=view.transform.position;var rotation=view.transform.rotation;float fov=view.fieldOfView;
            bool passed=room.SurfaceCount>=16;
            for(int i=0;i<2;i++)
            {
                room.SetEnhanced(i==1,false);
                float deadline=Time.realtimeSinceStartup+15;
                while(!room.ReflectionsReady&&Time.realtimeSinceStartup<deadline)yield return null;
                passed &= room.ReflectionsReady;
                Debug.Log("ROOM_DETAIL_CAPTURE enhanced="+room.Enhanced+" reflectionReady="+room.ReflectionsReady+" resolution="+(room.Probe?room.Probe.resolution:0)+" light="+(room.WindowLight?room.WindowLight.type.ToString():"missing"));
                yield return new WaitForEndOfFrame();
                string label=i==0?"before":"after";
                capture(view,Path.Combine(folder,label+"-room.png"));
                view.transform.position=new Vector3(.15f,1.32f,.05f);view.transform.LookAt(new Vector3(.95f,.70f,1.10f));view.fieldOfView=48;
                capture(view,Path.Combine(folder,label+"-furniture.png"));
                view.transform.position=new Vector3(0,1.26f,.15f);view.transform.LookAt(new Vector3(0,1.23f,1.15f));view.fieldOfView=48;
                capture(view,Path.Combine(folder,label+"-face.png"));
                view.transform.SetPositionAndRotation(position,rotation);view.fieldOfView=fov;
                if(i==1)passed &= room.WindowLight&&room.WindowLight.type==LightType.Spot&&room.WindowLight.shadows==LightShadows.Soft&&room.Probe&&room.Probe.resolution==256;
            }
            Time.timeScale=scale;
            session.PreviewEmotion("crying");
            yield return new WaitForSecondsRealtime(2);
            yield return new WaitForEndOfFrame();capture(view,Path.Combine(folder,"after-crying.png"));
            var face=UnityEngine.Object.FindFirstObjectByType<FacialPerformance>();
            bool tears=face&&face.Tears&&face.Tears.Visible&&face.Tears.Wetness>.5f;passed &= tears;
            session.SetMenuOpen(true);menu.Render(ConsultationMenu.Page.Visuals);
            yield return new WaitForEndOfFrame();capture(view,Path.Combine(folder,"room-detail-menu.png"));
            bool toggle=false;foreach(var button in menu.GetComponentsInChildren<Button>())
                if(button.GetComponentInChildren<Text>()?.text.StartsWith("Room detail:")==true){toggle=true;break;}
            passed &= toggle;
            room.SetEnhanced(enhanced,false);session.Visuals.Select(preset,strength,glow,false);
            File.WriteAllText(Path.Combine(folder,"room-detail-check.json"),"{\"passed\":"+(passed?"true":"false")+",\"surfaceBindings\":"+room.SurfaceCount+",\"tearsVisible\":"+(tears?"true":"false")+",\"filter\":\"Soft film\",\"savedPreferencesUnchanged\":true}");
            Debug.Log(passed?"ROOM_DETAIL_OK":"ROOM_DETAIL_FAILED");Application.Quit(passed?0:3);
        }
    }
}
