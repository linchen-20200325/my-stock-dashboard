"""🎯 標的／💼 持股／👤 我的 骨架 VM builder（純函式；僅第一屏四問＋占位卡）。"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from shared.ui2_contract.models import PageVM
from shared.ui2_contract.pages import P4_HOLD, P4_ME, P4_TARGET
from src.services.ui2.vm_common import build_page_vm

_SKELETON_PAGES = (P4_TARGET, P4_HOLD, P4_ME)


def build_skeleton_page_vm(canonical: Mapping[str, Any], *, top_n: int | None = None) -> PageVM:
    if canonical.get("page") not in _SKELETON_PAGES:
        raise ValueError(f"build_skeleton_page_vm 不接受 {canonical.get('page')!r}")
    return build_page_vm(canonical, top_n=top_n)
