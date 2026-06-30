"""tests/test_chip_concentration_fetcher_coverage.py — L1 籌碼濃度 fetcher 純解析輔助測試。

對應 src/data/stock/chip_concentration_fetcher.py 的純函式:
- _flatten_cols  (MultiIndex / 單層欄名攤平 + trim)
- _to_num        ('12.3%' / '1,234' / '-' → float/NaN)
- _find_col      (關鍵字找欄)
- _find_major_col(大戶比例欄優先序)
- _parse_date_series (一般解析 + %Y%m%d 退路)
- _adaptive_parse(多表挑「股權分散時序」抽三欄)
- _table_diag    (輕量診斷壓縮)

全部以 crafted in-memory DataFrame/值測試,**不觸網**(不呼叫 fetch_chip_concentration 的網路路徑)。
"""
from __future__ import annotations

import math

import pandas as pd
import pytest

from src.data.stock.chip_concentration_fetcher import (
    TWSTHR_URL,
    _UA_POOL,
    _adaptive_parse,
    _find_col,
    _find_major_col,
    _flatten_cols,
    _parse_date_series,
    _table_diag,
    _to_num,
)


class TestConstants:
    def test_url_template_has_ticker_placeholder(self):
        assert '{ticker}' in TWSTHR_URL
        assert TWSTHR_URL.format(ticker='2330').endswith('stock=2330')

    def test_ua_pool_non_empty_strings(self):
        assert isinstance(_UA_POOL, tuple) and len(_UA_POOL) >= 1
        assert all(isinstance(u, str) and 'Mozilla' in u for u in _UA_POOL)


class TestFlattenCols:
    def test_single_level_strips_whitespace(self):
        df = pd.DataFrame({'  date ': [1], 'value  ': [2]})
        out = _flatten_cols(df)
        assert list(out.columns) == ['date', 'value']

    def test_multiindex_joined_with_space(self):
        cols = pd.MultiIndex.from_tuples([('大戶', '比例'), ('日期', '')])
        df = pd.DataFrame([[1, 2]], columns=cols)
        out = _flatten_cols(df)
        # ('日期','') 的空字串會被 join 後 strip → '日期'
        assert list(out.columns) == ['大戶 比例', '日期']

    def test_multiindex_drops_nan_and_none_tokens(self):
        cols = pd.MultiIndex.from_tuples([('A', 'nan'), ('B', 'None')])
        df = pd.DataFrame([[1, 2]], columns=cols)
        out = _flatten_cols(df)
        assert list(out.columns) == ['A', 'B']

    def test_does_not_mutate_input(self):
        df = pd.DataFrame({' x ': [1]})
        _ = _flatten_cols(df)
        # 原 df 欄名不被改動(copy 語義)
        assert list(df.columns) == [' x ']


class TestToNum:
    def test_percent_string(self):
        assert _to_num('12.3%') == pytest.approx(12.3)

    def test_thousands_separator(self):
        assert _to_num('1,234') == pytest.approx(1234.0)

    def test_surrounding_whitespace(self):
        assert _to_num(' 56 ') == pytest.approx(56.0)

    def test_negative_value(self):
        assert _to_num('-4.5%') == pytest.approx(-4.5)

    @pytest.mark.parametrize('bad', ['', 'nan', 'None', '-', '--', 'abc'])
    def test_unparseable_returns_nan(self, bad):
        assert math.isnan(_to_num(bad))

    def test_numeric_input_passthrough(self):
        assert _to_num(42) == pytest.approx(42.0)
        assert _to_num(3.14) == pytest.approx(3.14)


class TestFindCol:
    def test_returns_first_keyword_match(self):
        cols = ['日期', '大戶持股比例', '散戶人數']
        assert _find_col(cols, ('比例',)) == '大戶持股比例'

    def test_no_match_returns_none(self):
        assert _find_col(['a', 'b'], ('比例',)) is None

    def test_matches_any_of_multiple_keywords(self):
        cols = ['股東人數']
        assert _find_col(cols, ('散戶', '人數')) == '股東人數'


class TestFindMajorCol:
    def test_pass1_major_plus_ratio_preferred(self):
        # 同時存在純大戶欄與大戶+比例欄 → 選後者
        cols = ['日期', '大戶張數', '大戶持股比例']
        assert _find_major_col(cols) == '大戶持股比例'

    def test_pass2_falls_back_to_pure_major_keyword(self):
        # 沒有比例字樣,退而求其次回大戶關鍵字欄
        cols = ['日期', '>400張大股東']
        assert _find_major_col(cols) == '>400張大股東'

    def test_percent_sign_counts_as_ratio(self):
        cols = ['集中度%']
        assert _find_major_col(cols) == '集中度%'

    def test_none_when_no_major_keyword(self):
        assert _find_major_col(['日期', '收盤價']) is None


