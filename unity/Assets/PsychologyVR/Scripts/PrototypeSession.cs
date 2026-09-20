using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Text;
using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.Networking;
using UnityEngine.XR;
using CommonUsages = UnityEngine.XR.CommonUsages;

namespace PsychologyVR
{
    [Serializable] public class SpeechSegment { public string text, emotion, gesture, voice_style, gaze, audio_url, segment_id,lip_sync_source; public float intensity,transition_seconds,pause_before_seconds,hold_after_seconds,gesture_at,gesture_duration_seconds;public MouthCue[] mouth_cues; }
    [Serializable] public class Reply { public string session_id, turn_id, dialogue_provider, tts_provider, scenario_id, character_name, initial_emotion; public float initial_intensity; public SpeechSegment[] segments; public int total_ms; }
    [Serializable] public class RequestBody { public string session_id, text, wav_base64, scenario_id, replace_session_id; public bool opening; }
    [Serializable] public class Health { public string dialogue_provider, tts_provider, stt_provider; }
    [Serializable] public class Transcript { public string text; }

    public class PrototypeSession : MonoBehaviour
    {
        public GameObject characterPrefab;
        public CharacterAppearance[] appearances;
        public GameObject playerPrefab;
        public GameObject environmentPrefab;
        public AnimationClip seatedClip;
        public string serviceUrl = "http://127.0.0.1:8765";
        public string Status { get; private set; } = "Connecting to local bridge...";
        public string Subtitle { get; private set; } = "";
        public string Providers { get; private set; } = "";
        string sessionId, input = "How are you feeling right now?", micDevice;
        int version;
        bool busy, paused, recording, controllerHeld;
        float recordingStarted;
        AudioClip microphoneClip;
        AudioSource voice;
        PerformanceDriver performance;
        FacialPerformance face;
        SeatedPlayerAvatar playerAvatar;
        Transform origin;
        Camera view;
        LineRenderer controllerRay;
        TextMesh subtitleText, inputStatusText;
        float[] microphoneMeter;
        float microphonePeak;
        ConsultationMenu menu;
        GameObject actor;
        public ScenarioCatalog Catalog {get;private set;}
        public ScenarioEntry CurrentScenario {get;private set;}
        public string ActiveAppearance {get;private set;}
        public CharacterAppearance[] Appearances=>appearances;
        public bool MenuOpen {get;private set;}
        public bool IsSwitching {get;private set;}
        public bool HasConversation {get;private set;}
        string initialEmotion="anxious";float initialIntensity=.65f;
        public bool IsBusy=>busy;
        public bool IsRecording=>recording;
        public bool CanSelect=>!IsSwitching&&!string.IsNullOrEmpty(sessionId);
        public bool CanSubmit=>CanSelect&&!busy&&!recording;
        public bool IsSpeechAudition=>Providers.Contains("higgs-recorded");
        public string Draft {get=>input;set=>input=value;}
        public string MicrophoneName=>string.IsNullOrEmpty(micDevice)?"No microphone detected":micDevice;
        public float SpeechVolume {get;private set;}=1;
        public bool SubtitlesEnabled {get;private set;}=true;
        public ConsultationVisuals Visuals {get;private set;}
        public RoomRendering Room {get;private set;}
        public BakedRoomLighting Bounce {get;private set;}
        public bool NaturalSkin {get;private set;}
        public float PreviewIntensity {get=>previewIntensity;set=>previewIntensity=value;}
        bool menuHeld;
        readonly HashSet<UnityWebRequest> activeRequests = new HashSet<UnityWebRequest>();
        float previewIntensity=.65f;

        void Awake(){Application.runInBackground=true;}

