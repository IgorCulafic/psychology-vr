param([ValidateSet('rtx3080','rtx4090')][string]$Profile)
$ErrorActionPreference='Stop'
$taskRoot=[IO.Path]::GetFullPath((Split-Path $PSScriptRoot -Parent))
Set-Location -LiteralPath $taskRoot
$taskPython=Join-Path $taskRoot '.tools/portable-env/Scripts/python.exe'
if (!(Test-Path -LiteralPath $taskPython)) { throw 'Run Setup.cmd first.' }
if (!$Profile) {
    Write-Host 'Hardware profiles. Close the game before switching.'
    Write-Host '1. RTX 3080 (default): Gemma QAT Q4, English, Kokoro voice'
    Write-Host '2. RTX 4090: Gemma Q8, Montenegrin, assigned BF16 cloned voices'
    Write-Host 'Both keep compact responses, cached prompts, model warmup and exact speech reuse.'
    $taskChoice=Read-Host 'Choose 1 or 2, or Enter to cancel'
    $Profile=switch($taskChoice){'1'{'rtx3080'} '2'{'rtx4090'} default{$null}}
    if (!$Profile) { return }
}
$taskGame=Join-Path $taskRoot 'unity/Builds/Windows/AlexPrototype.exe'
$taskRunning=@(Get-Process -Name AlexPrototype -ErrorAction SilentlyContinue | Where-Object { $_.Path -eq $taskGame })
if ($taskRunning.Count) { throw 'Close this installation''s game before switching hardware profiles.' }
& $taskPython (Join-Path $PSScriptRoot 'hardware-profile.py') $Profile --check
if ($LASTEXITCODE -ne 0) { throw 'The requested profile is invalid; no settings changed.' }
$taskRuntime=Join-Path $taskRoot 'services/.runtime'
New-Item -ItemType Directory -Path $taskRuntime -Force | Out-Null
$taskLock=$null
try {
    $taskLock=[IO.File]::Open((Join-Path $taskRuntime 'setup.lock'),'OpenOrCreate','ReadWrite','None')
    & (Join-Path $PSScriptRoot 'stop-services.ps1')
    & $taskPython (Join-Path $PSScriptRoot 'hardware-profile.py') $Profile
    if ($LASTEXITCODE -ne 0) { throw 'The profile could not be saved. The previous configuration was backed up.' }
    Write-Host 'Profile selected. Start Desktop, Start VR or Start Text Chat normally.'
    Write-Host 'The RTX 4090 profile requires the corresponding hardware and model downloads.'
} finally {
    if($taskLock){$taskLock.Dispose()}
}
