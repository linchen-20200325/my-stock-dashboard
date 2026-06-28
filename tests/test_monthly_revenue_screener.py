"""tests/test_monthly_revenue_screener.py — v18.180 月營收進退篩選測試

測試重點：
1. compute_yoy_mom 對 15+ 月歷史序列正確計算近 3 月 YoY + 末月 MoM
2. classify_trend 6 種 judgement（strong_up / up / strong_down / down / neutral / insufficient）
3. screen_from_batch 對多股 batch 結果分組計算
4. filter_by_mode 各模式過濾邏輯（含 any_up / any_down 聚合模式）
5. 邊界：缺基期 / 零分母 / 短歷史 graceful
"""
from __future__ import annotations

import pandas as pd
import pytest

from src.ui.tabs import monthly_revenue_screener as mrs


# ════════════════════════════════════════════════════════════════════
# §1 compute_yoy_mom 計算正確性
# ════════════════════════════════════════════════════════════════════
def _mk_series(monthly_revenues: list[float], start_year: int = 2023, start_month: int = 1) -> pd.DataFrame:
    """從月營收 list 造序列；月度自 (start_year, start_month) 起遞增。"""
    rows = []
    y, m = start_year, start_month
    for v in monthly_revenues:
        rows.append({"date": pd.Timestamp(year=y, month=m, day=1), "revenue": v})
        m += 1
        if m > 12:
            m = 1
            y += 1
    return pd.DataFrame(rows)


class TestComputeYoyMom:
    def test_15_months_yoy_last3_correct(self):
        # 12 月基期 = 100 / 110 / 120，當期 = 121 / 132 / 144（皆 +20%）
        base = [100.0, 105.0, 110.0, 115.0, 120.0, 125.0, 130.0, 135.0, 140.0, 145.0, 150.0, 155.0]
        curr = [120.0, 126.0, 132.0]  # vs base[0..2] = 100/105/110
        df = _mk_series(base + curr)
        stats = mrs.compute_yoy_mom(df)
        assert stats["months_available"] == 15
        assert stats["yoy_last3"][0] == pytest.approx(20.0, abs=0.01)  # 120/100-1=20%
        assert stats["yoy_last3"][1] == pytest.approx(20.0, abs=0.01)  # 126/105-1=20%
        assert stats["yoy_last3"][2] == pytest.approx(20.0, abs=0.01)  # 132/110-1=20%

    def test_mom_last_correct(self):
        base = [100.0] * 12
        curr = [110.0, 110.0, 121.0]  # 末月 121 / 上月 110 = +10%
        df = _mk_series(base + curr)
        stats = mrs.compute_yoy_mom(df)
        assert stats["mom_last"] == pytest.approx(10.0, abs=0.01)

    def test_insufficient_history_yoy_none(self):
        # 只有 5 個月 → 無 YoY 基期
        df = _mk_series([100.0] * 5)
        stats = mrs.compute_yoy_mom(df)
        assert all(y is None for y in stats["yoy_last3"])

    def test_empty_df_graceful(self):
        stats = mrs.compute_yoy_mom(pd.DataFrame())
        assert stats["months_available"] == 0
        assert stats["yoy_last3"] == []
        assert stats["mom_last"] is None

    def test_zero_base_no_div_zero(self):
        # 基期為 0 → YoY 應 None 而非 ZeroDivisionError
        base = [0.0] * 12
        curr = [100.0, 100.0, 100.0]
        df = _mk_series(base + curr)
        stats = mrs.compute_yoy_mom(df)
        # 末 3 月對應基期 0 / 0 / 0 → 全 None
        assert all(y is None for y in stats["yoy_last3"])

    def test_last_revenue_returned(self):
        df = _mk_series([50.0, 60.0, 70.0])
        stats = mrs.compute_yoy_mom(df)
        assert stats["last_revenue"] == 70.0


