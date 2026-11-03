# New UI2 Real Feed：Canonical Read Path Mapping（NUI2-REAL-FEED A1；2026-11-03）

- **狀態**：實作組產出（A1 mapping＋A2 adapter＋A3 shadow acceptance 同批），**待總管複驗／獨立 QA／客戶驗收**。
- **依據**：客戶 2026-11-03 指示 (11)（NUI2-REAL-FEED；選 A；本批 ≤3 項 A1／A2／A3；禁止清單；Stop／Decision Gate 規則）。
  **本批無新客戶裁示 ⇒ 無新 DEC**；下文標「AI 總管內部判準（可推翻）」者皆屬 `CLAUDE.md` v3 §03-1 內部自決。
- **基準**：`origin/main`＝`ade8181e`（#1002）。
- **上位**：`CLAUDE.md` §1／§2／§8.2 > `PROJECT_RULES.md` §19.8、§27～§29 > DEC-122～127 > `NEWUI2_ARCHITECTURE_GATE_2026-11-02.md` >
  `NEWUI2_REUSE_MATRIX_2026-11-02.md`／`NEWUI2_MIGRATION_CUTOVER_CONTRACT_2026-11-02.md` > 本檔。
- **輸入**：兩份**獨立**盤點（組 A：由 UI2 欄位往下；組 B：由 canonical 層往上；皆唯讀、各自單組）＋實作組實查程式（本檔 §1 記錄差異與裁定）。
- ⚠️ 揭露（`CLAUDE.md` §-2 規則 6）：本檔所有分類／全稱句為**實作組單組**整合兩份盤點後實查的結果；每列附驗證方式。
  「欄位清單」以 `src/services/ui2/scenarios.py` 的 canonical key 為準（**非 AST 窮舉**）；Legacy／Old UI 的其他能力不在本表射程。
- ⛔ **不得**把本批描述成「真資料已接上」：**只接 2 個事實**（台股加權指數、市場位階），其餘欄位在 Real 模式一律 ⬜＋原因。

---

## §0 一句話結論

- 本批可零寫入、零網路、自帶 provenance 讀取、且**已確認 canonical** 的事實只有兩個：**台股加權指數**（📊 卡）與**市場位階**（📊 現在狀態、🎯 W-4 context、🎯 6 維「市場環境」三處＋📊 L2「位階說明」）。
- 市場位階在現行正式規則下（`BREADTH_PROXY_SCORING_ENABLED=False`、UI2 Preview 不跑 🚀 更新鏈）**恆為 ⬜**：冷啟動＝Not Evaluated `⬜ 尚未載入`；
  若 session 有 warroom 但缺真實廣度＝Unable to Determine `⬜ 未評估／資料不足`。**這是現行正式語意，不是 bug**；Real-data Preview 誠實呈現它。
- 市場核心事實（16 燈 readiness、五桶、VIX／US10Y／DXY、指標危險度、今日主要風險、結論子句）**只存在 session**，須 🚀 `refresh_macro_now`
  （連網＋寫 `risk_cap_state.json`／`macro_state.json`）⇒ 本批 ⛔ 觸發（SG-01）⇒ Real 模式 capability `⬜ 尚未提供`＋原因。
- **B（Aggregator）不是 A 的前置**：只擋動作欄（動作欄維持 `⬜ 尚未提供（待 System Action Aggregator）`）。
  **C（OAuth／Sheet）是 💼 持股與 👤 我的真資料的前置**：本批兩頁在 Real 模式全為 capability＋原因，⛔ 呼叫 `get_holdings`／`get_account`／`build_login_url`。

---

## §1 兩組盤點差異與實查裁定（實作組；單組）

