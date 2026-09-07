"""src/ui/views/page_find.py — IA v2 第 2 頁「🔍 找標的」的**版面落地**（L5 UI）。

規格出處：`docs/wireframes/stock_ia_v1.html` 的 `PAGES[1]`（id=`find`），
客戶 2026-09-07 明示動工。單一職責（線框 `job` 原文）::

    從全市場縮到一張候選清單。

兩葉（線框 `leaves` 原文）::

    葉1 選股網
    葉2 板塊地圖（＝產業熱力圖＋板塊資金潮汐）

═══ 這個檔**不是**什麼（先讀這段）═════════════════════════════════════
它**不是**一套新的選股邏輯，也**不是**一套新的狀態模型。

- **排名邏輯**一律走 L3 `services.fundamental_screener_service.get_ranked_picks()`
  —— 那是「畫面 / 每月凍結 / MCP / 推播」四處的同源入口（該函式 docstring 明文）。
  本檔**不自己排序、不自己算百分位、不自己決定哪些檔進榜**。
- **四態**一律走 L0 `shared/ui_state.py::classify_ui_state()`。
- **卡片型別**（`Card` / `Note`）與**版面上限** `MAX_COLS` 一律 import
  `src/ui/tabs/tab_today.py` 與 `src/ui/views/_ui_kit.py`，本檔**一個都不複寫**。
- **因子命中數**走 L5 純函式 `tab_stock_picker.summarize_factor_hits()`
  （它的 docstring 明寫「`None` = 沒掃 / 掃失敗 → 不產生片語」，正是 §1 要的
  「掃失敗不假報 0」）。本檔不自己數 tier。

~~**本檔沒有 production caller**（`app.py` 本批不接線；且 FE-7 同時在改該檔，
本批一個字都沒有碰 `app.py` 與 `src/ui/tabs/__init__.py`）。~~舊分頁不動、不下架。

⚠️ **2026-09-07 FE-32 事實更正 —— 上面那句已經不成立，不是漏刪。**
`app.py` 現在**確實掛著本頁**（`with tab_find: render_page_find`，
`_render_tab_isolated` 包著）。那句話是本檔剛落地那一批寫的，當時為真；
之後接線的批次沒有回頭改它。**留著它很危險**：它會讓下一個人以為
「本頁改壞了也不影響線上」，而事實是**本頁每一次 app run 都會被執行**
（Streamlit 全 tab body 都跑）—— 本批那一整段「不准重用舊 widget key」
的理由，前提正是**本頁是活的**。舊分頁仍然不動、不下架（雙軌並存）。

═══ 四大鐵律的落點 ═══════════════════════════════════════════════════
1. **3 欄上限** —— 一律 `_ui_kit.grid()`（內部硬夾 `MAX_COLS`）。
   全檔 **0 個**裸 `st.columns(n)`。
2. **Form 防重繪** —— 條件表單是**一個 form、一顆 `form_submit_button`**；
   `st.button`（🗺️ 載入板塊地圖）與 `st.download_button`（CSV）**都在 form 外**
   （線框 F11：form 內放 `st.button` 實跑即拋 `StreamlitAPIException`）。
   widget 當下值與**已套用值**分家：下游只讀 submit handler 寫進
   `SS_APPLIED_SCREEN` 的那份。
3. **四態分離** —— 見下一段（本頁最容易寫錯的地方）。
4. **空狀態三要素** —— 一律 `tab_today.Note(now, why, where)`，
   三者非空、且不得自帶狀態 glyph（`__post_init__` 會 raise）。

⚠️ **鐵律 2 的一個已知缺口，本檔就地實作 + 回報，未改共用層**：
`_ui_kit.single_submit_form()` 目前**只支援一組 `st.radio`**，
而本頁的條件表單需要 `st.multiselect`（5 個因子）＋ `st.selectbox`（筆數）。
本檔的 `_render_screen_form()` 沿用它**完全相同的契約**
（一個 form / 一顆 submit / form 內無 button / widget 值與已套用值分家），
但**沒有**去改 `_ui_kit.py`（那是頁 1 已交付的共用層，本批的檔案邊界之外）。
→ **交接事項**：`single_submit_form` 應泛化成「form 內容由 caller 提供的
callback 畫、本函式只保證單一 submit 與已套用值寫入」，屆時本函式應被刪除。

═══ `requested=` 的來源（本頁**三個** gate，一個都不是從資料反推）═══════
L0 的鐵律：**`idle` 只能由上游帶下來，禁止由 `if not data:` 推導。**
頁 1 就是在這裡被紅隊抓到恆真式（`get_allocation()` 永不回 `None`，
於是 `requested=(alloc is not None)` 恆為 True、冷啟動沒有 idle 態）。
`tests/test_ui_state_model.py` 只比對 `requested=` 與 `has_value=` 的 AST
是否**逐字相同**，它自己的 docstring 就寫明「是護欄不是證明」——
**守衛綠燈不是合規證明**。本頁的三個 gate 全部是「使用者按過沒有」這個事實：

  1. **選股結果** ← `SS_APPLIED_SCREEN in session_state`。
     那個 key **只有** `_render_screen_form()` 的 submit 分支會寫。
     ⚠️ 不是 `bool(cands_df)`、不是 `not df.empty`、不是 `len(rows) > 0` ——
     那三種都分不出「還沒選」與「選了但 0 檔」。
  2. **板塊地圖（熱力圖 ＋ 泡泡圖）** ← `session_state[SS_MAP_REQUESTED]`。
     那個 key **只有**「🗺️ 載入板塊地圖」的 `st.button` 分支會寫。
  3. **未接線的那一項（產業熱力圖）** ← 同上兩個旗標；它的 `wired=False` 使
     `classify_ui_state` 第 1 條規則先判成 `unwired`，與請求與否無關
     （這是刻意的：未接線**永遠不會**因為多按一次而改變）。
     ⚠️ 估值（本益比）**本批已接線**，不再屬於這一條 —— 它的「沒有資料」
     現在走 `empty` 那條路（重按有機會好），與 `unwired`（重按永遠一樣）
     是兩件事。把接上之後的缺料仍畫成 `unwired`，等於對使用者說
     「沒有出口」，而其實有。

⚠️ **`requested=False` 時本檔一行 L3 都不呼叫。** 沒有輸入就不會有值，
`classify_ui_state` 那條「沒被叫過卻有值 → `ValueError`」在結構上跑不到。

═══ 三種「沒有結果」**絕不可混**（本頁的 §1 主戰場）═════════════════════
    還沒選            → `UI_IDLE`   （灰。**還沒有人叫過**）
    選了、跑完、0 檔  → `UI_EMPTY`  （灰。**這是一個有效的結果**，
                                     不是故障、也不是還沒跑；卡上明講）
    上游掛了          → `UI_FAILED` （紅。**唯一准用紅色的狀態**）

⚠️ **空結果不得冒充綠燈**：本檔**沒有任何一處**把「0 檔」寫成 live。
`Card.__post_init__` 也擋著 —— 非 live 不准帶結論文字（`value`）。
⚠️ 反方向也擋：把「還沒選」畫成紅色錯誤，等於捏造一個不存在的故障
（v3 §02 前半句要杜絕的假性錯誤；`CLAUDE.md §1.A` 第 4 點）。

═══ 取數：**唯一**的規則是「一律走 L3」═══════════════════════════════
    選股排名   L3 `services.fundamental_screener_service.get_ranked_picks`
    存活池     L3 `services.fundamental_screener_service.get_fundamental_survivors`
    估值 / 名稱 L3 `services.valuation_service.get_pe_name_maps`（本批新增）
    缺貨       L3 `services.shortage_screener_service.run_shortage_scan`
    抗跌 RS    L3 `services.rs_leader_service.run_rs_leader_scan`
    跨季轉強   L3 `services.fundamental_screener_service.build_trend_map`
    空頭濾網   L3 `services.allocation_service.get_macro_regime`
    板塊資金   L3 `services.sector_flow_service.get_sector_flow_view`
                 → L4 `ui.render.sector_flow_render.build_sector_flow_figure`（純繪圖）
    產業熱力圖 L3 `services.sector_heatmap_service.get_sector_heatmap_view`（本批新增）
                 → L4 `ui.render.sector_heatmap_render.build_sector_treemap`（純繪圖）
                 類股宇宙與口徑常數走 L0 `shared.sector_heatmap`

**零 L1 import、零 `requests` / `yfinance` / FinMind、零 `pd.read_csv(url)`、
零 SQL / parquet 讀寫、零 `@st.cache_data` / `@st.cache_resource`、
零 inline `ttl=`、零底線開頭的跨檔私有符號、零 `from app import`。**
（前車之鑑：`CLAUDE.md §8.2.A.2` 的 **V-SMART-CACHE-1**〔L5 自建 5 個 cache〕
與 **V-PICKER-PRIV-1**〔L5 直取 L1 的 `_fm_raw_headers`〕。）
⚠️ 本頁**受 `tests/test_c3_layering_guard.py` 管**（`_PATH_LAYERS` 已含
`src/ui/views/` → L5），違反 R4／R5 是 CI 紅燈，不是假綠燈。

═══ 產業熱力圖：**2026-09-07 已接上**（前一批標 unwired，以下是舊登記）═══
~~1. ⛔ **產業熱力圖** —— 線框葉2 的左半。~~
   ~~**卡在哪**：唯一的 public 入口是 L4 `ui.render.etf_render.render_sector_heatmap()`，
   而它**自帶 5 個寫死的 widget key**（`heatmap_market` / `heatmap_period` /
   `heatmap_refresh` / `heatmap_load` / `heatmap_loaded`）與**自己那顆 gate 按鈕**。
   在本頁再呼叫一次 → 與既有 🏦 ETF 分頁**撞 `DuplicateWidgetID`**，
   且畫面會出現**兩顆**載入鈕（線框 N6 明文要求那顆舊 gate 被本頁的
   「🗺️ 載入板塊地圖」**吸收**）。
   類股代表清單（`_US_SECTORS` / `_TW_SECTORS`）與 treemap 組裝
   （`_build_treemap_data`）**都是 L4 的私有符號**，跨檔直取正是
   V-PICKER-PRIV-1 的前車之鑑；自己抄一份類股表則是第二個 SSOT（§2.1）。
   → **本頁標 `unwired`，並在卡上寫明要補在哪**。~~

⚠️ **上面整段加刪除線保留、不刪**（repo 慣例：有意識的政策/狀態變更要留得下
病史）。**它當時的診斷是對的**，本批補的正是它指名要補的三件事；
但其中**有一句是錯的，一併更正**：

  ❌ **舊文寫「與既有 🏦 ETF 分頁撞」—— 分頁指錯了。**
     `render_sector_heatmap()` **不掛在 🏦 ETF 分頁**，它掛在 **🌍 市場環境**
     群組的 `st.tabs(['🌍 總經','🚦 總經 v2','🗺️ 產業熱力圖','🌊 板塊資金潮汐'])`
     第 3 格（`app.py` 的市場環境區塊）。ETF 分頁那邊只有
     `src/ui/etf/etf_dashboard.py` 的 `# noqa: F401` re-export shim
     （`app.py` 解析 `render_sector_heatmap` 的路徑），**它不畫熱力圖**。
     指錯分頁會讓下一個人跑去 ETF 分頁找那顆按鈕、找不到，然後以為這段是舊的。

✅ **本批怎麼接的**（三件事各有落點，一件都不是繞道）：
  1. **類股宇宙上移 L0** —— `shared/sector_heatmap.py` 新增 `US_SECTORS` /
     `TW_SECTORS` / 兩個 `*_SINGLE_STOCK_PROXY` 與 `sector_universe()` /
     `flatten_tickers()` / `coverage_counts()`；`etf_render` 端改為
     `_US_SECTORS = US_SECTORS` 這種**別名轉發**（舊分頁讀到的是同一個物件）。
  2. **treemap 組裝抽成 public L4** —— `ui.render.sector_heatmap_render.`
     `build_sector_treemap()`（`_build_treemap_data` 的本體，邏輯一行未改）。
     它 `return go.Figure`，**留在 L4**；下沉 L2 是 V-LEAD-RENDER-1 的反方向，
     而且 c3 guard 的 `_BANNED_IN_L2` 不含 plotly → 下沉了 CI 也抓不到。
  3. **取數走新的 L3** —— `services.sector_heatmap_service.get_sector_heatmap_view()`
     （內部呼叫**既有** L3 `etf_sector_service.get_sector_returns`）。
     本頁**沒有**、也不需要新增 `EX-PASSTHRU-1` 白名單條目。

⛔ **本頁一個舊 widget key 都沒有重用**（`heatmap_market` / `heatmap_period` /
`heatmap_refresh` / `heatmap_load` / `heatmap_loaded` 五個）。**為什麼這條是硬的**：
Streamlit 每次 app run 會跑**全部** tab body，而本頁的渲染順序在
🌍 市場環境的熱力圖**之前**。共用 `heatmap_loaded` 的話 ——
  · 使用者在舊分頁按過載入 → **本頁會在從未被造訪的情況下發出整批冷抓**
    （本頁台股 42 檔、舊分頁預設美股 66 檔；量測日 2026-09-07，數字會隨
    L0 類股表增刪而變，需要時請現場量 `flatten_tickers()`，不要引用本行）；
  · 反過來，本頁按了載入 → 舊分頁的 opt-in 效能保證當場失效
    （`tests/test_etf_render_heatmap_gate.py` 守的就是那件事）。
共用 **widget** key 更會讓**先執行的那一邊**佔住 ID、**另一邊**拋
`DuplicateWidgetID` —— 也就是會**弄壞舊分頁**。
守衛：`tests/test_p02_find_view.py::TestHeatmapKeysNeverCollideWithTheOldTab`。

⚠️ **本頁的熱力圖沒有市場／區間選擇器**（誠實揭露，不是漏做）：
線框葉2 的 live 原文只有**一顆**「🗺️ 載入板塊地圖」按鈕 ＋ 左右兩張圖，
**沒有畫任何下拉**。加兩個 selectbox ＝ 版面元件增減，依 `CLAUDE.md §-1.5`
v3 §03-2 ① 屬「要先出線框給客戶拍板」的那一類，**不是**內部自決 ——
故本頁固定畫 `HEATMAP_IS_US` / `HEATMAP_PERIOD_LABEL` 這一組，並在卡上寫明
「要切換市場或區間請到 🌍 市場環境 › 🗺️ 產業熱力圖」（兩邊仍並存）。

═══ 本批**新接上**的一項：估值（本益比）因子與「名稱」欄 ═══════════════
✅ **已接線**（2026-09-07 FE-18）。前一批標它 `unwired`，理由是
「`get_ranked_picks(pe_map=, name_map=)` 的 SSOT 住在 **L1**
`src/data/stock/yield_pe_fetcher.fetch_pe_name_maps`，而全 repo 沒有任何
L3 wrapper；L5 直呼 L1 是 R4 違憲，經 `src/ui/tabs/yield_screener.py` 的
re-export 繞道**只是騙過 AST、不改性質**」——
**那個判斷是對的，本批沒有推翻它**：本批補的是它指名要補的東西，
新增 L3 `services.valuation_service.get_pe_name_maps()`（L3 → L1，正常方向）。
⛔ **繞道那條路仍然禁止**：本檔對 `src.data.*` 與 `src.ui.tabs.yield_screener`
都是零 import（`tests/test_p02_find_view.py::TestValuationGoesThroughL3`
以 AST 釘住）。

⚠️ **接上不等於一定有資料**，三態仍然分開講（§1）：
  · 取數拋例外 → 上 `aux_errors`，**該因子不計入**，卡上寫明（不轉紅：
    一個因子掛掉不等於選股掛掉，這與缺貨 / RS 的既有處置一致）；
  · 回**空 map**（上市與上櫃都沒給資料）→ 同上，卡上寫明「這一輪 0 檔有
    本益比」。⚠️ 這一種 L3 的 note **看不見** ——
    `composite_rank_candidates` 的 `_missing` 只收缺貨與 RS，而它的
    「因子實際覆蓋」那句話有 `if _col_scores[_f]` 的前提，**整個因子全空時
    不會印**。所以「估值全空」這句話**只能本頁自己講**；
  · 拿到 N 檔 → **不再畫那則「少算了一個你勾的因子」的 Note**
    （留著就是假警告 —— `CLAUDE.md §1.A` 第 4 點的假性錯誤）。
    部分覆蓋（例如只有上市有）由 L3 自己的「因子實際覆蓋：估值分 N/M」
    那句話揭露，本檔**原樣透傳、不改寫**（§2.1 那是 L3 的話）。

⚠️ **本檔看不出「只有上市或只有上櫃掛了」**：L1 對兩個市場是各自
`try/except … continue` 的 fail-soft，半邊失敗時回一份只有另外半邊的 map
且不留旗標。L3 `get_pe_name_maps()` 的 docstring 已據實標明，本頁不假裝
知道（會反映在 L3 那句「估值分 N/M」的覆蓋率上，但那是**推論**不是**事實**）。

═══ 這個檔擋得住什麼、擋不住什麼（誠實邊界）═══════════════════════════
`load_screen_result()` / `load_sector_flow()` 的 `try/except` 擋得住的是
**呼叫期**例外（模組進得來、但呼叫時炸了）→ 轉成看得見的紅卡 ＋ `repr(e)`。

⛔ **擋不住 module-level 的 import 失敗。** 本檔 module level 有
`from src.ui.tabs.tab_today import ...`、`from src.ui.views._ui_kit import ...`
與四個 `shared.*`。**這幾條路徑上任何一個模組在 import 階段壞掉，
`import page_find` 自己會先 `ImportError`**，`render_page_find()` 根本不會
被呼叫到 —— 畫面全空白，而下面所有 `try/except` 一個都跑不到。

✅ **但故障半徑已經很小**（實測，量測日 2026-09-07，不是推論）：
`import src.ui.views.page_find` 只多帶進 **6 個 `src.*` 模組**
（`src.ui` / `src.ui.tabs` / `src.ui.tabs.tab_today` / `src.ui.views` /
`src.ui.views._ui_kit` / 自己）＋ `plotly`，**沒有 pandas、沒有任何
`src.services.*` / `src.compute.*` / `src.data.*`**。
這是因為 `src/ui/tabs/__init__.py` 已由 FE-7 於 2026-09-07（commit `dffb5fd`）
從 eager barrel 改為 PEP 562 lazy —— 頁 1 的 docstring 記載的「eager barrel
會拉進 152 個 `src.*` ＋ pandas ＋ plotly」是**改版前**的量測值。

⚠️ **本檔不因此宣稱「import 期已經安全」**：上面那 6 個模組仍是硬相依，
它們壞掉一樣是整頁空白。改變的是**數量級**，不是**性質**。

✅ **所有 L3 / L4 取數與繪圖都是函式體內的 late import 且各自包在 `try/except`
裡**（含 `load_factor_labels()` 與泡泡圖的 `build_sector_flow_figure`）——
**實測**（量測日 2026-09-07，本批接線後**重跑過**，不是沿用舊數字）：
把 6 個 L3 模組 ＋ 1 個 L4 模組全部注入 `ImportError` 後整頁仍
`exception == []`，畫出 **3 張紅卡**（條件表單 / 選股結果 / 板塊資金泡泡圖）
＋ **1 張未接線卡**（產業熱力圖），常駐的**口徑揭露**
（`SECTOR_FLOW_AXIS_NOTE`）照樣在最後一行。
第 6 個 L3 就是本批新增的 `services.valuation_service`。

⚠️ **同一次實測順帶發現的一個既有缺口，據實記錄，本批未修**：
`WIRING_DISCLOSURE`（表單下方的接線揭露）在這個情境下**畫不出來**。
機制是 `_render_screen_leaf()`：因子 label 的 L3 SSOT 載不進來時，它
**整支跳過 `_render_screen_form()`**、改畫一張「條件表單不可用」的紅卡，
而那句 caption 就長在被跳過的那支函式的最後一行。
也就是說「常駐」這兩個字對它**不完全成立**：L3 全掛時它會消失
（同一次實測：`SECTOR_FLOW_AXIS_NOTE` 有畫出來、`WIRING_DISCLOSURE` 沒有）。
這是**既有行為**（本批只改了那段字的內容，沒有動它畫在哪裡），
修它要動表單／葉的結構 —— 落在 `CLAUDE.md §-1`／§8.4 step 4 的範圍閘門外。
**登記，不動。**
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

import streamlit as st

from shared import ia_nav
# L0 SSOT：初篩四項的門檻與項數。**禁止在 UI 端寫死「4 項」「<50%」**
# （`PRESCREEN_REQUIRED_PASSES` 的 docstring 原文就是這句）。
from shared.fundamental_prescreen_thresholds import (
    DEBT_RATIO_MAX,
    EPS_MIN,
    PRESCREEN_REQUIRED_PASSES,
)
# L0 SSOT：泡泡圖三軸的視窗長度。口徑揭露那句話的 5 / 5 / 20 一律讀這裡，
# **不手抄數字**（§3.3；線框葉2 ④ 的 live 文案就是這三個數字組出來的）。
from shared.station_specs import (
    MISS_CONTRACT_DRIFT,
    MISS_FETCH_FAILED,
    MISS_TEXT,
)
# L0 SSOT：熱力圖的區間標籤與「台股是單一代表股不是類股平均」那段揭露。
# **本頁不手抄任何一個** —— 區間標籤打錯字時要當場 ValueError，不是靜默畫錯圖。
from shared.sector_heatmap import (
    SECTOR_PERIOD_LABELS,
)
from shared.sector_flow_thresholds import (
    WINDOW_SIZE,
    WINDOW_X,
    WINDOW_Y_MIN_DAYS,
    WINDOW_Y_PRIOR,
    WINDOW_Y_RECENT,
)
from shared.ui_state import (
    UI_DEGRADED,
    UI_FAILED,
    UI_IDLE,
    UI_LIVE,
    classify_ui_state,
)
from src.ui.tabs.tab_today import (
    NO_EXIT_MARKER,
    Card,
    Note,
    scrub_state_glyphs,
)
from src.ui.views._ui_kit import (
    MAX_COLS,
    grid,
    render_card_isolated,
    section_header,
)

# ══════════════════════════════════════════════════════════════════
# session key（本頁自有前綴 `p02`，不與 `app.py` 選股網的 `screener_*`
# 或 `tab_sector_flow` / `etf_render` 的 `heatmap_*` 相撞）
# ══════════════════════════════════════════════════════════════════
#: 條件表單的 key。線框寫 `st.form(form_screen)`；加 `_view` 後綴是為了
#: 與既有選股網（`app.py`）同時掛上時不撞 Streamlit 的 DuplicateWidgetID。
FORM_KEY: str = "form_screen_view"

#: 因子 multiselect 的 widget key —— **當下值**。下游禁止讀（鐵律 2）。
SS_FACTORS_WIDGET: str = "p02v_screen_factors_widget"
#: 顯示筆數 selectbox 的 widget key —— **當下值**。下游禁止讀。
SS_TOPN_WIDGET: str = "p02v_screen_topn_widget"

#: **已套用值**。只有 `_render_screen_form()` 的 submit 分支會寫，
#: 寫入形狀為 `{"factors": [...], "top_n": int}`。
#:
#: ⚠️ **這個 key 的「存在性」就是選股結果的 `requested=` gate。**
#: 不得改成從結果 DataFrame 反推（頁 1 的恆真式事故就是那樣來的）。
SS_APPLIED_SCREEN: str = "_p02_applied_screen"

#: 板塊地圖的 gate 旗標。只有「🗺️ 載入板塊地圖」的 `st.button` 分支會寫。
SS_MAP_REQUESTED: str = "_p02_map_requested"

#: 板塊地圖按鈕的 widget key。
SS_MAP_BUTTON: str = "p02v_load_sector_map"

# ══════════════════════════════════════════════════════════════════
# 產業熱力圖：固定的市場與區間（線框沒有畫下拉，見檔頭「沒有選擇器」那段）
# ══════════════════════════════════════════════════════════════════
#: 本頁熱力圖畫哪個市場。**台股**，理由是這一葉的另一半是「三大法人資金流向」
#: —— 三大法人是 **TWSE** 的東西；同一葉左邊放美股 GICS、右邊放台股法人，
#: 使用者會把兩張圖讀成同一個市場的故事，那是版面造成的誤導。
#: ⚠️ 這是**視覺／業務取捨**，不是技術細節：線框沒指定要哪個市場，
#: 由本批依「同一葉不混市場」判定。**與既有 🌍 市場環境 › 🗺️ 產業熱力圖
#: 的預設（美股）不同** —— 那邊仍可切換，兩邊並存期間不互相覆蓋。
HEATMAP_IS_US: bool = False

#: 本頁熱力圖的區間。取 L0 標籤表的**第一個**（`'1日'`），與既有分頁的
#: `index=0` 同一個值 —— **不手抄字串**，改表時本頁跟著動。
HEATMAP_PERIOD_LABEL: str = SECTOR_PERIOD_LABELS[0]

#: **還沒載入時**要先告訴使用者「等一下會畫哪個市場」的顯示名。
#: ⚠️ 為什麼不直接讀 L3 的 `MARKET_LABEL_TW`：那會變成一個 module-level 的
#: L3 import，本頁對 L3 一律是**函式體內的 late import**（檔頭「擋得住什麼」
#: 那段的前提就是這個）。代價是這個字串在本頁有一份、L3 有一份 ——
#: 兩者**必須一致**，由 `tests/test_p02_find_view.py::
#: TestHeatmapIsWiredAndTellsTheTruth::test_the_idle_market_label_matches_l3`
#: 釘住（不一致就紅燈，不靠自律）。
HEATMAP_MARKET_LABEL_IDLE: str = "台股類股"

#: 既有 🌍 市場環境 ›「🗺️ 產業熱力圖」那支 `render_sector_heatmap()` 寫死的
#: 五個 key。**本頁一個都不准用**（理由見檔頭；守衛在
#: `tests/test_p02_find_view.py::TestHeatmapKeysNeverCollideWithTheOldTab`）。
#: ⚠️ 放在這裡是**為了讓守衛有一份可比對的名單**，本頁的程式碼一行都不會讀它。
LEGACY_HEATMAP_KEYS: tuple[str, ...] = (
    "heatmap_market", "heatmap_period", "heatmap_refresh",
    "heatmap_load", "heatmap_loaded",
)

# ── 上游（既有分頁）寫進 session 的 UI 狀態 key ─────────────────────
#: ETF 組合按「計算組合」後寫入的持股列。
#: L3 `sector_flow_service` 的 docstring 明文：「**L5 只負責從 session_state 取
#: ETF 組合的 ticker + 個股 sheet_id 傳入**（session_state 是 UI 專屬，
#: 只能在 L5 讀）」—— 也就是讀這兩個 key 是 L3 契約**指派給 L5** 的工作，
#: 不是本檔自己多開的取數路徑。字面與 `src/ui/tabs/tab_sector_flow.py` 一致。
SS_ETF_PORTFOLIO_ROWS: str = "etf_portfolio_rows"
#: 個股組合 Google Sheet 的 sheet_id（同上）。
SS_STOCK_SHEET_ID: str = "stock_portfolio_sheet_id"

# ══════════════════════════════════════════════════════════════════
# 按鈕與葉的顯示名
# ══════════════════════════════════════════════════════════════════
#: ⚠️ **交接事項（本批未做，因為不得改共用層）**：`shared/ia_nav.py` 目前
#: **沒有**第 2 頁的 `ACTION_*` 與 `LEAF_*` 登錄（實測：`ACTION_LABELS` 只有
#: `update_today` 一項；`SECTION_LABELS` 只有 today 的兩葉 ＋ why / hold 各一）。
#: ia_nav 存在的理由正是「按鈕改名時，指路句要跟著改」——
#: 本檔的折衷是**在本檔內只定義一次**，按鈕與指路句**都讀同一個常數**，
#: 讓改名的失效模式在本頁內不成立；但**跨頁**仍缺一份 SSOT。
#: → 應在 `shared/ia_nav.py` 補 `ACTION_RUN_SCREEN` / `ACTION_LOAD_SECTOR_MAP`
#:   與 `LEAF_FIND_SCREEN` / `LEAF_FIND_SECTOR_MAP`，本檔改為讀它。
ACTION_RUN_SCREEN_LABEL: str = "🎯 開始選股"
ACTION_LOAD_MAP_LABEL: str = "🗺️ 載入板塊地圖"

#: 葉名（線框 `PAGES[1].leaves` 逐字）。
LEAF_SCREEN_TITLE: str = "選股網"
LEAF_MAP_TITLE: str = "板塊地圖（＝產業熱力圖＋板塊資金潮汐）"

#: 指路句一律由這兩支組出來，**不手抄按鈕名**（做法比照 `ia_nav.where_to_press`）。
_OPEN, _CLOSE = "「", "」"


def press(label: str) -> str:
    """`'按「🎯 開始選股」'` —— 指路句的唯一組法。"""
    return f"按{_OPEN}{label}{_CLOSE}"


# ══════════════════════════════════════════════════════════════════
# 顯示筆數（線框葉1 ③「綜合評分 · top 50」）
# ══════════════════════════════════════════════════════════════════
#: 可選的顯示筆數。**這不是門檻，是版面參數**（一次看幾列），
#: 故不進 `shared/*_thresholds.py`；預設 50 直接出自線框 ③ 的 `cells` 原文。
#:
#: ⚠️ 只有**一個**筆數：它同時是 `get_ranked_picks(top_n=)` 與畫面列數。
#: 既有選股網走 `top_n=300` 再 `.head(50)`，那是**兩個數字**，
#: 一旦有人只改其中一個，畫面說的「前 50 名」就會與實際取的不一致。
#: 本頁只留一個 → 結構上不會漂移。（空頭濾網在排名**之後**才剔除，
#: 故實際列數可能少於它 —— 卡上顯示的是**實際列數**，不是這個數字。）
TOP_N_OPTIONS: tuple[int, ...] = (20, 50, 100)
DEFAULT_TOP_N: int = 50

#: 預設勾選的因子 key。**維持 `eps_high`，不改成 `pe_low`**（2026-09-07 FE-18
#: 接上估值後複查）。原本的理由是「`pe_low` 未接線，拿它當預設等於讓每個人
#: 都拿到一份悄悄少算一個因子的名單」；那個理由**已經不成立**，但仍不改，
#: 換成新的理由：`eps_high` 的資料來自存活池自己的 `eps` 欄，**零額外取數**，
#: 而 `pe_low` 每一次都要打 TWSE ＋ TPEX 兩支 OpenAPI。預設值應該是最便宜的
#: 那一個，不是清單上的第一個。
#: ⚠️ **這是有意識的保留，不是漏改** —— 舊註解的理由已在上面逐句改寫並註明。
DEFAULT_FACTOR_KEY: str = "eps_high"

#: 估值（本益比）因子的 key。**本批已接線**（見檔頭「新接上的一項」）。
#: ⚠️ **舊名 `UNWIRED_FACTOR_KEY` 已改名，這是有意識的改名不是漏刪**：
#: 接上之後那個名字本身就是假的，留著會讓下一個讀者以為它還沒接。
#: 語意從「未接線的那一個」改為「要靠外部 `pe_map` 才算得出來的那一個」。
#: ⚠️ 它與其他四個因子的差別**仍然存在**：另外四個的資料來自存活池自己的欄位
#: 或既有掃描，只有它需要**額外一輪 L3 取數**；那一輪失敗或回空時，
#: 本頁必須自己講（L3 的 note 看不見這一種，見檔頭）。
PE_FACTOR_KEY: str = "pe_low"

# ══════════════════════════════════════════════════════════════════
# 文案常數（一句話只准寫一次 —— 手抄多份，改的時候一定會漏改）
# ══════════════════════════════════════════════════════════════════
#: 例外的**出處**。做法沿用頁 1：不共用 `tab_today.upstream_error_why()`，
#: 因為那支的文案寫死「讀 **L3 canonical 契約**時拋出例外」，
#: 拿它去包別的層等於**對使用者謊報出事的層**。
#: ⚠️ 洗掉狀態 glyph 那一步**仍然走對面的 SSOT** `scrub_state_glyphs()`，
#: 這裡換掉的只有出處那一句話（不是第二把尺）。
SRC_SCREEN: str = "L3 選股編排（`services.fundamental_screener_service.get_ranked_picks`）"
SRC_SURVIVORS: str = (
    "L3 基本面存活池（`services.fundamental_screener_service.get_fundamental_survivors`）")
SRC_SECTOR_FLOW: str = "L3 板塊資金（`services.sector_flow_service.get_sector_flow_view`）"
SRC_RENDER: str = "本頁的渲染層（`views/_ui_kit.render_card`）"

#: 熱力圖的**出處**（`_error_why()` 用）。本批新增的那一支 L3。
SRC_HEATMAP: str = "L3 產業熱力圖（`services.sector_heatmap_service.get_sector_heatmap_view`）"

#: 熱力圖 idle 態（線框葉2 grey 的**熱力圖那半句**逐字：
#: 「熱力圖要批次抓數十檔類股代表」）。與泡泡圖的 idle 理由**分開寫** ——
#: 兩張圖沒有載入的原因根本不同（一個要批次冷抓、一個只是讀盤後快照），
#: 合成一句會讓使用者以為按下去的代價是一樣的。
HEATMAP_IDLE_NOW: str = "**板塊資料尚未載入**"
HEATMAP_IDLE_WHY: str = (
    "熱力圖要**批次抓數十檔**類股代表與子成分的日線收盤（首次較久，"
    "之後 30 分鐘內走快取）；在你按下去之前，本頁**一次取數都不會發**"
)
HEATMAP_IDLE_WHERE: str = press(ACTION_LOAD_MAP_LABEL)

#: 批次抓取**全數失敗** → 紅態（線框葉2 `err` 原文：
#: 「🔴 熱力圖無法取得任何類股資料 / 批次抓取全數失敗」）。
#: ⚠️ **這一種刻意是紅的，不是灰的**：使用者已經按過按鈕、上游一檔都沒回來
#: ＝ 真故障，不是「還沒載入」。把它畫成灰的會讓真正的斷線被讀成「我還沒按」。
HEATMAP_FAILED_NOW: str = "**熱力圖無法取得任何類股資料**"
HEATMAP_FAILED_WHY: str = (
    "批次抓取全數失敗 —— 送出去的每一檔都沒有回來（yfinance 批次下載回空，"
    "或整批被限速／擋掉）。**畫面上不會出現任何一格**，"
    "本頁也**不會**拿 0% 把格子填滿冒充「全部持平」"
)
HEATMAP_FAILED_WHERE: str = (
    "先確認網路／NAS proxy；細節在"
    f"{ia_nav.where_to_find(ia_nav.SECTION_WHY_DATA_HEALTH)}。"
    f"稍後重新{press(ACTION_LOAD_MAP_LABEL)}可再試一次"
)

#: 部分覆蓋 → degraded（橘）。缺的格子在圖上**留白**，不填 0。
HEATMAP_DEGRADED_NOW: str = "**有幾格沒有資料，圖照畫但缺格是留白的**"
HEATMAP_DEGRADED_WHERE: str = (
    "常見原因是 yfinance 限速、該市場休市、標的停牌或已下市、"
    f"或上市未滿回看天數；稍後重新{press(ACTION_LOAD_MAP_LABEL)}多半會補齊。"
    "**缺格不會被填 0**，所以你看到的顏色都是真的有抓到的"
)

#: 「要換市場／區間去哪裡」——本頁沒有下拉（線框沒畫），據實指路。
#: ⚠️ 分頁名是 **🌍 市場環境 › 🗺️ 產業熱力圖**，不是 🏦 ETF 分頁
#: （舊登記把它寫成 ETF 分頁，那是錯的，見檔頭更正）。
HEATMAP_SWITCH_HINT: str = (
    "本頁固定畫這一組；要切換市場或區間，"
    "到 🌍 市場環境 ›「🗺️ 產業熱力圖」（兩邊並存期間各自獨立，互不影響）")

#: 估值取數的**出處**（`_error_why()` 用）。本批新增的那一支 L3。
SRC_PE: str = "L3 估值輸入（`services.valuation_service.get_pe_name_maps`）"

#: 估值因子**這一輪沒有資料**時的「去哪補」。
#: ⚠️ **與未接線那一種不同，這一種是有出口的** —— 東西已經接上了，
#: 拿不到是這一輪的事（上游掛了 / 兩個市場都沒給），重按有機會好。
#: 前一批的 `PE_UNWIRED_WHERE` 用 `NO_EXIT_MARKER`（「沒有使用者出口」）
#: 是對的，因為那時候按幾次都不會變；**接上之後照抄那句話就會變成說謊**。
PE_MISSING_WHERE: str = (
    f"{press(ACTION_RUN_SCREEN_LABEL)}重跑一次；"
    "TWSE / TPEX 的 OpenAPI 偶發不通時本頁會拿到空的對照表。"
    "若持續如此，到"
    f"{ia_nav.where_to_find(ia_nav.SECTION_WHY_DATA_HEALTH)}"
    "看那兩支 OpenAPI 與 NAS proxy 是否可用；"
    "在拿到之前**這個因子不計入綜合分，也不會被當成 0 分**"
)

#: 估值因子取數**拋例外**時的「為什麼沒有」前綴。實際訊息由 `_error_why()` 接。
PE_FAILED_WHY_HEAD: str = "本輪估值輸入取不到 —— "

#: 估值因子取數**回空 map** 時的「為什麼沒有」。
#: ⚠️ 這一句**只有本頁講得出來**：`composite_rank_candidates` 的
#: 「因子實際覆蓋」有 `if _col_scores[_f]` 的前提，整個因子全空時不會印，
#: 而它的 `_missing` 只收缺貨與 RS。詳見檔頭。
PE_EMPTY_WHY: str = (
    "本輪拿到的本益比對照表是空的（上市 TWSE 與上櫃 TPEX 兩支 OpenAPI "
    "都沒有給資料）—— 於是**每一檔都沒有估值分**。"
    "這不是「這些股票都很貴」，是**沒有數字**；"
    "L3 會讓缺料的因子不計入平均，**不會**拿 0 分頂替"
)

#: 表單下方常駐的接線揭露（不隨狀態消失）。
WIRING_DISCLOSURE: str = (
    "**取數接線揭露**：估值（本益比）/ 缺貨動能 / 抗跌 RS / 跨季轉強 / EPS "
    "五個因子都走 L3 service，**已全部接線**；結果表的「名稱」欄與估值同一份"
    "來源（`valuation_service.get_pe_name_maps`），一起帶進來。"
    "⚠️ 估值是唯一需要**額外一輪取數**的因子（TWSE ＋ TPEX 兩支 OpenAPI）——"
    "那一輪失敗或回空時，本頁會在結果卡上明講，**不會靜默把它當 0 分**。"
)

#: 選股結果 idle 態（線框葉1 ② grey 三要素，glyph 已移除 ——
#: 狀態頻道會由 `state_meta()` 出一次，文案不得自己再帶一個）。
SCREEN_IDLE_NOW: str = "**尚未選股**"
SCREEN_IDLE_WHY: str = (
    "選股要跑缺貨掃描與 RS 分位，首次約需數十秒；"
    "在你送出之前，本頁**一次 L3 取數都不會發**（沒有人叫過它）"
)
SCREEN_IDLE_WHERE: str = f"勾好條件後，{press(ACTION_RUN_SCREEN_LABEL)}（在表單裡）"

#: 選股跑完但 0 檔 —— **這是一個有效的結果**，不是故障、也不是還沒跑。
SCREEN_EMPTY_NOW: str = "**選股已完成，符合條件的標的是 0 檔**"

#: 板塊地圖 idle 態（線框葉2 grey 三要素）。
MAP_IDLE_NOW: str = "**板塊資料尚未載入**"
MAP_IDLE_WHY: str = (
    "泡泡圖讀每交易日盤後凍結的快照（不需重抓），"
    "但讀快照與比對你的持股板塊仍是一次真實的 I/O，故不在頁面載入時就跑"
)
MAP_IDLE_WHERE: str = press(ACTION_LOAD_MAP_LABEL)

#: 板塊資金泡泡圖的口徑揭露（線框葉2 ④，**常駐 caption，不隨狀態消失**）。
#: 三個視窗長度一律讀 L0 `shared/sector_flow_thresholds`，不手抄數字。
SECTOR_FLOW_AXIS_NOTE: str = (
    f"口徑：X＝近 {WINDOW_X} 交易日累計淨流入（億）"
    f"· Y＝動能變化（近 {WINDOW_Y_RECENT} 日均 − 前 {WINDOW_Y_PRIOR} 日均，億/天）"
    f"· 泡泡＝近 {WINDOW_SIZE} 交易日淨額規模（億）。"
    "**面積不等於權重。**　"
    f"交易日不足 {WINDOW_Y_MIN_DAYS} 天的板塊**不硬塞象限位置**，另行列名。"
)

#: 「這一格的狀態不會因為再按一次而改變」的統一說法（未接線專用）。
UNKNOWN_ERROR_TEXT: str = "（上游沒有給訊息）"


def _error_why(source: str, error: Any) -> str:
    """把上游例外轉成一句可以放進 `Note.why` 的話，**出處講對**。

    洗 glyph 一律走 `tab_today.scrub_state_glyphs()`（SSOT，唯一入口）——
    `Note.__post_init__` 拒收狀態 glyph，不洗就會把一張**該畫出來的紅卡**
    變成**整頁未捕捉例外**（§1：紅態要看得見，不是換一種炸法）。
    """
    _clean, _n = scrub_state_glyphs(error)
    _why = f"{source}拋出例外：{_clean or UNKNOWN_ERROR_TEXT}"
    if _n:
        _why += ("（上游訊息裡的狀態符號已移除，"
                 "以免和這張卡自己的狀態燈混成兩個互相矛盾的說法）")
    return _why


# ══════════════════════════════════════════════════════════════════
# 純資料層（零 streamlit；render 端把 session 讀出來再傳進來）
# ══════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class ScreenRequest:
    """使用者**已送出**的那一組條件。`submitted` 是本頁第 1 個 gate 旗標。

    Attributes:
        submitted: `SS_APPLIED_SCREEN` 這個 key 存不存在。
            **只有 submit handler 會寫它** —— 這是「有沒有人叫過」的事實，
            不是從結果資料反推的（L0 `shared/ui_state.py` 的鐵律）。
        factors: 已套用的因子 key（`SCREEN_ANGLE_LABELS` 的值）。
        top_n: 已套用的顯示筆數。
    """

    submitted: bool
    factors: tuple[str, ...] = ()
    top_n: int = DEFAULT_TOP_N


def applied_screen_request(session: Mapping[str, Any]) -> ScreenRequest:
    """讀**已套用值**（鐵律 2）。widget 當下值一律不讀。

    邊界：key 不存在 → `submitted=False`（冷啟動）。
    key 存在但形狀怪（被別人覆寫、或舊版殘留）→ 仍算「送出過」，
    但因子退回空 tuple、筆數退回預設 —— **不猜使用者的意思**，
    L3 會回「請至少勾選一個選股因子」，由它說話（§2.1 SSOT）。
    """
    if SS_APPLIED_SCREEN not in session:
        return ScreenRequest(submitted=False)
    _applied = session.get(SS_APPLIED_SCREEN)
    if not isinstance(_applied, Mapping):
        return ScreenRequest(submitted=True)
    _factors = tuple(str(_f) for _f in (_applied.get("factors") or ()))
    try:
        _top_n = int(_applied.get("top_n", DEFAULT_TOP_N))
    except (TypeError, ValueError):
        _top_n = DEFAULT_TOP_N
    return ScreenRequest(submitted=True, factors=_factors,
                         top_n=_top_n if _top_n > 0 else DEFAULT_TOP_N)


def map_requested(session: Mapping[str, Any]) -> bool:
    """板塊地圖的 gate 旗標（本頁第 2 個）。**只看按鈕 handler 寫的那個 key。**"""
    return bool(session.get(SS_MAP_REQUESTED))


@dataclass(frozen=True)
class ScreenResult:
    """一次選股的全部產出。**不含任何本檔自算的排名結論。**

    Attributes:
        requested: 由 `ScreenRequest.submitted` 帶下來，**不是**從 `df` 反推。
        df: L3 `get_ranked_picks()` 回的 DataFrame（可能是空表）；未請求 → None。
        note: L3 自己寫的 note（缺貨/RS 未掃、涵蓋門檻、空頭濾網是否套用…）。
            **原樣透傳，本檔不改寫、不摘要**（§2.1：那是 L3 的話）。
        rows: `df` 的實際列數；`None` = 這一輪沒有算過（≠ 0 檔）。
        survivors_n: 存活池檔數；`None` = 取不到（**不寫 0**，§1 不假報）。
        pe_n: 這一輪拿到幾檔的本益比。`None` = **取不到**（L3 拋例外）；
            `0` = **拿到了、但兩個市場都沒給資料**。
            ⚠️ 兩者**必須分開**：前者重按有機會好、後者是上游今天真的沒有東西，
            而且對 `get_ranked_picks` 的行為完全相同（都不計入）——
            分不開就只能講一句含糊的話，那正是 §1 要防的。
        name_n: 這一輪拿到幾檔的中文名（與 `pe_n` 同一份來源、同一次取數）。
            `None` 的語意同上。**它不是估值因子的一部分** ——
            名稱欄跟勾不勾估值無關，所以兩個數字分開放。
        hits: `summarize_factor_hits()` 的片語（掃失敗的因子不產生片語）。
        error: 排名本身拋出的例外 `repr(e)`；空字串 = 沒有錯誤。
        aux_errors: 週邊取數（存活池 / 三個掃描 / 總經）的失敗訊息。
            **它們不讓整張卡轉紅** —— 一個因子掛掉不等於選股掛掉，
            L3 會讓該因子「缺料不計入」；但**必須看得見**，故上卡片的 facts。
    """

    requested: bool
    df: Any = None
    note: str = ""
    rows: int | None = None
    survivors_n: int | None = None
    pe_n: int | None = None
    name_n: int | None = None
    hits: tuple[str, ...] = ()
    error: str = ""
    aux_errors: tuple[tuple[str, str], ...] = ()

    @property
    def has_rows(self) -> bool:
        """這一輪有沒有選出東西。**只在 `requested=True` 時有意義。**"""
        return bool(self.rows)


def _map_len(m: Mapping | None) -> int | None:
    """對照表 → 檔數。`None`（取不到）**維持 `None`**，不塌成 0。

    §1：`None` 與 `{}` 對 `get_ranked_picks` 的行為相同（都不計入），
    但對使用者是兩句不同的話 —— 「取不到」vs「上游今天沒有」。
    在這裡塌成 0 就再也分不出來了。
    """
    return None if m is None else len(m)


def _frame_rows(df: Any) -> int | None:
    """DataFrame → 列數。非 DataFrame / 讀不出來 → `None`（不猜 0）。"""
    if df is None:
        return None
    try:
        return int(len(df))
    except (TypeError, ValueError):     # noqa: PERF203 — 形狀不對就是 unknown
        return None


def _load_survivors() -> tuple[Any, int | None, str]:
    """L3 存活池 → `(df, 檔數, 錯誤字串)`。失敗 → `(None, None, repr(e))`。

    §1：失敗時檔數回 `None` 而**不是 0** —— 「取不到」與「池子是空的」
    是兩件事，卡上會分別顯示「—」與「0 檔」。
    """
    try:
        from src.services.fundamental_screener_service import (
            get_fundamental_survivors,
        )
        _df, _ = get_fundamental_survivors()
        return _df, _frame_rows(_df), ""
    except Exception as _e:  # noqa: BLE001 — 轉成看得見的 facts 列，不吞
        print(f"[views/page_find] 存活池不可用：{_e!r}")
        return None, None, repr(_e)


def _load_shortage(factors: Sequence[str]) -> tuple[list | None, str]:
    """勾了「缺貨動能」才掃。**沒勾 → 回 `None`**（不是 `[]`）。

    ⚠️ `None` 與 `[]` 的差別是 `summarize_factor_hits()` 契約的一部分：
    `None` = 沒掃 / 掃失敗 → **不產生片語**；`[]` = 掃了但零結果 → 印 `0/0`。
    §1：掃失敗不假報 0。
    """
    if "shortage" not in factors:
        return None, ""
    try:
        from src.services.shortage_screener_service import run_shortage_scan
        _rows, _ = run_shortage_scan()
        return _rows, ""
    except Exception as _e:  # noqa: BLE001 — 該因子缺料，不炸整體
        print(f"[views/page_find] 缺貨掃描失敗：{_e!r}")
        return None, repr(_e)


def _load_rs(factors: Sequence[str]) -> tuple[list | None, str]:
    """勾了「抗跌 RS」才掃。`None` / `[]` 的差別同 `_load_shortage`。

    ⚠️ `beat_only=False` ＋ `top_n=RS_SCAN_MAX` 是**綜合評分需要全存活池分位**
    的既定作法（`get_ranked_picks` 的 `auto_fetch=True` 分支用的就是這組參數）。
    改成 `beat_only=True` 會讓落後股從 `rs_map` 消失 → 對它們而言 RS 變成
    「缺料」→ 依規則**不計入**平均 → 綜合分反而**上升**（幫落後股加分），
    與意圖完全相反（`_apply_bear_market_filter` 的 docstring 明文警告）。
    """
    if "rs_leader" not in factors:
        return None, ""
    try:
        from shared.rs_screen_thresholds import RS_SCAN_MAX
        from src.services.rs_leader_service import run_rs_leader_scan
        _rows, _ = run_rs_leader_scan(beat_only=False, top_n=RS_SCAN_MAX)
        return _rows, ""
    except Exception as _e:  # noqa: BLE001 — 該因子缺料，不炸整體
        print(f"[views/page_find] 抗跌 RS 掃描失敗：{_e!r}")
        return None, repr(_e)


def _load_trend(factors: Sequence[str]) -> tuple[dict | None, str]:
    """勾了「跨季轉強」才算（從季快照算，非掃描）。`None` = 沒算 / 失敗。"""
    if "trend" not in factors:
        return None, ""
    try:
        from src.services.fundamental_screener_service import build_trend_map
        return build_trend_map(), ""
    except Exception as _e:  # noqa: BLE001 — 該因子缺料，不炸整體
        print(f"[views/page_find] 跨季趨勢計算失敗：{_e!r}")
        return None, repr(_e)


def _load_regime() -> tuple[str | None, str]:
    """canonical 總經位階字串 → 傳給 L3 當空頭濾網的輸入。

    ⚠️ `get_macro_regime()` 回的是**契約 dict**（regime / light / is_loaded…），
    不是字串。既有選股網踩過這個坑：整包 dict 傳下去，到
    `_apply_bear_market_filter` 的 `regime not in frozenset` 直接 TypeError
    （dict unhashable）→ 一按選股就炸。

    §1：總經**未評估**時回 `None`（＝不套用濾網），**不捏造多空**；
    L3 會在它自己的 note 裡明講「未套用」，那句話由它說，本檔不代言。
    """
    try:
        from src.services.allocation_service import get_macro_regime
        _state = get_macro_regime()
        if isinstance(_state, Mapping) and _state.get("is_loaded"):
            _regime = _state.get("regime")
            return (str(_regime) if _regime else None), ""
        return None, ""
    except Exception as _e:  # noqa: BLE001 — 總經取不到不該炸掉選股
        print(f"[views/page_find] 總經位階取得失敗，不套用空頭濾網：{_e!r}")
        return None, repr(_e)


def _load_pe_name_maps() -> tuple[dict | None, dict | None, str]:
    """L3 估值輸入 → `(pe_map, name_map, 錯誤字串)`。失敗 → `(None, None, repr(e))`。

    **一律呼叫，不看勾了哪些因子**（與既有選股網 `app.py` 同行為）：
    `name_map` 撐的是結果表的「名稱」欄，那一欄跟勾不勾估值因子無關。
    兩份 map 是**同一支** L3 一次回來的，分開抓會變成兩輪取數。

    §1：失敗時回 `None` 而**不是** `{}` —— 「取不到」與「兩個市場都沒給」
    是兩件事，卡上會分別顯示「取不到」與「0 檔有本益比」。
    ⚠️ 而 `{}` 與 `None` 傳給 `get_ranked_picks(pe_map=)` 的**行為相同**
    （L3 內部 `pe_map or {}`）—— 差別只在**本頁怎麼跟使用者講**，
    這正是為什麼不能圖省事把兩者合成一個。
    """
    try:
        from src.services.valuation_service import get_pe_name_maps
        _pe, _name = get_pe_name_maps()
        return (dict(_pe or {}), dict(_name or {}), "")
    except Exception as _e:  # noqa: BLE001 — 該因子缺料，不炸整體
        print(f"[views/page_find] 估值／名稱對照表取不到：{_e!r}")
        return None, None, repr(_e)


def _summarize_hits(factors: Sequence[str], *, shortage_rows: list | None,
                    rs_rows: list | None,
                    trend_map: dict | None) -> tuple[tuple[str, ...], str]:
    """「本次因子」片語（線框葉1 選股結果 live 文案的後半段）。

    走 L5 純函式 `tab_stock_picker.summarize_factor_hits()` —— 那支的分子
    一律用既有 tier SSOT 邊界，**本檔不自己數 tier**（既有選股網踩過的坑：
    三個裸 `len()` 全被當成「命中數」印出去，實際上是分母）。
    """
    try:
        from src.ui.tabs.tab_stock_picker import summarize_factor_hits
        return tuple(summarize_factor_hits(
            factors, shortage_rows=shortage_rows, rs_rows=rs_rows,
            trend_map=trend_map)), ""
    except Exception as _e:  # noqa: BLE001 — 摘要不可用不該炸掉結果表
        print(f"[views/page_find] 因子命中摘要不可用：{_e!r}")
        return (), repr(_e)


def load_screen_result(req: ScreenRequest) -> ScreenResult:
    """跑一次選股。**`req.submitted` 為 False 時一行 L3 都不呼叫。**

    路徑（全部 L3，逐項見檔頭「取數」表）：
        存活池 / 估值·名稱 / 缺貨 / RS / 跨季 / 總經位階
        → `get_ranked_picks(auto_fetch=False)`

    ⚠️ **為什麼是 `auto_fetch=False`**：三個掃描由本函式**顯式**發（每支各自
    try/except），這樣 (a) 一支掛掉不連坐其他支、(b) 掃描結果拿得到，
    才能用 SSOT 的 `summarize_factor_hits()` 算「本次因子」的分子/分母。
    傳 `auto_fetch=True` 的話掃描結果留在 L3 裡拿不到，畫面就只能自己再數一次
    ＝ 第二把尺。

    ⚠️ **`pe_map` / `name_map` 由本函式**顯式**注入**（2026-09-07 FE-18 接線；
    做法與既有選股網 `app.py` 相同 —— 那四個 orchestrator 共用同一份 map 是
    `get_ranked_picks` docstring 明文要求的 §2.1 SSOT）。
    取不到時傳 `None`，而 `None` 與 `{}` 對 L3 的**行為相同**（內部 `or {}`）
    ⇒ 該因子缺料不計入。**差別在畫面怎麼講**：本函式把「取不到」與
    「拿到 0 檔」分成兩種 `aux_errors` 訊息，因為 L3 的 note **兩種都不會提**
    （`_missing` 只收缺貨與 RS；「因子實際覆蓋」那句有 `if _col_scores[_f]`
    的前提，整個因子全空時不印）。

    邊界（四個都真的走得到）：
      (a) **冷啟動 / 還沒送出** → `ScreenResult(requested=False)`，
          全部格子 `idle`（**還沒有人叫**），不是 `empty`（叫了但沒值）。
      (b) **L3 在呼叫期拋例外**（含 late import 失敗）→ `repr(e)` 帶回 →
          結果卡轉**紅態**並把訊息印在畫面上。**不是 `except: pass`**。
      (c) **回空表 / `None` / 0 筆** → `rows` 分別是 `0` / `None` / `0`，
          `has_rows` 為 False → `empty`（灰）。**不是綠燈、也不是紅燈。**
      (d) **估值那一輪失敗或回空** → 排名照跑（少一個因子不等於選不出東西），
          但 `pe_n` 帶回 `None` / `0`，卡上明講。**不讓整張卡轉紅。**
    """
    if not req.submitted:
        return ScreenResult(requested=False)

    _factors = list(req.factors)
    _aux: list[tuple[str, str]] = []

    _surv_df, _surv_n, _surv_err = _load_survivors()
    if _surv_err:
        _aux.append(("存活池", _error_why(SRC_SURVIVORS, _surv_err)))
    _pe_map, _name_map, _pe_err = _load_pe_name_maps()
    if _pe_err:
        _aux.append(("估值（本益比）",
                     f"{PE_FAILED_WHY_HEAD}{_error_why(SRC_PE, _pe_err)}"
                     "；該因子不計入綜合分，「名稱」欄也會是空的"))
    elif not _pe_map:
        _aux.append(("估值（本益比）", PE_EMPTY_WHY))
    _short_rows, _short_err = _load_shortage(_factors)
    if _short_err:
        _aux.append(("缺貨掃描", f"失敗，該因子不計入綜合分：{_short_err}"))
    _rs_rows, _rs_err = _load_rs(_factors)
    if _rs_err:
        _aux.append(("抗跌 RS 掃描", f"失敗，該因子不計入綜合分：{_rs_err}"))
    _trend_map, _trend_err = _load_trend(_factors)
    if _trend_err:
        _aux.append(("跨季轉強", f"失敗，該因子不計入綜合分：{_trend_err}"))
    _regime, _regime_err = _load_regime()
    if _regime_err:
        _aux.append(("總經位階", f"取不到，空頭濾網未套用：{_regime_err}"))

    try:
        from src.services.fundamental_screener_service import get_ranked_picks
        _df, _note = get_ranked_picks(
            _factors,
            top_n=req.top_n,
            survivors_df=_surv_df,
            # 本批接線點。取不到 → `None`（與 `{}` 對 L3 行為相同，
            # 差別在畫面怎麼講 —— 見本函式 docstring）。
            pe_map=_pe_map,
            name_map=_name_map,
            shortage_rows=_short_rows,
            rs_rows=_rs_rows,
            trend_map=_trend_map,
            auto_fetch=False,
            regime=_regime,
        )
    except Exception as _e:  # noqa: BLE001 — 轉成紅態顯示，不吞
        print(f"[views/page_find] 選股排名失敗 → 結果卡轉紅態：{_e!r}")
        return ScreenResult(requested=True, error=repr(_e),
                            survivors_n=_surv_n,
                            pe_n=_map_len(_pe_map), name_n=_map_len(_name_map),
                            aux_errors=tuple(_aux))

    _hits, _hits_err = _summarize_hits(
        _factors, shortage_rows=_short_rows, rs_rows=_rs_rows,
        trend_map=_trend_map)
    if _hits_err:
        _aux.append(("因子命中摘要", f"不可用：{_hits_err}"))

    return ScreenResult(
        requested=True, df=_df, note=str(_note or ""),
        rows=_frame_rows(_df), survivors_n=_surv_n,
        pe_n=_map_len(_pe_map), name_n=_map_len(_name_map),
        hits=_hits, aux_errors=tuple(_aux))


# ══════════════════════════════════════════════════════════════════
# 葉2：板塊資金泡泡（L3 → L4 純繪圖）
# ══════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class SectorFlowReadout:
    """L3 `get_sector_flow_view()` 的回傳，攤成本頁要用的欄位。

    ⚠️ `ok=False` **不是故障** —— 它是 reader 的 sentinel，語意是
    「盤後凍結任務還沒產生快取」。那是 `empty`（灰）不是 `failed`（紅）；
    把它畫成紅色就是 v3 §02 前半句要杜絕的**假性錯誤**。
    """

    requested: bool
    ok: bool = False
    stale: bool = False
    sectors: tuple = ()
    highlight: tuple[str, ...] = ()
    insufficient: tuple[str, ...] = ()
    quadrant_counts: tuple[tuple[str, int], ...] = ()
    reason: str = ""
    updated_at: str = ""
    meta_updated_at: str = ""
    stale_reason: str = ""
    n_days: str = ""
    error: str = ""


def _etf_tickers(session: Mapping[str, Any]) -> list[str]:
    """ETF 組合持股的 ticker（讀 **UI 狀態**，不是抓資料）。

    L3 `sector_flow_service` 的 docstring 指派給 L5 的工作就是這一件；
    ticker 常帶 `.TW` / `.TWO` 後綴，正規化由 L3 負責（本檔不去尾碼，
    那會變成第二處正規化規則）。
    """
    _rows = session.get(SS_ETF_PORTFOLIO_ROWS) or []
    if not isinstance(_rows, list):
        return []
    return [str(_r.get("ticker")).strip() for _r in _rows
            if isinstance(_r, Mapping) and _r.get("ticker")]


def _quadrant_counts(sectors: Iterable[Mapping[str, Any]]
                     ) -> tuple[tuple[str, int], ...]:
    """象限 → 這一份快照裡有幾個板塊。**象限名一律讀資料本身，不手抄。**

    刻意**不**在本檔寫一份「漲潮 = X≥0 且 Y≥0」的對照表：那個定義住在 L0
    `shared/sector_flow_thresholds`（象限判定也在後端做完了），
    抄一份到 UI 就是第二個 SSOT，而且它會在門檻改動時無聲漂移。
    圖例改為顯示**這一輪實際落在各象限的板塊數**，零轉抄。
    """
    _counts: dict[str, int] = {}
    for _s in sectors or ():
        if not isinstance(_s, Mapping):
            continue
        _q = str(_s.get("quadrant") or "").strip()
        if _q:
            _counts[_q] = _counts.get(_q, 0) + 1
    return tuple(sorted(_counts.items(), key=lambda kv: (-kv[1], kv[0])))


def load_sector_flow(session: Mapping[str, Any], *,
                     requested: bool) -> SectorFlowReadout:
    """L3 板塊資金 view → 本頁要用的欄位。**未請求 → 一行 L3 都不呼叫。**

    邊界：
      (a) **未按載入鈕** → `requested=False`（idle，還沒有人叫）。
      (b) **L3 拋例外**（含 late import 失敗）→ `repr(e)` → 紅態。
      (c) **`ok=False`**（快取還沒產生）→ **灰態 `empty`**，理由用 L3 給的
          `reason` 原文。**不是紅態** —— 沒有人壞掉，只是東西還沒生出來。
      (d) **`is_stale`** → **`degraded`**（有值、可讀，但它是上一次凍結的快照）。
          沿用本 IA 既有判例：`tab_today.classify_macro_contract()` 對
          「AI 鎖定快照」也是走 `discriminative=False`（線框 N4 的第 3 條來源）。
    """
    if not requested:
        return SectorFlowReadout(requested=False)
    try:
        from src.services.sector_flow_service import get_sector_flow_view
        _view = get_sector_flow_view(
            etf_tickers=_etf_tickers(session),
            stock_sheet_id=(str(session.get(SS_STOCK_SHEET_ID) or "").strip()
                            or None),
        )
    except Exception as _e:  # noqa: BLE001 — 轉成紅態顯示，不吞
        print(f"[views/page_find] 板塊資金取數失敗 → 轉紅態：{_e!r}")
        return SectorFlowReadout(requested=True, error=repr(_e))

    _view = _view if isinstance(_view, Mapping) else {}
    if not _view.get("ok"):
        return SectorFlowReadout(
            requested=True, ok=False,
            reason=str(_view.get("reason") or "").strip())

    _sectors = tuple(_view.get("sectors") or ())
    _insuf = tuple(str(_s.get("sector")) for _s in _sectors
                   if isinstance(_s, Mapping) and _s.get("insufficient"))
    return SectorFlowReadout(
        requested=True, ok=True,
        stale=bool(_view.get("is_stale")),
        sectors=_sectors,
        highlight=tuple(sorted(str(_h) for _h in
                               (_view.get("highlight_sectors") or ()))),
        insufficient=_insuf,
        quadrant_counts=_quadrant_counts(_sectors),
        updated_at=str(_view.get("updated_at") or ""),
        meta_updated_at=str(_view.get("meta_updated_at") or ""),
        stale_reason=str(_view.get("stale_reason") or ""),
        n_days=str(_view.get("n_trading_days_used") or ""),
    )


@dataclass(frozen=True)
class HeatmapReadout:
    """L3 `get_sector_heatmap_view()` 的回傳，攤成本頁要用的欄位。

    Attributes:
        requested: 由「🗺️ 載入板塊地圖」那顆按鈕的 gate 旗標帶下來
            （**與泡泡圖同一顆**，線框 N6：舊分頁那顆 gate 被本頁這顆吸收）。
            **不是**從 `returns` 反推 —— 那分不出「還沒按」與「按了全數失敗」。
        figure: L4 組好的 treemap（`go.Figure`）。`None` = 這一輪沒有圖可畫。
        sectors_n / fetched_n: 母層類股共幾個 / 這一輪抓到幾個。
        sub_fetched_n / sub_total_n: 子成分同上。
        complete: 母層＋子成分**全部**抓到。缺一個就是 False。
        any_data: 這一輪**有沒有抓到任何一檔**。
            ⚠️ `False` 是**紅態**（線框葉2 `err`），不是灰的 empty ——
            使用者已經按過、上游一檔都沒回來，那是真故障。
        market_label / period_label / n_bars: 口徑揭露用（畫面要講清楚
            「1日」是 1 個**交易日**，不是 1 個日曆日）。
        single_stock_proxy / disclosure: 台股側「每個類股其實是一檔代表股」
            的揭露開關與原文（L0 SSOT，本頁**原樣印出、不改寫**）。
        error: 取數或組圖拋出的例外 `repr(e)`；空字串 = 沒有錯誤。
    """

    requested: bool
    figure: Any = None
    sectors_n: int = 0
    fetched_n: int = 0
    sub_fetched_n: int = 0
    sub_total_n: int = 0
    complete: bool = False
    any_data: bool = False
    market_label: str = ""
    period_label: str = ""
    n_bars: int = 0
    single_stock_proxy: bool = False
    disclosure: str = ""
    error: str = ""


def load_heatmap(*, requested: bool) -> HeatmapReadout:
    """L3 產業熱力圖 view → 本頁要用的欄位。**未請求 → 一行 L3 都不呼叫。**

    邊界（四種，各自一態）：
      (a) **未按載入鈕** → `requested=False`（idle。**整批冷抓不會發**）。
      (b) **L3 / L4 拋例外**（含 late import 失敗、區間標籤打錯）→ `repr(e)` → 紅態。
      (c) **一檔都沒抓到** → `any_data=False` → **紅態**（線框葉2 `err` 原文）。
          ⚠️ 這一種**不是** `empty`：泡泡圖的 `ok=False` 是「盤後任務還沒產生
          快取」（沒有人壞掉，灰），而這裡是「送出去了、一檔都沒回來」（真故障）。
          **兩者長得像、語意相反，不可以共用一態。**
      (d) **只抓到一部分** → `degraded`（橘）。圖照畫，缺格留白，**不填 0**。

    ⚠️ **組圖也包在同一個 `try` 裡**：treemap 組裝若炸掉（例如上游回了奇形怪狀
    的 dict），裸寫會讓整張葉子從這一行以下全部消失（半截死頁），
    而使用者連一句解釋都看不到。轉成一張紅卡，泡泡圖那半照畫。
    """
    if not requested:
        return HeatmapReadout(requested=False)
    try:
        from src.services.sector_heatmap_service import get_sector_heatmap_view
        _view = get_sector_heatmap_view(HEATMAP_IS_US, HEATMAP_PERIOD_LABEL)
        _view = _view if isinstance(_view, Mapping) else {}
        _returns = dict(_view.get("returns") or {})
        _sectors = dict(_view.get("sectors") or {})
        _cov = _view.get("coverage")
        _fig = None
        if _returns:
            from src.ui.render.sector_heatmap_render import build_sector_treemap
            _fig = build_sector_treemap(
                _sectors, _returns, str(_view.get("market_label") or ""),
                single_stock_proxy=bool(_view.get("single_stock_proxy")),
                period_label=str(_view.get("period_label") or ""))
    except Exception as _e:  # noqa: BLE001 — 轉成紅態顯示，不吞
        print(f"[views/page_find] 產業熱力圖取數／組圖失敗 → 轉紅態：{_e!r}")
        return HeatmapReadout(requested=True, error=repr(_e))

    return HeatmapReadout(
        requested=True,
        figure=_fig,
        sectors_n=getattr(_cov, "parent_total", len(_sectors)),
        fetched_n=getattr(_cov, "parent_fetched", 0),
        sub_fetched_n=getattr(_cov, "sub_fetched", 0),
        sub_total_n=getattr(_cov, "sub_total", 0),
        complete=bool(getattr(_cov, "complete", False)),
        any_data=bool(_returns),
        market_label=str(_view.get("market_label") or ""),
        period_label=str(_view.get("period_label") or ""),
        n_bars=int(_view.get("n_bars") or 0),
        single_stock_proxy=bool(_view.get("single_stock_proxy")),
        disclosure=str(_view.get("disclosure") or ""),
    )


# ══════════════════════════════════════════════════════════════════
# 卡片建構（純函式；`Card` / `Note` 的驗證在對面，本檔不重複）
# ══════════════════════════════════════════════════════════════════
def _fmt_count(n: int | None) -> str:
    """檔數 → 顯示字串。`None` = 取不到 → `'—'`，**不寫 0**（§1 不假報）。"""
    return "—" if n is None else f"{n}"


def _pe_broken(result: ScreenResult) -> bool:
    """這一輪的估值輸入**有沒有出事**（取不到，或拿到 0 檔）。

    ⚠️ 兩者合成一個布林**只用在「要不要另外畫一則說明」這個問題上** ——
    「是哪一種」仍然分開：理由句由 `load_screen_result` 依 `pe_err` /
    `not _pe_map` 分成兩段不同的文字放進 `aux_errors`，數字由 `pe_n` 的
    `None` / `0` 分辨。這裡只是問「畫不畫」，不是把兩件事講成一件。
    """
    return not result.pe_n


def _name_col_fact(result: ScreenResult) -> str:
    """結果表「名稱」欄這一列的說明。**四種情形四句話。**

    ⚠️ **「還沒送出」必須與「送出了但取不到」分開**（自審實測後補）：
    冷啟動時 `name_n` 也是 `None`，但那是因為**這一輪根本沒有發過取數**。
    對它說「這一輪取不到名稱對照表」＝ **替一輪沒發生的取數宣稱它的結果**，
    與把「還沒載入」畫成紅色是同一族的說謊（`CLAUDE.md §1.A` 第 4 點）。
    """
    if not result.requested:
        return "送出後才會取（與本益比同一份來源、同一次取數）"
    if result.name_n is None:
        return ("這一輪取不到名稱對照表 → 欄位是空的"
                "（與本益比同一份來源、同一次取數，一起沒拿到）")
    if not result.name_n:
        return ("名稱對照表這一輪是空的 → 欄位是空的"
                "（上市 TWSE 與上櫃 TPEX 都沒給資料，不是本頁沒接）")
    return (f"{result.name_n} 檔有中文名（與本益比同一份來源、同一次取數）"
            "—— 不在對照表裡的個股仍會是空白，**不拿代號頂替**")


def build_screen_result_card(result: ScreenResult, req: ScreenRequest
                             ) -> tuple[Card, tuple[tuple[str, str], ...]]:
    """線框葉1「選股結果」的總覽卡 →（`Card`, `facts`）。

    ⚠️ **`requested=` 與 `has_value=` 刻意是兩個不同的來源**：
    前者是「使用者按過 submit」（session key 存在性），
    後者是「這一輪選出東西了沒有」（DataFrame 列數）。
    `tests/test_ui_state_model.py` 的 AST 守衛會比對兩者是否同源 ——
    但那條守衛只比字面，**它綠燈不代表這裡是對的**；真正的理由在上面兩句。

    ⚠️ **「0 檔」與「讀不出列數」不是同一件事**（自審實測後補）：
    `rows == 0` ＝ 跑完了、真的沒有符合的 → `empty`（灰，有效結果）；
    `rows is None` ＝ L3 回了一個**讀不出列數的東西**（既有實作恆回
    DataFrame，所以走到這裡代表回傳契約變了）→ 走 `MISS_CONTRACT_DRIFT`
    → L0 把它**升成紅態**。修前兩者都被畫成「0 檔」，等於**替上游宣稱
    一件它沒說的事**（§1：錯誤的數字比沒有數字更危險）。
    """
    # 請求過、沒例外、卻連列數都讀不出來 = 回傳契約漂移（重跑不會好，要改程式）。
    # 用 L0 `station_specs` 的語彙，讓 `FAILED_REASONS` 自己決定要不要升紅 ——
    # 本檔**不自己判「這算不算故障」**。
    _reason = (MISS_CONTRACT_DRIFT
               if (result.requested and not result.error
                   and result.rows is None)
               else "")
    _state = classify_ui_state(
        requested=result.requested,
        error=result.error or None,
        has_value=result.has_rows,
        reason=_reason,
    )

    # ── facts：任何狀態都該看得見「這一次的條件本來長什麼樣」──────────
    _facts: list[tuple[str, str]] = [
        ("本次條件", "、".join(req.factors) if req.factors else "（未勾選任何因子）"),
        ("顯示筆數", f"綜合評分排序前 {req.top_n} 名"),
        ("存活池", f"{_fmt_count(result.survivors_n)} 檔（四項全過）"),
    ]
    # 估值那一輪的實際結果。**勾了才講**（沒勾就講 = 假警報，`§1.A` 第 4 點）；
    # 而「名稱欄」跟勾不勾無關，所以永遠講一次。
    # ⚠️ `aux_errors` 已經帶了失敗／全空的長句（見 `load_screen_result`），
    #    這裡只補一句**數字**，不重複那段理由。
    if PE_FACTOR_KEY in req.factors and not _pe_broken(result):
        _facts.append((
            "估值（本益比）",
            f"{_fmt_count(result.pe_n)} 檔有本益比（走 L3 "
            "`valuation_service.get_pe_name_maps`；≤0 的不算，那是缺值不是估值）"))
    _facts.append(("名稱欄", _name_col_fact(result)))
    _facts.extend(result.aux_errors)
    if result.note:
        # L3 自己寫的 note（缺貨/RS 未掃、涵蓋門檻、空頭濾網是否套用…）。
        # **原樣透傳**：那是 L3 的話，本檔不改寫、不摘要（§2.1 SSOT）。
        _facts.append(("L3 說明", result.note))

    if _state == UI_LIVE:
        # 線框 live 原文的格式：`🔭 存活池 274 檔 → 綜合入選前 50 名`
        _value = (f"🔭 存活池 {_fmt_count(result.survivors_n)} 檔 "
                  f"→ 綜合入選 {result.rows} 檔")
        _note = None
        if PE_FACTOR_KEY in req.factors and _pe_broken(result):
            # live 也要畫 Note —— `render_card` 已改成「只要有 Note 就畫」。
            # 靜默丟棄「你勾的因子其實沒算」這種說明 ＝ §1 禁止的掩蓋問題。
            #
            # ⚠️ **接線之後這則 Note 只在真的出事時才畫**（2026-09-07 FE-18）。
            # 前一批它是無條件畫的，因為那時候 `pe_map` 恆為 `None`；接上之後
            # 照樣無條件畫就變成**假警告** —— 名單明明算了估值，卻對使用者說
            # 「這份名單少算了一個你勾的因子」。假警報與假數字是同一種說謊
            # （`CLAUDE.md §1.A` 第 4 點：滿版假紅字會讓真正的問題沒人看得見）。
            _note = Note(
                now="**這份名單少算了一個你勾的因子**（估值／本益比）",
                why=(PE_EMPTY_WHY if result.pe_n == 0
                     else "本輪估值輸入取不到（詳細訊息見上方「估值（本益比）」那一列）"
                          " —— 該因子沒有計入綜合分"),
                where=PE_MISSING_WHERE)
        return Card(key="find.screen_result", label="選股結果",
                    state=UI_LIVE, value=_value, note=_note), tuple(_facts)

    if _state == UI_IDLE:
        _note = Note(now=SCREEN_IDLE_NOW, why=SCREEN_IDLE_WHY,
                     where=SCREEN_IDLE_WHERE)
    elif _state == UI_FAILED and result.error:
        _note = Note(
            now="**選股中止**",
            why=_error_why(SRC_SCREEN, result.error),
            where=("本站不以殘缺資料湊出名單。若是 FinMind 額度用罄，"
                   "額度每日 00:00 重置；其餘請到"
                   f"{ia_nav.where_to_find(ia_nav.SECTION_WHY_DATA_HEALTH)}"
                   "看 MOPS／Goodinfo 備援鏈是否可用"))
    elif _state == UI_FAILED:
        # 沒有例外、卻連「有幾列」都讀不出來 → 回傳契約漂移。
        # **不寫成「0 檔」** —— 那是替上游宣稱一件它沒說的事。
        _note = Note(
            now="**選股跑完了，但回傳的東西讀不出「有幾檔」**",
            why=(f"{MISS_TEXT.get(MISS_CONTRACT_DRIFT, '回傳形態與約定不符')}"
                 f"　—— {SRC_SCREEN}原本恆回一個 DataFrame，"
                 "本輪回的東西連列數都取不到"),
            where=(f"重跑不會好，這要改程式：{NO_EXIT_MARKER}；"
                   "請把這一行連同上方「L3 說明」回報給維護者"))
    else:   # UI_EMPTY —— 跑完了，0 檔。**這是有效結果，不是故障、不是還沒跑。**
        _note = Note(
            now=SCREEN_EMPTY_NOW,
            why=("**這是一個有效的結果**（已經跑完，不是還沒跑、也不是故障）—— "
                 "存活池本身可能為空、勾選的因子沒有一檔算得出綜合分、"
                 "或空頭濾網把候選全部剔除。上面的「L3 說明」寫的是哪一種"),
            where=("放寬條件（少勾幾個因子）後再"
                   f"{press(ACTION_RUN_SCREEN_LABEL)}；"
                   "若「L3 說明」指向季快照未就緒，那要等排程補抓，"
                   "重按不會改變它"))
    return Card(key="find.screen_result", label="選股結果",
                state=_state, note=_note), tuple(_facts)


def build_heatmap_card(hm: HeatmapReadout
                       ) -> tuple[Card, tuple[tuple[str, str], ...]]:
    """線框葉2 左半「產業漲跌熱力圖」的狀態卡。**2026-09-07 已接線。**

    四態對映（逐條理由見 `load_heatmap` 的 docstring）：
      未按載入鈕 → idle ／ L3 或組圖例外 → failed ／ **一檔都沒抓到 → failed
      （紅，線框葉2 `err` 原文）** ／ 只抓到一部分 → degraded ／ 全抓到 → live

    ⚠️ **`wired=` 不再傳 False。** 前一批這張卡恆為 `unwired`，理由是
    「唯一的 public 入口自帶 5 個寫死的 widget key」—— 那個理由**本批已經
    不成立**（類股宇宙上移 L0、treemap 組裝抽成 public L4、取數走新的 L3）。
    接上之後還畫 `unwired`，等於對使用者說「這裡沒有出口」，而其實有一顆按鈕
    就在上面 —— 那是反方向的說謊（同 FE-18 對估值那一項的處置）。
    """
    _state = classify_ui_state(
        requested=hm.requested,
        error=hm.error or None,
        has_value=hm.any_data,
        # 一檔都沒抓到 → 升紅（`MISS_FETCH_FAILED` 在 L0 的 `FAILED_REASONS` 裡）。
        # **不自己寫 `state = UI_FAILED`** —— 那會是本頁自建的第二套判定。
        reason=MISS_FETCH_FAILED,
        discriminative=hm.complete)
    _facts: list[tuple[str, str]] = [
        ("市場 / 區間", f"{hm.market_label or HEATMAP_MARKET_LABEL_IDLE}　·　"
                       f"{hm.period_label or HEATMAP_PERIOD_LABEL}"
         + (f"（＝ {hm.n_bars} 個**交易日**，不是日曆日）" if hm.n_bars else "")),
        ("顏色怎麼讀", "紅＝漲、綠＝跌（**台灣慣例**，與美股配色相反）；"
                        "抓不到的格子**留白**，不是綠色也不是 0%"),
        ("切換市場或區間", HEATMAP_SWITCH_HINT),
    ]
    if hm.requested:
        _facts.append((
            "資料覆蓋率",
            f"類股層 {hm.fetched_n}/{hm.sectors_n}"
            + (f"、子成分 {hm.sub_fetched_n}/{hm.sub_total_n}"
               if hm.sub_total_n else "")))
    if hm.single_stock_proxy and hm.disclosure:
        # H-2 揭露：台股側每個「類股」其實是一檔代表股。**L0 原文，不改寫。**
        _facts.append(("⚠️ 台股口徑", hm.disclosure))

    if _state == UI_LIVE:
        return Card(key="find.heatmap", label="產業漲跌熱力圖",
                    state=UI_LIVE,
                    value=f"{hm.fetched_n} 個類股"), tuple(_facts)

    if _state == UI_IDLE:
        _note = Note(now=HEATMAP_IDLE_NOW, why=HEATMAP_IDLE_WHY,
                     where=HEATMAP_IDLE_WHERE)
    elif _state == UI_FAILED and hm.error:
        _note = Note(now="**熱力圖畫不出來**",
                     why=_error_why(SRC_HEATMAP, hm.error),
                     where=HEATMAP_FAILED_WHERE)
    elif _state == UI_FAILED:
        # 按過了、一檔都沒回來 —— 線框葉2 `err` 就是這一格。
        _note = Note(now=HEATMAP_FAILED_NOW, why=HEATMAP_FAILED_WHY,
                     where=HEATMAP_FAILED_WHERE)
    else:   # UI_DEGRADED —— 有值、圖照畫，只是缺了幾格（留白，不填 0）。
        _note = Note(
            now=HEATMAP_DEGRADED_NOW,
            why=(f"這一輪只抓到 類股層 {hm.fetched_n}/{hm.sectors_n}"
                 + (f"、子成分 {hm.sub_fetched_n}/{hm.sub_total_n}"
                    if hm.sub_total_n else "")
                 + " —— 缺的格子在圖上**留白**、hover 顯示「無資料」，"
                   "**不會**填 0 冒充持平"),
            where=HEATMAP_DEGRADED_WHERE)
    return Card(key="find.heatmap", label="產業漲跌熱力圖",
                state=_state, note=_note), tuple(_facts)


def build_sector_flow_card(flow: SectorFlowReadout
                           ) -> tuple[Card, tuple[tuple[str, str], ...]]:
    """線框葉2 右半「三大法人資金流向泡泡圖」的狀態卡。

    四態對映（逐條理由見 `load_sector_flow` 的 docstring）：
      未按載入鈕 → idle ／ L3 例外 → failed ／ 快取未產生 → **empty（不是紅）**
      ／ 快取過期 → degraded ／ 其餘 → live
    """
    _state = classify_ui_state(
        requested=flow.requested,
        error=flow.error or None,
        has_value=bool(flow.sectors),
        discriminative=not flow.stale,
    )
    _facts: list[tuple[str, str]] = []
    if flow.updated_at:
        _facts.append(("快取更新於", flow.updated_at))
    if flow.n_days:
        _facts.append(("採用交易日", f"{flow.n_days} 天"))
    if flow.insufficient:
        _facts.append((f"交易日不足 {WINDOW_Y_MIN_DAYS} 天（未列入象限）",
                       "、".join(flow.insufficient)))
    _facts.append((
        "你的持股板塊",
        "、".join(flow.highlight) if flow.highlight else
        "未偵測到 —— 到 ETF 組合按「計算組合」，或設定個股組合雲端清單後才會標出"))

    if _state == UI_LIVE:
        _value = f"{len(flow.sectors)} 個板塊"
        return Card(key="find.sector_flow", label="三大法人資金流向泡泡圖",
                    state=UI_LIVE, value=_value), tuple(_facts)

    if _state == UI_IDLE:
        _note = Note(now=MAP_IDLE_NOW, why=MAP_IDLE_WHY, where=MAP_IDLE_WHERE)
    elif _state == UI_FAILED:
        _note = Note(now="**板塊資金圖無法產生**",
                     why=_error_why(SRC_SECTOR_FLOW, flow.error),
                     where=("先確認網路／proxy；細節在"
                            f"{ia_nav.where_to_find(ia_nav.SECTION_WHY_DATA_HEALTH)}"))
    elif _state == UI_DEGRADED:
        _note = Note(
            now="**畫的是最後一次成功凍結的快照，不是今天的**",
            why=(f"盤後凍結任務的更新時戳距今已超過門檻"
                 f"（{flow.stale_reason or '上游沒有給原因'}；"
                 f"metadata 時戳 {flow.meta_updated_at or '未知'}）—— "
                 "圖照畫，但別拿它當今天的資金流向讀"),
            where=("等當日盤後的「Update Sector Flow」排程跑完；"
                   f"重複{press(ACTION_LOAD_MAP_LABEL)}不會讓快照變新"))
        return Card(key="find.sector_flow", label="三大法人資金流向泡泡圖",
                    state=UI_DEGRADED, note=_note), tuple(_facts)
    else:   # UI_EMPTY —— 快取還沒產生。灰，不是紅（沒有人壞掉）。
        _note = Note(
            now="**板塊資金快取尚未產生**",
            why=(f"{flow.reason or '讀不到盤後凍結的快照'} —— "
                 "這不是故障，是當日盤後任務還沒產生資料"),
            where=("等當日盤後的「Update Sector Flow」排程；"
                   "或在 GitHub Actions 手動跑一次該工作流程"))
    return Card(key="find.sector_flow", label="三大法人資金流向泡泡圖",
                state=_state, note=_note), tuple(_facts)


# ══════════════════════════════════════════════════════════════════
# 渲染（薄；所有判斷都在上面的純函式裡）
# ══════════════════════════════════════════════════════════════════
def _render_one(card: Card, facts: Sequence[tuple[str, str]] = ()) -> None:
    """畫一張卡，**並且不讓它把整頁畫到一半就死掉**。

    ⚠️ **2026-09-07 FE-9：本體已上移至共用層** `_ui_kit.render_card_isolated()`
    —— 本頁與頁 1 原本各有一份逐行同構的 `_render_one()`（**兩把尺**：
    一邊修了「`except ... as _e` 的 `_e` 會被 `del`」那個坑、另一邊沒修，
    就是最典型的漂移）。**邏輯一字未改**，本函式只剩「把本頁專屬的三樣東西
    綁上去」：log 前綴 / 出處文案（出事的是哪一層只有本頁知道）/ 去哪補。
    """
    render_card_isolated(
        card, facts=facts,
        owner="views/page_find",
        error_why=lambda _err: _error_why(SRC_RENDER, _err),
        where=("這是渲染層的問題，不是你操作的問題 —— "
               f"{NO_EXIT_MARKER}；請把上面那行訊息回報給維護者"))


def load_factor_labels() -> tuple[dict[str, str] | None, str]:
    """L3 的「UI 下拉 label → factor key」SSOT。失敗 → `(None, repr(e))`。

    ⚠️ **為什麼這一支要單獨存在、而不是在 form 裡直接 import**（紅隊實測後修）：
    `SCREEN_ANGLE_LABELS` 是 form 畫得出來的**前提** —— 沒有它就沒有選項可畫。
    原本寫成 form 函式開頭一行裸 import，於是該 L3 模組**只要 import 失敗**，
    例外會直接穿過 `render_page_find()` 變成**整頁未捕捉例外**（畫面全空白、
    一句話都沒有）。§1 要的是「紅態看得見」，不是「換一種炸法」。
    現在改成：取不到 → 回 `None` → 葉1 畫一張**紅卡**說明，**不畫表單**
    （不能拿一份自己編的因子清單去頂替 SSOT —— 那是第二個真相源）。
    """
    try:
        from src.services.fundamental_screener_service import (
            SCREEN_ANGLE_LABELS,
        )
        return dict(SCREEN_ANGLE_LABELS), ""
    except Exception as _e:  # noqa: BLE001 — 轉成紅卡，不吞
        print(f"[views/page_find] 因子 label SSOT 取不到 → 表單不畫：{_e!r}")
        return None, repr(_e)


def build_form_unavailable_card(error: str) -> Card:
    """因子 label SSOT 載不進來 → 表單畫不出來。**紅態，且沒有使用者出口。**"""
    return Card(
        key="find.screen_form", label="條件表單",
        state=UI_FAILED,
        note=Note(
            now="**條件表單畫不出來**",
            why=_error_why(
                "L3 因子清單（`services.fundamental_screener_service."
                "SCREEN_ANGLE_LABELS`）", error),
            where=("本頁不會拿一份自己編的因子清單頂替它（那會變成第二個真相源，"
                   f"而且選出來的名單會與其他入口不一致）—— {NO_EXIT_MARKER}；"
                   "請把上面那行訊息回報給維護者")))


def _render_screen_form(labels: Mapping[str, str]) -> bool:
    """葉1 ① ② ③ 條件表單 —— 鐵律 2 ＋ 鐵律 1 的落點。

    Args:
        labels: L3 的 `SCREEN_ANGLE_LABELS`（label → factor key）。
            **由 caller 先取好並確認非 None** —— 見 `load_factor_labels()`。

    Returns:
        這一次 rerun 是否由 submit 觸發。

    結構保證（與 `_ui_kit.single_submit_form()` **同一套契約**）：
      · 一個 `st.form`、**一顆** `st.form_submit_button`；
      · form 內**沒有** `st.button` / `st.download_button`
        （Streamlit 實跑即拋 `StreamlitAPIException`，線框 F11）；
      · widget **當下值**（`SS_*_WIDGET`）與**已套用值**（`SS_APPLIED_SCREEN`）
        分家，下游只讀後者 —— 只包一層 `st.form` 只擋得住互動 rerun，
        **重運算一分沒省**，靠的是這一層分家。

    ⚠️ 為什麼沒有直接用 `_ui_kit.single_submit_form()`：它只吃一組 `st.radio`，
    而這裡需要 multiselect ＋ selectbox。見檔頭「鐵律 2 的一個已知缺口」。
    """
    # UI 下拉的 label → factor key 一律讀 L3 SSOT，**禁止 UI 端寫死 key**
    # （`SCREEN_ANGLE_LABELS` 上方註解原文）。
    _labels = list(labels)
    _default_labels = [_l for _l in _labels
                       if labels[_l] == DEFAULT_FACTOR_KEY]
    if not _default_labels:
        # §1 Fail Loud：預設因子從 SSOT 消失了 → **就地降級並說明**，
        # 不靜默退回「第一項」（第一項正好是本頁未接線的估值因子，
        # 那會讓每個人的預設名單都少算一個因子而沒有任何跡象）。
        st.warning(
            f"⚠️ 預設因子 `{DEFAULT_FACTOR_KEY}` 不在 L3 `SCREEN_ANGLE_LABELS` "
            "裡（對面可能改了因子 key）—— 本次表單**不預選任何因子**，"
            "請自行勾選；請把這行訊息回報給維護者。", icon="⚠️")

    with st.form(FORM_KEY):
        for _chunk, _columns in grid(("①", "②", "③"), MAX_COLS):
            for _slot, _col in zip(_chunk, _columns):
                with _col:
                    if _slot == "①":
                        st.markdown("**① 基本面優選**")
                        st.caption(
                            f"{PRESCREEN_REQUIRED_PASSES} 項全過（自動，不需勾選）："
                            f"負債比<{DEBT_RATIO_MAX * 100:g}% · 三率三升 YoY · "
                            f"淨流動值>0 · EPS>{EPS_MIN:g}。"
                            "四項全過才入選股網候選池。")
                    elif _slot == "②":
                        st.markdown("**② 勾條件**")
                        st.multiselect(
                            "要用哪些條件？（可複選）",
                            _labels, default=_default_labels,
                            key=SS_FACTORS_WIDGET,
                            label_visibility="collapsed")
                    else:
                        st.markdown("**③ 排序與筆數**")
                        st.caption("排序：綜合評分（各因子百分位平均）")
                        st.selectbox(
                            "顯示筆數", TOP_N_OPTIONS,
                            index=TOP_N_OPTIONS.index(DEFAULT_TOP_N),
                            key=SS_TOPN_WIDGET,
                            label_visibility="collapsed")
        _submitted = st.form_submit_button(ACTION_RUN_SCREEN_LABEL,
                                           type="primary")

    if _submitted:
        # 唯一的寫入點：widget 當下值 → 已套用值。
        # **這個 key 的存在性就是選股結果的 `requested=` gate**（見檔頭）。
        _picked = st.session_state.get(SS_FACTORS_WIDGET) or []
        st.session_state[SS_APPLIED_SCREEN] = {
            "factors": [labels[_l] for _l in _picked if _l in labels],
            "top_n": int(st.session_state.get(SS_TOPN_WIDGET, DEFAULT_TOP_N)),
        }
    st.caption(WIRING_DISCLOSURE)
    return bool(_submitted)


def _render_screen_leaf(session: Mapping[str, Any]) -> None:
    """葉1 選股網：條件表單 → 總覽卡 ＋ dataframe ＋ CSV。"""
    section_header(f"葉1 · {LEAF_SCREEN_TITLE}",
                   "勾條件 → 送出一次 → 一張候選清單。")

    # 表單畫得出來的前提是 L3 的因子清單載得進來。載不進來 → 紅卡，不畫表單
    # （見 `load_factor_labels()`：原本那行裸 import 會讓整頁空白）。
    _labels, _labels_err = load_factor_labels()
    if _labels is None:
        _render_one(build_form_unavailable_card(_labels_err))
    else:
        _render_screen_form(_labels)

    _req = applied_screen_request(session)
    _result = load_screen_result(_req)
    _card, _facts = build_screen_result_card(_result, _req)

    section_header("選股結果")
    _render_one(_card, _facts)

    if _card.state != UI_LIVE:
        return

    # ── 只有 live 才有表可畫。**CSV 鈕在 form 外**（線框 F11 連帶）──────
    st.caption("本次因子：" + (" · ".join(_result.hits) if _result.hits
                              else "僅基本面四項全過"))
    st.dataframe(_result.df, hide_index=True, width="stretch")
    try:
        _csv = _result.df.to_csv(index=False).encode("utf-8-sig")
    except Exception as _e:  # noqa: BLE001 — 下載不可用不該炸掉整張表
        print(f"[views/page_find] CSV 匯出失敗：{_e!r}")
        st.caption(f"（CSV 匯出暫不可用：{scrub_state_glyphs(repr(_e))[0]}）")
        return
    st.download_button("💾 下載選股結果 CSV", data=_csv,
                       file_name="screener_result.csv", mime="text/csv",
                       key="p02v_screen_csv")


def _render_map_leaf(session: Mapping[str, Any]) -> None:
    """葉2 板塊地圖：熱力圖 ＋ 資金泡泡並列 · 3 欄圖例 ＋ 口徑揭露。

    ⚠️ **2026-09-07 FE-32：docstring 的「（未接線）」三個字已移除** ——
    熱力圖本批接上了，留著那三個字就是一句過期的自述（下一個人會照著它
    以為這裡還沒接，然後又去做一次）。
    """
    section_header(f"葉2 · {LEAF_MAP_TITLE}",
                   "產業熱力圖與板塊資金泡泡在同一葉並列 —— "
                   "客戶已核准的入口整併，兩者不再是兩個分頁。")

    # 單顆 `st.button`，**不在 form 內**（線框葉2 live 原文）。
    # 它是板塊地圖那半頁的**唯一** gate 旗標寫入點。
    if st.button(ACTION_LOAD_MAP_LABEL, key=SS_MAP_BUTTON, type="primary"):
        st.session_state[SS_MAP_REQUESTED] = True

    _requested = map_requested(session)
    # 熱力圖是**批次冷抓數十檔**，spinner 只包這一段（泡泡圖讀本地快照，很快）。
    # ⚠️ `requested=False` 時 `load_heatmap` 直接回空 readout，一行 L3 都不呼叫。
    if _requested:
        with st.spinner("批次抓取類股代表的日線收盤…"):
            _heatmap = load_heatmap(requested=True)
    else:
        _heatmap = load_heatmap(requested=False)
    _flow = load_sector_flow(session, requested=_requested)

    _cards = (build_heatmap_card(_heatmap), build_sector_flow_card(_flow))
    # 兩張並列（鐵律 1：`grid` 內部硬夾 MAX_COLS，這裡要的是 2 欄）。
    for _chunk, _columns in grid(_cards, 2):
        for (_card, _facts), _col in zip(_chunk, _columns):
            with _col:
                _render_one(_card, _facts)

    # ── 左半：產業熱力圖 ─────────────────────────────────────────
    # ⚠️ **版面上的誠實揭露**：線框寫「左：熱力圖　右：泡泡圖」，而本頁的
    #    左右並列目前只落在**兩張狀態卡**上，兩張**圖**仍是上下堆疊
    #    （熱力圖在上、泡泡圖在下）。泡泡圖的版面是前一批已交付的，
    #    把它塞進半寬欄位屬版面異動（v3 §03-2 ①：要先出線框給客戶拍板），
    #    **不在本批的授權範圍內** —— 故本批只把熱力圖補在它自己那張卡下面。
    # ⚠️ 組圖已經在 `load_heatmap()` 裡包過 try 了（失敗 → 紅卡），
    #    這裡只剩 `st.plotly_chart` 本身；它若炸掉一樣不該吃掉下半頁。
    if _heatmap.figure is not None:
        try:
            st.plotly_chart(_heatmap.figure, width="stretch")
        except Exception as _e:  # noqa: BLE001 — 轉成看得見的紅字，不吞
            print(f"[views/page_find] 熱力圖繪製失敗：{_e!r}")
            st.error(
                "🔴 熱力圖畫不出來（資料讀到了，是繪圖層的問題）："
                f"{scrub_state_glyphs(repr(_e))[0] or UNKNOWN_ERROR_TEXT}",
                icon="🔴")

    if _flow.sectors:
        # ⚠️ L4 純繪圖層的 late import 也要包 —— 它若 import / 繪圖失敗，
        #    裸寫會讓**已經畫好的兩張卡以下全部消失**（半截死頁），
        #    而畫面上一句解釋都沒有。轉成一句看得見的紅字，圖例照畫。
        try:
            from src.ui.render.sector_flow_render import (
                build_sector_flow_figure,
            )
            st.plotly_chart(
                build_sector_flow_figure(
                    list(_flow.sectors),
                    highlight_sectors=set(_flow.highlight)),
                width="stretch")
        except Exception as _e:  # noqa: BLE001 — 轉成看得見的紅字，不吞
            print(f"[views/page_find] 泡泡圖繪製失敗：{_e!r}")
            st.error(
                "🔴 泡泡圖畫不出來（資料讀到了，是繪圖層的問題）："
                f"{scrub_state_glyphs(repr(_e))[0] or UNKNOWN_ERROR_TEXT}",
                icon="🔴")

        # ── 3 欄圖例（線框葉2 的 `n` 原文）。象限名讀資料本身，零轉抄。──
        section_header("圖例 — 這一份快照的象限分佈")
        for _chunk, _columns in grid(_flow.quadrant_counts, MAX_COLS):
            for (_q, _n), _col in zip(_chunk, _columns):
                with _col:
                    st.markdown(f"**{_q}**　{_n} 個板塊")

    # ── 口徑揭露：**常駐 caption，不隨狀態消失** ──────────────────────
    #    線框原文：「使用者看圖之前就該知道這張圖在量什麼」。
    st.caption(SECTOR_FLOW_AXIS_NOTE)


def render_page_find() -> None:
    """🔍 找標的（IA v2 第 2 頁）。**本批無 production caller，刻意如此。**"""
    _session = st.session_state

    st.markdown(f"## {ia_nav.page_label(ia_nav.PAGE_FIND)}")
    st.caption("從全市場縮到一張候選清單。")

    _leaf1, _leaf2 = st.tabs([LEAF_SCREEN_TITLE, LEAF_MAP_TITLE])
    with _leaf1:
        _render_screen_leaf(_session)
    with _leaf2:
        _render_map_leaf(_session)
