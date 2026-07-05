"""src/compute/etf/etf_recommendation.py — ETF「留 / 觀察 / 換」建議(L2 純函式,v19.64)。

多檔比較表已算出 綜合分 / 流動性 / 配息健康 / 估值 / σ位階,但 user 反映
「看不出哪些留、哪些賣」。本模組把這些**既有分數**收斂成一句話行動建議,
不重算任何指標,零 I/O,易測。門檻全走 shared/etf_recommendation_thresholds SSOT。

判斷分兩層:
  1. 單檔品質 → 綜合分分級(留 / 觀察 / 換);紅旗(流動性高風險 / 配息吃本金)
     會把「留」降到「觀察」、把「觀察」降到「換」。
  2. 同類重疊 → 同一 ETF 類別持有 ≥2 檔時,提示「留分數最高者,其餘擇一」
     (真正的抗跌分散來自不同資產類別,不是多買幾檔同質高股息)。

§1 寧缺勿假:抓取失敗 / 綜合分缺 → 回「資料不足」,絕不腦補一個建議。
"""
from __future__ import annotations

from shared.etf_recommendation_thresholds import (
    KEEP_COMPOSITE_MIN,
    REDUNDANCY_MIN_PEERS,
    SELL_COMPOSITE_MAX,
    SIGMA_Z_CHEAP,
    SIGMA_Z_RICH,
    VERDICT_ICONS,
    VERDICT_KEEP,
    VERDICT_NA,
    VERDICT_SWITCH,
    VERDICT_WATCH,
)


def _as_float(v):
    """None / 非數字 → None;否則 float。"""
    try:
        if v is None:
            return None
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f


def recommend_etf_action(row: dict) -> dict:
    """單檔 ETF → 建議 dict {verdict, icon, reasons: list[str], red_flags: list[str]}。

    只讀既有欄位(不重算):composite / liquidity_level / dividend_health /
    valuation_zone / sigma_z / error。缺 composite 或 error → 「資料不足」。
    """
    _row = row or {}
    if _row.get('error'):
        return {
            'verdict': VERDICT_NA, 'icon': VERDICT_ICONS[VERDICT_NA],
            'reasons': ['抓取失敗,無法評估'], 'red_flags': [],
        }
    composite = _as_float(_row.get('composite'))
    if composite is None:
        return {
            'verdict': VERDICT_WATCH, 'icon': VERDICT_ICONS[VERDICT_WATCH],
            'reasons': ['缺關鍵指標,綜合分無法計算 —— 先觀察'], 'red_flags': [],
        }

    liquidity = str(_row.get('liquidity_level') or '')
    div_health = str(_row.get('dividend_health') or '')

    # ── 紅旗(force downgrade,不管綜合分多高)──
    red_flags: list[str] = []
    if '🔴' in liquidity:
        red_flags.append('流動性高風險(量小/規模小,不易進出)')
    if '吃本金' in div_health:
        red_flags.append('配息吃本金(含息報酬 < 殖利率)')

    reasons: list[str] = []
    # ── 基準判斷:綜合分分級 ──
    if composite >= KEEP_COMPOSITE_MIN:
        verdict = VERDICT_KEEP
        reasons.append(f'綜合分 {composite:.2f}(≥{KEEP_COMPOSITE_MIN:.2f})體質佳')
    elif composite < SELL_COMPOSITE_MAX:
        verdict = VERDICT_SWITCH
        reasons.append(f'綜合分 {composite:.2f}(<{SELL_COMPOSITE_MAX:.2f})體質偏弱')
    else:
        verdict = VERDICT_WATCH
        reasons.append(f'綜合分 {composite:.2f} 中等')

    # ── 紅旗降級:留→觀察、觀察→換(換維持換)──
    if red_flags:
        if verdict == VERDICT_KEEP:
            verdict = VERDICT_WATCH
        elif verdict == VERDICT_WATCH:
            verdict = VERDICT_SWITCH
        reasons.extend(red_flags)

    # ── 估值/位階註解(只補加碼時機,不改留/換)──
    if verdict in (VERDICT_KEEP, VERDICT_WATCH):
        val = str(_row.get('valuation_zone') or '')
        sigma_z = _as_float(_row.get('sigma_z'))
        _cheap = ('🟢' in val) or (sigma_z is not None and sigma_z <= SIGMA_Z_CHEAP)
        _rich = ('🔴' in val) or (sigma_z is not None and sigma_z >= SIGMA_Z_RICH)
        if _cheap:
            reasons.append('價位偏低,分批加碼時機較佳')
        elif _rich:
            reasons.append('價位偏高,續抱可、暫緩加碼')

    return {
        'verdict': verdict, 'icon': VERDICT_ICONS[verdict],
        'reasons': reasons, 'red_flags': red_flags,
    }


def _detect_redundancy(rows) -> dict:
    """同一 ETF 類別持有 ≥REDUNDANCY_MIN_PEERS 檔 → 標「同類重疊」。

    回傳 {ticker: note}。每類保留綜合分最高者標「同類最優」,其餘標「可擇一」。
    無類別(get_category_name 回 '')或 error 的不參與。
    """
    from src.compute.etf.etf_categories import get_category_name  # noqa: PLC0415
    by_cat: dict[str, list[dict]] = {}
    for r in rows or []:
        if not r or r.get('error'):
            continue
        _cat = get_category_name(r.get('ticker'))
        if not _cat:
            continue
        by_cat.setdefault(_cat, []).append(r)

    notes: dict[str, str] = {}
    for _cat, group in by_cat.items():
        if len(group) < REDUNDANCY_MIN_PEERS:
            continue
        # 綜合分最高者為該類「留」;缺分者排最後。
        _best = max(group, key=lambda r: (_as_float(r.get('composite')) if _as_float(r.get('composite')) is not None else -1.0))
        _best_id = _best.get('ticker')
        for r in group:
            _tk = r.get('ticker')
            if _tk == _best_id:
                notes[_tk] = f'同類「{_cat}」中分數最高,建議留為此類代表'
            else:
                notes[_tk] = f'與 {_best_id} 同屬「{_cat}」,分數較低 → 同類擇一即可'
    return notes


def recommend_etf_actions(rows) -> list[dict]:
    """整批 rows → 與 rows 同序的建議 list(單檔品質 + 同類重疊註解)。

    每個 verdict dict 額外帶:
      'reasons' 併入同類重疊提示、'redundant_note'(有重疊時才有)、
      'reason_text'(reasons 用「;」串好,方便 UI 直接塞欄位)。
    """
    _redundancy = _detect_redundancy(rows)
    out: list[dict] = []
    for r in rows or []:
        v = recommend_etf_action(r)
        _note = _redundancy.get((r or {}).get('ticker'))
        if _note:
            v['redundant_note'] = _note
            v['reasons'] = [*v['reasons'], _note]
        v['reason_text'] = ';'.join(v['reasons'])
        out.append(v)
    return out
