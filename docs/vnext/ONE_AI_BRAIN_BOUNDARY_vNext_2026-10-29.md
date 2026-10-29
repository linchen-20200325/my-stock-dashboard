# One AI Brain Boundary vNext（唯一 AI 大腦的邊界契約）

- **狀態**：正式／現行（Phase 1 凍結版；**本 phase 不改任何 AI 程式、prompt、persona、出口**）
- **日期**：2026-10-29　**基準**：PR base＝main `978ecedc`
- **決策來源**：One AI Brain, Many Data Views；Local AI Summary 來自同一 Brain＋同一 Digest 的 slice；AI 投資總結定位與「只回答六題／目標輸出格式／查看依據／禁止」；`build_ai_summary` 不得直接視為 One AI Brain、須盤點並決定 reuse／refactor／replace ＝ **客戶 2026-10-29（`docs/DECISIONS.md` DEC-109 十九～二十二，逐字）**；Brain 邊界細則、AI 出口判定、入口（R13）、驗收測試 ＝ **AI 總管內部決定（DEC-110）**。AI 投資總結新輸出格式（R12）＝客戶 DEC-109 二十一本身即新客戶裁示，取代 DEC-091(d)／A 規格 §5／`ai_summary.html` 舊五段的**呈現格式**。
- **上位**：`CLAUDE.md` > `PROCESS.md` > `PROJECT_RULES.md`（§13 D3／D4、§16.1 Data ≠ AI）＋`docs/governance/*` > 最新有效 DEC（DEC-027、DEC-054／055、DEC-091(d)、DEC-092、DEC-095、DEC-109／110）> **本檔**。
- **配套**：`docs/vnext/DECISION_DIGEST_CONTRACT_vNext_2026-10-29.md`（唯一輸入）、`docs/vnext/PRESENTATION_CONTRACT_vNext_2026-10-29.md` §13.3（入口版位）。
- ⚠️ **揭露（`CLAUDE.md` §-2 規則 6）**：AI 出口盤點為單組調查 Inv-4＋稽核組勘誤（已併入 §6）；「0 caller」為 grep、非窮舉；App ⑦ 與 LINE 分歧為 INFERENCE。

---

## §1 定位（客戶原文 DEC-109 十九）

**One AI Brain, Many Data Views**。不是：市場一套 AI、標的一套 AI、持股一套 AI、最後再另一套 AI。各頁只提供：Data View、Rule Result、Local Explanation、scoped AI summary（需要時）。**Local AI Summary 必須來自同一 Brain＋同一 Decision Digest 的對應 slice**，避免跨頁 AI 結論互相矛盾。

## §2 邊界（DEC-110 內部）

1. **唯一輸入**＝一份 `DecisionDigest`（AB-0 v1／Phase 7 升 v2）。⛔ 其他輸入（session、UI 文字、widget 狀態、`macro_state.json` AI 欄位、AI 情緒、各頁自建 dict）。
2. **輸出必過 `shared/decision_digest_grounding.check_summary`**，只採用通過的句子（surviving）；驗不過 → **退回 `src/services/decision_digest_summary.build_rule_summary`**（規則式摘要，無 AI）。
3. **失敗不快取、失敗退避**（`CLAUDE.md` §1.A 第 3 點）；**只按鈕觸發**（付費）；⛔ 回寫資料、⛔ 自行取數、⛔ 使用工具。
4. **Digest 不受 UI 影響**：Top-N、expander 收展、頁面是否載入都不改變 Brain 的輸入（Presentation Contract §9、§10 R9）。

## §3 禁止清單（客戶 DEC-109 十七＋內部）

- ⛔ 掃 Streamlit 文字當 canonical data；⛔ 從顏色猜狀態；⛔ 從 widget 顯示文字推斷數據；⛔ 因 expander 收合就不讀某資料；⛔ 因 UI 沒顯示某指標就認定不存在；⛔ 從 UI Top-N 認為只有 Top-N 資料存在（客戶原文）。
- ⛔ 讀 `st.session_state`；⛔ 接受 `top_n`／`expanded` 等 UI 參數；⛔ 搬 `macro_state.json` 的 AI 文字欄位；⛔ AI 情緒當規則（`exit_signals.judge_news_sentiment`）；⛔ 各頁自建 prompt；⛔ 使用 `src/config/persona.TAIWAN_ADVISOR_PERSONA`（「給出明確的動作」與 DEC-054 第 6 點衝突，`CV1-FU-06`）。
- ⛔ 創造：行動、四態、產業或趨勢結論、confidence、數字、門檻、公式、股票、產業趨勢、策略分類（DEC-027、DEC-091 §三、DEC-092 Q1）。
- ⛔ 把 Risk Cap 連到具體行動（屬新規則 HI-1／HI-4）；RC-VISIBILITY 核准前只能答 Risk Cap **狀態**與客戶核准措辭（DEC-081 Q2-2）。

