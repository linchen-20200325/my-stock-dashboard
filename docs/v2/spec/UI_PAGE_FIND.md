# UI_PAGE_FIND —— 「🔍 找標的」頁完整版面（第 4 份）

**基準**：線框 `docs/v2/wireframe/wf_page_find.js`（客戶審過）＝版面來源；元件一律引用第 2 份 `UI_COMPONENTS.md`、token 一律引用第 1 份 `UI_TOKENS.md`（⛔ 本檔不改這兩份、⛔ 不新造元件類型）。
實作對照 `src/ui/views/page_find.py::render_page_find()`。斷點沿用第 2 份 `≤640 / 641–880 / ≥881`（CSS 現況不一致已由第 2 份登記為實作待修，本檔不重述）。
⚠️ 本檔為 UI 設計組 WH 單組產出，未經第二組複驗（§-2 規則 6）；**全檔免責只講這一次**。

## ① 四層結構

「四層」＝ `UI_COMPONENTS` §1 卡片四層密度 `.blk.t1~t4`，由 `layers[].n` **自動掛**（⛔ 非逐塊手選）。
⚠️ 線框另有 `n0` 葉外 chrome（五頁共用）與 `n5` 葉2 → **據實列出，不計入四層**。

| 層 | 線框 | block key | leaf | 卡密度 | 主徽章 | 卡標字級 | cols D/T/P |
|---|---|---|---|---|---|---|---|
| 葉外 | n0 | `find.statusbar`／`chrome.asof` | — | `t3` `6px 9px` | `.sbadge b3` `11px`／`2px 10px`／min-h 28 | `13px/700` | 1/1/1 |
| 第一層 條件表單 | n1 | `find.screen_form`／`find.scenario_quickpick`／`find.wiring_disclosure` | l1 | `t1` `15px 17px`；border **2px** | `.sbadge b1` `14.5px`／`10px 22px`／min-h 46／border 2px | `17.5px/700` | 3/2/1・3/3/1・1/1/1 |
| 第二層 總覽卡 | n2 | `find.screen_summary` | l1 | `t2` `10px 12px` | `.sbadge b2` `12.5px`／`5px 13px`／min-h 36 | `14.5px/700` | 1/1/1 |
| 第三層 大表＋CSV | n3 | `find.screen_table`／`find.pick_reason`／`find.csv` | l1 | `t3` `6px 9px` | `.sbadge b3` | `13px/700` | 1/1/1 |
| 第四層 展開佐證 | n4 | `find.pe_two_kinds` | l1 | `t4` `5px 9px`；border 1px **dashed** | `.sbadge b4` `10.5px`／`2px 5px`／min-h 26／border 0 | `12.5px/700` `--ink-2` | 1/1/1 |
| 葉2 | n5 | `find.map_cta`／`find.heatmap`／`find.sector_flow`／`find.map_scale_disclosure` | l2 | `t2`（**WH 本組新訂**：`n5` 超出 `n1~n4` 自動對映，取「核心卡」） | `.sbadge b2` | `14.5px/700` | 1/1/1・2/1/1・2/1/1・1/1/1 |

**按鈕（一律取 `UI_COMPONENTS` §3，⛔ 不新造）**
- **主 CTA `🎯 開始選股`**（n1，SSOT `page_find.py:422`）＝ §3 主 CTA：`min-height:40px`／`6px 16px`／`13.5px/700`／`radius:3px`／底 `--ink`／框 `2px solid --ink`／hover 底＋框 `--ochre`、字 `--paper`；焦點環 `2px solid --focus` `offset:2px`。**form 內只有這一顆、住預設葉 l1 ⇒「全站唯一一顆主 CTA 且在預設葉可見」成立。**
- **葉2 `🗺️ 載入板塊地圖`**（`:1621`，form 外、非預設葉 ⇒ **不是**頁主 CTA）＝ §3 次級（說明）：`min-height:40px`／`6px 16px`／`13.5px/700`／底 `transparent`／框 `1px solid --ink`／hover 底 `--panel-2`、框 `--rule-2`。
- **CSV `💾 下載選股結果 CSV`**（n3，form 外）＝ §3 次級（說明）；0 列時走 §3 停用態 `13.5px/500`＋`1px dashed --rule-2`＋字 `--sig-grey`（見 ⑤）。
- **〔為什麼有些本益比是空的 ▸〕**（n4）＝ §3 次級（展開佐證）：`min-height/width:44px`／`7px 9px`／`12.5px/600`。
- 因子清單載不進來時 `build_form_unavailable_card()`（`:1479`）取代表單 ⇒ 該情境**全頁無主 CTA**，按鈕位走上列停用態。

