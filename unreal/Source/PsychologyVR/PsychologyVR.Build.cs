using UnrealBuildTool;
public class PsychologyVR : ModuleRules
{
    public PsychologyVR(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
        PublicDependencyModuleNames.AddRange(new[] {"Core", "CoreUObject", "Engine", "InputCore", "HTTP", "Json", "JsonUtilities", "UMG", "Slate", "SlateCore", "HeadMountedDisplay", "XRBase", "AudioCaptureCore"});
    }
}
