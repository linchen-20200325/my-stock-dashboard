# 合規戊組｜控制流獨立複驗

> **組別**：戊組（獨立複驗）　**日期**：2026-09-14　**基準 commit**：`fab88a7`
> **紀律聲明**：本組**未讀取**丁組（或任何其他組）的報告，未詢問其成員。
> 全部結論由本組自建方法獨立產出。與他組一致與否，本組**不知情**。
> **repo 未被修改**：全程 `git status --porcelain` 為空（報告末尾附最終確認）。
> 所有突變實驗都在 scratchpad 的 hardlink 副本內進行。

---

## 0. 三個改動點的判定（TL;DR）

| # | 改動點 | 判定 | 一句話理由 |
|---|---|---|---|
| **1** | `shared/thresholds.py` 殖利率四燈**只改中文、保留 emoji + code** | ⚠️ **字面兼控制流 —— 但承重的是 emoji，不是中文** | 唯一的下游判斷式讀的是 `'🟢' in val` / `'🔴' in val`（`etf_recommendation.py:110-111`）。**照題目給的約束（保留 emoji）改中文 → 實測 80 組零差異。** 但這條的危險不在「能不能改」，而在**護欄裝反了**（見 §1.4）→ 仍須列為**條件放行**，不得當成「純字面」無腦放行。 |
| **2** | `v5_modules.calc_dividend_yield_357` 的 `signal`/`msg`，以及「其他地方是否另有 357 字面複本」 | ⚠️ **字面兼控制流（確認命中，且比預期嚴重）** | (a) 題目懷疑的「UI 層自己 inline 一份」**實際存在**：`section_batch_fetcher.py:183-193` 的 `val4 = '🟢便宜'/'🟡合理'/'🔴昂貴'/'🔴超貴'`，**四個下游拿它做判斷**，實測改中文會改掉「最終建議」「操作狀態燈」「汰弱名單」「AI 建議句」。(b) `calc_dividend_yield_357` 自己的 `signal` 雖然**沒有**被任何 production 判斷式比較，但它的**格式**（`<emoji><半形空格><中文>`）被 `page_inspect._signal_label()` 依賴 —— 少一個空格，訊號頻道**靜默消失**。 |
| **3** | 功能名稱「型態目標價」 | ✅ **純字面（在本 repo 全庫範圍內）** | 12 處 `.py` 出現全部是 docstring / 註解 / `st.markdown`·`st.expander`·`st.caption`·`st.text_area` 的顯示參數 / assert **訊息**（非 assert 條件）。**零** 比較式、**零** dict key、**零** DataFrame 欄名、**零** session_state key、**零** 落地檔。實測突變全庫 8,344 測試只紅 1 條（且那條是真護欄，見 §3.3）。 |

---

## 1. 方法（三層，全部自建）

我刻意**不**沿用「grep 關鍵字」，因為 grep 無法區分「這個字在 `if` 裡」和「這個字在 `st.markdown` 裡」——
而這正是本次要判的東西。三層如下。

### 1.1 靜態層：AST 語法角色分類器

自建 `eg/e_ast.py`：對全 repo **726 個 `.py` 檔**（0 parse error）建 parent-chain，
把每一個**含中文或 emoji 的 `str` 字面**依其**語法位置**打標籤：

- `COMPARE[Eq/NotEq/In/NotIn/Lt/...]` — 出現在 `ast.Compare` 的任一 operand
- `IN_TEST:If / While / IfExp / comprehension / assert` — 位於判斷式子樹內（往上走 parent 直到遇到 statement）
- `DICT_KEY` — `ast.Dict` 的 key
- `SUBSCRIPT_KEY:<被索引的物件>` — `x['中文']`（DataFrame 欄名 / session_state key 都會落這裡）
- `CALL_ARG:.startswith/.endswith/.find/.isin/.get/.replace/...`
- `KWARG:<參數名>`、`MATCH_CASE`、`IN_LAMBDA`
- **docstring 與裸 `Expr` 字串主動排除**（避免把註解當成程式行為）

第二支 `eg/fate.py` 做「單一字面的命運追蹤」：**不排除** docstring，
對指定子字串列出**每一個** Constant 節點的完整 parent 鏈 + 所在函式名，確保沒有東西被靜默丟掉。

**普查結果（量測日 2026-09-14，本組單組掃描）**：

```
含中文/emoji 且落在有語法意義位置的字面 : 9,561
  其中 production（非 tests/）             : 4,505
  ** production 中「直接參與判斷式」      :   769 處 **
  production 中文 dict key                : 1,206 處
  production 中文 subscript key（含 df 欄名）:  481 處
```

熱點檔前 5：`data_loader.py`(74) / `leading_indicators.py`(46) / `etf_fetch.py`(43) /
`tab_stock.py`(38) / `etf_tab_portfolio.py`(29)。
→ **「中文字串當控制流」在本 repo 不是個案，是系統性寫法。** 合規窗口的每一筆都必須逐筆驗，不能類推。

