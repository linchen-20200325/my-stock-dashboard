# DEAD_CODE.md — 死碼登記簿（全 repo 唯一入口）

> **客戶 2026-09-21 裁示**：遇到死碼**先查本檔** —— 有登記就引用編號，沒登記就**先登記再處理**。
> **本輪只盤點、不修**：登記**不等於**動工授權（§-1「沒實際 bug／沒具體需求 → 不要動」仍是閘門）。
> ⚠️ **本檔不是全 repo 死碼的窮舉** —— 它是四組獨立調查 + 總管複驗的**已查證項目**彙整。
> ⛔ **不得**被引用為「repo 裡只有這些死碼」；**未登記 ≠ 不存在**。

## 判定準則（客戶定義，逐字照用）

| 型 | 定義 |
|---|---|
| **A** | production 0 caller（grep 全 repo，排除 `tests/`、docstring、註解） |
| **B** | 條件恆為 False（數學上或型別上可證明） |
| **C** | 早退分支永遠到不了（前面有無條件 return） |
| **D** | 參數從未被傳入（簽章有、呼叫端 0 處） |

⛔ **不符合任一型就不算**：「看起來沒用」不算、「好像過期了」不算、
**「註解說它死了」不算 —— 要自己驗**（活教材見 D-010）。

**狀態欄四種**：`確認`（驗過成立）／`疑似`（可能是但掃不到，例如動態組字串）／
`已推翻`（曾判死碼、後來發現是活碼）／`已修`（後續版本已處理）。
**第五種（2026-09-21 補）**：`待修（非死碼）` —— 查證途中挖出、**不符合 A／B／C／D 任一型**（所以不是死碼），
但屬**真實缺陷**，且客戶裁示「登記，不修」者。⛔ 不得標成 `確認` —— 那一欄的語意是「**確認為死碼**」，
把非死碼標進去會讓本檔的死碼清單失真。首例：**D-013**。

---

## ① 假死碼區（客戶指定優先 —— 因為它們會誤導）

| 編號 | 位置 | 類型 | 證據 | 狀態 |
|---|---|---|---|---|
| **D-001** | `src/compute/risk/risk_radar.py::synthesize_dual_verdict` — 參數 `valuation_level` | **A＋D** | 全 repo 唯一 production 呼叫端 `src/ui/tabs/macro/helpers.py:230` 只傳 6 個參數（`slow_level`／`slow_score`／`slow_color`／`slow_icon`／`slow_action`／`radar_level`），**不含本參數**；其餘呼叫全在 `tests/`。production 恆為 `None` ⇒ `_apply_third_axis_overlay` 內 `== "極貴"` / `== "便宜"` 兩分支恆 False。無 `**kwargs`／dict-unpack／動態餵值。 | **確認** |
| **D-002** | 同函式 — 參數 `event_calendar_level` | **A＋D** | 同 D-001：該 production 呼叫端亦未傳此參數。 | **確認** |
| **D-003** | `src/services/financial_health_engine.py::no_ai_overall_verdict` — `else 50`（約 L1110） | **C** | `score_pct = round(total_pts/max_pts*100) if max_pts>0 else 50`，而 `max_pts = len(valid)*2` ⇒ `max_pts==0` 與 `not valid` 是**同一條件**。唯一輸出 `score_pct` 的 return 在 L1227；但 L1165 `if not valid: return {..., "score_pct": None, ...}` 是**無條件早退**且寫在它前面 ⇒ 50 算得出來，**永遠離不開這個函式**。實測：讓 11 項 checks 全落 N/A 後呼叫，回傳 `score_pct=None`，不是 50。 | **確認** |
| **D-004** | `src/data/macro/macro_snapshot.py::compute_twii_bias` — `bias_240 or 0` | —（原指 B） | 見下方「D-004 推翻說明」。 | **已推翻** |
| **D-013** | `src/data/macro/macro_snapshot.py::compute_twii_bias` — `calc_bias_pct(...) or 0`（**實測 4 處**：`:350`／`:354`／`:355`／`:356`） | **—（非死碼：缺值處理缺口）** | `NaN <= 0` 恆 False ⇒ guard 攔不住；`bool(nan) is True` ⇒ `nan or 0` 得 **`nan` 不是 `0`**，NaN 靜默流向下游。詳見下方「D-013 說明」。 | **待修（非死碼）** |

🔴 **D-001／D-002 必讀 —— 這不是普通死碼，是一顆裝好只差引信的合規地雷。**
那兩個走不到的分支裡裝的是**直接買賣建議文案**。以下為**原始碼既有字串的原文引用，僅作合規舉證，
不是本檔的任何建議**：
- **D-001** 死分支：「估值頂部分位（極貴），建議減倉至中性」／「估值底部分位（便宜），可逐步擇機加碼」
- **D-002** 死分支：「重大事件臨近，暫緩單筆加碼」／「事件曆逆風，留意波動放大」／「事件曆順風，可酌量擇機」

