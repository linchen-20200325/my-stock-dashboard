Dim shell
Set shell = CreateObject("WScript.Shell")
Dim gitS
gitS = """C:\Program Files\Git\cmd\git.exe"" -C ""E:\01.Github\my-stock-dashboard"" "
shell.Run gitS & "add -A", 1, True
shell.Run gitS & "commit -m ""v18.463: UI 重構 — 10 Tab → 4 群組 + 選股網整合 + AI 置頂卡""", 1, True
shell.Run gitS & "push origin main", 1, True
MsgBox "Done! Stock v18.463 pushed.", vbInformation, "Git Push"
