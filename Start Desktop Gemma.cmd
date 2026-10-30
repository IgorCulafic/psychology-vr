@echo off
set "PSModulePath="
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\launch.ps1" -Desktop -Config "services/.runtime/config-desktopgemma.json" -GamePath "%~dp0..\PsychologyVR\unity\Builds\Windows\AlexPrototype.exe"
set "result=%ERRORLEVEL%"
if not "%result%"=="0" pause
exit /b %result%
