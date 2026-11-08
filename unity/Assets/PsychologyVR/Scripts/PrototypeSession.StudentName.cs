using System;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using System.Text;
using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.UI;

namespace PsychologyVR
{
    public partial class PrototypeSession
    {
        public string StudentName {get;private set;}="";
        public bool NamePromptOpen=>menu&&menu.WaitingForStudentName;
        bool launchNamePromptRequested;
        bool exportingSession;
        string lastExportedLog;
        public string SessionExportStatus {get;private set;}="";
        public bool CanExportSession=>CanSelect&&!NamePromptOpen&&!exportingSession&&!string.IsNullOrEmpty(StudentName);

        void ClearSessionExportStatus()
        {
            SessionExportStatus="";lastExportedLog=null;
        }

        public void ExportSessionLog()
        {
            if(CanExportSession)StartCoroutine(ExportCurrentSessionLog());
        }

        IEnumerator ExportCurrentSessionLog()
        {
            string key=sessionId;int token=version;exportingSession=true;
            SessionExportStatus="Saving session log…";
            Reply saved=null;
            yield return Post("/session/export",new RequestBody{session_id=key},raw=>saved=JsonUtility.FromJson<Reply>(raw));
            exportingSession=false;
            if(token!=version||key!=sessionId)yield break;
            if(saved!=null&&!string.IsNullOrEmpty(saved.filename))
            {
                lastExportedLog=saved.filename;
                SessionExportStatus="Saved "+saved.filename+" in logs/exports.";
            }
            else SessionExportStatus="Could not save the session log. Check the local service and try again.";
        }

        bool ConfigureServiceOverride()
        {
            var args=Environment.GetCommandLineArgs();int at=Array.IndexOf(args,"--service-url");
            if(at<0)return true;
            if(at+1>=args.Length||!Uri.TryCreate(args[at+1],UriKind.Absolute,out Uri uri)||uri.Scheme!="http"||!uri.IsLoopback||uri.AbsolutePath!="/"||uri.Query!=""||uri.Fragment!=""||uri.UserInfo!="")
            {
                Status="The service address must be a local HTTP address.";
                Debug.LogError("Invalid --service-url: use an HTTP loopback address with no path, query or credentials.");
                Application.Quit(2);return false;
            }
            serviceUrl=uri.GetLeftPart(UriPartial.Authority);return true;
        }

        string ConversationDiagnosticName
        {
            get
            {
                var args=Environment.GetCommandLineArgs();
                if(Array.Exists(args,value=>value=="--smoke-test"||value=="--streaming-check"||value=="--headset-free-stress"||value=="--performance-replay"))return "Automated check";
                return IsSpeechAudition?"Voice audition":null;
            }
        }

        void PromptForLaunchStudentName()
        {
            var args=Environment.GetCommandLineArgs();
            if(ConversationDiagnosticName!=null||Array.Exists(args,value=>value=="--menu-preview"||value=="--integration-preview"||value=="--record-alex"||value=="--alex-preview"||value=="--environment-preview"||value=="--visuals-preview"||value=="--metahuman-check"||value=="--seated-idle-check"))return;
            if(launchNamePromptRequested&&!string.IsNullOrEmpty(StudentName))return;
            launchNamePromptRequested=true;
            if(!string.IsNullOrEmpty(StudentName))return;
            // Cancellation leaves the normal menu available; it never starts dialogue.
            SetMenuOpen(true);
            PromptForStudentName(CurrentScenario,ActiveAppearance,"",true);
        }

        void PromptForStudentName(ScenarioEntry entry,string appearanceId,string firstText,bool opening)
        {
            if(NamePromptOpen||IsSwitching)return;
            bool wasOpen=MenuOpen;
            var previousPage=menu.CurrentPage;
            menu.PromptForStudentName(name=>
            {
                // A name is attached only once the replacement session succeeds.
                menu.Render(previousPage);
                StartCoroutine(SwitchScenario(entry,appearanceId,name,firstText,opening));
            },()=>
            {
                SetMenuOpen(wasOpen);
                if(wasOpen)menu.Render(previousPage);
            },entry.character_name);
            SetMenuOpen(true);
        }

