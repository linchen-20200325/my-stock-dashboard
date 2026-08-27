"""shared/ui_state.py — L0 介面狀態模型（v3 憲法 §02「介面狀態嚴格分離」，2026-08-27）。

v3 §02 原文：
    「**未點擊載入**」以**灰色說明提示**，「**系統真出錯**」才標註**紅色警示**，
    杜絕假性錯誤滿版。

本模組是那句話的可執行版本。**純函式，零 I/O、零 streamlit**（L0 Shared）。

══════════════════════════════════════════════════════════════════
為什麼這是一個**新模組**，而不是在 `station_specs` 的四態裡加第五個
══════════════════════════════════════════════════════════════════
`station_specs.classify_state()` 的四態（live / degraded / missing / unwired）
回答的是「**這個值能不能用**」；v3 §02 問的是「**系統有沒有被叫過**」。
兩條軸正交，**不能互相取代**。三個理由（逐一實測過，不是照抄規格）：

1. **簽名裡根本沒有那個輸入。** `classify_state(spec, *, has_value, reason=None)`
   —— 沒有 `requested`。加一個態卻沒有資料源，等於逼每個呼叫端自己用
   `if not data:` 去猜，而那正是要修的病本身。

2. **`StationSpec` 是編寫期的靜態註冊表，裝不下 session 狀態。**
   `wired` / `discriminative` / `emits_level` 全部住在 `@dataclass(frozen=True)`
   的 module-level 常數裡 —— 它們是**寫程式的人在編寫時宣告好的事實**，
   一個 session 內永遠不變。而 `requested` 是**執行期、每個 session 不同、
   每次 rerun 都可能改變**的東西。兩者生命週期與擁有者都不同。

3. **不能塞 `MISS_NOT_REQUESTED` 進 `MISS_*`。**
   `most_fundamental_miss()` 是 `min(reasons, key=MISS_PRIORITY.index)`，
   而 `MISS_PRIORITY` 的排序準則（寫在該檔註解裡）是「**解釋力涵蓋範圍**」。
   「還沒去拿」與「拿了但失敗」之間**沒有涵蓋關係** —— 排前面會對真故障說
   「你還沒點」，排後面會對沒跑過的項目說「這類持股不適用（不是壞掉）」。
   **兩個方向都是假斷言**，因為排序函式的前提在這一對上不成立。
   （§-2 規則 6 的 `MISS_*` 選錯實證，就是同一個病：把不同軸的東西
   丟進同一個優先序比大小。）
   ⚠️ 再者 `classify_state` **不讀 `reason`**（實測：函式體只碰 `spec.wired` /
   `has_value` / `spec.discriminative`），所以就算塞進去，四態仍判 `missing`、
   畫面仍印「無資料」—— 而「無資料」本身就是假話：不是沒有資料，是沒有人去要。

**兩邊並存、互不取代**：一盞燈可以同時是「已請求」（本模組）與「門檻已失準」
（`station_specs`）。需要同時表達時，兩個模型各判各的，不要把其中一個塞進另一個。

══════════════════════════════════════════════════════════════════
最重要的一條施行規則（第 5 類「分不出來」的解藥）
══════════════════════════════════════════════════════════════════

    **`idle` 只能由上游帶下來，禁止由 `if not data:` 推導。**

理由：`if not data:` **分不出**「還沒叫」與「叫了但失敗」——
那正是 S-4.1 / S-4.3 / S-4.6 三處的共同根因，也是 Fund 端
`helpers/io/freshness.py` 在另一個 repo 獨立長出同一個 bug 的原因。
**若允許推導，這個模型第一天就退化成原樣。**

守衛（三層，缺一層就守不住 —— 見 `tests/test_ui_state_model.py`）：
  1. **結構**：`requested` 是**必填的 keyword-only 參數，沒有預設值** ——
     不回答「有沒有被叫過」就拿不到任何狀態。
  2. **矛盾即炸**（§1 Fail Loud）：`requested=False` 卻同時帶了值／錯誤／
     in_flight → `ValueError`。沒被叫過就不可能有本輪的值或錯誤；
     會出現這種組合，多半是把上一輪的殘留當成本輪的事實。
  3. **CI 守衛**：AST 掃全 repo 的呼叫點，`requested=` 綁定的運算式
     **不得與 `has_value=` 綁定的運算式相同**。這條直接把上面那句鐵律
     編碼成可執行的檢查。

══════════════════════════════════════════════════════════════════
顏色：只新增一個
══════════════════════════════════════════════════════════════════
`failed`（紅）是**唯一**的顏色擴充 —— 它就是 v3 §02 所謂「系統真出錯」。
`idle` / `loading` / `empty` / `unwired` **共用既有的中性灰**
（`shared.colors.TRAFFIC_NEUTRAL`），靠 glyph 與文案區分，不引入新色票。
`degraded` 沿用既有的橘。**不新增任何其他顏色。**
"""
from __future__ import annotations

