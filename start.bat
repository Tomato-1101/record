@echo off
cd /d "%~dp0"

echo Starting transcription app...
echo.

if exist "venv\Scripts\pythonw.exe" (
    echo Using virtual environment Python
    start "" "venv\Scripts\pythonw.exe" main.pyw
) else (
    echo Virtual environment not found, using system Python
    start "" pythonw.exe main.pyw
)

timeout /t 1 /nobreak >nul
exit