### 1.2 資料面：落地 / 傳輸 schema 實測

- **parquet 全掃**（14 個檔）：欄名**全部 ASCII**；`forward_test/picks.parquet` 的
  `factors` 欄實際內容為 `pe_low,eps_high,shortage,rs_leader,trend`（ASCII code，非中文）。
- **Google Sheets header 實測**：`gsheet_portfolio.py:82/88/499` →
  `['name','ticker','lots','avg_price','updated_at']` / `['name','ticker','updated_at']` /
  `['cohort','stock_id','name','entry_price','factors','frozen_at']` —— **全 ASCII**。
- **session_state key**：用兩種獨立方法查 ——
  (a) AST 的 `SUBSCRIPT_KEY:st.session_state` 標籤；(b) `grep "session_state\[['\"][^'\"]*[一-鿿]"`。
  **兩法都是 0 命中 → 全 repo 沒有任何一個 session_state key 含中文。**
- **非 `.py` 檔**（json/toml/yml/yaml/html/js/csv）掃三個改動點的字面 → **0 命中**。

### 1.3 動態層：直譯器內實跑 production 函式 + 全庫突變實驗

兩種：
1. **直接餵值比對**：import production 函式，用原字串跑一次、改寫字串跑一次，逐欄比對回傳。
2. **突變實驗（本組的主要武器）**：用 `cp -al`（hardlink）把 repo 複製到 scratchpad，
   **只斷開要改的那一個檔的 hardlink**再改它，然後在副本內跑**完整 8,344 項測試套件**。
   另建**未突變對照組**跑同一套，用來把「sandbox 假陽性」扣掉。
   → 這回答的是「**如果有人改錯了，CI 會不會抓到？**」
   對照組實測有 2 條固定紅（`test_deprecation_honesty::test_accepted_table_has_no_stale_entries`、
   `test_sector_heatmap_universe_single_source::...test_the_one_place_is_l0`），
   **與突變無關**（未突變的對照組也紅），以下一律扣除後報數。

---

## 2. 改動點 1｜殖利率四燈（`shared/thresholds.py`）

### 2.1 這四個字面往哪裡去（完整資料流，逐點附 file:line）

`shared/thresholds.py:59/61/63/64`
```python
    if cur_yield >= YIELD_HIGH:  return '🟢 強烈買進', 'strong_buy'   # :59
    if cur_yield <= YIELD_LOW:   return '🔴 獲利了結', 'sell'         # :61
    if cur_yield <= YIELD_MID:   return '🟡 適度減碼', 'reduce'       # :63
    return '⚪ 中性持有', 'neutral'                                    # :64
```

**丟掉 label、只取 code 的 caller（＝改中文對它們完全無感）**：
- `src/ui/etf/etf_tab_single.py:432` — `_, _zone_code = classify_yield_zone(...)` → `_ZONE_UX[_zone_code]`（`:455/:467`）
- `src/ui/tabs/tab_stock.py:704` — `_, _yld_code = classify_yield_zone(_cur_yld)`

**會把 label 傳下去的唯一一條鏈**：
```
shared/thresholds.py:59-64          classify_yield_zone() → label
  → src/compute/etf/etf_helpers.py:122   yield_valuation_zone() 只回 label（code 被丟掉）
    → src/compute/etf/etf_scoring_helpers.py:119   _r['valuation_zone'] = <label>
      ├─→ src/compute/etf/etf_recommendation.py:108-111   ★ 唯一判斷式
      └─→ src/ui/etf/etf_tab_grp_compare.py:210          DataFrame 欄 '7%估值'（純顯示）
```

★ 那個唯一判斷式（`etf_recommendation.py:108-111`）：
```python
val = str(_row.get('valuation_zone') or '')
_cheap = ('🟢' in val) or (sigma_z is not None and sigma_z <= SIGMA_Z_CHEAP)
_rich  = ('🔴' in val) or (sigma_z is not None and sigma_z >= SIGMA_Z_RICH)
```
**它只看 emoji，不看中文。**

`etf_tab_grp_compare.py:210` 那條路我另外查了「是不是被 Styler 依字串上色」：
本 repo 唯一的 `df.style.map` 在 `src/ui/etf/etf_tab_dividend_station.py:93`，
`subset=("健檢","財報體檢","建議動作")` —— **不含 `'7%估值'`**，且 `_bg` 判的也是 `🔴`/`🟡`（`:87-91`）。

### 2.2 動態實證（直譯器內實跑，`eg/dyn_cp1.py`）

```
=== B. recommend_etf_action: 原 label vs 改寫中文(emoji 保留) ===
  compared 80 rows, diffs=0

=== C. 若 emoji 也被改掉（反例／對照組）===
  拿掉 emoji 後 diffs=10 / 80  <= 證明 emoji 才是承重的
```
（80 組 = 5 種 zone × 4 種 composite × 4 種 sigma_z）

### 2.3 全庫突變實驗

