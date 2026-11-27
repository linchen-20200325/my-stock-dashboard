"""M2 個股查詢垂直切片「B 線」：UI2 離線整合接收測試（tests-only；零網路、零 secrets、不落盤）。

授權：#1199 R23.38（comment 7216622932）B 項。⛔ 本檔不改任何 production 檔、守衛、旗標；不造 FAKE 畫面。

═══ 這個測試在驗什麼 ═══
A 線（尚不存在）將提供 `fetch_stock_latest_ohlcv(sid, *, token)`：回傳「同次已驗證日序列＋末列」＋ source／as_of／fetched_at、
原始 OHLCV、錯誤／缺值分離、量為原值單位（NV，不換算）。本檔在**測試內**定義「接收橋」（純函式，僅存在於本檔），
把該資料契約轉成 `build_quote_view` 的輸入，並驗證輸出 `QuoteView`：
  `AContractResult`（本檔 dataclass，待 A 實作後以真函式回傳型別替換） → `bridge()` → `build_quote_view` → `QuoteView`
C 線（`build_stock_research_facts`，尚不存在）的「確定性計算結果」改用 repo **既有真純函式**對同一組 bars 計算
（`src/compute/strategy/tech_indicators.py`：`calc_ma_series`／`calc_rsi`／`calc_volume_ratio`；
`src/compute/strategy/overextension.py`：`assess_price_overextension`），所以橋接的不是純 mock。

═══ 契約依據（讀碼引用；行號為 origin/main da6f901 當時）═══
- `shared/ui2_contract/quote_view.py`：`QuoteViewState` L48-54；`CHIP_TEXT`／`NOTICE_TEXT` L61-84；
  `build_quote_view(selection, *, loaded, fetch_error, close, trade_date, fetched_at, source, is_stale)` L189-225；
  優先序 選取無效 > 讀取失敗 > 未載入 > 缺值 > 過期 > OK（L12-13、L195-225）；
  `fetch_error` 非 None 只決定狀態、原文不進任何輸出（L22-23、L201）；`fetched_at` 缺／不可辨識→「抓取時間未知」（L24-25、L224）；
  函式**無時鐘**、不判斷未來日、`is_stale` 由呼叫端傳入（L26）。
- `shared/ui2_contract/target_selection.py::parse_ticker_input`：只 strip＋upper、不補零不去零（D2）、全形／後綴／過短過長 invalid。
  前導零：`"0050"` 的 symbol 原樣保留（L48 D1／D2）。
- `src/ui2/views/target.py::lookup_submission_view` L31-34：現行唯一接收層，`loaded=False` 固定 → 只會得到
  SELECTION_INVALID／NOT_LOADED（P1；DEC-223〔docs/DECISIONS.md〕：不接資料、P2 另案）。
- `docs/vnext/NEWUI2_TARGET_LOOKUP_QUOTE_WIREFRAME_2026-11-21.md` §5 六態表（文案與 `quote_view.py` 一致）。
- DEC-221（選取契約）、DEC-223（P1 輸入；A1 已核准：過期沿用 7 日門檻、價格顯示範圍 0.005～1,000,000）。
- `src/data/core/finmind_client.py::finmind_get`（只讀回傳形狀、不呼叫）：成功→DataFrame（可能空）；失敗／例外→**空 DataFrame**
  （§1 fail-safe），確定失敗時才在 `failed` list 寫一筆說明。⇒ 「空」本身分不出「真沒資料」與「失敗」：A 必須自行把兩者分開成
  `error`／`missing`（本檔契約即據此把兩者設為互斥欄位）。
- 過期門檻：`shared/staleness.py::STALE_DAYS_DAILY`（=7，日頻；`data_coverage.py` 等同 SSOT 消費）＋`staleness_days`
  （距「預期最新交易日」的日曆天，週末往前退）。本檔**不自訂門檻**。

═══ 接收橋對 A／C 契約的假設（P 收斂用；每條都是『假設』，未對真 A／C 驗證）═══
見模組常數 `A_CONTRACT_ASSUMPTIONS`／`C_CONTRACT_ASSUMPTIONS`，並由測試強制其存在。

═══ 結構 ═══
§1 資料契約與橋　§2 案例矩陣　§3 逐案例驗收＋不變量　§4 有牙（錯誤橋必須被判紅）　§5 序列／事實（C 側確定性）
§6 安全負控　§7 與 UI2 既有接收層的接線事實（characterization；AppTest）
"""
from __future__ import annotations

import dataclasses
import datetime as dt
import inspect
import math
import pathlib
import socket
from dataclasses import dataclass, field

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from shared.staleness import STALE_DAYS_DAILY, staleness_days
from shared.ui2_contract.pages import P4_TARGET
from shared.ui2_contract.quote_view import (
    CHIP_TEXT, NOTICE_TEXT, TEXT_FETCHED_AT_UNKNOWN, VALUE_BEARING, QuoteView, QuoteViewState as S,
    build_quote_view, is_valid_iso_date,
)
from shared.ui2_contract.target_selection import SelectionStatus, parse_ticker_input
from src.compute.strategy.overextension import assess_price_overextension
from src.compute.strategy.tech_indicators import calc_ma_series, calc_rsi, calc_volume_ratio

ROOT = pathlib.Path(__file__).resolve().parent.parent

#: 測試用「今日」：2026-11-25 為週三（以 `dt.date.weekday()` 在 §0 測試中釘死），橋與被測函式皆不讀系統時鐘。
TODAY = dt.date(2026, 11, 25)

