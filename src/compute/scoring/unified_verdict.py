"""src/compute/scoring/unified_verdict.py — 統一裁決引擎 L2 純函式(v19.201)。

單一職責:把「各軸已算好的體質結果」依 profile 套固定裁決規則,收斂成一個統一三態
(🟢續抱/🟡留意/🔴汰弱/⚪無法評分)+ 各軸並陳。**零 I/O、零 streamlit、不重算任何指標、
絕不把不同軸平均**(§2.1)。

裁決規則(2026-08-20 user 核准):
  ① 主軸資料缺 → ⚪ 無法評分(§1 不腦補)
  ② 主軸 → base 三態(門檻沿用既有 SSOT)
  ③ 閘門否決(停牌/流動性🔴/配息吃本金/追蹤誤差…)→ 降一階(不平均)
  ④ 次軸背離 → 只加註不翻轉(主🟢+次🔴 或 主🔴+次🟢)
  ⑤ 估值 / 總經 → 獨立並陳,永不改健康三態

輸入全部由 caller(L3 service)從既有引擎取好後傳入,本層不 fetch、不碰 UI。
"""
from __future__ import annotations

from dataclasses import dataclass

from shared.dividend_station_thresholds import STOCK_SWAP_GRADES
from shared.etf_recommendation_thresholds import (
    KEEP_COMPOSITE_MIN,
    SELL_COMPOSITE_MAX,
)
from shared.health_thresholds import HEALTH_GRADE_A_MIN, HEALTH_GRADE_B_MIN
from shared.unified_verdict_thresholds import (
    AXIS_DISPLAY_NAME,
    AXIS_ETF_COMPOSITE,
    AXIS_FUNDAMENTAL,
    AXIS_TECHNICAL,
    DIVERGENCE_MSG_STRONG_PRIMARY_WEAK_SECONDARY,
    DIVERGENCE_MSG_WEAK_PRIMARY_STRONG_SECONDARY,
    FUNDAMENTAL_KEEP_GRADES,
    FUNDAMENTAL_WATCH_GRADES,
    PROFILE_ROLES,
    PROFILE_TRADING,
    VERDICT_CUT,
    VERDICT_KEEP,
    VERDICT_LABEL,
    VERDICT_NA,
    VERDICT_WATCH,
    downgrade_verdict,
)


# ══════════════════════════════════════════════════════════════
# 各軸 → 三態 的對映(門檻全部沿用既有 SSOT,不重訂數字)
# ══════════════════════════════════════════════════════════════
def technical_health_to_state(score) -> str | None:
    """技術健康分(0-100)→ 三態。None/非數字 → None(缺值)。門檻:HEALTH_GRADE_A/B_MIN。"""
    if score is None:
        return None
    try:
        s = float(score)
    except (TypeError, ValueError):
        return None
    if s != s:  # NaN
        return None
    if s >= HEALTH_GRADE_A_MIN:
        return VERDICT_KEEP
    if s >= HEALTH_GRADE_B_MIN:
        return VERDICT_WATCH
    return VERDICT_CUT


def fundamental_grade_to_state(grade) -> str | None:
    """財報 grade(A+…F)→ 三態。None/未知 grade → None(缺值,§1 不硬歸類)。

    CUT 沿用 STOCK_SWAP_GRADES(C,F);KEEP=FUNDAMENTAL_KEEP_GRADES(A+/A/B+);
    WATCH=FUNDAMENTAL_WATCH_GRADES(B)。不在三者任一 → None(未知,交 coverage 處理)。
    """
    if not grade:
        return None
    g = str(grade).strip()
    if g in STOCK_SWAP_GRADES:
        return VERDICT_CUT
    if g in FUNDAMENTAL_KEEP_GRADES:
        return VERDICT_KEEP
    if g in FUNDAMENTAL_WATCH_GRADES:
        return VERDICT_WATCH
    return None


def etf_composite_to_state(composite) -> str | None:
    """ETF 綜合分(0-1)→ 三態。門檻:KEEP/SELL_COMPOSITE。None/非數字 → None。"""
    if composite is None:
        return None
    try:
        c = float(composite)
    except (TypeError, ValueError):
        return None
    if c != c:  # NaN
        return None
    if c >= KEEP_COMPOSITE_MIN:
        return VERDICT_KEEP
    if c < SELL_COMPOSITE_MAX:
        return VERDICT_CUT
    return VERDICT_WATCH


# axis → (state 對映函式, 該軸原值 kwarg 名)
_AXIS_STATE_FN = {
    AXIS_TECHNICAL: technical_health_to_state,
    AXIS_FUNDAMENTAL: fundamental_grade_to_state,
    AXIS_ETF_COMPOSITE: etf_composite_to_state,
}


@dataclass(frozen=True)
class UnifiedVerdict:
    """統一裁決結果(§設計:三態 + 各軸並陳 + 背離加註 + coverage)。"""
    verdict: str                     # VERDICT_KEEP/WATCH/CUT/NA
    label: str                       # 中文 emoji 標籤
    profile: str                     # 用了哪個 profile
    primary_axis: str                # 主軸
    primary_state: str | None        # 主軸的三態(gate 降級前)
    axes: tuple[dict, ...]           # 各軸並陳:{axis,name,value,state}
    divergence: str | None           # 背離加註(僅加註,未翻轉 verdict)
    gate_downgrades: tuple[str, ...]  # 觸發降級的閘門原因
    valuation_label: str | None      # 估值軸(獨立,不影響 verdict)
    macro_ctx: dict | None           # 總經 context(並陳,未融入)
    coverage: dict                   # 各軸是否有值
    reasons: tuple[str, ...]         # 每步為何(§2.2 provenance)


