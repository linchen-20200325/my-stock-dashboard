"""M2 個股查詢「B 線」：UI2 離線整合接收測試（tests-only；零網路、零 secrets、不落盤）。

授權：#1199 R23.38（comment 7216622932）B 項；P-M2b 介面核對（comment 7216937148）。
⛔ 本檔不改任何 production 檔、守衛、旗標；不造 FAKE 畫面；**不 import 尚未合併的模組**（#1289／#1290 在 main 上不存在，
   本檔必須在 main 基底獨立可跑），故以「測試內替身」對映真 API，並逐處註明對應的 head 與行號。

═══ 驗證的資料流 ═══
`fetch_stock_latest_ohlcv`（A，#1289）→ **接收橋 `bridge()`（本檔，僅存在於測試）** → `build_quote_view`（B，既有）→ `QuoteView`
                                    └→ rows→DataFrame 小橋 `rows_to_frame()` → 事實（C，#1290；本檔以既有真純函式組成的替身）
- A 側替身：`OhlcvRow`／`StockLatestOhlcv`／`STATE_*`（形狀對映 #1289 head 56ce53be
  `src/data/stock/stock_latest_ohlcv.py` L106-111〔狀態〕、L156-164〔OhlcvRow〕、L167-192〔StockLatestOhlcv〕、L83〔source〕）。
- C 側替身：`FactsStandIn`（欄位名對映 #1290 head 7877f534 `src/compute/strategy/stock_research_facts.py` L132-150）；
  數值由 repo **既有真純函式**算（`calc_ma_series`／`calc_rsi`／`calc_volume_ratio`／`assess_price_overextension`）。
  C 的**真**函式只在 scratch 疊加 PR 檔案時驗證（不入庫、不進此檔；見回報）。
- 待 #1289／#1290 合併後：§7 的 `test_wiring_fact_a_and_c_modules_not_in_main_yet` 會**有意轉紅**，提醒把替身換成真 import。

═══ 契約依據 ═══
- `shared/ui2_contract/quote_view.py`：`QuoteViewState` L48-54；`CHIP_TEXT`／`NOTICE_TEXT` L61-84；`build_quote_view` L189-225
  （優先序 L12-13；`fetch_error` 原文不進輸出 L22-23；`fetched_at` 缺／不可辨識→「抓取時間未知」L24-25；**無時鐘**，`is_stale` 由呼叫端傳入 L26；
  `trade_date`／`fetched_at`／`close`／`source` 全是**字串／float 契約**，`date`／`datetime` 物件不被接受）。
- `shared/ui2_contract/target_selection.py::parse_ticker_input`：只 strip＋upper、不補零不去零。
- `src/ui2/views/target.py::lookup_submission_view` L31-34：現行唯一接收層，`loaded=False` 固定（P1；DEC-223：不接資料）。
- wireframe `docs/vnext/NEWUI2_TARGET_LOOKUP_QUOTE_WIREFRAME_2026-11-21.md` §5 六態表；DEC-221／DEC-223。
- 過期門檻：`shared/staleness.py::STALE_DAYS_DAILY`（=7）＋`staleness_days`（日曆天、週末往前退）。本檔**不自訂門檻**。

═══ A 狀態 → B 的映射表（P-M2b；後續 L3 沿用同一表，不得另寫）═══
| A state        | B 呼叫                                            | B 結果                                   |
| ok             | loaded=True, close=latest.close, trade_date=as_of.isoformat(), fetched_at=fetched_at.isoformat(), source | OK（或 STALE：is_stale 由呼叫端注入） |
| no_data        | loaded=True, close=None                            | MISSING（語意＝無資料或無法區分，不稱下市／查無此股） |
| fetch_failed   | fetch_error=<固定非 None>                          | FETCH_FAILED（紅、固定句）                |
| invalid_data   | loaded=True, close=None                            | MISSING（**不得 OK、不得 FETCH_FAILED**） |
| invalid_symbol | 不呼叫 A（`parse_ticker_input` 先擋）               | SELECTION_INVALID                         |

═══ 結構 ═══
§1 A 替身與橋　§2 案例矩陣　§3 逐案例驗收＋不變量　§4 映射表／型別負控　§5 有牙（錯誤橋必須判紅）　§6 事實（C 側）／安全　§7 接線事實（AppTest）
"""
from __future__ import annotations

import dataclasses
import datetime as dt
import inspect
import math
import pathlib
import socket
from dataclasses import dataclass

import numpy as np
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

#: 測試用「今日」（台北日）：2026-11-25 為週三（§3 釘死）；橋與被測函式皆不讀系統時鐘。
TODAY = dt.date(2026, 11, 25)

# 每條標註：【驗證】＝已對照 #1289／#1290 head 的原始碼確認；【假設】＝仍未對真實回應／真 L3 驗證。
A_CONTRACT_ASSUMPTIONS = (
    "A1【驗證 #1289 56ce53be L167-192】回傳單一不可變物件 StockLatestOhlcv：state/symbol/rows/latest/as_of/fetched_at/source/"
    "authenticated/error_code/reasons/n_rows。（原假設的 bars→rows、last→latest；**沒有** error／missing 兩欄。）",
    "A2【驗證 L106-111】狀態五值 ok/no_data/fetch_failed/invalid_symbol/invalid_data。『error vs missing 分離』改由 state 表達："
    "fetch_failed＝確定失敗；no_data＝查無或無法區分（A 自述不聲稱下市）；invalid_data＝資料不可信。",
    "A3【驗證 L113-118、L385-391】error_code 是固定短碼（invalid_symbol/no_data/fetch_exception/fetch_transient/invalid_data），"
    "不含例外原文。橋仍**不回顯**它（縱深防禦；測試以惡意 error_code 驗證）。",
    "A4【驗證 L156-164】OhlcvRow.volume_shares 為 FinMind 原始成交量、未換算；**不會是 None**（缺值→invalid_data）。"
    "單位（股／張）仍 NV（A 自述 L21-22）。（原假設『volume 可為 None』作廢。）",
    "A5【驗證 L18、L121-122(C)】價格為原始未調整價；C 的 limitations 揭露此限制。",
    "A6【驗證 L402-406】OK 時 latest＝rows[-1]、as_of＝latest.date。橋仍驗證（縱深防禦）：不一致→MISSING。",
    "A7【驗證 L47-49、L289-296】A **不排序**：亂序／重複日期一律 invalid_data。（原假設『橋排序』作廢——橋改為拒絕非嚴格遞增，不排序。）",
    "A8【驗證 L83】source＝'FinMind:TaiwanStockPrice:raw_http'（固定常數；原假設字串已更正）。",
    "A9【驗證 L293-294】A 以台北日 today 判未來日（invalid_data）。橋再以注入的 today 檢查一次（縱深防禦）。",
    "A10【假設】過期＝staleness_days(as_of, today) > STALE_DAYS_DAILY（嚴格大於）；A **不判過期**（L7），由 L3 以台北日判並注入。",
    "A11【驗證 L371-372、L145-146 等】as_of 是 datetime.date、fetched_at 是 tz-aware UTC datetime；B 只收 ISO 字串→轉字串是橋接責任"
    "（§4 型別負控以實測鎖死）。",
    "A12【驗證 L329-337】簽名 fetch_stock_latest_ohlcv(stock_id, *, token='', lookback_days=400, today=None, now=None, timeout=20)；"
    "空 token 不被擋（authenticated=False）。缺 token 的 400/401/403 落 no_data（與查無不可分）→UI 文案不得稱『查無此股』。",
    "A13【假設，NV】FinMind 真實回應列形（停牌／無成交列 O=H=L=0）會使整段 invalid_data（A 自述 L55-56；P-M2b R-I1）。",
)
C_CONTRACT_ASSUMPTIONS = (
    "C1【驗證 #1290 7877f534 L239-340】入口 build_stock_research_facts(bars: DataFrame, *, as_of: str|date) -> StockResearchFacts；"
    "bars 小寫 open/high/low/close/volume、DatetimeIndex 嚴格遞增、as_of 必須＝最後一列日期（不符 raise）。",
    "C2【驗證 L132-150】輸出欄位 as_of/bar_count/first_date/price_basis/close/ma{5,20,60,120,240}/rsi14/volume_ratio5/bias20_pct/"
    "overextension_level/overheated/support_20d/resistance_20d/support_resistance_bars/limitations。本檔替身只實作其中**不依賴**"
    "支撐壓力的子集（support／resistance 由 scratch 驗證真函式）。",
    "C3【驗證 L26-38、L270-277】根數不足→None（不是 0）；全平盤 RSI 無定義→None＋limitation（不輸出 0.0）；過熱判定同步 None。",
    "C4【驗證 L121-125】limitations 一律含『價格為未調整原始價』『均線為參考』；不含買賣／目標／停損字樣。",
    "C5【驗證 L196-230】結構性壞輸入（NaN/inf、價 ≤0、high<low、volume<0、非遞增、as_of 不符）→ raise StockResearchFactsInputError；"
    "volume==0 合法。橋只在 A=ok（A 已驗證）時才呼叫 C。",
    "C6【假設】C 在 pandas 2.x 的行為未實測（C 自述 L47-50，本環境只有 3.x）。",
)