| # | 議題 | 組 A | 組 B | 實查與裁定 |
|---|---|---|---|---|
| D1 | 位階入口 | `allocation_service.get_macro_regime(strict=True, require_valid_risk_cap=True)` | `macro_state_locker.get_macro_state(warroom, …)`，warroom 由殼以白名單唯讀 Mapping 注入 | **採 A**。實查：(1) `get_macro_regime` docstring 自稱「`get_macro_state` 與 session_state 之間的**唯一橋樑**；任何 UI 一律」用它；(2) 它對 session **只做 `.get('warroom_summary')`**（讀碼 `allocation_service.py:342-392`＋A3 runtime 紀錄器實測 0 次寫入）；(3) B 案需要殼讀非 `ui2_` key（`warroom_summary`）再傳出 ⇒ 撞 G9（或另開 helper 例外），若改成 feed 端 `warroom=None` 寫死，等於在 adapter 裡另做一個「Preview 永遠沒有 warroom」的判斷；(4) 兩者在 strict 下皆不吞錯（實測：壞 `macro_state.json` → `RuntimeError`）、皆不寫檔。`require_valid_risk_cap=True` 與 Legacy New UI 市場頁同一呼叫；其 Risk Cap 欄位（`exposure_limit_pct`／`risk_cap_disclosure`）**不進 snapshot**（`RegimeFact` 欄位集合由測試鎖定）。 |
| D2 | A3 shadow 方法 | 一般道注入＋真 git 追蹤 parquet | 建議以 `run_headless_refresh(tmpdir)` 跑 headless session | **採 A**：客戶 (11)／總管規格要求 A3 一般道**不連網**；`run_headless_refresh` 需網路且其 MODE_WARM 寫檔範圍未驗（B 自述）⇒ 不採。 |
| D3 | A2 射程 | 只接 2 事實 | 建議再接 R 類（sector_flow、ticker_sector_map、calibration、Rule Registry） | **採 A（規格限 2 事實）**；B 的 R 類登記為下一批候選（§6 PORT／候選表）。 |
| D4 | VIX／US10Y／DXY 來源 | readiness 側車（`compute_five_bucket_summary(readiness_out=)`），無 as_of | session `macro_info['vix']`（`date` 可經 L2 `dated_inputs.extract_vix`） | **兩者都只存在 session（須 🚀 更新鏈）** ⇒ 本批不接，分類 🟡；另登記 **VIX 雙路徑**（市場：session `macro_info['vix']`／readiness；持股：`dividend_station_service.fetch_vix()` render 時連網、無 as_of）。readiness 與 `macro_info` 何者為 UI2 的唯一入口＝PORT 批決定（`NUI2-PORT-READINESS-L3`）。 |
| D5 | 利差 | ⬜ 無 canonical 欄（SG） | R\*／未驗 | **實查**：`shared/macro_buckets.py` 的 DangerSpec 全部 key＝`health ndc_signal m1b_m2_gap ism_pmi us_core_cpi tw_export bias_240 vix us10y dxy adl fut_net margin jingqi foreign_net news_systemic usdtwd taiex`，**沒有利差** ⇒ 採 A：⬜＋SG-02（新資料定義）。 |
| D6 | 守衛 | G2 範圍＝目錄全檔，需檔案層級例外 | 同；另指出 G9 整包 session 傳遞漏洞 | 兩者皆採：新增 G2F（具名 `FEED_FILES`）＋G9 補洞（§7）。 |
| D7 | `is_stale=None` | 建議 Stale `⚠ 可能已過期` | （未論） | **採 A，AI 總管內部判準（可推翻）**：service 檔頭明文「attrs 缺 → `is_stale=None`（⬜ 未判定），⛔ 不當成新鮮」⇒ 新鮮度未知 ⛔ 當 OK。 |
| D8 | 位階 FieldVM.source | 寫「總經 canonical 契約」，分支 id 放 detail | 未論 | **改採規格**：`規則分支 id：<source>（非資料來源）`（誠實標分支、⛔ 偽裝資料來源）。 |

---

## §2 Fake → Real 邊界（A2 實作）

```
Existing Canonical Services（唯讀）
  ├─ src/services/market_twii_view_service.get_twii_trend_view(1)       讀 git 追蹤 data_cache/twii_ohlcv.parquet
  └─ src/services/allocation_service.get_macro_regime(strict=True,
        require_valid_risk_cap=True)                                     session .get＋讀本地 macro_state.json／risk_cap_state.json
        │
        ▼
src/services/ui2/real_feed.py（L3；New UI2 唯一做 I/O 的檔；G2F）     每 rerun 一次；例外接住→錯誤字串；兩事實隔離
        │   RealFeedSnapshot（frozen；TwiiFact／RegimeFact 原樣欄位；⛔ Risk Cap 欄位）
        ▼
src/services/ui2/real_canonical.py（L3；純函式；G2）                    snapshot → canonical dict（沿用既有 spec 鍵）
        ▼
既有 build_market_page_vm／build_skeleton_page_vm（VM 不重寫；只加 banner 分派）
        ▼
src/ui2（L5；不重寫）＋殼 `ui2_feed` 切換（預設 FAKE）
```

- **Real／Fake 區分**：`PageVM.is_fake=False`、`scenario_id="real"`（`SCENARIO_REAL` **不在** `SCENARIO_IDS`）；banner＝`REAL_PREVIEW_BANNER_TEXT`
  「Real-data Preview（非正式 production default）」＋`REAL_PREVIEW_BANNER_NOTE`；real 的任何字串 ⛔ 含 `FAKE`、FAKE 的 source 必以 `FAKE` 開頭（雙向測試）；
  FAKE canonical 用 `real` 場景、或非 FAKE 用 FAKE 場景 → `build_page_vm` raise。FAKE 六場景原封不動（regression）。
- **殼**：`ui2_feed`（selectbox，Preview 控制內；預設 `fake`）。Real 模式時場景／帳戶兩個 FAKE 維度 widget **disabled**（保留狀態）。
- ⛔ 本批未改：`app.py`、`requirements.txt`、`src/ui/**`、`src/ui_v2/**`、`src/data/**`、`src/compute/**`、`shared/`（非 `ui2_contract`）、`src/services/`（非 `ui2/`）。

---

## §3 canonical service 性質（Preview 呼叫時；實查）

