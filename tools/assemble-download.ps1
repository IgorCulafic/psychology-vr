param([string]$Folder=$PSScriptRoot)
$ErrorActionPreference='Stop'
$taskFolder=[IO.Path]::GetFullPath($Folder)
$taskManifest=Get-Content -LiteralPath (Join-Path $taskFolder 'download-manifest.json') -Raw | ConvertFrom-Json
if ([IO.Path]::GetFileName($taskManifest.archive) -ne $taskManifest.archive -or [string]::IsNullOrWhiteSpace($taskManifest.archive)) { throw 'Invalid archive name in download manifest.' }
$taskArchive=Join-Path $taskFolder $taskManifest.archive
if (Test-Path -LiteralPath $taskArchive) {
    if ((Get-FileHash -LiteralPath $taskArchive -Algorithm SHA256).Hash -eq $taskManifest.archive_sha256) {
        Write-Host 'The complete verified ZIP already exists.';exit 0
    }
    throw 'An existing ZIP has a different checksum. Rename it before assembling.'
}
foreach ($taskPart in $taskManifest.parts) {
    if ([IO.Path]::GetFileName($taskPart.name) -ne $taskPart.name) { throw 'Invalid download manifest path.' }
    $taskPath=Join-Path $taskFolder $taskPart.name
    if (!(Test-Path -LiteralPath $taskPath) -or (Get-Item -LiteralPath $taskPath).Length -ne $taskPart.bytes) {
        throw "Missing/incomplete download: $($taskPart.name)"
    }
    Write-Host "Verifying $($taskPart.name)..."
    if ((Get-FileHash -LiteralPath $taskPath -Algorithm SHA256).Hash -ne $taskPart.sha256) { throw "Checksum failed: $($taskPart.name)" }
}
$taskTemporary=$taskArchive+'.assembling'
if (Test-Path -LiteralPath $taskTemporary) { throw 'An unfinished assembly exists. Rename or remove that .assembling file before retrying.' }
$taskOutput=[IO.File]::Open($taskTemporary,'CreateNew','Write','None')
try {
    foreach ($taskPart in $taskManifest.parts) {
        Write-Host "Joining $($taskPart.name)..."
        $taskInput=[IO.File]::OpenRead((Join-Path $taskFolder $taskPart.name))
        try { $taskInput.CopyTo($taskOutput,8MB) } finally { $taskInput.Dispose() }
    }
} finally { $taskOutput.Dispose() }
if ((Get-FileHash -LiteralPath $taskTemporary -Algorithm SHA256).Hash -ne $taskManifest.archive_sha256) { throw 'Final ZIP checksum failed.' }
Move-Item -LiteralPath $taskTemporary -Destination $taskArchive
Write-Host "Verified ZIP ready: $taskArchive"
Write-Host 'Extract the complete PsychologyVR folder, then run Setup.cmd.'
