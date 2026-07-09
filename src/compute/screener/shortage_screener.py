"""src/compute/screener/shortage_screener.py — 缺貨 / 供不應求選股計分 L2 純函式（v19.65）。

「缺貨選股」用四個間接財務/營運訊號交叉驗證「市場供不應求」：
  ① 合約負債大增（客戶預付訂金搶產能）      權重 35
  ② 毛利率走揚（成功轉嫁漲價）              權重 25
  ③ 存貨週轉天數下降（做出來就賣掉）        權重 20
  ④ 月營收 YoY 連續成長                    權重 20
四項計分加總（滿分 100）→ 分級（🟥強 / 🟧中 / ⬜不明顯）。

§8.2 layer:L2 Compute — **純函式,無 I/O,無 Streamlit,無 FinMind SDK**。
  抓取（合約負債/季損益/月營收）由 L3 `shortage_screener_service` 負責,本層只吃已對齊
  的季度序列 + 月營收 YoY,故可用合成資料完整單元測試。
§1 fail-loud:缺值/無科目一律回 None + 標「資料不足 / 無科目」旗標,**絕不補 0 造假**,
  也絕不拋 Exception（單股異常不影響整批）。
§3.3:所有門檻/權重從 SSOT import,無 inline magic number。

輸入 schema（per stock）:
    {
      "stock_id": "2330",
      "name": "台積電",
      "is_finance": False,                 # 金融股(代號 28/58)→ 不適用
      "quarters": [                        # 由「近到遠」排序,index 0 = 最新季 t
        {"label": "2025Q1", "revenue": ..., "gross_profit": ..., "cogs": ...,
         "contract_liab": ..., "inventory": ...},   # 單位「元」,任一值可為 None/NaN
        {"label": "2024Q4", ...},
        ...                                # 至少 5 季（SHORTAGE_MIN_QUARTERS）才能算 YoY
      ],
      "revenue_yoy_last3": [12.5, 15.1, 18.2],   # [M-2, M-1, M] 月營收 YoY%,元素可 None
    }
"""
from __future__ import annotations

import logging as _sh_log
from dataclasses import dataclass, field
from typing import Any

# ── SSOT：訊號邊界值（重用既有）+ 本篩選器權重/分級（新）─────────────
from shared.signal_thresholds import (
    CL_GROWTH_YOY_PCT,
    CL_SURGE_YOY_PCT,
    LEAD_CL_QOQ_SURGE_PCT,
)
from shared.shortage_screen_thresholds import (
    SHORTAGE_CL_GROWTH_SCORE,
    SHORTAGE_CL_QOQ_BONUS,
    SHORTAGE_CL_SURGE_SCORE,
    SHORTAGE_GM_DUAL_UP_SCORE,
    SHORTAGE_GM_SINGLE_UP_SCORE,
    SHORTAGE_INV_DUAL_DOWN_SCORE,
    SHORTAGE_INV_SINGLE_DOWN_SCORE,
    SHORTAGE_MIN_QUARTERS,
    SHORTAGE_QUARTER_DAYS,
    SHORTAGE_REV_PARTIAL_SCORE,
    SHORTAGE_REV_STEADY_SCORE,
    SHORTAGE_REV_STRONG_SCORE,
    SHORTAGE_REVENUE_YOY_MIN_PCT,
    SHORTAGE_TIER_MID_MIN,
    SHORTAGE_TIER_STRONG_MIN,
    SHORTAGE_VERSION,
    SHORTAGE_W_CONTRACT_LIAB,
    TIER_ICONS,
    TIER_INSUFFICIENT,
    TIER_MID,
    TIER_NA,
    TIER_STRONG,
    TIER_WEAK,
)

_logger = _sh_log.getLogger(__name__)


# ════════════════════════════════════════════════════════════════
# 輸出模型
# ════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class ShortageScore:
    """單股缺貨評分結果。total=四訊號加總（0-100）;tier=分級 label。"""

    stock_id: str
    name: str
    total: float
    tier: str
    tier_icon: str
    c1_contract_liab: float
    c2_gross_margin: float
    c3_inventory_days: float
    c4_revenue_yoy: float
    cl_na: bool                       # True = 無合約負債科目 → 缺最核心訊號,已降級
    reasons: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    version: str = SHORTAGE_VERSION

    @property
    def reason_text(self) -> str:
        return "；".join(self.reasons)

    def to_row(self) -> dict[str, Any]:
        """→ 供 DataFrame / UI 表格用的一列。"""
        return {
            "代碼": self.stock_id,
            "名稱": self.name,
            "缺貨分數": round(self.total, 1),
            "訊號強度": f"{self.tier_icon} {self.tier}",
            "①合約負債": round(self.c1_contract_liab, 1),
            "②毛利率": round(self.c2_gross_margin, 1),
            "③存貨天數": round(self.c3_inventory_days, 1),
            "④月營收": round(self.c4_revenue_yoy, 1),
            "理由": self.reason_text,
            "_tier": self.tier,
        }


