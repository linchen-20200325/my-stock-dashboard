"""姿態油門 SSOT + 純映射(總經健康分 → 建議持股區間 %)。

設計理念(v19.62 使用者框架討論結論):
  總經**擇時**不可靠;它適合當「**油門**」——決定「該多積極 / 持股幾成」,
  **不是「開關」**(全進全出)。本模組把總經健康分(0-100)映成一條「建議持股區間」,
  並保留 regime 否決(空頭防禦時強制壓低上界),讓使用者用「姿態」思考而非「進出」。

邊界對齊既有 SSOT(不另立矛盾數字):
  - 健康分界 80 / 50 / 35 對齊 HEALTH_GRADE_A_MIN / HEALTH_GRADE_B_MIN /
    HEALTH_DEFENSE_THRESHOLD 預設。
  - 持股 % 帶邊界對齊 EXPOSURE_BULL / NEUTRAL / BEAR(80 / 50 / 20,config.py)。

純模組:零 L1+ 依賴,可單元測試。caller:
  `from shared.position_throttle import compute_position_throttle`
"""
from __future__ import annotations

# 健康分界(B/DEF 對齊既有分級常數;此處複寫值而非 import,避免 L0 交叉耦合,以註解釘一致)
#
# ⚠️ A 切點 2026-08-19 自 80 改為 65 —— 尺度借用錯誤修正(user 核准)
# ══════════════════════════════════════════════════════════════════════════
# 舊值 80 註解寫「對齊 HEALTH_GRADE_A_MIN」,但那是**個股六因子健康分**的 A 級線,
# 與總經 health 是兩個不同尺度的量。借出方 `shared/health_thresholds.py` 的模組
# docstring 自己就明文禁止這種借用:
#     「本模組僅收**個股健康度評分 0~100** 的 A/B/C 三級分界…**不收**市場曝險、
#       廣度評分、ETF 星評等獨立評分系統的閾值——**那些屬不同維度**。」
#
# 兩個尺度差在哪(實測):
#   - 個股健康分 = 趨勢30+RSI20+量比15+IBS10+KD15+布林10,滿分 100 且**真的會到 80+**
#     (`src/compute/scoring/scoring_helpers.calc_health_score`)。
#   - 總經 health = 0.6×jqavg + 0.4×score_pct,而 jqavg(σ=3.32)在數學上是個
#     **準常數 ≈ +29.8**(它貢獻 health 變異僅 2.8%;corr(health, score_pct)=0.987)。
#     ⇒ health ≡ 29.8 + 0.4×score_pct,值域被壓成 **[21.6, 78.1]**。
#     要 health ≥ 80 需 score_pct=100 **且** jqavg ≥ 66.7 —— 後者 20 年只有 2 天
#     (2008-11,且那兩天 score 僅 1~2/6),兩者同時成立 **0 天**。
#
# ⇒ 「積極」這一級在 2007-2026 的 4,769 個交易日裡**從未觸發過**,四級油門實際只有三級。
#
# 新值來源(§3.3 provenance,非拍腦袋):
#   scripts/calibrate_macro_traffic.run_backtest 重建 2007-01-12~2026-07-21
#   n=4,769,health 分布 mean 50.61 / std 11.92 / 值域 [21.6, 78.1]。
#   P90 = 65.6 → 取 65(整數切點,對應約 P89)。實測「積極」約 **25 天/年**
#   (每季約 6 天),稀有度合理,且**防禦帶依定義完全不動**(仍 30.4 天/年)——
#   這是三個候選修法裡唯一不會讓防禦天數暴增的一個。
#
# ⚠️ 這是治症狀不是治病。根因是 health 公式把 60% 權重壓在一個準常數上,
#   health 至今仍是 score_pct 的仿射壓縮。根治須把 jqavg 先 z-score/百分位化
#   到與 score_pct 可比的尺度,再用同一份樣本以 ROC 一次選出 A/B/DEF 三個切點
#   寫回 macro_thresholds.json —— 那正是該檔 `_comment_v19_173` 自列的待辦,
#   屬獨立提案(改公式=行為變更,需獨立驗證),本次**不做**。
THROTTLE_HEALTH_A: int = 65    # ≥ 此 → 積極帶(總經 health 專屬;2007-2026 n=4,769 的 P90≈65.6)
THROTTLE_HEALTH_B: int = 50    # ≥ 此 → 中性偏多帶(對齊 HEALTH_GRADE_B_MIN)
THROTTLE_HEALTH_DEF: int = 35  # < 此 → 防禦帶(對齊 HEALTH_DEFENSE_THRESHOLD 預設)

