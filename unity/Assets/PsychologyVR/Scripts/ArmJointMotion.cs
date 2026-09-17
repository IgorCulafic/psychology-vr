using UnityEngine;

namespace PsychologyVR
{
    // Joint-space arm solver. Hand orientation is constructed from bounded wrist
    // flexion/deviation; palm roll belongs to the forearm, never to the wrist.
    public sealed class ArmJointMotion
    {
        readonly Transform upper,lower,hand,twist1,twist2,elbowShare;
        readonly Quaternion upperBasis,lowerBasis,handBasis;
        readonly Quaternion twist1Rest,twist2Rest,elbowShareRest;
        readonly Vector3 fingerLocal,palmLocal,lowerPalmLocal,hingeLocal;
        readonly float side;
        float roll,flex,deviation;
        bool initialized;
        public float WristBend {get;private set;}
        public float ElbowBend {get;private set;}
        public float HingeError {get;private set;}
        public float WristTwist {get;private set;}
        public float ForearmRoll=>roll;

        public ArmJointMotion(Transform upper,Transform lower,Transform hand,Vector3 fingers,Vector3 palm,float side)
        {
            this.upper=upper;this.lower=lower;this.hand=hand;this.side=side;
            fingerLocal=fingers;palmLocal=palm;handBasis=Quaternion.LookRotation(fingers,palm);
            Vector3 u=(lower.position-upper.position).normalized,v=(hand.position-lower.position).normalized;
            Vector3 hinge=Vector3.Cross(u,v).normalized;
            if(hinge.sqrMagnitude<.5f)hinge=Vector3.Cross(u,hand.up).normalized;
            hingeLocal=upper.InverseTransformDirection(hinge);
            upperBasis=Quaternion.LookRotation(upper.InverseTransformDirection(u),hingeLocal);
            lowerBasis=Quaternion.LookRotation(lower.InverseTransformDirection(v),lower.InverseTransformDirection(hinge));
            lowerPalmLocal=lower.InverseTransformDirection(Vector3.ProjectOnPlane(hand.TransformDirection(palm),v).normalized);
            string prefix=lower.name.Replace("Forearm","");
            foreach(var bone in lower.GetComponentsInChildren<Transform>())
            {
                if(bone.name==prefix+"ForearmTwist01")twist1=bone;
                if(bone.name==prefix+"ForearmTwist02")twist2=bone;
                if(bone.name==prefix+"ElbowShareBone")elbowShare=bone;
            }
            twist1Rest=twist1?twist1.localRotation:Quaternion.identity;
            twist2Rest=twist2?twist2.localRotation:Quaternion.identity;
            elbowShareRest=elbowShare?elbowShare.localRotation:Quaternion.identity;
        }

