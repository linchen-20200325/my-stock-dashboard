"""shared/strategy_class_schema.py — 策略分類**唯讀**契約（AB-4r；L0 純函式＋常數）。

═══ 這個檔是什麼 ═══════════════════════════════════════════════════════
D2.5 計畫 `docs/vnext/NEWUI_D25_PLAN_2026-10-27.md` §5 序 5「AB-4r 策略分類唯讀契約」。
規格與決策理由：`docs/vnext/NEWUI_D25_AB4R_SPEC_2026-10-27.md`。
本檔定下三件事：
1. `portfolio_id` 的**來源**（AB-0 `HoldingKey` 刻意留白、交給本批）：
   `derive_portfolio_id(sheet_id, portfolio_name)` ＝ `"pfv1-"` ＋ sha256(sid＋NUL＋name) 前 20 個十六進位字元。
2. 持股鍵的組法：`build_holding_keys(...)` → `{ticker 原字串: HoldingKey(pid, ticker)}`
   （給 AB-1 builder 的 `holding_keys: Mapping[str, HoldingKey]`；**本批不接線**）。
3. `strategy_class` 分頁（`name | ticker | strategy | updated_at`）的**解析規則**：
   `parse_strategy_records(values, sheet_id=...)` → `StrategyReadResult`。

═══ 本檔刻意「不做」的事 ═══════════════════════════════════════════════
- 不取數、不寫入、不建分頁、不接 builder、不接 UI；零 I/O、零 streamlit、零 `src.*`。
- **不猜策略**：值經 strip → NFKC 後必須**恰好**等於 `StrategyType` 三值之一，否則該列記入
  `invalid_rows`（⛔ 不默默當未分類、⛔ 不做大小寫／同義詞對映）。
- **不擇一**：同一個鍵出現不同值 → 記入 `conflict_keys`、該鍵不入 entries（讀成未分類）。
- **不補鍵、不改寫 ticker**：ticker 只 strip（與 `gsheet_portfolio.parse_portfolio_records` 相同）；
  `HoldingKey` 建構失敗 → 記錄，不轉換（全形數字「２３３０」不會被變成「2330」）。

分層（CLAUDE.md §8.2）：L0 —— 只 import 標準函式庫與 `shared.*`。
表頭不符的例外 `StrategySchemaMismatchError` 放在本檔（L0 不得 import L1 的
`gsheet_portfolio.SheetSchemaMismatchError`）；L1 reader 再轉成 gsheet 的同型別例外上拋。
"""
from __future__ import annotations

import hashlib
import unicodedata
from collections.abc import Mapping as _AbcMapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Iterable, Literal, Mapping

from shared.decision_digest import HoldingKey, StrategyType
from shared.sheet_id import sanitize_sheet_id

# ══════════════════════════════════════════════════════════════════════
# 常數（§3.3 SSOT）
# ══════════════════════════════════════════════════════════════════════
#: 策略分類分頁名稱（與 `portfolios` 分頁物理隔離 ⇒ 現有 5 欄表頭完全不動）。
STRATEGY_WORKSHEET_NAME: str = "strategy_class"
#: 第一列從 A 欄起必須逐字等於此四欄（右側可自加欄）。
STRATEGY_HEADERS: tuple = ("name", "ticker", "strategy", "updated_at")
#: portfolio_id 的版本前綴：日後若換演算法，換前綴 ⇒ 新舊 id 不會互撞。
PORTFOLIO_ID_PREFIX: str = "pfv1-"
#: sha256 十六進位截取長度（20 hex ＝ 80 bit）。
PORTFOLIO_ID_HEX_LEN: int = 20
#: 有分類時 `HoldingEntry.strategy_source` 的值（客戶設定位置；不含 AI 字樣、不是佔位字）。
STRATEGY_SOURCE: str = "google_sheet:strategy_class"

#: `StrategyReadResult.status` 的合法值。
STATUS_OK: str = "ok"
STATUS_WORKSHEET_MISSING: str = "worksheet_missing"
STATUS_NOT_BOUND: str = "not_bound"
StrategyReadStatus = Literal["ok", "worksheet_missing", "not_bound"]
_STATUSES: frozenset = frozenset({STATUS_OK, STATUS_WORKSHEET_MISSING, STATUS_NOT_BOUND})