import inspect
from typing import Any

from shared.colors import (
    TRAFFIC_GREEN,
    TRAFFIC_NEUTRAL,
    TRAFFIC_RED,
    TRAFFIC_YELLOW,
)
# 缺值原因沿用 `station_specs` 的既有語彙，**不另立第二套**（§2 SSOT）。
# 這是 L0 → L0 的 import，不違反 §8.2 分層。
from shared.station_specs import (
    MISS_CONTRACT_DRIFT,
    MISS_FETCH_FAILED,
)

# ══════════════════════════════════════════════════════════════════
# 七態
# ══════════════════════════════════════════════════════════════════

#: 沒有人叫過它。**v3 §02 的主角。** 灰。
UI_IDLE = "idle"
#: 真的正在跑（**只有 spinner 生命週期內**才准是這個）。灰。
UI_LOADING = "loading"
#: 叫過了、有錯。**唯一准用紅色的狀態。**
UI_FAILED = "failed"
#: 叫過了、沒錯、就是沒值（新標的、視窗不足…）。灰。
UI_EMPTY = "empty"
#: 有值、可讀，但門檻已失去判別力。橘。
UI_DEGRADED = "degraded"
#: 刻意沒接，叫不叫都一樣。灰。
UI_UNWIRED = "unwired"
#: 有值、可信。綠。
UI_LIVE = "live"

UI_STATES: tuple[str, ...] = (
    UI_UNWIRED, UI_IDLE, UI_LOADING, UI_FAILED, UI_EMPTY, UI_DEGRADED, UI_LIVE,
)

#: 狀態 → (人話名稱, glyph, hex)。**畫面一律從這裡取，禁止各處自己配色**（§3.3）。
#: glyph 刻意各不相同：顏色只有灰／橘／紅／綠四種，灰的四個狀態必須靠 glyph 分辨。
UI_STATE_META: dict[str, tuple[str, str, str]] = {
    UI_IDLE:     ("尚未載入",   "⬜", TRAFFIC_NEUTRAL),
    UI_LOADING:  ("載入中",     "⏳", TRAFFIC_NEUTRAL),
    UI_FAILED:   ("取得失敗",   "🔴", TRAFFIC_RED),
    UI_EMPTY:    ("無資料",     "▨", TRAFFIC_NEUTRAL),
    UI_DEGRADED: ("門檻已失準", "🟠", TRAFFIC_YELLOW),
    UI_UNWIRED:  ("未接線",     "⛔", TRAFFIC_NEUTRAL),
    UI_LIVE:     ("運作中",     "🟢", TRAFFIC_GREEN),
}

#: 「請求過、沒有例外物件、但沒值」時，哪些缺值原因要**升級成 `failed`**。
#:
#: 為什麼只有這兩個：`MISS_FETCH_FAILED` 與 `MISS_CONTRACT_DRIFT` 的
#: `MISS_TEXT` 都指向「**系統壞了、去看錯誤／去修程式**」；其餘四個
#: （`no_input` / `not_enough` / `n/a` / `no_variation`）指向「等一等、
#: 這是資料本身的性質」—— 那不是 v3 §02 所謂的「系統真出錯」，
#: 標紅就變成假性錯誤（v3 §02 前半句要杜絕的東西）。
FAILED_REASONS: frozenset[str] = frozenset({MISS_FETCH_FAILED, MISS_CONTRACT_DRIFT})


