"""「🚦 今天」頁版面與狀態契約 —— 純結構層（契約 C）。

唯一資料來源：`docs/v2/spec/UI_PAGE_TODAY.md`（＋ 它引用的第 1、2 份）。
每個值旁以 `# UI_PAGE_TODAY.md:NN` 標出處。
⛔ 本檔不 import streamlit：**本輪只做結構定義**（四層有哪些 block、各自掛哪一階、
   狀態怎麼映射），`st.*` 渲染留到下一輪。

**四層由層序自動掛**（UI_COMPONENTS.md:36「⛔ 非逐塊手選」）：本檔的 `tier`／
`badge_size`／`title_px` **一律自 `components.tier_for_layer(layer)` 推導**，
⛔ 不逐塊寫死 —— 手選在結構上就沒有落點。

**§1 Fail Loud 在本頁的落點**（UI_PAGE_TODAY.md:122-141）：
灰態／紅態的大字區**一律留白**，⛔ 不顯示 `0`、⛔ 不顯示上一輪殘值；
`degraded` **觀測照出、判決留白**；`partial` 分子分母拿不到 → **fail-safe 降級 #7**，
⛔ 不得退回 #1「正常」（往「看起來沒事」退就是假綠燈）。
"""
from __future__ import annotations

from types import MappingProxyType
from typing import Final, Mapping

from src.ui_v2 import components


def _frozen(mapping: dict) -> Mapping:
    return MappingProxyType(mapping)


# ══════════════════════════════════════════════════════════════════
# ① 四層結構 —— UI_PAGE_TODAY.md:12-18
# ⚠️ 線框 `n0` 為**葉外 chrome**（五頁共用，不屬任何葉）→ 據實列出，⛔ 不計入四層。
# ⚠️ 第三層與第四層**線框同為 `n3`**（UI_PAGE_TODAY.md:17-18 表格逐字），非筆誤。
# ══════════════════════════════════════════════════════════════════
_LAYER_PLAN: Final[tuple[tuple[int, str, tuple[str, ...], bool, bool], ...]] = (
    # (layer, wireframe_n, blocks, has_main_cta, allows_interaction)
    # 葉外 chrome：3 張狀態卡（交易日／總經／Sheet），UI_PAGE_TODAY.md:14／:20。
    # allows_interaction=True 的依據：UI_PAGE_TODAY.md:104-105「頁首『上一次更新的結果』
    # 整段…含**全頁唯一** `st.expander`…建議掛 `n0` 葉外 chrome」—— expander 即互動元件。
    (0, "n0", ("today.statusbar",), False, True),
    # 第一層＝**單一結論燈** ＋ 一句話結論（user 2026-09-16 裁示，UI_PAGE_TODAY.md:23-24）；
    # ⛔ 不再是 3 張並排卡。互動：UI_PAGE_TODAY.md:99「展開佐證 ▸」觸發器逐字落在 today.verdict.live。
    (1, "n1", ("today.verdict",), False, True),
    # 第二層＝3 張並排卡（UI_PAGE_TODAY.md:27）；
    # ⛔ 本層不得放任何按鈕、連結、`st.popover`（UI_PAGE_TODAY.md:26／:32）。
    (2, "n2", ("today.summary", "today.key_banner", "today.holdings"), False, False),
    # 第三層＝操作列，**全站唯一一顆主 CTA** 掛在這裡（UI_PAGE_TODAY.md:17／:39）。
    (3, "n3", ("today.actions",), True, True),
    # 第四層＝展開佐證（UI_PAGE_TODAY.md:18／:45）；t4 ＝ 1px **dashed**。
    (4, "n3", ("today.warroom", "today.detail"), False, True),
)


def _build_layers() -> tuple[Mapping[str, object], ...]:
    """把層序展開成版面層 —— `tier`／`badge_size`／`title_px` 全部**自動掛**。

    UI_COMPONENTS.md:36「四層由 `layers[].n` 自動掛，⛔ 非逐塊手選」：
    這個函式就是那句話的可執行形式 —— 三個密度相關欄位都只有一個來源
    （`components.tier_for_layer` → `components.CARD_TIERS`），沒有第二條路可以塞值。
    """
    built = []
    for layer, wireframe_n, blocks, has_main_cta, allows_interaction in _LAYER_PLAN:
        tier = components.tier_for_layer(layer)
        tier_spec = components.CARD_TIERS[tier]
        built.append(_frozen({
            "layer": layer,
            "wireframe_n": wireframe_n,
            "blocks": tuple(blocks),
            "tier": tier,
            "badge_size": tier_spec["badge_size"],
            "title_px": tier_spec["title_px"],
            "has_main_cta": has_main_cta,
            "allows_interaction": allows_interaction,
        }))
    return tuple(built)


