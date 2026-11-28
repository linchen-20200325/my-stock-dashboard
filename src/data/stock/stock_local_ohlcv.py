"""src/data/stock/stock_local_ohlcv.py — 本機匯入個股日 K（L1；純 bytes 解析，無 I/O）。

用途
====
把「使用者自己提供的一份 CSV（以 bytes 傳入）」解析、驗證成與 FinMind 路徑**同型**的 `OhlcvRow` tuple，
使 `stock_latest_ohlcv.rows_to_bars_frame` 可直接轉成 L2 `build_stock_research_facts` 的輸入。
本檔**只解析＋驗證**：不讀檔、不寫檔、不連網、不取時鐘、不讀環境變數、不快取、不印 log。
上傳／檔案 widget／取得日（匯入時間）都屬 L3／UI 的責任，本層一概不碰。

層級與依賴（CLAUDE.md §8.2）
===========================
L1 Data。直接 import：標準庫 `csv`／`io`／`re`／`dataclasses`／`datetime.date`／`typing`、`pandas`，以及
同層 `src.data.stock.stock_latest_ohlcv`（重用 `validate_ohlcv_frame`／`OhlcvRow`／`STATE_*`／`ERR_*`／
`REASON_*`／`reason_missing_column` 與私有 `_normalize_symbol`——後者是「代號規則 SSOT」，同層同套件內
引用，**不複製第二份正規式**）。⛔ 不 import streamlit／requests／proxy／FinMind 取數函式。
⚠️ 傳遞性事實：`stock_latest_ohlcv` 本身會 import `src.data.core.finmind_client`（→ `requests`，且載入
`src.data.core` 套件）；本檔不呼叫其中任何網路函式。

資料口徑（據實；不宣稱已驗證）
==============================
- 來源＝使用者提供的檔案，**系統無法驗證其真偽、單位、是否還原、是否含息**。`source` 固定為
  `SOURCE_LOCAL_IMPORT`，**不含檔名／路徑／任何使用者輸入**。
- 價格單位視為「元／股」、volume **原樣不換算**（欄位單位＝使用者檔案的單位；**單位未驗證＝NV**）。
- 沒有「匯入時間／fetched_at」欄：取得日由 L3 另行記錄。`as_of`＝末列資料日。

輸入契約
========
`parse_local_ohlcv_csv(file_bytes, symbol, *, today)`
- `today`：`datetime.date`（非 `datetime`），**必須由呼叫端傳入**（本層不取時鐘）；型別錯 → `ValueError`（固定訊息）。
- `symbol`：沿用 `stock_latest_ohlcv._normalize_symbol` 規則（前導零保留；`"0050"`）；不合法 →
  `STATE_INVALID_SYMBOL`，且**完全不解析檔案**（連 `file_bytes` 型別都不看）。
- `file_bytes`：只收 `bytes`／`bytearray`／`memoryview`，其餘 → `invalid_data`（`input_not_bytes`）；
  已 `release()` 或無法讀取的 memoryview 同樣回 `input_not_bytes`（不 raise）。
  大小上限 `MAX_FILE_BYTES`（2 MiB）：超過 → `file_too_large`，**不解析**。資料列上限 `MAX_DATA_ROWS`（5000）：
  超過 → `too_many_rows`。兩者皆為具名常數；剛好等於上限允許，多 1 即拒。

編碼
====
只接受 UTF-8（可帶**一個** UTF-8 BOM），嚴格解碼；big5／cp950／其他編碼解碼失敗 → `encoding_not_utf8`
（不猜編碼、不 `errors='replace'`）。含 NUL 位元組 → `contains_nul`（先於解碼檢查，UTF-16 也落此）。

CSV 結構
========
- 以標準庫 `csv.reader(strict=True)` 讀入，**全部當字串**（前導零如 `0050` 不會被型別推斷吃掉）。
  CSV 方言錯誤（引號不成對、欄位超過 csv 預設欄寬上限）→ `csv_malformed`。
- 完全空白的行（`[]`）略過（只是排版）；只含空白字元的行不略過（欄數不符 → `row_length_mismatch`）。
  每個資料列欄數必須等於表頭欄數（不補空、不截斷）。
- 表頭各欄 `strip()`；**欄名大小寫須完全相符**（不做模糊比對）；重複欄名（含重複空名）→ `duplicate_column`。
- 必備欄：`stock_id`、`date`；價量欄**二選一**：FinMind 原生 `open,max,min,close,Trading_Volume`，
  或 `open,high,low,close,volume`。兩組的專屬欄（`max/min/Trading_Volume` 與 `high/low/volume`）同時出現任一
  （含混用，如 `max`＋`low`）→ `ambiguous_ohlcv_columns`（不猜該用哪一組）；兩組專屬欄都沒有 →
  `missing_ohlcv_columns`；只有一組時缺哪欄 → `missing_column_<欄名>`。額外欄忽略。
- 每一列 `stock_id` 正規化後必須等於使用者輸入代號，否則整批 `stock_id_mismatch`。

空檔的選擇（以測試固定）
========================
- **0 位元組／只有 BOM／只有空白行**：`STATE_INVALID_DATA`（`empty_file`）——沒有表頭就不是一份有效 CSV，
  這是「檔案壞了／傳錯檔」，不是「這檔股票沒有資料」。
- **表頭合法、零資料列**：`STATE_NO_DATA`（`error_code="no_data"`）——檔案本身有效，只是沒有列；
  **不說「查無此股」**。表頭不合法（缺欄等）則優先 `invalid_data`。

值驗證（全部重用 `validate_ohlcv_frame`／`_validate`，不複製第二套）
================================================================
ISO 日期、嚴格遞增、唯一、不晚於 `today`；缺值（空字串／`nan`／`null`／`none`／`na`／`n/a`）→ `<欄>_missing`
（**絕不補 0**）；±inf、`1e400`、400 位數整數字串 → `<欄>_not_finite`（`float()` 對字串溢位回 inf，不拋
OverflowError）；其他非數值 → `<欄>_not_numeric`；open／high／low／close ≤ 0 → `<欄>_not_positive`；
OHLC 關係；volume ≥ 0（`volume==0` 合法，與缺值可區分）。**全有或全無**：任一列有問題 → 整批
`invalid_data`、`rows=()`，不丟列、不修正、不排序。
本層在交給 `_validate` 前只做「字串形狀」預濾（另加下列兩條「不可默默變成 0」的字面檢查）：數字儲存格須為 ASCII 的十進位／科學記號
（`[+-]?digits[.digits][e±digits]`）；其餘（`1_0`、全形數字、`1,234`、`0x10`…）一律當 `not_numeric`
（Python `float()` 其實會接受底線與全形數字，那不是我們要接受的檔案格式）。
- **不可表示的非零字面**：尾數含非零位數、但 `float()` 下溢成 0.0（如 `1e-400`、`-1e-999`）→ 整批
  `<欄>_not_representable`（價格與 volume 同；不默默變 0）。字面真的是 0（`0`、`0.0`、`0e5`）照原規則
  （volume=0 合法；價格 ≤0 → `<欄>_not_positive`）。
- **負零**：字面為 `-0`、`-0.0`、`-0e5` → 整批 `<欄>_negative_zero`（價格另外也會帶 `<欄>_not_positive`；
  volume 因此不會輸出 `-0.0`）。

限制（據實；**非核准行為**）
==========================
- **不設價格／volume 的絕對上限**：上限屬尚未核准的業務門檻。極大但有限的值（如 `1e300`）**會被接受**；
  下游滾動均量等計算可能因此溢位成偽值（inf／NaN 或錯誤量比）。上限待核准門檻，未核准前請勿當成「已防禦」。
- 單位（元／股、股／張）、是否還原、是否含息，皆未驗證（見「資料口徑」）。

安全
====
任何回傳欄位／`repr`／例外訊息都**只含固定字串與驗證後的數值／日期／代號**，不含檔名、路徑、儲存格原文。
本模組不 import `logging`、不 `print`、不開檔。唯一會 raise 的是 `today` 型別錯誤（固定訊息 `ValueError`）。
"""
from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from datetime import date, datetime

