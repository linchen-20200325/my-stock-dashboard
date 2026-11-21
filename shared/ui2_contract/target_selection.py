"""公開股票選取／跨頁代號 identity 小契約（B-UI2-PUBLIC-TICKER-CONTRACT-MINSLICE-1；L0；純離線、無 I/O）。

⛔ 本模組**只定義契約**：沒有任何 production caller、不碰 Streamlit session、不碰導航／按鈕、不讀私人 Sheet。
⛔ 絕不含「是否持有」欄位／函式／推論 —— 本契約只回答「使用者輸入的是不是一個格式合法的代號」與
   「這個代號的報價資料目前可不可用」，與帳本、持股完全無關。
⛔ 不取代、不改動既有的任何代號 normalize 函式；語意刻意不同（見下方「與既有函式的差異」）。

═══ 設計決策與理由（依「最安全、最防禦、最小破壞、真實性優先」；§1 Fail Loud, Never Fake）═══
D1 TICKER_PATTERN＝`[0-9][0-9A-Z]{3,5}`（總長 4~6、首字元數字）。涵蓋 0050、2330、00631L、00980A。
   用 `fullmatch`（不用 `$`，避免 `$` 吃掉尾端換行）。
D2 只做 `strip()`＋`upper()`，**不補零、不去零、不猜**。"50" 不會被當成 "0050"（過短 → invalid，
   原因明確），否則會悄悄選到另一檔標的 —— 錯的代號比沒有代號更危險。
D3 **先驗 ASCII 再 upper()**：Python 的 `upper()` 會把部分非 ASCII 字元映射成 ASCII（例如 'ı'→'I'、'ſ'→'S'），
   若先 upper 再比對，會讓看起來不是代號的輸入被「規格化」成合法代號＝自動修正。全形（２３３０）一律 invalid。
D4 小寫 ASCII 視為大小寫規格化：'2330a' → '2330A'（SELECTED）。這是唯一的規格化，且保留原始輸入於 `raw`。
D5 帶 `.TW`／`.TWO` 後綴一律 invalid（reason=`suffix_not_accepted`）：後綴代表「上市／上櫃」判定，
   本契約不替上游猜；須由上游先明確處理（拆後綴＋自行決定市場）再傳入。
D6 非 str（int、bytes…）→ invalid(`not_text`)，不 raise、不 `str()` 強轉（`50` 強轉成 "50" 或 b'0050' 強轉成 "b'0050'" 都是造假）。
   None／空字串／全空白 → EMPTY（使用者沒選，不是錯誤）。內部含空白 → invalid。
D7 重複**必須揭露**：`parse_ticker_list` 不默默去重或覆蓋，`duplicates` 逐一列出（每個重複代號列一次，依「第二次出現」順序）。
D8 `quote_readiness`：全為呼叫端傳入的布林，函式內無時鐘、無網路。優先序固定（見函式 docstring）；
   任一條件缺失都不得得到 READY。旗標非 bool 即 `TypeError`（Fail Loud；寧可炸掉不可把真值判斷當成就緒）。
D9 使用自有 str Enum（`SelectionStatus`、`QuoteReadiness`），**不**新增 FieldState、不沿用 DEC-124 capability marker；
   QuoteReadiness 的值一律帶 `quote_` 前綴，避免與 FieldState 的值（如 stale）同字串而被誤當同一語意軸。

═══ 與既有四個 normalize 函式的差異（據實描述；新契約的設計決策，不改動、不取代既有函式）═══
- `normalize_holding_ticker`：只 `strip().upper()`，非 str 拋 TypeError，不加減 `.TW`、不補零。與本契約在
  strip＋upper／不補後綴／不去後綴上同向；差異僅在本契約多了格式驗證、後綴一律 invalid、重複顯式揭露、可用性判定。
- `normalize_etf_ticker`：4~6 碼純台股代號補 `.TW`，已含後綴原樣，空值回 ''，非字串以 `str()` 強轉。
- `dividend_station_thresholds.normalize_ticker`：去 `.TW`／`.TWO` 並大寫，`str()` 強轉。
- `etf_smart_analysis._normalize_ticker`：無 '.' 就補 `.TW`。
「數字化（0050→50）」是 DEC-218 §D-1 所述 SA 推播路徑的另一處行為，**不屬**上列四個函式。
本契約：不補 `.TW`、不去 `.TW`、不數字化，後綴須由上游明確處理，重複須揭露，非 str 不強轉。
是否、何時、由誰接線＝另行授權（I1144-WIRING-GATE 等），本檔不授權 runtime 接線。

═══ 補充說明 ═══
- `strip()` 會修剪首尾 Unicode 空白（含 NBSP、全形空格、換行），屬「首尾空白修剪」；內部空白仍 invalid。
- `duplicates` 每個代號只列一次、不含次數（要次數請呼叫端自行統計）。
- `quote_readiness` 只檢查 `selection.status`／`symbol` 非 None，不重驗格式；信任邊界在 `parse_ticker_input`。
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any

#: 合法代號格式：總長 4~6、首字元數字、其餘 0-9A-Z（涵蓋 0050、2330、00631L、00980A）。
TICKER_PATTERN = re.compile(r"[0-9][0-9A-Z]{3,5}")
TICKER_MIN_LEN = 4
TICKER_MAX_LEN = 6
_REJECTED_SUFFIXES = (".TW", ".TWO")


class SelectionStatus(str, Enum):
    SELECTED = "selected"
    EMPTY = "empty"
    INVALID = "invalid"


class QuoteReadiness(str, Enum):
    SELECTION_INVALID = "quote_selection_invalid"
    NOT_LOADED = "quote_not_loaded"
    SOURCE_UNAVAILABLE = "quote_source_unavailable"
    AS_OF_UNKNOWN = "quote_as_of_unknown"
    STALE = "quote_stale"
    READY = "quote_ready"


# reason 具名常數（invalid 的原因；EMPTY／SELECTED 的 reason 為 None）
REASON_NOT_TEXT = "not_text"
REASON_SUFFIX = "suffix_not_accepted"
REASON_NON_ASCII = "non_ascii_characters"
REASON_INTERNAL_WHITESPACE = "internal_whitespace"
REASON_BAD_CHARS = "invalid_characters"
REASON_TOO_SHORT = "too_short"
REASON_TOO_LONG = "too_long"
REASON_FIRST_NOT_DIGIT = "first_char_not_digit"
REASON_NOT_A_LIST = "not_a_list"


@dataclass(frozen=True)
class TickerSelection:
    raw: Any
    symbol: str | None
    status: SelectionStatus
    reason: str | None


@dataclass(frozen=True)
class TickerSelectionSet:
    selected: tuple[str, ...]
    duplicates: tuple[str, ...]
    invalid: tuple[TickerSelection, ...]
    empty_count: int


def _invalid(raw: Any, reason: str) -> TickerSelection:
    return TickerSelection(raw=raw, symbol=None, status=SelectionStatus.INVALID, reason=reason)


def parse_ticker_input(raw: Any) -> TickerSelection:
    """單一輸入 → TickerSelection。只做 strip＋（ASCII 檢查後）upper；永不 raise、不補零、不猜。"""
    if raw is None:
        return TickerSelection(raw=raw, symbol=None, status=SelectionStatus.EMPTY, reason=None)
    if not isinstance(raw, str):
        return _invalid(raw, REASON_NOT_TEXT)
    text = raw.strip()
    if text == "":
        return TickerSelection(raw=raw, symbol=None, status=SelectionStatus.EMPTY, reason=None)
    if not text.isascii():
        return _invalid(raw, REASON_NON_ASCII)
    if any(ch.isspace() for ch in text):
        return _invalid(raw, REASON_INTERNAL_WHITESPACE)
    sym = text.upper()
    if sym.endswith(_REJECTED_SUFFIXES):
        return _invalid(raw, REASON_SUFFIX)
    if not all(ch.isdigit() or ("A" <= ch <= "Z") for ch in sym):
        return _invalid(raw, REASON_BAD_CHARS)
    if len(sym) < TICKER_MIN_LEN:
        return _invalid(raw, REASON_TOO_SHORT)
    if len(sym) > TICKER_MAX_LEN:
        return _invalid(raw, REASON_TOO_LONG)
    if not ("0" <= sym[0] <= "9"):
        return _invalid(raw, REASON_FIRST_NOT_DIGIT)
    if TICKER_PATTERN.fullmatch(sym) is None:      # 縱深防禦：上列分支已窮盡，此行不應觸發
        return _invalid(raw, REASON_BAD_CHARS)
    return TickerSelection(raw=raw, symbol=sym, status=SelectionStatus.SELECTED, reason=None)


def parse_ticker_list(raws: Any) -> TickerSelectionSet:
    """多個輸入 → TickerSelectionSet（保序）。僅接受 list／tuple；其他型別（含 None、str）視為整體 invalid，不猜。

    `selected`＝唯一有效代號（保序）；`duplicates`＝重複出現的代號（每個列一次，依第二次出現順序，**顯式揭露**）；
    `invalid`＝逐項 TickerSelection；`empty_count`＝空項數。
    """
    if not isinstance(raws, (list, tuple)):
        return TickerSelectionSet((), (), (_invalid(raws, REASON_NOT_A_LIST),), 0)
    selected: list[str] = []
    duplicates: list[str] = []
    invalid: list[TickerSelection] = []
    empty_count = 0
    for item in raws:
        sel = parse_ticker_input(item)
        if sel.status is SelectionStatus.EMPTY:
            empty_count += 1
        elif sel.status is SelectionStatus.INVALID:
            invalid.append(sel)
        elif sel.symbol in selected:
            if sel.symbol not in duplicates:
                duplicates.append(sel.symbol)
        else:
            selected.append(sel.symbol)
    return TickerSelectionSet(tuple(selected), tuple(duplicates), tuple(invalid), empty_count)


def quote_readiness(selection: TickerSelection, *, loaded: bool, source_present: bool,
                    as_of_known: bool, is_stale: bool) -> QuoteReadiness:
    """報價資料可用性。優先序固定（先命中者勝）：

    選取無效 > 未載入 > 來源缺席 > as_of 未知 > 過期 > 就緒。
    只有「選取有效、已載入、來源在場、as_of 已知、未過期」同時成立才回 READY；任一缺失都不得 READY。
    旗標全由呼叫端傳入（無時鐘、無網路）；非 bool 旗標 → TypeError（Fail Loud）。
    """
    for name, flag in (("loaded", loaded), ("source_present", source_present),
                       ("as_of_known", as_of_known), ("is_stale", is_stale)):
        if not isinstance(flag, bool):
            raise TypeError(f"{name} 必須是 bool，收到 {flag!r}")
    if (not isinstance(selection, TickerSelection)
            or selection.status is not SelectionStatus.SELECTED or selection.symbol is None):
        return QuoteReadiness.SELECTION_INVALID
    if not loaded:
        return QuoteReadiness.NOT_LOADED
    if not source_present:
        return QuoteReadiness.SOURCE_UNAVAILABLE
    if not as_of_known:
        return QuoteReadiness.AS_OF_UNKNOWN
    if is_stale:
        return QuoteReadiness.STALE
    return QuoteReadiness.READY
