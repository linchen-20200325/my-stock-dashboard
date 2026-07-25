"""src/compute/notify/signal_message.py — 每日推播訊息組字(L2 純函式)。

吃選股清單 records(`get_ranked_picks` → df.to_dict）+ 各檔技術快照
(`build_technical_snapshot`)+ 跨季財報趨勢(`cross_quarter_trends`)+ 缺貨 tier
→ 組成手機推播純文字訊息(每檔 2 行)。

版面(v20-PUSH.2,user 選「趨勢併入兩行」):
  行1  {趨勢燈} {代碼} {名稱}  {綜合分} {📈財報變好/➡️持平/📉轉弱}
  行2  {現價}元 · 距月線% · RSI · KD方向 · {缺貨強/中/弱}

§1 fail-loud:缺料(技術/趨勢/缺貨任一)→ 略過該徽章 / 顯示「技術資料不足」(**不腦補、
不印 nan**);清單為空 → `format_empty_message` 明講原因,不偽造清單。
§8.2 L2:無 I/O、無 streamlit。趨勢燈與徽章僅反映**客觀計算事實**,非買賣建議。
"""
from __future__ import annotations

import math

from shared.shortage_screen_thresholds import TIER_MID, TIER_STRONG, TIER_WEAK

# 財報趨勢門檻:近 5 季 favorable_count / favorable_of 比例(§3.3 命名常數,非 inline magic)。
# favorable = 毛利率↑ / 營益率↑ / 負債比↓ / 營收YoY↑ 中「方向為佳」的個數。
_FUND_TREND_GOOD_RATIO = 0.75    # ≥ → 📈財報變好
_FUND_TREND_WEAK_RATIO = 0.25    # ≤ → 📉財報轉弱

# 缺貨 tier → 徽章(SSOT:tier 字串來自 shared.shortage_screen_thresholds;資料不足/不適用 → 略)
_SHORTAGE_LABEL = {TIER_STRONG: "缺貨強", TIER_MID: "缺貨中", TIER_WEAK: "缺貨弱"}


def _num(x):
    """轉 float(numpy 純量也可);None / NaN / 非數值 → None(§1 缺料不顯示、不印 nan)。"""
    try:
        _v = float(x)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(_v) else _v


def _trend_emoji(snap: dict) -> str:
    """趨勢燈號 = 客觀 MA 排列事實(非買賣建議):🟢多頭排列 / 🟡未站上均線 / ⚪資料不足。"""
    if not snap or not snap.get("ok") or snap.get("ma_bull") is None:
        return "⚪"
    return "🟢" if snap.get("ma_bull") else "🟡"


def format_fundamental_trend(trend: dict | None) -> str:
    """跨季趨勢一列 → 財報趨勢徽章。

    近 5 季有資料的因子中「方向為佳」比例 ≥0.75 → 📈財報變好、≤0.25 → 📉財報轉弱、
    其餘 → ➡️財報持平。無資料(favorable_of≤0)→ ''(§1 不臆造)。
    """
    if not trend:
        return ""
    _of = _num(trend.get("favorable_of"))
    _cnt = _num(trend.get("favorable_count"))
    if not _of or _cnt is None or _of <= 0:
        return ""
    _ratio = _cnt / _of
    if _ratio >= _FUND_TREND_GOOD_RATIO:
        return "📈財報變好"
    if _ratio <= _FUND_TREND_WEAK_RATIO:
        return "📉財報轉弱"
    return "➡️財報持平"


def format_shortage_badge(tier) -> str:
    """缺貨 tier(強缺貨/中度/不明顯…)→ 徽章(缺貨強/中/弱);資料不足/不適用/缺 → ''。"""
    return _SHORTAGE_LABEL.get(str(tier).strip(), "") if tier else ""


def format_technical_line(snap: dict) -> str:
    """一檔技術快照 → 一行技術面文字(缺料的欄自動略過;全缺 → 「技術資料不足」)。"""
    if not snap or not snap.get("ok"):
        return "技術資料不足"
    parts: list[str] = []
    price = _num(snap.get("price"))
    if price is not None:
        parts.append(f"{price:g}元")
    bias = _num(snap.get("bias20_pct"))
    if bias is not None:
        parts.append(f"距月線 {bias:+.1f}%")
    rsi = _num(snap.get("rsi"))
    if rsi is not None:
        parts.append(f"RSI {rsi:.0f}")
    if snap.get("kd_gold") is not None:
        parts.append("KD偏多" if snap.get("kd_gold") else "KD偏空")
    return " · ".join(parts) if parts else "技術資料不足"


def format_signal_message(picks: list[dict], tech_by_code: dict, *,
                          as_of: str, regime: str | None = None,
                          trend_by_code: dict | None = None,
                          shortage_by_code: dict | None = None) -> str:
    """選股清單 + 技術快照 + 財報趨勢 + 缺貨 tier → 手機推播純文字(每檔 2 行)。

    Args:
        picks: `get_ranked_picks` 的 df.to_dict('records')(每筆含 代碼/名稱/綜合分)。
        tech_by_code: {股號: build_technical_snapshot 輸出}。
        trend_by_code: {股號: cross_quarter_trends 一列 dict}(選填;無 → 不顯示財報趨勢)。
        shortage_by_code: {股號: 缺貨 tier 字串}(選填;無 → 不顯示缺貨)。
        as_of: 資料時間(字串,orchestrator 傳入 TW 時間)。
        regime: 總經 regime(選填,顯示於抬頭)。
    """
    trend_by_code = trend_by_code or {}
    shortage_by_code = shortage_by_code or {}
    head = f"📊 台股選股訊號 · {as_of} · 前 {len(picks)} 名"
    if regime:
        head += f" · 總經 {regime}"
    lines: list[str] = [head, ""]
    for _p in picks:
        code = str(_p.get("代碼", "") or "").strip()
        name = str(_p.get("名稱", "") or "").strip()
        snap = tech_by_code.get(code) or {}
        comp = _num(_p.get("綜合分"))
        comp_s = f"{comp:g}" if comp is not None else "—"
        # 行1:趨勢燈 + 代碼名稱 + 綜合分 + 財報趨勢徽章
        _title = f"{_trend_emoji(snap)} {code} {name}".rstrip()   # 無中文名時不留尾空格
        _fund = format_fundamental_trend(trend_by_code.get(code))
        lines.append(f"{_title}  綜合分 {comp_s}" + (f" {_fund}" if _fund else ""))
        # 行2:技術面 + 缺貨徽章
        _tech = format_technical_line(snap)
        _short = format_shortage_badge(shortage_by_code.get(code))
        lines.append("  " + (f"{_tech} · {_short}" if _short else _tech))
    lines.append("")
    lines.append("⚠️ 清單訊號,非買賣建議;🟢多頭排列 🟡未站上均線 ⚪資料不足。")
    return "\n".join(lines)


def format_empty_message(*, as_of: str, reason: str) -> str:
    """清單為空(季快照未就緒 / 存活池空)→ 明講原因,**不偽造清單**(§1)。"""
    return (f"📊 台股選股訊號 · {as_of}\n\n"
            f"今日無訊號:{reason}\n"
            "(季快照未就緒 / 存活池空時,依 §1 不偽造清單。)")
