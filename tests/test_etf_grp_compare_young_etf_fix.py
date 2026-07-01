"""tests/test_etf_grp_compare_young_etf_fix.py — v18.452 ETF 多檔比較表 2 處真 bug 修。

production bug(user 截圖「ETF 多檔比較」表,00981A.TW / 0050.TW 兩列全指出「這都錯誤」):

1. 名稱欄:`_fetch_one_etf` 只用 yfinance `.info` 的 shortName/longName,對台股 ETF
   常回發行商英文名(而非商品名),與已存在的 SSOT `fetch_etf_zh_name()`(MoneyDJ 中文
   名,etf_tab_single.py 早已採用)不一致 —— 同一系統兩個 Tab 對同一檔 ETF 顯示不同名稱。

2. 「3Y CAGR%」/「5Y均殖%」:年輕 ETF(如上市僅 13 個月)實際資料跨度遠不足宣稱的
   3/5 年,但 calc_cagr/calc_avg_yield 舊版不知道呼叫端「宣稱」的年期,照樣外推/局部
   平均,產生統計上不可能的數字(如 191% 3Y CAGR)並貼上「3Y/5Y」標籤誤導使用者。

修法:
- `_fetch_one_etf` 中文名優先呼叫既有 SSOT `fetch_etf_zh_name()`(§8.2 沿用既有函式,
  不新增重複邏輯),fallback 至 yfinance → ticker,對齊 etf_tab_single.py 既有寫法。
- `calc_cagr(df, expected_years=N)` / `calc_avg_yield(df, divs, years=N,
  require_full_years=True)` 新增可選嚴格模式:實際資料跨度不足宣稱年期時回 None
  (§1 寧缺勿假),而非外推假數字。兩個新參數皆預設為舊行為(None / False),不破壞
  既有呼叫端。
"""
from __future__ import annotations

import datetime

import pandas as pd
import pytest

import src.ui.etf.etf_tab_grp_compare as grp
from src.compute.etf.etf_calc import calc_avg_yield, calc_cagr, calc_total_return_1y


def _price_df(n_days: int) -> pd.DataFrame:
    idx = pd.date_range(end=datetime.date.today(), periods=n_days, freq='D')
    return pd.DataFrame({'Close': [100.0 + i * 0.05 for i in range(n_days)]}, index=idx)


def _divs_1_year_only() -> pd.Series:
    """只在最近 1 年內有配息紀錄(模擬剛上市 ETF,無 2~5 年前的配息資料)。"""
    now = datetime.date.today()
    dates = pd.to_datetime([now - datetime.timedelta(days=d) for d in (30, 120, 210, 300)])
    return pd.Series([1.0, 1.0, 1.0, 1.0], index=dates)


def _divs_5_years() -> pd.Series:
    """5 個完整年度桶皆有配息(模擬老牌 ETF,如 0050)。"""
    now = datetime.date.today()
    dates, vals = [], []
    for y in range(5):
        dates.append(pd.Timestamp(now) - pd.Timedelta(days=365 * y + 60))
        vals.append(1.0)
    return pd.Series(vals, index=pd.DatetimeIndex(dates))


# ── A. calc_cagr / calc_avg_yield 嚴格模式行為 ──────────────────────

class TestCagrExpectedYears:
    def test_short_window_claiming_3y_returns_none(self):
        """13 個月資料,宣稱 3Y → 應回 None,不得外推假 CAGR。"""
        df = _price_df(395)
        assert calc_cagr(df, expected_years=3) is None

    def test_full_3y_window_computes_real_value(self):
        """實際跨度 ≥ 3 年(容差內)→ 應正常算出數值,不誤殺老牌 ETF。"""
        df = _price_df(1200)  # ~3.3 年
        r = calc_cagr(df, expected_years=3)
        assert r is not None
        assert isinstance(r, float)

    def test_backward_compat_no_expected_years(self):
        """未傳 expected_years(舊呼叫端)→ 維持舊行為,13 個月窗口仍外推出數值。"""
        df = _price_df(395)
        r = calc_cagr(df)
        assert r is not None and r != 0.0


class TestAvgYieldRequireFullYears:
    def test_young_etf_partial_years_returns_none(self):
        """配息只涵蓋 1 個年度桶,宣稱 5Y 平均且 require_full_years=True → 應回 None。"""
        df = _price_df(400)
        divs = _divs_1_year_only()
        assert calc_avg_yield(df, divs, years=5, require_full_years=True) is None

    def test_full_5_years_computes_real_value(self):
        """5 個年度桶皆有資料 → 正常算出平均殖利率,不誤殺老牌 ETF。"""
        df = _price_df(1900)  # ~5.2 年
        divs = _divs_5_years()
        r = calc_avg_yield(df, divs, years=5, require_full_years=True)
        assert r is not None and r > 0

    def test_backward_compat_default_false(self):
        """require_full_years 預設 False → 維持舊行為(局部年度桶仍會平均出數字)。"""
        df = _price_df(400)
        divs = _divs_1_year_only()
        r = calc_avg_yield(df, divs, years=5)
        assert r is not None and r != 0.0


