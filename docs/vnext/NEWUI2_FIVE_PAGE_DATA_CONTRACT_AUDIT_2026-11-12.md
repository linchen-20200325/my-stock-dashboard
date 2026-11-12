# NEWUI2 五頁資料契約稽核（A1 欄位契約＋B1 安全面向；docs-only）— 2026-11-12

> **性質**：稽核證據。**不是 SSOT、不是授權**。未修改任何 src／tests／workflow／資料；不接線、不解除任何 Gate、不把研究候選當成核准。
> **基準**：main `7eb48d6c`（本回合 `git fetch` 實取）。引用一律「檔:符號」為主；少數行號為輔，且只對 `7eb48d6c` 成立（3C 文件重整後 BACKLOG 等行號已漂移，見 §5 S14）。
> **授權來源**：客戶「方案 B」Batch 1 授權（客戶 2026-11-12 裁示；原話與編號**見後續 DEC 登錄**，本文不自編 DEC 號、不轉錄原話）。
> **圖例**：**FACT**＝本回合讀碼／讀檔／執行直接確認；**APPROVED**＝文件記載客戶已裁示（轉錄，非本文確認）；**RECOMMENDATION**＝AI 推薦，非裁示；**HOLD**＝客戶裁示維持未授權；**INFERENCE**＝由 FACT 推得、未實測；**NOT VERIFIED**＝未驗，不得當前提。
> **稽核分類**：READY／BLOCKED／NOT VERIFIED **僅為本文的稽核分類**，**不是**正式 Data State enum（正式資料語意只有 `shared/ui2_contract/models.py::FieldState` 的五態，DEC-124；`tests/test_ui2_guards.py::test_dec124_data_semantics_are_exactly_the_five` 釘住）。READY＝接線與資料契約面成立且有守衛，**不含**授權條款（全域前提：TWSE／TPEX／data.gov.tw／Yahoo 授權原文 NOT VERIFIED，FinMind 僅 PARTIALLY VERIFIED，故**沒有任何欄位是 license-verified**）；BLOCKED＝至少一個未關閉的 Gate／缺 L3／缺定義；NOT VERIFIED＝缺證據。
> **單組聲明**：本文由單一文件組整理 5 份單組調查並自行重核關鍵事實（§10），**未經第二組獨立複驗**（`CLAUDE.md` §-2 規則 6）。全稱句只能當**待驗事項**，不得作為後續動作前提，不得寫進 commit／PR 當已完成事實。**非作者獨立 QA：待做。**

---

## 0. 結論先行

| # | 結論 | 標籤 |
|---|---|---|
| 1 | **預設路徑（無 `?ui2_dev=1`）只到 FAKE 冷啟動，0 個真值。** Real feed 只能從開發面 selectbox 選到；`app.py` 對 UI2 的引用為 0 | FACT（§10 V1） |
| 2 | **REAL 軸帶真值的畫面欄位只有 2 個**：台股卡（收盤）與 20 根日 K，兩者都是同一份 `data_cache/twii_ohlcv.parquet`（同一 service 讀兩次）。其餘全是 `⬜ 尚未提供` 或固定占位 | FACT（§10 V2） |
| 3 | **市場位階雖已接線，但在 UI2 獨立 session 結構上恆為「⬜ 尚未載入」**：`get_macro_regime` 只讀 `st.session_state['warroom_summary']`，其生產者全在 Legacy；`macro_state.json`／`risk_cap_state.json` 不在 git；`BREADTH_PROXY_SCORING_ENABLED=False`。本沙箱實測回 `unloaded` | FACT（§10 V2）；部署端 NOT VERIFIED |
| 4 | **「市場資金與籌碼」區塊在 UI2 的 VM 契約中不存在。** 融資 L3（`margin_fact_service`）與板塊 L3（`sector_flow_fact_service`）在 `src/ui2`、`src/services/ui2`、`shared/ui2_contract` 引用數＝0；大盤外資**沒有** L3；三大法人（外資／投信／自營）UI2 無入口 | FACT（§10 V3） |
| 5 | **🗂 資料頁整頁是固定空殼且不讀 snapshot；💼 持股頁沒有任何資料路徑**（資料日、判得出是寫死字樣，持股表 `hold_table_html()` 無參數） | FACT（§2.4、§2.5） |
| 6 | **跨層口徑問題已有實證**：`finmind_inst.parquet` 同欄兩種 `source` 標籤（4920／19 列）；板塊「外資分項」與 FinMind「大盤外資」同日不等（37 共同日，中位絕對差 55.4 億，最大 239.6 億）；板塊 stale 4 日 vs 融資／外資／TWII 7 日；成交量備援會「猜單位」（**僅 INFERENCE，未實際觸發**） | FACT／INFERENCE（§4、§10 V4／V5／V8） |
| 7 | **新鮮度判定偏弱**：日曆天>7 才過期、`date.today()` 伺服器時區、無交易日曆；as_of 2026-11-09 時 `age_days=3`、`is_stale=False`，卡片無過期提示 | FACT（§10 V7） |
| 8 | **B1：未發現「契約內、可重現、不涉及新設計決策」的缺陷。** 另有 Visual Gate 候選 VG1／VG2、文案漂移（「只接 2 項真資料」）、GUARD-GAP G1／G2；Real 軸瀏覽器量測因環境限制**未做** | FACT／NOT VERIFIED（§7） |
| 9 | **所有 Gate 維持 HOLD／未授權**（§6）。本文不暗示任何 Gate 已解除、任何接線已授權 | FACT |

---

## 1. 範圍與方法

- 五頁＝`src/ui2/views/{market,target,hold,me,data}.py`（📊 市場、🎯 標的、💼 持股、👤 我的、🗂 資料）。
- 資料模式用語：**FAKE**＝`preview_feed.get_preview_page_vm`→`scenarios.fake_canonical`（值以 `FAKE` 標示）；**REAL**＝`real_feed.read_real_snapshot`→`real_canonical`（只有 3 個事實：台股卡、日 K、位階）；**STATIC／FIXED**＝`html.py` 或契約寫死的字樣／槽；**NP**＝NOT_PROVIDED＝`⬜ 尚未提供` capability marker（兩 feed 同）。
- 來源：5 份單組調查（程式追溯、文件契約、反向缺口、市場契約、UI2 安全）＋本回合重核（§10）。**欄位數量（45／46 等）屬人工建模計數，本回合未重算**，僅作量級參考。
- 渲染白名單：`src/ui2/views/_page.py::SHOWN_FOLDS`＝`(p4_target,conditions)`、`(p4_me,digest)`、`(p4_me,registry)` 三個收合區；其餘 L2／L3 區塊在 VM 但**不渲染**（FACT，已讀碼）。`hold.py` 不呼叫 `render_cards`（FACT，grep）。

---

## 2. 五頁欄位對應表

**欄位合併規則**（欄數過多，為可讀性所做，未丟資訊）：① 「page」改為各小節標題；② 「現有欄位與單位」併入「canonical source」欄；③ 同質 NOT_PROVIDED 欄位若 canonical／producer／Gate 完全相同，合併為一列並於「UI field」列舉；④ 「Coverage／PIT／License」欄的全域前提（上述授權未驗）不逐列重複，僅記該列特有者；⑤ 測試欄只列代表性測試（檔::函式，均已 grep 確認存在），**不證明目前綠燈**。FAKE 值一律標示 FAKE，不在表內當作資料。

表頭：`#`｜section／UI field｜資料模式｜canonical source／欄位單位｜producer→consumer｜資料日／抓取日／發布時點資格｜缺值／過期語意｜Cov／PIT／Lic｜UI2／Digest｜Gate｜測試｜分類

### 2.1 📊 市場（`p4_market`）

