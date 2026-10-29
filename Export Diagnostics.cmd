@echo off
set "PSModulePath="
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\export-diagnostics.ps1"
set "result=%ERRORLEVEL%"
pause
exit /b %result%