**實驗 A — 照題目的約束改（保留 emoji，只改中文）**：
`'🟢 強烈買進'→'🟢 現在很划算'`、`'🔴 獲利了結'→'🔴 現在偏貴，可賣一些'`、
`'🟡 適度減碼'→'🟡 有點貴，減一點'`、`'⚪ 中性持有'→'⚪ 不上不下，續抱'`

→ 全庫 **5 條真紅**（扣除 2 條 sandbox 假陽性）：
```
tests/test_pr_d_etf_ssot.py::TestEtfHelpersSSOT::test_yield_valuation_zone_behavior
tests/test_pr_f_audit_residual.py::TestU8_ClassifyYieldZone::test_strong_buy_at_7pct
tests/test_pr_f_audit_residual.py::TestU8_ClassifyYieldZone::test_sell_below_3pct
tests/test_pr_f_audit_residual.py::TestU8_ClassifyYieldZone::test_reduce_3_to_5
tests/test_pr_f_audit_residual.py::TestU8_ClassifyYieldZone::test_neutral_5_to_7
```
這 5 條是**真護欄**（它們實際呼叫 production 函式），是**文案鎖**：
`tests/test_pr_d_etf_ssot.py:115-121`、`tests/test_pr_f_audit_residual.py:52/58/64/70`。
→ **改中文必須同 PR 更新這 5 條**，否則 CI 紅。

**實驗 B（反例）— 改錯的改法：中文一字不動，只拿掉 emoji**：
→ 全庫 **0 條真紅**。

### 2.4 ⚠️ 本點最重要的發現：**護欄裝反了**

| 改法 | 實際行為變更 | CI 抓得到嗎 |
|---|---|---|
| 只改中文（保留 emoji） | **無**（80/80 相同） | **會紅 5 條** |
| 只拿掉 emoji（中文不動） | **有**（10/80 不同，加碼/減碼時機註解翻掉） | **0 條紅** |

**測試鎖住了不重要的那一半，放生了重要的那一半。**
這代表：合規窗口若在此改字，**CI 的綠燈不能當作「沒改壞」的證據**——
它只證明「你沒動到被鎖的中文」，完全不證明「emoji 還在」。

### 2.5 判定與放行條件

⚠️ **字面兼控制流 → 條件放行，不是無條件純字面。**
**准改的前提（三條同時滿足，缺一不可）**：
1. `'🟢'` `'🔴'` `'🟡'` `'⚪'` 四個 emoji **原封不動**（`etf_recommendation.py:110-111` 只認它們）；
2. 第二個回傳值（`strong_buy`/`sell`/`reduce`/`neutral`/`na`）**原封不動**；
3. 同 PR 更新 `tests/test_pr_d_etf_ssot.py:115-121` 與 `tests/test_pr_f_audit_residual.py:52/58/64/70`。
**另建議（超出窗口、屬另案）**：補一條「emoji 不得從 label 消失」的護欄，把裝反的護欄補正。

---

## 3. 改動點 2｜357 估值措辭

### 3.1 ★ 題目的懷疑成立：UI 層確實另有一份 inline 複本

`src/ui/tabs/stock_grp_sections/section_batch_fetcher.py:183-193`（AST 確認：**在 `run_batch_fetch` 函式體內**）
```python
val4 = '⚪無股利'                       # :183
if avg_div4 > 0 and price4 > 0:
    ch4, fa4, de4 = avg_div4/YIELD_HIGH_DEC, avg_div4/YIELD_MID_DEC, avg_div4/YIELD_LOW_DEC
    if   price4 <= ch4: val4 = '🟢便宜'   # :187   ← 注意：emoji 與中文之間**沒有空格**
    elif price4 <= fa4: val4 = '🟡合理'   # :189      （與 v5_modules 的 '🟢 甜甜價' 格式不同）
    elif price4 <= de4: val4 = '🔴昂貴'   # :191
    else:               val4 = '🔴超貴'   # :193
```
它**不走** `classify_stock_357_price`，而是自己再算一次三檔目標價 —— 是第二份實作，不只是第二份字面。

`val4` 的四個去向（同檔）：
- `:261` → DataFrame 欄 **`'357評價'`**
- `:268` → **`'_val'`**
- `:297` → `classify_stock_status_lamp(..., valuation_label=val4)`

### 3.2 四個下游判斷式（全部靠中文子字串，emoji 不參與）

| 判斷式 | file:line | 讀的字 |
|---|---|---|
| `final_recommendation()` 加分 | `src/ui/tabs/tab_helpers.py:100-103` | `'便宜'` +2 分、`'合理'` +1 分 |
| `classify_stock_status_lamp()` 🟠減碼 | `src/ui/tabs/tab_helpers.py:175` | `'昂貴'` or `'超貴'` |
| `summarize_candidates()` 汰弱 | `src/compute/screener/scorability.py:163`（marker 定義在 `:34` `EXPENSIVE_VALUATION_MARKER = "超貴"`） | `'超貴'` |
| `generate_ai_comment()` 建議句 | `src/services/app_ai_service.py:296 / 299 / 336 / 338` | `'便宜'` / `'昂貴'` / `'超貴'` |