A_CONTRACT_ASSUMPTIONS = (
    "A1 回傳單一物件含：symbol(str，保留前導零)、bars(同次已驗證日序列，每列 date/open/high/low/close/volume)、"
    "last(末列＝日期最大者)、source(str)、as_of(=末列交易日)、fetched_at(抓取時間，與 as_of 分離)、error、missing。",
    "A2 error 與 missing 互斥且分離：error＝讀取失敗（網路／額度／逾時…）；missing＝讀取成功但該代號查無資料／欄位缺。"
    "（finmind_get 失敗與無資料都回空 DataFrame，A 必須自行分辨。）",
    "A3 error 只應是分類 token；但橋不信任它——即使 A 傳進含 token／URL 的原文，橋也不得讓它進任何輸出。",
    "A4 bars 的 volume 為來源原值單位（NV，不換算）；可為 None（缺值）；橋原樣透傳、不補 0。",
    "A5 價格為未還原權息的原始價；橋/事實的 limits 必須揭露此限制。",
    "A6 as_of 與末列日期必須一致；不一致、末列缺、symbol 與查詢不同（含前導零被吃掉）＝橋視為不可信 → MISSING（不當 OK）。",
    "A7 bars 順序不保證：橋以日期升冪排序後取最大日為末列；重複日期＝序列不可信 → MISSING。",
    "A8 source 字串由 A 提供（本檔用 'FinMind:TaiwanStockPrice' 為假設值，非 A 的實際字串）。",
    "A9 資料日在『今日』之後（未來日）＝不可信 → MISSING；橋自己判（quote_view 無時鐘）。",
    "A10 過期＝staleness_days(as_of, today) > shared.staleness.STALE_DAYS_DAILY（嚴格大於；與 stale_tag／data_coverage 的 > 慣例同）。",
)
C_CONTRACT_ASSUMPTIONS = (
    "C1 事實只在 view 為 OK／STALE 時產出；其餘態 facts=None。",
    "C2 根數不足時指標為 None（不是 0、不是 NaN）；overextension 回『資料不足』。",
    "C3 事實必須揭露：日期區間、根數、未還原權息、量為原值單位；文案不含買賣／目標／停損字樣。",
    "C4 同一組 bars（不論輸入順序）得到相同事實（確定性）。",
    "C5 序列內任一根收盤無效（缺／非數／≤0）→ 不產指標（facts=None＋原因），不 ffill、不補 0。",
)

SECRET = "SECRET123"
HOSTILE_ERROR = (f"HTTPError: https://api.finmindtrade.com/api/v4/data?dataset=TaiwanStockPrice&token={SECRET} "
                 f"Authorization: Bearer {SECRET} FINMIND_TOKEN=/home/x/.env")
LEAK_MARKERS = (SECRET, "FINMIND", "Bearer", "token", "http", "Authorization", "/home/")
FORBIDDEN_FACT_WORDS = ("買進", "賣出", "加碼", "減碼", "目標價", "目標", "停損", "停利", "進場", "出場", "建議買", "建議賣")


@pytest.fixture(autouse=True)
def _offline(monkeypatch):
    """全檔零網路：任何 socket 連線都 raise（並記錄）。"""
    attempts: list[str] = []

    def deny(*a, **k):
        attempts.append(repr(a)[:80])
        raise OSError("network disabled by test (M2 lookup integration, offline)")
    monkeypatch.setattr(socket.socket, "connect", deny)
    monkeypatch.setattr(socket.socket, "connect_ex", deny)
    monkeypatch.setattr(socket, "create_connection", deny)
    monkeypatch.setenv("UI2_LOOKUP_INPUT", "")
    yield attempts
    assert attempts == [], f"本檔不得有任何網路連線：{attempts}"


# ════════════════════════════════════════════════════════════════════
# §1 資料契約（A 側，測試內表示）與接收橋
# ════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class AContractBar:
    """A 契約的一列日 K（待 A 實作後以真型別替換）。所有欄位型別刻意是 object：橋必須不信任。"""
    date: object
    open: object
    high: object
    low: object
    close: object
    volume: object          # 原值單位（NV），可為 None


@dataclass(frozen=True)
class AContractResult:
    """A 契約（待 A 實作後以 `fetch_stock_latest_ohlcv` 的真回傳型別替換）。"""
    symbol: object
    bars: object                       # 同次已驗證日序列（tuple[AContractBar, ...]）
    last: object                       # 末列（AContractBar | None）
    source: object
    as_of: object
    fetched_at: object
    error: object = None               # 讀取失敗（A 應給分類 token；橋不信任）
    missing: object = None             # 讀取成功但缺值


@dataclass(frozen=True)
class ResearchFacts:
    """C 側『確定性證據』的測試內替身：欄位由 repo 真純函式算出。"""
    n_bars: int
    first_date: str
    last_date: str
    last_volume: float | None
    ma20: float | None
    rsi14: float | None
    volume_ratio5: float | None
    overextension_level: str
    limits: tuple[str, ...]

    def lines(self) -> tuple[str, ...]:
        def f(x, spec=".2f"):
            return "資料不足" if x is None else format(x, spec)
        return (f"日 K {self.n_bars} 根（{self.first_date}～{self.last_date}）",
                f"MA20 {f(self.ma20)}", f"RSI14 {f(self.rsi14, '.1f')}", f"量比(5日) {f(self.volume_ratio5)}",
                f"位階 {self.overextension_level}",
                f"成交量原值 {'未提供' if self.last_volume is None else format(self.last_volume, ',.0f')}",
                *self.limits)


@dataclass(frozen=True)
class BridgeOutput:
    view: QuoteView
    facts: ResearchFacts | None
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class Policy:
    """橋的『旋鈕』：預設＝正確行為。§4 每個旋鈕翻一個＝一個『錯誤橋』，必須被驗收判紅（有牙）。"""
    missing_close_as_zero: bool = False
    ignore_stale: bool = False
    fetched_at_from_trade_date: bool = False
    leak_error_text: bool = False
    symbol_loose_zero_match: bool = False
    accept_future_date: bool = False
    accept_duplicate_dates: bool = False
    skip_sort: bool = False
    facts_zero_fill: bool = False
    facts_on_non_value_state: bool = False
    volume_none_as_zero: bool = False


CORRECT = Policy()


def _norm_series(bars, policy: Policy):
    """→ (升冪序列 | None, reasons)。None＝序列不可信。"""
    if not isinstance(bars, (tuple, list)) or len(bars) == 0:
        return None, ["series_empty"]
    if any(not isinstance(b, AContractBar) or not is_valid_iso_date(b.date) for b in bars):
        return None, ["bar_date_invalid"]
    dates = [b.date for b in bars]
    reasons: list[str] = []
    if len(set(dates)) != len(dates):
        if not policy.accept_duplicate_dates:
            return None, ["duplicate_trade_date"]
    if policy.skip_sort:
        return list(bars), reasons
    out = sorted(bars, key=lambda b: b.date)
    if [b.date for b in out] != dates:
        reasons.append("reordered_ascending")
    return out, reasons


def _valid_close(x) -> bool:
    return (isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(float(x)) and float(x) > 0)


