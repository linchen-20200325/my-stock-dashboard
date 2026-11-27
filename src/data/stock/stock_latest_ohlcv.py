"""src/data/stock/stock_latest_ohlcv.py — 個股最新日 OHLCV（L1 薄包裝；M2）。

用途
====
給畫面層／計算層一份「**同次抓取、按日期遞增、已驗證**」的個股日 K 序列（原始未調整價），
並以固定欄位交代 symbol／資料日（as_of）／抓取時間（fetched_at）／來源（source）／狀態。
本檔**只取數＋驗證**：不算均線、不判過期、不落盤、不快取、不碰 UI。

層級與依賴（CLAUDE.md §8.2）
===========================
L1 Data。只依賴 `src.data.core.finmind_client.finmind_get`（公開 L1，plain `requests`、verify=True、
憑證只走 Authorization header）。⛔ 不 import streamlit；⛔ 不使用 `_fetch_finmind_price_raw`／`_bps_dl`／
`_fm_raw_headers`（那條路徑走 `verify=False` 的 proxy session）；⛔ 不使用 `st.cache_data`、不寫檔、
不留全域可變快取。每次呼叫都是一次新的抓取（快取／節流屬呼叫端或 L3 的決定）。

資料口徑（據實）
================
- 資料集：FinMind `TaiwanStockPrice`（個股日 K，**原始未調整價**；非還原股價）。
- 欄位對應：`date`→date、`open`→open、`max`→high、`min`→low、`close`→close、
  `Trading_Volume`→volume_shares。
- `volume_shares`：**FinMind 原始成交量欄，單位依 FinMind 文件為股；本模組不換算（不 /1000）；
  單位核實＝NV**（尚未以真實回應核對）。
- 價格單位為「元／股」，不換算、不還原。
- 0050 等前導零代號一律以**字串**傳遞，不轉 int。

狀態（`StockLatestOhlcv.state`；字串常數）
=========================================
- `STATE_OK`：抓到、驗證全過。`rows` 非空、`latest`／`as_of` 有值。
- `STATE_NO_DATA`：FinMind 回空表且**沒有**確定性失敗訊號。語意是「查無資料或在這一層無法區分」——
  可能是代號不存在、區間內無交易日、或 FinMind 非暫時性的拒絕（400／401／403／422…，`finmind_get`
  對這些也回空表）。**不聲稱該標的已下市／不存在。**
- `STATE_FETCH_FAILED`：確定的抓取失敗——`finmind_get` 的 `failed` 有記錄（402／429／5xx／例外），
  或呼叫它本身拋例外。`error_code` 為固定短碼，**不含**例外原文、URL、token。
- `STATE_INVALID_SYMBOL`：代號格式不合法；**不呼叫** `finmind_get`。`symbol` 為 None（不回顯未驗證輸入）。
- `STATE_INVALID_DATA`：抓到了但資料不可信（缺欄／日期異常／缺值／OHLC 不變量違反…）。
  `reasons` 列固定原因碼；**不丟列、不修正、不排序**；此狀態下 `rows` 為空、`latest`／`as_of` 為 None，
  避免下游誤用可疑資料。

代號規則（對齊 `shared/ui2_contract/target_selection.TICKER_PATTERN`，但本檔不 import 它）
===============================================================================
只接受 `str`；`strip()` 後須為 ASCII、總長 4～6、首字元數字、其餘 0-9／A-Z（小寫 ASCII 轉大寫，
唯一的規格化）。`int`／`bytes`／`None` 等一律 INVALID_SYMBOL（不 `str()` 強轉）；`"50"` 過短 → INVALID_SYMBOL
（不補零，否則會悄悄選到另一檔標的）。含 `.TW`／`.TWO` 後綴、內部空白、全形字元一律 INVALID_SYMBOL。

驗證規則（任一違反 → INVALID_DATA；原因碼見 `REASON_*`）
=======================================================
1. 必要欄位齊全：date／open／max／min／close／Trading_Volume；若有 `stock_id` 欄，必須全等於 symbol。
2. date：須為嚴格 `YYYY-MM-DD` 字串且為有效日曆日；不得重複；**必須嚴格遞增——亂序一律 INVALID_DATA
   （本模組不自行排序，也不記 reorder 後放行）**；不得晚於 today（台北日；未來日）。
3. 數值欄（open／high／low／close／volume_shares）：None／NaN／空字串→`<欄>_missing`；
   ±inf（含 float 溢位）→`<欄>_not_finite`；其他非數值（含 bool、無法解析的字串）→`<欄>_not_numeric`。
   **缺值絕不變成 0。**
4. 價量關係：close>0；open／high／low 不得為負；high≥low；low≤open≤high；low≤close≤high；volume≥0。

⚠️ 事實提醒（INFERENCE，NV）：FinMind 在「無成交」的日子可能給 open／max／min＝0 而 close 為前收；
依上列不變量該列會被判 INVALID_DATA（本模組選擇不放行、不修補）。是否需要特例處理，待以真實回應核實後另案。

安全
====
token 不進任何回傳欄位／`repr`／例外訊息／print／log；log 只記例外「類別名」。`finmind_get` 內部自己的
print 不含 token（憑證只放 header），本模組不額外印任何東西。
"""
from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any

