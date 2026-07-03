Dim oShell, oFSO, oFile, oExec
Set oShell = CreateObject("WScript.Shell")
Set oFSO = CreateObject("Scripting.FileSystemObject")
Dim logPath: logPath = "E:\01.Github\my-stock-dashboard\git_stock_log.txt"
Set oFile = oFSO.CreateTextFile(logPath, True)
oFile.WriteLine "=== " & Now() & " ==="
Dim gitPath: gitPath = "C:\Program Files\Git\cmd\git.exe"
oShell.CurrentDirectory = "E:\01.Github\my-stock-dashboard"
Set oExec = oShell.Exec("""" & gitPath & """ status --short")
oFile.WriteLine "Status: " & oExec.StdOut.ReadAll() & oExec.StdErr.ReadAll()
Set oExec = oShell.Exec("""" & gitPath & """ add infra/oauth.py")
oFile.WriteLine "Add: " & oExec.StdOut.ReadAll() & oExec.StdErr.ReadAll()
Set oExec = oShell.Exec("""" & gitPath & """ commit -m ""fix(oauth): prompt=select_account consent to prevent auto-selecting wrong Google account (v19.293 port)""")
oFile.WriteLine "Commit: " & oExec.StdOut.ReadAll() & oExec.StdErr.ReadAll()
Set oExec = oShell.Exec("""" & gitPath & """ push origin main")
oFile.WriteLine "Push: " & oExec.StdOut.ReadAll() & oExec.StdErr.ReadAll()
oFile.WriteLine "=== Done ==="
oFile.Close
MsgBox "Done! Check git_stock_log.txt", 64, "Git"