# ════════════════════════════════════════════════════════════════
# Safe accessors — 缺值/非數字/NaN 一律 None,絕不拋
# ════════════════════════════════════════════════════════════════
def _num(v: Any) -> float | None:
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if f != f:  # NaN
        return None
    return f


def _q_get(quarters: Any, idx: int, key: str) -> float | None:
    """取第 idx 季（0=最新）的 key 欄位數值,越界/缺欄回 None。"""
    if not isinstance(quarters, list) or idx < 0 or idx >= len(quarters):
        return None
    q = quarters[idx]
    if not isinstance(q, dict):
        return None
    return _num(q.get(key))


def _gm_at(quarters: Any, idx: int) -> float | None:
    """第 idx 季毛利率(%) = 毛利 / 營收 × 100。營收 ≤ 0 → None（§4.4 防除零）。"""
    rev = _q_get(quarters, idx, "revenue")
    gp = _q_get(quarters, idx, "gross_profit")
    if rev is None or gp is None or rev <= 0:
        return None
    return gp / rev * 100.0


def _dio_at(quarters: Any, idx: int) -> float | None:
    """第 idx 季存貨在手天數 DIO = 存貨 /（近 4 季營業成本 / 365）。

    需 idx..idx+3 四季成本齊全且和 > 0、idx 季存貨齊全,否則 None（§4.1：用近 4 季
    成本年化,避免單季成本 ×90 粗估失真）。
    """
    inv = _q_get(quarters, idx, "inventory")
    if inv is None:
        return None
    cogs_ttm = 0.0
    for j in range(idx, idx + 4):
        c = _q_get(quarters, j, "cogs")
        if c is None:
            return None
        cogs_ttm += c
    if cogs_ttm <= 0:
        return None
    return inv / (cogs_ttm / SHORTAGE_QUARTER_DAYS)


# ════════════════════════════════════════════════════════════════
# ① 合約負債（35）
# ════════════════════════════════════════════════════════════════
def _score_contract_liab(quarters: Any) -> tuple[float, bool, str, dict]:
    """回 (score, cl_na, reason, metrics)。cl_na=True 表示無合約負債科目（不當壞事,標降級）。"""
    cl_t = _q_get(quarters, 0, "contract_liab")
    cl_t1 = _q_get(quarters, 1, "contract_liab")
    cl_t4 = _q_get(quarters, 4, "contract_liab")

    if cl_t is None:
        return 0.0, True, "⚪合約負債：無此科目（服務/金融業常見，信心降級）", {
            "cl_yoy": None, "cl_qoq": None}

    cl_yoy = ((cl_t / cl_t4 - 1.0) * 100.0) if (cl_t4 is not None and cl_t4 > 0) else None
    cl_qoq = ((cl_t / cl_t1 - 1.0) * 100.0) if (cl_t1 is not None and cl_t1 > 0) else None

    score = 0.0
    if cl_yoy is not None and cl_yoy >= CL_SURGE_YOY_PCT:
        score = SHORTAGE_CL_SURGE_SCORE
    elif cl_yoy is not None and cl_yoy >= CL_GROWTH_YOY_PCT:
        score = SHORTAGE_CL_GROWTH_SCORE
    if cl_qoq is not None and cl_qoq >= LEAD_CL_QOQ_SURGE_PCT:
        score = min(SHORTAGE_W_CONTRACT_LIAB, score + SHORTAGE_CL_QOQ_BONUS)

    if score > 0:
        _parts = []
        if cl_yoy is not None:
            _parts.append(f"YoY{cl_yoy:+.0f}%")
        if cl_qoq is not None:
            _parts.append(f"QoQ{cl_qoq:+.0f}%")
        icon = "🟢" if score >= SHORTAGE_CL_GROWTH_SCORE else "🟡"
        reason = f"{icon}合約負債{'/'.join(_parts)}"
    elif cl_yoy is None and cl_qoq is None:
        reason = "⚪合約負債：基期不足無法比較"
    else:
        _p = []
        if cl_yoy is not None:
            _p.append(f"YoY{cl_yoy:+.0f}%")
        if cl_qoq is not None:
            _p.append(f"QoQ{cl_qoq:+.0f}%")
        reason = f"🔴合約負債{'/'.join(_p)}（未達門檻）"
    return score, False, reason, {"cl_yoy": cl_yoy, "cl_qoq": cl_qoq}


