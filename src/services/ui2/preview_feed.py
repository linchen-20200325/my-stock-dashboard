"""Preview 期 feed：取 FAKE scenario → PageVM。

⚠️ 這是 Preview feed，**不是**第二套 data pipeline：它不取任何資料、不呼叫任何 service。
日後真 feed（原樣帶出既有 L3 service 結果）取代本檔時，VM builder 與 L5 畫面不需重做。
"""
from __future__ import annotations

from shared.ui2_contract.models import PageVM
from shared.ui2_contract.pages import P4_MARKET, PAGE_IDS, SCENARIO_COLD, SCENARIO_IDS
from src.services.ui2.market_vm import build_market_page_vm
from src.services.ui2.scenarios import fake_canonical
from src.services.ui2.skeleton_vm import build_skeleton_page_vm

DEFAULT_SCENARIO = SCENARIO_COLD


def get_preview_page_vm(page_id: str, scenario_id: str, *, top_n: int | None = None) -> PageVM:
    if page_id not in PAGE_IDS:
        raise ValueError(f"unknown page {page_id!r}")
    if scenario_id not in SCENARIO_IDS:
        raise ValueError(f"unknown scenario {scenario_id!r}")
    canonical = fake_canonical(page_id, scenario_id)
    if page_id == P4_MARKET:
        return build_market_page_vm(canonical, top_n=top_n)
    return build_skeleton_page_vm(canonical, top_n=top_n)
