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

**本檔沒有 production caller**（`app.py` 本批不接線）。舊分頁不動、不下架。

═══ 四態的唯一真相源 ═══════════════════════════════════════════════════
L0 `shared/ui_state.py` 七態，是線框四態 ＋ 正常態的超集：

    灰態（無資料）→ `UI_EMPTY`（已請求但沒回值）／`UI_IDLE`（**還沒有人叫過**）
    未接線        → `UI_UNWIRED`   （`DangerSpec.wired=False`）
    已失準        → `UI_DEGRADED`  （`DangerSpec.discriminative=False`）
    紅態（真故障）→ `UI_FAILED`    （呼叫拋例外 / 來源回錯）
    正常          → `UI_LIVE`

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
    產出的 `today.summary` block（位階已接線、動能與風險誠實標未接線）。
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
本檔 module level 就 `from src.ui.tabs.tab_today import ...`，而
`src/ui/tabs/__init__.py` 是一個 **eager barrel**（檔頭自陳「即時轉發，
不是延遲載入」），一路把 152 個 `src.*` 模組 ＋ pandas ＋ plotly 全拉進來
（實測值，量測日 2026-09-07）—— 其中就包含
`src.services.section_inputs` 與 `src.compute.macro.macro_helpers`。
所以那兩個模組**若在 import 階段就壞掉**，`import page_today` 自己會先
`ImportError`，`render_page_today()` 根本不會被呼叫到，畫面上
**一個 markdown 都不會有**（紅隊實測 `n_markdown=0`）。

**為什麼不改成 lazy 而是把宣稱改誠實**（§-2：沒查證的宣稱比沒有宣稱更危險）：
真正的根因是那個 eager barrel，而它在 `src/ui/tabs/`，**不在本批的檔案邊界內**。
在邊界內能做的只有「把 `tab_today` 的每一個符號都推進函式體」——
但第一次呼叫時 barrel 照樣會被執行，失敗只是**換個時間點**發生，
而且 module-level 的契約自檢（`_assert_applied_key_matches_reader()`，
一道刻意的 fail loud）會被迫拿掉或延後，**淨值是負的**。
故此處只把宣稱改成可驗證的版本，不假裝擋得住。

═══ 分層（CLAUDE.md §8.2）═════════════════════════════════════════════
L5。取數走 L3（`section_inputs` / `allocation_service`），計算走 L2
（`macro_helpers` / `daily_key_alerts`），門檻走 L0（`macro_buckets`），
渲染走 L4（`macro_v2_cards` 的標籤函式）與同層 kit（`_ui_kit`）。
**零 L1 import、零 `requests` / `yfinance` / FinMind、零檔案讀寫、
零 `@st.cache_data` / `@st.cache_resource`。**
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

import streamlit as st

from shared import ia_nav
# L0 SSOT：regime → 中文。`tab_macro_v2.parallel_verdict()` 讀的也是這一份，
# 本檔直接讀源頭**不是**第二把尺（見檔頭陷阱 3 的 2026-09-07 修註）。
from shared.allocation_decision import REGIME_LABEL
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
    UI_FAILED,
    UI_IDLE,
    UI_LIVE,
    UI_UNWIRED,
    classify_ui_state,
)
from src.ui.tabs.tab_today import (
    CONTRACT_NO_EXIT_WHERE,
    LEAF_CONCLUSION,
    LEAF_DETAIL,
    MODE_LABELS,
    MODE_WARM,
    NO_EXIT_MARKER,
    Card,
    Note,
    applied_update_mode,
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
    render_card,
    render_cards,
    render_note,
    section_header,
    single_submit_form,
)

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

#: 本頁 radio 的 widget key —— **當下值**，下游禁止讀（鐵律 2）。
#: 刻意與 `tab_today` 的 widget key **不同**：兩頁若同時掛上，
#: 相同的 widget key 會直接撞成 Streamlit 的 DuplicateWidgetID。
#: 而**已套用值刻意共用** —— 它們是同一頁的兩種畫法，模式本來就該一致。
SS_MODE_WIDGET: str = "p01v_update_mode_widget"