LAYERS: Final[tuple[Mapping[str, object], ...]] = _build_layers()

#: block → 線框 `cols`，記法 `(桌機, 平板, 手機)`。
#: ⚠️ `today.holdings` **刻意不在表內**：它是新訂 block、線框 `n2` 未定義其 cols
#:   （UI_PAGE_TODAY.md:30）⇒ ⛔ 不得自行發明一組塞進來（CLAUDE.md §1 反捏造）。
BLOCK_COLS: Final[Mapping[str, tuple[int, int, int]]] = _frozen({
    "today.statusbar":  (1, 1, 1),   # UI_PAGE_TODAY.md:20
    "today.verdict":    (1, 1, 1),   # UI_PAGE_TODAY.md:22
    "today.summary":    (3, 2, 1),   # UI_PAGE_TODAY.md:28
    "today.key_banner": (1, 1, 1),   # UI_PAGE_TODAY.md:29
    "today.actions":    (1, 1, 1),   # UI_PAGE_TODAY.md:39
    "today.warroom":    (1, 1, 1),   # UI_PAGE_TODAY.md:45
    "today.detail":     (3, 2, 1),   # UI_PAGE_TODAY.md:45
})

#: 線框 `cols 3/2/1`（＝ 桌機 3／平板 2／手機 1）。
G3_COLS: Final[tuple[int, int, int]] = (3, 2, 1)

#: 各 block 依線框 `states` 會用到的徽章號。
#: ⚠️ 只登記規格**明文列出**的四個 block；`today.statusbar`／`key_banner`／`actions`／
#:   `holdings` 規格未給徽章清單 ⇒ ⛔ 不自行補一組（規格的洞，見交付報告）。
BLOCK_BADGES: Final[Mapping[str, tuple[int, ...]]] = _frozen({
    "today.verdict": (1, 3, 4, 5, 6, 7),           # UI_PAGE_TODAY.md:22
    "today.summary": (1, 3, 4, 5, 6, 7, 8, 9),     # UI_PAGE_TODAY.md:28
    "today.warroom": (1, 3, 5, 6, 7),              # UI_PAGE_TODAY.md:45
    "today.detail":  (1, 3, 4, 5, 6, 7, 8, 9),     # UI_PAGE_TODAY.md:45
})

#: **已撤回、不是待補**的 block（UI_PAGE_TODAY.md:97）：
#: `get_macro_state()` 只有 9 key、無 `as_of` ⇒ 原「逐格顯示 as_of」規格已撤回。
#: ⛔ 不得從 `LAYERS` 悄悄消失而不留紀錄（§-2 規則 6 的同一紀律）。
WITHDRAWN_BLOCKS: Final[frozenset[str]] = frozenset({"chrome.asof"})

#: **客戶未裁、去向開放**的卡（UI_PAGE_TODAY.md:115）。
#: 客戶只裁示「不搬」進 `today.summary`，**沒有裁示要刪** ⇒
#: ⛔ 不得自行判定刪除、⛔ 不得自行安排到第二層其他 block，但也⛔ 不得默默消失。
OPEN_ITEMS: Final[frozenset[str]] = frozenset({"verdict.exposure", "verdict.regime"})

_BLOCK_LAYER: Final[Mapping[str, int]] = _frozen(
    {block: layer["layer"] for layer in LAYERS for block in layer["blocks"]}
)


def blocks_of_layer(layer: int) -> tuple[str, ...]:
    """該層由上而下的 block key。未知層序 → `ValueError`。"""
    for entry in LAYERS:
        if entry["layer"] == layer:
            return entry["blocks"]
    raise ValueError(f"未知的層序 {layer!r}：只有 0（葉外 chrome）與 1~4 四層")


def tier_for_block(block_key: str) -> str:
    """block → 卡密度。**⛔ 刻意不提供 tier 覆寫參數**：密度只能由它所在的層決定。"""
    try:
        layer = _BLOCK_LAYER[block_key]
    except KeyError:
        raise KeyError(f"未知的 block：{block_key!r}") from None
    return components.tier_for_layer(layer)


