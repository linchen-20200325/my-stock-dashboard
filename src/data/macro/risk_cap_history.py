"""src/data/macro/risk_cap_history.py — 每日系統風險上限「系統歷史 Sheet」的儲存端（L1；VN1-STORE 最小 PoC）。

═══ 範圍（客戶 2026-10-19 裁示 A）═══════════════════════════════════════════
「本次只核准保存方向 A 與最小 PoC；尚未核准正式 production 排程寫入。」⇒ 本檔提供：
1. `HistoryWorksheet`：最小工作表介面（`get_all_values` / `append_row`）。
2. `InMemoryWorksheet`：記憶體假表（PoC 示範冪等、測試用）。
3. `GspreadWorksheetAdapter`：包一個**呼叫端已建好**的 gspread `Worksheet` 物件 ——
   本檔**不載入任何憑證、不開任何 client**；建構時核對「試算表 ID ＝ 系統歷史 Sheet ID（環境變數）」
   且工作表名稱正確，對不上一律拒絕（含不自動寫表頭）。
4. `upsert_record(ws, row)`：冪等寫入（規則見下）。
5. `load_writer_credentials_or_refuse()`：未來排程寫入帳號的唯一入口；**本 PoC 階段一律拒絕**。

⛔ 與個人持股 Sheet 完全分離（客戶裁示第 4、5 點）：本檔不 import、也不得 import 個人持股 Sheet 的
讀取／登入模組，不讀個人持股 Sheet 的既有 SA 金鑰（`tests/test_vn1_store_poc.py` 以 AST／字串守衛）。

═══ 冪等與歷史保真規則（同一天重跑；稽核修正 2026-10-19 後的現行版）═══════════════════
鍵 ＝（`record_date`, `risk_cap_ruleset_version`）。**既有列永不修改**（本檔沒有 update API —— 只增不改）。

| 已有（同鍵）         | 本輪                         | 動作 |
|---|---|---|
| 無                    | 任何                         | 追加 |
| 有 VALID              | VALID、內容相同              | 不寫（`NOOP_DUPLICATE`） |
| 有 VALID              | VALID、內容不同              | 首筆不動；本輪以 `SAME_DAY_CONFLICT` **另記一列**（上限值空白、差異寫在原因）；同一個衝突不重複記；回 `CONFLICT_KEPT_EXISTING`（腳本以非 0 結束） |
| 任何                  | 非 VALID、內容與同鍵同狀態的最後一列相同 | 不寫（`NOOP_DUPLICATE`） |
| 任何（含已有 VALID）  | 非 VALID、內容不同           | 追加（失敗也是當天的真實事實） |
| 只有非 VALID          | VALID                        | 追加（舊列一字不動） |

⇒ 每個鍵**至多一筆 VALID**（當天第一筆有效紀錄不可變 —— 要選「哪一份比較對」等於新增判斷規則，交給人看）。
讀端（L3 `compare_status`）只拿 VALID 比較；同日較晚的失敗列／衝突列不會蓋掉或稀釋它。
「內容」只比 `CONTENT_COLUMNS`（含 `reason_detail`；不含寫入時刻／run id／來源標籤等 provenance）。

📌 稽核修正（2026-10-19，有意識的變更，不是漏刪）：修前「已有 VALID、本輪非 VALID → 不寫」與
「VALID 內容不同 → 不寫、只回衝突碼」兩條，會讓當天較晚的失敗與衝突**只留在 Actions log**（log 會過期）；
改為另記一列。修前的理由（不得蓋掉當天已成立的有效紀錄）由「既有列永不修改＋讀端只認首筆 VALID」守住。

⚠️ 併發：讀全表再追加**不是原子操作**。本 PoC 的前提是「單一寫入者」（未來排程以 workflow
`concurrency` group 序列化）；兩個寫入者同時跑仍可能各追加一筆 —— 已知限制，正式化前要處理。

分層（CLAUDE.md §8.2）：L1 —— 只 import 標準函式庫與 L0（`shared.risk_cap_history_policy`）；
⛔ 不 import streamlit、⛔ 不 import L2／L3。
"""
from __future__ import annotations

