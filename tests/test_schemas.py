"""test_schemas.py — pandera schema POC unit tests(v18.397 P5-A5)。

涵蓋:
- import smoke + PANDERA_AVAILABLE 變數
- OHLCVSchema:invariants(low ≤ open/close ≤ high)
- MonthlyRevenueSchema:date 升序 / unique / revenue 正或 NaN
- try_validate wrapper:agree / violation / pandera-not-installed graceful
"""
from __future__ import annotations

import pandas as pd
import pytest

from src.compute.risk.schemas import (
    PANDERA_AVAILABLE,
    OHLCVSchema, MonthlyRevenueSchema, MacroDFSchema,
    PMISchema, ForeignFlowSchema,
    try_validate,
)


def test_module_smoke():
    """import 路徑 + 5 schema instance 存在(installed 才非 None)。
    v18.434 P2 補:PMISchema + ForeignFlowSchema。"""
    from src.compute.risk import schemas
    assert hasattr(schemas, 'PANDERA_AVAILABLE')
    assert hasattr(schemas, 'OHLCVSchema')
    assert hasattr(schemas, 'MonthlyRevenueSchema')
    assert hasattr(schemas, 'MacroDFSchema')
    assert hasattr(schemas, 'PMISchema')
    assert hasattr(schemas, 'ForeignFlowSchema')
    assert callable(schemas.try_validate)


@pytest.mark.skipif(not PANDERA_AVAILABLE, reason='pandera not installed')
class TestOHLCVSchema:
    def _valid_df(self):
        return pd.DataFrame({
            'open':   [100.0, 105.0, 110.0],
            'high':   [102.0, 108.0, 112.0],
            'low':    [99.0, 104.0, 109.0],
            'close':  [101.0, 107.0, 111.0],
            'volume': [10000, 12000, 15000],
        })

    def test_valid(self):
        df = self._valid_df()
        validated = OHLCVSchema.validate(df)
        assert len(validated) == 3

    def test_invariant_low_gt_close_violation(self):
        df = self._valid_df()
        df.loc[0, 'low'] = 200.0  # low > close → 違反
        with pytest.raises(Exception):  # pandera.errors.SchemaError
            OHLCVSchema.validate(df)

    def test_negative_volume_violation(self):
        df = self._valid_df()
        df.loc[1, 'volume'] = -100
        with pytest.raises(Exception):
            OHLCVSchema.validate(df)


@pytest.mark.skipif(not PANDERA_AVAILABLE, reason='pandera not installed')
class TestMonthlyRevenueSchema:
    def test_valid_with_nan(self):
        df = pd.DataFrame({
            'date': pd.to_datetime(['2026-01-31', '2026-02-28', '2026-03-31']),
            'revenue': [1000.0, float('nan'), 1100.0],  # NaN 允許(停業/等公布)
        })
        validated = MonthlyRevenueSchema.validate(df)
        assert len(validated) == 3

    def test_zero_revenue_violation(self):
        df = pd.DataFrame({
            'date': pd.to_datetime(['2026-01-31', '2026-02-28']),
            'revenue': [1000.0, 0.0],  # 0 違反「正或 NaN」
        })
        with pytest.raises(Exception):
            MonthlyRevenueSchema.validate(df)

    def test_date_not_monotonic_violation(self):
        df = pd.DataFrame({
            'date': pd.to_datetime(['2026-02-28', '2026-01-31']),  # 反序
            'revenue': [1000.0, 1100.0],
        })
        with pytest.raises(Exception):
            MonthlyRevenueSchema.validate(df)


@pytest.mark.skipif(not PANDERA_AVAILABLE, reason='pandera not installed')
class TestPMISchema:
    """P2 v18.434 — PMI schema 範圍 + ascending 檢查"""
    def test_valid(self):
        df = pd.DataFrame({
            'date': pd.to_datetime(['2026-01-31', '2026-02-28', '2026-03-31']),
            'value': [50.5, 52.0, 48.3],
        })
        assert len(PMISchema.validate(df)) == 3

    def test_pmi_out_of_range_violation(self):
        df = pd.DataFrame({
            'date': pd.to_datetime(['2026-01-31', '2026-02-28']),
            'value': [50.0, 75.0],  # 75 > PMI_VALID_MAX(70)
        })
        with pytest.raises(Exception):
            PMISchema.validate(df)

    def test_date_descending_violation(self):
        df = pd.DataFrame({
            'date': pd.to_datetime(['2026-02-28', '2026-01-31']),  # 反序
            'value': [50.0, 52.0],
        })
        with pytest.raises(Exception):
            PMISchema.validate(df)


@pytest.mark.skipif(not PANDERA_AVAILABLE, reason='pandera not installed')
class TestForeignFlowSchema:
    """P2 v18.434 — 外資資金流量 schema(可正可負 + 單位 sanity check)"""
    def test_valid_with_negative(self):
        df = pd.DataFrame({
            'date': pd.to_datetime(['2026-06-01', '2026-06-02', '2026-06-03']),
            'foreign_net_yi': [120.5, -85.3, 0.0],  # 正/負/零都合法
        })
        assert len(ForeignFlowSchema.validate(df)) == 3

    def test_unit_confusion_violation(self):
        df = pd.DataFrame({
            'date': pd.to_datetime(['2026-06-01']),
            'foreign_net_yi': [1.5e8],  # 元的單位寫成億 → 爆 9999 上限
        })
        with pytest.raises(Exception):
            ForeignFlowSchema.validate(df)


class TestTryValidate:
    def test_pandera_not_installed_graceful(self):
        if PANDERA_AVAILABLE:
            pytest.skip('pandera installed — 跳過 graceful path test')
        df = pd.DataFrame({'a': [1]})
        result, errors = try_validate(df, OHLCVSchema)
        assert 'pandera not installed' in errors[0]

    @pytest.mark.skipif(not PANDERA_AVAILABLE, reason='pandera not installed')
    def test_valid_input(self):
        df = pd.DataFrame({
            'open':   [100.0], 'high':   [102.0], 'low':    [99.0],
            'close':  [101.0], 'volume': [10000],
        })
        result, errors = try_validate(df, OHLCVSchema)
        assert errors == []
        assert len(result) == 1

    @pytest.mark.skipif(not PANDERA_AVAILABLE, reason='pandera not installed')
    def test_invalid_input_returns_errors(self):
        df = pd.DataFrame({
            'open':   [100.0], 'high':   [102.0], 'low':    [200.0],  # low > open
            'close':  [101.0], 'volume': [10000],
        })
        result, errors = try_validate(df, OHLCVSchema)
        assert len(errors) > 0
        # 原 df 不變(non-raise wrapper)
        assert len(result) == 1
