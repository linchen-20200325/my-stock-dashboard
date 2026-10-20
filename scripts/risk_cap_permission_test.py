#!/usr/bin/env python3
"""scripts/risk_cap_permission_test.py — VN1-STORE「Sheet 權限驗證 Gate」：P1／P2／R1／R2／R3。

依據：`docs/vnext/VN1_STORE_CREDENTIAL_SPEC.md` 第 5 節（P1／P2／R1～R5 語意的**唯一**依據）；
DEC-064 G1／G2；客戶 2026-10-20 決策（reader 測試用一次性例外 secret、R1 安全解讀、P1 只寫一列測試列並立刻刪除）。
⛔ production 寫入**仍未核准**（DEC-063）—— 本腳本不寫任何正式歷史、不改 Risk Cap 公式或語意。

兩個子命令（只在 `.github/workflows/risk_cap_history_poc.yml` 對應 job 內有意義）::

    python scripts/risk_cap_permission_test.py writer   # P1 + R1（WIF writer 身分，job `permission_test_writer`）
    python scripts/risk_cap_permission_test.py reader   # P2 + R2 + R3（一次性 reader 測試 key，job `permission_test_reader`）

writer（scope＝`WRITER_SCOPES`）
-------------------------------
1. **R1（先做）**：對每個非空的個人持股 Sheet ID **只發唯讀 GET**（`spreadsheets/{id}?fields=spreadsheetId`）。
   403 PERMISSION_DENIED（且 reason 不是 API 未啟用／scope 不足／API key 類）或 404 NOT_FOUND ⇒ PASS
   （連讀都不行 ⇒ 不可能寫；客戶 R1 安全解讀）。⛔ 永不對持股 Sheet 發任何非 GET 請求（`GuardedSheets` 硬擋）。
   任何 R1 為 FAIL（2xx ⇒ writer 讀得到持股 Sheet）⇒ **立刻停下，不做 P1**。
2. **P1**：只在 System Risk Cap Sheet 的工作表 `risk_cap_daily`：
   (i) 讀 metadata 找到該工作表的 sheetId（找不到 ⇒ FAIL）；
   (ii) `values:append` 一列測試列 `["PERMISSION_TEST", <run id>, <UTC ISO>, 說明]`（RAW／INSERT_ROWS），
        由回應的 `updates.updatedRange` 解析列號（必須恰好是 `A{r}:D{r}`）；
   (iii) 讀回該範圍、逐格比對；
   (iv) `finally` 一律清理：刪除前**再讀一次**該列，A 欄＝標記且 B 欄＝本次 run id 才刪；不符 ⇒ 不刪那一列，
        改在整個分頁 A:B 搜尋「標記＋run id」，**恰好一列**才刪那一列，否則 FAIL 並印人工清理指引（不含 Sheet ID）；
        刪除用 `batchUpdate deleteDimension ROWS [r-1, r)` —— ⛔ 不清除範圍、⛔ 不動其他任何一列；
   (v) 再讀 A:B 確認標記列已不存在。四步全部成功才 PASS。

reader（scope 恰好 `spreadsheets.readonly`）
-------------------------------------------
- **P2**：讀 System Risk Cap Sheet metadata 與 `risk_cap_daily!A1:Z5` ⇒ 都 200 才 PASS（只回報列數；空分頁也算 PASS）。
- **R2**：對持股 Sheet 只發 GET，判定同 R1。
- **R3**：對 `risk_cap_daily` 嘗試 append 標記列 ⇒ 只有 403 PERMISSION_DENIED 才 PASS；
  預期 reason＝ACCESS_TOKEN_SCOPE_INSUFFICIENT（scope 層擋下）—— 檢視者 ACL 層**沒有被單獨驗到**
  （reader 永遠不得持有寫入 scope）。2xx ⇒ FAIL 並印人工清理指引。

輸出（只有這些）：測試 ID、判定、HTTP 狀態碼、Google error.status、error.details[].reason、身分 email、固定說明文字。
⛔ 不印任何 Sheet ID、token、憑證內容、回應內文（除上述欄位）、例外訊息（只印例外類別名）。

結束碼：0 ＝ 全部 PASS；1 ＝ 任一 FAIL／INCONCLUSIVE／SKIPPED；2 ＝ 前置條件被拒（REFUSED，未發任何 Sheets 請求）。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import quote

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

# L0 SSOT（只 import 標準函式庫）：scope、工作表名、System Risk Cap Sheet ID 的環境變數名。
from shared.risk_cap_history_policy import (  # noqa: E402
    HISTORY_SHEET_ID_ENV_VAR,
    HISTORY_WORKSHEET_NAME,
    READER_SCOPES,
    WRITER_SCOPES,
)

EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_REFUSED = 2

PASS = "PASS"
FAIL = "FAIL"
INCONCLUSIVE = "INCONCLUSIVE"
SKIPPED = "SKIPPED"

#: 客戶設定的固定身分（DEC-064；不是 secret）。
WRITER_SA = "risk-cap-writer@mystock20260823.iam.gserviceaccount.com"
READER_SA = "risk-cap-reader@mystock20260823.iam.gserviceaccount.com"
#: reader 唯一允許的 scope（與 L0 `READER_SCOPES` 雙重核對；不一致 ⇒ REFUSED）。
READONLY_SCOPE = "https://www.googleapis.com/auth/spreadsheets.readonly"
#: 客戶一次性測試例外 secret 的環境變數名（只在 reader job 注入；測後客戶刪除）。
READER_TEST_SA_JSON_ENV = "RISK_CAP_READER_TEST_SA_JSON"
#: 個人持股 Sheet ID 的環境變數名（沿用 `push_holdings_daily.yml` 的 secrets 名稱）；非空者都測，至少要一個。
HOLDINGS_ENV_VARS: tuple[str, ...] = ("PORTFOLIO_SHEET_ID", "STOCK_PORTFOLIO_SHEET_ID")
GAC_ENV_VAR = "GOOGLE_APPLICATION_CREDENTIALS"
RUN_ID_ENV_VAR = "GITHUB_RUN_ID"

SHEETS_API = "https://sheets.googleapis.com/v4/spreadsheets"
HTTP_TIMEOUT_S = 30

P1_MARKER = "PERMISSION_TEST"
P1_NOTE = "VN1-STORE P1 permission test — not Risk Cap history; auto-deleted"
R3_MARKER = "PERMISSION_TEST_R3_SHOULD_FAIL"
R3_NOTE = "VN1-STORE R3 reader write attempt — must be rejected; delete if present"

#: 這些 reason 代表「被擋在專案／API／scope 層」，不能證明 Sheet ACL 拒絕 ⇒ 反向測試不得判 PASS。
_NON_ACL_REASONS: frozenset[str] = frozenset({
    "SERVICE_DISABLED", "ACCESS_TOKEN_SCOPE_INSUFFICIENT", "USER_PROJECT_DENIED", "CONSUMER_INVALID",
    "BILLING_DISABLED", "RATE_LIMIT_EXCEEDED", "RESOURCE_EXHAUSTED",
})
_SAFE_TOKEN_RE = re.compile(r"^[A-Z0-9_]{1,64}$")


class Refused(Exception):
    """前置條件不成立 ⇒ 不發任何 Sheets 請求（exit 2）。`message` 為固定文字，⛔ 不含 secret／Sheet ID。"""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class HoldingsWriteRefused(RuntimeError):
    """程式試圖對非 System Risk Cap Sheet 發出非 GET 請求 —— 一律硬擋（⛔ 不會送出）。"""


@dataclass(frozen=True)
class CheckResult:
    """一項測試的結論（全部欄位都可以印；⛔ 沒有 Sheet ID／token／回應內文欄位）。"""

    test_id: str
    verdict: str
    http: int | None = None
    status: str = ""
    reason: str = ""
    note: str = ""


@dataclass
class Report:
    mode: str
    identity: str = ""
    refused: str = ""
    setup_error: str = ""
    results: list[CheckResult] = field(default_factory=list)
    manual_cleanup: list[str] = field(default_factory=list)

    @property
    def exit_code(self) -> int:
        if self.refused:
            return EXIT_REFUSED
        if self.setup_error or not self.results:
            return EXIT_FAIL
        return EXIT_PASS if all(r.verdict == PASS for r in self.results) else EXIT_FAIL


# ══════════════════════════════════════════════════════════════════════
# Google 錯誤判讀（只取 code／status／details[].reason；⛔ 不取 message）
# ══════════════════════════════════════════════════════════════════════
def _safe(value: Any) -> str:
    s = str(value or "")
    return s if _SAFE_TOKEN_RE.fullmatch(s) else ("?" if s else "")


def google_error(body: Any) -> tuple[str, tuple[str, ...]]:
    """Google JSON 錯誤 → (`error.status`, `error.details[].reason` 們)。不認得的格式 ⇒ ("", ())。"""
    err = body.get("error") if isinstance(body, dict) else None
    if not isinstance(err, dict):
        return "", ()
    details = err.get("details")
    reasons = tuple(_safe(d.get("reason")) for d in details
                    if isinstance(d, dict) and d.get("reason")) if isinstance(details, list) else ()
    return _safe(err.get("status")), reasons


def _non_acl(reasons: Sequence[str]) -> bool:
    return any(r in _NON_ACL_REASONS or r.startswith("API_KEY_") or r == "?" for r in reasons)


def classify_reverse_read(http: int, body: Any) -> tuple[str, str, str]:
    """R1／R2（對持股 Sheet 的唯讀 GET）判定 → (verdict, status, reason 串)。

    PASS：403 PERMISSION_DENIED 且 reason 不屬 API 未啟用／scope 不足／API key／專案層；或 404 NOT_FOUND。
    FAIL：任何 2xx（讀得到持股 Sheet）。其餘一律 INCONCLUSIVE（⛔ 不當 PASS）。
    """
    status, reasons = google_error(body)
    reason = ",".join(reasons)
    if 200 <= http < 300:
        return FAIL, status, reason
    if http == 404 and status == "NOT_FOUND":
        return PASS, status, reason
    if http == 403 and status == "PERMISSION_DENIED" and not _non_acl(reasons):
        return PASS, status, reason
    return INCONCLUSIVE, status, reason


def classify_write_denied(http: int, body: Any) -> tuple[str, str, str]:
    """R3（reader 對 System Risk Cap Sheet 寫入）判定 → (verdict, status, reason 串)。

    PASS：403 PERMISSION_DENIED，且 reason 是 ACCESS_TOKEN_SCOPE_INSUFFICIENT（scope 層，預期）或沒有任何
    非 ACL 的 reason（ACL 層）。FAIL：任何 2xx。其餘（含 403 SERVICE_DISABLED）一律 INCONCLUSIVE。
    """
    status, reasons = google_error(body)
    reason = ",".join(reasons)
    if 200 <= http < 300:
        return FAIL, status, reason
    if http == 403 and status == "PERMISSION_DENIED":
        others = [r for r in reasons if r != "ACCESS_TOKEN_SCOPE_INSUFFICIENT"]
        if not _non_acl(others):
            return PASS, status, reason
    return INCONCLUSIVE, status, reason


# ══════════════════════════════════════════════════════════════════════
# HTTP：只准對 System Risk Cap Sheet 發非 GET 請求
# ══════════════════════════════════════════════════════════════════════
def target_spreadsheet_id(url: str) -> str:
    """`{SHEETS_API}/{id}[/...|:...|?...]` → id；不是 Sheets URL ⇒ ""。"""
    prefix = SHEETS_API + "/"
    if not url.startswith(prefix):
        return ""
    return re.split(r"[/:?]", url[len(prefix):], maxsplit=1)[0]


class GuardedSheets:
    """包住 `AuthorizedSession`：非 GET 請求只准打 `write_target`（System Risk Cap Sheet），否則**不送出**直接拒絕。"""

    def __init__(self, session: Any, *, write_target: str, holdings_ids: Sequence[str]) -> None:
        self._session = session
        self._write_target = write_target
        self._holdings = frozenset(holdings_ids)

    def request(self, method: str, url: str, *, params: Mapping[str, str] | None = None,
                json_body: Any = None) -> tuple[int, Any]:
        method = method.upper()
        target = target_spreadsheet_id(url)
        if not target:
            raise HoldingsWriteRefused("只准呼叫 Sheets v4 spreadsheets 端點")
        if method != "GET" and (target != self._write_target or target in self._holdings):
            raise HoldingsWriteRefused("非 GET 請求只准打 System Risk Cap Sheet —— 拒絕送出")
        kwargs: dict[str, Any] = {"timeout": HTTP_TIMEOUT_S}
        if params:
            kwargs["params"] = dict(params)
        if json_body is not None:
            kwargs["json"] = json_body
        resp = self._session.request(method, url, **kwargs)
        try:
            body = resp.json()
        except ValueError:
            body = None
        return int(resp.status_code), body

    def get(self, url: str, params: Mapping[str, str] | None = None) -> tuple[int, Any]:
        return self.request("GET", url, params=params)

    def post(self, url: str, json_body: Any, params: Mapping[str, str] | None = None) -> tuple[int, Any]:
        return self.request("POST", url, params=params, json_body=json_body)


def _meta_url(sid: str) -> str:
    return f"{SHEETS_API}/{sid}"


def _values_url(sid: str, rng: str, suffix: str = "") -> str:
    return f"{SHEETS_API}/{sid}/values/{quote(rng, safe='!:')}{suffix}"


def _batch_url(sid: str) -> str:
    return f"{SHEETS_API}/{sid}:batchUpdate"


def _exc_note(prefix: str, exc: BaseException) -> str:
    return f"{prefix}：請求例外 {type(exc).__name__}（訊息不印，防外洩）"


# ══════════════════════════════════════════════════════════════════════
# 前置條件
# ══════════════════════════════════════════════════════════════════════
def sheet_targets(environ: Mapping[str, str]) -> tuple[str, dict[str, str]]:
    """→ (System Risk Cap Sheet ID, {持股環境變數名: ID})。不合格 ⇒ `Refused`（⛔ 訊息不含 ID）。"""
    rc = (environ.get(HISTORY_SHEET_ID_ENV_VAR) or "").strip()
    if not rc:
        raise Refused(f"{HISTORY_SHEET_ID_ENV_VAR} 未設定 → 拒絕")
    holdings = {name: (environ.get(name) or "").strip() for name in HOLDINGS_ENV_VARS}
    holdings = {k: v for k, v in holdings.items() if v}
    if not holdings:
        raise Refused(f"持股 Sheet ID（{'／'.join(HOLDINGS_ENV_VARS)}）一個都沒設 → 無法做反向測試 → 拒絕")
    if rc in holdings.values():
        raise Refused("System Risk Cap Sheet ID 與持股 Sheet ID 相同 —— 兩本 Sheet 必須完全隔離 → 拒絕")
    for v in [rc, *holdings.values()]:
        if not re.fullmatch(r"[A-Za-z0-9_\-]{10,200}", v):
            raise Refused("Sheet ID 格式不合法（只接受英數、底線、連字號）→ 拒絕")
    return rc, holdings


def _run_id(environ: Mapping[str, str]) -> str:
    rid = (environ.get(RUN_ID_ENV_VAR) or "").strip()
    if not re.fullmatch(r"\d{1,20}", rid):
        raise Refused(f"{RUN_ID_ENV_VAR} 未設定或不是數字（測試列標記需要它）→ 拒絕")
    return rid


def check_writer_credentials_file(environ: Mapping[str, str]) -> None:
    """ADC 憑證檔必須是 WIF 的 `external_account`（只讀 `type`；⛔ 不印內容）。"""
    path = environ.get(GAC_ENV_VAR, "")
    if not path:
        raise Refused(f"{GAC_ENV_VAR} 未設定（auth step 沒有產生 ADC 憑證檔）→ 拒絕")
    try:
        with open(path, encoding="utf-8") as fh:
            info = json.load(fh)
    except OSError:
        raise Refused(f"{GAC_ENV_VAR} 指向的檔案讀不到 → 拒絕") from None
    except ValueError:
        raise Refused(f"{GAC_ENV_VAR} 指向的檔案不是合法 JSON → 拒絕") from None
    if not isinstance(info, dict) or info.get("type") != "external_account":
        raise Refused("writer 憑證檔類型不是 external_account（只接受 WIF 短效憑證；writer JSON key 依 DEC-064 G1 禁止）→ 拒絕")


# ══════════════════════════════════════════════════════════════════════
# 預設依賴（測試以假物件注入）
# ══════════════════════════════════════════════════════════════════════
def _default_writer_creds(environ: Mapping[str, str]) -> Any:
    check_writer_credentials_file(environ)
    import google.auth

    creds, _project = google.auth.default(scopes=list(WRITER_SCOPES))
    return creds


def _default_reader_creds(info: Mapping[str, Any], scopes: Sequence[str]) -> Any:
    from google.oauth2 import service_account

    return service_account.Credentials.from_service_account_info(dict(info), scopes=list(scopes))


def _default_session(creds: Any) -> Any:
    from google.auth.transport.requests import AuthorizedSession

    return AuthorizedSession(creds)


WriterCredsLoader = Callable[[Mapping[str, str]], Any]
ReaderCredsFactory = Callable[[Mapping[str, Any], Sequence[str]], Any]
SessionFactory = Callable[[Any], Any]


# ══════════════════════════════════════════════════════════════════════
# 反向讀取（R1／R2）
# ══════════════════════════════════════════════════════════════════════
def reverse_read(api: GuardedSheets, test_id: str, sid: str) -> CheckResult:
    try:
        http, body = api.get(_meta_url(sid), {"fields": "spreadsheetId"})
    except Exception as e:  # noqa: BLE001 —— 只取類別名
        return CheckResult(test_id, INCONCLUSIVE, note=_exc_note("唯讀 GET", e))
    verdict, status, reason = classify_reverse_read(http, body)
    note = {PASS: "持股 Sheet 讀不到（唯讀 GET 被拒 ⇒ 也不可能寫）",
            FAIL: "⚠️⚠️ 讀得到個人持股 Sheet —— 立刻停下，移除該 SA 的分享並回報",
            INCONCLUSIVE: "錯誤不是 Sheet ACL 拒絕（API 未啟用／scope／其他）—— 不能當通過"}[verdict]
    return CheckResult(test_id, verdict, http, status, reason, note)


# ══════════════════════════════════════════════════════════════════════
# P1：append → 讀回 → 刪除 → 確認已刪
# ══════════════════════════════════════════════════════════════════════
_UPDATED_RANGE_RE = re.compile(r"^(?:'?(?P<tab>[^'!]+)'?!)?(?P<c1>[A-Z]+)(?P<r1>\d+)(?::(?P<c2>[A-Z]+)(?P<r2>\d+))?$")


def parse_updated_row(updated_range: Any, tab: str = HISTORY_WORKSHEET_NAME) -> int | None:
    """`risk_cap_daily!A5:D5` → 5；任何其他形狀（別的分頁、跨列、不是 A:D）⇒ None。"""
    m = _UPDATED_RANGE_RE.fullmatch(str(updated_range or ""))
    if not m or m.group("tab") != tab:
        return None
    r1, r2 = int(m.group("r1")), int(m.group("r2") or m.group("r1"))
    if (m.group("c1"), m.group("c2"), r1) != ("A", "D", r2) or r1 < 1:
        return None
    return r1


def _values(body: Any) -> list[list[str]]:
    vals = body.get("values") if isinstance(body, dict) else None
    if not isinstance(vals, list):
        return []
    return [[str(c) for c in row] if isinstance(row, list) else [] for row in vals]


def _range_start_row(body: Any) -> int | None:
    m = _UPDATED_RANGE_RE.fullmatch(str(body.get("range", "")) if isinstance(body, dict) else "")
    return int(m.group("r1")) if m else None


def find_marker_rows(api: GuardedSheets, sid: str, marker: str, run_id: str,
                     tab: str = HISTORY_WORKSHEET_NAME) -> list[int] | None:
    """整個分頁 A:B 找「A＝marker 且 B＝run id」的列號（1-based）。讀取失敗 ⇒ None。"""
    http, body = api.get(_values_url(sid, f"{tab}!A:B"))
    if http != 200:
        return None
    start = _range_start_row(body) if isinstance(body, dict) and body.get("range") else 1
    if start is None:
        return None
    return [start + i for i, row in enumerate(_values(body))
            if len(row) >= 2 and row[0] == marker and row[1] == run_id]


def _manual_cleanup_text(marker: str, run_id: str, tab: str = HISTORY_WORKSHEET_NAME) -> str:
    return (f"人工清理：開 System Risk Cap Sheet 的 `{tab}` 分頁，找 A 欄＝{marker}、B 欄＝{run_id} 的列，"
            "刪除那一整列（⛔ 不要動其他任何一列）")


def _delete_row(api: GuardedSheets, sid: str, sheet_id: int, row_no: int) -> bool:
    body = {"requests": [{"deleteDimension": {"range": {
        "sheetId": sheet_id, "dimension": "ROWS", "startIndex": row_no - 1, "endIndex": row_no}}}]}
    http, _ = api.post(_batch_url(sid), body)
    return 200 <= http < 300


def _cleanup(api: GuardedSheets, sid: str, sheet_id: int, run_id: str, row_no: int | None,
             append_confirmed: bool) -> tuple[bool, str]:
    """→ (清理成功?, 固定說明)。只刪「再讀一次確認是自己那一列」或「整分頁恰好一列標記」的那一列。"""
    tab = HISTORY_WORKSHEET_NAME
    target = None
    if row_no is not None:
        http, body = api.get(_values_url(sid, f"{tab}!A{row_no}:B{row_no}"))
        if http == 200 and _values(body) == [[P1_MARKER, run_id]]:
            target = row_no
    if target is None:
        hits = find_marker_rows(api, sid, P1_MARKER, run_id)
        if hits is None:
            return False, "清理前搜尋標記列失敗（未刪任何列）"
        if not hits:
            if append_confirmed:
                return False, "append 回報成功但找不到標記列（未刪任何列）"
            return True, "append 未成功，分頁內沒有標記列，無需清理"
        if len(hits) != 1:
            return False, f"分頁內標記列不只一列（{len(hits)} 列），為安全起見未刪任何列"
        target = hits[0]
    if not _delete_row(api, sid, sheet_id, target):
        return False, "deleteDimension 失敗"
    return True, "已刪除測試列"


def run_p1(api: GuardedSheets, sid: str, run_id: str, now_iso: str, manual: list[str]) -> CheckResult:
    tab = HISTORY_WORKSHEET_NAME
    # (i) 找工作表 sheetId（只讀）
    try:
        http, body = api.get(_meta_url(sid), {"fields": "sheets.properties"})
    except Exception as e:  # noqa: BLE001
        return CheckResult("P1", FAIL, note=_exc_note("讀 metadata", e))
    if http != 200:
        status, reasons = google_error(body)
        return CheckResult("P1", FAIL, http, status, ",".join(reasons), "讀 System Risk Cap Sheet metadata 失敗（未寫入）")
    sheets = body.get("sheets") if isinstance(body, dict) else None
    sheet_ids = [s["properties"].get("sheetId") for s in (sheets or [])
                 if isinstance(s, dict) and isinstance(s.get("properties"), dict)
                 and s["properties"].get("title") == tab]
    if len(sheet_ids) != 1 or not isinstance(sheet_ids[0], int):
        return CheckResult("P1", FAIL, http, note=f"找不到工作表 `{tab}`（未寫入）")
    sheet_id = sheet_ids[0]

    row = [P1_MARKER, run_id, now_iso, P1_NOTE]
    append_ok = readback_ok = False
    append_http: int | None = None
    append_status = append_reason = ""
    row_no: int | None = None
    step_note = ""
    cleanup_ok, cleanup_note = False, ""
    try:
        # (ii) append 一列測試列
        append_http, abody = api.post(
            _values_url(sid, f"{tab}!A1", ":append"),
            {"range": f"{tab}!A1", "majorDimension": "ROWS", "values": [row]},
            {"valueInputOption": "RAW", "insertDataOption": "INSERT_ROWS"})
        append_status, reasons = google_error(abody)
        append_reason = ",".join(reasons)
        if 200 <= append_http < 300:
            append_ok = True
            updates = abody.get("updates") if isinstance(abody, dict) else None
            row_no = parse_updated_row(updates.get("updatedRange") if isinstance(updates, dict) else None)
            if row_no is None:
                step_note = "append 成功但 updatedRange 不是預期的單列 A:D"
            else:
                # (iii) 讀回比對
                http, rbody = api.get(_values_url(sid, f"{tab}!A{row_no}:D{row_no}"))
                readback_ok = http == 200 and _values(rbody) == [row]
                if not readback_ok:
                    step_note = "讀回內容與寫入不符"
        else:
            step_note = "append 被拒（writer 可能未被分享為編輯者）"
    except Exception as e:  # noqa: BLE001
        step_note = _exc_note("append／讀回", e)
    finally:
        # (iv) 一律清理（只要 append 請求可能已送出）
        try:
            cleanup_ok, cleanup_note = _cleanup(api, sid, sheet_id, run_id, row_no, append_ok)
        except Exception as e:  # noqa: BLE001
            cleanup_ok, cleanup_note = False, _exc_note("清理", e)

    # (v) 確認標記列已不存在
    gone_ok = False
    try:
        hits = find_marker_rows(api, sid, P1_MARKER, run_id)
        gone_ok = hits is not None and not hits
    except Exception:  # noqa: BLE001
        gone_ok = False
    if not cleanup_ok or not gone_ok:
        manual.append(_manual_cleanup_text(P1_MARKER, run_id))

    passed = append_ok and readback_ok and cleanup_ok and gone_ok
    parts = [f"append={'ok' if append_ok else 'NG'}", f"readback={'ok' if readback_ok else 'NG'}",
             f"delete={'ok' if cleanup_ok else 'NG'}", f"verify_gone={'ok' if gone_ok else 'NG'}"]
    note = " ".join(parts) + (f"；{step_note}" if step_note else "") + (f"；{cleanup_note}" if cleanup_note else "")
    return CheckResult("P1", PASS if passed else FAIL, append_http, append_status, append_reason, note)


# ══════════════════════════════════════════════════════════════════════
# writer／reader 主流程
# ══════════════════════════════════════════════════════════════════════
def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def run_writer(environ: Mapping[str, str] | None = None, *,
               creds_loader: WriterCredsLoader = _default_writer_creds,
               session_factory: SessionFactory = _default_session,
               now_fn: Callable[[], str] = _now_iso) -> Report:
    env = os.environ if environ is None else environ
    rep = Report("writer")
    try:
        rc, holdings = sheet_targets(env)
        run_id = _run_id(env)
        creds = creds_loader(env)
    except Refused as e:
        rep.refused = e.message
        return rep
    except Exception as e:  # noqa: BLE001
        rep.setup_error = f"載入 writer 憑證失敗：{type(e).__name__}"
        return rep
    email = getattr(creds, "service_account_email", None)
    if email != WRITER_SA:
        rep.refused = "writer 憑證要 impersonate 的 SA 不是 risk-cap-writer（或沒有設定 impersonation）→ 拒絕"
        return rep
    rep.identity = WRITER_SA
    api = GuardedSheets(session_factory(creds), write_target=rc, holdings_ids=list(holdings.values()))

    for name, sid in holdings.items():
        rep.results.append(reverse_read(api, f"R1[{name}]", sid))
    if any(r.verdict == FAIL for r in rep.results):
        rep.results.append(CheckResult("P1", SKIPPED, note="R1 失敗（writer 讀得到持股 Sheet）⇒ 立刻停下，未寫入任何列"))
        return rep
    rep.results.append(run_p1(api, rc, run_id, now_fn(), rep.manual_cleanup))
    return rep


def run_reader(environ: Mapping[str, str] | None = None, *,
               creds_factory: ReaderCredsFactory = _default_reader_creds,
               session_factory: SessionFactory = _default_session) -> Report:
    env = os.environ if environ is None else environ
    rep = Report("reader")
    try:
        rc, holdings = sheet_targets(env)
        run_id = _run_id(env)
        raw = env.get(READER_TEST_SA_JSON_ENV) or ""
        if not raw.strip():
            raise Refused(f"{READER_TEST_SA_JSON_ENV} 未設定 → 拒絕")
        try:
            info = json.loads(raw)
        except ValueError:
            raise Refused(f"{READER_TEST_SA_JSON_ENV} 不是合法 JSON → 拒絕") from None
        if not isinstance(info, dict) or info.get("type") != "service_account":
            raise Refused("reader 測試憑證不是 service_account 類型 → 拒絕")
        if info.get("client_email") != READER_SA:
            raise Refused("reader 測試憑證不是 risk-cap-reader（client_email 不符）→ 拒絕")
        if tuple(READER_SCOPES) != (READONLY_SCOPE,):
            raise Refused("L0 READER_SCOPES 不是恰好 spreadsheets.readonly → 拒絕")
        try:
            creds = creds_factory(info, tuple(READER_SCOPES))
        except Exception as e:  # noqa: BLE001
            rep.setup_error = f"建立 reader 憑證失敗：{type(e).__name__}"
            return rep
        finally:
            info = None  # noqa: F841 —— 不再持有金鑰內容
        if tuple(getattr(creds, "scopes", None) or ()) != (READONLY_SCOPE,):
            raise Refused("reader 憑證 scope 不是恰好 spreadsheets.readonly → 拒絕")
        if getattr(creds, "service_account_email", None) != READER_SA:
            raise Refused("reader 憑證身分不是 risk-cap-reader → 拒絕")
    except Refused as e:
        rep.refused = e.message
        return rep
    rep.identity = READER_SA
    api = GuardedSheets(session_factory(creds), write_target=rc, holdings_ids=list(holdings.values()))
    tab = HISTORY_WORKSHEET_NAME

    # P2：metadata ＋ 前 5 列
    try:
        mh, mbody = api.get(_meta_url(rc), {"fields": "spreadsheetId"})
        vh, vbody = api.get(_values_url(rc, f"{tab}!A1:Z5"))
    except Exception as e:  # noqa: BLE001
        rep.results.append(CheckResult("P2", FAIL, note=_exc_note("讀取", e)))
    else:
        if mh == 200 and vh == 200:
            n = len(_values(vbody))
            rep.results.append(CheckResult("P2", PASS, vh, note=f"metadata=200 values=200 rows={n}"
                                           + ("（tab empty）" if n == 0 else "")))
        else:
            bad = vbody if mh == 200 else mbody
            status, reasons = google_error(bad)
            rep.results.append(CheckResult("P2", FAIL, vh if mh == 200 else mh, status, ",".join(reasons),
                                           f"metadata={mh} values={vh}"))

    # R2：持股 Sheet 只發 GET
    for name, sid in holdings.items():
        rep.results.append(reverse_read(api, f"R2[{name}]", sid))

    # R3：寫入必須被拒
    r3_row = [R3_MARKER, run_id, _now_iso(), R3_NOTE]
    try:
        http, body = api.post(_values_url(rc, f"{tab}!A1", ":append"),
                              {"range": f"{tab}!A1", "majorDimension": "ROWS", "values": [r3_row]},
                              {"valueInputOption": "RAW", "insertDataOption": "INSERT_ROWS"})
    except Exception as e:  # noqa: BLE001
        rep.results.append(CheckResult("R3", INCONCLUSIVE, note=_exc_note("append", e)))
    else:
        verdict, status, reason = classify_write_denied(http, body)
        if verdict == PASS:
            layer = "scope 層擋下" if "ACCESS_TOKEN_SCOPE_INSUFFICIENT" in reason else "ACL 層擋下"
            note = (f"寫入被拒（{layer}）；檢視者 ACL 層未被單獨驗到（reader 永遠不得持有寫入 scope）")
        elif verdict == FAIL:
            note = "⚠️⚠️ reader 寫入成功 —— 立刻停下並回報"
            rep.manual_cleanup.append(_manual_cleanup_text(R3_MARKER, run_id))
        else:
            note = "錯誤不是 PERMISSION_DENIED（或是 API 未啟用等）—— 不能當通過"
        rep.results.append(CheckResult("R3", verdict, http, status, reason, note))
    return rep


# ══════════════════════════════════════════════════════════════════════
# 輸出
# ══════════════════════════════════════════════════════════════════════
TAG = "[risk_cap_permission_test]"


def format_report(rep: Report) -> list[str]:
    lines = [f"{TAG} mode={rep.mode}"]
    if rep.refused:
        return lines + [f"{TAG} REFUSED：{rep.refused}", f"{TAG} 未發出任何 Sheets 請求"]
    if rep.identity:
        lines.append(f"{TAG} identity={rep.identity}")
    if rep.setup_error:
        lines.append(f"{TAG} FAIL：{rep.setup_error}")
    for r in rep.results:
        lines.append(f"{TAG} {r.test_id} {r.verdict} http={r.http if r.http is not None else '-'} "
                     f"status={r.status or '-'} reason={r.reason or '-'} identity={rep.identity or '-'}"
                     + (f" note={r.note}" if r.note else ""))
    for m in rep.manual_cleanup:
        lines.append(f"{TAG} ⚠️ {m}")
    lines.append(f"{TAG} ── summary ──")
    for r in rep.results:
        lines.append(f"{TAG} | {r.test_id:<32} | {r.verdict:<12} |")
    lines.append(f"{TAG} exit={rep.exit_code}")
    return lines


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="VN1-STORE Sheet 權限驗證 Gate（P1／P2／R1／R2／R3）")
    ap.add_argument("role", choices=("writer", "reader"))
    args = ap.parse_args(argv)
    rep = run_writer() if args.role == "writer" else run_reader()
    for line in format_report(rep):
        print(line)
    return rep.exit_code


if __name__ == "__main__":
    sys.exit(main())
