# NEWUI2 五頁資料契約稽核（A1 欄位契約＋B1 安全面向；docs-only）— 2026-11-12

> **性質**：稽核證據。**不是 SSOT、不是授權**。未修改任何 src／tests／workflow／資料；不接線、不解除任何 Gate、不把研究候選當成核准。
> **基準**：**程式／資料事實基準 main `7eb48d6c`**（#1161～#1163 已含在其歷史內）；其後 main 的變動僅為 docs（#1166，main `dae78eea`；`git diff --stat 7eb48d6c origin/main` 核實只有 `docs/DECISIONS.md` +25 行，無 src／tests／資料／workflow 變動，故本文程式與資料斷言不受影響）。**資料量測日 2026-11-12**（沙箱時鐘；本機 `data_cache` 最新資料日 2026-11-09）。引用一律「檔:符號」（`CLAUDE.md` §8.2.A.0 規則 1），**本文不引用行號**（3C 文件重整後 BACKLOG 等行號已漂移，見 §5 ST-14）。
> **證據來源**：本文整理 5 份單組調查報告（程式追溯、文件契約、反向缺口、市場契約、UI2 安全）並加上本文自行重核（§10）。**5 份調查報告為 session 暫存、未入 repo**，因此文內**不以其章節／編號為引用**；凡僅出自調查報告而本 PR 未重核者，一律標「調查者 FACT／本 PR 未重核」。文內的 CF-n／ST-n 只是**本文內部編號**（衝突／過期），不是 repo ID。
> **授權來源**：**已登錄於 main：DEC-174（PR #1166，main `dae78eea`）**＝客戶 2026-11-12 對 Batch 1 的「方案 B」裁示（原句見 DEC-174，本文不轉錄；本文不引申其授權範圍）。**消歧**：此「方案 B」是 Batch 1 的選項，與 DEC-165／166／167／170／171 在 Issue #1144 脈絡內各自出現的「方案 A／B」（Digest A2、B 線 Gate 研究、CI 修復 fallback、公開 repo 資料曝露稽核）**不同義**，不得互相引用授權範圍。
> **圖例**：**FACT**＝本回合讀碼／讀檔／執行直接確認；**APPROVED（轉錄）**＝文件記載客戶已裁示，**非本文確認**；來源類別不一：DEC-155 為 ChatGPT 獨立裁示（非客戶逐字）、DEC-158 自陳「非客戶逐字原文」、DEC-158～171 多為 Issue 轉錄或 AI 摘要，依 DEC-172 D3 須逐項核查來源，**本文未逐項核查，不得據此擴權**；**RECOMMENDATION**＝AI 推薦，非裁示；**HOLD**＝客戶裁示維持未授權；**INFERENCE**＝由 FACT 推得、未實測；**NOT VERIFIED**＝未驗，不得當前提。
> **稽核分類**：READY／BLOCKED／NOT VERIFIED **僅為本文的稽核分類**，**不是**正式 Data State enum（正式資料語意只有 `shared/ui2_contract/models.py::FieldState` 的五態，DEC-124；`tests/test_ui2_guards.py::test_dec124_data_semantics_are_exactly_the_five` 釘住）。READY＝接線與資料契約面成立且有守衛（**僅指畫面欄位已有真值且受守衛；不等於資料新鮮、不等於可對外呈現**），**不含**授權條款（全域前提：TWSE／TPEX／data.gov.tw／Yahoo 授權原文 NOT VERIFIED，FinMind 僅 PARTIALLY VERIFIED，故**沒有任何欄位是 license-verified**）；BLOCKED＝至少一個未關閉的 Gate／缺 L3／缺定義；NOT VERIFIED＝缺證據。
> **單組聲明**：本文由單一文件組整理 5 份單組調查並自行重核關鍵事實（§10），**未經第二組獨立複驗**（`CLAUDE.md` §-2 規則 6）。全稱句只能當**待驗事項**，不得作為後續動作前提，不得寫進 commit／PR 當已完成事實。**非作者獨立 QA：待做。**

---

## 0. 結論先行

| # | 結論 | 標籤 |
|---|---|---|
| 1 | **預設路徑（無 `?ui2_dev=1`）只到 FAKE 冷啟動，0 個真值。** Real feed 只能從開發面 selectbox 選到；`app.py` 對 UI2 的引用為 0 | FACT（§10 V1） |
| 2 | **REAL 軸帶真值的畫面欄位只有 2 個**：台股卡（收盤）與 20 根日 K，兩者都是同一份 `data_cache/twii_ohlcv.parquet`（同一 service 讀兩次）。其餘全是 `⬜ 尚未提供` 或固定占位 | FACT（§10 V2） |
| 3 | **市場位階已接線，但在 UI2 獨立 session 目前恆為「⬜ 尚未載入」。** 因果鏈（讀碼）：`allocation_service.get_macro_regime` 讀 `st.session_state['warroom_summary']`，其寫入點只在 Legacy（`src/ui/tabs/macro/section_state.py`、`section_traffic_light.py`、`src/services/warroom_apply.py`），UI2 三目錄 0 寫入；無 warroom 時 `macro_state_locker.get_macro_state` 另讀本地 `macro_state.json`／`risk_cap_state.json`（兩檔在 `.gitignore`、`git ls-files`＝0、沙箱不存在），**但旗標 `shared/signal_thresholds.BREADTH_PROXY_SCORING_ENABLED=False` 時 `_nowr_no_real_breadth` 成立，即使狀態檔有效也回 `unloaded`**（DEC-074 B／DH-REGIME-NOWARROOM）。本沙箱實測 `unloaded`。結論取決於兩個條件：旗標值、以及 UI2 session 是否有人寫入 `warroom_summary`。**部署端 NOT VERIFIED 的範圍縮到這兩點**（旗標為 repo 常數，本 SHA 讀為 False；未驗的是部署版本是否同 SHA、以及部署 session 是否被寫入） | FACT（沙箱）；部署端 NOT VERIFIED |
| 4 | **「市場資金與籌碼」區塊在 UI2 的 VM 契約中不存在。** 融資 L3（`margin_fact_service`）與板塊 L3（`sector_flow_fact_service`）在 `src/ui2`、`src/services/ui2`、`shared/ui2_contract` 引用數＝0；大盤外資**沒有** L3；三大法人（外資／投信／自營）UI2 無入口 | FACT（§10 V3） |
| 5 | **🗂 資料頁整頁是固定空殼且不讀 snapshot；💼 持股頁沒有任何資料路徑**（資料日、判得出是寫死字樣，持股表 `hold_table_html()` 無參數） | FACT（§2.4、§2.5） |
| 6 | **跨層口徑問題已有實證**：`finmind_inst.parquet` 同欄兩種 `source` 標籤（4920／19 列）；板塊「外資分項」與 FinMind「大盤外資」同日不等（37 共同日，中位絕對差 55.4 億，最大 239.6 億；窗內橫跨 source 斷點，拆分後新標籤 19 日中位 49.19／最大 140.28、舊標籤 18 日中位 60.18／最大 239.57，見 X-03）；板塊 stale 4 日 vs 融資／外資／TWII 7 日；成交量備援會「猜單位」（**僅 INFERENCE，未實際觸發**） | FACT／INFERENCE（§4、§10 V4／V5／V8） |
| 7 | **新鮮度判定偏弱**：日曆天>7 才過期、無交易日曆、基準日因路徑而異（TWII 卡用主機 `date.today()`）；as_of 2026-11-09 時 `age_days=3`、`is_stale=False`，卡片無過期提示。`git log -- data_cache/twii_ohlcv.parquet` 最後一筆資料 commit＝`4432d5a7`（2026-11-10 08:46 +0800，資料日 2026-11-09），此後 main 無新資料 commit；固定來源字樣仍寫「每日更新」。**停更原因（推論）**：每日資料 PR #1124～#1126 open 未合併（既有 HOLD），見 X-09；#1124 內文「資料狀態」段（本回合重讀）顯示：分支上 `finmind_inst`／`finmind_margin` 資料日到 2026-11-11、`twii_ohlcv` 到 2026-11-10 | FACT（§10 V7、V10、V15）；原因 INFERENCE |
| 8 | **B1：未發現「契約內、可重現、不涉及新設計決策」的缺陷。** 另有 Visual Gate 候選 VG1／VG2、文案漂移（「只接 2 項真資料」）、GUARD-GAP G1／G2；Real 軸瀏覽器量測因環境限制**未做** | FACT／NOT VERIFIED（§7） |
| 9 | **所有 Gate 維持 HOLD／未授權**（§6）。本文不暗示任何 Gate 已解除、任何接線已授權 | FACT |
| 10 | **原則：畫面完成或測試綠燈 ≠ 資料可用。** 本文引用的 82／82 viewport、1705 passed、41 passed 等皆為 **FAKE／Preview 軸**、調查者自報、本 PR 未重跑；它們不證明任何 Real 欄位有資料、新鮮或可對外呈現。READY 僅指「接線＋契約面成立」 | FACT |

### 0.1 不可直接採信的欄位（彙整；細節見括號內章節）

- **外資序列 `finmind_inst.parquet`**（X-02）：同欄兩種 `source` 標籤，多日彙總跨斷點；`:Foreign` 成分 NOT VERIFIED。
- **板塊「外資分項」**（X-03）：與 FinMind 大盤外資同日不等（中位約 49～60 億），不可並列、加減、同標籤顯示。
- **台股卡／日 K 的「新鮮」感**（X-09、M-10、M-23）：資料日停在 2026-11-09，固定字樣仍寫「每日更新」；停更疑為每日資料 PR #1124～#1126 未合併（INFERENCE）。
- **成交量序列**（X-10）：Legacy 備援會猜單位當「億元」（INFERENCE 偏差）；UI2 不顯示，但日後不可重用。
- **融資 L3 的來源字樣**（X-12）：`MARGIN_SOURCE_TEXT` 含「全市場」，FinMind 範圍 NOT VERIFIED。
- **PMI**（M-15）：`is_proxy: true`、與景氣燈號意義不同，DEC-155（ChatGPT 獨立裁示）不得為正式訊號。
- **市場位階**（M-05）：目前恆為「⬜ 尚未載入」，**不可讀成「中性」或「安全」**。
- **FAKE 值**（預設路徑全部數值，如「FAKE 組合 · 12 檔」「無需處理（FAKE）」）：只是示意，不是資料。

---

## 1. 範圍與方法

- 五頁＝`src/ui2/views/{market,target,hold,me,data}.py`（📊 市場、🎯 標的、💼 持股、👤 我的、🗂 資料）。
- 資料模式用語：**FAKE**＝`preview_feed.get_preview_page_vm`→`scenarios.fake_canonical`（值以 `FAKE` 標示）；**REAL**＝`real_feed.read_real_snapshot`→`real_canonical`（只有 3 個事實：台股卡、日 K、位階）；**STATIC／FIXED**＝`html.py` 或契約寫死的字樣／槽；**NP**＝NOT_PROVIDED＝`⬜ 尚未提供` capability marker（兩 feed 同）。
- 來源：5 份單組調查（程式追溯、文件契約、反向缺口、市場契約、UI2 安全）＋本回合重核（§10）。**欄位數量（45／46 等）屬人工建模計數，本回合未重算**，僅作量級參考。
- **畫面完成或測試綠燈 ≠ 資料可用**（見 §0-10）：判斷「可用」要同時看 (a) 是否有真值來源、(b) 資料日與新鮮度、(c) 授權與 PIT 證據；畫面與守衛測試只回答版面與契約。
- 渲染白名單：`src/ui2/views/_page.py::SHOWN_FOLDS`＝`(p4_target,conditions)`、`(p4_me,digest)`、`(p4_me,registry)` 三個收合區；其餘 L2／L3 區塊在 VM 但**不渲染**（FACT，已讀碼）。`hold.py` 不呼叫 `render_cards`（FACT，grep）。

---

## 2. 五頁欄位對應表

**欄位合併規則**（欄數過多，為可讀性所做）：① 「page」改為各小節標題；② 「現有欄位與單位」併入「canonical source」欄；③ 只有「同一頁內 canonical、producer、Gate 三者**完全相同**」的 NP 欄位才合併為一列（M-07、U-01、U-03、D-01、D-02）；三者任一不同一律拆列（本版已把原 M-17、M-21、T-05、T-09、H-06 拆開）；④ 「Coverage／PIT／License」欄的全域前提（上述授權未驗）不逐列重複，僅記該列特有者；⑤ 測試欄只列代表性測試（檔::函式，均已 grep 確認存在），**不證明目前綠燈**。FAKE 值一律標示 FAKE，不在表內當作資料。

**完整性檢查（機械式，本回合執行）**：以 `python -I` 呼叫 `real_canonical(page, read_real_snapshot())` 列舉五頁 REAL canonical 的所有欄位鍵（`current_state`、`context_rows`、`action_needed`、`next_step`、`cta`、`cards`、`sections[*].fields`、`conclusion`、`main_risk`、`kbar`、🎯 `target.search`／`target.lookup`），逐一對照下列各列：**以標籤對應後無實質遺漏**（REAL canonical 的鍵數、以及其中需靠欄位標籤才能對上本表列的比例，本文未重數，故不引用數字；對應不是鍵名逐字相同）。已含 QA 指出的 🎯 `full`、`lk_research`、💼 `why`／`raw`、👤 主 CTA。**HTML 內不經 VM 欄位的固定字樣**（頂列、導覽、標題、💼 `hold_*_html` 槽）另以 `html.py` 符號列入（M-01、H-02、H-06 等）；此外的純版面元素（導覽列本身、分隔線）不列。本表**不保證**窮舉畫面上每個像素或字串。

表頭：`#`｜section／UI field｜資料模式｜canonical source／欄位單位｜producer→consumer｜資料日／抓取日／發布時點資格｜缺值／過期語意｜Cov／PIT／Lic｜UI2／Digest｜Gate｜測試｜分類

### 2.1 📊 市場（`p4_market`）

