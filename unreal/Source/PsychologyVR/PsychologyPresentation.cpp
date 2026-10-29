#include "PsychologyRuntime.h"
#include "Camera/CameraComponent.h"
#include "MotionControllerComponent.h"
#include "HeadMountedDisplayFunctionLibrary.h"
#include "Components/WidgetInteractionComponent.h"
#include "Components/WidgetComponent.h"
#include "Components/TextRenderComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Animation/MorphTarget.h"
#include "Kismet/GameplayStatics.h"
#include "GameFramework/PlayerController.h"
#include "Blueprint/WidgetTree.h"
#include "Components/Border.h"
#include "Components/VerticalBox.h"
#include "Components/HorizontalBox.h"
#include "Components/TextBlock.h"
#include "Components/Button.h"
#include "Components/EditableTextBox.h"
#include "Components/ComboBoxString.h"
#include "Components/CheckBox.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "UnrealClient.h"
#if WITH_EDITOR
#include "ShaderCompiler.h"
#endif

APsychologyPatient::APsychologyPatient()
{
    PrimaryActorTick.bCanEverTick=true;
    Body=CreateDefaultSubobject<USkeletalMeshComponent>(TEXT("PatientBody")); SetRootComponent(Body);
    Body->SetCollisionEnabled(ECollisionEnabled::NoCollision);
}
void APsychologyPatient::Perform_Implementation(const FPsychologyBeat& NewBeat) { ActiveBeat=NewBeat; }
void APsychologyPatient::SpeechClock_Implementation(float Seconds,FName MouthCue)
{
    SpeechUpdated=FPlatformTime::Seconds();
    SpeechAmount=(MouthCue==TEXT("X") || MouthCue==TEXT("A"))?0.f:MouthCue==TEXT("B")?.15f:.25f+.16f*FMath::Sin(Seconds*19);
}
void APsychologyPatient::StopPerformance_Implementation() { SpeechAmount=0; SpeechUpdated=-10; }
void APsychologyPatient::Tick(float Delta)
{
    Super::Tick(Delta); if(!UseDefaultFace || !Body->GetSkeletalMeshAsset()) return;
    TMap<FString,float> Face;
    auto Pair=[&](const FString& N,float V) { Face.Add(N+TEXT("_L"),V); Face.Add(N+TEXT("_R"),V); };
    const FName E=ActiveBeat.Emotion;
    if(E==TEXT("calm") || E==TEXT("relieved")) { Pair(TEXT("Mouth_Smile"),.18); Pair(TEXT("Eye_Squint"),.12); }
    if(E==TEXT("happy") || E==TEXT("hopeful")) { Pair(TEXT("Mouth_Smile"),E==TEXT("happy")?.8:.35); Pair(TEXT("Cheek_Raise"),.4); Pair(TEXT("Brow_Raise_Inner"),.3); }
    if(E==TEXT("sad") || E==TEXT("crying") || E==TEXT("despondent")) { Pair(TEXT("Brow_Raise_Inner"),.9); Pair(TEXT("Mouth_Frown"),.75); Pair(TEXT("Eye_Blink"),E==TEXT("crying")?.4:E==TEXT("despondent")?.45:0); }
    if(E==TEXT("angry")) { Pair(TEXT("Brow_Drop"),1); Pair(TEXT("Brow_Compress"),1); Pair(TEXT("Eye_Squint"),.7); Pair(TEXT("Mouth_Press"),.6); }
    if(E==TEXT("frustrated")) { Pair(TEXT("Brow_Compress"),.35); Face.Add(TEXT("Brow_Raise_Outer_L"),.65); Pair(TEXT("Mouth_Press"),.5); }
    if(E==TEXT("anxious") || E==TEXT("afraid") || E==TEXT("panicked")) { Pair(TEXT("Brow_Raise_Inner"),.85); Pair(TEXT("Eye_Wide"),E==TEXT("anxious")?.25:.85); Pair(TEXT("Mouth_Stretch"),.4); }
    if(E==TEXT("disgusted")) { Pair(TEXT("Nose_Sneer"),.9); Pair(TEXT("Mouth_Up_Upper"),.6); Pair(TEXT("Eye_Squint"),.45); }
    if(E==TEXT("surprised")) { Pair(TEXT("Brow_Raise_Outer"),.8); Pair(TEXT("Eye_Wide"),.7); Face.Add(TEXT("V_Open"),.2); }
    if(E==TEXT("ashamed") || E==TEXT("guilty")) { Pair(TEXT("Brow_Raise_Inner"),.6); Pair(TEXT("Mouth_Frown"),.4); Pair(TEXT("Eye_Blink"),.25); }
    if(E==TEXT("confused") || E==TEXT("skeptical")) { Face.Add(TEXT("Brow_Raise_Outer_L"),.75); Face.Add(TEXT("Eye_Squint_R"),.45); }
    for(auto& Entry:Face) Entry.Value*=FMath::Clamp(ActiveBeat.Intensity,0.f,1.f);
    const double Now=FPlatformTime::Seconds();
    const float Blink=FMath::Pow(FMath::Max(0.f,FMath::Cos(float(Now*1.3))),32.f);
    Pair(TEXT("Eye_Blink"),FMath::Max(Blink,Face.FindRef(TEXT("Eye_Blink_L"))));
    if(Now-SpeechUpdated<.15) { Face.Add(TEXT("V_Open"),SpeechAmount); Face.Add(TEXT("Jaw_Open"),SpeechAmount); }
    for(const auto& Morph:Body->GetSkeletalMeshAsset()->GetMorphTargets())
    {
        const FString Name=Morph->GetName(); float Goal=0;
        for(const auto& Entry:Face) if(Name.EndsWith(Entry.Key)) { Goal=Entry.Value; break; }
        const float Speed=Name.Contains(TEXT("Blink"))?30.f:Name.Contains(TEXT("Open"))?20.f:3.f/FMath::Max(.15f,ActiveBeat.TransitionSeconds);
        Body->SetMorphTarget(Morph->GetFName(),FMath::FInterpTo(Body->GetMorphTarget(Morph->GetFName()),Goal,Delta,Speed));
    }
}