**排列（三斷點）**：欄數一律取線框 `cols`，硬夾 `MAX_COLS＝3`（`_ui_kit.py:99` 由 `tab_today.MAX_COLS` import，本檔不另立 3）；多於 3 格**換行排下一列，不是加欄**。
⚠️ n1 的 `3/2/1` **未落地**：實作 `page_find.py:1530` 為 `grid(("①","②","③"), MAX_COLS)`，三斷點恆 3 欄（`st.columns` 依比例切寬、不認 CSS 斷點）→ **實作待修**。
⚠️ n5 的 `2/1/1` 只落地一半：實作兩張**卡**並列，兩張**圖**上下堆疊。

**首屏可見範圍**：**三個斷點一律「需實機量測」**（比照第 3 份）。repo 內無 `vh`、本頁 `var(--` 與 `<style>` 皆 0 命中 ⇒ 排版全由 Streamlit 自身 CSS 決定；本頁另多兩個 repo 反解不出的高度來源 —— `st.tabs` 頭高與 `st.form` 邊框高（由 Streamlit 版本決定，floor 見 `requirements.txt`）。⛔ 不猜。
**唯一可宣稱的是順序（不含高度）**：標題 → caption → 兩葉 tab 頭 → 葉1 `section_header` → 條件表單 → 接線揭露 caption → 「選股結果」總覽卡；**表與 CSV 恆在總覽卡之後**（`:1590` 早退）。

## ② 狀態覆蓋（線框 `states` 十鍵 ∪ 實作分支 → `UI_COMPONENTS` #1~#10）

| 線框鍵 | 常數（`shared/ui_state.py`） | 徽章 | 實作 |
|---|---|---|---|
| `live` | `UI_LIVE="live"` | **#1** | ✅ 三個 `classify_ui_state` 呼叫點（`:1221`／`:1322`／`:1385`） |
| `loading` | `UI_LOADING` | **#2** | ❌ 見處置 1 |
| `idle` | `UI_IDLE` | **#3** | ✅（`SS_APPLIED_SCREEN`／`SS_MAP_REQUESTED` 存在性） |
| `degraded` | `UI_DEGRADED` | **#4** | ⚠️ 僅葉2 見處置 5 |
| `unwired` | `UI_UNWIRED` | **#5** | ❌ 見處置 2 |
| `error` | `UI_FAILED=`**`"failed"`** | **#6** | ✅（`error` 物件／`MISS_CONTRACT_DRIFT` 經 `FAILED_REASONS` 升紅）；字面不一致同第 3 份落差 5，以常數為準 |
| `empty`／`missing` | `UI_EMPTY` ＋ `MISS_*` | **#7** | ⚠️ 見處置 3 |
| `na` | `UI_EMPTY` ＋ `MISS_NOT_APPLICABLE` | **#8** | ❌ 見處置 3 |
| `partial` | **七態無** | **#9** | ❌ 見處置 4 |
| （線框無此鍵） | `emits_level=False` | **#10** | **不適用**：本頁 `emits_level` 0 命中 ⇒ **不畫 #10**；⛔ 不得併進 #8 |

