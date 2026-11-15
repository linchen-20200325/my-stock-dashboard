# New UI2 五頁資料／功能／驗收矩陣（索引）— 2026-11-13

> 📌 **這份文件是什麼、不是什麼（請先讀）**
> - **是索引矩陣**：DEC-178 Quality Batch 1 工作項 ③（`docs/BACKLOG.md` `DEC178-QUALITY-BATCH-1`）。只把既有 SSOT 的**編號**對到「資料集／功能／驗收測試／完成層級」，內容一律寫「→ 檔名 §節／編號」，**不複製**。
> - **既有 SSOT**：欄位級＝`NEWUI2_FIVE_PAGE_DATA_CONTRACT_AUDIT_2026-11-12.md`（下稱 **AUD**，M-／T-／H-／U-／D-、X-、§6 Gate 表）；能力級＝`NEWUI2_CAPMAP_3COL_2026-11-10.md`（**CAPMAP**，MK-／TG-／HD-／ME-／DT-／SY- 共 100 列）；其餘引用 `NEWUI2_MARKET_DATA_CONTRACT_VALIDATION_2026-11-12.md`（MKT）、`PUBLIC_DATA_EXPOSURE_LICENSE_ARCH_AUDIT_2026-11-11.md`（**LIC** §2）、`NEWUI2_CUTOVER_GAP_MATRIX_2026-11-10.md`（**CUT**）、`QUALITY_BATCH1_COVERAGE_GAP_AUDIT_2026-11-13.md`（**GAP**）。均在 `docs/vnext/`。
> - **不是授權**：不解除任何 Gate／HOLD（`I1144-WIRING-GATE`、`DG-SCOPE`／`DG-COV`／`DG-PIT`／`DG-LIC`、DEC-177 Q1～Q7、#1124～#1126、#1119 全部維持原狀）；**不新增**資料欄位、來源、接線、API、cron、Secrets、版面；不建議放寬任何守衛或修改 Active Contract。
> - **不是 QA PASS**：單組撰寫（執行 AI），輸入為兩份單組調查報告＋GAP §4.2 更正，已親驗承重引用（§7）；**未經非作者獨立 QA**（`CLAUDE.md` §-2 規則 3／4／6）。全稱句只能當待驗事項。
> - **標註**：**FACT**＝本次讀檔／grep／`git`／`gh api` 唯讀直接確認；**INFERENCE**＝由事實推論；**INHERITED**＝轉述 AUD 等文件、本次未重核；**NOT VERIFIED**＝未驗，不得當前提；**NOT AVAILABLE**＝契約／資料層查無此欄。本批**未跑** pytest／AppTest／瀏覽器／viewport，**所有「測試 PASS」＝NOT VERIFIED**，只確認測試函式存在。引用一律「檔:符號」，不引行號（`CLAUDE.md` §8.2.A.0 規則 1）。

## 0. 基準與頁首事實

| 項 | 結論 | 標籤／證據 |
|---|---|---|
| 基準 main | `origin/main` ＝ `5b180ea2da2c6445ecf38722676d481082ed1646` | FACT：`git fetch origin main` 後 `git rev-parse origin/main` 與 `gh api repos/linchen-20200325/my-stock-dashboard/commits/main --jq .sha` 一致。本分支另含 docs-only 提交 `a734f9b`（Batch 1 ①）、`e922e6e`（Batch 1 ②）。撰寫日 2026-11-13 |
| 自 AUD 基準 `7eb48d6c` 以來程式／資料差異 | `git diff --stat 7eb48d6c origin/main -- src shared app.py app_ui2.py data_cache tests scripts .github` 只有 `.github/workflows/pr-check.yml`（+7/−2）與 `tests/test_agent_definitions_guard.py`（+381）；`src shared app.py app_ui2.py data_cache scripts` **無 diff** | FACT。故 AUD 對 src／shared／data_cache 的斷言在 `5b180ea` 仍適用（AUD 各列本身正確性＝INHERITED） |
| #1124～#1126 目前 head（只記錄、不碰） | #1124 head `3cd3f525`（`macro-history`；head commit「每日總經歷史增量：2026-11-12」，2026-11-12T17:29:34Z）；#1125 `cf4739c5`（`sector-flow`）；#1126 `1654ae60`（`macro-forward-test`）；三者 `state=open`、`merged=false`、base `85c65dfc` | FACT（`gh api repos/…/pulls/{n}` 唯讀）。AUD 記載 head `fc447def`／base `043a4d21` ＝**已過期**（見 §7-1） |
| PR 分支資料日 vs main | #1124 內文「資料狀態」段：分支上 `finmind_inst`／`finmind_margin` 資料日 2026-11-12、`twii_ohlcv` 2026-11-11；**main** `data_cache/metadata.json` 仍 2026-11-09 | FACT（PR 內文為自動產生字樣；PIT／是否交易日／cron 成功率 NOT VERIFIED）。停更因果（PR 未併 vs cron 失敗）＝INFERENCE |
| 欄位通則：fetched_at | UI2 VM 契約 `shared/ui2_contract/models.py::FreshnessInfo` 只有 `as_of`／`source` 兩欄 → **NOT AVAILABLE（VM 契約層）**。儲存層有（`tw_pmi.parquet`／`finmind_inst.parquet` 欄，→AUD M-15、X-02；INHERITED），且 `src/services/ui2/real_canonical.py` 內 `FETCHED_AT_MISSING` 用於「日 K 是否已收盤」判定（不顯示） | FACT（`FreshnessInfo` 親讀；`grep -i fetched_at`（**不分大小寫**；小寫 `fetched_at` 於該三目錄 0 命中）於 `src/services/ui2 shared/ui2_contract src/ui2` 僅命中 `src/services/ui2/real_canonical.py` 的 `OC.FETCHED_AT_MISSING` 一處；常數定義在 `shared/twii_ohlc_contract.py`）。GAP §4.2-5 同 |
| 欄位通則：PIT／release_date | UI2 VM 契約與 UI2 三層**無此欄**（`grep -i "release_date\|point.in.time"` 於上述目錄＝0）→ **NOT AVAILABLE**；Gate 面＝`DG-PIT`（HOLD，→AUD §6.1） | FACT |
| 欄位通則：currency／幣別 | `grep -iE "currency\|幣別"` 於 `src/services/ui2 shared/ui2_contract src/ui2`＝0 → **NOT AVAILABLE**；單位以 AUD 各列「欄位單位」為準（如億、指數點） | FACT |
| 欄位通則：Canonical｜Shadow | repo **無**「每 Dataset 的 Canonical／Shadow 屬性」；唯一用語＝`shared/ui2_contract/pages.py` 註解「Real＝唯讀 real-data shadow（非 production default）」。本矩陣「接線」欄只據 `src/services/ui2/real_feed.py` 三 reader 分 FAKE／REAL shadow／NP／0 caller | FACT。若要把四欄變正式契約欄位＝新設計決策，須 Data Contract Gate；**本矩陣不新增** |
| 授權通則 | 沒有任何 Dataset 是 license-verified：FinMind A 層 PARTIALLY VERIFIED、C 層（本專案已取得授權）NOT VERIFIED；TWSE／TPEX／MOPS／CBC／Yahoo 三層 NOT VERIFIED；data.gov.tw A 層 PARTIAL（OGDL 轉錄本）、B／C NOT VERIFIED；**FRED 不在 LIC 表內**（`grep -ci FRED`＝0） | FACT（LIC §2 親讀）。`DG-LIC` HOLD，AI 不下結論 |

