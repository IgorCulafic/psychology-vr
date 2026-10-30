@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\test-rtx3080.ps1" %*
set "taskExit=%ERRORLEVEL%"
echo.
pause
exit /b %taskExit%
