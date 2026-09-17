$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path $PSScriptRoot -Parent
foreach ($taskName in @('bridge','model')) {
    $taskRecord = Join-Path $taskRoot "services/.runtime/$taskName-process.json"
    if (Test-Path -LiteralPath $taskRecord) {
        $taskInfo = Get-Content -LiteralPath $taskRecord -Raw | ConvertFrom-Json
        $taskProcess = Get-Process -Id $taskInfo.Id -ErrorAction SilentlyContinue
        # The Windows venv launcher can spawn a second Python process. Stop its
        # project-local bridge child as well, without touching other Python jobs.
        if ($taskProcess -and $taskProcess.Path -eq $taskInfo.Path -and
            $taskProcess.StartTime.ToUniversalTime().Ticks -eq $taskInfo.StartTicks) {
            if ($taskName -eq 'bridge') {
                Get-CimInstance Win32_Process -Filter "ParentProcessId = $($taskInfo.Id)" | ForEach-Object {
                    if ($_.ExecutablePath -and $_.ExecutablePath.StartsWith($taskRoot + '\', [StringComparison]::OrdinalIgnoreCase) -and
                        $_.CommandLine -match 'services/alex_service.py') {
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
