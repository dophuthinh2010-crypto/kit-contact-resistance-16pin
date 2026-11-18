@echo off
rem Starts the CR-TEST app with the virtual environment created during installation.
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo The app is not installed yet. See docs\INSTALL.md, step 3.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m crkit_app
if errorlevel 1 pause
