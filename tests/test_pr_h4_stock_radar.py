"""v18.336 PR-H4 — 個股 Tab 操作雷達 + 3 個 SSOT 函式守衛測試。

R-1 audit P1 收尾 — 個股 Tab 缺操作狀態燈/月線乖離/年線乖離視覺化補齊。

新增 SSOT(tab_helpers.py):
- compute_stop_levels(price) — 停利停損價位 + %(原 tab_stock:591-602 inline)
- classify_bias_zone(bias_pct) — 月線/年線乖離分層(對應 STOCK_BIAS_*)
- classify_stock_status_lamp(health, trend, bias, vol, val) — 操作狀態燈
  (原 tab_stock_grp:285-305 inline,兩 Tab 共用)

UI 改動(tab_stock.py):
- 停利停損改走 compute_stop_levels SSOT(L596-613)
- 新增「📊 操作雷達」4 卡(L614-674):狀態燈 + 月線乖離 + 年線乖離 + 趨勢
"""
from __future__ import annotations


# ─────────── A. compute_stop_levels ───────────

class TestComputeStopLevels:
    """停利停損 SSOT 計算。"""

    def test_basic_compute(self):
        from tab_helpers import compute_stop_levels
        import pytest
        r = compute_stop_levels(100.0)
        assert r is not None
        # STOP_PROFIT_T1_PCT=5, T2_PCT=10, LOSS_PCT=8(浮點容差)
        assert r['stop_profit_t1'] == pytest.approx(105.0, abs=1e-9)
        assert r['stop_profit_t2'] == pytest.approx(110.0, abs=1e-9)
        assert r['stop_loss_default'] == pytest.approx(92.0, abs=1e-9)
        assert r['t1_pct'] == 5.0
        assert r['t2_pct'] == 10.0
        assert r['loss_pct'] == 8.0

    def test_none_price(self):
        from tab_helpers import compute_stop_levels
        assert compute_stop_levels(None) is None

    def test_zero_price(self):
        from tab_helpers import compute_stop_levels
        assert compute_stop_levels(0) is None

    def test_negative_price(self):
        from tab_helpers import compute_stop_levels
        assert compute_stop_levels(-5) is None


# ─────────── B. classify_bias_zone ───────────

class TestClassifyBiasZone:
    """乖離分層 SSOT(對應 STOCK_BIAS_DEEP/OVERHEAT/MILD)。"""

    def test_none(self):
        from tab_helpers import classify_bias_zone
        label, color = classify_bias_zone(None)
        assert '無資料' in label

    def test_deep_negative_below_minus_20(self):
        """STOCK_BIAS_DEEP_DEVIATION_PCT=20 → bias < -20% = 深度負乖離。"""
        from tab_helpers import classify_bias_zone
        label, color = classify_bias_zone(-25.0)
        assert '深度負乖離' in label
        assert '布局' in label

    def test_overheat_above_plus_20(self):
        from tab_helpers import classify_bias_zone
        label, color = classify_bias_zone(+25.0)
        assert '過熱正乖離' in label
        assert '出場' in label

    def test_mild_between_15_and_20_positive(self):
        from tab_helpers import classify_bias_zone
        label, color = classify_bias_zone(+17.0)
        assert '中度乖離' in label

    def test_mild_between_15_and_20_negative(self):
        from tab_helpers import classify_bias_zone
        label, color = classify_bias_zone(-17.0)
        assert '中度乖離' in label

    def test_neutral_within_15(self):
        from tab_helpers import classify_bias_zone
        label, color = classify_bias_zone(+5.0)
        assert '中性區' in label

    def test_boundary_exact_minus_15(self):
        """|bias| = 15% 應為中性(strict > 才中度)。"""
        from tab_helpers import classify_bias_zone
        label, color = classify_bias_zone(-15.0)
        assert '中性區' in label


# ─────────── C. classify_stock_status_lamp ───────────

