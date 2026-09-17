using System.Collections.Generic;
using UnityEngine;

namespace PsychologyVR
{
    public class AvatarSkinRendering : MonoBehaviour
    {
        readonly Dictionary<Renderer,Material[]> originals=new Dictionary<Renderer,Material[]>();
        RoomSurfaceLibrary library;
        public int SkinBindings {get;private set;}
        public void Initialize(bool natural)
        {
            library=Resources.Load<RoomSurfaceLibrary>("Visuals/SkinSurfaces");
            foreach(var renderer in GetComponentsInChildren<SkinnedMeshRenderer>())originals[renderer]=renderer.sharedMaterials;
            Apply(natural);
        }
        public void Apply(bool natural)
        {
            SkinBindings=0;
            foreach(var pair in originals)
            {
                var materials=(Material[])pair.Value.Clone();
                if(library)for(int i=0;i<materials.Length;i++)foreach(var entry in library.entries)
                    if(materials[i]==entry.original){SkinBindings++;if(natural)materials[i]=entry.enhanced;break;}
                if(pair.Key)pair.Key.sharedMaterials=materials;
            }
        }
    }
}