SECRET = "SECRET123"
HOSTILE_CODE = (f"HTTPError: https://api.finmindtrade.com/api/v4/data?dataset=TaiwanStockPrice&token={SECRET} "
                f"Authorization: Bearer {SECRET} FINMIND_TOKEN=/home/x/.env")
LEAK_MARKERS = (SECRET, "FINMIND", "Bearer", "token", "http", "Authorization", "/home/")
FORBIDDEN_FACT_WORDS = ("買進", "賣出", "加碼", "減碼", "目標價", "目標", "停損", "停利", "進場", "出場", "建議買", "建議賣")
FORBIDDEN_MISSING_WORDS = ("查無此股", "下市", "不存在", "無此股票")     # no_data 語意＝無資料或無法區分，不得斷言標的不存在


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
# §1 A 側替身（形狀對映 #1289）與接收橋
# ════════════════════════════════════════════════════════════════════
STATE_OK, STATE_NO_DATA, STATE_FETCH_FAILED = "ok", "no_data", "fetch_failed"          # 對映 #1289 L106-108
STATE_INVALID_SYMBOL, STATE_INVALID_DATA = "invalid_symbol", "invalid_data"             # 對映 L109-110
ALL_A_STATES = (STATE_OK, STATE_NO_DATA, STATE_FETCH_FAILED, STATE_INVALID_SYMBOL, STATE_INVALID_DATA)
SRC = "FinMind:TaiwanStockPrice:raw_http"                                               # 對映 L83
FETCHED_DT = dt.datetime(2026, 11, 25, 1, 30, tzinfo=dt.timezone.utc)                   # 台北 09:30；A 的 fetched_at 為 UTC aware
FETCHED_ISO = "2026-11-25T01:30:00+00:00"


@dataclass(frozen=True)
class OhlcvRow:
    """對映 #1289 L156-164（date 是 datetime.date；量欄名 volume_shares）。型別刻意不強制：橋必須不信任。"""
    date: object
    open: object
    high: object
    low: object
    close: object
    volume_shares: object


@dataclass(frozen=True)
class StockLatestOhlcv:
    """對映 #1289 L167-192。"""
    state: object
    symbol: object
    rows: object
    latest: object
    as_of: object
    fetched_at: object
    source: object
    authenticated: object
    error_code: object
    reasons: object
    n_rows: object


@dataclass(frozen=True)
class FactsStandIn:
    """C 的測試內替身（欄位名對映 #1290 L132-150；support／resistance 不在替身內）。"""
    as_of: dt.date
    bar_count: int
    first_date: dt.date
    price_basis: str
    close: float
    ma: dict
    rsi14: float | None
    volume_ratio5: float | None
    bias20_pct: float | None
    overextension_level: str | None
    overheated: bool | None
    last_volume_shares: float
    limitations: tuple[str, ...]

    def lines(self) -> tuple[str, ...]:
        def f(x, spec=".2f"):
            return "資料不足" if x is None else format(x, spec)
        return (f"日 K {self.bar_count} 根（{self.first_date}～{self.as_of}）",
                *(f"MA{w} {f(v)}" for w, v in self.ma.items()),
                f"RSI14 {f(self.rsi14, '.1f')}", f"量比(5日) {f(self.volume_ratio5)}", f"乖離20 {f(self.bias20_pct)}",
                f"位階 {self.overextension_level or '不判定'}",
                f"成交量原值 {self.last_volume_shares:,.0f}", *self.limitations)


@dataclass(frozen=True)
class BridgeOutput:
    view: QuoteView
    facts: FactsStandIn | None
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class Policy:
    """橋的『旋鈕』：預設＝正確行為。§5 每個旋鈕翻一個＝一個錯誤橋，必須被驗收判紅。"""
    missing_close_as_zero: bool = False
    ignore_stale: bool = False
    fetched_at_from_trade_date: bool = False
    leak_error_text: bool = False
    symbol_loose_zero_match: bool = False
    accept_future_date: bool = False
    accept_unsorted_rows: bool = False
    facts_zero_fill: bool = False
    facts_on_non_value_state: bool = False
    facts_flat_rsi_zero: bool = False
    invalid_data_as_fetch_failed: bool = False
    no_data_as_fetch_failed: bool = False
    pass_date_objects: bool = False
    close_as_numpy_scalar: bool = False
    call_fetch_on_invalid_symbol: bool = False


CORRECT = Policy()
#: 窗口（交易日根數）：C 的 MA 視窗＝#1290 L110
MA_WINDOWS = (5, 20, 60, 120, 240)
LIMITATION_UNADJUSTED = "價格為未調整原始價，除權息日前後指標可能失真。"        # 對映 #1290 L121
LIMITATION_MA_REFERENCE = "均線為參考，不等於正式台股趨勢判斷。"                # 對映 L122


_ROW_FIELDS = ("date", "open", "high", "low", "close", "volume_shares")


def _is_row(r) -> bool:
    """以欄位（duck typing）判斷是否為 OhlcvRow 形狀——不綁測試內替身的類別，日後換成 #1289 真 `OhlcvRow` 時橋不必改。"""
    return all(hasattr(r, f) for f in _ROW_FIELDS)


def _is_date(x) -> bool:
    return isinstance(x, dt.date) and not isinstance(x, dt.datetime)


def rows_to_frame(rows) -> pd.DataFrame:
    """rows→DataFrame 小橋（P-M2b #1：A 在 head 56ce53be 沒有 `to_bars_frame`，故寫在測試內）：
    `volume_shares→volume` 原值不換算、index＝`DatetimeIndex(name='date')`、欄全小寫。非遞增／空 → ValueError（不排序）。"""
    if not rows:
        raise ValueError("rows 為空")
    idx = pd.DatetimeIndex([pd.Timestamp(r.date) for r in rows], name="date")
    df = pd.DataFrame({"open": [float(r.open) for r in rows], "high": [float(r.high) for r in rows],
                       "low": [float(r.low) for r in rows], "close": [float(r.close) for r in rows],
                       "volume": [float(r.volume_shares) for r in rows]}, index=idx)
    if not idx.is_monotonic_increasing or not idx.is_unique:
        raise ValueError("rows 非嚴格遞增")
    return df