| # | section／UI field | 模式 | canonical／欄位單位 | producer→consumer | 日期／發布資格 | 缺值／過期語意 | Cov／PIT／Lic | UI2／Digest | Gate | 測試 | 分類 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| M-01 | 頂列 Active Sheet／帳號 | STATIC | 無 | `html.py::top_status_row_html` 寫死 | — | 固定 `⬜ 尚未提供`（不讀 `ui2_account`／query） | — | UI2 是；Digest 否 | `NUI2-AUTH-CONTRACT-GATE` | `test_ui2_batch2.py::test_w1_top_row_is_fixed_placeholder_not_login` | BLOCKED（刻意固定占位） |
| M-02 | 資料模式 banner | STATIC（依 `is_fake`） | `text.py::PREVIEW_BANNER_TEXT`／`REAL_PREVIEW_BANNER_*` | `vm_common._banner_for`→`html.banner_html` | — | — | — | UI2 是 | 無 | `test_ui2_real_feed.py::test_real_scenario_axis_is_separate_from_fake_scenarios` | READY |
| M-03 | 主 CTA「🚀 更新今日戰情」 | STATIC | 無 | `vm_common.cta_from_spec`（`enabled=False` 寫死） | — | disabled＋原因句 | — | UI2 是 | SG-01 | `test_ui2_real_feed.py::test_real_vms_create_no_actions_and_no_forbidden_terms` | BLOCKED（刻意） |
| M-04 | 今日結論 | FAKE／REAL=NP | 無 producer（文件稱 L0 `shared/market_conclusion.build_market_conclusion` 可 reuse；**程式未接，可否直接接 NOT VERIFIED**） | `real_canonical._market` | — | NP | — | 否 | `NUI2-PORT-CONCLUSION-CLAUSES`、`NUI2-CONCLUSION-REAL-FEED` | `test_ui2_batch3.py`（結論句型） | BLOCKED |
| M-05 | 現在狀態＝市場位階 | FAKE（`震盪` 寫死）／**REAL 已接線** | `RegimeFact(regime,light,source,is_loaded)`；類別值，**無 as_of、無單位** | `allocation_service.get_macro_regime(strict=True, require_valid_risk_cap=True)`→`macro_state_locker.get_macro_state`→`real_feed._read_regime`→`real_canonical.regime_spec` | **契約無資料日**，畫面寫 `⬜ 資料日未提供`；禁以 `cl_ts` 頂替（SG-10） | `is_loaded=True`→值；`unloaded`→`not_evaluated ⬜ 尚未載入`；`unevaluated:breadth_unavailable`→`undeterminable`；讀取例外→紅 | PIT 無；`macro_state.json`／`risk_cap_state.json` **不在 git**（`.gitignore` 列出，`git ls-files`＝0） | UI2 是；Digest 走同函式但 **Digest 0 production caller** | 無（已接）；`NUI2-REALFEED-WARROOM-CONTRACT-INTEGRATION`（條件式）；`NUI2-PREVIEW-CLOUD-STATE-FILES`（NOT VERIFIED） | `test_ui2_real_feed.py::test_regime_unloaded_is_not_evaluated_with_the_l0_explanation`、`::test_regime_is_identical_across_pages` | READY（接線）但**實值語意＝冷啟動居多**；Cloud NOT VERIFIED |
| M-06 | Risk Cap（context row） | FIXED（兩 feed 同） | 不讀任何 producer；`RegimeFact` 欄位集被測試鎖住不含 exposure | `real_canonical._risk_cap_row` | — | `undeterminable ⬜ 無法判定` | — | UI2 固定；Digest 另有 `risk_cap` 路徑（兩邊有意不同） | SG-06／RC-VISIBILITY／C2b／DEC-141 Q5 | `::test_regime_fact_never_carries_risk_cap_fields`、`::test_risk_cap_stays_undeterminable_even_if_the_contract_returns_a_cap` | BLOCKED（刻意不接） |
| M-07 | 是否需行動／下一步 | NP（FAKE cold 的「下一步」例外，見 §7 N2） | 無 | `vm_common.aggregator_pending_field` | — | `⬜ 尚未提供（待系統動作整合）` | — | 否 | `NUI2-AGGREGATOR-IMPL`（blocked-on-customer） | `::test_risk_cap_and_action_fields_are_identical_across_pages_and_feeds` | BLOCKED |
| M-08 | 今日主要風險 | FAKE／REAL=NP | 無 producer | `real_canonical._market` | — | NP；FAKE cold 為 `⬜ 尚未載入，請按更新` | — | 否 | `NUI2-PORT-MAIN-RISK` | `test_ui2_batch3.py`（退化句） | BLOCKED |
| M-09 | 台股走勢主圖（20 根日 K） | FAKE=空槽；**REAL 已接線** | `data_cache/twii_ohlcv.parquet` 欄 open／high／low／close（指數點）；OHLC 契約 `shared/twii_ohlc_contract.validate_ohlc_window` | `market_twii_view_service.get_twii_trend_view(20, with_ohlc=True)`→`macro_cache_reader.load_twii_ohlc`→`real_feed._read_twii_kbar`→`real_canonical.kbar_chart_spec`→`html.kbar_chart_html` | 資料日＝parquet `date` 最大值；`fetched_at` 僅供「已收盤」判定、不顯示；Yahoo EOD | `ok=False`→灰；`ohlc_ok=False`→灰；契約違反／與卡片不同源→紅；不足 20 根照實少畫；stale 與卡片同字樣 | 來源 Yahoo `^TWII`（授權 NOT VERIFIED）；無 `release_date` | UI2 是；Digest 否 | 無擋接線；條件式 `I1140-OHLC-GUARD`（with_ohlc 路徑未套卡片價格守衛） | `tests/test_ui2_twii_kbar.py::test_every_contract_violation_makes_only_the_chart_red`、`::test_card_and_chart_must_be_the_same_snapshot_or_the_chart_is_red` | READY（限 20 根；MA／量／更長視窗 BLOCKED，需 Visual Gate） |
| M-10 | 核心卡：台股（`twii`） | FAKE（`12,345.67`）／**REAL 已接線** | 同上，欄 `close`；顯示 `f"{x:,.2f}"`，**卡片不標單位** | `get_trend_view(1)`→`real_feed._read_twii`→`real_canonical.twii_card_spec` | as_of＝parquet 末列；`source` 字樣為常數 `TWII_SOURCE_TEXT`（**非** parquet 的 `source` 欄、無 `fetched_at`） | `ok=False`→Missing；`failed`→紅；`is_stale=True`→`⚠ 過期 N 天`；`None`→`⚠ 可能已過期`；close≤0／非有限／`age_days<0`→契約違反紅 | 同上 | UI2 是；**Digest market 段不含 TWII** | 無（卡片層） | `::test_twii_parquet_is_the_real_local_cache_and_feed_reads_it_without_hardcoding`、`::test_twii_unknown_freshness_is_never_ok`、`::test_twii_broken_contract_is_loud_and_isolated` | READY；新鮮度判定偏弱（§4 X-07） |
| M-11 | 核心卡：VIX | FAKE／REAL=NP | 候選兩條：`macro_snapshot.fetch_vix_block`（yfinance 直連，無 as_of）／session `macro_info['vix']`；兩者皆未接 | `real_canonical` `_not_provided`（`此項目尚未開放`） | DEC-070「只用已完成收盤」僅語意裁示，程式未實作（`VN1-PG-VIX-ASOF`） | NP | Yahoo 授權 NOT VERIFIED | 否 | 客戶 D2＝維持空槽（轉錄）；`NUI2-VIX-TWO-PATHS` | `::test_every_unwired_real_field_states_its_reason` | BLOCKED |
| M-12 | 核心卡：US 10Y | FAKE／REAL=NP | 候選 A：`macro_snapshot.fetch_us10y_block`（FRED 公開 `fredgraph.csv` DGS10；**函式簽名有 `fred_api_key`，函式體內未使用**，§10 V9）；候選 B：session；Yahoo `^TNX` 為國際趨勢另一口徑 | 同上 | 無落地檔；FRED 當日值發布時刻 NOT VERIFIED | NP | FRED 授權 NOT VERIFIED | 否 | D1＝FRED DGS10 **僅口徑**（APPROVED 轉錄，不授權實作） | 同上 | BLOCKED（口徑已定、實作未授權） |
| M-13 | 核心卡：利差 | FAKE／REAL=NP | 無 canonical 欄；三種定義（10Y-2Y／10Y-3M／M1B-M2）未擇 | — | — | NP | — | 否 | D3＝維持空槽；`NUI2-REALFEED-SG-02-SPREAD-DEF` | 同上 | BLOCKED（業務定義缺口，非接線缺口） |
| M-14 | 核心卡：DXY | FAKE／REAL=NP | 顯示路徑 `macro_alert._yf_latest`→`DX-Y.NYB`；舊戰情備援鏈 `DX-Y.NYB→DX=F→UUP` 可能落到 ETF | — | — | NP | — | 否 | 未授權；推薦 C＝維持空槽（RECOMMENDATION） | 同上 | BLOCKED |
| M-15 | 核心卡：PMI／景氣 | FAKE／REAL=NP | `tw_pmi.parquet`（`is_proxy: true`，`CACHE_DATASET_CADENCE` 未登錄→必回 stale）vs 景氣燈號，兩者意義不同 | — | — | NP | — | 否 | D4＝維持空槽；`NUI2-REALFEED-SG-03-PMI-DEF`；DEC-155（proxy PMI 不得為正式訊號） | 同上 | BLOCKED |
| M-16 | 🤖 OneBrain Outlook | FAKE／REAL=NP | 程式內 0 個 OneBrain producer | `real_canonical` `_R_STAGE_G` | — | NP | — | 否 | `FUI-STAGE-G`、SG-09 | `test_ui2_p2_primary_slot.py::test_onebrain_content_is_unchanged_only_its_position_moves` | BLOCKED |
| M-17 | （不渲染）為什麼／指標明細／原始資料表 | VM 有、畫面無 | REAL `why.regime_explain`（位階完整說明）已接線，其餘 NP | `real_canonical._market` | — | 不渲染（`SHOWN_FOLDS` 排除） | — | 否 | `NUI2-PORT-READINESS-L3`、`NUI2-PORT-INDICATOR-TILES` | `test_ui2_p3_evidence_preservation.py::test_render_policy_guard_has_teeth` | BLOCKED |
| M-18 | **市場資金與籌碼：融資餘額** | **不在 VM／畫面** | `finmind_margin.parquet` 欄 `margin_balance`（元）→L3 `margin_fact_service.get_margin_fact`（億）；本回合讀 L3：`OK`、5399.15741 億、as_of 2026-11-09、非 stale、`age_days=3` | L3 存在，**0 production caller**（§10 V3） | 無 `release_date`；`fetched_at` 對多數列為 bootstrap 單一時點（文件側 FACT，本回合未重算），不可作可得日 | L3 四態；缺值≠0（有測試） | FinMind PARTIALLY（禁再散布原始資料、須標「FinMind」）；DG-PIT、DG-LIC | UI2 否；Digest 否 | `I1144-WIRING-GATE`、DG-SCOPE、DG-PIT、DG-LIC；`I1140-MARGIN-SOURCE-TEXT`（常數含「全市場」字樣，見 §4 X-12）；`I1140-MARGIN-UNIT-MIX`（條件式） | `tests/test_margin_fact_service.py::test_stale_boundary_7_days_not_stale_8_days_stale`、`::test_scope_guard_not_wired_to_ui_or_real_feed` | BLOCKED（資料層 READY；接線 HOLD） |
| M-19 | **市場資金與籌碼：板塊資金（衍生聚合）** | **不在 VM／畫面** | `data_cache/sector_flow/daily_net.parquet`（億；張×1000×收盤）→L3 `sector_flow_fact_service.get_sector_flow_fact`；本回合讀 L3：41／38／3、合計 −920.24812237 億、`complete`、非 stale | L3 存在，**0 production caller** | 視窗＝最新交易日；無 `release_date`；歷史列用回補當下的產業對映（文件側） | `complete` 只代表來源旗標完整、**不是**覆蓋率；缺價剔除股數 L3 不外露（§4 X-03） | TWSE／TPEX 授權 NOT VERIFIED；DG-COV；DG-PIT | UI2 否；Digest 否 | `I1144-WIRING-GATE`、`I1140-COVERAGE-MIN`、DG-PIT、DG-LIC、DG-SCOPE | `tests/test_sector_flow_fact_service.py::test_real_data_cache_once`、`::test_no_market_wide_or_forbidden_fields` | BLOCKED |
| M-20 | **市場資金與籌碼：大盤外資淨買賣超（僅外資）** | **不在 VM／畫面** | `finmind_inst.parquet` 欄 `foreign_buy`（億）；**沒有專用 L3**（L1 僅 `macro_cache_reader.load_extreme_risk_legs` 吐 5 日合計） | — | 同上 | — | 同上＋`source` 標籤斷點（§4 X-02） | 否 | 外資 L3 **未授權、另案**（DEC-164 G-9 轉錄）；`I1144-WIRING-GATE` | 無（缺口，見 §8） | BLOCKED |
| M-21 | 三大法人（外資／投信／自營）單日；國際趨勢（DJI／IXIC／SOX／US10Y／DXY）；台股成交量 | **不在 VM／畫面** | 法人：舊路徑 TWSE BFI82U（session）；國際趨勢：舊 `_market_blocks.intl_series`，**無乾淨 L3**；成交量：`TwiiTrendView` 不含 volume | — | 國際趨勢無 freshness 規則；成交量欄稀疏（最近 40 列中 27 列 NaN，§10 V7） | — | 授權 NOT VERIFIED | 否 | 無授權路徑（G2F 禁讀 session）；成交量需 L3＋全 0／全空隱藏（`CLAUDE.md` §1.A） | — | BLOCKED |