import pandas as pd

from src.data.stock.stock_latest_ohlcv import (
    ERR_INVALID_DATA,
    ERR_INVALID_SYMBOL,
    ERR_NO_DATA,
    STATE_INVALID_DATA,
    STATE_INVALID_SYMBOL,
    STATE_NO_DATA,
    STATE_OK,
    OhlcvRow,
    _normalize_symbol,
    reason_missing_column,
    reason_value,
    validate_ohlcv_frame,
)

# ── 常數（具名；不得 inline magic number）────────────────────────────────

#: 來源標記（固定字串；不含檔名／路徑／使用者輸入）。
SOURCE_LOCAL_IMPORT = "本機匯入（使用者提供檔案，來源未經系統驗證）"
#: 檔案大小上限（bytes）。剛好等於允許，多 1 byte 即拒。
MAX_FILE_BYTES = 2 * 1024 * 1024
#: 資料列上限（不含表頭）。剛好等於允許，多 1 列即拒。
MAX_DATA_ROWS = 5000
#: UTF-8 解碼用的 codec（`utf-8-sig`＝嚴格 UTF-8＋容許開頭**一個** BOM）。
_CODEC = "utf-8-sig"

# 檔案層原因碼（固定集合；由測試鎖定）
REASON_INPUT_NOT_BYTES = "input_not_bytes"
REASON_FILE_TOO_LARGE = "file_too_large"
REASON_EMPTY_FILE = "empty_file"
REASON_CONTAINS_NUL = "contains_nul"
REASON_ENCODING_NOT_UTF8 = "encoding_not_utf8"
REASON_CSV_MALFORMED = "csv_malformed"
REASON_DUPLICATE_COLUMN = "duplicate_column"
REASON_AMBIGUOUS_OHLCV_COLUMNS = "ambiguous_ohlcv_columns"
REASON_MISSING_OHLCV_COLUMNS = "missing_ohlcv_columns"
REASON_ROW_LENGTH_MISMATCH = "row_length_mismatch"
REASON_TOO_MANY_ROWS = "too_many_rows"

