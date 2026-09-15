# PB_LEVEL_TRACE — `classify_pb_level()` 的「🔴 超貴」有沒有流進 `tab_helpers.py:175`？

> 補漏專查組，2026-09-14。唯讀調查，**未修改 repo 任何檔案、未 git 寫入**。
> ⚠️ 本報告全部結論**由本組單組產出，未經第二組獨立複驗**（CLAUDE.md §-2 規則 6）。
> 依該條，在被獨立稽核之前屬**待驗事項**。§5 逐項列出本組沒查到 / 沒查證的部分。

---

## §1 一句話結論

**沒有流進去。** `classify_pb_level()` 產出的 `'🔴 超貴'` 經 `_pb_eval3` 進入
`_fund_map[sid]['P/B評價']` 之後，**只被顯示（3 處 `st.dataframe` 欄位）與餵給 AI prompt（1 處）**，
**從未進入任何判斷式** —— 特別是**沒有**進入 `src/ui/tabs/tab_helpers.py:175`
那個點亮「🟠 減碼」的 `'超貴' in ...`。

**但這個「沒有」是靠兩層偶然擋住的，不是靠設計擋住的**（詳見 §2.4）：

1. **靠 dict key 不同名**：被判斷的 key 是 `'357評價'` / `'_val'`，PB 走的是 `'P/B評價'`，
   兩個 key set 交集為空 → PB 進不去判斷式。
2. **靠判斷式用「昂貴」而 PB 用「偏貴」**：PB 的中間帶叫 `'🟡 偏貴'`，
   而 `tab_helpers.py:175` 比對的是 `'昂貴'` / `'超貴'` —— `'偏貴'` 不含這兩個子字串。

⚠️ **實測證實：只要 PB 標籤被餵進去，那盞燈就會亮。**
`classify_stock_status_lamp(..., valuation_label='3.00 🔴 超貴')` → **`'🟠 減碼'`**（§3 動態驗證 B）。
也就是說，**這兩個量綱目前沒有耦合，純粹是因為沒有人把它接上去**；
`tab_helpers.py:175` 的判斷式本身**對 PE/PB/殖利率一視同仁**，
任何人日後把 `'P/B評價'` 塞進 `'_val'`、或把 PB 標籤傳給 `valuation_label`，**當場就是量綱混用 bug**。

---

## §2 完整資料流（逐步 `file:line`）

### 2.1 PB 這條線：產生 → 去了哪裡（**終點是顯示，不是判斷**）

| # | 步驟 | 位置 | 內容 |
|---|---|---|---|
| 1 | **產生** | `shared/stock_buckets.py:321-340` | `classify_pb_level(pb, bands)` → `'🟢 便宜'` / `'🟢 合理'` / `'🟡 偏貴'` / `'🔴 超貴'` / `'—'`（**emoji 後有半形空格**） |
| 2 | **組字串** | `src/ui/tabs/stock_grp_sections/section_portfolio_summary.py:261` | `_pb_eval3 = f'{_pb_raw3:.2f} {classify_pb_level(_pb_raw3, _bands3)}'` → 形狀如 `'3.00 🔴 超貴'` |
| 3 | **裝箱** | `section_portfolio_summary.py:274,280` | `_fund_map[_sid3] = {..., 'P/B評價': _pb_eval3}` |
| 4 | **回傳** | `section_portfolio_summary.py:158` | `_fund_map = _precompute_fund_map(results_t3)` |

**終點共 4 個，逐一追到底：**

| 終點 | 位置 | 判斷？ |
|---|---|---|
| **A. 🏆 組合排行總表** | `section_portfolio_summary.py:321` → `:344` `'P/B': fd.get('P/B評價','-')` → `:347` `pd.DataFrame(rows)` → `:360` `st.dataframe(...)` | ❌ **純顯示**。排序鍵是 `['_p','多因子']`（`:348`），不含 P/B |
| **B. ③ 多因子評分排行** | `section_portfolio_summary.py:646` → `:656` `'P/B評價': _fd.get('P/B評價','-')` → `:660` `st.dataframe(...)`；`:668` 只是 `TextColumn` 欄位設定 | ❌ **純顯示** |
| **C. ④ 汰弱留強明細** | `section_portfolio_summary.py:746` `_row.update(fund_map.get(_sid3, {}))` → `:754` `df_cmp` → `:757` `_col_order` | ❌ **連顯示都沒有** —— `_col_order` 白名單為 `['名稱','代碼','出場','操作狀態','RSI','KD','量比','IBS','趨勢','357評價','VCP','合約負債']`，**不含 `'P/B評價'`**，該欄被濾掉 |
| **D. AI 組合建議 prompt** | `src/ui/tabs/stock_grp_sections/section_ai_portfolio.py:137` `f"... P/B={_fd_p.get('P/B評價','-')} \| "` | ❌ **只進 LLM prompt 字串**，不進 Python 判斷式 |

