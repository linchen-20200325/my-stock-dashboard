"""src/data/risk_cap/history.py — 每日系統風險上限「系統歷史 Sheet」的儲存端（L1；VN1-STORE 最小 PoC）。

📌 2026-10-20（VN1-STORE Pre-Hardening 批；有意識的搬移，不是漏刪）：本檔原在 ~~`src/data/macro/risk_cap_history.py`~~。
   舊位置的理由（它屬總經 L1）仍成立；被權衡掉的原因：`src.data.macro` 是 eager barrel，一 import 就連帶載入
   `macro_core`（pandas／streamlit…）⇒ production 寫入 job 無法只裝 hash 鎖定的最小依賴
   （`requirements-risk-cap-writer.txt`）。新套件 `src/data/risk_cap/` ⛔ 不做 barrel／re-export shim；
   寫入路徑只載標準函式庫＋L0（`tests/test_vn1_prehardening.py` 以子行程 `sys.modules` 守衛）。

═══ 範圍（客戶 2026-10-19 裁示 A）═══════════════════════════════════════════
「本次只核准保存方向 A 與最小 PoC；尚未核准正式 production 排程寫入。」⇒ 本檔提供：
1. `HistoryWorksheet`：最小工作表介面（`get_all_values` / `append_row`）。
2. `InMemoryWorksheet`：記憶體假表（PoC 示範冪等、測試用）。
3. `GspreadWorksheetAdapter`：包一個**呼叫端已建好**的 gspread `Worksheet` 物件 ——
   本檔**不載入任何憑證、不開任何 client**；建構時核對「試算表 ID ＝ 系統歷史 Sheet ID（環境變數）」
   且工作表名稱正確，對不上一律拒絕（含不自動寫表頭）。
4. `upsert_record(ws, row)`：冪等寫入（規則見下）。
5. `load_writer_credentials_or_refuse()`：排程寫入帳號的唯一入口；`PRODUCTION_WRITE_APPROVED=False` ⇒ **一律拒絕**。

═══ Production Wiring 批（2026-10-20；production 寫入**仍未核准**）新增 ═══════════════════
6. `GspreadWorksheetAdapter(ws, expected_sheet_id=...)`：預期 Sheet ID 可由呼叫端**注入**（受信任來源：
   GitHub secret／Streamlit secrets；⛔ 不解析網址、⛔ 不吃使用者輸入）；未注入時沿用環境變數（PoC 既有行為）。
7. `open_history_worksheet(client, sheet_id)`：以 ID 開 `risk_cap_daily` 並包成 adapter；錯誤分型
   （`HistoryTabMissing`／`HistoryApiError`／`HistoryTargetMismatch`）。`read_history_records(adapter)`：
   讀全表 → `rows_as_records`（表頭不符 ⇒ `HistorySchemaMismatch`）。⛔ 不補值、⛔ 不 fillna、⛔ 不轉 0。
8. `build_reader_client(info)`：**只** `service_account.Credentials.from_service_account_info(info, READER_SCOPES)`；
   身分必須是 `risk-cap-reader`（拒 writer／fund-nav／external_account）；⛔ 永不呼叫 `google.auth.default`。
9. `build_writer_client(environ)`：先過寫入閘門（核准旗標第一個檢查）→ ADC 憑證檔必須是 WIF 的
   `external_account`（拒任何 JSON key）→ 才 `google.auth.default(scopes=WRITER_SCOPES)`；⛔ 沒有任何退路。
   reader 與 writer 憑證**不可互換**（型別、身分、scope 三重分開）。

═══ Pre-Hardening 批（2026-10-20；production 寫入**仍未核准**、以下全部**未執行**）新增 ═══════════════
10. `record_sha256`／`header_state`／`read_history_values`：一列紀錄的指紋、表頭狀態、讀全表原樣。
11. `precheck_target(values, record, *, today_tw)` → `PrecheckResult`：首次寫入前的目標檢查（空表或表頭逐字相符、
    無權限驗證殘留、同鍵不存在、日期＝今天台北、規則／schema 版本＝現行）。
12. `verify_written(values, record, run_id)` → `VerifyResult`：寫後讀回恰好一列相符、逐欄相等、表頭位置正確且唯一。
    ⛔ 兩者都是純函式、⛔ 永不刪除任何列（自動回滾未經客戶核准 —— 失敗只紅燈＋人工查看）。
13. `build_writer_client(..., scopes=READER_SCOPES)`：同一個 WIF writer 身分換唯讀 token（寫前檢查／寫後讀回用）；
    scope 只准恰好 `WRITER_SCOPES` 或 `READER_SCOPES`（`writer_scopes`）。

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
Google 套件（`gspread`／`google.auth`／`google.oauth2`）一律在函式內延遲 import（I/O 屬 L1 本分）；
⛔ 不 import streamlit、⛔ 不 import L2／L3。
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Iterable, Iterator, Mapping, Protocol, Sequence

from shared.risk_cap_history_policy import (
    COL_EXPOSURE_LIMIT_PCT,
    COL_RECORD_DATE,
    COL_RULESET_VERSION,
    COL_RUN_ID,
    COL_SCHEMA_VERSION,
    COL_REASON_CODE,
    COL_REASON_DETAIL,
    COL_STATUS,
    CONTENT_COLUMNS,
    GAC_ENV_VAR,
    HEADER_STATE_ABSENT,
    HEADER_STATE_MATCH,
    HEADER_STATE_MISMATCH,
    HISTORY_COLUMNS,
    HISTORY_SCHEMA_VERSION,
    HISTORY_SHEET_ID_ENV_VAR,
    HISTORY_WORKSHEET_NAME,
    IDEMPOTENCY_KEY_COLUMNS,
    PERMISSION_TEST_MARKER_PREFIX,
    PRECHECK_FAIL_DATE_NOT_TODAY,
    PRECHECK_FAIL_DUPLICATE_HEADER,
    PRECHECK_FAIL_HEADER_MISMATCH,
    PRECHECK_FAIL_KEY_EXISTS,
    PRECHECK_FAIL_PERMISSION_TEST_RESIDUE,
    PRECHECK_FAIL_ROW_INVALID,
    PRECHECK_FAIL_ROW_TOO_LONG,
    PRECHECK_FAIL_RULESET_VERSION,
    PRECHECK_FAIL_SCHEMA_VERSION,
    PRODUCTION_WRITE_APPROVED,
    READER_CREDENTIAL_TYPE,
    READER_SA_EMAIL,
    READER_SCOPES,
    REASON_CODE_SAME_DAY_CONFLICT,
    SHEETS_HTTP_TIMEOUT_S,
    STATUS_SAME_DAY_CONFLICT,
    STATUS_VALID,
    UPSERT_APPENDED,
    UPSERT_CONFLICT_KEPT_EXISTING,
    UPSERT_NOOP_DUPLICATE,
    VERIFY_FAIL_DUPLICATE_HEADER,
    VERIFY_FAIL_FIELD_MISMATCH,
    VERIFY_FAIL_HEADER_MISMATCH,
    VERIFY_FAIL_MULTIPLE_MATCHES,
    VERIFY_FAIL_NO_MATCH,
    VERIFY_FAIL_ROW_TOO_LONG,
    WRITE_ENABLE_ENV_VAR,
    WRITER_CREDENTIAL_TYPE,
    WRITER_SA_EMAIL,
    WRITER_SCOPES,
)
from shared.risk_cap_policy import RISK_CAP_RULESET_VERSION


class HistorySchemaMismatch(RuntimeError):
    """工作表第一列（表頭）與 `HISTORY_COLUMNS` 不一致 —— ⛔ 不猜欄位對應、不寫。"""


class HistoryRowInvalid(ValueError):
    """要寫的列缺欄、多欄或不是全字串 —— ⛔ 不補、不寫。"""


class HistoryTargetMismatch(RuntimeError):
    """要寫的試算表不是系統歷史 Sheet（ID 或工作表名稱對不上，或沒設定預期 ID）—— ⛔ 不讀、不寫。"""


class ProductionWriteNotApproved(RuntimeError):
    """production 寫入尚未核准（客戶 2026-10-19：只核准方向 A 與最小 PoC）或憑證未設定。"""


class WriterCredentialRefused(ProductionWriteNotApproved):
    """writer 憑證不合格（沒有 WIF 憑證檔、是 JSON key、身分不是 `risk-cap-writer`…）。

    是 `ProductionWriteNotApproved` 的子類：既有呼叫端（`--write` 一律 exit 2）不必改就照樣拒絕。
    ⛔ 訊息只含固定文字（不含檔案內容、檔案路徑、例外原文）。
    """


class HistoryReadError(RuntimeError):
    """讀取系統歷史 Sheet 失敗（分型見子類；L3 據此分類狀態）。訊息只含固定文字＋例外類別名。"""


class HistoryTabMissing(HistoryReadError):
    """試算表內沒有 `risk_cap_daily` 分頁。"""


class HistoryApiError(HistoryReadError):
    """Google API／傳輸／權杖錯誤。`error_type` ＝ 原例外類別名（⛔ 不帶訊息原文：可能含 URL／ID）。"""

    def __init__(self, error_type: str) -> None:
        super().__init__(f"Google API／傳輸錯誤（{error_type}）")
        self.error_type = error_type


class ReaderIdentityMismatch(RuntimeError):
    """reader 憑證身分不是 `risk-cap-reader`（含 writer、fund-nav、external_account、缺欄）—— ⛔ 不建 client。"""


class ReaderCredentialInvalid(RuntimeError):
    """reader 身分對，但 key 內容無法載入（例如 private_key 損壞）。訊息只含例外類別名。"""


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
      - 預期 ID：呼叫端注入的 `expected_sheet_id`（Production Wiring 批 2026-10-20；受信任來源 ——
        GitHub secret／Streamlit secrets，⛔ 不是使用者輸入、⛔ 不解析網址，格式不符直接拒絕）；
        未注入時取自環境變數 `RISK_CAP_HISTORY_SHEET_ID`（`environ` 可注入；PoC 既有行為）；都沒有 ⇒ 拒絕；
      - worksheet 所屬試算表 ID 必須等於它；取不到或不等 ⇒ 拒絕；
      - 工作表名稱必須是 `HISTORY_WORKSHEET_NAME`。
    ⇒ 寫錯目標（例如誤傳個人持股 Sheet 的工作表）時，連讀都不讀、表頭也不會被自動寫進去。
    寫入一律 `value_input_option="RAW"`（不讓 Sheets 把 "2026-10-19"、"30" 自動轉型；讀回仍是同一個字串）。
    """

    def __init__(self, worksheet: Any, *, expected_sheet_id: str | None = None,
                 environ: Mapping[str, str] | None = None) -> None:
        if worksheet is None:
            raise ValueError("worksheet 不得為 None（本 PoC 不自行開 Sheet）")
        if expected_sheet_id is not None:
            self._expected_id = validate_sheet_id(expected_sheet_id)
        else:
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