| Service | 讀寫 | session | 網路 | 失敗模式 | 本批 |
|---|---|---|---|---|---|
| `market_twii_view_service.get_twii_trend_view` | 唯讀（讀 parquet＋`metadata.json`） | 不碰 | 否 | 讀不到 `ok=False`（灰）；import／讀取例外 `failed=True`（紅）；`n<1` raise | ✅ 接 |
| `allocation_service.get_macro_regime(strict=True, require_valid_risk_cap=True)` | 唯讀（讀 `macro_state.json`／`risk_cap_state.json`，皆**不在** git） | 只 `.get('warroom_summary')` | 否 | strict：檔存在卻壞 → raise；檔不存在 → 未評估 | ✅ 接 |
| `allocation_service.get_allocation` | **寫** session（`_alloc_decision_cache`／`_alloc_decision_sig`） | 寫 | 否 | — | ⛔（G2F） |
| `macro_refresh_service.refresh_macro_now` | **寫** session＋`risk_cap_state.json`＋`macro_state.json` | 寫 | **是** | — | ⛔（SG-01；G2F／G9） |
| `me_account_service.get_account` | OAuth 已設定且未登入時經 `build_login_url`→`get_login_state` **寫** `st.session_state["_oauth_state"]`＋`_nonce_store.issue` | 寫 | 否 | — | ⛔（C；G2F） |
| `holdings_service.get_holdings` | 唯讀（自稱） | 經 L1 讀 `gsheet_tokens` | **是**（Sheets） | — | ⛔（C；G2F） |
| `sector_flow_service.get_sector_flow_view` | 唯讀 | `use_active_selection=True` 時經 holdings（C） | 否（三參數關閉時） | `ok=False` | 未接（排序在 L5 → PORT） |

驗證：讀碼（各檔對應函式）＋A3 測試（runtime 紀錄器、socket guard、工作樹與狀態檔 hash／mtime；另人工 `git status --porcelain` 前後比對）。

---

## §4 四頁逐欄 mapping（UI2 Field → VM → canonical → provenance → freshness／missing → 分類 → Real 模式呈現）

分類：**✅ 本批接**／**✅C** 有 canonical 但被 C（OAuth／Sheet）擋／**🟡** 需先 PORT 至 L3（Legacy UI 層內部邏輯，直接接＝第二套 rule engine）或只存在 session／**🔒** 契約固定／**⬜** 無 source／無定義。
Real 模式「⬜ 尚未提供＋原因」＝capability marker（Preview-only；DEC-124；`NUI2-CAPABILITY-MARKER-CUTOVER-ZERO`）。

### §4.1 📊 市場（`p4_market`）