⇒ **任何人把這條線接上，畫面立刻開始輸出買賣建議，直接違反合規母法禁用語。**
**處置建議：接線前必須先改寫這兩句文案。**（⛔ 本輪只登記，不修。）

**D-004 推翻說明（總管親自實跑）**：`calc_bias_pct(20000, ma=0)` → `None` → `or 0` → **`0`**。
「`ma > 0` 恆真」不成立 —— `shared/calc_helpers.py` 的 guard 是 `if _ma <= 0: return None`，
而程式**沒有任何 assert 強制 TWII > 0**，冷啟動只回一筆 `Close=0.0` 的髒值就會觸發 ⇒ **它是活碼**。
🔶 **附帶挖出一個反方向的真問題（一併登記，非死碼）**：**NaN 路徑 `or 0` 攔不住** ——
`calc_bias_pct(20000, ma=nan)` → `nan`，而 `bool(nan) is True` ⇒ `nan or 0` 得到 **`nan` 不是 `0`**，
NaN 會直接流向下游（`_ma <= 0` 對 NaN 恆 False，guard 同樣攔不住）。

**D-013 說明（由上面 🔶 那段升格為獨立編號；客戶 2026-09-21 裁示「登記，不修」）**

- **位置**：`src/data/macro/macro_snapshot.py::compute_twii_bias` 的 `calc_bias_pct(...) or 0`。
  ⚠️ **實測 4 處，非 3 處**（見下「與交辦內容的出入」）：`bias_20`／`bias_60`／`bias_240`（`:354`／`:355`／`:356`）
  **進入回傳 dict、直接流向下游**；另 1 處 `_b240_log`（`:350`）只餵同函式的 `print()`，`f'{nan:.1f}'` 印出 `nan`、不中斷。
- **問題**：`shared/calc_helpers.py::calc_bias_pct` 的 guard 是 `if _ma <= 0: return None`，
  但 **`NaN <= 0` 恆為 False**，guard 攔不住 NaN ⇒ 回傳 `nan`；
  而 **`bool(nan)` 是 `True`** ⇒ `nan or 0` 得到 **`nan` 不是 `0`**，NaN 直接流向下游。
- **證據（總管實跑；WE2 已獨立重跑，逐項相符）**：`calc_bias_pct(20000, float('nan'))` → `nan`；`nan or 0` → `nan`。
  對照 `calc_bias_pct(20000, 0.0)` → `None` → `or 0` → `0`。guard 原文與 `nan <= 0 → False` 亦經原始碼與實跑雙向確認。
- **類型**：**不是死碼** —— 是**缺值處理缺口**（`CLAUDE.md` §1 Fail Loud 相關：NaN 靜默流下游，
  既未 `raise`、也未帶 `is_imputed` 旗標）。⛔ 故「類型」欄不填 A／B／C／D，「狀態」欄用 `待修（非死碼）`。
- **與 D-004 的關係（同一行 code 的兩條路徑，⛔ 不可互相引用為對方的結論）**：
  `ma == 0` → `None → or 0 → 0`（**D-004：活碼，已推翻**）；`ma == NaN` → `nan → or 0 → nan`（**D-013：缺口**）。
- **客戶裁示**：2026-09-21「**登記，不修**」。⛔ 本輪不動任何一行 code。

⚠️ **與交辦內容的出入（據實記錄，⛔ 不吞）**：交辦規格寫「三處」，WE2 實際 grep 得 **4 處**（`:350`／`:354`／`:355`／`:356`）。
差的那 1 處是 `:350` 的 `_b240_log`，只進 log、不進回傳值 —— 「三處」若指**回傳 dict 內的三個**則正確。
本檔按實測登記 **4 處**並標明其中 1 處僅影響 log，⛔ 不以「差一處而已」帶過。

---

## ② 真死碼區