# ════════════════════════════════════════════════════════════════
# ② 毛利率走揚（25）
# ════════════════════════════════════════════════════════════════
def _score_gross_margin(quarters: Any) -> tuple[float, str, dict]:
    gm_t = _gm_at(quarters, 0)
    gm_t1 = _gm_at(quarters, 1)
    gm_t4 = _gm_at(quarters, 4)
    metrics = {"gm_t": gm_t, "gm_t1": gm_t1, "gm_t4": gm_t4}

    if gm_t is None or gm_t1 is None or gm_t4 is None:
        return 0.0, "⚪毛利率：資料不足", metrics

    up_qoq = gm_t > gm_t1
    up_yoy = gm_t > gm_t4
    if up_qoq and up_yoy:
        return SHORTAGE_GM_DUAL_UP_SCORE, f"🟢毛利率{gm_t:.1f}%（季增+年增雙升）", metrics
    if up_qoq or up_yoy:
        _which = "季增" if up_qoq else "年增"
        return SHORTAGE_GM_SINGLE_UP_SCORE, f"🟡毛利率{gm_t:.1f}%（僅{_which}）", metrics
    return 0.0, f"🔴毛利率{gm_t:.1f}%（未走揚）", metrics


# ════════════════════════════════════════════════════════════════
# ③ 存貨週轉天數下降（20）
# ════════════════════════════════════════════════════════════════
def _score_inventory_days(quarters: Any) -> tuple[float, str, dict]:
    dio_t = _dio_at(quarters, 0)
    dio_t1 = _dio_at(quarters, 1)
    dio_t4 = _dio_at(quarters, 4)
    metrics = {"dio_t": dio_t, "dio_t1": dio_t1, "dio_t4": dio_t4}

    if dio_t is None or dio_t1 is None:
        return 0.0, "⚪存貨天數：資料不足（或無存貨：金融/服務業）", metrics

    down_qoq = dio_t < dio_t1
    down_yoy = (dio_t < dio_t4) if dio_t4 is not None else None
    known = [s for s in (down_qoq, down_yoy) if s is not None]
    n_down = sum(1 for s in known if s)

    if len(known) == 2 and n_down == 2:
        return SHORTAGE_INV_DUAL_DOWN_SCORE, f"🟢存貨天數{dio_t:.0f}天（較上季+去年同季雙降）", metrics
    if n_down >= 1:
        return SHORTAGE_INV_SINGLE_DOWN_SCORE, f"🟡存貨天數{dio_t:.0f}天（下降中）", metrics
    return 0.0, f"🔴存貨天數{dio_t:.0f}天（未下降）", metrics


# ════════════════════════════════════════════════════════════════
# ④ 月營收 YoY 連續成長（20）
# ════════════════════════════════════════════════════════════════
def _score_revenue_yoy(yoy_last3: Any) -> tuple[float, str, dict]:
    raw = yoy_last3 if isinstance(yoy_last3, list) else []
    valid = [y for y in (_num(v) for v in raw) if y is not None]
    metrics = {"rev_yoy_last3": [_num(v) for v in raw]}

    if len(valid) < 2:
        return 0.0, "⚪月營收 YoY：資料不足", metrics

    _min = SHORTAGE_REVENUE_YOY_MIN_PCT
    all_above = all(y > _min for y in valid)
    increasing = all(valid[i] < valid[i + 1] for i in range(len(valid) - 1))
    _last = valid[-1]

    if all_above and increasing:
        return SHORTAGE_REV_STRONG_SCORE, f"🟢月營收 YoY 逐月加速（末月{_last:+.0f}%）", metrics
    if all_above:
        return SHORTAGE_REV_STEADY_SCORE, f"🟡月營收 YoY 皆>{_min:.0f}%（末月{_last:+.0f}%）", metrics
    if any(y > _min for y in valid):
        return SHORTAGE_REV_PARTIAL_SCORE, f"🟡月營收 YoY 部分達標（末月{_last:+.0f}%）", metrics
    return 0.0, f"🔴月營收 YoY 動能不足（末月{_last:+.0f}%）", metrics


# ════════════════════════════════════════════════════════════════
# 分級
# ════════════════════════════════════════════════════════════════
def _tier_from_total(total: float) -> str:
    if total >= SHORTAGE_TIER_STRONG_MIN:
        return TIER_STRONG
    if total >= SHORTAGE_TIER_MID_MIN:
        return TIER_MID
    return TIER_WEAK


