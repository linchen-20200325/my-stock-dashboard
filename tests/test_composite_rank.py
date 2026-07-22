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


def test_percentile_missing_and_nan_omitted():
    # v19.90：缺值/NaN 不再記 0，而是【不放 key】（代表無此因子資料）
    sc = _percentile_scores(["A", "B", "C"], {"A": 5, "B": None, "C": float("nan")},
                            higher_better=True)
    assert "B" not in sc and "C" not in sc
    assert sc["A"] == 100.0            # 唯一有值 → 100


def test_missing_factor_not_zero_dragged():
    """v19.90 核心修：缺料因子『不計入平均』（不再灌 0 拖垮綜合分）。"""
    rows = [{"代碼": "B", "缺貨分數": 100}]   # 只有 B 有缺貨分
    df, _ = composite_rank_candidates(_surv(["A", "B"], [9, 1]),
                                      factors=["eps_high", "shortage"], shortage_rows=rows)
    _score = {r["代碼"]: r["綜合分"] for _, r in df.iterrows()}
    # A：EPS=100、缺貨無資料 → 只平均 EPS = 100（舊 0-fill 會變 (100+0)/2=50）
    assert _score["A"] == 100.0
    # B：EPS=50、缺貨=100 → 平均 = 75
    assert _score["B"] == 75.0
    assert list(df["代碼"]) == ["A", "B"]
    # A 的缺貨分欄應為空白（NaN/None），不是 0
    _a_short = df[df["代碼"] == "A"]["缺貨分"].iloc[0]
    assert _a_short != _a_short or _a_short is None   # NaN or None


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


def test_trend_factor_ranks_by_favorable_count():
    # A-2：跨季轉強因子 = trend_map {stock_id: favorable_count 0-4}
    tm = {"A": 4, "B": 1}
    df, note = composite_rank_candidates(_surv(["A", "B"], [1, 1]),
                                         factors=["trend"], trend_map=tm)
    assert list(df["代碼"]) == ["A", "B"] and note == ""
    assert "跨季分" in df.columns


def test_trend_missing_no_scan_note():
    # trend 未提供（空 map）→ 不觸發「尚未掃描」提示（trend 是算的、非掃描）
    df, note = composite_rank_candidates(_surv(["A", "B"], [3, 1]),
                                         factors=["eps_high", "trend"], trend_map=None)
    assert "尚未掃描" not in note
    assert list(df["代碼"]) == ["A", "B"]   # 用 EPS 排（trend 無資料不計入）


def test_trend_missing_stock_omitted_not_zero():
    # A 有 trend、B 無 → B 的跨季分空白（不灌 0，§1）
    df, _ = composite_rank_candidates(_surv(["A", "B"], [1, 1]),
                                      factors=["eps_high", "trend"], trend_map={"A": 4})
    _b_trend = df[df["代碼"] == "B"]["跨季分"].iloc[0]
    assert _b_trend != _b_trend or _b_trend is None   # NaN or None


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


def _auto_pick_script():
    import pandas as pd

    from src.ui.tabs.tab_stock_picker import render_tab_stock_picker
    _cands = pd.DataFrame({"代碼": ["2330", "2317", "2454"], "名稱": ["A", "B", "C"]})
    render_tab_stock_picker(gemini_fn=None, candidates=_cands,
                            source_label="基本面優選", auto_pick=True, skip_s3=True)


@pytest.mark.slow
class TestAutoPickNoMultiselect:
    """v19.89：auto_pick=True → 不出手動候選 multiselect（簡易版核心），且不炸。"""

    @classmethod
    def setup_class(cls):
        try:
            from streamlit.testing.v1 import AppTest  # noqa: F401
        except ImportError:
            pytest.skip("streamlit.testing.v1.AppTest 不可用(collection stub 生態)")

    def test_auto_pick_hides_multiselect(self):
        from streamlit.testing.v1 import AppTest
        at = AppTest.from_function(_auto_pick_script).run(timeout=60)
        assert not at.exception, [f"{e.type}: {str(e.value)[:200]}" for e in at.exception]
        assert len(at.multiselect) == 0   # auto_pick → 無手動候選勾選框
        # 候選已自動帶入
        assert any("已自動帶入" in m.value for m in at.markdown)