| 編號 | 位置 | 類型 | 證據 | 狀態 |
|---|---|---|---|---|
| **D-005** | `src/services/app_ai_service.py::build_llm_context`（原 `app.py::_build_llm_context`，F2 搬遷） | **A** | 定義 1、production **0**、test 6 檔。三處**互相獨立**的原始碼註解各自佐證 0 caller：`section_news_ai.py:87`、`ai_structured_summary.py:67`、`app_ai_service.py:167`。 | **確認** |
| **D-006** | `src/compute/screener/fundamental_screener.py::screen_stocks` | **A** | production 0。`app.py` 與 `mcp_server/server.py` 只 import L3 的 `fundamental_screener_service`；MCP 的同名工具 `screen_stocks` 走的是 `get_ranked_picks`，**不是**本函式。命中僅 `tests/`。 | **確認** |
| **D-007** | `src/data/macro/macro_core.py::MACRO_THRESHOLDS` — 四鍵 `HY_SPREAD`(水位版)／`YIELD_10Y2Y`／`YIELD_10Y3M`／`FED_BS_YOY` | **B**（門檻結構上永遠餵不到資料） | 全 repo `MACRO_THRESHOLDS[...]` 只有 `['VIX']` 被讀；`shared/macro_buckets.py` 的 `DangerSpec` 清單無此四鍵；`src/config/config.py::MACRO_ALERT_RULES` 只有 vix/cpi/us10y/dxy/pcr；全 repo **無 DGS2／DGS3MO／WALCL fetcher**（grep 僅 1 處教學頁文案）；HY OAS 唯一 fetcher（`risk_radar.py` 打 `BAMLH0A0HYM2`）自建獨立 delta_bp 門檻、不讀本表。四鍵僅 `tests/test_macro_core.py` 做 schema 完整性檢查。 | **確認** |
| **D-008** | `src/data/macro/tw_macro.py::fetch_tw_market_snapshot` | **A** | 定義 1、production 0；僅 `tests/test_tw_macro.py`(2) ＋ 自身 docstring(1)。 | **確認** |
| **D-009** | `src/compute/health/fin_snapshot_io.py::list_all_stocks_with_snapshots` | **A** | 定義 1、production 0；僅 `tests/test_mj_snapshot_io.py`(3)。 | **確認** |
| **D-014** | `scripts/update_macro_history.py` — 舊 CBC PXWeb「存量 vs 流量」解析鏈 8 個符號：`_parse_cbc_pxweb_level`／`_cbc_find_column_labels`／`_cbc_label_text`／`_is_level_series`／`_to_float`（本檔那個；`shared/regime_arbiter.py`、`src/compute/etf/portfolio_gates.py`、`src/data/stock/market_close_fetcher.py` 各有同名獨立定義，與本案無關）／`_CBC_LEVEL_LABEL_KEYS`／`_CBC_FLOW_LABEL_KEYS`／`_CBC_LEVEL_MAX_MOM_ABS`。連帶：`tests/test_b7b_m1m2_level_parse.py` 只測上列符號的 9 條直接單測 —— 整個 `TestParseLevelColumn`（`test_labels_pick_level_not_flow`／`test_labels_prefer_daily_average_when_two_levels`／`test_no_labels_unique_definitional_candidate`／`test_no_labels_flow_only_fails_loud`／`test_no_labels_two_level_like_columns_does_not_guess`／`test_label_says_level_but_values_negative_rejected`）＋ `TestSeriesNameOnLabels` 的 `test_m1a_only_balance_column_rejected`／`test_m1b_and_m1a_both_balance_picks_m1b`／`test_m2_label_lowercase_ok` —— 以及只被這 9 條使用的 helper `_resp` | **A**（僅在批 R 樹成立；連帶測試不計型，見證據） | **因批 R（DL-f1-r1）改用 EF15M01 而成孤兒**：`3671001` 把 Tier 2 從 EF19M01／EF21M01 改為只抓 EF15M01，並改用新的純函式 `_parse_cbc_ef15m01_levels` 解析 ⇒ 唯一 production 呼叫端 `fetch_finmind_m1m2` 不再呼叫 `_parse_cbc_pxweb_level`；其餘 7 個只在這條鏈內被用到（`_parse_cbc_pxweb_level` → `_cbc_find_column_labels` → `_cbc_label_text`；→ `_is_level_series` → `_CBC_LEVEL_MAX_MOM_ABS`；→ `_to_float`／`_CBC_LEVEL_LABEL_KEYS`／`_CBC_FLOW_LABEL_KEYS`）⇒ 整串 production 0 caller。**批 R 獨立 QA** 在組合樹（`eeccb9f`＋`3671001`）以 `git grep -w` 核對：除定義與彼此互相呼叫外，只剩測試與註解參照（總管轉述）。**交接本編修組重掃相符（2026-09-28）**：`git grep -w`＋AST 於 `3671001` 樹（疊上 `origin/main` 其後改動的 7 個檔，兩邊改動檔案不重疊），8 個符號只見於定義、鏈內互相呼叫、同檔一段自陳「成為 0 production caller」的註解（註解說它死了不算 —— 已另以 AST 驗）、以及 `tests/test_b7b_m1m2_level_parse.py`；import `scripts.update_macro_history` 的只有 `tests/`；同檔無 `getattr`／`globals()` 以字串取用這些名稱。保留 `_cbc_norm_label`（新解析器仍在用，**不是**死碼）。⚠️ **在 `origin/main`（`2dab6c2`）上仍是活碼**：`fetch_finmind_m1m2` 仍呼叫 `_parse_cbc_pxweb_level` ⇒ 型 A 只在批 R 樹成立，⛔ 不得脫離批 R 單獨刪。**連帶測試**：9 條測試與 `_resp` 是上列符號的直接單測（`_resp` 在 `3671001` 只被這 9 條使用），依 `CLAUDE.md` §-1.5.F 判定 3(3)(b)「孤兒測試」隨本批清除；測試碼不在型 A 的判定範圍（型 A 的 grep 本就排除 `tests/`），故不另立編號、不標型（比照 D-013 的原則：非死碼不混入死碼清單）。**由 `a218f9a`（批 R 第二個 commit，回應 QA）刪除**：交接本編修組以 `git show` 核對 —— 該版上列 8 個定義皆不存在、`_cbc_norm_label` 仍在；測試檔整個 `TestParseLevelColumn` 移除、`TestSeriesNameOnLabels` 只剩 `test_end_to_end_m1a_table_writes_nothing`、`_resp` 移除，與上列 9 條＋`_resp` 逐一相符。依 `CLAUDE.md` §-1.5.F 判定 3(4)「因本次改動才變成沒用的」在本批清除（總管裁定）。 | **已修**（#732 `c21cd40`，2026-09-28 squash merge；PR head `50b1ccc`＝`3671001`＋`a218f9a` 的 cherry-pick〔`git patch-id` 相同〕；交接本編修組以 `git grep -w` 於 `c21cd40` 全樹核對：8 個符號皆已不存在、`_cbc_norm_label` 仍在，見 ⑥）｜~~**確認**（批 R 同 PR 清除，待合併；合併後改 `已修` 並附 hash）~~ |
| **D-015** | `src/services/rs_leader_service.py::run_rs_leader_scan` — `refresh` 分支內的 `_clear(fetch_yf_close)`、`_clear(fetch_stock_history_1y)` 兩個呼叫（連帶 docstring「refresh: True → 清 L1 大盤/個股 cache + 本層 cache 重掃」中「清 L1 大盤/個股 cache」一語不實）；同分支第三個呼叫 `_clear(_scan_cached)` **有作用、不在本列** | **B**（`_clear` 內 `callable(getattr(fn, "clear", None))` 對這兩個函式恆 False）＋ **D**（`refresh` 參數 production 呼叫端 0 處傳入；測試有 1 例，依 D-001 前例不計） | 交接本 (c) D2-f9（批 D 實作組發現、批 D QA 核實；第二輪分類兩組同判）。**交接本編修組 2026-09-28 以 `git show`／`git grep` 於 `origin/main`（`2a68b55`）重核**：① `_clear(fn)` 只在 `getattr(fn, "clear", None)` 可呼叫時才呼叫它，否則什麼都不做；② `fetch_yf_close` 由 `from src.data.macro import fetch_yf_close` 取得 —— barrel 的 PEP 562 `__getattr__` 回傳子模組上的同一物件；全樹唯一定義 `src/data/macro/macro_core.py::fetch_yf_close` 是無裝飾器的一般 `def`；`fetch_stock_history_1y` 的全樹唯一定義 `src/data/stock/picker_fetcher.py::fetch_stock_history_1y` 亦是無裝飾器的一般 `def`；③ 全樹無任何程式存取這兩個名稱的 `.clear`，非測試碼也沒有重新綁定它們（重新綁定只見測試的 `monkeypatch.setattr`，換上的替身也是一般函式）⇒ 兩行 `_clear` 恆不做事；④ docstring 所稱的 L1 快取實際在別處、這兩行清不到：`fetch_yf_close` 的 1 小時成功快取是 `macro_core` 模組層字典 `_YF_CLOSE_CACHE`，`fetch_stock_history_1y` 內部改走 `src/data/proxy/yf_proxy.py::cached_history`（`st.cache_data`）；⑤ 同分支的 `_scan_cached` 掛 `st.cache_data`、有 `.clear`，第三行有作用（`tests/test_d3_backoff_d2f1_d2f2.py` 的夾具亦先斷言 `_scan_cached` 有 `clear`）；⑥ `refresh` 的非測試呼叫端 `app.py`、`src/services/fundamental_screener_service.py::get_ranked_picks`、`src/ui/views/page_find.py::_load_rs` 三處皆只傳 `beat_only=False, top_n=RS_SCAN_MAX` ⇒ production 下整個 `refresh` 分支到不了。⚠️ **與交辦內容的出入（據實記錄，⛔ 不吞）**：交辦寫「正式呼叫端與測試都不傳 `refresh=True`」—— 測試**有**傳：`tests/test_d3_backoff_d2f1_d2f2.py::TestD2f1MarketFailNotCached::test_failure_never_raises_to_caller_and_output_identical` 的參數化 `refresh` 例（#730 `eeccb9f` 加入）以 `refresh=True` 呼叫；該測試把上游換成無 `.clear` 的本地替身、只驗輸出與不拋，這兩行在測試中同樣不做事 —— 不影響型 B／D 的判定（型 D 依 D-001 前例只看 production），但日後改這兩行或 `refresh` 語意時該例會跑到。處理：隨批 D3b（D2-f9）；登記 ≠ 動工授權（`CLAUDE.md` §8.2.A.3）。 | **已修**（#741 `efca639`，2026-09-28 squash merge：兩行空操作已刪、docstring 改成實情；PR head `182d1a0`＝`ba9c9f9`＋`2f4caa2` 的 cherry-pick〔`git patch-id` 各自相同〕；交接本編修組以 `git show efca639 -- src/services/rs_leader_service.py` 核對刪除範圍、以 `git grep` 於 `b7456d1`〔＝`origin/main`〕核對非測試碼 0 命中，見 ⑥）｜~~**確認**（處理批＝批 D3b〔交接本 (c) D2-f9〕，登記時尚未動工；合併後改 `已修` 並附 hash）~~ |
| **D-016** | `src/data/macro/tw_macro.py::fetch_cbc_discount_rate` | **A**（`疑似`：單組字樣搜尋） | 交接本 (c) D2-f13 的一半（批 D3a QA 發現同檔 `_ttl_cache` 會把 `fetch_fred` 的失敗結果凍住 —— `fetch_china_macro` 30 分鐘、本函式 1 小時）。**2026-09-28 第四輪補分類 A 組**以字樣搜尋查無 production 呼叫端（⚠️ 單組）⇒ 總管裁定：D2-f13 只修 `fetch_china_macro` 與同型的 `fetch_usdtwd_close`（批 D3g），本函式**不修**，依 `CLAUDE.md` §8.2.A.3 先登記於此（總管轉述）。**交接本編修組登記時的字樣核對（僅供定位，⛔ 不算第二組獨立驗）**：`git grep -n fetch_cbc_discount_rate` 於 `origin/main`（`b2dafba`）全樹只見 —— 定義本身（`src/data/macro/tw_macro.py`，掛 `_ttl_cache(ttl_sec=TTL_1HOUR, maxsize=4)`）與函式內 `validate_in_log_mode(..., label='fetch_cbc_discount_rate')`；`tests/test_tw_macro_policy.py` 的 2 個測試（`test_fetch_cbc_discount_rate_via_fred`、`test_fetch_cbc_discount_rate_no_api_key`）；`docs/DEAD_CODE_AUDIT.md`（v18.400 歷史稽核表，列在「prod dead test-live」、類別 (c)）；其餘檔案 0 命中。⚠️ 字樣搜尋抓不到以字串組名的動態取用（`getattr`／`globals()`）—— 這正是標 `疑似` 的原因。與 D-011（同檔 `fetch_usdtwd_close`，曾被當死碼、已推翻）不是同一支。登記 ≠ 動工授權（§8.2.A.3）；本輪不修、不刪。 | **疑似**（⚠️ 單組字樣搜尋，待第二組驗；2026-09-28 登記） |
| **D-017** | `scripts/calibrate_macro_traffic.py::_build_features_at` — 區域變數 `_adr_series`（`_ar = _adr_series = float("nan")` 連鎖賦值中的後者） | **A**（延伸：變數賦值後 0 讀取；⚠️ 客戶定義的 A 是「production 0 caller」，延伸到變數為交接本編修組判讀） | 交接本 DL-f1-s57（2026-09-28 批 R4 實作組發現；交接本編修組當時以 pyflakes 3.4.0 實跑 `b2dafba`、`8bb46f4`、`6f3a43d` 三版，皆只報 1 條「local variable '_adr_series' is assigned to but never used」）。**2026-09-29 第五輪分類 A／B 兩組一致**判為賦值後未用（pyflakes 實跑；總管轉述）⇒ 等技術債批 1，依 `CLAUDE.md` §8.2.A.3 先登記於此。交接本編修組 2026-09-29 登記時另以 pyflakes 3.4.0 實跑 `origin/main`（`da4eb94`）版同檔：同樣只報這 1 條。同一行的 `_ar` pyflakes 未報、不在本列。死賦值、不影響輸出（⚠️ 編修組判讀）。登記 ≠ 動工授權（§8.2.A.3）；本輪不修、不刪。 | **確認**（兩組一致；pyflakes 實跑；2026-09-29 登記） |
| **D-018** | `src/data/macro/tw_macro.py::fetch_tw_cpi_yoy` | **A**（`疑似`：單組） | **2026-09-29 第五輪分類 A 組**查得正式環境無呼叫端、恆回 None（⚠️ 單組；總管轉述；「恆回 None」交接本編修組未實跑）⇒ 標 `疑似`（比照 D-016），依 `CLAUDE.md` §8.2.A.3 先登記。**交接本編修組登記時的字樣核對（僅供定位，⛔ 不算第二組獨立驗）**：`git grep -n fetch_tw_cpi_yoy` 於 `origin/main`（`da4eb94`）全樹只見 —— 定義本身（`src/data/macro/tw_macro.py`，掛 `_ttl_cache(ttl_sec=TTL_15MIN, maxsize=8)`，經 `_finmind_macro_series` 取 FinMind TaiwanMacroEconomics）與函式內 `validate_in_log_mode(..., label='fetch_tw_cpi_yoy')`；`tests/test_tw_macro_policy.py` 的 3 個測試（`test_fetch_tw_cpi_yoy_via_proxy`、`test_fetch_tw_cpi_yoy_sanity_filters_out_of_range`、`test_fetch_tw_cpi_yoy_proxy_fail_returns_none`）；`docs/DEAD_CODE_AUDIT.md`（v18.400 歷史稽核表，類別 (c)）；其餘檔案 0 命中。⚠️ 字樣搜尋抓不到以字串組名的動態取用（`getattr`／`globals()`）—— 故標 `疑似`。與 D-016（同檔 `fetch_cbc_discount_rate`）同型、與 D-019 同批登記。登記 ≠ 動工授權（§8.2.A.3）；本輪不修、不刪。 | **疑似**（⚠️ 單組，待第二組驗；2026-09-29 登記） |
| **D-019** | `src/data/macro/tw_macro.py::fetch_tw_unemployment` | **A**（`疑似`：單組） | 同 D-018（**2026-09-29 第五輪分類 A 組**，⚠️ 單組；總管轉述；「恆回 None」交接本編修組未實跑）。**交接本編修組登記時的字樣核對（僅供定位，⛔ 不算第二組獨立驗）**：`git grep -n fetch_tw_unemployment` 於 `origin/main`（`da4eb94`）全樹只見 —— 定義本身（同檔，掛 `_ttl_cache(ttl_sec=TTL_15MIN, maxsize=8)`）與函式內 `validate_in_log_mode(..., label='fetch_tw_unemployment')`；`tests/test_tw_macro_policy.py` 的 1 個測試（`test_fetch_tw_unemployment_via_proxy`）；`docs/DEAD_CODE_AUDIT.md`（類別 (b)?）；其餘檔案 0 命中。⚠️ 同 D-018，標 `疑似`。登記 ≠ 動工授權（§8.2.A.3）；本輪不修、不刪。 | **疑似**（⚠️ 單組，待第二組驗；2026-09-29 登記） |

