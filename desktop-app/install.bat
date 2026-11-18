@echo off
rem One-click installer for the CR-TEST desktop app (Windows).
rem Creates a private Python environment in .venv, installs the packages, runs the tests, then starts the app.
rem A copy of everything it prints goes to install_log.txt next to this file.
setlocal
cd /d "%~dp0"
set LOG=install_log.txt
echo CR-TEST installer %date% %time% > %LOG%

set PY=
rem PySide6 needs 64-bit Python: prefer the 64-bit one when several are installed
where py >nul 2>nul && ( py -3-64 --version >nul 2>nul && set "PY=py -3-64" )
if not defined PY ( where py >nul 2>nul && set "PY=py -3" )
if not defined PY ( where python >nul 2>nul && set PY=python )
if not defined PY (
  echo Python was not found. Install Python 3.10 or newer from python.org ^(tick "Add python.exe to PATH"^), then run this again.
  echo ERROR: python not found >> %LOG%
  pause
  exit /b 1
)
echo [1/5] Python:
%PY% --version >> %LOG% 2>&1
%PY% --version

if not exist ".venv\Scripts\python.exe" (
  echo [2/5] Creating the app's Python environment in .venv ...
  %PY% -m venv .venv >> %LOG% 2>&1 || goto :fail
) else (
  echo [2/5] Python environment already exists.
)

echo [3/5] Installing PySide6, pyserial, pyqtgraph, numpy ^(first time: a few minutes^) ...
".venv\Scripts\python.exe" -m pip install --upgrade pip >> %LOG% 2>&1
".venv\Scripts\python.exe" -m pip install -r requirements.txt >> %LOG% 2>&1 || goto :fail

echo [4/5] Running the self-tests ...
".venv\Scripts\python.exe" -m unittest discover tests >> %LOG% 2>&1 || goto :fail
echo       tests passed

echo [5/5] Starting the app ...
echo INSTALL OK >> %LOG%
start "" /b ".venv\Scripts\pythonw.exe" -m crkit_app 2> app_error_log.txt
exit /b 0

:fail
echo.
echo Something went wrong. Details are in %CD%\%LOG%
echo INSTALL FAILED >> %LOG%
pause
exit /b 1