def build_facts_standin(rows, as_of: dt.date, policy: Policy) -> FactsStandIn:
    """C 替身：同一組 rows → 既有真純函式。不足→None；全平盤 RSI→None（對映 #1290 L270-277）。"""
    df = rows_to_frame(rows)
    if df.index[-1].date() != as_of:
        raise ValueError("as_of 與最後一列日期不符")           # 對映 C 的 raise（#1290 L248-250）
    n = len(df)
    close = df["close"]
    ma = {}
    for w in MA_WINDOWS:
        v = calc_ma_series(close, w).iloc[-1] if n >= w else None
        ma[w] = round(float(v), 4) if v is not None and pd.notna(v) else None
    rsi_undefined = n >= 15 and not (close.diff().abs() > 0).any()
    rsi = None if n < 15 or rsi_undefined else calc_rsi(df, 14)
    if rsi_undefined and policy.facts_flat_rsi_zero:
        rsi = calc_rsi(df, 14)                                # 錯誤橋：採用真 kernel 的偽值 0.0
    vr = calc_volume_ratio(df, 5) if n >= 6 else None
    bias = level = overheated = None
    if n >= 21:
        oe = assess_price_overextension(close)
        bias = round(float(oe["bias_pct"]), 4) if oe["bias_pct"] is not None else None
        if not rsi_undefined:
            level, overheated = str(oe["level"]), bool(oe["overheated"])
    if policy.facts_zero_fill:                                # 錯誤橋：不足補 0
        ma = {w: (0.0 if v is None else v) for w, v in ma.items()}
        rsi, vr, bias = (0.0 if x is None else x for x in (rsi, vr, bias))
    lim = [LIMITATION_UNADJUSTED, LIMITATION_MA_REFERENCE]
    short = [f"MA{w}" for w, v in ma.items() if v is None]
    if short:
        lim.append("下列指標根數不足而無法計算：" + "、".join(short) + "。")
    return FactsStandIn(as_of=as_of, bar_count=n, first_date=df.index[0].date(), price_basis="unadjusted",
                        close=round(float(close.iloc[-1]), 4), ma=ma, rsi14=rsi, volume_ratio5=vr, bias20_pct=bias,
                        overextension_level=level, overheated=overheated,
                        last_volume_shares=float(df["volume"].iloc[-1]), limitations=tuple(lim))


def _rows_trusted(result, sym, today: dt.date, policy: Policy) -> tuple[bool, list[str]]:
    """A=ok 時的縱深防禦驗證（A 已驗證過；橋不假設 A 永遠正確）。"""
    bad: list[str] = []
    rows = result.rows
    if not isinstance(rows, tuple) or len(rows) == 0 or any(not _is_row(r) for r in rows):
        return False, ["rows_invalid"]
    if any(not _is_date(r.date) for r in rows):
        bad.append("row_date_not_date")
    else:
        ds = [r.date for r in rows]
        if not policy.accept_unsorted_rows and any(b <= a for a, b in zip(ds, ds[1:])):
            bad.append("rows_not_strictly_ascending")          # 不排序、不去重（A 也不排序）
        if ds and ds[-1] > today and not policy.accept_future_date:
            bad.append("trade_date_in_future")
    same = (result.symbol == sym) if not policy.symbol_loose_zero_match else (
        isinstance(result.symbol, str) and sym is not None and result.symbol.lstrip("0") == sym.lstrip("0"))
    if sym is None or not same:
        bad.append("symbol_mismatch")
    if not bad:
        if result.latest is not rows[-1] and result.latest != rows[-1]:
            bad.append("latest_not_last_row")
        elif result.as_of != rows[-1].date:
            bad.append("as_of_mismatch")
        elif result.n_rows != len(rows):
            bad.append("n_rows_mismatch")
    return (not bad), bad


def bridge(raw, result, *, today: dt.date, policy: Policy = CORRECT) -> BridgeOutput:
    """A（StockLatestOhlcv 或 None）→ `build_quote_view` 輸入 →（OK／STALE 時）事實。純函式；today 由呼叫端注入。
    未知 state → ValueError（Fail Loud；不靜默當成任何一態）。"""
    sel = parse_ticker_input(raw)
    reasons: list[str] = []

    def view(**kw):
        base = dict(loaded=True, fetch_error=None, close=None, trade_date=None, fetched_at=None, source=None, is_stale=False)
        base.update(kw)
        return build_quote_view(sel, **base)

    if result is None:                                          # 尚未查詢（含：選取無效時 A 根本沒被呼叫）
        return BridgeOutput(view(loaded=False), None, ())
    if result.state not in ALL_A_STATES:
        raise ValueError(f"未知的 A state：{result.state!r}")
    if result.state == STATE_INVALID_SYMBOL:                    # A 說代號無效 → 一律 SELECTION_INVALID，絕不顯示資料
        v = build_quote_view(parse_ticker_input(None), loaded=False, fetch_error=None, close=None, trade_date=None,
                             fetched_at=None, source=None, is_stale=False) if sel.status is SelectionStatus.SELECTED \
            else view(loaded=False)
        return BridgeOutput(v, None, ("a_invalid_symbol",))
    if result.state == STATE_FETCH_FAILED:
        reasons.append(str(result.error_code) if policy.leak_error_text else "a_fetch_failed")
        return BridgeOutput(view(fetch_error="fetch_failed"), None, tuple(reasons))
    if result.state in (STATE_NO_DATA, STATE_INVALID_DATA):
        reasons.append("a_" + result.state)
        if result.state == STATE_INVALID_DATA and policy.invalid_data_as_fetch_failed:
            return BridgeOutput(view(fetch_error="fetch_failed"), None, tuple(reasons))
        if result.state == STATE_NO_DATA and policy.no_data_as_fetch_failed:
            return BridgeOutput(view(fetch_error="fetch_failed"), None, tuple(reasons))
        close = 0 if policy.missing_close_as_zero else None
        return BridgeOutput(view(close=close, source=result.source), None, tuple(reasons))

    # ── state == ok ──
    trusted, bad = _rows_trusted(result, sel.symbol, today, policy)
    reasons += bad
    last = result.latest if trusted else None
    close = None if last is None else last.close
    td = None if last is None else last.date
    if policy.close_as_numpy_scalar and close is not None and isinstance(close, float):
        close = np.float32(close)         # 錯誤橋：傳 numpy 純量（非 float 子類）
    if td is not None and policy.pass_date_objects:
        trade_date, fa = td, result.fetched_at
    else:
        trade_date = td.isoformat() if td is not None else None
        fa = result.fetched_at
        if isinstance(fa, dt.datetime) and fa.tzinfo is not None and fa.utcoffset() is not None:
            fa = fa.isoformat()
        else:
            fa = None                                          # naive／非 datetime → 抓取時間未知（不以交易日冒充）
    if policy.fetched_at_from_trade_date and td is not None:
        fa = td.isoformat()
    days = staleness_days(td, today=today) if td is not None else None
    is_stale = bool(days is not None and days > STALE_DAYS_DAILY) and not policy.ignore_stale
    v = view(close=close, trade_date=trade_date, fetched_at=fa, source=result.source, is_stale=is_stale)
    facts = None
    if (v.state in VALUE_BEARING or policy.facts_on_non_value_state) and isinstance(result.rows, tuple) and result.rows:
        try:
            facts = build_facts_standin(result.rows, result.rows[-1].date, policy)
        except (ValueError, TypeError):
            reasons.append("facts_unavailable")
    return BridgeOutput(v, facts, tuple(reasons))


