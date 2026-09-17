using System;
using UnityEngine;
namespace PsychologyVR
{
    [Serializable] public class ScenarioEntry
    {
        public string id,character_id,character_name,title,summary,focus,avatar_id;
        public int age;
    }
    [Serializable] public class ScenarioCatalog
    {
        public string default_scenario_id;
        public ScenarioEntry[] scenarios;
        public static ScenarioCatalog Load()=>JsonUtility.FromJson<ScenarioCatalog>(Resources.Load<TextAsset>("ScenarioCatalog").text);
        public ScenarioEntry Find(string id)=>Array.Find(scenarios,s=>s.id==id);
    }
    [Serializable] public class CharacterAppearance
    {
        public string id,label;
        public GameObject prefab;
        public AnimationClip seatedClip;
    }
}
