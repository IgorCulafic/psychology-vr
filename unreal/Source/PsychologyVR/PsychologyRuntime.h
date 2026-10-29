#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/GameModeBase.h"
#include "Blueprint/UserWidget.h"
#include "AudioCaptureCore.h"
#include "Dom/JsonObject.h"
#include "PsychologyRuntime.generated.h"

class UAudioComponent;
class USoundWaveProcedural;
class USkeletalMeshComponent;
class UCameraComponent;
class UMotionControllerComponent;
class UWidgetInteractionComponent;
class UWidgetComponent;
class UTextRenderComponent;
class UTextBlock;
class UEditableTextBox;
class UComboBoxString;
class UCheckBox;

USTRUCT(BlueprintType)
struct FPsychologyBeat
{
    GENERATED_BODY()
    UPROPERTY(BlueprintReadOnly) FString Text;
    UPROPERTY(BlueprintReadOnly) FName Emotion = "neutral";
    UPROPERTY(BlueprintReadOnly) float Intensity = .5f;
    UPROPERTY(BlueprintReadOnly) FName Gesture = "none";
    UPROPERTY(BlueprintReadOnly) FName Gaze = "listener";
    UPROPERTY(BlueprintReadOnly) FName VoiceStyle = "normal";
    UPROPERTY(BlueprintReadOnly) float TransitionSeconds = .65f;
    UPROPERTY(BlueprintReadOnly) float GestureAt = 0;
    UPROPERTY(BlueprintReadOnly) float GestureDuration = 1;
    UPROPERTY(BlueprintReadOnly) float AudioDurationSeconds = 0;
};

DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FPerformanceCue, const FPsychologyBeat&, Beat);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FSpeechClock, float, Seconds, FName, MouthCue);
DECLARE_DYNAMIC_MULTICAST_DELEGATE(FPerformanceStopped);

// Engine-independent transport. Animation plugins subscribe to these Blueprint events.
UCLASS(ClassGroup=Psychology, meta=(BlueprintSpawnableComponent))
class PSYCHOLOGYVR_API UPsychologySession : public UActorComponent
{
    GENERATED_BODY()
public:
    UPsychologySession();
    virtual void BeginPlay() override;
    virtual void EndPlay(const EEndPlayReason::Type Reason) override;
    virtual void TickComponent(float Delta, ELevelTick Tick, FActorComponentTickFunction* Function) override;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) FString ServiceUrl = "http://127.0.0.1:8765";
    UPROPERTY(BlueprintReadOnly) FString Status = "Connecting to the local AI service...";
    UPROPERTY(BlueprintReadOnly) FString Subtitle;
    UPROPERTY(BlueprintReadOnly) FString CharacterName;
    UPROPERTY(BlueprintReadOnly) bool Busy = false;
    UPROPERTY(BlueprintReadOnly) bool Recording = false;
    UPROPERTY(BlueprintReadOnly) int32 FinishedTurns = 0;
    UPROPERTY(BlueprintAssignable) FPerformanceCue OnPerformance;
    UPROPERTY(BlueprintAssignable) FSpeechClock OnSpeechClock;
    UPROPERTY(BlueprintAssignable) FPerformanceStopped OnPerformanceStopped;
    UFUNCTION(BlueprintCallable) void Connect();
    UFUNCTION(BlueprintCallable) void NewConversation(const FString& Scenario);
    UFUNCTION(BlueprintCallable) void Submit(const FString& Text, bool Opening = false);
    UFUNCTION(BlueprintCallable) void Interrupt();
    UFUNCTION(BlueprintCallable) void StartRecording();
    UFUNCTION(BlueprintCallable) void StopRecording();
    void RefreshModels();
    void ChangeModel(const FString& Id);
    TArray<TSharedPtr<FJsonValue>> Models;
    FString CurrentModel;
    bool ModelChanging=false, ModelSelectionEnabled=false;
    TArray<TSharedPtr<FJsonValue>> Scenarios;
    FString SelectedScenario;
    int32 MicrophoneIndex = INDEX_NONE;
    TArray<Audio::FCaptureDeviceInfo> Microphones;