@dataclass
class FetchSpy:
    """假 A：記錄呼叫次數與參數；回傳預先指定的結果。"""
    result: object
    calls: list

    def __call__(self, stock_id, **kw):
        self.calls.append((stock_id, kw))
        return self.result


def lookup(raw, fetch, *, today: dt.date, token: str = "", policy: Policy = CORRECT) -> BridgeOutput:
    """L3 形的最小編排（測試內）：先 parse → 選取有效才呼叫 A（symbol 原樣、token 以 keyword）→ 橋。"""
    sel = parse_ticker_input(raw)
    if sel.status is not SelectionStatus.SELECTED and not policy.call_fetch_on_invalid_symbol:
        return bridge(raw, None, today=today, policy=policy)
    res = fetch(sel.symbol if sel.symbol is not None else raw, token=token)
    return bridge(raw, res, today=today, policy=policy)


# ════════════════════════════════════════════════════════════════════
# §2 案例矩陣（全部合成、離線）
# ════════════════════════════════════════════════════════════════════
def _weekdays_ending(end: str, n: int) -> list[dt.date]:
    d = dt.date.fromisoformat(end)
    assert d.weekday() < 5, f"{end} 不是平日"
    out: list[dt.date] = []
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d -= dt.timedelta(days=1)
    return out[::-1]


def make_rows(end: str, n: int = 60, last_close: float = 188.55) -> tuple[OhlcvRow, ...]:
    rows = []
    for i, d in enumerate(_weekdays_ending(end, n)):
        back = n - 1 - i
        c = round(last_close - back * 0.25 - 0.1 * (back % 3), 2)
        rows.append(OhlcvRow(d, round(c - 0.1, 2), round(c + 0.5, 2), round(c - 0.5, 2), c, 1_000_000.0 + 1000 * i))
    return tuple(rows)


def make_ok(symbol="0050", rows=None, *, end="2026-11-24", n=60, source=SRC, fetched_at=FETCHED_DT, as_of="auto",
            latest="auto", n_rows="auto", **kw) -> StockLatestOhlcv:
    rows = make_rows(end, n, **kw) if rows is None else rows
    if latest == "auto":
        latest = rows[-1] if rows else None
    if as_of == "auto":
        as_of = latest.date if latest is not None else None
    if n_rows == "auto":
        n_rows = len(rows)
    return StockLatestOhlcv(STATE_OK, symbol, rows, latest, as_of, fetched_at, source, True, None, (), n_rows)


def make_empty(state, symbol="0050", *, error_code=None, reasons=(), authenticated=True, fetched_at=FETCHED_DT):
    """A 非 OK 的回傳形狀（#1289 `_empty` L253-258）：rows=()、latest／as_of=None、n_rows=0。"""
    return StockLatestOhlcv(state, None if state == STATE_INVALID_SYMBOL else symbol, (), None, None, fetched_at, SRC,
                            authenticated, error_code, reasons, 0)


def _with_latest(rows, **kw):
    new = dataclasses.replace(rows[-1], **kw)
    return tuple(rows[:-1]) + (new,)


@dataclass(frozen=True)
class Case:
    id: str
    raw: object
    result: object
    state: S
    today: dt.date = TODAY
    reason_has: tuple[str, ...] = ()
    symbol: str | None = None               # 預期 view.symbol
    trade_date: str | None = None
    fetched_text: str | None = None
    value_text: str | None = None
    facts_none: tuple[str, ...] = ()        # 預期為 None 的 facts 欄位（ma 以 'ma5' 形式）
    expect_facts: bool | None = None        # None＝OK／STALE 才有