## 1. 五頁總表

頁序／id：`shared/ui2_contract/pages.py::PAGE_LABELS`（前四頁取自 `shared/ia_nav4.py`；第五頁 `P4_DATA="p4_data"` 為 UI2 自有，DEC-146）；守衛 `tests/test_ui2_guards.py::test_only_five_pages`（斷言順序 `p4_market, p4_target, p4_hold, p4_me, p4_data`）。入口 `app_ui2.py`→`src/ui2/shell/app.py`；`app.py` 對 ui2 引用 **0**（`grep -c -i ui2 app.py`＝0）。VM builder 由兩條 feed 共用：FAKE `src/services/ui2/preview_feed.py`→`scenarios.fake_canonical`；REAL `real_feed.read_real_snapshot`→`real_canonical.get_real_page_vm`。

| 頁 | page_id | view（`src/ui2/views/`） | VM builder（FAKE／REAL 共用） | 欄位／能力索引 | 規格與線框（`docs/vnext/`） | 核准 DEC 引用（`docs/DECISIONS.md`） |
|---|---|---|---|---|---|---|
| 📊 市場 | `p4_market` | `market.py` | `src/services/ui2/market_vm.py::build_market_page_vm`（`MARKET_CARD_IDS`） | AUD §2.1 M-01～M-23；CAPMAP MK-01～25 | `PHASE4_MARKET_PAGE_WIREFRAME_2026-10-30`；`NEWUI2_WIREFRAMES_2026-11-02` §2；`NEWUI2_MARKET_TWII_CHART_WIRING_VISUAL_SPEC_2026-11-09`；`NEWUI2_MARKET_CAPITAL_FLOW_TEXT_WIREFRAME_2026-11-11`（草案）；MKT | DEC-117（P4 線框）、DEC-133（順序）、DEC-156（日 K）、DEC-157（順序 B）；資金籌碼僅草案，`I1144-WIRING-GATE` HOLD |
| 🎯 標的 | `p4_target` | `target.py` | `skeleton_vm.py::build_skeleton_page_vm` | AUD §2.2 T-01～T-14；CAPMAP TG-01～31 | `PHASE5_TARGET_PAGE_WIREFRAME_2026-10-31`；`NEWUI2_TARGET_READONLY_CONTRACT_AUDIT_2026-11-09` | DEC-121（雙模式 Q2=B）；資料接線皆 HOLD（§4） |
| 💼 持股 | `p4_hold` | `hold.py`（不呼叫 `render_cards`；AUD §1） | 同上 | AUD §2.3 H-01～H-09；CAPMAP HD-01～16 | `NEWUI2_HOLD_READONLY_CONTRACT_AUDIT_2026-11-09`；`NEWUI2_HOLD_W11_REMAINING_DRAFT_2026-11-05`（歷史） | DEC-141（版面／空槽 Q1～Q8，資料接線未授權） |
| 👤 我的 | `p4_me` | `me.py` | 同上 | AUD §2.4 U-01～U-07；CAPMAP ME-01～14 | `ME_PAGE_DRAFT_2026-10-25`（部分 SUPERSEDED） | DEC-083（Stage C）；真 OAuth／Sheet 未授權（`NUI2-ME-ACCOUNT-REAL-GATE`／`NUI2-AUTH-CONTRACT-GATE`） |
| 🗂 資料 | `p4_data` | `data.py` | 同上；canonical＝`src/services/ui2/data_page.py::data_page_canonical`（固定空殼，`real_canonical._data` 不讀 snapshot） | AUD §2.5 D-01、D-02（＋U-07）；CAPMAP DT-01～06 | `NEWUI2_P6_DATA_HEALTH_TEXT_WIREFRAME_2026-11-04`；`NEWUI2_DATA_FRESHNESS_OVERVIEW_TEXT_WIREFRAME_2026-11-12`（草案）；`NEWUI2_DATA_FRESHNESS_OVERVIEW_IMPLEMENTATION_DECISION_SHEET_2026-11-13`（Q1～Q7） | DEC-142、DEC-146（五頁導覽）、DEC-177（總覽 A+B，允許最小實作但不解除 Gate）；Q1～Q7 待回覆 |
| 跨頁 | — | `src/ui2/shell/app.py` | — | CAPMAP SY-01～08；AUD §7 | `FINAL_UI_CONTRACT_FREEZE_2026-11-02`；`NEWUI2_ACTIVE_PRESENTATION_CONTRACT_2026-11-03`；`NEWUI2_TOP_FIVE_APPROVED_VISUAL_AND_SAFETY_GATE_2026-11-07`；`docs/governance/{OLD_UI_FIRST_ADAPTATION_GATE_2026-11-08,UI_VISUAL_FIDELITY_GATE}.md` | DEC-142、DEC-146、DEC-124（五態） |

## 2. 資料矩陣

