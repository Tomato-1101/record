@echo off
chcp 65001 > nul
title 環境構築

echo ========================================
echo   環境構築スクリプト
echo ========================================
echo.

REM Python確認
python --version
if %errorlevel% neq 0 (
    echo Pythonがインストールされていません。
    echo https://www.python.org/downloads/ からインストールしてください。
    pause
    exit /b 1
)

echo.
echo [1/4] 仮想環境を作成中...
if not exist venv (
    python -m venv venv
    echo 仮想環境を作成しました。
) else (
    echo 仮想環境は既に存在します。
)

echo.
echo [2/4] 仮想環境をアクティベート中...
call "%~dp0venv\Scripts\activate.bat"

echo.
echo [3/4] pipを更新中...
python -m pip install --upgrade pip --quiet

echo.
echo [4/4] 依存パッケージをインストール中...
pip install -r requirements.txt --quiet

echo.
echo PyTorch (CPU版) をインストール中...
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu --quiet

echo.
echo ========================================
echo   環境構築が完了しました！
echo ========================================
echo.
echo 次のステップ:
echo   1. .env.example を .env にコピー
echo   2. .env にAPIキーを設定
echo   3. run.bat でアプリを起動
echo.
pause