**逐項處置**
1. **#2 `loading`：實作待補（不是規格待決）。** 分類器有能力產生（第 3 份已證），缺的是 caller —— 本頁 **0 處傳 `in_flight=`**。**處置**：取數段包 `st.spinner`，並把 `in_flight=True` 顯式傳進上列三個呼叫點。⛔ 在補上之前**不得**拿 #3「尚未載入」冒充載入中。
2. **#5 `unwired`：本頁要拆兩種，⛔ 不得一律補旗標。** (a) `find.scenario_quickpick`／`find.pick_reason` 線框 `src:null`、畫面上**整塊不存在** ⇒ **不畫**，⛔ 不得用 #5 冒充「有這塊但沒接線」；(b) 日後若保留欄位而不接線（線框 `screen_table.unwired`「該欄整欄未接線」）→ 才傳 `wired=False` 走 #5。`:1316` 已撤回熱力圖的該旗標，⛔ 不得回填。
3. **#7／#8：規格待接線（本份的主體）。** 實作只有單一 `UI_EMPTY`、glyph `▨`「無資料」，未依 `miss_reason` 拆二。**處置**：依 ③ 的對照表拆 `⚠︎ —`／`N/A`；⛔ 不得為了對齊線框鍵數新造第 11 種徽章；⛔ 不得把 `missing` 畫成 #8（#8 重跑無效，畫錯＝給錯指引）。
4. **#9 `partial`：先降級，⛔ 不得長期停在降級態。** 依第 2 份 fail-safe：分子分母拿不到 → 恆顯示 #7，⛔ 不得退回 #1。⚠️ **但本頁 L3 已經算出分母** —— `fundamental_screener_service.py` 的 `_cov_bits`＝`f"{因子} {len(_col_scores[f])}/{len(ids)}"`（現只拼進 `note` 字串）⇒ **接到欄標題層即可畫 #9 `◧ N／M`**，這是接線工作、不是缺資料。
5. **#4 `degraded`：葉1 待補。** 現僅葉2 可達（`:1329`／`:1389`）。線框 `screen_table.degraded` 要求 🟠 標在**該欄標題旁（不是逐格）**＋就地寫「請不要把它當入選理由讀」→ 待接。

## ③ 🔴 三種數值語彙同框（**🆕 本塊整塊新訂**）

**現況（據實）**：`N/A`／`⚠︎`／`0.00`／`:.2f`／`column_config` 在 `page_find.py` **全部 0 命中**；唯一格式化 `_fmt_count()`（`:1161-1163`）只服務「檔數」語境、**不進表格** ⇒ **表上只有「有數字」與「空白」兩種**，三語彙目前分不開。

| 語意 | 二元組（`INDICATOR_SPEC` R-3） | 單元格字面 | 徽章 | 前景色 | tooltip |
|---|---|---|---|---|---|
| 真的是 0 | `(0.0, None)` | `0.00` | **#1** | `--ink` | 無；⛔ 不得因為值是 0 就畫成灰 |
| 結構上不適用 | `(None, MISS_NOT_APPLICABLE)` | `N/A` | **#8** | `--sig-grey` | 「這類標的沒有這一項」；⛔ **不計入**「本輪 N 項未評估」 |
| 缺漏 | `(None, 其餘 MISS_*)` | `⚠︎ —` | **#7** | `--sig-grey` | `MISS_TEXT.get(reason) or MISS_TEXT[MISS_CONTRACT_DRIFT]`（⛔ 不得裸查表）；計入未評估 **+1** |
| 部分計入 | 值 ＋ `partial=True` | 值帶 `*` 上標 | **#9** `◧ N／M`（標**欄標題**） | 底 `--panel-2`／字 `--sig-blue` | 「N／M 計入」 |

⛔ **不得另立第四種寫法**（含線框 `find.pe_two_kinds.live` 提案的 `⚠ 非正值`，見 ④）。

**具體做法（兩軌，軌 A 是過渡）**
- **軌 A（保留 `st.dataframe`）**：數值欄在 L5 **預先格式化成字串**再交表，欄設定 `st.column_config.TextColumn(<欄名>, help=<該欄三態說明>, width="small")`。
  ⛔ **不得用 `NumberColumn`** —— 它的 `format="%.2f"` 只吃數字、`None` 一律畫成空白，**承載不了** `N/A` 與 `⚠︎ —` 兩種字面（這正是現況只有兩種語彙的技術成因）。
  ⚠️ 限制照實寫：`column_config` **無對齊參數、無字型參數** ⇒ 軌 A 只做得到「**分得開**」，做不到第 2 份 §4 的 `text-align:end` ＋ `--mono` ＋ `tabular-nums`。