### 2.2 🎯 標的（`p4_target`）

| # | section／UI field | 模式 | canonical／單位 | producer→consumer | 日期／資格 | 缺值／過期語意 | Cov／PIT／Lic | UI2／Digest | Gate | 測試 | 分類 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| T-01 | 模式切換（市場精選／即時查一檔） | UI 狀態 | `ui2_target_mode`（純 UI） | `views/target.py` | — | — | — | UI2 是 | 無 | `test_ui2_batch3.py::test_modes_are_never_fully_expanded_together` | READY（結構，非資料） |
| T-02 | 搜尋框／CTA「查詢」；名稱搜尋提示 | STATIC，disabled；名稱搜尋 NP | 無（任何輸入都不查詢） | `html.search_html` | — | 原因句「尚未開放查詢」 | 單檔腿皆需網路＋FinMind token／quota（文件側） | 否 | TGT-01；啟用需客戶 Gate＋獨立 G2F 擴充＋負向測試 | `::test_search_box_and_cta_present_in_both_modes_and_not_actionable` | BLOCKED |
| T-03 | 現在狀態（精選摘要） | FAKE／REAL=NP | 文件稱 `fundamental_screener_service.get_ranked_picks`；**程式未接** | `real_canonical._target` | 財報 as_of＝`民國{y}Q{s}`；公告日對齊 NOT VERIFIED | NP | MOPS 條款未查 | 否 | SG-04／SG-13（因子組合無 canonical 定義）、`I1144-WIRING-GATE` | `::test_every_unwired_real_field_states_its_reason` | BLOCKED |
| T-04 | 市場位階（W-4 context 一行） | FAKE／**REAL 已接線**（同 M-05 同一次 snapshot） | 同 M-05 | 同 M-05 | 同 M-05 | 同 M-05；`ctxline_html` 以 Neutral chip 畫，狀態只靠文字（Wireframes §9 已核准） | 同 M-05 | 同 M-05 | 同 M-05 | `test_ui2_batch3.py::test_target_market_regime_follows_the_same_market_context` | READY（恆未載入，同 M-05） |
| T-05 | Risk Cap／是否需行動／下一步 | FIXED／NP | 同 M-06／M-07；「動作權威＝💼 持股」 | 同上 | — | 同上 | — | 否 | SG-06、`NUI2-AGGREGATOR-IMPL` | 同 M | BLOCKED |
| T-06 | 精選卡：產業機會 Top 5 | FAKE／REAL=NP | 候選 L3 A：`sector_flow_service.get_sector_flow_view(strict=True)`（固定三參數＝純本地讀檔）；候選 L3 B：`sector_flow_fact_service`（**兩個板塊 L3 並存，無擇一規則**，§5 C7）；排序在 L5 `rank_industries` | 未接 | `observation_date` 嚴格 YYYY-MM-DD；stale＞4 日曆日 | NP | `ticker_sector.json` 個股級對照落在公開 repo | 否 | `NUI2-PORT-INDUSTRY-RANK`、DG-LIC、`I1144-DATA-STORAGE-DECISION` | 同上 | BLOCKED |
| T-07 | 精選卡：候選 Top 10 | FAKE／REAL=NP | `get_ranked_picks(auto_fetch=False)`；僅 `eps_high`／`trend` 兩因子可無網路；`eps_high` 為單季非 TTM | 未接 | 同 T-03 | NP | — | 否 | SG-04／SG-13 | 同上 | BLOCKED（技術上可重用≠業務定義已裁，§5 C8） |
| T-08 | 選股條件（唯一在 🎯 渲染的收合區） | NP | 無 | `real_canonical._target` | — | expander 內為 NP | — | 否 | 同 T-07 | `test_ui2_p3_evidence_preservation.py` | BLOCKED |
| T-09 | 查一檔：結果頭、基本面、估值、籌碼 | FAKE（`FAKE-0001`）／REAL=NP（`queried=False`） | `fetch_metrics`、`get_financial_statements`、`get_chips_readout`（皆連網） | 未接 | — | REAL 只畫灰說明「即時查一檔尚未開放」 | FinMind／MOPS | 否 | SG-08（Forward EPS／Fair Value 無來源）；個別資料契約 Gate | `test_ui2_batch3.py::test_fake_lookup_result_is_labelled_fake_and_has_no_real_ticker` | BLOCKED |
| T-10 | 查一檔：趨勢、產業 | FIXED（`⬜ 尚未定義`） | 無定義（DEC-092 Q2） | — | — | `not_evaluated` | — | 否 | 業務定義缺口 | 同上 | BLOCKED |
| T-11 | 查一檔：市場環境 | FAKE／REAL 已接線但 `queried=False` 不渲染 | 同 M-05 | — | — | 同 M-05 | — | — | 同 M-05 | — | READY（VM 有、畫面無） |
| T-12 | 加入觀察（disabled）＋隔離說明 | STATIC | 寫 Google Sheet（`watchlist_service`）被 G2F 禁 | — | — | disabled | — | 否 | OAuth／Sheet Gate（永不無 Gate 接線） | `::test_lookup_writes_only_ui2_prefixed_session_state` | BLOCKED |

### 2.3 💼 持股（`p4_hold`）

| # | section／UI field | 模式 | canonical／單位 | producer→consumer | 日期／資格 | 缺值／過期語意 | Cov／PIT／Lic | UI2／Digest | Gate | 測試 | 分類 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| H-01 | 組合狀態行：組合名稱／檔數 | FAKE／REAL=NP | 文件稱 `holdings_service.get_holdings`→`gsheet_portfolio`；被 G2F 禁；程式 0 個 holdings producer | `real_canonical._hold` | 使用者手填，無單一資料日 | NP（FAKE loaded 顯示「FAKE 組合 · 12 檔」但下方持股表為空槽） | Google Sheet（使用者資產） | 否 | `NUI2-ME-ACCOUNT-REAL-GATE`、`NUI2-AUTH-CONTRACT-GATE`、G-F2、G-F6 | `tests/test_ui2_hold_w11_batch1.py::test_hold_layout_contract_all_states` | BLOCKED |
| H-02 | 組合狀態行：資料日、判得出 | **STATIC，無 VM 欄位** | 無 | `html.hold_status_html` 寫死 `⬜ 資料日未提供`／`⬜ 尚未提供` | — | 固定 | — | 否 | 接真資料需先改 L0 VM 契約＋html（現契約沒有承載位置） | 同上 | BLOCKED |
| H-03 | Risk Cap／目前曝險 | FIXED（Risk Cap `無法判定`；曝險 `⬜ 資料未備`，「無現金／總資產來源」） | 無 producer；舊 UI 也沒有（Sheet 表頭無現金／總資產） | `real_canonical._risk_cap_row`／`_hold` | — | Missing／Undeterminable | — | 否 | SG-05、SG-06、RC-VISIBILITY、DEC-141 Q5 | `test_ui2_real_feed.py::test_risk_cap_and_action_fields_are_identical_across_pages_and_feeds` | BLOCKED（資料不存在，非 UI 缺口） |
| H-04 | 今日需處理（單行） | NP | 無 | `vm_common.aggregator_pending_field` | — | `⬜ 尚未提供（待系統動作整合）` | — | 否 | `NUI2-AGGREGATOR-IMPL` | `test_ui2_hold_w11_batch1.py::test_mutations_action_row` | BLOCKED |
| H-05 | 主 CTA「🚀 更新持股戰情」 | STATIC disabled（「需登入後才能讀取持股」） | — | — | — | disabled | — | 否 | 登入 Gate | `test_ui2_hold_header.py::test_anchors_and_cta_preserved` | BLOCKED |
| H-06 | 建議持股水位空槽；產業曝險／集中度空槽 | STATIC | 無（SPEC 文字 `text.py::HOLD_PRIMARY_SPEC` 宣告單位 %）；舊持股頁無對應，個股組合頁有（等權、無張數） | `html.hold_body_html` | — | 固定 | — | 否 | 客戶 Gate（資料來源與等權假設）；HD-11 | `::test_css_geometry_contract` | BLOCKED |
| H-07 | OneBrain 持股摘要 | NP | 無 producer | `real_canonical._hold` | — | NP | — | 否 | `FUI-STAGE-G` | 同上 | BLOCKED |
| H-08 | 持股表（8 欄表頭＋原因句） | STATIC；`hold_table_html()` **無參數** | 無資料路徑；VM 的 `holdings_table` 卡與 `next_step` **在 VM 但 view 不渲染** | `html.hold_table_html` | — | 不畫假列、不畫「0 檔」 | — | 否 | 同 H-01；逐檔現價另需連網行情（價格新鮮度逐源未追） | `::test_vm_still_carries_next_step_and_holdings_card` | BLOCKED |

### 2.4 👤 我的（`p4_me`）

