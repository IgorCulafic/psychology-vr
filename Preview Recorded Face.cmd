@echo off
cd /d "%~dp0"
if not exist "unity\Builds\LiveLinkPreview\LiveLinkPreview.exe" (
  echo Build the recorded facial performance preview in Unity first.
  pause
  exit /b 1
)
set "takeFolder=%~dp0docs\generated\livelink-poc"
if not "%~1"=="" set "takeFolder=%~1"
if not exist "%takeFolder%\performance.json" (
  echo No prepared recording was found.
  echo Drag a folder containing performance.json onto this launcher,
  echo or prepare your video as described in docs\RECORDED_FACE_POC.md.
  echo Personal recording data is not included in the release.
  pause
  exit /b 1
)
start "" "unity\Builds\LiveLinkPreview\LiveLinkPreview.exe" --data "%takeFolder%" -screen-fullscreen 0 -screen-width 1280 -screen-height 820