        void InitializeSession(GameObject loadedRoom)
        {
            Application.runInBackground = true;
            NaturalSkin=PlayerPrefs.GetInt("NaturalSkin",1)==1;
            if(loadedRoom||environmentPrefab)
            {
                var room=loadedRoom?loadedRoom:Instantiate(environmentPrefab);
                if(loadedRoom){Bounce=room.AddComponent<BakedRoomLighting>();Bounce.Initialize();}
                Room=room.AddComponent<RoomRendering>();Room.Initialize();
            }
            else PrototypeRoom.Build(new GameObject("Consultation room").transform);
            var rig = new GameObject("Seated origin"); origin = rig.transform; origin.position = new Vector3(0, 0, -1.5f);
            var cameraObject = new GameObject("Player camera"); cameraObject.tag = "MainCamera";
            cameraObject.transform.SetParent(origin, false); view = cameraObject.AddComponent<Camera>();
            view.nearClipPlane = .05f; view.farClipPlane = 40; view.backgroundColor = new Color(.28f,.34f,.35f);
            view.clearFlags = CameraClearFlags.SolidColor;
            cameraObject.AddComponent<AudioListener>();
            Visuals=gameObject.AddComponent<ConsultationVisuals>();Visuals.Initialize(view);
            if(playerPrefab)
            {
                var player=Instantiate(playerPrefab,origin.position,Quaternion.identity);player.name="Seated player";
                player.AddComponent<AvatarSkinRendering>().Initialize(NaturalSkin);Bounce?.RegisterAvatar(player);
                playerAvatar=player.AddComponent<SeatedPlayerAvatar>();playerAvatar.Initialize(origin,view);
                playerAvatar.Recentered=()=>{if(MenuOpen)menu?.Reposition();};
            }
            Catalog=ScenarioCatalog.Load();CurrentScenario=Catalog.Find(Catalog.default_scenario_id);
            if(appearances==null || appearances.Length==0)appearances=new[]{new CharacterAppearance{id="jumper",label="Jumper",prefab=characterPrefab,seatedClip=seatedClip}};
            ActiveAppearance=CurrentScenario.avatar_id;SpawnCharacter(ActiveAppearance);
            subtitleText = Label("Subtitles", new Vector3(0,1.03f,.35f), .005f, TextAnchor.MiddleCenter);
            inputStatusText = Label("Speech input status", new Vector3(0,.85f,.35f), .003f, TextAnchor.MiddleCenter);
            SpeechVolume=PlayerPrefs.GetFloat("SpeechVolume",1);SubtitlesEnabled=PlayerPrefs.GetInt("Subtitles",1)==1;voice.volume=SpeechVolume;
            menu=gameObject.AddComponent<ConsultationMenu>();menu.Initialize(this,view);
            var pointer = new GameObject("Right controller pointer");
            controllerRay = pointer.AddComponent<LineRenderer>(); controllerRay.positionCount = 2;
            controllerRay.startWidth = .003f; controllerRay.endWidth = .001f;
            // Lit is referenced by the actor assets and therefore retained in builds.
            controllerRay.sharedMaterial = PrototypeRoom.Material("Pointer",new Color(.3f,.9f,.8f));
            controllerRay.sharedMaterial.EnableKeyword("_EMISSION");
            controllerRay.sharedMaterial.SetColor("_EmissionColor",new Color(.3f,.9f,.8f));
            if (Microphone.devices.Length > 0) micDevice = Microphone.devices[0];
            string savedMic=PlayerPrefs.GetString("Microphone","");if(Array.IndexOf(Microphone.devices,savedMic)>=0)micDevice=savedMic;
            bool diagnostic=Array.Exists(Environment.GetCommandLineArgs(),a=>a=="--integration-preview"||a=="--record-alex"||a=="--alex-preview"||a=="--environment-preview"||a=="--smoke-test"||a=="--visuals-preview");
            SetMenuOpen(!diagnostic);
            if(Array.IndexOf(Environment.GetCommandLineArgs(),"--menu-preview")>=0)StartCoroutine(MenuPreview.Run(this,menu,view,Capture));
            if(Array.IndexOf(Environment.GetCommandLineArgs(),"--visuals-preview")>=0) StartCoroutine(VisualsPreview.Run(this,menu,view,Capture));
            else if(Array.IndexOf(Environment.GetCommandLineArgs(),"--integration-preview")>=0) StartCoroutine(IntegrationPreview.Run(face,voice,view,playerAvatar,Capture));
            else if(Array.IndexOf(Environment.GetCommandLineArgs(),"--record-alex")>=0) StartCoroutine(AlexAnimationRecorder.Run(face,voice));
            else if(Array.IndexOf(Environment.GetCommandLineArgs(),"--alex-preview")>=0) StartCoroutine(AlexPerformancePreview.Run(face,voice,view,Capture));
            else if(Array.IndexOf(Environment.GetCommandLineArgs(),"--environment-preview")>=0) StartCoroutine(EnvironmentPreview());
            else StartCoroutine(Connect());
            if(Array.IndexOf(Environment.GetCommandLineArgs(),"--smoke-test")>=0) StartCoroutine(SmokeTest());
        }

        IEnumerator Start()
        {
            GameObject room=null;
            const string scenePath="Assets/PsychologyVR/Scenes/ConsultationLighting.unity";
            Debug.Log("BOUNCE_LOAD available="+Application.CanStreamedLevelBeLoaded(scenePath));
            if(Application.CanStreamedLevelBeLoaded(scenePath))
            {
                var scene=UnityEngine.SceneManagement.SceneManager.GetSceneByPath(scenePath);
                if(!scene.isLoaded)yield return UnityEngine.SceneManagement.SceneManager.LoadSceneAsync(scenePath,UnityEngine.SceneManagement.LoadSceneMode.Additive);
                scene=UnityEngine.SceneManagement.SceneManager.GetSceneByPath(scenePath);
                foreach(var root in scene.GetRootGameObjects())if(root.GetComponent<RoomLighting>()){room=root;break;}
                // Use this scene's environment and probe set for the runtime actors.
                UnityEngine.SceneManagement.SceneManager.SetActiveScene(scene);
                LightProbes.Tetrahedralize();
                var sceneProbes=LightProbes.GetSharedLightProbesForScene(scene);
                Debug.Log("BOUNCE_PROBES scene="+(sceneProbes?sceneProbes.countSelf:0));
                Debug.Log("BOUNCE_LOAD scene="+scene.path+" roots="+scene.rootCount+" room="+(room?room.name:"missing")+" lightmaps="+LightmapSettings.lightmaps.Length+" probes="+(LightmapSettings.lightProbes?LightmapSettings.lightProbes.count:0));
            }
            InitializeSession(room);
            yield return InitializeXR();
        }

