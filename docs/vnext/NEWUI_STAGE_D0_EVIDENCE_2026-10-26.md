# 新 UI Stage D0 實證報告（Stage B 草稿 INFERENCE／未複驗項 vs 最新 main）

- **日期**：2026-10-26
- **批次**：`NEWUI-STAGE-D0-EVIDENCE`（DEC-089 條件 2）
- **性質**：docs-only 實證報告。**0 程式碼、0 測試、0 navigation 變更、不刪舊 UI、不改投資語意、不新增資料來源。** 不改 Stage B 草稿本檔（更正只列於第 8 節）。
- **狀態**：**各結論分別來自單一 agent，未交叉；僅標「總管已驗」者經總管抽驗；整份報告原始版本未經獨立 QA（QA 修正已套用，見 10.4）**（`CLAUDE.md` §-2 規則 6）。

## 0. 範圍與方法

| 項目 | 內容 |
|---|---|
| 基準 | main `96206a96`（#940 合併後）；唯讀 |
| 產出方式 | 4 組唯讀 agent（G6／G3；G4；導覽殼與動態引用；🎯 輸入面與 D5）各自讀碼；各結論分別來自單一 agent，未交叉；僅標「總管已驗」者經總管抽驗 |
| 總管抽驗 | 見第 10.1 節「總管已驗」清單；其餘全部是單一 agent 結論 |
| 沙箱限制 | 無法連外網（不能量測外連延遲／重複外連）；無法實機操作 Streamlit（所有「手機點擊」「重新整理後消失」類行為只能讀碼推論）；`data_cache/` 與 `/tmp/st_cache/` 的部署環境內容不可見 |
| 已實跑測試 | `tests/test_p04_hold_view.py` ＋ `tests/test_p04_hold_v2_cards.py`＝1435 passed, 1 deselected（2026-10-26，基準 main `96206a96`；子 agent 於沙箱安裝 requirements.txt＋pytest 後執行；FinMind 套件未安裝僅警告）；總管另跑 `tests/test_ia_v2_sidebar_nav.py` ＋ `tests/test_c3_layering_guard.py`＝41 passed, 5 deselected（2026-10-26；子 agent 與總管各自在沙箱實跑，QA 未重現） |
| 標記慣例 | **FACT**＝讀碼／實跑可重現，附 `file::symbol`；**INFERENCE**＝由程式推得但未實跑／未實機；**MISSING**＝現有程式碼無此欄位／函式；**未確認**＝沒追到；**需新來源**＝資料不在現有任何來源。行號一律不寫（會漂移）；會漂移的量測值標日期（2026-10-26） |
| 路徑簡寫 | `DSS`＝`src/services/dividend_station_service.py`；`station_cards`／`station_charts`＝`src/ui/render/` 下同名 L4 模組（以 repo 實際路徑為準，本報告未逐一重驗路徑前綴者標「單組」） |

## 1. 總表（Stage B 草稿 INFERENCE 項 × 現況）

狀態圖例：✅ FACT 已驗｜🟡 部分成立／有落差｜⬜ MISSING｜🔶 需新來源｜❓ 未確認。

