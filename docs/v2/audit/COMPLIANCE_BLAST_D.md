# 合規丁組 — 改動爆炸半徑與風險評估

> **任務**：不找違規（甲/乙/丙做）。回答「**改這些字串會炸到什麼、安全的施工順序是什麼**」。
> **調查方式**：唯讀。AST 掃描（中文字面出現在 `==` / `in` / `.startswith` / `dict key` /
> `Subscript` 條件位置，全 repo 545+ `.py`，命中 4,320 筆後逐層過濾）＋ grep ＋
> **在直譯器內實跑 production 函式做突變實驗**（不改 repo 任何檔案）。
> **量測日 2026-09-14**；分支 `claude/stock-dashboard-handoff-g9dtm0`；工作區 clean。
>
> ⚠️ **依 `CLAUDE.md §-2` 規則 6 據實標註**：本檔**全部由丁組單組產出，沒有第二組獨立複驗**。
> 凡標 **【實測】** 者是我實際跑過 / grep 命中的事實；凡標 **【單組結論】** 者是我從事實推出的判斷，
> **不得**被引用為「已查證的事實」去支撐下一步。凡標 **【未查證】** 者我根本沒查。
> ⚠️ **本檔會被拿來決定施工順序。漏一個 caller 就會弄壞線上畫面。** 不確定的地方我一律標不確定。

---

## 0. 三句話結論（先看這個）

1. **客戶開的窗口「只改字面、不改行為」，這三個改動點裡有兩個當場踩破窗口。**
   最嚴重的是 **357 估值措辭**：`section_batch_fetcher.py` 有一份 **inline 第四版 357 字面**
   （`'🟢便宜' / '🟡合理' / '🔴昂貴' / '🔴超貴'`），被 `tab_helpers.final_recommendation`
   拿去做 `'便宜' in val → +2 分` 的**加總**。**我實跑證明：只改中文措辭、一個數字沒動，
   組合排行總表的「綜合建議」會從 🟡觀察 靜默翻成 🔴等待。** 沒有例外、沒有紅燈、沒有 log。
2. **殖利率四燈（`shared/thresholds`）的控制流鎖在 emoji，不鎖在中文。**
   `etf_recommendation.py` 讀的是 `'🟢' in val` / `'🔴' in val`。**中文可改，emoji 一個字元都不能動。**
   但同一支函式對配息健康是 `'吃本金' in div_health` —— **那是鎖中文的**，一改就翻判。
3. **「型態目標價」是三者中唯一真正的純字面改動**（0 控制流、0 dict key、0 落地資料），
   但它有 **7 個使用者可見出現點 + 2 條跨頁指路句**，其中一條住在 **L0 共用檔**、
   會經 `st.warning` 印出、**而且同一份字串會被送進 Gemini prompt**。**要改就 7 處一起改**，
   改一半 = 教學頁指路到一個已經不存在的名字（那是 §1 意義上的說謊）。

---

## 1. 逐點爆炸半徑表

### 1.1 改動點 A｜`shared/thresholds.py` 殖利率四燈（L0 SSOT）

**產出處【實測】**
```
shared/thresholds.py:59   return '🟢 強烈買進', 'strong_buy'
shared/thresholds.py:61   return '🔴 獲利了結', 'sell'
shared/thresholds.py:63   return '🟡 適度減碼', 'reduce'
shared/thresholds.py:64   return '⚪ 中性持有', 'neutral'
```

#### production caller（`classify_yield_zone`，全 repo grep，**非測試**）【實測】

| # | 位置 | 取 label 還是 code | 用途 |
|---|---|---|---|
| 1 | `src/compute/etf/etf_helpers.py:118,122`（`yield_valuation_zone`） | **label** | 轉手回傳，本身是第二層 SSOT |
| 2 | `src/ui/tabs/tab_stock.py:703-704` | **code** 只取 `_yld_code` | label 丟棄 |
| 3 | `src/ui/etf/etf_tab_single.py:29,432` | **code** 只取 `_zone_code` | 再查 `_ZONE_UX` dict |

`yield_valuation_zone`（label 版）的下游【實測】：

| # | 位置 | 做什麼 |
|---|---|---|
| 4 | `src/compute/etf/etf_scoring_helpers.py:119` | `_r['valuation_zone'] = yield_valuation_zone(...)` → **寫進 row dict** |
| 5 | `src/ui/etf/etf_tab_grp_compare.py:210` | `'7%估值': r.get('valuation_zone','—')` → **DataFrame 欄值** |
| 6 | **`src/compute/etf/etf_recommendation.py:108-110`** | **⚠️ 控制流** |

#### ⚠️ 控制流：**鎖 emoji，不鎖中文**【實測 + 實跑驗證】

```python
# src/compute/etf/etf_recommendation.py:108-110
val = str(_row.get('valuation_zone') or '')
_cheap = ('🟢' in val) or (sigma_z is not None and sigma_z <= SIGMA_Z_CHEAP)
_rich  = ('🔴' in val) or (sigma_z is not None and sigma_z >= SIGMA_Z_RICH)
```

我實跑 `recommend_etf_action`（不改檔，直接餵不同 `valuation_zone`）：

| 餵進去的 `valuation_zone` | verdict | 估值註解 |
|---|---|---|
| `'🟢 強烈買進'`（現況） | 留下 | `價位偏低,分批加碼時機較佳` |
| `'🟢 殖利率偏高區'`（**只改中文**） | 留下 | `價位偏低,分批加碼時機較佳` ✅ **不變** |
| `'強烈買進'`（**拿掉 emoji**） | 留下 | **（空）** ❌ 註解靜默消失 |
| `'🟩 強烈買進'`（**換一個綠色 emoji**） | 留下 | **（空）** ❌ 同上 |
| `'🔴 殖利率偏低區'`（只改中文） | 留下 | `價位偏高,續抱可、暫緩加碼` ✅ |

→ **結論【單組結論】：中文措辭可改；`🟢` `🔴` 兩個 codepoint 是承重的，動了就是行為變更且無紅燈。**
`🟡`（reduce）與 `⚪`（neutral）**沒有**被判讀，動了無影響。

#### dict key / DataFrame 欄名【實測】
- **不是 dict key**：`etf_tab_single.py:434-453` 的 `_ZONE_UX` 是用 **code**（`'strong_buy'/'neutral'/'reduce'/'sell'`）當 key。
  ⚠️ **反過來要寫死：`code` 一個字都不能改**，改了 `_ZONE_UX[_zone_code]` 當場 `KeyError` 炸掉 ETF 單檔頁。
- **是 DataFrame 欄「值」**（不是欄名）：`etf_tab_grp_compare.py:210` 的 `'7%估值'` 欄。欄名來自
  `shared/etf_ui_labels.ETF_METRIC_LABELS['valuation_zone'] = '7%估值'`，與四燈字面無關。

#### 落地資料【實測】
- **不進 parquet**：`data_cache/` 全目錄 grep 四個字面 → **0 命中**。
- **不進 Google Sheet**：三個 worksheet 的 headers 都是英文（`gsheet_portfolio.py:82,88,499`
  = `name/ticker/lots/avg_price/updated_at`、`name/ticker/updated_at`、
  `cohort/stock_id/name/entry_price/factors/frozen_at`）。
