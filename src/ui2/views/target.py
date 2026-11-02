"""target 頁 view：只渲染 PageVM。"""
from __future__ import annotations

from shared.ui2_contract.models import PageVM
from src.ui2.views._page import render_page


def render(vm: PageVM) -> None:
    render_page(vm)
