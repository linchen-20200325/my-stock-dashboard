"""block 登記處 —— 「依 block 查密度階」的單一入口（客戶 2026-09-25 裁示 1）。

**同一套機制，⛔ 不是第二套**：每一頁各自持有「block → 層」的版面契約
（`page_today.py` / `page_find.py`），各自的 `tier_for_block()` 一律經
`components.tier_for_layer()` 由**層**推出密度；本檔只負責**把 block 分派到它的那一頁**。
⛔ 本檔不持有任何一個 tier 值、⛔ 不提供 tier 覆寫參數。

`markup.card_html(block=…)` 經本檔查階 ⇒ 「🚦 今天」的 block 仍由 `page_today.tier_for_block`
回答（輸出逐 byte 不變），「🔍 找標的」的 block 由 `page_find.tier_for_block` 回答。

⛔ 本檔不 import streamlit。
"""
from __future__ import annotations

from types import MappingProxyType, ModuleType
from typing import Final, Mapping

from src.ui_v2 import page_find, page_today

#: 登記的頁面契約（頁名 → 模組）。每個模組都必須有 `LAYERS` / `tier_for_block` /
#: `BADGES_NOT_ON_PAGE`。加一頁 ＝ 加一列。
PAGES: Final[Mapping[str, ModuleType]] = MappingProxyType({
    "today": page_today,
    "find": page_find,
})


def _build_owner() -> Mapping[str, str]:
    owner: dict[str, str] = {}
    for page, mod in PAGES.items():
        for layer in mod.LAYERS:
            for block in layer["blocks"]:
                if block in owner:
                    # §1：同一個 block 被兩頁登記 ⇒ 查到哪一頁全看字典順序 —— 當場炸。
                    raise RuntimeError(
                        f"block {block!r} 同時登記在 {owner[block]!r} 與 {page!r} 兩頁")
                owner[block] = page
    return MappingProxyType(owner)


#: block → 它所屬的頁名。
BLOCK_PAGE: Final[Mapping[str, str]] = _build_owner()


def page_of_block(block_key: str) -> ModuleType:
    """block → 它所屬的頁面契約模組。未知 block → `KeyError`（⛔ 不猜一頁）。"""
    try:
        return PAGES[BLOCK_PAGE[block_key]]
    except KeyError:
        raise KeyError(f"未知的 block：{block_key!r}") from None


def tier_for_block(block_key: str) -> str:
    """block → 卡密度。交給**它那一頁**的 `tier_for_block`（⛔ 無覆寫參數）。"""
    return page_of_block(block_key).tier_for_block(block_key)


def badges_not_on_page(block_key: str) -> frozenset[int]:
    """block 所屬那一頁**不畫**的徽章號。"""
    return frozenset(page_of_block(block_key).BADGES_NOT_ON_PAGE)


__all__ = ["PAGES", "BLOCK_PAGE", "page_of_block", "tier_for_block", "badges_not_on_page"]
