@echo off
REM 議事録アプリ起動スクリプト（高速起動版）
cd /d "%~dp0"

echo ====================================
echo    議事録アプリを起動しています...
echo ====================================
echo.

REM 仮想環境のPythonwを使用
if exist "venv\Scripts\pythonw.exe" (
    echo 仮想環境のPythonを使用します
    start "" "venv\Scripts\pythonw.exe" main.pyw
    timeout /t 1 /nobreak >nul
    exit
)

REM 仮想環境がない場合はシステムのPythonw
echo システムのPythonを使用します
start "" pythonw.exe main.pyw
timeout /t 1 /nobreak >nul
exit
