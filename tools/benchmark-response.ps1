param([int]$Turns=8, [string]$Audio, [double]$TargetSeconds=14)
$ErrorActionPreference='Stop'
$taskRoot=Split-Path $PSScriptRoot -Parent
Set-Location -LiteralPath $taskRoot
& (Join-Path $PSScriptRoot 'launch.ps1') -NoGame
$taskPython=Join-Path $taskRoot '.tools/portable-env/Scripts/python.exe'
$taskArgs=@((Join-Path $PSScriptRoot 'benchmark-response.py'),'--turns',[string]$Turns,'--target-seconds',$TargetSeconds.ToString([Globalization.CultureInfo]::InvariantCulture))
if ($Audio) { $taskArgs+=@('--audio',$Audio) }
& $taskPython @taskArgs
if ($LASTEXITCODE -ne 0) { throw 'Benchmark failed; inspect services/.runtime logs.' }
