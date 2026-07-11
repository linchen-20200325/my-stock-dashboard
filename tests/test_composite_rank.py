"""tests/test_composite_rank.py — 選股網多因子綜合評分（v19.88）。

驗 composite_rank_candidates：單/多因子平均、pe 低分高、缺料記 0、缺掃描 note、空因子/空池。
"""
from __future__ import annotations

import pandas as pd
import pytest

from src.services.fundamental_screener_service import (
    _percentile_scores,
    composite_rank_candidates,
)


def _surv(ids, eps):
    return pd.DataFrame({"stock_id": ids, "eps": eps})


# ── 百分位分 ──────────────────────────────────────────────────
def test_percentile_higher_better():
    sc = _percentile_scores(["A", "B", "C"], {"A": 1, "B": 2, "C": 3}, higher_better=True)
    assert sc["C"] == 100.0 and sc["A"] < sc["B"] < sc["C"]


def test_percentile_lower_better_pe():
    sc = _percentile_scores(["A", "B", "C"], {"A": 30, "B": 10, "C": 20}, higher_better=False)
    assert sc["B"] == 100.0            # PE 最低 → 最高分
    assert sc["A"] < sc["C"] < sc["B"]


def test_percentile_missing_and_nan_zero():
    sc = _percentile_scores(["A", "B", "C"], {"A": 5, "B": None, "C": float("nan")},
                            higher_better=True)
    assert sc["B"] == 0.0 and sc["C"] == 0.0
    assert sc["A"] == 100.0            # 唯一有值 → 100


# ── 綜合評分 ──────────────────────────────────────────────────
def test_single_factor_orders_like_that_factor():
    df, note = composite_rank_candidates(
        _surv(["A", "B", "C"], [1, 9, 5]), factors=["eps_high"])
    assert list(df["代碼"]) == ["B", "C", "A"]   # EPS 高→低
    assert note == "" and "綜合分" in df.columns


def test_two_factors_average():
    # A: PE低(好) 但 EPS 低(差)；B: PE高(差) 但 EPS 高(好) → 綜合分接近，順序看平均
    df, _ = composite_rank_candidates(
        _surv(["A", "B"], [1, 9]), factors=["pe_low", "eps_high"],
        pe_map={"A": 8, "B": 30})
    # A: 估值100 + EPS50；B: 估值50 + EPS100 → 兩者綜合分相等(各 (100+50)/2=75)
    assert set(df["綜合分"]) == {75.0}
    assert "估值分" in df.columns and "EPS分" in df.columns


def test_shortage_factor_needs_scan_note_but_not_block():
    df, note = composite_rank_candidates(
        _surv(["A", "B"], [3, 1]), factors=["eps_high", "shortage"], shortage_rows=None)
    assert "缺貨動能" in note and "尚未掃描" in note
    # 缺貨全 0 分，仍能用 EPS 排序（不擋）
    assert list(df["代碼"]) == ["A", "B"]


def test_shortage_scores_used_when_scanned():
    rows = [{"代碼": "B", "缺貨分數": 90}, {"代碼": "A", "缺貨分數": 10}]
    df, note = composite_rank_candidates(
        _surv(["A", "B"], [1, 1]), factors=["shortage"], shortage_rows=rows)
    assert list(df["代碼"]) == ["B", "A"] and note == ""


def test_empty_factors():
    df, note = composite_rank_candidates(_surv(["A"], [1]), factors=[])
    assert df.empty and "至少勾選" in note


def test_empty_pool():
    df, note = composite_rank_candidates(None, factors=["eps_high"])
    assert df.empty and "存活池" in note


def test_top_n_caps():
    df, _ = composite_rank_candidates(
        _surv([str(i) for i in range(10)], list(range(10))),
        factors=["eps_high"], top_n=3)
    assert len(df) == 3 and list(df["代碼"]) == ["9", "8", "7"]


# ── 實機 render：② 複選因子 → 綜合評分 → ③ picker（對齊 pe_river slow+skip 慣例）──
def _composite_flow_script():
    import streamlit as st

    from src.services.fundamental_screener_service import (
        composite_rank_candidates,
        get_fundamental_survivors,
    )
    from src.ui.tabs.tab_stock_picker import (
        render_prescreen_panel,
        render_tab_stock_picker,
    )
    render_prescreen_panel()
    surv, _ = get_fundamental_survivors()
    cands, note = composite_rank_candidates(surv, factors=["pe_low", "eps_high"], top_n=50)
    if note:
        st.info(note)
    if not cands.empty:
        st.dataframe(cands.head(50), hide_index=True)
    render_tab_stock_picker(gemini_fn=None, candidates=cands,
                            source_label="基本面優選", skip_s3=True)


@pytest.mark.slow
class TestCompositeFlowRender:
    @classmethod
    def setup_class(cls):
        try:
            from streamlit.testing.v1 import AppTest  # noqa: F401
        except ImportError:
            pytest.skip("streamlit.testing.v1.AppTest 不可用(collection stub 生態)")

    def test_composite_flow_renders(self):
        from streamlit.testing.v1 import AppTest
        at = AppTest.from_function(_composite_flow_script).run(timeout=90)
        assert not at.exception, [f"{e.type}: {str(e.value)[:200]}" for e in at.exception]
        assert len(at.multiselect) >= 1   # picker 候選勾選框
