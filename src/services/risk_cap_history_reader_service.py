"""src/services/risk_cap_history_reader_service.py — 系統歷史 Sheet 的**網站讀取端**（L3；VN1-STORE Production Wiring 批）。

═══ 範圍（2026-10-20；production 寫入**仍未核准**，本檔只讀）═══════════════════════════
`read_history(...)` → `ReadResult`：
  1. 憑證**只**取自 Streamlit secrets 的 `[risk_cap_history_reader]` 表格（規格
     `docs/vnext/VN1_STORE_CREDENTIAL_SPEC.md` 步驟 8；DEC-064 G2）與頂層 `risk_cap_history_sheet_id`。
     ⛔ 沒有 `os.environ` 退路、⛔ 不讀 `[gcp_service_account]`／`google_oauth`／session `gsheet_tokens`、
     ⛔ 不讀 `GCP_SERVICE_ACCOUNT_JSON`、⛔ 不沿用 fund-nav（身分檢查在 L1 `check_reader_identity`）。
  2. 經 L1 `build_reader_client`（只 `from_service_account_info`，永不 `google.auth.default`）→
     `open_history_worksheet`（以注入的 ID 開 `risk_cap_daily`，核對 ID 與分頁名）→ `read_history_records`。
  3. 讀取狀態（`P.READ_STATUS_*`）照實分類；**只有成功（OK／EMPTY）進快取**，任何失敗 ⛔ 不快取
     （v3 §02「只快取成功結果」）：快取的內層函式失敗時**拋例外**，`st.cache_data` 不會存例外。
  4. 讀到了才算比較（L3 `risk_cap_history_service.compare_status`，⛔ 本檔不另判）：
     空表 ⇒ EMPTY ＋ `START_RECORDING`（「從今天開始記錄」—— ⛔ 不是 0、不是中性）；
     過期 ⇒ 照樣 `STALE`；讀不到 ⇒ `compare=None`（⛔ 不假裝有歷史）。
  5. 缺值原樣：列是 L1 讀回的全字串 dict，空白就是空白（⛔ 不 fillna、不補 0、不沿用前值）。
     回修第 1 輪（2026-10-20）：標 `VALID` 卻沒有可用上限值（空白／不是數字／不是有限數）的列 ⇒ 整次讀取回
     `CONTENT_SUSPECT`（資料內容疑義），⛔ 不送進比較、⛔ 不補 0、⛔ 不略過該列，且 ⛔ 不快取（在快取函式內拋）。
  6. `detail` 只含固定文字＋例外類別名：⛔ 不含 Sheet ID、key 內容、例外訊息原文。

⛔ 本批**沒有**任何畫面呼叫本檔（UI 接線屬另案、須先出線框，CLAUDE.md §-1.5.A-8）。
📌 2026-10-20（VN1-STORE Pre-Hardening 批；有意識的變更，不是漏刪）：`app.py` 開機時呼叫一次
`run_smoke_if_flagged()` —— **只**在 Streamlit secrets 頂層 `risk_cap_history_smoke` 恰好為 `true` 時，每個行程
跑一次真連線 smoke（`smoke_check`），結果只寫**一行 log**、⛔ 畫面零輸出；旗標沒開 ⇒ 零 Google 呼叫。
smoke 走與 `read_history` 同一條讀取路徑（`_load_target`／`_fetch_values`／`_records_from_values`），但**繞過快取**
（量的是「現在連得上嗎」）；log 只含狀態字彙、布林、計數、最新列的日期／run id／sha256 —— ⛔ 不含任何儲存格值、
Sheet ID、例外訊息原文。

分層（CLAUDE.md §8.2）：L3 —— import L0（`shared.*`）、L1（`src.data.risk_cap.history`）、
L3（`risk_cap_history_service.compare_status`）；streamlit 依 EX-CACHE-1 慣例條件 import，
只用 `st.secrets` 與 `st.cache_data`；零 L4/L5。
"""
from __future__ import annotations

import math
import threading
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Mapping

from shared import risk_cap_history_policy as P
from shared.risk_cap_policy import RISK_CAP_RULESET_VERSION
from shared.ttls import TTL_30MIN
from src.data.risk_cap import history as L1H
from src.services.risk_cap_history_service import CompareResult, compare_status

# EX-CACHE-1 標準寫法(CLAUDE.md §8.2.A.1):條件 import,只為取 cache decorator 與 st.secrets。
try:
    import streamlit as st