import os
from typing import Any, Iterable, Mapping, Protocol, Sequence

from shared.risk_cap_history_policy import (
    COL_EXPOSURE_LIMIT_PCT,
    COL_REASON_CODE,
    COL_REASON_DETAIL,
    COL_STATUS,
    CONTENT_COLUMNS,
    HISTORY_COLUMNS,
    HISTORY_SHEET_ID_ENV_VAR,
    HISTORY_WORKSHEET_NAME,
    IDEMPOTENCY_KEY_COLUMNS,
    PRODUCTION_WRITE_APPROVED,
    REASON_CODE_SAME_DAY_CONFLICT,
    STATUS_SAME_DAY_CONFLICT,
    STATUS_VALID,
    UPSERT_APPENDED,
    UPSERT_CONFLICT_KEPT_EXISTING,
    UPSERT_NOOP_DUPLICATE,
    WRITE_ENABLE_ENV_VAR,
    WRITER_SA_ENV_VAR,
)


class HistorySchemaMismatch(RuntimeError):
    """工作表第一列（表頭）與 `HISTORY_COLUMNS` 不一致 —— ⛔ 不猜欄位對應、不寫。"""


class HistoryRowInvalid(ValueError):
    """要寫的列缺欄、多欄或不是全字串 —— ⛔ 不補、不寫。"""


class HistoryTargetMismatch(RuntimeError):
    """要寫的試算表不是系統歷史 Sheet（ID 或工作表名稱對不上，或沒設定預期 ID）—— ⛔ 不讀、不寫。"""


class ProductionWriteNotApproved(RuntimeError):
    """production 寫入尚未核准（客戶 2026-10-19：只核准方向 A 與最小 PoC）或憑證未設定。"""


class HistoryWorksheet(Protocol):
    """最小工作表介面（gspread `Worksheet` 的子集）。所有值一律是字串。"""

    def get_all_values(self) -> list[list[str]]: ...

    def append_row(self, values: list[str]) -> Any: ...


class InMemoryWorksheet:
    """記憶體假表：PoC `--simulate-rerun` 與測試用。行為對齊 gspread（回字串、空表回 `[]`）。"""

    def __init__(self, rows: Iterable[Sequence[str]] = ()) -> None:
        self._rows: list[list[str]] = [list(r) for r in rows]
        self.append_calls = 0

    def get_all_values(self) -> list[list[str]]:
        return [list(r) for r in self._rows]

    def append_row(self, values: list[str]) -> None:
        self.append_calls += 1
        self._rows.append([str(v) for v in values])


def _worksheet_sheet_id(worksheet: Any) -> str | None:
    """gspread `Worksheet` 所屬試算表 ID（v6：`spreadsheet_id`；舊版：`spreadsheet.id`）。取不到 ⇒ None。"""
    sid = getattr(worksheet, "spreadsheet_id", None)
    if not sid:
        sid = getattr(getattr(worksheet, "spreadsheet", None), "id", None)
    return str(sid) if sid else None