| # | section／UI field | 模式 | canonical／單位 | producer→consumer | 日期／資格 | 缺值／過期語意 | Cov／PIT／Lic | UI2／Digest | Gate | 測試 | 分類 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| U-01 | 連線狀態／異常／下一步 | FAKE（`Google 已登入（FAKE 帳號）`）／REAL=NP | 文件稱 `me_account_service.get_account`（讀路徑會寫 `_oauth_state`＋nonce，被禁）；Real 軸 `account` 刻意為 None | `real_canonical._me` | — | NP；FAKE unavailable→紅 | — | 否 | SG-11、`NUI2-AUTH-CONTRACT-GATE`、`NUI2-ME-ACCOUNT-REAL-GATE` | `test_ui2_real_feed.py::test_real_me_page_does_not_pretend_to_know_the_account` | BLOCKED |
| U-02 | 帳戶動作列（切換 Sheet／選組合／觀察清單／登出） | FAKE only（REAL 不畫） | 無 | `html.account_actions_html`（全 disabled） | — | disabled | — | 否 | 同上 | `test_ui2_batch3.py::test_me_signed_out_signed_in_unavailable_semantics_and_axes` | BLOCKED |
| U-03 | 4 卡：Google／Sheet／組合／觀察清單 | FAKE／REAL=NP（`需登入並讀取 Sheet，目前尚未開放`） | 文件稱 `portfolio_binding_service.get_active_selection` | — | — | NP；FAKE signed_out→Missing | — | 否 | 同上 | 同上 | BLOCKED |
| U-04 | 一般設定（Strategy／Notifications／Display） | NP（兩 feed 同） | 未找到正式 canonical settings contract | — | — | NP | — | 否 | 無 ID；**NOT VERIFIED**（兩組皆未窮舉） | `::test_every_unwired_real_field_states_its_reason` | NOT VERIFIED |
| U-05 | Audit：Decision Digest（收合，白名單） | NP | `src/services/decision_digest_builder.py` 存在（A2 已完成，PR #1146），**非測試、非 digest 自家檔 0 個 import** | — | — | NP | — | **Digest 0 production caller** | G-F4／G-F5、Stage F | `test_ui2_p3_evidence_preservation.py` | BLOCKED |
| U-06 | Audit：Rule Registry（收合，白名單） | NP | 候選 L0 `RULE_ID_ALLOWLIST`（零 I/O）；`calibration_status_service`（文件側提出、未驗） | — | — | NP | — | 否 | `NUI2-REALFEED-NEXT-SESSIONFREE`（候選，§-1 無指派不動工） | 同上 | NOT VERIFIED |
| U-07 | （不渲染）Data Freshness／System Information | VM 有、畫面無 | — | `real_canonical._me` | — | 不渲染（不在 `SHOWN_FOLDS`） | — | 否 | 同 §2.5 | — | BLOCKED |

### 2.5 🗂 資料（`p4_data`）

| # | section／UI field | 模式 | canonical／單位 | producer→consumer | 日期／資格 | 缺值／過期語意 | Cov／PIT／Lic | UI2／Digest | Gate | 測試 | 分類 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| D-01 | 資料健康度／是否需行動／下一步／CTA「查看資料健康度」 | NP／STATIC disabled（兩 feed **共用同一份**固定內容） | `src/services/ui2/data_page.py::data_page_canonical`；`real_canonical._data` **不讀 snapshot** | — | 文字「不顯示任何來源狀態與資料日」 | NP | 新欄／分母須先 Data Contract Gate；不可用 cron 時刻冒充觀測日 | 否 | `NUI2-P6-*` 線框決策；DEC-146 第一批僅空殼 | `test_ui2_guards.py`（`data_page.py` 在掃描清單，逐項未驗） | BLOCKED |
| D-02 | 資料來源與連線：來源健康度／資料日／Active Sheet | NP | 舊 `data_registry_summary_service.summarize_data_registry`（session）；`data_cache/metadata.json` 已有 `fetch_outcome`／`last_error`，**UI2 未讀** | — | — | NP；與殼頂列 Active Sheet 重複承載同一件事 | — | 否 | 同上 | 同上 | BLOCKED |

> **後果（FACT）**：REAL 已掌握 TWII 的 as_of／stale／upstream（M-10），🗂 頁仍全為空殼；「Data Freshness」又被 `SHOWN_FOLDS` 排除 → **畫面上沒有任何總覽新鮮度的位置**。

---

## 3. 舊 UI 能力承接缺口（反向視角）

> **「舊 UI 有」≠「UI2 資料可用」。** 「舊 UI」＝Legacy New UI（`app.py` 預設路由，`src/ui/views/**`）為主、Old UI（`?legacy=1`）為輔。「舊 UI 仍可用」只確認程式路徑存在，**未實機開頁**（INFERENCE 層級）。UI2 目前可合法接線的現成 L3 事實層只有 `margin_fact_service`、`sector_flow_fact_service` 兩個且 0 caller；法人、VIX、US10Y、DXY、國際指數**沒有**對應唯讀 L3。**缺口大宗是「沒有合格 L3／定義」，不是「沒人接」。**

### 3.1 有效缺口 17 項（舊 UI 有、UI2 無）

| ID | 頁 | 舊 UI 能力 | 舊取數（檔:符號） | UI2 現況與障礙 |
|---|---|---|---|---|
| G03 | 📊 | MA5／60／120／200 參考線 | `_market_blocks.MA_REFERENCE_SPECS`；值來自 `market_strategy.get_market_assessment`（live、寫 session） | 日 K 無 MA；補 MA 須走 parquet 同源計算，**不得**重用上述 live 函式 |
| G04 | 📊 | 市場位階 | `page_today.get_macro_regime` | **名義已承接、實質不可用**（§0-3） |
| G06 | 📊 | 16 燈／五桶風險摘要／主要風險 | `page_market.calc_traffic_light`、`page_today.compute_five_bucket_summary` | 五桶需 session 的 `macro_info`／`cl_data`；無合法唯讀 L3 |
| G07 | 📊 | VIX／US10Y／利差／DXY／PMI 卡 | `macro_snapshot.fetch_vix_block`／`fetch_us10y_block` 等 | 五卡全 NP；接線前須先解 §4 X-04～X-06 |
| G08 | 📊 | 國際趨勢小倍數 | `_market_blocks.INTL_GROUPS`；`daily_checklist.INTL_MAP`（**無 SPX、無 NDX**；NDX 全 repo 0 命中，客戶口語的 NDX 在 repo 實為 `^IXIC`） | 無落地檔、無唯讀 L3 |
| G10 | 📊 | 大盤籌碼：外資／投信／自營、融資、PCR、期貨 | `page_market._render_x8`、`daily_data_fetchers.fetch_institutional`／`fetch_margin_balance` | 無；融資／板塊 L3 未接；**法人無 UI2 fact service** |
| G11 | 📊 | 今日結論句 | `page_market.build_market_conclusion` | 依賴 Aggregator／位階，與 G04 連動 |
| G14 | 🎯 | 產業機會 Top 5（`x_yi`＝近 5 日累計） | `page_find.get_sector_flow_view` | `industry_top` NP；候選 L3 的視窗是**最新單日**，與舊 UI 的 5 日累計**不是同一指標**，接線時不可同名 |
| G15 | 🎯 | 候選 Top N／完整排名＋CSV | `fundamental_screener_service.get_ranked_picks` | NP；需連網與 FinMind 快照 |
| G16 | 🎯 | 缺貨／RS 領先／跨季轉強 | `page_find.run_shortage_scan` 等 | RS 領先以 live `^TWII` 為基準，與 UI2 parquet 非同源 |
| G17 | 🎯 | 即時查一檔：6 維 snapshot | `page_inspect.fetch_metrics` 等 | disabled；單股價格鏈與 TWII 路徑完全不同 |
| G20 | 💼 | 持股表（Sheet 讀取） | `holdings_service.get_holdings` | 需 OAuth／Sheet；**不得**因 Legacy 有就推定 UI2 可讀 |
| G21 | 💼 | 235 燈／汰換／80-20／配息 | `dividend_station_service` | 無 |
| G22 | 💼 | VaR／壓測／配息現金流 | `portfolio_deep_service` | 無 |
| G25 | 👤 | 帳號／Sheet 綁定／active portfolio | `me_account_service`、`portfolio_binding_service` | Real `account=None` |
| G26 | 🗂 | 資料健康度、reconcile、校準狀態 | `data_registry_summary_service.summarize_data_registry` 等 | 固定空殼 |
| G27 | 🗂 | 資料體檢燈牆／API 診斷／Fetcher 監控 | `src/ui/pages/health_inspector.py` 等 | 無（Old UI 診斷面） |

### 3.2 其餘分類（共 27 列：17＋10）

- **已承接（2）**：G01 台股收盤卡、G02 日 K（UI2 較舊 UI 更完整；舊 UI 圖 A 為收盤折線，漲跌 % 走另一條 live 管線，口徑不同，§4 X-07）。
- **刻意不承接（5，附依據）**：G05 Risk Cap（Freeze §0.1.4／DEC-124）、G09 關鍵警示（待 Aggregator）、G12 一鍵更新 refresh producer（G2F 禁 producer）、G18 加入觀察清單（無授權的 Sheet 寫入）、G24 AI 戰情總結（Stage G）。
- **非缺口（2）**：G19 名稱搜尋（舊 UI 也沒有）、G23 目前曝險（資料本身不存在）。
- **NOT VERIFIED（1）**：G13 風險雷達／總經指南針／新聞 AI（Old UI 側；是否仍被 Legacy New UI 呼叫未核）。
- 計數方法為逐列人工計（16＋G04＝17；17＋2＋5＋2＋1＝27），分類有爭議處（G09／G11 是否同一缺口）以列為單位不去重。

---

## 4. 跨頁／跨層口徑問題

只放 FACT 與清楚標示的 INFERENCE。「UI2 影響」＝是否已污染 UI2 目前畫面。

