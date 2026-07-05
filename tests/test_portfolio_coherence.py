"""股債比 + 總經一致性純函式測試(#2 + #3 股債比)。"""
from src.compute.etf.portfolio_coherence import (
    BOND_HIGH_PCT,
    BOND_LOW_PCT,
    assess_stock_bond,
    classify_asset_class,
    coherence_note,
)


def test_classify_bond_vs_stock():
    assert classify_asset_class('00679B.TW') == 'bond'
    assert classify_asset_class('00937B') == 'bond'
    assert classify_asset_class('BND') == 'bond'
    assert classify_asset_class('TLT') == 'bond'
    assert classify_asset_class('0050.TW') == 'stock'
    assert classify_asset_class('00878.TW') == 'stock'
    assert classify_asset_class('') == 'stock'


def test_assess_stock_bond_ratio():
    rows = [
        {'ticker': '0050.TW', 'value': 60},
        {'ticker': '00878.TW', 'value': 20},
        {'ticker': '00679B.TW', 'value': 20},
    ]
    r = assess_stock_bond(rows)
    assert r['stock_value'] == 80 and r['bond_value'] == 20
    assert r['stock_pct'] == 80.0 and r['bond_pct'] == 20.0


def test_assess_empty():
    r = assess_stock_bond([])
    assert r['total'] == 0 and r['bond_pct'] == 0.0


def test_coherence_defensive_but_all_stock_warns():
    lvl, msg = coherence_note('防禦', bond_pct=5)
    assert lvl == 'warn' and '打架' in msg


def test_coherence_bull_high_bond_info():
    lvl, msg = coherence_note('積極', bond_pct=70)
    assert lvl == 'info'


def test_coherence_aligned_ok():
    lvl, _ = coherence_note('中性偏多', bond_pct=30)
    assert lvl == 'ok'


def test_coherence_na_when_no_posture():
    lvl, _ = coherence_note('', bond_pct=50)
    assert lvl == 'na'


def test_thresholds_are_ssot():
    # 邊界:恰 BOND_LOW → 不算 <low(不觸發 warn)
    lvl, _ = coherence_note('防禦', bond_pct=BOND_LOW_PCT)
    assert lvl != 'warn'
    lvl2, _ = coherence_note('積極', bond_pct=BOND_HIGH_PCT)
    assert lvl2 != 'info'


# ── 核心/衛星(#4)────────────────────────────────────────────────────────
from src.compute.etf.portfolio_coherence import (  # noqa: E402
    assess_core_satellite,
    classify_core_satellite,
)


def test_classify_core_satellite():
    assert classify_core_satellite('0050.TW') == '核心'     # 市值型
    assert classify_core_satellite('006208.TW') == '核心'
    assert classify_core_satellite('00878.TW') == '衛星'    # 高股息
    assert classify_core_satellite('00891.TW') == '衛星'    # 半導體
    assert classify_core_satellite('00679B.TW') == '債券'
    assert classify_core_satellite('2330.TW') == '衛星'     # 個股 → 衛星


def test_assess_core_satellite_ratio():
    rows = [
        {'ticker': '0050.TW', 'value': 50},      # 核心
        {'ticker': '00878.TW', 'value': 30},     # 衛星
        {'ticker': '00679B.TW', 'value': 20},    # 債券
    ]
    r = assess_core_satellite(rows)
    assert r['core_pct'] == 50.0 and r['satellite_pct'] == 30.0 and r['bond_pct'] == 20.0
    assert abs(r['core_pct'] + r['satellite_pct'] + r['bond_pct'] - 100) < 0.1