⚠️ `scorability.py:32` 有一行**只存在於註解**的跨檔耦合聲明：
> `# 「357 評價」欄的超貴標記。產生端：section_batch_fetcher 的 `val4 = '🔴超貴'`。`
→ 兩個檔的字面必須一致，**但沒有任何測試在守這件事**（見 §4）。

### 3.3 動態實證（`eg/dyn_cp2b.py`，直譯器內實跑 production 函式）

改寫規則：**只改中文、emoji 保留**（`'🟢便宜'→'🟢現在划算'` 等）。

```
=== ① final_recommendation（tab_helpers:100-103）===
   DIFF  '🟢便宜'->'🟢現在划算' health=90 trend=📈多頭:  ('🟢 積極',…) -> ('🟡 觀察',…)
   DIFF  '🟢便宜'->'🟢現在划算' health=70 trend=📈多頭:  ('🟡 觀察',…) -> ('🔴 等待',…)
   DIFF  '🟢便宜'->'🟢現在划算' health=70 trend=📉空頭:  ('🟡 觀察',…) -> ('🔴 等待',…)
   DIFF  '🟢便宜'->'🟢現在划算' health=40 trend=📈多頭:  ('🟡 觀察',…) -> ('🔴 等待',…)
   DIFF  '🟡合理'->'🟡價格還行' health=70 trend=📈多頭:  ('🟡 觀察',…) -> ('🔴 等待',…)
   diffs=5

=== ② classify_stock_status_lamp（tab_helpers:175）===
   DIFF  '🔴昂貴'->'🔴有點貴'  bias=-5/5/25:  '🟠 減碼' -> '⚪'
   DIFF  '🔴超貴'->'🔴貴到不行' bias=-5/5/25:  '🟠 減碼' -> '⚪'
   diffs=6

=== ③ summarize_candidates 汰弱（scorability:163, marker='超貴'）===
   '🔴超貴'  eliminated=('A',) kept=()   |  '🔴貴到不行' eliminated=() kept=('A',)  <== 汰弱結果不同!

=== ④ generate_ai_comment（app_ai_service:296/299/336/338）===
   DIFF '🟢便宜' -> '🟢現在划算'
        原: • ✅ 【積極買入】評分≥75且位於357便宜區，可分批布局。
        新: • ✅ 【評分優良】多因子評分≥75，技術面健康，可考慮建立底倉。
        原: • 💎 【357估值】位於7%殖利率線以下（便宜區），策略1認定的必買送分題。
        新: （整句消失）
   DIFF '🔴昂貴'/'🔴超貴' → 【357估值】警語整句消失
   diffs=3
```

**「一支股票從『積極』掉到『等待』、從『減碼燈』掉到『無燈』、從『被汰除』變成『被保留』」
—— 全部只因為改了顯示文字。且畫面上不會有任何錯誤訊息。**

### 3.4 `calc_dividend_yield_357` 自己的 `signal` / `msg`

**(a) 沒有任何 production 判斷式比較它。** 我用 AST 掃全 repo 所有 `ast.Compare`，
找「一邊是含中文的字面、另一邊的 unparse 含 `signal`/`msg`」，production（非 tests）只有 2 處，**都不是 357**：
- `src/compute/scoring/exit_signals.py:258` — `'大戶倒貨' in (chip_signal or '')`（籌碼訊號）
- `src/ui/tabs/stock_sections/section_health_score.py:371` — `'強勢' / '渙散' in _ch['signal']`（籌碼訊號，`_ch` 非 `_dy5`）

**(b) 但它的「格式」是承重的。** `src/ui/views/page_inspect.py:1318` 把 `signal` 塞進 `ValuationReadout`，
`:1889` 再經 `_signal_label()`（`:652-673`）：
```python
_parts = _txt.split(maxsplit=1)                       # ← 切第一個空白
_label = _parts[1].strip() if len(_parts) > 1 else _txt
return "" if banned_signal_glyphs(_label) else _label # ← 殘留燈號 → 回空字串
```
實測（`eg/dyn_cp2.py`）：
```
  ① 保留 emoji + 空格（合規）  '🟢 現在很划算（…）' -> '現在很划算（…）'
  ② 保留 emoji，**去掉空格**   '🟢現在很划算（…）'  -> ''   ⚠️ 訊號頻道消失!
  ③ 純中文，拿掉 emoji         '現在很划算（…）'    -> '現在很划算（…）'
  ④ 中文裡混進燈號 emoji       '🟢 現在很划算 🔴不追高' -> ''  ⚠️ 訊號頻道消失!
```
→ **`<emoji><半形空格><中文>` 這個格式，以及「中文段內不得再出現 🔴🟡🟢⚪」，都是硬約束。**
危險點在於：同一份 357 措辭在本 repo 存在**兩種格式**
（`v5_modules` 有空格、`section_batch_fetcher` 沒空格），改的人很容易「順手統一」而踩雷。