except ImportError:                                   # pragma: no cover
    class _NoOpST:
        @staticmethod
        def cache_data(*args, **kwargs):
            if args and callable(args[0]):
                return args[0]
            return lambda f: f
        cache_resource = cache_data
        secrets: dict = {}
    st = _NoOpST()  # noqa

#: 讀取快取的存活時間。每日只寫一次（排程寫入後 ≤30 分鐘內畫面就看得到）；⛔ 失敗結果不進快取。
HISTORY_READ_TTL_S: int = TTL_30MIN

ReaderClientFactory = Callable[[Mapping[str, Any]], Any]


@dataclass(frozen=True)
class ReadResult:
    """`read_history` 的結論。

    status：`P.READ_STATUS_*`。rows：讀到的列（全字串 dict，原樣；讀失敗為空 tuple）。
    compare：只有 OK／EMPTY 才有（`compare_status` 的結論）；讀失敗為 None（⛔ 不假裝有歷史）。
    detail：給人看的原因（固定文字＋例外類別名；⛔ 不含 secret／Sheet ID／例外訊息原文）。
    """

    status: str
    rows: tuple[Mapping[str, str], ...] = ()
    compare: CompareResult | None = None
    detail: str = ""


class HistoryContentSuspect(RuntimeError):
    """表頭正確，但有列標 VALID 卻沒有可用上限值。`sheet_rows` ＝ 試算表列號（表頭是第 1 列）。"""

    def __init__(self, sheet_rows: tuple[int, ...]) -> None:
        super().__init__(f"VALID 列沒有可用上限值：第 {sheet_rows} 列")
        self.sheet_rows = sheet_rows


def _usable_limit(value: str) -> bool:
    """上限值字串能否解析成有限數字（⛔ 只判「是不是數字」—— 不設範圍、不新增任何門檻）。"""
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _check_valid_rows(records: list[dict[str, str]]) -> None:
    """VALID 列必須帶可用上限值；任一列不符 ⇒ `HistoryContentSuspect`（列出全部不符的試算表列號）。"""
    bad = tuple(i + 2 for i, r in enumerate(records)
                if r.get(P.COL_STATUS) == P.STATUS_VALID and not _usable_limit(r.get(P.COL_EXPOSURE_LIMIT_PCT, "")))
    if bad:
        raise HistoryContentSuspect(bad)


def _log(status: str, detail: str) -> None:
    print(f"[risk_cap_history_reader] {status}：{detail}")


def _fail(status: str, detail: str) -> ReadResult:
    _log(status, detail)
    return ReadResult(status=status, detail=detail)


def _fetch_values(sheet_id: str, info: Mapping[str, Any],
                  client_factory: ReaderClientFactory) -> list[list[str]]:
    """**不快取**的讀取 I/O：建 reader client → 以注入的 ID 開 `risk_cap_daily`（核對 ID／分頁名）→ 讀全表原樣。

    快取路徑（`_fetch_records_cached`）與 smoke（`smoke_check`）共用這一支 —— 兩者讀的是同一條路徑。
    """
    client = client_factory(info)
    ws = L1H.open_history_worksheet(client, sheet_id)
    return L1H.read_history_values(ws)


def _records_from_values(values: list[list[str]]) -> list[dict[str, str]]:
    """全表原樣 → 列 dict（表頭不符 ⇒ `HistorySchemaMismatch`）＋ VALID 列內容檢查（不符 ⇒ `HistoryContentSuspect`）。"""
    records = L1H.rows_as_records(values)
    _check_valid_rows(records)              # 內容疑義也是失敗 ⇒ 在快取函式內拋（⛔ 不快取）
    return records


def _fetch_records(sheet_id: str, info: Mapping[str, Any],
                   client_factory: ReaderClientFactory) -> list[dict[str, str]]:
    """**不快取**的完整讀取（I/O ＋ 解析＋內容檢查）。失敗一律拋。"""
    return _records_from_values(_fetch_values(sheet_id, info, client_factory))


@st.cache_data(ttl=HISTORY_READ_TTL_S, show_spinner=False)
def _fetch_records_cached(sheet_id: str, reader_email: str, _info: Mapping[str, Any],
                          _client_factory: ReaderClientFactory) -> list[dict[str, str]]:
    """讀全表（只有成功才回傳 ⇒ 只有成功會被快取）。任何失敗一律**拋**（`st.cache_data` 不快取例外）。

    快取鍵只有 `sheet_id` 與 `reader_email`（底線開頭參數不進雜湊 —— key 內容 ⛔ 不參與快取鍵計算）。
    📌 2026-10-20（Pre-Hardening 批）：本體拆成不快取的 `_fetch_records`（smoke 也用它的兩段），行為不變。
    """
    return _fetch_records(sheet_id, _info, _client_factory)


