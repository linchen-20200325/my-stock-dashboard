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
§4.5 時序對齊:t-1 / t-4 / TTM 四季一律以 **季序**(label 'YYYYQn' 或 date)取,
  不用 list 位置 —— 季序列有洞時位置 4 ≠ 去年同季(B6-b 2026-08 修,同
  monthly_revenue_calc v19.83「位置索引當去年同月」的 bug 形狀)。
  季別無 label/date 可定序時才退回位置索引(舊行為;連續序列兩法等價)。

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
from src.compute.health.monthly_revenue_month_contract import (
    MONTH_CONTRACT_KEY,
    STATUS_FAIL_CLOSED,
    STATUS_OK,
    TARGET_MONTHS,
    legacy_undetermined_contract,
)
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
    # ── DEC-149 Phase 3B（2026-11-08）schema-additive：缺值 vs 真 0 分的旗標 ──────────────
    # 「ok」＝該分項**沒有**走進本檔既有的「資料不足 → 0 分」分支（定義逐字取自各 _score_* 的資料不足
    # 判斷，**不是**新的「有效／獨立」資格或門檻）。只是旗標：⛔ 不改任何分數、權重、tier 門檻。
    # None＝舊建構（呼叫端沒給）＝「未評估」，⛔ 不等於 False（缺值）。
    n_signals_ok: int | None = None
    c1_ok: bool | None = None
    c2_ok: bool | None = None
    c3_ok: bool | None = None
    c4_ok: bool | None = None
    miss_reason: str = ""             # 缺值原因（短字串；全部 ok 或未評估 → ""）

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
            # DEC-149 Phase 3B additive：舊 consumer 讀既有鍵不受影響；缺貨分數 0.0 可能是
            # 「真 0 分」或「該項缺值」→ 看下列旗標區分（⛔ 不改分數數值）。
            "有效訊號數": self.n_signals_ok,
            "缺值原因": self.miss_reason,
            "_n_signals_ok": self.n_signals_ok,
            "_c1_ok": self.c1_ok,
            "_c2_ok": self.c2_ok,
            "_c3_ok": self.c3_ok,
            "_c4_ok": self.c4_ok,
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


# ════════════════════════════════════════════════════════════════
# 季序對齊（§2.3 PIT / §4.5 時序對齊）— 不用「位置」當「季距」
# ════════════════════════════════════════════════════════════════
# B6-b(2026-08):原本 t-1 / t-4 / TTM 四季一律用 **list 位置** 索引(quarters[1] /
# quarters[4] / range(idx, idx+4)),等於假設「季序列連續無缺季」。實際 L1
# `fetch_quarterly_shortage_frame` 的季別來自「損益表日期 ∪ 資產負債表日期」的
# 聯集,任一邊缺季 / FinMind 該季無資料 → 序列出現洞,位置 4 就不再是「去年同季」,
# 而會**靜默**拿前年 Q4 之類的錯基期算 YoY。
# 這與 monthly_revenue_calc v19.83 修掉的「位置索引 −12 當去年同月」是同一個 bug
# 形狀(見 src/compute/health/monthly_revenue_calc.py:63-66 註解),此處補上同一解法:
# 以 label 'YYYYQn' / date 'YYYY-MM-DD' 換算「季序 ordinal」查表;整批無法定序時
# 才退回位置索引(舊行為,連續序列兩法等價)。缺該季 → 回 None(§1 絕不拿鄰季冒充)。
_QUARTERS_PER_YEAR = 4