| ID | 問題 | 證據 | 標籤 | UI2 影響 |
|---|---|---|---|---|
| X-01 | 市場位階在 UI2 恆「未載入」 | §0-3、M-05 | FACT | 位階欄是常數字樣，永遠不會出現位階值 |
| X-02 | **`finmind_inst.parquet` 同欄 `foreign_buy` 內兩種 `source` 標籤**：`…:Foreign` 4920 列（2006-09-29～2026-10-08）、`…:Foreign_Investor` 19 列（2026-10-12～2026-11-09）；單一 `source` 欄、無獨立口徑欄 | 本回合 `python -I` 讀 parquet 重算（§10 V4）；`scripts/update_macro_history.py::fetch_finmind_inst` docstring 自述「讀 `source` 欄即可分辨新舊口徑」 | FACT（標籤分布）；「`:Foreign` 列是否含外資自營商、自哪天起」＝docstring 轉述「派工規格所載實測事實，本批未重抓驗證」→ **NOT VERIFIED**；`docs/vnext/…CHIPS_OLD_UI_FIRST_MAPPING` §1.1 只寫「2017-12-18 前」，與 docstring 三時期說法不一致（文件側） | 目前無（UI2 未用）；任何跨斷點（≥19 列）的外資彙總都會混口徑；`load_extreme_risk_legs` 不檢查 `source`（INFERENCE：近 5 日窗在新口徑內） |
| X-03 | **板塊「外資分項」≠ FinMind「大盤外資」**：同 37 個共同交易日（2026-09-11～11-09）中 36 天同號，逐日絕對差中位 55.4 億、最大 239.6 億；最新日 −942.4 vs −900.6 億（差 −41.9） | 本回合唯讀重算（§10 V5）；方法：`daily_net.parquet` 逐日 `foreign_yi` 加總 vs `finmind_inst.foreign_buy` | FACT（數字）；成因＝**INFERENCE**（板塊用「張數×收盤價」估算、FinMind 用申報買賣金額差；上櫃範圍 FinMind dataset 是否含 NOT VERIFIED） | 目前無；未來若兩者並列同標籤＝誤導（G-10：不可比較或加減）。另：板塊 L3 `n_dropped_missing_price`（缺價被剔除股數；`metadata.json` per_day 15761）**L3 不外露**，故「合計」的覆蓋範圍使用者看不到 |
| X-04 | VIX：`fetch_vix_block`（raw yfinance，3mo）、`macro_core.fetch_yf_close('^VIX')`（6mo，NAS proxy）、`macro_alert._yf_latest` 三條取數；`allocation_service._read_vix` 讀 session | 反向調查 T-8（讀碼） | FACT（多管線）；「同頁兩個 VIX 可不一致」＝INFERENCE | 無（UI2 空槽） |
| X-05 | US10Y：FRED `DGS10`（五桶燈優先）vs Yahoo `^TNX`（國際趨勢圖）；Legacy 在 `page_market` 有「與國際市場區的 Yahoo ^TNX 不同源」揭露；警示路徑「session 已算值 > yfinance 即時」可能換源（INFERENCE） | T-4 | FACT（雙口徑）／INFERENCE（換源） | 無（UI2 空槽）；D1 已定口徑為 FRED（僅口徑） |
| X-06 | DXY：顯示備援鏈可落到 ETF（`UUP`，~27 美元尺度）；五桶燈有 [70,130] 範圍擋，國際趨勢圖 B 是否有擋＝grep 無命中（未追上游過濾） | T-5 | FACT（備援鏈）／INFERENCE（圖 B 可能畫出 UUP 尺度） | 無 |
| X-07 | 加權指數 4 條 Yahoo 取數管線（parquet cron／live `yf_proxy`／raw `yf.download`／`macro_core` chart）；Legacy 圖 A「收盤取 parquet、MA 取 live」；漲跌 % 走 `shared/stats_helpers.calc_stats`，其 `pct = ... if prev else 0` 是缺值補 0 形態（Legacy 路徑） | T-7、F5、F7 | FACT（多管線）；「圖 A 收盤與 MA 最新日可能相差」＝INFERENCE | UI2 只用 parquet 管線（單一、可驗）；UI2 無漲跌欄 |
| X-08 | **新鮮度閾值不一致**：板塊 `SECTOR_FLOW_STALE_MAX_CALENDAR_DAYS=4`（`shared/sector_flow_thresholds.py`）；TWII／融資／外資走 `CACHE_DATASET_CADENCE` daily→`STALE_DAYS_DAILY=7`（`shared/staleness.py`）；PMI 未登錄 cadence 必 stale；皆不看交易日曆。**判定基準日也不一致**：板塊 `reader._compute_staleness` 與融資 L3 用台北今日（`tw_now().date()`），TWII 卡／日 K 的新鮮度走 L1 預設主機 `date.today()`（`get_twii_trend_view(today=None)` docstring：新鮮度沿用 L1 預設）；部署主機時區 NOT VERIFIED（`I1140-TODAY-TZ` 條件式） | 本回合讀碼（§10 V7） | FACT；「同一資料日可能板塊過期、外資／融資不過期，連假下一個 stale 一個非 stale」＝INFERENCE | 目前無（三者未並列）；`N-1`（§8）為候選項 |
| X-09 | **卡片新鮮度**：`compute_cache_staleness` 以 `_dt.date.today()`（伺服器時區）計日曆天；日頻門檻 7 | `src/data/macro/macro_cache_reader.py::compute_cache_staleness`；本回合實測 as_of 2026-11-09、today 2026-11-12→`age_days=3`、`is_stale=False` | FACT | 11-10、11-11 兩個平日收盤未入庫（是否皆為開市日 NOT VERIFIED），卡片無任何過期提示 |
| X-10 | **成交量序列「猜單位」**：`leading_indicators.twse_volume` 備援段對 Yahoo `^TWII` 的 `Volume` 以 `for _div in [1e8, 1e4, 1e3]` 逐一嘗試，第一個落在 `5 < v < 20000` 者收下並當「億元」；同檔把 FMTQIK／MI_INDEX（成交金額，億）與該備援 `update` 進**同一個** `vol_dict` | 本回合讀碼＋讀 parquet（§10 V8）；`twii_ohlcv.parquet` 最近一筆非 NaN volume＝4,239,400（2026-11-05），除以 1e4＝423.94 通過條件 | 迴圈與合併＝**FACT**；「偏差 ≥10× 的格點會被混入、標成億元」＝**INFERENCE（未實際觸發備援、未取得同日 FMTQIK 對帳）** | UI2 不顯示成交量，**尚未污染**；日後接成交量須避開 `twse_volume`，改建唯讀 L3 |
| X-11 | 融資單位：`fetch_margin_balance` 走 `shared/margin_schema` SSOT；`leading_indicators._to_yi_mg`／`_twse_margin_day` 以數值區間猜單位，不引用 `margin_schema` | 反向調查 T-3（grep） | FACT（實作重複）；數值分歧 NOT VERIFIED | 無（UI2 若接 `margin_fact_service` 走 SSOT）；`I1140-MARGIN-UNIT-MIX`（歷史混用僅驗最新點） |
| X-12 | 融資 L3 使用者可見常數 `MARGIN_SOURCE_TEXT`＝「本地融資餘額歷史快取（FinMind 全市場融資金額，元換算為億元；每日更新）」含「全市場」；FinMind 該 dataset 是否含上櫃 NOT VERIFIED | `src/services/margin_fact_service.py::MARGIN_SOURCE_TEXT`；板塊側有 `test_no_market_wide_or_forbidden_fields` 守住，融資側 `test_source_has_only_fixed_user_visible_strings` 只釘常數名稱集合、不禁內容 | FACT（字面與守衛範圍）；是否構成誤導＝文案裁示 | 無（L3 未接線）；接線前須處理 `I1140-MARGIN-SOURCE-TEXT` |
| X-13 | 兩個板塊 L3 並存：`sector_flow_service.get_sector_flow_view`（🎯 產業）與 `sector_flow_fact_service.get_sector_flow_fact`（📊 資金），讀同一份 `data_cache/sector_flow/*`，stale 規則與狀態詞彙不同 | 文件側（TARGET_AUDIT §1 C1、DEC-164 §三） | FACT（並存）；無擇一／對帳規則＝NOT VERIFIED（建議登記 two-paths 風險，INFERENCE） | 無（皆未接） |
| X-14 | `partial`／`unknown`（板塊 completeness）不在 `FieldState` 五態內，線框的 `partial` 狀態無映射、無測試 | `shared/ui2_contract/models.py`（五態恰五個）；L3 `completeness` | FACT | 無（未接線） |

---

## 5. 文件間衝突與過期宣告

調查共整理 **17 項衝突、14 項過期宣告**（單組、逐份閱讀並抽查，**非窮舉**）。本節只取影響最大者；其餘見調查結論（原料位於調查者 scratchpad，**未入 repo**；未納入原因＝多為文字漂移、無資料欄位後果）。表中標「本回合重核」者已自行驗證（§10 V9）。

### 5.1 衝突（取 8 項）

| # | 議題 | 兩邊說法 | 判斷 |
|---|---|---|---|
| C1 | 台股主圖現況 | A：「誠實空槽」（Gap Audit、Old-First 差異矩陣、MARKET_READONLY，基準 `f5e78e10`／`e909152`）；B：已有 20 根日 K 主圖（CAPMAP_3COL、ISSUE1110） | **FACT：B 為現況**。`src/ui2/views/market.py` 有 `kbar_chart_html`（本回合重核）；A 基準早於 #1101／#1109（`31acbe87` 2026-11-10 03:34、`81db0637` 2026-11-10 13:34，`git log` 重核） |
| C2 | Real feed 接了幾個事實 | 「2 個」：REAL_FEED_MAPPING、DATA_LINEAGE、ISSUE1110、**UI 文案** `src/ui2/shell/app.py::_FEED_LABELS`「只接 2 項真資料」；「3 個」：CAPMAP、PREGATE 研究 | **FACT**：`real_feed.py` 三個 reader（卡、日 K、位階）；兩個 canonical service、三個 UI 事實；**文案仍寫 2 項＝文案漂移**（§7 D）。本文不改文案 |
| C3 | `fetch_us10y_block` 有無 FRED API 第二層 | MARKET_READONLY 暗示兩層；ISSUE1110 稱 docstring 的 Tier 1 在函式體不存在 | **FACT（本回合重核）**：函式簽名與 docstring 有 `fred_api_key`／Tier 1，函式體只有 `fredgraph.csv`，簽名行外 0 次引用 `fred_api_key`；ISSUE1110 較準 |
| C5 | 憲法 §2.1「VIX：Yahoo 主、CBOE CDN 備」「TW 融資：TWSE 主→HiStock→Wearn」 | 與碼不符：`cdn.cboe.com` 僅在 `src/compute/risk/risk_radar.py`（VIX3M 等），`fetch_vix_block` 無 CBOE 備援（本回合重核）；融資鏈實為 FinMind→MI_MARGN→HiStock→Goodinfo→Yahoo→鉅亨（**此鏈順序為文件側／調查者讀碼轉述，本回合未重核**） | **FACT（VIX 部分已重核）**：憲法宣告與碼不符；本文不改憲法（§-1：無指派不動工） |
| C7 | 板塊兩個 L3 並存 | 見 §4 X-13 | NOT VERIFIED（無擇一規則） |
| C9 | 外資口徑比較 | 板塊外資分項 −942.4 億 vs `finmind_inst` −900.56 億（文件記 −41.9 差），G-10「不可比」 | **FACT：差額本回合重算吻合**（§10 V5）；成因 NOT VERIFIED |
| C11 | Stage F／G 是否為前置 | Cutover：F／G「暫列 cutover 前置」；PREGATE：G-F2～G-F6「不阻塞」市場資金與籌碼接線 | 兩者範圍不同（cutover vs 單一區塊接線），不矛盾但易混讀；「不阻塞」本身＝INFERENCE，未經客戶確認 |
| C16 | 閾值不一致 | 板塊 4 日、融資／TWII 7 日、PMI 必 stale | 見 §4 X-08；無任何文件裁示統一 |

### 5.2 過期宣告（取 6 項）