- **進 session_state（僅記憶體、不落盤）**：`etf_tab_grp_compare.py:157` `st.session_state[_cache_key] = rows`，
  rows 帶 `valuation_zone`。跨 session 不保留 → **無新舊資料對不上的風險**。
- `@st.cache_data`：streamlit 以函式 bytecode 入 key，改字面即自動失效 → 無殘留快取問題【單組結論】。

#### 教學卡另一份同字面（**獨立於 SSOT，要一起改否則兩邊打架**）【實測】
```
src/data/core/data_registry.py:693  ('殖利率 ≥ §§YIELD_HIGH§§%', '🟢 便宜價／強烈買進（357 殖利率估值法則）')
src/data/core/data_registry.py:694  (...,                        '⚪ 合理價／中性持有')
src/data/core/data_registry.py:695  (...,                        '🟡 昂貴，適度減碼')
src/data/core/data_registry.py:696  (...,                        '🔴 過貴，獲利了結')
```
渲染路徑：`data_registry.render_edu_card_html()` → `_resolve_edu_rules` → `_esc` → HTML（`tab_edu.py`）。
**純顯示，0 控制流**【實測：AST 掃描 `EDU_GUIDE` 值無任何條件位置命中】。

#### 另外三份「同語意、不同字面」的 357 措辭（**不是同一個 SSOT，別以為改一處就到底**）【實測】
1. `src/ui/etf/etf_tab_single.py:435-453` `_ZONE_UX` 的 `box` / `tc`（ETF 教學脈絡措辭）
2. `src/ui/etf/etf_tab_grp_compare.py:249` column help 字串（`殖利率≥7%🟢強烈買進 / …` 一整句）
3. `src/ui/etf/etf_tab_single.py:518` `_prem_action = '🟢 強烈買進時機'`（**折溢價**的，與殖利率無關，同字面不同語意）

**判定：A 點 ⇒ 中文純字面（✅），emoji 兼控制流（⚠️）。**

---

### 1.2 改動點 B｜`v5_modules.calc_dividend_yield_357` 的 5 個 `msg` / `signal`

**產出處【實測】** `src/compute/strategy/v5_modules.py:357-374`
（`甜甜價`／`高殖利率`／`合理`／`昂貴`／`超貴` 五分支的 `signal` + `msg`；msg 內含
「策略1 存股首選」「可分批布局」「持有但不追高」「建議逢高減碼」）

#### production caller（`calc_dividend_yield_357`，**非測試、非 docstring**）【實測】

| # | 位置 | 用了回傳 dict 的哪些 key |
|---|---|---|
| 1 | `src/ui/views/page_inspect.py:1300-1319` | `est_yield` / `zone_code` / **`signal`** / **`msg`** → 塞 `ValuationReadout` |
| 2 | `src/ui/tabs/stock_sections/section_health_score.py:412-427` | `color` / `est_yield` / **`signal`（`[:12]` 截斷）**；**沒用 `msg`** |

⚠️ `src/ui/tabs/tab_stock.py:148` 只是 **import，本檔沒有呼叫點**【實測：全 repo `calc_dividend_yield_357(`
的 production 呼叫只有上面 2 處】。

#### 控制流【實測】
- `page_inspect.py` 對 `signal` / `msg` **零判讀**：`msg` → `_facts.append(("L2 說明", val.msg))` 原樣透傳；
  `signal` → `_signal_label(val.signal)`。判狀態靠 `zone_code` / `est_yield` / `error`，**不靠中文**。
- `section_health_score.py` 只取 `color` 與 `signal[:12]` 顯示。
- → **B 點的 5 個 msg 本身是純字面。**

#### ⚠️ 但有兩個必須寫死的副作用

**(a) `signal` 被硬截斷 `[:12]`**（`section_health_score.py:427`）。
措辭變長 → 卡片上斷在半個詞。**不是行為變更，但是可見的品質退化**，改文案時必須連同截斷長度一起看。

**(b) `zone_code` 是四個 dict 的 key，一個字都不能改**【實測】：
```
shared/thresholds.py:classify_stock_357_price → 'cheap'/'fair'/'dear'/'overpriced'/'na'
  ↳ v5_modules.py:337                       if zone_code == 'cheap' / 'fair' / 'dear'
  ↳ section_357_valuation.py:92  _TEACHER_LABELS[_code357]   ← KeyError 風險
  ↳ section_357_valuation.py:116 _BOX_LABELS[_code357]       ← KeyError 風險
  ↳ section_psy_checklist.py:115 _code357 in ('cheap','fair')
```

#### ⚠️⚠️ **真正的地雷：另一份 inline 357 字面，而且它接控制流**【實測 + 實跑驗證】

```python
# src/ui/tabs/stock_grp_sections/section_batch_fetcher.py:183-193
val4 = '⚪無股利'
if avg_div4 > 0 and price4 > 0:
    ...
    val4 = '🟢便宜'   # :187
    val4 = '🟡合理'   # :189
    val4 = '🔴昂貴'   # :191
    val4 = '🔴超貴'   # :193
```
`val4` 同時進三條路【實測】：
1. 顯示：`'357評價': val4`（排行總表欄）
2. **`'_val': val4`** → `tab_helpers.final_recommendation`
3. **`valuation_label=val4`** → `tab_helpers.classify_stock_status_lamp`

```python
# src/ui/tabs/tab_helpers.py:100-103   ← 加總，不是顯示
if '便宜' in val:   pts += 2
elif '合理' in val: pts += 1
# src/ui/tabs/tab_helpers.py:175
if valuation_label and ('昂貴' in str(valuation_label) or '超貴' in str(valuation_label)):
    return '🟠 減碼'
```

**我實跑的突變實驗（health=60、多因子=60、trend=多頭，其餘完全不動）：**

| `_val` | `final_recommendation` 輸出 |
|---|---|
| `'🟢便宜'`（現況） | **🟡 觀察** |
| `'🟢低估（殖利率≥7%）'`（只改措辭） | **🔴 等待** ❌ |
| `'🟡合理'`（現況） | **🟡 觀察** |
| `'🟡中性區間'`（只改措辭） | **🔴 等待** ❌ |

| `valuation_label` | `classify_stock_status_lamp` |
|---|---|
| `'🔴昂貴'` / `'🔴超貴'`（現況） | **🟠 減碼** |
| `'🔴偏高區'` / `'🔴溢價區'`（只改措辭） | **⚪** ❌ 減碼燈整個消失 |

→ **這是本次調查最重要的一條：357 措辭在「🏆 個股組合」路徑上是承重字串。
「只改字面」在這裡是假的 —— 它會改排名結論，而且完全靜默。**

#### 落地資料【實測】
- `msg` / `signal` / `val4` 都 **不進** parquet、不進 Google Sheet（同 A 點查法）。
- `val4` 進 `st.session_state['t3_data']['results']`（`section_batch_fetcher.py:368`）——
  記憶體，不落盤。

**判定：B 點的 5 個 `msg` ⇒ 純字面（✅）；但「357 措辭」這個主題 ⇒ 字面兼控制流（⚠️），不在窗口內。**

