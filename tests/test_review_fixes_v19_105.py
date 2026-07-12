# -*- coding: utf-8 -*-
"""v19.105 — 第九份外部 review 查證屬實項修復的回歸鎖。

涵蓋(僅鎖「查證屬實 + 本次已修」項,誤判/待核准項不在此檔):
- Bug1  app_render 因子條 total=0 → ZeroDivisionError 炸整張健康卡
- Bug3  chart_plotter 單列 df → 零寬 initial_range
- Bug4  macro_ui_components stat_card/margin_card 字串型數值 → TypeError 炸卡
- 1-A   picker_fetcher 裸 yfinance(無代理無快取)→ 改走 yf_proxy.cached_history
- 1-B   etf_fetch 兩處 attempts=1 使 403 直連降級永不觸發(同 v18.455 病)
- 2-A④ data_loader.get_quarterly_data 完全未快取 → TTL_3DAY
- §3.3  data_loader FinMind SDK except 靜默吞 → 補 log
- §4.2  config.WEIGHT_TABLES 三態權重和=1 import 時 fail loud
- 3-B   Bollinger σ 統一母體標準差 ddof=0(原樣本 σ 帶寬虛胖 ~√(20/19))
- 正名  scoring_engine sharpe_20 註解(20 日期間 Sharpe,非年化)
- 正名  exit_signals 週 MACD 3/5/3 docstring 標註非標準參數代理
- 清理  chart_plotter._get_revenue_range 除錯 print 移除(僅留 except log)
- 12    @monitored 擴編:chip_concentration / share_capital 進監控 registry
"""
from __future__ import annotations

import inspect
import math
import re
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent


def _src(rel: str) -> str:
    return (REPO / rel).read_text(encoding='utf-8')


# ═════════════════════════════════════════════════════════════════
# Bug1:健康卡因子條 total=0 防呆
# ═════════════════════════════════════════════════════════════════
class TestHealthBreakdownZeroTotal:
    def test_zero_total_no_crash(self):
        from src.ui.render.app_render import render_health_score
        html = render_health_score(50, {'趨勢': ('均線多頭', 0, 0)})
        assert isinstance(html, str) and '趨勢' in html  # 不炸,正常出卡

    def test_normal_total_still_correct(self):
        from src.ui.render.app_render import render_health_score
        html = render_health_score(80, {'籌碼': ('法人買超', 3, 4)})
        assert 'width:75%' in html  # 3/4 → 75%,行為不變

    def test_guard_in_source(self):
        assert 'if total else 0.0' in _src('src/ui/render/app_render.py')


# ═════════════════════════════════════════════════════════════════
# Bug3:單列 df 的 initial_range
# ═════════════════════════════════════════════════════════════════
def test_initial_range_single_row_guard_in_source():
    text = _src('src/ui/render/chart_plotter.py')
    assert 'if total_days >= 2 else None' in text, (
        '單列 df 應交給 plotly autorange(initial_range=None),而非零寬 range')


# ═════════════════════════════════════════════════════════════════
# Bug4:stat_card / margin_card 數值 coerce
# ═════════════════════════════════════════════════════════════════
class TestCardNumericGuards:
    def test_stat_card_string_pct_neutral(self):
        from src.ui.render.macro_ui_components import stat_card
        html = stat_card('測試', {'pct': 'N/A', 'last': 'x'})
        assert '─' in html and '0.00%' in html  # coerce 失敗 → 中性 0

    def test_stat_card_numeric_string_pct_coerced(self):
        from src.ui.render.macro_ui_components import stat_card
        html = stat_card('測試', {'pct': '-1.5', 'last': 'x'})
        assert '▼' in html and '1.50%' in html  # 字串數字 → 正常判方向

    def test_margin_card_garbage_string_falls_back_to_pending(self):
        from src.ui.render.macro_ui_components import margin_card
        html = margin_card('六千')
        assert '抓取中' in html  # 視同未取得,誠實顯示,不炸不腦補

    def test_margin_card_numeric_string_coerced(self):
        from src.ui.render.macro_ui_components import margin_card
        html = margin_card('3500')
        assert '高危' in html  # '3500' → 3500 億 > 3400 超熱門檻


# ═════════════════════════════════════════════════════════════════
# 1-A:picker_fetcher 走 yf_proxy(代理 + 快取)
# ═════════════════════════════════════════════════════════════════
def test_picker_fetcher_uses_yf_proxy():
    text = _src('src/data/stock/picker_fetcher.py')
    assert 'yf_proxy import cached_history' in text
    live = [ln for ln in text.splitlines() if not ln.lstrip().startswith('#')]
    assert not any('yf.Ticker(' in ln for ln in live), '裸 yfinance 直抓已移除,不應回歸'
    assert not any('import yfinance' in ln for ln in live)


# ═════════════════════════════════════════════════════════════════
# 1-B:etf_fetch attempts=2(403 降級鏈需連續 2 次才觸發)
# ═════════════════════════════════════════════════════════════════
def test_etf_fetch_nav_attempts_allow_degrade():
    text = _src('src/data/etf/etf_fetch.py')
    assert 'timeout=15, attempts=2' in text  # FinMind NAV 段
    assert 'timeout=10, attempts=2' in text  # TWSE openapi 段


