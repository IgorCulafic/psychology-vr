param([switch]$Desktop, [switch]$Scripted, [switch]$NoGame, [switch]$ModelOnly, [string]$Config='services/config.local.json', [string]$GamePath)
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path $PSScriptRoot -Parent
Set-Location -LiteralPath $taskRoot
$taskRuntime = Join-Path $taskRoot 'services/.runtime'
New-Item -ItemType Directory -Path $taskRuntime -Force | Out-Null
$taskConfig = if ($Scripted) {'services/config.example.json'} else {$Config}
$taskSettings = Get-Content -LiteralPath $taskConfig -Raw | ConvertFrom-Json
$taskPython = Join-Path $taskRoot $(if($taskSettings.bridge_python){$taskSettings.bridge_python}else{'.venv/Scripts/python.exe'})
if (-not (Test-Path -LiteralPath $taskPython)) { throw 'Project Python is missing. Run Setup.cmd or follow README.md setup instructions.' }
$taskGpuLayers = if ($null -ne $taskSettings.llm_gpu_layers) { [string]$taskSettings.llm_gpu_layers } else { '99' }
$taskSelectedModel = $null
if ($taskSettings.dialogue_model) {
    $taskCatalog = Get-Content (Join-Path $taskRoot 'services/dialogue-models.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    $taskSelectedModel = $taskCatalog.models | Where-Object id -eq $taskSettings.dialogue_model
    if (!$taskSelectedModel) { throw 'Unknown dialogue model setting.' }
    if ($null -eq $taskSettings.llm_gpu_layers) { $taskGpuLayers = [string]$taskSelectedModel.gpu_layers }
}
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
    $taskLaunch = & $taskPython (Join-Path $taskRoot 'services/inference_runtime.py') $taskConfig | ConvertFrom-Json
    if ($LASTEXITCODE -ne 0) { throw 'Invalid dialogue launch settings.' }
    $taskArgumentKey = ($taskLaunch.arguments | ConvertTo-Json -Compress)
    $taskModel = Join-Path $taskRoot $(if($taskSelectedModel){$taskSelectedModel.model_path}elseif($taskSettings.llm_model_path){$taskSettings.llm_model_path}else{'.cache/models/qwen/Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-IQ4_XS.gguf'})
    $taskModelRecord=Join-Path $taskRuntime 'model-process.json'
    if((Get-Health 'http://127.0.0.1:8087/health') -and !(Test-Path -LiteralPath $taskModelRecord)) {
        throw 'Another installation is already using the dialogue service port. Stop its services before starting this GPU preset.'
    }
    if((Get-Health 'http://127.0.0.1:8087/health') -and (Test-Path -LiteralPath $taskModelRecord)) {
        $taskRunning=Get-Content -LiteralPath $taskModelRecord -Raw | ConvertFrom-Json
        if(($taskRunning.ModelPath -and $taskRunning.ModelPath -ne $taskModel) -or
           ($null -ne $taskRunning.GpuLayers -and [string]$taskRunning.GpuLayers -ne $taskGpuLayers) -or
           (!$taskRunning.ModelPath) -or $taskRunning.Arguments -ne $taskArgumentKey) {
            throw 'The running dialogue service uses older/different GPU settings. Close the game and run Stop Services.cmd, then start again.'
        }
    }
    if (-not (Get-Health 'http://127.0.0.1:8087/health')) {
        $taskServer = Join-Path $taskRoot $(if($taskSelectedModel){$taskSelectedModel.server_path}else{'.tools/llama/llama-server.exe'})
        if (-not (Test-Path -LiteralPath $taskServer) -or -not (Test-Path -LiteralPath $taskModel)) { throw 'Model/runtime missing. See README.md.' }
        $taskArguments = @($taskLaunch.arguments | ForEach-Object { if ($_ -match '\s') { '"'+$_+'"' } else { $_ } })
        $taskProcess = Start-Process -FilePath $taskServer -ArgumentList $taskArguments -WorkingDirectory $taskRoot -WindowStyle Hidden -PassThru `
            -RedirectStandardOutput (Join-Path $taskRuntime 'model.out.log') -RedirectStandardError (Join-Path $taskRuntime 'model.err.log')
        @{Id=$taskProcess.Id; Path=$taskServer; StartTicks=$taskProcess.StartTime.ToUniversalTime().Ticks; ModelPath=$taskModel; GpuLayers=$taskGpuLayers; Arguments=$taskArgumentKey} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $taskRuntime 'model-process.json')
        Write-Host "Loading dialogue model: $(if($taskSelectedModel){$taskSelectedModel.label}else{[IO.Path]::GetFileName($taskModel)})..."
        Wait-Health 'http://127.0.0.1:8087/health' 120 | Out-Null
    }
}
if ($ModelOnly) { Write-Host 'Local dialogue model is ready.'; return }
$taskSpeechHealth = Get-Health 'http://127.0.0.1:8766/health'
if ($taskSettings.tts_provider -eq 'higgs' -and $taskSpeechHealth -and $taskSpeechHealth.config_signature -ne $taskLaunch.config_signature) {
    throw 'A speech worker with different settings is running. Close the game and run Stop Services.cmd.'
}
if ($taskSettings.tts_provider -eq 'higgs' -and -not $taskSpeechHealth) {
    $taskSpeechPython = Join-Path $taskRoot $(if($taskSettings.higgs_python){$taskSettings.higgs_python}else{'.tools/alternative-tts-venv/Scripts/python.exe'})
    if (-not (Test-Path -LiteralPath $taskSpeechPython)) { throw 'Higgs environment missing. See docs/LIVE_EXPRESSIVE_SPEECH.md.' }
    $taskProcess = Start-Process -FilePath $taskSpeechPython -ArgumentList 'services/higgs_service.py','--config',('"'+$taskConfig+'"') `
        -WorkingDirectory $taskRoot -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $taskRuntime 'higgs.out.log') -RedirectStandardError (Join-Path $taskRuntime 'higgs.err.log')
    @{Id=$taskProcess.Id; Path=$taskSpeechPython; StartTicks=$taskProcess.StartTime.ToUniversalTime().Ticks} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $taskRuntime 'speech-process.json')
    Write-Host 'Loading expressive voice...'
    Wait-Health 'http://127.0.0.1:8766/health' 600 | Out-Null
}
$expectedProvider = if ($Scripted) {'scripted'} else {'llama.cpp'}
$taskBridgeHealth = Get-Health 'http://127.0.0.1:8765/health'
if ($taskBridgeHealth -and ($taskBridgeHealth.dialogue_provider -ne $expectedProvider -or
    (-not $Scripted -and $taskBridgeHealth.config_signature -ne $taskLaunch.config_signature) -or
    $taskBridgeHealth.tts_provider -ne $taskSettings.tts_provider -or
    $taskBridgeHealth.stt_provider -ne $taskSettings.stt_provider -or
    $taskBridgeHealth.stt_model -ne $taskSettings.stt_model -or
    ($taskSettings.stt_language -and $taskBridgeHealth.stt_language -ne $taskSettings.stt_language))) {
    throw 'A bridge with a different configuration is already running. Run tools/stop-services.ps1 -BridgeOnly, then launch again.'
}
if (-not $taskBridgeHealth) {
    $env:HF_HOME = Join-Path $taskRoot '.cache/huggingface'
    $env:HF_HUB_OFFLINE = '1'
    $taskProcess = Start-Process -FilePath $taskPython -ArgumentList 'services/alex_service.py','--config',('"'+$taskConfig+'"') `
        -WorkingDirectory $taskRoot -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $taskRuntime 'bridge.out.log') -RedirectStandardError (Join-Path $taskRuntime 'bridge.err.log')
    @{Id=$taskProcess.Id; Path=$taskPython; StartTicks=$taskProcess.StartTime.ToUniversalTime().Ticks} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $taskRuntime 'bridge-process.json')
    Wait-Health 'http://127.0.0.1:8765/health' 120 | Out-Null
}
if (-not $NoGame) {
    $taskGame = if ($GamePath) { [IO.Path]::GetFullPath($GamePath) } else { Join-Path $taskRoot 'unity/Builds/Windows/AlexPrototype.exe' }
    if (-not (Test-Path -LiteralPath $taskGame)) { throw 'Build the Windows prototype from the Psychology VR menu in Unity first.' }
    $taskGameArguments = @('-logFile', ('"'+(Join-Path $taskRuntime 'player.log')+'"'))
    if ($Desktop) { $taskGameArguments += '--desktop' }
    # The game is the interactive application the user is explicitly launching.
    $taskExistingGame = @(Get-Process -Name ([IO.Path]::GetFileNameWithoutExtension($taskGame)) -ErrorAction SilentlyContinue | Where-Object { $_.Path -eq $taskGame })
    if ($taskExistingGame.Count) { Write-Host 'The game application is already running.' }
    else { Start-Process -FilePath $taskGame -ArgumentList $taskGameArguments -WorkingDirectory $taskRoot }
}
Write-Host 'Alex prototype services are ready. Use tools/stop-services.ps1 after playing to free GPU memory.'
