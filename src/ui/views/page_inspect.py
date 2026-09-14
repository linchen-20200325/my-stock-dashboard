"""src/ui/views/page_inspect.py — IA v2 第 3 頁「🔬 查一檔」的**版面落地**（L5 UI）。

規格出處：`docs/wireframes/stock_ia_v1.html` 的 `PAGES[2]`（id=`inspect`）。
單一職責（線框 `job` 原文）::

    一個代碼進去，一份判決出來 —— 系統判型，然後走兩套完全不同的明細。

兩葉（線框 `leaves` 原文）::

    葉1 單檔診斷（個股／ETF/unknown 三分支）
    葉2 多檔比較（可混貼）

═══ 這個檔**不是**什麼（先讀這段）═════════════════════════════════════
它**不是**一套新的判型規則、**不是**一套新的財報判讀、**不是**新的狀態模型。

- **判型**一律走 L2 純函式 `compute.etf.asset_lag.classify_asset_kind()`
  （`00` 開頭→etf、4 碼首位 1-9→stock、其餘→unknown）。
  本檔**不自己寫前綴規則**，也不「順手」補一條 heuristic 去縮小 unknown 的範圍。
- **個股 / ETF 的指標**一律走 L3 `services.dividend_station_service.fetch_metrics()`
  —— 它自己就按 `asset_kind` 分兩條路（個股走財報體檢＋KD，ETF 走折溢價／配息／
  同儕），本頁只是把它攤到畫面上。本檔**不自己算任何一個數字**。
- **獲利能力三格**走 L3 `stock_grp_service.get_financial_statements()`
  → L3 `financial_health_engine.analyze_financial_health()` 的
  `profitability_module`。門檻（毛利率 40%、安全邊際 60%…）住在 L0
  `shared/financial_health_thresholds.py`，判讀在 L3，**本頁只讀 Status 字串**。
- **四態**一律走 L0 `shared/ui_state.py::classify_ui_state()`。
- **卡片型別**（`Card` / `Note`）與**版面上限** `MAX_COLS` 一律 import
  `src/ui/tabs/tab_today.py` 與 `src/ui/views/_ui_kit.py`，本檔**一個都不複寫**。

~~**本檔沒有 production caller**（`app.py` 掛載另案；本批一個字都沒有碰 `app.py`、
`page_today.py`、`page_find.py`、`_ui_kit.py`、`src/ui/tabs/**`、`shared/**`）。~~
舊分頁（`tab_stock` / `etf_tab_*`）不動、不下架。

⚠️ **2026-09-08 FE-36 事實更正 —— 刪除線是有意識保留，不是漏刪。**
那句在本檔剛落地那一批為真；**之後接線的批次沒有回頭改它** ——
也就是說 「掛載另案」那個「另案」早就落地了，**這是 `b5bdb36`（側欄 radio 改動）之前就已經存在的漂移**，
不是這次弄壞的（一併收掉，但據實區分責任）。
**現行**：`app.py::_ia_view_inspect()` 在側欄「🆕 新版戰情室（試用中）」radio
選到本頁時 late import 並呼叫 `render_page_inspect()`；**沒被選到時本檔連 import 都不發生**
（`tests/test_ia_v2_sidebar_nav.py::TestNothingRunsUntilYouPick`）。
⚠️ **有 caller 之後，這一頁的每一個 bug 都是使用者看得到的** ——
不得再拿「反正沒有人在用」當放寬任何守衛的理由。
掛載形態由 `tests/test_p0x_view_mount_claims.py` 釘住：再改一次就轉紅。

═══ 四大鐵律的落點 ═══════════════════════════════════════════════════
1. **3 欄上限** —— 一律 `_ui_kit.grid()`（內部硬夾 `MAX_COLS`）。
   全檔 **0 個**裸 `st.columns(n)`。線框 F11 點名的兩處降階都在這裡落地：
   6 個 MA checkbox 原 `st.columns(6)` → **3 欄 × 2 排**；
   💰 獲利能力診斷原 `tab_stock.py` 的 `st.columns(5)` → **3 欄 × 2 排**
   （本頁只畫線框列出的 3 格，第 2 排留給後續補齊的淨利率 / ROE）。
2. **Form 防重繪** —— 本頁**兩個 form、各一顆 `form_submit_button`**
   （葉1 `form_ticker`、葉2 `form_batch`）。線框註記本頁是「**全站最大 form
   受益點**」：代碼 + 期間 + 6 個 MA + 判型覆寫，改一個就整站 rerun 一次。
   form 內**沒有**任何 `st.button` / `st.download_button`（線框 F11：實跑即拋
   `StreamlitAPIException`）。widget 當下值與**已套用值**分家，下游只讀後者。
3. **四態分離** —— 見下面兩段（本頁最容易寫錯的地方，而且錯法有三種）。
4. **空狀態三要素** —— 一律 `tab_today.Note(now, why, where)`，
   三者非空、且不得自帶狀態 glyph（`__post_init__` 會 raise）。

⚠️ **鐵律 2 的同一個已知缺口，本檔沿用頁 2 的處置：就地實作 + 登記，未改共用層。**
`_ui_kit.single_submit_form()` 只支援一組 `st.radio`；本頁葉1 需要
`st.text_input` ＋ `st.selectbox` ×2 ＋ `st.checkbox` ×6，葉2 需要
`st.text_area` ＋ `st.selectbox`。兩支表單函式沿用它**完全相同的契約**
（一個 form / 一顆 submit / form 內無 button / widget 值與已套用值分家），
但**沒有**去改 `_ui_kit.py`（頁 1 已交付的共用層，本批的檔案邊界之外）。
→ **交接事項（與頁 2 是同一項，不是第二項）**：`single_submit_form` 應泛化成
「form 內容由 caller 提供的 callback 畫、本函式只保證單一 submit 與已套用值寫入」，
屆時本檔的 `_render_ticker_form()` / `_render_batch_form()` 與頁 2 的
`_render_screen_form()` **三支一起刪掉**。

═══ `requested=` 的來源（本頁**兩個** gate，一個都不是從資料反推）═══════
L0 的鐵律：**`idle` 只能由上游帶下來，禁止由 `if not data:` 推導。**
頁 1 就是在這裡被紅隊抓到恆真式（`get_allocation()` 永不回 `None`，
於是 `requested=(alloc is not None)` 恆為 True、冷啟動沒有 idle 態）。

  1. **葉1 全部區塊** ← `SS_APPLIED_TICKER in session_state`。
     那個 key **只有** `_render_ticker_form()` 的 submit 分支會寫。
     ⚠️ 不是 `bool(ticker)`、不是 `metrics is not None`、不是 `len(rows) > 0`。
  2. **葉2 批次表** ← `SS_APPLIED_BATCH in session_state`。
     那個 key **只有** `_render_batch_form()` 的 submit 分支會寫。

本頁的下游 gate（`StockReadout.requested` / `EtfReadout.requested` /
`ProfitabilityReadout.requested`）**全部由上面兩個帶下來**，而且都多帶一個條件：
**判型判成這一支才算「有人叫過它」**。使用者輸入 `00878` 時，
沒有任何人要求過個股財報 —— 個股那三格的正確狀態是 `idle`，不是 `empty`。

⚠️ **`requested=False` 時本檔一行 L3 都不呼叫。** 沒有輸入就不會有值，
`classify_ui_state` 那條「沒被叫過卻有值 → `ValueError`」在結構上跑不到。

═══ 三種「沒有結果」**絕不可混**（本頁的 §1 主戰場）═════════════════════
    還沒輸入代碼        → `UI_IDLE`   （灰。**還沒有人叫過**）
    輸入了、查無此代碼  → `UI_EMPTY`  （灰。**這是一個有效的結果**，
                                       不是故障、也不是還沒查；卡上明講）
    上游掛了            → `UI_FAILED` （紅。**唯一准用紅色的狀態**）

**而本頁還有第四種**，線框特地為它補畫了一個區塊（葉1-C，原文
「**第三條路 · 不是紅態**」）：

    判不出是個股還是 ETF → `UI_EMPTY` + `MISS_NOT_APPLICABLE`（灰）

⛔ **它絕對不可以是 `failed`。** 判型失敗不是系統壞掉 —— `classify_asset_kind`
對美股 / 指數 / 興櫃 / 打錯的代碼一律回 `unknown`，那是**這個輸入不在本站的
射程內**，不是「本站壞了」。線框 note 原文：「v1 的查一檔只有『未輸入』灰態與
『抓取失敗』紅態，`unknown` 無處可去 —— 那會逼實作把它塞進其中一個，
**兩個都是說謊**。」
⚠️ 也不可以是 `unwired`：`unwired` 的語意是「**這個功能沒接**」，
但判型是接好的、而且**正常運作**，它只是誠實地回答「我判不出來」。
用 `MISS_NOT_APPLICABLE`（L0 原文：「這類持股不適用這盞燈（不是壞掉）」）
是因為它是 `FAILED_REASONS` **之外**的原因 → L0 讓它留在灰色。

═══ 判型可手動覆寫（線框 F4，不是可有可無的裝飾）═══════════════════════
線框把這一條寫成硬要求，理由是 repo 已記錄的同型事故：`station_cards.py`
記著「型別大小寫打錯一個字母 → **可信度虛高到 100% 並打開巡航 gate**」。
型別分支推到流量最高的頁，**必須讓使用者看得到系統判成什麼、並且改得動**。
→ 表單裡有一個「判型」下拉（自動 / 個股 / ETF），判決卡的 facts
**永遠**顯示「系統判的是什麼」與「這一輪實際用的是什麼」兩列，覆寫時兩列會不同。

═══ 取數：**唯一**的規則是「一律走 L3」═══════════════════════════════
    判型            L2 `compute.etf.asset_lag.classify_asset_kind` / `pick_benchmark`
                      （純函式、零 I/O；L5→L2 下行 import，C3 規則 5 合規）
    357 位階        L2 `compute.strategy.v5_modules.calc_dividend_yield_357`
                      （同上，純函式；**輸入**走下一行那支 L3）
    個股配息        L3 `services.valuation_service.get_stock_dividends`（本批新增）
    近 20 日籌碼    L3 `services.stock_chips_service.get_chips_readout`（本批新增）
    個股指標        L3 `services.dividend_station_service.fetch_metrics(t, 'stock')`
    ETF 指標        L3 `services.dividend_station_service.fetch_metrics(t, 'etf')`
    獲利能力三格    L3 `services.stock_grp_service.get_financial_statements`
                      → L3 `services.financial_health_engine.analyze_financial_health`
    FinMind token   L0 `src.config.config.get_finmind_token`

**零 L1 import、零 `requests` / `yfinance` / FinMind / `pd.read_csv(url)`、
零 SQL / parquet 讀寫、零 `@st.cache_data` / `@st.cache_resource`、
零 inline `ttl=`、零底線開頭的跨檔私有符號、零 `from app import`。**
（前車之鑑：`CLAUDE.md §8.2.A.2` 的 **V-SMART-CACHE-1**〔L5 自建 5 個 cache〕
與 **V-PICKER-PRIV-1**〔L5 直取 L1 的 `_fm_raw_headers`〕。）
⚠️ 本頁**受 `tests/test_c3_layering_guard.py` 管**（`_PATH_LAYERS` 已含
`src/ui/views/` → L5），違反 R4／R5 是 CI 紅燈，不是假綠燈。

═══ 本批**新接上**的兩項（2026-09-07 FE-18）═══════════════════════════
（**後續 2026-09-07 FE-28 再接上第三項：籌碼卡的異常值徽章** ——
原本登記在下面「沒有接上」的第 5 項，該項已改寫，見那裡。）
1. ✅ **個股「估值（357 評價）」判決卡。**
   前一批卡在「357 位階要 `calc_dividend_yield_357(price, avg_div_twd=,
   div_years=)`，而全 repo 沒有任何 L3 介面回傳個股的配息歷史」。
   **拒絕拿 ETF 配息去頂替的那個判斷是對的，本批沒有推翻它** ——
   `etf_grp_compare_service.get_etf_dividends()` 是 ETF 用的 pass-through，
   拿它餵個股是替上游宣稱一件它沒說的事；`tests/test_p03_inspect_view.py`
   的 `test_valuation_never_eats_etf_dividends` 仍以 AST 釘住那條禁令。
   本批補的是**正確的來源**：新增 L3
   `services.valuation_service.get_stock_dividends()` → L1
   `app_stock_fetchers.fetch_dividend_data`（FinMind → yfinance → TWSE，
   **與既有 🔬 個股分頁那張 357 卡同一份數字**，兩張卡不會打架）。
   ⚠️ 前一批那句「**全 repo 沒有任何 L3 介面回傳個股配息歷史**」**不精確**：
   `yield_screener_service.get_annual_dividends()` 是存在的，只是它回一個
   yfinance 單源的逐年 Series，**沒有**「近 5 年平均」與「有配息年數」——
   拿它就得在本頁自己算那兩個數，那是第二把尺（§2.1）。**是「餵不了」，
   不是「不存在」**，據實更正。
2. ✅ **個股「籌碼」判決卡。**
   判讀那一半本來就有（L0 純函式 `shared.macro_compute.
   analyze_20d_chips_from_df`，吃 df、免 I/O）；本批補的是餵它的那份 df ——
   新增 L3 `services.stock_chips_service.get_chips_readout()` → L1
   `app_stock_fetchers.fetch_price_data`（`StockDataLoader.get_combined_data`
   的 public 包裝，**與既有 🔬 個股分頁同一條抓取線**）。
   ⚠️ 前一批那句「那份 df 同時要有 `主力合計` 與 `volume`」是**錯的**
   （實測 2026-09-07 讀 `macro_compute.py` 原始碼）：該函式檢查的是
   **`外資` / `投信` / `volume`**，`主力合計` 一次都沒用到 ——
   那是另一支（L2 `inst_sanity.flag_latest_inst_outlier_from_df` 的異常值
   徽章）吃的欄位，被混為一談了。**本批照實際欄位接線**，
   ~~而那個異常值徽章**本批沒有接**（見下面「沒有接上」的第 3 項）。~~
   ⚠️ **2026-09-07 FE-28 更正：徽章已接上，上面那句刪除線是事實更正、不是漏刪。**
   「兩支不同的函式、兩組不同的欄位」那半句**仍然成立**（也正是徽章要與集中度
   **分別判、分別報**的理由）；不成立的只有「沒有接」。現行做法見下面第 5 項。

═══ 本批**沒有接上**的~~三~~兩項（誠實揭露，不是漏寫）═══════════════════
（**2026-09-07 FE-28 事實更正**：第 5 項〔籌碼卡的異常值徽章〕**已接上**，
故本節由三項降為兩項。刪除線是有意識的更正，不是漏刪 —— 第 5 項原文保留在
下面並就地改寫，**不刪掉**，因為它記錄的「為什麼當時接不了」在當時是真的。）
3. ⛔ **葉1-A 明細的其餘七段**（K 線＋均線 / 357 河流圖 / 財報領先指標 /
   VCP・布林 / 月營收 / 什麼時候買賣 / 心理檢查）。**只有 💰 獲利能力診斷
   這一段接上了。** 其餘七段的現行實作是 `src/ui/tabs/stock_sections/section_*.py`，
   每一支都直接 import L1（`src.data.core` / `src.data.stock`）並自帶 widget key，
   在本頁再掛一次會撞 `DuplicateWidgetID`。→ **標 `unwired`**，見 `DETAIL_WHERE`。
4. ⛔ **葉1-B ETF 明細的七段**（淨值 vs 市價 / 折溢價帶 / 配息紀錄與以息養股 /
   成分股與集中度 / 同儕 7 維 / 標準差買賣帶 / 破發檢查）。同 3。
   ⚠️ 線框對這一葉的紅隊註記是「**與個股分支重疊近零**（13 個個股概念在 ETF 頁
   0 命中、6 個 ETF 概念在個股頁 0 命中）—— **合併的是入口與骨架，不是內容**」。
   本檔照這句寫：骨架（form / 判型 / 3 欄判決卡 / 單欄堆疊明細）兩支共用，
   **每一張卡的 label 與 facts 全部換掉**，沒有一個欄位是兩邊共用的。
5. ✅ **籌碼卡的「異常值徽章」—— 2026-09-07 FE-28 已接上**（線框對這一格
   寫的是「近 20 日主力買賣超與集中度，**含異常值徽章**」）。
   ⚠️ **本項原文（下面刪除線那段）一字未刪，只加註** —— 它記錄的是
   「當時為什麼接不了」，那在**當時是真的**（前一批的檔案邊界不含 L3 那一支）。
   把它整段刪掉，下一個人會看不出這一格是**接上的**、還是**一開始就沒人想過**。
   ~~徽章那一半走的是 L2 `inst_sanity.flag_latest_inst_outlier_from_df`，
   它吃的是 `主力合計` ＋ 30 日均量，與本批接上的近 20 日籌碼判讀（吃
   `外資` / `投信` / `volume`）**是兩支不同的函式、兩組不同的欄位**。
   接它需要把 df 交給 L5 或在 L3 再做一次判讀，兩者都超出本批的檔案邊界。
   → **本批只接判讀、不接徽章**，卡上的「接線後的樣子」已據實改寫，
   不再宣稱有徽章。~~

   **現行（FE-28）**：
   · **「兩支不同的函式、兩組不同的欄位」仍然成立**，而且正是現行做法的理由 ——
     徽章與集中度**分別判、分別報**，不互相背書。
   · **判在 L3**（`stock_chips_service._outlier_fields`）：徽章與判讀吃的是
     **同一份 df**，在那一層算等於零額外取數；`ChipsReadout` 新增
     `outlier_*` 五個欄位帶上來（**只增不改**既有欄位）。
     於是**本檔不必 import L2、也不必接手 `DataFrame`** —— 原文寫的那兩條路
     （把 df 交給 L5／在 L3 再做一次判讀）都不是現行做法。
   · **實測查證（2026-09-07）**：`fetch_price_data` → `get_combined_data` 回的
     df **確實同時持有 `主力合計` 與 `volume`**（前者由 L1
     `data_loader_inst_fetchers._normalize_inst_pivot` 產出並 merge 進來，
     後者來自日線）—— 亦即前一批說的「要多取一份 df」並不成立，
     **本來就在同一張表裡**。
   · **畫面**：徽章走 `facts` 的一列（`CHIPS_OUTLIER_LABEL`），
     **三態各出一句話**（有異常／判過了沒有異常／**判不出來**），
     **不佔訊號頻道、不改變卡的狀態**。理由三條寫在 `build_chips_card`
     的 docstring 裡，此處不重複。

⚠️ **本頁沒有任何一格會判 `UI_DEGRADED`**，這是刻意的：上游沒有回傳任何
「門檻已失準」的訊號（`discriminative=False` 的來源），硬湊一個等於捏造一種
使用者無從查證的狀態。線框葉1-A 的 `degradedCells`（「趨勢因子無 MA，不計入」）
描述的是**接線後**的樣子 —— 那一格（K 線＋均線）在本頁是 `unwired`，
**沒有 MA 可以「不計入」**。接上之後才會有真的 degraded 可判。
⚠️ 本批接上的兩格**也沒有**引入 degraded：籌碼判不出來（法人欄缺／全為 0）
與 357 算不出來（無股價／無配息紀錄）都是**缺值**，走 `empty`（灰）——
`degraded` 的語意是「**有值**、只是別照門檻讀」，缺值套上去是第三種說謊。
⚠️ **FE-28 的異常值徽章同樣沒有引入 degraded，理由同上**：它判不出來時是
**沒有值**（缺 `主力合計` 欄／均量窗內有天數沒有量／最新一日分不出 0 的意思），
不是「有值但門檻失準」。上游 L2 `inst_sanity` 也**沒有**回傳任何
`discriminative=False` 的訊號可以據以判 degraded ——
硬湊一個就是本節開頭那句「捏造一種使用者無從查證的狀態」。
✅ **附帶：徽章也不佔訊號頻道**（`signal_text` 留白）。依
`_ui_kit.render_card` 對 `signal_text` 的判準，它載的是**判決語**
（有異常／沒有異常），不是 band 觀測；而且這張卡的訊號頻道已經被 L0 的
籌碼訊號佔住，塞第二個進去就是同一張卡兩盞燈。完整三條理由寫在
`build_chips_card` 的 docstring。

═══ 這個檔擋得住什麼、擋不住什麼（誠實邊界）═══════════════════════════
`classify_kind()` / `load_stock_readout()` / `load_etf_readout()` /
`load_profitability()` / `load_batch_rows()` 的 `try/except` 擋得住的是
**呼叫期**例外（模組進得來、但呼叫時炸了）→ 轉成看得見的紅卡 ＋ `repr(e)`。

⛔ **擋不住 module-level 的 import 失敗。** 本檔 module level 有
`from src.ui.tabs.tab_today import ...`、`from src.ui.views._ui_kit import ...`、
`from src.config.config import MA_*` 與三個 `shared.*`。這幾條路徑上任何一個
模組在 import 階段壞掉，`import page_inspect` 自己會先 `ImportError`，
`render_page_inspect()` 根本不會被呼叫到 —— 畫面全空白，而下面所有
`try/except` 一個都跑不到。

✅ **所有 L2 / L3 取數都是函式體內的 late import 且各自包在 `try/except` 裡。**
⚠️ **判型的 L2 late import 是刻意的、不是懶惰**：`src.compute.etf.asset_lag`
所屬的套件 `__init__` 是 eager barrel —— 實測（量測日 2026-09-07）
`import src.compute.etf.asset_lag` 會連帶拉進 **pandas / requests / yfinance /
streamlit ＋ 33 個 `src.*` 模組**（含 `src.data.core.data_loader`）。
放在 module level 會讓「打開這一頁」的故障半徑等於整條資料層。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

import streamlit as st

from shared import ia_nav
# L0 SSOT：均線週期。**禁止在 UI 端寫死 20 / 60 / 120 / 240**（§3.3）。
from shared.station_specs import MISS_NOT_APPLICABLE, MISS_TEXT
from shared.ui_state import (
    UI_EMPTY,
    UI_FAILED,
    UI_IDLE,
    UI_LIVE,
    classify_ui_state,
)
from src.config.config import MA_ANNUAL, MA_LONG, MA_MID, MA_SHORT
from src.ui.tabs.tab_today import (
    NO_EXIT_MARKER,
    Card,
    Note,
    scrub_state_glyphs,
)
from src.ui.views._ui_kit import (
    MAX_COLS,
    banned_signal_glyphs,
    grid,
    render_card_isolated,
    section_header,
)

# ══════════════════════════════════════════════════════════════════
# session key（本頁自有前綴 `p03`，不與 `tab_stock` 的 `t2_*`、
# `tab_stock_grp` 的 `grp_*`、`etf_tab_*` 的 key 相撞）
# ══════════════════════════════════════════════════════════════════
# ⚠️ **2026-09-08 FE-36 語彙更正（本區塊各行原文一字未改）**：以下若干行寫
#    「與既有 🔬 個股分頁 / 舊分頁**同時掛上**時不撞 `DuplicateWidgetID`」。`b5bdb36` 把五頁
#    改成側欄 radio ＋ `st.stop()` 之後，**新頁與舊頁籤不再進到同一個 script
#    run**，「同時掛上 → 同輪撞 ID」這個機制對舊分頁**已不成立**。
#    ✅ **前綴照留，理由換成兩條仍然成立的**：(a) `st.session_state` 跨 rerun、
#    跨頁存活，切一下側欄 radio 就是同 session 的一次 rerun ⇒ 同名 key 照樣
#    互相污染；(b) `st.stop()` 之前跑完的**整個側欄** widget（導覽 radio 自己、
#    連線測試鈕、強制刷新鈕、Sheet ID 輸入框…）**與本頁同輪**，那才是現在真正
#    會撞 ID 的對手。掛載形態由 `tests/test_p0x_view_mount_claims.py` 釘住。
#: 葉1 單檔表單的 key。線框寫 `st.form(form_ticker)`；加 `_view` 後綴是為了
#: 與既有 🔬 個股分頁同時掛上時不撞 Streamlit 的 DuplicateWidgetID。
FORM_TICKER_KEY: str = "form_ticker_view"
#: 葉2 多檔表單的 key（線框 `st.form(form_batch)`）。
FORM_BATCH_KEY: str = "form_batch_view"

#: 代碼輸入框的 widget key —— **當下值**。下游禁止讀（鐵律 2）。
SS_TICKER_WIDGET: str = "p03v_ticker_widget"
#: 期間下拉的 widget key —— **當下值**。下游禁止讀。
SS_PERIOD_WIDGET: str = "p03v_period_widget"
#: 判型覆寫下拉的 widget key —— **當下值**。下游禁止讀。
SS_KIND_WIDGET: str = "p03v_kind_widget"
#: 6 個 MA checkbox 的 widget key 前綴 —— **當下值**。下游禁止讀。
SS_MA_WIDGET_PREFIX: str = "p03v_ma_"
#: 批次代碼輸入框的 widget key —— **當下值**。下游禁止讀。
SS_BATCH_WIDGET: str = "p03v_batch_widget"
#: 批次型別篩選的 widget key —— **當下值**。下游禁止讀。
SS_BATCH_FILTER_WIDGET: str = "p03v_batch_filter_widget"
#: 批次下鑽選單的 widget key。**它在 form 外**（不是表單的一部分，
#: 而是對「已經算完的那份結果」換一列看，零額外 L3 呼叫）。
SS_DRILL_WIDGET: str = "p03v_drill_widget"

#: **已套用值**（葉1）。只有 `_render_ticker_form()` 的 submit 分支會寫，
#: 寫入形狀為 `{"ticker": str, "period_days": int, "mas": [int, ...],
#: "kind_choice": str}`。
#:
#: ⚠️ **這個 key 的「存在性」就是葉1 全部區塊的 `requested=` gate。**
#: 不得改成從 `ticker` 或結果反推 —— `bool(ticker)` 分不出「還沒送出」與
#: 「送出了但代碼是空字串」，而後者是一個**有效的使用者行為**（要看到
#: 「請輸入代碼」那句話，不是看到冷啟動的 idle）。
SS_APPLIED_TICKER: str = "_p03_applied_ticker"

#: **已套用值**（葉2）。只有 `_render_batch_form()` 的 submit 分支會寫，
#: 寫入形狀為 `{"raw": str, "kind_filter": str}`。**存在性 = 葉2 的 gate。**
SS_APPLIED_BATCH: str = "_p03_applied_batch"

# ══════════════════════════════════════════════════════════════════
# 按鈕與葉的顯示名
# ══════════════════════════════════════════════════════════════════
#: ⚠️ **交接事項（與頁 2 同一項）**：`shared/ia_nav.py` 目前**沒有**第 3 頁的
#: `ACTION_*` 與 `LEAF_*` 登錄（實測 2026-09-07：`ACTION_LABELS` 只有
#: `update_today`）。ia_nav 存在的理由正是「按鈕改名時，指路句要跟著改」——
#: 本檔的折衷是**在本檔內只定義一次**，按鈕與指路句**都讀同一個常數**，
#: 讓改名的失效模式在本頁內不成立；但**跨頁**仍缺一份 SSOT。
#: → 應在 `shared/ia_nav.py` 補 `ACTION_LOAD_INSPECT` / `ACTION_RUN_BATCH`
#:   與 `LEAF_INSPECT_SINGLE` / `LEAF_INSPECT_BATCH`，本檔改為讀它。
ACTION_LOAD_INSPECT_LABEL: str = "🔍 載入完整分析"
ACTION_RUN_BATCH_LABEL: str = "🚀 批次分析"

#: 葉名（線框 `PAGES[2].leaves` 逐字）。
LEAF_SINGLE_TITLE: str = "單檔診斷（個股／ETF/unknown 三分支）"
LEAF_BATCH_TITLE: str = "多檔比較（可混貼）"

#: 指路句一律由這一支組出來，**不手抄按鈕名**（做法比照 `ia_nav.where_to_press`）。
_OPEN, _CLOSE = "「", "」"


def press(label: str) -> str:
    """`'按「🔍 載入完整分析」'` —— 指路句的唯一組法。"""
    return f"按{_OPEN}{label}{_CLOSE}"


# ══════════════════════════════════════════════════════════════════
# 表單選項（**版面參數，不是門檻** —— 故不進 `shared/*_thresholds.py`）
# ══════════════════════════════════════════════════════════════════
#: 期間（交易日）。預設 250 直接出自線框葉1 ① 的 `cells` 原文「250 日 · 還原 K」。
#: ⚠️ 這是**畫面參數**（一次看多長），不是任何判斷的門檻 —— 頁 2 的
#: `TOP_N_OPTIONS` 立的是同一個判例。
PERIOD_OPTIONS: tuple[int, ...] = (120, 250, 500)
DEFAULT_PERIOD_DAYS: int = 250

#: 6 個 MA 週期（線框 F11：原 `st.columns(6)` → 3 欄 × 2 排）。
#: **20 / 60 / 120 / 240 一律讀 L0 `src/config/config.py` 的 SSOT，不手抄。**
#:
#: ⚠️ **5 與 100 在 L0 沒有 SSOT**（實測 2026-09-07：`config.py` 只有
#: `MA_SHORT=20` / `MA_MID=60` / `MA_LONG=120` / `MA_ANNUAL=240`），
#: 而既有 🔬 個股分頁的 6 顆 checkbox 是 5 / 20 / 60 / 100 / 120 / 240
#: （`tab_stock.py` 的 `t2_ma5` … `t2_ma240`）。本頁**照既有畫面的那 6 個**，
#: 缺 SSOT 的那兩個就地寫成具名常數並在此標明 —— 不假裝它們有出處。
#: → **交接事項**：若這 6 個要成為全站規格，應在 L0 補一份
#:   `MA_PERIODS_ON_CHART` 之類的 SSOT，本檔與 `tab_stock.py` 都改讀它。
MA_FAST_NO_SSOT: int = 5
MA_MID_FAST_NO_SSOT: int = 100
MA_OPTIONS: tuple[int, ...] = (
    MA_FAST_NO_SSOT, MA_SHORT, MA_MID, MA_MID_FAST_NO_SSOT, MA_LONG, MA_ANNUAL,
)
#: 預設打勾的兩條（線框 ③ 的 `cells` 原文「MA20 · MA100 已勾」，
#: 與既有 `tab_stock.py` 的 `value=True` 兩顆逐字一致）。
DEFAULT_MAS: tuple[int, ...] = (MA_SHORT, MA_MID_FAST_NO_SSOT)

#: 判型覆寫的三個選項（線框 F4：「判型結果就地顯示且**可手動覆寫**」）。
#: **值是本頁的 UI 選項 key，不是 L2 的資產型別字串** —— 兩者的對映在
#: `classify_kind()` 裡做，因為型別字串的 SSOT 在 L2，而本檔 module level
#: 刻意不 import L2（見檔頭最後一段的故障半徑說明）。
KIND_CHOICE_AUTO: str = "auto"
KIND_CHOICE_STOCK: str = "stock"
KIND_CHOICE_ETF: str = "etf"
KIND_CHOICE_LABELS: dict[str, str] = {
    KIND_CHOICE_AUTO: "自動判型（系統判）",
    KIND_CHOICE_STOCK: "強制當個股",
    KIND_CHOICE_ETF: "強制當 ETF",
}

#: 批次型別篩選（線框葉2 live 原文「貼一串代碼（可混 個股／ETF）＋ **篩選**」）。
#: 客戶已核准**允許混貼**，故預設「全部」；篩選只影響**顯示**，
#: **不影響取數**（每一檔都照樣判型與取數，否則「有幾檔失敗」會被篩掉而看不見）。
BATCH_FILTER_ALL: str = "all"
BATCH_FILTER_LABELS: dict[str, str] = {
    BATCH_FILTER_ALL: "全部（混貼）",
    KIND_CHOICE_STOCK: "只看個股",
    KIND_CHOICE_ETF: "只看 ETF",
}

#: 判不出型別時的顯示名。**型別字串→中文名的對映表**都在函式體內就地組
#: （`classify_kind()` / `load_batch_rows()`），因為 key 必須是 L2 的 SSOT
#: 字串，而本檔 module level 刻意不 import L2。只有這個 fallback 沒有 key，
#: 所以它可以住在這裡。
KIND_LABEL_FALLBACK: str = "無法判定"

#: 一次批次最多幾檔。**這是節流上限，不是門檻** —— 每一檔都會發一輪
#: L3 取數（財報 + 日線），檔數直接等於等待時間。超過的部分**明講被截掉**，
#: 不靜默丟掉（§1）。
BATCH_MAX_TICKERS: int = 20

# ══════════════════════════════════════════════════════════════════
# 文案常數（一句話只准寫一次 —— 手抄多份，改的時候一定會漏改）
# ══════════════════════════════════════════════════════════════════
#: 例外的**出處**。做法沿用頁 1／頁 2：不共用 `tab_today.upstream_error_why()`，
#: 因為那支的文案寫死「讀 **L3 canonical 契約**時拋出例外」，
#: 拿它去包別的層等於**對使用者謊報出事的層**。
#: ⚠️ 洗掉狀態 glyph 那一步**仍然走對面的 SSOT** `scrub_state_glyphs()`，
#: 這裡換掉的只有出處那一句話（不是第二把尺）。
SRC_CLASSIFY: str = "L2 判型純函式（`compute.etf.asset_lag.classify_asset_kind`）"
SRC_METRICS: str = "L3 逐檔指標（`services.dividend_station_service.fetch_metrics`）"
SRC_STATEMENTS: str = (
    "L3 財報取數（`services.stock_grp_service.get_financial_statements`）")
SRC_HEALTH: str = (
    "L3 財報體檢（`services.financial_health_engine.analyze_financial_health`）")
SRC_DIVIDENDS: str = (
    "L3 個股配息（`services.valuation_service.get_stock_dividends`）")
SRC_357: str = (
    "L2 357 位階（`compute.strategy.v5_modules.calc_dividend_yield_357`）")
SRC_CHIPS: str = (
    "L3 近 20 日籌碼（`services.stock_chips_service.get_chips_readout`）")
SRC_RENDER: str = "本頁的渲染層（`views/_ui_kit.render_card`）"

UNKNOWN_ERROR_TEXT: str = "（上游沒有給訊息）"

#: 葉1 idle 三要素（線框葉1 ① 的 greyCells 原文「（輸入代碼，例：2330 或 00878）」）。
SINGLE_IDLE_NOW: str = "**尚未載入任何分析**"
SINGLE_IDLE_WHY: str = (
    "明細需要 K 線、三大法人、月／季營收等六類資料；"
    "在你送出之前，本頁**一次 L3 取數都不會發**（沒有人叫過它）")
SINGLE_IDLE_WHERE: str = (
    f"在上方表單輸入代碼（例：2330 或 00878）後，{press(ACTION_LOAD_INSPECT_LABEL)}")

#: 送出了、但代碼欄是空的。**這是一個有效的使用者行為**，不是冷啟動。
BLANK_TICKER_NOW: str = "**你按了載入，但代碼欄是空的**"
BLANK_TICKER_WHY: str = (
    "本頁不會替你猜一個代碼，也不會拿上一次查過的那一檔頂替 —— "
    "那會讓你看著別檔的數字做這一檔的決定")
BLANK_TICKER_WHERE: str = (
    f"在代碼欄填一個台股代號（個股 4 碼如 2330；ETF `00` 開頭如 00878），"
    f"再{press(ACTION_LOAD_INSPECT_LABEL)}")

#: 葉1-C unknown 分支（線框 grey 三要素逐字，glyph 已移除 —— 狀態頻道會由
#: `state_meta()` 出一次，文案不得自己再帶一個）。
UNKNOWN_NOW: str = "**無法判定這是個股還是 ETF** —— 已停在這裡，沒有替你猜"
UNKNOWN_WHY: str = (
    "`classify_asset_kind` 對非台股代號回 `unknown`"
    "（美股／指數／興櫃／輸入錯誤都會落在這）。"
    f"{MISS_TEXT[MISS_NOT_APPLICABLE]}"
    "依 §4.6「不猜」，本站不替你選一邊；"
    "**這不是故障，重按一百次也是同一個答案**")
UNKNOWN_WHERE: str = (
    "確認代碼；若確定它是台股，在上方表單把「判型」從自動改成"
    f"「{KIND_CHOICE_LABELS[KIND_CHOICE_STOCK]}」或"
    f"「{KIND_CHOICE_LABELS[KIND_CHOICE_ETF]}」後重新載入")

#: 未接線那一項（明細）的「去哪補」。**沒有使用者可執行的出口** ——
#: 線框對這類的原文就是「這是待接線項，不是你操作的問題」。
#:
#: ⚠️ **估值（357）與籌碼的 `*_WHERE` 已改寫，這是有意識的改寫不是漏刪**
#: （2026-09-07 FE-18）：那兩格**已經接線**，再用 `NO_EXIT_MARKER`
#: （「沒有使用者出口」）就是說謊 —— 接上之後「算不出來」是**這一輪**的事，
#: 重按有機會好。舊句被權衡掉的只有「沒有出口」這半句，
#: 「不拿缺值湊結論」那半句原封不動搬進了下面的新文案。

#: 357 **算不出來**時的「去哪補」（**有出口**：重按 / 換代碼 / 等資料補齊）。
VALUATION_WHERE: str = (
    f"若是暫時抓不到，{press(ACTION_LOAD_INSPECT_LABEL)}重跑一次；"
    "若這一檔近 5 年真的沒有配息，357 這套殖利率法則**本來就不適用它**，"
    "重按幾次都一樣 —— 那不是故障，改看健康度與獲利能力那幾格。"
    "配息資料持續抓不到時，到"
    f"{ia_nav.where_to_find(ia_nav.SECTION_WHY_DATA_HEALTH)}"
    "看 FinMind／yfinance／TWSE 三段備援鏈是否可用")
#: 357 算不出來的「為什麼」**由 L2 自己說**（它回的 `msg` 已經寫明是無股價
#: 還是無配息紀錄），本檔只補「本站的處置」。**不自己判是哪一種**（§2.1）。
VALUATION_WHY_TAIL: str = (
    "　本站**不以 0% 殖利率頂替** —— 0% 會被同一套門檻判成「超貴」，"
    "那是拿缺資料當看空結論（`CLAUDE.md §1`）")
#: 三段備援鏈跑完、一段都沒有給配息紀錄時，**兩種可能都要講**（§1 不猜）。
VALUATION_NO_SOURCE_WHY: str = (
    "配息備援鏈（FinMind → yfinance → TWSE）跑完了，**沒有一段給出紀錄**。"
    "那可能是這一檔近 5 年真的沒有配息，也可能是三段這一輪都沒拿到 —— "
    "**上游的回傳值分不出這兩者，本站也不猜**")

#: 籌碼**判不出來**時的「去哪補」（**有出口**：重按 / 等三大法人資料補齊）。
CHIPS_WHERE: str = (
    f"{press(ACTION_LOAD_INSPECT_LABEL)}重跑一次；"
    "三大法人那一腿常態性地比日線晚到（TWSE 盤後 ~14:30、完整要等 17:00 後），"
    "新上市或長期停牌的標的也可能整段沒有法人資料。"
    "持續如此請到"
    f"{ia_nav.where_to_find(ia_nav.SECTION_WHY_DATA_HEALTH)}"
    "看 TWSE／TPEX／FinMind 的法人備援鏈是否可用")
#: 籌碼判不出來的「為什麼」前綴 —— 後面接 L0 自己給的原因原文。
CHIPS_MISS_WHY_HEAD: str = (
    "日線抓回來了，但**判不出籌碼**（上游給的原因："
)
CHIPS_MISS_WHY_TAIL: str = (
    "）。近 20 日集中度要「外資 ＋ 投信淨買賣超」與「成交量」兩組數字，"
    "缺一組就算不出來 —— **這是資料缺漏，不是這一檔籌碼不好**；"
    "本站不拿 0% 集中度頂替（0% 是「買賣超剛好抵銷」這個結論，不是缺值）"
)

# ── 異常值徽章（線框對這一格寫的「含異常值徽章」，2026-09-07 FE-28 接線）──
#: 徽章那一列在 `facts` 裡的欄位名。**它是與集中度並列的第二個檢查**，
#: 不是集中度的附註 —— 兩支吃的欄位不同，會出現「一支判得出、一支判不出」。
CHIPS_OUTLIER_LABEL: str = "單日爆量檢查"
#: 「判不出來」的開頭。**這一句是本格存在的理由**：
#: 既有 🔬 個股分頁的寫法是 `if _inst_flag.is_outlier:` 才畫徽章 ——
#: 於是「判不出來」與「判過了沒有異常」在畫面上長得**一模一樣**（都是沒有徽章），
#: 而使用者只會讀到後者。§1：把「沒量到」講成「量到了沒事」就是捏造一個觀測。
CHIPS_OUTLIER_UNKNOWN_HEAD: str = (
    "**判不出來** —— 這**不等於**「沒有異常」。（上游原因：`{reason}`）　")
#: `vol_unavailable`：L2 把三種情形收斂成同一個 token，**分不出是哪一種**。
CHIPS_OUTLIER_UNKNOWN_VOL: str = (
    "這一項要「最新一日的主力買賣超」與「均量窗**每一天都有量**」兩件事。"
    "缺欄位、剛上市／長期停牌而歷史短於窗長度、或本輪載入的天數不夠，"
    "都會落在這同一個原因裡 —— **上游的回傳值分不出是哪一種，本站也不猜**")
#: `inst_net_zero`：上游對這一欄補過 0，於是「0」有兩種意思。
CHIPS_OUTLIER_UNKNOWN_ZERO: str = (
    "最新一日的主力買賣超是 0，而上游對這一欄做過**缺值補 0**，"
    "所以這個 0 分不出「今天法人真的沒有買賣超」與「今天的法人資料還沒到」"
    "（三大法人常態性地比日線晚到）—— 分不出來就不判，"
    "**不拿 0 倍當「沒有異常」**")
#: 上游改了 `reason` 的字彙時走這一條。**不假裝看得懂**（§1）。
CHIPS_OUTLIER_UNKNOWN_OTHER: str = (
    "本站沒有對應這個原因的說法 —— 上游的回傳字彙可能改了。"
    "**不替它猜一個意思**；請照上面那個原文去對上游的程式碼")
#: 判出來了的兩句。`{}` 全部由 L3 帶上來，**本檔不寫門檻、也不寫窗長度**（§3.3）。
CHIPS_OUTLIER_ANOMALY_TEXT: str = (
    "**有異常**：最新一日主力買賣超達均量的 {ratio} 倍，"
    "超過門檻 {threshold} 倍{window}。單日淨買賣超遠離常量，"
    "上面那個近 20 日的集中度會被這一天拉動")
CHIPS_OUTLIER_NORMAL_TEXT: str = (
    "**判過了，沒有異常**：最新一日主力買賣超是均量的 {ratio} 倍，"
    "未達門檻 {threshold} 倍{window}")
#: 均量窗那個括號。**數字由 L3 帶上來**（L2 的簽章預設值），本檔不寫。
CHIPS_OUTLIER_WINDOW_TEXT: str = "（均量窗 {window} 個交易日）"
#: 窗長度讀不到時（L3 的 `outlier_window is None`）的替代講法 —— **不填數字**。
CHIPS_OUTLIER_WINDOW_UNKNOWN: str = "（均量窗長度由上游決定，本站這一輪讀不到）"


def _outlier_fact(chips: "ChipsView") -> tuple[str, str] | None:
    """徽章那一列 `(欄位名, 值)`；**這一輪沒跑到 → `None`（不出這一列）**。

    ⚠️ **三態一律出一列**（有異常 / 沒有異常 / 判不出來）。
    「不出這一列」只保留給 `outlier_verdict == ""`，而那只發生在**連 df 都
    沒拿到**（取數失敗、或冷啟動根本沒呼叫）—— 那時整張卡已經是紅／灰態，
    卡自己會講。**其餘任何情形都必須出這一列**，理由見
    `CHIPS_OUTLIER_UNKNOWN_HEAD` 的註解。

    ⚠️ **門檻與均量窗一個數字都不在本檔** —— 兩者都由 L3 從上游讀來
    （門檻 → L0 `shared.signal_thresholds.INST_NET_OUTLIER_VOLUME_RATIO`；
    窗長度 → L2 那支的簽章預設值）。在畫面上抄一個 `5` 或 `30`，
    上游改的時候這裡不會跟著動，而且沒有任何測試會紅（§3.3）。
    窗長度讀不到 → 講「上游設定的窗長度」，**不填一個猜的數字**（§1）。
    """
    _v = chips.outlier_verdict
    if not _v:
        return None
    # ⚠️ **late import 且刻意排在早退之後**：三個字面的 SSOT 在 L3
    # （抄一份到本檔就是第二把尺），但 module level import 會把
    # `src.services` 的 eager barrel 拉進「打開這一頁」的故障半徑，
    # 也會讓「還沒有人叫過就不准碰 L3」那道守衛失效（`ChipsView` 未接線 /
    # 冷啟動時 `outlier_verdict` 是空的 → 上面那行就回去了，一行都不 import）。
    from src.services.stock_chips_service import (
        OUTLIER_ANOMALY,
        OUTLIER_NORMAL,
    )

    _win = (CHIPS_OUTLIER_WINDOW_TEXT.format(window=chips.outlier_window)
            if chips.outlier_window is not None
            else CHIPS_OUTLIER_WINDOW_UNKNOWN)

    if _v in (OUTLIER_ANOMALY, OUTLIER_NORMAL):
        _tpl = (CHIPS_OUTLIER_ANOMALY_TEXT if _v == OUTLIER_ANOMALY
                else CHIPS_OUTLIER_NORMAL_TEXT)
        return (CHIPS_OUTLIER_LABEL,
                _tpl.format(ratio=_fmt_num(chips.outlier_ratio, digits=1),
                            window=_win,
                            threshold=_fmt_num(chips.outlier_threshold,
                                               digits=1)))

    _tail = {"vol_unavailable": CHIPS_OUTLIER_UNKNOWN_VOL,
             "inst_net_zero": CHIPS_OUTLIER_UNKNOWN_ZERO}.get(
                 chips.outlier_reason, CHIPS_OUTLIER_UNKNOWN_OTHER)
    return (CHIPS_OUTLIER_LABEL,
            CHIPS_OUTLIER_UNKNOWN_HEAD.format(
                reason=chips.outlier_reason or "上游沒有說") + _tail)

DETAIL_WHERE: str = (
    f"{NO_EXIT_MARKER} —— 這是待接線項，不是你操作的問題；"
    "現行入口仍在既有的 🔬 個股 / 🏦 ETF 分頁。"
    "要接上需先讓 `src/ui/tabs/stock_sections/section_*.py` 與 "
    "`src/ui/etf/etf_tab_*.py` 的每一段能被外部重複掛載"
    "（widget key 加前綴參數、取數改走 L3、gate 由 caller 提供）")
DETAIL_WHY: str = (
    "那幾段的現行實作各自直接 import L1（`src.data.core` / `src.data.stock` / "
    "`src.data.etf`）並自帶寫死的 widget key；在本頁再掛一次會撞 "
    "`DuplicateWidgetID`，而把取數抄一份到本頁則會變成第二個真相源")

#: 表單下方常駐的接線揭露（**不隨狀態消失**）。
WIRING_DISCLOSURE_SINGLE: str = (
    "**取數接線揭露**：判型、個股健康度、**估值（357）**、**籌碼**、"
    "💰 獲利能力三格、ETF 折溢價／配息／同儕 —— 這幾項走 L3，已接線；"
    "**K 線與其餘明細在本頁仍未接線** —— "
    "它們的卡會標「未接線」並寫明要補在哪，不會拿空白冒充結果。"
    "期間的選擇**只決定籌碼那一格載入多長的日線**；"
    "近 20 日的判讀窗由上游決定，**改期間不會改變籌碼結論**。"
    "均線的選擇目前**沒有東西會用到**（K 線那一段未接線）—— "
    "這兩句寫在這裡，是為了不讓你以為調了有效。")
WIRING_DISCLOSURE_BATCH: str = (
    "**取數接線揭露**：批次表的每一列走的是與葉1 **同一支** L3 "
    "（`fetch_metrics`），所以欄位也一樣 —— 個股給財報體檢分數，"
    "ETF 給折溢價／配息／同儕。**葉1 新接上的估值（357）與籌碼，"
    "批次表裡仍然不會出現** —— 它們各自要再發一輪取數（配息鏈 / 日線 ＋"
    "三大法人），一次 20 檔會把等待時間變成好幾倍。這是**刻意不做**，"
    "不是漏做；要看那兩格請到葉1 用同一個代碼載入。")

#: 葉2 idle / 空 三要素（線框葉2 grey 原文）。
BATCH_IDLE_NOW: str = "**尚未批次分析**"
BATCH_IDLE_WHY: str = (
    "批次會對每檔各發一輪 L3 取數（財報 + 日線），時間 ≈ 檔數 × 單檔時間；"
    "在你送出之前，本頁**一次 L3 取數都不會發**")
BATCH_IDLE_WHERE: str = f"在表單貼上代碼後，{press(ACTION_RUN_BATCH_LABEL)}"
BATCH_EMPTY_NOW: str = "**你按了批次分析，但沒有解析出任何代碼**"


def _signal_label(raw: Any) -> str:
    """上游的訊號字面（`'🔥 大戶吸籌'` / `'🟡 合理（5~7%）'`）→ **純中文標籤**。

    鐵律 3：訊號頻道只准出中文，帶了狀態 glyph／燈號 emoji 會被
    `_ui_kit.assert_signal_text_clean()` 當場 raise（`🔴` 與 `🟡` 都在禁用集）。

    ⚠️ **本函式不重寫判讀**，只把上游自己帶的圖示拿掉 —— 吸籌／倒貨／發散、
    便宜／合理／昂貴這些字面仍然是 L0／L2 的（§2.1：本檔不維護第二份對照表）。
    切法是「取第一個空白之後」，因為兩支上游的格式一律是 `<圖示> <中文>`。

    ⚠️ **上游若改了格式** 導致仍有禁用符號殘留 → **回空字串，不出訊號頻道**。
    少一個頻道好過畫出兩個互相矛盾的燈，也好過在 `render_card()` 裡才炸
    （那會變成半截死頁；理由見 `assert_signal_text_clean` 的 docstring）。
    ⚠️ 這**不是**第二把尺：「哪些符號被禁」讀的是 `_ui_kit` 的同一份 SSOT
    （`banned_signal_glyphs()`），本檔沒有自己列一份符號表。
    """
    _txt = str(raw or "").strip()
    if not _txt:
        return ""
    _parts = _txt.split(maxsplit=1)
    _label = _parts[1].strip() if len(_parts) > 1 else _txt
    return "" if banned_signal_glyphs(_label) else _label


def _error_why(source: str, error: Any, *, verb: str = "拋出例外") -> str:
    """把上游的失敗轉成一句可以放進 `Note.why` 的話，**出處與動詞都講對**。

    洗 glyph 一律走 `tab_today.scrub_state_glyphs()`（SSOT，唯一入口）——
    `Note.__post_init__` 拒收狀態 glyph，不洗就會把一張**該畫出來的紅卡**
    變成**整頁未捕捉例外**（§1：紅態要看得見，不是換一種炸法）。

    Args:
        verb: **上游是怎麼失敗的。** 預設「拋出例外」；有些上游是
            **回傳一個錯誤字串**而不是拋例外（L1 `fetch_price_data` 就刻意
            這麼做，讓暫時性失敗不進 `st.cache_data`）—— 對那一種寫
            「拋出例外」是**替上游宣稱一件它沒做的事**，下一個人會照著去
            traceback 裡找一個根本不存在的例外。傳 `verb="回報失敗"`。
    """
    _clean, _n = scrub_state_glyphs(error)
    _why = f"{source}{verb}：{_clean or UNKNOWN_ERROR_TEXT}"
    if _n:
        _why += ("（上游訊息裡的狀態符號已移除，"
                 "以免和這張卡自己的狀態燈混成兩個互相矛盾的說法）")
    return _why


# ══════════════════════════════════════════════════════════════════
# 純資料層（零 streamlit；render 端把 session 讀出來再傳進來）
# ══════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class InspectRequest:
    """使用者**已送出**的那一組單檔條件。`submitted` 是本頁第 1 個 gate 旗標。

    Attributes:
        submitted: `SS_APPLIED_TICKER` 這個 key 存不存在。
            **只有 submit handler 會寫它** —— 這是「有沒有人叫過」的事實，
            不是從 `ticker` 或結果反推的（L0 `shared/ui_state.py` 的鐵律）。
        ticker: 已套用的代碼（已 strip + upper）。**可能是空字串** ——
            那代表「按了送出但沒填」，是一個**有效的使用者行為**，
            與 `submitted=False`（冷啟動）是兩件事。
        period_days: 已套用的期間（交易日）。
        mas: 已套用的均線週期。
        kind_choice: 已套用的判型選項（`KIND_CHOICE_*`）。
    """

    submitted: bool
    ticker: str = ""
    period_days: int = DEFAULT_PERIOD_DAYS
    mas: tuple[int, ...] = DEFAULT_MAS
    kind_choice: str = KIND_CHOICE_AUTO

    @property
    def has_ticker(self) -> bool:
        """送出的那一輪有沒有真的填代碼。**只在 `submitted=True` 時有意義。**"""
        return bool(self.ticker)


def _clean_code(raw: Any) -> str:
    """使用者輸入 → 代碼。只做 strip ＋ upper，**不做任何補零 / 補後綴**。

    ⚠️ 刻意不在這裡補 `.TW` / `.TWO`：那是取數端（L3 `fetch_metrics`）
    自己的正規化規則，抄一份到 UI 就是第二個 SSOT，而且它會在對面改規則時
    無聲漂移。判型（`classify_asset_kind`）本來就吃得下帶不帶後綴的寫法。
    """
    return str(raw or "").strip().upper()


def applied_inspect_request(session: Mapping[str, Any]) -> InspectRequest:
    """讀**已套用值**（鐵律 2）。widget 當下值一律不讀。

    邊界：key 不存在 → `submitted=False`（冷啟動）。
    key 存在但形狀怪（被別人覆寫、或舊版殘留）→ 仍算「送出過」，
    其餘欄位退回預設 —— **不猜使用者的意思**。
    """
    if SS_APPLIED_TICKER not in session:
        return InspectRequest(submitted=False)
    _applied = session.get(SS_APPLIED_TICKER)
    if not isinstance(_applied, Mapping):
        return InspectRequest(submitted=True)
    try:
        _period = int(_applied.get("period_days", DEFAULT_PERIOD_DAYS))
    except (TypeError, ValueError):
        _period = DEFAULT_PERIOD_DAYS
    _mas = tuple(int(_m) for _m in (_applied.get("mas") or ())
                 if isinstance(_m, int))
    _choice = str(_applied.get("kind_choice") or KIND_CHOICE_AUTO)
    return InspectRequest(
        submitted=True,
        ticker=_clean_code(_applied.get("ticker")),
        period_days=_period if _period > 0 else DEFAULT_PERIOD_DAYS,
        mas=_mas,
        kind_choice=(_choice if _choice in KIND_CHOICE_LABELS
                     else KIND_CHOICE_AUTO))


@dataclass(frozen=True)
class BatchRequest:
    """使用者**已送出**的那一組批次條件。`submitted` 是本頁第 2 個 gate 旗標。"""

    submitted: bool
    tickers: tuple[str, ...] = ()
    kind_filter: str = BATCH_FILTER_ALL
    truncated: int = 0          #: 超過 `BATCH_MAX_TICKERS` 被截掉幾檔（0 = 沒截）

    @property
    def has_tickers(self) -> bool:
        """送出的那一輪有沒有解析出代碼。**只在 `submitted=True` 時有意義。**"""
        return bool(self.tickers)


def parse_tickers(raw: Any) -> tuple[tuple[str, ...], int]:
    """一串貼上來的代碼 → `(去重後的代碼, 被截掉幾檔)`。

    分隔符一律「非英數即分隔」（逗號 / 空白 / 換行 / 頓號 / 分號都吃），
    **順序保留**（使用者貼的順序就是他心裡的順序），重複只留第一次出現的。
    超過 `BATCH_MAX_TICKERS` 的部分截掉，**並把截掉幾檔回傳**——
    §1：靜默丟掉使用者貼的東西，等於讓他以為那幾檔查過了。
    """
    _buf: list[str] = []
    _cur: list[str] = []
    for _ch in str(raw or ""):
        if _ch.isalnum() or _ch == ".":
            _cur.append(_ch)
            continue
        if _cur:
            _buf.append("".join(_cur))
            _cur = []
    if _cur:
        _buf.append("".join(_cur))

    _seen: list[str] = []
    for _t in _buf:
        _code = _clean_code(_t)
        if _code and _code not in _seen:
            _seen.append(_code)
    if len(_seen) <= BATCH_MAX_TICKERS:
        return tuple(_seen), 0
    return tuple(_seen[:BATCH_MAX_TICKERS]), len(_seen) - BATCH_MAX_TICKERS


def applied_batch_request(session: Mapping[str, Any]) -> BatchRequest:
    """讀**已套用值**（鐵律 2）。widget 當下值一律不讀。"""
    if SS_APPLIED_BATCH not in session:
        return BatchRequest(submitted=False)
    _applied = session.get(SS_APPLIED_BATCH)
    if not isinstance(_applied, Mapping):
        return BatchRequest(submitted=True)
    _tickers, _cut = parse_tickers(_applied.get("raw"))
    _filter = str(_applied.get("kind_filter") or BATCH_FILTER_ALL)
    return BatchRequest(
        submitted=True, tickers=_tickers, truncated=_cut,
        kind_filter=(_filter if _filter in BATCH_FILTER_LABELS
                     else BATCH_FILTER_ALL))


# ══════════════════════════════════════════════════════════════════
# 判型（線框葉1 ① 的 F4；三分支的分岔點就在這裡）
# ══════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class KindVerdict:
    """一次判型的結果。**三個布林旗標由 `classify_kind()` 一次算好。**

    ⚠️ **為什麼不是在畫面上比 `kind == "stock"`**：資產型別字串的 SSOT
    住在 L2（`asset_lag` 的 `ASSET_STOCK` / `ASSET_ETF` / `ASSET_UNKNOWN`），
    而本檔 module level 刻意不 import L2（檔頭最後一段：那個 import 會拉進
    pandas / requests / yfinance / streamlit ＋ 33 個 `src.*`）。
    在畫面上寫 `kind == "stock"` 會變成**第二份型別字面**，對面改字串時
    本頁會安靜地全部落到 unknown 分支 —— 那正是線框 F4 引用的
    `station_cards.py` 事故（大小寫打錯一個字母 → 可信度虛高到 100%）。

    Attributes:
        requested: 由 `InspectRequest.submitted` 帶下來（**不是**從代碼反推）。
        code: 這一輪判的代碼。
        auto_kind: **系統**判出來的型別字串（覆寫與否都照算、照顯示）。
        kind: 這一輪**實際採用**的型別字串（覆寫時 ≠ `auto_kind`）。
        overridden: 使用者有沒有手動覆寫。
        benchmark: `pick_benchmark(kind)` 的結果；unknown → None。
        error: 判型本身拋出的例外 `repr(e)`；空字串 = 沒有錯誤。
    """

    requested: bool
    code: str = ""
    auto_kind: str = ""
    kind: str = ""
    kind_label: str = ""
    auto_kind_label: str = ""
    overridden: bool = False
    benchmark: str | None = None
    is_stock: bool = False
    is_etf: bool = False
    is_unknown: bool = False
    error: str = ""

    @property
    def is_resolved(self) -> bool:
        """判出了一支**走得下去**的分支沒有。

        ⚠️ **不是 `bool(self.kind)`**：unknown 也是一個非空字串
        （L2 的 `ASSET_UNKNOWN`），拿它當「有值」會讓判不出型別的那一輪
        被畫成綠燈 —— 那正是線框葉1-C 要防的「把 unknown 塞進另外兩態」。
        """
        return self.is_stock or self.is_etf


def classify_kind(req: InspectRequest) -> KindVerdict:
    """代碼 → 型別判決。**`req.submitted` 為 False 時一行 L2 都不呼叫。**

    路徑：L2 純函式 `compute.etf.asset_lag.classify_asset_kind` / `pick_benchmark`。

    ⚠️ **late import 是刻意的**（見檔頭）：`src.compute.etf` 是 eager barrel，
    module-level import 會把整條資料層拉進「打開這一頁」的故障半徑。

    ⚠️ **覆寫不會跳過自動判型**（線框 F4）：`auto_kind` 一律照算，
    畫面上兩列並陳。使用者要看得到「系統判成什麼」才知道自己在覆寫什麼。

    邊界（三個都真的走得到）：
      (a) **冷啟動 / 還沒送出** → `KindVerdict(requested=False)`，全 idle。
      (b) **送出了但代碼是空的** → 仍 `requested=True`，但不呼叫 L2
          （空字串沒有東西好判），回 `is_unknown=False` 且 `kind=""` →
          畫面走「代碼欄是空的」那張 empty 卡，**不是** unknown 分支。
      (c) **L2 在呼叫期拋例外**（含 late import 失敗）→ `repr(e)` 帶回 → 紅態。
          此時**連手動覆寫也救不回來**：型別字串的 SSOT 在那個模組裡，
          拿不到它就沒有合法的型別可用（本檔不自己編一個字面頂替）。
    """
    if not req.submitted:
        return KindVerdict(requested=False)
    _code = req.ticker
    if not _code:
        return KindVerdict(requested=True)
    try:
        from src.compute.etf.asset_lag import (
            ASSET_ETF,
            ASSET_STOCK,
            ASSET_UNKNOWN,
            classify_asset_kind,
            pick_benchmark,
        )
    except Exception as _e:  # noqa: BLE001 — 轉成紅卡，不吞
        print(f"[views/page_inspect] 判型模組載不進來 → 整葉轉紅態：{_e!r}")
        return KindVerdict(requested=True, code=_code, error=repr(_e))

    try:
        _auto = str(classify_asset_kind(_code))
        # UI 選項 key → L2 的型別字串。**對映只在這裡做一次**（SSOT 在 L2）。
        _choice_map = {KIND_CHOICE_STOCK: ASSET_STOCK,
                       KIND_CHOICE_ETF: ASSET_ETF}
        _kind = _choice_map.get(req.kind_choice, _auto)
        _bench = pick_benchmark(_kind)
    except Exception as _e:  # noqa: BLE001 — 轉成紅卡，不吞
        print(f"[views/page_inspect] 判型失敗 → 整葉轉紅態：{_e!r}")
        return KindVerdict(requested=True, code=_code, error=repr(_e))

    # 型別字串 → 中文名。**key 一律是 L2 的 SSOT 字串**（本檔不寫死字面）。
    _labels = {ASSET_STOCK: "個股", ASSET_ETF: "ETF",
               ASSET_UNKNOWN: KIND_LABEL_FALLBACK}
    return KindVerdict(
        requested=True, code=_code, auto_kind=_auto, kind=_kind,
        kind_label=_labels.get(_kind, KIND_LABEL_FALLBACK),
        auto_kind_label=_labels.get(_auto, KIND_LABEL_FALLBACK),
        overridden=(_kind != _auto), benchmark=_bench,
        is_stock=(_kind == ASSET_STOCK), is_etf=(_kind == ASSET_ETF),
        is_unknown=(_kind == ASSET_UNKNOWN))


# ══════════════════════════════════════════════════════════════════
# 葉1-A：個股分支的取數（L3 `fetch_metrics(..., 'stock')`）
# ══════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class StockReadout:
    """個股那一輪的 L3 產出。**不含任何本檔自算的判斷。**

    Attributes:
        requested: **「有人叫過」＋「判型判成個股」兩件事的合取。**
            使用者輸入 `00878` 時沒有任何人要求過個股財報 —— 那三格的正確
            狀態是 `idle`，不是 `empty`（「查了但沒有」是另一回事）。
        score_pct: 財報體檢綜合分（0-100）。`None` = 算不出來（**不寫 0**）。
        grade: 財報體檢等第（A / B / C…）。
        headline: L3 自己寫的一句總結。**原樣透傳，本檔不改寫**（§2.1）。
        fail_items: L3 判為不及格的項目名。
        trend_verdict: 跨季財報趨勢（`is_breakdown` / `is_turnaround` / `verdict`）。
        name: 中文名（查無 → 空字串，**不拿代號頂替**）。
        price: 現價。`None` = 日線那一腿沒抓到。
        error: 取數本身拋出的例外 `repr(e)`；空字串 = 沒有錯誤。
    """

    requested: bool
    score_pct: float | None = None
    grade: str = ""
    headline: str = ""
    fail_items: tuple[str, ...] = ()
    trend_verdict: Mapping[str, Any] | None = None
    name: str = ""
    price: float | None = None
    error: str = ""


def _num(value: Any) -> float | None:
    """任何東西 → float，或 `None`。**不猜 0**（§1：0 是一個結論，不是缺值）。"""
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _fetch_metrics(code: str, kind: str) -> tuple[Mapping[str, Any], str]:
    """L3 逐檔指標 → `(metrics, 錯誤字串)`。失敗 → `({}, repr(e))`。

    **本頁全部的 L3 取數都經過這一支**（葉1 個股 / 葉1 ETF / 葉2 批次三處），
    所以「出事時說哪一句話」只有一份。⚠️ `fetch_metrics` 對 **ETF** 是
    fail-loud 的（拿不到日線就 `raise`），對**個股**是 best-effort
    （各腿獨立 try，缺的填 `None`）—— 這個差異是 L3 自己的契約，
    本檔**不去抹平它**：抹平就等於替其中一邊宣稱一件它沒說的事。
    """
    try:
        from src.services.dividend_station_service import fetch_metrics
        _m = fetch_metrics(code, kind)
        return (_m if isinstance(_m, Mapping) else {}), ""
    except Exception as _e:  # noqa: BLE001 — 轉成紅態顯示，不吞
        print(f"[views/page_inspect] {code}（{kind}）指標取數失敗：{_e!r}")
        return {}, repr(_e)


def load_stock_readout(verdict: KindVerdict) -> StockReadout:
    """個股指標。**判型不是個股、或還沒有人叫過 → 一行 L3 都不呼叫。**

    邊界：
      (a) **冷啟動 / 判型是 ETF 或 unknown** → `requested=False` → idle。
      (b) **L3 拋例外**（含 late import 失敗）→ `repr(e)` → 紅態。
      (c) **回來了但 `mj_score_pct` 是 `None`** → `empty`（灰）——
          那是 L3 的 best-effort 契約：財報那一腿沒抓到。**不是紅、也不是 0 分。**
    """
    _requested = bool(verdict.requested and verdict.is_stock)
    if not _requested:
        return StockReadout(requested=False)
    _m, _err = _fetch_metrics(verdict.code, verdict.kind)
    if _err:
        return StockReadout(requested=True, error=_err)
    _trend = _m.get("trend_verdict")
    return StockReadout(
        requested=True,
        score_pct=_num(_m.get("mj_score_pct")),
        grade=str(_m.get("mj_grade") or ""),
        headline=str(_m.get("mj_headline") or ""),
        fail_items=tuple(str(_f) for _f in (_m.get("mj_fail_items") or ())),
        trend_verdict=_trend if isinstance(_trend, Mapping) else None,
        name=str(_m.get("name") or ""),
        price=_num(_m.get("current_price")))


# ══════════════════════════════════════════════════════════════════
# 葉1-A 💰 獲利能力診斷（**缺值三律樣板** —— 線框點名的那一格）
# ══════════════════════════════════════════════════════════════════
#: 一格獲利能力卡的三態判讀來源。`status` 是 L3 給的字串，本檔只做**顯示對映**，
#: **不重新判一次好壞**（門檻住在 L0 `shared/financial_health_thresholds.py`，
#: 判讀住在 L3 `financial_health_engine`）。
#:
#: ⚠️ **這張表就是線框那條 note 的修法**：現行 `tab_stock.py` 那組卡用
#: `== 'Good'` 的**布林**判定，欄位取不到就落 else → 紅底 ＋ N/A ＋「辛苦生意」，
#: **把「沒有資料」講成「這是爛生意」**。正確樣板是同檔 80 行後的負債比卡：
#: `{'Pass':綠,'Warning':黃,'Fail':紅,'N/A':灰}.get(status, 灰)` —— 也就是
#: **缺值要有自己的一格，而且落在灰色那一邊**。本表照那個樣板寫：
#: 查不到的 status **不會**掉進任何一個結論，而是被 `_MISSING_STATUSES` 攔下來。
GROSS_MARGIN_LABELS: dict[str, str] = {"Good": "好生意", "Average": "普通"}
OPERATING_MARGIN_LABELS: dict[str, str] = {"Yes": "本業獲利", "No": "本業虧損"}
SAFETY_MARGIN_LABELS: dict[str, str] = {
    "Strong": "抗震極強", "Acceptable": "抗震尚可", "Weak": "抗震不足"}

#: 💰 三格灰態的**指定文案** —— 損益表整張沒回來時講這一句。
#: ⚠️ **客戶已核准的線框原文，逐字收錄，不得改寫、不得「優化」。**
#: 它要同時講完三件事：發生什麼（只拿到一半）、為什麼算不出來（沒有營收
#: 就沒有任何一個「率」）、以及**本站不拿 0 頂替**——
#: 因為「0% 毛利」是一個**結論**，跟「沒有資料」是兩回事。
PROFIT_GAP_WHY: str = (
    "這一輪只拿到一半的財報 → 三張財報表裡，損益表這一輪沒有回來。"
    "沒有營收就算不出任何一個「率」，本站不會拿 0 頂替 ——"
    "「0% 毛利」是一個結論，不是「沒有資料」。")

#: 不是「損益表沒回來」的其他缺值（單一欄位沒抓到、上游標單位異常）走這一句。
#: **兩句分開** —— 共用一句等於對其中一邊說謊（同 `_etf_card` 的註解）。
PROFIT_MISS_WHY: str = (
    "這一格的欄位這一季沒抓到、或上游判定單位異常標了 N/A —— "
    "**這是「沒有資料」，不是「這門生意不好」**；"
    "本站不拿缺值去湊一個負面結論")

#: L3 用來表達「這一格算不出來」的字面。`"N/A"` 是 L3 明文寫的
#: （`Status: "N/A" if _bad_om else ...`）；`""` / `None` 是欄位根本不存在。
_MISSING_STATUSES: frozenset[str] = frozenset({"", "N/A", "None", "none"})


@dataclass(frozen=True)
class ProfitCell:
    """獲利能力三格中的一格。**`label_text` 為空 = 這一格沒有結論可講。**"""

    key: str
    label: str
    value_text: str = ""
    label_text: str = ""

    @property
    def has_value(self) -> bool:
        """有沒有算出來。**只看數值** —— 結論標籤是另一條頻道。

        ⚠️ **刻意不要求 `label_text` 也有值**（自審實測後改）：
        「有 58.2% 但對映表查不到那個 Status」是 **L3 換了詞彙**（契約漂移），
        **不是**「沒有資料」。把它畫成灰色的「資料缺漏」會是第二種說謊 ——
        數字明明在手上，卻對使用者說沒有。
        正確的處置是**照實把數字畫出來、結論那一格留白**：
        `_ui_kit.render_card()` 的契約本來就寫「`signal_text` 空字串 =
        這張卡沒有燈號頻道」。

        真正的「缺值」在更前面就被攔下來了 —— `_cell()` 遇到
        `Value` 為空 / 含 `N/A`、或 `Status` 落在 `_MISSING_STATUSES`，
        回的是一個**兩個欄位都空**的 `ProfitCell`。
        兩個關卡各管一件事：`_cell()` 判「有沒有資料」，本屬性只是讀它。
        """
        return bool(self.value_text)


@dataclass(frozen=True)
class ProfitabilityReadout:
    """💰 獲利能力診斷那一輪的 L3 產出（線框葉1-A 的第 4 個 block）。

    Attributes:
        requested: 同 `StockReadout.requested`（有人叫過 ＋ 判型是個股）。
        cells: 三格（毛利率 / 營業利益率 / 安全邊際）。
        error: 財報取數或體檢**本身**拋出的例外；空字串 = 沒有錯誤。
        upstream_note: L3 回的 `error` 欄（例如「查無此代碼」）——
            **那不是例外，是一個有效的結果**，故不進 `error`。
        income_statement_missing: L3 的 `Profitability_Module.Data_Gap` 說
            **整張損益表這一輪沒回來**（sentinel 是營業收入）。
            ⚠️ 這一格不是「又一個缺值」，它決定灰態要講哪一句：
            整張表沒回來 → `PROFIT_GAP_WHY`（客戶核准的線框原文）；
            單一欄位沒抓到 → `PROFIT_MISS_WHY`。
        gap_why: L3 對上一項寫的原話（`Data_Gap.why`）。**原樣透傳，本檔
            不改寫**（§2.1）—— 只在事實列出現，不進 `Note`。
    """

    requested: bool
    cells: tuple[ProfitCell, ...] = ()
    error: str = ""
    upstream_note: str = ""
    income_statement_missing: bool = False
    gap_why: str = ""


def _cell(key: str, label: str, slot: Any, *, value_field: str,
          status_field: str, labels: Mapping[str, str]) -> ProfitCell:
    """L3 的一個子欄位 → 一格。**缺值一律回空的 `ProfitCell`，不落結論。**"""
    if not isinstance(slot, Mapping):
        return ProfitCell(key=key, label=label)
    _status = str(slot.get(status_field) or "")
    _value = str(slot.get(value_field) or "")
    if _status in _MISSING_STATUSES or "N/A" in _value or not _value:
        return ProfitCell(key=key, label=label)
    return ProfitCell(key=key, label=label, value_text=_value,
                      label_text=labels.get(_status, ""))


def load_profitability(verdict: KindVerdict) -> ProfitabilityReadout:
    """💰 獲利能力三格。**判型不是個股、或還沒有人叫過 → 一行 L3 都不呼叫。**

    路徑（兩支都是 L3）：
        `stock_grp_service.get_financial_statements(code, token)`
        → `financial_health_engine.analyze_financial_health("", code, fin_data)`
        → `["profitability_module"]`

    ⚠️ `api_key=""` 是**刻意**的：那條分支走的是 L3 的**純計算**路徑
    （檔內註解原文「api_key="" → 純 no-AI 路徑」）。本頁的三格是數字與門檻，
    不需要、也不應該讓一次 LLM 呼叫決定它的顏色。

    邊界：
      (a) **判型不是個股** → `requested=False` → idle（ETF 沒有這一組指標）。
      (b) **L3 拋例外** → 紅態。
      (c) **`fin_data` 帶 `error`**（查無此代碼 / 額度用罄）→ **不是例外** →
          三格各自 `empty`，並把 L3 的原話放進 `upstream_note` 給使用者看。
      (d) **某一格的 Status 是 `N/A`** → **只有那一格** `empty`，
          另外兩格照常 live —— 線框 `errCells` 的原文就是這個形狀
          （毛利率⚪ / 營業利益率 42.1% / 安全邊際⚪）。
    """
    _requested = bool(verdict.requested and verdict.is_stock)
    if not _requested:
        return ProfitabilityReadout(requested=False)

    try:
        from src.config.config import get_finmind_token
        _token = str(get_finmind_token() or "")
    except Exception as _e:  # noqa: BLE001 — 讀不到就交給 fetcher 的 env fallback
        print(f"[views/page_inspect] FinMind token 讀取失敗，改用 env fallback：{_e!r}")
        _token = ""

    try:
        from src.services.stock_grp_service import get_financial_statements
        _fin = get_financial_statements(verdict.code, _token)
    except Exception as _e:  # noqa: BLE001 — 轉成紅態顯示，不吞
        print(f"[views/page_inspect] 財報取數失敗 → 獲利能力轉紅態：{_e!r}")
        return ProfitabilityReadout(
            requested=True, error=_error_why(SRC_STATEMENTS, repr(_e)))

    _fin = _fin if isinstance(_fin, Mapping) else {}
    _upstream = str(_fin.get("error") or "")
    try:
        from src.services.financial_health_engine import analyze_financial_health
        _fh = analyze_financial_health("", verdict.code, dict(_fin))
    except Exception as _e:  # noqa: BLE001 — 轉成紅態顯示，不吞
        print(f"[views/page_inspect] 財報體檢失敗 → 獲利能力轉紅態：{_e!r}")
        return ProfitabilityReadout(
            requested=True, upstream_note=_upstream,
            error=_error_why(SRC_HEALTH, repr(_e)))

    _prof = (_fh or {}).get("profitability_module")
    _prof = _prof if isinstance(_prof, Mapping) else {}
    # L3 的缺漏旗標（§1 三律之(3)：輸出帶旗標）。
    # ⚠️ **「是不是損益表整張缺」由 L3 判，本檔不自己去看營收欄位** ——
    #    在 UI 端重判一次，等於把 sentinel 的定義複製成第二份（違 §2.1 SSOT）。
    _gap = _prof.get("Data_Gap")
    _gap = _gap if isinstance(_gap, Mapping) else {}
    try:
        from src.services.financial_health_engine import GAP_INCOME_STATEMENT
        _is_missing = str(_gap.get("missing") or "") == GAP_INCOME_STATEMENT
    except Exception as _e:  # noqa: BLE001 — 常數讀不到就退回「不特別講」
        print(f"[views/page_inspect] Data_Gap 常數讀取失敗：{_e!r}")
        _is_missing = False
    return ProfitabilityReadout(
        requested=True, upstream_note=_upstream,
        income_statement_missing=_is_missing,
        gap_why=str(_gap.get("why") or ""),
        cells=(
            _cell("gross_margin", "毛利率", _prof.get("Gross_Margin"),
                  value_field="Value", status_field="Status",
                  labels=GROSS_MARGIN_LABELS),
            _cell("operating_margin", "營業利益率",
                  _prof.get("Operating_Margin"), value_field="Value",
                  status_field="Core_Business_Profitable",
                  labels=OPERATING_MARGIN_LABELS),
            _cell("safety_margin", "安全邊際", _prof.get("Margin_Of_Safety"),
                  value_field="Value", status_field="Status",
                  labels=SAFETY_MARGIN_LABELS),
        ))


# ══════════════════════════════════════════════════════════════════
# 葉1-A 判決卡②「估值（357 評價）」—— **本批接線**
# ══════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class ValuationReadout:
    """357 存股評價那一輪的產出。**判定由 L2 做，本檔只搬運。**

    Attributes:
        requested: 同 `StockReadout.requested`（有人叫過 ＋ 判型是個股）。
        est_yield_pct: 估計殖利率（%）。`None` ＝ **未評估**（無股價或無配息
            紀錄）。⚠️ **不是 0** —— 0% 會被同一套門檻判成「超貴」，
            那是拿缺資料當看空結論（L2 那支的 docstring 明文警告）。
        zone_code: L2 的位階 code（`cheap` / `fair` / `dear` / `overpriced`
            / `na`）。**字面由 L2 決定，本檔不寫死對照表** —— 只拿它判
            「是不是 `na`」，中文說法一律讀 L2 給的 `signal` / `msg`。
        signal: L2 給的訊號字面（帶圖示，例：`'🟡 合理（5~7%）'`）。
            **原樣收下**；要進訊號頻道時由 `_signal_label()` 去圖示（鐵律 3）。
        msg: L2 自己寫的一句話。**原樣透傳，本檔不改寫**（§2.1）。
        avg_div_twd / paying_years / source / years_n: L3 給的**輸入**與來歷。
            `avg_div_twd is None` ＝ 三段備援都沒有給配息紀錄（**不是 0 元**）；
            `paying_years is None` ＝ 未知（**不是 0 年**）。
        price: 這一輪用的現價（沿用個股那一輪 `fetch_metrics` 的
            `current_price`，**不另外再抓一次**）。
        error: 取數或計算拋出的例外 `repr(e)`；空字串 = 沒有錯誤。
    """

    requested: bool
    est_yield_pct: float | None = None
    zone_code: str = ""
    signal: str = ""
    msg: str = ""
    avg_div_twd: float | None = None
    paying_years: int | None = None
    source: str = ""
    years_n: int = 0
    price: float | None = None
    error: str = ""

    @property
    def has_zone(self) -> bool:
        """L2 判出一個**位階**了沒有。`na`（未評估）不算有值。"""
        return bool(self.est_yield_pct is not None and self.zone_code
                    and self.zone_code != "na")


def load_valuation(verdict: KindVerdict, stock: StockReadout
                   ) -> ValuationReadout:
    """357 存股評價。**判型不是個股、或還沒有人叫過 → 一行 L3 都不呼叫。**

    路徑：L3 `valuation_service.get_stock_dividends(code)`（配息鏈）
    → L2 `v5_modules.calc_dividend_yield_357(price, avg_div_twd=, div_years=)`。

    ⚠️ **現價不另外抓**：用 `stock.price`（個股那一輪 `fetch_metrics` 已經拿
    到的 `current_price`）。再抓一次會有兩個可能不一致的價格，而畫面上沒有
    任何地方講得清楚哪一格用的是哪一個（§2.1）。
    ⚠️ **`price=None` 照樣往下送**：L2 對它有明確處置（回 `zone_code='na'`
    ＋ 訊息「無股價」），本檔**不自己先攔一次**——攔了就變成第二把尺。

    ⚠️ **L5→L2 的 late import 與判型那一支同一個理由**（見檔頭）：
    `src.compute.strategy` 是 eager barrel，實測（量測日 2026-09-07）
    `import src.compute.strategy.v5_modules` 會連帶拉進 pandas ＋ streamlit
    ＋ 12 個 `src.*`。放 module level 會擴大「打開這一頁」的故障半徑。

    邊界（四個都真的走得到）：
      (a) **冷啟動 / 判型是 ETF 或 unknown** → `requested=False` → idle。
      (b) **L3 / L2 拋例外**（含 late import 失敗）→ `repr(e)` → 紅態。
      (c) **三段備援都沒有配息紀錄** → `avg_div_twd=None` → L2 回 `na` →
          **`empty`（灰）**。**這是一個有效結果**：可能真的沒配息、也可能
          三段都沒拿到，兩種可能都寫在卡上（§1 不猜）。
      (d) **有配息但沒有現價** → 同樣 `na`，L2 的 `msg` 會說是「無股價」——
          本檔把它原樣顯示，**不自己判是哪一種**。
    """
    _requested = bool(verdict.requested and verdict.is_stock)
    if not _requested:
        return ValuationReadout(requested=False)

    try:
        from src.services.valuation_service import get_stock_dividends
        _div = get_stock_dividends(verdict.code)
    except Exception as _e:  # noqa: BLE001 — 轉成紅態顯示，不吞
        print(f"[views/page_inspect] 配息取數失敗 → 估值轉紅態：{_e!r}")
        return ValuationReadout(
            requested=True, price=stock.price,
            error=_error_why(SRC_DIVIDENDS, repr(_e)))

    try:
        from src.compute.strategy.v5_modules import calc_dividend_yield_357
        _z = calc_dividend_yield_357(
            stock.price,
            avg_div_twd=_div.avg_div_twd,
            div_years=_div.paying_years)
    except Exception as _e:  # noqa: BLE001 — 轉成紅態顯示，不吞
        print(f"[views/page_inspect] 357 位階計算失敗 → 估值轉紅態：{_e!r}")
        return ValuationReadout(
            requested=True, price=stock.price,
            avg_div_twd=_div.avg_div_twd, paying_years=_div.paying_years,
            source=_div.source, years_n=len(_div.years),
            error=_error_why(SRC_357, repr(_e)))

    _z = _z if isinstance(_z, Mapping) else {}
    return ValuationReadout(
        requested=True,
        est_yield_pct=_num(_z.get("est_yield")),
        zone_code=str(_z.get("zone_code") or ""),
        signal=str(_z.get("signal") or ""),
        msg=str(_z.get("msg") or ""),
        avg_div_twd=_div.avg_div_twd, paying_years=_div.paying_years,
        source=_div.source, years_n=len(_div.years), price=stock.price)


# ══════════════════════════════════════════════════════════════════
# 葉1-A 判決卡③「籌碼」—— **本批接線**
# ══════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class ChipsView:
    """近 20 日籌碼那一輪的產出。**攤平 L3 的 `ChipsReadout`，零再計算。**

    ⚠️ **本檔不重新判一次吸籌／倒貨／發散**：那三個字面與門檻住在 L0
    `shared.macro_compute.analyze_20d_chips_from_df`，由 L3 呼叫一次。
    在畫面上再比一次 `concentration > 5` 就是第二把尺（§2.1），
    而且它會在對面改門檻時無聲漂移。

    Attributes:
        requested: 同 `StockReadout.requested`（有人叫過 ＋ 判型是個股）。
        signal / concentration / continuity / days / pos_days: L0 的產出，
            缺值一律 `None`（**不寫 0**）。
        miss_reason: L0 說「判不出來」的原因原文。空 = 判得出來。
            ⚠️ **這不是故障** → `empty`（灰），不是 `failed`（紅）。
        error: 取數失敗（L1 給的錯誤字串或例外）→ `failed`（紅）。
        days_loaded: 這一輪載入了幾個交易日的日線（＝表單的「期間」）。
            **它不是判讀窗** —— 近 20 日那個窗由 L0 決定，改期間不會改結論。
        outlier_verdict / outlier_ratio / outlier_threshold / outlier_window
            / outlier_reason: 線框那句「含異常值徽章」的那一半，**攤平 L3 的
            同名欄位，零再計算**（2026-09-07 FE-28 接線）。
            ⚠️ 它是**第二個獨立的檢查**，不是集中度的附註：吃的是
            `主力合計` ＋ 均量窗，與集中度吃的 `外資` / `投信` 不同，
            所以「集中度判得出來、徽章判不出來」是**正常組合**。
            ⚠️ `outlier_verdict` 三態：有異常 / **判過了沒有異常** /
            **判不出來**。中間與後面那兩個是兩件事 —— 混為一談就是把
            「沒量到」講成「量到了沒事」。空字串 = 這一輪根本沒跑到
            （必然伴隨 `error`，卡自己已經是紅態）。
            ⚠️ **本檔不重判、也不寫門檻與窗長度**：`outlier_threshold` 來自
            L0 SSOT、`outlier_window` 來自 L2 簽章，都由 L3 讀好帶上來（§3.3）。
    """

    requested: bool
    signal: str = ""
    concentration: float | None = None
    continuity: float | None = None
    days: int | None = None
    pos_days: int | None = None
    rows: int | None = None
    days_loaded: int | None = None
    miss_reason: str = ""
    error: str = ""
    outlier_verdict: str = ""
    outlier_ratio: float | None = None
    outlier_threshold: float | None = None
    outlier_window: int | None = None
    outlier_reason: str = ""

    @property
    def has_verdict(self) -> bool:
        """判出結論了沒有。**缺原因或取數失敗都不算。**

        ⚠️ **不看徽章**（同 L3 `ChipsReadout.has_verdict`）：徽章判不出來
        不該把一個判得出來的集中度連坐成灰態，反之亦然。
        """
        return bool(self.signal) and not self.miss_reason and not self.error


def load_chips(verdict: KindVerdict, req: InspectRequest) -> ChipsView:
    """近 20 日籌碼。**判型不是個股、或還沒有人叫過 → 一行 L3 都不呼叫。**

    路徑：L3 `stock_chips_service.get_chips_readout(code, days=)`
    （內部：L1 `fetch_price_data` → L0 `analyze_20d_chips_from_df`）。

    ⚠️ **`days=req.period_days`**：表單那個「期間」決定**載入多長的日線**。
    它**不是**判讀窗 —— 近 20 日那個窗長度住在 L0（`df.tail(20)`），
    所以把期間從 120 改成 500 **不會**改變籌碼結論。這一句已寫進
    `WIRING_DISCLOSURE_SINGLE`，避免使用者以為調期間就能看「近 60 日籌碼」。

    邊界（四個都真的走得到）：
      (a) **冷啟動 / 判型是 ETF 或 unknown** → `requested=False` → idle。
      (b) **L3 拋例外，或 L1 回錯誤字串** → 紅態。
      (c) **日線回來了但法人欄缺／全為 0／成交量 0／筆數不足** → **灰態**
          ＋ L0 給的原因原文。**沒有人壞掉，是資料缺漏。**
      (d) **判出來了** → live，數字與訊號都是 L0 的。

    ⚠️ **異常值徽章走 (b) 以外的每一條路**：只要 df 回得來（(c) 與 (d) 都是），
    L3 就一定判過一次，所以兩條路都要把 `outlier_*` 帶上來。
    只有 (a)(b) 沒有徽章可帶 —— **那時 `outlier_verdict` 留空**，
    畫面就不出那一列（卡本身已經是灰／紅態，會自己講）。
    """
    _requested = bool(verdict.requested and verdict.is_stock)
    if not _requested:
        return ChipsView(requested=False)

    try:
        from src.services.stock_chips_service import get_chips_readout
        _c = get_chips_readout(verdict.code, days=req.period_days)
    except Exception as _e:  # noqa: BLE001 — 轉成紅態顯示，不吞
        print(f"[views/page_inspect] 籌碼取數失敗 → 轉紅態：{_e!r}")
        return ChipsView(requested=True, days_loaded=req.period_days,
                         error=_error_why(SRC_CHIPS, repr(_e)))

    if _c.error:
        # L1 的「暫時性失敗」走的是回傳值不是例外（它刻意不讓失敗進 cache）。
        # 那仍然是**取數失敗** → 紅態，訊息原樣透傳。
        # ⚠️ 動詞用「回報失敗」不是「拋出例外」—— 這一條路上真的沒有例外，
        # 寫成例外會讓下一個人去 traceback 裡找一個不存在的東西（§1）。
        return ChipsView(requested=True, days_loaded=req.period_days,
                         rows=_c.rows,
                         error=_error_why(SRC_CHIPS, _c.error,
                                          verb="回報失敗"))

    return ChipsView(
        requested=True, signal=_c.signal, concentration=_c.concentration,
        continuity=_c.continuity, days=_c.days, pos_days=_c.pos_days,
        rows=_c.rows, days_loaded=req.period_days,
        miss_reason=_c.miss_reason,
        # 徽章：**與 `miss_reason` 無關地照搬**。df 回得來就一定判過一次，
        # 集中度判不判得出來都一樣（兩支吃的欄位不同，見 L3 檔頭）。
        outlier_verdict=_c.outlier_verdict, outlier_ratio=_c.outlier_ratio,
        outlier_threshold=_c.outlier_threshold,
        outlier_window=_c.outlier_window, outlier_reason=_c.outlier_reason)


# ══════════════════════════════════════════════════════════════════
# 葉1-B：ETF 分支的取數（同一支 L3，`asset_kind='etf'`）
# ══════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class EtfReadout:
    """ETF 那一輪的 L3 產出。**與個股分支重疊近零 —— 共用的是骨架，不是內容。**

    Attributes:
        requested: **「有人叫過」＋「判型判成 ETF」兩件事的合取。**
        premium_pct: 折溢價（%）。`None` = L3 拿不到官方 iNAV（**不是 0%**）。
            ⚠️ L3 檔內註解記著一個已修的事故：末端 fallback 到 yfinance
            `navPrice` 會回「最後已公告淨值」被硬戳今日 → **假溢價**。
            現行契約是拿不到就**不填這個欄位** —— 本檔照收，缺就是缺。
        annual_yield_pct: 年化配息率（%）。`None` = 沒有配息紀錄或抓不到。
        peer_ranks: `{月數: 分位}`，0 = 最強。`None` = 同儕不足 / 抓取失敗。
        quality: L3 的 ETF 品質評等 dict（內扣費用 / AUM / Beta / 殖利率 CV）。
        sharpe / ann_return_3y_pct / inception_years: 其餘可用的中繼資料。
        error: 取數本身拋出的例外 `repr(e)`。**ETF 這一支是 fail-loud 的**：
            拿不到日線 L3 就 `raise`，所以這個欄位比個股那邊常出現。
    """

    requested: bool
    premium_pct: float | None = None
    annual_yield_pct: float | None = None
    peer_ranks: Mapping[int, float] | None = None
    quality: Mapping[str, Any] | None = None
    sharpe: float | None = None
    ann_return_3y_pct: float | None = None
    inception_years: float | None = None
    error: str = ""


def load_etf_readout(verdict: KindVerdict) -> EtfReadout:
    """ETF 指標。**判型不是 ETF、或還沒有人叫過 → 一行 L3 都不呼叫。**

    邊界：
      (a) **冷啟動 / 判型是個股或 unknown** → `requested=False` → idle。
      (b) **L3 拋例外**（拿不到日線 / late import 失敗）→ 紅態。
          線框 `errCells` 的原文就是這個形狀：折溢價🔴、配息🟢、同儕⬜ ——
          注意**三格不同時轉紅**，因為它們不是同一次取數的成敗。
      (c) **回來了但某一格是 `None`** → **只有那一格** `empty`。
    """
    _requested = bool(verdict.requested and verdict.is_etf)
    if not _requested:
        return EtfReadout(requested=False)
    _m, _err = _fetch_metrics(verdict.code, verdict.kind)
    if _err:
        return EtfReadout(requested=True, error=_err)
    _peer = _m.get("peer_ranks")
    _quality = _m.get("etf_quality")
    return EtfReadout(
        requested=True,
        premium_pct=_num(_m.get("premium_pct")),
        annual_yield_pct=_num(_m.get("annual_yield_pct")),
        peer_ranks=_peer if isinstance(_peer, Mapping) else None,
        quality=_quality if isinstance(_quality, Mapping) else None,
        sharpe=_num(_m.get("sharpe")),
        ann_return_3y_pct=_num(_m.get("ann_return_3y_pct")),
        inception_years=_num(_m.get("inception_years")))


# ══════════════════════════════════════════════════════════════════
# 葉2：多檔比較（可混貼）—— 逐檔判型 → 逐檔同一支 L3
# ══════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class BatchRow:
    """批次表的一列。**一檔失敗不作廢其他檔**（線框葉2 err 原文）。

    Attributes:
        code: 代碼。
        kind: 型別字串（判不出來 → L2 的 unknown 字串）。
        kind_label: 型別的中文顯示名（unknown 也有名字，不留白）。
        is_stock / is_etf / is_unknown: 由 `classify_kind()` 一次算好（同 `KindVerdict`）。
        headline: 這一列的一句話結論。**未接線 / 缺值時為空字串**。
        metrics: 攤平成 `(欄位名, 顯示值)` 的中繼資料，直接進表。
        error: **這一檔**的錯誤；空字串 = 這一檔沒事。
    """

    code: str
    kind: str = ""
    kind_label: str = ""
    is_stock: bool = False
    is_etf: bool = False
    is_unknown: bool = False
    headline: str = ""
    metrics: tuple[tuple[str, str], ...] = ()
    error: str = ""

    @property
    def ok(self) -> bool:
        """這一列有沒有成功。**unknown 也算成功** —— 判不出來是有效答案。"""
        return not self.error


@dataclass(frozen=True)
class BatchReadout:
    """一次批次的全部產出。

    Attributes:
        requested: 由 `BatchRequest.submitted` 帶下來，**不是**從 `rows` 反推。
        rows: 逐檔一列（**含失敗的那幾列**，它們要看得見）。
        error: 整批共通的失敗（例如判型模組載不進來）→ 這時 `rows` 是空的。
    """

    requested: bool
    rows: tuple[BatchRow, ...] = ()
    error: str = ""

    @property
    def has_rows(self) -> bool:
        """**只在 `requested=True` 時有意義。**"""
        return bool(self.rows)

    @property
    def failed_codes(self) -> tuple[str, ...]:
        return tuple(_r.code for _r in self.rows if not _r.ok)


def _fmt_pct(value: float | None, *, digits: int = 2) -> str:
    """百分比 → 顯示字串。`None` → `'—'`，**不寫 0%**（§1 不假報）。"""
    return "—" if value is None else f"{value:+.{digits}f}%"


def _fmt_num(value: float | None, *, digits: int = 1, unit: str = "") -> str:
    """數值 → 顯示字串。`None` → `'—'`，**不寫 0**（§1 不假報）。"""
    return "—" if value is None else f"{value:.{digits}f}{unit}"


def _batch_row(code: str, *, stock_kind: str, etf_kind: str,
               kind_labels: Mapping[str, str],
               classify, benchmark_of) -> BatchRow:
    """一檔 → 一列。**每一檔各自 try**，一檔炸不連坐其他檔。

    Args:
        stock_kind / etf_kind: L2 的型別字串 SSOT（`ASSET_STOCK` / `ASSET_ETF`），
            **由 caller 傳進來** —— 本函式不自己 import L2，也就不會多出
            第二份型別字面（線框 F4 引用的 `station_cards.py` 事故就是字面漂移）。
        kind_labels: 型別字串 → 中文顯示名。查不到 → `KIND_LABEL_FALLBACK`。
        classify / benchmark_of: L2 的兩支純函式，同樣由 caller 傳進來。
    """
    try:
        _kind = str(classify(code))
    except Exception as _e:  # noqa: BLE001 — 這一檔判不動，其餘照跑
        print(f"[views/page_inspect] {code} 判型失敗：{_e!r}")
        return BatchRow(code=code, error=repr(_e))

    _label = kind_labels.get(_kind, KIND_LABEL_FALLBACK)
    _is_stock = _kind == stock_kind
    _is_etf = _kind == etf_kind
    _is_unknown = not (_is_stock or _is_etf)
    if _is_unknown:
        # 判不出來 → **不取數**（沒有一條路可以走），但它是一列有效結果。
        return BatchRow(code=code, kind=_kind, kind_label=_label,
                        is_unknown=True)

    _m, _err = _fetch_metrics(code, _kind)
    if _err:
        return BatchRow(code=code, kind=_kind, kind_label=_label,
                        is_stock=_is_stock, is_etf=_is_etf, error=_err)

    if _is_stock:
        _score = _num(_m.get("mj_score_pct"))
        _grade = str(_m.get("mj_grade") or "")
        _name = str(_m.get("name") or "")
        return BatchRow(
            code=code, kind=_kind, kind_label=_label, is_stock=True,
            headline=str(_m.get("mj_headline") or ""),
            metrics=(
                ("名稱", _name or "—"),
                ("財報體檢", (f"{_fmt_num(_score, digits=0)} 分"
                              + (f" · {_grade} 級" if _grade else ""))
                 if _score is not None else "—"),
                ("現價", _fmt_num(_num(_m.get("current_price")), digits=2)),
                ("估值（357）", "未接線"),
                ("籌碼", "未接線"),
            ))

    _bench = benchmark_of(_kind)
    _peer = _m.get("peer_ranks")
    return BatchRow(
        code=code, kind=_kind, kind_label=_label, is_etf=True,
        metrics=(
            ("折溢價", _fmt_pct(_num(_m.get("premium_pct")))),
            ("年化配息率", _fmt_num(_num(_m.get("annual_yield_pct")),
                                     digits=2, unit="%")),
            ("同儕分位（12 月）",
             _fmt_num(_num((_peer or {}).get(12)), digits=2)
             if isinstance(_peer, Mapping) else "—"),
            ("現價", _fmt_num(_num(_m.get("current_price")), digits=2)),
            ("基準", str(_bench or "—")),
        ))


def load_batch_rows(req: BatchRequest) -> BatchReadout:
    """跑一次批次。**`req.submitted` 為 False 時一行 L2／L3 都不呼叫。**

    ⚠️ **篩選只影響顯示，不影響取數**：每一檔都照樣判型與取數，
    否則「其中 1 檔失敗」會在切換篩選時**被篩掉而看不見**
    （線框葉2 err 原文：「其餘 2 檔照常顯示，**不整批作廢**」——
    那句話的前提是失敗的那一檔也還在表上）。

    邊界：
      (a) **冷啟動 / 還沒送出** → `requested=False` → idle。
      (b) **判型模組載不進來** → 整批 `error` → 紅態（沒有任何一列算得出來）。
      (c) **貼了東西但解析不出代碼** → `rows=()` → `empty`（灰，有效結果）。
      (d) **其中幾檔失敗** → 那幾列帶 `error`，**整張表照樣是 live**。
    """
    if not req.submitted:
        return BatchReadout(requested=False)
    if not req.tickers:
        return BatchReadout(requested=True)
    try:
        from src.compute.etf.asset_lag import (
            ASSET_ETF,
            ASSET_STOCK,
            ASSET_UNKNOWN,
            classify_asset_kind,
            pick_benchmark,
        )
    except Exception as _e:  # noqa: BLE001 — 轉成紅態顯示，不吞
        print(f"[views/page_inspect] 判型模組載不進來 → 批次整批轉紅態：{_e!r}")
        return BatchReadout(requested=True, error=repr(_e))

    # 型別字串 → 中文名。**key 一律是 L2 的 SSOT 字串**，本檔不寫死字面。
    _labels = {ASSET_STOCK: "個股", ASSET_ETF: "ETF",
               ASSET_UNKNOWN: KIND_LABEL_FALLBACK}
    _rows = tuple(_batch_row(_c, stock_kind=ASSET_STOCK, etf_kind=ASSET_ETF,
                             kind_labels=_labels, classify=classify_asset_kind,
                             benchmark_of=pick_benchmark)
                  for _c in req.tickers)
    return BatchReadout(requested=True, rows=_rows)


def visible_batch_rows(readout: BatchReadout,
                       req: BatchRequest) -> tuple[BatchRow, ...]:
    """套用型別篩選。**失敗的列永遠留著** —— 它們不屬於任何型別，

    但把它們篩掉就會讓使用者以為那幾檔沒貼到（線框葉2 err 的前提）。
    """
    if req.kind_filter == BATCH_FILTER_ALL:
        return readout.rows
    _want_stock = req.kind_filter == KIND_CHOICE_STOCK
    return tuple(_r for _r in readout.rows
                 if (not _r.ok) or (_r.is_stock if _want_stock else _r.is_etf))


# ══════════════════════════════════════════════════════════════════
# 卡片建構（純函式；`Card` / `Note` 的驗證在對面，本檔不重複）
# ══════════════════════════════════════════════════════════════════
#: 一張卡回傳的形狀：`(Card, facts, signal_text)`。
#: `signal_text` 是**訊號頻道的中文標籤**（鐵律 3：帶 emoji 會被
#: `_ui_kit.assert_signal_text_clean()` 當場 raise —— 狀態頻道的 🔴 與燈號的 🔴
#: 撞在同一張卡上就沒有資訊了）。
_Built = tuple[Card, tuple[tuple[str, str], ...], str]


def build_kind_card(verdict: KindVerdict, req: InspectRequest) -> _Built:
    """線框葉1 ① 的「判型結果」卡（F4：**就地顯示且可手動覆寫**）。

    ⚠️ **facts 兩列並陳、任何狀態都給**：「系統判的」與「這一輪用的」。
    覆寫時兩列會不同 —— 使用者必須看得到自己覆寫掉了什麼，
    否則覆寫本身就變成另一個看不見的分支（線框 F4 引用的
    `station_cards.py` 事故：型別字母打錯 → 可信度虛高到 100%）。
    """
    _state = classify_ui_state(
        requested=verdict.requested,
        error=verdict.error or None,
        # ⚠️ **不是 `bool(verdict.kind)`** —— unknown 也是非空字串，
        #    那樣寫會把「判不出來」畫成綠燈。見 `KindVerdict.is_resolved`。
        has_value=verdict.is_resolved,
        # 判不出型別 **不是故障**：`MISS_NOT_APPLICABLE` 不在 L0 的
        # `FAILED_REASONS` 裡 → 留在灰色。線框葉1-C：「第三條路 · 不是紅態」。
        reason=MISS_NOT_APPLICABLE if verdict.is_unknown else "",
    )
    _facts: list[tuple[str, str]] = [
        ("代碼", verdict.code or "（未輸入）"),
        ("系統判型", verdict.auto_kind_label or "—"),
        ("這一輪採用", verdict.kind_label or "—"),
        ("判型來源",
         ("你手動指定（覆寫了系統判型）" if verdict.overridden
          else f"系統自動（{SRC_CLASSIFY}）")),
        ("比較基準", str(verdict.benchmark or "—（判不出型別就沒有基準）")),
        ("期間 / 均線",
         f"{req.period_days} 交易日 · "
         + ("、".join(f"MA{_m}" for _m in req.mas) if req.mas else "未勾任何均線")),
    ]

    if _state == UI_LIVE:
        return (Card(key="inspect.kind", label="判型結果", state=UI_LIVE,
                     value=verdict.kind_label),
                tuple(_facts), "手動指定" if verdict.overridden else "自動判型")

    if _state == UI_IDLE:
        _note = Note(now=SINGLE_IDLE_NOW, why=SINGLE_IDLE_WHY,
                     where=SINGLE_IDLE_WHERE)
    elif _state == UI_FAILED:
        _note = Note(
            now="**判型判不動了**",
            why=_error_why(SRC_CLASSIFY, verdict.error),
            where=("這一格壞掉時**手動覆寫也救不回來** —— 型別字串的唯一真相源"
                   f"就在那個模組裡，本頁不會自己編一個字面頂替；{NO_EXIT_MARKER}，"
                   "請把上面那行訊息回報給維護者"))
    elif verdict.is_unknown:
        # UI_EMPTY ＋ 判出 unknown = **線框葉1-C 的那一態**（灰，不是紅）。
        _note = Note(now=UNKNOWN_NOW, why=UNKNOWN_WHY, where=UNKNOWN_WHERE)
    else:   # UI_EMPTY ＋ 沒有代碼 = 按了送出但沒填。**與冷啟動 idle 不同。**
        _note = Note(now=BLANK_TICKER_NOW, why=BLANK_TICKER_WHY,
                     where=BLANK_TICKER_WHERE)
    return Card(key="inspect.kind", label="判型結果", state=_state,
                note=_note), tuple(_facts), ""


def build_unknown_card(verdict: KindVerdict) -> _Built:
    """線框葉1-C「unknown 分支」的獨立區塊 —— **第三條路，不是紅態**。

    ⚠️ 它與 `build_kind_card()` 的 empty 分支**不是同一張卡**：
    判型卡回答「系統判成什麼」，本卡回答「所以接下來會發生什麼」
    （答案是：什麼都不會發生，本站停在這裡）。線框把它畫成一個獨立 block，
    因為 v1 沒有它的時候，`unknown` 只能被塞進「未輸入」或「抓取失敗」——
    **兩個都是說謊**。

    狀態一律 `empty` ＋ `MISS_NOT_APPLICABLE`：
      · 不是 `failed` —— 判型是接好的、而且正常運作，它只是誠實地說判不出來；
      · 不是 `unwired` —— `unwired` 的語意是「這個功能沒接」，這裡接了；
      · 不是 `idle` —— 使用者確實叫過了。
    """
    _state = classify_ui_state(
        requested=verdict.requested, has_value=False,
        reason=MISS_NOT_APPLICABLE)
    return (Card(key="inspect.unknown", label="判不出型別 —— 已停在這裡",
                 state=_state,
                 note=Note(now=UNKNOWN_NOW, why=UNKNOWN_WHY,
                           where=UNKNOWN_WHERE)),
            (("代碼", verdict.code or "（未輸入）"),
             ("系統判型", verdict.auto_kind_label or "—"),
             ("本站的處置", "不猜、不硬塞進個股或 ETF 任何一邊（§4.6）")),
            "")


def build_health_card(stock: StockReadout) -> _Built:
    """線框葉1-A 判決卡①「健康度」。走 L3 的財報體檢綜合分。

    ⚠️ **`score_pct is None` 是 `empty` 不是 `failed`**：L3 對個股是
    best-effort（財報那一腿沒抓到就填 `None`），沒有人壞掉。
    ⚠️ **也不寫 0 分** —— 0 分是一個結論（「這公司爛透了」），缺值不是。
    """
    _state = classify_ui_state(
        requested=stock.requested,
        error=stock.error or None,
        has_value=(stock.score_pct is not None))
    _facts: list[tuple[str, str]] = []
    if stock.name:
        _facts.append(("名稱", stock.name))
    if stock.price is not None:
        _facts.append(("現價", _fmt_num(stock.price, digits=2)))
    if stock.headline:
        # L3 自己寫的一句話。**原樣透傳**（§2.1：那是 L3 的話）。
        _facts.append(("L3 總結", stock.headline))
    if stock.fail_items:
        _facts.append(("不及格項目", "、".join(stock.fail_items)))
    if stock.trend_verdict:
        _facts.append(("跨季趨勢", str(stock.trend_verdict.get("verdict") or "—")))

    if _state == UI_LIVE:
        _value = (f"{_fmt_num(stock.score_pct, digits=0)} / 100"
                  + (f" · {stock.grade} 級" if stock.grade else ""))
        return (Card(key="inspect.stock.health", label="健康度",
                     state=UI_LIVE, value=_value),
                tuple(_facts), stock.grade or "")

    if _state == UI_IDLE:
        _note = Note(now=SINGLE_IDLE_NOW, why=SINGLE_IDLE_WHY,
                     where=SINGLE_IDLE_WHERE)
    elif _state == UI_FAILED:
        _note = Note(now="**健康度算不出來**",
                     why=_error_why(SRC_METRICS, stock.error),
                     where=("先確認代碼與網路／proxy；細節在"
                            f"{ia_nav.where_to_find(ia_nav.SECTION_WHY_DATA_HEALTH)}"))
    else:   # UI_EMPTY
        _note = Note(
            now="**這一檔的財報體檢分數算不出來**",
            why=("**這是一個有效的結果**（已經查完，不是還沒查、也不是故障）—— "
                 "多半是這一檔的季報還沒進 FinMind、或該季欄位缺得太多；"
                 "本站不拿 0 分頂替，0 分是一個結論、不是缺值"),
            where=("新上市或剛換季的標的等資料補齊；若持續如此，到"
                   f"{ia_nav.where_to_find(ia_nav.SECTION_WHY_DATA_HEALTH)}"
                   "看 FinMind／MOPS 備援鏈是否可用"))
    return Card(key="inspect.stock.health", label="健康度", state=_state,
                note=_note), tuple(_facts), ""


def _fmt_div(value: float | None) -> str:
    """股利／殖利率 → 顯示字串。`None` → `'—'`，**不寫 0**（§1 不假報）。"""
    return "—" if value is None else _fmt_num(value, digits=2)


def build_valuation_card(val: ValuationReadout) -> _Built:
    """線框葉1-A 判決卡②「估值（357 評價）」—— **本批已接線**（見檔頭 1）。

    ⚠️ **簽章從 `(requested: bool)` 改成吃一份 readout，這是接線的一部分**：
    前一批它是 `wired=False` 的死卡，不需要任何資料；接上之後它必須能講出
    「這一輪算出什麼 / 為什麼算不出來」，`bool` 帶不動那些事實。

    ⚠️ **`na` 是 `empty`（灰），不是 `failed`（紅）**：L2 對「無股價」與
    「無配息紀錄」都回 `zone_code='na'` ＋ `est_yield=None`，那是**這套法則
    不適用這一檔**，不是系統壞掉。把它畫成紅色就是捏造一個不存在的故障
    （`CLAUDE.md §1.A` 第 4 點）。
    ⚠️ **也不寫 0%**：0% 會被同一套門檻判成「超貴」——
    那是拿缺資料當看空結論（L2 那支的 docstring 明文警告）。

    ⚠️ **中文說法一律讀 L2 的 `signal` / `msg`**，本檔不寫第二份
    便宜／合理／昂貴對照表（§2.1；判型那一格立的是同一個判例）。
    """
    _state = classify_ui_state(
        requested=val.requested,
        error=val.error or None,
        has_value=val.has_zone)

    # ⚠️ **缺值的括號說明只在 `empty` 時給**（自審實測後改）：
    # `idle`（還沒有人叫過）與 `failed`（上游炸了）這兩態根本沒跑到取數，
    # 卻印「沒有拿到配息紀錄」「三段都沒有給」，等於**替一輪沒發生的取數
    # 宣稱它的結果**（§1：錯誤的數字比沒有數字更危險，錯誤的敘述亦然）。
    # 那兩態的原因由 Note 講（它才知道是「還沒叫」還是「炸了」）。
    _ran = (_state == UI_EMPTY)
    _facts: list[tuple[str, str]] = [
        ("近 5 年平均年現金股利",
         ("—（備援鏈跑完，沒有一段給出紀錄）" if _ran else "—")
         if val.avg_div_twd is None else f"{_fmt_div(val.avg_div_twd)} 元／股"),
        ("近 5 年有配息年數",
         ("—（未知，不是 0 年）" if _ran else "—")
         if val.paying_years is None else f"{val.paying_years} 年"),
        ("配息資料來源",
         val.source or ("—（FinMind／yfinance／TWSE 三段都沒有給）"
                        if _ran else "—")),
        ("這一輪用的現價",
         ("—（日線那一腿沒抓到）" if _ran else "—")
         if val.price is None else _fmt_num(val.price, digits=2)),
    ]
    if val.msg:
        # L2 自己寫的一句話（含三檔目標價或「不適用」的理由）。
        # **原樣透傳**：那是 L2 的話，本檔不改寫、不摘要（§2.1）。
        _facts.append(("L2 說明", val.msg))

    if _state == UI_LIVE:
        return (Card(key="inspect.stock.valuation", label="估值（357 評價）",
                     state=UI_LIVE,
                     value=f"殖利率 {_fmt_div(val.est_yield_pct)}%"),
                tuple(_facts), _signal_label(val.signal))

    if _state == UI_IDLE:
        _note = Note(now=SINGLE_IDLE_NOW, why=SINGLE_IDLE_WHY,
                     where=SINGLE_IDLE_WHERE)
    elif _state == UI_FAILED:
        _note = Note(now="**357 估值算不出來**", why=val.error,
                     where=("先確認代碼與網路／proxy；細節在"
                            f"{ia_nav.where_to_find(ia_nav.SECTION_WHY_DATA_HEALTH)}"))
    else:   # UI_EMPTY —— **有效結果**：這套法則不適用這一檔，或缺一半輸入。
        # 「是缺股價還是缺配息」由 L2 的 `msg` 說（它已經寫明），本檔不再判一次；
        # 只有「三段備援都沒給」這一種 L2 講不出來（它看不到來源），本檔補。
        #
        # ⚠️ **`msg` 進 `Note` 前一定要洗 glyph**（自審實測後補）：
        # `Note.__post_init__` 拒收狀態 glyph，而本函式是在 `_render_one()`
        # 的**保護圈外**被呼叫的（`_render_stock_branch` 先建好三張卡才畫）——
        # 上游哪天在 `msg` 裡放一個 `🔴`，這裡就會拋 `ValueError` 並炸掉**整頁**，
        # 而不是畫出那張灰卡。§1 要的是「狀態看得見」，不是換一種炸法。
        # 洗的動作走 `tab_today.scrub_state_glyphs()` SSOT，不自己列符號表。
        _why = (VALUATION_NO_SOURCE_WHY if not val.source and not val.years_n
                else (scrub_state_glyphs(val.msg)[0]
                      or "357 殖利率法則在這一檔上不適用"))
        _note = Note(now="**這一檔算不出 357 位階**",
                     why=f"{_why}{VALUATION_WHY_TAIL}",
                     where=VALUATION_WHERE)
    return (Card(key="inspect.stock.valuation", label="估值（357 評價）",
                 state=_state, note=_note), tuple(_facts), "")


def build_chips_card(chips: ChipsView) -> _Built:
    """線框葉1-A 判決卡③「籌碼」—— **本批已接線**（見檔頭 2）。

    ⚠️ **簽章從 `(requested: bool)` 改成吃一份 readout**，理由同上一支。

    ⚠️ **三種「沒有籌碼結論」對到三個不同的狀態**：
      · 還沒載入 → `idle`（灰）；
      · 日線抓不到 → `failed`（紅，L1 說了原因）；
      · 日線有了但法人欄缺／全為 0／成交量 0 → `empty`（灰，**資料缺漏**）。
    把第三種畫成紅色就是把「沒有資料」講成「系統壞了」；
    畫成綠色 ＋ 0% 集中度則是把缺值講成「買賣超剛好抵銷」這個結論。兩個都是說謊。

    ⚠️ **本檔不重判吸籌／倒貨／發散**：那三個字面與門檻住在 L0，
    由 L3 呼叫一次（見 `ChipsView` 的 docstring）。

    ═══ 異常值徽章（2026-09-07 FE-28 接線）═══════════════════════════
    線框對這一格的原文是「近 20 日主力買賣超與集中度，**含異常值徽章**」。
    徽章走 `facts` 的一列（`CHIPS_OUTLIER_LABEL`），**不佔訊號頻道**，
    也**不改變這張卡的狀態**。三個理由：

      1. **訊號頻道一張卡只有一個**，而它已經被 L0 的籌碼訊號
         （吸籌／倒貨／發散）佔住了。塞第二個進去就是同一張卡兩盞燈打架
         —— `_ui_kit` 檔頭鐵律 3 要防的正是這件事。
      2. **徽章載的是判決語（有異常／沒有異常），不是 band 觀測。**
         依 `_ui_kit.render_card` 對 `signal_text` 的判準（2026-09-07 獨立
         稽核裁定）：載 band／level 觀測 → 照出；**載判決語 → 留白**。
      3. **不改卡的狀態**，因為徽章與集中度是**兩個獨立的檢查**：徽章判不
         出來時把整張卡打成灰的，會把一個**判得出來的集中度**一起藏掉；
         反過來把卡打成綠的，又會替判不出來的那一半背書。狀態頻道跟著
         **集中度**走，徽章在自己那一列把話講完。

    ⚠️ **「判不出來」與「判過了沒有異常」在畫面上必須看得出差別。**
    既有 🔬 個股分頁的寫法是 `if _inst_flag.is_outlier:` 才畫徽章 ——
    於是兩者長得一模一樣（都是沒有徽章），而使用者只會讀成後者。
    本檔三態各出一句話，**判不出來那一句還明說「這不等於沒有異常」**。
    """
    _state = classify_ui_state(
        requested=chips.requested,
        error=chips.error or None,
        has_value=chips.has_verdict)

    _facts: list[tuple[str, str]] = [
        ("判讀窗",
         ("—" if chips.days is None else f"最近 {chips.days} 個交易日")
         + "（窗長度由上游決定，**不隨表單的「期間」改變**）"),
        ("本輪載入",
         "—" if chips.days_loaded is None
         else f"{chips.days_loaded} 個交易日的日線"
              + (f"（實得 {chips.rows} 列）" if chips.rows is not None else "")),
    ]
    if chips.continuity is not None:
        _facts.append(("連續性",
                       f"{_fmt_num(chips.continuity, digits=1)}% 的交易日是"
                       "法人淨買超"
                       + (f"（{chips.pos_days} / {chips.days} 日）"
                          if chips.pos_days is not None
                          and chips.days is not None else "")))
    # 線框那句「含異常值徽章」的那一半。**三態一律出這一列**（含「判不出來」）
    # —— 只在「這一輪根本沒跑到」時回 `None`，見 `_outlier_fact` 的 docstring。
    _badge = _outlier_fact(chips)
    if _badge is not None:
        _facts.append(_badge)
    if chips.miss_reason:
        # L0 自己給的原因原文（`'df缺法人/量欄'` …）。**不改寫**（§2.1）。
        _facts.append(("上游說明", chips.miss_reason))

    if _state == UI_LIVE:
        return (Card(key="inspect.stock.chips", label="籌碼", state=UI_LIVE,
                     value=(f"集中度 {_fmt_num(chips.concentration, digits=2)}%")),
                tuple(_facts), _signal_label(chips.signal))

    if _state == UI_IDLE:
        _note = Note(now=SINGLE_IDLE_NOW, why=SINGLE_IDLE_WHY,
                     where=SINGLE_IDLE_WHERE)
    elif _state == UI_FAILED:
        _note = Note(now="**籌碼算不出來**", why=chips.error,
                     where=("先確認代碼與網路／proxy；細節在"
                            f"{ia_nav.where_to_find(ia_nav.SECTION_WHY_DATA_HEALTH)}"))
    else:   # UI_EMPTY —— 日線回來了，但判不出籌碼。**資料缺漏，不是故障。**
        # ⚠️ 洗 glyph 的理由同 `build_valuation_card` 的 empty 分支：
        # 這句話會把**上游的原文**插進 `Note`，而本函式在 `_render_one()` 的
        # 保護圈外執行 —— 不洗就會把一張該畫出來的灰卡變成整頁未捕捉例外。
        _note = Note(
            now="**這一檔判不出近 20 日籌碼**",
            why=(f"{CHIPS_MISS_WHY_HEAD}"
                 f"{scrub_state_glyphs(chips.miss_reason)[0] or '上游沒有說'}"
                 f"{CHIPS_MISS_WHY_TAIL}"),
            where=CHIPS_WHERE)
    return (Card(key="inspect.stock.chips", label="籌碼", state=_state,
                 note=_note), tuple(_facts), "")


def build_profit_cards(prof: ProfitabilityReadout) -> tuple[_Built, ...]:
    """線框葉1-A 第 4 個 block「💰 獲利能力診斷」的三格（**缺值三律樣板**）。

    ⚠️ **這一組就是線框那條 note 的修法**：缺值是**灰**的「資料缺漏」，
    不是**紅**的「辛苦生意」。現行 `tab_stock.py` 那組卡用 `== 'Good'` 的布林
    判定，欄位取不到就落 else → 紅底 ＋ N/A ＋「辛苦生意」，
    **把「沒有資料」講成「這是爛生意」**。

    ⚠️ **三格各自判態**（線框 `errCells` 的形狀就是這樣：毛利率⚪ /
    營業利益率 42.1% / 安全邊際⚪）。掛在區塊上會讓「只有一格缺」被另外兩格
    替它通過 —— `_ui_kit` 檔頭寫的「粒度就是一張卡」。
    """
    _labels = ("毛利率", "營業利益率", "安全邊際")
    _keys = ("gross_margin", "operating_margin", "safety_margin")
    _cells = {_c.key: _c for _c in prof.cells}
    _facts_list: list[tuple[str, str]] = []
    if prof.upstream_note:
        # L3 回的 `error` 欄（查無此代碼 / 額度用罄）**不是例外**，
        # 是一個有效的結果 —— 原樣給使用者看，本檔不改寫（§2.1）。
        _facts_list.append(("L3 說明", prof.upstream_note))
    if prof.gap_why:
        # L3 對缺漏寫的原話（哪個欄位、為什麼判成缺漏）。**原樣透傳**，
        # 但先洗掉狀態 glyph —— 這裡在 `_render_one()` 的保護圈外，
        # 帶 glyph 的上游字串會讓一張該畫出來的灰卡變成整頁未捕捉例外
        # （同 `build_chips_card` 的 empty 分支）。
        _facts_list.append(("缺漏原因", scrub_state_glyphs(prof.gap_why)[0]))
    _facts: tuple[tuple[str, str], ...] = tuple(_facts_list)

    _out: list[_Built] = []
    for _key, _label in zip(_keys, _labels):
        _cell_obj = _cells.get(_key, ProfitCell(key=_key, label=_label))
        _state = classify_ui_state(
            requested=prof.requested,
            error=prof.error or None,
            has_value=_cell_obj.has_value)
        if _state == UI_LIVE:
            _out.append((Card(key=f"inspect.profit.{_key}", label=_label,
                              state=UI_LIVE, value=_cell_obj.value_text),
                         _facts, _cell_obj.label_text))
            continue
        if _state == UI_IDLE:
            _note = Note(now=SINGLE_IDLE_NOW, why=SINGLE_IDLE_WHY,
                         where=SINGLE_IDLE_WHERE)
        elif _state == UI_FAILED:
            _note = Note(now=f"**{_label}算不出來**", why=prof.error,
                         where=("先確認代碼與 FinMind 額度；細節在"
                                f"{ia_nav.where_to_find(ia_nav.SECTION_WHY_DATA_HEALTH)}"))
        else:   # UI_EMPTY —— **這一格就是線框點名要修的那一格。**
            # ⚠️ **兩種缺值，兩句話**：整張損益表沒回來（`PROFIT_GAP_WHY`，
            #    客戶核准的線框原文）vs 單一欄位沒抓到／單位異常
            #    （`PROFIT_MISS_WHY`）。共用一句會對其中一邊說謊。
            _note = Note(
                now=f"**{_label}：資料缺漏**",
                why=(PROFIT_GAP_WHY if prof.income_statement_missing
                     else PROFIT_MISS_WHY),
                where=("其餘兩格若有值就照常顯示，不必重按；"
                       "季報補齊後這一格會自己回來。持續缺漏請到"
                       f"{ia_nav.where_to_find(ia_nav.SECTION_WHY_DATA_HEALTH)}"
                       "看 FinMind／MOPS 備援鏈"))
        _out.append((Card(key=f"inspect.profit.{_key}", label=_label,
                          state=_state, note=_note), _facts, ""))
    return tuple(_out)


# ══════════════════════════════════════════════════════════════════
# 葉1-B ETF 判決卡（骨架同 A，**內容全換** —— 線框：重疊近零）
# ══════════════════════════════════════════════════════════════════
def _etf_card(key: str, label: str, etf: EtfReadout, *,
              has_value: bool, value: str, signal: str,
              empty_now: str, empty_why: str, empty_where: str,
              facts: Sequence[tuple[str, str]] = ()) -> _Built:
    """ETF 三格共用的建構器。**三格各自判態**（線框 errCells 的形狀）。

    ⚠️ 共用的只有「怎麼判態、怎麼組卡」；每一格的 label / value / 缺值理由
    **全部由呼叫端給** —— 折溢價缺與配息缺是兩件完全不同的事，
    共用一句「資料缺漏」等於對其中一邊說了謊。
    """
    _state = classify_ui_state(
        requested=etf.requested,
        error=etf.error or None,
        has_value=has_value)
    if _state == UI_LIVE:
        return (Card(key=key, label=label, state=UI_LIVE, value=value),
                tuple(facts), signal)
    if _state == UI_IDLE:
        _note = Note(now=SINGLE_IDLE_NOW, why=SINGLE_IDLE_WHY,
                     where=SINGLE_IDLE_WHERE)
    elif _state == UI_FAILED:
        _note = Note(
            now=f"**{label}取不到**",
            why=_error_why(SRC_METRICS, etf.error),
            where=("這一支 L3 對 ETF 是 fail-loud 的（拿不到日線就直接拋）—— "
                   "先確認代碼與網路／proxy；細節在"
                   f"{ia_nav.where_to_find(ia_nav.SECTION_WHY_DATA_HEALTH)}"))
    else:   # UI_EMPTY
        _note = Note(now=empty_now, why=empty_why, where=empty_where)
    return Card(key=key, label=label, state=_state, note=_note), tuple(facts), ""


def build_premium_card(etf: EtfReadout) -> _Built:
    """線框葉1-B 判決卡①「折溢價」。

    ⚠️ **缺值一定要是 `empty`，不能填 0%。** L3 檔內註解記著一個已修的事故：
    末端 fallback 到 yfinance `navPrice` 會回「最後已公告淨值」被硬戳今日 →
    **假溢價 +5.07%** 觸發假燈。現行 L3 契約是拿不到就**不填這個欄位**，
    本檔照收 —— 把它顯示成 0%（＝「貼近淨值」這個結論）是同一個錯的另一半。
    """
    return _etf_card(
        "inspect.etf.premium", "折溢價", etf,
        has_value=(etf.premium_pct is not None),
        value=_fmt_pct(etf.premium_pct), signal="",
        empty_now="**這一檔沒有折溢價資料**",
        empty_why=("上游拿不到同日的官方 iNAV（或三道守門員判定它不可信）—— "
                   "**這是「沒有淨值」，不是「折溢價為 0」**；"
                   "本站不拿最後一次公告的淨值硬戳今天的價格算一個假溢價"),
        empty_where=("等當日官方 iNAV 公告；規模小或剛掛牌的 ETF 常態如此。"
                     "重按不會讓淨值提早出現"))


def build_dividend_card(etf: EtfReadout) -> _Built:
    """線框葉1-B 判決卡②「配息」。"""
    return _etf_card(
        "inspect.etf.dividend", "配息", etf,
        has_value=(etf.annual_yield_pct is not None),
        value=_fmt_num(etf.annual_yield_pct, digits=2, unit="%"),
        signal="年化配息率",
        empty_now="**這一檔查不到近一年的配息紀錄**",
        empty_why=("**這是一個有效的結果**：可能它真的沒配過息（累積型／剛掛牌），"
                   "也可能上游這一輪沒回配息序列。本站不把兩者都寫成 0%，"
                   "因為 0% 是「不配息」這個結論"),
        empty_where=("到公開資訊觀測站或發行商網站對一次配息公告；"
                     "若確定有配過息卻查不到，到"
                     f"{ia_nav.where_to_find(ia_nav.SECTION_WHY_DATA_HEALTH)}看來源狀態"))


def build_peer_card(etf: EtfReadout) -> _Built:
    """線框葉1-B 判決卡③「追蹤／同儕」。

    分位（0 = 最強、1 = 最弱）由 L3 換算好，**本檔不重新換算**
    （L3 的 `_fetch_peer_ranks` docstring 明寫 percentile → 分位的方向）。
    """
    _peer = etf.peer_ranks or {}
    _p12 = _num(_peer.get(12))
    _facts = tuple(
        (f"近 {_m} 月分位", _fmt_num(_num(_peer.get(_m)), digits=2))
        for _m in (3, 6, 12) if _peer.get(_m) is not None)
    if etf.quality:
        _facts += (("品質評等", str(etf.quality.get("stars") or "—")),)
    if etf.inception_years is not None:
        _facts += (("成立年數", _fmt_num(etf.inception_years, digits=1, unit=" 年")),)
    return _etf_card(
        "inspect.etf.peer", "追蹤／同儕", etf,
        has_value=(_p12 is not None),
        value=f"近 12 月分位 {_fmt_num(_p12, digits=2)}",
        signal="0 = 同類最強", facts=_facts,
        empty_now="**同儕排名算不出來**",
        empty_why=("同類 ETF 的檔數不足以排名，或同儕那一腿這一輪抓取失敗 —— "
                   "L3 對這一格是 best-effort（算不出就回 `None`），"
                   "**不會拿一個中位數頂替**"),
        empty_where=("冷門或剛掛牌的類別常態如此；重按通常不會改變。"
                     "細節在"
                     f"{ia_nav.where_to_find(ia_nav.SECTION_WHY_DATA_HEALTH)}"))


# ══════════════════════════════════════════════════════════════════
# 兩支明細（線框葉1-A 第 3 個 block ／ 葉1-B 的明細列）—— **本批未接線**
# ══════════════════════════════════════════════════════════════════
#: 線框葉1-A 明細的順序（`live` 原文逐字，💰 那一段已接線故不在此列）。
STOCK_DETAIL_SECTIONS: tuple[str, ...] = (
    "K 線＋均線", "357 評價河流圖", "財報領先指標", "VCP／布林",
    "月營收", "什麼時候買賣", "心理檢查",
)
#: 線框葉1-B note 的明細順序（逐字）。
ETF_DETAIL_SECTIONS: tuple[str, ...] = (
    "淨值 vs 市價走勢", "折溢價帶", "配息紀錄與以息養股試算",
    "成分股與集中度", "同儕 7 維評分", "標準差買賣帶", "破發檢查",
)


def build_detail_card(requested: bool, *, key: str, label: str,
                      sections: Sequence[str], entry: str) -> _Built:
    """明細那一段的未接線卡（個股 / ETF 各一張，內容全換）。

    `wired=False` → 一律 `unwired`，**按幾次都一樣**。
    ⚠️ **刻意把七段的名字列出來**：只寫「明細未接線」會讓使用者不知道
    自己少看了什麼；列出來他至少知道該去舊分頁找哪幾段。
    """
    _state = classify_ui_state(requested=requested, has_value=False,
                               wired=False)
    return (Card(key=key, label=label, state=_state,
                 note=Note(now=f"**本頁還沒有{label}**", why=DETAIL_WHY,
                           where=DETAIL_WHERE)),
            (("這一段本來會有", " → ".join(sections)),
             ("現行入口", entry),
             ("接線後的樣子", "單欄堆疊、依序排下來（線框：**不用 expander**）")),
            "")


# ══════════════════════════════════════════════════════════════════
# 葉2 批次表的總覽卡
# ══════════════════════════════════════════════════════════════════
def build_batch_card(readout: BatchReadout, req: BatchRequest) -> _Built:
    """線框葉2「多檔比較」的總覽卡。

    ⚠️ **「其中幾檔失敗」不讓整張卡轉紅**（線框 err 原文：「其餘 2 檔照常顯示，
    **不整批作廢**」）。失敗檔數上 facts、也留在表上，但狀態仍是 live ——
    紅色留給「整批都算不出來」那一種。
    """
    _state = classify_ui_state(
        requested=readout.requested,
        error=readout.error or None,
        has_value=readout.has_rows)
    _facts: list[tuple[str, str]] = [
        ("這一批", f"{len(req.tickers)} 檔"),
        ("型別篩選", BATCH_FILTER_LABELS.get(req.kind_filter, req.kind_filter)),
    ]
    if req.truncated:
        _facts.append((
            "超出上限被截掉",
            f"{req.truncated} 檔（一次最多 {BATCH_MAX_TICKERS} 檔）—— "
            "被截掉的那幾檔**沒有查過**，請分批再貼一次"))
    if readout.failed_codes:
        _facts.append((
            "其中失敗",
            "、".join(readout.failed_codes)
            + " —— 其餘照常顯示，**不整批作廢**；單獨重試那幾檔即可"))

    if _state == UI_LIVE:
        _ok = len([_r for _r in readout.rows if _r.ok])
        return (Card(key="inspect.batch", label="批次分析結果", state=UI_LIVE,
                     value=f"{_ok} / {len(readout.rows)} 檔算出來"),
                tuple(_facts), "")
    if _state == UI_IDLE:
        _note = Note(now=BATCH_IDLE_NOW, why=BATCH_IDLE_WHY,
                     where=BATCH_IDLE_WHERE)
    elif _state == UI_FAILED:
        _note = Note(
            now="**整批都算不出來**",
            why=_error_why(SRC_CLASSIFY, readout.error),
            where=(f"這不是某一檔的問題，是判型本身載不進來；{NO_EXIT_MARKER}，"
                   "請把上面那行訊息回報給維護者"))
    else:   # UI_EMPTY
        _note = Note(
            now=BATCH_EMPTY_NOW,
            why=("**這是一個有效的結果**（已經送出，不是還沒送）—— "
                 "輸入框裡沒有任何看起來像代碼的字串"),
            where=("用逗號、空白或換行分隔貼上代碼（例：`2330 00878 2317`），"
                   f"再{press(ACTION_RUN_BATCH_LABEL)}"))
    return Card(key="inspect.batch", label="批次分析結果", state=_state,
                note=_note), tuple(_facts), ""


# ══════════════════════════════════════════════════════════════════
# 渲染（薄；所有判斷都在上面的純函式裡）
# ══════════════════════════════════════════════════════════════════
def _render_one(built: _Built) -> None:
    """畫一張卡，**並且不讓它把整頁畫到一半就死掉**。

    ⚠️ **本體在共用層** `_ui_kit.render_card_isolated()`（頁 1／頁 2 已上移，
    本頁**不寫第三份**）。本函式只剩「把本頁專屬的三樣東西綁上去」：
    log 前綴 / 出處文案（出事的是哪一層只有本頁知道）/ 去哪補。
    """
    _card, _facts, _signal = built
    render_card_isolated(
        _card, facts=_facts, signal_text=_signal,
        owner="views/page_inspect",
        error_why=lambda _err: _error_why(SRC_RENDER, _err),
        where=("這是渲染層的問題，不是你操作的問題 —— "
               f"{NO_EXIT_MARKER}；請把上面那行訊息回報給維護者"))


def _render_row(builts: Sequence[_Built]) -> None:
    """一列卡（鐵律 1：`grid()` 內部硬夾 `MAX_COLS`，多的換行排下一列）。"""
    for _chunk, _columns in grid(tuple(builts), MAX_COLS):
        for _built, _col in zip(_chunk, _columns):
            with _col:
                _render_one(_built)


def _render_ticker_form() -> bool:
    """葉1 ① 輸入表單 —— 鐵律 2 ＋ 鐵律 1 的落點（線框：**全站最大 form 受益點**）。

    Returns:
        這一次 rerun 是否由 submit 觸發。

    結構保證（與 `_ui_kit.single_submit_form()` **同一套契約**）：
      · 一個 `st.form`、**一顆** `st.form_submit_button`；
      · form 內**沒有** `st.button` / `st.download_button`
        （Streamlit 實跑即拋 `StreamlitAPIException`，線框 F11）；
      · widget **當下值**（`SS_*_WIDGET`）與**已套用值**（`SS_APPLIED_TICKER`）
        分家，下游只讀後者 —— 只包一層 `st.form` 只擋得住互動 rerun，
        **重運算一分沒省**，靠的是這一層分家。

    ⚠️ 線框 F11 點名的降階就在這裡：6 個 MA checkbox 原為 `st.columns(6)`，
    本函式走 `grid(MA_OPTIONS, MAX_COLS)` → **3 欄 × 2 排**。
    ⚠️ 為什麼沒有直接用 `_ui_kit.single_submit_form()`：它只吃一組 `st.radio`，
    而這裡需要 text_input ＋ selectbox ×2 ＋ checkbox ×6。見檔頭「鐵律 2 的缺口」。
    """
    with st.form(FORM_TICKER_KEY):
        for _chunk, _columns in grid(("①", "②", "③"), MAX_COLS):
            for _slot, _col in zip(_chunk, _columns):
                with _col:
                    if _slot == "①":
                        st.markdown("**① 代碼**")
                        st.text_input(
                            "代碼", key=SS_TICKER_WIDGET,
                            placeholder="例：2330 或 00878",
                            label_visibility="collapsed")
                        st.selectbox(
                            "判型", list(KIND_CHOICE_LABELS),
                            format_func=lambda _k: KIND_CHOICE_LABELS[_k],
                            key=SS_KIND_WIDGET)
                    elif _slot == "②":
                        st.markdown("**② 期間 / K 線**")
                        st.selectbox(
                            "期間（交易日）", PERIOD_OPTIONS,
                            index=PERIOD_OPTIONS.index(DEFAULT_PERIOD_DAYS),
                            key=SS_PERIOD_WIDGET)
                        st.caption("K 線一律用**還原價**（已還原除權息）。")
                    else:
                        st.markdown("**③ 均線**")
                        st.caption(
                            "預設勾 "
                            + "、".join(f"MA{_m}" for _m in DEFAULT_MAS)
                            + "（線框 ③ 原文）。改完所有均線再送出一次，"
                              "不是每勾一個就整站 rerun 一次。")
        # 6 個 MA checkbox：**3 欄 × 2 排**（線框 F11 的降階）。
        for _chunk, _columns in grid(MA_OPTIONS, MAX_COLS):
            for _ma, _col in zip(_chunk, _columns):
                with _col:
                    st.checkbox(f"MA{_ma}", value=(_ma in DEFAULT_MAS),
                                key=f"{SS_MA_WIDGET_PREFIX}{_ma}")
        _submitted = st.form_submit_button(ACTION_LOAD_INSPECT_LABEL,
                                           type="primary")

    if _submitted:
        # 唯一的寫入點：widget 當下值 → 已套用值。
        # **這個 key 的存在性就是葉1 全部區塊的 `requested=` gate**（見檔頭）。
        st.session_state[SS_APPLIED_TICKER] = {
            "ticker": st.session_state.get(SS_TICKER_WIDGET, ""),
            "period_days": int(st.session_state.get(SS_PERIOD_WIDGET,
                                                    DEFAULT_PERIOD_DAYS)),
            "mas": [_m for _m in MA_OPTIONS
                    if st.session_state.get(f"{SS_MA_WIDGET_PREFIX}{_m}")],
            "kind_choice": st.session_state.get(SS_KIND_WIDGET,
                                                KIND_CHOICE_AUTO),
        }
    st.caption(WIRING_DISCLOSURE_SINGLE)
    return bool(_submitted)


def _render_batch_form() -> bool:
    """葉2 表單 —— 契約同 `_render_ticker_form()`（一 form、一 submit、無 button）。"""
    with st.form(FORM_BATCH_KEY):
        st.text_area(
            "貼一串代碼（可混 個股／ETF；逗號、空白或換行分隔）",
            key=SS_BATCH_WIDGET, height=90,
            placeholder="例：2330 00878 2317 0050")
        st.selectbox(
            "型別篩選（**只影響顯示，不影響取數**）",
            list(BATCH_FILTER_LABELS),
            format_func=lambda _k: BATCH_FILTER_LABELS[_k],
            key=SS_BATCH_FILTER_WIDGET)
        _submitted = st.form_submit_button(ACTION_RUN_BATCH_LABEL,
                                           type="primary")
    if _submitted:
        # 唯一的寫入點（同上）。
        st.session_state[SS_APPLIED_BATCH] = {
            "raw": st.session_state.get(SS_BATCH_WIDGET, ""),
            "kind_filter": st.session_state.get(SS_BATCH_FILTER_WIDGET,
                                                BATCH_FILTER_ALL),
        }
    st.caption(WIRING_DISCLOSURE_BATCH)
    return bool(_submitted)


def _render_stock_branch(verdict: KindVerdict, req: InspectRequest) -> None:
    """葉1-A 個股分支：判決卡（3 欄）→ 明細（單欄堆疊）→ 💰 獲利能力（3 欄 × 2 排）。"""
    _stock = load_stock_readout(verdict)
    section_header("葉1-A 個股分支 · 判決卡",
                   "健康度／估值／籌碼 —— 三格各自判態，一格缺不把另外兩格染色。")
    # ⚠️ **估值那一格吃 `_stock`**：357 要的現價就是健康度那一輪已經拿到的
    # `current_price`，再抓一次會有兩個可能不一致的價格（見 `load_valuation`）。
    _render_row((build_health_card(_stock),
                 build_valuation_card(load_valuation(verdict, _stock)),
                 build_chips_card(load_chips(verdict, req))))

    section_header("葉1-A 個股分支 · 明細（依序）",
                   "線框：**單欄堆疊、不用 expander** —— "
                   "expander 收合只是視覺收合，body 每次 rerun 照跑。")
    _render_one(build_detail_card(
        req.submitted, key="inspect.stock.detail", label="個股明細",
        sections=STOCK_DETAIL_SECTIONS,
        entry="🔬 個股分頁（本頁不重複掛載，避免撞 DuplicateWidgetID）"))

    section_header("💰 獲利能力診斷",
                   "線框 F11：原 `st.columns(5)` → **3 欄 × 2 排**。"
                   "缺值是灰的「資料缺漏」，**不是**紅的「辛苦生意」。")
    _render_row(build_profit_cards(load_profitability(verdict)))


def _render_etf_branch(verdict: KindVerdict, req: InspectRequest) -> None:
    """葉1-B ETF 分支：**骨架同 A，內容全換**（線框：與個股重疊近零）。"""
    _etf = load_etf_readout(verdict)
    section_header("葉1-B ETF 分支 · 判決卡",
                   "折溢價／配息／追蹤·同儕 —— 與個股那三格沒有一個欄位是共用的。")
    _render_row((build_premium_card(_etf), build_dividend_card(_etf),
                 build_peer_card(_etf)))

    section_header("葉1-B ETF 分支 · 明細（依序）",
                   "線框：骨架同 A、**內容全換**。")
    _render_one(build_detail_card(
        req.submitted, key="inspect.etf.detail", label="ETF 明細",
        sections=ETF_DETAIL_SECTIONS,
        entry="🏦 ETF 分頁（本頁不重複掛載，避免撞 DuplicateWidgetID）"))


def _render_single_leaf(session: Mapping[str, Any]) -> None:
    """葉1 單檔診斷：表單 → 判型 → **三分支擇一**。"""
    section_header(f"葉1 · {LEAF_SINGLE_TITLE}",
                   "一個代碼進去，一份判決出來 —— 系統判型，"
                   "然後走兩套完全不同的明細。")
    _render_ticker_form()

    _req = applied_inspect_request(session)
    _verdict = classify_kind(_req)

    section_header("判型結果",
                   "系統判成什麼、這一輪實際用什麼 —— 兩列並陳，覆寫時會不同。")
    _render_one(build_kind_card(_verdict, _req))

    # ── 三分支擇一。**判不出型別時兩支都不畫** —— 那正是葉1-C 的用途。──
    if _verdict.is_stock:
        _render_stock_branch(_verdict, _req)
    elif _verdict.is_etf:
        _render_etf_branch(_verdict, _req)
    elif _verdict.is_unknown:
        section_header("葉1-C 判不出型別",
                       "線框原文：**第三條路 · 不是紅態**。")
        _render_one(build_unknown_card(_verdict))
    else:
        # 冷啟動、代碼空白、或判型本身壞掉 —— 三種都由判型卡自己講完了，
        # 這裡**刻意不再畫第二張卡**（同一件事講兩次 = 兩個可能互相矛盾的說法）。
        # 但個股那三格的 idle 骨架要畫出來，讓人先看到「等一下會拿到什麼」——
        # 線框葉1-A 的 `greyCells` 畫的就是這個。
        if not _verdict.error:
            section_header("等一下會拿到什麼（尚未載入）",
                           "以**個股**分支的三格預覽；輸入 ETF 代碼時"
                           "整組會換成折溢價／配息／追蹤·同儕。")
            # 這一支走到時 `_verdict.is_stock` 必為 False（冷啟動／代碼空白），
            # 三支 loader 都會回 `requested=False` → 三格 idle，
            # **一行 L3 都不會發**（`TestNothingIsCalledBeforeYouAsk` 實測）。
            _stock_idle = load_stock_readout(_verdict)
            _render_row((build_health_card(_stock_idle),
                         build_valuation_card(
                             load_valuation(_verdict, _stock_idle)),
                         build_chips_card(load_chips(_verdict, _req))))


def _render_batch_leaf(session: Mapping[str, Any]) -> None:
    """葉2 多檔比較：表單 → 批次表 → 下鑽（依型別走 A 或 B 的欄位）。"""
    section_header(f"葉2 · {LEAF_BATCH_TITLE}",
                   "客戶已核准**允許混貼** —— 個股與 ETF 可以貼在同一次輸入，"
                   "每一檔各自判型、各自走自己那套欄位。")
    _render_batch_form()

    _req = applied_batch_request(session)
    _readout = load_batch_rows(_req)
    _card, _facts, _signal = build_batch_card(_readout, _req)
    _render_one((_card, _facts, _signal))
    if _card.state != UI_LIVE:
        return

    _rows = visible_batch_rows(_readout, _req)
    if not _rows:
        st.caption("（這個型別篩選底下沒有任何一列 —— "
                   "**失敗的列不會被篩掉**，所以這裡是空的就代表真的沒有。）")
        return

    # ── 批次表。欄位隨型別不同，故攤成「代碼 / 型別 / 狀態 / 明細」四欄，
    #    每一列的指標以 `key=value` 串在「明細」欄 —— 個股與 ETF 的欄位
    #    **重疊近零**，硬併成一張寬表會有一半的格子永遠是空的。────────────
    st.dataframe(
        [{"代碼": _r.code,
          "型別": _r.kind_label,
          "狀態": ("失敗" if not _r.ok else
                   ("判不出型別" if _r.is_unknown else "已算出")),
          "明細": (scrub_state_glyphs(_r.error)[0] if not _r.ok else
                   " · ".join(f"{_k}：{_v}" for _k, _v in _r.metrics)
                   or "（此型別不取數）")}
         for _r in _rows],
        hide_index=True, width="stretch")

    # ── 下鑽：**在 form 外**，而且**零額外 L3 呼叫** —— 換一列看的是
    #    上面那一輪已經算完的結果，不會再發一次取數。───────────────────
    _pickable = [_r.code for _r in _rows if _r.ok and not _r.is_unknown]
    if not _pickable:
        st.caption("（沒有可以下鑽的列 —— 失敗與判不出型別的列沒有明細可展開。）")
        return
    _picked = st.selectbox("下鑽看某一檔的判決卡", _pickable,
                           key=SS_DRILL_WIDGET)
    _row = next((_r for _r in _rows if _r.code == _picked), None)
    if _row is None:
        return
    section_header(f"{_row.code} · {_row.kind_label}",
                   "依型別走 A 或 B 的欄位。**這一段沒有再發任何取數** —— "
                   "顯示的是上面那一輪批次已經算完的同一份結果。")
    for _chunk, _columns in grid(_row.metrics, MAX_COLS):
        for (_k, _v), _col in zip(_chunk, _columns):
            with _col:
                st.markdown(f"**{_k}**　{_v}")
    if _row.headline:
        st.caption(f"L3 總結：{_row.headline}")
    st.caption("要看完整判決卡與明細，請到葉1 用同一個代碼載入 —— "
               "葉1 會走完整的三分支，包含 💰 獲利能力診斷。")


def render_page_inspect() -> None:
    """🔬 查一檔（IA v2 第 3 頁）。~~**本批無 production caller，刻意如此。**~~

    ⚠️ **2026-09-08 FE-36 事實更正（刪除線有意識保留，不是漏刪）**：
    那句在本檔剛落地那一批為真，之後接線的批次沒有回頭改它 ——
    **是 `b5bdb36`（側欄 radio 改動）之前就存在的漂移，不是這次弄壞的。**
    **現行**：`app.py::_ia_view_inspect()` 於側欄「🆕 新版戰情室（試用中）」radio
    選到本頁時 late import 並呼叫本函式。理由與守衛見檔頭 FE-36 那段。
    """
    _session = st.session_state

    st.markdown(f"## {ia_nav.page_label(ia_nav.PAGE_INSPECT)}")
    st.caption("一個代碼進去，一份判決出來 —— 系統判型，"
               "然後走兩套完全不同的明細。")

    _leaf1, _leaf2 = st.tabs([LEAF_SINGLE_TITLE, LEAF_BATCH_TITLE])
    with _leaf1:
        _render_single_leaf(_session)
    with _leaf2:
        _render_batch_leaf(_session)
