using System;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.InputSystem.UI;
using UnityEngine.UI;

namespace PsychologyVR
{
    public class ConsultationMenu:MonoBehaviour
    {
        public enum Page {Session,Characters,Settings,Preview,Visuals,Rendering,Models}
        public Page CurrentPage {get;private set;}
        public bool Visible=>canvas && canvas.gameObject.activeSelf;
        public bool DescriptionsHidden {get;private set;}
        PrototypeSession session;Camera view;Canvas canvas;RectTransform content;Font font;
        Text status,transcript,volumeLabel,micLabel;InputField message;
        string pending,appearance;int characterPage;
        WorldButton hovered;
        readonly List<(Button button,Func<bool> enabled)> conditions=new List<(Button,Func<bool>)>();
        static readonly Color Ink=new Color(.89f,.92f,.87f),Muted=new Color(.61f,.70f,.65f),Panel=new Color(.055f,.105f,.093f,.98f),Card=new Color(.095f,.16f,.139f),Accent=new Color(.64f,.79f,.55f);
        public void Initialize(PrototypeSession owner,Camera camera)
        {
            session=owner;view=camera;font=Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
            DescriptionsHidden=PlayerPrefs.GetInt("HideCharacterDescriptions",0)==1;
            if(!EventSystem.current){var events=new GameObject("Menu input",typeof(EventSystem));events.AddComponent<InputSystemUIInputModule>().AssignDefaultActions();}
            var obj=new GameObject("Consultation menu",typeof(RectTransform),typeof(Canvas),typeof(GraphicRaycaster));obj.layer=5;
            obj.transform.SetParent(transform,false);canvas=obj.GetComponent<Canvas>();canvas.renderMode=RenderMode.WorldSpace;canvas.worldCamera=view;canvas.sortingOrder=20;
            var rect=obj.GetComponent<RectTransform>();rect.sizeDelta=new Vector2(960,760);rect.localScale=Vector3.one*.0012f;
            pending=session.CurrentScenario.id;appearance=session.CurrentScenario.avatar_id;
            canvas.gameObject.SetActive(false);
        }
        public void Show(bool visible)
        {
            Hover(null);canvas.gameObject.SetActive(visible);
            if(!visible){EventSystem.current?.SetSelectedGameObject(null);return;}
            Reposition();Render(CurrentPage);
        }
        public void Reposition()
        {
            Vector3 forward=Vector3.ProjectOnPlane(view.transform.forward,Vector3.up).normalized;
            if(forward.sqrMagnitude<.1f)forward=Vector3.forward;
            canvas.transform.position=view.transform.position+forward*1.08f-Vector3.up*.02f;
            canvas.transform.rotation=Quaternion.LookRotation(forward,Vector3.up);
        }
        public void Render(Page page)
        {
            CurrentPage=page;Hover(null);conditions.Clear();status=transcript=volumeLabel=micLabel=null;message=null;
            if(content){content.gameObject.SetActive(false);Destroy(content.gameObject);}
            content=Rect("Menu content",canvas.transform,0,0,960,760);content.gameObject.AddComponent<Image>().color=Panel;
            TextAt("CONSULTATION",32,24,580,36,28,Ink,FontStyle.Bold);
            TextAt("A space for listening",34,67,580,25,18,Muted);
            ButtonAt("Close  ×",800,28,128,48,()=>session.SetMenuOpen(false));
            string[] names={"Session","Characters & situations","Settings"};
            for(int i=0;i<3;i++){int index=i;ButtonAt(names[i],32+i*300,112,288,48,()=>Render((Page)index),active:(int)page==i);}
            if(page==Page.Session)SessionPage();else if(page==Page.Characters)CharactersPage();else if(page==Page.Settings)SettingsPage();else if(page==Page.Visuals)VisualsPage();else if(page==Page.Rendering)RenderingPage();else if(page==Page.Models)ModelsPage();else PreviewPage();
            TextAt("Esc / right B · Menu     Left X · Recenter",34,708,710,24,17,Muted);
            TextAt("PC VR",820,708,108,24,17,Muted);
            Refresh();
        }
        void SessionPage()
        {
            var current=session.CurrentScenario;
            TextAt(current.character_name+"  /  "+SituationTitle(current),34,188,890,38,27,Ink,FontStyle.Bold);
            status=TextAt("",34,238,890,48,20,Accent);
            Box(32,300,896,145,Card);TextAt("CONVERSATION",50,312,800,24,15,Muted);
            transcript=TextAt("",50,342,860,92,22,Ink);
            if(session.IsSpeechAudition)
            {
                TextAt("RECORDED VOICE TEST · select a clip with the right trigger",34,455,890,28,18,Muted);
                string[] commands={"neutral","angry","closer","compare"};
                string[] labels={"Neutral","Angry","Milder anger","Compare all"};
                for(int i=0;i<commands.Length;i++){string command=commands[i];ButtonAt(labels[i],32+i*226,502,214,56,()=>session.PlaySpeechAudition(command),()=>session.CanSubmit);}
            }
            else if(!UnityEngine.XR.XRSettings.isDeviceActive)
            {
                message=InputAt(32,465,724,84,session.Draft);message.onValueChanged.AddListener(value=>session.Draft=value);
                ButtonAt("Send",772,465,156,84,()=>{session.SetMenuOpen(false);session.Submit(session.Draft);},()=>session.CanSubmit&&!string.IsNullOrWhiteSpace(session.Draft));
                TextAt("Or return to the room and hold Space / right A to speak.",34,560,890,28,17,Muted);
            }
            else TextAt("Return to the room. Hold right A to speak, then release to send.",34,477,890,76,24,Ink);
            ButtonAt("Return to room",32,620,288,54,()=>session.SetMenuOpen(false),active:true);
            ButtonAt(session.HasConversation?"Restart conversation":"Begin conversation",332,620,288,54,()=>session.StartScenario(current.id,session.ActiveAppearance),()=>session.CanSelect);
            ButtonAt("Stop reply",632,620,296,54,()=>session.Interrupt(false),()=>session.IsBusy);
        }
        void CharactersPage()
        {
            var catalog=session.Catalog;
            if(catalog.Find(pending)==null)pending=session.CurrentScenario.id;
            var selected=catalog.Find(pending);
            var characters=catalog.scenarios.GroupBy(s=>s.character_id).Select(g=>g.First()).ToArray();
            characterPage=Mathf.Clamp(characterPage,0,Mathf.Max(0,(characters.Length-1)/4));
            TextAt("CHOOSE A CHARACTER",34,188,310,28,17,Muted);
            for(int i=characterPage*4;i<Mathf.Min(characters.Length,characterPage*4+4);i++)
            {
                var entry=characters[i];ButtonAt(entry.character_name+"  ·  "+entry.age,32,232+(i%4)*66,274,54,()=>{pending=entry.id;appearance=entry.avatar_id;Render(Page.Characters);},active:entry.character_id==selected.character_id);
            }
            if(characters.Length>4){ButtonAt("Previous",32,512,132,40,()=>{characterPage--;Render(Page.Characters);},()=>characterPage>0);ButtonAt("Next",174,512,132,40,()=>{characterPage++;Render(Page.Characters);},()=>characterPage<(characters.Length-1)/4);}
            ButtonAt(DescriptionsHidden?"Show descriptions":"Hide descriptions",32,556,274,54,()=>SetDescriptionsHidden(!DescriptionsHidden),active:DescriptionsHidden);
            Box(326,185,602,425,Card);
            var texture=Resources.Load<Texture2D>("Menu/"+appearance)??Resources.Load<Texture2D>("Menu/"+selected.character_id);
            if(texture){var photo=Rect("Portrait",content,346,205,144,144).gameObject.AddComponent<RawImage>();photo.texture=texture;photo.uvRect=selected.character_id=="alex"?new Rect(.28f,.16f,.44f,.7f):new Rect(0,0,1,1);photo.raycastTarget=false;}
            TextAt(selected.character_name,510,207,396,36,31,Ink,FontStyle.Bold);
            TextAt(selected.age+" years old",512,252,390,30,19,Muted);
            TextAt(DescriptionsHidden?"Student view":selected.focus,512,291,388,56,19,Accent);
            var situations=catalog.scenarios.Where(s=>s.character_id==selected.character_id).ToArray();
            int at=Array.FindIndex(situations,s=>s.id==pending);
            TextAt("SITUATION  "+(at+1)+" / "+situations.Length,346,369,550,24,15,Muted);
            TextAt(SituationTitle(selected),346,402,452,42,25,Ink,FontStyle.Bold);
            ButtonAt("‹",810,397,42,44,()=>{var s=situations[(at-1+situations.Length)%situations.Length];pending=s.id;appearance=s.avatar_id;Render(Page.Characters);},()=>situations.Length>1);
            ButtonAt("›",864,397,42,44,()=>{var s=situations[(at+1)%situations.Length];pending=s.id;appearance=s.avatar_id;Render(Page.Characters);},()=>situations.Length>1);
            TextAt(DescriptionsHidden?"Discover their story through conversation.":selected.summary,346,450,560,106,19,Ink);
            var look=session.Appearances.FirstOrDefault(a=>a.id==appearance);
            ButtonAt("Appearance: "+(look?.label??"Unavailable"),346,565,560,32,()=>{int n=Array.FindIndex(session.Appearances,a=>a.id==appearance);appearance=session.Appearances[(n+1)%session.Appearances.Length].id;Render(Page.Characters);},()=>session.Appearances.Length>1);
            ButtonAt("Start new conversation",326,626,602,54,()=>session.StartScenario(pending,appearance),()=>session.CanSelect&&session.HasAppearance(appearance),active:true);
            status=TextAt("",34,623,274,67,17,Muted);
        }
        void SettingsPage()
        {
            TextAt("Make yourself comfortable",34,188,880,36,27,Ink,FontStyle.Bold);
            Box(32,246,896,82,Card);volumeLabel=TextAt("",50,270,620,36,24,Ink);
            ButtonAt("−",770,264,62,46,()=>{session.SetVolume(session.SpeechVolume-.1f);Refresh();});ButtonAt("+",848,264,62,46,()=>{session.SetVolume(session.SpeechVolume+.1f);Refresh();});
            ButtonAt("Subtitles: "+(session.SubtitlesEnabled?"On":"Off"),32,344,436,58,()=>{session.SetSubtitles(!session.SubtitlesEnabled);Render(Page.Settings);});
            ButtonAt("Recenter seated view",490,344,438,58,()=>{session.Recenter();Show(true);});
            Box(32,424,896,92,Card);TextAt("MICROPHONE",50,436,750,20,15,Muted);
            micLabel=TextAt("",50,465,742,42,18,Ink);ButtonAt("Next",812,445,98,50,()=>{session.NextMicrophone();Refresh();},()=>!session.IsRecording&&Microphone.devices.Length>1);
            ButtonAt("Reconnect",32,540,284,52,()=>session.Reconnect(),()=>!session.IsSwitching);
            ButtonAt("Character preview",338,540,284,52,()=>Render(Page.Preview));
            ButtonAt("Quit game",644,540,284,52,()=>Application.Quit());
            ButtonAt("Visual style",32,608,284,48,()=>Render(Page.Visuals));
            ButtonAt("Dialogue model",338,608,284,48,()=>{Render(Page.Models);session.RefreshModels();});
            status=TextAt("",644,606,284,42,15,Accent);
            TextAt("Right A / Space: hold to speak\nRight trigger: select    Grip: close your fingers",34,652,884,45,17,Muted);
        }
        void PreviewPage()
        {
            TextAt("Character performance preview",34,188,850,36,26,Ink,FontStyle.Bold);
            TextAt("Intensity: "+Mathf.RoundToInt(session.PreviewIntensity*100)+"%",34,244,620,36,22,Ink);
            ButtonAt("−",770,234,62,46,()=>{session.PreviewIntensity=Mathf.Clamp01(session.PreviewIntensity-.1f);Render(Page.Preview);});ButtonAt("+",848,234,62,46,()=>{session.PreviewIntensity=Mathf.Clamp01(session.PreviewIntensity+.1f);Render(Page.Preview);});
            var moods=EmotionLibrary.Catalog.emotions;
            for(int i=0;i<moods.Length;i++){var mood=moods[i];ButtonAt(mood.label,32+(i%4)*226,300+(i/4)*56,214,44,()=>{session.PreviewEmotion(mood.name);session.SetMenuOpen(false);});}
            TextAt(session.Providers,34,602,890,42,16,Muted);
            ButtonAt("Back to settings",32,650,896,38,()=>Render(Page.Settings));
        }
        void ModelsPage()
        {
            TextAt("Dialogue model",34,188,880,36,27,Ink,FontStyle.Bold);
            TextAt("Changes apply between replies. Stop the current reply first. Your conversation is kept.",34,235,880,48,18,Muted);
            var models=session.Models;
            if(models?.models!=null)for(int i=0;i<models.models.Length;i++)
            {
                var model=models.models[i];float y=300+i*90;
                ButtonAt(model.label+(models.current==model.id?"  ✓":!model.installed?" (not installed)":""),32,y,436,58,()=>session.ChangeModel(model.id),()=>session.CanChangeModel&&model.installed&&models.enabled&&!models.switching&&models.current!=model.id,active:models.current==model.id);
                TextAt(model.description,490,y,438,70,18,Muted);
            }
            else TextAt("Loading model settings…",34,300,880,40,22,Ink);
            status=TextAt("",34,582,880,60,17,Accent);
            ButtonAt("Back to settings",32,650,896,38,()=>Render(Page.Settings));
        }
        void VisualsPage()
        {
            var visuals=session.Visuals;
            TextAt("Light, colour and atmosphere",34,188,880,36,27,Ink,FontStyle.Bold);
            for(int i=0;i<ConsultationVisuals.Names.Length;i++)
            {
                int preset=i;
                ButtonAt(ConsultationVisuals.Names[i],32+i*226,250,214,56,()=>{visuals.Select(preset,visuals.Strength,visuals.Glow);Render(Page.Visuals);},active:visuals.Preset==i);
            }
            Box(32,330,896,100,Card);
            TextAt(ConsultationVisuals.Descriptions[visuals.Preset],50,347,860,70,22,Ink);
            TextAt("Filter strength  ·  "+Mathf.RoundToInt(visuals.Strength*100)+"%",34,460,710,36,24,Ink);
            ButtonAt("−",770,450,62,46,()=>{visuals.Select(visuals.Preset,visuals.Strength-.1f,visuals.Glow);Render(Page.Visuals);},()=>visuals.Preset!=0&&visuals.Strength>0);
            ButtonAt("+",848,450,62,46,()=>{visuals.Select(visuals.Preset,visuals.Strength+.1f,visuals.Glow);Render(Page.Visuals);},()=>visuals.Preset!=0&&visuals.Strength<1);
            ButtonAt("Soft glow: "+(visuals.Glow?"On":"Off"),32,522,436,56,()=>{visuals.Select(visuals.Preset,visuals.Strength,!visuals.Glow);Render(Page.Visuals);},()=>visuals.Preset!=0);
            ButtonAt("View room",490,522,438,56,()=>session.SetMenuOpen(false),active:true);
            if(session.Room)ButtonAt("Room detail: "+(session.Room.Enhanced?"Enhanced":"Original"),32,590,436,44,()=>{session.Room.SetEnhanced(!session.Room.Enhanced);Render(Page.Visuals);});
            ButtonAt("Lighting and skin",490,590,438,44,()=>Render(Page.Rendering));
            ButtonAt("Back to settings",32,650,896,38,()=>Render(Page.Settings));
        }
        void Update(){if(Visible)Refresh();}
        void RenderingPage()
        {
            TextAt("Lighting and skin",34,188,880,36,27,Ink,FontStyle.Bold);
            ButtonAt("Bounced lighting: "+(session.Bounce&&session.Bounce.Active?"On":"Off"),32,254,896,58,()=>{session.Bounce.SetRequested(!session.Bounce.Requested);Render(Page.Rendering);},()=>session.Bounce&&session.Bounce.Available&&session.Room.Enhanced);
            TextAt("Soft indirect light from the room's surfaces. Uses Enhanced room detail.",34,330,890,64,22,Muted);
            ButtonAt("Skin shading: "+(session.NaturalSkin?"Natural":"Original"),32,420,896,58,()=>{session.SetNaturalSkin(!session.NaturalSkin);Render(Page.Rendering);});
            TextAt("Less uniform shine on the jumper character's face and hands.",34,496,890,64,22,Muted);
            ButtonAt("View room",32,588,896,48,()=>session.SetMenuOpen(false),active:true);
            ButtonAt("Back to visual style",32,650,896,38,()=>Render(Page.Visuals));
        }
        public void SetDescriptionsHidden(bool hidden)
        {
            DescriptionsHidden=hidden;PlayerPrefs.SetInt("HideCharacterDescriptions",hidden?1:0);PlayerPrefs.Save();
            if(Visible)Render(CurrentPage);
        }
        string SituationTitle(ScenarioEntry entry)
        {
            if(!DescriptionsHidden)return entry.title;
            var situations=session.Catalog.scenarios.Where(s=>s.character_id==entry.character_id).ToArray();
            return "Case "+(Array.FindIndex(situations,s=>s.id==entry.id)+1);
        }
        void Refresh()
        {
            if(status)status.text=CurrentPage==Page.Session&&session.IsBusy&&!session.IsSwitching?"Conversation paused. Return to the room to continue.":session.Status;
            if(transcript)transcript.text=string.IsNullOrWhiteSpace(session.Subtitle)?"Take a moment. Begin when you are ready.":session.Subtitle;
            if(volumeLabel)volumeLabel.text="Speech volume  ·  "+Mathf.RoundToInt(session.SpeechVolume*100)+"%";
            if(micLabel)micLabel.text=session.MicrophoneName;
            foreach(var item in conditions)if(item.button)item.button.interactable=item.enabled();
        }
        public void Hover(WorldButton target)
        {
            if(target==hovered)return;
            var data=new PointerEventData(EventSystem.current);
            if(hovered)hovered.GetComponent<Button>()?.OnPointerExit(data);
            hovered=target;if(hovered)hovered.GetComponent<Button>()?.OnPointerEnter(data);
        }
        RectTransform Rect(string name,Transform parent,float x,float y,float w,float h)
        {
            var go=new GameObject(name,typeof(RectTransform));go.layer=5;var r=go.GetComponent<RectTransform>();r.SetParent(parent,false);r.anchorMin=r.anchorMax=new Vector2(0,1);r.pivot=new Vector2(0,1);r.anchoredPosition=new Vector2(x,-y);r.sizeDelta=new Vector2(w,h);return r;
        }
        void Box(float x,float y,float w,float h,Color color)=>Rect("Card",content,x,y,w,h).gameObject.AddComponent<Image>().color=color;
        Text TextAt(string value,float x,float y,float w,float h,int size,Color color,FontStyle style=FontStyle.Normal,Transform parent=null)
        {
            var t=Rect(value,parent?parent:content,x,y,w,h).gameObject.AddComponent<Text>();t.font=font;t.text=value;t.fontSize=size;t.color=color;t.fontStyle=style;t.raycastTarget=false;t.horizontalOverflow=HorizontalWrapMode.Wrap;t.verticalOverflow=VerticalWrapMode.Truncate;return t;
        }
        Button ButtonAt(string label,float x,float y,float w,float h,Action action,Func<bool> enabled=null,bool active=false)
        {
            var r=Rect(label,content,x,y,w,h);var image=r.gameObject.AddComponent<Image>();image.color=active?Accent:Card;
            var button=r.gameObject.AddComponent<Button>();button.targetGraphic=image;var colors=button.colors;colors.highlightedColor=new Color(.82f,.93f,.75f);colors.pressedColor=new Color(.58f,.73f,.53f);colors.disabledColor=new Color(.4f,.4f,.4f,.55f);button.colors=colors;
            button.onClick.AddListener(()=>action());
            var text=TextAt(label,12,0,w-24,h,20,active?Panel:Ink,FontStyle.Normal,r);text.alignment=TextAnchor.MiddleCenter;
            var collider=r.gameObject.AddComponent<BoxCollider>();collider.size=new Vector3(w,h,8);collider.center=new Vector3(w*.5f,-h*.5f,0);
            r.gameObject.AddComponent<WorldButton>().Clicked=()=>{if(button.interactable)button.onClick.Invoke();};
            if(enabled!=null)conditions.Add((button,enabled));return button;
        }
        InputField InputAt(float x,float y,float w,float h,string text)
        {
            var r=Rect("Message",content,x,y,w,h);r.gameObject.AddComponent<Image>().color=new Color(.15f,.22f,.19f);
            var field=r.gameObject.AddComponent<InputField>();field.textComponent=TextAt("",16,12,w-32,h-24,22,Ink,parent:r);
            field.placeholder=TextAt("Type a message…",16,12,w-32,h-24,22,Muted,parent:r);field.lineType=InputField.LineType.MultiLineNewline;field.characterLimit=2000;field.text=text;return field;
        }
    }
}
