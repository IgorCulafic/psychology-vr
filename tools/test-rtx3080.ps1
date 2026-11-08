param(
    [ValidateSet('menu','preflight','quick','tuning','voice','voice-ab','stt','q8','combined-bf16','combined-nf4','monitor')]
    [string]$Mode='menu',
    [int]$Turns=4,
    [int]$Repeats=2,
    [int]$Seconds=120,
    [ValidateRange(0,49)][Nullable[int]]$GpuLayers,
    [string]$Audio,
    [switch]$AllowQuantizedVoice
)
$ErrorActionPreference='Stop'
$taskRoot=Split-Path $PSScriptRoot -Parent
$taskPython=Join-Path $taskRoot '.tools/portable-env/Scripts/python.exe'
if (!(Test-Path -LiteralPath $taskPython)) { $taskPython=Join-Path $taskRoot '.venv/Scripts/python.exe' }
if (!(Test-Path -LiteralPath $taskPython)) { throw 'Run this inside the complete PsychologyVR application with its Python runtime installed.' }
if ($Mode -eq 'menu') {
    Write-Host 'RTX 3080 performance test - 10 GB / 12 GB'
    Write-Host 'Close the game and Stop Services before isolated tests. Reports stay on this PC.'
    Write-Host '1. Quick test: QAT Q4 dialogue, BF16 cloned voices, CPU STT (separate stages)'
    Write-Host '2. Dialogue tuning: baseline vs smaller batch vs 4 CPU threads'
    Write-Host '3. BF16 voice-only test (four assigned voices, cold/warm)'
    Write-Host '4. BF16 decoder A/B comparison (WAV parity and speed)'
    Write-Host '5. CPU transcription: beam 5 vs 1'
    Write-Host '6. Primary Q8 dialogue-only, partial GPU offload (slower comparison)'
    Write-Host '7. Combined BF16 speech + CPU dialogue (slow diagnostic; can take 10+ minutes)'
    Write-Host '8. EXPERIMENT: combined NF4 speech + partial GPU QAT dialogue (voice quality changes)'
    Write-Host '9. Hardware preflight only'
    Write-Host '10. Monitor GPU during your own game conversation (120 seconds)'
    Write-Host '0. Exit'
    $taskChoice=Read-Host 'Choose test'
    $taskModes=@{'1'='quick';'2'='tuning';'3'='voice';'4'='voice-ab';'5'='stt';'6'='q8';'7'='combined-bf16';'8'='combined-nf4';'9'='preflight';'10'='monitor'}
    if ($taskChoice -eq '0') { exit 0 }
    if (!$taskModes.ContainsKey($taskChoice)) { throw 'Choose one of the listed tests.' }
    $Mode=$taskModes[$taskChoice]
    if ($Mode -eq 'combined-nf4') { $AllowQuantizedVoice=$true }
}
if ($Mode -eq 'combined-nf4' -and !$AllowQuantizedVoice) {
    throw 'This changes voice precision for a quality comparison. Pass -AllowQuantizedVoice to opt in.'
}
$taskArguments=@((Join-Path $PSScriptRoot 'test-rtx3080.py'),'--mode',$Mode,'--turns',"$Turns",'--repeats',"$Repeats",'--seconds',"$Seconds")
if ($Audio) { $taskArguments+=@('--audio',$Audio) }
if ($null -ne $GpuLayers) { $taskArguments+=@('--gpu-layers',"$GpuLayers") }
if ($AllowQuantizedVoice) { $taskArguments+='--allow-quantized-voice' }
& $taskPython @taskArguments
exit $LASTEXITCODE
