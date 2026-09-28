using System;
using System.Collections;
using UnityEngine;
using UnityEngine.Networking;

namespace PsychologyVR
{
    [Serializable] public class DialogueModelEntry { public string id,label,description; public bool installed; }
    [Serializable] public class DialogueModelStatus { public string current,target,error; public bool switching,enabled; public DialogueModelEntry[] models; }
    public partial class PrototypeSession
    {
        public DialogueModelStatus Models {get;private set;}
        public bool CanChangeModel=>!IsSwitching&&!busy&&!recording;
        public void RefreshModels()=>StartCoroutine(ReadModels());
        IEnumerator ReadModels()
        {
            using(var request=UnityWebRequest.Get(serviceUrl+"/models"))
            {
                request.timeout=5;yield return request.SendWebRequest();
                if(request.result==UnityWebRequest.Result.Success)Models=JsonUtility.FromJson<DialogueModelStatus>(request.downloadHandler.text);
                else {Models=null;Status="Model settings unavailable. Reconnect to the updated local service.";}
            }
            if(MenuOpen&&menu.CurrentPage==ConsultationMenu.Page.Models)menu.Render(ConsultationMenu.Page.Models);
        }
        public void ChangeModel(string id) {if(CanChangeModel)StartCoroutine(ChangeModelRoutine(id));}
        IEnumerator ChangeModelRoutine(string id)
        {
            IsSwitching=true;Status="Loading dialogue model… The voice stays unchanged.";
            bool accepted=false;
            yield return Post("/models/select",new RequestBody{model_id=id},raw=>{Models=JsonUtility.FromJson<DialogueModelStatus>(raw);accepted=true;});
            if(accepted)
            {
                float deadline=Time.realtimeSinceStartup+360;
                while(Models!=null&&Models.switching&&Time.realtimeSinceStartup<deadline)
                {yield return new WaitForSecondsRealtime(1);yield return ReadModels();}
                if(Models!=null)Status=!string.IsNullOrEmpty(Models.error)?Models.error:Models.switching?"Still loading. Reopen model settings to check progress.":"Model ready. Conversation and 16-bit voice retained.";
            }
            IsSwitching=false;
            if(MenuOpen&&menu.CurrentPage==ConsultationMenu.Page.Models)menu.Render(ConsultationMenu.Page.Models);
        }
    }
}
