"""「即時查一檔」結果區的 display-ready view-model（L0；純函式、frozen dataclass、零 I/O、零 streamlit、零時鐘）。

⛔ 本批只提供**純呈現層**資料形狀：無 production caller、不接線、不讀任何檔／網路／session。
   線框出處：GitHub #1199 R23.50（客戶已拍板）。只可 import `shared.*` 與標準庫。

═══ 介面 ═══
`build_local_lookup_result(quote, *, open_, high, low, close, volume, as_of, ma20, ma240, bias20_pct, vol_ratio5,
                          support, resistance, support_resistance_bars=None, source_user_declared)`   # source_user_declared 必填、無預設

- `quote`：呼叫端以 `quote_view.build_quote_view` 建好的 `QuoteView`（六態、symbol、資料日、抓取時間、來源、過期旗標
  都**只從這裡取**，不另開第二套文案、不另判狀態）。
- 其餘皆為 primitive（`Optional[float]` 等）。**只有 OK／STALE 兩態會畫數字**（`VALUE_BEARING`）；
  NOT_LOADED／SELECTION_INVALID／FETCH_FAILED／MISSING 只畫狀態列＋研究解釋固定字樣，數字區整個不出現
  （未載入 ≠ 資料未備，不能把「還沒查」畫成一排「資料未備」）。
- 缺值規則（§1 Fail Loud / missing ≠ 0）：None／bool／非數值／NaN／inf／超出顯示範圍 → 一律
  `TEXT_MISSING`（「⬜ 資料未備」）且 `is_missing=True`；**真 0（例如量 0 的跌停鎖死日）照實顯示「0」**，與缺值可區分。
  不補 0、不補值、不從別欄推。
- 矛盾輸入 fail loud（`ValueError`；支撐＞壓力亦同）：`as_of` 與 `quote` 的資料日不同；`close` 與 `quote` 的收盤不同；
  已有效的 high < low，或 open／close 落在 [low, high] 之外。這類是呼叫端接錯資料，不是「缺值」。

═══ 欄位 → 來源欄位對映（以讀到的程式為準；未驗的明寫）═══
| VM 欄位 | 參數 | 來源 |
|---|---|---|
| 開／高／低 | open_／high／low | `src/data/stock/stock_latest_ohlcv.OhlcvRow.open／high／low`（原始未調整價；`StockLatestOhlcv.latest`） |
| 收（OHLCV 列與價格區） | `quote`（`close` 僅交叉核對） | `OhlcvRow.close` → 呼叫端餵 `build_quote_view(close=…)`；價格區與 OHLCV 列同取 `quote.fact.close` |
| 量 | volume | `OhlcvRow.volume_shares`（FinMind 原始欄，**單位未驗**；本檔**不標股／張**，原值照顯示） |
| 資料日 | `quote`、`as_of` | `StockLatestOhlcv.as_of`（＝最後一列日期）＝`StockResearchFacts.as_of`；`as_of` 參數只做一致性核對 |
| 抓取時間 | `quote` | `StockLatestOhlcv.fetched_at`（UTC，呼叫端 isoformat 後交 `build_quote_view`）；缺／不可辨識 → 「抓取時間未知」，**不以資料日或匯入時間代替** |
| 來源 | `quote` | `StockLatestOhlcv.source`；依線框標「使用者自述，未經系統驗證」（`source_user_declared`） |
| MA20 | ma20 | `StockResearchFacts.ma[20]`（價格，4 位小數，本檔顯示 2 位） |
| MA240 | ma240 | `StockResearchFacts.ma[240]`（根數不足為 None → 缺值） |
| 乖離20 | bias20_pct | `StockResearchFacts.bias20_pct`（**單位 %**，不是比率；21 根以上才有） |
| 量比5 | vol_ratio5 | `StockResearchFacts.volume_ratio5`（**倍數**＝今日量／前 5 日均量，來源 2 位小數；6 根以上才有） |
| 支撐／壓力 | support／resistance／support_resistance_bars | `StockResearchFacts.support_20d／resistance_20d／support_resistance_bars`（C 已提供；實際涵蓋根數可 <20，標籤照實寫根數，不謊稱「20 日」） |

═══ 接線批待辦（本批未接線，下一批必做）═══
(a) `src/ui2/components/html.py::LOCAL_LOOKUP_RESULT_CSS` 必須併入 `src/ui2/shell/css.py` 的 CSS（單一注入點），
    **不可**直接丟 `st.markdown`。
(b) 「🤖 研究解釋：尚未啟用 ⬜」「日K非即時」「價格口徑由使用者聲明為未調整原始價，系統未驗證；除權息日前後指標可能失真」「使用者自述，未經系統驗證」
    是本檔**硬編碼字樣**，接線時須過 Copy Gate／三軸字樣守衛。

⚠️ 未驗：本檔以 `build_stock_research_facts` 與 `OhlcvRow` 原始碼為準，**尚未**與真實 FinMind 回應做端對端核對（本批無接線）。
"""
from __future__ import annotations

