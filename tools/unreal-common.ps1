$ErrorActionPreference = 'Stop'
$unrealRoot = Split-Path $PSScriptRoot -Parent
$unrealProject = Join-Path $unrealRoot 'unreal/PsychologyVR.uproject'
$unrealRuntime = Join-Path $unrealRoot 'services/.runtime'
function Find-UnrealEngine {
    $candidates = @($env:UE_ROOT, 'C:\Program Files\Epic Games\UE_5.8')
    $registry = 'HKLM:\SOFTWARE\EpicGames\Unreal Engine\5.8'
    if (Test-Path $registry) { $candidates += (Get-ItemProperty $registry).InstalledDirectory }
    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path -LiteralPath (Join-Path $candidate 'Engine/Binaries/Win64/UnrealEditor.exe'))) {
            return $candidate
        }
    }
    throw 'Unreal Engine 5.8 is missing. Install it through Epic Games Launcher, or set UE_ROOT to its installation folder. See docs/UNREAL_PORT.md.'
}
function Assert-UnrealEditorSdk {
    foreach ($key in @('HKLM:\SOFTWARE\WOW6432Node\Microsoft\Microsoft SDKs\NETFXSDK', 'HKLM:\SOFTWARE\Microsoft\Microsoft SDKs\NETFXSDK')) {
        if (Test-Path $key) {
            foreach ($entry in Get-ChildItem $key) {
                $sdk = (Get-ItemProperty $entry.PSPath -ErrorAction SilentlyContinue).KitsInstallationFolder
                if ($sdk -and (Test-Path -LiteralPath $sdk)) { return }
            }
        }
    }
    throw 'Unreal editor compilation requires the .NET Framework SDK. In Visual Studio Installer > Build Tools 2022 > Modify > Individual components, install .NET Framework 4.8 SDK and .NET Framework 4.8 targeting pack. Then run this launcher again.'
}