def assess_unified(*, profile: str,
                   technical_health=None,
                   fundamental_grade=None,
                   etf_composite=None,
                   valuation_label=None,
                   gates=None,
                   macro_ctx=None) -> UnifiedVerdict:
    """套裁決規則 → UnifiedVerdict。所有輸入皆為既有引擎算好的結果(本函式不 fetch)。

    Args:
        profile: PROFILE_* 之一(caller 依分頁 context 決定主/次軸)。
        technical_health: calc_health_score 的 0-100(或 None)。
        fundamental_grade: financial_health no_ai_overall_verdict 的 grade A+…F(或 None)。
        etf_composite: compute_etf_composite_score 的 0-1(或 None)。
        valuation_label: 估值 zone 標籤(獨立軸,並陳用)。
        gates: 生效中的閘門原因 list[str](停牌/流動性🔴/配息吃本金/追蹤誤差…);任一存在 → 降一階。
        macro_ctx: 總經 context dict(regime/light…);並陳用,不融入 verdict。
    """
    _roles = PROFILE_ROLES.get(profile)
    reasons: list[str] = []
    if _roles is None:
        # 未知 profile:保守用交易 profile,並記錄(不靜默)。
        reasons.append(f'未知 profile={profile!r},fallback={PROFILE_TRADING}')
        profile = PROFILE_TRADING
        _roles = PROFILE_ROLES[PROFILE_TRADING]
    primary_axis, secondary_axis = _roles

    _axis_value = {
        AXIS_TECHNICAL: technical_health,
        AXIS_FUNDAMENTAL: fundamental_grade,
        AXIS_ETF_COMPOSITE: etf_composite,
    }

    def _state_of(axis):
        return _AXIS_STATE_FN[axis](_axis_value[axis]) if axis else None

    primary_state = _state_of(primary_axis)
    secondary_state = _state_of(secondary_axis)

    # 各軸並陳(所有「有傳值」的軸都列出,含非主/次軸)
    axes: list[dict] = []
    for axis, fn in _AXIS_STATE_FN.items():
        val = _axis_value[axis]
        if val is None:
            continue
        axes.append({
            'axis': axis,
            'name': AXIS_DISPLAY_NAME.get(axis, axis),
            'value': val,
            'state': fn(val),
            'is_primary': axis == primary_axis,
        })

    coverage = {
        'primary_present': primary_state is not None,
        'secondary_present': secondary_state is not None,
        'n_axes': len(axes),
    }

    # ① 主軸資料缺 → ⚪ 無法評分(§1 不腦補)
    if primary_state is None:
        reasons.append(f'主軸({AXIS_DISPLAY_NAME.get(primary_axis, primary_axis)})資料不足 → 無法評分')
        return UnifiedVerdict(
            verdict=VERDICT_NA, label=VERDICT_LABEL[VERDICT_NA], profile=profile,
            primary_axis=primary_axis, primary_state=None, axes=tuple(axes),
            divergence=None, gate_downgrades=(), valuation_label=valuation_label,
            macro_ctx=macro_ctx, coverage=coverage, reasons=tuple(reasons),
        )

    # ② 主軸 → base 三態
    verdict = primary_state
    reasons.append(f'主軸 {AXIS_DISPLAY_NAME.get(primary_axis, primary_axis)} → {VERDICT_LABEL[primary_state]}')

    # ③ 閘門否決(任一生效 → 降一階,不因數量疊加;對齊 recommend_etf_action)
    gate_list = [g for g in (gates or []) if g]
    if gate_list:
        _before = verdict
        verdict = downgrade_verdict(verdict, 1)
        if verdict != _before:
            reasons.append(f'閘門降級 {VERDICT_LABEL[_before]}→{VERDICT_LABEL[verdict]}:' + '、'.join(gate_list))
        else:
            reasons.append('閘門已在最低階,無可再降:' + '、'.join(gate_list))

    # ④ 次軸背離(只加註,不翻轉 verdict) —— 用「軸的原始三態」比,非 gate 後
    divergence = None
    if secondary_state is not None and secondary_axis is not None:
        _pn = AXIS_DISPLAY_NAME.get(primary_axis, primary_axis)
        _sn = AXIS_DISPLAY_NAME.get(secondary_axis, secondary_axis)
        if primary_state == VERDICT_KEEP and secondary_state == VERDICT_CUT:
            divergence = DIVERGENCE_MSG_STRONG_PRIMARY_WEAK_SECONDARY.format(
                primary_name=_pn, secondary_name=_sn)
        elif primary_state == VERDICT_CUT and secondary_state == VERDICT_KEEP:
            divergence = DIVERGENCE_MSG_WEAK_PRIMARY_STRONG_SECONDARY.format(
                primary_name=_pn, secondary_name=_sn)
        if divergence:
            reasons.append('⚠️ 背離加註:' + divergence)

    # ⑤ 估值 / 總經:並陳,不改 verdict
    if valuation_label:
        reasons.append(f'估值(獨立軸,不改三態):{valuation_label}')

    return UnifiedVerdict(
        verdict=verdict, label=VERDICT_LABEL[verdict], profile=profile,
        primary_axis=primary_axis, primary_state=primary_state, axes=tuple(axes),
        divergence=divergence, gate_downgrades=tuple(gate_list),
        valuation_label=valuation_label, macro_ctx=macro_ctx,
        coverage=coverage, reasons=tuple(reasons),
    )