class GspreadWorksheetAdapter:
    """包一個**呼叫端已建好**的 gspread `Worksheet`。⛔ 本類別不載入憑證、不開 client、不選 Sheet。

    建構時（以及每次讀寫前）核對：
      - 預期 ID 取自環境變數 `RISK_CAP_HISTORY_SHEET_ID`（`environ` 可注入）；沒設 ⇒ 拒絕；
      - worksheet 所屬試算表 ID 必須等於它；取不到或不等 ⇒ 拒絕；
      - 工作表名稱必須是 `HISTORY_WORKSHEET_NAME`。
    ⇒ 寫錯目標（例如誤傳個人持股 Sheet 的工作表）時，連讀都不讀、表頭也不會被自動寫進去。
    寫入一律 `value_input_option="RAW"`（不讓 Sheets 把 "2026-10-19"、"30" 自動轉型；讀回仍是同一個字串）。
    """

    def __init__(self, worksheet: Any, *, environ: Mapping[str, str] | None = None) -> None:
        if worksheet is None:
            raise ValueError("worksheet 不得為 None（本 PoC 不自行開 Sheet）")
        env = os.environ if environ is None else environ
        self._expected_id = env.get(HISTORY_SHEET_ID_ENV_VAR) or ""
        self._ws = worksheet
        self._verify()

    def _verify(self) -> None:
        if not self._expected_id:
            raise HistoryTargetMismatch(f"未設定 {HISTORY_SHEET_ID_ENV_VAR}（無從核對寫入目標）→ 拒絕")
        actual = _worksheet_sheet_id(self._ws)
        if actual != self._expected_id:
            raise HistoryTargetMismatch("工作表所屬試算表不是系統歷史 Sheet（ID 不符或取不到）→ 拒絕")
        title = getattr(self._ws, "title", None)
        if title != HISTORY_WORKSHEET_NAME:
            raise HistoryTargetMismatch(
                f"工作表名稱 {title!r} 不是 {HISTORY_WORKSHEET_NAME!r} → 拒絕")

    def get_all_values(self) -> list[list[str]]:
        self._verify()
        return [[str(c) for c in row] for row in self._ws.get_all_values()]

    def append_row(self, values: list[str]) -> Any:
        self._verify()
        return self._ws.append_row(list(values), value_input_option="RAW")


def _validate_row(row: Mapping[str, str]) -> None:
    keys = set(row)
    want = set(HISTORY_COLUMNS)
    if keys != want:
        raise HistoryRowInvalid(f"欄位不符：缺 {sorted(want - keys)}；多 {sorted(keys - want)}")
    bad = [k for k, v in row.items() if not isinstance(v, str)]
    if bad:
        raise HistoryRowInvalid(f"欄位值必須是字串（序列化由 L3 build_record 負責）：{bad}")


def rows_as_records(values: list[list[str]]) -> list[dict[str, str]]:
    """`get_all_values()` → 每列一個 dict。空表 → `[]`。表頭不符 → `HistorySchemaMismatch`。

    資料列欄數不足時以空字串補到表頭長度（Sheets 會省略列尾空白儲存格）；多於表頭 → 不符。
    """
    if not values:
        return []
    header = list(values[0])
    if tuple(header) != HISTORY_COLUMNS:
        raise HistorySchemaMismatch(f"表頭與 HISTORY_COLUMNS 不一致：{header!r}")
    out: list[dict[str, str]] = []
    n = len(header)
    for i, raw in enumerate(values[1:], start=2):
        if len(raw) > n:
            raise HistorySchemaMismatch(f"第 {i} 列欄數 {len(raw)} 超過表頭 {n}")
        padded = list(raw) + [""] * (n - len(raw))
        out.append(dict(zip(header, padded)))
    return out


def _key(row: Mapping[str, str]) -> tuple[str, ...]:
    return tuple(row[c] for c in IDEMPOTENCY_KEY_COLUMNS)


def _content(row: Mapping[str, str]) -> tuple[str, ...]:
    return tuple(row.get(c, "") for c in CONTENT_COLUMNS)


def _conflict_row(first_valid: Mapping[str, str], row: Mapping[str, str]) -> dict[str, str]:
    """本輪 VALID 與當天首筆 VALID 內容不同 → 衝突列：狀態改 `SAME_DAY_CONFLICT`、上限值空白，
    差異（欄名：首筆 → 本輪）寫進 `reason_detail`。其餘欄位照本輪原樣（provenance 照實）。"""
    diffs = [f"{c}：{first_valid.get(c, '')} → {row.get(c, '')}"
             for c in CONTENT_COLUMNS if c != COL_STATUS and first_valid.get(c, "") != row.get(c, "")]
    out = dict(row)
    out[COL_STATUS] = STATUS_SAME_DAY_CONFLICT
    out[COL_REASON_CODE] = REASON_CODE_SAME_DAY_CONFLICT
    out[COL_EXPOSURE_LIMIT_PCT] = ""
    out[COL_REASON_DETAIL] = ("同日已有有效紀錄（首筆不動），本輪有效結果內容不同；差異："
                              + "；".join(diffs))
    return out


