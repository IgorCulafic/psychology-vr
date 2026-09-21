param([string]$Config='services/config.local.json', [switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path $PSScriptRoot -Parent
Set-Location -LiteralPath $taskRoot
& (Join-Path $PSScriptRoot 'launch.ps1') -ModelOnly -Config $Config
$taskUrl = 'http://127.0.0.1:8794'
$taskHealth = $null
try { $taskHealth = Invoke-RestMethod "$taskUrl/health" -TimeoutSec 2 } catch {}
if ($taskHealth -and $taskHealth.service -ne 'psychology-text-chat') { throw 'Port 8794 is occupied by a different application.' }
if (-not $taskHealth) {
    $taskRuntime = Join-Path $taskRoot 'services/.runtime'
    $taskSettings=Get-Content -LiteralPath $Config -Raw | ConvertFrom-Json
    $taskPython = Join-Path $taskRoot $(if($taskSettings.bridge_python){$taskSettings.bridge_python}else{'.venv/Scripts/python.exe'})
    $taskProcess = Start-Process -FilePath $taskPython -ArgumentList 'services/text_chat.py','--config',('"'+$Config+'"') -WorkingDirectory $taskRoot -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $taskRuntime 'text-chat.out.log') -RedirectStandardError (Join-Path $taskRuntime 'text-chat.err.log')
    @{Id=$taskProcess.Id; Path=$taskPython; StartTicks=$taskProcess.StartTime.ToUniversalTime().Ticks} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $taskRuntime 'text-chat-process.json')
    $taskDeadline = (Get-Date).AddSeconds(20)
    do {
        try { $taskHealth = Invoke-RestMethod "$taskUrl/health" -TimeoutSec 2 } catch {}
        if ($taskHealth) { break }
        Start-Sleep -Milliseconds 300
    } while ((Get-Date) -lt $taskDeadline)
    if (-not $taskHealth -or $taskHealth.service -ne 'psychology-text-chat') { throw 'Text chat did not start. Check services/.runtime/text-chat.err.log.' }
}
if (-not $NoBrowser) { Start-Process "$taskUrl/" }
Write-Host "Text conversations: $taskUrl/"
Write-Host 'Stop everything afterwards with tools/stop-services.ps1; -TextOnly stops only this browser service.'