> ⚠️ **終點 C 是本次最需要確認的一步**（`dict.update()` 有覆蓋既有 key 的能力）。
> 實查：`_row` 在 `:745` 由 `{k:v for k,v in _r3.items() if not k.startswith('_') and k != 'stock_id'}` 建立，
> 已把 `'_val'` 濾掉；而 `_fund_map` 的 6 個 key
> （`'近4季EPS'`/`'毛利率%'`/`'殖利率%'`/`'SQ評分'`/`'FGMS'`/`'P/B評價'`）
> **與被判斷的 key（`'357評價'`/`'_val'`/`'val_label'`）交集為空集合**（§3 動態驗證已實測）
> → `.update()` **不會**覆蓋 `'357評價'`。

### 2.2 反查：`tab_helpers.py:175` 的 `valuation_label` 實際是誰傳的？

判斷式原文（`src/ui/tabs/tab_helpers.py:175`）：
```python
if valuation_label and ('昂貴' in str(valuation_label) or '超貴' in str(valuation_label)):
    return '🟠 減碼'
```

`classify_stock_status_lamp` 的 **production caller 全部只有 2 個**
（掃描方法：`grep -rn "classify_stock_status_lamp"`，排除 `tests/`）：

| # | caller | 傳進去的是什麼 | 來源量綱 | 形狀 |
|---|---|---|---|---|
| **1** | `src/ui/tabs/stock_grp_sections/section_batch_fetcher.py:294-297`，`valuation_label=val4` | `val4`，inline 產生於 **同檔 `:183-193`** | **357 殖利率估值**（`avg_div4 / YIELD_*_DEC` 反推目標價比大小） | `'🟢便宜'`/`'🟡合理'`/`'🔴昂貴'`/`'🔴超貴'`/`'⚪無股利'`（**emoji 後無空格**） |
| **2** | `src/ui/tabs/tab_stock.py:712-715`，`valuation_label=_valuation_simple` | `_valuation_simple`，產生於 **同檔 `:699-708`**：`classify_yield_zone(_cur_yld)` 回 code，`'sell'→'昂貴'`（`:706`）、`'reduce'→'偏貴'`（`:708`），其餘維持 `None` | **357 殖利率估值**（`shared/thresholds.classify_yield_zone`） | `'昂貴'` / `'偏貴'` / `None`（**純文字，無 emoji**） |

**兩個 caller 傳的都是「殖利率估值標籤」，沒有一個傳 PB、也沒有一個傳本益比（PE）標籤。**

> 📌 **附帶發現（caller 2 的一個不對稱，非本次主題但一併記錄）**：
> `_valuation_simple` **永遠不可能是 `'超貴'`** —— `:705-708` 只映射 `sell→'昂貴'` 與 `reduce→'偏貴'`。
> 而 `'偏貴'` **不含** `'昂貴'` 也不含 `'超貴'` → **`reduce` 這一段在個股 Tab 永遠點不亮 🟠 減碼**（§3 動態驗證 D 實測）。
> 對照組合 Tab 的 `val4`：`'🔴昂貴'` 與 `'🔴超貴'` **兩段都會點亮**。
> ⇒ **同一盞「🟠 減碼」燈，個股 Tab 與組合 Tab 的觸發帶不一樣寬。**
> ⚠️ 這是本組的**觀察**，不是本次派工要查的結論，**未查證這是有意設計還是疏漏**，也未查 git history。

### 2.3 另外三個「有判斷」的地方 —— 逐一確認 PB 都沒進去

AST 掃描（§4 方法）找出全 repo **production 只有 4 個判斷點**用到這四個字面：

