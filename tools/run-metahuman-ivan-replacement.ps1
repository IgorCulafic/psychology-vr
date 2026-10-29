param([int]$AssemblyProcessId)
$ErrorActionPreference='Stop'
$projectRoot=Split-Path $PSScriptRoot -Parent
$editorPath='C:/Program Files/Epic Games/UE_5.8/Engine/Binaries/Win64/UnrealEditor.exe'
$statusPath="$projectRoot/experiments/metahuman/ivan-replacement-status.json"
function Status($stage,$state) { @{stage=$stage;status=$state;updated=(Get-Date).ToString('o')} | ConvertTo-Json | Set-Content $statusPath }
function Unreal-Stage($name,$script,$flag,$report,$expected) {
    Status $name 'running'
    $started=Get-Date
    $p=Start-Process -FilePath $editorPath -ArgumentList "$projectRoot/experiments/metahuman/MetaHumanAudition.uproject -ExecutePythonScript=$projectRoot/tools/$script $flag -unattended -nosplash -NoSound -nohmd -abslog=$projectRoot/experiments/metahuman/ivan-$name.log" -WindowStyle Hidden -PassThru
    $p.WaitForExit()
    $reportPath="$projectRoot/experiments/metahuman/$report"
    if((Get-Item $reportPath).LastWriteTime -lt $started){throw "$name did not write a fresh report"}
    $result=Get-Content $reportPath -Raw | ConvertFrom-Json
    if($result.status -notin $expected){throw "$name failed: $($result.error)"}
}
try {
    Status 'assembly' 'waiting'
    if($AssemblyProcessId){Wait-Process -Id $AssemblyProcessId -ErrorAction SilentlyContinue}
    $assembly=Get-Content "$projectRoot/experiments/metahuman/cast/assembly-report.json" -Raw | ConvertFrom-Json
    if($assembly.status -ne 'assembled'){throw 'Replacement assembly is incomplete.'}
    Unreal-Stage 'prepare' 'metahuman-cast-prepare.py' '' 'cast/prepare-report.json' @('prepared_restart_before_bake')
    Unreal-Stage 'export' 'metahuman-unity-export.py' '' 'exports/unity/manifest.json' @('exported')
    Unreal-Stage 'pose-prepare' 'metahuman-unity-performance.py' '-mhOnly=ivan' 'exports/unity/performance.json' @('prepared_restart_required','exported')
    Unreal-Stage 'pose-bake' 'metahuman-unity-performance.py' '-mhOnly=ivan' 'exports/unity/performance.json' @('exported')
    Status 'stage-assets' 'running'
    & 'C:/Program Files/Blender Foundation/Blender 5.2/blender.exe' -b -t 4 --python "$projectRoot/tools/audit-metahuman-hair-uv.py"
    if($LASTEXITCODE -ne 0){throw 'Hair UV audit failed.'}
    & "$projectRoot/.tools/livelink-venv/Scripts/python.exe" "$projectRoot/tools/stage-metahuman-unity.py"
    if($LASTEXITCODE -ne 0){throw 'Asset staging failed.'}
    & 'C:/Program Files/Blender Foundation/Blender 5.2/blender.exe' -b -t 4 --python "$projectRoot/tools/build-metahuman-clothes.py"
    if($LASTEXITCODE -ne 0){throw 'Clothing build failed.'}
    Status 'unity-build' 'running'
    $p=Start-Process -FilePath 'C:/Program Files/Unity/Hub/Editor/6000.6.0f1/Editor/Unity.exe' -ArgumentList "-batchmode -quit -projectPath $projectRoot/unity -executeMethod PsychologyVR.Editor.MetaHumanSetup.BuildAll -logFile $projectRoot/experiments/metahuman/unity-bruce-build.log" -WindowStyle Hidden -PassThru
    $p.WaitForExit();if($p.ExitCode -ne 0){throw 'Unity build failed.'}
    Status 'ready-for-review' 'success'
} catch {
    @{status='error';error=$_.Exception.Message;updated=(Get-Date).ToString('o')} | ConvertTo-Json | Set-Content $statusPath
    throw
}
