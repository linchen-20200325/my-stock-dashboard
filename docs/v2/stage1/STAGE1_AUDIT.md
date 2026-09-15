# STAGE1_AUDIT — 階段 1 獨立稽核（QA / Red Team）

> **產出日**：2026-09-15｜**稽核組**：階段 1 獨立稽核組（執行 AI，**單組**）
> **量測基準**：`git HEAD = fab88a7`，工作區乾淨（`git status --short` 無輸出）
> **稽核對象**：`scratchpad/DATA_LINEAGE.md`（636 行）、`scratchpad/INDICATOR_SSOT.md`（1,650 行）
> **紀律**：全程唯讀。**未動任何程式碼、未動被稽核的兩份文件、未做任何 git 寫入。**
> 本檔是本 session **唯一**新建的檔案（另有 `scratchpad/audit/` 下 6 支探針腳本，皆為本檔證據）。
> **狀態**：⚠️ **本檔本身也是單組結論，未經第三組複驗**（`CLAUDE.md §-2` 規則 6）。

---

## 0. 一頁結論

| # | 等級 | 標題 | 落在 |
|---|---|---|---|
| **A1** | 🔴 | `DATA_LINEAGE` 三處引用 **`macro_helpers.compute_macro_health`** —— **全站沒有這個函式**，而且 repo 自己早就寫下「它不存在」 | §2 |
| **A2** | 🔴 | `INDICATOR_SSOT` 四處引用 **`v5_modules.py:calc_357_valuation`** —— 真名是 `calc_dividend_yield_357` | §2 |
| **A3** | 🔴 | `DATA_LINEAGE` 引用 **`risk_radar.py:vix_block`** —— 該檔無此符號 | §2 |
| **A4** | ⚠️ | `DATA_LINEAGE` 兩處把 **`M1B_M2_GAP_DETERIORATION_THRESHOLD`** 當成 M1B/M2 現行判定門檻 —— 它 **0 consumer（死常數）**，且單位（pts/月 月差分）與被比較的量（gap level, pp）**不是同一種東西** | §2 / §6 |
| **B1** | ✅ | 紅線 1（`calc_fundamental_score` 量綱錯誤）**成立**，且**有 production caller、有渲染到畫面** ⇒ 嚴重性**不下修** | §1 |
| **B2** | ✅ | 紅線 2（m1b/m2 負值）**成立**；**根因已找到**（repo 自陳：流量當存量）；**但該 parquet 在 `src/`+`app.py` 內 0 個讀取點** ⇒ **沒有進入燈號判定** | §1 |
| **B3** | ✅ | 紅線 3（health=0→弱勢危險、sharpe→0.0）**成立**；**下游無 gate**；sharpe 0.0 實測**吃掉一整顆星**（5★→4★） | §1 |
| **C1** | 🔴 | 兩份**都漏**：`shared/macro_compute.py:58-60` 三連缺值偽裝，缺年線 ⇒ `bias_240` 恆 0 ⇒ **恆判「🟢 強勢多頭 / 持股 80-100%」** | §3 |
| **C2** | 🔴 | 兩份**都漏**：`shared/thresholds.py` 內兩支 L0 SSOT 分級函式 **docstring 自稱「等價」，實測不等價** —— 5.0% 殖利率一支說「適度減碼」、另一支說「合理價 — 可分批布局」 | §6 |
| **D1** | ⚖️ | 「15 個 family」vs「7 份」**兩者都對，在數不同的東西**；但 `INDICATOR_SSOT` 寫「**比回報的 7 份更多**」**是錯的** —— 15 **不包含** 7 裡的 2 個 | §4 |
| **E1** | ⚠️ | `INDICATOR_SSOT §5.2` 的 🔴「MDD 量綱雙胞胎、比較時必須換算」**高估** —— 實測兩者**從不相遇**，`risk_control` 沒有 import `calc_mdd` | §4 |

**沒有找到的**：兩份文件**都沒有**產生買賣建議（§5 逐條查過，全部行動語都在反引號內且標示為引用）。

---

## §1 三條紅線的獨立複驗

> **方法宣告**：本節**未採信**兩份文件的任何轉述。三條都自己重跑，且**刻意用與總管不同的路徑**——
> 總管查的是「這個 bug 在不在」，本組查的是「**它有沒有出口**」（caller → render → 有沒有 gate 擋住）。
> 探針原碼：`scratchpad/audit/p1_fund.py` / `p2_m1m2.py` / `p2b.py` / `p2c.py` / `p2d.py` / `p3.py` / `p3b.py`。

---

### 紅線 1｜`calc_fundamental_score` 拿「元/股」當「%」比門檻

**結論：✅ 成立。並且回答總管沒問的那一題 —— 有 production caller，而且有渲染到畫面。嚴重性不下修，反而要上修。**

**(a) 量綱錯誤本身（實跑）**

```
$ python scratchpad/audit/p1_fund.py
signature: (qtr_df, yearly_df, avg_div)
YIELD_HIGH/MID/LOW = 7.0 5.0 3.0

avg_div=  13.0  valuation.score=3  dividend.score=2  valuation.checks=[('357殖利率估值', '13.0% 便宜區 >7%', True)]
avg_div=   5.0  valuation.score=2  dividend.score=2  valuation.checks=[('357殖利率估值', '5.0% 合理 5~7%', True)]
avg_div=   3.5  valuation.score=1  dividend.score=1  valuation.checks=[('357殖利率估值', '3.5% 合理 3~5%', False)]
avg_div=   2.0  valuation.score=0  dividend.score=1  valuation.checks=[('357殖利率估值', '2.0% 偏貴 <3%', False)]
avg_div=   0.0  valuation.score=0  dividend.score=0  valuation.checks=[]
avg_div=  None  valuation.score=0  dividend.score=0  valuation.checks=[]
```

函式簽章 `(qtr_df, yearly_df, avg_div)` —— **`price` 不是輸入**。估值分是 `avg_div_twd` 的單調函式。

**(b) `avg_div` 確實是「元/股」（三段追到源頭，全部本次實測）**

1. `src/data/stock/app_stock_fetchers.py:fetch_dividend_data` —— `ddf['cash'] = to_numeric(ddf[cash_col])`（`cash_col` 取 `CashDividend` / `cash_dividend` / `StockEarningsDistribution`）→ `groupby('year').sum().tail(5)` → `avg_div = yr['cash'].mean()` ⇒ **近 5 年每年現金股利（元/股）的算術平均**。
2. `src/ui/tabs/tab_stock.py:701` —— `_cur_yld = (avg_div2 / _cur_p * 100)`：**同一個變數，同一個檔案**，要除以股價才變成 %。
3. `src/ui/tabs/tab_stock.py:1591-1593` —— `_cp2_ai = round(avg_div2/YIELD_HIGH_DEC, 1)`：除以 0.07 得到**價格**，只有「元」除以「比例」才會得到「元」。

**(c) ⭐ production caller 存在（總管未問的那一題）**

```
src/ui/tabs/tab_stock.py:894   render_health_score_section(sid2, health2, details2, df2, price2, qtr2, yearly2, avg_div2, ...)
  └─ src/ui/tabs/stock_sections/section_health_score.py:99   _fund_sc = calc_fundamental_score(qtr2, yearly2, avg_div2)
       └─ section_health_score.py:123   st.markdown(render_health_score(health2, details2, sid2, _fund_sc, _tech_al), unsafe_allow_html=True)
            └─ src/ui/render/app_render.py:58-79   fund_html —— 逐個 cat 印出 {sc}（0-3 大字）+ 每個 check 的 ✓/✗ + 名稱
```

- 呼叫鏈上 **沒有任何 gate**：`tab_stock.py` 從 `t2d` 解包後直接呼叫，`awk` 掃 303–900 行**無 `st.stop` / 無提前 `return`**。
- ⇒ **這不是死碼，是每次「🔍 載入完整分析」都會畫出來的四張小卡之一。**

**(d) 畫面上會看到什麼 —— 本組把 `INDICATOR_SSOT` 的精準度再確認一次（它是對的）**

`app_render.py:70` 的迴圈是 `for cn, cv, cp in fs.get('checks', [])[:3]:`，而字串只組 `{cn}` 與 `✓/✗` ——
**`cv`（`'13.0%'` 那個字串）被 unpack 了但沒有被渲染**。
⇒ 使用者看到的是「⚖️ 估值 **3** ✓ 357殖利率估值」，**看不到那個假的百分號**。
⇒ `INDICATOR_SSOT §4.2` 寫「**錯的是分數與 ✓/✗，不是一個印出來的數字**（這反而更難被使用者發現）」—— **本組複驗屬實**。

**(e) 本組追加：同一畫面上「合理 vs 昂貴」自相矛盾（實測）**

`calc_fundamental_score` 對 `[3, 5)` 標「**合理 3~5%**」；
`shared/thresholds.py:classify_stock_357_price` 對 yield ∈ [3%,5%) 回 `'dear'`，
`src/ui/tabs/stock_sections/section_357_valuation.py:117` 把 `'dear'` 映射成 **`'🔴昂貴價 — 謹慎操作'`**。
兩張卡在**同一頁、同一次 render**（`tab_stock.py:894` 與 `:930`）。

**嚴重性判定：不下修。** 有 caller、有渲染、無 gate、且錯誤方向是**把真實低殖利率的貴股打成「便宜區」滿分**。

---

### 紅線 2｜`data_cache/finmind_m1m2.parquet` 的 `m1b` / `m2` 有負值

