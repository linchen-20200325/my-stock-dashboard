"""src/compute/notify/watchlist_message.py — 觀察池推播組字（T3，L2 純函式）。

§8.2 layer：**L2 純函式** —— 零 I/O、零 streamlit。輸入是
`watchlist_triggers.ScanResult`，輸出是要送進 `send_notification()` 的純文字。
（同 `src/compute/notify/__init__.py:3` 既有紀律。）

風格對齊既有的 `signal_message.py`：`format_*` 回純字串、帶 `as_of`、
§1 的「不偽造」原則寫在函式 docstring 裡。

════════════════════════════════════════════════════════════════════
深連結 —— 流程圖層次 4「二次分析」的接點
════════════════════════════════════════════════════════════════════
每檔附 `{app_url}?sid={代號}`。使用者點進去會直接落在該股頁面，
因為 `app.py` 開機閘門會把 `?sid=` 還原進 session（S1 那批**刻意保留**
的那段 —— 當時只拔掉 `chips_loaded` 的跨 session 還原，`sid` 保留的理由
正是「那是設定不是資料，還原它不會製造假的已載入狀態」）。

⇒ **閉環用一個 URL 就收，不需要 LINE webhook、不需要另架服務。**

════════════════════════════════════════════════════════════════════
§1 三種「不可偽裝成沒事」的狀態
════════════════════════════════════════════════════════════════════
1. **全部抓不到 K 線** → `format_scan_failure`，絕不可推「今日無觸發」
   （那會把「全部失敗」說成「全部安全」，是最危險的假訊號）。
2. **觀察池是空的** → `format_empty_watchlist`，讓使用者知道清單掉了
   而不是「沒訊號」。
3. **部分檔未評估** → 在正常訊息末尾**逐檔列出**原因，不靜默吞掉。
"""
from __future__ import annotations

from typing import Iterable

__all__ = [
    "build_deep_link",
    "format_watchlist_alert",
    "format_quiet_health_check",
    "format_scan_failure",
    "format_empty_watchlist",
]

_DISCLAIMER = "⚠️ 技術訊號提醒，非買賣建議。點連結回網頁做二次分析再決定。"


def build_deep_link(app_url: str, ticker: str) -> str:
    """組深連結 `{app_url}?sid={ticker}`。

    容錯：`app_url` 有無結尾斜線都可；已帶 query string 時用 `&` 銜接。
    `app_url` 為空 → 回空字串（caller 不印連結，而非印一個壞掉的 URL）。
    """
    _u = str(app_url or "").strip()
    _t = str(ticker or "").strip()
    if not _u or not _t:
        return ""
    _sep = "&" if "?" in _u else "?"
    return f"{_u}{_sep}sid={_t}"


def _fmt_dates(dates: Iterable[str]) -> str:
    """資料日期字串。多個日期並存代表各檔資料不同步，必須讓使用者看見。"""
    _d = [d for d in dates if d]
    if not _d:
        return "資料日未知"
    if len(_d) == 1:
        return f"資料日 {_d[0]}"
    return f"資料日 {_d[0]}～{_d[-1]}（**各檔不同步**）"


def _skipped_block(scan) -> list[str]:
    """未評估清單。§1：不靜默吞掉，逐檔講原因。"""
    _sk = scan.skipped
    if not _sk:
        return []
    _lines = ["", f"⚪ 未評估 {len(_sk)} 檔（**不代表沒事**）："]
    _lines += [f"　· {v.ticker} {v.name}".rstrip() + f" — {v.skipped_reason}"
               for v in _sk]
    return _lines


def format_watchlist_alert(scan, *, as_of: str, app_url: str = "") -> str:
    """有觸發時的推播。

    Args:
        scan: `watchlist_triggers.ScanResult`。
        as_of: 執行時間字串（orchestrator 傳入 TW 時間）。
        app_url: Streamlit app 網址；空字串 → 不附連結（不印壞 URL）。

    §1：每檔會標示「三維出場實際評估了幾維」—— v1 常態只有技術面一維，
    不標的話使用者會把 1 維的結論讀成三維綜合判斷。
    """
    _fired = scan.fired
    _head = [
        f"🔔 觀察池提醒 · {as_of}",
        f"{_fmt_dates(scan.data_dates)}　監控 {scan.n_evaluated} 檔　觸發 {len(_fired)} 檔",
        "",
    ]
    _body: list[str] = []
    for _v in _fired:
        _title = f"🔴 {_v.ticker} {_v.name}".rstrip()
        if _v.close is not None:
            _title += f"　收 {_v.close:.2f}"
        _body.append(_title)
        _body += [f"　· {r}" for r in _v.reasons]
        # §1：三維出場有觸發時，講清楚是幾維算出來的
        if _v.exit_score is not None and _v.evaluated_dims < 3:
            _body.append(
                f"　（三維出場只評估了 {_v.evaluated_dims}/3 維 —— "
                "籌碼需法人資料、新聞需 AI，本次未齊）")
        _link = build_deep_link(app_url, _v.ticker)
        if _link:
            _body.append(f"　🔗 {_link}")
        _body.append("")

    return "\n".join(_head + _body + _skipped_block(scan) + ["", _DISCLAIMER])


def format_quiet_health_check(scan, *, as_of: str, period_label: str = "本週") -> str:
    """健康碼 —— 定期確認 cron 還活著。

    純事件驅動推播的盲點：連續多日沒消息時，使用者分不出
    「市場平靜」與「cron 三天前就掛了」。這則訊息就是解那個盲點，
    成本極低（一週一則）。

    §1：即使是健康碼也要帶未評估清單 —— 若有 8 檔長期抓不到，
    「監控 10 檔」這句話本身就會誤導。
    """
    _lines = [
        f"✅ 觀察池運作正常 · {as_of}",
        f"{_fmt_dates(scan.data_dates)}",
        "",
        f"{period_label}監控 {scan.n_evaluated} 檔，目前無觸發。",
    ]
    return "\n".join(_lines + _skipped_block(scan))


def format_scan_failure(*, as_of: str, n_total: int, detail: str = "") -> str:
    """§1 最重要的一則：**全部**抓不到 K 線。

    絕不可推「今日無觸發」—— 那會把「全部失敗」說成「全部安全」。
    使用者依據那句話決定不看盤，而實際上系統根本沒在監控。
    """
    _lines = [
        f"🚨 觀察池掃描失敗 · {as_of}",
        "",
        f"清單內 {n_total} 檔**全部**取不到 K 線，本次**沒有做任何判斷**。",
        "這不等於「今天沒事」—— 系統這次完全沒有監控到你的持股。",
        "",
        "常見原因：Yahoo 限流 / FinMind quota 用罄 / 觀察池代號格式錯誤。",
    ]
    if detail:
        _lines += ["", f"診斷：{detail}"]
    return "\n".join(_lines)


def format_empty_watchlist(*, as_of: str, source_hint: str = "") -> str:
    """觀察池是空的。

    §1：必須與「有清單但沒訊號」區分 —— 否則清單來源壞掉時，
    使用者會以為系統在正常監控。
    """
    _lines = [
        f"⚠️ 觀察池是空的 · {as_of}",
        "",
        "本次讀到 0 檔標的，因此**沒有監控任何東西**。",
        "若你確實有在追蹤股票，代表清單來源沒讀到。",
    ]
    if source_hint:
        _lines += ["", f"來源：{source_hint}"]
    return "\n".join(_lines)
