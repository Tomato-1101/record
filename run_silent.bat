@echo off
REM Run app without terminal window
cd /d "%~dp0"

REM Check if virtual environment exists
if exist "venv\Scripts\pythonw.exe" (
    start "" "venv\Scripts\pythonw.exe" "src\main.py"
) else (
    echo Virtual environment not found!
    echo Please run setup.bat first.
    pause
    exit /b 1
)

exit