def compute_facts(bars: list[AContractBar], policy: Policy) -> ResearchFacts | None:
    """C 側替身：同一組 bars → 既有真純函式。任一收盤無效 → None（C5）。"""
    if any(not _valid_close(b.close) for b in bars):
        return None
    df = pd.DataFrame({
        "close": [float(b.close) for b in bars],
        "high": [float(b.high) if _valid_close(b.high) else float("nan") for b in bars],
        "low": [float(b.low) if _valid_close(b.low) else float("nan") for b in bars],
        "volume": [float(b.volume) if isinstance(b.volume, (int, float)) and not isinstance(b.volume, bool)
                   and math.isfinite(float(b.volume)) else float("nan") for b in bars],
    })
    n = len(df)
    ma = calc_ma_series(df["close"], 20).iloc[-1] if n >= 20 else None
    ma20 = float(ma) if ma is not None and pd.notna(ma) else None
    rsi14 = calc_rsi(df, 14)                                       # 根數不足 → None（真函式）
    vols = df["volume"].iloc[-6:] if n >= 6 else None
    vr = calc_volume_ratio(df, 5) if vols is not None and vols.notna().all() else None   # NaN 量不可流入（真函式會回 nan）
    level = assess_price_overextension(df["close"])["level"]       # 不足 21 根 → '資料不足'
    last_vol = bars[-1].volume if isinstance(bars[-1].volume, (int, float)) and not isinstance(bars[-1].volume, bool) else None
    if policy.facts_zero_fill:                                     # 錯誤橋：不足補 0
        ma20, rsi14, vr = (0.0 if x is None else x for x in (ma20, rsi14, vr))
    if policy.volume_none_as_zero and last_vol is None:            # 錯誤橋：量缺當 0
        last_vol = 0
    limits = ("價格為來源原始價，未還原權息", f"僅 {n} 根日 K（{bars[0].date}～{bars[-1].date}）",
              "成交量為來源原值單位，未換算")
    return ResearchFacts(n_bars=n, first_date=bars[0].date, last_date=bars[-1].date,
                         last_volume=None if last_vol is None else float(last_vol), ma20=ma20, rsi14=rsi14,
                         volume_ratio5=vr, overextension_level=level, limits=limits)


def bridge(raw, result, *, today: dt.date, policy: Policy = CORRECT) -> BridgeOutput:
    """A 契約 → `build_quote_view` 輸入 →（OK／STALE 時）C 側事實。純函式，無時鐘（today 由呼叫端注入）。"""
    sel = parse_ticker_input(raw)
    if result is None:                                             # 尚未查詢
        v = build_quote_view(sel, loaded=False, fetch_error=None, close=None, trade_date=None, fetched_at=None,
                             source=None, is_stale=False)
        return BridgeOutput(v, None, ())
    reasons: list[str] = []
    if result.error is not None:                                   # 讀取失敗：只傳『有錯』，原文不進任何輸出
        if policy.leak_error_text:
            reasons.append(str(result.error))
        else:
            reasons.append("a_error")
        v = build_quote_view(sel, loaded=True, fetch_error="fetch_failed", close=None, trade_date=None,
                             fetched_at=None, source=None, is_stale=False)
        return BridgeOutput(v, None, tuple(reasons))

    trusted = True
    series, rs = _norm_series(result.bars, policy)
    reasons += rs
    if result.missing is not None:
        reasons.append("a_missing")
        trusted = False
    if series is None:
        trusted = False
    sym = sel.symbol
    if sym is not None:
        same = (result.symbol == sym) if not policy.symbol_loose_zero_match else (
            isinstance(result.symbol, str) and result.symbol.lstrip("0") == sym.lstrip("0"))
        if not same:
            reasons.append("symbol_mismatch")
            trusted = False
    last = series[-1] if series else None
    if trusted and last is not None:
        if not isinstance(result.last, AContractBar) or result.last.date != last.date:
            reasons.append("last_row_mismatch")
            trusted = False
        elif result.as_of != last.date:
            reasons.append("as_of_mismatch")
            trusted = False
        elif last.date > today.isoformat() and not policy.accept_future_date:
            reasons.append("trade_date_in_future")
            trusted = False
    close = last.close if (trusted and last is not None) else None
    trade_date = last.date if (trusted and last is not None) else None
    if policy.missing_close_as_zero and close is None:
        close = 0
    days = staleness_days(trade_date, today=today) if trade_date is not None else None
    is_stale = (days is not None and days > STALE_DAYS_DAILY) and not policy.ignore_stale
    fa = result.fetched_at
    if policy.fetched_at_from_trade_date and trade_date is not None and not isinstance(fa, str):
        fa = trade_date
    v = build_quote_view(sel, loaded=True, fetch_error=None, close=close, trade_date=trade_date, fetched_at=fa,
                         source=result.source, is_stale=is_stale)
    facts = None
    if (v.state in VALUE_BEARING or policy.facts_on_non_value_state) and series is not None:
        facts = compute_facts(series, policy)
        if facts is None:
            reasons.append("series_has_invalid_close")
    return BridgeOutput(v, facts, tuple(reasons))


# ════════════════════════════════════════════════════════════════════
# §2 案例矩陣（全部合成、離線）
# ════════════════════════════════════════════════════════════════════
def _weekdays_ending(end: str, n: int) -> list[str]:
    d = dt.date.fromisoformat(end)
    assert d.weekday() < 5, f"{end} 不是平日"
    out: list[str] = []
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d -= dt.timedelta(days=1)
    return out[::-1]


def make_bars(end: str, n: int = 60, last_close: float = 188.55, *, last_volume="auto") -> tuple[AContractBar, ...]:
    dates = _weekdays_ending(end, n)
    bars = []
    for i, d in enumerate(dates):
        back = n - 1 - i
        c = round(last_close - back * 0.25 - 0.1 * (back % 3), 2)
        vol = 1_000_000 + 1000 * i
        bars.append(AContractBar(d, round(c - 0.1, 2), round(c + 0.5, 2), round(c - 0.5, 2), c, vol))
    if last_volume != "auto":
        bars[-1] = dataclasses.replace(bars[-1], volume=last_volume)
    return tuple(bars)


FETCHED = "2026-11-25T09:30:00+08:00"
SRC = "FinMind:TaiwanStockPrice"


