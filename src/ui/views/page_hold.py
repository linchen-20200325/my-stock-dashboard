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

⚠️ **「本檔沒有 production caller」這句話已經過期**（2026-09-07 更正）：
`app.py` **已經掛上本頁**（`render_page_hold` 於 `app.py` 的分頁列，量測日 2026-09-07；
掛載由另一組完成，本批一個字都沒有碰 `app.py`）。**這是事實更正，不是政策變更** ——
本批同樣沒有碰 `page_today.py`、`page_find.py`、`page_inspect.py`、`page_why.py`、
`_ui_kit.py`、`src/ui/tabs/**`、`shared/**`。
舊分頁（`etf_tab_dividend_station` 等）不動、不下架。
⚠️ **有 caller 之後，這一頁的每一個 bug 都是使用者看得到的** ——
下一個人不得再拿「反正沒有人在用」當放寬任何守衛的理由。

═══ 取數接線表（**唯一的規則是「一律走 L3」**）═════════════════════════
**已接線（全部唯讀）**::

    持股清單      L3 `services.holdings_service.get_holdings`      ← **本批新增**
    戰情表 ＋ VIX L3 `services.dividend_station_service.get_station_rows`
    規則式彙總    L3 `services.dividend_station_service.build_station_digest`
                  （內含 80/20 `compute_allocation_split` ＋ 停利 `flag_take_profit`）
    組合層金額    L3 `services.dividend_station_service.compute_portfolio_totals`
    壓力測試      L3 `services.portfolio_deep_service.get_portfolio_stress`   ← **本批新增**
    VaR           L3 `services.portfolio_deep_service.get_portfolio_var`      ← **本批新增**
    配息現金流    L3 `services.portfolio_deep_service.get_dividend_cash_flow` ← **本批新增**
    換入候選      L3 `services.dividend_station_service.get_switch_in_candidates`
    換股建議      L3 `services.dividend_station_service.build_switch_advice`
    綁定狀態      L3 `services.portfolio_binding_service.get_binding_state`
    VIX（單獨）   L3 `services.dividend_station_service.fetch_vix`
    總經位階      L3 `services.dividend_station_service.get_station_macro`
    建議持股水位  L3 `services.allocation_service.get_allocation`
    N/M 盞可信度  L4 `ui.render.station_cards.aggregate_judged` / `tally_states` /
                  `is_fully_judged` / `cruise_or_gap`（**與既有戰情室同一把尺**）
    燈格牆渲染    L4 `ui.render.station_cards.render_light_wall` / `render_legend`
    兩套刻度揭露  L0 `shared/station_specs.py`（純常數，零 I/O）

⚠️ **`services/holdings_service.py` 是本批補上的那一步。** 在它之前，
`src/services/` 底下沒有任何一支回傳「你持有哪幾檔、各幾張、均價多少」
（**這句全稱句出自另一組（AUD-5）的窮舉，本頁作者沒有自己重跑** —— §-2 規則 6），
唯一產得出那份 list 的是
L5 私有函式 `etf_tab_dividend_station._load_holdings_from_portfolio()` ——
本頁**不會**去 import 它（跨檔取用底線開頭的私有符號＝`CLAUDE.md §8.2.A.2`
**V-PICKER-PRIV-1** 登記的違憲；經別的 L5 檔 re-export 繞道只是騙過靜態檢查）。
補的是一支**住在 L3 的公開唯讀介面**，而 L3 → L1 是正常方向
（既成範式：`watchlist_service` / `portfolio_binding_service`）。

⚠️ **讀持股要連 Google，所以它綁在表單的第二個選項上。** 選「只讀市場端」時本頁
**真的不會**去讀你的 Sheet —— 戰情室會是灰的 `idle`（沒有人叫過），不是空白、不是紅色。

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

═══ 這一批**仍然沒有接上**的項目（誠實揭露，不是漏寫）═══════════════════
持股清單接上之後，戰情室 ①③④⑤ ＋ ⑥ 的核心／衛星 ＋ 葉2 的持股列預覽都活了。
**剩下這幾項卡在別的地方，與持股清單無關** —— 「去哪補」各自不同：

  1. ⛔ **⑥ 再平衡**。**缺的不是 L3 wrapper**（本批補的
     `services/portfolio_deep_service.py` 就在那裡，壓測與 VaR 走的是它）——
     缺的是**目標權重**。再平衡是「實際權重 vs **你想要的**目標權重」的比較，
     而持股帳本那張表只有 `name / ticker / lots / avg_price / updated_at` 五欄
     （實測 `data/portfolio/gsheet_portfolio._HEADERS`，量測日 2026-09-07），
     **沒有目標比例**；L3 `portfolio_analysis_bridge` 也明寫
     「組合管理未存目標比例（§1 不拿現況冒充目標）」。
     L2 `portfolio_gates.evaluate_rebalance_gate` 對這種輸入的判定就是
     「⚪ 無法判定：尚未設定目標權重」—— 拿現況當目標，偏離度必然是 0.0%，
     那不是「已平衡」而是「沒算」。要讓使用者填目標比例＝**新增畫面元件**，
     落在 UI 草稿先行（`CLAUDE.md §-1.5` A-8）。
     ⛔ **也不會改用** `compute.strategy.portfolio_manager.CoreSatelliteManager`
     頂替：它的核心比例是**另一套**（依 regime 0.60~0.85），與本頁 ⑤／⑥
     用的 L0 80/20 目標不同 —— 同一頁出現兩個互相矛盾的核心比例（§2.1 SSOT）。
  2. ✅ **⑥ 壓力測試 / VaR / 配息現金流 —— 本批已接線**
     （L3 `services/portfolio_deep_service.py`）。三項共同的單位陷阱
     **張 → 股 → 元** 一律住在那一支 L3 的 `_lot_to_shares()`
     （**該檔唯一**的乘法點 —— 守衛：`tests/test_p04_hold_view.py::
     TestPortfolioDeepServiceIsReadOnly::test_there_is_exactly_one_multiplication_site`），
     本頁**一個乘法都沒有**（§4.1 漏乘 = 1000 倍低估）。
     ⚠️ **「該檔唯一」不是「全站唯一」，別把這兩句讀成同一句。**
     實測（`grep -rn 'SHARES_PER_LOT' --include=*.py`，量測日 2026-09-07）
     全站另有 `services/dividend_station_service.py`（① 那張卡的總市值，
     本頁拿它對帳）與 `compute/sector_flow.py`（板塊資金流的張×元→億 合併係數）
     各自也乘每張股數。**本頁的數字只保證走 `portfolio_deep_service` 這一支**，
     不對另外兩支的納入口徑背書 —— 「對不起來」正因如此才要在卡面講
     （見 `_degraded_bits()`：那一態是橘的 `UI_DEGRADED`，不是綠的）。
     守衛：`TestTheLotToShareClaimIsMeasurable`。
     ⚠️ **配息現金流只接了不需要稅率的那一半**：綜所稅邊際稅率是**使用者輸入**，
     新增輸入元件要先出線框草稿給客戶拍板（A-8），故本批一律傳
     `marginal_rate=None`（L3 明文支援：只算二代健保）。
     卡面**必須把「不含綜所稅」講出來**，否則「稅後」兩個字就是在說謊。
  3. ⛔ **⑥ 葡萄串領息**。實作在 L5 `tabs.grape_ladder`、自帶寫死的 widget key，
     在本頁再掛一次會撞 `DuplicateWidgetID`。
  4. ⛔ **⑦ AI 戰情總結**。四支 L3 都在（`build_station_digest` →
     `build_summary_prompt` → `build_ai_summary`，`gemini_fn` 由
     `app_ai_service.gemini_call` 注入），digest 現在也**真的算得出來了**；
     卡住的是**畫面**：線框在這一區畫了一顆單獨的 `st.button`［ ⚡ 生成 AI 總結 ］，
     而「新增一個視覺元件」要先出線框草稿給客戶拍板（`CLAUDE.md §-1.5` A-8）。
     ⚠️ **不會用「自動生成」繞過那顆鈕** —— 每次 rerun 都打一次付費 AI，
     比少一顆鈕嚴重得多。
  5. ⛔ **葉2 的「Sheet 選擇」與「觀察清單管理」**。這兩項**不是缺 L3，是缺授權** ——
     它們本質上是**寫入**，而本頁一律唯讀（見檔頭第二段）。

⚠️ **一個沒有做、而且要講出來的取捨**：本頁**不能**把 `get_station_rows()` 的結果
存進 `st.session_state`（那會是 gate 之外的第二個 session 寫入點，
`tests/test_p04_hold_view.py` 直接禁止本檔出現任何 session 下標指派）。
於是**送出之後的每一次 rerun 都會重跑一次整段編排** —— 網路那一層由 L1 的
`@st.cache_data` 擋住（本頁不自建快取，`CLAUDE.md §8.2.A.2` V-SMART-CACHE-1），
但逐檔的純運算會重算。既有 🏦 ETF ›存股戰情室 是靠自己存 session 避開這件事的。
**這是已知代價，不是沒想到；沙箱測不到它的實際延遲。**

⚠️ **本頁會判 `UI_DEGRADED` 的有兩處，兩處都不是硬湊的。**

**其一：② 兩套刻度。**
它直接讀 L0 `station_specs` 的 `discriminative` 旗標。實測（量測日 2026-09-07）
`KEY_STOCK_TREND`（財報趨勢）標了 `discriminative=False`，
`degraded_reason` 原文是「這格只比較**最近兩季**，看不出趨勢」——
而那盞燈正是本頁個股「健檢」欄（`swap_level`）的輸入之一
（L2 `assess_stock`：grade 尚可但 `is_breakdown` → 提前 🟡）。
**所以本頁這一側的刻度確實有一個已失準的輸入**，線框 ② 的 degraded 文案
（「某一側的門檻來源已標 `discriminative=False`」）在 repo 現況下是**真的**。
若哪天那個旗標被改回 `True`，這張卡會自己變回 live —— 本檔沒有寫死任何一邊。

**其二：⑥ 的壓力測試與 VaR**（`_degraded_bits()`）。兩種情形會讓那個金額
**失去判別力**，兩種都由 L3 的欄位帶下來、本頁不自己判斷：
  (a) `reconciled=False` —— 本格的總市值與 ① 那張卡的
      `compute_portfolio_totals()` 對不起來（兩邊納入的持股列不是同一批）；
  (b) `no_price` 非空 —— 有持股抓不到價格序列，被排除在樣本外。
兩者都是「**算得出來、但打了折**」：綠燈配一行小字等於讓使用者把一個
已知失準的金額當成結論讀（§1「錯誤的數字比沒有數字更危險」）。
⛔ **不降成 `UI_FAILED`（紅）** —— 紅是「系統真出錯」；把打折畫成故障
就是製造假警報，而滿版假紅字會讓**真的**故障沒人看得見（`CLAUDE.md §1.A-4`）。
⚠️ 降級後 `Card` 規定非 live 不得帶結論文字 → **現值改掛 facts 的「現值」列**
（與 `page_today` 的 degraded 同一種做法，不另立第二套寫法），
**數字不藏起來**，只是不再當成結論、也不再出燈號（門檻已失準就別照門檻讀）。

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
    KIND_ETF,
    SATELLITE_TAKE_PROFIT_PCT,
    SATELLITE_TARGET_PCT,
    VIX_LIGHT1,
    VIX_LIGHT2,
    VIX_LIGHT3,
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

#: 持股列預覽的「種類」欄顯示字。**判型本身在 L0**（`classify_asset_kind`），
#: 這裡只是把 L0 的 `KIND_*` 換成中文；本檔**不判**任何一檔是 ETF 還是個股。
#: ⚠️ 為什麼不共用 L3 戰情表那一欄：那一欄是 `get_station_rows()` **算完之後**
#: 才有的，而預覽表要在算之前就顯示（它是「我讀到了什麼」，不是「算出了什麼」）。
KIND_LABELS: dict[str, str] = {KIND_ETF: "ETF"}
KIND_FALLBACK_LABEL: str = "個股"


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
#: 額外向 Google Sheets **讀**綁定狀態 ＋ 持股清單（唯讀）。
#:
#: ⚠️ **常數名沿用 `with_binding`，但它現在讀的不只綁定狀態。** 名字沒有跟著改，
#: 是因為它是**已套用值寫進 session 的字面字串**：改掉會讓使用者上一輪的選擇在
#: 下一次部署後解析失敗（`applied_hold_request()` 會把不認得的值退回
#: `SCOPE_MARKET`）。**畫面上的標籤照實改**（下面那一行）—— 使用者讀的是標籤，
#: 不是常數名。標籤沒改才是說謊。
SCOPE_WITH_BINDING: str = "with_binding"
SCOPE_LABELS: dict[str, str] = {
    SCOPE_MARKET: "只讀市場端（不連 Google，也不讀你的持股）",
    SCOPE_WITH_BINDING: "加讀 Google Sheet：綁定狀態 ＋ 你的持股清單（唯讀，不寫入）",
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

#: 選了「只讀市場端」時的三要素。**這不是故障，是你選的。**
#:
#: ⚠️ 名字從 `BINDING_NOT_ASKED_*` 改成 `GOOGLE_NOT_ASKED_*`（2026-09-07）：
#: 這一輪之後，同一個選項擋掉的**不只是綁定狀態，還有整份持股清單** ——
#: 名字沒跟著改，下一個人會以為戰情室那一片灰是別的原因。
GOOGLE_NOT_ASKED_NOW: str = "**這一輪沒有讀 Google Sheet**"
GOOGLE_NOT_ASKED_WHY: str = (
    "你這一輪選的是"
    f"「{SCOPE_LABELS[SCOPE_MARKET]}」—— 本頁因此**真的沒有發那一次網路呼叫**，"
    "不是發了失敗，也不是拿上一輪的殘留頂替。"
    "**你的持股清單也在這一次呼叫裡**，所以戰情室整片都是灰的（沒有人叫過），"
    "不是「你沒有持股」")
GOOGLE_NOT_ASKED_WHERE: str = (
    f"到{SETUP_WHERE}把選項改成"
    f"「{SCOPE_LABELS[SCOPE_WITH_BINDING]}」，再{press(ACTION_RUN_WARROOM_LABEL)}")

#: 未接線卡的共同開頭。**每一張卡的 `where` 都必須在這之後接自己那一段**
#: —— 剩下的幾張卡不是卡在同一個地方（有的缺 L3 wrapper、有的缺一個畫面元件、
#: 有的根本是本頁不准寫），共用一句話會讓「補哪一層才會好」這個資訊消失。
UNWIRED_WHERE_PREFIX: str = (
    f"{NO_EXIT_MARKER} —— 這是待接線項，不是你操作的問題；"
    f"{press(ACTION_RUN_WARROOM_LABEL)}也不會改變它。")

#: ⚠️ **`MISSING_L3_WRAPPER_WHY` 本批已刪除，不要再加回來。**
#: 它原本是 ⑥ 再平衡 / 壓力測試 / VaR 三張卡共用的理由（「L3 沒有 wrapper」）——
#: 本批補上 `services/portfolio_deep_service.py` 之後，那句話對這三張卡**都是假的**：
#: 壓測與 VaR 已經接線，而再平衡缺的從來就不是 wrapper（缺的是目標權重，見
#: `DEEP_SPECS`）。留著一個「還沒有 wrapper」的常數，遲早有人拿它去當理由，
#: 叫下一個人去補一支已經在那裡的東西（§-2：沒查證的宣稱比沒有宣稱更危險）。
#: 守衛：`tests/test_p04_hold_view.py::TestUnwiredStaysUnwired`。

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
    "**取數接線揭露**：本頁的持股清單走 L3 `holdings_service.get_holdings()`"
    "（**唯讀**），戰情表 / 燈牆 / 換股建議 / 80-20 偏離 / 衛星停利 / 結論三張卡"
    "都由它餵進 `dividend_station_service` 的既有 L3 算出來。"
    "⑥ 的**壓力測試 · VaR · 配息現金流**走 L3 `portfolio_deep_service`（**唯讀**）—— "
    "張→股→元 的換算住在那一支 L3，本頁一個乘法都沒有。"
    "**仍未接線的是**：⑥ 的再平衡（帳本沒有「目標比例」這一欄，"
    "沒有目標就沒有偏離）、⑥ 的葡萄串領息（實作在 L5）、"
    "⑦ AI 總結（要一顆線框畫了、但尚未拍板的按鈕）、"
    "以及葉2 的 Sheet 選擇與觀察清單管理（那兩項是**寫入**，本頁唯讀）。"
    "⚠️ **配息現金流只算到扣二代健保為止，不含綜所稅** —— "
    "稅率要你自己填，而那是一個還沒拍板的輸入元件。"
    "未接線的卡會標「未接線」並各自寫明要補在哪，不會拿空白冒充結果。")

