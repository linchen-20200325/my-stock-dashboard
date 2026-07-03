Dim oShell, oFSO, oFile, oExec
Set oShell = CreateObject("WScript.Shell")
Set oFSO = CreateObject("Scripting.FileSystemObject")
Dim logPath: logPath = "E:\01.Github\my-stock-dashboard\git_push_v18458_log.txt"
Set oFile = oFSO.CreateTextFile(logPath, True)
Dim gitPath: gitPath = "C:\Program Files\Git\cmd\git.exe"
oShell.CurrentDirectory = "E:\01.Github\my-stock-dashboard"

oFile.WriteLine "=== " & Now() & " ==="

' git status first
Set oExec = oShell.Exec("""" & gitPath & """ status --short")
oFile.WriteLine "STATUS:" & vbCrLf & oExec.StdOut.ReadAll() & oExec.StdErr.ReadAll()

' === v18.455/456/457/458: all staged together ===
' v18.455: ETF zh_name fix
Set oExec = oShell.Exec("""" & gitPath & """ add src/data/etf/etf_fetch.py")
oFile.WriteLine "add etf_fetch: " & oExec.StdOut.ReadAll() & oExec.StdErr.ReadAll()

' v18.456: MJ bootstrap + data_loader
Set oExec = oShell.Exec("""" & gitPath & """ add src/data/core/data_loader.py")
oFile.WriteLine "add data_loader: " & oExec.StdOut.ReadAll() & oExec.StdErr.ReadAll()
Set oExec = oShell.Exec("""" & gitPath & """ add src/compute/health/mj_trend_score.py")
oFile.WriteLine "add mj_trend: " & oExec.StdOut.ReadAll() & oExec.StdErr.ReadAll()

' v18.457: t2_inst + Reuters + dragon capex
Set oExec = oShell.Exec("""" & gitPath & """ add src/ui/tabs/tab_stock.py")
oFile.WriteLine "add tab_stock: " & oExec.StdOut.ReadAll() & oExec.StdErr.ReadAll()
Set oExec = oShell.Exec("""" & gitPath & """ add src/ui/tabs/stock_sections/section_dragon_alert.py")
oFile.WriteLine "add section_dragon: " & oExec.StdOut.ReadAll() & oExec.StdErr.ReadAll()
Set oExec = oShell.Exec("""" & gitPath & """ add src/data/news/news_fetcher.py")
oFile.WriteLine "add news_fetcher: " & oExec.StdOut.ReadAll() & oExec.StdErr.ReadAll()

' v18.458: financial_leading capex + stale Reuters strings
Set oExec = oShell.Exec("""" & gitPath & """ add src/ui/tabs/stock_sections/section_financial_leading.py")
oFile.WriteLine "add section_financial: " & oExec.StdOut.ReadAll() & oExec.StdErr.ReadAll()
Set oExec = oShell.Exec("""" & gitPath & """ add src/ui/tabs/tab_edu.py")
oFile.WriteLine "add tab_edu: " & oExec.StdOut.ReadAll() & oExec.StdErr.ReadAll()
Set oExec = oShell.Exec("""" & gitPath & """ add src/data/core/data_registry.py")
oFile.WriteLine "add data_registry: " & oExec.StdOut.ReadAll() & oExec.StdErr.ReadAll()

' STATE.md
Set oExec = oShell.Exec("""" & gitPath & """ add STATE.md")
oFile.WriteLine "add STATE.md: " & oExec.StdOut.ReadAll() & oExec.StdErr.ReadAll()

' Commit all v18.455-458 together
Dim commitMsg
commitMsg = "fix: ETF zh_name + MJ bootstrap + t2_inst + Reuters + dragon capex + financial_leading (v18.455-458)" & vbCrLf & vbCrLf & _
    "v18.455: fetch_etf_zh_name attempts=1->2 (proxy 403 fallback fix)" & vbCrLf & _
    "v18.456: MJ trend bootstrap from prev_period_data (Streamlit Cloud restart fix)" & vbCrLf & _
    "v18.457: t2_inst session key write + Reuters RSS removed + dragon alert uses CF capex" & vbCrLf & _
    "v18.458: section_financial_leading uses CF capex + stale Reuters description strings removed"

Set oExec = oShell.Exec("""" & gitPath & """ commit -m """ & commitMsg & """")
oFile.WriteLine "COMMIT:" & vbCrLf & oExec.StdOut.ReadAll() & oExec.StdErr.ReadAll()

' Push
Set oExec = oShell.Exec("""" & gitPath & """ push origin main")
oFile.WriteLine "PUSH:" & vbCrLf & oExec.StdOut.ReadAll() & oExec.StdErr.ReadAll()

oFile.WriteLine "=== Done " & Now() & " ==="
oFile.Close
MsgBox "Stock dashboard pushed! Check git_push_v18458_log.txt", 64, "Git Push Done"
