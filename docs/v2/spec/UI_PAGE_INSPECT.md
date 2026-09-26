# UI_PAGE_INSPECT —— 「🔬 查一檔」頁完整版面（第 5 份）

**基準**：線框 `docs/v2/wireframe/wf_page_inspect.js`＝版面來源；元件一律引用第 2 份 `UI_COMPONENTS.md`、token 一律引用第 1 份 `UI_TOKENS.md`（⛔ 本檔不改這兩份、⛔ 不新造元件類型、⛔ 不動線框）。
實作對照 `src/ui/views/page_inspect.py::render_page_inspect()`（`:2527`，2546 行）。斷點沿用第 2 份 `≤640 / 641–880 / ≥881`。
⚠️ 本檔為 UI 設計組 WM 單組產出，未經第二組複驗（§-2 規則 6）；**全檔免責只講這一次**。⛔ 客戶**尚未看過本份** —— 全檔無「已核准／已拍板」字樣，除非該處另註出處。

## ① 四層結構（＋每層元件、三斷點、首屏）

「四層」＝ `UI_COMPONENTS` §1 卡片四層密度 `.blk.t1~t4`，由 `layers[].n` **自動掛**（`UI_COMPONENTS:18` 逐字「⛔ 非逐塊手選」）。
線框實測（WM node 解析）：**5 層 22 block、2 葉**（`l1` 單檔診斷／`l2` 多檔比較），`cols` 只有 `3/2/1` 與 `1/1/1` 兩種。`n0` 為葉外 chrome → **據實列出，不計入四層**。

| 層 | n | block key（leaf） | 卡密度 | 主徽章 | 卡標字級 | cols D/T/P |
|---|---|---|---|---|---|---|
| 葉外 | n0 | `inspect.statusbar`／`chrome.asof`／`chrome.footer`（leaf 全 null） | `t3` `6px 9px` | `.sbadge b3` `11px`／`2px 10px`／min-h 28 | `13px/700` | 1/1/1 |
| **第一層** 輸入與判型 | n1 | `inspect.form`（**3/2/1**）／`inspect.wiring_single`／`inspect.kind`／`inspect.unknown`（l1） | `t1` `15px 17px`；border **2px** | `.sbadge b1` `14.5px`／`10px 22px`／min-h 46／border 2px | `17.5px/700` | 3/2/1・其餘 1/1/1 |
| **第二層** 三張判決卡 | n2 | 個股 A：`inspect.stock.health`／`.valuation`／`.chips`；ETF B：`inspect.etf.premium`／`.dividend`／`.peer`（l1，**6 block 全 3/2/1**） | `t2` `10px 12px` | `.sbadge b2` `12.5px`／`5px 13px`／min-h 36 | `14.5px/700` | 3/2/1 |
| **第三層** 明細 | n3 | `inspect.profit`（**3/2/1**）／`inspect.pattern_measure`／`inspect.stock.detail`／`inspect.etf.detail`（l1）；`inspect.batch.form`／`inspect.batch`（**l2**） | `t3` `6px 9px` | `.sbadge b3` | `13px/700` | 3/2/1・其餘 1/1/1 |
| **第四層** 展開佐證 | n4 | `inspect.evi.cards`／`.overlap`／`.cost`（leaf 全 l1） | `t4` `5px 9px`；border 1px **dashed** | `.sbadge b4` `10.5px`／`2px 5px`／min-h 26／border 0 | `12.5px/700` `--ink-2` | 1/1/1 |

⚠️ **「357 算式」在線框沒有獨立 block** —— 它併在 `inspect.evi.cards.live` 的第 2 條列項（逐字「估值（357）—— 三段門檻（7% / 5% / 3%）與各自對應的價位；平均年現金股利、實際有配息的年數」）。**數學式**逐字取 `DECISION_RULES.md:66`：`cheap = avg_div ÷ YIELD_HIGH_DEC(0.07)｜fair = avg_div ÷ YIELD_MID_DEC(0.05)｜dear = avg_div ÷ YIELD_LOW_DEC(0.03)`（皆 `round(x,1)`，`avg_div` 量綱＝**元/股**）；SSOT ＝ `shared/thresholds.py:22-28` 三常數＋`:67 classify_stock_357_price`＋`:96-98` 反推價（WM 實查四處）。⛔ 不得在本頁另寫一份算式。