- **軌 B（目標，符合 §4）**：結果表改自繪 `.tw` HTML（`st.markdown(..., unsafe_allow_html=True)`；同一注入路徑 `_ui_kit.py:292` 本頁已在用）。套 §4：外層 `overflow-x:auto`／`1px solid --rule`／`radius:3px`／`margin-top:12px`；表頭 `min-height:36px`／`12px/700 --ink-2`／底 `--panel-2`；列高 `38px`；`table{min-width:460px}`、數值欄 `min-width:88px`、識別欄 `min-width:132px`；**數值欄一律 `text-align:end` ＋ `--mono` ＋ `font-variant-numeric:tabular-nums` ＋ `white-space:nowrap`**。

**右對齊時三種語彙寬度不一致 —— 三條處理**
1. **右對齊對齊的是右邊界**：`18.20`／`N/A`／`⚠︎ —` 右邊界一致，左側參差是正確結果。⛔ 不得用空白補齊（HTML 會摺疊空白，且會被 `to_csv` 寫進檔案）。
2. `tabular-nums` **只保證數字等寬**；`N/A`／`—` 非數字 ⇒ 缺值字面走 `--sans`、字級同數值 `13px/1.5`、色 `--sig-grey`，數字仍走 `--mono`。
3. `⚠︎` **必須是 `U+26A0 U+FE0E` 兩碼**（第 2 份 #7 逐字即此二碼）—— 少了 `U+FE0E` 會被渲染成彩色 emoji、寬度變全形而撐破 `min-width:88px`。

**手機 ≤640 卡片流（🆕 新訂；`@media`／`卡片流`／`var(--` 在 `page_find.py`＋`_ui_kit.py` 全 0 命中，三斷點同一份 `st.dataframe`）**：一列 → 一張 `.blk.t3`（`6px 9px`／`radius:2px`／`margin-top:6px`）；`代碼`＋`名稱` 升為 `.bt .t 13px/700`；`綜合分` 升為卡內 `24px/700 --mono` tabular-nums；其餘因子欄降為 `key　value` 成對（key `--mono` `9.5px` `--ink-3`；value `11.5px/700`），每卡至多 **4 對**，其餘收進〔展開佐證〕（44×44）。缺值在卡內**照樣寫 `N/A`／`⚠︎ —`**，⛔ 不得因為卡片沒有欄位就省略。

## ④ 🔴 本益比的兩種「沒有」

**(a) 應然（畫面怎麼畫）** —— **載體是第四層 `find.pe_two_kinds`，不是結果表的欄**（**總管判定 2026-09-16**：結果表整表判設計變更、⛔ 無原始值欄例外，見 ⑥）。該塊內 `本益比` 三分支，⛔ 不得同形（**重試有用性相反**）：
`PE>0` → `18.20`（#1）｜`PE<=0`（虧損股）＝**結構上不適用** → `N/A`（**#8**，tooltip「本益比為非正值（虧損），這類標的沒有這一項」，不計入未評估）｜`PE` 為 `NaN`／欄位不存在 ＝ **缺漏** → `⚠︎ —`（**#7**，tooltip「TWSE／TPEX 這一輪沒有給這一檔的本益比」，計入未評估 +1）｜逾 sanity `(0,200]` → `⚠︎ —`（`INDICATOR_SPEC.md:108` 逐字）。
⛔ **線框提案的第三符號 `⚠ 非正值` 不採用**（**WH 本組判定**）：它是 `UI_COMPONENTS` #7／#8 之外的**第四種寫法**，且 `INDICATOR_SPEC` R-1 已把 `PE<=0` 判為 `MISS_NOT_APPLICABLE` ⇒ 併入 #8 `N/A`，「非正值」三字寫進 tooltip 與第四層展開文字。→ **線框 `find.pe_two_kinds.live` 該格待同步**。

**(b) 現行阻斷點（逐字）＝ 在 L1，不在 UI**：`src/data/stock/yield_pe_fetcher.py::fetch_pe_name_maps`
`if _pe != _pe or _pe <= 0:      # NaN / ≤0 → 無本益比,不放 key` → `continue`
⇒ **`NaN`（缺漏）與 `<=0`（不適用）都變成「key 不在 `pe_map`」**，到 L5 已無任何可分辨資訊。

