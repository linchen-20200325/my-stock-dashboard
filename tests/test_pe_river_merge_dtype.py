"""tests/test_pe_river_merge_dtype.py — v18.454 個股「PE 本益比河流圖」MergeError 真回歸修。

production bug(user 回報「個股」分頁渲染異常,已隔離):
    MergeError: incompatible merge keys [0] dtype('<M8[s]') and dtype('<M8[us]'),
    must be the same type

根因(2 個獨立 agent 交叉驗證同一結論):`_render_pe_river()` 的
`pd.merge_asof(_df_p, _df_a, on='date', ...)` 兩側日期欄位精度不同 ——
- `_df_p`(股價側):`df2['date']` 源自 data_loader 的 `.dt.date`(Python date
  object,object dtype),此函式內再用 `pd.to_datetime()` 重新解析 → pandas
  推得 `datetime64[s]`。
- `_df_a`(季報側):`qtr2['date']` 源自 FinMind 字串日期,`pd.to_datetime()`
  解析字串 → pandas 推得 `datetime64[us]`。

兩側從未被顯式對齊精度,pandas merge_asof 要求兩側 key dtype 完全一致
(含精度單位),精度不同即直接拋 MergeError,拖垮整個「個股」分頁
(v18.440 per-tab 隔離器攔到,其他分頁不受影響,但「個股」本身全炸)。

修法:兩側各自 `pd.to_datetime()` 後統一 `.astype('datetime64[ns]')`。

本測試用 AppTest 灌入「刻意製造兩種精度」的真實資料形狀(股價側用
`.dt.date` 物件、季報側用原始字串日期,與生產環境資料源真實形狀一致),
驗證 render_357_valuation_section 呼叫鏈不再 MergeError。
"""
from __future__ import annotations

import datetime

import pandas as pd
import pytest


def _make_price_df(n: int = 260) -> pd.DataFrame:
    """模擬 data_loader 產出的股價 df:'date' 欄為 .dt.date 物件(object dtype)。"""
    _dates = pd.date_range(end=datetime.date.today(), periods=n, freq='B')
    _close = pd.Series([100.0 + i * 0.1 for i in range(n)])
    return pd.DataFrame({
        'date': _dates.date,  # .dt.date 物件陣列(object dtype)— 對齊 data_loader 真實形狀
        'close': _close.values,
        'open': (_close - 0.5).values,
        'high': (_close + 1.0).values,
        'low': (_close - 1.0).values,
        'volume': [1_000_000] * n,
    })


def _make_qtr_df(n_quarters: int = 8) -> pd.DataFrame:
    """模擬 FinMind 季報 df:'date' 欄為原始字串(對齊 data_loader 真實形狀)。"""
    _rows = []
    _year, _q = 2024, 1
    for i in range(n_quarters):
        _q_end = {1: '03-31', 2: '06-30', 3: '09-30', 4: '12-31'}[_q]
        _rows.append({
            '年度': _year, '季度': _q,
            'date': f'{_year}-{_q_end}',  # 原始字串日期 — 對齊 FinMind 真實形狀
            'EPS': 1.5 + i * 0.1,
        })
        _q += 1
        if _q > 4:
            _q = 1
            _year += 1
    return pd.DataFrame(_rows)


