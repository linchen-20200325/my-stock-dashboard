> **歷史／適用性引言（2026-11-07 抽出）**：本檔自 Draft PR #1030（head 1e5afee1） 原內容抽出保存（來源分支 `docs/newui2-data-page-trend-onebrain-pdf-20261106`），抽出日期 2026-11-07。
> 此為歷史草案／研究材料，**不是現行施工依據**；現行方向以 DEC-142／DEC-146 與 `NEWUI2_TOP_FIVE_APPROVED_VISUAL_AND_SAFETY_GATE_2026-11-07.md` 為準。

# New UI2｜以第一版有效能力重整五頁藍圖（2026-11-06）
> 客戶本輪要求「重新規劃，如果建議保留的部分是……」，句尾未完整，但上下文是要求把前一輪 Old UI reuse audit 的推薦項納入 New UI2。此文為**保守暫定設計提案**，待使用者進一步修正；不得把未說完的話推定為額外授權。Main basis `343f0e0e`、本 PR #1030 最新 Legacy Reuse Audit；開工前重驗 GitHub。Docs-only，不動 production/RuleIDs/Schema/舊 UI。
## 1. 最小三路線
|方案|速度與 Token|風險|裁定|
|---|---|---|---|
| A 整搬舊 UI/Prompt|初期快，但冗長|舊式過度行動、缺資料誤判|不採|
| B 全部重寫|最慢且昂貴|公式漂移、資料/AI 耦合|不採|
| C **重用 L0/L1/L2 確定性核心＋headless Evidence＋極簡 UI2 projection**|較快、可逐項驗|需要 lineage audit|推薦|
## 2. 五頁一覽
|頁|L1 畫面|完整 AI evidence|不准誤搬|
|---|---|---|---|
|📊市場|市場位階與已核准 Risk Cap、台股/國際兩軸、前夜美股、外資籌碼、短/中/長研究摘要|16 指標、ADL、景氣/利率/匯率、外資/投信/融資/期貨、多市場共振與反證|舊 SOX×DXY 的「重壓／減碼」語句、未核准台股/國際趨勢結論|
|🎯標的|市場精選/查一檔雙模式、公司財務安全、獲利品質、營收趨勢、估值、籌碼、產業機會|FH_* 體檢項、歷史現金流、月營收×季報（legacy 65/35）、改善/惡化、集保散戶人數/大戶比例、價值/成長候選及所有反證|散戶人數≠散戶持股比例；財務完整度不足不得高評級；65/35 非新交易規則|
|💼持股|目前持有、單檔/產業直接曝險、集中度、OneBrain 持股摘要、必要警示|持股各公司財務/法人/重大事件、ETF 穿透證據、重疊與風險上限|ETF 成分資料不足時不得報出完整穿透集中度；不可另算 Risk Cap|
|👤我的|帳戶、Sheet、通知、設定、權限|設定/稽核資訊；不暴露 secrets|不複製資料健康牆/不產生交易指令|
|🗂資料|全站來源健康度／失敗／過期／未接線總表及可追溯細節|Capability/Data State 和 Evidence coverage diagnostics|網路刷新與寫入需另 Gate；不能缺值補零|
## 3. 財報精簡不丟證據
保留 `financial_health_engine` 確定性結果、`financial_health_thresholds`、`fin_trend_score`、`fin_health_diff`，UI 只呈現財務安全、獲利、營運改善/惡化及重要風險。原始明細、N/A/期限/錯誤及反證必保存在 approved canonical/Evidence，OneBrain 與總結可按 scope 讀取。Old AI prompt 不能作唯一計算真相。
## 4. OneBrain 總架構
四個主要 page-specific AI 入口 + 一個 global reviewer（👤我的優先 deterministic 輔助）。相同 headless Complete Evidence Ledger，required manifest/內部只讀索引、分批 evidence pack、可檢驗 coverage、負面證據強制保留、快取版本和日期驗證。**AI 不自行抓外部數據**。各 AI 都輸出白話：目前怎麼了／為何重要／支持與反證／有何不知道／接下來觀察什麼。只輸出短、中、長，而非固定 3/6/9 月。正式單一行動權威及 Risk Cap 不由模型取代。
## 5. 第一版能力三種承接等級
A **優先重用既有算好的來源**：財報 FH/跨期、三大法人、已存在國際序列、Risk Cap/Regime、missing/freshness；
B **整理後再接**：集保籌碼、產業熱力與資金流、跨季選股及 forward test、ETF 成分穿透、歷史新聞/事件；
C **研究候選不得啟用**：大盤 EPS×PE（缺正式 index forward EPS）、缺貨/大訂單的未核實敘事、正式短中長預測公式、舊 UI 自行下單與武斷多空文案。
## 6. 施工順序及停手
1. 綜合 #1022/#1027/#1029/#1030 的視覺提案、五頁導航與資料頁，把時效與資料問題先設計為正確 disabled/unknown 狀態；取得客戶視覺核准。
2. Claude Code 分 1~3 項安全批次完成 approved presentation-only，保持 390/1440/a11y 和現有 W-11 手機順序；避免衝突 Work A 所有正在改動的資料契約。
3. 獨立 lineage/Gate 稽核 producer→canonical→Domain→Digest→LLM→Page；按 A/B/C 層級逐個接線。未過 High Gate 不改 AI runtime/LLM tools/訊號門檻/新來源。
4. 獨立 QA／CI／合併後同步正式治理文件，不能把此暫定設計文件視為已經 merge 或 production 已實作。