#: 數字儲存格原因碼的 kind（與 `reason_value(field, kind)` 組成 `<欄>_<kind>`；由測試鎖定）。
KIND_NOT_REPRESENTABLE = "not_representable"
KIND_NEGATIVE_ZERO = "negative_zero"
#: 輸出欄名（與 `_FINMIND_COLS` 逐位對應；原因碼用的是這組名稱，如 `volume_shares_missing`）。
_FIELD_NAMES = ("open", "high", "low", "close", "volume_shares")

#: `today` 型別錯誤的固定訊息。
TODAY_TYPE_MESSAGE = "today must be a datetime.date (not datetime)"

# 欄名
_COL_STOCK_ID = "stock_id"
_COL_DATE = "date"
#: FinMind 原生欄名組（輸出給 `_validate` 的也是這組欄名）。
_FINMIND_COLS = ("open", "max", "min", "close", "Trading_Volume")
#: 英文小寫欄名組，與 `_FINMIND_COLS` 逐位對應。
_ENGLISH_COLS = ("open", "high", "low", "close", "volume")
_FINMIND_ONLY = tuple(c for c in _FINMIND_COLS if c not in _ENGLISH_COLS)   # max / min / Trading_Volume
_ENGLISH_ONLY = tuple(c for c in _ENGLISH_COLS if c not in _FINMIND_COLS)   # high / low / volume

# 數字儲存格：ASCII 十進位／科學記號（fullmatch；線性，無災難性回溯）
_NUMBER_RE = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?")
#: 視為「缺值」的字面（小寫比對）→ 交給 `_validate` 判 `<欄>_missing`。
_MISSING_TOKENS = frozenset({"", "nan", "null", "none", "na", "n/a"})
#: 無窮大字面（小寫比對）→ 交給 `_validate` 判 `<欄>_not_finite`。
_POS_INF_TOKENS = frozenset({"inf", "+inf", "infinity", "+infinity"})
_NEG_INF_TOKENS = frozenset({"-inf", "-infinity"})
#: 任何通不過預濾的儲存格 → 一個必定非數值的固定字串（`_to_float` → `not_numeric`）。
_NOT_NUMERIC_TOKEN = "?"
#: 代號不符時塞給 `_validate` 的 stock_id 儲存格（必定不等於任何合法代號）。
_MISMATCH_CELL = ""