def make_result(symbol="0050", bars=None, *, end="2026-11-24", n=60, source=SRC, fetched_at=FETCHED, as_of="auto",
                last="auto", error=None, missing=None, **bar_kw) -> AContractResult:
    if bars is None:
        bars = make_bars(end, n, **bar_kw)
    if last == "auto":
        last = max(bars, key=lambda b: b.date) if bars else None
    if as_of == "auto":
        as_of = last.date if last is not None else None
    return AContractResult(symbol=symbol, bars=bars, last=last, source=source, as_of=as_of, fetched_at=fetched_at,
                           error=error, missing=missing)


def _with_last(bars, **kw):
    return tuple(bars[:-1]) + (dataclasses.replace(bars[-1], **kw),)


@dataclass(frozen=True)
class Case:
    id: str
    raw: object
    result: object
    state: S
    today: dt.date = TODAY
    reason_has: tuple[str, ...] = ()
    symbol: str | None = None               # 預期 view.symbol（SELECTION_INVALID 為 None）
    trade_date: str | None = None           # 預期（OK／STALE）
    fetched_text: str | None = None         # 預期 fetched_at_text（OK／STALE）
    value_text: str | None = None
    facts_none_fields: tuple[str, ...] = ()
    expect_facts: bool | None = None        # None＝OK／STALE 才有


def _cases() -> list[Case]:
    c: list[Case] = []
    A = c.append
    ok_kw = dict(trade_date="2026-11-24", fetched_text=f"抓取時間 {FETCHED}", value_text="188.55")
    # ── OK ＋ 前導零／大小寫 ──
    A(Case("ok_0050", "0050", make_result("0050"), S.OK, symbol="0050", **ok_kw))
    A(Case("ok_2330", "2330", make_result("2330"), S.OK, symbol="2330", **ok_kw))
    A(Case("ok_6code_00980A", "00980A", make_result("00980A"), S.OK, symbol="00980A", **ok_kw))
    A(Case("ok_lowercase_padded", " 00631l ", make_result("00631L"), S.OK, symbol="00631L", **ok_kw))
    # ── 選取無效（A 不應被呼叫，但即使給了結果也不得顯示）──
    for i, raw in enumerate(["abc!!", "", "   ", "23 30", "1234567", "50", "2330.TW", "２３３０", None, 50, b"0050"]):
        A(Case(f"invalid_{i}", raw, make_result("0050") if i % 2 else None, S.SELECTION_INVALID, symbol=None,
               expect_facts=False))
    # ── 讀取失敗（固定文案；原文不洩漏）──
    A(Case("fetch_failed_hostile_text", "0050", make_result(error=HOSTILE_ERROR), S.FETCH_FAILED, symbol="0050",
           reason_has=("fetch_failed",), expect_facts=False))
    A(Case("fetch_failed_beats_good_data", "0050", make_result(error="Timeout"), S.FETCH_FAILED, symbol="0050",
           expect_facts=False))
    # ── 未載入 ──
    A(Case("not_loaded", "0050", None, S.NOT_LOADED, symbol="0050", expect_facts=False))
    # ── 缺值（絕不 0、不補值）──
    bars = make_bars("2026-11-24")
    A(Case("missing_close_none", "0050", make_result(bars=_with_last(bars, close=None)), S.MISSING, symbol="0050",
           reason_has=("close_missing",)))
    for tag, bad in [("str", "N/A"), ("zero", 0), ("nan", float("nan")), ("neg", -1.0), ("bool", True)]:
        A(Case(f"missing_close_invalid_{tag}", "0050", make_result(bars=_with_last(bars, close=bad)), S.MISSING,
               symbol="0050", reason_has=("close_invalid",)))
    A(Case("missing_close_out_of_range", "0050", make_result(bars=_with_last(bars, close=0.001)), S.MISSING,
           symbol="0050", reason_has=("close_out_of_display_range",)))
    A(Case("missing_source_none", "0050", make_result(source=None), S.MISSING, symbol="0050",
           reason_has=("source_missing",)))
    A(Case("missing_source_newline", "0050", make_result(source="Fin\nMind"), S.MISSING, symbol="0050",
           reason_has=("source_invalid",)))
    A(Case("missing_a_reports_missing", "0050", make_result(bars=(), last=None, as_of=None, missing="no_rows"),
           S.MISSING, symbol="0050", reason_has=("close_missing", "trade_date_missing")))
    A(Case("missing_empty_series", "0050", make_result(bars=(), last=None, as_of=None), S.MISSING, symbol="0050",
           reason_has=("close_missing",)))
    A(Case("missing_a_flag_even_with_bars", "0050", make_result(missing="partial"), S.MISSING, symbol="0050"))
    A(Case("missing_as_of_none", "0050", make_result(as_of=None), S.MISSING, symbol="0050",
           reason_has=("trade_date_missing",)))
    A(Case("missing_as_of_differs_from_last_row", "0050", make_result(as_of="2026-11-20"), S.MISSING, symbol="0050"))
    A(Case("missing_last_row_not_latest", "0050", make_result(last=bars[-2]), S.MISSING, symbol="0050"))
    A(Case("missing_last_row_none", "0050", make_result(last=None), S.MISSING, symbol="0050"))
    A(Case("missing_symbol_zero_stripped", "0050", make_result(symbol="50"), S.MISSING, symbol="0050"))
    A(Case("missing_symbol_other", "0050", make_result(symbol="2330"), S.MISSING, symbol="0050"))
    dup = bars + (dataclasses.replace(bars[-1], close=1.0),)            # 同日兩列不同收盤
    A(Case("missing_duplicate_trade_dates", "0050", make_result(bars=dup), S.MISSING, symbol="0050"))
    A(Case("missing_bar_date_invalid", "0050", make_result(bars=_with_last(bars, date="2026-02-30")), S.MISSING,
           symbol="0050"))
    A(Case("missing_future_trade_date", "0050", make_result(end="2026-11-26"), S.MISSING, symbol="0050",
           reason_has=("trade_date_missing",)))
    # ── 過期（沿用 STALE_DAYS_DAILY=7；嚴格大於）──
    A(Case("stale_8_days", "0050", make_result(end="2026-11-17"), S.STALE, symbol="0050", trade_date="2026-11-17",
           fetched_text=f"抓取時間 {FETCHED}", value_text="188.55"))
    A(Case("fresh_7_days_boundary_is_ok", "0050", make_result(end="2026-11-18"), S.OK, symbol="0050",
           trade_date="2026-11-18", fetched_text=f"抓取時間 {FETCHED}", value_text="188.55"))
    sat = dt.date(2026, 11, 28)
    A(Case("saturday_after_friday_close_is_ok", "0050", make_result(end="2026-11-27", fetched_at="2026-11-28T10:00:00+08:00"),
           S.OK, today=sat, symbol="0050", trade_date="2026-11-27", fetched_text="抓取時間 2026-11-28T10:00:00+08:00",
           value_text="188.55"))
    A(Case("stale_beats_nothing_missing_beats_stale", "0050", make_result(bars=_with_last(make_bars("2026-11-10"), close=None)),
           S.MISSING, symbol="0050", reason_has=("close_missing",)))
    # ── fetched_at 與 trade_date 分離、不互相冒充 ──
    A(Case("fetched_at_none_is_unknown_not_trade_date", "0050", make_result(fetched_at=None), S.OK, symbol="0050",
           trade_date="2026-11-24", fetched_text=TEXT_FETCHED_AT_UNKNOWN, value_text="188.55"))
    A(Case("fetched_at_garbage_is_unknown", "0050", make_result(fetched_at="yesterday-ish"), S.OK, symbol="0050",
           trade_date="2026-11-24", fetched_text=TEXT_FETCHED_AT_UNKNOWN, value_text="188.55"))
    A(Case("fetched_at_date_only_ok", "0050", make_result(fetched_at="2026-11-25"), S.OK, symbol="0050",
           trade_date="2026-11-24", fetched_text="抓取時間 2026-11-25", value_text="188.55"))
    # ── 排序／量缺／短序列 ──
    shuffled = tuple(reversed(make_bars("2026-11-24")))
    A(Case("unsorted_bars_use_max_date", "0050", make_result(bars=shuffled), S.OK, symbol="0050", **ok_kw))
    A(Case("volume_missing_last_bar", "0050", make_result(last_volume=None), S.OK, symbol="0050",
           facts_none_fields=("last_volume", "volume_ratio5"), **ok_kw))
    A(Case("short_series_3_bars", "0050", make_result(n=3), S.OK, symbol="0050", trade_date="2026-11-24",
           fetched_text=f"抓取時間 {FETCHED}", value_text="188.55",
           facts_none_fields=("ma20", "rsi14", "volume_ratio5")))
    A(Case("series_19_bars_no_ma20", "0050", make_result(n=19), S.OK, symbol="0050", trade_date="2026-11-24",
           fetched_text=f"抓取時間 {FETCHED}", value_text="188.55", facts_none_fields=("ma20",)))
    mid = list(make_bars("2026-11-24"))
    mid[10] = dataclasses.replace(mid[10], close=None)
    A(Case("mid_series_invalid_close_view_ok_facts_none", "0050", make_result(bars=tuple(mid)), S.OK, symbol="0050",
           expect_facts=False, **ok_kw))
    return c


