@echo off
set "PSModulePath="
cd /d "%~dp0"
if not exist ".tools\portable-env\Scripts\python.exe" (
  echo Run Setup.cmd first, then retry this source-art download.
  pause
  exit /b 1
)
".tools\portable-env\Scripts\python.exe" "tools\download-source-assets.py"
set "result=%ERRORLEVEL%"
pause
exit /b %result%