| # | 判斷點 | 讀哪個欄位 | PB 會不會進來 |
|---|---|---|---|
| 1 | `src/ui/tabs/tab_helpers.py:175`（🟠 減碼燈） | 參數 `valuation_label` | ❌ 見 §2.2，兩個 caller 都傳 357 |
| 2 | `src/ui/tabs/tab_helpers.py:100,102`（`final_recommendation` 綜合建議 +2/+1 分） | `row.get('_val','')`（`:86`） | ❌ `'_val'` 由 `section_batch_fetcher.py:268` 寫入 `val4`（357）。PB 在 `'P/B評價'`，不同 key（§3 動態驗證已實測） |
| 3 | `src/compute/screener/scorability.py:34,165-167`（汰弱留強 eliminate） | `r.get('357評價','')`（`:165`），常數 `EXPENSIVE_VALUATION_MARKER = '超貴'`（`:34`） | ❌ 讀 `'357評價'`（`section_batch_fetcher.py:261` 寫入 `val4`）。**且時序上也不可能**：唯一 caller `section_portfolio_summary.py:89` 跑在 `_precompute_fund_map`（`:158`）**之前**，PB 那時還沒算出來 |
| 4 | `src/services/app_ai_service.py:296,299,336,338`（AI 文字建議分支） | `val = str(data.get('val_label',''))`（`:267`） | ❌ **而且這 4 個分支目前是死的**：全 repo `generate_ai_comment(` 的 production 呼叫**只有 1 處** —— `src/ui/tabs/stock_sections/section_op_recommendation.py:112`，而 `:104` 把 `'val_label': ''` **寫死成空字串**（該處 `:102-103` 註解自陳原碼走 `if 'xx' in dir()` 恆 False，故實質為 `''`）→ `'昂貴' in ''` 恆 False |

> 另有 `src/compute/risk/risk_radar.py:677,679` 的 `valuation_level == "極貴"` / `== "便宜"`：
> 那是**總經/市場層**的估值分位（詞彙是 `"便宜"/"合理"/"偏貴"/"極貴"`，**用「極貴」不是「超貴」**），
> 且 `valuation_level` 是 `*` 後的 keyword-only 參數、預設 `None`，
> **全 repo 只有 `tests/test_dual_verdict_ui.py` 傳值，production 零 caller** → 目前完全 inert。
> 就算 PB 標籤流到那裡也不會命中（`==` 精確比對，`'🟢 便宜' != '便宜'`）。

### 2.4 為什麼說「擋住是偶然、不是設計」

- `tab_helpers.py:175` 的判斷式**對輸入的量綱沒有任何檢查**：它只做子字串比對，
  收到殖利率標籤、PE 標籤、PB 標籤都會照亮燈。docstring（`:144`、`:152`）
  雖然寫了「估值『昂貴 / 超貴』(357 殖利率分級結論)」，**但那是註解，不是約束**。
- PB 沒被誤觸的**唯一實質理由**是：PB 的中間帶被命名為 `'🟡 偏貴'`（不含「昂貴」），
  而 PB 的頂帶 `'🔴 超貴'` **恰好沒有被接到那個參數上**。
  ⚠️ **`'超貴'` 這個字面在 PB 與 357 兩邊是逐字相同的** —— 一旦有人接線，靜默耦合當場成立。

---

## §3 動態驗證結果（在直譯器內 import production 函式實跑；**未改 repo**）

腳本：`<scratchpad>/dyn_check.py`、`<scratchpad>/dyn_wiring.py`（皆在 scratchpad，非 repo 內）。

### A. `classify_pb_level` 實際輸出（確認字面形狀）
```
pb=0.5  -> '🟢 便宜'      pb=2.0 -> '🟡 偏貴'      pb=0    -> '—'
pb=1.0  -> '🟢 合理'      pb=3.0 -> '🔴 超貴'      pb=None -> '—'
```

### B. ⚠️ 把 PB 標籤**直接**餵給 `classify_stock_status_lamp`（假設耦合成立時會怎樣）
```
_pb_eval3='3.00 🔴 超貴'  -> lamp='🟠 減碼'   ← 會亮！
_pb_eval3='2.00 🟡 偏貴'  -> lamp='⚪'
_pb_eval3='1.00 🟢 合理'  -> lamp='⚪'
_pb_eval3='0.50 🟢 便宜'  -> lamp='⚪'
```
**⇒ 判斷式對 PB 的「超貴」完全沒有免疫力。目前沒亮，純粹是因為沒接上。**