**(c) 另一個顯示面副作用**：`section_health_score.py:427` 印的是 `_dy5["signal"][:12]` ——
**硬切 12 字元**。現行 `'🟢 甜甜價（7%+近5年年年配）'` 已經被切成 `'🟢 甜甜價（7%+近5年'`。
換更長的措辭會被切在更奇怪的位置（不是行為變更，但是使用者看得到的品質問題）。

### 3.5 357 措辭在本 repo 共有 **5 份獨立複本**（本組實測列舉；**未宣稱窮舉**）

| # | 位置 | 格式 | 是否承重 |
|---|---|---|---|
| 1 | `src/compute/strategy/v5_modules.py:356-373` | `🟢 甜甜價（…）`（**有**空格） | 格式承重（`_signal_label`）；字面不承重 |
| 2 | `src/ui/tabs/stock_grp_sections/section_batch_fetcher.py:183-193` | `🟢便宜`（**無**空格） | ★ **字面承重（4 個下游）** |
| 3 | `src/ui/tabs/stock_sections/section_357_valuation.py:115-117, 130-132` | `🟢便宜價 — 積極買進` | 純顯示（走 `_code357` 分派） |
| 4 | `src/ui/etf/etf_tab_single.py:435-451` | `🟢 <b>強烈買進（特價）</b>…` | 純顯示（走 `_zone_code` 分派） |
| 5 | `src/data/core/data_registry.py:693-696` EDU_GUIDE | `🟢 便宜價／強烈買進…` | 純顯示（教學卡） |

另有**第 6 份不同語意、同樣用字**的系統：`shared/stock_buckets.py:331-340`
`classify_pb_level()` 回 `'🟢 便宜'/'🟢 合理'/'🟡 偏貴'/'🔴 超貴'`（**P/B 分級，不是 357**）。
⚠️ 它的輸出在 `section_portfolio_summary.py:261` 被組成 `_pb_eval3` 字串 ——
**我沒有查證 `_pb_eval3` 最終有沒有流進 `tab_helpers.py:175` 那個 `'超貴' in` 判斷式**（見 §5 未驗清單）。

### 3.6 `app_ai_service.generate_ai_comment` 的一個緩解事實（但不能當護身符）

唯一的 production caller `src/ui/tabs/stock_sections/section_op_recommendation.py:104` 寫死
`'val_label': ''`（檔內註解自陳舊碼走 `dir()` 判斷、該變數從未定義，實質恆空）。
→ **目前**那 4 個 `if '便宜' in val` 分支在畫面上不會觸發。
⚠️ 但 `generate_ai_comment` 是 **L3 public 函式**，簽章接受任意 `val_label`；
一旦有人把真的 357 label 接上去，字面立刻變承重。**不得據此宣告該處安全。**

### 3.7 判定與放行條件

⚠️ **字面兼控制流 → 不在窗口內，必須另案。**
具體切法：
- **`section_batch_fetcher.py:183-193` 的五個字面：一個字都不准改。** 要改必須連同
  `tab_helpers.py:100-103`、`tab_helpers.py:175`、`scorability.py:34`、`app_ai_service.py:296/299/336/338`
  一起改，那是**重構**不是文案調整（且該走 §8 流程）。
- **`v5_modules.py:356-373` 的 `signal`/`msg`**：字面本身沒有 production 判斷式在讀，
  但受三條格式硬約束（emoji + **半形空格** + 中文段內不得含 🔴🟡🟢⚪），
  且 `tests/test_b1b_stock_math.py:178/335/379` 與 `tests/test_p03_inspect_view.py:786`
  （`assert _signal == '合理（5~7%）'`，**等號**比對）是真護欄、會紅、須同 PR 更新。
  → 本組建議：**這一塊也另案**，理由是「三條隱形格式約束 + 兩處文案鎖」已經超出
  「只改使用者看得到的文字、不會改行為」這個窗口的保證強度。

---

## 4. 改動點 3｜功能名稱「型態目標價」

### 4.1 全部 12 處（`eg/fate.py` 追蹤，**含** docstring，不漏）

| file:line | 語法角色 |
|---|---|
| `shared/scoring_regime_gate.py:2` | 模組 docstring |
| `shared/scoring_regime_gate.py:132`（字面在 `:137`） | f-string 片段 → `RETURN`（`notice()` 的**使用者可見字串**） |
| `src/ui/tabs/pattern_targets_ui.py:1 / :181` | docstring |
| `src/ui/tabs/stock_grp_sections/section_portfolio_summary.py:139 / :517 / :524` | `ARG->st.markdown` / docstring |
| `src/ui/tabs/tab_edu.py:774` | `ARG->st.markdown` |
| `src/ui/tabs/tab_stock.py:243` | `ARG->st.expander`（label） |
| `src/ui/tabs/tab_stock_grp.py:53 / :62` | `ARG->st.text_area`（label）/ `ARG->st.caption` |
| `tests/test_pattern_targets_ui_mounted.py:1 / :33 / :54 / :56` | docstring / **assert 失敗訊息**（非 assert 條件） |