TSharedRef<SWidget> UPsychologyMenu::RebuildWidget()
{
    if(!WidgetTree) WidgetTree=NewObject<UWidgetTree>(this);
    auto* Back=WidgetTree->ConstructWidget<UBorder>(); Back->SetBrushColor(FLinearColor(.035,.045,.05,.97)); Back->SetPadding(FMargin(24)); WidgetTree->RootWidget=Back;
    auto* Column=WidgetTree->ConstructWidget<UVerticalBox>(); Back->SetContent(Column);
    auto Text=[&](const FString& Value,int Size) { auto* T=WidgetTree->ConstructWidget<UTextBlock>(); T->SetText(FText::FromString(Value)); auto Font=T->GetFont(); Font.Size=Size; T->SetFont(Font); T->SetAutoWrapText(true); Column->AddChild(T); return T; };
    Text(TEXT("Psychology VR  |  Unreal"),26);
    Text(TEXT("Choose a patient. Hold Space / right A to speak; Escape / right B opens this menu."),15);
    Picker=WidgetTree->ConstructWidget<UComboBoxString>(); Column->AddChild(Picker);
    ShowDescriptions=WidgetTree->ConstructWidget<UCheckBox>(); auto* Label=WidgetTree->ConstructWidget<UTextBlock>(); Label->SetText(FText::FromString(TEXT("Show case descriptions (teacher view)"))); ShowDescriptions->SetContent(Label); Column->AddChild(ShowDescriptions);
    Description=Text(TEXT(""),15);
    auto* Actions=WidgetTree->ConstructWidget<UHorizontalBox>(); Column->AddChild(Actions);
    auto Button=[&](const FString& Name) { auto* B=WidgetTree->ConstructWidget<UButton>(); auto* T=WidgetTree->ConstructWidget<UTextBlock>(); T->SetText(FText::FromString(Name)); auto Font=T->GetFont(); Font.Size=16; T->SetFont(Font); B->SetContent(T); Actions->AddChild(B); return B; };
    Button(TEXT("  New conversation  "))->OnClicked.AddDynamic(this,&UPsychologyMenu::BeginConversation);
    Button(TEXT("  Stop reply  "))->OnClicked.AddDynamic(this,&UPsychologyMenu::Stop);
    Button(TEXT("  Reconnect  "))->OnClicked.AddDynamic(this,&UPsychologyMenu::Reconnect);
    Button(TEXT("  Return to room  "))->OnClicked.AddDynamic(this,&UPsychologyMenu::Dismiss);
    Text(TEXT("Microphone (Windows default initially)"),15);
    MicPicker=WidgetTree->ConstructWidget<UComboBoxString>(); MicPicker->AddOption(TEXT("Windows default")); MicPicker->SetSelectedIndex(0); Column->AddChild(MicPicker);
    MicPicker->OnSelectionChanged.AddDynamic(this,&UPsychologyMenu::MicrophoneChanged);
    ModelLabel=Text(TEXT("Dialogue model"),15);
    ModelPicker=WidgetTree->ConstructWidget<UComboBoxString>(); Column->AddChild(ModelPicker);
    auto* Apply=WidgetTree->ConstructWidget<UButton>(); auto* ApplyText=WidgetTree->ConstructWidget<UTextBlock>();
    ApplyText->SetText(FText::FromString(TEXT("Apply dialogue model (between replies)"))); Apply->SetContent(ApplyText); Column->AddChild(Apply);
    Apply->OnClicked.AddDynamic(this,&UPsychologyMenu::ApplyModel);
    Draft=WidgetTree->ConstructWidget<UEditableTextBox>(); Draft->SetHintText(FText::FromString(TEXT("Type a message for the patient..."))); Column->AddChild(Draft);
    auto* SendButton=WidgetTree->ConstructWidget<UButton>(); auto* SendLabel=WidgetTree->ConstructWidget<UTextBlock>(); SendLabel->SetText(FText::FromString(TEXT("Send message"))); SendButton->SetContent(SendLabel); Column->AddChild(SendButton); SendButton->OnClicked.AddDynamic(this,&UPsychologyMenu::Send);
    StatusText=Text(TEXT("Connecting..."),17); ReplyText=Text(TEXT(""),19);
    return Super::RebuildWidget();
}
void UPsychologyMenu::NativeTick(const FGeometry& G,float Delta)
{
    Super::NativeTick(G,Delta); if(!Session || !Picker) return;
    if(CatalogCount!=Session->Scenarios.Num())
    {
        CatalogCount=Session->Scenarios.Num(); Picker->ClearOptions();
        for(const auto& Item:Session->Scenarios) { auto J=Item->AsObject(); Picker->AddOption(J->GetStringField(TEXT("character_name"))); }
        if(CatalogCount) Picker->SetSelectedIndex(0);
    }
    if(MicPicker->GetOptionCount()!=Session->Microphones.Num()+1)
    {
        MicPicker->ClearOptions(); MicPicker->AddOption(TEXT("Windows default"));
        for(const auto& Mic:Session->Microphones) MicPicker->AddOption(Mic.DeviceName);
        MicPicker->SetSelectedIndex(Session->MicrophoneIndex+1);
    }
    StatusText->SetText(FText::FromString(Session->Status)); ReplyText->SetText(FText::FromString(Session->Subtitle));
    if(ModelPicker->GetOptionCount()!=Session->Models.Num())
    {
        ModelPicker->ClearOptions();
        for(const auto& Item:Session->Models) { auto J=Item->AsObject(); ModelPicker->AddOption(J->GetStringField(TEXT("label"))+(J->GetBoolField(TEXT("installed"))?TEXT(""):TEXT(" (not installed)"))); }
        ModelPicker->SetSelectedIndex(0);
    }
    ModelPicker->SetIsEnabled(Session->ModelSelectionEnabled && !Session->Busy && !Session->Recording);
    ModelLabel->SetText(FText::FromString(TEXT("Dialogue model | Active: ")+Session->CurrentModel));
    FString Details;
    if(ShowDescriptions->IsChecked() && Session->Scenarios.IsValidIndex(Picker->GetSelectedIndex()))
        Session->Scenarios[Picker->GetSelectedIndex()]->AsObject()->TryGetStringField(TEXT("summary"),Details);
    Description->SetText(FText::FromString(Details));
}
void UPsychologyMenu::BeginConversation() { if(Session && Session->Scenarios.IsValidIndex(Picker->GetSelectedIndex())) Session->NewConversation(Session->Scenarios[Picker->GetSelectedIndex()]->AsObject()->GetStringField(TEXT("id"))); }
void UPsychologyMenu::Send() { if(Session && !Session->Busy) { Session->Submit(Draft->GetText().ToString()); Draft->SetText(FText::GetEmpty()); } }
void UPsychologyMenu::Stop() { if(Session) Session->Interrupt(); }
void UPsychologyMenu::Reconnect() { if(Session) Session->Connect(); }
void UPsychologyMenu::Dismiss() { if(auto* Pawn=Cast<APsychologyPawn>(GetOwningPlayerPawn())) Pawn->ToggleMenu(); }
void UPsychologyMenu::MicrophoneChanged(FString,ESelectInfo::Type Type) { if(Type!=ESelectInfo::Direct && Session && !Session->Recording) Session->MicrophoneIndex=MicPicker->GetSelectedIndex()-1; }
void UPsychologyMenu::ApplyModel()
{
    if(!Session || !Session->Models.IsValidIndex(ModelPicker->GetSelectedIndex())) return;
    auto J=Session->Models[ModelPicker->GetSelectedIndex()]->AsObject();
    if(!J->GetBoolField(TEXT("installed"))) { Session->Status=TEXT("That model is not installed on this PC."); return; }
    Session->ChangeModel(J->GetStringField(TEXT("id")));
}