def _cases() -> list[Case]:
    c: list[Case] = []
    A = c.append
    ok_kw = dict(trade_date="2026-11-24", fetched_text=f"抓取時間 {FETCHED_ISO}", value_text="188.55")
    A(Case("ok_0050", "0050", make_ok("0050"), S.OK, symbol="0050", **ok_kw))
    A(Case("ok_2330", "2330", make_ok("2330"), S.OK, symbol="2330", **ok_kw))
    A(Case("ok_6code_00980A", "00980A", make_ok("00980A"), S.OK, symbol="00980A", **ok_kw))
    A(Case("ok_lowercase_padded", " 00631l ", make_ok("00631L"), S.OK, symbol="00631L", **ok_kw))
    for i, raw in enumerate(["abc!!", "", "   ", "23 30", "1234567", "50", "2330.TW", "２３３０", None, 50, b"0050"]):
        A(Case(f"invalid_{i}", raw, None if i % 2 == 0 else make_ok("0050"), S.SELECTION_INVALID, symbol=None,
               expect_facts=False))
    A(Case("a_invalid_symbol_state", "0050", make_empty(STATE_INVALID_SYMBOL, error_code="invalid_symbol"),
           S.SELECTION_INVALID, symbol=None, expect_facts=False))
    A(Case("fetch_failed_transient", "0050", make_empty(STATE_FETCH_FAILED, error_code="fetch_transient"),
           S.FETCH_FAILED, symbol="0050", reason_has=("fetch_failed",), expect_facts=False))
    A(Case("fetch_failed_exception", "0050", make_empty(STATE_FETCH_FAILED, error_code="fetch_exception"),
           S.FETCH_FAILED, symbol="0050", expect_facts=False))
    A(Case("fetch_failed_hostile_error_code", "0050", make_empty(STATE_FETCH_FAILED, error_code=HOSTILE_CODE),
           S.FETCH_FAILED, symbol="0050", reason_has=("fetch_failed",), expect_facts=False))
    A(Case("not_loaded", "0050", None, S.NOT_LOADED, symbol="0050", expect_facts=False))
    # ── A 非 OK → MISSING（no_data／invalid_data）──
    A(Case("no_data", "0050", make_empty(STATE_NO_DATA, error_code="no_data"), S.MISSING, symbol="0050",
           reason_has=("close_missing", "trade_date_missing"), expect_facts=False))
    A(Case("no_data_unauthenticated", "0050", make_empty(STATE_NO_DATA, error_code="no_data", authenticated=False),
           S.MISSING, symbol="0050", expect_facts=False))
    A(Case("invalid_data_close_outside_range", "0050", make_empty(STATE_INVALID_DATA, error_code="invalid_data",
                                                                  reasons=("close_outside_low_high",)),
           S.MISSING, symbol="0050", reason_has=("close_missing",), expect_facts=False))
    A(Case("invalid_data_many_reasons", "0050", make_empty(STATE_INVALID_DATA, error_code="invalid_data",
                                                           reasons=("date_not_ascending", "volume_shares_missing")),
           S.MISSING, symbol="0050", expect_facts=False))
    # ── A=ok 但橋縱深防禦判不可信 → MISSING ──
    rows = make_rows("2026-11-24")
    A(Case("def_symbol_zero_stripped", "0050", make_ok("50"), S.MISSING, symbol="0050", reason_has=("trade_date_missing",),
           expect_facts=False))
    A(Case("def_symbol_other", "0050", make_ok("2330"), S.MISSING, symbol="0050", expect_facts=False))
    A(Case("def_latest_none", "0050", make_ok(latest=None), S.MISSING, symbol="0050", expect_facts=False))
    A(Case("def_latest_not_last_row", "0050", make_ok(latest=rows[-2], as_of=rows[-2].date), S.MISSING, symbol="0050",
           expect_facts=False))
    A(Case("def_as_of_none", "0050", make_ok(as_of=None), S.MISSING, symbol="0050", expect_facts=False))
    A(Case("def_as_of_differs", "0050", make_ok(as_of=dt.date(2026, 11, 20)), S.MISSING, symbol="0050", expect_facts=False))
    A(Case("def_n_rows_mismatch", "0050", make_ok(n_rows=3), S.MISSING, symbol="0050", expect_facts=False))
    A(Case("def_rows_empty_but_ok", "0050", make_ok(rows=(), latest=None), S.MISSING, symbol="0050", expect_facts=False))
    A(Case("def_rows_reversed", "0050", make_ok(rows=tuple(reversed(rows)), latest=rows[-1], as_of=rows[-1].date),
           S.MISSING, symbol="0050", expect_facts=False))
    swapped = rows[:10] + (rows[11], rows[10]) + rows[12:]          # 中段兩列對調；末列仍是最新日 → latest／as_of 一致
    A(Case("def_rows_unsorted_in_middle", "0050", make_ok(rows=swapped), S.MISSING, symbol="0050", expect_facts=False))
    dup = rows + (dataclasses.replace(rows[-1], close=1.0),)
    A(Case("def_duplicate_dates", "0050", make_ok(rows=dup, latest=dup[-1], as_of=dup[-1].date), S.MISSING, symbol="0050",
           expect_facts=False))
    A(Case("def_row_date_is_datetime", "0050", make_ok(rows=_with_latest(rows, date=dt.datetime(2026, 11, 24, 0, 0))),
           S.MISSING, symbol="0050", expect_facts=False))
    A(Case("def_row_date_is_str", "0050", make_ok(rows=_with_latest(rows, date="2026-11-24")), S.MISSING, symbol="0050",
           expect_facts=False))
    A(Case("def_future_trade_date", "0050", make_ok(end="2026-11-26"), S.MISSING, symbol="0050",
           reason_has=("trade_date_missing",), expect_facts=False))
    for tag, bad, why in [("none", None, "close_missing"), ("str", "N/A", "close_invalid"), ("zero", 0.0, "close_invalid"),
                          ("nan", float("nan"), "close_invalid"), ("neg", -1.0, "close_invalid"),
                          ("bool", True, "close_invalid"), ("tiny", 0.001, "close_out_of_display_range")]:
        A(Case(f"def_latest_close_{tag}", "0050", make_ok(rows=_with_latest(rows, close=bad)), S.MISSING, symbol="0050",
               reason_has=(why,), expect_facts=False))
    A(Case("def_source_none", "0050", make_ok(source=None), S.MISSING, symbol="0050", reason_has=("source_missing",),
           expect_facts=False))
    A(Case("def_source_newline", "0050", make_ok(source="Fin\nMind"), S.MISSING, symbol="0050",
           reason_has=("source_invalid",), expect_facts=False))
    # ── 過期（沿用 STALE_DAYS_DAILY=7；嚴格大於）──
    A(Case("stale_8_days", "0050", make_ok(end="2026-11-17"), S.STALE, symbol="0050", trade_date="2026-11-17",
           fetched_text=f"抓取時間 {FETCHED_ISO}", value_text="188.55"))
    A(Case("fresh_7_days_boundary_is_ok", "0050", make_ok(end="2026-11-18"), S.OK, symbol="0050",
           trade_date="2026-11-18", fetched_text=f"抓取時間 {FETCHED_ISO}", value_text="188.55"))
    sat_fetch = dt.datetime(2026, 11, 28, 2, 0, tzinfo=dt.timezone.utc)
    A(Case("saturday_after_friday_close_is_ok", "0050", make_ok(end="2026-11-27", fetched_at=sat_fetch), S.OK,
           today=dt.date(2026, 11, 28), symbol="0050", trade_date="2026-11-27",
           fetched_text="抓取時間 2026-11-28T02:00:00+00:00", value_text="188.55"))
    # ── fetched_at 與 trade_date 分離、不互相冒充 ──
    A(Case("fetched_at_naive_is_unknown_not_trade_date", "0050", make_ok(fetched_at=dt.datetime(2026, 11, 25, 9, 30)),
           S.OK, symbol="0050", trade_date="2026-11-24", fetched_text=TEXT_FETCHED_AT_UNKNOWN, value_text="188.55"))
    A(Case("fetched_at_none_is_unknown", "0050", make_ok(fetched_at=None), S.OK, symbol="0050", trade_date="2026-11-24",
           fetched_text=TEXT_FETCHED_AT_UNKNOWN, value_text="188.55"))
    taipei = dt.timezone(dt.timedelta(hours=8))
    A(Case("fetched_at_other_tz_kept_verbatim", "0050", make_ok(fetched_at=dt.datetime(2026, 11, 25, 9, 30, tzinfo=taipei)),
           S.OK, symbol="0050", trade_date="2026-11-24", fetched_text="抓取時間 2026-11-25T09:30:00+08:00",
           value_text="188.55"))
    # ── 序列長度／量／平盤（事實側）──
    A(Case("short_series_3_rows", "0050", make_ok(n=3), S.OK, symbol="0050", trade_date="2026-11-24",
           fetched_text=f"抓取時間 {FETCHED_ISO}", value_text="188.55",
           facts_none=("ma5", "ma20", "ma60", "ma120", "ma240", "rsi14", "volume_ratio5", "bias20_pct", "overheated")))
    A(Case("series_19_rows", "0050", make_ok(n=19), S.OK, symbol="0050", trade_date="2026-11-24",
           fetched_text=f"抓取時間 {FETCHED_ISO}", value_text="188.55", facts_none=("ma20", "ma60", "bias20_pct")))
    zero_vol = tuple(dataclasses.replace(r, volume_shares=0.0) for r in make_rows("2026-11-24", 30))
    A(Case("volume_all_zero_is_valid_ratio_none", "0050", make_ok(rows=zero_vol), S.OK, symbol="0050", **ok_kw,
           facts_none=("volume_ratio5",)))
    flat = tuple(OhlcvRow(r.date, 100.0, 100.0, 100.0, 100.0, 1000.0) for r in make_rows("2026-11-24", 40))
    A(Case("flat_prices_rsi_undefined_is_none", "0050", make_ok(rows=flat), S.OK, symbol="0050", trade_date="2026-11-24",
           fetched_text=f"抓取時間 {FETCHED_ISO}", value_text="100.00", facts_none=("rsi14", "overheated")))
    return c


CASES = _cases()
CASE_IDS = [c.id for c in CASES]


# ════════════════════════════════════════════════════════════════════
# §3 逐案例驗收 ＋ 不變量（violations＝空 才算通過）
# ════════════════════════════════════════════════════════════════════
def _facts_field(facts: FactsStandIn, name: str):
    return facts.ma[int(name[2:])] if name.startswith("ma") else getattr(facts, name)


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
        if v.fetched_at_text == f"抓取時間 {case.trade_date}":
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
        for f in case.facts_none:
            if _facts_field(out.facts, f) is not None:
                bad.append(f"facts.{f} 應為 None（不補 0／不偽值）：{_facts_field(out.facts, f)!r}")
        txt = "\n".join(out.facts.lines())
        for w in FORBIDDEN_FACT_WORDS:
            if w in txt:
                bad.append(f"facts 含禁字 {w}")
        if "未調整原始價" not in txt:
            bad.append("facts 缺『未調整原始價』限制揭露")
    blob = _all_text(out)
    for m in LEAK_MARKERS:
        if m in blob.replace(SRC, ""):          # 合法來源標籤本身不算洩漏
            bad.append(f"輸出含敏感標記 {m!r}")
    if v.state is S.MISSING:
        for w in FORBIDDEN_MISSING_WORDS:
            if w in blob:
                bad.append(f"MISSING 文案斷言標的不存在 {w!r}")
    if v.state in (S.MISSING, S.FETCH_FAILED, S.NOT_LOADED, S.SELECTION_INVALID) and "0.00" in blob:
        bad.append("非資料態出現 0.00")
    return bad