CASES = _cases()
CASE_IDS = [c.id for c in CASES]


# ════════════════════════════════════════════════════════════════════
# §3 逐案例驗收 ＋ 不變量（violations＝空 才算通過）
# ════════════════════════════════════════════════════════════════════
def _all_text(out: BridgeOutput) -> str:
    v = out.view
    parts = [v.chip_text, v.value_text, v.trade_date_text, v.fetched_at_text, v.source_text, v.notice_text, v.reason,
             v.symbol, repr(v), repr(out)]
    if out.facts is not None:
        parts += list(out.facts.lines())
    return "\n".join(p for p in parts if p)


def violations(case: Case, out: BridgeOutput) -> list[str]:
    v, bad = out.view, []
    if v.state is not case.state:
        bad.append(f"state {v.state} != {case.state}")
    for tok in case.reason_has:
        if tok not in (v.reason or ""):
            bad.append(f"reason 缺 {tok}：{v.reason!r}")
    if v.chip_text != CHIP_TEXT[v.state] or v.notice_text != NOTICE_TEXT[v.state]:
        bad.append("chip／notice 不是契約文案")
    if v.state in VALUE_BEARING:
        if v.value_text is None:
            bad.append("OK／STALE 沒有 value_text")
        if case.value_text is not None and v.value_text != case.value_text:
            bad.append(f"value_text {v.value_text!r}")
        if case.trade_date is not None and v.trade_date_text != f"交易日 {case.trade_date}":
            bad.append(f"trade_date_text {v.trade_date_text!r}")
        if case.fetched_text is not None and v.fetched_at_text != case.fetched_text:
            bad.append(f"fetched_at_text {v.fetched_at_text!r} != {case.fetched_text!r}")
        if v.fetched_at_text == f"抓取時間 {case.trade_date}" and case.fetched_text != v.fetched_at_text:
            bad.append("fetched_at 冒充 trade_date")
    else:
        if any(x is not None for x in (v.value_text, v.trade_date_text, v.fetched_at_text, v.source_text)):
            bad.append("非 OK／STALE 態帶了數值／日期／來源欄")
        if v.fact is not None:
            bad.append("非 OK／STALE 態有 fact")
    if v.symbol != case.symbol:
        bad.append(f"symbol {v.symbol!r} != {case.symbol!r}（前導零？）")
    want_facts = case.expect_facts if case.expect_facts is not None else (case.state in VALUE_BEARING)
    if want_facts != (out.facts is not None):
        bad.append(f"facts 存在性 {out.facts is not None} != {want_facts}")
    if out.facts is not None:
        for f in case.facts_none_fields:
            if getattr(out.facts, f) is not None:
                bad.append(f"facts.{f} 應為 None（不補 0）：{getattr(out.facts, f)!r}")
        txt = "\n".join(out.facts.lines())
        for w in FORBIDDEN_FACT_WORDS:
            if w in txt:
                bad.append(f"facts 含禁字 {w}")
        if "未還原權息" not in txt or "未換算" not in txt:
            bad.append("facts 缺限制揭露")
    blob = _all_text(out)
    for m in LEAK_MARKERS:
        if m in blob.replace(SRC, ""):          # 合法來源標籤 'FinMind:TaiwanStockPrice' 本身不算洩漏
            bad.append(f"輸出含敏感標記 {m!r}")
    if v.state in (S.MISSING, S.FETCH_FAILED, S.NOT_LOADED, S.SELECTION_INVALID) and "0.00" in blob:
        bad.append("非資料態出現 0.00")
    return bad