通則：**currency／fetched_at／PIT／Canonical|Shadow 於 UI2 VM 契約層一律 NOT AVAILABLE**（見 §0）；表內「as_of」欄只填 `data_cache/metadata.json`（及 `sector_flow/metadata.json`）實值。每格「→」指 AUD／CAPMAP 的逐欄內容，不重複。「驗收」欄＝§3 列號。接線欄圖例：**REAL shadow**＝`real_feed.py` 三 reader（`_read_twii`／`_read_twii_kbar`／`_read_regime`）之一；**FAKE**＝只有示意值；**NP**＝`⬜ 尚未提供`；**0 caller**＝L3 存在但 UI2 未用。

**`data_cache/metadata.json` 實值（FACT，main `5b180ea`；本沙箱親讀）**：`twii_ohlcv` last_updated 2026-11-09、row_count 4913；`finmind_inst` 2026-11-09、4939；`finmind_margin` 2026-11-09、4939；`finmind_m1m2` 2026-09-01、239、`fetch_outcome=NO_NEW_DATA`；`tw_pmi` 2026-10-01、172、`UNDETERMINED`。另 `data_cache/sector_flow/metadata.json`：last_updated 2026-11-09、row_count 1716、n_days 37。

| Dataset | 頁 | source／schema／unit | as_of（metadata） | PIT／freshness／missing reason | 授權（LIC §2） | Producer→Consumer | 接線 | 阻擋 Gate ID | 驗收 |
|---|---|---|---|---|---|---|---|---|---|
| D1 台股卡 `twii` | 📊 | `twii_ohlcv.parquet`（Yahoo `^TWII`）；指數點、卡不標單位 →AUD M-10、MK-03 | 2026-11-09（4913 列）；VM 有 `as_of`，無 fetched_at | 無 release_date；`is_stale` 日曆天>7（`shared/staleness.STALE_DAYS_DAILY=7`）；缺值走 Missing／灰／紅 →AUD M-10、M-22、X-08、X-09 | Yahoo NOT VERIFIED | cron→`market_twii_view_service.get_twii_trend_view`→`real_feed._read_twii`→`real_canonical.twii_card_spec` | **REAL shadow**；FAKE `12,345.67` | `I1140-TODAY-TZ`（條件式）、`DG-LIC`；資料日停滯與 #1124 HOLD 並存（因果 INFERENCE） | F02 |
| D2 20 根日 K | 📊 | 同 parquet 的 open／high／low／close；`shared/twii_ohlc_contract.validate_ohlc_window` →AUD M-09、MK-04 | 同 D1 | 同 D1；與卡片同源對帳不符則紅；volume 欄稀疏（AUD M-21c，沙箱無 pyarrow 未重算＝INHERITED） | 同 D1 | `get_twii_trend_view(20, with_ohlc=True)`→`real_feed._read_twii_kbar`→`real_canonical.kbar_chart_spec`→`components/html.py::kbar_chart_html` | **REAL shadow**；FAKE＝空槽 | `I1140-OHLC-GUARD`（條件式）、`DG-LIC` | F03 |
| D3 市場位階 | 📊🎯 | `allocation_service.get_macro_regime(strict=True, require_valid_risk_cap=True)`→`macro_state_locker`；類別值無單位 →AUD M-05、T-04、MK-02、TG-30 | **契約無 as_of**（畫面 `⬜ 資料日未提供`）；`macro_state.json`／`risk_cap_state.json` 不在 git（AUD §0-3，INHERITED） | 無 PIT；`BREADTH_PROXY_SCORING_ENABLED=False`（`shared/signal_thresholds.py` 親讀）→ 無 warroom 時恆 `unloaded`（未載入≠中性／安全）→AUD X-01 | 內部計算，不適用 | Legacy 寫 `warroom_summary`（UI2 無寫入點，INHERITED）→`real_feed._read_regime`→`real_canonical.regime_spec` | **REAL shadow 已接線，但沙箱恆未載入**；Cloud NOT VERIFIED。AUD 不列 READY | `NUI2-REALFEED-WARROOM-CONTRACT-INTEGRATION`、`NUI2-PREVIEW-CLOUD-STATE-FILES`、SG-10（位階 as_of；定義於 `NEWUI2_REAL_FEED_MAPPING_2026-11-03` §6，**非** BACKLOG 獨立 ID） | F04 |
| D4 Risk Cap | 📊🎯💼 | 不讀任何 producer；`RegimeFact` 欄位集被測試鎖住 →AUD M-06、T-05a、H-03、MK-05、HD-01 | — | `⬜ 無法判定` | — | `real_canonical._risk_cap_row` 固定 | 刻意固定（非缺口） | SG-06、`RC-VISIBILITY`、DEC-141 Q5 | F05 |
| D5 VIX／US10Y／利差／DXY／PMI 卡 | 📊 | 候選：`macro_snapshot.fetch_vix_block`／`fetch_us10y_block`、Yahoo `DX-Y.NYB`、`tw_pmi.parquet`（欄 date／pmi／source／fetched_at）、`macro_last_good/tw_pmi.json`（`is_proxy`）→AUD M-11～M-15、X-04～X-06、MK-09～13 | `tw_pmi` 2026-10-01、`UNDETERMINED`；VIX／US10Y／DXY 無落地檔（AUD） | PMI 未登錄 `CACHE_DATASET_CADENCE`（`src/data/macro/macro_cache_reader.py`；親讀僅含 twii／finmind_inst／finmind_margin／finmind_m1m2）→必 stale；DEC-070 僅語意未實作；利差三種定義未擇 | Yahoo、data.gov.tw（A 層 PARTIAL）NOT VERIFIED；FRED 無 LIC 列 | 無接線 | **NP**（FAKE 有示意值） | Issue #1110 題號 D1～D5（DEC-158 轉錄）、DEC-155、`NUI2-VIX-TWO-PATHS`、`VN1-PG-VIX-ASOF`、`NUI2-REALFEED-SG-02-SPREAD-DEF`／`-SG-03-PMI-DEF`、`ISSUE1110-DXY-UUP-LABEL` | F07 |
| D6 融資餘額 | 📊（不在 VM） | `finmind_margin.parquet` 欄 `margin_balance`（元）→L3 `src/services/margin_fact_service.py`（億）→AUD M-18、X-11、X-12、MK-19 | 2026-11-09（4939 列）；fetched_at 多為 bootstrap 單一時點（AUD，INHERITED） | 無 release_date；L3 四態；stale 7 日曆天（台北日）→AUD X-08 | FinMind A 層 PARTIAL、C 層 NOT VERIFIED（禁再散布、須標 FinMind） | cron→L3→**0 production caller**（`grep` 於 src／shared／scripts／app.py／app_ui2.py 僅 L3 本檔與 `shared/sector_flow_fact_thresholds.py` 提及，皆非 caller） | **FAKE／REAL 皆無**（0 caller） | `I1144-WIRING-GATE`、DG-SCOPE（`I1144-UI2-PREGATE`）、DG-PIT、DG-LIC、`I1140-MARGIN-SOURCE-TEXT`、`I1140-MARGIN-UNIT-MIX` | F08 |
| D7 板塊資金（衍生聚合） | 📊（不在 VM）；🎯 候選 | `data_cache/sector_flow/daily_net.parquet`（億）→L3 `src/services/sector_flow_fact_service.py`；並存 `sector_flow_service.get_sector_flow_view`（Legacy／🎯 候選）→AUD M-19、T-06、X-03、X-13、MK-19、TG-05 | `sector_flow/metadata.json` 2026-11-09 | stale 4 日曆天（`shared/sector_flow_thresholds.SECTOR_FLOW_STALE_MAX_CALENDAR_DAYS=4`）；`complete` 非覆蓋率；缺價剔除股數 L3 不外露 | TWSE／TPEX NOT VERIFIED；個股級對照落公開 repo | cron→L3→**0 caller** | 無 feed；🎯 產業 Top5＝NP | `I1144-WIRING-GATE`、`I1140-COVERAGE-MIN`（DG-COV）、DG-PIT、DG-LIC、DG-SCOPE、`I1144-DATA-STORAGE-DECISION`、`I1140-SECTOR-UNOBS-LABELS`、`I1140-SECTOR-DROPPED-PRICE`、`I1140-ETF-FAMILY-ABSENT`、`I1140-SECTOR-CRON-SCOPE` | F08 |
| D8 大盤外資淨買賣超 | 📊（不在 VM） | `finmind_inst.parquet` 欄 `foreign_buy`（億）、`source`、`fetched_at` →AUD M-20、X-02（同欄兩種 `source` 標籤，INHERITED：沙箱無 pyarrow） | 2026-11-09（4939 列） | **無專用 L3**；僅 `macro_cache_reader.load_extreme_risk_legs` 與 `scripts/` 讀 | FinMind PARTIAL | — | 無 | 外資 L3 未授權、另案（DEC-164 G-9；無獨立 ID）、`I1144-WIRING-GATE`、DG-PIT | F08 |
| D9 三大法人單日／國際趨勢／台股成交量 | 📊（不在 VM） | 舊 TWSE BFI82U（session）；`_market_blocks.intl_series`；volume 欄 →AUD M-21a～c、X-10、MK-14、MK-19 | — | 無乾淨 L3／freshness／PIT 規則 | TWSE／Yahoo NOT VERIFIED | Legacy only | 無（不可用） | 外資 L3 另案、`I1144-WIRING-GATE` | — |
| D10 精選：產業 Top5／候選 Top10／選股條件 | 🎯 | 候選 `fundamental_screener_service.get_ranked_picks`（FinMind 財報）、板塊 L3 →AUD T-03～T-08、T-13、CF-8；TG-05／07／08 | 財報 as_of `民國{y}Q{s}`，公告日對齊 NOT VERIFIED | `eps_high` 單季非 TTM；因子組合無 canonical 定義 | FinMind PARTIAL；MOPS NOT VERIFIED | 未接 | **NP**（FAKE 有示意） | SG-04／SG-13、`NUI2-REALFEED-SG-04-CANDIDATE-FACTORS`、`NUI2-PORT-INDUSTRY-RANK`、`I1144-DATA-STORAGE-DECISION`、DG-LIC | F11 |
| D11 即時查一檔（基本面／估值／籌碼／趨勢／產業） | 🎯 | 文件側 `fetch_metrics`／`get_financial_statements`／`get_chips_readout`（連網＋token）→AUD T-09～T-12、T-14；TG-02／04／14／15／18 | — | 趨勢／產業無定義（DEC-092 Q2）；Forward EPS／Fair Value 無來源（SG-08） | FinMind PARTIAL | 未接；輸入框 disabled | NP；REAL `queried=False` 只畫灰說明 | `TGT-01`（僅 `docs/vnext/*`，非 BACKLOG／DEC ID）、SG-08、`FUI-STAGE-G`、DG-LIC | F10／F12 |
| D12 持股／曝險／持股表 | 💼 | Google Sheet（`holdings_service.get_holdings`→`gsheet_portfolio`）→AUD H-01～H-09；HD-01～16 | 使用者手填；`html.py::hold_status_html` 資料日固定 `⬜ 資料日未提供` | 無現金／總資產來源；曝險「資料未備」；`hold_table_html()` 無參數 | 使用者資產（T5），不在 LIC 表 | 被 G2F 禁；程式 0 個 holdings producer | **NP／固定空槽**（FAKE 有「FAKE 組合 · 12 檔」，持股表仍空） | `NUI2-ME-ACCOUNT-REAL-GATE`、`NUI2-AUTH-CONTRACT-GATE`（G-F6）、G-F2、SG-05、SG-06、`NUI2-AGGREGATOR-IMPL` | F13 |
| D13 帳戶／Sheet／組合／觀察清單／設定 | 👤 | `me_account_service`、`portfolio_binding_service`（讀路徑會寫 `_oauth_state`，被禁）→AUD U-01～U-04；ME-01～07 | — | 一般設定無 canonical settings 契約（AUD U-04 NOT VERIFIED） | OAuth／Sheet（不在 LIC 表） | REAL `account=None` | FAKE 有（帳戶態示意）；REAL NP | `NUI2-AUTH-CONTRACT-GATE`、`NUI2-ME-ACCOUNT-REAL-GATE`、SG-11 | F14／F15 |
| D14 Decision Digest／Rule Registry | 👤（收合白名單） | `src/services/decision_digest_builder.py`；`shared/decision_digest_rules.RULE_ID_ALLOWLIST` →AUD U-05、U-06、§4.2；ME-08／09 | — | Digest `DataStatus` 六值 vs UI2 `FieldState` 五值，**無核准對映**（兩 enum 親讀；AUD §4.2） | — | `tests/test_decision_digest_invariants_guard.py::ALLOWED_CALLERS = frozenset()`（親讀）→ production caller 0 | NP | G-F4／G-F5、`FUI-STAGE-F`、`NUI2-REALFEED-NEXT-SESSIONFREE`（候選） | F16 |
| D15 資料健康度／來源與連線／資料日 | 🗂 | 固定 `data_page_canonical`，文案常數 `R_DATA_NOT_WIRED`；不讀 snapshot；舊 `summarize_data_registry`（session）→AUD D-01、D-02、U-07；DT-01～06、ME-10 | `metadata.json` 已有 `fetch_outcome`／`last_error`，台股卡經 `shared/upstream_state` 間接消費（AUD M-22）；🗂 頁不讀 | 畫面上沒有任何總覽新鮮度位置（AUD §2.5 後果）；`grep freshness_overview` 於 src／shared／app_ui2.py＝0 | — | 無 | **固定空殼**（FAKE／REAL 同一份） | DEC-177 Q1～Q7（`DEC177-FRESHNESS-IMPL-DECISION-SHEET`）、`NUI2-P6-WIREFRAME-CUSTOMER-DECISIONS` | F17 |