**結論：✅ 負值成立（數字與文件完全一致）。⭐ 但本組追到了兩件文件沒追到的事：**
**(i) 根因 repo 自己早就寫下來了；(ii) 這個 parquet 在 app 內 0 個讀取點 ⇒ 沒有進入燈號判定。**

**(a) 實測數字（`scratchpad/audit/p2c.py`）**

```
n= 240   m1b<0: 73   m2<0: 47   m2<m1b: 63   |gap|>30: 188
date range: 2006-08-01 -> 2026-07-01
m1b : min=-472,037  max=635,797
m2  : min=-255,360  max=964,868
gap : min=-13,976.5 max=+36,033.7
```
⇒ `DATA_LINEAGE §C-R2` 的「73/240、47/240」**逐字正確**。

**(b) ⭐ 根因：不必推測，repo 自己寫過了（`DATA_LINEAGE §F-1` 說「本組沒有查出根因」）**

`shared/signal_thresholds.py:196-201`（逐字）：

> `data_cache/finmind_m1m2.parquet` 實測 `m1b_m2_gap` ∈ [-13,976, +36,034]（真實量綱是 ±10 個百分點），
> 且 `m1b` 欄 239 筆中有 **72 筆為負** —— 貨幣供給額不可能為負。**根因在
> `scripts/update_macro_history.fetch_finmind_m1m2` 的 CBC PXWeb 解析把「月變動量(流量)」當成
> 「餘額(存量)」,再對一個會變號的序列算 YoY。** 這個根因本次未修。

同一個根因在 `scripts/export_stock_db.py:200-210` 又寫了一次，並附**更強的證據**：
「2006-12 的 m1b=325,888 與 2007-04 的 22,383 相差 15 倍，那是**月變動額**不是餘額，
只是剛好落在合理區間」⇒ **連「通過 sanity 的 38 列也不可信」。**

⇒ **`DATA_LINEAGE` 的「未查出根因」是可以被關掉的** —— 一次 `grep -rn finmind_m1m2 shared/` 就會命中。
（本組不責怪該組**標註**了未查證 —— 那是對的；問題是**它其實查得到**。）

**(c) ⭐ 那個負值**到底有沒有進燈號判定**？—— 答：沒有。**

| 讀取點 | 位置 | 有沒有 gate |
|---|---|---|
| `scripts/export_stock_db.py:244` `write_money_supply` | 離線匯出 | ✅ **有** `_money_supply_sanity_gate`（`m1b>0` ∧ `m2>=m1b` ∧ `|gap|<=30`），不過就 `DROP TABLE` 整表不外送 |
| `scripts/calibrate_health_weights.py:271` | 離線校準 | ✅ **有** staleness gate（`raise SystemExit`），且只寫 `MACRO_HEALTH_WEIGHT_PROPOSAL.md`，**不寫門檻** |
| `src/**` + `app.py` | — | 🟢 **0 個讀取點** |

實測（`grep -rn finmind_m1m2 src/ app.py shared/`）：`src/` 內唯一命中是
`src/data/macro/macro_cache_reader.py:60` 的 `CACHE_DATASET_CADENCE` **登錄項**（新鮮度對照表的一個 key），
而真正讀 parquet 的 `load_v2_chart_series` **只讀 `twii_ohlcv` 與 `finmind_margin` 兩支**（實測該函式全文）。

⇒ 🔴 **`DATA_LINEAGE` 主表該列的「畫面落點 = 🌍 總經 v2 › 走勢卡」是錯的。** 它到不了走勢卡。

**(d) 線上燈號走的是另一條路（不同實作，不同量綱）**

五桶燈的 `m1b_m2_gap` 來自 `macro_helpers.py:1803` 的 `_traced("m1b_m2_gap", ..., _g(m1b_m2_info, "gap"), ...)`，
而 `m1b_m2_info` 來自 **`src/data/macro/tw_macro.py:fetch_cbc_m1b_m2`** —— 它讀 `ms1.json`，
拿到的**本來就是 YoY 率**，`gap = round(m1b_yoy - m2_yoy, 2)`（百分點）。**與 parquet 的 writer 是兩支獨立實作。**

**(e) ⚠️ 但這裡有一個**潛在**缺口（本組新發現，不是現正出錯）**

```
$ python scratchpad/audit/p2d.py
gap=  -13976.5  within_valid_range=True  classify_danger=red
gap=    -925.2  within_valid_range=True  classify_danger=red
gap=    2349.7  within_valid_range=True  classify_danger=green
```
`shared/macro_buckets.py` 的 `DangerSpec("m1b_m2_gap", ...)` **沒有 `valid_min` / `valid_max`**
（實測：`valid_min=None valid_max=None`；16 盞燈中只有 `us10y` [0,20] 與 `dxy` [70,130] 有）。
⇒ 若線上路徑哪天也吐出量綱壞掉的值，**`§3.2` 範圍守衛不會攔，會直接判成紅燈**（而不是誠實的 gray）。
⚠️ **本組不宣稱線上會發生** —— 只宣稱**那道守衛不存在**。

**(f) 另一層已存在的護欄（本組確認，供風險定位）**

`shared/signal_thresholds.py:M1B_M2_LEG_ENABLED = False` ⇒ `market_strategy.market_regime` 的
M1B-M2 腿已於 2026-08-19 校準後**停用**（AUC 0.5366），`_max` 從 6 降 5。
⚠️ 但**五桶燈那一盞仍 `wired=True`**（實測），停用的只有評分腿。

---

### 紅線 3｜`calc_health_score` 全缺 → 0 分 →「弱勢危險」；`calc_sharpe` 缺值回 `0.0`

**結論：✅ 兩條都成立。下游查過了，⛔ 沒有任何覆蓋率 gate 攔它們。sharpe 的 0.0 實測吃掉一整顆星。**

**(a) `calc_health_score` 實跑（`scratchpad/audit/p3.py`）**

```
     df=None, all None -> score=0  details={}  grade=('弱勢危險', '#ef4444', 'health-C', '🔴')
    empty df, all None -> score=0  details={}  grade=('弱勢危險', '#ef4444', 'health-C', '🔴')

health_grade 邊界：0/1/49 → 弱勢危險🔴 ｜ 50/79 → 震盪盤整🟡 ｜ 80/100 → 優質優良🟢
```
`details={}`（**空 dict，不是 `None`，也沒有任何缺值旗標**）⇒ 消費端在型別上分不出「0 分」與「沒資料」。

**(b) 下游有沒有 gate？—— 沒有（實測呼叫鏈）**

`src/ui/tabs/stock_sections/section_health_score.py:86-96`：
```
if health2 >= HEALTH_GRADE_A_MIN: ...
elif health2 >= HEALTH_GRADE_B_MIN: ...
else:  _ha = f'健康度 {health2:.0f}分，技術面偏弱，跳過'
       _hb = '不要強求，另找更好標的'
```
⇒ **`health2 = 0`（＝完全沒資料）落到 `else`，輸出的是一個有明確方向的結論**，而不是「未評估」。
⇒ 上游 `tab_stock.py:894` 呼叫前**沒有** `if df2 is None or df2.empty: return`（本組 awk 掃 303–900 行確認）。
⇒ 順帶：`tab_stock.py:285` `cur_price2 = float(df2['close'].iloc[-1]) if ... else 0` —— **股價也被填 0**。

**(c) `calc_sharpe` 三條路全部回 `0.0`（`src/compute/etf/etf_calc.py:726-744`，實跑）**

```
calc_sharpe(10 rows)             = 0.0     # len(ret) < 20
calc_sharpe(flat 60 rows, vol=0) = 0.0     # ann_vol <= 0
calc_sharpe(empty)               = 0.0     # except → [calc_sharpe] swallow: KeyError: 'Close'
```
第三條同時違反 `CLAUDE.md §1`（吞例外後回假值）與客戶紅線（缺值填 0）。

**(d) ⭐ 下游 gate 查了 —— 有一個正確的機制，但被 `0.0` 繞過（本組量化）**

`etf_scoring_helpers.compute_etf_composite_score` 的 docstring 自陳「**缺項 rescale 有效權重**」——
也就是說**它本來設計成吃得下 `None`**。但 `build_etf_score_row:104` 寫的是 `_r['sharpe'] = calc_sharpe(df)`，
`calc_sharpe` **永不回 None** ⇒ rescale 永遠不會對 sharpe 生效。

實測（`scratchpad/audit/p3b.py`，同一組其他 6 個維度固定）：

| `row['sharpe']` | 綜合分 | 星等 |
|---|---|---|
| `0.0`（現況：缺值） | **0.767** | **4 ★** |
| `None`（誠實缺值） | **0.911** | **5 ★** |

⇒ **一檔上市未滿 20 個交易日的新 ETF，因為「算不出夏普」而被扣掉一整顆星**，
而畫面上它看起來就是「夏普 0.00」——一個合法的觀測值。
（`_WEIGHTS['sharpe'] = 0.15`、`_NORM['sharpe'] = (1.0, 0.2)`，實測。）

**(e) 對照組：同一個 repo 有做對的版本**

`src/compute/etf/dividend_station.py:sharpe_weekly` —— 週數不足 / 波動≈0 → **`return None`**，
下游 `health_b(None)` → `Flag("⚪", "B 無夏普（週數不足或波動為零,算不出來）", miss_reason=SS.MISS_NOT_ENOUGH)`。
⇒ **同一個指標，兩支實作，一支誠實一支填 0。** `INDICATOR_SSOT §5.1` 對此的記載本組複驗屬實。