#: `InvalidRow.reason` 代碼（機器可讀；⛔ 不回顯使用者的格子內容）。
INVALID_MISSING_NAME: str = "missing_name"
INVALID_MISSING_TICKER: str = "missing_ticker"
INVALID_BAD_STRATEGY: str = "bad_strategy"
INVALID_BAD_KEY: str = "bad_key"
INVALID_NON_TEXT_CELL: str = "non_text_cell"

#: 合法策略字串 → StrategyType（只認 enum 自己的值，⛔ 不加同義詞）。
_STRATEGY_BY_VALUE: dict = {s.value: s for s in StrategyType}

#: 表頭不符的具體原因（給 log／測試用；例外訊息不回顯使用者的表頭內容）。
HEADER_FIRST_ROW_BLANK: str = "first_row_blank"
HEADER_DUPLICATE: str = "duplicate_header"
HEADER_MISMATCH: str = "header_mismatch"


class StrategySchemaMismatchError(ValueError):
    """`strategy_class` 分頁第一列欄名與 `STRATEGY_HEADERS` 不符（或本分頁欄名重複）。⛔ 不修表頭。"""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(
            f"「{STRATEGY_WORKSHEET_NAME}」分頁第一列欄名不符（{reason}）；"
            f"第一列須從 A 欄起依序為：{'、'.join(STRATEGY_HEADERS)}（右邊可自加欄）。")


# ══════════════════════════════════════════════════════════════════════
# portfolio_id
# ══════════════════════════════════════════════════════════════════════
def _normalize_portfolio_name(portfolio_name: Any) -> str:
    """組合名稱 → 比對用字串。規則與 `gsheet_portfolio` 篩組合**逐條相同**：
    `_list_portfolios_names` / `_load_portfolio_rows` / `load_portfolio` 都是 `str.strip()` 後**逐字**相等
    （⛔ 無 NFKC、無大小寫折疊、中間空白保留）⇒ 同一個組合在兩邊被分到同一組。"""
    if type(portfolio_name) is not str:
        raise ValueError(f"portfolio_name 必須是 str：{type(portfolio_name).__name__}")
    name = portfolio_name.strip()
    if not name:
        raise ValueError("portfolio_name 不可為空")
    return name


def _normalize_sheet_id(sheet_id: Any) -> str:
    if type(sheet_id) is not str:
        raise ValueError(f"sheet_id 必須是 str：{type(sheet_id).__name__}")
    sid = sanitize_sheet_id(sheet_id)
    if not sid:
        raise ValueError("sheet_id 消毒後為空（不是可用的 Google Sheet ID）")
    return sid


def derive_portfolio_id(sheet_id: str, portfolio_name: str) -> str:
    """(Sheet ID, 組合名稱) → 不透明、決定性的 `portfolio_id`（`pfv1-` ＋ 20 hex）。

    - sid＝`sanitize_sheet_id(sheet_id)`（唯一 Sheet ID parser）；name＝`portfolio_name.strip()`。
    - 兩者以 NUL 分隔後 sha256：sid 字母集不含 NUL ⇒ (sid, name) 與雜湊輸入一一對應。
    - 任一為空、非 str、sid 消毒不過 → `ValueError`（⛔ 不退回任何預設 Sheet）。
    - ⚠️ 組合改名 / 換一本（或複製）Sheet ⇒ pid 改變 ⇒ 舊分類讀不到（讀成未分類，fail-safe）。
    """
    sid = _normalize_sheet_id(sheet_id)
    name = _normalize_portfolio_name(portfolio_name)
    digest = hashlib.sha256((sid + "\x00" + name).encode("utf-8")).hexdigest()
    return PORTFOLIO_ID_PREFIX + digest[:PORTFOLIO_ID_HEX_LEN]


