Dim shell
Set shell = CreateObject("WScript.Shell")
Dim git
git = """C:\Program Files\Git\cmd\git.exe"" -C ""E:\01.Github\my-stock-dashboard"" "

shell.Run git & "add -A", 1, True
shell.Run git & "commit -m ""v18.461: TW timezone fix for sidebar date display""", 1, True
shell.Run git & "push origin main", 1, True

MsgBox "Stock v18.461 push done!", vbInformation, "Git Push"