| # | section／UI field | 模式 | canonical／欄位單位 | producer→consumer | 日期／發布資格 | 缺值／過期語意 | Cov／PIT／Lic | UI2／Digest | Gate | 測試 | 分類 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| M-01 | 頂列 Active Sheet／帳號 | STATIC | 無 | `html.py::top_status_row_html` 寫死 | — | 固定 `⬜ 尚未提供`（不讀 `ui2_account`／query） | — | UI2 是；Digest 否 | `NUI2-AUTH-CONTRACT-GATE` | `test_ui2_batch2.py::test_w1_top_row_is_fixed_placeholder_not_login` | BLOCKED（刻意固定占位） |
| M-02 | 資料模式 banner | STATIC（依 `is_fake`） | `text.py::PREVIEW_BANNER_TEXT`／`REAL_PREVIEW_BANNER_*` | `vm_common._banner_for`→`html.banner_html` | — | — | — | UI2 是 | 無 | `test_ui2_real_feed.py::test_real_scenario_axis_is_separate_from_fake_scenarios` | READY |
| M-03 | 主 CTA「🚀 更新今日戰情」 | STATIC | 無 | `vm_common.cta_from_spec`（`enabled=False` 寫死） | — | disabled＋原因句 | — | UI2 是 | SG-01 | `test_ui2_real_feed.py::test_real_vms_create_no_actions_and_no_forbidden_terms` | BLOCKED（刻意） |
| M-04 | 今日結論 | FAKE／REAL=NP | 無 producer（文件稱 L0 `shared/market_conclusion.build_market_conclusion` 可 reuse；**程式未接，可否直接接 NOT VERIFIED**） | `real_canonical._market` | — | NP | — | 否 | `NUI2-PORT-CONCLUSION-CLAUSES`、`NUI2-CONCLUSION-REAL-FEED` | `test_ui2_batch3.py`（結論句型） | BLOCKED |
| M-05 | 現在狀態＝市場位階 | FAKE（`震盪` 寫死）／**REAL 已接線** | `RegimeFact(regime,light,source,is_loaded)`；類別值，**無 as_of、無單位** | `allocation_service.get_macro_regime(strict=True, require_valid_risk_cap=True)`→`macro_state_locker.get_macro_state`→`real_feed._read_regime`→`real_canonical.regime_spec` | **契約無資料日**，畫面寫 `⬜ 資料日未提供`；禁以 `cl_ts` 頂替（SG-10） | `is_loaded=True`→值；`unloaded`→`not_evaluated ⬜ 尚未載入`；`unevaluated:breadth_unavailable`→`undeterminable`；讀取例外→紅 | PIT 無；`macro_state.json`／`risk_cap_state.json` **不在 git**（`.gitignore` 列出，`git ls-files`＝0） | UI2 是；Digest 走同函式但 **Digest 0 production caller** | 無（已接）；`NUI2-REALFEED-WARROOM-CONTRACT-INTEGRATION`（條件式）；`NUI2-PREVIEW-CLOUD-STATE-FILES`（NOT VERIFIED） | `test_ui2_real_feed.py::test_regime_unloaded_is_not_evaluated_with_the_l0_explanation`、`::test_regime_is_identical_across_pages` | **NOT VERIFIED**（接線成立；實值在 UI2 獨立 session 目前恆為未載入，取決於旗標與 session 寫入，部署端未驗）——**不列 READY** |
| M-06 | Risk Cap（context row） | FIXED（兩 feed 同） | 不讀任何 producer；`RegimeFact` 欄位集被測試鎖住不含 exposure | `real_canonical._risk_cap_row` | — | `undeterminable ⬜ 無法判定` | — | UI2 固定；Digest 另有 `risk_cap` 路徑（兩邊有意不同） | SG-06／RC-VISIBILITY／C2b／DEC-141 Q5 | `::test_regime_fact_never_carries_risk_cap_fields`、`::test_risk_cap_stays_undeterminable_even_if_the_contract_returns_a_cap` | BLOCKED（刻意不接） |
| M-07 | 是否需行動／下一步 | NP（FAKE cold 的「下一步」例外，見 §7 N2） | 無 | `vm_common.aggregator_pending_field` | — | `⬜ 尚未提供（待系統動作整合）` | — | 否 | `NUI2-AGGREGATOR-IMPL`（blocked-on-customer） | `::test_risk_cap_and_action_fields_are_identical_across_pages_and_feeds` | BLOCKED |
| M-08 | 今日主要風險 | FAKE／REAL=NP | 無 producer | `real_canonical._market` | — | NP；FAKE cold 為 `⬜ 尚未載入，請按更新` | — | 否 | `NUI2-PORT-MAIN-RISK` | `test_ui2_batch3.py`（退化句） | BLOCKED |
| M-09 | 台股走勢主圖（20 根日 K） | FAKE=空槽；**REAL 已接線** | `data_cache/twii_ohlcv.parquet` 欄 open／high／low／close（指數點）；OHLC 契約 `shared/twii_ohlc_contract.validate_ohlc_window` | `market_twii_view_service.get_twii_trend_view(20, with_ohlc=True)`→`macro_cache_reader.load_twii_ohlc`→`real_feed._read_twii_kbar`→`real_canonical.kbar_chart_spec`→`html.kbar_chart_html` | 資料日＝parquet `date` 最大值；`fetched_at` 僅供「已收盤」判定、不顯示；Yahoo EOD | `ok=False`→灰；`ohlc_ok=False`→灰；契約違反／與卡片不同源→紅；不足 20 根照實少畫；stale 與卡片同字樣；副標固定「加權指數日 K｜單位：指數點｜顏色只比較當日開盤與收盤，不是相對前一日漲跌」（`html.KBAR_SUBTITLE`）、文字圖例「紅＝收盤＞開盤／綠＝收盤＜開盤／灰＝收盤＝開盤」（`html.KBAR_LEGEND`，DEC-156 A） | 來源 Yahoo `^TWII`（授權 NOT VERIFIED）；無 `release_date` | UI2 是；Digest 否 | 無擋接線；條件式 `I1140-OHLC-GUARD`（with_ohlc 路徑未套卡片價格守衛） | `tests/test_ui2_twii_kbar.py::test_every_contract_violation_makes_only_the_chart_red`、`::test_card_and_chart_must_be_the_same_snapshot_or_the_chart_is_red` | READY（限接線＋契約；**不代表資料新鮮**，見 M-10；MA／量／更長視窗 BLOCKED，需 Visual Gate） |
| M-10 | 核心卡：台股（`twii`） | FAKE（`12,345.67`）／**REAL 已接線** | 同上，欄 `close`；顯示 `f"{x:,.2f}"`，**卡片不標單位** | `get_trend_view(1)`→`real_feed._read_twii`→`real_canonical.twii_card_spec` | as_of＝parquet 末列；`source` 字樣為常數 `TWII_SOURCE_TEXT`（**非** parquet 的 `source` 欄、無 `fetched_at`） | `ok=False`→Missing；`failed`→紅；`is_stale=True`→`⚠ 過期 N 天`；`None`→`⚠ 可能已過期`；close≤0／非有限／`age_days<0`→契約違反紅 | 同上 | UI2 是；**Digest market 段不含 TWII** | 無（卡片層） | `::test_twii_parquet_is_the_real_local_cache_and_feed_reads_it_without_hardcoding`、`::test_twii_unknown_freshness_is_never_ok`、`::test_twii_broken_contract_is_loud_and_isolated` | READY（接線＋契約）；**資料新鮮度偏弱**：`git log -- data_cache/twii_ohlcv.parquet` 最後一筆資料 commit＝`4432d5a7`（2026-11-10 08:46 +0800，內容資料日 2026-11-09），此後 main 無新資料 commit（本回合重驗，main 仍為 `7eb48d6c`）；11-10／11-11 是否為交易日 NOT VERIFIED。**FACT**：每日資料 PR #1124（含 `twii_ohlcv.parquet` 增量至 2026-11-10）open 未合併，屬既有 HOLD（#1124～#1126）；停更疑為 PR 未合併而非 cron 失敗＝INFERENCE，cron 成功率 NOT VERIFIED（詳 X-09）。READY 標籤**不代表資料新鮮** |
| M-11 | 核心卡：VIX | FAKE／REAL=NP | 候選兩條：`macro_snapshot.fetch_vix_block`（yfinance 直連，無 as_of）／session `macro_info['vix']`；兩者皆未接 | `real_canonical` `_not_provided`（`此項目尚未開放`） | DEC-070「只用已完成收盤」僅語意裁示，程式未實作（`VN1-PG-VIX-ASOF`） | NP | Yahoo 授權 NOT VERIFIED | 否 | Issue #1110 題號 D2＝維持空槽（DEC-158 轉錄，非客戶逐字，不得擴權）；`NUI2-VIX-TWO-PATHS` | `::test_every_unwired_real_field_states_its_reason` | BLOCKED |
| M-12 | 核心卡：US 10Y | FAKE／REAL=NP | 候選 A：`macro_snapshot.fetch_us10y_block`（FRED 公開 `fredgraph.csv` DGS10；**函式簽名有 `fred_api_key`，函式體內未使用**，§10 V9）；候選 B：session；Yahoo `^TNX` 為國際趨勢另一口徑 | 同上 | 無落地檔；FRED 當日值發布時刻 NOT VERIFIED | NP | FRED 授權 NOT VERIFIED | 否 | Issue #1110 題號 D1＝FRED DGS10 **僅口徑**（DEC-158 轉錄，不授權實作；題號 D1 ≠ DEC-172 治理 D1） | 同上 | BLOCKED（口徑已定、實作未授權） |
| M-13 | 核心卡：利差 | FAKE／REAL=NP | 無 canonical 欄；三種定義（10Y-2Y／10Y-3M／M1B-M2）未擇 | — | — | NP | — | 否 | Issue #1110 題號 D3＝維持空槽（DEC-158）；`NUI2-REALFEED-SG-02-SPREAD-DEF` | 同上 | BLOCKED（業務定義缺口，非接線缺口） |
| M-14 | 核心卡：DXY | FAKE／REAL=NP | 顯示路徑 `macro_alert._yf_latest`→`DX-Y.NYB`；舊戰情備援鏈 `DX-Y.NYB→DX=F→UUP` 可能落到 ETF | — | — | NP | — | 否 | 未授權；推薦 C＝維持空槽（RECOMMENDATION） | 同上 | BLOCKED |
| M-15 | 核心卡：PMI／景氣 | FAKE／REAL=NP | `data_cache/tw_pmi.parquet`（欄 `date pmi source fetched_at`，末列 2026-10-01＝62.5，source `data.gov.tw:dataset:6100`；`CACHE_DATASET_CADENCE`〔`macro_cache_reader`〕未登錄→`compute_cache_staleness` 必回 stale）與 `data_cache/macro_last_good/tw_pmi.json`（**`is_proxy: true` 在此檔**，不在 parquet）vs 景氣燈號，兩者意義不同 | — | — | NP | — | 否 | Issue #1110 題號 D4＝維持空槽（DEC-158）；`NUI2-REALFEED-SG-03-PMI-DEF`；DEC-155（proxy PMI 不得為正式訊號；**來源類別：ChatGPT 獨立裁示，非客戶逐字**） | 同上 | BLOCKED |
| M-16 | 🤖 OneBrain Outlook | FAKE／REAL=NP | 程式內 0 個 OneBrain producer | `real_canonical` `_R_STAGE_G` | — | NP | — | 否 | `FUI-STAGE-G`、SG-09 | `test_ui2_p2_primary_slot.py::test_onebrain_content_is_unchanged_only_its_position_moves` | BLOCKED |
| M-17a | （不渲染）為什麼（L2：`regime_explain`、`why_f`） | VM 有、畫面無；`regime_explain` **REAL 已接線**（位階完整說明） | 同 M-05 | `real_canonical._market` | 同 M-05 | 不渲染（`SHOWN_FOLDS` 排除） | — | 否 | 同 M-05 | `test_ui2_p3_evidence_preservation.py::test_render_policy_guard_has_teeth` | NOT VERIFIED（同 M-05） |
| M-17b | （不渲染）指標明細（`detail_f`，L3）／原始資料表（`raw_f`，L3） | VM 有、畫面無；NP | 無 producer（五桶需 session 的 `macro_info`／`cl_data`） | `real_canonical._market` | — | 不渲染 | — | 否 | `NUI2-PORT-READINESS-L3`、`NUI2-PORT-INDICATOR-TILES` | 同上 | BLOCKED |
| M-18 | **市場資金與籌碼：融資餘額** | **不在 VM／畫面** | `finmind_margin.parquet` 欄 `margin_balance`（元）→L3 `margin_fact_service.get_margin_fact`（億）；本回合讀 L3：`OK`、5399.15741 億、as_of 2026-11-09、非 stale、`age_days=3` | L3 存在，**0 production caller**（§10 V3） | 無 `release_date`；`fetched_at` 對多數列為 bootstrap 單一時點（文件側 FACT，本回合未重算），不可作可得日 | L3 四態；缺值≠0（有測試） | FinMind PARTIALLY（禁再散布原始資料、須標「FinMind」）；DG-PIT、DG-LIC | UI2 否；Digest 否 | `I1144-WIRING-GATE`、DG-SCOPE、DG-PIT、DG-LIC；`I1140-MARGIN-SOURCE-TEXT`（常數含「全市場」字樣，見 §4 X-12）；`I1140-MARGIN-UNIT-MIX`（條件式） | `tests/test_margin_fact_service.py::test_stale_boundary_7_days_not_stale_8_days_stale`、`::test_scope_guard_not_wired_to_ui_or_real_feed` | BLOCKED（資料層 READY；接線 HOLD） |
| M-19 | **市場資金與籌碼：板塊資金（衍生聚合）** | **不在 VM／畫面** | `data_cache/sector_flow/daily_net.parquet`（億；張×1000×收盤）→L3 `sector_flow_fact_service.get_sector_flow_fact`；本回合讀 L3：41／38／3、合計 −920.24812237 億、`complete`、非 stale | L3 存在，**0 production caller** | 視窗＝最新交易日；無 `release_date`；歷史列用回補當下的產業對映（文件側） | `complete` 只代表來源旗標完整、**不是**覆蓋率；缺價剔除股數 L3 不外露（§4 X-03） | TWSE／TPEX 授權 NOT VERIFIED；DG-COV；DG-PIT | UI2 否；Digest 否 | `I1144-WIRING-GATE`、`I1140-COVERAGE-MIN`、DG-PIT、DG-LIC、DG-SCOPE | `tests/test_sector_flow_fact_service.py::test_real_data_cache_once`、`::test_no_market_wide_or_forbidden_fields` | BLOCKED |
| M-20 | **市場資金與籌碼：大盤外資淨買賣超（僅外資）** | **不在 VM／畫面** | `finmind_inst.parquet` 欄 `foreign_buy`（億）；**沒有專用 L3**（L1 僅 `macro_cache_reader.load_extreme_risk_legs` 吐 5 日合計） | — | 同上 | — | 同上＋`source` 標籤斷點（§4 X-02） | 否 | 外資 L3 **未授權、另案**（DEC-164 G-9 轉錄）；`I1144-WIRING-GATE` | 無（缺口，見 §8） | BLOCKED |
| M-21a | 三大法人（外資／投信／自營）單日 | **不在 VM／畫面** | 舊路徑 TWSE BFI82U（session；`InstNetDict`）；UI2 無入口 | — | 授權 NOT VERIFIED | — | TWSE | 否 | 外資 L3 另案（未授權）；`I1144-WIRING-GATE` | — | BLOCKED |
| M-21b | 國際趨勢（DJI／IXIC／SOX／US10Y／DXY small multiples） | **不在 VM／畫面** | 舊 `_market_blocks.intl_series`（讀 `cl_data['intl']`）；**無乾淨 L3**，無 freshness 規則、無 PIT 剔除 | — | US EOD 時差未處理（文件側） | — | Yahoo | 否 | 無授權路徑（G2F 禁讀 session）；B／C 方案未授權 | — | BLOCKED |
| M-21c | 台股成交量 | **不在 VM／畫面** | `TwiiTrendView` 不含 volume；`twii_ohlcv.parquet` 的 `volume` 欄稀疏（最近 40 列中 27 列 NaN，§10 V7） | — | — | 全 0／全空須隱藏（`CLAUDE.md` §1.A）；NaN≠0 | Yahoo | 否 | 未授權；需 L3 新增 | — | BLOCKED |
| M-22 | 台股卡／日 K 的上游抓取三態字樣 | **REAL 已接線**（隨 M-09／M-10） | `upstream_state` ∈ {空, `NO_NEW_DATA`, `FETCH_FAILED`, `UNDETERMINED`}（`shared/upstream_state.py` 文案 SSOT）：「上游最近一次抓取失敗」／「最近一次抓取成功，來源無新資料（不代表資料最新）」／「最近一次抓取結果無法判定」 | `compute_cache_staleness`（讀 `data_cache/metadata.json` 的 `last_error`／`fetch_outcome`）→`get_trend_view`→`real_canonical.twii_card_spec`（附在卡片 reason） | 反映「最近一次抓取」，**不蘊含資料新鮮** | 三態各自文案；`ok` 但 stale 仍照畫 | — | UI2 是 | 無 | `test_ui2_real_feed.py::test_twii_states_are_mapped_without_inventing_values` | READY（字樣）；本沙箱 `metadata.json` `twii_ohlcv.last_error=null` |
| M-23 | 台股卡固定來源字樣 | **REAL 已接線**（常數） | `market_twii_view_service.TWII_SOURCE_TEXT`＝「本地加權指數歷史快取（來源 Yahoo，每日更新）」；**常數，不隨新鮮度變**，非 parquet `source` 欄、無 `fetched_at` | `twii_card_spec` | — | 不隨資料實況改變 | — | UI2 是 | 無 | 同 M-10 | READY（字樣存在）；**風險**：當資料已停在 2026-11-09 時，固定字樣仍寫「每日更新」，與實況不符（INFERENCE：讀者可能誤以為每日皆有新資料）。**FACT**：資料停在 11-09 與每日資料 PR #1124～#1126 未合併（既有 HOLD）同時成立；二者因果＝INFERENCE（見 X-09）。是否改字樣屬文案裁示，本文不動 |

### 2.2 🎯 標的（`p4_target`）