| # | Stage B 草稿的宣稱／INFERENCE | D0 狀態 | 證據（file::symbol） | 詳見 |
|---|---|---|---|---|
| 1 | G6 逐檔表 9 欄位都已在既有 rows | 🟡 7 欄 FACT；市值單位為「張·元」；健檢「等第」不存在字母等第；235 燈僅 ETF | `DSS::get_station_rows`、`row_from_assessment`、`stock_row_from_assessment`、`_error_row`、`build_station_rows` | 2 |
| 2 | G6 展開＝逐盞燈明細＋週線／布林 z 兩圖 | 🟡 只對 ETF 成立；個股／失敗列為空 Series＋miss_reason | `DSS::KEY_WEEKLY_SERIES`、`station_charts::render_weekly_ma_chart`／`render_boll_z_chart` | 2.4 |
| 3 | G6 資料日（as_of／stale） | ⬜ MISSING | `DSS::get_station_rows` 只回 `(rows, vix)`；`page_hold::StationReadout` 無此欄 | 2.5 |
| 4 | 手機燈牆互動 | 🟡 hover 僅 `title=`；無點擊展開；原檔刻意不做就地展開＝新互動元件 | `station_cards::render_light_wall`、`page_hold::_render_light_wall` docstring | 2.6 |
| 5 | G6 須擴充唯讀守衛白名單 | ✅ 白名單 26 項；`KEY_WEEKLY_SERIES` 不在其中 | `tests/test_p04_hold_view.py::_ALLOWED_L3` | 2.7 |
| 6 | G3 三數＝同一 `build_station_digest` | 🟡 兩數來自 digest／rows，第三數「未判」不是 digest 鍵 | `DSS::build_station_digest`、`page_hold::load_station`、`build_todo_card`、`station_cards::is_fully_judged` | 3.1 |
| 7 | G3「訊號可信度 N/M」 | ✅ 可算，但來源是 L4 對 rows 的 `_lights` 計算，不在 digest | `station_cards::aggregate_judged`／`tally_states`／`cruise_or_gap`、`StationReadout.judged/total_lights` | 3.2 |
| 8 | G3 digest 能跨頁取用 | ⬜ 不可；不存 session，檔頭明寫禁止且有測試守衛 | `page_hold` 檔頭；`SS_APPLIED_HOLD`＝`_p04_applied_hold`；`_ui_kit::single_submit_form` | 3.4 |
| 9 | G3 重複外連／延遲 | ❓ VIX 與 ETF 日線有快取；個股路徑未追到；實測延遲 MISSING | `macro_core::fetch_yf_close`、`etf_fetch`（`@st.cache_data`，`TTL_1HOUR`） | 3.5 |
| 10 | G4 全站一行狀態可由 L3 彙總呼叫 | ⬜ 現無此函式（QA-2 風險 5 結論） | `shared/fetch_monitor::get_monitor_registry`、`data_registry_summary_service::summarize_data_registry`、`page_why::_render_user_health_wall` | 4 |
| 11 | G4 四屬性（fetched_at／as_of／來源身分／影響功能） | 🟡 各只部分成立 | 同上＋`src/data/core/data_registry::DATA_REGISTRY`、`shared/input_provenance_policy` | 4.2 |
| 12 | G4「重新檢查」只重讀紀錄不外連 | 🟡 兩讀取面純讀＝FACT；`get_monitor_registry` 回傳 shallow copy（FACT） | 同上 | 4.3 |
| 13 | G1 導覽殼七頁與 `ia_nav` 一致 | ✅ 7 鍵與順序一致；1 處與草稿不一致（E7）、另有 3 項 repo 現況觀察（5.2） | `ia_nav::PAGE_LABELS`、`LEAF_*` | 5 |
| 14 | G5 可點跳轉機制 | ❓ 技術可行性未證（程式於 rerun 寫 nav radio key） | `app.py::_IA_NAV_KEY` | 5.4 |
| 15 | G2 候選預填／外部頁預填 | ⬜ 無現成入口 | `page_inspect::SS_APPLIED_TICKER` 等 | 5.5 |
| 16 | D-24 名稱→代號搜尋 | ⬜ 無 name→code 函式；市場別／權威類型欄位需新來源 | `stock_names::get_stock_name`（僅 code→name） | 6.1 |
| 17 | D5 帶入我的持股 | ✅ 讀取面存在；輸入框帶入 MISSING | `holdings_service::get_holdings` | 6.2 |
| 18 | D-25 scoped 重抓 | 🟡 僅 Google Sheet 讀取有 scoped 失效；個股資料無 | `portfolio_binding_service::reload_my_sheet_reads` | 6.3 |
| 19 | D-20 熱力圖切換＋排行表 | 🟡 L3 支援切換；排行表在舊 L4，新頁無欄位 | `sector_heatmap_service::get_sector_heatmap_view`、`etf_render::render_sector_heatmap` | 6.4 |
| 20 | D-21「as_of（INFERENCE：L3 note 含）」 | ❌ 不成立（更正，見 8） | `fundamental_screener_service`、`fundamentals_snapshot_loader` | 6.5 |

## 2. G6 逐檔表（🛡️ 逐檔戰情表＋展開明細）

### 2.1 rows 的形狀（FACT，單組讀碼）

- `DSS::get_station_rows` 回傳 `(rows, vix)`，**沒有** as_of／stale／日期欄。
- 每列為下列三型之一：ETF 成功列（`row_from_assessment`）、個股成功列（`stock_row_from_assessment`）、抓取失敗列（`_error_row`）；`build_station_rows` 再追加 `_weekly_series`、`held`、市值、損益%、張數、均價、現價（總管已驗：存在，缺值為 `None`，不是 0）。
- 失敗列**沒有**張數／均價／現價鍵（是「無此鍵」，不是 `None`）。**消費端必須 `.get` 並先判 `_detail.error`。**

### 2.2 九欄位判定