# ══════════════════════════════════════════════════════════════════════
# 持股鍵
# ══════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class HoldingKeysResult:
    """`build_holding_keys` 的結果。`keys`：ticker 原字串 → HoldingKey（唯讀）；
    `rejected`：建不出 HoldingKey 的 ticker（保序、去重；⛔ 不補鍵、不改寫）。"""
    keys: Mapping = field(default_factory=lambda: MappingProxyType({}))
    rejected: tuple = ()

    def __post_init__(self) -> None:
        # QA m-2：一律複製成新的唯讀 mapping（斷開呼叫端 dict 的別名），並驗型別。
        if not isinstance(self.keys, _AbcMapping):
            raise TypeError(f"keys 必須是 Mapping：{type(self.keys).__name__}")
        keys = dict(self.keys)
        for t, k in keys.items():
            if type(t) is not str or type(k) is not HoldingKey or k.symbol != t:
                raise ValueError("keys 只能是 ticker 原字串 → HoldingKey(pid, 同一 ticker)")
        if type(self.rejected) is not tuple or any(type(t) is not str for t in self.rejected):
            raise TypeError("rejected 必須是 str 的 tuple")
        object.__setattr__(self, "keys", MappingProxyType(keys))


def build_holding_keys(*, sheet_id: str, portfolio_name: str,
                       tickers: Iterable[str]) -> HoldingKeysResult:
    """一個組合的持股 ticker → `{ticker: HoldingKey(pid, ticker)}`。

    ⛔ 不預先套 AB-2a 的 `SYMBOL_PATTERN`：那是 AB-2a validator 的 fail-closed 關卡，這裡先濾掉會把它遮住。
    只有 AB-0 `HoldingKey` 本身拒收（空白、控制字元、非 NFKC…）的 ticker 進 `rejected`。
    ticker 非 str → `TypeError`（Fail Loud；不 str() 轉換，`50.0` 不是 `0050`）。
    """
    pid = derive_portfolio_id(sheet_id, portfolio_name)
    if isinstance(tickers, (str, bytes)):
        raise TypeError("tickers 必須是 ticker 的序列，不是單一字串")
    keys: dict = {}
    rejected: list = []
    for t in tickers:
        if type(t) is not str:
            raise TypeError(f"ticker 必須是 str：{type(t).__name__}")
        if t in keys or t in rejected:
            continue
        try:
            keys[t] = HoldingKey(pid, t)
        except ValueError:
            rejected.append(t)
    return HoldingKeysResult(keys=MappingProxyType(keys), rejected=tuple(rejected))


# ══════════════════════════════════════════════════════════════════════
# strategy_class 分頁解析
# ══════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class InvalidRow:
    """無法採用的一列。`row`：Sheet 上的列號（1-based，表頭＝第 1 列）；`reason`：`INVALID_*`。"""
    row: int
    reason: str


@dataclass(frozen=True)
class StrategyReadResult:
    """策略分類讀取結果。`entries` 只含「存股／資本利得」且無衝突的鍵（唯讀 mapping）。

    - status＝"ok"：分頁在、表頭合格（含空分頁 ⇒ 0 entries）。
    - status＝"worksheet_missing"：這本 Sheet 沒有 `strategy_class` 分頁（⛔ 讀取不建）。
    - status＝"not_bound"：沒有可用的 Sheet ID。
    三種都可以用 `lookup` 查：查無 → 未分類。
    """
    status: str
    entries: Mapping = field(default_factory=lambda: MappingProxyType({}))
    invalid_rows: tuple = ()
    conflict_keys: tuple = ()

    def __post_init__(self) -> None:
        if self.status not in _STATUSES:
            raise ValueError(f"status 不合法：{self.status!r}")
        # QA m-2：一律複製成新的 MappingProxyType（斷開外部 dict 別名），再逐項驗型別。
        if not isinstance(self.entries, _AbcMapping):
            raise TypeError(f"entries 必須是 Mapping：{type(self.entries).__name__}")
        entries = dict(self.entries)
        for k, v in entries.items():
            if type(k) is not HoldingKey or type(v) is not StrategyType or v is StrategyType.UNCLASSIFIED:
                raise ValueError("entries 只能是 HoldingKey → 存股／資本利得")
        if type(self.invalid_rows) is not tuple or type(self.conflict_keys) is not tuple:
            raise TypeError("invalid_rows／conflict_keys 必須是 tuple")
        if any(type(r) is not InvalidRow for r in self.invalid_rows):
            raise TypeError("invalid_rows 的元素必須是 InvalidRow")
        if any(type(k) is not HoldingKey for k in self.conflict_keys):
            raise TypeError("conflict_keys 的元素必須是 HoldingKey")
        object.__setattr__(self, "entries", MappingProxyType(entries))
        if self.status != STATUS_OK and (self.entries or self.invalid_rows or self.conflict_keys):
            raise ValueError(f"status={self.status!r} 時不得有任何內容")