**未被 UI2 消費的落地檔**：`finmind_m1m2.parquet`（來源 CBC EF15M01，`scripts/update_macro_history.py` 檔頭自述；授權對照 LIC 的 CBC 列，非 FinMind 列）、`tw_pmi.parquet`；`grep -rlE "m1m2|tw_pmi|finmind_margin|finmind_inst|daily_net|margin_fact_service|sector_flow_fact_service"` 於 `src/ui2 src/services/ui2 shared/ui2_contract app_ui2.py src/services/market_twii_view_service.py`＝**無命中**（FACT）。故 UI2 實際消費的事實**只有三個**（卡、日 K、位階）；「只有這三個」屬單組 grep 全稱句＝待驗事項。

## 3. 功能／驗收矩陣

**完成層級定義**：**Preview-FAKE**＝只有示意值／固定占位／disabled；**REAL shadow**＝經 `real_feed` 唯讀讀真資料，仍是 Preview（非 production default）；**Production**＝`app.py` 預設路由已切換且資料／授權／Gate 皆通過。**Production 完成目前達成欄位數＝0**，證據：(1) `grep -c -i ui2 app.py`＝0，且 `tests/test_ui2_registration_and_boot.py::test_production_app_does_not_reference_ui2` 存在（FACT，PASS＝NOT VERIFIED）；(2) AUD §0 #1「預設路徑只到 FAKE 冷啟動」、#2「REAL 軸帶真值欄位只有 2 個」（INHERITED）；(3) CUT §1.1 C1～C7 目前狀態欄：C1 部分／C2 未滿足／C3 部分／C4 部分／C5 未滿足／C6 未滿足／C7 未滿足，**無一「已滿足」**（親讀該表，狀態正確性＝INHERITED，基準日 2026-11-10）；CUT §5.1「目前不可提 cutover」。故下表「完成層級」最高只到 REAL shadow。測試檔皆位於 `tests/`；`@pytest.mark.ui2_browser` 者 `pytest.ini` 預設不跑（`addopts` 含 `-m "not slow and not ui2_browser"`），CI 另有 `ui2-browser (streamlit …)`／`ui2-browser-gate`（`.github/workflows/pr-check.yml`；是否 required check＝NOT VERIFIED，該檔自陳 AI 無權限讀寫）。

