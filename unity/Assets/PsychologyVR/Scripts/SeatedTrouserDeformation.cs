using UnityEngine;

namespace PsychologyVR
{
    // Called after the existing recorded pose, never drives bones or advances its own clock.
    public sealed class SeatedTrouserDeformation : MonoBehaviour
    {
        public SkinnedMeshRenderer trousers;
        public Transform leftThigh,leftKnee,leftFoot,leftHand,leftMiddle;
        public Transform rightThigh,rightKnee,rightFoot,rightHand,rightMiddle;
        Material fabric;
        float leftBend,rightBend,leftContact,rightContact;
        static readonly int KneeL=Shader.PropertyToID("_ClothKneeL"),KneeR=Shader.PropertyToID("_ClothKneeR");
        static readonly int AxisL=Shader.PropertyToID("_ClothAxisL"),AxisR=Shader.PropertyToID("_ClothAxisR");
        static readonly int HandL=Shader.PropertyToID("_ClothHandL"),HandR=Shader.PropertyToID("_ClothHandR");
        static readonly int Up=Shader.PropertyToID("_ClothUp"),Response=Shader.PropertyToID("_ClothResponseTime");

        public void ApplyPose(float deltaTime)
        {
            if(!fabric)fabric=trousers.material;
            float blend=deltaTime<=0?1:1-Mathf.Exp(-deltaTime/fabric.GetFloat(Response));
            ApplySide(leftThigh,leftKnee,leftFoot,leftHand,leftMiddle,KneeL,AxisL,HandL,blend,ref leftBend,ref leftContact);
            ApplySide(rightThigh,rightKnee,rightFoot,rightHand,rightMiddle,KneeR,AxisR,HandR,blend,ref rightBend,ref rightContact);
            fabric.SetVector(Up,transform.up);
        }
        void ApplySide(Transform thigh,Transform knee,Transform foot,Transform hand,Transform middle,
            int kneeId,int axisId,int handId,float blend,ref float bend,ref float contact)
        {
            var axis=(thigh.position-knee.position).normalized;
            float targetBend=Vector3.Angle(knee.position-thigh.position,foot.position-knee.position)/140f;
            var palm=Vector3.Lerp(hand.position,middle.position,.55f);
            var segment=knee.position-thigh.position;
            var nearest=thigh.position+segment*Mathf.Clamp01(Vector3.Dot(palm-thigh.position,segment)/segment.sqrMagnitude);
            // Ivan's thigh surface plus palm centre lies ~18 cm from the bone axis.
            float targetContact=1-Mathf.InverseLerp(.18f,.24f,Vector3.Distance(palm,nearest));
            bend=Mathf.Lerp(bend,Mathf.Clamp01(targetBend),blend);contact=Mathf.Lerp(contact,targetContact,blend);
            fabric.SetVector(kneeId,new Vector4(knee.position.x,knee.position.y,knee.position.z,bend));
            fabric.SetVector(axisId,axis);
            fabric.SetVector(handId,new Vector4(palm.x,palm.y,palm.z,contact));
        }
        void OnDestroy(){if(fabric){if(Application.isPlaying)Destroy(fabric);else DestroyImmediate(fabric);}}
    }
}