---

### 1.3 改動點 C｜功能名稱「型態目標價」

#### 全 repo `.py` 出現點逐一判讀【實測，15 處】

| # | 位置 | 使用者看得到？ | 性質 |
|---|---|---|---|
| 1 | `shared/scoring_regime_gate.py:52` | ❌ | module docstring |
| 2 | **`shared/scoring_regime_gate.py:137`** | ✅ | **`notice()` 回傳字串 → `st.warning`** |
| 3 | **`src/ui/tabs/tab_edu.py:779`** | ✅ | **教學頁指路句**「📍 在系統哪裡看」 |
| 4 | `src/ui/tabs/stock_grp_sections/section_batch_fetcher.py:197` | ❌ | 註解 |
| 5 | **`.../section_portfolio_summary.py:148`** | ✅ | **markdown 表格 cell 的跨頁指路**（完整見「🎯 型態目標價」） |
| 6 | `.../section_portfolio_summary.py:163` | ❌ | 註解 |
| 7 | `.../section_portfolio_summary.py:517` | ❌ | docstring |
| 8 | **`.../section_portfolio_summary.py:524`** | ✅ | **`st.markdown('#### 🎯 型態目標價（全組合）')`** |
| 9 | `src/ui/tabs/pattern_targets_ui.py:1` | ❌ | module docstring |
| 10 | `src/ui/tabs/pattern_targets_ui.py:181` | ❌ | docstring |
| 11 | **`src/ui/tabs/tab_stock.py:243`** | ✅ | **`st.expander('🎯 型態目標價（本檔 K 線自動算…）')`** |
| 12 | `src/ui/tabs/tab_stock.py:244` | ❌ | 註解 |
| 13 | `src/ui/tabs/tab_stock_grp.py:45` | ❌ | 註解 |
| 14 | **`src/ui/tabs/tab_stock_grp.py:53`** | ✅ | **`st.text_area` 的 label** |
| 15 | **`src/ui/tabs/tab_stock_grp.py:64`** | ✅ | **`st.caption`** |

→ **使用者可見 7 處、開發者可見 8 處。** 另在 `STATE.md` / `CLAUDE.md` / `PLAN_T4.md` /
`docs/audit-2026-08/*` 有 md 引用（repo 文件，不是畫面）。

#### 控制流【實測】
**0 處。** AST 掃描「中文字面在 `==`/`in`/`.startswith`/dict key/Subscript」全 repo 4,320 筆命中裡，
**「型態目標價」一次都沒有**出現在條件位置。

#### dict key / 欄名【實測】
- **不是欄名**：排行總表那一欄叫 `'型態'`（`section_portfolio_summary.py:359`），不是 `'型態目標價'`。
- **不是 session key**：session key 是 `'_pattern'`、`f"_{prefix}_ov_pattern"`、`'t3_data'`。

#### 落地資料【實測】
無。不進 parquet / Sheet / CSV。

#### ⚠️ 但有三個必須一起看的東西

**(a) 它住在 L0，而且會被送進 LLM prompt。**【實測】
```
shared/scoring_regime_gate.py:137 notice()
  → section_batch_fetcher.py:355  risk_alerts_t3.append(_regime_dec.notice())
  → section_batch_fetcher.py:371  st.session_state['t3_data']['risk_alerts']
  → section_portfolio_summary.py:184  st.warning(alert)            ← 畫面
  → section_ai_portfolio.py:204      '\n'.join(f'⚠️ {_a}' …)      ← 進 Gemini payload
```
改這一句 = 同時改畫面 + 改送給模型的 context。**不是行為變更，但要在交付報告揭露**【單組結論】。

**(b) 兩條指路句是跨頁交叉引用，改一半就變成假指路。**
`tab_edu.py:779`（教學頁指向功能）＋ `section_portfolio_summary.py:148`（表格指向區塊）
＋ `section_portfolio_summary.py:524` / `tab_stock.py:243`（被指向的那兩個標題）——
**四者互為一組，必須同一個 commit 一起改。**

**(c) 千萬不要順手改到「型態的三個判定值」——那是完全不同的東西，而且鎖控制流。**【實測】
```
src/compute/strategy/pattern_targets.py:204,206,208  pattern = "破底翻" / "N字整理" / "型態未明"
  ↳ pattern_targets.py:281   if pattern == "破底翻"
  ↳ pattern_targets.py:418   if pattern == "型態未明"
  ↳ pattern_targets_ui.py:30 _PATTERNS = ("破底翻","N字整理","型態未明")   ← selectbox 選項
  ↳ pattern_targets_ui.py:101 st.session_state[f"_{prefix}_ov_pattern"] = …  ← session 值
  ↳ pattern_targets_ui.py:132,134  if pattern == "破底翻" / "N字整理"
```
**「型態目標價」＝ 功能名（可改）；「破底翻／N字整理／型態未明」＝ 引擎回傳值（不可改）。**
兩者只差三個字，非常容易誤傷。

**判定：C 點 ⇒ ✅ 純字面。三者中唯一完全落在客戶窗口內的。**

---

### 1.4 自行擴充：同型風險、丁組實測找到的其他改動點

> 這一節是我依「產出使用者可見結論字串 → 被 caller 拿去判讀」這個**模式**去掃出來的。
> ⚠️【單組結論 + 未窮舉】：我掃的是 AST 條件位置的中文字面，**沒有**掃 f-string 拼接後才被判讀的情形。

| ID | 字串 | 產出處 | 判讀處 | 判定 |
|---|---|---|---|---|
| **D-1** | `'吃本金'` | `etf_helpers.py:350` `dividend_health_label` | **`etf_recommendation.py:70` `if '吃本金' in div_health:`** | ⚠️ **字面兼控制流** |
| **D-2** | `'留下'/'觀察'/'考慮換'` | `shared/etf_recommendation_thresholds.py:34-37` | **`etf_tab_single.py:181-182` `'留' in _vlabel` / `'換' in` / `'觀察' in`** | ⚠️ 字面兼控制流（只影響卡片框色） |
| **D-3** | 同上 | 同上 | `VERDICT_ICONS` **以顯示字串當 dict key**（`thresholds.py:39-44`） | ⚠️ 字面兼資料（自洽，但外面不得再硬寫） |
| **D-4** | `'便宜'/'昂貴'/'超貴'/'多頭'/'空頭'` | — | `app_ai_service.py:296,299,332,336,338` | ⚪ **production 死碼**（見下） |
| **D-5** | `'吸籌'/'倒貨'` | `shared.macro_compute.analyze_20d_chips_from_df` | `shared/stock_buckets.py:198,200`；`section_chips_20d.py:49,50,78,79,84,85` | ⚠️ 字面兼控制流 |
| **D-6** | `'多頭'/'空頭'/'多箱'` | `classify_trend_4tier` | `tab_helpers.py:104,167`；`section_kline_chart.py:138,141,144,160` | ⚠️ 字面兼控制流 |
| **D-7** | `'瀕死'/'成長'/'新創'` | `financial_health_engine` DNA | `financial_health_engine.py:1115`；`tab_stock.py:1436`；`section_financial_health.py:678` | ⚠️ 字面兼控制流 |
| **D-8** | `'平靜'/'警戒'/'警報'/'極端警報'`、`'極貴'/'便宜'` | `risk_radar` | `risk_radar.py:568,576,588,625,677,679` | ⚠️ 字面兼控制流 |
| **D-9** | `'動作建議'/'燈號'/'建議動作'/'加碼金'/'357評價'/'綜合建議'` | 多處 | **DataFrame 欄名 / dict key**（`etf_calc.py:1074,1118`、`dividend_station_service.py:812,977-1023`、`watchlist_health_service.py:126`、`page_hold.py:1882`、`etf_tab_dividend_station.py:602,636,639`） | ⚠️ **字面兼資料** |
| **D-10** | `act['動作'] == '買進'` | `etf_tab_portfolio.py:864-865` | 同檔 | ⚠️ 字面兼控制流 |

