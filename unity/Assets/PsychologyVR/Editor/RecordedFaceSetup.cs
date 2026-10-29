using System;
using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;

namespace PsychologyVR.Editor
{
    public static class RecordedFaceSetup
    {
        const string Output = "Assets/PsychologyVR/Generated/LiveLink";
        [MenuItem("Psychology VR/Build recorded facial performance preview")]
        public static void Build()
        {
            if (!Application.isBatchMode && !EditorSceneManager.SaveCurrentModifiedScenesIfUserWantsTo()) return;
            string data = Path.GetFullPath("../docs/generated/livelink-poc/performance.json");
            var take = RecordedFaceTake.Load(data);
            AssetDatabase.Refresh();
            var prefab = AssetDatabase.LoadAssetAtPath<GameObject>("Assets/PsychologyVR/Prefabs/JumperCandidate.prefab");
            if (!prefab) throw new InvalidOperationException("JumperCandidate prefab is required.");
            Directory.CreateDirectory(Output); AssetDatabase.Refresh();
            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            var actor = (GameObject)PrefabUtility.InstantiatePrefab(prefab);
            Bake(take, actor);
            var preview = new GameObject("Recorded facial performance").AddComponent<RecordedFacePreview>();
            preview.character = actor;
            var camera = new GameObject("Portrait camera").AddComponent<Camera>();
            camera.nearClipPlane = .03f; camera.clearFlags = CameraClearFlags.SolidColor;
            camera.backgroundColor = new Color(.10f, .13f, .16f); preview.view = camera;
            var background = new GameObject("Preview background").AddComponent<Camera>();
            background.cullingMask = 0; background.depth = -5;
            background.clearFlags = CameraClearFlags.SolidColor; background.backgroundColor = new Color(.06f, .08f, .10f);
            RenderSettings.ambientMode = AmbientMode.Flat; RenderSettings.ambientLight = new Color(.48f, .48f, .48f);
            var key = new GameObject("Key").AddComponent<Light>();
            key.type = LightType.Directional; key.intensity = 1.5f; key.transform.rotation = Quaternion.Euler(30, -25, 0);
            var fill = new GameObject("Fill").AddComponent<Light>();
            fill.type = LightType.Directional; fill.intensity = .65f; fill.transform.rotation = Quaternion.Euler(20, 145, 0);
            string path = Output + "/RecordedFacePreview.unity";
            EditorSceneManager.SaveScene(scene, path); AssetDatabase.SaveAssets();
            var report = BuildPipeline.BuildPlayer(new BuildPlayerOptions {
                scenes = new[] { path }, locationPathName = "Builds/LiveLinkPreview/LiveLinkPreview.exe",
                target = BuildTarget.StandaloneWindows64, options = BuildOptions.Development });
            if (report.summary.result != UnityEditor.Build.Reporting.BuildResult.Succeeded)
                throw new Exception("Recorded face preview build failed: " + report.summary.result);
            Debug.Log("RECORDED_FACE_BUILD_OK");
        }