import math
import numbers
from dataclasses import dataclass

from shared.ui2_contract.quote_view import (
    CHIP_TEXT, CLOSE_DISPLAY_MAX, CLOSE_DISPLAY_MIN, NOTICE_TEXT, VALUE_BEARING, QuoteView, QuoteViewState,
)
from shared.ui2_contract.text import TEXT_MISSING_NOT_READY
from shared.ui2_contract.tones import ChipTone

# ── 字樣（本檔新增；不改 `text.py`）────────────────────────────────────
TEXT_MISSING = TEXT_MISSING_NOT_READY                 # 「⬜ 資料未備」（沿用既有字樣，不新造）
TEXT_LIMIT_UNADJUSTED = "價格口徑由使用者聲明為未調整原始價，系統未驗證；除權息日前後指標可能失真"   # 已核准 Copy（R23.52 U1；P-M2k D-1）
TEXT_LIMIT_NOT_REALTIME = "日K非即時"
TEXT_SOURCE_USER_DECLARED = "使用者自述，未經系統驗證"
TEXT_RESEARCH_DISABLED = "🤖 研究解釋：尚未啟用 ⬜"
#: L5 本機日K檔選擇區的固定字樣。`TEXT_LOCAL_FILE_LABEL`＝R23.50 已拍板線框用語「本機日K檔選擇」；
#: ⚠️ `TEXT_LOCAL_UNAVAILABLE`／`TEXT_LOCAL_NO_FILES` 是**新增字樣，尚未過 Copy Gate**（接線 PR 須請 P／客戶核可或改字）。
TEXT_LOCAL_FILE_LABEL = "本機日K檔選擇"
TEXT_LOCAL_UNAVAILABLE = "本機日K檔功能目前無法使用"       # 所有拒絕類原因共用一句（不洩漏是哪個檢查失敗）
TEXT_LOCAL_NO_FILES = "受控目錄內沒有可選的日K檔"
#: 系統真的讀不到／檔案本身有問題 → 紅色「讀取失敗」：沿用 `quote_view` 既有文案（不新增第二套）。
TEXT_LOCAL_FAILED_CHIP = CHIP_TEXT[QuoteViewState.FETCH_FAILED]
TEXT_LOCAL_FAILED_NOTICE = NOTICE_TEXT[QuoteViewState.FETCH_FAILED] or ""
SOURCE_SEP = "｜"

# ── 顯示範圍（具名、可調；單位錯誤防線，同 quote_view 的 CLOSE_DISPLAY_*）────────
PRICE_DISPLAY_MIN = CLOSE_DISPLAY_MIN
PRICE_DISPLAY_MAX = CLOSE_DISPLAY_MAX
# ⛔ 量／乖離／量比**不設**自訂顯示上限（客戶未核可；上限會把減資後真實的大乖離誤寫成「資料未備」，違反 §1）。
#    只擋 None／bool／非數值／NaN／inf（與量、量比的負值）。價格顯示範圍沿用 quote_view 已核准者。

