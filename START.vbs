Set ws  = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
Dim dir : dir = fso.GetParentFolderName(WScript.ScriptFullName)

' Kill any old instance on port 7860 silently
ws.Run "cmd /c for /f ""tokens=5"" %a in ('netstat -aon ^| find "":7860""') do taskkill /f /pid %a", 0, True

' Start backend silently — window style 0 = completely hidden
ws.Run "cmd /c cd /d """ & dir & """ && python backend\app.py", 0, False

' Wait for server to start, then open browser
WScript.Sleep 3500
ws.Run "http://localhost:7860"