## 7. 2026-11-06 最新 OneBrain 架構（取代舊「每頁一個獨立 AI」與泛泛總結文字）
- 使用者提供基金專案的**架構參考**：唯一 Canonical Data → 可追溯 Evidence Registry 與確定性 Domain 計算 → UI ViewModel 與 Decision Digest **雙投影** → **同一 OneBrain 協調六個領域分析單元** → 全域整合/反證檢查 → 所有使用者可見的白話文分析。**只借架構，不搬基金 NAV、配息、同類基金、換檔等專用公式或資料**。
- 台股六個領域分析單元：①市場趨勢（台股/國際/景氣）；②籌碼資金（外資/投信/融資/集保）；③財報品質（EPS/營收/OCF/FCF/財務體檢）；④產業前景（AI/CSP/訂單/產業供需，僅 approved research context）；⑤持股風險（直接/ETF 穿透/集中度/公司事件）；⑥資料稽核（完整性/新鮮度/缺失/矛盾）。這是**任務分域**，不是六個不連動 AI，也不是強制每次跑六次 LLM。
- 四個主要分析分頁可有自己的 scoped OneBrain 入口；👤我的優先登入/設定/稽核；另設全域總結 OneBrain 交叉比對領域報告並回查 evidence IDs、正反證、資料日期和 coverage manifest；總結不能只對 AI 文字做二次潤稿。
- 所有 OneBrain 報告均用**白話文**：一句話現況→短/中/長→支持與反證→無法確認之處→下一步追蹤；歷史研判和預測不得冒充已發生事實。**短/中/長不等於固定 3/6/9 個月**。
- 只有已核准 adapters 取得外部資料，OneBrain 本體**無任意網路搜尋、新 API、資料寫入權限**。完整 headless evidence 不從 UI 卡片/Top-N 萃取；token 限制以分批、內部只讀回查、manifest + deterministic coverage gate 解決，不能 silent truncation。
- 舊規則衝突：main 的四頁上限、👤我的內建完整資料健康度、桌機左 rail、手機抽屜 JS_V4 的**呈現布局**，將由使用者最近核准的五頁＋頂部導航/Sheet/右上帳號取代。真正刪除程式/JS_V4/guard 或改 auth，必須另行完成正式 DEC/Active Contract/路由/瀏覽器 QA；**歷史決策原文與安全守衛不得直接刪除**。
- 新 UI2 **Dark-only**；基金截圖僅供導覽與 OneBrain 佈局參考，禁止將基金領域決策搬到股票專案。