| # | 過期宣告（出處） | 取代依據 | 本回合重核 |
|---|---|---|---|
| S1 | 「TWII 主圖誠實空槽」（Gap Audit、Old-First 矩陣、MARKET_READONLY） | #1101／#1109；`src/ui2/views/market.py` 有 `kbar_chart_html`；`tests/test_ui2_guards.py::G2F_IMPORT_ALLOWLIST` 含 `twii_kbar_fact_of` | **已重核：成立** |
| S2 | 「Real-data Preview 目前只讀 TWII 收盤及嚴格 Regime 兩個事實」（Gap Audit 第 6 行；REAL_FEED_MAPPING；DATA_LINEAGE） | 同 S1；現為三個 UI 事實（卡、日 K、位階） | **已重核：Gap Audit 該句原文存在；現況為三事實** |
| S4 | ISSUE1110 §5 資安發現（診斷頁顯示金鑰前後 4 碼、整段 `PROXY_URL`） | #1113／#1114；`src/ui/pages/api_diagnostic.py` 已無 `_mask` | **已重核：`_mask` 命中 0**（修復 PR 的正確性本回合未驗） |
| S11 | 「`I1144-A2-IMPL` 已授權、尚未實作」（`docs/BACKLOG.md` 舊列） | DEC-166；BACKLOG「Issue #1144 結果」列：已完成（PR #1146，`d4f7b3f`） | **已重核**：BACKLOG 同檔並存兩列（一列「已授權、尚未實作」、一列「已完成」），`git log` 見 `d4f7b3f6` 改動 `decision_digest_builder.py`。**同檔新舊並存，讀舊列會誤判** |
| S12 | 「#1149 被 CI 環境阻塞」 | DEC-170 §四：#1150 修復、#1149 合併 | 未重核（轉述） |
| S14 | `NEWUI2_CUTOVER_GAP_MATRIX` 內 BACKLOG 行號引用 | 3C 重整（DEC-173）搬移 BACKLOG；`REORG3C-REF-SYNC`（open） | **已重核**：`FUI-STAGE-F` 現於 BACKLOG 約 1125 行（非該矩陣所引的 1201），1201 行現為「客戶點名 16 項」表頭。**依 §8.2.A.0 規則 1，本文一律用 ID／符號** |

其餘過期宣告（S3、S5～S10、S13）出處與取代依據見調查結論，**本回合未逐項重核**，不納入本文。

---

## 6. Gate 全表

> **照實抄文件記載的狀態。本文不宣稱任何 Gate 已解除、不暗示任何接線已授權。「誰能解除」＝文件記載的裁示者／解除條件。** BACKLOG ID 本回合 grep 均存在（命中次數不一，不代表狀態）。

### 6.1 市場資金與籌碼線（Issue #1140／#1144）

| Gate ID | 內容 | 狀態 | 誰能解除 | 相關欄位 |
|---|---|---|---|---|
| `I1144-WIRING-GATE` | UI2 runtime 接線（feed／section／`G2F_IMPORT_ALLOWLIST`／snapshot／canonical／VM／view） | **HOLD／未授權** | 客戶（新 Gate） | M-18～M-21，以及**所有尚未接進 `real_feed` 的資料欄位**（皆需同類 allowlist 變更） |
| DG-COV＝`I1140-COVERAGE-MIN` | 板塊最低 coverage 門檻與母體口徑；**不得自設百分比** | **HOLD** | 客戶 | M-19 |
| DG-PIT | 無 `release_date` 時是否接受「資料日＋抓取時間（明示非發布時點）」 | **HOLD** | 客戶 | M-18、M-19、M-20 |
| DG-LIC＋`I1144-LIC-THREE-QUESTIONS` | TWSE／TPEX／FinMind 等資料於 Cloud 呈現與衍生聚合的授權（是否商業／是否公開／公開 repo 是否保留個股級來源列） | **HOLD**（FinMind PARTIALLY；其餘 NOT VERIFIED） | 客戶／法務（AI 不下結論） | 全部取自三家＋Yahoo＋MOPS＋data.gov.tw 的欄位 |
| DG-SCOPE | 日後接線先融資一項（A）或融資＋板塊（C） | **HOLD**（AI 推薦非裁示） | 客戶（須附推薦，§8.4 step 4） | M-18、M-19 |
| `I1144-DATA-STORAGE-DECISION` | 是否修改公開 repo 的資料保存方式 | **待客戶裁示，非動工項** | 客戶 | T-06 產業對映／候選池、M-19 |
| 外資 L3（無獨立 ID） | 大盤外資淨買賣超唯讀 L3＋授權 | **未授權、另案** | 客戶（授權）；總管（技術設計） | M-20 |
| `I1140-MARGIN-SOURCE-TEXT`／`-ETF-FAMILY-ABSENT`／`-SECTOR-CRON-SCOPE` | 接線前文案約束（不稱全市場；家族成員缺席揭露；診斷計數範圍） | open | 總管提案＋客戶（文案） | M-18、M-19 |
| `I1140-SECTOR-UNOBS-LABELS`／`-DROPPED-PRICE` | 3 個偶發標籤成因、15761 含義 | open，成因 NOT VERIFIED | 總管（獨立一組查證） | M-19 |
| `I1140-MARGIN-UNIT-MIX` | 歷史融資單位混用只驗最新點 | open，條件式（取歷史序列才觸發） | 總管 | M-18 |
| `I1140-OHLC-GUARD`／`-FUTURE-ASOF-ASYM`／`-TODAY-TZ` | 日 K 路徑守衛／未來日不對稱／時區 | open，條件式 | 條件觸發 | M-09、M-10 |
| `I1140-REGIME-SET-EQ`／`I1140-MACRO-STATE-NONCANON` | UI2 與 Digest 兩份位階白名單無等式測試；`get_macro_state` 把非 canonical regime 洗成 `neutral` | open（既知、被測試釘住、不動） | 總管 | M-05 |

### 6.2 Digest／Stage F 線

| Gate ID | 內容 | 狀態 | 誰能解除 | 相關欄位 |
|---|---|---|---|---|
| G-F1 | headless 市場輸入供應 | 方案 A 已核准（DEC-161，轉錄）；MISSING 項目維持 MISSING | — | Digest 市場段 |
| G-F2 | headless 持股授權 | 待裁示 | 客戶 | 💼、Digest 持股段 |
| G-F3 | A2 stale 取向 | 待裁示 | 客戶 | 所有 stale 值 |
| G-F4／G-F5 | Digest v2 schema／PIT；production caller 時機 | 待裁示 | 客戶 | U-05 |
| G-F6＝`NUI2-AUTH-CONTRACT-GATE` | 登入前置 | 待裁示／open | 客戶 | 💼、👤 |
| `I1144-DG-A3`／`I1144-DG-HEALTH` | Digest regime／light 配對一致性；`market.health` 範圍 | 未授權、獨立 Gate | 客戶 | Digest 市場段 |
| `FUI-STAGE-F／G／H／I` | Digest／OneBrain／跨頁一致／real-data 驗收 | open（未開始） | 依序前置，客戶 | M-16、H-07 |

### 6.3 Cutover／身分／動作線

| Gate ID | 內容 | 狀態 | 誰能解除 | 相關欄位 |
|---|---|---|---|---|
| `NUI2-AGGREGATOR-IMPL` | System Action Aggregator 實作 | blocked-on-customer | 客戶 | M-07、H-04 |
| `NUI2-ME-ACCOUNT-REAL-GATE` | 真 OAuth／Sheet | open | 客戶 | 💼、👤 |
| SG-01～SG-14 | Stop Gate 候選（更新 CTA、利差、PMI、候選因子、目前曝險、Risk Cap 數值、動作欄、Forward EPS、OneBrain、位階 as_of、OAuth、五桶 thin L3、新公式／門檻） | open，本批未觸發 | 客戶（各自） | 見 §2 各列 |
| RC-VISIBILITY／C2b／DEC-141 Q5 | Risk Cap 數值／日期／沿用天數顯示 | 未授權 | 客戶 | M-06、H-03 |
| D1～D5（Issue #1121 轉錄） | D1 US10Y 口徑 FRED DGS10（僅口徑）；D2 VIX、D3 利差、D4 PMI 維持空槽；D5 不新增每日落地 cron | 轉錄式裁示（非逐字、非 QA PASS） | — | M-11～M-15 |
| `NUI2-PORT-*` | Old UI L5 邏輯上移 L3＋parity（READINESS-L3／CONCLUSION-CLAUSES／MAIN-RISK／INDUSTRY-RANK／INDICATOR-TILES） | open | 客戶授權施工 | M-04、M-08、M-17、T-06 |
| `NUI2-CUTOVER`／`NUI2-REMOVAL-GATE`／`NUI2-CAPMAP-3COL` | cutover／移除 | open（文件記 0 條 cutover 條件已滿足） | 客戶 | 全頁 |
| `NUI2-PREVIEW-CLOUD-STATE-FILES`／`NUI2-PREVIEW-APP-MANUAL`／`NUI2-ACC-REAL-DEVICE` | Cloud 狀態檔、Cloud Preview 人工建立、真機驗收 | open／NOT VERIFIED | 真機人工＋工程 | M-05、全頁 |
| 治理類 | #1119 Actions 精簡 HOLD；#1124～#1126 未處置；`REORG3C-Q5-GATE` | HOLD／open | 客戶 | 無直接欄位；**本批不碰** |

---

## 7. B1：UI2 安全面向結論

### 7.1 結論

**未發現「契約內、可重現、不涉及新設計決策」的缺陷**（發現統計：BUG-in-contract 0｜GUARD-GAP 2｜VISUAL-GATE-CANDIDATE 2｜NOT-A-DEFECT 4＋1 文案項）。**這不是任何 UI 改動的授權**——任何 UI 改動須先出文字線框給客戶（§-1.5 草稿先行）。

### 7.2 檢查面向與方法（單組調查者執行；本文僅轉述）

| 面向 | 方法 | 結果 |
|---|---|---|
| 1 手機 390／桌機 1440 首屏（遮擋／裁切／需捲動） | `tests/ui2_viewport` 量測 5 頁×6 場景＋🎯 lookup＋👤 三帳戶態＋📊 長字串 stress，× 390／1440，共 82 狀態；Streamlit 1.67.0 與 1.59.2 各跑一次；另對預設道 320…1440 多寬度手動探測 | 82／82 通過；無水平溢出、無裁切（FAKE 軸） |
| 2 資料狀態 vs 契約（四態／chip tone／字樣） | 讀碼＋`tests/test_ui2_guards.py` 系列 | 未發現；🗂 頁全為 capability 軸 |
| 3 缺值被誤呈現為 0／正常／中性／安全 | 靜態 grep `or 0`／`.get(…,0)`／`fillna`／`else 0` 等於 `src/ui2 src/services/ui2 shared/ui2_contract`＝0 命中；AppTest 逐「5 頁×6 場景」取可見文字 grep 孤立 `0`／`安全`／`正常`／`中性` 等 | 唯一命中＝客戶逐字句「未評估不等於安全」（DEC-117 Q6=A 必須外露）；其餘 0 |
| 4 Preview／FAKE vs Real 標示混淆 | 預設道 banner 探測；Real 標示 DOM 模擬（360…1440） | 未發現契約內缺陷；**Real 軸真實瀏覽器量測未做**（見 7.4） |
| 5 既核准 UI 版面的安全回歸守衛缺口 | 盤點 viewport 矩陣與守衛 | 見 GUARD-GAP |

