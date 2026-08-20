"""統一裁決引擎 L0+L2 測試(v19.201)。

覆蓋:三態對映(門檻沿用既有 SSOT)、profile 主/次軸、閘門降級(不平均)、
背離只加註不翻轉、§1 主軸缺→⚪無法評分、估值/總經並陳不影響 verdict。

3 個最容易出錯的輸入:
  1. 主軸資料缺(None / NaN / 未知 grade)—— 必須 ⚪ 無法評分,不可腦補。
  2. 主🟢 但次🔴 背離 —— 只加註,verdict 仍🟢(不可被次軸翻成🟡/🔴)。
  3. 閘門疊加 —— 只降一階(不因閘門數量多降多階、不平均)。
"""
from __future__ import annotations

import math

import pytest

from shared.dividend_station_thresholds import KIND_ETF, KIND_STOCK
from shared.unified_verdict_thresholds import (
    AXIS_ETF_COMPOSITE,
    AXIS_FUNDAMENTAL,
    AXIS_TECHNICAL,
    PROFILE_DIVIDEND_HOLD,
    PROFILE_ETF,
    PROFILE_ROLES,
    PROFILE_TRADING,
    VERDICT_CUT,
    VERDICT_KEEP,
    VERDICT_NA,
    VERDICT_WATCH,
    default_profile_for,
    downgrade_verdict,
)
from src.compute.scoring.unified_verdict import (
    assess_unified,
    etf_composite_to_state,
    fundamental_grade_to_state,
    technical_health_to_state,
)


# ══════════════════════════════════════════════════════════════
# L0
# ══════════════════════════════════════════════════════════════
def test_downgrade_verdict_steps():
    assert downgrade_verdict(VERDICT_KEEP) == VERDICT_WATCH
    assert downgrade_verdict(VERDICT_WATCH) == VERDICT_CUT
    assert downgrade_verdict(VERDICT_CUT) == VERDICT_CUT          # 封頂
    assert downgrade_verdict(VERDICT_KEEP, 2) == VERDICT_CUT
    assert downgrade_verdict(VERDICT_KEEP, 0) == VERDICT_KEEP     # 不降
    assert downgrade_verdict(VERDICT_NA) == VERDICT_NA            # NA 不參與


def test_default_profile_for():
    assert default_profile_for(KIND_ETF) == PROFILE_ETF
    assert default_profile_for(KIND_STOCK) == PROFILE_TRADING     # 個股預設交易(存股 caller 需覆蓋)
    assert default_profile_for('unknown') == PROFILE_TRADING


def test_profile_roles_complete():
    assert PROFILE_ROLES[PROFILE_DIVIDEND_HOLD] == (AXIS_FUNDAMENTAL, AXIS_TECHNICAL)
    assert PROFILE_ROLES[PROFILE_TRADING] == (AXIS_TECHNICAL, AXIS_FUNDAMENTAL)
    assert PROFILE_ROLES[PROFILE_ETF] == (AXIS_ETF_COMPOSITE, None)


# ══════════════════════════════════════════════════════════════
# 各軸 → 三態(門檻沿用既有 SSOT)
# ══════════════════════════════════════════════════════════════
def test_technical_health_to_state():
    assert technical_health_to_state(80) == VERDICT_KEEP     # HEALTH_GRADE_A_MIN
    assert technical_health_to_state(79) == VERDICT_WATCH
    assert technical_health_to_state(50) == VERDICT_WATCH    # HEALTH_GRADE_B_MIN
    assert technical_health_to_state(49) == VERDICT_CUT
    assert technical_health_to_state(None) is None
    assert technical_health_to_state(float('nan')) is None
    assert technical_health_to_state('x') is None


def test_fundamental_grade_to_state():
    for g in ('A+', 'A', 'B+'):
        assert fundamental_grade_to_state(g) == VERDICT_KEEP
    assert fundamental_grade_to_state('B') == VERDICT_WATCH
    for g in ('C', 'F'):                                     # STOCK_SWAP_GRADES
        assert fundamental_grade_to_state(g) == VERDICT_CUT
    assert fundamental_grade_to_state(None) is None
    assert fundamental_grade_to_state('') is None
    assert fundamental_grade_to_state('Z') is None          # 未知 grade → None(不硬歸類)


def test_etf_composite_to_state():
    assert etf_composite_to_state(0.65) == VERDICT_KEEP      # KEEP_COMPOSITE_MIN
    assert etf_composite_to_state(0.5) == VERDICT_WATCH
    assert etf_composite_to_state(0.35) == VERDICT_WATCH     # 邊界:非 <0.35
    assert etf_composite_to_state(0.34) == VERDICT_CUT       # SELL_COMPOSITE_MAX
    assert etf_composite_to_state(None) is None
    assert etf_composite_to_state(float('nan')) is None