# ══════════════════════════════════════════════════════════════════
# ③ 三卡歸位（user 2026-09-16 裁示，UI_PAGE_TODAY.md:111-115）
# 裁示逐字：位階 ← summary.regime（既有）／動能 ← 未接線（exposure 不是動能，不搬）
#          ／風險 ← danger（對得上，直接對映）
# ══════════════════════════════════════════════════════════════════
SUMMARY_COLUMNS: Final[tuple[Mapping[str, object], ...]] = (
    # (a) 既有、維持現接線；⛔ 不得把 `verdict.regime` 搬過去（同源重複＝撞欄不是填空）
    _frozen({"name": "位階", "source": "summary.regime", "wired": True, "badge": None}),
    # (b) 維持未接線；⛔ 不得拿 `verdict.exposure` 頂替（exposure ＝ 配置油門帶，不是動能）。
    #     未接線態依 ② 走 #5，⛔ 不得畫成 #1。
    _frozen({"name": "動能", "source": None, "wired": False, "badge": 5}),
    # (c) 直接對映
    _frozen({"name": "風險", "source": "verdict.danger", "wired": True, "badge": None}),
)

# UI_PAGE_TODAY.md:86-87「本頁**不畫 #10**；⛔ 但不得因此把 #10 併進 #8」
BADGES_NOT_ON_PAGE: Final[frozenset[int]] = frozenset({10})
BADGES_ON_PAGE: Final[frozenset[int]] = frozenset(
    b["n"] for b in components.BADGES if b["n"] not in BADGES_NOT_ON_PAGE
)


# ══════════════════════════════════════════════════════════════════
# 第三層 主 CTA —— UI_PAGE_TODAY.md:39-43／:127-129
# ══════════════════════════════════════════════════════════════════
#: 字串 SSOT ＝ `shared/ia_nav.py ACTION_LABELS[ACTION_UPDATE_TODAY]`，
#: 與線框 `mainCTA.label` **逐字相同**（UI_PAGE_TODAY.md:39-40）。
MAIN_CTA: Final[Mapping[str, object]] = _frozen({
    "label": "🚀 更新今日戰情",
    "button": "primary_cta",   # UI_PAGE_TODAY.md:41 按鈕規格取 UI_COMPONENTS §3 主 CTA
    "unique_per_site": True,   # UI_COMPONENTS.md:104「主 CTA（**全站唯一一顆**）」
})

#: 上游這輪失敗（可重試）時的說明字，UI_PAGE_TODAY.md:127 逐字。
MAIN_CTA_RETRY_NOTE: Final[str] = "可以重試 —— 上游這輪失敗，不是程式錯誤。"

#: 契約漂移時的說明字，UI_PAGE_TODAY.md:128-129 逐字。
#: ⛔ 不得對契約漂移給「可重跑」指引 —— 重按不會好，給錯指引比不給更糟。
MAIN_CTA_CONTRACT_DRIFT_NOTE: Final[str] = "🔴 重按不會好，程式要修，請回報。"

#: 契約漂移的 miss reason（`FAILED_REASONS` 內），UI_PAGE_TODAY.md:128／:141。
MISS_CONTRACT_DRIFT: Final[str] = "MISS_CONTRACT_DRIFT"


def main_cta_state(*, failure_reason: str | None = None) -> Mapping[str, object]:
    """主 CTA 的可按性與說明字（UI_PAGE_TODAY.md:127-129）。

    - 一般的上游失敗（`MISS_NO_INPUT` 等）→ **可按** ＋「可以重試」；
    - `MISS_CONTRACT_DRIFT` → **停用** ＋「重按不會好，程式要修，請回報。」
    """
    if failure_reason == MISS_CONTRACT_DRIFT:
        return _frozen({"enabled": False, "note": MAIN_CTA_CONTRACT_DRIFT_NOTE})
    if failure_reason is None:
        return _frozen({"enabled": True, "note": None})
    return _frozen({"enabled": True, "note": MAIN_CTA_RETRY_NOTE})


