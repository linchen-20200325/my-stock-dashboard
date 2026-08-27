# stock_trap_and_stale.md — 假「已棄用」註解 + 快取無 TTL（my-stock-dashboard）

- **執行組**：資料工程組
- **日期**：2026-08-27
- **規格來源**：`scratchpad/gc_inventory_stock.md`（唯讀盤點組）+ `scratchpad/gcwork/`
- **邊界**：只動 `market_strategy.py` / `macro_cache_reader.py` /
  `calibrate_health_weights.py` / `section_long_term.py` / 新增測試檔。
  **未動**任何 A 組、B 組檔案，未動 `CLAUDE.md` / `PROCESS.md`，**未刪任何檔案**。

---

## 誠實聲明（先讀）

1. 本檔全部結論由**單一組（本組）**產出，**未經第二組獨立複驗**（§-2 規則 6）。
   凡「只有這幾處」「全都掃過了」一律只能當**待驗事項**。
2. 盤點組自陳它的 AST 掃描**只掃 top-level def/class**。本組**另跑一輪補掃**
   class 內 method + nested function（`scratchpad/dg/scan3.py`）→ **0 命中**，
   也就是那個盲區在「棄用標記」這一題上是空的。**這句話同樣沒有第二組驗過。**
3. 本輪**新增了一個 production 行為變更**（校準 cron 過期即 `SystemExit`），
   下面「行為變更」段有完整說明與可見後果。

---

## 組 1｜假「已棄用」註解

### 1-1 `src/services/market_strategy.py::market_score` —— 註解說謊，已改寫

**實查（自己重跑，不是轉述盤點組）**：
- `get_market_assessment()` 在 `market_strategy.py:391`（盤點組寫 `:355`，行號已漂移）
  **無條件**呼叫 `market_score`。
- 合併是 `{**old_result, **regime_result}`，regime 在右邊 →
  `score` / `max_score` / `signals` **一律被蓋掉**。
- 用 AST 抽兩個函式的 return dict key 實測：
  `market_regime` → bullrun/label/m1b_m2_gap/max_score/missing_factors/regime/score/score_partial/signals
  `market_score`  → confidence/max_score/score/signals/status
  ⇒ **`market_score` 對外的獨佔輸出只剩 `status` 與 `confidence` 兩個 key。**
- 這兩個 key 的下游消費端：本組掃全 repo（149 處 `status`/`confidence` 取值）**沒有找到**。
  ⚠️ 這是**單組結論**，只能當待驗事項，**不是刪除許可**。

**處置**：把註解改成**現在的真實角色**，不是把「已棄用」三個字刪掉：
寫出（a）誰在呼叫、（b）它現在只提供哪兩個 key、（c）**三條退場條件**
（無消費端 + 同步刪呼叫與合併 + 兩條 §1 迴歸測試另找宿主）、
（d）標明「無消費端」是單組結論。呼叫行 `:391` 另加一行「這不是相容性殘留」。

⚠️ 一個實作細節，寫下來防後人踩：**誠實註解裡不得照抄那句舊標記的原字串** ——
守衛是靠掃描標記文字判定的，照抄一次會讓守衛把這段更正註解本身判成違規（實測過）。

### 1-2 `detect_mk_golden_inflection` DEPRECATED alias —— 改走遷移，不是改註解

`macro_helpers.py:729` 的 alias 標 `DEPRECATED，勿用於新程式碼`，而
`section_long_term.py` 還在 import 它（盤點組寫 `:43`，實際 `:41`→ 遷移後 `:51`）。

**處置選遷移而不是改註解**，理由：alias 自己的註解就寫「**待全部 caller 遷移完成後移除本行**」，
而 `section_long_term.py` 是它**最後一個 production caller**。遷到正名後的
`detect_cpi_fed_double_top`（alias 指向同一物件，**行為零變更**；`section_state.py` 早已用新名）
之後，那個 DEPRECATED 標記就變成**真話**。

⚠️ **邊界註記（回報總管）**：`macro_helpers.py` 屬 A 組，本組**一個字都沒動**。
因此該檔 alias 上方那段「v19.173 當下仍以舊名呼叫的地方：section_long_term.py:43」
現在是**過期的快照**（它自帶「v19.173 當下」的時間戳，不是現在式謊言，但仍建議由
A 組或後續派工順手更新）。本組**沒有**因此被迫動 A 組的檔案。

### 1-3 `ui_widgets.BREADTH_DEPRECATED_TITLES` —— 確認過，**沒動**

