Set objShell = CreateObject("WScript.Shell")
Set objFSO = CreateObject("Scripting.FileSystemObject")

' Get script directory
strScriptPath = objFSO.GetParentFolderName(WScript.ScriptFullName)

' Change current directory
objShell.CurrentDirectory = strScriptPath

' Check if virtual environment exists
strVenvPython = strScriptPath & "\venv\Scripts\pythonw.exe"
strMainPy = strScriptPath & "\src\main.py"

If objFSO.FileExists(strVenvPython) Then
    ' Use virtual environment Python
    strCommand = """" & strVenvPython & """ """ & strMainPy & """"
    ' 0 = No window, False = Don't wait for completion
    objShell.Run strCommand, 0, False
Else
    ' Show error message
    MsgBox "Virtual environment not found!" & vbCrLf & "Please run setup.bat first.", vbExclamation, "Error"
End If