class TestParseDateSeries:
    def test_standard_iso_dates(self):
        s = pd.Series(['2026-01-31', '2026-02-28'])
        out = _parse_date_series(s)
        assert out.notna().all()
        assert out.iloc[0] == pd.Timestamp('2026-01-31')

    def test_yyyymmdd_digit_fallback(self):
        # 純數字 8 碼 → 走 %Y%m%d 退路
        s = pd.Series(['20260131', '20260228', '20260331'])
        out = _parse_date_series(s)
        assert out.notna().all()
        assert out.iloc[2] == pd.Timestamp('2026-03-31')

    def test_garbage_yields_nat(self):
        s = pd.Series(['xxx', 'yyy'])
        out = _parse_date_series(s)
        assert out.isna().all()


class TestAdaptiveParse:
    def _timeseries_table(self):
        # 模擬 twsthr 時序表:read_html 未抓表頭 → 整數欄名,首列為真實表頭
        return pd.DataFrame([
            ['資料日期', '>400張大股東持有百分比', '50張以下小股東人數'],
            ['2026-01-03', '70.5%', '12,345'],
            ['2026-01-10', '71.2%', '12,100'],
            ['2026-01-17', '69.8%', '12,500'],
        ])

    def test_extracts_three_columns_sorted(self):
        out = _adaptive_parse([self._timeseries_table()])
        assert list(out.columns) == ['日期', '大戶比例', '散戶人數']
        assert len(out) == 3
        # 日期升序
        assert out['日期'].is_monotonic_increasing
        assert out['大戶比例'].iloc[0] == pytest.approx(70.5)
        assert out['散戶人數'].iloc[0] == pytest.approx(12345.0)

    def test_named_header_table(self):
        # 欄名直接命名(非整數索引)亦能解析
        df = pd.DataFrame({
            '資料日期': ['2026-01-03', '2026-01-10'],
            '大股東持股比例': ['65.0%', '66.0%'],
            '小股東人數': ['1,000', '1,100'],
        })
        out = _adaptive_parse([df])
        assert len(out) == 2
        assert out['大戶比例'].tolist() == pytest.approx([65.0, 66.0])

    def test_picks_best_among_multiple_tables(self):
        noise = pd.DataFrame({'隨機欄A': [1, 2], '隨機欄B': [3, 4]})
        good = self._timeseries_table()
        out = _adaptive_parse([noise, good])
        # 應挑出時序表而非雜訊表
        assert len(out) == 3
        assert '大戶比例' in out.columns

    def test_empty_table_list_returns_empty(self):
        out = _adaptive_parse([])
        assert isinstance(out, pd.DataFrame) and out.empty

    def test_table_without_major_or_retail_returns_empty(self):
        df = pd.DataFrame({'日期': ['2026-01-03'], '收盤價': ['100']})
        out = _adaptive_parse([df])
        assert out.empty

    def test_drops_rows_with_both_values_missing(self):
        df = pd.DataFrame({
            '資料日期': ['2026-01-03', '2026-01-10'],
            '大股東持股比例': ['70.0%', '-'],
            '小股東人數': ['1,000', '--'],
        })
        out = _adaptive_parse([df])
        # 第二列兩數值皆缺 → 被丟棄
        assert len(out) == 1
        assert out['大戶比例'].iloc[0] == pytest.approx(70.0)

    def test_skips_too_narrow_table(self):
        # 只有 1 欄(< 2)應被跳過 → 整體無可用表 → 空
        narrow = pd.DataFrame({'大戶比例': ['70%']})
        out = _adaptive_parse([narrow])
        assert out.empty


class TestTableDiag:
    def test_diag_structure(self):
        df = pd.DataFrame({' a ': [1, 2, 3], 'b': [4, 5, 6]})
        diag = _table_diag([df])
        assert len(diag) == 1
        entry = diag[0]
        assert entry['idx'] == 0
        assert entry['shape'] == [3, 2]
        # 欄名經 _flatten_cols trim
        assert entry['columns'] == ['a', 'b']
        assert isinstance(entry['preview'], pd.DataFrame)

    def test_preview_capped_at_five_rows(self):
        df = pd.DataFrame({'x': list(range(10))})
        diag = _table_diag([df])
        assert len(diag[0]['preview']) == 5


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
