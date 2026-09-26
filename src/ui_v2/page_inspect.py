"""「🔬 查一檔」頁的版面契約 —— 純結構層（與 `page_today.py` / `page_find.py` / `page_hold.py` 同一套作法）。

唯一資料來源：`docs/v2/spec/UI_PAGE_INSPECT.md` ① 四層結構表（⛔ 不寫行號）。
⛔ 本檔不 import streamlit。

**範圍（同找標的頁／我的持股頁，客戶 2026-09-25 裁示 1）**：只登記本頁**真的畫成卡**的
**程式卡 key**，讓 `markup.card_html(block=…)` 經 `src/ui_v2/blocks.py` 查得到它們的密度階。
⛔ 不是整張 ① 表的搬家：規格裡**沒有卡在畫**的 block（`inspect.statusbar`、`inspect.form`、
`inspect.wiring_single`、`inspect.pattern_measure`、`inspect.batch.form`、`inspect.evi.*` 三塊）
不登記 —— 登記一個沒有人畫的 block 只會產生沒有消費者的契約。

🔴 **規格 block key ≠ 程式卡 key（據實登記，⛔ 本檔不改名）**：規格 ① 表第三層的
`inspect.profit` 是**容器**，程式畫成三張卡（`inspect.profit.gross_margin` /
`.operating_margin` / `.safety_margin`）。本檔**照程式的 key 登記**，每一列都註明它屬於
規格哪一個 block；卡的**層**（⇒ 密度）一律取它所屬規格 block 的層。

**密度由層決定**（UI_COMPONENTS.md §1「四層由 `layers[].n` 自動掛，⛔ 非逐塊手選」）：
每張卡的 `tier` 一律經 `components.tier_for_layer()` 推出，⛔ 沒有逐卡寫死的階。
"""
from __future__ import annotations

from types import MappingProxyType
from typing import Final, Mapping

from src.ui_v2 import components


def _frozen(mapping: dict) -> Mapping:
    return MappingProxyType(mapping)


# (密度層, 線框 n, 規格 block key, 該 block 的 cols（桌機, 平板, 手機）, 程式卡 keys)
# 層與 cols 一律取 UI_PAGE_INSPECT.md ① 表（「3/2/1・其餘 1/1/1」逐格照抄）。
_LAYER_PLAN: Final[tuple[tuple[int, str, str, tuple[int, int, int], tuple[str, ...]], ...]] = (
    # ① 表「第一層 輸入與判型」列：`inspect.kind`／`inspect.unknown`（「其餘 1/1/1」）
    (1, "n1", "inspect.kind", (1, 1, 1), ("inspect.kind",)),
    (1, "n1", "inspect.unknown", (1, 1, 1), ("inspect.unknown",)),
    # ① 表「第二層 三張判決卡」列（「6 block 全 3/2/1」）
    (2, "n2", "inspect.stock.health", (3, 2, 1), ("inspect.stock.health",)),
    (2, "n2", "inspect.stock.valuation", (3, 2, 1), ("inspect.stock.valuation",)),
    (2, "n2", "inspect.stock.chips", (3, 2, 1), ("inspect.stock.chips",)),
    (2, "n2", "inspect.etf.premium", (3, 2, 1), ("inspect.etf.premium",)),
    (2, "n2", "inspect.etf.dividend", (3, 2, 1), ("inspect.etf.dividend",)),
    (2, "n2", "inspect.etf.peer", (3, 2, 1), ("inspect.etf.peer",)),
    # ① 表「第三層 明細」列：`inspect.profit`（3/2/1）→ 程式三張卡；其餘 1/1/1
    (3, "n3", "inspect.profit", (3, 2, 1),
     ("inspect.profit.gross_margin", "inspect.profit.operating_margin",
      "inspect.profit.safety_margin")),
    (3, "n3", "inspect.stock.detail", (1, 1, 1), ("inspect.stock.detail",)),
    (3, "n3", "inspect.etf.detail", (1, 1, 1), ("inspect.etf.detail",)),
    (3, "n3", "inspect.batch", (1, 1, 1), ("inspect.batch",)),
)


def _build_layers() -> tuple[Mapping[str, object], ...]:
    built = []
    for layer, wireframe_n, spec_block, _cols, blocks in _LAYER_PLAN:
        tier = components.tier_for_layer(layer)
        built.append(_frozen({
            "layer": layer,
            "wireframe_n": wireframe_n,
            "spec_block": spec_block,
            "blocks": tuple(blocks),
            "tier": tier,
            "badge_size": components.CARD_TIERS[tier]["badge_size"],
            "title_px": components.CARD_TIERS[tier]["title_px"],
        }))
    return tuple(built)


LAYERS: Final[tuple[Mapping[str, object], ...]] = _build_layers()

#: 程式卡 key → 它所屬規格 block 的 cols `(桌機, 平板, 手機)`（UI_PAGE_INSPECT.md ① 表 cols 欄）。
#: ⚠️ 同找標的頁／我的持股頁：本頁的卡由 Streamlit `_ui_kit.grid()` 排，⛔ 不走 `markup.grid_html()`
#:   （契約層 CSS 只產 `page_today.BLOCK_COLS` 出現過的欄數），故本表⛔ 不得拿去餵 `grid_html()`。
#: ⚠️ 據實揭露：本頁 view 目前**仍一律以 `MAX_COLS` 排列**（卡化這一批⛔ 不改版面）；
#:   規格 ① 表自陳「`3/2/1` 的 `tablet=2` 未落地」—— 要照本表排 ＝ 版面佈局異動，
#:   依 `CLAUDE.md §-1.5` v3 §03-2 ① 先送客戶拍板。
BLOCK_COLS: Final[Mapping[str, tuple[int, int, int]]] = _frozen({
    block: cols for _l, _n, _spec, cols, blocks in _LAYER_PLAN for block in blocks
})

#: 程式卡 key → 規格 block key。
SPEC_BLOCK: Final[Mapping[str, str]] = _frozen({
    block: spec for _l, _n, spec, _c, blocks in _LAYER_PLAN for block in blocks
})

#: UI_PAGE_INSPECT.md ② 狀態覆蓋表 #10 列：「`emits_level` 在本頁 0 命中 ⇒ **不畫 #10**；⛔ 不得併進 #8」。
BADGES_NOT_ON_PAGE: Final[frozenset[int]] = frozenset({10})

_BLOCK_LAYER: Final[Mapping[str, int]] = _frozen(
    {block: layer["layer"] for layer in LAYERS for block in layer["blocks"]}
)

assert set(BLOCK_COLS) == set(_BLOCK_LAYER) == set(SPEC_BLOCK), (
    "BLOCK_COLS / SPEC_BLOCK 與 LAYERS 登記的卡不一致 —— 要一起改")
assert len(_BLOCK_LAYER) == sum(len(p[4]) for p in _LAYER_PLAN), "同一張卡登記了兩次"


def tier_for_block(block_key: str) -> str:
    """卡 key → 卡密度。**⛔ 刻意不提供 tier 覆寫參數**（同 `page_today.tier_for_block`）。"""
    try:
        layer = _BLOCK_LAYER[block_key]
    except KeyError:
        raise KeyError(f"未知的 block：{block_key!r}") from None
    return components.tier_for_layer(layer)


__all__ = ["LAYERS", "BLOCK_COLS", "SPEC_BLOCK", "BADGES_NOT_ON_PAGE", "tier_for_block"]
