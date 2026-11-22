"""OneBrain：持股讀取快照 → Digest `holdings_rows` 的 **dormant** L3 純轉換（C-OB-HOLDINGS-ADAPTER-DORMANT-1）。

授權：Issue #1199 comment 7062910532（新 L3 純轉換＋合成測試）；純資料介面設計 7063534925、逐項裁定 7063710260。
契約：`docs/vnext/ONEBRAIN_HOLDINGS_INPUT_CONTRACT_2026-11-21.md`（下文 §A／§B／§C 指該文件章節）。

═══ 是什麼／不是什麼 ═══════════════════════════════════════════════════
- **是**：一個純資料型別 `HoldingsReadSnapshot`（一次持股讀取的結果摘要：讀取結局、保留列代號、丟列計數等）
  ＋一個純函式 `adapt_holdings_read(snapshot)`，輸出 `HoldingsAdapterResult`（`holdings_rows` ＋ 固定原因碼）。
- **只依賴標準庫**；⛔ 不 import 任何 `src.*`、不引用資料層的型別或函式、不讀 Sheet／OAuth／網路／檔案、不呼叫時鐘、
  不 import streamlit、不 import Digest 家族模組、不改 Digest schema、不接任何 production caller（0 caller，dormant）。
- **轉換邊界**：「資料層讀取結果 → `HoldingsReadSnapshot`」的轉換**不在本模組**，目前只存在於測試
  （`tests/test_onebrain_holdings_adapter_dormant.py`）。**快照通過驗證只代表形狀與自洽**，不代表它忠實反映來源；
  正式轉換與來源驗證待接線 Gate。

═══ 快照驗證的兩層 ═══════════════════════════════════════════════════
1. **建構期（`__post_init__`，raise）**：型別／值域／結構錯誤——未知 `outcome`、非 bool 旗標、負數或 bool 冒充的計數、
   代號非字串或含前後空白、非 ok 結局卻帶計數。⛔ 訊息不含任何資料值。
2. **adapter（回 None＋原因碼）**：形狀合法但語意不足——ok 結局卻有計數為 None ⇒ `counts_unknown`；
   跨欄不一致（列數對不上、保留模式與空白計數矛盾、保留列重複卻宣稱無重複…）⇒ `tally_inconsistent`。
   兩者刻意**不**放進建構期：它們是「來源給了不足／矛盾的資訊」，應以降級結果揭露，而非讓呼叫端崩潰。

═══ 對映規則（契約 §B1／§B2／§B3） ═══════════════════════════════════════
總則：**未知／零列回 None、不冒稱零持股或完整；已知但未評估仍保留部位；來源不完整則保守降級。**
本模組**永遠不回 `[]`**（結果型別直接拒收空 tuple）——`[]` 會讓 coverage `unkeyed_held_count` 由 None（未知）
變成 0（已知），把「不知道」偽裝成「已知沒有」（§B1）。

| 快照 | `holdings_rows` | 原因碼 |
|---|---|---|
| `outcome` 為讀取例外類（登入／權限／找不到／配額／網路／分頁／表頭／其他） | None | `read_exception_*` |
| `outcome` 為非 ok 狀態（`not_selected`／分頁不存在／表頭不符／空表／其他） | None | `not_selected`／`read_status_*` |
| ok 但任一計數或代號序列為 None | None | `counts_unknown` |
| ok 但跨欄不一致 | None | `tally_inconsistent`（fail-closed） |
| ok 且來源列數 0（§C-1 待決；保守） | None | `zero_rows` |
| ok 且有 EX 證據：空白值以外的丟列 >0、保留列含 NaN／+inf、重複代號 | None（**保守降級**） | `ex_dropped_*`／`non_finite_kept`／`duplicate_tickers` |
| ok、未保留空白值模式、且有空白值丟列（IN-U 已被丟） | None | `in_u_blank_dropped` |
| 其餘（乾淨；含保留空白值模式下張數／均價空白的 IN-U 列） | 每個保留代號一筆 `{'ticker', 'held': True}`，不去重、不丟 IN-U、順序不變 | 恆含 `universe_not_independent`；有 IN-U 列再加 `in_u_blank_kept` |

**為什麼 EX 證據要降級成 None，而不是給 list 並「揭露」？**（依據：契約 §A 註（過渡期）；下列技術理由原文保留，為作者單組判斷、未經第二組驗證）
無效列（EX 丟列、重複代號、非有限值、預設模式空白值丟列）→ None 是契約 §A 註的**過渡期**口徑（客戶裁示 #1199 comment
7071998333，#1260 合併）；§A 第 9–12 列所載 list 為目標態，揭露通道與各型解除前置（§A 註第 3 點）通過前不得改回 list（預設模式空白值丟列無從還原，永不改 list）。
Digest／coverage 目前**沒有**承載丟列、非有限值、重複代號的欄位（契約 §C-2／§C-3／§C-4，皆需 schema 放行）。若照樣給
list，四段齊備時 `DigestCoverage.is_complete` 會是 True——下游看到「完整」，實際上來源有列被剔除或值無效（§C-6）。
在沒有揭露通道之前，保守降級成「未知」是唯一不冒稱完整的做法；原因碼記錄降級理由。
- 重複代號：有鍵重複會讓 builder `ValueError(duplicate_holding_key)`，無鍵重複會被計成「另有 2 檔」（§C-3，計數單位
  未裁示）——兩者都不該由 adapter 擅自決定。
- 未保留空白值模式下丟掉的空白值列屬 IN-U（DEC-218 §一 第 1 點）：已被丟，adapter 無從還原 ⇒ None（§C-8(b)）。
- ⚠️ NOT VERIFIED（契約 §C-8）：真實 Sheet 的空白格可能被讀成 0 而落入 `non_positive`；在本模組會被當 EX 降級成 None。

**為什麼 list 只給 `ticker`＋`held`？** builder 只讀 `ticker`／`代號` 與 `held`（不讀張數／均價）。張數／均價是私人數值，
快照本身也不收——帶下去只增加外洩面與「看似有值」的假精度，對 Digest 零貢獻。

**`universe_not_independent` 為何恆在 list 路徑？** 來源列數與保留列同源，不是獨立應有母體（契約 §B2-1；DEC-213 I3
未落地）。依契約任何以此餵入的 Digest 都必須 incomplete，但現行 coverage 無欄位承載（§C-6；#1254 的 strict xfail 仍在）。
adapter 無法改 coverage，只能在自己的結果上**明示**，避免呼叫端把 `is_complete` 當成已證明完整。

已知限制（據實）：無時點（§C-10，本模組不補）；無鍵部位在 Digest 只剩計數（§C-5）；單組撰寫與自測，未經非作者 QA。
Digest NOT READY；OneBrain NOT READY；OneBrain 正式廣度 NOT EVALUATED。
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields

# ══════════════════════════════════════════════════════════════════════
# 快照詞彙（字串值鏡像資料層的狀態／分類代碼；一致性由測試逐值比對，漂移即紅）
# ══════════════════════════════════════════════════════════════════════
OUTCOME_OK = "ok"
OUTCOME_NOT_SELECTED = "not_selected"
OUTCOME_STATUS_WORKSHEET_MISSING = "worksheet_missing"
OUTCOME_STATUS_SCHEMA_MISMATCH = "schema_mismatch"
OUTCOME_STATUS_EMPTY = "empty"
OUTCOME_STATUS_OTHER = "status_other"
OUTCOME_EXCEPTION_LOGIN_REQUIRED = "exception_login_required"
OUTCOME_EXCEPTION_PERMISSION_DENIED = "exception_permission_denied"
OUTCOME_EXCEPTION_SHEET_NOT_FOUND = "exception_sheet_not_found"
OUTCOME_EXCEPTION_QUOTA_EXCEEDED = "exception_quota_exceeded"
OUTCOME_EXCEPTION_NETWORK = "exception_network"
OUTCOME_EXCEPTION_WORKSHEET_MISSING = "exception_worksheet_missing"
OUTCOME_EXCEPTION_SCHEMA_MISMATCH = "exception_schema_mismatch"
OUTCOME_EXCEPTION_OTHER = "exception_other"

#: 丟列原因鍵（值與順序鏡像資料層的固定五鍵；測試比對含順序）。`blank_value` 屬 IN-U，其餘屬 EX。
DROP_REASON_KEYS: tuple = ("blank_ticker", "non_numeric", "non_finite", "non_positive", "blank_value")

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

#: 非 ok 結局 → 原因碼（ok 不在表內）。
_OUTCOME_REASON = {
    OUTCOME_NOT_SELECTED: REASON_NOT_SELECTED,
    OUTCOME_STATUS_WORKSHEET_MISSING: REASON_READ_STATUS_WORKSHEET_MISSING,
    OUTCOME_STATUS_SCHEMA_MISMATCH: REASON_READ_STATUS_SCHEMA_MISMATCH,
    OUTCOME_STATUS_EMPTY: REASON_READ_STATUS_EMPTY,
    OUTCOME_STATUS_OTHER: REASON_READ_STATUS_OTHER,
    OUTCOME_EXCEPTION_LOGIN_REQUIRED: REASON_READ_EXCEPTION_LOGIN_REQUIRED,
    OUTCOME_EXCEPTION_PERMISSION_DENIED: REASON_READ_EXCEPTION_PERMISSION_DENIED,
    OUTCOME_EXCEPTION_SHEET_NOT_FOUND: REASON_READ_EXCEPTION_SHEET_NOT_FOUND,
    OUTCOME_EXCEPTION_QUOTA_EXCEEDED: REASON_READ_EXCEPTION_QUOTA_EXCEEDED,
    OUTCOME_EXCEPTION_NETWORK: REASON_READ_EXCEPTION_NETWORK,
    OUTCOME_EXCEPTION_WORKSHEET_MISSING: REASON_READ_EXCEPTION_WORKSHEET_MISSING,
    OUTCOME_EXCEPTION_SCHEMA_MISMATCH: REASON_READ_EXCEPTION_SCHEMA_MISMATCH,
    OUTCOME_EXCEPTION_OTHER: REASON_READ_EXCEPTION_OTHER,
}
ALL_OUTCOMES: tuple = (OUTCOME_OK, *_OUTCOME_REASON)

#: EX 丟列欄位 → 原因碼（空白值丟列屬 IN-U，另行處理）。
_EX_DROP_REASON = {
    "dropped_blank_ticker": REASON_EX_DROPPED_BLANK_TICKER,
    "dropped_non_numeric": REASON_EX_DROPPED_NON_NUMERIC,
    "dropped_non_finite": REASON_EX_DROPPED_NON_FINITE,
    "dropped_non_positive": REASON_EX_DROPPED_NON_POSITIVE,
}
#: 丟列原因鍵 → 快照欄位名（測試轉換器據此填欄位）。
DROP_REASON_FIELDS: dict = {k: f"dropped_{k}" for k in DROP_REASON_KEYS}


# ══════════════════════════════════════════════════════════════════════
# 快照（純資料）
# ══════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class HoldingsReadSnapshot:
    """一次「選定單一組合」持股讀取的結果摘要（凍結；純資料；不含張數、均價、組合名、sheet_id、身分）。

    欄位：
    - `outcome`：讀取結局（`ALL_OUTCOMES` 之一）。非 ok 時其餘計數／代號欄位必須全為 None（未知，⛔ 不是 0）。
    - `blank_values_retained`：來源讀取是否以「保留張數／均價空白列」模式進行（True ⇒ 空白值列保留為 IN-U）。
    - `kept_tickers`：保留列的代號，依來源順序、**不去重**（每列一個）；ok 時可為 None（＝未知）。
    - `source_row_count`：選定組合的來源列數（保留＋丟棄；與保留列**同源**，不是獨立應有母體）。
    - `dropped_blank_ticker`／`dropped_non_numeric`／`dropped_non_finite`（-inf）／`dropped_non_positive`：EX 丟列數。
    - `dropped_blank_value`：張數或均價空白而被丟的列數（IN-U；保留模式下必為 0）。
    - `kept_blank_value_count`：保留列中張數或均價空白的列數（IN-U；非保留模式下必為 0）。
    - `kept_non_finite_count`：保留列中張數或均價為 NaN／+inf 的列數（EX 證據；資料層現況只揭露不過濾）。
    - `duplicate_ticker_count`：來源列中出現 >= 2 次的相異代號數。
    驗證只到形狀與自洽（見模組 docstring）；**不代表**忠實反映來源。repr 不印代號。
    """
    outcome: str
    blank_values_retained: bool
    kept_tickers: tuple | None = field(default=None, repr=False)
    source_row_count: int | None = None
    dropped_blank_ticker: int | None = None
    dropped_non_numeric: int | None = None
    dropped_non_finite: int | None = None
    dropped_non_positive: int | None = None
    dropped_blank_value: int | None = None
    kept_blank_value_count: int | None = None
    kept_non_finite_count: int | None = None
    duplicate_ticker_count: int | None = None

    def __post_init__(self) -> None:
        if type(self.outcome) is not str or self.outcome not in ALL_OUTCOMES:
            raise ValueError("HoldingsReadSnapshot.outcome 必須是固定結局代碼之一")
        if type(self.blank_values_retained) is not bool:
            raise TypeError("HoldingsReadSnapshot.blank_values_retained 必須是 bool")
        counts = _counts(self)
        for name, v in counts.items():
            if v is not None and (type(v) is not int or v < 0):
                raise ValueError(f"HoldingsReadSnapshot.{name} 必須是 None 或非負 int")
        if self.kept_tickers is not None:
            if type(self.kept_tickers) is not tuple:
                raise TypeError("HoldingsReadSnapshot.kept_tickers 必須是 None 或 tuple")
            for tk in self.kept_tickers:
                if type(tk) is not str or not tk.strip() or tk != tk.strip():
                    raise ValueError("HoldingsReadSnapshot.kept_tickers 每項必須是無前後空白的非空 str")
        if self.outcome != OUTCOME_OK and (self.kept_tickers is not None
                                           or any(v is not None for v in counts.values())):
            raise ValueError("HoldingsReadSnapshot：非 ok 結局的計數與代號必須全為 None（未知不是 0）")


_COUNT_FIELDS = tuple(f.name for f in fields(HoldingsReadSnapshot)
                      if f.name not in ("outcome", "blank_values_retained", "kept_tickers"))


def _counts(s: HoldingsReadSnapshot) -> dict:
    """快照的計數欄位 {欄名: 值}（依宣告順序；不含 outcome／旗標／代號）。"""
    d = asdict(s)
    return {n: d[n] for n in _COUNT_FIELDS}


# ══════════════════════════════════════════════════════════════════════
# 結果型別
# ══════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class HoldingsAdapterResult:
    """adapter 輸出（凍結）。

    - `holdings_rows`：`None`（未知／降級）或**非空** tuple of `{'ticker': str, 'held': True}`；⛔ 永不為空 tuple。
      dict 不得就地改；要可改的副本用 `rows_for_digest()`。repr 不印（含代號）。
    - `reasons`：固定原因碼（`ALL_REASONS` 子集，依其順序去重排序）。None 時必非空；list 時恆含 `universe_not_independent`。
    - `kept_positions`／`in_u_positions`：list 時＝輸出列數／其中 IN-U 列數；None 時皆為 None。
    違反任一條 ⇒ `ValueError`（訊息不含任何資料值）。
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
        """給 Digest 組裝的 `holdings_rows`：None 照傳；否則逐列獨立副本的 list。"""
        return None if self.holdings_rows is None else [dict(r) for r in self.holdings_rows]