---

## §2 引用抽查表

**方法（與兩組都不同）**：用正則從兩份文件抽出**全部** `` `path.py:symbol` `` 形式的引用（**不抽樣，全取**），
共 **104 筆**（`DATA_LINEAGE` 68 筆去重、`INDICATOR_SSOT` 36 筆去重），
逐筆 (1) `find` 檔案是否存在、(2) 檔內是否有 `def` / `class` / module-level 常數 / 字串命中，
再對其中 **31 筆**做**語意複核**（讀原碼，判斷「符號存在」之外，**文件對它的描述對不對**）。
腳本：`scratchpad/audit/extract_refs.py` + `check_refs.py`。

**自動檢查總結**：104 筆中 **2 筆符號不存在**、4 筆為函式內區域變數（自動判定漏判，人工複核後 ✅）。
**語意複核另外抓到 2 筆「存在但描述不符」。**

| # | 文件 | 引用 | 判定 | 說明 |
|---|---|---|---|---|
| 1 | DL | `src/compute/macro/macro_helpers.py:compute_macro_health` | 🔴 **不存在** | **見 A1，下方單獨展開** |
| 2 | IS | `src/compute/strategy/v5_modules.py:calc_357_valuation` | 🔴 **不存在** | **見 A2，下方單獨展開** |
| 3 | DL | `src/compute/risk/risk_radar.py:vix_block` | 🔴 **不存在** | 該檔內 VIX 相關符號是 `_signal_vix_level` / `_signal_vix_term_struct` / `_resolve_vix3m`。`fetch_vix_block` 在 `macro_snapshot.py`，**不在 risk_radar** |
| 4 | DL | `shared/signal_thresholds.py:M1B_M2_GAP_DETERIORATION_THRESHOLD`（當成現行門檻） | ⚠️ **存在但語意不符** | **見 A4，下方單獨展開** |
| 5 | IS | `src/compute/etf/etf_calc.py:calc_mdd` ×「`MAX_PORTFOLIO_DRAWDOWN` 對照、比較時必須換算」 | ⚠️ **存在但語意不符** | **見 §4-E1** |
| 6 | DL | `src/data/macro/macro_snapshot.py:fetch_us10y_block` | ✅ | 失敗回 `{'us10y': {'_err':…, 'current': None, 'value': None}}` —— 頂層鍵 `us10y` 不帶 `_`，`_is_block_failure`（`all(k.startswith('_'))`）判不出來。**逐字正確** |
| 7 | DL | `src/data/macro/macro_snapshot.py:fetch_vix_block` / `fetch_cpi_block` / `fetch_fed_funds_block` / `fetch_export_block` | ✅ | 4 支皆掛 `@_cache_success_only(ttl=TTL_1HOUR)` |
| 8 | DL | 「9 支 block 中 6 走 `_cache_success_only`、3 沒走（m1b_m2 / twii_2y_for_ma240 / us10y）」 | ✅ **逐支複驗屬實** | 實測 decorator 行號：139/404/579/655/670/857 為 `_cache_success_only`；175/362/528 為 plain `@st.cache_data` |
| 9 | DL | `src/data/macro/tw_macro.py:fetch_cbc_m1b_m2` 三 Tier + `is_proxy_tier` | ✅ | Tier1 `ms1.json` / Tier2 `EF15M01` / Tier3 `^TWII` proxy，僅 Tier3 設 `is_proxy_tier=True` |
| 10 | DL | `shared/macro_provenance.py:is_m1b_m2_proxy`「精確集合比對，刻意不做 substring 嗅探」 | ✅ | docstring 逐字吻合（旗標 → `M1B_PROXY_SOURCE_LABELS` 集合 → False） |
| 11 | DL | `scripts/update_macro_history.py:fetch_finmind_m1m2` | ✅ | 存在；`source = "CBC:PXWeb:EF19M01+EF21M01"` 與 parquet `source` 欄一致 |
| 12 | DL | `src/data/stock/app_stock_fetchers.py:fetch_dividend_data` 開頭 `avg_div=0.0` | ✅ | 逐字屬實（見 §1 紅線 1） |
| 13 | DL | `src/services/market_strategy.py:volume_window_stats` 回 `(None, None)` | ✅ | 存在；`market_strategy.py:295` `_vol_ratio = ... if (avg_volume or 0) > 0 else None` |
| 14 | DL | `src/data/core/data_registry.py:DATA_REGISTRY` | ✅ | module-level 常數存在 |
| 15 | DL | `src/data/macro/macro_core.py:PMI_SOURCE_REGISTRY` + 8 支 `_pmi_src_*` | ✅ | `_pmi_src_cier_en_monthly` / `_dgtw` / `_ndc` / `_cier8` / `_cier21` / `_stockfeel` / `_cnyes` / `_moneydj` 八支 `def` 全部命中 |
| 16 | DL | `src/data/portfolio/forward_test_store.py:FORWARD_TEST_STORE_PATH` | ✅ | 常數存在；`data_cache/forward_test/picks.parquet` 實體存在（5,129 bytes） |
| 17 | DL | `src/ui/views/page_today.py:AS_OF_NOT_IN_CONTRACT` / `REFRESH_FAILED_WHAT_NOW` | ✅ | 兩個 module-level `str` 常數皆存在（:610 / :589） |
| 18 | DL | `src/compute/risk/reconcile.py:reconcile_us10y` / `normalize_tnx_quote` | ✅ | 兩支 `def` 存在 |
| 19 | DL | `src/data/core/financial_statements_fetcher.py:_v()` 迴圈跑完 `return 0.0` | ✅ | 存在，C-R3 描述屬實 |
| 20 | DL | `data_cache/twii_ohlcv.parquet` volume「41 個 0 + 11 個 NaN」 | ✅ **數字逐一複驗** | 實測 `n_zero=41, n_nan=11, close n_zero=0`（n=4,932，2006-07-17→2026-09-11） |
| 21 | IS | `shared/macro_buckets.py:classify_danger` 的三段 direction 邏輯 | ✅ **逐字比對原碼一致** | 文件貼的虛擬碼與 `macro_buckets.py:538-569` 行為等價 |
| 22 | IS | `shared/macro_buckets.py:BUCKET_DANGER_SPECS`「16 個」 | ✅（**但見 §4-F3**） | 實測 `len = 16`，5 桶 `{long:3, mid:6, short:3, chips:3, news:1}` |
| 23 | IS | `max_score` 恆為 None | ✅ **四段證據全部複驗屬實** | `grep max_score macro_helpers.py` → 只有 :370 / :372 / :374 / :425，**return dict 內 0 命中**；`signals.parquet` 實測 `rows=16`、`max_score notna = 0/16`、`score = [2.5,2.5,2.5,1.5,3.5,3.5]` |
| 24 | IS | `src/compute/risk/risk_radar.py:_apply_third_axis_overlay` 的 `valuation_level` 是死碼 | ✅ **複驗屬實** | `grep -rn "valuation_level\s*=" --include=*.py .` → production **0 命中**，全部在 `tests/test_dual_verdict_ui.py` |
| 25 | IS | `src/compute/screener/scorability.py:EXPENSIVE_VALUATION_MARKER = "超貴"` | ✅ | 常數存在（:34），並在 `:122` 當預設參數 |
| 26 | IS | `shared/thresholds.py:classify_stock_357_price` → `cheap/fair/dear/overpriced/na` | ✅ | 五個 code 逐字吻合 |
| 27 | IS | `section_357_valuation.py:_PE_BANDS` / `_BOX_LABELS` / `_TEACHER_LABELS` | ✅ | 三者皆為 `render_357_valuation_section` 內的**函式區域變數**（:311 / :114 / :92）。自動檢查誤判為 mention-only，人工複核**確認存在**且內容吻合 |
| 28 | IS | `src/compute/scoring/scoring_helpers.py:calc_health_score` / `calc_fundamental_score` | ✅ | 見 §1 |
| 29 | IS | `src/compute/etf/etf_scoring_helpers.py:_WEIGHTS` 與 `_NORM`（🔴 inline） | ✅ | 實測 `_WEIGHTS = {'total_ret_1y':0.25,'cagr_3y':0.2,'sharpe':0.15,'mdd':0.15,'expense_ratio':0.12,'aum':0.08,'div_yield_cv':0.05}`、`_NORM['sharpe']=(1.0,0.2)` —— 全 inline 屬實 |
| 30 | IS | `src/compute/etf/dividend_station.py:sharpe_weekly` / `light_235` / `screen_333` | ✅ | 三支 `def` 存在 |
| 31 | IS | `src/ui/tabs/tab_helpers.py:classify_stock_status_lamp` / `final_recommendation` | ✅ | 兩支存在；§3.6 貼的 if-else 串與原碼一致 |
| 32 | IS | `src/services/financial_health_engine.py:no_ai_overall_verdict` / `_no_ai_profitability` | ✅ | 兩支存在 |
| 33 | IS | `shared/position_throttle.py:compute_position_throttle` | ✅ | 存在 |
| 34 | IS | `src/compute/macro/macro_forward_test.py:build_signal_row` | ✅ | 存在；`'max_score': _opt_float(tl.get('max_score'))` 用 `.get()` 屬實 |
| 35 | IS | `shared/stock_buckets.py:classify_pb_level` | ✅ | 存在 |

---

### 🔴 A1（**本次最嚴重的一條**）｜`compute_macro_health` —— 文件引用了一個 repo 自己記錄過「不存在」的函式

