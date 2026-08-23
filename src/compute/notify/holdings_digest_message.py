"""L2 Compute — 每日「持股續抱 / 換股」推播訊息格式化（純函式）。

`build_station_digest`（規則式事實）+ `build_switch_advice`（換出/換入/攻守）→ 一則
LINE 可讀文字。這是每日推播的**可靠主體**（不需 AI 也成立;AI 潤稿由腳本另外附加）。

§8.2 L2:純字串,無 I/O、無 streamlit。
§1 Fail-Loud / 反捏造:所有代號 / 數字**只**來自 digest / switch,不重抓、不推估。
  缺資料的區段誠實標「無」或整段略過,不硬湊;抓取失敗的檔明列為「未納入」而非當作無事。
"""
from __future__ import annotations

import numbers

from shared import dividend_station_thresholds as T

_DISCLAIMER = "　研究參考,非投資建議。"


def _num(x) -> "float | None":
    # numbers.Real 涵蓋 np.int64 / np.float64（pandas 衍生值）;排除 bool（True/False 不是數字）。
    return x if isinstance(x, numbers.Real) and not isinstance(x, bool) else None


def _code(d: dict, key: str = "代號") -> str:
    """安全取代號/字串欄:`.get(k,'')` 只在 key 缺席時給預設,present-but-None 仍會印字面
    "None" → 一律 `str(... or '')`（§1/§3.3 不印 None、不捏造）。"""
    return str(d.get(key) or "")


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
        _lines.append(f"　・{_code(d)}" + (f"（{_act}）" if _act else ""))
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
        _lines.append(f"　・{_code(c)} {_nm}".rstrip() + _tail)
    return _lines


def _picks_lines(picks) -> list[str]:
    """今日選股 Top N（換股池,已排除持股 → 全是「可換入」標的）。空/None → 略過。

    picks 來源 = get_switch_in_candidates（同一次 get_ranked_picks,不重抓),鍵為 代碼/名稱/綜合分。
    這段把「每日選股清單」併進持股推:換出的持股從這個池 + 觀察清單🟢 挑換入(§ user 2026-08-23)。
    ⚠️ 「已排除持股」由 caller 保證（picks 傳自 get_switch_in_candidates(exclude=held)）,
    本純函式不自行過濾;若他處重用本函式且未先排除持股,header 措辭需相應調整。
    """
    if not picks:
        return []
    _lines = [f"📈 今日選股 Top{len(picks)}（換股池·已排除持股）"]
    for _i, c in enumerate(picks, 1):
        _nm = str(c.get("名稱", "") or "").strip()
        _score = _num(c.get("綜合分"))
        _tail = f"（綜合分 {_score:.0f}）" if _score is not None else ""
        _lines.append(f"　{_i}. {_code(c, '代碼')} {_nm}".rstrip() + _tail)
    return _lines


def _adds_lines(digest: dict) -> list[str]:
    """235 逢低加碼觸發。空 → 略過。"""
    _adds = digest.get("adds") or []
    if not _adds:
        return []
    _lines = ["➕ 235 逢低加碼觸發"]
    for d in _adds:
        _lines.append(f"　・{_code(d)} {_code(d, '235')}"
                      f" 加碼{_code(d, '加碼金')}".rstrip())
    return _lines


def _take_profit_lines(digest: dict) -> list[str]:
    """衛星達停利門檻（§3.3 門檻走 SSOT,不硬寫 15）。空 → 略過。"""
    _tp = digest.get("take_profit") or []
    if not _tp:
        return []
    _lines = [f"💰 衛星達停利門檻（≥{T.SATELLITE_TAKE_PROFIT_PCT:.0f}%,建議滾回核心）"]
    for d in _tp:
        _pnl = _num(d.get("損益%"))
        _lines.append(f"　・{_code(d)}"
                      + (f"（+{_pnl:.0f}%）" if _pnl is not None else ""))
    return _lines


def _allocation_line(digest: dict) -> list[str]:
    """80/20 實際配置偏離。缺（無張數/均價 → allocation=None,或上游契約漂移缺鍵）→ 略過
    （§1 不捏造;不因單一區段缺鍵而 KeyError 炸掉整則推播,與其他區段一致走 .get + _num）。"""
    _a = digest.get("allocation")
    if not _a:
        return []
    _core, _sat = _num(_a.get("core_pct")), _num(_a.get("sat_pct"))
    _ct, _st, _dev = _num(_a.get("core_target")), _num(_a.get("sat_target")), _num(_a.get("core_dev"))
    if None in (_core, _sat, _ct, _st, _dev):
        return []
    _partial = "（部分持股缺金額,僅供參考）" if _a.get("partial") else ""
    return [f"⚖️ 配置：核心 {_core:.0f}% / 衛星 {_sat:.0f}%"
            f"（目標 {_ct:.0f}/{_st:.0f},核心偏離 {_dev:+.0f}%）{_partial}"]


def _errors_line(digest: dict) -> list[str]:
    """抓取失敗未納入判斷的檔（§1 誠實排除,不當作無事）。空 → 略過。"""
    _errs = digest.get("errors") or []
    if not _errs:
        return []
    return [f"⚠️ {len(_errs)} 檔抓取失敗未納入：" + "、".join(str(e) for e in _errs)]


