"""姿態油門純函式測試(健康分 → 建議持股區間 + regime 否決)。"""
from shared.position_throttle import (
    THROTTLE_TIERS,
    compute_position_throttle,
)


def test_tiers_ssot_ordered_and_bounded():
    # tier 依 health_min 由高到低;% 邊界對齊 80/50/20
    mins = [t[0] for t in THROTTLE_TIERS]
    assert mins == sorted(mins, reverse=True)
    assert THROTTLE_TIERS[0][1:3] == (80, 100)   # 積極帶下界=EXPOSURE_BULL
    assert THROTTLE_TIERS[-1][2] == 20           # 防禦帶上界=EXPOSURE_BEAR


def test_aggressive_band():
    r = compute_position_throttle(88, regime='bull')
    assert (r['lo_pct'], r['hi_pct']) == (80, 100)
    assert r['posture'] == '積極' and r['mid_pct'] == 90
    assert not r['regime_capped']


def test_neutral_band():
    r = compute_position_throttle(62, regime='neutral')
    assert (r['lo_pct'], r['hi_pct']) == (50, 70)
    assert r['posture'] == '中性偏多'


def test_turn_defensive_band():
    r = compute_position_throttle(40, regime='neutral')
    assert (r['lo_pct'], r['hi_pct']) == (30, 50)
    assert r['posture'] == '轉守'


def test_defense_band_low_health():
    r = compute_position_throttle(20)
    assert (r['lo_pct'], r['hi_pct']) == (0, 20)
    assert r['posture'] == '防禦'


def test_boundary_values_align_ssot():
    # 恰在分界:80 → 積極, 50 → 中性, 35 → 轉守, 34 → 防禦
    assert compute_position_throttle(80)['posture'] == '積極'
    assert compute_position_throttle(50)['posture'] == '中性偏多'
    assert compute_position_throttle(35)['posture'] == '轉守'
    assert compute_position_throttle(34)['posture'] == '防禦'


def test_regime_veto_caps_upper_even_if_health_high():
    # 健康分高但 regime=bear / defense=True → 上界壓到防禦帶(總經否決)
    r1 = compute_position_throttle(90, regime='bear')
    assert r1['hi_pct'] == 20 and r1['regime_capped'] and '否決' in r1['posture']
    r2 = compute_position_throttle(90, regime='bull', defense=True)
    assert r2['hi_pct'] == 20 and r2['regime_capped']


def test_no_veto_when_already_defensive():
    # 已在防禦帶 + regime bear → 不需再壓,regime_capped=False(未放大)
    r = compute_position_throttle(10, regime='bear')
    assert r['hi_pct'] == 20 and not r['regime_capped']


def test_health_clamped_to_0_100():
    assert compute_position_throttle(999)['posture'] == '積極'
    assert compute_position_throttle(-5)['posture'] == '防禦'