| # | section／UI field | 模式 | canonical／單位 | producer→consumer | 日期／資格 | 缺值／過期語意 | Cov／PIT／Lic | UI2／Digest | Gate | 測試 | 分類 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| T-01 | 模式切換（市場精選／即時查一檔） | UI 狀態 | `ui2_target_mode`（純 UI） | `views/target.py` | — | — | — | UI2 是 | 無 | `test_ui2_batch3.py::test_modes_are_never_fully_expanded_together` | READY（結構，非資料） |
| T-02 | 搜尋框／CTA「查詢」；名稱搜尋提示 | STATIC，disabled；名稱搜尋 NP | 無（任何輸入都不查詢） | `html.search_html` | — | 原因句「尚未開放查詢」 | 單檔腿皆需網路＋FinMind token／quota（文件側） | 否 | `TGT-01`（僅見 `NEWUI2_MARKET_TARGET_OLD_FIRST_DATA_CONTRACT_AUDIT_2026-11-09.md`／CAPMAP，**非 BACKLOG／DECISIONS ID**）；啟用需客戶 Gate＋獨立 G2F 擴充＋負向測試 | `::test_search_box_and_cta_present_in_both_modes_and_not_actionable` | BLOCKED |
| T-03 | 現在狀態（精選摘要） | FAKE／REAL=NP | 文件稱 `fundamental_screener_service.get_ranked_picks`；**程式未接** | `real_canonical._target` | 財報 as_of＝`民國{y}Q{s}`；公告日對齊 NOT VERIFIED | NP | MOPS 條款未查 | 否 | SG-04／SG-13（因子組合無 canonical 定義）、`I1144-WIRING-GATE` | `::test_every_unwired_real_field_states_its_reason` | BLOCKED |
| T-04 | 市場位階（W-4 context 一行） | FAKE／**REAL 已接線**（同 M-05 同一次 snapshot） | 同 M-05 | 同 M-05 | 同 M-05 | 同 M-05；`ctxline_html` 以 Neutral chip 畫，狀態只靠文字（Wireframes §9 已核准） | 同 M-05 | 同 M-05 | 同 M-05 | `test_ui2_batch3.py::test_target_market_regime_follows_the_same_market_context` | NOT VERIFIED（同 M-05：接線成立、實值目前恆未載入，不列 READY） |
| T-05a | Risk Cap（context row） | FIXED | 同 M-06 | 同 M-06 | — | `⬜ 無法判定` | — | 否 | SG-06、RC-VISIBILITY、DEC-141 Q5 | 同 M-06 | BLOCKED（刻意不接） |
| T-05b | 是否需行動／下一步 | NP（文字「本頁不產生持股動作；動作權威＝💼 持股」） | 無 | `vm_common.aggregator_pending_field` | — | NP | — | 否 | `NUI2-AGGREGATOR-IMPL` | 同 M-07 | BLOCKED |
| T-06 | 精選卡：產業機會 Top 5 | FAKE／REAL=NP | 候選 A（既有 L3、dict 契約 `ok/reason`，非 FieldState）：`sector_flow_service.get_sector_flow_view(etf_tickers=None, include_stock_watchlists=False, use_active_selection=False, strict=True)`（出處：`NEWUI2_REAL_FEED_MAPPING_2026-11-03.md` T6 的寫法為前三個參數；**`strict=True` 是本文所加**；`stock_sheet_id` 不傳）；候選 B（#1142 fact service、FieldState 契約）：`sector_flow_fact_service`（**兩個板塊 L3 並存，無擇一規則**，§5 CF-7）；排序在 L5 `rank_industries`。⚠️ **本回合核對**：即使只傳 `strict=True`，`stock_sheet_id` 預設 `None` 時 `_collect_stock_watchlist_tickers(None)` 立即回 `[]`、不讀 Sheet；但 `highlight_sectors` 恆空，**不得顯示「無持股」**（讀者看不到 highlight ≠ 沒有持股） | 未接 | `observation_date` 嚴格 YYYY-MM-DD；stale＞4 日曆日 | NP | `ticker_sector.json` 個股級對照落在公開 repo | 否 | `NUI2-PORT-INDUSTRY-RANK`、DG-LIC、`I1144-DATA-STORAGE-DECISION` | 同上 | BLOCKED |
| T-07 | 精選卡：候選 Top 10 | FAKE／REAL=NP | `get_ranked_picks(auto_fetch=False)`；僅 `eps_high`／`trend` 兩因子可無網路；`eps_high` 為單季非 TTM | 未接 | 同 T-03 | NP | — | 否 | SG-04／SG-13 | 同上 | BLOCKED（技術上可重用≠業務定義已裁，§5 CF-8） |
| T-08 | 選股條件（唯一在 🎯 渲染的收合區） | NP | 無 | `real_canonical._target` | — | expander 內為 NP | — | 否 | 同 T-07 | `test_ui2_p3_evidence_preservation.py` | BLOCKED |
| T-09a | 查一檔：結果頭（ticker／name／chips） | FAKE（`FAKE-0001`）／REAL `queried=False`（不畫，只畫灰說明「即時查一檔尚未開放」） | 無 producer | `real_canonical._target` | — | 灰說明 | — | 否 | 同 T-02 | `test_ui2_batch3.py::test_fake_lookup_result_is_labelled_fake_and_has_no_real_ticker` | BLOCKED |
| T-09b | 查一檔 snapshot：基本面 | FAKE／REAL=NP | 文件側：`fetch_metrics`、`get_financial_statements`（FinMind，連網） | 未接 | 財報公告日對齊 NOT VERIFIED | NP | FinMind PARTIALLY | 否 | 單檔腿網路＋token／quota；個別資料契約 Gate | `::test_every_unwired_real_field_states_its_reason` | BLOCKED |
| T-09c | 查一檔 snapshot：估值 | FAKE／REAL=NP | 文件側：`fetch_metrics`；Forward EPS／Fair Value 無來源 | 未接 | — | NP | — | 否 | SG-08 | 同上 | BLOCKED |
| T-09d | 查一檔 snapshot：籌碼 | FAKE／REAL=NP | 文件側：`get_chips_readout`（連網） | 未接 | — | NP | TWSE／FinMind | 否 | 單檔腿 Gate；DEC-164 融資／板塊 L3 與單檔籌碼無關 | 同上 | BLOCKED |
| T-10 | 查一檔：趨勢、產業 | FIXED（`⬜ 尚未定義`） | 無定義（DEC-092 Q2） | — | — | `not_evaluated` | — | 否 | 業務定義缺口 | 同上 | BLOCKED |
| T-11 | 查一檔：市場環境 | FAKE／REAL 已接線但 `queried=False` 不渲染 | 同 M-05 | — | — | 同 M-05 | — | — | 同 M-05 | — | NOT VERIFIED（同 M-05／T-04：接線成立、實值目前恆未載入；VM 有、畫面無） |
| T-12 | 加入觀察（disabled）＋隔離說明 | STATIC | 寫 Google Sheet（`watchlist_service`）被 G2F 禁 | — | — | disabled | — | 否 | OAuth／Sheet Gate（永不無 Gate 接線） | `::test_lookup_writes_only_ui2_prefixed_session_state` | BLOCKED |
| T-13 | （不渲染）精選 L3「完整 6 欄表／跨季趨勢」（`full_f`） | VM 有、畫面無；NP | 文件側：`fundamental_screener_service`／`cross_quarter_trends`（需連網與快照）；程式未接 | `real_canonical._target` | 財報 as_of＝`民國{y}Q{s}` | 不渲染（不在 `SHOWN_FOLDS`） | MOPS 條款未查 | 否 | SG-04／SG-13 | `test_ui2_p3_evidence_preservation.py` | BLOCKED |
| T-14 | （不渲染）查一檔 L2「基本面／估值／🤖 研究解釋」（`lk_fundamental`／`lk_valuation`／`lk_research`；後者內含欄位 `lk_f3`） | VM 有、畫面無；NP | `lk_research` 為 `_R_STAGE_G`（Stage G）；其餘同 T-09b／c | `real_canonical._target` | — | 不渲染 | — | 否 | `FUI-STAGE-G`；SG-08 | 同上 | BLOCKED |

### 2.3 💼 持股（`p4_hold`）

| # | section／UI field | 模式 | canonical／單位 | producer→consumer | 日期／資格 | 缺值／過期語意 | Cov／PIT／Lic | UI2／Digest | Gate | 測試 | 分類 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| H-01 | 組合狀態行：組合名稱／檔數 | FAKE／REAL=NP | 文件稱 `holdings_service.get_holdings`→`gsheet_portfolio`；被 G2F 禁；程式 0 個 holdings producer | `real_canonical._hold` | 使用者手填，無單一資料日 | NP（FAKE loaded 顯示「FAKE 組合 · 12 檔」但下方持股表為空槽） | Google Sheet（使用者資產） | 否 | `NUI2-ME-ACCOUNT-REAL-GATE`、`NUI2-AUTH-CONTRACT-GATE`、G-F2、G-F6 | `tests/test_ui2_hold_w11_batch1.py::test_hold_layout_contract_all_states` | BLOCKED |
| H-02 | 組合狀態行：資料日、判得出 | **STATIC，無 VM 欄位** | 無 | `html.hold_status_html` 寫死 `⬜ 資料日未提供`／`⬜ 尚未提供` | — | 固定 | — | 否 | 接真資料需先改 L0 VM 契約＋html（現契約沒有承載位置） | 同上 | BLOCKED |
| H-03 | Risk Cap／目前曝險 | FIXED（Risk Cap `無法判定`；曝險 `⬜ 資料未備`，「無現金／總資產來源」） | 無 producer；舊 UI 也沒有（Sheet 表頭無現金／總資產） | `real_canonical._risk_cap_row`／`_hold` | — | Missing／Undeterminable | — | 否 | SG-05、SG-06、RC-VISIBILITY、DEC-141 Q5 | `test_ui2_real_feed.py::test_risk_cap_and_action_fields_are_identical_across_pages_and_feeds` | BLOCKED（資料不存在，非 UI 缺口） |
| H-04 | 今日需處理（單行） | NP | 無 | `vm_common.aggregator_pending_field` | — | `⬜ 尚未提供（待系統動作整合）` | — | 否 | `NUI2-AGGREGATOR-IMPL` | `test_ui2_hold_w11_batch1.py::test_mutations_action_row` | BLOCKED |
| H-05 | 主 CTA「🚀 更新持股戰情」 | STATIC disabled（「需登入後才能讀取持股」） | — | — | — | disabled | — | 否 | 登入 Gate | `test_ui2_hold_header.py::test_anchors_and_cta_preserved` | BLOCKED |
| H-06a | 建議持股水位空槽（市場端） | STATIC | 無（不讀 Risk Cap）；`⬜ 尚未提供`＋「市場端建議區間尚未開放；這不是投資上限」 | `html.hold_body_html` | — | 固定 | — | 否 | SG-06、RC-VISIBILITY；CAPMAP HD-10 | `test_ui2_hold_w11_batch1.py::test_mutations_body` | BLOCKED |
| H-06b | 產業曝險／集中度空槽（Primary） | STATIC | 無 VM 欄位；SPEC 文字 `text.py::HOLD_PRIMARY_SPEC` 宣告單位 %；舊持股頁無對應，個股組合頁有（等權、無張數，`compute/risk/concentration.py`） | `html.hold_body_html` | — | 固定 | — | 否 | 客戶 Gate（資料來源與等權假設）；CAPMAP HD-11 | `::test_css_geometry_contract` | BLOCKED |
| H-07 | OneBrain 持股摘要 | NP | 無 producer | `real_canonical._hold` | — | NP | — | 否 | `FUI-STAGE-G` | 同上 | BLOCKED |
| H-08 | 持股表（8 欄表頭＋原因句） | STATIC；`hold_table_html()` **無參數** | 無資料路徑；VM 的 `holdings_table` 卡與 `next_step` **在 VM 但 view 不渲染** | `html.hold_table_html` | — | 不畫假列、不畫「0 檔」 | — | 否 | 同 H-01；逐檔現價另需連網行情（價格新鮮度逐源未追） | `::test_vm_still_carries_next_step_and_holdings_card` | BLOCKED |
| H-09 | （不渲染）明細（`why_f`，L2）／原始明細（`raw_f`，L3） | VM 有、畫面無；NP | 無 producer（`_R_PATH_C`：需登入並讀取 Sheet） | `real_canonical._hold` | — | 不渲染 | Google Sheet | 否 | 同 H-01 | `test_ui2_p3_evidence_preservation.py` | BLOCKED |

### 2.4 👤 我的（`p4_me`）

| # | section／UI field | 模式 | canonical／單位 | producer→consumer | 日期／資格 | 缺值／過期語意 | Cov／PIT／Lic | UI2／Digest | Gate | 測試 | 分類 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| U-01 | 連線狀態／異常／下一步 | FAKE（`Google 已登入（FAKE 帳號）`）／REAL=NP | 文件稱 `me_account_service.get_account`（讀路徑會寫 `_oauth_state`＋nonce，被禁）；Real 軸 `account` 刻意為 None | `real_canonical._me` | — | NP；FAKE unavailable→紅 | — | 否 | SG-11、`NUI2-AUTH-CONTRACT-GATE`、`NUI2-ME-ACCOUNT-REAL-GATE` | `test_ui2_real_feed.py::test_real_me_page_does_not_pretend_to_know_the_account` | BLOCKED |
| U-02a | 第一屏主 CTA「帳戶管理」 | STATIC disabled（原因「登入與 Sheet 操作尚未開放」） | 無 | `real_canonical._me`（`cta`） | — | disabled | — | 否 | `NUI2-ME-ACCOUNT-REAL-GATE` | `test_ui2_batch3.py::test_me_three_account_states_have_the_right_primary_cta_and_disabled_actions` | BLOCKED |
| U-02 | 帳戶動作列（切換 Sheet／選組合／觀察清單／登出） | FAKE only（REAL 不畫） | 無 | `html.account_actions_html`（全 disabled） | — | disabled | — | 否 | 同上 | `test_ui2_batch3.py::test_me_signed_out_signed_in_unavailable_semantics_and_axes` | BLOCKED |
| U-03 | 4 卡：Google／Sheet／組合／觀察清單 | FAKE／REAL=NP（`需登入並讀取 Sheet，目前尚未開放`） | 文件稱 `portfolio_binding_service.get_active_selection` | — | — | NP；FAKE signed_out→Missing | — | 否 | 同上 | 同上 | BLOCKED |
| U-04 | 一般設定（Strategy／Notifications／Display） | NP（兩 feed 同） | 未找到正式 canonical settings contract | — | — | NP | — | 否 | 無 ID；**NOT VERIFIED**（兩組皆未窮舉） | `::test_every_unwired_real_field_states_its_reason` | NOT VERIFIED |
| U-05 | Audit：Decision Digest（收合，白名單） | NP | `src/services/decision_digest_builder.py` 存在（A2 已完成，PR #1146），**非測試、非 digest 自家檔 0 個 import** | — | — | NP | — | **Digest 0 production caller** | G-F4／G-F5、Stage F | `test_ui2_p3_evidence_preservation.py` | BLOCKED |
| U-06 | Audit：Rule Registry（收合，白名單） | NP | 候選 L0 `shared/decision_digest_rules.RULE_ID_ALLOWLIST`（零 I/O） | — | — | NP | — | 否 | `NUI2-REALFEED-NEXT-SESSIONFREE`（候選，§-1 無指派不動工） | 同上 | NOT VERIFIED |
| U-07 | （不渲染）Data Freshness（`fresh_f`）／System Information（`sys_f`） | VM 有、畫面無；NP | System Information 候選 `calibration_status_service.get_calibration_status`（session-free；`NUI2-REALFEED-NEXT-SESSIONFREE` 對應此項，**不是** Rule Registry；文件側提出、未驗）；Data Freshness 無 producer | `real_canonical._me` | — | 不渲染（不在 `SHOWN_FOLDS`） | — | 否 | `NUI2-REALFEED-NEXT-SESSIONFREE`（候選）；Data Freshness 同 §2.5 | — | BLOCKED |

### 2.5 🗂 資料（`p4_data`）

| # | section／UI field | 模式 | canonical／單位 | producer→consumer | 日期／資格 | 缺值／過期語意 | Cov／PIT／Lic | UI2／Digest | Gate | 測試 | 分類 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| D-01 | 資料健康度／是否需行動／下一步／CTA「查看資料健康度」 | NP／STATIC disabled（兩 feed **共用同一份**固定內容） | `src/services/ui2/data_page.py::data_page_canonical`；`real_canonical._data` **不讀 snapshot** | — | 文字「不顯示任何來源狀態與資料日」 | NP | 新欄／分母須先 Data Contract Gate；不可用 cron 時刻冒充觀測日 | 否 | `NUI2-P6-*` 線框決策；DEC-146 第一批僅空殼 | `test_ui2_guards.py`（`data_page.py` 在掃描清單，逐項未驗） | BLOCKED |
| D-02 | 資料來源與連線：來源健康度／資料日／Active Sheet | NP | 舊 `data_registry_summary_service.summarize_data_registry`（session）；`data_cache/metadata.json` 已有 `fetch_outcome`／`last_error`：**UI2 台股卡與日 K 已經由 `upstream_state` 間接消費**（M-22），**只有 🗂 資料頁不讀** | — | — | NP；與殼頂列 Active Sheet 重複承載同一件事 | — | 否 | 同上 | 同上 | BLOCKED |

> **後果（FACT）**：REAL 已掌握 TWII 的 as_of／stale／upstream（M-10），🗂 頁仍全為空殼；「Data Freshness」又被 `SHOWN_FOLDS` 排除 → **畫面上沒有任何總覽新鮮度的位置**。

---

## 3. 舊 UI 能力承接缺口（反向視角）

> **「舊 UI 有」≠「UI2 資料可用」。** 「舊 UI」＝Legacy New UI（`app.py` 預設路由，`src/ui/views/**`）為主、Old UI（`?legacy=1`）為輔。「舊 UI 仍可用」只確認程式路徑存在，**未實機開頁**（INFERENCE 層級）。
> **名詞定義（fact service）**：指 #1142（DEC-164 G-9）新增、專為 UI2 事實層設計的唯讀 L3，回傳 `FieldState` 四態＋`as_of`＋`is_stale`。**查法**：`ls src/services | grep -i fact` 只命中 `margin_fact_service.py`、`sector_flow_fact_service.py`；`grep -rln FieldState src/services`（排除 `ui2`）亦只命中這兩檔——兩者皆 0 production caller。**既有**的 L3 `sector_flow_service.get_sector_flow_view`（Legacy 在用，dict 契約 `ok/reason`，非 FieldState）也可當 🎯 產業 Top5 的候選資料源，同樣未接，且與 fact service 並存（§5 CF-7）。除此之外，法人買賣超、VIX、US10Y、DXY、國際指數**沒有**對應的唯讀 L3。**缺口大宗是「沒有合格 L3／定義」，不是「沒人接」。**

### 3.1 取數能力缺口 17 項（舊 UI 有、UI2 無；反向調查 27 列中的有效缺口）

> 調查者 FACT／本 PR 未逐列重核；這 27 列（編號 G01–G27 為本文內部編號）的範圍是**資料取數與核心區塊**，**不等於** CAPMAP 的全部 100 列——對帳見 §3.3。

| ID | 頁 | 舊 UI 能力 | 舊取數（檔:符號） | UI2 現況與障礙 |
|---|---|---|---|---|
| G03 | 📊 | MA5／60／120／200 參考線 | `_market_blocks.MA_REFERENCE_SPECS`；值來自 `market_strategy.get_market_assessment`（live、寫 session） | 日 K 無 MA；補 MA 須走 parquet 同源計算，**不得**重用上述 live 函式 |
| G04 | 📊 | 市場位階 | `page_today.get_macro_regime` | **已接線，但在 UI2 獨立 session 目前恆為未載入**（§0-3） |
| G06 | 📊 | 16 燈／五桶風險摘要／主要風險 | `page_market.calc_traffic_light`、`page_today.compute_five_bucket_summary` | 五桶需 session 的 `macro_info`／`cl_data`；無合法唯讀 L3 |
| G07 | 📊 | VIX／US10Y／利差／DXY／PMI 卡 | `macro_snapshot.fetch_vix_block`／`fetch_us10y_block` 等 | 五卡全 NP；接線前須先解 §4 X-04～X-06 |
| G08 | 📊 | 國際趨勢小倍數 | `_market_blocks.INTL_GROUPS`；`daily_checklist.INTL_MAP`（**無 SPX、無 NDX**；NDX 全 repo 0 命中，客戶口語的 NDX 在 repo 實為 `^IXIC`） | 無落地檔、無唯讀 L3 |
| G10 | 📊 | 大盤籌碼：外資／投信／自營、融資、PCR、期貨 | `page_market._render_x8`、`daily_data_fetchers.fetch_institutional`／`fetch_margin_balance` | 無；融資／板塊 L3 未接；**法人無 UI2 fact service** |
| G11 | 📊 | 今日結論句 | `page_market.build_market_conclusion` | 依賴 Aggregator／位階，與 G04 連動 |
| G14 | 🎯 | 產業機會 Top 5（`x_yi`＝近 5 日累計） | `page_find.get_sector_flow_view` | `industry_top` NP；候選 fact service 的視窗是**最新單日**，與舊 UI 的 5 日累計**不是同一指標**，接線時不可同名 |
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

