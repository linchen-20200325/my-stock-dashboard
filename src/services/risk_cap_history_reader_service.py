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
  6. `detail` 只含固定文字＋例外類別名：⛔ 不含 Sheet ID、key 內容、例外訊息原文。

⛔ 本批**沒有**任何畫面呼叫本檔（UI 接線屬另案、須先出線框，CLAUDE.md §-1.5.A-8）。

分層（CLAUDE.md §8.2）：L3 —— import L0（`shared.*`）、L1（`src.data.macro.risk_cap_history`）、
L3（`risk_cap_history_service.compare_status`）；streamlit 依 EX-CACHE-1 慣例條件 import，
只用 `st.secrets` 與 `st.cache_data`；零 L4/L5。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Mapping

from shared import risk_cap_history_policy as P
from shared.risk_cap_policy import RISK_CAP_RULESET_VERSION
from shared.ttls import TTL_30MIN
from src.data.macro import risk_cap_history as L1H
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


def _log(status: str, detail: str) -> None:
    print(f"[risk_cap_history_reader] {status}：{detail}")


def _fail(status: str, detail: str) -> ReadResult:
    _log(status, detail)
    return ReadResult(status=status, detail=detail)


@st.cache_data(ttl=HISTORY_READ_TTL_S, show_spinner=False)
def _fetch_records_cached(sheet_id: str, reader_email: str, _info: Mapping[str, Any],
                          _client_factory: ReaderClientFactory) -> list[dict[str, str]]:
    """讀全表（只有成功才回傳 ⇒ 只有成功會被快取）。任何失敗一律**拋**（`st.cache_data` 不快取例外）。

    快取鍵只有 `sheet_id` 與 `reader_email`（底線開頭參數不進雜湊 —— key 內容 ⛔ 不參與快取鍵計算）。
    """
    client = _client_factory(_info)
    ws = L1H.open_history_worksheet(client, sheet_id)
    return L1H.read_history_records(ws)


def clear_read_cache() -> None:
    """清掉讀取快取（測試與日後「重新讀取」按鈕用）。無 streamlit 時為 no-op。"""
    clear = getattr(_fetch_records_cached, "clear", None)
    if callable(clear):
        clear()


def _secret_get(secrets: Any, key: str) -> Any:
    """`st.secrets.get(key)`；沒有 secrets.toml 時 streamlit 會拋 —— 由呼叫端分類（⛔ 不吞成「有值」）。"""
    return secrets.get(key)


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

    try:
        records = _fetch_records_cached(sheet_id, email, info, factory)
    except L1H.ReaderIdentityMismatch as e:
        return _fail(P.READ_STATUS_IDENTITY_MISMATCH, str(e))
    except L1H.ReaderCredentialInvalid as e:
        return _fail(P.READ_STATUS_NO_CREDENTIAL, str(e))
    except L1H.HistoryTabMissing:
        return _fail(P.READ_STATUS_TAB_MISSING, f"試算表內沒有 {P.HISTORY_WORKSHEET_NAME!r} 分頁")
    except L1H.HistorySchemaMismatch:
        return _fail(P.READ_STATUS_SCHEMA_MISMATCH, "表頭與歷史紀錄 schema 不一致（⛔ 不猜欄位對應）")
    except L1H.HistoryApiError as e:
        return _fail(P.READ_STATUS_API_ERROR, f"Google API／傳輸錯誤（{e.error_type}）")
    except L1H.HistoryTargetMismatch:
        return _fail(P.READ_STATUS_IDENTITY_MISMATCH, "開到的試算表／分頁與系統歷史 Sheet 核對不符")

    rows = tuple(dict(r) for r in records)
    cmp = compare_status(list(rows), expected_date=expected_date, ruleset_version=ruleset_version, now=now)
    if not rows:
        return ReadResult(status=P.READ_STATUS_EMPTY, rows=(), compare=cmp,
                          detail="系統歷史 Sheet 尚無任何紀錄（從今天開始記錄）")
    return ReadResult(status=P.READ_STATUS_OK, rows=rows, compare=cmp, detail="")
