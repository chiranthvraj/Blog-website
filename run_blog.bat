@echo off
setlocal
cd /d "%~dp0"

set "PYTHON="
if exist "%~dp0.venv\Scripts\python.exe" set "PYTHON=%~dp0.venv\Scripts\python.exe"

if not defined PYTHON (
    where py >nul 2>nul
    if errorlevel 1 (
        echo Python was not found. Install Python 3.10 or newer, then try again.
        pause
        exit /b 1
    )
    echo Creating a project virtual environment...
    py -3 -m venv "%~dp0.venv"
    if errorlevel 1 goto :error
    set "PYTHON=%~dp0.venv\Scripts\python.exe"
)

"%PYTHON%" -c "import flask, pymongo" >nul 2>nul
if errorlevel 1 (
    echo Installing project dependencies into the selected environment...
    "%PYTHON%" -m pip install -r "%~dp0requirements.txt"
    if errorlevel 1 goto :error
)

echo.
echo Starting Little Stories at http://127.0.0.1:5000
echo Leave this window open while you use the site. Press Ctrl+C to stop.
echo If you see an address-in-use error, close the other Flask terminal first.
echo.
start "" http://127.0.0.1:5000
"%PYTHON%" "%~dp0app.py"
if errorlevel 1 goto :error
exit /b 0

:error
echo.
echo The blog could not start. Read the error above, then check MongoDB and Python.
pause
exit /b 1