def clear_read_cache() -> None:
    """清掉讀取快取（測試與日後「重新讀取」按鈕用）。無 streamlit 時為 no-op。"""
    clear = getattr(_fetch_records_cached, "clear", None)
    if callable(clear):
        clear()


def _secret_get(secrets: Any, key: str) -> Any:
    """`st.secrets.get(key)`；沒有 secrets.toml 時 streamlit 會拋 —— 由呼叫端分類（⛔ 不吞成「有值」）。"""
    return secrets.get(key)


def _load_target(src: Any) -> ReadResult | tuple[str, dict, str]:
    """secrets → （Sheet ID, reader key 表格, reader email）；任何一項不合格 ⇒ 失敗的 `ReadResult`（已記 log）。

    `read_history` 與 `smoke_check` 共用（同一條 secrets 規則；⛔ 沒有環境變數退路）。
    """
    try:
        table = _secret_get(src, P.READER_SECRETS_TABLE)
    except Exception as e:  # noqa: BLE001 —— 沒有 secrets.toml 也是「沒有 reader 憑證」，照實分類並記 log
        return _fail(P.READ_STATUS_NO_CREDENTIAL, f"Streamlit secrets 無法讀取（{type(e).__name__}）")
    if not isinstance(table, Mapping) or not table:
        return _fail(P.READ_STATUS_NO_CREDENTIAL, f"Streamlit secrets 沒有 [{P.READER_SECRETS_TABLE}] 表格")
    try:
        raw_id = _secret_get(src, P.READER_SHEET_ID_SECRET_KEY)
    except Exception as e:  # noqa: BLE001
        return _fail(P.READ_STATUS_NO_SHEET_ID, f"Streamlit secrets 無法讀取（{type(e).__name__}）")
    if raw_id is None or (isinstance(raw_id, str) and not raw_id.strip()):
        return _fail(P.READ_STATUS_NO_SHEET_ID, f"Streamlit secrets 沒有 {P.READER_SHEET_ID_SECRET_KEY}")
    try:
        sheet_id = L1H.validate_sheet_id(raw_id)
    except L1H.HistoryTargetMismatch:
        return _fail(P.READ_STATUS_NO_SHEET_ID, f"{P.READER_SHEET_ID_SECRET_KEY} 不是純 Sheet ID（不接受網址）")

    info = dict(table)
    try:
        email = L1H.check_reader_identity(info)
    except L1H.ReaderIdentityMismatch as e:
        return _fail(P.READ_STATUS_IDENTITY_MISMATCH, str(e))
    return sheet_id, info, email


#: 讀取失敗的例外 → 讀取狀態（`read_history` 與 `smoke_check` 共用；⛔ 不含一般程式錯誤 —— 那是 bug，照樣拋）。
_READ_ERRORS: tuple[type[BaseException], ...] = (
    L1H.ReaderIdentityMismatch, L1H.ReaderCredentialInvalid, L1H.HistoryTabMissing, L1H.HistorySchemaMismatch,
    L1H.HistoryApiError, L1H.HistoryTargetMismatch, HistoryContentSuspect,
)


def _read_failure(e: BaseException) -> ReadResult:
    """`_READ_ERRORS` 之一 → 失敗的 `ReadResult`（固定文字＋類別名；已記 log）。"""
    if isinstance(e, L1H.ReaderIdentityMismatch):
        return _fail(P.READ_STATUS_IDENTITY_MISMATCH, str(e))
    if isinstance(e, L1H.ReaderCredentialInvalid):
        return _fail(P.READ_STATUS_NO_CREDENTIAL, str(e))
    if isinstance(e, L1H.HistoryTabMissing):
        return _fail(P.READ_STATUS_TAB_MISSING, f"試算表內沒有 {P.HISTORY_WORKSHEET_NAME!r} 分頁")
    if isinstance(e, L1H.HistorySchemaMismatch):
        return _fail(P.READ_STATUS_SCHEMA_MISMATCH, "表頭與歷史紀錄 schema 不一致（⛔ 不猜欄位對應）")
    if isinstance(e, L1H.HistoryApiError):
        return _fail(P.READ_STATUS_API_ERROR, f"Google API／傳輸錯誤（{e.error_type}）")
    if isinstance(e, L1H.HistoryTargetMismatch):
        return _fail(P.READ_STATUS_IDENTITY_MISMATCH, "開到的試算表／分頁與系統歷史 Sheet 核對不符")
    if isinstance(e, HistoryContentSuspect):
        rows_txt = "、".join(str(n) for n in e.sheet_rows)
        return _fail(P.READ_STATUS_CONTENT_SUSPECT,
                     f"資料內容疑義：試算表第 {rows_txt} 列狀態為 VALID 但上限值空白或不是有限數字（⛔ 不比較、不補 0）")
    raise TypeError(f"不是讀取錯誤：{type(e).__name__}")   # pragma: no cover —— 只會收到 _READ_ERRORS


