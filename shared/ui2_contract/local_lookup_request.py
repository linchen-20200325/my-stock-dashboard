"""「本機日K檔查一檔」的請求／回應純契約（L0；P-M2g §三；GitHub #1199 R23.54）。

⛔ 只定義資料形狀與不變量：無 production caller、不做任何 I/O、不讀 streamlit／session／時鐘／檔案、不 import `src.*`。
   「這個請求是不是本機」的**判斷**屬 L3；本檔只**正規化**證據（`build_local_proof`）並驗形狀，
   **不寫任何「是否本機／是否 loopback」結論**（避免第二個權威）。

═══ 三個 frozen dataclass ═══
- `LocalProof`：L3 判斷用的**證據**（bind_address 原值、是否有 headers、Host 去 port 小寫、proxy 類標頭名稱）。
- `LocalLookupRequest`：`op` ∈ {list, query}；query 須帶 symbol／filename，**list 時兩者必須為 None**
  （依 P 表「query 必填」推得的收緊，待 P 確認）。`filename`／`symbol` 以 `repr=False` 隱藏；`LocalProof.bind_address`／`request_host` 亦同。
- `LocalLookupResponse`：`ok=True ⇒ reason_code=None`；`ok=False ⇒ reason_code ∈ REASON_CODE_SET`；
  `filenames` 僅 list 成功可非空；`vm` 僅 query 成功、或 query 且 `parse_failed` 可非 None。

═══ 接線批須知（L3／L5；本檔不能代勞）═══
1. **L3 列目錄時必須先過濾不合規檔名**（含空字串、`.`／`..`、含 `/`、**含反斜線 `\\`**、含 NUL 者），再組
   `LocalLookupResponse.filenames`，**不可讓單一怪檔名使整個清單失敗**。已知取捨：POSIX 合法檔名 `a\\b.csv`
   會使 `LocalLookupResponse` 建構時 ValueError，故過濾是 L3 的責任（本檔刻意不放寬 `\\` 的拒絕）。
2. **`st.context.headers` 是 `StreamlitHeaders`：同名多值只回第一個值**（`headers["host"]` 看不到第二個 Host）。
   本檔 `build_local_proof` 的「衝突多 Host 偵測」**只對 dict 型、大小寫變體並存**的輸入有效，**不能**防多個同名 Host。
   L3／L5 接線時須**先**以 `headers.get_all("host")` 檢查筆數與值（多於 1 筆即視為異常），**再**呼叫本函式。
   **L0 沒有防多 Host，不得宣稱它有。**
3. 未加括號的 `::1:8501` 會被當成 IPv6 位址原樣保留為 `request_host="::1:8501"`（保守方向：不去 port）；
   L3 **不得**把它視為本機。

═══ Fail Loud ═══
`__post_init__` 一律以固定訊息 raise（TypeError／ValueError），**不回顯任何輸入內容**。型別嚴格：bool 不可冒充 str；
tuple 元素須為 str。

═══ build_local_proof（建議、可刪）═══
`build_local_proof(bind_address, headers)`：只正規化——標頭名稱小寫、Host 去 port 並小寫（`[::1]:8501`→`::1`）、
無 Host→None、proxy 類標頭名稱（`x-forwarded-*`／`forwarded`／`x-real-ip`／`via`／`cf-connecting-ip`／`cf-ray`／
`cdn-loop`／`true-client-ip`／`x-client-ip`／`x-original-forwarded-for`）小寫排序去重；
`None`／空 mapping ⇒ `headers_present=False`。Host 格式不合法（如 `:8501`、`a:b`、`[::1`）或同一請求出現互相衝突的多個
Host 標頭 ⇒ `ValueError`（固定訊息；由 L3 對映為 `bad_request`）。

⚠️ 同名多值：`headers` 若為 `StreamlitHeaders`，本函式只看得到每個名稱的第一個值；多 Host 須由呼叫端先以
`headers.get_all("host")` 檢查（見「接線批須知」2）。本函式**不能**防多 Host。

⚠️ **proxy 標頭名稱清單不完備，不得單獨證明隔離**（黑名單不是正向證明）；isolation 由 L3 精確 loopback 驗證。

⛔ 接線批待辦：L3 才可決定 loopback／proxy／hosted 的放行與否；本檔的 `reason_code` 只是固定詞彙。
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal

from shared.ui2_contract.local_lookup_result import LocalLookupResultVM

# ── 固定詞彙 ─────────────────────────────────────────────────────────
OP_LIST = "list"
OP_QUERY = "query"
OPS = (OP_LIST, OP_QUERY)

REASON_NOT_ENABLED = "not_enabled"
REASON_BIND_NOT_LOOPBACK = "bind_not_loopback"
REASON_NO_REQUEST_CONTEXT = "no_request_context"
REASON_HOST_NOT_LOOPBACK = "host_not_loopback"
REASON_PROXY_HEADERS_PRESENT = "proxy_headers_present"
REASON_HOSTED_RUNTIME = "hosted_runtime"
REASON_DIR_INVALID = "dir_invalid"
REASON_DIR_INSIDE_REPO = "dir_inside_repo"
REASON_FILE_INVALID = "file_invalid"
REASON_FILE_NOT_REGULAR = "file_not_regular"
REASON_FILE_TOO_LARGE = "file_too_large"
REASON_FILE_UNREADABLE = "file_unreadable"
REASON_PARSE_FAILED = "parse_failed"
REASON_BAD_REQUEST = "bad_request"

#: 固定順序版（逐字、不可增減；測試鎖定）。
REASON_CODES: tuple[str, ...] = (
    REASON_NOT_ENABLED, REASON_BIND_NOT_LOOPBACK, REASON_NO_REQUEST_CONTEXT, REASON_HOST_NOT_LOOPBACK,
    REASON_PROXY_HEADERS_PRESENT, REASON_HOSTED_RUNTIME, REASON_DIR_INVALID, REASON_DIR_INSIDE_REPO,
    REASON_FILE_INVALID, REASON_FILE_NOT_REGULAR, REASON_FILE_TOO_LARGE, REASON_FILE_UNREADABLE,
    REASON_PARSE_FAILED, REASON_BAD_REQUEST,
)
REASON_CODE_SET: frozenset[str] = frozenset(REASON_CODES)

#: proxy 類標頭（名稱，小寫）：精確名稱集合（逐字相等比對，不代表清單完備）＋前綴。
#: ⚠️ **此清單不完備，不得單獨證明隔離**（黑名單不是正向證明）；isolation 由 L3 精確 loopback 驗證。
#: 多列一個名稱＝多偵測＝多拒絕（純收緊）。`x-original-forwarded-for` 不以 `x-forwarded-` 開頭，故須列為精確名稱。
PROXY_HEADER_EXACT = frozenset({
    "forwarded", "x-real-ip", "via",
    "cf-connecting-ip", "cf-ray", "cdn-loop", "true-client-ip", "x-client-ip", "x-original-forwarded-for",
})
PROXY_HEADER_PREFIX = "x-forwarded-"

_HOST_HEADER = "host"
_IPV6_CHARS = frozenset("0123456789abcdef:.")


# ── 驗證小工具（固定訊息，不回顯輸入）──────────────────────────────────
def _is_str(x: object) -> bool:
    return isinstance(x, str)


def _is_proxy_name(name: str) -> bool:
    return name in PROXY_HEADER_EXACT or name.startswith(PROXY_HEADER_PREFIX)


def _host_ok(host: str) -> bool:
    """已正規化 Host 的形狀：非空、小寫、無 port、無括號、無空白／控制字元。IPv6 為裸位址（≥2 個冒號）。"""
    if host == "" or host != host.lower() or "[" in host or "]" in host:
        return False
    if any(c.isspace() or not c.isprintable() for c in host):
        return False
    n = host.count(":")
    if n == 1:
        return False                                   # host:port
    if n >= 2:
        return all(c in _IPV6_CHARS for c in host)
    return True


@dataclass(frozen=True)
class LocalProof:
    """L3 判斷用證據（只正規化、不下結論）。欄位見模組 docstring。"""
    bind_address: str | None = field(repr=False)       # repr=False：不讓位址／Host 進 log 或錯誤畫面
    headers_present: bool
    request_host: str | None = field(repr=False)
    proxy_header_names: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.bind_address is not None and not _is_str(self.bind_address):
            raise TypeError("LocalProof.bind_address 必須是 str 或 None")
        if type(self.headers_present) is not bool:
            raise TypeError("LocalProof.headers_present 必須是 bool")
        if self.request_host is not None:
            if not _is_str(self.request_host):
                raise TypeError("LocalProof.request_host 必須是 str 或 None")
            if not _host_ok(self.request_host):
                raise ValueError("LocalProof.request_host 必須是已去 port 的非空小寫主機名稱")
        names = self.proxy_header_names
        if not isinstance(names, tuple) or not all(_is_str(n) for n in names):
            raise TypeError("LocalProof.proxy_header_names 必須是 str 的 tuple")
        if any(n != n.lower() or not _is_proxy_name(n) for n in names):
            raise ValueError("LocalProof.proxy_header_names 只可含小寫的 proxy 類標頭名稱")
        if list(names) != sorted(set(names)):
            raise ValueError("LocalProof.proxy_header_names 必須排序且不重複")
        if not self.headers_present and (self.request_host is not None or names):
            raise ValueError("LocalProof 無 headers 時不得有 request_host／proxy_header_names")


@dataclass(frozen=True)
class LocalLookupRequest:
    op: Literal["list", "query"]
    proof: LocalProof
    symbol: str | None = field(default=None, repr=False)
    filename: str | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if not _is_str(self.op) or self.op not in OPS:
            raise ValueError("LocalLookupRequest.op 必須是 list 或 query")
        if not isinstance(self.proof, LocalProof):
            raise TypeError("LocalLookupRequest.proof 必須是 LocalProof")
        for v in (self.symbol, self.filename):
            if v is not None and not _is_str(v):
                raise TypeError("LocalLookupRequest.symbol／filename 必須是 str 或 None")
        if self.op == OP_LIST:
            if self.symbol is not None or self.filename is not None:
                raise ValueError("LocalLookupRequest list 時 symbol／filename 必須為 None")
        elif not self.symbol or not self.filename:
            raise ValueError("LocalLookupRequest query 必須有非空 symbol 與 filename")


@dataclass(frozen=True)
class LocalLookupResponse:
    op: Literal["list", "query"]
    ok: bool
    reason_code: str | None = None
    filenames: tuple[str, ...] = ()
    vm: LocalLookupResultVM | None = None

    def __post_init__(self) -> None:
        if not _is_str(self.op) or self.op not in OPS:
            raise ValueError("LocalLookupResponse.op 必須是 list 或 query")
        if type(self.ok) is not bool:
            raise TypeError("LocalLookupResponse.ok 必須是 bool")
        if self.reason_code is not None and not _is_str(self.reason_code):
            raise TypeError("LocalLookupResponse.reason_code 必須是 str 或 None")
        if not isinstance(self.filenames, tuple) or not all(_is_str(n) for n in self.filenames):
            raise TypeError("LocalLookupResponse.filenames 必須是 str 的 tuple")
        if self.vm is not None and not isinstance(self.vm, LocalLookupResultVM):
            raise TypeError("LocalLookupResponse.vm 必須是 LocalLookupResultVM 或 None")
        if any(n in ("", ".", "..") or "/" in n or "\\" in n or "\x00" in n for n in self.filenames):
            raise ValueError("LocalLookupResponse.filenames 只可含非空的檔名（basename；不得為 . 或 ..）")
        if self.ok:
            if self.reason_code is not None:
                raise ValueError("LocalLookupResponse ok=True 時 reason_code 必須為 None")
        elif self.reason_code not in REASON_CODE_SET:
            raise ValueError("LocalLookupResponse ok=False 時 reason_code 必須屬固定集合")
        if self.filenames and not (self.op == OP_LIST and self.ok):
            raise ValueError("LocalLookupResponse filenames 僅限 list 成功")
        if self.vm is not None and not (
                self.op == OP_QUERY and (self.ok or self.reason_code == REASON_PARSE_FAILED)):
            raise ValueError("LocalLookupResponse vm 僅限 query 成功或 query 的 parse_failed")
        if self.op == OP_QUERY and self.ok and self.vm is None:
            raise ValueError("LocalLookupResponse query 成功必須有 vm")


# ── build_local_proof（建議、可刪）─────────────────────────────────────
def _normalize_host(value: object) -> str | None:
    """Host 標頭值 → 去 port、小寫、去 IPv6 括號。空值→None；格式不合法→ValueError（固定訊息）。"""
    if not _is_str(value):
        raise TypeError("Host 標頭值必須是 str")
    s = value.strip().lower()
    if s == "":
        return None
    if s.startswith("["):
        end = s.find("]")
        rest = s[end + 1:] if end != -1 else None
        if end == -1 or rest is None or not (rest == "" or (rest.startswith(":") and rest[1:].isdigit()
                                                           and rest[1:].isascii() and len(rest) <= 6)):
            raise ValueError("Host 標頭格式不合法")
        host = s[1:end]
    else:
        n = s.count(":")
        if n == 1:
            host, port = s.split(":")
            if not (port.isdigit() and port.isascii() and len(port) <= 5):
                raise ValueError("Host 標頭格式不合法")
        else:
            host = s
    if not _host_ok(host) or host.count(":") == 1:
        raise ValueError("Host 標頭格式不合法")
    return host


def build_local_proof(bind_address: str | None, headers: Mapping[str, str] | None) -> LocalProof:
    """只正規化證據，**不做**任何本機／loopback／安全判斷（見模組 docstring）。

    ⚠️ `headers` 為 `StreamlitHeaders`（`st.context.headers`）時，同名多值只會取到第一個值；「衝突多 Host 偵測」只對
    dict 型的**大小寫變體並存**（如 `{"Host": a, "host": b}`）有效。呼叫端須先以 `headers.get_all("host")` 檢查筆數與值，
    本函式不保證能防多 Host。
    """
    if bind_address is not None and not _is_str(bind_address):
        raise TypeError("bind_address 必須是 str 或 None")
    if headers is None or (isinstance(headers, Mapping) and len(headers) == 0):
        return LocalProof(bind_address=bind_address, headers_present=False, request_host=None,
                          proxy_header_names=())
    if not isinstance(headers, Mapping):
        raise TypeError("headers 必須是 Mapping 或 None")
    hosts: set[str | None] = set()
    proxies: set[str] = set()
    for k, v in headers.items():
        if not _is_str(k):
            raise TypeError("headers 的鍵必須是 str")
        name = k.strip().lower()
        if name == _HOST_HEADER:
            hosts.add(_normalize_host(v))
        elif _is_proxy_name(name):
            proxies.add(name)
    present_hosts = {h for h in hosts if h is not None}
    if len(present_hosts) > 1:
        raise ValueError("headers 含互相衝突的多個 Host")
    return LocalProof(bind_address=bind_address, headers_present=True,
                      request_host=next(iter(present_hosts), None), proxy_header_names=tuple(sorted(proxies)))
