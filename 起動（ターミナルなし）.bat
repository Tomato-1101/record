@echo off
REM 議事録アプリ起動スクリプト（ターミナルなし）
cd /d "%~dp0"

REM 仮想環境のPythonwを使用
if exist "venv\Scripts\pythonw.exe" (
    start "" "venv\Scripts\pythonw.exe" main.pyw
) else (
    start "" pythonw.exe main.pyw
)

REM このバッチファイルは即座に終了します
exit