**D-4 的細節值得單獨寫出來，因為它正是憲法 §-2 點名的那種坑**【實測】：
`app_ai_service.generate_ai_comment` 的 `'便宜' in val` / `'多頭' in trend` 分支，
**全 repo 只有 1 個 production 呼叫點**（`section_op_recommendation.py:112`），
而該呼叫點 **:104-105 硬寫 `'val_label': ''`、`'trend': ''`**（檔內註解自陳
「`_357_label2` / `_trend_text2` 從未被定義，故 `dir()` 永遠 False，實質 ''」）。
→ **那五個分支在 production 恆為 False，「🚀 強烈買入 / ✅ 積極買入」那兩句話目前印不出來。**
⚠️ 這一條對突變測試設計很關鍵：**任何針對這段的守衛，如果只驗「函式輸出不含強烈買入」，
就是一個永遠會綠的假護欄** —— 它綠不是因為修好了，是因為那段本來就跑不到。

---

## 2. 測試衝擊清單

> 【實測】全 `tests/`（370 檔、`--collect-only` = **8,341 tests**，`pytest.ini` 有
> `addopts = -m "not slow"`，**25 個檔帶 `@pytest.mark.slow` 預設不跑**）。
> 下表由目標字面 grep + 逐條讀出判定，**逐檔判讀、非窮舉宣稱**【單組結論】。

### (a) 必須跟著改的（不改就紅）

| 檔:行 | assert 內容 | 打到哪個改動點 |
|---|---|---|
| `tests/test_pr_f_audit_residual.py:52` | `assert '強烈買進' in label` | A |
| `tests/test_pr_f_audit_residual.py:58` | `assert '獲利了結' in label` | A |
| `tests/test_pr_f_audit_residual.py:64` | `assert '適度減碼' in label` | A |
| `tests/test_pr_f_audit_residual.py:70` | `assert '中性持有' in label` | A |
| `tests/test_pr_d_etf_ssot.py:115` | `assert '強烈買進' in yield_valuation_zone(7.5, 5.0)` | A |
| `tests/test_pr_d_etf_ssot.py:117` | `assert '獲利了結' in …(2.5, 5.0)` | A |
| `tests/test_pr_d_etf_ssot.py:119` | `assert '適度減碼' in …(4.0, 5.0)` | A |
| `tests/test_pr_d_etf_ssot.py:121` | `assert '中性持有' in …(6.0, 5.0)` | A |
| `tests/test_b1b_stock_math.py:237` | `expected_kw = {"cheap": ("甜甜價","高殖利率"), "fair": ("合理",), "dear": ("昂貴",), "overpriced": ("超貴",)}` | B（signal） |
| `tests/test_b1b_stock_math.py:336` | `for bad in ("超貴","昂貴","甜甜價","合理"): assert bad not in r["signal"]` | B（反向：缺資料不得給結論） |
| `tests/test_b1b_stock_math.py:379` | `assert "甜甜價" in r["signal"]` | B |
| `tests/test_b1b_stock_math.py:374` | `assert "未知" in r["msg"]` | B（若改「配息年數未知」措辭才會紅） |
| `tests/test_h1_scoring_regime_gate.py:372-373` | `for kept in ("健康度","型態"): assert kept in notice` | **C** —— ⚠️ 只釘 `"型態"` 兩字，**不是**「型態目標價」；新名保留「型態」二字即不紅 |
| `tests/test_pr_d_etf_ssot.py:129,131` | `'雙贏' / '吃本金' in dividend_health_label(...)` | D-1 |
| `tests/test_etf_total_return_no_double_count.py:364` | `assert row['dividend_health'] == '🔴 吃本金 -5.0pp'`（**全等**） | D-1 |
| `tests/test_etf_total_return_no_double_count.py:374` | `assert row['dividend_health'].startswith('✅ 雙贏')` | D-1 |
| `tests/test_etf_total_return_no_double_count.py:413` | `assert any('吃本金' in _f for _f in verdict['red_flags'])` | D-1 |

### (b) 改了會變成**假護欄**的（不會紅，但從此不再守任何東西）⚠️ 最危險的一類

> 特徵：**測試自己手寫 fixture 字串**當輸入，而不是跟 production 產出對帳。
> production 改了字面，fixture 沒改 → 測試照綠，但它驗的是一個**系統已經不會再產生的字串**。

| 檔:行 | fixture | 為什麼會變假 |
|---|---|---|
| `tests/test_etf_recommendation.py:28` | `'valuation_zone': '⚪ 中性持有'` | 全檔 12 個 case 的 base row |
| `tests/test_etf_recommendation.py:92` | `_row(composite=0.8, valuation_zone='🟢 強烈買進')` | 驗「便宜 → 加碼註解」。改字面後這條**仍綠**（因為 🟢 還在），但它餵的是幽靈字串 |
| `tests/test_etf_recommendation.py:127` | 同上 | 同上 |
| `tests/test_etf_recommendation.py:27` | `'dividend_health': '✅ 雙贏 +2.0pp'` | D-1 |
| `tests/test_etf_recommendation.py:65,74` | `dividend_health='🔴 吃本金 -3.0pp'` | D-1 |
| **`tests/test_tab_helpers.py:124,131,138,151,157,163`** | `'_val': '便宜' / '合理' / '昂貴'` | **最嚴重**。這 6 條是 `final_recommendation` 唯一的護欄，全部手寫 `'便宜'`。改 `section_batch_fetcher.py:187` 的字面 → **production 加分邏輯掛掉，這 6 條照樣全綠** |
| `tests/test_pr_h4_stock_radar.py:104-163` | `classify_stock_status_lamp(..., '🔴昂貴')` 等 | 同上，8 條全手寫 |
| **`tests/test_p03_inspect_view.py:646`** | `_live_valuation()` 手寫 `signal="🟡 合理（5~7%）"`, `msg="殖利率 6.85%，位於合理區間（97.9~137.0）"` | 檔內註解自稱「走 L2 的字面，本測試不自己編中文」—— **實際上就是自己編的**。B 點改了它不會紅 |
| `tests/test_p03_inspect_view.py:783` | `assert _signal == "合理（5~7%）"`（**全等**） | 驗的是上一格那個手寫 fixture，不是 production |
| `tests/test_symmetry_p3_etf_tracking_error.py:46` | `'valuation_zone': '—'` | 影響小 |
| `tests/test_etf_score_row.py:19` | 只釘欄位名 `valuation_zone` 存在 | 不受影響，但也不會幫你抓到 |
| `tests/test_i2_bias_estimated_disclosure.py:492` | `_BASE = {... "val_label": "", ...}` | D-4 的死碼被測試**照抄了那個空字串** → 那段永遠測不到 |

