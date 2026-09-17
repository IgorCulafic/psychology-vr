using System;
using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEngine;

namespace PsychologyVR.Editor
{
    public static class ForearmRegression
    {
        [Serializable] class Report
        {
            public bool passed;
            public int cases;
            public float helperAngle,helperShift,vertexDrift,handDrift;
        }
        static Transform Bone(GameObject actor,string name)
        {
            foreach(var bone in actor.GetComponentsInChildren<Transform>())if(bone.name=="CC_Base_"+name)return bone;
            throw new Exception("Missing bone "+name);
        }
        static List<Vector3[]> Skin(SkinnedMeshRenderer[] renderers)
        {
            var result=new List<Vector3[]>();var mesh=new Mesh();
            try {foreach(var renderer in renderers){renderer.BakeMesh(mesh);result.Add(mesh.vertices);}}
            finally {UnityEngine.Object.DestroyImmediate(mesh);}
            return result;
        }
        public static void Run()
        {
            var report=new Report();
            foreach(string sideName in new[]{"L","R"})
            {
                var prefab=AssetDatabase.LoadAssetAtPath<GameObject>("Assets/PsychologyVR/Prefabs/JumperCandidate.prefab");
                var actor=UnityEngine.Object.Instantiate(prefab);
                try
                {
                    CandidateSeatedPose.Apply(actor);var root=actor.transform;
                    var upper=Bone(actor,sideName+"_Upperarm");var lower=Bone(actor,sideName+"_Forearm");var hand=Bone(actor,sideName+"_Hand");
                    var middle=Bone(actor,sideName+"_Mid1");var index=Bone(actor,sideName+"_Index1");var pinky=Bone(actor,sideName+"_Pinky1");
                    var helpers=new[]{Bone(actor,sideName+"_ForearmTwist01"),Bone(actor,sideName+"_ForearmTwist02"),Bone(actor,sideName+"_ElbowShareBone")};
                    Vector3 palm=Vector3.Cross(index.position-hand.position,pinky.position-hand.position).normalized;
                    if(Vector3.Dot(palm,root.up)>0)palm=-palm;
                    float side=Mathf.Sign(root.InverseTransformPoint(upper.position).x);
                    var solver=new ArmJointMotion(upper,lower,hand,hand.InverseTransformDirection((middle.position-hand.position).normalized),hand.InverseTransformDirection(palm),side);
                    var renderers=actor.GetComponentsInChildren<SkinnedMeshRenderer>();
                    foreach(var position in new[]{new Vector3(side*.12f,.65f,.23f),new Vector3(side*.28f,.92f,.40f),new Vector3(side*.10f,1.18f,.22f)})
                    {
                        Vector3 target=root.TransformPoint(position),pole=root.right*side*.4f-root.up+root.forward*.12f;
                        Vector3 restFinger=root.forward+root.right*side*.08f;
                        solver.Solve(target,pole,restFinger,-root.up,root.forward,root.up,.8f,.15f);
                        var rotations=new Quaternion[3];var positions=new Vector3[3];
                        for(int i=0;i<3;i++){rotations[i]=helpers[i].rotation;positions[i]=helpers[i].position;}
                        Vector3 wrist=hand.position;var skin=Skin(renderers);
                        for(int pass=0;pass<16;pass++)
                        {
                            // Contact iterations freeze the animation clock. Solving
                            // the same target again must not deform the forearm again.
                            solver.Solve(target,pole,restFinger,-root.up,root.forward,root.up,.8f,0);
                            for(int i=0;i<3;i++)
                            {
                                report.helperAngle=Mathf.Max(report.helperAngle,Quaternion.Angle(rotations[i],helpers[i].rotation));
                                report.helperShift=Mathf.Max(report.helperShift,Vector3.Distance(positions[i],helpers[i].position));
                            }
                        }
                        var after=Skin(renderers);
                        for(int r=0;r<skin.Count;r++)for(int v=0;v<skin[r].Length;v++)report.vertexDrift=Mathf.Max(report.vertexDrift,Vector3.Distance(skin[r][v],after[r][v]));
                        report.handDrift=Mathf.Max(report.handDrift,Vector3.Distance(wrist,hand.position));report.cases++;
                    }
                }
                finally {UnityEngine.Object.DestroyImmediate(actor);}
            }
            report.passed=report.helperAngle<.1f&&report.helperShift<.00001f&&report.vertexDrift<.00002f&&report.handDrift<.00001f;
            Directory.CreateDirectory("../docs/generated");
            File.WriteAllText("../docs/generated/forearm-regression.json",JsonUtility.ToJson(report,true));
            Debug.Log("FOREARM_REGRESSION "+JsonUtility.ToJson(report));
            if(!report.passed)throw new Exception("Repeated contact solves change forearm helpers or skinned vertices.");
            Debug.Log("FOREARM_REGRESSION_OK");
        }
        public static void CheckAndBuild(){Run();BodyContactChecks.Run();ProjectSetup.BuildWindows();}
    }
}
