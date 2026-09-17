using System;
using System.IO;
using System.Collections.Generic;
using UnityEditor;
using UnityEngine;

namespace PsychologyVR.Editor
{
    public static class SurfaceDetailSetup
    {
        [Serializable] class Map { public string material,map; public bool occlusion; }
        [Serializable] class MapList { public Map[] materials; }
        public static void Prepare()
        {
            const string art="Assets/PsychologyVR/Art/Environment";
            const string folder=art+"/Materials/SurfaceDetail";
            Directory.CreateDirectory(folder);AssetDatabase.Refresh();
            var records=JsonUtility.FromJson<MapList>(File.ReadAllText(art+"/surface-detail.json"));
            var entries=new List<RoomSurfaceLibrary.Entry>();
            foreach(var record in records.materials)
            {
                var original=AssetDatabase.LoadAssetAtPath<Material>(art+"/Materials/"+record.material+".mat");
                if(!original)throw new InvalidOperationException("Missing source material: "+record.material);
                string path=folder+"/"+record.material+".mat";
                var material=AssetDatabase.LoadAssetAtPath<Material>(path);
                if(!material){material=new Material(original);AssetDatabase.CreateAsset(material,path);}else material.CopyPropertiesFromMaterial(original);
                var packed=AssetDatabase.LoadAssetAtPath<Texture2D>(record.map);
                if(!packed)throw new InvalidOperationException("Missing packed texture: "+record.map);
                material.SetTexture("_MetallicGlossMap",packed);material.EnableKeyword("_METALLICSPECGLOSSMAP");material.SetFloat("_Smoothness",1);
                if(record.occlusion){material.SetTexture("_OcclusionMap",packed);material.EnableKeyword("_OCCLUSIONMAP");material.SetFloat("_OcclusionStrength",.7f);}
                if(record.material=="Room_Oak"){material.SetFloat("_BumpScale",.55f);material.SetFloat("_Smoothness",.85f);}
                if(record.material=="Room_Plaster"||record.material=="Room_Sage"){material.SetFloat("_BumpScale",.2f);material.SetFloat("_Smoothness",.35f);}
                EditorUtility.SetDirty(material);entries.Add(new RoomSurfaceLibrary.Entry{original=original,enhanced=material});
            }
            const string libraryPath="Assets/PsychologyVR/Resources/Visuals/RoomSurfaces.asset";
            var library=AssetDatabase.LoadAssetAtPath<RoomSurfaceLibrary>(libraryPath);
            if(!library){library=ScriptableObject.CreateInstance<RoomSurfaceLibrary>();AssetDatabase.CreateAsset(library,libraryPath);}
            library.entries=entries.ToArray();EditorUtility.SetDirty(library);
            var tags=new SerializedObject(AssetDatabase.LoadAllAssetsAtPath("ProjectSettings/TagManager.asset")[0]);
            var layer=tags.FindProperty("layers").GetArrayElementAtIndex(8);
            if(!string.IsNullOrEmpty(layer.stringValue)&&layer.stringValue!="RoomGeometry")throw new InvalidOperationException("Layer 8 is already assigned; choose a free room geometry layer.");
            layer.stringValue="RoomGeometry";tags.ApplyModifiedPropertiesWithoutUndo();
            var quality=new SerializedObject(AssetDatabase.LoadAllAssetsAtPath("ProjectSettings/QualitySettings.asset")[0]);
            var levels=quality.FindProperty("m_QualitySettings");
            for(int i=0;i<levels.arraySize;i++)if(levels.GetArrayElementAtIndex(i).FindPropertyRelative("name").stringValue=="PC")
                levels.GetArrayElementAtIndex(i).FindPropertyRelative("realtimeReflectionProbes").boolValue=true;
            quality.ApplyModifiedPropertiesWithoutUndo();AssetDatabase.SaveAssets();
        }
        public static void Build(){Prepare();ProjectSetup.ConfigureAndBuild();Debug.Log("SURFACE_DETAIL_BUILD_OK");}
    }
}