### C. 對照組：現行真正傳進去的 357 標籤（`section_batch_fetcher` 的 `val4`）
```
'🟢便宜' -> '⚪'      '🔴昂貴' -> '🟠 減碼'      '⚪無股利' -> '⚪'
'🟡合理' -> '⚪'      '🔴超貴' -> '🟠 減碼'
```

### D. 對照組：個股 Tab 的 `_valuation_simple`
```
'昂貴' -> '🟠 減碼'      '偏貴' -> '⚪'   ← reduce 段點不亮（見 §2.2 附帶發現）      None -> '⚪'
```

### E. 真實 production 函式的接線驗證（**不是孤立函式，是真的 `summarize_candidates` / `final_recommendation`**）
```
[汰弱留強] row={'健康度':80,'357評價':'🟢便宜','P/B評價':'3.00 🔴 超貴'}
           -> eliminated=()      kept=('9999',)    ← PB 超貴沒有造成淘汰 ✅
[汰弱留強] row={'健康度':80,'357評價':'🔴超貴','P/B評價':'0.50 🟢 便宜'}
           -> eliminated=('8888',) kept=()         ← 淘汰確實只看 357 ✅

[綜合建議] _val='🟢便宜' + 'P/B評價'='3.00 🔴 超貴' -> ('🟢 積極', '#22c55e')
[綜合建議] _val='🔴超貴' + 'P/B評價'='0.50 🟢 便宜' -> ('🟢 積極', '#22c55e')
           ← 兩者相同 ⇒ 'P/B評價' 對 final_recommendation 零影響 ✅

fund_map keys ∩ judged keys = set()   ← 空集合，.update() 不會覆蓋被判斷的欄位 ✅
```

> ⚠️ **動態驗證的限制（誠實標明）**：以上是**在直譯器內以人造 row 呼叫 production 純函式**。
> **沒有**實際跑起 Streamlit 畫面、**沒有**跑真實網路取數（`_precompute_fund_map` 內含 I/O）。
> 因此「PB 不會點亮減碼燈」這個結論的證據鏈是
> 「**靜態追出 caller 只有 2 個 + 動態證實那 2 個傳的 key 與 PB 的 key 不相交**」，
> **不是**「在真實畫面上觀察到燈沒亮」。

---

## §4 「四字面」（超貴 / 昂貴 / 便宜 / 合理）全部複本清單

### 4.1 掃描方法與範圍（**先講清楚，結論才有得打折**）

- **工具**：自寫 AST 腳本（`<scratchpad>/scan_literals.py` 抓字串常值、`<scratchpad>/scan_judge.py` 抓判斷式），
  **不是**純 grep —— grep 會把大量註解 / docstring 散文（「合理範圍」「合理性檢查」）當命中。
- **排除**：module / class / function 的 **docstring** 已用 AST 排除；`.git` / `__pycache__` / `.venv` / `node_modules` 已排除。
- **⚠️ 已知盲點（會漏的東西）**：
  - **inline `#` 註解不在 AST 內** → 註解裡的這四個字**掃不到**（但註解不影響行為）。
  - **動態組出來的字串掃不到**：`f'{x}貴'`、`'超' + '貴'`、從 JSON / DB / session_state 讀進來的值。
    本組**沒有**針對這種形狀另做掃描。
  - **只掃 `.py`**。另查非 `.py` 檔：命中的只有 `__pycache__/*.pyc`（`.py` 的衍生物）與 **`STATE.md`**（文件）；
    **沒有** `.json` / `.csv` / `.yml` 等資料檔帶這四個字面（`grep -rln` 實測）。
- **⚠️ 本清單是單組窮舉，未經第二組驗證。** 依 §-2 規則 6，**不得**當成「只有這些」的既定前提。

### 4.2 **產生端**（把估值分級輸出成這四個字面的地方）

