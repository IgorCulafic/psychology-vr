param([switch]$Desktop, [switch]$Scripted, [switch]$NoGame)
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path $PSScriptRoot -Parent
Set-Location -LiteralPath $taskRoot
$taskRuntime = Join-Path $taskRoot 'services/.runtime'
New-Item -ItemType Directory -Path $taskRuntime -Force | Out-Null
$taskPython = Join-Path $taskRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $taskPython)) { throw 'Project Python is missing. Follow README.md setup instructions.' }
function Get-Health([string]$Url) {
    try { return Invoke-RestMethod -Uri $Url -TimeoutSec 2 } catch { return $null }
}
function Wait-Health([string]$Url, [int]$Seconds) {
    $deadline = (Get-Date).AddSeconds($Seconds)
    do {
        $health = Get-Health $Url
        if ($health) { return $health }
        Start-Sleep -Milliseconds 500
    } while ((Get-Date) -lt $deadline)
    throw "Service did not become ready: $Url. Check services/.runtime logs."
}
if (-not $Scripted) {
    if (-not (Get-Health 'http://127.0.0.1:8087/health')) {
        $taskServer = Join-Path $taskRoot '.tools/llama/llama-server.exe'
        $taskModel = Join-Path $taskRoot '.cache/models/qwen/Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-IQ4_XS.gguf'
        if (-not (Test-Path -LiteralPath $taskServer) -or -not (Test-Path -LiteralPath $taskModel)) { throw 'Model/runtime missing. See README.md.' }
        $taskArguments = @('--model', ('"'+$taskModel+'"'), '--alias','alex-qwen','--host','127.0.0.1','--port','8087',
            '--ctx-size','4096','--parallel','1','--n-gpu-layers','99','--batch-size','256','--ubatch-size','128',
            '--jinja','--reasoning','off','--spec-type','none')
        $taskProcess = Start-Process -FilePath $taskServer -ArgumentList $taskArguments -WorkingDirectory $taskRoot -WindowStyle Hidden -PassThru `
            -RedirectStandardOutput (Join-Path $taskRuntime 'model.out.log') -RedirectStandardError (Join-Path $taskRuntime 'model.err.log')
        @{Id=$taskProcess.Id; Path=$taskServer; StartTicks=$taskProcess.StartTime.ToUniversalTime().Ticks} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $taskRuntime 'model-process.json')
        Write-Host 'Loading Qwen...'
        Wait-Health 'http://127.0.0.1:8087/health' 120 | Out-Null
    }
}
$expectedProvider = if ($Scripted) {'scripted'} else {'llama.cpp'}
$taskBridgeHealth = Get-Health 'http://127.0.0.1:8765/health'
if ($taskBridgeHealth -and $taskBridgeHealth.dialogue_provider -ne $expectedProvider) {
    throw 'A bridge with a different configuration is already running. Run tools/stop-services.ps1 first.'
}
if (-not $taskBridgeHealth) {
    $taskConfig = if ($Scripted) {'services/config.example.json'} else {'services/config.local.json'}
    $env:HF_HOME = Join-Path $taskRoot '.cache/huggingface'
    $env:HF_HUB_OFFLINE = '1'
    $taskProcess = Start-Process -FilePath $taskPython -ArgumentList 'services/alex_service.py','--config',$taskConfig `
        -WorkingDirectory $taskRoot -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $taskRuntime 'bridge.out.log') -RedirectStandardError (Join-Path $taskRuntime 'bridge.err.log')
    @{Id=$taskProcess.Id; Path=$taskPython; StartTicks=$taskProcess.StartTime.ToUniversalTime().Ticks} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $taskRuntime 'bridge-process.json')
    Wait-Health 'http://127.0.0.1:8765/health' 20 | Out-Null
}
if (-not $NoGame) {
    $taskGame = Join-Path $taskRoot 'unity/Builds/Windows/AlexPrototype.exe'
    if (-not (Test-Path -LiteralPath $taskGame)) { throw 'Build the Windows prototype from the Psychology VR menu in Unity first.' }
    $taskGameArguments = @('-logFile', ('"'+(Join-Path $taskRuntime 'player.log')+'"'))
    if ($Desktop) { $taskGameArguments += '--desktop' }
    # The game is the interactive application the user is explicitly launching.
    Start-Process -FilePath $taskGame -ArgumentList $taskGameArguments -WorkingDirectory $taskRoot
}
Write-Host 'Alex prototype services are ready. Use tools/stop-services.ps1 after playing to free GPU memory.'
