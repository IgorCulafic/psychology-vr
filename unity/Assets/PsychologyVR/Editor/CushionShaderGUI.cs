using System;
using UnityEditor;
using UnityEditor.Rendering.Universal.ShaderGUI;
using UnityEngine;

namespace PsychologyVR.Editor
{
    public sealed class CushionShaderGUI : ShaderGUI
    {
        // URP's Lit inspector is internal. Reuse it rather than duplicating its controls and keywords.
        readonly ShaderGUI lit=(ShaderGUI)Activator.CreateInstance(typeof(LitGUI).Assembly.GetType(
            "UnityEditor.Rendering.Universal.ShaderGUI.LitShader",true));
        bool pressureExpanded=true;

        public override void OnGUI(MaterialEditor editor,MaterialProperty[] properties)
        {
            lit.OnGUI(editor,properties);
            pressureExpanded=EditorGUILayout.Foldout(pressureExpanded,"Cushion Deformation",true,EditorStyles.foldoutHeader);
            if(!pressureExpanded)return;
            editor.ShaderProperty(FindProperty("_CushionSeatDepth",properties),"Seat indentation (m)");
            editor.ShaderProperty(FindProperty("_CushionBackDepth",properties),"Back indentation (m)");
            editor.ShaderProperty(FindProperty("_CushionSeatRadiusX",properties),"Buttock pressure radius - width (m)");
            editor.ShaderProperty(FindProperty("_CushionSeatRadiusZ",properties),"Buttock pressure radius - depth (m)");
            editor.ShaderProperty(FindProperty("_CushionThighDepth",properties),"Thigh indentation (m)");
            editor.ShaderProperty(FindProperty("_CushionThighRadiusX",properties),"Thigh pressure radius - width (m)");
            editor.ShaderProperty(FindProperty("_CushionThighRadiusZ",properties),"Thigh pressure radius - length (m)");
            editor.ShaderProperty(FindProperty("_CushionBackRadiusX",properties),"Back pressure radius - width (m)");
            editor.ShaderProperty(FindProperty("_CushionBackRadiusY",properties),"Back pressure radius - height (m)");
            editor.ShaderProperty(FindProperty("_CushionResponseTime",properties),"Cushion response time (s)");
        }

        public override void ValidateMaterial(Material material)=>lit.ValidateMaterial(material);

        public override void AssignNewShaderToMaterial(Material material,Shader oldShader,Shader newShader)
            =>lit.AssignNewShaderToMaterial(material,oldShader,newShader);
    }
}