        static void Bake(RecordedFaceTake take, GameObject actor)
        {
            var source = new Dictionary<string, float>(); var targets = new Dictionary<string, float>();
            var curves = new Dictionary<string, AnimationCurve>();
            var available = new HashSet<string>();
            foreach (var renderer in actor.GetComponentsInChildren<SkinnedMeshRenderer>())
                for (int i = 0; i < renderer.sharedMesh.blendShapeCount; i++)
                    available.Add(RecordedFaceMapping.ShapeName(renderer.sharedMesh.GetBlendShapeName(i)));
            foreach (var channel in RecordedFaceMapping.Channels)
            {
                if (!available.Contains(channel.target)) throw new InvalidDataException("Missing CC shape: " + channel.target);
                if (Array.IndexOf(take.names, channel.source) < 0) throw new InvalidDataException("Missing source channel: " + channel.source);
                curves[channel.target] = new AnimationCurve();
            }
            foreach (var frame in take.frames)
            {
                take.Sample(frame.time, source); RecordedFaceMapping.Map(source, targets, 1);
                foreach (var entry in curves) entry.Value.AddKey(frame.time, targets[entry.Key] * 100);
            }
            foreach (var curve in curves.Values)
                for (int i = 0; i < curve.length; i++)
                {
                    AnimationUtility.SetKeyLeftTangentMode(curve, i, AnimationUtility.TangentMode.Linear);
                    AnimationUtility.SetKeyRightTangentMode(curve, i, AnimationUtility.TangentMode.Linear);
                }
            var clip = new AnimationClip { name = "MySlate_1_VideoDerived_Face", frameRate = take.fps };
            int bindings = 0;
            foreach (var mesh in actor.GetComponentsInChildren<SkinnedMeshRenderer>())
                for (int i = 0; i < mesh.sharedMesh.blendShapeCount; i++)
                {
                    string fullName = mesh.sharedMesh.GetBlendShapeName(i), name = RecordedFaceMapping.ShapeName(fullName);
                    if (!curves.TryGetValue(name, out var curve)) continue;
                    if ((mesh.name.Contains("Mustache") || mesh.name.Contains("Soul_Patch")) && name == "Jaw_Open") continue;
                    AnimationUtility.SetEditorCurve(clip, EditorCurveBinding.FloatCurve(
                        AnimationUtility.CalculateTransformPath(mesh.transform, actor.transform), typeof(SkinnedMeshRenderer),
                        "blendShape." + fullName), curve); bindings++;
                }
            Transform jaw = null, head = null, eye = null;
            foreach (var t in actor.GetComponentsInChildren<Transform>())
            { if (t.name == "CC_Base_JawRoot") jaw = t; if (t.name == "CC_Base_Head") head = t; if (t.name == "CC_Base_L_Eye") eye = t; }
            if (!jaw || !head || !eye) throw new InvalidDataException("Missing facial bones.");
            // Same jaw coordination used by the supplied CC rig and the live preview.
            Vector3 forward = eye.position - head.position; forward.y = 0;
            // Average both eyes to remove the left-eye horizontal offset.
            foreach (var t in actor.GetComponentsInChildren<Transform>())
                if (t.name == "CC_Base_R_Eye") { forward = (eye.position + t.position) * .5f - head.position; forward.y = 0; }
            forward.Normalize(); var axis = jaw.InverseTransformDirection(Vector3.Cross(Vector3.up, forward));
            var rest = jaw.localRotation; var rotations = new[] { new AnimationCurve(), new AnimationCurve(), new AnimationCurve(), new AnimationCurve() };
            var headBinding = new RecordedHeadBinding(head, forward);
            var headRotations = new[] { new AnimationCurve(), new AnimationCurve(), new AnimationCurve(), new AnimationCurve() };
            foreach (var frame in take.frames)
            {
                take.Sample(frame.time, source); RecordedFaceMapping.Map(source, targets, 1);
                var q = rest * Quaternion.AngleAxis(targets["Jaw_Open"] * 25, axis);
                for (int j = 0; j < 4; j++) rotations[j].AddKey(frame.time, q[j]);
                var h = headBinding.Rotation(take.SampleHead(frame.time));
                for (int j = 0; j < 4; j++) headRotations[j].AddKey(frame.time, h[j]);
            }
            for (int j = 0; j < 4; j++)
            {
                AnimationUtility.SetEditorCurve(clip, EditorCurveBinding.FloatCurve(
                    AnimationUtility.CalculateTransformPath(jaw, actor.transform), typeof(Transform), "m_LocalRotation." + "xyzw"[j]), rotations[j]);
                if (take.headPoseVersion > 0)
                {
                    for (int k = 0; k < headRotations[j].length; k++)
                    {
                        AnimationUtility.SetKeyLeftTangentMode(headRotations[j], k, AnimationUtility.TangentMode.Linear);
                        AnimationUtility.SetKeyRightTangentMode(headRotations[j], k, AnimationUtility.TangentMode.Linear);
                    }
                    AnimationUtility.SetEditorCurve(clip, EditorCurveBinding.FloatCurve(
                        AnimationUtility.CalculateTransformPath(head, actor.transform), typeof(Transform), "m_LocalRotation." + "xyzw"[j]), headRotations[j]);
                }
            }
            clip.EnsureQuaternionContinuity();
            string output = Output + "/MySlate_1_Face.anim";
            var existing = AssetDatabase.LoadAssetAtPath<AnimationClip>(output);
            if (existing) { EditorUtility.CopySerialized(clip, existing); UnityEngine.Object.DestroyImmediate(clip); clip = existing; }
            else AssetDatabase.CreateAsset(clip, output);
            if (bindings < 100 || clip.length < 9) throw new InvalidDataException("Incomplete animation export.");
            // Check a sampled baked curve against the input after retargeting, including the jaw bone.
            var firstMesh = actor.GetComponentsInChildren<SkinnedMeshRenderer>();
            float sampleTime = take.frames[take.frames.Length / 2].time;
            take.Sample(sampleTime, source); RecordedFaceMapping.Map(source, targets, 1);
            clip.SampleAnimation(actor, sampleTime);
            float headError = Quaternion.Angle(head.localRotation, headBinding.Rotation(take.SampleHead(sampleTime)));
            float maxError = 0;
            foreach (var mesh in firstMesh)
                for (int i = 0; i < mesh.sharedMesh.blendShapeCount; i++)
                {
                    string name = RecordedFaceMapping.ShapeName(mesh.sharedMesh.GetBlendShapeName(i));
                    if (curves.ContainsKey(name)) maxError = Mathf.Max(maxError, Mathf.Abs(mesh.GetBlendShapeWeight(i) - RecordedFaceMapping.MeshValue(mesh.name, name, targets)));
                    mesh.SetBlendShapeWeight(i, 0);
                }
            jaw.localRotation = rest;
            head.localRotation = headBinding.rest;
            if (maxError > .05f) throw new InvalidDataException("Baked animation differs from retargeted sample: " + maxError);
            // Test interpolation as well as keyed poses, and require rest restoration at zero strength.
            foreach (float fraction in new[] { 0f, .137f, .503f, .777f, .99f })
            {
                float time = fraction * (take.duration - 1 / take.fps);
                clip.SampleAnimation(actor, time);
                headError = Mathf.Max(headError, Quaternion.Angle(head.localRotation, headBinding.Rotation(take.SampleHead(time))));
            }
            if (headError > .1f) throw new InvalidDataException("Baked head rotation differs from preview: " + headError);
            headBinding.Apply(take.SampleHead(sampleTime, 0));
            if (Quaternion.Angle(head.localRotation, headBinding.rest) > .01f) throw new InvalidDataException("Head rest restoration failed.");
            jaw.localRotation = rest;
            foreach (var mesh in firstMesh)
                for (int i = 0; i < mesh.sharedMesh.blendShapeCount; i++) mesh.SetBlendShapeWeight(i, 0);
            File.WriteAllText("../docs/generated/livelink-poc/unity-bake-report.json",
                "{\"meshCurveBindings\":" + bindings + ",\"mappedControls\":" + curves.Count +
                ",\"frames\":" + take.frames.Length + ",\"sampleVerified\":true,\"headRotationVerified\":true,\"headCurveBindings\":4}");
            Debug.Log("RECORDED_FACE_BAKE_OK bindings=" + bindings + " maxError=" + maxError + " headErrorDegrees=" + headError);
        }
    }
}