另跑 `python -m pytest tests/test_ui2_*.py -q`：**1705 passed, 41 deselected, 3 xfailed**；`UI2_BROWSER_LANE=required … -m ui2_browser`：**41 passed**（皆調查者自報；本文未重跑）。

### 7.3 候選項（皆**非缺陷**、**非授權**）

| ID | 內容 | 分類 | 處置 |
|---|---|---|---|
| VG1 | FAKE 與 Real 標示在第一列樣式相同（只靠文字「示意資料（FAKE）」vs「Real-data Preview（非正式 production default）」區分） | VISUAL-GATE-CANDIDATE | 視覺契約外改動，須先出文字線框給客戶；本批不修 |
| VG2 | FAKE 👤 預設帳戶態＝signed_in，頁內「Google 已登入（FAKE 帳號）」與頂列「帳號 ⬜ 尚未提供」並置（全帶 FAKE 標示；`ui2_account` 僅開發面示意） | VISUAL-GATE-CANDIDATE | 改 FAKE 場景預設屬設計決策，須經草稿 gate |
| D（文案漂移） | `src/ui2/shell/app.py::_FEED_LABELS` 與 `tests/test_ui2_drawer_browser.py` 皆寫「只接 2 項真資料」，實況＝REAL 帶真值 2 欄（台股卡、日 K）＋位階已接線（恆未載入）；`shared/ui2_contract/text.py::REAL_PREVIEW_BANNER_NOTE`「僅台股與市場位階為真資料」則與位階口徑一致。**只描述事實，不改文案**（開發面文案，非產品畫面；改字樣須先確認屬哪一類） | 文案漂移 | 登記，不動 |
| N1 | 🎯 W-4 context 行對 Unavailable 也用 Neutral 色（非紅） | NOT-A-DEFECT | Wireframes §9／DEC-123 Q3 已核准 |
| N2 | FAKE 冷啟動「⬜ 尚未載入，請按更新」＋「下一步 按 🚀 更新」，但 CTA disabled | NOT-A-DEFECT（登記） | `text.py::RISK_SENTENCE_NOT_LOADED` 為客戶逐字常數（DEC-117 Q6=A）；頁首有 `示意資料（FAKE）`；Real 軸的對應欄位為 `_not_provided`、無「請按更新」。此處**僅登記**，不認定為缺陷、不建議改字 |
| N3 | Real 標示補充說明在 ≤640px 隱藏 | NOT-A-DEFECT | P1 已核准單行設計；非 Real 欄位一律 `⬜ 尚未提供` |
| GUARD-GAP G1 | viewport 量測矩陣只含 390×844、1440×900（僅一處 320×568） | 低；非缺陷 | 調查者手動探測 320…1100 寬無問題，故只是無自動守衛 |
| GUARD-GAP G2 | Real 軸瀏覽器量測證據只在 repo 既有 JSON（由 `test_ui2_real_feed.py` 的 `source_hash` 新鮮度守衛），本批未獨立複驗內容 | 低；非缺陷 | 登記 |

### 7.4 限制（如實）

- **Real-data Preview 瀏覽器量測因環境限制未執行**（背景啟動被環境拒絕，依規則不繞過）。Real 軸僅有靜態審閱、既有 pytest、DOM 模擬（INFERENCE）。
- Streamlit 1.56.0 本次未重跑（1.59.2、1.67.0 已跑；1.67.0 超出 `requirements.txt` 宣告範圍，僅作額外觀察）；Safari／Firefox／真機／Cloud／螢幕閱讀器未實測。
- 調查者**未讀**：`scenarios.py`、`real_canonical.py` 第 330 行之後、`models.py`、`views/{hold,me,target}.py`。故「5 個面向皆未發現問題」是單組、有明確未讀範圍的結論，**待獨立複驗**。

---

## 8. 「五頁驗收問題」逐題回答

**Q1　五頁每個資料欄位來自哪裡？** 見 §2。一句話：預設路徑全是 FAKE／固定占位；REAL 只有台股卡與日 K 來自 `data_cache/twii_ohlcv.parquet`（Yahoo `^TWII` cron 落地），位階來自 `get_macro_regime`（session＋本地狀態檔）。其餘 NP。

**Q2　哪些可用、哪些不可用？**
- **可用（READY，限接線＋契約面）**：台股卡、20 根日 K（M-09、M-10）；位階字樣管線（M-05，但實值恆未載入）；資料模式 banner。
- **資料層可用但 UI2 未接**：融資、板塊（L3 存在，0 caller；M-18、M-19）。
- **不可用**：其餘全部（BLOCKED／NOT VERIFIED）。
- 所有「可用」均以授權條款 NOT VERIFIED 為前提。

**Q3　口徑問題？** 見 §4：X-02（外資 source 斷點）、X-03（板塊外資≠大盤外資）、X-08（4 日 vs 7 日）、X-09（新鮮度偏弱）、X-10（成交量猜單位，INFERENCE）、X-12（融資常數含「全市場」）；以及 VIX／US10Y／DXY／TWII 的多管線（X-04～X-07，UI2 尚未污染）。

**Q4　舊 UI 有、UI2 未承接？** 見 §3：17 項有效缺口；其中**法人買賣超沒有 UI2 fact service**、國際趨勢與 VIX／DXY 沒有乾淨 L3。

**Q5　現有授權內可修復的事項？** 以本文證據：**無**。B1 未發現契約內可重現缺陷；X 系列口徑問題的修復多半涉及新定義／新 L3／文案裁示（屬 Decision Gate），文案漂移 D 屬開發面字樣，亦需先確認類別。**不要把「建議下一批」讀成授權。**

**Q6　市場頁距離「市場資金與籌碼」接線還差哪些 Gate？** 至少：`I1144-WIRING-GATE`（授權）、DG-SCOPE（範圍）、DG-COV（板塊覆蓋門檻與母體口徑）、DG-PIT（無 `release_date` 的取捨）、DG-LIC（授權三問）；大盤外資另需外資 L3 授權；接線前文案項 `I1140-MARGIN-SOURCE-TEXT`／`-ETF-FAMILY-ABSENT`／`-SECTOR-CRON-SCOPE`；`partial` 無映射（X-14）。接線面至少 5 處（`real_feed`、`G2F_IMPORT_ALLOWLIST`、`real_canonical`／snapshot、market VM、`views/market.py`＋FAKE 對稱；文件側清單）。**全部維持 HOLD。** 詳見同批 `NEWUI2_MARKET_DATA_CONTRACT_VALIDATION_2026-11-12.md`。

---

## 9. 全稱句與查法；未查證／環境限制

| # | 全稱句 | 查法 | 可信度 |
|---|---|---|---|
| 1 | 預設路徑不可能進入 REAL | 讀 `src/ui2/shell/app.py::run`：`KEY_FEED` 預設 `FEED_FAKE`，唯一寫入點為 `_render_dev_surface` 的 selectbox（僅 `dev=True`）；`grep ui2_feed|KEY_FEED src/ui2` 只命中該檔；`grep ui2 app.py`＝0 行。**未跑 AppTest 窮舉**，未驗 Streamlit 是否另有 URL→session_state 綁定 | 單組讀碼；NOT VERIFIED（動態） |
| 2 | REAL 只有 3 個事實（卡、日 K、位階） | `src/services/ui2/real_feed.py` 僅 `_read_twii`／`_read_twii_kbar`／`_read_regime` 三個 reader，`read_real_snapshot` 只組這三項 | 單組讀碼（本回合重核） |
| 3 | REAL 帶真值的畫面欄位只有 2 個 | 同 2；位階列 `is_loaded=False`；本沙箱 `read_real_snapshot()` 實測 | 沙箱成立；部署端 NOT VERIFIED |
| 4 | `margin_fact_service`／`sector_flow_fact_service` 在 UI2 三目錄引用＝0 | `grep -rln "margin_fact_service\|sector_flow_fact_service" src/ui2 src/services/ui2 shared/ui2_contract`＝無輸出；全 repo `.py` 另 grep 僅命中兩 L3 自身、`shared/sector_flow_fact_thresholds.py`、兩測試檔；**僅靜態 `.py`**，不含動態 import、文件、設定檔 | 單組 grep |
| 5 | 沒有任何欄位是 license-verified | 逐份閱讀文件；全域前提 | 待驗事項 |
| 6 | `src/ui2`、`src/services/ui2`、`shared/ui2_contract` 沒有把缺值補 0 的路徑 | `grep -rnE "or 0\b|\.get\([^)]*, ?0\)|fillna|else 0\b"`＝0 命中（調查者）；非 AST 窮舉；`html.py` 字串拼接未掃 | 低–中，單組 grep |
| 7 | Digest 0 production caller | `grep -rln "decision_digest_builder|decision_digest_summary|build_decision_digest" --include=*.py`，排除 `tests/`：僅 `shared/decision_digest_terms.py`、`src/services/decision_digest_assembly.py`、`src/services/decision_digest_builder.py`（digest 自家檔） | 單組 grep（本回合重核） |
| 8 | 衝突 17 項、過期宣告 14 項 | 單組逐份閱讀＋抽查，非窮舉；3C 重整後 `HANDOFF.md`／`PROJECT_STATE.md` 最新狀態調查者未讀 | 待驗事項 |
| 9 | B1「5 個面向皆未發現問題」 | §7.2 的方法清單；§7.4 明列未讀檔案 | 單組；待獨立複驗 |

**未查證／環境限制**：
- 未連外網；Cloud／真機／Playwright（Real 軸）／上游 API 可用性／cron 實際成功率皆未驗。
- 未重跑 5 份調查報告所引的 pytest（調查者自報數字僅轉述）；本文引用的測試名均已 grep 確認存在，**不代表目前綠燈**。
- TWSE／TPEX／data.gov.tw／Yahoo／FRED 授權原文 NOT VERIFIED；FinMind PARTIALLY。
- 11-10、11-11 是否為台股交易日（無行事曆）；`macro_state.json` 在部署端是否存在；`get_macro_state` 在「warroom 存在＋旗標 False」分支的逐行行為。
- 欄位數量（45／46）為人工建模，未重算。
- FinMind 外資／融資 dataset 是否含上櫃；`:Foreign` 列是否含外資自營商（docstring 轉述）；3 個偶發板塊標籤成因；15761 的組成（INFERENCE：T86 `selectType=ALL` 含權證等；未逐檔驗）。
- GitHub Issue（#1121／#1130／#1132／#1134／#1136／#1140／#1144）原文不在 repo；DEC 內客戶原文皆為轉錄，逐字性無法驗證。

