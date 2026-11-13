using System.Linq;
using NUnit.Framework;
using UnityEditor;
using UnityEngine;
using UnityEngine.Rendering;

namespace PsychologyVR.Editor
{
    public class EnvironmentLightmapUvTests
    {
        [TestCase("water_cup", "Torus")]
        [TestCase("potted_plant_01", "potted_plant_01_leaves")]
        [TestCase("potted_plant_02", "potted_plant_02_leaves")]
        public void ImportedMeshesKeepGeometryAndLightmapUvs(string model, string expectedMesh)
        {
            var path="Assets/PsychologyVR/Art/Environment/Models/"+model+".fbx";
            var meshes=AssetDatabase.LoadAllAssetsAtPath(path).OfType<Mesh>().ToArray();
            Assert.That(meshes.Any(mesh=>mesh.name==expectedMesh),Is.True,$"Missing {model}/{expectedMesh}");
            foreach(var mesh in meshes)
            {
                Assert.That(mesh.vertexCount,Is.GreaterThan(0),$"Empty mesh: {model}/{mesh.name}");
                Assert.That(mesh.HasVertexAttribute(VertexAttribute.TexCoord0),Is.True,$"Missing texture UVs: {model}/{mesh.name}");
                Assert.That(mesh.HasVertexAttribute(VertexAttribute.TexCoord1),Is.True,$"Missing lightmap UVs: {model}/{mesh.name}");
            }
        }
    }
}
