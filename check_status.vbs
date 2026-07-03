Dim oShell, proc, gitExe, fso, f
Set oShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
gitExe = "C:\Program Files\Git\cmd\git.exe"

' Check stock repo git log
Set proc = oShell.Exec("""" & gitExe & """ -C ""E:\01.Github\my-stock-dashboard"" log --oneline -3")
Do While proc.Status = 0 : WScript.Sleep 200 : Loop
Dim stockLog : stockLog = proc.StdOut.ReadAll

' Check fund repo git log
Set proc = oShell.Exec("""" & gitExe & """ -C ""E:\01.Github\my-Fund-dashboard"" log --oneline -3")
Do While proc.Status = 0 : WScript.Sleep 200 : Loop
Dim fundLog : fundLog = proc.StdOut.ReadAll

MsgBox "=== STOCK (my-stock-dashboard) ===" & vbCrLf & stockLog & vbCrLf & "=== FUND (my-Fund-dashboard) ===" & vbCrLf & fundLog, 64, "Git Status Check"
