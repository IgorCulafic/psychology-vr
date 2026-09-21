@echo off
set "PSModulePath="
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\run-portable.ps1" -Mode Setup
set "result=%ERRORLEVEL%"
pause
exit /b %result%
