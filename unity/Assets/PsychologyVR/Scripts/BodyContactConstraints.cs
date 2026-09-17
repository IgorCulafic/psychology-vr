using System;
using System.Collections.Generic;
using UnityEngine;

namespace PsychologyVR
{
    // Runs after FacialPerformance's gaze correction. These bone-following
    // capsules are query geometry, not rigidbodies that fight the animation.
    [DefaultExecutionOrder(200)]
    public sealed class BodyContactConstraints : MonoBehaviour
    {
        sealed class Boundary
        {
            public Transform startBone,endBone;
            public Vector3 startLocal,endLocal;
            public float radius;
            public int region;
            public Vector3 Start=>startBone.TransformPoint(startLocal);
            public Vector3 End=>endBone.TransformPoint(endLocal);
        }
        public sealed class Hand
        {
            internal readonly List<Segment> segments=new List<Segment>();
            internal Vector3 offset,target;
            internal Action<Vector3> solve;
            internal HandArticulation articulation;
        }
        internal sealed class Segment
        {
            public Transform start,end;
            public Vector3 endLocal;
            public float radius;
            public Vector3 A=>start.position;
            public Vector3 B=>end?end.position:start.TransformPoint(endLocal);
        }
        readonly List<Boundary> boundaries=new List<Boundary>();
        PerformanceDriver driver;
        const float Margin=.005f,MaxOffset=.14f;
        public float MaxBefore {get;private set;}
        public float MaxAfter {get;private set;}
        public float CurrentPenetration {get;private set;}
        public float MaxCorrection {get;private set;}
        public int Corrections {get;private set;}
        public int FingerCorrections {get;private set;}
        public int HandPairCorrections {get;private set;}
        public float MaxHandPairAfter {get;private set;}
        public readonly int[] RegionContacts=new int[3]; // thighs, torso, head
        public int BoundaryCount=>boundaries.Count;
        public bool drawBoundaries;