        IEnumerator InitializeXR()
        {
            if(Array.IndexOf(Environment.GetCommandLineArgs(),"--desktop")>=0) yield break;
            var manager=UnityEngine.XR.Management.XRGeneralSettings.Instance?.Manager;
            if(!manager) yield break;
            yield return manager.InitializeLoader();
            if(manager.activeLoader!=null)
            {
                manager.StartSubsystems();
                var inputs=new List<XRInputSubsystem>(); SubsystemManager.GetSubsystems(inputs);
                foreach(var subsystem in inputs) subsystem.TrySetTrackingOriginMode(TrackingOriginModeFlags.Floor);
            }
            else Debug.Log("No active headset. Desktop controls remain available.");
        }

        IEnumerator EnvironmentPreview()
        {
            Status="Environment preview";
            // No inference or speech is needed to inspect the room.
            yield return null; yield return null;
            foreach(var renderer in FindObjectsByType<MeshRenderer>(FindObjectsSortMode.None)) Debug.Log("ROOM_RENDERER "+renderer.name+" enabled="+renderer.enabled+" bounds="+renderer.bounds+" materials="+string.Join(",",Array.ConvertAll(renderer.sharedMaterials,m=>m?m.name:"null")));
            var args=Environment.GetCommandLineArgs();int at=Array.IndexOf(args,"--capture-path");
            if(at<0 || at+1>=args.Length) {Application.Quit(2);yield break;}
            Capture(view,args[at+1]);
            var overview=new GameObject("Overview camera").AddComponent<Camera>();
            overview.transform.position=new Vector3(-2.3f,1.9f,-2.6f);overview.transform.LookAt(new Vector3(.2f,1.1f,.9f));overview.fieldOfView=65;
            overview.nearClipPlane=.05f;Capture(overview,args[at+1].Replace(".png","-overview.png"));
            Debug.Log("ENVIRONMENT_PREVIEW_OK");Application.Quit(0);
        }
        static void Capture(Camera camera,string path)
        {
            var target=new RenderTexture(1600,1000,24);
            // A full camera render updates the volume stack before applying colour grading.
            UnityEngine.Rendering.RenderPipeline.SubmitRenderRequest(camera,new UnityEngine.Rendering.RenderPipeline.StandardRequest{destination=target});
            RenderTexture.active=target;var texture=new Texture2D(1600,1000,TextureFormat.RGB24,false);
            texture.ReadPixels(new Rect(0,0,1600,1000),0,0);texture.Apply();File.WriteAllBytes(path,texture.EncodeToPNG());
            RenderTexture.active=null;target.Release();Destroy(target);Destroy(texture);
        }