# ══════════════════════════════════════════════════════════════════
# ② 狀態 → 徽章（UI_PAGE_TODAY.md:58-90）
# ══════════════════════════════════════════════════════════════════
#: 線框鍵 `error` ↔ 常數值 `"failed"`：以**常數**為準，線框鍵名視為同義
#: （UI_PAGE_TODAY.md:89-90，⛔ 不得為對齊線框去改 `UI_FAILED` 的值）。
_STATE_BADGE: Final[Mapping[str, int]] = _frozen({
    "live":     1,   # UI_PAGE_TODAY.md:62
    "loading":  2,   # UI_PAGE_TODAY.md:63 ⛔ 不得拿 #3 冒充載入中
    "idle":     3,   # UI_PAGE_TODAY.md:64
    "degraded": 4,   # UI_PAGE_TODAY.md:65
    "unwired":  5,   # UI_PAGE_TODAY.md:66
    "failed":   6,   # UI_PAGE_TODAY.md:67（常數值）
    "error":    6,   # UI_PAGE_TODAY.md:89-90（線框鍵，同義）
    # `missing` 無獨立常數、併入 UI_EMPTY：兩鍵**都畫 #7**
    # （UI_PAGE_TODAY.md:80-81；⛔ 不得畫成 #8 —— #8 專屬 MISS_NOT_APPLICABLE，
    #  重跑無效，畫錯等於給錯指引）。
    "missing":  7,
})

#: #8 專屬的缺值原因（UI_PAGE_TODAY.md:70「靠 `miss_reason` 分辨」）。
MISS_NOT_APPLICABLE: Final[str] = "MISS_NOT_APPLICABLE"

_KNOWN_STATES: Final[frozenset[str]] = frozenset(_STATE_BADGE) | {"empty", "na", "partial"}


def resolve_badge(
    *,
    state: str,
    miss_reason: str | None = None,
    numerator: int | None = None,
    denominator: int | None = None,
) -> int:
    """狀態（＋缺值原因／分子分母）→ 徽章號 #1~#10。

    `empty`／`na` 靠 `miss_reason` 分辨 #7 vs #8（UI_PAGE_TODAY.md:68-70）。
    `partial` 走 **fail-safe**：分子分母任一拿不到 → 降級 #7「缺漏 · 可重跑」，
    ⛔ 不得退回 #1「正常」（UI_COMPONENTS.md:78／UI_PAGE_TODAY.md:83-84）；
    L3 補齊分子分母後自動接回 #9，**不是永久降級**（UI_PAGE_TODAY.md:84-85）。
    """
    if state not in _KNOWN_STATES:
        raise ValueError(
            f"未知的狀態 {state!r}：七態 SSOT 在 shared/ui_state.py，"
            "⛔ 不得為了畫得出來就給它一個近似的徽章"
        )

    if state == "partial":
        if numerator is None or denominator is None:
            return 7   # fail-safe：缺資訊時往保守側退
        return 9

    if state in ("empty", "na"):
        return 8 if miss_reason == MISS_NOT_APPLICABLE else 7

    return _STATE_BADGE[state]


# ══════════════════════════════════════════════════════════════════
# ④ 缺值時的畫面行為 —— UI_PAGE_TODAY.md:122-141（§1 Fail Loud 的 UI 面）
# ══════════════════════════════════════════════════════════════════
#: 灰態與紅態：大字區**一律留白**，⛔ 不得顯示 `0` 或上一輪殘值。
_BLANK_VALUE_STATES: Final[frozenset[str]] = frozenset({
    "failed", "error",                                  # 紅態
    "idle", "loading", "unwired", "empty", "missing", "na",  # 灰態
})

#: 判決留白的狀態：`degraded` ＝ 門檻已失準 ⇒ ⛔ 不照失效門檻判燈
#: （但**觀測照出**，⛔ 不因為門檻失效就把值藏起來，UI_PAGE_TODAY.md:137-138）。
_BLANK_LEVEL_STATES: Final[frozenset[str]] = _BLANK_VALUE_STATES | {"degraded"}


def card_value_text(*, state: str, value: object) -> str | None:
    """卡片大字區的**觀測值**字串；灰態／紅態一律 `None`（留白）。

    ⛔ 全域：缺值一律不顯示為 `0`（UI_PAGE_TODAY.md:141）。
    """
    if state not in _KNOWN_STATES:
        raise ValueError(f"未知的狀態 {state!r}")
    if state in _BLANK_VALUE_STATES:
        return None
    if value is None:
        # 有色態卻沒有值 —— 留白比印出 "None" 誠實（§1：寧可留白，不可造假）。
        return None
    return str(value)


def card_level_text(*, state: str, level: object) -> str | None:
    """卡片的**判決**（燈號等級）字串；`degraded` 一律 `None`（判決留白）。"""
    if state not in _KNOWN_STATES:
        raise ValueError(f"未知的狀態 {state!r}")
    if state in _BLANK_LEVEL_STATES:
        return None
    if level is None:
        return None
    return str(level)