| # | 位置 | 字串的**確切形狀** | 量綱 | 誰消費 |
|---|---|---|---|---|
| **P1** | `shared/stock_buckets.py:335,337,339,340`（`classify_pb_level`） | `'🟢 便宜'` `'🟢 合理'` `'🟡 偏貴'` `'🔴 超貴'`（**emoji + 半形空格**；中間帶用「**偏貴**」） | **股價淨值比 P/B** | `section_portfolio_summary.py:261`（→ 顯示）、`tab_stock.py:1605`（→ AI prompt） |
| **P2** | `src/compute/strategy/v5_modules.py:365,368,371`（`calc_dividend_yield_357` 的 `signal`） | `f'🟡 合理（{YIELD_MID:g}~{YIELD_HIGH:g}%）'` / `f'🔴 昂貴（{YIELD_LOW:g}~{YIELD_MID:g}%）'` / `f'🔴 超貴（<{YIELD_LOW:g}%）'`（**emoji + 空格 + 全形括號帶數字**；便宜段措辭是 `'🟢 甜甜價…'` / `'🟢 高殖利率…'`，**不含「便宜」二字**） | **357 殖利率** | `section_health_score.py:412`（`:427` 取 `_dy5['signal'][:12]` 顯示）、`page_inspect.py:1301`（`:1319` 存進 `ValuationReadout.signal` 顯示）。**兩處皆純顯示** |
| **P3** | `src/ui/tabs/stock_grp_sections/section_batch_fetcher.py:187,189,191,193`（inline 複本） | `'🟢便宜'` `'🟡合理'` `'🔴昂貴'` `'🔴超貴'`（**emoji 後無空格**；頂帶用「**昂貴**」+「**超貴**」兩段） | **357 殖利率** | ⚠️ **唯一會被判斷的一份**：`:261` → `'357評價'` → `scorability.py:165`；`:268` → `'_val'` → `tab_helpers.py:100,102`；`:297` → `valuation_label` → **`tab_helpers.py:175`** |
| **P4** | `src/ui/tabs/tab_stock.py:1594-1595`（AI prompt inline） | `'便宜'` / `'合理'` / `'昂貴'` / `'超過昂貴'`（**純文字、無 emoji**；頂帶是「**超過昂貴**」不是「超貴」） | **357 殖利率** | `:1596` 併入 `_fund_str2` AI prompt 字串 |
| **P5** | `src/ui/tabs/tab_stock.py:706,708` | `'昂貴'` / `'偏貴'`（**純文字**；**無「超貴」段**） | **357 殖利率**（`classify_yield_zone` code 映射） | `:715` → **`tab_helpers.py:175`** |
| **P6** | `src/ui/tabs/stock_sections/section_357_valuation.py:293-295, 398-400, 486-488` | `'🟢 便宜區'` / `'🟡 合理區'` / `'🔴 昂貴區'` / `'⛔ 超昂貴'`（**emoji + 空格 + 「區」字**；頂帶「**超昂貴**」） | **357 殖利率** | 同檔 `st.caption` 顯示 |
| **P7** | `src/ui/tabs/stock_sections/section_357_valuation.py:115-118` | `'🟢便宜價 — 積極買進'` / `'🟡合理價 — 可分批布局'` / `'🔴昂貴價 — 謹慎操作'` / `'🔴超過昂貴 — 避免追高'`（**無空格 + 「價」字 + 破折號建議**） | **357 殖利率** | 同檔顯示 |
| **P8** | `src/ui/tabs/stock_sections/section_357_valuation.py:130-132, 244-246, 297, 363-365, 455-457` | 圖表 trace 名稱 / 軸標：`'🟢便宜(7%)'`、`'7%便宜'`、`f'PE{_pe_low}便宜'`、`'便宜:'` 等（多種形狀） | 357 殖利率 / **本益比 PE 河流圖**（`:363-365`） | Plotly trace `name=` 與 caption，純顯示 |
| **P9** | `src/ui/tabs/tab_stock_picker.py:866,868,870,872` | `'✅ 便宜 '` / `'✅ 合理 '` / `'❌ 昂貴 '` / `'❌ 超昂貴 '`（**✅/❌ + 空格 + 尾隨空格**；頂帶「**超昂貴**」） | 選股網估值 | 同檔顯示 |
| **P10** | `src/data/core/data_registry.py:693-695` | `'🟢 便宜價／強烈買進（357 殖利率估值法則）'` / `'⚪ 合理價／中性持有'` / `'🟡 昂貴，適度減碼'`（**長句、全形斜線**） | 357 殖利率（欄位說明文案） | registry 說明文字 |
| **P11** | `src/compute/scoring/scoring_helpers.py:108,110,112` | `'便宜區 >7%'` / `'合理 5~7%'` / `'合理 3~5%'` | 357 殖利率（評分理由字串） | 評分 reason 顯示 |
| **P12** | `src/ui/etf/etf_tab_single.py:441,445-446,450-451,471,522` | `'🔵 合理買進'`、`'🟡 <b>適度減碼（合理）</b>…'`、`'🔴 <b>獲利了結（昂貴）</b>…'`（**含 HTML tag**） | **ETF 殖利率** | 同檔 HTML 顯示 |
| **P13** | `src/compute/risk/risk_radar.py:679-680` | `"便宜"`（**純文字，精確比對**）；另 `:677` 用 `"極貴"` | **總經/市場估值分位**（**第 4 種量綱**） | `:679` 判斷（但 production 零 caller，見 §2.3） |
| **P14** | `src/compute/screener/scorability.py:34` | `EXPENSIVE_VALUATION_MARKER = "超貴"`（**具名常數，無 emoji**） | 消費 P3 的 357 標記 | `:122`/`:166` 判斷 |
| **P15** | `src/ui/etf/etf_tab_portfolio.py:659,679,725`、`etf_tab_grp_compare.py:269`、`etf_helpers.py:221`、`ui_widgets.py:170`、`fundamental_screener_service.py:182`、`ai_qa_service.py:756`、`etf_tab_single.py:969` | 散文式說明句（如 `'σ 便宜 / +'`、`'折價撿便宜（存股框架條件 C）'`、`'估值便宜（本益比低）'`） | 混雜（σ 位階 / 折溢價 / PE） | 純 caption / help 文案 |