**(c) 落地前置＝ L1 必須先補旗標**（⛔ **不得寫成「UI 改一下就好」** —— L5 沒有第二個資訊源可以反推，在 (c) 完成前 L5 怎麼改都是猜）：依 `INDICATOR_SPEC` R-1 改回二元組 ——
`PE<=0` → `(None, MISS_NOT_APPLICABLE)`｜`NaN`／欄位不存在 → `(None, MISS_NO_INPUT)`｜整批抓取失敗 → `(None, MISS_FETCH_FAILED)`（**R-1 分支序：失敗必須排第一**，否則一次全站 outage 會被畫成滿版「不適用」而不計入未評估）。⛔ R-1 明文禁 `continue`（把該檔悄悄丟掉）。
**已登記編號（引用前已 grep 確認存在）**：**`D-08`** ＝ `INDICATOR_SPEC.md:179` §5 待修表（檔案:符號同上，分類**設計變更**）＋ 同檔 `:108`；同族 **`D-30`** ＝ `DECISION_RULES.md:191`（`else 0` 使無資料顯示成虧損）。
⇒ **在 `D-08` 修完之前，第四層只能照線框 `live` 現況那段誠實寫「本益比目前分不出這兩種」**，⛔ 不得先畫成分得開的樣子。

## ⑤ 反例自檢

**A. 選股全部失敗**（上游皆失敗 ⇒ `requested=True` ＋ `error`）
- **n1 條件表單：照畫、主 CTA 可按** —— 線框 n1 label 逐字「它同時是本頁所有灰態的出口，任何狀態下都看得到」。⚠️ 例外：因子清單本身載不進來 → `build_form_unavailable_card()` 改畫紅卡、不畫表單 ⇒ 該情境無主 CTA，走 ① 的停用態。
- **n2 總覽卡：#6 🔴 取得失敗**，大字區**留白**，⛔ 不得顯示 `0` 或上一輪殘值；`aux_errors` **逐源**列出（存活池／估值／缺貨／RS／跨季／總經位階），一源壞**不染色**其餘。⚠️ `MISS_CONTRACT_DRIFT` 在 `FAILED_REASONS` 內 → #6 且**⛔ 不得給「可以重跑」指引**。
- **n3 表：不出現**（由總覽卡負責，與實作 `:1590` 早退一致）。**n3 CSV：不同** —— 線框 `find.csv.empty` 逐字「0 列也是一個結果」「無資料時**停用但不隱藏**」，實作早退讓 CSV **一起消失** ⇒ **實作待修**：0 列／錯誤時 CSV 鈕**留在畫面上走停用態**。
- **n4 `find.pe_two_kinds`：常駐**（線框十態全寫「常駐」）＋ 就地補「這一輪估值資料取不到 —— 〈錯誤訊息〉」，⛔ 不得因為沒有結果就收起來。
- **n0 葉外**：`find.statusbar`（線框 `src` 指 `:796`，該行實為 `_load_regime`）與 `chrome.asof`（`src:null`）本頁**皆無實作** ⇒ 失敗時無可顯示；⛔ 不得用總覽卡的紅態冒充一條不存在的狀態列。