實查：`ui_widgets.py:127`，docstring 自陳「留作考古 + **守衛測試的黑名單來源**」，
`section_overview.py:67` 實際引用。**名字含 DEPRECATED，本體是活的守衛資料。**
本組除了讀它以外沒有碰它，並在 `test_deprecation_honesty.py` 加了一條
`test_name_containing_deprecated_is_not_flagged` 把「只看標記文字、不看符號名」
這個判定方式釘住 —— 日後有人把判定改成比對符號名，那條會轉紅。

### 自己再掃一輪的結果（第三、四處）

工具：`scratchpad/dg/scan.py`（top-level，標記→caller）、`scan2.py`（反向：宣稱零 caller 但仍被引用）、
`scan3.py`（補盤點組盲區：method / nested function）。

| # | 位置 | 病症 | 處置 |
|---|---|---|---|
| **#3** | `src/ui/render/etf_render.py::MACRO_ALLOC` | **反方向的謊**：註解寫「保留給尚未遷移的 caller（`etf_tab_ai._generate_report` 的 prompt 文案）作 fallback」，但那個 caller 已在**同一個版本 v19.170** 被移除（`etf_tab_ai.py:10/24/170` 三處註解自陳不再引用）。實際唯一引用是 `etf_dashboard.py` 的 `# noqa: F401` re-export shim。→ 註解**留住了一個其實可以刪的東西**，與 1-1 剛好相反。 | **未修**（不在檔案邊界內），已登記於守衛的 `_ACCEPTED` 表並寫明理由 |
| **#4** | `etf_render.py::MACRO_DESC` / `::_PERIOD_MAP` | **行號腐爛**：註解指名的 shim 行號（`etf_dashboard.py:40` / `:46`）都已漂移；`_PERIOD_MAP` 更嚴重 —— 名字沒變但**值的語意已從「計算區間」變成「下載窗」**，留著本身就是誤導源 | 同上，已登記 |
| （查證後**排除**） | `src/compute/etf/portfolio_coherence.py::classify_core_satellite` | docstring 說「ETF 投組頁不再使用」對投組頁**成立**，但同檔 `assess_core_satellite` 仍呼叫它；兩者 production 皆 0 caller。**標記沒有說謊**，只是沒提同檔 caller | 未修，已登記 |
| （查證後**排除**，本組掃描的假陽性） | `src/ui/pages/data_coverage.py:21` 「`detect_frozen_columns` 全 repo 零 caller」 | 讀完上下文：那是「**問題 → 修法**」的稽核敘事（下一行就是「修：本檔接上」），**不是現在式宣稱**。且 HEAD commit `646b7fd` 已把它接線 | 不動；本組據實記為自己的假陽性 |

**盲區補掃**：`scan3.py` 掃 class 內 method + nested function 的棄用標記 → **0 命中**。

---

## 組 1 的守衛怎麼設計的

問題：**「把假註解放回去」本身測不出東西** —— 程式行為沒變。
所以守的不是行為，是「**標記與實際 caller 狀態不得矛盾**」。

`tests/test_deprecation_honesty.py` 三層：

1. **通用矛盾守衛** `test_no_deprecated_marker_on_symbol_that_still_has_callers`
   掃 `src/ shared/ scripts/ infra/ tools/ mcp_server/ app.py` 全部 top-level 符號，
   取**緊貼定義的註解區塊 + docstring**，命中強標記
   （`DEPRECATED|deprecated|已棄用|已廢棄|已退役|不再使用|勿用於新程式碼|不再被呼叫`）
   即比對 production caller。有 caller → 紅。
   - **刻意不收**「舊版 / legacy」：本 repo 有大量「舊版寫錯，已修」的歷史說明句，收進來全是雜訊。
   - **caller 判定刻意不用名稱比對**（盤點組就是這樣誤判的：`shared/regime_arbiter.py`
     有個**參數**叫 `market_score`）。只認三種不會誤判的引用：
     (a) `from X import S`、(b) `obj.S` 屬性存取、(c) **定義檔自身**檔內的 `Name`。
     別的檔案裡的**裸 Name** 一律不算 —— 在別檔要用 S 必須先 import，而 import 已由 (a) 抓到。
   - `_ACCEPTED` 白名單：每筆都要寫**誰該修、為什麼本輪沒修**。這是「暫緩」不是「豁免」。
2. **白名單防腐** `test_accepted_table_has_no_stale_entries`
   矛盾解除了卻忘了把白名單那筆拿掉 → 白名單自己變成下一個說謊的文件。這條擋它。
