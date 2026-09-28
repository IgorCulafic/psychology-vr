param([Parameter(Mandatory=$true)][ValidateSet('bonsai','gemma','qwen')][string]$Model,
      [string]$Config='services/config.local.json')
$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
if (![IO.Path]::IsPathRooted($Config)) { $Config=Join-Path $root $Config }
$settings=Get-Content -LiteralPath $Config -Raw | ConvertFrom-Json
$catalog=Get-Content (Join-Path $root 'services/dialogue-models.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$selected=$catalog.models | Where-Object id -eq $Model
foreach ($relative in @($selected.model_path,$selected.server_path)) {
    if (!(Test-Path -LiteralPath (Join-Path $root $relative))) { throw "Model/runtime missing: $relative" }
}
# A file handle serializes model changes, including separate bridge instances.
$lockPath=Join-Path $root 'services/.runtime/model-selection.lock'
$guard=[IO.File]::Open($lockPath,'OpenOrCreate','ReadWrite','None')
$staged=Join-Path $root 'services/.runtime/model-selection.config.json'
try {
    $old=Get-Content -LiteralPath $Config -Raw
    $settings | Add-Member -NotePropertyName dialogue_model -NotePropertyValue $Model -Force
    $settings | Add-Member -NotePropertyName llm_model_path -NotePropertyValue $selected.model_path -Force
    $settings | Add-Member -NotePropertyName llm_gpu_layers -NotePropertyValue $selected.gpu_layers -Force
    $settings | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $staged -Encoding UTF8
    $recordPath=Join-Path $root 'services/.runtime/model-process.json'
    $healthy=$false
    try { $healthy=[bool](Invoke-RestMethod 'http://127.0.0.1:8087/health' -TimeoutSec 2) } catch {}
    if ($healthy) {
        if (!(Test-Path $recordPath)) { throw 'Another model server owns port 8087. Stop it yourself before switching.' }
        $record=Get-Content $recordPath -Raw | ConvertFrom-Json
        $process=Get-Process -Id $record.Id -ErrorAction SilentlyContinue
        if (!$process -or $process.Path -ne $record.Path -or $process.StartTime.ToUniversalTime().Ticks -ne $record.StartTicks) {
            throw 'Model process ownership could not be verified. No process was stopped.'
        }
    }
    & (Join-Path $PSScriptRoot 'stop-services.ps1') -ModelOnly
    try {
        & (Join-Path $PSScriptRoot 'launch.ps1') -ModelOnly -Config $staged
        # The durable setting changes only after the new model passes its health check.
        $saved=$Config+'.tmp'
        $settings | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $saved -Encoding UTF8
        Move-Item -LiteralPath $saved -Destination $Config -Force
    } catch {
        $failure=$_
        & (Join-Path $PSScriptRoot 'stop-services.ps1') -ModelOnly
        $old | Set-Content -LiteralPath $staged -Encoding UTF8
        try { & (Join-Path $PSScriptRoot 'launch.ps1') -ModelOnly -Config $staged } catch { Write-Warning "Previous model could not be restored: $_" }
        throw $failure
    }
} finally { $guard.Dispose() }