def _run(case: Case, policy: Policy = CORRECT) -> BridgeOutput:
    return bridge(case.raw, case.result, today=case.today, policy=policy)


def _case(cid: str) -> Case:
    return next(c for c in CASES if c.id == cid)


@pytest.mark.parametrize("case", CASES, ids=CASE_IDS)
def test_case_matches_contract(case):
    assert violations(case, _run(case)) == []


def test_today_is_a_wednesday_and_rows_are_weekdays():
    assert TODAY.weekday() == 2
    assert all(r.date.weekday() < 5 for r in make_rows("2026-11-24", 60))


def test_all_six_states_are_covered_by_cases():
    assert {c.state for c in CASES} == set(S)


def test_case_ids_unique_and_no_skip_marks():
    assert len(set(CASE_IDS)) == len(CASE_IDS)
    src = pathlib.Path(__file__).read_text(encoding="utf-8")
    assert "pytest.mark.skip" + "(" not in src and "pytest.mark.xfail" + "(" not in src and "pytest.skip" + "(" not in src


def test_ok_detail_exact():
    out = _run(_case("ok_0050"))
    v = out.view
    assert (v.state, v.chip_text, v.value_text, v.reason, v.notice_text) == (S.OK, "資料正常", "188.55", None, None)
    assert v.trade_date_text == "交易日 2026-11-24" and v.fetched_at_text == f"抓取時間 {FETCHED_ISO}"
    assert v.source_text == f"來源 {SRC}" and v.symbol == "0050"
    assert v.fact is not None and v.fact.trade_date == "2026-11-24" and v.fact.fetched_at == FETCHED_ISO


def test_stale_shows_last_close_with_stale_chip():
    v = _run(_case("stale_8_days")).view
    assert (v.state, v.chip_text, v.value_text, v.notice_text) == (S.STALE, "資料過期", "188.55", "資料已過期，仍顯示最後收盤")


def test_stale_threshold_is_the_repo_ssot_not_a_local_number():
    """門檻取自 `shared.staleness.STALE_DAYS_DAILY`：距預期最新交易日恰＝門檻→OK，門檻+1→STALE。"""
    assert STALE_DAYS_DAILY == 7        # 若 SSOT 變動，案例日期（11-18／11-17）須有意識改寫
    for end, want in [("2026-11-18", S.OK), ("2026-11-17", S.STALE)]:
        age = staleness_days(end, today=TODAY)
        assert (age > STALE_DAYS_DAILY) is (want is S.STALE), (end, age)
        assert bridge("0050", make_ok(end=end), today=TODAY).view.state is want


def test_stale_accepts_date_objects_in_the_real_ssot_function():
    """橋把 `date` 交給 `staleness_days`（真函式接受 date／str）；兩種型別結果相同。"""
    assert staleness_days(dt.date(2026, 11, 17), today=TODAY) == staleness_days("2026-11-17", today=TODAY) == 8


def test_view_state_does_not_depend_on_volume_value():
    a = bridge("0050", make_ok(), today=TODAY).view
    rows = tuple(dataclasses.replace(r, volume_shares=r.volume_shares * 7 + 3) for r in make_rows("2026-11-24"))
    b = bridge("0050", make_ok(rows=rows), today=TODAY).view
    assert a == b


def test_fetch_failed_text_is_fixed_and_tone_is_danger_not_grey():
    out = _run(_case("fetch_failed_hostile_error_code"))
    assert out.view.notice_text == "讀取失敗，請稍後再試" and out.view.tone.name == "DANGER"
    assert out.reasons == ("a_fetch_failed",)


def test_selection_invalid_is_grey_not_red():
    out = _run(_case("invalid_0"))
    assert out.view.tone.name == "NEUTRAL_INFO" and out.view.symbol is None and out.view.reason is not None


def test_leading_zero_symbol_verbatim_and_never_numerified():
    out = _run(_case("ok_0050"))
    assert out.view.symbol == "0050" and out.view.fact.symbol == "0050"
    assert parse_ticker_input("0050").symbol == "0050" and parse_ticker_input("50").status is SelectionStatus.INVALID
    assert bridge("0050", make_ok("50"), today=TODAY).view.state is S.MISSING     # A 若吃掉前導零 → 不當 OK


# ════════════════════════════════════════════════════════════════════
# §4 映射表（P-M2b）／型別負控（以實測鎖死）
# ════════════════════════════════════════════════════════════════════
MAPPING = (   # (A state, 範例結果, 預期 B 態, 預期 reason 子字串)
    (STATE_OK, make_ok(), S.OK, ""),
    (STATE_NO_DATA, make_empty(STATE_NO_DATA, error_code="no_data"), S.MISSING, "close_missing"),
    (STATE_FETCH_FAILED, make_empty(STATE_FETCH_FAILED, error_code="fetch_transient"), S.FETCH_FAILED, "fetch_failed"),
    (STATE_INVALID_DATA, make_empty(STATE_INVALID_DATA, error_code="invalid_data", reasons=("close_outside_low_high",)),
     S.MISSING, "close_missing"),
    (STATE_INVALID_SYMBOL, make_empty(STATE_INVALID_SYMBOL, error_code="invalid_symbol"), S.SELECTION_INVALID, ""),
)


@pytest.mark.parametrize("a_state,res,want,why", MAPPING, ids=[m[0] for m in MAPPING])
def test_state_mapping_table(a_state, res, want, why):
    assert res.state == a_state
    v = bridge("0050", res, today=TODAY).view
    assert v.state is want and why in (v.reason or "")
    if want is not S.OK:
        assert v.value_text is None and v.fact is None


def test_mapping_table_covers_every_a_state_exactly_once():
    assert sorted(m[0] for m in MAPPING) == sorted(ALL_A_STATES) and len(MAPPING) == len(ALL_A_STATES)


def test_invalid_data_is_missing_never_ok_never_fetch_failed():
    v = bridge("0050", make_empty(STATE_INVALID_DATA, reasons=("date_not_ascending",)), today=TODAY).view
    assert v.state is S.MISSING and v.state not in (S.OK, S.STALE, S.FETCH_FAILED) and v.tone.name == "WARNING"


def test_no_data_wording_does_not_claim_delisting_or_nonexistence():
    for st in (STATE_NO_DATA, STATE_INVALID_DATA):
        v = bridge("0050", make_empty(st), today=TODAY).view
        txt = " ".join(x for x in (v.chip_text, v.notice_text, v.reason) if x)
        assert not [w for w in FORBIDDEN_MISSING_WORDS if w in txt], txt
    assert NOTICE_TEXT[S.MISSING] == "資料未備（非 0）"


def test_bridge_is_duck_typed_so_the_real_1289_types_drop_in():
    """橋只看欄位、不綁替身類別：換成 #1289 真 `OhlcvRow`／`StockLatestOhlcv`（同欄位名）結果不變（scratch 以真 A 驗證過）。"""
    from types import SimpleNamespace as NS
    base = make_ok()
    rows = tuple(NS(**dataclasses.asdict(r)) for r in base.rows)
    res = NS(**{**dataclasses.asdict(base), "rows": rows, "latest": rows[-1]})
    assert bridge("0050", res, today=TODAY).view == bridge("0050", base, today=TODAY).view
    assert bridge("0050", res, today=TODAY).facts == bridge("0050", base, today=TODAY).facts


def test_unknown_a_state_fails_loud():
    weird = dataclasses.replace(make_ok(), state="stale")
    with pytest.raises(ValueError):
        bridge("0050", weird, today=TODAY)


