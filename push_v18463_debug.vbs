Dim shell
Set shell = CreateObject("WScript.Shell")
Dim gitDir
gitDir = "E:\01.Github\my-stock-dashboard"
Dim git
git = """C:\Program Files\Git\cmd\git.exe"""

' Run all git commands in ONE cmd window that stays open
Dim cmd
cmd = "cmd.exe /k """ & git & " -C """ & gitDir & """ status && " & _
              git & " -C """ & gitDir & """ add -A && " & _
              git & " -C """ & gitDir & """ commit -m ""v18.463: UI re layout - 10 Tab to 4 groups + screener unification + AI top card"" && " & _
              git & " -C """ & gitDir & """ push origin main && echo DONE"""

shell.Run cmd, 1, False
