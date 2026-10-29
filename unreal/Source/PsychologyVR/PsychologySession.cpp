#include "PsychologyRuntime.h"
#include "HttpModule.h"
#include "Interfaces/IHttpResponse.h"
#include "Serialization/JsonSerializer.h"
#include "Components/AudioComponent.h"
#include "Sound/SoundWaveProcedural.h"
#include "Audio.h"
#include "Misc/Base64.h"
#include "Misc/ScopeLock.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"

namespace
{
using Obj = TSharedPtr<FJsonObject>;
Obj Object() { return MakeShared<FJsonObject>(); }
FString Str(Obj J, const TCHAR* Key, const FString& Default=TEXT("")) { FString S; return J && J->TryGetStringField(Key,S) ? S : Default; }
double Num(Obj J, const TCHAR* Key, double Default=0) { double V; return J && J->TryGetNumberField(Key,V) ? V : Default; }
bool Bool(Obj J, const TCHAR* Key) { bool V=false; return J && J->TryGetBoolField(Key,V) && V; }
double Now() { return FPlatformTime::Seconds(); }
}

UPsychologySession::UPsychologySession() { PrimaryComponentTick.bCanEverTick=true; }
void UPsychologySession::BeginPlay()
{
    Super::BeginPlay();
    FString Url;
    if(FParse::Value(FCommandLine::Get(),TEXT("BridgeUrl="),Url)) ServiceUrl=Url;
    // Audio downloads and microphone uploads stay on the chosen local bridge.
    if(!ServiceUrl.StartsWith(TEXT("http://127.0.0.1:"))) { Fail(TEXT("BridgeUrl must use http://127.0.0.1:PORT")); return; }
    Voice=NewObject<UAudioComponent>(GetOwner()); Voice->RegisterComponent(); Voice->bAutoActivate=false;
    Voice->bAllowSpatialization=false; Voice->bIsUISound=true;
    Capture.GetCaptureDevicesAvailable(Microphones);
    Connect();
}
void UPsychologySession::Request(const FString& Path, FObject Body, TFunction<void(FObject)> Callback, int32 Token)
{
    auto R=FHttpModule::Get().CreateRequest();
    R->SetURL(ServiceUrl+Path); R->SetVerb(Body?TEXT("POST"):TEXT("GET")); R->SetTimeout(95);
    if(Body) { FString Json; auto W=TJsonWriterFactory<>::Create(&Json); FJsonSerializer::Serialize(Body.ToSharedRef(),W); R->SetHeader(TEXT("Content-Type"),TEXT("application/json")); R->SetContentAsString(Json); }
    TWeakObjectPtr<UPsychologySession> Weak(this);
    R->OnProcessRequestComplete().BindLambda([Weak,Token,Callback=MoveTemp(Callback)](FHttpRequestPtr, FHttpResponsePtr Response, bool OK)
    {
        if(!Weak.IsValid() || Weak->Epoch!=Token) return;
        Weak->RequestPending=false;
        Obj Data;
        if(!OK || !Response || Response->GetResponseCode()!=200 || !FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Response->GetContentAsString()),Data))
        { Weak->Fail(Response?FString::Printf(TEXT("Service error %d: %s"),Response->GetResponseCode(),*Response->GetContentAsString().Left(240)):TEXT("Local service unavailable. Use Reconnect after starting services.")); return; }
        Callback(Data);
    });
    if(!R->ProcessRequest()) { RequestPending=false; Fail(TEXT("Could not send local service request.")); }
}
void UPsychologySession::Connect()
{
    if(Busy || Recording) { Status=TEXT("Stop the current reply/recording before reconnecting."); return; }
    ++Epoch; RequestPending=true; Status=TEXT("Connecting...");
    Request(TEXT("/catalog"),nullptr,[this](Obj Data)
    {
        const TArray<TSharedPtr<FJsonValue>>* Items;
        if(!Data->TryGetArrayField(TEXT("scenarios"),Items)) { Fail(TEXT("Invalid character catalog.")); return; }
        Scenarios=*Items; SelectedScenario=Str(Data,TEXT("default_scenario_id"));
        Status=TEXT("Choose a patient and start a conversation.");
        if(FParse::Param(FCommandLine::Get(),TEXT("PsychologySmoke"))) NewConversation(SelectedScenario);
        else RefreshModels();
    },Epoch);
}
void UPsychologySession::RefreshModels()
{
    RequestPending=true;
    Request(TEXT("/models"),nullptr,[this](Obj Data)
    {
        const TArray<TSharedPtr<FJsonValue>>* Items;
        if(Data->TryGetArrayField(TEXT("models"),Items)) Models=*Items;
        CurrentModel=Str(Data,TEXT("current")); ModelSelectionEnabled=Bool(Data,TEXT("enabled"));
        const bool WasChanging=ModelChanging; ModelChanging=Bool(Data,TEXT("switching"));
        if(ModelChanging) { Busy=true; NextModelPoll=Now()+1; Status=TEXT("Loading dialogue model... Voice stays unchanged."); }
        else if(WasChanging) { Busy=false; Status=Str(Data,TEXT("error")); if(Status.IsEmpty()) Status=TEXT("Model ready. Conversation and voice retained."); }
    },Epoch);
}
void UPsychologySession::ChangeModel(const FString& Id)
{
    if(Busy || Recording || RequestPending || !ModelSelectionEnabled) { Status=TEXT("Finish or stop the reply before changing model."); return; }
    ModelChanging=true; Busy=true; RequestPending=true; NextModelPoll=DBL_MAX;
    Status=TEXT("Changing dialogue model...");
    auto B=Object(); B->SetStringField(TEXT("model_id"),Id);
    Request(TEXT("/models/select"),B,[this](Obj) { RefreshModels(); },Epoch);
}
void UPsychologySession::NewConversation(const FString& Scenario)
{
    if(Busy || Recording || RequestPending) { Status=TEXT("Stop the current reply before changing patient."); return; }
    ++Epoch; RequestPending=true; Busy=true; Ended=false; SelectedScenario=Scenario;
    auto B=Object(); B->SetStringField(TEXT("scenario_id"),Scenario);
    if(!SessionId.IsEmpty()) B->SetStringField(TEXT("replace_session_id"),SessionId);
    Request(TEXT("/session"),B,[this](Obj Data)
    {
        SessionId=Str(Data,TEXT("session_id")); CharacterName=Str(Data,TEXT("character_name")); Generation=Num(Data,TEXT("generation"));
        TurnId.Empty(); Subtitle.Empty(); Busy=false; Completed=0;
        Beat=FPsychologyBeat(); Beat.Emotion=FName(Str(Data,TEXT("initial_emotion"))); Beat.Intensity=Num(Data,TEXT("initial_intensity"),.5);
        OnPerformance.Broadcast(Beat); Submit(TEXT(""),true);
    },Epoch);
}
void UPsychologySession::Submit(const FString& Text, bool Opening)
{
    if(Busy || RequestPending || Recording || Ended || SessionId.IsEmpty() || (!Opening && Text.TrimStartAndEnd().IsEmpty())) return;
    Busy=true; RequestPending=true; Completed=0; TurnId.Empty(); Subtitle.Empty();
    Status=CharacterName+TEXT(" is preparing a reply..."); LastProgress=Now();
    auto B=Object(); B->SetStringField(TEXT("session_id"),SessionId); B->SetStringField(TEXT("text"),Text);
    B->SetBoolField(TEXT("opening"),Opening); B->SetNumberField(TEXT("expected_generation"),Generation);
    Request(TEXT("/turn/start"),B,[this](Obj Data) { TurnId=Str(Data,TEXT("turn_id")); NextPoll=Now(); },Epoch);
}
UPsychologySession::FObject UPsychologySession::PlaybackBody() const
{
    auto B=Object(); B->SetStringField(TEXT("session_id"),SessionId); B->SetStringField(TEXT("turn_id"),TurnId);
    B->SetNumberField(TEXT("completed_count"),Completed); B->SetNumberField(TEXT("partial_seconds"),HeardSeconds()); return B;
}
float UPsychologySession::HeardSeconds() const
{
    if(!Playing || Duration<=0) return 0;
    const float Wall=FMath::Max(0.,Now()-SegmentStart-.08);
    // Conservative estimate: rendered PCM and elapsed playback, less output buffering.
    const float Rendered=Wave ? FMath::Max(0.f,float(AudioBytes-Wave->GetAvailableAudioByteCount())/BytesPerSecond-.08f) : Wall;
    return FMath::Clamp(FMath::Min(Wall,Rendered),0.f,Duration);
}
void UPsychologySession::Poll()
{
    RequestPending=true;
    Request(TEXT("/turn/poll"),PlaybackBody(),[this](Obj Data)
    {
        if(Bool(Data,TEXT("closed"))) { Fail(TEXT("This reply has closed. Stop reply, then reconnect.")); return; }
        const TArray<TSharedPtr<FJsonValue>>* Segments;
        if(Data->TryGetArrayField(TEXT("segments"),Segments) && Segments->IsValidIndex(Completed)) { LoadSegment((*Segments)[Completed]->AsObject()); return; }
        if(Bool(Data,TEXT("done"))) { if(!Str(Data,TEXT("error")).IsEmpty()) { Status=Str(Data,TEXT("error")); Finish(true); } else Finish(false); return; }
        NextPoll=Now()+.15;
    },Epoch);
}
void UPsychologySession::LoadSegment(FObject Segment)
{
    CurrentSegment=Segment; WaitingAudio=true; LastProgress=Now();
    Beat=FPsychologyBeat(); Beat.Text=Str(Segment,TEXT("text")); Beat.Emotion=FName(Str(Segment,TEXT("emotion"),TEXT("neutral")));
    Beat.Intensity=Num(Segment,TEXT("intensity"),.5); Beat.Gesture=FName(Str(Segment,TEXT("gesture"),TEXT("none")));
    Beat.Gaze=FName(Str(Segment,TEXT("gaze"),TEXT("listener"))); Beat.VoiceStyle=FName(Str(Segment,TEXT("voice_style"),TEXT("normal")));
    Beat.TransitionSeconds=Num(Segment,TEXT("transition_seconds"),.65); Beat.GestureAt=Num(Segment,TEXT("gesture_at")); Beat.GestureDuration=Num(Segment,TEXT("gesture_duration_seconds"),1);
    HoldSeconds=FMath::Clamp(float(Num(Segment,TEXT("hold_after_seconds"))),0.f,5.f);
    FString Path=Str(Segment,TEXT("audio_url"));
    if(Path.IsEmpty()) { PendingPCM.Empty(); Duration=FMath::Clamp(Beat.Text.Len()/14.f,2.f,20.f); StartAt=Now()+Num(Segment,TEXT("pause_before_seconds")); WaitingAudio=false; return; }
    if(!Path.StartsWith(TEXT("/audio/")) || Path.Contains(TEXT("..")) || Path.Contains(TEXT(":"))) { Fail(TEXT("Invalid speech URL.")); return; }
    auto R=FHttpModule::Get().CreateRequest(); R->SetURL(ServiceUrl+Path); R->SetVerb(TEXT("GET")); R->SetTimeout(30);
    const int32 Token=Epoch; TWeakObjectPtr<UPsychologySession> Weak(this);
    R->OnProcessRequestComplete().BindLambda([Weak,Token](FHttpRequestPtr,FHttpResponsePtr Response,bool OK)
    {
        if(!Weak.IsValid() || Weak->Epoch!=Token) return;
        if(!OK || !Response || Response->GetResponseCode()!=200) { Weak->Fail(TEXT("Speech download failed. Stop reply before retrying.")); return; }
        TArray<uint8> Raw=Response->GetContent(); FWaveModInfo Info;
        if(!Info.ReadWaveInfo(Raw.GetData(),Raw.Num()) || *Info.pBitsPerSample!=16 || *Info.pFormatTag!=1 || *Info.pChannels<1 || *Info.pChannels>2 || *Info.pSamplesPerSec<8000 || *Info.pSamplesPerSec>192000 || Info.SampleDataSize==0)
        { Weak->Fail(TEXT("Speech must be PCM16 mono/stereo WAV.")); return; }
        Weak->PendingRate=*Info.pSamplesPerSec; Weak->PendingChannels=*Info.pChannels;
        Weak->PendingPCM.SetNumUninitialized(Info.SampleDataSize); FMemory::Memcpy(Weak->PendingPCM.GetData(),Info.SampleDataStart,Info.SampleDataSize);
        Weak->BytesPerSecond=Weak->PendingRate*Weak->PendingChannels*2;
        Weak->Duration=float(Info.SampleDataSize)/Weak->BytesPerSecond;
        Weak->StartAt=Now()+FMath::Clamp(Num(Weak->CurrentSegment,TEXT("pause_before_seconds")),0.,5.);
        Weak->WaitingAudio=false;
    });
    if(!R->ProcessRequest()) Fail(TEXT("Could not fetch speech."));
}
void UPsychologySession::StartSegment()
{
    StartAt=0; Playing=true; SegmentStart=Now(); LastAck=Now(); AudioBytes=PendingPCM.Num();
    Wave=nullptr;
    if(AudioBytes>0)
    {
        Wave=NewObject<USoundWaveProcedural>(this); Wave->SetSampleRate(PendingRate); Wave->NumChannels=PendingChannels;
        Wave->Duration=INDEFINITELY_LOOPING_DURATION; Wave->bLooping=false;
        Wave->QueueAudio(PendingPCM.GetData(),PendingPCM.Num()); Voice->SetSound(Wave); Voice->Play();
    }
    PendingPCM.Empty(); Beat.AudioDurationSeconds=Duration; Subtitle=Beat.Text; Status=CharacterName+TEXT(" is speaking..."); OnPerformance.Broadcast(Beat);
    UE_LOG(LogTemp,Display,TEXT("PSYCHOLOGY_SEGMENT_START index=%d emotion=%s"),Completed,*Beat.Emotion.ToString());
}
void UPsychologySession::CompleteSegment()
{
    Playing=false; Voice->Stop(); Wave=nullptr; ++Completed; LastProgress=Now();
    OnSpeechClock.Broadcast(Duration,TEXT("X")); OnPerformanceStopped.Broadcast();
    RequestPending=true;
    Request(TEXT("/playback"),PlaybackBody(),[this](Obj) { Holding=true; HoldUntil=Now()+HoldSeconds; },Epoch);
}
void UPsychologySession::Finish(bool Interrupted)
{
    RequestPending=true; auto B=PlaybackBody(); B->SetBoolField(TEXT("interrupted"),Interrupted);
    Request(TEXT("/turn/finish"),B,[this,Interrupted](Obj Data)
    {
        Generation=Num(Data,TEXT("generation"),Generation); const TSharedPtr<FJsonObject>* Rel;
        if(Data->TryGetObjectField(TEXT("relationship"),Rel)) Ended=Str(*Rel,TEXT("status"))==TEXT("ended");
        Busy=false; TurnId.Empty(); Completed=0; ++FinishedTurns; OnPerformanceStopped.Broadcast();
        Status=Ended?TEXT("The patient ended the session. Start a new conversation."):Interrupted?TEXT("Reply stopped."):TEXT("Ready. Hold Space / right A to speak.");
        UE_LOG(LogTemp,Display,TEXT("PSYCHOLOGY_TURN_FINISHED interrupted=%d"),Interrupted);
    },Epoch);
}
void UPsychologySession::Interrupt()
{
    if(ModelChanging) { Status=TEXT("Please wait for the model change to finish."); return; }
    if(Recording) { Capture.StopStream(); Capture.CloseStream(); Recording=false; }
    if(SessionId.IsEmpty()) { Busy=false; RequestPending=false; return; }
    auto B=PlaybackBody(); ++Epoch; Busy=true; RequestPending=true;
    if(Voice) Voice->Stop(); Playing=false; WaitingAudio=false; Holding=false; StartAt=0; PendingPCM.Empty(); Wave=nullptr;
    OnPerformanceStopped.Broadcast(); Status=TEXT("Stopping reply...");
    Request(TEXT("/interrupt"),B,[this](Obj Data) { Generation=Num(Data,TEXT("generation"),Generation); Busy=false; TurnId.Empty(); Completed=0; Status=TEXT("Reply stopped. Ready."); },Epoch);
}
void UPsychologySession::Fail(const FString& Message)
{
    ModelChanging=false;
    Status=Message; RequestPending=false; NextPoll=DBL_MAX; StartAt=0;
    if(Voice) Voice->Stop(); Playing=false; WaitingAudio=false; Holding=false; OnPerformanceStopped.Broadcast();
    // Keep an unresolved turn busy: only Stop/interrupt may reconcile its history.
    Busy=!SessionId.IsEmpty() && !TurnId.IsEmpty();
    UE_LOG(LogTemp,Error,TEXT("PSYCHOLOGY_SERVICE_ERROR %s"),*Message);
}
void UPsychologySession::StartRecording()
{
    if(Recording || Busy || RequestPending || SessionId.IsEmpty() || Ended) return;
    Audio::FAudioCaptureDeviceParams Params; Params.DeviceIndex=MicrophoneIndex;
    { FScopeLock Guard(&CaptureMutex); Captured.Empty(); }
    bool Open=Capture.OpenAudioCaptureStream(Params,[this](const void* Data,int32 Frames,int32 Channels,int32 Rate,double,bool)
    {
        FScopeLock Guard(&CaptureMutex); CaptureRate=Rate;
        if(!Data || Channels<1 || Captured.Num()>Rate*30) return;
        const float* Samples=static_cast<const float*>(Data);
        for(int32 Frame=0;Frame<Frames;++Frame) { float Sum=0; for(int32 C=0;C<Channels;++C) Sum+=Samples[Frame*Channels+C]; Captured.Add(int16(FMath::Clamp(Sum/Channels,-1.f,1.f)*32767)); }
    },1024);
    if(!Open || !Capture.StartStream()) { Capture.CloseStream(); Status=TEXT("Microphone unavailable. Select an input in the menu and check Windows permissions."); return; }
    Recording=true; RecordStarted=Now(); Status=TEXT("Recording... release Space / right A to send.");
}
void UPsychologySession::StopRecording()
{
    if(!Recording) return;
    Capture.StopStream(); Capture.CloseStream(); Recording=false;
    TArray<int16> PCM; int32 Rate;
    { FScopeLock Guard(&CaptureMutex); PCM=MoveTemp(Captured); Rate=CaptureRate; }
    if(PCM.Num()<Rate/4) { Status=TEXT("Recording too short. Hold the talk button while speaking."); return; }
    TArray<uint8> Wav;
    auto Add=[&Wav](const void* P,int32 N) { Wav.Append(static_cast<const uint8*>(P),N); };
    auto U32=[&Add](uint32 N) { Add(&N,4); }; auto U16=[&Add](uint16 N) { Add(&N,2); };
    Add("RIFF",4); U32(36+PCM.Num()*2); Add("WAVEfmt ",8); U32(16); U16(1); U16(1); U32(Rate); U32(Rate*2); U16(2); U16(16); Add("data",4); U32(PCM.Num()*2); Add(PCM.GetData(),PCM.Num()*2);
    RequestPending=true; Status=TEXT("Recognizing speech..."); auto B=Object(); B->SetStringField(TEXT("wav_base64"),FBase64::Encode(Wav));
    Request(TEXT("/transcribe"),B,[this](Obj Data) { FString Text=Str(Data,TEXT("text")); if(Text.TrimStartAndEnd().IsEmpty()) Status=TEXT("No clear speech detected. Try again."); else Submit(Text); },Epoch);
}
void UPsychologySession::TickComponent(float Delta,ELevelTick Tick,FActorComponentTickFunction* Function)
{
    Super::TickComponent(Delta,Tick,Function);
    if(ModelChanging) { if(!RequestPending && Now()>=NextModelPoll) RefreshModels(); return; }
    if(Recording && Now()-RecordStarted>29) StopRecording();
    if(!Busy || TurnId.IsEmpty()) return;
    if(StartAt>0 && !WaitingAudio && Now()>=StartAt) StartSegment();
    if(Playing)
    {
        float Clock=HeardSeconds(); FName Cue=TEXT("X"); const TArray<TSharedPtr<FJsonValue>>* Cues;
        if(CurrentSegment && CurrentSegment->TryGetArrayField(TEXT("mouth_cues"),Cues))
            for(const auto& Item:*Cues) { auto J=Item->AsObject(); if(Clock>=Num(J,TEXT("start")) && Clock<Num(J,TEXT("end"))) { Cue=FName(Str(J,TEXT("value"))); break; } }
        else if(Wave) Cue=TEXT("D");
        OnSpeechClock.Broadcast(Clock,Cue);
        if(!RequestPending && Now()-SegmentStart>=Duration+.15 && (!Wave || Wave->GetAvailableAudioByteCount()==0)) { CompleteSegment(); return; }
        if(Now()-LastAck>=1 && !RequestPending) { LastAck=Now(); RequestPending=true; Request(TEXT("/playback"),PlaybackBody(),[](Obj){},Epoch); }
        return;
    }
    if(Holding && Now()>=HoldUntil) { Holding=false; NextPoll=Now(); }
    if(!WaitingAudio && !Holding && StartAt==0 && !RequestPending && Now()>=NextPoll) Poll();
    if(Now()-LastProgress>240) { Interrupt(); Status=TEXT("Reply timed out and was stopped."); }
}
void UPsychologySession::EndPlay(const EEndPlayReason::Type Reason)
{
    if(Capture.IsStreamOpen()) { Capture.StopStream(); Capture.CloseStream(); }
    if(!SessionId.IsEmpty()) Interrupt();
    ++Epoch; Super::EndPlay(Reason);
}
