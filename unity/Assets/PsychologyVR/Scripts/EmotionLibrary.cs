using System;
using UnityEngine;

namespace PsychologyVR
{
    [Serializable] public class EmotionShape {public string name;public float weight;}
    [Serializable] public class EmotionPreset
    {
        public string name,label,description;
        public EmotionShape[] shapes;
        public float headPitch,headYaw,torsoPitch,tremble,tears,lookAwayChance,blinkInterval=1;
    }
    [Serializable] public class EmotionAlias {public string name,emotion;}
    [Serializable] public class EmotionCatalog {public int version;public EmotionPreset[] emotions;public EmotionAlias[] aliases;}
    public static class EmotionLibrary
    {
        static EmotionCatalog catalog;
        public static EmotionCatalog Catalog
        {
            get
            {
                if(catalog==null) catalog=JsonUtility.FromJson<EmotionCatalog>(Resources.Load<TextAsset>("EmotionCatalog").text);
                return catalog;
            }
        }
        public static EmotionPreset Find(string name)
        {
            foreach(var alias in Catalog.aliases)if(alias.name==name){name=alias.emotion;break;}
            foreach(var preset in Catalog.emotions)if(preset.name==name)return preset;
            return Catalog.emotions[0];
        }
    }
}
