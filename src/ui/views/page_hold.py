"""src/ui/views/page_hold.py — IA v2 第 4 頁「💼 我的持股」的**版面落地**（L5 UI）。

規格出處：`docs/wireframes/stock_ia_v1.html` 的 `PAGES[3]`（id=`hold`）。
單一職責（線框 `job` 原文）::

    我已經持有的，該加、該換、該減。（F3：七個區塊全部補齊）

兩葉（線框 `leaves` 原文）::

    葉1 戰情室（1️⃣~6️⃣ ＋ 80/20 配置偏離）
    葉2 組合設定（＝組合管理＋Sheet 綁定）

═══ ⚠️ 這一頁碰的是**使用者資產** —— 先讀這段 ═════════════════════════
前三頁碰的是公開市場資料；**本頁的輸入是使用者自己的 Google Sheets 持股帳本**。
故本頁多一條前三頁沒有的鐵律：

    **本頁一律唯讀。不寫入、不刪除、不改動任何一列持股。**

落實方式（四道，缺一道就只剩自律）：
  1. **本頁只 import 讀取型 L3**（見下方「取數接線表」）。全部四支的名字都以
     `get_` / `fetch_` 開頭，且都在各自的 docstring 自陳「唯讀」／「純讀不寫」。
  2. **凡是需要寫入才做得到的功能，一律標 `unwired` 並寫明「去哪補」** ——
     線框葉2 列的「Sheet 選擇」「觀察清單管理」都落在這一類。
     **不是**「先做一個能寫的版本再說」。
  3. **不顯示任何憑證**：`BindingState.sheet_id` 是 Google Sheet 的識別碼，
     本頁**一個字元都不印出來**，只印「有沒有綁」這個布林（見 `load_binding()`）。
  4. **測試釘死**：`tests/test_p04_hold_view.py::TestReadOnly` 以 AST 白名單釘住
     「本頁可以呼叫哪幾支 L3」，並以黑名單釘住整個 gsheet 寫入面
     （`save_portfolio` / `delete_portfolio` / `save_stock_watchlist` /
     `add_to_stock_watchlist` / `create_new_sheet` / `rename_sheet` …）一個都不准出現。

⚠️ **一個誠實的例外，先講清楚**：`allocation_service.get_allocation()` 會寫
`st.session_state` 的兩個**記憶化快取鍵**（`_ALLOC_CACHE_KEY` / `_ALLOC_SIG_KEY`）。
那是 session 內的計算快取，**不碰 Google Sheets、不碰任何使用者資產**，
且寫入發生在 L3 內部、不是本頁做的。寫在這裡是因為「唯讀」這種全稱句
不該有沒講出來的例外（§-2 規則 6）。

═══ 這個檔**不是**什麼 ═══════════════════════════════════════════════
- **不是**一套新的燈號規則：235 加碼燈 / 3-3-3 / 健檢四盞的判定全在
  L2 `compute.etf.dividend_station` 與 L0 `shared/station_specs.py`，本檔一盞都不判。
- **不是**第二份門檻：80/20 目標、衛星停利門檻、VIX 三段門檻一律讀 L0
  `shared/dividend_station_thresholds.py`，**本檔不寫死任何一個數字**。
- **不是**新的狀態模型：四態一律走 L0 `shared/ui_state.py::classify_ui_state()`。
- **不是**新的卡片型別：`Card` / `Note` / `MAX_COLS` 一律 import
  `src/ui/tabs/tab_today.py` 與 `src/ui/views/_ui_kit.py`。

**本檔沒有 production caller**（`app.py` 掛載另案；本批一個字都沒有碰 `app.py`、
`page_today.py`、`page_find.py`、`page_inspect.py`、`_ui_kit.py`、
`src/ui/tabs/**`、`shared/**`）。舊分頁（`etf_tab_dividend_station` 等）不動、不下架。

═══ 取數接線表（**唯一的規則是「一律走 L3」**）═════════════════════════
**已接線（四支，全部唯讀）**::

    綁定狀態      L3 `services.portfolio_binding_service.get_binding_state`
    VIX           L3 `services.dividend_station_service.fetch_vix`
    總經位階      L3 `services.dividend_station_service.get_station_macro`
    建議持股水位  L3 `services.allocation_service.get_allocation`
    兩套刻度揭露  L0 `shared/station_specs.py`（純常數，零 I/O）

**未接線（全部指向同一個根因）**::

    ⛔ **持股清單本身沒有 L3 介面。**
       實測（量測日 2026-09-07）：`src/services/` 底下沒有任何一支回傳
       「你持有哪幾檔、各幾張、均價多少」。唯一產得出那份 list 的是 L5 私有函式
       `src/ui/etf/etf_tab_dividend_station._load_holdings_from_portfolio()`，
       而它直接呼叫 L1 `gsheet_portfolio` 的**私有** accessor
       （`_get_active_sheet_id` / `_get_active_stock_sheet_id`）。
       跨檔取用底線開頭的私有符號正是 `CLAUDE.md §8.2.A.2` **V-PICKER-PRIV-1**
       登記的那種違憲；經別的 L5 檔 re-export 繞道**只是騙過靜態檢查、不改變性質**
       （頁 2 對估值 PE、頁 3 對估值 357 都是這樣拒絕的，本頁照辦）。
       → 因此**戰情室七個區塊裡有六個的主體是 `unwired`**，見下方「本批沒有接上的項目」。

⚠️ 戰情室的**運算**其實幾乎全都已經有 L3 了（`dividend_station_service` 的
`get_station_rows` / `build_switch_advice` / `compute_portfolio_totals` /
`compute_allocation_split` / `flag_take_profit` / `build_station_digest` /
`build_ai_summary`）—— **缺的只有第一步：把持股清單交給它們。**
這是本頁最重要的一句話：**不是「算不出來」，是「沒有東西可以餵進去」。**
補一支 L3 holdings loader，上面七支全部立刻可用。

**零 L1 import、零 `requests` / `yfinance` / FinMind / `pd.read_csv(url)`、
零 SQL / parquet 讀寫、零 `@st.cache_data` / `@st.cache_resource`、
零 inline `ttl=`、零底線開頭的跨檔私有符號、零 `from app import`。**
⚠️ 本頁**受 `tests/test_c3_layering_guard.py` 管**（`_PATH_LAYERS` 已含
`src/ui/views/` → L5），違反 R4／R5 是 CI 紅燈，不是假綠燈。

═══ 四大鐵律的落點 ═══════════════════════════════════════════════════
1. **3 欄上限** —— 一律 `_ui_kit.grid()`（內部硬夾 `MAX_COLS`）。全檔 **0 個**裸
   `st.columns(n)`。線框 ① 的「三張卡」與 ⑥ 的六個並列區塊都走它
   （⑥ 是 **3 欄 × 2 排**，不是 `st.columns(6)`）。
2. **Form 防重繪** —— 本頁**只有一個 form**（葉2 `form_holdings`），
   **一顆** `st.form_submit_button`（線框原文 ［ 🚀 跑存股戰情室 ］），
   form 內**沒有**任何 `st.button` / `st.download_button`。
   ⚠️ 本頁**直接用共用層** `_ui_kit.single_submit_form()` —— 它只吃一組
   `st.radio`，而本頁的表單輸入**剛好就只有一組 radio**，所以**不必**像頁 2／頁 3
   那樣就地實作第四份表單函式。（那兩頁的「交接事項」仍然成立，只是本頁用不到。）
3. **四態分離** —— 見下面兩段。
4. **空狀態三要素** —— 一律 `tab_today.Note(now, why, where)`。

═══ `requested=` 的來源（本頁**兩個** gate，一個都不是從資料反推）═══════
L0 的鐵律：**`idle` 只能由上游帶下來，禁止由 `if not data:` 推導。**
（頁 1 就是在這裡被紅隊抓到恆真式 `(alloc is not None)`。）

  1. **戰情室全部區塊 ＋ 葉2 的持股列預覽** ← `SS_APPLIED_HOLD in session_state`。
     那個 key **只有** `_ui_kit.single_submit_form()` 的 submit 分支會寫
     （本頁把它當 `applied_key` 傳進去，全檔沒有第二個寫入點）。
  2. **綁定狀態那兩張卡** ← 上面那個 gate **並且**使用者這一輪選了
     「連 Google Sheet 綁定狀態一起讀」。沒選就是**沒有人叫過它** → `idle`，
     而且本頁**真的不會發那一次網路呼叫**。

  ⚠️ **第三個 gate 是「不需要 gate」**：② 兩套刻度揭露是**常駐**的
  （線框原文：「揭露常駐，不隨載入狀態消失」），它的輸入是 L0 的
  `@dataclass(frozen=True)` 常數表，**沒有任何取數**。故它傳的是**字面 `True`**，
  不是從任何資料推回來的東西 —— 一個「永遠開著」的揭露，寫 `requested=True`
  是陳述事實，不是恆真式。（恆真式的問題不在於它恆真，而在於它**假裝自己在判斷**。）

⚠️ **`requested=False` 時本檔一行 L3 都不呼叫。**（`tests/test_p04_hold_view.py::
TestNothingIsCalledBeforeYouAsk` 用不繼承 `Exception` 的毒藥實測，不是讀 docstring。）

═══ 三種「沒有持股」**絕不可混**（本頁的 §1 主戰場）═══════════════════
本頁最容易寫錯、而且錯了最像對的地方::

    還沒按 🚀（或沒選要讀 Sheet） → `UI_IDLE`   灰。**還沒有人叫過。**
    讀了，發現你還沒綁 Sheet       → `UI_EMPTY`  灰。**這是有效結果**，不是故障。
    讀了，綁到了，但那本 Sheet 一本組合都沒有 → `UI_EMPTY`  灰。**同上，而且
                                     與上一條**不是同一件事**，文案必須分得出來。
    讀了，Google 那端掛了          → `UI_FAILED` 紅。**唯一准用紅色的狀態。**

⛔ **「空的組合」不是故障。** 一個剛註冊、還沒填任何一列的使用者，看到的應該是
「你的 Sheet 綁好了，只是還沒有內容」，**不是**一片紅色的錯誤。
把它畫成紅色 = v3 §02 前半句要杜絕的「假性錯誤滿版」，而且會讓**真的**壞掉那一次
沒有人看得見。

⛔ **「還沒綁」與「綁了但空」也不可混。** 前者要你去綁，後者要你去填 ——
指路句完全不同，混在一起等於對其中一半的人指錯路。
本檔的結構性解法：**拆成兩張卡**（`build_binding_card` 判「有沒有綁」、
`build_portfolio_count_card` 判「綁到的那本裡有幾本組合」），
讓兩件事各自持有自己的狀態，**沒有任何一格需要同時代表兩件事**。
沒綁的時候第二張卡是 `idle`（沒有人問過「那本裡有幾本」，因為根本還沒有那一本）——
這一步剛好與 L3 的契約對齊：`BindingState.portfolio_count=None` 的註解寫著
「未知（未綁 or 讀取失敗）；**不腦補 0**」。

═══ 本批**沒有接上**的項目（誠實揭露，不是漏寫）═══════════════════════
全部指向同一個根因（**持股清單沒有 L3 介面**），但「去哪補」各自不同，
因為它們卡住的**位置**不同 —— 有的只差第一步，有的連運算都還沒有 L3：

  1. ⛔ **① 結論三張卡**（該做什麼 / 訊號可信度 / 需要處理）。
     運算面 **L3 已備齊**（`compute_portfolio_totals` ＋ `build_station_digest`），
     只差持股清單。
  2. ⛔ **③ 燈牆**（235 加碼燈 / 3-3-3 / 健檢四盞）。同上（`get_station_rows`）。
  3. ⛔ **④ 換股建議**。`build_switch_advice()` 與 `get_switch_in_candidates()`
     兩支 L3 都在，但**兩半都需要持股清單**：換出要「你持有的紅燈」，
     換入要 `exclude=已持有代號`。⚠️ **刻意不出半個建議** —— 少了 `exclude`
     的「換入候選」會叫你買你已經有的東西，那不是降級，那是錯的建議。
  4. ⛔ **⑤ 80/20 配置偏離 ＋ 衛星停利**。`compute_allocation_split` /
     `flag_take_profit` 都在，只差持股清單（兩支都要張數與均價）。
  5. ⛔ **⑥ 組合深度分析六項**。這一項**卡得比別項深**：再平衡 / 壓力測試 /
     VaR 的純函式在 L2（`compute.etf.etf_calc`），但**連 L3 wrapper 都還沒有**；
     配息現金流有 L3（`dividend_tax_service.get_dividend_tax_view`）但要
     `[{ticker, shares}]`；葡萄串領息的實作是 L5（`tabs.grape_ladder`）、
     自帶寫死的 widget key，在本頁再掛一次會撞 `DuplicateWidgetID`。
  6. ⛔ **⑦ AI 戰情總結**。`build_station_digest` → `build_summary_prompt` →
     `build_ai_summary(digest, gemini_fn)` 三支 L3 都在，`gemini_fn` 也有
     （L3 `app_ai_service.gemini_call`），**只差 digest 的輸入是持股**。
     ⚠️ 線框在這一區畫了一顆單獨的 `st.button`［ ⚡ 生成 AI 總結 ］，
     **本頁刻意沒有把它畫出來**：它的輸入（上方六段的結論）全部未接線，
     畫一顆按了不會發生任何事的鈕，就是線框 F5／N2 兩次點名要修的那種**假出口**。
     接線後再補那顆鈕（它必須在 form **外**）。
  7. ⛔ **葉2 的「Sheet 選擇」與「觀察清單管理」**。這兩項**不是缺 L3，是缺授權** ——
     它們本質上是**寫入**，而本頁一律唯讀（見檔頭第二段）。

⚠️ **本頁唯一會判 `UI_DEGRADED` 的是 ② 兩套刻度**，而且**不是硬湊的**：
它直接讀 L0 `station_specs` 的 `discriminative` 旗標。實測（量測日 2026-09-07）
`KEY_STOCK_TREND`（財報趨勢）標了 `discriminative=False`，
`degraded_reason` 原文是「這格只比較**最近兩季**，看不出趨勢」——
而那盞燈正是本頁個股「健檢」欄（`swap_level`）的輸入之一
（L2 `assess_stock`：grade 尚可但 `is_breakdown` → 提前 🟡）。
**所以本頁這一側的刻度確實有一個已失準的輸入**，線框 ② 的 degraded 文案
（「某一側的門檻來源已標 `discriminative=False`」）在 repo 現況下是**真的**。
若哪天那個旗標被改回 `True`，這張卡會自己變回 live —— 本檔沒有寫死任何一邊。

═══ 這個檔擋得住什麼、擋不住什麼（誠實邊界）═══════════════════════════
`load_vix()` / `load_macro()` / `load_allocation()` / `load_binding()` 的
`try/except` 擋得住的是**呼叫期**例外（模組進得來、但呼叫時炸了）→ 轉成
看得見的紅卡 ＋ `repr(e)`。

⛔ **擋不住 module-level 的 import 失敗。** 本檔 module level 有
`shared.*` 三支與 `src.ui.tabs.tab_today` / `src.ui.views._ui_kit`。
這幾條路徑上任何一個模組在 import 階段壞掉，`import page_hold` 自己會先
`ImportError`，`render_page_hold()` 根本不會被呼叫到 —— 畫面全空白。

✅ **所有 L3 取數都是函式體內的 late import 且各自包在 `try/except` 裡。**
⚠️ 這裡的 late import **不是懶惰**：`src.services.dividend_station_service`
在 module level 就 `import pandas` 並拉進 `src.compute.etf.dividend_station`；
`allocation_service` 更會拉進 `streamlit` ＋ `macro_state_locker`。
放在 module level 會讓「打開這一頁」的故障半徑等於整條資料層。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

import streamlit as st

from shared import ia_nav
# L0 SSOT：燈號規格表（含 `discriminative` 旗標）與缺值原因語彙。
from shared.station_specs import (
    KEY_HEALTH_A,
    KEY_HEALTH_B,
    KEY_HEALTH_C,
    KEY_HEALTH_D,
    KEY_STOCK_HEALTH,
    KEY_STOCK_KD,
    KEY_STOCK_SWAP,
    KEY_STOCK_TREND,
    MISS_FETCH_FAILED,
    MISS_NO_INPUT,
    SPECS_BY_KEY,
)
# L0 SSOT：80/20 目標、衛星停利門檻、VIX 三段門檻。**本檔不寫死任何一個數字。**
from shared.dividend_station_thresholds import (
    CORE_TARGET_PCT,
    SATELLITE_TAKE_PROFIT_PCT,
    SATELLITE_TARGET_PCT,
    VIX_LIGHT1,
    VIX_LIGHT2,
    VIX_LIGHT3,
)
from shared.ui_state import (
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
    banned_signal_glyphs,
    grid,
    render_card_isolated,
    section_header,
    single_submit_form,
)

# ══════════════════════════════════════════════════════════════════
# session key（本頁自有前綴 `p04`，不與既有 `etf_tab_dividend_station` 的
# `_station_*`、`portfolio_manager` 的 key 相撞）
# ══════════════════════════════════════════════════════════════════
#: 葉2 表單的 key。線框寫 `st.form(form_holdings)`；加 `_view` 後綴是為了
#: 與既有 🏦 ETF ›存股戰情室 同時掛上時不撞 Streamlit 的 DuplicateWidgetID。
FORM_HOLDINGS_KEY: str = "form_holdings_view"

#: 「這一輪要跑到哪裡」radio 的 widget key —— **當下值**。下游禁止讀（鐵律 2）。
SS_SCOPE_WIDGET: str = "p04v_scope_widget"

#: **已套用值**。只有 `_ui_kit.single_submit_form()` 的 submit 分支會寫，
#: 寫入形狀為 `{"mode": <SCOPE_*>}`。
#:
#: ⚠️ **這個 key 的「存在性」就是本頁全部區塊的 `requested=` gate。**
#: 不得改成從結果反推 —— `bool(rows)` 分不出「還沒按」與「按了但你沒有持股」，
#: 而後者在本頁是一個**極常見且完全正常**的狀態（新使用者）。
SS_APPLIED_HOLD: str = "_p04_applied_hold"

# ══════════════════════════════════════════════════════════════════
# 按鈕與葉的顯示名
# ══════════════════════════════════════════════════════════════════
#: ⚠️ **交接事項（與頁 2／頁 3 同一項）**：`shared/ia_nav.py` 目前**沒有**第 4 頁的
#: `ACTION_*` 登錄（實測 2026-09-07：`ACTION_LABELS` 只有 `update_today`）。
#: 本檔的折衷是**在本檔內只定義一次**，按鈕與指路句**都讀同一個常數**。
#: → 應在 `shared/ia_nav.py` 補 `ACTION_RUN_WARROOM`，本檔改為讀它。
#: （`SECTION_HOLD_PORTFOLIO_SETUP` 已經在 `ia_nav` 裡，指路句一律走它。）
ACTION_RUN_WARROOM_LABEL: str = "🚀 跑存股戰情室"

#: 葉名（線框 `PAGES[3].leaves` 逐字）。
LEAF_WARROOM_TITLE: str = "戰情室（1️⃣~6️⃣ ＋ 80/20 配置偏離）"
LEAF_SETUP_TITLE: str = "組合設定（＝組合管理＋Sheet 綁定）"

_OPEN, _CLOSE = "「", "」"


def press(label: str) -> str:
    """`'按「🚀 跑存股戰情室」'` —— 指路句的唯一組法。"""
    return f"按{_OPEN}{label}{_CLOSE}"


#: 表單所在的分區（指路句用）。走 `ia_nav`，**不手抄頁名**。
SETUP_WHERE: str = ia_nav.where_to_find(ia_nav.SECTION_HOLD_PORTFOLIO_SETUP)

# ══════════════════════════════════════════════════════════════════
# 表單選項（**版面／取數範圍參數，不是門檻** —— 故不進 `shared/*_thresholds.py`）
# ══════════════════════════════════════════════════════════════════
#: 只讀不需要 Google 授權的市場端資料（VIX / 總經位階 / 建議持股水位）。
SCOPE_MARKET: str = "market"
#: 額外向 Google Sheets **讀一次**綁定狀態（唯讀：有沒有登入、有沒有綁、有幾本組合）。
SCOPE_WITH_BINDING: str = "with_binding"
SCOPE_LABELS: dict[str, str] = {
    SCOPE_MARKET: "只讀市場端（不連 Google）",
    SCOPE_WITH_BINDING: "加讀 Google Sheet 綁定狀態（唯讀，不寫入）",
}
SCOPE_OPTIONS: tuple[str, ...] = (SCOPE_MARKET, SCOPE_WITH_BINDING)

# ══════════════════════════════════════════════════════════════════
# 兩套刻度（線框 ②）—— 讀 L0 規格表，**本檔不描述任何門檻數字**
# ══════════════════════════════════════════════════════════════════
#: 本頁「健檢」欄那一套刻度背後的燈（ETF 四盞健檢 ＋ 個股汰換那一盞）。
#: `swap_level` 就是個股列的「健檢」欄（L3 `stock_row_from_assessment` 明寫
#: 「`健檢` 欄復用 swap_level」）。
HOLD_SCALE_SPEC_KEYS: tuple[str, ...] = (
    KEY_HEALTH_A, KEY_HEALTH_B, KEY_HEALTH_C, KEY_HEALTH_D, KEY_STOCK_SWAP,
)
#: 上面那一套的**輸入**（不直接顯示，但會決定它的等級）。
#: L2 `assess_stock`：grade 尚可但財報趨勢 `is_breakdown` → 提前判 🟡。
#: → 輸入失準，輸出就跟著失準；判 degraded 時**必須連輸入一起看**。
HOLD_SCALE_INPUT_SPEC_KEYS: tuple[str, ...] = (
    KEY_STOCK_HEALTH, KEY_STOCK_TREND, KEY_STOCK_KD,
)
#: 「🔬 查一檔」那一套刻度背後的燈（財報體檢綜合分 0-100 ＋ 等第）。
INSPECT_SCALE_SPEC_KEYS: tuple[str, ...] = (KEY_STOCK_HEALTH,)

#: 兩套刻度各自「長什麼樣」的一句話。**不是門檻**（門檻由 L0 的
#: `StationSpec.threshold_text` 供給），是**值域的形狀** —— 而值域形狀正是
#: 「不可互比」的理由：一個是序數燈號、一個是連續分數。
HOLD_SCALE_SHAPE: str = "序數燈號 ⚪ / 🟢 / 🟡 / 🔴（四盞燈取最嚴重，**沒有分數**）"
INSPECT_SCALE_SHAPE: str = "連續分數 0–100 ＋ 等第（**沒有燈號**）"

# ══════════════════════════════════════════════════════════════════
# 文案常數（一句話只准寫一次 —— 手抄多份，改的時候一定會漏改）
# ══════════════════════════════════════════════════════════════════
#: 例外的**出處**。做法沿用頁 1／2／3：不共用 `tab_today.upstream_error_why()`，
#: 因為那支的文案寫死「讀 **L3 canonical 契約**時拋出例外」，
#: 拿它去包別的層等於**對使用者謊報出事的層**。
#: ⚠️ 洗掉狀態 glyph 那一步**仍然走對面的 SSOT** `scrub_state_glyphs()`。
SRC_BINDING: str = (
    "L3 綁定狀態（`services.portfolio_binding_service.get_binding_state`）")
SRC_VIX: str = "L3 VIX（`services.dividend_station_service.fetch_vix`）"
SRC_MACRO: str = (
    "L3 總經位階（`services.dividend_station_service.get_station_macro`）")
SRC_ALLOC: str = "L3 建議持股水位（`services.allocation_service.get_allocation`）"
SRC_RENDER: str = "本頁的渲染層（`views/_ui_kit.render_card`）"

UNKNOWN_ERROR_TEXT: str = "（上游沒有給訊息）"

#: 冷啟動三要素（線框葉1 ① 的 `greyCells` 原文就是三格「⬜ 尚未執行」）。
IDLE_NOW: str = "**尚未執行**"
IDLE_WHY: str = (
    "戰情室的每一盞燈都以「你實際持有什麼」為輸入；"
    "在你送出之前，本頁**一次 L3 取數都不會發**（沒有人叫過它）")
IDLE_WHERE: str = f"到{SETUP_WHERE}，{press(ACTION_RUN_WARROOM_LABEL)}"

#: 選了「只讀市場端」時，Google 那兩張卡的三要素。**這不是故障，是你選的。**
BINDING_NOT_ASKED_NOW: str = "**這一輪沒有讀 Google Sheet 綁定狀態**"
BINDING_NOT_ASKED_WHY: str = (
    "你這一輪選的是"
    f"「{SCOPE_LABELS[SCOPE_MARKET]}」—— 本頁因此**真的沒有發那一次網路呼叫**，"
    "不是發了失敗，也不是拿上一輪的殘留頂替")
BINDING_NOT_ASKED_WHERE: str = (
    f"到{SETUP_WHERE}把選項改成"
    f"「{SCOPE_LABELS[SCOPE_WITH_BINDING]}」，再{press(ACTION_RUN_WARROOM_LABEL)}")

#: **持股清單未接線** —— 本頁六個區塊的共同根因。
#: 每一張卡的 `where` 都**在這一句之外再加自己那一段**（見各 builder），
#: 因為它們卡住的位置不同：有的只差第一步，有的連運算的 L3 都還沒有。
HOLDINGS_WHY: str = (
    "本頁一律走 L3，而 `src/services/` 底下**沒有任何一支**回傳"
    "「你持有哪幾檔、各幾張、均價多少」（實測量測日 2026-09-07）。"
    "唯一產得出那份清單的是既有 🏦 ETF 分頁裡的 L5 私有函式，"
    "它直接取用 L1 gsheet 的私有 accessor —— 跨層直取私有符號是分層違憲"
    "（`CLAUDE.md §8.2.A.2` V-PICKER-PRIV-1），"
    "經別的 UI 檔 re-export 繞道只是騙過靜態檢查、不改變性質")
HOLDINGS_WHERE_PREFIX: str = (
    f"{NO_EXIT_MARKER} —— 這是待接線項，不是你操作的問題；"
    f"{press(ACTION_RUN_WARROOM_LABEL)}也不會改變它。要接上需先在 `src/services/` "
    "補一支**唯讀**的 L3 holdings loader（回 "
    "`[{'ticker','name','held','asset_kind','asset_class','lots','avg_price'}, …]`），")

#: 唯讀邊界：需要**寫入**才做得到的功能。**不是缺 L3，是缺授權。**
READONLY_WHY: str = (
    "這一項本質上是**寫入**（會改到你 Google Sheet 裡的內容），"
    "而本頁對你的持股帳本**一律唯讀** —— 本批不實作任何寫入路徑，"
    "也不在畫面上放一顆按了會改資料的鈕")
READONLY_WHERE: str = (
    f"{NO_EXIT_MARKER}（本頁刻意沒有這個出口）—— "
    "現行入口仍在既有的 📁 組合管理分頁；"
    "要在本頁做，必須先由客戶拍板「這一頁可以寫入」，"
    "再補一支寫入型 L3 並補上二次確認與失敗回報")

#: 表單下方常駐的接線揭露（**不隨狀態消失**）。
WIRING_DISCLOSURE: str = (
    "**取數接線揭露**：本頁已接線的只有四項 —— Google Sheet **綁定狀態**、"
    "**VIX**、**總經位階**、**建議持股水位**，四項全部唯讀。"
    "**戰情室的七個區塊主體全部未接線**，根因只有一個："
    "`src/services/` 沒有回傳持股清單的 L3 介面。"
    "運算那一端其實已經齊了（燈牆、換股、80/20、停利、AI 摘要都有 L3）——"
    "**缺的是把清單餵進去的那第一步**。"
    "未接線的卡會標「未接線」並各自寫明要補在哪，不會拿空白冒充結果。")

#: 唯讀宣告（常駐，與接線揭露並列）。
READONLY_DISCLOSURE: str = (
    "**唯讀宣告**：本頁**只讀不寫** —— 不新增、不修改、不刪除你 Google Sheet 裡的"
    "任何一列持股，也不會在畫面上顯示 Sheet 識別碼或任何憑證"
    "（只顯示「有沒有綁」這件事）。"
    "需要寫入才做得到的功能（選 Sheet、管理觀察清單）在本頁一律標「未接線」。")


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
class HoldRequest:
    """使用者**已送出**的那一輪。`submitted` 是本頁的第 1 個 gate 旗標。

    Attributes:
        submitted: `SS_APPLIED_HOLD` 這個 key 存不存在。
            **只有 submit handler 會寫它** —— 這是「有沒有人叫過」的事實，
            不是從結果反推的（L0 `shared/ui_state.py` 的鐵律）。
        mode: 已套用的範圍（`SCOPE_*`）。
    """

    submitted: bool
    mode: str = SCOPE_MARKET

    @property
    def wants_binding(self) -> bool:
        """這一輪要不要向 Google 讀綁定狀態。**本頁的第 2 個 gate。**

        ⚠️ 它是**使用者的選擇**，不是資料的性質 —— 所以它是合法的 gate 來源。
        """
        return self.submitted and self.mode == SCOPE_WITH_BINDING


def applied_hold_request(session: Mapping[str, Any]) -> HoldRequest:
    """讀**已套用值**（鐵律 2）。widget 當下值一律不讀。

    邊界：key 不存在 → `submitted=False`（冷啟動）。
    key 存在但形狀怪（被別人覆寫、或舊版殘留）→ 仍算「送出過」，
    範圍退回最保守的 `SCOPE_MARKET`（**不猜使用者要連 Google**）。
    """
    if SS_APPLIED_HOLD not in session:
        return HoldRequest(submitted=False)
    _applied = session.get(SS_APPLIED_HOLD)
    if not isinstance(_applied, Mapping):
        return HoldRequest(submitted=True)
    _mode = str(_applied.get("mode") or SCOPE_MARKET)
    return HoldRequest(
        submitted=True,
        mode=_mode if _mode in SCOPE_LABELS else SCOPE_MARKET)


# ══════════════════════════════════════════════════════════════════
# ② 兩套刻度（線框葉1 ②）—— **零 I/O**，只讀 L0 規格表
# ══════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class ScaleRow:
    """一套刻度裡的一盞燈（給揭露表用）。全部欄位原樣取自 L0 `StationSpec`。"""

    key: str
    label: str
    threshold_text: str
    source: str
    discriminative: bool = True
    degraded_reason: str = ""


@dataclass(frozen=True)
class ScaleDisclosure:
    """線框 ② 的資料：兩套刻度各自的定義、門檻、以及**有沒有一側已失準**。

    Attributes:
        hold_rows: 本頁「健檢」那一套（含它的輸入燈）。
        inspect_rows: 「🔬 查一檔」的「健康度」那一套。
        degraded: 兩側任一盞燈在 L0 標了 `discriminative=False`。
        degraded_notes: `(哪一盞, L0 給的 degraded_reason)`，**原文透傳**。
        error: 讀規格表本身出錯（理論上不會，但 §1 不假設）。
    """

    hold_rows: tuple[ScaleRow, ...] = ()
    inspect_rows: tuple[ScaleRow, ...] = ()
    degraded_notes: tuple[tuple[str, str], ...] = ()
    error: str = ""

    @property
    def degraded(self) -> bool:
        return bool(self.degraded_notes)

    @property
    def has_rows(self) -> bool:
        return bool(self.hold_rows and self.inspect_rows)


def _scale_rows(keys: Sequence[str]) -> tuple[ScaleRow, ...]:
    """spec key → `ScaleRow`。查無此 key **直接跳過**，不編一個假的出來。

    ⚠️ 跳過是安全的、也是唯一誠實的：`SPECS_BY_KEY` 是 L0 的 SSOT，
    key 不在裡面代表**規格表改過而本檔沒跟上** —— 這時補一列「（不明）」
    會讓使用者以為那盞燈存在。少一列，加上 `has_rows` 的判定，
    比多一列假的好。
    """
    _out: list[ScaleRow] = []
    for _k in keys:
        _spec = SPECS_BY_KEY.get(_k)
        if _spec is None:
            print(f"[views/page_hold] 規格表沒有 {_k!r} —— 兩套刻度揭露少一列")
            continue
        _out.append(ScaleRow(
            key=_k,
            label=str(getattr(_spec, "label", "") or _k),
            threshold_text=str(getattr(_spec, "threshold_text", "") or ""),
            source=str(getattr(_spec, "source", "") or ""),
            discriminative=bool(getattr(_spec, "discriminative", True)),
            degraded_reason=str(getattr(_spec, "degraded_reason", "") or "")))
    return tuple(_out)


def build_scale_disclosure() -> ScaleDisclosure:
    """線框 ② 的資料來源。**零 I/O、零 L3** —— 只讀 L0 的 `@dataclass` 常數表。

    因為零 I/O，它**不需要 gate**（線框原文：「揭露常駐，不隨載入狀態消失」）。

    ⚠️ `degraded` 是**算出來的，不是寫死的**：任一側的燈在 L0 標了
    `discriminative=False` 就成立。實測（量測日 2026-09-07）成立的那一盞是
    財報趨勢 —— 它是本頁個股「健檢」欄的輸入之一。旗標若被改回 `True`，
    這張卡會自己回到 live。
    """
    try:
        _hold = _scale_rows(HOLD_SCALE_SPEC_KEYS + HOLD_SCALE_INPUT_SPEC_KEYS)
        _inspect = _scale_rows(INSPECT_SCALE_SPEC_KEYS)
    except Exception as _e:  # noqa: BLE001 — 轉成紅卡，不吞
        print(f"[views/page_hold] 規格表讀取失敗 → 兩套刻度揭露轉紅態：{_e!r}")
        return ScaleDisclosure(error=repr(_e))
    _notes = tuple(
        (_r.label, _r.degraded_reason)
        for _r in (_hold + _inspect) if not _r.discriminative)
    return ScaleDisclosure(hold_rows=_hold, inspect_rows=_inspect,
                           degraded_notes=_notes)


# ══════════════════════════════════════════════════════════════════
# 已接線的四支 L3（**全部唯讀**）
# ══════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class VixReadout:
    """VIX 那一輪的 L3 產出（線框 ③ 的「＋ VIX」那一半）。

    Attributes:
        requested: 由 `HoldRequest.submitted` 帶下來（**不是**從 `vix` 反推）。
        vix: 最新 VIX 收盤。`None` = L3 這一輪拿不到（**不是 0**）。
        error: 呼叫期例外 `repr(e)`；空字串 = 沒有錯誤。

    ⚠️ L3 `fetch_vix()` 的契約是「抓不到 → `None`」（它自己吞掉網路例外並印 log）。
    所以本頁看得到的 `error` 只會是 **late import 失敗**那一類。
    這代表：**「VIX 抓不到」在本頁一律是灰的 `empty`，不是紅的 `failed`** ——
    那是 L3 說的，不是本頁判的，本檔不去替它加一種它沒有的區分。
    """

    requested: bool
    vix: float | None = None
    error: str = ""


def load_vix(req: HoldRequest) -> VixReadout:
    """VIX。**`req.submitted` 為 False 時一行 L3 都不呼叫。**"""
    if not req.submitted:
        return VixReadout(requested=False)
    try:
        from src.services.dividend_station_service import fetch_vix
        _v = fetch_vix()
    except Exception as _e:  # noqa: BLE001 — 轉成紅態顯示，不吞
        print(f"[views/page_hold] VIX 取數失敗 → 轉紅態：{_e!r}")
        return VixReadout(requested=True, error=repr(_e))
    return VixReadout(requested=True, vix=_num(_v))


@dataclass(frozen=True)
class MacroReadout:
    """總經位階那一輪的 L3 產出（線框 ④ 的「搭配總經位階」那一半）。

    Attributes:
        requested: 由 `HoldRequest.submitted` 帶下來。
        loaded: 總經**這一輪有沒有被評估過**。`False` → 依規則**不以「中性」代替**
            （線框 ④ degraded 原文：「不猜多空」）。
        regime / light / health / posture_label / posture_range: L3 原樣透傳。
        error: 呼叫期例外。
    """

    requested: bool
    loaded: bool = False
    regime: str = ""
    light: str = ""
    health: float | None = None
    defense: bool | None = None
    posture_label: str = ""
    posture_range: str = ""
    error: str = ""


def load_macro(req: HoldRequest) -> MacroReadout:
    """總經位階。**`req.submitted` 為 False 時一行 L3 都不呼叫。**

    邊界：
      (a) **冷啟動** → `requested=False` → idle。
      (b) **L3 拋例外**（含 late import 失敗）→ 紅態。
      (c) **回來了但 `loaded=False`** → `empty`（灰）——「總經本輪未評估」是一個
          **有效的結果**，不是故障；而且**不得**拿「中性」頂替（§1）。
    """
    if not req.submitted:
        return MacroReadout(requested=False)
    try:
        from src.services.dividend_station_service import get_station_macro
        _m = get_station_macro()
    except Exception as _e:  # noqa: BLE001 — 轉成紅態顯示，不吞
        print(f"[views/page_hold] 總經位階取數失敗 → 轉紅態：{_e!r}")
        return MacroReadout(requested=True, error=repr(_e))
    _m = _m if isinstance(_m, Mapping) else {}
    _defense = _m.get("defense")
    return MacroReadout(
        requested=True,
        loaded=bool(_m.get("loaded")),
        regime=str(_m.get("regime") or ""),
        light=str(_m.get("light") or ""),
        health=_num(_m.get("health")),
        defense=bool(_defense) if isinstance(_defense, bool) else None,
        posture_label=_clean_signal(_m.get("posture_label")),
        posture_range=str(_m.get("posture_range") or ""))


@dataclass(frozen=True)
class AllocationReadout:
    """建議持股水位那一輪的 L3 產出（全站唯一的持股水位 SSOT）。

    ⚠️ **本頁一個百分比都不寫死。** `range_text` / `posture` 全部由 L3 的
    `AllocationDecision` 供給（`tests/test_no_hardcoded_position_pct.py`
    守著這條：任何 UI 檔寫死持股百分比就 CI 紅燈）。

    Attributes:
        requested: 由 `HoldRequest.submitted` 帶下來。
        is_loaded: 總經有沒有評估過。`False` → L3 的 `final_*` 全是 `None`，
            畫面**必須誠實顯示未評估**，不得填一個看起來合理的區間。
        range_text: L3 自己格式化好的區間字串（**原樣透傳，本檔不重排版**）。
        posture / cap_name / drivers / conflicts: L3 原樣透傳。
        error: 呼叫期例外。
    """

    requested: bool
    is_loaded: bool = False
    range_text: str = ""
    posture: str = ""
    cap_name: str = ""
    drivers: tuple[str, ...] = ()
    conflicts: tuple[str, ...] = ()
    error: str = ""


def load_allocation(req: HoldRequest) -> AllocationReadout:
    """建議持股水位。**`req.submitted` 為 False 時一行 L3 都不呼叫。**

    ⚠️ 這一支是本頁**唯一**會寫到 `st.session_state` 的下游 —— L3 內部的
    記憶化快取鍵（`_ALLOC_CACHE_KEY` / `_ALLOC_SIG_KEY`）。那是 session 內的
    計算快取，**不碰 Google Sheets、不碰任何使用者資產**。檔頭已揭露。
    """
    if not req.submitted:
        return AllocationReadout(requested=False)
    try:
        from src.services.allocation_service import get_allocation
        _a = get_allocation()
    except Exception as _e:  # noqa: BLE001 — 轉成紅態顯示，不吞
        print(f"[views/page_hold] 建議持股水位取數失敗 → 轉紅態：{_e!r}")
        return AllocationReadout(requested=True, error=repr(_e))
    return AllocationReadout(
        requested=True,
        is_loaded=bool(getattr(_a, "is_loaded", False)),
        range_text=str(getattr(_a, "range_text", "") or ""),
        posture=_clean_signal(getattr(_a, "posture", "")),
        cap_name=str(getattr(_a, "cap_name", "") or ""),
        drivers=tuple(str(_d) for _d in (getattr(_a, "drivers", ()) or ())),
        conflicts=tuple(str(_c) for _c in (getattr(_a, "conflicts", ()) or ())))


@dataclass(frozen=True)
class BindingReadout:
    """Google Sheet 綁定狀態（線框葉2）。**唯讀，而且不攜帶 sheet id。**

    ⚠️ **這個 dataclass 刻意沒有 `sheet_id` 欄位。** L3 的 `BindingState` 有，
    但那是 Google Sheet 的識別碼 —— 把它帶進 UI 層，遲早有人「順手」印出來
    當作除錯資訊。**結構上不讓它進來**，比寫一句「記得不要印」可靠。
    本頁只需要一個布林：**有沒有綁**。

    Attributes:
        requested: 「有人叫過」＋「這一輪選了要讀 Google」兩件事的合取。
        submitted: 表單**有沒有被送出過**（不參與任何 `classify_ui_state` 判定）。
            只用來分流 `idle` 的**文案**：冷啟動要你去按那顆鈕，
            「按了但選了不讀 Google」要你去改選項 —— 兩者都是 `idle`，
            但指路句完全不同，用同一句會對其中一半的人指錯路。
        logged_in / sheet_bound: 兩個布林。**沒有識別碼。**
        status: L3 的三態字串（`unbound` / `bound_empty` / `bound`），原樣透傳。
        count_requested: **第二張卡的 gate** —— 只有「已經綁到一本」時，
            「那本裡有幾本組合」這個問題才有人問過。沒綁 → 那張卡是 `idle`。
        portfolio_count: 組合本數。`None` = 未知（L3 契約：未綁 or 讀取失敗，
            **不腦補 0**）。
        count_missing_reason: `portfolio_count is None` 時要用哪個 L0 缺值原因。
            綁了卻讀不到 → `MISS_FETCH_FAILED`（L0 會把它升成**紅色**，
            因為那是「系統真出錯」被 L3 降級成中性回來的）；其餘 → 空。
        error: 呼叫期例外。
    """

    requested: bool
    submitted: bool = False
    logged_in: bool = False
    sheet_bound: bool = False
    status: str = ""
    count_requested: bool = False
    portfolio_count: int | None = None
    count_missing_reason: str = ""
    error: str = ""

    @property
    def count_gate(self) -> bool:
        """第二張卡真正用的 gate。**`count_requested` ∪「問到一半炸掉」。**

        ⚠️ **為什麼不是直接用 `count_requested`**（實測抓到的，不是理論）：
        整支 L3 拋例外時，我們**確實問過**「那本裡有幾本組合」（那個問題包在
        同一次讀取裡），只是它炸了。若這時 gate 是 False，第二張卡就會拿到
        「`requested=False` 卻帶 `error`」—— L0 當場 `ValueError`（§1 Fail Loud），
        **整頁變成未捕捉例外**。

        ⚠️ **這不違反「gate 不得從資料反推」**：`error` 不是資料，它是
        「這次請求發生了什麼事」。L0 自己就把 `requested=False` ＋ `error`
        列為矛盾組合並拒收 —— 也就是說 L0 的模型裡「有錯誤」蘊含「問過了」。
        本屬性只是把那條蘊含寫出來，不是拿結果去猜有沒有人問。
        """
        return bool(self.count_requested or (self.requested and self.error))

    @property
    def has_portfolios(self) -> bool:
        """**「0 本」不算「有值」。**

        ⚠️ 這一條容易寫反。`portfolio_count == 0` 確實是一次**成功的量測**，
        但把它畫成 `live` ＋ 一顆綠色「運作中」的 chip，讀起來是
        「一切正常，你有 0 本組合」—— 那在視覺上宣稱了一份健康的讀數，
        而下游其實**什麼都沒有可以算**。L0 對 `empty` 的定義正是
        「叫過了、沒錯、就是沒值」，0 本剛好就是那個意思。

        ⚠️ 它與 `None`（未知）**仍然分得開**：兩者 `has_value` 都是 False，
        但 `None` 會帶 `MISS_FETCH_FAILED` 被 L0 升成**紅色**，`0` 不帶原因、
        留在**灰色**。狀態機分得開，文案也各寫各的（見
        `build_portfolio_count_card`）。
        """
        return bool(self.portfolio_count)


def load_binding(req: HoldRequest) -> BindingReadout:
    """Google Sheet 綁定狀態。**`req.wants_binding` 為 False 時一行 L3 都不呼叫。**

    路徑：L3 `services.portfolio_binding_service.get_binding_state()` ——
    它的 docstring 自陳「**純讀不寫**」。

    邊界（四種，全部走得到，而且**一種都不可以混**）：
      (a) **沒按 / 這一輪選了不讀 Google** → `requested=False` → 兩張卡都 idle。
      (b) **讀了，未登入或沒綁 Sheet** → `sheet_bound=False` → 第一張卡 `empty`
          （**有效結果**：你確實還沒綁），第二張卡 `idle`
          （沒有那一本，就沒有人問過「那本裡有幾本」）。
      (c) **讀了，綁到了** → 第一張卡 `live`；第二張卡看本數：
          `0` → `empty`（**綁好了但還沒填內容，這不是故障**）；
          `None` → `MISS_FETCH_FAILED` → L0 升成 **`failed`（紅）** ——
          L3 為了不擋住全域狀態列，把「讀組合清單失敗」降級成中性的
          `status=bound` + `count=None`；本頁**把那個被吞掉的失敗還原成紅色**，
          因為在這一頁它就是「系統真出錯」。
      (d) **L3 自己拋例外** → 兩張卡都 `failed`。
    """
    if not req.wants_binding:
        return BindingReadout(requested=False, submitted=req.submitted)
    try:
        from src.services.portfolio_binding_service import (
            STATUS_BOUND,
            STATUS_UNBOUND,
            get_binding_state,
        )
        _s = get_binding_state()
    except Exception as _e:  # noqa: BLE001 — 轉成紅態顯示，不吞
        print(f"[views/page_hold] 綁定狀態讀取失敗 → 轉紅態：{_e!r}")
        # ⚠️ `count_requested=True` 是必要的，不是順手填的：這一輪確實**問過**
        #    「那本裡有幾本組合」（問題包在同一次讀取裡），只是整支炸了。
        #    填 False 會讓第二張卡拿到「requested=False 卻帶 error」——
        #    L0 會當場 `ValueError`（§1 Fail Loud），整頁變成未捕捉例外。
        return BindingReadout(requested=True, submitted=req.submitted,
                              count_requested=True, error=repr(_e))

    _status = str(getattr(_s, "status", "") or "")
    _bound = bool(_status and _status != STATUS_UNBOUND)
    _count = getattr(_s, "portfolio_count", None)
    _count = _count if isinstance(_count, int) and not isinstance(_count, bool) else None
    # 綁了卻拿不到本數 = L3 把一次真失敗降級成中性回來 → 在本頁還原成紅色。
    _reason = (MISS_FETCH_FAILED
               if (_bound and _count is None and _status == STATUS_BOUND) else "")
    return BindingReadout(
        requested=True,
        submitted=req.submitted,
        logged_in=bool(getattr(_s, "logged_in", False)),
        sheet_bound=_bound,
        status=_status,
        count_requested=bool(req.wants_binding and _bound),
        portfolio_count=_count,
        count_missing_reason=_reason)


def _num(value: Any) -> float | None:
    """任何東西 → float，或 `None`。**不猜 0**（§1：0 是一個結論，不是缺值）。"""
    if value is None or isinstance(value, bool):
        return None
    try:
        _f = float(value)
    except (TypeError, ValueError):
        return None
    if _f != _f:        # NaN
        return None
    return _f


def _fmt_num(value: float | None, *, digits: int = 1, unit: str = "") -> str:
    """數值 → 顯示字串。`None` → `'—'`，**不寫 0**（§1 不假報）。"""
    return "—" if value is None else f"{value:.{digits}f}{unit}"


def _clean_signal(text: Any) -> str:
    """L3 來的字串 → 可以放進訊號頻道／結論欄的**純中文標籤**。

    ⚠️ **為什麼需要它**：L3 `get_station_macro()` 的 `posture_label` 形狀是
    `f"{icon} {posture}"`（例如「🟢 積極」），`AllocationDecision.posture` 未來
    也可能長出 icon。那個 emoji 撞上狀態頻道自己的 glyph 就是 `_ui_kit` 檔頭
    鐵律 3 講的「**兩個紅撞在一起**」—— 同一張卡出兩個符號等於沒有資訊。

    ⚠️ **禁用字面集合走共用層的 SSOT** `_ui_kit.banned_signal_glyphs()`
    （＝ L0 狀態 glyph ∪ L0 燈號 emoji 的聯集），**本檔不自己列一份**。
    這裡是**過濾**而不是 `assert_signal_text_clean()` 的 raise：上游字串不是
    本頁寫的，為了一個 emoji 讓整頁炸掉不是 §1 要的「紅態看得見」。
    """
    _out = str(text or "")
    for _g in banned_signal_glyphs(_out):
        _out = _out.replace(_g, "")
    return _out.strip()


# ══════════════════════════════════════════════════════════════════
# 卡片建構（純函式；`Card` / `Note` 的驗證在對面，本檔不重複）
# ══════════════════════════════════════════════════════════════════
#: 一張卡回傳的形狀：`(Card, facts, signal_text)`。
#: `signal_text` 是**訊號頻道的中文標籤**（鐵律 3：帶 emoji 會被
#: `_ui_kit.assert_signal_text_clean()` 當場 raise）。
_Built = tuple[Card, tuple[tuple[str, str], ...], str]


@dataclass(frozen=True)
class UnwiredSpec:
    """一張未接線卡的全部文案。**每一張都必須有自己的 `why` 與 `where`。**

    ⚠️ 為什麼要一個 dataclass 而不是六組 if：本頁未接線的卡有 **17 張**，
    共用一句「未接線」會讓使用者以為它們卡在同一步 —— 實際上不是：
    ① 只差把清單餵進去（運算的 L3 已經在了）、
    ⑥ 的再平衡連運算的 L3 都還沒有、
    葉2 的 Sheet 選擇根本不是缺 L3 而是**缺授權**（本頁唯讀）。
    「去哪補」寫錯，比不寫更糟。
    """

    key: str
    label: str
    now: str
    why: str
    where: str
    facts: tuple[tuple[str, str], ...] = field(default_factory=tuple)


def build_unwired_card(requested: bool, spec: UnwiredSpec) -> _Built:
    """未接線卡的唯一建構器。

    `wired=False` → `classify_ui_state` 第 1 條規則直接判 `unwired`，
    **與請求與否無關**：未接線的東西不會因為多按一次而改變，
    這正是它與「查不到」必須分成兩態的原因。
    """
    _state = classify_ui_state(requested=requested, has_value=False,
                               wired=False)
    return (Card(key=spec.key, label=spec.label, state=_state,
                 note=Note(now=spec.now, why=spec.why, where=spec.where)),
            tuple(spec.facts), "")


def _holdings_where(tail: str) -> str:
    """未接線卡的「去哪補」＝ 共同前綴 ＋ **這一張自己**卡在哪。"""
    return HOLDINGS_WHERE_PREFIX + tail


# ── ① 結論（三張卡）───────────────────────────────────────────────
#: 線框 ① 的 `cells` 逐字：該做什麼 / 訊號可信度 / 需要處理。
CONCLUSION_SPECS: tuple[UnwiredSpec, ...] = (
    UnwiredSpec(
        key="hold.conclusion.action", label="該做什麼",
        now="**本頁還算不出「今天該做什麼」**",
        why=HOLDINGS_WHY,
        where=_holdings_where(
            "接上之後這一格走 L3 `compute_portfolio_totals()` ＋ "
            "`build_station_digest()` —— **兩支都已經在 `src/services/` 裡了**，"
            "只差把清單交給它們"),
        facts=(("接線後的樣子", "檔數 · 幾檔建議加碼 · 幾檔建議汰換"),
               ("運算的 L3", "已就緒（`dividend_station_service`）"),
               ("卡住的那一步", "持股清單沒有 L3 介面"))),
    UnwiredSpec(
        key="hold.conclusion.confidence", label="訊號可信度",
        now="**本頁還算不出「幾盞燈判得出來」**",
        why=HOLDINGS_WHY,
        where=_holdings_where(
            "接上之後這一格數的是 L3 每一列的 `_lights`（ETF 8 盞 / 個股 4 盞）"
            "裡**有判定**的比例 —— 逐盞燈的四態 L2 早就算好了"),
        facts=(("接線後的樣子", "N / M 盞已判定（分母隨持股檔數與成分變動）"),
               ("為什麼分母不寫死",
                "抓取失敗的列若整個不出現，分母會悄悄變小、可信度虛高 —— "
                "L2 `missing_light_cells()` 就是為了防這件事"))),
    UnwiredSpec(
        key="hold.conclusion.todo", label="需要處理",
        now="**本頁還列不出「有幾檔需要你處理」**",
        why=HOLDINGS_WHY,
        where=_holdings_where(
            "接上之後這一格讀 L3 `build_station_digest()` 的 `adds`（235 加碼觸發）"
            "與 `reds`（健檢紅燈需汰弱），兩者都已經是算好的欄位"),
        facts=(("接線後的樣子", "加碼 N · 減碼 N · 未判 N"),
               ("⚠️ 線框的紅態是另一件事",
                "線框這一格的 `errCells` 是「讀不到持股清單」的**紅**態 —— "
                "那要等接線之後才會出現（讀得到才有得失敗）；"
                "現在是**未接線**，兩者不同"))),
)


def build_conclusion_cards(requested: bool) -> tuple[_Built, ...]:
    """線框葉1 ①「結論（三張卡）」—— 本批**三張全部未接線**。

    ⚠️ **三張各有自己的 `where`**：它們接線後讀的是不同的 L3 產出
    （組合彙總 / 逐盞燈四態 / digest 的 adds+reds）。共用一句話會讓
    「補哪一支就會好」這個資訊消失。
    """
    return tuple(build_unwired_card(requested, _s) for _s in CONCLUSION_SPECS)


# ── ② 同一個名詞，兩套刻度 ────────────────────────────────────────
SCALE_LIVE_VALUE: str = "兩套刻度並存 —— 不可互比"
SCALE_DEGRADED_NOW: str = "**兩套刻度目前不一致，本頁不提供跨頁比較**"
SCALE_DEGRADED_WHERE: str = (
    "兩套刻度各自的出處與門檻**就在這張卡下面**，可以逐項對照；"
    f"更完整的說明在{ia_nav.where_to_find(ia_nav.PAGE_WHY)}")


def build_scale_card(disclosure: ScaleDisclosure) -> _Built:
    """線框葉1 ②「同一個名詞，兩套刻度」—— **常駐揭露，非摺疊**。

    線框 note 原文：「**v1 漏畫。**它是防「同名不同義」誤讀的唯一揭露 ——
    拿掉之後就會有人拿兩套刻度互比，而畫面不會攔他。」

    ⚠️ **`requested=True` 是字面常數，不是恆真式。** 這張卡的輸入是 L0 的
    `@dataclass(frozen=True)` 常數表，**沒有任何取數** —— 沒有「叫過 / 沒叫過」
    可言。寫成 `bool(rows)` 之類的東西才是頁 1 那種恆真式（假裝在判斷）。
    這裡誠實地寫「這個揭露永遠開著」。

    ⚠️ **`degraded` 由 L0 的 `discriminative` 旗標決定，本檔不寫死哪一盞。**
    """
    _state = classify_ui_state(
        requested=True,
        error=disclosure.error or None,
        has_value=disclosure.has_rows,
        reason=MISS_NO_INPUT,
        discriminative=(not disclosure.degraded))
    _facts: list[tuple[str, str]] = [
        ("💼 我的持股 › 戰情表「健檢」", HOLD_SCALE_SHAPE),
        ("🔬 查一檔 › 判決卡「健康度」", INSPECT_SCALE_SHAPE),
        ("為什麼不可互比",
         "一個是**序數**（🟢 只表示「比 🟡 好」，沒有距離），"
         "一個是**基數**（分數可以相減）—— "
         "拿 🟢 去對 80 分是把兩種不同的量測混成一個數字"),
    ]
    for _label, _reason in disclosure.degraded_notes:
        # L0 的 `degraded_reason` **原樣透傳**（§2.1：那是 L0 的話，本檔不改寫）。
        _facts.append((f"⚠️ 已失準：{_label}", _reason))

    if _state == UI_LIVE:
        return (Card(key="hold.scales", label="同一個名詞，兩套刻度",
                     state=UI_LIVE, value=SCALE_LIVE_VALUE),
                tuple(_facts), "兩套並存")
    if _state == UI_FAILED:
        _note = Note(now="**兩套刻度的定義讀不出來**",
                     why=_error_why("L0 燈號規格表（`shared/station_specs.py`）",
                                    disclosure.error),
                     where=(f"{NO_EXIT_MARKER} —— 這是規格表本身的問題，"
                            "請把上面那行訊息回報給維護者"))
    elif _state == UI_IDLE:      # 結構上到不了（`requested` 是字面 True）。
        _note = Note(now=IDLE_NOW, why=IDLE_WHY, where=IDLE_WHERE)
    else:                        # degraded / empty 共用同一段說明。
        _note = Note(
            now=SCALE_DEGRADED_NOW,
            why=("其中一側的門檻來源在 L0 規格表標了 `discriminative=False`"
                 "（燈會亮、也有等級，只是**別照門檻讀**）—— "
                 "詳細原因見下方逐盞列表，那段文字是 L0 自己寫的，本頁沒有改寫"
                 if disclosure.degraded else
                 "L0 規格表這一輪沒有回傳可用的燈號定義"),
            where=SCALE_DEGRADED_WHERE)
    return Card(key="hold.scales", label="同一個名詞，兩套刻度",
                state=_state, note=_note), tuple(_facts), ""


# ── ③ 戰情表（燈牆 ＋ VIX）────────────────────────────────────────
LIGHTWALL_SPEC: UnwiredSpec = UnwiredSpec(
    key="hold.lightwall", label="燈牆（235 加碼燈 · 3-3-3 · 健檢四盞）",
    now="**燈牆點不亮**",
    why=HOLDINGS_WHY,
    where=_holdings_where(
        "接上之後這一格走 L3 `get_station_rows(holdings)` —— "
        "它會抓一次 VIX ＋ 逐檔指標並回一張表；"
        "點左表右側就地展開的那份週線與布林 z，也已經在每一列的 "
        "`_weekly_series` 鍵裡了"),
    facts=(("接線後的樣子", "逐檔 235 加碼燈 / 3-3-3 判定；點任一檔右側展開週線與布林 z"),
           ("⚠️ 線框的紅態是另一件事",
            "線框 ③ 的 err 是「已綁定的 Google Sheet 讀取失敗」—— "
            "那要等接線之後才會出現；現在是**未接線**"),
           ("運算的 L3", "已就緒（`dividend_station_service.get_station_rows`）")))


def build_lightwall_card(requested: bool) -> _Built:
    """線框葉1 ③ 的「燈牆」那一半 —— **本批未接線**。"""
    return build_unwired_card(requested, LIGHTWALL_SPEC)


def build_vix_card(vix: VixReadout) -> _Built:
    """線框葉1 ③ 的「＋ VIX」那一半 —— **已接線**。

    ⚠️ **VIX 拿不到是 `empty`（灰），不是 `failed`（紅）。** L3 `fetch_vix()`
    自己吞掉網路例外並回 `None`，它的 docstring 明寫「抓不到 → None
    （§1 不猜，235 該條件不觸發）」。本頁**不去替它加一種它沒有的區分** ——
    把「上游說沒有」畫成紅色故障，就是 v3 §02 要杜絕的假性錯誤。

    ⚠️ **門檻三段一律讀 L0**（`VIX_LIGHT1/2/3`），本檔不寫死數字。
    """
    _state = classify_ui_state(
        requested=vix.requested,
        error=vix.error or None,
        has_value=(vix.vix is not None))
    _facts: tuple[tuple[str, str], ...] = (
        ("235 加碼燈的 VIX 門檻",
         f"< {VIX_LIGHT1:g} 巡航　{VIX_LIGHT1:g}–{VIX_LIGHT2:g} 燈一　"
         f"{VIX_LIGHT2:g}–{VIX_LIGHT3:g} 燈二　≥ {VIX_LIGHT3:g} 燈三"),
        ("門檻出處", "L0 `shared/dividend_station_thresholds.py`（本頁不寫死）"),
        ("單位", "點數，**不是**百分比"),
    )
    if _state == UI_LIVE:
        return (Card(key="hold.vix", label="VIX（市場恐慌指數）",
                     state=UI_LIVE, value=_fmt_num(vix.vix, digits=2)),
                _facts, "")
    if _state == UI_IDLE:
        _note = Note(now=IDLE_NOW, why=IDLE_WHY, where=IDLE_WHERE)
    elif _state == UI_FAILED:
        _note = Note(
            now="**VIX 這一格畫不出來**",
            why=_error_why(SRC_VIX, vix.error),
            where=(f"{NO_EXIT_MARKER} —— 這不是取數失敗（L3 取不到時回的是"
                   "「沒有值」而不是例外），是那一支 L3 自己載不進來；"
                   "請把上面那行訊息回報給維護者"))
    else:   # UI_EMPTY
        _note = Note(
            now="**這一輪拿不到 VIX**",
            why=("**這是一個有效的結果**（已經去要過，不是還沒去要）—— "
                 "上游這一輪沒有回最新收盤。本站不拿舊值或 0 頂替："
                 "0 在 VIX 的刻度上是「市場完全無波動」，那是一個結論、不是缺值"),
            where=(f"稍後{press(ACTION_RUN_WARROOM_LABEL)}再試一次；"
                   "持續拿不到請到"
                   f"{ia_nav.where_to_find(ia_nav.SECTION_WHY_DATA_HEALTH)}"
                   "看 Yahoo 那一源的狀態"))
    return Card(key="hold.vix", label="VIX（市場恐慌指數）",
                state=_state, note=_note), _facts, ""


# ── ④ 換股建議（搭配總經位階）─────────────────────────────────────
SWITCH_SPEC: UnwiredSpec = UnwiredSpec(
    key="hold.switch", label="換股建議（該換）",
    now="**本頁還給不出換股建議**",
    why=HOLDINGS_WHY,
    where=_holdings_where(
        "接上之後這一格走 L3 `build_switch_advice(rows, macro, candidates)` ＋ "
        "`get_switch_in_candidates(regime=…, exclude=已持有代號)` —— **兩支都已經在了**"),
    facts=(
        ("接線後的樣子", "換出 N 檔（體質轉弱）→ 換入 N 檔（優先來自你的觀察清單）"),
        ("⚠️ 為什麼不先出「換入」那一半",
         "換入候選的 L3 已經可用，但它要 `exclude=你已持有的代號`；"
         "**少了那個輸入，它會叫你買你已經有的東西** —— "
         "那不是降級的建議，是錯的建議，所以本頁一半都不出"),
        ("與這一格互補的另一半", "⑤ 的 80/20 偏離回答「該減」，本格回答「該換」")))


def build_switch_card(requested: bool) -> _Built:
    """線框葉1 ④「換股建議」—— **本批未接線**（兩半都缺同一個輸入）。

    線框 note 原文：「**v1 漏畫 —— 而它正是本頁職責「該加、該換、該減」的
    那個「該換」。**」

    ⚠️ **刻意不出半個建議。** 線框把「未套用總經位階」設計成 `degraded`
    （有值、能看，只是少一個輸入，必須講出來）—— 那個設計的前提是
    **建議本身存在**。本頁連建議都產不出來（換出要持股、換入要 `exclude` 持股），
    所以是 `unwired` 而不是 `degraded`。**把 unwired 畫成 degraded 會讓使用者
    以為畫面上有一份「打了折的建議」可以看，實際上一個字都沒有。**
    """
    return build_unwired_card(requested, SWITCH_SPEC)


def build_macro_stage_card(macro: MacroReadout) -> _Built:
    """線框葉1 ④ 的「搭配總經位階」那一半 —— **已接線**。

    ⚠️ **`loaded=False` 是 `empty`（灰），不是 `failed`（紅），
    而且絕對不可以拿「中性」頂替。** 線框 ④ 的 degraded 文案原文：
    「總經本輪未評估，**依規則不以「中性」代替 —— 不猜多空**」。
    這一句是本頁對 §1 最直接的服從：多空是一個結論，缺值不是。
    """
    _state = classify_ui_state(
        requested=macro.requested,
        error=macro.error or None,
        has_value=macro.loaded)
    _facts: list[tuple[str, str]] = [
        ("這個位階會怎麼被用到",
         "接線後它是換股建議的**攻守閘門**：轉守 → 換入從嚴（少給候選）；"
         "未評估 → 只做汰弱、不套攻守"),
        ("來源", "L3 `get_station_macro()` —— 唯讀，不打 API"),
    ]
    if macro.regime:
        _facts.append(("regime", macro.regime))
    if macro.health is not None:
        _facts.append(("總經健康分", _fmt_num(macro.health, digits=0)))
    if macro.posture_range:
        _facts.append(("姿態油門帶", macro.posture_range))

    if _state == UI_LIVE:
        return (Card(key="hold.macro_stage", label="總經位階（換股的攻守閘門）",
                     state=UI_LIVE, value=macro.posture_label or macro.regime),
                tuple(_facts),
                "轉守" if macro.defense else ("已評估" if macro.loaded else ""))
    if _state == UI_IDLE:
        _note = Note(now=IDLE_NOW, why=IDLE_WHY, where=IDLE_WHERE)
    elif _state == UI_FAILED:
        _note = Note(now="**總經位階讀不出來**",
                     why=_error_why(SRC_MACRO, macro.error),
                     where=(f"{NO_EXIT_MARKER} —— 請把上面那行訊息回報給維護者；"
                            f"總經本身的狀態在"
                            f"{ia_nav.where_to_find(ia_nav.PAGE_TODAY)}"))
    else:   # UI_EMPTY
        _note = Note(
            now="**總經本輪未評估**",
            why=("**這是一個有效的結果**（已經去讀過，不是還沒讀）—— "
                 "本站**不以「中性」代替未評估**：多空是一個結論，缺值不是。"
                 "接線後的換股建議在這種情況下只做汰弱，不套攻守"),
            where=(f"到{ia_nav.where_to_find(ia_nav.PAGE_TODAY)}更新總經之後，"
                   f"回到本頁{press(ACTION_RUN_WARROOM_LABEL)}"))
    return Card(key="hold.macro_stage", label="總經位階（換股的攻守閘門）",
                state=_state, note=_note), tuple(_facts), ""


# ── ⑤ 80/20 配置偏離 ＋ 衛星停利 ──────────────────────────────────
#: ⚠️ 目標配置與停利門檻**一律讀 L0**（`CORE_TARGET_PCT` / `SATELLITE_TARGET_PCT` /
#: `SATELLITE_TAKE_PROFIT_PCT`），本檔一個數字都不寫死（§3.3 ＋
#: `tests/test_no_hardcoded_position_pct.py`）。
ALLOCATION_SPLIT_SPEC: UnwiredSpec = UnwiredSpec(
    key="hold.alloc_split", label="80/20 配置偏離（該減）",
    now="**本頁還算不出核心／衛星的實際配置**",
    why=HOLDINGS_WHY,
    where=_holdings_where(
        "接上之後這一格走 L3 `compute_allocation_split(rows)` —— "
        "它只納入**有市值**的持有列，缺張數／均價的會被排除並回 `partial=True`，"
        "呼叫端必須把「N 檔裡只算了 M 檔」講出來"),
    facts=(
        ("接線後的樣子", "核心 x% / 衛星 y%（目標見下一列），以及偏離幾個百分點"),
        ("目標（L0 SSOT）",
         f"核心 {CORE_TARGET_PCT:g}／衛星 {SATELLITE_TARGET_PCT:g}"),
        ("近似法的已知限制",
         "核心＝ETF、衛星＝個股是以代號型別近似；主題型 ETF 會被算成核心")))

TAKE_PROFIT_SPEC: UnwiredSpec = UnwiredSpec(
    key="hold.take_profit", label="衛星停利",
    now="**本頁還判不出哪幾檔達停利門檻**",
    why=HOLDINGS_WHY,
    where=_holdings_where(
        "接上之後這一格走 L3 `flag_take_profit(rows)` —— "
        "它只對**有損益%**的持有衛星列判；沒有成本就不判、不捏造"),
    facts=(
        ("接線後的樣子", "達門檻的衛星代號 ＋ 各自的損益%"),
        ("門檻（L0 SSOT）",
         f"衛星獲利達 {SATELLITE_TAKE_PROFIT_PCT:g} 個百分點即嚴格停利滾回核心"),
        ("為什麼缺成本就不判", "沒有均價就沒有損益%，硬判等於替你編一個報酬率")))


def build_allocation_split_card(requested: bool) -> _Built:
    """線框葉1 ⑤ 的「80/20 配置偏離」那一半 —— **本批未接線**。"""
    return build_unwired_card(requested, ALLOCATION_SPLIT_SPEC)


def build_take_profit_card(requested: bool) -> _Built:
    """線框葉1 ⑤ 的「衛星停利」那一半 —— **本批未接線**。"""
    return build_unwired_card(requested, TAKE_PROFIT_SPEC)


def build_position_cap_card(alloc: AllocationReadout) -> _Built:
    """線框葉1 ⑤ 的第三格：**市場端**的建議持股水位 —— **已接線**。

    ⚠️ 它與 80/20 **不是同一件事，不可互相取代**：
      · 80/20 問的是「你手上那一堆，核心與衛星各佔多少」（**組合內部**的比例）；
      · 本格問的是「以現在的總經與風控，整體該擺多少在股票上」（**市場端**的上限）。
    兩者都關係到「該減」，但分母不同。放在同一區塊是因為線框 ⑤ 的職責是「該減」，
    **不是**因為它們可以合併成一個數字。

    ⚠️ **本頁一個百分比都不寫死。** 區間文字由 L3 `AllocationDecision.range_text`
    原樣供給（`tests/test_no_hardcoded_position_pct.py` 守著這條）。
    """
    _state = classify_ui_state(
        requested=alloc.requested,
        error=alloc.error or None,
        has_value=alloc.is_loaded)
    _facts: list[tuple[str, str]] = [
        ("這個數字的分母",
         "**整體資產**（市場端上限），不是核心／衛星那個組合內部的比例"),
        ("來源", "全站唯一的建議持股 SSOT（L3 `get_allocation()`），本頁不自行再算"),
    ]
    if alloc.cap_name:
        _facts.append(("生效的天花板", alloc.cap_name))
    if alloc.drivers:
        _facts.append(("推導依據", "、".join(alloc.drivers)))
    if alloc.conflicts:
        # L3 明寫「與最終結論相反、但被壓制的訊號（**要顯示，不要藏**）」。
        _facts.append(("被壓制但仍要看見的反向訊號", "、".join(alloc.conflicts)))

    if _state == UI_LIVE:
        return (Card(key="hold.position_cap", label="建議持股水位（市場端）",
                     state=UI_LIVE, value=alloc.range_text or "—"),
                tuple(_facts), alloc.posture or "")
    if _state == UI_IDLE:
        _note = Note(now=IDLE_NOW, why=IDLE_WHY, where=IDLE_WHERE)
    elif _state == UI_FAILED:
        _note = Note(now="**建議持股水位讀不出來**",
                     why=_error_why(SRC_ALLOC, alloc.error),
                     where=(f"{NO_EXIT_MARKER} —— 請把上面那行訊息回報給維護者"))
    else:   # UI_EMPTY
        _note = Note(
            now="**總經未評估，本站不給建議水位**",
            why=("**這是一個有效的結果**：SSOT 的契約就是「未評估時 `final_*` 為 "
                 "`None`，畫面須誠實顯示未評估」。填一個看起來合理的區間，"
                 "等於替你做了一個沒有依據的決定"),
            where=(f"到{ia_nav.where_to_find(ia_nav.PAGE_TODAY)}更新總經之後，"
                   f"回到本頁{press(ACTION_RUN_WARROOM_LABEL)}"))
    return Card(key="hold.position_cap", label="建議持股水位（市場端）",
                state=_state, note=_note), tuple(_facts), ""


# ── ⑥ 組合深度分析（提升，不再埋 expander；區塊並列，各自 gate）──────
#: 線框 ⑥ `live` 原文逐字的六項。
#: ⚠️ **六項卡住的位置不同**（三種），所以 `where` 分成三類寫，不是六份複製：
#:   (a) 純函式在 L2、**連 L3 wrapper 都還沒有** → 再平衡 / 壓力測試 / VaR；
#:   (b) **L3 已經有**，只差持股 → 核心／衛星、配息現金流；
#:   (c) **實作在 L5**、自帶寫死的 widget key → 葡萄串領息。
DEEP_SPECS: tuple[UnwiredSpec, ...] = (
    UnwiredSpec(
        key="hold.deep.rebalance", label="再平衡",
        now="**再平衡未接線**", why=HOLDINGS_WHY,
        where=_holdings_where(
            "**並且**再補一支 L3 wrapper 轉發 L2 `compute.etf.etf_calc` 的再平衡計算"
            "（這一項與 ① / ③ 不同：連運算的 L3 都還沒有，不只是缺清單）"),
        facts=(("卡住的層", "L2 有純函式，**L3 沒有 wrapper**，L1 沒有清單"),)),
    UnwiredSpec(
        key="hold.deep.core_satellite", label="核心／衛星",
        now="**核心／衛星拆解未接線**", why=HOLDINGS_WHY,
        where=_holdings_where(
            "接上之後這一格與 ⑤ 共用同一支 L3 `compute_allocation_split(rows)`"),
        facts=(("卡住的層", "只差持股清單（L3 已就緒）"),
               ("與 ⑤ 的關係", "同一支 L3、不同呈現：⑤ 講偏離，這裡講組成"))),
    UnwiredSpec(
        key="hold.deep.stress", label="壓力測試",
        now="**壓力測試未接線**", why=HOLDINGS_WHY,
        where=_holdings_where(
            "**並且**再補一支 L3 wrapper 轉發 L2 "
            "`compute.etf.etf_calc.calc_portfolio_stress_test`"),
        facts=(("卡住的層", "L2 有純函式，**L3 沒有 wrapper**，L1 沒有清單"),)),
    UnwiredSpec(
        key="hold.deep.var", label="VaR",
        now="**VaR 未接線**", why=HOLDINGS_WHY,
        where=_holdings_where(
            "**並且**再補一支 L3 wrapper 轉發 L2 "
            "`compute.etf.etf_calc.compute_portfolio_vs_benchmark`（含權重對齊）"),
        facts=(("卡住的層", "L2 有純函式，**L3 沒有 wrapper**，L1 沒有清單"),)),
    UnwiredSpec(
        key="hold.deep.dividend_cash", label="配息現金流",
        now="**配息現金流未接線**", why=HOLDINGS_WHY,
        where=_holdings_where(
            "接上之後這一格走 L3 "
            "`dividend_tax_service.get_dividend_tax_view(holdings, marginal_rate=…)`"
            "—— **那一支已經在了**，它要的是 `[{'ticker', 'shares'}]`"),
        facts=(("卡住的層", "只差持股清單（L3 已就緒）"),
               ("接線後還要問你一件事",
                "綜所稅邊際稅率（不填 → 只算二代健保，不算綜所稅）"))),
    UnwiredSpec(
        key="hold.deep.grape", label="葡萄串領息",
        now="**葡萄串領息未接線**", why=HOLDINGS_WHY,
        where=_holdings_where(
            "**並且**先讓現行實作（L5 `tabs.grape_ladder`）能被外部重複掛載"
            "（widget key 加前綴參數、取數改走 L3、gate 由 caller 提供）——"
            "現在直接在本頁再掛一次會撞 `DuplicateWidgetID`"),
        facts=(("卡住的層", "實作在 L5、自帶寫死的 widget key"),
               ("現行入口", "既有的 🏦 ETF 分頁（本頁不重複掛載）"))),
)

#: 線框 ⑥ note 原文（**這是本區塊存在的理由，不是裝飾**）。
DEEP_CAPTION: str = (
    "線框 ⑥ 原文：現況埋在「5️⃣ 組合深度分析」expander 第五層。"
    "**expander 收合只是視覺收合、body 每次 rerun 照跑** —— 埋起來沒省效能，"
    "只是讓人找不到。改**並列 ＋ 各自 gate**（3 欄 × 2 排，不是一排六欄）。")


def build_deep_cards(requested: bool) -> tuple[_Built, ...]:
    """線框葉1 ⑥「組合深度分析」六項 —— 本批**六項全部未接線**。

    ⚠️ **六張的 `where` 分成三類、不是六份複製** —— 見 `DEEP_SPECS` 的註解。
    寫成同一句會讓「補哪一層才會好」這個資訊消失，而那正是這幾張卡唯一的價值。
    """
    return tuple(build_unwired_card(requested, _s) for _s in DEEP_SPECS)


# ── ⑦ AI 戰情總結（唯一推播出口）──────────────────────────────────
AI_SUMMARY_SPEC: UnwiredSpec = UnwiredSpec(
    key="hold.ai_summary", label="AI 戰情總結（唯一推播出口）",
    now="**本頁還生不出 AI 戰情總結**",
    why=HOLDINGS_WHY,
    where=_holdings_where(
        "接上之後這一格走 L3 `build_station_digest(rows, vix)` → "
        "`build_summary_prompt(digest, switch)` → "
        "`build_ai_summary(digest, gemini_fn)`，`gemini_fn` 由 L3 "
        "`app_ai_service.gemini_call` 注入 —— **四支全部都已經在了**"),
    facts=(
        ("接線後的樣子", "一段可直接推播的文字總結（含當日建議與理由）＋ 複製鈕"),
        ("⚠️ 線框畫了一顆鈕，本頁刻意沒有畫",
         "線框在這一區畫了單獨一顆［ ⚡ 生成 AI 總結 ］。它的輸入是上方六段的結論，"
         "而那六段全部未接線 —— 畫一顆按了不會發生任何事的鈕，"
         "就是線框 F5／N2 兩次點名要修的**假出口**。接線後再補，且它必須在表單**外**"),
        ("AI 的角色", "只潤稿。數字全部來自 digest，L3 明文禁止它自行杜撰代號或數字")))


def build_ai_summary_card(requested: bool) -> _Built:
    """線框葉1 ⑦「AI 戰情總結」—— **本批未接線**。

    線框 note 原文：「**v1 漏畫 —— 而它是本頁唯一的推播出口。**
    拿掉之後這頁就只能看、不能送出去。」
    """
    return build_unwired_card(requested, AI_SUMMARY_SPEC)


# ── 葉2 組合設定 ──────────────────────────────────────────────────
def build_binding_card(binding: BindingReadout) -> _Built:
    """葉2 第一張卡：**有沒有綁**（Google 登入 ＋ Sheet 綁定）—— 已接線、唯讀。

    ⚠️ **這張卡刻意不顯示 sheet id。** `BindingReadout` 結構上就沒有那個欄位
    （見它的 docstring）。畫面只回答一個布林。

    三種「沒有」不可混（本卡負責前兩種，第三種在 `build_portfolio_count_card`）：
      · 沒按 / 這一輪選了不讀 Google → `idle`
      · 讀了、沒登入或沒綁              → `empty`（**有效結果**，不是故障）
      · 讀了、Google 那端掛了           → `failed`
    """
    _state = classify_ui_state(
        requested=binding.requested,
        error=binding.error or None,
        has_value=binding.sheet_bound)
    _facts: list[tuple[str, str]] = [
        ("本頁對這本 Sheet 的權限", "**唯讀** —— 不新增、不修改、不刪除任何一列"),
        ("畫面不顯示的東西", "Sheet 識別碼與任何憑證（結構上就沒有帶進本層）"),
    ]
    if binding.requested and not binding.error:
        _facts.append(("Google 登入", "已登入" if binding.logged_in else "未登入"))
        if binding.status:
            _facts.append(("L3 回的狀態字串", binding.status))

    if _state == UI_LIVE:
        return (Card(key="hold.binding", label="Google Sheet 綁定",
                     state=UI_LIVE, value="已綁定一本"),
                tuple(_facts), "唯讀")
    if _state == UI_IDLE:
        # 兩種 idle 的文案不同（見 `binding_scope_idle`）：冷啟動 vs 選了不讀。
        if binding_scope_idle(binding):
            _note = Note(now=BINDING_NOT_ASKED_NOW, why=BINDING_NOT_ASKED_WHY,
                         where=BINDING_NOT_ASKED_WHERE)
        else:
            _note = Note(now=IDLE_NOW, why=IDLE_WHY, where=IDLE_WHERE)
    elif _state == UI_FAILED:
        _note = Note(
            now="**綁定狀態讀不出來**",
            why=_error_why(SRC_BINDING, binding.error),
            where=("先確認網路與 Google 授權是否仍有效；"
                   f"細節在{ia_nav.where_to_find(ia_nav.SECTION_WHY_DATA_HEALTH)}"))
    else:   # UI_EMPTY —— **還沒綁。這是有效結果，不是故障。**
        _note = Note(
            now="**你還沒有綁定持股 Sheet**",
            why=("**這是一個有效的結果**（已經去讀過，不是還沒讀、也不是故障）—— "
                 "戰情室的每一盞燈都以「你實際持有什麼」為輸入，沒有清單就沒有東西可判。"
                 "新使用者在這裡看到灰色是正常的"),
            where=("用 Google 登入後選一本 Sheet —— "
                   "**現行入口在既有的 📁 組合管理分頁**；"
                   "本頁只讀不寫，所以不在這裡放選 Sheet 的控制項"))
    return Card(key="hold.binding", label="Google Sheet 綁定",
                state=_state, note=_note), tuple(_facts), ""


def binding_scope_idle(binding: BindingReadout) -> bool:
    """這一輪的 idle 是不是「使用者選了不讀 Google」造成的（而不是冷啟動）。

    ⚠️ 兩者**都是 `idle`**，但**指路句完全不同**：冷啟動要你去按那顆鈕，
    「選了不讀」要你去改選項。用同一句話會對其中一半的人指錯路。
    這一支只做**文案分流**，不參與任何 `classify_ui_state` 的判定
    （狀態仍然只由 L0 決定）。

    ⚠️ 它讀的是 `submitted`（表單送出過沒有）而**不是**任何資料 ——
    冷啟動 `submitted=False`，「按了但選了只讀市場端」`submitted=True`
    且 `requested=False`。
    """
    return bool(binding.submitted and not binding.requested)


def build_portfolio_count_card(binding: BindingReadout) -> _Built:
    """葉2 第二張卡：**那本 Sheet 裡有幾本組合** —— 已接線、唯讀。

    ⚠️ **這張卡的存在就是「三態不得混」的結構性解法。**
    把「有沒有綁」與「綁到的那本裡有沒有內容」拆成兩張卡之後，
    **沒有任何一格需要同時代表兩件事**：

      · 還沒綁      → 本卡 `idle`（沒有那一本，就沒有人問過「那本裡有幾本」）
      · 綁了、0 本  → 本卡 `empty`（**綁好了但還沒填 —— 這不是故障**）
      · 綁了、讀不到→ 本卡 `failed`（L3 為了不擋住全域狀態列把它降級成中性，
                       本頁把那個被吞掉的失敗**還原成紅色**）
      · 綁了、N 本  → 本卡 `live`

    這一步剛好與 L3 契約對齊：`BindingState.portfolio_count=None` 的註解寫著
    「未知（未綁 or 讀取失敗）；**不腦補 0**」。
    """
    _state = classify_ui_state(
        requested=binding.count_gate,
        error=binding.error or None,
        has_value=binding.has_portfolios,
        reason=binding.count_missing_reason)
    _facts: tuple[tuple[str, str], ...] = (
        ("讀法", "只數「這本 Sheet 裡有幾本組合」，**不讀任何一列持股內容**"),
        ("為什麼不顯示 0",
         "L3 的契約是「未知 → `None`，**不腦補 0**」——"
         "「讀不到」與「真的是 0 本」是兩件事"),
    )
    if _state == UI_LIVE:
        return (Card(key="hold.portfolio_count", label="這本 Sheet 裡的組合",
                     state=UI_LIVE, value=f"{binding.portfolio_count} 本"),
                _facts, "")
    # ⚠️ **`idle` 有三種來源，文案一種都不可以共用**（實跑對過畫面才拆成三支）：
    #    冷啟動「還沒按」／按了但選「只讀市場端」／讀了但你根本還沒綁。
    #    共用一句就會出現「上一張卡顯示你還沒有綁定」這種**假敘述** ——
    #    冷啟動時上一張卡寫的是「尚未執行」，根本沒說過那句話。
    if _state == UI_IDLE and binding_scope_idle(binding):
        _note = Note(now=BINDING_NOT_ASKED_NOW, why=BINDING_NOT_ASKED_WHY,
                     where=BINDING_NOT_ASKED_WHERE)
    elif _state == UI_IDLE and not binding.submitted:
        _note = Note(now=IDLE_NOW, why=IDLE_WHY, where=IDLE_WHERE)
    elif _state == UI_IDLE:
        _note = Note(
            now="**還沒有可以數的 Sheet**",
            why=("上一張卡顯示你**還沒有綁定** —— "
                 "沒有那一本，就沒有人問過「那一本裡有幾本組合」。"
                 "**這不是失敗，是這個問題還沒有成立**"),
            where="先完成上一張卡說的綁定，這一格會自己有東西")
    elif _state == UI_FAILED:
        _note = Note(
            now=("**綁定看起來正常，但讀不到組合清單**"
                 if not binding.error else "**組合本數讀不出來**"),
            why=(_error_why(SRC_BINDING, binding.error) if binding.error else
                 "已經綁到一本 Sheet，但向它要組合清單時失敗了 —— "
                 "L3 為了不讓全域狀態列被擋住，把這次失敗降級成中性回傳；"
                 "**在這一頁它就是「系統真出錯」，所以還原成紅色**。"
                 "常見原因：授權過期、該 Sheet 被移除分享、或 Google 端暫時性錯誤"),
            where=("重新用 Google 登入授權一次，或確認那本 Sheet 仍然分享給你；"
                   f"來源狀態在{ia_nav.where_to_find(ia_nav.SECTION_WHY_DATA_HEALTH)}"))
    else:   # UI_EMPTY —— **綁了但空。這是有效結果，不是故障。**
        _note = Note(
            now="**Sheet 綁好了，但裡面還沒有任何一本組合**",
            why=("**這是一個有效的結果**（已經讀完，不是還沒讀、也不是故障）—— "
                 "空的組合就是空的，本站不把它畫成紅色錯誤。"
                 "剛建好 Sheet 還沒填內容時，這裡本來就該是灰的"),
            where=("到既有的 📁 組合管理分頁新增一本組合並填入持股列；"
                   "填完回本頁"
                   f"{press(ACTION_RUN_WARROOM_LABEL)}"))
    return Card(key="hold.portfolio_count", label="這本 Sheet 裡的組合",
                state=_state, note=_note), _facts, ""


#: 葉2 剩下兩項：線框 live 原文列的「Sheet 選擇」與「觀察清單管理」。
#: **這兩項不是缺 L3，是缺授權** —— 它們本質上是寫入，而本頁一律唯讀。
SETUP_UNWIRED_SPECS: tuple[UnwiredSpec, ...] = (
    UnwiredSpec(
        key="hold.setup.preview", label="持股列預覽",
        now="**本頁不顯示你的持股列**",
        why=HOLDINGS_WHY,
        where=_holdings_where(
            "接上之後這一格顯示每一列的代號／張數／均價 —— "
            "**仍然唯讀**（能看不能改）"),
        facts=(("卡住的層", "只差持股清單（唯讀就夠）"),
               ("接線後仍不會顯示的東西", "Sheet 識別碼與任何憑證"))),
    UnwiredSpec(
        key="hold.setup.pick_sheet", label="Sheet 選擇",
        now="**本頁不提供選 Sheet 的控制項**",
        why=READONLY_WHY, where=READONLY_WHERE,
        facts=(("為什麼", "選 Sheet 會改寫你的綁定設定 —— 那是寫入"),
               ("現行入口", "既有的 📁 組合管理分頁"))),
    UnwiredSpec(
        key="hold.setup.watchlist", label="觀察清單管理",
        now="**本頁不提供觀察清單的新增／刪除**",
        why=READONLY_WHY, where=READONLY_WHERE,
        facts=(("為什麼", "新增或移除觀察清單會寫回你的 Sheet —— 那是寫入"),
               ("現行入口", "既有的 📁 組合管理分頁 ／ 選股網的「加入觀察清單」"))),
)


def build_setup_unwired_cards(requested: bool) -> tuple[_Built, ...]:
    """葉2 的三張未接線卡（持股列預覽 / Sheet 選擇 / 觀察清單管理）。

    ⚠️ 後兩張的 `why` 走 `READONLY_WHY` 而**不是** `HOLDINGS_WHY` ——
    它們卡住的原因根本不同：前者是「沒有 L3」，後者是「本頁不准寫」。
    寫成同一句就等於告訴使用者「補一支 L3 就會有」，而那是假的。
    """
    return tuple(build_unwired_card(requested, _s) for _s in SETUP_UNWIRED_SPECS)


# ══════════════════════════════════════════════════════════════════
# 渲染（薄；所有判斷都在上面的純函式裡）
# ══════════════════════════════════════════════════════════════════
def _render_one(built: _Built) -> None:
    """畫一張卡，**並且不讓它把整頁畫到一半就死掉**。

    ⚠️ **本體在共用層** `_ui_kit.render_card_isolated()`（頁 1／2／3 已上移，
    本頁**不寫第四份**）。本函式只剩「把本頁專屬的三樣東西綁上去」：
    log 前綴 / 出處文案（出事的是哪一層只有本頁知道）/ 去哪補。
    """
    _card, _facts, _signal = built
    render_card_isolated(
        _card, facts=_facts, signal_text=_signal,
        owner="views/page_hold",
        error_why=lambda _err: _error_why(SRC_RENDER, _err),
        where=("這是渲染層的問題，不是你操作的問題 —— "
               f"{NO_EXIT_MARKER}；請把上面那行訊息回報給維護者"))


def _render_row(builts: Sequence[_Built]) -> None:
    """一列卡（鐵律 1：`grid()` 內部硬夾 `MAX_COLS`，多的換行排下一列）。"""
    for _chunk, _columns in grid(tuple(builts), MAX_COLS):
        for _built, _col in zip(_chunk, _columns):
            with _col:
                _render_one(_built)


def _render_holdings_form() -> bool:
    """葉2 的表單 —— 鐵律 2 的落點（線框：`st.form(form_holdings)` ＋ 單一 submit）。

    Returns:
        這一次 rerun 是否由 submit 觸發。

    ⚠️ **本頁直接用共用層 `_ui_kit.single_submit_form()`，沒有就地實作第四份。**
    頁 2／頁 3 各自就地實作，是因為它們的表單需要 `text_input` / `selectbox` /
    `checkbox`，而共用層只吃一組 `st.radio`。本頁的表單輸入**剛好就只有一組
    radio**（這一輪要不要順便讀 Google 綁定狀態），所以直接用它 ——
    **能用共用層就不要多開一把尺。**

    結構保證（由共用層提供，本檔不重複實作）：
      · 一個 `st.form`、**一顆** `st.form_submit_button`；
      · form 內**沒有** `st.button` / `st.download_button`（線框 F11：實跑即拋）；
      · widget **當下值**（`SS_SCOPE_WIDGET`）與**已套用值**（`SS_APPLIED_HOLD`）
        分家，下游只讀後者。

    ⚠️ **這個 radio 不是裝飾。** 選「只讀市場端」時，本頁**真的不會**向 Google
    發那一次讀取 —— 綁定那兩張卡會是 `idle`（沒有人叫過），不是空白、不是紅色。
    """
    return single_submit_form(
        FORM_HOLDINGS_KEY,
        submit_label=ACTION_RUN_WARROOM_LABEL,
        radio_label="這一輪要跑到哪裡（**兩個選項都不會寫入你的 Sheet**）",
        options=SCOPE_OPTIONS,
        option_labels=SCOPE_LABELS,
        widget_key=SS_SCOPE_WIDGET,
        applied_key=SS_APPLIED_HOLD)


def _render_warroom_leaf(session: Mapping[str, Any]) -> None:
    """葉1 戰情室：線框的七個區塊，**依線框順序**。"""
    _req = applied_hold_request(session)

    section_header("① 結論（三張卡）",
                   "線框：現行戰情室已是「結論在前、明細在後」，**結構不動**。")
    _render_row(build_conclusion_cards(_req.submitted))

    section_header("② 同一個名詞，兩套刻度",
                   "**常駐揭露 · 非摺疊** —— 它是防「同名不同義」誤讀的唯一揭露；"
                   "拿掉之後就會有人拿兩套刻度互比，而畫面不會攔他。")
    _scales = build_scale_disclosure()
    _render_one(build_scale_card(_scales))
    _render_scale_tables(_scales)

    section_header("③ 戰情表（燈牆 ＋ VIX）",
                   "線框：3 欄燈格 · 點左表右側就地展開。"
                   "燈牆與 VIX **各自判態** —— 一邊沒有不把另一邊染色。")
    _render_row((build_lightwall_card(_req.submitted),
                 build_vix_card(load_vix(_req))))

    section_header("④ 換股建議（搭配總經位階）",
                   "線框：本頁職責「該加、**該換**、該減」的那個「該換」。")
    _render_row((build_switch_card(_req.submitted),
                 build_macro_stage_card(load_macro(_req))))

    section_header("⑤ 80/20 配置偏離 ＋ 衛星停利",
                   "線框：它回答「該減」，與 ④ 的「該換」互補 —— "
                   "兩個都缺，本頁的職責就只剩三分之一。")
    _render_row((build_allocation_split_card(_req.submitted),
                 build_take_profit_card(_req.submitted),
                 build_position_cap_card(load_allocation(_req))))

    section_header("⑥ 組合深度分析（提升，不再埋 expander）", DEEP_CAPTION)
    _render_row(build_deep_cards(_req.submitted))

    section_header("⑦ AI 戰情總結（唯一推播出口）",
                   "線框：拿掉之後這頁就只能看、不能送出去。")
    _render_one(build_ai_summary_card(_req.submitted))


def _render_scale_tables(disclosure: ScaleDisclosure) -> None:
    """② 的逐盞門檻對照 —— **兩套刻度就地並陳**（線框：「就地列出兩者的定義與門檻」）。

    ⚠️ 這一段**不判態、不取數**，只是把 `build_scale_card()` 已經算好的
    `ScaleRow` 攤開。狀態由那張卡負責，這裡多判一次就會有兩個可能矛盾的說法。
    """
    if not disclosure.has_rows:
        return
    for _title, _rows, _hint in (
            ("💼 我的持股 › 戰情表「健檢」這一套", disclosure.hold_rows,
             HOLD_SCALE_SHAPE),
            ("🔬 查一檔 › 判決卡「健康度」那一套", disclosure.inspect_rows,
             INSPECT_SCALE_SHAPE)):
        st.caption(f"**{_title}** —— {_hint}")
        st.dataframe(
            [{"這一盞": _r.label,
              "門檻": _r.threshold_text or "—",
              "出處": _r.source or "—",
              "判別力": ("已失準（別照門檻讀）" if not _r.discriminative
                          else "正常")}
             for _r in _rows],
            hide_index=True, width="stretch")


def _render_setup_form_block() -> bool:
    """葉2 的**上半**：標題 ＋ 表單 ＋ 兩段常駐揭露。

    ⚠️ **它被單獨切出來，是為了讓 submit handler 先跑** —— 見
    `render_page_hold()` 裡「執行順序 ≠ 顯示順序」那段註解。
    """
    section_header(f"葉2 · {LEAF_SETUP_TITLE}",
                   "線框：**就地完成，不必去別頁** —— "
                   "但本頁對你的持股帳本**一律唯讀**，"
                   "需要寫入才做得到的部分會標「未接線」並說明原因。")
    _submitted = _render_holdings_form()
    st.caption(WIRING_DISCLOSURE)
    st.caption(READONLY_DISCLOSURE)
    return _submitted


def _render_setup_result_block(session: Mapping[str, Any]) -> None:
    """葉2 的**下半**：綁定兩張卡 → 三張未接線卡。"""
    _req = applied_hold_request(session)
    _binding = load_binding(_req)

    section_header("Google 登入與 Sheet 綁定（唯讀）",
                   "「還沒綁」與「綁了但裡面是空的」是**兩件事**，"
                   "所以拆成兩張卡 —— 沒有任何一格需要同時代表兩件事。")
    _render_row((build_binding_card(_binding),
                 build_portfolio_count_card(_binding)))

    section_header("持股列預覽 · Sheet 選擇 · 觀察清單管理",
                   "第一張卡缺的是 L3；後兩張卡**不是缺 L3，是缺授權** —— "
                   "它們本質上是寫入，而本頁唯讀。")
    _render_row(build_setup_unwired_cards(_req.submitted))


def render_page_hold() -> None:
    """💼 我的持股（IA v2 第 4 頁）。**本批無 production caller，刻意如此。**"""
    _session = st.session_state

    st.markdown(f"## {ia_nav.page_label(ia_nav.PAGE_HOLD)}")
    st.caption("我已經持有的，該加、該換、該減。")

    _leaf1, _leaf2 = st.tabs([LEAF_WARROOM_TITLE, LEAF_SETUP_TITLE])

    # ⚠️ **執行順序 ≠ 顯示順序，而且這裡的執行順序是必要的、不是風格。**
    # 線框把表單放在**葉2**，但它的 gate（`SS_APPLIED_HOLD`）被**葉1**消費。
    # `st.tabs` 這一輪會把兩葉的 body 都跑完；submit 觸發的那一次 rerun 裡，
    # 若葉1 先跑，它讀 session 時那個 key **還沒被寫進去** ——
    # 使用者按了鈕，戰情室卻還是一片「尚未執行」，而且**不會再自動 rerun**
    # 把它救回來（頁面看起來就是「這顆鈕沒反應」）。
    # 故：先把表單畫進葉2 的容器（submit handler 在這裡寫 gate），
    # 再畫葉1，最後回到葉2 畫它的下半。容器可以重複進入，
    # 顯示位置仍然分別在各自的分頁裡。
    # 守衛：`tests/test_p04_hold_view.py::TestFormRunsBeforeItsConsumers`。
    with _leaf2:
        _render_setup_form_block()
    with _leaf1:
        _render_warroom_leaf(_session)
    with _leaf2:
        _render_setup_result_block(_session)
