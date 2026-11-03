"""📊 市場頁第一屏 VM builder（純函式範例）。

輸入＝canonical dict（Preview 期＝`scenarios` 的 FAKE dict；日後＝既有 services 輸出經 feed 原樣帶出）。
輸出＝`PageVM`。

⛔ 本檔**不**：聚合動作、由 regime 推導「是否需要行動」（Gate §4.4 X11）、新增門檻／分支、
為缺值補 0／中性／續抱／safe。「是否需要行動」恆為 `⬜ 尚未提供（待 System Action Aggregator）`。
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from shared.ui2_contract.models import PageVM
from shared.ui2_contract.pages import P4_MARKET
from src.services.ui2.vm_common import build_page_vm

#: 市場頁核心指標卡 id（顯示順序；線框 §2.1）。僅排版契約，不含門檻。
MARKET_CARD_IDS: tuple[str, ...] = (
    "twii", "vix", "us10y", "spread", "dxy", "pmi",
)


def build_market_page_vm(canonical: Mapping[str, Any], *, top_n: int | None = None,
                         mode: str | None = None) -> PageVM:
    if canonical.get("page") != P4_MARKET:
        raise ValueError(f"build_market_page_vm 只接受市場頁 canonical，收到 {canonical.get('page')!r}")
    got = tuple(c["key"] for c in canonical.get("cards", ()))
    if got != MARKET_CARD_IDS:
        raise ValueError(f"市場頁核心指標卡須為 {MARKET_CARD_IDS}，收到 {got}")
    return build_page_vm(canonical, top_n=top_n, mode=mode)