import pandas as pd

from src.data.core.finmind_client import finmind_get

_log = logging.getLogger(__name__)

# ── 常數（具名；不得 inline magic number）────────────────────────────────

#: FinMind dataset（個股日 K，原始未調整價）。
DATASET_STOCK_PRICE = "TaiwanStockPrice"
#: 來源標記；沿用 `data_loader._fetch_finmind_price_raw` 既有慣例字串（本檔不 import 該私有函式）。
SOURCE_FINMIND_STOCK_PRICE = "FinMind:TaiwanStockPrice:raw_http"

#: 回看日曆日數預設值。約 13 個月，足以涵蓋 240 交易日年線（`ANNUAL_MA`＝240）＋假日／停牌缺口餘裕。
#: 這是「取數視窗」而非任何指標參數；C 線要更長／更短由呼叫端以 `lookback_days` 指定。
DEFAULT_LOOKBACK_DAYS = 400
#: `lookback_days` 合理上限（日曆日，約 10 年）；超過視為呼叫端錯誤（ValueError）。
MAX_LOOKBACK_DAYS = 3650
#: 單次請求逾時秒數（對齊 `finmind_get` 預設）。
DEFAULT_TIMEOUT_SECONDS = 20
#: 嘗試次數。1＝不重試：失敗時不連續轟炸來源（CLAUDE.md §1.A-3(b)）。
FETCH_ATTEMPTS = 1

#: 台北時區＝UTC+8（CLAUDE.md §4.5；不使用第三方時區庫）。
TAIPEI_UTC_OFFSET_HOURS = 8
_TAIPEI_TZ = timezone(timedelta(hours=TAIPEI_UTC_OFFSET_HOURS))

# 代號規則（對齊 TICKER_PATTERN 的語意；見模組 docstring）
SYMBOL_MIN_LEN = 4
SYMBOL_MAX_LEN = 6
_SYMBOL_RE = re.compile(r"[0-9][0-9A-Z]{3,5}")
_DATE_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")

# ── 狀態常數 ────────────────────────────────────────────────────────────
STATE_OK = "ok"
STATE_NO_DATA = "no_data"
STATE_FETCH_FAILED = "fetch_failed"
STATE_INVALID_SYMBOL = "invalid_symbol"
STATE_INVALID_DATA = "invalid_data"
ALL_STATES = (STATE_OK, STATE_NO_DATA, STATE_FETCH_FAILED, STATE_INVALID_SYMBOL, STATE_INVALID_DATA)

# ── error_code（固定短碼；非 OK 才有）─────────────────────────────────
ERR_INVALID_SYMBOL = "invalid_symbol"
ERR_NO_DATA = "no_data"
ERR_FETCH_EXCEPTION = "fetch_exception"      # finmind_get 拋例外（原文不帶出）
ERR_FETCH_TRANSIENT = "fetch_transient"      # finmind_get 記錄了 402／429／5xx／例外
ERR_INVALID_DATA = "invalid_data"