def _run(case: Case, policy: Policy = CORRECT) -> BridgeOutput:
    return bridge(case.raw, case.result, today=case.today, policy=policy)


@pytest.mark.parametrize("case", CASES, ids=CASE_IDS)
def test_case_matches_contract(case):
    assert violations(case, _run(case)) == []


def test_today_is_a_wednesday_and_bars_are_weekdays():
    assert TODAY.weekday() == 2
    assert all(dt.date.fromisoformat(b.date).weekday() < 5 for b in make_bars("2026-11-24", 60))


def test_all_six_states_are_covered_by_cases():
    assert {c.state for c in CASES} == set(S)


def test_case_ids_unique_and_no_skip_marks():
    assert len(set(CASE_IDS)) == len(CASE_IDS)
    src = pathlib.Path(__file__).read_text(encoding="utf-8")
    assert "pytest.mark.skip" + "(" not in src and "pytest.mark.xfail" + "(" not in src and "pytest.skip" + "(" not in src


def test_ok_detail_exact():
    out = _run(next(c for c in CASES if c.id == "ok_0050"))
    v = out.view
    assert (v.state, v.chip_text, v.value_text, v.reason, v.notice_text) == (S.OK, "資料正常", "188.55", None, None)
    assert v.trade_date_text == "交易日 2026-11-24" and v.fetched_at_text == f"抓取時間 {FETCHED}"
    assert v.source_text == f"來源 {SRC}" and v.symbol == "0050"
    assert v.fact is not None and v.fact.trade_date == "2026-11-24" and v.fact.fetched_at == FETCHED


def test_stale_shows_last_close_with_stale_chip():
    v = _run(next(c for c in CASES if c.id == "stale_8_days")).view
    assert (v.state, v.chip_text, v.value_text, v.notice_text) == (S.STALE, "資料過期", "188.55", "資料已過期，仍顯示最後收盤")


def test_stale_threshold_is_the_repo_ssot_not_a_local_number():
    """門檻取自 `shared.staleness.STALE_DAYS_DAILY`：資料日距預期最新交易日恰好＝門檻→OK，門檻+1→STALE（以日曆天、平日資料日）。"""
    assert STALE_DAYS_DAILY == 7        # 若 SSOT 變動，案例日期（11-18／11-17）須有意識改寫
    for end, want in [("2026-11-18", S.OK), ("2026-11-17", S.STALE)]:
        age = staleness_days(end, today=TODAY)
        assert (age > STALE_DAYS_DAILY) is (want is S.STALE), (end, age)
        assert bridge("0050", make_result(end=end), today=TODAY).view.state is want


def test_view_state_never_depends_on_volume():
    a = _run(next(c for c in CASES if c.id == "ok_0050")).view
    b = _run(next(c for c in CASES if c.id == "volume_missing_last_bar")).view
    assert a == b                                                    # 量是 facts 的事，不影響報價畫面狀態


def test_fetch_failed_text_is_fixed_and_tone_is_danger_not_grey():
    out = _run(next(c for c in CASES if c.id == "fetch_failed_hostile_text"))
    assert out.view.notice_text == "讀取失敗，請稍後再試" and out.view.tone.name == "DANGER"
    assert out.reasons == ("a_error",)                               # 橋不留任何原文


def test_selection_invalid_is_grey_not_red():
    out = _run(next(c for c in CASES if c.id == "invalid_0"))
    assert out.view.tone.name == "NEUTRAL_INFO" and out.view.symbol is None and out.view.reason is not None


def test_leading_zero_symbol_verbatim_and_never_numerified():
    out = _run(next(c for c in CASES if c.id == "ok_0050"))
    assert out.view.symbol == "0050" and out.view.fact.symbol == "0050"
    assert parse_ticker_input("0050").symbol == "0050" and parse_ticker_input("50").status is SelectionStatus.INVALID


# ════════════════════════════════════════════════════════════════════
# §4 有牙：每個『錯誤橋』必須被驗收判紅（且正確橋全綠）
# ════════════════════════════════════════════════════════════════════
MUTANTS = {
    "missing_close_as_zero": Policy(missing_close_as_zero=True),
    "ignore_stale": Policy(ignore_stale=True),
    "fetched_at_from_trade_date": Policy(fetched_at_from_trade_date=True),
    "leak_error_text": Policy(leak_error_text=True),
    "symbol_loose_zero_match": Policy(symbol_loose_zero_match=True),
    "accept_future_date": Policy(accept_future_date=True),
    "accept_duplicate_dates": Policy(accept_duplicate_dates=True),
    "skip_sort": Policy(skip_sort=True),
    "facts_zero_fill": Policy(facts_zero_fill=True),
    "facts_on_non_value_state": Policy(facts_on_non_value_state=True),
    "volume_none_as_zero": Policy(volume_none_as_zero=True),
}


def test_correct_bridge_has_zero_violations_across_all_cases():
    assert {c.id: violations(c, _run(c)) for c in CASES if violations(c, _run(c))} == {}


@pytest.mark.parametrize("name", sorted(MUTANTS))
def test_wrong_bridge_is_caught(name):
    pol = MUTANTS[name]
    caught = {c.id: v for c in CASES if (v := violations(c, _run(c, pol)))}
    assert caught, f"錯誤橋 {name} 沒有被任何案例抓到（驗收無牙）"


def test_mutant_set_covers_every_policy_knob():
    assert {f.name for f in dataclasses.fields(Policy)} == set(MUTANTS), "新增旋鈕必須同時新增對應的錯誤橋"
    for f in dataclasses.fields(Policy):
        assert getattr(CORRECT, f.name) is False


def test_missing_close_as_zero_is_not_hidden_by_quote_view_alone():
    """quote_view 會把 0 判成 close_invalid（仍 MISSING），所以狀態相同；有牙點在『原因』必須是 close_missing（缺值≠無效值）。"""
    case = next(c for c in CASES if c.id == "missing_close_none")
    bad = _run(case, Policy(missing_close_as_zero=True))
    assert bad.view.state is S.MISSING and "close_invalid" in bad.view.reason and "close_missing" not in bad.view.reason
    assert violations(case, bad) != []


