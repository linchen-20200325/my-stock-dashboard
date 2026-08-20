"""shared/unified_verdict_thresholds.py — 統一裁決引擎 L0 SSOT(v19.201)。

「統一 Health Score 引擎」的常數層:三態詞彙 + 各軸角色表 + profile 對映。
**不含任何評分數學、不做平均**(§2.1) —— 各軸的分數由既有引擎算好後傳入,本層只定義
「三態詞彙、哪一軸當主軸、基本面 grade 如何切三態」這些**定義**。

設計依據(2026-08-20 user 核准的設計方案):
- 輸出=統一三態 + 各軸並陳;範圍=per-asset;主軸依 asset_kind/context 決定。
- 背離只加註不翻轉;技術軸用 calc_health_score;新增不取代既有裁決。

門檻沿用既有 SSOT,不重訂:
- 技術軸→三態:`shared/health_thresholds.HEALTH_GRADE_A_MIN/B_MIN`(80/50)。
- ETF 綜合分→三態:`shared/etf_recommendation_thresholds.KEEP/SELL_COMPOSITE`(0.65/0.35)。
- 基本面 grade→三態:CUT 沿用 `dividend_station_thresholds.STOCK_SWAP_GRADES`(C,F);
  KEEP/WATCH 切點(A+/A/B+ vs B)為本引擎新增之**顯式** SSOT(見下),不腦補。
"""
from __future__ import annotations

# ── 統一三態 + 無法評分(§1:資料不足為獨立第四態,非第四種「壞」)──
VERDICT_KEEP: str = 'keep'    # 🟢 續抱 / 健康
VERDICT_WATCH: str = 'watch'  # 🟡 留意 / 觀察
VERDICT_CUT: str = 'cut'      # 🔴 汰弱 / 換出
VERDICT_NA: str = 'na'        # ⚪ 無法評分(主軸資料缺)

# 顯示用中文標籤 + emoji(SSOT,UI 直接引用,勿散寫字面)
VERDICT_LABEL: dict[str, str] = {
    VERDICT_KEEP:  '🟢 續抱',
    VERDICT_WATCH: '🟡 留意',
    VERDICT_CUT:   '🔴 汰弱',
    VERDICT_NA:    '⚪ 無法評分',
}

# 嚴重度序(降級用:keep→watch→cut,cut 為底)。閘門否決時 downgrade 一階。
VERDICT_SEVERITY: dict[str, int] = {
    VERDICT_KEEP: 0,
    VERDICT_WATCH: 1,
    VERDICT_CUT: 2,
}
# 依嚴重度反查(downgrade 後取回標籤)
_SEVERITY_TO_VERDICT: dict[int, str] = {v: k for k, v in VERDICT_SEVERITY.items()}


def downgrade_verdict(verdict: str, steps: int = 1) -> str:
    """把三態往「更差」降 steps 階(keep→watch→cut,cut 封頂)。

    VERDICT_NA 不參與降級(資料不足無從降,原樣回)。steps<=0 原樣回。
    """
    if verdict not in VERDICT_SEVERITY or steps <= 0:
        return verdict
    _sev = min(VERDICT_SEVERITY[VERDICT_CUT], VERDICT_SEVERITY[verdict] + steps)
    return _SEVERITY_TO_VERDICT[_sev]


# ── 軸別 ──
AXIS_TECHNICAL: str = 'technical'         # 技術健康分(calc_health_score,0-100)
AXIS_FUNDAMENTAL: str = 'fundamental'     # 財報體檢 grade(A+…F)
AXIS_ETF_COMPOSITE: str = 'etf_composite'  # ETF 7 維綜合分(0-1)

# ── profile → (主軸, 次軸)。次軸=None 表示無次軸(僅並陳,不做背離)──
PROFILE_DIVIDEND_HOLD: str = 'dividend_hold'  # 存股 / 長期個股 → 基本面主軸
PROFILE_TRADING: str = 'trading'              # 交易 / 短線個股 → 技術主軸
PROFILE_ETF: str = 'etf'                      # ETF → 綜合分主軸

PROFILE_ROLES: dict[str, tuple[str, str | None]] = {
    PROFILE_DIVIDEND_HOLD: (AXIS_FUNDAMENTAL, AXIS_TECHNICAL),
    PROFILE_TRADING:       (AXIS_TECHNICAL, AXIS_FUNDAMENTAL),
    PROFILE_ETF:           (AXIS_ETF_COMPOSITE, None),
}


def default_profile_for(asset_kind: str) -> str:
    """asset_kind(etf/stock/unknown)→ 預設 profile。

    ⚠️ ticker 分類**無法**分辨「存股 vs 交易」個股(那是持有意圖/分頁 context)。
    故:etf→ETF profile;stock/unknown→交易 profile(選股網視角預設)。
    **存股戰情室等長期持有 context 的 caller 必須明確傳 PROFILE_DIVIDEND_HOLD 覆蓋**,
    不可依賴此預設(此預設只是 caller 未指定 context 時的保守 fallback)。
    """
    from shared.dividend_station_thresholds import KIND_ETF
    return PROFILE_ETF if asset_kind == KIND_ETF else PROFILE_TRADING


# ── 基本面 grade → 三態 的切點(本引擎新增之顯式 SSOT)──
# CUT 沿用既有 STOCK_SWAP_GRADES(C,F);KEEP/WATCH 依既有 6 grade 序切:
#   前 3(A+/A/B+)=🟢、次 1(B)=🟡、後 2(C/F)=🔴。此 KEEP/WATCH 切點為新增,顯式列此。
FUNDAMENTAL_KEEP_GRADES: tuple[str, ...] = ('A+', 'A', 'B+')
FUNDAMENTAL_WATCH_GRADES: tuple[str, ...] = ('B',)
# (CUT grades = shared.dividend_station_thresholds.STOCK_SWAP_GRADES,不在此重定義)

# ── 背離加註(§設計:只加註不翻轉)的訊息模板 ──
# 主軸🟢 但次軸🔴 / 主軸🔴 但次軸🟢 才算背離;其餘不出旗標。
DIVERGENCE_MSG_STRONG_PRIMARY_WEAK_SECONDARY: str = (
    '{primary_name}佳但{secondary_name}弱 —— 續抱可,留意進出時機')
DIVERGENCE_MSG_WEAK_PRIMARY_STRONG_SECONDARY: str = (
    '{primary_name}弱但{secondary_name}強 —— 反彈慎防當反轉')

AXIS_DISPLAY_NAME: dict[str, str] = {
    AXIS_TECHNICAL: '技術面',
    AXIS_FUNDAMENTAL: '基本面',
    AXIS_ETF_COMPOSITE: 'ETF綜合',
}
