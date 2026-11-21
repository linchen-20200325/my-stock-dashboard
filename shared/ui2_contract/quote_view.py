"""公開股票報價「畫面狀態」契約（B-UI2-PUBLIC-QUOTE-VIEW-CONTRACT-1；L0；純離線、無 I/O、無時鐘）。

⛔ 只定義契約：無 production caller、不接 Real feed、不碰 Streamlit session／導航／按鈕、不讀私人 Sheet、
   無任何「是否持有」欄位或推論。本模組也不授權 runtime 接線。

═══ 輸入／輸出 ═══
`build_quote_view(selection, *, loaded, fetch_error, close, trade_date, fetched_at, source, is_stale) -> QuoteView`
- `selection`：`target_selection.parse_ticker_input` 的結果（信任邊界在該函式；symbol 原樣使用，0050 的前導零保留）。
- `trade_date`（交易日）與 `fetched_at`（抓取時間）**完全分開**，互相不得代填。

═══ 狀態優先序（先命中者勝；固定）═══
選取無效 > 讀取失敗（`fetch_error` 非 None）> 未載入 > 缺值 > 過期 > OK。
- 缺值＝`close`／`trade_date`／`source` 任一缺，或 `close` 非有限數／≤0／為 bool／非數字型別，或 `trade_date`
  不是合法 ISO 日期（YYYY-MM-DD 格式＋日曆有效性，如 2026-02-30 無效）。MISSING 一律帶具名 reason，**絕不顯示 0、不補值**。
- 過期＝`is_stale` 為 True 且資料完整：仍顯示最後收盤，chip 標過期。
- 只有 OK 與 STALE 可有 `value_text`（比照 `models.VALUE_BEARING_STATES` 慣例）；其餘態 `value_text` 必為 None。任何缺失不得得 OK。
- `fetched_at` 缺或格式不可辨識 → **不影響 OK**，但文字固定為「抓取時間未知」（不得以交易日代替，也不顯示無法辨識的原字串）。
- 無時鐘：函式**不判斷交易日是否為未來日**，也不計算過期天數；`is_stale` 由呼叫端傳入。

═══ 與 `target_selection.quote_readiness` 的關係 ═══
本函式是**畫面狀態契約**；`quote_readiness` 是**布林優先序契約**。兩者並存、不得矛盾，方向一致的定義：
(a) SELECTION_INVALID 兩邊同時成立；(b) OK⇔READY、STALE⇔STALE；(c) 其他任何畫面狀態，readiness 都不是 READY 或 STALE。
對應輸入：loaded 同；source_present＝（fetch_error 為 None 且 source 有效且 close 有效）；as_of_known＝trade_date 合法。
唯一排序差異是設計上刻意的：畫面把「讀取失敗」排在「未載入」之前（讀取已發生且失敗，應如實告知），
布林契約則無 fetch_error 概念；兩者在該情形下都不是就緒，方向一致。

`QuoteViewState` 的值帶 `quote_view_` 前綴，避免與 FieldState 等其他語意軸的值同字串；不新增 FieldState。
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from enum import Enum

from shared.ui2_contract.target_selection import SelectionStatus, TickerSelection
from shared.ui2_contract.tones import ChipTone


class QuoteViewState(str, Enum):
    OK = "quote_view_ok"
    NOT_LOADED = "quote_view_not_loaded"
    MISSING = "quote_view_missing"
    FETCH_FAILED = "quote_view_fetch_failed"
    STALE = "quote_view_stale"
    SELECTION_INVALID = "quote_view_selection_invalid"


#: 只有這兩態可帶 value_text
VALUE_BEARING = frozenset({QuoteViewState.OK, QuoteViewState.STALE})

#: chip 文字與 tone（文案 SSOT；線框文件須與此一致）。無效輸入＝灰（說明）；真出錯＝紅。
CHIP_TEXT = {
    QuoteViewState.OK: "資料正常",
    QuoteViewState.NOT_LOADED: "尚未查詢",
    QuoteViewState.MISSING: "資料未備",
    QuoteViewState.FETCH_FAILED: "讀取失敗",
    QuoteViewState.STALE: "資料過期",
    QuoteViewState.SELECTION_INVALID: "代號無效",
}
CHIP_TONE = {
    QuoteViewState.OK: ChipTone.POSITIVE,
    QuoteViewState.NOT_LOADED: ChipTone.NEUTRAL_INFO,
    QuoteViewState.MISSING: ChipTone.WARNING,
    QuoteViewState.FETCH_FAILED: ChipTone.DANGER,
    QuoteViewState.STALE: ChipTone.WARNING,
    QuoteViewState.SELECTION_INVALID: ChipTone.NEUTRAL_INFO,
}
NOTICE_TEXT = {
    QuoteViewState.OK: None,
    QuoteViewState.NOT_LOADED: "尚未查詢",
    QuoteViewState.MISSING: "資料未備（非 0）",
    QuoteViewState.FETCH_FAILED: "讀取失敗，請稍後再試",
    QuoteViewState.STALE: "資料已過期，仍顯示最後收盤",
    QuoteViewState.SELECTION_INVALID: "請輸入 4～6 碼代號（例如 0050）",
}
TEXT_FETCHED_AT_UNKNOWN = "抓取時間未知"

REASON_CLOSE_MISSING = "close_missing"
REASON_CLOSE_INVALID = "close_invalid"
REASON_TRADE_DATE_MISSING = "trade_date_missing"
REASON_TRADE_DATE_INVALID = "trade_date_invalid"
REASON_SOURCE_MISSING = "source_missing"
REASON_FETCH_FAILED = "fetch_failed"

_DATE_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
_FETCHED_AT_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}(?:[T ][0-9:.+Zz-]*)?")


@dataclass(frozen=True)
class QuoteFact:
    """已驗證的報價事實（只在 OK／STALE 產生）。trade_date 與 fetched_at 各自獨立。"""
    symbol: str
    close: float
    trade_date: str
    fetched_at: str | None
    source: str


@dataclass(frozen=True)
class QuoteView:
    state: QuoteViewState
    chip_text: str
    tone: ChipTone
    symbol: str | None
    value_text: str | None
    trade_date_text: str | None
    fetched_at_text: str | None
    source_text: str | None
    notice_text: str | None
    reason: str | None
    fact: QuoteFact | None


def _leap(y: int) -> bool:
    return y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)


def is_valid_iso_date(value: object) -> bool:
    """YYYY-MM-DD（ASCII）且為有效日曆日；不判斷是否未來日（無時鐘）。"""
    if not isinstance(value, str) or _DATE_RE.fullmatch(value) is None:
        return False
    y, m, d = int(value[0:4]), int(value[5:7]), int(value[8:10])
    if y < 1 or not 1 <= m <= 12:
        return False
    dim = [31, 29 if _leap(y) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m - 1]
    return 1 <= d <= dim


def _close_ok(close: object) -> bool:
    if isinstance(close, bool) or not isinstance(close, (int, float)):
        return False
    return math.isfinite(close) and close > 0


def _fetched_at_ok(value: object) -> bool:
    return (isinstance(value, str) and _FETCHED_AT_RE.fullmatch(value) is not None
            and is_valid_iso_date(value[:10]))


def _source_ok(value: object) -> bool:
    return isinstance(value, str) and value.strip() != ""


def _bare(state: QuoteViewState, symbol: str | None, reason: str | None) -> QuoteView:
    return QuoteView(state=state, chip_text=CHIP_TEXT[state], tone=CHIP_TONE[state], symbol=symbol,
                     value_text=None, trade_date_text=None, fetched_at_text=None, source_text=None,
                     notice_text=NOTICE_TEXT[state], reason=reason, fact=None)


def build_quote_view(selection: TickerSelection, *, loaded: bool, fetch_error: str | None, close: object,
                     trade_date: object, fetched_at: object, source: object, is_stale: bool) -> QuoteView:
    """依固定優先序建畫面狀態（見模組 docstring）。旗標非 bool → TypeError（Fail Loud）。"""
    for name, flag in (("loaded", loaded), ("is_stale", is_stale)):
        if not isinstance(flag, bool):
            raise TypeError(f"{name} 必須是 bool，收到 {flag!r}")
    if (not isinstance(selection, TickerSelection)
            or selection.status is not SelectionStatus.SELECTED or selection.symbol is None):
        reason = selection.reason if isinstance(selection, TickerSelection) else "selection_not_parsed"
        return _bare(QuoteViewState.SELECTION_INVALID, None, reason)
    symbol = selection.symbol
    if fetch_error is not None:
        reason = fetch_error if isinstance(fetch_error, str) and fetch_error.strip() else REASON_FETCH_FAILED
        return _bare(QuoteViewState.FETCH_FAILED, symbol, reason)
    if not loaded:
        return _bare(QuoteViewState.NOT_LOADED, symbol, None)
    reasons = []
    if close is None:
        reasons.append(REASON_CLOSE_MISSING)
    elif not _close_ok(close):
        reasons.append(REASON_CLOSE_INVALID)
    if trade_date is None:
        reasons.append(REASON_TRADE_DATE_MISSING)
    elif not is_valid_iso_date(trade_date):
        reasons.append(REASON_TRADE_DATE_INVALID)
    if not _source_ok(source):
        reasons.append(REASON_SOURCE_MISSING)
    if reasons:
        return _bare(QuoteViewState.MISSING, symbol, "+".join(reasons))
    fa = fetched_at if _fetched_at_ok(fetched_at) else None
    fact = QuoteFact(symbol=symbol, close=float(close), trade_date=trade_date, fetched_at=fa,
                     source=source.strip())
    state = QuoteViewState.STALE if is_stale else QuoteViewState.OK
    return QuoteView(
        state=state, chip_text=CHIP_TEXT[state], tone=CHIP_TONE[state], symbol=symbol,
        value_text=f"{fact.close:,.2f}", trade_date_text=f"交易日 {fact.trade_date}",
        fetched_at_text=(f"抓取時間 {fa}" if fa is not None else TEXT_FETCHED_AT_UNKNOWN),
        source_text=f"來源 {fact.source}", notice_text=NOTICE_TEXT[state], reason=None, fact=fact)
