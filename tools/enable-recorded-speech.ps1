$ErrorActionPreference='Stop'
$taskRoot=Split-Path $PSScriptRoot -Parent
Set-Location -LiteralPath $taskRoot
try {
    Write-Host 'Close the game before enabling recorded speech.'
    & (Join-Path $PSScriptRoot 'stop-services.ps1')
    $taskPython=Join-Path $taskRoot '.tools/portable-env/Scripts/python.exe'
    if (!(Test-Path -LiteralPath $taskPython)) { throw 'Run Setup.cmd first.' }
    & $taskPython (Join-Path $PSScriptRoot 'enable-recorded-speech.py')
    if ($LASTEXITCODE -ne 0) { throw 'Recorded speech was not enabled.' }
} catch { Write-Host $_.Exception.Message; exit 1 }