---

## ③ 已推翻區（曾被當死碼、實為活碼）

| 編號 | 位置 | 類型 | 證據 | 狀態 |
|---|---|---|---|---|
| **D-010** | `shared/data_freshness.py::detect_frozen_columns` | —（曾指 A） | 其 wrapper `leading_frozen_columns` 現有 **2 個 production caller**：`src/compute/macro/macro_helpers.py:332`、`src/ui/pages/data_coverage.py:632`。 | **已推翻** |
| **D-011** | `src/data/macro/tw_macro.py::fetch_usdtwd_close` | —（曾指 A） | 現有 production caller：`src/ui/etf/etf_tab_portfolio.py:112-113`。 | **已推翻** |

🔶 **D-010 一併登記的陷阱（客戶規則的活教材）**：`src/ui/pages/data_coverage.py:21` 的註解
逐字仍寫「**全 repo 零 caller**」，而**同一個檔案** L72 `import` 它、L632 呼叫它 ——
**註解與實作自相矛盾**。這正是「註解說它死了不算，要自己驗」的現場證據。

---

## ④ 已修區

| 編號 | 位置 | 類型 | 證據 | 狀態 |
|---|---|---|---|---|
| **D-012** | `src/data/macro/tw_macro.py::fetch_pmi_history` | **A** | v19.86 已整刪，`tw_macro.py:1140` 留有刪除註記；且 `tests/test_review_fixes_v19_85.py::test_fetch_pmi_history_deleted` **反向守衛它不准回來**（斷言 `"def fetch_pmi_history" not in src`）。 | **已修** |

