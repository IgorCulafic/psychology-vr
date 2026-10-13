using System;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace PsychologyVR.Editor
{
    [InitializeOnLoad]
    public static class MetaHumanSeatedIdleSetup
    {
        const string Root="Assets/PsychologyVR/Art/MetaHumans/ivan/";
        [Serializable] public sealed class BonePose {public string name,parent;public Vector3 p;public Quaternion q;}
        [Serializable] public sealed class RestPose {public BonePose[] rest;}
        [Serializable] public sealed class Frame {public float time;public BonePose[] bones;}
        [Serializable] public sealed class Recording {public float fps;public Frame[] frames;}
        [Serializable] public sealed class SeatFrame {public float time;public Vector3 p;}
        [Serializable] public sealed class SeatMotion {public SeatFrame[] frames;}

        static MetaHumanSeatedIdleSetup()
        {
            if(Array.IndexOf(Environment.GetCommandLineArgs(),"--seated-idle-check")>=0)
            {
                EditorApplication.update+=FinishPreview;
                Application.logMessageReceived+=(message,stack,type)=>
                {
                    if(message.StartsWith("METAHUMAN_CHECK_FAILED")||(type==LogType.Exception&&stack.Contains("PsychologyVR")))EditorApplication.Exit(2);
                };
            }
        }
        public static void Preview()
        {
            EditorSceneManager.OpenScene("Assets/PsychologyVR/Scenes/Consultation.unity");
            EditorApplication.isPaused=false;
            EditorApplication.isPlaying=true;
        }
        static void FinishPreview()
        {
            if(!EditorApplication.isPlaying)return;
            if(EditorApplication.isPaused)
            {
                Debug.Log("METAHUMAN_IDLE_EDITOR_PAUSE: resuming the automated preview.");
                EditorApplication.isPaused=false;
            }
            EditorApplication.QueuePlayerLoopUpdate();
            string path=Path.Combine(Argument("--capture-path"),"idle-report.json");
            if(File.Exists(path))
            {
                bool passed=JsonUtility.FromJson<MetaHumanIdlePreview.Report>(File.ReadAllText(path)).passed;
                if(passed&&Array.IndexOf(Environment.GetCommandLineArgs(),"--wardrobe-check")>=0)IvanWardrobeSetup.Validate();
                EditorApplication.Exit(passed?0:2);
            }
        }

        public static void ImportVideo()
        {
            var recording=JsonUtility.FromJson<Recording>(File.ReadAllText(Argument("--native-idle-source")));
            var actor=PrefabUtility.LoadPrefabContents(Root+"Character.prefab");
            try
            {
                var rig=actor.GetComponent<MetaHumanJointRig>();
                var bones=rig.bodyObject.GetComponentsInChildren<Transform>().ToDictionary(t=>t.name);
                var clip=new AnimationClip{name="SeatedVideo5799",legacy=true,frameRate=recording.fps,wrapMode=WrapMode.Loop};
                int retained=0;
                for(int i=0;i<recording.frames[0].bones.Length;i++)
                {
                    string name=recording.frames[0].bones[i].name;
                    var bone=bones[name];
                    string path=AnimationUtility.CalculateTransformPath(bone,rig.bodyObject.transform);
                    var values=recording.frames.Select(f=>f.bones[i].q).ToArray();
                    for(int k=1;k<values.Length;k++)if(Quaternion.Dot(values[k-1],values[k])<0)
                        values[k]=new Quaternion(-values[k].x,-values[k].y,-values[k].z,-values[k].w);
                    var ids=Enumerable.Range(0,values.Length).ToArray();retained+=ids.Length;
                    for(int axis=0;axis<4;axis++)
                    {
                        var curve=new AnimationCurve(ids.Select(k=>new Keyframe(recording.frames[k].time,values[k][axis])).ToArray());
                        LinearTangents(curve);
                        clip.SetCurve(path,typeof(Transform),"localRotation."+"xyzw"[axis],curve);
                    }
                    if(name=="pelvis")for(int axis=0;axis<3;axis++)
                    {
                        var curve=new AnimationCurve(recording.frames.Select(f=>new Keyframe(f.time,f.bones[i].p[axis])).ToArray());
                        LinearTangents(curve);clip.SetCurve(path,typeof(Transform),"localPosition."+"xyz"[axis],curve);
                    }
                }
                string asset=Root+"animations/SeatedVideo5799.anim";
                var restBones=rig.bodyObject.GetComponentsInChildren<Transform>();
                var restP=restBones.Select(t=>t.localPosition).ToArray();var restQ=restBones.Select(t=>t.localRotation).ToArray();
                float maxRotationError=0,maxPositionError=0;string worstRotation="";
                foreach(var frame in recording.frames)
                {
                    clip.SampleAnimation(rig.bodyObject,frame.time);
                    foreach(var pose in frame.bones)
                    {
                        var bone=bones[pose.name];
                        float error=Quaternion.Angle(pose.q,bone.localRotation);
                        if(error>maxRotationError){maxRotationError=error;worstRotation=pose.name+" at "+frame.time+" seconds";}
                        if(pose.name=="pelvis")maxPositionError=Mathf.Max(maxPositionError,Vector3.Distance(pose.p,bone.localPosition));
                    }
                }
                for(int k=0;k<restBones.Length;k++){restBones[k].localPosition=restP[k];restBones[k].localRotation=restQ[k];}
                if(maxRotationError>.15f||maxPositionError>.0001f)
                    throw new InvalidOperationException("Imported video differs from the prepared native poses: "+maxRotationError+" degrees, "+maxPositionError+" m. "+worstRotation);
                var existing=AssetDatabase.LoadAssetAtPath<AnimationClip>(asset);
                if(existing){EditorUtility.CopySerialized(clip,existing);UnityEngine.Object.DestroyImmediate(clip);clip=existing;}
                else AssetDatabase.CreateAsset(clip,asset);
                rig.seatedIdle=clip;PrefabUtility.SaveAsPrefabAsset(actor,Root+"Character.prefab");
                AssetDatabase.SaveAssets();
                Debug.Log("METAHUMAN_VIDEO_IMPORTED duration="+clip.length+" bones="+recording.frames[0].bones.Length+" rotationKeys="+retained+" maxRotationError="+maxRotationError+" maxPositionError="+maxPositionError);
            }
            finally{PrefabUtility.UnloadPrefabContents(actor);}
        }

        static void LinearTangents(AnimationCurve curve)
        {
            var keys=curve.keys;
            for(int k=0;k<keys.Length;k++)
            {
                keys[k].inTangent=k>0?(keys[k].value-keys[k-1].value)/(keys[k].time-keys[k-1].time):0;
                keys[k].outTangent=k+1<keys.Length?(keys[k+1].value-keys[k].value)/(keys[k+1].time-keys[k].time):0;
            }
            // Set once: per-key editor setters rebuild this dense curve repeatedly.
            curve.keys=keys;
            for(int k=0;k+1<keys.Length;k++)
            {
                float time=(keys[k].time+keys[k+1].time)*.5f;
                float fraction=(time-keys[k].time)/(keys[k+1].time-keys[k].time);
                if(Mathf.Abs(curve.Evaluate(time)-Mathf.Lerp(keys[k].value,keys[k+1].value,fraction))>.00001f)
                    throw new InvalidOperationException("Prepared animation curve does not interpolate linearly.");
            }
        }

        public static void ExportRest()
        {
            var actor=UnityEngine.Object.Instantiate(AssetDatabase.LoadAssetAtPath<GameObject>(Root+"Character.prefab"));
            try
            {
                var rig=actor.GetComponent<MetaHumanJointRig>();
                var bones=rig.bodyObject.GetComponentsInChildren<Transform>().Where(t=>t!=rig.bodyObject.transform).ToArray();
                var result=new RestPose{rest=bones.Select(t=>new BonePose{name=t.name,parent=t.parent==rig.bodyObject.transform?"":t.parent.name,p=t.position,q=t.rotation}).ToArray()};
                File.WriteAllText(Argument("--native-rest-output"),JsonUtility.ToJson(result));
                rig.Initialize();
                Debug.Log("METAHUMAN_IDLE_BASELINE pelvis="+bones.First(t=>t.name=="pelvis").position+" left="+bones.First(t=>t.name=="hand_l").position+" right="+bones.First(t=>t.name=="hand_r").position);
            }
            finally{UnityEngine.Object.DestroyImmediate(actor);}
        }

        public static void FitSeat()
        {
            var actor=UnityEngine.Object.Instantiate(AssetDatabase.LoadAssetAtPath<GameObject>(Root+"Character.prefab"));
            var room=UnityEngine.Object.Instantiate(AssetDatabase.LoadAssetAtPath<GameObject>("Assets/PsychologyVR/Prefabs/ConsultationRoom.prefab"));
            var baked=new Mesh();
            try
            {
                actor.transform.SetPositionAndRotation(new Vector3(0,0,1.15f),Quaternion.Euler(0,180,0));
                var rig=actor.GetComponent<MetaHumanJointRig>();var clip=rig.seatedIdle;
                clip.SampleAnimation(rig.bodyObject,0);
                var pelvis=rig.bodyObject.GetComponentsInChildren<Transform>().First(t=>t.name=="pelvis");
                var body=rig.bodyObject.GetComponentsInChildren<Transform>().ToDictionary(t=>t.name);
                var joints=new[]{body["thigh_l"],body["calf_l"],body["thigh_r"],body["calf_r"]};
                var tilt=new Quaternion[2];
                // Bake the knee lowering while preserving the captured shin motion;
                // no runtime IK or fixed feet are introduced.
                for(int side=0;side<2;side++)
                {
                    var thigh=joints[side*2];var calf=joints[side*2+1];var foot=body[side==0?"foot_l":"foot_r"];
                    var direction=calf.position-thigh.position;
                    tilt[side]=Quaternion.FromToRotation(direction,direction+Vector3.up*(.07f-foot.position.y));
                }
                string thighPath=AnimationUtility.CalculateTransformPath(joints[0],rig.bodyObject.transform);
                var times=AnimationUtility.GetEditorCurve(clip,EditorCurveBinding.FloatCurve(thighPath,typeof(Transform),"m_LocalRotation.x")).keys.Select(k=>k.time).ToArray();
                var curves=joints.Select(t=>new[]{new AnimationCurve(),new AnimationCurve(),new AnimationCurve(),new AnimationCurve()}).ToArray();
                var previous=new Quaternion[4];
                foreach(float time in times)
                {
                    clip.SampleAnimation(rig.bodyObject,time);
                    for(int side=0;side<2;side++)
                    {
                        var calf=joints[side*2+1];var rotation=calf.rotation;
                        joints[side*2].rotation=tilt[side]*joints[side*2].rotation;calf.rotation=rotation;
                    }
                    for(int i=0;i<4;i++)
                    {
                        var q=joints[i].localRotation;if(Quaternion.Dot(previous[i],q)<0)q=new Quaternion(-q.x,-q.y,-q.z,-q.w);previous[i]=q;
                        for(int axis=0;axis<4;axis++)curves[i][axis].AddKey(new Keyframe(time,q[axis]));
                    }
                }
                for(int i=0;i<4;i++)for(int axis=0;axis<4;axis++)
                    AnimationUtility.SetEditorCurve(clip,EditorCurveBinding.FloatCurve(AnimationUtility.CalculateTransformPath(joints[i],rig.bodyObject.transform),typeof(Transform),"m_LocalRotation."+"xyzw"[axis]),curves[i][axis]);
                clip.SampleAnimation(rig.bodyObject,0);
                var skin=rig.bodyObject.GetComponentInChildren<SkinnedMeshRenderer>();skin.BakeMesh(baked);
                var visible=baked.triangles.Distinct().Select(i=>skin.transform.TransformPoint(baked.vertices[i])).ToArray();
                float bottom=visible
                    .Where(v=>Mathf.Abs(v.x-pelvis.position.x)<.15f&&Mathf.Abs(v.z-pelvis.position.z)<.12f).Min(v=>v.y);
                var chair=room.GetComponentsInChildren<Transform>().First(t=>t.name=="modern_arm_chair_01"&&t.position.z>0);
                float seat=float.NegativeInfinity;
                foreach(var filter in chair.GetComponentsInChildren<MeshFilter>())
                {
                    var collider=filter.gameObject.AddComponent<MeshCollider>();collider.sharedMesh=filter.sharedMesh;
                    if(collider.Raycast(new Ray(pelvis.position+Vector3.up*.1f,Vector3.down),out var hit,1f))seat=Mathf.Max(seat,hit.point.y);
                }
                if(float.IsNegativeInfinity(seat))throw new InvalidOperationException("No seat surface below Ivan's pelvis.");
                float offset=seat-.005f-bottom;
                Debug.Log("METAHUMAN_SEAT_CONTACT bottom="+bottom+" seat="+seat+" offset="+offset);
                string path=AnimationUtility.CalculateTransformPath(pelvis,rig.bodyObject.transform);
                var binding=EditorCurveBinding.FloatCurve(path,typeof(Transform),"m_LocalPosition.y");
                var curve=AnimationUtility.GetEditorCurve(clip,binding);
                var localOffset=pelvis.parent.InverseTransformVector(Vector3.up*offset);
                for(int axis=0;axis<3;axis++)
                {
                    binding=EditorCurveBinding.FloatCurve(path,typeof(Transform),"m_LocalPosition."+"xyz"[axis]);
                    curve=AnimationUtility.GetEditorCurve(clip,binding);
                    var keys=curve.keys;for(int i=0;i<keys.Length;i++)keys[i].value+=localOffset[axis];
                    curve.keys=keys;AnimationUtility.SetEditorCurve(clip,binding,curve);
                }
                clip.EnsureQuaternionContinuity();
                EditorUtility.SetDirty(clip);AssetDatabase.SaveAssets();
            }
            finally{UnityEngine.Object.DestroyImmediate(baked);UnityEngine.Object.DestroyImmediate(actor);UnityEngine.Object.DestroyImmediate(room);}
        }

        public static void CorrectSeatedMotion()
        {
            var motion=JsonUtility.FromJson<SeatMotion>(File.ReadAllText(Argument("--seat-motion")));
            var actor=UnityEngine.Object.Instantiate(AssetDatabase.LoadAssetAtPath<GameObject>(Root+"Character.prefab"));
            try
            {
                actor.transform.SetPositionAndRotation(new Vector3(0,0,1.15f),Quaternion.Euler(0,180,0));
                var rig=actor.GetComponent<MetaHumanJointRig>();var clip=rig.seatedIdle;
                var bones=rig.bodyObject.GetComponentsInChildren<Transform>().ToDictionary(t=>t.name);
                clip.SampleAnimation(rig.bodyObject,0);
                var pelvis=bones["pelvis"];var root=bones["root"];
                var seat=pelvis.position-Vector3.up*.02f;
                string rootPath=AnimationUtility.CalculateTransformPath(root,rig.bodyObject.transform);
                for(int axis=0;axis<3;axis++)AnimationUtility.SetEditorCurve(clip,EditorCurveBinding.FloatCurve(rootPath,typeof(Transform),"m_LocalPosition."+"xyz"[axis]),null);
                root.localPosition=Vector3.zero;
                string hipPath=AnimationUtility.CalculateTransformPath(pelvis,rig.bodyObject.transform);
                var position=new[]{new AnimationCurve(),new AnimationCurve(),new AnimationCurve()};
                foreach(var frame in motion.frames)
                {
                    var p=pelvis.parent.InverseTransformPoint(seat+actor.transform.TransformVector(frame.p));
                    for(int axis=0;axis<3;axis++)position[axis].AddKey(new Keyframe(frame.time,p[axis]));
                }
                for(int axis=0;axis<3;axis++)AnimationUtility.SetEditorCurve(clip,EditorCurveBinding.FloatCurve(hipPath,typeof(Transform),"m_LocalPosition."+"xyz"[axis]),position[axis]);
                clip.SampleAnimation(rig.bodyObject,0);
                var joints=new[]{bones["spine_01"],bones["thigh_l"],bones["calf_l"],bones["thigh_r"],bones["calf_r"]};
                var tilt=new Quaternion[2];
                for(int side=0;side<2;side++)
                {
                    var thigh=joints[1+side*2];var direction=joints[2+side*2].position-thigh.position;
                    var narrowed=direction;narrowed.x=(side==0?1:-1)*.22f-thigh.position.x;
                    tilt[side]=Quaternion.FromToRotation(direction,narrowed);
                }
                var recline=Quaternion.AngleAxis(-10,actor.transform.right);
                var curves=joints.Select(t=>new[]{new AnimationCurve(),new AnimationCurve(),new AnimationCurve(),new AnimationCurve()}).ToArray();
                var previous=new Quaternion[joints.Length];
                foreach(var frame in motion.frames)
                {
                    clip.SampleAnimation(rig.bodyObject,frame.time);
                    joints[0].rotation=recline*joints[0].rotation;
                    for(int side=0;side<2;side++)
                    {
                        var calf=joints[2+side*2];var rotation=calf.rotation;
                        joints[1+side*2].rotation=tilt[side]*joints[1+side*2].rotation;calf.rotation=rotation;
                    }
                    for(int i=0;i<joints.Length;i++)
                    {
                        var q=joints[i].localRotation;if(Quaternion.Dot(previous[i],q)<0)q=new Quaternion(-q.x,-q.y,-q.z,-q.w);previous[i]=q;
                        for(int axis=0;axis<4;axis++)curves[i][axis].AddKey(new Keyframe(frame.time,q[axis]));
                    }
                }
                for(int i=0;i<joints.Length;i++)for(int axis=0;axis<4;axis++)AnimationUtility.SetEditorCurve(clip,EditorCurveBinding.FloatCurve(AnimationUtility.CalculateTransformPath(joints[i],rig.bodyObject.transform),typeof(Transform),"m_LocalRotation."+"xyzw"[axis]),curves[i][axis]);
                clip.EnsureQuaternionContinuity();EditorUtility.SetDirty(clip);AssetDatabase.SaveAssets();
                Debug.Log("METAHUMAN_SEATED_MOTION_CORRECTED frames="+motion.frames.Length+" seat="+seat);
            }
            finally{UnityEngine.Object.DestroyImmediate(actor);}
        }

        static string Argument(string name)
        {
            var args=Environment.GetCommandLineArgs();int at=Array.IndexOf(args,name);
            if(at<0||at+1>=args.Length)throw new ArgumentException(name+" is required.");
            return Path.GetFullPath(args[at+1]);
        }
    }
}
