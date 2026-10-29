# Decision Digest Contract vNext（AI 決策輸入層契約）

- **狀態**：正式／現行（Phase 1 凍結版；**本 phase 只凍結契約，不改 `shared/decision_digest*.py`、`src/services/decision_digest_*.py` 任何一行**）
- **日期**：2026-10-29　**基準**：PR base＝main `978ecedc`；程式事實適用 `978ecedc`（本分支只多 docs）
- **決策來源**：架構鏈、「Digest 不是 UI scrape」、AI 不得從 UI 反推、最低概念契約欄位、不得創造新 confidence 語意、「Digest contract 凍結前不得寫新 LLM prompt／glue」＝**客戶 2026-10-29（`docs/DECISIONS.md` DEC-109 十六～十八、三十一，逐字）**；以 AB-0 v1 為基底、加性 v2 計畫 A1～A8、依賴順序＝**AI 總管內部決定（DEC-110，`CLAUDE.md` §-1.5.D v3 §03-1）**，Phase 7 實作並過獨立 QA。
- **上位**：`CLAUDE.md` > `PROCESS.md` > `PROJECT_RULES.md`＋`docs/governance/*` > 最新有效 DEC（DEC-092、DEC-093～096、DEC-109／110）> **本檔**。既有 C 規格 `docs/vnext/NEWUI_D25_C_AI_BRAIN_DATA_2026-10-27.md` §4（草案，已被其 §11 取代）與 AB-1／AB-2a／AB-4r spec 仍為實作細節出處；**與本檔衝突時以本檔＋程式為準**。
- **配套**：`docs/vnext/ONE_AI_BRAIN_BOUNDARY_vNext_2026-10-29.md`（Brain 邊界）、`docs/vnext/PRESENTATION_CONTRACT_vNext_2026-10-29.md` §9（UI 簡化不得減少 AI Decision Context）。
- ⚠️ **揭露（`CLAUDE.md` §-2 規則 6）**：現況盤點來自單組調查 Inv-4＋獨立稽核組勘誤（已併入 §2、§4）；「0 production caller」等為 grep 結果、非窮舉；**承重判定（A4 前置、headless 組裝點、不新增 confidence）建議 Phase 7 開工前另組覆核**。

---

## §1 架構鏈（客戶原文 DEC-109 十六）

```
Raw Sources
→ Canonical Data
→ Deterministic Rules / Indicators / Risk Cap
→ Decision Digest
→ One AI Brain
→ UI Local Summary / AI 投資總結
```

- **Data View ≠ Decision Context ≠ AI Output.**（客戶原文）各頁畫面是 Data View；Decision Digest 是 Decision Context；Brain 的摘要是 AI Output。三者分開，⛔ 任一層從另一層反推。
- **Decision Digest 是 AI 的完整、結構化、可追溯決策輸入層。它不是 UI scrape。**（客戶原文）
- **Decision Digest 必須直接由 canonical data＋formal rule results 建立。**（客戶原文 十七）
- 與 `CLAUDE.md` §8.2 七層的對映（INFERENCE，撰寫組）：Canonical Data＝L1（＋L0 schema）；Rules／Indicators／Risk Cap＝L2 純函式＋L3 編排；Decision Digest＝L0 契約（`shared/decision_digest.py`）＋L3 builder（`src/services/decision_digest_builder.py`）；One AI Brain＝L3 service（Phase 7 新建）；UI Local Summary＝L4／L5 只渲染。

## §2 AI 不得從 UI 反推資料（客戶原文 DEC-109 十七，逐字）

One AI Brain 不得：scrape Streamlit 文字當 canonical data；從顏色猜狀態；從 widget 顯示文字推斷數據；因 expander 收合就不讀某資料；因 UI 沒顯示某指標就認定不存在；從 UI Top-N 認為只有 Top-N 資料存在。

### 2.1 現況結構性風險（FACT＋稽核勘誤；Phase 7 前置）

