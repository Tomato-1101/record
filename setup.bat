@echo off
setlocal enabledelayedexpansion
chcp 65001 > nul
title 議事録アプリ - セットアップ & 起動

cd /d %~dp0

echo ========================================
echo   議事録アプリ - 起動スクリプト
echo ========================================
echo.

REM Pythonの検出とインストール
set PYTHON_CMD=python

python --version > nul 2>&1
if %errorlevel% neq 0 (
    REM pythonコマンドが見つからない場合、pyランチャーを確認
    py --version > nul 2>&1
    if !errorlevel! equ 0 (
        set PYTHON_CMD=py
        echo [情報] Pythonランチャー(py.exe)を使用します。
    ) else (
        REM Pythonが見つからない場合
        cls
        echo ========================================================
        echo  [重要] Pythonが見つかりません
        echo ========================================================
        echo.
        echo  このアプリを実行するには Python が必要です。
        echo.
        echo  1. 自動インストールを試みる (Winget使用)
        echo  2. 手動でダウンロードページを開く
        echo  3. 終了
        echo.
        
        choice /c 123 /m "選択してください"
        if !errorlevel! equ 3 exit /b 1
        if !errorlevel! equ 2 (
            start https://www.python.org/downloads/
            pause
            exit /b 1
        )
        if !errorlevel! equ 1 (
            echo.
            echo [1/2] Wingetを確認中...
            winget --version > nul 2>&1
            if !errorlevel! neq 0 (
                echo [エラー] Wingetが見つかりません。手動インストールを選択してください。
                pause
                exit /b 1
            )
            
            echo [2/2] Python 3.12をインストール中...
            echo ※ 管理者権限の確認が表示される場合があります。「はい」を選択してください。
            winget install -e --id Python.Python.3.12 --scope machine
            
            if !errorlevel! neq 0 (
                echo.
                echo [エラー] インストールに失敗しました。
                pause
                exit /b 1
            )
            
            echo.
            echo ========================================================
            echo  [成功] Pythonのインストールが完了しました
            echo ========================================================
            echo.
            echo  環境変数を反映させるため、このウィンドウを閉じて
            echo  もう一度 setup.bat を実行してください。
            echo.
            pause
            exit /b 0
        )
    )
)

REM 仮想環境の作成（存在しない場合）
if not exist venv (
    echo [1/3] 仮想環境を作成中...
    %PYTHON_CMD% -m venv venv
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