# ── 原因碼（INVALID_DATA 的 reasons；固定集合）────────────────────────────
REASON_RESPONSE_NOT_DATAFRAME = "response_not_dataframe"
REASON_STOCK_ID_MISMATCH = "stock_id_mismatch"
REASON_DATE_UNPARSEABLE = "date_unparseable"
REASON_DATE_DUPLICATE = "date_duplicate"
REASON_DATE_NOT_ASCENDING = "date_not_ascending"
REASON_DATE_IN_FUTURE = "date_in_future"
REASON_CLOSE_NOT_POSITIVE = "close_not_positive"
REASON_PRICE_NEGATIVE = "price_negative"
REASON_HIGH_BELOW_LOW = "high_below_low"
REASON_OPEN_OUTSIDE_RANGE = "open_outside_low_high"
REASON_CLOSE_OUTSIDE_RANGE = "close_outside_low_high"
REASON_VOLUME_NEGATIVE = "volume_negative"

# 欄位對應：(輸出欄位名, FinMind 欄位名)
_COL_DATE = "date"
_COL_STOCK_ID = "stock_id"
_NUM_FIELDS = (
    ("open", "open"),
    ("high", "max"),
    ("low", "min"),
    ("close", "close"),
    ("volume_shares", "Trading_Volume"),
)
_REQUIRED_FM_COLS = (_COL_DATE,) + tuple(fm for _, fm in _NUM_FIELDS)


def reason_missing_column(fm_col: str) -> str:
    return f"missing_column_{fm_col}"


def reason_value(field: str, kind: str) -> str:
    """kind ∈ {'missing','not_finite','not_numeric'} → 例如 `close_missing`。"""
    return f"{field}_{kind}"


@dataclass(frozen=True)
class OhlcvRow:
    """單日 OHLCV（原始未調整價；volume_shares 單位依 FinMind 原始欄，未換算）。"""
    date: date
    open: float
    high: float
    low: float
    close: float
    volume_shares: float


@dataclass(frozen=True)
class StockLatestOhlcv:
    """`fetch_stock_latest_ohlcv` 的回傳（不可變）。缺值一律 None，絕不補 0。

    - `state`：見模組 docstring 的狀態常數。
    - `symbol`：驗證後的字串（保留前導零，如 "0050"）；INVALID_SYMBOL 時為 None。
    - `rows`：同次抓取、日期嚴格遞增、已驗證的 OhlcvRow tuple；只有 OK 非空。
    - `latest`／`as_of`：最後一列／其日期（資料日，非抓取日）；非 OK 為 None。
    - `fetched_at`：本次抓取時間（UTC、含時區）。與 `as_of` 完全分開。
    - `source`：資料來源標記字串。
    - `authenticated`：本次是否帶了 token（只有布林，不含 token 本身）。
    - `error_code`：固定短碼（非 OK 才有）；不含例外原文／URL／token。
    - `reasons`：INVALID_DATA 的固定原因碼 tuple（去重、依首次出現順序）。
    - `n_rows`：`len(rows)`。
    """
    state: str
    symbol: str | None
    rows: tuple[OhlcvRow, ...]
    latest: OhlcvRow | None
    as_of: date | None
    fetched_at: datetime
    source: str
    authenticated: bool
    error_code: str | None
    reasons: tuple[str, ...]
    n_rows: int


# ── 內部：代號／日期／數值 ──────────────────────────────────────────────

def _normalize_symbol(raw: Any) -> str | None:
    """合法 → 大寫代號字串；否則 None。不 raise、不補零、不強轉非 str。"""
    if not isinstance(raw, str):
        return None
    text = raw.strip()
    if not text or not text.isascii():
        return None
    sym = text.upper()                       # 先驗 ASCII 再 upper（避免 'ı'→'I' 之類的自動修正）
    if not (SYMBOL_MIN_LEN <= len(sym) <= SYMBOL_MAX_LEN):
        return None
    if _SYMBOL_RE.fullmatch(sym) is None:    # fullmatch：不讓 `$` 吃掉尾端換行；內部空白／符號／後綴皆落此
        return None
    return sym


def _parse_iso_date(value: Any) -> date | None:
    if not isinstance(value, str) or _DATE_RE.fullmatch(value) is None:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:                       # 例如 2026-02-30
        return None