### 3.3 與 CAPMAP 對帳（`docs/vnext/NEWUI2_CAPMAP_3COL_2026-11-10.md`）

**範圍與方法**：CAPMAP 是 Old UI → Legacy New UI → UI2 的三欄能力對照，**共 100 列**（本回合以腳本計：📊 MK 25、🎯 TG 31、💼 HD 16、👤 ME 14、🗂 DT 6、系統 SY 8）。其「測試證據」欄為 `NONE（UI2）` 者共 **46 列**，缺口等級為：critical 1、major 23、minor 21、none 1。**表 A 的篩選依據是代理條件「測試證據＝NONE」，不是「UI2 無承接」**——兩者不同，所以表 B 另列「功能存在＝否」但測試證據非 NONE 的列。CAPMAP 基準為 `f4d86b4f`（2026-11-10）；自該基準至 `7eb48d6c`，對 `src/ui2`、`src/services/ui2`、`shared/ui2_contract`、`app_ui2.py` 做提交紀錄路徑篩選，只有一次變更（`907322aa`，#1141 安全修復：close≤0 拒用、未來 as_of 不顯示負過期天數），**未新增能力**（INFERENCE：僅依提交紀錄路徑篩選，**未逐列重核 UI2 欄**）。§3.1 的 G 列只涵蓋資料取數與核心區塊，**未涵蓋**下列個股／ETF／持股深度等能力，故補此對帳。缺口等級為 CAPMAP 的「暫定、非客戶核准」分級，本文照錄不改。

**表 A**＝CAPMAP 中 **UI2 測試證據為 NONE 且等級為 critical／major 的 24 列**（承接狀態＝CAPMAP「UI2 功能存在」欄：否＝完全沒有；部分＝只有占位／骨架）：

| CAPMAP 編號 | 能力 | UI2 功能存在 | 等級 | 對應本文 |
|---|---|---|---|---|
| MK-14 | 國際趨勢 small multiples | 否 | major | G08／M-21b |
| MK-16 | 五桶摘要／指標危險度 | 否 | major | G06／M-17b |
| MK-17 | **景氣拐點**六大面向／CPI×Fed／總經拼圖 | 否 | major | **本文 §3.1 未單列**（以 CAPMAP 為準） |
| MK-19 | 大盤籌碼：法人／融資／熱錢 | 否 | major | G10／M-18～M-21a |
| MK-20 | 風險雷達／攻擊發動／策略矩陣 | 否 | major | G13（NOT VERIFIED） |
| TG-09 | 基本面初篩逐檔明細＋涵蓋率警示 | 否 | major | 與 G15 相關；本文未單列 |
| TG-11 | 凍結前 20 名＋前進式驗證對帳 | 否 | major | 與 G16 相關；本文未單列 |
| TG-13 | **個股 K 線＋均線** | 否 | major | **本文未單列** |
| TG-14 | **基本面：財報體檢**／財報領先／月營收／龍頭預警 | 部分 | major | G17／T-09b（僅占位） |
| TG-15 | **估值現況**：357 殖利率／PE／PB | 部分 | major | G17／T-09c（僅占位） |
| TG-16 | **歷史估值區間**：河流圖 | 否 | **critical** | **本文未單列** |
| TG-18 | **單檔籌碼**：近 20 日／爆量／集保大戶 | 部分 | major | G17／T-09d（僅占位） |
| TG-20 | 單檔風險：VCP／布林／心理檢查 | 否 | major | 本文未單列 |
| TG-22 | 型態目標價 ZigZag | 否 | major | 本文未單列 |
| TG-23 | AI 首席顧問／AI 財報體檢 | 部分 | major | 與 G17 相關（Stage G） |
| TG-25 | **ETF** 單檔三判決卡 | 否 | major | **本文未單列**（ETF 整組） |
| TG-26 | **ETF** 明細七段／3-3-3／標準差帶 | 否 | major | **本文未單列**（ETF 整組） |
| HD-05 | 235 燈牆／逐盞明細 | 否 | major | G21 |
| HD-06 | 80/20 配置偏離＋衛星停利 | 否 | major | G21 |
| HD-07 | 換股建議 | 否 | major | G21 |
| HD-08 | VaR／壓測／配息現金流 | 否 | major | G22 |
| HD-09 | **再平衡／Overlap**／效率前緣／對 0050／稅後 | 否 | major | **本文未單列** |
| ME-12 | AI 問答 | 否 | major | 本文未單列 |
| ME-14 | 免責聲明 footer | 否 | major | 本文未單列（是否為 cutover 必備＝客戶未裁，文件側） |

**表 B**＝CAPMAP 中 **「UI2 功能存在＝否」但測試證據非 NONE** 的列（共 8 列；表 A 的篩選會漏掉它們，因為這些列的「測試」多半是證明 UI2 沒有／不產生該能力的守衛）：

| CAPMAP 編號 | 能力 | 等級 | 對應本文／說明 |
|---|---|---|---|
| MK-15 | 16 燈指標明細 | major | M-17b（VM 有、畫面無） |
| **TG-21** | 個股買賣語意：停利停損／目標價／三維出場 | **critical** | **§2 沒有此列**。**UI2 刻意不產生買賣判斷**（`tests/test_ui2_batch3.py::test_target_creates_no_buy_judgement_or_action_authority`）＝**刻意不承接**；CAPMAP 備註：保留或正式退場為客戶 Gate（UI2 現狀＝等同未承接） |
| HD-03 | 讀取持股（Google 登入＋Sheet；整頁真資料前置） | critical | H-01（前置條件；`NUI2-ME-ACCOUNT-REAL-GATE`） |
| ME-04 | Sheet／組合／觀察清單／持股列 CRUD | major | U-02（動作列全 disabled）；**CAPMAP 此列功能存在＝否（非「部分」）**，測試為 `tests/test_ui2_batch3.py::test_ui2_has_no_oauth_sheet_or_secrets_call`（「不存在」守衛） |
| ME-10 | Data Freshness 資料健康牆 | major | U-07／D-01（VM 有、畫面無） |
| TG-03 | 名稱搜尋 | minor | T-02（新能力，舊 UI 也沒有） |
| TG-12 | 全台股跨季趨勢排行＋CSV | minor | 本文未單列 |
| ME-11 | System Information | minor | U-07 |

**CAPMAP「功能存在＝部分」且測試證據非 NONE 的 critical／major 列**（此類才對應 §2 各列）：MK-01→M-04、MK-05→M-06、MK-06→M-07、MK-07→M-08、MK-08→M-03、MK-09／10／12／13→M-11／12／14／15、TG-02→T-02、TG-04→T-09a～d、TG-05→T-06、TG-07→T-07、TG-08→T-08、TG-10→T-12、HD-01→H-03、HD-02→H-04、HD-04→H-08、HD-10→H-06a、HD-11→H-06b、HD-13→H-07、ME-01／02→U-01／U-03、ME-08→U-05、ME-09→U-06、DT-01→D-01；**MK-22（News AI 總裁決，部分，major）§2 未單列**。（上一版稱這些列「分散在 §2 各列」不準確：ME-04 非「部分」、TG-21 在 §2 沒有，已更正如上。）

**表 A 以外的 NONE 列（22 列，minor 21＋none 1）**——如實分類：
- **診斷／教學面（7 列）**：ME-13（教學）、DT-02～DT-06（資料源清單／雙演算法對帳／API 根因診斷／門檻校準／副作用控制）、SY-06（側欄連線狀態）。
- **投資／分析功能與全域呈現（15 列）**：MK-18 市場廣度／ADL、MK-21 總經指南針、MK-24 大盤 EPS×PE 模型（none）、MK-25 總經 v2 密度／搜尋／分類、TG-06 產業趨勢、TG-17 Forward EPS／Fair Value、TG-24 個股↔總經／持倉 banner、TG-27 多檔比較（ETF 7 維）、TG-28 三階段濾網＋AI 報告／組合體檢、TG-29 帶入我的持股、HD-12 策略分類、HD-14 葡萄串領息、HD-15 同名兩套刻度揭露、HD-16 持股↔Sheet 綁定狀態、SY-05 全域置底常駐條。
（上一版稱這 22 列「多為 Old UI 診斷／教學面」不準確，已更正。）這 22 列等級為 minor 以下，**本文未逐列展開**。

**CAPMAP 與本文的字面衝突（CAPMAP 此處已過期或易誤讀）**：CAPMAP 將 **MK-02（市場位階）與 TG-30（🎯 市場位階 context 一行）的「真資料」欄標為「是」**；本文結論是「已接線，但在 UI2 獨立 session 目前恆為未載入」（§0-3，沙箱實測 `unloaded`）。CAPMAP 自己的備註已寫「實值多半為尚未載入，未實機驗」，因此不是兩套事實，而是**欄位值「是」只表示接線路徑為真、容易被讀成『有值』**；本文不改 CAPMAP，讀者以本文 §0-3 為準，並把 CAPMAP 這兩列的「真資料＝是」視為需更正的過期標示（待總管決定是否登記）。

**結論**：CAPMAP 的 100 列中，UI2 有真值的只有 MK-03（台股卡）、MK-04（日 K）；MK-02／TG-30（位階）接線成立但目前恆未載入（§0-3）。**個股深度（K 線／財報體檢／估值／單檔籌碼）、ETF 整組、市場廣度與景氣拐點、再平衡／Overlap 均為 UI2 完全無承接或僅占位**，且多數不在目前 Gate 表內（是否屬 cutover 必要項由客戶決定，NOT VERIFIED）。

---

## 4. 跨頁／跨層口徑問題

只放 FACT 與清楚標示的 INFERENCE。「UI2 影響」＝是否已污染 UI2 目前畫面。標「調查者 FACT／本 PR 未重核」者＝出自反向調查報告（未入 repo）、本 PR 未獨立驗證。

| ID | 問題 | 證據 | 標籤 | UI2 影響 |
|---|---|---|---|---|
| X-01 | 市場位階在 UI2 獨立 session **目前**為未載入；條件：`BREADTH_PROXY_SCORING_ENABLED=False`（DEC-074 B）**且** UI2 session 無人寫入 `warroom_summary`（寫入點只在 Legacy） | §0-3、M-05；沙箱實測 | FACT（沙箱）；部署端 NOT VERIFIED（僅此兩條件） | 位階欄在上述條件成立期間是常數字樣；任一條件改變（例如旗標翻 True 或 UI2 新增 warroom producer——均需客戶 Gate）則不成立 |
| X-02 | **`finmind_inst.parquet` 同欄 `foreign_buy` 內兩種 `source` 標籤**：`…:Foreign` 4920 列（2006-09-29～2026-10-08）、`…:Foreign_Investor` 19 列（2026-10-12～2026-11-09）；單一 `source` 欄、無獨立口徑欄 | 本回合 `python -I` 讀 parquet 重算（§10 V4）；`scripts/update_macro_history.py::fetch_finmind_inst` docstring 自述「讀 `source` 欄即可分辨新舊口徑」。**讀取者盤點**（本回合 `grep -rn finmind_inst --include=*.py`，排除 `tests/`，僅靜態）：`src` 內僅 `macro_cache_reader.load_extreme_risk_legs`（末 5 列、只讀 `date`／`foreign_buy`）；`scripts/` 另有 `calibrate_health_weights.py`（整檔 `read_parquet`，餵 `build_feature_frame`，註解自陳只看正負號）、`export_stock_db.py`（寫 `institutional_flow` 表，只取 `date`／`foreign_buy`，註解自陳「本表不帶 source 欄」）、`analyze_ring1_gate.py`（5 日滾動合計）、`calibrate_macro_traffic.py`（左 join `foreign_buy`）——它們取用整段序列、**未見按 `source` 分流**（已確認取欄範圍者：`export_stock_db`、`analyze_ring1_gate`、`calibrate_macro_traffic`；`calibrate_health_weights` 內部 `build_feature_frame` 未讀） | FACT（標籤分布與讀取者清單）；「`:Foreign` 列是否含外資自營商、自哪天起」＝docstring 轉述「派工規格所載實測事實，本批未重抓驗證」→ **NOT VERIFIED**；`NEWUI2_MARKET_CHIPS_OLD_UI_FIRST_MAPPING_2026-11-11.md` §1.1 只寫「2017-12-18 前」，與 docstring 三時期說法不一致（文件側） | UI2 目前無；`scripts/` 的校準與匯出會混口徑（INFERENCE：單位同為億，影響限於舊標籤時期外資自營商差額，docstring 自述近年約 0） |
| X-03 | **板塊「外資分項」≠ FinMind「大盤外資」**：同 37 個共同交易日（2026-09-11～11-09）中 36 天同號，逐日絕對差中位 55.4 億、最大 239.6 億；最新日 −942.4 vs −900.6 億（差 −41.9）。**37 日窗橫跨 source 標籤斷點**，拆分：舊標籤 `:Foreign` 18 日（2026-09-11～10-08）中位 60.18／最大 239.57（**最大值 239.6 全來自舊標籤日**，2026-09-18），同號 18／18；新標籤 `:Foreign_Investor` 19 日（2026-10-12～11-09）中位 49.19／最大 140.28，同號 18／19 | 本回合唯讀重算與拆分（§10 V5、V11）；方法：`daily_net.parquet` 逐日 `foreign_yi` 加總 vs `finmind_inst.foreign_buy` | FACT（數字）；成因＝**INFERENCE**（板塊用「張數×收盤價」估算、FinMind 用申報買賣金額差；舊標籤日另可能含外資自營商〔NOT VERIFIED〕；上櫃範圍 FinMind dataset 是否含 NOT VERIFIED）。新標籤日中位仍約 49 億，故「差距主要來自舊標籤口徑」不成立（INFERENCE） | 目前無；未來若兩者並列同標籤＝誤導（G-10：不可比較或加減）。另：板塊 L3 `n_dropped_missing_price`（缺價被剔除股數；`metadata.json` per_day 15761）**L3 不外露**，故「合計」的覆蓋範圍使用者看不到 |
| X-04 | VIX：`fetch_vix_block`（raw yfinance，3mo）、`macro_core.fetch_yf_close('^VIX')`（6mo，NAS proxy）、`macro_alert._yf_latest` 三條取數；`allocation_service._read_vix` 讀 session | 調查者 FACT／本 PR 未重核（僅確認 `allocation_service._read_vix` 存在） | 調查者 FACT（多管線）；「同頁兩個 VIX 可不一致」＝INFERENCE | 無（UI2 空槽） |
| X-05 | US10Y：FRED `DGS10`（五桶燈優先）vs Yahoo `^TNX`（國際趨勢圖）；Legacy 在 `page_market` 有「與國際市場區的 Yahoo ^TNX 不同源」揭露；警示路徑「session 已算值 > yfinance 即時」可能換源（INFERENCE） | 本回合重核：`src/ui/views/page_market.py` 內該揭露字串存在；其餘調查者 FACT／本 PR 未重核 | FACT（雙口徑與揭露）／INFERENCE（換源） | 無（UI2 空槽）；口徑決定見 DEC-158 題號 D1（僅口徑，§6.3） |
| X-06 | DXY：顯示備援鏈 `DX-Y.NYB→DX=F→UUP` 可落到 ETF（`UUP`，~27 美元尺度）；五桶燈有 [70,130] 範圍擋，國際趨勢圖 B 是否有擋＝grep 無命中（未追上游過濾） | 本回合重核備援鏈（`src/data/daily/daily_data_fetchers.py`）；BACKLOG `ISSUE1110-DXY-UUP-LABEL` 已登記 | FACT（備援鏈）／INFERENCE（圖 B 可能畫出 UUP 尺度） | 無 |
| X-07 | 加權指數 4 條 Yahoo 取數管線（parquet cron／live `yf_proxy`／raw `yf.download`／`macro_core` chart）；Legacy 圖 A「收盤取 parquet、MA 取 live」；漲跌 % 走 `shared/stats_helpers.calc_stats`，其 `pct = (last - prev) / prev * 100 if prev else 0` 是缺值補 0 形態（Legacy 路徑） | 本回合重核：`calc_stats` 補 0 形態存在；「4 條管線」「圖 A 收盤取 parquet、MA 取 live」調查者 FACT／本 PR 未重核 | FACT（補 0 形態）／調查者 FACT（多管線）；「圖 A 收盤與 MA 最新日可能相差」＝INFERENCE | UI2 只用 parquet 管線（單一、可驗）；UI2 無漲跌欄 |
| X-08 | **新鮮度閾值與基準日不一致**：板塊 `SECTOR_FLOW_STALE_MAX_CALENDAR_DAYS=4`（`shared/sector_flow_thresholds.py`）；TWII／融資／外資走 `CACHE_DATASET_CADENCE`（定義於 `src/data/macro/macro_cache_reader.py`）daily→`STALE_DAYS_DAILY=7`（`shared/staleness.py`）；PMI 未登錄 cadence 必 stale；皆不看交易日曆。基準日：板塊 `reader._compute_staleness` 與融資 L3 用台北今日（`tw_now().date()`），TWII 卡／日 K 的新鮮度走 L1 預設主機 `date.today()`（`get_twii_trend_view(today=None)`）——**此基準日差異即既有 BACKLOG `I1140-TODAY-TZ`**（「`get_twii_trend_view(today=None)` 用主機 `date.today()`，日 K 路徑用台北日」），本文併入該項，不另立新項（**此併入判斷為 INFERENCE**：該 BACKLOG 原文範圍較窄，只述 `get_twii_trend_view(today=None)` 與日 K 路徑，並未涵蓋板塊／融資／外資的基準日，是否同屬一項待總管確認）；部署主機時區 NOT VERIFIED | 本回合讀碼（§10 V7） | FACT；「同一資料日可能板塊過期、外資／融資不過期，連假下一個 stale 一個非 stale」＝INFERENCE | 目前無（三者未並列）；候選項 N-1 見 `NEWUI2_MARKET_DATA_CONTRACT_VALIDATION_2026-11-12.md` §5 |
| X-09 | **卡片新鮮度**：`compute_cache_staleness` 以 `_dt.date.today()`（主機日期）計日曆天；日頻門檻 7。**實況**：`twii_ohlcv.parquet` 最後一筆資料 commit＝`4432d5a7`（2026-11-10 08:46 +0800，資料日 2026-11-09），此後 main 無新資料 commit | `src/data/macro/macro_cache_reader.py::compute_cache_staleness`；本回合實測 as_of 2026-11-09、today 2026-11-12→`age_days=3`、`is_stale=False`；提交紀錄重驗（§10 V10） | FACT（資料日、提交時間、PR 狀態）；原因＝INFERENCE | 11-10、11-11 兩個平日收盤未入庫（是否皆為開市日 NOT VERIFIED），卡片無任何過期提示，且固定來源字樣仍寫「每日更新」（M-23）；READY 標籤不代表資料新鮮。**每日資料 PR 證據（本回合重驗，FACT）**：`origin/auto/data-macro-history` 最新提交 `fc447def`（2026-11-11 16:59:56 +0000，「每日總經歷史增量：2026-11-11」），相對 main 差 5 檔（含 `data_cache/twii_ohlcv.parquet`、`finmind_inst.parquet`、`finmind_margin.parquet`、`macro_last_good/tw_pmi.json`、`metadata.json`）；該分支的 `twii_ohlcv.parquet` 末日 2026-11-10（4914 列），main 為 2026-11-09（4913 列）。對應的 PR **#1124（macro-history）、#1125（sector-flow）、#1126（macro-forward-test）皆 open、未合併**（GitHub 讀取：`merged=false`；`mergeable_state`：讀取當時為 `behind`（另有審查讀到 `unknown`）；三 PR 的 base 仍是舊的 `043a4d21`；該欄位由 GitHub 惰性計算、隨時會變，不作為判斷依據；#1124 head 即 `fc447def`；PR 內文自陳「未經人工審閱不得合併」）。#1124 內文「資料狀態」段（本回合重讀）顯示：分支上 `finmind_inst`／`finmind_margin` 資料日到 2026-11-11、`twii_ohlcv` 到 2026-11-10；此三 PR 屬既有 HOLD（BACKLOG 記「#1124～#1126 未處置（#1126 PIT 未驗）」，DEC-159 記其 PIT NOT VERIFIED；DEC-174 的 HOLD 清單與 BACKLOG 記為維持未處置，禁止順手合併／改寫／rebase）。 **推論（INFERENCE）**：main 上 TWII 卡資料日停在 2026-11-09，疑為每日資料 PR 未合併，**非 cron 失敗**（自動分支 11-11 仍有增量提交）；**cron 實際成功率 NOT VERIFIED**（三條自動分支最新提交均為 2026-11-11 UTC，11-12 當日有無增量提交本回合讀不到）。即使 #1124 合併，TWII 卡也只會前進到 2026-11-10，不是今日。 |
| X-10 | **成交量序列「猜單位」**：`leading_indicators.twse_volume` 備援段對 Yahoo `^TWII` 的 `Volume` 以 `for _div in [1e8, 1e4, 1e3]` 逐一嘗試，第一個落在 `5 < v < 20000` 者收下並當「億元」；同檔把 FMTQIK／MI_INDEX（成交金額，億）與該備援 `update` 進**同一個** `vol_dict` | 本回合讀碼＋讀 parquet（§10 V8）；`twii_ohlcv.parquet` 最近一筆非 NaN volume＝4,239,400（2026-11-05），除以 1e4＝423.94 通過條件 | 迴圈與合併＝**FACT**；「偏差 ≥10× 的格點會被混入、標成億元」＝**INFERENCE（未實際觸發備援、未取得同日 FMTQIK 對帳）** | UI2 不顯示成交量，**尚未污染**；日後接成交量須避開 `twse_volume`，改建唯讀 L3 |
| X-11 | 融資單位：`fetch_margin_balance` 走 `shared/margin_schema` SSOT；`leading_indicators._to_yi_mg`／`_twse_margin_day` 以數值區間猜單位，不引用 `margin_schema` | 調查者 grep（本 PR 未獨立重跑） | FACT（實作重複）；數值分歧 NOT VERIFIED | 無（UI2 若接 `margin_fact_service` 走 SSOT）；`I1140-MARGIN-UNIT-MIX`（歷史混用僅驗最新點） |
| X-12 | 融資 L3 使用者可見常數 `MARGIN_SOURCE_TEXT`＝「本地融資餘額歷史快取（FinMind 全市場融資金額，元換算為億元；每日更新）」含「全市場」；FinMind 該 dataset 是否含上櫃 NOT VERIFIED | `src/services/margin_fact_service.py::MARGIN_SOURCE_TEXT`；板塊側有 `test_no_market_wide_or_forbidden_fields` 守住，融資側 `test_source_has_only_fixed_user_visible_strings` 只釘常數名稱集合、不禁內容 | FACT（字面與守衛範圍）；是否構成誤導＝文案裁示 | 無（L3 未接線）；接線前須處理 `I1140-MARGIN-SOURCE-TEXT` |
| X-13 | 兩個板塊 L3 並存：`sector_flow_service.get_sector_flow_view`（🎯 產業）與 `sector_flow_fact_service.get_sector_flow_fact`（📊 資金），讀同一份 `data_cache/sector_flow/*`，stale 規則與狀態詞彙不同 | 文件側（`NEWUI2_MARKET_TARGET_OLD_FIRST_DATA_CONTRACT_AUDIT_2026-11-09.md`、DEC-164 §三） | FACT（並存）；無擇一／對帳規則＝NOT VERIFIED（建議登記 two-paths 風險，INFERENCE） | 無（皆未接） |
| X-14 | `partial`／`unknown`（板塊 completeness）不在 `FieldState` 五態內，線框的 `partial` 狀態無映射、無測試 | `shared/ui2_contract/models.py`（五態恰五個）；L3 `completeness` | FACT | 無（未接線） |