def format_holdings_message(digest: dict, switch: "dict | None" = None, *,
                            as_of: str, picks: "list | None" = None,
                            alert_block: str = "", alert_extreme: bool = False) -> str:
    """digest(+switch+picks) → 每日持股續抱/換股 LINE 訊息（純函式,§1 數字全來自上游）。

    區段:標題 → 位階 → VIX → 換出 → 換入 → 今日選股 Top N（換股池）→ 235 加碼 →
    衛星停利 → 配置 → 抓取失敗 → 免責。
    picks（get_switch_in_candidates 的清單,已排除持股）併入「每日選股」→ 一則涵蓋
    持股續抱/換股 + 選股清單（§ user 2026-08-23 合併需求）;None → 不顯示該段（向後相容）。
    「今日無需動作」判定:無換出、無加碼、無停利 → 明講續抱（對齊 build_summary_prompt 語氣）。
    """
    digest = digest or {}
    _vix = _num(digest.get("vix"))
    _vix_txt = f"{_vix:.1f}" if _vix is not None else "抓取失敗"
    _total = int(_num(digest.get("total")) or 0)   # 契約漂移防禦:非數 total → 0,不 ValueError

    # 風險警語置頂:LINE 手機通知的預覽只顯示開頭數十字,要行動的訊息若排在
    # 標題與位階之後,推播列上根本看不到。由 orchestrator 傳入(見
    # src/compute/notify/market_alert_banner.build_alert_block);空字串 → 不佔行。
    lines: list[str] = ([alert_block, ""] if alert_block else []) + [
        "💼 持股戰情室｜每日續抱 / 換股",
        f"🕐 {as_of}（開盤前檢視,價格以最近交易日收盤為準）",
        _macro_line(switch),
        f"😱 VIX：{_vix_txt}　有效判斷 {_total} 檔",
        "",
    ]
    lines += _switch_out_lines(digest, switch)
    _in = _switch_in_lines(switch)
    _src = (switch or {}).get("switch_in_src")
    # 換入段顯示條件:來自你的觀察清單🟢 → 顯示(與全市場排名不同來源,各有價值);
    #   來自 screener 排名 + 已附「今日選股(換股池)」→ 同一批,只留清單(去重)。
    _show_in = bool(_in) and not (picks and _src == "screener")
    # cross-section 去重:換入段有顯示時,選股清單別重列同一檔(觀察清單🟢 也可能同時排進 screener)。
    _picks_show = picks
    if _show_in and picks:
        _in_codes = {T.normalize_ticker(d.get("代號"))
                     for d in (switch or {}).get("switch_in", [])}
        _picks_show = [c for c in picks
                       if T.normalize_ticker(c.get("代碼")) not in _in_codes]
    _pk = _picks_lines(_picks_show)
    if _show_in:
        lines += [""] + _in
    if _pk:
        lines += [""] + _pk
        # 風控(稽核🟡):總經轉守時 build_switch_advice 本把換入 cap 到 3 檔,但 screener 去重把
        # 換入段抹平 → 防禦盤易讀成「買這 10 檔」。補「換股從嚴」提醒,不需 AI 也看得到防禦訊號。
        if (switch or {}).get("stance") == "defensive":
            lines += ["　⚠️ 總經轉守：換股從嚴、優先汰弱、勿追高（此為換股池,非全數買進建議）"]
    for _seg in (_adds_lines(digest), _take_profit_lines(digest),
                 _allocation_line(digest), _errors_line(digest)):
        if _seg:
            lines += [""] + _seg

    # 收尾判定（§1 不含糊、不從零資料給安心結論）:
    #   total==0（代號讀到了但每檔抓取全失敗,例如 FinMind quota/斷網）→ 誠實「未能判斷」,
    #     **絕不**印「續抱、無需動作」的假 all-clear（稽核 🔴 A）;
    #   total>0 且無換出/加碼/停利 → 明講續抱。
    _switch_out = (switch or {}).get("switch_out") if switch is not None else digest.get("reds")
    _no_action = (not (_switch_out or [])
                  and not (digest.get("adds") or [])
                  and not (digest.get("take_profit") or []))
    if _total <= 0:
        lines += ["", "⚠️ 今日無任何持股完成評估（資料抓取全失敗），未能判斷 —— 請稍後檢視或查 log。"]
    elif _no_action and alert_extreme:
        # 個股健檢與大盤極端風險是**兩個不同的判斷範圍**,結論可以相反:
        # 手上每一檔的體質都還行(無換出/加碼/停利)、但大盤與資金面同時崩。
        # 若照常印「今日無需動作:續抱」,使用者會在同一則訊息裡讀到
        # 「清倉」與「續抱」兩個相反指令,而多數人會採信讓自己舒服的那個。
        # 故極端風險成立時明確限縮這句話的範圍,並把裁決權指回上方警語。
        lines += ["", "📭 個股層面無須換出 —— 但這只看單一持股體質，"
                      "不覆蓋上方的大盤極端風險，請以警語為準。"]
    elif _no_action:
        lines += ["", "📭 今日無需動作：續抱、定期定額即可。"]

    lines += ["", _DISCLAIMER]
    return "\n".join(lines)