#: Google Sheet ID 的字元集（網址 `/d/` 與 `/edit` 之間那段）。⛔ 含 `/`、`:`、空白 ⇒ 不是純 ID（多半是貼了網址）。
_SHEET_ID_RE = re.compile(r"[A-Za-z0-9_-]+")


def validate_sheet_id(sheet_id: Any) -> str:
    """受信任來源給的 Sheet ID → 原樣回傳；不是純 ID（空、非字串、含網址字元）⇒ `HistoryTargetMismatch`。

    ⛔ 不解析網址、⛔ 不 strip 以外的任何修正（猜錯 ID ＝ 讀寫錯的試算表）。錯誤訊息 ⛔ 不含 ID 本身。
    """
    if not isinstance(sheet_id, str) or not _SHEET_ID_RE.fullmatch(sheet_id.strip()):
        raise HistoryTargetMismatch("系統歷史 Sheet ID 未設定或不是純 ID（不接受網址）→ 拒絕")
    return sheet_id.strip()


def _api_error_types() -> tuple[type[BaseException], ...]:
    """會被歸類成「Google API／傳輸錯誤」的例外類別（延遲 import；缺套件 ⇒ ImportError 照拋，⛔ 不吞）。

    ⛔ 不含一般程式錯誤（TypeError／KeyError…）—— 那是 bug，必須照樣炸（CLAUDE.md §1）。
    """
    import gspread.exceptions as gse
    import google.auth.exceptions as gae
    import requests.exceptions as rqe
    return (gse.GSpreadException, gae.GoogleAuthError, rqe.RequestException, OSError)