```
$ grep -rn "def compute_macro_health" --include=*.py .
（無輸出，exit 1）
```

`DATA_LINEAGE` 三處引用它：
- **L107**：血緣總圖 mermaid 節點 `C1["macro_helpers.compute_macro_health"]`（圖上 L2 的**唯一** macro 計算節點）
- **L167**：美國核心 CPI 那一列的「**消費端**」欄 = `src/compute/macro/macro_helpers.py:compute_macro_health`
- **L170**：VIX 那一列的「消費端」欄 = 同上

**而 repo 早就把這件事寫下來了** —— `shared/signal_thresholds.py:57-64`（逐字）：

> ⚠️ 2026-08-19 稽核更正:本區塊原寫「macro_helpers.py compute_macro_health」——
> **全站沒有這個函式**。它只存在於 8 個檔案的註解/docstring 裡
> (本檔、macro_buckets、position_throttle、section_long、tab_macro、macro_classroom、ui_widgets、tests/test_macro_buckets)。
> 真正的實作是 `calc_traffic_light` 內的 `_health_parts` / `_w_sum` / `_health` 那段 inline 程式碼。
> **一個「被 8 處引用、卻不存在的符號名」本身就是 §3.3 反捏造要防的東西。**

**為什麼這一條特別重**（三層，逐層都成立）：

1. **它正面違反客戶紅線**「不得發明不存在的資料源」。
2. **它違反 `DATA_LINEAGE §0.2` 自己立的硬規矩**：
   「每一列的『取數』欄都必須是我在本 session 內 grep 到的真實 `file:符號名`。**查不到就寫「⚠️ 查無實作」，⛔ 不留白、⛔ 不編**」。
   —— 這一條是它自稱的「第一要務」。
3. **它是 `CLAUDE.md §-2` 點名的 `db4c139` 型態的完美複製**：**一個宣稱，作者自己沒查，而 repo 裡就有反證。**
   一次 `grep -rn "def compute_macro_health"` 即可否證。

⚠️ **對照組（這一點對 `INDICATOR_SSOT` 有利，要據實記）**：`INDICATOR_SSOT` **0 次**使用這個假名，
其 §3.2 正確寫成「程式 `src/compute/macro/macro_helpers.py:calc_traffic_light` 的 `health` 欄」。
⇒ **同一批產出的兩份文件，一份踩了、一份沒踩** —— 這同時是 §4 的跨文件不一致（見 §4-F1）。

---

### 🔴 A2｜`v5_modules.py:calc_357_valuation` —— 真名是 `calc_dividend_yield_357`

```
$ grep -rn "calc_357_valuation" --include=*.py src/ shared/
（無輸出）
$ grep -n "def calc_dividend_yield_357" src/compute/strategy/v5_modules.py
309:def calc_dividend_yield_357(price: float, *, avg_div_twd, div_years=None) -> dict:
```

`INDICATOR_SSOT` **四處**使用這個假名：
- **L135**：§2.1 主表「程式」欄 —— `classify_stock_357_price`（L0 判定）＋ **`calc_357_valuation`**（L2 文案）
- **L141**：§2.1「缺值行為」欄 —— 「`v5_modules.calc_357_valuation` 回 `{...}`」
- **L256**：§2.6 估值字面表 **F4 列**的「產生點」欄
- **L1590**：§9.2 自陳「只讀了 `calc_357_valuation`」

**這一條與 A1 不同，要精確區分**：
- ✅ **它描述的「內容」是真的** —— 本組逐字比對 `calc_dividend_yield_357`，
  文件引用的 docstring（`§1：不可回 0 —— 0% 會被判成「超貴」，那是拿缺資料當看空結論`）
  與六個 `signal` 字串（`🟢 甜甜價（7%+近5年年年配）` …）**全部逐字吻合**。
- 🔴 **錯的是「名字」** —— 疑似把 L5 的檔名 `section_357_valuation.py` 與 L2 的函式名混成一個不存在的符號。

⇒ 依 `INDICATOR_SSOT §0.2`「三個閱讀約定」與客戶紅線，**名字錯了就是查無實作**：
拿 `v5_modules.py:calc_357_valuation` 去 grep 會 0 命中，下一個人會以為這條鏈不存在。
⚠️ 而 **§9.2「只讀了 `calc_357_valuation`」** 這句自我揭露也因此指向一個不存在的符號 —— **連盲點清單都錯了名字**。

---

### ⚠️ A4｜`M1B_M2_GAP_DETERIORATION_THRESHOLD` —— 死常數 + 量綱不同，被當成現行門檻引用兩次

```
$ grep -rn "M1B_M2_GAP_DETERIORATION_THRESHOLD" --include=*.py .
./shared/signal_thresholds.py:266:M1B_M2_GAP_DETERIORATION_THRESHOLD: float = -2.0
   → 非定義處引用：0 筆
```
對照同一區塊的鄰居（本組一併測了，用來證明這**不是**整批死掉、是**單獨一顆**）：

| 常數 | 非定義處引用數 |
|---|---|
| `FOREIGN_5D_NET_THRESHOLD_YI` | 21 |
| `MARGIN_BALANCE_OVERHEAT_THRESHOLD_YI` | 58 |
| `TWII_20D_DROP_THRESHOLD_PCT` | 4 |
| **`M1B_M2_GAP_DETERIORATION_THRESHOLD`** | **0** |

`DATA_LINEAGE` 兩處把它當現行門檻：
- **L182** 主表：「`gap` 單位 **pts/月**（門檻 `M1B_M2_GAP_DETERIORATION_THRESHOLD = -2.0`）」
- **L462** §C-R2：「實測值域 -925 ~ +2349，**而判定門檻是 `M1B_M2_GAP_DETERIORATION_THRESHOLD = -2.0` pts**」

**兩個獨立的錯**：
1. **它沒有 consumer。** 唯一的消費者 `macro_signal_lookback_tw.py` 已於 v19.181 detox 整檔刪除
   （`CLAUDE.md §8.2.A.2` 有記該檔被刪，但**沒有記這顆常數因此變成孤兒**）。
   **現行**的 m1b_m2_gap 門檻是 `shared/macro_buckets.py` 的 `DangerSpec("m1b_m2_gap", yellow=1.0, red=0.0)`。
2. **它量的不是同一個東西。** 其 docstring 逐字：「（單位：**pts/月，月差分**）」——
   它吃的是 `gap.diff()`（**月變化量**）；而 parquet 的 `m1b_m2_gap` 欄與線上的 `gap` 都是 **level**（pp）。
   拿 level 去比一個為 diff 設計的門檻，**本身就是 `CLAUDE.md §4.1` 的量綱錯誤**。
   （`DangerSpec` 對同一個 key 宣告 `unit="%"`，`market_strategy.py` 也印 `%` ⇒ 「pts/月」這個單位標記
   在**三個真相源裡是少數派**。）

⇒ §C-R2 的**結論仍成立**（那份資料確實壞了），但它**用錯了佐證**。
⚠️ 據實說明來歷：「pts/月」這個說法**沿自 `CLAUDE.md §4.1` 的單位陷阱表**，
`DATA_LINEAGE` 是**沿用上游而未複驗**——但它把這一列標成「本次實測」而不是「【上游材料】」。

---

## §3 兩份都漏掉的「缺值填 0」

**方法（刻意與兩組不同）**：不 grep 字面，改用 **AST 掃描**（`scratchpad/audit/ast_zero.py`）
把 `src/` + `shared/` + `scripts/` + `app.py` 全部解析成語法樹，抓三種節點：
`dict.get(k, 0)` / `X if COND else 0`（IfExp orelse 為 0）/ `X or 0`（BoolOp 末項為 0）。
**原始命中 707 筆**（`dict.get(...,0)` 305、`or 0` 220、`ternary else 0` 182）。

⛔ **本節不列 707 筆。** 客戶要的是判斷力不是數量。
本組先把範圍收到**判定層**（`src/compute/` / `src/services/` / `shared/`）且該行涉及**可量測的物理量**
（價/率/分/量/額…），得 **88 筆**，再逐筆套 `DATA_LINEAGE §C` 自己訂的 if-else 判準，
**只報兩份文件沒有列、且本組判定為紅/黃的**。**合法的 0 一律不列**（下方 §3-B 舉例說明為什麼不列）。

### §3-A 本組新報的（依嚴重度排序）

