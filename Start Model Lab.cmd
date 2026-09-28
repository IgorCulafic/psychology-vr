@echo off
set "PSModulePath="
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\launch-model-lab.ps1"
if errorlevel 1 pause