**按鈕（一律取 `UI_COMPONENTS` §3，⛔ 不新造）**
- **主 CTA `🔍 載入完整分析`**（n1）＝ §3 主 CTA：`min-height:40px`／`6px 16px`／`13.5px/700`／`radius:3px`／底 `--ink`／框 `2px solid --ink`／hover 底＋框 `--ochre`、字 `--paper`；焦點環 `2px solid --focus` `offset:2px`。SSOT `ACTION_LOAD_INSPECT_LABEL`（`:348`，＝線框 `mainCTA.src` 指的那一行，WM 實查逐字命中），在 `st.form(FORM_TICKER_KEY)`（`:2308`）內、`form_submit_button(..., type="primary")`（`:2342`）。**form 內只有這一顆、住預設葉 `l1`。**
- **葉2 `🚀 批次分析`**（n3，`l2`）＝ §3 **主 CTA 同款**（`:349` 定義、`:2373` submit，WM 實查逐字 `type="primary"`）。⚠️ **派工單寫「依 `UI_PAGE_FIND` 先例落次級」，WM 據實更正**：`UI_PAGE_FIND` 的「次級」已由該份自己在 2026-09-16（WJ）更正為「主 CTA 同款」，理由同此（實作 `type="primary"`）。⛔ 但它**不是頁主 CTA** —— 線框 `mainCTA` 欄只列葉1 那顆。
- **展開佐證觸發器**（n4，三塊各一）＝ §3 次級（展開佐證）：`min-height/width:44px`／`7px 9px`／`12.5px/600`；`inspect.evi.cards.evidence` 逐字要求「位置在**區塊標題列的最右側**、與標題同一行右對齊」，**標題本身不可點**。⚠️ `st.expander` 的控制項在標題左側、方向相反 ⇒ 須「標題列切兩欄＋右欄放次級按鈕」；實作 `st.expander` **AST 0 處**（檔內多處明寫「不用 expander」）⇒ 無既有阻礙。
- **停用態**（§3：`13.5px/500`＋`1px dashed --rule-2`＋字 `--sig-grey`）→ 兩個 form 的 `loading`（線框 `inspect.form.loading`／`inspect.batch.form.loading` 皆逐字「submit 停用」）。

**排列（三斷點）**：欄數一律取線框 `cols`，硬夾 `MAX_COLS＝3`（`tab_today.py:86` 定義、經 `_ui_kit.py:99` 轉 import，本檔不另立 3）。**裸 `st.columns(n)` 全檔 0 處（WM AST 實測）**，一律走 `_ui_kit.grid()`；`grid()` docstring 逐字「多出來的格子**換行排下一列**；天然不足一列的**保持原欄數、不硬湊三欄**」（`_ui_kit.py:135-136`）。
⚠️ **`3/2/1` 的 `tablet=2` 未落地**：`grid(items, MAX_COLS)` 三斷點恆 3 欄；`≤640` 堆成 1 欄是 Streamlit bundle 自帶的 `columns:640px` 斷點（**此為 `UI_PAGE_FIND:29` 的 WJ 實測，WM 未重驗、照此打折**）⇒ `641–880` 仍恆 3 欄，**登記為實作待修**。

**首屏可見範圍**：**三個斷點一律「需實機量測」**（比照第 3、4 份）。本頁 `var(--`／`<style>`／`@media`／`unsafe_allow_html` **各 0 命中（WM 實測）** ⇒ 排版全由 Streamlit 自身 CSS 決定；另有兩個 repo 反解不出的高度來源 —— `st.tabs` 頭高與 `st.form` 邊框高（由 Streamlit 版本決定，floor 見 `requirements.txt`）。⛔ **不猜、⛔ 不得寫推導值冒充量測。**
**唯一可宣稱的是順序（不含高度）**：`## 🔬 查一檔` 標題 → caption → 兩葉 tab 頭（`st.tabs`，`:2542`）→ 葉1 `section_header` → 輸入表單 → 接線揭露 → 判型 →（三張判決卡｜unknown 卡）→ 💰 三格 → 明細卡。⚠️ **兩葉的 body 同一輪都會跑完**（線框 `l2.note` 逐字「st.tabs 這一輪會把兩葉的 body 都跑完，葉只是視覺分組、不是執行閘門」）—— 真正的閘門是 form submit 寫進 session 的 applied key。

**表格三斷點**：**只有 `inspect.batch` 用到**（實作 `st.dataframe`，`:2492`，AST 全檔恰 1 處；四欄＝`代碼｜型別｜狀態｜明細`）。桌機／平板走 §4 表格（表頭 `min-height:36px`／`12px/700 --ink-2`／底 `--panel-2`；列高 `38px`；`table{min-width:460px}`、數值欄 `min-width:88px`、識別欄 `min-width:132px`；**數值欄 `text-align:end` ＋ `--mono` ＋ `tabular-nums` ＋ `nowrap`**）；**手機 ≤640 走 §4 卡片流**（一列＝一張 `.blk.t3`、每卡至多 **4 對** key/value，其餘收進 44×44〔展開佐證〕）。✅ 卡片流 key 的 `--ink-3` 對比已於 `UI_COMPONENTS` §4（2026-09-16 改值）實算六格全 PASS ⇒ 本頁**沒有** `UI_PAGE_FIND` 當時的無障礙阻斷。