| 欄位 | 判定 | 說明 |
|---|---|---|
| 代號 | ✅ FACT | 每型皆有 |
| 名稱 | ✅ FACT | 可能為空字串（holdings 預設 `""`） |
| 張數／均價／現價 | ✅ FACT（成功列） | 缺值 `None`；失敗列無此鍵 |
| 損益% | ✅ FACT | 已算好，單位為百分點；缺值 `None` |
| 市值 | 🟡 FACT 但單位為「張·元」 | `compute_portfolio_totals` docstring 明寫；換元需 ×`SHARES_PER_LOT`；`page_hold.py` 有「本頁不自行再算」（持股水位）與「刻意不重算」（核心／衛星）等同精神註解；字串「本檔不自算」逐字 0 命中。現有 rows 的市值欄位單位為「張·元」；若要以元顯示，需另行換算（設計選擇，不在本報告決定） |
| 健檢等第 | 🟡 與草稿措辭有落差 | row 只有 🔴🟡🟢⚪ 圖示（ETF＝四盞取最嚴重；個股＝`swap_level`）；**不存在字母等第**。個股另有「財報體檢」字串 `mj_grade`（score） |
| 235 燈狀態 | 🟡 僅 ETF | ETF 有「235 燈號」字串與 `_lights` 內 `KEY_LIGHT235`；個股列無此鍵＝**不適用**；失敗列為「—」 |

### 2.3 `_lights`／`_detail` 契約（FACT，單組）

- `_lights`：`tuple[LightCell]`（`src/compute/etf/dividend_station.py`，frozen；欄位 key／level／state／miss_reason／axes_used）。ETF 8 盞；個股 4 盞（僅「汰換建議」有等級）；失敗列用 `missing_light_cells`。
- `_detail`：`dict[str,str]`。ETF 鍵：健檢 A–D／235 觸發／深水防守／3-3-3 明細（／ETF 品質）；個股鍵：財報總評／財報弱項／財報趨勢／KD 明細／KD 交叉；失敗列 `{"error": …}`。**`_detail` 不以燈 key 索引，須 L5 對照。**
- `station_cards::render_holding_detail` 已能逐燈顯示。

### 2.4 週線／布林 z（FACT／INFERENCE）

- `_weekly_series`（`DSS::KEY_WEEKLY_SERIES`）每列必有；payload：`n_weeks`／`close`／`ma{4,13,52}`／`ma_miss`／`boll_z`／`boll_z_miss`／`boll_period_weeks`／`miss_reason`。**零新增取數。**
- 個股與失敗列：空 Series＋`miss_reason`（`MISS_NOT_APPLICABLE`／`MISS_FETCH_FAILED`）→ G6「展開兩圖」**只對 ETF 成立**；個股列目前為空 Series＋`miss_reason`。
- 既有 L4：`station_charts::render_weekly_ma_chart`／`render_boll_z_chart`。
- 日線 period＝5y，約 260 週：**INFERENCE**（由程式推得，未實跑）。

### 2.5 資料日（as_of／stale）

⬜ MISSING。`StationReadout` 無此欄；現價資料日未帶出。現有 rows 無資料日欄；若要顯示，需在 `fetch_metrics` 新增帶出 `_close.index[-1]` 的 L3 欄位（非新取數；範圍擴大，依草稿規則須回報）。

### 2.6 燈牆互動（讀碼事實，未實機驗）

- `render_light_wall`：hover 僅 `title=`（手機無 hover）；名稱 ellipsis；燈條 nowrap；無點擊展開。
- `page_hold::_render_light_wall` docstring 明寫「刻意不做就地展開」（互動元件屬草稿先行）→ 手機點擊展開＝新互動元件。
- `src/ui_v2/page_hold.py`：v2 版面契約純結構層（約 115 行，無 streamlit、無 render），與逐檔表／燈牆互動無關（QA 讀碼）。

### 2.7 唯讀守衛

- `tests/test_p04_hold_view.py::_ALLOWED_L3`＝**26 項**（2026-10-26，總管以 AST 實數；子 agent 曾回報 25 與 29，皆不採用）。`KEY_WEEKLY_SERIES` 不在其中。
- `page_hold` 若 import 新 L3 符號：須同步擴充白名單與 `page_hold` 檔頭取數接線表。`src.ui.*` 的 import（如 `station_charts`）不在掃描範圍。
- 其他檢查：`_WRITE_SURFACE`、禁 import `src.data`、禁 import `app`、禁底線私有符號、禁 cache 裝飾器與 ttl、禁 I/O 函式庫。
- `_DOWNSTREAM` 毒藥模組清單：新增 L3 服務模組時應同步（依註解推得，**INFERENCE**）。

## 3. G3 ⚡

### 3.1 digest 口徑

- `DSS::build_station_digest(rows, vix=None)` 純函式。鍵：`total`、`vix`、`reds`、`held_reds`、`adds`、`watch_adds`、`errors`、`allocation`、`take_profit`，異常時才有 `invalid`。
- `reds`＝持有＋觀察清單；`held_reds`、`adds` 只持有。`page_hold::load_station` 的 `cut_n`＝`len(digest["reds"])`。
- `build_todo_card` 三數＝「加碼 N · 汰弱 N · 未判 N」，其中**第三數「未判」不是 digest 鍵**，來自 `station.unjudged_rows`（L4 `is_fully_judged` 重算）。→ 草稿「三數＝同一 digest」**僅部分成立**。

