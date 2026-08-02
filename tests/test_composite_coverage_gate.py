"""選股網綜合分「最低因子涵蓋門檻」測試(A 修,2026-08)。

背景:v19.90「綜合分只平均有資料因子」修掉了「缺料灌 0 拖垮」的舊 bug,但走到另一極端
——缺料完全不罰,只要唯一有資料的因子夠高就封頂。user 2026-08 實測:2061 風青勾了
估值+缺貨+RS 三因子,只有 RS=100,綜合分卻 100 排第一,贏過兩因子都有的股。

修法(A 最低涵蓋門檻):一檔需「有資料的勾選因子 > 勾選因子數 × 0.5」(嚴格過半)才進
綜合排序,否則綜合分 None 排最後。SSOT = SCREENER_MIN_FACTOR_COVERAGE_RATIO。
分母用「全域實際有資料的勾選因子」——某因子完全沒掃到時不算(不因『勾了沒掃』清空全榜)。

3 個最容易出錯的輸入:1-of-2 邊界、勾了但全域沒掃的因子、全因子皆缺的股。
"""
from __future__ import annotations

import pandas as pd

from src.services.fundamental_screener_service import composite_rank_candidates
from shared.signal_thresholds import SCREENER_MIN_FACTOR_COVERAGE_RATIO


def _surv(ids, eps=None):
    return pd.DataFrame({"stock_id": ids, "eps": eps if eps is not None else [1] * len(ids)})


# ── SSOT 常數 ────────────────────────────────────────────────────────────────
def test_ssot_ratio_is_half():
    assert SCREENER_MIN_FACTOR_COVERAGE_RATIO == 0.5


# ── 核心情境:2061 只有 RS → 不再衝頂 ──────────────────────────────────────────
def test_single_factor_stock_gated_out_3factors():
    """3 因子勾選;2061 只有 RS(=100)→ 未過半(需≥2)→ 綜合分 None,不再排第一。"""
    surv = _surv(["2061", "2248", "5538"])
    df, note = composite_rank_candidates(
        surv,
        factors=["pe_low", "shortage", "rs_leader"],
        pe_map={"2248": 10, "5538": 20},                       # 2061 無估值
        shortage_rows=[{"代碼": "5538", "缺貨分數": 80}],       # 只有 5538 有缺貨
        rs_rows=[{"代碼": "2061", "RS(σ)": 3.0},               # 2061 RS 最高 → 100
                 {"代碼": "2248", "RS(σ)": 2.0},
                 {"代碼": "5538", "RS(σ)": 1.0}],
    )
    _score = {r["代碼"]: r["綜合分"] for _, r in df.iterrows()}
    # 2061:只有 RS(1/3 因子)→ 未過半 → 綜合分 None
    assert pd.isna(_score["2061"])
    # 2061 的 RS 分仍顯示(=100,證明「有 RS 高分但不進綜合」)
    _rs_2061 = df[df["代碼"] == "2061"]["RS分"].iloc[0]
    assert _rs_2061 == 100.0
    # 有效股(≥2 因子)排在被門檻擋下的 2061 之前
    assert list(df["代碼"])[-1] == "2061"
    assert not pd.isna(_score["2248"]) and not pd.isna(_score["5538"])
    # 涵蓋門檻提示(1 檔被擋)
    assert "涵蓋" in note and "1 檔" in note


def test_two_of_three_passes():
    """2-of-3 因子 → 過半(2 > 1.5)→ 進榜,綜合分 = 兩因子平均。"""
    df, _ = composite_rank_candidates(
        _surv(["X"]),
        factors=["pe_low", "shortage", "rs_leader"],
        pe_map={"X": 10},
        rs_rows=[{"代碼": "X", "RS(σ)": 1.0}],
        shortage_rows=[{"代碼": "OTHER", "缺貨分數": 1}],  # 缺貨全域有資料但 X 無
    )
    _x = df[df["代碼"] == "X"]["綜合分"].iloc[0]
    assert not pd.isna(_x)   # X 有 估值 + RS = 2/3 → 進榜