| # | 頁 | 功能（→AUD／CAPMAP） | 驗收測試（檔::符號；函式存在已親驗，PASS＝NOT VERIFIED） | 完成層級 |
|---|---|---|---|---|
| F01 | 📊 | 頂列固定占位 →M-01 | `test_ui2_batch2.py::test_w1_top_row_is_fixed_placeholder_not_login` | Preview-FAKE（刻意占位） |
| F02 | 📊 | 台股卡 →M-10／M-22／M-23；MK-03 | `test_ui2_real_feed.py::test_twii_states_are_mapped_without_inventing_values`；`::test_twii_unknown_freshness_is_never_ok`；`::test_twii_broken_contract_is_loud_and_isolated`；`::test_twii_parquet_is_the_real_local_cache_and_feed_reads_it_without_hardcoding` | REAL shadow（資料停 2026-11-09，新鮮度偏弱 →AUD M-10；READY 不代表新鮮） |
| F03 | 📊 | 20 根日 K →M-09；MK-04 | `test_ui2_twii_kbar.py::test_every_contract_violation_makes_only_the_chart_red`；`::test_card_and_chart_must_be_the_same_snapshot_or_the_chart_is_red` | REAL shadow |
| F04 | 📊🎯 | 市場位階 →M-05／M-17a／T-04／T-11；MK-02、TG-30 | `test_ui2_real_feed.py::test_regime_unloaded_is_not_evaluated_with_the_l0_explanation`；`::test_regime_is_identical_across_pages`；`test_ui2_batch3.py::test_target_market_regime_follows_the_same_market_context` | REAL shadow（接線成立；沙箱實值恆「尚未載入」；Cloud NOT VERIFIED） |
| F05 | 📊🎯💼 | Risk Cap／行動欄 →M-06／M-07／T-05a／T-05b／H-03／H-04 | `test_ui2_real_feed.py::test_regime_fact_never_carries_risk_cap_fields`；`::test_risk_cap_stays_undeterminable_even_if_the_contract_returns_a_cap`；`::test_risk_cap_and_action_fields_are_identical_across_pages_and_feeds` | Preview-FAKE（固定「無法判定」／NP） |
| F06 | 📊 | 結論／主要風險／OneBrain →M-04／M-08／M-16 | `test_ui2_batch3.py::test_conclusion_has_no_direction_causality_or_action`；`::test_main_risk_never_says_safe_or_no_risk_and_never_lists_items`；`test_ui2_p2_primary_slot.py::test_onebrain_content_is_unchanged_only_its_position_moves` | Preview-FAKE（Real＝NP） |
| F07 | 📊 | VIX／US10Y／利差／DXY／PMI 卡 →M-11～M-15；MK-09～13 | `test_ui2_real_feed.py::test_every_unwired_real_field_states_its_reason` | Preview-FAKE（Real＝NP） |
| F08 | 📊 | 資金與籌碼（融資／板塊／外資／三大法人）→M-18～M-21c；MK-19 | UI2 側**無測試**（不在 VM／畫面）。L3 側：`test_margin_fact_service.py::test_stale_boundary_7_days_not_stale_8_days_stale`、`::test_scope_guard_not_wired_to_ui_or_real_feed`；`test_sector_flow_fact_service.py::test_real_data_cache_once`、`::test_no_market_wide_or_forbidden_fields`；外資無 L3、無測試（AUD §2.1 M-20） | 資料層存在、UI2 完成＝0（BLOCKED） |
| F09 | 🎯 | 雙模式切換 →T-01；TG-01 | `test_ui2_batch3.py::test_modes_are_never_fully_expanded_together` | Preview-FAKE（結構） |
| F10 | 🎯 | 搜尋框／CTA／加入觀察 →T-02／T-12；TG-02、TG-10 | `test_ui2_batch3.py::test_search_box_and_cta_present_in_both_modes_and_not_actionable`；`::test_lookup_writes_only_ui2_prefixed_session_state` | Preview-FAKE（disabled） |
| F11 | 🎯 | 精選 Top5／Top10／條件／完整表 →T-03～T-08／T-13；TG-05、07、08 | `test_ui2_p3_evidence_preservation.py::test_render_policy_guard_has_teeth`（條件 fold 在 `SHOWN_FOLDS`）；`test_ui2_real_feed.py::test_every_unwired_real_field_states_its_reason` | Preview-FAKE（Real＝NP） |
| F12 | 🎯 | 查一檔結果／snapshot →T-09a～d／T-10／T-14；TG-04、14、15、18 | `test_ui2_batch3.py::test_fake_lookup_result_is_labelled_fake_and_has_no_real_ticker` | Preview-FAKE（Real `queried=False`） |
| F13 | 💼 | W-11 版面／組合狀態／第一屏／持股表骨架 →H-01～H-09；HD-01～04、10、11 | `test_ui2_hold_w11_batch1.py::test_hold_layout_contract_all_states`；`::test_mutations_action_row`；`::test_mutations_body`；`::test_css_geometry_contract`；`::test_vm_still_carries_next_step_and_holdings_card`；`test_ui2_hold_header.py::test_anchors_and_cta_preserved` | Preview-FAKE（全頁無資料路徑） |
| F14 | 👤 | 連線狀態／帳戶動作／4 卡 →U-01～U-03；ME-01～04 | `test_ui2_batch3.py::test_me_three_account_states_have_the_right_primary_cta_and_disabled_actions`；`::test_me_signed_out_signed_in_unavailable_semantics_and_axes`；`test_ui2_real_feed.py::test_real_me_page_does_not_pretend_to_know_the_account` | Preview-FAKE（FAKE 帳號；Real `account=None`） |
| F15 | 👤 | 一般設定（Strategy／Notifications／Display）→U-04；ME-05～07 | 僅 `test_ui2_real_feed.py::test_every_unwired_real_field_states_its_reason` 泛掃；專屬驗收 NOT VERIFIED（AUD U-04 自述） | Preview-FAKE（NP） |
| F16 | 👤 | Digest Viewer／Rule Registry 收合 →U-05／U-06；ME-08、09 | `src/ui2/views/_page.py::SHOWN_FOLDS`（白名單）＋`test_ui2_p3_evidence_preservation.py::test_render_policy_guard_has_teeth`；`test_ui2_contract_teeth_pending.py::test_me_page_audit_surface_exception_does_not_allow_evidence_expanders` | Preview-FAKE（內容 NP） |
| F17 | 🗂 | 空殼 →D-01／D-02；DT-01～06 | `test_ui2_drawer_browser.py::test_data_page_is_honest_not_wired_shell`（`ui2_browser`，預設不跑）；`test_ui2_guards.py` 掃描清單含 `src/services/ui2/data_page.py`；**無預設 pytest 道的專屬 UI 測試** | Preview-FAKE（固定「尚未提供」） |
| F18 | 跨頁 | 五頁導覽 →SY-01 | `test_ui2_guards.py::test_only_five_pages`；`test_ui2_registration_and_boot.py::test_nav_has_exactly_the_five_pages`；`test_ui2_contract_teeth_pending.py::test_nav_is_exactly_five_pages_account_area_is_not_a_sixth` | Preview-FAKE |
| F19 | 跨頁 | 資料語意恰五態 →SY-04 | `test_ui2_guards.py::test_dec124_data_semantics_are_exactly_the_five` | 契約守衛 |
| F20 | 跨頁 | 正式 app 不引用 UI2 | `test_ui2_registration_and_boot.py::test_production_app_does_not_reference_ui2` | 契約守衛（證明 Production＝0） |
| F21 | 跨頁 | Real 軸只放行已接線欄位 →SY-07 | `test_ui2_real_feed.py::test_only_wired_fields_carry_data_across_injected_combinations`（`WIRED_PATHS` 於同檔）；`test_ui2_guards.py::G2F_IMPORT_ALLOWLIST`（僅放行 `get_twii_trend_view`、`get_macro_regime`、`real_canonical` 具名符號） | 契約守衛（allowlist 變更須客戶另裁） |
| F22 | 跨頁 | 版面／viewport／真瀏覽器 →SY-08 | `test_ui2_batch2.py::test_real_browser_viewport_acceptance`；`tests/ui2_viewport/measure_viewport.py`（錨點 `p2_nav_margin_160`）＋`docs/vnext/newui2_batch{2,3,3b}/viewport_measurements*.json`；`test_ui2_drawer_browser.py`（25 個 `def test_`）、`test_ui2_drawer_js_guard.py`（21 個） | Preview-FAKE 軸；Real 軸瀏覽器量測未做、真機／Safari／Cloud NOT VERIFIED（AUD §7.4） |

