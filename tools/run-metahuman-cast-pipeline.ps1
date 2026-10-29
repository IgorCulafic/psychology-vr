param([int]$AssemblyProcessId, [switch]$FinalPass, [switch]$TearsOnly)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$editorPath = 'C:/Program Files/Epic Games/UE_5.8/Engine/Binaries/Win64/UnrealEditor.exe'
$projectPath = "$projectRoot/experiments/metahuman/MetaHumanAudition.uproject"
$workPath = "$projectRoot/experiments/metahuman/cast"
function Run-Stage($name, $script, $flag, $report, $expected) {
    @{stage=$name;status='running'} | ConvertTo-Json | Set-Content "$workPath/pipeline-status.json"
    $stageStart = Get-Date
    $arguments = @($projectPath,"-ExecutePythonScript=$projectRoot/tools/$script",$flag,'-unattended','-nosplash','-NoSound','-nohmd',"-abslog=$projectRoot/experiments/metahuman/cast-$name.log")
    $taskProcess = Start-Process -FilePath $editorPath -ArgumentList ($arguments -join ' ') -WindowStyle Hidden -PassThru
    $taskProcess.WaitForExit()
    if ($taskProcess.ExitCode -ne 0) { throw "Stage $name editor exited with $($taskProcess.ExitCode)" }
    if ($report) {
        if ((Get-Item "$projectRoot/experiments/metahuman/$report").LastWriteTime -lt $stageStart) { throw "Stage $name did not write a fresh report" }
        $result = Get-Content "$projectRoot/experiments/metahuman/$report" -Raw | ConvertFrom-Json
        if ($result.status -ne $expected) { throw "Stage $name failed: $($result.error)" }
    }
}
try {
    if ($TearsOnly) {
        Run-Stage 'tears-build' 'metahuman-tears-build.py' '' 'tears/build-report.json' 'exported_not_rendered'
        Run-Stage 'tears-render' 'metahuman-audition-render.py' '-mhTears' 'tears/render-report.json' 'rendered'
        @{stage='complete';status='success'} | ConvertTo-Json | Set-Content "$workPath/pipeline-status.json"
        return
    }
    if ($FinalPass) {
        Run-Stage 'frame' 'metahuman-cast-frame.py' '' 'cast/framing-report.json' 'framed'
        Run-Stage 'tears-build' 'metahuman-tears-build.py' '' 'tears/build-report.json' 'exported_not_rendered'
        Run-Stage 'render' 'metahuman-audition-render.py' '-mhCast' 'cast/render-report.json' 'rendered'
        Run-Stage 'tears-render' 'metahuman-audition-render.py' '-mhTears' 'tears/render-report.json' 'rendered'
        @{stage='complete';status='success'} | ConvertTo-Json | Set-Content "$workPath/pipeline-status.json"
        return
    }
    if ($AssemblyProcessId) { Wait-Process -Id $AssemblyProcessId -ErrorAction SilentlyContinue }
    $assembly = Get-Content "$workPath/assembly-report.json" -Raw | ConvertFrom-Json
    if ($assembly.status -ne 'assembled') { throw 'Character assembly did not finish successfully' }
    Run-Stage 'tears-probe' 'metahuman-tears-probe.py' '' '' ''
    Run-Stage 'prepare' 'metahuman-cast-prepare.py' '' 'cast/prepare-report.json' 'prepared_restart_before_bake'
    Run-Stage 'bake' 'metahuman-speaking-build.py' '-mhCast' 'cast/build-report.json' 'exported_not_rendered'
    Run-Stage 'frame' 'metahuman-cast-frame.py' '' 'cast/framing-report.json' 'framed'
    Run-Stage 'render' 'metahuman-audition-render.py' '-mhCast' 'cast/render-report.json' 'rendered'
    @{stage='complete';status='success'} | ConvertTo-Json | Set-Content "$workPath/pipeline-status.json"
} catch {
    @{stage='failed';status='error';error=$_.Exception.Message} | ConvertTo-Json | Set-Content "$workPath/pipeline-status.json"
    throw
}
