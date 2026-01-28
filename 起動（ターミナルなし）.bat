@echo off
REM 議事録アプリ起動スクリプト（ターミナルなし）
cd /d "%~dp0"

REM Pythonパスを検出
where pythonw >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo エラー: pythonw.exe が見つかりません
    echo Python がインストールされていることを確認してください
    pause
    exit /b 1
)

REM アプリをターミナルなしで起動
start "" pythonw main.pyw

REM このバッチファイルは即座に終了します
exit