3. **契約守衛**（擋通用守衛擋不到的那一種）
   GC 的人若把假註解**和**函式**和**呼叫行一起刪乾淨，標記消失 → 通用守衛無話可說，
   但 `status` / `confidence` 已經靜默不見。故加：
   - `test_market_score_is_reached_by_get_market_assessment`：monkeypatch 成回哨兵值的假函式，
     哨兵沒出現在結果 dict 就是呼叫鏈被剪斷；
   - `test_market_assessment_still_exposes_status_and_confidence`：真實路徑下兩個 key 必須在；
   - `test_deprecated_alias_has_no_production_caller`：alias 必須維持「真的沒人用」。

---

## 組 2｜快取讀取端不檢查年齡

**共用做法**：全部沿用 `src/data/sector_flow/reader.py::_compute_staleness` 的規矩
（**判不出來 → 視為過期**，不假設新鮮），**不另發明一套**；門檻一律走 L0 SSOT
`shared/staleness.py`，本輪**沒有新增任何門檻數值**。

新 API 都放在 `macro_cache_reader.py`（L1）：
- `read_cache_metadata(cache_dir)` — 讀 `data_cache/metadata.json`（cron 的自陳狀態）
- `CACHE_DATASET_CADENCE` — dataset → (頻率, `MACRO_PUBLICATION_LAG_DAYS` 的 indicator key)
  ⚠️ 這是**頻率分類**不是門檻
- `compute_cache_staleness(dataset, *, cache_dir, df, today)` →
  `{is_stale, reason, as_of, age_days, periods_behind, upstream_error, meta_last_updated}`

**頻率感知**（這一點很重要，做錯會天天假紅燈）：
`finmind_m1m2` 的 `date` 欄是**資料月月初**，依 `shared/staleness.py` G2 區塊的明文，
月初 as_of **不得**用日曆天量 → 走 `monthly_release_status`（以「期」為單位）。
實測：2026-06 這一期在 2026-07-20 仍是當期（日曆天已 49 天），到 2026-08-16 才落後 1 期。

### 2-1 `finmind_m1m2.parquet` × `calibrate_health_weights.py` —— 加輸入閘門（**行為變更**）

實測現況：
```
finmind_m1m2 最新資料月 2026-06-01（87 天前），已落後 1 個發布期
metadata.json → last_updated 2026-06-01 / last_error '抓取結果為空'
```
原本 `main()` **只擋「檔案不存在」**。檔案在、讀得到、239 列 —— 於是 cron 每季照跑，
把三個月前的 M1B-M2 gap 當當期特徵擬權重，寫成 `MACRO_HEALTH_WEIGHT_PROPOSAL.md` 給人審。

**處置**：新增 `check_inputs_fresh()`，過期 or 上游自陳失敗 → `SystemExit`，訊息裡講出
**哪一個資料集、舊到什麼時候、上游報什麼錯、正解是什麼**。
另外：能跑時，提案尾端會自動附上每個輸入的 as-of 表（§2.2 provenance，讓人審者看得到吃的是哪天的資料）。

⚠️ **刻意不提供旁路旗標**。留一條「加個旗標就能跑」的路，等於留下一個可被引用來
合理化「這次先跑一下」的正當出口。守衛 `test_gate_has_no_bypass_flag` 釘住這件事。

**可見後果（必須讓總管知道）**：`.github/workflows/calibrate_health_weights.yml`
沒有 `continue-on-error`，排程是每季首日 UTC 10:00 → **下一次 2026-10-01 會紅**，
除非上游在那之前修好。**這正是要的效果**（現在是「綠燈但吃過期資料」），
但它是**行為變更**，不是重構。

### 2-2 `load_twii_close` / `load_v2_chart_series` —— 年齡帶出來，契約不變

回傳的 Series 掛 `.attrs`：`cache_dataset / is_stale / stale_reason / as_of / age_days / upstream_error`，
過期時另 print 一行（§1 出聲不吞）。
**dict 的 key 集合、Series 內容、回傳型別一字未改** → 既有消費端
（`services/macro_v2_service.get_chart_series`）行為零變化。

⚠️ **已知缺口，據實登記（本輪未修，已寫進 `macro_cache_reader.py` 檔頭）**：
`macro_v2_service.get_chart_series()` 會把 Series 轉成 `[(iso_date, value)]` 再進
`@st.cache_data`，**`.attrs` 在那一步就掉了**；`tab_macro_v2.py`（L5）也還沒有顯示過期旗標的位置。
要讓使用者在畫面上看見，必須同時改 `services/macro_v2_service.py`（L3）與
`src/ui/tabs/tab_macro_v2.py`（L5，**B 組檔案**）—— 兩者都不在本次派工的檔案邊界內。
**現況 = L1 已誠實算出並 print，但畫面仍看不到。這是待辦，不是已完成。**

