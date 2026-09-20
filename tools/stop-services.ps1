param([switch]$BridgeOnly, [switch]$ModelOnly, [switch]$SpeechOnly)
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path $PSScriptRoot -Parent
if (([int]$BridgeOnly.IsPresent+[int]$ModelOnly.IsPresent+[int]$SpeechOnly.IsPresent) -gt 1) { throw 'Choose only one service selector.' }
$taskServices = if ($BridgeOnly) { @('bridge') } elseif ($ModelOnly) { @('model') } elseif ($SpeechOnly) { @('speech') } else { @('bridge','speech','model') }
foreach ($taskName in $taskServices) {
    $taskRecord = Join-Path $taskRoot "services/.runtime/$taskName-process.json"
    if (Test-Path -LiteralPath $taskRecord) {
        $taskInfo = Get-Content -LiteralPath $taskRecord -Raw | ConvertFrom-Json
        $taskProcess = Get-Process -Id $taskInfo.Id -ErrorAction SilentlyContinue
        # The Windows venv launcher can spawn a second Python process. Stop its
        # project-local bridge child as well, without touching other Python jobs.
        if ($taskProcess -and $taskProcess.Path -eq $taskInfo.Path -and
            $taskProcess.StartTime.ToUniversalTime().Ticks -eq $taskInfo.StartTicks) {
            if ($taskName -in @('bridge','speech')) {
                Get-CimInstance Win32_Process -Filter "ParentProcessId = $($taskInfo.Id)" | ForEach-Object {
                    # uv's registered venv launcher may use a base Python outside the project.
                    # Parent identity/start time above and the specific child script below scope it.
                    if ($_.ExecutablePath -and ([IO.Path]::GetFileName($_.ExecutablePath) -eq 'python.exe') -and
                        $_.CommandLine -match 'services[\\/](alex_service|emotion_audition|higgs_service)\.py') {
                        $taskChild = Get-Process -Id $_.ProcessId -ErrorAction SilentlyContinue
                        if ($taskChild -and -not $taskChild.HasExited) { $taskChild.Kill(); $taskChild.WaitForExit(5000) | Out-Null }
                    }
                }
            }
            if (-not $taskProcess.HasExited) { $taskProcess.Kill(); $taskProcess.WaitForExit(5000) | Out-Null }
        }
        Remove-Item -LiteralPath $taskRecord
    }
}
Write-Host 'Stopped services started by this project launcher.'
