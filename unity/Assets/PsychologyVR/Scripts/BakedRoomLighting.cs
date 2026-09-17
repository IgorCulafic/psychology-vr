using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering;

namespace PsychologyVR
{
    public class BakedRoomLighting : MonoBehaviour
    {
        readonly Dictionary<Renderer,int> indices=new Dictionary<Renderer,int>();
        readonly List<Renderer> probeReceivers=new List<Renderer>();
        public bool Requested {get;private set;}
        public bool Active {get;private set;}
        public int MappedRenderers {get;private set;}
        public bool Available=>MappedRenderers>0&&LightmapSettings.lightProbes!=null&&LightmapSettings.lightProbes.count>0;
        bool enhanced=true;
        public void Initialize()
        {
            foreach(var renderer in GetComponentsInChildren<Renderer>())
            {
                indices[renderer]=renderer.lightmapIndex;
                if(renderer.lightmapIndex>=0&&renderer.lightmapIndex<LightmapSettings.lightmaps.Length)MappedRenderers++;
                else probeReceivers.Add(renderer);
            }
            Requested=PlayerPrefs.GetInt("BouncedLighting",1)==1;
            Apply();
        }
        public void RegisterAvatar(GameObject avatar)
        {
            probeReceivers.AddRange(avatar.GetComponentsInChildren<Renderer>());Apply();
        }
        public void SetRequested(bool enabled,bool save=true)
        {
            Requested=enabled;Apply();
            if(save){PlayerPrefs.SetInt("BouncedLighting",enabled?1:0);PlayerPrefs.Save();}
            GetComponent<RoomRendering>()?.RefreshIndirectState();
        }
        public void SetRoomDetail(bool enabled){enhanced=enabled;Apply();}
        void Apply()
        {
            Active=Available&&Requested&&enhanced;
            foreach(var pair in indices)if(pair.Key)pair.Key.lightmapIndex=Active?pair.Value:-1;
            probeReceivers.RemoveAll(renderer=>!renderer);
            foreach(var renderer in probeReceivers)renderer.lightProbeUsage=Active?LightProbeUsage.BlendProbes:LightProbeUsage.Off;
        }
    }
}