# ══════════════════════════════════════════════════════════════════════
# 公開 API
# ══════════════════════════════════════════════════════════════════════
def adapt_holdings_read(snapshot: HoldingsReadSnapshot) -> HoldingsAdapterResult:
    """`HoldingsReadSnapshot` → `HoldingsAdapterResult`（純函式）。⛔ 不接受其他型別（含子類別、具同名屬性的物件）⇒ TypeError。"""
    if type(snapshot) is not HoldingsReadSnapshot:
        raise TypeError(f"adapt_holdings_read 只接受 HoldingsReadSnapshot：{type(snapshot).__name__}")
    s = snapshot
    if s.outcome != OUTCOME_OK:
        return _none(_OUTCOME_REASON[s.outcome])
    if _has_unknown(s):
        return _none(REASON_COUNTS_UNKNOWN)
    if not _is_consistent(s):
        return _none(REASON_TALLY_INCONSISTENT)
    if s.source_row_count == 0:
        return _none(REASON_ZERO_ROWS)
    blockers = (*_ex_evidence_reasons(s), *_duplicate_reasons(s), *_in_u_dropped_reasons(s))
    if blockers:
        return _none(*blockers)
    reasons = [REASON_UNIVERSE_NOT_INDEPENDENT]
    if s.kept_blank_value_count > 0:
        reasons.append(REASON_IN_U_BLANK_KEPT)
    return HoldingsAdapterResult(holdings_rows=_rows_for_digest(s.kept_tickers), reasons=_ordered(reasons),
                                 kept_positions=len(s.kept_tickers), in_u_positions=s.kept_blank_value_count)