class TestMergeDtypeAlignment:
    """純邏輯驗證(不觸網、不需 Streamlit context):兩側日期欄位型別對齊。"""

    def test_price_and_quarterly_dates_have_matching_dtype_after_fix(self):
        """複現生產環境真實資料形狀,驗證兩側 pd.to_datetime + astype 後 dtype 一致。"""
        df2 = _make_price_df()
        qtr2 = _make_qtr_df()

        # 股價側(對齊 section_357_valuation.py 修復後邏輯)
        _rdates_pe = pd.to_datetime(df2['date'], errors='coerce').astype('datetime64[ns]')
        # 季報側
        _announce = (pd.to_datetime(qtr2['date'], errors='coerce')
                      + pd.Timedelta(days=60)).astype('datetime64[ns]')

        assert _rdates_pe.dtype == _announce.dtype, (
            f'兩側日期精度仍不一致:{_rdates_pe.dtype} vs {_announce.dtype}'
        )

    def test_merge_asof_does_not_raise_with_real_shape_data(self):
        """直接重現 production 崩潰條件(未修復前必炸 MergeError),驗證修復後 merge_asof 成功。"""
        df2 = _make_price_df()
        qtr2 = _make_qtr_df()

        _qs = qtr2.sort_values(['年度', '季度']).reset_index(drop=True).copy()
        _qs['ttm_eps'] = pd.to_numeric(_qs['EPS'], errors='coerce').rolling(4, min_periods=4).sum()
        _qs['announce'] = (pd.to_datetime(_qs['date'], errors='coerce')
                            + pd.Timedelta(days=60)).astype('datetime64[ns]')
        _qa = _qs.dropna(subset=['ttm_eps', 'announce']).sort_values('announce').reset_index(drop=True)

        _rdates_pe = pd.to_datetime(df2['date'], errors='coerce').astype('datetime64[ns]').reset_index(drop=True)
        _rclose_pe = pd.to_numeric(df2['close'], errors='coerce').reset_index(drop=True)
        _df_p = pd.DataFrame({'date': _rdates_pe, 'close': _rclose_pe}).sort_values('date').reset_index(drop=True)
        _df_a = _qa[['announce', 'ttm_eps']].rename(columns={'announce': 'date'})

        _merged = pd.merge_asof(_df_p, _df_a, on='date', direction='backward')
        assert not _merged.empty
        assert 'ttm_eps' in _merged.columns

    def test_pre_fix_shapes_would_have_mismatched_dtypes(self):
        """反向確認:若省略 .astype 正規化,兩側精度確實不同(證明本測試有意義,不是巧合一致)。"""
        df2 = _make_price_df()
        qtr2 = _make_qtr_df()
        _rdates_no_fix = pd.to_datetime(df2['date'], errors='coerce')
        _announce_no_fix = pd.to_datetime(qtr2['date'], errors='coerce') + pd.Timedelta(days=60)
        assert _rdates_no_fix.dtype != _announce_no_fix.dtype, (
            '本測試資料形狀未能重現精度不一致情境,測試資料需調整'
        )


@pytest.mark.slow
class TestRenderPeRiverAppTest:
    """實機 render 驗證(需 streamlit.testing.v1.AppTest)。"""

    @classmethod
    def setup_class(cls):
        try:
            from streamlit.testing.v1 import AppTest  # noqa: F401
        except ImportError:
            pytest.skip('streamlit.testing.v1.AppTest 不可用')

    def test_render_357_valuation_section_no_mergeerror(self):
        from streamlit.testing.v1 import AppTest

        df2 = _make_price_df()
        qtr2 = _make_qtr_df()

        _drv = f'''
import sys, os
sys.path.insert(0, os.getcwd())
import streamlit as st
import pandas as pd
import datetime

df2 = pd.DataFrame({df2.to_dict(orient='list')!r})
df2['date'] = pd.to_datetime(df2['date']).dt.date
qtr2 = pd.DataFrame({qtr2.to_dict(orient='list')!r})

from src.ui.tabs.stock_sections.section_357_valuation import render_357_valuation_section
render_357_valuation_section(
    '2330', '台積電', df2, float(df2['close'].iloc[-1]),
    qtr2, [], 0.0, None, {{'div_src': 'test'}},
)
'''
        at = AppTest.from_string(_drv, default_timeout=60)
        at.run()
        if at.exception:
            _msgs = [f'{e.type}: {str(e.value)[:300]}' for e in at.exception]
            pytest.fail('render_357_valuation_section 有 uncaught exception:\n' + '\n'.join(_msgs))


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
