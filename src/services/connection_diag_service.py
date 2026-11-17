"""連線診斷服務（L3）：🗂 資料頁「🔌 連線診斷」的唯一探測入口（GitHub #1110 D-T2）。

安全邊界（測試以 AST／行為鎖住）：
- `run_connection_check()` **無參數**；探測 URL 只用本檔常數（或 `get_nas_relay()` 的 base＋固定路徑），不接受任何外部輸入。
- TLS 一律 `verify=True`、`allow_redirects=False`、timeout＝(connect 3s, read 5s)；單次檢查 ≤ 7 個請求；`stream=True` 且不讀 body。
- 全進程 `threading.Lock` 非阻塞＋模組層 cooldown（跨 session）：忙碌／冷卻中回前次結果並帶 `DiagNotice.WAIT`。
- 輸出只有 `shared.ui2_contract.diag` 的枚舉；例外原文／host／IP／URL／header／body 一律不輸出（分類只看例外型別與整數狀態碼）。
- 不用 fetch_url／nas_relay_fetch／build_unverified_proxy_session；不抓 OHLC／行情；Gemini、FRED 不探測。
- 金鑰只送往 https 的 NAS base（明文 http 一律不送，顯示「認證未驗證」）；FinMind token 只送往本檔常數的 https 端點。
"""
from __future__ import annotations

import threading
import time
from dataclasses import replace

import requests

from shared.ui2_contract.diag import (
    INITIAL_REPORT, DiagNotice, DiagReason, DiagReport, DiagStatus, ProbeResult,
)

#: 固定探測端點（⛔ 變數／外部輸入）。僅 Yahoo 首頁；FinMind／TWSE／NAS 代理沒有 GPT 核准的低副作用健康端點 → 不發請求、固定「尚未檢查」。
YAHOO_PROBE_URL = "https://finance.yahoo.com/"
NAS_ROOT_PATH = "/"
NAS_PROXY_PATH = "/proxy"          # 不帶 url 參數：只用來判斷是否強制認證，不會代抓任何資料

CONNECT_TIMEOUT_S = 3
READ_TIMEOUT_S = 5
COOLDOWN_S = 20.0
MAX_REQUESTS = 5          # NAS 中繼站 3 ＋ Yahoo 1（其餘不發請求）；上限仍 ≤ 7

_NO_PROXY = {"http": None, "https": None}      # 直連：忽略環境 proxy

_LOCK = threading.Lock()
_STATE: dict = {"last_report": None, "last_finished": None}


# ── 分類（複製自 src/ui/pages/api_diagnostic.py 的 _classify_*，parity 測試鎖住；另加 SSLError／407）──
def _classify_status(code: int) -> DiagReason | None:
    if code < 400:
        return None
    if code in (401, 403):
        return DiagReason.AUTH
    if 500 <= code <= 599:
        return DiagReason.SERVER
    return DiagReason.OTHER


def _classify_exception(e: BaseException) -> DiagReason:
    """例外 → 固定類別。只看型別，⛔ 不讀例外訊息。"""
    ex = requests.exceptions
    if isinstance(e, ex.ProxyError):       # ProxyError 是 ConnectionError 子類，要先判
        return DiagReason.PROXY
    if isinstance(e, ex.Timeout):          # ConnectTimeout 同時是 ConnectionError 子類，要先判
        return DiagReason.TIMEOUT
    if isinstance(e, ex.SSLError):         # SSLError 是 ConnectionError 子類，要先判
        return DiagReason.TLS
    if isinstance(e, ex.ConnectionError):
        return DiagReason.CONNECTION
    return DiagReason.OTHER


def _get(url: str, *, headers: dict | None = None, proxies: dict | None = None) -> int:
    """唯一的對外請求點。回整數狀態碼；⛔ 讀 body／回 response；例外由呼叫端依型別分類。"""
    r = requests.get(url, headers=headers, proxies=proxies, timeout=(CONNECT_TIMEOUT_S, READ_TIMEOUT_S),
                     verify=True, allow_redirects=False, stream=True)
    try:
        code = r.status_code
    finally:
        r.close()
    if isinstance(code, bool) or not isinstance(code, int):
        raise ValueError("status")        # 非整數狀態碼 → 呼叫端歸「其他」
    return code


def _http_probe(url: str, *, headers: dict | None = None, proxies: dict | None = None) -> ProbeResult:
    try:
        code = _get(url, headers=headers, proxies=proxies)
    except Exception as e:   # noqa: BLE001 — 只取型別分類；不保留例外原文
        return ProbeResult(DiagStatus.FAILED, _classify_exception(e))
    cat = _classify_status(code)
    return ProbeResult(DiagStatus.SUCCESS) if cat is None else ProbeResult(DiagStatus.FAILED, cat)


