param(
    [string]$Cases = 'all'
)
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$fishPython = Join-Path $taskRoot '.tools\fish-speech\.venv\Scripts\python.exe'
$fishModel = Join-Path $taskRoot '.cache\fish-s2-pro\model.safetensors.index.json'
if (-not (Test-Path -LiteralPath $fishPython) -or -not (Test-Path -LiteralPath $fishModel)) {
    throw 'Fish S2 Pro is not installed. See docs/FISH_LOCAL_SETUP.md.'
}
$env:PYTHONUTF8 = '1'
& $fishPython -u (Join-Path $taskRoot 'tools\audition_fish_local.py') --cases $Cases
exit $LASTEXITCODE
