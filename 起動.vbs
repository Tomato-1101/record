Set objShell = CreateObject("WScript.Shell")
Set objFSO = CreateObject("Scripting.FileSystemObject")

' スクリプトのディレクトリを取得
strScriptPath = objFSO.GetParentFolderName(WScript.ScriptFullName)

' カレントディレクトリを変更
objShell.CurrentDirectory = strScriptPath

' 仮想環境のPythonwを優先
strVenvPython = strScriptPath & "\venv\Scripts\pythonw.exe"
strMainPyw = strScriptPath & "\main.pyw"

If objFSO.FileExists(strVenvPython) Then
    ' 仮想環境のPythonを使用
    strCommand = """" & strVenvPython & """ """ & strMainPyw & """"
Else
    ' システムのPythonwを使用
    strCommand = "pythonw.exe """ & strMainPyw & """"
End If

' 0 = ウィンドウを表示しない, False = 処理の完了を待たない
objShell.Run strCommand, 0, False
