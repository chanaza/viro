Dim installDir
installDir = Left(WScript.ScriptFullName, InStrRev(WScript.ScriptFullName, "\") - 1)
Dim python
python = installDir & "\viro-env\Scripts\python.exe"
Dim script
script = installDir & "\run_app.py"
Dim cmd
cmd = Chr(34) & python & Chr(34) & " " & Chr(34) & script & Chr(34)
CreateObject("WScript.Shell").Run cmd, 0, False
