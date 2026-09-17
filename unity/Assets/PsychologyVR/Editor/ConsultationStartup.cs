using System;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace PsychologyVR.Editor
{
    [InitializeOnLoad]
    public static class ConsultationStartup
    {
        const string ScenePath = "Assets/PsychologyVR/Scenes/Consultation.unity";

        static ConsultationStartup()
        {
            EditorApplication.delayCall += Initialize;
        }

        static void Initialize()
        {
            if (Application.isBatchMode || EditorApplication.isPlayingOrWillChangePlaymode) return;
            if (EditorApplication.isCompiling || EditorApplication.isUpdating)
            {
                EditorApplication.delayCall += Initialize;
                return;
            }

            var scene = AssetDatabase.LoadAssetAtPath<SceneAsset>(ScenePath);
            if (!scene) return;
            EditorSceneManager.playModeStartScene = scene;

            // Keep existing work intact; only replace Unity's clean startup scene.
            var active = SceneManager.GetActiveScene();
            if (SceneManager.sceneCount == 1 && string.IsNullOrEmpty(active.path) && !active.isDirty)
                EditorSceneManager.OpenScene(ScenePath);
            Debug.Log("Consultation ready. Press Play to open the room and character menu.");
        }

        [MenuItem("Psychology VR/Open consultation scene", false, 0)]
        public static void OpenConsultation()
        {
            if (!EditorSceneManager.SaveCurrentModifiedScenesIfUserWantsTo()) return;
            EditorSceneManager.OpenScene(ScenePath);
            EditorSceneManager.playModeStartScene = AssetDatabase.LoadAssetAtPath<SceneAsset>(ScenePath);
        }

        [MenuItem("Psychology VR/Open consultation scene", true)]
        static bool CanOpenConsultation() => !EditorApplication.isPlayingOrWillChangePlaymode;

        [MenuItem("Psychology VR/Play the currently open scene", false, 1)]
        static void PlayCurrentScene()
        {
            // Allows the separate character audition scene to run independently.
            EditorSceneManager.playModeStartScene = null;
            EditorApplication.isPlaying = true;
        }

        [MenuItem("Psychology VR/Play the currently open scene", true)]
        static bool CanPlayCurrentScene() => !EditorApplication.isPlayingOrWillChangePlaymode;

        public static void Validate()
        {
            var scene = EditorSceneManager.OpenScene(ScenePath);
            var session = UnityEngine.Object.FindFirstObjectByType<PrototypeSession>();
            if (!scene.IsValid() || !session || !session.characterPrefab || !session.playerPrefab || !session.environmentPrefab)
                throw new InvalidOperationException("Consultation scene or its required prefab references are missing.");
            EditorSceneManager.playModeStartScene = AssetDatabase.LoadAssetAtPath<SceneAsset>(ScenePath);
            if (!EditorSceneManager.playModeStartScene)
                throw new InvalidOperationException("Consultation could not be assigned as the Play Mode scene.");
            Debug.Log("CONSULTATION_STARTUP_OK: scene, character, player, room and Play Mode scene verified.");
        }
    }
}