## 4. 缺口與阻擋（只引 ID，不解除）

| 缺口 | 證據索引 | 阻擋（ID） |
|---|---|---|
| 市場「資金與籌碼」不在 VM／畫面 | AUD M-18～M-21c；§2 D6～D9 | `I1144-WIRING-GATE`、DG-SCOPE／DG-COV／DG-PIT／DG-LIC（別名定義 AUD §6.0；對應 `I1144-UI2-PREGATE`、`I1140-COVERAGE-MIN`、`I1144-LIC-THREE-QUESTIONS`）、外資 L3 另案 |
| 5 張核心卡中 4 張（VIX／US10Y／利差／DXY／PMI） | AUD M-11～M-15；D5 | Issue #1110 題號 D1～D5（DEC-158 轉錄）、DEC-155、`NUI2-VIX-TWO-PATHS`、`VN1-PG-VIX-ASOF` |
| 今日結論／主要風險／OneBrain／行動欄 | AUD M-04／M-07／M-08／M-16／T-05b／H-04 | `NUI2-AGGREGATOR-IMPL`、`NUI2-PORT-CONCLUSION-CLAUSES`、`NUI2-PORT-MAIN-RISK`、`NUI2-CONCLUSION-REAL-FEED`、`FUI-STAGE-G` |
| 🎯 精選／查一檔／搜尋 | AUD T-02～T-11；D10／D11 | SG-04／SG-13（`NUI2-REALFEED-SG-04-CANDIDATE-FACTORS`）、`NUI2-PORT-INDUSTRY-RANK`、`I1144-DATA-STORAGE-DECISION`、DG-LIC |
| 💼 全頁無資料路徑 | AUD H-01～H-09；D12 | `NUI2-ME-ACCOUNT-REAL-GATE`、`NUI2-AUTH-CONTRACT-GATE`、G-F2、SG-05／06、`RC-VISIBILITY`、DEC-141 Q5 |
| 👤 真登入／Sheet／設定／Rule Registry | AUD U-01～U-07；D13／D14 | `NUI2-AUTH-CONTRACT-GATE`、SG-11、G-F4／G-F5、`FUI-STAGE-F` |
| 🗂 帶真值的新鮮度總覽 | AUD D-01／D-02；D15；GAP §2.3 軸 4 | DEC-177 Q1～Q7（`DEC177-FRESHNESS-IMPL-DECISION-SHEET`）；`G2F_IMPORT_ALLOWLIST`／`WIRED_PATHS` 變更須客戶另裁；`NUI2-P6-*` |
| 資料日停滯 | AUD M-10、X-09；§0 | 每日資料 PR #1124～#1126 HOLD（DEC-174 清單；PIT NOT VERIFIED） |
| Cutover | CUT §1.1／§5.1 | `NUI2-CUTOVER`、`NUI2-REMOVAL-GATE`、`NUI2-CAPMAP-3COL`（CAPMAP：critical 8、major 49、minor 34、none 9；真資料「是」僅 5 列＝親讀 §3） |
| Real 軸真瀏覽器量測、真機 | AUD §7.4；CUT §5.2 | `NUI2-ACC-REAL-DEVICE`、`NUI2-PREVIEW-CLOUD-STATE-FILES` |

