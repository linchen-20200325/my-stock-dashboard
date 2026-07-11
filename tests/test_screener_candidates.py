"""tests/test_screener_candidates.py — 選股網候選 builder（v19.74）。

驗 build_candidate_frame 四個排序角度 + 邊界（None PE 不崩、掃描缺→note、存活池交集）。
"""
from __future__ import annotations

import pandas as pd

from src.services.fundamental_screener_service import (
    SCREEN_ANGLE_LABELS,
    build_candidate_frame,
)


def _surv(ids, eps):
    return pd.DataFrame({"stock_id": ids, "eps": eps})


def test_angle_labels_cover_four():
    assert set(SCREEN_ANGLE_LABELS.values()) == {"pe_low", "eps_high", "shortage", "rs_leader"}


def test_pe_low_missing_pe_goes_last_no_crash():
    # C 無 PE（None）+ D 無 PE(NaN) → 兩個 None/NaN 都要排最後且不崩
    df, note = build_candidate_frame(
        _surv(["A", "B", "C", "D"], [1, 2, 3, 4]), angle="pe_low",
        pe_map={"A": 20, "B": 8, "C": None, "D": float("nan")},
        name_map={"A": "台A"})
    assert list(df["代碼"])[:2] == ["B", "A"]     # 8 < 20
    assert set(list(df["代碼"])[2:]) == {"C", "D"}  # 無 PE 兩檔墊底
    assert note == ""
    assert df.iloc[1]["名稱"] == "台A"             # name_map 套用


def test_eps_high_desc():
    df, _ = build_candidate_frame(_surv(["A", "B", "C"], [1, 9, 5]), angle="eps_high")
    assert list(df["代碼"]) == ["B", "C", "A"]


def test_shortage_needs_scan_first():
    df, note = build_candidate_frame(_surv(["A"], [1]), angle="shortage", shortage_rows=None)
    assert df.empty and "掃描缺貨" in note


def test_shortage_ranks_by_scan_and_intersects_survivors():
    rows = [{"代碼": "B", "缺貨分數": 90}, {"代碼": "X", "缺貨分數": 80},
            {"代碼": "A", "缺貨分數": 70}]
    df, note = build_candidate_frame(_surv(["A", "B", "C"], [1, 2, 3]),
                                     angle="shortage", shortage_rows=rows)
    assert list(df["代碼"]) == ["B", "A"]   # X 非存活池剔除；掃描順序保留
    assert note == "" and "缺貨分數" in df.columns


def test_rs_needs_scan_first():
    df, note = build_candidate_frame(_surv(["A"], [1]), angle="rs_leader", rs_rows=[])
    assert df.empty and "抗跌" in note


def test_rs_ranks_by_scan():
    rows = [{"代碼": "C", "RS(σ)": 1.8}, {"代碼": "A", "RS(σ)": 0.5}]
    df, _ = build_candidate_frame(_surv(["A", "B", "C"], [1, 2, 3]),
                                  angle="rs_leader", rs_rows=rows)
    assert list(df["代碼"]) == ["C", "A"]


def test_empty_survivor_pool_failloud():
    df, note = build_candidate_frame(None, angle="pe_low")
    assert df.empty and "存活池" in note


def test_top_n_caps_output():
    df, _ = build_candidate_frame(_surv([str(i) for i in range(10)], list(range(10))),
                                  angle="eps_high", top_n=3)
    assert len(df) == 3 and list(df["代碼"]) == ["9", "8", "7"]


def test_scan_intersect_empty_gives_note():
    # 掃描結果與存活池完全無交集 → 空 + note
    df, note = build_candidate_frame(_surv(["A", "B"], [1, 2]), angle="shortage",
                                     shortage_rows=[{"代碼": "ZZZ", "缺貨分數": 99}])
    assert df.empty and "無交集" in note


# ── 實機 render：選股網②③核心路徑（存活池 → 候選 → 三階段 picker）──
def _screener_flow_script():
    import streamlit as st

    from src.services.fundamental_screener_service import (
        build_candidate_frame,
        get_fundamental_survivors,
    )
    from src.ui.tabs.tab_stock_picker import (
        render_prescreen_panel,
        render_tab_stock_picker,
    )
    render_prescreen_panel()
    surv, _ = get_fundamental_survivors()
    cands, note = build_candidate_frame(surv, angle="eps_high", top_n=50)
    if note:
        st.info(note)
    render_tab_stock_picker(gemini_fn=None, candidates=cands,
                            source_label="基本面優選", skip_s3=True)


def test_screener_candidate_to_picker_renders():
    """存活池 → build_candidate_frame → picker 候選 multiselect 真的畫得出來、無 exception。"""
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_function(_screener_flow_script).run(timeout=90)
    assert not at.exception, [f"{e.type}: {str(e.value)[:200]}" for e in at.exception]
    assert len(at.multiselect) >= 1   # 候選勾選框有出現