def _append(ws: HistoryWorksheet, values: list[list[str]], row: Mapping[str, str]) -> None:
    if not values:
        ws.append_row(list(HISTORY_COLUMNS))
    ws.append_row([row[c] for c in HISTORY_COLUMNS])


def upsert_record(ws: HistoryWorksheet, row: Mapping[str, str]) -> str:
    """冪等寫入一列（規則見檔頭表格）。回傳 `UPSERT_*` 結果碼。⛔ 永不修改既有列。

    空表 ⇒ 先寫表頭再寫資料列。表頭不符 ⇒ `HistorySchemaMismatch`（不寫）。
    """
    _validate_row(row)
    values = ws.get_all_values()
    existing = rows_as_records(values)
    same_key = [r for r in existing if _key(r) == _key(row)]
    valid_rows = [r for r in same_key if r.get(COL_STATUS) == STATUS_VALID]

    if row[COL_STATUS] == STATUS_VALID and valid_rows:
        if _content(valid_rows[0]) == _content(row):
            print(f"[risk_cap_history] {_key(row)} 同內容重跑 → 不寫")
            return UPSERT_NOOP_DUPLICATE
        conflict = _conflict_row(valid_rows[0], row)
        if any(r.get(COL_STATUS) == STATUS_SAME_DAY_CONFLICT and _content(r) == _content(conflict)
               for r in same_key):
            print(f"[risk_cap_history] ⚠️ {_key(row)} 同一個同日衝突已記過 → 不重複記")
        else:
            _append(ws, values, conflict)
            print(f"[risk_cap_history] ⚠️ {_key(row)} 同日有效紀錄內容不同 → 首筆不動、另記衝突列（需人工查看）")
        return UPSERT_CONFLICT_KEPT_EXISTING
    if row[COL_STATUS] != STATUS_VALID:
        same_status = [r for r in same_key if r.get(COL_STATUS) == row[COL_STATUS]]
        if same_status and _content(same_status[-1]) == _content(row):
            print(f"[risk_cap_history] {_key(row)} 同一個非有效狀態重跑 → 不寫")
            return UPSERT_NOOP_DUPLICATE
    _append(ws, values, row)
    return UPSERT_APPENDED


def load_writer_credentials_or_refuse(environ: Mapping[str, str] | None = None) -> None:
    """未來排程寫入帳號的**唯一**入口。本 PoC 階段：**一律拒絕**（`ProductionWriteNotApproved`）。

    拒絕順序（訊息照實講卡在哪）：
      1. `PRODUCTION_WRITE_APPROVED` 為 False（L0；改它需要客戶另一次裁示，DEC-009）；
      2. `RISK_CAP_HISTORY_WRITE_ENABLED` 沒設成 "1"；
      3. 寫入 SA（`RISK_CAP_HISTORY_WRITER_SA_JSON`）或 Sheet ID（`RISK_CAP_HISTORY_SHEET_ID`）沒設。
    ⛔ 不讀個人持股 Sheet 的既有 SA 金鑰；⛔ 不讀 `st.secrets`；⛔ 不讀網站讀取端的金鑰名稱。
    即使 1~3 都過了，本 PoC 也**沒有**實作建立 client —— 那屬正式化批次（需客戶核准＋新憑證）。
    """
    env = os.environ if environ is None else environ
    if not PRODUCTION_WRITE_APPROVED:
        raise ProductionWriteNotApproved(
            "系統歷史 Sheet 的 production 寫入尚未核准（客戶 2026-10-19：只核准保存方向 A 與最小 PoC）；"
            "本 PoC 不寫任何真實 Sheet。")
    if env.get(WRITE_ENABLE_ENV_VAR) != "1":
        raise ProductionWriteNotApproved(f"{WRITE_ENABLE_ENV_VAR} 未設為 1")
    missing = [k for k in (WRITER_SA_ENV_VAR, HISTORY_SHEET_ID_ENV_VAR) if not env.get(k)]
    if missing:
        raise ProductionWriteNotApproved(f"寫入憑證未設定：{missing}")
    raise ProductionWriteNotApproved("本 PoC 未實作建立寫入 client（正式化批次另案）")
