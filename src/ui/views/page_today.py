"""src/ui/views/page_today.py — IA v2 第 1 頁「🚦 今天」的**版面重寫**（L5 UI）。

規格出處：`docs/wireframes/stock_ia_v1.html` 的 `PAGES[0]`（id=`today`），
客戶 2026-09-05 拍板。單一職責（線框 `job` 原文）::

    回答「今天能不能出手、出手到幾成」。

═══ 這個檔**不是**什麼（先讀這段）═════════════════════════════════════
它**不是**一個新的第 1 頁，也**不是**一套新的狀態模型。

`src/ui/tabs/tab_today.py`（PR #662，`tests/test_p01_today_skeleton.py` 守著）
已經是這一頁的**契約與純函式的家**。本檔做的是**版面呈現與互動排版的重寫**，
以及**接上葉2「指標明細」**（那一塊 `tab_today` 尚未做）。
所有型別（`Card` / `Note` / `Block`）、四態判定（`classify_macro_contract`）、
狀態列（`build_status_bar_cards`）、上游例外洗字（`scrub_state_glyphs` /
`upstream_error_why`）、更新模式讀取（`applied_update_mode`）、版面上限
（`MAX_COLS`）**一律 import 復用**，本檔**一個都不複寫**。

~~**本檔沒有 production caller**（`app.py` 本批不接線）。~~舊分頁不動、不下架。

⚠️ **2026-09-08 FE-36 事實更正 —— 刪除線是有意識保留，不是漏刪。**
那句在本檔剛落地那一批為真；**之後接線的批次沒有回頭改它** ——
也就是說 **這是 `b5bdb36`（側欄 radio 改動）之前就已經存在的漂移**，
不是這次弄壞的（一併收掉，但據實區分責任）。
**現行**：`app.py::_ia_view_today()` 在側欄「🆕 新版戰情室（試用中）」radio
選到本頁時 late import 並呼叫 `render_page_today()`；**沒被選到時本檔連 import 都不發生**
（`tests/test_ia_v2_sidebar_nav.py::TestNothingRunsUntilYouPick`）。
⚠️ **有 caller 之後，這一頁的每一個 bug 都是使用者看得到的** ——
不得再拿「反正沒有人在用」當放寬任何守衛的理由。
掛載形態由 `tests/test_p0x_view_mount_claims.py` 釘住：再改一次就轉紅。

═══ 四態的唯一真相源 ═══════════════════════════════════════════════════
L0 `shared/ui_state.py` 七態，是線框四態 ＋ 正常態的超集：

    灰態（無資料）→ `UI_EMPTY`（已請求但沒回值）／`UI_IDLE`（**還沒有人叫過**）
                     ⤷ 2026-09-23 起 `UI_EMPTY` 再分出 `UI_MISSING_RETRYABLE`（#7）
                       與 `UI_NOT_APPLICABLE`（#8），見本節末的 D-3(a) 附註
    未接線        → `UI_UNWIRED`   （`DangerSpec.wired=False`）
    已失準        → `UI_DEGRADED`  （`DangerSpec.discriminative=False`）
    紅態（真故障）→ `UI_FAILED`    （呼叫拋例外 / 來源回錯）
    正常          → `UI_LIVE`

⚠️ **2026-09-23（客戶裁示 D-3(a)）：`UI_EMPTY` 分出三種可分辨的缺值。**
本頁**判態的寫法一行未改** —— 分辨是 L0 `classify_ui_state()` 依既有的
`reason=` 自動做掉的（本頁本來就有在傳），畫面因此自動多出一層資訊：

    `MISS_NO_INPUT`       → `UI_MISSING_RETRYABLE`（#7 缺漏）    **再按一次有用**
    `MISS_NOT_APPLICABLE` → `UI_NOT_APPLICABLE`（#8 結構上不適用）**按幾次都一樣**
    其餘／沒給原因        → `UI_EMPTY`（無資料）                 **分不出是哪一種**

⛔ **判不出來時不准挑一個看起來合理的**：`MISS_NOT_ENOUGH`（等時間累積）與
`MISS_NO_VARIATION`（等它開始動）**刻意留在 `UI_EMPTY`** —— 它們重試無用，但也
**不是**「結構上不適用」，硬塞進 #8 等於對使用者說一句永久性的假話
（`CLAUDE.md §-2` 記載過同型事故：新上市標的收到「可以重跑一次」的錯誤指引）。
⛔ **本頁不得出現缺值家族的任何字面 glyph** —— 符號一律由 `state_meta()` 從 L0
供給一次。守衛 `tests/test_ui_empty_split.py` **整檔掃描、連註解與 docstring 都算**，
所以本段只寫得出常數名、寫不出符號本身；那是刻意的。

⚠️ **`idle` 與 `empty` 的分家不准合併** —— 那正是 `CLAUDE.md §1.A` 第 4 點
「未點擊載入＝灰色說明；系統真出錯＝紅色警示」。
⚠️ `classify_ui_state()` 的 `requested=` **必填、且禁止由 `bool(data)` 反推**。
本頁一共只有**三個** gate 旗標來源，每一個都是「上游自己標的事實」：

  1. **五桶 / 16 盞燈 / 今日關鍵** ← `upstream_requested(session)`：
     讀**上游 session key 的存在性**（`UPSTREAM_SESSION_KEYS`；沿用
     `tests/test_ui_state_model.py` 明文認可的
     `"_macro_compass_cache" in session_state` 那個 pattern）。
  2. **市場位階** ← `classify_macro_contract()`：讀契約自己的 `source`
     分支標記（`source != SOURCE_UNLOADED`），那是上游標的旗標。
  3. **建議持股（卡①）** ← `contract_attempted()`：**沿用第 2 條的判定**
     （`classify_macro_contract(...) != UI_IDLE`），因為 `get_allocation()`
     的 `is_loaded` 就是從同一次 `get_macro_state()` 帶下來的。

⚠️ **2026-09-07 修（紅隊實測）：卡①② 的 `requested=` 曾經是恆真式。**
修前寫的是 `requested=(bool(alloc_error) or alloc is not None)` ——
而 `get_allocation()` 的 return 只有 `return _cached` / `return _decision`，
**永不回 `None`**；`_load_allocation()` 也只在拋例外時回 `None`（並同時填
`alloc_error`）。兩條路合起來 ⇒ 那個運算式**恆為 True**，卡① 在真實
render path 上**沒有 idle 態**，冷啟動會顯示「叫了沒回」而不是「還沒有人叫」。
卡② 的 `requested=(bool(parallel_error) or parallel is not None)` 同構。
`tests/test_ui_state_model.py` 抓不到它 —— 那條守衛只比對 `requested=` 與
`has_value=` 的 AST 是否**逐字相同**，它自己的 docstring 就寫明「是護欄不是
證明」。**守衛綠燈不是合規證明。**
⚠️ 更強的一道：`requested` 為 False 時**根本不呼叫**五桶計算 ——
沒有輸入就不會有 `state=="ok"` 的紀錄，`classify_ui_state` 那條
「沒被叫過卻有值 → `ValueError`」的 fail-loud 在結構上就跑不到。

═══ 三個會讓畫面說謊的契約陷阱（實測結論，逐條處置）═══════════════════
1. **`get_macro_state()` 只有 9 個 key，沒有 `as_of` / `timestamp`。**
   → 本頁**不顯示任何「資料時間」欄位**。原規格要求逐格顯示 as_of，
     已撤回；改為在葉2 頁首用 `AS_OF_NOT_IN_CONTRACT` 一句話講明
     「契約無此欄位、要顯示得先擴充 L3」。**寧可說沒有，也不編一個時間。**
     可顯示的是 readiness 側車真的有的 `hit_source`（命中來源）。
2. **`normalize_regime()` 不認得 `'unknown'`，會把它洗成 `'neutral'`** ——
   等於把「未評估」偽裝成「震盪」。
   → 本檔**一次都沒有** import 或呼叫 `normalize_regime`。位階一律直接用
     `get_macro_regime()` 回來的 `regime` / `light`，不再加工。
3. **禁止合成第三顆燈。** `overall_verdict()`（16 盞燈的危險度，**不含方向**）
   與 `get_macro_regime()`（市場位階）實跑燈色不一致 39.5%、方向相反 18 組；
   客戶 2026-08-27 裁示**並列揭露、不得調和**。
   → 葉1 結論區**三張並排的卡**：建議持股 / 指標危險度 / 市場位階。
     本檔**不平均、不取 worst、不合成第三顆**，畫面上也**不比對**兩者
     （要比對的話，比較邏輯住在 `tab_macro_v2.parallel_verdict()`，
     本頁本批不渲染它）。

   ⚠️ **2026-09-07 修（紅隊實測）：「各自算完」原本在一條路徑上不成立。**
   修前的 `_load_parallel()` 開頭是 `if regime is None: return None, ""` ——
   而危險度那一半（`build_rows` → `bucket_summary` → `overall_verdict`）
   **完全不依賴 regime**，卻被 regime 的失敗連坐。實跑
   `build_verdict_tiles(None, 'RuntimeError("boom")', None,
   'RuntimeError("boom")', None, "")` 得到卡② `state=idle` 且理由寫
   「16 盞燈本輪一盞都沒有落在綠 / 黃 / 紅」—— **那 16 盞燈這一輪根本沒被
   算過**，等於畫面上出現一個「這一輪沒發生過的計算」的結論（§1 造假）。
   反方向也一樣：卡③ 修前寫 `if _regime_state == UI_LIVE and parallel is
   not None`，位階明明是 live、只因危險度那半組不出來就被畫成「尚未評估」。
   → **現行：兩半各自一支 loader（`_load_danger` / `_load_regime`），
   誰失敗只影響誰那一張卡。** 兩張卡的字面都走各自那一半的 SSOT
   （危險度：L4 `BAND_META`；位階：L0 `REGIME_LABEL`），
   與 `parallel_verdict()` 內部讀的是同一份，不是第二把尺。

═══ 葉2「指標明細」的取數路徑（**唯一**一條）═══════════════════════════
    L3 `services.section_inputs.load_section_inputs(st.session_state)`
      → L2 `compute.macro.macro_helpers.compute_five_bucket_summary(
             ..., readiness_out=rd)`
      → 側車 `rd` **恆為 16 筆**（缺席也有紀錄）
      → 門檻與燈號一律走 L0 `shared/macro_buckets.py`

⚠️ **任何從 `st.session_state` 直抽 `macro_info['vix']` 的寫法都是第二條
取數路徑**，本檔一處都沒有。分母就是 `len(BUCKET_DANGER_SPECS)`＝16；
`wired=False` 與 `discriminative=False` **刻意不排除出分母**
（燈會亮，只是判讀沒意義 —— 見 `DangerSpec` 的欄位註解）。

⚠️ **葉2 分成五桶（`BUCKET_ORDER`），不是線框的七段。** 線框七段
（A 市場狀態 / B 長期 / C 中期 / D 短線 / E 籌碼 / F 全球風險 / G 跨桶裁決）
住在 `tab_today.DETAIL_SEGMENTS`；16 盞燈涵蓋的是 B/C/D/E，
**A 與 G 沒有對應的燈、F 只被 `us10y` / `dxy` / `vix` 部分涵蓋**。
與其把七段硬套上去、留三段空殼假裝有結構，不如照 16 盞燈真正的歸屬分五段，
並在頁首講明這件事（`SEGMENT_COVERAGE_NOTE`）。

═══ 與線框的差異（**逐項揭露**，2026-09-07 補）═══════════════════════════
線框 `PAGES[0]` 葉1 的 ③ 是**三欄摘要（位階 / 動能 / 風險）**。

  · **葉1 ③ ＝ 線框的三欄摘要**，直接取用 `tab_today.build_today_blocks()`
    產出的 `today.summary` block（位階已接線、~~動能與風險誠實標未接線~~
    → 2026-09-26 起「風險」格接上指標危險度、動能仍誠實標未接線；見 `build_summary_tiles()`）。
    **零新增取數** —— 那個 block 本來每一輪就已經算出來了。
  · **五桶摘要移到葉2 的頁首**（葉2 本來就是五桶明細，那才是它的歸屬）。
    **內容一格都沒有刪**，只是換了位置。

⚠️ 2026-09-07 之前這裡是**未揭露的偏離**：③ 被換成「五桶摘要」，
而全檔連「三欄」「動能」`today.summary` 都 grep 不到，只留下編號「③」——
`build_today_blocks()` 每一輪照算，然後 7 個 block 丟掉 6 個。
改回線框**不需要客戶 gate**（那是回到已核准的線框，不是偏離它）；
**日後要再動這兩葉的版面才需要先出線框草稿**（`CLAUDE.md` §-1.5 A-8）。

═══ 這個檔擋得住什麼、擋不住什麼（**誠實邊界**，2026-09-07 補）═══════════
`load_macro_readout()` / `_load_*()` 的 `try/except` 擋得住的是
**呼叫期**例外（模組進得來、但呼叫時炸了）—— 紅隊實測那條路徑是好的：
`compute_five_bucket_summary` 拋例外時，`故障 15` 與 `repr(e)` 會上畫面 20 處。

⛔ **它擋不住 module-level 的 import 失敗，那會是整頁空白。**
本檔 module level 就 `from src.ui.tabs.tab_today import ...`，會連帶執行
`src/ui/tabs/__init__.py`。那條 import chain 上的模組**若在 import 階段就壞掉**，
`import page_today` 自己會先 `ImportError`，`render_page_today()` 根本不會被
呼叫到，畫面上**一個 markdown 都不會有**。

~~`src/ui/tabs/__init__.py` 是一個 **eager barrel**（檔頭自陳「即時轉發，
不是延遲載入」），一路把 152 個 `src.*` 模組 ＋ pandas ＋ plotly 全拉進來
（實測值，量測日 2026-09-07）—— 其中就包含
`src.services.section_inputs` 與 `src.compute.macro.macro_helpers`。~~
~~**為什麼不改成 lazy 而是把宣稱改誠實**（§-2）：真正的根因是那個 eager
barrel，而它在 `src/ui/tabs/`，**不在本批的檔案邊界內**。~~

⚠️ **2026-09-07 更新（同日稍晚，FE-7）：上面兩段刪除線是事實更正，不是漏刪。**
**決策者:AI 總管。** 那個 barrel **已經改成延遲載入了**，所以「拉進 152 個模組」
與「不在檔案邊界內」兩個前提都已不成立：
  · 實測 `import src.ui.views.page_today` 的 `src.*` 由 **152 → 6**
    （`src.ui` / `src.ui.tabs` / `src.ui.tabs.tab_today` / `src.ui.views` /
     `src.ui.views._ui_kit` / 本檔），`section_inputs` 與 `macro_helpers`
    **不再**出現在本檔的 import chain 上。
  · 紅隊實測（讓 `macro_helpers` 在 import 期拋 `ImportError`）：
    改前 `n_markdown=0`＋未捕捉例外；改後 `n_markdown=79`、例外為 `None`，
    錯誤轉成畫面上的紅態並進 stderr。

⚠️ **但上面那條 ⛔ 仍然完全有效，不要讀成「現在擋得住了」**：
本檔 module level 真正需要的模組（`tab_today` / `_ui_kit` / `shared.*`）
**若壞掉，整頁一樣空白**。延遲載入消掉的是**不相干模組的連坐**，
**不是**本檔自己的必要相依。故障半徑縮小，不等於故障消失。

═══ 原地重抓（T3-1，2026-09-09 客戶裁決）══════════════════════════════
~~本頁**只讀** session、**自己不取數**。~~
⚠️ **2026-09-09 更新：上面那句刪除線是有意識的政策變更，不是漏刪。決策者：客戶。**
裁決原文是「頁1『🚀 更新今日戰情』要**原地直接觸發台股今日資料重抓並即時刷新本頁**，
不要跳轉回舊分頁」。**舊句在它寫下的那天為真**（當時 submit 真的只記模式），
但一句過期的免責聲明比沒有更糟：它會叫使用者跑去別的分頁做他在這裡就能做的事。

**現行**：`_render_update_form()` 的 submit → `_run_refresh_now()` →
L3 `services.macro_refresh_service.refresh_macro_now()` → 報告落
`SS_REFRESH_REPORT` → `st.rerun()` → 下一輪 `_render_refresh_report()` 畫在頁首。

⛔ **這是一條「平行路徑」，不是收編舊分頁。** `src/ui/tabs/**` 本階段
**一個字都沒有動**（客戶明令舊 7 頁籤保留原樣），所以本頁按鈕**碰不到**
舊分頁其他區塊寫的東西 —— 建議持股（卡①）／市場位階（卡③）／今日關鍵的
門檻層／新聞桶都在射程外。**摸不到的一律逐條列在畫面上**
（清單 SSOT：`macro_refresh_service.UNTOUCHED_BLOCKS`），
不留白讓人以為整頁都是今天的（§1）。

═══ v2 卡面樣板（2026-09-23，客戶要的「一張給客戶看的樣板」）════════════
葉1 ① 那一排**三張卡裡只有第一張**（`verdict.exposure`）改走 v2 卡面；
另外兩張（`verdict.danger` / `verdict.regime`）**一行都沒動**，刻意留著當對照組。
CSS 與 HTML 一律 import `src/ui_v2/markup.py`（既有 repo 內模組、純字串、零 streamlit），
**本檔⛔ 不抄一份 CSS** —— 抄 ~30 條規則進 L5 就是第二個真相源（§2.1），
而且改了規格之後畫面**看起來仍然正常**、只是與規格對不上。
細節（徽章對映怎麼對出來的、灰字那一行怎麼壓、錯誤怎麼隔離）見下方「v2 卡面」區塊。

═══ 分層（CLAUDE.md §8.2）═════════════════════════════════════════════
L5。取數走 L3（`section_inputs` / `allocation_service` /
**`macro_refresh_service`**），計算走 L2（`macro_helpers` / `daily_key_alerts`），
門檻走 L0（`macro_buckets`），渲染走 L4（`macro_v2_cards` 的標籤函式）
與同層 kit（`_ui_kit`）。
**零 L1 import、零 `requests` / `yfinance` / FinMind、零檔案讀寫、
零 `@st.cache_data` / `@st.cache_resource`。**
⚠️ 上面這句**講的是本檔自己**，不是它呼叫的東西：按下更新之後，
L3 `macro_refresh_service` 當然會去打 L1 fetcher —— 那正是分層要的方向
（L5 → L3 → L1），本檔一行取數都沒有自己寫（v3 §01「UI 純畫面調用」）。
⚠️ `macro_refresh_service` 一律在 `_run_refresh_now()` 裡 **late import**：
它 module-level 會拉 `src.compute.macro` 這個 eager barrel，
擺在檔頭等於把 FE-7 消掉的「不相干模組 import 失敗 ⇒ 整頁空白」接回來。
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from html import escape as html_escape
from typing import TYPE_CHECKING, Any, Final, Mapping, Sequence

import streamlit as st

from shared import ia_nav
# ⚠️ 這兩個**模組物件**只為了「**用常數名反解常數值**」（`getattr`）——
#    見 `_v2_badge_to_l0_state()`：`src/ui_v2/components.py::BADGES` 存的是
#    **常數名字串**（`"UI_LIVE"` / `"MISS_NO_INPUT"`），不是值。用 `getattr` 反解 ＝
#    對映**由 SSOT 推出來**；手抄一張「名字 → 值」的表才是第二把尺（§2.1）。
from shared import station_specs as _station_specs
from shared import ui_state as _ui_state
# L0 SSOT：regime → 中文。`tab_macro_v2.parallel_verdict()` 讀的也是這一份，
# 本檔直接讀源頭**不是**第二把尺（見檔頭陷阱 3 的 2026-09-07 修註）。
from shared.allocation_decision import REGIME_LABEL
# 燈卡「變化方向」列（2026-09-24）：哪幾盞燈有這一列 ＋ 列標籤。純常數 L0。
from shared.lamp_direction_thresholds import (
    LAMP_DIRECTION_ERROR_TEMPLATE,
    LAMP_DIRECTION_FACT_KEY,
    LAMP_DIRECTION_KEYS,
    LAMP_DIRECTION_MISSING_REASON,
)
from shared.macro_buckets import (
    BUCKET_DANGER_SPECS,
    BUCKET_META,
    BUCKET_ORDER,
    LEVEL_COLOR,
    MISSING_NO_EXTRACTION,
    MISSING_NO_VALUE,
    MISSING_NOT_LOADED,
    MISSING_NOT_WIRED,
    MISSING_OUT_OF_RANGE,
    SPECS_BY_KEY,
    classify_danger,
    fmt_value,
    has_thresholds,
)
from shared.station_specs import (
    MISS_CONTRACT_DRIFT,
    MISS_NO_INPUT,
    MISS_NOT_APPLICABLE,
    MISS_TEXT,
)
from shared.ui_state import (
    UI_DEGRADED,
    UI_EMPTY,
    UI_FAILED,
    UI_IDLE,
    UI_LIVE,
    UI_LOADING,
    UI_MISSING_RETRYABLE,
    UI_NOT_APPLICABLE,
    UI_PARTIAL,
    UI_STATES,
    UI_UNWIRED,
    classify_ui_state,
)
from src.ui.tabs.tab_today import (
    # ⚠️ T3-1（2026-09-09）起**不再** import `CONTRACT_NO_EXIT_WHERE`：
    #    那句話寫死「本批的按鈕**還沒接上取數**」，而頁1 的按鈕當天已經
    #    接上了 —— 對本頁而言它已成假敘述。位階卡改用本檔的
    #    `EXIT_OUT_OF_REACH`（**接上了，但這一格不在射程內**，那才是實話）。
    #    ⛔ `tab_today.py` 本身一個字都沒動（檔案邊界）：那句話在**它自己那一頁**
    #    仍然為真，`tests/test_p01_today_skeleton.py` 照舊守著它。
    #
    # 📌 **2026-09-24 事實更正 —— 有意識的更正，⛔ 不是漏刪；上面整段一字未改。**
    #    上面那段講的是「**⛔ 不拿它當 `where=` 用**」，那**仍然完全有效** ——
    #    本檔所有自己寫的 `where=` 照舊只走 `EXIT_*`。
    #    **變的是它從頭到尾都還在畫面上這個事實**：位階卡 `degraded` 態刻意
    #    **整份沿用** `build_status_bar_card().note`（§2.1 SSOT：⛔ 不另寫一份文案，
    #    見下方該分支的註 ＋ `tests/test_p01_today_view.py` 逐欄釘死兩邊相同），
    #    ⇒ **那一態的 `where` 本來就是對面這個常數**，⛔ 不是本檔的 `EXIT_*`。
    #    🔴 **為什麼現在非 import 不可**：`_v2_exit_phrase()` 以 `is` 比**物件身分**
    #    查表，查不到就 `raise` ⇒ 不登記的話，`degraded` 的位階卡會在 v2 卡面
    #    **當場炸成紅卡**（本輪實跑抓到，⛔ 不是推測）。**import 它是為了「認得它」，
    #    ⛔ 不是為了「用它」** —— 兩件事不一樣。
    CONTRACT_NO_EXIT_WHERE,
    LEAF_CONCLUSION,
    LEAF_DETAIL,
    MODE_FORCE,
    MODE_LABELS,
    MODE_WARM,
    NO_EXIT_MARKER,
    # 🔴 2026-09-24 整頁卡化新增：未接線態的指路**常數**（`_staged_card()` 用的那一份）。
    #    import 它的理由與 `CONTRACT_NO_EXIT_WHERE` 同構 —— 是為了讓
    #    `_v2_exit_phrase()` 的 `is` 查表**認得它**，⛔ 不是為了「用它」寫新文案。
    #    本檔所有自己寫的 `where=` 照舊只走本檔的 `EXIT_*`。
    STAGED_ROLLOUT_WHERE,
    Card,
    Note,
    applied_update_mode,
    build_status_bar_card,
    build_status_bar_cards,
    build_today_blocks,
    classify_macro_contract,
    scrub_state_glyphs,
    upstream_error_why,
)
from src.ui.views._ui_kit import (
    MAX_COLS,
    assert_signal_text_clean,
    grid,
    render_card_isolated,
    # ~~`render_cards`~~ 🔴 **2026-09-24 整頁卡化後 0 caller，同批移除**
    #    （有意識的清理，⛔ 不是漏刪；`CLAUDE.md §-1.5.F 判定 3(4)`：
    #     因本次改動才變成孤兒的東西，是本次任務的**收尾義務**）。
    #    本頁原本有三處用它畫「無燈號、無 facts」的簡單卡（狀態列 / 三欄摘要 / ⑤⑥），
    #    現在那三處改走 `_render_tiles(_tiles_of_cards(...))` 的 v2 卡面。
    #    ⚠️ **`_ui_kit.render_cards()` 本身一個字都沒動** —— 頁2~頁5 仍在用它。
    render_note,
    section_header,
    single_submit_form,
)
# ── v2 卡面（樣板卡，見下方「v2 卡面」區塊）───────────────────────────
# ⚠️ **`v2_page` ＝ `src/ui_v2/page_today.py`（v2 的版面與狀態契約），⛔ 不是本檔。**
#    兩個檔同名，讀到 `v2_page.` 開頭的一律指對面那一份。
# ⚠️ **為什麼敢放在 module level**（本檔檔頭那條 ⛔「module-level import 失敗 ＝ 整頁空白」
#    仍然完全有效，這裡是逐條對照後的判斷，不是忽略它）：
#    `src/ui_v2/{tokens,components,page_today,markup}.py` 實測**只 import 標準函式庫**
#    （`types` / `typing` / `html`）＋ 彼此，**零第三方**（⛔ 無 streamlit / pandas / plotly）
#    ⇒ 它們的 import 失敗風險與本檔已經接受的 `shared.*` **同一級**，
#    ⛔ 不是 FE-7 消掉的那種「不相干模組連坐」。
#    代價換到的是：下面兩支 `_assert_*` 能在 **import 時**就驗完對映
#    （沿用本檔既有慣例 `_assert_applied_key_matches_reader` /
#     `_assert_every_update_mode_is_mapped`：契約由模組自己在 import 時攜帶並驗證）。
#    ⛔ `src/ui_v2/render.py` **不得**被 import —— 那支才是會拉 streamlit 的渲染層，
#    而本檔要的只有「產字串」的純層（`markup`）。分層：`src.ui_v2` 與本檔同為 **L5**
#    （`tests/test_c3_layering_guard.py` 的 `_MODULE_LAYERS` 明文登記），非跨層上行。
from src.ui_v2 import components as v2_components
from src.ui_v2 import markup as v2_markup
from src.ui_v2 import page_today as v2_page

if TYPE_CHECKING:  # 只為型別標註；執行期在 `_load_lamp_directions()` 內 lazy import
    from src.compute.macro.lamp_direction import LampDirection

# ══════════════════════════════════════════════════════════════════
# session key
# ══════════════════════════════════════════════════════════════════
#: **已套用的更新模式**所在的 session key。
#:
#: ⚠️ 這是一份**刻意的鏡像**：讀取器 `tab_today.applied_update_mode()` 讀的是
#: 該檔的 `_SS_APPLIED`，而那是**私有符號、不得跨層直取**
#: （`CLAUDE.md §8.2.A.2` **V-PICKER-PRIV-1** 的前車之鑑就是跨檔直取底線符號）。
#: 兩害相權：鏡像一個字串、並在 import 時**用讀取器自己驗一次**，
#: 遠好過複寫一支讀取器（那才是真的第二把尺）。
#: 對面改名時本模組會**當場 raise**，不會靜默變成「模式永遠讀不到」。
SS_APPLIED_MODE: str = "_p01_applied"

# ⚠️ **2026-09-08 FE-36 語彙更正（本區塊各行原文一字未改）**：以下若干行寫
#    「與既有 `tab_today` / 舊分頁**同時掛上**時不撞 `DuplicateWidgetID`」。`b5bdb36` 把五頁
#    改成側欄 radio ＋ `st.stop()` 之後，**新頁與舊頁籤不再進到同一個 script
#    run**，「同時掛上 → 同輪撞 ID」這個機制對舊分頁**已不成立**。
#    ✅ **前綴照留，理由換成兩條仍然成立的**：(a) `st.session_state` 跨 rerun、
#    跨頁存活，切一下側欄 radio 就是同 session 的一次 rerun ⇒ 同名 key 照樣
#    互相污染；(b) `st.stop()` 之前跑完的**整個側欄** widget（導覽 radio 自己、
#    連線測試鈕、強制刷新鈕、Sheet ID 輸入框…）**與本頁同輪**，那才是現在真正
#    會撞 ID 的對手。掛載形態由 `tests/test_p0x_view_mount_claims.py` 釘住。
#: 本頁 radio 的 widget key —— **當下值**，下游禁止讀（鐵律 2）。
#: 刻意與 `tab_today` 的 widget key **不同**：兩頁若同時掛上，
#: 相同的 widget key 會直接撞成 Streamlit 的 DuplicateWidgetID。
#: 而**已套用值刻意共用** —— 它們是同一頁的兩種畫法，模式本來就該一致。
SS_MODE_WIDGET: str = "p01v_update_mode_widget"

#: 本頁 form 的 key（同上，與 `tab_today` 的 `form_today` 分開）。
FORM_KEY: str = "form_today_view"

#: **上一次**原地重抓的報告（`macro_refresh_service.MacroRefreshReport`）。
#:
#: 為什麼要存進 session 再 rerun（而不是就地印在按鈕下面）：
#: 這一輪的 16 盞燈是在 submit **之前**就算好的。不 rerun 就會出現
#: 「新報告 ＋ 舊燈號」的畫面，而使用者沒有辦法分辨哪一半是新的（§1）。
SS_REFRESH_REPORT: str = "_p01_refresh_report"


def _assert_applied_key_matches_reader() -> None:
    """import 時就驗：本檔寫的 key，`tab_today.applied_update_mode()` 讀得到嗎？

    §1 Fail Loud。沒有這一道的話，對面把 `_SS_APPLIED` 改名的那天，
    本頁的「已套用模式」會**永遠顯示未選擇**而沒有任何人會發現 ——
    畫面看起來完全正常，只是那顆按鈕從此不再影響任何東西。
    （做法比照 `shared/unified_verdict_thresholds._assert_icon_prefixes_label()`
    的既有慣例：契約由模組自己在 import 時攜帶並驗證。）
    """
    _probe = applied_update_mode({SS_APPLIED_MODE: {"mode": MODE_WARM}})
    if _probe != MODE_WARM:
        raise RuntimeError(
            f"`page_today.SS_APPLIED_MODE`（{SS_APPLIED_MODE!r}）已經不是 "
            "`tab_today.applied_update_mode()` 讀的那個 session key —— "
            "對面很可能改了 `_SS_APPLIED`。請同步本常數，"
            "不要改成自己寫一支讀取器（那會變成第二把尺）。")


_assert_applied_key_matches_reader()

#: 上游（既有總經分頁 / 排程）寫進 session 的 key。**只看存在性，不看內容。**
#:
#: 這就是 `classify_ui_state(requested=)` 的 gate 旗標來源。
#: `shared/ui_state.py` 的鐵律是「`idle` 只能由上游帶下來，禁止由
#: `if not data:` 推導」；**key 存在 = 有人寫過它 = 這份資料被要求過**，
#: 與「這一輪有沒有值」是兩件事（同 `tests/test_ui_state_model.py` 認可的
#: `"_macro_compass_cache" in session_state` 寫法）。
#:
#: 清單＝`services.section_inputs.load_section_inputs()` 讀的那幾個 key。
#: 兩者必須一致：少列一個，就會出現「上游其實寫了、本頁卻判 idle 而不去算」。
#:
#: ⚠️ **2026-09-07 修（稽核實測）：上面那句宣稱原本是假的。**
#: 修前只列 9 個，而 `load_section_inputs` 另讀 `_last_inst` / `cl_ts` /
#: `futures_net` / `_last_inst_date` / `_last_margin` —— **少列 5 個**。
#: 處置是**補齊清單**（而不是把宣稱改弱），理由：那 5 個 key 的寫入端
#: 實測全部是同一個上游 `src/ui/tabs/tab_macro.py`
#: （`_last_inst` / `cl_ts` / `_last_inst_date` / `_last_margin` 四個各有
#: 一處 `st.session_state[...] = ...`；`futures_net` 全 repo **沒有任何
#: session 寫入點**，`load_section_inputs` 對它一律吃 `state.get(..., 0)`
#: 的預設值）。既然來源同一個，補進來不會把別頁的殘留誤判成「總經被叫過」，
#: 而宣稱從此是**逐字為真**的。`futures_net` 沒有寫入點 → 它永遠不會
#: 觸發這個 gate；列出來是為了讓「清單＝loader 讀的 key」這句話真的成立。
UPSTREAM_SESSION_KEYS: tuple[str, ...] = (
    "macro_info", "mkt_info", "warroom_summary", "m1b_m2_info",
    "bias_info", "cl_data", "li_latest", "jingqi_info", "_macro_news_items",
    "_last_inst", "_last_inst_date", "_last_margin", "cl_ts", "futures_net",
)

#: 門檻層警示的 session key（`check_macro_alerts` 的輸出）。
#: `None`（這輪沒跑到）與 `[]`（跑了但 snapshot 全 None）都 falsy，
#: 兩者都**不等於「今天沒事」**（`collect_key_alerts` docstring 明文）。
SESSION_KEY_MACRO_ALERTS: str = "macro_alerts"

# ══════════════════════════════════════════════════════════════════
# 缺值原因：readiness 側車的語彙 → `shared/ui_state` 吃的語彙
# ══════════════════════════════════════════════════════════════════
#: `macro_buckets.MISSING_*` → `station_specs.MISS_*`。
#:
#: 為什麼需要這張表：`classify_ui_state(reason=)` 的升紅判準
#: （`ui_state.FAILED_REASONS`）用的是 `station_specs` 的語彙，
#: 而 readiness 側車寫下的是 `macro_buckets` 的語彙 —— **兩套字面不通用**。
#: 不翻譯就直接餵進去的話，`out_of_range`（量綱漂移，最毒的一種）與
#: `no_extraction`（spec 註冊了卻沒人寫取值 ＝ 程式 bug）**永遠不會升紅**，
#: 會被畫成一般灰態「無資料」而沒有人去修。
#:
#: 對映理由逐條（比的是**處置**，不是字面像不像）：
#:   · `no_extraction` → `contract_drift`：兩者的處置都是「重跑不會好，去改程式」。
#:   · `out_of_range`  → `contract_drift`：`MISS_CONTRACT_DRIFT` 的定義原文就是
#:     「上游給了值，但值不在約定的形態裡」—— 與 DXY→UUP、殖利率×10 完全同構。
#:   · `no_value` / `not_loaded` → `no_input`：都是「這輪沒拿到，重跑可能就好」。
#:   · `not_wired` → `n/a`：實務上到不了這裡（`wired=False` 由 `classify_ui_state`
#:     的第 1 條規則先判成 `unwired`），列出來只是**不留空**。
READINESS_REASON_TO_MISS: dict[str, str] = {
    MISSING_NO_EXTRACTION: MISS_CONTRACT_DRIFT,
    MISSING_OUT_OF_RANGE: MISS_CONTRACT_DRIFT,
    MISSING_NO_VALUE: MISS_NO_INPUT,
    MISSING_NOT_LOADED: MISS_NO_INPUT,
    MISSING_NOT_WIRED: MISS_NOT_APPLICABLE,
}

#: 側車沒有交代缺值原因時的說法。
#:
#: 為什麼不套一個現成的 `MISS_*`：套哪一個都是在**替上游宣稱一件它沒說的事**
#: —— 套 `no_input` 會叫人「重跑一次」，套 `contract_drift` 會叫人去改程式，
#: 兩句都可能是錯的指引（§-2 規則 6 的 `MISS_*` 選錯實證就是這個病）。
#: 立場沿用 L4 `macro_v2_cards.NO_REASON_TEXT`（「上游沒有交代原因（程式要修）」）：
#: **沒有原因這件事本身就是要修的東西**，如實說出來。
UNKNOWN_REASON_WHY: str = (
    "readiness 側車沒有交代缺值原因（`reason` 欄為空、或不在 `MISSING_*` 清單內）"
    "—— **這是程式要修的訊號，不是資料問題**；"
    "在原因補上之前，本頁不替上游猜一個理由")

# ══════════════════════════════════════════════════════════════════
# 文案常數（一句話只准寫一次；指路句一律走 `shared/ia_nav`）
# ══════════════════════════════════════════════════════════════════
#: 本頁的按鈕**碰得到什麼**。
#:
#: ⚠️ **2026-09-09 T3-1：本常數改名 ＋ 改義，是有意識的政策變更，不是漏刪。**
#: 舊名是 `PAGE_READ_ONLY_WHY`，內容是「本頁**只讀** session、**自己不取數**」。
#: 客戶當日裁決「頁1 的按鈕要原地觸發台股今日資料重抓」之後，
#: **那句話變成假的** —— 而一句過期的免責聲明比沒有更糟：
#: 它會叫使用者跑去別的分頁做一件他其實在這裡就能做的事。
#: · **舊寫法的理由仍然成立**（在它寫下的那天）：當時 submit 真的只記模式，
#:   寫成「按一下就會有」才是假指路。
#: · **被權衡掉的是它的前提**，不是它的精神 —— 精神（不承諾交付不出來的結果）
#:   原封不動搬到下面三條分流：**碰得到的才說碰得到**。
PAGE_REFRESH_SCOPE_WHY: str = (
    f"{ia_nav.where_to_press(ia_nav.ACTION_UPDATE_TODAY)}會**在這一頁原地重抓**"
    "台股與總經今日資料（大盤 / 法人 / 融資 / 廣度 / 先行指標 / 6 源總經快照），"
    "抓完直接刷新本頁；**但它碰不到每一格** —— 碰不到的那些，"
    "本頁會在更新報告裡逐條列出來")

# ── 三種「出口」：這一格現在該往哪走 ─────────────────────────────
# ⚠️ **為什麼一定要分三種**（T3-1 的動工條件之一）：
# 舊碼 15 個灰態 / 紅態全部共用同一句 `NO_LOAD_EXIT_WHERE`。按鈕接上取數之後，
# 若把那 15 處**全部**改成「按本頁按鈕」，就會製造一種新的假指路 ——
# **契約漂移（`out_of_range` / `no_extraction`）那幾處按一百次也沒用**，
# 而建議持股 / 市場位階 / 今日關鍵的門檻層**本頁按鈕根本摸不到**。
# 三句話對應三種**處置**，不是三種語氣。

#: (a) 這一格**可以**靠本頁的按鈕重抓 —— 它就是這條路徑會更新的東西。
EXIT_RETRY_HERE: str = (
    f"{PAGE_REFRESH_SCOPE_WHY}。**這一格在它的射程內**：按一次就會重抓這一源。"
    f"連按幾次都一樣灰的話，就是上游真的給不出來 —— 去 "
    f"{ia_nav.where_to_find(ia_nav.SECTION_WHY_DATA_HEALTH)}看根因。"
    "⚠️ 失敗的取數結果會被快取住，**馬上重按多半會拿到同一個失敗**；"
    "要繞過快取請把更新模式切到「強制重抓」")

#: (b) 重抓沒有用 —— 這是**程式**要修的，不是資料問題。
EXIT_FIX_CODE: str = (
    f"{NO_EXIT_MARKER} —— **這一格重抓沒有用**：問題不在「今天有沒有資料」，"
    "而在取值路徑本身（值不在約定的形態裡、或這盞燈根本沒有取值程式）。"
    f"{ia_nav.where_to_press(ia_nav.ACTION_UPDATE_TODAY)}按一百次也一樣。"
    f"要看它到底怎麼了，去 {ia_nav.where_to_find(ia_nav.SECTION_WHY_DATA_HEALTH)}")

#: (c) 本頁按鈕**摸不到**這一格 —— 它的寫入點在別的地方。
EXIT_OUT_OF_REACH: str = (
    f"{NO_EXIT_MARKER} —— **這一格不在本頁按鈕的射程內**："
    "它的資料由舊「🌍 總經」分頁的其他區塊寫進 session，本頁沒有渲染那一段。"
    f"{ia_nav.where_to_press(ia_nav.ACTION_UPDATE_TODAY)}不會讓它離開現在的狀態"
    "（更新報告的「這一輪沒有更新到」會逐條列出它與它的寫入點）")

#: (a)+(c) **複合**：一半可以在本頁重抓、一半摸不到。今日關鍵橫幅專用。
#:
#: 為什麼不硬塞進上面三種其中一種：這張卡的兩半各有各的答案 ——
#: 急變層吃 `macro_info`（本頁按鈕會更新），門檻層吃 `macro_alerts`
#: （本頁摸不到）。說成「可以重抓」會讓人以為按了就會變綠（不會，最多變成
#: 「已列出急變層、門檻層未評估」）；說成「摸不到」又把真的會更新的那一半
#: 也一起否認掉。**兩半都講，才是實話。**
EXIT_ALERTS_PARTIAL: str = (
    f"{ia_nav.where_to_press(ia_nav.ACTION_UPDATE_TODAY)}"
    "**只更新得到這張卡的一半**：急變層要用的總經快照會重抓，"
    "**門檻層掃描本頁摸不到**（它掛在舊「🌍 總經」分頁的中期桶裡）。"
    "也就是說按完之後這張卡最多是「已列出急變層、門檻層未評估」，**不會變綠**。"
    f"要看門檻層到底怎麼了，去 {ia_nav.where_to_find(ia_nav.SECTION_WHY_DATA_HEALTH)}")

#: (d) **已失準**（`discriminative=False`）那一格的指路 —— 不是「沒資料」，是「別照門檻讀」。
#:
#: 🔴 **2026-09-24 從 `build_indicator_tile()` 的 UI_DEGRADED 分支原地上提，字面一字未改。**
#:    **上提的理由（⛔ 不是為了整齊）**：`_v2_exit_phrase()` 以 `is` 比**物件身分**查表，
#:    而寫在函式體裡的那一段含 f-string 插值（`ia_nav.where_to_find(...)`）
#:    ⇒ **每呼叫一次就是一個新物件**，`is` 永遠對不上 ⇒ 那張卡會被畫成**紅卡**。
#:    整頁卡化之前這條路徑不走 v2 卡面，所以不會爆；現在 16 盞燈全走 v2 了。
#:    ⚠️ **這一態在 production 真的走得到**：`margin`（融資餘額）的
#:    `DangerSpec.discriminative` 實測為 `False`（量測日 2026-09-24）——
#:    ⛔ 不是為了「以防萬一」而登記的預防性條目。
EXIT_DEGRADED_READ_DIRECTION: str = (
    "這一態不用你做什麼 —— 別看它有沒有過線，"
    "改看它相對自身近年區間的變化方向；"
    f"門檻本身要不要改屬另案，見 {ia_nav.where_to_find(ia_nav.SECTION_WHY_DATA_HEALTH)}")

#: 16 盞燈裡**本頁按鈕摸不到**的那幾盞（其餘 14 盞都在射程內）。
#:
#: 推導（兩步，各自可查，**不是**在這裡另立一份「燈 → 來源」對照）：
#:   1. L2 `macro_helpers` 的 readiness 取值表寫明 `health` 讀
#:      `warroom_summary.health_score`、`news_systemic` 讀 `_macro_news_items`；
#:   2. L3 `macro_refresh_service.WRITES_SESSION_KEYS` 沒有這兩個 key
#:      （它們的寫入點都在 `src/ui/tabs/**`，本階段不准動）。
#: 第 2 步由 `tests/test_p01_macro_refresh.py::TestOutOfReachLightsAreReallyOutOfReach`
#: 現場比對 —— 哪天這兩個 key 被接進本路徑，那支測試會紅，這裡就得跟著改。
OUT_OF_REACH_LIGHT_KEYS: frozenset[str] = frozenset({"health", "news_systemic"})

#: 五桶裡整桶都摸不到的那一桶（`news` 桶旗下只有 `news_systemic` 一盞燈）。
OUT_OF_REACH_BUCKETS: frozenset[str] = frozenset({"news"})


#: 冷啟動（側車**根本沒有跑**）那一盞燈的「為什麼沒有」。
#:
#: ⚠️ **它與 `UNKNOWN_REASON_WHY` 是兩件不同的事，不得共用**（2026-09-09 修）：
#: 前者是「還沒有人去取」，處置是**按按鈕**；後者是「取了、側車卻沒交代原因」，
#: 處置是**改程式**。修前兩者共用同一段文案，於是**每一次冷啟動**、每一盞燈
#: 都在說「這是程式要修的訊號」—— 叫使用者去修一個不存在的 bug。
#: 用字沿用 `build_bucket_tiles` 冷啟動那一支（同一件事只講一種說法）。
IDLE_LIGHT_WHY: str = (
    "冷啟動 session：上游一個總經 key 都還沒寫進來，本頁因此**連算都沒有算** "
    "—— 這是「還沒叫」，不是「叫了沒回」，也不是「掃過了沒問題」")


def indicator_exit(key: str, rec: Mapping[str, Any] | None = None) -> str:
    """一盞燈的灰態該給哪一種出口。**三選一，順序有意義；紅態另判。**

    1. **摸不到**（`OUT_OF_REACH_LIGHT_KEYS`）→ `EXIT_OUT_OF_REACH`。
       **排第一**：它的寫入點在別的地方，這件事與側車有沒有交代原因無關；
       而且它給的是這一格**唯一可行的下一步**（那份資料要去哪裡才生得出來），
       比一句「這是程式要修的」有用。
    2. **側車跑過了、卻沒交代（或交代了沒登記的）原因** → `EXIT_FIX_CODE`。
       ⚠️ 2026-09-09 ★3：這一格的 `why` 走 `UNKNOWN_REASON_WHY`
       （「這是**程式要修**的訊號，不是資料問題」），修前 `where` 卻走
       `EXIT_RETRY_HERE`（「按一次就會**重抓**這一源」）—— **同一張卡上
       兩句互相打臉**，而且照 `where` 做的人會白按。
       前提是側車**真的跑過**：`_rec` 的 docstring 自陳「恆為 16 筆 ——
       缺席也要有紀錄」，且 `macro_helpers` 末段有 `no_extraction` 掃描
       替沒取值的 spec 補一筆。所以「請求過、卻沒有登記的原因」＝ 程式的洞。
    3. 其餘 → `EXIT_RETRY_HERE`。

    Args:
        key: `DangerSpec.key`。
        rec: 側車那一筆。**`None` ＝ 呼叫端只問「摸得到嗎」** ——
            冷啟動那一支就是這樣叫的：側車根本沒跑，`reason` 為空是**正常的**，
            不該因此判成程式 bug（見 `IDLE_LIGHT_WHY`）。
    """
    if key in OUT_OF_REACH_LIGHT_KEYS:
        return EXIT_OUT_OF_REACH
    if rec is not None and reason_is_unregistered(rec):
        return EXIT_FIX_CODE
    return EXIT_RETRY_HERE


def bucket_exit(bucket: str) -> str:
    """一整桶的灰態該給哪一種出口。"""
    return (EXIT_OUT_OF_REACH if bucket in OUT_OF_REACH_BUCKETS
            else EXIT_RETRY_HERE)


# ══════════════════════════════════════════════════════════════════
# 原地重抓（T3-1，2026-09-09 客戶裁決）的文案與模式對映
# ══════════════════════════════════════════════════════════════════
#: 本頁 radio 的選項 key → L3 `macro_refresh_service` 的模式字串。
#:
#: ⚠️ **為什麼右邊是字面而不是 `import macro_refresh_service.MODE_*`**：
#: 那個 module 會把 `src.compute.macro` 這個 **eager barrel** 一起拉進來
#: （它 module-level import `macro_helpers` ＋ `flow_engine`）——
#: 也就是把檔頭 FE-7 好不容易消掉的「不相干模組 import 失敗 ⇒ 整頁空白」
#: 又接回來。服務本體一律在 `_run_refresh_now()` 裡 late import。
#:
#: ⚠️ **代價講在明處**：右邊兩個字面因此是**第二份定義**，會漂。
#: 兩道守衛把它釘住，缺一不可：
#:   1. CI —— `tests/test_p01_macro_refresh.py::TestModeMappingMatchesTheService`
#:      同時 import 兩邊逐值比對（漂了 CI 就紅，不必等到有人按按鈕）；
#:   2. 執行期 —— `_run_refresh_now()` 拿到服務之後**再驗一次**，
#:      對不上就 `RuntimeError`，**不 fallback 成正常更新**
#:      （fallback 等於替使用者改掉他選的模式）。
UPDATE_MODE_TO_REFRESH_MODE: dict[str, str] = {
    MODE_WARM: "warm",
    MODE_FORCE: "force",
}


def _assert_every_update_mode_is_mapped() -> None:
    """import 時就驗：radio 上的每一個模式都有對應的重抓模式（§1 Fail Loud）。"""
    _missing = [_m for _m in MODE_LABELS if _m not in UPDATE_MODE_TO_REFRESH_MODE]
    if _missing:
        raise RuntimeError(
            f"`tab_today.MODE_LABELS` 多了 {_missing} 這些更新模式，"
            "但 `page_today.UPDATE_MODE_TO_REFRESH_MODE` 沒有對應 —— "
            "按下去會沒有反應。請補對映，**不要**讓它 fallback 成正常更新"
            "（那等於替使用者改掉他選的模式）。")


_assert_every_update_mode_is_mapped()

#: `st.status` 進行中的標題。**刻意不寫秒數上界**（見 `_run_refresh_now`）。
REFRESH_RUNNING_LABEL: str = (
    "🚀 正在原地重抓今日資料 —— 逐個來源列在下面，"
    "**暖快取數秒、冷啟動較久**；每一行出現＝那一源已經有結論")

#: 按鈕下方的速度提示。同上：講體感分級，不講秒數。
REFRESH_SPEED_HINT: str = (
    "暖快取時多半數秒內結束；冷啟動（或選「強制重抓」）會久一些，"
    "**進度會一行一行出現**，沒有停住就是還在跑。"
    "跑完會自動刷新本頁，並在頁首留下這一輪的結果。")

#: 有失敗時該怎麼辦。⛔ **不得寫「請重試」。**
#:
#: 理由（實測，不是保守）：失敗的取數結果會被 `@st.cache_data` 連同失敗一起
#: 快取住一段時間（TTL 由 `shared/ttls.py` 決定）。在那段時間內**馬上重按會
#: 拿到同一個失敗**，於是「請重試」就是一句會讓人白按好幾次的假指路。
#: 真正繞得過快取的動作只有一個：把更新模式切到「強制重抓」。
REFRESH_FAILED_WHAT_NOW: str = (
    "**下一步**：失敗的取數結果會連同失敗一起被快取一段時間，"
    "**馬上再按一次「正常更新」多半會拿到同一個失敗**。"
    "要真的重打上游，請把更新模式切到「強制重抓（清快取）」再送出一次；"
    "還是失敗就是上游真的給不出來 —— "
    f"去 {ia_nav.where_to_find(ia_nav.SECTION_WHY_DATA_HEALTH)}看根因。"
    "⚠️ 沒有更新到的那幾格**現在顯示的是上一輪的值**，不是今天的。")

#: 「這一輪沒有更新到」那一段的標題與說明。
#: ⚠️ 常數自帶 Markdown 粗體，呼叫端**不要再包一層** `**` ——
#: 巢狀的 `**` 會被 Streamlit 解析成「粗體 + 一段普通字 + 粗體」，
#: 畫面上會冒出裸露的星號（本批 AppTest 實測踩過）。
UNTOUCHED_HEADING: str = "**這一輪沒有更新到**（本頁按鈕摸不到的區塊）"
UNTOUCHED_WHY: str = (
    "⚠️ 下面這幾塊**不在本頁按鈕的射程內** —— 它們現在顯示的是"
    "**上一次跑舊「🌍 總經」分頁留下的值**，或根本沒有值。"
    "留白不寫等於讓整頁看起來都是今天的，所以這裡逐條列出來，"
    "連「誰才寫得到它」一起講（清單與寫入點的 SSOT 在 L3 "
    "`services.macro_refresh_service.UNTOUCHED_BLOCKS`，本頁不另抄一份）。")

#: 契約沒有時間欄位這件事（陷阱 1）。**不編一個時間出來。**
AS_OF_NOT_IN_CONTRACT: str = (
    "⏱ **本頁不顯示「資料時間」**：readiness 側車與 L3 總經契約"
    "都沒有逐指標的 `as_of` / `timestamp` 欄位（實測，非推測）。"
    "要顯示真實時間得先擴充 L3 契約 —— 在那之前，"
    "寧可什麼都不寫，也不編一個時間出來（§1）。"
    "側車真的有的是「命中來源」，已逐格顯示。")

#: 五桶 vs 線框七段的涵蓋度（見檔頭）。
SEGMENT_COVERAGE_NOTE: str = (
    "本葉照 16 盞燈**真正的歸屬**分成五桶（長期 / 中期 / 短線急殺 / 籌碼 / 新聞）。"
    "線框寫的七段另含「A 市場狀態」與「G 跨桶裁決」—— "
    "那兩段**沒有對應的燈**，「F 全球風險」也只被其中三盞部分涵蓋。"
    "與其擺三段空殼假裝有結構，不如照實分段並在這裡講明。")

#: 葉1 ③（線框原文的三欄摘要）的說明。**這一格是回到線框，不是偏離它。**
LEAF1_SUMMARY_NOTE: str = (
    "位階 / 動能 / 風險三欄 —— 線框 `PAGES[0]` 葉1 ③ 的原文格式，"
    "直接取用 `tab_today.build_today_blocks()` 的 `today.summary`（**零新增取數**）。"
    "位階已接上 L3 契約；動能**誠實標未接線**，不拿別的東西頂替。")
#: 📌 **2026-09-26 事實更正（有意識的更正，⛔ 不是漏刪）**：上句原為
#: 「~~動能與風險**誠實標未接線**~~」。「風險」格已依客戶 2026-09-16 裁示
#: 「風險 ← danger」接上指標危險度（`build_summary_tiles()`），舊句**在它寫下的當天是對的**，
#: 現在再印就是畫面上的假宣稱（§1）。處置**只刪「與風險」三字**，⛔ 不新增任何字。

#: 五桶摘要搬家的揭露（【5】）。**內容一格都沒刪，只是換位置。**
BUCKET_SUMMARY_MOVED_NOTE: str = (
    "門檻與燈號全部走 `shared/macro_buckets.py`（SSOT）。"
    "⚠️ 這一區 2026-09-07 從**葉1 ③**移到葉2 頁首：葉1 ③ 在線框是"
    "「三欄摘要（位階 / 動能 / 風險）」，先前被這一區換掉且未揭露；"
    "葉2 本來就是五桶明細，這裡才是五桶摘要的歸屬。**內容一格都沒有刪。**")

#: 並列揭露（陷阱 3）的固定說明。兩顆燈**各自算完擺在一起**，不調和。
PARALLEL_DISCLOSURE: str = (
    "⚖️ 下面兩顆燈**不是同一個量，也刻意不合成第三顆**："
    "「指標危險度」問的是 16 盞燈裡有沒有踩到危險門檻（**不含多空方向**）；"
    "「市場位階」問的是多空（看不到 VIX / PMI / CPI / 融資）。"
    "實跑比對兩者燈色不一致約四成、方向相反 18 組 —— "
    "客戶 2026-08-27 裁示並列揭露，**併成一顆會毀掉這個資訊**。")

#: L4 標籤模組載不進來時的說法（邊界 (b)：service / render 模組 import 失敗）。
L4_LABEL_UNAVAILABLE: str = (
    "燈號中文標籤與門檻帶由 L4 `src/ui/render/macro_v2_cards.py` 供給，"
    "本輪載入失敗；**不在這裡另寫一份**（那會是第二把尺）。已保留原始例外："
)

# ══════════════════════════════════════════════════════════════════
# 例外的**出處**（【8b】2026-09-07 修）
# ══════════════════════════════════════════════════════════════════
#: 為什麼需要這一組常數 ＋ `_error_why()`，而不是全部走
#: `tab_today.upstream_error_why()`：那支的文案**寫死**「讀 **L3 canonical
#: 契約**時拋出例外」，因為它在對面那個檔裡只服務一件事（`get_macro_state`）。
#: 本頁卻拿它去包 **L2**（`macro_helpers` / `daily_key_alerts`）與 **L5**
#: （`tab_macro_v2` 的純函式）的例外 —— 那是**對使用者謊報出事的層**：
#: 五桶算錯的時候畫面會叫人去看 L3 契約，而真正壞掉的是 L2。
#:
#: ⚠️ **這不是第二把尺**：洗掉狀態 glyph 的那一步仍然走對面的 SSOT
#: `scrub_state_glyphs()`（唯一入口，`Note.__post_init__` 那道驗證靠它）。
#: 這裡換掉的**只有出處那一句話**。`upstream_error_why()` 在本頁仍然用於
#: 市場位階那一張卡 —— 那一張**真的**是 L3 canonical 契約，文案原本就對。
#: ⛔ 不改 `tab_today.py` 一個字（檔案邊界）。
SRC_ALLOCATION: str = "L3 建議持股服務（`services.allocation_service.get_allocation`）"
SRC_FIVE_BUCKET: str = (
    "L3 `services.section_inputs` → L2 `compute.macro.macro_helpers`（五桶取數）")
SRC_DANGER: str = (
    "L5 `tabs.tab_macro_v2` 的危險度純函式（吃 L2 算好的 readiness 側車）")
SRC_KEY_ALERTS: str = "L2 `compute.macro.daily_key_alerts`（今日關鍵）"
SRC_RENDER: str = "本頁的渲染層（`views/_ui_kit.render_card`）"


def _error_why(source: str, error: Any) -> str:
    """把上游例外轉成一句可以放進 `Note.why` 的話，**出處講對**。

    Args:
        source: 出事的那一層 / 那個模組（本檔的 `SRC_*` 常數之一）。
        error: 例外字串（`repr(e)`）。

    洗 glyph 一律走 `tab_today.scrub_state_glyphs()`（SSOT，唯一入口）——
    `Note.__post_init__` 拒收狀態 glyph，不洗就會把一張該畫出來的紅卡
    變成整頁未捕捉例外（§1：紅態要看得見，不是換一種炸法）。
    """
    _clean, _n = scrub_state_glyphs(error)
    _why = f"{source}拋出例外：{_clean or '（上游沒有給訊息）'}"
    if _n:
        _why += ("（上游訊息裡的狀態符號已移除，"
                 "以免和這張卡自己的狀態燈混成兩個互相矛盾的說法）")
    return _why


# ══════════════════════════════════════════════════════════════════
# 純資料層（零 streamlit；render 端把 session 讀出來再傳進來）
# ══════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class MacroReadout:
    """本頁這一輪從上游讀到的全部東西。**不含任何本檔自算的結論。**

    Attributes:
        requested: 上游有沒有寫過任何一個 `UPSTREAM_SESSION_KEYS`。
            這是 `classify_ui_state(requested=)` 的唯一來源。
        readiness: `compute_five_bucket_summary(readiness_out=)` 的側車，
            **恆 16 筆**；`requested=False` 或取數失敗時為空 dict。
        summary: 五桶 summary（`{bucket: {level,label,headline,color,emoji,details}}`）。
        error: 讀 / 算的過程中拋出的例外，`repr(e)` 原樣保留（§1：紅態要看得見）。
            空字串 = 沒有錯誤。
    """

    requested: bool
    readiness: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    summary: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    error: str = ""


@dataclass(frozen=True)
class Coverage:
    """葉1 / 葉2 頁首的**分母**。線框原文：`0／16 個指標正常運作中`。

    ⚠️ `unwired` 與 `stale` **都在分母裡**（`DangerSpec` 的欄位註解明文：
    `discriminative=False` 不改分母；而 `wired=False` 雖然不進**分子**，
    但線框的灰態原文就是 `0／16 …（無資料 15 · 未接線 1）` —— 16 是總數）。
    把未接線的燈藏起來，等於製造一個永遠 100% 的假可信度。
    """

    total: int
    live: int
    stale: int
    unwired: int
    fault: int
    gray: int

    def text(self) -> str:
        """線框格式的一句話。"""
        return (f"訊號可信度 **{self.live}／{self.total}** 個指標正常運作中"
                f"（無資料 {self.gray} · 已失準 {self.stale} · "
                f"未接線 {self.unwired} · 故障 {self.fault}）")


def upstream_requested(session: Mapping[str, Any]) -> bool:
    """上游有沒有寫過總經輸入？**看 key 的存在性，不看內容。**

    這是 `classify_ui_state(requested=)` 的 gate 旗標。
    `shared/ui_state.py` 的鐵律：`idle` 只能由上游帶下來，
    **禁止**由 `bool(data)` / `not df.empty` 反推 —— 那分不出
    「還沒有人叫」與「叫了但失敗」。
    """
    return any(_k in session for _k in UPSTREAM_SESSION_KEYS)


def contract_attempted(regime: Mapping[str, Any] | None,
                       *, error: Any = None) -> bool:
    """L3 總經契約**這一輪有沒有被叫過**（卡① 的 gate 旗標）。

    Args:
        regime: `get_macro_regime()` 的 dict。
        error: 讀契約 / 讀建議持股時拋出的例外。

    **判定完全轉交 `tab_today.classify_macro_contract()`** ——
    它回 `UI_IDLE` 的充要條件就是「`source == SOURCE_UNLOADED` 且沒有例外」，
    也就是「四條來源都沒有、沒有人算過」。`source` 是**上游自己標的分支
    標記**，不是拿資料的有無反推（`shared/ui_state.py` 的鐵律）。

    ⚠️ **為什麼卡①（建議持股）可以用位階契約的 gate**：
    `services.allocation_service.get_allocation()` 內部呼叫的就是同一支
    `macro_state_locker.get_macro_state()`，它的 `is_loaded` 是從那個 dict
    帶下來的（`build_allocation_decision` 第一行 `_is_loaded =
    bool(_ms.get('is_loaded'))`）。**同一次仲裁的兩個出口，不會一個叫過
    一個沒叫過。**

    ⚠️ **為什麼不直接用 `alloc is not None`**（這就是修掉的那個 bug）：
    `get_allocation()` 的 return 只有 `return _cached` / `return _decision`，
    **永不回 None**，於是那個運算式恆為 True → 卡① 沒有 idle 態。
    """
    return classify_macro_contract(regime, error=error) != UI_IDLE


def load_macro_readout(session: Mapping[str, Any]) -> MacroReadout:
    """走**唯一那條**取數路徑，把五桶 summary 與 readiness 側車讀回來。

    路徑：L3 `load_section_inputs` → L2 `compute_five_bucket_summary`
    （`readiness_out=` 側車）。本函式**不碰 streamlit**、不建快取、
    也不從 `session` 直抽任何指標值（那會是第二條取數路徑）。

    邊界處置（三個都真的走得到，不是理論）：
      (a) **冷啟動 session**：`upstream_requested()` 為 False →
          **連算都不算**，回空側車。所有格子因此是 `idle`（還沒有人叫），
          而不是 `empty`（叫了但沒值）—— 兩者的處置完全不同。
          這同時讓 `classify_ui_state` 那條「沒被叫過卻有值 → ValueError」
          在結構上跑不到。
      (b) **L3 / L2 在「呼叫期」拋例外**（`load_section_inputs` /
          `compute_five_bucket_summary` 自己炸了）→ 進 `except`，
          `repr(e)` 原樣帶回 → 全部格子轉**紅態**並把訊息印在畫面上。
          **不是 `except: pass`** —— 例外被轉成一個看得見的狀態，不是被吞掉。
          ~~⛔ **擋不住的是 module-level 的 import 失敗**：本檔 module level
          經 `tab_today` → `src/ui/tabs/__init__.py`（eager barrel）就已經把
          這兩個模組拉進來了，它們若在 import 階段壞掉，`page_today` 自己
          會先 `ImportError`，**整頁空白**（實測 `n_markdown=0`）。
          下面這個 `try` 只是**同一個模組的第二次 import**（已在
          `sys.modules` 裡），因此它**只保護呼叫期**。~~
          ⚠️ **2026-09-07 事實更正（FE-7），不是漏刪；決策者:AI 總管。**
          `src/ui/tabs/__init__.py` 已改為**延遲載入**，這兩個模組
          **不再**被本檔的 module-level import chain 拉進來
          （實測 `src.*` 由 152 → 6）。因此下面這個 `try` **是它們的第一次
          import**，import 期的失敗現在**真的會被這裡接住**並轉成紅態
          （紅隊實測：改前 `n_markdown=0`＋未捕捉例外，改後 `n_markdown=79`）。
          ⚠️ 但本函式仍**只保護這兩個模組** —— 本檔 module level 真正
          相依的 `tab_today` / `_ui_kit` / `shared.*` 若壞掉，整頁一樣空白。
          完整說明見檔頭「這個檔擋得住什麼、擋不住什麼」。
      (c) **某指標回空 DataFrame / None**：側車自己會記成
          `state="missing"` + `reason`，逐格轉灰或升紅，**不影響其他格**。
    """
    if not upstream_requested(session):
        return MacroReadout(requested=False)
    try:
        from src.compute.macro.macro_helpers import compute_five_bucket_summary
        from src.services.section_inputs import load_section_inputs

        _si = load_section_inputs(dict(session))
        _readiness: dict = {}
        _summary = compute_five_bucket_summary(
            _si.macro_info, _si.mkt_info, _si.warroom_summary,
            _si.m1b_m2_info, _si.bias_info, _si.cl_data,
            _si.li_latest, _si.jingqi_info, _si.news_items,
            readiness_out=_readiness,
        )
        return MacroReadout(requested=True, readiness=_readiness,
                            summary=_summary or {})
    except Exception as _e:  # noqa: BLE001 — 轉成紅態顯示，不吞
        # §1：出聲不吞。畫面會拿到 `repr(e)`，log 也留一份給部署環境。
        print(f"[views/page_today] 五桶取數失敗 → 全頁轉紅態：{_e!r}")
        return MacroReadout(requested=True, error=repr(_e))


def indicator_state(rec: Mapping[str, Any], spec: Any, *, requested: bool,
                    error: str) -> str:
    """一盞燈的七態。**判定完全交給 L0**，本函式只做語彙翻譯。

    Args:
        rec: readiness 側車的一筆。空 dict = 這一輪沒有算（冷啟動 / 取數失敗）。
        spec: 該燈的 `DangerSpec`。**只用來取 `wired` / `discriminative`**。
        requested: 由 `upstream_requested()` 帶下來的 gate 旗標。
        error: 取數階段的例外字串（空字串 = 沒有錯）。

    ⚠️ `requested=` 與 `has_value=` **刻意是兩個不同的運算式**
    （`tests/test_ui_state_model.py` 的 AST 守衛會比對這兩者是否同源）。

    ⚠️ **`wired` / `discriminative` 無條件讀 `spec`，一個字都不讀側車**
    （【3】2026-09-07 修，紅隊實測攻破後）。這兩個旗標是**編寫期的靜態事實**
    （`DangerSpec` 的 frozen 常數），一個 session 內永遠不變。

    修前寫的是 `bool(rec.get("wired", spec.wired))` —— 側車只要有這個欄位就
    **覆寫** L0 SSOT。紅隊只改側車一筆、L0 一個字沒動：
    `rd["foreign_net"].update(wired=True, state="ok", value=100.0, reason=None)`
    → 畫面變成「🟢 運作中 ｜ 綠 ｜ 100億」、coverage `4／16（未接線 0）`，
    **而 `SPECS_BY_KEY["foreign_net"].wired` 仍然是 `False`**。
    一盞決策端刻意沒接的燈，被一筆側車資料變成了「運作中」。

    有人會說「側車本來就是從 `SPECS_BY_KEY` 抄的（`macro_helpers._rec`），
    兩者同源」—— **那正是應該直接讀源頭的理由，不是可以多留一條覆寫路徑的
    理由**（總管 2026-09-07 裁定）。同源 ⇒ 讀側車零收益；多一條路 ⇒
    多一個可以讓 L0 說謊的入口。**收益為零、風險為正，就不要留那條路。**

    ⚠️ 冷啟動時側車是空的：讀 `spec` 讓 `foreign_net`（`wired=False`）
    照樣畫成「未接線」而不是「尚未載入」—— 它**永遠不會載入**，處置完全不同，
    且線框的灰態原文明寫 `0／16 …（無資料 15 · **未接線 1**）`。
    """
    _reason = str(rec.get("reason") or "")
    _has_value = rec.get("state") == "ok" and rec.get("value") is not None
    # ⛔ 這兩個旗標**不得**改回 `rec.get(...)` —— 見上方 docstring 的紅隊實證。
    #    `tests/test_p01_today_view.py::TestSidecarCannotOverrideSSOT` 釘住它。
    return classify_ui_state(
        requested=requested,
        error=error or None,
        has_value=_has_value,
        reason=READINESS_REASON_TO_MISS.get(_reason, ""),
        wired=bool(spec.wired),
        discriminative=bool(spec.discriminative),
    )


def _miss_why(rec: Mapping[str, Any]) -> str:
    """缺值原因 → 給使用者的「為什麼沒有」。文字走 L0 `MISS_TEXT`，本檔不另寫。"""
    _mapped = READINESS_REASON_TO_MISS.get(str(rec.get("reason") or ""), "")
    return MISS_TEXT.get(_mapped, UNKNOWN_REASON_WHY)


def reason_is_unregistered(rec: Mapping[str, Any]) -> bool:
    """側車這一筆**有沒有交代一個本頁認得的缺值原因**。

    ⚠️ **刻意用 `_miss_why(...) == UNKNOWN_REASON_WHY` 判，不另寫一條規則**：
    「要不要說『上游沒交代原因』」與「要給哪一種出口」必須是**同一個判斷**。
    寫成 `reason not in READINESS_REASON_TO_MISS` 看起來一樣，但它漏掉
    「原因有登記、`MISS_TEXT` 卻沒有那一句」的情形 —— 那時 `why` 仍會落到
    `UNKNOWN_REASON_WHY`，而 `where` 會走另一條路。**兩把尺就是本批要修的病。**

    ⚠️ 2026-09-09 獨立 QA 抓到的第三個洞：這種情形的 `why` 走
    `UNKNOWN_REASON_WHY`（「這是**程式要修**的訊號，不是資料問題」），
    `where` 卻走 `EXIT_RETRY_HERE`（「按一次就會**重抓**這一源」）——
    **同一張卡上兩句互相打臉**，而且照 `where` 做的人會白按。
    """
    return _miss_why(rec) == UNKNOWN_REASON_WHY


@dataclass(frozen=True)
class Tile:
    """一張卡 ＋ 它的渲染附件。`Card` 本身不帶燈號與中繼資料欄。

    ⚠️ 為什麼不直接擴 `Card`：`Card` 住在 `tab_today.py`，有
    `tests/test_p01_today_skeleton.py` 守著，**本批不得改它一個字**
    （檔案邊界）。把附件掛在外面是**唯一**不動對面檔案的做法。
    """

    card: Card
    signal_text: str = ""
    signal_color: str = ""
    facts: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        """【7】2026-09-07：**訊號頻道在建構期就驗，不留到渲染期。**

        `_ui_kit.render_card()` 本來就會拒收帶狀態 glyph / 燈號 emoji 的
        `signal_text`（那個 `ValueError` 是刻意的 Fail Loud，**沒有拿掉**）。
        問題出在**時機**：紅隊實測，只要任何一個 SSOT 標籤含 `🔴`，
        `render_page_today()` 會畫到第 27 個 markdown **之後**才炸 →
        **半截死頁**：上半頁已經渲染、下半頁全部消失，畫面上一句解釋都沒有。

        `build_*` 全部產出 `Tile`，所以驗在這裡 ＝ 驗在**任何一個 `st.*`
        被呼叫之前**：要嘛整頁是對的，要嘛在還沒畫任何東西時就當場說明。
        兩邊呼叫的是**同一支** `assert_signal_text_clean()`，不是兩把尺。
        """
        assert_signal_text_clean(f"Tile(card={self.card.key!r})",
                                 self.signal_text)


def build_indicator_tile(key: str, rec: Mapping[str, Any], *,
                         requested: bool, error: str,
                         band_label: Any = None,
                         thr_text: Any = None,
                         l4_error: str = "",
                         direction: LampDirection | None = None,
                         direction_missing: bool = False) -> Tile:
    """一盞燈 → 一張卡。**燈號與門檻全部走 L0 / L4 SSOT，本檔不判燈。**

    Args:
        key: `DangerSpec.key`。
        rec: readiness 側車的那一筆（可能是空 dict）。
        requested / error: 見 `indicator_state`。
        band_label: L4 `macro_v2_cards.band_meta` 或 None（載入失敗）。
        thr_text: L4 `macro_v2_cards.threshold_text` 或 None（載入失敗）。
        l4_error: L4 載入失敗時的 `repr(e)`。
        direction: L2 `lamp_direction.LampDirection` 或 None。None → **不出**
            「變化方向」列（與加這一列之前逐字相同）。只接受
            `LAMP_DIRECTION_KEYS` 內的燈，其餘 → `ValueError`。
            ⚠️ 它**只加一列 fact**，不碰 `_band` / `_state` / 燈號頻道。
            位置：live → 第一列（判決行正下方）；degraded → 緊接「現值」；
            其餘狀態（尚未載入 / 失敗 / 未接線…）→ **不出這一列**。
            `direction.direction == "error"` → 該列顯示「計算失敗（例外型別）」。
        direction_missing: True ＝ caller **有**給 directions mapping、但裡面缺這盞燈
            （2026-09-25）。判為**計算失敗**（不是「無資料」—— 缺 key 是程式沒回傳，
            不是序列不夠），顯示「計算失敗（未回傳）」。⛔ 不讓該列靜默消失。
            只用 L0 常數組字，不需要 L2（L2 載入失敗時也畫得出來）。

    ⚠️ **`classify_danger()` 對沒有門檻的 spec 會 TypeError**（L0 刻意的
    fail loud）。所以一律**先問 `has_thresholds(spec)`** —— 不 guard 的話
    一盞沒門檻的燈就把整頁炸掉。現行 16 盞都有門檻，但那是**現況不是保證**：
    `BUCKET_DANGER_SPECS` 隨時可能加一條參考型的進來。
    """
    _spec = SPECS_BY_KEY[key]
    _state = indicator_state(rec, _spec, requested=requested, error=error)
    _value = rec.get("value")
    _has_thr = has_thresholds(_spec)
    _band = classify_danger(_value, _spec) if _has_thr else "gray"

    # ── 中繼資料列：任何狀態都該看得見「這盞燈本來長什麼樣」──────────
    _facts: list[tuple[str, str]] = []
    if thr_text is not None and _has_thr:
        _facts.append(("門檻帶", thr_text(_spec)))
    elif not _has_thr:
        _facts.append(("門檻帶", "這條線沒有門檻，**不判燈**"))
    else:
        _facts.append(("門檻帶", f"{L4_LABEL_UNAVAILABLE}`{l4_error}`"))
    _facts.append(("命中來源", str(rec.get("hit_source") or "—　本輪未命中任何源")))
    if _spec.source:
        _facts.append(("門檻出處", _spec.source))
    if _spec.note:
        _facts.append(("這條線在看什麼", _spec.note))

    # ── 燈號頻道：**只出中文標籤**（`_ui_kit.render_card` 會擋 emoji）──
    _signal_text, _signal_color = "", ""
    if _state in (UI_LIVE, UI_DEGRADED) and band_label is not None:
        _zh, _hex = band_label(_band, _spec)
        _signal_text, _signal_color = _zh, _hex
    elif _state in (UI_LIVE, UI_DEGRADED):
        _facts.insert(0, ("燈號", f"{L4_LABEL_UNAVAILABLE}`{l4_error}`"))

    _shown = fmt_value(_value, _spec) if _value is not None else ""

    # ── 「變化方向」列（2026-09-24）：只加一列 fact，⛔ 不碰 `_band` / `_state` ──
    _dir_fact: tuple[str, str] | None = None
    if direction is not None or direction_missing:
        if key not in LAMP_DIRECTION_KEYS:
            raise ValueError(f"{key!r} 不在 LAMP_DIRECTION_KEYS，不該帶「變化方向」")
        # 只有 live / degraded（有值）才出這一列。尚未載入 / 失敗 / 未接線等灰紅態
        # 一律不出（v3 §02：「未載入」必須看起來與「有資料」截然不同）。
        if _state in (UI_LIVE, UI_DEGRADED):
            if direction is not None:
                from src.compute.macro.lamp_direction import format_direction_text
                _dir_text = format_direction_text(direction)
            else:
                _dir_text = LAMP_DIRECTION_ERROR_TEMPLATE.format(
                    reason=LAMP_DIRECTION_MISSING_REASON)
            _dir_fact = (LAMP_DIRECTION_FACT_KEY, _dir_text)

    if _state == UI_LIVE:
        if _dir_fact is not None:
            _facts.insert(0, _dir_fact)        # 判決行正下方的第一列
        return Tile(Card(key=f"detail.{key}", label=_spec.label,
                         state=_state, value=_shown),
                    signal_text=_signal_text, signal_color=_signal_color,
                    facts=tuple(_facts))

    # 非 live 一律要三要素。`Card` 規定非 live 不得帶 `value`，
    # 所以**已失準**那一態的現值改掛在 facts（它是有值的，不能藏起來）。
    if _state == UI_DEGRADED:
        _facts.insert(0, ("現值", _shown or "—"))
        if _dir_fact is not None:
            _facts.insert(1, _dir_fact)        # 緊接「現值」
        _note = Note(
            now=f"{_spec.label}　**有值，但門檻已失去判別力**",
            # §1 + 規格：理由直接讀 SSOT，不自己寫一份。
            why=(_spec.degraded_reason
                 or "SSOT 標了 `discriminative=False` 卻沒填 `degraded_reason`"
                    " —— 這是程式要修的訊號"),
            # 🔴 2026-09-24 改引 `EXIT_DEGRADED_READ_DIRECTION`（**字面一字未改**）——
            #    上提的理由見該常數：寫在這裡的話每次呼叫都是新物件，
            #    `_v2_exit_phrase()` 的 `is` 查表永遠對不上 ⇒ 這張卡會被畫成紅卡。
            where=EXIT_DEGRADED_READ_DIRECTION,
        )
    elif _state == UI_UNWIRED:
        _note = Note(
            now=f"{_spec.label}　**這盞燈沒有在運作**（決策端刻意未接線）",
            why=(_spec.unwired_reason
                 or "SSOT 標了 `wired=False` 卻沒填 `unwired_reason`"
                    " —— 這是程式要修的訊號"),
            where=(f"這一態{NO_EXIT_MARKER} —— 這是待接線項，不是你操作的問題；"
                   "它**永遠不會亮**，重按更新一百次也一樣"),
        )
    elif _state == UI_FAILED and error:
        # 出處是**五桶取數**（L3 section_inputs → L2 macro_helpers），
        # 不是 L3 canonical 契約 —— 見【8b】與 `_error_why` 的註解。
        _note = Note(now=f"{_spec.label}　取得失敗",
                     why=_error_why(SRC_FIVE_BUCKET, error),
                     where=EXIT_FIX_CODE)
    elif _state == UI_FAILED:
        # 側車自己判出的紅（量綱漂移 / spec 沒有取值路徑）—— 不是本頁拋的例外。
        _clean, _n = scrub_state_glyphs(_miss_why(rec))
        _why = _clean + ("（原文的狀態符號已移除，"
                         "以免和這張卡自己的狀態燈變成兩個矛盾的說法）" if _n else "")
        _note = Note(now=f"{_spec.label}　**這盞燈壞了，不是沒資料**", why=_why,
                     where=EXIT_FIX_CODE)
    elif _state == UI_IDLE:
        # 冷啟動：側車**根本沒有跑**（`load_macro_readout` 在 `requested=False`
        # 時連算都不算，回空側車）—— 於是 `rec` 是空 dict、`reason` 是空字串。
        # ⚠️ 這一支是 2026-09-09 ★3 一併補的：修前它與下面那一支共用同一段
        # 文案，於是**每一次冷啟動、每一盞燈**都在說「側車沒有交代缺值原因，
        # 這是程式要修的訊號」。冷啟動沒有原因是**正常的**，而且處置正好相反
        # （按鈕就是解法）。只改 `where` 不改這一支的話，冷啟動會變成
        # 「程式要修 ＋ 按一百次也一樣」—— 把最常見的狀態講成故障。
        _note = Note(now=f"{_spec.label}　**尚未載入**（還沒有人去取這份資料）",
                     why=IDLE_LIGHT_WHY, where=indicator_exit(key))
    else:
        _clean, _n = scrub_state_glyphs(_miss_why(rec))
        _why = _clean + ("（原文的狀態符號已移除，"
                         "以免和這張卡自己的狀態燈變成兩個矛盾的說法）" if _n else "")
        # ★3：`why` 說「程式要修」時，`where` 不准說「按一次就會重抓」。
        # **`rec` 一定要傳下去** —— 那是分流判得出這件事的唯一依據
        # （不傳 ＝ 退回修前那條「一律可以重抓」的路）。
        _note = Note(now=f"{_spec.label}　無數值", why=_why,
                     where=indicator_exit(key, rec))
    # 燈號頻道跟著卡走：**`degraded` 是「有值、燈也亮」**，
    # 把它的燈藏起來等於把它降級成灰態，那是另一種說謊。
    # 其餘非 live 的狀態在上面根本沒有取到 `signal_text`（維持空字串）。
    return Tile(Card(key=f"detail.{key}", label=_spec.label, state=_state,
                     note=_note),
                signal_text=_signal_text, signal_color=_signal_color,
                facts=tuple(_facts))


def build_indicator_tiles(readout: MacroReadout, *,
                          band_label: Any = None, thr_text: Any = None,
                          l4_error: str = "",
                          directions: Mapping[str, LampDirection] | None = None,
                          ) -> dict[str, list[Tile]]:
    """16 盞燈 → 依 `BUCKET_ORDER` 分桶的卡片。**分母恆為 16。**

    迭代來源是 L0 `BUCKET_DANGER_SPECS` 而**不是**側車的 key ——
    側車在冷啟動 / 取數失敗時是空的，照它迭代會讓整個葉2 消失，
    而「什麼都不畫」是最糟的一種說謊（線框：未評估 ≠ 沒事）。

    `directions`：`{key: LampDirection}`（2026-09-24「變化方向」列）。
    **只取 `LAMP_DIRECTION_KEYS` 內的 key**，其餘 key 即使出現在 mapping 裡也不傳。
    （2026-09-24 首批 4 盞；2026-09-26 起 `LAMP_DIRECTION_KEYS` ＝ 全部 16 盞，
    沒有歷史的燈顯示「無資料」。未接線 / 尚未載入 / 失敗的卡仍不出這一列。）
    - `directions is None` ⇒ 呼叫端**沒要**這一列 ⇒ 所有卡都不出（與加列前逐字相同）。
    - `directions` 是 mapping 但**缺**某一盞（或該值為 None）⇒ 該卡顯示「計算失敗（未回傳）」
      （2026-09-25；判為計算失敗而非無資料 —— 缺 key 是程式沒回傳結果，不是序列不夠）。
      ⛔ 不讓列靜默消失（空 dict 也一樣：所有 live / degraded 卡都顯示計算失敗）。
    """
    _dirs = directions if directions is not None else {}
    # 缺 key 與「key 在、值是 None」同樣處理 —— 兩者都是沒回傳結果（⛔ 不讓列消失）。
    _missing = ({_k for _k in LAMP_DIRECTION_KEYS if _dirs.get(_k) is None}
                if directions is not None else set())
    if _missing:
        print(f"[views/page_today] 變化方向結果缺 key（顯示計算失敗）：{sorted(_missing)}")
    _out: dict[str, list[Tile]] = {_b: [] for _b in BUCKET_ORDER}
    for _spec in BUCKET_DANGER_SPECS:
        _rec = readout.readiness.get(_spec.key) or {}
        _out.setdefault(_spec.bucket, []).append(
            build_indicator_tile(_spec.key, _rec,
                                 requested=readout.requested,
                                 error=readout.error,
                                 band_label=band_label, thr_text=thr_text,
                                 l4_error=l4_error,
                                 direction=(_dirs.get(_spec.key)
                                            if _spec.key in LAMP_DIRECTION_KEYS
                                            else None),
                                 direction_missing=_spec.key in _missing))
    return _out


def coverage(tiles_by_bucket: Mapping[str, Sequence[Tile]]) -> Coverage:
    """把已經判好態的卡片數成分子 / 分母。**不重判態**（重判就是第二把尺）。"""
    _all = [_t.card.state for _b in BUCKET_ORDER
            for _t in tiles_by_bucket.get(_b, ())]
    _live = sum(1 for _s in _all if _s == UI_LIVE)
    _stale = sum(1 for _s in _all if _s == UI_DEGRADED)
    _unwired = sum(1 for _s in _all if _s == UI_UNWIRED)
    _fault = sum(1 for _s in _all if _s == UI_FAILED)
    return Coverage(total=len(_all), live=_live, stale=_stale,
                    unwired=_unwired, fault=_fault,
                    gray=len(_all) - _live - _stale - _unwired - _fault)


def build_bucket_tiles(readout: MacroReadout) -> tuple[Tile, ...]:
    """**葉2 頁首**的五桶摘要。燈號與短語全部來自 `compute_five_bucket_summary`。

    ⚠️ 2026-09-07 從葉1 ③ 移到這裡（【5】）：線框 `PAGES[0]` 的葉1 ③ 是
    **三欄摘要（位階 / 動能 / 風險）**，那一格已改回線框、直接取用
    `tab_today.build_today_blocks()` 的 `today.summary` block。
    五桶摘要**內容一格都沒刪**，只是搬到它真正的歸屬（葉2 就是五桶明細）。

    本函式**不判燈** —— `level` / `label` / `headline` / `color` 都是上游算好的，
    這裡只決定「這一格該長成哪一態」。
    """
    _tiles: list[Tile] = []
    for _b in BUCKET_ORDER:
        _meta = BUCKET_META[_b]
        _name = f"{_meta['emoji']} {_meta['title']}"
        _sum = readout.summary.get(_b) or {}
        _level = str(_sum.get("level") or "gray")
        _state = classify_ui_state(
            requested=readout.requested,
            error=readout.error or None,
            has_value=(_level in LEVEL_COLOR and _level != "gray"),
        )
        if _state == UI_LIVE:
            _tiles.append(Tile(
                Card(key=f"summary.{_b}", label=_name, state=_state,
                     value=str(_sum.get("headline") or "")),
                # `label` 是 L0 `bucket_level_label()` 的輸出（純中文短語）。
                signal_text=str(_sum.get("label") or ""),
                signal_color=str(_sum.get("color") or LEVEL_COLOR["gray"]),
                facts=(("這一桶在看什麼", str(_meta["sub"])),)))
            continue
        if _state == UI_FAILED:
            _note = Note(now=f"{_name}　這一桶算不出來",
                         why=_error_why(SRC_FIVE_BUCKET, readout.error),
                         where=EXIT_FIX_CODE)
        elif readout.requested:
            _note = Note(
                now=f"{_name}　**全部無資料**",
                why=("這一桶旗下的燈本輪一盞都沒有取到值 —— "
                     "上游 session 裡有容器、但欄位是空的。"
                     "**本站不以缺值推導「中性」**，所以它是灰的不是綠的"),
                where=bucket_exit(_b))
        else:
            _note = Note(
                now=f"{_name}　**尚未載入**（還沒有人去取這份資料）",
                why=("冷啟動 session：上游一個總經 key 都還沒寫進來，"
                     "本頁因此連算都沒有算 —— 這是「還沒叫」，不是「叫了沒回」"),
                where=bucket_exit(_b))
        _tiles.append(Tile(Card(key=f"summary.{_b}", label=_name,
                                state=_state, note=_note),
                           facts=(("這一桶在看什麼", str(_meta["sub"])),)))
    return tuple(_tiles)


def build_key_alert_tile(alerts: Mapping[str, Any] | None, *,
                         requested: bool, threshold_scanned: bool,
                         error: str,
                         band_zh_color: Mapping[str, tuple[str, str]] | None = None,
                         ) -> Tile:
    """葉1 ④ 今日關鍵橫幅。**`items == []` 不等於「今天沒事」。**

    `collect_key_alerts` 的 docstring 明文列了三種都會得到 `items == []` 的情形：
    門檻層沒跑到（`None`）／跑了但 snapshot 全 None（`[]`）／真的評估過且無異常。
    **只有第三種才准顯示綠燈** —— 判別責任在 render 端，也就是這裡。

    做法：把「門檻層有沒有真的掃過」餵給 `discriminative=` ——
    語意完全對得上（**有值、燈也亮，但這條線的判讀不完整**：只涵蓋急變層）。
    這樣就不必自己再寫一套三態判斷。

    ⚠️ **【8c】2026-09-07 修：有紅的那天，紅色要出得來 —— 但出在訊號頻道。**
    線框原文是 `🔴 今日關鍵：3 紅 1 黃`，而修前這張卡的**狀態頻道**恆為
    「🟢 運作中」，紅只藏在 value 的文字裡（`3 紅 · 1 黃`），
    狀態頻道與內容因此不一致。

    **不能**把它改成 `state=failed` 去拿那顆紅：狀態頻道的 `🔴` 在 L0
    `UI_STATE_META` 的語意是**故障**（「這張卡自己壞了」），
    而「今天有 3 個指標踩線」是**訊號紅**（卡片運作完全正常）。
    兩者撞在一起就是本 kit 檔頭鐵律 3 點名的「兩個紅撞在一起」，
    使用者會分不出「今天很危險」與「橫幅抓不到資料」。

    → **正解是本卡本來就有、卻沒被用到的第二個頻道**：`signal_text` ＋
    `signal_color`（`_ui_kit.render_card` 的燈號 chip）。中文標籤與色碼取自
    L4 `BAND_META`（`band_zh_color`），**本檔不自己挑色、不自己寫「紅」字**。
    emoji 不進訊號頻道是 user 2026-08-26 的裁示（同一顆 `🔴` 會撞），
    所以畫面上呈現的是**紅色的「紅」字 chip**，不是 `🔴`。
    """
    _items = list((alerts or {}).get("items") or [])
    _n_red = int((alerts or {}).get("n_red") or 0)
    _n_yellow = int((alerts or {}).get("n_yellow") or 0)
    _state = classify_ui_state(
        requested=requested,
        error=error or None,
        has_value=bool(_items) or threshold_scanned,
        discriminative=threshold_scanned,
    )
    _facts = tuple(
        ("關鍵事項", scrub_state_glyphs(_i.get("text") or "")[0])
        for _i in _items[:MAX_COLS]
    )
    _label = "今日關鍵"
    # 訊號頻道的燈色：紅 > 黃 > 綠（worst-of，與五桶 rollup 同語意）。
    # ⚠️ `_level` 只在「已經評估過」的兩態（live / degraded）用得到；
    #    灰態不給燈 —— **未評估 ≠ 綠**。
    _level = "red" if _n_red else ("yellow" if _n_yellow else "green")
    _sig_zh, _sig_hex = (band_zh_color or {}).get(_level, ("", ""))
    if _state == UI_LIVE:
        _v = (f"{_n_red} 紅 · {_n_yellow} 黃" if _items
              else "門檻層與急變層本輪皆無異常")
        return Tile(Card(key="key_banner.alerts", label=_label,
                         state=_state, value=_v),
                    signal_text=_sig_zh, signal_color=_sig_hex, facts=_facts)
    if _state == UI_FAILED:
        _note = Note(now=f"{_label}　橫幅本身無法產生",
                     why=_error_why(SRC_KEY_ALERTS, error),
                     where=EXIT_FIX_CODE)
    elif _state == UI_DEGRADED:
        _note = Note(
            now=f"{_label}　已列出異常，但**本列僅含急變層**",
            why=("門檻層本輪未評估（`macro_alerts` 為 `None` 或 `[]`）—— "
                 "紅 / 黃條照顯示，但它沒有涵蓋門檻層，"
                 "**不能把它讀成「門檻都沒踩到」**"),
            where=EXIT_ALERTS_PARTIAL)
    elif requested:
        _note = Note(
            now=f"{_label}　**門檻掃描尚未完成** —— **未評估 ≠ 無異常**",
            why=("門檻層這輪沒跑到（`None`），或跑了但 snapshot 全是 `None`（`[]`）"
                 "—— 兩者都不是「沒事」，急變層也沒有東西可比"),
            where=EXIT_ALERTS_PARTIAL)
    else:
        _note = Note(
            now=f"{_label}　尚未載入 —— **未評估 ≠ 無異常**",
            why="冷啟動 session：總經指標一項都還沒寫進來，沒有東西可以掃",
            where=EXIT_ALERTS_PARTIAL)
    # degraded 是「**有值**、燈也亮，只是判讀不完整」 → 燈要照出。
    # 其餘灰態 / 紅態沒有評估結果，燈號頻道一律留白（未評估 ≠ 綠）。
    #
    # ⚠️ **【FIX-2】2026-09-07 稽核提問：degraded 會不會亮出一顆「綠」？**
    # （那會是災難：degraded 下的綠只代表「急變層 0 紅 0 黃」，而門檻層
    #  `threshold_scanned=False` **根本沒掃**，讀起來卻像 all-clear。）
    # **查證結論：在上游契約下不可達 → 本輪不改行為，只把前提釘住。**
    # 推導（三步，每一步都可查）：
    #   1. degraded ⟸ `discriminative=False` ⟸ `threshold_scanned=False`；
    #      而 `has_value=bool(_items) or threshold_scanned` ⇒ 此時
    #      **`_items` 必為非空**（空的話是 `empty` 灰態，走不到這裡）。
    #   2. `_items` 的唯一生產者是 L2 `daily_key_alerts.collect_key_alerts()`
    #      （見 `_load_key_alerts()`，本頁沒有第二個來源）。該函式的兩個
    #      appender **只產 `severity` 0（紅）/ 1（黃）**：`_threshold_items()`
    #      先 `if lvl not in ('red','yellow'): continue`，`_delta_items()`
    #      兩處 append 寫死 0 / 1。**它沒有「綠 item」這種東西。**
    #   3. 同一支函式的 `n_red` / `n_yellow` 是**對 `items` 數出來的**
    #      ⇒ `n_red + n_yellow == len(_items)` ⇒ `_items` 非空 ⇒ 至少一紅或
    #      一黃 ⇒ `_level` 只會是 `red` / `yellow`，**不可能是 `green`**。
    # ⇒ 「degraded + 綠」只有在**呼叫端手捏一個 `collect_key_alerts` 產不出
    #    的 mapping**（有 items 卻 0 紅 0 黃）時才拼得出來 —— 那是稽核組說的
    #    「程式上可達」，不是上游契約可達。
    # ⚠️ 這個結論**建立在第 2、3 步那個前提上**（每個 item 都是紅或黃）。
    #    哪天有人替 `collect_key_alerts` 加一種「綠 / 提示」item，前提就破了，
    #    這裡就會真的亮出誤導性的綠燈 →
    #    `tests/test_p01_today_view.py::TestDegradedGreenIsUnreachableUpstream`
    #    **會當場轉紅**，逼下一個人回來改這一段（而不是靜靜地錯下去）。
    _sig = (_sig_zh, _sig_hex) if _state == UI_DEGRADED else ("", "")
    return Tile(Card(key="key_banner.alerts", label=_label, state=_state,
                     note=_note),
                signal_text=_sig[0], signal_color=_sig[1], facts=_facts)


#: 位階卡的標題。**刻意不再宣稱本卡是本站位階的唯一出處**（2026-09-07
#: FIX-4）—— 那是一句要窮舉全 repo 才成立的全稱句，而獨立稽核當天實測
#: 它是**假的**（點名的四處平行判讀見 `REGIME_SCOPE_NOTE`）。
#: 現行寫法是**單點可驗**的：
#: 這張卡的值取自哪一個契約，讀一行 code 就能驗，不必相信任何全稱宣稱。
#: 三個分支（live / degraded / 其餘）共用這一個常數 —— 標題只准定義一次，
#: 不然改了一處、另外兩處還在對使用者說舊話。
REGIME_CARD_LABEL: str = "市場位階（總經契約）"

#: 位階卡的誠實揭露（掛 `facts`，**每一態都出**）。
#:
#: 2026-09-07 獨立稽核實測：本卡原標題那句「唯一出處」的宣稱是**假的**。
#: canonical 確實是 L3 `macro_state_locker.get_macro_state()`（仲裁邏輯在
#: L0 `shared/regime_arbiter.arbitrate_regime()`），但**全站另有未經這個
#: 仲裁的平行判讀，而且都是活線**：
#:   · `src/ui/tabs/macro/section_cross_ai.py` 的「① 目前總經位階」
#:     （自己用 OECD CLI / PMI × 台灣出口 YoY 判 6 態，**與本卡正面撞名**）
#:     與「⑤ 結論」（自建 `_bull_score` / `_bear_score` 投票 → 整體偏多 /
#:     偏空 / 溫和偏多 / 中性觀望）
#:   · `src/compute/macro/macro_helpers.classify_long_term_regime()`
#:     （docstring 自稱「長期總經位階判讀」，4 態，接到「雙速合議」）
#:   · `src/ui/tabs/macro/section_news_ai.py` 直讀
#:     `macro_state.json['market_regime']` 印成「市場體制」（繞過來源優先序）
#: 那四處住在**舊版分頁**，客戶明令本批不得修改 → 能改的只有**本頁的宣稱**。
#: ⚠️ 本揭露點名的四處**本身也是一種宣稱** —— 一份假的「未納管清單」跟
#: 一句假的唯一性宣稱一樣糟，所以它由 `tests/test_p01_today_view.py::
#: TestNoGlobalUniquenessClaim` **反向釘住**（哪天真的被收斂掉 → 轉紅，
#: 回來改這段文案，而不是留一份過期的點名）。
REGIME_SCOPE_NOTE: str = (
    "本頁一律取自 L3 總經契約 `get_macro_state()`"
    "（仲裁在 L0 `regime_arbiter.arbitrate_regime()`）。"
    "舊版「🌍 市場環境」分頁另有**未經這個仲裁**的平行判讀"
    "（「① 目前總經位階」/「⑤ 結論」的多空計分 / 雙速合議的長期位階），"
    "新聞頁另有直讀 `macro_state.json` 快照印出的「市場體制」。"
    "**兩邊不一致是預期的；本頁以這張卡為準。**"
)

#: 上面那段揭露掛在 `facts` 時用的**標籤**。⛔ 不在各處各寫一份字面。
#:
#: 🔴 **為什麼非得是一個常數**：`V2_HOVER_ONLY_FACTS`（見下方 v2 卡面段）要拿它
#: **比對**才知道哪一列該移出卡面。兩邊各寫一份 `"位階的出處"` 的話，
#: 改了一處就**默默**失配 —— 那一列會悄悄回到卡面（或悄悄兩邊都不見），
#: 而畫面**看起來仍然正常**，⛔ 沒有人會發現（`CLAUDE.md §1` 靜默失效）。
REGIME_SCOPE_FACT_KEY: str = "位階的出處"


def _danger_tile(*, key: str, label: str,
                 danger: tuple[str, str] | None, danger_error: str,
                 danger_requested: bool, danger_source: str,
                 band_zh_color: Mapping[str, tuple[str, str]] | None,
                 l4_error: str) -> Tile:
    """指標危險度（16 盞燈 worst-of，**不含多空方向**）的一張卡。

    📌 **2026-09-26 抽出**：原本寫死在 `build_verdict_tiles()` 卡② 裡；
    葉1 ③ 三欄摘要的「風險」格依客戶 2026-09-16 裁示
    「**風險 ← danger（對得上，直接對映）**」（`UI_PAGE_TODAY.md` ③；
    契約 `src/ui_v2/page_today.py::SUMMARY_COLUMNS`「風險」列
    `source="verdict.danger"`）要吃**同一份**讀數，所以抽成一支 ——
    **⛔ 不複寫第二份文案**（兩份會漂開，§2.1）。
    `key` / `label` 由呼叫端給：卡② 照舊、「風險」格沿用 `tab_today` 那一格
    自己的 key 與標題（⛔ 不新造標題字串）。
    判態、三要素文案、出口，**逐字就是卡② 原本那一段**。
    """
    _band = danger[0] if danger is not None else "gray"
    _danger_state = classify_ui_state(
        requested=(bool(danger_error) or danger_requested),
        error=danger_error or None,
        has_value=(danger is not None and _band != "gray"),
    )
    if _danger_state == UI_LIVE:
        _zh, _hex = (band_zh_color or {}).get(_band, ("", ""))
        _dfacts: tuple[tuple[str, str], ...] = ()
        if not _zh:
            # L4 載不進來 → 誠實留白 ＋ 就地說明，不自己編一組中文與色碼。
            _dfacts = (("燈號", f"{L4_LABEL_UNAVAILABLE}`{l4_error}`"),)
        return Tile(
            Card(key=key, label=label,
                 state=_danger_state, value=str(danger[1])),
            signal_text=_zh, signal_color=_hex, facts=_dfacts)
    if danger_error:
        _why = _error_why(danger_source, danger_error)
    elif _danger_state == UI_IDLE:
        _why = ("上游一個總經 session key 都還沒寫進來，"
                "本頁因此**連 16 盞燈都沒有算** —— "
                "這是「還沒叫」，不是「叫了沒回」，"
                "更**不是**「掃過了沒有指標踩線」")
    else:
        # 只有真的算過、而且 16 盞全灰時才准講這句話（修前不管有沒有算
        # 過都印它，那就是在畫面上宣稱一個沒發生過的計算 —— §1 造假）。
        _why = ("16 盞燈本輪一盞都沒有落在綠 / 黃 / 紅 —— 也就是沒有資料可彙總。"
                "**灰不是綠**：它的意思是「沒得判斷」，不是「沒有指標踩線」")
    return Tile(Card(
        key=key, label=label,
        state=_danger_state,
        note=Note(now="**指標危險度：尚未載入**", why=_why,
                  where=(EXIT_FIX_CODE if danger_error
                         else EXIT_RETRY_HERE))))


def build_verdict_tiles(*, alloc: Any, alloc_error: str,
                        danger: tuple[str, str] | None, danger_error: str,
                        danger_requested: bool,
                        danger_source: str = SRC_DANGER,
                        regime: Mapping[str, Any] | None,
                        regime_error: str,
                        band_zh_color: Mapping[str, tuple[str, str]] | None = None,
                        l4_error: str = "") -> tuple[Tile, ...]:
    """葉1 ① 今日結論 —— **三張並排的卡，沒有第四張「合成結論」**。

    Args:
        alloc / alloc_error: `_load_allocation()` 的兩個回傳。
        danger / danger_error / danger_requested / danger_source:
            `_load_danger()` 的三個回傳 ＋ 五桶的 gate 旗標。
            `danger` 是 `overall_verdict()` 的 `(band, detail)`，**不含方向**。
        regime / regime_error: `_load_regime()` 的兩個回傳（市場位階契約）。
        band_zh_color: L4 `macro_v2_cards.BAND_META`（band → 中文 + 色碼）。
            `None` = L4 載不進來 → 燈號頻道誠實留白並就地說明，
            **不在這裡另寫一份「綠 / 黃 / 紅」對照表**（那才是第二把尺）。
        l4_error: L4 載入失敗時的 `repr(e)`。

    ⚠️ **【1】2026-09-07 修：三張卡的取數與失敗完全獨立。**
    修前 `_load_parallel()` 開頭是 `if regime is None: return None, ""` ——
    危險度那一半（16 盞燈的 worst-of）**完全不依賴 regime**，卻被 regime
    的失敗連坐，而且畫面上還印出「16 盞燈本輪一盞都沒有落在綠 / 黃 / 紅」
    這種**這一輪根本沒發生過的計算**的結論（§1 造假）。反方向同樣壞：
    位階明明 live，只因危險度那半組不出來就被畫成「尚未評估」。
    → 現行：**誰失敗只影響誰那一張卡。**

    ⚠️ 陷阱 3：**不平均、不取 worst、不合成一顆燈**，畫面上也不比對兩者
    （要比對的話，比較邏輯住在 `tab_macro_v2.parallel_verdict()`）。
    ⚠️ 陷阱 2：`regime` 一律用契約回來的原值，**不再套 `normalize_regime()`**
    （它不認得 `'unknown'`，會把「未評估」洗成「震盪」）。
    """
    _tiles: list[Tile] = []
    # 位階契約的態先判一次：卡③ 用它，卡① 的 gate 旗標也從它衍生
    # （`get_allocation()` 的 `is_loaded` 就是同一次 `get_macro_state()`
    #  帶下來的 —— 同一次仲裁的兩個出口，不會一個叫過一個沒叫過）。
    _regime_state = classify_macro_contract(regime, error=regime_error or None)

    # ① 能不能出手 / 出手到幾成 —— **本頁一律取自** L3 `get_allocation()`。
    #    （2026-09-07 FIX-4：原文宣稱這是本站的唯一出處，改成單點可驗的
    #     說法 ——「整個 repo 只有這一處」要窮舉才成立，本組沒有驗過它，
    #     依 §-2 規則 6 就不寫；「本頁取自哪裡」讀一行 code 就能驗。）
    #    本檔**不寫任何水位數字**，一律取 `range_text` / `posture`（動態）。
    #    ⚠️ `requested=` **不得**寫成 `alloc is not None`（恆真式，見
    #    `contract_attempted()` 的 docstring）。
    _alloc_state = classify_ui_state(
        requested=(bool(alloc_error)
                   or contract_attempted(regime, error=regime_error or None)),
        error=alloc_error or None,
        has_value=bool(getattr(alloc, "is_loaded", False)),
    )
    if _alloc_state == UI_LIVE:
        _drv = "；".join(getattr(alloc, "drivers", ()) or ()) or "—"
        _facts = [("推導依據", _drv), ("姿態", str(alloc.posture))]
        if alloc.cap_text:
            _facts.append(("硬否決天花板", alloc.cap_text))
        if alloc.conflicts:
            # 「與結論相反但被壓制的訊號**要顯示，不要藏**」（SSOT docstring 原文）。
            _facts.append(("被壓制的反向訊號", "；".join(alloc.conflicts)))
        _tiles.append(Tile(
            Card(key="verdict.exposure", label="能不能出手 · 出手到幾成",
                 state=_alloc_state, value=alloc.range_text),
            signal_text=str(alloc.posture), facts=tuple(_facts)))
    else:
        if alloc_error:
            _why = _error_why(SRC_ALLOCATION, alloc_error)
        elif _alloc_state == UI_IDLE:
            _why = ("L3 總經契約這一輪**還沒有人叫過**（`source` 仍是 "
                    "`unloaded`：四條來源一條都沒寫進來）—— "
                    "這是「還沒叫」，不是「叫了沒回」，更不是「今天不能出手」")
        else:
            _why = ("L3 建議持股契約回報未評估（`is_loaded=False`）—— "
                    "總經健康分與規則引擎快照兩條來源本輪都沒有值；"
                    "**本站不以缺值推導一個安全水位**")
        _tiles.append(Tile(Card(
            key="verdict.exposure", label="能不能出手 · 出手到幾成",
            state=_alloc_state,
            note=Note(now="**今天能不能出手：尚未評估**", why=_why,
                      where=(EXIT_FIX_CODE if alloc_error
                             else EXIT_OUT_OF_REACH)))))

    # ② 指標危險度（16 盞燈的 worst-of，**不含多空方向**）。
    #    ⚠️ 這一張**完全不看 regime**；regime 掛掉時它照樣要算得出來。
    #    📌 2026-09-26：本段原樣抽成 `_danger_tile()`（葉1 ③「風險」格共用同一支，
    #    ⛔ 不複寫第二份文案）；本卡的 key / 標題照舊，輸出逐 byte 不變。
    _tiles.append(_danger_tile(
        key="verdict.danger", label="指標危險度（不含多空方向）",
        danger=danger, danger_error=danger_error,
        danger_requested=danger_requested, danger_source=danger_source,
        band_zh_color=band_zh_color, l4_error=l4_error))

    # ③ 市場位階 —— 本頁取自 L3 契約（見 `REGIME_CARD_LABEL` /
    #    `REGIME_SCOPE_NOTE`：原標題的唯一性宣稱實測為假，已改）。
    #    狀態沿用 `tab_today.classify_macro_contract()` —— 那支函式讀的是契約
    #    自己的 `source` 分支標記（上游帶下來的旗標），不是拿資料反推。
    #    ⚠️ 這一張**完全不看 16 盞燈**（修前寫 `and parallel is not None`，
    #       危險度那半組不出來就會把一個 live 的位階畫成「尚未評估」）。
    _reg = dict(regime or {})
    # `REGIME_LABEL` 是 L0 SSOT（`parallel_verdict()` 讀的也是這一份）。
    # **本檔不另立一份 regime→中文對照**（§2.1 SSOT）。
    _rk = str(_reg.get("regime") or "unknown").strip().lower()
    _rlabel = REGIME_LABEL.get(_rk, REGIME_LABEL["unknown"])
    _rsource = str(_reg.get("source") or "—")
    if _regime_state == UI_LIVE:
        # live ⇒ `is_loaded=True`，所以這裡不可能對一個未評估的契約印出方向
        # （`get_macro_state` 實測：`source == 'unloaded'` ⟺ `is_loaded=False`）。
        _tiles.append(Tile(
            Card(key="verdict.regime", label=REGIME_CARD_LABEL,
                 state=_regime_state, value=_rlabel),
            signal_text=_rlabel,
            facts=(("生效分支", _rsource),
                   (REGIME_SCOPE_FACT_KEY, REGIME_SCOPE_NOTE))))
    elif _regime_state == UI_DEGRADED:
        # ⚠️ **【FIX-1】2026-09-07：degraded 修前掉進下面那個 `else`。**
        # 修前的判斷是 `if _regime_state == UI_LIVE: ... else: ...` ——
        # **所有非 live 的狀態（含 `UI_DEGRADED`）都走 else**，於是對一個
        # `is_loaded=True`、**有值**的契約印出「市場位階：尚未評估」＋
        # 「L3 canonical 契約四條來源本輪皆無值」。**那是假敘述**：
        # degraded 的前提就是有值 —— L0 `shared/station_specs.py:139`
        # 「`discriminative=False` → 燈會亮、也有等級，只是門檻已失去判別力」、
        # 同檔 `:527`「degraded（**有值、燈照亮**，只是別照門檻讀）」。
        # （實測可達：`macro_state_locker.get_macro_state()` 走 `_file_ok`
        #  分支時 `source=SOURCE_FILE_RULE_ENGINE` ⇒ `discriminative=False`，
        #  而同一個分支 `_is_loaded=True`、`regime` 是真的位階值。）
        #
        # **位階本身照印**：它是「這個值落在哪一段」的**觀測**，不是 pass/fail
        # 的**判決**；留白會把使用者本來看得到的東西藏起來。免責聲明由狀態
        # 頻道的「🟠 門檻已失準」chip ＋ 下面的三要素負責。
        #
        # ⚠️ 文案**不自己另寫一份**：`tab_today.build_status_bar_card()` 對
        # **同一個契約的同一個狀態**已經有經過推敲的說法（快照 / 時間不明 /
        # 不編一個時間），這裡直接取用**它產出的 `Note`** —— 同一支純函式、
        # 同一組輸入 ⇒ 同一段話，不是一份會漂開的複本（§2.1 SSOT）。
        # 兩處的態一定一致：`error` 在 `classify_ui_state` 的順序（4）排在
        # `discriminative`（6）之前 ⇒ 走到這裡就代表 `regime_error` 是空的，
        # 對面拿同樣的輸入只會得到同一個 `UI_DEGRADED`。
        # `Card.__post_init__` 保證非 live 必附 `Note`；真的取不到就讓
        # `Card(...)` 當場 fail loud，**不吞**（§1）。
        _tiles.append(Tile(
            Card(key="verdict.regime", label=REGIME_CARD_LABEL,
                 state=_regime_state,
                 note=build_status_bar_card(regime,
                                            error=regime_error or None).note),
            # 非 live 不得帶 `value`（`Card.__post_init__`）→ 現值改掛 facts，
            # 與 `build_indicator_tile()` 的 degraded 同一個走法（那裡也是
            # `_facts.insert(0, ("現值", ...))`），不是第二種做法。
            signal_text=_rlabel,
            facts=(("現值", _rlabel), ("生效分支", _rsource),
                   (REGIME_SCOPE_FACT_KEY, REGIME_SCOPE_NOTE))))
    else:
        _tiles.append(Tile(Card(
            key="verdict.regime", label=REGIME_CARD_LABEL,
            state=_regime_state,
            note=Note(
                now="**市場位階：尚未評估**",
                # 這一張**真的**是 L3 canonical 契約 → 文案原本就對，
                # 續用對面的 SSOT `upstream_error_why()`（見 `_error_why` 註）。
                why=(upstream_error_why(regime_error) if regime_error else
                     "L3 canonical 契約四條來源本輪皆無值 → 回 `unknown`，"
                     "**不是** `neutral`；本站不以缺值推導「中性」"),
                where=(EXIT_OUT_OF_REACH if not regime_error
                       else EXIT_FIX_CODE))),
            facts=((REGIME_SCOPE_FACT_KEY, REGIME_SCOPE_NOTE),)))
    return tuple(_tiles)


# ══════════════════════════════════════════════════════════════════
# 上游取用（薄殼；每一支都把例外轉成「看得見的紅態」而不是吞掉）
# ══════════════════════════════════════════════════════════════════
def _load_l4_labels() -> tuple[Any, Any, Any, str]:
    """L4 的燈號標籤與門檻帶文字。回 `(band_meta, threshold_text, BAND_META, err)`。

    第三個回傳是 L4 的 `BAND_META`（band → `(中文, 色碼)`）—— 結論卡②
    與今日關鍵橫幅的燈號 chip 用它。`tab_macro_v2.parallel_verdict()` 內部
    讀的也是同一份（`zh, color = BAND_META[band]`），所以**不是第二把尺**。

    為什麼要 lazy 且容錯：這兩支住在 `src/ui/render/macro_v2_cards.py`，
    該模組 module-level `import plotly`。plotly 是本站的實依賴，正常環境不會缺；
    真的缺了的時候，**正確的行為是那兩個欄位誠實說「載不進來」**，
    而不是 (a) 整頁崩、或 (b) 在這裡另寫一份 `綠 / 黃 / 紅` 的對照表
    —— (b) 才是真正的災難：畫面上從此有兩把尺。
    """
    try:
        from src.ui.render.macro_v2_cards import (
            BAND_META, band_meta, threshold_text,
        )
        return band_meta, threshold_text, BAND_META, ""
    except Exception as _e:  # noqa: BLE001 — 轉成可見的說明，不吞
        print(f"[views/page_today] L4 標籤模組載入失敗：{_e!r}")
        return None, None, None, repr(_e)


#: 「變化方向」各支 L3 loader 負責哪幾盞燈的序列（loader 失敗 ⇒ 只有這幾盞顯示計算失敗）。
#: m1b_m2_gap 刻意不在任何一支底下（歷史檔已知損壞，恆為無資料，不讀 L3）。
_LAMP_DIRECTION_LOADERS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("get_chart_series", ("margin", "bias_240")),     # 交易日
    ("get_monthly_history", ("ism_pmi",)),            # 月
)

def _session_vix_series(si: Any) -> list | None:
    """vix 的方向序列，取自 `SectionInputs.macro_info['vix']`（與燈值同一次抓取）。

    **與燈值同源**（見 `macro_helpers.compute_five_bucket_summary` 的 values dict）：
    `dates` / `values` 與燈值 `current` 住在同一個 dict。兩條長度不一、或末值 ≠ `current`
    ⇒ 回 None（印 log；L2 回無資料）—— ⛔ 不截斷湊長度、⛔ 不拿別次抓取的序列配這一次的燈值。
    值本身壞掉（`float()` 失敗）⇒ **丟例外**，由 caller 判為**這一盞**計算失敗（⛔ 不補值）。
    """
    _vix = si.macro_info.get("vix") if isinstance(si.macro_info, Mapping) else None
    if not isinstance(_vix, Mapping):
        return None
    _ds, _vs = _vix.get("dates"), _vix.get("values")
    if not (_ds and _vs):
        return None
    _cur = _vix.get("current")
    if len(_ds) != len(_vs):
        print(f"[views/page_today] 變化方向 vix：dates {len(_ds)} 筆 ≠ values "
              f"{len(_vs)} 筆 → 不給序列（顯示無資料）")
        return None
    if _cur is None or not math.isclose(float(_vs[-1]), float(_cur),
                                        rel_tol=1e-9, abs_tol=1e-9):
        print(f"[views/page_today] 變化方向 vix：序列末值 {_vs[-1]!r} ≠ 燈值 "
              f"{_cur!r} → 不給序列（顯示無資料，不混抓取批次）")
        return None
    return [(str(_d)[:10], _v) for _d, _v in zip(_ds, _vs)]


#: 2026-09-26：序列來自**本輪 session**（經 L3 `load_section_inputs`，與燈值同一條取數路徑、
#: 同一次抓取）的燈 → 各自的抽取函式。**每盞各自 try**：一盞的值壞掉只讓那一盞計算失敗。
#: （adl 刻意不在這裡：單日估算無自相關，恆為無資料 —— 見 L0 檔頭。）
_SESSION_DIRECTION_EXTRACTORS: tuple[tuple[str, Any], ...] = (
    ("vix", _session_vix_series),
)
_LAMP_DIRECTION_SESSION_KEYS: tuple[str, ...] = tuple(
    _k for _k, _ in _SESSION_DIRECTION_EXTRACTORS)


def _session_direction_series(
        session: Mapping[str, Any] | None) -> tuple[dict[str, list], dict[str, str]]:
    """回 `(series, failed)`：`series` ＝ `{key: [(iso_date, value), ...]}`；
    `failed` ＝ `{key: 例外型別名}`（**只有**抽取丟例外的那幾盞）。

    取不到的 key 不放進 `series`（§1：不放空序列冒充有資料）。session 為 None ⇒ `({}, {})`。
    `load_section_inputs` 本身丟例外 ⇒ 往上拋（caller 判所有 session 燈計算失敗）。
    取數只經 L3 `load_section_inputs`（本檔唯一的 session 取數路徑），⛔ 不直抽 session。
    """
    if session is None:
        return {}, {}
    from src.services.section_inputs import load_section_inputs

    _si = load_section_inputs(dict(session))
    _out: dict[str, list] = {}
    _failed: dict[str, str] = {}
    for _k, _fn in _SESSION_DIRECTION_EXTRACTORS:
        try:
            _pts = _fn(_si)
        except Exception as _e:  # noqa: BLE001 — 只影響這一盞；⛔ 不補值
            print(f"[views/page_today] 變化方向計算失敗（session 序列 {_k}）：{_e!r}")
            _failed[_k] = type(_e).__name__
            continue
        if _pts:
            _out[_k] = _pts
    return _out, _failed


def _load_lamp_directions(session: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """燈卡「變化方向」列：L3 取歷史 → L2 算方向。回 `{key: LampDirection}`。

    只算 `LAMP_DIRECTION_KEYS` 那幾盞。某一條序列取不到 ⇒ L2 回 `nodata`
    （畫面顯示「無資料」），⛔ 不整列消失、⛔ 不編箭頭。

    §1 Fail Loud（2026-09-25 修；修前是 `except` → `return {}` ⇒ 列**靜默消失**）：
    - 某支 L3 loader 丟例外 ⇒ 印 log，**只有序列來自那支 loader 的燈**回 `error`
      （`_LAMP_DIRECTION_LOADERS`：`get_chart_series` → margin / bias_240；
      `get_monthly_history` → ism_pmi）。⛔ 不能把它們降成「無資料」冒充序列不夠。
      m1b_m2_gap 不讀任何 L3（設計上恆為無資料），故不受 L3 失敗影響；
    - 單一盞的 L2 計算丟例外 ⇒ 印 log，**只有那一盞**回 `error`，其餘照常。
    - L2 模組本身載入失敗 ⇒ 做不出 `LampDirection`，印 log 回 `{}`；
      `build_indicator_tiles` 對缺 key 一律顯示「計算失敗（未回傳）」（只用 L0 常數）。
    - 2026-09-26：`session` → `_session_direction_series()`（vix）。L3 讀 session 丟例外
      ⇒ 印 log，**只有** `_LAMP_DIRECTION_SESSION_KEYS` 回 `error`；單一盞的值壞掉
      ⇒ **只有那一盞** `error`。`session=None` ⇒ 沒有序列 ⇒ 無資料（L2 nodata）。
    畫面顯示「計算失敗（例外型別）」；**燈號與其他列不受影響**（它不參與判燈）。
    """
    try:
        from src.compute.macro.lamp_direction import (
            compute_lamp_direction,
            error_direction,
        )
    except Exception as _e:  # noqa: BLE001 — 轉成 log；缺 key 由 build 端顯示計算失敗
        print(f"[views/page_today] 變化方向計算失敗（L2 載入失敗）：{_e!r}")
        return {}
    _hist: dict[str, Any] = {}
    _failed: dict[str, str] = {}                     # key → 例外型別名
    try:
        from src.services import macro_v2_service as _svc
    except Exception as _e:  # noqa: BLE001 — L3 載入失敗 ⇒ 所有「有 loader」的燈都失敗
        print(f"[views/page_today] 變化方向計算失敗（L3 載入）：{_e!r}")
        _svc = None
        for _name, _keys in _LAMP_DIRECTION_LOADERS:
            _failed.update({_k: type(_e).__name__ for _k in _keys})
    if _svc is not None:
        for _name, _keys in _LAMP_DIRECTION_LOADERS:
            try:
                _hist.update(getattr(_svc, _name)() or {})
            except Exception as _e:  # noqa: BLE001 — 只影響這支 loader 負責的燈
                print(f"[views/page_today] 變化方向計算失敗（取數 {_name}）：{_e!r}")
                _failed.update({_k: type(_e).__name__ for _k in _keys})
    try:
        _s_hist, _s_failed = _session_direction_series(session)
        _hist.update(_s_hist)
        _failed.update(_s_failed)
    except Exception as _e:  # noqa: BLE001 — L3 讀 session 失敗 ⇒ 只影響序列來自 session 的燈
        print(f"[views/page_today] 變化方向計算失敗（session 序列）：{_e!r}")
        _failed.update({_k: type(_e).__name__ for _k in _LAMP_DIRECTION_SESSION_KEYS})
    # ⚠️ m1b_m2_gap 與其餘 mode = "none" 的燈刻意不給序列：L2 恆回 nodata。
    _out: dict[str, Any] = {}
    for _k in LAMP_DIRECTION_KEYS:
        if _k in _failed:
            _out[_k] = error_direction(_k, _failed[_k])
            continue
        try:
            _out[_k] = compute_lamp_direction(_k, _hist.get(_k))
        except Exception as _e:  # noqa: BLE001 — 只影響這一盞
            print(f"[views/page_today] 變化方向計算失敗（{_k}）：{_e!r}")
            _out[_k] = error_direction(_k, type(_e).__name__)
    return _out


def _load_allocation() -> tuple[Any, str]:
    """`get_allocation()`（建議持股 SSOT）。回 `(decision, err)`。"""
    try:
        from src.services.allocation_service import get_allocation
        return get_allocation(), ""
    except Exception as _e:  # noqa: BLE001
        print(f"[views/page_today] get_allocation 失敗：{_e!r}")
        return None, repr(_e)


def _load_regime() -> tuple[Mapping[str, Any] | None, str]:
    """`get_macro_regime()`（市場位階 SSOT）。回 `(regime_dict, err)`。"""
    try:
        from src.services.allocation_service import get_macro_regime
        return get_macro_regime(), ""
    except Exception as _e:  # noqa: BLE001
        print(f"[views/page_today] get_macro_regime 失敗：{_e!r}")
        return None, repr(_e)


def _load_danger(readout: MacroReadout) -> tuple[tuple[str, str] | None, str, str]:
    """**指標危險度那一半**（16 盞燈 worst-of）。回 `((band, detail), err, 出處)`。

    走 `tab_macro_v2` 既有的三支純函式（`build_rows` → `bucket_summary` →
    `overall_verdict`），**本檔不重寫一套 worst-of** —— 重寫就是第二把尺。

    ⚠️ **【1】2026-09-07：這一支完全不吃 `regime`，也不得吃。**
    修前它是 `_load_parallel(readout, regime)`，開頭一句
    `if regime is None: return None, ""` 把**不依賴 regime 的計算**
    綁在 regime 的成敗上，於是位階掛掉時畫面會印出一句
    「16 盞燈本輪一盞都沒有落在綠 / 黃 / 紅」——
    **那 16 盞燈這一輪根本沒被算過**。§1：不得顯示一個沒發生過的計算的結論。
    `overall_verdict()` 自己的 docstring 也明文寫「**本函式不吃、也不得吃
    regime**」，修前的寫法等於在呼叫端把那條約束又綁回去。

    三種回傳，出處都講對（【8b】）：
      · `readout.requested=False` → `(None, "", "")`：**連算都沒算**（idle）。
      · `readout.error` → `(None, 該錯誤, SRC_FIVE_BUCKET)`：五桶那一輪就
        炸了，危險度沒有輸入可算 —— 出處是**五桶**，不是本函式。
      · 本函式自己炸 → `(None, repr(e), SRC_DANGER)`。
    """
    if not readout.requested:
        return None, "", ""
    if readout.error:
        # 輸入（readiness 側車）本身就沒有 —— 據實把上游的錯與出處帶下去，
        # 不在這裡改寫成「沒有資料可彙總」（那會把故障說成缺資料）。
        return None, readout.error, SRC_FIVE_BUCKET
    try:
        from src.ui.tabs.tab_macro_v2 import (
            build_rows, bucket_summary, overall_verdict,
        )
        return overall_verdict(
            bucket_summary(build_rows(dict(readout.readiness)))), "", ""
    except Exception as _e:  # noqa: BLE001
        print(f"[views/page_today] 指標危險度算不出來：{_e!r}")
        return None, repr(_e), SRC_DANGER


def _load_key_alerts(session: Mapping[str, Any]) -> tuple[Any, bool, str]:
    """今日關鍵橫幅。回 `(alerts, threshold_scanned, err)`。

    `threshold_scanned` 用 `bool(session['macro_alerts'])` —— `None`（沒跑到）
    與 `[]`（跑了但全 None）都 falsy，兩者都**不算掃過**。
    """
    _raw = session.get(SESSION_KEY_MACRO_ALERTS)
    try:
        # ⚠️ 這是 **L2**（`compute.macro`），不是 L3 契約 —— 錯誤文案走
        #    `_error_why(SRC_KEY_ALERTS, ...)`，見【8b】。
        from src.compute.macro.daily_key_alerts import collect_key_alerts
        return (collect_key_alerts(_raw, session.get("macro_info")),
                bool(_raw), "")
    except Exception as _e:  # noqa: BLE001
        print(f"[views/page_today] collect_key_alerts 失敗：{_e!r}")
        return None, bool(_raw), repr(_e)


# ══════════════════════════════════════════════════════════════════
# v2 卡面（葉1 ① **三張並排的卡全部**走這條路）
#
# ⚠️ **2026-09-24 客戶裁示批 1：下面那條刪除線是有意識的政策變更，⛔ 不是漏刪。**
# ~~客戶要的是「一張給客戶看的樣板」，所以這一段**刻意只接一張卡**：~~
# ~~`verdict.exposure`。同一排的另外兩張（`verdict.danger` / `verdict.regime`）~~
# ~~一行都沒動，留著當**對照組** —— 新舊兩種卡面並排，差異一眼看得到。~~
# · **舊做法的理由仍然成立**（在它寫下的那天）：樣板卡就是要讓客戶把新舊兩種卡面
#   擺在一起比，留兩張舊卡當對照組是**當時唯一看得到差異**的方式。
# · **被權衡掉的是它的前提**：客戶 2026-09-24 看過對照之後裁示「三張同版」——
#   對照組的任務結束了，再留著只會讓同一排長出兩種卡面（那本身就是版面不一致）。
# **現行**：`V2_CARD_BLOCKS` 是 **key → block 的分派表**，日後加卡只要加一列。
#
# 🔴 **CSS 一律走 `src/ui_v2/markup.page_css()`，⛔ 不在本檔抄一份。**
#    抄 ~30 條規則進 L5 ＝ 第二個真相源（§2.1）：`markup.py` 改了色票 / 密度階，
#    本檔這一份不會跟著動，而畫面**看起來仍然正常**（只是與規格對不上）。
#    `markup.py` 是既有的 repo 內模組，⛔ 不是新依賴、⛔ 不是新 pip 套件。
#
# 🔴 **本區塊零顏色、零字級、零 px**（§3.3 反捏造）——
#    全部由 `markup.page_css()` / `components.*` 供給。
#    📌 **2026-09-24 更新**：~~本區塊唯一的數字是 `V2_LEVEL_MAX_CHARS`~~ ——
#    那個常數本輪已刪（0 caller，見其原址的清理註）。**現在本區塊一個自有數字都沒有**：
#    `why` 那一列的字數預算 `V2_WHY_MAX_CHARS` **直接讀**契約層的
#    `v2_markup.FACT_VALUE_MAX_CHARS`，⛔ 不再抄一份。
# ══════════════════════════════════════════════════════════════════
#: 分派表**手寫**的那 12 列（＝ key 無法由 L0 SSOT 展開的那些）。
#:
#: ⛔ **刻意與 `_V2_SSOT_BLOCKS` 分開放**（唯一理由，⛔ 不是排版偏好）：
#: 分開才驗得到「兩邊有沒有撞 key」（`_assert_v2_dispatch_keys_do_not_collide()`）——
#: 直接寫在同一個 dict 字面量裡的話，重複 key 會被 Python **靜默**吃掉
#: （後寫的蓋前寫的，⛔ 不報錯），從合併結果反推**永遠驗不到**。
_V2_HANDWRITTEN_BLOCKS: dict[str, str] = {
    # ── 葉外 chrome（t3）：頂部狀態列三張 ─────────────────────────
    # 來源是 `tab_today.build_status_bar_cards()` 的 `Card`（⛔ 不是 `Tile`）——
    # 橋接在 `_tiles_of_cards()`，**`tab_today.py` 一個字都沒動**（檔案邊界）。
    "statusbar.trading_day": "today.statusbar",
    "statusbar.macro":       "today.statusbar",
    "statusbar.sheet":       "today.statusbar",
    # ── 第一層（t1）：葉1 ① 三張並排的結論卡 ───────────────────────
    "verdict.exposure": "today.verdict",   # ① 能不能出手 · 出手到幾成
    "verdict.danger":   "today.verdict",   # ② 指標危險度（不含多空方向）
    "verdict.regime":   "today.verdict",   # ③ 市場位階
    # ── 第二層（t2）：葉1 ③ 線框的三欄摘要 ──────────────────────────
    # 同樣來自 `build_today_blocks()["today.summary"].cards` 的 `Card`。
    "summary.regime":   "today.summary",
    "summary.momentum": "today.summary",
    "summary.risk":     "today.summary",
    # ── 第二層（t2）：葉1 ④ 今日關鍵橫幅 ───────────────────────────
    "key_banner.alerts": "today.key_banner",
    # ── 第四層（t4）：葉1 ⑤⑥ 作戰室 / AI 摘要（未接線，誠實標） ──────
    "warroom.todo": "today.warroom",
    "warroom.ai":   "today.warroom",
}

#: 分派表**由 L0 SSOT 展開**的那 21 列 —— 葉2 五桶摘要（5）＋ 指標明細 16 盞燈。
#: ⚠️ **⛔ 不手抄 key**：手抄一份 21 個 key 的名單就是第二把尺 —— L0 加一盞燈、
#: 改一個桶名，名單不會跟著動，而那盞燈會**靜靜地退回舊卡面**
#: （畫面看起來正常，只是同一葉長出兩種卡面）。
#:
#: 🔴 **五桶摘要為什麼併進 `today.detail`（本輪的判斷，就地寫明理由）**：
#:    v2 契約層的 block key **只有 8 個**，⛔ 而且本輪不得新開
#:    （那是契約層 `src/ui_v2/page_today.py::_LAYER_PLAN`，不在本輪的檔案邊界內）。
#:    可選的只有既有 8 個裡的哪一個，判準三條，三條都指向 `today.detail`：
#:    ① **同一葉**：五桶摘要住在葉2（`LEAF_DETAIL`），`today.detail` 是葉2 唯一的
#:       block；`today.summary` 是**葉1 ③** 的三欄摘要，已經被上面三列佔住，
#:       兩組不相干的卡共用一個 block key 會讓「這個 block 是什麼」變成兩種答案。
#:    ② **同一批資料的 roll-up**：五桶摘要就是這 16 盞燈**按桶收斂**的結果
#:       （同一次 `compute_five_bucket_summary` 側車：`readout.summary` 與
#:        `readout.readiness` 來自同一支 `load_macro_readout()`），
#:       ⛔ 不是另一組觀測 —— 它與 16 盞燈本來就該同階。
#:    ③ **密度階對得上**：`today.detail` ⇒ 第四層 ⇒ **t4（展開佐證）**，
#:       而葉2 整葉就是「展開佐證」；判給 `today.summary` 會讓它宣稱 **t2（核心卡）**
#:       的密度，與它所在的葉自相矛盾。
#:       附帶：`BLOCK_COLS["today.detail"] == (3, 2, 1)`，桌機 3 欄 ——
#:       與本檔 `_render_tiles(...)` 既有的 `MAX_COLS=3` **實際排法一致**
#:       （⛔ 不是挑一個讓數字好看的 block：對不上的話卡面契約與實際欄數會說兩種話）。
_V2_SSOT_BLOCKS: dict[str, str] = {
    **{f"summary.{_b}": "today.detail" for _b in BUCKET_ORDER},
    **{f"detail.{_s.key}": "today.detail" for _s in BUCKET_DANGER_SPECS},
}

#: **分派表**：走 v2 卡面的卡 `key` → 它在 v2 版面契約裡的 **block key**。
#: 不在表內的 key 一律走既有 `_ui_kit.render_card_isolated()`（舊卡面）。
#: **手寫 12 列 ＋ SSOT 展開 21 列 ＝ 整頁 33 張卡**
#: （客戶 2026-09-24 裁示：放棄分批，一次整頁卡化）。
#:
#: ⚠️ **2026-09-24（同日稍早）取代舊的「`V2_CARD_KEYS` 單一 key ＋ `V2_BLOCK` 單一常數」**
#: （有意識的政策變更，⛔ 不是漏刪；決策者：客戶）。**舊寫法的理由仍然成立**：
#: 只有一張卡時它是最省的寫法。**被權衡掉的是它的擴充成本** —— 加第二張就得同時
#: 改兩個常數 ＋ 一支只驗一個 block 的斷言；分派表把「加一張卡」收斂成**加一列**。
#:
#: 密度階**不由本檔指定** —— `v2_markup.card_html()` 內部呼叫
#: `v2_page.tier_for_block()` 依「它所在的層」自動決定（該函式刻意沒有 `tier=` 入口）。
#: ~~本檔只在 import 時**逐 block 驗**它真的是 t1（見 `_assert_v2_blocks_are_tier_one`）。~~
#:
#: 🔴 **2026-09-24 客戶裁示「一次把整頁卡化」：上面那條刪除線是有意識的政策變更，⛔ 不是漏刪。**
#: **舊句的理由仍然成立**：表裡只有 `today.verdict` 一個 block 時，「逐 block 驗它是 t1」
#: 與「驗這一個 block 是 t1」**外延相同**，寫哪個都對，而且它擋得住「對面把結論燈搬層」。
#: **被權衡掉的是它的前提** —— 整頁卡化之後表裡有 **6 個 block、橫跨 4 個密度階**
#: （`today.statusbar` t3 ／ `today.verdict` t1 ／ `today.summary` t2 ／
#:  `today.key_banner` t2 ／ `today.warroom` t4 ／ `today.detail` t4；
#:  實測值見 `V2_EXPECTED_TIERS`），「全部都是 t1」這個期望值**本身就變成假的**。
#: **現行**：期望值改成**逐 block 各自的密度階**（`V2_EXPECTED_TIERS`），
#: 守的東西一樣（對面搬層 ⇒ 當場炸），⛔ 不是把斷言拿掉了事。
V2_CARD_BLOCKS: dict[str, str] = {**_V2_HANDWRITTEN_BLOCKS, **_V2_SSOT_BLOCKS}

#: 走 v2 卡面的卡 key。**由分派表推出來，⛔ 不另列一份名單**（那才是第二把尺）。
V2_CARD_KEYS: frozenset[str] = frozenset(V2_CARD_BLOCKS)

#: ~~分派表裡**每一個** block 都應該落在的密度階。~~**這是斷言用的期望值，不是設定值**
#: —— 本檔沒有任何地方把它傳給 `card_html`（傳不進去，那支函式不收）。
#:
#: 🔴 **2026-09-24 整頁卡化：單一字串 → 逐 block 對照表。有意識的政策變更，⛔ 不是漏刪。**
#: **舊寫法的理由仍然成立**：表裡只有一個 block 時，一個字串就講得完。
#: **被權衡掉的是它的前提** —— 現在橫跨四階，一個字串**表達不了**，
#: 硬留著只有兩條路：把它放寬成「不驗」，或把四階硬說成 t1。兩條都是弱化。
#:
#: ⚠️ **這張表是期望值，⛔ 不是來源** —— 實際密度階永遠由
#: `v2_page.tier_for_block()`（＝ block 所在的層）決定；本表只負責在
#: **import 時**把「對面把某個 block 搬到別層」變成當場 `RuntimeError`。
#: ⛔ 對不上時**不得**把期望值改成現況了事（那等於把守衛關掉）。
V2_EXPECTED_TIERS: dict[str, str] = {
    "today.statusbar":  "t3",   # 葉外 chrome
    "today.verdict":    "t1",   # 第一層 結論燈
    "today.summary":    "t2",   # 第二層 核心卡
    "today.key_banner": "t2",   # 第二層 核心卡
    "today.warroom":    "t4",   # 第四層 展開佐證
    "today.detail":     "t4",   # 第四層 展開佐證
}

#: 樣式表模式。出處：`src/ui_v2/render.py::unwired_view_model(*, mode="dark")` 的既有預設值
#: （本檔**不 import** 那支 —— 它會拉 streamlit；只沿用它已經定案的字面）。
#: 合法值由 `tokens.get_token(mode=)` 把關，寫錯會當場炸，⛔ 不會靜默退回一組顏色。
V2_CSS_MODE: str = "dark"

#: 這一次 script run 有沒有吐過 v2 樣式表。
#:
#: ⚠️ **刻意是「一次 script run 一次」，⛔ 不是「一個 session 一次」**（實作細節，寫死免得被改回去）：
#: Streamlit 每一輪 rerun 會**重建整棵元素樹**，這一輪沒有再吐一次的元素就會從 DOM 消失。
#: 真的做成「整個 session 只注入一次」的話，**第二次 rerun 起樣式表就不見了** ——
#: 卡片變成沒有樣式的裸 HTML，而**所有守衛仍然是綠的**（字都還在、測試也抓不到）。
#: 那正是 §1 要防的靜默失效。故 `render_page_today()` 在**每一輪開頭清掉這個旗標**，
#: 本旗標只負責「同一輪裡畫第二張 v2 卡時不要再吐一次」。
SS_V2_CSS_DONE: str = "_p01_v2_css_emitted"

#: v2 卡面產不出來時，例外的出處（【8b】：出事的是哪一層只有本頁知道）。
SRC_V2_MARKUP: str = (
    "L5 `src/ui_v2/markup`（v2 卡面標記層：`page_css` / `card_html`）")

# ~~`V2_LEVEL_MAX_CHARS`（壓縮後那一行的字數上限）與 `V2_LEVEL_ELLIPSIS`（截斷記號）~~
# 🔴 **2026-09-24 整頁卡化：兩者已刪除。有意識的清理，⛔ 不是漏刪；決策者：AI 總管。**
#
# · **它們為什麼在**：舊做法把三段 `Note` 壓成**一行**，那一行沒有任何長度保證，
#   所以需要一個字數夾子 ＋ 一個截斷記號。**那個理由在它寫下的那天完全成立。**
# · **它們為什麼走**：本輪改成三列 fact 之後，**沒有任何一段文字走本檔的夾子** ——
#   `now` 與 `去哪補` 由來源本身就短；`why` 走 `_v2_why_phrase()` 的**子句邊界**收尾；
#   真的還超出的（只有紅態）交給**契約層自己**的
#   `v2_markup.FACT_VALUE_MAX_CHARS`。⇒ 兩個常數 **0 caller**。
# · **為什麼不留著**：`CLAUDE.md §-1.5.F 判定 3(4)` —— 「**因本次改動才變成 0 caller
#   的孤兒**」是本次任務的**收尾義務**，⛔ 不是趁機清全 repo。
#   留一個字數夾子在那裡，下一個人會以為卡面還有一道本檔自己的截斷，
#   然後在兩把尺之間找 bug。
# · **它的「46」沒有消失，而且不再是第二份**：`V2_WHY_MAX_CHARS` 現在**直接讀**
#   `v2_markup.FACT_VALUE_MAX_CHARS`（見該常數）⇒ 全頁只剩**一個** 46。

#: 出口常數 → v2 卡面那一行的**固定短語**。⛔ 不是截斷。
#:
#: 🔴 **2026-09-24 客戶退回「截尾＋…」：讀起來是斷句，改成重寫成短語。**
#: 舊做法（`where.split("。")[0]` ＋ 字數上限）的理由仍然成立 —— 它**不挑字**，
#: 文案怎麼改都跟得上。**被權衡掉的是它的產出**：首句本身就有 40~90 字，
#: 夾住之後必然斷在半句話中間，而「讀不完的半句」對使用者等於沒有指路。
#:
#: 🔴 **key 是常數物件本身，`_v2_exit_phrase()` 用 `is` 比對**（客戶明示）：
#: 改成比對字串開頭的話，文案改一個字就**默默**退回長句 —— ⛔ 不會報錯（§1）。
#: ⚠️ **據實揭露（§3.3）：這~~四~~**五**個短語沒有契約層出處，是實作層挑的**
#: （「四 → 五」是 2026-09-24 整頁卡化新增 `EXIT_DEGRADED_READ_DIRECTION` 那一列所致；
#:  另兩列 `CONTRACT_NO_EXIT_WHERE` / `STAGED_ROLLOUT_WHERE` **不算**在內 ——
#:  它們回的是 `NO_EXIT_MARKER` 這個既有 SSOT 常數本身，⛔ 不是本檔挑的字）。
#: 客戶只給「≤30 字」這個上限與三個
#: **舉例**；用字一律沿用對應常數自己的字面（射程／程式要修／只更新得到一半／
#: **方向·門檻** —— 後者出自 `EXIT_DEGRADED_READ_DIRECTION` 原文的
#: 「別看它有沒有過線，改看它…的變化**方向**」），⛔ 不新造名詞。
#: 🔴 **⛔ 一個字都沒刪**：完整三段原文照舊掛在外層 `title=`。
#: ⚠️ ~~`EXIT_ALERTS_PARTIAL` 現在**沒有**卡走到（今日關鍵橫幅不在 `V2_CARD_BLOCKS`
#: 內）。仍然登記，是因為漏登的後果是**渲染當下才炸**；登記的成本是一行。~~
#: 📌 **2026-09-24 事實更正 —— 有意識的更正，⛔ 不是漏刪。** 整頁卡化之後
#: `key_banner.alerts` **已經在** `V2_CARD_BLOCKS` 內 ⇒ 這一條**真的有卡在走**。
#: ⚠️ 變的只有事實；**當初「先登記」的判斷仍然成立**（漏登的後果是渲染當下才炸）。
#: 🔴 **`CONTRACT_NO_EXIT_WHERE` 是對面 `tab_today` 的常數，⛔ 不是本檔的 `EXIT_*`**
#: （2026-09-24 補登；**實跑抓到的漏登**，⛔ 不是預防性登記）：位階卡 `degraded` 態
#: 刻意**整份沿用** `build_status_bar_card().note`（§2.1 SSOT），所以它的 `where`
#: 是**那一支**給的物件。三張卡全部改走 v2 卡面之後，這一態會走進 `_v2_exit_phrase()`
#: ⇒ 漏登＝`KeyError`＝**畫成紅卡**。⚠️ 它的短語沿用該常數自己開頭的
#: `NO_EXIT_MARKER` 字面（⛔ 不新造名詞）；**完整原文照舊掛在外層 `title=`**。
#: 🔴 **2026-09-24 整頁卡化新增兩列（`EXIT_DEGRADED_READ_DIRECTION` /
#: `STAGED_ROLLOUT_WHERE`），並新增一道 fallback（見 `_v2_exit_phrase()` 第 2 段）。**
#: 原因是**實跑窮舉**出來的，⛔ 不是推測：本輪把 33 張卡在
#: idle / empty / unwired / degraded / failed / live 各態下全部建一遍，
#: 收集到 **22 個相異的 `Note.where` 物件**，其中
#:   · 5 個對得上本表既有的 `EXIT_*` / `CONTRACT_NO_EXIT_WHERE`；
#:   · 1 個是 `tab_today.STAGED_ROLLOUT_WHERE`（**模組常數，比得到身分** → 本輪登記）；
#:   · 1 個是本輪上提的 `EXIT_DEGRADED_READ_DIRECTION`（**原本寫在函式體裡**）；
#:   · 其餘 15 個全部是**函式體內的 f-string**（`statusbar.sheet` /
#:     `statusbar.macro` 紅態 / 16 盞燈的 unwired 態）—— 它們住在
#:     `src/ui/tabs/tab_today.py`，**本輪的檔案邊界外**，⛔ 上提不得。
#:     這 15 個**每次呼叫都是新物件**，`is` 在結構上永遠對不上。
V2_EXIT_PHRASES: tuple[tuple[str, str], ...] = (
    (EXIT_RETRY_HERE,             "按上方 🚀 更新"),
    (EXIT_OUT_OF_REACH,           "不在本頁射程內"),
    (EXIT_FIX_CODE,               "需修程式"),
    (EXIT_ALERTS_PARTIAL,         "只更新得到一半"),
    (EXIT_DEGRADED_READ_DIRECTION, "改看方向，別照門檻讀"),
    (CONTRACT_NO_EXIT_WHERE,      NO_EXIT_MARKER),
    (STAGED_ROLLOUT_WHERE,        NO_EXIT_MARKER),
)

#: 三要素**第三列**（`Note.where`）的 fact 列標籤。用語沿用鐵律 4 的三要素字面。
#:
#: ⚠️ ~~壓縮後那一行**退而求其次**時掛的 fact 列標籤。~~
#: 📌 **2026-09-24 整頁卡化更新（有意識的更正，⛔ 不是漏刪）**：它已經**不是退路**，
#: 而是三列 fact 的**固定第三列**（見下方 `V2_NOW_FACT_KEY` / `V2_WHY_FACT_KEY`）。
#: **但下面整段理由一字未改、而且全部仍然成立** —— 它解釋的是「**為什麼三要素
#: 非走 fact 列不可**」，那個結構性原因（契約對灰態紅態一律判決留白）沒有任何改變。
#:
#: 🔴 **為什麼需要這個退路（實測，⛔ 不是設計偏好）**：v2 契約層對
#: **灰態與紅態一律「判決留白」**（`v2_page.card_level_text()` 對
#: `idle` / `empty` / `missing` / `na` / `unwired` / `failed` / `degraded` 一律回 `None`，
#: 本輪逐態實跑確認）—— 而**會帶 `Note` 的正好就是這些態**。
#: 也就是說：指路句若只走 `level=`，在**每一個需要它的狀態下都會整段消失**，
#: 而畫面上只剩標題＋徽章，看起來完全正常（⛔ §1 無聲丟棄 ＋ 鐵律 4 三要素蒸發）。
#: ⇒ 契約留白時改掛成**卡內第一列 fact**（fact 列任何狀態都會畫）。
#: ⚠️ 走哪一邊**由契約自己的 `card_level_text()` 決定**，⛔ 不是本檔另判一次；
#: 兩條路互斥，⛔ 不會重複印。契約哪天改成灰態也畫判決區，這一行**自動**搬回
#: `.blk-lvl`，本檔一個字都不用改。
V2_GUIDE_FACT_KEY: str = "去哪補"

#: 🔴 **2026-09-24 客戶裁示：三要素要在卡面上看得到，⛔ 不是只剩一條指路 ＋ hover。**
#:
#: 鐵律 4 的三要素（`Note.now` / `.why` / `.where`）各自一列 fact。
#: **標籤逐字沿用鐵律 4 自己的說法**（現在怎樣 / 為什麼 / 去哪補），⛔ 不新造名詞；
#: 第三列沿用既有的 `V2_GUIDE_FACT_KEY`（⛔ 不另立一個同義的常數）。
#:
#: ⚠️ **順序有意義，⛔ 不得調換**：使用者的閱讀順序是
#: 「**這一格現在怎樣 → 為什麼 → 那我能做什麼**」，
#: 把「去哪補」排在中間會讓最可操作的那一句被夾在兩段說明裡。
V2_NOW_FACT_KEY: str = "現在"
V2_WHY_FACT_KEY: str = "為什麼"

#: `Note.why` 壓成一列時，**允許在哪些「子句邊界」收尾**（由寬到嚴，依序嘗試）。
#:
#: 🔴 **這是子句切分，⛔ 不是字數截斷** —— 客戶 2026-09-24 退回的是
#: 「截尾＋`…`」（讀起來是斷句）。本表切的每一刀都落在**標點劃出的子句界線**上，
#: 切完仍是一個讀得完的完整子句，⛔ 不會斷在半句話中間。
#:
#: **順序的依據（⛔ 不是隨手排的）**：依「後半段**離主旨多遠**」由遠而近 ——
#:   1. `——` 後面幾乎都是**對比澄清**（「這是『還沒叫』，不是『叫了沒回』」）：
#:      有價值，但它澄清的是**前半段已經講過的事**，是最先可讓的；
#:   2. `。` 後面是**另一整句**補充（常是上游例外訊息的後續句）；
#:   3. `；` 後面是**第二個獨立子句**；
#:   4. `（` 後面是**括號補充**；
#:   5. `，` 後面是**同句的後續子句**（離主旨最近，**最後才讓**）。
#: ⚠️ **只有在還超出顯示預算時才往下切一刀**（見 `_v2_why_phrase()`）——
#: 短的 `why` 一個字都不動，而且**切到進預算就停**（⛔ 不會一路切到剩半句）。
#: **被切掉的部分⛔ 沒有消失**：完整三段原文照舊掛在卡的外層 `title=`（hover 看得到）。
#:
#: ⚠️ **據實揭露（§3.3）：這張表與它的順序沒有契約層出處，是實作層挑的**
#: （沿用 `V2_EXIT_PHRASES` 的既有先例）。
V2_WHY_CLAUSE_SEPARATORS: tuple[str, ...] = ("——", "。", "；", "（", "，")

#: `why` 那一列的顯示預算。**刻意與 `v2_markup.FACT_VALUE_MAX_CHARS` 對齊**
#: —— 那是 fact 值那一格真正會動手截斷的地方；本檔要做的是
#: 「**在它動手之前，先在子句邊界收好**」，所以兩者必須是同一個數字。
#:
#: 🔴 **直接讀對面的常數、⛔ 不手抄一個 46**（§2.1）：手抄的那天對面調了值，
#: 本檔會在它的預算之外多送幾個字過去，然後**被它截尾** —— 而那正是本輪要避免的事，
#: 且畫面上看起來完全正常（只是多了一個 `…`）。
V2_WHY_MAX_CHARS: int = v2_markup.FACT_VALUE_MAX_CHARS

#: **移出卡面、只留 hover** 的 fact 列：`card.key` → 該卡要移出的 fact **標籤**集合。
#:
#: 🔴 **2026-09-24 客戶裁示：卡③「位階的出處」那一列不再出現在卡面。**
#: 🔴 **⛔ 一個字都沒刪** —— 整段 `REGIME_SCOPE_NOTE`（193 字）**原文逐字**改掛該卡的
#:    `title=`（見 `v2_card_html` 結尾），滑過去就看得到。
#:    ⚠️ 這**不是**漏渲染：下一個人看到卡③ 少一列時，請先讀本註再動手。
#:
#: **為什麼移的是這一列（判準，⛔ 不是「嫌它長」）**：它是**免責說明**，⛔ 不是**觀測值**。
#: `REGIME_SCOPE_NOTE` 的 docstring 自陳：它是為了**否認**一句 2026-09-07 獨立稽核
#: **實測為假**的全稱宣稱而寫的**誠實揭露**（被否認的那句話、以及它假在哪裡，
#: 逐字寫在該常數與 `REGIME_CARD_LABEL` 的註裡 —— 本行⛔ 不複述，複述一次就是
#: 多一個會漂開的複本，而且會再踩一次
#: `tests/test_views_no_unverified_universal_claims.py` 的登記制）。
#: 揭露的職責是「**要看得到**」，
#: ⛔ 不是「**要佔住第一眼**」—— 三張並排的 t1 結論卡是拿來一眼看結論的，
#: 193 字的免責擺在那裡會把真正的觀測（現值 / 生效分支）擠掉。
#: ⇒ **移的是版位，⛔ 不是內容**；內容一字不少地留在 hover。
#:
#: ⚠️ **同一張卡 degraded 態的 `("現值", _rlabel)` 是觀測值 ⇒ ⛔ 不在表內，照留卡面。**
#:    本表比對的是**單一標籤**，⛔ 不是「這張卡的 facts 全部不顯示」。
#: ⚠️ **表外的卡一行都沒變**（⛔ 不是「所有 fact 都不顯示」）——
#:    卡① `verdict.exposure` / 卡② `verdict.danger` 的 fact 列原樣照畫。
#: ⚠️ 日後要再移一列，**先問自己：它是免責 / 出處說明，還是這一眼要看的觀測值？**
#:    是觀測值 → ⛔ 不准移進來（那就是把使用者該看到的東西藏進 hover）。
V2_HOVER_ONLY_FACTS: dict[str, frozenset[str]] = {
    "verdict.regime": frozenset({REGIME_SCOPE_FACT_KEY}),
}

#: 🔴 **2026-09-25 客戶核可線框：16 盞燈卡（`detail.*`）的三列出處說明收進「▸ 詳細」。**
#: 摺起來的是這三個**標籤**（`build_indicator_tile` 逐字組的那三列）；
#: 卡面留：標題＋徽章、大字、判決行、「變化方向」、「門檻帶」；
#: 非 live 卡的三要素（現在／為什麼／去哪補）與 degraded 的「現值」**照留卡面、⛔ 不摺**。
#: ⛔ **一個字都沒刪、沒改寫** —— 同一段文字只是換進 ~~原生 `<details>`~~ 純 CSS 開關
#:    （2026-09-25 客戶選 (b)：`<details>` 在 iPhone 點了沒反應；現為隱藏 checkbox ＋
#:    `<label for>`，見 `markup._fold_rules`。預設收合，⛔ 無 JS、⛔ 無 hover）；
#:    列的畫法與卡面同一支（`markup._facts_block`）。
#: ⚠️ 只作用於 `V2_FOLD_CARD_PREFIX` 開頭的卡 ⇒ 本頁其餘卡與其他四頁**逐 byte 不變**。
V2_FOLD_CARD_PREFIX: Final[str] = "detail."
V2_FOLDED_FACT_KEYS: frozenset[str] = frozenset({"命中來源", "門檻出處", "這條線在看什麼"})

#: L0 十態 → （`src/ui_v2/page_today.py` 的狀態語彙, `resolve_badge()` 要的缺值原因）。
#:
#: **為什麼需要這張表**：兩邊是**兩套字面**，不通用 ——
#: L0 把 `UI_EMPTY` 拆成 `missing_retryable` / `not_applicable`（鍵名刻意避開
#: `station_specs.STATE_MISSING`）；v2 契約層用的是線框語彙 `missing` / `na`。
#: 不翻譯直接餵進去，`card_value_text()` 會當場 `ValueError`（它只認 v2 那套）。
#: 這與本檔既有的 `READINESS_REASON_TO_MISS` 是**同一種東西**（語彙翻譯），
#: ⛔ 不是第二張狀態表：**徽章與留白規則都仍然由對面決定**，這裡只換字面。
#:
#: 🔴 **這張表不是抄來的，是對出來的，而且 import 時會回推驗一次**
#: （`_assert_v2_state_vocab_matches_ssot`）：每一筆都要能從
#: `components.BADGES[*].state_const` / `.miss_reason` **解回同一個 L0 態**。
V2_STATE_VOCAB: dict[str, tuple[str, str | None]] = {
    UI_LIVE:              ("live",     None),
    UI_LOADING:           ("loading",  None),
    UI_IDLE:              ("idle",     None),
    UI_DEGRADED:          ("degraded", None),
    UI_UNWIRED:           ("unwired",  None),
    UI_FAILED:            ("failed",   None),
    # #7／#8 的分辨鍵在 `miss_reason`；`Card` **沒有** `reason` 欄位，
    # 所以分辨結果是 L0 先編碼進狀態鍵、本表再翻回 v2 語彙（見 `shared/ui_state.py`）。
    UI_MISSING_RETRYABLE: ("missing",  None),
    UI_NOT_APPLICABLE:    ("na",       v2_page.MISS_NOT_APPLICABLE),
    UI_EMPTY:             ("empty",    None),
    UI_PARTIAL:           ("partial",  None),
}

#: **回推對不上、而且契約本身就分不出來**的兩態。⛔ 登記制，不是漏驗。
#:
#: · `UI_EMPTY`：#7 與 #8 的 `state_const` **都是** `UI_EMPTY`，分辨鍵是
#:   `miss_reason`，而 `Card` 不帶原因 ⇒ 從一個裸 `empty` **解不出**是哪一顆。
#:   **本檔不自己挑**：把決定權交回 v2 的 SSOT 函式 `v2_page.resolve_badge()`，
#:   它對 `state="empty"` 有明文裁決（`UI_PAGE_TODAY.md ② 狀態覆蓋表 empty 列`：
#:   「#7 被 `empty`＋`missing` 兩鍵共用」）。
#:   ⚠️ **據實揭露一個兩邊說法不一致的地方**（⛔ 不吞）：L0 對裸 `UI_EMPTY` 的立場是
#:   「**分不出是哪一種缺值**、對能不能重試不做任何宣稱」，而 v2 的 #7 文字**會**
#:   宣稱可重跑。⇒ 這一態的徽章文字比 L0 多講了一句話。本輪**照 v2 SSOT 走並登記在此**，
#:   ⛔ 不在本檔另發明一顆徽章（那是 §3.3），要改請先改 v2 契約層。
#: · `UI_PARTIAL`：#9 的 `state_const` 是 `None`（七態沒有 partial，#9 是新訂的），
#:   本來就回推不到；`resolve_badge` 在拿不到分子分母時走**它自己的 fail-safe**
#:   降 #7，⛔ 本檔不代它決定。
#:
#: ⛔ **任何不在本集合、又回推對不上的 L0 態 → import 時 `RuntimeError`。**
#: 這就是「查不到就 fail loud」的落點：L0 日後新增第十一態時，
#: 本頁**當場說出來**，⛔ 不會靜靜地給它一顆看起來合理的徽章。
V2_BADGE_AMBIGUOUS: frozenset[str] = frozenset({UI_EMPTY, UI_PARTIAL})

#: 📌 **2026-09-26 補（上面 `V2_BADGE_AMBIGUOUS` 的註解一字未動）**：客戶同日新增 #11
#: 「▨ 無資料」（有效的空結果）。它**不是**在本檔另發明一顆徽章 —— 徽章住在
#: `src/ui_v2/components.py::BADGES`、判定在 `v2_page.resolve_badge(valid_empty=True)`；
#: 本檔只負責**哪幾張卡有資格**，而且是**登記制**（見下表）。
#: 裸 `UI_EMPTY` 的預設仍然是 #7 —— 上面那段「徽章文字比 L0 多講了一句話」的揭露，
#: 對**沒登記**的卡照樣成立、照樣有效。
#:
#: **有效的空結果登記處**：`(card.key, 定義 `note.now` 的模組, 常數名)`。
#: 只有 `card.state == UI_EMPTY` **且** `(card.key, card.note.now)` 在此的卡才畫 #11。
#:
#: 🔴 **判準（嚴格）**：上游這一輪**成功算完**、結果**真的是 0／空**；而且**同一個
#: `(key, now)` 不會在任何別的路徑出現**（真缺漏／上游失敗被吞成空／還沒載入／未評估／
#: 未綁定／這輪沒讀／契約漂移）。只要同一對 `(key, now)` 還蓋著其中任一條路徑，
#: 就⛔ **不得登記** —— 登記了＝把 #11 擴散到那條路徑上（客戶裁示明文禁止）。
#: 逐張審查結果（含排除理由）見 `HANDOFF.md §6.4` 與 `docs/v2/spec/UI_COMPONENTS.md §2` #11 列。
#:
#: ⚠️ **為什麼存「模組＋常數名」而不是直接 import 常數**：`page_find`／`page_hold` 在
#: import 時就 `from src.ui.views.page_today import …`，本檔若在頂層反向 import 它們 ＝ 循環 import。
#: 故登記用**名字**、第一次查表時才解析（`v2_valid_empty_pairs()`）；解析不到 → `RuntimeError`
#: （§1：⛔ 不讓一個打錯的常數名靜靜地讓 #11 消失）。⛔ **不抄字串**：比對用的是那個常數的**值**。
V2_VALID_EMPTY_SPEC: tuple[tuple[str, str, str], ...] = (
    # 「這本 Sheet 裡的組合」：Sheet 讀成功、組合清單長度 0（L3 `STATUS_BOUND_EMPTY`，
    # `portfolio_count=0`）。讀取失敗走 `portfolio_count=None` ＋ `MISS_FETCH_FAILED`（紅），
    # 未綁定走 idle —— 兩者都**不會**產出 `COUNT_EMPTY_NOW` 的 `UI_EMPTY` 卡。
    ("hold.portfolio_count", "src.ui.views.page_hold", "COUNT_EMPTY_NOW"),
)

_V2_VALID_EMPTY_CACHE: list[frozenset[tuple[str, str]]] = []


def v2_valid_empty_pairs() -> frozenset[tuple[str, str]]:
    """`V2_VALID_EMPTY_SPEC` → `{(card.key, note.now 的值)}`。第一次呼叫時解析、之後沿用。

    解析不到（模組不在、常數改名、值不是非空字串）→ `RuntimeError`，⛔ 不略過。
    """
    if _V2_VALID_EMPTY_CACHE:
        return _V2_VALID_EMPTY_CACHE[0]
    import importlib
    _pairs: set[tuple[str, str]] = set()
    for _key, _mod_name, _const in V2_VALID_EMPTY_SPEC:
        _val = getattr(importlib.import_module(_mod_name), _const, None)
        if not isinstance(_val, str) or not _val.strip():
            raise RuntimeError(
                f"#11 登記 {(_key, _mod_name, _const)!r} 解析不到一個非空字串常數 —— "
                "常數被改名或刪了？⛔ 不要把這一列刪掉了事，先確認那張卡的空結果文案去哪了。")
        _pairs.add((_key, _val))
    _V2_VALID_EMPTY_CACHE.append(frozenset(_pairs))
    return _V2_VALID_EMPTY_CACHE[0]


def v2_card_badge_n(card: Card) -> int:
    """一張 `Card` → v2 徽章號。**三頁共用**（今天／找標的／我的持股都走這一支）。

    ＝ `V2_STATE_VOCAB` 翻字面 → `v2_page.resolve_badge()`；**唯一多做的一件事**是查
    `v2_valid_empty_pairs()`：登記過的有效空結果 → #11，其餘行為與改動前逐一相同。
    未知狀態 → `KeyError`（⛔ 不兜底，同改動前）。
    """
    _v2_state, _reason = V2_STATE_VOCAB[card.state]
    _valid_empty = (card.state == UI_EMPTY and card.note is not None
                    and (card.key, card.note.now) in v2_valid_empty_pairs())
    return v2_page.resolve_badge(state=_v2_state, miss_reason=_reason,
                                 valid_empty=_valid_empty)


def _v2_badge_to_l0_state(badge_n: int) -> str | None:
    """徽章號 → 它宣稱的 L0 狀態。**用常數名反解，⛔ 不手抄對照表。**

    `components.BADGES` 存的是**常數名字串**：`state_const` 是
    `shared/ui_state.py` 的名字、`miss_reason` 是 `shared/station_specs.py` 的名字。
    帶 `miss_reason` 的那兩顆（#7／#8）要再過一手 `ui_state.EMPTY_STATE_BY_REASON`
    （缺值原因 → 拆出來的那一態），因為它們的 `state_const` 都還寫著 `UI_EMPTY`。

    Returns:
        解得出來的 L0 狀態字串；解不出來（`state_const` 是 `None` 或不是十態之一）→ `None`。
    """
    _spec = v2_components.badge(badge_n)
    _reason_name = _spec["miss_reason"]
    if _reason_name is not None:
        _reason = getattr(_station_specs, str(_reason_name), None)
        return _ui_state.EMPTY_STATE_BY_REASON.get(_reason)
    _const_name = _spec["state_const"]
    _value = getattr(_ui_state, str(_const_name), None)
    return _value if _value in UI_STATES else None


def _assert_v2_blocks_are_tier_one() -> None:
    """import 時就驗：分派表裡**每一個** block 都落在**它該落的**密度階（§1 Fail Loud）。

    ⚠️ **2026-09-24 由「逐 block 驗它是 t1」改成「逐 block 驗它是期望的那一階」** ——
    ⛔ 不是拿掉這道斷言：整頁卡化之後分派表橫跨四階，「全部是 t1」**本身就是假的**，
    留著只能靠放寬（＝關掉守衛）或說謊（＝把 t4 說成 t1）。
    ⚠️ **函式名刻意不改**（`_assert_v2_blocks_are_tier_one`，雖然它已經不只驗 t1）：
    改名是**純 cosmetic**（`CLAUDE.md §8.1 step 6` 的反例），而且本檔在本輪已經
    改動夠多。**語意以本 docstring 與 `V2_EXPECTED_TIERS` 為準，⛔ 不以函式名為準。**
    📌 **實測（量測日 2026-09-24）**：全 repo `grep _assert_v2_blocks_are_tier_one`
    在本檔以外 **0 命中** ⇒ 改名不會弄壞任何東西；**不改純粹是不想製造無意義的 diff**，
    ⛔ 不是「怕動到別人」（那會是一句沒查過的話）。

    守的東西一字未減：對面把某個 block 搬到別層的那天，這些卡會靜靜地換成另一個
    密度階 —— 畫面**看起來仍然正常**，只是與規格對不上。
    另加一道：分派表用到的 block **必須**已登記期望值，⛔ 不得「沒登記就當它對」。
    """
    _blocks = sorted(set(V2_CARD_BLOCKS.values()))
    _unregistered = [_b for _b in _blocks if _b not in V2_EXPECTED_TIERS]
    if _unregistered:
        raise RuntimeError(
            f"v2 分派表用到的 block {_unregistered} 沒有登記期望密度階 —— "
            "請在 `V2_EXPECTED_TIERS` 補上它**應該**落在哪一階（查 "
            "`src/ui_v2/page_today.py::_LAYER_PLAN`），"
            "⛔ 不得因為「反正現在對得上」就不登記：不登記＝這個 block 日後被搬層"
            "**沒有任何守衛會發現**。")
    for _block in _blocks:
        _tier = v2_page.tier_for_block(_block)
        _want = V2_EXPECTED_TIERS[_block]
        if _tier != _want:
            raise RuntimeError(
                f"v2 卡面的 block {_block!r} 現在落在密度階 {_tier!r}，"
                f"不是登記的 {_want!r} —— "
                "`src/ui_v2/page_today.py` 的層序很可能動過。"
                "請確認規格，⛔ 不要把期望值改成現況了事。")


def _assert_v2_dispatch_keys_do_not_collide() -> None:
    """import 時就驗：分派表裡**沒有兩組不同來源的卡搶同一個 `card.key`**（§1）。

    🔴 **為什麼需要這一道（實測的近距離擦撞，⛔ 不是預防性儀式）**：
    葉1 ③ 的三欄摘要用 `summary.regime` / `summary.momentum` / `summary.risk`
    （`tab_today.build_today_blocks()`），而葉2 的**五桶摘要**用
    `summary.{BUCKET_ORDER}`（本檔 `build_bucket_tiles()`）—— **同一個 `summary.` 前綴、
    兩支不同的 builder**。現況 `BUCKET_ORDER` ＝ long/mid/short/chips/news，
    與 regime/momentum/risk 零交集，所以**現在**沒事。
    但這是**巧合，不是設計**：L0 哪天把某一桶改名成 `risk`，
    分派表的那一列就會被另一列覆蓋掉 ⇒ 那張卡被**送進錯的 block**（錯的密度階、
    錯的欄數），而畫面**看起來完全正常**。那正是 §1 的靜默失效。

    ⚠️ **驗的是兩份來源的交集，⛔ 不是合併後的 dict** —— 合併後撞掉的那一列
    **已經不在**了（dict 字面量與 `**` 展開都是後寫的蓋前寫的、⛔ 不報錯），
    從結果反推**永遠驗不到**。這也是上面 `_V2_HANDWRITTEN_BLOCKS` /
    `_V2_SSOT_BLOCKS` 刻意分開放的唯一理由。
    """
    _clash = sorted(set(_V2_HANDWRITTEN_BLOCKS) & set(_V2_SSOT_BLOCKS))
    # SSOT 展開內部也要驗：`BUCKET_ORDER` 與 `BUCKET_DANGER_SPECS` 各自有可能重複。
    _expanded = ([f"summary.{_b}" for _b in BUCKET_ORDER]
                 + [f"detail.{_s.key}" for _s in BUCKET_DANGER_SPECS])
    _dupes = sorted({_k for _k in _expanded if _expanded.count(_k) > 1})
    if _clash or _dupes:
        raise RuntimeError(
            f"v2 分派表的 key 撞了：手寫列與 SSOT 展開相撞 {_clash}、"
            f"SSOT 展開內部重複 {_dupes} —— 兩組不同來源的卡搶同一個 `card.key`，"
            "其中一組會被靜默送進錯的 block（錯的密度階、錯的欄數），"
            "而畫面看起來完全正常。"
            "⛔ 不要把其中一列刪掉了事，先確認是哪一邊該改名。")


def _assert_v2_state_vocab_matches_ssot() -> None:
    """import 時就驗：`V2_STATE_VOCAB` 真的對得上兩邊的 SSOT（§1 Fail Loud）。

    驗兩件事：
      1. **十態一個都不准漏** —— L0 新增狀態時當場炸，
         ⛔ 不會在 render 期才變成一個 `KeyError` 紅卡（更不會靜默挑一顆徽章）。
      2. **逐筆回推** —— `resolve_badge()` 給的那顆徽章，要能經
         `state_const` / `miss_reason` **解回同一個 L0 態**；
         解不回來的，必須已登記在 `V2_BADGE_AMBIGUOUS` 並寫明理由。
    """
    _missing = [_s for _s in UI_STATES if _s not in V2_STATE_VOCAB]
    if _missing:
        raise RuntimeError(
            f"`shared/ui_state.py` 的狀態 {_missing} 在 `V2_STATE_VOCAB` 裡沒有對應 —— "
            "v2 卡面會在畫到它的時候炸。請去 `src/ui_v2/components.py::BADGES` 把它"
            "對得到的徽章查出來再補；**查不到就不要填**（§1：⛔ 不挑一顆看起來合理的）。")
    for _l0_state, (_v2_state, _reason) in V2_STATE_VOCAB.items():
        _n = v2_page.resolve_badge(state=_v2_state, miss_reason=_reason)
        _back = _v2_badge_to_l0_state(_n)
        if _back == _l0_state or _l0_state in V2_BADGE_AMBIGUOUS:
            continue
        raise RuntimeError(
            f"L0 狀態 {_l0_state!r} 被對到徽章 #{_n}，但那顆徽章宣稱的是 {_back!r} —— "
            "對映錯了，或 `src/ui_v2/components.py::BADGES` 改過。"
            "若這是一個**契約本身就分不出來**的態，請登記進 `V2_BADGE_AMBIGUOUS` "
            "**並寫明它為什麼分不出來**，⛔ 不要把回推那一段拿掉。")


_assert_v2_blocks_are_tier_one()
_assert_v2_dispatch_keys_do_not_collide()
_assert_v2_state_vocab_matches_ssot()


def v2_plain(text: object) -> str:
    """把 Markdown 強調記號拿掉。**只拿掉記號本身，⛔ 一個字都不刪。**

    為什麼要這一步：既有卡面走 `st.markdown`（`**粗體**` 會被解析），
    v2 卡面是 `card_html()` 產的 **raw HTML**、而且它把所有文字都 `escape` 過 ——
    同一串 `**今天能不能出手：尚未評估**` 在 v2 卡上會**原樣印出星號**。
    ⛔ 不是為了好看才改：印出裸星號會讓使用者以為畫面壞了。
    """
    return str(text).replace("**", "").replace("`", "")


def _v2_exit_phrase(where: str) -> str:
    """出口文案 → 卡面那一行的固定短語。**兩段查表，⛔ 不比字串開頭。**

    **第 1 段（主路）：`is` 比物件身分。** 客戶 2026-09-24 明示 ——
    改成比對字串開頭的話，文案改一個字就**默默**退回長句，⛔ 不會報錯（§1）。

    🔴 **第 2 段（2026-09-24 整頁卡化新增）：含 `NO_EXIT_MARKER` → 回
    `NO_EXIT_MARKER` 本身。⛔ 這不是「比字串開頭」的後門，理由三條**：
      ① **它比對的是一個為此而生的 SSOT 標記**，⛔ 不是任何一句文案的前綴。
         `tab_today.NO_EXIT_MARKER` 的 docstring 逐字寫明它存在的理由就是
         「守衛…**就是靠這個標記在每一張卡上確認**『本批沒有給出一個按了也沒用的
         指路』…各處自己造句 ＝ 守衛只能改用模糊比對」—— 也就是說，
         **用它做 containment 比對正是 SSOT 自己指定的用法**。
      ② **它回的是那個標記本身，⛔ 不是從長句裁下來的一段**
         —— 沒有半句話、沒有截尾號，與客戶退回的做法不同類。
      ③ **⛔ 非它不可**：本輪實跑窮舉的 22 個 `where` 裡有 15 個是
         `src/ui/tabs/tab_today.py` **函式體內的 f-string**（每次呼叫都是新物件），
         而那個檔在本輪的檔案邊界外 ⇒ 身分比對在結構上永遠對不上。
         沒有這一段，`statusbar.sheet` 等 15 種情形會被畫成**紅卡** ——
         把一張「未接線」的灰卡謊報成故障，那本身就是 §1 禁止的假警報。

    第 3 段：查不到 → `raise`（§1）：⛔ 不回一個「看起來合理」的短語（那是捏造），
    也⛔ 不偷偷退回截斷 —— 那正是客戶 2026-09-24 退回的做法，
    而退回之後畫面**看起來仍然正常**，沒有人會發現（§1 靜默失效）。
    """
    for _const, _phrase in V2_EXIT_PHRASES:
        if where is _const:
            return _phrase
    if NO_EXIT_MARKER in where:
        return NO_EXIT_MARKER
    raise KeyError(
        f"這段出口文案沒有登記短語（開頭 {where[:16]!r}…）—— "
        "新增 `EXIT_*` 常數時**必須**同步補一列 `V2_EXIT_PHRASES`。")


def _v2_why_phrase(why: str) -> str:
    """`Note.why` → 卡面那一列。**在子句邊界收尾，⛔ 不做字數截斷。**

    做法：短的**一個字都不動**；超出 `V2_WHY_MAX_CHARS` 時，依
    `V2_WHY_CLAUSE_SEPARATORS` 找**第一個能一刀進預算**的子句界線，切在那裡。

    🔴 **「一刀要能進預算」是硬條件，⛔ 不是寫法偏好**（實測踩到才加的）：
    容許「切了還是超出」的半吊子切法時，`why` 若長成
    `「{出處}（補充）拋出例外：{repr(e)}」`（＝ `_error_why()` 的形狀），
    `（` 那一刀會把**例外本身**整段砍掉，只留下出處前綴 ——
    而那正是這一態使用者唯一需要的東西。有了硬條件，那一刀因為
    「切了仍超出」而**不被採用**，整段原文留給契約層的夾子處理（見下段）。

    ⚠️ **一刀都找不到時本函式⛔ 不動手**：那時交給
    `v2_markup._fact_value_cell()` 的 `FACT_VALUE_MAX_CHARS` 收尾 ——
    它是**契約層自己**的夾子，而且會把**完整原文**掛在那一格的 `title=`。
    ⛔ 本檔不再疊第二個夾子（兩個夾子＝兩把尺，外面那把還會看不到裡面那把切過）。

    **本輪實跑（量測日 2026-09-24）**：33 張卡在
    `idle` / `empty` / `unwired` / `degraded` / `failed` / `live` 各態下逐一建出並產 HTML
    （批次窮舉 228 組 tile×狀態 ＋ 一次針對 `degraded`／`live` 的補跑 ——
     前者的側車沒帶 `state="ok"`，所以 16 盞燈那邊**跑不到** degraded，補跑才涵蓋到）。
    結果：灰態（`idle` / `empty` / `unwired` / `degraded`）**全部**一刀進預算，
    ⛔ 沒有一張走到契約層的夾子；**只有紅態（`failed`）走得到**
    —— 它的 `why` 是 `{出處}拋出例外：{repr(e)}`，長度無上限、
    而且**後半段才是重點**，本來就不該切。
    ⚠️ **這是本組單組窮舉的結論，未經第二組獨立驗**（`CLAUDE.md §-2` 規則 6）。
    """
    _text = why.strip()
    if len(_text) <= V2_WHY_MAX_CHARS:
        return _text                       # 短的一個字都不動
    for _sep in V2_WHY_CLAUSE_SEPARATORS:
        if _sep not in _text:
            continue
        _head = _text.split(_sep)[0].strip()
        # ⛔ 空的前半段不算一刀（例：`why` 本身就以分隔符開頭）——
        #    §1：回一個空字串等於把「為什麼沒有」這一段**靜默刪掉**。
        if _head and len(_head) <= V2_WHY_MAX_CHARS:
            return _head
    return _text


def v2_level_line(tile: Tile) -> tuple[str | None, tuple[tuple[str, str], ...], str]:
    """把三段 `Note` 攤成**三列 fact**，外加 hover 用的完整原文。

    Returns:
        `(判決語, 三要素的 fact 列, 要掛在 title= 的完整原文)`。
        · **live**（`Card.__post_init__` 只強制「非 live 必附 Note」⇒ live 沒有 Note）
          → `(signal_text, (), "")`：那一格放**判決語**（本頁是 `alloc.posture`），
          那正是 `.blk-lvl` 這個槽位在 v2 規格裡的本業。
        · **其餘** → `(None, ((現在, …), (為什麼, …), (去哪補, …)), 完整三段原文)`。

    🔴 **2026-09-24 客戶裁示：由「一行」改成「2~3 列」。有意識的政策變更，⛔ 不是漏刪。**
    · **舊做法的理由仍然成立**：一行 `「現況」· <出口短語>` 是**最省版位**的寫法，
      而當時整排只有三張 t1 結論卡，版位就是最稀缺的東西。
    · **被權衡掉的是它的產出**：三要素裡**只有兩個**上得了卡面
      （`now` 被引號包住當前綴、`where` 只剩短語），而「**為什麼沒有**」
      —— 三要素裡唯一回答「這是不是故障」的那一段 —— **完全只活在 hover**。
      滑鼠碰不到的裝置（手機 / 平板）等於看不到它。
    **現行**：三段各自一列，`why` 也上卡面。

    ⚠️ **客戶要的是「短」，⛔ 不是「把指路刪掉」**（鐵律 4 空狀態引導三要素）：
    壓縮之後**必須留下可操作的下一步**，所以第三列固定是 `<出口短語>`
    （短語由 `_v2_exit_phrase()` 依**出口常數的物件身分**查表，⛔ 不是截首句）。
    `why` 那一列走 `_v2_why_phrase()` 的**子句邊界**收尾，⛔ 不是截尾號。
    ⛔ 收尾也不是丟棄：收掉的只是**顯示**，原文一字不少地留在 `title=`。

    ⚠️ 三列**刻意不自帶標籤文字**（「去哪補：」之類）：標籤由 fact 列的 key 供給
    （`V2_NOW_FACT_KEY` / `V2_WHY_FACT_KEY` / `V2_GUIDE_FACT_KEY`）—— 自帶就會印兩次。
    """
    _note = tile.card.note
    if _note is None:
        return (v2_plain(tile.signal_text) or None), (), ""
    _now = v2_plain(_note.now)
    _why = v2_plain(_note.why)
    _where = v2_plain(_note.where)
    # 出口 → **固定短語**（⛔ 不截首句；見 `V2_EXIT_PHRASES` 的 2026-09-24 註）。
    # 🔴 比對餵的是 `_note.where`（**原物件**），⛔ 不是 `v2_plain()` 產的新字串。
    _rows = (
        (V2_NOW_FACT_KEY,   _now),
        (V2_WHY_FACT_KEY,   _v2_why_phrase(_why)),
        (V2_GUIDE_FACT_KEY, _v2_exit_phrase(_note.where)),
    )
    _full = f"{_now}｜為什麼沒有：{_why}｜去哪補：{_where}"
    return None, _rows, _full


def v2_card_html(tile: Tile) -> str:
    """一張 `Tile` → v2 卡面的 HTML。**所有文字都由 `card_html()` escape。**

    對映（照 v2 結構）：
      · 卡框 ← `V2_CARD_BLOCKS[card.key]` ⇒ t1 密度階
        （階由 `tier_for_block` 決定，本檔只驗不設；未登記的 key → `KeyError`，⛔ 不猜一個 block）
      · 標題 ← `card.label`
      · 徽章 ← `card.state` 經 `V2_STATE_VOCAB` → `v2_page.resolve_badge()`
      · 大字 ← `card.value`；**非 live 時整塊不渲染**
      · 灰字 ← `v2_level_line()` 的判決語（**只有 live 有**）
      · fact 列 ← **鐵律 4 三要素三列**（現在 / 為什麼 / 去哪補）**排在最前**，
        其後是 `tile.facts`（沿用既有的「門檻帶」「命中來源」…），
        **扣掉 `V2_HOVER_ONLY_FACTS` 登記要移進 hover 的那幾列**
        （目前只有卡③ `verdict.regime` 的「位階的出處」；⛔ 不是漏渲染，見該表）

    ⚠️ **三要素走 fact 列而不是 `.blk-lvl`，由契約自己說了算**：
    v2 對灰態／紅態一律**判決留白**（實測逐態確認），而會帶 `Note` 的正好就是那些態
    ⇒ 只掛 `level=` 的話，**在每一個需要它的狀態下都會整段消失**（⛔ §1 無聲丟棄）。
    故這裡**先問 `v2_page.card_level_text()`**：它願意畫「現在」那一段就走 `.blk-lvl`
    （其餘兩列照樣是 fact），它留白就三列全走 fact。
    ⛔ 兩條路互斥，⛔ 不會重複印；⛔ 本檔不自己判「這個狀態要不要留白」。
    ⚠️ 現況**實跑逐態確認**：Note-bearing 的七態契約全部留白 ⇒ 實際走的一律是
    「三列全 fact」那條。留著另一條**不是死碼**：契約哪天改成灰態也畫判決區，
    本檔一個字都不用改就會自動跟上（那正是「由契約說了算」的意思）。

    ⚠️ **大字區的留白規則由對面決定，本檔⛔ 不再寫一層判斷**：
    `card_html()` 內部走 `v2_page.card_value_text()` —— 灰態紅態一律留白
    （⛔ 無 `0`、⛔ 無「尚未評估」代打、⛔ 無上一輪殘值）。本檔只負責
    「非 live 的 `Card.value` 本來就是空字串 ⇒ 傳 `None`」這件**型別**上的事。

    ⚠️ **`title=` 裝兩種東西，⛔ 不是只有 `Note`**：`v2_level_line()` 壓掉的三段原文，
    ＋ `V2_HOVER_ONLY_FACTS` 從卡面移出來的那幾列（以 `｜` 相接，沿用 `_full` 的接法）。
    ⛔ 兩者都**一個字都沒刪**，只是換了露出的位置。

    ⚠️ `title=` 這個 hover 槽**掛在外層 div**，不是掛在灰字那一行上：
    `card_html()` 把每一段文字都 escape，**沒有**掛屬性的入口，而
    `src/ui_v2/**` 在本輪的檔案邊界外（⛔ 不改它去開一個入口）。
    外層 div **只有 `title` 一個屬性、零 CSS**，⛔ 不影響 `.blk*` 任何一條規則
    （那些選擇器都不看祖先）。
    """
    _card = tile.card
    # 未知狀態 → `KeyError`。⛔ 不 `.get()` 兜底（兜底＝挑一顆看起來合理的徽章）。
    _v2_state, _reason = V2_STATE_VOCAB[_card.state]
    _badge_n = v2_card_badge_n(_card)   # 2026-09-26：改走三頁共用的那一支（#11 登記制）
    _level, _guide_rows, _full = v2_level_line(tile)
    # 🔴 **移出卡面、只留 hover** 的那幾列（見 `V2_HOVER_ONLY_FACTS` 的判準與理由）。
    #    🔴 餵進 hover 的是 `tile.facts` 的**原字串**，⛔ 不過 `v2_plain()` ——
    #       那支會吃掉 `**` 與反引號，**也就是真的刪字**；而 hover 是
    #       「**完整原文**」那條通道（卡面才是被排版規則夾的那一條）。
    #    ⚠️ 只比對**標籤**⇒ 同一張卡的其餘 fact（例如 degraded 態的「現值」
    #       這個**觀測值**）照留卡面；表外的卡一行都沒變。
    _hover_keys = V2_HOVER_ONLY_FACTS.get(_card.key, frozenset())
    _moved = tuple(f"{_k}：{_v}" for _k, _v in tile.facts if _k in _hover_keys)
    if _hover_keys and not _moved:
        # §1 Fail Loud：登記了要搬、卻一列都沒搬到 ⇒ 那段**揭露兩邊都不見了**
        # （卡面已經不畫、hover 又沒接到）。⛔ 不靜靜地少一段 ——
        # `_render_one_v2()` 會把這個例外轉成**看得見的紅卡**，逼人回來看。
        raise KeyError(
            f"卡 {_card.key!r} 登記了要移進 hover 的 fact "
            f"{sorted(_hover_keys)!r}，但這張卡一列都沒有 —— 標籤改過了嗎？"
            "⛔ 不要把登記拿掉了事，那會讓揭露悄悄消失。")
    _facts = tuple((v2_plain(_k), v2_plain(_v))
                   for _k, _v in tile.facts if _k not in _hover_keys)
    if _guide_rows:
        # 🔴 三要素**排在最前** —— 使用者要先知道「這一格現在怎樣」，
        #    才輪得到「門檻帶」「命中來源」這些中繼資料。
        _head_text = _guide_rows[0][1]                  # ＝「現在」那一列的文字
        if v2_page.card_level_text(state=_v2_state, level=_head_text) is not None:
            _level = _head_text                  # 契約願意畫判決區 → 「現在」走 `.blk-lvl`
            _facts = tuple(_guide_rows[1:]) + _facts
        else:
            _facts = tuple(_guide_rows) + _facts          # 留白 → 三列全走 fact
    # 🔴 16 盞燈卡：三列出處說明移進「▸ 詳細」摺疊區（見 `V2_FOLDED_FACT_KEYS`）。
    _folded: tuple[tuple[str, str], ...] = ()
    if _card.key.startswith(V2_FOLD_CARD_PREFIX):
        _folded = tuple(r for r in _facts if r[0] in V2_FOLDED_FACT_KEYS)
        if not _folded:
            # §1 Fail Loud：「命中來源」每張燈卡都有（`build_indicator_tile` 無條件組）。
            # 一列都沒摺到 ＝ 標籤被改過 ⇒ 摺疊區會靜靜消失，⛔ 不吞。
            raise KeyError(
                f"卡 {_card.key!r} 應摺進「▸ 詳細」的 {sorted(V2_FOLDED_FACT_KEYS)!r}"
                " 一列都沒有 —— 標籤改過了嗎？")
        _facts = tuple(r for r in _facts if r[0] not in V2_FOLDED_FACT_KEYS)
    _html = v2_markup.card_html(
        block=V2_CARD_BLOCKS[_card.key],
        state=_v2_state,
        title=v2_plain(_card.label),
        value=(v2_plain(_card.value) or None),
        level=_level,
        badge_n=_badge_n,
        facts=_facts,
        folded_facts=_folded,
        # 🔴 id 由卡 key 決定 ⇒ 每輪 rerun 相同（展開狀態不被重設）；非燈卡不給。
        fold_id=(v2_markup.fold_dom_id(_card.key) if _folded else None),
    )
    # `Note` 原文 ＋ 移出卡面的那幾列，共用同一個 hover 槽（`｜` 沿用 `_full` 的接法）。
    _hover = "｜".join(_p for _p in (_full, *_moved) if _p)
    if not _hover:
        return _html
    # 🔴 2026-09-26 修：hover 內的換行一律轉成 `&#10;`（屬性內的換行字元參照，瀏覽器提示框照樣換行）。
    #    修前 margin 的 degraded `why` 含 "\n\n"，空行會**結束 CommonMark 的 HTML 區塊**，
    #    後半段被當成一般 Markdown 段落 ⇒ 卡片文字漏到卡外、尾巴多出一個 `">`。
    _title = html_escape(_hover, quote=True).replace("\n", "&#10;")
    return f'<div title="{_title}">{_html}</div>'


def _inject_v2_css() -> None:
    """吐出 v2 樣式表，**同一輪 script run 只吐一次**（旗標見 `SS_V2_CSS_DONE`）。

    ⛔ **不在本檔抄 CSS**：內容一律是 `v2_markup.page_css()` 的產出，本檔只負責
    包一層 `<style>` 丟給 `st.markdown` —— 與 `src/ui_v2/render.py` 的注入形態相同。
    `page_css()` 自己有 §1 落點：任何一個 token 拿不到就**整張不產出**，
    ⛔ 不會留下半套樣式表（那會畫出「看起來正常、其實是錯色」的卡）。
    """
    if st.session_state.get(SS_V2_CSS_DONE):
        return
    st.markdown(f"<style>{v2_markup.page_css(V2_CSS_MODE)}</style>",
                unsafe_allow_html=True)
    st.session_state[SS_V2_CSS_DONE] = True


def _render_one_v2(tile: Tile) -> None:
    """畫一張 v2 卡面，**並且不讓它把整頁畫到一半就死掉**。

    ⚠️ **錯誤隔離⛔ 不准降級**：這條路徑與 `_ui_kit.render_card_isolated()`
    做的是**同一件事** —— 炸了就**就地轉成一張看得見的紅卡 ＋ `repr(e)`**，
    其餘的卡照畫；log 也留一份。⛔ 不是 `except: pass`，也⛔ 不是
    「悄悄退回舊卡面」（那會讓 v2 壞掉這件事沒有人查得到 —— §-2：
    沒查證的宣稱比沒有宣稱更危險，靜默的降級同理）。

    ⚠️ 補救卡走既有的 `render_card_isolated()`：它是**第二層**防線
    （連補救卡都畫不出來時還有一道），而且那支就是本頁其餘卡片的同一支，
    ⛔ 不是為了這條路徑另寫一把尺。
    """
    try:
        _inject_v2_css()
        st.markdown(v2_card_html(tile), unsafe_allow_html=True)
        return
    except Exception as _e:  # noqa: BLE001 — 轉成看得見的紅卡，不吞
        # ⚠️ `except ... as _e` 的 `_e` 在區塊結束時會被 `del`，先把字串取出來
        #    （同 `_ui_kit.render_card_isolated()` 踩過的那個坑）。
        _err = repr(_e)
        print(f"[views/page_today] 卡 {tile.card.key!r} 的 v2 卡面畫不出來 "
              f"→ 轉紅卡：{_err}")
    # 卡的 label 不受 `Note` 那道 glyph 驗證管，先洗過再放進 `Note.now`，
    # 否則這張補救卡自己會再炸一次（§1：紅態要看得見，不是換一種炸法）。
    _label = scrub_state_glyphs(tile.card.label)[0] or tile.card.key
    render_card_isolated(
        Card(key=f"{tile.card.key}.v2_render_failed", label=_label,
             state=UI_FAILED,
             note=Note(now=f"{_label}　**這一格畫不出來**",
                       why=_error_why(SRC_V2_MARKUP, _err),
                       where=EXIT_FIX_CODE)),
        owner="views/page_today",
        error_why=lambda _err2: _error_why(SRC_RENDER, _err2),
        where=EXIT_FIX_CODE)


# ══════════════════════════════════════════════════════════════════
# 渲染（薄；所有判斷都在上面的純函式裡）
# ══════════════════════════════════════════════════════════════════
def _render_one(tile: Tile) -> None:
    """畫一張卡，**並且不讓它把整頁畫到一半就死掉**（【7】2026-09-07）。

    第一道防線在建構期（`Tile.__post_init__`），這裡是第二道。
    ⚠️ **2026-09-07 FE-9：第二道的本體已上移至共用層**
    `_ui_kit.render_card_isolated()` —— 頁 1 與頁 2 原本各有一份逐行同構的
    `_render_one()`（**兩把尺**，遲早漂移）。**邏輯一字未改**，
    本函式只剩「把本頁專屬的三樣東西綁上去」：
    log 前綴 / 出處文案（【8b】：出事的是哪一層只有本頁知道）/ 去哪補。

    ⚠️ **2026-09-23：`V2_CARD_KEYS` 裡的卡改走 v2 卡面；2026-09-24 客戶裁示批 1 起，
    葉1 ① 三張並排的卡全部在表內**（對照組已完成任務 —— 見 `V2_CARD_BLOCKS` 的更正註）。
    分派只看 `card.key`，**表外每一張走的路一行都沒有變**。
    兩條路徑**都**被包在「一張卡炸了不影響別張」的機制裡（見 `_render_one_v2`）。
    """
    if tile.card.key in V2_CARD_KEYS:
        _render_one_v2(tile)
        return
    render_card_isolated(
        tile.card, signal_text=tile.signal_text,
        signal_color=tile.signal_color, facts=tile.facts,
        owner="views/page_today",
        error_why=lambda _err: _error_why(SRC_RENDER, _err),
        where=EXIT_FIX_CODE)


def _render_tiles(tiles: Sequence[Tile], cols: int = MAX_COLS) -> None:
    """一組 `Tile` → 鐵律 1 的網格。"""
    for _chunk, _columns in grid(tiles, cols):
        for _tile, _col in zip(_chunk, _columns):
            with _col:
                _render_one(_tile)


#: 葉1 ③ 三欄摘要裡**接到指標危險度**的那一格（`tab_today.build_today_blocks()`
#: 的 key）。客戶 2026-09-16 裁示「**風險 ← danger（對得上，直接對映）**」；
#: 「動能」維持未接線（「exposure 不是動能，不搬」）、「位階」維持既有接線。
SUMMARY_RISK_KEY: str = "summary.risk"


def build_summary_tiles(cards: Sequence[Card], *,
                        danger: tuple[str, str] | None, danger_error: str,
                        danger_requested: bool,
                        danger_source: str = SRC_DANGER,
                        band_zh_color: Mapping[str, tuple[str, str]] | None = None,
                        l4_error: str = "") -> tuple[Tile, ...]:
    """葉1 ③ 三欄摘要 → `Tile`。**只換「風險」那一格，其餘照 `_tiles_of_cards()`。**

    · 「風險」格 ＝ `_danger_tile()`：與卡② `verdict.danger` **同一份讀數、同一支判態、
      同一段文案**（⛔ 不另寫一份）；key 與標題沿用 `tab_today` 那一格自己的
      （`card.key` / `card.label`），⛔ 不新造標題字串。
    · 位階 / 動能兩格原樣橋接（`Tile(card)`），⛔ 不碰。
    · **逐格獨立判態**（`UI_PAGE_TODAY.md` ④A「一格壞不染色另兩格」）：
      危險度的成敗只進「風險」這一格，另兩格的輸入裡根本沒有它。
    · `tab_today.py` 一個字都沒動（它的 `summary.risk` 仍是 staged 卡，舊分頁與
      `tests/test_p01_today_skeleton.py` 照舊）—— 接線只發生在本頁這一側。
    """
    return tuple(
        (_danger_tile(key=_c.key, label=_c.label,
                      danger=danger, danger_error=danger_error,
                      danger_requested=danger_requested,
                      danger_source=danger_source,
                      band_zh_color=band_zh_color, l4_error=l4_error)
         if _c.key == SUMMARY_RISK_KEY else Tile(_c))
        for _c in cards)


def _tiles_of_cards(cards: Sequence[Card]) -> tuple[Tile, ...]:
    """對面 `tab_today` 的 `Card` → 本頁的 `Tile`。**橋接，⛔ 不是複寫。**

    🔴 **2026-09-24 整頁卡化新增。** 頂部狀態列（3）、葉1 ③ 三欄摘要（3；📌 2026-09-26 起改走
    `build_summary_tiles()`：位階／動能兩格仍是這裡的 `Tile(card)`，「風險」格改接危險度）、
    ⑤⑥ 作戰室（2）共 8 張卡的**內容**由 `tab_today.build_status_bar_cards()` /
    `build_today_blocks()` 產出，型別是 `Card`；而 v2 卡面那條路
    （`_render_one()` → `V2_CARD_KEYS`）吃的是 `Tile`。

    ⚠️ **為什麼橋在這一側，⛔ 不是去改 `tab_today.py`**：那個檔是**舊分頁也在用**
    的契約與純函式的家（`tests/test_p01_today_skeleton.py` 守著），
    **本輪的檔案邊界明文不含它**。把 `Card` 包成 `Tile` 是**唯一**不動對面一個字
    的做法 —— 與 `Tile` 這個型別當初誕生的理由完全一樣（見 `Tile` 的 docstring）。

    ⚠️ **⛔ 不帶 `signal_text` / `facts`**：這 8 張卡本來走
    `_ui_kit.render_cards()`，那支就**沒有**燈號頻道與 fact 列這兩個入口
    （它的 docstring 逐字寫「無燈號頻道、無 facts 的簡單情形」）
    ⇒ 上游本來就沒有產這兩樣東西給它們。這裡憑空補一個**就是捏造**（§3.3）。
    三要素該露出的部分由 `v2_level_line()` 的三列 fact 負責，⛔ 不是這裡。
    """
    return tuple(Tile(_c) for _c in cards)


def refresh_is_clean(report: Any) -> bool:
    """這一輪算不算「乾乾淨淨跑完」。**跳過不算乾淨，只拿到半桶也不算。**

    抽成獨立純函式的理由（不是為了好看）：這個判準是本頁**唯一**決定
    `st.status` 收綠燈還是紅燈的地方，而它正是最容易被人「順手放寬」的一行
    （`ok` 就好了吧？部分成功也算成功吧？）。抽出來之後
    `tests/test_p01_macro_refresh.py` 的突變測試才拔得動它 ——
    改成 `return True` 必須當場轉紅。

    ⚠️ **`report.partials` 是 2026-09-09 加的第三個條件，不是贅字**：
    L3 刻意讓「某桶 4 檔只拿到 2 檔」**不**計入 `failures`
    （整桶標失敗會把「兩檔有值」講成「什麼都沒有」）。代價是 `ok` 會是 True
    —— 少了這一條，一輪只拿到半桶資料的更新會收**綠燈**。
    """
    return (bool(report.ok) and not report.skipped and not report.partials)


def refresh_status_state(report: Any) -> str:
    """`st.status(state=)` 的收尾值。只有兩種：`complete` / `error`。"""
    return "complete" if refresh_is_clean(report) else "error"


def _event_icon(result: Any) -> str:
    """進度列的圖示。**跳過不是成功、只拿到一半也不是** —— 四種結局四個圖示。

    ⚠️ **`partial` 一定要排在 `ok` 前面**：一個「4 檔只拿到 2 檔」的桶
    `ok` 是 True（它確實拿到東西了），先問 `ok` 就會給它一個 ✅ ——
    而那正是本批要修的說謊方式（部分成功畫成成功）。
    """
    if getattr(result, "skipped", False):
        return "⏭"
    if getattr(result, "partial", False):
        return "⚠️"
    return "✅" if getattr(result, "ok", False) else "❌"


def _run_refresh_now(mode: str) -> Any:
    """原地重抓 —— 逐來源顯示進度，回傳 `MacroRefreshReport`。

    ⚠️ **`st.status` 的收尾狀態只有兩種，判準寫死在這裡（T3-1 動工條件 ⑥）**：
    `complete` **只在「全部來源與步驟都成功、而且沒有任何一步被跳過」時給**，
    其餘一律 `error`。理由：部分成功的畫面**混合了新舊資料**，而使用者
    沒有任何方式分辨哪一格是今天的 —— 把它畫成綠色的「完成」，
    就是拿混合畫面當今天的結論（§1）。
    **跳過也算 `error`**：一個「本輪沒有廣度資料所以沒算旌旗」的輪次，
    畫面上的旌旗那盞燈仍是上一輪的值，這件事必須看得見。

    ⚠️ **不寫任何秒數上界**：`tab_macro` 的 spinner 文案有一個由
    `tests/test_p0a_key_alerts_and_spinner.py` 反解 code 逾時算出來的上界守衛；
    本頁的文案**不在那支守衛的射程內**，寫死秒數＝寫一個沒人在守的數字，
    它會在下一次有人調 timeout 時默默變成謊話。這裡只講**體感分級**
    （暖快取數秒 / 冷啟動較久）與**真的經過了幾秒**（`time.time()` 實測）。
    """
    from src.services import macro_refresh_service as _RS

    # 守衛 2/2（見 `UPDATE_MODE_TO_REFRESH_MODE` 的註解）：字面對不上就當場炸，
    # **不 fallback**。fallback 會讓使用者選了「強制重抓」卻跑成「正常更新」，
    # 而畫面上完全看不出來 —— 那比報錯糟得多（§1）。
    _valid = {_RS.MODE_WARM, _RS.MODE_FORCE}
    if mode not in _valid:
        raise RuntimeError(
            f"`page_today.UPDATE_MODE_TO_REFRESH_MODE` 給出的模式 {mode!r} "
            f"不在 `macro_refresh_service` 的 {sorted(_valid)} 裡 —— "
            "兩邊的模式字串漂開了，請同步（不要在這裡挑一個預設值）。")

    with st.status(REFRESH_RUNNING_LABEL, expanded=True) as _status:
        def _on_event(kind: str, result: Any) -> None:
            # 顯示名一律取 `result.label`（SSOT 在 L3），本頁不自己翻中文。
            _detail = getattr(result, "detail", "") or ""
            st.write(f"{_event_icon(result)} **{result.label}**"
                     + (f" — {_detail}" if _detail else ""))

        _report = _RS.refresh_macro_now(mode=mode, on_event=_on_event)
        _clean = refresh_is_clean(_report)
        _status.update(
            label=(f"{'✅' if _clean else '⚠️'} 更新結束 ——"
                   f" 實際耗時 {_report.elapsed_s:.1f} 秒、"
                   f"失敗 {len(_report.failures)} 項、"
                   f"本輪沒有條件跑 {len(_report.skipped)} 項"),
            state=refresh_status_state(_report),
            expanded=True)
    return _report


def _render_refresh_report(report: Any) -> None:
    """頁首：**上一次**按下更新的結果。留在畫面上直到下一次更新。

    §1：這一段的存在理由是「沒更新到的東西如果留白，看起來跟更新過一模一樣」。
    所以它**一定**會列出 `untouched`（本路徑摸不到的區塊），
    即使那一輪一切順利。

    🔴 **2026-09-24 客戶裁示：整段收進 `st.expander(..., expanded=False)`。**
    **⛔ 一個字都沒有刪 —— 只是預設收起來。** 這一段在展開後仍然一字不差。

    🔴 **但「真錯誤」留在收合區外面（客戶明示的那半句，也是 §1 的要求）**：
    `report.failures`（取不到的來源 / 跑不完的步驟）與 `report.empties`
    （沒報錯但一筆都沒有）這兩段 `st.error` **畫在 expander 之前**。
    把一個**真的失敗**藏進預設收合的區塊裡，使用者看不到故障 ——
    那是 `CLAUDE.md §1.A` 第 4 點那條「介面狀態嚴格分離」的**反向**失效：
    A-4 防的是「把沒載入畫成紅色（假警報）」，這裡防的是
    「**把真紅色藏起來（假平安）**」。兩者同樣是造假。

    ⚠️ **`partials` / `skipped` 的 `st.warning` 進收合區，但⛔ 沒有被藏起來**：
    它們的計數寫進 expander 的**標題**（見 `_label`）⇒ 不展開也看得到
    「這一輪有 N 項只拿到一半 / M 項跳過」。客戶那句話點名的是 `st.error`；
    黃字降一階、且在標題留計數，是本輪的判斷（⛔ 非客戶明示）。

    ⚠️ **內層那個 `st.expander("這一輪碰了哪些資料？…")` 原樣保留、⛔ 沒有攤平**：
    本輪實測 Streamlit 1.59.2 **允許巢狀 expander**（`AppTest` 跑 outer→inner
    無例外、兩層的 markdown 都收得到）。⛔ 不憑記憶假設它不行而去動那一段。
    """
    _clean = refresh_is_clean(report)
    # ── 真錯誤：留在收合區**外面**（見 docstring）──────────────────
    if report.failures:
        st.error(
            "**這一輪有取不到的來源 / 跑不完的步驟**：\n\n"
            + "\n".join(f"- ❌ {_f}" for _f in report.failures)
            + f"\n\n{REFRESH_FAILED_WHAT_NOW}", icon="❌")
    # ⚠️ 「回空」與「跑失敗」分開講（2026-09-09）：回空的那幾桶**沒有拋例外**，
    #    它們在上面那段裡只表現成一行稽核結論。使用者要知道的是**哪一塊**
    #    現在顯示的是上一輪的值 —— 那要逐桶列出來才看得到。
    if report.empties:
        st.error(
            "**這幾個來源這一輪回空**（沒有報錯，但一筆資料都沒有）：\n\n"
            + "\n".join(f"- ❌ {_e}" for _e in report.empties)
            + f"\n\n{REFRESH_FAILED_WHAT_NOW}", icon="🕳")

    # ── 其餘整段：預設收合。標題自帶「這一輪出了什麼事」的計數 ────────
    #    ⛔ 標題不得只寫「上一次更新的結果」—— 那會讓一個有 3 項跳過的更新
    #    看起來和乾淨跑完的一模一樣（§1：留白看起來就跟更新過一樣）。
    _counts = [
        f"{len(report.failures)} 項失敗" if report.failures else "",
        f"{len(report.empties)} 項回空" if report.empties else "",
        f"{len(report.partials)} 項只拿到一半" if report.partials else "",
        f"{len(report.skipped)} 項跳過" if report.skipped else "",
    ]
    _issues = "　·　".join(_c for _c in _counts if _c)
    _label = (
        f"{'✅' if _clean else '⚠️'} 上一次更新的結果"
        f"　·　{MODE_LABELS.get(_refresh_mode_label_key(report.mode), report.mode)}"
        f"　·　送出於 {report.started_at}"
        f"　·　實際耗時 {report.elapsed_s:.1f} 秒"
        + (f"　·　{_issues}" if _issues else ""))
    with st.expander(_label, expanded=False):
        if report.partials:
            st.warning(
                "**這幾個來源只拿到一部分**（拿到的是今天的，缺的那幾檔"
                "顯示的是上一輪的值）：\n\n"
                + "\n".join(f"- ⚠️ {_p}" for _p in report.partials), icon="⚠️")
        if report.skipped:
            st.warning(
                "**這一輪有步驟沒有條件跑**（跳過 ≠ 成功，也 ≠ 失敗）：\n\n"
                + "\n".join(f"- ⏭ {_s}" for _s in report.skipped), icon="⏭")
        if _clean:
            st.success(
                f"7 個來源**都真的拿到資料了**，全部步驟也都跑完（{report.started_at} 送出）。"
                "⚠️ 這句話**只涵蓋下面「有更新到」那一段列出的 key** —— "
                "本頁按鈕碰不到的區塊見下一段。", icon="✅")

        with st.expander("這一輪碰了哪些資料？（逐鍵列出）", expanded=False):
            st.markdown(
                "**有更新到（實測寫進 session 的 key）**：\n\n"
                + ("\n".join(f"- `{_k}`" for _k in report.written_keys)
                   or "- （這一輪一個 key 都沒寫成功）"))
            # ⚠️ 這一段是 2026-09-09 補的另一半：只列「有更新到」的話，
            #    一個宣告寫得到、這輪卻沒寫到的 key（旌旗 / 市場評估 / 6 源快照 …）
            #    會**兩份清單都不在** —— 使用者想確認「它更新了沒」，
            #    在畫面上找不到任何一句話回答他。
            if report.not_written_keys:
                st.markdown(
                    "**沒更新到（本頁按鈕寫得到、但這一輪沒有寫進去）**：\n\n"
                    + "\n".join(f"- `{_k}`" for _k in report.not_written_keys)
                    + "\n\n這幾格顯示的是**上一輪的值**；原因見上面的失敗 / 跳過清單。")
            if report.popped_keys:
                st.markdown("**刪除的 key**：\n\n"
                            + "\n".join(f"- `{_k}`" for _k in report.popped_keys))
            if report.cleared:
                st.markdown("**強制重抓清掉的快取**：\n\n"
                            + "\n".join(f"- {_c}" for _c in report.cleared))
            st.markdown(
                "\n**逐來源結果**（這一格只說「這個 job 有沒有以例外收場」）：\n\n"
                + "\n".join(
                    f"- {_event_icon(_r)} {_r.label}"
                    + (f" — {_r.detail}" if _r.detail else "")
                    for _r in tuple(report.sources) + tuple(report.steps)))
            # ⚠️ 上下兩格**不是重複**：上面是「有沒有炸」，下面是「真的收到什麼」。
            #    一個 job 可以不炸而回空 —— 那正是這一段存在的理由。
            st.markdown(
                "\n**逐來源實際收到的內容**（`N/M` ＝ 拿到幾項 / 要抓幾項）：\n\n"
                + ("\n".join(f"- {_event_icon(_c)} {_c.label} — {_c.detail}"
                             for _c in report.contents)
                   or "- （這一輪沒有做判空 —— 取數整條失敗，連 bundle 都沒有）"))

        st.markdown(UNTOUCHED_HEADING)
        st.caption(UNTOUCHED_WHY)
        for _b in report.untouched:
            st.markdown(
                f"- **{_b.label}**"
                + (f"（`{_b.session_key}`）" if _b.session_key else "")
                + f" —— {_b.why}。**寫得到它的是**：{_b.writer}")


def _refresh_mode_label_key(mode: str) -> str:
    """L3 的模式字串 → 本頁 radio 的選項 key（顯示名走 `MODE_LABELS` SSOT）。"""
    for _k, _v in UPDATE_MODE_TO_REFRESH_MODE.items():
        if _v == mode:
            return _k
    return mode


def _render_update_form(session: Mapping[str, Any]) -> None:
    """葉1 ② 操作列 —— 鐵律 2 的落點，**兼原地重抓的觸發點**。

    ⚠️ **2026-09-09 T3-1：submit 從「只記模式」改成「記模式 ＋ 立刻重抓」。**
    客戶裁決：頁1 的按鈕要在**本頁原地**觸發台股今日資料重抓並即時刷新，
    不跳轉回舊分頁。流程：`st.status` 逐來源顯示 → 報告落 session →
    `st.rerun()` → 下一輪由 `_render_refresh_report()` 在頁首畫出來。

    ⚠️ **為什麼報告要繞一圈 session 再 rerun，而不是就地印**：
    這一輪的每一張卡都是在 submit **之前**就已經算好的（`render_page_today()`
    開頭就把 `_readout` / `_alloc` / `_regime` 讀完了）。不 rerun 的話，
    畫面上會是「新的報告 ＋ 舊的 16 盞燈」—— 那正是本頁最不該做的事。
    """
    _submitted = single_submit_form(
        FORM_KEY,
        submit_label=ia_nav.action_label(ia_nav.ACTION_UPDATE_TODAY),
        radio_label="更新模式",
        options=tuple(MODE_LABELS),
        option_labels=MODE_LABELS,
        widget_key=SS_MODE_WIDGET,
        applied_key=SS_APPLIED_MODE,
    )
    # 下游**只讀已套用值**（鐵律 2），且讀取器是對面的 SSOT。
    # submit 那一輪 `single_submit_form` 已經把值寫進去了，所以這裡讀得到。
    _mode = applied_update_mode(session)
    st.caption(
        f"已套用的更新模式：**{MODE_LABELS[_mode] if _mode else '（尚未送出過）'}**"
        f"　·　⚠️ {PAGE_REFRESH_SCOPE_WHY}。{REFRESH_SPEED_HINT}")

    if not _submitted:
        return
    if _mode not in UPDATE_MODE_TO_REFRESH_MODE:
        # §1：對不上就出聲，不要拿一個預設模式假裝使用者選了它。
        st.error(f"未知的更新模式 `{_mode!r}` —— 本頁不替你挑一個模式跑。", icon="❌")
        return
    st.session_state[SS_REFRESH_REPORT] = _run_refresh_now(
        UPDATE_MODE_TO_REFRESH_MODE[_mode])
    st.rerun()


def render_page_today() -> None:
    """🚦 今天（IA v2 第 1 頁）。~~**本批無 production caller，刻意如此。**~~

    ⚠️ **2026-09-08 FE-36 事實更正（刪除線有意識保留，不是漏刪）**：
    那句在本檔剛落地那一批為真，之後接線的批次沒有回頭改它 ——
    **是 `b5bdb36`（側欄 radio 改動）之前就存在的漂移，不是這次弄壞的。**
    **現行**：`app.py::_ia_view_today()` 於側欄「🆕 新版戰情室（試用中）」radio
    選到本頁時 late import 並呼叫本函式。理由與守衛見檔頭 FE-36 那段。
    """
    _session = st.session_state
    # ⚠️ 每一輪開頭清掉 v2 樣式表旗標 —— 見 `SS_V2_CSS_DONE`：Streamlit 每輪重建
    #    元素樹，做成「一個 session 只注入一次」的話第二輪起樣式表就不見了，
    #    而所有守衛仍然是綠的。旗標只負責「同一輪裡不要吐第二次」。
    _session.pop(SS_V2_CSS_DONE, None)
    # ⚠️ **刻意在這裡就吐掉，而不是留給第一張 v2 卡**：那張卡畫在 `st.columns` 的
    #    第一欄裡，`<style>` 雖然不顯示，Streamlit 仍會替它包一層 `stMarkdown` 容器
    #    ⇒ 第一欄會比另外兩欄多一塊垂直間距，三張並排的卡就對不齊了。
    #    `_render_one_v2()` 裡那一次呼叫保留當保險（旗標已設 ⇒ 它會直接 return），
    #    這樣就算有別的進入點單獨畫那張卡，也不會出現沒有樣式的裸 HTML。
    _inject_v2_css()
    _readout = load_macro_readout(_session)
    _band_label, _thr_text, _band_zh, _l4_err = _load_l4_labels()
    _alloc, _alloc_err = _load_allocation()
    _regime, _regime_err = _load_regime()
    # ⚠️【1】兩顆燈**各自一支 loader**：危險度不吃 regime、位階不吃 16 盞燈。
    #    誰失敗只影響誰那一張卡（修前是 regime 掛掉就連坐危險度）。
    _danger, _danger_err, _danger_src = _load_danger(_readout)
    _alerts, _scanned, _alerts_err = _load_key_alerts(_session)

    _tiles_by_bucket = build_indicator_tiles(
        _readout, band_label=_band_label, thr_text=_thr_text, l4_error=_l4_err,
        directions=_load_lamp_directions(_session))
    _cov = coverage(_tiles_by_bucket)
    # 線框七塊全部照算（`build_today_blocks` 是純函式），葉1 ③ 與 ⑤⑥ 各取所需。
    _blocks = {_b.key: _b for _b in build_today_blocks(
        macro_state=_regime, macro_error=_regime_err or None)}

    st.markdown(f"## {ia_nav.page_label(ia_nav.PAGE_TODAY)}")
    st.caption("回答「今天能不能出手、出手到幾成」。")

    # ── 頁首：上一次原地重抓的結果（T3-1）──────────────────────
    # 它**留在畫面上**直到下一次更新 —— 因為「這一輪沒有更新到哪幾塊」
    # 描述的正是**現在畫面上這些卡**的狀態，不是一則過眼即忘的通知（§1）。
    _report = _session.get(SS_REFRESH_REPORT)
    if _report is not None:
        try:
            _render_refresh_report(_report)
        except Exception as _e:  # noqa: BLE001
            # ⚠️ 這一道**不是**泛用的 try/except（§1 禁止吞例外），它擋的是一個
            # 具體且真實的情境：Streamlit Cloud 會在檔案變更時**熱重載程式碼但
            # 不清 session**。上一版存進去的 `MacroRefreshReport` 因此可能少了
            # 新版讀的欄位 → `AttributeError` 從頁首炸穿 ⇒ **整頁空白**
            # （檔頭那條 ⛔ 講的正是這種故障半徑）。
            # 處置是**把它變成看得見的紅字 + 丟掉那份過期報告**，不是靜默略過：
            # 例外原文照印，下一次按更新就會寫入新格式的報告。
            print(f"[views/page_today] 舊格式的更新報告畫不出來：{_e!r}")
            st.session_state.pop(SS_REFRESH_REPORT, None)
            st.error(
                "上一次更新的報告畫不出來（多半是程式更新後 session 裡留著舊格式的"
                f"報告）。**它已經被清掉**，請重新按一次更新。原始例外：`{_e!r}`",
                icon="⚠️")

    # ── （跨頁）頂部狀態列：常駐一條，位在兩葉之上 ───────────────────
    # 三張卡完全復用 `tab_today.build_status_bar_cards()`（交易日 / 總經 /
    # Sheet 綁定），本檔一個字都不重寫。
    # 🔴 2026-09-24 整頁卡化：三張狀態卡改走 v2 卡面（`_tiles_of_cards()` 橋接）。
    #    **內容仍然完全復用 `tab_today.build_status_bar_cards()`，本檔一個字都不重寫**；
    #    換的只有畫它的那一層（`render_cards` → `_render_tiles` → v2 卡面）。
    _render_tiles(_tiles_of_cards(
        build_status_bar_cards(_regime, error=_regime_err or None)))

    _leaf1, _leaf2 = st.tabs([
        ia_nav.SECTION_LABELS[LEAF_CONCLUSION],
        ia_nav.SECTION_LABELS[LEAF_DETAIL],
    ])

    with _leaf1:
        section_header("① 今日結論", _cov.text())
        st.caption(PARALLEL_DISCLOSURE)
        _render_tiles(build_verdict_tiles(
            alloc=_alloc, alloc_error=_alloc_err,
            danger=_danger, danger_error=_danger_err,
            danger_requested=_readout.requested, danger_source=_danger_src,
            regime=_regime, regime_error=_regime_err,
            band_zh_color=_band_zh, l4_error=_l4_err))

        section_header("② 操作列")
        _render_update_form(_session)

        # ③ **線框原文的三欄摘要（位階 / 動能 / 風險）**，直接取用
        #    `tab_today.build_today_blocks()` 的 `today.summary` block ——
        #    位階已接線、動能誠實標未接線（風險格見下方 2026-09-26 註）。**零新增取數**：那個 block
        #    本來每一輪就已經算出來了（修前算完丟掉，改成五桶摘要且零揭露）。
        _summary = _blocks["today.summary"]
        section_header(_summary.title, LEAF1_SUMMARY_NOTE)
        # 🔴 2026-09-24 整頁卡化：三欄摘要改走 v2 卡面（同上，內容一字未改）。
        # 📌 2026-09-26：「風險」格接上指標危險度（客戶裁示「風險 ← danger」）——
        #    讀數就是上面卡② 用的同一個 `_danger`，**零新增取數**。
        _render_tiles(build_summary_tiles(
            _summary.cards,
            danger=_danger, danger_error=_danger_err,
            danger_requested=_readout.requested, danger_source=_danger_src,
            band_zh_color=_band_zh, l4_error=_l4_err))

        section_header("④ 今日關鍵橫幅")
        _render_tiles((build_key_alert_tile(
            _alerts, requested=_readout.requested,
            threshold_scanned=_scanned, error=_alerts_err,
            band_zh_color=_band_zh),), cols=1)

        # ⑤⑥ 尚未接線的區塊：整段復用 `tab_today.build_today_blocks()`，
        #    連「為什麼未接線」的文案都走對面的 SSOT 常數。
        _warroom = _blocks["today.warroom"]
        section_header(_warroom.title)
        # 🔴 2026-09-24 整頁卡化：⑤⑥ 兩張卡改走 v2 卡面（同上，內容一字未改）。
        _render_tiles(_tiles_of_cards(_warroom.cards))

    with _leaf2:
        # 五桶摘要（原葉1 ③）搬到這裡 —— 葉2 本來就是五桶明細，這才是它的歸屬。
        section_header("五桶摘要", BUCKET_SUMMARY_MOVED_NOTE)
        _render_tiles(build_bucket_tiles(_readout))

        section_header("指標明細 — 五桶逐段", _cov.text())
        st.caption(SEGMENT_COVERAGE_NOTE)
        st.caption(AS_OF_NOT_IN_CONTRACT)
        if _l4_err:
            # §1：載不進來就講出來，不要讓那兩欄默默空白。
            st.warning(f"{L4_LABEL_UNAVAILABLE}`{_l4_err}`", icon="⚠️")
        if not _readout.requested:
            render_note(Note(
                now=f"**{_cov.total} 盞燈全部尚未載入**（還沒有人去取這份資料）",
                why=("冷啟動 session：上游一個總經 key 都還沒寫進來 —— "
                     "這是「還沒叫」，不是「叫了沒回」，"
                     "也**不是**「掃過了沒問題」"),
                where=EXIT_RETRY_HERE))
        for _b in BUCKET_ORDER:
            _meta = BUCKET_META[_b]
            section_header(f"{_meta['emoji']} {_meta['title']}",
                           str(_meta["sub"]))
            _render_tiles(_tiles_by_bucket.get(_b, ()))