def observation_miss_reason(value: object, miss_reason: str | None) -> str | None:
    """檢查 `(值, 缺值原因)` 二元組的合法性（UI_PAGE_TODAY.md:141）。

    `(None, None)`（沒有值也沒有原因）與 `(值, MISS_*)`（有值卻同時宣告缺漏）
    皆為**非法二元組** → 一律回 `"MISS_CONTRACT_DRIFT"`。
    合法時回傳原本的 `miss_reason`（有值時為 `None`）。
    """
    has_value = value is not None
    has_reason = miss_reason is not None
    if has_value == has_reason:
        # 兩者皆有 或 兩者皆無 —— 兩種都是契約漂移。
        return MISS_CONTRACT_DRIFT
    return miss_reason


# ══════════════════════════════════════════════════════════════════
# 🆕 第二層 `today.holdings` 持倉健檢 —— UI_PAGE_TODAY.md:30-37
# 🔴 資料限制（硬規則）：持股來源 `stock_watchlist` 的 schema **只有**
#    `name`／`ticker`／`updated_at` 三欄 ⇒ **這張卡拿不到部位大小**。
# ══════════════════════════════════════════════════════════════════
#: **可顯示**的九項，皆由**檔數**推得（UI_PAGE_TODAY.md:34）。
#: ⛔ **不得顯示**：損益、部位佔比、金額、張數、均價，
#:   或任何需要張數／均價才算得出來的量（UI_PAGE_TODAY.md:35）。
HOLDINGS_DISPLAY_FIELDS: Final[tuple[str, ...]] = (
    "n_total", "n_classified", "n_unclassified", "n_industries",
    "coverage_pct", "top1_pct", "top3_pct", "hhi", "n_eff",
)

#: `concentration.py` 一律 `basis='equal_weight'` 並要求 UI 揭露該假設
#: （UI_PAGE_TODAY.md:33-34，`BASIS_EQUAL_WEIGHT`）。
HOLDINGS_BASIS: Final[str] = "equal_weight"

#: 標籤**逐字**，⛔ 不得標成「部位佔比」（UI_PAGE_TODAY.md:36）。
HOLDINGS_TOP1_LABEL: Final[str] = "最大單一產業（檔數等權）"

#: 等權假設揭露句一行（**必填**），說明字級 `--ink-3` `11.5px`（UI_PAGE_TODAY.md:34）。
#: ⚠️ 規格要求「必填」但**未給逐字文案** ⇒ 本句為實作組草擬（見交付報告）。
HOLDINGS_EQUAL_WEIGHT_DISCLOSURE: Final[Mapping[str, object]] = _frozen({
    "text": "集中度以「檔數等權」計算 —— 持股來源只有代號與名稱，沒有張數與均價，"
            "因此這裡的百分比是檔數佔比，不是部位佔比。",
    "color": "--ink-3",   # UI_TOKENS.md:107 說明字級的色
    "font_px": 11.5,      # UI_TOKENS.md:107 說明 `11.5px`
})


def holdings_badge(*, n_classified: int) -> int:
    """持倉健檢卡的徽章號。

    `is_computable=False`（`n_classified == 0`）→ **#7 缺漏 · 可重跑**
    （Sheet 失敗可重試），⛔ 不得顯示 `0` 或「完美分散」、⛔ 不得退回 #1
    （UI_PAGE_TODAY.md:37／:125-126）。
    """
    if not isinstance(n_classified, int) or isinstance(n_classified, bool):
        raise TypeError(f"n_classified 必須是 int，收到 {type(n_classified).__name__}")
    if n_classified < 0:
        raise ValueError(f"n_classified 不得為負：{n_classified}")
    return 7 if n_classified == 0 else 1


__all__ = [
    "LAYERS", "BLOCK_COLS", "BLOCK_BADGES", "WITHDRAWN_BLOCKS", "OPEN_ITEMS",
    "SUMMARY_COLUMNS", "BADGES_ON_PAGE", "BADGES_NOT_ON_PAGE",
    "MAIN_CTA", "MAIN_CTA_RETRY_NOTE", "MAIN_CTA_CONTRACT_DRIFT_NOTE", "G3_COLS",
    "HOLDINGS_DISPLAY_FIELDS", "HOLDINGS_BASIS", "HOLDINGS_TOP1_LABEL",
    "HOLDINGS_EQUAL_WEIGHT_DISCLOSURE",
    "MISS_CONTRACT_DRIFT", "MISS_NOT_APPLICABLE",
    "tier_for_block", "blocks_of_layer", "resolve_badge",
    "card_value_text", "card_level_text", "observation_miss_reason",
    "main_cta_state", "holdings_badge",
]
