# -*- coding: utf-8 -*-
"""v19.110 — 週 MACD 升級標準 12/26/9(user 核准插隊項)回歸鎖。

三個最容易出錯的輸入(§6):
1. 歷史不足 175 交易日 → 誠實 False(不退回 3/5/3 混模型,§1 一名一義)
2. 序列頭端有崩盤、尾端多頭 → False(鎖死舊版「取最舊 30 日」缺陷不回歸)
3. close 含 NaN → dropna 後照算,不炸
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent


def _src(rel: str) -> str:
    return (REPO / rel).read_text(encoding='utf-8')


def _daily_from_weekly(weekly_closes) -> pd.Series:
    """每週收盤展開成 5 根日K(組內同值 → 組末收盤=該週收盤,合成無損)。"""
    return pd.Series(np.repeat(np.asarray(weekly_closes, dtype=float), 5))


def _manual_osc(weekly_closes) -> list:
    """教科書式獨立重算(與 production 同公式、不同程式路徑,§4.3 對帳)。"""
    from shared.signal_thresholds import (
        WK_MACD_FAST_SPAN, WK_MACD_SIGNAL_SPAN, WK_MACD_SLOW_SPAN,
    )
    w = pd.Series(np.asarray(weekly_closes, dtype=float))
    dif = (w.ewm(span=WK_MACD_FAST_SPAN, adjust=False).mean()
           - w.ewm(span=WK_MACD_SLOW_SPAN, adjust=False).mean())
    dea = dif.ewm(span=WK_MACD_SIGNAL_SPAN, adjust=False).mean()
    return (dif - dea).tolist()


def _crossing_weekly() -> list:
    """造一條「多頭 → 高檔轉弱」且 OSC 恰於最後一週由正翻負的週K序列。

    50 週線性上漲(動能飽和,OSC 正但收斂)→ 尾端連 3 週下跌;逐步延長
    下跌直到獨立重算確認 OSC[-2]>0 且 OSC[-1]<=0(用對帳器找,不用手猜)。
    """
    base = list(np.linspace(100.0, 200.0, 50))
    for n_drop in range(1, 12):
        w = base + [base[-1] * (1 - 0.03 * i) for i in range(1, n_drop + 1)]
        osc = _manual_osc(w)
        if osc[-2] > 0 and osc[-1] <= 0:
            return w
    raise AssertionError('對帳器找不到翻負點 — 測試場景建構失敗')


# ═════════════════════════════════════════════════════════════════
# 行為
# ═════════════════════════════════════════════════════════════════
class TestWeeklyMacd:
    def test_cross_detected_and_agrees_with_manual_recompute(self):
        from src.compute.scoring.exit_signals import _weekly_macd_turn_negative
        w = _crossing_weekly()
        assert _weekly_macd_turn_negative(_daily_from_weekly(w)) is True, (
            '獨立重算 OSC 已翻負,production 必須同判(§4.3 雙算對帳)')

    def test_uptrend_no_signal(self):
        from src.compute.scoring.exit_signals import _weekly_macd_turn_negative
        w = list(np.linspace(100.0, 300.0, 60))   # 60 週純多頭
        assert _weekly_macd_turn_negative(_daily_from_weekly(w)) is False

    def test_insufficient_history_honest_false(self):
        from shared.signal_thresholds import (
            WK_MACD_DAYS_PER_WEEK, WK_MACD_MIN_WEEKS,
        )
        from src.compute.scoring.exit_signals import _weekly_macd_turn_negative
        _need = WK_MACD_MIN_WEEKS * WK_MACD_DAYS_PER_WEEK   # 175
        w = _crossing_weekly()
        daily = _daily_from_weekly(w)
        assert _weekly_macd_turn_negative(daily.tail(_need - 1)) is False, (
            '不足 175 日 → False,不得退回 3/5/3 混模型(§1)')
        assert _weekly_macd_turn_negative(None) is False

    def test_head_crash_tail_uptrend_false_locks_old_defect(self):
        from src.compute.scoring.exit_signals import _weekly_macd_turn_negative
        # 頭端 6 週崩盤(舊版 range(0,30) 只看這裡 → 會誤報)+ 尾端 60 週多頭
        head = [200.0, 180.0, 150.0, 120.0, 100.0, 90.0]
        tail = list(np.linspace(90.0, 260.0, 60))
        daily = _daily_from_weekly(head + tail)
        assert _weekly_macd_turn_negative(daily) is False, (
            '訊號必須看序列尾端(近期),舊版「取最舊 30 日」缺陷不得回歸')

    def test_nan_in_series_dropped_not_crash(self):
        from src.compute.scoring.exit_signals import _weekly_macd_turn_negative
        w = _crossing_weekly()
        daily = _daily_from_weekly(w).copy()
        daily.iloc[3] = float('nan')      # 頭部一筆 NaN
        assert _weekly_macd_turn_negative(daily) in (True, False)  # 不炸
        # dropna 後仍足量且尾端翻負場景 → 應維持 True
        assert _weekly_macd_turn_negative(daily) is True


# ═════════════════════════════════════════════════════════════════
# SSOT
# ═════════════════════════════════════════════════════════════════
def test_params_are_ssot_standard():
    from shared.signal_thresholds import (
        WK_MACD_DAYS_PER_WEEK, WK_MACD_FAST_SPAN, WK_MACD_MIN_WEEKS,
        WK_MACD_SIGNAL_SPAN, WK_MACD_SLOW_SPAN,
    )
    assert (WK_MACD_FAST_SPAN, WK_MACD_SLOW_SPAN, WK_MACD_SIGNAL_SPAN) == (12, 26, 9)
    assert WK_MACD_MIN_WEEKS == 35 and WK_MACD_DAYS_PER_WEEK == 5
    body = _src('src/compute/scoring/exit_signals.py')
    assert 'span=3' not in body and 'span=5' not in body, '3/5/3 代理不得殘留'
    assert 'WK_MACD_FAST_SPAN' in body, '參數必須 import SSOT,非 inline'