def read_history(*, expected_date: str, now: datetime,
                 ruleset_version: str = RISK_CAP_RULESET_VERSION,
                 secrets: Mapping[str, Any] | None = None,
                 client_factory: ReaderClientFactory | None = None) -> ReadResult:
    """讀系統歷史 Sheet → `ReadResult`（狀態、原樣列、比較結論）。

    Args:
        expected_date: 「應該要有紀錄」的台北日期（交給 `compare_status`；本檔不藏時刻門檻）。
        now: 帶時區的「現在」（7 天有效期用）。
        ruleset_version: 只比同規則版本。
        secrets: 注入用（測試）；None ⇒ `st.secrets`。⛔ 沒有環境變數退路。
        client_factory: 注入用（測試）；None ⇒ L1 `build_reader_client`。
    """
    src = st.secrets if secrets is None else secrets
    factory = L1H.build_reader_client if client_factory is None else client_factory

    target = _load_target(src)
    if isinstance(target, ReadResult):
        return target
    sheet_id, info, email = target
    try:
        records = _fetch_records_cached(sheet_id, email, info, factory)
    except _READ_ERRORS as e:
        return _read_failure(e)

    rows = tuple(dict(r) for r in records)
    cmp = compare_status(list(rows), expected_date=expected_date, ruleset_version=ruleset_version, now=now)
    if not rows:
        return ReadResult(status=P.READ_STATUS_EMPTY, rows=(), compare=cmp,
                          detail="系統歷史 Sheet 尚無任何紀錄（從今天開始記錄）")
    return ReadResult(status=P.READ_STATUS_OK, rows=rows, compare=cmp, detail="")


# ══════════════════════════════════════════════════════════════════════
# 真連線 smoke（VN1-STORE Pre-Hardening 批，2026-10-20；只寫 log、⛔ 畫面零變化）
# ══════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class SmokeResult:
    """`smoke_check` 的結論 —— **只有**下列欄位（⛔ 不帶任何儲存格值、Sheet ID、例外原文）。

    read_status：`P.READ_STATUS_*`。identity_ok：reader 身分檢查是否通過（沒走到 ⇒ None）。
    header_state：`P.HEADER_STATE_*`（沒讀到表 ⇒ `NOT_READ`）。data_rows：表頭以下列數（沒讀到 ⇒ None）。
    latest_*：表內**最後一列**（＝最後寫入的一列）的 record_date／run_id／`record_sha256`（沒有資料列 ⇒ 空字串）。
    compare_status：`compare_status` 的狀態（預期日期＝今天台北；沒讀到 ⇒ 空字串）。
    """

    read_status: str
    identity_ok: bool | None = None
    header_state: str = P.HEADER_STATE_NOT_READ
    data_rows: int | None = None
    latest_record_date: str = ""
    latest_run_id: str = ""
    latest_row_sha256: str = ""
    compare_status: str = ""

    def log_line(self) -> str:
        def _v(x: Any) -> str:
            return "-" if x is None or x == "" else str(x)
        return (f"{P.READER_SMOKE_LOG_PREFIX} read_status={self.read_status} identity_ok={_v(self.identity_ok)} "
                f"header_state={self.header_state} data_rows={_v(self.data_rows)} "
                f"latest_record_date={_v(self.latest_record_date)} latest_run_id={_v(self.latest_run_id)} "
                f"latest_row_sha256={_v(self.latest_row_sha256)} compare_status={_v(self.compare_status)}")