### 4.2 狀態詞彙對映：Digest `DataStatus` vs UI2 `FieldState`（只寫有證據的）

- **兩套詞彙**（FACT，讀碼）：Digest `shared/decision_digest.py::DataStatus`＝`ok／stale／missing／proxy／failed／invalid`（六值，「沒有 neutral」；`missing／failed／invalid` 為無值態）；UI2 `shared/ui2_contract/models.py::FieldState`＝`ok／missing／stale／unavailable／not_evaluated`（五值，DEC-124 釘「恰為五個」）。
- **程式內沒有任何映射**（FACT，grep）：含 `DataStatus` 的非測試檔只有 `shared/decision_digest*.py`、`src/services/decision_digest_{assembly,summary,builder}.py`；含 `FieldState` 的非 UI2 檔只有兩個 fact service；**沒有任何檔同時 import 兩者**，UI2 也未 import `DataStatus`。
- **名稱層級的對應**（INFERENCE，僅依名稱與註解）：`ok↔OK`、`stale↔STALE`、`missing↔MISSING`。**無對應名稱者**：`proxy`（UI2 無「代理值」態；PMI proxy 目前以 NP 空槽處理）、`failed`（最近似 `UNAVAILABLE`，但語意是否等價 NOT VERIFIED）、`invalid`（UI2 兩個 fact service 對 NaN／inf 的處理即不一致：融資→`MISSING`、板塊→整份 `UNAVAILABLE`；Digest 為獨立的 `INVALID`）、UI2 `NOT_EVALUATED`（Digest 無對應，位階未載入時以 `MISSING`＋`_UNEVALUATED_*` 文字處理）。
- **結論**：Digest 與 UI2 目前**不是同一套狀態詞彙，也沒有核准的對映**；任何把 Digest 欄位餵給 UI2（或反向）的工作都須先有對映決策（屬 G-F4／G-F5 範疇，客戶 Gate）。其餘對映細節 NOT VERIFIED。

---

## 5. 文件間衝突與過期宣告

調查共整理 **17 項衝突、14 項過期宣告**（單組、逐份閱讀並抽查，**非窮舉**）。本節只取影響最大者；其餘未納入（原因＝多為文字漂移、無資料欄位後果；調查報告未入 repo，故不提供編號對照）。**編號 CF-n／ST-n 為本文內部編號**（沿用調查流水號，故不連續），不是 repo ID；表中標「本回合重核」者已自行驗證（§10 V9）。

### 5.1 衝突（取 9 項）

| # | 議題 | 兩邊說法 | 判斷 |
|---|---|---|---|
| CF-1 | 台股主圖現況 | A：「誠實空槽」（`NEWUI2_OLD_UI_FIRST_FIVE_PAGE_GAP_AUDIT_2026-11-09.md`、`NEWUI2_MARKET_TARGET_OLD_FIRST_DATA_CONTRACT_AUDIT_2026-11-09.md`、`NEWUI2_MARKET_READONLY_CONTRACT_AUDIT_2026-11-09.md`，基準 `f5e78e10`／`e909152`）；B：已有 20 根日 K 主圖（`NEWUI2_CAPMAP_3COL_2026-11-10.md`、`ISSUE1110_DATA_AVAILABILITY_MATRIX_2026-11-10.md`） | **FACT：B 為現況**。`src/ui2/views/market.py` 有 `kbar_chart_html`（本回合重核）；A 基準早於 #1101／#1109（`31acbe87` 2026-11-10 03:34、`81db0637` 2026-11-10 13:34，提交紀錄重核） |
| CF-2 | Real feed 接了幾個事實 | 「2 個」：`NEWUI2_REAL_FEED_MAPPING_2026-11-03.md`、`DATA_LINEAGE_VERIFICATION_2026-11-05.md`、ISSUE1110 矩陣、**UI 文案** `src/ui2/shell/app.py::_FEED_LABELS`「只接 2 項真資料」；「3 個」：CAPMAP、`UI2_RUNTIME_PREGATE_RESEARCH_2026-11-11.md` | **FACT**：`real_feed.py` 三個 reader（卡、日 K、位階）；兩個 canonical service、三個 UI 事實；**文案仍寫 2 項＝文案漂移**（§7.3 D）。本文不改文案 |
| CF-3 | `fetch_us10y_block` 有無 FRED API 第二層 | `NEWUI2_MARKET_READONLY_CONTRACT_AUDIT_2026-11-09.md` 暗示兩層；ISSUE1110 矩陣稱 docstring 的 Tier 1 在函式體不存在 | **FACT（本回合重核）**：函式簽名與 docstring 有 `fred_api_key`／Tier 1，函式體只有 `fredgraph.csv`，簽名行外 0 次引用 `fred_api_key`；ISSUE1110 較準 |
| CF-5 | 憲法 §2.1「VIX：Yahoo 主、CBOE CDN 備」「TW 融資：TWSE 主→HiStock→Wearn」 | 與碼不符：`cdn.cboe.com` 僅在 `src/compute/risk/risk_radar.py`（VIX3M 等），`fetch_vix_block` 無 CBOE 備援（本回合重核）；融資鏈實為 FinMind→MI_MARGN→HiStock→Goodinfo→Yahoo→鉅亨（**此鏈順序為調查者讀碼轉述，本回合未重核**） | **FACT（VIX 部分已重核）**：憲法宣告與碼不符；本文不改憲法（§-1：無指派不動工） |
| CF-7 | 板塊兩個 L3 並存 | 見 §4 X-13 | NOT VERIFIED（無擇一規則） |
| CF-8 | 候選排名「可 as-is 重用」vs「定義未訂」 | `NEWUI2_MARKET_TARGET_OLD_FIRST_DATA_CONTRACT_AUDIT_2026-11-09.md` §2：可 `get_ranked_picks`（`eps_high`／`trend` 兩因子無網路）；BACKLOG `NUI2-REALFEED-SG-04-CANDIDATE-FACTORS` open（需客戶裁示） | 兩者看的層不同（技術副作用 vs 業務因子定義）；以 BACKLOG open 列為準：仍 BLOCKED |
| CF-9 | 外資口徑比較 | 板塊外資分項 −942.4 億 vs `finmind_inst` −900.56 億（差 −41.9），G-10「不可比」 | **FACT：差額本回合重算吻合**（§10 V5）；成因 NOT VERIFIED |
| CF-11 | Stage F／G 是否為前置 | Cutover 矩陣：F／G「暫列 cutover 前置」；PREGATE 研究：G-F2～G-F6「不阻塞」市場資金與籌碼接線 | 兩者範圍不同（cutover vs 單一區塊接線），不矛盾但易混讀；「不阻塞」本身＝INFERENCE，未經客戶確認 |
| CF-16 | 閾值不一致 | 板塊 4 日、融資／TWII 7 日、PMI 必 stale | 見 §4 X-08；無任何文件裁示統一 |

### 5.2 過期宣告（取 6 項）

| # | 過期宣告（出處） | 取代依據 | 本回合重核 |
|---|---|---|---|
| ST-1 | 「TWII 主圖誠實空槽」（同 CF-1 三檔） | #1101／#1109；`src/ui2/views/market.py` 有 `kbar_chart_html`；`tests/test_ui2_guards.py::G2F_IMPORT_ALLOWLIST` 含 `twii_kbar_fact_of` | **已重核：成立** |
| ST-2 | 「Real-data Preview 目前只讀 TWII 收盤及嚴格 Regime 兩個事實」（Gap Audit 檔頭「現行 UI2」說明句；REAL_FEED_MAPPING；DATA_LINEAGE） | 同 ST-1；現為三個 UI 事實（卡、日 K、位階） | **已重核：Gap Audit 該句原文存在；現況為三事實** |
| ST-4 | ISSUE1110 矩陣 §5 資安發現（診斷頁顯示金鑰前後 4 碼、整段 `PROXY_URL`） | #1113／#1114；`src/ui/pages/api_diagnostic.py` 已無 `_mask` | **已重核：`_mask` 命中 0**（修復 PR 的正確性本回合未驗） |
| ST-11 | 「`I1144-A2-IMPL` 已授權、尚未實作」（`docs/BACKLOG.md` 舊列） | DEC-166；BACKLOG「Issue #1144 結果」列：已完成（PR #1146，`d4f7b3f`） | **已重核**：BACKLOG 同檔並存兩列（一列「已授權、尚未實作」、一列「已完成」），提交紀錄見 `d4f7b3f6` 改動 `decision_digest_builder.py`。**同檔新舊並存，讀舊列會誤判** |
| ST-12 | 「#1149 被 CI 環境阻塞」 | DEC-170 §四：#1150 修復、#1149 合併 | 未重核（轉述） |
| ST-14 | `NEWUI2_CUTOVER_GAP_MATRIX_2026-11-10.md` 內 BACKLOG 行號引用 | 3C 重整（DEC-173）搬移 BACKLOG；`REORG3C-REF-SYNC`（open） | **已重核**：`FUI-STAGE-F` 在現行 BACKLOG 的位置與該矩陣所引行號不同（該行號現指向其他內容）。**依 §8.2.A.0 規則 1，本文一律用 ID／符號** |

其餘過期宣告（本文未取者）出處與取代依據**本回合未逐項重核**，不納入本文。

---

## 6. Gate 全表

> **照實抄文件記載的狀態。本文不宣稱任何 Gate 已解除、不暗示任何接線已授權。「誰能解除」＝文件記載的裁示者／解除條件。**
> **ID 查證範圍**：下列 ID 以 grep 查證於 `docs/BACKLOG.md`／`docs/DECISIONS.md`（命中次數不一，不代表狀態），**例外**：(a) `DG-COV／DG-PIT／DG-LIC／DG-SCOPE` 是**別名**（見 §6.0）；(b) `SG-01～SG-14` 的定義表在 `NEWUI2_REAL_FEED_MAPPING_2026-11-03.md` §6，BACKLOG 只有 `NUI2-REALFEED-SG-xx` 候選列；(c) `TGT-01` 與 CAPMAP 能力編號（`HD-03`、`HD-10`、`HD-11` 等）**只出現在 `docs/vnext/*`**（`TGT-01` 見 `NEWUI2_MARKET_TARGET_OLD_FIRST_DATA_CONTRACT_AUDIT_2026-11-09.md`、CAPMAP；`HD-xx` 見 CAPMAP），**不在 BACKLOG／DECISIONS**；(d) `G-9`／`G-10` 是 DEC-164 G 表題號、`G-F1～G-F6` 是 Stage F 文件題號、`DEC-141 Q5` 是決策題號，皆非 BACKLOG ID；(e)「外資 L3」無獨立 ID。

### 6.0 `DG-*` 別名定義

| 別名 | 定義處 | 對應 BACKLOG／DEC |
|---|---|---|
| DG-COV | `docs/vnext/UI2_RUNTIME_PREGATE_RESEARCH_2026-11-11.md` §1.4 | BACKLOG `I1140-COVERAGE-MIN`；登錄於 DEC-166（研究文件）、DEC-169（Coverage 母體收斂） |
| DG-PIT | 同研究 §2 | BACKLOG `I1144-UI2-PREGATE` 列與『Issue #1144』段「仍開放」條；DEC-166、DEC-167、DEC-169 |
| DG-LIC | 同研究 §3 | BACKLOG `I1144-LIC-THREE-QUESTIONS`、`I1144-UI2-PREGATE`；DEC-169、DEC-171 |
| DG-SCOPE | 同研究 §5.2（三方案）與 §6 | BACKLOG `I1144-UI2-PREGATE`；DEC-166 |
| WIRING-GATE | — | BACKLOG `I1144-WIRING-GATE`；DEC-164 G-9、DEC-165 |

### 6.1 市場資金與籌碼線（Issue #1140／#1144）

