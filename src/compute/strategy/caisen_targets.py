"""src/compute/strategy/caisen_targets.py — 蔡森形態學目標價引擎(L2 純函式)。

把「蔡森(阿森)線型形態學」的**目標價 / 甜蜜價 / 止損 / 風報比**做成
**確定性演算法**:輸入 high/low 序列 + 現價 → ZigZag 擺動點 → 機械對映關鍵點 →
等幅滿足量測目標。**演算法推導,非主觀型態判定**。

三段式 pipeline(全純函式,零 I/O — 不 import requests/yfinance/streamlit/proxy):
  1. detect_swings(highs, lows)        — ZigZag 擺動點偵測(確定性反轉≥pct)
  2. derive_caisen_levels(swings, px)  — 從擺動點機械對映蔡森關鍵位
  3. compute_caisen_targets(**levels)  — 等幅滿足量測 → 目標/止損/風報比

§1 Fail Loud / Never Fake:輸入缺值 / 算不出 → 回 None(不腦補假值);
浮點比較用容差(_EPS);除零一律 guard。

單位約定(§4.1):所有 price 參數同幣別同單位(TWD / 點數皆可,只要**全程一致**),
本模組**不做**單位轉換 — 呼叫端須保證 high/low/current_price 同源同單位。
"""
from __future__ import annotations

import math

# 浮點容差(§4.3 禁 ==;除零 / 反轉判定用)
_EPS = 1e-9


def _finite(x) -> bool:
    """x 是否為可用的有限實數(None / NaN / 非數 → False)。"""
    if x is None:
        return False
    try:
        return math.isfinite(float(x))
    except (TypeError, ValueError):
        return False


def _f(x):
    """安全轉 float;失敗回 None(non-fabricating)。"""
    if x is None:
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


# ── 函式 1:ZigZag 擺動點偵測 ────────────────────────────────────────
def detect_swings(highs, lows, *, pct: float = 0.08) -> list[dict]:
    """ZigZag 擺動點偵測(確定性演算法)。

    自上一個確認的轉折(或起點)反轉 **≥ pct**(預設 8%)才確認新轉折;
    high 取自 `highs`、low 取自 `lows`,交替輸出。**只輸出已被 pct 反轉確認**
    的轉折(進行中、尚未反轉 pct 的最末段極值不列入 — 忠於「確認」語意;
    當下極值由 caller 以 `current_price` 另行提供)。

    Args:
        highs: 高價序列(list[float] 或 pd.Series)。
        lows:  低價序列(list[float] 或 pd.Series),需與 highs 同索引對齊。
        pct:   反轉確認門檻(小數,0.08 = 8%)。

    Returns:
        list[dict]:`[{"idx": int, "price": float, "kind": "high"|"low"}, ...]`
        依 idx 遞增、kind 交替。序列 < 3 或有效點 < 3 → `[]`。

    NaN / None:該索引任一(high 或 low)非有限 → 整根跳過(不 ffill、不腦補)。
    """
    H = list(highs)
    L = list(lows)
    n = min(len(H), len(L))
    if n < 3:
        return []

    # 有效索引:high 與 low 皆為有限實數才納入(NaN 跳過,§1 不填補)
    valid = [i for i in range(n) if _finite(H[i]) and _finite(L[i])]
    if len(valid) < 3:
        return []

    up_thr = 1.0 + pct   # 由低點反轉向上的確認乘數
    dn_thr = 1.0 - pct   # 由高點反轉向下的確認乘數

    pivots: list[dict] = []
    i0 = valid[0]
    hi_idx, hi_val = i0, float(H[i0])   # 目前上行段的候選高點
    lo_idx, lo_val = i0, float(L[i0])   # 目前下行段的候選低點
    trend = 0                            # 0=未定 / 1=上行(找高) / -1=下行(找低)

    for i in valid[1:]:
        h = float(H[i])
        l = float(L[i])

        if trend == 0:
            # 方向未定:同時追蹤自起點的最高高 / 最低低,先達 pct 者定方向
            if h > hi_val:
                hi_idx, hi_val = i, h
            if l < lo_val:
                lo_idx, lo_val = i, l
            if l <= hi_val * dn_thr:
                # 先向上抬到 hi 再回落 pct → 起點高點確認,轉下行找低
                pivots.append({"idx": hi_idx, "price": hi_val, "kind": "high"})
                trend = -1
                lo_idx, lo_val = i, l
            elif h >= lo_val * up_thr:
                # 先向下探到 lo 再彈升 pct → 起點低點確認,轉上行找高
                pivots.append({"idx": lo_idx, "price": lo_val, "kind": "low"})
                trend = 1
                hi_idx, hi_val = i, h

        elif trend == 1:
            # 上行段:延伸更高高;回落 pct → 確認高點,轉下行
            if h > hi_val:
                hi_idx, hi_val = i, h
            if l <= hi_val * dn_thr:
                pivots.append({"idx": hi_idx, "price": hi_val, "kind": "high"})
                trend = -1
                lo_idx, lo_val = i, l

        else:  # trend == -1
            # 下行段:延伸更低低;彈升 pct → 確認低點,轉上行
            if l < lo_val:
                lo_idx, lo_val = i, l
            if h >= lo_val * up_thr:
                pivots.append({"idx": lo_idx, "price": lo_val, "kind": "low"})
                trend = 1
                hi_idx, hi_val = i, h

    return pivots


