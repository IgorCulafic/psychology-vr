using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering;

namespace PsychologyVR
{
    public class RoomRendering : MonoBehaviour
    {
        public bool Enhanced { get; private set; }
        public bool ReflectionsReady => !reflectionPending && !reflectionBusy && !reflectionFailed;
        public int SurfaceCount { get; private set; }
        public Light WindowLight { get; private set; }
        public ReflectionProbe Probe { get; private set; }
        readonly Dictionary<Renderer, Material[]> originals = new Dictionary<Renderer, Material[]>();
        readonly Dictionary<Material, Material> replacements = new Dictionary<Material, Material>();
        Color ambientSky, ambientEquator, ambientGround;
        float ceilingIntensity, frontIntensity;
        Light ceiling, front, windowBounce;
        bool reflectionPending, reflectionBusy, reflectionFailed;
        Quaternion windowRotation;
        float windowIntensity;
        LightType windowType;
        LightShadows windowShadows;

        public void Initialize()
        {
            RenderSettings.ambientMode=AmbientMode.Trilight;
            RenderSettings.ambientSkyColor=new Color(.62f,.65f,.67f);
            RenderSettings.ambientEquatorColor=new Color(.48f,.46f,.42f);
            RenderSettings.ambientGroundColor=new Color(.28f,.25f,.21f);
            RenderSettings.reflectionIntensity=.55f;
            ambientSky=RenderSettings.ambientSkyColor;ambientEquator=RenderSettings.ambientEquatorColor;ambientGround=RenderSettings.ambientGroundColor;
            var library=Resources.Load<RoomSurfaceLibrary>("Visuals/RoomSurfaces");
            if(library)foreach(var entry in library.entries)if(entry.original&&entry.enhanced)replacements[entry.original]=entry.enhanced;
            foreach(var renderer in GetComponentsInChildren<Renderer>())
            {
                originals[renderer]=renderer.sharedMaterials;
                foreach(var material in renderer.sharedMaterials)if(material&&replacements.ContainsKey(material))SurfaceCount++;
            }
            foreach(var light in GetComponentsInChildren<Light>())
            {
                if(light.name=="Window soft fill")WindowLight=light;
                if(light.name=="Ceiling warm fill")ceiling=light;
                if(light.name=="Reflected room light")front=light;
            }
            if(WindowLight){windowType=WindowLight.type;windowRotation=WindowLight.transform.localRotation;windowIntensity=WindowLight.intensity;windowShadows=WindowLight.shadows;}
            if(WindowLight)
            {
                windowBounce=new GameObject("Window frame bounce").AddComponent<Light>();windowBounce.transform.SetParent(transform,false);
                windowBounce.transform.position=WindowLight.transform.position;windowBounce.type=LightType.Point;
                windowBounce.color=WindowLight.color;windowBounce.intensity=.85f;windowBounce.range=3;windowBounce.shadows=LightShadows.None;
            }
            if(ceiling)ceilingIntensity=ceiling.intensity;if(front)frontIntensity=front.intensity;
            Probe=GetComponentInChildren<ReflectionProbe>();
            QualitySettings.realtimeReflectionProbes=true;
            // The reflection captures the furnished room, excluding people and the menu.
            foreach(var child in GetComponentsInChildren<Transform>())child.gameObject.layer=8;
            if(Probe){Probe.cullingMask=1<<8;Probe.refreshMode=ReflectionProbeRefreshMode.ViaScripting;Probe.timeSlicingMode=ReflectionProbeTimeSlicingMode.NoTimeSlicing;}
            SetEnhanced(PlayerPrefs.GetInt("EnhancedRoomRendering",1)==1,false);
            StartCoroutine(RefreshReflections());
        }

        public void SetEnhanced(bool enhanced, bool save=true)
        {
            Enhanced=enhanced;
            foreach(var pair in originals)
            {
                var materials=(Material[])pair.Value.Clone();
                if(enhanced)for(int i=0;i<materials.Length;i++)if(materials[i]&&replacements.TryGetValue(materials[i],out var replacement))materials[i]=replacement;
                pair.Key.sharedMaterials=materials;
            }
            RenderSettings.ambientSkyColor=enhanced?new Color(.59f,.63f,.66f):ambientSky;
            RenderSettings.ambientEquatorColor=enhanced?new Color(.44f,.43f,.39f):ambientEquator;
            RenderSettings.ambientGroundColor=enhanced?new Color(.26f,.235f,.20f):ambientGround;
            if(WindowLight)
            {
                WindowLight.type=enhanced?LightType.Spot:windowType;
                WindowLight.intensity=enhanced?5.0f:windowIntensity;
                WindowLight.shadows=enhanced?LightShadows.Soft:windowShadows;
                WindowLight.spotAngle=120;WindowLight.innerSpotAngle=85;
                WindowLight.shadowBias=.035f;WindowLight.shadowNormalBias=.12f;WindowLight.shadowCustomResolution=1024;
                if(enhanced)WindowLight.transform.LookAt(transform.TransformPoint(new Vector3(0,.85f,.6f)));
                else WindowLight.transform.localRotation=windowRotation;
            }
            GetComponent<BakedRoomLighting>()?.SetRoomDetail(enhanced);
            if(windowBounce)windowBounce.enabled=enhanced&&!(GetComponent<BakedRoomLighting>()?.Active??false);
            if(ceiling)ceiling.intensity=ceilingIntensity;
            if(front)front.intensity=enhanced?.85f:frontIntensity;
            reflectionPending=true;reflectionFailed=false;
            if(save){PlayerPrefs.SetInt("EnhancedRoomRendering",enhanced?1:0);PlayerPrefs.Save();}
        }

        public void RefreshIndirectState()
        {
            if(windowBounce)windowBounce.enabled=Enhanced&&!(GetComponent<BakedRoomLighting>()?.Active??false);
            reflectionPending=true;reflectionFailed=false;
        }

        void OnApplicationFocus(bool focused)
        {
            if(focused&&reflectionFailed){reflectionPending=true;reflectionFailed=false;}
        }

        IEnumerator RefreshReflections()
        {
            while(true)
            {
                yield return null;
                if(!reflectionPending)continue;
                reflectionPending=false;
                if(!Probe)continue;
                reflectionBusy=true;
                Probe.resolution=Enhanced?256:128;Probe.boxProjection=true;Probe.hdr=true;
                yield return new WaitForEndOfFrame();
                int renderId=Probe.RenderProbe();
                float deadline=Time.realtimeSinceStartup+8;
                while(renderId>=0&&!Probe.IsFinishedRendering(renderId)&&Time.realtimeSinceStartup<deadline)yield return null;
                reflectionFailed=renderId<0||!Probe.IsFinishedRendering(renderId);
                if(reflectionFailed)Debug.LogWarning("Room reflection capture did not finish; retaining the last available reflection.");
                reflectionBusy=false;
            }
        }
    }
}
