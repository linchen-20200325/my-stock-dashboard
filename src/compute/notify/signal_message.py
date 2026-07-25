"""src/compute/notify/signal_message.py — 每日推播訊息組字(L2 純函式)。

吃選股清單 records(`get_ranked_picks` → df.to_dict）+ 各檔技術快照
(`build_technical_snapshot`)→ 組成手機推播純文字訊息。

精簡原則(v20-PUSH.1,user「數字太多」）:每檔只出「趨勢燈 + 代碼名稱 + 綜合分」
一行 + 「現價 / 距月線 / RSI / KD 方向」一行。基本面 5 項內部分數(綜合分已代表)、
MACD 柱狀原始值(隨股價尺度亂跳、不可跨股比較)不列。

§1 fail-loud:技術快照缺 / 欄位 None/NaN → 顯示「技術資料不足」或略過該欄(**不腦補、
不印 nan**);清單為空 → `format_empty_message` 明講原因,不偽造清單。
§8.2 L2:無 I/O、無 streamlit。趨勢燈號僅反映**客觀 MA 排列事實**,非買賣建議。
"""
from __future__ import annotations

import math


def _num(x):
    """轉 float(numpy 純量也可);None / NaN / 非數值 → None。

    v20-PUSH.1 修:pandas 把缺料因子存成 NaN(非 None),`float(nan)` 會騙過 `is not None`
    印出「nan」→ 顯式擋掉,§1 缺料不顯示、不腦補、不印 nan。
    """
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


def format_technical_line(snap: dict) -> str:
    """一檔技術快照 → 一行技術面文字(缺料的欄自動略過;全缺 → 「技術資料不足」)。

    只留 4 個可跨股比較、好讀的訊號:現價 / 距月線% / RSI / KD 方向。
    """
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
                          as_of: str, regime: str | None = None) -> str:
    """選股清單 + 各檔技術快照 → 手機推播純文字(每檔 2 行,精簡)。

    Args:
        picks: `get_ranked_picks` 的 df.to_dict('records')(每筆含 代碼/名稱/綜合分)。
        tech_by_code: {股號: build_technical_snapshot 輸出}。
        as_of: 資料時間(字串,orchestrator 傳入 TW 時間)。
        regime: 總經 regime(選填,顯示於抬頭)。
    """
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
        _title = f"{_trend_emoji(snap)} {code} {name}".rstrip()   # 無中文名時不留尾空格
        lines.append(f"{_title}  綜合分 {comp_s}")
        lines.append("  " + format_technical_line(snap))
    lines.append("")
    lines.append("⚠️ 清單訊號,非買賣建議;🟢多頭排列 🟡未站上均線 ⚪資料不足。")
    return "\n".join(lines)


def format_empty_message(*, as_of: str, reason: str) -> str:
    """清單為空(季快照未就緒 / 存活池空)→ 明講原因,**不偽造清單**(§1)。"""
    return (f"📊 台股選股訊號 · {as_of}\n\n"
            f"今日無訊號:{reason}\n"
            "(季快照未就緒 / 存活池空時,依 §1 不偽造清單。)")