        IEnumerator SmokeTest()
        {
            float deadline=Time.realtimeSinceStartup+30;
            while(string.IsNullOrEmpty(sessionId) && Time.realtimeSinceStartup<deadline) yield return null;
            if(string.IsNullOrEmpty(sessionId)) { Debug.LogError("SMOKE_FAILED: bridge connection"); Application.Quit(2); yield break; }
            if(IsSpeechAudition)
            {
                SetMenuOpen(true);menu.Render(ConsultationMenu.Page.Session);yield return null;
                var compare=Array.Find(menu.GetComponentsInChildren<UnityEngine.UI.Button>(),button=>button.name=="Compare all");
                if(!compare||!compare.interactable){Debug.LogError("SMOKE_FAILED: audition button unavailable");Application.Quit(3);yield break;}
                compare.onClick.Invoke();
                if(MenuOpen||!busy){Debug.LogError("SMOKE_FAILED: audition button did not start playback");Application.Quit(3);yield break;}
                Debug.Log("AUDITION_BUTTON_OK");
            }
            else Submit("How are you feeling right now?");
            deadline=Time.realtimeSinceStartup+145;
            while(string.IsNullOrEmpty(Subtitle) && busy && Time.realtimeSinceStartup<deadline) yield return null;
            if(string.IsNullOrEmpty(Subtitle)) { Debug.LogError("SMOKE_FAILED: "+Status); Application.Quit(3); yield break; }
            yield return new WaitForSeconds(1);
            // An offscreen render also works when the smoke-test window is hidden.
            var target=new RenderTexture(1440,900,24);
            UnityEngine.Rendering.RenderPipeline.SubmitRenderRequest(view,
                new UnityEngine.Rendering.Universal.UniversalRenderPipeline.SingleCameraRequest{destination=target});
            RenderTexture.active=target;
            var texture=new Texture2D(1440,900,TextureFormat.RGB24,false);
            texture.ReadPixels(new Rect(0,0,1440,900),0,0); texture.Apply();
            var args=Environment.GetCommandLineArgs(); int at=Array.IndexOf(args,"--capture-path");
            if(at>=0 && at+1<args.Length) File.WriteAllBytes(args[at+1],texture.EncodeToPNG());
            Destroy(texture);
            RenderTexture.active=null; target.Release(); Destroy(target);
            bool heardAudio=voice.isPlaying;float maximumJaw=face?face.JawWeight:0;
            deadline=Time.realtimeSinceStartup+120;
            while(busy && Time.realtimeSinceStartup<deadline)
            {heardAudio|=voice.isPlaying;if(face)maximumJaw=Mathf.Max(maximumJaw,face.JawWeight);yield return null;}
            if(busy || !heardAudio || maximumJaw<.05f)
            {Debug.LogError("SMOKE_FAILED: reply did not complete with audible playback and jaw movement");Application.Quit(4);yield break;}
            Debug.Log("SMOKE_PLAYBACK_OK maximumJaw="+maximumJaw+" voicePosition="+voice.transform.position);
            Debug.Log("SMOKE_OK: "+Providers+" | "+Subtitle);
            Application.Quit(0);
        }

        TextMesh Label(string name, Vector3 position, float size, TextAnchor anchor)
        {
            var obj = new GameObject(name); obj.transform.position = position;
            var text = obj.AddComponent<TextMesh>(); text.characterSize = size; text.fontSize = 64;
            text.anchor = anchor; text.alignment = TextAlignment.Center; text.color = new Color(.93f,.96f,.94f);
            return text;
        }

