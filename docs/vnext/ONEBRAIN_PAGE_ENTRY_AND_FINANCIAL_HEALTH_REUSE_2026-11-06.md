# New UI2｜每頁 OneBrain 入口＋共用證據大腦＋財報體檢 L1 精簡 v0.1

> 2026-11-06 客戶要求：重用第一版「MJ 財報課程」導入的財報體檢架構，**不以老師姓名命名 UI**；簡化使用者畫面，把已核准完整指標及跨期證據交給 OneBrain；每頁可以設專屬 AI 入口防止跨頁 Token 遺漏。**PROPOSED、docs-only；不授權 AI runtime/資料/schema/計算/導航變更。** base main `343f0e0e`，需在施工前重驗。
>
> 對於外部課程真實教綱，**本文件僅證明 repository 第一版已實作的分析架構**，不宣稱已查證課程官網或老師全部教學。

## 1. repo 已有的財報方法（僅列可從程式查證部分）

- `src/services/financial_health_engine.py`：存活能力、經營、獲利、財務結構、償債、綜合診斷等既有模組；`shared/financial_health_thresholds.py` 為 FH_* 正式門檻 SSOT。歷史 MJ_* 只是 backward-compat alias，不建立第二套規則。
- `src/compute/health/fin_trend_score.py`：**月營收 65%＋季財報 35%** 的既有融合分數（這是現有引擎的歷史公式，**不是本次新核准 UI2 投資模型**）；`fin_health_diff.py` 對兩期逐指標改善／惡化及本業盈轉虧/虧轉盈產生 verdict。保留精確 source + timeframe + rule version。
- `src/ui/tabs/stock_grp_sections/section_financial_health.py`：第一版有現金／OCF／負債、經營 DSO/DIO/DPO、毛利／營業利益／淨利／ROE 多表、多個 expander、5 年現金流。**UI2 不複製舊資料牆，但也不能漏掉可追溯證據或違反既有規則**。
- 缺值絕不能被 0、Pass、紅旗不存在或低風險替代；已有測試防止只算出少數指標卻評成高等級。金融業與非金融業門檻可能不同，需使用正式 producer 的領域分類，不把某產業特殊比率直接當通用安全線。

## 2. 🎯 個股查詢 UI 的 L1 簡化（提案）

```text
個股標頭：名稱／代碼／市場與資料日期
[財務安全（真狀態或無法判定）] [獲利品質] [營運動能]
[主要財務風險 1~2 項（無數據則缺值）]
[近期改善／惡化（依既有確定性引擎）] [查看完整分析：OneBrain]
主要價格圖＋SPEC；必要時精簡基本面、估值、籌碼卡（按已核准排序）
```

- 不在一般 UI 重建 5 模組×多表×長 expander、技術 RuleIDs、原始資料；保留使用者任務必要的詳細功能入口，但不把 AI 當成唯一證據倉庫。
- AI read path：既有財務原始指標、現金流、財報跨期差異、規則結果、未評項、負面證據與源時間戳 → headless Complete Evidence/Digest；**欄位是否真的已通達 Digest 必須做 evidence-by-evidence audit，不能因舊 UI 有就宣稱 OneBrain 已看到**。
- 財報評等仍由確定性規則出，AI 只能做對照解釋、追蹤財務惡化及反證；不能偷偷替換 SSOT 門檻、輸出新正式建議，或將 AI 的文字評語當 objective fact。

## 3. 三方案（Token × 正確性 × 速度）

| 方案 | 原理 | 缺陷/效益 | 結論 |
|---|---|---|---|
| A 每頁一套完全獨立 AI＋獨立資料輸入 | 每頁自做 prompts / 新聞讀取 / 財務來源 | 重複資料、費 Token、跨頁衝突與多套 Action Authority | 不採 |
| B 全站共用一個一次性超長 prompt | 一次裝全部 evidence | 超 context、lost-in-the-middle、低價值資料擠掉反證 | 不採 |
| **C 共用 Evidence Ledger + per-page scoped analysis + on-demand global synthesis** | 5 頁各有獨立提問入口，視需要讀取自己域的資料包；Global 用同一份 ledger 補足其他關鍵域 | Token 可控，保持獨立責任與全域結論 | **推薦（設計）** |

