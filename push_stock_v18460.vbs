Dim oShell
Set oShell = CreateObject("WScript.Shell")

Dim gitExe
gitExe = "C:\Program Files\Git\cmd\git.exe"

Dim repoPath
repoPath = "E:\01.Github\my-stock-dashboard"

Dim proc, exitCode

Set proc = oShell.Exec("""" & gitExe & """ -C """ & repoPath & """ add -A")
Do While proc.Status = 0 : WScript.Sleep 200 : Loop
exitCode = proc.ExitCode
If exitCode <> 0 Then
    MsgBox "git add failed: " & proc.StdErr.ReadAll, 16, "Push Stock v18.460"
    WScript.Quit exitCode
End If

Set proc = oShell.Exec("""" & gitExe & """ -C """ & repoPath & """ commit -m ""v18.460: LOW audit fixes - CBC_RATE boundary 2.0->2.125, USDCNY thresholds 7.0/7.2/7.4->7.1/7.3/7.45, CNYES RSS dead->CNA finance; M4/M5 WONTFIX; Yahoo Finance RSS confirmed OK""")
Do While proc.Status = 0 : WScript.Sleep 200 : Loop
exitCode = proc.ExitCode
If exitCode <> 0 Then
    MsgBox "git commit failed (may already be committed): " & proc.StdErr.ReadAll, 48, "Push Stock v18.460"
End If

Set proc = oShell.Exec("""" & gitExe & """ -C """ & repoPath & """ push origin main")
Do While proc.Status = 0 : WScript.Sleep 200 : Loop
exitCode = proc.ExitCode
If exitCode <> 0 Then
    MsgBox "git push failed: " & proc.StdErr.ReadAll, 16, "Push Stock v18.460"
    WScript.Quit exitCode
End If

MsgBox "Stock v18.460 pushed successfully!", 64, "Push Stock v18.460"
WScript.Quit 0