#: 唯讀宣告（常駐，與接線揭露並列）。
READONLY_DISCLOSURE: str = (
    "**唯讀宣告**：本頁**只讀不寫** —— 不新增、不修改、不刪除你 Google Sheet 裡的"
    "任何一列持股，也不會在畫面上顯示 Sheet 識別碼或任何憑證"
    "（只顯示「有沒有綁」這件事）。"
    "需要寫入才做得到的功能（選 Sheet、管理觀察清單）在本頁一律標「未接線」。")


def _idle_note(scope_idle: bool) -> Note:
    """`idle` 的三要素。**兩種來源、兩套指路句，這裡是唯一的分流點。**

    Args:
        scope_idle: `True` = 使用者按了鈕但這一輪選「只讀市場端」；
            `False` = 冷啟動（還沒有人按過）。

    ⚠️ 兩者都是 `idle`，共用一句話會對其中一半的人指錯路：冷啟動要你去按鈕，
    「選了不讀」要你去改選項 —— 對後者說「請按下那顆鈕」，他會按了又按。
    ⚠️ 這一支**只挑文案**，不參與任何 `classify_ui_state()` 的判定
    （狀態仍然只由 L0 決定，而 `scope_idle` 讀的是使用者的選擇、不是資料）。
    """
    if scope_idle:
        return Note(now=GOOGLE_NOT_ASKED_NOW, why=GOOGLE_NOT_ASKED_WHY,
                    where=GOOGLE_NOT_ASKED_WHERE)
    return Note(now=IDLE_NOW, why=IDLE_WHY, where=IDLE_WHERE)


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
    """建議持股水位那一輪的 L3 產出（`get_allocation()` 的仲裁結果）。

    本頁顯示的持股水位一律取自 L3 `get_allocation()`，本頁不自行再算；
    它仲裁「姿態油門 × macro_state 曝險上限 × VIX／三環天花板」三條輸入，
    **取最低**。

    ⚠️ **這不是「全站唯一」的持股水位算法**（舊文案這樣寫，實測為假）。
    全站另有**沒有進到上面那個 min() 裡**的獨立算法，實測至少四支
    （量測日 2026-09-07，逐支可單點 grep）：
      · `src/compute/notify/market_alert_banner.py` 的
        `EXTREME_TARGET_POSITION_PCT` / `LEAD_TARGET_POSITION_PCT`
        （每日推播 `scripts/push_holdings_daily.py` 在用）；
      · `src/compute/strategy/v4_strategy_engine.py::check_macro_veto()`
        回傳的 `max_position`（docstring 自稱「強制持股水位上限」）；
      · `src/services/market_strategy.py` 的 `exposure_pct`
        （← `src/compute/risk/risk_control.py::portfolio_exposure`）；
      · **本頁 ④ 那格自己印的「姿態油門帶」** ——
        `src/services/dividend_station_service.py::get_station_macro()` 的
        `posture_range`，直接 `compute_position_throttle()`，**未套任何 cap**。
    最後那一項是**同一頁的自我矛盾**，不是別人家的事：④ 與 ⑤ 同時印兩個持股
    區間、口徑不同，使用者不會知道。故 ④ 那格必須自己標明「未套天花板」。
    守衛：`tests/test_p04_hold_allocation_ssot_claim.py`（同時**反向**驗這四支
    現在真的還在；哪天被收斂掉，測試轉紅提醒改文案 —— 假的「未納管清單」
    跟假的「全站唯一」一樣糟）。

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


# ══════════════════════════════════════════════════════════════════
# 持股清單（本頁的第一輸入）—— **本批新接線，唯讀**
# ══════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class HoldingsReadout:
    """你持有哪幾檔。**本頁其餘七個區塊全部以它為輸入。**

    Attributes:
        requested: 由 `HoldRequest.wants_binding` 帶下來 —— 讀持股要連 Google，
            所以它與綁定狀態共用同一個使用者選擇（**不是**從資料反推）。
        holdings: L3 的清單原樣搬運（`ticker` / `name` / `held` / `asset_kind` /
            `asset_class` / `lots` / `avg_price`）。
            ⚠️ 觀察清單那些列的 `lots` / `avg_price` 是 `None` —— 那份分頁的
            schema **只有三欄**，本來就沒有張數與均價。**它們不是 0。**
        bound: 有沒有綁到投資組合 Sheet。`False` ＋ 空清單 = 你還沒綁（**有效結果**）。
        portfolio_name / watchlist_name: 實際讀到的那一本／那一份的名字。
        more_portfolios / more_watchlists: 那本 Sheet 裡**還有別本沒讀**
            （L3 只取第一本，沿用既有行為）。不講出來，使用者會以為畫面上就是全部。
        watchlist_error: 觀察清單那半讀取失敗。**持股本身不受影響，但不得吞掉。**
        error: 持股清單整份讀取失敗（L3 對投資組合那半是 fail loud）。
    """

    requested: bool
    submitted: bool = False
    holdings: tuple[dict, ...] = ()
    bound: bool = False
    portfolio_name: str = ""
    watchlist_name: str = ""
    more_portfolios: bool = False
    more_watchlists: bool = False
    watchlist_error: str = ""
    error: str = ""

    @property
    def has_holdings(self) -> bool:
        """**空清單不算有值。** 「你還沒有任何持股」是 `empty`，不是 `live`。"""
        return bool(self.holdings)

    @property
    def scope_idle(self) -> bool:
        """這一輪的 idle 是不是「使用者選了不讀 Google」造成的（而非冷啟動）。

        ⚠️ 兩者**都是 `idle`**，但指路句完全不同：冷啟動要你去按那顆鈕，
        「選了不讀」要你去改選項。用同一句會對其中一半的人指錯路。
        同 `binding_scope_idle()`，只做文案分流，不參與任何狀態判定。
        """
        return bool(self.submitted and not self.requested)

    @property
    def held_tickers(self) -> tuple[str, ...]:
        """已持有代號 —— 給 `get_switch_in_candidates(exclude=…)`。

        ⚠️ **刻意不在這裡去 `.TW` / `.TWO` 後綴**：L3 那一支自己會用 L0
        `normalize_ticker()` 把 exclude 與候選兩邊都正規化再比對。
        在這裡先去一次，等於把同一條規則寫成兩份（§2.1 SSOT）。
        """
        return tuple(str(_h.get("ticker") or "")
                     for _h in self.holdings if _h.get("held"))


def load_holdings(req: HoldRequest) -> HoldingsReadout:
    """持股清單。**`req.wants_binding` 為 False 時一行 L3 都不呼叫。**

    路徑：L3 `services.holdings_service.get_holdings()` —— 它的 docstring
    自陳「純讀不寫」，且**只呼叫 L1 gsheet 的讀取面**。

    邊界（四種，一種都不可以混）：
      (a) 沒按 / 這一輪選了不讀 Google → `requested=False` → 全頁 idle。
      (b) 讀了、沒綁 Sheet             → `bound=False` ＋ 空清單 → `empty`（灰）。
      (c) 讀了、綁了、但一列都沒有     → `bound=True` ＋ 空清單 → `empty`（灰）——
          **與 (b) 不是同一件事**，指路句不同（去綁 vs 去填）。
      (d) L3 拋例外                    → `failed`（紅）。L3 對「投資組合」那半
          **刻意 fail loud**：半份清單算出來的 80/20 與損益看起來正常、實際是錯的。
    """
    if not req.wants_binding:
        return HoldingsReadout(requested=False, submitted=req.submitted)
    try:
        from src.services.holdings_service import get_holdings
        _h = get_holdings()
    except Exception as _e:  # noqa: BLE001 — 轉成紅態顯示，不吞
        print(f"[views/page_hold] 持股清單讀取失敗 → 轉紅態：{_e!r}")
        return HoldingsReadout(requested=True, submitted=req.submitted,
                               error=repr(_e))
    return HoldingsReadout(
        requested=True, submitted=req.submitted,
        holdings=tuple(dict(_r) for _r in (getattr(_h, "holdings", ()) or ())),
        bound=bool(getattr(_h, "bound", False)),
        portfolio_name=str(getattr(_h, "portfolio_name", "") or ""),
        watchlist_name=str(getattr(_h, "watchlist_name", "") or ""),
        more_portfolios=bool(getattr(_h, "more_portfolios", False)),
        more_watchlists=bool(getattr(_h, "more_watchlists", False)),
        watchlist_error=str(getattr(_h, "watchlist_error", "") or ""))


# ══════════════════════════════════════════════════════════════════
# 戰情表（燈牆 ＋ 規則式彙總）—— **本批新接線**
# ══════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class StationReadout:
    """一次戰情室運算的全部產出。**本頁不判任何一盞燈，只搬運。**

    Attributes:
        requested: 由 `HoldingsReadout.requested` 帶下來。
        rows: L3 `get_station_rows()` 的逐檔列（含非顯示欄 `_lights` / `_detail`）。
            ⚠️ **這裡刻意沒有 `vix` 欄位**：`get_station_rows()` 內部確實抓了一次
            （digest 需要它），但畫面上那張 VIX 卡走的是**另一個 gate**
            （選「只讀市場端」時也要看得到 VIX，那一輪根本不會跑戰情表）。
            兩邊打到的是 L1 同一個 module-level 快取，不是兩次網路。
            存一份沒有人讀的副本，只會多一個將來可能與畫面不一致的數字。
        totals: L3 `compute_portfolio_totals()`；`None` = 算不出來（**不填 0**）。
        split: 80/20 實際配置；`None` = 沒有可計價持股。
        take_profit: 達停利門檻的衛星列（可以是空的 —— 那是**有效結果**）。
        add_n / cut_n / err_n: digest 的加碼 / 汰弱 / 整批抓取失敗檔數。
        judged / total_lights: 「N/M 盞給得出判定」。**分母是動態的**
            （ETF 8 盞、個股 3 盞），本檔一個總數都不寫死。
        unjudged_rows: 有幾列不是「每盞適用燈都判得出來」。
            （「每一列都判得出來嗎」這個布林只在算 `cruise_text` 時用到一次，
            不另存一份 —— 存了就會有人拿它去重寫巡航那句話，而那句話的 SSOT
            在 L4 `cruise_or_gap()`。）
        tally: 四態各有幾格（分母口徑與 `judged` 同一把尺）。
        cruise_text: L4 巡航 gate 的那一句（**顯示層 SSOT，本檔不自己寫**）。
        error: 呼叫期例外，或持股那一層帶下來的例外。
    """

    requested: bool
    submitted: bool = False
    #: 有沒有綁到持股 Sheet / 這一輪讀到幾列持股。
    #: ⚠️ **這兩個欄位存在的唯一理由是「三種沒有不可混」**（見檔頭）：
    #: 「還沒綁」要你去綁、「綁了但空」要你去填 —— 指路句完全不同。
    #: 沒有它們，戰情室每一張空卡就只能寫一句「沒有持股（可能是 A 也可能是 B）」。
    bound: bool = False
    holdings_n: int = 0
    rows: tuple[dict, ...] = ()
    totals: Mapping[str, Any] | None = None
    split: Mapping[str, Any] | None = None
    take_profit: tuple[Mapping[str, Any], ...] = ()
    add_n: int = 0
    cut_n: int = 0
    err_n: int = 0
    judged: int = 0
    total_lights: int = 0
    unjudged_rows: int = 0
    tally: Mapping[str, int] = field(default_factory=dict)
    cruise_text: str = ""
    error: str = ""

    @property
    def has_rows(self) -> bool:
        return bool(self.rows)

    @property
    def scope_idle(self) -> bool:
        """同 `HoldingsReadout.scope_idle` —— 只做 idle 的**文案**分流。"""
        return bool(self.submitted and not self.requested)

    @property
    def has_lights(self) -> bool:
        """分母 > 0 才算「算得出可信度」。**0/0 不是可信度，是沒東西可以算。**"""
        return self.total_lights > 0


def load_station(holdings: HoldingsReadout) -> StationReadout:
    """戰情表。**`holdings.requested` 為 False 時一行 L3 都不呼叫。**

    ⚠️ **持股是空的時候，本函式也不呼叫 L3。** 那不是把 gate 從資料反推 ——
    `requested` 照樣是 `True`（使用者確實叫過），只是「對空清單跑一次逐檔抓取」
    沒有任何意義。回傳的 `rows=()` 讓卡片落在 `empty`（灰），這正確：
    **叫過了、沒有錯、就是沒有東西可以判。**

    ⚠️ **上游的例外原樣往下帶**：持股讀不到時，戰情室的每一格都該是紅的 ——
    這一頁沒有「持股讀不到但燈牆還亮著」這種狀態。
    """
    if not holdings.requested:
        return StationReadout(requested=False, submitted=holdings.submitted)
    if holdings.error:
        return StationReadout(requested=True, submitted=holdings.submitted,
                              bound=holdings.bound, error=holdings.error)
    if not holdings.has_holdings:
        return StationReadout(requested=True, submitted=holdings.submitted,
                              bound=holdings.bound)
    try:
        from src.services.dividend_station_service import (
            build_station_digest,
            compute_portfolio_totals,
            get_station_rows,
        )
        # L4（顯示層）：N/M 的分母口徑與既有戰情室**同一把尺**，本檔不自己數。
        from src.ui.render.station_cards import (
            aggregate_judged,
            cruise_or_gap,
            is_fully_judged,
            tally_states,
        )
        _rows, _vix = get_station_rows([dict(_h) for _h in holdings.holdings])
        _rows = list(_rows or ())
        _digest = build_station_digest(_rows, _vix)
        _totals = compute_portfolio_totals(_rows)
        _cells = [(_r.get("_lights") or ()) for _r in _rows]
        _judged, _total = aggregate_judged(_cells)
        _unjudged = sum(1 for _c in _cells if not is_fully_judged(_c))
        _all_judged = bool(_cells) and _unjudged == 0
        _tally = tally_states(_cells)
        _cruise = cruise_or_gap(_judged, _total, all_rows_judged=_all_judged)
    except Exception as _e:  # noqa: BLE001 — 轉成紅態顯示，不吞
        print(f"[views/page_hold] 戰情表運算失敗 → 轉紅態：{_e!r}")
        return StationReadout(requested=True, submitted=holdings.submitted,
                              bound=holdings.bound,
                              holdings_n=len(holdings.holdings), error=repr(_e))
    return StationReadout(
        requested=True, submitted=holdings.submitted,
        bound=holdings.bound, holdings_n=len(holdings.holdings),
        rows=tuple(_rows),
        totals=_digest_map(_totals),
        split=_digest_map(_digest.get("allocation")),
        take_profit=tuple(dict(_t) for _t in (_digest.get("take_profit") or ())),
        add_n=len(_digest.get("adds") or ()),
        cut_n=len(_digest.get("reds") or ()),
        err_n=len(_digest.get("errors") or ()),
        judged=int(_judged), total_lights=int(_total),
        unjudged_rows=int(_unjudged),
        tally=dict(_tally or {}),
        cruise_text=_clean_signal(_cruise))


def _digest_map(value: Any) -> Mapping[str, Any] | None:
    """L3 回的 dict → 唯讀複本；不是 Mapping（含 `None`）就原樣回 `None`。

    §1：`None` 在這幾支 L3 的契約裡是「**算不出來**」（不是 0、不是空）——
    本層不把它改寫成 `{}`，否則下游分不出「沒有這個結論」與「結論是空的」。
    """
    return dict(value) if isinstance(value, Mapping) else None


# ══════════════════════════════════════════════════════════════════
# 換股建議（換出 ＋ 換入）—— **本批新接線**
# ══════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class SwitchReadout:
    """線框 ④ 的「該換」。**換出與換入必須同時有輸入才產得出來。**

    Attributes:
        requested: 由 `StationReadout.requested` 帶下來。
        switch_out: 你**持有**且健檢 🔴 的那幾檔（觀察清單的紅燈不算換出）。
        switch_in: 換入候選。優先來自**你自己的觀察清單**綠燈；沒有才 fallback 選股池。
        switch_in_src: `watchlist`（你選的）/ `screener`（全自動排名）。
        stance: 總經攻守（`unknown` = 未評估 → 只做汰弱，**不套攻守、不猜多空**）。
        excluded_n: 傳給 `get_switch_in_candidates(exclude=…)` 的已持有檔數。
            ⚠️ 這個數字要顯示出來 —— 少了 exclude，換入候選會**叫你買你已經有的東西**。
        error: 呼叫期例外，或上游帶下來的例外。
    """

    requested: bool
    submitted: bool = False
    switch_out: tuple[Mapping[str, Any], ...] = ()
    switch_in: tuple[Mapping[str, Any], ...] = ()
    switch_in_src: str = ""
    stance: str = ""
    excluded_n: int = 0
    error: str = ""

    @property
    def scope_idle(self) -> bool:
        """同 `HoldingsReadout.scope_idle` —— 只做 idle 的**文案**分流。"""
        return bool(self.submitted and not self.requested)

    @property
    def has_advice(self) -> bool:
        """**兩半都沒有東西才算沒有建議。** 「沒有一檔要換」也是一個結論 ——

        但它需要**有列可以判**才成立，而那由 `StationReadout.has_rows` 決定；
        本屬性只回答「這一輪產出了幾個具體標的」。
        """
        return bool(self.switch_out or self.switch_in)


def load_switch(station: StationReadout, macro: MacroReadout,
                holdings: HoldingsReadout) -> SwitchReadout:
    """換股建議。**`station.requested` 為 False 時一行 L3 都不呼叫。**

    ⚠️ **`exclude=已持有代號` 是必要參數，不是可選的優化。** 少了它，
    「換入候選」會從全市場排名裡挑出你**已經持有**的那幾檔叫你買 ——
    那不是降級的建議，是**錯的**建議（§1）。故本函式一定先取
    `holdings.held_tickers` 再呼叫 L3。

    ⚠️ **總經未評估時仍然出建議**，但 `stance` 是 `unknown`：L3 的契約是
    「只做汰弱、不套攻守」——**不以「中性」代替未評估**（線框 ④ 原文：不猜多空）。
    """
    if not station.requested:
        return SwitchReadout(requested=False, submitted=station.submitted)
    if station.error:
        return SwitchReadout(requested=True, submitted=station.submitted,
                             error=station.error)
    if not station.has_rows:
        return SwitchReadout(requested=True, submitted=station.submitted)
    _exclude = list(holdings.held_tickers)
    try:
        from src.services.dividend_station_service import (
            build_switch_advice,
            get_switch_in_candidates,
        )
        _cands = get_switch_in_candidates(
            regime=(macro.regime or None) if macro.loaded else None,
            exclude=_exclude)
        _adv = build_switch_advice(list(station.rows), _macro_payload(macro), _cands)
    except Exception as _e:  # noqa: BLE001 — 轉成紅態顯示，不吞
        print(f"[views/page_hold] 換股建議失敗 → 轉紅態：{_e!r}")
        return SwitchReadout(requested=True, submitted=station.submitted,
                             error=repr(_e))
    _adv = _adv if isinstance(_adv, Mapping) else {}
    return SwitchReadout(
        requested=True, submitted=station.submitted,
        switch_out=tuple(dict(_d) for _d in (_adv.get("switch_out") or ())),
        switch_in=tuple(dict(_d) for _d in (_adv.get("switch_in") or ())),
        switch_in_src=str(_adv.get("switch_in_src") or ""),
        stance=str(_adv.get("stance") or ""),
        excluded_n=len(_exclude))


def _macro_payload(macro: MacroReadout) -> dict:
    """`MacroReadout` → L3 `build_switch_advice()` 吃的那個 dict。**純轉換。**

    ⚠️ `loaded=False` 時**不填任何攻守值** —— L3 自己會判 `stance="unknown"`。
    在這裡補一個「中性」等於替總經下了一個它沒下的結論（§1）。
    """
    return {
        "loaded": macro.loaded,
        "defense": macro.defense,
        "regime": macro.regime,
        "posture_label": macro.posture_label,
        "posture_range": macro.posture_range,
    }


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

    ⚠️ 為什麼要一個 dataclass 而不是幾組 if：本批接線之後仍未接線的卡有
    **8 張**，共用一句「未接線」會讓使用者以為它們卡在同一步 —— 實際上不是：
    ⑥ 的再平衡 / 壓力測試 / VaR 缺的是 **L3 wrapper**、
    ⑥ 的配息現金流缺的是 **單位換算的落點 ＋ 一個要先拍板的輸入元件**、
    ⑥ 的葡萄串卡在 **L5 寫死的 widget key**、
    ⑦ 的 AI 總結缺的是 **一顆要先出線框拍板的按鈕**（資料已經有了）、
    葉2 的 Sheet 選擇根本不是缺 L3 而是**缺授權**（本頁唯讀）。
    「去哪補」寫錯，比不寫更糟。

    ⚠️ **「持股清單沒有 L3」這個理由本批已經不成立**（`holdings_service` 已補），
    任何一張卡都不得再拿它當 `why` —— 那會叫人去補一支已經在那裡的東西。
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


def _unwired_where(tail: str) -> str:
    """未接線卡的「去哪補」＝ 共同前綴 ＋ **這一張自己**卡在哪。

    ⚠️ `tail` **不得留空、不得兩張卡共用** —— 剩下的未接線卡卡在不同的層
    （缺 L3 wrapper / 缺一個要先拍板的畫面元件 / 本頁不准寫），
    共用一句話會讓「補哪一層才會好」這個唯一有價值的資訊消失。
    守衛：`tests/test_p04_hold_view.py::TestUnwiredStaysUnwired`。
    """
    return UNWIRED_WHERE_PREFIX + tail


# ── ① 結論（三張卡）───────────────────────────────────────────────
#: 線框 ① 的 `cells` 逐字：該做什麼 / 訊號可信度 / 需要處理。
#: **三張卡讀的是三種不同的產出**，所以拆成三支 builder、各自判態：
#:   · 該做什麼   ← digest 的 `reds`/`adds` ＋ `compute_portfolio_totals()`
#:   · 訊號可信度 ← L4 `aggregate_judged()` / `tally_states()`（**分母動態**）
#:   · 需要處理   ← digest 的 `adds`/`reds` ＋ 「有幾列判不全」
#: 一張壞掉不把另外兩張染色（線框：逐格獨立判態）。
CONCLUSION_ACTION_KEY: str = "hold.conclusion.action"
CONCLUSION_CONFIDENCE_KEY: str = "hold.conclusion.confidence"
CONCLUSION_TODO_KEY: str = "hold.conclusion.todo"

#: 「沒有持股」的**三種來源，三套文案，一句都不共用**（檔頭鐵律的落點）。
#:   · 還沒綁 Sheet        → 要你去**綁**
#:   · 綁了但一列都沒有    → 要你去**填**
#:   · 讀到列了但戰情表空  → 那是**上游形狀變了**，要回報
#: 共用一句「沒有持股」等於對其中兩種人指錯路。
NOT_BOUND_NOW: str = "**你還沒有綁定持股 Sheet**"
NOT_BOUND_WHY: str = (
    "**這是一個有效的結果**（已經去讀過，不是還沒讀、也不是故障）—— "
    "戰情室的每一盞燈都以「你實際持有什麼」為輸入，沒有綁定就沒有清單可讀。"
    "本站**不拿範例持股頂替** —— 那會讓你以為畫面上那幾檔是你的。"
    "新使用者在這裡看到灰色是正常的")
NOT_BOUND_WHERE: str = (
    "用 Google 登入後選一本持股 Sheet —— **現行入口在既有的 📁 組合管理分頁**"
    "（本頁只讀不寫，所以不在這裡放選 Sheet 的控制項）；"
    "綁定狀態在下面的**葉2 組合設定**看得到")

EMPTY_SHEET_NOW: str = "**Sheet 綁好了，但裡面還沒有任何一列持股**"
EMPTY_SHEET_WHY: str = (
    "**這是一個有效的結果**（已經讀完，不是還沒讀、也不是故障）—— "
    "空的組合就是空的，本站不把它畫成紅色錯誤。"
    "⚠️ 這與上一種**不是同一件事**：你已經綁好了，缺的是內容")
EMPTY_SHEET_WHERE: str = (
    "到既有的 📁 組合管理分頁新增一本組合並填入持股列（代號／張數／均價），"
    f"填完回本頁{press(ACTION_RUN_WARROOM_LABEL)}")

NO_ROWS_NOW: str = "**讀到了持股，但戰情表一列都沒有回來**"
NO_ROWS_WHY: str = (
    "持股清單讀到了，但 L3 戰情表對它回了空的一批 —— "
    "**這不該發生**（正常情況下一檔持股就對應一列，抓不到的那些會標成錯誤列）。"
    "本站不在這裡自己補一張表：那會讓一個上游的形狀變化看起來像「你沒有持股」")
NO_ROWS_WHERE: str = (
    f"{NO_EXIT_MARKER} —— 這不是你操作的問題；請把這一句連同你的持股檔數"
    "回報給維護者")

#: 上游（持股／戰情表）出事時的出處字串。
SRC_HOLDINGS: str = "L3 持股清單（`services.holdings_service.get_holdings`）"
SRC_STATION: str = (
    "L3 戰情表（`services.dividend_station_service.get_station_rows`）")
SRC_SWITCH: str = (
    "L3 換股建議（`services.dividend_station_service.build_switch_advice` ＋ "
    "`get_switch_in_candidates`）")
#: ⑥ 的三支（本批新增）。**出處分開寫**：三格各自 gate、各自 try/except，
#: 一格炸了只有那一格會紅 —— 出處寫成同一句就分不出是哪一支掛的。
SRC_STRESS: str = (
    "L3 壓力測試（`services.portfolio_deep_service.get_portfolio_stress`）")
SRC_VAR: str = "L3 VaR（`services.portfolio_deep_service.get_portfolio_var`）"
SRC_DIV_CASH: str = (
    "L3 配息現金流（`services.portfolio_deep_service.get_dividend_cash_flow`）")


def _station_note(station: StationReadout, *, now: str, source: str) -> Note:
    """戰情表系列卡片的**非 live** 三要素。四態各自一段，**一段都不共用**。

    ⚠️ `empty` 那一段刻意與 `failed` 分得很開：讀到一份空的持股清單是
    **完全正常**的（新使用者），畫成紅色就是 v3 §02 要杜絕的假性錯誤。
    """
    if not station.requested:
        return _idle_note(station.scope_idle)
    if station.error:
        return Note(now=now, why=_error_why(source, station.error),
                    where=("先確認網路與 Google 授權是否仍有效；"
                           "持續失敗請把上面那行訊息回報給維護者，"
                           f"來源狀態在"
                           f"{ia_nav.where_to_find(ia_nav.SECTION_WHY_DATA_HEALTH)}"))
    if station.holdings_n:
        return Note(now=NO_ROWS_NOW, why=NO_ROWS_WHY, where=NO_ROWS_WHERE)
    if station.bound:
        return Note(now=EMPTY_SHEET_NOW, why=EMPTY_SHEET_WHY, where=EMPTY_SHEET_WHERE)
    return Note(now=NOT_BOUND_NOW, why=NOT_BOUND_WHY, where=NOT_BOUND_WHERE)


def _totals_facts(station: StationReadout) -> list[tuple[str, str]]:
    """金額那幾列。**算不出來就不放這個數字，不填 0**（§1）。"""
    _t = station.totals
    if not _t:
        return [("未實現損益／總市值",
                 "**算不出來** —— 持股缺張數／均價／現價。"
                 "本站在這裡**不填 0**：0 元損益是一個結論，缺值不是")]
    _out = [("未實現損益（元）",
             f"{_t.get('pnl_twd', 0):+,.0f}　（{_t.get('pnl_pct', 0):+.1f}%）"),
            ("總市值（元）", f"{_t.get('value_twd', 0):,.0f}")]
    if _t.get("partial"):
        _held_n, _valued_n = int(_t.get("held_n", 0)), int(_t.get("valued_n", 0))
        _out.append((
            "⚠️ 上面兩個金額只涵蓋一部分",
            f"{_held_n - _valued_n}/{_held_n} 檔持股缺張數或均價，**沒有**納入 —— "
            f"上面兩個數字只涵蓋其餘 {_valued_n} 檔。到 📁 組合管理補齊即可"))
    return _out


def build_action_card(station: StationReadout) -> _Built:
    """線框 ① 第一張：**今天該做什麼** —— 已接線。

    ⚠️ **「沒事」這句話有 gate。** 一句「今天沒有需要動作的部位」與
    「有 3 盞燈根本判不出來」在畫面上長得一模一樣，而處置完全相反（§1）。
    本檔**不自己判**那個 gate —— 巡航那句話由 L4 `cruise_or_gap()` 產生
    （與既有戰情室**同一把尺**），本檔只負責把它顯示出來。
    """
    _state = classify_ui_state(
        requested=station.requested,
        error=station.error or None,
        has_value=station.has_rows)
    _facts: list[tuple[str, str]] = [("檔數", f"{len(station.rows)} 檔")]
    _facts += _totals_facts(station)
    if station.err_n:
        _facts.append(("⚠️ 未納入任何判斷",
                       f"另有 {station.err_n} 檔整批抓取失敗 —— "
                       "它們**沒有**被當成「沒事」，只是這一輪抓不到"))
    _facts.append(("這一句是怎麼來的",
                   "有紅燈／加碼燈就直接列出來（**不排優先序**，兩件事同時成立時"
                   "兩個都講）；都沒有才輪到巡航 gate，而巡航要「每一列的每一盞"
                   "適用燈都判得出來」才准說"))
    if _state != UI_LIVE:
        return (Card(key=CONCLUSION_ACTION_KEY, label="該做什麼", state=_state,
                     note=_station_note(station, now="**本頁還算不出「今天該做什麼」**",
                                        source=SRC_STATION)),
                tuple(_facts), "")
    _parts = ([f"{station.cut_n} 檔亮汰弱紅燈"] if station.cut_n else []) + \
             ([f"{station.add_n} 檔亮加碼燈"] if station.add_n else [])
    _headline = ("今天要看的：" + "、".join(_parts) if _parts
                 else station.cruise_text or "—")
    return (Card(key=CONCLUSION_ACTION_KEY, label="該做什麼", state=UI_LIVE,
                 value=_headline),
            tuple(_facts), "有動作" if _parts else "")


def build_confidence_card(station: StationReadout) -> _Built:
    """線框 ① 第二張：**訊號可信度（N/M 盞給得出判定）** —— 已接線。

    ⚠️ **分母是動態的，本檔一個總數都不寫死。** ETF 8 盞、個股 3 盞
    （4 盞扣掉「依規格就不出等級」的 KD），混合持股的總格數隨組合成分改變。
    分母口徑走 L4 `aggregate_judged()`，與燈牆上每一列的 N/M **同一把尺** ——
    同一頁上兩個不同的分母，使用者只會讀成「有一邊算錯了」。

    ⚠️ **抓取失敗的列留在分母裡**。L2 `missing_light_cells()` 的 docstring
    把理由寫得很清楚：把算不出來的移出分母，畫面會在資料最爛的時候顯示
    可信度最高（§1）。本檔不去動它。
    """
    _state = classify_ui_state(
        requested=station.requested,
        error=station.error or None,
        has_value=station.has_lights)
    _facts: list[tuple[str, str]] = [
        ("分母為什麼不寫死",
         "ETF 8 盞、個股 3 盞（KD 依規格就不出等級，不進分母）—— "
         "總格數隨你的持股檔數與成分改變，寫死就會在下一次變動時變成假話"),
        ("與燈牆的關係", "燈牆每一列的 N/M 與這裡是**同一把尺**（L4 `judged_count`）"),
    ]
    if station.tally:
        _facts.append((
            "四態各有幾格",
            "、".join(f"{_k}：{_v}" for _k, _v in station.tally.items() if _v)
            or "（這一輪一格都沒有）"))
    if station.unjudged_rows:
        _facts.append(("判不全的列",
                       f"{station.unjudged_rows} 列不是「每一盞適用燈都判得出來」—— "
                       "只要有一列不滿足，就不准說「今天沒事」"))
    if _state != UI_LIVE:
        # ⚠️ **「有列、但沒有逐盞燈資料」是另一種空，不可以借用上面那三句。**
        #    （實跑抓到的：借用之後畫面會說「戰情表一列都沒有回來」，
        #    而其實回來了 N 列 —— 那是一句**當場可以被使用者否證的假話**。）
        _note = (Note(now="**有持股，但這一輪算不出訊號可信度**",
                      why=("戰情表回來了，但每一列都沒有帶逐盞燈的判定資料 —— "
                           "**這通常代表這份結果是舊版執行留下的**，"
                           "或上游換了形狀。本站不畫一個 0/0 假裝算過"),
                      where=(f"{press(ACTION_RUN_WARROOM_LABEL)}重跑一次；"
                             "仍然沒有請把這一句回報給維護者"))
                 if (station.has_rows and not station.error)
                 else _station_note(station,
                                    now="**本頁還算不出「幾盞燈判得出來」**",
                                    source=SRC_STATION))
        return (Card(key=CONCLUSION_CONFIDENCE_KEY, label="訊號可信度", state=_state,
                     note=_note),
                tuple(_facts), "")
    return (Card(key=CONCLUSION_CONFIDENCE_KEY, label="訊號可信度", state=UI_LIVE,
                 value=f"{station.judged}/{station.total_lights} 盞給得出判定"),
            tuple(_facts), "")


def build_todo_card(station: StationReadout) -> _Built:
    """線框 ① 第三張：**需要處理** —— 已接線。

    ⚠️ 「未判」與「沒事」不可以合成一個數字：前者是「還不知道」，
    後者是「知道且沒事」。三個數字**各自列出**。
    """
    _state = classify_ui_state(
        requested=station.requested,
        error=station.error or None,
        has_value=station.has_rows)
    _facts: list[tuple[str, str]] = [
        ("加碼 N", "235 加碼燈觸發（digest 的 `adds`）"),
        ("汰弱 N", "健檢紅燈（digest 的 `reds`，與 LINE 每日推播同一組定義）"),
        ("未判 N", "**有幾列判不全** —— 不是「沒事」，是還不知道"),
    ]
    if _state != UI_LIVE:
        return (Card(key=CONCLUSION_TODO_KEY, label="需要處理", state=_state,
                     note=_station_note(
                         station, now="**本頁還列不出「有幾檔需要你處理」**",
                         source=SRC_STATION)),
                tuple(_facts), "")
    return (Card(key=CONCLUSION_TODO_KEY, label="需要處理", state=UI_LIVE,
                 value=(f"加碼 {station.add_n} · 汰弱 {station.cut_n} · "
                        f"未判 {station.unjudged_rows}")),
            tuple(_facts),
            "待處理" if (station.add_n or station.cut_n) else "")


def build_conclusion_cards(station: StationReadout) -> tuple[_Built, ...]:
    """線框葉1 ①「結論（三張卡）」—— **本批三張全部接線**。"""
    return (build_action_card(station), build_confidence_card(station),
            build_todo_card(station))


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
def build_lightwall_card(station: StationReadout) -> _Built:
    """線框葉1 ③ 的「燈牆」那一半 —— **已接線**。

    這張卡只給**整面牆的摘要**；逐檔的燈條由 `_render_light_wall_block()`
    畫在卡下面，走 L4 `render_light_wall()`（**與既有戰情室同一支渲染器**，
    本頁不畫第二種燈格）。

    ⚠️ **本頁一盞燈都不判。** 每一盞燈的等級與四態都在 L2
    `compute.etf.dividend_station`，本檔連「哪一盞算綠」都沒有寫。
    """
    _state = classify_ui_state(
        requested=station.requested,
        error=station.error or None,
        has_value=station.has_rows)
    _facts: list[tuple[str, str]] = [
        ("兩個頻道分開看",
         "**填色＝這盞燈自己的判定**、**外框／紋理＝這盞燈可不可信**（四態）—— "
         "一盞「亮著綠燈但其實沒有資料」的燈，填色會是灰的而且帶斜紋"),
        ("235 加碼燈的紅不是體質差",
         "它的 🔴 是「跌得夠深、該加多少碼」的訊號，不是健康度"),
        ("燈的判定在哪裡",
         "全部在 L2 `compute.etf.dividend_station`；本頁一盞都不判，只顯示"),
    ]
    if station.err_n:
        _facts.append(("⚠️ 抓取失敗的列沒有消失",
                       f"{station.err_n} 檔整批抓取失敗 —— 它們照樣出現在牆上、"
                       "而且**留在分母裡**把可信度拉低（移走分母會讓資料最爛的時候"
                       "顯示可信度最高）"))
    if _state != UI_LIVE:
        return (Card(key="hold.lightwall",
                     label="燈牆（235 加碼燈 · 3-3-3 · 健檢四盞）", state=_state,
                     note=_station_note(station, now="**燈牆點不亮**",
                                        source=SRC_STATION)),
                tuple(_facts), "")
    # ⚠️ **`0/0 盞有判定` 是一句沒有意義的話**（分母 0 不是「都判不出來」，
    #    是「這一輪根本沒有燈可以數」）—— 兩者要用不同的句子講。
    return (Card(key="hold.lightwall",
                 label="燈牆（235 加碼燈 · 3-3-3 · 健檢四盞）", state=UI_LIVE,
                 value=(f"{len(station.rows)} 檔 · "
                        f"{station.judged}/{station.total_lights} 盞有判定"
                        if station.has_lights
                        else f"{len(station.rows)} 檔（這一輪沒有逐盞燈資料）")),
            tuple(_facts), "")


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
def build_switch_card(switch: SwitchReadout, station: StationReadout) -> _Built:
    """線框葉1 ④「換股建議」—— **已接線（換出 ＋ 換入兩半都在）**。

    線框 note 原文：「**v1 漏畫 —— 而它正是本頁職責「該加、該換、該減」的
    那個「該換」。**」

    ⚠️ **換入候選一定帶 `exclude=你已持有的代號`。** 少了它，L3 會從全市場
    排名裡挑出你**已經持有**的那幾檔叫你買 —— 那不是降級的建議，是錯的建議。
    本卡把 `excluded_n` 顯示出來，讓「有沒有真的排除」看得見，
    而不是一句沒有人能驗證的宣稱。

    ⚠️ **總經未評估 → `stance=unknown`，只做汰弱、不套攻守。**
    線框 ④ 原文：「依規則不以「中性」代替 —— 不猜多空」。

    ⚠️ **為什麼要多收一個 `station`**（實測抓到的，不是理論）：空態有**兩種**，
    而它們只有 `station` 分得出來 ——
      · 「你根本沒有持股」（沒綁 / 綁了但空）→ 要你去綁、去填；
      · 「有持股，但這一輪沒有一檔要換」→ 那是**好消息**，要你去看可信度。
    只看 `switch` 的話兩者都是「沒有建議換股」，等於對其中一半的人指錯路。
    """
    _state = classify_ui_state(
        requested=switch.requested,
        error=switch.error or None,
        has_value=switch.has_advice)
    _STANCE = {"defensive": "轉守 → 換入從嚴（少給候選）",
               "aggressive": "偏多 → 換入給滿",
               "neutral": "中性 → 換入給滿",
               "unknown": "**總經未評估 → 只做汰弱，不套攻守**（不猜多空）"}
    # ⚠️ **沒問過的時候不印那個 0。** 「已排除 0 檔」讀起來像「你一檔都沒有持有」，
    #    而冷啟動時本頁根本還沒去看過你持有什麼（§1：0 是一個結論，不是缺值）。
    _facts: list[tuple[str, str]] = [
        ("換入候選已排除的檔數",
         (f"{switch.excluded_n} 檔（你已持有的）—— "
          "少了這個排除，畫面會叫你買你已經有的東西")
         if switch.requested else
         ("接線後這裡會顯示**排除了你已持有的幾檔** —— "
          "少了這個排除，畫面會叫你買你已經有的東西")),
        ("換入的優先序",
         "先看**你自己的觀察清單**裡健檢綠燈的；沒有才 fallback 選股池全自動排名"),
        ("與 ⑤ 的關係", "⑤ 的 80/20 偏離回答「該減」，本格回答「該換」"),
    ]
    if switch.stance:
        _facts.append(("總經攻守閘門", _STANCE.get(switch.stance, switch.stance)))
    if switch.switch_out:
        _facts.append(("建議換出（你持有的紅燈）",
                       "、".join(f"{_d.get('代號', '')}"
                                 f"（{_d.get('建議動作', '')}）"
                                 for _d in switch.switch_out)))
    if switch.switch_in:
        _src = ("你的觀察清單" if switch.switch_in_src == "watchlist"
                else "選股池全自動排名")
        _facts.append((f"建議換入（來源：{_src}）",
                       "、".join(f"{_d.get('代號', '')} {_d.get('名稱', '')}".strip()
                                 for _d in switch.switch_in)))
    if _state == UI_LIVE:
        return (Card(key="hold.switch", label="換股建議（該換）", state=UI_LIVE,
                     value=(f"換出 {len(switch.switch_out)} 檔 → "
                            f"換入 {len(switch.switch_in)} 檔")),
                tuple(_facts),
                "有換股" if switch.switch_out else "")
    if _state == UI_IDLE:
        _note = _idle_note(switch.scope_idle)
    elif _state == UI_FAILED:
        _note = Note(now="**換股建議算不出來**",
                     why=_error_why(SRC_SWITCH, switch.error),
                     where=(f"{NO_EXIT_MARKER} —— 請把上面那行訊息回報給維護者；"
                            "換出那一半只需要你的持股，換入那一半還要選股池，"
                            "兩者任一失敗都會走到這裡"))
    elif not station.has_rows:
        # 沒有持股 ≠ 沒有一檔要換。三種「沒有」在這裡照樣不可以混。
        _note = _station_note(station, now="**還沒有可以換的持股**",
                              source=SRC_STATION)
    else:   # UI_EMPTY —— **有持股，但沒有一檔要換，也是一個結論。**
        _note = Note(
            now="**這一輪沒有建議換股**",
            why=("**這是一個有效的結果**（已經算過，不是還沒算）—— "
                 "你持有的部位裡沒有健檢紅燈可換出，而且觀察清單與選股池"
                 "這一輪也沒有給出可換入的標的。"
                 "本站**不硬湊一檔給你換** —— 那會變成憑空生出來的建議"),
            where=("若你預期應該要有：先看上面 ① 的「訊號可信度」——"
                   "判不出來的燈不會變成紅燈，也就不會被列為換出；"
                   f"補齊資料後{press(ACTION_RUN_WARROOM_LABEL)}再看一次"))
    return Card(key="hold.switch", label="換股建議（該換）",
                state=_state, note=_note), tuple(_facts), ""


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
        # 誠實揭露：這條帶子與 ⑤「建議持股水位（市場端）」**口徑不同** ——
        # 它是 `get_station_macro()` 直接 `compute_position_throttle()` 的產出，
        # **沒有**經過 L3 `get_allocation()` 的天花板仲裁（§2.1 SSOT）。
        # ⚠️ 只加說明：**不改取數來源、不拿掉這一格**（那是版面／功能變更，
        #    依 `CLAUDE.md §-1.5` A-8「草稿先行」要先送客戶拍板）。
        _facts.append(
            ("姿態油門帶（**未套天花板的原始帶**）",
             f"{macro.posture_range} —— 這是 L3 `get_station_macro()` 直接給的"
             "姿態帶，**沒套** VIX／三環／`exposure_limit_pct` 任何一條天花板。"
             "**最終水位請看 ⑤「建議持股水位（市場端）」那一格**"
             "（走 `get_allocation()`，已套天花板）—— "
             "同一頁的兩個持股區間口徑不同，別把它們讀成同一個數字"))

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
def _split_facts(station: StationReadout) -> list[tuple[str, str]]:
    """核心／衛星那兩張卡共用的中繼資料列（**同一支 L3、同一份數字**）。"""
    _facts: list[tuple[str, str]] = [
        ("目標（L0 SSOT）",
         f"核心 {CORE_TARGET_PCT:g}／衛星 {SATELLITE_TARGET_PCT:g}"),
        ("近似法的已知限制",
         "核心＝ETF、衛星＝個股是以**代號型別**近似；主題型 ETF 會被算成核心"),
        ("只納入有市值的持有列",
         "缺張數／均價的持有列**不進分子也不進分母** —— 硬算等於替你編一個比例"),
    ]
    _sp = station.split
    if _sp and _sp.get("partial"):
        _facts.append((
            "⚠️ 這個比例只涵蓋一部分",
            f"{int(_sp.get('held_n', 0))} 檔持有列裡只算了 "
            f"{int(_sp.get('valued_n', 0))} 檔（其餘缺金額）—— **僅供參考**"))
    return _facts


def build_allocation_split_card(station: StationReadout) -> _Built:
    """線框葉1 ⑤ 的「80/20 配置偏離」那一半 —— **已接線**。

    ⚠️ 它與 `build_position_cap_card()`（建議持股水位）**不是同一件事**：
    本格問的是「你手上那一堆，核心與衛星各佔多少」（**組合內部**的比例），
    那一格問的是「整體該擺多少在股票上」（**市場端**的上限）。**分母不同。**
    """
    _state = classify_ui_state(
        requested=station.requested,
        error=station.error or None,
        has_value=station.split is not None)
    _facts = _split_facts(station)
    _sp = station.split
    if _state == UI_LIVE and _sp:
        _dev = float(_sp.get("core_dev", 0.0))
        _facts.insert(0, ("核心偏離目標", f"{_dev:+.1f} 個百分點"))
        return (Card(key="hold.alloc_split", label="80/20 配置偏離（該減）",
                     state=UI_LIVE,
                     # §4.1：單位要寫出來 —— 「核心 100.0」看不出是百分比還是檔數。
                     # ⚠️ 這兩個數字**來自 L3**，不是本檔寫死的持股百分比
                     # （`tests/test_no_hardcoded_position_pct.py` 掃的是字面常數）。
                     value=(f"核心 {float(_sp.get('core_pct', 0)):.1f}%"
                            f" ／ 衛星 {float(_sp.get('sat_pct', 0)):.1f}%")),
                tuple(_facts),
                "偏離" if abs(_dev) >= 1 else "接近目標")
    if _state == UI_IDLE:
        _note = _idle_note(station.scope_idle)
    elif _state == UI_FAILED:
        _note = Note(now="**核心／衛星的實際配置算不出來**",
                     why=_error_why(SRC_STATION, station.error),
                     where=(f"{NO_EXIT_MARKER} —— 請把上面那行訊息回報給維護者"))
    elif not station.has_rows:
        _note = _station_note(station, now="**還沒有可以拆的持股**",
                              source=SRC_STATION)
    else:   # 有列、但一列都沒有市值
        _note = Note(
            now="**有持股，但算不出核心／衛星的比例**",
            why=("**這是一個有效的結果**（已經算過，不是還沒算）—— "
                 "你的持有列裡沒有任何一列同時有張數與現價，"
                 "沒有市值就沒有比例。本站**不用檔數當比例頂替** —— "
                 "三檔各一張與三檔各一百張，配置完全不同"),
            where=("到既有的 📁 組合管理分頁把持股的**張數**與**均價**補齊，"
                   f"回本頁{press(ACTION_RUN_WARROOM_LABEL)}"))
    return Card(key="hold.alloc_split", label="80/20 配置偏離（該減）",
                state=_state, note=_note), tuple(_facts), ""


def build_take_profit_card(station: StationReadout) -> _Built:
    """線框葉1 ⑤ 的「衛星停利」那一半 —— **已接線**。

    ⚠️ **「沒有一檔達門檻」是 `empty`（灰），而且是好消息，不是故障。**
    ⚠️ **沒有成本就不判**：L3 只對有損益% 的持有衛星列判定 ——
    硬判等於替你編一個報酬率（§1）。
    """
    _state = classify_ui_state(
        requested=station.requested,
        error=station.error or None,
        has_value=bool(station.take_profit))
    _facts: list[tuple[str, str]] = [
        ("門檻（L0 SSOT）",
         f"衛星獲利達 {SATELLITE_TAKE_PROFIT_PCT:g} 個百分點即嚴格停利滾回核心"),
        ("為什麼缺成本就不判", "沒有均價就沒有損益%，硬判等於替你編一個報酬率"),
        ("只判衛星（個股）", "核心（ETF）走定期定額，不套這條停利規則"),
    ]
    if _state == UI_LIVE:
        _facts.insert(0, ("達門檻的衛星",
                          "、".join(f"{_d.get('代號', '')}"
                                    f"（{_d.get('損益%', '')}%）"
                                    for _d in station.take_profit)))
        return (Card(key="hold.take_profit", label="衛星停利", state=UI_LIVE,
                     value=f"{len(station.take_profit)} 檔達停利門檻"),
                tuple(_facts), "可停利")
    if _state == UI_IDLE:
        _note = _idle_note(station.scope_idle)
    elif _state == UI_FAILED:
        _note = Note(now="**停利判不出來**",
                     why=_error_why(SRC_STATION, station.error),
                     where=(f"{NO_EXIT_MARKER} —— 請把上面那行訊息回報給維護者"))
    elif not station.has_rows:
        _note = _station_note(station, now="**還沒有可以判停利的持股**",
                              source=SRC_STATION)
    else:
        _note = Note(
            now="**沒有任何一檔衛星達停利門檻**",
            why=("**這是一個有效的結果**（已經逐檔判過，不是還沒判）—— "
                 "可能是還沒漲到門檻，也可能是那幾檔沒有均價因此**判不了**。"
                 "本站不把「判不了」講成「沒達標」：兩者在這張卡上都是灰的，"
                 "但下面那一列會告訴你缺的是什麼"),
            where=("若你預期應該要有：到 📁 組合管理確認那幾檔**個股**的均價有填；"
                   f"補齊後回本頁{press(ACTION_RUN_WARROOM_LABEL)}"))
    return Card(key="hold.take_profit", label="衛星停利",
                state=_state, note=_note), tuple(_facts), ""


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
        ("來源", "L3 `get_allocation()`，本頁不自行再算 —— 它仲裁"
                 "「姿態油門 × macro_state 曝險上限 × VIX／三環天花板」"
                 "三條輸入，**取最低**"),
        # 誠實揭露：舊文案寫「全站唯一的建議持股 SSOT」，實測為假。
        # 只把「全站唯一」四個字刪掉不夠 —— 讀者仍會以為全站只有這一處。
        ("⚠️ 這**不是**全站唯一的持股水位算法",
         "全站另有**沒進到上面那道仲裁**的獨立算法：每日推播的 "
         "`market_alert_banner`、v4 否決權的 `max_position`、"
         "`market_strategy` 的 `exposure_pct`；"
         "**連本頁 ④ 那格的「姿態油門帶」也是** —— 它走 `get_station_macro()`，"
         "**沒套任何天花板**。要看最終水位，以本格為準"),
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
#: 線框 ⑥ `live` 原文逐字的六項。**本批之後未接線的只剩兩項**，
#: 而且它們卡的**不是同一件事**（共用一句話會讓「補哪一層才會好」消失）：
#:   (a) **再平衡** —— 不是缺 L3 wrapper（`portfolio_deep_service` 已經在了），
#:       是**帳本沒有目標權重那一欄**；要讓使用者填＝新增畫面元件（A-8）。
#:   (b) **葡萄串領息** —— 實作在 L5、自帶寫死的 widget key。
#: 其餘四項（核心／衛星 · 壓力測試 · VaR · 配息現金流）**都已接線**。
DEEP_SPECS: tuple[UnwiredSpec, ...] = (
    UnwiredSpec(
        key="hold.deep.rebalance", label="再平衡",
        now="**再平衡未接線**",
        why=("**這一格缺的不是 L3 wrapper** —— 本批補的 "
             "`services.portfolio_deep_service` 就在那裡，隔壁的壓力測試與 VaR "
             "走的就是它。缺的是**目標權重**：再平衡是「實際權重 vs "
             "**你想要的**目標權重」的比較，而你的持股帳本那張表只有 "
             "`name / ticker / lots / avg_price / updated_at` 五欄，"
             "**沒有目標比例**。若拿現況當目標，偏離度必然是 0.0% —— "
             "那不是「已平衡」而是「沒算」（L2 `portfolio_gates."
             "evaluate_rebalance_gate` 對這種輸入的判定就是「⚪ 無法判定」）"),
        where=_unwired_where(
            "要接上需先讓你能填「目標比例%」—— 那是**新增一個畫面元件**，"
            "依 `CLAUDE.md §-1.5` A-8 要先出線框草稿給客戶拍板，不在本批。"
            "**也不會**改用 `compute.strategy.portfolio_manager."
            "CoreSatelliteManager` 頂替：它的核心比例是另一套（依市場狀態 "
            "0.60~0.85），與本頁 ⑤／⑥ 用的 L0 80/20 目標不同 —— "
            "同一頁出現兩個互相矛盾的核心比例，比少一格糟糕得多（§2.1 SSOT）"),
        facts=(("卡住的層", "**不是** L3 —— 是你的帳本沒有「目標比例」這一欄"),
               ("持股清單", "✅ 已接線（`holdings_service`）—— 不是卡在這裡"),
               ("L3 wrapper", "✅ 已補（`portfolio_deep_service`）—— 也不是卡在這裡"),
               ("為什麼不拿現況當目標",
                "偏離度會恆等於 0.0%，畫面永遠是綠的 —— "
                "那個綠燈代表「沒算」而不是「已平衡」（§1）"))),
    UnwiredSpec(
        key="hold.deep.grape", label="葡萄串領息",
        now="**葡萄串領息未接線**",
        why=("這一格的實作**住在 L5**（`tabs.grape_ladder`）而不是 L3，"
             "而且它自帶寫死的 widget key —— 在本頁再掛一次會撞 "
             "`DuplicateWidgetID`，那不是「畫得醜」，是**整頁當場拋例外**"),
        where=_unwired_where(
            "要接上需先讓現行實作能被外部重複掛載（widget key 加前綴參數、"
            "取數改走 L3、gate 由 caller 提供）—— 那是改既有分頁，"
            "落在 §8.4 step 4 的範圍閘門，不在本批"),
        facts=(("卡住的層", "實作在 L5、自帶寫死的 widget key"),
               ("現行入口", "既有的 🏦 ETF 分頁（本頁不重複掛載）"))),
)


# ══════════════════════════════════════════════════════════════════
# ⑥ 的取數：壓力測試 / VaR / 配息現金流（**本批新接線，全部唯讀**）
# ══════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class DeepReadout:
    """⑥ 三格的 L3 產出。**一次 `load_deep()`，三張卡共用，各自持有自己的錯誤。**

    ⚠️ **為什麼三個 error 欄位而不是一個**：線框 ⑥ 寫「區塊並列 · **各自 gate**」。
    壓測要打 `fetch_etf_info`、VaR 要打 `fetch_etf_price`、配息要打
    `fetch_etf_dividends` —— 三條上游各自會掛。用一個 error 欄位，
    任何一條掛掉都會把另外兩格一起染紅，使用者會以為整個組合分析壞了。

    Attributes:
        requested: 由 `StationReadout.requested` 帶下來（**不是**從資料反推）。
        submitted: 只用來分流 `idle` 的**文案**（冷啟動 vs 選了不讀 Google）。
        bound / holdings_n: 「三種沒有不可混」用的兩個事實，原樣從戰情表帶下來。
        has_station_rows: 戰情表這一輪有沒有列。**空清單時本函式一行 L3 都不呼叫**
            （對空清單跑一次逐檔抓取沒有意義），但 `requested` 仍然是 `True`。
        stress / var / cash: 三支 L3 的回傳（`None` = 沒跑到或炸了）。
        stress_error / var_error / cash_error: 各自的呼叫期例外。
        error: **上游**（戰情表／持股清單）帶下來的例外 —— 這一種是三格全紅，
            因為三格的輸入都沒有了。
    """

    requested: bool
    submitted: bool = False
    bound: bool = False
    holdings_n: int = 0
    has_station_rows: bool = False
    stress: Any = None
    var: Any = None
    cash: Any = None
    stress_error: str = ""
    var_error: str = ""
    cash_error: str = ""
    error: str = ""

    @property
    def scope_idle(self) -> bool:
        """同 `StationReadout.scope_idle` —— 只做 idle 的**文案**分流。"""
        return bool(self.submitted and not self.requested)


def load_deep(station: StationReadout) -> DeepReadout:
    """⑥ 的三支 L3。**`station.requested` 為 False 時一行 L3 都不呼叫。**

    ⚠️ **戰情表是空的時候也不呼叫。** 那不是把 gate 從資料反推 ——
    `requested` 照樣是 `True`（使用者確實叫過），只是「對空清單算 VaR」
    沒有任何意義。回傳的三個 `None` 讓卡片落在 `empty`（灰），這正確：
    **叫過了、沒有錯、就是沒有東西可以算。**

    ⚠️ **三支各自包 try/except**：一支掛掉只有那一格轉紅（線框：逐格獨立判態）。
    上游（持股／戰情表）的例外則是三格全紅 —— 那一種是輸入本身沒有了。

    ⚠️ **本函式不做任何算術。** 張→股→元 的換算、權重、分位數全部住在
    L3 `portfolio_deep_service`（§4.1：同一個乘法不得散在 UI 各處）。
    """
    _shared = {"submitted": station.submitted, "bound": station.bound,
               "holdings_n": station.holdings_n}
    if not station.requested:
        return DeepReadout(requested=False, submitted=station.submitted)
    if station.error:
        return DeepReadout(requested=True, error=station.error, **_shared)
    if not station.has_rows:
        return DeepReadout(requested=True, **_shared)

    # ⚠️ **三支各自具名 import，不用 `getattr(module, name)`**：
    # 動態取屬性會直接繞過 `tests/test_p04_hold_view.py::TestReadOnly` 的
    # **符號白名單**（它掃的是 `ast.ImportFrom`）—— 那道護欄的意義就沒了。
    try:
        from src.services.portfolio_deep_service import (
            get_dividend_cash_flow,
            get_portfolio_stress,
            get_portfolio_var,
        )
    except Exception as _e:  # noqa: BLE001 — 整支 L3 進不來 = 三格都沒有輸入
        print(f"[views/page_hold] ⑥ 深度分析 L3 import 失敗 → 三格轉紅態：{_e!r}")
        return DeepReadout(requested=True, has_station_rows=True, **_shared,
                           stress_error=repr(_e), var_error=repr(_e),
                           cash_error=repr(_e))
    _rows = [dict(_r) for _r in station.rows]
    _stress, _stress_err = _guarded(get_portfolio_stress, _rows, "壓力測試")
    _var, _var_err = _guarded(get_portfolio_var, _rows, "VaR")
    _cash, _cash_err = _guarded(get_dividend_cash_flow, _rows, "配息現金流")
    return DeepReadout(
        requested=True, has_station_rows=True, **_shared,
        stress=_stress, var=_var, cash=_cash,
        stress_error=_stress_err, var_error=_var_err, cash_error=_cash_err)


def _guarded(fn, rows: list[dict], label: str) -> tuple[Any, str]:
    """跑一支 ⑥ 的 L3，把**呼叫期**例外轉成字串。

    ⚠️ **一格一個 try** —— 三格共用一個 try 的話，先炸的那一支會讓後兩支
    根本沒跑到，畫面上卻是三格全紅：使用者會以為整個組合分析壞了，
    而實際上只有一條上游掛掉（線框 ⑥：區塊並列 · 逐格獨立判態）。
    """
    try:
        return fn(rows), ""
    except Exception as _e:  # noqa: BLE001 — 轉成紅態顯示，不吞、不染色鄰格
        print(f"[views/page_hold] ⑥ {label} 取數失敗 → 該格轉紅態：{_e!r}")
        return None, repr(_e)


def _deep_note(deep: DeepReadout, *, now: str, source: str,
               error: str) -> Note:
    """⑥ 三格的**非 live** 三要素。四態各自一段，一段都不共用。

    ⚠️ `empty` 分兩層：**戰情表本身沒有列**（走 `_station_note` 那三句：
    還沒綁 / 綁了但空 / 有持股但一列都沒回來）與**有列但算不出來**
    （那一句由呼叫端自己寫，因為每一格缺的東西不同）。
    """
    if not deep.requested:
        return _idle_note(deep.scope_idle)
    if error or deep.error:
        return Note(now=now, why=_error_why(source, error or deep.error),
                    where=(f"{NO_EXIT_MARKER} —— 請把上面那行訊息回報給維護者；"
                           "若只有這一格紅、其餘幾格正常，"
                           "那就是這一條上游單獨掛了，不是整個組合分析壞掉"))
    if deep.holdings_n:
        return Note(now=NO_ROWS_NOW, why=NO_ROWS_WHY, where=NO_ROWS_WHERE)
    if deep.bound:
        return Note(now=EMPTY_SHEET_NOW, why=EMPTY_SHEET_WHY,
                    where=EMPTY_SHEET_WHERE)
    return Note(now=NOT_BOUND_NOW, why=NOT_BOUND_WHY, where=NOT_BOUND_WHERE)


def _deep_reason(result: Any) -> str:
    """L3 給的「算不出來的原因」。**沒有給就誠實說沒有給**，不留一個空句。

    ⚠️ 這裡刻意不編一個原因 —— 「上游沒有說為什麼」本身就是要講出來的事實
    （對照 `UNKNOWN_ERROR_TEXT` 的同一個做法）。
    """
    return str(getattr(result, "reason", "") or "") or UNKNOWN_ERROR_TEXT


def _valued_facts(result: Any) -> list[tuple[str, str]]:
    """「這個數字涵蓋了你幾檔持股」——`partial` 時**必須講**（§1）。

    不講的話，使用者會把「三檔裡只算了一檔」的風險數字當成整個組合的風險。
    """
    _facts: list[tuple[str, str]] = []
    _valued = getattr(result, "valued_n", None)
    _held = getattr(result, "held_n", None)
    if isinstance(_valued, int) and isinstance(_held, int) and _held:
        _facts.append(("涵蓋範圍",
                       f"{_held} 檔持有列裡納入了 {_valued} 檔"
                       + ("（其餘缺張數／均價／現價 —— **不進分子也不進分母**）"
                          if _valued < _held else "")))
    if getattr(result, "reconciled", True) is False:
        _facts.append((
            "⚠️ 兩套算法對不起來",
            _reconcile_gap_text(result)
            + " —— 代表兩邊納入的持股列不是同一批。"
              "**這一格因此判「已失準」（橘），不是「運作中」（綠）**"))
    return _facts


def _reconcile_gap_text(result: Any) -> str:
    """§4.3 對帳差多少。**差額算不出來就說算不出來**，不寫一個看起來像 0 的數字。

    ⚠️ 只用 `getattr` 讀**現有**欄位，不依賴任何尚未落地的 L3 新欄位。
    ⚠️ 除法前用容差擋 0（§6：浮點不用 `==`）—— 對照值真的是 0 時，
    「差 100%」是個沒有意義的數字，寧可說「占比算不出來」。
    """
    _own_raw = getattr(result, "total_value_twd", None)
    _ref_raw = getattr(result, "reference_value_twd", None)
    try:
        _own, _ref = float(_own_raw), float(_ref_raw)
    except (TypeError, ValueError):
        return ("本格的總市值與 ① 那張卡的 L3 `compute_portfolio_totals()` 對不上"
                f"（本格 {_own_raw!r}／對照 {_ref_raw!r} —— "
                "其中一邊不是數字，差額算不出來）")
    _gap = abs(_own - _ref)
    return ("本格的總市值與 ① 那張卡的 L3 `compute_portfolio_totals()` 對不上："
            f"本格納入 {_own:,.0f} 元、對照 {_ref:,.0f} 元，差 {_gap:,.0f} 元"
            + (f"（差 {_gap / abs(_ref) * 100.0:.1f}%）" if abs(_ref) > 1e-9
               else "（對照值為 0，差幾 % 算不出來）"))


def _degraded_bits(result: Any) -> list[tuple[str, str]]:
    """讓 ⑥ 這個金額**失去判別力**的原因 → `(為什麼失準, 去哪補)`。

    空 list ＝ 這個數字還有判別力（→ `UI_LIVE`）。非空 ＝ `UI_DEGRADED`（橘）。

    ⚠️ **兩種情形都不是「系統壞了」**（那是 `UI_FAILED` / 紅，走 `error` 那條）——
    是「**算得出來、但打了折**」。混成紅色就是製造假警報，而滿版假紅字會讓
    真的故障沒人看得見（`CLAUDE.md §1.A-4`「介面狀態嚴格分離」）。

    ⚠️ **只讀 L3 現有欄位**（`reconciled` / `reference_value_twd` /
    `total_value_twd` / `no_price` / `held_n`），一律 `getattr` 帶預設 ——
    沒有這些欄位的結果型別（實測 2026-09-07：`DividendCashResult` 兩個都沒有）
    自然回空 list，行為不變。
    """
    _bits: list[tuple[str, str]] = []
    if getattr(result, "reconciled", True) is False:
        _bits.append((
            "**兩套算法對不起來** —— " + _reconcile_gap_text(result)
            + "。兩邊的納入條件是各寫各的（這正是對帳的意義），"
              "對不上就代表其中一邊漏了列或多算了列，"
              "**本頁不替任何一邊背書**",
            "到既有的 📁 組合管理分頁把持股的**張數／均價**補齊"
            "（兩套算法差的多半就是那幾列），"
            f"再回本頁{press(ACTION_RUN_WARROOM_LABEL)}"))
    _no_price = tuple(getattr(result, "no_price", ()) or ())
    if _no_price:
        _held = getattr(result, "held_n", None)
        _bits.append((
            f"**有 {len(_no_price)} 檔抓不到價格序列**"
            + (f"（持有 {_held} 檔）" if isinstance(_held, int) and _held else "")
            + "：" + "、".join(_no_price)
            + " —— 抓不到就**不納入**（不是當成 0% 報酬），"
              "所以這個尾部估計**涵蓋不到這幾檔的風險**，"
              "缺的那幾檔真的大跌時不會反映在這個數字裡",
            "先確認這幾檔的代號是否正確（本頁顯示的是正規化後的代號）；"
            "若是新上市／剛買進的標的，等歷史累積起來才會有價格序列，"
            f"再回本頁{press(ACTION_RUN_WARROOM_LABEL)}"))
    return _bits


def _degraded_note(label: str, bits: Sequence[tuple[str, str]]) -> Note:
    """⑥ 的「有值但失準」三要素。**橘，不是紅**；現值由呼叫端掛在 facts。

    Raises:
        ValueError: `bits` 為空（§1 Fail Loud）。判成 degraded 卻說不出哪裡失準，
            代表判定與理由脫節 —— 那時畫面會出現一張說不清自己為什麼是橘的卡，
            比直接炸掉危險。
    """
    if not bits:
        raise ValueError(
            f"{label} 判成 {UI_DEGRADED!r} 卻沒有給任何失準原因 —— "
            "`_degraded_bits()` 與 `classify_ui_state(discriminative=...)` "
            "必須由同一份判定供給")
    _wheres: list[str] = []
    for _, _where in bits:
        if _where not in _wheres:      # 兩個原因同時成立時不重複同一句出口
            _wheres.append(_where)
    return Note(
        now=f"{label}　**算得出來，但這個數字已經失準** —— 現值見上方「現值」列",
        why="；又，".join(_why for _why, _ in bits),
        where="；".join(_wheres))


def build_stress_card(deep: DeepReadout) -> _Built:
    """線框 ⑥ 的「壓力測試」—— **本批新接線**。

    ⚠️ **Beta 缺值會被 L2 以 1.0 估算** —— 那一列必須揭示出來（§1 帶旗標）。
    ⚠️ 金額是**元**（L3 已在 `_lot_to_shares()` 乘過每張股數），本頁不做任何換算。
    ⚠️ **對帳失敗（`reconciled=False`）→ 橘的 `UI_DEGRADED`，不是綠的。**
    金額照給（掛在 facts 的「現值」列），但不再當結論、不再出燈號 ——
    綠燈配一行小字等於讓人把一個已知失準的數字讀成結論（§1）。
    """
    _res = deep.stress
    _degraded = _degraded_bits(_res) if _res is not None else []
    _state = classify_ui_state(
        requested=deep.requested,
        error=deep.stress_error or deep.error or None,
        has_value=bool(_res is not None and _res.computed),
        discriminative=not _degraded)
    _facts: list[tuple[str, str]] = [
        ("這不是預測", "它回答的是「同樣的跌幅打在**你這個組合**上會是多少」，"
                       "不是「大盤會不會跌」"),
    ]
    # ⚠️ **跌幅只在 L3 真的回了東西時才印。** 沒有結果時 `getattr(..., 0.0)`
    # 會印成「假設大盤下跌 0 個百分點」—— 那是一個假的情境設定，
    # 比不印糟糕得多（§1：本頁自己不持有這個門檻，它只由 L0 經 L3 帶下來）。
    if _res is not None:
        _facts.insert(0, ("情境（L0 SSOT）",
                          f"假設大盤下跌 {abs(float(_res.drop_pct)):g} 個百分點，"
                          "以各檔 Beta 加權估算回撤"))
    _facts += _valued_facts(_res)
    if _res is not None and getattr(_res, "beta_imputed", ()):
        _facts.append((
            "⚠️ 這幾檔的 Beta 是估的",
            "、".join(_res.beta_imputed)
            + " —— 查無 Beta，L2 以 1.0 估算後納入（**不是真實 Beta**）"))
    if _state in (UI_LIVE, UI_DEGRADED) and _res is not None:
        _facts.insert(1, ("納入計算的組合總市值（元）",
                          f"{_res.total_value_twd:,.0f}"))
        _facts.insert(2, ("警示門檻（L0 SSOT）",
                          f"回撤大於總市值的 {_res.warn_pct:g} 個百分點就示警"))
        # §4.1：單位寫出來 —— 「-224,000」看不出是元還是張。
        _shown = f"約 {abs(_res.loss_twd):,.0f} 元（{_res.loss_pct:.1f}%）"
        if _state == UI_LIVE:
            return (Card(key="hold.deep.stress", label="壓力測試", state=UI_LIVE,
                         value=_shown),
                    tuple(_facts),
                    "超過門檻" if _res.warn else "門檻內")
        # `Card` 規定非 live 不得帶結論文字 → 現值改掛 facts（`page_today` 同款做法）。
        # **數字不藏起來**，只是不再當結論；燈號頻道一併留白 ——
        # 一邊掛「🟠 門檻已失準」一邊出「門檻內」是同一張卡說兩句相反的話。
        _facts.insert(0, ("現值（已失準，別照門檻讀）", _shown))
        return (Card(key="hold.deep.stress", label="壓力測試",
                     state=UI_DEGRADED,
                     note=_degraded_note("壓力測試", _degraded)),
                tuple(_facts), "")
    if _state == UI_IDLE:
        _note = _idle_note(deep.scope_idle)
    elif _state == UI_FAILED:
        _note = _deep_note(deep, now="**壓力測試算不出來**", source=SRC_STRESS,
                           error=deep.stress_error)
    elif not deep.has_station_rows:
        _note = _deep_note(deep, now="**還沒有可以壓測的持股**",
                           source=SRC_STRESS, error="")
    else:
        _note = Note(
            now="**有持股，但壓力測試算不出來**",
            why=("**這是一個有效的結果**（已經算過，不是還沒算）—— "
                 + _deep_reason(_res)
                 + "。本站不用檔數當權重頂替：三檔各一張與三檔各一百張，"
                   "承受同一個跌幅的損失完全不同"),
            where=("到既有的 📁 組合管理分頁把持股的**張數**與**均價**補齊，"
                   f"回本頁{press(ACTION_RUN_WARROOM_LABEL)}"))
    return Card(key="hold.deep.stress", label="壓力測試",
                state=_state, note=_note), tuple(_facts), ""


def build_var_card(deep: DeepReadout) -> _Built:
    """線框 ⑥ 的「VaR」—— **本批新接線**。

    ⚠️ **對齊規則整段交給 L2** `align_portfolio_returns`：只取「全員皆有交易」
    的共同日，**絕不** ffill／fillna(0)。補 0 會稀釋波動、讓尾部看起來比實際小。
    ⚠️ **樣本短就不報**：共同交易日不足一個月時 L3 回 `computed=False` ——
    畫面顯示灰的「算不出來」，**不報一個樣本三天的 VaR**。
    """
    _res = deep.var
    # ⚠️ **取價那一層整個掛掉 → 紅，不是灰**（v3 §02「介面狀態嚴格分離」）。
    # L3 把「回空資料」（這一檔沒有那段歷史 → 灰、有效結果）與「拋例外」
    # （上游壞了 → 紅）分成兩個欄位。混成一種的話，Yahoo 掛掉的那一天
    # 使用者會以為「我的股票太新所以算不出來」，而**真的**壞掉那一次
    # 沒有人看得見 —— 那是「假性錯誤滿版」的反面：**假性正常**。
    _dead_src = ("；".join(_res.fetch_errors)
                 if _res is not None and _res.upstream_down else "")
    # ⚠️ **「部分沒價格」與「上游整個掛掉」是兩件事，兩件都不吞。**
    # 上一段的 `_dead_src` 走 error → 紅；這裡的 `no_price` 走 discriminative
    # → 橘（有值、但涵蓋不到那幾檔）。混成同一種，其中一件必然被另一件蓋掉。
    _degraded = _degraded_bits(_res) if _res is not None else []
    _state = classify_ui_state(
        requested=deep.requested,
        error=deep.var_error or deep.error or _dead_src or None,
        has_value=bool(_res is not None and _res.computed),
        discriminative=not _degraded)
    _facts: list[tuple[str, str]] = [
        ("這個數字的意思",
         "在正常市況下，單日虧損**不超過**這個金額的機率約 95%（另一個是 99%）"),
        ("樣本怎麼取", "只取「當天全部持股都有交易」的共同日 —— "
                       "缺的日子一律剔除，**不補 0、不 ffill**（補了會低估尾部風險）"),
        ("已知限制", "日報酬是**原幣別**報酬；外幣計價的持股未含匯率變動"),
    ]
    _facts += _valued_facts(_res)
    if _res is not None and getattr(_res, "no_price", ()):
        _facts.append(("⚠️ 這幾檔沒有價格序列",
                       "、".join(_res.no_price)
                       + " —— 抓不到就**不納入**（不是當成 0% 報酬）"))
    if _state in (UI_LIVE, UI_DEGRADED) and _res is not None:
        _facts.insert(1, ("樣本",
                          f"{_res.n_common} 個共同交易日"
                          + (f"（{_res.first_day} ~ {_res.last_day}）"
                             if _res.first_day else "")
                          + f"；聯集 {_res.n_union} 日，剔除 {_res.dropped} 個非共同日"))
        _facts.insert(2, ("99% 單日", f"約 {_res.hist_99_twd:,.0f} 元（歷史模擬法）"))
        _facts.insert(3, ("參數法（常態假設）對照",
                          f"95% 約 {_res.param_95_twd:,.0f} 元 ／ "
                          f"99% 約 {_res.param_99_twd:,.0f} 元 —— "
                          "肥尾時歷史模擬法通常比它保守"))
        _facts.insert(4, ("月度 99%（√一個月交易日 近似）",
                          f"約 {_res.monthly_99_twd:,.0f} 元"
                          f"，占總市值 {_res.monthly_99_pct:.2f}%"
                          f"（示警門檻 {_res.warn_pct:g}）"))
        if _res.window_squeezed and _res.limiter:
            _facts.append((
                "⚠️ 樣本視窗被壓縮",
                f"最晚有資料的是 {_res.limiter}"
                + (f"（{_res.limiter_start} 才開始）" if _res.limiter_start else "")
                + " —— 視窗越短，尾部估計越樂觀"))
        _shown = f"單日 95%：約 {_res.hist_95_twd:,.0f} 元"
        if _state == UI_LIVE:
            return (Card(key="hold.deep.var", label="VaR（風險值）",
                         state=UI_LIVE, value=_shown),
                    tuple(_facts),
                    "月度尾部偏高" if _res.warn else "月度尾部可控")
        # `Card` 規定非 live 不得帶結論文字 → 現值改掛 facts（`page_today` 同款做法）。
        # 燈號頻道留白：門檻已失準卻還出「月度尾部可控」，是同一張卡說兩句相反的話。
        _facts.insert(0, ("現值（已失準，別照門檻讀）", _shown))
        return (Card(key="hold.deep.var", label="VaR（風險值）",
                     state=UI_DEGRADED,
                     note=_degraded_note("VaR（風險值）", _degraded)),
                tuple(_facts), "")
    if _state == UI_IDLE:
        _note = _idle_note(deep.scope_idle)
    elif _state == UI_FAILED:
        _note = _deep_note(deep, now="**VaR 算不出來**", source=SRC_VAR,
                           error=deep.var_error or _dead_src)
    elif not deep.has_station_rows:
        _note = _deep_note(deep, now="**還沒有可以算 VaR 的持股**",
                           source=SRC_VAR, error="")
    else:
        _note = Note(
            now="**有持股，但 VaR 算不出來**",
            why=("**這是一個有效的結果**（已經算過，不是還沒算）—— "
                 + _deep_reason(_res)
                 + "。本站寧可不給，也不給一個用補值撐出來的尾部估計："
                   "把缺的交易日填成 0% 報酬會讓風險看起來比實際小（§1）"),
            where=("若是新上市／剛買進的標的，等歷史累積到至少一個月的共同交易日"
                   f"再回本頁{press(ACTION_RUN_WARROOM_LABEL)}；"
                   "若是缺張數／均價，到既有的 📁 組合管理分頁補齊"))
    return Card(key="hold.deep.var", label="VaR（風險值）",
                state=_state, note=_note), tuple(_facts), ""


def build_dividend_cash_card(deep: DeepReadout) -> _Built:
    """線框 ⑥ 的「配息現金流」—— **本批新接線，但只接了不需要稅率的那一半**。

    ⚠️ **不含綜所稅，卡面必須講。** 稅率是使用者輸入，而新增輸入元件要先出
    線框草稿給客戶拍板（`CLAUDE.md §-1.5` A-8）。L3 一律傳 `marginal_rate=None`
    （它明文支援：只算二代健保）。**寫「稅後」而不講這件事就是說謊。**

    ⚠️ **張 → 股 的換算在 L3** `portfolio_deep_service._lot_to_shares()`
    —— **該檔唯一**的乘法點（守衛：`test_there_is_exactly_one_multiplication_site`），
    **不是全站唯一**（實測：`dividend_station_service` 與 `compute.sector_flow`
    也各有一處）。本頁一個乘法都沒有；漏乘就是 1000 倍低估（§4.1）。
    卡面同時印出「該檔唯一 ≠ 全站唯一」那一列，理由見檔頭。
    """
    _res = deep.cash
    _state = classify_ui_state(
        requested=deep.requested,
        error=deep.cash_error or deep.error or None,
        has_value=bool(_res is not None and _res.computed and _res.has_payouts))
    _facts: list[tuple[str, str]] = [
        ("⚠️ 這不是「稅後」",
         "只算到扣掉**二代健保補充保費**為止，**不含綜所稅** —— "
         "綜所稅要你自己的邊際稅率，而那個輸入元件還沒拍板（本頁不自己加）"),
        ("統計區間", "近一年**實際除息**的逐筆金額（每股配息 × 你的股數），"
                     "不是用殖利率回推的估計值"),
        ("張 → 股 的換算住哪裡",
         "L3 `portfolio_deep_service._lot_to_shares()` —— **該檔唯一**的乘法點，"
         "**本頁一個乘法都沒有**"),
        # 誠實揭露：舊文案寫「全站唯一乘法點」，實測為假（全站至少三處）。
        # 只把「全站」兩個字刪掉不夠 —— 讀者仍會以為全站只有這一處。
        ("⚠️ 「該檔唯一」不等於「全站唯一」",
         "全站不只這一處：`dividend_station_service` 的總市值（① 那張卡，"
         "本頁拿它對帳）與 `compute.sector_flow` 的板塊資金流各自也乘每張股數。"
         "**本格的數字只保證走 `portfolio_deep_service` 這一支**，"
         "不對另外兩支的納入口徑背書 —— 對不上時 ⑥ 那兩格會轉「已失準」"),
    ]
    if _res is not None and getattr(_res, "overseas", ()):
        _facts.append(("外幣／海外標的（已排除，僅標記）",
                       "、".join(_res.overseas)
                       + " —— 海外所得走最低稅負制，與國內二代健保**不混算**"))
    _held = getattr(_res, "held_n", 0) or 0
    _lots = getattr(_res, "lots_n", 0) or 0
    if _res is not None and _held and _lots < _held:
        _facts.append((
            "涵蓋範圍",
            f"{_held} 檔持有列裡納入了 {_lots} 檔 —— "
            "沒有張數的列不算（觀察清單那幾列本來就沒有張數，**不是 0 張**）"))
    if _state == UI_LIVE and _res is not None:
        _facts.insert(1, ("扣二代健保後", f"約 {_res.net_after_nhi_twd:,.0f} 元"))
        _facts.insert(2, ("二代健保補充保費", f"約 {_res.nhi_twd:,.0f} 元"
                                              f"（{_res.payouts_n} 筆逐筆判門檻）"))
        _facts.insert(3, ("納入計算的股數",
                          f"{_res.shares_total:,.0f} 股（＝帳本張數 × 每張股數）"))
        return (Card(key="hold.deep.dividend_cash", label="配息現金流",
                     state=UI_LIVE,
                     value=f"近一年稅前約 {_res.gross_twd:,.0f} 元"),
                tuple(_facts), "不含綜所稅")
    if _state == UI_IDLE:
        _note = _idle_note(deep.scope_idle)
    elif _state == UI_FAILED:
        _note = _deep_note(deep, now="**配息現金流算不出來**",
                           source=SRC_DIV_CASH, error=deep.cash_error)
    elif not deep.has_station_rows:
        _note = _deep_note(deep, now="**還沒有可以算配息的持股**",
                           source=SRC_DIV_CASH, error="")
    elif _res is not None and _res.computed:
        _note = Note(
            now="**近一年查不到任何一筆配息**",
            why=("**這是一個有效的結果**（已經逐檔查過，不是還沒查）—— "
                 "可能是你手上這幾檔近一年真的沒有除息，"
                 "也可能是上游沒有這幾檔的配息紀錄。"
                 "本站**不用殖利率回推一個數字頂替** —— 那會變成一筆你其實"
                 "沒有收到的錢"),
            where=("若你確定收過息：先確認代號是否正確（本頁顯示的是正規化後的"
                   f"代號），再{press(ACTION_RUN_WARROOM_LABEL)}試一次"))
    else:
        _note = Note(
            now="**有持股，但配息現金流算不出來**",
            why=("**這是一個有效的結果**（已經算過，不是還沒算）—— "
                 + _deep_reason(_res)),
            where=("到既有的 📁 組合管理分頁把持股的**張數**補齊，"
                   f"回本頁{press(ACTION_RUN_WARROOM_LABEL)}"))
    return Card(key="hold.deep.dividend_cash", label="配息現金流",
                state=_state, note=_note), tuple(_facts), ""


DEEP_CAPTION: str = (
    "線框 ⑥ 原文：現況埋在「5️⃣ 組合深度分析」expander 第五層。"
    "**expander 收合只是視覺收合、body 每次 rerun 照跑** —— 埋起來沒省效能，"
    "只是讓人找不到。改**並列 ＋ 各自 gate**（3 欄 × 2 排，不是一排六欄）。"
    "⚠️ 壓力測試 · VaR · 配息現金流這三格**每一格都會逐檔向上游取數**"
    "（Beta / 近一年日收 / 近一年配息）—— 它們共用送出鈕那一個 gate，"
    "不會在你按之前先跑；快取集中在 L1，本頁不自建第二層。")


def build_core_satellite_card(station: StationReadout) -> _Built:
    """線框 ⑥ 的「核心／衛星」—— **已接線**（與 ⑤ 共用同一支 L3）。

    ⚠️ **與 ⑤ 是同一份數字、不同呈現**：⑤ 講**偏離**（離目標多遠），
    這裡講**組成**（實際各佔多少、各幾檔）。**刻意不重算** ——
    同一頁上兩個由不同算式得出的核心比例，使用者只會讀成「有一邊錯了」。
    """
    _state = classify_ui_state(
        requested=station.requested,
        error=station.error or None,
        has_value=station.split is not None)
    _facts = _split_facts(station)
    _facts.insert(0, ("與 ⑤ 的關係",
                      "**同一支 L3 `compute_allocation_split()`、同一份數字** —— "
                      "⑤ 講偏離，這裡講組成。本頁不重算第二遍"))
    _sp = station.split
    if _state == UI_LIVE and _sp:
        _facts.insert(1, ("納入計算的市值（元·張價）",
                          f"{float(_sp.get('total_value', 0)):,.0f}"))
        return (Card(key="hold.deep.core_satellite", label="核心／衛星",
                     state=UI_LIVE,
                     # §4.1：單位要寫出來 —— 「核心 100.0」看不出是百分比還是檔數。
                     # ⚠️ 這兩個數字**來自 L3**，不是本檔寫死的持股百分比
                     # （`tests/test_no_hardcoded_position_pct.py` 掃的是字面常數）。
                     value=(f"核心 {float(_sp.get('core_pct', 0)):.1f}%"
                            f" ／ 衛星 {float(_sp.get('sat_pct', 0)):.1f}%")),
                tuple(_facts), "")
    _split_card = build_allocation_split_card(station)[0]
    # 狀態與文案**與 ⑤ 完全一致**（同一份輸入、同一個判定）——
    # 兩張卡對同一件事給兩種說法，比少一張卡糟糕得多。
    return Card(key="hold.deep.core_satellite", label="核心／衛星",
                state=_state, note=_split_card.note), tuple(_facts), ""


def build_deep_cards(station: StationReadout,
                     deep: DeepReadout) -> tuple[_Built, ...]:
    """線框葉1 ⑥「組合深度分析」六項 —— **本批之後接線 4 項、未接線 2 項**。

    ⚠️ **順序照線框**（再平衡 / 核心衛星 / 壓力測試 / VaR / 配息現金流 / 葡萄串），
    接線的那幾項**留在它們原本的位置**，不因為先做好就被搬到前面。

    ⚠️ **兩張未接線卡的 `where` 不共用** —— 一個是帳本缺欄位（要先拍板一個
    輸入元件），一個是 L5 的 widget key 撞名。見 `DEEP_SPECS`。

    Args:
        station: 戰情表那一輪（核心／衛星用它）。
        deep: ⑥ 的三支 L3（**同一輪**，由 `load_deep(station)` 帶下來）。
            拆成兩個參數是刻意的：核心／衛星與 ⑤ **共用同一份數字**（不重算），
            而壓測／VaR／配息是**另外三次取數** —— 混成一個容器會讓
            「這一格是不是重算了第二遍」變得看不出來。
    """
    _unwired = {_s.key: build_unwired_card(station.requested, _s)
                for _s in DEEP_SPECS}
    return (_unwired["hold.deep.rebalance"],
            build_core_satellite_card(station),
            build_stress_card(deep),
            build_var_card(deep),
            build_dividend_cash_card(deep),
            _unwired["hold.deep.grape"])


# ── ⑦ AI 戰情總結（唯一推播出口）──────────────────────────────────
AI_SUMMARY_SPEC: UnwiredSpec = UnwiredSpec(
    key="hold.ai_summary", label="AI 戰情總結（唯一推播出口）",
    now="**本頁還生不出 AI 戰情總結**",
    why=("**這一格缺的已經不是資料了。** 四支 L3 都在（`build_station_digest` → "
         "`build_summary_prompt` → `build_ai_summary`，`gemini_fn` 由 "
         "`app_ai_service.gemini_call` 注入），而 digest 的輸入（戰情表）"
         "在本批**已經算得出來**。卡住的是**畫面**：線框在這一區畫了一顆單獨的"
         "按鈕［ ⚡ 生成 AI 總結 ］，而**新增一個視覺元件要先出線框草稿"
         "給客戶拍板**（`CLAUDE.md §-1.5` A-8），本批不自己加"),
    where=_unwired_where(
        "要接上需先讓客戶拍板那顆按鈕（位置必須在表單**外**），"
        "再把 `build_ai_summary(digest, gemini_fn)` 接上去"),
    facts=(
        ("接線後的樣子", "一段可直接推播的文字總結（含當日建議與理由）＋ 複製鈕"),
        ("⚠️ 為什麼不乾脆自動生成",
         "那會讓**每一次頁面互動**都打一次付費 AI —— 比少一顆鈕嚴重得多。"
         "AI 總結必須由使用者明確按一次才發，這正是線框把它畫成按鈕的原因"),
        ("⚠️ 也不會畫一顆按了沒反應的鈕",
         "線框 F5／N2 兩次點名要修的**假出口**就是那個 —— "
         "本頁寧可誠實標未接線"),
        ("AI 的角色", "只潤稿。數字全部來自 digest，L3 明文禁止它自行杜撰代號或數字")))


def build_ai_summary_card(requested: bool) -> _Built:
    """線框葉1 ⑦「AI 戰情總結」—— **本批仍未接線（缺的是一顆要先拍板的鈕）**。

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
            _note = Note(now=GOOGLE_NOT_ASKED_NOW, why=GOOGLE_NOT_ASKED_WHY,
                         where=GOOGLE_NOT_ASKED_WHERE)
        else:
            _note = Note(now=IDLE_NOW, why=IDLE_WHY, where=IDLE_WHERE)
    elif _state == UI_FAILED:
        _note = Note(
            now="**綁定狀態讀不出來**",
            why=_error_why(SRC_BINDING, binding.error),
            where=("先確認網路與 Google 授權是否仍有效；"
                   f"細節在{ia_nav.where_to_find(ia_nav.SECTION_WHY_DATA_HEALTH)}"))
    else:   # UI_EMPTY —— **還沒綁。這是有效結果，不是故障。**
        # ⚠️ 與戰情室那幾張空卡**共用同一組常數**：同一件事在同一頁上寫兩份，
        #    改的時候一定會漏改一份，於是兩張卡對同一個狀況給出兩種說法。
        _note = Note(now=NOT_BOUND_NOW, why=NOT_BOUND_WHY, where=NOT_BOUND_WHERE)
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
        _note = Note(now=GOOGLE_NOT_ASKED_NOW, why=GOOGLE_NOT_ASKED_WHY,
                     where=GOOGLE_NOT_ASKED_WHERE)
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
#: （原本第三項「持股列預覽」本批**已接線**，見 `build_holdings_preview_card()`。）
SETUP_UNWIRED_SPECS: tuple[UnwiredSpec, ...] = (
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


def build_holdings_preview_card(holdings: HoldingsReadout) -> _Built:
    """葉2 第三張卡：**持股列預覽** —— 已接線、**能看不能改**。

    ⚠️ **這張卡不顯示 Sheet 識別碼**，也不顯示任何憑證 —— 與綁定那兩張卡同一條線。
    ⚠️ **觀察清單那些列的張數／均價是 `None`，畫面顯示「—」而不是 0**：
    `stock_watchlist` 分頁的 schema 只有三欄，本來就沒有張數與均價。
    寫 0 會讓人以為「持有 0 張、成本 0 元」，那是一個結論，不是缺值（§1）。
    """
    _state = classify_ui_state(
        requested=holdings.requested,
        error=holdings.error or None,
        has_value=holdings.has_holdings)
    _held_n = len(holdings.held_tickers)
    _facts: list[tuple[str, str]] = [
        ("本頁對這份清單的權限", "**唯讀** —— 不新增、不修改、不刪除任何一列"),
        ("畫面不顯示的東西", "Sheet 識別碼與任何憑證（結構上就沒有帶進本層）"),
        ("觀察清單為什麼沒有張數／均價",
         "那份分頁的 schema 只有「清單名／代號／更新時間」三欄，"
         "**本來就沒有**張數與均價 —— 顯示「—」而不是 0"),
    ]
    if holdings.portfolio_name:
        _facts.append(("讀到的投資組合", holdings.portfolio_name))
    if holdings.watchlist_name:
        _facts.append(("讀到的觀察清單", holdings.watchlist_name))
    if holdings.more_portfolios or holdings.more_watchlists:
        _facts.append((
            "⚠️ 這本 Sheet 裡還有別的沒讀",
            "本頁只取**第一本**組合／**第一份**觀察清單（沿用既有行為）—— "
            "畫面上這幾檔**不是你的全部**"))
    if holdings.watchlist_error:
        # §1：觀察清單那半失敗**不得靜默** —— 它會影響換股建議的「換入」來源。
        _facts.append((
            "⚠️ 觀察清單這一輪讀不到",
            f"{holdings.watchlist_error} —— 持股本身不受影響，"
            "但④ 換股建議的「換入」會退回選股池全自動排名"))
    if _state == UI_LIVE:
        return (Card(key="hold.setup.preview", label="持股列預覽", state=UI_LIVE,
                     value=(f"{len(holdings.holdings)} 列"
                            f"（持有 {_held_n} · 觀察 "
                            f"{len(holdings.holdings) - _held_n}）")),
                tuple(_facts), "唯讀")
    if _state == UI_IDLE:
        _note = _idle_note(holdings.scope_idle)
    elif _state == UI_FAILED:
        _note = Note(
            now="**持股清單讀不出來**",
            why=_error_why(SRC_HOLDINGS, holdings.error),
            where=("先確認網路與 Google 授權是否仍有效；"
                   "**本站不顯示半份清單** —— 少一半算出來的配置比例與損益"
                   "看起來完全正常、實際上是錯的，所以整份都不給"))
    elif holdings.bound:
        _note = Note(now=EMPTY_SHEET_NOW, why=EMPTY_SHEET_WHY,
                     where=EMPTY_SHEET_WHERE)
    else:
        _note = Note(now=NOT_BOUND_NOW, why=NOT_BOUND_WHY, where=NOT_BOUND_WHERE)
    return Card(key="hold.setup.preview", label="持股列預覽",
                state=_state, note=_note), tuple(_facts), ""


def build_setup_unwired_cards(requested: bool) -> tuple[_Built, ...]:
    """葉2 的兩張未接線卡（Sheet 選擇 / 觀察清單管理）。

    ⚠️ 這兩張的 `why` 走 `READONLY_WHY` —— 它們卡住的原因**不是缺 L3**，
    是本頁不准寫。寫成「補一支 L3 就會有」是假的：就算補了，本頁也不會做那件事。
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


def _render_warroom_leaf(req: HoldRequest, holdings: HoldingsReadout) -> None:
    """葉1 戰情室：線框的七個區塊，**依線框順序**。

    ⚠️ **`load_station()` 在這裡只跑一次**，六個區塊共用同一份 rows ——
    每個區塊各自呼叫一次會讓同一頁上出現六份可能不一致的戰情表
    （而且要打六次網路）。
    """
    _station = load_station(holdings)

    section_header("① 結論（三張卡）",
                   "線框：現行戰情室已是「結論在前、明細在後」，**結構不動**。")
    _render_row(build_conclusion_cards(_station))

    section_header("② 同一個名詞，兩套刻度",
                   "**常駐揭露 · 非摺疊** —— 它是防「同名不同義」誤讀的唯一揭露；"
                   "拿掉之後就會有人拿兩套刻度互比，而畫面不會攔他。")
    _scales = build_scale_disclosure()
    _render_one(build_scale_card(_scales))
    _render_scale_tables(_scales)

    section_header("③ 戰情表（燈牆 ＋ VIX）",
                   "線框：3 欄燈格 · 點左表右側就地展開。"
                   "燈牆與 VIX **各自判態** —— 一邊沒有不把另一邊染色。")
    _render_row((build_lightwall_card(_station),
                 build_vix_card(load_vix(req))))
    _render_light_wall(_station)

    _macro = load_macro(req)
    section_header("④ 換股建議（搭配總經位階）",
                   "線框：本頁職責「該加、**該換**、該減」的那個「該換」。")
    _render_row((build_switch_card(load_switch(_station, _macro, holdings),
                                   _station),
                 build_macro_stage_card(_macro)))

    section_header("⑤ 80/20 配置偏離 ＋ 衛星停利",
                   "線框：它回答「該減」，與 ④ 的「該換」互補 —— "
                   "兩個都缺，本頁的職責就只剩三分之一。")
    _render_row((build_allocation_split_card(_station),
                 build_take_profit_card(_station),
                 build_position_cap_card(load_allocation(req))))

    section_header("⑥ 組合深度分析（提升，不再埋 expander）", DEEP_CAPTION)
    _render_row(build_deep_cards(_station, load_deep(_station)))

    section_header("⑦ AI 戰情總結（唯一推播出口）",
                   "線框：拿掉之後這頁就只能看、不能送出去。")
    _render_one(build_ai_summary_card(req.submitted))


def _render_light_wall(station: StationReadout) -> None:
    """③ 的逐檔燈條 —— **走 L4 `render_light_wall()`，本頁不畫第二種燈格**。

    ⚠️ 這一段**不判態、不取數**：狀態由 `build_lightwall_card()` 那張卡負責，
    這裡多判一次就會有兩個可能互相矛盾的說法（同 `_render_scale_tables()`）。

    ⚠️ **沒有 `_lights` 就整段不畫。** 那代表這份結果不是本輪算出來的
    （或 L3 換了形狀）—— 畫一排空格子假裝有燈，比不畫糟糕得多（§1）。

    ⚠️ **刻意不做「點一列就地展開」**（線框 ③ 的下半句）：既有戰情室是用
    `st.dataframe(on_select="rerun")` ＋ L4 `render_holding_detail()` 做的，
    在本頁那是**新增一個互動元件**，落在 UI 草稿先行（`CLAUDE.md §-1.5` A-8）。
    燈牆本身是一次 `st.markdown` 的純 HTML、零 widget，故先出這一半。
    """
    if not station.has_rows:
        return
    _items = [(str(_r.get("代號", "") or ""), str(_r.get("名稱", "") or ""),
               (_r.get("_lights") or ()))
              for _r in station.rows]
    if not any(_it[2] for _it in _items):
        print("[views/page_hold] 戰情表沒有 `_lights` —— 燈牆整段不畫（不畫空格子）")
        return
    from src.ui.render.station_cards import (
        CSS as _WALL_CSS,
        render_legend,
        render_light_wall,
    )
    st.markdown(_WALL_CSS, unsafe_allow_html=True)
    st.caption(
        "**填色＝這盞燈自己的判定**、**外框／紋理＝這盞燈可不可信**（四態）—— "
        "一盞「亮著綠燈但其實沒有資料」的燈，填色會是灰的而且帶斜紋。"
        "每一列右邊的 N/M 與上面 ① 的可信度是**同一把尺**；"
        "分母比格子數少是正常的（還沒有判燈規則的燈不進分母）。")
    render_legend()
    render_light_wall(_items)


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


def _render_setup_result_block(req: HoldRequest,
                               holdings: HoldingsReadout) -> None:
    """葉2 的**下半**：綁定兩張卡 → 持股列預覽 → 兩張未接線卡。"""
    _binding = load_binding(req)

    section_header("Google 登入與 Sheet 綁定（唯讀）",
                   "「還沒綁」與「綁了但裡面是空的」是**兩件事**，"
                   "所以拆成兩張卡 —— 沒有任何一格需要同時代表兩件事。")
    _render_row((build_binding_card(_binding),
                 build_portfolio_count_card(_binding)))

    section_header("持股列預覽 · Sheet 選擇 · 觀察清單管理",
                   "第一張卡**已接線但唯讀**（能看不能改）；"
                   "後兩張卡**不是缺 L3，是缺授權** —— 它們本質上是寫入。")
    _render_row((build_holdings_preview_card(holdings),)
                + build_setup_unwired_cards(req.submitted))
    _render_holdings_preview(holdings)


def _render_holdings_preview(holdings: HoldingsReadout) -> None:
    """持股列的逐列預覽表 —— **唯讀，而且不顯示 Sheet 識別碼**。

    ⚠️ **張數／均價缺的時候顯示「—」，不顯示 0。** 觀察清單那些列本來就沒有
    這兩欄（那份分頁的 schema 只有三欄）；寫 0 會讀成「持有 0 張、成本 0 元」，
    那是一個結論，不是缺值（§1）。

    ⚠️ 這一段不判態（同 `_render_light_wall()`）—— 狀態在
    `build_holdings_preview_card()` 那張卡上。
    """
    if not holdings.has_holdings:
        return
    st.caption("**唯讀** —— 要新增／修改／刪除請到既有的 📁 組合管理分頁。")
    st.dataframe(
        [{"代號": str(_h.get("ticker", "") or ""),
          "名稱": str(_h.get("name", "") or "—"),
          "種類": KIND_LABELS.get(str(_h.get("asset_kind", "")),
                                  KIND_FALLBACK_LABEL),
          "張數": _fmt_lots(_h.get("lots")),
          "均價": _fmt_num(_num(_h.get("avg_price")), digits=2),
          "來源": "持有（投資組合）" if _h.get("held") else "觀察清單（未持有）"}
         for _h in holdings.holdings],
        hide_index=True, width="stretch")


def _fmt_lots(value: Any) -> str:
    """張數 → 顯示字串。`None` → `'—'`（**不是 0**）；零股不被四捨五入掉。"""
    _v = _num(value)
    return "—" if _v is None else f"{_v:g}"


def render_page_hold() -> None:
    """💼 我的持股（IA v2 第 4 頁）。**已由 `app.py` 掛載**（量測日 2026-09-07）。"""
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
    # 表單跑完才讀 gate（上面那段註解的理由），而且**持股清單只讀一次** ——
    # 葉1 的戰情室與葉2 的預覽表吃的必須是同一份清單，分別讀兩次會多打一次
    # Google，而且兩葉有機會顯示不一樣的內容。
    _req = applied_hold_request(_session)
    _holdings = load_holdings(_req)
    with _leaf1:
        _render_warroom_leaf(_req, _holdings)
    with _leaf2:
        _render_setup_result_block(_req, _holdings)
