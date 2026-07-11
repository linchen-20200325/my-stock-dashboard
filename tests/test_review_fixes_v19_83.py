"""v19.83 — 第六份外部 review 查證後修復的回歸測試。

對應修復（查證屬實才修,詳見 STATE.md v19.83）:
1. data_loader get_quarterly_data:恆真 `True if ... else True` + 月加總欄名
   KeyError(get_monthly_revenue 契約是 date/revenue,原寫死 年/月/營收)
2. tab_stock 寫入 t2_shares_{sid}(V4 外本比分母原永遠 fallback 1,000,000 張)
3. calc_vcp 補 try/except(契約「失敗回 None」,原缺 high/low 或 0 價位會炸)
4. etf_fetch NAV 狀態排除清單補 '429'
5. compute_yoy_mom 改「去年同月」日曆對齊(原位置索引 -12 缺月會錯基期)
6. FinMind token 前綴不再印入 log
7. proxy_helper _URL_CACHE 上限 + 過期逐出(原無上限單調增長)
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parent.parent


# ══════════════════════════════════════════════════════════════
# 1. get_quarterly_data 金融股判定 + 月加總欄名契約
# ══════════════════════════════════════════════════════════════
class TestQuarterlyFinanceGate:
    def _src(self):
        return (REPO / "src/data/core/data_loader.py").read_text(encoding="utf-8")

    def test_tautology_removed(self):
        """恆真 `True if finance_candidates else True` 必須不存在。"""
        src = self._src()
        assert "True if finance_candidates else True" not in src
        assert "is_finance = bool(finance_candidates)" in src

    def test_monthly_agg_uses_contract_columns(self):
        """月加總 fallback 必須用 get_monthly_revenue 實際契約欄位(date/revenue),
        不可寫死 年/月/營收(該欄名組合從未存在 → KeyError → 整檔季報全滅)。"""
        src = self._src()
        assert "df_month[['年', '月', '營收']]" not in src
        # 雙名容錯偵測必須存在
        assert "'date' if 'date' in df_month.columns" in src
        assert "'revenue' if 'revenue' in df_month.columns" in src

    def test_no_pd_na_revenue_fallback(self):
        """無任何營收欄時營收 fallback 必須是 float nan(pd.NA object 會讓
        `(營收<0).any()` 拋 TypeError)。"""
        src = self._src()
        assert "df_quarterly['營收'] = pd.NA" not in src


# ══════════════════════════════════════════════════════════════
# 2. V4 外本比分母:t2_shares 寫入
# ══════════════════════════════════════════════════════════════
class TestV4SharesWrite:
    def test_tab_stock_writes_t2_shares(self):
        src = (REPO / "src/ui/tabs/tab_stock.py").read_text(encoding="utf-8")
        assert "st.session_state[f't2_shares_{sid2}']" in src, \
            "t2_shares_{sid} 必須有寫入處(原全 repo 只有讀取,分母永遠是預設 1,000,000)"
        assert "_cap_v4 / 10000" in src, "股本(元)→張數換算須為 /10(面額)/1000(股/張)=/10000"

    def test_capital_to_lots_formula(self):
        """台積電股本 ~2,593 億元 → 25,932,138 張(數量級 sanity)。"""
        _cap_twd = 259_321_385_180.0
        _lots = int(_cap_twd / 10000)
        assert 25_000_000 < _lots < 27_000_000

    def test_reader_default_unchanged(self):
        """section_health_score 讀取端 fallback 1,000,000 不動(§1:股本抓不到時不虛構)。"""
        src = (REPO / "src/ui/tabs/stock_sections/section_health_score.py").read_text(
            encoding="utf-8")
        assert "st.session_state.get(f't2_shares_{sid2}', 1000000)" in src


# ══════════════════════════════════════════════════════════════
# 3. calc_vcp 契約:失敗回 None 不炸
# ══════════════════════════════════════════════════════════════
class TestCalcVcpContract:
    def _mk_df(self, n=60):
        highs = [100.0 + i * 0.01 for i in range(n)]
        lows = [90.0 + i * 0.01 for i in range(n)]
        return pd.DataFrame({"high": highs, "low": lows})

    def test_missing_columns_returns_none(self):
        from src.compute.strategy.tech_indicators import calc_vcp
        df = pd.DataFrame({"close": [100.0] * 60})   # 無 high/low
        assert calc_vcp(df) is None   # 原本 KeyError 直接炸

    def test_zero_price_swing_returns_none(self):
        """swing 價位 0(壞 tick)→ 契約仍須回 None 不炸。

        註:numpy float ÷0 給 inf+RuntimeWarning(非 ZeroDivisionError),此例
        走 len(ranges)<3 → None;真正的炸點是缺欄 KeyError(上一測試)。"""
        from src.compute.strategy.tech_indicators import calc_vcp
        df = self._mk_df()
        df.loc[20, "high"] = 200.0   # H swing @20
        df.loc[30, "low"] = 0.0      # L swing 值 0 @30 → range ÷min(200,0)=÷0
        assert calc_vcp(df) is None

    def test_happy_path_still_returns_dict(self):
        from src.compute.strategy.tech_indicators import calc_vcp
        df = self._mk_df()
        df.loc[12, "high"] = 150.0
        df.loc[22, "low"] = 50.0
        df.loc[32, "high"] = 140.0
        df.loc[42, "low"] = 60.0
        out = calc_vcp(df)
        assert out is not None
        assert set(out) == {"swings", "contracting", "latest_range"}
        assert out["contracting"] is True   # 200% > 180% > 133%


# ══════════════════════════════════════════════════════════════
# 4. etf_fetch NAV 狀態排除清單補 '429'
# ══════════════════════════════════════════════════════════════
class TestEtf429Whitelist:
    def test_429_in_exclusion_tuple(self):
        src = (REPO / "src/data/etf/etf_fetch.py").read_text(encoding="utf-8")
        assert "'400', '401', '402', '403', '404', '429', '500'" in src


# ══════════════════════════════════════════════════════════════
# 5. compute_yoy_mom 日曆同月對齊
# ══════════════════════════════════════════════════════════════
class TestYoyCalendarAligned:
    @staticmethod
    def _mk(dates, revs):
        return pd.DataFrame({"date": pd.to_datetime(dates), "revenue": revs})

    def test_continuous_series_same_as_positional(self):
        """連續 24 月:日曆法與舊位置法結果相同(回歸保護)。"""
        from src.compute.health.monthly_revenue_calc import compute_yoy_mom
        dates = pd.date_range("2024-01-01", periods=24, freq="MS")
        revs = [100.0 + i for i in range(24)]
        out = compute_yoy_mom(self._mk(dates, revs))
        # 2025-10/11/12 vs 2024-10/11/12: (121/109-1)*100 ...
        exp = [(revs[21] / revs[9] - 1) * 100,
               (revs[22] / revs[10] - 1) * 100,
               (revs[23] / revs[11] - 1) * 100]
        assert len(out["yoy_last3"]) == 3
        assert all(a is not None and abs(a - b) < 1e-9
                   for a, b in zip(out["yoy_last3"], exp))

    def test_missing_month_no_wrong_base(self):
        """缺 2024-10:2025-10 的基期不存在 → None(原位置法會錯拿 2024-11 當基期)。"""
        from src.compute.health.monthly_revenue_calc import compute_yoy_mom
        dates = list(pd.date_range("2024-01-01", periods=24, freq="MS"))
        revs = [100.0 + i for i in range(24)]
        drop = dates.index(pd.Timestamp("2024-10-01"))
        dates.pop(drop); revs.pop(drop)
        out = compute_yoy_mom(self._mk(dates, revs))
        y_m2, y_m1, y_m0 = out["yoy_last3"]   # 2025-10, 2025-11, 2025-12
        assert y_m2 is None, "基期缺月必須回 None,不可錯位取值"
        assert y_m1 is not None and abs(y_m1 - (122 / 110 - 1) * 100) < 1e-9
        assert y_m0 is not None and abs(y_m0 - (123 / 111 - 1) * 100) < 1e-9

    def test_no_date_column_positional_fallback(self):
        """無 date 欄 → 退回位置索引(舊行為)。"""
        from src.compute.health.monthly_revenue_calc import compute_yoy_mom
        df = pd.DataFrame({"revenue": [100.0 + i for i in range(24)]})
        out = compute_yoy_mom(df)
        assert abs(out["yoy_last3"][-1] - (123 / 111 - 1) * 100) < 1e-9

    def test_short_series_insufficient(self):
        from src.compute.health.monthly_revenue_calc import compute_yoy_mom, classify_trend
        dates = pd.date_range("2025-01-01", periods=6, freq="MS")
        out = compute_yoy_mom(self._mk(dates, [100.0] * 6))
        assert out["yoy_last3"] == [None, None, None]
        assert classify_trend(out) == "insufficient"


# ══════════════════════════════════════════════════════════════
# 6. token 前綴不入 log
# ══════════════════════════════════════════════════════════════
class TestTokenNotPrinted:
    def test_no_token_slice_in_print(self):
        src = (REPO / "src/data/core/data_loader.py").read_text(encoding="utf-8")
        assert "_fm_token[:12]" not in src
        assert "len(_fm_token)" in src


# ══════════════════════════════════════════════════════════════
# 7. _URL_CACHE 上限 + 過期逐出
# ══════════════════════════════════════════════════════════════
class TestUrlCacheBounded:
    def test_put_enforces_max_and_evicts_expired(self):
        from src.data.proxy import proxy_helper as P
        _saved = dict(P._URL_CACHE)
        try:
            P._URL_CACHE.clear()
            # 塞爆:上限必須生效
            for i in range(P._URL_CACHE_MAX + 50):
                P._url_cache_put(("u", i), b"x")
            assert len(P._URL_CACHE) <= P._URL_CACHE_MAX
            # 過期項在下一次寫入時被逐出
            import time as _t
            P._URL_CACHE[("stale", 0)] = (_t.time() - P._URL_CACHE_TTL - 10, b"old", 200)
            P._url_cache_put(("fresh", 0), b"new")
            assert ("stale", 0) not in P._URL_CACHE
            assert ("fresh", 0) in P._URL_CACHE
        finally:
            P._URL_CACHE.clear()
            P._URL_CACHE.update(_saved)

    def test_oldest_evicted_first(self):
        from src.data.proxy import proxy_helper as P
        _saved = dict(P._URL_CACHE)
        try:
            P._URL_CACHE.clear()
            for i in range(P._URL_CACHE_MAX):
                P._url_cache_put(("k", i), b"x")
            _oldest_key = min(P._URL_CACHE, key=lambda k: P._URL_CACHE[k][0])
            P._url_cache_put(("k", "new"), b"y")
            assert _oldest_key not in P._URL_CACHE
            assert ("k", "new") in P._URL_CACHE
        finally:
            P._URL_CACHE.clear()
            P._URL_CACHE.update(_saved)
