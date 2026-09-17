using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
namespace PsychologyVR.Editor
{
    public static class MenuSetup
    {
        public static void SyncCatalog()
        {
            const string root="Assets/PsychologyVR";
            var catalog=JsonUtility.FromJson<ScenarioCatalog>(File.ReadAllText("../characters/catalog.json"));
            File.WriteAllText(root+"/Resources/ScenarioCatalog.json",JsonUtility.ToJson(catalog,true));
            Directory.CreateDirectory(root+"/Resources/Menu");
            string portrait="../docs/generated/consultation-integration/alex-unity-neutral.png";
            if(File.Exists(portrait))File.Copy(portrait,root+"/Resources/Menu/alex.png",true);
            string original="../docs/generated/alex-unity-neutral.png";
            if(File.Exists(original))File.Copy(original,root+"/Resources/Menu/original-alex.png",true);
            AssetDatabase.Refresh();
            var texture=AssetImporter.GetAtPath(root+"/Resources/Menu/alex.png") as TextureImporter;
            if(texture && texture.maxTextureSize!=1024){texture.maxTextureSize=1024;texture.SaveAndReimport();}
        }
        public static void Prepare()
        {
            SyncCatalog();const string root="Assets/PsychologyVR";
            var scene=EditorSceneManager.OpenScene(root+"/Scenes/Consultation.unity");
            var session=Object.FindFirstObjectByType<PrototypeSession>();
            AssignAppearances(session);
            EditorUtility.SetDirty(session);EditorSceneManager.SaveScene(scene);AssetDatabase.SaveAssets();
        }
        public static void AssignAppearances(PrototypeSession session)
        {
            if(session.appearances!=null&&session.appearances.Length>0)return;
            const string root="Assets/PsychologyVR";
            var clip=AssetDatabase.LoadAllAssetsAtPath(root+"/Art/Characters/Alex/Alex.fbx").OfType<AnimationClip>().First(c=>!c.name.StartsWith("__")&&c.name.ToLowerInvariant().EndsWith("sit"));
            session.appearances=new[]{
                new CharacterAppearance{id="jumper",label="Jumper",prefab=AssetDatabase.LoadAssetAtPath<GameObject>(root+"/Prefabs/JumperCandidate.prefab")},
                new CharacterAppearance{id="original-alex",label="Original Alex",prefab=AssetDatabase.LoadAssetAtPath<GameObject>(root+"/Prefabs/Alex.prefab"),seatedClip=clip}
            };
        }
        [MenuItem("Psychology VR/Build menu and character library")]
        public static void Build(){Prepare();ProjectSetup.ConfigureAndBuild();Debug.Log("MENU_BUILD_OK");}
    }
}