⚠️ **總管自陳的踩坑（一併登記此陷阱）**：查證途中一度誤判它「還在」—— 因為 grep 命中的是
**測試裡的斷言字串**。⇒ **grep 找定義時要排除測試中的字串斷言。**

📌 **2026-09-28**：**D-014**（`scripts/update_macro_history.py` 舊 CBC PXWeb 解析鏈 8 個符號，連帶 9 條測試與 `_resp`）已隨 #732 `c21cd40` 合併刪除 → 狀態改 `已修`；**該列留在 ② 原位、不搬列**（搬列＝刪列；同 D-004 以 `已推翻` 留在 ① 的前例），證據見該列與 ⑥。

📌 **2026-09-28**：**D-015**（`src/services/rs_leader_service.py::run_rs_leader_scan` 的 `refresh` 分支兩行空操作 `_clear(fetch_yf_close)`、`_clear(fetch_stock_history_1y)`，連帶 docstring「清 L1 大盤/個股 cache」不實一語）已隨 #741 `efca639` 合併刪除、docstring 改成實情 → 狀態改 `已修`；**該列留在 ② 原位、不搬列**（同 D-014），證據見該列與 ⑥。與 D-014 不同：**有反向守衛測試** —— `tests/test_d3b_backoff_d2f4_d2f7_d2f9.py::TestD2f9RefreshUnchanged::test_dead_lines_removed_and_docstring_truthful` 斷言兩行字樣不在原始碼、docstring 不再寫「清 L1 大盤/個股 cache」。

