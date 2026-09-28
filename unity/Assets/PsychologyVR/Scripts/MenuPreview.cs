using System;
using System.Collections;
using System.IO;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.UI;
namespace PsychologyVR
{
    public static class MenuPreview
    {
        [Serializable] class Report {public bool startupOpen,desktopClick,controllerRay,pauseFreezes,resumeAdvances,switchedAppearance,restartedScenario,hiddenAfterStart,settingsPersisted,passed;public int scenarios;}
        public static IEnumerator Run(PrototypeSession session,ConsultationMenu menu,Camera view,Action<Camera,string> capture)
        {
            var args=Environment.GetCommandLineArgs();int at=Array.IndexOf(args,"--capture-path");
            if(at<0){Debug.LogError("MENU_PREVIEW_FAILED: capture path missing");Application.Quit(2);yield break;}
            string folder=Path.GetDirectoryName(args[at+1]);Directory.CreateDirectory(folder);
            if(Array.IndexOf(args,"--models-preview")>=0)
            {
                float until=Time.realtimeSinceStartup+30;
                while(!session.CanSelect&&Time.realtimeSinceStartup<until)yield return null;
                menu.Render(ConsultationMenu.Page.Settings);
                var modelButton=Array.Find(menu.GetComponentsInChildren<Button>(),b=>b.name=="Dialogue model");
                modelButton.onClick.Invoke();
                while(session.Models==null&&Time.realtimeSinceStartup<until)yield return null;
                yield return null;yield return new WaitForEndOfFrame();
                bool passed=session.Models?.models?.Length==3&&menu.CurrentPage==ConsultationMenu.Page.Models;
                capture(view,Path.Combine(folder,"menu-models.png"));
                Debug.Log(passed?"MODEL_MENU_OK":"MODEL_MENU_FAILED");Application.Quit(passed?0:4);yield break;
            }
            if(Array.IndexOf(args,"--descriptions-preview")>=0)
            {
                yield return DescriptionPreview(session,menu,view,capture,folder);yield break;
            }
            float deadline=Time.realtimeSinceStartup+30;
            while(!session.CanSelect&&Time.realtimeSinceStartup<deadline)yield return null;
            if(!session.CanSelect){Debug.LogError("MENU_PREVIEW_FAILED: service unavailable");Application.Quit(3);yield break;}
            yield return new WaitForEndOfFrame();var report=new Report{startupOpen=session.MenuOpen,scenarios=session.Catalog.scenarios.Length};
            capture(view,Path.Combine(folder,"menu-session.png"));
            Button Find(string name)=>Array.Find(menu.GetComponentsInChildren<Button>(),b=>b.name==name);
            var chooser=Find("Characters & situations");
            var mouse=new PointerEventData(EventSystem.current){button=PointerEventData.InputButton.Left,position=view.WorldToScreenPoint(chooser.GetComponent<BoxCollider>().bounds.center)};
            var hits=new List<RaycastResult>();EventSystem.current.RaycastAll(mouse,hits);
            if(hits.Count>0&&hits[0].gameObject==chooser.gameObject)ExecuteEvents.Execute(hits[0].gameObject,mouse,ExecuteEvents.pointerClickHandler);
            yield return null;yield return new WaitForEndOfFrame();report.desktopClick=menu.CurrentPage==ConsultationMenu.Page.Characters;
            capture(view,Path.Combine(folder,"menu-characters.png"));
            Find("Appearance: Jumper").onClick.Invoke();yield return null;yield return new WaitForEndOfFrame();capture(view,Path.Combine(folder,"menu-original-appearance.png"));
            Find("Appearance: Original Alex").onClick.Invoke();yield return null;
            var settings=Find("Settings");var target=settings.GetComponent<BoxCollider>().bounds.center;
            Physics.SyncTransforms();
            if(Physics.Raycast(view.transform.position,(target-view.transform.position).normalized,out var hit,3,1<<5))
            {var button=hit.collider.GetComponent<WorldButton>();report.controllerRay=button&&button.gameObject==settings.gameObject;if(button)button.Click();}
            yield return null;yield return new WaitForEndOfFrame();capture(view,Path.Combine(folder,"menu-settings.png"));
            float originalVolume=session.SpeechVolume;bool originalSubtitles=session.SubtitlesEnabled;
            session.SetVolume(.7f);session.SetSubtitles(false);report.settingsPersisted=Mathf.Abs(PlayerPrefs.GetFloat("SpeechVolume")-.7f)<.01f&&PlayerPrefs.GetInt("Subtitles")==0;
            session.SetVolume(originalVolume);session.SetSubtitles(originalSubtitles);
            session.StartScenario(session.CurrentScenario.id,"original-alex");
            deadline=Time.realtimeSinceStartup+45;
            while((session.IsSwitching||!session.IsBusy)&&Time.realtimeSinceStartup<deadline)yield return null;
            var voice=Array.Find(UnityEngine.Object.FindObjectsByType<AudioSource>(FindObjectsSortMode.None),a=>a.gameObject.name=="Character voice");
            while((!voice||!voice.isPlaying)&&Time.realtimeSinceStartup<deadline){voice=Array.Find(UnityEngine.Object.FindObjectsByType<AudioSource>(FindObjectsSortMode.None),a=>a.gameObject.name=="Character voice");yield return null;}
            report.switchedAppearance=session.ActiveAppearance=="original-alex";
            report.hiddenAfterStart=!session.MenuOpen;
            if(voice&&voice.isPlaying)
            {
                session.SetMenuOpen(true);float t=voice.time;yield return new WaitForSecondsRealtime(.3f);report.pauseFreezes=Mathf.Abs(voice.time-t)<.03f;
                session.SetMenuOpen(false);yield return new WaitForSecondsRealtime(.3f);report.resumeAdvances=voice.time>t+.1f;
            }
            session.SetMenuOpen(true);session.StartScenario(session.CurrentScenario.id,"jumper");
            deadline=Time.realtimeSinceStartup+45;while((session.IsSwitching||session.ActiveAppearance!="jumper"||string.IsNullOrEmpty(session.Subtitle))&&Time.realtimeSinceStartup<deadline)yield return null;
            report.restartedScenario=session.ActiveAppearance=="jumper"&&!string.IsNullOrEmpty(session.Subtitle);
            yield return new WaitForSeconds(.3f);yield return new WaitForEndOfFrame();capture(view,Path.Combine(folder,"menu-closed-room.png"));
            report.passed=report.startupOpen&&report.desktopClick&&report.controllerRay&&report.pauseFreezes&&report.resumeAdvances&&report.switchedAppearance&&report.restartedScenario&&report.hiddenAfterStart&&report.settingsPersisted;
            File.WriteAllText(Path.Combine(folder,"menu-check.json"),JsonUtility.ToJson(report,true));Debug.Log(report.passed?"MENU_PREVIEW_OK":"MENU_PREVIEW_FAILED");Application.Quit(report.passed?0:4);
        }
        [Serializable] class DescriptionReport {public bool hiddenPicker,hiddenSession,staysHiddenOnReopen,preferenceSaved,restoresDescriptions,passed;}
        static IEnumerator DescriptionPreview(PrototypeSession session,ConsultationMenu menu,Camera view,Action<Camera,string> capture,string folder)
        {
            bool original=menu.DescriptionsHidden;var entry=session.CurrentScenario;var report=new DescriptionReport();
            bool Has(string value)=>Array.Exists(menu.GetComponentsInChildren<Text>(),t=>t.text.Contains(value));
            bool NoSpoilers()=>!Has(entry.title)&&!Has(entry.summary)&&!Has(entry.focus);
            menu.Render(ConsultationMenu.Page.Characters);menu.SetDescriptionsHidden(false);
            yield return null;yield return new WaitForEndOfFrame();
            var hide=Array.Find(menu.GetComponentsInChildren<Button>(),b=>b.name=="Hide descriptions");hide.onClick.Invoke();
            yield return null;yield return new WaitForEndOfFrame();
            report.hiddenPicker=NoSpoilers()&&Has("Case 1")&&Has(entry.character_name);
            report.preferenceSaved=PlayerPrefs.GetInt("HideCharacterDescriptions")==1;
            capture(view,Path.Combine(folder,"student-picker.png"));
            session.SetMenuOpen(false);session.SetMenuOpen(true);
            yield return null;report.staysHiddenOnReopen=NoSpoilers();
            menu.Render(ConsultationMenu.Page.Session);yield return null;yield return new WaitForEndOfFrame();
            report.hiddenSession=NoSpoilers()&&Has("Case 1");capture(view,Path.Combine(folder,"student-session.png"));
            menu.Render(ConsultationMenu.Page.Characters);
            var show=Array.Find(menu.GetComponentsInChildren<Button>(),b=>b.name=="Show descriptions");show.onClick.Invoke();
            yield return null;yield return new WaitForEndOfFrame();
            report.restoresDescriptions=Has(entry.title)&&Has(entry.summary)&&Has(entry.focus);
            capture(view,Path.Combine(folder,"descriptions-visible.png"));
            menu.SetDescriptionsHidden(original);
            report.passed=report.hiddenPicker&&report.hiddenSession&&report.staysHiddenOnReopen&&report.preferenceSaved&&report.restoresDescriptions;
            File.WriteAllText(Path.Combine(folder,"description-check.json"),JsonUtility.ToJson(report,true));
            Debug.Log(report.passed?"DESCRIPTION_PREVIEW_OK":"DESCRIPTION_PREVIEW_FAILED");Application.Quit(report.passed?0:4);
        }
    }
}