        public bool HasAppearance(string id)=>Array.Exists(appearances,a=>a.id==id&&a.prefab);
        void SpawnCharacter(string id)
        {
            var appearance=Array.Find(appearances,a=>a.id==id&&a.prefab);
            if(appearance==null)throw new InvalidOperationException("Character appearance unavailable: "+id);
            if(actor){actor.SetActive(false);Destroy(actor);}
            actor=Instantiate(appearance.prefab,new Vector3(0,0,1.15f),Quaternion.Euler(0,180,0));actor.name=CurrentScenario.character_name;
            actor.AddComponent<AvatarSkinRendering>().Initialize(NaturalSkin);Bounce?.RegisterAvatar(actor);
            foreach(var animator in actor.GetComponentsInChildren<Animator>())animator.enabled=false;
            Animation animation=null;
            if(appearance.seatedClip){animation=actor.AddComponent<Animation>();animation.AddClip(appearance.seatedClip,"Seated");animation.clip=appearance.seatedClip;animation.wrapMode=WrapMode.Loop;animation.Play("Seated");}
            else CandidateSeatedPose.Apply(actor);
            performance=actor.AddComponent<PerformanceDriver>();performance.seatedAnimation=animation;performance.useStaticSeatedPose=!appearance.seatedClip;
            face=actor.AddComponent<FacialPerformance>();face.body=performance;face.conversationTarget=view.transform;
            var emitter=new GameObject("Character voice");emitter.transform.SetParent(face.Head?face.Head:actor.transform,false);
            voice=emitter.AddComponent<AudioSource>();voice.spatialBlend=1;voice.minDistance=1;voice.maxDistance=8;voice.volume=SpeechVolume;
            ActiveAppearance=id;
        }
        public void SetMenuOpen(bool open)
        {
            if(open && recording){Microphone.End(micDevice);recording=false;if(microphoneClip)Destroy(microphoneClip);Status="Recording discarded. Return to the room to speak.";}
            MenuOpen=open;paused=open;face?.PauseSpeech(open);performance?.PausePerformance(open);if(voice){if(open)voice.Pause();else voice.UnPause();}
            if(open)InputDevices.GetDeviceAtXRNode(XRNode.RightHand).TryGetFeatureValue(CommonUsages.triggerButton,out lastTrigger);
            if(playerAvatar)playerAvatar.AllowDesktopLook=!open;
            menu?.Show(open);
        }
        public void SetVolume(float value){SpeechVolume=Mathf.Clamp01(value);voice.volume=SpeechVolume;PlayerPrefs.SetFloat("SpeechVolume",SpeechVolume);PlayerPrefs.Save();}
        public void SetNaturalSkin(bool enabled,bool save=true)
        {
            NaturalSkin=enabled;
            foreach(var skin in FindObjectsByType<AvatarSkinRendering>())skin.Apply(enabled);
            if(save){PlayerPrefs.SetInt("NaturalSkin",enabled?1:0);PlayerPrefs.Save();}
        }
        public void SetSubtitles(bool value){SubtitlesEnabled=value;PlayerPrefs.SetInt("Subtitles",value?1:0);PlayerPrefs.Save();}
        public void NextMicrophone(){var devices=Microphone.devices;if(devices.Length==0)return;micDevice=devices[(Array.IndexOf(devices,micDevice)+1)%devices.Length];PlayerPrefs.SetString("Microphone",micDevice);PlayerPrefs.Save();}
        public void Recenter()=>playerAvatar?.Recenter();
        public void PreviewEmotion(string name){performance?.PausePerformance(false);performance?.Apply(name,previewIntensity,"none");}
        public void PlaySpeechAudition(string command)
        {
            if(!IsSpeechAudition || !CanSubmit)return;
            input=command;SetMenuOpen(false);Submit(command);
        }
        public void Reconnect(){if(!IsSwitching)StartCoroutine(Connect());}
        void CancelLocal()
        {
            if(recording){Microphone.End(micDevice);recording=false;if(microphoneClip)Destroy(microphoneClip);}
            version++;foreach(var request in activeRequests)request.Abort();activeRequests.Clear();
            if(voice){voice.Stop();if(voice.clip){Destroy(voice.clip);voice.clip=null;}}
            face?.StopSpeech();performance?.StopGesture(true);Subtitle="";busy=false;
        }
        IEnumerator Connect()
        {
            if(IsSwitching)yield break;IsSwitching=true;CancelLocal();int token=version;Status="Connecting…";
            using(var request=UnityWebRequest.Get(serviceUrl+"/health"))
            {
                request.timeout=5;yield return request.SendWebRequest();
                if(request.result!=UnityWebRequest.Result.Success){Status="Local service is offline. Start it, then choose Reconnect in Settings.";IsSwitching=false;sessionId=null;yield break;}
                var health=JsonUtility.FromJson<Health>(request.downloadHandler.text);Providers=$"Dialogue: {health.dialogue_provider} | Voice: {health.tts_provider} | STT: {health.stt_provider}";
            }
            using(var request=UnityWebRequest.Get(serviceUrl+"/catalog"))
            {
                request.timeout=5;yield return request.SendWebRequest();
                if(request.result!=UnityWebRequest.Result.Success){Status="Could not load the character library. Reconnect in Settings.";IsSwitching=false;sessionId=null;yield break;}
                var catalog=JsonUtility.FromJson<ScenarioCatalog>(request.downloadHandler.text);
                if(catalog?.scenarios==null || catalog.scenarios.Length==0){Status="The character library is empty.";IsSwitching=false;sessionId=null;yield break;}
                Catalog=catalog;
            }
            var selected=Catalog.Find(CurrentScenario.id)??Catalog.Find(Catalog.default_scenario_id);
            Reply reply=null;yield return Post("/session",new RequestBody{scenario_id=selected.id},raw=>reply=JsonUtility.FromJson<Reply>(raw));
            if(token!=version){IsSwitching=false;yield break;}
            if(reply!=null)
            {
                sessionId=reply.session_id;bool sameCharacter=CurrentScenario.character_id==selected.character_id;CurrentScenario=selected;
                if(!sameCharacter&&HasAppearance(selected.avatar_id))SpawnCharacter(selected.avatar_id);
                initialEmotion=reply.initial_emotion;initialIntensity=reply.initial_intensity;HasConversation=false;
                performance?.Apply(initialEmotion,initialIntensity,"none");Status="Ready. Choose a character or return to the room to begin.";
            }
            else sessionId=null;
            IsSwitching=false;if(MenuOpen)menu.Render(menu.CurrentPage);
        }
        public void StartScenario(string id,string appearanceId)
        {
            if(!CanSelect)return;
            var entry=Catalog.Find(id);
            if(entry==null||!HasAppearance(appearanceId)){Status="This character's appearance is not installed.";return;}
            StartCoroutine(SwitchScenario(entry,appearanceId));
        }
        IEnumerator SwitchScenario(ScenarioEntry entry,string appearanceId)
        {
            IsSwitching=true;CancelLocal();int token=version;Status="Preparing "+entry.character_name+"…";
            Reply reply=null;yield return Post("/session",new RequestBody{scenario_id=entry.id,replace_session_id=sessionId},raw=>reply=JsonUtility.FromJson<Reply>(raw));
            if(token!=version){IsSwitching=false;yield break;}
            if(reply==null){IsSwitching=false;yield break;}
            sessionId=reply.session_id;CurrentScenario=entry;SpawnCharacter(appearanceId);performance.Apply(reply.initial_emotion,reply.initial_intensity,"none",true);
            initialEmotion=reply.initial_emotion;initialIntensity=reply.initial_intensity;HasConversation=false;
            input="";IsSwitching=false;SetMenuOpen(false);Status="Ready.";Submit("",true);
        }