## §4 Slice 規則（Local Summary ⊂ 全文）

一份 Digest → 一份 SummaryResult；各頁 Local Summary＝**同一結果依段 key 過濾的子集**，⛔ 另組 prompt、⛔ 另呼叫 AI。

| 頁 | 收合態 slice（R13 入口卡） |
|---|---|
| 📊 市場 | 市場一句＋主要風險（＋Risk Cap 狀態句） |
| 🎯 標的 | 標的機會一句（產業／候選；未定義者固定「⬜ 尚未定義」） |
| 💼 持股 | 持股一句＋本期行動 |
| 👤 我的 | 不放（非分析頁） |
| 展開面板 | 全文（§5 全部項目） |

驗收：Local Summary 每句 ⊂ 全文 lines（逐字）。

## §5 AI 投資總結新輸出格式（R12；客戶 DEC-109 二十一逐字）

**只回答**：1 現在整體環境如何？2 最大的 1～3 個變化是什麼？3 我的持股是否需要動？4 是否有新的值得看的機會？5 Risk Cap 是否限制行動？6 哪些地方因 Missing 無法判斷？

**目標輸出**：

| 項 | 量 | 每項附 |
|---|---|---|
| 市場 | 一句 | `查看依據` |
| 持股 | 一句 | `查看依據` |
| 標的機會 | 一句 | `查看依據` |
| 主要風險 | 1～3 點 | `查看依據` |
| 本期行動 | 最多 3 項 | `查看依據` |

`查看依據` 回到：Decision Digest、canonical evidence、rule result（只從 Digest／`evidence_refs` 渲染）。

**禁止（客戶原文）**：把所有市場圖重畫一次；把持股表再複製一次；重複候選表；長篇 AI essay；成為另一個 Report Wall。

**R12 讀法（DEC-110）**：
- 本格式即新客戶裁示（DEC-109），**取代**舊「固定五段（市場／產業／存股／資本利得／本期行動）」的**呈現格式**——出處＝DEC-091(d) 客戶原文、A 規格 `NEWUI_D25_A_FOUR_PAGE_SPEC_2026-10-27.md` §5、`d25_wireframes/ai_summary.html`，經 DEC-092 設計核准承接（DEC-092 本文無「五段」字樣）。
- **存股／資本利得／未分類的分類資料仍保留**（在 Digest 與查看依據裡）；持股一句可引用分類結果，⛔ AI 推論分類（DEC-091(e)、DEC-092 Q1）。
- 第 6 題（Missing）以每項的 Missing 誠實句＋查看依據回答，不另設段落（內部讀法）。
- **不另開客戶 Gate**：依 `PROJECT_RULES.md` §0.1「變更既有裁示需新的客戶 Decision」——客戶最新指示本身即新 DEC-109；DEC-013「已裁示事項不重問」。**Phase 7 實作前仍須依草稿先行出線框**（`CLAUDE.md` §-1.5.D v3 §03-2 ①）。
- 程式寫死五段（FACT）：`shared/decision_digest_terms.SECTION_KEYS`（固定順序）、`decision_digest_grounding.py` G5「五段齊全、唯一、固定順序」、`src/services/decision_digest_summary.py` 各段組裝 → Phase 7 內部改動，BACKLOG `P1R-AB2A-FIVE-SECTION-REWIRE`。
- 「最大 1～3 個變化」無正式變化量排序規則 → 內部先用 DEC-092 Q3 五桶規則＋既有方向值，沒有就 MISSING；若客戶要依變化幅度排序才需裁示。

## §6 AI 出口盤點與判定（FACT＋稽核勘誤；判定＝DEC-110）

