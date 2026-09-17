using UnityEngine;

namespace PsychologyVR
{
    public static class PrototypeRoom
    {
        public static Material Material(string name, Color color)
        {
            var mat = new Material(Shader.Find("Universal Render Pipeline/Lit"));
            mat.name = name;
            mat.color = color;
            mat.SetFloat("_Smoothness", .15f);
            return mat;
        }
        public static GameObject Box(string name, Vector3 position, Vector3 scale, Material material, Transform parent)
        {
            var obj = GameObject.CreatePrimitive(PrimitiveType.Cube);
            obj.name = name; obj.transform.SetParent(parent, false);
            obj.transform.localPosition = position; obj.transform.localScale = scale;
            obj.GetComponent<Renderer>().sharedMaterial = material;
            return obj;
        }
        public static void Build(Transform parent)
        {
            var wall = Material("Warm plaster", new Color(.77f, .75f, .68f));
            var sage = Material("Sage wall", new Color(.3f, .42f, .39f));
            var wood = Material("Warm oak", new Color(.38f, .23f, .13f));
            var fabric = Material("Blue upholstery", new Color(.17f, .29f, .33f));
            var cream = Material("Ivory", new Color(.9f, .86f, .73f));
            Box("Floor", new Vector3(0, -.08f, 0), new Vector3(6, .15f, 6), wood, parent);
            Box("Back wall", new Vector3(0, 1.5f, 3), new Vector3(6, 3, .15f), sage, parent);
            Box("Left wall", new Vector3(-3, 1.5f, 0), new Vector3(.15f, 3, 6), wall, parent);
            Box("Right wall", new Vector3(3, 1.5f, 0), new Vector3(.15f, 3, 6), wall, parent);
            Box("Rug", new Vector3(0, .006f, .1f), new Vector3(2.8f, .012f, 3.6f), fabric, parent);
            Chair(parent, new Vector3(0, 0, 1.15f), fabric, wood);
            Box("Side table top", new Vector3(1.0f, .54f, 1.15f), new Vector3(.65f, .08f, .6f), wood, parent);
            Box("Side table base", new Vector3(1.0f, .26f, 1.15f), new Vector3(.12f, .52f, .12f), wood, parent);
            Box("Tissue box", new Vector3(.9f, .64f, 1.15f), new Vector3(.22f, .12f, .13f), cream, parent);
            Box("Tissue", new Vector3(.9f, .73f, 1.15f), new Vector3(.08f, .08f, .015f), cream, parent);
            Box("Wall art frame", new Vector3(0, 1.95f, 2.9f), new Vector3(1.3f, .7f, .06f), wood, parent);
            Box("Wall art", new Vector3(0, 1.95f, 2.86f), new Vector3(1.2f, .6f, .015f), cream, parent);
            Box("Art accent", new Vector3(.12f, 1.94f, 2.84f), new Vector3(.4f, .35f, .01f), sage, parent);
            var lightObj = new GameObject("Soft daylight"); lightObj.transform.SetParent(parent);
            lightObj.transform.rotation = Quaternion.Euler(45, -25, 0);
            var light = lightObj.AddComponent<Light>(); light.type = LightType.Directional;
            light.intensity = 1.4f; light.shadows = LightShadows.Soft; light.color = new Color(1, .94f, .85f);
            RenderSettings.ambientLight = new Color(.55f, .6f, .64f);
            RenderSettings.ambientMode = UnityEngine.Rendering.AmbientMode.Flat;
        }
        static void Chair(Transform parent, Vector3 p, Material fabric, Material wood)
        {
            Box("Patient seat", p + new Vector3(0, .46f, 0), new Vector3(.68f, .14f, .62f), fabric, parent);
            Box("Patient backrest", p + new Vector3(0, .83f, .3f), new Vector3(.68f, .66f, .13f), fabric, parent);
            foreach (float x in new[]{-.26f,.26f}) foreach(float z in new[]{-.22f,.22f})
                Box("Chair leg", p + new Vector3(x, .21f, z), new Vector3(.055f,.42f,.055f),wood,parent);
        }
    }
}