| # | UI2 Field（key） | VM 落點 | Canonical（檔:符號） | Provenance | freshness／missing 語意 | 分類 | Real 模式 |
|---|---|---|---|---|---|---|---|
| M1 | 市場目前狀態（`regime`） | `FirstScreenVM.current_state` | `allocation_service.get_macro_regime(strict=True, require_valid_risk_cap=True)` → `macro_state_locker.get_macro_state`；顯示字 `shared.allocation_decision.REGIME_LABEL` | `source`＝**規則分支 id**（`shared.regime_arbiter.SOURCE_*`）；**無 as_of、無 fetched_at** | 見 §5.2 | ✅ | 冷啟動 `⬜ 尚未載入`；detail＝`⬜ 資料日未提供（市場位階契約不含資料日）；說明見「為什麼（L2）」` |
| M1b | 位階說明（L2 `why` 區） | `SectionVM.fields[0]` | 同 M1（同一 snapshot） | 同 M1 | 同 M1；detail＝L0 `NOT_LOADED_PENDING_BREADTH_EXPLAIN`／`UNEVALUATED_BREADTH_EXPLAIN` **逐字** | ✅ | 第一屏放短句、完整說明在 L2（Freeze §16.5 縮字句；⛔ 移出必要項） |
| M2 | Risk Cap（`context_rows`） | `context_rows[0]` | 🔒 Freeze §0.1.4＋Q1=A；`TEXT_RISK_CAP_UNDETERMINABLE` | — | Unable to Determine（固定） | 🔒 | `⬜ 無法判定`（與 FAKE 同一 FieldVM；測試鎖定） |
| M3 | 是否需要行動 | `action_needed` | 🔒 B：`vm_common.PAGES_ACTION_FROM_AGGREGATOR_ONLY` | — | capability | 🔒（B） | `⬜ 尚未提供（待 System Action Aggregator）` |
| M4 | 下一步 | `next_step` | 🔒 B（None → aggregator pending） | — | capability | 🔒（B） | 同上（⛔ 指向 disabled 的 🚀） |
| M5 | 🚀 更新今日戰情 | `primary_cta` | `macro_refresh_service.refresh_macro_now`（Reuse S21） | — | disabled | 🔒＋SG-01 | disabled「Preview 不觸發更新（另開 Gate）」 |
| M6 | 今日結論 | `FirstScreenVM.conclusion` | L0 `shared.market_conclusion.build_market_conclusion` ✅；子句 `page_market.regime_clause／danger_clause`（L5） | 無 as_of | 子句缺值明寫 | 🟡（PORT；danger 子句需 session readiness） | `⬜ 尚未提供`「尚未接線（結論子句需先 PORT）」 |
| M7 | 今日主要風險 | `PageContext.main_risk` | L5 `_market_blocks.build_market_risks／hero_risk_*` | 無 | DEC-117 Q6 退化句 | 🟡（PORT＋session） | `⬜ 尚未提供`「尚未接線（需 🚀 更新後的 session）」 |
| M8 | 台股（`cards.twii`） | `CardVM` | `market_twii_view_service.get_twii_trend_view(1)` → L1 `macro_cache_reader.load_twii_close`（`.attrs`） | `source`＝`TWII_SOURCE_TEXT`、`as_of`、`is_stale`、`age_days`、`stale_reason`、`upstream_error`；**無 fetched_at** | 見 §5.1 | ✅ | 例：`44,920.14`、資料日 `2026-11-02`（量測日快照）、來源 chip |
| M9 | VIX | `CardVM` | readiness `vix`（L2 `compute_five_bucket_summary(readiness_out=)`，經 L3 `section_inputs.load_section_inputs(session)`；編排在 L5 `page_today.load_macro_readout`）；或 session `macro_info['vix']` | readiness 無 as_of；`macro_info` 有 `date` | ok／missing＋reason；無 stale 態 | 🟡（session＋PORT；D4） | `⬜ 尚未提供`＋原因 |
| M10 | US 10Y | `CardVM` | readiness `us10y`／`macro_info['us10y']` | 同 M9 | 同 M9 | 🟡 | 同上 |
| M11 | 利差 | `CardVM` | **無 canonical 欄**（D5 實查） | — | — | ⬜＋SG-02 | `⬜ 尚未提供`「無 canonical 利差定義」 |
| M12 | DXY | `CardVM` | readiness `dxy` | 同 M9 | 同 M9 | 🟡 | 同上 |
| M13 | PMI／景氣 | `CardVM` | readiness `ism_pmi`（實為台灣 PMI）vs `ndc_signal`（景氣燈號）；另 `tw_pmi.parquet`（L1 `load_tw_pmi_history`，無 L3） | parquet 有日期、無 is_stale | — | 🟡＋SG-03 | `⬜ 尚未提供`「兩源語意不同、待定義」 |
| M14 | 🤖 OneBrain Outlook | `SectionVM` | 無（Stage G） | — | — | ⬜＋SG-09 | `⬜ 尚未提供`「Stage G 前不提供」 |
| M15 | 位階理由／反證／新鮮度／來源（L2） | `SectionVM` | L5 `page_market._render_x1` | — | — | 🟡 | `⬜ 尚未提供`（M1b 位階說明已接） |
| M16 | 指標明細 16 項（L3） | `SectionVM` | L5 `page_today.build_indicator_tiles`＋readiness | 無 as_of | 七態 | 🟡 | `⬜ 尚未提供` |
| M17 | 原始資料表（L3） | `SectionVM` | L5 `page_market.raw_rows(session, …)` 直讀 session | — | — | 🟡（⛔ 直搬） | `⬜ 尚未提供` |

### §4.2 🎯 標的（`p4_target`）

| # | Field | Canonical | 分類 | Real 模式 |
|---|---|---|---|---|
| T1 | 精選摘要（`pick_summary`） | `fundamental_screener_service.get_ranked_picks`（表單因子＋`pe_map` 連網）＋L5 `page_find` 編排 | 🟡＋SG-04 | `⬜ 尚未提供`＋原因 |
| T2 | W-4 市場位階（`market_regime`） | **同 M1（同一 snapshot）** | ✅ | 同 M1（跨頁一致性測試鎖定） |
| T3 | W-4 Risk Cap | 同 M2 | 🔒 | 同 M2 |
| T4 | 是否需要行動（`no_holding_action`） | 🔒 capability「本頁不產生持股動作；動作權威＝💼 持股」 | 🔒 | 同 FAKE 字樣（`NUI2-TARGET-FAKE-ACTION-TEXT-REAUDIT` 再審：Real 模式沿用、未自創） |
| T5 | 下一步 | 🔒 capability | 🔒 | 同 FAKE |
| T6 | 產業機會 Top 5 | `sector_flow_service.get_sector_flow_view(etf_tickers=None, include_stock_watchlists=False, use_active_selection=False)`（資料）＋L5 `_target_blocks.rank_industries`（排序，DEC-121 Q1=A） | 🟡（排序 PORT） | `⬜ 尚未提供`＋原因 |
| T7 | 候選 Top 10 | 同 T1；或 `forward_test_service`＋`picks.parquet`（每月凍結＝不同語意） | 🟡＋SG-04 | `⬜ 尚未提供`＋原因 |
| T8／T9 | 選股條件／完整表 | L5 `page_find` | 🟡 | `⬜ 尚未提供` |
| T10 | 名稱搜尋 | 無（`FUI-NAME-SEARCH`） | ⬜ | `⬜ 尚未提供` |
| T11 | 搜尋 CTA／模式 | presentation | 🔒 | disabled（真查詢不在本批） |
| T12 | 查詢摘要 | 名稱 L0 `src/config/stock_names`（V-L0-NAME-1）；判型 L5 `_target_blocks.kind_chip_text` | 🟡 | `⬜ 尚未提供`；Real 模式 `queried=False`（未查詢，⛔ 假 ticker） |
| T13 | 6 維：基本面 | `financial_health_engine.analyze_financial_health(api_key="")`（連網） | 🟡 | `⬜ 尚未提供` |
| T14 | 6 維：估值 | `valuation_service.get_pe_name_maps`／`get_stock_dividends`（連網） | 🟡＋SG-08 | `⬜ 尚未提供`；Forward／Fair Value 恆無法產生 |
| T15 | 6 維：籌碼 | `stock_chips_service.get_chips_readout` | 🟡 | `⬜ 尚未提供` |
| T16／T17 | 6 維：趨勢／產業 | 🔒 `⬜ 尚未定義`（DEC-092 Q2） | 🔒 | 同 FAKE FieldVM（測試鎖定） |
| T18 | 6 維：市場環境（`dim_market_env`） | **同 M1（同一 snapshot）** | ✅ | 同 M1；⚠️ Real 模式未查詢 ⇒ Snapshot 區塊不渲染（VM 層一致性仍測） |
| T19 | 加入觀察 CTA | `watchlist_service`（寫入） | 🔒 | disabled |
| T20 | 查一檔 L2（基本面／估值／研究解釋） | 同 T13／T14；研究解釋 Stage G | 🟡／⬜ | `⬜ 尚未提供` |

