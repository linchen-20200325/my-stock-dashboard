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

**本檔沒有 production caller**（`app.py` 本批不接線；且 FE-7 同時在改該檔，
本批一個字都沒有碰 `app.py` 與 `src/ui/tabs/__init__.py`）。舊分頁不動、不下架。

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
  3. **未接線的兩項** ← 同上兩個旗標；它們的 `wired=False` 使
     `classify_ui_state` 第 1 條規則先判成 `unwired`，與請求與否無關
     （這是刻意的：未接線**永遠不會**因為多按一次而改變）。

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
    缺貨       L3 `services.shortage_screener_service.run_shortage_scan`
    抗跌 RS    L3 `services.rs_leader_service.run_rs_leader_scan`
    跨季轉強   L3 `services.fundamental_screener_service.build_trend_map`
    空頭濾網   L3 `services.allocation_service.get_macro_regime`
    板塊資金   L3 `services.sector_flow_service.get_sector_flow_view`
                 → L4 `ui.render.sector_flow_render.build_sector_flow_figure`（純繪圖）

**零 L1 import、零 `requests` / `yfinance` / FinMind、零 `pd.read_csv(url)`、
零 SQL / parquet 讀寫、零 `@st.cache_data` / `@st.cache_resource`、
零 inline `ttl=`、零底線開頭的跨檔私有符號、零 `from app import`。**
（前車之鑑：`CLAUDE.md §8.2.A.2` 的 **V-SMART-CACHE-1**〔L5 自建 5 個 cache〕
與 **V-PICKER-PRIV-1**〔L5 直取 L1 的 `_fm_raw_headers`〕。）
⚠️ 本頁**受 `tests/test_c3_layering_guard.py` 管**（`_PATH_LAYERS` 已含
`src/ui/views/` → L5），違反 R4／R5 是 CI 紅燈，不是假綠燈。

═══ 本批**沒有接上**的兩項（誠實揭露，不是漏寫）═══════════════════════
1. ⛔ **產業熱力圖** —— 線框葉2 的左半。
   **卡在哪**：唯一的 public 入口是 L4 `ui.render.etf_render.render_sector_heatmap()`，
   而它**自帶 5 個寫死的 widget key**（`heatmap_market` / `heatmap_period` /
   `heatmap_refresh` / `heatmap_load` / `heatmap_loaded`）與**自己那顆 gate 按鈕**。
   在本頁再呼叫一次 → 與既有 🏦 ETF 分頁**撞 `DuplicateWidgetID`**，
   且畫面會出現**兩顆**載入鈕（線框 N6 明文要求那顆舊 gate 被本頁的
   「🗺️ 載入板塊地圖」**吸收**）。
   類股代表清單（`_US_SECTORS` / `_TW_SECTORS`）與 treemap 組裝
   （`_build_treemap_data`）**都是 L4 的私有符號**，跨檔直取正是
   V-PICKER-PRIV-1 的前車之鑑；自己抄一份類股表則是第二個 SSOT（§2.1）。
   → **本頁標 `unwired`，並在卡上寫明要補在哪**（見 `HEATMAP_WHERE`）。
2. ⛔ **估值（本益比）因子與「名稱」欄** —— `get_ranked_picks(pe_map=, name_map=)`
   的 SSOT 是 **L1** `src/data/stock/yield_pe_fetcher.fetch_pe_name_maps`，
   **全 repo 沒有任何 L3 wrapper**（`services/yield_screener_service.py` 只轉發
   股利與 proxy 設定，不含它）。L5 直呼 L1 是 R4 違憲；經
   `src/ui/tabs/yield_screener.py` 的 re-export 繞道**只是騙過 AST、不改性質**。
   → **不接**。若使用者勾了「估值」，本頁在卡上與表單下方**都**寫明
   「這個因子在本頁沒有資料、不計入綜合分」，**不靜默降級**
   （`composite_rank_candidates` 的 note 只揭露缺貨 / RS 兩個因子，
   pe 缺料**不會**出現在它的 note 裡 —— 那就是本檔必須自己講的原因）。

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
**實測**：把 5 個 L3 模組 ＋ 1 個 L4 模組全部注入 `ImportError` 後整頁仍
`exception == []`，畫出 2 張紅卡 ＋ 1 張未接線卡，常駐的口徑揭露照樣在最後一行。
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
    MISS_TEXT,
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
    render_card,
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