def empty_result(status: str) -> StrategyReadResult:
    """沒有內容的結果（not_bound／worksheet_missing；或空分頁的 ok）。"""
    return StrategyReadResult(status=status)


def _is_blank(v: Any) -> bool:
    """空白格：None 或只含空白的 str（與 `gsheet_portfolio._is_blank_cell` 同一定義）。"""
    return v is None or (type(v) is str and not v.strip())


def _check_header(values: list) -> bool:
    """表頭關卡。回 True＝有表頭可讀；False＝整張表沒有任何非空白格（空分頁）。不合格 → raise。

    規則比照 `gsheet_portfolio._header_state`（逐字比對，⛔ 不 strip、不折疊大小寫）：
    整張表空白 → 空；第一列整列空白但下面有資料 → 不符；本分頁欄名在第一列重複 → 不符；
    第一列從 A 欄起 ＝ STRATEGY_HEADERS → OK（右側自加欄允許）。
    ⚠️ 刻意**不**沿用 `_header_state` 的「窄表頭前段」放寬（例：只有 name/ticker 兩欄）：
    `strategy` 欄是本分頁唯一的資料欄，沒有它就沒有可讀的內容 ⇒ 判不符（Fail Loud）。
    """
    if not any(not _is_blank(c) for r in values for c in r):
        return False
    first = list(values[0])
    if all(_is_blank(c) for c in first):
        raise StrategySchemaMismatchError(HEADER_FIRST_ROW_BLANK)
    if any(first.count(h) > 1 for h in STRATEGY_HEADERS):
        raise StrategySchemaMismatchError(HEADER_DUPLICATE)
    if tuple(first[:len(STRATEGY_HEADERS)]) != STRATEGY_HEADERS:
        raise StrategySchemaMismatchError(HEADER_MISMATCH)
    return True


def _cell(row: list, i: int) -> Any:
    return row[i] if i < len(row) else None


def _normalize_strategy(raw: str) -> StrategyType | None:
    """strip → NFKC → 必須恰好是三值之一；否則 None（呼叫端記 invalid）。"""
    return _STRATEGY_BY_VALUE.get(unicodedata.normalize("NFKC", raw.strip()))


