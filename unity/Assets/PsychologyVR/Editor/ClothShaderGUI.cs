using System;
using UnityEditor;
using UnityEditor.Rendering.Universal.ShaderGUI;
using UnityEngine;

namespace PsychologyVR.Editor
{
    public sealed class ClothShaderGUI : ShaderGUI
    {
        readonly ShaderGUI lit=(ShaderGUI)Activator.CreateInstance(typeof(LitGUI).Assembly.GetType(
            "UnityEditor.Rendering.Universal.ShaderGUI.LitShader",true));
        public override void OnGUI(MaterialEditor editor,MaterialProperty[] properties)
        {
            lit.OnGUI(editor,properties);
            EditorGUILayout.LabelField("Seated fabric deformation",EditorStyles.boldLabel);
            foreach(string name in new[]{"_ClothFoldDepth","_ClothContactDepth","_ClothFoldRadius","_ClothResponseTime"})
            {var p=FindProperty(name,properties);editor.ShaderProperty(p,p.displayName);}
        }
        public override void ValidateMaterial(Material material)=>lit.ValidateMaterial(material);
        public override void AssignNewShaderToMaterial(Material material,Shader oldShader,Shader newShader)
            =>lit.AssignNewShaderToMaterial(material,oldShader,newShader);
    }
}