#: 區塊鍵（固定順序）
OHLCV_KEYS = ("open", "high", "low", "close", "volume")
INDICATOR_KEYS = ("ma20", "ma240", "bias20", "vol_ratio5", "support", "resistance")
_OHLCV_LABELS = {"open": "開", "high": "高", "low": "低", "close": "收", "volume": "量"}


@dataclass(frozen=True)
class LocalLookupCell:
    """一格：缺值時 `value_text`＝`TEXT_MISSING`、`is_missing=True`；真 0 為 `is_missing=False` 且 `value_text` 為「0」等數字。"""
    key: str
    label: str
    value_text: str
    is_missing: bool


@dataclass(frozen=True)
class LocalLookupResultVM:
    state: QuoteViewState
    chip_text: str
    tone: ChipTone
    symbol: str | None
    notice_text: str | None
    has_data: bool                       # 只有 OK／STALE 為 True；False 時以下數字區全空
    close_text: str | None
    as_of_text: str | None
    fetched_at_text: str | None
    source_text: str | None
    ohlcv: tuple[LocalLookupCell, ...]
    indicators: tuple[LocalLookupCell, ...]
    notes: tuple[str, ...]
    research_text: str


# ── 數值驗證／格式化（缺值一律明確字樣，不補 0）────────────────────────────
def _num(x: object) -> float | None:
    """有限實數 → float；None／bool／非實數／NaN／inf／大到無法轉浮點 → None。"""
    if x is None or isinstance(x, bool):
        return None
    if not isinstance(x, numbers.Real):
        return None
    try:
        v = float(x)
    except (OverflowError, ValueError, TypeError):
        return None
    return v if math.isfinite(v) else None


def _price(x: object) -> float | None:
    v = _num(x)
    if v is None or v <= 0 or v < PRICE_DISPLAY_MIN or v > PRICE_DISPLAY_MAX:
        return None
    return v


def _volume(x: object) -> float | None:
    v = _num(x)
    if v is None or v < 0:
        return None
    return abs(v)                # abs：-0.0 → 0.0，避免顯示「-0」


def _bias(x: object) -> float | None:
    v = _num(x)
    return v


def _ratio(x: object) -> float | None:
    v = _num(x)
    return None if v is None or v < 0 else abs(v)    # abs：-0.0 → 0.0


def _fmt_price(v: float) -> str:
    return f"{v:,.2f}"


def _fmt_volume(v: float) -> str:
    return f"{v:,.0f}" if v.is_integer() else f"{v:,.2f}"


def _fmt_bias(v: float) -> str:
    r = round(v, 2)
    return "0.00%" if r == 0 else f"{r:+.2f}%"          # 避免「-0.00%」


def _fmt_ratio(v: float) -> str:
    return f"{v:,.2f} 倍"


def _cell(key: str, label: str, value: float | None, fmt) -> LocalLookupCell:
    if value is None:
        return LocalLookupCell(key=key, label=label, value_text=TEXT_MISSING, is_missing=True)
    return LocalLookupCell(key=key, label=label, value_text=fmt(value), is_missing=False)


def _sr_suffix(bars: object) -> str:
    """支撐／壓力標籤的窗口：恰 20 根 → 「近20日」；其他有效根數照實寫根數；未知 → 不寫窗口（不謊稱 20 日）。"""
    if isinstance(bars, bool) or not isinstance(bars, int) or bars <= 0:
        return ""
    return "（近20日）" if bars == 20 else f"（近{bars}根日K）"


def _check_ohlc_consistent(o: float | None, h: float | None, l: float | None, c: float | None) -> None:
    if h is not None and l is not None and h < l:
        raise ValueError("ohlc_inconsistent: high < low")
    for name, v in (("open", o), ("close", c)):
        if v is None:
            continue
        if (l is not None and v < l) or (h is not None and v > h):
            raise ValueError(f"ohlc_inconsistent: {name} 落在 [low, high] 之外")


