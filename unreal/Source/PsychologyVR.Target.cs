using UnrealBuildTool;
public class PsychologyVRTarget : TargetRules
{
    public PsychologyVRTarget(TargetInfo Target) : base(Target)
    {
        Type = TargetType.Game;
        DefaultBuildSettings = BuildSettingsVersion.Latest;
        IncludeOrderVersion = EngineIncludeOrderVersion.Latest;
        ExtraModuleNames.Add("PsychologyVR");
    }
}