def _q_ordinal(q: Any) -> int | None:
    """單季 → 季序 ordinal(年×4 + 季−1)。優先 label 'YYYYQn',退 date 'YYYY-MM-DD'。

    兩者皆無法解析 → None(caller 整批退回位置索引 = 舊行為)。
    """
    if not isinstance(q, dict):
        return None
    _lab = str(q.get("label") or "").strip().upper()
    if "Q" in _lab:
        _y_txt, _, _s_txt = _lab.partition("Q")
        try:
            _y, _s = int(_y_txt), int(_s_txt)
        except ValueError:
            _y = _s = 0
        if _y > 0 and 1 <= _s <= _QUARTERS_PER_YEAR:
            return _y * _QUARTERS_PER_YEAR + (_s - 1)
    _d = str(q.get("date") or "").strip()
    if len(_d) >= 7:
        try:
            _y, _m = int(_d[:4]), int(_d[5:7])
        except ValueError:
            return None
        if _y > 0 and 1 <= _m <= 12:
            return _y * _QUARTERS_PER_YEAR + ((_m - 1) // 3)
    return None


def _offset_index_map(quarters: Any) -> dict[int, int] | None:
    """{距最新季幾季: list index}。任一季無法定序 → None(退回位置索引)。"""
    if not isinstance(quarters, list) or not quarters:
        return None
    _ords: list[tuple[int, int]] = []
    for _i, _q in enumerate(quarters):
        _o = _q_ordinal(_q)
        if _o is None:
            return None                       # 混雜/無標記 → 整批退回位置索引
        _ords.append((_o, _i))
    # 整批季別標記**全部相同**(如 label 全 'Q'、date 全同一天)⇒ 該欄位不帶季序資訊,
    # 與「無標記」同類 → 退回位置索引。若不擋,下面 setdefault 會產出只剩
    # {0: 0} 的**退化 map**,t-1 / t-4 一律查不到 ⇒ 每個 YoY 訊號都被誤標資料不足。
    # ⚠️ 只擋「全同一季」這種完全退化;偶有重複(如某季被重報兩次)仍走 ordinal 路徑,
    #    由下面的 setdefault 取先出現者,缺的那季照常標資料不足(那才是正確的 §1 行為)。
    if len({_o for _o, _ in _ords}) == 1 and len(_ords) > 1:
        return None
    _latest = max(_o for _o, _ in _ords)
    _out: dict[int, int] = {}
    for _o, _i in _ords:
        _out.setdefault(_latest - _o, _i)     # 同季重複 → 取先出現者(近→遠慣例)
    return _out


def _at(quarters: Any, omap: dict[int, int] | None, offset: int) -> int:
    """「最新季往前 offset 季」的 list index。

    omap 為 None(無法定序)→ 退回位置索引 offset(舊行為)。
    可定序但**該季不存在** → 回 -1 ⇒ `_q_get` 回 None ⇒ 該訊號標資料不足(§1)。
    """
    if omap is None:
        return int(offset)
    return omap.get(int(offset), -1)


def _gm_at(quarters: Any, omap: dict[int, int] | None, offset: int) -> float | None:
    """距最新季 offset 季的毛利率(%) = 毛利 / 營收 × 100。營收 ≤ 0 → None（§4.4 防除零）。"""
    _i = _at(quarters, omap, offset)
    rev = _q_get(quarters, _i, "revenue")
    gp = _q_get(quarters, _i, "gross_profit")
    if rev is None or gp is None or rev <= 0:
        return None
    return gp / rev * 100.0


def _dio_at(quarters: Any, omap: dict[int, int] | None, offset: int) -> float | None:
    """距最新季 offset 季的存貨在手天數 DIO = 存貨 /（近 4 季營業成本 / 365）。

    需 offset..offset+3 **四個真實季**的成本齊全且和 > 0、該季存貨齊全,否則 None
    （§4.1：用近 4 季成本年化,避免單季成本 ×90 粗估失真;§4.5：四季以「季序」取,
    缺季不以鄰季頂替）。
    """
    inv = _q_get(quarters, _at(quarters, omap, offset), "inventory")
    if inv is None:
        return None
    cogs_ttm = 0.0
    for j in range(int(offset), int(offset) + _QUARTERS_PER_YEAR):
        c = _q_get(quarters, _at(quarters, omap, j), "cogs")
        if c is None:
            return None
        cogs_ttm += c
    if cogs_ttm <= 0:
        return None
    return inv / (cogs_ttm / SHORTAGE_QUARTER_DAYS)


# ════════════════════════════════════════════════════════════════
# ① 合約負債（35）
# ════════════════════════════════════════════════════════════════
def _score_contract_liab(quarters: Any, omap: dict[int, int] | None) -> tuple[float, bool, str, dict]:
    """回 (score, cl_na, reason, metrics)。cl_na=True 表示無合約負債科目（不當壞事,標降級）。"""
    cl_t = _q_get(quarters, _at(quarters, omap, 0), "contract_liab")
    cl_t1 = _q_get(quarters, _at(quarters, omap, 1), "contract_liab")
    cl_t4 = _q_get(quarters, _at(quarters, omap, _QUARTERS_PER_YEAR), "contract_liab")

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
def _score_gross_margin(quarters: Any, omap: dict[int, int] | None) -> tuple[float, str, dict]:
    gm_t = _gm_at(quarters, omap, 0)
    gm_t1 = _gm_at(quarters, omap, 1)
    gm_t4 = _gm_at(quarters, omap, _QUARTERS_PER_YEAR)
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
def _score_inventory_days(quarters: Any, omap: dict[int, int] | None) -> tuple[float, str, dict]:
    dio_t = _dio_at(quarters, omap, 0)
    dio_t1 = _dio_at(quarters, omap, 1)
    dio_t4 = _dio_at(quarters, omap, _QUARTERS_PER_YEAR)
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
# ④ 月營收 YoY 連續成長（20）  —— DEC-151 Batch B：依『月份資料契約』評分
# ════════════════════════════════════════════════════════════════
# 客戶裁示(DEC-151):C4 採最近三個完整且到公告時點的日曆月、可信月份鍵、保留缺值位置;
# 不連續不得判逐月加速,可依既有部分達標規則評分但不得虛構證據。
# 修前 bug:`valid = [非 None]` 把缺值壓縮掉 → `[20,None,40]` 被當成連續兩月『逐月加速』。
# 現行:固定 3 個『位置』(契約 yoy_target3;缺值保留 None),五項獨立欄位各自判定,**不壓成單一布林**。
# 只重用既有分支與既有常數(STRONG/STEADY/PARTIAL 分數、SHORTAGE_REVENUE_YOY_MIN_PCT),不新增分數/門檻/權重。
_BASIS_TARGET = "target3"        # 評分輸入 = 契約的固定 3 個目標月 YoY(yoy_target3)
_BASIS_LEGACY = "legacy_last3"   # 無目標月(as_of 缺/舊輸入)→ 退回舊 revenue_yoy_last3 的 3 個位置
_FLAGS3 = ("target_observed", "target_base_valid", "target_yoy_computable")


def _as3(x: Any) -> list:
    """任意輸入 → 長度 3 的 list(不足左補 None、過長取最後 3、非 list → 全 None)。保留位置,不壓縮。"""
    if not isinstance(x, (list, tuple)):
        return [None] * TARGET_MONTHS
    _l = list(x)[-TARGET_MONTHS:]
    return [None] * (TARGET_MONTHS - len(_l)) + _l


def _labels_consecutive(labels: list) -> bool:
    """3 個 'YYYY-MM' 是否為連續日曆月(任一為 None/無法解析 → False;跨年 12→01 正確)。"""
    try:
        _idx = [int(m[:4]) * 12 + int(m[5:7]) - 1 for m in labels]
    except (TypeError, ValueError, IndexError):
        return False
    return all(b - a == 1 for a, b in zip(_idx, _idx[1:]))


def _c4_result(score: float, reason: str, metrics: dict, *, ok: bool, miss: str = "") -> tuple[float, str, dict]:
    metrics["rev_c4_ok"] = ok
    metrics["rev_c4_miss"] = "" if ok else miss
    return score, reason, metrics


def _score_revenue_yoy(yoy_last3: Any, contract: Any = None) -> tuple[float, str, dict]:
    """C4 評分。`contract`＝DEC-151 Batch A 月份資料契約(缺 → 舊輸入 UNDETERMINED,**不得**判逐月加速)。

    判定用契約五項獨立欄位(連續性/觀測/基期/可算/公告時點),缺值保留位置:
      FAIL_CLOSED               → 資料不足(0 分,c4_ok=False),不是真 0 分
      STRONG(逐月加速)          → 契約 OK 且 3 目標月皆『觀測+基期有效+可算』、連續、3 月公告時點資格皆 True、
                                  嚴格遞增、皆 > 門檻;任一為 None(NOT VERIFIED)/False/缺月 → 禁止
      STEADY(皆>門檻)           → 3 個位置皆有值、連續(舊輸入連續性 UNDETERMINED 亦允許但註記)、皆 > 門檻
      PARTIAL / 動能不足 / 資料不足 → 有缺月或不連續:有效值(保留位置)≥2 且任一>門檻 → PARTIAL;
                                  ≥2 皆≤門檻 → 動能不足;<2 → 資料不足。**不給 STEADY/STRONG**,不補值、不把缺月當 0
    真 0% / 負 YoY 是有效值(0.0 / 負數),與 missing(None)嚴格區分。
    """
    c = contract if isinstance(contract, dict) and "contract_status" in contract \
        else legacy_undetermined_contract()
    status = c.get("contract_status")
    legacy = [_num(v) for v in (yoy_last3 if isinstance(yoy_last3, list) else [])]
    metrics: dict[str, Any] = {
        "rev_yoy_last3": list(legacy),          # 舊 key 保留(舊 consumer / CLI 讀它)
        "rev_c4_contract_status": status,
        "rev_c4_basis": "none",
        "rev_yoy_scored": [None] * TARGET_MONTHS,
        "rev_target_months": [None] * TARGET_MONTHS,
        "rev_missing_reasons": [None] * TARGET_MONTHS,
        "rev_contiguous": None,
        "rev_date_eligible": [None] * TARGET_MONTHS,
        "rev_strong_blocked_by": [],
    }

    if status == STATUS_FAIL_CLOSED:
        _why = ",".join(str(r) for r in (c.get("contract_fail_reasons") or [])) or "未註明"
        return _c4_result(0.0, f"⚪月營收 YoY：資料不足（月份契約 FAIL_CLOSED：{_why}）", metrics, ok=False,
                          miss=f"④月營收月份契約FAIL_CLOSED({_why})")

    # ── 評分輸入:優先『固定 3 個目標月』(保留位置);目標月未定(as_of 缺/舊輸入)→ 退回舊 3 位置 ──
    _tm = _as3(c.get("yoy_target_months"))
    use_target = status == STATUS_OK and all(m is not None for m in _tm)
    if use_target:
        basis, labels = _BASIS_TARGET, _tm
        raw3 = [_num(v) for v in _as3(c.get("yoy_target3"))]
        contiguous: bool | None = _labels_consecutive(labels)
        elig = _as3(c.get("target_date_eligible"))
        reasons3 = _as3(c.get("yoy_missing_reasons"))
        flags = [_as3(c.get(k)) for k in _FLAGS3]
        # 值存在但契約明說『該月未觀測/基期無效/不可算』(False)→ 視為不可用(fail-closed,不信不一致的值)
        vals = [None if (raw3[i] is not None and any(f[i] is False for f in flags)) else raw3[i]
                for i in range(TARGET_MONTHS)]
        flags_all_true = all(f[i] is True for f in flags for i in range(TARGET_MONTHS))
    else:
        basis = _BASIS_LEGACY
        _ym = _as3(c.get("yoy_months")) if status == STATUS_OK else [None] * TARGET_MONTHS
        labels = _ym
        vals = _as3(legacy)
        contiguous = c.get("yoy_months_contiguous") if status == STATUS_OK else None  # 舊輸入 = UNDETERMINED
        elig = [None] * TARGET_MONTHS            # 沒有目標月 → 公告時點資格一律 NOT VERIFIED
        reasons3 = [None] * TARGET_MONTHS
        flags_all_true = False
    metrics.update({"rev_c4_basis": basis, "rev_yoy_scored": list(vals), "rev_target_months": list(labels),
                    "rev_missing_reasons": list(reasons3), "rev_contiguous": contiguous,
                    "rev_date_eligible": list(elig)})

    _min = SHORTAGE_REVENUE_YOY_MIN_PCT
    idx_valid = [i for i, v in enumerate(vals) if v is not None]
    valid = [vals[i] for i in idx_valid]
    n_missing = TARGET_MONTHS - len(valid)

    def _pos(i: int) -> str:
        return labels[i] if labels[i] else f"第{i + 1}位"

    _missing_desc = "、".join(f"{_pos(i)}" + (f"({reasons3[i]})" if reasons3[i] else "")
                              for i in range(TARGET_MONTHS) if vals[i] is None)

    if len(valid) < 2:
        _miss = (f"④月營收缺月/不連續(有值{len(valid)}/{TARGET_MONTHS})" if basis == _BASIS_TARGET and n_missing
                 else "④月營收有效月數<2")
        _tail = f"（缺：{_missing_desc}）" if n_missing and basis == _BASIS_TARGET else ""
        return _c4_result(0.0, f"⚪月營收 YoY：資料不足{_tail}", metrics, ok=False, miss=_miss)

    _last = valid[-1]
    all_above = all(y > _min for y in valid)

    # ── 3 個位置皆有值 ───────────────────────────────────────────────
    if n_missing == 0 and contiguous is not False:
        increasing = all(valid[i] < valid[i + 1] for i in range(len(valid) - 1))
        if all_above:
            blockers: list[str] = []
            if status != STATUS_OK:          # 無月份契約(舊輸入/UNDETERMINED):連續性與日期資格皆 NOT VERIFIED
                blockers.append(f"契約{status}(連續性與日期資格 NOT VERIFIED)")
            else:
                if basis != _BASIS_TARGET:
                    blockers.append("目標月未定")
                if basis == _BASIS_TARGET and not flags_all_true:
                    blockers.append("觀測/基期/可算未全確認")
                if c.get("yoy_months_contiguous") is not True:
                    blockers.append("連續性未確認")
                if not all(e is True for e in elig):
                    blockers.append("日期資格 NOT VERIFIED" if any(e is None for e in elig) else "日期資格未通過")
            metrics["rev_strong_blocked_by"] = blockers if increasing else []
            if increasing and not blockers:
                return _c4_result(SHORTAGE_REV_STRONG_SCORE, f"🟢月營收 YoY 逐月加速（末月{_last:+.0f}%）",
                                  metrics, ok=True)
            _note = ""
            if increasing and blockers:
                _note = f"；未判定加速：{'、'.join(blockers)}"
            elif contiguous is None:
                _note = "；月份連續性未驗證"
            return _c4_result(SHORTAGE_REV_STEADY_SCORE, f"🟡月營收 YoY 皆>{_min:.0f}%（末月{_last:+.0f}%{_note}）",
                              metrics, ok=True)
        if any(y > _min for y in valid):
            return _c4_result(SHORTAGE_REV_PARTIAL_SCORE, f"🟡月營收 YoY 部分達標（末月{_last:+.0f}%）",
                              metrics, ok=True)
        return _c4_result(0.0, f"🔴月營收 YoY 動能不足（末月{_last:+.0f}%）", metrics, ok=True)

    # ── 有缺月 / 不連續:不得 STEADY/STRONG;僅依既有『部分達標』『動能不足』規則,不補值 ──
    metrics["rev_strong_blocked_by"] = ["缺月" if n_missing else "不連續"]
    _gap = (f"缺：{_missing_desc}" if n_missing else "月份不連續")
    if any(y > _min for y in valid):
        return _c4_result(SHORTAGE_REV_PARTIAL_SCORE,
                          f"🟡月營收 YoY 部分達標（{len(valid)}/{TARGET_MONTHS}月有值，{_gap}；最近有值月{_last:+.0f}%）",
                          metrics, ok=True)
    return _c4_result(0.0, f"🔴月營收 YoY 動能不足（{len(valid)}/{TARGET_MONTHS}月有值，{_gap}；最近有值月{_last:+.0f}%）",
                      metrics, ok=True)


# ════════════════════════════════════════════════════════════════
# 有效旗標（DEC-149 Phase 3B）—— 只讀各分項既有的「資料不足」判斷,不新增任何有效定義
# ════════════════════════════════════════════════════════════════
def _signal_flags(cl_na: bool, m1: dict, m2: dict, m3: dict, m4: dict) -> tuple[
        tuple[bool, bool, bool, bool], str]:
    """回 ((c1_ok, c2_ok, c3_ok, c4_ok), miss_reason)。ok＝未走進該分項的『資料不足』0 分分支。

    逐項對應既有判斷（⛔ 不得改成別的定義）：
      C1 _score_contract_liab：t 期合約負債存在（非 cl_na）且 YoY／QoQ 至少算得出一個
         （兩者皆 None ＝ 既有的「基期不足無法比較」資料不足分支）
      C2 _score_gross_margin：gm_t／gm_t1／gm_t4 皆有
      C3 _score_inventory_days：dio_t 與 dio_t1 皆有（dio_t4 缺不算資料不足,既有行為）
      C4 _score_revenue_yoy：沒走進『資料不足』分支＝契約非 FAIL_CLOSED 且『保留位置』的有效月數 ≥ 2
         （DEC-151 Batch B：由 `_score_revenue_yoy` 回報 `rev_c4_ok`；舊手建 m4 沒有該鍵時退回舊算法）
    """
    c1 = (not cl_na) and (m1.get("cl_yoy") is not None or m1.get("cl_qoq") is not None)
    c2 = all(m2.get(k) is not None for k in ("gm_t", "gm_t1", "gm_t4"))
    c3 = m3.get("dio_t") is not None and m3.get("dio_t1") is not None
    c4 = m4.get("rev_c4_ok")
    if c4 is None:   # 舊手建 m4(無 Batch B 鍵)→ 舊算法
        c4 = sum(1 for y in (m4.get("rev_yoy_last3") or []) if y is not None) >= 2
    miss: list[str] = []
    if not c1:
        miss.append("①合約負債無科目" if cl_na else "①合約負債基期不足")
    if not c2:
        miss.append("②毛利率資料不足")
    if not c3:
        miss.append("③存貨天數資料不足")
    if not c4:
        miss.append(m4.get("rev_c4_miss") or "④月營收有效月數<2")
    return (c1, c2, c3, c4), "、".join(miss)


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

    # 季序對齊表(§4.5):有 label/date → 以「季序」取 t-1 / t-4 / TTM 四季;
    # 無標記 → None ⇒ 退回位置索引(舊行為,連續序列等價)。
    omap = _offset_index_map(quarters)

    c1, cl_na, r1, m1 = _score_contract_liab(quarters, omap)
    c2, r2, m2 = _score_gross_margin(quarters, omap)
    c3, r3, m3 = _score_inventory_days(quarters, omap)
    c4, r4, m4 = _score_revenue_yoy(stock.get("revenue_yoy_last3"),
                                     stock.get(MONTH_CONTRACT_KEY))

    total = c1 + c2 + c3 + c4
    tier = _tier_from_total(total)

    reasons = [r for r in (r1, r2, r3, r4) if r]
    # 無合約負債科目 → 缺最核心的缺貨證據 → 強訊號封頂為中度（fail-loud 誠實降級）
    if cl_na and tier == TIER_STRONG:
        tier = TIER_MID
        reasons.append("⚠️因無合約負債科目，強訊號降級為中度")

    # §5 可觀測性:quarter_aligned=False 代表該檔季別無 label/date 可定序,
    # t-1 / t-4 是用「list 位置」取的(連續序列才等價)。
    metrics = {**m1, **m2, **m3, **m4, "n_quarters": n_q,
               "quarter_aligned": omap is not None}

    # DEC-149 Phase 3B：四項全缺（n_signals_ok == 0）→ 無法評估,不進正式排名。
    # 重用 TIER_INSUFFICIENT（「資料不足」＝無法評估,語意吻合；`_rankable` 與 L3 `_RANKABLE_TIERS`
    # 本來就不含它 → 排除邏輯與診斷列分流不需另開 tier）。此時 total 必為 0.0（四項皆走資料不足 0 分分支）,
    # 分數數值照舊不動；與「資料完整、四項真低分」（n_ok=4,仍是 TIER_WEAK 且在榜）靠旗標區分。
    (f1, f2, f3, f4), miss_reason = _signal_flags(cl_na, m1, m2, m3, m4)
    n_ok = int(f1) + int(f2) + int(f3) + int(f4)
    if n_ok == 0:
        tier = TIER_INSUFFICIENT
        reasons.append("四項缺貨訊號皆缺值，無法評估（資料不足，不是 0 分）")
    return ShortageScore(
        stock_id=stock_id, name=name, total=total, tier=tier,
        tier_icon=TIER_ICONS.get(tier, ""),
        c1_contract_liab=c1, c2_gross_margin=c2,
        c3_inventory_days=c3, c4_revenue_yoy=c4,
        cl_na=cl_na, reasons=reasons, metrics=metrics,
        n_signals_ok=n_ok, c1_ok=f1, c2_ok=f2, c3_ok=f3, c4_ok=f4,
        miss_reason=miss_reason,
    )


def _na_result(stock_id: str, name: str, tier: str, reason: str) -> ShortageScore:
    return ShortageScore(
        stock_id=stock_id, name=name, total=0.0, tier=tier,
        tier_icon=TIER_ICONS.get(tier, ""),
        c1_contract_liab=0.0, c2_gross_margin=0.0,
        c3_inventory_days=0.0, c4_revenue_yoy=0.0,
        cl_na=False, reasons=[reason], metrics={},
        # DEC-149 Phase 3B：四項都沒評估（輸入錯誤／金融股／季數不足）→ 旗標全 False、n=0
        n_signals_ok=0, c1_ok=False, c2_ok=False, c3_ok=False, c4_ok=False,
        miss_reason=reason,
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
