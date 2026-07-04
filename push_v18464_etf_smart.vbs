Dim shell
Set shell = CreateObject("WScript.Shell")
Dim git
git = """C:\Program Files\Git\cmd\git.exe"" -C ""E:\01.Github\my-stock-dashboard"" "
shell.Run git & "add -A", 1, True
shell.Run git & "commit -m ""v18.464: ETF 重構 — 移除質借模擬 + 新增標準差買賣帶 + 三維分散度分析""", 1, True
shell.Run git & "push origin main", 1, True
MsgBox "Done! Stock v18.464 pushed.", vbInformation, "Git Push"