        public static bool ValidateStudentName(string value,out string name,out string error)
        {
            name="";error=null;
            if(value==null)value="";
            for(int i=0;i<value.Length;i++)
            {
                char character=value[i];
                if(char.IsSurrogate(character)&&(!char.IsHighSurrogate(character)||i+1>=value.Length||!char.IsLowSurrogate(value[i+1])))
                {error="Enter a name without control characters.";return false;}
                var category=CharUnicodeInfo.GetUnicodeCategory(value,i);
                if(category==UnicodeCategory.Control||category==UnicodeCategory.Format||category==UnicodeCategory.LineSeparator||category==UnicodeCategory.ParagraphSeparator)
                {error="Enter a name on one line, without control characters.";return false;}
                if(char.IsHighSurrogate(character))i++;
            }
            name=value.Normalize(NormalizationForm.FormC).Trim();
            if(name.Length==0){error="Enter the student's name to continue.";return false;}
            int length=0;
            for(int i=0;i<name.Length;i++,length++)if(char.IsHighSurrogate(name[i]))i++;
            if(length>80){error="Use 80 characters or fewer.";return false;}
            return true;
        }

        // Opt-in regression check uses the actual menu, input field and session API.
        // This flag deliberately does not provide an automatic student identity.
        IEnumerator CheckStudentNamePrompt()
        {
            float deadline=Time.realtimeSinceStartup+35;
            while((!CanSelect||IsSwitching)&&Time.realtimeSinceStartup<deadline)yield return null;
            if(!CanSelect||StudentName!=""){FailStudentNameCheck("connection or initial identity");yield break;}
            string before=sessionId;
            yield return null;
            if(!NamePromptOpen||!MenuOpen||IsSwitching||sessionId!=before||HasConversation)
            {FailStudentNameCheck("launch prompt missing or conversation started before name confirmation");yield break;}
            var field=StudentNameCheckInput();
            var confirm=StudentNameCheckButton("Start conversation");
            if(!field||!confirm||field.lineType!=InputField.LineType.SingleLine||field.characterLimit!=80)
            {FailStudentNameCheck("name controls missing");yield break;}
            field.text="   ";yield return null;
            if(confirm.interactable){FailStudentNameCheck("blank name accepted");yield break;}
            field.text="Ana\u2028Test";yield return null;
            if(confirm.interactable){FailStudentNameCheck("line separator accepted");yield break;}
            var cancel=StudentNameCheckButton("Cancel");cancel.onClick.Invoke();yield return null;
            if(NamePromptOpen||!MenuOpen||sessionId!=before||StudentName!=""||HasConversation)
            {FailStudentNameCheck("cancel changed original session");yield break;}

            StartScenario(CurrentScenario.id,ActiveAppearance);yield return null;
            field=StudentNameCheckInput();field.text="  Ana C\u030Cukić  ";yield return null;
            confirm=StudentNameCheckButton("Start conversation");
            if(!confirm.interactable||StudentName!=""){FailStudentNameCheck("valid input state");yield break;}
            var args=Environment.GetCommandLineArgs();int captureAt=Array.IndexOf(args,"--capture-path");
            if(captureAt>=0&&captureAt+1<args.Length)Capture(view,args[captureAt+1]);
            confirm.onClick.Invoke();
            deadline=Time.realtimeSinceStartup+150;
            while((IsSwitching||!HasConversation||busy)&&Time.realtimeSinceStartup<deadline)yield return null;
            if(IsSwitching||busy||!HasConversation||StudentName!="Ana Čukić"||sessionId==before)
            {FailStudentNameCheck("named session failed: "+Status);yield break;}
            string namedSession=sessionId;
            SetMenuOpen(true);menu.Render(ConsultationMenu.Page.Session);yield return null;
            var export=StudentNameCheckButton("Export session log");
            if(!export||!export.interactable){FailStudentNameCheck("session export button unavailable");yield break;}
            export.onClick.Invoke();deadline=Time.realtimeSinceStartup+30;
            while(exportingSession&&Time.realtimeSinceStartup<deadline)yield return null;
            if(exportingSession||string.IsNullOrEmpty(lastExportedLog)||lastExportedLog.IndexOf("Ana",StringComparison.OrdinalIgnoreCase)<0||!SessionExportStatus.StartsWith("Saved ",StringComparison.Ordinal)||sessionId!=namedSession||!HasConversation)
            {FailStudentNameCheck("named log export failed or changed conversation");yield break;}
            string exportedStatus=SessionExportStatus,exportedFilename=lastExportedLog;
            StartScenario(CurrentScenario.id,ActiveAppearance);yield return null;
            field=StudentNameCheckInput();
            if(!NamePromptOpen||field.text!=""){FailStudentNameCheck("new conversation did not ask again");yield break;}
            StudentNameCheckButton("Cancel").onClick.Invoke();yield return null;
            if(NamePromptOpen||sessionId!=namedSession||StudentName!="Ana Čukić"||!HasConversation||SessionExportStatus!=exportedStatus||lastExportedLog!=exportedFilename)
            {FailStudentNameCheck("cancel changed named conversation");yield break;}
            Interrupt(true);deadline=Time.realtimeSinceStartup+30;
            while(busy&&Time.realtimeSinceStartup<deadline)yield return null;
            if(busy||StudentName!="Ana Čukić"||HasConversation||SessionExportStatus!=""||lastExportedLog!=null)
            {FailStudentNameCheck("reset lost student identity");yield break;}
            Reconnect();deadline=Time.realtimeSinceStartup+35;
            while(IsSwitching&&Time.realtimeSinceStartup<deadline)yield return null;
            if(IsSwitching||!CanSelect||NamePromptOpen||StudentName!="Ana Čukić"||SessionExportStatus!=""||lastExportedLog!=null)
            {FailStudentNameCheck("reconnect lost identity or repeated launch prompt");yield break;}
            Debug.Log("STUDENT_NAME_CHECK_OK automatic launch prompt, validation, normalized Unicode, cancellation, named session, log export, reset and reconnect");
            Application.Quit(0);
        }

