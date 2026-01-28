@echo off
REM 議事録アプリ起動スクリプト（高速起動版）
cd /d "%~dp0"

REM ローディングメッセージを表示
echo ====================================
echo    議事録アプリを起動しています...
echo ====================================
echo.
echo アプリウィンドウが表示されるまでお待ちください。
echo （初回起動時は数秒かかる場合があります）
echo.

REM Pythonwで起動（ターミナルなし）
start "" pythonw.exe main.pyw

REM バッチファイルは即座に終了
timeout /t 2 /nobreak >nul
exit