# ════════════════════════════════════════════════════════════════════
# §2 classify_trend 6 種 judgement
# ════════════════════════════════════════════════════════════════════
class TestClassifyTrend:
    def test_strong_up_all_yoy_ge_threshold_mom_positive(self):
        stats = {"yoy_last3": [20.0, 18.0, 22.0], "mom_last": 5.0}
        assert mrs.classify_trend(stats, yoy_threshold=15.0) == "strong_up"

    def test_up_all_yoy_positive_below_threshold(self):
        stats = {"yoy_last3": [5.0, 8.0, 12.0], "mom_last": 2.0}
        assert mrs.classify_trend(stats, yoy_threshold=15.0) == "up"

    def test_strong_down_all_yoy_le_neg_threshold(self):
        stats = {"yoy_last3": [-20.0, -25.0, -18.0], "mom_last": -5.0}
        assert mrs.classify_trend(stats, yoy_threshold=15.0) == "strong_down"

    def test_down_all_yoy_negative_above_threshold(self):
        stats = {"yoy_last3": [-5.0, -8.0, -12.0], "mom_last": -2.0}
        assert mrs.classify_trend(stats, yoy_threshold=15.0) == "down"

    def test_neutral_mixed_yoy(self):
        # YoY 混合 +/− → 中性
        stats = {"yoy_last3": [10.0, -5.0, 8.0], "mom_last": 3.0}
        assert mrs.classify_trend(stats) == "neutral"

    def test_neutral_yoy_up_but_mom_down(self):
        # YoY 全正但 MoM 末月轉負 → 雙條件不滿足
        stats = {"yoy_last3": [10.0, 12.0, 8.0], "mom_last": -3.0}
        assert mrs.classify_trend(stats) == "neutral"

    def test_insufficient_yoy_none(self):
        stats = {"yoy_last3": [None, None, None], "mom_last": 5.0}
        assert mrs.classify_trend(stats) == "insufficient"

    def test_insufficient_mom_none(self):
        stats = {"yoy_last3": [10.0, 12.0, 8.0], "mom_last": None}
        assert mrs.classify_trend(stats) == "insufficient"

    def test_insufficient_partial_yoy_none(self):
        stats = {"yoy_last3": [10.0, None, 8.0], "mom_last": 5.0}
        assert mrs.classify_trend(stats) == "insufficient"

    def test_boundary_yoy_exact_threshold_strong_up(self):
        # 恰等於門檻應算強進步（>=）
        stats = {"yoy_last3": [15.0, 15.0, 15.0], "mom_last": 0.0}
        assert mrs.classify_trend(stats, yoy_threshold=15.0) == "strong_up"

    def test_boundary_mom_exact_zero_up(self):
        # MoM 恰為 0 應算進步（>=）
        stats = {"yoy_last3": [5.0, 5.0, 5.0], "mom_last": 0.0}
        assert mrs.classify_trend(stats) == "up"

    def test_custom_threshold(self):
        stats = {"yoy_last3": [8.0, 10.0, 12.0], "mom_last": 3.0}
        # 門檻 = 7% 全部達標 → strong_up
        assert mrs.classify_trend(stats, yoy_threshold=7.0) == "strong_up"


# ════════════════════════════════════════════════════════════════════
# §3 screen_from_batch 多股分組計算
# ════════════════════════════════════════════════════════════════════
class TestScreenFromBatch:
    def test_two_stocks_split_into_rows(self):
        # 2 股各 3 月（不足 15 月 → 應分類資料不足）
        df_batch = pd.DataFrame([
            {"stock_id": "2330", "date": pd.Timestamp("2024-01-01"), "revenue": 1e10},
            {"stock_id": "2330", "date": pd.Timestamp("2024-02-01"), "revenue": 1.1e10},
            {"stock_id": "2330", "date": pd.Timestamp("2024-03-01"), "revenue": 1.2e10},
            {"stock_id": "2317", "date": pd.Timestamp("2024-01-01"), "revenue": 5e10},
            {"stock_id": "2317", "date": pd.Timestamp("2024-02-01"), "revenue": 5.1e10},
            {"stock_id": "2317", "date": pd.Timestamp("2024-03-01"), "revenue": 5.2e10},
        ])
        result = mrs.screen_from_batch(df_batch)
        assert len(result) == 2
        assert set(result["代碼"].tolist()) == {"2330", "2317"}
        # 3 月資料不足 15 月 → 全部資料不足
        assert all(result["_trend_key"] == "insufficient")

    def test_name_map_attached(self):
        df_batch = pd.DataFrame([
            {"stock_id": "2330", "date": pd.Timestamp("2024-01-01"), "revenue": 1e10},
        ])
        result = mrs.screen_from_batch(df_batch, name_map={"2330": "台積電"})
        assert result.iloc[0]["名稱"] == "台積電"

    def test_revenue_in_yi_unit(self):
        df_batch = pd.DataFrame([
            {"stock_id": "2330", "date": pd.Timestamp("2024-01-01"), "revenue": 1.5e10},
        ])
        result = mrs.screen_from_batch(df_batch)
        # 1.5e10 元 = 150 億
        assert result.iloc[0]["末月營收(億)"] == 150.0

    def test_empty_batch_returns_empty(self):
        result = mrs.screen_from_batch(pd.DataFrame())
        assert result.empty