| Gate ID | 內容 | 狀態 | 誰能解除 | 相關欄位 |
|---|---|---|---|---|
| `I1144-WIRING-GATE` | UI2 runtime 接線（feed／section／`G2F_IMPORT_ALLOWLIST`／snapshot／canonical／VM／view） | **HOLD／未授權** | 客戶（新 Gate） | M-18～M-21c，以及**所有尚未接進 `real_feed` 的資料欄位**（皆需同類 allowlist 變更） |
| DG-COV＝`I1140-COVERAGE-MIN` | 板塊最低 coverage 門檻與母體口徑；**不得自設百分比** | **HOLD** | 客戶 | M-19 |
| DG-PIT | 無 `release_date` 時是否接受「資料日＋抓取時間（明示非發布時點）」 | **HOLD** | 客戶 | M-18、M-19、M-20 |
| DG-LIC＋`I1144-LIC-THREE-QUESTIONS` | TWSE／TPEX／FinMind 等資料於 Cloud 呈現與衍生聚合的授權（是否商業／是否公開／公開 repo 是否保留個股級來源列） | **HOLD**（FinMind PARTIALLY；其餘 NOT VERIFIED） | 客戶／法務（AI 不下結論） | 全部取自三家＋Yahoo＋MOPS＋data.gov.tw 的欄位 |
| DG-SCOPE | 日後接線先融資一項（A）或融資＋板塊（C） | **HOLD**（AI 推薦非裁示） | 客戶（須附推薦，§8.4 step 4） | M-18、M-19 |
| `I1144-DATA-STORAGE-DECISION` | 是否修改公開 repo 的資料保存方式 | **待客戶裁示，非動工項** | 客戶 | T-06 產業對映／候選池、M-19 |
| 外資 L3（無獨立 ID） | 大盤外資淨買賣超唯讀 L3＋授權 | **未授權、另案** | 客戶（授權）；總管（技術設計） | M-20 |
| `I1140-MARGIN-SOURCE-TEXT`／`-ETF-FAMILY-ABSENT`／`-SECTOR-CRON-SCOPE` | 接線前文案約束（不稱全市場；家族成員缺席揭露；診斷計數範圍） | open | 總管提案＋客戶（文案） | M-18、M-19 |
| `I1140-SECTOR-UNOBS-LABELS`／`-DROPPED-PRICE` | 3 個偶發標籤成因、15761 含義 | open，成因 NOT VERIFIED | 總管（獨立一組查證） | M-19 |
| `I1140-MARGIN-UNIT-MIX` | 歷史融資單位混用只驗最新點 | open，條件式（取歷史序列才觸發） | 總管 | M-18 |
| `I1140-OHLC-GUARD`／`-FUTURE-ASOF-ASYM`／`-TODAY-TZ` | 日 K 路徑守衛／未來日不對稱／主機日 vs 台北日（**§4 X-08 的基準日差異併入 `-TODAY-TZ`**） | open，條件式 | 條件觸發 | M-09、M-10 |
| `I1140-REGIME-SET-EQ`／`I1140-MACRO-STATE-NONCANON` | UI2 與 Digest 兩份位階白名單無等式測試；`get_macro_state` 把非 canonical regime 洗成 `neutral` | open（既知、被測試釘住、不動） | 總管 | M-05 |

### 6.2 Digest／Stage F 線

| Gate ID | 內容 | 狀態 | 誰能解除 | 相關欄位 |
|---|---|---|---|---|
| G-F1 | headless 市場輸入供應 | 方案 A（DEC-161 轉錄；來源類別依 DEC-172 D3 未逐項核）；MISSING 項目維持 MISSING | — | Digest 市場段 |
| G-F2 | headless 持股授權 | 待裁示 | 客戶 | 💼、Digest 持股段 |
| G-F3 | A2 stale 取向 | 待裁示 | 客戶 | 所有 stale 值 |
| G-F4／G-F5 | Digest v2 schema／PIT；production caller 時機 | 待裁示 | 客戶 | U-05 |
| G-F6＝`NUI2-AUTH-CONTRACT-GATE` | 登入前置 | 待裁示／open | 客戶 | 💼、👤 |
| `I1144-DG-A3`／`I1144-DG-HEALTH` | Digest regime／light 配對一致性；`market.health` 範圍 | 未授權、獨立 Gate | 客戶 | Digest 市場段 |
| `FUI-STAGE-F／G／H／I` | Digest／OneBrain／跨頁一致／real-data 驗收 | open（未開始） | 依序前置，客戶 | M-16、H-07 |

### 6.3 Cutover／身分／動作線

| Gate ID | 內容 | 狀態 | 誰能解除 | 相關欄位 |
|---|---|---|---|---|
| `NUI2-AGGREGATOR-IMPL` | System Action Aggregator 實作 | blocked-on-customer | 客戶 | M-07、T-05b、H-04 |
| `NUI2-ME-ACCOUNT-REAL-GATE` | 真 OAuth／Sheet | open | 客戶 | 💼、👤 |
| SG-01～SG-14 | Stop Gate 候選（定義表見 `NEWUI2_REAL_FEED_MAPPING_2026-11-03.md` §6：更新 CTA、利差、PMI、候選因子、目前曝險、Risk Cap 數值、動作欄、Forward EPS、OneBrain、位階 as_of、OAuth、五桶 thin L3、新公式／門檻） | open，本批未觸發 | 客戶（各自） | 見 §2 各列 |
| RC-VISIBILITY／C2b／DEC-141 Q5 | Risk Cap 數值／日期／沿用天數顯示 | 未授權 | 客戶 | M-06、T-05a、H-03 |
| **Issue #1110 題號 D1～D5**（經 DEC-158 轉錄） | D1 US10Y 口徑 FRED DGS10（僅口徑）；D2 VIX、D3 利差、D4 PMI 維持空槽；D5 不新增每日落地 cron。**消歧**：這是 **GitHub Issue #1110 的題號**，DEC-158 明文「不是 `DEC-*` 條文編號」；與 **DEC-172 的治理 D1–D5**（Skip-PR 廢除、GitHub-first、客戶裁示來源規則等，無關資料欄位）**不同義** | 轉錄式裁示：DEC-158 自陳「非客戶逐字原文、非 QA PASS」；依 DEC-172 D3 須逐項核查來源，本文未核 | — | M-11～M-15 |
| DEC-155 | proxy PMI（`UNDETERMINED`）不得為正式訊號等（#1088 治理裁示） | **來源類別：ChatGPT 獨立裁示，非客戶逐字裁示**（DEC-155 標題自陳）；依 DEC-172 D3 須逐項核查 | — | M-15 |
| `NUI2-PORT-*` | Old UI L5 邏輯上移 L3＋parity（READINESS-L3／CONCLUSION-CLAUSES／MAIN-RISK／INDUSTRY-RANK／INDICATOR-TILES） | open | 客戶授權施工 | M-04、M-08、M-17b、T-06 |
| `NUI2-CUTOVER`／`NUI2-REMOVAL-GATE`／`NUI2-CAPMAP-3COL` | cutover／移除 | open（文件記 0 條 cutover 條件已滿足） | 客戶 | 全頁 |
| `NUI2-PREVIEW-CLOUD-STATE-FILES`／`NUI2-PREVIEW-APP-MANUAL`／`NUI2-ACC-REAL-DEVICE` | Cloud 狀態檔、Cloud Preview 人工建立、真機驗收 | open／NOT VERIFIED | 真機人工＋工程 | M-05、全頁 |
| 治理類 | #1119 Actions 精簡 HOLD；**#1124～#1126＝每日資料發布 PR（macro-history／sector-flow／macro-forward-test）：open 未合併，未處置，#1126 PIT 未驗**（BACKLOG『Issue #1140』段「維持」條；DEC-159 記其 PIT NOT VERIFIED）；`REORG3C-Q5-GATE` | HOLD／open（DEC-174 的 HOLD 清單與 BACKLOG 記為維持未處置，禁止順手合併／改寫／rebase） | 客戶 | **間接**：TWII 卡／日 K 的資料日停在 2026-11-09 與此相關（X-09，因果＝INFERENCE）；**本批不碰** |
| 市場頁核心卡專屬項（與 §8 Q6 對齊） | VIX：Issue #1110 題號 D2、`VN1-PG-VIX-ASOF`、`NUI2-VIX-TWO-PATHS`；US10Y：題號 D1（僅口徑）；利差：題號 D3、`NUI2-REALFEED-SG-02-SPREAD-DEF`；DXY：無專屬 Gate ID（`ISSUE1110-DXY-UUP-LABEL` 為標示項）；PMI：題號 D4、DEC-155、`NUI2-REALFEED-SG-03-PMI-DEF` | open／空槽維持（題號經 DEC-158 轉錄；DEC-155 為 ChatGPT 獨立裁示） | 客戶 | M-11～M-15 |

---

## 7. B1：UI2 安全面向結論

### 7.1 結論

**未發現「契約內、可重現、不涉及新設計決策」的缺陷**（發現統計：BUG-in-contract 0｜GUARD-GAP 2｜VISUAL-GATE-CANDIDATE 2｜NOT-A-DEFECT 3〔N1～N3〕＋文案漂移 1〔D〕）。調查者自報 NOT-A-DEFECT 為 6，但其文字僅逐項列出 N1～N4，且 N4 與 VG2 是同一事項；本文只採可核對者（N4 併入 VG2），其餘兩項在調查報告中未列出、無法核對。**這不是任何 UI 改動的授權**——任何 UI 改動須先出文字線框給客戶（§-1.5 草稿先行）。

### 7.2 檢查面向與方法（單組調查者執行；本文僅轉述）

> ⚠️ **警語：下列 82／82、1705 passed、41 passed 全是 FAKE／Preview 軸的版面與契約守衛結果，且為調查者自報、本 PR 未重跑。它們不證明任何 Real 欄位有資料、新鮮或可對外呈現（§0-10：畫面完成或測試綠燈 ≠ 資料可用）。**

| 面向 | 方法 | 結果 |
|---|---|---|
| 1 手機 390／桌機 1440 首屏（遮擋／裁切／需捲動） | `tests/ui2_viewport` 量測 5 頁×6 場景＋🎯 lookup＋👤 三帳戶態＋📊 長字串 stress，× 390／1440，共 82 狀態；Streamlit 1.67.0 與 1.59.2 各跑一次；另對預設道 320…1440 多寬度手動探測 | 82／82 通過；無水平溢出、無裁切（**FAKE 軸**） |
| 2 資料狀態 vs 契約（四態／chip tone／字樣） | 讀碼＋`tests/test_ui2_guards.py` 系列 | 未發現；🗂 頁全為 capability 軸 |
| 3 缺值被誤呈現為 0／正常／中性／安全 | 靜態 grep `or 0`／`.get(…,0)`／`fillna`／`else 0` 等於 `src/ui2 src/services/ui2 shared/ui2_contract`＝0 命中；AppTest 逐「5 頁×6 場景」取可見文字 grep 孤立 `0`／`安全`／`正常`／`中性` 等 | 唯一命中＝客戶逐字句「未評估不等於安全」（DEC-117 Q6=A 必須外露；轉錄）；其餘 0。**未讀範圍的補掃見 §8 Q5** |
| 4 Preview／FAKE vs Real 標示混淆 | 預設道 banner 探測；Real 標示 DOM 模擬（360…1440） | 未發現契約內缺陷；**Real 軸真實瀏覽器量測未做**（見 7.4） |
| 5 既核准 UI 版面的安全回歸守衛缺口 | 盤點 viewport 矩陣與守衛 | 見 GUARD-GAP |

另跑 `python -m pytest tests/test_ui2_*.py -q`：**1705 passed, 41 deselected, 3 xfailed**；`UI2_BROWSER_LANE=required … -m ui2_browser`：**41 passed**（調查者自報；本文未重跑）。

### 7.3 候選項（皆**非缺陷**、**非授權**）

| ID | 內容 | 分類 | 處置 |
|---|---|---|---|
| VG1 | FAKE 與 Real 標示在第一列樣式相同（只靠文字「示意資料（FAKE）」vs「Real-data Preview（非正式 production default）」區分） | VISUAL-GATE-CANDIDATE | 視覺契約外改動，須先出文字線框給客戶；本批不修 |
| VG2 | FAKE 👤 預設帳戶態＝signed_in，頁內「Google 已登入（FAKE 帳號）」與頂列「帳號 ⬜ 尚未提供」並置（全帶 FAKE 標示；`ui2_account` 僅開發面示意）。即調查者 N4 | VISUAL-GATE-CANDIDATE | 改 FAKE 場景預設屬設計決策，須經草稿 gate |
| D（文案漂移） | `src/ui2/shell/app.py::_FEED_LABELS` 與 `tests/test_ui2_drawer_browser.py` 皆寫「只接 2 項真資料」，實況＝REAL 帶真值 2 欄（台股卡、日 K）＋位階已接線（目前恆未載入）；`shared/ui2_contract/text.py::REAL_PREVIEW_BANNER_NOTE`「僅台股與市場位階為真資料」則與位階口徑一致。**只描述事實，不改文案**（開發面文案，非產品畫面；改字樣須先確認屬哪一類） | 文案漂移 | 登記，不動 |
| N1 | 🎯 W-4 context 行對 Unavailable 也用 Neutral 色（非紅） | NOT-A-DEFECT | Wireframes §9／DEC-123 Q3 已核准（轉錄，來源依 DEC-172 D3 未逐項核） |
| N2 | FAKE 冷啟動「⬜ 尚未載入，請按更新」＋「下一步 按 🚀 更新」，但 CTA disabled | NOT-A-DEFECT（登記） | `text.py::RISK_SENTENCE_NOT_LOADED` 為客戶逐字常數（DEC-117 Q6=A，轉錄）；頁首有 `示意資料（FAKE）`；Real 軸的對應欄位為 `_not_provided`、無「請按更新」。此處**僅登記**，不認定為缺陷、不建議改字 |
| N3 | Real 標示補充說明在 ≤640px 隱藏 | NOT-A-DEFECT | P1 已核准單行設計；非 Real 欄位一律 `⬜ 尚未提供` |
| GUARD-GAP G1 | viewport 量測矩陣只含 390×844、1440×900（僅一處 320×568） | 低；非缺陷 | 調查者手動探測 320…1100 寬無問題，故只是無自動守衛 |
| GUARD-GAP G2 | Real 軸瀏覽器量測證據只在 repo 既有 JSON（由 `test_ui2_real_feed.py` 的 `source_hash` 新鮮度守衛），本批未獨立複驗內容 | 低；非缺陷 | 登記 |

### 7.4 限制（如實）

- **Real-data Preview 瀏覽器量測因環境限制未執行**（背景啟動被環境拒絕，依規則不繞過）。Real 軸僅有靜態審閱、既有 pytest、DOM 模擬（INFERENCE）。
- Streamlit 1.56.0 本次未重跑（1.59.2、1.67.0 已跑；1.67.0 超出 `requirements.txt` 宣告範圍，僅作額外觀察）；Safari／Firefox／真機／Cloud／螢幕閱讀器未實測。
- 調查者**未讀**：`src/services/ui2/scenarios.py`、`src/services/ui2/real_canonical.py` 的 `kbar_chart_spec` 之後各函式（`_market`／`_target`／`_hold`／`_me`／`_data`／`real_canonical`）、`shared/ui2_contract/models.py`、`src/ui2/views/{hold,me,target}.py`。**本回合已補掃（grep 層級）並記錄於 §8 Q5**；「5 個面向皆未發現問題」仍是單組結論，**待獨立複驗**。

---

## 8. 「五頁驗收問題」逐題回答

> 授權來源：**已登錄於 main：DEC-174（PR #1166，main `dae78eea`）**（客戶 Batch 1「方案 B」；與 DEC-165／166／167／170／171 的「方案 A／B」不同義，見檔頭）。以下回答皆為稽核證據，**不是授權**。

**Q1　五頁每個資料欄位來自哪裡？** 見 §2。一句話：預設路徑全是 FAKE／固定占位；REAL 只有台股卡與日 K 來自 `data_cache/twii_ohlcv.parquet`（Yahoo `^TWII` cron 落地），位階來自 `get_macro_regime`（session＋本地狀態檔，目前恆未載入）。其餘 NP。

**Q2　哪些可用、哪些不可用？**（「可用」＝有真值來源且接線＋契約成立；**不等於資料新鮮、不等於可對外呈現**）
- **有真值（READY，限接線＋契約面）**：台股卡、20 根日 K（M-09、M-10）；資料模式 banner（M-02，非資料欄）。**資料新鮮度偏弱**：最後一筆資料 commit 為 2026-11-10 08:46（+0800），資料日 2026-11-09（X-09）。
- **已接線，但在 UI2 獨立 session 目前恆為「⬜ 尚未載入」**：市場位階（M-05、T-04、T-11）——**不列為「可用」**，亦非 READY（§0-3）。
- **資料層可用但 UI2 未接**：融資、板塊（L3 存在，0 caller；M-18、M-19）。
- **不可用**：其餘全部（BLOCKED／NOT VERIFIED），含大盤外資、三大法人、國際趨勢、成交量、VIX／US10Y／利差／DXY／PMI、個股深度、ETF 整組（§3.3）。
- 所有「有真值」均以授權條款 NOT VERIFIED 為前提。

**Q3　口徑問題？** 見 §4：X-02（外資 source 斷點，含 `scripts/` 讀取者）、X-03（板塊外資≠大盤外資，已拆斷點前後）、X-08（4 日 vs 7 日、台北 vs 主機基準日，併入 `I1140-TODAY-TZ`）、X-09（新鮮度偏弱）、X-10（成交量猜單位，INFERENCE）、X-12（融資常數含「全市場」）；VIX／US10Y／DXY／TWII 多管線（X-04～X-07，UI2 尚未污染）；Digest `DataStatus` 與 UI2 `FieldState` 無核准對映（§4.2）。

**Q4　舊 UI 有、UI2 未承接？** 見 §3：取數能力缺口 17 項（§3.1）；**另與 CAPMAP 100 列對帳（§3.3）**：UI2 測試證據為 NONE 的 critical／major 共 24 列，其中個股 K 線／財報體檢／估值／單檔籌碼、ETF 整組、市場廣度與景氣拐點、再平衡／Overlap 在 §3.1 並未單列。**法人買賣超沒有 UI2 fact service**、國際趨勢與 VIX／DXY 沒有乾淨 L3。