**⇒ 回答派工的問題「第四份、第五份有沒有？」：有，而且遠不只五份。**
若只算「**把一組估值分級輸出成這四個字面的產生端**」，本組數到 **P1–P13 共 13 處**（P14 是消費端常數、P15 是散文）。
若只算「**四段式估值分級的完整複本**」（便宜/合理/昂貴/超貴 一整組），至少 **P1、P2、P3、P4、P6、P7、P9** 共 **7 份**，
**七份的字串形狀沒有任何兩份完全相同**（空格、emoji、「區」/「價」後綴、「超貴」vs「超過昂貴」vs「超昂貴」vs「極貴」全都不一樣）。

### 4.3 **消費端（判斷式）**完整清單 —— production 只有 4 處

| 位置 | 判斷式 | 輸入來源 | 現況 |
|---|---|---|---|
| `src/ui/tabs/tab_helpers.py:175` | `'昂貴' in ... or '超貴' in ...` | P3（組合 Tab）/ P5（個股 Tab） | **活的**，點亮 🟠 減碼 |
| `src/ui/tabs/tab_helpers.py:100,102` | `'便宜' in val` / `'合理' in val` | P3 的 `'_val'` | **活的**，綜合建議 +2/+1 分 |
| `src/compute/screener/scorability.py:166` | `'超貴' in _val_txt` | P3 的 `'357評價'` | **活的**，汰弱留強 eliminate |
| `src/services/app_ai_service.py:296,299,336,338` | `'便宜' in val` / `'昂貴' in val or '超貴' in val` | `data['val_label']` | **實質死碼**：唯一 caller `section_op_recommendation.py:104` 寫死 `''` |
| （`src/compute/risk/risk_radar.py:677,679`） | `valuation_level == "極貴"` / `== "便宜"` | keyword-only，預設 `None` | **production 零 caller**，只有測試傳值 |

> ⚠️ **注意 `scorability.py:34` 的註解自陳：「產生端：section_batch_fetcher 的 `val4 = '🔴超貴'`」** ——
> 這是**全 repo 唯一一處**把「這個字面從哪來」寫進 code 的地方，
> 也正好證實了：**被判斷的那份是 P3（357），不是 P1（PB）。**

---

## §5 我沒查到 / 沒查證的（依 §-2 規則 6 誠實標明）