**零** `COMPARE`、**零** `DICT_KEY`、**零** `SUBSCRIPT`、**零** `MATCH_CASE`。

### 4.2 資料面

- **session_state**：全 repo 無任何含中文的 session key（兩法互證，§1.2）。
- **DataFrame 欄名**：`section_portfolio_summary.py:331/363/538` 的欄叫 **`'型態'`（2 字）**，
  不是「型態目標價」。⚠️ 這是一個**改名地雷**：全字串取代 `型態`→`線型` 會誤傷這個欄名，
  以及 `src/compute/strategy/pattern_targets.py:418` 的 `if pattern == "型態未明":`（**真判斷式**）。
- **落地檔 / Google Sheet**：無（schema 全 ASCII）。
- **Streamlit widget 身分**：我特別查了「label 會不會變成 auto widget key」——
  `tab_stock_grp.py:52-55` 的 `st.text_area(..., key='multi_input')` **有顯式 key**，
  改 label 不會動到 widget 身分、不會清掉使用者輸入。
  `tab_stock.py:243` 是 `st.expander`（純 layout container，狀態不進 session_state）。

### 4.3 全庫突變實驗

把 6 個檔內的 `型態目標價` 全換成 `線型推算價`（共 14 處）→ 全庫 **1 條真紅**：
```
tests/test_h1_scoring_regime_gate.py::TestUserFacingNotice::test_notice_says_what_still_works
```
`tests/test_h1_scoring_regime_gate.py:370-374`：
```python
notice = resolve_scoring_regime({"is_loaded": False}).notice()
for kept in ("健康度", "型態"):
    assert kept in notice
```
→ **真護欄**（實跑 production `notice()`）。它守的是「別讓使用者以為整批分析都廢了」這個語意，
不是守「型態目標價」這五個字。⚠️ 若改名後**仍保留「型態」二字**（例：`型態目標價`→`型態推算價`），
**這條會照樣綠** —— 它只鎖了 2 個字，不是全名。

**UI 顯示字串（expander / markdown / caption / text_area label）突變 → 0 條紅**，
與「純顯示」的靜態判定一致。

### 4.4 判定

✅ **純字面** —— 在「全 repo `.py` + 非 `.py` 設定檔 + parquet + Google Sheet schema + session_state」
這個掃描範圍內，「型態目標價」沒有被任何判斷、key、欄名、落地欄位使用。
**放行條件**：(1) 改名須用**整詞**取代，不得全字串取代「型態」二字
（會誤傷 `pattern_targets.py:418` 的 `if pattern == "型態未明"` 與 `'型態'` 欄名）；
(2) `shared/scoring_regime_gate.py:137` 那一處同時受 `test_h1_scoring_regime_gate.py:370-374` 鎖住，
改名若把「型態」二字也拿掉，須同 PR 更新該測試。

---

## 5. 獨立問題：有沒有「production 壞掉、測試依然綠燈」的假護欄？

**有，而且是本次最嚴重的發現。** 分三類。

### 5.1 ★ A 類：手寫 fixture 字面，與 production 生產端完全斷線

這些測試**自己捏一個 `valuation_zone` / `_val` / `357評價` 字串**餵給消費端，
**從不呼叫生產端**。生產端的字面怎麼變，它們都不會知道。

| file:line | 手寫的字面 | 對應的 production 生產端 |
|---|---|---|
| `tests/test_etf_recommendation.py:28` | `'valuation_zone': '⚪ 中性持有'`（`_row()` 預設） | `etf_scoring_helpers.py:119` |
| `tests/test_etf_recommendation.py:92, 127` | `valuation_zone='🟢 強烈買進'` | 同上 |
| `tests/test_pr_h4_stock_radar.py:124` | `valuation_label='昂貴'` | `section_batch_fetcher.py:191`（實際是 `'🔴昂貴'`） |
| `tests/test_pr_h4_stock_radar.py:132` | `valuation_label='超貴'` | `section_batch_fetcher.py:193`（實際是 `'🔴超貴'`） |
| `tests/test_pr_h4_stock_radar.py:140` | `valuation_label='合理'` | `section_batch_fetcher.py:189`（實際是 `'🟡合理'`） |
| `tests/test_tab_helpers.py:124, 152` | `'_val': '便宜'` | `section_batch_fetcher.py:187`（實際是 `'🟢便宜'`） |
| `tests/test_tab_helpers.py:131, 158, 164` | `'_val': '合理'` | 同上 |
| `tests/test_tab_helpers.py:138` | `'_val': '昂貴'` | 同上 |
| `tests/test_b5b_stock_grp.py:66-68, 177, 398-405` | `'357評價': '🟢便宜'/'🟡合理'/'🔴超貴'`、`'_val': '🟢便宜'` | 同上 |
| `tests/test_i1_multifactor_weight_caption.py:108, 114` | `"357評價": "🟡合理"` | 同上 |