**Q5　現有授權內可修復的事項？**

判準取 B1 調查所用的三條件：(1) 違反已核准契約；(2) 可重現；(3) 不需新設計決策。另依 §-1，沒有 user 指派／實際 bug 觸發不動工。**已登錄於 main：DEC-174（PR #1166，main `dae78eea`）；本文不引申其授權範圍**。下表仍是**依 B1 判準的分類，不是授權判定**。**統一說明（適用下表所有「補測試／改字樣／補守衛」類項目）**：v3 §03-1 允許內部撰寫測試與 CI 守衛，但動工觸發仍受 §-1（需有實際 bug／user 指派）與 DEC-174 B1 範圍拘束；本批均未動。

| 候選項 | 出處 | 滿足三條件？ | 理由 |
|---|---|---|---|
| 位階恆未載入（M-05） | §0-3 | 否 | 非缺陷：由客戶裁示的旗標（DEC-074 B）與 UI2 無 warroom producer 造成；改變需客戶 Gate（旗標翻轉或新 producer） |
| `I1140-REGIME-SET-EQ`（UI2／Digest 兩份位階集合無等式測試） | BACKLOG；本文 `NEWUI2_MARKET_DATA_CONTRACT_VALIDATION_2026-11-12.md` §6.2 | 否 | 屬補守衛（測試）；目前無不一致的可重現證據、非缺陷；依上列統一說明本批未動 |
| `I1140-ETF-FAMILY-ABSENT` | BACKLOG | 否 | 潛在項：現值 `n_member_absent_cells=0`；L3 未接線，使用者看不到；揭露文案屬設計 |
| `I1140-SECTOR-UNOBS-LABELS`／`-DROPPED-PRICE` | BACKLOG | 否 | 成因 NOT VERIFIED；`daily_net.parquet` 不存個股代碼，無法重現；需新儲存／新來源（未授權） |
| `I1140-MARGIN-SOURCE-TEXT`（常數含「全市場」） | BACKLOG；§4 X-12 | 否 | 改字樣屬文案裁示；L3 未接線，畫面看不到；FinMind 範圍 NOT VERIFIED |
| `I1140-MARGIN-UNIT-MIX` | BACKLOG | 否 | 條件式：取歷史序列才觸發；未觸發 |
| `I1140-OHLC-GUARD`／`-FUTURE-ASOF-ASYM`／`-TODAY-TZ` | BACKLOG | NOT VERIFIED | 條件式；本回合未重現（部署主機時區未知）；修復會改變新鮮度判定語意（N-1，業務語意） |
| 成交量猜單位（X-10） | §4 | 否 | Legacy 路徑，UI2 不用；未實際觸發備援（INFERENCE）；§-1 無觸發 |
| 新鮮度偏弱／資料停在 2026-11-09（X-09） | §4 | 否 | 非 UI2 契約違反（契約允許日曆天>7 才過期）；改閾值屬業務語意。**資料停在 2026-11-09 與每日資料 PR #1124～#1126 open 未合併（既有 HOLD、PIT 未驗；DEC-174 的 HOLD 清單與 BACKLOG 記為維持未處置，禁止順手合併／改寫／rebase）同時成立——FACT；停更疑為 PR 未合併而非 cron 失敗——INFERENCE，cron 成功率 NOT VERIFIED。** 處置每日資料 PR 需客戶裁示（見 §11 第 4 項），本批不碰 |
| 文案漂移 D（「只接 2 項真資料」） | §7.3 | NOT VERIFIED | 開發面字樣、非缺陷（B1 判定）；修改會連動 `tests/test_ui2_drawer_browser.py`；依上列統一說明本批未動（B1 已判非缺陷） |
| N-3 `partial` 映射／N-4 缺價股數外露 | 市場契約文件 §5 | 否 | 需新設計決策（狀態映射、揭露方式） |
| GUARD-GAP G1／G2 | §7.3 | 否 | 補守衛（新測試），非缺陷；依上列統一說明本批未動 |
| VG1／VG2 | §7.3 | 否 | Visual Gate：須先出文字線框 |
| BACKLOG 同檔新舊並存（ST-11） | §5.2 | 否 | 治理文件修正，本批禁改 BACKLOG（由總管另 PR） |

**結論**：在 B1 判準與目前證據下，**沒有任何候選項被確認同時滿足三條件**；其中「NOT VERIFIED」者是證據不足而非確認無害。此結論受 B1 調查未讀範圍限制，該範圍本回合補掃如下（**grep 層級，非完整逐行審查**）：
- **範圍**：`src/services/ui2/scenarios.py`（427 行）、`shared/ui2_contract/models.py`（361 行）、`src/services/ui2/real_canonical.py`（682 行；重點為 `kbar_chart_spec` 之後各函式）、`src/ui2/views/{hold,me,target}.py`（22／20／45 行）。
- **缺值預設值寫法**：`grep -nE "or 0\b|\.get\([^)]*, ?0\)|fillna|else 0\b|or 0\.0|else 0\.0|or \"—\"|else \"—\"|getattr\([^)]*, ?0\)"` 於上述檔＝**0 命中**。`or ""` 三處（`scenarios._status_of` 的 `status_text or ""`；`real_canonical.TwiiKbarFact.from_view` 的 `ohlc_error or ""`、`stale_reason or ""`）皆為**文字欄位**空字串化，不產生數值；`_KBAR_REASON_CATEGORY.get(code, "日 K 資料未通過檢核")` 的預設值是**失敗句**，不是正常值。
- **人類可見字串**（安全／正常／中性／無風險／無需／續抱／沒有持股／0 檔／今日無）：真正的字串值只命中 `scenarios.py` 的 FAKE 值「無需處理（FAKE）」（👤 FAKE 下一步，帶 FAKE 標示）；其餘命中皆為註解中的**禁止語**（「⛔ 推導 safe／neutral／無需調整」）。
- **`views/{hold,me,target}.py`**：全檔量小，未見資料處理邏輯（僅呼叫 `render_*`／HTML 組裝）；`hold.py` 不呼叫 `render_cards`（與 §2.3 H-08 一致）。
- **限制**：不是 AST 掃描、未逐行讀 `scenarios.py`／`models.py`；結論僅為「補掃範圍內**未發現**缺值被當 0／正常／中性呈現的寫法」（單組、待獨立複驗）。

**Q6　市場頁距離接線還差哪些 Gate？**

**(a) 市場頁每個卡位／區塊尚缺的 Gate**（全部維持 HOLD／未授權；ID 定義見 §6，核心卡專屬項見 §6.3；「無專屬 ID」＝本回合在 BACKLOG／DECISIONS 查無）。**通則**：所有尚未接進 `real_feed` 的卡位，另需 `I1144-WIRING-GATE` 同類授權——**FACT（文件側 + 讀碼）**：DEC-164 G-9 明列「未核准：UI2 feed／section runtime 接線、資料來源變更」，且 `tests/test_ui2_guards.py::G2F_IMPORT_ALLOWLIST` 只放行兩個具名 service import；**新取數來源另需新授權**——FACT（文件側）：DEC-158 題號 D5 不核准新增每日落地 cron、DEC-164 G-9 不核准資料來源變更；**個別卡位是否算『新來源』＝INFERENCE**（例如 US10Y 走既有 `fetch_us10y_block` 是否算新來源，文件未明）：

| 卡位／區塊 | 現況 | 尚缺 Gate（ID） | 其他缺口 |
|---|---|---|---|
| 台股卡／日 K | 已接線（有真值） | 條件式：`I1140-OHLC-GUARD`、`I1140-TODAY-TZ`、`I1140-FUTURE-ASOF-ASYM`；DG-LIC（Yahoo） | 資料停在 2026-11-09、固定字樣「每日更新」（X-09、M-23） |
| 市場位階（現在狀態） | 已接線；目前恆未載入 | `NUI2-REALFEED-WARROOM-CONTRACT-INTEGRATION`、`NUI2-PREVIEW-CLOUD-STATE-FILES`、SG-10（位階 as_of）；旗標 `BREADTH_PROXY_SCORING_ENABLED` 屬 DEC-074 B | 部署端 NOT VERIFIED |
| Risk Cap | 固定 `⬜ 無法判定` | SG-06、RC-VISIBILITY、DEC-141 Q5 | 目前曝險無來源 |
| VIX | NP | Issue #1110 題號 D2（維持空槽，DEC-158）、`VN1-PG-VIX-ASOF`（已收盤日）、`NUI2-VIX-TWO-PATHS`、DG-LIC | 無乾淨 L3 |
| US10Y | NP | D1（僅口徑，實作需另授權，DEC-158）；DG-LIC（FRED）；FRED 當日值發布時刻 NOT VERIFIED | 新取數需新授權 |
| 利差 | NP | D3、`NUI2-REALFEED-SG-02-SPREAD-DEF` | 業務定義缺口 |
| DXY | NP | 無專屬 Gate ID（BACKLOG `ISSUE1110-DXY-UUP-LABEL` 為標示項）；DG-LIC | 備援鏈可落到 ETF（X-06） |
| PMI／景氣 | NP | D4、DEC-155、`NUI2-REALFEED-SG-03-PMI-DEF` | proxy PMI 不得為正式訊號 |
| 今日結論 | NP | `NUI2-PORT-CONCLUSION-CLAUSES`、`NUI2-CONCLUSION-REAL-FEED` | 依賴位階與 Aggregator |
| 今日主要風險 | NP | `NUI2-PORT-MAIN-RISK` | 依賴 session 更新鏈 |
| 是否需行動／下一步 | NP | `NUI2-AGGREGATOR-IMPL` | — |
| 主 CTA 更新 | disabled | `NUI2-REALFEED-SG-01-PREVIEW-REFRESH`（SG-01） | 會連網＋寫檔 |
| OneBrain | NP | `FUI-STAGE-G`、SG-09 | 無 producer |
| 為什麼／明細／原始資料表 | 不渲染 | `NUI2-PORT-READINESS-L3`、`NUI2-PORT-INDICATOR-TILES` | — |
| 融資餘額（資金與籌碼） | 不在 VM；L3 存在 | `I1144-WIRING-GATE`、DG-SCOPE、DG-PIT、DG-LIC、`I1140-MARGIN-SOURCE-TEXT`、`I1140-MARGIN-UNIT-MIX`（條件式） | — |
| 板塊資金（資金與籌碼） | 不在 VM；L3 存在 | `I1144-WIRING-GATE`、DG-COV、DG-PIT、DG-LIC、DG-SCOPE、`I1140-ETF-FAMILY-ABSENT`、`I1140-SECTOR-CRON-SCOPE`、`I1140-SECTOR-UNOBS-LABELS`、`I1140-SECTOR-DROPPED-PRICE`、`I1144-DATA-STORAGE-DECISION` | `partial` 無映射（N-3）；缺價股數不外露（N-4） |
| 大盤外資（資金與籌碼） | 不在 VM；無 L3 | 外資 L3（未授權、另案）＋ `I1144-WIRING-GATE`、DG-PIT、DG-LIC | `source` 標籤斷點（X-02）；與板塊外資不可比（X-03） |
| 三大法人單日／國際趨勢／成交量 | 不在 VM；無 L3 | 無授權路徑（無專屬 Gate ID；G2F 禁讀 session）；成交量另需全 0／全空隱藏規則 | 新 L3 與新授權 |
| 頂列 Active Sheet／帳號 | 固定占位 | `NUI2-AUTH-CONTRACT-GATE` | — |

**(b) 「市場資金與籌碼」接線面：確定 8＋不確定 1＋文案面 1（INFERENCE），與下列 10 項一致**（依文件側盤點，不保證窮舉；出處：`UI2_RUNTIME_PREGATE_RESEARCH_2026-11-11.md` §4.3＋§5.1，本回合逐項確認這些檔／符號存在；「是否需動」為 INFERENCE，因為尚未授權也無定稿設計）：
1. `src/services/ui2/real_feed.py`（`read_real_snapshot` 與新增 `_read_*`）
2. `tests/test_ui2_guards.py::G2F_IMPORT_ALLOWLIST`（及 `_G2F_BANNED_NAMES`：feed 不得自帶時鐘）
3. `src/services/ui2/real_canonical.py`（`RealFeedSnapshot`、事實 dataclass、`FieldState`→VM 映射）
4. `src/services/ui2/market_vm.py`／VM builder（新 L1 SectionVM；不動 `MARKET_CARD_IDS`）
5. `src/ui2/views/market.py`（OneBrain 之後渲染，確認 `skip` 不重複）
6. `src/services/ui2/scenarios.py`（FAKE 對稱占位，須帶 FAKE 標示）
7. `tests/test_ui2_real_feed.py::WIRED_PATHS` 與 `_paths`／`_all_fields`
8. 視窗量測（390／1440；`docs/vnext/newui2_realfeed/` 既有量測為舊值）
9. **不確定項**：`shared/ui2_contract/*`（新文案常數、`partial` 映射）——是否需動取決於 N-3 的映射決策與文案裁示，目前**尚無定稿設計**，故無法列為確定。
10. **文案面（INFERENCE：接線後會失真）**：`shared/ui2_contract/text.py::REAL_PREVIEW_BANNER_NOTE`「僅台股與市場位階為真資料」與開發面 `src/ui2/shell/app.py::_FEED_LABELS`「只接 2 項真資料」在接線後會與實況不符；且 `tests/test_ui2_drawer_browser.py` 以後者字樣選取 selectbox，改字樣須連動該測試。

→ 因此「至少 5 處」改為：**確定 8 個接線／守衛／量測面＋1 個不確定項（原因如上）＋1 個文案面（INFERENCE）**。詳見同批 `NEWUI2_MARKET_DATA_CONTRACT_VALIDATION_2026-11-12.md`。

---

## 9. 全稱句與查法；未查證／環境限制

| # | 全稱句 | 查法 | 可信度 |
|---|---|---|---|
| 1 | 預設路徑不可能進入 REAL | 讀 `src/ui2/shell/app.py::run`：`KEY_FEED` 預設 `FEED_FAKE`，唯一寫入點為 `_render_dev_surface` 的 selectbox（僅 `dev=True`）；`grep ui2_feed|KEY_FEED src/ui2` 只命中該檔；`grep ui2 app.py`＝0 行。**未跑 AppTest 窮舉**，未驗 Streamlit 是否另有 URL→session_state 綁定 | 單組讀碼；NOT VERIFIED（動態） |
| 2 | REAL 只有 3 個事實（卡、日 K、位階） | `src/services/ui2/real_feed.py` 僅 `_read_twii`／`_read_twii_kbar`／`_read_regime` 三個 reader，`read_real_snapshot` 只組這三項 | 單組讀碼（本回合重核） |
| 3 | REAL 帶真值的畫面欄位只有 2 個 | 同 2；位階列 `is_loaded=False`；本沙箱 `read_real_snapshot()` 實測 | 沙箱成立；部署端 NOT VERIFIED（僅旗標值與 session 寫入兩點） |
| 4 | `margin_fact_service`／`sector_flow_fact_service` 在 UI2 三目錄引用＝0 | `grep -rln "margin_fact_service\|sector_flow_fact_service" src/ui2 src/services/ui2 shared/ui2_contract`＝無輸出；全 repo `.py` 另 grep 僅命中兩 L3 自身、`shared/sector_flow_fact_thresholds.py`、兩測試檔；**僅靜態 `.py`**，不含動態 import、文件、設定檔 | 單組 grep |
| 5 | 「fact service 只有兩個」 | `ls src/services \| grep -i fact`；`grep -rl FieldState --include=*.py src shared scripts app.py app_ui2.py` 排除 `ui2` 路徑只命中兩 L3 | 單組 grep（以 `FieldState` 為定義） |
| 6 | 「讀取 `finmind_inst.parquet` 的 `.py`」清單（X-02） | `grep -rn finmind_inst --include=*.py .`，排除 `tests/` 與 `.claude/` | 單組 grep；不含動態組字串、notebook、文件 |
| 7 | 沒有任何欄位是 license-verified | 逐份閱讀文件；全域前提 | 待驗事項 |
| 8 | UI2 三目錄沒有把缺值補 0 的路徑 | 調查者與本回合補掃（§8 Q5）：`grep -rnE "or 0\b|\.get\([^)]*, ?0\)|fillna|else 0\b"`＝0 命中；非 AST 窮舉；`html.py` 字串拼接由調查者讀 | 低–中，單組 grep |
| 9 | Digest 0 production caller | `grep -rln "decision_digest_builder|decision_digest_summary|build_decision_digest" --include=*.py`，排除 `tests/`：僅 `shared/decision_digest_terms.py`、`src/services/decision_digest_assembly.py`、`src/services/decision_digest_builder.py`（digest 自家檔） | 單組 grep（本回合重核） |
| 10 | 衝突 17 項、過期宣告 14 項 | 單組逐份閱讀＋抽查，非窮舉；3C 重整後 `HANDOFF.md`／`PROJECT_STATE.md` 最新狀態調查者未讀 | 待驗事項 |
| 11 | B1「5 個面向皆未發現問題」 | §7.2 的方法清單；§7.4 與 §8 Q5 明列未讀範圍與補掃 | 單組；待獨立複驗 |
| 12 | CAPMAP「46 列 NONE／100 列」 | 本回合以腳本解析 CAPMAP 表格列計數（編號 `^[A-Z]{2}-\d\d`）；僅計數與等級，不重核各列 UI2 欄 | 單組腳本 |