## 5. 已知文件矛盾（只記錄；不建議放寬守衛、不修改 Active Contract）

| # | 矛盾 | 證據（可 grep） | 標籤 |
|---|---|---|---|
| C-1 | Active Contract 正文「四頁，不得新增第五頁」vs 現行五頁；頂部 📌 已註，正文標題仍四頁 | `NEWUI2_ACTIVE_PRESENTATION_CONTRACT_2026-11-03.md` `## §2 四頁正式 Human UI 與每頁優先順序`；`tests/test_ui2_guards.py::test_only_five_pages` | FACT |
| C-2 | 守衛釘住舊標題：`tests/test_ui2_active_contract_docs.py` 斷言 `"## §2 四頁正式 Human UI"`、`"## §5 👤 我的 → 資料健康度"`。改標題會令守衛紅；任何「修正文」須同步改測試＝守衛調整，需客戶裁示 | 同檔（親讀斷言字串） | FACT；後果＝INFERENCE |
| C-3 | 資料健康度落點：DEC-128／Active §5＝👤 我的；DEC-142／146＝🗂 資料；CUT 自述不裁決；`src/ui2/views/_page.py` 註解仍寫「〔→ P6 資料健康度〕」 | CUT「資料健康度的最終落點」、`_page.py` | FACT。**DEC-177 fence 已表態**：完整資料健康度仍保留在 👤 我的既有契約位置；🗂 本批只處理新鮮度摘要，不搬移入口（`docs/DECISIONS.md` DEC-177 fence；客戶訊息轉錄，逐字一致性 NOT VERIFIED）；`DEC176-HEALTH-ESCALATION-1` 是否結案由總管判定，本文件不裁決 |
| C-4 | 台股主圖：舊 Gap Audit／MARKET_READONLY 稱「誠實空槽」vs 現碼 `market.py` 已有 `kbar_chart_html` | `src/ui2/views/market.py`；AUD CF-1／ST-1 | FACT |
| C-5 | Real feed 事實數與文案：實際 3 reader；`src/ui2/shell/app.py::_FEED_LABELS`（及 `tests/test_ui2_drawer_browser.py`）寫「只接 2 項真資料」；`shared/ui2_contract/text.py::REAL_PREVIEW_BANNER_NOTE` 寫「僅台股與市場位階為真資料」 | 三處皆親讀；AUD §7.3 D 已登記（登記，不動） | FACT |
| C-6 | 導航演進：手機底部四格／左 rail（Wireframes §0.4）→ DEC-134 抽屜 → DEC-146 頂部兩列 | `NEWUI2_WIREFRAMES_2026-11-02.md` `### §0.4`；CUT §1.0 | FACT |
| C-7 | 🗂 文件狀態：`NEWUI2_DATA_PAGE_FIVE_NAV_PROPOSAL_2026-11-06.md` 自標歷史；新鮮度線框仍標「草案」，決策單稱「完整 A+B 做不出來」 | 各檔頭 📌 | FACT |
| C-8 | 市場頁順序：DEC-133 G-3 被 DEC-157 有意取代；舊 P2 線框仍描述前者 | `src/ui2/views/market.py` 檔頭 docstring | FACT |
| C-9 | `docs/BACKLOG.md` 同檔新舊並存（`I1144-A2-IMPL` 4 處命中）；`FUI-STAGE-F` 狀態「open」vs 已有 `decision_digest_builder.py` | AUD ST-11；CUT §4-8 | INFERENCE（讀舊列會誤判） |
| C-10 | AUD 引用的「1705 passed、82／82 viewport、41 passed」為 FAKE 軸、調查者自報、非本次執行，不可當 Production 驗收證據 | AUD §0 #10、§7.2 | INHERITED |
| C-11 | AUD 的 PR 證據過期（head／base／分支資料日） | §0；§7-1 | FACT |

