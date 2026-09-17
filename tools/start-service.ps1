param([string]$Config = 'services/config.local.json')
$ErrorActionPreference='Stop'
$taskRoot = Split-Path $PSScriptRoot -Parent
Set-Location -LiteralPath $taskRoot
$env:HF_HOME = Join-Path $taskRoot '.cache/huggingface'
$env:HF_HUB_OFFLINE = '1'
$pythonPath = Join-Path $taskRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { $pythonPath = 'python' }
& $pythonPath services/alex_service.py --config $Config