# ── 函式 2:機械對映蔡森關鍵位 ──────────────────────────────────────
def derive_caisen_levels(swings, current_price) -> dict | None:
    """從擺動點 + 現價,機械對映蔡森關鍵點(演算法推導,非型態判定)。

    以「最近一個顯著擺動高」為錨(壓力 / 頸線 / 第一波高),往前找起漲低、
    往後找整理低,並以整體最低低作為破底參考。

    Args:
        swings: detect_swings 的輸出(或等結構 list[dict])。
        current_price: 現價(float)。

    Returns:
        dict 含所有 key:
          wave1_high / neckline   最近顯著擺動高(壓力 / 頸線)
          wave1_start             該高之前最近的擺動低(第一波起漲)
          consolidation_low       該高之後的擺動低(整理拉回低;無 → None)
          breakdown_low           所有擺動低中的最低(甩轎破底低)
          support / prior_low     更早的擺動低(前低 / 支撐)
          pattern                 '破底翻' / 'N字整理' / '型態未明'
          current_price           原樣帶回
        swings 不足(空 / <2 / 無擺動高)→ 回 None。
    """
    if not swings or len(swings) < 2:
        return None

    highs = sorted((s for s in swings if s.get("kind") == "high"),
                   key=lambda s: s["idx"])
    lows = sorted((s for s in swings if s.get("kind") == "low"),
                  key=lambda s: s["idx"])
    if not highs:
        return None

    px = _f(current_price)

    # 最近顯著擺動高 = 錨
    wave1 = highs[-1]
    wave1_high = _f(wave1["price"])
    neckline = wave1_high
    anchor_idx = wave1["idx"]

    # 第一波起漲低 = 錨之前最近的擺動低
    prior_to_anchor = [s for s in lows if s["idx"] < anchor_idx]
    wave1_start = _f(prior_to_anchor[-1]["price"]) if prior_to_anchor else None
    wave1_start_idx = prior_to_anchor[-1]["idx"] if prior_to_anchor else None

    # 整理拉回低 = 錨之後最早的擺動低(尚未出現 → None,§4.6 三態)
    after_anchor = [s for s in lows if s["idx"] > anchor_idx]
    consolidation_low = _f(after_anchor[0]["price"]) if after_anchor else None

    # 破底低 = 所有擺動低中的最低(甩轎破底)
    breakdown_low = None
    if lows:
        _low_prices = [_f(s["price"]) for s in lows]
        _low_prices = [p for p in _low_prices if p is not None]
        breakdown_low = min(_low_prices) if _low_prices else None

    # 前低 / 支撐 = 比第一波起漲更早的擺動低(無則退回起漲低本身)
    older = [s for s in lows
             if wave1_start_idx is not None and s["idx"] < wave1_start_idx]
    if older:
        support = _f(older[-1]["price"])
    else:
        support = wave1_start
    prior_low = support

    # 型態判定(規則序:破底翻 > N字整理 > 型態未明)
    broke_below = (breakdown_low is not None and support is not None
                   and breakdown_low < support - _EPS)
    stood_back = (px is not None and support is not None
                  and px > support + _EPS)
    if broke_below and stood_back:
        pattern = "破底翻"
    elif consolidation_low is not None:
        pattern = "N字整理"
    else:
        pattern = "型態未明"

    return {
        "wave1_high": wave1_high,
        "neckline": neckline,
        "wave1_start": wave1_start,
        "consolidation_low": consolidation_low,
        "breakdown_low": breakdown_low,
        "support": support,
        "prior_low": prior_low,
        "pattern": pattern,
        "current_price": px,
    }