def _to_float(value: Any) -> tuple[float | None, str | None]:
    """→ (float, None) 或 (None, kind)；kind ∈ {'missing','not_finite','not_numeric'}。絕不回 0 替代缺值。"""
    if value is None:
        return None, "missing"
    if isinstance(value, bool):
        return None, "not_numeric"
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None, "missing"
        try:
            num = float(text)
        except ValueError:
            return None, "not_numeric"
        except OverflowError:
            return None, "not_finite"
    else:
        try:
            num = float(value)
        except (TypeError, ValueError):
            return None, "not_numeric"
        except OverflowError:                # 例如 10**400
            return None, "not_finite"
    if math.isnan(num):
        return None, "missing"
    if math.isinf(num):
        return None, "not_finite"
    return num, None


# ── 內部：結果建構 ──────────────────────────────────────────────────────

def _empty(state: str, symbol: str | None, fetched_at: datetime, authenticated: bool,
           error_code: str | None, reasons: tuple[str, ...] = ()) -> StockLatestOhlcv:
    return StockLatestOhlcv(
        state=state, symbol=symbol, rows=(), latest=None, as_of=None,
        fetched_at=fetched_at, source=SOURCE_FINMIND_STOCK_PRICE,
        authenticated=authenticated, error_code=error_code, reasons=reasons, n_rows=0)


def _validate(df: pd.DataFrame, symbol: str, today: date) -> tuple[tuple[OhlcvRow, ...], tuple[str, ...]]:
    """→ (rows, reasons)。reasons 非空時 rows 必為空（不放行可疑資料）。"""
    reasons: list[str] = []

    def _add(code: str) -> None:
        if code not in reasons:
            reasons.append(code)

    missing_cols = [c for c in _REQUIRED_FM_COLS if c not in df.columns]
    for col in missing_cols:
        _add(reason_missing_column(col))
    if missing_cols:
        return (), tuple(reasons)

    if _COL_STOCK_ID in df.columns:
        if any(not (isinstance(v, str) and v.strip().upper() == symbol) for v in df[_COL_STOCK_ID].tolist()):
            _add(REASON_STOCK_ID_MISMATCH)

    dates = df[_COL_DATE].tolist()
    cols = {out: df[fm].tolist() for out, fm in _NUM_FIELDS}
    rows: list[OhlcvRow] = []
    seen: set[date] = set()
    prev: date | None = None
    for i, raw_date in enumerate(dates):
        d = _parse_iso_date(raw_date)
        if d is None:
            _add(REASON_DATE_UNPARSEABLE)
        else:
            if d in seen:
                _add(REASON_DATE_DUPLICATE)
            elif prev is not None and d < prev:
                _add(REASON_DATE_NOT_ASCENDING)
            if d > today:
                _add(REASON_DATE_IN_FUTURE)
            seen.add(d)
            prev = d if prev is None or d > prev else prev

        vals: dict[str, float | None] = {}
        for out, _fm in _NUM_FIELDS:
            num, kind = _to_float(cols[out][i])
            if kind is not None:
                _add(reason_value(out, kind))
            vals[out] = num

        o, h, lo, c, v = (vals["open"], vals["high"], vals["low"], vals["close"], vals["volume_shares"])
        if c is not None and c <= 0:
            _add(REASON_CLOSE_NOT_POSITIVE)
        if any(x is not None and x < 0 for x in (o, h, lo)):
            _add(REASON_PRICE_NEGATIVE)
        if h is not None and lo is not None and h < lo:
            _add(REASON_HIGH_BELOW_LOW)
        if o is not None and ((lo is not None and o < lo) or (h is not None and o > h)):
            _add(REASON_OPEN_OUTSIDE_RANGE)
        if c is not None and ((lo is not None and c < lo) or (h is not None and c > h)):
            _add(REASON_CLOSE_OUTSIDE_RANGE)
        if v is not None and v < 0:
            _add(REASON_VOLUME_NEGATIVE)

        if d is not None and None not in (o, h, lo, c, v):
            rows.append(OhlcvRow(date=d, open=o, high=h, low=lo, close=c, volume_shares=v))  # type: ignore[arg-type]

    if reasons:
        return (), tuple(reasons)
    return tuple(rows), ()


