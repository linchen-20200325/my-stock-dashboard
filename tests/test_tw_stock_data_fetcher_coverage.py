"""tests/test_tw_stock_data_fetcher_coverage.py — #11-19 測試覆蓋。

Target: src/data/stock/tw_stock_data_fetcher.py (L1 fetcher)

SMOKE + 純函式單元測試。只測 deterministic / pure helpers，**絕不**呼叫
真網路 fetch_* 函式：
  - fuzzy_get_from_df  : DataFrame 別名查找（exact / contains / default）
  - _detect_quarter_cols: 季欄位 regex 偵測
  - parse_goodinfo_table: BeautifulSoup HTML → DataFrame（含括號轉負、逗號去除）
  - calc_financial_metrics: 純比率計算（毛利率/負債比/ROE…+ 零分母 guard）
  - _gi_latest          : graceful no-lxml / 缺欄位 → None（不爆）
  - _goodinfo_url       : URL 組裝
"""
from __future__ import annotations

import pandas as pd
import pytest

from src.data.stock.tw_stock_data_fetcher import (
    FIELD_ALIASES,
    fuzzy_get_from_df,
    _detect_quarter_cols,
    parse_goodinfo_table,
    calc_financial_metrics,
    _gi_latest,
    _goodinfo_url,
)


# ─────────────────────────────────────────────
# §1 import smoke
# ─────────────────────────────────────────────
def test_module_smoke():
    """import 路徑 + 純函式 callable + 別名表存在。"""
    from src.data.stock import tw_stock_data_fetcher as m
    assert callable(m.fuzzy_get_from_df)
    assert callable(m.parse_goodinfo_table)
    assert callable(m.calc_financial_metrics)
    assert callable(m._detect_quarter_cols)
    assert isinstance(FIELD_ALIASES, dict) and "營業收入" in FIELD_ALIASES


# ─────────────────────────────────────────────
# §2 _detect_quarter_cols
# ─────────────────────────────────────────────
class TestDetectQuarterCols:
    def test_basic_quarter_detection(self):
        # 只有 2024Q1 / 2024Q2 命中（西元 4 碼 + Q[1-4]）
        headers = ["科目", "2024Q1", "2024Q2", "TTM"]
        assert _detect_quarter_cols(headers) == [1, 2]

    def test_no_quarter_returns_empty(self):
        assert _detect_quarter_cols(["Field", "Total", "Avg"]) == []

    def test_q5_not_matched(self):
        # Q5 不是合法季（pattern 限 Q[1-4]）
        assert _detect_quarter_cols(["2024Q5", "2024Q3"]) == [1]

    def test_empty_headers(self):
        assert _detect_quarter_cols([]) == []


# ─────────────────────────────────────────────
# §3 fuzzy_get_from_df
# ─────────────────────────────────────────────
class TestFuzzyGetFromDf:
    def test_exact_alias_match_returns_last(self):
        # '營業收入淨額' 是 '營業收入' 的別名；取最後一筆 200.0
        df = pd.DataFrame({"營業收入淨額": [100.0, 200.0]})
        assert fuzzy_get_from_df(df, "營業收入") == 200.0

    def test_contains_substring_match(self):
        # 無精確別名，但欄名含 '存貨' → contains 匹配，取最後一筆
        df = pd.DataFrame({"XX存貨YY": [5.0, 7.0]})
        assert fuzzy_get_from_df(df, "存貨") == 7.0

    def test_default_when_missing(self):
        df = pd.DataFrame({"無關欄位": [1.0]})
        assert fuzzy_get_from_df(df, "存貨", default=-1.0) == -1.0

    def test_default_zero_by_default(self):
        df = pd.DataFrame({"無關欄位": [1.0]})
        assert fuzzy_get_from_df(df, "毛利") == 0.0

    def test_skips_nan_uses_prior_value(self):
        # dropna 後取最後有效值（最後一筆是 NaN → 取前一筆 50.0）
        df = pd.DataFrame({"總資產": [50.0, float("nan")]})
        assert fuzzy_get_from_df(df, "總資產") == 50.0

    def test_all_nan_falls_to_default(self):
        df = pd.DataFrame({"總資產": [float("nan"), float("nan")]})
        assert fuzzy_get_from_df(df, "總資產", default=-9.0) == -9.0

    def test_field_with_no_alias_uses_field_itself(self):
        # 別名表沒有的 field → 用 field 本身當唯一別名
        df = pd.DataFrame({"自訂欄位": [3.0]})
        assert fuzzy_get_from_df(df, "自訂欄位") == 3.0


# ─────────────────────────────────────────────
# §4 parse_goodinfo_table
# ─────────────────────────────────────────────
class TestParseGoodinfoTable:
    _HTML = """
    <table>
    <tr><th>科目</th><th>2024Q1</th><th>2024Q2</th></tr>
    <tr><td>營業收入</td><td>1,000</td><td>1,100</td></tr>
    <tr><td>淨利</td><td>(50)</td><td>120</td></tr>
    </table>
    """

    def test_shape_and_axes(self):
        df = parse_goodinfo_table(self._HTML)
        assert df.shape == (2, 2)
        assert list(df.columns) == ["2024Q1", "2024Q2"]
        assert list(df.index) == ["營業收入", "淨利"]

    def test_comma_stripped(self):
        df = parse_goodinfo_table(self._HTML)
        assert df.loc["營業收入", "2024Q1"] == 1000.0

    def test_parentheses_become_negative(self):
        # (50) → -50.0（會計負數慣例）
        df = parse_goodinfo_table(self._HTML)
        assert df.loc["淨利", "2024Q1"] == -50.0

    def test_no_table_returns_empty(self):
        assert parse_goodinfo_table("<div>no table here</div>").empty

    def test_no_quarter_cols_returns_empty(self):
        html = "<table><tr><th>A</th><th>B</th></tr><tr><td>x</td><td>1</td></tr></table>"
        assert parse_goodinfo_table(html).empty

    def test_single_header_row_returns_empty(self):
        # 只有表頭一列 (<2 rows) → empty
        html = "<table><tr><th>科目</th><th>2024Q1</th></tr></table>"
        assert parse_goodinfo_table(html).empty

    def test_non_numeric_cell_becomes_none(self):
        html = """
        <table>
        <tr><th>科目</th><th>2024Q1</th></tr>
        <tr><td>EPS</td><td>--</td></tr>
        </table>
        """
        df = parse_goodinfo_table(html)
        assert pd.isna(df.loc["EPS", "2024Q1"])