def _probe_nas_relay() -> ProbeResult:
    from src.data.proxy.proxy_helper import get_nas_relay
    try:
        cfg = get_nas_relay()
    except Exception:   # noqa: BLE001
        return ProbeResult(DiagStatus.FAILED, DiagReason.OTHER)
    if cfg is None:
        return ProbeResult(DiagStatus.NOT_CONFIGURED)
    base, key = cfg
    if not str(base).lower().startswith("https://"):
        return ProbeResult(DiagStatus.AUTH_UNVERIFIED, DiagReason.PLAIN_HTTP)      # 不送金鑰、不發請求
    try:
        root = _get(f"{base}{NAS_ROOT_PATH}")
    except Exception as e:   # noqa: BLE001
        return ProbeResult(DiagStatus.FAILED, _classify_exception(e))
    if 500 <= root <= 599:
        return ProbeResult(DiagStatus.FAILED, DiagReason.SERVER)
    try:
        nokey = _get(f"{base}{NAS_PROXY_PATH}")
    except Exception as e:   # noqa: BLE001
        return ProbeResult(DiagStatus.FAILED, _classify_exception(e))
    if nokey not in (401, 403):
        return ProbeResult(DiagStatus.AUTH_UNVERIFIED, DiagReason.AUTH_NOT_ENFORCED)   # 未證明伺服器強制認證
    if not key:
        return ProbeResult(DiagStatus.AUTH_UNVERIFIED, DiagReason.KEY_MISSING)
    try:
        withkey = _get(f"{base}{NAS_PROXY_PATH}", headers={"X-API-Key": key})
    except Exception as e:   # noqa: BLE001
        return ProbeResult(DiagStatus.FAILED, _classify_exception(e))
    if withkey in (401, 403):
        return ProbeResult(DiagStatus.FAILED, DiagReason.AUTH)
    if 500 <= withkey <= 599:
        return ProbeResult(DiagStatus.FAILED, DiagReason.SERVER)
    return ProbeResult(DiagStatus.SUCCESS)


def _probe_nas_proxy() -> ProbeResult:
    from src.data.proxy.proxy_helper import get_proxy_config
    try:
        cfg = get_proxy_config()
    except Exception:   # noqa: BLE001
        return ProbeResult(DiagStatus.FAILED, DiagReason.OTHER)
    if not cfg:
        return ProbeResult(DiagStatus.NOT_CONFIGURED)
    return ProbeResult(DiagStatus.NOT_CHECKED)      # 無核准的健康端點 → 不發請求


def _probe_finmind() -> ProbeResult:
    """FinMind 只有資料類端點、未被核准為健康端點 → 不發請求；無 token＝未設定，有 token 也維持尚未檢查。"""
    from src.config import get_finmind_token
    try:
        token = get_finmind_token()
    except Exception:   # noqa: BLE001
        token = ""
    return ProbeResult(DiagStatus.NOT_CONFIGURED if not token else DiagStatus.NOT_CHECKED)


def _safe(fn) -> ProbeResult:
    try:
        return fn()
    except Exception:   # noqa: BLE001 — 任何未預期錯誤 → 固定「其他」，不外洩內容
        return ProbeResult(DiagStatus.FAILED, DiagReason.OTHER)


def _probe_all() -> DiagReport:
    return DiagReport(
        nas_relay=_safe(_probe_nas_relay),
        nas_proxy=_safe(_probe_nas_proxy),
        finmind=_safe(_probe_finmind),
        yahoo=_safe(lambda: _http_probe(YAHOO_PROBE_URL, proxies=_NO_PROXY)),
        twse=ProbeResult(DiagStatus.NOT_CHECKED),      # 無核准的健康端點 → 不發請求
    )


def run_connection_check() -> DiagReport:
    """使用者點擊後呼叫一次。忙碌／冷卻中不重複探測：回前次結果（無則初始態）並帶 `DiagNotice.WAIT`。"""
    if not _LOCK.acquire(blocking=False):
        return replace(_STATE["last_report"] or INITIAL_REPORT, notice=DiagNotice.WAIT)
    try:
        last = _STATE["last_finished"]
        if last is not None and (time.monotonic() - last) < COOLDOWN_S:
            return replace(_STATE["last_report"] or INITIAL_REPORT, notice=DiagNotice.WAIT)
        report = _probe_all()
        _STATE["last_report"] = report
        _STATE["last_finished"] = time.monotonic()
        return report
    finally:
        _LOCK.release()