- **市場段依賴 session warroom**：Digest 市場段上游 `src/services/macro_state_locker.get_macro_state(warroom_summary=...)` 的第一優先來源是呼叫端傳入的 `warroom_summary`（`effective_regime`）。**新 UI 唯一寫入 warroom 的路徑**是今天頁「🚀 更新今日戰情」（`page_today` → `macro_refresh_service.refresh_macro_now` → `warroom_apply.compute_and_store_warroom_summary`）；**`page_market` 只讀不寫**；舊 UI `section_traffic_light`／`section_state` 也會寫（FACT，稽核組查證）。因此 Digest 市場段的內容取決於「**session 是否已有 warroom（取決於是否按過更新今日戰情）**」——⛔ 不是「使用者是否先載入市場頁」。另：`BREADTH_PROXY_SCORING_ENABLED=False` 時，無 warroom → 結果為 `unknown`／`is_loaded=False`。
- 這違反「⛔ 因 UI 收合／未載入而少讀」的精神 → **Phase 7 前置：建立 headless canonical Digest 組裝點**（不讀 `st.session_state`，由 canonical service 取數；無資料時誠實 MISSING），BACKLOG `P1R-DIGEST-HEADLESS-ASSEMBLY`。
- **反例（FACT）**：`app.py` 約 L1210 `render_tab_summary('選股網', {'選股結果': _cands.head(15)…, '缺貨掃描': st.session_state.get('_shortage_rows'), …})`＝UI Top-N＋session 片段直接餵 AI（legacy 路徑）→ 新架構 ⛔ 沿用此模式。

## §3 既有檔（FACT，main `978ecedc`；AB-0／AB-1／AB-2a／AB-4r 已合併、0 production caller）

| 層 | 檔＋符號 | 內容 | PR |
|---|---|---|---|
| L0 AB-0 | `shared/decision_digest.py`（`SCHEMA_VERSION="decision_digest.v1"`、`MAX_ACTIONS=3`；`DataStatus`／`MissingReason`／`Availability`／`AiParticipation`／`StrategyType`／`DefinitionState`／`ActionOrigin`；`Provenance`／`RuleRef`／`Fact`／`HoldingKey`／`HoldingEntry`／`ActionRef`／`FactSection`／`DefinitionSection`／`HoldingsSection`／`RiskCapSection`／`ActionsSection`／`DecisionDigest`；validate／assert_valid） | 嚴格可追溯骨架 | #949 |
| L0 AB-1 | `shared/decision_digest_rules.py`（`RULE_ID_ALLOWLIST`、`Q4_ACTION_PRIORITY`、`assert_strict`） | rule_id 允許名單、Q4 優先序 | #951 |
| L3 AB-1 | `src/services/decision_digest_builder.py::build_decision_digest`、`SourceStamp` | 純函式 builder（0 production caller） | #951 |
| L0 AB-2a | `shared/decision_digest_terms.py`（`SECTION_KEYS`＝market／industry／buy_and_hold／capital_gain／actions 固定五段）、`decision_digest_validator.py`（`assess_digest`、四態）、`decision_digest_grounding.py`（`Lit`／`Ref`、`check_summary`、G1～G6；G5「五段齊全、唯一、固定順序」） | grounding／驗證 | #953 |
| L3 AB-2a | `src/services/decision_digest_summary.py::build_rule_summary` | 規則式摘要（只接受 rule_only；0 caller） | #953 |
| AB-4r | `shared/strategy_class_schema.py`（`derive_portfolio_id`）、`src/data/portfolio/strategy_class_reader.py::read_strategy_classes` | 策略分類唯讀契約；**未接 builder**（`AB4R-WIRE-BUILDER`） | #955 |
| 守衛 | `tests/test_decision_digest_{contract,builder,rules,grounding,validator,round2,summary}.py`、AST：`test_builder_imports_no_streamlit_ui_or_network`、`test_builder_not_imported_directly_by_app_or_ia_nav`、`test_builder_signature_does_not_accept_industry_or_picks` | — | — |

## §4 最低概念契約（客戶 DEC-109 十八：每個可判斷項概念上至少保留）

客戶原文欄位：identifier／value／result／unit（如適用）／source／as_of／retrieved_at（若已有）／stale／freshness／missing／unavailable／provenance／rule result／relevant threshold／policy reference／confidence／evidence state（**只有既有正式語意才保留**）。**不得創造新的 confidence 語意。** 不要現在建立巨大 schema；先盤點、建立 minimum sufficient contract。