### §4.3 💼 持股（`p4_hold`）

| # | Field | Canonical | 分類 | Real 模式 |
|---|---|---|---|---|
| H1 | 組合狀態 | `holdings_service.get_holdings`（經 L1 `gsheet_portfolio` 讀 `st.session_state['gsheet_tokens']`）＋`portfolio_binding_service` | ✅C | `⬜ 尚未提供`「需 Google OAuth／Sheet（路徑 C）」 |
| H2 | Risk Cap | 🔒 同 M2 | 🔒 | `⬜ 無法判定` |
| H3 | 目前曝險 | **無來源**（現金／總資產分母；Gate §4.4 X1） | ⬜＋SG-05 | `⬜ 資料未備`「無現金／總資產來源」（契約固定） |
| H4／H5 | 是否需要行動／下一步 | 🔒 B | 🔒 | 待 Aggregator |
| H6 | 🚀 更新持股戰情 | 既有持股更新入口（producer） | 🔒 | disabled |
| H7 | Holdings 表 | `dividend_station_service.get_station_rows`（每檔連網）＋H1 | ✅C＋B | `⬜ 尚未提供` |
| H8 | 🤖 OneBrain 持股摘要 | Stage G | ⬜＋SG-09 | `⬜ 尚未提供` |
| H9／H10 | L2／L3 明細 | L5 `page_hold` builders（⛔ `posture_range`） | 🟡 | `⬜ 尚未提供` |

### §4.4 👤 我的（`p4_me`）

| # | Field | Canonical | 分類 | Real 模式 |
|---|---|---|---|---|
| E1 | 連線狀態／Google | `me_account_service.get_account` | ✅C（讀路徑有寫入副作用，§3） | `⬜ 尚未提供`；`account=None`（⛔ 假裝 signed-in／out） |
| E2 | Sheet（末 6 碼） | `me_account_service.get_sheet_view`（連 Google） | ✅C | `⬜ 尚未提供` |
| E3／E4 | 組合／觀察清單 | `me_account_service.get_sheet_contents`／`portfolio_binding_service.get_active_selection` | ✅C | `⬜ 尚未提供` |
| E5／E6 | 連線異常／下一步 | 由 E1～E4 組出（L5 `page_me` V6 PORT） | 🟡C | `⬜ 尚未提供` |
| E7 | 管理動作（切換 Sheet／選組合／登出／登入） | `me_account_service.bind_sheet／select_*／logout`（寫入） | 🔒 | 單一 disabled「帳戶管理」 |
| E8～E10 | Strategy／Notifications／Display | **未找到**正式 canonical settings contract（兩組皆未窮舉） | ⬜（未驗） | `⬜ 尚未提供` |
| E11 | Decision Digest | `decision_digest_builder`（0 production caller；Stage F） | ⬜＋SG-09 | `⬜ 尚未提供（待 Headless Digest）` |
| E12 | Rule Registry | ✅ L0 `shared/decision_digest_rules.RULE_ID_ALLOWLIST` 等（零 I/O） | ✅（不在本批 2 事實） | `⬜ 尚未提供`（候選，§6） |
| E13 | Data Freshness | `data_registry_summary_service.summarize_data_registry(session)`；`data_cache/metadata.json` 只有 L1 reader | 🟡 | `⬜ 尚未提供` |
| E14 | System Information | `calibration_status_service.get_calibration_status`（組 B：session-free） | ✅（不在本批；組 A 未驗） | `⬜ 尚未提供`（候選，§6） |

### §4.5 計數（以上表列為準；欄位粒度，非窮舉保證）

