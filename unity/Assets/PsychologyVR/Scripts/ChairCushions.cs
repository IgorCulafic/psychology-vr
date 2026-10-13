using System.Collections.Generic;
using UnityEngine;

namespace PsychologyVR
{
    // Pressure is visual only; the existing seated pose and leg contacts own the body.
    [DefaultExecutionOrder(200)]
    public sealed class ChairCushions : MonoBehaviour
    {
        static readonly int Origin=Shader.PropertyToID("_CushionOrigin");
        static readonly int Right=Shader.PropertyToID("_CushionRight");
        static readonly int Up=Shader.PropertyToID("_CushionUp");
        static readonly int Forward=Shader.PropertyToID("_CushionForward");
        static readonly int Seat=Shader.PropertyToID("_CushionSeat");
        static readonly int RightSeat=Shader.PropertyToID("_CushionRightSeat");
        static readonly int LeftThigh=Shader.PropertyToID("_CushionLeftThigh");
        static readonly int RightThigh=Shader.PropertyToID("_CushionRightThigh");
        static readonly int ThighDirections=Shader.PropertyToID("_CushionThighDirections");
        static readonly int Back=Shader.PropertyToID("_CushionBack");
        static readonly int SeatDepth=Shader.PropertyToID("_CushionSeatDepth");
        static readonly int BackDepth=Shader.PropertyToID("_CushionBackDepth");
        static readonly int ThighDepth=Shader.PropertyToID("_CushionThighDepth");
        static readonly int ResponseTime=Shader.PropertyToID("_CushionResponseTime");
        readonly List<Material> materials=new List<Material>(2);
        MaterialPropertyBlock properties;
        Transform chair,pelvis,chest;
        Transform leftThigh,rightThigh,leftKnee,rightKnee;
        MeshRenderer cushion;
        PerformanceDriver performance;
        float backLoad;
        bool haveSeatedContacts;
        Vector4 seatedHeights;
        Vector4 leftSeatPressure,rightSeatPressure,leftThighPressure,rightThighPressure;
        Vector2 leftThighDirection,rightThighDirection,backCenter;

        void Awake(){properties=new MaterialPropertyBlock();}

        internal void SetPatient(GameObject patient)
        {
            if(cushion)cushion.SetPropertyBlock(null,1);
            chair=null;cushion=null;pelvis=null;chest=null;
            leftThigh=null;rightThigh=null;leftKnee=null;rightKnee=null;
            backLoad=0;haveSeatedContacts=false;properties.Clear();
            performance=patient.GetComponent<PerformanceDriver>();
            float closest=float.PositiveInfinity;
            foreach(Transform prop in transform)
            {
                if(prop.name!="modern_arm_chair_01")continue;
                float distance=(prop.position-patient.transform.position).sqrMagnitude;
                if(distance>=closest)continue;
                closest=distance;chair=prop;
            }
            if(!chair)return;
            cushion=chair.GetComponentInChildren<MeshRenderer>();
            var metaHuman=patient.GetComponent<MetaHumanJointRig>();
            var skeleton=metaHuman?metaHuman.bodyObject:patient;
            foreach(var bone in skeleton.GetComponentsInChildren<Transform>())
            {
                if(bone.name=="CC_Base_Hip"||bone.name=="mixamorig:Hips"||bone.name=="pelvis")pelvis=bone;
                if(bone.name=="CC_Base_Spine02"||bone.name=="mixamorig:Spine2"||bone.name=="spine_05")chest=bone;
                if(bone.name=="CC_Base_L_Thigh"||bone.name=="mixamorig:LeftUpLeg"||bone.name=="thigh_l")leftThigh=bone;
                if(bone.name=="CC_Base_R_Thigh"||bone.name=="mixamorig:RightUpLeg"||bone.name=="thigh_r")rightThigh=bone;
                if(bone.name=="CC_Base_L_Calf"||bone.name=="mixamorig:LeftLeg"||bone.name=="calf_l")leftKnee=bone;
                if(bone.name=="CC_Base_R_Calf"||bone.name=="mixamorig:RightLeg"||bone.name=="calf_r")rightKnee=bone;
            }
            if(!cushion||!pelvis||!chest||!leftThigh||!rightThigh||!leftKnee||!rightKnee)
            {Debug.LogError("Patient chair pressure needs a cushion renderer, pelvis, chest and both thigh/knee bones.",this);enabled=false;return;}
            enabled=true;
            properties.SetVector(Origin,chair.position);
            properties.SetVector(Right,chair.right);
            properties.SetVector(Up,chair.up);
            properties.SetVector(Forward,chair.forward);
        }

