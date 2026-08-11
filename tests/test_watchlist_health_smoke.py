"""tests/test_watchlist_health_smoke.py — 🩺 組合體檢 section 實機 mount 冒煙(slow)。

守衛 L5 section 掛載不炸(空清單 → info;有清單 → 按鈕態,不主動抓價)。對齊
test_sector_flow_stage2 的 AppTest 慣例(stub 生態下 AppTest 不可用 → skip)。
"""
from __future__ import annotations

import pytest

_DRV = (
    "import sys, os\n"
    "sys.path.insert(0, os.getcwd())\n"
    "import streamlit as st\n"
    "from src.ui.tabs.stock_grp_sections import render_watchlist_health_section\n"
    "render_watchlist_health_section(st.session_state.get('_codes', []))\n"
)


@pytest.mark.slow
@pytest.mark.parametrize("codes", [[], ["2330", "00980A"]])
def test_watchlist_health_section_mounts(codes):
    try:
        from streamlit.testing.v1 import AppTest
    except ImportError:
        pytest.skip("streamlit.testing.v1.AppTest 不可用(collection stub 生態)")
    at = AppTest.from_string(_DRV, default_timeout=60)
    at.session_state["_codes"] = codes
    at.run()
    if at.exception:
        msgs = [f"{e.type}: {str(e.value)[:300]}" for e in at.exception]
        pytest.fail("render_watchlist_health_section 有 uncaught exception:\n" + "\n".join(msgs))