| 分類 | 數 | 欄位 |
|---|---|---|
| ✅ 本批接（2 個事實 → 5 個落點） | 2 事實 | 台股（M8）；市場位階（M1、M1b、T2、T18） |
| ✅ 有 canonical、零 I/O，但不在本批 | 2 | E12、E14（下一批候選） |
| ✅C 被 OAuth／Sheet 擋 | 6 | H1、H7、E1～E4 |
| 🟡 需先 PORT／只存在 session | 約 22 | M6 M7 M9 M10 M12 M13 M15 M16 M17；T1 T6 T7 T8 T9 T12 T13 T14 T15 T20；H9 H10；E5 E6 E13 |
| 🔒 契約固定 | 約 16 | Risk Cap×3、動作／下一步（📊💼 B、🎯 capability）、CTA 類、趨勢／產業、加入觀察、帳戶管理動作 |
| ⬜ 無 source／定義 | 約 8 | M11、M14、T10、H3、H8、E8～E11 |

---

## §5 語意映射（A2；`src/services/ui2/real_canonical.py` 檔頭同步記載）

### §5.1 台股加權指數

| 輸入 | 呈現 | 依據 |
|---|---|---|
| 讀取丟例外（feed 接住） | Unavailable `🔴 來源目前不可用`＋原因 | §1；CLAUDE.md §1.A-4 灰紅分離 |
| `failed=True` | Unavailable | service 定義「讀取時丟了例外」 |
| `ok=False, failed=False` | Missing `⬜ 資料未取得`＋原因 | service 定義「讀不到」（灰） |
| `is_stale=True` | Stale `⚠ 過期 N 天`（N＝`age_days`；None → `⚠ 可能已過期`） | §2.4 Freshness |
| `is_stale=None` | Stale `⚠ 可能已過期`＋「新鮮度未判定」 | **AI 總管內部判準（可推翻）**：新鮮度未知 ⛔ 當 OK |
| `is_stale=False` | OK（值＝最新收盤，`f"{v:,.2f}"`） | — |
| `ok=True` 但無收盤值／非有限數／`is_stale` 非 bool | **raise**（fail loud） | §1 |
| `upstream_error`／`stale_reason` | 放 detail（原樣，只截長度） | provenance |

### §5.2 市場位階（三處＋L2 共用同一個 `RegimeFact`）

| 輸入 | 呈現 | 依據 |
|---|---|---|
| strict 讀取例外 | Unavailable＋原因（⛔ 吞成「未評估」） | `get_macro_state` strict 語意 |
| `is_loaded=True` | OK＋`REGIME_LABEL[regime]`；as_of `None`＋detail `⬜ 資料日未提供` | 全站統一顯示字；⛔ `cl_ts` 頂替（SG-10） |
| `source=unloaded` | Not Evaluated `⬜ 尚未載入`；L2 detail＝L0 `NOT_LOADED_PENDING_BREADTH_EXPLAIN`（旗標 False；DH-REGIME-NOWARROOM）＋「Real-data Preview 不觸發更新」 | 既有 L0 SSOT |
| `source=unevaluated:breadth_unavailable` | Unable to Determine `⬜ 未評估／資料不足`；L2 detail＝L0 `UNEVALUATED_BREADTH_EXPLAIN` | DEC-074／075 客戶逐字；DEC-124 歸類 |
| 未知 `source`；`is_loaded` 與 `source`／`regime` 矛盾 | **raise** | §1 fail loud |
| `FieldVM.source` | `規則分支 id：<source>（非資料來源）` | 規格：⛔ 偽裝資料來源 |
| `file_error`（strict 下 Risk Cap／舊檔讀壞） | 留在 snapshot、**不呈現**（不影響位階；Risk Cap 恆 ⬜） | 登記 `NUI2-REALFEED-FILE-ERROR-UNSURFACED` |

---

## §6 Stop Gate 候選（命中即停該項；A／B／C＋推薦送客戶；本批**未觸發任何一項**——全部維持 ⬜／disabled）