APsychologyPawn::APsychologyPawn()
{
    PrimaryActorTick.bCanEverTick=true;
    auto* Origin=CreateDefaultSubobject<USceneComponent>(TEXT("SeatedOrigin")); SetRootComponent(Origin);
    Camera=CreateDefaultSubobject<UCameraComponent>(TEXT("Head")); Camera->SetupAttachment(Origin); Camera->SetRelativeLocation(FVector(0,0,122)); Camera->bLockToHmd=true;
    RightHand=CreateDefaultSubobject<UMotionControllerComponent>(TEXT("RightController")); RightHand->SetupAttachment(Origin); RightHand->SetTrackingMotionSource(TEXT("Right"));
    LeftHand=CreateDefaultSubobject<UMotionControllerComponent>(TEXT("LeftController")); LeftHand->SetupAttachment(Origin); LeftHand->SetTrackingMotionSource(TEXT("Left"));
    Pointer=CreateDefaultSubobject<UWidgetInteractionComponent>(TEXT("MenuPointer")); Pointer->SetupAttachment(RightHand); Pointer->InteractionDistance=600; Pointer->bShowDebug=true;
    WorldMenu=CreateDefaultSubobject<UWidgetComponent>(TEXT("VRMenu")); WorldMenu->SetupAttachment(Camera); WorldMenu->SetRelativeLocation(FVector(95,0,0)); WorldMenu->SetRelativeRotation(FRotator(0,180,0)); WorldMenu->SetRelativeScale3D(FVector(.11)); WorldMenu->SetDrawSize(FVector2D(1000,700));
    Captions=CreateDefaultSubobject<UTextRenderComponent>(TEXT("Subtitles")); Captions->SetupAttachment(Camera); Captions->SetRelativeLocation(FVector(90,0,-22)); Captions->SetRelativeRotation(FRotator(0,180,0)); Captions->SetWorldSize(1.7); Captions->SetHorizontalAlignment(EHTA_Center);
    Session=CreateDefaultSubobject<UPsychologySession>(TEXT("PatientSession"));
}
void APsychologyPawn::BeginPlay()
{
    Super::BeginPlay();
#if WITH_EDITOR
    FString ValidationCapture;
    if(FParse::Value(FCommandLine::Get(),TEXT("PsychologyCapture="),ValidationCapture) && GShaderCompilingManager)
        GShaderCompilingManager->FinishAllCompilation();
#endif
    VR=!FParse::Param(FCommandLine::Get(),TEXT("nohmd")) && UHeadMountedDisplayFunctionLibrary::IsHeadMountedDisplayEnabled();
    if(VR) { UHeadMountedDisplayFunctionLibrary::SetTrackingOrigin(EHMDTrackingOrigin::LocalFloor); Camera->SetRelativeLocation(FVector::ZeroVector); }
    else Pointer->SetActive(false);
    TArray<AActor*> Patients; UGameplayStatics::GetAllActorsOfClass(GetWorld(),APsychologyPatient::StaticClass(),Patients);
    if(Patients.Num()) { auto* Patient=Cast<APsychologyPatient>(Patients[0]); Session->OnPerformance.AddDynamic(Patient,&APsychologyPatient::Perform); Session->OnSpeechClock.AddDynamic(Patient,&APsychologyPatient::SpeechClock); Session->OnPerformanceStopped.AddDynamic(Patient,&APsychologyPatient::StopPerformance); }
    auto* PC=Cast<APlayerController>(GetController());
    Menu=CreateWidget<UPsychologyMenu>(PC,UPsychologyMenu::StaticClass()); Menu->Session=Session;
    if(VR) WorldMenu->SetWidget(Menu);
    else { WorldMenu->SetVisibility(false); Menu->AddToViewport(); Menu->SetDesiredSizeInViewport(FVector2D(950,620)); Menu->SetPositionInViewport(FVector2D(30,30)); }
    if(PC) { PC->bShowMouseCursor=!VR; PC->SetInputMode(FInputModeGameAndUI()); }
    if(FParse::Param(FCommandLine::Get(),TEXT("NoMenu")) || FParse::Param(FCommandLine::Get(),TEXT("PsychologySmoke"))) ToggleMenu();
    UE_LOG(LogTemp,Display,TEXT("PSYCHOLOGY_WORLD_READY patients=%d vr=%d"),Patients.Num(),VR);
}
void APsychologyPawn::Tick(float Delta)
{
    Super::Tick(Delta);
    FString CapturePath;
    if(FParse::Value(FCommandLine::Get(),TEXT("PsychologyCapture="),CapturePath))
    {
        if(!CaptureRequested && GetWorld()->GetTimeSeconds()>10)
        {
#if WITH_EDITOR
            if(GShaderCompilingManager && GShaderCompilingManager->IsCompiling()) return;
#endif
            CaptureRequested=true;
            CaptureReadyTime=GetWorld()->GetTimeSeconds();
            FScreenshotRequest::RequestScreenshot(CapturePath,true,false);
        }
        if(CaptureRequested && GetWorld()->GetTimeSeconds()>CaptureReadyTime+2 && !FParse::Param(FCommandLine::Get(),TEXT("PsychologySmoke"))) FPlatformMisc::RequestExit(false);
    }
    FString Caption=Session->Subtitle;
    // Keep the VR caption within a readable panel width.
    TArray<FString> Words; Caption.ParseIntoArrayWS(Words); Caption.Empty(); int Count=0;
    for(const auto& Word:Words) { if(Count+Word.Len()>72) { Caption+=TEXT("\n"); Count=0; } Caption+=Word+TEXT(" "); Count+=Word.Len()+1; }
    Captions->SetText(FText::FromString(MenuVisible?TEXT(""):Caption));
    if(FParse::Param(FCommandLine::Get(),TEXT("PsychologySmoke")))
    {
        if(Session->FinishedTurns>0 && (CapturePath.IsEmpty() || (CaptureRequested && GetWorld()->GetTimeSeconds()>CaptureReadyTime+2))) { UE_LOG(LogTemp,Display,TEXT("PSYCHOLOGY_SMOKE_OK")); FPlatformMisc::RequestExitWithStatus(false,0); }
        else if(GetWorld()->GetTimeSeconds()>150) { UE_LOG(LogTemp,Error,TEXT("PSYCHOLOGY_SMOKE_TIMEOUT %s"),*Session->Status); FPlatformMisc::RequestExitWithStatus(false,2); }
    }
}
void APsychologyPawn::ToggleMenu()
{
    MenuVisible=!MenuVisible; if(VR) WorldMenu->SetVisibility(MenuVisible); else if(Menu) Menu->SetVisibility(MenuVisible?ESlateVisibility::Visible:ESlateVisibility::Collapsed);
    if(auto* PC=Cast<APlayerController>(GetController())) { PC->bShowMouseCursor=MenuVisible&&!VR; if(MenuVisible) PC->SetInputMode(FInputModeGameAndUI()); else PC->SetInputMode(FInputModeGameOnly()); }
}
void APsychologyPawn::Recenter() { UHeadMountedDisplayFunctionLibrary::ResetOrientationAndPosition(); }
void APsychologyPawn::SelectPressed() { if(MenuVisible) Pointer->PressPointerKey(EKeys::LeftMouseButton); }
void APsychologyPawn::SelectReleased() { Pointer->ReleasePointerKey(EKeys::LeftMouseButton); }
void APsychologyPawn::TalkBegin() { if(!MenuVisible) Session->StartRecording(); }
void APsychologyPawn::TalkEnd() { Session->StopRecording(); }
void APsychologyPawn::LookX(float V) { if(!VR && !MenuVisible) Camera->AddLocalRotation(FRotator(0,V,0)); }
void APsychologyPawn::LookY(float V) { if(!VR && !MenuVisible) Camera->AddLocalRotation(FRotator(V,0,0)); }
void APsychologyPawn::SetupPlayerInputComponent(UInputComponent* I)
{
    Super::SetupPlayerInputComponent(I);
    I->BindAction(TEXT("Talk"),IE_Pressed,this,&APsychologyPawn::TalkBegin); I->BindAction(TEXT("Talk"),IE_Released,this,&APsychologyPawn::TalkEnd);
    I->BindAction(TEXT("Menu"),IE_Pressed,this,&APsychologyPawn::ToggleMenu); I->BindAction(TEXT("Recenter"),IE_Pressed,this,&APsychologyPawn::Recenter);
    I->BindAction(TEXT("Select"),IE_Pressed,this,&APsychologyPawn::SelectPressed); I->BindAction(TEXT("Select"),IE_Released,this,&APsychologyPawn::SelectReleased);
    I->BindAction(TEXT("StopReply"),IE_Pressed,Session.Get(),&UPsychologySession::Interrupt);
    I->BindAxis(TEXT("LookX"),this,&APsychologyPawn::LookX); I->BindAxis(TEXT("LookY"),this,&APsychologyPawn::LookY);
}
APsychologyGameMode::APsychologyGameMode() { DefaultPawnClass=APsychologyPawn::StaticClass(); }