1. ⭐ **「production 只有 4 個判斷點」是本組單組 AST 窮舉的全稱句，沒有第二組驗過。**
   掃描只涵蓋 `ast.Compare`（`in`/`==`/`!=` 等）與一組具名 method call
   （`startswith`/`endswith`/`contains`/`find`/`index`/`count`/`replace`/`split`/`eq`/`isin`）。
   **會漏**：`re` 正則比對、`any(w in s for w in LIST)` 這種**常數在 list/dict 裡**的形狀、
   pandas `df[col].str.contains(變數)`、以及任何**用變數而非常值**做比對的地方。
2. **動態驗證沒有跑真實畫面**（見 §3 末的限制欄）。沒跑 Streamlit、沒跑真實取數。
   「PB 不會點亮減碼燈」是**靜態接線 + 人造 row 實測**的合成結論，不是畫面觀察。
3. **沒查 git history**，因此**無法回答「這是有意為之還是意外」的歷史意圖**部分 ——
   §2.4 的「靠偶然擋住」是**對現行 code 的結構判斷**，不是對作者意圖的考證。
   （能說的只有：`scorability.py:34` 的註解顯示**至少那一處**的作者清楚知道字面來源是 357。）
4. **「四字面複本共 N 份」沒有給精確數字當結論**，因為「什麼算一份複本」本身可爭議
   （P8 一個檔就有 5 組不同形狀）。§4.2 給的是**逐處位置**，請以位置清單為準，不要引用任何總數。
5. **沒查 `.md` / `SPEC.md` / `ARCHITECTURE.md` 裡對這四個字面的規範性描述**
   （只確認 `STATE.md` 含這些字，未讀內容）。若那些文件對「超貴」有 SSOT 宣告，本組不知道。
6. **§2.2 的「附帶發現」（個股 Tab 的 `reduce` 段點不亮減碼燈）未經查證是 bug 還是設計**，
   也**未**列入本次派工範圍。**僅記錄，不下結論。**
7. **`tab_stock.py:1605` 的 PB（P1 的第二個消費點）只確認流向 AI prompt 字串**，
   未逐字追 prompt 之後 LLM 回應如何被使用。

---

## §6 對「哪些字准改」的直接影響（供總管決策，**本身是建議不是既定事實**）

| 要改的字 | 位置 | 改了會怎樣 |
|---|---|---|
| **P1 PB 的 `'🔴 超貴'` / `'🟢 便宜'` / `'🟢 合理'` / `'🟡 偏貴'`** | `shared/stock_buckets.py:335-340` | **目前只影響顯示與 AI prompt**（§2.1 四個終點全是顯示）。⚠️ 但 `tests/test_pb_bands_ssot.py:61-64` 用 `'便宜' in ...` / `'超貴' in ...` 斷言 → **改字會讓那 4 條測試紅燈** |
| **P3 的 `val4` 四個字面** | `section_batch_fetcher.py:187-193` | ⛔ **最危險的一份**。同時被 3 個判斷式吃：`tab_helpers.py:175`（減碼燈）、`tab_helpers.py:100,102`（綜合建議分數）、`scorability.py:166`（汰弱留強淘汰）。**改這裡必須同步改那 3 處，否則靜默失效**（燈不亮、分數少加、該淘汰的沒淘汰 —— 三者都不會報錯） |
| **P5 的 `'昂貴'`** | `tab_stock.py:706` | 被 `tab_helpers.py:175` 吃 → 改字 = 個股 Tab 減碼燈全滅（靜默） |
| **`tab_helpers.py:175` 判斷式本身的 `'昂貴'`/`'超貴'`** | `tab_helpers.py:175` | 必須與 P3、P5 **同時**改 |
| **P2/P4/P6~P13、P15** | 各該處 | **只影響顯示**（P13 的判斷式 production 零 caller）。⚠️ 仍須查各自的測試斷言 |

> ⚠️ **只改 PE/357 那邊、不改 PB 那邊 → 沒事**（兩者目前無耦合，§1）。
> ⚠️ **只改 PB 那邊、不改 357 那邊 → 也沒事**（同理），但**會踩到 `test_pb_bands_ssot.py` 的斷言**。
> ⛔ **真正會靜默弄壞畫面的是動 P3 / P5 / `tab_helpers.py:175` 這三處而沒有同步。**
> 以上為本組單組判斷，**未經第二組複驗**，請勿直接當作「可以動手」的授權。
