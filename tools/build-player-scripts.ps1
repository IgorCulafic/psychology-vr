param(
    [string]$Compiler = '.tools/roslyn/4.14.0/tasks/net472/csc.exe',
    [string]$PlayerDirectory = 'unity/Builds/Windows'
)
$ErrorActionPreference = 'Stop'
$taskRoot = [IO.Path]::GetFullPath((Split-Path $PSScriptRoot -Parent))
Set-Location -LiteralPath $taskRoot
$taskCompiler = [IO.Path]::GetFullPath((Join-Path $taskRoot $Compiler))
$taskPlayer = [IO.Path]::GetFullPath((Join-Path $taskRoot $PlayerDirectory))
$taskManaged = Join-Path $taskPlayer 'AlexPrototype_Data/Managed'
$taskAssembly = Join-Path $taskManaged 'Assembly-CSharp.dll'
if (!(Test-Path -LiteralPath $taskCompiler)) { throw 'Microsoft C# compiler missing. Use Unity Editor to build, or provide -Compiler.' }
if (!(Test-Path -LiteralPath $taskAssembly)) { throw 'A complete Mono Windows player is required. Extract the verified Windows release first.' }
$taskExistingGame = @(Get-Process -Name AlexPrototype -ErrorAction SilentlyContinue | Where-Object { $_.Path -eq (Join-Path $taskPlayer 'AlexPrototype.exe') })
if ($taskExistingGame.Count) { throw 'Close this installation of Psychology VR before rebuilding its scripts.' }
$taskBuild = Join-Path $taskRoot 'services/.runtime/player-script-build'
New-Item -ItemType Directory -Path $taskBuild -Force | Out-Null
$taskOutput = Join-Path $taskBuild 'Assembly-CSharp.dll'
$taskResponse = Join-Path $taskBuild 'compile.rsp'
$taskOptions = @(
    '/nologo', '/target:library', '/nostdlib+', '/langversion:latest', '/optimize+',
    '/define:UNITY_6000_6_OR_NEWER;UNITY_6000_0_OR_NEWER;UNITY_STANDALONE;UNITY_STANDALONE_WIN;UNITY_64;ENABLE_INPUT_SYSTEM',
    ('/out:"' + $taskOutput + '"')
)
$taskOptions += Get-ChildItem -LiteralPath $taskManaged -Filter '*.dll' | Where-Object Name -ne 'Assembly-CSharp.dll' | ForEach-Object { '/reference:"' + $_.FullName + '"' }
$taskOptions += Get-ChildItem -LiteralPath (Join-Path $taskRoot 'unity/Assets') -Filter '*.cs' -Recurse | Where-Object { $_.FullName -notmatch '[\\/]Editor[\\/]' } | ForEach-Object { '"' + $_.FullName + '"' }
[IO.File]::WriteAllLines($taskResponse, [string[]]$taskOptions, [Text.UTF8Encoding]::new($false))
& $taskCompiler ('@' + $taskResponse)
if ($LASTEXITCODE -ne 0) { throw 'Player script compilation failed; the existing player has not been changed.' }
$taskOriginalName = [Reflection.AssemblyName]::GetAssemblyName($taskAssembly)
$taskNewName = [Reflection.AssemblyName]::GetAssemblyName($taskOutput)
if ($taskOriginalName.FullName -ne $taskNewName.FullName) { throw 'Compiled assembly identity differs from the release player.' }
$taskBackup = Join-Path $taskBuild ('Assembly-CSharp-before-' + [DateTime]::UtcNow.Ticks + '.dll')
Copy-Item -LiteralPath $taskAssembly -Destination $taskBackup
Copy-Item -LiteralPath $taskOutput -Destination $taskAssembly -Force
Write-Host 'Player scripts compiled against the release libraries. Runtime checks are still required.'