**圖表容器**：K 線與 357 河流圖**只出現在兩支 detail 的 `live` 文字**，而那兩支現況 `unwired`（見 ③②註與 ②）⇒ **目前無任何一塊需要掛圖表容器**；接線時對映 §5「標準」`260px`（`l=8, r=8, t=35, b=20`）。⛔ 不得預先把圖表容器畫成佔位。

## ② 狀態覆蓋（線框十鍵 ∪ 實作分支 → `UI_COMPONENTS` #1~#10）

線框十態鍵 **22 塊全同序** `live|idle|loading|empty|missing|na|partial|degraded|unwired|error`；**220 格中 150 有值、70 為 null**（WM node 實測）。`null` ＝「這個區塊在這個情況下結構上不存在」，⛔ 不得畫成空卡。

| 線框鍵 | 常數（`shared/ui_state.py`） | 徽章 | 實作現況（WM AST 實測） |
|---|---|---|---|
| `live` | `UI_LIVE` | **#1** | ✅ Name 15 處（＋import 共 16） |
| `loading` | `UI_LOADING` | **#2** | ❌ **0 處**（連 import 都沒有）；`st.spinner` 亦 0 ⇒ **實作待補**，⛔ 在補上之前不得拿 #3 冒充載入中 |
| `idle` | `UI_IDLE` | **#3** | ✅ Name 7 處（＋import 共 8） |
| `degraded` | `UI_DEGRADED` | **#4** | ❌ 0 處（唯一字面在檔頭 `:219` 散文）。⚠️ **這不是缺陷**：`:219` 逐字「**本頁沒有任何一格會判 `UI_DEGRADED`**，這是刻意的」，線框 `inspect.profit.degraded` 亦自陳「本頁目前不會出現這一態」 |
| `unwired` | `UI_UNWIRED` | **#5** | ⚠️ **常數名 0 次，但該態確實會出現** —— 經 `classify_ui_state(..., wired=False)` 間接產生（`:2197`，AST 全檔**恰 1 處**），載體是兩支 detail 卡 |
| `error` | `UI_FAILED` | **#6** | ✅ Name 7 處（＋import 共 8）；字面為 `"failed"`，以常數為準 |
| `empty`／`missing` | `UI_EMPTY` ＋ `MISS_*` | **#7** | ⚠️ Name 1 處（＋import 共 2）；實作只有單一 `UI_EMPTY`，**未依 `miss_reason` 拆 #7／#8** |
| `na` | `UI_EMPTY` ＋ `MISS_NOT_APPLICABLE` | **#8** | ❌ 同上，⛔ 不得把 `missing` 畫成 #8（#8 重跑無效，畫錯＝給錯指引） |
| `partial` | **七態無** | **#9** | ❌ 0 處 |
| （線框無此鍵） | `emits_level=False` | **#10** | **不適用**：`emits_level` 在本頁 **0 命中**（另 2 處 `discriminative` 在 `:220`／`:230` 散文、非 code）⇒ **不畫 #10**；⛔ 不得併進 #8 |

⇒ **實際會出現在畫面上的是 5 態：#1／#3／#5／#6／#7。** #2／#4／#8／#9 皆未落地（#4 為刻意，其餘三者待補）。
**`partial` 的逐字要求（線框）**：`inspect.profit` 標「**3 / 5 格已接線**」並明列還沒接的是〔稅後淨利率〕〔ROE〕；`inspect.batch` 標「**N/M 檔成功**」；兩支 detail「**該段標 `N/M`**」。
⚠️ 依 §2 fail-safe：**分子分母拿不到 → 一律降 #7『缺漏 · 可重跑』，⛔ 不得退回 #1『正常』。**
🔴 **WM 判定（須覆核）**：`inspect.profit` 的「3 / 5」講的是**接線度**，`inspect.batch` 的「N/M」講的是**資料涵蓋度** —— 兩者**母體不同類**。⛔ 共用 #9 時**必須在 tooltip 寫明母體**（「5 格中 3 格已接線」vs「M 檔中 N 檔算出來」），否則使用者會把「還沒做」讀成「這一輪沒拿到」。此為 `UI_PAGE_FIND` ② 處置 4 同型的母體歧義。

