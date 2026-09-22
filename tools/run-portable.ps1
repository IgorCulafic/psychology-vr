param([ValidateSet('VR','Desktop','Text','Setup','Check','Settings')][string]$Mode='VR')
$ErrorActionPreference='Stop'
$taskRoot=[IO.Path]::GetFullPath((Split-Path $PSScriptRoot -Parent))
Set-Location -LiteralPath $taskRoot
$taskRuntime=Join-Path $taskRoot 'services/.runtime'
New-Item -ItemType Directory -Path $taskRuntime -Force | Out-Null
$taskLock=$null
function Invoke-Checked([string]$Executable,[string[]]$Arguments) {
    & $Executable @Arguments
    if($LASTEXITCODE -ne 0){throw "Command failed (exit $LASTEXITCODE): $Executable"}
}
try {
    $taskLock=[IO.File]::Open((Join-Path $taskRuntime 'setup.lock'),'OpenOrCreate','ReadWrite','None')
    Start-Transcript -Path (Join-Path $taskRuntime 'setup-latest.log') -Force | Out-Null
    $taskPreset=$null
    if($Mode -eq 'Settings') {
        Write-Host 'PC settings - dialogue model and GPU allocation. Voice quality is unchanged.'
        Write-Host 'Close the game first. This will stop this installation''s AI services.'
        Write-Host '1. Auto-detect GPU (recommended): 24 GB -> RTX 4090 preset; 32 GB+ -> original quality'
        Write-Host '2. University / RTX 4090: IQ3_M, 32 GPU layers'
        Write-Host '3. Original quality: IQ4_XS, 48 GPU layers (32 GB+ recommended)'
        Write-Host 'Enter to cancel.'
        $taskChoice=Read-Host 'Choose 1, 2 or 3'
        $taskPreset=switch($taskChoice){'1'{'auto'} '2'{'rtx4090'} '3'{'quality'} default{$null}}
        if(!$taskPreset){Write-Host 'No settings changed.';return}
        & (Join-Path $PSScriptRoot 'stop-services.ps1')
    }
    $taskManifest=Get-Content (Join-Path $taskRoot 'services/portable-manifest.json') -Raw | ConvertFrom-Json
    $env:UV_PYTHON_INSTALL_DIR=Join-Path $taskRoot '.tools/python'
    $env:UV_CACHE_DIR=Join-Path $taskRoot '.cache/uv'
    $env:HF_HOME=Join-Path $taskRoot '.cache/huggingface'
    $env:HF_HUB_DISABLE_TELEMETRY='1';$env:PYTHONUTF8='1'
    $taskPython=Join-Path $taskRoot '.tools/portable-env/Scripts/python.exe'
    $taskStampPath=Join-Path $taskRuntime 'portable-ready.json'
    $taskKey=(Get-FileHash services/portable-manifest.json).Hash+(Get-FileHash services/requirements-portable.txt).Hash
    $taskReady=$false
    if((Test-Path -LiteralPath $taskStampPath) -and (Test-Path -LiteralPath $taskPython)) {
        $taskStamp=Get-Content -LiteralPath $taskStampPath -Raw | ConvertFrom-Json
        $taskReady=($taskStamp.root -eq $taskRoot -and $taskStamp.key -eq $taskKey -and $Mode -notin @('Setup','Settings'))
    }
    if(-not $taskReady) {
        Write-Host 'Setup: Python, speech libraries and approximately 25-28 GB of AI models, depending on GPU preset.'
        Write-Host 'Keep this window open. A failed download can be resumed by starting again.'
        $taskBootstrap=Join-Path $taskRoot '.tools/bootstrap'
        New-Item -ItemType Directory -Path $taskBootstrap -Force | Out-Null
        $taskZip=Join-Path $taskBootstrap 'uv.zip'
        if(!(Test-Path -LiteralPath $taskZip) -or (Get-FileHash -LiteralPath $taskZip).Hash -ne $taskManifest.uv.sha256) {
            [Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12
            Invoke-WebRequest -UseBasicParsing -Uri $taskManifest.uv.url -OutFile $taskZip
        }
        if((Get-FileHash -LiteralPath $taskZip).Hash -ne $taskManifest.uv.sha256){throw 'Installer checksum mismatch; run setup again.'}
        Expand-Archive -LiteralPath $taskZip -DestinationPath $taskBootstrap -Force
        $taskUv=(Get-ChildItem -LiteralPath $taskBootstrap -Filter uv.exe -Recurse | Select-Object -First 1).FullName
        if(!$taskUv){throw 'Portable package installer was not found.'}
        Invoke-Checked $taskUv @('python','install',$taskManifest.python,'--no-registry','--no-bin')
        $taskBase=(& $taskUv python find $taskManifest.python --managed-python).Trim()
        if($LASTEXITCODE -ne 0){throw 'Python setup failed.'}
        # Environments can be recreated after moving the folder; logs/voices/config stay intact.
        $taskEnvironment=[IO.Path]::GetFullPath((Join-Path $taskRoot '.tools/portable-env'))
        if($taskEnvironment -ne ($taskRoot.TrimEnd('\')+'\.tools\portable-env')){throw 'Unexpected environment folder.'}
        $taskEnvironmentStamp=Join-Path $taskRuntime 'portable-environment.json'
        $taskEnvironmentReady=$false
        if((Test-Path -LiteralPath $taskEnvironmentStamp) -and (Test-Path -LiteralPath $taskPython)) {
            $taskPrevious=Get-Content -LiteralPath $taskEnvironmentStamp -Raw | ConvertFrom-Json
            $taskEnvironmentReady=($taskPrevious.root -eq $taskRoot -and $taskPrevious.key -eq $taskKey)
        }
        if(-not $taskEnvironmentReady) {
            if(Test-Path -LiteralPath $taskEnvironment) {
                Invoke-Checked $taskUv @('venv','--clear','--python',$taskBase,$taskEnvironment)
            } else {Invoke-Checked $taskUv @('venv','--python',$taskBase,$taskEnvironment)}
            Invoke-Checked $taskUv @('pip','install','--python',$taskPython,'-r',(Join-Path $taskRoot 'services/requirements-portable.txt'))
            @{root=$taskRoot;key=$taskKey} | ConvertTo-Json | Set-Content -LiteralPath $taskEnvironmentStamp -Encoding UTF8
        }
        $env:HF_HUB_OFFLINE='0'
        $taskSetupArguments=@((Join-Path $PSScriptRoot 'setup-portable.py'))
        if($taskPreset){$taskSetupArguments+=@('--preset',$taskPreset)}
        Invoke-Checked $taskPython $taskSetupArguments
        @{root=$taskRoot;key=$taskKey} | ConvertTo-Json | Set-Content -LiteralPath $taskStampPath -Encoding UTF8
    }
    Invoke-Checked $taskPython @((Join-Path $PSScriptRoot 'setup-portable.py'),'--check')
    $taskLock.Dispose();$taskLock=$null
    if($Mode -eq 'VR'){& (Join-Path $PSScriptRoot 'launch.ps1')}
    elseif($Mode -eq 'Desktop'){& (Join-Path $PSScriptRoot 'launch.ps1') -Desktop}
    elseif($Mode -eq 'Text'){& (Join-Path $PSScriptRoot 'launch-text-chat.ps1')}
    else {Write-Host 'Setup complete. You can now use Start VR, Start Desktop or Start Text Chat.'}
} catch {
    Write-Host "`nCould not start: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host 'Details: services/.runtime/setup-latest.log. Close duplicate launchers, then try again.'
    exit 1
} finally {
    if($taskLock){$taskLock.Dispose()}
    try {Stop-Transcript | Out-Null} catch {}
}