| SG | 欄位 | 觸發類型 | 現況與推薦（AI 總管；客戶可推翻） |
|---|---|---|---|
| SG-01 | 📊／💼 🚀 更新 CTA（Preview refresh） | 外部取數＋寫 canonical 檔（`risk_cap_state.json`／`macro_state.json`）＋Risk Cap runtime 寫入 | 也是 Preview 出現「已載入」macro 的唯一既有路徑。(a) 維持冷啟動誠實呈現〔**推薦**〕(b) Preview 接 🚀、寫入隔離 state_dir（需客戶裁示）(c) 等 Stage F Canonical Snapshot |
| SG-02 | 📊 利差 | 新資料定義 | 無 canonical 欄（D5）；10Y-2Y／10Y-3M／M1B-M2 三種語意 |
| SG-03 | 📊 PMI／景氣 | 新資料定義（選源／合併卡） | 台灣 PMI（CIER）vs NDC 景氣燈號；session readiness vs `tw_pmi.parquet` 兩條路 |
| SG-04 | 🎯 候選 Top 10／精選摘要 | 新資料定義 | 因子組合無 canonical 定義（UI 表單 vs cron 全因子 vs 每月凍結 picks） |
| SG-05 | 💼 目前曝險 | 新 source | 現金／總資產分母 |
| SG-06 | Risk Cap 數值（三頁） | Risk Cap semantics／numerical activation | 恆 `⬜ 無法判定`；⛔ 由 `get_allocation`／`risk_cap_state.json`／`exposure_limit_pct` 推導 |
| SG-07 | 動作欄、⚡ W-10 舊警示轉接 | System Action semantics／Action Authority | 維持 `⬜ 尚未提供（待 System Action Aggregator）` |
| SG-08 | 🎯 估值 Forward EPS／Fair Value | Forward EPS 新來源 | `grep -rli "forward.eps|forward_eps|fwd_eps" src shared` 0 檔（組 B）；⛔ TTM 冒充 |
| SG-09 | OneBrain／Digest／研究解釋 | runtime | Stage F／G |
| SG-10 | 位階 as_of | 改既有 service 契約／新資料定義 | 契約無 as_of；⛔ `cl_ts` 頂替；擴契約＝改既有 service（Migration §3-7 須客戶 Gate） |
| SG-11 | 👤 E1～E4、💼 H1／H7 | OAuth／credential architecture | 讀路徑寫 `_oauth_state`＋nonce；app_ui2 OAuth bootstrap；Preview redirect URI（🟡 Manual Action）；改用 service account＝credential 架構改變 |
| SG-12 | 📊 五桶／16 燈／關鍵警示 thin L3 | 是否算第二套 | 組 B 讀法：只包同一支 L2 ⇒ 不算新規則；但仍是新 service ⇒ PORT 批前由總管裁定（內部自決；登記） |
| SG-13 | 🎯 候選 Top 10 因子 | 無 canonical 定義 | 同 SG-04（獨立列出供客戶勾選） |

---

## §7 跨頁同一 canonical fact 清單

| Canonical fact | 出現位置 | 本批 | 一致性保證 |
|---|---|---|---|
| 市場位階 | 📊 current_state、📊 L2 位階說明、🎯 W-4 `market_regime`、🎯 6 維 `dim_market_env`（未來 💼 context） | **接** | 同一 `RealFeedSnapshot.regime`；`tests/test_ui2_real_feed.py::test_regime_is_identical_across_pages`（四態）＋checker teeth＋單一呼叫計數 |
| Risk Cap 閘門 | 📊／🎯／💼 context row | 🔒 | 三頁 FieldVM 相等且等於 FAKE（測試鎖定） |
| System Action | 📊 action_needed／next_step；💼 同 | 🔒 | 同一 aggregator-pending FieldVM |
| 台股加權指數 | 📊 卡（本批）；📊 圖 A（未來，同 `TwiiTrendView`）；readiness `taiex`（session，另一路） | 只接卡 | ⚠️ 登記「`taiex`（session readiness）vs `twii_ohlcv.parquet`」同事實兩條路（`NUI2-TWII-TWO-PATHS`） |
| **VIX** | 📊 卡（session `macro_info['vix']`／readiness，更新時抓、3mo）；💼 持股（`dividend_station_service.fetch_vix()`，render 時連網、6mo、無 as_of） | 未接 | ⚠️ 同事實兩條路徑（`NUI2-VIX-TWO-PATHS`）；UI2 接時只能擇一 |
| 帳戶↔持股 | 👤 Google／Sheet 卡；💼「未登入→指向 👤」 | C | 待 C |
| 組合名稱 | 👤 組合卡；💼 組合狀態 | C | 待 C |
| 產業對映 | 🎯 候選表產業欄；🎯 查一檔 chip | 未接 | `target_industry_service`（同一 reader） |

---

## §8 OAuth／Sheet dependency 盤點（只盤點，本批 ⛔ 動）

- **讀寫分離**：L1 `src/data/portfolio/gsheet_portfolio.py` 同模組同時有讀（`list_portfolios`／`load_portfolio`／`read_sheet_title`…）與寫（`save_portfolio`／`save_stock_watchlist`／`add_to_stock_watchlist`／`delete_*`／`create_new_sheet`／`rename_sheet`／`append_forward_test_picks`）；分離靠 **L3 守衛**（`holdings_service` 只讀；組 B 讀測試名）。
- **讀路徑副作用**：`me_account_service.get_account` → `oauth_state.build_login_url` → `get_login_state` 寫 `st.session_state["_oauth_state"]`＋server 端 nonce（實查 `oauth_state.py` `get_login_state`／`build_login_url`）⇒ 違 UI2「session key 只限 `ui2_`」與 no-write；只有 OAuth **未設定**時回 `ACCOUNT_NOT_CONFIGURED` 無副作用。
- **secrets 來源**：`st.secrets['google_oauth']`（亦接受 session 內 in-app 設定）；部署預設 Sheet `st.secrets[PORTFOLIO_SHEET_KEY]`；`oauth_csrf_enforce`／`oauth_silent_reauth`；service account（cron）讀 `os.environ`；Risk Cap 歷史讀取端 `st.secrets['[risk_cap_history_reader]']`。repo 內是否有 secrets 檔：**未驗**。
- **既有 canonical 優先 reuse**：`portfolio_binding_service.get_active_sheet／get_active_selection`（Sheet SSOT，DEC-083 Q6／Q7）、`holdings_service.get_holdings`、`me_account_service.get_account／get_sheet_view／get_sheet_contents`；UI2 ⛔ 直接碰 `oauth_state`（Reuse S13）。Sheet **不是** UI2 私有 DB。
- **nonce** 為 process 記憶體（多副本／重啟失效）；Preview 是另一個 app ⇒ 天然隔離（組 B）。
- **C 需要的人工動作**（🟡 Manual Action Gate，屆時才發）：Preview Cloud App、Secrets、Google OAuth redirect URI。

