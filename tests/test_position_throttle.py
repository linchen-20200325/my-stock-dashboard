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


# ── 加碼三問決策關卡 ────────────────────────────────────────────────────
from shared.position_throttle import ADD_SIGMA_MAX, assess_add_gate  # noqa: E402


def test_add_gate_all_pass():
    r = assess_add_gate(sigma_z=-1.5, trend_bearish=False, macro_defensive=False)
    assert r['can_add'] and r['blocked_by'] == []


def test_add_gate_blocked_by_high_position():
    # σ 太高(追高)→ 擋
    r = assess_add_gate(sigma_z=0.8, trend_bearish=False, macro_defensive=False)
    assert not r['can_add'] and any('位階' in b for b in r['blocked_by'])


def test_add_gate_blocked_by_bearish_trend():
    # 空頭排列(攤平弱勢)→ 擋
    r = assess_add_gate(sigma_z=-2.0, trend_bearish=True, macro_defensive=False)
    assert not r['can_add'] and any('趨勢' in b for b in r['blocked_by'])


def test_add_gate_blocked_by_macro_defense():
    r = assess_add_gate(sigma_z=-2.0, trend_bearish=False, macro_defensive=True)
    assert not r['can_add'] and any('總經' in b for b in r['blocked_by'])


def test_add_gate_sigma_none_blocks_position_check():
    r = assess_add_gate(sigma_z=None, trend_bearish=False, macro_defensive=False)
    assert not r['can_add']


def test_add_gate_boundary_sigma_equals_threshold():
    # σ 恰 = -1(門檻)→ 通過(≤)
    r = assess_add_gate(sigma_z=ADD_SIGMA_MAX, trend_bearish=False, macro_defensive=False)
    assert r['checks'][0][1] is True