# ── 公開 API ────────────────────────────────────────────────────────────

def fetch_stock_latest_ohlcv(
    stock_id: str,
    *,
    token: str = "",
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    today: date | None = None,
    now: datetime | None = None,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> StockLatestOhlcv:
    """抓取個股近 `lookback_days` 日曆日的日 K（FinMind TaiwanStockPrice，原始未調整價），驗證後回傳。

    Args:
        stock_id:      代號字串（"0050" 保留前導零）。非法 → INVALID_SYMBOL，且不呼叫 finmind_get。
        token:         FinMind token（可空＝免費額度）。只走 Authorization header；不進任何輸出。
        lookback_days: 取數視窗（日曆日，1～`MAX_LOOKBACK_DAYS`）；超出範圍 → ValueError（呼叫端錯誤）。
        today:         「今天」（台北日），供測試注入；預設由 `now` 換算為台北日。用於未來日判斷與取數區間終點。
        now:           「現在」（須為 tz-aware）；預設 `datetime.now(UTC)`。`fetched_at` 一律轉 UTC。
        timeout:       單次請求秒數。

    Returns:
        `StockLatestOhlcv`（見其 docstring）。除 `lookback_days`／`today`／`now` 的型別錯誤（ValueError）外，
        **不 raise**——抓取例外一律轉成 FETCH_FAILED＋固定 error_code。
    """
    if isinstance(lookback_days, bool) or not isinstance(lookback_days, int) \
            or not 1 <= lookback_days <= MAX_LOOKBACK_DAYS:
        raise ValueError("lookback_days must be an int within 1..MAX_LOOKBACK_DAYS")
    if now is None:
        now = datetime.now(timezone.utc)
    elif not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be a timezone-aware datetime")
    fetched_at = now.astimezone(timezone.utc)
    if today is None:
        today = fetched_at.astimezone(_TAIPEI_TZ).date()
    elif isinstance(today, datetime) or not isinstance(today, date):
        raise ValueError("today must be a datetime.date (not datetime)")

    tok = token.strip() if isinstance(token, str) else ""
    authenticated = bool(tok)

    symbol = _normalize_symbol(stock_id)
    if symbol is None:
        return _empty(STATE_INVALID_SYMBOL, None, fetched_at, authenticated, ERR_INVALID_SYMBOL)

    start = today - timedelta(days=lookback_days)
    failed: list = []
    try:
        df = finmind_get(
            DATASET_STOCK_PRICE,
            data_id=symbol,
            start_date=start.isoformat(),
            end_date=today.isoformat(),
            token=tok,
            timeout=timeout,
            retries=FETCH_ATTEMPTS,
            failed=failed,
        )
    except Exception as exc:                  # noqa: BLE001 — 一律轉固定短碼；只記類別名，不記訊息
        _log.warning("stock_latest_ohlcv fetch exception: %s", type(exc).__name__)
        return _empty(STATE_FETCH_FAILED, symbol, fetched_at, authenticated, ERR_FETCH_EXCEPTION)

    if failed:
        _log.warning("stock_latest_ohlcv transient fetch failure (n=%d)", len(failed))
        return _empty(STATE_FETCH_FAILED, symbol, fetched_at, authenticated, ERR_FETCH_TRANSIENT)
    if not isinstance(df, pd.DataFrame):
        return _empty(STATE_INVALID_DATA, symbol, fetched_at, authenticated, ERR_INVALID_DATA,
                      (REASON_RESPONSE_NOT_DATAFRAME,))
    if df.empty:
        return _empty(STATE_NO_DATA, symbol, fetched_at, authenticated, ERR_NO_DATA)

    rows, reasons = _validate(df, symbol, today)
    if reasons:
        return _empty(STATE_INVALID_DATA, symbol, fetched_at, authenticated, ERR_INVALID_DATA, reasons)

    latest = rows[-1]
    return StockLatestOhlcv(
        state=STATE_OK, symbol=symbol, rows=rows, latest=latest, as_of=latest.date,
        fetched_at=fetched_at, source=SOURCE_FINMIND_STOCK_PRICE, authenticated=authenticated,
        error_code=None, reasons=(), n_rows=len(rows))
