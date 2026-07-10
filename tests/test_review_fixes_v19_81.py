"""tests/test_review_fixes_v19_81.py — 第四份外部 review 查證後修復守護。

TARGET:
- src/data/core/data_loader.py           (A 3 處 volume astype(int) NaN 防炸 + §1 log)
- src/data/stock/tw_stock_data_fetcher.py (C 比率分母 NaN-truthy 防傳染)

查證裁決:其餘主張為已修過/過時或誤判 — 詳 PR 描述。
"""
from __future__ import annotations

import math
from pathlib import Path

import pandas as pd
import pytest

_REPO = Path(__file__).resolve().parents[1]


def _src(rel: str) -> str:
    return (_REPO / rel).read_text(encoding="utf-8")


# ══════════════════════════════════════════════════════════════
# A — data_loader 3 條 K 線路徑 volume NaN → astype(int) 防炸
# ══════════════════════════════════════════════════════════════
class TestVolumeNaNGuard:
    def test_three_sites_fillna_before_astype(self):
        src = _src("src/data/core/data_loader.py")
        # Yahoo(adj) / Yahoo(備援) / FinMind 三處全補 fillna(0)
        assert src.count(".fillna(0) / 1000)") == 3
        # 不再有未防護的 volume 轉張寫法
        assert src.count("'volume'] / 1000)") == 0
        # §1:顯式填補必須 log 受影響筆數
        assert src.count("volume NaN") >= 3

    def test_nan_volume_crashes_without_fillna(self):
        """golden:pandas 對含 NaN 序列 astype(int) 必炸 — 修復存在的理由。"""
        s = pd.Series([1000.0, float("nan"), 3000.0])
        with pytest.raises(ValueError):  # IntCastingNaNError ⊂ ValueError
            (s / 1000).round().astype(int)

    def test_fillna_pattern_yields_zero_for_nan(self):
        """§4.6 語意:停牌/無量日 NaN → 0 張(跌停 0 vol 為有效報價)。"""
        s = pd.Series([1000.0, float("nan"), 3500.0])
        out = (s.fillna(0) / 1000).round().astype(int)
        assert out.tolist() == [1, 0, 4]


# ══════════════════════════════════════════════════════════════
# C — calc_financial_metrics 比率分母 NaN-truthy 防傳染
# ══════════════════════════════════════════════════════════════
class TestNaNSafeDenominators:
    @staticmethod
    def _df(**cols) -> pd.DataFrame:
        return pd.DataFrame({k: [v] for k, v in cols.items()})

    def _calc(self, bs=None, inc=None, cf=None):
        from src.data.stock.tw_stock_data_fetcher import calc_financial_metrics
        empty = pd.DataFrame()
        return calc_financial_metrics(
            bs if bs is not None else empty,
            inc if inc is not None else empty,
            cf if cf is not None else empty,
        )

    def test_happy_path_ratios_unchanged(self):
        inc = self._df(營業收入=1000.0, 毛利=400.0, 營業利益=200.0, 淨利=100.0)
        bs = self._df(總資產=5000.0, 流動資產=2000.0, 總負債=2500.0,
                      流動負債=1000.0, 股東權益合計=2500.0)
        m = self._calc(bs=bs, inc=inc)
        assert m["毛利率(%)"] == pytest.approx(40.0)
        assert m["營益率(%)"] == pytest.approx(20.0)
        assert m["淨利率(%)"] == pytest.approx(10.0)
        assert m["負債比率(%)"] == pytest.approx(50.0)
        assert m["流動比率"] == pytest.approx(2.0)
        assert m["ROE(%)"] == pytest.approx(4.0)

    def test_nan_revenue_no_longer_pollutes_margins(self):
        """MOPS read_html 可回字串 "nan" → fuzzy_get float("nan")=NaN,
        NaN 為 truthy → 舊 `if rev` 擋不住,毛利率=NaN 傳染健康引擎。
        新行為:無效分母 → 0.0(維持既有缺分母語意)。"""
        inc = self._df(營業收入="nan", 毛利=400.0, 營業利益=200.0, 淨利=100.0)
        m = self._calc(inc=inc)
        for key in ("毛利率(%)", "營益率(%)", "淨利率(%)"):
            assert not math.isnan(m[key]), f"{key} 被 NaN 分母傳染"
            assert m[key] == 0.0

    def test_nan_equity_and_assets_guarded(self):
        bs = self._df(總資產="nan", 流動資產=2000.0, 總負債=2500.0,
                      流動負債="nan", 股東權益合計="nan")
        inc = self._df(營業收入=1000.0, 淨利=100.0)
        m = self._calc(bs=bs, inc=inc)
        assert m["負債比率(%)"] == 0.0
        assert m["流動比率"] == 0.0
        assert m["ROE(%)"] == 0.0

    def test_zero_revenue_semantics_unchanged(self):
        inc = self._df(營業收入=0.0, 毛利=400.0)
        m = self._calc(inc=inc)
        assert m["毛利率(%)"] == 0.0