# ── 2 因子:1-of-2 也擋(對應 user 更早『估值+RS』那張截圖)──────────────────────
def test_one_of_two_gated_out():
    """2 因子勾選;只有 1 個有資料 → 需 2(過半嚴格 >1)→ None。"""
    df, note = composite_rank_candidates(
        _surv(["ONLY_RS", "BOTH"]),
        factors=["pe_low", "rs_leader"],
        pe_map={"BOTH": 12},                                   # ONLY_RS 無估值
        rs_rows=[{"代碼": "ONLY_RS", "RS(σ)": 2.0},
                 {"代碼": "BOTH", "RS(σ)": 1.0}],
    )
    _score = {r["代碼"]: r["綜合分"] for _, r in df.iterrows()}
    assert pd.isna(_score["ONLY_RS"])       # 1/2 → 擋下
    assert not pd.isna(_score["BOTH"])      # 2/2 → 進榜
    assert list(df["代碼"]) == ["BOTH", "ONLY_RS"]
    assert "涵蓋" in note


def test_two_of_two_passes():
    df, note = composite_rank_candidates(
        _surv(["A", "B"]),
        factors=["pe_low", "rs_leader"],
        pe_map={"A": 8, "B": 30},
        rs_rows=[{"代碼": "A", "RS(σ)": 1.0}, {"代碼": "B", "RS(σ)": 2.0}],
    )
    assert not df["綜合分"].isna().any()   # 兩檔皆 2/2 → 都進榜
    assert "涵蓋" not in note              # 無人被擋


# ── 1 因子:維持原行為(不因門檻誤擋)────────────────────────────────────────────
def test_single_ticked_factor_unchanged():
    """只勾 1 因子 → 門檻 = 0.5*1 = 0.5,有該因子(1 > 0.5)即進榜(原行為不變)。"""
    df, note = composite_rank_candidates(
        _surv(["A", "B", "C"], [1, 9, 5]), factors=["eps_high"])
    assert list(df["代碼"]) == ["B", "C", "A"]   # 純 EPS 排序
    assert not df["綜合分"].isna().any()
    assert "涵蓋" not in note


# ── edge:勾了但全域沒掃的因子 → 不清空全榜 ─────────────────────────────────────
def test_unscanned_factor_not_counted_in_denominator():
    """勾 eps+shortage 但 shortage 未掃(rows=None)→ shortage 不算門檻分母 →
    只有 eps 的股仍進榜(不被『勾了沒掃的因子』清空)。"""
    df, note = composite_rank_candidates(
        _surv(["A", "B"], [3, 1]),
        factors=["eps_high", "shortage"], shortage_rows=None)
    assert not df["綜合分"].isna().any()        # 兩檔都靠 eps 進榜
    assert list(df["代碼"]) == ["A", "B"]
    assert "尚未掃描" in note                    # 仍有「缺貨未掃」提示
    assert "涵蓋未過半" not in note              # 但沒有人因涵蓋被擋


# ── edge:全勾選因子皆缺的股 → None(本就如此,非新擋下,不計入涵蓋提示數)──────────
def test_all_factors_missing_still_none():
    df, note = composite_rank_candidates(
        _surv(["HAS", "NONE"]),
        factors=["pe_low", "rs_leader"],
        pe_map={"HAS": 10},
        rs_rows=[{"代碼": "HAS", "RS(σ)": 1.0}])
    _score = {r["代碼"]: r["綜合分"] for _, r in df.iterrows()}
    assert pd.isna(_score["NONE"])          # 兩因子皆無 → None
    assert not pd.isna(_score["HAS"])       # 2/2 → 進榜
    # NONE 是「全無資料」(非「有部分但不足過半」)→ 不計入涵蓋門檻提示數
    assert "涵蓋" not in note