# ── 函式 3:等幅滿足量測 → 目標 / 止損 / 風報比 ──────────────────────
def compute_caisen_targets(
    *,
    pattern,
    support,
    breakdown_low,
    wave1_start,
    wave1_high,
    consolidation_low,
    neckline,
    current_price,
    buffer_pct: float = 0.01,
) -> dict:
    """確定性計算甜蜜價 / 止損 / 目標 / 風報比(缺值回 None,不腦補)。

    公式:
      甜蜜價 sweet   = neckline(突破買點);sweet_low=(consolidation_low 或 support)、
                       sweet_high=neckline。
      止損 stop      = 破底翻 → breakdown_low*(1-buffer_pct);
                       其他(突破 / N字) → min(consolidation_low, neckline)*(1-buffer_pct)
                       (None 值跳過,取可用者)。
      目標(等幅滿足):
        target_n  (N字第一波)  = consolidation_low + (wave1_high - wave1_start)  [需 consolidation_low]
        target_box(底型第一波) = neckline + (wave1_high - box_low),box_low=(breakdown_low 或 support)
        target2   (第二波)     = neckline + 2*(wave1_high - box_low)
        target1               = N字優先(target_n 有就用),否則 target_box。
      風報比 rr = (target1 - sweet) / (sweet - stop);分母 ≤ 0 或缺值 → None。

    Returns:
        dict:sweet / sweet_low / sweet_high / stop / target_n / target_box /
        target2 / target1 / rr / pattern / notes(list[str] 記錄用了哪條公式、缺哪些值)。
    """
    notes: list[str] = []

    _support = _f(support)
    _breakdown = _f(breakdown_low)
    _w1_start = _f(wave1_start)
    _w1_high = _f(wave1_high)
    _consol = _f(consolidation_low)
    _neck = _f(neckline)
    _px = _f(current_price)

    # ── 甜蜜價 ──
    sweet = _neck  # 代表值 = 頸線突破買點
    sweet_high = _neck
    if _consol is not None:
        sweet_low = _consol
    else:
        sweet_low = _support
    if sweet is None:
        notes.append("甜蜜價缺 neckline → sweet=None")
    else:
        notes.append(f"甜蜜價=頸線突破買點 sweet={sweet:g}")
    if _consol is None and _support is not None:
        notes.append("sweet_low 無整理低 → 退回 support")

    # ── 止損 ──
    stop = None
    if pattern == "破底翻":
        if _breakdown is not None:
            stop = _breakdown * (1.0 - buffer_pct)
            notes.append(f"止損(破底翻)=breakdown_low*(1-{buffer_pct:g})={stop:g}")
        else:
            notes.append("止損(破底翻)缺 breakdown_low → stop=None")
    else:
        _base_cands = [v for v in (_consol, _neck) if v is not None]
        if _base_cands:
            _base = min(_base_cands)
            stop = _base * (1.0 - buffer_pct)
            notes.append(
                f"止損(突破/N字)=min(consolidation_low,neckline)*(1-{buffer_pct:g})={stop:g}"
            )
        else:
            notes.append("止損(突破/N字)缺 consolidation_low 與 neckline → stop=None")

    # ── 目標:N字第一波(等幅滿足) ──
    if _consol is not None and _w1_high is not None and _w1_start is not None:
        target_n = _consol + (_w1_high - _w1_start)
        notes.append(
            f"target_n(N字等幅)=consolidation_low+(wave1_high-wave1_start)={target_n:g}"
        )
    else:
        target_n = None
        _miss = [k for k, v in (("consolidation_low", _consol),
                                ("wave1_high", _w1_high),
                                ("wave1_start", _w1_start)) if v is None]
        notes.append(f"target_n=None(缺 {', '.join(_miss)})")

    # ── 目標:底型第一波 / 第二波 ──
    box_low = _breakdown if _breakdown is not None else _support
    if _neck is not None and _w1_high is not None and box_low is not None:
        _amp = _w1_high - box_low
        target_box = _neck + _amp
        target2 = _neck + 2.0 * _amp
        notes.append(
            f"target_box(底型等幅)=neckline+(wave1_high-box_low[{box_low:g}])={target_box:g};"
            f"target2=neckline+2*幅={target2:g}"
        )
    else:
        target_box = None
        target2 = None
        _miss = [k for k, v in (("neckline", _neck),
                                ("wave1_high", _w1_high),
                                ("box_low", box_low)) if v is None]
        notes.append(f"target_box/target2=None(缺 {', '.join(_miss)})")

    # ── target1:N字優先 ──
    if target_n is not None:
        target1 = target_n
        notes.append("target1←target_n(N字優先)")
    elif target_box is not None:
        target1 = target_box
        notes.append("target1←target_box(無 N字,採底型)")
    else:
        target1 = None
        notes.append("target1=None(N字與底型皆算不出)")

    # ── 風報比 rr ──
    rr = None
    if target1 is not None and sweet is not None and stop is not None:
        denom = sweet - stop
        if denom > _EPS:
            rr = (target1 - sweet) / denom
            notes.append(f"rr=(target1-sweet)/(sweet-stop)={rr:.3f}")
        else:
            notes.append("rr=None(分母 sweet-stop ≤ 0)")
    else:
        _miss = [k for k, v in (("target1", target1), ("sweet", sweet),
                                ("stop", stop)) if v is None]
        notes.append(f"rr=None(缺 {', '.join(_miss)})")

    return {
        "sweet": sweet,
        "sweet_low": sweet_low,
        "sweet_high": sweet_high,
        "stop": stop,
        "target_n": target_n,
        "target_box": target_box,
        "target2": target2,
        "target1": target1,
        "rr": rr,
        "pattern": pattern,
        "notes": notes,
    }


