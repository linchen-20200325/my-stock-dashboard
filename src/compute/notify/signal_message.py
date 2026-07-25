"""src/compute/notify/signal_message.py — 每日推播訊息組字(L2 純函式)。

吃選股清單 records(`get_ranked_picks` → df.to_dict）+ 各檔技術快照
(`build_technical_snapshot`)→ 組成 Telegram 純文字訊息。

§1 fail-loud:技術快照缺 / 欄位 None → 顯示「技術資料不足」或略過該欄(**不腦補**);
清單為空 → `format_empty_message` 明講原因,不偽造清單。
§8.2 L2:無 I/O、無 streamlit。趨勢燈號僅反映**客觀 MA 排列事實**,非買賣建議。
"""
from __future__ import annotations

# 選股因子分欄(composite_rank_candidates 顯示欄名);顯示時去尾字「分」
_FACTOR_COLS = ["估值分", "EPS分", "缺貨分", "RS分", "跨季分"]


def _num(x):
    """轉 float(numpy 純量也可);非數值 → None。"""
    try:
        return float(x) if x is not None else None
    except (TypeError, ValueError):
        return None


def _trend_emoji(snap: dict) -> str:
    """趨勢燈號 = 客觀 MA 排列事實(非買賣建議):🟢多頭排列 / 🟡未站上均線 / ⚪資料不足。"""
    if not snap or not snap.get("ok") or snap.get("ma_bull") is None:
        return "⚪"
    return "🟢" if snap.get("ma_bull") else "🟡"


def format_technical_line(snap: dict) -> str:
    """一檔技術快照 → 一行技術面文字(缺料的欄自動略過;全缺 → 「技術資料不足」)。"""
    if not snap or not snap.get("ok"):
        return "技術資料不足"
    parts: list[str] = []
    price = _num(snap.get("price"))
    if price is not None:
        parts.append(f"現價 {price:g}")
    bias = _num(snap.get("bias20_pct"))
    if bias is not None:
        parts.append(f"距MA20 {bias:+.1f}%")
    rsi = _num(snap.get("rsi"))
    if rsi is not None:
        parts.append(f"RSI {rsi:.0f}")
    if snap.get("kd_gold") is not None:
        parts.append("KD偏多" if snap.get("kd_gold") else "KD偏空")
    mh = _num(snap.get("macd_hist"))
    if mh is not None:
        parts.append(f"MACD柱 {mh:+.2f}")
    return " · ".join(parts) if parts else "技術資料不足"


def format_signal_message(picks: list[dict], tech_by_code: dict, *,
                          as_of: str, regime: str | None = None) -> str:
    """選股清單 + 各檔技術快照 → Telegram 純文字訊息。

    Args:
        picks: `get_ranked_picks` 的 df.to_dict('records')(每筆含 代碼/名稱/綜合分/各因子分)。
        tech_by_code: {股號: build_technical_snapshot 輸出}。
        as_of: 資料時間(字串,orchestrator 傳入 TW 時間)。
        regime: 總經 regime(選填,顯示於抬頭)。
    """
    head = f"📊 台股選股訊號 · {as_of}\n綜合分前 {len(picks)} 名"
    if regime:
        head += f" · 總經 {regime}"
    lines: list[str] = [head, ""]
    for _p in picks:
        code = str(_p.get("代碼", "") or "").strip()
        name = str(_p.get("名稱", "") or "").strip()
        snap = tech_by_code.get(code) or {}
        comp = _num(_p.get("綜合分"))
        comp_s = f"{comp:g}" if comp is not None else "—"
        lines.append(f"{_trend_emoji(snap)} {code} {name}  綜合分 {comp_s}")
        _facs = [f"{c[:-1]} {_num(_p.get(c)):g}"
                 for c in _FACTOR_COLS if _num(_p.get(c)) is not None]
        if _facs:
            lines.append("  基本面: " + " · ".join(_facs))
        lines.append("  技術面: " + format_technical_line(snap))
    lines.append("")
    lines.append("⚠️ 清單訊號,非個人化買賣建議;🟢多頭排列 🟡未站上均線 ⚪資料不足。")
    return "\n".join(lines)


def format_empty_message(*, as_of: str, reason: str) -> str:
    """清單為空(季快照未就緒 / 存活池空)→ 明講原因,**不偽造清單**(§1)。"""
    return (f"📊 台股選股訊號 · {as_of}\n\n"
            f"今日無訊號:{reason}\n"
            "(季快照未就緒 / 存活池空時,依 §1 不偽造清單。)")