### 3.2 訊號可信度 N/M

不在 digest；由 L4 `station_cards::aggregate_judged`／`is_fully_judged`／`tally_states`／`cruise_or_gap` 從 rows 的 `_lights` 計算，存於 `StationReadout.judged`／`total_lights`；卡片 `build_confidence_card`。

### 3.3 「未判≠沒事」現有落點（FACT）

`digest.errors`／`invalid`；`build_summary_prompt` 異常時不送續抱句；`build_todo_card` 與 `build_confidence_card` 文案；L4 `cruise_or_gap`。

### 3.4 跨頁性

digest 不跨頁、不存 session（`page_hold` 檔頭明寫禁止，測試守衛）；`load_station` 每次 rerun 重算；gate `SS_APPLIED_HOLD`＝`_p04_applied_hold`，唯一寫入點 `src/ui/views/_ui_kit.py::single_submit_form`。→ ⚡ 要數字，只能**自帶 gate 再呼叫同組 L3**。

### 3.5 重複外連

- VIX：`macro_core.fetch_yf_close`，module dict 快取 TTL 3600s＋失敗退避。ETF 日線：`etf_fetch`，`@st.cache_data` `ttl=TTL_1HOUR` `max_entries=20`。
- 個股路徑（`StockDataLoader`／`fetch_financial_statements`）與配息快取的對應：**未追到＝未確認**。`get_station_rows` 本身無快取。
- 實測延遲／重複外連：**MISSING**（沙箱不能連外）。

## 4. G4 🩺

### 4.1 QA-2 風險 5 結論

**現無可被「全站一行狀態」直接呼叫的 L3 彙總函式。** 現有兩條來源，皆不涵蓋全站：

| 來源 | 層 | 涵蓋 | 限制 |
|---|---|---|---|
| `shared/fetch_monitor::get_monitor_registry` | L0，純 in-process dict，零 I/O | 僅 `@monitored` 的 9 支 fetcher（總管已驗：`src` 內 `@monitored` 計 9（2026-10-26）；`page_why.MONITORED_FETCHER_COUNT`＝9；`COVERAGE_DISCLOSURE` 明講不代表全站） | 不是全站 |
| `data_registry_summary_service::summarize_data_registry(session)` | L3 | 讀 `session_state['data_registry']`，需先按「🚀 更新今日戰情」才有 | 明寫不判新鮮度燈號 |

`page_why` 的彙總在 L5 私有 `_render_user_health_wall`，無回傳值。組卡函式：`load_sources`／`probe_from_entry`／`build_source_card`／`load_registry`／`build_registry_card` 等。

### 4.2 四屬性

| 屬性 | 現況 |
|---|---|
| fetched_at | 僅 9 支 `@monitored` 有（`last_called_at`）；registry 側 ⬜ MISSING |
| as_of | registry 的 `last_updated` 語意混合（資料日或抓取日代理，官方明講不蓋燈號）；monitor 側 ⬜ MISSING |
| 來源身分 | `DATA_REGISTRY`（`src/data/core/data_registry.py`）有 source／endpoint／identifier／requires_key；通用 `Provenance`（`shared/input_provenance_policy`，五值）只用在總經輸入；「資料項目→Provenance」通用對應 ⬜ MISSING |
| 影響功能 | 只有自由文字 `usage`／`state_key`；結構化欄位 ⬜ MISSING |
| FinMind 額度 | ⬜ MISSING（`UNMEASURED_SOURCES`，`wired=False`） |

### 4.3 其他 FACT

- `FreshnessStatus` 四值：fresh／stale／missing／undetermined。`UI_STATE_META` 十項：idle／loading／failed／empty／missing_retryable／not_applicable／partial／degraded／unwired／live。
- 「重新檢查」只重讀紀錄、不清快取、不外連：兩條讀取面皆純讀（FACT）；`get_monitor_registry` 回傳 shallow copy（`{k: dict(v) for k,v in _MONITOR_REGISTRY.items()}`；QA 讀碼確認，FACT）。

## 5. 導覽殼／動態引用（D1／D2／D9／D10）

### 5.1 `ia_nav`

- `ia_nav.PAGE_LABELS` 7 鍵與順序與草稿 B0.4 一致：market 📊 大盤、today 🚦 今天、find 🔍 找標的、inspect 🔬 查一檔、hold 💼 我的持股、why 📖 憑什麼、me 👤 我的。
- 總管已驗：`page_link`／`switch_page` 在 `src`、`app.py`、`shared` 皆 0 命中。
- `where_to_find`／`where_to_press`／`page_label` 對未知鍵 raise `ValueError`（實跑），**只驗鍵存在於 `SECTION_LABELS`，不驗葉在 view 內真的存在**。

