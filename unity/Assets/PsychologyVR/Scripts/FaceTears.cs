using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering;

namespace PsychologyVR
{
    // Surface anchors are barycentric coordinates on Alex's skin. They follow
    // the deformed face, including expression blends and the seated animation.
    [DefaultExecutionOrder(200)]
    public class FaceTears : MonoBehaviour
    {
        struct Anchor {public int a,b,c;public Vector3 weights;}
        const int Rows=18;
        public float startHeight=.094f,endHeight=.017f,startWidth=.020f,endWidth=.034f;
        SkinnedMeshRenderer skin;
        Transform head;
        Mesh baked,ribbon;
        Material material;
        Texture2D alphaMap;
        readonly List<Vector3> bakedVertices=new List<Vector3>();
        readonly List<Vector3> bakedNormals=new List<Vector3>();
        MeshRenderer display;
        Anchor[] anchors;
        Vector3[] ribbonVertices;
        float target,wetness;
        Transform[] drops=new Transform[4];
        Material dropMaterial;
        public float Wetness=>wetness;
        public int AnchorCount {get;private set;}
        public bool Visible=>display && display.enabled;

        public void Initialize(Transform headBone,SkinnedMeshRenderer skinRenderer)
        {
            head=headBone;skin=skinRenderer;baked=new Mesh();ribbon=new Mesh();
            var surface=new GameObject("Tear tracks");surface.transform.SetParent(head,false);
            surface.AddComponent<MeshFilter>().sharedMesh=ribbon;display=surface.AddComponent<MeshRenderer>();
            display.shadowCastingMode=ShadowCastingMode.Off;display.receiveShadows=false;
            var source=Resources.Load<Material>("AlexTearFilm");
            material=source?new Material(source):new Material(Shader.Find("Universal Render Pipeline/Lit"));material.name="Alex tear film";
            material.SetFloat("_Surface",1);material.SetFloat("_SrcBlend",(float)BlendMode.SrcAlpha);
            material.SetFloat("_DstBlend",(float)BlendMode.OneMinusSrcAlpha);material.SetFloat("_ZWrite",0);
            material.SetFloat("_Cull",0);material.SetFloat("_Smoothness",.98f);
            material.EnableKeyword("_SURFACE_TYPE_TRANSPARENT");material.renderQueue=3000;
            display.sharedMaterial=material;display.enabled=false;
            // A narrow, soft-edged film reads as wet skin rather than painted stripes.
            alphaMap=new Texture2D(32,128,TextureFormat.RGBA32,false);alphaMap.wrapMode=TextureWrapMode.Clamp;
            var pixels=new Color[32*128];
            for(int y=0;y<128;y++)for(int x=0;x<32;x++)
            {
                float u=x/31f,v=y/127f;
                float alpha=Mathf.Pow(Mathf.Clamp01(Mathf.Sin(u*Mathf.PI)),1.6f)*Mathf.SmoothStep(0,1,v/.07f)*Mathf.SmoothStep(0,1,(1-v)/.18f);
                pixels[y*32+x]=new Color(1,1,1,alpha);
            }
            alphaMap.SetPixels(pixels);alphaMap.Apply();material.SetTexture("_BaseMap",alphaMap);
            dropMaterial=new Material(material);dropMaterial.SetTexture("_BaseMap",Texture2D.whiteTexture);
            for(int i=0;i<drops.Length;i++)
            {
                var drop=GameObject.CreatePrimitive(PrimitiveType.Sphere);drop.name="Moving tear bead";
                Destroy(drop.GetComponent<Collider>());drop.transform.SetParent(transform,false);
                drop.GetComponent<MeshRenderer>().sharedMaterial=dropMaterial;
                drop.GetComponent<MeshRenderer>().shadowCastingMode=ShadowCastingMode.Off;
                drops[i]=drop.transform;drop.SetActive(false);
            }
            StartCoroutine(BuildAnchors());
        }
        IEnumerator BuildAnchors()
        {
            // Skinning matrices are not ready during the actor's Awake callback.
            yield return null;yield return new WaitForEndOfFrame();
            skin.BakeMesh(baked,false);var vertices=baked.vertices;var triangles=baked.triangles;
            var projected=new Vector3[vertices.Length];
            // Build a head-relative frontal projection in the original rest pose.
            for(int i=0;i<vertices.Length;i++)
            {
                Vector3 delta=WorldPoint(vertices[i])-head.position;
                projected[i]=new Vector3(Vector3.Dot(delta,transform.right),Vector3.Dot(delta,transform.up),Vector3.Dot(delta,transform.forward));
            }
            var bounds=new Bounds(projected[0],Vector3.zero);foreach(var p in projected)bounds.Encapsulate(p);
            Debug.Log("TEAR_PROJECTION bounds="+bounds+" skinScale="+skin.transform.lossyScale);
            anchors=new Anchor[Rows*4];ribbonVertices=new Vector3[anchors.Length];var uv=new Vector2[anchors.Length];
            var indices=new int[(Rows-1)*12];int at=0;
            for(int side=0;side<2;side++)for(int row=0;row<Rows;row++)
            {
                float t=(float)row/(Rows-1),sign=side==0?-1:1;
                float x=sign*Mathf.Lerp(startWidth,endWidth,Mathf.Sin(t*Mathf.PI*.65f))+.0005f*Mathf.Sin(t*12+side);
                float y=Mathf.Lerp(startHeight,endHeight+(side==0?0:.009f),t),width=Mathf.Lerp(.0018f,.0008f,t);
                for(int edge=0;edge<2;edge++)
                {
                    int index=side*Rows*2+row*2+edge;
                    anchors[index]=Project(projected,triangles,new Vector2(x+(edge==0?-width:width),y));
                    uv[index]=new Vector2(edge,t);
                    if(anchors[index].weights!=Vector3.zero)AnchorCount++;
                }
                if(row==Rows-1)continue;
                int a=side*Rows*2+row*2;
                indices[at++]=a;indices[at++]=a+2;indices[at++]=a+1;
                indices[at++]=a+1;indices[at++]=a+2;indices[at++]=a+3;
            }
            ribbon.vertices=ribbonVertices;ribbon.triangles=indices;ribbon.uv=uv;ribbon.MarkDynamic();
            Debug.Log("TEAR_ANCHORS "+AnchorCount+"/"+anchors.Length);
        }
        static Anchor Project(Vector3[] vertices,int[] triangles,Vector2 point)
        {
            var result=new Anchor();float front=float.NegativeInfinity;
            for(int i=0;i<triangles.Length;i+=3)
            {
                int a=triangles[i],b=triangles[i+1],c=triangles[i+2];
                Vector2 v0=(Vector2)(vertices[b]-vertices[a]),v1=(Vector2)(vertices[c]-vertices[a]),v2=point-(Vector2)vertices[a];
                float det=v0.x*v1.y-v1.x*v0.y;if(Mathf.Abs(det)<1e-10f)continue;
                float u=(v2.x*v1.y-v1.x*v2.y)/det,v=(v0.x*v2.y-v2.x*v0.y)/det,w=1-u-v;
                if(u<0 || v<0 || w<0)continue;
                float z=w*vertices[a].z+u*vertices[b].z+v*vertices[c].z;
                if(z<=front)continue;front=z;result=new Anchor{a=a,b=b,c=c,weights=new Vector3(w,u,v)};
            }
            return result;
        }
        public void SetIntensity(float intensity) {target=Mathf.Clamp01(intensity);}
        // BakeMesh(useScale:false) supplies positions without compensating for
        // renderer scale. Alex's FBX renderer scale is 100; do not apply it twice.
        Vector3 WorldPoint(Vector3 point)=>skin.transform.position+skin.transform.rotation*point;
        void LateUpdate()
        {
            if(!skin || anchors==null)return;
            wetness=Mathf.MoveTowards(wetness,target,Time.deltaTime*(target>wetness?.6f:.45f));
            display.enabled=wetness>.005f && AnchorCount==anchors.Length;
            foreach(var drop in drops)if(drop)drop.gameObject.SetActive(display.enabled);
            if(!display.enabled)return;
            skin.BakeMesh(baked,false);baked.GetVertices(bakedVertices);baked.GetNormals(bakedNormals);
            for(int i=0;i<anchors.Length;i++)
            {
                var a=anchors[i];Vector3 p=bakedVertices[a.a]*a.weights.x+bakedVertices[a.b]*a.weights.y+bakedVertices[a.c]*a.weights.z;
                Vector3 normal=(bakedNormals[a.a]*a.weights.x+bakedNormals[a.b]*a.weights.y+bakedNormals[a.c]*a.weights.z).normalized;
                ribbonVertices[i]=head.InverseTransformPoint(WorldPoint(p)+skin.transform.TransformDirection(normal)*.0006f);
            }
            ribbon.vertices=ribbonVertices;ribbon.RecalculateNormals();ribbon.RecalculateBounds();
            material.SetColor("_BaseColor",new Color(.78f,.86f,.9f,.62f*wetness));
            dropMaterial.SetColor("_BaseColor",new Color(.80f,.91f,1,.8f*wetness));
            for(int i=0;i<drops.Length;i++)
            {
                float progress=Mathf.Repeat(Time.time*.37f+i*.41f,1),row=progress*(Rows-1);
                int a=Mathf.FloorToInt(row),b=Mathf.Min(a+1,Rows-1),offset=(i%2)*Rows*2;
                Vector3 start=(ribbonVertices[offset+a*2]+ribbonVertices[offset+a*2+1])*.5f;
                Vector3 end=(ribbonVertices[offset+b*2]+ribbonVertices[offset+b*2+1])*.5f;
                drops[i].position=head.TransformPoint(Vector3.Lerp(start,end,row-a));
                drops[i].rotation=head.rotation;
                drops[i].localScale=new Vector3(.0035f,.006f,.002f)*Mathf.Min(1,wetness*2)*Mathf.Sin(progress*Mathf.PI);
            }
        }
        void OnDestroy()
        {
            if(baked)Destroy(baked);if(ribbon)Destroy(ribbon);if(material)Destroy(material);if(dropMaterial)Destroy(dropMaterial);if(alphaMap)Destroy(alphaMap);
        }
    }
}
