> **歷史／適用性引言（2026-11-07 抽出）**：本檔自 Draft PR #1030（head 1e5afee1） 原內容抽出保存（來源分支 `docs/newui2-data-page-trend-onebrain-pdf-20261106`），抽出日期 2026-11-07。
> 此為歷史草案／研究材料，**不是現行施工依據**；現行方向以 DEC-142／DEC-146 與 `NEWUI2_TOP_FIVE_APPROVED_VISUAL_AND_SAFETY_GATE_2026-11-07.md` 為準。
> 補註：3／6／9 個月固定時域已被 `ONEBRAIN_EVIDENCE_COVERAGE_TOKEN_BUDGET_SHORT_MED_LONG_2026-11-06.md` 的短／中／長取代（DEC-142）；輸入隔離原則部分仍可參考。

# New UI2｜OneBrain 嚴格輸入隔離＋3／6／9 個月研究視窗（客戶方向，待正式 Gate）
> 使用者 2026-11-06 明確要求：PDF 研究精華融入市場／標的／持股功能，不單列老師專區；OneBrain 的**所有資料只能由本專案資料層提供**，AI 不得自主取得其他外部數據。此文件為需求落盤／docs-only，不修改既有正式投資規則與 AI runtime。以 main `343f0e0e` 與 #1030 的研究文件為基底；後續重查最新 GitHub。

## 1. 絕對禁止 AI 自行取數
- LLM/OneBrain execution environment 應採 **無外部資料網路訪問**、只讀且 scoped 的資料輸入（schema-validated Evidence／Decision Digest）；不得提供 browser/search/news/web fetch、Python 網路請求、行情 API、資料庫寫入或可回寫 canonical 的工具。
- 來源取得僅限經使用者和專案治理**已批准**的 adapter / fetcher，執行於 AI 之外；新聞、公告、產業訂單與財報也不例外。**來源尚未核准就不能先抓回來餵 AI**。歷史 PDF 是 research method/basis，不能冒充 current objective market facts。
- 資料層獨立完成取得→解析→標準化→有效性/時點/缺失/去重/脫敏→來源與 claim 可追溯→canonical/event facts。沒有可驗證的一手證據之報導只可標待核實。
- OneBrain 僅接受既有 Evidence / Digest（需保持 complete semantic coverage；UI Top-N 不限制 AI 的 approved evidence），可做解釋、對照、情境、反證、待驗清單；**不得補 missing、推導未授權交易公式、寫 Risk Cap 或 System Action、產出另一套正式動作權威**。
- 在 runtime Gate 驗收：實際對 OneBrain 注入假裝搜尋工具／URL 的測試，應驗證無外連權限；schema 嚴格拒絕外部資料混入；輸出引用必回查已輸入 evidence_id/source/as_of；缺值只能誠實降級。

## 2. PDF 研究精華融入對應分析（不獨立卡、不冠人名）
| 分析/頁面 | 從 PDF 的哪一種研究方法切入 | 使用限制 |
|---|---|---|
| 📊 市場籌碼／短期環境 | PDF p.39–43：外資現貨、融資、散戶 ETF 資金與市場修正 | 用已核准且足夠新鮮的當前欄位重新驗證；PDF 當時數字只能作歷史研究 |
| 📊 市場大盤情境與 6 個月觀察 | PDF p.42：EPS × PE 情境矩陣 | 缺大盤 EPS 正式資料源時僅顯示方法/研究槽，不可產生數值或結論 |
| 🎯 標的、💼 持股及 9 個月產業前瞻 | PDF p.29、32–38、44、54：CSP CAPEX、供應鏈、折舊、FCF、缺貨／訂單兌現 | 產業缺貨、大單需資料層提供正式證據；並檢查負面事件、取消單、庫存與產能過剩 |
| OneBrain | 同一份 research provenance + 所有經治理核准的現行 Evidence | PDF 只是對問題、情境與反證的研究框架，不是「PDF 宣稱即客觀真值」 |

## 3. 三個統一前瞻視窗（客戶本次提及 3／6／9 個月）
- **未來 3 個月**：外資／融資籌碼、夜間美股領先背景、新聞事件、月營收與近季風險。顯示正反證、時間和資料完整度。
- **未來 6 個月**：產業訂單是否兌現營收、EPS 修正、估值/利率/景氣；保留不同情境，不把 PE×EPS 未經驗證研究轉成正式價格目標。
- **未來 9 個月**：CAPEX 與供應鏈產能、技術世代、產品需求、獲利品質、FCF／折舊／競爭反證。
- 每視窗的欄位為視覺草稿：horizon／claim／supporting_evidence／counter_evidence／source+as_of／coverage／limitation／next_verification；**不宣稱已核准 3／6／9 預測模型**，不做保證勝率、不改正式 action。
- 短期數日～數週的風險監控**仍可獨立存在**，不得因提供 3 個月研究窗而漏掉隔夜風險；這是展示視窗，不是投資判斷的唯一期間。

## 4. 既有狀態與設計待辦
- 新 UI2 的 `🗂 資料` 頁繼續集中完整來源健康度；市場/標的/持股在相應判斷旁仍保留必要 source/as_of/缺值限制。
- 更新的獨立 HTML 預覽 v0.6 已改成 3／6／9 個月，PDF 精華內嵌研究視角，不獨立命名老師；**HTML 與程式不具實際 AI 執行權限**。
- 正式修改 OneBrain runtime 的輸入工具權限、來源白名單或 Digest schema 必須獨立 High Gate＋安全／回歸驗證，不能僅因此文件而開工。