#: 預設勾選的因子 key。**刻意不用 `SCREEN_ANGLE_LABELS` 的第一項** ——
#: 第一項是 `pe_low`（估值），而它在本頁未接線（見檔頭「沒有接上的兩項」②）。
#: 拿一個必然沒有資料的因子當預設，等於讓每個第一次進來的人都拿到一份
#: 悄悄少算一個因子的名單。`eps_high` 的資料來自存活池自己的 `eps` 欄，
#: 不需要任何額外取數。
DEFAULT_FACTOR_KEY: str = "eps_high"

#: 本頁**未接線**的因子 key（缺 `pe_map`）。見檔頭「沒有接上的兩項」②。
UNWIRED_FACTOR_KEY: str = "pe_low"

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

#: 熱力圖未接線的「去哪補」。**沒有使用者可執行的出口** ——
#: 線框葉2 的 unwired 原文就是這句：「這是待接線項，不是你操作的問題」。
HEATMAP_WHERE: str = (
    f"{NO_EXIT_MARKER} —— 這是待接線項，不是你操作的問題；"
    f"{press(ACTION_LOAD_MAP_LABEL)}也不會改變它。"
    "要接上需先讓 L4 `ui/render/etf_render.render_sector_heatmap()` 能被外部"
    "重複掛載（widget key 加前綴參數、載入 gate 由 caller 提供），"
    "或把類股代表清單上移到 L0 並讓 treemap 組裝成為 public"
)

#: 估值因子未接線的「去哪補」。同樣沒有使用者出口。
PE_UNWIRED_WHERE: str = (
    f"{NO_EXIT_MARKER} —— 這是待接線項，不是你操作的問題。"
    "要接上需先在 `src/services/` 補一支 L3 wrapper 轉發 L1 "
    "`src.data.stock.yield_pe_fetcher.fetch_pe_name_maps`；"
    "在那之前本頁不會、也不該直呼 L1"
)

#: 估值因子未接線的「為什麼沒有」。
PE_UNWIRED_WHY: str = (
    "本益比／名稱對照表的唯一真相源住在 L1，而它**沒有 L3 介面**；"
    "L5 直呼 L1 是分層違憲（`CLAUDE.md §8.2` 硬規則第 4 條），"
    "經其他 L5 檔 re-export 繞道只是騙過靜態檢查、不改變性質"
)