        void LateUpdate()
        {
            if(!cushion||!pelvis||!chest || (performance&&performance.IsPaused&&haveSeatedContacts))return;
            Vector3 hip=chair.InverseTransformPoint(pelvis.position);
            Vector3 torso=chair.InverseTransformPoint(chest.position);
            Vector3 leftRoot=chair.InverseTransformPoint(leftThigh.position);
            Vector3 rightRoot=chair.InverseTransformPoint(rightThigh.position);
            Vector3 leftEnd=chair.InverseTransformPoint(leftKnee.position);
            Vector3 rightEnd=chair.InverseTransformPoint(rightKnee.position);
            // The rear contacts follow the femur heads; the front contacts follow each thigh.
            Vector3 leftSeat=Vector3.Lerp(hip,leftRoot,.85f)-Vector3.forward*.02f;
            Vector3 rightSeat=Vector3.Lerp(hip,rightRoot,.85f)-Vector3.forward*.02f;
            Vector3 leftFront=Vector3.Lerp(leftRoot,leftEnd,.4f);
            Vector3 rightFront=Vector3.Lerp(rightRoot,rightEnd,.4f);
            Vector2 leftDirection=new Vector2(leftEnd.x-leftRoot.x,leftEnd.z-leftRoot.z).normalized;
            Vector2 rightDirection=new Vector2(rightEnd.x-rightRoot.x,rightEnd.z-rightRoot.z).normalized;
            if(!haveSeatedContacts)
            {
                seatedHeights=new Vector4(leftSeat.y,rightSeat.y,leftFront.y,rightFront.y);
                haveSeatedContacts=true;
                // The patient is already seated, including when the opening menu pauses motion.
                leftSeatPressure=new Vector4(leftSeat.x,leftSeat.z,1,0);
                rightSeatPressure=new Vector4(rightSeat.x,rightSeat.z,1,0);
                leftThighPressure=new Vector4(leftFront.x,leftFront.z,1,0);
                rightThighPressure=new Vector4(rightFront.x,rightFront.z,1,0);
                leftThighDirection=leftDirection;rightThighDirection=rightDirection;
                backCenter=new Vector2(torso.x,torso.y);
            }
            // The front of the sloping back pillow, measured from the imported chair.
            float backSurface=.157f-.44f*torso.y;
            float targetBack=Mathf.SmoothStep(0,1,(backSurface-(torso.z-.13f))/.025f);
            // Reuse the list: room detail can switch the cushion material during play.
            cushion.GetSharedMaterials(materials);
            Material material=materials[1];
            float blend=1-Mathf.Exp(-Time.deltaTime/material.GetFloat(ResponseTime));
            backLoad=Mathf.Lerp(backLoad,targetBack,blend);
            UpdatePressure(ref leftSeatPressure,leftSeat,seatedHeights.x,blend);
            UpdatePressure(ref rightSeatPressure,rightSeat,seatedHeights.y,blend);
            UpdatePressure(ref leftThighPressure,leftFront,seatedHeights.z,blend);
            UpdatePressure(ref rightThighPressure,rightFront,seatedHeights.w,blend);
            leftThighDirection=Vector2.Lerp(leftThighDirection,leftDirection,blend).normalized;
            rightThighDirection=Vector2.Lerp(rightThighDirection,rightDirection,blend).normalized;
            backCenter=Vector2.Lerp(backCenter,new Vector2(torso.x,torso.y),blend);
            float seatDepth=material.GetFloat(SeatDepth);
            float thighDepth=material.GetFloat(ThighDepth);
            properties.SetVector(Seat,WithDepth(leftSeatPressure,seatDepth));
            properties.SetVector(RightSeat,WithDepth(rightSeatPressure,seatDepth));
            properties.SetVector(LeftThigh,WithDepth(leftThighPressure,thighDepth));
            properties.SetVector(RightThigh,WithDepth(rightThighPressure,thighDepth));
            properties.SetVector(ThighDirections,new Vector4(leftThighDirection.x,leftThighDirection.y,rightThighDirection.x,rightThighDirection.y));
            properties.SetVector(Back,new Vector4(backCenter.x,backCenter.y,backLoad*material.GetFloat(BackDepth),0));
            // Slot 0 is the rigid frame. The block also survives the room detail toggle.
            cushion.SetPropertyBlock(properties,1);
        }

        static void UpdatePressure(ref Vector4 pressure,Vector3 point,float restHeight,float blend)
        {
            // Small seated-idle motion does not take the patient's weight off the cushion.
            float load=1-Mathf.SmoothStep(0,1,(point.y-restHeight-.04f)/.05f);
            pressure=Vector4.Lerp(pressure,new Vector4(point.x,point.z,load,0),blend);
        }

        static Vector4 WithDepth(Vector4 pressure,float depth)
        {pressure.z*=depth;return pressure;}

        void OnDisable(){if(cushion)cushion.SetPropertyBlock(null,1);}
    }
}
