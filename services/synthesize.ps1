param([Parameter(Mandatory=$true)][string]$TextPath, [Parameter(Mandatory=$true)][string]$OutputPath)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$speaker = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
    $speaker.Rate = -1
    $speaker.SetOutputToWaveFile($OutputPath)
    $speaker.Speak([System.IO.File]::ReadAllText($TextPath))
} finally { $speaker.Dispose() }
