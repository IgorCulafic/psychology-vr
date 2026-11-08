param([ValidateSet('quality','fast-clone','int8-clone','vr-friendly','throughput','mtp-on','mtp-off','latency-bf16','audio-envelope','rhubarb','sentence-start','approved-phrasing','q8-gpu-bf16')][string]$Profile)
$ErrorActionPreference='Stop'
$taskRoot=Split-Path $PSScriptRoot -Parent
Set-Location -LiteralPath $taskRoot
$taskPython=Join-Path $taskRoot '.tools/portable-env/Scripts/python.exe'
if (!(Test-Path -LiteralPath $taskPython)) { throw 'Run Setup.cmd first.' }
if (!$Profile) {
    Write-Host 'Optimization settings. Close the game before applying a profile.'
    Write-Host '1. BF16 voice quality (Gemma Q8 with partial CPU offload)'
    Write-Host '2. Faster NF4 cloned voices (Gemma Q8 fully on GPU; listen before teaching)'
    Write-Host '3. INT8 cloned voices (comparison; can be slower than BF16)'
    Write-Host '4. Smaller batches for VR rendering'
    Write-Host '5. Larger batches for prompt throughput'
    Write-Host '6. Enable optional Gemma MTP speculative decoding'
    Write-Host '7. Disable MTP'
    Write-Host '8. Optional low latency: QAT Q4 + BF16 voices, sentence delivery, greedy STT (install QAT Q4 via PC Settings 6 first)'
    Write-Host '9. Audio envelope mouth movement (skip Rhubarb alignment; less precise lips)'
    Write-Host '10. Restore Rhubarb mouth alignment'
    Write-Host '11. Optional sentence streaming (same voice/precision; listen for changed phrasing)'
    Write-Host '12. Restore the voice pack''s approved phrasing mode'
    Write-Host '13. Experimental Q8 fully on GPU + BF16, smaller buffers/single context (24 GB may be tight)'
    $taskChoice=Read-Host 'Choose 1 to 13, or Enter to cancel'
    $Profile=switch($taskChoice){'1'{'quality'} '2'{'fast-clone'} '3'{'int8-clone'} '4'{'vr-friendly'} '5'{'throughput'} '6'{'mtp-on'} '7'{'mtp-off'} '8'{'latency-bf16'} '9'{'audio-envelope'} '10'{'rhubarb'} '11'{'sentence-start'} '12'{'approved-phrasing'} '13'{'q8-gpu-bf16'} default{$null}}
    if (!$Profile) { return }
}
& (Join-Path $PSScriptRoot 'stop-services.ps1')
& $taskPython (Join-Path $PSScriptRoot 'optimization-settings.py') $Profile
if ($LASTEXITCODE -ne 0) { throw 'Optimization settings were not applied.' }