| # | 位置 | 寫法 | 判定 | 理由 |
|---|---|---|---|---|
| **N1** ⭐ | `shared/macro_compute.py:58-60`<br>`evaluate_market_status_v4_final` | `current_price = current_price or 1.0`<br>`ma_240 = ma_240 or current_price`<br>`futures_net_oi = futures_net_oi or 0` | 🔴 **紅** | **三連缺值偽裝，而且會翻成最樂觀的結論。** ① 缺價 → **捏造 1.0 元**；② **缺年線 → 拿現價頂替 ⇒ `bias_240 = ((p−ma)/ma)×100 = 0.0` 恆成立**，於是 `is_bull_market = p >= ma×0.99` **恆為 True**；③ 缺外資期貨 → 0 口 ⇒ `is_foreign_hedging = False`。<br>三者疊起來：**完全沒有資料時，函式回「🟢 強勢多頭」+「建議擴大核心部位…」+ `hold_ratio = "80% - 100%"`。**<br>**有 production caller**：`src/ui/tabs/macro/section_warroom.py:88`，且 caller 端**又補了一次** `or 0`（`_wr_bias.get('price', 0) or 0` / `_wr_bias.get('ma240', 0) or 0`）⇒ 缺值一路暢通。<br>畫面實際會印 `f'年線乖離 {_v4["Bias_240"]:+.1f}%'` ⇒ **「年線乖離 +0.0%」被當成一個真的量測值顯示出來**。<br>⚖️ **減輕情節（要據實記）**：主結論已於 v19.182（C1）改由 `calc_traffic_light.effective_regime` 供給，`_v4` 的 `Is_Bull` 只降為補充提示。**但 `Bias_240` 那個數字仍直接顯示。**<br>⚠️ `DATA_LINEAGE §C-A6` 列的是**同一檔的 :104-106**（法人 `fillna(0)`），**不是這三行** |
| **N2** | `src/services/financial_health_engine.py:305,371,943,968` `cash_pct = fd.get("現金佔總資產(%)", 0) or 0` | `.get(k,0) or 0` | 🔴 **紅** | 缺「現金佔總資產」⇒ 0% ⇒ `if cash_pct >= FH_CASH_RATIO_SAFE_PCT` / `>= FH_CASH_RATIO_WATCH_PCT` 全落空 ⇒ 判成**現金最枯竭**的一級，並進 `_score(cash_pct, [(SAFE,80),(WATCH,60)])` 拿最低分。<br>⭐ **與 §C-R3 是同一種病、但在另一個檔** —— 該檔**自己有**正確的三態機制 `_stmt_gap()`（缺 → `N/A` + `Data_Gap` 旗標），且**就用在同一支函式的隔壁兩行**（`ca` / `cl` 走 `_stmt_gap`）。**同一個函式裡兩套標準。** |
| **N3** | `src/services/financial_health_engine.py:860,863,877` `debt / eq / lt_liab / ppe = fd.get(..., 0) or 0` | 同上 | 🟡 **黃** | 缺「負債比率(%)」⇒ 0% ⇒ **「零負債」是最好的讀數**。<br>⚖️ **有部分護欄**：`if debt == 0 and not is_finance:` 會從 `總負債/總資產` **重算兜底**；`ppe > 0` / `eq > 0` 也有守衛。<br>🔴 **但兜底本身又是 `.get(...,0) or 0` 疊起來的** —— `_tl`/`_ta`/`_cl`/`_ca` 四個原始欄同樣缺→0，兜底就靜默失效，`debt` 停在 0。判黃不判紅，因為本組**未**追到「debt=0 最終會不會變成一個 Pass」 |
| **N4** | `src/services/health_history_service.py:83` `"rsi": r.get("rsi") or 0` | `or 0` | 🔴 **紅** | 缺 RSI ⇒ **0** ⇒ RSI=0 是**理論上的極端超賣**，不是「沒資料」。<br>⭐ **最能說明問題的是它的鄰居**：**同一個 dict literal 的上一行**寫的是 `"health": r.get("health")` —— **沒有 `or 0`，誠實留 None**。**兩行之間兩套標準。**<br>有 production caller：`src/ui/tabs/stock_sections/section_kline_chart.py:175`（健康度歷史走勢圖），⇒ 缺 RSI 的日子會在圖上畫成一個**觸底的點** |
| **N5** | `src/services/app_ai_service.py:274-275` `b240 = data.get('bias_240') or 0` / `b20 = data.get('bias_20') or 0` | `or 0` | 🟡 **黃** | 缺乖離 ⇒ 0% ⇒ **「股價恰在均線上」**這個具體判斷被餵進 **LLM prompt**。<br>判黃不判紅：本組**未**複驗該 prompt 段的完整輸出，也未確認 caller 是否已先擋 |
| **N6** | `src/compute/risk/risk_radar.py:120,356` `delta_pct = (cur - prev) / prev * 100 if prev else 0.0` | `ternary else 0` | 🟡 **黃** | 前一日基準缺 ⇒ 日變化 **0.0%**（「今天沒動」）而非「不知道」。這兩處分別在 `_signal_vix_level` 與另一支 signal 內，**風險雷達**會拿它判斷 |
| **N7** | `shared/stats_helpers.py:76` `pct = (last - prev) / prev * 100 if prev else 0` | `ternary else 0` | 🟡 **黃** | 通用工具層的「變化率」缺基準 → 0%。因為是 **shared 層的通用 helper**，任何 caller 都繼承這個行為，而函式簽章上看不出來 |

### §3-B 本組**特意不列**的（判斷力示範，避免湊數）

| 位置 | 為什麼不列 |
|---|---|
| `financial_health_engine.py:358,372,388,970` `ar_days = fd.get("應收帳款天數", 0) or 0` | ✅ **下游一律用 `ar_days > 0` / `0 < ar_days <= FH_DSO_FAST_DAYS` 守住** ⇒ 0 進不了判定。**與 N2 同一行寫法、判定相反**，差別就在有沒有 `> 0` 守衛 |
| `scoring_engine.py:115-118` `ma5 = latest.get('MA5', 0) or 0` | ✅ 下游全是 `if ma5 > 0 and ...`。（`DATA_LINEAGE §C-3` 已列為綠，本組同意） |
| `scoring_engine.py:145,154,162` `... else 0` | ✅ 那是**評分表的最低分級**（if-elif-else 的 else 分支），不是缺值 —— 0 是有效分數 |
| `portfolio_coherence.py:57-58` `round(_stock/_total*100,1) if _total else 0.0` | ✅ `_total = 0` 代表**投組真的是空的**，佔比 0% 是真觀測 |
| `concentration.py:183` `_coverage_pct = (_classified/_total*100) if _total > 0 else 0.0` | ✅ 沒有任何標的時覆蓋率 0% 是真的 |
| `macro_session_patch.py:166` `int(_prev.get("rounds", 0) or 0) + 1` | ✅ 計數器，第一輪本來就是 0 |
| `etf_smart_analysis.py:193` `[1.0 if t in peers else 0.0 ...]` | ✅ one-hot 指示向量，0 是真值 |

---

## §4 兩份文件之間的不一致

### ⭐ D1｜「15 個 family」vs「7 份」—— **裁決：兩者在數不同的東西；但 `INDICATOR_SSOT` 的措辭是錯的**

| | `INDICATOR_SSOT §2.6` | `DATA_LINEAGE §B-2` |
|---|---|---|
| 數的單位 | **估值中文標籤字面的產生點**（1 個「產生點的一組標籤」＝ 1 family） | **357 殖利率「分級＋三檔反推價位」的呼叫點**（有沒有走 SSOT 函式） |
| 涵蓋題材 | 357 殖利率 **＋ ETF 7% 估值 ＋ PB 分級 ＋ PE 河流 ＋ 教學表** | **只有 357 殖利率** |
| 數量 | **15**（F1–F15） | **7**（①–⑦） |

**兩者都不算錯。** 但 `INDICATOR_SSOT` 的標題寫「**實測 15 個 family，比回報的 7 份更多**」——
「更多」蘊含**包含關係**，而 **包含關係不成立**：

| `DATA_LINEAGE` 的 7 個裡 | 在 15 裡嗎 |
|---|---|
| ② `section_psy_checklist.py` | ❌ **不在**（只在 §2.6 末尾的散文裡被當「正確樣板」提到，不是 family 列） |
| ⑥ `section_op_recommendation.py` | ❌ **不在** |

⚠️ **這兩個之所以不在 15 裡，其實是 `INDICATOR_SSOT` 判對了**（它們**不產生中文標籤**：②只取 `zone_code`、⑥只回一個布林），
⇒ **問題不在內容，在措辭。** 「比 7 更多」會讓讀者以為 7 已被 15 吸收，
於是下一個人只看 15 就以為窮舉了呼叫點 —— 而②⑥恰恰是「**走了 SSOT**」與「**只用單一門檻自算**」兩個
`DATA_LINEAGE` 特別關心的形態。

**本組建議的正確說法**（不是要求改文件，是給讀者的併讀規則）：
> **7 = 357 的呼叫點（誰繞過 SSOT 函式）；15 = 估值標籤字面的產生點（誰各寫一套中文）。兩張表要併讀，不可互相取代。**

---

### F1｜同一個函式，兩份文件給了兩個不同的名字（一真一假）

| | 寫法 | 判定 |
|---|---|---|
| `DATA_LINEAGE` L107/L167/L170 | `macro_helpers.compute_macro_health` | 🔴 **不存在** |
| `INDICATOR_SSOT §3.2` | `macro_helpers.calc_traffic_light` 的 `health` 欄 | ✅ **正確** |

⇒ 讀者同時拿到兩份，會以為是兩個東西（一個「算 health」、一個「算紅綠燈」），
實際上 **`health` 就是 `calc_traffic_light` 回傳 dict 裡的一個鍵**，沒有第二支函式。

---

### F2｜同一顆常數，兩份文件給了兩種單位

| | `m1b_m2_gap` 的單位 |
|---|---|
| `DATA_LINEAGE` L182 | 「**pts/月**（門檻 `M1B_M2_GAP_DETERIORATION_THRESHOLD = -2.0`）」 |
| `INDICATOR_SSOT §3.1` 門檻表 | `DangerSpec.unit` 逐字取自原碼 ⇒ **`"%"`**（yellow=1.0 / red=0.0） |
| **原碼**（本組實測） | `DangerSpec("m1b_m2_gap", ..., unit="%")`；`tw_macro`：`gap = m1b_yoy − m2_yoy`（pp）；`market_strategy.py:150` 印 `f'({m1b_m2_gap:+.2f}%)'` |