def test_invalid_symbol_state_never_shows_the_symbol_even_if_b_parse_succeeds():
    v = bridge("0050", make_empty(STATE_INVALID_SYMBOL), today=TODAY).view
    assert v.state is S.SELECTION_INVALID and v.symbol is None and v.value_text is None


def _sel():
    return parse_ticker_input("0050")


def _bqv(**kw):
    base = dict(loaded=True, fetch_error=None, close=119.8, trade_date="2026-11-25", fetched_at=FETCHED_ISO, source=SRC, is_stale=False)
    base.update(kw)
    return build_quote_view(_sel(), **base)


def test_type_control_iso_strings_are_the_only_accepted_date_form():
    """鎖死『轉字串是橋接責任』：B 只收 ISO 字串（實測 2026-11-27）。"""
    ok = _bqv()
    assert ok.state is S.OK and ok.fetched_at_text == f"抓取時間 {FETCHED_ISO}" and ok.trade_date_text == "交易日 2026-11-25"
    for bad_td in (dt.date(2026, 11, 25), dt.datetime(2026, 11, 25, 1, 30)):
        v = _bqv(trade_date=bad_td)
        assert v.state is S.MISSING and "trade_date_invalid" in v.reason and v.value_text is None


def test_type_control_datetime_fetched_at_is_silently_unknown_not_missing():
    """⚠️ 實測與 P-M2b 描述不同：把 `datetime`／`date` 直傳 fetched_at **不會**變 MISSING，而是 OK＋『抓取時間未知』
    （抓取時間被靜默吞掉）。故橋必須自己 isoformat；本測釘住 B 的實際行為，並由 §5 `pass_date_objects` 錯誤橋保護。"""
    for bad_fa in (FETCHED_DT, FETCHED_DT.date()):
        v = _bqv(fetched_at=bad_fa)
        assert v.state is S.OK and v.fetched_at_text == TEXT_FETCHED_AT_UNKNOWN
    assert bridge("0050", make_ok(), today=TODAY).view.fetched_at_text == f"抓取時間 {FETCHED_ISO}"


def test_type_control_numpy_close_behaviour_is_pinned():
    """np.float64 是 float 子類 → OK；np.int64／np.float32 不是 → close_invalid（MISSING，不 raise）。橋只傳 python float。"""
    assert _bqv(close=np.float64(119.8)).state is S.OK
    for c in (np.int64(120), np.float32(119.8), np.int64(0)):
        v = _bqv(close=c)
        assert v.state is S.MISSING and "close_invalid" in v.reason
    assert type(bridge("0050", make_ok(), today=TODAY).view.fact.close) is float


def test_lookup_calls_a_only_for_a_valid_selection_with_verbatim_symbol_and_keyword_token():
    spy = FetchSpy(make_ok(), [])
    calls: list = []
    out = lookup(" 00631l ", FetchSpy(make_ok("00631L"), calls), today=TODAY, token="TKN")
    assert calls == [("00631L", {"token": "TKN"})] and out.view.state is S.OK
    for raw in ("abc!!", "", "50", None, 50, "2330.TW"):
        out = lookup(raw, spy, today=TODAY)
        assert out.view.state is S.SELECTION_INVALID
    assert spy.calls == []                      # invalid_symbol → 不呼叫 A
    assert "TKN" not in _all_text(lookup("0050", FetchSpy(make_ok(), []), today=TODAY, token="TKN"))


# ════════════════════════════════════════════════════════════════════
# §5 有牙：每個『錯誤橋』必須被驗收判紅（且正確橋全綠）
# ════════════════════════════════════════════════════════════════════
MUTANTS = {
    "missing_close_as_zero": Policy(missing_close_as_zero=True),
    "ignore_stale": Policy(ignore_stale=True),
    "fetched_at_from_trade_date": Policy(fetched_at_from_trade_date=True),
    "leak_error_text": Policy(leak_error_text=True),
    "symbol_loose_zero_match": Policy(symbol_loose_zero_match=True),
    "accept_future_date": Policy(accept_future_date=True),
    "accept_unsorted_rows": Policy(accept_unsorted_rows=True),
    "facts_zero_fill": Policy(facts_zero_fill=True),
    "facts_on_non_value_state": Policy(facts_on_non_value_state=True),
    "facts_flat_rsi_zero": Policy(facts_flat_rsi_zero=True),
    "invalid_data_as_fetch_failed": Policy(invalid_data_as_fetch_failed=True),
    "no_data_as_fetch_failed": Policy(no_data_as_fetch_failed=True),
    "pass_date_objects": Policy(pass_date_objects=True),
    "close_as_numpy_scalar": Policy(close_as_numpy_scalar=True),
}
LOOKUP_MUTANTS = {"call_fetch_on_invalid_symbol": Policy(call_fetch_on_invalid_symbol=True)}


def test_correct_bridge_has_zero_violations_across_all_cases():
    assert {c.id: violations(c, _run(c)) for c in CASES if violations(c, _run(c))} == {}


@pytest.mark.parametrize("name", sorted(MUTANTS))
def test_wrong_bridge_is_caught(name):
    caught = {c.id: v for c in CASES if (v := violations(c, _run(c, MUTANTS[name])))}
    assert caught, f"錯誤橋 {name} 沒有被任何案例抓到（驗收無牙）"


@pytest.mark.parametrize("name", sorted(LOOKUP_MUTANTS))
def test_wrong_lookup_is_caught_by_the_call_spy(name):
    spy = FetchSpy(make_ok(), [])
    try:
        lookup("abc!!", spy, today=TODAY, policy=LOOKUP_MUTANTS[name])
    except Exception:       # noqa: BLE001 — 錯誤編排可能在後續階段才失敗；有牙的證據是『A 被呼叫了』
        pass
    assert spy.calls != [], "錯誤編排沒有觸發不該有的 A 呼叫（spy 無牙）"


def test_mutant_set_covers_every_policy_knob():
    assert {f.name for f in dataclasses.fields(Policy)} == set(MUTANTS) | set(LOOKUP_MUTANTS), "新增旋鈕必須同時新增錯誤橋"
    assert all(getattr(CORRECT, f.name) is False for f in dataclasses.fields(Policy))


def test_missing_close_as_zero_is_not_hidden_by_quote_view_alone():
    """quote_view 會把 0 判成 close_invalid（仍 MISSING）；有牙點在『原因』必須是 close_missing（缺值≠無效值）。"""
    case = _case("no_data")
    bad = _run(case, Policy(missing_close_as_zero=True))
    assert bad.view.state is S.MISSING and "close_invalid" in bad.view.reason and "close_missing" not in bad.view.reason
    assert violations(case, bad) != []


# ════════════════════════════════════════════════════════════════════
# §6 事實（C 側替身；既有真純函式）／安全負控
# ════════════════════════════════════════════════════════════════════
def test_facts_equal_direct_calls_to_the_real_pure_functions():
    rows = make_rows("2026-11-24", 60)
    facts = bridge("0050", make_ok(rows=rows), today=TODAY).facts
    df = rows_to_frame(rows)
    assert facts.ma[20] == pytest.approx(float(df["close"].rolling(20).mean().iloc[-1]), abs=1e-4)
    assert facts.ma[60] is not None and facts.ma[120] is None and facts.ma[240] is None
    assert facts.rsi14 == calc_rsi(df, 14) and facts.volume_ratio5 == calc_volume_ratio(df, 5)
    assert facts.overextension_level == assess_price_overextension(df["close"])["level"]
    assert facts.bar_count == 60 and (facts.first_date, facts.as_of) == (rows[0].date, rows[-1].date)
    assert facts.price_basis == "unadjusted" and facts.close == 188.55


