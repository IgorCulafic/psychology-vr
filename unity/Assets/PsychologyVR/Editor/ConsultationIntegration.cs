using System;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace PsychologyVR.Editor
{
    public static class ConsultationIntegration
    {
        const string Root="Assets/PsychologyVR";
        [MenuItem("Psychology VR/Integrate jumper and player and build")]
        public static void Build()
        {
            AssetDatabase.Refresh();
            var jumper=AssetDatabase.LoadAssetAtPath<GameObject>(Root+"/Prefabs/JumperCandidate.prefab");
            if(!jumper)throw new InvalidOperationException("Prepare the jumper candidate prefab first.");
            var player=UnityEngine.Object.Instantiate(jumper);player.name="Seated player avatar";
            string folder=Root+"/Art/Characters/Player";Directory.CreateDirectory(folder);AssetDatabase.Refresh();
            int removed=0;
            foreach(var renderer in player.GetComponentsInChildren<SkinnedMeshRenderer>())
            {
                bool clothing=renderer.name=="Boxers"||renderer.name=="Slacks"||renderer.name=="Men_s_sweater_2"||renderer.name=="hoshoes_10652_Shape";
                if(renderer.name!="CC_Base_Body" && !clothing){UnityEngine.Object.DestroyImmediate(renderer.gameObject);continue;}
                renderer.updateWhenOffscreen=true;
                if(renderer.name=="CC_Base_Body")
                {
                    var mesh=UnityEngine.Object.Instantiate(renderer.sharedMesh);mesh.name="Player body without head";mesh.ClearBlendShapes();
                    for(int s=0;s<mesh.subMeshCount;s++)
                    {
                        string name=renderer.sharedMaterials[s].name;
                        if(name.Contains("Skin_Head")||name.Contains("Eyelash")){removed+=mesh.GetTriangles(s).Length/3;mesh.SetTriangles(Array.Empty<int>(),s);}
                    }
                    string path=folder+"/HeadlessBody.asset";var existing=AssetDatabase.LoadAssetAtPath<Mesh>(path);
                    if(existing){EditorUtility.CopySerialized(mesh,existing);UnityEngine.Object.DestroyImmediate(mesh);mesh=existing;}else AssetDatabase.CreateAsset(mesh,path);
                    renderer.sharedMesh=mesh;
                }
                if(renderer.name=="Men_s_sweater_2")
                {
                    var materials=renderer.sharedMaterials;
                    for(int i=0;i<materials.Length;i++)
                    {
                        string path=folder+"/Sweater_"+i+".mat";var material=AssetDatabase.LoadAssetAtPath<Material>(path);
                        if(!material){material=new Material(materials[i]);AssetDatabase.CreateAsset(material,path);}
                        material.SetColor("_BaseColor",new Color(.38f,.55f,.63f));EditorUtility.SetDirty(material);materials[i]=material;
                    }
                    renderer.sharedMaterials=materials;
                }
            }
            var animator=player.GetComponent<Animator>();if(animator)UnityEngine.Object.DestroyImmediate(animator);
            var playerPrefab=PrefabUtility.SaveAsPrefabAsset(player,Root+"/Prefabs/SeatedPlayer.prefab");UnityEngine.Object.DestroyImmediate(player);
            if(removed<100)throw new InvalidOperationException("Player head removal failed.");
            var scene=EditorSceneManager.OpenScene(Root+"/Scenes/Consultation.unity");
            var session=UnityEngine.Object.FindFirstObjectByType<PrototypeSession>();session.characterPrefab=jumper;session.seatedClip=null;session.playerPrefab=playerPrefab;
            EditorUtility.SetDirty(session);EditorSceneManager.SaveScene(scene);AssetDatabase.SaveAssets();
            File.WriteAllText("../docs/generated/player-avatar-import.json","{\"removedHeadTriangles\":"+removed+",\"source\":\"JumperCandidate\"}");
            ProjectSetup.ConfigureAndBuild();Debug.Log("CONSULTATION_INTEGRATION_BUILD_OK headTrianglesRemoved="+removed);
        }
    }
}