        IEnumerator Post(string path, RequestBody body, Action<string> onSuccess, bool track=true)
        {
            using (var request = new UnityWebRequest(serviceUrl+path,"POST"))
            {
                request.uploadHandler = new UploadHandlerRaw(Encoding.UTF8.GetBytes(JsonUtility.ToJson(body)));
                request.downloadHandler = new DownloadHandlerBuffer(); request.SetRequestHeader("Content-Type","application/json");
                request.timeout = 150; if(track) activeRequests.Add(request);
                yield return request.SendWebRequest(); if(track) activeRequests.Remove(request);
                if(request.result == UnityWebRequest.Result.Success) onSuccess(request.downloadHandler.text);
                else if(request.error != "Request aborted") Status = "Service error: " + request.downloadHandler.text;
            }
        }

        public void Submit(string text, bool opening=false)
        {
            if(busy || paused || IsSwitching || string.IsNullOrEmpty(sessionId)) return;
            HasConversation=true;
            StartCoroutine(Turn(text,opening));
        }

        IEnumerator Turn(string text, bool opening)
        {
            busy = true; int token = version; Status = CurrentScenario.character_name+" is preparing a reply…";
            Reply reply = null;
            yield return Post("/turn",new RequestBody{session_id=sessionId,text=text,opening=opening},raw=>reply=JsonUtility.FromJson<Reply>(raw));
            if(token != version) yield break;
            if(reply == null || reply.segments == null) { busy=false; yield break; }
            foreach(var segment in reply.segments)
            {
                if(token!=version) yield break;
                AudioClip clip = null;
                if(!string.IsNullOrEmpty(segment.audio_url))
                {
                    using(var request=UnityWebRequestMultimedia.GetAudioClip(serviceUrl+segment.audio_url,AudioType.WAV))
                    {
                        request.timeout=15; activeRequests.Add(request); yield return request.SendWebRequest(); activeRequests.Remove(request);
                        if(token!=version) yield break;
                        if(request.result==UnityWebRequest.Result.Success) clip=DownloadHandlerAudioClip.GetContent(request);
                        else { Status="Speech audio could not be loaded."; busy=false; yield break; }
                    }
                }
                while(paused && token==version) yield return null;
                if(token!=version){if(clip)Destroy(clip);yield break;}
                performance?.BeginBeat(segment);
                yield return PerformancePause(Mathf.Clamp(segment.pause_before_seconds,0,1.5f),token);
                if(token!=version){if(clip)Destroy(clip);yield break;}
                Subtitle=segment.text;
                Status=CurrentScenario.character_name+" is speaking…";
                if(clip)
                {
                    voice.clip=clip;face?.BeginSpeech(voice,segment.mouth_cues);voice.Play();
                    bool gestured=false;float gestureAt=Mathf.Clamp(segment.gesture_at,0,.85f)*clip.length;
                    while((voice.isPlaying || paused) && token==version)
                    {
                        if(!paused && !gestured && voice.time>=gestureAt)
                        {performance?.TriggerGesture(segment.gesture,segment.gesture_duration_seconds);gestured=true;Debug.Log("PERFORMANCE_CUE emotion="+segment.emotion+" gesture="+segment.gesture+" at="+voice.time);}
                        yield return null;
                    }
                    if(token!=version){Destroy(clip);yield break;}
                    face?.StopSpeech();voice.clip=null; Destroy(clip);
                }
                else
                {
                    float duration=Mathf.Max(2,segment.text.Length/15f),offset=Mathf.Clamp(segment.gesture_at,0,.85f)*duration;
                    yield return PerformancePause(offset,token);
                    if(token!=version)yield break;
                    performance?.TriggerGesture(segment.gesture,segment.gesture_duration_seconds);
                    yield return PerformancePause(duration-offset,token);
                }
                if(token!=version)yield break;
                performance?.StopGesture();
                yield return PerformancePause(Mathf.Clamp(segment.hold_after_seconds,0,1.5f),token);
            }
            if(token==version) { busy=false; performance?.StopGesture(); Status="Ready. Hold Space / right A to speak."; }
        }

        public void Interrupt(bool reset)
        {
            if(IsSwitching)return;
            CancelLocal();paused=MenuOpen;busy=true;
            int token=version;
            if(string.IsNullOrEmpty(sessionId)) { busy=false; return; }
            StartCoroutine(Invalidate(reset,token));
        }