def smoke_check(now: datetime, *, secrets: Mapping[str, Any] | None = None,
                client_factory: ReaderClientFactory | None = None,
                ruleset_version: str = RISK_CAP_RULESET_VERSION) -> SmokeResult:
    """真連線 smoke：與 `read_history` 同一條 secrets／讀取路徑，但**繞過快取**。只回 `SmokeResult`（⛔ 不回列內容）。"""
    src = st.secrets if secrets is None else secrets
    factory = L1H.build_reader_client if client_factory is None else client_factory

    target = _load_target(src)
    if isinstance(target, ReadResult):
        return SmokeResult(read_status=target.status,
                           identity_ok=False if target.status == P.READ_STATUS_IDENTITY_MISMATCH else None)
    sheet_id, info, _email = target
    try:
        values = _fetch_values(sheet_id, info, factory)
    except _READ_ERRORS as e:
        failed = _read_failure(e)
        return SmokeResult(read_status=failed.status,
                           identity_ok=False if failed.status == P.READ_STATUS_IDENTITY_MISMATCH else True)
    state = L1H.header_state(values)
    n_data = max(len(values) - 1, 0)
    try:
        records = _records_from_values(values)
    except _READ_ERRORS as e:
        return SmokeResult(read_status=_read_failure(e).status, identity_ok=True, header_state=state, data_rows=n_data)
    latest = records[-1] if records else None
    expected = now.astimezone(P.RECORD_DATE_TZ).date().isoformat()
    cmp = compare_status(records, expected_date=expected, ruleset_version=ruleset_version, now=now)
    return SmokeResult(
        read_status=P.READ_STATUS_OK if records else P.READ_STATUS_EMPTY, identity_ok=True,
        header_state=state, data_rows=n_data,
        latest_record_date=latest[P.COL_RECORD_DATE] if latest else "",
        latest_run_id=latest[P.COL_RUN_ID] if latest else "",
        latest_row_sha256=L1H.record_sha256(latest) if latest else "",
        compare_status=cmp.status)


_SMOKE_LOCK = threading.Lock()
_SMOKE_DONE = False


def _smoke_flag_on(src: Any) -> bool:
    """secrets 頂層 `risk_cap_history_smoke` **恰好**是 `True` 才算開（`"true"` 字串、1… 一律不算）。

    secrets 讀不到（本機沒有 secrets.toml）＝ 旗標沒開 —— 這是「功能沒啟用」，不是被吞掉的錯誤。
    """
    try:
        return _secret_get(src, P.READER_SMOKE_SECRET_KEY) is True
    except Exception:  # noqa: BLE001 —— 沒有 secrets ⇒ 旗標沒開（⛔ 不視為開）
        return False


def run_smoke_if_flagged(*, now: datetime | None = None, secrets: Mapping[str, Any] | None = None,
                         client_factory: ReaderClientFactory | None = None) -> SmokeResult | None:
    """`app.py` 開機時呼叫：旗標恰好為 True 時，**每個行程只跑一次** `smoke_check` 並印一行固定格式 log。

    旗標沒開 ⇒ 回 None、零 Google 呼叫、零輸出。讀取失敗本身是 `SmokeResult` 裡的狀態（照實印出，⛔ 不吞）。
    ⚠️ 本函式是全 repo **唯一**刻意「不讓例外往上拋」的地方：它跑在 app 開機路徑，smoke 只是觀測、
    不得讓網站掛掉。所以 `smoke_check` 本身若有程式 bug（非讀取錯誤），這裡只印例外**類別名**一行並繼續 ——
    ⛔ 不印訊息原文（可能帶 Sheet ID）。範圍只包住 `smoke_check` 一個呼叫，其餘照常。
    """
    global _SMOKE_DONE
    src = st.secrets if secrets is None else secrets
    if not _smoke_flag_on(src):
        return None
    with _SMOKE_LOCK:
        if _SMOKE_DONE:
            return None
        _SMOKE_DONE = True
    try:
        result = smoke_check(now or datetime.now(P.RECORD_DATE_TZ), secrets=src, client_factory=client_factory)
    except Exception as e:  # noqa: BLE001 —— 見 docstring：唯一不讓 app 開機掛掉的地方；只印類別名
        print(f"{P.READER_SMOKE_LOG_PREFIX} read_status={P.READER_SMOKE_STATUS_BUG} error_type={type(e).__name__}",
              flush=True)
        return None
    print(result.log_line(), flush=True)
    return result