### (c) 其實在釘別的東西、動不到的

| 檔 | 釘什麼 | 為什麼不受影響 |
|---|---|---|
| `tests/test_pattern_targets_ui_mounted.py`（全檔） | 模組名 / 函式名 / 掛載點 / L2 純度 / 人名黑名單 | **完全不 assert 顯示字串**。C 點的 7 處改完，這 8 條全綠【實測：`grep 型態目標價` 只命中 docstring 與 assert message】 |
| `tests/test_b6a_edu_doc_parity.py:767-781` | tab_edu 必須含 `'頭肩底（Inverse Head & Shoulders）'` 且 120 字內有 `'未實作'` | 釘的是頭肩底章節，不是「型態目標價」。**但改 tab_edu 時別動到那一段** |
| `tests/test_b6a_edu_doc_parity.py:783-795` | 行為斷言：`derive_pattern_levels(...)['pattern'] == '破底翻'` | 釘引擎回傳值（不可改），與功能名無關 |
| `tests/test_f1_edu_token_coverage.py:424,431,555` | `§§TOKEN§§` 取代後不得殘留 `§§` | 只驗 token 機制；`data_registry.py:693-696` 的中文可自由改 |
| `tests/test_user_facing_copy_guard.py`（全檔） | 使用者文案不得含版本號/檔名/模組路徑/函式呼叫/內部標記/修改史 | 只掃「開發者備忘」形狀，不掃投資用語 |
| `tests/test_pr_f_audit_residual.py:86-91` | `yield_valuation_zone(cur,avg) == classify_yield_zone(cur,avg)[0]` | **等價性**斷言，兩邊一起改就一起過 ✅ 這條是好的 |
| `tests/test_b1b_stock_math.py:224-231` | `v5["zone_code"] == classify_stock_357_price(...)[0]` + 三檔目標價同源 | 釘 code 與數字，不釘措辭 ✅ |
| `tests/test_etf_recommendation.py`（門檻類 8 條） | `VERDICT_*` 常數比對 | 走常數，改 constant 值會自動跟上 ✅ |
| `tests/test_symmetry_p3_etf_tracking_error.py:74,78,108` | `v['verdict'] == VERDICT_WATCH` | 同上 ✅ |

### golden / snapshot / AppTest 專項【實測】
- **沒有** 對這三個改動點的字面 golden / snapshot 檔（`tests/` 底下無 `.golden` / `.snap` 檔案；
  帶 `golden` 字樣的 `test_five_bucket_golden.py` 是五桶門檻，與本次無關）。
- **AppTest（`at.run()`）共 35 檔**，其中 25 檔 `@pytest.mark.slow` **預設不跑**。
  對本次三個改動點，我逐檔 grep **沒有找到**以顯示字串做斷言的 AppTest【單組結論，未逐檔全讀】。
  ⚠️ **但 slow lane 預設被 `-m "not slow"` 關掉** —— 施工序裡我把它列成明確的一步，
  否則會出現「本機全綠、CI slow lane 才紅」。

---

## 3. 「字面 vs 行為」判定（逐點，附證據）

| 改動點 | 判定 | 證據 |
|---|---|---|
| **A. `shared/thresholds` 四燈的中文** | ✅ **純字面** | 3 個 caller 中 2 個只取 code；label 唯一的判讀是 `'🟢'/'🔴' in val`（`etf_recommendation.py:109-110`），**實跑驗證改中文不改結論**；不進任何落地資料 |
| **A′. 四燈的 emoji `🟢` `🔴`** | ⚠️ **字面兼控制流** → **不在窗口內** | 實跑：拿掉 🟢 後「分批加碼時機較佳」註解靜默消失 |
| **A″. `zone_code` (`strong_buy`…)** | ⚠️ **字面兼資料** → 不在窗口內 | `_ZONE_UX[_zone_code]`（`etf_tab_single.py:453`）會 KeyError |
| **B. 5 個 `msg`** | ✅ **純字面** | 唯二 caller：`page_inspect` 原樣透傳進 `_facts`；`section_health_score` 根本沒讀 `msg` |
| **B′. 5 個 `signal`** | ✅ 純字面，但**有截斷** | `section_health_score.py:427` `[:12]`；`page_inspect` 走 `_signal_label()` 洗 glyph |
| **B″. 「357 措辭」這個主題（含 `val4`）** | ⚠️⚠️ **字面兼控制流** → **不在窗口內，必須另案** | 實跑：`'🟢便宜'→'🟢低估…'` 讓綜合建議 🟡觀察 → 🔴等待；`'🔴昂貴'→'🔴偏高區'` 讓 🟠減碼 燈消失 |
| **C. 「型態目標價」** | ✅ **純字面** | AST 全 repo 條件位置 0 命中；不是欄名、不是 session key、不落地。唯一注意：`notice()` 會進 LLM prompt（仍是字面） |
| **D-1 `'吃本金'`** | ⚠️ **字面兼控制流** | 實跑：改成「本金侵蝕」→ verdict 由 **考慮換 靜默變 觀察**、red_flags 變空 |
| **D-2/D-3 `'留下'/'觀察'/'考慮換'`** | ⚠️ 字面兼控制流 + 兼資料 | `etf_tab_single.py:181-182` 子字串判色；`VERDICT_ICONS` 以顯示字串為 key |
| **D-5~D-8** | ⚠️ 字面兼控制流 | 見 1.4 表 |
| **D-9** | ⚠️ 字面兼資料 | DataFrame 欄名 / dict key |
| **D-4** | ⚪ 特例：**production 死碼** | 唯一 caller 硬寫 `val_label=''` → 分支恆 False。改不改都無行為差，但**不能拿它當「已修好」的證據** |

---

## 4. 安全改動順序（一次一檔，依 `PROCESS.md §3`「寫入嚴格序列化、一次一檔」）

> 【實測】`PROCESS.md:31` 原文：「並行處理（限唯讀）…**寫入（改 code）仍嚴格序列化，一次一檔**」，
> 且 `:35-36` 明文該半句未被 `CLAUDE.md §-2` / `§-1.5` 鬆動。
> **排序原則**：先跑「零控制流、零跨檔、零測試耦合」的那幾步，用它們驗證流程本身可行；
> 承重的留到最後、或根本不做。

### 前置（不算施工步，但必須先做）
- **P0**：把本檔第 3 節的判定交給**獨立第二組**複驗 —— 尤其 B″ 與 D-1 那兩個「實跑證明」。
  我一組跑出來的結果不該直接當施工前提（§-2 規則 6）。
- **P1**：跑基線並存檔：`python -m pytest tests/ -q`（8,341 tests）＋
  `python -m pytest tests/ -q -m slow`（**slow lane 一定要單獨跑一次**，`pytest.ini` 預設排除它）。
  **沒有綠色基線就不要開始** —— 否則分不清紅燈是你弄的還是本來就紅。