## 6. NOT VERIFIED 清單

1. 所有 pytest／AppTest／Playwright／viewport 的 PASS（本批未跑，亦未驗 CI 實況）。
2. Streamlit Cloud 部署實況：位階實值、`macro_state.json` 是否存在、正式 UI 是否接線。
3. 授權原文與 C 層（本專案已取得授權）：FinMind／TWSE／TPEX／MOPS／data.gov.tw／CBC／Yahoo／FRED（FRED 無 LIC 列）。
4. parquet 內容（沙箱無 `pyarrow`）：`finmind_inst` `source` 標籤斷點、`volume` 稀疏度、板塊與外資差距——全為 AUD 轉述。
5. #1124～#1126 分支資料的 PIT、是否為交易日、cron 近期成功率；停更因果。
6. AUD／CAPMAP／MKT／LIC／CUT 各列內部正確性（本檔只確認編號存在與少數引用）；需非作者複核（`DEC174-B1-INDEP-QA`）。
7. branch protection／`ui2-browser-gate` 是否 required。
8. 「UI2 只消費三個事實」「`margin_fact_service`／`sector_flow_fact_service` 0 caller」為單組 grep 全稱句。
9. AUD U-04（一般設定）、U-06（Rule Registry）、F15 專屬驗收。
10. DEC fence 與客戶原始訊息的逐字一致性（原始對話不在 repo）。

## 7. 報告與親驗不一致（以親驗為準）

| # | 報告說法 | 親驗結果 | 影響 |
|---|---|---|---|
| 1 | AUD（及 r4 引述）：#1124 head `fc447def`、base `043a4d21`；分支資料日 finmind 到 11-11、`twii_ohlcv` 到 11-10 | `gh api` 現況：head `3cd3f525`／`cf4739c5`／`1654ae60`，base `85c65dfc`，仍 open、未併；#1124 內文現為 finmind 到 11-12、`twii_ohlcv` 到 11-11。PR **標題**仍是「2026-11-10」，與 head commit 日期（11-12）不同 | AUD X-09／§6／MKT §0 的分支日期落後一天；已於 §0 更正，AUD 原文未改（本批不動） |
| 2 | r5：🗂 頁「**無專屬測試**」 | 存在 `tests/test_ui2_drawer_browser.py::test_data_page_is_honest_not_wired_shell`（`ui2_browser` marker，預設 pytest 不跑）；AUD D-01 測試欄只列 `test_ui2_guards.py` | 更正為「無預設 pytest 道的專屬測試，只有瀏覽器道一支」（F17） |
| 3 | r4 §C：Gate `I1140-DROPPED-PRICE` | BACKLOG 實際 ID 為 `I1140-SECTOR-DROPPED-PRICE`（`I1140-DROPPED-PRICE` 0 命中） | §2 D7 用正確 ID |
| 4 | r4 §C：Gate `NUI2-REALFEED-SG-10`（「我已 grep 確認存在」） | BACKLOG／DECISIONS **0 命中**；SG-10 定義於 `NEWUI2_REAL_FEED_MAPPING_2026-11-03.md` §6 | §2 D3 改寫為「SG-10（非 BACKLOG 獨立 ID）」；BACKLOG 只有 `NUI2-REALFEED-SG-01…04` 候選列 |
| 5 | r4 §B 通則：「data.gov.tw／FRED 授權 NOT VERIFIED」 | LIC §2：data.gov.tw A 層 **PARTIAL**（OGDL 轉錄本）、B／C NOT VERIFIED；FRED **無列**（非 NOT VERIFIED，是未登錄） | §0、§2 D5 已修 |
| 6 | r4 D7：板塊 as_of 僅寫「視窗＝最新交易日」 | `data_cache/sector_flow/metadata.json` 有 last_updated 2026-11-09、row_count 1716、n_days 37 | 補入 §2 |
| 7 | r5：`test_production_app_does_not_reference_ui2` 未註檔 | 位於 `tests/test_ui2_registration_and_boot.py`（非 `test_ui2_guards.py`） | F20 已標檔 |
| 8 | r5：`test_ui2_batch2.py::test_*viewport*`（萬用字元） | 該檔僅 `test_real_browser_viewport_acceptance` 一支符合 | F22 已具名 |
| 9 | 本沙箱 `origin/main` 追蹤 ref 一開始是 `85c65df`（過期），與 r4／GAP 的 `5b180ea` 不符 | `git fetch origin main` 後與 `gh api` 同為 `5b180ea` | 差異 diff 一律以 fetch 後 `origin/main` 為準；僅更新遠端追蹤 ref，未動工作樹 |
| 10 | GAP §4.2-5（沿用）：「UI2 VM 契約沒有 fetched_at」 | 精確說法：VM 欄位不存在，但 `real_canonical` 內 `FETCHED_AT_MISSING` 用儲存層 fetched_at 判日 K 收盤 | §0 採精確說法 |

> 未發現不一致（親驗吻合）：AUD 的 M-／T-／H-／U-／D- 編號全存在；CAPMAP MK-02、TG-30、HD-03／10／11、SY-01、DT-01 存在，100 列分佈 MK25／TG31／HD16／ME14／DT6／SY8；`real_feed.py` 三 reader；`metadata.json` 五個 dataset 值；`G2F_IMPORT_ALLOWLIST`／`WIRED_PATHS`／`SHOWN_FOLDS` 位置；`app.py` ui2 引用 0；`FreshnessInfo` 僅 `as_of`／`source`；單組 diff 結論與 GAP §K6 一致。
