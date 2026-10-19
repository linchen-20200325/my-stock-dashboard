"""src/data/macro/risk_cap_history.py — 每日系統風險上限「系統歷史 Sheet」的儲存端（L1；VN1-STORE 最小 PoC）。

═══ 範圍（客戶 2026-10-19 裁示 A）═══════════════════════════════════════════
「本次只核准保存方向 A 與最小 PoC；尚未核准正式 production 排程寫入。」⇒ 本檔提供：
1. `HistoryWorksheet`：最小工作表介面（`get_all_values` / `append_row`）。
2. `InMemoryWorksheet`：記憶體假表（PoC 示範冪等、測試用）。
3. `GspreadWorksheetAdapter`：包一個**呼叫端已建好**的 gspread `Worksheet` 物件 ——
   本檔**不載入任何憑證、不開任何 client**。
4. `upsert_record(ws, row)`：冪等寫入（規則見下）。
5. `load_writer_credentials_or_refuse()`：未來排程寫入帳號的唯一入口；**本 PoC 階段一律拒絕**。

⛔ 與個人持股 Sheet 完全分離（客戶裁示第 4、5 點）：本檔不 import、也不得 import
`gsheet_portfolio` / `gsheet_sa_reader` / `oauth_state`，不讀 `GCP_SERVICE_ACCOUNT_JSON`
（`tests/test_vn1_store_poc.py` 以 AST／字串守衛）。

═══ 冪等規則（同一天重跑）══════════════════════════════════════════════════
鍵 ＝（`record_date`, `risk_cap_ruleset_version`）。選擇「最保守、又照實保留歷史」的規則：

| 已有（同鍵）       | 本輪            | 動作 | 為什麼 |
|---|---|---|---|
| 無                  | 任何            | 追加 | 第一筆 |
| 有 VALID            | VALID、內容相同 | 不寫（`NOOP_DUPLICATE`） | 重跑同一份結果 |
| 有 VALID            | VALID、內容不同 | ⛔ 不覆寫、不追加（`CONFLICT_KEPT_EXISTING`） | 當天第一筆有效紀錄**不可變**；要選「哪一份比較對」等於新增判斷規則，交給人看 |
| 有 VALID            | 非 VALID        | 不寫（`NOOP_VALID_EXISTS`） | 後來的失敗不得蓋掉／稀釋當天已成立的有效紀錄 |
| 只有非 VALID        | VALID           | **追加**（舊列一字不動） | 稍早那一輪確實失敗過 —— 那是事實，不改寫；有效紀錄另起一列 |
| 只有非 VALID        | 非 VALID、內容與該鍵最後一列相同 | 不寫（`NOOP_DUPLICATE`） | 重跑同一個失敗 |
| 只有非 VALID        | 非 VALID、內容不同 | 追加 | 不同的失敗原因是新的事實 |

⇒ 每個鍵**至多一筆 VALID**；既有列**永不修改**（本檔沒有 update API —— 只增不改）。
「內容」只比 `CONTENT_COLUMNS`（不含寫入時刻／run id 等 provenance）。

⚠️ 併發：讀全表再追加**不是原子操作**。本 PoC 的前提是「單一寫入者」（未來排程以 workflow
`concurrency` group 序列化）；兩個寫入者同時跑仍可能各追加一筆 —— 已知限制，正式化前要處理。

分層（CLAUDE.md §8.2）：L1 —— 只 import 標準函式庫與 L0（`shared.risk_cap_history_policy`）；
⛔ 不 import streamlit、⛔ 不 import L2／L3。
"""
from __future__ import annotations

import os
from typing import Any, Iterable, Mapping, Protocol, Sequence

from shared.risk_cap_history_policy import (
    CONTENT_COLUMNS,
    HISTORY_COLUMNS,
    HISTORY_SHEET_ID_ENV_VAR,
    IDEMPOTENCY_KEY_COLUMNS,
    PRODUCTION_WRITE_APPROVED,
    STATUS_VALID,
    UPSERT_APPENDED,
    UPSERT_CONFLICT_KEPT_EXISTING,
    UPSERT_NOOP_DUPLICATE,
    UPSERT_NOOP_VALID_EXISTS,
    WRITE_ENABLE_ENV_VAR,
    WRITER_SA_ENV_VAR,
)
from shared.risk_cap_history_policy import COL_STATUS


