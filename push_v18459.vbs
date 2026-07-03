Dim oShell, oFSO, oFile, oExec
Set oShell = CreateObject("WScript.Shell")
Set oFSO = CreateObject("Scripting.FileSystemObject")
Dim logPath: logPath = "E:\01.Github\my-stock-dashboard\push_v18459.log"
Set oFile = oFSO.CreateTextFile(logPath, True)
Dim gitPath: gitPath = "C:\Program Files\Git\cmd\git.exe"
oShell.CurrentDirectory = "E:\01.Github\my-stock-dashboard"

oFile.WriteLine "=== " & Now() & " ==="

' git status
Set oExec = oShell.Exec("""" & gitPath & """ status --short")
oFile.WriteLine "STATUS:" & vbCrLf & oExec.StdOut.ReadAll() & oExec.StdErr.ReadAll()

' git add all
Set oExec = oShell.Exec("""" & gitPath & """ add -A")
oFile.WriteLine "ADD: " & oExec.StdOut.ReadAll() & oExec.StdErr.ReadAll()

' Commit
Dim commitMsg
commitMsg = "v18.459: audit fixes - VIX dual-green bug, Bloomberg RSS removed, CHN_PMI->CHN_BCI label"
Set oExec = oShell.Exec("""" & gitPath & """ commit -m """ & commitMsg & """")
oFile.WriteLine "COMMIT:" & vbCrLf & oExec.StdOut.ReadAll() & oExec.StdErr.ReadAll()

' Push
Set oExec = oShell.Exec("""" & gitPath & """ push origin main")
oFile.WriteLine "PUSH:" & vbCrLf & oExec.StdOut.ReadAll() & oExec.StdErr.ReadAll()

oFile.WriteLine "=== Done " & Now() & " ==="
oFile.Close
MsgBox "Stock push done! Check push_v18459.log", 64, "Git Push Done"
