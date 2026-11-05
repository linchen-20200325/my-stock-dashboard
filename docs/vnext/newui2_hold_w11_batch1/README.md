# 💼 持股 W-11 批 1（版面空槽）— 前後對照證據

- **基準（before）**：origin/main `1548cc5b2c12c4210cc402a3c72d7e85e56633b3`；**after**＝分支 `ui2/hold-w11-batch1` 工作樹（見 PR）。
- **授權**：DEC-141（客戶 2026-11-05 Q1~Q8）。**僅版面／欄位結構／空槽，不含任何資料接線。**
- **資料性質**：**全部為 FAKE scenario（`app_ui2.py` Preview；頁首 banner「示意資料（FAKE）」）**。圖中「FAKE 組合 · 12 檔」等為示意，不是持股或建議。
- **不宣稱 pixel parity**：參考原圖不在 repo；依據是 Wireframes §4.2／W-6／W-11 與草稿 `NEWUI2_HOLD_W11_REMAINING_DRAFT_2026-11-05.md` 的**文字**。
- **emoji 字型**：擷取環境（headless Chromium）emoji 字型可能不完整，🚀／⬜／💼 等在圖中可能呈現不同於真機；before／after 同環境。真機、Streamlit Cloud、iOS、Firefox／WebKit、Light 皆**未驗**。
- 擷取：`python -m tests.ui2_viewport.measure_viewport --out <dir> --shots all`（Streamlit 1.59.2；Playwright 1.64.1）。

## 檔案（390×844＝mobile、1440×900＝desktop；場景 loaded、cold）

`before/`、`after/` 同檔名：`{mobile,desktop}_p4_hold_{loaded,cold}.png`。

## 變更

1. 組合狀態行（標題下）：`組合：<既有欄位> · 資料日 ⬜ 資料日未提供 · 判得出 ⬜ 尚未提供`（Q4：未授權組合層日期，不冒充）。
2. 今日需處理：原「是否需要行動／下一步」兩列→單行，內容仍 `⬜ 尚未提供（待系統動作整合）`（VM 欄位全保留）。
3. 建議持股水位（市場端）空槽、Primary「產業曝險／集中度」空槽（桌機 ≥240px；手機一行）。
4. 持股表：桌機八欄表頭、手機四欄＋每列展開提示、原因句；無資料列。