private:
    using FObject = TSharedPtr<FJsonObject>;
    void Request(const FString& Path, FObject Body, TFunction<void(FObject)> Callback, int32 Token);
    void Poll();
    void LoadSegment(FObject Segment);
    void StartSegment();
    void CompleteSegment();
    void Finish(bool Interrupted);
    void Fail(const FString& Message);
    FObject PlaybackBody() const;
    float HeardSeconds() const;
    UPROPERTY() TObjectPtr<UAudioComponent> Voice;
    UPROPERTY() TObjectPtr<USoundWaveProcedural> Wave;
    FString SessionId, TurnId;
    int32 Epoch=0, Generation=0, Completed=0;
    bool RequestPending=false, Ended=false, Playing=false, WaitingAudio=false, Holding=false;
    double NextPoll=0, LastProgress=0, SegmentStart=0, StartAt=0, HoldUntil=0, LastAck=0;
    float Duration=0, HoldSeconds=0;
    int32 AudioBytes=0, BytesPerSecond=1;
    FObject CurrentSegment;
    FPsychologyBeat Beat;
    TArray<uint8> PendingPCM;
    int32 PendingRate=24000, PendingChannels=1;
    Audio::FAudioCapture Capture;
    FCriticalSection CaptureMutex;
    TArray<int16> Captured;
    int32 CaptureRate=48000;
    double RecordStarted=0;
    double NextModelPoll=0;
};

UCLASS(Blueprintable)
class PSYCHOLOGYVR_API APsychologyPatient : public AActor
{
    GENERATED_BODY()
public:
    APsychologyPatient();
    virtual void Tick(float Delta) override;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly) TObjectPtr<USkeletalMeshComponent> Body;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) bool UseDefaultFace = true;
    UFUNCTION(BlueprintNativeEvent) void Perform(const FPsychologyBeat& NewBeat);
    UFUNCTION(BlueprintNativeEvent) void SpeechClock(float Seconds, FName MouthCue);
    UFUNCTION(BlueprintNativeEvent) void StopPerformance();
private:
    FPsychologyBeat ActiveBeat;
    float SpeechAmount=0;
    double SpeechUpdated=-10;
};

UCLASS()
class PSYCHOLOGYVR_API UPsychologyMenu : public UUserWidget
{
    GENERATED_BODY()
public:
    UPROPERTY() TObjectPtr<UPsychologySession> Session;
    virtual TSharedRef<SWidget> RebuildWidget() override;
    virtual void NativeTick(const FGeometry& Geometry, float Delta) override;
    UFUNCTION() void BeginConversation();
    UFUNCTION() void Send();
    UFUNCTION() void Stop();
    UFUNCTION() void Reconnect();
    UFUNCTION() void Dismiss();
    UFUNCTION() void MicrophoneChanged(FString Item, ESelectInfo::Type Type);
    UFUNCTION() void ApplyModel();
private:
    UPROPERTY() TObjectPtr<UTextBlock> StatusText;
    UPROPERTY() TObjectPtr<UTextBlock> Description;
    UPROPERTY() TObjectPtr<UTextBlock> ReplyText;
    UPROPERTY() TObjectPtr<UEditableTextBox> Draft;
    UPROPERTY() TObjectPtr<UComboBoxString> Picker;
    UPROPERTY() TObjectPtr<UComboBoxString> MicPicker;
    UPROPERTY() TObjectPtr<UComboBoxString> ModelPicker;
    UPROPERTY() TObjectPtr<UTextBlock> ModelLabel;
    UPROPERTY() TObjectPtr<UCheckBox> ShowDescriptions;
    int32 CatalogCount=-1;
};

UCLASS()
class PSYCHOLOGYVR_API APsychologyPawn : public APawn
{
    GENERATED_BODY()
public:
    APsychologyPawn();
    virtual void BeginPlay() override;
    virtual void Tick(float Delta) override;
    virtual void SetupPlayerInputComponent(UInputComponent* Input) override;
    void ToggleMenu();
    void Recenter();
    void SelectPressed();
    void SelectReleased();
    void LookX(float Value);
    void LookY(float Value);
    void TalkBegin();
    void TalkEnd();
    UPROPERTY(VisibleAnywhere) TObjectPtr<UPsychologySession> Session;
    UPROPERTY(VisibleAnywhere) TObjectPtr<UCameraComponent> Camera;
    UPROPERTY(VisibleAnywhere) TObjectPtr<UMotionControllerComponent> RightHand;
    UPROPERTY(VisibleAnywhere) TObjectPtr<UMotionControllerComponent> LeftHand;
    UPROPERTY(VisibleAnywhere) TObjectPtr<UWidgetInteractionComponent> Pointer;
    UPROPERTY(VisibleAnywhere) TObjectPtr<UWidgetComponent> WorldMenu;
    UPROPERTY(VisibleAnywhere) TObjectPtr<UTextRenderComponent> Captions;
    UPROPERTY() TObjectPtr<UPsychologyMenu> Menu;
    bool MenuVisible=true, VR=false;
    bool CaptureRequested=false;
    double CaptureReadyTime=0;
};

UCLASS()
class PSYCHOLOGYVR_API APsychologyGameMode : public AGameModeBase
{
    GENERATED_BODY()
public:
    APsychologyGameMode();
};