## ③ 🔴 三處「線框說有、實作沒有」

> ⛔ **本節每一處都分三段寫：(a) 應然／(b) 現況實測／(c) 要做到需要什麼。⛔ 不得只讀 (a)。**
> 判準沿用客戶本輪對本益比的裁示逐字 ——「**不要假裝做得到**」。

### ①｜獲利能力 5 指標「3 欄 × 2 排」

- **(a) 應然**：線框 `inspect.profit` **確實指定 3 欄 × 2 排**，`live` 逐字「**3 欄 × 2 排，共 5 格**（5 ÷ 3 → 第 2 排 2 格 ＋ 1 個空位）」；第 1 排〔毛利率〕〔營業利益率〕〔安全邊際〕已接線，第 2 排〔稅後淨利率〕〔ROE〕**明標未接線**。`unwired` 態另逐字「🔴 **現況比這裡畫的更糟** —— 這兩格在本頁**連一張『未接線』的卡都沒有**，畫面上只有一排三格」。📌 **5 格的來歷（線框 `evidence` 逐字，⛔ 照這樣寫）**：「**總管拍板（客戶未表示偏好、授權總管決定）＋2026-09-14**」，⛔ **不是「客戶核准」**。⚠️ 線框亦自陳「**核准線框**（＝ `docs/wireframes/stock_ia_v1.html`）**在這一格自己前後不一致**」（`:824` `n` 欄寫 2 排、`:825-827` 格子清單只列 3 個），該不一致登記於 `wf_global.js` 的 `DEV-20`。
- **(b) 現況實測（WM 實查）**：`build_profit_cards`（`:2010`）的 `_labels` 逐字 `("毛利率", "營業利益率", "安全邊際")`（`:2022`）、`_keys` `("gross_margin", "operating_margin", "safety_margin")`（`:2023`）—— **只有 3 格**。`grid()` 「天然不足一列的保持原欄數、不硬湊三欄」⇒ 3 格 ＝ **恰好一排，沒有第 2 排**。**稅後淨利率與 ROE 在畫面上完全不存在**：無卡、無佔位、無 unwired 標示。⚠️ `page_inspect.py:49-50` 註解逐字「第 2 排留給後續補齊的淨利率 / ROE」、`:2405-2407` 的 `section_header` 標題也寫「**3 欄 × 2 排**」而下一行（`:2408`）只送 3 張卡 —— **那是意圖與標題，不是實作**。
- **(c) 要做到需要什麼**：真正達成 (a) 需把 L3 `financial_health_engine` 已有的 `Net_Margin` 與 `ROE` 接進來（⚠️ 「上游五欄都有回」為線框單組實測、未實跑，照此打折）；**或至少先畫兩張 `#5 這項還沒做` 的 unwired 卡把第 2 排佔出來**。
  🔴 **WM 本組建議（⛔ 非客戶裁示、⛔ 非總管拍板）：以「先畫兩張 unwired 卡」為現行落地態。** 三條理由：(i) 線框 `unwired` 態要求的正是這個；(ii) 不需要動 L3，落在本頁檔案邊界內；(iii) 現況「只有一排三格」會讓使用者**看不出自己少看了兩個指標** —— 那是 `CLAUDE.md §1` 要防的「把缺口掩蓋成完整」。⚠️ 接線時另須一併改兩處：`:2065` 寫死的「其餘兩格」在 5 格後就是錯的；ROE 那一格上游回的是 `Leverage_Warning`（槓桿警語）而非 pass/fail 判決語，**⛔ 不得照抄前三格的形狀、⛔ 不得替它編一句中文判讀語**（`GROSS_/OPERATING_/SAFETY_MARGIN_LABELS` 三張對照表沒有它們的）。

### ②｜成本口徑（加權移動平均 vs FIFO）