**未查證／環境限制**：
- 未連外網；Cloud／真機／Playwright（Real 軸）／上游 API 可用性／cron 實際成功率皆未驗。
- 未重跑 5 份調查報告所引的 pytest（調查者自報數字僅轉述）；本文引用的測試名均已 grep 確認存在，**不代表目前綠燈**。
- TWSE／TPEX／data.gov.tw／Yahoo／FRED 授權原文 NOT VERIFIED；FinMind PARTIALLY。
- 11-10、11-11 是否為台股交易日（無行事曆）；`macro_state.json` 在部署端是否存在；`get_macro_state` 在「warroom 存在＋旗標 False」分支的逐行行為。
- 欄位數量（45／46）為人工建模，未重算。
- FinMind 外資／融資 dataset 是否含上櫃；`:Foreign` 列是否含外資自營商（docstring 轉述）；3 個偶發板塊標籤成因；15761 的組成（INFERENCE：T86 `selectType=ALL` 含權證等；未逐檔驗）。
- GitHub Issue（#1121／#1130／#1132／#1134／#1136／#1140／#1144）原文不在 repo；DEC 內客戶原文皆為轉錄，逐字性無法驗證；DEC-158～171 依 DEC-172 D3 須逐項核查來源，本文未核。
- **已登錄於 main：DEC-174（PR #1166，main `dae78eea`）；本文不引申其授權範圍。**

---

## 10. 本回合重核紀錄與勘誤

### 10.1 重核（方法與結果）

| # | 項目 | 方法 | 結果 |
|---|---|---|---|
| V1 | 預設路徑只到 FAKE cold；Real 只經開發面 | 讀 `src/ui2/shell/app.py`（`run`、`_render_dev_surface`、`dev_surface_enabled`）；`grep ui2_feed|KEY_FEED src/ui2`；`grep ui2 app.py` | **一致**（`KEY_FEED` 預設 `FEED_FAKE`；selectbox 僅 `?ui2_dev=1` 渲染；`app.py` 0 行引用 ui2）。動態（AppTest）NOT VERIFIED |
| V2 | REAL 帶真值只有台股卡 close＋日 K（同一 parquet）；位階已接線但目前恆「尚未載入」 | 讀 `real_feed.py`、`allocation_service.get_macro_regime`、`macro_state_locker.get_macro_state`（`_nowr_no_real_breadth`）；`grep warroom_summary` 於 UI2 三目錄（僅說明文字，無寫入）；寫入點僅在 `src/ui/tabs/macro/section_state.py`、`section_traffic_light.py`、`src/services/warroom_apply.py`；`git ls-files` 無 `macro_state.json`／`risk_cap_state.json` 且 `.gitignore` 列出；`BREADTH_PROXY_SCORING_ENABLED=False`；**沙箱實測 `read_real_snapshot()`**：`regime=unknown, light=⬜, source=unloaded, is_loaded=False`；`twii.close=(41661.69921875,), as_of=2026-11-09`；`kbar` 為 `TwiiKbarFact` | **一致** |
| V3 | 兩 L3 在 UI2 三目錄引用＝0 | `grep -rln` 三目錄＝無輸出；全 repo `.py` grep（排除 worktree 副本）僅 `margin_fact_service.py`（自身）、`sector_flow_fact_service.py`（自身）、`shared/sector_flow_fact_thresholds.py`、兩測試檔；`margin_fact_service.py` docstring 自述「目前 0 production caller」 | **一致**（僅靜態 `.py`） |
| V4 | `finmind_inst.parquet` source 斷點 | `python -I` 唯讀 `pd.read_parquet`：欄 `date foreign_buy source fetched_at`，4939 列；`source` 分布 `…:Foreign`＝4920（2006-09-29～2026-10-08）、`…:Foreign_Investor`＝19（2026-10-12～2026-11-09）；同一日無兩種標籤並存 | **一致** |
| V5 | 板塊外資分項 vs FinMind 大盤外資 | `python -I`：`sector_flow/daily_net.parquet` 逐日 `foreign_yi`（所有原始標籤列，`min_count=1` 加總）inner-join `finmind_inst.foreign_buy` 逐日加總；共同日 37（2026-09-11～2026-11-09），同號 36，逐日絕對差中位 55.42、最大 239.57（億）；最新日 −942.44 vs −900.56，差 −41.87 | **一致**（調查者稱中位 55.4、最大 239.6、−942.4／−900.6／−41.9） |
| V6 | 「只接 2 項真資料」文案 | `grep -rn "只接 2 項" src tests app_ui2.py`：`src/ui2/shell/app.py`（`_FEED_LABELS`）與 `tests/test_ui2_drawer_browser.py`；`shared/ui2_contract/text.py` 的 `REAL_PREVIEW_BANNER_NOTE`＝「僅台股與市場位階為真資料」 | **一致**（只描述事實，未改文案） |
| V7 | 卡片新鮮度 | 讀 `compute_cache_staleness`／`STALE_DAYS_DAILY=7`／`CACHE_DATASET_CADENCE`（`macro_cache_reader`）；沙箱 today 2026-11-12；另讀 `sector_flow/reader._compute_staleness`（`tw_now().date()`）與 `margin_fact_service._taipei_today` | **一致**（age_days=3、is_stale=False；基準日差異＝`I1140-TODAY-TZ`） |
| V8 | 成交量備援迴圈 `for _div in [1e8,1e4,1e3]` | 讀 `src/data/macro/leading_indicators.py` 的 `twse_volume` 備援段與 `vol_dict.update(...)` 合併處；讀 parquet 最近非 NaN volume＝4,239,400（2026-11-05），除以 1e8＝0.042（不入）、除以 1e4＝423.94（入 `5<v<20000`） | **迴圈與合併為 FACT；數值偏差標 INFERENCE**（未實際觸發備援；未取得同日 FMTQIK 對帳） |
| V9 | 文件側過期宣告抽驗 ≥5 項 | ST-1（`market.py` 有 `kbar_chart_html`、`G2F_IMPORT_ALLOWLIST` 含 `twii_kbar_fact_of`、兩 PR 提交時間）；ST-2（Gap Audit 檔頭「現行 UI2」說明句原文存在）；ST-4（`api_diagnostic.py` 的 `_mask` 命中 0）；ST-11（BACKLOG 同檔新舊兩列並存）；ST-14（`FUI-STAGE-F` 行號與矩陣所引不同）；另 CF-3（`fetch_us10y_block` 簽名外 0 次使用 `fred_api_key`）、CF-5（`cdn.cboe.com` 僅在 `risk_radar.py`） | **全部一致**（ST-4 僅確認症狀消失） |
| V10 | 台股資料實況（第二版新增，第三版擴充） | 查 main 對該路徑的提交紀錄：最後一筆 `4432d5a7`「每日總經歷史增量：2026-11-09 (#1103)」2026-11-10 08:46:18 +0800；再 fetch 後 main 仍為 `7eb48d6c`，此路徑之後無新提交；`metadata.json` `twii_ohlcv.last_updated=2026-11-09` | **一致**（本回合自行重驗） |
| V15 | 每日資料 PR 狀態（第三版新增） | 查 `origin/auto/data-macro-history`／`auto/data-sector-flow`／`auto/data-macro-forward-test` 最新提交：`fc447def`（2026-11-11 16:59:56 +0000）、`1efb178a`（2026-11-11 17:21:40 +0000）、`428258b3`（2026-11-11 17:28:10 +0000）；比較分支與 main 的差異含 `twii_ohlcv.parquet`；取分支上的 parquet 讀末日＝2026-11-10（4914 列）；GitHub MCP 讀 PR #1124／#1125／#1126：皆 `state=open`、`merged=false`，`mergeable_state`：讀取當時為 `behind`（另有審查讀到 `unknown`）；三 PR 的 base 仍是舊的 `043a4d21`；該欄位由 GitHub 惰性計算、隨時會變，不作為判斷依據；#1124 head＝`fc447def`；#1124 內文資料狀態段：`finmind_inst`／`finmind_margin` 資料日 2026-11-11、`twii_ohlcv` 2026-11-10；BACKLOG／DEC-159 grep 確認「#1124～#1126 未處置、PIT NOT VERIFIED」 | 本回合自行重驗 |
| V11 | 外資差距拆分（第二版新增） | 同 V5 加上以 `source` 後綴標記每日標籤：舊標籤 18 日（2026-09-11～2026-10-08）中位 60.18／最大 239.57（2026-09-18）／同號 18；新標籤 19 日（2026-10-12～2026-11-09）中位 49.19／最大 140.28／同號 18 | **與 QA 數字一致** |
| V12 | CAPMAP 計數（第二版新增） | 腳本解析 CAPMAP 表格：100 列（MK25／TG31／HD16／ME14／DT6／SY8）；測試證據欄 `NONE` 46 列（critical 1／major 23／minor 21／none 1）；自 `f4d86b4f` 起對 UI2 路徑的提交紀錄只有 `907322aa` | **與 QA 所述（約 100／約 46／重要約 23）一致**（critical＋major＝24） |
| V13 | B1 未讀範圍補掃（第二版新增） | 見 §8 Q5 | 補掃範圍內未發現缺值預設寫法 |
| V14 | 讀取者／服務清單（第二版新增） | `grep -rn finmind_inst --include=*.py`；`ls src/services \| grep -i fact`；`grep -rl FieldState|DataStatus --include=*.py src shared scripts` | 見 §4 X-02、§3 名詞定義、§4.2 |

另本回合讀 L3 實況（`python -I`，唯讀）：`get_margin_fact()`→`OK`、5399.15741 億、as_of 2026-11-09、非 stale；`get_sector_flow_fact()`→`OK`、`complete`、41／38／3、合計 −920.24812237 億、非 stale。`metadata.json` per_day：18026−15761＝2265（算術吻合）。

### 10.2 勘誤

第一版（head `ba037e5a`）已記錄 6 項勘誤（成交量示例數字、測試檔歸屬、absent 計數、`:Foreign` 成分降為 NOT VERIFIED、BACKLOG 同檔新舊並存、行號改用 ID）；第二版（回應 #1165 審查回饋）**新增更正**：

1. **位階分類**：第一版 M-05／T-04／Q2 把位階標成 READY／「可用」；更正為「已接線，但在 UI2 獨立 session 目前恆為未載入」，分類改 NOT VERIFIED，且 X-01 的「永遠」改為條件式。
2. **`is_proxy` 位置**：第一版把 `is_proxy: true` 寫成在 `tw_pmi.parquet`；實際在 `data_cache/macro_last_good/tw_pmi.json`，parquet 欄位為 `date pmi source fetched_at`（本回合讀檔確認）。
3. **U-06／U-07**：第一版把 `calibration_status_service` 歸 Rule Registry；BACKLOG `NUI2-REALFEED-NEXT-SESSIONFREE` 與 `NEWUI2_REAL_FEED_MAPPING_2026-11-03.md` E12／E14 顯示 Rule Registry→L0 `RULE_ID_ALLOWLIST`、System Information→`calibration_status_service`（＝U-07）。
4. **`CACHE_DATASET_CADENCE` 出處**：在 `src/data/macro/macro_cache_reader.py`，不是 `shared/staleness.py`（後者只有 `STALE_DAYS_DAILY` 與 `stale_days_threshold`）。
5. **`get_sector_flow_view` 呼叫寫法**：改寫為 `etf_tickers=None, include_stock_watchlists=False, use_active_selection=False, strict=True`（對齊 `NEWUI2_REAL_FEED_MAPPING_2026-11-03.md` T6）。**但 QA 稱「只傳 `strict=True` 會觸發 Sheet 讀取」本回合未成立**：`_collect_stock_watchlist_tickers(None)` 在 `stock_sheet_id` 為空時立即回 `[]`、不讀 Sheet；已在 T-06 如實記錄，並保留「highlight 恆空、不得顯示無持股」的警語。
6. **ID 存在性**：`TGT-01`、CAPMAP 編號 `HD-xx` 只在 `docs/vnext/*`，不在 BACKLOG／DECISIONS（§6 說明已更正）。
7. **索引引用**：移除不可追溯引用（調查報告內部的 `T-x`、`F5`、`F7`、「C1 報告」、「原料」）；改為 repo 檔案／符號，或標「調查者 FACT／本 PR 未重核」。
8. **基準日不一致**：由「新增觀察」改為併入既有 BACKLOG `I1140-TODAY-TZ`（第三版再註：此併入判斷為 INFERENCE——該 BACKLOG 原文範圍較窄）。
9. **37 日外資窗**：橫跨 source 標籤斷點，已拆分報告（X-03）；最大值 239.6 全來自舊標籤日。
10. **NOT-A-DEFECT 計數**：與 §7.3 表對齊（見 §7.1）。
11. **行號引用**：刪除 `src/ui2/shell/app.py:42`、「約 1537–1557 行」、「約 1125 行」、「第 330 行」等，改用檔:符號。
12. **D1～D5 消歧**：Issue #1110 題號（DEC-158）≠ DEC-172 治理 D1–D5；DEC-155 來源類別標為 ChatGPT 獨立裁示。
13. **「接線面至少 5 處」**：改為逐項列表（§8 Q6b；確定 8＋不確定 1＋文案面 1）。

第三版（回應 head `c03b24cf` 複驗的 11 條）**新增更正**：(1) 補每日資料 PR #1124～#1126 證據（V15），停更原因標 INFERENCE；(2) §3.3 篩選依據改述為代理條件並補表 B，更正「分散在 §2 各列」「多為診斷／教學面」兩處不準確敘述，並寫出 CAPMAP「真資料＝是」與本文的字面衝突；(3) T-11 由 READY 改 NOT VERIFIED；(4) Q5 統一說明與 DEC-174 查核措辭；(5) Q6 補通則與核心卡專屬 Gate（§6.3）、接線面補文案面；(6) 新增 §0.1 不可直接採信的欄位；(7) T-06 出處註明 `strict=True` 為本文所加；(8) §2 完整性改為「以標籤對應後無實質遺漏」；(9)`I1140-TODAY-TZ` 併入標 INFERENCE；(10) DEC-174 措辭（第四版已改為「已登錄於 main：DEC-174（PR #1166，main `dae78eea`）」）。

---

## 11. 下一批施工候選（最多 3 項；**皆為 RECOMMENDATION，非授權；不得自動跨越 Decision Gate**）

> DEC-174 規定每批最多三項；以下只放 3 項。條件式者註明「需客戶先裁示，未裁示則不計入該批」。

| # | 項目 | 需客戶裁示？ | 前置 Gate | 風險 | AI 總管推薦 |
|---|---|---|---|---|---|
| 1 | **獨立複驗本文與同批市場契約文件**：派第二組（非作者）重做 §10 的 V1～V15 關鍵 FACT，特別是 X-02／X-03／X-10、CAPMAP 對帳（§3.3），以及部署端（Cloud）位階實況 | 否（內部 QA；§-2 規則 4） | 無 | 低；docs-only。不做的風險：全稱句長期停在單組待驗 | **推薦先做**。同時決定本批兩份文件是否升格為被引用的前提 |
| 2 | **把「接線前須客戶裁示」整理成商業語言的一頁決策單**（DG-SCOPE／DG-COV／DG-PIT／DG-LIC 四問＋AI 推薦） | 是（決策單本身要客戶看） | `I1144-WIRING-GATE` 不在此批解除；僅整理決策材料 | 低；不動 runtime。風險＝被讀成授權（各表已標 HOLD） | 推薦；與 #1 同批或其後。（新候選 N-1～N-4、§7.3 文案漂移項、§3.3 CAPMAP 未承接清單的 BACKLOG 登記屬總管治理流程〔另案 PR〕，**不計入本批施工項**） |
| 3 | **（需客戶先裁示，未裁示則不計入該批）🗂 資料頁新鮮度總覽的文字線框草稿**：目前畫面沒有任何總覽新鮮度的位置（§2.5 後果），REAL 已掌握 TWII as_of／stale | 是（UI 版面異動，§-1.5 草稿先行；客戶拍板前不得寫 UI code） | 新欄／分母須先過 Data Contract Gate；不得以 cron 時刻冒充觀測日 | 中；易擴大為跨頁重排。與 `NUI2-P6-*` 既有線框決策可能重疊（需先查） | 暫不推薦自動啟動；列為客戶可選項，**不跨越 Gate** |

### 11.1 需客戶裁示的待決事項（不計入批次項數）

| 待決事項 | 現況 | 前置 | 風險 | AI 總管推薦 |
|---|---|---|---|---|
| **是否處置每日資料 PR #1124～#1126**（合併／關閉／維持 HOLD；TWII 卡資料日停在 2026-11-09 與此相關，因果＝INFERENCE） | DEC-174 的 HOLD 清單與 BACKLOG 記為維持未處置，禁止順手合併／改寫／rebase；PIT 未驗（#1126 PIT 未驗；#1124／#1125 的 PIT 亦記為 NOT VERIFIED）。#1124 內文「資料狀態」段（本回合重讀）顯示：分支上 `finmind_inst`／`finmind_margin` 資料日到 2026-11-11、`twii_ohlcv` 到 2026-11-10 | 先有 PIT 證據；PR 內文要求人工審閱與 `ui2-browser-gate` 同 head 綠燈；`mergeable_state`：讀取當時為 `behind`（另有審查讀到 `unknown`）；三 PR 的 base 仍是舊的 `043a4d21`；該欄位由 GitHub 惰性計算、隨時會變，不作為判斷依據 | **風險（INFERENCE）**：自動資料未經審閱進主線；即使合併 #1124，TWII 卡也只到 2026-11-10；釘住快取日期的測試可能改變（`test_real_cache_pinned_snapshot` 等會 skip 或改測資料）；Cloud 顯示的資料口徑改變（含 `tw_pmi.json` proxy 欄）。**不處置的風險**：卡片持續顯示舊資料日、固定字樣仍寫「每日更新」 | **推薦：本批與下一批都不處置**；先做唯讀 PIT 檢查（三 PR 資料列的可得日、有無修訂）與 cron 成功率檢查，再出商業語言決策單請客戶裁示合併／關閉策略。**本批不得處置那些 PR** |

> 本文為稽核證據。接線、新增 L3、改文案、改 UI 結構、改資料保存方式——**每一項都需客戶另行授權**。