# ══════════════════════════════════════════════════════════════════════
# 內部（各自獨立，便於突變測試逐一替換）
# ══════════════════════════════════════════════════════════════════════
def _ordered(reasons) -> tuple:
    return tuple(sorted(set(reasons), key=_REASON_RANK.__getitem__))


def _none(*reasons) -> HoldingsAdapterResult:
    return HoldingsAdapterResult(holdings_rows=None, reasons=_ordered(reasons))


def _has_unknown(s: HoldingsReadSnapshot) -> bool:
    """ok 結局但任一計數或代號序列為 None（形狀合法、語意不足）。"""
    return s.kept_tickers is None or any(v is None for v in _counts(s).values())


def _is_consistent(s: HoldingsReadSnapshot) -> bool:
    """跨欄自洽（形狀合法但彼此矛盾 ⇒ False ⇒ fail-closed）。"""
    kept = len(s.kept_tickers)
    c = _counts(s)
    dropped = sum(c[DROP_REASON_FIELDS[k]] for k in DROP_REASON_KEYS)
    if s.source_row_count != kept + dropped:
        return False
    if s.kept_blank_value_count + s.kept_non_finite_count > kept:
        return False
    if s.blank_values_retained and s.dropped_blank_value != 0:
        return False
    if not s.blank_values_retained and s.kept_blank_value_count != 0:
        return False
    if len(set(s.kept_tickers)) != kept and s.duplicate_ticker_count == 0:
        return False                      # 保留列自身就有重複，卻宣稱來源無重複代號
    return _duplicate_bound_ok(s)