def test_rows_to_frame_shape_matches_what_c_requires():
    """C 的輸入契約（#1290 L14-21）：小寫五欄、DatetimeIndex(name='date') 嚴格遞增、量欄原值（volume_shares→volume）。"""
    rows = make_rows("2026-11-24", 30)
    df = rows_to_frame(rows)
    assert list(df.columns) == ["open", "high", "low", "close", "volume"]
    assert isinstance(df.index, pd.DatetimeIndex) and df.index.name == "date" and df.index.is_monotonic_increasing
    assert df["volume"].tolist() == [r.volume_shares for r in rows]            # NV：不換算
    assert df.index[-1].date() == rows[-1].date
    with pytest.raises(ValueError):
        rows_to_frame(tuple(reversed(rows)))                                    # 不排序
    with pytest.raises(ValueError):
        rows_to_frame(())


def test_volume_passed_through_in_source_units_not_converted():
    rows = _with_latest(make_rows("2026-11-24", 30), volume_shares=12_345_678.0)
    f = bridge("0050", make_ok(rows=rows), today=TODAY).facts
    assert f.last_volume_shares == 12_345_678.0 and "12,345,678" in "\n".join(f.lines())


def test_insufficient_rows_give_none_never_zero_or_nan():
    for n, none_fields in [(1, ("rsi14", "volume_ratio5", "bias20_pct")), (5, ("rsi14", "volume_ratio5")),
                           (14, ("rsi14",)), (19, ("bias20_pct", "overheated"))]:
        f = bridge("0050", make_ok(n=n), today=TODAY).facts
        assert f is not None and f.bar_count == n, n
        for name in none_fields:
            assert getattr(f, name) is None, (n, name)
        for name in ("rsi14", "volume_ratio5", "bias20_pct"):
            val = getattr(f, name)
            assert val is None or math.isfinite(val)
    assert bridge("0050", make_ok(n=20), today=TODAY).facts.ma[20] is not None
    assert bridge("0050", make_ok(n=15), today=TODAY).facts.rsi14 is not None
    assert bridge("0050", make_ok(n=21), today=TODAY).facts.overextension_level in ("過熱", "偏熱", "正常")
    assert bridge("0050", make_ok(n=3), today=TODAY).facts.limitations[-1].startswith("下列指標根數不足")


def test_facts_disclose_limits_and_have_no_trade_words():
    f = bridge("0050", make_ok(n=45), today=TODAY).facts
    txt = "\n".join(f.lines())
    assert LIMITATION_UNADJUSTED in txt and "45 根" in txt and str(f.first_date) in txt and str(f.as_of) in txt
    assert not [w for w in FORBIDDEN_FACT_WORDS if w in txt]


def test_overextension_level_words_are_descriptive_not_directive():
    levels = {assess_price_overextension(pd.Series([100.0 + i * i * 0.2 for i in range(40)]))["level"],
              assess_price_overextension(pd.Series([100.0] * 40))["level"],
              assess_price_overextension(pd.Series([100.0] * 5))["level"]}
    assert levels <= {"過熱", "偏熱", "正常", "資料不足"}
    assert not [w for lv in levels for w in FORBIDDEN_FACT_WORDS if w in lv]


def test_facts_deterministic_and_independent_of_fetch_time():
    a = bridge("0050", make_ok(n=40), today=TODAY)
    b = bridge("0050", make_ok(n=40, fetched_at=dt.datetime(2026, 11, 25, 5, 0, tzinfo=dt.timezone.utc)), today=TODAY)
    assert a.facts == b.facts and a.view.fact.trade_date == b.view.fact.trade_date and a.view != b.view


def test_facts_absent_on_every_non_value_state():
    for c in CASES:
        out = _run(c)
        if out.view.state not in VALUE_BEARING:
            assert out.facts is None, c.id


def test_hostile_error_code_never_reaches_any_output():
    out = bridge("0050", make_empty(STATE_FETCH_FAILED, error_code=HOSTILE_CODE), today=TODAY)
    blob = _all_text(out)
    for m in LEAK_MARKERS:
        assert m not in blob, m
    assert out.view.state is S.FETCH_FAILED and out.view.reason == "fetch_failed" and out.facts is None


def test_hostile_source_with_control_chars_is_rejected_not_displayed():
    for src in ("FinMind\r\nSet-Cookie: x", "a" * 65, "   ", None, 123):
        out = bridge("0050", make_ok(source=src), today=TODAY)
        assert out.view.state is S.MISSING and out.view.value_text is None, src


def test_leak_check_has_teeth():
    case = _case("fetch_failed_hostile_error_code")
    out = bridge(case.raw, case.result, today=case.today, policy=Policy(leak_error_text=True))
    assert any("敏感標記" in v for v in violations(case, out))


def test_bridge_signature_and_token_never_in_a_result():
    assert set(inspect.signature(bridge).parameters) == {"raw", "result", "today", "policy"}
    assert "token" not in {f.name for f in dataclasses.fields(StockLatestOhlcv)}     # A 只回 authenticated 布林（#1289 L177）


def test_quote_view_signature_has_not_drifted_from_what_the_bridge_assumes():
    assert list(inspect.signature(build_quote_view).parameters) == [
        "selection", "loaded", "fetch_error", "close", "trade_date", "fetched_at", "source", "is_stale"]
    assert {f.name for f in dataclasses.fields(QuoteView)} == {
        "state", "chip_text", "tone", "symbol", "value_text", "trade_date_text", "fetched_at_text", "source_text",
        "notice_text", "reason", "fact"}


def test_a_replica_fields_match_the_1289_shape():
    assert [f.name for f in dataclasses.fields(StockLatestOhlcv)] == [
        "state", "symbol", "rows", "latest", "as_of", "fetched_at", "source", "authenticated", "error_code", "reasons", "n_rows"]
    assert [f.name for f in dataclasses.fields(OhlcvRow)] == ["date", "open", "high", "low", "close", "volume_shares"]
    assert ALL_A_STATES == ("ok", "no_data", "fetch_failed", "invalid_symbol", "invalid_data")


def test_assumption_lists_exist_numbered_and_tagged():
    for tup, p in ((A_CONTRACT_ASSUMPTIONS, "A"), (C_CONTRACT_ASSUMPTIONS, "C")):
        assert all(a.startswith(f"{p}{i + 1}【驗證 ") or a.startswith(f"{p}{i + 1}【假設") for i, a in enumerate(tup))
    assert len(A_CONTRACT_ASSUMPTIONS) == 13 and len(C_CONTRACT_ASSUMPTIONS) == 6


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
                          fetched_at=FETCHED_ISO, source=SRC, is_stale=False)
    assert ok.state is S.OK and lookup_submission_view("0050").state is S.NOT_LOADED


def test_wiring_fact_a_and_c_modules_not_in_main_yet():
    """#1289（`src/data/stock/stock_latest_ohlcv.py`）與 #1290（`src/compute/strategy/stock_research_facts.py`）合併前，
    main 上沒有這兩個模組，本檔因此以測試內替身（§1）對映其形狀。**合併後本測試會有意轉紅**：請把 `StockLatestOhlcv`／`OhlcvRow`／
    `STATE_*` 換成真 import、把 `build_facts_standin` 換成真 `build_stock_research_facts`（見 *_CONTRACT_ASSUMPTIONS）。"""
    import importlib.util
    for mod in ("src.data.stock.stock_latest_ohlcv", "src.compute.strategy.stock_research_facts"):
        try:
            found = importlib.util.find_spec(mod) is not None
        except ModuleNotFoundError:
            found = False
        assert found is False, f"{mod} 已存在：請以真 API 替換測試內替身，並刪除本測試"
