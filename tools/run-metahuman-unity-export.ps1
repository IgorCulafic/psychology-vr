$ErrorActionPreference='Stop'
$projectRoot=Split-Path $PSScriptRoot -Parent
$editorPath='C:/Program Files/Epic Games/UE_5.8/Engine/Binaries/Win64/UnrealEditor.exe'
$outPath="$projectRoot/experiments/metahuman/exports/unity"
try {
    foreach($stage in @('metahuman-unity-export','metahuman-unity-performance','metahuman-unity-performance')) {
        @{stage=$stage;status='running'} | ConvertTo-Json | Set-Content "$outPath/pipeline.json"
        $started=Get-Date
        $taskProcess=Start-Process $editorPath -ArgumentList "$projectRoot/experiments/metahuman/MetaHumanAudition.uproject -ExecutePythonScript=$projectRoot/tools/$stage.py -unattended -nosplash -NoSound -nohmd -abslog=$projectRoot/experiments/metahuman/$stage.log" -WindowStyle Hidden -PassThru
        $taskProcess.WaitForExit()
        # Some engine builds fault during D3D shutdown after a successful export.
        # Require a fresh, explicit success report rather than accepting an old report.
        $file=if($stage -eq 'metahuman-unity-export'){'manifest.json'}else{'performance.json'}
        if((Get-Item "$outPath/$file").LastWriteTime -lt $started){throw "Stage did not write a fresh report: $stage (exit $($taskProcess.ExitCode))"}
        $result=Get-Content "$outPath/$file" -Raw | ConvertFrom-Json
        if($result.status -notin @('exported','prepared_restart_required')){throw $result.error}
    }
    if($result.status -ne 'exported'){throw 'Performance preparation completed, but the bake did not complete.'}
    @{status='exported'} | ConvertTo-Json | Set-Content "$outPath/pipeline.json"
} catch {
    @{status='error';error=$_.Exception.Message} | ConvertTo-Json | Set-Content "$outPath/pipeline.json"
}
