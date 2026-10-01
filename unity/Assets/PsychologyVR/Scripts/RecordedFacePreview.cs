using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;

namespace PsychologyVR
{
    public sealed class RecordedFacePreview : MonoBehaviour
    {
        public GameObject character;
        public Camera view;
        readonly Dictionary<string, float> source = new Dictionary<string, float>();
        readonly Dictionary<string, float> targets = new Dictionary<string, float>();
        RecordedFaceTake take;
        SkinnedMeshRenderer[] meshes;
        Transform jaw;
        Quaternion jawRest;
        Vector3 jawAxis;
        RecordedHeadBinding headBinding;
        float headStrength = 1;
        Texture2D reference;
        RenderTexture portrait;
        string folder, error;
        float clock, intensity = 1;
        int referenceFrame = -1;
        bool playing = true, renderMode;

        IEnumerator Start()
        {
            folder = Path.GetFullPath(Path.Combine(Application.dataPath,
                Application.isEditor ? "../../docs/generated/livelink-poc" : "../../../../docs/generated/livelink-poc"));
            var args = Environment.GetCommandLineArgs();
            int at = Array.IndexOf(args, "--data");
            if (at >= 0 && at + 1 < args.Length) folder = Path.GetFullPath(args[at + 1]);
            renderMode = Array.IndexOf(args, "--render") >= 0;
            try { take = RecordedFaceTake.Load(Path.Combine(folder, "performance.json")); }
            catch (Exception e) { error = e.Message; Debug.LogError(e); yield break; }
            foreach (var a in character.GetComponentsInChildren<Animator>()) a.enabled = false;
            CandidateSeatedPose.Apply(character);
            meshes = character.GetComponentsInChildren<SkinnedMeshRenderer>();
            Transform head = null, leftEye = null, rightEye = null;
            foreach (var t in character.GetComponentsInChildren<Transform>())
            {
                if (t.name == "CC_Base_Head") head = t;
                if (t.name == "CC_Base_JawRoot") jaw = t;
                if (t.name == "CC_Base_L_Eye") leftEye = t;
                if (t.name == "CC_Base_R_Eye") rightEye = t;
            }
            if (!head || !jaw || !leftEye || !rightEye)
            { error = "The preview requires the supplied Jumper CC rig."; Debug.LogError(error); yield break; }
            Vector3 eyes = (leftEye.position + rightEye.position) * .5f;
            Vector3 forward = eyes - head.position; forward.y = 0; forward.Normalize();
            jawRest = jaw.localRotation;
            jawAxis = jaw.InverseTransformDirection(Vector3.Cross(Vector3.up, forward));
            headBinding = new RecordedHeadBinding(head, forward);
            Vector3 focus = eyes - Vector3.up * .035f;
            view.transform.position = focus + forward * .56f;
            view.transform.LookAt(focus); view.fieldOfView = 33;
            portrait = new RenderTexture(600, 600, 24);
            view.targetTexture = portrait;
            reference = new Texture2D(2, 2);
            Debug.Log("RECORDED_FACE_READY frames=" + take.frames.Length + " method=" + take.method);
            if (renderMode) yield return RenderTake();
        }
        void Update()
        {
            if (take == null || meshes == null || error != null || renderMode) return;
            if (playing) clock = (clock + Time.deltaTime) % take.duration;
            Apply(clock);
        }
        void Apply(float time)
        {
            take.Sample(time, source);
            RecordedFaceMapping.Map(source, targets, intensity);
            foreach (var mesh in meshes)
            {
                if (!mesh.sharedMesh) continue;
                for (int i = 0; i < mesh.sharedMesh.blendShapeCount; i++)
                    mesh.SetBlendShapeWeight(i, RecordedFaceMapping.MeshValue(mesh.name,
                        RecordedFaceMapping.ShapeName(mesh.sharedMesh.GetBlendShapeName(i)), targets));
            }
            targets.TryGetValue("Jaw_Open", out float opening);
            jaw.localRotation = jawRest * Quaternion.AngleAxis(opening * 25, jawAxis);
            headBinding.Apply(take.SampleHead(time, headStrength));
            int frame = Mathf.Clamp(Mathf.FloorToInt(time * take.fps), 0, take.frames.Length - 1);
            if (frame != referenceFrame)
            {
                string path = Path.Combine(folder, "face", frame.ToString("D5") + ".jpg");
                if (File.Exists(path)) reference.LoadImage(File.ReadAllBytes(path));
                referenceFrame = frame;
            }
        }
        void OnGUI()
        {
            GUI.skin.label.fontSize = 18;
            GUI.skin.button.fontSize = 17;
            if (error != null) { GUI.Label(new Rect(20, 20, Screen.width - 40, 100), error); return; }
            if (take == null || reference == null) return;
            float width = Mathf.Min((Screen.width - 60) / 2f, Screen.height - 190);
            float left = (Screen.width - width * 2 - 20) / 2;
            GUI.Label(new Rect(left, 12, 1000, 30), "Acted facial animation / Unity proof of concept");
            GUI.DrawTexture(new Rect(left, 80, width, width), reference, ScaleMode.ScaleToFit);
            GUI.DrawTexture(new Rect(left + width + 20, 80, width, width), portrait, ScaleMode.ScaleToFit);
            GUI.Label(new Rect(left, 48, width, 28), "Your recording (face crop)");
            GUI.Label(new Rect(left + width + 20, 48, width, 28), "Jumper / video-derived facial motion");
            float y = width + 95;
            if (GUI.Button(new Rect(left, y, 100, 32), playing ? "Pause" : "Play")) playing = !playing;
            if (GUI.Button(new Rect(left + 110, y, 100, 32), "Restart")) { clock = 0; Apply(clock); }
            GUI.Label(new Rect(left + 225, y, 200, 32), clock.ToString("F2") + " / " + take.duration.ToString("F2") + " s");
            float value = GUI.HorizontalSlider(new Rect(left + 420, y + 10, width * 2 - 420, 20), clock, 0, take.duration);
            if (Mathf.Abs(value - clock) > .001f) { clock = value; playing = false; Apply(clock); }
            GUI.Label(new Rect(left, y + 42, 190, 28), "Intensity " + intensity.ToString("F2"));
            intensity = GUI.HorizontalSlider(new Rect(left + 180, y + 51, 240, 20), intensity, 0, 1.5f);
            GUI.Label(new Rect(left + 450, y + 42, 190, 28), "Head motion " + headStrength.ToString("F2"));
            headStrength = GUI.HorizontalSlider(new Rect(left + 630, y + 51, 200, 20), headStrength, 0, 1);
            GUI.Label(new Rect(left + 850, y + 42, 350, 50), "Body fixed / silent preview");
        }
        IEnumerator RenderTake()
        {
            string output = Path.Combine(folder, "unity-frames"); Directory.CreateDirectory(output);
            var pixels = new Texture2D(600, 600, TextureFormat.RGB24, false);
            var rt = new RenderTexture(600, 600, 24);
            for (int i = 0; i < take.frames.Length; i++)
            {
                clock = i / take.fps; Apply(clock);
                yield return new WaitForEndOfFrame();
                RenderPipeline.SubmitRenderRequest(view, new UniversalRenderPipeline.SingleCameraRequest { destination = rt });
                RenderTexture.active = rt; pixels.ReadPixels(new Rect(0, 0, 600, 600), 0, 0); pixels.Apply(); RenderTexture.active = null;
                File.WriteAllBytes(Path.Combine(output, i.ToString("D5") + ".jpg"), pixels.EncodeToJPG(94));
            }
            Debug.Log("RECORDED_FACE_RENDER_OK frames=" + take.frames.Length);
            rt.Release(); Destroy(pixels); Application.Quit();
        }
        void OnDestroy()
        {
            if (portrait) portrait.Release();
            if (reference) Destroy(reference);
        }
    }
}