| 概念 | AB-0 v1 現況（FACT） | 缺口 → v2 加性項 |
|---|---|---|
| identifier | `Fact.fact_id`、`ActionRef.action_id`、`HoldingKey(portfolio_id, symbol)` | — |
| value／result | `Fact.value`（有限實數）或 `Fact.text` | text 逐字等於規則輸出、`ActionRef.text` 綁分支碼未驗（`AB1-ACTION-TEXT-RULE-BINDING`） |
| unit | `Fact.unit` 選填 | 市場事實無 unit（維持選填） |
| source | `Provenance.source`（拒 AI 字樣） | 標籤為服務名（例 `macro_state`）非真資料源 → A1 |
| as_of | `Provenance.as_of`（防 lookahead） | `get_macro_state` 無逐指標 as_of（`AS_OF_NOT_IN_CONTRACT`）；只有 Risk Cap snapshot_ts 是真日期；其餘靠 `SourceStamp`，否則 MISSING |
| retrieved_at | `Provenance.fetched_at` | 同上 |
| stale／freshness | `DataStatus.STALE` 有定義 | builder 從不產出 STALE → A2；DEC-080 freshness 軸未進契約 → A1 |
| missing／unavailable | `DataStatus`{ok, stale, missing, proxy, failed, invalid}（**無 neutral**）、`MissingReason`、各段 `Availability` | 最完整；不動 |
| provenance 等級 | 只有 `DataStatus.PROXY` | DEC-080 provenance 軸 {official, secondary, estimated, proxy, unavailable} 未進契約 → A1 |
| rule result | `Fact`＋`RuleRef`、`ActionRef.rule` | 市場事實刻意不帶 rule（維持） |
| threshold／policy reference | `RuleRef(rule_id, rule_version)` | 無門檻值欄 → A8：**維持 RuleRef**，「查看依據」以 rule_id 對回 SSOT 常數渲染，Digest ⛔ 搬門檻數值 |
| confidence／evidence | evidence：`ActionRef.evidence_refs`（只指 ok／stale 事實）、G6 每句要 Ref | **無正式 Digest confidence 語意** → **只保留可得性 N／M（A6 coverage）**；⛔ 新增 confidence 欄或列舉；舊 `tl['conf']`（`macro_helpers` 約 L615，來源可得 %）與 `exit_signals` AI 情緒 confidence（AI 產生）**都不得當 confidence** |

## §5 以 AB-0 v1 為基底：不動項（Phase 7 亦不得改）

`Fact`、`Provenance`、`RuleRef`、`DataStatus`、`MissingReason`、`Availability`、`AiParticipation`、`ActionRef`、`HoldingKey`、各段推導規則、`DefinitionSection` 綁定（台股／國際趨勢、估值、產業＝`NOT_DEFINED`／`RESEARCH_ONLY` 直到正式 Gate）、`MAX_ACTIONS=3`、AB-2a 句型白名單與 G1～G6 的**防線語意**（G5 的「段落集合」隨 R12 新輸出格式於 Phase 7 內部調整，見 Brain 文件 §5）。列舉成員由測試鎖死，新增成員＝改契約、須升 `SCHEMA_VERSION`。

## §6 加性 v2 計畫 A1～A8（內部技術決定；Phase 7 實作、升 `decision_digest.v2`、過獨立 QA）

| # | 加性項 | 內容與邊界 |
|---|---|---|
| A1 | Provenance 兩軸 | 加 DEC-080 `provenance_class`、`freshness`（值取 `shared/input_provenance_policy.py`；`carried_forward` 無正式定義不啟用） |
| A2 | 產出 STALE | builder 依 `shared/staleness` 判 STALE（⛔ 自訂門檻） |
| A3 | candidates 段 | ticker 鍵；只搬 `get_ranked_picks`／`get_switch_in_candidates` 既有輸出＋來源；⛔ 帶產業結論；G1 擴允許名單；**L3 請求參數＝既有預設（`DEFAULT_TOP_N=50`），與 UI Top-N 無關** |
| A4 | risks 段 | 五桶各取最需注意一項（DEC-092 Q3）；不足 → MISSING。**前置**：worst-of 的 `build_rows`／`bucket_summary`／`overall_verdict` 目前**只在 L5 `tab_macro_v2`**；計算核心在 L2（`macro_helpers.compute_five_bucket_summary`、`src/compute/macro/daily_key_alerts.collect_key_alerts`），兩者輸入皆為 session 片段；無 L3 canonical service；`macro_alerts` 唯一寫入點是舊 UI `section_mid`（FACT，稽核組）→ **worst-of 由 L5 下沉＋建 L3 canonical 輸入組裝（不讀 session）**（`P1R-FIVE-BUCKET-L3`） |
| A5 | 持股 entry 數值 facts | 張數／均價／現價／損益%／健檢燈；只搬 `holdings_service`／station rows；⛔ 帶加碼金；核心／衛星只能標「依種類近似」 |
| A6 | coverage | `{evaluated, expected}`（N／M）；**⛔ 新增 confidence** |
| A7 | excluded_count | 外幣排除數、AB-4r invalid／conflict／unmatched 計數（現在被 `continue` 靜默丟棄，`XV-C05`） |
| A8 | 門檻引用 | 維持 `RuleRef`；查看依據以 rule_id 對回 SSOT 常數渲染；Digest ⛔ 搬門檻值 |