---

## §9 守衛（加性；不放寬）

- **G2（VM 純度）**：規則與 `_G2_ALLOWED_PROJECT` **一字未改**；掃描範圍＝L0／L3 UI2 全檔**扣除具名** `FEED_FILES=(src/services/ui2/real_feed.py,)`（測試釘死只有這一個檔、且該檔若能過 G2 就不該被豁免）。
  ⚠️ Migration §6 原寫「`_G2_ALLOWED_PROJECT` 須明確擴充並過審」——本批**未擴充** G2 白名單，改以更窄的 G2F 處理（VM 檔不因真 feed 放寬）。
- **G2F（新增）**：只套 `FEED_FILES`；import 白名單＝`shared`、`src.services.ui2`、`src.services.market_twii_view_service`、`src.services.allocation_service`；
  ⛔ streamlit／`src.data`／`src.compute`／Legacy UI／網路／檔案／時鐘、⛔ `session_state`、⛔ producer／寫入名稱（`refresh_macro_now`、`get_allocation`、`register_*`、`apply_*`、`compute_and_lock_risk_cap`、`risk_cap_history_*`、`get_account`、`build_login_url`、`get_holdings`、`save_*`、`write_*`、`delete_*`、`bind_*`、`select_*`、`open`…）；24 項注入 mutation 全紅；純 VM 檔 ⛔ 反向 import feed。
- **G9 補洞（加性）**：UI2 L5／L6 ⛔ 整包傳 `st.session_state`（`dict(st.session_state)`、`fn(st.session_state)`、`f(state=st.session_state)`、`f(**st.session_state)`）與取別名（`s = st.session_state`）；5 項注入 mutation 全紅。
- **capability marker 允許清單**：明確擴充 `src/services/ui2/real_canonical.py`（Real 模式未接線欄位＝`⬜ 尚未提供`＋原因）；cutover 前清零規則不變。
- c3 layering：`real_feed`／`real_canonical` 皆 L3（`src/services/` 前綴）；L3→L3／L0 合法；c3 未改。
- `src/services/__init__.py` eager import（`NUI2-SERVICES-INIT-EAGER`）：本批**只記錄、不修**——Preview 行程 import `src.services.*` 本來就會載入 L1／Legacy L4 模組（只 import、不取數）；real feed 本身零網路由 socket guard 實測。

---

## §10 未驗與限制（誠實揭露）

1. **Preview Cloud 的 CWD 與 `macro_state.json`／`risk_cap_state.json` 是否存在：未驗**（R2；`NUI2-PREVIEW-CLOUD-STATE-FILES`）。本地 sandbox 兩檔皆不存在 ⇒ 位階＝冷啟動。
2. 錯誤字串**未經金鑰遮蔽**（只截長度 300 字）：UI2 守衛 `check_no_oauth_or_sheet` 禁止識別字含 `secrets`（擋到 `scrub_secrets`），本批不放寬該守衛；兩個讀取皆本地檔、不涉憑證（`NUI2-REALFEED-ERROR-SCRUB`）。
3. TWII `is_stale` 由 L1 依「今天」判定 ⇒ 測試以相對斷言（⛔ 寫死值／is_stale）；viewport 證據為量測日（2026-11-03）快照。
4. Real 模式 🎯 查一檔未查詢 ⇒ 6 維 Snapshot（含「市場環境」）**不渲染**；位階一致性在 VM 層驗。
5. 第一屏量測（390×844／1440×900，Streamlit 1.59.2 與 1.56.0）**11/11** 通過，但手機市場頁「今日主要風險後第一區塊距導覽」餘裕 **27.8px**（門檻 1 行行高 24px；AI 總管內部判準）——任何一句 L1 字串再變長即可能不過（Freeze §16.5：縮字句 → 合併一行 → Decision Gate）。
6. 兩份盤點與本整合皆為**單組**；計數非 AST 窮舉；E8～E10、E14、T1／T13～T15 的 I/O 輪廓部分**未驗**。
7. 本批是 **shadow** acceptance：**不得**宣稱 Migration Contract C5（real-data acceptance）通過；C5 依 Cutover 鏈在 C2（含 Aggregator）之後，且 Audit Checklist §9 的「Desktop 真資料／真機、AI Failure」等未做。