⚠️ 特別注意 `test_pr_h4_stock_radar.py` 與 `test_tab_helpers.py`：它們手寫的是**不帶 emoji**的
`'昂貴'`/`'便宜'`，而 production 送的是**帶 emoji**的 `'🔴昂貴'`/`'🟢便宜'`。
**測試連 production 字串的形狀都沒對上**，卻通過 —— 因為判斷式用的是 `in`（子字串）。

**結構性原因（AST 確認）**：那 5 個承重字面**全部寫在 `run_batch_fetch()` 函式體內**
（`section_batch_fetcher.py:183/187/189/191/193`），而 `run_batch_fetch` 是一個
會開 ThreadPool 真抓資料的 Streamlit UI 函式。
全 repo 對它的測試只有 `tests/test_health_history_b8.py:293` 的
`assertTrue(callable(bf.run_batch_fetch))` —— **只驗它「是個可呼叫物」，從不呼叫它。**
→ **這五個字面在架構上就不可能被任何單元測試觀測到。**

**實測證明（不是推論）**：在 hardlink 副本內把這 5 個字面全部改掉
（`'🟢便宜'→'🟢現在划算'` 等），跑**完整測試套件**：
```
22 failed, 8305 passed, 17 skipped   ← 先跑（sandbox 缺 requirements.txt/.github/docs 等）
   → 補齊缺檔後重跑那 22 條：2 failed, 321 passed
   → 那 2 條在**未突變的對照組**也紅 ⇒ 純 sandbox 假陽性
∴ 突變造成的真紅 = 0 條
```
**§3.3 已實測會翻掉的「最終建議 / 操作狀態燈 / 汰弱名單 / AI 建議句」，測試套件一條都沒抓到。**

### 5.2 ★ B 類：護欄鎖錯了那一半（改動點 1）

見 §2.4。`tests/test_pr_d_etf_ssot.py:115-121` 與 `tests/test_pr_f_audit_residual.py:52/58/64/70`
鎖住四燈的**中文**，但唯一的下游判斷式（`etf_recommendation.py:110-111`）讀的是 **emoji**。
實測：改中文 → 5 紅（假警報）；拿掉 emoji → **0 紅**（真漏網）。
這比「沒有測試」更危險，因為它會製造「這一塊有守」的錯覺。

### 5.3 C 類：只靠註解維繫的跨檔耦合，零機械守衛

`src/compute/screener/scorability.py:32`
```python
# 「357 評價」欄的超貴標記。產生端：section_batch_fetcher 的 `val4 = '🔴超貴'`。
EXPENSIVE_VALUATION_MARKER = "超貴"      # :34
```
兩個檔的字面必須一致，但**沒有任何測試比對這兩處**。
（對照 CLAUDE.md §8.2.A.0 規則 3：「清單由測試強制，不由人工維護」——
這裡正是「靠人工同步」的同一種失效模式。）

### 5.4 附帶發現（不在三個改動點內，但合規窗口會踩到）

- `tests/test_user_facing_copy_guard.py:66-73` 會掃 `EDU_GUIDE` 的
  `meaning/how_to_read/pair_with/historical_anchor/upstream/downstream`
  與 `DangerSpec` 的 `note/unwired_reason/degraded_reason`，
  **禁止**出現：版本號 `v\d+\.\d+`、檔名 `*.py`、模組路徑 `shared/…`、函式呼叫 `xxx.yyy(`、
  `SSOT|DESIGN|WONTFIX|TODO|FIXME`、以及「稽核/實測/舊文案/舊版教學/本次修掉」。
  → 合規窗口改這些欄位時，新文案不得帶入上述字樣。**這是真護欄（會紅）。**
- `src/services/fundamental_screener_service.py:181-190` `SCREEN_ANGLE_LABELS`
  是 **中文 label → ASCII key** 的 dict（`"估值便宜（本益比低）": "pe_low"` 等）。
  改這裡的中文 = 改 **dict key**。本組**未追查**它的 selectbox 是否有顯式 `key=`、
  以及使用者已選值是否以 label 存在 session_state（見 §6）。

---

## 6. 我**沒有**驗到什麼（依 CLAUDE.md §-2 規則 6 誠實揭露）

以下一律**不得**被引用為「已查證」：

1. **「全 repo 沒有其他地方拿這三組字面做判斷」是本組單組結論。**
   掃描範圍：全 repo `.py`（726 檔，AST）＋ `.json/.toml/.yml/.yaml/.html/.js/.csv`（grep）
   ＋ 14 個 parquet 的欄名 ＋ Google Sheet header 常數。
   **未掃**：`.md` 文件內嵌的可執行片段、`.github/workflows` 內的 inline python、
   `mcp_server/` 以外的任何非 Python 服務、以及**執行期才組出來的字串**
   （`f"{x}貴"`、`"".join([...])`、`getattr` 動態取名）—— AST 對後者天生無能。
