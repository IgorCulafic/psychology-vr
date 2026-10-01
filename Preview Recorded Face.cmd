@echo off
cd /d "%~dp0"
if not exist "unity\Builds\LiveLinkPreview\LiveLinkPreview.exe" (
  echo Build the recorded facial performance preview in Unity first.
  pause
  exit /b 1
)
start "" "unity\Builds\LiveLinkPreview\LiveLinkPreview.exe" --data "%~dp0docs\generated\livelink-poc" -screen-fullscreen 0 -screen-width 1280 -screen-height 820
