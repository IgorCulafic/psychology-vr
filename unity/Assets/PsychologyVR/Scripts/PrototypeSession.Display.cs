using System;
using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.UI;

namespace PsychologyVR
{
    public partial class PrototypeSession
    {
        Canvas desktopDialogue;
        Text desktopSubtitle,desktopStatus;
        Image desktopCaptionBackground;
        public bool Borderless {get;private set;}
        public int DesktopSubtitleSize {get;private set;}=30;
        bool DesktopDisplayActive=>desktopDialogue&&desktopDialogue.gameObject.activeSelf;

        void InitializeDisplay()
        {
            Borderless=Screen.fullScreenMode==FullScreenMode.FullScreenWindow;
            DesktopSubtitleSize=Mathf.Clamp(PlayerPrefs.GetInt("DesktopSubtitleSize",30),22,44);
            var obj=new GameObject("Desktop dialogue",typeof(Canvas),typeof(CanvasScaler));
            obj.transform.SetParent(transform,false);
            desktopDialogue=obj.GetComponent<Canvas>();desktopDialogue.renderMode=RenderMode.ScreenSpaceOverlay;desktopDialogue.sortingOrder=30;
            var scaler=obj.GetComponent<CanvasScaler>();scaler.uiScaleMode=CanvasScaler.ScaleMode.ScaleWithScreenSize;
            scaler.referenceResolution=new Vector2(1920,1080);scaler.matchWidthOrHeight=.5f;
            var panel=new GameObject("Caption background",typeof(RectTransform),typeof(Image));panel.transform.SetParent(obj.transform,false);
            var rect=panel.GetComponent<RectTransform>();rect.anchorMin=new Vector2(.1f,0);rect.anchorMax=new Vector2(.9f,0);rect.pivot=new Vector2(.5f,0);rect.anchoredPosition=new Vector2(0,80);rect.sizeDelta=new Vector2(0,160);
            desktopCaptionBackground=panel.GetComponent<Image>();desktopCaptionBackground.color=new Color(.02f,.03f,.03f,.8f);desktopCaptionBackground.raycastTarget=false;
            desktopSubtitle=DisplayText(panel.transform,"Subtitles",DesktopSubtitleSize);
            var sub=desktopSubtitle.rectTransform;sub.anchorMin=Vector2.zero;sub.anchorMax=Vector2.one;sub.offsetMin=new Vector2(24,12);sub.offsetMax=new Vector2(-24,-12);
            desktopStatus=DisplayText(obj.transform,"Speech status",22);
            var statusRect=desktopStatus.rectTransform;statusRect.anchorMin=new Vector2(.1f,0);statusRect.anchorMax=new Vector2(.9f,0);statusRect.pivot=new Vector2(.5f,0);statusRect.anchoredPosition=new Vector2(0,25);statusRect.sizeDelta=new Vector2(0,40);
            // Automated captures keep their explicit command-line dimensions.
            bool diagnostic=Array.Exists(Environment.GetCommandLineArgs(),a=>a.StartsWith("--")&&a!="--desktop");
            if(!UnityEngine.XR.XRSettings.isDeviceActive&&!diagnostic)
                SetBorderless(PlayerPrefs.GetInt("BorderlessFullscreen",1)==1);
            if(!UnityEngine.XR.XRSettings.isDeviceActive){QualitySettings.vSyncCount=0;Application.targetFrameRate=60;}
            UpdateDesktopDisplay();
        }
        Text DisplayText(Transform parent,string name,int size)
        {
            var obj=new GameObject(name,typeof(RectTransform),typeof(Text));obj.transform.SetParent(parent,false);
            var text=obj.GetComponent<Text>();text.font=Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");text.fontSize=size;text.color=Color.white;text.alignment=TextAnchor.MiddleCenter;text.raycastTarget=false;
            text.horizontalOverflow=HorizontalWrapMode.Wrap;text.verticalOverflow=VerticalWrapMode.Truncate;return text;
        }
        public void SetBorderless(bool enabled)
        {
            if(UnityEngine.XR.XRSettings.isDeviceActive)return;
            var resolution=Screen.currentResolution;
            int width=enabled?resolution.width:Mathf.Min(1440,resolution.width-80);
            int height=enabled?resolution.height:Mathf.Min(900,resolution.height-100);
            Screen.SetResolution(width,height,enabled?FullScreenMode.FullScreenWindow:FullScreenMode.Windowed);
            Borderless=enabled;
            PlayerPrefs.SetInt("BorderlessFullscreen",enabled?1:0);PlayerPrefs.Save();
        }
        public void SetDesktopSubtitleSize(int size)
        {
            DesktopSubtitleSize=Mathf.Clamp(size,22,44);if(desktopSubtitle)desktopSubtitle.fontSize=DesktopSubtitleSize;
            PlayerPrefs.SetInt("DesktopSubtitleSize",DesktopSubtitleSize);PlayerPrefs.Save();
        }
        void UpdateDesktopDisplay()
        {
            if(!desktopDialogue)return;
            bool desktop=!UnityEngine.XR.XRSettings.isDeviceActive;desktopDialogue.gameObject.SetActive(desktop);
            if(!desktop)return;
            if(Keyboard.current?.f11Key.wasPressedThisFrame==true){SetBorderless(!Borderless);if(MenuOpen)menu.Render(menu.CurrentPage);}
            desktopSubtitle.text=SubtitlesEnabled&&!MenuOpen?Subtitle:"";
            desktopCaptionBackground.rectTransform.sizeDelta=new Vector2(0,Mathf.Clamp(desktopSubtitle.preferredHeight+24,100,360));
            desktopCaptionBackground.enabled=!string.IsNullOrWhiteSpace(desktopSubtitle.text);
            desktopStatus.text=MenuOpen?"":recording?"Listening · release Space to send":Status;
        }
    }
}
