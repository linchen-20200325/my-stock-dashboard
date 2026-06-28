"""v18.328 bugfix 守衛：個股「K 線截止：1970-01-01」假日期回歸防護。

根因：個股 price df 經 reset_index(drop=True)（RangeIndex，日期在 'date' 欄），
原碼 `pd.to_datetime(df.index[-1])` 把整數 index（如 249）當 epoch 納秒
→ Timestamp('1970-01-01 ...')，且非 NaT 致 'date' 欄 fallback 被跳過
→ 資料新鮮度條與側欄健診都顯示「K 線 1970-01-01」假日期（違 §1 寧可炸不可造假）。

修法：canonical `sidebar_health.kline_end_date()` 改為優先 'date' 欄、僅當 index
真為 DatetimeIndex 才用 index、皆不可得回 ""；tab_stock 資料新鮮度條共用之。
"""
from __future__ import annotations

import re

import pandas as pd

from src.ui.pages import kline_end_date


def _real_price_df(last_date="2026-06-26", n=250):
    """重現 fetch_price_data 輸出形狀：RangeIndex + 'date' 欄。"""
    dates = pd.date_range(end=last_date, periods=n, freq="B")
    df = pd.DataFrame({"date": dates, "close": range(n)})
    return df.reset_index(drop=True)  # RangeIndex，日期在 'date' 欄


class TestKlineEndDate:
    def test_rangeindex_with_date_col_uses_date_not_epoch(self):
        """核心回歸：RangeIndex 個股 df 取到真截止日，**絕不**回 1970-01-01。"""
        df = _real_price_df("2026-06-26")
        out = kline_end_date(df)
        assert out == "2026-06-26"
        assert out != "1970-01-01"
        assert not out.startswith("1970")

    def test_datetimeindex_without_date_col_uses_index(self):
        idx = pd.date_range(end="2026-06-26", periods=10, freq="B")
        df = pd.DataFrame({"close": range(10)}, index=idx)
        assert kline_end_date(df) == "2026-06-26"

    def test_rangeindex_without_date_col_returns_empty_not_epoch(self):
        """無 'date' 欄又非 DatetimeIndex → 寧可回 ""（顯示 —），不捏造 1970。"""
        df = pd.DataFrame({"close": range(5)})  # RangeIndex，無 'date'
        assert kline_end_date(df) == ""

    def test_empty_and_none(self):
        assert kline_end_date(None) == ""
        assert kline_end_date(pd.DataFrame()) == ""

    def test_bad_date_value_returns_empty(self):
        df = pd.DataFrame({"date": ["not-a-date"], "close": [1]})
        # errors="coerce" → NaT → ""，不丟例外
        assert kline_end_date(df) == ""


class TestNoBuggyPatternRemains:
    """釘住：兩處消費端都不得再殘留 `to_datetime(...index[-1])` 假日期 antipattern。"""

    def test_tab_stock_uses_shared_helper(self):
        src = open("src/ui/tabs/tab_stock.py", encoding="utf-8").read()
        assert "from src.ui.pages import kline_end_date" in src
        assert "kline_end_date(df2)" in src
        # 舊 bug 變數整段移除（_df_end_date 不得再出現於可執行碼）
        assert "_df_end_date" not in src
        # 舊 buggy 賦值形狀不得殘留（註解提及不算，故釘賦值式）
        assert not re.search(r"_df_end_date\s*=\s*pd\.to_datetime", src)

    def test_sidebar_health_helper_guards_datetimeindex(self):
        src = open("src/ui/pages/sidebar_health.py", encoding="utf-8").read()
        assert "def kline_end_date(" in src
        assert "DatetimeIndex" in src  # 僅當真 DatetimeIndex 才用 index
        assert "_kline_end_date" not in src  # 舊私有名已退役
