using UnrealBuildTool;
public class PsychologyVREditorTarget : TargetRules
{
    public PsychologyVREditorTarget(TargetInfo Target) : base(Target)
    {
        Type = TargetType.Editor;
        DefaultBuildSettings = BuildSettingsVersion.Latest;
        IncludeOrderVersion = EngineIncludeOrderVersion.Latest;
        ExtraModuleNames.Add("PsychologyVR");
    }
}