# ══════════════════════════════════════════════════════════════
# assess_unified — 核心裁決
# ══════════════════════════════════════════════════════════════
def test_dividend_hold_fundamental_primary_keep():
    v = assess_unified(profile=PROFILE_DIVIDEND_HOLD,
                       fundamental_grade='A', technical_health=90)
    assert v.verdict == VERDICT_KEEP
    assert v.primary_axis == AXIS_FUNDAMENTAL
    assert v.coverage['primary_present'] and v.coverage['secondary_present']
    assert v.divergence is None


def test_primary_missing_is_na():
    """§1:主軸(基本面)資料缺 → ⚪ 無法評分,即使次軸(技術)很好。"""
    v = assess_unified(profile=PROFILE_DIVIDEND_HOLD,
                       fundamental_grade=None, technical_health=95)
    assert v.verdict == VERDICT_NA
    assert v.primary_state is None
    assert not v.coverage['primary_present']


def test_gate_downgrades_one_step_only():
    """閘門疊加只降一階(不平均、不因數量多降多階)。"""
    v = assess_unified(profile=PROFILE_TRADING, technical_health=90,   # keep
                       gates=['停牌', '流動性🔴', '配息吃本金'])
    assert v.verdict == VERDICT_WATCH                        # keep→watch(只一階)
    assert set(v.gate_downgrades) == {'停牌', '流動性🔴', '配息吃本金'}


def test_gate_on_cut_stays_cut():
    v = assess_unified(profile=PROFILE_TRADING, technical_health=40,   # cut
                       gates=['流動性🔴'])
    assert v.verdict == VERDICT_CUT


def test_divergence_only_annotates_not_flips_keep():
    """主🟢(財報A)+ 次🔴(技術40)→ 背離加註,但 verdict 仍🟢(不翻轉)。"""
    v = assess_unified(profile=PROFILE_DIVIDEND_HOLD,
                       fundamental_grade='A', technical_health=40)
    assert v.verdict == VERDICT_KEEP                         # 未被次軸翻轉
    assert v.divergence is not None
    assert '基本面' in v.divergence and '技術面' in v.divergence


def test_divergence_weak_primary_strong_secondary():
    """主🔴(財報F)+ 次🟢(技術90)→ 反向背離加註,verdict 仍🔴。"""
    v = assess_unified(profile=PROFILE_DIVIDEND_HOLD,
                       fundamental_grade='F', technical_health=90)
    assert v.verdict == VERDICT_CUT
    assert v.divergence is not None


def test_no_divergence_when_watch_involved():
    """一軸是🟡時不算背離(只有🟢×🔴 對立才加註)。"""
    v = assess_unified(profile=PROFILE_DIVIDEND_HOLD,
                       fundamental_grade='A', technical_health=60)  # keep + watch
    assert v.divergence is None


def test_etf_profile_composite_primary():
    v = assess_unified(profile=PROFILE_ETF, etf_composite=0.72)
    assert v.verdict == VERDICT_KEEP
    assert v.primary_axis == AXIS_ETF_COMPOSITE
    assert v.coverage['secondary_present'] is False          # ETF 無次軸


def test_valuation_and_macro_are_passthrough_not_fused():
    """估值/總經並陳,不改 verdict。"""
    v_cheap = assess_unified(profile=PROFILE_TRADING, technical_health=90,
                             valuation_label='🟢便宜', macro_ctx={'regime': 'bull'})
    v_rich = assess_unified(profile=PROFILE_TRADING, technical_health=90,
                            valuation_label='🔴貴', macro_ctx={'regime': 'bear'})
    assert v_cheap.verdict == v_rich.verdict == VERDICT_KEEP   # 估值/總經未影響三態
    assert v_cheap.valuation_label == '🟢便宜'
    assert v_rich.macro_ctx == {'regime': 'bear'}


def test_unknown_profile_falls_back_to_trading():
    v = assess_unified(profile='bogus', technical_health=90)
    assert v.profile == PROFILE_TRADING
    assert any('未知 profile' in r for r in v.reasons)
    assert v.verdict == VERDICT_KEEP


def test_reasons_and_axes_populated():
    v = assess_unified(profile=PROFILE_DIVIDEND_HOLD,
                       fundamental_grade='C', technical_health=85, gates=['停牌'])
    assert v.reasons                                          # 每步為何非空
    # 各軸並陳:基本面 + 技術 都列出
    _axes = {a['axis'] for a in v.axes}
    assert AXIS_FUNDAMENTAL in _axes and AXIS_TECHNICAL in _axes
    # 主軸 C→cut,閘門停牌 → 已在最低階仍 cut
    assert v.verdict == VERDICT_CUT