@contextmanager
def _classified_read_errors() -> Iterator[None]:
    """把 Google 端錯誤分型：沒有分頁 ⇒ `HistoryTabMissing`；其餘 API／傳輸 ⇒ `HistoryApiError`（只帶類別名）。"""
    import gspread.exceptions as gse
    api_types = _api_error_types()
    try:
        yield
    except gse.WorksheetNotFound:
        raise HistoryTabMissing(f"試算表內沒有 {HISTORY_WORKSHEET_NAME!r} 分頁") from None
    except HistoryReadError:
        raise
    except api_types as e:
        raise HistoryApiError(type(e).__name__) from None


def open_history_worksheet(client: Any, sheet_id: str) -> GspreadWorksheetAdapter:
    """以**受信任注入**的 Sheet ID 開系統歷史 Sheet 的 `risk_cap_daily` 分頁，包成核對過的 adapter。

    `client`：`build_reader_client`／`build_writer_client` 的回傳（gspread `Client` 介面：
    `open_by_key(id).worksheet(title)`）。⛔ 不用 `open_by_url`／`open(title)`（不解析網址、不按名稱搜尋）。
    """
    sid = validate_sheet_id(sheet_id)
    with _classified_read_errors():
        ws = client.open_by_key(sid).worksheet(HISTORY_WORKSHEET_NAME)
    return GspreadWorksheetAdapter(ws, expected_sheet_id=sid)


