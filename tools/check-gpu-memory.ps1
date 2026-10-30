$ErrorActionPreference='Stop'
$taskRoot=Split-Path $PSScriptRoot -Parent
$taskOutput=Join-Path $taskRoot 'services/.runtime/gpu-memory-snapshot.json'
$taskRows=@{}
try {
    $taskCounters=Get-Counter '\GPU Process Memory(*)\Shared Usage','\GPU Process Memory(*)\Dedicated Usage'
    foreach($taskSample in $taskCounters.CounterSamples) {
        if($taskSample.InstanceName -notmatch '^pid_(\d+)_') { continue }
        $taskProcessId=[int]$Matches[1]
        if(!$taskRows.ContainsKey($taskProcessId)) {
            $taskProcess=Get-Process -Id $taskProcessId -ErrorAction SilentlyContinue
            $taskRows[$taskProcessId]=[ordered]@{pid=$taskProcessId;name=$taskProcess.ProcessName;shared_mib=0;dedicated_mib=0}
        }
        $taskField=if($taskSample.Path -match '\\shared usage$'){'shared_mib'}else{'dedicated_mib'}
        $taskRows[$taskProcessId][$taskField]+=[math]::Round($taskSample.CookedValue/1MB,1)
    }
    $taskResult=[ordered]@{timestamp=(Get-Date).ToUniversalTime().ToString('o');available=$true;
        scope='Windows GPU process memory, summed across adapters';processes=@($taskRows.Values | Where-Object { $_.shared_mib -gt 1 -or $_.dedicated_mib -gt 1 })}
} catch {
    $taskResult=[ordered]@{timestamp=(Get-Date).ToUniversalTime().ToString('o');available=$false;
        reason='GPU performance counters unavailable; inspect Task Manager GPU dedicated/shared memory.';processes=@()}
}
New-Item -ItemType Directory -Path (Split-Path $taskOutput) -Force | Out-Null
$taskResult | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $taskOutput -Encoding UTF8
if($taskResult.available) { $taskResult.processes | ForEach-Object { [pscustomobject]$_ } | Sort-Object dedicated_mib -Descending | Format-Table }
else { Write-Host $taskResult.reason }
Write-Host 'Saved:' $taskOutput
Write-Host 'Shared memory is a diagnostic signal, not proof of paging. Compare with generation timing and dedicated-memory headroom.'