### 5.2 與草稿不一致處

1. （與草稿不一致，見 E7）`ia_nav.LEAF_*` 只有 today 兩個；其他葉常數在各 view（如 `page_find.LEAF_SCREEN_TITLE`）。find／inspect 的葉在 `ia_nav` 無 id，`where_to_find` 目前指不到。

**repo 現況觀察（非草稿內容，不列入 errata）**：

- `page_hold.LEAF_SETUP_TITLE`＝「組合設定（＝組合管理＋Sheet 綁定）」，與 `SECTION_LABELS`「組合設定」字面不同。
- 舊 UI 導覽字面（「不使用」「🆕 新版戰情室（試用中）」）在 `app.py`、`page_me`、`page_market` 三處各手抄（新發現）。`SWITCH_BACK_TEXT` 在 `page_me.py`（草稿 B7 已寫對）。
- 各 view 檔頭「IA v2 第 N 頁」編號與現行 7 頁順序不同（僅文字）。

### 5.3 `app.py` 與殼敏感測試

- `app.py`：`_IA_NAV_KEY`＝`'_sb_ia_page'`、`_IA_NAV_OFF`、radio `index=0`、`_IA_VIEWS` 7 個 late-import wrapper＋set 對帳 raise `RuntimeError`、分派後 `st.stop()`。
- `tests/test_ia_v2_sidebar_nav.py` 對殼敏感：`_sb_ia_page` 字串只准出現在 `app.py`（位置須恰為 `[("app.py",1)]`）；逐字斷言 `_IA_NAV_OPTIONS = (_IA_NAV_OFF, *_IA_PAGE_LABELS.values())`；`app.py` 不得手抄任何頁名；`_IA_VIEWS[` 只准 1 次；`st.tabs` 恰 7 個；`_VIEW_MODULES` 寫死 7 個 view（新 view 不在其中則毒藥守衛不涵蓋）。→ **D2 須同步擴充並獨立 QA。** 實跑 41 passed（含 c3 layering）。

### 5.4 G5 跳轉機制

程式於 rerun 中寫入 nav radio key 的可行性＝**未確認**（repo 無此用法，僅測試端預寫；Streamlit 限制未實證）。→ D9 前置未決技術項。

### 5.5 預填與 session 鍵

`SS_APPLIED_TICKER`＝`_p03_applied_ticker`（`page_inspect`）、`SS_APPLIED_SCREEN`＝`_p02_applied_screen`（`page_find`）、`SS_APPLIED_HOLD`（`page_hold`）、另 `SS_APPLIED_BATCH`；皆於各頁 form submit 寫入；形狀是 widget 當下值（如 `{ticker, period_days, mas, kind_choice}`），不是單一代號欄；外部頁預填目前無現成入口。

### 5.6 選定與登入逾期

`shared/sheet_id.py`：`ACTIVE_PORTFOLIO_SESSION_KEY`＝`_me_active_portfolio`、`ACTIVE_WATCHLIST_SESSION_KEY`＝`_me_active_watchlist`，值 `{sheet_id,name,skip}`，僅 session（程式註解＋DEC-083＋BACKLOG `NAV-PERSIST`）。「重新整理後確實消失」未實機驗＝INFERENCE。`LOGIN_EXPIRED_WHERE` 見 `page_hold`（與 `NAV-PERSIST` 衝突，矩陣已登記）。

### 5.7 手抄頁名（D10 工作量依據）

約 20 處使用者可見字串（口徑不可重建，僅供量級參考；QA 以較寬鬆 regex 重數得更多）：`page_hold`（約 7 處）、`page_why`（約 7 處）、`page_market`（約 5 處）、`page_me`（約 4 行）。`ia_nav` 引用 105 行（口徑：`src/ui/views`）；`where_to_find`／`where_to_press`／`page_label(` 呼叫約 55～57 處（2026-10-26，grep `where_to_find|where_to_press|page_label(`；`src/ui/views` 內 55，含 `shared`、`app.py` 為 57）。

### 5.8 其他

各 view render 函式 7 支都在；docstring 與行為是否逐項一致**未逐項驗**。

## 6. 🎯 輸入面與 D5

### 6.1 D-24 名稱／代號搜尋

