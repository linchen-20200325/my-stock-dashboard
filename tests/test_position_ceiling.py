"""tests/test_position_ceiling.py — 姿態油門「建議區間」× §十一「風險上限」並排守衛(v19.168 第1項)。

user 拍板:「兩個都留 上限 vs 建議區間」。§十一 曝險鎖的 exposure_limit_pct(薩姆/PMI/
外資期貨硬否決天花板)不再是孤立的第三個持股%,而是與總經油門 gauge 的「建議持股區間」
並排呈現、清楚標成互補(實際持股取兩者較低)。未跑 §十一 AI 裁決(無 exposure_limit_pct)
時只顯示區間(§1 fail-safe)。
"""
from __future__ import annotations

from pathlib import Path

import pytest

_SRC = (Path(__file__).resolve().parents[1]
        / "src/ui/tabs/macro/section_traffic_light.py").read_text(encoding="utf-8")


# ── source-scan:接線不回退 ──────────────────────────────────────
def test_gauge_reads_exposure_ceiling_and_labels_complement():
    assert "exposure_limit_pct" in _SRC, "gauge 未讀 §十一 曝險上限"
    assert "系統風險上限" in _SRC
    assert "取較低者" in _SRC, "未標明『實際取兩者較低』的互補關係"


# ── 實機 render(AppTest,對齊 pe_river/cross_ai slow 慣例)──────
def _script_with_ceiling():
    import streamlit as st
    st.session_state["macro_state"] = {"exposure_limit_pct": 40}
    from src.ui.tabs.macro.section_traffic_light import render_position_throttle
    # health 62 → 建議區間 50–70%;上限 40 < 70 → 實際上限取 40%
    render_position_throttle({"health": 62, "regime": "neutral", "defense": False})


def _script_no_ceiling():
    from src.ui.tabs.macro.section_traffic_light import render_position_throttle
    render_position_throttle({"health": 62, "regime": "neutral", "defense": False})


@pytest.mark.slow
class TestCeilingRender:
    @classmethod
    def setup_class(cls):
        try:
            from streamlit.testing.v1 import AppTest  # noqa: F401
        except ImportError:
            pytest.skip("streamlit.testing.v1.AppTest 不可用(collection stub 生態)")

    def test_ceiling_shown_alongside_range(self):
        from streamlit.testing.v1 import AppTest
        at = AppTest.from_function(_script_with_ceiling).run(timeout=30)
        assert not at.exception
        _all = " ".join(m.value for m in at.markdown)
        assert "建議持股" in _all and "50–70%" in _all          # 建議區間仍在
        assert "系統風險上限" in _all and "40%" in _all           # 上限並排
        assert "實際上限 40%" in _all                             # 取較低者

    def test_no_ceiling_when_not_evaluated(self):
        from streamlit.testing.v1 import AppTest
        at = AppTest.from_function(_script_no_ceiling).run(timeout=30)
        assert not at.exception
        _all = " ".join(m.value for m in at.markdown)
        assert "建議持股" in _all                                 # 區間照顯示
        assert "系統風險上限" not in _all                         # 無上限 → 不偽造(§1)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