class TestClassifyStockStatusLamp:
    """操作狀態燈 SSOT(原組合 Tab inline 抽出,兩 Tab 共用)。"""

    def test_blue_addon_four_conditions_all_met(self):
        """🔵 加碼:健康 A 級 + 多頭 + 量縮 + 近 20MA。"""
        from tab_helpers import classify_stock_status_lamp
        # HEALTH_GRADE_A_MIN=80, GRP_VOL_SHRINK_RATIO=0.7,
        # GRP_NEAR_MA20_BIAS_PCT=3
        r = classify_stock_status_lamp(
            health_score=85, trend_label='📈 多頭',
            bias_pct=2.0, vol_ratio=0.5,
            valuation_label=None)
        assert r == '🔵 加碼'

    def test_yellow_warn_overheat_bias(self):
        """🟡 警示:bias > GRP_BIAS_OVERHEAT_WARN_PCT(25%)。"""
        from tab_helpers import classify_stock_status_lamp
        r = classify_stock_status_lamp(
            health_score=70, trend_label='📈 多頭',
            bias_pct=30.0, vol_ratio=1.0,
            valuation_label=None)
        assert r == '🟡 警示'

    def test_orange_reduce_expensive_valuation(self):
        from tab_helpers import classify_stock_status_lamp
        r = classify_stock_status_lamp(
            health_score=70, trend_label='📊 多箱',
            bias_pct=10.0, vol_ratio=1.0,
            valuation_label='昂貴')
        assert r == '🟠 減碼'

    def test_orange_super_expensive(self):
        from tab_helpers import classify_stock_status_lamp
        r = classify_stock_status_lamp(
            health_score=70, trend_label='📊 多箱',
            bias_pct=10.0, vol_ratio=1.0,
            valuation_label='超貴')
        assert r == '🟠 減碼'

    def test_neutral_default(self):
        from tab_helpers import classify_stock_status_lamp
        r = classify_stock_status_lamp(
            health_score=50, trend_label='📊 空箱',
            bias_pct=5.0, vol_ratio=1.2,
            valuation_label='合理')
        assert r == '⚪'

    def test_blue_blocked_by_low_health(self):
        """健康 < A 級(80)→ 不觸發 🔵 即使其他條件全 OK。"""
        from tab_helpers import classify_stock_status_lamp
        r = classify_stock_status_lamp(
            health_score=70, trend_label='📈 多頭',
            bias_pct=2.0, vol_ratio=0.5,
            valuation_label=None)
        # 不該 🔵
        assert r != '🔵 加碼'

    def test_blue_blocked_by_not_bull(self):
        from tab_helpers import classify_stock_status_lamp
        r = classify_stock_status_lamp(
            health_score=85, trend_label='📊 多箱',
            bias_pct=2.0, vol_ratio=0.5,
            valuation_label=None)
        assert r != '🔵 加碼'

    def test_none_inputs_default_neutral(self):
        from tab_helpers import classify_stock_status_lamp
        r = classify_stock_status_lamp(None, None, None, None, None)
        assert r == '⚪'


# ─────────── D. Caller migration ───────────

class TestCallerMigration:
    """個股 + 個股組合 Tab 已改用 SSOT。"""

    def test_tab_stock_imports_three_helpers(self):
        src = open('tab_stock.py', encoding='utf-8').read()
        assert 'classify_stock_status_lamp' in src
        assert 'classify_bias_zone' in src
        assert 'compute_stop_levels' in src

    def test_tab_stock_uses_compute_stop_levels(self):
        src = open('tab_stock.py', encoding='utf-8').read()
        # SSOT 呼叫存在
        assert 'compute_stop_levels(_cur_p)' in src
        # 原 inline 計算已淨空(L591-593 hardcode)
        assert "round(_cur_p * (1 + STOP_PROFIT_T1_PCT / 100)" not in src
        assert "round(_cur_p * (1 - STOP_LOSS_DEFAULT_PCT / 100)" not in src

    def test_tab_stock_has_operation_radar(self):
        """個股 Tab 新增「📊 操作雷達」4 卡。"""
        src = open('tab_stock.py', encoding='utf-8').read()
        assert '📊 操作雷達' in src
        assert "classify_stock_status_lamp(" in src
        assert 'classify_bias_zone(_bias20_pct)' in src
        assert 'classify_bias_zone(_bias240_pct)' in src

    def test_tab_stock_grp_uses_status_lamp_ssot(self):
        src = open('tab_stock_grp.py', encoding='utf-8').read()
        assert 'classify_stock_status_lamp' in src
        # 原 inline 4 段 if 已淨空
        assert "_status4 = '🔵 加碼'" not in src
        assert "_status4 = '🟡 警示'" not in src
        assert "_status4 = '🟠 減碼'" not in src


class TestModulesImportable:
    def test_tab_helpers_clean(self):
        import tab_helpers  # noqa: F401

    def test_tab_stock_clean(self):
        import tab_stock  # noqa: F401

    def test_tab_stock_grp_clean(self):
        import tab_stock_grp  # noqa: F401