⇒ **`INDICATOR_SSOT` 對，`DATA_LINEAGE` 錯**（詳見 A4）。

---

### ⚠️ E1｜`INDICATOR_SSOT §5.2` 的 MDD「量綱雙胞胎」**高估了嚴重性**

文件寫（🔴 級）：
> `MAX_PORTFOLIO_DRAWDOWN = 0.15` 是比例，`calc_mdd` 回的是百分比（−15.0）—— **兩者差 100×。比較時必須換算**

**本組實測否證「必須換算」這半句**：

| 事實 | 證據 |
|---|---|
| `risk_control.py` **沒有 import `calc_mdd`** | 該檔 import 區唯一外部來源是 `from src.config import (MAX_POSITION_PER_STOCK, MAX_PORTFOLIO_DRAWDOWN, ...)` |
| `update_drawdown` 用**自己算的比例**比自己的比例常數 | `drawdown = (peak − current)/peak`（比例，正值）；`if drawdown >= self.max_drawdown_pct`（0.15）⇒ **量綱內部一致** |
| `MAX_PORTFOLIO_DRAWDOWN` 的全部出現處 | 只有 `config.py:18` 與 `risk_control.py:11,15,159`。**沒有任何一處與 `calc_mdd` 相遇** |
| `calc_mdd` 的下游 | 只有 ETF 評分 `_NORM['mdd'] = (-10.0, -30.0)`（同為百分比，一致） |

⇒ **正確的說法是「命名衛生問題」**（兩個都叫 drawdown、刻度不同、常數名沒編碼單位 —— 這部分文件說得對，
且 `CLAUDE.md §4.1` 命名規範確實被違反），**不是「有一條會算錯 100 倍的比較路徑」**。
⚠️ 文件同一格說的「`→ risk_control.update_drawdown` 對照」也因此不成立 —— **沒有對照**。

---

### F3｜`INDICATOR_SSOT §3.1`「五桶 16 盞燈」—— 數字對，但少一句話

實測 `BUCKET_DANGER_SPECS` 共 16 個，**其中 `wired = False` 有 1 個**：

```
UNWIRED: foreign_net 外資現貨淨買賣
  reason: FinMind inst net 單位未確認（股 / 千股 / 億元）—— §4.1。確認前填值會直接誤判紅綠燈，故決策端刻意回 None（§1 寧缺勿錯）。
```
⇒ **production 永遠只會亮 15 盞，第 16 盞恆 gray。** §3.1 的門檻表 8 欄裡沒有 `wired` 欄，
標題「16 盞燈」會讓讀者以為 16 盞都在跑。
⚖️ **這是精度不足，不是錯** —— 而且那顆 `unwired_reason` 寫得非常好（是本 repo 缺值治理的正面範例）。

---

## §5 它們有沒有違反自己的規則

### 5.1 有沒有產生買賣建議？——**沒有。兩份都通過。**

**方法**：對兩份全文 grep 行動語（`建議買/賣/加碼/減碼/布局/分批/進場/逢低/持有`、`可逢`、`積極買進`、
`強烈買進`、`該買`、`該賣`、`逢高減碼`、`停損設`、`分批布局`、`建議持股`），再對每一個命中做
`S1-6 §1 STEP 2`「缺項填補測試」——問：這句有沒有把「只有讀者才有的六個變數」當成已知值填掉？

| 文件 | 命中 | 判定 |
|---|---|---|
| **`DATA_LINEAGE`** | **0 筆** | ✅ 完全乾淨。它在 §0.5 立了規矩「引用到程式碼內含操作字樣的段落時，**只寫位置、不轉錄字樣**」，**全文確實做到**（本組全文 grep 驗證） |
| **`INDICATOR_SSOT`** | 16 筆 | ✅ **全部在反引號內、且全部是引用現行 code**。§8 的標題逐字寫「**現行 code 裡的行動語（稽核軌跡，非本文件的建議）**」；§5.4 寫「（**引用：現行 UI 字串**）」；§3.6 的 code block 內逐行加 `# 引用：現行 code 的 label` |

⇒ 依本次任務書「**引用現行 code 的違規原文當稽核軌跡是允許的，但必須有明確標示為引用**」，
**兩份都合規。**

⚖️ **一個要記下來的邊界案例（不判違規）**：`INDICATOR_SSOT` L338 的實測反例表
逐字重現了 `recommend_etf_action` 的輸出 `reasons=['綜合分 0.70(≥0.65)體質佳', **'價位偏低,分批加碼時機較佳'**]`。
它在反引號內、且處在「改一個字就改行為」的 bug demo 上下文，**本組判為合規**；
但那一列**沒有**像 §5.4 / §3.6 那樣加「引用」標記 ⇒ **是該文件自己標記紀律的一處不一致**，值得補。

### 5.2 「每條規則都要有 if-else 或評分表」——**基本達成，兩處缺格**

本組逐節檢查 `INDICATOR_SSOT` 的指標表（§2.1–§6.3）：**絕大多數都附了 if-else 虛擬碼或評分表**
（§3.1 `classify_danger` 三段 direction、§3.4 五步驟、§4.3 分級樹、§4.5 `_norm` 加權、§5.4 分段查表…），
**規則面達標**。缺的是**缺值行為**那一欄：

| 位置 | 缺什麼 |
|---|---|
| `§5.3` 停損表「固定停損（備援）」列 | 「缺值行為」欄寫 **`—`** |
| `§5.3` 停損表「投組回撤煞車」列 | 「缺值行為」欄寫 **`—`** |

⇒ 三套並存的停損門檻裡，**只有 ATR 停損那一套寫了缺值行為**。
⚖️ 嚴格說這不違反「每條規則都要有 if-else」（算式欄有給），但客戶紅線是「缺失值不得填 0」，
**沒寫缺值行為 = 沒辦法判它有沒有踩紅線**。

### 5.3 有沒有未標註的全稱句？——**沒有找到。兩份的自標紀律都做得很好。**

本組特別去找「該標而沒標」的全稱句，**沒有找到反例**。相反，兩份的自標是本次看到最紮實的部分：
- `DATA_LINEAGE §0.1` 立了四級證據標記（【本次實測】/【碼內自陳】/【上游材料】/⚠️ 查無），全文逐列標；
  `§0.1b` 還把「所有計數以 HEAD=fab88a7 為準、過期就現場重量」寫死。
- `INDICATOR_SSOT §6.2` 主動寫「**本檔沿用 S1-2 的推導，同樣未跑反例實測**」——
  **這句自標救了它**（見 §6-C3：本組跑了那個反例，結論要修正）。
- `INDICATOR_SSOT §2.6` C5 寫「（**單組 grep 結論，未複驗**）」——本組複驗後**確認它是對的**。

⚠️ **唯一的落差不是「沒標」，是「標了但其實查得到」**：`DATA_LINEAGE §F-1` 把
「m1b/m2 負值的根因」列為**沒查出來**，而根因就寫在 `shared/signal_thresholds.py` 裡（見 §1 紅線 2(b)）。
**誠實標註不等於已盡查證義務。**

---

## §6 兩組都沒想到的

### ⭐ C2｜`shared/thresholds.py` 裡**兩支 L0 SSOT 分級函式互相矛盾，而其中一支的 docstring 宣稱它們等價**

`shared/thresholds.py:90`（`classify_stock_357_price` 的 docstring，逐字）：
> **與 `classify_yield_zone()` 等價(都用同 SSOT 常數)**，差別:本函式吃 price+avg_div 而非 cur_yield…

**實跑否證**（固定 `avg_div = 7.0` 元，用 `price = avg_div / yield` 反推，讓兩支吃到同一個殖利率）：

| 殖利率 | `classify_yield_zone` | `classify_stock_357_price` → UI 標籤 | 一致？ |
|---|---|---|---|
| 8.0% | 🟢 強烈買進 (`strong_buy`) | `cheap` → 🟢便宜價 | ✅ |
| 7.0% | 🟢 強烈買進 (`strong_buy`) | `cheap` → 🟢便宜價 | ✅ |
| **6.0%** | **⚪ 中性持有** (`neutral`) | **`fair` → 🟡合理價 — 可分批布局** | ❌ **顏色與動作都不同** |
| **5.0%** | **🟡 適度減碼** (`reduce`) | **`fair` → 🟡合理價 — 可分批布局** | ❌ **方向相反** |
| 4.5% / 4.0% | 🟡 適度減碼 (`reduce`) | `dear` → 🔴昂貴價 — 謹慎操作 | ❌ 🟡 vs 🔴 |
| **3.0%** | **🔴 獲利了結** (`sell`) | **`overpriced` → 🔴超過昂貴 — 避免追高** | ❌ 動作不同 |

**根因（兩層，都在同一個檔案裡）**：
1. **邊界含入方向相反**。`classify_yield_zone` 用 `cur_yield <= YIELD_MID` 把 **5.0% 歸到差的一側**；
   `classify_stock_357_price` 用 `price <= targets['fair']`（等價於 `yield >= 5%`）把 **5.0% 歸到好的一側**。
   3.0% 同理。**兩支對同一顆常數採了相反的開閉區間。**
2. **級距語意整體錯開一格**：5–7% 在一支是「⚪ 中性」、在另一支是「🟡 合理／可分批布局」；
   3–5% 在一支是「🟡 適度減碼」、在另一支是「🔴 昂貴價」。

