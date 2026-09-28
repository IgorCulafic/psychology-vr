param([switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path $PSScriptRoot -Parent
Set-Location -LiteralPath $taskRoot
$taskUrl = 'http://127.0.0.1:8797'
$taskHealth = $null
try { $taskHealth = Invoke-RestMethod "$taskUrl/health" -TimeoutSec 2 } catch {}
if ($taskHealth) {
    if ($taskHealth.service -ne 'psychology-model-lab') { throw 'Port 8797 is occupied by another application.' }
    if (-not $NoBrowser) { Start-Process "$taskUrl/" }
    Write-Host "Model Lab is already running: $taskUrl/"
    exit 0
}
$taskPython = $null
foreach ($taskCandidate in @('.tools/portable-env/Scripts/python.exe', '.venv/Scripts/python.exe')) {
    $taskPath = Join-Path $taskRoot $taskCandidate
    if (Test-Path -LiteralPath $taskPath) { $taskPython = $taskPath; break }
}
if (-not $taskPython) { throw 'Run Setup.cmd first, or run services/model_lab.py with Python 3.11 or newer.' }
Write-Host "Model Lab: $taskUrl/"
Write-Host 'Keep this window open. Ctrl+C stops the lab and requests cancellation of its active test.'
Write-Host 'The lab uses the loaded model at 127.0.0.1:8087. Start the intended model before testing.'
if (-not $NoBrowser) { Start-Process "$taskUrl/" }
& $taskPython -u (Join-Path $taskRoot 'services/model_lab.py')
exit $LASTEXITCODE