---

### Step 1｜`src/ui/tabs/tab_edu.py` — 教學頁指路句（C 點）
- **改什麼**：`:779-781` 的「在系統哪裡看：…的「型態目標價」區塊」。
- **為什麼排第一**：純 markdown 字串、0 caller、0 控制流、0 測試 assert 它。風險最低。
- **驗**：`pytest tests/test_b6a_edu_doc_parity.py tests/test_strategy_code_wiring.py tests/test_f1_edu_token_coverage.py -q`
- **不過就停在這**：若 `test_b6a::test_head_and_shoulders_is_labelled_as_not_implemented` 紅
  → 你改到了隔壁那個被字面釘住的頭肩底章節。**復原、只改指路句那三行**。
- ⚠️ **但這一步不可以單獨交付**：改完這裡、沒改 Step 2/3 的話，教學頁會指向一個
  畫面上已經不叫這個名字的區塊 —— 那比不改更糟（§1）。**Step 1~3 是一個交付單位。**

### Step 2｜`src/ui/tabs/tab_stock.py` — expander 標題（C 點）
- **改什麼**：`:243` `st.expander('🎯 型態目標價（本檔 K 線自動算：甜蜜價·止損·目標）')`。
- **驗**：`pytest tests/test_pattern_targets_ui_mounted.py tests/test_d1_stock_tab.py tests/test_no_undefined_names.py -q`
  ＋ `pytest tests/ -q -m slow -k "stock or inspect"`
- **停在哪**：`test_pattern_targets_ui_mounted` 紅 → 你動到了函式名 / 掛載點而不只是標題。

### Step 3｜`src/ui/tabs/tab_stock_grp.py` + `.../section_portfolio_summary.py` — 其餘 4 處顯示名（C 點）
- **改什麼**：`tab_stock_grp.py:53`（text_area label）、`:64`（caption）；
  `section_portfolio_summary.py:148`（表格 cell 指路）、`:524`（區塊標題）。
- ⚠️ **這是本序列唯一一步動兩個檔**。若要嚴守「一次一檔」，拆成 3a / 3b 兩步；
  但**兩檔必須在同一個 PR 內合併交付**，否則 `:148` 的指路會指向舊名。**我的建議：拆步、合 PR。**
- **驗**：`pytest tests/test_b5b_stock_grp.py tests/test_pattern_targets_ui_mounted.py -q`
  ＋ `pytest tests/ -q -m slow -k "grp or portfolio"`
- **停在哪**：`test_b5b_stock_grp` 紅 → 你動到了 `'型態'` 欄名（`:359`）而不是標題。

### Step 4｜`shared/scoring_regime_gate.py` — `notice()` 內的功能名（C 點，L0）
- **改什麼**：`:137` 的「健康度／趨勢／357／出場訊號／**型態目標價**不吃 regime」。
- **為什麼排在 C 的最後**：它是 L0、有測試釘、而且**同一份字串會進 Gemini prompt**。
- **驗**：`pytest tests/test_h1_scoring_regime_gate.py tests/test_i1_ai_qa_regime.py -q`
- **停在哪**：`test_notice_says_what_still_works`（`:371-373`）紅
  → 新名沒有保留「**型態**」兩字。**這是刻意的護欄，不要去改測試**，改你的新名。
- **交付報告要寫**：這句話同時出現在 `st.warning` 與送給模型的 context（`section_ai_portfolio.py:204`）。

### ✅ **Step 1~4 做完 = 改動點 C 全部結案。到這裡是一個乾淨的可交付單位。**

---

### Step 5｜`src/compute/strategy/v5_modules.py` — 5 個 `msg`（B 點，**只改 msg，不碰 signal**）
- **改什麼**：`:359`（存股首選）、`:366`（可分批布局）、`:369`（持有但不追高）、`:373`（建議逢高減碼）。
- **不改什麼**：**`signal` 一個字都不要動**（`:357/361/365/368/371`）——
  `test_b1b_stock_math.py:237,336,379` 三處直接釘 signal 的關鍵詞，動了要連測試一起改，
  而那正是把護欄改軟的典型路徑。**msg 與 signal 分兩批，本步只做 msg。**
- **驗**：`pytest tests/test_b1b_stock_math.py tests/test_p03_inspect_view.py -q`
  ＋ `pytest tests/ -q -m slow -k inspect`
- **停在哪**：`test_unknown_years_do_not_claim_instability`（`:374` `assert "未知" in r["msg"]`）紅
  → 你把「配息年數未知」那段一起改掉了。**那是 §1 的誠實揭露，改回來。**
- **交付報告要寫**：`section_health_score.py:427` 有 `signal[:12]` 截斷；本步沒動 signal 所以不受影響，
  但**下一批若要動 signal，必須連截斷一起評估**。

### Step 6｜`src/data/core/data_registry.py` — 教學卡四段判讀（A 點的顯示面）
- **改什麼**：`:693-696` 四行 verdict 文案的中文。
- **不改什麼**：`§§YIELD_HIGH§§` 等 token、以及每行開頭的 emoji。
- **驗**：`pytest tests/test_f1_edu_token_coverage.py tests/test_user_facing_copy_guard.py tests/test_data_registry_panel.py -q`
- **停在哪**：`test_f1` 報 `§§` 殘留 → token 被你改壞了。

### Step 7｜`shared/thresholds.py` — 四燈中文（A 點，**L0、最後做**）
- **改什麼**：`:59/61/63/64` 四個 return 的**中文部分**；順手改 `:11,13,22,24,44-47,82` 的 docstring/註解。
- **⛔ 絕對不改**：`🟢` `🔴`（承重，見 1.1 實測表）、`'strong_buy'/'sell'/'reduce'/'neutral'/'na'`（dict key）。
  `🟡` `⚪` 未被判讀，但**一併不動**，理由是留一致性、不製造第二套規則。
- **必須同批改的測試**（(a) 類，4+4 條）：`test_pr_f_audit_residual.py:52,58,64,70`、
  `test_pr_d_etf_ssot.py:115,117,119,121`。
- **必須同批改的 fixture**（(b) 類假護欄）：`test_etf_recommendation.py:28,92,127`。
  ⚠️ **不改這三處 = 測試全綠但已不守任何東西**。改它們不是「為了讓測試過」，
  正好相反 —— 是為了**讓它們繼續守得住**。
- **驗**：`pytest tests/test_pr_f_audit_residual.py tests/test_pr_d_etf_ssot.py tests/test_etf_recommendation.py tests/test_etf_helpers.py tests/test_etf_total_return_no_double_count.py tests/test_symmetry_p3_etf_tracking_error.py -q`
  ＋ **全量** `pytest tests/ -q` ＋ `pytest tests/ -q -m slow`
- **停在哪**：`test_etf_recommendation::test_cheap_valuation_adds_add_timing_note` 紅
  → 你動到了 emoji。**立刻停手，這已經是行為變更，超出客戶開的窗口。**