2. **`_pb_eval3` 的最終流向未查證。** `shared/stock_buckets.py:331-340` 的
   `classify_pb_level()` 也產出 `'🔴 超貴'`，在 `section_portfolio_summary.py:261`
   被組成 `_pb_eval3` 字串。**我沒有追到它最後有沒有進到 `tab_helpers.py:175` 的
   `'超貴' in valuation_label` 判斷式。** 若有，那是**第二個**會被 357 措辭影響的來源。
   → **這一條建議指派另一組專查，不要由想動手的那一組自己查。**
3. **突變實驗只覆蓋我實際跑的三種突變**（CP1 改中文 / CP1 去 emoji / CP2 改 val4 / CP3 改名），
   不等於「任何改法都安全」。特別是我**沒有**測「同時改多處」「改標點」「改全形半形括號」。
4. **`forward_test` 的 `factors` 欄**：我只證實**現存** parquet（60 列，量測日 2026-09-14）
   內容為 ASCII code。我**沒有**追查 `build_pick_snapshot_rows` 的 production caller
   是否在任何路徑下會塞中文進去（`tests/test_forward_test*.py` 內確實出現過
   `"估值便宜,跨季轉強"` 這種中文 factors 字串）。
5. **Streamlit 版本相關行為**（widget 身分演算法、Styler 相容性）未在部署環境實測，
   只在本地 sandbox（Python 3.11.15）驗證。CLAUDE.md §-1.5.A-7(2)：此為無法沙箱驗的限制。
6. **2 條 sandbox 固定紅**（`test_deprecation_honesty::test_accepted_table_has_no_stale_entries`、
   `test_sector_heatmap_universe_single_source::…test_the_one_place_is_l0`）我只證明
   「未突變的對照組也紅 ⇒ 與突變無關」，**沒有**進一步查明它們為何在 hardlink 副本內紅。
   若它們其實對某類改動敏感，我的「0 條真紅」結論會需要重估。
7. **本報告全部判定由本組單組產出，未經第二組獨立複驗。**

---

## 7. 給總管的可執行結論

| 改動點 | 准不准改 | 硬性前提 |
|---|---|---|
| **1 殖利率四燈** | ⚠️ **條件放行** | ① emoji `🟢🔴🟡⚪` 一個都不准動；② 第二回傳值不准動；③ 同 PR 更新 `test_pr_d_etf_ssot.py:115-121` + `test_pr_f_audit_residual.py:52/58/64/70`；④ **CI 綠燈不可當作沒改壞的證據**（護欄裝反，§2.4） |
| **2 357 措辭** | ⛔ **不在窗口內，另案** | `section_batch_fetcher.py:183-193` 一個字都不准動（4 個下游判斷式）；`v5_modules.py:356-373` 受「emoji+半形空格+中文段內不得含燈號」三條隱形格式約束，且有 2 處等號文案鎖 |
| **3 型態目標價** | ✅ **放行** | ① 用**整詞**取代，不得全字串取代「型態」（會誤傷 `pattern_targets.py:418` 與 `'型態'` 欄名）；② 若連「型態」二字都改掉，同 PR 更新 `test_h1_scoring_regime_gate.py:370-374` |

**另案建議（超出本次窗口，屬 §8.4 step 4 的 scope 決策，不由本組決定）**：
1. 補一條機械護欄，把 `section_batch_fetcher.py:183-193` 的五個字面與
   `tab_helpers.py:100/102/175`、`scorability.py:34`、`app_ai_service.py:296/336/338`
   綁在一起（**突變測試**：改任一字面 → 必須有測試轉紅。對應 CLAUDE.md §-1.5.E A7）。
2. 補一條「四燈 label 必須以 `🟢/🔴/🟡/⚪` 開頭」的護欄，修正 §2.4 裝反的護欄。
3. 把 `section_batch_fetcher.py:183-193` 收回 `classify_stock_357_price` SSOT ——
   它現在是**第二份實作**（自己再算一次三檔目標價），不只是第二份字面。

---

## 8. 復現用檔案（全部在 scratchpad，repo 未被改動）

```
eg/e_ast.py      AST 語法角色分類器（全庫掃描）        → eg/e_hits.json（9,561 筆）
eg/fate.py       單一字面命運追蹤（含 docstring，不漏）
eg/q.py          e_hits.json 查詢器
eg/dyn_cp1.py    改動點1 動態實測（classify_yield_zone / recommend_etf_action 80 組）
eg/dyn_cp2.py    改動點2 動態實測（calc_dividend_yield_357 / _signal_label 格式依賴）
eg/dyn_cp2b.py   改動點2 動態實測（val4 → 4 個下游判斷式）
eg/mut/          突變副本（hardlink，只斷開被改的檔）
eg/ctl/          未突變對照組（用來扣掉 sandbox 假陽性）
```

**repo 完整性最終確認**（本報告寫完前執行）：
```
$ cd /home/user/my-stock-dashboard && git status --porcelain
(空)
```
全程唯讀，未執行任何 git 寫入。
