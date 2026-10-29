param([switch]$CompileOnly, [string]$Blender)
. (Join-Path $PSScriptRoot 'unreal-common.ps1')
$engine = Find-UnrealEngine
Assert-UnrealEditorSdk
New-Item -ItemType Directory -Path $unrealRuntime -Force | Out-Null
Push-Location -LiteralPath $unrealRoot
try {
    Write-Host 'Compiling the Unreal editor module...'
    & (Join-Path $engine 'Engine/Build/BatchFiles/Build.bat') PsychologyVREditor Win64 Development "-Project=$unrealProject" -WaitMutex -NoHotReloadFromIDE -MaxParallelActions=4 "-log=$unrealRuntime/unreal-build.log"
    if ($LASTEXITCODE -ne 0) { throw 'Unreal compilation failed. See services/.runtime/unreal-build.log.' }
    if ($CompileOnly) { return }
    $source = Join-Path $unrealRoot 'unity/Assets/PsychologyVR/Art/Characters/Candidates/Jumper/Jumper.fbx'
    $converted = Join-Path $unrealRoot '.cache/unreal/JumperSeated.fbx'
    if (!(Test-Path -LiteralPath $source) -or (Get-Item -LiteralPath $source).Length -lt 1000) { throw 'Source character missing or still a Git LFS pointer. Run git lfs pull first.' }
    $exporter = Join-Path $PSScriptRoot 'prepare-unreal-character.py'
    if (!(Test-Path -LiteralPath $converted) -or (Get-Item $converted).LastWriteTimeUtc -lt (Get-Item $source).LastWriteTimeUtc -or (Get-Item $converted).LastWriteTimeUtc -lt (Get-Item $exporter).LastWriteTimeUtc) {
        if (!$Blender) { $Blender = $env:BLENDER_EXE }
        if (!$Blender) { $Blender = 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' }
        if (!(Test-Path -LiteralPath $Blender)) { throw 'Blender is needed for the initial character conversion. Set BLENDER_EXE to blender.exe, or pass -Blender. See docs/UNREAL_PORT.md.' }
        Write-Host 'Converting the character and seated animation...'
        & $Blender --background --python-exit-code 1 --python $exporter
        if ($LASTEXITCODE -ne 0) { throw 'Character conversion failed.' }
    }
    Write-Host 'Importing the room, materials and character. Existing consultation maps are preserved.'
    $importScript = Join-Path $unrealRoot 'unreal/Content/Python/build_consultation.py'
    $importLog = Join-Path $unrealRuntime 'unreal-import.log'
    $arguments = @('"'+$unrealProject+'"', '-unattended', '-nosplash', '-nullrhi', '-nosound', '-ExecutePythonScript="'+$importScript+'"', '-abslog="'+$importLog+'"')
    $process = Start-Process -FilePath (Join-Path $engine 'Engine/Binaries/Win64/UnrealEditor-Cmd.exe') -ArgumentList $arguments -WorkingDirectory $unrealRoot -WindowStyle Hidden -PassThru -Wait
    if ($process.ExitCode -ne 0 -or !(Test-Path $importLog) -or !(Select-String -LiteralPath $importLog -SimpleMatch 'PSYCHOLOGY_IMPORT_OK' -Quiet)) {
        throw 'Unreal asset import did not complete. See services/.runtime/unreal-import.log.'
    }
    if (!(Test-Path (Join-Path $unrealRoot 'unreal/Content/Psychology/Consultation.umap'))) { throw 'Consultation map was not saved.' }
    Write-Host 'Unreal project prepared. Use Open Unreal Editor.cmd, Start Unreal Desktop.cmd or Start Unreal VR.cmd.'
} finally { Pop-Location }