**⭐ 這不是理論問題 —— 同一個個股頁同時跑三套**（`src/ui/tabs/tab_stock.py`，本組追鏈實測）：

| 行 | 走哪一支 | 一檔 5.0% 殖利率的股票會被說成 |
|---|---|---|
| `:701-707` | `classify_yield_zone(_cur_yld)` → `_valuation_simple` → `classify_stock_status_lamp` | code=`reduce` → `_valuation_simple = '偏貴'` |
| `:930` | `render_357_valuation_section` → `classify_stock_357_price` | **🟡合理價 — 可分批布局** |
| `:894` | `render_health_score_section` → `calc_fundamental_score` | 拿 **`avg_div` 元** 比 7/5/3 ⇒ 完全無關的第三種答案（紅線 1） |

**兩份文件為什麼沒抓到**（據實說明，避免誇大本組貢獻）：
- `INDICATOR_SSOT §2.6` **有**把 F1 / F2 列成兩個 family，`§3.6` **也有**實測出
  「個股頁 `'偏貴'` 不觸發 🟠減碼、組合頁 `'🔴昂貴'` 會觸發」——**它摸到了症狀**。
- **但它把病因歸給「字面耦合」（標籤字串不一致）。本組的發現是：字面只是表層，
  `yellow/red` 的分界本身就對不上，而且 `shared/thresholds.py` 的 docstring 還寫了「等價」。**
  ⇒ 就算把全站字串統一成 code 比對（§2.6 推薦的樣板），**這兩支仍然會給出相反的答案**。
- `DATA_LINEAGE §B-2` 把 `classify_stock_357_price` 當成「**那個** SSOT 函式」，列了誰繞過它；
  **它沒有注意到同一個檔案裡還有第二支 SSOT 函式，而且不等價。**

⇒ **`DATA_LINEAGE §B-2` 的「✅ 數字（7/5/3）是 SSOT 的，沒有 magic number 問題」需要補一句**：
**數字是 SSOT 的，但「拿數字劃界的規則」有兩份，而且兩份會吵架。**

---

### ⭐ C3｜`INDICATOR_SSOT §6.2` 自陳「未跑反例」的那一條 —— **本組跑了，結論要修正**

文件寫：
> `macro_snapshot.py` 的 `'bias_240': calc_bias_pct(...) or 0` 看似把缺值壓成 0…
> 但 `calc_bias_pct` 只在 `ma <= 0` 時回 `None`，而該 caller 的 `ma` 來自台股指數收盤價的平均
> ⇒ `ma > 0` 恆成立 ⇒ **`or 0` 是死碼，不是活 bug**。
> ⚠️ 本檔沿用 S1-2 的推導（`close > 0 → mean > 0 → ma > 0`），**同樣未跑反例實測**。

**本組跑了反例**（直接餵 `compute_twii_bias` 一個受污染的 close 序列）：

```
   all zeros:  {'bias_240': 0, 'ma240': 0.0,  'data_days': 300, 'is_estimated': False}
    negative:  {'bias_240': 0, 'ma240': -5.0, 'data_days': 300, 'is_estimated': False}
```

**三點修正**：
1. **`or 0` 不是結構上的死碼，是「條件成立的死碼」。** 它的「死」完全建立在
   **上游資料不會出現 ≤0 的 close** 這個**資料品質假設**上 —— 函式內**沒有任何守衛**
   （`_cs = _twii[_cc_b].dropna()` 只擋 NaN，不擋 0 與負數）。
   而這個 repo **已經有** writer 把假 0 寫進同一支 parquet 的前例（`twii_ohlcv.volume` 41 個 0，
   `DATA_LINEAGE §C-R1` 自己列的）。
2. **⭐ 真正被漏掉的是後果比文件描述的更嚴重**：一旦觸發，輸出是
   `is_estimated = False` + `data_days = 300` ——
   **看起來是一個「資料齊全、完全可信」的讀數**。
   對比 n<240 那條路（`is_estimated = True`，畫面會掛「估算」chip），
   **這條路連一個旗標都沒有。** `classify_danger('bias_240', 0)` → **green**（yellow=10 / red=20）。
3. **⚖️ 但現況確實沒有在燒**：本組實測 `data_cache/twii_ohlcv.parquet` 的 `close`
   **`n_zero=0, n_neg=0, n_nan=0`**（n=4,932）⇒ **潛在缺口，不是現行 bug**。

⇒ 準確說法：**`or 0` 今天不會觸發（文件的結論對），但它「不會觸發」的理由是運氣不是設計（文件的理由不夠強），
而且觸發時它會製造一個「沒有任何旗標的綠燈」（文件沒講）。**

---

### C4｜`bias_240` 有**兩支獨立實作，對「資料不足」採相反政策**（兩份都沒並排看）

| 實作 | 位置 | n < 240 時 |
|---|---|---|
| **A** | `src/data/macro/macro_snapshot.py:compute_twii_bias` | `_ma240 = mean(tail(min(240, n)))` ⇒ **用較短均線冒充年線**，回 `is_estimated=True` |
| **B** | `src/data/macro/macro_cache_reader.py:load_v2_chart_series` | `if len(_close) >= DEFAULT_BIAS_MA_LEN:` ⇒ **拒畫**，並 print「**不以較短均線冒充年線**」，key 直接不出現 |

**同一個指標名、同一個資料源（^TWII close）、同一層（L1）、相反的缺值政策。**
B 的作法正是 `CLAUDE.md §1` 要的；A 的作法 `INDICATOR_SSOT §6.2` 已批評過 ——
**但沒有人指出 repo 裡就有一份做對的版本，而且就在隔壁檔案。**
⇒ 這條的價值在於：**修法不必發明**，把 B 的判斷搬進 A 即可。

---

### C5｜`DATA_LINEAGE` 主表對 `finmind_m1m2.parquet` 的「消費端／畫面落點」是錯的

文件 L184 寫：消費端 =「`macro_cache_reader`（`CACHE_DATASET_CADENCE` 走月頻判定）」、畫面落點 =「🌍 總經 v2 › 走勢卡」。

**實測**：`load_v2_chart_series` 全文只讀 **`twii_ohlcv`**（算 `bias_240`）與 **`finmind_margin`**（算 `margin`），
回傳的 dict 只有這兩個 key。`finmind_m1m2` 在 `macro_cache_reader.py` 裡**只出現在 `CACHE_DATASET_CADENCE` 的登錄項**
（一張**新鮮度對照表**，不是讀取點）。

⇒ 「在新鮮度登記表裡有一筆」被誤讀成「有人在讀它」。
⇒ **正確的落點是：`src/` 內 0 個讀取點；只有 `scripts/export_stock_db.py`（有 sanity gate）
與 `scripts/calibrate_health_weights.py`（有 staleness gate）兩支離線腳本。**

**這件事同時是好消息與壞消息**：好消息是負值進不了畫面（紅線 2 的爆炸半徑比想像小）；
壞消息是 **git 追蹤著一份 240 列、最後更新停在 2026-07-01、36% 的列在物理上不可能的資料檔，而 app 根本沒在用它** ——
它的存在只會讓下一個人（含 AI）以為那是活的資料源。

---

### C6｜`M1B_M2_GAP_DETERIORATION_THRESHOLD` 是 v19.181 detox 留下的**唯一**孤兒常數

見 A4。本組特意把同區塊另外三顆一起量（21 / 58 / 4 個引用），**證明這不是「一整批都死了」而是漏了一顆**——
`CLAUDE.md §8.2.A.2` 記了 `macro_signal_lookback_tw.py` 被整檔移除、也記了 §4.1 的 evidence 改指向
`shared/signal_thresholds.py`，**但沒有人回頭看「改指過去的那顆常數還有沒有人用」**。
⇒ 對照 `CLAUDE.md §-1.5.F 判定 3(4)` 的判準（「因為這次改動才變成沒用的嗎？」）——
**它正是那一類**，只是在 v19.181 當時沒被清掉。**本組僅登記，不動（§-1）。**

---

## §7 我查過、確認沒問題的區塊（明列）

> 列在這裡的每一項，本組都**實際跑過或讀過原碼**，不是「沒看到問題」。

### 7.1 `DATA_LINEAGE` 確認正確的

| 區塊 | 本組怎麼驗 | 結果 |
|---|---|---|
| **§E-1** `fetch_us10y_block` 的雙重問題 | 讀 `macro_snapshot.py:528-577` 全文 + `_is_block_failure` 全文 | ✅ **兩半都對**：① 它掛的是 plain `@st.cache_data`；② 失敗回 `{'us10y': {...}}`，頂層鍵不帶 `_` ⇒ `all(k.startswith('_'))` 為 False ⇒ 即使改掛 `_cache_success_only` **也判不出失敗** |
| **9 支 block 的 6/3 分佈** | 逐 decorator 比對行號 | ✅ 6 支 `_cache_success_only`（vix/cpi/fed_funds/tw_pmi/ndc/export）、3 支 plain（m1b_m2/twii_2y/us10y）—— **一支不多一支不少** |
| **§C-R1** `twii_ohlcv.volume` 41 個 0 + 11 個 NaN | `read_parquet` 實測 | ✅ **逐字相符**（n=4,932，`volume` n_zero=41 / n_nan=11） |
| **§C-R2** m1b 73/240、m2 47/240 為負 | `read_parquet` 實測 | ✅ **逐字相符** |
| **§C-R3** `_v()` 永不回 None | 讀 `financial_statements_fetcher.py` | ✅ 迴圈跑完 `return 0.0`，描述屬實 |
| **§A-2** M1B/M2 三 Tier + 只有 Tier3 是 proxy | 讀 `tw_macro.fetch_cbc_m1b_m2` 全文 | ✅ 三個 `return` 分支、僅 Tier3 設 `is_proxy_tier=True` |
| **§B-6** 正面範例清單（`data_registry` / `PMI_SOURCE_REGISTRY` / `CBC_MS1_URLS` / `ttls` / `margin_schema` / `edu_tokens` / `roc_calendar` / `macro_provenance`） | 逐一 grep 存在性 + 讀 `is_m1b_m2_proxy` 全文 | ✅ 8 項全部存在且描述吻合 |
| **§0.2 的自我紀律本身** | 全文 grep 行動語 | ✅ 「只寫位置、不轉錄字樣」**全文 0 例外** |
| **§0.4 六種缺值語彙** | 抽驗 `fetch_fred` 空 DF / `_err_*` dict / `fetch_price_data` err token | ✅ 六種都能對到實例 |