## §7 Domain 覆蓋與缺口（FACT，Inv-4）

| Domain | 現況 | 缺口 |
|---|---|---|
| 市場 | `market.regime`／`light`／`health`（`get_macro_state`） | 依賴 session warroom（§2.1） |
| Risk Cap | `cap_pct`、`exposure_lo／hi_pct`、`cap_valid`（摘要層不顯示數值，DEC-081 Q2-2） | RC-VISIBILITY 未核准前只能答狀態＋核准措辭 |
| 持股 | 只有鍵＋行動事實 | A5 |
| 策略分類 | 固定「未分類」直到 AB-4w（HI-5） | `AB4R-WIRE-BUILDER`；⛔ AI 推論 |
| 行動 | `dividend_station._action` ∈ {cut, take_profit_force, take_profit_partial, pause_add, add}，Q4 排序最多 3 | 個股 assess_stock／flag_take_profit／換股建議不搬（待 `AB1-STOCK-PATH-AND-TAKE-PROFIT-RANK` 客戶裁示） |
| 台股／國際趨勢、估值 | `DefinitionSection` 固定 NOT_DEFINED／RESEARCH_ONLY | 正式定義屬 High Gate |
| 產業 | NOT_DEFINED | 產業趨勢正式定義未核准（DEC-092 Q5） |
| 候選／新機會 | 無此段（C §11 #4 拿掉） | A3 |
| 主要風險／五桶／變化 | 無此段，只存在 UI 層 | A4；「最大 1～3 變化」**無正式變化量選取規則** → 列為 Phase 7 線框待客戶拍板點 **W8**（Presentation Contract §22；BACKLOG `P1R-P7-WF-CHANGE-RANK`），**不作內部預設**；拍板前此項誠實 MISSING |
| 資料健康 N／M | 無 | A6 |

## §8 Phase 7 依賴順序（INFERENCE，內部；可調）

1. `AB4R-WIRE-BUILDER`（策略分類唯讀接 builder）。依 BACKLOG 該列原文：**唯讀接線本身不是 HI-5 寫入面**，但「使用者手動建立的 `strategy_class` 分頁分類不得在 AB-4w（HI-5）核准上線前生效」→ 接線後 Digest `holdings[].strategy_type` 仍一律「未分類」，提前生效須重新送 Gate；且**接線前必修 `XV-C05`**（鍵大小寫不一致致行動被靜默丟棄）。
2. 五桶／key alerts worst-of 由 L5 下沉＋L3 canonical 輸入組裝（A4 前置，`P1R-FIVE-BUCKET-L3`）
3. headless canonical Digest 組裝點取代 session warroom 依賴（`P1R-DIGEST-HEADLESS-ASSEMBLY`）
4. A1～A7 升 v2（含 A8 規範）
5. AB-5／AB-6：UI 先只用規則式摘要（`build_rule_summary`，輸出格式依 R12 調整）
6. AB-2b（AI 出口）先過既有 Decision Gate（`BP-DR-20`：AI 只選句型填 slot vs 自然語言潤飾）

**硬限制（客戶原文 DEC-109 三十一）**：「**不得在 Decision Digest contract 未凍結前：直接開始寫新的 LLM prompt／glue。**」本檔凍結的是**最低概念契約與 v1 不動項**；**v2 schema（A1～A7）定案前，不寫新的 prompt／glue**（A8 為規範、不另成 schema 欄位）。

## §9 驗收（Phase 7 開工時寫成測試；本 phase 不寫 code）

1. AST：Digest 組裝點不 import `streamlit`／`src.ui.*`／`app`；不讀 `st.session_state`。
2. 簽名：組裝點與 builder 不接受 `top_n`／`expanded`／任何 UI 參數。
3. 不變性：同一組上游輸出下，UI Top-3 vs 全量、expander 收／展、是否載入市場頁，`digest.to_dict()` **完全相同**。
4. headless：無 session 冷啟動時市場段由 canonical 路徑組出，或誠實 MISSING（不因沒按「🚀 更新今日戰情」而內容不同於 canonical 路徑可得之資料）。
5. 列舉鎖：`DataStatus`、`AiParticipation` 成員不變；**無 confidence 列舉**。
6. candidates G1 反例測試（不在允許名單的 ticker／產業結論被拒）。

## §10 不在本 phase 範圍

本 phase **只凍結契約**：⛔ 改 `shared/decision_digest*.py`、`src/services/decision_digest_*.py`、⛔ 新 prompt、⛔ 接線 production。A1～A8、§8 步驟均登 BACKLOG（`P1R-DIGEST-V2-A1..A8` 等）。