### Step 8｜`src/ui/etf/etf_tab_single.py` / `etf_tab_grp_compare.py` — ETF 頁的同字面複本
- **改什麼**：`etf_tab_single.py:435-453`（`_ZONE_UX` 的 `box`/`tc` 值）、`:518`（折溢價那句）；
  `etf_tab_grp_compare.py:249`（column help 整句）。
- **不改什麼**：`_ZONE_UX` 的 **key**。
- **驗**：`pytest tests/test_etf_single_verdict_card.py tests/test_etf_grp_compare_declutter.py tests/test_etf_tab_imports.py -q`
- **為什麼排最後**：它是 A 點的「一致性收尾」—— Step 7 改完不改這裡，同一套殖利率結論在
  ETF 單檔頁與多檔頁會用兩種措辭。

---

### ⛔ **不排進本序列的（超出客戶窗口，必須另案立項）**

| 項目 | 為什麼不能放進「只改文字」的窗口 |
|---|---|
| `section_batch_fetcher.py:183-193` 的 `val4` 四個字面 | **實跑證明會改排名結論**（B″）。要改就得**同時**改 `tab_helpers.py:100-103,175` 的判讀式，那是改行為，不是改文字 |
| `etf_helpers.py:350` 的 `'吃本金'` | **實跑證明會翻 verdict**（D-1） |
| `etf_recommendation_thresholds.py:34-37` 的 `VERDICT_*` | `etf_tab_single.py:181-182` 子字串判色 + `VERDICT_ICONS` 以它為 key（D-2/D-3） |
| `pattern_targets.py:204-208` 的 `破底翻/N字整理/型態未明` | `==` 控制流 + selectbox 選項 + session 值（1.3(c)） |
| 四燈的 emoji、所有 `zone_code` / `VERDICT_*` 常數值 | 同上 |
| D-5~D-10 | 同上 |

**這些的正確做法（給另案用，本批不做）【單組結論】**：把「判讀」與「顯示」分家 ——
判讀改吃 **code**（`zone_code` / `'cheap'` / `red_flag` 旗標），顯示層再把 code 映成中文。
`shared/thresholds.classify_yield_zone` 的 docstring 自己就寫了這個政策：
「caller 需要不同 UX 措辭…可基於 **code** 做下游 UX 映射」——
**問題是 `etf_recommendation.py` 沒照做，它去讀 label 了。**

---

## 5. 突變測試設計（v3 §03-1「拔掉修復邏輯必須轉為紅燈」）

> **本階段禁止寫 code，以下只給設計。**
> 目標檔（建議）：`tests/test_compliance_wording_guard.py`。
> house style 直接沿用 **`tests/test_user_facing_copy_guard.py`**（那是本 repo 同類守衛的最佳範本，
> 它已經有「守衛的守衛」＋「反向不誤判」＋「掃描面不得為空」三件套）。

### 5.1 掃描面：**掃資料結構的值，不掃整個檔案**

理由照抄 `test_user_facing_copy_guard.py` 檔頭的判讀：掃整檔會把註解、dict key、
內部常數名一起掃進來 → 逼人為了讓測試綠而去刪有用的註解。

建議的掃描面分三類，**每一類都要能指出「這個值真的會被渲染」的證據**：

| 類 | 掃什麼 | 渲染證據【實測】 |
|---|---|---|
| **①  函式輸出** | `classify_yield_zone(cur, avg)[0]` 對一組**覆蓋全分支**的輸入；`calc_dividend_yield_357(...)` 的 `msg` / `signal` | `etf_tab_grp_compare.py:210` 欄值；`page_inspect.py:1883` `_facts`；`section_health_score.py:427` |
| **② 資料結構值** | `EDU_GUIDE[*].how_to_read`（沿用既有 `_EDU_RENDERED_FIELDS`）、`ETF_METRIC_LABELS`、`VERDICT_ICONS` 的 key | `data_registry.render_edu_card_html()` 逐欄 `_esc()` 注入 HTML |
| **③ 原始碼字面（AST，最後手段）** | `src/ui/**` 裡**傳給 `st.markdown/caption/info/warning/metric/expander`** 的字串常數 | AST 只看 `ast.Call` 的實參 —— **天然看不到註解與 docstring**（照抄 `test_b6a` 的設計原則） |

⚠️ **③ 的射程必須明講。** `test_views_no_unverified_universal_claims.py` 檔頭記載
「只掃 `src/ui/views/**`，不掃 `src/ui/tabs/` / `src/ui/etf/` —— 那是客戶明令**本批**不得修改的舊版 Tab，
掃了只會製造**改不了的紅燈**，而一支沒人能修綠的守衛最後一定會被 `-k` 掉或被加白名單」。
**那句「本批」指的是 2026-09-07 的 IA v2 批，不是這次的合規窗口**【實測：該檔頭日期】。
→ **這次的射程要含不含 `tabs/` / `etf/`，是總管要對客戶確認的範圍問題，不是我能代決的**（§8.4 step 4）。
我的建議【單組結論】：**含**，因為合規窗口的整個意義就在舊 Tab 的文案；
但**必須先確認客戶那條「舊 Tab 不得修改」的限制是否已被本次窗口取代**。

### 5.2 檢出規則：**登記制，不要啟發式**

沿用 `test_views_no_unverified_universal_claims.py` 的 REGISTRY 設計，而不是
`test_user_facing_copy_guard.py` 的純 regex —— 理由（照抄那支檔頭，三條都成立）：
1. 啟發式擋不住換句話說的人（`強烈買進` → `強力買進` → `積極買進` → …）；
2. 啟發式方向也錯（「附近有『非投資建議』四個字就放行」是一個**可以被隨手滿足**的條件）；
3. 登記制強迫**逐句判讀一次**，並把判讀留成白紙黑字給下一個人複查。

**每一條命中必須登記成一筆**，欄位：
`origin`（來源識別，例：`classify_yield_zone(7.0)[0]`）、`snippet`（正規化後的字面特徵，
**≥10 字、不寫行號** —— `CLAUDE.md §8.2.A.0` 規則 1）、`kind`、`why`。
`kind` 只有兩種：
- `ALLOWED` — 已判讀為不構成合規問題（例：`⚪ 未評估`、`資料不足`、`—`）；
- `PENDING` — 尚未處理的違規用語 → **紅燈**。
**不留 `# noqa` 之類的行尾逃生口**（`test_views_no_unverified_universal_claims.py` 檔頭：
「**留但書等於留引用點**」）。

**正規化**（`_normalize`）必做：去空白、去 `*`、去反引號、去各式引號括號、**去 emoji**。
理由【實測】：`etf_tab_grp_compare.py:249` 寫的是 `殖利率≥7%🟢強烈買進`（無空白、夾 emoji），
`etf_tab_single.py:435` 寫的是 `🟢 <b>強烈買進（特價）</b>`（夾 HTML tag）——
**使用者眼睛看到的一模一樣，字面 grep 卻掃不到**。

### 5.3 ⚠️ 怎麼確保它不是「永遠不會失敗的假護欄」

本 repo 已經被這種東西咬過至少三次【實測，全部有檔可查】：
- `CLAUDE.md §-2` 記載：235 燈缺資料偵測 `weekly_close is None` 在 production **恆為 False**（死碼），
  commit message 卻宣稱「順帶修掉」；
