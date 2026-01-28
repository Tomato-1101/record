@echo off
cd /d "%~dp0"

echo ==========================================
echo   Transcription App - Debug Mode
echo ==========================================
echo.
echo Current directory: %CD%
echo.

if exist "venv\Scripts\python.exe" (
    echo [OK] Virtual environment found
    echo Path: venv\Scripts\python.exe
    set PYTHON_CMD=venv\Scripts\python.exe
) else (
    echo [WARNING] Virtual environment not found
    echo Using system Python
    set PYTHON_CMD=python.exe
)

echo.
echo Checking main.pyw...
if exist "main.pyw" (
    echo [OK] main.pyw found
) else (
    echo [ERROR] main.pyw not found
    pause
    exit /b 1
)

echo.
echo Starting app...
echo.

%PYTHON_CMD% main.pyw

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Failed to start app
    echo Error code: %ERRORLEVEL%
    echo.
    echo Check logs/app.log for details
    echo.
)

pause
