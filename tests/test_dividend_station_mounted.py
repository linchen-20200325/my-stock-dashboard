"""💰 存股戰情室 L5：headless mount 冒煙（button-gated,不觸發抓取）。"""
from __future__ import annotations

import textwrap

import pytest

pytestmark = pytest.mark.slow


def test_render_dividend_station_mounts_clean(tmp_path):
    from streamlit.testing.v1 import AppTest

    script = tmp_path / "_mount.py"
    script.write_text(textwrap.dedent("""
        import streamlit as st
        from src.ui.etf.etf_tab_dividend_station import render_dividend_station
        render_dividend_station()
    """), encoding="utf-8")

    at = AppTest.from_file(str(script), default_timeout=60)
    at.run()
    assert not at.exception, f"我的持股戰情室 mount 有 uncaught exception: {at.exception}"
    # 未按執行前顯示提示,不應自動抓取
    heads = [m.value for m in at.markdown]
    assert any("持股戰情室" in h for h in heads)
    labels = [b.label for b in at.button]
    assert "🚀 跑存股戰情室" in labels