## 4. 每頁入口職責（只做入口設計，不承諾每次都呼叫 LLM）
| 頁 | 可見入口 | 最小 domain pack | 跨域必要情境 |
|---|---|---|---|
| 📊 市場 | 「🤖 分析市場」 | 台股與國際序列、前夜美股、法人籌碼、宏觀研究 | 遇重要持股／產業風險可檢索完整已核准證據 |
| 🎯 標的 | 「🤖 深度研究此檔」 | 財務體檢、營收、EPS、估值、籌碼、已核准新聞／訂單 | 需同步讀大盤及該產業，不能用局部價格圖代替 |
| 💼 持股 | 「🤖 分析持股風險」 | Portfolio + ETF 穿透可得度、持股財報及負面事件 | 需全市場風險 Context 與公司來源 |
| 👤 我的 | 「🤖 說明設定／稽核」候選 | 已核准設定、決策證據與覆蓋報告 | 不展示憑證、不可執行登入與寫入 |
| 🗂 資料 | 「🤖 解釋資料缺口」候選 | capability、data state、freshness、失敗原因與 lineage | 不自行 retry/fetch/new API；診斷非投資動作 |

- 預設**用於使用者當頁上下文**，而不是 UI 所見的 Top N：依核准的內部 evidence ID 對全部 relevant facts 檢索。跨域需求由同一 planner 提出 typed 的 internal-only read。問題要求「全站短中長」、「持股對市場」時切到 global integration，並對 Required Evidence Matrix 作 deterministic coverage gate。
- 出於成本，必要時用純計算／模板而非 LLM（例如資料頁缺欄清單）、snapshot/content-hash + as_of cache 和 delta analysis。**不以「每頁 1 顆入口」代表必須每次開頁發 1 次昂貴推理**。
- OneBrain runtime 應禁止網際網路搜尋與所有未核准外部取數工具；所有 approved news/data 只能由 AI 外的資料層接入。無法取得就明確 partial/unavailable。

## 5. 有界 Token 與 Coverage Gate
- `RequiredEvidenceManifest`：按公司/頁/問題產生 expected fact IDs 與來源/時間/風險旗標/反證需求（確定性），不靠 AI 自評完整性。
- `PageEvidencePack`：先送最新正式判定摘要＋重要支持／反對證據＋所有 missing/stale flags 與完整 index；超額採 **typed chunks** 按需唯讀回查，不允許 silent truncation。
- `PageInsight`：schema 欄位 page_id、scope、evidence_refs、positive/negative、unresolved、source_as_of、analysis_status、limitation、model/token budget。缺證據時是 `PARTIAL`（設計語意，非新正式 enum），不宣稱完整。
- `GlobalSynthesis`：讀 PageInsight 的引用/版本、必需的 full ledger，再交叉檢核矛盾、重疊、同一消息多來源重複計數；一頁出錯不該當其他頁完全沒有風險。
- QA：因 UI 顯示少了財報細表而 Ledger loss=0；加入新負面財報後財報頁與全域摘要都有該 fact（或明確 partial）；token 擠爆不偷刪 evidence；cache as_of 過期會失效；跨頁結果同一套正式 Risk Cap/Action authority；external tools 不可見。

## 6. 下一個 Decision Gate 與施工分離
1. 視覺 Gate：先確定每頁 OneBrain 按鈕的實際位置、disabled/availability 顯示；不改 #1028 W-11 已核准手機順序及 #1019 drawer JS_V4。
2. 先做 **只讀財報數據血緣/完整性 coverage audit**（資料分層 Work A 與 Claude 可能同檔，須以 GitHub 最新 PR/diff 協調）；不先開新的人工財報公式。
3. **Runtime Security Gate（High）**：內部唯讀 Evidence reader、OneBrain API、source allowlist、無網路工具、完整性指標與快取權限；一律與視覺 PR 分離。
4. **投資領域 Gate（High）**：既有 65/35 公式是 legacy FACT，不代表准許新 UI 直接升為單一買賣結論。真正加入多域短／中／長合成時不得繞過正式 Risk Cap / System Action。
5. 任何正式新命名都保持中性：財報體檢、經營品質、跨期趨勢，不用老師姓名；內部 provenance 可保留原始來源。