def parse_strategy_records(values: list, *, sheet_id: str) -> StrategyReadResult:
    """`strategy_class` 分頁 `get_all_values()` 的結果 → `StrategyReadResult(status="ok")`。純函式。

    - `values` 必須是 list（每列 list/tuple）；否則 `TypeError`。sheet_id 不合格 → `ValueError`。
    - 沒有任何列（或整張表空白）→ 空分頁、0 entries（不是 schema mismatch：分頁存在、只是還沒人填；
      與 `gsheet_portfolio` 對空表回 EMPTY／[] 一致。日後寫入面建分頁時會一次寫上表頭）。
    - 表頭不符 → `StrategySchemaMismatchError`。
    - 逐列（自第 2 列）：全空白列略過；name／ticker／strategy 任一格非 str 且非 None（例 NaN、數字）
      → `non_text_cell`；name 空 → `missing_name`；ticker 空 → `missing_ticker`；
      strategy 不合法（含空）→ `bad_strategy`；HoldingKey 建不出 → `bad_key`。
    - 同鍵同值去重；同鍵不同值（含「未分類」vs 其他）→ `conflict_keys`，該鍵不入 entries。
    - 同鍵既有合法列、又有 `bad_strategy` 列（name／ticker 有效、只有策略值不合法）→ 也記 `conflict_keys`、
      不入 entries（⛔ 不保留合法值）。`bad_key` 列對應不到鍵，只記 `invalid_rows`。
    - 「未分類」列合法但不入 entries（AB-0：未分類時 strategy_source 必須 None ＝ 不必記錄）。
    """
    sid = _normalize_sheet_id(sheet_id)
    if type(values) is not list:
        raise TypeError(f"values 必須是 list：{type(values).__name__}")
    rows: list = []
    for r in values:
        if type(r) not in (list, tuple):
            raise TypeError(f"values 的每一列必須是 list：{type(r).__name__}")
        rows.append(list(r))
    if not rows or not _check_header(rows):
        return empty_result(STATUS_OK)

    i_name, i_ticker, i_strategy = (STRATEGY_HEADERS.index(h) for h in ("name", "ticker", "strategy"))
    invalid: list = []
    seen: dict = {}          # HoldingKey → StrategyType（第一次看到的值）
    order: list = []         # HoldingKey 首見順序（合法列）
    conflicting: set = set()  # 同鍵不同值
    poisoned: set = set()     # 鍵有效但策略值不合法的列所屬的鍵
    for n, row in enumerate(rows[1:], start=2):
        if all(_is_blank(c) for c in row):
            continue
        cells = [_cell(row, i) for i in (i_name, i_ticker, i_strategy)]
        if any(c is not None and type(c) is not str for c in cells):
            invalid.append(InvalidRow(n, INVALID_NON_TEXT_CELL))
            continue
        name, ticker, strategy_raw = (c or "" for c in cells)
        if not name.strip():
            invalid.append(InvalidRow(n, INVALID_MISSING_NAME))
            continue
        ticker = ticker.strip()
        if not ticker:
            invalid.append(InvalidRow(n, INVALID_MISSING_TICKER))
            continue
        try:
            key = HoldingKey(derive_portfolio_id(sid, name), ticker)
        except ValueError:
            invalid.append(InvalidRow(n, INVALID_BAD_KEY))
            continue
        strategy = _normalize_strategy(strategy_raw)
        if strategy is None:
            # QA m-1：鍵有效、只有策略值不合法 ⇒ 這個鍵被「污染」：若同鍵另有合法列，
            # 不得保留那個合法值（使用者對這檔的意圖不明）⇒ 收尾時一併記為衝突。
            invalid.append(InvalidRow(n, INVALID_BAD_STRATEGY))
            poisoned.add(key)
            continue
        if key not in seen:
            seen[key] = strategy
            order.append(key)
        elif seen[key] is not strategy:
            conflicting.add(key)

    conflicting |= poisoned & set(seen)
    conflicts = [k for k in order if k in conflicting]
    entries = {k: seen[k] for k in order
               if k not in conflicting and seen[k] is not StrategyType.UNCLASSIFIED}
    return StrategyReadResult(status=STATUS_OK, entries=MappingProxyType(entries),
                              invalid_rows=tuple(invalid), conflict_keys=tuple(conflicts))


def lookup(result: StrategyReadResult, key: HoldingKey) -> StrategyType:
    """查一檔持股的策略；查無（含衝突、無效列、未綁定、分頁不存在）→ 未分類。"""
    if type(result) is not StrategyReadResult:
        raise TypeError(f"result 必須是 StrategyReadResult：{type(result).__name__}")
    if type(key) is not HoldingKey:
        raise TypeError(f"key 必須是 HoldingKey：{type(key).__name__}")
    return result.entries.get(key, StrategyType.UNCLASSIFIED)


def unmatched_keys(result: StrategyReadResult, holding_keys: Mapping) -> tuple:
    """entries 裡**不對應任何持股鍵**的鍵（孤兒；保 entries 順序）。純揭露，⛔ 不改 `lookup` 的結果。

    典型成因：Sheet 把 `0050` 存成數字 `50`、大小寫不符（`00631l` vs `00631L`）、組合名打錯／改名。
    這些列在讀取端只會讀成「未分類」，本函式是唯一能把它們揭露出來的地方（QA-A M-1）。
    `holding_keys`：`build_holding_keys(...).keys`（ticker → HoldingKey）；型別不對 → `TypeError`。
    """
    if type(result) is not StrategyReadResult:
        raise TypeError(f"result 必須是 StrategyReadResult：{type(result).__name__}")
    if not isinstance(holding_keys, _AbcMapping):
        raise TypeError(f"holding_keys 必須是 Mapping：{type(holding_keys).__name__}")
    held = set()
    for k in holding_keys.values():
        if type(k) is not HoldingKey:
            raise TypeError(f"holding_keys 的值必須是 HoldingKey：{type(k).__name__}")
        held.add(k)
    return tuple(k for k in result.entries if k not in held)
