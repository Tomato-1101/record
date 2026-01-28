Set objShell = CreateObject("WScript.Shell")
Set objFSO = CreateObject("Scripting.FileSystemObject")

' スクリプトのディレクトリを取得
strScriptPath = objFSO.GetParentFolderName(WScript.ScriptFullName)

' Pythonwでアプリを起動（ウィンドウなし）
strCommand = "pythonw.exe """ & strScriptPath & "\main.pyw"""

' 0 = ウィンドウを表示しない, False = 処理の完了を待たない
objShell.Run strCommand, 0, False
