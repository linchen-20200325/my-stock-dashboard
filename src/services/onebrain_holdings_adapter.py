"""OneBrain：L1 持股讀取結果 → Digest `holdings_rows` 的 **dormant** L3 純轉換（C-OB-HOLDINGS-ADAPTER-DORMANT-1）。

授權：Issue #1199 comment 7062910532（新 L3 純轉換＋合成測試；最多一支 Draft PR；不合併）。
契約：`docs/vnext/ONEBRAIN_HOLDINGS_INPUT_CONTRACT_2026-11-21.md`（下文 §A／§B／§C 指該文件章節）。

═══ 是什麼／不是什麼 ═══════════════════════════════════════════════════
- **是**：一個純函式 `adapt_holdings_read`。輸入只有兩種——呼叫端**已經拿到**的 L1 `PortfolioReadTally`，
  或 L1 讀取時拋出的**例外物件**（呼叫端自己 `except` 後傳進來）。輸出 `HoldingsAdapterResult`：
  `holdings_rows`（`None` 或非空 tuple）＋**固定原因碼**。
- **不是**：本模組 ⛔ 不讀 Sheet、不碰 OAuth／網路／檔案、不呼叫 `load_portfolio_tallied` 或任何 L1 讀取入口、
  不呼叫時鐘、不 import streamlit、不 import Digest 家族模組、不改 Digest schema、不接任何 production caller
  （0 caller，dormant；`tests/test_onebrain_holdings_adapter_dormant.py` 以 AST 守衛）。
- 分層：L3 → L1（`gsheet_portfolio` 的型別、狀態常數與純函式 `classify_read_error`）是 §8.2 的正常方向；
  只用 public 符號。

═══ 對映規則（契約 §B1／§B2／§B3） ═══════════════════════════════════════
總則：**未知／零列回 None、不冒稱零持股或完整；已知但未評估仍保留部位；來源不完整則保守降級。**
本模組**永遠不回 `[]`**（結果型別直接拒收空 tuple）——`[]` 會讓 coverage `unkeyed_held_count` 由 None（未知）
變成 0（已知），把「不知道」偽裝成「已知沒有」（§B1）。

| 輸入 | `holdings_rows` | 原因碼 |
|---|---|---|
| 例外物件（`LoginRequiredError`／權限／網路／配額／其他） | None | `read_exception_*`（依 L1 `classify_read_error` 的**型別**分類；⛔ 不含例外訊息、不含型別名） |
| `status != ok`（`not_selected`／`worksheet_missing`／`schema_mismatch`／`empty`／其他） | None | `not_selected`／`read_status_*` |
| ok 但任一計數為 None | None | `counts_unknown` |
| ok 但計數彼此矛盾（手工捏造或損毀的 tally） | None | `tally_inconsistent`（fail-closed） |
| ok 且 `raw == 0`（§C-1 待決；保守） | None | `zero_rows` |
| ok 且有 EX 證據：`dropped` 中 `blank_value` 以外任一 >0、`kept_non_finite > 0`、重複代號 | None（**保守降級**） | `ex_dropped_*`／`non_finite_kept`／`duplicate_tickers` |
| ok、預設模式（`keep_blank` False）且 `dropped['blank_value'] > 0` | None | `in_u_blank_dropped` |
| 其餘（乾淨；含 `keep_blank` True 時張數／均價空白的 IN-U 列） | `rows` 每列一筆 `{'ticker', 'held': True}`，不去重、不丟 IN-U、順序同 L1 | 恆含 `universe_not_independent`；有 IN-U 列再加 `in_u_blank_kept` |

**為什麼 EX 證據要降級成 None，而不是給 list 並「揭露」？**（技術判斷，作者單組，未經第二組驗證）
Digest／coverage 目前**沒有**承載 L1 丟列、非有限值、重複代號的欄位（契約 §C-2／§C-3／§C-4，皆需 schema 放行）。
若照樣給 list，四段齊備時 `DigestCoverage.is_complete` 會是 True——下游看到的是「完整」，實際上來源有列被剔除或值
無效（§C-6）。在沒有揭露通道之前，保守降級成「未知」是唯一不冒稱完整的做法；原因碼記錄降級理由。
- 重複代號另一層理由：有鍵重複會讓 builder `ValueError(duplicate_holding_key)`，無鍵重複會被計成「另有 2 檔」
  （§C-3，計數單位未裁示）——兩者都不該由 adapter 擅自決定。
- 預設模式丟掉的 `blank_value` 列屬 IN-U（DEC-218 §一 第 1 點）：L1 已把它丟了，adapter 無從還原 ⇒ None。
  呼叫端若要保留 IN-U，須以 `keep_blank` True 模式讀取（§C-8(b)；本模組不替呼叫端讀）。
- ⚠️ NOT VERIFIED（契約 §C-8）：真實 gspread 讀到的空白格可能變成 0 而落入 `non_positive`；在本模組會被當 EX 降級
  成 None（保守），不會被誤當成乾淨 list。

**為什麼 list 只給 `ticker`＋`held`？** builder 只讀 `ticker`／`代號` 與 `held`（不讀 lots／avg_price）。張數／均價是
私人數值，且 IN-U 列為 None、L1 保留列可能含 NaN／+inf——帶下去只增加外洩面與「看似有值」的假精度，對 Digest 零貢獻。
需要時呼叫端可回頭讀 tally 本身。

**`universe_not_independent` 為何恆在 list 路徑？** L1 `raw` 與 `rows` 同源，不是獨立應有母體（契約 §B2-1；DEC-213 I3
未落地）。依契約任何以 L1 rows 餵入的 Digest 都必須 incomplete，但現行 coverage 無欄位承載（§C-6；#1254 的 strict xfail
仍在）。adapter 無法改 coverage，只能在自己的結果上**明示**這一點，避免呼叫端把 `is_complete` 當成已證明完整。

已知限制（據實）：
- 無時點：tally 與輸出都不帶 `fetched_at`／`as_of`（§C-10），本模組不補（不呼叫時鐘）。
- 無鍵部位（無 `HoldingKey`）在 Digest 只剩計數（`unkeyed_count`），身分與原因不在輸出（§C-5）。
- 單組撰寫與自測；未經非作者 QA。Digest NOT READY；OneBrain 正式廣度 NOT EVALUATED。
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from src.data.portfolio import gsheet_portfolio as _gsp   # L3 → L1（正常方向；只用 public 型別／常數／純函式）

# ══════════════════════════════════════════════════════════════════════
# 固定原因碼（字串只含小寫英文與底線：⛔ 不含代號、組合名、sheet_id、身分、任何數字）
# ══════════════════════════════════════════════════════════════════════
REASON_READ_EXCEPTION_LOGIN_REQUIRED = "read_exception_login_required"
REASON_READ_EXCEPTION_PERMISSION_DENIED = "read_exception_permission_denied"
REASON_READ_EXCEPTION_SHEET_NOT_FOUND = "read_exception_sheet_not_found"
REASON_READ_EXCEPTION_QUOTA_EXCEEDED = "read_exception_quota_exceeded"
REASON_READ_EXCEPTION_NETWORK = "read_exception_network"
REASON_READ_EXCEPTION_WORKSHEET_MISSING = "read_exception_worksheet_missing"
REASON_READ_EXCEPTION_SCHEMA_MISMATCH = "read_exception_schema_mismatch"
REASON_READ_EXCEPTION_OTHER = "read_exception_other"
REASON_NOT_SELECTED = "not_selected"
REASON_READ_STATUS_WORKSHEET_MISSING = "read_status_worksheet_missing"
REASON_READ_STATUS_SCHEMA_MISMATCH = "read_status_schema_mismatch"
REASON_READ_STATUS_EMPTY = "read_status_empty"
REASON_READ_STATUS_OTHER = "read_status_other"
REASON_COUNTS_UNKNOWN = "counts_unknown"
REASON_TALLY_INCONSISTENT = "tally_inconsistent"
REASON_ZERO_ROWS = "zero_rows"
REASON_EX_DROPPED_BLANK_TICKER = "ex_dropped_blank_ticker"
REASON_EX_DROPPED_NON_NUMERIC = "ex_dropped_non_numeric"
REASON_EX_DROPPED_NON_FINITE = "ex_dropped_non_finite"
REASON_EX_DROPPED_NON_POSITIVE = "ex_dropped_non_positive"
REASON_NON_FINITE_KEPT = "non_finite_kept"
REASON_DUPLICATE_TICKERS = "duplicate_tickers"
REASON_IN_U_BLANK_DROPPED = "in_u_blank_dropped"
REASON_IN_U_BLANK_KEPT = "in_u_blank_kept"
REASON_UNIVERSE_NOT_INDEPENDENT = "universe_not_independent"

#: 全部原因碼，**順序即輸出排序**（`reasons` 依此去重排序，穩定、與發現順序無關）。
ALL_REASONS: tuple = (
    REASON_READ_EXCEPTION_LOGIN_REQUIRED, REASON_READ_EXCEPTION_PERMISSION_DENIED,
    REASON_READ_EXCEPTION_SHEET_NOT_FOUND, REASON_READ_EXCEPTION_QUOTA_EXCEEDED, REASON_READ_EXCEPTION_NETWORK,
    REASON_READ_EXCEPTION_WORKSHEET_MISSING, REASON_READ_EXCEPTION_SCHEMA_MISMATCH, REASON_READ_EXCEPTION_OTHER,
    REASON_NOT_SELECTED, REASON_READ_STATUS_WORKSHEET_MISSING, REASON_READ_STATUS_SCHEMA_MISMATCH,
    REASON_READ_STATUS_EMPTY, REASON_READ_STATUS_OTHER,
    REASON_COUNTS_UNKNOWN, REASON_TALLY_INCONSISTENT, REASON_ZERO_ROWS,
    REASON_EX_DROPPED_BLANK_TICKER, REASON_EX_DROPPED_NON_NUMERIC, REASON_EX_DROPPED_NON_FINITE,
    REASON_EX_DROPPED_NON_POSITIVE, REASON_NON_FINITE_KEPT, REASON_DUPLICATE_TICKERS,
    REASON_IN_U_BLANK_DROPPED, REASON_IN_U_BLANK_KEPT, REASON_UNIVERSE_NOT_INDEPENDENT,
)
_REASON_RANK = {r: i for i, r in enumerate(ALL_REASONS)}

#: L1 `classify_read_error` 代碼 → 原因碼（`error:<型別名>` 一律歸 OTHER：⛔ 型別名不進原因碼）。
_EXCEPTION_REASON = {
    _gsp.READ_ERROR_LOGIN_REQUIRED: REASON_READ_EXCEPTION_LOGIN_REQUIRED,
    _gsp.READ_ERROR_PERMISSION_DENIED: REASON_READ_EXCEPTION_PERMISSION_DENIED,
    _gsp.READ_ERROR_SHEET_NOT_FOUND: REASON_READ_EXCEPTION_SHEET_NOT_FOUND,
    _gsp.READ_ERROR_QUOTA_EXCEEDED: REASON_READ_EXCEPTION_QUOTA_EXCEEDED,
    _gsp.READ_ERROR_NETWORK: REASON_READ_EXCEPTION_NETWORK,
    _gsp.READ_WORKSHEET_MISSING: REASON_READ_EXCEPTION_WORKSHEET_MISSING,
    _gsp.READ_SCHEMA_MISMATCH: REASON_READ_EXCEPTION_SCHEMA_MISMATCH,
}
#: 非 ok 狀態 → 原因碼（未列出的狀態一律 OTHER：⛔ 狀態字串本身不進原因碼）。
_STATUS_REASON = {
    _gsp.TALLY_NOT_SELECTED: REASON_NOT_SELECTED,
    _gsp.READ_WORKSHEET_MISSING: REASON_READ_STATUS_WORKSHEET_MISSING,
    _gsp.READ_SCHEMA_MISMATCH: REASON_READ_STATUS_SCHEMA_MISMATCH,
    _gsp.READ_EMPTY: REASON_READ_STATUS_EMPTY,
}
#: L1 EX 丟列原因（`blank_value` 屬 IN-U，另行處理）→ 原因碼。
_EX_DROP_REASON = {
    _gsp.DROP_BLANK_TICKER: REASON_EX_DROPPED_BLANK_TICKER,
    _gsp.DROP_NON_NUMERIC: REASON_EX_DROPPED_NON_NUMERIC,
    _gsp.DROP_NON_FINITE: REASON_EX_DROPPED_NON_FINITE,
    _gsp.DROP_NON_POSITIVE: REASON_EX_DROPPED_NON_POSITIVE,
}
if set(_EX_DROP_REASON) | {_gsp.DROP_BLANK_VALUE} != set(_gsp.TALLY_DROP_REASONS):   # L1 丟列原因若增減 ⇒ 匯入即炸
    raise ImportError("onebrain_holdings_adapter：L1 TALLY_DROP_REASONS 與本模組的 EX／IN-U 分類不一致，須先更新分類")

#: tally 中「ok 時必為 int」的計數欄位（`status`／`keep_blank`／`rows`／`dropped_by_reason`／`duplicate_tickers` 另驗）。
_COUNT_FIELDS = ("sheet_data_rows", "blank_rows", "blank_name_rows", "other_name_rows", "raw", "kept",
                 "kept_with_missing_value", "kept_non_finite", "kept_clean",
                 "duplicate_source_rows", "duplicate_kept_rows")


# ══════════════════════════════════════════════════════════════════════
# 結果型別
# ══════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class HoldingsAdapterResult:
    """adapter 輸出（凍結）。

    - `holdings_rows`：`None`（未知／降級）或**非空** tuple of `{'ticker': str, 'held': True}`；⛔ 永不為空 tuple。
      dict 為獨立副本，但仍是可變 dict——呼叫端不得就地改；要可改的副本用 `rows_for_digest()`。
      repr 不印（含代號，屬私人持股資訊）。
    - `reasons`：固定原因碼（`ALL_REASONS` 的子集，依其順序去重排序）。None 時必非空；list 時恆含
      `universe_not_independent`。
    - `kept_positions`：list 時＝輸出列數（＝L1 `kept`）；None 時為 None。
    - `in_u_positions`：list 時＝其中張數／均價空白的 IN-U 列數（＝L1 `kept_with_missing_value`）；None 時為 None。
    違反以上任一條 ⇒ `ValueError`（Fail Loud；訊息不含任何資料值）。
    """
    holdings_rows: tuple | None = field(repr=False)
    reasons: tuple
    kept_positions: int | None = None
    in_u_positions: int | None = None

    def __post_init__(self) -> None:
        if type(self.reasons) is not tuple or any(r not in _REASON_RANK for r in self.reasons):
            raise ValueError("HoldingsAdapterResult.reasons 必須是固定原因碼的 tuple")
        if self.reasons != _ordered(self.reasons):
            raise ValueError("HoldingsAdapterResult.reasons 必須依 ALL_REASONS 順序去重排序")
        if self.holdings_rows is None:
            if not self.reasons:
                raise ValueError("HoldingsAdapterResult：holdings_rows 為 None 時 reasons 不得為空")
            if self.kept_positions is not None or self.in_u_positions is not None:
                raise ValueError("HoldingsAdapterResult：holdings_rows 為 None 時計數必須為 None")
            return
        if type(self.holdings_rows) is not tuple or not self.holdings_rows:
            raise ValueError("HoldingsAdapterResult.holdings_rows 必須是 None 或非空 tuple（⛔ 不得以空清單冒稱零持股）")
        for row in self.holdings_rows:
            if (type(row) is not dict or set(row) != {"ticker", "held"} or row["held"] is not True
                    or type(row["ticker"]) is not str or not row["ticker"].strip()):
                raise ValueError("HoldingsAdapterResult.holdings_rows 每列必須恰為 {'ticker': 非空 str, 'held': True}")
        if REASON_UNIVERSE_NOT_INDEPENDENT not in self.reasons:
            raise ValueError("HoldingsAdapterResult：list 路徑必須標示 universe_not_independent")
        for name, v in (("kept_positions", self.kept_positions), ("in_u_positions", self.in_u_positions)):
            if type(v) is not int or v < 0:
                raise ValueError(f"HoldingsAdapterResult.{name} 在 list 路徑必須是非負 int")
        if self.kept_positions != len(self.holdings_rows):
            raise ValueError("HoldingsAdapterResult：kept_positions 與輸出列數不一致（列被丟失或灌水）")
        if self.in_u_positions > self.kept_positions:
            raise ValueError("HoldingsAdapterResult：in_u_positions 不得大於 kept_positions")
        if (self.in_u_positions > 0) != (REASON_IN_U_BLANK_KEPT in self.reasons):
            raise ValueError("HoldingsAdapterResult：in_u_positions 與 in_u_blank_kept 標示不一致")

    def rows_for_digest(self) -> list | None:
        """給 `build_decision_digest`／`assemble_digest` 的 `holdings_rows`：None 照傳；否則逐列獨立副本的 list。"""
        return None if self.holdings_rows is None else [dict(r) for r in self.holdings_rows]


# ══════════════════════════════════════════════════════════════════════
# 公開 API
# ══════════════════════════════════════════════════════════════════════
def adapt_holdings_read(read) -> HoldingsAdapterResult:
    """已注入的 L1 讀取結果（`PortfolioReadTally`）或讀取例外物件 → `HoldingsAdapterResult`（純函式）。

    ⛔ 不 re-raise 傳入的例外、不把例外吞成 0 或空清單；⛔ 不讀任何來源。其他輸入型別 ⇒ `TypeError`。
    """
    if isinstance(read, BaseException):
        return _none(_exception_reason(read))
    if type(read) is not _gsp.PortfolioReadTally:
        raise TypeError(f"adapt_holdings_read 只接受 PortfolioReadTally 或例外物件：{type(read).__name__}")
    if read.status != _gsp.READ_OK:
        return _none(_STATUS_REASON.get(read.status, REASON_READ_STATUS_OTHER))
    if any(getattr(read, f) is None for f in _COUNT_FIELDS) or read.rows is None \
            or read.dropped_by_reason is None or read.duplicate_tickers is None:
        return _none(REASON_COUNTS_UNKNOWN)
    if not _is_consistent(read):
        return _none(REASON_TALLY_INCONSISTENT)
    if read.raw == 0:
        return _none(REASON_ZERO_ROWS)
    blockers = (*_ex_evidence_reasons(read), *_duplicate_reasons(read), *_in_u_dropped_reasons(read))
    if blockers:
        return _none(*blockers)
    reasons = [REASON_UNIVERSE_NOT_INDEPENDENT]
    if read.kept_with_missing_value > 0:
        reasons.append(REASON_IN_U_BLANK_KEPT)
    return HoldingsAdapterResult(holdings_rows=_rows_for_digest(read.rows), reasons=_ordered(reasons),
                                 kept_positions=read.kept, in_u_positions=read.kept_with_missing_value)


# ══════════════════════════════════════════════════════════════════════
# 內部（各自獨立，便於突變測試逐一替換）
# ══════════════════════════════════════════════════════════════════════
def _ordered(reasons) -> tuple:
    return tuple(sorted(set(reasons), key=_REASON_RANK.__getitem__))


def _none(*reasons) -> HoldingsAdapterResult:
    return HoldingsAdapterResult(holdings_rows=None, reasons=_ordered(reasons))


def _exception_reason(exc: BaseException) -> str:
    """只看型別（經 L1 `classify_read_error`，它也只看型別與 APIError.code）；⛔ 訊息與型別名都不進原因碼。"""
    return _EXCEPTION_REASON.get(_gsp.classify_read_error(exc), REASON_READ_EXCEPTION_OTHER)


def _is_int(v) -> bool:
    return type(v) is int and v >= 0


def _is_consistent(t) -> bool:
    """ok tally 的最低限度自洽檢查（L1 正常產出必過；手工捏造／損毀的 tally ⇒ False ⇒ fail-closed）。"""
    if type(t.keep_blank) is not bool or type(t.rows) is not tuple or type(t.duplicate_tickers) is not tuple:
        return False
    if not all(_is_int(getattr(t, f)) for f in _COUNT_FIELDS):
        return False
    pairs = t.dropped_by_reason
    if type(pairs) is not tuple or not all(type(p) is tuple and len(p) == 2 for p in pairs):
        return False
    dropped = dict(pairs)
    if tuple(dropped) != tuple(_gsp.TALLY_DROP_REASONS) or not all(_is_int(v) for v in dropped.values()):
        return False
    if t.raw != t.kept + sum(dropped.values()) or t.kept != len(t.rows):
        return False
    if t.kept != t.kept_clean + t.kept_with_missing_value + t.kept_non_finite:
        return False
    if (t.keep_blank and dropped[_gsp.DROP_BLANK_VALUE] != 0) or (not t.keep_blank and t.kept_with_missing_value != 0):
        return False
    for row in t.rows:
        if not isinstance(row, Mapping):
            return False
        tk = row.get("ticker")
        if type(tk) is not str or not tk.strip() or tk != tk.strip():
            return False
    return True


def _ex_evidence_reasons(t) -> tuple:
    """EX 證據：L1 依 EX 規則丟列（`blank_value` 以外）、保留列含 NaN／+inf。"""
    dropped = dict(t.dropped_by_reason)
    out = [reason for key, reason in _EX_DROP_REASON.items() if dropped[key] > 0]
    if t.kept_non_finite > 0:
        out.append(REASON_NON_FINITE_KEPT)
    return tuple(out)


def _duplicate_reasons(t) -> tuple:
    """重複代號（L1 揭露的來源列重複，或保留列自身重複）⇒ 不得默默去重、不得逕行灌入 ⇒ 降級。"""
    tickers = [row["ticker"] for row in t.rows]
    if t.duplicate_tickers or t.duplicate_source_rows > 0 or t.duplicate_kept_rows > 0 \
            or len(set(tickers)) != len(tickers):
        return (REASON_DUPLICATE_TICKERS,)
    return ()


def _in_u_dropped_reasons(t) -> tuple:
    """預設模式下 L1 已丟掉張數／均價空白的 IN-U 列 ⇒ adapter 無從還原 ⇒ 降級。"""
    if not t.keep_blank and dict(t.dropped_by_reason)[_gsp.DROP_BLANK_VALUE] > 0:
        return (REASON_IN_U_BLANK_DROPPED,)
    return ()


def _rows_for_digest(rows) -> tuple:
    """L1 rows → Digest 持有列：每列一筆、順序不變、⛔ 不去重、⛔ 不丟 IN-U；只帶 builder 會讀的 `ticker` 與 `held`。"""
    return tuple({"ticker": row["ticker"], "held": True} for row in rows)


__all__ = ["HoldingsAdapterResult", "adapt_holdings_read", "ALL_REASONS",
           *sorted(n for n in list(globals()) if n.startswith("REASON_"))]