# ═════════════════════════════════════════════════════════════════
# 2-A④ + §3.3:data_loader 季報快取 + SDK except log
# ═════════════════════════════════════════════════════════════════
class TestDataLoaderFixes:
    def test_quarterly_data_cached_ttl_3day(self):
        text = _src('src/data/core/data_loader.py')
        assert re.search(
            r'@st\.cache_data\(ttl=TTL_3DAY[^)]*\)\s*\n\s*def get_quarterly_data',
            text), 'get_quarterly_data 應掛 @st.cache_data(ttl=TTL_3DAY)'
        assert re.search(r'from shared\.ttls import [^\n]*TTL_3DAY', text)

    def test_sdk_fallback_logged(self):
        text = _src('src/data/core/data_loader.py')
        assert '[法人] FinMind SDK 路徑失敗' in text, (
            '§3.3:SDK except 不得靜默吞,須 log 後走 raw fallback')


# ═════════════════════════════════════════════════════════════════
# §4.2:WEIGHT_TABLES 權重和不變量
# ═════════════════════════════════════════════════════════════════
class TestWeightTablesInvariant:
    def test_each_regime_sums_to_one(self):
        from src.config.config import WEIGHT_TABLES
        for regime, w in WEIGHT_TABLES.items():
            assert math.isclose(sum(w.values()), 1.0, abs_tol=1e-9), (
                f'{regime} 權重和 {sum(w.values())} ≠ 1')

    def test_fail_loud_validation_in_source(self):
        text = _src('src/config/config.py')
        assert '權重未歸一' in text and '_math.isclose' in text, (
            'import 時 fail-loud 驗證不可被移除(§4.2/§1)')


# ═════════════════════════════════════════════════════════════════
# 3-B:Bollinger 母體 σ(ddof=0)
# ═════════════════════════════════════════════════════════════════
class TestBollingerPopulationSigma:
    def test_ddof0_in_all_bollinger_sites(self):
        assert _src('src/compute/strategy/tech_indicators.py').count('.std(ddof=0)') == 2
        assert '.std(ddof=0)' in _src('src/compute/scoring/scoring_engine.py')
        assert '.std(ddof=0)' in _src('src/compute/strategy/v5_modules.py')

    def test_width_series_matches_population_sigma(self):
        from src.compute.strategy.tech_indicators import calc_bollinger_width_series
        close = pd.Series(np.linspace(100.0, 120.0, 40))
        bw = calc_bollinger_width_series(close, 20, 2.0)
        ma = close.rolling(20).mean()
        std0 = close.rolling(20).std(ddof=0)
        std1 = close.rolling(20).std(ddof=1)
        # 公式 (4·k·std/2)/ma,k=2 → 4·std/ma;必須用母體 σ
        assert np.isclose(bw.iloc[-1], (4 * std0 / ma).iloc[-1], rtol=1e-12)
        assert not np.isclose(bw.iloc[-1], (4 * std1 / ma).iloc[-1], rtol=1e-6), (
            '樣本 σ(ddof=1)版本應與母體 σ 有 ~√(20/19) 差異,若相等代表改動被回退')


# ═════════════════════════════════════════════════════════════════
# 正名:sharpe_20 註解 + 週 MACD docstring
# ═════════════════════════════════════════════════════════════════
class TestFormulaNaming:
    def test_sharpe20_comment_states_period_not_annualized(self):
        text = _src('src/compute/scoring/scoring_engine.py')
        line = next(ln for ln in text.splitlines()
                    if ln.strip().startswith('sharpe_20 = ret20'))
        assert '非年化' in line, 'sharpe_20 註解須明示為期間 Sharpe,非年化'

    def test_weekly_macd_docstring_warns_nonstandard(self):
        from src.compute.scoring.exit_signals import _weekly_macd_turn_negative
        doc = _weekly_macd_turn_negative.__doc__ or ''
        assert '12/26/9' in doc and '非標準' in doc, (
            '3/5/3 週 MACD 為樣本受限代理,docstring 須警示不可與券商值對照')


# ═════════════════════════════════════════════════════════════════
# 清理:_get_revenue_range 除錯 print 移除
# ═════════════════════════════════════════════════════════════════
class TestRevenueRangeClean:
    def test_no_debug_print_in_body(self):
        from src.ui.render.chart_plotter import _get_revenue_range
        src = inspect.getsource(_get_revenue_range)
        assert '除錯' not in src
        assert src.count('print(') == 1, '僅 except 分支保留 1 個 log print'

    def test_happy_path_silent_and_correct(self, capsys):
        from src.ui.render.chart_plotter import _get_revenue_range
        res = _get_revenue_range(pd.Series([1000.0, 2000.0, 3000.0]))
        assert capsys.readouterr().out == '', '正常路徑不得再噴 stdout 除錯'
        assert res is not None and res[0] == 0
        assert math.isclose(res[1], 3.45)  # (3000/1000)×(1+0.15)


# ═════════════════════════════════════════════════════════════════
# 12:@monitored 擴編(集保籌碼集中度 / 股本)
# ═════════════════════════════════════════════════════════════════
def test_monitored_registers_chip_and_capital_fetchers():
    import src.data.stock.chip_concentration_fetcher  # noqa: F401 觸發登錄
    import src.data.stock.share_capital_fetcher  # noqa: F401
    from shared.data_categories import CAT_CHIPS, CAT_STOCK
    from shared.fetch_monitor import get_monitor_registry

    reg = get_monitor_registry()
    assert 'fetch_chip_concentration' in reg, '集保籌碼集中度須進監控 registry'
    assert 'fetch_share_capital' in reg, '股本須進監控 registry'
    cc, cap = reg['fetch_chip_concentration'], reg['fetch_share_capital']
    assert cc['category'] == CAT_CHIPS and cc['frequency'] == 'weekly'
    assert cap['category'] == CAT_STOCK and cap['frequency'] == 'quarterly'
    # registry key 為動態 per 股(scanner B5),固定填必孤兒誤報 → 必須留 None
    assert cc['registry_key'] is None and cap['registry_key'] is None