**B. 部分成功（部分標的缺因子）**
- 有值的格 #1；缺的格依 `miss_reason` 分 #7／#8，**⛔ 不得只靠顏色**（兩者同屬灰系，R-3）。
- ⛔ **缺值不得顯示成 `0`**：L3 現行**已經是對的**（缺料填 `None`，`fundamental_screener_service.py:392-393` 註解逐字「畫面顯示空白，非 0」）—— 本份要做的是把「空白」升級為 `⚠︎ —`／`N/A`，**⛔ 不是把 `None` 改回 0**。
- `partial`：分子分母拿不到 → 恆降 #7，**⛔ 不得退回 #1「正常」**；本頁分母已存在，見 ② 處置 4。
- **冷啟動（還沒點「🎯 開始選股」）：一律 #3 ⬜ 尚未載入 ＋ 灰色說明**，⛔ **不得畫成紅色錯誤**（`CLAUDE.md §1.A` 第 4 點）。
- 🔴 **涵蓋門檻擋掉的標的不得從畫面消失**（`INDICATOR_SPEC` R-3 末句「須另列『資料不足，未列入排序』清單到**個股層級**」，引用即可）—— **本頁現行違反**：畫面同源入口 `get_ranked_picks` 寫死 `drop_unscored=True`（`fundamental_screener_service.py:526`），綜合分 `None` 的檔被移出名單（`:391-393`），只在 `note` 留**彙總檔數**（`:411-416`／`:430-433`）＝ 不是個股層級。
  **處置**：第三層另列「資料不足，未列入排序」清單（逐檔 代碼＋名稱＋缺哪幾個因子）。⚠️ **⛔ 不得在 L3 直接翻掉 `drop_unscored`** —— 該旗標的既有理由是防污染 forward-test 每月凍結名單（`:512-517` 註解），翻掉會同時改到凍結紀錄；改由 L5 另取未評分清單。

## ⑥ 線框 vs 實作的差異（三項）

| 項目 | 應然（線框） | 現況（實作） | 分類與理由 |
|---|---|---|---|
| **結果表欄位** | 6 欄固定：`代號｜名稱｜評分｜本益比｜殖利率｜缺貨`，值為原始值（`18.20`） | `代碼｜名稱｜綜合分｜〈估值分／EPS分／缺貨分／RS分／跨季分〉`（依勾選動態增欄），因子值為**百分位 0–100、1 位小數**；**無殖利率欄** | **設計變更（線框待改）；⛔ 無欄位例外**（**總管判定 2026-09-16**，推翻 WH 原寫的「本益比欄例外保留原始值」，見檔尾「總管推翻」列）。三條理由：(a) 因子欄是**勾選決定的動態欄**，線框的固定 6 欄模型描述不了；(b) 百分位是 L3 排序用的同一把尺，改回原始值會讓「綜合分」與欄值兩套尺並存（違 §2.1 SSOT）；(c) ③④ 的三語彙同框**不需要**表內原始值欄當載體 —— **載體是第四層 `find.pe_two_kinds`，與結果表不同層、不同 block**（線框實測：本頁 **6 層 14 block**，`n=3`＝`find.screen_table`／`find.pick_reason`／`find.csv`，而 `find.pe_two_kinds` **單獨成層於 `n=4`**；客戶本輪指令原文亦逐字「第四層：展開佐證（本益比的兩種「沒有」）」），且**百分位欄自身即可承載三語彙**（未評分的檔百分位即 `None` ⇒ `0.00`／`N/A`／`⚠︎ —` 在**純百分位表**照樣同框）。**殖利率欄：不加**（**WH 本組判定，⚠️ 待覆核**）—— 依據是來源端「沒配息」與「還沒公告」本身分不開（該數字見檔尾「轉錄」列，**總管未獨立查證來源端**）；若該依據成立，加了只會多一欄畫不出三語彙的欄，**線框待刪該欄**。 |
| **CSV 檔名＋鈕字串** | 檔名含〈頁名〉〈區塊名〉〈**資料歸屬日**〉；block `name`「⬇ 下載結果 CSV」 | 檔名寫死 `screener_result.csv`（`page_find.py:1604`），**不含資料歸屬日** ⇒ 連兩天下載得到兩個同名檔；鈕字串 production／線框 `states.live` 為「💾 下載選股結果 CSV」 | **檔名＝實作待修；鈕字串＝待客戶拍板（兩份真相源）。** ⚠️ 檔名規則編號 **`G-24` 存在但不在** `INDICATOR_SPEC` §5／`DECISION_RULES` §8 —— 出處是 `docs/v2/audit/DRAFT_GAP_AUDIT.md:296` ＋ `S1-3B_FULL_DRAFT_SPEC.md:2874`（Part 6.3），引用時請指這兩處。鈕字串**推薦取 production 那串、線框改齊**（它已是使用者看過的字面）；⛔ 不得兩邊各留一份。 |
| **手機卡片流** | 表 → 橫捲 → 卡片流三段 | 三斷點同一份 `st.dataframe`；唯一響應機制是 `grid()` 的 `st.columns` 堆疊，**不是 CSS 斷點** | **🆕 本份新訂**（第 2 份 §4 亦自標「本塊多為新訂」）。規格見 ③ 末段；落地與軌 B 同一批，⛔ 不得只做卡片流而留 `st.dataframe` 在桌機（那會變成兩套表格規格）。 |

