"""位階過熱(追高風險)純函式測試。"""
import numpy as np
import pandas as pd

from shared.signal_thresholds import GRP_BIAS_OVERHEAT_WARN_PCT
from src.compute.strategy.overextension import (
    assess_price_overextension,
    overextension_label,
)


def test_insufficient_data():
    r = assess_price_overextension(pd.Series([10, 11, 12]))
    assert r['level'] == '資料不足' and not r['overheated']
    assert overextension_label(pd.Series([10, 11])) == '❓ N/A'


def test_normal_flat_price():
    # 平盤小幅雜訊 → 乖離小、RSI 中性 → 正常
    s = pd.Series(100 + np.random.default_rng(7).normal(0, 0.3, 60))
    r = assess_price_overextension(s)
    assert r['level'] == '正常' and not r['overheated']
    assert overextension_label(s) == '🟢 正常'


def test_overheated_sharp_rally():
    # 急拉噴出(45 平盤後 8 天陡升)→ 遠離 MA20(乖離 >25%)+ RSI 過熱 → 過熱
    s = pd.Series(list(np.full(45, 100.0)) + list(np.linspace(108, 180, 8)))
    r = assess_price_overextension(s)
    assert r['overheated']
    assert r['bias_pct'] > GRP_BIAS_OVERHEAT_WARN_PCT
    assert r['level'] == '過熱'          # 乖離 + RSI 兩訊號皆中
    lbl = overextension_label(s)
    assert lbl.startswith('🔴') and '乖離' in lbl


def test_bias_only_is_at_least_warm():
    # 緩漲但已遠離 MA20(乖離>25%)→ 至少偏熱
    s = pd.Series(list(np.full(40, 100.0)) + list(np.linspace(100, 140, 40)))
    r = assess_price_overextension(s)
    assert r['overheated'] and r['bias_pct'] is not None


def test_reasons_reference_ssot_thresholds():
    s = pd.Series(list(np.full(40, 100.0)) + list(np.linspace(101, 150, 20)))
    r = assess_price_overextension(s)
    # 理由字串應提到 SSOT 門檻數字
    joined = '｜'.join(r['reasons'])
    if r['bias_pct'] and r['bias_pct'] > GRP_BIAS_OVERHEAT_WARN_PCT:
        assert '25' in joined


def test_none_input_safe():
    assert assess_price_overextension(None)['level'] == '資料不足'