# ─────────────────────────────────────────────
# §5 calc_financial_metrics
# ─────────────────────────────────────────────
class TestCalcFinancialMetrics:
    def _frames(self):
        bs = pd.DataFrame({
            "總資產": [1000.0], "總負債": [400.0],
            "流動資產": [600.0], "流動負債": [300.0],
            "股東權益合計": [600.0], "非流動資產": [400.0],
            "現金及約當現金": [200.0], "存貨": [100.0],
        })
        inc = pd.DataFrame({
            "營業收入": [500.0], "毛利": [150.0],
            "營業利益": [100.0], "淨利": [60.0], "EPS": [3.5],
        })
        cf = pd.DataFrame({
            "營業活動現金流量": [80.0],
            "資本支出": [-30.0],        # CF 表通常為負
            "支付現金股利": [-10.0],
        })
        return bs, inc, cf

    def test_ratios_exact(self):
        bs, inc, cf = self._frames()
        m = calc_financial_metrics(bs, inc, cf)
        assert m["毛利率(%)"] == 30.0          # 150/500
        assert m["營益率(%)"] == 20.0          # 100/500
        assert m["淨利率(%)"] == 12.0          # 60/500
        assert m["負債比率(%)"] == 40.0        # 400/1000
        assert m["流動比率"] == 2.0            # 600/300
        assert m["ROE(%)"] == 10.0             # 60/600

    def test_capex_and_div_abs(self):
        # 資本支出 / 股利支付 取絕對值
        bs, inc, cf = self._frames()
        m = calc_financial_metrics(bs, inc, cf)
        assert m["資本支出(千)"] == 30.0
        assert m["股利支付(千)"] == 10.0
        assert m["營業現金流(千)"] == 80.0

    def test_passthrough_values(self):
        bs, inc, cf = self._frames()
        m = calc_financial_metrics(bs, inc, cf)
        assert m["營業收入(千)"] == 500.0
        assert m["EPS"] == 3.5
        assert m["現金(千)"] == 200.0
        assert m["source"] == "tw_stock_data_fetcher"

    def test_is_finance_flag_passed(self):
        bs, inc, cf = self._frames()
        m = calc_financial_metrics(bs, inc, cf, is_finance=True)
        assert m["is_finance"] is True

    def test_zero_divisor_guards_return_zero_not_raise(self):
        # 空 DataFrame → 所有分母 0 → ratio 回 0.0（不 ÷0 爆炸）
        empty = pd.DataFrame()
        m = calc_financial_metrics(empty, empty, empty)
        assert m["毛利率(%)"] == 0.0
        assert m["負債比率(%)"] == 0.0
        assert m["流動比率"] == 0.0
        assert m["ROE(%)"] == 0.0
        # 缺資料時數值回 default 0.0
        assert m["營業收入(千)"] == 0.0

    def test_zero_revenue_no_divzero(self):
        bs = pd.DataFrame({"總資產": [1000.0], "總負債": [400.0]})
        inc = pd.DataFrame({"營業收入": [0.0], "毛利": [50.0]})
        cf = pd.DataFrame()
        m = calc_financial_metrics(bs, inc, cf)
        assert m["毛利率(%)"] == 0.0  # rev=0 → guard 回 0.0


# ─────────────────────────────────────────────
# §6 _gi_latest — graceful failure (no network)
# ─────────────────────────────────────────────
class TestGiLatest:
    def test_missing_field_returns_none(self):
        # 欄位不存在（或 lxml 缺失導致 read_html 失敗）→ None，不爆
        html = """
        <table>
        <tr><th>科目</th><th>2024Q1</th></tr>
        <tr><td>資產總額</td><td>5,000</td></tr>
        </table>
        """
        assert _gi_latest(html, "不存在的欄位") is None

    def test_garbage_html_returns_none(self):
        # 完全非表格 HTML → None（read_html 無表 / 例外都吞成 None）
        assert _gi_latest("<p>not a table at all</p>", "資產總額") is None


# ─────────────────────────────────────────────
# §7 _goodinfo_url
# ─────────────────────────────────────────────
class TestGoodinfoUrl:
    def test_known_report_type_maps_code(self):
        url = _goodinfo_url("2330", "BS")
        assert "STOCK_ID=2330" in url
        assert "REPORT_TYPE=BALANCE_SHEET" in url

    def test_unknown_report_passes_through(self):
        # 未知 report 直接當 code 用（report_map.get fallback）
        url = _goodinfo_url("2317", "CUSTOM")
        assert "REPORT_TYPE=CUSTOM" in url
        assert "STOCK_ID=2317" in url


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