# ── 函式 4:批次摘要(組合 Tab 用,一次跑三段 + 誠實 gate)────────────────
def summarize_caisen(highs, lows, current_price, *, pct: float = 0.08) -> dict:
    """單檔蔡森批次摘要 — 給「個股組合」批次表用的精選欄位 + §1 誠實 gate。

    一次跑完 detect_swings → derive_caisen_levels → compute_caisen_targets,只回
    對操盤最可操作的幾個數字,並套兩條誠實規則(§1 Fail Loud / Never Fake):

    1. **擺動點不足**(levels is None):`pattern=None`、全數 None、`reason="擺動點不足"`。
    2. **型態未明 gate**:此型態下 `consolidation_low is None`,引擎止損退化成
       `neckline×(1-buffer)`(貼最近擺動高下緣),分母 `sweet-stop` 極小 → `rr` 會被
       灌成「假高風報比」誤導進場。故**封鎖** sweet/dist/stop/target1/rr(全 None),
       只保留 `pattern="型態未明"` + `reason`,交由使用者看圖(下鑽)判斷。破底翻 / N字
       的止損有真實整理低 / 破底低支撐,數字健全,照常回傳。

    另加 `dist_pct`(距甜蜜價%)= (現價 − 甜蜜價)/甜蜜價 × 100 —— 負=待突破、
    正=甜蜜價已過期(現價已站上頸線)。比絕對甜蜜價更可操作。

    Args:
        highs / lows: 高 / 低價序列(與 detect_swings 同,list 或 pd.Series)。
        current_price: 現價(float)。
        pct: ZigZag 反轉門檻(小數,預設 0.08)。

    Returns:
        dict:pattern / sweet / dist_pct / stop / target1 / rr / levels / ok / reason。
        `levels` = derive_caisen_levels 原始輸出(供下鑽 seed 每個關鍵點);
        `ok` = bool(型態明確且 rr 算得出,可直接列入可操作候選);
        `reason` = None(正常)或原因字串(擺動點不足 / 型態未明·需看圖)。
    """
    out: dict = {
        "pattern": None, "sweet": None, "dist_pct": None, "stop": None,
        "target1": None, "rr": None, "levels": None, "ok": False, "reason": None,
    }
    px = _f(current_price)
    swings = detect_swings(highs, lows, pct=pct)
    levels = derive_caisen_levels(swings, px)
    if not levels:
        out["reason"] = "擺動點不足"
        return out

    out["levels"] = levels
    pattern = levels.get("pattern")
    out["pattern"] = pattern

    # 型態未明:引擎止損退化 → rr 假高,封鎖可操作數字(§1 不誤導)
    if pattern == "型態未明":
        out["reason"] = "型態未明·需看圖"
        return out

    r = compute_caisen_targets(
        pattern=pattern,
        support=levels.get("support"),
        breakdown_low=levels.get("breakdown_low"),
        wave1_start=levels.get("wave1_start"),
        wave1_high=levels.get("wave1_high"),
        consolidation_low=levels.get("consolidation_low"),
        neckline=levels.get("neckline"),
        current_price=px,
    )
    sweet = r.get("sweet")
    out["sweet"] = sweet
    out["stop"] = r.get("stop")
    out["target1"] = r.get("target1")
    out["rr"] = r.get("rr")
    if sweet is not None and px is not None and abs(sweet) > _EPS:
        out["dist_pct"] = (px - sweet) / sweet * 100.0
    out["ok"] = out["rr"] is not None
    return out