class HistorySchemaMismatch(RuntimeError):
    """工作表第一列（表頭）與 `HISTORY_COLUMNS` 不一致 —— ⛔ 不猜欄位對應、不寫。"""


class HistoryRowInvalid(ValueError):
    """要寫的列缺欄、多欄或不是全字串 —— ⛔ 不補、不寫。"""


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


class GspreadWorksheetAdapter:
    """包一個**呼叫端已建好**的 gspread `Worksheet`。⛔ 本類別不載入憑證、不開 client、不選 Sheet。

    寫入一律 `value_input_option="RAW"`（不讓 Sheets 把 "2026-10-19"、"30" 自動轉型；讀回仍是同一個字串）。
    """

    def __init__(self, worksheet: Any) -> None:
        if worksheet is None:
            raise ValueError("worksheet 不得為 None（本 PoC 不自行開 Sheet）")
        self._ws = worksheet

    def get_all_values(self) -> list[list[str]]:
        return [[str(c) for c in row] for row in self._ws.get_all_values()]

    def append_row(self, values: list[str]) -> Any:
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


def upsert_record(ws: HistoryWorksheet, row: Mapping[str, str]) -> str:
    """冪等寫入一列（規則見檔頭表格）。回傳 `UPSERT_*` 結果碼。⛔ 永不修改既有列。

    空表 ⇒ 先寫表頭再寫資料列。表頭不符 ⇒ `HistorySchemaMismatch`（不寫）。
    """
    _validate_row(row)
    values = ws.get_all_values()
    existing = rows_as_records(values)
    same_key = [r for r in existing if _key(r) == _key(row)]
    valid_rows = [r for r in same_key if r.get(COL_STATUS) == STATUS_VALID]
    new_is_valid = row[COL_STATUS] == STATUS_VALID

    if valid_rows:
        if not new_is_valid:
            print(f"[risk_cap_history] {_key(row)} 已有 VALID 紀錄 → 本輪 {row[COL_STATUS]} 不寫")
            return UPSERT_NOOP_VALID_EXISTS
        if _content(valid_rows[0]) == _content(row):
            print(f"[risk_cap_history] {_key(row)} 同內容重跑 → 不寫")
            return UPSERT_NOOP_DUPLICATE
        print(f"[risk_cap_history] ⚠️ {_key(row)} 當天已有 VALID 紀錄、本輪 VALID 內容不同 → "
              "⛔ 不覆寫、不追加（需人工查看）")
        return UPSERT_CONFLICT_KEPT_EXISTING
    if same_key and not new_is_valid and _content(same_key[-1]) == _content(row):
        print(f"[risk_cap_history] {_key(row)} 同一個非有效狀態重跑 → 不寫")
        return UPSERT_NOOP_DUPLICATE
    if not values:
        ws.append_row(list(HISTORY_COLUMNS))
    ws.append_row([row[c] for c in HISTORY_COLUMNS])
    return UPSERT_APPENDED


def load_writer_credentials_or_refuse(environ: Mapping[str, str] | None = None) -> None:
    """未來排程寫入帳號的**唯一**入口。本 PoC 階段：**一律拒絕**（`ProductionWriteNotApproved`）。

    拒絕順序（訊息照實講卡在哪）：
      1. `PRODUCTION_WRITE_APPROVED` 為 False（L0；改它需要客戶另一次裁示，DEC-009）；
      2. `RISK_CAP_HISTORY_WRITE_ENABLED` 沒設成 "1"；
      3. 寫入 SA（`RISK_CAP_HISTORY_WRITER_SA_JSON`）或 Sheet ID（`RISK_CAP_HISTORY_SHEET_ID`）沒設。
    ⛔ 不讀 `GCP_SERVICE_ACCOUNT_JSON`（個人持股 Sheet 的 SA）；⛔ 不讀 `st.secrets`。
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
