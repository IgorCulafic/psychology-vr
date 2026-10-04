$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path $PSScriptRoot -Parent
Set-Location -LiteralPath $taskRoot
try {
    $taskCandidates = @((Join-Path $taskRoot '.tools/portable-env/Scripts/python.exe'), (Join-Path $taskRoot '.venv/Scripts/python.exe'))
    $taskPython = $taskCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    if (!$taskPython) { throw 'Run Setup.cmd once to install the project Python, then export again.' }
    & $taskPython (Join-Path $PSScriptRoot 'export-diagnostics.py')
    if ($LASTEXITCODE -ne 0) { throw 'Diagnostics export failed. See the error above.' }
    exit 0
} catch {
    Write-Host $_.Exception.Message
    exit 1
}