# ════════════════════════════════════════════════════════════════════
# §4 filter_by_mode 過濾邏輯
# ════════════════════════════════════════════════════════════════════
class TestFilterByMode:
    def _mk_result(self):
        return pd.DataFrame([
            {"代碼": "A", "_trend_key": "strong_up", "YoY(%)": 20.0},
            {"代碼": "B", "_trend_key": "up", "YoY(%)": 5.0},
            {"代碼": "C", "_trend_key": "neutral", "YoY(%)": 0.0},
            {"代碼": "D", "_trend_key": "down", "YoY(%)": -5.0},
            {"代碼": "E", "_trend_key": "strong_down", "YoY(%)": -20.0},
        ])

    def test_mode_strong_up_only(self):
        result = mrs.filter_by_mode(self._mk_result(), "strong_up")
        assert len(result) == 1
        assert result.iloc[0]["代碼"] == "A"

    def test_mode_any_up_includes_strong_up_and_up(self):
        result = mrs.filter_by_mode(self._mk_result(), "any_up")
        assert len(result) == 2
        assert set(result["代碼"].tolist()) == {"A", "B"}

    def test_mode_any_down_includes_strong_down_and_down(self):
        result = mrs.filter_by_mode(self._mk_result(), "any_down")
        assert len(result) == 2
        assert set(result["代碼"].tolist()) == {"D", "E"}

    def test_mode_all_returns_full(self):
        result = mrs.filter_by_mode(self._mk_result(), "all")
        assert len(result) == 5

    def test_empty_df_graceful(self):
        result = mrs.filter_by_mode(pd.DataFrame(), "strong_up")
        assert result.empty


# ════════════════════════════════════════════════════════════════════
# §5 TREND_LABELS 完整性
# ════════════════════════════════════════════════════════════════════
class TestTrendLabels:
    def test_all_6_categories_have_label(self):
        for k in ("strong_up", "up", "strong_down", "down", "neutral", "insufficient"):
            assert k in mrs.TREND_LABELS
            assert mrs.TREND_LABELS[k].strip() != ""


# ════════════════════════════════════════════════════════════════════
# §6 整合：完整 pipeline 強進步 case
# ════════════════════════════════════════════════════════════════════
class TestEndToEnd:
    def test_strong_up_full_pipeline(self):
        # 造一檔 15 月歷史，末 3 月 YoY 都 +20% 以上 + MoM 正
        base = [100.0, 105.0, 110.0, 115.0, 120.0, 125.0, 130.0,
                135.0, 140.0, 145.0, 150.0, 155.0]
        curr = [125.0, 132.0, 145.0]  # vs 100/105/110 = +25/+25.7/+31.8%
        rows = []
        y, m = 2023, 1
        for v in base + curr:
            rows.append({"stock_id": "9999", "date": pd.Timestamp(year=y, month=m, day=1), "revenue": v})
            m += 1
            if m > 12:
                m = 1
                y += 1
        df_batch = pd.DataFrame(rows)
        result = mrs.screen_from_batch(df_batch, yoy_threshold=15.0)
        assert result.iloc[0]["_trend_key"] == "strong_up"

        filtered = mrs.filter_by_mode(result, "any_up")
        assert len(filtered) == 1