### 2-3 `macro_last_good/tw_pmi.json` —— 到期**前** 21 天讓 CI 轉紅

事實：`cached_at 2026-07-01` + TTL 90 天（`macro_core._MACRO_CACHE_TTL_DAYS`，強制執行）
→ **2026-09-29 靜默過期**；`series_id='cier-seed-2026-06'` = **人工 seed**；
且 `metadata.json` 顯示 tw_pmi 抓取持續為空（`last_updated: null`）→ **沒有東西會來接替它**。

**怎麼做到「到期前就知道」**：`tests/test_macro_last_good_expiry.py` 在
**到期前 `_WARN_LEAD_DAYS = 21` 天**就讓 CI 轉紅，而不是等到期當天靠使用者發現畫面變了。
- 21 天的理由：CIER PMI 每月第 1 個營業日公布，三週的窗**至少涵蓋一個完整公布週期**
  （= 還來得及讓真資料自己接上），同時留得下人工判斷的時間。
- TTL **從 production SSOT 讀**，本檔不複寫（`test_ttl_is_read_from_production_ssot`
  用 `inspect.getsource` 釘住取得方式）。
- 另有 `test_report_current_headroom` 每次跑都 print 剩餘天數（現況：**剩 33 天，紅燈日 2026-09-08**）。
- 紅燈訊息直接寫出正解，並**明文禁止**用「把 TTL 調長 / 把 cached_at 往後改」變綠
  —— 那只是把炸彈往後挪，而且會讓一個 2026-06 的數字冒充更晚的當期值（§1）。
- `test_manual_seed_entries_are_labelled_as_seed`：seed 條目必須自己講明是 seed，
  日後有人把標記拿掉（讓它看起來像真抓）→ 轉紅。

**本輪沒有動 `data_cache/macro_last_good/tw_pmi.json` 一個位元組**（§5 凍結快照 + 不在邊界內）。

---

## 明確沒做的（本波範圍外，遵照派工）

- **沒刪任何檔案**：`stock_etf_dashboard/`（2,658 LOC）與全部孤兒清單一律未動。
- **沒動兩個總經 Tab**：合併 = 分頁結構異動，要先出線框給客戶；且
  `tab_macro_v2.py:19` 自陳「2026-08-25 **user 核准**兩個分頁並排」。
- **沒改任何門檻數值**。

---

## ⚠️ 交付紀錄：一次跨組 commit 碰撞（據實登記，已由對方自行解開）

多組共用同一個 checkout（同一個 git index），過程如下，寫下來防重犯：

1. 本組完成後 `git add` **逐檔指定**（未用 `-A` / `.`），準備以自己的訊息 commit。
2. 在那之間，**另一組把共用 index 一次 commit 掉了** → 本組 7 個檔案被收進
   他們的 commit `a76efe8`（18 檔）。本組當下**沒有自行改寫歷史**：
   要修就得 `--amend` 一則含有他組工作的 commit，那既超出本組檔案邊界，
   也屬「重寫歷史」，不在常設授權的免請示範圍內。
3. 對方隨後自行改寫歷史（`a76efe8` → `d43292a`），把本組 7 檔**釋回工作目錄**，
   本組才得以用自己的訊息獨立 commit（`8a73814`，只含本組 8 檔，逐檔驗過
   `git show HEAD:<檔>` 與工作目錄一致）。
   ⚠️ `a76efe8` **已不在 branch 上**（object 仍在，但只能靠 reflog / 直接指定 hash 取用）——
   本行保留該 hash 純粹是為了讓這段經過查得到，不是可用的參照點。
   後續該組又再改寫一次（現行 `fb7f695`），故本檔提到的任何他組 hash **都可能已失效**;
   要追溯請以「檔案 + `git log --follow`」為準，不要以 hash 為準。

**方法性教訓**：多組共用同一個 checkout 時，`git add` 逐檔指定**不足以**防撞 ——
index 是共用的，別人一個沒有 pathspec 的 `git commit` 就會把你暫存的東西一起帶走。
安全做法是 **`git commit -F msg -- <逐檔路徑>`**（pathspec 形式，繞過 index
直接提交指定路徑），或各組使用獨立 worktree。本組第二次即改用 pathspec 形式。
