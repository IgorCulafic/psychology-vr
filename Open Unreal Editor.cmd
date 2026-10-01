@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\launch-unreal.ps1" -Mode Editor
if errorlevel 1 pause