---
⚠️ **複驗分級**
**總管實查**＝客戶四層與線框 `n=1/2/3/4` 逐字對位（`find.screen_form`／`find.screen_summary`／`find.screen_table`＋`find.csv`／`find.pe_two_kinds`）、6 層 14 block、主 CTA `ACTION_RUN_SCREEN_LABEL`（`:422`）與「form 內只有這一顆、在預設葉」、CSV `download_button` 三參數且在 form 外、`N/A`／`⚠︎`／`:.2f`／`column_config` 在 `page_find.py` 0 命中、`yield_pe_fetcher.py` 的 `if _pe != _pe or _pe <= 0: continue` 逐字。**2026-09-16 增補**＝node 解析 `wf_page_find.js`（`global.window={WF_PAGES:[]}` shim 後 `require`）得 **6 層 14 block**、`n=3`＝`find.screen_table`／`find.pick_reason`／`find.csv`、**`find.pe_two_kinds` 單獨成層於 `n=4`**；線框 `mainCTA`＝`🎯 開始選股`／`src` 指 `src/ui/views/page_find.py:422`。
**WH 本組實查（2026-09-16）**＝線框 `layers`／`cols`／`leaf`／`src` 全表（node 實際解析）、`find.pe_two_kinds.live` 的三符號提案原文、`find.csv.empty`「0 列也是一個結果」、`D-08`（`INDICATOR_SPEC.md:108`／`:179`）與 `D-30`（`DECISION_RULES.md:191`）存在、`G-24` **不在** 兩份 spec 而在 `DRAFT_GAP_AUDIT.md:296`／`S1-3B:2874`、`drop_unscored=True` 寫死於 `get_ranked_picks`（`:526`）且 `:391-393` 會移出名單、`_cov_bits` 分母已算出、`page_find.py:1590` 早退連帶 CSV 消失、`MAX_COLS` 由 `_ui_kit.py:99` 轉 import、`⚠︎`＝`U+26A0 U+FE0E`。
**WH 本組判定（⛔ 不是量測、⛔ 不是客戶裁示）**＝ ④ 不採用 `⚠ 非正值`（併入 #8）、⑥ 結果表欄位的分類（設計變更）、⑥「殖利率欄不加」（依據為末列「轉錄」的來源端數字，**總管未獨立查證**，⚠️ 仍須覆核）、`n5` 取 `t2` 密度、葉2 與 CSV 鈕對映到 §3 次級（說明）。**皆須客戶或第二組覆核。**
**總管推翻（2026-09-16）**＝ WH 原判「⑥ 結果表 `本益比` 欄例外保留原始值」**已推翻**：線框實測 6 層 14 block、`find.pe_two_kinds` 單獨成層於 `n=4`（與 `n=3` 的結果表不同層、不同 block）⇒ 三語彙的載體本來就不在表裡，且百分位欄未評分時即為 `None`、自身即可承載三語彙 ⇒「需要一個原始值欄當載體」的前提不成立。**此為總管判定，⛔ 非客戶裁示（客戶尚未看過本份）。**
**INV-6 單組（未複驗，⛔ 不得當前提）**＝其餘盤點與所有「0 命中」類全稱句（`in_flight=`／`wired=` 0 處、`classify_ui_state` 只有 3 個呼叫點、`@media`／`var(--`／`殖利率`／`on_select` 0 命中、結果 df 欄位、葉2 兩張圖上下堆疊），**皆單次 `grep`、未做 AST**。
**轉錄（非任何一組實測）**＝殖利率「沒配息 vs 還沒公告」在來源端同為空字串（2026-08-05 前 410 檔中 99 檔為空 ≈24%）。
