"""src/data/portfolio/oauth_nonce_store.py — OAuth `state` 一次性 nonce 表（L1，SEC-2）。

§8.2 layer:L1 Data（純 Python，**不 import streamlit**）。只依賴 L0 `shared.oauth_csrf_policy`。

存什麼
======
process 級 dict：`{nonce: (到期的 monotonic 秒, sha256(瀏覽器綁定 bytes) 的 hex)}`。
⛔ 不存 token、不存 cookie 原文、不存帳號 —— 只有 nonce（本來就會出現在 authorize URL）
與綁定值的單向雜湊。

為什麼要綁瀏覽器（不能只存 nonce）
==================================
攻擊者在**他自己的瀏覽器**開本站就能領到一個登記過的 nonce，再把
`?code=<他的授權碼>&state=<那個 nonce>` 丟給受害者 —— 只看「nonce 有沒有登記過」會放行，
受害者就被登入成攻擊者的帳號（login CSRF）。綁定 = 發 nonce 時記下**發起者瀏覽器**的
XSRF token 雜湊，消耗時比對**回呼者瀏覽器**的雜湊，不同就拒絕。理由詳見
`shared/oauth_csrf_policy.py`。

規則
====
- `issue()`：先清掉過期項、滿了丟最久沒被延長的，再登記 / 延長（每次 rerun 都會呼叫）。
- `consume()`：**先 pop**（一次性：不論結果如何都燒掉）→ 檢查到期 → `hmac.compare_digest`。
- 多執行緒：Streamlit 每個 session 一條執行緒，全部操作在同一把 `threading.Lock` 內。
⚠️ 已知限制（據實標明）：表在**單一 process** 記憶體內。多副本部署或 process 重啟 ⇒ 回呼落到
另一個 process 時查無此 nonce（reason=`unknown`）→ 嚴格模式下登入被拒。量測與應變見
docs/OAUTH_SETUP.md「SEC-2 量測」（secrets `oauth_csrf_enforce=false` 可暫時放行）。
"""
from __future__ import annotations

import hmac
import threading
import time

from shared.oauth_csrf_policy import OAUTH_STATE_MAX_ENTRIES, OAUTH_STATE_TTL_SEC

# ── reason codes(§3.3 具名常數;只記這些代碼,⛔ 不記 nonce / cookie / token 值)──────
REASON_OK = "ok"
REASON_UNKNOWN = "unknown"        # 沒登記過 / 已用過 / 被擠掉 / 另一個 process 發的
REASON_EXPIRED = "expired"        # 登記過但超過 OAUTH_STATE_TTL_SEC 沒延長
REASON_MISMATCH = "mismatch"      # 不是發起登入的那個瀏覽器(login CSRF 的樣子)
REASON_NO_COOKIE = "no_cookie"    # 回呼者沒有可解析的 XSRF cookie → 無從比對

_STORE: "dict[str, tuple[float, str]]" = {}
_LOCK = threading.Lock()


def _now() -> float:
    """單調時鐘(測試以 monkeypatch 換掉;不受系統時間調整影響)。"""
    return time.monotonic()


def _purge_expired(now: float) -> None:
    """清掉過期項。持鎖呼叫。

    dict 依「最後一次 issue」排序且 TTL 固定 ⇒ 到期時間由前往後遞增,
    從頭 pop 到第一個未過期即可(O(過期筆數),不必每次掃全表)。
    """
    while _STORE:
        _first = next(iter(_STORE))
        if _STORE[_first][0] > now:
            break
        del _STORE[_first]


def issue(nonce: str, binding_hash: "str | None", *,
          ttl: float = OAUTH_STATE_TTL_SEC,
          max_entries: int = OAUTH_STATE_MAX_ENTRIES) -> bool:
    """登記(或延長)`nonce`,綁定到 `binding_hash`。回是否有登記。

    `binding_hash` 為 None(讀不到瀏覽器 XSRF cookie)或 nonce 為空 → 不登記、回 False
    (無從綁定就不發「可用的」nonce;callback 會以 `no_cookie` / `unknown` 拒絕)。
    已存在 → 移到最後並重設到期時間(＝延長;綁定以本次為準,呼叫端只會用本 session 的 nonce)。
    """
    if not nonce or not binding_hash:
        return False
    with _LOCK:
        _now_ts = _now()
        _purge_expired(_now_ts)
        _STORE.pop(nonce, None)
        while len(_STORE) >= max_entries:
            del _STORE[next(iter(_STORE))]   # 擠掉最久沒被延長的那筆(fail closed)
        _STORE[nonce] = (_now_ts + ttl, binding_hash)
    return True


def consume(nonce: str, binding_hash: "str | None") -> "tuple[bool, str]":
    """驗證並**燒掉** `nonce`。回 `(ok, reason)`;`reason` ∈ REASON_*。

    順序固定:先 pop(一次性 —— 比對失敗也燒掉,攻擊者不能拿同一個 nonce 重試)
    → 沒 cookie → 查無 → 過期 → 綁定比對(`hmac.compare_digest`,定時比較)。
    """
    with _LOCK:
        _entry = _STORE.pop(nonce, None) if nonce else None
        _now_ts = _now()
    if not binding_hash:
        return False, REASON_NO_COOKIE
    if _entry is None:
        return False, REASON_UNKNOWN
    _expires, _bound_hash = _entry
    if _now_ts >= _expires:
        return False, REASON_EXPIRED
    if not hmac.compare_digest(_bound_hash.encode("ascii"),
                               str(binding_hash).encode("ascii", "replace")):
        return False, REASON_MISMATCH
    return True, REASON_OK
