"""「💼 我的持股」頁的版面契約 —— 純結構層（與 `page_today.py` / `page_find.py` 同一套作法）。

唯一資料來源：`docs/v2/spec/UI_PAGE_HOLD.md` ① 五層結構表 ＋
`docs/v2/spec/DATA_MAP_HOLD.md`「block key ≠ 實作 key」那一條（⛔ 不寫行號）。
⛔ 本檔不 import streamlit。

**範圍（同找標的頁，客戶 2026-09-25 裁示 1）**：只登記本頁**真的畫成卡**的**程式卡 key**，
讓 `markup.card_html(block=…)` 經 `src/ui_v2/blocks.py` 查得到它們的密度階。
⛔ 不是整張 ① 表的搬家：規格裡**沒有卡在畫**的 block（`hold.run_scope`、`hold.scope_note`、
`hold.cold_start_toc`、`hold.fx_pnl`、`hold.evi_*` 四塊，以及只是 `section_header` 容器的
`hold.setup`）不登記 —— 登記一個沒有人畫的 block 只會產生沒有消費者的契約。

🔴 **規格 block key ≠ 程式卡 key（據實登記，⛔ 本檔不改名）**：規格 ① 表的 key 多是**容器**
（一個 block 底下有 2~6 張程式卡），`DATA_MAP_HOLD.md` 逐字列出對映。本檔**照程式的 key 登記**，
每一列都註明它屬於規格哪一個 block；卡的**層**（⇒ 密度）一律取它所屬規格 block 的層。

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
# 層與 cols 一律取 UI_PAGE_HOLD.md ① 表（與原型 `gen_today_v2.py::HOLD_LAYOUT` 同值）。
_LAYER_PLAN: Final[tuple[tuple[int, str, str, tuple[int, int, int], tuple[str, ...]], ...]] = (
    # ① 表「第○層」列：`hold.scale_disclosure` → 程式 key `hold.scales`（DATA_MAP_HOLD 逐字）
    (0, "n0", "hold.scale_disclosure", (1, 1, 1), ("hold.scales",)),
    # ① 表「第二層」列
    (2, "n2", "hold.conclusion_cards", (3, 2, 1),
     ("hold.conclusion.action", "hold.conclusion.confidence", "hold.conclusion.todo")),
    (2, "n2", "hold.alloc_deviation", (2, 1, 1),
     ("hold.alloc_split", "hold.take_profit", "hold.position_cap")),
    # ① 表「第三層」列（葉1）
    (3, "n3", "hold.war_table", (3, 2, 1), ("hold.lightwall", "hold.vix")),
    (3, "n3", "hold.swap_compare", (1, 1, 1), ("hold.switch", "hold.macro_stage")),
    # ⚠️ `hold.deep.rebalance` 在規格另屬 `hold.rebalance_deviation`、`hold.deep.stress`／`.var`
    #    另屬 `hold.scenario_calc`（DATA_MAP_HOLD「並陳不裁決」）—— 三者同為第三層（⇒ 同一密度），
    #    本檔**照程式實際的容器**（⑥ 並列 6 張）登記在 `hold.deep_analysis` 底下，⛔ 不代為裁決。
    (3, "n3", "hold.deep_analysis", (3, 2, 1),
     ("hold.deep.rebalance", "hold.deep.core_satellite", "hold.deep.stress",
      "hold.deep.var", "hold.deep.dividend_cash", "hold.deep.grape")),
    (3, "n3", "hold.ai_summary", (1, 1, 1), ("hold.ai_summary",)),
    # ① 表「第三層」列（葉2）
    (3, "n3", "hold.binding", (2, 1, 1), ("hold.binding",)),
    (3, "n3", "hold.portfolio_count", (2, 1, 1), ("hold.portfolio_count",)),
    (3, "n3", "hold.setup.preview", (1, 1, 1), ("hold.setup.preview",)),
    (3, "n3", "hold.setup.pick_sheet", (2, 1, 1), ("hold.setup.pick_sheet",)),
    (3, "n3", "hold.setup.watchlist", (2, 1, 1), ("hold.setup.watchlist",)),
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

#: 程式卡 key → 它所屬規格 block 的 cols `(桌機, 平板, 手機)`（UI_PAGE_HOLD.md ① 表 cols 欄）。
#: ⚠️ 同找標的頁：本頁的卡由 Streamlit `_ui_kit.grid()` 排，⛔ 不走 `markup.grid_html()`
#:   （契約層 CSS 只產 `page_today.BLOCK_COLS` 出現過的欄數），故本表⛔ 不得拿去餵 `grid_html()`。
#: ⚠️ 據實揭露：本頁 view 目前**仍一律以 `MAX_COLS` 排列**（卡化這一批⛔ 不改版面），
#:   與本表不同的 block（`alloc_deviation` 2/1/1、`swap_compare` 1/1/1、葉2 兩張 2/1/1）
#:   要照本表排 ＝ 版面佈局異動，依 `CLAUDE.md §-1.5` v3 §03-2 ① 先送客戶拍板。
BLOCK_COLS: Final[Mapping[str, tuple[int, int, int]]] = _frozen({
    block: cols for _l, _n, _spec, cols, blocks in _LAYER_PLAN for block in blocks
})

#: 程式卡 key → 規格 block key（`DATA_MAP_HOLD.md`「block key ≠ 實作 key」那一條）。
SPEC_BLOCK: Final[Mapping[str, str]] = _frozen({
    block: spec for _l, _n, spec, _c, blocks in _LAYER_PLAN for block in blocks
})

#: UI_PAGE_HOLD.md ② 狀態覆蓋表「#10 ◆ … 本頁不畫；⛔ 不得併進 #8」。
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