---

## 10. 本回合重核紀錄與勘誤

### 10.1 九項重核（方法與結果）

| # | 項目 | 方法 | 結果 |
|---|---|---|---|
| V1 | 預設路徑只到 FAKE cold；Real 只經開發面 | 讀 `src/ui2/shell/app.py`（`run`、`_render_dev_surface`、`dev_surface_enabled`）；`grep ui2_feed|KEY_FEED src/ui2`；`grep ui2 app.py` | **一致**（`KEY_FEED` 預設 `FEED_FAKE`；selectbox 僅 `?ui2_dev=1` 渲染；`app.py` 0 行引用 ui2）。動態（AppTest）NOT VERIFIED |
| V2 | REAL 帶真值只有台股卡 close＋日 K（同一 parquet）；位階已接線但恆「尚未載入」 | 讀 `real_feed.py`、`allocation_service.get_macro_regime`；`grep warroom_summary` 於 UI2 三目錄（僅說明文字，無寫入）；寫入點僅在 `src/ui/tabs/macro/section_state.py`、`section_traffic_light.py`、`src/services/warroom_apply.py`；`git ls-files` 無 `macro_state.json`／`risk_cap_state.json` 且 `.gitignore` 列出；`shared/signal_thresholds.py::BREADTH_PROXY_SCORING_ENABLED=False`；**沙箱實測 `read_real_snapshot()`**：`regime=unknown, light=⬜, source=unloaded, is_loaded=False`；`twii.close=(41661.69921875,), as_of=2026-11-09`；`kbar` 為 `TwiiKbarFact` | **一致** |
| V3 | 兩 L3 在 UI2 三目錄引用＝0 | `grep -rln` 三目錄＝無輸出；全 repo `.py` grep（排除 worktree 副本）僅 `margin_fact_service.py`（自身）、`sector_flow_fact_service.py`（自身）、`shared/sector_flow_fact_thresholds.py`、兩測試檔；`margin_fact_service.py` docstring 自述「目前 0 production caller」；另 `app.py app_ui2.py scripts shared src` 的 grep 同結果 | **一致**（僅靜態 `.py`） |
| V4 | `finmind_inst.parquet` source 斷點 | `python -I` 唯讀 `pd.read_parquet`：欄 `date foreign_buy source fetched_at`，4939 列；`source` 分布 `…:Foreign`＝4920（2006-09-29～2026-10-08）、`…:Foreign_Investor`＝19（2026-10-12～2026-11-09） | **一致** |
| V5 | 板塊外資分項 vs FinMind 大盤外資 | `python -I`：`sector_flow/daily_net.parquet` 逐日 `foreign_yi`（所有原始標籤列，`min_count=1` 加總）inner-join `finmind_inst.foreign_buy` 逐日加總；共同日 37（2026-09-11～2026-11-09），同號 36，逐日絕對差中位 55.42、最大 239.57（億）；最新日 −942.44 vs −900.56，差 −41.87 | **一致**（C1 報告稱中位 55.4、最大 239.6、−942.4／−900.6／−41.9） |
| V6 | 「只接 2 項真資料」文案 | `grep -rn "只接 2 項" src tests app_ui2.py`：`src/ui2/shell/app.py:42`（`_FEED_LABELS`）與 `tests/test_ui2_drawer_browser.py`（以該字樣選 selectbox）；`shared/ui2_contract/text.py` 的 `REAL_PREVIEW_BANNER_NOTE`＝「僅台股與市場位階為真資料」 | **一致**（只描述事實，未改文案） |
| V7 | 卡片新鮮度判定 | 讀 `macro_cache_reader.compute_cache_staleness`（`_today = today or _dt.date.today()`、日頻 `age_days > stale_days_threshold(cadence)`）、`shared/staleness.py::STALE_DAYS_DAILY=7`、`CACHE_DATASET_CADENCE`；沙箱實測 today 2026-11-12、`twii.as_of=2026-11-09`、`age_days=3`、`is_stale=False`；parquet 最近 40 列 volume 27 列 NaN；`metadata.json` `datasets.twii_ohlcv.last_updated=2026-11-09`、`last_error=null` | **一致** |
| V8 | F2 成交量備援 `for _div in [1e8,1e4,1e3]` | 讀 `src/data/macro/leading_indicators.py`（`twse_volume` 備援段與約 1537–1557 行的 `vol_dict.update(...)`）；讀 parquet 最近非 NaN volume＝4,239,400（2026-11-05），除以 1e8＝0.042（不入）、除以 1e4＝423.94（入 `5<v<20000`） | **迴圈與合併為 FACT；數值偏差標 INFERENCE**（未實際觸發備援；未取得同日 FMTQIK 對帳）。**示例數字更正**：原料用中位數 2,895,800→289.6；本文以 parquet 最近值重算為 423.94（結論相同） |
| V9 | 文件側過期宣告抽驗 ≥5 項 | S1（`market.py` 有 `kbar_chart_html`、`G2F_IMPORT_ALLOWLIST` 含 `twii_kbar_fact_of`、`git log` 兩 PR 時間）；S2（Gap Audit 第 6 行原文存在）；S4（`api_diagnostic.py` 的 `_mask` 命中 0）；S11（BACKLOG 同檔新舊兩列並存、`git log` 見 `d4f7b3f6`）；S14（`FUI-STAGE-F` 現於約 1125 行、1201 行為不同內容）；另 C3（`fetch_us10y_block` 簽名外 0 次使用 `fred_api_key`）、C5（`cdn.cboe.com` 僅在 `risk_radar.py`） | **全部一致**（S4 僅確認症狀消失，未驗修復 PR 正確性） |

另本回合讀 L3 實況（`python -I`，唯讀）：`get_margin_fact()`→`OK`、5399.15741 億、as_of 2026-11-09、非 stale、`age_days=3`；`get_sector_flow_fact()`→`OK`、`completeness=complete`、41／38／3（未觀測：化學生技醫療、未分類、電子工業）、合計 −920.24812237 億、非 stale，caveats 含 `scope_includes_etf_etn_and_receipt_labels`、`absent_cells_in_window`。`data_cache/sector_flow/metadata.json`：`per_day['20261109']` 的 `n_stock_days_with_net=18026`、`n_dropped_missing_price=15761`、18026−15761=2265（算術吻合）。

### 10.2 勘誤（原料與本回合實測不符或需補充處）

1. **成交量示例數字**：反向調查 T-1 用中位數 2,895,800→「289.6 億元」；以 parquet 最近非 NaN 值重算為 4,239,400→423.94。結論（會通過條件而被標成億元）不變，**以本文為準**。
2. **測試檔歸屬**：程式追溯將 `test_regime_see_why_premise_breadth_proxy_scoring_is_off` 歸在位階相關測試；實際位於 `tests/test_ui2_p1_human_text.py`，不是 `tests/test_ui2_real_feed.py`。
3. **「absent」計數需分清**：市場契約調查引用 `n_member_absent_cells=0`（ETF 家族成員缺席）；本回合 L3 `coverage.n_absent_cells_window=53`（板塊×日 空格，`metadata.json bubble_window.n_absent_cells=53`）。兩者是不同量，**不互相矛盾**；`I1140-ETF-FAMILY-ABSENT` 針對前者，其值為 0。
4. **`:Foreign` 斷點敘述**：兩份調查均稱「含外資自營商」。repo 內唯一依據是 `fetch_finmind_inst` docstring 轉述派工規格（自述「本批未重抓驗證」），**本文降為 NOT VERIFIED**；已重核者僅有標籤分布與日期切點。
5. **BACKLOG 同檔新舊並存**：原料將 `I1144-A2-IMPL`「已授權、尚未實作」列為「過期宣告」；本回合確認該舊列仍在 BACKLOG 同檔，並與「已完成」列並存（§5.2 S11），讀者需以較新列為準。
6. **BACKLOG／其他文件行號**：原料中所有 BACKLOG 行號（如 `:1207`、`:2201`）在 3C 重整後不可信，本文一律改用 ID。

---

## 11. 建議下一批（最多 3 項；**皆為 RECOMMENDATION，非授權；不得自動跨越 Decision Gate**）

| # | 項目 | 需客戶裁示？ | 前置 Gate | 風險 | AI 總管推薦 |
|---|---|---|---|---|---|
| 1 | **獨立複驗本文與同批市場契約文件**：派第二組（非作者）重做 §10 九項與 §4 口徑表的關鍵 FACT，特別是 X-02／X-03／X-10 與部署端（Cloud）位階實況 | 否（內部 QA；§-2 規則 4） | 無 | 低；docs-only。風險在於不做：全稱句長期停在單組待驗 | **推薦先做**。同時決定本批兩份文件是否升格為被引用的前提 |
| 2 | **把「接線前須客戶裁示」整理成商業語言的一頁決策單**（DG-SCOPE／DG-COV／DG-PIT／DG-LIC 四問＋AI 推薦），並登記新候選 N-1～N-4（見市場契約文件 §6）與 §7 文案漂移項到 BACKLOG | 是（決策單本身要客戶看；登記屬治理 PR，由總管另案） | `I1144-WIRING-GATE` 不在此批解除；僅整理決策材料 | 低；不動 runtime。風險＝被讀成授權（已於各表標 HOLD） | 推薦；與 #1 同批或其後 |
| 3 | **（僅在客戶先裁示後）🗂 資料頁新鮮度總覽的文字線框草稿**：目前畫面沒有任何總覽新鮮度的位置（§2.5 後果），REAL 已掌握 TWII as_of／stale | 是（UI 版面異動，§-1.5 草稿先行；客戶拍板前不得寫 UI code） | 新欄／分母須先過 Data Contract Gate；不得以 cron 時刻冒充觀測日 | 中；易擴大為跨頁重排。與 `NUI2-P6-*` 既有線框決策可能重疊（需先查） | 暫不推薦自動啟動；列為客戶可選項，**不跨越 Gate** |

> 本文為稽核證據。接線、新增 L3、改文案、改 UI 結構、改資料保存方式——**每一項都需客戶另行授權**。