        InputField StudentNameCheckInput()=>Array.Find(menu.GetComponentsInChildren<InputField>(),field=>field.gameObject.name=="Student name");
        Button StudentNameCheckButton(string label)=>Array.Find(menu.GetComponentsInChildren<Button>(),button=>button.gameObject.name==label);
        static void FailStudentNameCheck(string reason){Debug.LogError("STUDENT_NAME_CHECK_FAILED "+reason);Application.Quit(5);}
    }

    public partial class ConsultationMenu
    {
        Action<string> studentNameConfirmed;
        Action studentNameCancelled;
        string studentNameDraft="",studentPatient="";
        bool studentUppercase=true;
        InputField studentNameInput;
        Text studentNameError;
        readonly List<(Text label,string character)> studentKeys=new List<(Text,string)>();
        public bool WaitingForStudentName=>studentNameConfirmed!=null;

        public void PromptForStudentName(Action<string> confirmed,Action cancelled,string patient)
        {
            studentNameDraft="";studentUppercase=true;studentPatient=patient;
            studentNameConfirmed=confirmed;studentNameCancelled=cancelled;
        }

        public void CancelStudentName()
        {
            if(!WaitingForStudentName)return;
            var cancelled=studentNameCancelled;
            ClearStudentNamePrompt();cancelled?.Invoke();
        }

        void ClearStudentNamePrompt()
        {
            studentNameConfirmed=null;studentNameCancelled=null;studentNameDraft="";
            studentNameInput=null;studentNameError=null;studentKeys.Clear();
        }

        void ConfirmStudentName()
        {
            if(!WaitingForStudentName)return;
            if(!PrototypeSession.ValidateStudentName(studentNameDraft,out string name,out string error))
            {if(studentNameError)studentNameError.text=error??"Enter the student's name to continue.";return;}
            var confirmed=studentNameConfirmed;
            ClearStudentNamePrompt();confirmed(name);
        }