def _count_quarters(quarters: Any) -> int:
    if not isinstance(quarters, list):
        return 0
    return sum(1 for q in quarters if isinstance(q, dict))


# ════════════════════════════════════════════════════════════════
# 主評分
# ════════════════════════════════════════════════════════════════
def score_shortage(stock: Any) -> ShortageScore:
    """單股缺貨評分。任何缺值/異常 → 回帶旗標的降級結果,絕不拋 Exception。"""
    if not isinstance(stock, dict):
        return _na_result("", "", TIER_NA, "輸入格式錯誤")

    stock_id = str(stock.get("stock_id") or stock.get("id") or "").strip()
    name = str(stock.get("name") or "")

    # 金融股（代號 28/58 開頭）：毛利率/存貨/合約負債概念不通用 → 不適用
    if bool(stock.get("is_finance")):
        return _na_result(stock_id, name, TIER_NA,
                          "金融股不適用缺貨模型（毛利率/存貨/合約負債概念不通用）")

    quarters = stock.get("quarters") or []
    n_q = _count_quarters(quarters)
    if n_q < SHORTAGE_MIN_QUARTERS:
        return _na_result(stock_id, name, TIER_INSUFFICIENT,
                          f"季財報僅 {n_q} 季（需 ≥{SHORTAGE_MIN_QUARTERS} 季算年增）")

    c1, cl_na, r1, m1 = _score_contract_liab(quarters)
    c2, r2, m2 = _score_gross_margin(quarters)
    c3, r3, m3 = _score_inventory_days(quarters)
    c4, r4, m4 = _score_revenue_yoy(stock.get("revenue_yoy_last3"))

    total = c1 + c2 + c3 + c4
    tier = _tier_from_total(total)

    reasons = [r for r in (r1, r2, r3, r4) if r]
    # 無合約負債科目 → 缺最核心的缺貨證據 → 強訊號封頂為中度（fail-loud 誠實降級）
    if cl_na and tier == TIER_STRONG:
        tier = TIER_MID
        reasons.append("⚠️因無合約負債科目，強訊號降級為中度")

    metrics = {**m1, **m2, **m3, **m4, "n_quarters": n_q}
    return ShortageScore(
        stock_id=stock_id, name=name, total=total, tier=tier,
        tier_icon=TIER_ICONS.get(tier, ""),
        c1_contract_liab=c1, c2_gross_margin=c2,
        c3_inventory_days=c3, c4_revenue_yoy=c4,
        cl_na=cl_na, reasons=reasons, metrics=metrics,
    )


def _na_result(stock_id: str, name: str, tier: str, reason: str) -> ShortageScore:
    return ShortageScore(
        stock_id=stock_id, name=name, total=0.0, tier=tier,
        tier_icon=TIER_ICONS.get(tier, ""),
        c1_contract_liab=0.0, c2_gross_margin=0.0,
        c3_inventory_days=0.0, c4_revenue_yoy=0.0,
        cl_na=False, reasons=[reason], metrics={},
    )


# ════════════════════════════════════════════════════════════════
# 批次 + 排序
# ════════════════════════════════════════════════════════════════
def rank_shortage(
    stocks: Any,
    *,
    include_na: bool = False,
) -> list[ShortageScore]:
    """批次評分 + 依缺貨分數由高到低排序。

    Args:
        stocks: list of stock dict（見模組 docstring schema）
        include_na: True 則保留「資料不足/不適用」（排在最後）;預設 False 只回可評分者

    Returns:
        list[ShortageScore]（單股異常會被吃掉不影響整批）
    """
    if not isinstance(stocks, list):
        return []
    scored: list[ShortageScore] = []
    for s in stocks:
        try:
            scored.append(score_shortage(s))
        except Exception as e:  # noqa: BLE001 — 單股異常不炸整批
            _logger.warning("[shortage] 單股評分異常: %s: %s", type(e).__name__, e)
    _rankable = {TIER_STRONG, TIER_MID, TIER_WEAK}
    if not include_na:
        scored = [s for s in scored if s.tier in _rankable]
    # 可評分者依 total 降冪；不可評分者（include_na）沉底
    scored.sort(key=lambda s: (s.tier in _rankable, s.total), reverse=True)
    return scored


def to_rows(scores: list[ShortageScore]) -> list[dict]:
    """list[ShortageScore] → list[dict]（DataFrame-ready）。"""
    return [s.to_row() for s in scores]