---

## ⑤ 與既有文件的關係（避免變成第二個真相源）

`docs/DEAD_CODE_AUDIT.md`（101 行，v18.400）是**既有的死碼稽核紀錄**。
依客戶 2026-09-21 新規則「遇到死碼先查 `DEAD_CODE.md`」，**本檔自即日起為死碼登記的唯一入口**；
`docs/DEAD_CODE_AUDIT.md` **降為歷史稽核紀錄**（內容**不刪、不改**），兩檔關係於此標明。

## ⑥ 本檔的複驗分級（依 §-2 規則 6 誠實揭露）

| 分級 | 項目 | 說明 |
|---|---|---|
| **實跑實測** | D-003、D-004 | 真的執行過函式／helper 並比對回傳值（D-003 得 `score_pct=None`；D-004 得 `0` 與 `nan`）。 |
| **grep／呼叫端靜態分類** | D-001、D-002、D-005～D-009 | 靜態掃描 + 呼叫端逐一判讀，**未實跑**。 |
| **caller 反證** | D-010、D-011 | 指出具體 production caller，反證「死碼」宣稱不成立。 |
| **測試守衛佐證** | D-012 | 由既有反向守衛測試佐證已刪、且不准回來。 |
| **實跑實測** | D-013 | 總管實跑 ＋ **WE2 獨立重跑**（`calc_bias_pct(20000, nan)` → `nan`；`nan or 0` → `nan`；`calc_bias_pct(20000, 0.0)` → `None`）。⚠️ 但「共 4 處」是 **WE2 單組 grep**，未經第二組複驗。 |
| **grep／呼叫端靜態分類** | D-014 | 批 R 獨立 QA 在組合樹（`eeccb9f`＋`3671001`）以 `git grep -w` 核對（總管轉述；交接本編修組未見 QA 原始輸出）；交接本編修組 2026-09-28 另以 `git grep -w`＋AST 重掃（`3671001` 樹，疊上 `origin/main` 其後改動的 7 個檔；兩邊改動檔案不重疊）→ 相符，並以 `git show` 核對 `a218f9a` 的刪除範圍。**未實跑**。⚠️「0 production caller」是全稱句，且**只在批 R 樹成立**（`origin/main` 上仍是活碼，見該列）；兩組各自單組、未經第三組重掃。 📌 **2026-09-28 補**：#732 `c21cd40` 合併後，批 R 樹即現行 `origin/main`，「只在批 R 樹成立」一語已隨合併失效；已修的核對見下一列。 |
| **grep／呼叫端靜態分類** | D-014（已修） | 交接本編修組 2026-09-28 以 `git grep -w` 於 `c21cd40`（＝`origin/main`）全樹重掃：`_parse_cbc_pxweb_level`／`_cbc_find_column_labels`／`_cbc_label_text`／`_is_level_series`／`_CBC_LEVEL_LABEL_KEYS`／`_CBC_FLOW_LABEL_KEYS`／`_CBC_LEVEL_MAX_MOM_ABS` 全樹 0 命中，`_to_float` 在 `scripts/update_macro_history.py` 0 命中（他檔同名獨立定義不計），`_cbc_norm_label` 仍在；`tests/test_b7b_m1m2_level_parse.py` 已無 `TestParseLevelColumn` 與 `_resp`，`TestSeriesNameOnLabels` 只剩 `test_end_to_end_m1a_table_writes_nothing`。**未實跑**。⚠️ 與 D-012 不同：**沒有反向守衛測試**（全樹 grep 不到這些名稱）⇒ 日後有人加回來，CI 不會擋。⚠️ 單組（交接本編修組一組核對，未經第二組）。 |
| **grep／呼叫端靜態分類** | D-015 | 交接本編修組 2026-09-28 以 `git show`／`git grep` 於 `origin/main`（`2a68b55`）核對：兩個函式的定義與裝飾器、barrel 轉發、全樹 `.clear`／重新綁定、`run_rs_leader_scan` 的全部呼叫端（含測試；#736 未動相關檔，`3f001cd` 上跑相同搜尋結果一致）。**未實跑**。判型（**B＋D**）為交接本編修組判定（原 D2-f9 的發現與核實為批 D 實作組＋批 D QA）。⚠️「兩行恆不做事」「production 0 處傳 `refresh`」是全稱句（`git grep` 窮舉），未經第二組重掃；⚠️ 單組（交接本編修組一組核對，未經第二組）。 |
| **grep／呼叫端靜態分類** | D-015（已修） | 交接本編修組 2026-09-28 以 `git show efca639 -- src/services/rs_leader_service.py` 核對刪除範圍：`refresh` 分支只剩 `_clear(_scan_cached)`，兩行 `_clear(fetch_yf_close)`、`_clear(fetch_stock_history_1y)` 已刪，docstring 改為只清本層（掃描結果快取＋掃描層退避紀錄）、不清 L1 大盤／個股快取；再以 `git grep` 於 `b7456d1`（＝`origin/main`）全樹搜尋兩行字樣：只見於 `tests/test_d3b_backoff_d2f4_d2f7_d2f9.py`（反向守衛與修前對照組），非測試碼 0 命中。**未實跑**。有反向守衛測試（見 ④ 2026-09-28 D-015 補註）。⚠️ 單組（交接本編修組一組核對，未經第二組）。 |
| **grep／呼叫端靜態分類** | D-016 | 第四輪補分類 A 組字樣搜尋（總管轉述；交接本編修組未見 A 組原始輸出）；交接本編修組 2026-09-28 登記時以 `git grep` 於 `origin/main`（`b2dafba`）看全樹命中分布（見該列），僅供定位、⛔ 不算第二組獨立驗。**未實跑**。⚠️「production 0 呼叫端」是全稱句 —— 故狀態標 `疑似`；待第二組重掃（含動態取用）後再改 `確認` 或 `已推翻`。⚠️ 單組。 |
| **grep／呼叫端靜態分類** | D-017 | 第五輪分類 A／B 兩組以 pyflakes 實跑（總管轉述；交接本編修組未見兩組原始輸出）；交接本編修組 2026-09-29 以 pyflakes 3.4.0 實跑 `origin/main`（`da4eb94`）同檔 → 只報 `_adr_series` 這 1 條（2026-09-28 另實跑三版，見交接本 DL-f1-s57）。靜態分析、**未執行函式**。兩組一致 ⇒ 狀態標 `確認`；型別 A 延伸到變數為交接本編修組判讀（見該列）。 |
| **grep／呼叫端靜態分類** | D-018、D-019 | 第五輪分類 A 組字樣搜尋（總管轉述；交接本編修組未見 A 組原始輸出）；交接本編修組 2026-09-29 登記時以 `git grep` 於 `origin/main`（`da4eb94`）看全樹命中分布（見各列），僅供定位、⛔ 不算第二組獨立驗。**未實跑**（含「恆回 None」）。⚠️「production 0 呼叫端」是全稱句 —— 故狀態標 `疑似`；待第二組重掃（含動態取用）後再改 `確認` 或 `已推翻`。⚠️ 單組。 |

⚠️ **未經第二組複驗的部分**：D-001／D-002 的「**無任何動態餵值**」、D-005～D-009 的
「**production 0 caller**」都是**全稱句** —— 由調查組窮舉 + 總管複驗得出，**沒有第三組獨立重掃**。
依 §-2 規則 6，它們**可以照著用，但不得當成已證事實**去支撐下一步的刪除動作。
⛔ 並請記得檔頭那句：**本檔非窮舉。**