def _duplicate_bound_ok(s: HoldingsReadSnapshot) -> bool:
    """每個重複代號至少占兩列「代號非空」的來源列。

    理由：重複代號只從代號非空的來源列計算（代號空白的列不構成任何代號）；而代號空白的列恰好全數歸入
    `dropped_blank_ticker`（該丟列原因判定順序第一、條件就是代號去空白後為空），故代號非空的來源列數＝
    `source_row_count − dropped_blank_ticker`，⇒ `2 × duplicate_ticker_count ≤ source_row_count − dropped_blank_ticker`。
    """
    return s.duplicate_ticker_count * 2 <= s.source_row_count - s.dropped_blank_ticker


def _ex_evidence_reasons(s: HoldingsReadSnapshot) -> tuple:
    """EX 證據：空白值以外的丟列、保留列含 NaN／+inf。"""
    c = _counts(s)
    out = [reason for name, reason in _EX_DROP_REASON.items() if c[name] > 0]
    if s.kept_non_finite_count > 0:
        out.append(REASON_NON_FINITE_KEPT)
    return tuple(out)


def _duplicate_reasons(s: HoldingsReadSnapshot) -> tuple:
    """重複代號 ⇒ 不得默默去重、不得逕行灌入 ⇒ 降級。"""
    if s.duplicate_ticker_count > 0 or len(set(s.kept_tickers)) != len(s.kept_tickers):
        return (REASON_DUPLICATE_TICKERS,)
    return ()


def _in_u_dropped_reasons(s: HoldingsReadSnapshot) -> tuple:
    """未保留空白值模式下已丟掉 IN-U 列 ⇒ 無從還原 ⇒ 降級。"""
    if not s.blank_values_retained and s.dropped_blank_value > 0:
        return (REASON_IN_U_BLANK_DROPPED,)
    return ()


def _rows_for_digest(tickers) -> tuple:
    """保留代號 → Digest 持有列：每個一筆、順序不變、⛔ 不去重、⛔ 不丟 IN-U；只帶 `ticker` 與 `held`。"""
    return tuple({"ticker": tk, "held": True} for tk in tickers)


#: 公開 API（`REASON_*`／`OUTCOME_*` 常數亦為公開，依名稱前綴辨識）。
__all__ = [
    "ALL_OUTCOMES",
    "ALL_REASONS",
    "DROP_REASON_FIELDS",
    "DROP_REASON_KEYS",
    "HoldingsAdapterResult",
    "HoldingsReadSnapshot",
    "adapt_holdings_read",
]