# ════════════════════════════════════════════════════════════════════
# §5 序列／事實（C 側確定性：以 repo 既有真純函式計算）
# ════════════════════════════════════════════════════════════════════
def test_facts_equal_direct_calls_to_the_real_pure_functions():
    bars = make_bars("2026-11-24", 60)
    facts = bridge("0050", make_result(bars=bars), today=TODAY).facts
    df = pd.DataFrame({"close": [b.close for b in bars], "high": [b.high for b in bars], "low": [b.low for b in bars],
                       "volume": [float(b.volume) for b in bars]})
    assert facts.ma20 == pytest.approx(float(df["close"].rolling(20).mean().iloc[-1]))
    assert facts.rsi14 == calc_rsi(df, 14) and facts.volume_ratio5 == calc_volume_ratio(df, 5)
    assert facts.overextension_level == assess_price_overextension(df["close"])["level"]
    assert facts.n_bars == 60 and (facts.first_date, facts.last_date) == (bars[0].date, bars[-1].date)
    assert facts.rsi14 is not None and 0 <= facts.rsi14 <= 100 and facts.volume_ratio5 is not None


def test_facts_deterministic_regardless_of_input_order():
    bars = make_bars("2026-11-24", 40)
    a = bridge("0050", make_result(bars=bars), today=TODAY)
    b = bridge("0050", make_result(bars=tuple(reversed(bars))), today=TODAY)
    c = bridge("0050", make_result(bars=tuple(sorted(bars, key=lambda x: (hash(x.date) % 7, x.date)))), today=TODAY)
    assert a.facts == b.facts == c.facts and a.view == b.view == c.view
    assert "reordered_ascending" in b.reasons and "reordered_ascending" not in a.reasons


def test_insufficient_bars_give_none_never_zero_or_nan():
    for n, none_fields in [(1, ("ma20", "rsi14", "volume_ratio5")), (5, ("ma20", "rsi14", "volume_ratio5")),
                           (14, ("ma20", "rsi14")), (19, ("ma20",))]:
        f = bridge("0050", make_result(n=n), today=TODAY).facts
        assert f is not None and f.n_bars == n
        for name in none_fields:
            assert getattr(f, name) is None, (n, name)
        for name in ("ma20", "rsi14", "volume_ratio5"):
            val = getattr(f, name)
            assert val is None or (math.isfinite(val) and val != 0)
    assert bridge("0050", make_result(n=20), today=TODAY).facts.ma20 is not None
    assert bridge("0050", make_result(n=15), today=TODAY).facts.rsi14 is not None
    assert bridge("0050", make_result(n=3), today=TODAY).facts.overextension_level == "資料不足"


def test_volume_is_passed_through_in_source_units_not_converted():
    bars = make_bars("2026-11-24", 30, last_volume=12_345_678)
    f = bridge("0050", make_result(bars=bars), today=TODAY).facts
    assert f.last_volume == 12_345_678.0                              # NV：不 /1000、不 /1e8
    assert "12,345,678" in "\n".join(f.lines()) and "未換算" in "\n".join(f.limits)


def test_missing_volume_in_window_blocks_ratio_and_is_not_nan():
    bars = list(make_bars("2026-11-24", 30))
    bars[-3] = dataclasses.replace(bars[-3], volume=None)
    f = bridge("0050", make_result(bars=tuple(bars)), today=TODAY).facts
    assert f.volume_ratio5 is None and f.last_volume == float(bars[-1].volume)
    assert "資料不足" in "\n".join(f.lines())


def test_facts_disclose_limits_and_date_range_and_have_no_trade_words():
    f = bridge("0050", make_result(n=45), today=TODAY).facts
    txt = "\n".join(f.lines())
    assert "未還原權息" in txt and "僅 45 根日 K" in txt and f.first_date in txt and f.last_date in txt
    assert not [w for w in FORBIDDEN_FACT_WORDS if w in txt]


def test_overextension_level_words_are_descriptive_not_directive():
    levels = {assess_price_overextension(pd.Series([100.0 + i * i * 0.2 for i in range(40)]))["level"],
              assess_price_overextension(pd.Series([100.0] * 40))["level"],
              assess_price_overextension(pd.Series([100.0] * 5))["level"]}
    assert levels <= {"過熱", "偏熱", "正常", "資料不足"}
    assert not [w for lv in levels for w in FORBIDDEN_FACT_WORDS if w in lv]


@pytest.mark.parametrize("bad_close", [None, "x", 0, -3.0, float("nan"), float("inf"), True])
def test_any_invalid_close_in_series_blocks_facts_and_is_reported(bad_close):
    bars = list(make_bars("2026-11-24", 40))
    bars[7] = dataclasses.replace(bars[7], close=bad_close)
    out = bridge("0050", make_result(bars=tuple(bars)), today=TODAY)
    assert out.view.state is S.OK and out.facts is None and "series_has_invalid_close" in out.reasons


def test_facts_absent_on_every_non_value_state():
    for c in CASES:
        out = _run(c)
        if out.view.state not in VALUE_BEARING:
            assert out.facts is None, c.id


# ════════════════════════════════════════════════════════════════════
# §6 安全負控
# ════════════════════════════════════════════════════════════════════
def test_hostile_error_text_never_reaches_any_output():
    out = bridge("0050", make_result(error=HOSTILE_ERROR), today=TODAY)
    blob = _all_text(out)
    for m in LEAK_MARKERS:
        assert m not in blob, m
    assert out.view.state is S.FETCH_FAILED and out.view.reason == "fetch_failed" and out.facts is None


def test_hostile_source_with_control_chars_is_rejected_not_displayed():
    for src in ("FinMind\r\nSet-Cookie: x", "a" * 65, "   ", None, 123):
        out = bridge("0050", make_result(source=src), today=TODAY)
        assert out.view.state is S.MISSING and out.view.value_text is None, src


def test_leak_check_has_teeth():
    case = next(c for c in CASES if c.id == "fetch_failed_hostile_text")
    out = bridge(case.raw, case.result, today=case.today, policy=Policy(leak_error_text=True))
    assert any("敏感標記" in v for v in violations(case, out))


def test_no_token_or_secret_is_needed_by_the_bridge_signature():
    assert set(inspect.signature(bridge).parameters) == {"raw", "result", "today", "policy"}
    assert "token" not in {f.name for f in dataclasses.fields(AContractResult)}      # A 的 token 是呼叫參數，不是回傳欄位