# ── 結果型別 ────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class LocalOhlcvImport:
    """`parse_local_ohlcv_csv` 的回傳（不可變）。缺值一律 None／空，絕不補 0。

    - `state`：`STATE_OK`／`STATE_NO_DATA`／`STATE_INVALID_SYMBOL`／`STATE_INVALID_DATA`
      （沿用 `stock_latest_ohlcv` 的字串常數；沒有 FETCH_FAILED——本層不取數）。
    - `symbol`：驗證後代號（保留前導零）；INVALID_SYMBOL 時為 None（不回顯未驗證輸入）。
    - `rows`：與 FinMind 路徑同型的 `OhlcvRow` tuple（日期嚴格遞增）；只有 OK 非空。
    - `latest`／`as_of`：最後一列／其日期（資料日）；非 OK 為 None。
    - `source`：固定 `SOURCE_LOCAL_IMPORT`。
    - `error_code`：固定短碼（非 OK 才有）。
    - `reasons`：固定原因碼 tuple（去重、依首次出現順序）。
    - `n_rows`：`len(rows)`。
    ⛔ 沒有 fetched_at／authenticated／匯入時間欄：取得日由 L3 另處理。
    """
    state: str
    symbol: str | None
    rows: tuple[OhlcvRow, ...]
    latest: OhlcvRow | None
    as_of: date | None
    source: str
    error_code: str | None
    reasons: tuple[str, ...]
    n_rows: int


def _fail(state: str, symbol: str | None, error_code: str, reasons: tuple[str, ...] = ()) -> LocalOhlcvImport:
    return LocalOhlcvImport(state=state, symbol=symbol, rows=(), latest=None, as_of=None,
                            source=SOURCE_LOCAL_IMPORT, error_code=error_code, reasons=reasons, n_rows=0)


def _invalid(symbol: str, *reasons: str) -> LocalOhlcvImport:
    return _fail(STATE_INVALID_DATA, symbol, ERR_INVALID_DATA, tuple(dict.fromkeys(reasons)))


# ── 內部：儲存格預濾 ────────────────────────────────────────────────────

def _numeric_cell(raw: str) -> tuple[str, str | None]:
    """CSV 數字儲存格 → `(交給 _validate 的字串, 本層額外原因 kind 或 None)`（只改「形狀」，不改數值語意）。

    缺值字面→""（`<欄>_missing`）；ASCII 數字→原樣（`float()` 可能得 inf→`not_finite`）；
    inf 字面→標準 inf 字串；其餘一律→固定非數值字串（`not_numeric`）。絕不產出 0 替代。
    額外 kind：非零字面下溢成 0.0 → `not_representable`；字面為負零 → `negative_zero`。
    """
    text = raw.strip()
    low = text.lower()
    if low in _MISSING_TOKENS:
        return "", None
    if low in _POS_INF_TOKENS:
        return "inf", None
    if low in _NEG_INF_TOKENS:
        return "-inf", None
    if _NUMBER_RE.fullmatch(text) is None:
        return _NOT_NUMERIC_TOKEN, None
    mantissa = low.split("e", 1)[0]
    if float(text) == 0.0:                           # 含 -0.0；float(str) 對溢位回 inf、不拋例外
        if any(c in "123456789" for c in mantissa):  # 字面非零卻變 0：不可默默變 0
            return text, KIND_NOT_REPRESENTABLE
        if text.startswith("-"):                     # 字面為負零
            return text, KIND_NEGATIVE_ZERO
    return text, None


def _decode(data: bytes) -> str | None:
    try:
        return data.decode(_CODEC)
    except UnicodeDecodeError:
        return None


def _select_columns(names: list[str]) -> tuple[tuple[str, ...] | None, list[str]]:
    """→ (價量欄組或 None, 欄位層原因碼 list)。`names` 已 strip、無重複。"""
    have = set(names)
    reasons: list[str] = []
    for col in (_COL_STOCK_ID, _COL_DATE):
        if col not in have:
            reasons.append(reason_missing_column(col))
    has_fm = any(c in have for c in _FINMIND_ONLY)
    has_en = any(c in have for c in _ENGLISH_ONLY)
    group: tuple[str, ...] | None = None
    if has_fm and has_en:
        reasons.append(REASON_AMBIGUOUS_OHLCV_COLUMNS)
    elif has_fm or has_en:
        group = _FINMIND_COLS if has_fm else _ENGLISH_COLS
        reasons.extend(reason_missing_column(c) for c in group if c not in have)
    else:
        reasons.append(REASON_MISSING_OHLCV_COLUMNS)
        reasons.extend(reason_missing_column(c) for c in ("open", "close") if c not in have)
    if reasons:
        return None, reasons
    return group, reasons


# ── 公開 API ────────────────────────────────────────────────────────────

