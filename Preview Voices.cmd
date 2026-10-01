@echo off
cd /d "%~dp0"
if not exist "voices\index.html" (
  echo The voice listening page is missing. Extract the complete release package.
  pause
  exit /b 1
)
start "" "%~dp0voices\index.html"
