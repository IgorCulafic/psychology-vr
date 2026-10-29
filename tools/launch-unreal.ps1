param(
    [ValidateSet('Editor','Desktop','VR')][string]$Mode='Desktop',
    [switch]$NoServices,
    [string]$Config='services/config.local.json',
    [string]$BridgeUrl='http://127.0.0.1:8765'
)
. (Join-Path $PSScriptRoot 'unreal-common.ps1')
$engine = Find-UnrealEngine
New-Item -ItemType Directory -Path $unrealRuntime -Force | Out-Null
$instancePath=Join-Path $unrealRuntime ('unreal-'+$Mode.ToLower()+'-process.json')
if(Test-Path $instancePath) {
    $instance=Get-Content $instancePath -Raw | ConvertFrom-Json
    $running=Get-Process -Id $instance.Id -ErrorAction SilentlyContinue
    if($running -and $running.Path -eq $instance.Path -and $running.StartTime.ToUniversalTime().Ticks -eq $instance.StartTicks) {
        Write-Host "Unreal $Mode is already running (PID $($instance.Id)). It may still be loading; check its window instead of opening a second copy."
        return
    }
}
# Prevent repeated clicks from starting duplicate AI/bootstrap jobs during startup.
$startupGuard=[IO.File]::Open((Join-Path $unrealRuntime 'unreal-launch.lock'),'OpenOrCreate','ReadWrite','None')
try {
$module = Join-Path $unrealRoot 'unreal/Binaries/Win64/UnrealEditor-PsychologyVR.dll'
$map = Join-Path $unrealRoot 'unreal/Content/Psychology/Consultation.umap'
$needsBuild = !(Test-Path $module) -or !(Test-Path $map)
if (!$needsBuild) {
    $builtAt = (Get-Item $module).LastWriteTimeUtc
    $needsBuild = @(Get-ChildItem (Join-Path $unrealRoot 'unreal/Source') -File -Recurse | Where-Object { $_.LastWriteTimeUtc -gt $builtAt }).Count -gt 0
}
if ($needsBuild) { & (Join-Path $PSScriptRoot 'build-unreal.ps1') }
if ($BridgeUrl -notmatch '^http://127\.0\.0\.1:\d{1,5}$') { throw 'BridgeUrl must be http://127.0.0.1:PORT.' }
if ($BridgeUrl -ne 'http://127.0.0.1:8765' -and !$NoServices) { throw 'For a separately managed bridge, supply -NoServices -BridgeUrl http://127.0.0.1:PORT.' }
if ($Mode -ne 'Editor' -and !$NoServices) {
    # Reuse the same installed model/voice configuration; never duplicate the GPU services.
    Write-Host 'Preparing the shared AI services first. Unreal opens when they are ready; keep this window open.'
    & (Join-Path $PSScriptRoot 'launch.ps1') -NoGame -Config $Config
}
$playerLog=Join-Path $unrealRuntime ('unreal-'+$Mode.ToLower()+'.log')
if(Test-Path $playerLog) { Copy-Item -LiteralPath $playerLog -Destination ($playerLog+'.previous') -Force; Clear-Content -LiteralPath $playerLog }
$arguments = @(('"'+$unrealProject+'"'), '/Game/Psychology/Consultation', '-nosplash', ('-BridgeUrl='+$BridgeUrl), ('-abslog="'+$playerLog+'"'))
if ($Mode -eq 'Desktop') { $arguments += @('-game','-nohmd','-windowed','-ResX=1600','-ResY=900') }
if ($Mode -eq 'VR') { $arguments += @('-game','-vr') }
# This is the interactive application explicitly requested by the user.
$executable=Join-Path $engine 'Engine/Binaries/Win64/UnrealEditor.exe'
$process=Start-Process -FilePath $executable -ArgumentList $arguments -WorkingDirectory $unrealRoot -PassThru
@{Id=$process.Id;Path=$executable;StartTicks=$process.StartTime.ToUniversalTime().Ticks} | ConvertTo-Json | Set-Content $instancePath
Write-Host "Starting Unreal ($Mode). First scene/shader loading may take a while. Log: $playerLog"
$deadline=(Get-Date).AddSeconds(90)
do {
    Start-Sleep -Milliseconds 500
    $process.Refresh()
    if($process.HasExited) { throw "Unreal exited during startup (code $($process.ExitCode)). See $playerLog" }
    if(Test-Path $playerLog) {
        $ready=Select-String -LiteralPath $playerLog -Pattern $(if($Mode -eq 'Editor'){'Engine is initialized'}else{'PSYCHOLOGY_WORLD_READY'}) -Quiet
        if($ready) { Write-Host "Unreal $Mode is ready."; return }
    }
} while((Get-Date) -lt $deadline)
Write-Host "Unreal is still running/loading. Follow $playerLog for progress; don't open another copy."
} finally { $startupGuard.Dispose() }