def read_history_records(ws: HistoryWorksheet) -> list[dict[str, str]]:
    """讀全表 → 每列一個 dict（全字串，原樣；⛔ 不補值、不轉 0）。空表 ⇒ `[]`。

    API／傳輸錯誤 ⇒ `HistoryApiError`；表頭不符 ⇒ `HistorySchemaMismatch`；目標核對不符 ⇒ `HistoryTargetMismatch`。
    """
    with _classified_read_errors():
        values = ws.get_all_values()
    return rows_as_records(values)


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


# ══════════════════════════════════════════════════════════════════════
# 首次 production 寫入的前置檢查／寫後驗證（VN1-STORE Pre-Hardening 批，2026-10-20）
# 純函式：只吃 `get_all_values()` 的結果與要寫的紀錄，⛔ 不做 I/O、⛔ 永不刪除任何列。
# 只在寫入閘門之後才會被腳本呼叫（`PRODUCTION_WRITE_APPROVED` 仍為 False ⇒ 本批不可能走到）。
# ══════════════════════════════════════════════════════════════════════
def record_sha256(record: Mapping[str, str]) -> str:
    """一列紀錄的指紋：依 `HISTORY_COLUMNS` 欄序的 `[欄名, 值]` 陣列 → 緊湊 JSON（UTF-8）→ sha256 hex。

    欄序固定、⛔ 不 sort、⛔ 不正規化值（要比對的就是「寫進去的字串」本身）。列不合 schema ⇒ `HistoryRowInvalid`。
    只印這個雜湊（⛔ 不印值）即可在 log／證據裡核對「compute 算的、寫進去的、讀回來的是同一列」。
    """
    _validate_row(record)
    payload = json.dumps([[c, record[c]] for c in HISTORY_COLUMNS], ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def header_state(values: Sequence[Sequence[str]]) -> str:
    """`get_all_values()` 的第一列 → `HEADER_STATE_ABSENT`／`MATCH`／`MISMATCH`（⛔ 不猜欄位對應）。"""
    if not values:
        return HEADER_STATE_ABSENT
    return HEADER_STATE_MATCH if tuple(values[0]) == HISTORY_COLUMNS else HEADER_STATE_MISMATCH


def read_history_values(ws: HistoryWorksheet) -> list[list[str]]:
    """讀全表原樣（全字串）；錯誤分型同 `read_history_records`。給寫前檢查／寫後驗證／reader smoke 用。"""
    with _classified_read_errors():
        return [[str(c) for c in row] for row in ws.get_all_values()]


@dataclass(frozen=True)
class PrecheckResult:
    """`precheck_target` 的結論。`failures` 為 `PRECHECK_FAIL_*`（空 ⇒ 可以寫）；`data_rows` ＝ 表頭以下的列數。"""

    failures: tuple[str, ...]
    header_state: str
    data_rows: int

    @property
    def ok(self) -> bool:
        return not self.failures


@dataclass(frozen=True)
class VerifyResult:
    """`verify_written` 的結論。`failures` 為 `VERIFY_FAIL_*`；`matches` ＝ run_id＋record_date 相符的列數；
    `mismatched_columns` ＝ 唯一相符列與紀錄不同的**欄名**（⛔ 不帶值）；`readback_sha256` ＝ 唯一相符列的
    `record_sha256`（相符列不是恰好一列 ⇒ 空字串）。"""

    failures: tuple[str, ...]
    matches: int
    mismatched_columns: tuple[str, ...] = ()
    readback_sha256: str = ""

    @property
    def ok(self) -> bool:
        return not self.failures


def _has_permission_test_residue(values: Sequence[Sequence[str]]) -> bool:
    """任一格（去頭尾空白、不分大小寫）以 `PERMISSION_TEST` 開頭 ⇒ 有殘留。從嚴：寧可誤擋、不可漏放（fail closed）。"""
    prefix = PERMISSION_TEST_MARKER_PREFIX.casefold()
    return any(str(c).strip().casefold().startswith(prefix) for row in values for c in row)


def _loose_key(row: Mapping[str, str]) -> tuple[str, ...]:
    """寫前檢查用的同鍵比對：去頭尾空白後比（既有列被手動改出空白也算同鍵 ⇒ 拒寫）。⛔ 只用於寫前檢查，
    `upsert_record` 的既有冪等語意不變。"""
    return tuple(str(v).strip() for v in _key(row))


def _data_rows_check(values: Sequence[Sequence[str]], dup_code: str, long_code: str) -> list[str]:
    """表頭正確時，資料區不得再有表頭列、不得有欄數超過表頭的列。"""
    out: list[str] = []
    rows = values[1:]
    if any(tuple(r) == HISTORY_COLUMNS for r in rows):
        out.append(dup_code)
    if any(len(r) > len(HISTORY_COLUMNS) for r in rows):
        out.append(long_code)
    return out


def _padded(raw: Sequence[str]) -> dict[str, str]:
    return dict(zip(HISTORY_COLUMNS, list(raw) + [""] * (len(HISTORY_COLUMNS) - len(raw))))


def precheck_target(values: Sequence[Sequence[str]], record: Mapping[str, str], *, today_tw: str) -> PrecheckResult:
    """首次（以及每一次）寫入前的目標檢查。全部條件都過才可以寫；**列出所有**不符項（⛔ 不短路、⛔ 不修正）。

    1. 紀錄本身合 schema（否則只回 `RECORD_ROW_INVALID`，其餘無從檢查）；
    2. 表是空的，或第一列逐字等於 schema 表頭；資料區沒有第二列表頭、沒有超長列；
    3. 表內任何一格都沒有權限驗證測試列標記（`PERMISSION_TEST…`；去頭尾空白、不分大小寫）；
    4. 同鍵（record_date, ruleset_version；去頭尾空白後比）**任何狀態**的列都不存在（首次寫入不碰既有同日紀錄）；
    5. `record_date` ＝ 寫入當下的台北日期 `today_tw`（呼叫端給；跨午夜 ⇒ 拒寫，⛔ 不改日期）；
    6. 規則版本／schema 版本 ＝ 現行常數（舊程式算的列不准寫進來）。
    """
    try:
        _validate_row(record)
    except HistoryRowInvalid:
        return PrecheckResult((PRECHECK_FAIL_ROW_INVALID,), header_state(values), max(len(values) - 1, 0))
    state = header_state(values)
    fails: list[str] = []
    if state == HEADER_STATE_MISMATCH:
        fails.append(PRECHECK_FAIL_HEADER_MISMATCH)
    if state == HEADER_STATE_MATCH:
        fails += _data_rows_check(values, PRECHECK_FAIL_DUPLICATE_HEADER, PRECHECK_FAIL_ROW_TOO_LONG)
    if _has_permission_test_residue(values):
        fails.append(PRECHECK_FAIL_PERMISSION_TEST_RESIDUE)
    if state == HEADER_STATE_MATCH and any(_loose_key(_padded(r)) == _loose_key(record) for r in values[1:]):
        fails.append(PRECHECK_FAIL_KEY_EXISTS)
    if record[COL_RECORD_DATE] != today_tw:
        fails.append(PRECHECK_FAIL_DATE_NOT_TODAY)
    if record[COL_RULESET_VERSION] != RISK_CAP_RULESET_VERSION:
        fails.append(PRECHECK_FAIL_RULESET_VERSION)
    if record[COL_SCHEMA_VERSION] != HISTORY_SCHEMA_VERSION:
        fails.append(PRECHECK_FAIL_SCHEMA_VERSION)
    return PrecheckResult(tuple(fails), state, max(len(values) - 1, 0))


def verify_written(values: Sequence[Sequence[str]], record: Mapping[str, str], run_id: str) -> VerifyResult:
    """寫後讀回驗證：表頭在第一列且唯一；`run_id`＋`record_date` 相符的列**恰好一列**，且逐欄等於紀錄。

    0 列或 ≥2 列或任一欄不同 ⇒ 失敗。⛔ 永不刪除、⛔ 不修正 —— 自動回滾未經客戶核准；失敗只能紅燈＋人工查看。
    """
    _validate_row(record)
    if header_state(values) != HEADER_STATE_MATCH:
        return VerifyResult((VERIFY_FAIL_HEADER_MISMATCH,), 0)
    fails = _data_rows_check(values, VERIFY_FAIL_DUPLICATE_HEADER, VERIFY_FAIL_ROW_TOO_LONG)
    hits = [_padded(r) for r in values[1:]
            if len(r) <= len(HISTORY_COLUMNS)
            and _padded(r)[COL_RUN_ID] == run_id and _padded(r)[COL_RECORD_DATE] == record[COL_RECORD_DATE]]
    if not hits:
        return VerifyResult(tuple(fails + [VERIFY_FAIL_NO_MATCH]), 0)
    if len(hits) > 1:
        return VerifyResult(tuple(fails + [VERIFY_FAIL_MULTIPLE_MATCHES]), len(hits))
    diff = tuple(c for c in HISTORY_COLUMNS if hits[0][c] != record[c])
    if diff:
        fails.append(VERIFY_FAIL_FIELD_MISMATCH)
    return VerifyResult(tuple(fails), 1, diff, record_sha256(hits[0]))


def assert_production_write_approved() -> None:
    """寫入閘門的**第一道**：`PRODUCTION_WRITE_APPROVED`（L0）為 False ⇒ 一律 `ProductionWriteNotApproved`。

    改它需要客戶另一次裁示（DEC-009）；⛔ 本檔沒有任何繞過它的參數或環境變數。
    """
    if not PRODUCTION_WRITE_APPROVED:
        raise ProductionWriteNotApproved(
            "系統歷史 Sheet 的 production 寫入尚未核准（客戶 2026-10-19：只核准保存方向 A 與最小 PoC）；"
            "本 PoC 不寫任何真實 Sheet。")


def check_writer_credentials_file(environ: Mapping[str, str]) -> str:
    """writer ADC 憑證檔必須是 WIF 的 `external_account`，且**不是任何 key 檔**。回傳檔案路徑。

    拒絕（`WriterCredentialRefused`）：`GOOGLE_APPLICATION_CREDENTIALS` 沒設／讀不到／不是 JSON 物件；
    型別是 `service_account`（JSON key，DEC-064 G1 禁止）或任何非 `external_account`；檔內帶 `private_key`；
    沒有 impersonation 目標，或目標不是 `risk-cap-writer`。
    ⛔ 只讀 `type`／`private_key` 是否存在／impersonation URL；⛔ 錯誤訊息不含檔案內容或解析錯誤原文。
    （`scripts/risk_cap_permission_test.py`／`risk_cap_wif_auth_check.py` 各有一份較寬的同類檢查，本批不動那兩支
    已實跑驗證過的腳本；本函式是 production 寫入路徑的唯一檢查。）
    """
    path = environ.get(GAC_ENV_VAR, "")
    if not path:
        raise WriterCredentialRefused(f"{GAC_ENV_VAR} 未設定（auth step 沒有產生 WIF 憑證檔）→ 拒絕")
    try:
        with open(path, encoding="utf-8") as fh:
            info = json.load(fh)
    except OSError:
        raise WriterCredentialRefused(f"{GAC_ENV_VAR} 指向的檔案讀不到 → 拒絕") from None
    except ValueError:
        raise WriterCredentialRefused(f"{GAC_ENV_VAR} 指向的檔案不是合法 JSON → 拒絕") from None
    if not isinstance(info, dict):
        raise WriterCredentialRefused("writer 憑證檔不是 JSON 物件 → 拒絕")
    cred_type = info.get("type")
    if cred_type == READER_CREDENTIAL_TYPE:
        raise WriterCredentialRefused("writer 憑證檔是 service_account JSON key —— writer JSON key 依 DEC-064 G1 禁止；"
                                      "只接受 WIF 產生的 external_account 憑證 → 拒絕")
    if cred_type != WRITER_CREDENTIAL_TYPE:
        raise WriterCredentialRefused(f"writer 憑證檔類型不是 {WRITER_CREDENTIAL_TYPE}（只接受 WIF 短效憑證）→ 拒絕")
    if "private_key" in info:
        raise WriterCredentialRefused("writer 憑證檔含 private_key（任何 key 檔都不接受）→ 拒絕")
    target = info.get("service_account_impersonation_url")
    if not isinstance(target, str) or f"/serviceAccounts/{WRITER_SA_EMAIL}:" not in target:
        raise WriterCredentialRefused("writer 憑證檔沒有 impersonate risk-cap-writer → 拒絕")
    return path


def load_writer_credentials_or_refuse(environ: Mapping[str, str] | None = None) -> str:
    """排程寫入帳號的**唯一**入口。`PRODUCTION_WRITE_APPROVED=False` ⇒ **一律拒絕**（`ProductionWriteNotApproved`）。

    拒絕順序（訊息照實講卡在哪；第 1 道永遠最先檢查）：
      1. `PRODUCTION_WRITE_APPROVED` 為 False（L0；改它需要客戶另一次裁示，DEC-009）；
      2. `RISK_CAP_HISTORY_WRITE_ENABLED` 沒設成 "1"；
      3. Sheet ID（`RISK_CAP_HISTORY_SHEET_ID`）沒設或不是純 ID；
      4. writer 憑證檔不是 WIF `external_account`（`check_writer_credentials_file`）。
    全部通過 ⇒ 回傳已檢查的憑證檔路徑（給 `build_writer_client`）。

    📌 2026-10-20（VN1-STORE Production Wiring 批；有意識的變更，不是漏刪）：原第 4 步
    ~~「即使 1~3 都過了：本 PoC **沒有**實作建立寫入 client —— 仍拒絕」~~ 改為真正的 WIF 憑證檔檢查，
    讓「核准之後」那條路是真的程式碼（規格第 6 節第 4 項）。舊做法的理由（未核准時絕不可能寫）由第 1 道
    `PRODUCTION_WRITE_APPROVED=False` 守住 —— 它仍是第一個檢查、本批未改它的值。
    📌 2026-10-19（WIF auth-only 批）：原「寫入 SA 的 JSON key 環境變數」檢查已移除（DEC-064 G1 禁止 writer key）。
    ⛔ 不讀個人持股 Sheet 的既有 SA 金鑰；⛔ 不讀 `st.secrets`；⛔ 不讀 reader 的 secrets 表格；⛔ 不讀任何 JSON key。
    """
    env = os.environ if environ is None else environ
    assert_production_write_approved()
    if env.get(WRITE_ENABLE_ENV_VAR) != "1":
        raise ProductionWriteNotApproved(f"{WRITE_ENABLE_ENV_VAR} 未設為 1")
    if not env.get(HISTORY_SHEET_ID_ENV_VAR):
        raise ProductionWriteNotApproved(f"寫入目標未設定：{HISTORY_SHEET_ID_ENV_VAR}")
    try:
        validate_sheet_id(env.get(HISTORY_SHEET_ID_ENV_VAR))
    except HistoryTargetMismatch:
        raise ProductionWriteNotApproved(f"寫入目標格式不符：{HISTORY_SHEET_ID_ENV_VAR} 不是純 Sheet ID") from None
    return check_writer_credentials_file(env)


def writer_scopes(scopes: Sequence[str]) -> tuple[str, ...]:
    """writer 身分可用的 scope：**只**允許恰好 `WRITER_SCOPES`（寫入）或恰好 `READER_SCOPES`（寫前檢查／寫後讀回）。

    其餘（含加 Drive、混搭、空）一律 `WriterCredentialRefused` —— ⛔ writer 身分不得拿到比試算表讀寫更大的權限。
    """
    chosen = tuple(scopes)
    if chosen not in (tuple(WRITER_SCOPES), tuple(READER_SCOPES)):
        raise WriterCredentialRefused("writer 身分只准用 spreadsheets 或 spreadsheets.readonly scope → 拒絕")
    return chosen


def build_writer_client(environ: Mapping[str, str] | None = None, *,
                        scopes: Sequence[str] = WRITER_SCOPES) -> Any:
    """WIF writer 的 gspread client。**第一步就是寫入閘門**（`load_writer_credentials_or_refuse`）。

    閘門過了才 `google.auth.default(scopes=...)` —— 而且只在行程環境的
    `GOOGLE_APPLICATION_CREDENTIALS` 就是剛檢查過的那個檔時（`google.auth.default` 只讀行程環境；
    注入的 `environ` 與行程環境不一致 ⇒ 拒絕，⛔ 不讓它去讀別的憑證）。取得的身分必須是 `risk-cap-writer`。
    ⛔ 沒有任何退路：不讀 JSON key、不讀 reader 表格、不讀 gcloud 使用者憑證、不讀 metadata server。

    📌 2026-10-20（Pre-Hardening 批；有意識的擴充，不是放寬）：新增 `scopes`，預設仍是 `WRITER_SCOPES`；
    **唯一**允許的另一個值是 `READER_SCOPES`（同一個 WIF writer 身分、唯讀 token —— 寫前檢查與寫後讀回用，
    讀的時候手上就沒有寫權限）。身分檢查不變；閘門仍是第一步（scope 檢查在閘門之後）。
    """
    env = os.environ if environ is None else environ
    path = load_writer_credentials_or_refuse(env)
    chosen = writer_scopes(scopes)
    if os.environ.get(GAC_ENV_VAR) != path:
        raise WriterCredentialRefused(f"行程環境的 {GAC_ENV_VAR} 不是剛檢查過的 WIF 憑證檔 → 拒絕")
    import google.auth

    creds, _project = google.auth.default(scopes=list(chosen))
    if getattr(creds, "service_account_email", None) != WRITER_SA_EMAIL:
        raise WriterCredentialRefused("WIF 憑證的 impersonation 身分不是 risk-cap-writer → 拒絕")
    return _authorized_client(creds)


def check_reader_identity(info: Any) -> str:
    """reader key（L3 從 Streamlit secrets 讀進來的 key/value 表格）身分檢查。回傳 client_email。

    必須：`type == "service_account"` 且 `client_email == risk-cap-reader`。
    拒絕（`ReaderIdentityMismatch`）：external_account（WIF 設定檔不可當 reader）、writer 身分、fund-nav、
    其他任何 SA、缺欄。⛔ 錯誤訊息不含 key 內容（只講是哪一類不符）。
    """
    if not isinstance(info, Mapping):
        raise ReaderIdentityMismatch("reader 憑證不是 key/value 表格 → 拒絕")
    cred_type = info.get("type")
    if cred_type == WRITER_CREDENTIAL_TYPE:
        raise ReaderIdentityMismatch("reader 憑證是 external_account（WIF 設定檔）—— reader 只接受 risk-cap-reader key → 拒絕")
    if cred_type != READER_CREDENTIAL_TYPE:
        raise ReaderIdentityMismatch("reader 憑證類型不是 service_account → 拒絕")
    email = info.get("client_email")
    if email == WRITER_SA_EMAIL:
        raise ReaderIdentityMismatch("reader 憑證是 risk-cap-writer 身分（reader／writer 不得互換）→ 拒絕")
    if isinstance(email, str) and "fund-nav" in email.lower():
        raise ReaderIdentityMismatch("reader 憑證是 fund-nav 身分（不得沿用 fund-nav）→ 拒絕")
    if email != READER_SA_EMAIL:
        raise ReaderIdentityMismatch("reader 憑證身分不是 risk-cap-reader → 拒絕")
    return email


def build_reader_client(info: Mapping[str, Any]) -> Any:
    """reader 的 gspread client：**只** `service_account.Credentials.from_service_account_info(info, READER_SCOPES)`。

    ⛔ 永不呼叫 `google.auth.default`（不讀 ADC、不讀 `GOOGLE_APPLICATION_CREDENTIALS`、不讀 metadata server）。
    建出的憑證身分必須仍是 `risk-cap-reader`、scope 必須恰好是唯讀。key 損壞 ⇒ `ReaderCredentialInvalid`（只帶類別名）。
    """
    check_reader_identity(info)
    import google.auth.exceptions as gae
    from google.oauth2 import service_account

    # 回修第 1 輪（2026-10-20）：key 內容問題（google-auth 的 `GoogleAuthError` 系列，含 `MalformedError`；
    # 以及私鑰解析的 `ValueError`）⇒ `ReaderCredentialInvalid`（L3 歸 NO_CREDENTIAL）。
    # ⛔ 不再接 `KeyError`／`TypeError`：那多半是程式 bug，必須照樣炸（CLAUDE.md §1）。
    try:
        creds = service_account.Credentials.from_service_account_info(dict(info), scopes=list(READER_SCOPES))
    except (gae.GoogleAuthError, ValueError) as e:
        raise ReaderCredentialInvalid(f"reader key 無法載入（{type(e).__name__}）") from None
    if getattr(creds, "service_account_email", None) != READER_SA_EMAIL:
        raise ReaderIdentityMismatch("reader 憑證建立後身分不是 risk-cap-reader → 拒絕")
    if tuple(getattr(creds, "scopes", None) or ()) != tuple(READER_SCOPES):
        raise ReaderIdentityMismatch("reader 憑證 scope 不是恰好 spreadsheets.readonly → 拒絕")
    return _authorized_client(creds)


def _authorized_client(creds: Any) -> Any:
    """`gspread.authorize(creds)` ＋ 每個請求的逾時（L0 `SHEETS_HTTP_TIMEOUT_S`）。reader 與 writer 共用這一支。

    📌 2026-10-20（Pre-Hardening 回修第 1 輪；有意識的變更）：gspread 預設不設逾時 ⇒ Google 端卡住時網站／排程會一直等。
    逾時屬 `requests.exceptions.Timeout` ⇒ 讀取端歸類為 `HistoryApiError`（`_api_error_types` 已含 `RequestException`）。
    """
    import gspread

    client = gspread.authorize(creds)
    client.set_timeout(SHEETS_HTTP_TIMEOUT_S)
    return client