#: 本頁 form 的 key（同上，與 `tab_today` 的 `form_today` 分開）。
FORM_KEY: str = "form_today_view"


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
#: 本頁**只讀 session、不取數**這件事的唯一寫法。
#:
#: 為什麼要反覆強調：本頁的 submit 只記下更新模式，**不觸發任何取數**。
#: 寫成「按一下就會有」是**假指路** —— 它承諾了這一批交付不出來的結果
#: （`tab_today` 的紅隊在 `CONTRACT_NO_EXIT_WHERE` 上抓到過同一個病）。
PAGE_READ_ONLY_WHY: str = (
    "本頁**只讀** session 裡既有的總經輸入、**自己不取數**："
    "五桶的原始資料由既有的總經分頁（或每日排程）寫進 session，本頁再讀它")

#: 「這一格現在沒有你可以執行的出口」＋ 指到診斷分區。
#: `NO_EXIT_MARKER` 與分區名都是 SSOT，本檔不手抄任何分頁名或按鈕名。
NO_LOAD_EXIT_WHERE: str = (
    f"{NO_EXIT_MARKER} —— {PAGE_READ_ONLY_WHY}；"
    f"{ia_nav.where_to_press(ia_nav.ACTION_UPDATE_TODAY)}只會記下你選的更新模式，"
    f"不會讓這一格離開現在的狀態。要看這一源到底怎麼了，去 "
    f"{ia_nav.where_to_find(ia_nav.SECTION_WHY_DATA_HEALTH)}")

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
    "位階已接上 L3 契約；動能與風險**誠實標未接線**，不拿別的東西頂替。")

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
          ⛔ **擋不住的是 module-level 的 import 失敗**：本檔 module level
          經 `tab_today` → `src/ui/tabs/__init__.py`（eager barrel）就已經把
          這兩個模組拉進來了，它們若在 import 階段壞掉，`page_today` 自己
          會先 `ImportError`，**整頁空白**（實測 `n_markdown=0`）。
          下面這個 `try` 只是**同一個模組的第二次 import**（已在
          `sys.modules` 裡），因此它**只保護呼叫期**。完整說明見檔頭
          「這個檔擋得住什麼、擋不住什麼」。
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
                         l4_error: str = "") -> Tile:
    """一盞燈 → 一張卡。**燈號與門檻全部走 L0 / L4 SSOT，本檔不判燈。**

    Args:
        key: `DangerSpec.key`。
        rec: readiness 側車的那一筆（可能是空 dict）。
        requested / error: 見 `indicator_state`。
        band_label: L4 `macro_v2_cards.band_meta` 或 None（載入失敗）。
        thr_text: L4 `macro_v2_cards.threshold_text` 或 None（載入失敗）。
        l4_error: L4 載入失敗時的 `repr(e)`。

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

    if _state == UI_LIVE:
        return Tile(Card(key=f"detail.{key}", label=_spec.label,
                         state=_state, value=_shown),
                    signal_text=_signal_text, signal_color=_signal_color,
                    facts=tuple(_facts))

    # 非 live 一律要三要素。`Card` 規定非 live 不得帶 `value`，
    # 所以**已失準**那一態的現值改掛在 facts（它是有值的，不能藏起來）。
    if _state == UI_DEGRADED:
        _facts.insert(0, ("現值", _shown or "—"))
        _note = Note(
            now=f"{_spec.label}　**有值，但門檻已失去判別力**",
            # §1 + 規格：理由直接讀 SSOT，不自己寫一份。
            why=(_spec.degraded_reason
                 or "SSOT 標了 `discriminative=False` 卻沒填 `degraded_reason`"
                    " —— 這是程式要修的訊號"),
            where=("這一態不用你做什麼 —— 別看它有沒有過線，"
                   "改看它相對自身近年區間的變化方向；"
                   f"門檻本身要不要改屬另案，見 {ia_nav.where_to_find(ia_nav.SECTION_WHY_DATA_HEALTH)}"),
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
                     where=NO_LOAD_EXIT_WHERE)
    elif _state == UI_FAILED:
        # 側車自己判出的紅（量綱漂移 / spec 沒有取值路徑）—— 不是本頁拋的例外。
        _clean, _n = scrub_state_glyphs(_miss_why(rec))
        _why = _clean + ("（原文的狀態符號已移除，"
                         "以免和這張卡自己的狀態燈變成兩個矛盾的說法）" if _n else "")
        _note = Note(now=f"{_spec.label}　**這盞燈壞了，不是沒資料**", why=_why,
                     where=NO_LOAD_EXIT_WHERE)
    else:
        _clean, _n = scrub_state_glyphs(_miss_why(rec))
        _why = _clean + ("（原文的狀態符號已移除，"
                         "以免和這張卡自己的狀態燈變成兩個矛盾的說法）" if _n else "")
        _note = Note(now=f"{_spec.label}　無數值", why=_why,
                     where=NO_LOAD_EXIT_WHERE)
    # 燈號頻道跟著卡走：**`degraded` 是「有值、燈也亮」**，
    # 把它的燈藏起來等於把它降級成灰態，那是另一種說謊。
    # 其餘非 live 的狀態在上面根本沒有取到 `signal_text`（維持空字串）。
    return Tile(Card(key=f"detail.{key}", label=_spec.label, state=_state,
                     note=_note),
                signal_text=_signal_text, signal_color=_signal_color,
                facts=tuple(_facts))


def build_indicator_tiles(readout: MacroReadout, *,
                          band_label: Any = None, thr_text: Any = None,
                          l4_error: str = "") -> dict[str, list[Tile]]:
    """16 盞燈 → 依 `BUCKET_ORDER` 分桶的卡片。**分母恆為 16。**

    迭代來源是 L0 `BUCKET_DANGER_SPECS` 而**不是**側車的 key ——
    側車在冷啟動 / 取數失敗時是空的，照它迭代會讓整個葉2 消失，
    而「什麼都不畫」是最糟的一種說謊（線框：未評估 ≠ 沒事）。
    """
    _out: dict[str, list[Tile]] = {_b: [] for _b in BUCKET_ORDER}
    for _spec in BUCKET_DANGER_SPECS:
        _rec = readout.readiness.get(_spec.key) or {}
        _out.setdefault(_spec.bucket, []).append(
            build_indicator_tile(_spec.key, _rec,
                                 requested=readout.requested,
                                 error=readout.error,
                                 band_label=band_label, thr_text=thr_text,
                                 l4_error=l4_error))
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
                         where=NO_LOAD_EXIT_WHERE)
        elif readout.requested:
            _note = Note(
                now=f"{_name}　**全部無資料**",
                why=("這一桶旗下的燈本輪一盞都沒有取到值 —— "
                     "上游 session 裡有容器、但欄位是空的。"
                     "**本站不以缺值推導「中性」**，所以它是灰的不是綠的"),
                where=NO_LOAD_EXIT_WHERE)
        else:
            _note = Note(
                now=f"{_name}　**尚未載入**（還沒有人去取這份資料）",
                why=("冷啟動 session：上游一個總經 key 都還沒寫進來，"
                     "本頁因此連算都沒有算 —— 這是「還沒叫」，不是「叫了沒回」"),
                where=NO_LOAD_EXIT_WHERE)
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
                     where=NO_LOAD_EXIT_WHERE)
    elif _state == UI_DEGRADED:
        _note = Note(
            now=f"{_label}　已列出異常，但**本列僅含急變層**",
            why=("門檻層本輪未評估（`macro_alerts` 為 `None` 或 `[]`）—— "
                 "紅 / 黃條照顯示，但它沒有涵蓋門檻層，"
                 "**不能把它讀成「門檻都沒踩到」**"),
            where=NO_LOAD_EXIT_WHERE)
    elif requested:
        _note = Note(
            now=f"{_label}　**門檻掃描尚未完成** —— **未評估 ≠ 無異常**",
            why=("門檻層這輪沒跑到（`None`），或跑了但 snapshot 全是 `None`（`[]`）"
                 "—— 兩者都不是「沒事」，急變層也沒有東西可比"),
            where=NO_LOAD_EXIT_WHERE)
    else:
        _note = Note(
            now=f"{_label}　尚未載入 —— **未評估 ≠ 無異常**",
            why="冷啟動 session：總經指標一項都還沒寫進來，沒有東西可以掃",
            where=NO_LOAD_EXIT_WHERE)
    # degraded 是「**有值**、燈也亮，只是判讀不完整」 → 燈要照出。
    # 其餘灰態 / 紅態沒有評估結果，燈號頻道一律留白（未評估 ≠ 綠）。
    _sig = (_sig_zh, _sig_hex) if _state == UI_DEGRADED else ("", "")
    return Tile(Card(key="key_banner.alerts", label=_label, state=_state,
                     note=_note),
                signal_text=_sig[0], signal_color=_sig[1], facts=_facts)


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

    # ① 能不能出手 / 出手到幾成 —— 全站唯一出處 `get_allocation()`。
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
                      where=NO_LOAD_EXIT_WHERE))))

    # ② 指標危險度（16 盞燈的 worst-of，**不含多空方向**）。
    #    ⚠️ 這一張**完全不看 regime**；regime 掛掉時它照樣要算得出來。
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
        _tiles.append(Tile(
            Card(key="verdict.danger", label="指標危險度（不含多空方向）",
                 state=_danger_state, value=str(danger[1])),
            signal_text=_zh, signal_color=_hex, facts=_dfacts))
    else:
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
        _tiles.append(Tile(Card(
            key="verdict.danger", label="指標危險度（不含多空方向）",
            state=_danger_state,
            note=Note(now="**指標危險度：尚未載入**", why=_why,
                      where=NO_LOAD_EXIT_WHERE))))

    # ③ 市場位階（全站唯一出處 `get_macro_regime()`）。
    #    狀態沿用 `tab_today.classify_macro_contract()` —— 那支函式讀的是契約
    #    自己的 `source` 分支標記（上游帶下來的旗標），不是拿資料反推。
    #    ⚠️ 這一張**完全不看 16 盞燈**（修前寫 `and parallel is not None`，
    #       危險度那半組不出來就會把一個 live 的位階畫成「尚未評估」）。
    _reg = dict(regime or {})
    if _regime_state == UI_LIVE:
        # `REGIME_LABEL` 是 L0 SSOT（`parallel_verdict()` 讀的也是這一份）。
        # live ⇒ `is_loaded=True`，所以這裡不可能對一個未評估的契約印出方向
        # （`get_macro_state` 實測：`source == 'unloaded'` ⟺ `is_loaded=False`）。
        _rk = str(_reg.get("regime") or "unknown").strip().lower()
        _tiles.append(Tile(
            Card(key="verdict.regime", label="市場位階（全站唯一出處）",
                 state=_regime_state,
                 value=REGIME_LABEL.get(_rk, REGIME_LABEL["unknown"])),
            signal_text=REGIME_LABEL.get(_rk, REGIME_LABEL["unknown"]),
            facts=(("生效分支", str(_reg.get("source") or "—")),)))
    else:
        _tiles.append(Tile(Card(
            key="verdict.regime", label="市場位階（全站唯一出處）",
            state=_regime_state,
            note=Note(
                now="**市場位階：尚未評估**",
                # 這一張**真的**是 L3 canonical 契約 → 文案原本就對，
                # 續用對面的 SSOT `upstream_error_why()`（見 `_error_why` 註）。
                why=(upstream_error_why(regime_error) if regime_error else
                     "L3 canonical 契約四條來源本輪皆無值 → 回 `unknown`，"
                     "**不是** `neutral`；本站不以缺值推導「中性」"),
                where=(CONTRACT_NO_EXIT_WHERE if not regime_error
                       else NO_LOAD_EXIT_WHERE)))))
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
# 渲染（薄；所有判斷都在上面的純函式裡）
# ══════════════════════════════════════════════════════════════════
def _render_one(tile: Tile) -> None:
    """畫一張卡，**並且不讓它把整頁畫到一半就死掉**（【7】2026-09-07）。

    第一道防線在建構期（`Tile.__post_init__`），這裡是第二道：
    渲染期若仍有東西炸（例如 L0 給了一個未知狀態名 → `state_meta()`
    fail loud），把它**就地轉成一張紅卡 ＋ `repr(e)`**，其餘的卡照畫。

    ⚠️ **不是 `except: pass`**：例外被轉成一個看得見的紅態並附原文，
    log 也留一份。§1 要的是「紅態看得見」——
    半截死頁（上半頁在、下半頁全沒了、畫面上沒有任何一句解釋）
    比一張紅卡危險得多，因為使用者根本不知道有東西不見了。
    """
    try:
        render_card(tile.card, signal_text=tile.signal_text,
                    signal_color=tile.signal_color, facts=tile.facts)
        return
    except Exception as _e:  # noqa: BLE001 — 轉成看得見的紅卡，不吞
        # ⚠️ `except ... as _e` 的 `_e` 在區塊結束時會被 `del` 掉，
        #    所以在區塊內就把字串取出來（不然下面會是 NameError）。
        _err = repr(_e)
        print(f"[views/page_today] 卡 {tile.card.key!r} 渲染失敗 → 轉紅卡：{_err}")
    # 卡的 label 本身不受 `Note` 那道 glyph 驗證管，先洗過再放進 `Note.now`，
    # 否則這張補救卡自己會再炸一次（§1：紅態要看得見，不是換一種炸法）。
    _label = scrub_state_glyphs(tile.card.label)[0] or tile.card.key
    render_card(Card(
        key=f"{tile.card.key}.render_failed", label=_label, state=UI_FAILED,
        note=Note(now=f"{_label}　**這一格畫不出來**",
                  why=_error_why(SRC_RENDER, _err),
                  where=NO_LOAD_EXIT_WHERE)))


def _render_tiles(tiles: Sequence[Tile], cols: int = MAX_COLS) -> None:
    """一組 `Tile` → 鐵律 1 的網格。"""
    for _chunk, _columns in grid(tiles, cols):
        for _tile, _col in zip(_chunk, _columns):
            with _col:
                _render_one(_tile)


def _render_update_form(session: Mapping[str, Any]) -> None:
    """葉1 ② 操作列 —— 鐵律 2 的落點。"""
    single_submit_form(
        FORM_KEY,
        submit_label=ia_nav.action_label(ia_nav.ACTION_UPDATE_TODAY),
        radio_label="更新模式",
        options=tuple(MODE_LABELS),
        option_labels=MODE_LABELS,
        widget_key=SS_MODE_WIDGET,
        applied_key=SS_APPLIED_MODE,
    )
    # 下游**只讀已套用值**（鐵律 2），且讀取器是對面的 SSOT。
    _mode = applied_update_mode(session)
    st.caption(
        f"已套用的更新模式：**{MODE_LABELS[_mode] if _mode else '（尚未送出過）'}**"
        f"　·　⚠️ {PAGE_READ_ONLY_WHY} —— 按下它會記住你選的模式，"
        "**但不會去抓資料**；標「未接線」「尚未載入」的區塊不會因此改變。"
        "這不是故障，是本頁的職責邊界。")


def render_page_today() -> None:
    """🚦 今天（IA v2 第 1 頁）。**本批無 production caller，刻意如此。**"""
    _session = st.session_state
    _readout = load_macro_readout(_session)
    _band_label, _thr_text, _band_zh, _l4_err = _load_l4_labels()
    _alloc, _alloc_err = _load_allocation()
    _regime, _regime_err = _load_regime()
    # ⚠️【1】兩顆燈**各自一支 loader**：危險度不吃 regime、位階不吃 16 盞燈。
    #    誰失敗只影響誰那一張卡（修前是 regime 掛掉就連坐危險度）。
    _danger, _danger_err, _danger_src = _load_danger(_readout)
    _alerts, _scanned, _alerts_err = _load_key_alerts(_session)

    _tiles_by_bucket = build_indicator_tiles(
        _readout, band_label=_band_label, thr_text=_thr_text, l4_error=_l4_err)
    _cov = coverage(_tiles_by_bucket)
    # 線框七塊全部照算（`build_today_blocks` 是純函式），葉1 ③ 與 ⑤⑥ 各取所需。
    _blocks = {_b.key: _b for _b in build_today_blocks(
        macro_state=_regime, macro_error=_regime_err or None)}

    st.markdown(f"## {ia_nav.page_label(ia_nav.PAGE_TODAY)}")
    st.caption("回答「今天能不能出手、出手到幾成」。")

    # ── （跨頁）頂部狀態列：常駐一條，位在兩葉之上 ───────────────────
    # 三張卡完全復用 `tab_today.build_status_bar_cards()`（交易日 / 總經 /
    # Sheet 綁定），本檔一個字都不重寫。
    render_cards(build_status_bar_cards(_regime, error=_regime_err or None))

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
        #    位階已接線、動能與風險誠實標未接線。**零新增取數**：那個 block
        #    本來每一輪就已經算出來了（修前算完丟掉，改成五桶摘要且零揭露）。
        _summary = _blocks["today.summary"]
        section_header(_summary.title, LEAF1_SUMMARY_NOTE)
        render_cards(_summary.cards)

        section_header("④ 今日關鍵橫幅")
        _render_tiles((build_key_alert_tile(
            _alerts, requested=_readout.requested,
            threshold_scanned=_scanned, error=_alerts_err,
            band_zh_color=_band_zh),), cols=1)

        # ⑤⑥ 尚未接線的區塊：整段復用 `tab_today.build_today_blocks()`，
        #    連「為什麼未接線」的文案都走對面的 SSOT 常數。
        _warroom = _blocks["today.warroom"]
        section_header(_warroom.title)
        render_cards(_warroom.cards)

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
                where=NO_LOAD_EXIT_WHERE))
        for _b in BUCKET_ORDER:
            _meta = BUCKET_META[_b]
            section_header(f"{_meta['emoji']} {_meta['title']}",
                           str(_meta["sub"]))
            _render_tiles(_tiles_by_bucket.get(_b, ()))
