@echo off
set "PSModulePath="
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\optimization-settings.ps1"
set "result=%ERRORLEVEL%"
pause
exit /b %result%