- **(a) 應然**：線框 `inspect.evi.cost.live` **有指定**，逐字「本系統採**加權移動平均法**，與部分券商 **FIFO** 對帳單可能產生差異。」（同句逐字見 `S1-3B_FULL_DRAFT_SPEC.md:868`、`S2-UI_SPEC.md:749`，WM 實查兩處命中），`D-2` 標為「**客戶指定必含**」。
- **(b) 現況實測（WM 實查）**：**`FIFO` 與 `加權移動平均` 在 `src/`＋`shared/` 全 0 命中**（單次 grep）。`avg_price` 是**使用者自己填在 Google Sheets 的欄位**（`gsheet_portfolio.py:82` `_HEADERS = ['name','ticker','lots','avg_price','updated_at']`），**系統不計算成本**；同代號重複列的處置是「保留首見、丟棄其餘」（`gsheet_sa_reader.py:107-114`，註解逐字「v1 保留首見（**加權合併屬 v2**）」）。且**查一檔頁根本不碰成本**：`成本`／`均價`／`avg_price` 在 `page_inspect.py` **0 命中**。
- **(c) 三個未解問題（逐一登記，⛔ WM 不代為決定）**：
  1. **落點偏離**：`S1-3B:854`／`S2-UI_SPEC:710` 的 D-2 落點是「**頁4 葉1／頁4 葉2／Part 5 再平衡區塊**（＋一個已失去載體的基金站落點）」—— **四個裡沒有本頁（頁3 🔬 查一檔）**。線框自陳是依派工單加入，旗標「★待拍板（落點）／偏離核准線框／單組結論／未驗證」。⇒ **這段該不該出現在查一檔頁，本身就未定。**
  2. **權重未定義**：`S1-5_HOLDINGS_MODEL.md:640` **P-1** 指出母法只說「統一採加權移動平均法」，**沒說權重是什麼（金額 vs 單位數）**；P-1 本身是**建議**，決定權未行使。
  3. **實作不存在**：見 (b)。
  ⛔ **在 (b) 成立的前提下，畫面上不得寫「本系統採加權移動平均法」** —— 那會是宣稱一件系統沒做的事（違 `CLAUDE.md §1`，同客戶「不要假裝做得到」）。**現行只能誠實寫**（文案擬稿，⛔ 非客戶逐字）：`now`＝「**這裡的成本是你自己填的均價**」；`why`＝「這一頁沒有在替你算成本 —— 你在持股表填的那個均價，系統原樣拿來用、**不會替你重算**；同一個代號填了兩列時，**只留第一列**，另一列會被丟掉並列出來給你看。」⛔ 使用者看到的字面不得出現「FIFO」「加權移動平均」「D-2」「L1」這類內部詞或系統做不到的口徑宣稱。
  📌 **落點若拍板為「放」**：線框自己的提案是**綁在 ETF 明細第 3 段「配息紀錄與以息養股試算」的佐證裡**（該段現況 `unwired`），⛔ 不掛整頁 —— 避免在沒有成本欄位的區塊旁邊出現成本說明。**此為線框單組提案，WM 轉錄、未背書。**

### ③｜個股與 ETF 重疊 —— ⚠️ 它的意思與字面不同

- **(a) 應然**：線框 `inspect.evi.overlap.live` 逐字「本頁把個股與 ETF 放在同一個入口，但**兩邊看的東西幾乎完全不同** —— 逐項比對的結果是 **13 個個股概念在 ETF 那邊完全沒有、6 個 ETF 概念在個股那邊完全沒有**」＋「**合併的是入口與骨架，不是內容** —— 所以你查 ETF 時看不到本益比、查個股時看不到折溢價，**那不是漏了，是它本來就不存在**」。
  ⛔ **它是「為什麼兩種標的共用一頁」的設計理由揭露，不是資料功能。⛔ 不得寫成、也不得實作成「這檔股票被哪些 ETF 持有」。**
- **(b) 現況實測（WM 實查）**：repo 內只有 **ETF × ETF** 持股重疊 —— `etf_calc.py:877 calc_holdings_overlap_pct(h1, h2)`（Σ min 權重）與 `:908 calc_jaccard_overlap(h1, h2)`（|A∩B|/|A∪B|），兩者都吃**兩份 ETF 持股**。「某檔個股被哪些 ETF 持有」的反查**查無實作**（單次 grep，0 命中）。
- **(c) 要做到需要什麼**：(a) 的揭露文字**現在就能上**（它不需要任何資料）；⛔ 但 **13／6 這兩個數字線框自標「紅隊比對結果、本組未複驗」** ⇒ 引用時**必須照此標明**，⛔ 不得當成已查證的事實，⛔ 不得把它寫成畫面上的權威統計。若要讓它成為可宣稱的數字，需另派一組逐項重做該比對。反查功能若真的要做，需新增 L1 取數 ＋ L2 反向索引，**那是新功能、不在本頁範圍**。

## ④ 反例自檢

