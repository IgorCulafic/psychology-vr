using System;
using UnityEditor;
using UnityEngine;

namespace PsychologyVR.Editor
{
    public static class BodyContactChecks
    {
        static void Require(bool value,string message){if(!value)throw new Exception("Body contact: "+message);}
        static Transform Node(Transform parent,string name,Vector3 position)
        {
            var node=new GameObject(name).transform;node.SetParent(parent);node.position=position;return node;
        }
        // Independent geometric cases plus deliberately obstructed synthetic hand.
        // This checks actual correction, not just a naturally collision-free pose.
        public static void Run()
        {
            var root=new GameObject("Contact checks");
            try
            {
                var head=Node(root.transform,"Head",new Vector3(0,2,0));
                var contact=root.AddComponent<BodyContactConstraints>();
                contact.Initialize(null,null,null,null,null,null,null,head);
                float depth=contact.Probe(new Vector3(0,2.07f,.05f),new Vector3(0,2.07f,.05f),.01f,out Vector3 normal,out int region);
                Require(Mathf.Abs(depth-.085f)<.0001f&&region==2&&Vector3.Dot(normal,Vector3.forward)>.99f,"point inside head");
                depth=contact.Probe(new Vector3(0,2,.075f),new Vector3(0,2.2f,.075f),.01f,out _,out _);
                Require(Mathf.Abs(depth-.06f)<.0001f,"parallel segments");
                depth=contact.Probe(new Vector3(-.2f,2.07f,.025f),new Vector3(.2f,2.07f,.025f),.01f,out _,out _);
                Require(Mathf.Abs(depth-.11f)<.0001f,"crossing segments");
                head.position+=Vector3.forward*.3f;
                Require(contact.Probe(new Vector3(0,2.07f,.05f),new Vector3(0,2.07f,.05f),.01f,out _,out _)==0,"boundary follows head translation");

                var wrist=Node(root.transform,"Hand",new Vector3(0,2.04f,.405f));
                var digits=new Transform[4][];
                for(int f=0;f<4;f++)digits[f]=Digit(wrist,"Finger"+f,(f-1.5f)*.018f);
                var thumb=Digit(wrist,"Thumb",-.045f);
                var articulation=new HandArticulation(digits,thumb,Vector3.back);
                var hand=contact.Register(wrist,digits,thumb,articulation,target=>wrist.position=target);
                Vector3 blocked=wrist.position;
                contact.Resolve(hand,blocked,1/60f);
                Require(contact.Corrections>0&&contact.MaxBefore>.005f,"obstructed hand must engage constraints");
                Require(contact.MaxAfter<.002f&&Vector3.Distance(wrist.position,blocked)>.005f,"obstructed hand must leave body");
                float firstOffset=Vector3.Distance(wrist.position,blocked);
                contact.Resolve(hand,blocked+Vector3.forward*.3f,1/60f);
                float released=Vector3.Distance(wrist.position,blocked+Vector3.forward*.3f);
                Require(released>0&&released<firstOffset,"contact offset releases gradually");
                wrist.position=new Vector3(0,2,.45f);
                articulation.Apply("angry",1,0,1);
                Require(articulation.ConstrainContact(contact)>0,"blocked curled fingers can release independently");
                wrist.position=new Vector3(-.01f,0,.5f);
                var secondWrist=Node(root.transform,"Other hand",new Vector3(.01f,0,.5f));
                var secondDigits=new Transform[4][];
                for(int f=0;f<4;f++)secondDigits[f]=Digit(secondWrist,"Other finger"+f,(f-1.5f)*.018f);
                var secondThumb=Digit(secondWrist,"Other thumb",-.045f);
                var secondArticulation=new HandArticulation(secondDigits,secondThumb,Vector3.back);
                var firstHand=contact.Register(wrist,digits,thumb,articulation,target=>wrist.position=target);
                var secondHand=contact.Register(secondWrist,secondDigits,secondThumb,secondArticulation,target=>secondWrist.position=target);
                contact.SeparateHands(firstHand,wrist.position,secondHand,secondWrist.position);
                Require(contact.HandPairCorrections>0&&contact.MaxHandPairAfter<.002f,"crossing hands separate");
                Debug.Log("BODY_CONTACT_GEOMETRY_OK");
            }
            finally {UnityEngine.Object.DestroyImmediate(root);}
        }
        static Transform[] Digit(Transform wrist,string name,float x)
        {
            var chain=new Transform[3];var parent=wrist;
            for(int j=0;j<3;j++)
            {
                chain[j]=Node(parent,name+j,wrist.position+new Vector3(x,.045f+j*.025f,0));parent=chain[j];
            }
            return chain;
        }
        public static void CheckAndBuild(){Run();ProjectSetup.BuildWindows();}
    }
}