### 7.2 `INDICATOR_SSOT` 確認正確的

| 區塊 | 本組怎麼驗 | 結果 |
|---|---|---|
| **§3.3** `max_score` 恆 None（四段證據） | `grep max_score macro_helpers.py` + `read_parquet(signals.parquet)` | ✅ **四段全部複驗屬實**：return dict 內 0 命中；`rows=16`、`max_score notna=0/16`、`score=[2.5,2.5,2.5,1.5,3.5,3.5]`（0.5 級距也屬實） |
| **§3.1** `classify_danger` 三段 direction | 逐行比對 `macro_buckets.py:538-569` | ✅ 文件的虛擬碼與原碼**行為等價**（含 `band` 的 `red_lo` / `yellow_lo`） |
| **§3.1** 只有 `us10y`/`dxy` 有 valid range | 程式列印所有 spec 的 valid_min/max | ✅ 屬實（`m1b_m2_gap` / `bias_240` / `ndc_signal` 皆 None） |
| **§2.6 C5** `valuation_level` 是死碼 | `grep -rn "valuation_level\s*="` | ✅ **production 0 命中**，5 處全在 `tests/test_dual_verdict_ui.py` |
| **§2.6 C3** `EXPENSIVE_VALUATION_MARKER` 接不住其他 family | 讀 `scorability.py:34,122` + 字串比對 | ✅ 常數值確為 `"超貴"`；`'⛔ 超昂貴'` / `'🔴超過昂貴'` 確實不含子字串「超貴」 |
| **§4.2** `checks` 的 `cv` 被 unpack 但沒渲染 | 讀 `app_render.py:70-72` | ✅ `for cn, cv, cp in ...` 後字串只用 `{cn}` 與 `✓/✗`，**`cv` 完全沒用到** |
| **§4.2** 「合理 3~5%」vs「🔴昂貴價」矛盾 | 讀 `thresholds.py:84` + `section_357_valuation.py:117` | ✅ 屬實（並由本組 §6-C2 進一步擴大） |
| **§5.1** `sharpe_weekly` 回 None、`health_b` 三態 | 讀 `dividend_station.py:191-283` | ✅ 屬實，且 `health_b` 的 `miss_reason` 註解（2026-08-25 稽核更正）也吻合 |
| **§5.6** `calc_liquidity_score` 的 AUM 段 `except: pass` | 讀原碼 | ✅ 屬實 |
| **§6.3 路徑更正**（`exit_signals` 在 `src/compute/scoring/` 不在 `strategy/`） | `find` | ✅ 屬實 —— **`CLAUDE.md §8.2` 的 L2 代表檔列錯了，這份改對了** |
| **§8 的引用標示紀律** | 全文 grep 行動語 + 讀上下文 | ✅ 16 筆行動語全部在反引號內且有引用標示（唯一例外見 §5.1 邊界案例） |
| **§9 的自標** | 逐條讀 | ✅ 未發現「該標而未標」；§6.2 的自標甚至**直接指向本組 C3 要修的那一條** |

---

## §8 我沒查到的（`CLAUDE.md §-2` 規則 6 誠實揭露）

### 8.1 🔴 承重 —— 請優先覆核（後續會有人拿去當前提）

1. **「`finmind_m1m2.parquet` 在 `src/`+`app.py` 內 0 個讀取點」是本組單組 grep 的全稱句。**
   方法：`grep -rn finmind_m1m2 src/ app.py shared/` + 讀 `load_v2_chart_series` 全文。
   ⛔ **沒有涵蓋動態路徑**：字串拼接的檔名（`f"{name}.parquet"`）、`glob`、`os.listdir`、
   `DEFAULT_PARQUET_CACHE_DIR` 的目錄掃描。若有任何一處用變數組檔名，本組掃不到。
   **在第二組驗證前，不得據此宣稱「負值絕對進不了畫面」。**
2. **「`M1B_M2_GAP_DETERIORATION_THRESHOLD` 0 consumer」同樣是單組 grep。** 同上，動態 `getattr`
   （例如 `getattr(signal_thresholds, name)`）掃不到。
3. **§6-C2 的「三套並存」是本組讀 `tab_stock.py` 三個呼叫點推導的，沒有實機跑過一檔 5.0% 的股票。**
   結論「畫面上會同時出現『偏貴』與『合理價』」是**推導**，不是**實測畫面**。

### 8.2 🟡 結構性查不到（沙箱能力限制，不是偷懶）

4. **完全沒有實機 render。** 本沙箱無 Streamlit runtime（每次 import 都出
   `No runtime found, using MemoryCacheStorageManager`），外連被 proxy 403 擋
   （實測 `^TWII` 下載失敗：`CONNECT tunnel failed, response 403`）。
   ⇒ **所有「畫面會顯示 X」的判斷都是讀 render 函式推導的，沒有一張截圖。**
5. **沒有跑任何測試。** 未執行 `pytest`，因此**沒有**驗證兩份文件引用的測試檔
   （`tests/test_c3_layering_guard.py` / `test_scoring_helpers.py` / `test_dual_verdict_ui.py` …）是否真的綠燈。
6. **線上 M1B/M2 的真實值域沒量到。** 紅線 2(d) 說「線上走 `ms1.json`、gap 是 pp 量綱」是
   **讀 `fetch_cbc_m1b_m2` 原碼**得到的，**沒有實際打過 CBC API**（外連被擋）。
   ⇒ 「線上不會出現量綱壞掉的值」**本組沒有證據**，只證明了「沒有守衛」。

### 8.3 🟡 有能力查但本輪沒做（範圍取捨，據實列出）

7. **AST 掃描的 707 筆只細看了 88 筆。** 收斂條件是「判定層 ∧ 涉及可量測物理量」——
   ⇒ **`src/ui/**` 與 `src/data/**` 的 619 筆完全沒逐筆判**。
   `src/data/` 尤其可疑（那是 producer 端，一個 0 會流很遠）。
   ⛔ **§3 的 7 條新報**是「本組看的那 88 筆裡的」，**不是全站窮舉**。
8. **只掃了三種 AST pattern**（`dict.get(k,0)` / `else 0` / `or 0`）。
   **沒掃**：函式預設參數 `=0`、`np.nan_to_num`、`.fillna(method=...)`、`replace(nan, 0)`、
   `int()`/`float()` 對空字串的行為、`defaultdict(int)`、`sum([])==0`。
9. **104 筆引用只做了 31 筆語意複核。** 其餘 73 筆**只驗了「符號存在」**，
   **沒有驗「文件對它的描述對不對」** ⇒ **A 類（存在但語意不符）很可能還有，本組只是沒看到。**
   ⛔ **不得把「只有 2 筆不存在」讀成「其餘 102 筆描述都正確」。**
10. **兩份文件的 §D（不可重建資料）、§A-1/A-3~A-7（fallback 鏈）、§B-1/B-4（Yahoo 雙實作、快取層數）
    本組完全沒驗。** 尤其 **§B-1「Yahoo Finance 有兩套獨立取數實作」** 是個承重宣稱，本輪沒碰。
11. **`INDICATOR_SSOT` 的 §4.3 / §4.4 / §4.6 / §5.5 / §5.7 / §6.1 / §6.3 未逐條複核**
    （財報體檢分級樹、獲利能力 5 指標、選股網涵蓋門檻、集中度、停利門檻、KD 的 `.replace(0,1)`、出場訊號三維）。
    只確認了符號存在。
12. **沒有比對兩份文件與 `S1-1` / `S1-2` / `S2-ENG_SPEC` 等上游材料。**
    ⇒ 兩份自標的【上游材料】那些列，**本組沒有回上游查它們有沒有轉述失真**（A4 是**碰巧**撞到的一例）。

### 8.4 📌 唯讀紀律

- 本 session **未動任何程式碼、未動 `DATA_LINEAGE.md`、未動 `INDICATOR_SSOT.md`、未做任何 git 操作**。
- 唯一寫入：本檔 `scratchpad/STAGE1_AUDIT.md` + `scratchpad/audit/` 下 8 支探針／腳本
  （`p1_fund.py` `p2_m1m2.py` `p2b.py` `p2c.py` `p2d.py` `p3.py` `p3b.py` `ast_zero.py` `extract_refs.py`
  `check_refs.py` `filter_zero.py` 及其 json 輸出），全部在 scratchpad 內、不進 repo。
- 稽核結束時 `git status --short` 仍為空（與開場一致）。
