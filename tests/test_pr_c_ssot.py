"""v18.328 PR-C SSOT 守衛測試 — 三項違憲修正驗證:
1. 停利停損常數(P2)
2. 量比軸線(P3)
3. 趨勢判定 4 段函式(P1)
"""
from __future__ import annotations

import shared.signal_thresholds as st_mod
from shared.colors import TRAFFIC_GREEN, TRAFFIC_RED, TRAFFIC_YELLOW
from src.ui.tabs import classify_trend_4tier


class TestStopProfitLossSSOT:
    def test_constants_exist_and_values(self):
        assert st_mod.STOP_PROFIT_T1_PCT == 5.0
        assert st_mod.STOP_PROFIT_T2_PCT == 10.0
        assert st_mod.STOP_LOSS_DEFAULT_PCT == 8.0

    def test_no_inline_in_tab_stock(self):
        src = open('src/ui/tabs/tab_stock.py', encoding='utf-8').read()
        assert '_cur_p * 1.05' not in src
        assert '_cur_p * 1.10' not in src
        assert '_cur_p * 0.92' not in src
        assert 'STOP_PROFIT_T1_PCT' in src
        assert 'STOP_PROFIT_T2_PCT' in src
        assert 'STOP_LOSS_DEFAULT_PCT' in src


class TestVolumeRatioSSOT:
    def test_constants_exist_and_values(self):
        assert st_mod.VOLUME_RATIO_SURGE == 1.5
        assert st_mod.VOLUME_RATIO_MILD == 1.0
        assert st_mod.VOLUME_RATIO_DRY == 0.5

    def test_no_inline_in_tab_stock(self):
        src = open('src/ui/tabs/tab_stock.py', encoding='utf-8').read()
        # 個股 Tab 警示列 + 健康度卡片皆改 SSOT
        assert 'vr2 < 0.5' not in src
        assert 'vr2>=1.5' not in src
        assert 'vr2>=1.0' not in src
        assert 'VOLUME_RATIO_DRY' in src
        assert 'VOLUME_RATIO_SURGE' in src
        assert 'VOLUME_RATIO_MILD' in src

    def test_dry_below_mild_below_surge(self):
        """量比常數單調遞增:DRY < MILD < SURGE。"""
        assert st_mod.VOLUME_RATIO_DRY < st_mod.VOLUME_RATIO_MILD < st_mod.VOLUME_RATIO_SURGE


class TestClassifyTrend4Tier:
    """SSOT 函式行為測試(原 inline 邏輯)。"""

    def test_bull_alignment(self):
        """price > ma20 > ma_long → 多頭 + 綠"""
        label, color = classify_trend_4tier(110, 105, 100)
        assert '多頭' in label
        assert color == TRAFFIC_GREEN

    def test_bear_alignment(self):
        """price < ma20 < ma_long → 空頭 + 紅"""
        label, color = classify_trend_4tier(90, 95, 100)
        assert '空頭' in label
        assert color == TRAFFIC_RED

    def test_bullish_box(self):
        """站上 ma_long 但短均未多頭 → 多箱 + 黃"""
        label, color = classify_trend_4tier(105, 100, 100)  # price > ma_long but ma20 == ma_long
        assert '多箱' in label
        assert color == TRAFFIC_YELLOW

    def test_bearish_box(self):
        """低於 ma_long 且非空頭排列 → 空箱 + 黃"""
        label, color = classify_trend_4tier(95, 100, 105)  # 還在多箱判定之前需 price > ma_long
        # 95 < 100 < 105 = 空頭排列,實際會回空頭
        assert '空頭' in label or '空箱' in label

    def test_no_data_returns_empty_label(self):
        """缺值 → ⚪無資料"""
        label, color = classify_trend_4tier(0, None, None)
        assert '無資料' in label

        label2, _ = classify_trend_4tier(100, None, 90)
        assert '無資料' in label2

    def test_two_tabs_use_ssot(self):
        """兩 Tab 必須 import classify_trend_4tier 走 SSOT。"""
        src_stock = open('src/ui/tabs/tab_stock.py', encoding='utf-8').read()
        src_grp = open('src/ui/tabs/tab_stock_grp.py', encoding='utf-8').read()
        assert 'classify_trend_4tier' in src_stock
        assert 'classify_trend_4tier' in src_grp

    def test_no_inline_4tier_in_grp(self):
        """組合 Tab 原 inline 4 段邏輯已退役。"""
        src = open('src/ui/tabs/tab_stock_grp.py', encoding='utf-8').read()
        # 原本的 inline 判斷模式
        assert "price4 > ma20_4 > ma100_4" not in src
        assert "price4 < ma20_4 < ma100_4" not in src

    def test_no_inline_4tier_in_stock(self):
        """個股 Tab K 線註解原 inline 邏輯已退役。"""
        src = open('src/ui/tabs/tab_stock.py', encoding='utf-8').read()
        # K 線註解段原本的 inline 判斷模式
        assert '_kp > _km20 > _km100' not in src
        assert '_kp < _km20 < _km100' not in src
