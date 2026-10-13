using System;
using System.IO;
using System.Collections;
using UnityEngine;
using UnityEngine.Rendering;
namespace PsychologyVR
{
    public class MetaHumanPreview : MonoBehaviour
    {
        public GameObject[] characters;
        public Camera view;
        public AudioClip[] angryVoices;
        public TextAsset[] angryCues;
        int selected;string mood="neutral";bool close=true;
        bool movieCapture;
        PerformanceDriver body;FacialPerformance face;AudioSource voice;
        [Serializable] class CueFile {public MouthCue[] mouthCues;}
        bool CaptureCharacter(int index)
        {
            var args=Environment.GetCommandLineArgs();int flag=Array.IndexOf(args,"--character");
            return flag<0||(flag+1<args.Length&&string.Equals(characters[index].name,args[flag+1],StringComparison.OrdinalIgnoreCase));
        }
        void Select(int index)
        {
            foreach(var c in characters)c.SetActive(false);
            selected=index;var actor=characters[index];actor.SetActive(true);
            body=actor.GetComponent<PerformanceDriver>();if(!body)body=actor.AddComponent<PerformanceDriver>();
            face=actor.GetComponent<FacialPerformance>();if(!face)face=actor.AddComponent<FacialPerformance>();face.body=body;
            voice=actor.GetComponent<AudioSource>();if(!voice)voice=actor.AddComponent<AudioSource>();
            Mood("neutral");
        }
        void Mood(string value){mood=value;body.Apply(value,value=="neutral"?0:1,"none",true);}
        void Speak()
        {
            if(angryVoices==null||selected>=angryVoices.Length)return;
            voice.clip=angryVoices[selected];voice.Play();face.BeginSpeech(voice,angryCues[selected]?JsonUtility.FromJson<CueFile>(angryCues[selected].text).mouthCues:null);
        }
        IEnumerator Start()
        {
            Select(0);
            QualitySettings.vSyncCount=0;Application.targetFrameRate=60;
            var args=Environment.GetCommandLineArgs();
            if(Array.IndexOf(args,"--movies")>=0){yield return Movies();Application.Quit();yield break;}
            if(Array.IndexOf(args,"--outfit-check")>=0)
            {
                string outfits=Path.GetFullPath(Path.Combine(Application.dataPath,"../../../../experiments/metahuman/outfit-review"));Directory.CreateDirectory(outfits);
                for(int i=0;i<characters.Length;i++){if(!CaptureCharacter(i))continue;if(i!=selected)Select(i);close=false;yield return new WaitForSeconds(1);yield return Capture(outfits,i+"-outfit");}
                Application.Quit();yield break;
            }
            if(Array.IndexOf(Environment.GetCommandLineArgs(),"--capture")<0)yield break;
            string folder=Path.GetFullPath(Path.Combine(Application.dataPath,"../../../../experiments/metahuman/unity-review"));Directory.CreateDirectory(folder);
            for(int i=0;i<characters.Length;i++)
            {
                if(!CaptureCharacter(i))continue;
                if(i!=selected)Select(i);yield return new WaitForSeconds(.8f);close=false;yield return null;yield return Capture(folder,i+"-body");close=true;
                foreach(string e in new[]{"neutral","angry","crying","afraid","happy","sad","disgusted"})
                {Mood(e);yield return new WaitForSeconds(3);yield return Capture(folder,i+"-"+e);}
                Mood("angry");Speak();yield return new WaitForSeconds(2);yield return Capture(folder,i+"-speaking");voice.Stop();face.StopSpeech();
                Debug.Log("MH_REVIEW "+characters[i].name+" joints="+face.ShapeBindingCount+" tears="+face.Tears.AnchorCount);
            }
            Application.Quit();
        }
        [Serializable] class MovieTake {public string character;public int frames,fps;public float speechStart,speechDuration,jawRange;}
        IEnumerator Movies()
        {
            movieCapture=true;Time.captureFramerate=30;UnityEngine.Random.InitState(47);
            string folder=Path.GetFullPath(Path.Combine(Application.dataPath,"../../../../experiments/metahuman/unity-movies"));Directory.CreateDirectory(folder);
            var rt=RenderTexture.GetTemporary(960,960,24,RenderTextureFormat.ARGB32);
            var pixels=new Texture2D(960,960,TextureFormat.RGB24,false);
            for(int i=0;i<characters.Length;i++)
            {
                if(!CaptureCharacter(i))continue;
                if(i!=selected)Select(i);close=false;yield return new WaitForSeconds(.8f);
                string take=Path.Combine(folder,characters[i].name.ToLowerInvariant());Directory.CreateDirectory(take);
                float speechStart=15,duration=angryVoices[i].length;int frames=Mathf.CeilToInt((speechStart+duration+1)*30);
                float low=1,high=0;
                for(int f=0;f<frames;f++)
                {
                    float t=f/30f;
                    if(f==0){Mood("neutral");close=false;}
                    if(f==4*30){close=true;Mood("afraid");}
                    if(f==9*30)Mood("crying");
                    if(f==15*30)
                    {
                        Mood("angry");voice.clip=angryVoices[i];
                        face.BeginSpeech(voice,JsonUtility.FromJson<CueFile>(angryCues[i].text).mouthCues);
                    }
                    if(t>=speechStart&&t<speechStart+duration)face.SetSpeechPreviewTime(t-speechStart);
                    else if(t>=speechStart+duration)face.StopSpeech();
                    // Run the regular LateUpdate paths once at 1/30 s before rendering.
                    yield return new WaitForEndOfFrame();
                    var request=new RenderPipeline.StandardRequest{destination=rt};RenderPipeline.SubmitRenderRequest(view,request);
                    var old=RenderTexture.active;RenderTexture.active=rt;pixels.ReadPixels(new Rect(0,0,960,960),0,0);pixels.Apply();
                    File.WriteAllBytes(Path.Combine(take,f.ToString("D5")+".jpg"),pixels.EncodeToJPG(94));RenderTexture.active=old;
                    if(t>=speechStart&&t<speechStart+duration){low=Mathf.Min(low,face.JawWeight);high=Mathf.Max(high,face.JawWeight);}
                    yield return null;
                }
                var result=new MovieTake{character=characters[i].name,frames=frames,fps=30,speechStart=speechStart,speechDuration=duration,jawRange=high-low};
                File.WriteAllText(Path.Combine(take,"take.json"),JsonUtility.ToJson(result,true));
                Debug.Log("MH_MOVIE_OK "+result.character+" frames="+frames+" jawRange="+result.jawRange);
            }
            Destroy(pixels);RenderTexture.ReleaseTemporary(rt);Time.captureFramerate=0;
        }
        IEnumerator Capture(string folder,string name)
        {
            yield return new WaitForEndOfFrame();var rt=RenderTexture.GetTemporary(1280,1280,24,RenderTextureFormat.ARGB32);
            var request=new RenderPipeline.StandardRequest{destination=rt};RenderPipeline.SubmitRenderRequest(view,request);
            var old=RenderTexture.active;RenderTexture.active=rt;var image=new Texture2D(rt.width,rt.height,TextureFormat.RGB24,false);image.ReadPixels(new Rect(0,0,rt.width,rt.height),0,0);image.Apply();
            File.WriteAllBytes(Path.Combine(folder,name+".png"),image.EncodeToPNG());Destroy(image);RenderTexture.active=old;RenderTexture.ReleaseTemporary(rt);
        }
        void LateUpdate()
        {
            if(!face||!face.Head)return;
            var actor=characters[selected].transform;
            float fullBodyFocus=(actor.InverseTransformPoint(face.Head.position).y+.15f)*.5f;
            Vector3 focus=close?face.Head.position+Vector3.up*.055f:actor.position+Vector3.up*fullBodyFocus;
            view.transform.position=focus+(close?Vector3.forward*.9f:new Vector3(.65f,.12f,2.8f));view.transform.LookAt(focus);view.fieldOfView=close?35:36;
        }
        void OnGUI()
        {
            if(movieCapture)return;
            GUILayout.BeginArea(new Rect(15,15,440,320),GUI.skin.box);GUILayout.Label("MetaHuman Unity validation · "+mood);
            GUILayout.BeginHorizontal();for(int i=0;i<characters.Length;i++)if(GUILayout.Button(characters[i].name))Select(i);GUILayout.EndHorizontal();
            GUILayout.BeginHorizontal();foreach(string e in new[]{"neutral","angry","crying","afraid"})if(GUILayout.Button(e))Mood(e);GUILayout.EndHorizontal();
            GUILayout.BeginHorizontal();foreach(string e in new[]{"happy","sad","disgusted"})if(GUILayout.Button(e))Mood(e);GUILayout.EndHorizontal();
            if(GUILayout.Button("Play assigned voice"))Speak();if(GUILayout.Button("Toggle full body"))close=!close;
            GUILayout.EndArea();
        }
    }
}
