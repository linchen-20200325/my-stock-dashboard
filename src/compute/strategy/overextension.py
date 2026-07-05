"""src/compute/strategy/overextension.py — 位階過熱評估(追高風險)L2 純函式。

框架討論結論(Feature 2):選股的「熱門新聞」不該當買點——新聞熱度常在頭部才爆量。
本模組把「**位階過熱**」做成客觀警示:當價格已**遠離均線 / RSI 過熱**,代表題材可能
已發酵、追高風險大。搭配「這檔最近很熱門嗎?」由使用者判斷,兩者皆中 = 典型追高陷阱。

訊號(門檻走 SSOT,§3.3):
  ① MA20 正乖離 > GRP_BIAS_OVERHEAT_WARN_PCT(25%)
  ② RSI(14) > RSI_OVERBOUGHT(70)
  兩個都中 → 過熱(🔴);中一個 → 偏熱(🟡);都沒中 → 正常(🟢)。

純函式:只需收盤序列,無 I/O。reuse compute_rsi / calc_ma_series / calc_bias_pct(SSOT)。
"""
from __future__ import annotations

import pandas as pd

from shared.calc_helpers import calc_bias_pct
from shared.signal_thresholds import GRP_BIAS_OVERHEAT_WARN_PCT
from src.compute.scoring.scoring_engine import compute_rsi
from src.compute.strategy.tech_indicators import calc_ma_series
from src.config.config import RSI_OVERBOUGHT

_EMPTY = {'level': '資料不足', 'overheated': False, 'bias_pct': None,
          'rsi': None, 'reasons': [], 'icon': '⚪'}


def assess_price_overextension(close, *, ma_window: int = 20,
                               rsi_period: int = 14) -> dict:
    """位階過熱評估(追高風險)。

    Args:
        close: 收盤價序列(pd.Series / list)。
    Returns:
        {level, overheated, bias_pct, rsi, reasons, icon}
        - level: '過熱'(2 訊號) / '偏熱'(1) / '正常'(0) / '資料不足'
        - overheated: bool(≥1 訊號)
        - bias_pct: MA20 乖離率 %(None=算不出);rsi: RSI 值
    """
    if close is None:
        return dict(_EMPTY)
    _c = pd.Series(close).dropna()
    if len(_c) < ma_window + 1:
        return dict(_EMPTY)

    _ma = calc_ma_series(_c, ma_window).dropna()
    _last_ma = float(_ma.iloc[-1]) if len(_ma) else None
    _bias = calc_bias_pct(float(_c.iloc[-1]), _last_ma)

    _rsi_s = compute_rsi(_c, rsi_period).dropna()
    _rsi = float(_rsi_s.iloc[-1]) if len(_rsi_s) else None

    reasons: list[str] = []
    if _bias is not None and _bias > GRP_BIAS_OVERHEAT_WARN_PCT:
        reasons.append(f'乖離+{_bias:.0f}%（>{GRP_BIAS_OVERHEAT_WARN_PCT:.0f}%）')
    if _rsi is not None and _rsi > RSI_OVERBOUGHT:
        reasons.append(f'RSI {_rsi:.0f}（>{RSI_OVERBOUGHT}）')

    _n = len(reasons)
    _level = '過熱' if _n >= 2 else ('偏熱' if _n == 1 else '正常')
    _icon = '🔴' if _n >= 2 else ('🟡' if _n == 1 else '🟢')
    return {'level': _level, 'overheated': _n >= 1, 'bias_pct': _bias,
            'rsi': _rsi, 'reasons': reasons, 'icon': _icon}


def overextension_label(close) -> str:
    """選股網用簡短標籤:'🔴 過熱｜乖離+30%…' / '🟢 正常' / '❓ N/A'。"""
    _r = assess_price_overextension(close)
    if _r['level'] == '資料不足':
        return '❓ N/A'
    if _r['level'] == '正常':
        return '🟢 正常'
    return f"{_r['icon']} {_r['level']}｜{'、'.join(_r['reasons'])}"
