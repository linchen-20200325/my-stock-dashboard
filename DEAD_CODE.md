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

⚠️ **未經第二組複驗的部分**：D-001／D-002 的「**無任何動態餵值**」、D-005～D-009 的
「**production 0 caller**」都是**全稱句** —— 由調查組窮舉 + 總管複驗得出，**沒有第三組獨立重掃**。
依 §-2 規則 6，它們**可以照著用，但不得當成已證事實**去支撐下一步的刪除動作。
⛔ 並請記得檔頭那句：**本檔非窮舉。**