def parse_local_ohlcv_csv(file_bytes: object, symbol: object, *, today: date) -> LocalOhlcvImport:
    """把使用者提供的 CSV bytes 解析、驗證成 `LocalOhlcvImport`（純函式；契約見模組 docstring）。

    Args:
        file_bytes: `bytes`／`bytearray`／`memoryview`（UTF-8，可帶 BOM）。
        symbol:     使用者輸入的代號（"0050" 保留前導零）。
        today:      台北日（`datetime.date`），由呼叫端傳入；用於「不得晚於今天」。

    Returns:
        `LocalOhlcvImport`。除 `today` 型別錯誤（ValueError）外**不 raise**；所有檔案問題都轉成
        INVALID_DATA＋固定原因碼，且全有或全無（任一列有問題 → 整批拒絕，`rows=()`）。
    """
    if isinstance(today, datetime) or not isinstance(today, date):
        raise ValueError(TODAY_TYPE_MESSAGE)

    sym = _normalize_symbol(symbol)
    if sym is None:                                   # 先於一切：代號不合法 → 不看檔案
        return _fail(STATE_INVALID_SYMBOL, None, ERR_INVALID_SYMBOL)

    if not isinstance(file_bytes, (bytes, bytearray, memoryview)):
        return _invalid(sym, REASON_INPUT_NOT_BYTES)
    try:
        size = file_bytes.nbytes if isinstance(file_bytes, memoryview) else len(file_bytes)
        if size > MAX_FILE_BYTES:                     # 複製前先擋，不解析
            return _invalid(sym, REASON_FILE_TOO_LARGE)
        data = bytes(file_bytes)
    except ValueError:                                # 已 release() 的 memoryview：不可讀 → 固定原因碼，不 raise
        return _invalid(sym, REASON_INPUT_NOT_BYTES)
    if b"\x00" in data:
        return _invalid(sym, REASON_CONTAINS_NUL)
    text = _decode(data)
    if text is None:
        return _invalid(sym, REASON_ENCODING_NOT_UTF8)

    header: list[str] | None = None
    body: list[list[str]] = []
    try:
        for fields in csv.reader(io.StringIO(text, newline=""), strict=True):
            if not fields:                            # 完全空白行：只是排版
                continue
            if header is None:
                header = [c.strip() for c in fields]
                continue
            if len(fields) != len(header):
                return _invalid(sym, REASON_ROW_LENGTH_MISMATCH)
            if len(body) >= MAX_DATA_ROWS:            # 第 MAX+1 列 → 拒絕（剛好 MAX 列允許）
                return _invalid(sym, REASON_TOO_MANY_ROWS)
            body.append(fields)
    except csv.Error:
        return _invalid(sym, REASON_CSV_MALFORMED)

    if header is None:
        return _invalid(sym, REASON_EMPTY_FILE)
    if len(set(header)) != len(header):
        return _invalid(sym, REASON_DUPLICATE_COLUMN)
    group, col_reasons = _select_columns(header)
    if group is None:
        return _invalid(sym, *col_reasons)
    if not body:
        return _fail(STATE_NO_DATA, sym, ERR_NO_DATA)

    idx = {name: i for i, name in enumerate(header)}
    frame_cols: dict[str, list[str]] = {
        _COL_DATE: [r[idx[_COL_DATE]].strip() for r in body],
        _COL_STOCK_ID: [(_MISMATCH_CELL if _normalize_symbol(r[idx[_COL_STOCK_ID]]) != sym else sym)
                        for r in body],
    }
    extra: list[str] = []                             # 本層的數字字面原因（_validate 看不到）
    for fm_col, src_col, field in zip(_FINMIND_COLS, group, _FIELD_NAMES):
        cells = [_numeric_cell(r[idx[src_col]]) for r in body]
        frame_cols[fm_col] = [c for c, _k in cells]
        extra.extend(reason_value(field, k) for k in dict.fromkeys(k for _c, k in cells if k is not None))

    rows, reasons = validate_ohlcv_frame(pd.DataFrame(frame_cols, dtype=object), sym, today)
    if reasons or extra:
        return _invalid(sym, *reasons, *extra)
    latest = rows[-1]
    return LocalOhlcvImport(state=STATE_OK, symbol=sym, rows=rows, latest=latest, as_of=latest.date,
                            source=SOURCE_LOCAL_IMPORT, error_code=None, reasons=(), n_rows=len(rows))
