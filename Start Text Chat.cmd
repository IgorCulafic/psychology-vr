@echo off
set "PSModulePath="
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\run-portable.ps1" -Mode Text
set "result=%ERRORLEVEL%"
if not "%result%"=="0" pause
exit /b %result%