**A. 全部失敗**（送出後上游皆失敗）
- **n1 表單：照畫、主 CTA 可按** —— 線框 `inspect.form.error` 逐字「**表單本身不會壞**；送出後的錯誤由下方各區塊各自顯示（**不會整頁變紅**）」。三格維持已填值。
- **n1 `inspect.kind`：#6 🔴 判型失敗**（附錯誤型別），逐字「**這種時候不會替你猜一個型別**」。判型失敗 ⇒ 兩支分支的判決卡**都不畫**。
- **n2 三張判決卡：各自判態，一格紅不染另外兩格**（WM 實查：三張卡各自走 `classify_ui_state`，`build_health_card` `:1781`／`build_valuation_card` `:1838`／`build_chips_card` `:1918`，Card 構造分別在 `:1808`／`:1886`／`:1985`）。大字區**留白**，⛔ 不得顯示 `0` 或上一輪殘值。
- **n3 `inspect.profit`：出錯時整排一起紅**（線框 `error` 逐字「**出錯時是整排一起紅，不是單一格紅** —— 上面『一格缺不影響其他格』只適用於**缺資料**，不適用於**出錯**」；實作各格共用同一個 `prof.error`，`:2041-2044`）。
- **n4 三塊佐證：常駐** —— `evi.overlap`／`evi.cost` 的 `error` 態線框逐字「同上」（揭露文字不隨狀態消失）；`evi.cards` 的觸發器仍在，展開後寫錯誤型別。⛔ 不得因為沒有結果就收起來。
- **n0 葉外**：`inspect.statusbar`／`chrome.asof`／`chrome.footer` 在 `page_inspect.py` **0 命中（WM 實測）**；其中 `statusbar`／`asof` ⇒ 失敗時無可顯示，⛔ 不得用判決卡的紅態冒充一條不存在的狀態列。
- ✅ **`chrome.footer`（頁尾免責，`D-1`「每一頁都要有」）＝ 已澄清：非缺陷**（**總管更正 2026-09-16**；~~原登記「現況本頁沒有 —— 登記為實作待修」~~ 保留在此標明更正理由，⛔ 非靜默刪除）。**WQ 本組重跑確認的三條證據**：(i) `app.py:514-517` `def _render_footer()` 就是 `D-1` 的免責頁尾，逐字「⚠️ 台股AI戰情室 v3.0 · 僅供學術研究，非投資建議，盈虧自負」；(ii) `app.py:604` 在 `_render_tab_isolated(_IA_VIEWS[_IA_PAGE], …)`（`:603`）**之後**、`st.stop()`（`:605`）**之前**呼叫 `_render_footer()` ⇒ **每一個 IA 頁都會拿到頁尾，不分頁面**；(iii) 該處註解（`app.py:599`）逐字「免責聲明**照樣出**(法遵文字,不分頁面),故 `st.stop()` 前先呼叫 footer。」 **誤判原因**：原查法拿「頁面自己有沒有畫 footer」當判準（`grep footer page_inspect.py`），等於假設頁尾須由**頁面自己**畫；實際上它是 **L6 `app.py` 統一出的跨頁 chrome**，而本表 `n0` 本來就是葉外 chrome（`:10`「不計入四層」、`:14`「leaf 全 null」）⇒ **頁面 0 命中是正確設計，不是缺陷**。⛔ 不得據此在 `page_inspect.py` 內另畫一份頁尾（`app.py:512-513` 註解逐字已點名「複製第二份 = 兩邊會漂移」）。
- **錯誤路徑體質（WM AST 實測）**：14 個 `try` 區塊、**`except: pass` 0 處**、錯誤一律 `print` ＋ 轉 `repr(e)` 上畫面（19 處）—— 與 `CLAUDE.md §1` 同向，⛔ 接線時不得改成靜默吞掉。