| 出口 | 現況 | 判定 |
|---|---|---|
| `dividend_station_service.build_ai_summary`（約 L1599）＋`build_summary_prompt`（約 L1487） | 輸入＝`build_station_digest` dict（L3 結構化）＋`build_switch_advice`；**不只持股**：還帶 VIX、觀察清單 235 燈、資料不足項、換入候選；**不提總經位階／成數**；無 as_of；missing 靠 prompt 句；無 grounding；prompt 帶加碼金（HI-2）與核心／衛星近似分類 | **partial／legacy building block**：保留 `build_station_digest` 當結構化來源（reuse）；prompt 與出口 **replace**。⛔ 宣稱 One AI Brain 已完成 |
| 呼叫者：`page_hold` ⑦ AI 戰情總結（約 L4259、L4371）；舊 UI `etf_tab_dividend_station.py` 約 L712 | App 經 `src/services/app_ai_service.gemini_call` **固定帶 `TAIWAN_ADVISOR_PERSONA`**，temperature 0.3 | legacy，遷移前保留（付費 gate 不變） |
| LINE AI 總結 `scripts/push_holdings_daily.py`（約 L144） | 同 `build_summary_prompt`；走 `ai_fetcher.post_gemini`，**不帶 persona**、temperature 0.2 | **refactor**：改吃 Brain 同一輸出 slice（App／LINE persona 與溫度不同 → 可能分歧，INFERENCE） |
| 週報 `weekly_review_service.build_weekly_review`＋`weekly_review_prompt` | 自建 headless「大盤定調」（加權 vs 年線），非 `get_macro_state` | **replace**（第二套市場定調） |
| 每日選股 `push_daily_signals`＋`ai_judgment` | 要 AI 分類偏多／偏空／需觀察＝AI 產生判斷 | legacy（排程已停）；⛔ 併入 Brain |
| `app_ai_service.gemini_call` | 金鑰池、v1beta、失敗回 ⚠️ 字串；persona 衝突 | legacy transport；交 AB-2b Decision Gate |
| `ai_fetcher.post_gemini` | — | AB-2b 單一傳輸層候選 |
| `macro_state_locker.execute_and_lock` | Python 算 system_state，AI 只寫 traffic_light／market_level／strategy／analysis_summary 文字；`get_macro_state` 不讀這些 AI 欄位 | legacy；Digest ⛔ 搬 AI 文字欄位 |
| `ai_qa_service.run_agent`（6 唯讀工具）／`summarize_tab`／`discuss_stock` | SYSTEM_INSTRUCTION 強制先下方向判斷；`summarize_tab`＝每頁一套 AI | 獨立功能，⛔ 併入 Brain（C §2.3）；「工具 ok=false 明講無法判斷」可借用 |
| `page_why` 問 AI（`run_agent(require_valid_risk_cap=True)`，legacy-only） | — | legacy |
| `ai_structured_summary.build_structured_summary_prompt` | 各 tab 章節名＋字串 | legacy；⛔ 當 Brain 輸入 |
| `exit_signals.judge_news_sentiment` | AI 情緒 → 進出場訊號（利空採信 confidence≥50） | legacy；⛔ 以 rule result 進 Digest |
| `sidebar_health._call_gemini_brief`、`financial_health_engine` AI insight、`section_news_ai`、`tab_stock`、`tab_stock_grp`、`etf_tab_ai` 等 | grep 分類 | legacy |
| 新四頁 `page_market`／`page_target` | `HERO_AI_PLACEHOLDER`／`AI_PLACEHOLDER`「🤖 AI 投資總結：⬜ 尚未提供」，無 AI 呼叫 | AB-5 接點 |

## §7 入口（R13）

AI 投資總結入口＝**各頁 L1 固定元素**（E2 卡＋展開面板；桌機展開面板、手機全螢幕面板），**計入 Visual Budget**；**不是第五頁、IA 不變**（DEC-091 §三「不是第五個主導航頁」；`ai_summary.html`；`index.html`「全站唯一，不是第五個主導航」）→ 不需 page-count Decision Gate（客戶 DEC-109 二十：只有真的需要 page-count／IA 變更才整理單一最小 Decision Gate）。

## §8 驗收測試（Phase 7 寫成測試）

1. **AST 守衛擴到 Brain**：不 import `streamlit`／`src.ui.*`／`views`／`app`。
2. **簽名守衛**：Brain 與 Digest 組裝點不接受 `top_n`／`expanded`／任何 UI 參數。
3. **不變性**：同一上游輸出下，UI Top-3 vs 全量、expander 收／展，`digest.to_dict()` 完全相同。
4. **headless**：無 session 冷啟動時市場段由 canonical 路徑組出或誠實 MISSING，不因沒按「🚀 更新今日戰情」而與 canonical 可得資料不同。
5. **slice**：Local Summary 每句 ⊂ 全文 lines（逐字）。
6. **查看依據只從 Digest／`evidence_refs` 渲染**；突變：AI 文字換自由文字必被 `check_summary` 拒。
7. **列舉鎖**：`DataStatus`、`AiParticipation` 成員不變；無 confidence 列舉。
8. **candidates G1 反例**：不在允許名單的 ticker／產業結論被拒。

## §9 既有 Gate 依賴（不因本檔解除）

- **AB-2b Decision Gate**（`BP-DR-20`）：AI 只選句型填 slot vs 自然語言潤飾 —— 未裁示前 AI 出口不接 production。
- **RC-VISIBILITY／DEC-081 Q2-2**：核准顯示前只能答 Risk Cap 狀態與核准措辭；把 cap 連到具體行動屬新規則（HI-1／HI-4），⛔ AI 推論。
- **變化排序**：無正式規則 → MISSING（§5 末點）。
- **AB-4w（HI-5）**：策略分類寫入面未核准 → 讀不到即「未分類」。
