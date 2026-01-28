@echo off
REM 議事録アプリ起動スクリプト（デバッグ用・エラー表示）
cd /d "%~dp0"

echo ====================================
echo    議事録アプリ デバッグ起動
echo ====================================
echo.
echo カレントディレクトリ: %CD%
echo.

REM 仮想環境の確認
if exist "venv\Scripts\pythonw.exe" (
    echo [OK] 仮想環境が見つかりました
    echo パス: venv\Scripts\pythonw.exe
    set PYTHON_CMD=venv\Scripts\python.exe
) else (
    echo [警告] 仮想環境が見つかりません
    echo システムのPythonを使用します
    set PYTHON_CMD=python.exe
)

echo.
echo main.pywの確認...
if exist "main.pyw" (
    echo [OK] main.pywが見つかりました
) else (
    echo [エラー] main.pywが見つかりません
    pause
    exit /b 1
)

echo.
echo アプリを起動します...
echo.

REM Pythonでエラーを表示
%PYTHON_CMD% main.pyw

REM エラーが発生した場合
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [エラー] アプリの起動に失敗しました
    echo エラーコード: %ERRORLEVEL%
    echo.
)

pause
