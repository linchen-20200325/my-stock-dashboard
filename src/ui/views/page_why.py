"""src/ui/views/page_why.py — IA v2 第 5 頁「📖 憑什麼」的**版面落地**（L5 UI）。

規格出處：`docs/wireframes/stock_ia_v1.html` 的 `PAGES[4]`（id=`why`）。
單一職責（線框 `job` 原文）::

    一句話：解釋數字怎麼來、資料新不新鮮、以及直接問。

**三葉**（線框 `leaves` 原文，本頁是五頁裡唯一的三葉頁）::

    葉1 教學       靜態 · 無 gate
    葉2 資料體檢   使用者版常駐（3 欄燈號卡牆）＋ 工程師版單一 checkbox gate
    葉3 AI 問答    chat_input · 天然 gate

═══ ⚠️ 這一頁最容易寫錯的地方 —— 先讀這段 ═════════════════════════════
本頁的職責就是「**誠實報告哪些源是壞的**」。也就是說：

    **一個源取不到，那張卡必須顯示它取不到 ——
      不是跳過不畫、也不是畫成綠色。**

失效模式有兩種，兩種都會產生**假綠燈**，而且第二種特別隱形：

  1. **把壞的畫成綠的。** 本檔的結構性防線：`build_source_card()` 只有在 L0
     的呼叫紀錄明確等於 `ok` 時才會有 `has_value=True`；**任何**其他狀態
     （含 L0 給了本檔沒見過的字面值）一律帶著 `error` 進 `classify_ui_state()`
     → 紅。守衛：`tests/test_p05_why_view.py::TestNoFakeGreenLight`。
  2. ⭐ **把壞的整個不畫。** 這面牆只看得到掛了 `@monitored` 的 fetcher。
     線框具名的三個來源（FRED / FinMind 額度 / TWSE）原本**一支都沒掛**；
     FE-20 這一批在 L1 補上了 **FRED**（`fetch_fred`）與
     **TWSE 盤後市場成交資訊**（`twse_volume`）兩支，
     **FinMind 額度仍然量不到**（它卡在更前面一層，見下方「取數接線表」①）。
     → ⚠️ **接上兩支之後，本檔的處置一個字都沒有拆掉**：
     「把量不到的來源**具名**畫成未接線灰卡」這個機制（`UNMEASURED_SOURCES`
     ＋ `build_unmeasured_cards()`）**原封保留** —— 現在裡面剩 FinMind 額度一張，
     未來任何一個量不到的源都往這裡加；牆下方那段**常駐**的涵蓋率揭露
     （`COVERAGE_DISCLOSURE`）同樣保留，仍然明說
     「這面牆沒有紅燈**不等於**全站都好」。
     ⚠️ **接上 2 支 ≠ 全站被量到**：`src/` 底下掛了 `@monitored` 的**支數**
     由本檔模組常數 `MONITORED_FETCHER_COUNT` 單一持有（畫面文案共用它，
     不再各寫一份寫死值），而全站來源清單（L1 `data_registry`）有數十個。
     ⚠️ 那個數字**會漂**，所以不靠自律維護：
     `tests/test_p05_why_view.py::TestMonitoredCountIsNotStale` 每次 CI
     用 **AST 重數一次** `src/`，數字對不上就當場紅燈。
     守衛：`tests/test_p05_why_view.py::TestUnmeasuredSourcesAreVisible`
     ＋ `TestNamedSourcesAreReallyWired` —— 後者**直接掃 L1 原始碼**：
     本頁宣稱已接線的那兩支若在 L1 被拔掉裝飾器，**當場 CI 紅燈**，
     不會靜靜地變回「牆上少一盞、畫面看起來一切正常」。

═══ 這個檔**不是**什麼 ═══════════════════════════════════════════════
- **不是**第二份門檻表：紅綠燈怎麼判、每一盞的門檻與出處，全部逐欄讀 L0
  `shared/macro_buckets.py` 與 `shared/station_specs.py`，**本檔一個門檻數字都沒有**。
- **不是**新的狀態模型：七態一律走 L0 `shared/ui_state.py::classify_ui_state()`。
- **不是**新的卡片型別：`Card` / `Note` / `MAX_COLS` 一律 import
  `src/ui/tabs/tab_today.py` 與 `src/ui/views/_ui_kit.py`（**不寫第五份渲染器**）。
- **不是**診斷面板的搬家：`src/ui/pages/{data_coverage,api_diagnostic,health_inspector,
  data_registry_panel,reconcile_panel,calibration_ui}.py` 一支都**沒有 import**
  （它們自己直接讀 `st.session_state` 或直呼 L1，把它們拉進來等於把違憲一起繼承）。

~~**本檔沒有 production caller**（`app.py` 掛載另案；本批一個字都沒有碰 `app.py`、
`page_today.py`、`page_find.py`、`page_inspect.py`、`page_hold.py`、`_ui_kit.py`、
`src/ui/tabs/**`、`src/services/**`、`shared/**`、任何既有測試）。~~
舊分頁（🔎 資料診斷 / 📚 教學 / 🧬 AI 問答）不動、不下架。

⚠️ **2026-09-08 FE-36 事實更正 —— 刪除線是有意識保留，不是漏刪。**
那句在本檔剛落地那一批為真；**之後接線的批次沒有回頭改它** ——
也就是說 「掛載另案」那個「另案」早就落地了，**這是 `b5bdb36`（側欄 radio 改動）之前就已經存在的漂移**，
不是這次弄壞的（一併收掉，但據實區分責任）。
**現行**：`app.py::_ia_view_why()` 在側欄「🆕 新版戰情室（試用中）」radio
選到本頁時 late import 並呼叫 `render_page_why()`；**沒被選到時本檔連 import 都不發生**
（`tests/test_ia_v2_sidebar_nav.py::TestNothingRunsUntilYouPick`）。
⚠️ **有 caller 之後，這一頁的每一個 bug 都是使用者看得到的** ——
不得再拿「反正沒有人在用」當放寬任何守衛的理由。
掛載形態由 `tests/test_p0x_view_mount_claims.py` 釘住：再改一次就轉紅。

═══ 取數接線表 ═══════════════════════════════════════════════════════
**已接線**::

    來源健康（葉2 使用者版 ＋ 工程師版的 Fetcher 監控）
        L0 `shared.fetch_monitor.get_monitor_registry()`
        —— 純 in-process dict，**零 I/O、零網路**。它記的是
           「哪一支 fetcher 被真的呼叫過、結果是什麼」。
        ⚠️ **這面牆量到的單位是「fetcher」，不是「來源」。**
           FE-20 在 L1 補掛的 `fetch_fred` / `twse_volume` 各自只代表
           **那一支**最後一次呼叫的結果，**不代表** FRED / TWSE 這兩個來源
           整體都好 —— 同一個來源可以有很多支 fetcher（本頁 `NAMED_SOURCES`
           的 `covers` 欄逐支寫明它到底量到了哪一段）。
        ⚠️ 「呼叫」在各支之間**不是同一件事**（`CACHE_SEMANTICS` 誠實揭露）。
    燈號規格（葉1 教學的門檻表 ＋ 葉2 的「未接線／已失準」卡）
        L0 `shared/macro_buckets.py`（`BUCKET_DANGER_SPECS` / `REFERENCE_TREND_SPECS`）
        L0 `shared/station_specs.py`（`STATION_SPECS`）
        —— `@dataclass(frozen=True)` 常數表，**零 I/O**。
           `unwired_reason` / `degraded_reason` / `no_level_reason` **原文透傳**
           （線框 note 明文要求「直接讀自 SSOT」）。
    AI 問答（葉3）
        L3 `services.app_ai_service.get_gemini_api_key`
        L3 `services.ai_qa_service.run_agent`

⚠️ **為什麼葉1／葉2 走 L0 而不是 L3**：它們要的東西**本來就住在 L0**
（規格常數表、in-process 呼叫紀錄），中間沒有任何取數。硬加一層 L3 pass-through
正是 `CLAUDE.md §8.1` step 6 點名的「用不到的抽象」。L5 → L0 是全站每一頁都在走的
方向，不受 §8.2 任何一條硬規則限制。**「一律走 L3」規範的是「取數」，
不是「讀常數」。**

**未接線（五項，各自的「去哪補」都不同 —— 它們卡住的位置不一樣）**::

    ① FinMind **額度**的健康燈
       （原本這一項還包含 FRED 與 TWSE —— FE-20 已在 L1 補上 `@monitored`，
         改列到上面的「已接線」；額度**沒有**跟著補上，原因在下面。）
       → 額度卡在**比另外兩個更前面一層**：它是 FinMind **帳號層級**的資訊，
         不在任何一支 fetcher 的回傳裡 —— 「幫現有 fetcher 掛監控」補不到它。
       → ⚠️ **本批沒有實測到 FinMind 有沒有可查額度的 API**（誠實揭露）：
         沙箱對外連線被政策擋掉（實測 `api.finmindtrade.com` 的 CONNECT
         回 403），而本 repo 早已移除 FinMind SDK（`requirements.txt` v19.79
         的註記），沒有本地介面可以反查。**在確認之前不猜、不接**；
         尤其**不得**拿「已用次數」冒充「剩餘額度」（那是兩個不同的數）。
    ② 健康評分六因子的「因子名 ＋ 配分」
       → 權重是 L2 `compute/scoring/scoring_helpers.calc_health_score` 內的
         **inline 數字**，L0 `shared/position_throttle.py` 的註解另抄了一份
         （兩份會漂移）。**沒有任何一份是可讀的資料結構。**
    ③ 既有 1,582 行靜態教學內容的搬遷
       → 線框 DECISIONS #9 裁決「原樣搬過來」，但那是跨檔搬遷，
         屬 `CLAUDE.md §8.4` step 4 的範圍問題，**本批不夾帶**。
    ④ 工程師版六個面板裡的五個（資料源清單 / 雙演算法對帳 / API 根因 /
       原始資料表 / 門檻校準）
       → 現行實作都在 L5，且各自直接讀 `st.session_state` 或直呼 L1 / `scripts/`。
    ⑤ AI 問答的「就地設定金鑰入口」
       → 那是**收憑證**，需要客戶先拍板「這一頁可以收金鑰」，本批不做。

**零 L1 import、零 `requests` / `yfinance` / FinMind / `pd.read_csv` /
SQL / parquet、零 `@st.cache_data` / `@st.cache_resource`、零 inline `ttl=`、
零底線開頭的跨檔私有符號、零 `from app import`。**
⚠️ 本頁**受 `tests/test_c3_layering_guard.py` 管**（`_PATH_LAYERS` 已含
`src/ui/views/` → L5），違反 R4／R5 是 CI 紅燈，不是假綠燈。

═══ 四大鐵律的落點 ═══════════════════════════════════════════════════
1. **3 欄上限** —— 一律 `_ui_kit.grid()`（內部硬夾 `MAX_COLS`）。全檔 **0 個**裸
   `st.columns(n)`。線框葉2 的 `cols:3` 註記「**原 `columns(7)` 降階**」講的
   就是這一條：燈牆的格子數是動態的（登錄幾支就幾格），一律**換行排下一列**。
2. **Form 防重繪** —— ⚠️ **本頁刻意一個 `st.form` 都沒有。**
   線框葉2 工程師版原文：「內含 **1 個 checkbox 全有全無** · **不加 form**」，
   而線框 DECISIONS #7 更明文**撤回**了 v1 的 `form_diag` 提案，理由是
   「v1 說 6 個獨立 checkbox 包成一個 form；實測 `app.py` 是 **1 個** checkbox
   全有全無、六個 panel 檔內 checkbox **各為 0** —— **要解的問題不存在**」。
   → 一個 widget 包 form **省不到任何一次 rerun**，只是多一次點擊。
   守衛：`tests/test_p05_why_view.py::TestEngineerGateHasNoForm`。
   葉3 的 `st.chat_input` 同理是**天然 gate**（送出即是 submit），
   而且 Streamlit 明文禁止把 `chat_input` 放進 `st.form`。
3. **四態分離** —— 見下面兩段。
4. **空狀態三要素** —— 一律 `tab_today.Note(now, why, where)`。

═══ `requested=` 的來源（三個 gate ＋ 一個「不需要 gate」）═══════════════
L0 的鐵律：**`idle` 只能由上游帶下來，禁止由 `if not data:` 推導。**
（頁 1 就是在這裡被紅隊抓到恆真式 `(alloc is not None)`。）

  1. **葉2 使用者版的每一盞來源燈** ← `SourceProbe.called`，
     來自 L0 `fetch_monitor` 的 `last_status`。
     ⚠️ **這不是從資料反推**：`last_status` 是**呼叫紀錄**（`@monitored`
     在 import 時寫 `'未執行'`、在真的被呼叫時改寫），不是那支 fetcher
     **抓回來的東西**。抓回來的東西是 `last_rows`，本檔**沒有**拿它當 gate。
     結構上分得開：`called` 只看「是不是還停在未執行」，
     `ok` 只看「是不是 `ok`」，兩個欄位分別存放，`classify_ui_state()`
     讀到的是兩個不同的名字。
     守衛：`tests/test_p05_why_view.py::TestRequestedIsNotDerivedFromData`
     ＋ `TestCallRecordIsTheGateNotTheRows`。
  2. **葉2 工程師版的整段** ← `EngineerRequest.opened`，
     即那**一顆** `st.checkbox` 的回傳值。沒勾 → 六個面板**一個都不建構**，
     只畫一張 idle 卡（線框 grey 原文一字不改）。
  3. **葉3 AI 問答** ← `QaRequest.asked`，即 `st.chat_input` 這一輪有沒有
     回傳字串。**使用者送出問題本身就是 gate**（線框：「天然 gate」），
     不需要另做一顆 submit。

  ⚠️ **第四個是「不需要 gate」**：葉1 教學與所有 L0-only 的卡走
  `build_l0_card()`，它傳的是**字面 `True`** —— 而且**全檔的字面 `requested=`
  只有那一處**（守衛：`TestLeafOneHasNoGate`）。
  理由與頁 4 ② 相同：這些卡的輸入是 `@dataclass(frozen=True)` 常數表，
  **沒有任何取數**，也就沒有「叫過 / 沒叫過」可言。寫字面常數是在**陳述**
  「這個揭露永遠開著」；寫 `bool(rows)` 之類的才是**假裝在判斷**
  （恆真式的問題不在於它恆真，而在於它假裝自己在判斷）。

⚠️ **`requested=False` 時本檔一行 L3 都不呼叫。**
（`tests/test_p05_why_view.py::TestNothingIsCalledBeforeYouAsk` 用**不繼承
`Exception`** 的毒藥實測，不是讀 docstring。）

═══ 三種狀態**絕不可混**（本頁的 §1 主戰場）═══════════════════════════
線框葉2 工程師版的 note 記了一次真實事故（F7）：v1 憑印象寫「6 個 checkbox
包成 form」，實測是 1 個。本頁要防的是同一族的混淆::

    還沒打開進階診斷                → `UI_IDLE`    ⬜ **還沒有人叫過。**
    打開了，但某個源這輪沒回        → **有效結果**：那一盞自己是 idle／empty，
                                      **整段診斷仍然是 live** —— 一格沒回
                                      不把另外兩格、也不把整段染色。
    診斷本身掛了（L0 登錄表讀不出來）→ `UI_FAILED`  🔴 **唯一准用紅色的狀態。**

⛔ **把「還沒打開」畫成紅色**＝ v3 §02 前半句要杜絕的「假性錯誤滿版」，
而滿版假紅字會讓**真的**壞掉那一次沒有人看得見。
⛔ **把「某一源沒回」升級成「整段診斷壞了」**＝ 用一格的狀態去代表一整段，
線框反覆寫的「**逐格獨立判態**」就是在防這個。
本檔的結構性解法：**狀態掛在卡上，不掛在區塊上**（`_ui_kit.render_card()`
的粒度就是一張卡），而整段的狀態由 `build_engineer_card()` **只看
「L0 登錄表讀不讀得出來」**，不看任何一盞燈的死活。

═══ 這個檔擋得住什麼、擋不住什麼（誠實邊界）═══════════════════════════
`load_sources()` / `load_qa()` 的 `try/except` 擋得住的是**呼叫期**例外
（模組進得來、但呼叫時炸了）→ 轉成看得見的紅卡 ＋ `repr(e)`。

⛔ **擋不住 module-level 的 import 失敗。** 本檔 module level 有
`shared.*` 五支與 `src.ui.tabs.tab_today` / `src.ui.views._ui_kit`。
這幾條路徑上任何一個模組在 import 階段壞掉，`import page_why` 自己會先
`ImportError`，`render_page_why()` 根本不會被呼叫到 —— 畫面全空白。

✅ **兩支 L3 都是函式體內的 late import 且各自包在 `try/except` 裡**
（`ai_qa_service` 在 module level 就拉進一堆 L0 與 `requests`；
`app_ai_service` module level 直接 `import requests`。
放在 module level 會讓「打開這一頁」的故障半徑等於整條 AI 資料層）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

import streamlit as st

from shared import ia_nav
# L0 SSOT：@monitored fetcher 的**呼叫紀錄**（純 in-process dict，零 I/O）。
from shared.fetch_monitor import get_monitor_registry
# L0 SSOT：總經燈規格（含 `wired` / `discriminative` 與各自的原因欄）。
from shared.macro_buckets import (
    BUCKET_DANGER_SPECS,
    REFERENCE_TREND_SPECS,
)
# L0 SSOT：持股／個股燈規格 ＋ 缺值原因語彙。
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
    STATION_SPECS,
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
    grid,
    render_card_isolated,
    section_header,
)

# ══════════════════════════════════════════════════════════════════
# session key（本頁自有前綴 `p05`，不與既有 `_diag_adv_on`、
# `ai_qa_history` 相撞 —— 舊分頁仍掛著，撞了會是 DuplicateWidgetID）
# ══════════════════════════════════════════════════════════════════
# ⚠️ **2026-09-08 FE-36 語彙更正（本區塊各行原文一字未改）**：以下若干行寫
#    「與既有 🔎 資料診斷 / 🧬 AI 問答 等舊分頁**同時掛上**時不撞 `DuplicateWidgetID`」。`b5bdb36` 把五頁
#    改成側欄 radio ＋ `st.stop()` 之後，**新頁與舊頁籤不再進到同一個 script
#    run**，「同時掛上 → 同輪撞 ID」這個機制對舊分頁**已不成立**。
#    ✅ **前綴照留，理由換成兩條仍然成立的**：(a) `st.session_state` 跨 rerun、
#    跨頁存活，切一下側欄 radio 就是同 session 的一次 rerun ⇒ 同名 key 照樣
#    互相污染；(b) `st.stop()` 之前跑完的**整個側欄** widget（導覽 radio 自己、
#    連線測試鈕、強制刷新鈕、Sheet ID 輸入框…）**與本頁同輪**，那才是現在真正
#    會撞 ID 的對手。掛載形態由 `tests/test_p0x_view_mount_claims.py` 釘住。
#: 工程師版那**一顆** checkbox 的 key。
#:
#: ⚠️ **它就是葉2 工程師版的 gate，而且沒有「已套用值」這一層。**
#: 頁 1~4 的 gate 要分「widget 當下值 / 已套用值」，是因為那幾頁的 gate 是
#: `st.form` ＋ submit（form 內的 widget 在按下 submit 前不算數）。
#: 本頁**沒有 form**（線框明文「不加 form」），checkbox 的當下值**就是**
#: 使用者的意思 —— 勾了就是要載入，取消勾就是不要。多包一層「已套用值」
#: 會讓「取消勾選之後診斷還留在畫面上」，那才是說謊。
SS_ENGINEER_GATE: str = "p05v_engineer_gate"

#: 葉3 的對話紀錄。`[{"role": "user"|"assistant", "content": str}, ...]`。
#:
#: ⚠️ **這不是 gate。** gate 是 `st.chat_input` 這一輪的回傳值。
#: 用 `len(history)` 當 gate 會讓「上一輪問過、這一輪沒問」被誤判成
#: 「這一輪問了」—— 而那正是 L0 鐵律禁止的「從資料反推」。
SS_QA_HISTORY: str = "p05v_qa_history"

# ══════════════════════════════════════════════════════════════════
# 葉名與控制項的顯示名（線框原文逐字）
# ══════════════════════════════════════════════════════════════════
#: 線框 `PAGES[4].leaves` 逐字。
LEAF_EDU_TITLE: str = "教學"
LEAF_DATA_HEALTH_TITLE: str = "資料體檢"
LEAF_QA_TITLE: str = "AI 問答"

#: 線框葉2 工程師版原文。⚠️ **兩個 label 是兩個東西** —— 線框 N5 補註逐字記載：
#: 上一輪把「摺疊標題」和「要勾的 checkbox」混成一個，還截短了摺疊標題的後半句。
#: production（`app.py`）是**兩步**，本頁照抄兩步，一個字都不截。
ENGINEER_EXPANDER_LABEL: str = "🔧 進階診斷（工程師用；一般使用者不需要打開）"
ENGINEER_CHECKBOX_LABEL: str = "載入進階診斷（較耗時，部分項目會實際打外部 API）"
ENGINEER_CHECKBOX_HELP: str = (
    "資料源清單 · Fetcher 監控 · 雙演算法對帳 · API 根因 · 原始資料表 · 門檻校準")

#: 葉3 的輸入提示（線框 live 原文的例句）。
QA_PLACEHOLDER: str = "例如：2330 現在健康度多少？"

_OPEN, _CLOSE = "「", "」"


def press(label: str) -> str:
    """`'勾「載入進階診斷…」'` 之外的通用組法 —— 指路句的唯一組法。"""
    return f"按{_OPEN}{label}{_CLOSE}"


def tick(label: str) -> str:
    """checkbox 專用的指路句（**動詞不同**：那是「勾」不是「按」）。"""
    return f"勾{_OPEN}{label}{_CLOSE}"


def expand(label: str) -> str:
    """摺疊區專用的指路句（**動詞不同**：那是「展開」不是「按」）。"""
    return f"展開{_OPEN}{label}{_CLOSE}"


#: 本頁資料體檢分區的指路目標。走 `ia_nav`，**不手抄頁名**。
DATA_HEALTH_WHERE: str = ia_nav.where_to_find(ia_nav.SECTION_WHY_DATA_HEALTH)
#: 進階診斷那**兩步**的完整指路（線框 grey 的 `where` 原文就是兩步）。
ENGINEER_WHERE: str = (
    f"在{DATA_HEALTH_WHERE}{expand(ENGINEER_EXPANDER_LABEL)}"
    f"→ {tick(ENGINEER_CHECKBOX_LABEL)}")

# ══════════════════════════════════════════════════════════════════
# L0 `fetch_monitor` 的狀態字面值
# ══════════════════════════════════════════════════════════════════
#: ⚠️ **這是本檔已知的第二真相源，據實揭露（§2.1 SSOT / §-2 規則 6）。**
#: L0 `shared/fetch_monitor.py` **沒有**把這三個狀態匯出成常數 ——
#: 實測（量測日 2026-09-07）`'未執行'` 寫在 `monitored()` 的登錄字典裡、
#: `'ok'` / `'failed'` 寫在 `_record()` 的呼叫端，三個都是 inline 字面值。
#: 本檔只好重抄一次。
#:
#: **交接事項**：應在 `shared/fetch_monitor.py` 匯出 `STATUS_NEVER_RUN` /
#: `STATUS_OK` / `STATUS_FAILED`，本檔改為 import 它們。
#: 在那之前，`tests/test_p05_why_view.py::TestStatusLiteralsMatchL0` 直接
#: 掃 L0 的原始碼，字面值一漂移就 CI 紅燈（**不是靠自律**）。
STATUS_NEVER_RUN: str = "未執行"
STATUS_OK: str = "ok"
STATUS_FAILED: str = "failed"

#: 本檔認得的全部狀態。**認不得的一律走紅**（見 `probe_from_entry`）。
KNOWN_STATUSES: frozenset[str] = frozenset(
    {STATUS_NEVER_RUN, STATUS_OK, STATUS_FAILED})

# ══════════════════════════════════════════════════════════════════
# 兩套「健康度」刻度（線框葉1 live 原文點名的那一項）
# ══════════════════════════════════════════════════════════════════
#: 💼 我的持股 › 戰情表「健檢」那一套背後的燈。
HOLD_SCALE_SPEC_KEYS: tuple[str, ...] = (
    KEY_HEALTH_A, KEY_HEALTH_B, KEY_HEALTH_C, KEY_HEALTH_D, KEY_STOCK_SWAP,
)
#: 上面那一套的**輸入**（不直接顯示，但會決定它的等級）。
HOLD_SCALE_INPUT_SPEC_KEYS: tuple[str, ...] = (
    KEY_STOCK_HEALTH, KEY_STOCK_TREND, KEY_STOCK_KD,
)
#: 🔬 查一檔 › 判決卡「健康度」那一套背後的燈。
INSPECT_SCALE_SPEC_KEYS: tuple[str, ...] = (KEY_STOCK_HEALTH,)

#: 兩套刻度各自「長什麼樣」。**不是門檻**（門檻由 L0 `threshold_text` 供給），
#: 是**值域的形狀** —— 而值域形狀正是「不可互比」的理由。
#:
#: ⚠️ **交接事項（誠實揭露）**：這兩句在 `src/ui/views/page_hold.py` 也各有一份
#: （`HOLD_SCALE_SHAPE` / `INSPECT_SCALE_SHAPE`）。本檔**刻意不 import 那一份**，
#: 因為 `page_hold` 這一批正由另一組在改，跨檔耦合會讓兩邊互相卡住；
#: 但兩份 prose 並存**確實是漂移風險**。正解是在 L0 `shared/station_specs.py`
#: 補一個 `scale_shape` 欄位讓兩頁都讀它 —— 本批不動 `shared/**`，故留紀錄。
HOLD_SCALE_SHAPE: str = "序數燈號 ⚪ / 🟢 / 🟡 / 🔴（四盞燈取最嚴重，**沒有分數**）"
INSPECT_SCALE_SHAPE: str = "連續分數 0–100 ＋ 等第（**沒有燈號**）"

#: 門檻方向的中文說法。
#:
#: ⚠️ **交接事項**：L0 `DangerSpec.direction` / `StationSpec.direction` 只存
#: `'high_bad'` / `'low_bad'` / `'band'` / `'categorical'` 這幾個字面值，
#: **L0 沒有附中文說法**（實測 2026-09-07：全 `shared/` 無對映表）。
#: 這裡的中文屬**顯示文字**（同 `page_hold` 的 `SCOPE_LABELS`），不是門檻；
#: 但它描述的是門檻語意，理想位置仍在 L0 `direction` 旁邊。
DIRECTION_LABELS: dict[str, str] = {
    "high_bad": "越高越危險",
    "low_bad": "越低越危險",
    "band": "兩側都危險（區間）",
    "categorical": "分類，不比大小",
}

# ══════════════════════════════════════════════════════════════════
# 文案常數（一句話只准寫一次 —— 手抄多份，改的時候一定會漏改）
# ══════════════════════════════════════════════════════════════════
#: 例外的**出處**。做法沿用頁 1／2／3／4：不共用 `tab_today.upstream_error_why()`，
#: 因為那支的文案寫死「讀 **L3 canonical 契約**時拋出例外」，
#: 拿它去包別的層等於**對使用者謊報出事的層**。
#: ⚠️ 洗掉狀態 glyph 那一步**仍然走對面的 SSOT** `scrub_state_glyphs()`。
SRC_MONITOR: str = "L0 fetcher 登錄表（`shared.fetch_monitor.get_monitor_registry`）"
SRC_SPECS: str = (
    "L0 燈號規格表（`shared/macro_buckets.py` ＋ `shared/station_specs.py`）")
SRC_QA_KEY: str = "L3 金鑰（`services.app_ai_service.get_gemini_api_key`）"
SRC_QA_AGENT: str = "L3 AI 問答（`services.ai_qa_service.run_agent`）"
SRC_RENDER: str = "本頁的渲染層（`views/_ui_kit.render_card`）"

UNKNOWN_ERROR_TEXT: str = "（上游沒有給訊息）"

#: L0 的原因欄（`unwired_reason` / `degraded_reason`）**原文透傳**時的出處標註。
#: 線框葉2 note 明文：「`unwired_reason` / `degraded_reason` 直接讀自 SSOT」。
L0_REASON_FACT_LABEL: str = "這段話的出處"
L0_REASON_FACT_TEXT: str = (
    "L0 燈號規格表自己寫的（`unwired_reason` / `degraded_reason`）—— "
    "本頁**沒有改寫**，只在放進三要素時移除了會和狀態燈打架的符號")

#: ⚠️ **「一次呼叫」在各支之間不是同一件事 —— 這是誠實揭露，不是免責聲明。**
#:
#: `@monitored` 的慣例是掛在 cache 裝飾器**之內**（最貼函式），這樣快取命中就不會
#: 觸發它，`last_called_at` 才真的等於「最後一次真實外抓」。但**不是每一支的快取
#: 都寫成裝飾器**：實測（量測日 2026-09-07）L1 `fetch_fred` 的 30 分鐘 TTL 是
#: **寫在函式體內**的 module-level dict（因為那個模組規定不依賴 streamlit，
#: 沒有 `@st.cache_data` 可用），所以那一支在 TTL 內的命中**仍會被記成一次呼叫**。
#:
#: ⚠️ 本頁讀的是 L0 登錄表，**結構上分不出**哪一支是哪一種 —— 所以這裡把差別說出來，
#: 而不是統一宣稱「快取命中一律不計」（那句對掛在 cache 之內的那幾支是對的，
#: 對 `fetch_fred` 就是**假的**）。
#: ✅ **但「未檢查 → 綠燈」那一次翻轉不受影響**：函式體內的快取與 L0 登錄表同屬
#: 這一個 process，第一次呼叫必然是 cache miss，**快取點不亮一盞還沒亮過的燈**。
CACHE_SEMANTICS: str = (
    "**這面牆上的時間是什麼**：`@monitored` 多數掛在 cache 裝飾器之內，"
    "所以快取命中不會刷新它 —— 那個時間就是最後一次真實外抓。"
    "但有些 fetcher 的快取是寫在函式體內的（例如 FRED 那一支，"
    "因為它所在的模組刻意不依賴 Streamlit，用不了 Streamlit 的快取裝飾器），"
    "那一類的時間代表「最後一次**呼叫**」，**可能新於**最後一次真實外抓。"
    "⚠️ 本頁讀的是登錄表，分不出哪一支是哪一種，所以這裡把差別說出來，"
    "不統一宣稱「快取命中一律不計」。"
    "✅ 不受影響的是「未檢查」這一態：快取與登錄表同屬一個 process，"
    "第一次呼叫必然沒有快取可用 —— **快取點不亮一盞還沒亮過的燈**。")

#: 「未執行」到底是什麼意思。這一句會出現在每一盞 idle 的來源燈上。
NEVER_RUN_WHY: str = (
    "這一支 fetcher **這個 session 還沒有真的對外抓過** —— "
    "它在被 import 時就先登錄了自己（所以你現在看得到它），"
    "但還沒有任何一次真實請求。⚠️ **快取命中點不亮這一盞**："
    "如果別的頁是拿快取回答你的，這一盞仍然會停在「未檢查」"
    "（綠燈**上顯示的時間**是另一回事，見下方那段「這面牆上的時間是什麼」）")
NEVER_RUN_WHERE: str = (
    "到會用到它的那一頁按更新／載入，讓它真的跑一次；"
    f"跑完回到{DATA_HEALTH_WHERE}就會看到時間")


# ── 線框葉2 `cells` 具名的三個來源：兩個已接線、一個仍量不到 ─────────────
@dataclass(frozen=True)
class NamedSource:
    """線框具名的一個來源，**接線後的現況**。

    ⚠️ **這張表是本頁對外的宣稱，所以它必須可被機器查核。**
    `fetcher` / `module` 兩欄不是裝飾用的 —— `tests/test_p05_why_view.py::
    TestNamedSourcesAreReallyWired` 拿它們**直接掃 L1 原始碼**：
    宣稱 `wired=True` 的那一支若在 L1 被拔掉 `@monitored`，**當場 CI 紅燈**。
    否則這面牆會靜靜地少一盞，而畫面看起來一切正常（本頁第二種假綠燈）。

    Attributes:
        label: 線框上的名字。
        fetcher: L0 登錄名（＝ `@monitored()` 的第一個引數）；未接線者為空字串。
        module: 那支 fetcher 住的 L1 檔（**字串，不是 import** —— L5 不碰 L1）。
        covers: 這一支到底量到了**哪一段**。⚠️ 一支綠燈不代表整個來源都好。
    """

    label: str
    wired: bool
    covers: str
    fetcher: str = ""
    module: str = ""


#: 線框葉2 `cells` 點名的三個來源。**兩個已接線、一個仍量不到。**
NAMED_SOURCES: tuple[NamedSource, ...] = (
    NamedSource(
        label="FRED（美國總經）", wired=True, fetcher="fetch_fred",
        module="src/data/macro/macro_core.py",
        covers="FRED 序列取數這一支（DGS10 / CPI / NAPM … 共用同一支）"),
    NamedSource(
        label="TWSE（台股收盤）", wired=True, fetcher="twse_volume",
        module="src/data/macro/leading_indicators.py",
        covers="TWSE 盤後「每日市場成交資訊」（FMTQIK）這一支"),
    NamedSource(
        label="FinMind（API 額度）", wired=False, fetcher="", module="",
        covers="額度是帳號層級資訊，不在任何一支 fetcher 的回傳裡"),
)

#: 🔒 **`src/` 底下掛了 `@monitored` 的 fetcher 支數 —— 本頁這個數字的單一出處。**
#:
#: ⚠️ **這個常數存在的理由是「四份會各自漂」，不是為了少打幾個字。**
#: 本檔原本把同一個數字**寫死四份**（檔頭 docstring、本節註解、`UNMEASURED_WHY`、
#: `COVERAGE_DISCLOSURE`），而**沒有任何一條測試在守那個總數** —— 任何人在 L1
#: 多掛一支，畫面就靜靜地少報一支，**CI 全綠**。那正是本頁第二種假綠燈
#: （把量不到的整個不畫）從**文案**這道門走回來：牆上不會出現紅燈，
#: 只會出現一句**過時而且看起來很篤定**的數字。
#: 現在全檔只有這一個字面值，畫面文案一律內插它。
#:
#: ⚠️ **它是單組實測值，會漂**（依 `CLAUDE.md §8.2.A.0` 規則 4 標量測日：
#: **2026-09-07**）—— 所以**不靠自律維護**：
#: `tests/test_p05_why_view.py::TestMonitoredCountIsNotStale` 每次 CI 用
#: **AST 重數一次** `src/**/*.py`，對不上就紅，並直接指名要改哪裡。
#:
#: **計數規則（AST，不是 grep）**：數的是「函式定義上實際掛著名為 `monitored`
#: 的裝飾器」的**次數**（同一個登錄名重複掛也各算一次）。用 AST 而不用 grep，
#: 是因為 AST 天生不受下列三件事影響：
#:   · **縮排**（寫在 class 裡的 method）—— 實測（量測日 2026-09-07）`src/`
#:     現況**縮排寫法 0 處**，全部貼在行首；但 `grep -rn "^@monitored"` 只抓行首，
#:     **日後只要有人把它寫進 class，那道 grep 就會低估**（AST 不會）。
#:     這件事本身也有守衛：`TestMonitoredCountIsNotStale` 會比對
#:     「行首 grep 的結果」與「AST 的結果」，一旦分岔就紅，
#:     逼人去改**畫面上印給使用者的那道指令**，而不是去改 AST。
#:   · **換行寫法**（`@monitored(` 之後才換行接參數）—— `src/` 現況幾乎全是
#:     這種多行寫法，AST 照樣數對。
#:   · **註解與字串裡的 `@monitored` 字樣** —— 本檔文案裡就有一大堆，
#:     所以 `grep -rn '@monitored' src/`（不帶 `^`）數出來的是**字樣數**，
#:     **不是支數**，兩者差很多。
#:
#: ⚠️ **範圍是 `src/`，不是整個 repo**：`tests/` 底下另有若干個 `@monitored`，
#: 那些是測試自己造的探針函式（`__p05_probe_raise__` 之類），
#: 不是 production fetcher，也不會出現在這面牆上。
MONITORED_FETCHER_COUNT: int = 9

#: 畫面上印給使用者的「你自己去重現一次」指令。
#: ⚠️ 它必須**真的重現得出** `MONITORED_FETCHER_COUNT` —— 原文印的是
#: `grep -rn '@monitored' src/`（不帶 `^`），那道指令數到的是**字樣數**、
#: 不是支數，讀者照著跑會得到一個對不上的數字，然後合理地認為這面牆在說謊。
#: 這是**修正錯誤**（讓它回到它本來就該做到的事），不是改設計。
#: 守衛：`TestMonitoredCountIsNotStale::test_the_recipe_printed_to_users_still_works`。
MONITORED_COUNT_RECIPE: str = 'grep -rn "^@monitored" src/ --include=*.py'

#: 共同根因。⚠️ 支數一律內插 `MONITORED_FETCHER_COUNT`，**不准在這裡寫死**。
UNMEASURED_WHY: str = (
    "這面牆讀的是 L0 fetcher 登錄表，而登錄表只看得到掛了 `@monitored` 的 "
    f"fetcher —— 實測（量測日 2026-09-07，`{MONITORED_COUNT_RECIPE}`）"
    f"**`src/` 底下共 {MONITORED_FETCHER_COUNT} 支掛了**，這一個不在裡面。"
    "本頁是 L5，既不直接讀 L1 的來源清單、也不自己打 API，"
    "所以這一盞**現在沒有東西可以點亮**")

#: 涵蓋率揭露（**常駐，不隨狀態消失**）—— 本頁最重要的一段話。
#:
#: ⚠️ **FE-20 把 FRED 與 TWSE 接上之後，這段話沒有被縮短，只有被改準。**
#: 「掛了 3 支就以為全站都掛了」正是這段話要防的那種樂觀 —— 接上兩支之後，
#: 它要防的東西**沒有變少**，只是名單換了幾個名字。
COVERAGE_DISCLOSURE: str = (
    "**這面牆涵蓋什麼**：只涵蓋掛了 `@monitored`（L0 `shared/fetch_monitor.py`）"
    "**而且本 session 已經被載入過**的 fetcher，再加上 L0 燈號規格表**自己標記**的"
    "「未接線／已失準」。兩者都是零 I/O 的常數與紀錄，本頁不會為了畫這面牆去打任何 API。\n\n"
    "**線框具名的那三個來源**：**FRED** 與 **TWSE** 已在 L1 各掛上一支監控，"
    "所以它們**有資格**出現在上面那面牆上（真的出現還要那個模組被載入過，"
    "逐項見上方那段狀態一覽）；**FinMind 的 API 額度仍然量不到**，"
    "所以它仍是下面那張具名的灰卡。\n\n"
    "⚠️ **「那一支綠」不等於「那個來源好」**：同一個來源可以有很多支 fetcher，"
    "這面牆量到的單位是 **fetcher**，不是**來源**。\n\n"
    "**不涵蓋什麼**：全站來源清單的 SSOT 住在 L1 `src/data/core/data_registry.py`，"
    "本頁是 L5、依 `CLAUDE.md §8.2` 不得直接讀它，而 `src/services/` 也沒有把它轉出來 → "
    "**大多數來源仍然不在這面牆上**。實測（量測日 2026-09-07）"
    f"`src/` 底下只有 **{MONITORED_FETCHER_COUNT} 支** "
    "fetcher 掛了監控，而全站來源清單有數十個。\n\n"
    "⚠️ **所以：這面牆上沒有紅燈，不等於全站都好。** 它只說得出它看得到的那幾盞 —— "
    "接上兩支之後這句話**一個字都沒有變弱**。"
    "下面那張具名的灰卡就是為了不讓量不到的來源「因為沒被畫出來而看起來沒事」。")

#: 工程師版的常駐說明（摺疊起來也看得到的那一句在外面）。
ENGINEER_CAPTION: str = (
    "六個面板各自會組大量表格，**預設不跑**。"
    "勾一次全部載入、取消勾就全部收起來 —— 線框 F7／DECISIONS #7 實測後"
    "**撤回**了「包成 form」的提案：這裡只有一顆 checkbox，包 form 省不到任何一次 rerun。")

# ── 未接線卡的共同語彙 ──────────────────────────────────────────────
#: 未接線一律沒有使用者可執行的出口（沿用 `tab_today.NO_EXIT_MARKER` SSOT）。
NO_EXIT_PREFIX: str = f"{NO_EXIT_MARKER} —— 這是待接線項，不是你操作的問題；"


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


def _clean_reason(reason: Any) -> str:
    """L0 的原因欄 → 可以放進 `Note.why` 的字串。**內容不改寫，只洗 glyph。**

    ⚠️ 為什麼一定要洗：實測（2026-09-07）L0 `station_specs` 的
    `stock_kd.no_level_reason` 裡就有 **2 個**狀態 glyph（`🟢` / `🔴`）。
    不洗 → `Note.__post_init__` 直接 `ValueError` → **整段規格揭露消失**，
    而畫面上一句解釋都沒有。§1 要的是「說得出來」，不是「換一種炸法」。

    ⚠️ **洗過就要說**（§1：修改過的訊息不能假裝自己是原文）。
    完整原文仍可在下方的門檻對照表看到（那是 `st.dataframe`，不受 `Note` 拘束）。
    """
    _clean, _n = scrub_state_glyphs(reason)
    if not _clean:
        return UNKNOWN_ERROR_TEXT
    if _n:
        _clean += ("（原文裡的燈號符號已移除，以免和這張卡自己的狀態燈"
                   "變成兩個互相矛盾的說法；完整原文見下方對照表）")
    return _clean


# ══════════════════════════════════════════════════════════════════
# 純資料層（零 streamlit；render 端把東西讀出來再傳進來）
# ══════════════════════════════════════════════════════════════════
#: 一張卡回傳的形狀：`(Card, facts, signal_text)`。
#:
#: ⚠️ **本頁全部的 `signal_text` 都是空字串，而且是刻意的。**
#: 訊號頻道是給「業務燈號」用的（綠 / 循環惡化 …）；本頁畫的**就是狀態本身**，
#: 沒有第二個頻道。硬加一個訊號標籤會讓同一張卡出現兩套說法，
#: 正是 `_ui_kit` 鐵律 3 要防的「兩個紅撞在一起」。
_Built = tuple[Card, tuple[tuple[str, str], ...], str]


@dataclass(frozen=True)
class L0CardSpec:
    """一張 **L0-only** 卡的全部內容（葉1 教學 ＋ 葉2 的規格類卡片）。

    Attributes:
        key / label: 卡的識別字與畫面名。
        value: **只有 live 才會被用到**（`Card.__post_init__` 擋非 live 帶結論）。
        has_value: 這張卡算不算「有結論」。
        wired / discriminative: 直接來自 L0 規格表的旗標（或本檔宣告的未接線）。
        reason: 缺值原因（`MISS_*` 語彙）。
        error: 讀 L0 本身出錯（理論上不會，但 §1 不假設）。
        now / why / where: 非 live 時的三要素。三個都不得為空（`Note` 會 raise）。
        facts: 中繼資料列。**任何狀態都可帶** —— 這些不是「這一輪量到的數字」，
            而是「這一格本來長什麼樣」，未接線時照樣該讓人看見。
    """

    key: str
    label: str
    now: str
    why: str
    where: str
    value: str = ""
    has_value: bool = False
    wired: bool = True
    discriminative: bool = True
    reason: str = MISS_NO_INPUT
    error: str = ""
    facts: tuple[tuple[str, str], ...] = field(default_factory=tuple)


def build_l0_card(spec: L0CardSpec) -> _Built:
    """**本檔唯一的字面 `requested=True`** —— L0-only 卡的共同判態入口。

    為什麼是字面常數而不是某個運算式：這些卡的輸入是 L0 的
    `@dataclass(frozen=True)` 常數表，**沒有任何取數**，也就不存在
    「叫過 / 沒叫過」這個問題。寫字面 `True` 是在**陳述**「這個揭露永遠開著」；
    寫 `bool(rows)` 之類的則是在**假裝判斷** —— 那才是頁 1 被紅隊抓到的恆真式病
    （恆真式的問題不在於它恆真，而在於它假裝自己在判斷）。

    ⚠️ **把全部 L0-only 的卡收斂到這一支，是為了讓「無 gate」變成可稽核的事實**：
    全檔只要出現第二個字面 `requested=`，`TestLeafOneHasNoGate` 就轉紅。
    """
    _state = classify_ui_state(
        requested=True,
        error=spec.error or None,
        has_value=spec.has_value,
        reason=spec.reason,
        wired=spec.wired,
        discriminative=spec.discriminative)
    if _state == UI_LIVE:
        return (Card(key=spec.key, label=spec.label, state=UI_LIVE,
                     value=spec.value),
                tuple(spec.facts), "")
    if _state == UI_FAILED and spec.error:
        _note = Note(now=f"**{spec.label}讀不出來**",
                     why=_error_why(SRC_SPECS, spec.error),
                     where=(f"{NO_EXIT_MARKER} —— 這是規格表本身的問題，"
                            "請把上面那行訊息回報給維護者"))
    else:
        _note = Note(now=spec.now, why=spec.why, where=spec.where)
    return (Card(key=spec.key, label=spec.label, state=_state, note=_note),
            tuple(spec.facts), "")


@dataclass(frozen=True)
class SourceProbe:
    """一支 `@monitored` fetcher 在 L0 登錄表裡的**呼叫紀錄**（不是它抓到的資料）。

    Attributes:
        name: fetcher 名（L0 登錄時給的顯示名）。
        category / frequency: L0 的分組欄，原樣透傳。
        called: **gate。** 「這一支這個 session 有沒有真的被呼叫過」。
            ⚠️ 它只看 `last_status` **是不是還停在「未執行」** ——
            那是 `@monitored` 在**呼叫的當下**寫的紀錄，
            **不是**那支 fetcher 抓回來的東西（抓回來的東西是 `rows`）。
        ok: 最後一次真實呼叫成功了沒有。**只有 `last_status == 'ok'` 才是 True。**
        error: 要餵給 `classify_ui_state(error=)` 的訊息。非空 = 紅。
        last_called_at / rows / ms: L0 原樣透傳，只做顯示。
        unknown_status: L0 給了本檔不認得的狀態字面值時，原文放這裡。
            ⚠️ **不認得一律當紅**，絕不當綠（見 `probe_from_entry`）。
    """

    name: str
    called: bool
    ok: bool = False
    category: str = ""
    frequency: str = ""
    error: str = ""
    last_called_at: str = ""
    rows: str = ""
    ms: str = ""
    unknown_status: str = ""


@dataclass(frozen=True)
class SourceScan:
    """讀一次 L0 登錄表的結果。

    Attributes:
        scanned: **有沒有真的讀過**（不是「有沒有列」）。
            預設 `False`，只有 `load_sources()` 成功走完才會是 True ——
            這讓「沒有人叫過」與「叫了、登錄表是空的」在型別上就分得開。
        probes: 逐支 fetcher 的呼叫紀錄，依名字排序。
        error: 讀取期例外 `repr(e)`。
    """

    scanned: bool = False
    probes: tuple[SourceProbe, ...] = ()
    error: str = ""

    @property
    def readable(self) -> bool:
        """登錄表本身讀不讀得出來（**與裡面有幾列無關**）。"""
        return self.scanned and not self.error

    @property
    def count(self) -> int:
        return len(self.probes)


def _text(value: Any) -> str:
    """L0 欄位 → 顯示字串。`None` → 空字串（**不寫 0、不寫「N/A」**）。"""
    if value is None:
        return ""
    return str(value)


def probe_from_entry(name: str, entry: Mapping[str, Any]) -> SourceProbe:
    """L0 登錄表的一列 → `SourceProbe`。**任何非 `ok` 的狀態都不會變成綠燈。**

    三個已知狀態（實測 L0 `shared/fetch_monitor.py`）::

        '未執行'  → 還沒有人叫過它            → called=False  → idle ⬜
        'ok'      → 最後一次真實呼叫成功       → ok=True       → live 🟢
        'failed'  → 最後一次真實呼叫失敗       → error 非空    → failed 🔴

    ⚠️ **第四種：L0 給了本檔不認得的字面值。**
    這時本檔**不猜、也不當成綠燈** —— 原文放進 `unknown_status`，
    並組一句 `error` 讓它走紅態。理由：本檔的狀態字面值是**重抄**的第二真相源
    （見 `STATUS_NEVER_RUN` 的註解），L0 哪天改字或多一態，
    「靜默當綠」會讓一整批來源在畫面上憑空變好。
    §1：寧可炸出一張紅卡，也不要一個看起來正常的假綠燈。
    """
    _status = _text(entry.get("last_status"))
    _last_error = _text(entry.get("last_error"))
    _common = {
        "name": name,
        "category": _text(entry.get("category")),
        "frequency": _text(entry.get("frequency")),
        "last_called_at": _text(entry.get("last_called_at")),
        "rows": _text(entry.get("last_rows")),
        "ms": _text(entry.get("last_ms")),
    }
    if _status == STATUS_NEVER_RUN:
        return SourceProbe(called=False, ok=False, **_common)
    if _status == STATUS_OK:
        return SourceProbe(called=True, ok=True, **_common)
    if _status == STATUS_FAILED:
        return SourceProbe(called=True, ok=False,
                           error=_last_error or UNKNOWN_ERROR_TEXT, **_common)
    # 認不得 → 紅。**不 fallback 成綠、也不 fallback 成灰。**
    return SourceProbe(
        called=True, ok=False, unknown_status=_status,
        error=(f"L0 登錄表回了本頁不認得的狀態 {_status!r}"
               f"（本頁認得的是 {sorted(KNOWN_STATUSES)}）—— "
               "在確認它代表什麼之前，本頁一律不把它畫成正常"),
        **_common)


def load_sources() -> SourceScan:
    """讀一次 L0 fetcher 登錄表。**零 I/O、零網路、零 L3。**

    邊界：
      (a) **讀爆了**（理論上不會，L0 是純 dict）→ `error` → 紅卡。
      (b) **讀到了、但是空的** → `scanned=True` ＋ `probes=()`。
          這是**有效結果**，不是故障 —— 代表「本 session 還沒有任何掛了
          `@monitored` 的模組被 import 進來」。畫面必須說得出這件事，
          不能顯示一片空白讓人以為牆壞了。
      (c) 某一列的形狀怪（不是 Mapping）→ **那一列照畫，畫成紅的**。
          ⚠️ 這裡刻意**不是**「跳過那一列」：跳過就是本頁最隱形的那種假綠燈
          （檔頭第二段）—— 少掉的那一格不會有人發現，而畫面看起來一切正常。
    """
    try:
        _reg = get_monitor_registry()
    except Exception as _e:  # noqa: BLE001 — 轉成紅卡顯示，不吞
        print(f"[views/page_why] L0 fetcher 登錄表讀取失敗 → 轉紅態：{_e!r}")
        return SourceScan(error=repr(_e))
    _probes: list[SourceProbe] = []
    for _name, _entry in sorted((_reg or {}).items(), key=lambda _kv: str(_kv[0])):
        if isinstance(_entry, Mapping):
            _probes.append(probe_from_entry(str(_name), _entry))
            continue
        _shape = type(_entry).__name__
        print(f"[views/page_why] 登錄表的 {_name!r} 不是 Mapping "
              f"（{_shape}）—— 畫成紅卡，不跳過")
        _probes.append(SourceProbe(
            name=str(_name), called=True, ok=False,
            unknown_status=f"<{_shape} 不是 Mapping>",
            error=(f"L0 登錄表的 {_name!r} 這一列不是 Mapping（是 {_shape}）—— "
                   "本頁讀不出它的狀態；在確認之前一律不把它畫成正常")))
    return SourceScan(scanned=True, probes=tuple(_probes))


def build_source_card(probe: SourceProbe) -> _Built:
    """一盞來源燈。**線框葉2 使用者版的那一格。**

    四種畫面（線框的 `greyCells` / `cells` / `errCells` 逐一對上）::

        未執行  → ⬜ 未檢查            （`greyCells` 原文就是「⬜ 未檢查」）
        ok      → 🟢 ＋ 最後真實抓取時間（`cells` 的「🟢 09/05 14:30」）
        failed  → 🔴 ＋ L0 記下的錯誤原文（`errCells` 的「🔴 額度用罄」）
        不認得  → 🔴 ＋ 原狀態字面值    （線框沒有這一格，**因為它不該存在**）

    ⚠️ **`requested=` 讀的是呼叫紀錄，`has_value=` 讀的是成敗**，兩個不同欄位。
    L0 的鐵律禁的是「拿**資料本身**回推有沒有被叫過」；
    `last_status` 不是資料，它是 `@monitored` 在呼叫當下寫下的**紀錄**
    —— 那正是「上游帶下來的 gate 旗標」的定義。
    """
    _state = classify_ui_state(
        requested=probe.called,
        error=probe.error or None,
        has_value=probe.ok,
        reason=MISS_FETCH_FAILED)
    _facts: list[tuple[str, str]] = []
    if probe.category:
        _facts.append(("分類", probe.category))
    if probe.frequency:
        _facts.append(("更新頻率", probe.frequency))
    if probe.rows:
        _facts.append(("最後一次回了幾列", probe.rows))
    if probe.ms:
        _facts.append(("最後一次耗時（ms）", probe.ms))
    _facts.append(("這一盞的出處", SRC_MONITOR))

    if _state == UI_LIVE:
        _when = probe.last_called_at or "（L0 沒有記下時間）"
        return (Card(key=f"why.source.{probe.name}", label=probe.name,
                     state=UI_LIVE, value=_when),
                tuple(_facts), "")
    if _state == UI_IDLE:
        _note = Note(now="**未檢查**", why=NEVER_RUN_WHY, where=NEVER_RUN_WHERE)
    elif probe.unknown_status:
        _note = Note(
            now=f"**這一盞的狀態本頁看不懂**（L0 回 {probe.unknown_status!r}）",
            why=_clean_reason(probe.error),
            where=(f"{NO_EXIT_MARKER} —— 這是 L0 登錄表與本頁之間的契約漂移，"
                   "請把上面那行訊息回報給維護者；"
                   "在確認之前本頁**不會**把它畫成正常"))
    else:
        _note = Note(
            now="**最後一次真實抓取失敗了**",
            why=_error_why(f"{probe.name}（{SRC_MONITOR}）", probe.error),
            where=("這是上游來源的問題，不是你操作的問題 —— "
                   "可以到會用到它的那一頁重按一次更新；"
                   "若持續失敗請把上面那行訊息回報給維護者"))
    return (Card(key=f"why.source.{probe.name}", label=probe.name,
                 state=_state, note=_note),
            tuple(_facts), "")


def build_empty_registry_card() -> _Built:
    """登錄表**讀得到、但是空的** —— 這是有效結果，不是故障（灰，不是紅）。"""
    return build_l0_card(L0CardSpec(
        key="why.source.none", label="登錄表裡目前一支 fetcher 都沒有",
        has_value=False, reason=MISS_NO_INPUT,
        now="**這個 session 還沒有任何 fetcher 登錄**",
        why=("`@monitored` 是在**模組被 import 的時候**自我登錄的。"
             "本頁自己**不 import 任何 L1 模組**（L5 不得直呼 L1），"
             "所以如果你是直接打開這一頁、還沒去過任何會取數的分頁，"
             "登錄表就是空的 —— **這是正常的，不是壞掉**"),
        where=("先去任何一個會抓資料的分頁載入一次，"
               f"再回到{DATA_HEALTH_WHERE}；"
               "屆時這面牆會自己長出那幾支 fetcher，本頁不必改一行"),
        facts=(("這一格的出處", SRC_MONITOR),
               ("為什麼不顯示一片空白",
                "空白會讓人以為這面牆壞了；"
                "「讀到了、裡面沒有東西」與「讀不到」是兩件事，必須分得出來"))))


# ── 具名、但這面牆量不到的來源 ────────────────────────────────────────
#: ⚠️ **這個清單是機制，不是名單。**
#: 線框原本點名三個（FRED / FinMind 額度 / TWSE）；FE-20 把其中兩個在 L1 接上了，
#: 所以現在只剩一張。**清單縮短不等於機制可以拆掉** —— 它存在的理由是
#: 「量不到的來源必須被**具名畫出來**，否則畫面會是滿版綠」，
#: 而那個理由與清單裡有幾筆無關。未來任何一個量不到的源都往這裡加。
#:
#: ⚠️ **每一筆的「去哪補」都必須不同** —— 共用一句「未接線」會讓
#: 「補哪一步就會好」這個資訊消失（前四頁反覆踩過的同一個坑）。
UNMEASURED_SOURCES: tuple[L0CardSpec, ...] = (
    L0CardSpec(
        key="why.source.unmeasured.finmind_quota", label="FinMind（API 額度）",
        wired=False,
        now="**額度這件事本頁看不到**",
        why=(UNMEASURED_WHY +
             "。而且額度**比另外兩個具名來源更卡一層**：它是 FinMind **帳號層級**"
             "的資訊，不在任何一支 fetcher 的回傳裡 —— FE-20 已經幫 FRED 與 TWSE "
             "掛上了 `@monitored`，但同一招對額度**沒有用**："
             "掛上去只會知道「這次抓成功了」，不會知道「還剩多少」"),
        where=(f"{NO_EXIT_PREFIX}"
               "下一步是**先查證 FinMind 到底有沒有可查額度的介面**，再決定要不要"
               "在 L1 新增一支查額度的 fetcher、由 `src/services/` 轉出成 L3。"
               "⚠️ 這一步**本批沒有做到**：沙箱的對外連線被政策擋掉"
               "（實測 `api.finmindtrade.com` 的 CONNECT 回 403），"
               "而本 repo 早已移除 FinMind SDK，沒有本地介面可以反查 —— "
               "所以本頁**不宣稱它做得到、也不宣稱它做不到**。"
               "另外，查帳號額度要帶帳號 token，屬**憑證**範圍（同葉3 的第 ⑤ 項），"
               "需要先拍板「這一頁可以動用帳號憑證」"),
        facts=(("線框對這一格的期待", "🟢 額度剩 62%"),
               ("卡住的那一步", "連 fetcher 都還沒有，不只是沒掛監控"),
               ("本批查到哪裡",
                "沙箱對外連線被擋（CONNECT 403）→ **無法實測** FinMind "
                "有沒有額度查詢 API；本 repo 也沒有 FinMind SDK 可以反查"),
               ("⚠️ 為什麼不畫一個估計值",
                "額度用罄是「其他頁整片變紅」最常見的單一原因；"
                "在這裡放一個猜出來的百分比，等於把最需要準確的那一格變成假的"),
               ("⚠️ 為什麼不拿「已用次數」充數",
                "就算查得到用量，「已用 N 次」與「還剩多少」是兩個不同的數 —— "
                "沒有分母就換算不出剩餘額度，硬換算就是造假")),
    ),
)


def named_sources_text() -> str:
    """線框具名的三個來源，**現在各自在這面牆上的處境**（純函式，零 streamlit）。

    ⚠️ **為什麼這一段必須常駐、而且必須在「牆上有沒有那一格」之外另外講**：
    接上 `@monitored` 只讓那一支**有資格**出現在牆上；它真的出現，還要
    「那個 L1 模組在這個 session 被 import 過」。所以使用者可能會看到一面
    **沒有 FRED 的牆**，而那不代表 FRED 沒接線 —— 代表**還沒有人載入過它**。
    這一段就是把「應該看得到什麼」講出來，不讓「牆上沒有」被讀成「沒問題」。
    """
    _lines: list[str] = ["**線框具名的三個來源，現在各自的狀態**："]
    for _s in NAMED_SOURCES:
        if _s.wired:
            _lines.append(
                f"　· **{_s.label}｜已接線** —— 牆上的名字是 `{_s.fetcher}`，"
                f"量到的是：{_s.covers}。")
        else:
            _lines.append(
                f"　· **{_s.label}｜仍然量不到** —— {_s.covers}；"
                "它在下面被**具名畫成一張灰卡**，理由與下一步寫在卡上。")
    _lines.append(
        "⚠️ **「已接線」不保證你現在就看得到那一格**：接線只讓它**有資格**"
        "出現在牆上，真的出現還要「那個 L1 模組在這個 session 被載入過」。"
        "牆上找不到它 → 代表**還沒有人載入過**，不是它壞了。")
    _lines.append(
        "⚠️ **一支綠燈不等於那個來源整體都好** —— 同一個來源可以有很多支 fetcher，"
        "這面牆量到的單位是 **fetcher**，不是**來源**。")
    return "\n\n".join(_lines)


def build_unmeasured_cards() -> tuple[_Built, ...]:
    """量不到的來源 —— **具名畫出來，一張都不准跳過**。

    ⚠️ **這些卡存在的唯一理由**：不畫，畫面就會是滿版綠，
    而使用者不會知道某個常被引用的來源根本沒被量到。
    「跳過不畫」是本頁最隱形的一種假綠燈（見檔頭第二段）。

    ⚠️ **FE-20 把 FRED 與 TWSE 接上之後，這支函式與 `UNMEASURED_SOURCES`
    都沒有被拆掉** —— 少的只是清單裡的兩筆。接線讓某一筆離開清單是正常的；
    **把機制拿掉**才是把第二種假綠燈放回來（那時「量不到」會變成「畫面上不存在」）。
    """
    return tuple(build_l0_card(_s) for _s in UNMEASURED_SOURCES)


# ══════════════════════════════════════════════════════════════════
# L0 燈號規格表（葉1 的門檻對照 ＋ 葉2 的「未接線／已失準」卡）
# ══════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class SpecRow:
    """一盞燈的規格（給對照表用）。全部欄位**原樣**取自 L0，本檔不改寫。"""

    key: str
    label: str
    family: str            #: "總經" / "持股"
    group: str
    direction: str
    unit: str
    threshold_text: str
    source: str
    why: str
    wired: bool = True
    unwired_reason: str = ""
    discriminative: bool = True
    degraded_reason: str = ""
    emits_level: bool = True
    no_level_reason: str = ""

    @property
    def direction_text(self) -> str:
        """方向的中文說法。L0 沒有給中文（見 `DIRECTION_LABELS` 的交接註記），
        認不得的字面值**原樣顯示**，不編一個看起來合理的說法。"""
        return DIRECTION_LABELS.get(self.direction, self.direction or "—")

    @property
    def flag_text(self) -> str:
        """這一盞的已知限制。**三個旗標互相獨立，可能同時成立。**"""
        _flags: list[str] = []
        if not self.wired:
            _flags.append("未接線")
        if not self.discriminative:
            _flags.append("門檻已失準")
        if not self.emits_level:
            _flags.append("依規格不出等級")
        return " · ".join(_flags) if _flags else "正常"


def _macro_threshold_text(spec: Any) -> str:
    """總經燈的門檻文字。

    ⚠️ **本檔不重新措辭門檻，只把 L0 的欄位並排**。
    `DangerSpec` 沒有 `threshold_text`（那是 `StationSpec` 才有的欄位），
    只有 `yellow` / `red` / `yellow_lo` / `red_lo` 四個數字 ＋ `unit` ＋
    `decimals`。這裡做的是**格式化**（把 L0 的數字照 L0 給的小數位印出來），
    **不是**發明一句門檻描述 —— 發明描述就會出現「規格表寫 1.5% 但實作用 2%」
    那種漂移（`CLAUDE.md §3.3`）。
    """
    _unit = str(getattr(spec, "unit", "") or "")
    _dec = int(getattr(spec, "decimals", 1) or 0)

    def _fmt(_v: Any) -> str:
        if _v is None:
            return ""
        try:
            return f"{float(_v):.{_dec}f}{_unit}"
        except (TypeError, ValueError):
            return str(_v)

    _parts = [f"黃線 {_fmt(getattr(spec, 'yellow', None))}",
              f"紅線 {_fmt(getattr(spec, 'red', None))}"]
    _ylo = _fmt(getattr(spec, "yellow_lo", None))
    _rlo = _fmt(getattr(spec, "red_lo", None))
    if _ylo:
        _parts.append(f"低側黃線 {_ylo}")
    if _rlo:
        _parts.append(f"低側紅線 {_rlo}")
    return " · ".join(_parts)


def _macro_rows() -> tuple[SpecRow, ...]:
    """總經燈（`shared/macro_buckets.py`）→ `SpecRow`。"""
    _out: list[SpecRow] = []
    for _s in list(BUCKET_DANGER_SPECS) + list(REFERENCE_TREND_SPECS):
        _out.append(SpecRow(
            key=str(getattr(_s, "key", "") or ""),
            label=str(getattr(_s, "label", "") or ""),
            family="總經",
            group=str(getattr(_s, "bucket", "") or ""),
            direction=str(getattr(_s, "direction", "") or ""),
            unit=str(getattr(_s, "unit", "") or ""),
            threshold_text=_macro_threshold_text(_s),
            source=str(getattr(_s, "source", "") or ""),
            why=str(getattr(_s, "note", "") or ""),
            wired=bool(getattr(_s, "wired", True)),
            unwired_reason=str(getattr(_s, "unwired_reason", "") or ""),
            discriminative=bool(getattr(_s, "discriminative", True)),
            degraded_reason=str(getattr(_s, "degraded_reason", "") or "")))
    return tuple(_out)


def _station_rows() -> tuple[SpecRow, ...]:
    """持股／個股燈（`shared/station_specs.py`）→ `SpecRow`。"""
    _out: list[SpecRow] = []
    for _s in STATION_SPECS:
        _out.append(SpecRow(
            key=str(getattr(_s, "key", "") or ""),
            label=str(getattr(_s, "label", "") or ""),
            family="持股",
            group=str(getattr(_s, "group", "") or ""),
            direction=str(getattr(_s, "direction", "") or ""),
            unit=str(getattr(_s, "unit", "") or ""),
            threshold_text=str(getattr(_s, "threshold_text", "") or ""),
            source=str(getattr(_s, "source", "") or ""),
            why=str(getattr(_s, "why", "") or ""),
            wired=bool(getattr(_s, "wired", True)),
            unwired_reason=str(getattr(_s, "unwired_reason", "") or ""),
            discriminative=bool(getattr(_s, "discriminative", True)),
            degraded_reason=str(getattr(_s, "degraded_reason", "") or ""),
            emits_level=bool(getattr(_s, "emits_level", True)),
            no_level_reason=str(getattr(_s, "no_level_reason", "") or "")))
    return tuple(_out)


@dataclass(frozen=True)
class SpecScan:
    """兩張 L0 規格表讀一次的結果。

    Attributes:
        rows: 全部燈的規格列（總經 ＋ 持股）。
        error: 讀取期例外。
    """

    rows: tuple[SpecRow, ...] = ()
    error: str = ""

    @property
    def has_rows(self) -> bool:
        return bool(self.rows)

    @property
    def unwired(self) -> tuple[SpecRow, ...]:
        return tuple(_r for _r in self.rows if not _r.wired)

    @property
    def degraded(self) -> tuple[SpecRow, ...]:
        return tuple(_r for _r in self.rows if not _r.discriminative)

    @property
    def no_level(self) -> tuple[SpecRow, ...]:
        return tuple(_r for _r in self.rows if not _r.emits_level)


def load_specs() -> SpecScan:
    """讀 L0 的兩張燈號規格表。**零 I/O、零 L3**（`@dataclass` 常數表）。"""
    try:
        _rows = _macro_rows() + _station_rows()
    except Exception as _e:  # noqa: BLE001 — 轉成紅卡，不吞
        print(f"[views/page_why] L0 規格表讀取失敗 → 轉紅態：{_e!r}")
        return SpecScan(error=repr(_e))
    return SpecScan(rows=_rows)


def build_spec_flag_card(row: SpecRow) -> _Built:
    """L0 **自己標記**的「未接線 / 門檻已失準」燈 —— 線框葉2 的
    `unwiredCells` / `degradedCells` 就是這一種格子。

    線框葉2 note 原文：「其他頁出現非綠色時，這裡要能說出是哪一源、以及
    **這一盞為什麼不能信**（`unwired_reason` / `degraded_reason` 直接讀自 SSOT）」。

    ⚠️ **旗標與原因都不是本檔判的**，全部來自 L0。旗標哪天被翻回 `True`，
    這張卡會自己消失 —— 本檔沒有寫死任何一盞。
    """
    _reason = row.unwired_reason if not row.wired else row.degraded_reason
    _now = ("**這一盞刻意沒有接**" if not row.wired
            else "**這一盞會亮，但別照門檻讀**")
    return build_l0_card(L0CardSpec(
        key=f"why.spec.{row.key}", label=f"{row.label}（{row.family}燈）",
        wired=row.wired, discriminative=row.discriminative,
        has_value=True,
        now=_now,
        why=_clean_reason(_reason),
        where=(f"{NO_EXIT_MARKER} —— 這是**規格層面**的已知限制，"
               "不是這一輪抓壞了，重按幾次都一樣；"
               "下方的門檻對照表有這一盞的完整規格"),
        facts=((L0_REASON_FACT_LABEL, L0_REASON_FACT_TEXT),
               ("這一盞的門檻", row.threshold_text or "—"),
               ("值從哪來", row.source or "—"))))


def build_spec_flag_cards(scan: SpecScan) -> tuple[_Built, ...]:
    """全部被 L0 標記的燈。**沒有被標記時回空 tuple**（那時牆上就不該有這種卡）。"""
    return tuple(build_spec_flag_card(_r)
                 for _r in (scan.unwired + scan.degraded))


# ══════════════════════════════════════════════════════════════════
# 葉1 教學（靜態 · 無 gate）
# ══════════════════════════════════════════════════════════════════
def build_lights_card(scan: SpecScan) -> _Built:
    """線框葉1 的「紅綠燈怎麼判 · 各門檻的出處」。**L0-only，零取數。**"""
    _n_macro = sum(1 for _r in scan.rows if _r.family == "總經")
    _n_hold = sum(1 for _r in scan.rows if _r.family == "持股")
    return build_l0_card(L0CardSpec(
        key="why.edu.lights", label="紅綠燈怎麼判 · 各門檻的出處",
        error=scan.error,
        has_value=scan.has_rows,
        value=f"{_n_macro} 盞總經燈 ＋ {_n_hold} 盞持股燈",
        reason=MISS_NO_INPUT,
        now="**門檻表讀不出來**",
        why="L0 規格表這一輪沒有回傳任何一盞燈的定義",
        where=(f"{NO_EXIT_MARKER} —— 這是規格表本身的問題，"
               "請回報給維護者"),
        facts=(
            ("門檻從哪來",
             "全部逐欄讀 L0 規格表（`shared/macro_buckets.py` ＋ "
             "`shared/station_specs.py`）—— **本頁一個門檻數字都沒有寫**，"
             "上游改門檻，下面的表會自己跟著改"),
            ("怎麼判",
             "每一盞燈自己宣告「方向」：越高越危險 / 越低越危險 / 兩側都危險；"
             "值過黃線 → 🟡，過紅線 → 🔴，都沒過 → 🟢，取不到值 → ⬜"),
            ("⚠️ 灰燈有四種，不是一種",
             "「還沒載入」「抓了沒值」「刻意沒接」「不適用」在畫面上都是灰的，"
             "但處置完全相反 —— 逐盞的差別看下方表格的「已知限制」欄"),
            ("完整清單", "見下方「逐盞門檻對照表」，兩張表分別是總經與持股"))))


#: 六因子的**權重**在 repo 裡的實況（實測 2026-09-07）。
#: ⚠️ 這裡**只描述現況、不重抄權重數字** —— 重抄就變成第三份。
HEALTH6_WHY: str = (
    "「健康評分六因子」的因子名與配分**沒有任何一份是可讀的資料結構**："
    "權重是 L2 `src/compute/scoring/scoring_helpers.py::calc_health_score` 裡的"
    "**inline 數字**，而 L0 `shared/position_throttle.py` 的註解裡另外抄了一份文字版"
    "（實測 2026-09-07：兩處各一份）。本頁一律走 L3／L0，"
    "**不去讀 L2 的函式內文，也不把那組數字在這裡抄第三份** —— "
    "抄第三份就是再製造一次漂移，而漂移正是這一頁存在的理由")

HEALTH6_WHERE: str = (
    f"{NO_EXIT_PREFIX}"
    "要接上，正解是在 L0 補一份 `((因子名, 配分), …)` 的常數表，"
    "讓 L2 的 `calc_health_score` 與本頁**讀同一份**；"
    "退而求其次也可以在 `src/services/` 補一支回傳因子表的 L3。"
    "⚠️ **在那之前，這一格空著是誠實的** —— "
    "在這裡貼一份手抄的權重，等於在「解釋數字怎麼來」的頁面上放一個沒有出處的數字")


def build_health6_card() -> _Built:
    """線框葉1 的「健康評分六因子」—— **本批未接線**。"""
    return build_l0_card(L0CardSpec(
        key="why.edu.health6", label="健康評分六因子",
        wired=False,
        now="**六個因子各佔幾分，本頁還說不出來**",
        why=HEALTH6_WHY,
        where=HEALTH6_WHERE,
        facts=(("接線後的樣子", "六個因子逐項列出名稱與配分，合計 100"),
               ("卡住的那一步", "配分沒有 SSOT（L2 inline ＋ L0 註解各一份）"),
               ("⚠️ 順帶一提",
                "L0 `shared/health_thresholds.py` 有的是**等第分界**"
                "（A 級 / B 級的下界），那是**另一件事** —— "
                "分界說的是「幾分算好」，因子說的是「這幾分怎麼算出來的」"))))


def _scale_rows(keys: Sequence[str]) -> tuple[SpecRow, ...]:
    """spec key → `SpecRow`。查無此 key **直接跳過**，不編一個假的出來。

    ⚠️ 跳過是唯一誠實的選項：`SPECS_BY_KEY` 是 L0 的 SSOT，
    key 不在裡面代表**規格表改過而本檔沒跟上**。這時補一列「（不明）」
    會讓使用者以為那盞燈存在。
    """
    _out: list[SpecRow] = []
    _by_key = {_r.key: _r for _r in _station_rows()}
    for _k in keys:
        if _k not in SPECS_BY_KEY or _k not in _by_key:
            print(f"[views/page_why] 規格表沒有 {_k!r} —— 兩套刻度揭露少一列")
            continue
        _out.append(_by_key[_k])
    return tuple(_out)


@dataclass(frozen=True)
class ScaleDisclosure:
    """線框葉1 的「兩套『健康度』刻度的差別」。

    ⚠️ **這一段是頁 4 指過來的地方**：`page_hold` 的 ② 卡在 degraded 時，
    `where` 寫的是「更完整的說明在『📖 憑什麼』」—— 也就是這裡。
    所以本頁這一段**必須比頁 4 完整**，不能只是同一段話再貼一次。
    """

    hold_rows: tuple[SpecRow, ...] = ()
    inspect_rows: tuple[SpecRow, ...] = ()
    degraded_notes: tuple[tuple[str, str], ...] = ()
    error: str = ""

    @property
    def degraded(self) -> bool:
        return bool(self.degraded_notes)

    @property
    def has_rows(self) -> bool:
        return bool(self.hold_rows and self.inspect_rows)


def build_scale_disclosure() -> ScaleDisclosure:
    """兩套刻度的資料來源。**零 I/O、零 L3** —— 只讀 L0 常數表。

    `degraded` 是**算出來的，不是寫死的**：任一側的燈在 L0 標了
    `discriminative=False` 就成立。旗標若被改回 `True`，這張卡會自己回到 live。
    """
    try:
        _hold = _scale_rows(HOLD_SCALE_SPEC_KEYS + HOLD_SCALE_INPUT_SPEC_KEYS)
        _inspect = _scale_rows(INSPECT_SCALE_SPEC_KEYS)
    except Exception as _e:  # noqa: BLE001 — 轉成紅卡，不吞
        print(f"[views/page_why] 兩套刻度讀取失敗 → 轉紅態：{_e!r}")
        return ScaleDisclosure(error=repr(_e))
    _notes = tuple((_r.label, _r.degraded_reason)
                   for _r in (_hold + _inspect) if not _r.discriminative)
    return ScaleDisclosure(hold_rows=_hold, inspect_rows=_inspect,
                           degraded_notes=_notes)


def build_scale_card(disclosure: ScaleDisclosure) -> _Built:
    """線框葉1 的「兩套『健康度』刻度的差別」—— **常駐揭露，非摺疊**。"""
    _facts: list[tuple[str, str]] = [
        ("💼 我的持股 › 戰情表「健檢」", HOLD_SCALE_SHAPE),
        ("🔬 查一檔 › 判決卡「健康度」", INSPECT_SCALE_SHAPE),
        ("為什麼不可互比",
         "一個是**序數**（🟢 只表示「比 🟡 好」，兩盞之間沒有距離），"
         "一個是**基數**（分數可以相減、可以算平均）—— "
         "拿 🟢 去對 80 分，是把兩種不同的量測混成一個數字"),
        ("⚠️ 具體會怎麼錯",
         "「健檢 🟢 但健康度只有 62 分」不是矛盾，也不是其中一邊算錯 —— "
         "它們**問的不是同一個問題**：一個問「這檔該不該汰換」，"
         "一個問「這檔財報體質打幾分」。看到不一致時要做的是分別讀，不是取平均"),
        ("兩套各自的門檻", "見這張卡下面的兩張對照表，逐盞列出門檻與出處"),
    ]
    for _label, _reason in disclosure.degraded_notes:
        # L0 的 `degraded_reason` **原樣透傳**（facts 走 `st.caption`，
        # 不受 `Note` 的 glyph 驗證拘束，所以這裡是原文，不是洗過的）。
        _facts.append((f"⚠️ 已失準：{_label}", _reason))
    return build_l0_card(L0CardSpec(
        key="why.edu.scales", label="同一個名詞，兩套刻度",
        error=disclosure.error,
        has_value=disclosure.has_rows,
        discriminative=(not disclosure.degraded),
        value="兩套刻度並存 —— 不可互比",
        reason=MISS_NO_INPUT,
        now=("**兩套刻度目前有一側已失準，本頁不提供跨頁比較**"
             if disclosure.degraded else "**兩套刻度的定義讀不出來**"),
        why=("其中一側的門檻來源在 L0 規格表標了 `discriminative=False`"
             "（燈會亮、也有等級，只是**別照門檻讀**）—— "
             "逐盞原因見上方的 facts 與下方對照表，那段文字是 L0 自己寫的，"
             "本頁沒有改寫"
             if disclosure.degraded else
             "L0 規格表這一輪沒有回傳可用的燈號定義"),
        where=("兩套刻度各自的出處與門檻**就在這張卡下面**，可以逐項對照；"
               "要看某一檔的實際數字，到「🔬 查一檔」或「💼 我的持股」各看各的，"
               "**不要把兩邊的數字放在一起比**"),
        facts=tuple(_facts)))


def build_legacy_edu_card() -> _Built:
    """既有 1,582 行靜態教學內容的搬遷 —— **本批未搬，據實說明**。"""
    return build_l0_card(L0CardSpec(
        key="why.edu.legacy", label="完整策略邏輯說明書（既有 📚 教學）",
        wired=False,
        now="**既有的完整教學內容還沒有搬到這一頁**",
        why=("線框 DECISIONS #9 裁決「**留，原樣搬到「📖 憑什麼 › 教學」**」，"
             "但那是一份 1,582 行的既有靜態內容，搬遷會動到既有分頁與 caller —— "
             "屬 `CLAUDE.md §8.4` step 4 的**範圍**問題，"
             "本批（只新增這一個檔）刻意不夾帶"),
        where=("**這一項有出口**：既有的 📚 教學分頁**沒有下架**，"
               "現在就可以照舊使用；"
               "本頁上面那幾格（門檻怎麼判、門檻出處、兩套刻度）是**新**的，"
               "既有教學裡沒有"),
        facts=(("為什麼不先貼一份摘要",
                "摘要會變成第二份教學，兩份遲早不一致 —— "
                "而「兩份說法不一致」正是這一頁要解的問題本身"),
               ("搬遷的範圍", "跨檔搬遷 ＋ 既有 caller，需先走 §8.4 step 4 的範圍提案"))))


def build_edu_cards(spec_scan: SpecScan,
                    disclosure: ScaleDisclosure) -> tuple[_Built, ...]:
    """葉1 教學的四張卡。**一張都不需要 gate**（線框：靜態 · 無 gate）。"""
    return (build_lights_card(spec_scan),
            build_health6_card(),
            build_scale_card(disclosure),
            build_legacy_edu_card())


# ══════════════════════════════════════════════════════════════════
# 葉2 工程師版（摺疊 ＋ 一顆 checkbox 全有全無 · 不加 form）
# ══════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class EngineerRequest:
    """工程師版的 gate。**就是那一顆 checkbox 的當下值，沒有第二層。**"""

    opened: bool


def build_engineer_card(req: EngineerRequest, scan: SourceScan) -> _Built:
    """整段進階診斷**自己**的狀態。

    ⚠️ **它只看「L0 登錄表讀不讀得出來」，不看任何一盞燈的死活。**
    這是「三態不得混」的結構性落點：一盞來源燈紅了是**有效結果**
    （那一盞自己會紅），**不代表診斷壞了**。用一格的狀態去代表一整段，
    會讓「某個源這輪沒回」與「診斷本身掛了」在畫面上長得一樣。

    邊界：
      (a) **沒勾** → `requested=False` → idle。而且**本輪不帶任何結果進來**
          （下面第一行就把 scan 換成空的）—— 否則 L0 會因為
          「requested=False 卻帶了值」當場 `ValueError`（那是它在防
          「把上一輪殘留當本輪事實」）。
      (b) 勾了、登錄表讀得出來 → live（**即使裡面一列都沒有** ——
          「讀得到但是空的」是有效結果，由 `build_empty_registry_card()` 說明）。
      (c) 勾了、登錄表讀爆了 → failed 🔴。

    ⚠️ **(a) 的那一行不是靜默丟棄。** 呼叫端（`_render_engineer_block`）本來就
    已經 gate 過一次（沒勾根本不會去讀），所以這裡收到「沒勾卻帶著結果」代表
    有人繞過了那道 gate —— 那是 bug，不是常態。故**丟棄的同時 log 一行**，
    讓它留得下線索（§1：不吞、不假裝沒發生）。
    """
    _scan = scan if req.opened else SourceScan()
    if (not req.opened) and (scan.scanned or scan.error):
        print("[views/page_why] 進階診斷沒勾，卻收到本輪的登錄表結果 → 已丟棄。"
              "gate 應該在呼叫端就擋住（`_render_engineer_block`）；"
              "會走到這裡代表有人繞過了那道 gate")
    _state = classify_ui_state(
        requested=req.opened,
        error=_scan.error or None,
        has_value=_scan.readable,
        reason=MISS_FETCH_FAILED)
    _facts: tuple[tuple[str, str], ...] = (
        ("這一段的出處", SRC_MONITOR),
        ("為什麼要一顆 checkbox 擋著",
         "摺疊只收合**視覺**，body 每次 rerun 照樣執行 —— "
         "埋起來一分效能都沒省。真正省下執行的是這顆 gate"),
        ("⚠️ 為什麼沒有包 form",
         "form 的價值是「N 個 widget 只送一次」；這裡**只有一個** widget，"
         "包了省不到任何一次 rerun，只是多一次點擊"
         "（線框 F7／DECISIONS #7 實測後撤回了 form 提案）"))
    if _state == UI_LIVE:
        return (Card(key="why.engineer.gate", label="進階診斷",
                     state=UI_LIVE,
                     value=f"已載入 · 登錄表有 {_scan.count} 支 fetcher"),
                _facts, "")
    if _state == UI_IDLE:
        _note = Note(now="**進階診斷未載入**",
                     why="六個面板各自會組大量表格，預設不跑",
                     where=ENGINEER_WHERE)
    else:
        _note = Note(now="**進階診斷本身讀不出來**",
                     why=_error_why(SRC_MONITOR, _scan.error),
                     where=(f"{NO_EXIT_MARKER} —— 這是 L0 登錄表的問題，"
                            "不是某一個資料來源壞掉；"
                            "請把上面那行訊息回報給維護者"))
    return (Card(key="why.engineer.gate", label="進階診斷",
                 state=_state, note=_note), _facts, "")


#: 工程師版六個面板裡**未接線的五個**（線框 live 原文列的六項，扣掉 Fetcher 監控）。
#: ⚠️ 每一項的「去哪補」都不同 —— 它們卡住的位置不一樣。
ENGINEER_PANEL_SPECS: tuple[L0CardSpec, ...] = (
    L0CardSpec(
        key="why.engineer.registry", label="資料源清單",
        wired=False,
        now="**全站來源清單本頁讀不到**",
        why=("清單的 SSOT 住在 L1 `src/data/core/data_registry.py`，"
             "現行的診斷面板是直接讀 `st.session_state['data_registry']`（由總經頁寫入）。"
             "本頁是 L5，既不得直呼 L1，也不想依賴「你得先去過另一頁」"),
        where=(f"{NO_EXIT_PREFIX}"
               "在 `src/services/` 補一支回傳來源清單的唯讀 L3"
               "（把 `data_registry` 轉出來即可，不需要新的取數）"),
        facts=(("線框對這一格的期待", "全站資料來源逐筆列出，含最新時間戳"),
               ("卡住的那一步", "L1 的清單沒有 L3 轉出"))),
    L0CardSpec(
        key="why.engineer.reconcile", label="雙演算法對帳（§4.3）",
        wired=False,
        now="**雙演算法對帳本頁跑不了**",
        why=("對帳的純函式在 L2（`src/compute/risk/reconcile.py` 的"
             "`compute_health_score_arithmetic` / `_min_of_factors`），"
             "但 `src/services/` **沒有**任何一支把它包起來，"
             "而且它要的輸入也得由上游餵進來"),
        where=(f"{NO_EXIT_PREFIX}"
               "在 `src/services/` 補一支 L3 wrapper，"
               "由它負責取輸入並回傳兩種算法的差額"),
        facts=(("線框對這一格的期待", "同一個指標兩種算法並排，差額超過容差就標紅"),
               ("卡住的那一步", "L2 有純函式，但沒有 L3 wrapper、也沒有輸入來源"))),
    L0CardSpec(
        key="why.engineer.api_root", label="API 根因診斷",
        wired=False,
        now="**API 根因診斷本頁不做**",
        why=("現行實作（`src/ui/pages/api_diagnostic.py`）會**當場對外送出請求**"
             "來比對「走 proxy vs 直連」。那是 L5 直接打外部 API，"
             "正是 `CLAUDE.md §8.2` 明文禁止的；把它 import 進來"
             "等於把違憲一起繼承"),
        where=(f"{NO_EXIT_PREFIX}"
               "要在本頁做，得先把那段探測搬到 L1／L3（連線探測本來就是取數），"
               "本頁只負責顯示結果。⚠️ 在那之前，既有的 🔎 資料診斷分頁**沒有下架**"),
        facts=(("線框對這一格的期待", "金鑰來源 · proxy 設定 · 各 endpoint 雙跑比對"),
               ("卡住的那一步", "探測邏輯住在 L5 且會直接對外連線"))),
    L0CardSpec(
        key="why.engineer.raw", label="原始資料表",
        wired=False,
        now="**原始資料表本頁看不到**",
        why=("原始表要的是「這一輪各頁抓回來的 DataFrame 本體」，"
             "而那些只存在於各頁自己的 `st.session_state`。"
             "本頁去翻別頁的 session key 等於跟那些頁面**用約定俗成的字串耦合** —— "
             "對方改一個 key，這裡就會靜默變空（而空白看起來像沒問題）"),
        where=(f"{NO_EXIT_PREFIX}"
               "正解是由 L3 提供一份具名的快照介面，而不是讓 UI 互相翻 session"),
        facts=(("線框對這一格的期待", "各來源原始 DataFrame 就地展開"),
               ("卡住的那一步", "沒有具名介面，只有各頁私有的 session key"))),
    L0CardSpec(
        key="why.engineer.calibration", label="門檻校準",
        wired=False,
        now="**門檻校準本頁跑不了**",
        why=("校準是一支 `scripts/` 下的離線工作（季度 cron ＋ PR 審閱後才寫入），"
             "現行面板是從 UI 直接 import `scripts/`。"
             "本頁不從 UI 觸發離線腳本 —— 那會讓一次點擊變成一次可能改到門檻的動作"),
        where=(f"{NO_EXIT_PREFIX}"
               "要在本頁**唯讀顯示**校準結果，可由 L3 轉出 "
               "`shared/macro_calibration.py` 讀到的當前值；"
               "**觸發重新校準**則屬另一件事，需要客戶拍板"),
        facts=(("線框對這一格的期待", "當前校準值與上次校準時間"),
               ("卡住的那一步", "現行入口是從 UI import `scripts/`"),
               ("⚠️ 兩件事要分開",
                "「顯示現在的門檻」是唯讀，可以做；"
                "「重跑校準」會改到全站判燈，屬不可逆操作"))),
)


def build_engineer_panel_cards() -> tuple[_Built, ...]:
    """工程師版六項裡**未接線的五項**。

    ⚠️ **只有在 gate 打開時才會被建構** —— 沒打開時整段不畫，
    只留一張 idle 卡（`build_engineer_card`）。這正是「三態不得混」的落點：
    「還沒打開」與「打開了但這一項沒接線」是兩件事，**不會同時出現在畫面上**。
    """
    return tuple(build_l0_card(_s) for _s in ENGINEER_PANEL_SPECS)


# ══════════════════════════════════════════════════════════════════
# 葉3 AI 問答（chat_input · 天然 gate）
# ══════════════════════════════════════════════════════════════════
#: 沒有金鑰時的錯誤字串。**線框 err 原文：「🔴 AI 問答未啟用 / 未偵測到 API 金鑰」。**
#: ⚠️ 這裡不寫 glyph（`Note` 會拒收），glyph 由狀態頻道統一供給。
NO_KEY_ERROR: str = "未偵測到 Gemini API 金鑰（部署端沒有設，或這個環境讀不到）"

NO_KEY_WHERE: str = (
    "**其他分頁的功能完全不受影響** —— 只有這一葉需要金鑰。"
    "金鑰目前由部署端提供（`st.secrets` 或環境變數的 `GEMINI_API_KEY`）；"
    f"{NO_EXIT_MARKER}在這一頁就地設定，因為那等於在畫面上收憑證 —— "
    "要開這個入口必須先由客戶拍板「這一頁可以收金鑰」，本批不做")

QA_IDLE_WHY: str = (
    "AI **只根據本站已經載入的資料**作答，不自行上網查 —— "
    "所以它不會憑空生出數字；某一頁如果還沒載入，"
    "它會直接說「那一頁還沒有資料」，而不是猜一個")
QA_IDLE_WHERE: str = "直接在下方輸入問題並送出，**送出本身就是啟動**（不需要再按別的鈕）"


@dataclass(frozen=True)
class QaRequest:
    """這一輪使用者有沒有送出問題。**`asked` 就是葉3 的 gate。**

    ⚠️ `st.chat_input` 只有在「使用者這一輪剛送出」時才回字串，其餘 rerun 回
    `None` —— 它**天生**就是一個乾淨的 gate 旗標（線框：「天然 gate」）。
    本檔**不**用 `len(history)` 之類的東西頂替：那會讓「上一輪問過、
    這一輪沒問」被誤判成「這一輪問了」，正是 L0 鐵律禁止的從資料反推。
    """

    asked: bool
    question: str = ""
    history: tuple[Mapping[str, Any], ...] = ()


@dataclass(frozen=True)
class QaReadout:
    """一輪問答的 L3 產出。

    Attributes:
        asked: 由 `QaRequest.asked` 帶下來（**不是**從 `text` 反推）。
        answered: 這一輪拿到非空的回答了沒有。
        text / model / tool_calls: L3 原樣透傳。
        error: 呼叫期例外、上游回報的錯誤、或「沒有金鑰」。非空 = 紅。
        key_missing: 錯誤是不是「沒金鑰」這一種（文案完全不同，故分開帶）。
    """

    asked: bool
    answered: bool = False
    text: str = ""
    model: str = ""
    tool_calls: tuple[str, ...] = ()
    error: str = ""
    key_missing: bool = False


def load_qa(req: QaRequest) -> QaReadout:
    """跑一輪 AI 問答。**`req.asked` 為 False 時一行 L3 都不呼叫。**

    ⚠️ **連「有沒有金鑰」都不先問。** 讀金鑰是 L3 呼叫（會碰 `st.secrets`
    與環境變數），在使用者送出問題之前去問一次，就違反了本頁對自己的承諾
    「沒叫過就不發任何請求」，而且會讓一個從沒用過 AI 的使用者一進頁面
    就看到紅色 —— 那正是 v3 §02 要杜絕的假性錯誤。

    邊界：
      (a) **還沒問** → `asked=False` → idle（線框 grey：「⬜ 尚未提問」）。
      (b) **沒有金鑰** → 紅（線框 err：「🔴 AI 問答未啟用 / 未偵測到 API 金鑰」）。
      (c) **L3 拋例外**（含 late import 失敗）→ 紅。
      (d) **回來了但 `ok=False`** → 紅，並把上游的訊息原樣帶出來。
      (e) **回來了、`ok=True`、但沒有內容** → 灰的 `empty`：
          那是**有效結果**（模型真的沒話說），不是故障。
    """
    if not req.asked:
        return QaReadout(asked=False)
    try:
        from src.services.app_ai_service import get_gemini_api_key
        _key = str(get_gemini_api_key() or "").strip()
    except Exception as _e:  # noqa: BLE001 — 轉成紅態顯示，不吞
        print(f"[views/page_why] 讀 AI 金鑰失敗 → 轉紅態：{_e!r}")
        return QaReadout(asked=True, error=repr(_e))
    if not _key:
        return QaReadout(asked=True, key_missing=True, error=NO_KEY_ERROR)
    try:
        from src.services.ai_qa_service import run_agent
        _res = run_agent(req.question, list(req.history), api_key=_key)
    except Exception as _e:  # noqa: BLE001 — 轉成紅態顯示，不吞
        print(f"[views/page_why] AI 問答失敗 → 轉紅態：{_e!r}")
        return QaReadout(asked=True, error=repr(_e))
    _ok = bool(getattr(_res, "ok", False))
    _text = str(getattr(_res, "text", "") or "").strip()
    _err = str(getattr(_res, "error", "") or "").strip()
    _model = str(getattr(_res, "model", "") or "")
    _tools = tuple(
        str((_c or {}).get("name", "") if isinstance(_c, Mapping) else _c)
        for _c in (getattr(_res, "tool_calls", ()) or ()))
    if (not _ok) or _err:
        return QaReadout(asked=True, model=_model, tool_calls=_tools,
                         error=_err or UNKNOWN_ERROR_TEXT)
    return QaReadout(asked=True, answered=bool(_text), text=_text,
                     model=_model, tool_calls=_tools)


def build_qa_card(qa: QaReadout) -> _Built:
    """線框葉3 的狀態卡。**回答本身不畫在卡上**（那是聊天氣泡，見渲染段）。

    ⚠️ **這張卡講的是「這一輪問答的狀態」，不是「這一頁能不能用 AI」。**
    冷啟動時它是 idle（還沒問），**不是**紅色 —— 即使根本沒有金鑰。
    「沒有金鑰」要等使用者真的問一次才會被發現，而那是對的：
    在問之前先亮紅燈，等於替一個還沒發生的失敗製造一次假警報。
    """
    _state = classify_ui_state(
        requested=qa.asked,
        error=qa.error or None,
        has_value=qa.answered,
        reason=MISS_NO_INPUT)
    _facts: list[tuple[str, str]] = [
        ("這一葉的出處", f"{SRC_QA_KEY}　＋　{SRC_QA_AGENT}"),
        ("AI 拿得到什麼",
         "只有本站工具回傳的結構化結果。它被要求「需要數字時一律呼叫工具，"
         "嚴禁自行計算或杜撰」—— 工具回不出來時它必須說是哪個來源、為什麼"),
    ]
    if qa.model:
        _facts.append(("模型", qa.model))
    if qa.tool_calls:
        _facts.append(("這一輪用到的工具", " · ".join(qa.tool_calls)))

    if _state == UI_LIVE:
        return (Card(key="why.qa", label="AI 問答", state=UI_LIVE,
                     value="已回答（內容在上方對話裡）"),
                tuple(_facts), "")
    if _state == UI_IDLE:
        _note = Note(now="**尚未提問**", why=QA_IDLE_WHY, where=QA_IDLE_WHERE)
    elif qa.key_missing:
        _note = Note(now="**AI 問答未啟用**",
                     why=NO_KEY_ERROR, where=NO_KEY_WHERE)
    elif _state == UI_FAILED:
        _note = Note(now="**這一輪問答失敗了**",
                     why=_error_why(SRC_QA_AGENT, qa.error),
                     where=("可以換個問法再送一次；"
                            "若持續失敗，請把上面那行訊息回報給維護者。"
                            "**其他分頁的功能完全不受影響**"))
    else:
        _note = Note(now="**這一輪沒有回答內容**",
                     why=("上游沒有回報錯誤，但也沒有給任何文字 —— "
                          "這是一個**有效結果**（模型真的沒話說），不是故障"),
                     where="換一個更具體的問法再送一次（例如指名一檔代號）")
    return (Card(key="why.qa", label="AI 問答", state=_state, note=_note),
            tuple(_facts), "")


def read_history(session: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    """讀對話紀錄。形狀怪的一律當成空（**不猜**）。"""
    _raw = session.get(SS_QA_HISTORY)
    if not isinstance(_raw, (list, tuple)):
        return ()
    return tuple(_m for _m in _raw if isinstance(_m, Mapping))


def _append_history(role: str, content: str) -> None:
    """把一則訊息接到對話紀錄尾巴。

    ⚠️ **用 `setdefault` ＋ `append`，刻意不寫 `st.session_state[key] = …`**：
    本頁的 gate 全部是 widget 的當下值（checkbox / chat_input），
    **沒有任何一個 gate 是 session key**。禁止本檔出現 session 下標指派，
    等於在結構上保證「沒有人可以在這裡偽造一個『使用者問過了』」。
    守衛：`tests/test_p05_why_view.py::TestNoSessionSubscriptWrite`。
    """
    _hist = st.session_state.setdefault(SS_QA_HISTORY, [])
    if isinstance(_hist, list):
        _hist.append({"role": role, "content": content})


# ══════════════════════════════════════════════════════════════════
# 渲染（薄；所有判斷都在上面的純函式裡）
# ══════════════════════════════════════════════════════════════════
def _render_one(built: _Built) -> None:
    """畫一張卡，**並且不讓它把整頁畫到一半就死掉**。

    ⚠️ **本體在共用層** `_ui_kit.render_card_isolated()`（頁 1／2／3／4 已上移，
    本頁**不寫第五份**）。本函式只剩「把本頁專屬的三樣東西綁上去」：
    log 前綴 / 出處文案（出事的是哪一層只有本頁知道）/ 去哪補。
    """
    _card, _facts, _signal = built
    render_card_isolated(
        _card, facts=_facts, signal_text=_signal,
        owner="views/page_why",
        error_why=lambda _err: _error_why(SRC_RENDER, _err),
        where=("這是渲染層的問題，不是你操作的問題 —— "
               f"{NO_EXIT_MARKER}；請把上面那行訊息回報給維護者"))


def _render_row(builts: Sequence[_Built]) -> None:
    """一列卡（鐵律 1：`grid()` 內部硬夾 `MAX_COLS`，多的換行排下一列）。

    ⚠️ 線框葉2 註記「**原 `columns(7)` 降階**」講的就是這裡：
    這面牆的格子數是**動態的**（登錄幾支就幾格），所以它天生是
    「格子超過 3 個就換行排第二排，不是加欄」最典型的場景。
    """
    for _chunk, _columns in grid(tuple(builts), MAX_COLS):
        for _built, _col in zip(_chunk, _columns):
            with _col:
                _render_one(_built)


def _spec_table_rows(rows: Iterable[SpecRow]) -> list[dict]:
    """規格列 → `st.dataframe` 的 records。**全部原樣透傳，不改寫。**"""
    return [{
        "這一盞": _r.label,
        "分組": _r.group or "—",
        "方向": _r.direction_text,
        "門檻": _r.threshold_text or "—",
        "值從哪來": _r.source or "—",
        "在防什麼": _r.why or "—",
        "已知限制": _r.flag_text,
    } for _r in rows]


def _render_edu_leaf() -> None:
    """葉1 教學：**靜態 · 無 gate**（線框 grey 原文：「這頁沒有灰態」）。"""
    section_header(
        f"葉1 · {LEAF_EDU_TITLE}",
        "線框：**靜態 · 無 gate** —— 這一葉不取任何數，"
        "所以它永遠可讀，也永遠不會因為「還沒載入」而空掉。")

    _specs = load_specs()
    _scales = build_scale_disclosure()
    _render_row(build_edu_cards(_specs, _scales))

    if not _specs.has_rows:
        return

    section_header("逐盞門檻對照表",
                   "**這就是「各門檻的出處」** —— 每一欄都直接來自 L0 規格表；"
                   "本頁沒有改寫任何一個字，也沒有寫死任何一個數字。")
    for _family, _hint in (("總經", "五桶紅綠燈（🚦 今天 那一頁在用的）"),
                           ("持股", "戰情表與判決卡（💼 我的持股 / 🔬 查一檔 在用的）")):
        _rows = tuple(_r for _r in _specs.rows if _r.family == _family)
        if not _rows:
            continue
        st.caption(f"**{_family}燈** —— {_hint}（{len(_rows)} 盞）")
        st.dataframe(_spec_table_rows(_rows), hide_index=True, width="stretch")

    _no_level = _specs.no_level
    if _no_level:
        st.caption(
            "**依規格就不出等級的燈（不是壞掉，是還沒有判燈規則）**　"
            "⚠️ 這一類**刻意不給狀態燈** —— 七態裡沒有任何一態在講"
            "「有值、也照印，但依規格從來不出等級」，"
            "硬塞任何一態都會對使用者說錯話（`unwired` 說它沒接、"
            "`degraded` 說它門檻失準、`empty` 說它沒資料，三句都不是實情）。")
        for _r in _no_level:
            # L0 的 `no_level_reason` **原文透傳**（`st.caption` 不受 `Note` 拘束）。
            st.caption(f"　· **{_r.label}**：{_r.no_level_reason}")


def _render_user_health_wall() -> None:
    """葉2 使用者版：**常駐** 3 欄燈號卡牆（線框 `cols:3`）。"""
    section_header(
        f"葉2 · {LEAF_DATA_HEALTH_TITLE}（使用者版 · 常駐）",
        "線框：**3 欄燈號卡牆**（原 `columns(7)` 降階）。"
        "每一格**逐格獨立判態** —— 一格壞不把另外兩格一起染色。")

    _scan = load_sources()
    if not _scan.readable:
        # 登錄表本身讀不出來 → 一張紅卡把話說完（這時牆上不該有任何綠格子）。
        _render_one(build_engineer_card(EngineerRequest(opened=True), _scan))
    elif _scan.probes:
        _render_row(tuple(build_source_card(_p) for _p in _scan.probes))
    else:
        _render_one(build_empty_registry_card())

    # ⚠️ 下面這三段 caption 全部**常駐**（不得包進任何 if）——
    #    它們是本頁對「這面牆說得出什麼」的揭露，不是隨狀態出現的補充說明。
    st.caption(named_sources_text())
    st.caption(CACHE_SEMANTICS)

    st.caption("**具名、但這面牆量不到的來源** —— "
               "刻意畫出來，不是漏了：不畫，畫面會是滿版綠。")
    _render_row(build_unmeasured_cards())

    _specs = load_specs()
    _flags = build_spec_flag_cards(_specs)
    if _flags:
        st.caption("**L0 規格表自己標記的「未接線 / 已失準」** —— "
                   "原因逐字讀自 SSOT，本頁沒有改寫。")
        _render_row(_flags)

    st.caption(COVERAGE_DISCLOSURE)


def _render_engineer_block() -> None:
    """葉2 工程師版：**摺疊 ＋ 一顆 checkbox 全有全無 · 不加 form**。

    ⚠️ **兩步，兩個不同的 label**（線框 N5 補註逐字記載上一輪把它們混成一個）：
    先「展開」摺疊區，再「勾」裡面那一顆 checkbox。
    """
    with st.expander(ENGINEER_EXPANDER_LABEL, expanded=False):
        st.caption(ENGINEER_CAPTION)
        _opened = bool(st.checkbox(ENGINEER_CHECKBOX_LABEL,
                                   key=SS_ENGINEER_GATE,
                                   help=ENGINEER_CHECKBOX_HELP))
        _req = EngineerRequest(opened=_opened)
        # 沒勾 → **一次 L0 登錄表都不讀**，只畫 idle 卡。
        _scan = load_sources() if _opened else SourceScan()
        _render_one(build_engineer_card(_req, _scan))
        if not _opened:
            return

        st.caption("**六個面板** —— 目前只有「Fetcher 監控」接得上；"
                   "其餘五個各自卡在不同的地方，逐項寫在下面。")
        _render_row(build_engineer_panel_cards())

        st.caption("**🛰️ Fetcher 監控（`@monitored` 自我登錄）** —— "
                   "「未執行」＝ 本 session 尚無真實外抓"
                   "（**快取命中點不亮它**：第一次呼叫必然沒有快取可用）。"
                   "⚠️ 綠燈上那個**時間**是另一回事，見使用者版牆下的"
                   "「這面牆上的時間是什麼」。")
        if _scan.probes:
            st.dataframe(
                [{"fetcher": _p.name,
                  "分類": _p.category or "—",
                  "更新頻率": _p.frequency or "—",
                  "最後一次真實抓取": _p.last_called_at or "—",
                  "回了幾列": _p.rows or "—",
                  "耗時(ms)": _p.ms or "—",
                  "錯誤": _p.error or "",
                  "本頁看不懂的狀態": _p.unknown_status or ""}
                 for _p in _scan.probes],
                hide_index=True, width="stretch")
        else:
            st.caption("　登錄表目前是空的 —— 說明見上方使用者版的那張灰卡。")


def _render_qa_leaf(session: Mapping[str, Any]) -> None:
    """葉3 AI 問答：`st.chat_input` · **天然 gate**（送出本身就是啟動）。"""
    section_header(
        f"葉3 · {LEAF_QA_TITLE}",
        "線框：**chat_input · 天然 gate** —— 送出問題本身就是啟動，"
        "所以這一葉**沒有**額外的送出鈕，也沒有 form。")

    _history = read_history(session)
    for _msg in _history:
        _role = str(_msg.get("role") or "assistant")
        with st.chat_message("user" if _role == "user" else "assistant"):
            st.markdown(str(_msg.get("content") or ""))

    _typed = st.chat_input(QA_PLACEHOLDER, key="p05v_qa_input")
    _question = str(_typed or "").strip()
    _req = QaRequest(asked=bool(_question), question=_question,
                     history=_history)
    _qa = load_qa(_req)

    if _req.asked:
        with st.chat_message("user"):
            st.markdown(_question)
        _append_history("user", _question)
        if _qa.answered:
            with st.chat_message("assistant"):
                # 🧬 = AI 敘述旗標（沿用既有 🧬 AI 問答分頁的慣例）：
                # 讓使用者一眼看出這一段是模型寫的，不是本站算出來的數字。
                st.markdown(f"🧬 {_qa.text}")
            _append_history("assistant", f"🧬 {_qa.text}")

    _render_one(build_qa_card(_qa))


def render_page_why() -> None:
    """📖 憑什麼（IA v2 第 5 頁）。~~**本批無 production caller，刻意如此。**~~

    ⚠️ **2026-09-08 FE-36 事實更正（刪除線有意識保留，不是漏刪）**：
    那句在本檔剛落地那一批為真，之後接線的批次沒有回頭改它 ——
    **是 `b5bdb36`（側欄 radio 改動）之前就存在的漂移，不是這次弄壞的。**
    **現行**：`app.py::_ia_view_why()` 於側欄「🆕 新版戰情室（試用中）」radio
    選到本頁時 late import 並呼叫本函式。理由與守衛見檔頭 FE-36 那段。
    """
    _session = st.session_state

    st.markdown(f"## {ia_nav.page_label(ia_nav.PAGE_WHY)}")
    st.caption("解釋數字怎麼來、資料新不新鮮、以及直接問。")

    _leaf1, _leaf2, _leaf3 = st.tabs(
        [LEAF_EDU_TITLE, LEAF_DATA_HEALTH_TITLE, LEAF_QA_TITLE])

    # ⚠️ **本頁的三葉之間沒有任何 gate 依賴，所以顯示順序 = 執行順序。**
    # （頁 4 必須把葉2 的表單先跑一次，是因為它的 gate 被葉1 消費；
    #   本頁葉2 的 gate 只被葉2 自己消費、葉3 的 gate 只被葉3 自己消費，
    #   沒有跨葉的先後問題。）
    with _leaf1:
        _render_edu_leaf()
    with _leaf2:
        _render_user_health_wall()
        _render_engineer_block()
    with _leaf3:
        _render_qa_leaf(_session)