        IEnumerator Invalidate(bool reset,int token)
        {
            Status=reset?"Resetting session...":"Stopping reply...";
            bool success=false;
            yield return Post(reset?"/reset":"/interrupt",new RequestBody{session_id=sessionId},raw=>success=true,false);
            if(token!=version) yield break;
            busy=false;
            if(success) { Status=reset?"Session reset. Begin when ready.":"Stopped."; if(reset){performance?.Apply(initialEmotion,initialIntensity,"none");HasConversation=false;} }
        }

        void StartRecording()
        {
            if(recording)return;
            if(busy || paused || MenuOpen || IsSwitching || string.IsNullOrEmpty(sessionId))
            {
                Status=MenuOpen||paused?"Close the menu before holding A to speak.":busy?"Please wait for the reply, or use Menu > Stop reply.":"Reconnect in Settings before speaking.";
                Debug.Log("MIC_BLOCKED busy="+busy+" paused="+paused+" menu="+MenuOpen+" switching="+IsSwitching+" session="+!string.IsNullOrEmpty(sessionId));
                return;
            }
            if(string.IsNullOrEmpty(micDevice)) { Status="No microphone found."; return; }
            try { microphoneClip=Microphone.Start(micDevice,false,40,16000); }
            catch(Exception error) { Status="Microphone could not start. Check the input in Settings.";Debug.LogWarning("MIC_START_FAILED "+error.GetType().Name+" device="+micDevice);return; }
            if(!microphoneClip){Status="Microphone could not start. Check the input in Settings.";Debug.LogWarning("MIC_START_FAILED null clip device="+micDevice);return;}
            recording=true; recordingStarted=Time.realtimeSinceStartup;microphonePeak=0;
            microphoneMeter=new float[256*microphoneClip.channels];
            Debug.Log("MIC_START device="+micDevice+" rate="+microphoneClip.frequency);
            Status="Listening... release Space / right A when finished.";
        }

        IEnumerator PerformancePause(float seconds,int token)
        {
            float elapsed=0;
            while(token==version && (paused || elapsed<seconds))
            {if(!paused)elapsed+=Time.deltaTime;yield return null;}
        }
        void EndRecording()
        {
            if(!recording) return;
            int samples=Microphone.GetPosition(micDevice); Microphone.End(micDevice); recording=false;
            if(!microphoneClip || samples<=3200) { if(microphoneClip)Destroy(microphoneClip);Status=samples<=0?"No microphone data. Check the input in Settings.":"Hold A a little longer while speaking.";Debug.LogWarning("MIC_EMPTY samples="+samples);return; }
            var data=new float[samples*microphoneClip.channels];
            if(!microphoneClip.GetData(data,0)){Destroy(microphoneClip);Status="Microphone audio could not be read. Try another input in Settings.";Debug.LogWarning("MIC_READ_FAILED");return;}
            int channels=microphoneClip.channels, rate=microphoneClip.frequency; Destroy(microphoneClip);
            float peak=0;double energy=0;foreach(float sample in data){peak=Mathf.Max(peak,Mathf.Abs(sample));energy+=sample*sample;}
            Debug.Log("MIC_CAPTURE seconds="+((float)samples/rate).ToString("F2")+" peak="+peak.ToString("F5")+" rms="+Math.Sqrt(energy/data.Length).ToString("F5")+" device="+micDevice);
            if(peak<.0001f){Status="The microphone is silent. Check its mute switch or choose another input in Settings.";return;}
            byte[] bytes;
            using(var stream=new MemoryStream()) using(var writer=new BinaryWriter(stream))
            {
                writer.Write(Encoding.ASCII.GetBytes("RIFF")); writer.Write(36+samples*2); writer.Write(Encoding.ASCII.GetBytes("WAVEfmt "));
                writer.Write(16); writer.Write((short)1); writer.Write((short)1); writer.Write(rate); writer.Write(rate*2);
                writer.Write((short)2); writer.Write((short)16); writer.Write(Encoding.ASCII.GetBytes("data")); writer.Write(samples*2);
                for(int i=0;i<samples;i++) { float value=0; for(int c=0;c<channels;c++) value+=data[i*channels+c]; writer.Write((short)(Mathf.Clamp(value/channels,-1,1)*32767)); }
                bytes=stream.ToArray();
            }
            StartCoroutine(Transcribe(bytes));
        }
        IEnumerator Transcribe(byte[] wav)
        {
            busy=true; int token=version; Status="Transcribing..."; string text=null;
            yield return Post("/transcribe",new RequestBody{wav_base64=Convert.ToBase64String(wav)},raw=>text=JsonUtility.FromJson<Transcript>(raw).text);
            if(token!=version) yield break;
            busy=false;
            Debug.Log("MIC_TRANSCRIPT characters="+(text==null?-1:text.Length));
            if(!string.IsNullOrWhiteSpace(text)) { input=text; Submit(text); }
            else if(text!=null) Status="No speech detected. Try again.";
        }

