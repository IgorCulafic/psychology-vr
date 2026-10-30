@echo off
set "PSModulePath="
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\run-portable.ps1" -Mode Check
if errorlevel 1 goto end
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\benchmark-response.ps1"
:end
set "result=%ERRORLEVEL%"
pause
exit /b %result%