- 全 repo `*.py` **無 name→code 函式**（只有 code→name：`stock_names.get_stock_name`、`stock_names_fetcher._build_dynamic_name_cache`〔TWSE `STOCK_DAY_AVG_ALL`／`t187ap03_L`＋TPEx＋約 62 筆靜態〕、`yield_pe_fetcher.fetch_pe_name_maps` 等）。**未掃 json／csv／parquet。**
- 名稱快取 `/tmp/st_cache/tw_stock_names_v1.pkl`，TTL 24h；本環境不存在，無法驗筆數；網路失敗只剩約 62 筆靜態（2026-10-26）。
- 個股／ETF 僅靠 `shared/dividend_station_thresholds.classify_asset_kind` 代號規則（docstring 自稱啟發式非權威）。
- 🔶 市場別／權威類型欄位＝**需新來源**（例如清單類別欄）；同名／ETF 簡稱可否區分＝**未確認**（名單內容未驗）。
- 名稱→候選比對函式：現無（＝新邏輯）；現有 code→name 對照表的資料覆蓋度未驗。

### 6.2 D5 帶入持股

`holdings_service.get_holdings(keep_blank=False, resolve_names=True)`→`HoldingsResult`，`.held_tickers`／`.holdings`（欄 ticker／name／held／asset_kind／asset_class／lots／avg_price）；純讀、依 👤 選定、未選定回空且有 `SELECTION_*` 狀態、讀取失敗 raise。`page_find` 持股標示路徑升格為 FACT：`load_sector_flow`→`sector_flow_service.get_sector_flow_view(use_active_selection=True)`→`_active_selection_tickers`→`get_holdings(resolve_names=False)`。`page_find`／`page_inspect` 無直接帶入輸入框的程式（⬜ MISSING）。

### 6.3 D-9／D-25 scoped 重抓

- `portfolio_binding_service.reload_my_sheet_reads` 只換「本人×指定 Sheet」快取世代（不 `.clear()`）；唯一 production caller 為 `me_account_service`（總管已驗；`tests/` 另有 5 處呼叫）；僅涵蓋 Google Sheet 讀取；個股資料（財報／日線／新聞）無 scoped 失效函式（⬜ MISSING）。
- 「原樣強制重抓」（`st.cache_data.clear()`＋pop 四個 session 鍵）在**舊 UI** `src/ui/tabs/tab_stock.py` 與 `tabs/macro/handlers.py`；新 UI `page_find`／`page_inspect` **目前沒有**重抓入口。
- `fundamental_screener_service.get_fundamental_prescreen` 與 `get_sector_heatmap_view` 各有 `refresh` 參數，`page_find` 未傳。

### 6.4 D-20 熱力圖

`get_sector_heatmap_view(is_us, period_label, *, refresh=False)`；period 值域 `SECTOR_PERIOD_LABELS`＝1日／5日／1月／3月（1／5／21／63 交易日），非法值 raise；`page_find` 固定 `HEATMAP_IS_US=False`、`'1日'`，無選擇器；排行表在舊 L4 `etf_render.render_sector_heatmap`（內部取數＋畫圖，直接搬會形成兩條取數路徑）；新頁 `HeatmapReadout` 無排行資料欄位。

### 6.5 D-21 初篩涵蓋率

- 草稿「as_of（INFERENCE：L3 note 含）」**不成立**：`fundamental_screener_service`／`fundamental_prescreen`／`fundamentals_snapshot_loader` 的 `as_of` grep 為 0（總管已驗）。實際欄位為 meta 的 `roc_year`／`season`／`prev_roc_year`／`updated_at`。
- `data_cache/fundamentals/latest.json` 另有 `coverage{sii 1083, otc 891, total 1974, prev_total 1968}`（總管已驗為本機 repo 檔，**不代表部署環境**；量測日 2026-10-26）。
- `page_find._load_survivors` 丟棄 meta（含 coverage）。
- `get_ranked_picks` 的 note 是字串，含未掃描因子、因子覆蓋 k/N、涵蓋未過半排除檔數、空頭濾網說明，**不含 as_of／全市場涵蓋率**。
- 「涵蓋率」口徑為新定義，不在本輪定義。

### 6.6 其餘 D-n 現況核對