class TestTotalReturn1yRequireFullPeriod:
    """v18.454:年輕 ETF「1Y累積%」不得把上市至今報酬誤標為 1 年報酬(user 截圖
    00981A 顯示「1Y累積 212.26%」—— 上市僅 13 個月,p_start 實為上市首日低價)。"""

    def test_young_etf_short_history_returns_none(self):
        """實際資料跨度僅 300 天(< 365 天的 90% = 328.5 天)+ require_full_period=True
        → 應回 None,不得把「上市至今報酬」誤標為「1Y累積」。"""
        df = _price_df(300)
        divs = pd.Series(dtype=float)
        r = calc_total_return_1y(df, divs, require_full_period=True)
        assert r is None, f'資料跨度僅 300 天(<365*90%),不應算出 1Y 報酬:{r}'

    def test_mature_etf_full_history_computes_real_value(self):
        """資料跨度 ≥ 365 天(容差內)→ 正常算出數值,不誤殺老牌 ETF。"""
        df = _price_df(500)
        divs = pd.Series(dtype=float)
        r = calc_total_return_1y(df, divs, require_full_period=True)
        assert r is not None

    def test_backward_compat_default_false(self):
        """require_full_period 預設 False → 維持舊行為(短窗仍會算出數字)。"""
        df = _price_df(300)
        divs = pd.Series(dtype=float)
        r = calc_total_return_1y(df, divs)
        assert r is not None and r != 0.0


# ── B. _fetch_one_etf 名稱來源 + 端到端布線 ──────────────────────

class _FakeQuality(dict):
    pass


def _patch_fetch_one_etf_deps(monkeypatch, *, df, divs, info, zh_name):
    monkeypatch.setattr(grp, 'fetch_etf_price', lambda ticker, period='5y': df)
    monkeypatch.setattr(grp, 'fetch_etf_dividends', lambda ticker: divs)
    monkeypatch.setattr(grp, 'fetch_etf_info', lambda ticker: info)
    monkeypatch.setattr(grp, '_fetch_zh_n', lambda ticker: zh_name)
    monkeypatch.setattr(grp, 'compute_etf_quality', lambda ticker: {'stars': None, '_err': 'skip-network'})
    monkeypatch.setattr(grp, 'calc_premium_discount', lambda info, df, ticker: {})
    monkeypatch.setattr(grp, 'calc_liquidity_score', lambda df, aum: {})
    monkeypatch.setattr(grp, 'auto_detect_benchmark', lambda ticker: None)


class TestFetchOneEtfNameFix:
    def test_uses_moneydj_zh_name_over_yfinance_english_name(self, monkeypatch):
        """production bug 核心:yfinance shortName 回發行商英文名,MoneyDJ 中文名才是
        商品名 —— 有 zh_name 時必須採用,不得顯示 yfinance 的名稱。"""
        _patch_fetch_one_etf_deps(
            monkeypatch, df=_price_df(1900), divs=_divs_5_years(),
            info={'shortName': 'Yuanta Taiwan Top 50 ETF'},
            zh_name='元大台灣50',
        )
        r = grp._fetch_one_etf('0050.TW')
        assert r['name'] == '元大台灣50'
        assert 'Yuanta' not in r['name']

    def test_falls_back_to_yfinance_when_moneydj_misses(self, monkeypatch):
        """MoneyDJ 抓不到(回 None)時,須 fallback 至 yfinance,不得整欄空白。"""
        _patch_fetch_one_etf_deps(
            monkeypatch, df=_price_df(1900), divs=_divs_5_years(),
            info={'shortName': 'Some ETF Name'},
            zh_name=None,
        )
        r = grp._fetch_one_etf('9999.TW')
        assert r['name'] == 'Some ETF Name'

    def test_young_etf_cagr_and_avg_yield_are_none_not_fake_numbers(self, monkeypatch):
        """production bug 核心:年輕 ETF(13 個月資料)不得顯示假「3Y CAGR」/「5Y均殖」。"""
        _patch_fetch_one_etf_deps(
            monkeypatch, df=_price_df(395), divs=_divs_1_year_only(),
            info={'shortName': 'Young Active ETF'}, zh_name='主動新進 ETF',
        )
        r = grp._fetch_one_etf('00981A.TW')
        assert r['cagr_3y'] is None, f'年輕 ETF 不應有 3Y CAGR 數字:{r["cagr_3y"]}'
        assert r['avg_yield_5y'] is None, f'年輕 ETF 不應有 5Y均殖數字:{r["avg_yield_5y"]}'

    def test_mature_etf_cagr_and_avg_yield_still_populate(self, monkeypatch):
        """老牌 ETF(5+ 年資料)修復後仍應正常顯示數值,不誤殺。"""
        _patch_fetch_one_etf_deps(
            monkeypatch, df=_price_df(1900), divs=_divs_5_years(),
            info={'shortName': 'Mature ETF'}, zh_name='老牌 ETF',
        )
        r = grp._fetch_one_etf('0050.TW')
        assert r['cagr_3y'] is not None
        assert r['avg_yield_5y'] is not None

    def test_young_etf_1y_return_is_none_not_fake_212pct(self, monkeypatch):
        """v18.454:年輕 ETF(資料跨度僅 300 天,<365*90%)不得顯示假「1Y累積%」
        (user 截圖 00981A 顯示「1Y累積 212.26%」—— 實為上市至今報酬,非真 1 年報酬)。"""
        _patch_fetch_one_etf_deps(
            monkeypatch, df=_price_df(300), divs=pd.Series(dtype=float),
            info={'shortName': 'Young Active ETF'}, zh_name='主動新進 ETF',
        )
        r = grp._fetch_one_etf('00981A.TW')
        assert r['total_ret_1y'] is None, (
            f'資料跨度僅 300 天,不應顯示 1Y累積% 數字:{r["total_ret_1y"]}'
        )

    def test_mature_etf_1y_return_still_populates(self, monkeypatch):
        """老牌 ETF(資料跨度 ≥ 365 天)修復後仍應正常顯示 1Y 累積%,不誤殺。"""
        _patch_fetch_one_etf_deps(
            monkeypatch, df=_price_df(1900), divs=_divs_5_years(),
            info={'shortName': 'Mature ETF'}, zh_name='老牌 ETF',
        )
        r = grp._fetch_one_etf('0050.TW')
        assert r['total_ret_1y'] is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
