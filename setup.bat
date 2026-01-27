@echo off
chcp 65001 > nul
title 議事録アプリ - セットアップ & 起動

cd /d %~dp0

echo ========================================
echo   議事録アプリ - 起動スクリプト
echo ========================================
echo.

REM Python確認
python --version > nul 2>&1
if %errorlevel% neq 0 (
    echo [エラー] Pythonがインストールされていません。
    echo https://www.python.org/downloads/ からインストールしてください。
    pause
    exit /b 1
)

REM 仮想環境の作成（存在しない場合）
if not exist venv (
    echo [1/3] 仮想環境を作成中...
    python -m venv venv
)

REM 仮想環境のアクティベート
call venv\Scripts\activate.bat

REM 依存パッケージのインストール
echo [2/3] 環境を確認中...
pip install -r requirements.txt --quiet
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu --quiet --no-warn-script-location

REM .envファイルの確認と作成
if not exist .env (
    echo.
    echo [設定] .envファイルを作成しました。
    copy .env.example .env > nul
    echo.
    echo !!! 重要 !!!
    echo APIキーを設定する必要があります。
    echo 開かれたテキストファイルにAPIキーを入力して保存してください。
    echo その後、この画面に戻って何かキーを押すとアプリが起動します。
    echo.
    start notepad .env
    pause
)

echo.
echo [3/3] アプリケーションを起動中...
echo ========================================
echo.

python src/main.py

if %errorlevel% neq 0 (
    echo.
    echo [エラー] アプリケーションが終了しました（エラーコード: %errorlevel%）
    pause
)