**B. 部分成功**
- **葉1**：有值的格 #1；缺的格依 `miss_reason` 分 #7／#8（**待接線**，見 ②），**⛔ 不得只靠顏色**（兩者同屬灰系）。線框 `inspect.profit.empty` 逐字「⚪ **〈格名〉：資料缺漏** —— **不是**紅的『辛苦生意』（一格缺不會把其餘各格一起染色）」；`empty`（整張損益表沒回來）與 `missing`（單一欄位沒抓到／單位異常）**兩種缺值、兩句話**，實作已有 `PROFIT_GAP_WHY` vs `PROFIT_MISS_WHY` 兩個常數，⛔ 不得共用一句。
- **葉2 部分失敗：整張卡維持 #1，⛔ 不轉紅** —— `build_batch_card`（`:2211`）docstring 逐字「『其中幾檔失敗』**不讓整張卡轉紅** …… 紅色留給『**整批都算不出來**』那一種」；失敗代碼進 facts（逐字「其餘照常顯示，**不整批作廢**」）。⭐ **失敗的那一列不會從清單裡消失**（線框 `error` 逐字：該列**保留**、列首標紅、各格 `—` ＋ `⚠︎`）。⛔ 不得把失敗列篩掉。
- **`⚠︎` 必須是 `U+26A0 U+FE0E` 兩碼**（`UI_COMPONENTS` #7 逐字即此二碼）；缺值字面走 `--sans`、色 `--sig-grey`，數字仍走 `--mono`。⛔ **缺值不得顯示成 `0`。**
- **冷啟動（還沒按「🔍 載入完整分析」）：一律 #3 ⬜ 尚未載入 ＋ 灰色說明**，⛔ **不得畫成紅色錯誤**（`CLAUDE.md §1.A` 第 4 點）。線框 `inspect.form.idle` 逐字要求表單下方常駐一句「**按下去才會開始取數。在你按之前，這一頁不會發出任何一次網路連線。**」
- **每張卡各自隔離**：`render_card_isolated`（`_ui_kit` 本體，本頁 `:2273` 呼叫、包裝器 `_render_one` `:2265`）包住每張卡 ⇒ 一張卡拋例外不會炸掉整頁。
- 🔴 **WM 本組新發現（須覆核，⛔ 非派工單指定的三處）**：線框 `inspect.batch.live` 逐字「**點任一列就地展開該檔明細**」＋「✅ **整列可點**」，但實作 `st.dataframe`（`:2492`）的 **`on_select`／`selection_mode` 0 命中（WM AST＋grep）**，下鑽走的是另一顆 `st.selectbox("下鑽看某一檔的判決卡", …)`。⇒ **「整列可點」在本頁未落地**，現況是「選單挑一檔」。⛔ 不得寫成已做到；**分類待判**（實作待修 vs 線框待改）。

## ⑤ 特別注意 —— 判型三分支（＋實際存在的第四條路）

`classify_kind()`（`:876`）→ L2 `classify_asset_kind`。線框 `l1` 葉名逐字「單檔診斷（**個股／ETF/unknown 三分支**）」。
1. **個股（A）** → n2 走 `inspect.stock.{health,valuation,chips}`、n3 走 `inspect.profit` ＋ `inspect.stock.detail`。
2. **ETF（B）** → n2 換成 `inspect.etf.{premium,dividend,peer}`、n3 走 `inspect.etf.detail`。**骨架同、內容全換** —— 與 A **沒有一個欄位共用**（見 ③③）。
3. **unknown（C）** → `build_unknown_card`（`:1754`），label 逐字「**判不出型別 —— 已停在這裡**」。線框逐字「**第三條路，不是紅態**」、`error` 態逐字「**這一格不會變紅** —— 判不出型別是一個結果，不是故障」⇒ 徽章 **#3／#7 灰系，⛔ 不得用 #6 🔴**。**兩支明細都不畫**（WM 實查）。⛔ **不得替使用者猜一邊**（線框逐字「**本站不替你選一邊**」）。
4. ⚠️ **第四條路（實作有、線框葉名沒寫）**：冷啟動／代碼空白時畫**個股三格的 idle 骨架**（`:2462-2467`，WM 實查；`section_header` 逐字「等一下會拿到什麼（尚未載入）」＋「以**個股**分支的三格預覽」）。⇒ **畫面上會出現「看起來像個股」的骨架，但系統其實還沒判型。** 該支 `requested=False`、**一行 L3 都不會發**。⛔ 不得把它讀成「已判為個股」；規格要求該骨架**必須保留上述那句預覽揭露**，⛔ 不得省略。

⛔ **全頁禁止買賣建議**：本頁所有判決語（好生意／本業獲利／抗震極強／便宜·合理·昂貴）**只描述標的狀態**；⛔ 不得延伸為「該買／該賣／該加碼」—— 那需要代入只有讀者知道的資金、期間、風險承受度與既有部位。357 三段價位是**門檻反推價**，⛔ 不得標成進出場點。

---
⚠️ **複驗分級**

