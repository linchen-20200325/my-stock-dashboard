Dim shell
Set shell = CreateObject("WScript.Shell")
Dim git
git = """C:\Program Files\Git\cmd\git.exe"" -C ""E:\01.Github\my-stock-dashboard"" "
shell.Run git & "add -A", 1, True
shell.Run git & "commit -m ""v18.464+v18.465: ETF 重構 + MK 3-3-3 原則評估""", 1, True
shell.Run git & "push origin main", 1, True
MsgBox "Done! Stock v18.464+v18.465 pushed.", vbInformation, "Git Push"
