using UnityEngine;
namespace PsychologyVR
{
    // Finger hinges are cached in each joint's local rest frame. Parent bending
    // therefore carries distal hinges along without a shared world-space twist.
    public sealed class HandArticulation
    {
        class Joint
        {
            public Transform bone;
            public Quaternion rest;
            public Vector3 axis,spreadAxis,tipLocal;
            public float angle,spread,minAngle,maxAngle=105,rateOffset;
            public void Apply(float target,float delta,float targetSpread=0)
            {
                target=Mathf.Clamp(target,minAngle,maxAngle);
                float rate=(target>angle?9:6)+rateOffset;
                angle=Mathf.Lerp(angle,target,1-Mathf.Exp(-rate*delta));
                spread=Mathf.Lerp(spread,Mathf.Clamp(targetSpread,-12,12),1-Mathf.Exp(-5*delta));
                bone.localRotation=rest*Quaternion.AngleAxis(spread,spreadAxis)*Quaternion.AngleAxis(angle,axis);
            }
        }
        readonly Joint[][] fingers=new Joint[4][];
        readonly Joint[] thumb=new Joint[3];
        readonly float phase;
        string previousEmotion;
        float poseTime;
        public float LiftClearance {get;private set;}
        static readonly float[] RestSpread={3,0,-2,-5},OpenSpread={9,1,-5,-11};
        static readonly float[,] Relaxed={{5,10,6},{7,13,7},{10,17,10},{13,21,12}};
        static readonly float[,] Closed={{66,88,46},{70,93,52},{73,96,55},{76,98,58}};
        static readonly float[,] Open={{3,8,3},{5,10,4},{7,12,5},{10,15,7}};
        static readonly float[,] Cupped={{12,24,12},{15,28,14},{19,32,17},{23,36,20}};
        public HandArticulation(Transform[][] digits,Transform[] thumbs,Vector3 palmNormal,float phase=0)
        {
            this.phase=phase;
            Vector3 towardIndex=(digits[0][0].position-digits[3][0].position).normalized;
            for(int f=0;f<4;f++)
            {
                fingers[f]=new Joint[3];
                for(int j=0;j<3;j++)
                {
                    fingers[f][j]=Make(digits[f],j,palmNormal);
                }
                if(fingers[f][0]!=null&&digits[f][1])
                {
                    Vector3 along=(digits[f][1].position-digits[f][0].position).normalized;
                    float sign=Mathf.Sign(Vector3.Dot(Vector3.Cross(palmNormal,along),towardIndex));
                    fingers[f][0].spreadAxis=digits[f][0].InverseTransformDirection(palmNormal*sign);
                }
            }
            for(int j=0;j<3;j++)thumb[j]=Make(thumbs,j,palmNormal);
            if(thumb[0]!=null && thumbs[1] && digits[0][1])
            {
                Vector3 along=thumbs[1].position-thumbs[0].position;
                Vector3 across=digits[0][1].position-thumbs[0].position;
                thumb[0].axis=thumbs[0].InverseTransformDirection(Vector3.Cross(along,across).normalized);
                thumb[0].minAngle=-18;thumb[0].maxAngle=38;
            }
        }
        static Joint Make(Transform[] chain,int index,Vector3 palm)
        {
            var b=chain[index];if(!b)return null;
            Vector3 direction=index<2 && chain[index+1]?chain[index+1].position-b.position:b.position-chain[index-1].position;
            return new Joint{bone=b,rest=b.localRotation,axis=b.InverseTransformDirection(Vector3.Cross(direction.normalized,palm).normalized),spreadAxis=Vector3.up,tipLocal=b.InverseTransformVector(direction*.85f)};
        }
        public void Apply(string emotion,float intensity,float cover,float delta,float activity=0,float handLift=0,bool suppressMotion=false,bool supported=false,float action=0)
        {
            if(previousEmotion!=emotion){previousEmotion=emotion;poseTime=0;}
            poseTime+=delta;
            float grip=emotion=="angry"?Mathf.SmoothStep(0,1,Mathf.Clamp01(intensity*1.8f)):0;
            bool presenting=emotion=="frustrated"||emotion=="confused"||emotion=="happy";
            float open=presenting||emotion=="afraid"||emotion=="panicked"||emotion=="disgusted"?intensity:0;
            float cup=emotion=="crying"?Mathf.Lerp(.35f,1,cover):0;
            float moving=suppressMotion||emotion=="numb"?0:1;
            // Finger effort follows the current body/speech action. Independent
            // repeating finger clocks made the hand perform a different gesture.
            float thumbRub=action*activity*moving;
            float emphasis=presenting&&!supported?intensity*moving:0;
            float squeeze=grip*action*moving;
            float clutch=cup*action*moving;
            float settle=!supported&&(emotion=="neutral"||emotion=="calm")?.25f*moving:0;
            float clearancePulse=action*activity;
            LiftClearance=supported&&activity<=0?0:Mathf.Max(grip*.045f,clearancePulse*.07f*moving);
            // Wait for the supporting hand to clear the trouser surface before
            // curling into the palm. Raised gestures already have this clearance.
            float clearance=Mathf.SmoothStep(0,1,handLift*.45f/.045f);
            thumbRub*=clearance;
            for(int f=0;f<4;f++)for(int j=0;j<3;j++)
            {
                // On raising the hand, the fingertips open in a staggered sequence.
                float unfurl=Mathf.SmoothStep(0,1,(handLift-.025f*f)*3.5f);
                float openAmount=presenting?open*Mathf.Lerp(.25f,1,unfurl):open;
                float target=Mathf.Lerp(Relaxed[f,j],Open[f,j],openAmount);
                if(supported)target+=(1-grip)*(1-open)*Mathf.Exp(-poseTime*.5f)*(j==1?3:1.5f);
                target=Mathf.Lerp(target,Cupped[f,j],cup);
                target=Mathf.Lerp(target,Closed[f,j],grip);
                float curl=action*activity*(f<2?.75f:1)*moving*clearance;
                float explain=action*emphasis*clearance;
                float release=action*grip*moving;
                float press=action*cup*moving;
                float idle=action*settle*clearance;
                if(!supported && (emotion=="afraid"||emotion=="panicked"))target+=action*moving*(j==1?5:2)*(1+f*.1f);
                target+=(curl+idle)*(j==0?20:j==1?38:24);
                target+=explain*(j==0?16:j==1?32:20)*(f<2?.65f:1);
                target-=release*(j==0?14:j==1?24:14);
                target+=press*(j==0?8:j==1?16:10);
                // Relax the fingertips during the arm's return, then settle onto the lap.
                if(presenting)target+=(1-unfurl)*open*(j==0?4:j==1?9:5);
                float separation=Mathf.Lerp(RestSpread[f],OpenSpread[f],openAmount);
                separation=Mathf.Lerp(separation,RestSpread[f]*.35f,cup);
                separation=Mathf.Lerp(separation,0,grip);
                separation*=1-Mathf.Clamp01(curl+explain)*.55f;
                if(fingers[f][j]!=null)
                {
                    fingers[f][j].rateOffset=f*.6f-j*.4f+phase*.1f;
                    fingers[f][j].Apply(target,delta,j==0?separation:0);
                }
            }
            // Opposition, knuckle flexion and thumb-tip flexion stay independent.
            float opposition=Mathf.Lerp(Mathf.Lerp(3,-14,open),14,cup);
            float knuckle=Mathf.Lerp(Mathf.Lerp(14,5,open),20,cup);
            float tip=Mathf.Lerp(Mathf.Lerp(9,4,open),13,cup);
            float thumbGesture=action*emphasis*clearance;
            thumb[0]?.Apply(Mathf.Lerp(opposition,32,grip)+thumbRub*12+thumbGesture*12-squeeze*8+clutch*5,delta);
            thumb[1]?.Apply(Mathf.Lerp(knuckle,38,grip)+thumbRub*20+thumbGesture*18-squeeze*13+clutch*9,delta);
            thumb[2]?.Apply(Mathf.Lerp(tip,25,grip)+thumbRub*25+thumbGesture*20-squeeze*12+clutch*12,delta);
        }
        public int ConstrainContact(BodyContactConstraints contacts)
        {
            int changed=0;
            foreach(var chain in fingers)if(Relieve(chain,contacts,.009f))changed++;
            if(Relieve(thumb,contacts,.012f))changed++;
            return changed;
        }
        static float Penetration(Joint[] chain,BodyContactConstraints contacts,float radius)
        {
            float depth=0;
            for(int j=0;j<3;j++)
            {
                if(chain[j]==null)continue;
                Vector3 end=j<2&&chain[j+1]!=null?chain[j+1].bone.position:
                    chain[j].bone.TransformPoint(chain[j].tipLocal);
                depth=Mathf.Max(depth,contacts.Probe(chain[j].bone.position,end,radius,out _,out _));
            }
            return depth;
        }
        static bool Relieve(Joint[] chain,BodyContactConstraints contacts,float radius)
        {
            float originalDepth=Penetration(chain,contacts,radius);
            if(originalDepth<.0003f)return false;
            // A local search never adds curl, reverses a hinge, or changes spread.
            // Accept only steps which reduce penetration; the ordinary pose
            // smoother restores flexion gradually when the obstacle is gone.
            bool changed=false;
            for(int pass=0;pass<10;pass++)
            {
                bool improved=false;
                for(int j=2;j>=0;j--)
                {
                    var joint=chain[j];if(joint==null||joint.angle<=0)continue;
                    float saved=joint.angle;
                    joint.angle=Mathf.Max(0,saved-5);joint.Apply(joint.angle,0,joint.spread);
                    float depth=Penetration(chain,contacts,radius);
                    if(depth<originalDepth-.00001f){originalDepth=depth;improved=true;changed=true;}
                    else {joint.angle=saved;joint.Apply(saved,0,joint.spread);}
                }
                if(!improved||originalDepth<.0003f)break;
            }
            return changed;
        }
        public void ApplyController(float grip,float trigger,float delta)
        {
            for(int f=0;f<4;f++)for(int j=0;j<3;j++)
                fingers[f][j]?.Apply(Mathf.Lerp(Open[f,j],Closed[f,j],Mathf.Clamp01(f==0?trigger:grip)),delta);
            thumb[0]?.Apply(Mathf.Lerp(7,32,grip),delta);
            thumb[1]?.Apply(Mathf.Lerp(14,38,grip),delta);
            thumb[2]?.Apply(Mathf.Lerp(9,25,grip),delta);
        }
    }
}