**總管實查**＝（本檔**無**此類項目 —— 總管未對本頁下過實查結論；⛔ 不得把派工單轉述當成總管實查）。
**總管更正（2026-09-16）**＝**僅 `chrome.footer` 一項**。原登記「本頁 0 命中 ⇒ 實作待修」為**總管誤判**，誤在**拿「頁面自己有沒有畫 footer」當判準，但頁尾是 L6 `app.py` 統一出的跨頁 chrome**（`:514-517` 定義、`:604` 於 `st.stop()` 前對每一個 IA 頁呼叫、`:599` 註解逐字「不分頁面」）⇒ **非缺陷**；三條證據由 WQ 於 2026-09-16 自行重跑確認，全文見 ④A。⚠️ 本欄實查對象是 `app.py`（跨頁 chrome），**不是** `page_inspect.py` 的盤點 —— 上一行「總管未對本頁下過實查結論」仍然成立。⛔ 本次**只動這一項**，本檔其餘登記（`on_select`／`selection_mode`、5 指標 3 格、成本口徑、個股與 ETF 重疊…）一字未改。
**INV-7A 單組（實作面，未複驗，⛔ 不得當前提）**＝`page_inspect.py` 的全部盤點。⚠️ **WM 已就下列項目自行重跑並確認一致**：`st.button`／`st.download_button`／`st.expander`／裸 `st.columns` **皆 0**、`form_submit_button` **恰 2**（AST）；`UI_LIVE 16`／`UI_IDLE 8`／`UI_FAILED 8`／`UI_EMPTY 2`（＝AST Name 用法＋import）、`UI_LOADING`／`UI_DEGRADED`／`UI_UNWIRED` **AST 0**；`wired=False` **恰 1 處**（`:2197`）；14 `try`、`except: pass` **0**；`build_batch_card` 的「部分失敗維持 live」。**其餘未重跑者照單組打折。**
**INV-7B 單組（線框面，未複驗，⛔ 不得當前提）**＝`wf_page_inspect.js` 解析結果。🔴 **WM 覆核發現其元件對映有一處錯**（葉2 CTA 落「次級」，已於 ① 就地更正並附理由）；另「`n0`→`t3`」不在 `UI_COMPONENTS` 條文內，是第 3、4 份頁規格建立的先例，本檔沿用。⚠️ **WM 已 node 重跑並確認一致**：**5 層 22 block、2 葉**、cols 只有 `3/2/1` 與 `1/1/1`、十態鍵 22 塊同序、**220 格中 150 有值 / 70 null**、`mainCTA` 逐字與其 `src`、`inspect.profit`／`evi.cards`／`evi.overlap`／`evi.cost` 四塊的 `live`／`unwired`／`evidence` 全文。
**WM 本組實查（2026-09-16）**＝上兩段標「已重跑」者，另加：`shared/thresholds.py:22-28`／`:67`／`:96-98` 與 `DECISION_RULES.md:66` 的 357 算式四處逐字；`FIFO`／`加權移動平均` 在 `src/`＋`shared/` **0 命中**；`成本`／`均價`／`avg_price` 在 `page_inspect.py` **0 命中**；`gsheet_portfolio.py:82` `_HEADERS`；`gsheet_sa_reader.py:107-114`；`etf_calc.py:877`／`:908` 皆吃兩份 ETF 持股、個股反查 0 命中；`S1-3B:854`／`:868` 與 `S2-UI_SPEC:710`／`:749` 的 D-2 落點與逐字文案；`S1-5:640` P-1；`MAX_COLS=3`（`tab_today.py:86` → `_ui_kit.py:99`）與 `grid()` docstring（`_ui_kit.py:135-136`）；`var(--`／`<style>`／`@media`／`unsafe_allow_html` 在本頁 **各 0**；`on_select`／`selection_mode` **0 命中**；`emits_level` **0 命中**。
**WM 本組判定（⛔ 不是量測、⛔ 不是客戶裁示，全部須覆核）**＝(1) ③① 建議「先畫兩張 unwired 卡」為現行落地態；(2) ③② 現行誠實文案擬稿與「⛔ 畫面不得寫『本系統採加權移動平均法』」；(3) ② 末段「`profit` 的 3/5 與 `batch` 的 N/M 母體不同類、須在 tooltip 寫明母體」；(4) ④B 末項「整列可點未落地」的發現與其**待判分類**；(5) 葉2 CTA 對映到 §3「主 CTA 同款」（⛔ 更正派工單所述的「次級」）；~~(6) `chrome.footer` 缺頁尾免責登記為實作待修~~ → **已由總管更正為「非缺陷」，移至上方「總管更正（2026-09-16）」欄**（⛔ 舊判定保留不刪）。
**轉錄（非任何一組實測，引用時照此標明）**＝「13 個個股概念／6 個 ETF 概念 0 命中」（線框自標紅隊比對、線框未複驗）；「上游 L3 五欄都有回」（線框單組讀 `financial_health_engine`、未跨檔窮舉、未實跑）；Streamlit bundle 的 `columns:640px` 斷點（`UI_PAGE_FIND:29` WJ 實測，WM 未重驗）。
**窮舉宣稱的方法（逐項標明）**＝「0 處／恰 N 處」凡涉及 `page_inspect.py` 呼叫與常數者一律 **Python `ast` 全檔掃描**；涉及跨檔字串（`FIFO`／`加權移動平均`／個股反查）者為**單次 `grep`**，⛔ 非 AST、⛔ 不得當窮舉；線框計數一律 **node 解析** `wf_page_inspect.js`。
