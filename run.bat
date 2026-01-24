@echo off
chcp 65001 > nul
title 議事録文字起こしアプリ

echo ========================================
echo   議事録文字起こしアプリ
echo ========================================
echo.

REM 仮想環境をアクティベート
call "%~dp0venv\Scripts\activate.bat"

REM アプリを実行
python "%~dp0src\main.py"

REM エラーがあった場合は一時停止
if %errorlevel% neq 0 (
    echo.
    echo エラーが発生しました。
    pause
)
