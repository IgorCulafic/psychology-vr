using UnityEngine;
using UnityEngine.Rendering;

namespace PsychologyVR
{
    public class RoomLighting : MonoBehaviour
    {
        void Awake()
        {
            RenderSettings.ambientMode=AmbientMode.Trilight;
            RenderSettings.ambientSkyColor=new Color(.62f,.65f,.67f);
            RenderSettings.ambientEquatorColor=new Color(.48f,.46f,.42f);
            RenderSettings.ambientGroundColor=new Color(.28f,.25f,.21f);
            RenderSettings.reflectionIntensity=.55f;
        }
    }
}