        public void Initialize(PerformanceDriver owner,Transform leftThigh,Transform leftKnee,
            Transform rightThigh,Transform rightKnee,Transform waist,Transform chest,Transform head)
        {
            driver=owner;
            if(leftThigh&&leftKnee)Add(leftThigh,leftKnee,leftThigh.position,Vector3.Lerp(leftThigh.position,leftKnee.position,.94f),.093f,0);
            if(rightThigh&&rightKnee)Add(rightThigh,rightKnee,rightThigh.position,Vector3.Lerp(rightThigh.position,rightKnee.position,.94f),.093f,0);
            if(waist&&chest)Add(waist,chest,waist.position+transform.forward*.025f,
                chest.position+transform.up*.035f+transform.forward*.025f,.15f,1);
            if(head)Add(head,head,head.position+transform.up*.025f+transform.forward*.025f,
                head.position+transform.up*.115f+transform.forward*.025f,.095f,2);
        }
        void Add(Transform start,Transform end,Vector3 a,Vector3 b,float radius,int region)
        {
            if(!start||!end)return;
            boundaries.Add(new Boundary{startBone=start,endBone=end,startLocal=start.InverseTransformPoint(a),
                endLocal=end.InverseTransformPoint(b),radius=radius,region=region});
        }
        public Hand Register(Transform wrist,Transform[][] digits,Transform[] thumb,HandArticulation articulation,Action<Vector3> solve)
        {
            var hand=new Hand{articulation=articulation,solve=solve};
            foreach(var chain in digits)
            {
                if(chain[0])hand.segments.Add(new Segment{start=wrist,end=chain[0],radius=.022f});
                AddDigit(hand,chain,false);
            }
            AddDigit(hand,thumb,true);
            return hand;
        }
        static void AddDigit(Hand hand,Transform[] chain,bool thumb)
        {
            for(int j=0;j<3;j++)
            {
                if(!chain[j])continue;
                var segment=new Segment{start=chain[j],radius=thumb?.012f:.009f};
                if(j<2)segment.end=chain[j+1];
                else if(chain[1])
                {
                    Vector3 tip=(chain[2].position-chain[1].position)*.85f;
                    segment.endLocal=chain[2].InverseTransformVector(tip);
                }
                hand.segments.Add(segment);
            }
        }
        void LateUpdate()
        {
            if(!driver)return;
            CurrentPenetration=0;
            driver.ResolveBodyContacts();
        }
        public void Resolve(Hand hand,Vector3 target,float delta)
        {
            // Retain the previous frame's correction, releasing slowly. New outward
            // corrections are immediate: smoothing penetration lets skin clip.
            hand.offset*=Mathf.Exp(-delta/.22f);
            Vector3 offset=transform.TransformVector(hand.offset);
            hand.target=target+offset;hand.solve(hand.target);
            float before=Query(hand,out _,out _);
            MaxBefore=Mathf.Max(MaxBefore,before);
            for(int pass=0;pass<10;pass++)
            {
                float depth=Query(hand,out Vector3 normal,out int region);
                if(depth<.0003f)break;
                RegionContacts[region]++;Corrections++;
                offset=Vector3.ClampMagnitude(offset+normal*(depth+.001f),MaxOffset);
                hand.target=target+offset;hand.solve(hand.target);
            }
            // If reach limits prevent translating a finger clear, reduce only
            // the blocked digit's flexion. Other digits retain their performance.
            if(Query(hand,out _,out _)>.0003f)
            {
                FingerCorrections+=hand.articulation.ConstrainContact(this);
                for(int pass=0;pass<4;pass++)
                {
                    float depth=Query(hand,out Vector3 normal,out _);
                    if(depth<.0003f)break;
                    offset=Vector3.ClampMagnitude(offset+normal*(depth+.001f),MaxOffset);
                    hand.target=target+offset;hand.solve(hand.target);
                }
            }
            hand.offset=transform.InverseTransformVector(offset);
            MaxCorrection=Mathf.Max(MaxCorrection,offset.magnitude);
            float remaining=Query(hand,out _,out _);
            CurrentPenetration=Mathf.Max(CurrentPenetration,remaining);
            MaxAfter=Mathf.Max(MaxAfter,remaining);
        }
        float Query(Hand hand,out Vector3 normal,out int region)
        {
            float deepest=0;normal=transform.up;region=0;
            foreach(var segment in hand.segments)
            {
                float depth=Probe(segment.A,segment.B,segment.radius,out Vector3 n,out int r);
                if(depth>deepest){deepest=depth;normal=n;region=r;}
            }
            return deepest;
        }
        public void SeparateHands(Hand left,Vector3 leftTarget,Hand right,Vector3 rightTarget)
        {
            for(int pass=0;pass<12;pass++)
            {
                float depth=PairDepth(left,right,out Vector3 normal);
                if(depth<.0003f)break;
                HandPairCorrections++;
                // Crossing hands must separate toward their own side instead of
                // swapping sides when the nearest-point direction is ambiguous.
                if(Vector3.Dot(normal,-transform.right)<.25f)normal=-transform.right;
                left.offset=Vector3.ClampMagnitude(left.offset+transform.InverseTransformVector(normal*(depth*.55f+.001f)),MaxOffset);
                right.offset=Vector3.ClampMagnitude(right.offset-transform.InverseTransformVector(normal*(depth*.55f+.001f)),MaxOffset);
                Resolve(left,leftTarget,0);Resolve(right,rightTarget,0);
            }
            MaxHandPairAfter=Mathf.Max(MaxHandPairAfter,PairDepth(left,right,out _));
        }
        static float PairDepth(Hand left,Hand right,out Vector3 normal)
        {
            float deepest=0;normal=Vector3.left;
            foreach(var l in left.segments)foreach(var r in right.segments)
            {
                Closest(l.A,l.B,r.A,r.B,out Vector3 a,out Vector3 b);
                float depth=l.radius+r.radius+.003f-Vector3.Distance(a,b);
                if(depth<=deepest)continue;
                deepest=depth;normal=(a-b).normalized;
            }
            return deepest;
        }
        public float Probe(Vector3 a,Vector3 b,float radius,out Vector3 normal,out int region)
        {
            float deepest=0;normal=transform.up;region=0;
            foreach(var boundary in boundaries)
            {
                Closest(a,b,boundary.Start,boundary.End,out Vector3 onHand,out Vector3 onBody);
                Vector3 separation=onHand-onBody;
                float depth=boundary.radius+radius+Margin-separation.magnitude;
                if(depth<=deepest)continue;
                deepest=depth;region=boundary.region;
                normal=separation.sqrMagnitude>.000001f?separation.normalized:transform.forward;
            }
            return deepest;
        }
        // Closest points of finite segments, including parallel/zero-length cases.
        internal static void Closest(Vector3 p,Vector3 q,Vector3 r,Vector3 s,out Vector3 a,out Vector3 b)
        {
            Vector3 d=q-p,e=s-r,v=p-r;
            float dd=Vector3.Dot(d,d),ee=Vector3.Dot(e,e),ev=Vector3.Dot(e,v),t,u;
            if(dd<1e-10f&&ee<1e-10f){a=p;b=r;return;}
            if(dd<1e-10f){t=0;u=Mathf.Clamp01(ev/ee);}
            else
            {
                float dv=Vector3.Dot(d,v);
                if(ee<1e-10f){u=0;t=Mathf.Clamp01(-dv/dd);}
                else
                {
                    float de=Vector3.Dot(d,e),den=dd*ee-de*de;
                    t=den>1e-10f?Mathf.Clamp01((de*ev-dv*ee)/den):0;
                    u=(de*t+ev)/ee;
                    if(u<0){u=0;t=Mathf.Clamp01(-dv/dd);}
                    else if(u>1){u=1;t=Mathf.Clamp01((de-dv)/dd);}
                }
            }
            a=p+d*t;b=r+e*u;
        }
        void OnDrawGizmosSelected()
        {
            if(!drawBoundaries)return;
            foreach(var b in boundaries)
            {
                Gizmos.color=b.region==2?Color.cyan:b.region==1?Color.yellow:Color.green;
                Gizmos.DrawWireSphere(b.Start,b.radius);Gizmos.DrawWireSphere(b.End,b.radius);
                Gizmos.DrawLine(b.Start,b.End);
            }
        }
    }
}