        void Update()
        {
            if(!menu)return;
            if(!playerAvatar)
            {
            var head=InputDevices.GetDeviceAtXRNode(XRNode.Head);
            bool tracked=head.TryGetFeatureValue(CommonUsages.isTracked,out bool isTracked) && isTracked;
            if(tracked)
            {
                if(head.TryGetFeatureValue(CommonUsages.devicePosition,out Vector3 p)) view.transform.localPosition=p;
                if(head.TryGetFeatureValue(CommonUsages.deviceRotation,out Quaternion q)) view.transform.localRotation=q;
            }
            else
            {
                view.transform.localPosition=new Vector3(0,1.2f,0);
                if(Mouse.current!=null && Mouse.current.rightButton.isPressed)
                { var delta=Mouse.current.delta.ReadValue(); view.transform.Rotate(-delta.y*.08f,delta.x*.08f,0); }
            }
            }
            var keyboard=Keyboard.current;
            if(keyboard!=null)
            {
                if(keyboard.spaceKey.wasPressedThisFrame && GUI.GetNameOfFocusedControl()!="ConversationInput") StartRecording();
                if(keyboard.spaceKey.wasReleasedThisFrame) EndRecording();
                if(keyboard.escapeKey.wasPressedThisFrame) SetMenuOpen(!MenuOpen);
            }
            var controller=InputDevices.GetDeviceAtXRNode(XRNode.RightHand);
            controller.TryGetFeatureValue(CommonUsages.secondaryButton,out bool menuButton);
            if(menuButton&&!menuHeld)SetMenuOpen(!MenuOpen);menuHeld=menuButton;
            controller.TryGetFeatureValue(CommonUsages.primaryButton,out bool held);
            if(held && !controllerHeld) StartRecording(); if(!held && controllerHeld) EndRecording(); controllerHeld=held;
            Vector3 pointerStart=Vector3.zero,pointerDirection=Vector3.forward;
            bool pointing=playerAvatar && playerAvatar.RightPointer(out pointerStart,out pointerDirection);
            controllerRay.enabled=pointing&&MenuOpen;
            if(pointing&&MenuOpen)
            {
                Vector3 start=pointerStart,direction=pointerDirection;
                var hitButton=Physics.Raycast(start,direction,out RaycastHit hit,4,1<<5)?hit.collider.GetComponent<WorldButton>():null;
                menu.Hover(hitButton);controllerRay.SetPosition(0,start);controllerRay.SetPosition(1,hitButton?hit.point:start+direction*2);
                controller.TryGetFeatureValue(CommonUsages.triggerButton,out bool trigger);
                if(trigger&&!lastTrigger)hitButton?.Click();lastTrigger=trigger;
            }
            else{lastTrigger=false;menu.Hover(null);}
            if(recording && Time.realtimeSinceStartup-recordingStarted>=39) EndRecording();
            if(recording && microphoneClip)
            {
                int position=Microphone.GetPosition(micDevice);microphonePeak=0;
                if(position>=256 && microphoneClip.GetData(microphoneMeter,position-256))
                    foreach(float sample in microphoneMeter)microphonePeak=Mathf.Max(microphonePeak,Mathf.Abs(sample));
            }
            subtitleText.text=SubtitlesEnabled&&!MenuOpen?Wrap(Subtitle,55):"";
            subtitleText.transform.rotation=Quaternion.LookRotation(subtitleText.transform.position-view.transform.position);
            if(inputStatusText)
            {
                inputStatusText.text=MenuOpen?"":Wrap(recording?"Listening · "+(microphonePeak>.001f?"signal detected":"no signal yet")+"\nRelease A when finished.":Status,64);
                inputStatusText.color=recording?new Color(.65f,1,.7f):new Color(.82f,.9f,.86f);
                inputStatusText.transform.rotation=Quaternion.LookRotation(inputStatusText.transform.position-view.transform.position);
            }

        }
        bool lastTrigger;
        static string Wrap(string value,int width)
        {
            var builder=new StringBuilder(); int length=0;
            foreach(var word in value.Split(' ')) { if(length+word.Length>width) { builder.Append('\n'); length=0; } builder.Append(word).Append(' '); length+=word.Length+1; }
            return builder.ToString();
        }

        void OnGUI()
        {
            if(!menu||XRSettings.isDeviceActive||MenuOpen)return;
            GUI.Label(new Rect(20,Screen.height-32,700,26),"Esc · Menu    Space · Hold to speak    Right mouse · Look");
        }
        void OnDestroy()
        {
            foreach(var request in activeRequests) request.Abort();
            if(recording) Microphone.End(micDevice);
        }
    }
    public class WorldButton : MonoBehaviour
    {
        public Action Clicked;
        public void Click() { Clicked?.Invoke(); }
    }
}