#: 表單下方常駐的接線揭露（不隨狀態消失）。
WIRING_DISCLOSURE: str = (
    "**取數接線揭露**：缺貨動能 / 抗跌 RS / 跨季轉強 / EPS 四個因子走 L3 service，"
    "已接線；**估值（本益比）在本頁未接線** —— 勾了也不會計入綜合分，"
    "且結果表的「名稱」欄會是空的。理由與補法見結果卡上的說明。"
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
    hits: tuple[str, ...] = ()
    error: str = ""
    aux_errors: tuple[tuple[str, str], ...] = ()

    @property
    def has_rows(self) -> bool:
        """這一輪有沒有選出東西。**只在 `requested=True` 時有意義。**"""
        return bool(self.rows)


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
        存活池 / 缺貨 / RS / 跨季 / 總經位階 → `get_ranked_picks(auto_fetch=False)`

    ⚠️ **為什麼是 `auto_fetch=False`**：三個掃描由本函式**顯式**發（每支各自
    try/except），這樣 (a) 一支掛掉不連坐其他支、(b) 掃描結果拿得到，
    才能用 SSOT 的 `summarize_factor_hits()` 算「本次因子」的分子/分母。
    傳 `auto_fetch=True` 的話掃描結果留在 L3 裡拿不到，畫面就只能自己再數一次
    ＝ 第二把尺。

    ⚠️ **`pe_map` / `name_map` 一律傳 `None`** —— 見檔頭「沒有接上的兩項」②。
    這會讓「估值」因子缺料、「名稱」欄空白，而 L3 的 note **不會**提到它
    （`composite_rank_candidates` 的 `_missing` 只收缺貨與 RS）→
    所以本檔必須在卡上自己講，且**不得**假裝那是一個正常結果。

    邊界（三個都真的走得到）：
      (a) **冷啟動 / 還沒送出** → `ScreenResult(requested=False)`，
          全部格子 `idle`（**還沒有人叫**），不是 `empty`（叫了但沒值）。
      (b) **L3 在呼叫期拋例外**（含 late import 失敗）→ `repr(e)` 帶回 →
          結果卡轉**紅態**並把訊息印在畫面上。**不是 `except: pass`**。
      (c) **回空表 / `None` / 0 筆** → `rows` 分別是 `0` / `None` / `0`，
          `has_rows` 為 False → `empty`（灰）。**不是綠燈、也不是紅燈。**
    """
    if not req.submitted:
        return ScreenResult(requested=False)

    _factors = list(req.factors)
    _aux: list[tuple[str, str]] = []

    _surv_df, _surv_n, _surv_err = _load_survivors()
    if _surv_err:
        _aux.append(("存活池", _error_why(SRC_SURVIVORS, _surv_err)))
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
            pe_map=None,            # ← 未接線，見檔頭「沒有接上的兩項」②
            name_map=None,          # ← 同上
            shortage_rows=_short_rows,
            rs_rows=_rs_rows,
            trend_map=_trend_map,
            auto_fetch=False,
            regime=_regime,
        )
    except Exception as _e:  # noqa: BLE001 — 轉成紅態顯示，不吞
        print(f"[views/page_find] 選股排名失敗 → 結果卡轉紅態：{_e!r}")
        return ScreenResult(requested=True, error=repr(_e),
                            survivors_n=_surv_n, aux_errors=tuple(_aux))

    _hits, _hits_err = _summarize_hits(
        _factors, shortage_rows=_short_rows, rs_rows=_rs_rows,
        trend_map=_trend_map)
    if _hits_err:
        _aux.append(("因子命中摘要", f"不可用：{_hits_err}"))

    return ScreenResult(
        requested=True, df=_df, note=str(_note or ""),
        rows=_frame_rows(_df), survivors_n=_surv_n, hits=_hits,
        aux_errors=tuple(_aux))


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


# ══════════════════════════════════════════════════════════════════
# 卡片建構（純函式；`Card` / `Note` 的驗證在對面，本檔不重複）
# ══════════════════════════════════════════════════════════════════
def _fmt_count(n: int | None) -> str:
    """檔數 → 顯示字串。`None` = 取不到 → `'—'`，**不寫 0**（§1 不假報）。"""
    return "—" if n is None else f"{n}"


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
    if UNWIRED_FACTOR_KEY in req.factors:
        _facts.append((
            "估值（本益比）",
            f"**本頁未接線，不計入綜合分**；{PE_UNWIRED_WHY}"))
    _facts.append(("名稱欄", "本頁空白 —— 名稱對照表與本益比同一份來源，一起未接線"))
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
        if UNWIRED_FACTOR_KEY in req.factors:
            # live 也要畫 Note —— `render_card` 已改成「只要有 Note 就畫」。
            # 靜默丟棄「你勾的因子其實沒算」這種說明 ＝ §1 禁止的掩蓋問題。
            _note = Note(
                now="**這份名單少算了一個你勾的因子**（估值／本益比）",
                why=PE_UNWIRED_WHY,
                where=PE_UNWIRED_WHERE)
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


def build_heatmap_card(requested: bool) -> tuple[Card, tuple[tuple[str, str], ...]]:
    """線框葉2 左半「產業漲跌熱力圖」—— **本批未接線**（見檔頭）。

    `wired=False` → `classify_ui_state` 第 1 條規則直接判 `unwired`，
    **與請求與否無關**：未接線的東西不會因為多按一次而改變，
    這正是它與「尚未載入」必須分成兩態的原因。
    """
    _state = classify_ui_state(requested=requested, has_value=False,
                               wired=False)
    return Card(
        key="find.heatmap", label="產業漲跌熱力圖",
        state=_state,
        note=Note(
            now="**本頁還沒有產業熱力圖**",
            why=("唯一的 public 入口 `etf_render.render_sector_heatmap()` "
                 "自帶 5 個寫死的 widget key 與**自己那顆載入鈕**，"
                 "在本頁再掛一次會與既有 ETF 分頁撞 DuplicateWidgetID、"
                 "並讓畫面出現兩顆載入鈕；類股代表清單與 treemap 組裝"
                 "都是該檔的私有符號，跨檔直取是分層違憲，"
                 "自己抄一份類股表則會變成第二個真相源"),
            where=HEATMAP_WHERE)), (
        ("現行入口", "🏦 ETF 分頁的「🗺️ 產業熱力圖」（本頁不重複掛載）"),
        ("接線後的樣子", "與右側泡泡圖並列，共用本頁這一顆載入鈕"),
    )


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

    做法沿用頁 1：渲染期若仍有東西炸（例如 L0 給了未知狀態名 →
    `state_meta()` fail loud），把它**就地轉成一張紅卡 ＋ `repr(e)`**，
    其餘的卡照畫。**不是 `except: pass`** —— 例外被轉成看得見的紅態並附原文，
    log 也留一份。半截死頁（上半頁在、下半頁全沒了、畫面上沒有任何一句解釋）
    比一張紅卡危險得多，因為使用者根本不知道有東西不見了。
    """
    try:
        render_card(card, facts=tuple(facts))
        return
    except Exception as _e:  # noqa: BLE001 — 轉成看得見的紅卡，不吞
        # `except ... as _e` 的 `_e` 在區塊結束時會被 `del`，先取出字串。
        _err = repr(_e)
        print(f"[views/page_find] 卡 {card.key!r} 渲染失敗 → 轉紅卡：{_err}")
    _label = scrub_state_glyphs(card.label)[0] or card.key
    render_card(Card(
        key=f"{card.key}.render_failed", label=_label, state=UI_FAILED,
        note=Note(now=f"{_label}　**這一格畫不出來**",
                  why=_error_why(SRC_RENDER, _err),
                  where=("這是渲染層的問題，不是你操作的問題 —— "
                         f"{NO_EXIT_MARKER}；請把上面那行訊息回報給維護者"))))


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
    """葉2 板塊地圖：熱力圖（未接線）＋ 資金泡泡並列 · 3 欄圖例 ＋ 口徑揭露。"""
    section_header(f"葉2 · {LEAF_MAP_TITLE}",
                   "產業熱力圖與板塊資金泡泡在同一葉並列 —— "
                   "客戶已核准的入口整併，兩者不再是兩個分頁。")

    # 單顆 `st.button`，**不在 form 內**（線框葉2 live 原文）。
    # 它是板塊地圖那半頁的**唯一** gate 旗標寫入點。
    if st.button(ACTION_LOAD_MAP_LABEL, key=SS_MAP_BUTTON, type="primary"):
        st.session_state[SS_MAP_REQUESTED] = True

    _requested = map_requested(session)
    _flow = load_sector_flow(session, requested=_requested)

    _cards = (build_heatmap_card(_requested), build_sector_flow_card(_flow))
    # 兩張並列（鐵律 1：`grid` 內部硬夾 MAX_COLS，這裡要的是 2 欄）。
    for _chunk, _columns in grid(_cards, 2):
        for (_card, _facts), _col in zip(_chunk, _columns):
            with _col:
                _render_one(_card, _facts)

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