        void RenderStudentName()
        {
            Hover(null);conditions.Clear();studentKeys.Clear();status=transcript=volumeLabel=micLabel=null;message=null;
            if(content){content.gameObject.SetActive(false);Destroy(content.gameObject);}
            content=Rect("Student name prompt",canvas.transform,0,0,960,760);content.gameObject.AddComponent<Image>().color=Panel;
            TextAt("START CONVERSATION",32,24,896,36,28,Ink,FontStyle.Bold);
            var patient=TextAt("With "+studentPatient,34,68,890,28,20,Accent);patient.supportRichText=false;
            TextAt("Enter the student's name. It will be included in saved and downloaded conversation logs.",34,110,890,60,20,Muted);
            studentNameInput=InputAt(32,186,896,66,studentNameDraft);
            studentNameInput.gameObject.name="Student name";
            studentNameInput.lineType=InputField.LineType.SingleLine;studentNameInput.characterLimit=80;
            studentNameInput.textComponent.supportRichText=false;
            ((Text)studentNameInput.placeholder).text="Student's name";
            studentNameInput.onValueChanged.AddListener(value=>studentNameDraft=value);
            studentNameError=TextAt("",34,260,890,35,18,Accent);
            string[] rows={"QWERTYUIOP","ASDFGHJKL","ZXCVBNMČĆŽ","ŠĐ0123456789'-"};
            for(int row=0;row<rows.Length;row++)
            {
                string keys=rows[row];float width=(896-(keys.Length-1)*5)/(float)keys.Length;
                for(int i=0;i<keys.Length;i++)
                {
                    string character=keys[i].ToString();
                    var button=ButtonAt(character,32+i*(width+5),306+row*51,width,44,()=>AppendStudentCharacter(studentUppercase?character:character.ToLowerInvariant()));
                    studentKeys.Add((button.GetComponentInChildren<Text>(),character));
                }
            }
            ButtonAt("Shift",32,518,144,46,ToggleStudentCase);
            ButtonAt("Space",184,518,300,46,()=>AppendStudentCharacter(" "));
            ButtonAt("Backspace",492,518,244,46,DeleteStudentCharacter);
            ButtonAt("Clear",744,518,184,46,()=>SetStudentDraft(""));
            TextAt("Use the controller keyboard above or type with a physical keyboard.",34,584,890,30,18,Muted);
            ButtonAt("Cancel",32,634,288,56,CancelStudentName);
            ButtonAt("Start conversation",334,634,594,56,ConfirmStudentName,()=>PrototypeSession.ValidateStudentName(studentNameDraft,out _,out _),active:true);
            TextAt("Esc / right B · Cancel",34,708,890,24,17,Muted);
            studentNameInput.ActivateInputField();
            UpdateStudentName();
        }

        void UpdateStudentName()
        {
            if(studentNameError)
            {
                bool valid=PrototypeSession.ValidateStudentName(studentNameDraft,out _,out string error);
                studentNameError.text=valid||studentNameDraft.Length==0?"":error;
            }
            foreach(var condition in conditions)if(condition.button)condition.button.interactable=condition.enabled();
            var keyboard=Keyboard.current;
            if(keyboard!=null&&(keyboard.enterKey.wasPressedThisFrame||keyboard.numpadEnterKey.wasPressedThisFrame))ConfirmStudentName();
        }

        void SetStudentDraft(string value)
        {
            studentNameDraft=value;
            if(studentNameInput){studentNameInput.text=value;studentNameInput.caretPosition=value.Length;}
        }

        void AppendStudentCharacter(string value)
        {
            if(studentNameDraft.Length+value.Length<=80)SetStudentDraft(studentNameDraft+value);
        }

        void DeleteStudentCharacter()
        {
            var starts=StringInfo.ParseCombiningCharacters(studentNameDraft);
            if(starts.Length>0)SetStudentDraft(studentNameDraft.Substring(0,starts[starts.Length-1]));
        }

        void ToggleStudentCase()
        {
            studentUppercase=!studentUppercase;
            foreach(var key in studentKeys)if(key.label)key.label.text=studentUppercase?key.character:key.character.ToLowerInvariant();
        }
    }
}