def test_quote_view_signature_has_not_drifted_from_what_the_bridge_assumes():
    params = list(inspect.signature(build_quote_view).parameters)
    assert params == ["selection", "loaded", "fetch_error", "close", "trade_date", "fetched_at", "source", "is_stale"]
    assert {f.name for f in dataclasses.fields(QuoteView)} == {
        "state", "chip_text", "tone", "symbol", "value_text", "trade_date_text", "fetched_at_text", "source_text",
        "notice_text", "reason", "fact"}


def test_assumption_lists_exist_and_are_numbered():
    assert len(A_CONTRACT_ASSUMPTIONS) == 10 and all(a.startswith(f"A{i + 1} ") for i, a in enumerate(A_CONTRACT_ASSUMPTIONS))
    assert len(C_CONTRACT_ASSUMPTIONS) == 5 and all(a.startswith(f"C{i + 1} ") for i, a in enumerate(C_CONTRACT_ASSUMPTIONS))


# ════════════════════════════════════════════════════════════════════
# §7 與 UI2 既有接收層的接線事實（characterization；不改任何行為）
# ════════════════════════════════════════════════════════════════════
def _target_real_app(monkeypatch, *, calls: list) -> AppTest:
    """Real 模式 + 旗標開 + 標的頁。Real snapshot 以注入假值換掉 `read_real_snapshot`（不連網、不讀檔）。"""
    from src.services.ui2.real_canonical import RealFeedSnapshot
    snap = RealFeedSnapshot.of(None, "Exception", None, "Exception")
    monkeypatch.setattr("src.ui2.shell.app.read_real_snapshot", lambda: (calls.append(1), snap)[1])
    monkeypatch.setenv("UI2_LOOKUP_INPUT", "1")
    at = AppTest.from_file(str(ROOT / "app_ui2.py"), default_timeout=60)
    at.session_state["ui2_feed"] = "real"
    at.session_state["ui2_page"] = P4_TARGET
    at.run(timeout=60)
    assert not at.exception, at.exception
    return at


def _status_html(at: AppTest) -> list[str]:
    return [m.value for m in at.markdown if "ui2-lookup-status" in m.value]


def test_wiring_fact_current_input_shell_only_reaches_not_loaded_or_selection_invalid(monkeypatch, _offline):
    """【現況 characterization，非期望行為】現行輸入殼（`lookup_submission_view`，loaded=False 固定）**不取數**：
    任何輸入都只會得到 NOT_LOADED／SELECTION_INVALID，不產生 OK／STALE／MISSING／FETCH_FAILED。

    ⚠️ 待核准的正式接線（A／C 實作後、P2）完成時，本測試的『不取數』斷言須**有意識改寫**
    （那時「目前真行情未接」不再成立）；改寫而非刪除，並把 §1 的橋換成真 A／C。"""
    finmind_calls: list = []
    import src.data.core.finmind_client as FC
    monkeypatch.setattr(FC, "finmind_get", lambda *a, **k: (finmind_calls.append((a, k)), pd.DataFrame())[1])
    calls: list = []
    at = _target_real_app(monkeypatch, calls=calls)
    reads_after_load = len(calls)
    seen = {}
    for raw in ("0050", "2330", "00980A", "50", "abc!!", ""):
        at.text_input(key="ui2_lookup_text").set_value(raw)
        at.button[0].click().run(timeout=60)
        assert not at.exception, at.exception
        st_html = "".join(_status_html(at))
        seen[raw] = at.session_state["ui2_lookup_state"]
        html_all = "".join(m.value for m in at.markdown)
        for st in (S.OK, S.STALE, S.MISSING, S.FETCH_FAILED):
            assert st.value not in html_all, (raw, st)
            assert CHIP_TEXT[st] not in st_html, (raw, st)
        assert "188.55" not in html_all and "收盤價" not in st_html
    assert seen == {"0050": S.NOT_LOADED.value, "2330": S.NOT_LOADED.value, "00980A": S.NOT_LOADED.value,
                    "50": S.SELECTION_INVALID.value, "abc!!": S.SELECTION_INVALID.value, "": S.SELECTION_INVALID.value}
    assert finmind_calls == []                                        # 提交查詢不呼叫 FinMind
    assert _offline == []                                             # 也沒有任何連線嘗試
    assert reads_after_load >= 1                                      # Real snapshot 讀取是頁面本身的（與查詢無關）
    assert at.session_state["ui2_lookup_symbol"] == ""                # 最後一次是空字串＝無效


def test_wiring_fact_lookup_submission_view_is_the_only_receiver_and_never_loaded():
    from src.ui2.views.target import lookup_submission_view
    for raw in ("0050", "2330", " 00631l ", "abc", None):
        v = lookup_submission_view(raw)
        assert v.state in (S.NOT_LOADED, S.SELECTION_INVALID) and v.value_text is None
    # 同一個 selection 若改餵「已載入」資料，build_quote_view 會產出資料態——證明 P1 殼與契約之間唯一缺的是 A 的資料＋接線
    sel = parse_ticker_input("0050")
    ok = build_quote_view(sel, loaded=True, fetch_error=None, close=188.55, trade_date="2026-11-24",
                          fetched_at=FETCHED, source=SRC, is_stale=False)
    assert ok.state is S.OK and lookup_submission_view("0050").state is S.NOT_LOADED


def test_wiring_fact_a_and_c_functions_do_not_exist_yet_so_the_bridge_inputs_are_test_local():
    """A／C 現在不存在（origin/main da6f901）。若日後有人建立同名模組，提醒 P 收斂時把 §1 的測試內契約換成真型別／真函式。
    ⚠️ 模組路徑是**猜測**（A／C 的實際檔名未定）：這只是 best-effort 提醒，不是對『A／C 不存在』的全稱證明。"""
    import importlib.util
    for mod in ("src.data.stock.stock_latest_ohlcv", "src.services.stock_research_facts",
                "src.compute.stock.stock_research_facts"):
        try:
            found = importlib.util.find_spec(mod) is not None
        except ModuleNotFoundError:
            found = False
        assert found is False, f"{mod} 已存在：請以真函式替換測試內的 A 契約／compute_facts 替身（見 *_CONTRACT_ASSUMPTIONS）"