- `tests/test_financial_health_missing_data.py:625-635`：`oi_state == FIELD_ABSENT` 恆 False，
  因為 fetcher 查無回 `0.0`；
- `tests/test_b2b_pcr_scale.py:16,93`：PCR 沒換算 → `126.80 > 1.5` **恆真**，曝險恆 −10；
- **本次我自己新發現的第四例**：`app_ai_service.py:296-338` 的 `'便宜' in val`，
  唯一 caller 硬寫 `val_label=''`（`section_op_recommendation.py:104`）→ **五個分支恆 False**。

→ 因此本守衛**必須自帶四道自我證明**，缺一條就是假護欄：

**(D1) 守衛的守衛 — 正樣本必須被抓到。**
用**真的踩過的字串**當樣本（`'🟢 強烈買進'`、`'建議逢高減碼'`、`'策略1 存股首選'`、
`'可分批布局，勿一次梭哈'`、`'積極買進區'`、`'可大膽買進，股息都進口袋'`），
`assert _scan(sample)` 非空。樣本**寫死在測試檔內**，不從 production 讀 —— 否則
production 改了樣本也跟著變，守衛就永遠抓不到東西。
（範本：`test_user_facing_copy_guard.py:135-147`）

**(D2) 反向守衛 — 合法文案不得被誤判。**
樣本要包含那些**長得很像違規但其實是誠實揭露**的句子，例如
`'⚠️ 依既有評分綜合研判、非投資建議;完整細節見下方各面板。'`（`etf_tab_single.py:190` 實際字串）、
`'⚪ 未評估'`、`'無股價，357 殖利率法則不適用（不以 0% 代替，避免誤判為超貴）'`。
沒有這一條，守衛會逼人把**有價值的警語整段刪掉**。
（範本：`test_user_facing_copy_guard.py:150-161`）

**(D3) 掃描面非空 — 欄位改名讓守衛靜默失效，是最糟的失敗模式。**
`assert` 掃到的字串段數有下界（例：函式輸出 ≥ 9 段、`EDU_GUIDE` ≥ 100 段、AST 實參 ≥ N 段），
且**掃不到檔案 / 目錄不存在 / `ast.parse` 失敗一律 `AssertionError`，不 skip、不靜默過**。
（範本：`test_user_facing_copy_guard.py:164-176` ＋ `test_views_no_unverified_universal_claims.py` 檔頭
「一支永遠綠的守衛比沒有守衛更危險」）

**(D4) ⭐ 可達性證明 — 「這個字串真的會被印出來」必須被斷言，不能靠相信。**
這是專門擋 D-4 那一類坑的，也是我認為**本設計最不可省的一條**。做法二選一：
- **對函式輸出**：斷言**分支可達** —— 對 `calc_dividend_yield_357` 餵**真的會走到那個分支**的輸入
  （例 `price=100, avg_div=8, div_years=5` → 必走 `cheap`+stable），再驗輸出字串。
  這樣「那段是死碼」會當場現形（輸出不含預期字面 → 紅）。
- **對只在 UI 出現的字面**：斷言它出現在 **`st.*` 的實參位置**（AST），
  而不是「出現在這個 `.py` 檔裡」。後者會把註解、docstring、被 `if False` 包住的死碼一起算成「有印」。

**(D5) 加碼建議：把「拔掉修復會不會紅」寫成一條真的測試。**
`tests/test_b2b_pcr_scale.py:325-345` 有現成寫法：把**舊的（違規的）原始碼字面**
合成成一個字串餵給掃描器，斷言它**會被抓到**；再合成一個「只是在註解/docstring 裡提到舊寫法」的樣本，
斷言它**不會**被抓到。這等於在測試裡直接做了一次突變，且不必真的去改 production。
（`test_b2b_pcr_scale.py:342` 的 `test_guard_not_fooled_by_comments_and_docstrings` 就是這個。）

### 5.4 這支守衛**不該**做的事（防它變成另一個問題）

1. **不要用「全 repo 中文字面黑名單」** —— `'買進'` 兩個字在 `etf_tab_portfolio.py:864`
   是 `act['動作'] == '買進'` 的**控制流值**，在 `data_loader_inst_fetchers.py:53` 是
   **上游 TWSE 欄名解析**（`'買賣超' in k`）。掃到它們只會製造改不了的紅燈。
   → **射程要排除 L1 的欄名解析與所有控制流值**，並在檔頭寫清楚為什麼。
2. **不要斷言「一定含免責聲明」** —— 那是可以被隨手滿足的條件（D2 的反面），
   下一個人只要在違規句旁貼一句「非投資建議」就綠了。
3. **不要把它接到 `src/compute/**` 的 verdict 常數上** —— 那些是控制流值（1.4 表），
   守衛紅了只有兩條路：改行為（超出窗口）或加白名單（守衛自廢）。

---

## 6. 丁組自己的盲點（不要當成「全都查過了」）

1. **「牴觸只有上述這些」是我單組窮舉的全稱句，沒有第二組驗過。** 尤其：
   AST 掃描只看**字串常數出現在條件位置**；**f-string 拼接後才被判讀**、
   **常數先存進變數再比對**、**`.format()` / `%` 拼出來的字面**，我的掃描器**掃不到**。
2. **AppTest（35 檔，25 檔 `slow` 預設不跑）我沒有逐檔全讀**，只做了 grep。
   「沒有 AppTest 以顯示字串斷言」這句是【單組結論】，請據此打折。
3. **`mcp_server/` / `infra/` / `tools/` / `docs/` 我完全沒掃。**
   若有第二個介面（MCP tool 回傳、推播訊息）複製了這些字面，本檔看不到。
   ⚠️ `src/compute/notify/`（推播）我只掃到 `signal_message.py:86`、`ai_judgment.py:53`
   兩處控制流，**沒有**逐檔確認推播文案是否含同一批用語。
4. **我沒有跑全量測試。** 只跑了本檔點名的 6 個檔（229 passed / 1.09s）＋
   4 個檔（118 passed / 1.25s）＋ `--collect-only`（8,341 tests）。
   **全量綠不綠、slow lane 綠不綠，我不知道。** 施工前的 P1 基線必做。
5. **「客戶明令舊版 Tab 不得修改」那條限制現在還算不算數，我沒有能力判定。**
   它寫在 `test_views_no_unverified_universal_claims.py` 檔頭（2026-09-07 那一批）。
   本次合規窗口若涵蓋 `src/ui/tabs/` 與 `src/ui/etf/`，**那是範圍問題，依 `CLAUDE.md §8.4 step 4`
   要由總管附推薦方案送客戶拍板**，不該由丁組默默假設。
6. **`data_cache/` 我是用 `grep -rl` 掃的**，parquet 是二進位，**中文若經壓縮編碼我可能掃不到**。
   「四個字面不在 parquet 裡」這句的信心來自另一條獨立證據（Google Sheet / parquet 的
   headers 都是英文欄、且 `PICK_SNAPSHOT_HEADERS` 實測不含任何 verdict 欄），
   **不是**來自 grep 本身。