| D-n | 現況 |
|---|---|
| D-18 | `page_inspect` 6 個 MA checkbox 只回顯於 facts，頁面自揭露「沒有東西會用到（K 線未接線）」，旁無「尚未生效」圖示 |
| D-12 | 標題為 `ia_nav.page_label(PAGE_HOLD)`＋副句「我已經持有的，該加、該換、該減。」；「我的投資組合健康嗎？」0 命中；改標題牽動 `ia_nav` 與測試 |
| D-14 | `page_hold.DEEP_SPECS` 兩張未接線卡，葡萄串卡無舊 UI 步驟（dead-end 半成立） |
| D-19 | `BATCH_MAX_TICKERS`＝20，超過截斷並揭露；「型別篩選只影響顯示」未逐行驗 |
| D-22 | 七段明細有半 dead-end 指路（`DETAIL_WHERE`，無「側欄選不使用」步驟）；新聞／集保大戶／費用率·Beta·AUM／PROXY 缺席原因的現況未逐條核對＝未確認 |
| D-36 | ⚡ 引用端未建；`page_hold` 再平衡／葡萄串卡的指路句寫死，未用 `where_to_find` |
| D-40 | `page_market` 已有 `OLD_UI_POINTER`（測試對帳 `test_old_ui_pointer_strings_exist_in_app`），六項已有指路；羅盤／總經 v2 密度／籌碼雷達清快取／櫃買確實 0 命中＝靜默缺席；`OLD_UI_POINTER` 為頁內重複字串，非 `ia_nav` 組出（SSOT 放哪＝設計事項，不在本輪） |
| D-13 | 卡名／區塊名現為「AI 戰情總結（唯一推播出口）」，`AI_DISCLOSURE` 無「排程推播讀部署設定」揭露；`scripts/push_holdings_daily.py` 讀環境變數 `PORTFOLIO_SHEET_ID`／`STOCK_PORTFOLIO_SHEET_ID`（與頁面選定無關）→ 草稿 D-13 事實成立 |
| D-8 | L1 `gsheet_portfolio.classify_read_error` 429→`quota_exceeded`，L3 `portfolio_binding_service.sheet_read_issue`；👤 `page_me` 已用 `ISSUE_TEXT_QUOTA`；`page_hold` 僅處理 `schema_mismatch`，429 走通用 `_error_why`（非白話）；Gemini 429 是另一條線（`ai_qa_service`／`app_ai_service`） |

## 7. 未排程 D-n（`NEWUI-STAGE-D-UNSCHEDULED`）

D-12、D-14、D-19、D-22、D-36、D-40 現況見 6.6。**本報告只提供事實，不為其歸批**（歸批屬 `NEWUI-STAGE-D-UNSCHEDULED` 後續排程）。

## 8. 對 Stage B 草稿的更正清單（errata；只列不改草稿）

| # | 草稿位置 | 草稿說法 | D0 實證 | 嚴重度 |
|---|---|---|---|---|
| E1 | B4.3 K2 | `as_of`（INFERENCE：L3 note 含） | 不成立；0 命中；實際欄位 `roc_year`／`season`／`prev_roc_year`／`updated_at`＋`latest.json` 的 `coverage` | 高（影響 D5 範圍） |
| E2 | B3.2／B3.3／G6／B3.5 | 欄位含「健檢等第」 | 不存在字母等第；row 只有 🔴🟡🟢⚪ 圖示，個股另有 `mj_grade` 字串 | 中（措辭／欄位定義） |
| E3 | G6（B3.7／I5 已標 INFERENCE） | 欄位含「市值」 | 補充：單位是「張·元」，換元需 ×`SHARES_PER_LOT` | 低（補充） |
| E4 | G6／B3.2 | 「235 燈狀態」每列 | 僅 ETF 有；個股列無此鍵＝不適用 | 中 |
| E5 | G6（B3.7／I5 已標 INFERENCE） | 展開＝週線／布林 z 兩圖 | INFERENCE 已驗證：個股與失敗列為空 Series，只對 ETF 成立 | 中 |
| E6 | G3 | 三數＝同一 `build_station_digest` | 第三數「未判」來自 L4 重算，不是 digest 鍵 | 中 |
| E7 | B7／D-7 | 指路句統一由 `ia_nav` 組出 | `ia_nav.LEAF_*` 只有 today；find／inspect 的葉無 id | 中 |
| E10 | B3.3 表 | 「as_of＝價格序列末日」；「現價日期過舊→該列標 🕒」 | 兩處宣稱被推翻：資料日（as_of／stale）不在 rows，也不在 `StationReadout`（`get_station_rows` 只回 `(rows, vix)`） | 中 |

> 草稿 B10 的修正紀錄為歷史保留；本節不回頭改草稿，後續若修草稿須另走正規流程。編號 E8、E9 已於 QA 後移出 errata（見 10.4），保留編號不重排。

## 9. 對各 Stage D 批的影響（只描述前置條件／範圍擴大風險；不做設計、不改投資語意）

