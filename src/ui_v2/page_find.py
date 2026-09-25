"""「🔍 找標的」頁的版面契約 —— 純結構層（與 `page_today.py` 同一套作法）。

唯一資料來源：`docs/v2/spec/UI_PAGE_FIND.md` ① 四層結構表（⛔ 不寫行號）。
⛔ 本檔不 import streamlit。

**範圍（客戶 2026-09-25 裁示 1）**：只登記本頁**真的畫成卡**的四個 block，
讓 `markup.card_html(block=…)` 經 `src/ui_v2/blocks.py` 查得到它們的密度階。
⛔ 不是整張 ① 表的搬家：沒有卡在畫的 block（`find.statusbar`、`find.screen_table`、
`find.pe_two_kinds`…）不登記 —— 登記一個沒有人畫的 block 只會產生沒有消費者的契約。

**密度由層決定**（UI_COMPONENTS.md §1「四層由 `layers[].n` 自動掛，⛔ 非逐塊手選」）：
每個 block 的 `tier` 一律經 `components.tier_for_layer()` 推出，⛔ 沒有逐塊寫死的階。

🔴 **卡名不一致（據實登記，⛔ 本檔不改名 —— 客戶 2026-09-25 裁示 3）**：
規格 ① 表第二層的 block key 是 `find.screen_summary`，程式
（`src/ui/views/page_find.py::build_screen_result_card`）用的是 `find.screen_result`。
本檔**照程式的 key 登記**；兩者指的是同一張「選股結果」總覽卡。
"""
from __future__ import annotations

from types import MappingProxyType
from typing import Final, Mapping

from src.ui_v2 import components


def _frozen(mapping: dict) -> Mapping:
    return MappingProxyType(mapping)


#: 線框 `n5`（葉2）**不在** `components.tier_for_layer()` 認得的 0~4 之內
#: （實測 `tier_for_layer(5)` → `ValueError`，且有測試釘住，⛔ 不得為本頁放寬）。
#: 規格 ① 表「葉2」列逐字：「`t2`（**WH 本組新訂**：`n5` 超出 `n1~n4` 自動對映，
#: 取「核心卡」）」⇒ `n5` 取**核心卡那一層（第二層）的密度**。
#: ⚠️ 據實揭露：這是規格組新訂的對映，⛔ 不是線框自動掛出來的。
N5_DENSITY_LAYER: Final[int] = 2

# (密度層, 線框 n, blocks)
_LAYER_PLAN: Final[tuple[tuple[int, str, tuple[str, ...]], ...]] = (
    # UI_PAGE_FIND.md ① 表「第一層 條件表單」列（n1 → t1）
    (1, "n1", ("find.screen_form",)),
    # UI_PAGE_FIND.md ① 表「第二層 總覽卡」列（n2 → t2）；規格 key `find.screen_summary`，見檔頭
    (2, "n2", ("find.screen_result",)),
    # UI_PAGE_FIND.md ① 表「葉2」列（n5 → 取核心卡層，見 `N5_DENSITY_LAYER`）
    (N5_DENSITY_LAYER, "n5", ("find.heatmap", "find.sector_flow")),
)


def _build_layers() -> tuple[Mapping[str, object], ...]:
    built = []
    for layer, wireframe_n, blocks in _LAYER_PLAN:
        tier = components.tier_for_layer(layer)
        built.append(_frozen({
            "layer": layer,
            "wireframe_n": wireframe_n,
            "blocks": tuple(blocks),
            "tier": tier,
            "badge_size": components.CARD_TIERS[tier]["badge_size"],
            "title_px": components.CARD_TIERS[tier]["title_px"],
        }))
    return tuple(built)


LAYERS: Final[tuple[Mapping[str, object], ...]] = _build_layers()

#: block → block 內部一列幾格 `(桌機, 平板, 手機)`，UI_PAGE_FIND.md ① 表 cols 欄逐字。
#: ⚠️ 本頁的卡由 Streamlit `st.columns` 排（表單是 widget、兩張地圖卡是 `grid()`），
#:   ⛔ 不走 `markup.grid_html()` —— 契約層 CSS 沒有 `2/1/1` 這組 class
#:   （`markup.page_css()` 只產 `page_today.BLOCK_COLS` 出現過的欄數），
#:   故本表只供本頁 view 讀欄數用，⛔ 不得拿去餵 `grid_html()`。
BLOCK_COLS: Final[Mapping[str, tuple[int, int, int]]] = _frozen({
    "find.screen_form":   (3, 2, 1),   # ① 表「第一層」列 cols 首項
    "find.screen_result": (1, 1, 1),   # ① 表「第二層」列
    "find.heatmap":       (2, 1, 1),   # ① 表「葉2」列 cols 第 2 項
    "find.sector_flow":   (2, 1, 1),   # ① 表「葉2」列 cols 第 3 項
})

#: UI_PAGE_FIND.md ② 表 #10 列逐字：「本頁 `emits_level` 0 命中 ⇒ **不畫 #10**；⛔ 不得併進 #8」。
BADGES_NOT_ON_PAGE: Final[frozenset[int]] = frozenset({10})

_BLOCK_LAYER: Final[Mapping[str, int]] = _frozen(
    {block: layer["layer"] for layer in LAYERS for block in layer["blocks"]}
)

assert set(BLOCK_COLS) == set(_BLOCK_LAYER), (
    "BLOCK_COLS 與 LAYERS 登記的 block 不一致 —— 兩邊要一起改")


def tier_for_block(block_key: str) -> str:
    """block → 卡密度。**⛔ 刻意不提供 tier 覆寫參數**（同 `page_today.tier_for_block`）。"""
    try:
        layer = _BLOCK_LAYER[block_key]
    except KeyError:
        raise KeyError(f"未知的 block：{block_key!r}") from None
    return components.tier_for_layer(layer)


__all__ = ["LAYERS", "BLOCK_COLS", "BADGES_NOT_ON_PAGE", "N5_DENSITY_LAYER", "tier_for_block"]