def build_local_lookup_result(
        quote: QuoteView, *, open_: object, high: object, low: object, close: object, volume: object,
        as_of: str | None, ma20: object, ma240: object, bias20_pct: object, vol_ratio5: object,
        support: object, resistance: object, support_resistance_bars: object = None,
        source_user_declared: bool) -> LocalLookupResultVM:
    """建結果區 VM（見模組 docstring）。`quote` 非 `QuoteView`／`source_user_declared` 非 bool／未傳 → TypeError；
    `as_of` 非 str 且非 None → TypeError（須為 ISO 字串）。"""
    if not isinstance(quote, QuoteView):
        raise TypeError("quote 必須是 QuoteView（由 build_quote_view 產生）")
    if not isinstance(source_user_declared, bool):
        raise TypeError(f"source_user_declared 必須是 bool，收到 {source_user_declared!r}")
    if as_of is not None and not isinstance(as_of, str):
        raise TypeError("as_of 須為 ISO 字串（YYYY-MM-DD）或 None，不接受 date／datetime 物件")
    state = quote.state
    base = dict(state=state, chip_text=quote.chip_text, tone=quote.tone, symbol=quote.symbol,
                notice_text=quote.notice_text, research_text=TEXT_RESEARCH_DISABLED)
    if state not in VALUE_BEARING or quote.fact is None or quote.value_text is None:
        return LocalLookupResultVM(has_data=False, close_text=None, as_of_text=None, fetched_at_text=None,
                                   source_text=None, ohlcv=(), indicators=(), notes=(), **base)
    fact = quote.fact
    if as_of is not None and as_of != fact.trade_date:
        raise ValueError(f"as_of_mismatch: 傳入 {as_of!r} 與報價資料日 {fact.trade_date!r} 不同")
    o, h, l, c = _price(open_), _price(high), _price(low), _price(close)
    if c is not None and not math.isclose(c, fact.close, rel_tol=1e-9, abs_tol=1e-9):
        raise ValueError(f"close_mismatch: 傳入 {c!r} 與報價收盤 {fact.close!r} 不同")
    _check_ohlc_consistent(o, h, l, fact.close)
    sup, res = _price(support), _price(resistance)
    if sup is not None and res is not None and sup > res:
        raise ValueError("support_resistance_inverted: 支撐不可高於壓力（參數是否對調？）")
    ohlcv = (
        _cell("open", _OHLCV_LABELS["open"], o, _fmt_price),
        _cell("high", _OHLCV_LABELS["high"], h, _fmt_price),
        _cell("low", _OHLCV_LABELS["low"], l, _fmt_price),
        _cell("close", _OHLCV_LABELS["close"], fact.close, _fmt_price),     # 與價格區同源（quote.fact.close）
        _cell("volume", _OHLCV_LABELS["volume"], _volume(volume), _fmt_volume),   # 原值，不標股／張
    )
    sr = _sr_suffix(support_resistance_bars)
    indicators = (
        _cell("ma20", "MA20", _price(ma20), _fmt_price),
        _cell("ma240", "MA240", _price(ma240), _fmt_price),
        _cell("bias20", "乖離20", _bias(bias20_pct), _fmt_bias),
        _cell("vol_ratio5", "量比5", _ratio(vol_ratio5), _fmt_ratio),
        _cell("support", f"支撐{sr}", sup, _fmt_price),
        _cell("resistance", f"壓力{sr}", res, _fmt_price),
    )
    source_text = quote.source_text or ""
    if source_user_declared:
        source_text = f"{source_text}{SOURCE_SEP}{TEXT_SOURCE_USER_DECLARED}"
    return LocalLookupResultVM(
        has_data=True, close_text=quote.value_text, as_of_text=f"資料日 {fact.trade_date}",
        fetched_at_text=quote.fetched_at_text, source_text=source_text,
        ohlcv=ohlcv, indicators=indicators, notes=(TEXT_LIMIT_UNADJUSTED, TEXT_LIMIT_NOT_REALTIME), **base)