# 姿態油門刻度:(health_min, 持股下界%, 持股上界%, 姿態, icon)。
# **持股** 帶邊界 80/50/20 對齊 EXPOSURE_BULL/NEUTRAL/BEAR;70/30 為區間寬度設計值。
# ⚠️ 別把「持股 %」與「health 切點」搞混:同樣出現 80/50,但左欄是 health(0-100 分),
#    右邊兩欄是持股比例(%)。A 切點 2026-08-19 改 65 後兩者不再巧合同值(見上方註解)。
THROTTLE_TIERS: list[tuple[int, int, int, str, str]] = [
    (THROTTLE_HEALTH_A,   80, 100, '積極',     '🟢'),   # health ≥65
    (THROTTLE_HEALTH_B,   50, 70,  '中性偏多', '🟡'),   # health 50~64
    (THROTTLE_HEALTH_DEF, 30, 50,  '轉守',     '🟠'),   # health 35~49
    (0,                   0,  20,  '防禦',     '🔴'),   # health <35
]

# regime 否決:這些 regime(或 defense=True)強制把上界壓到防禦帶,
# 對齊 macro_helpers「空頭防禦｜降低部位」label 邏輯(總經惡化時無視技術面多頭)。
THROTTLE_VETO_REGIMES: frozenset[str] = frozenset({'bear', 'caution'})
_DEFENSE_HI_PCT: int = 20   # 防禦帶上界(= EXPOSURE_BEAR)


def compute_position_throttle(
    health: float,
    regime: str | None = None,
    defense: bool = False,
) -> dict:
    """總經健康分 → 建議持股區間(姿態油門)。

    Args:
        health: 總經健康分 0-100(compute_macro_health 的 'health')。
        regime: 'bull'/'neutral'/'caution'/'bear'(可選;用於否決)。
        defense: 空頭防禦旗標(compute_macro_health 的 'defense')。

    Returns:
        {lo_pct, hi_pct, mid_pct, posture, icon, regime_capped}
        - lo/hi/mid_pct: 建議持股區間下界/上界/中值(%)
        - posture: 姿態文字('積極'/'中性偏多'/'轉守'/'防禦'[/regime 否決])
        - regime_capped: 是否因 regime/defense 被強制壓低上界
    """
    _h = max(0.0, min(100.0, float(health)))
    lo, hi, posture, icon = 0, _DEFENSE_HI_PCT, '防禦', '🔴'
    for _hmin, _lo, _hi, _posture, _icon in THROTTLE_TIERS:
        if _h >= _hmin:
            lo, hi, posture, icon = _lo, _hi, _posture, _icon
            break

    # regime 否決:總經惡化 → 上界壓到防禦帶(不放大既有防禦帶)
    capped = False
    if (defense or (regime in THROTTLE_VETO_REGIMES)) and hi > _DEFENSE_HI_PCT:
        lo, hi, icon = 0, _DEFENSE_HI_PCT, '🔴'
        posture = '防禦(總經否決)'
        capped = True

    return {
        'lo_pct': lo, 'hi_pct': hi, 'mid_pct': round((lo + hi) / 2),
        'posture': posture, 'icon': icon, 'regime_capped': capped,
    }


# ── 加碼決策關卡(Feature 3:規則化加碼,防攤平弱勢 / 追高)──────────────────
ADD_SIGMA_MAX: float = -1.0
"""加碼位階門檻:σ z-score 須 ≤ 此(在 -1σ 以下才加碼,不追高)。"""


def assess_add_gate(sigma_z: float | None, trend_bearish: bool,
                    macro_defensive: bool) -> dict:
    """加碼三問(規則化)——三個都過才給加碼綠燈,防「感覺便宜就加 / 攤平弱勢」。

    ① 位階夠低:sigma_z ≤ ADD_SIGMA_MAX(-1σ 以下,不追高)
    ② 趨勢沒壞:非空頭排列(不是攤平弱勢股)
    ③ 總經沒轉防守

    Returns:
        {can_add: bool, checks: [(名稱, ok, 備註)], blocked_by: [未過的名稱]}
    """
    _pos_ok = sigma_z is not None and sigma_z <= ADD_SIGMA_MAX
    _trend_ok = not bool(trend_bearish)
    _macro_ok = not bool(macro_defensive)
    checks = [
        ('位階夠低（σ ≤ -1，不追高）', _pos_ok,
         f'σ={sigma_z:+.2f}' if sigma_z is not None else 'σ 未知'),
        ('趨勢沒壞（非空頭排列，不攤平弱勢）', _trend_ok,
         '空頭排列 ⚠️' if trend_bearish else '非空頭'),
        ('總經沒轉防守', _macro_ok, '總經防禦中 ⚠️' if macro_defensive else 'OK'),
    ]
    return {
        'can_add': _pos_ok and _trend_ok and _macro_ok,
        'checks': checks,
        'blocked_by': [name for name, ok, _ in checks if not ok],
    }