        public void Solve(Vector3 target,Vector3 pole,Vector3 restFingers,Vector3 restPalm,Vector3 gestureFingers,Vector3 gesturePalm,float gestureWeight,float deltaTime)
        {
            // Contact constraints may solve this arm many times in one frame.
            // Reconstruct the helpers from calibration each time: inheriting the
            // preceding solve's partial twist accumulates sleeve deformation.
            // Restore in parent-to-child order (Twist02 is under Twist01).
            if(twist1)twist1.localRotation=twist1Rest;
            if(twist2)twist2.localRotation=twist2Rest;
            if(elbowShare)elbowShare.localRotation=elbowShareRest;
            Vector3 shoulder=upper.position,delta=target-shoulder;
            float u=Vector3.Distance(shoulder,lower.position),v=Vector3.Distance(lower.position,hand.position);
            // Preserve a small elbow bend at maximum reach; never invert the hinge.
            float minDistance=Mathf.Sqrt(u*u+v*v+2*u*v*Mathf.Cos(145*Mathf.Deg2Rad));
            float maxDistance=Mathf.Sqrt(u*u+v*v+2*u*v*Mathf.Cos(8*Mathf.Deg2Rad));
            float distance=Mathf.Clamp(delta.magnitude,minDistance,maxDistance);
            Vector3 axis=delta.sqrMagnitude>.000001f?delta.normalized:upper.forward;
            Vector3 perpendicular=Vector3.ProjectOnPlane(pole,axis).normalized;
            if(perpendicular.sqrMagnitude<.5f)perpendicular=Vector3.ProjectOnPlane(upper.up,axis).normalized;
            float along=(u*u-v*v+distance*distance)/(2*distance);
            Vector3 elbow=shoulder+axis*along+perpendicular*Mathf.Sqrt(Mathf.Max(0,u*u-along*along));
            Vector3 upperDirection=(elbow-shoulder).normalized;
            Vector3 foreDirection=(shoulder+axis*distance-elbow).normalized;
            Vector3 hinge=Vector3.Cross(upperDirection,foreDirection).normalized;
            upper.rotation=Quaternion.LookRotation(upperDirection,hinge)*Quaternion.Inverse(upperBasis);
            lower.rotation=Quaternion.LookRotation(foreDirection,hinge)*Quaternion.Inverse(lowerBasis);

            // Neutral is the thumb-up forearm frame. Roll from palm-down to palm-up
            // travels through this frame, with no ambiguous 180-degree hand slerp.
            Vector3 neutralPalm=hinge*side;
            Vector3 basePalm=Vector3.ProjectOnPlane(lower.TransformDirection(lowerPalmLocal),foreDirection).normalized;
            float neutralOffset=Vector3.SignedAngle(basePalm,neutralPalm,foreDirection);
            float restRoll=PalmRoll(neutralPalm,restPalm,foreDirection);
            float gestureRoll=PalmRoll(neutralPalm,gesturePalm,foreDirection);
            float goalRoll=Mathf.Lerp(restRoll,gestureRoll,gestureWeight);
            if(!initialized){roll=restRoll;initialized=true;}
            roll=Mathf.MoveTowards(roll,goalRoll,150*deltaTime);
            Quaternion before=lower.rotation;
            Quaternion t1=twist1?twist1.rotation:Quaternion.identity,t2=twist2?twist2.rotation:Quaternion.identity;
            Quaternion share=elbowShare?elbowShare.rotation:Quaternion.identity;
            float totalRoll=neutralOffset+roll;
            lower.rotation=Quaternion.AngleAxis(totalRoll,foreDirection)*before;
            // CC's helper bones are branches, not part of the elbow-to-hand chain.
            // Distribute skin rotation along the sleeve and spare the elbow crease.
            if(twist1)twist1.rotation=Quaternion.AngleAxis(totalRoll*.4f,foreDirection)*t1;
            if(twist2)twist2.rotation=Quaternion.AngleAxis(totalRoll*.75f,foreDirection)*t2;
            if(elbowShare)elbowShare.rotation=share;

            Vector3 palm=Quaternion.AngleAxis(roll,foreDirection)*neutralPalm;
            Vector3 across=Vector3.Cross(palm,foreDirection).normalized;
            Vector3 wanted=Vector3.Slerp(restFingers.normalized,gestureFingers.normalized,gestureWeight);
            float f=Vector3.Dot(wanted,foreDirection),p=Vector3.Dot(wanted,palm),a=Vector3.Dot(wanted,across);
            float goalFlex=Mathf.Clamp(Mathf.Atan2(p,f)*Mathf.Rad2Deg,-35,50);
            float goalDeviation=Mathf.Clamp(Mathf.Atan2(a,Mathf.Sqrt(f*f+p*p))*Mathf.Rad2Deg,-18,18);
            flex=Mathf.MoveTowards(flex,goalFlex,120*deltaTime);
            deviation=Mathf.MoveTowards(deviation,goalDeviation,90*deltaTime);
            Quaternion bend=Quaternion.AngleAxis(deviation,palm)*Quaternion.AngleAxis(-flex,across);
            hand.rotation=Quaternion.LookRotation(bend*foreDirection,bend*palm)*Quaternion.Inverse(handBasis);

            // Measure the resulting bone geometry, not just the requested angles.
            Vector3 actualUpper=(lower.position-upper.position).normalized,actualFore=(hand.position-lower.position).normalized;
            WristBend=Vector3.Angle(actualFore,hand.TransformDirection(fingerLocal));
            Vector3 actualFingers=hand.TransformDirection(fingerLocal);
            Vector3 transportedPalm=Quaternion.FromToRotation(actualFore,actualFingers)*lower.TransformDirection(lowerPalmLocal);
            WristTwist=Mathf.Abs(Vector3.SignedAngle(transportedPalm,hand.TransformDirection(palmLocal),actualFingers));
            ElbowBend=Vector3.Angle(actualUpper,actualFore);
            HingeError=Vector3.Angle(Vector3.Cross(actualUpper,actualFore),upper.TransformDirection(hingeLocal));
        }
        static float PalmRoll(Vector3 neutral,Vector3 wanted,Vector3 axis)
        {
            var projected=Vector3.ProjectOnPlane(wanted,axis);
            if(projected.sqrMagnitude<.0001f)return 0;
            return Mathf.Clamp(Vector3.SignedAngle(neutral,projected,axis),-85,85);
        }
    }
}
