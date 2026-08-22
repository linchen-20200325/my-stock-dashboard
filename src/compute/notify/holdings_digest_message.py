"""L2 Compute — 每日「持股續抱 / 換股」推播訊息格式化（純函式）。

`build_station_digest`（規則式事實）+ `build_switch_advice`（換出/換入/攻守）→ 一則
LINE 可讀文字。這是每日推播的**可靠主體**（不需 AI 也成立;AI 潤稿由腳本另外附加）。

§8.2 L2:純字串,無 I/O、無 streamlit。
§1 Fail-Loud / 反捏造:所有代號 / 數字**只**來自 digest / switch,不重抓、不推估。
  缺資料的區段誠實標「無」或整段略過,不硬湊;抓取失敗的檔明列為「未納入」而非當作無事。
"""
from __future__ import annotations

from shared import dividend_station_thresholds as T

_DISCLAIMER = "　研究參考,非投資建議。"


def _num(x) -> "float | None":
    return x if isinstance(x, (int, float)) else None


def _macro_line(switch: "dict | None") -> str:
    """總經位階一行（未評估時誠實標,不瞎給攻守）。"""
    if not switch or not switch.get("loaded"):
        return "🧭 總經位階：未評估（僅依個股健檢汰弱,不套攻守）"
    _regime = switch.get("regime") or "unknown"
    _posture = switch.get("posture") or "—"
    _rng = switch.get("posture_range")
    _tail = f"｜建議持股 {_rng}" if _rng else ""
    return f"🧭 總經位階：{_regime}｜{_posture}{_tail}"


def _switch_out_lines(digest: dict, switch: "dict | None") -> list[str]:
    """建議換出（持有紅燈汰弱）。優先用 switch.switch_out（held-only,語意正確:只換你持有的）;
    switch 缺（極少數 build 失敗）才退 digest.reds,並誠實標「含觀察清單」以免暗示賣掉未持有標的。"""
    if switch is not None:
        _outs = switch.get("switch_out") or []
        _caveat = ""
    else:
        _outs = digest.get("reds") or []
        _caveat = "（含觀察清單紅燈）"
    if not _outs:
        return ["🔴 建議換出（持有紅燈汰弱）", "　✅ 無紅燈,續抱"]
    _lines = [f"🔴 建議換出（持有紅燈汰弱）{_caveat}"]
    for d in _outs:
        _act = str(d.get("建議動作", "") or "").strip()
        _lines.append(f"　・{d.get('代號', '')}" + (f"（{_act}）" if _act else ""))
    return _lines


def _switch_in_lines(switch: "dict | None") -> list[str]:
    """建議換入候選（來源:你的觀察清單綠燈 優先,否則選股池排名）。空 → 整段略過。"""
    if not switch:
        return []
    _ins = switch.get("switch_in") or []
    if not _ins:
        return []
    _src = "你的觀察清單" if switch.get("switch_in_src") == "watchlist" else "選股池排名"
    _lines = [f"🟢 建議換入（來源：{_src}）"]
    for c in _ins:
        _nm = str(c.get("名稱", "") or "").strip()
        _score = _num(c.get("綜合分"))
        _tail = f"（綜合分 {_score:.0f}）" if _score is not None else ""
        _lines.append(f"　・{c.get('代號', '')} {_nm}".rstrip() + _tail)
    return _lines


def _adds_lines(digest: dict) -> list[str]:
    """235 逢低加碼觸發。空 → 略過。"""
    _adds = digest.get("adds") or []
    if not _adds:
        return []
    _lines = ["➕ 235 逢低加碼觸發"]
    for d in _adds:
        _lines.append(f"　・{d.get('代號', '')} {d.get('235', '')}"
                      f" 加碼{d.get('加碼金', '')}".rstrip())
    return _lines


def _take_profit_lines(digest: dict) -> list[str]:
    """衛星達停利門檻（§3.3 門檻走 SSOT,不硬寫 15）。空 → 略過。"""
    _tp = digest.get("take_profit") or []
    if not _tp:
        return []
    _lines = [f"💰 衛星達停利門檻（≥{T.SATELLITE_TAKE_PROFIT_PCT:.0f}%,建議滾回核心）"]
    for d in _tp:
        _pnl = _num(d.get("損益%"))
        _lines.append(f"　・{d.get('代號', '')}"
                      + (f"（+{_pnl:.0f}%）" if _pnl is not None else ""))
    return _lines


def _allocation_line(digest: dict) -> list[str]:
    """80/20 實際配置偏離。缺（無張數/均價）→ 略過（§1 不捏造）。"""
    _a = digest.get("allocation")
    if not _a:
        return []
    _partial = "（部分持股缺金額,僅供參考）" if _a.get("partial") else ""
    return [f"⚖️ 配置：核心 {_a['core_pct']:.0f}% / 衛星 {_a['sat_pct']:.0f}%"
            f"（目標 {_a['core_target']:.0f}/{_a['sat_target']:.0f},"
            f"核心偏離 {_a['core_dev']:+.0f}%）{_partial}"]


def _errors_line(digest: dict) -> list[str]:
    """抓取失敗未納入判斷的檔（§1 誠實排除,不當作無事）。空 → 略過。"""
    _errs = digest.get("errors") or []
    if not _errs:
        return []
    return [f"⚠️ {len(_errs)} 檔抓取失敗未納入：" + "、".join(str(e) for e in _errs)]


def format_holdings_message(digest: dict, switch: "dict | None" = None, *,
                            as_of: str) -> str:
    """digest(+switch) → 每日持股續抱/換股 LINE 訊息（純函式,§1 數字全來自上游）。

    區段:標題 → 位階 → VIX → 換出 → 換入 → 235 加碼 → 衛星停利 → 配置 → 抓取失敗 → 免責。
    「今日無需動作」判定:無換出、無加碼、無停利 → 明講續抱（對齊 build_summary_prompt 語氣）。
    """
    digest = digest or {}
    _vix = _num(digest.get("vix"))
    _vix_txt = f"{_vix:.1f}" if _vix is not None else "抓取失敗"
    _total = int(digest.get("total", 0) or 0)

    lines: list[str] = [
        "💼 持股戰情室｜每日續抱 / 換股",
        f"🕐 {as_of}（收盤後檢視,價格以最近交易日為準）",
        _macro_line(switch),
        f"😱 VIX：{_vix_txt}　有效判斷 {_total} 檔",
        "",
    ]
    lines += _switch_out_lines(digest, switch)
    _in = _switch_in_lines(switch)
    if _in:
        lines += [""] + _in
    for _seg in (_adds_lines(digest), _take_profit_lines(digest),
                 _allocation_line(digest), _errors_line(digest)):
        if _seg:
            lines += [""] + _seg

    # 「今日無需動作」:無換出（held 紅燈）、無 235 加碼、無停利 → 明講續抱（§1 不含糊）。
    _switch_out = (switch or {}).get("switch_out") if switch is not None else digest.get("reds")
    _no_action = (not (_switch_out or [])
                  and not (digest.get("adds") or [])
                  and not (digest.get("take_profit") or []))
    if _no_action:
        lines += ["", "📭 今日無需動作：續抱、定期定額即可。"]

    lines += ["", _DISCLAIMER]
    return "\n".join(lines)