def classify_ui_state(
    *,
    requested: bool,
    in_flight: bool = False,
    error: Any = None,
    has_value: bool = False,
    reason: str = "",
    wired: bool = True,
    discriminative: bool = True,
) -> str:
    """一個介面區塊的七態。**不判內容，只判「這一格現在該長什麼樣」。**

    Args:
        requested: **必填，沒有預設值。** 使用者／排程有沒有實際叫過這份資料。
            **必須由上游的 gate 旗標帶下來**（按鈕 handler 寫入的 session key、
            或呼叫端顯式傳入），**禁止**用 `bool(data)` / `not df.empty` 這類
            「從資料本身推回來」的寫法 —— 那分不出「還沒叫」與「叫了但失敗」。
        in_flight: 真的正在跑。只有 `st.spinner` 生命週期內才該是 True。
        error: 上游的例外 / fail token / 錯誤字串。**有值 = 系統真出錯。**
        has_value: 這輪拿到可用的值了沒有。
        reason: 缺值原因，沿用 `station_specs` 的 `MISS_*` 語彙。
        wired: 這一格有沒有接線。False = 刻意沒接。
        discriminative: 門檻還有沒有判別力。

    Returns:
        `UI_STATES` 其中之一。

    判定順序（**順序有意義，勿對調**；程式碼是 SSOT，本 docstring 對齊程式碼）：

    ==  ======================  ==========  ====================================
    序  條件                    結果        為什麼排在這
    ==  ======================  ==========  ====================================
    1   ``not wired``           unwired     刻意沒接，任何值、任何請求都不改變它
    2   ``not requested``       idle        **v3 §02 的主角。排在 error 之前** ——
                                            沒請求過就不可能有*本輪*的錯誤；
                                            殘留的舊 error 不得讓閒置態變紅
    3   ``in_flight``           loading     只有真的在跑才准說「請稍候」
    4   ``error``               failed      請求過 + 有錯 = 「系統真出錯」，
                                            **唯一准用紅色的狀態**
    5   ``not has_value``       empty       請求過、沒錯、就是沒值 →
                                / failed    `reason` 落在 `FAILED_REASONS` 時升紅
    6   ``not discriminative``  degraded    有值、燈照亮，只是別照門檻讀
    7   其餘                    live
    ==  ======================  ==========  ====================================

    **為什麼 `idle` 必須排在 `error` 前面（勿再對調）**：Streamlit 每次 rerun
    都重跑整頁，session 裡很可能還躺著上一輪的錯誤字串。若先判 error，
    一個「使用者剛把頁面重置、還沒重新載入」的區塊會**亮紅燈**——
    那就是 v3 §02 前半句要杜絕的「假性錯誤」。

    Raises:
        ValueError: 當 ``requested=False`` 卻同時帶了 ``has_value`` / ``error``
            / ``in_flight`` 之一（§1 Fail Loud）。沒被叫過就不可能有本輪的值
            或錯誤 —— 會湊出這種組合，通常是**把上一輪的殘留當成本輪的事實**，
            或是把 `requested` 從資料本身推導出來時推錯了邊。
            **靜默容忍它等於讓這個模型第一天就退化。**
    """
    if not requested and (has_value or error or in_flight):
        raise ValueError(
            "requested=False 卻同時帶了 "
            f"has_value={has_value!r} / error={error!r} / in_flight={in_flight!r}"
            " —— 沒被叫過就不可能有本輪的值或錯誤。"
            "常見成因：(a) 把上一輪殘留的 session 值當成本輪事實；"
            "(b) `requested` 是從資料本身推回來的（違反本模組的鐵律："
            "idle 只能由上游帶下來）。請把 gate 旗標顯式傳進來。"
        )
    if not wired:
        return UI_UNWIRED
    if not requested:
        return UI_IDLE
    if in_flight:
        return UI_LOADING
    if error:
        return UI_FAILED
    if not has_value:
        return UI_FAILED if reason in FAILED_REASONS else UI_EMPTY
    if not discriminative:
        return UI_DEGRADED
    return UI_LIVE


def is_alarming(state: str) -> bool:
    """這個狀態該不該用紅色警示？**只有 `failed`。**

    v3 §02：「系統真出錯」才標註紅色警示。`idle` / `loading` / `empty` /
    `unwired` 一律灰，`degraded` 橘。提供這支是為了讓呼叫端**不必自己記**
    哪些算「真出錯」—— 各處自己記就會漂移（S-3.5 的紅黃用反就是這樣來的）。
    """
    return state == UI_FAILED


def state_meta(state: str) -> tuple[str, str, str]:
    """狀態 → (人話名稱, glyph, hex)。未知狀態 → Fail Loud。

    §1：不回一個「中性預設」把未知狀態畫成灰色 —— 那會讓打錯字的狀態名
    悄悄變成一個看起來正常的灰格子，永遠沒人發現。
    """
    if state not in UI_STATE_META:
        raise ValueError(
            f"未知的 UI 狀態 {state!r}；合法值：{sorted(UI_STATE_META)}"
        )
    return UI_STATE_META[state]


def requires_upstream_requested_flag() -> str:
    """回傳本模組的鐵律原文（給測試與錯誤訊息共用，避免兩份文字漂移）。"""
    return "idle 只能由上游帶下來，禁止由 `if not data:` 推導"


def _signature_has_required_requested() -> bool:
    """`requested` 是不是仍為「必填的 keyword-only 參數」。

    給 `tests/test_ui_state_model.py` 的突變守衛用：把 `requested` 拿掉、
    或替它加一個預設值，這支就回 False → 測試轉紅。
    寫在這裡而不是測試檔裡，是為了讓**模組自己**攜帶這條契約。
    """
    _p = inspect.signature(classify_ui_state).parameters.get("requested")
    return (_p is not None
            and _p.kind is inspect.Parameter.KEYWORD_ONLY
            and _p.default is inspect.Parameter.empty)