| 批 | 影響 |
|---|---|
| D1 導覽殼線框 | 線框須涵蓋 `LEAF_*` 目前分散的事實（5.2-1）；需客戶核准後才可寫殼 UI code |
| D2 殼實作 | `tests/test_ia_v2_sidebar_nav.py` 多處逐字／計數斷言（5.3）須同步擴充並獨立 QA；`_VIEW_MODULES` 寫死 7 個，新 view 不在毒藥守衛內；導覽字面三處手抄 |
| D3 逐檔表 | 欄位以 2.2 為準；「健檢等第」現有語彙為圖示與 `mj_grade` 字串（無字母等第）；市值單位；個股／失敗列的缺值顯示；資料日需新增 L3 欄位（範圍擴大，依草稿規則須回報）；須擴充 `_ALLOWED_L3` 與檔頭接線表；燈牆手機展開＝新互動元件 |
| D4 資料狀態列 | scoped 重讀只涵蓋 Google Sheet；429 目前走通用 `_error_why`；`SWITCH`／導覽字面手抄；觸及 `page_hold` 須同步 `test_p04_hold_view.py` |
| D5 輸入面 | 名稱→代號為新邏輯（覆蓋度未驗；市場別需新來源）；scoped 重抓只有 Sheet 讀取，個股資料無對應函式（範圍擴大風險）；D-20 排行表搬入會形成兩條取數路徑；D-21 的 as_of 不存在、coverage 在 `latest.json`（口徑待定義）；D-18 回顯無生效 |
| D6 找＋查同頁 | 依賴 D2；session 鍵形狀為 widget 當下值，預填無現成入口 |
| D7 ⚡ | digest 不能跨頁，需自帶 gate；「未判」第三數須自 L4 重算；重複外連未量測 |
| D8 資料中心 | 一行狀態無現成 L3 彙總（4.1）；四屬性多為 MISSING |
| D9 跨頁跳轉 | rerun 中寫 nav key 的可行性未證（5.4）；預填入口不存在 |
| D10 共用元件 | 手抄頁名約 20 處（非窮盡）；`where_to_find` 不驗葉存在 |
| D11 對等驗收 | 本報告的 FACT 不等於對等驗收；沿用 Coverage 四狀態 |

## 10. 揭露

### 10.1 總管已驗（本報告中標「總管已驗」者）

欄位存在與 `None` 缺值（`DSS` 市值／損益%／張數等）、`_ALLOWED_L3` 實為 26（2026-10-26）、`as_of` 在三個 fundamentals 模組 0 命中、`page_link`／`switch_page` 0 命中、`latest.json` 的 `coverage`、`reload_my_sheet_reads` 單一 caller（`me_account_service`）、`@monitored` 計 9（2026-10-26）、41 tests passed（2026-10-26）、`compute_portfolio_totals` 單位註解存在。

### 10.2 未經第二組複驗（單組產出，待獨立 QA）

**除 10.1 外，本報告全部內容皆為單組子 agent 產出，未經第二組獨立複驗，亦非總管逐項複驗。** 其中全稱類語句尤須打折：「現無可被呼叫的 L3 彙總函式」（4.1）、「全 repo 無 name→code 函式」（6.1，**未掃 json／csv／parquet**）、「新 UI 目前沒有重抓入口」（6.3）、「約 20 處手抄」（5.7，regex 非窮盡）、「各 view 7 支 render 函式都在」（5.8）、3.3 各落點（`build_summary_prompt` 等）未逐項驗。這些只能當待驗事項，不得作為後續施工前提。

### 10.3 驗不到而維持 MISSING／未確認

- 資料日（as_of／stale）；實測延遲／重複外連；個股路徑與配息快取的快取對應；程式於 rerun 寫 nav radio key；`/tmp/st_cache/tw_stock_names_v1.pkl` 筆數；同名／ETF 簡稱可否區分；D-19 型別篩選、D-22 缺席原因逐條現況；導覽殼各 view docstring 與行為是否逐項一致。
- 沙箱未實機操作：燈牆手機行為、「重新整理後選定消失」皆為讀碼推論（INFERENCE）。
- `data_cache/fundamentals/latest.json` 為本機 repo 檔，不代表部署環境。

### 10.4 QA 後修正歷程

兩組獨立 QA 後已套用：E8（`LEAF_SETUP_TITLE`）、E9（檔頭「第 N 頁」）移出 errata——草稿並未宣稱這兩點，改列 5.2「repo 現況觀察」；E6 刪除「可信度亦不在 digest」（草稿 B5 已寫來自 L4）；E7 縮為只剩 `ia_nav.LEAF_*`；E10 改引草稿原文；E3、E5 改為補充／INFERENCE 已驗證；第 2.2 節「本檔不自算」引文更正；`get_monitor_registry` 升級為 FACT；熱力圖服務模組名、rows 型數更正。

### 10.5 邊界

本報告未新增任何投資語意、未改任何 code／測試／threshold／資料來源，亦未把任何 INFERENCE 升格為 FACT；不授權施工。Stage D 各批仍須各自先過 DEC-084 Model×Effort Check、獨立 QA，舊 UI Removal Gate 不變、不刪舊 UI。
