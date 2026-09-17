using System;
using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;

namespace PsychologyVR.Editor
{
    public static class BounceLightingSetup
    {
        public const string ScenePath="Assets/PsychologyVR/Scenes/ConsultationLighting.unity";
        public static void Bake()
        {
            var scene=EditorSceneManager.NewScene(NewSceneSetup.EmptyScene,NewSceneMode.Single);
            var room=(GameObject)PrefabUtility.InstantiatePrefab(AssetDatabase.LoadAssetAtPath<GameObject>("Assets/PsychologyVR/Prefabs/ConsultationRoom.prefab"));
            PrefabUtility.UnpackPrefabInstance(room,PrefabUnpackMode.Completely,InteractionMode.AutomatedAction);
            var library=Resources.Load<RoomSurfaceLibrary>("Visuals/RoomSurfaces");
            var originals=new Dictionary<Renderer,Material[]>();
            foreach(var renderer in room.GetComponentsInChildren<MeshRenderer>())
            {
                originals[renderer]=renderer.sharedMaterials;
                var materials=renderer.sharedMaterials;
                for(int i=0;i<materials.Length;i++)foreach(var entry in library.entries)if(materials[i]==entry.original){materials[i]=entry.enhanced;break;}
                renderer.sharedMaterials=materials;
                GameObjectUtility.SetStaticEditorFlags(renderer.gameObject,StaticEditorFlags.ContributeGI|StaticEditorFlags.ReflectionProbeStatic);
                renderer.receiveGI=ReceiveGI.Lightmaps;
                renderer.scaleInLightmap=1;
                // Thin foliage/stems and the lamp have degenerate secondary UVs in the source meshes.
                // They still contribute to GI, but receive it from the baked probe field.
                if(renderer.name.StartsWith("Botanical stem")||renderer.name.Contains("leaves")||renderer.name.Contains("dirt")||renderer.name=="modern_ceiling_lamp_01")
                    renderer.receiveGI=ReceiveGI.LightProbes;
            }
            Light window=null;Quaternion windowRotation=Quaternion.identity;
            foreach(var light in room.GetComponentsInChildren<Light>())
            {
                light.lightmapBakeType=LightmapBakeType.Mixed;
                if(light.name=="Window soft fill")
                {
                    window=light;windowRotation=light.transform.rotation;light.type=LightType.Spot;light.intensity=5;
                    light.spotAngle=120;light.innerSpotAngle=85;light.transform.LookAt(new Vector3(0,.85f,.6f));light.shadows=LightShadows.Soft;
                }
                if(light.name=="Reflected room light")light.bounceIntensity=0;
            }
            // A broad baked emitter supplies the soft daylight that the opaque window
            // artwork cannot transmit into the room. Realtime lights retain their shadows.
            var daylight=new GameObject("Baked window daylight").AddComponent<Light>();
            daylight.transform.SetParent(room.transform,false);
            daylight.transform.position=new Vector3(2.3f,1.85f,.6f);
            daylight.transform.LookAt(new Vector3(0,1.1f,.6f));
            daylight.type=LightType.Rectangle;daylight.lightmapBakeType=LightmapBakeType.Baked;
            daylight.areaSize=new Vector2(2.2f,1.6f);daylight.intensity=3;
            daylight.color=new Color(.84f,.92f,1);daylight.shadows=LightShadows.Soft;daylight.range=8;
            var group=new GameObject("Room indirect light probes").AddComponent<LightProbeGroup>();group.transform.SetParent(room.transform,false);
            var points=new List<Vector3>();
            for(float x=-2.5f;x<=2.5f;x+=1)for(float z=-2.5f;z<=2.5f;z+=1)
                foreach(float y in new[]{.25f,.75f,1.25f,1.8f,2.5f})points.Add(new Vector3(x,y,z));
            group.probePositions=points.ToArray();
            foreach(var probe in room.GetComponentsInChildren<ReflectionProbe>())probe.enabled=false;
            RenderSettings.skybox=null;RenderSettings.ambientMode=AmbientMode.Flat;RenderSettings.ambientLight=new Color(.08f,.09f,.11f);
            var settings=new LightingSettings();settings.name="Consultation indirect lighting";
            settings.bakedGI=true;settings.realtimeGI=false;settings.mixedBakeMode=MixedLightingMode.IndirectOnly;
            settings.lightmapper=LightingSettings.Lightmapper.ProgressiveCPU;
            settings.lightmapResolution=16;settings.lightmapMaxSize=1024;settings.lightmapPadding=4;
            settings.directSampleCount=32;settings.indirectSampleCount=256;settings.environmentSampleCount=64;
            settings.maxBounces=4;settings.lightProbeSampleCountMultiplier=2;
            settings.filteringMode=LightingSettings.FilterMode.Auto;
            const string settingsPath="Assets/PsychologyVR/Scenes/ConsultationBounceSettings.lighting";
            var existing=AssetDatabase.LoadAssetAtPath<LightingSettings>(settingsPath);
            if(existing){EditorUtility.CopySerialized(settings,existing);UnityEngine.Object.DestroyImmediate(settings);settings=existing;EditorUtility.SetDirty(settings);}
            else AssetDatabase.CreateAsset(settings,settingsPath);
            Lightmapping.lightingSettings=settings;
            EditorSceneManager.SaveScene(scene,ScenePath);AssetDatabase.SaveAssets();
            Debug.Log("BOUNCE_BAKE_START renderers="+originals.Count+" probes="+points.Count);
            if(!Lightmapping.Bake())throw new InvalidOperationException("Indirect lighting bake failed.");
            // Runtime RoomRendering starts from the original materials/light parameters.
            foreach(var pair in originals)pair.Key.sharedMaterials=pair.Value;
            if(window){window.type=LightType.Point;window.intensity=3.2f;window.shadows=LightShadows.None;window.transform.rotation=windowRotation;}
            foreach(var probe in room.GetComponentsInChildren<ReflectionProbe>())probe.enabled=true;
            EditorSceneManager.SaveScene(scene);AssetDatabase.SaveAssets();
            int mapped=0;foreach(var renderer in originals.Keys)if(renderer.lightmapIndex>=0&&renderer.lightmapIndex<LightmapSettings.lightmaps.Length)mapped++;
            if(mapped<10||LightmapSettings.lightmaps.Length==0||LightmapSettings.lightProbes==null||LightmapSettings.lightProbes.count==0)
                throw new InvalidOperationException("Bake did not produce usable room lightmaps and probes.");
            EditorBuildSettings.scenes=new[]{new EditorBuildSettingsScene("Assets/PsychologyVR/Scenes/Consultation.unity",true),new EditorBuildSettingsScene(ScenePath,true)};
            Debug.Log("BOUNCE_BAKE_OK lightmaps="+LightmapSettings.lightmaps.Length+" mappedRenderers="+mapped+" probes="+LightmapSettings.lightProbes.count);
        }
    }
}
