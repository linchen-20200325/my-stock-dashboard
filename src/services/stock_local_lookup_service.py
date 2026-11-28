"""src/services/stock_local_lookup_service.py — 「本機日K檔查一檔」編排（L3；P-M2g／GitHub #1199 R23.52～R23.58）。

⛔ 本批**無 production caller**（不接線）：L5 之後才會取 `st.get_option`／`st.context.headers`、建 `LocalProof`、呼叫本檔。

═══ 職責 ═══
收一份 L0 `LocalLookupRequest`（內含 L5 取得的**原始證據** `LocalProof`），在 L3 內**自行重驗全部條件**
（不信任呼叫端布林），通過後才讀「使用者指定的本機資料夾」內的 CSV，經 L1 `parse_local_ohlcv_csv`、L2
`build_stock_research_facts`、L0 `build_quote_view`／`build_local_lookup_result` 組成 `LocalLookupResponse`。
任何失敗只回固定 `reason_code`（L0 `REASON_CODE_SET`），**不 raise、不洩漏路徑／檔名／內容／例外原文**。
**唯一會 raise 的情形**：`request` 本身不是 `LocalLookupRequest`（程式錯誤，固定訊息 TypeError）。
其餘一切（`request.proof` 不是 `LocalProof`、`environ`／`cwd`／`repo_root`／`now` 注入型別不符）**一律回固定碼
`bad_request`，不 raise**（list 與 query 一致；皆在任何檔案系統存取之前判定）。

═══ 層級（CLAUDE.md §8.2）═══
L3。可 import L0（`shared.*`）、L1（`src.data.stock.*`）、L2（`src.compute.strategy.*`）。
⛔ 不 import streamlit／requests／src.ui*／src.ui2／logging；不 print；不落盤、不連網、不快取、無全域可變狀態。
模組層無 I/O 副作用（只有常數）。

═══ 判定順序（固定；先失敗者勝；每次呼叫都重驗，無快取）═══
 0. 型別：`request` 非 `LocalLookupRequest` → TypeError；op 不認得、`request.proof` 非 `LocalProof`
    （含 duck-type／`object.__new__` 缺欄位）、`environ` 非 Mapping、`cwd`／`repo_root` 非 str／PathLike、
    `now` 非 aware datetime → `bad_request`（無檔案系統存取）
 1a. 平台：`os.name`（可注入 `os_name`）不是 `"posix"` → `not_enabled`。理由：非 POSIX 平台（Windows／java…）尚無路徑安全
    測試（無 O_NOFOLLOW／O_DIRECTORY／dir_fd），unknown≠safe，故視為未啟用。**先判平台、再判 env**。
 1b. `UI2_LOCAL_OHLCV_DIR` 缺或空字串 → `not_enabled`（**此前此後皆未碰檔案系統**：連 cwd 都不取）
 2. `proof.bind_address` ∉ {127.0.0.1, localhost, ::1}（None／空／0.0.0.0／其他）→ `bind_not_loopback`
 3. `proof.headers_present` 非 True → `no_request_context`
 4. `proof.request_host` ∉ {127.0.0.1, localhost, ::1}（None 或 `::1:8501` 這類未括號 IPv6 原樣）→ `host_not_loopback`
 5. `proof.proxy_header_names` 非空 → `proxy_headers_present`
 6. 託管負向證據（cwd、cwd resolve 後、repo_root resolve 後任一以 `/mount/src` 開頭，或 `STREAMLIT_SHARING_MODE`／
    `STREAMLIT_RUNTIME_ENV` 任一非空）→ `hosted_runtime`
    （負向證據**只能多拒、不能單獨當隔離**；清單是 NV，見 `HOSTED_*` 常數）
 7. query：`now` 驗證；用 L1 `parse_local_ohlcv_csv(b"", symbol)` 探代號（INVALID_SYMBOL → `bad_request`；
    **不另寫第二套代號規則、不 import 私有符號**；探測不觸及檔案系統）
 8. 目錄：非 str／含 NUL／非絕對／`resolve(strict=True)` 失敗／非目錄 → `dir_invalid`；
    與 repo_root 或 cwd（皆 resolve 後）有祖孫關係（相等／祖先／子孫）→ `dir_inside_repo`。
    **以目錄 fd 為基礎**：resolve 後先 `stat(ctrl)`，再 `os.open(ctrl, O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC)`，
    `fstat(fd)` 的 (st_dev, st_ino) 必須等於先前的 stat（否則 `dir_invalid`＝resolve 與 open 之間目錄被替換）；
    Linux 另以 `readlink(/proc/self/fd/<fd>)` 取 fd 的真實路徑，與 repo／cwd 做祖孫檢查（→ `dir_inside_repo`）
    並要求等於 resolve 結果（否則 `dir_invalid`）。**取不到 fd 的真實路徑（無 /proc／非 Linux）→ fail closed `dir_invalid`**
    （unknown≠safe；不退回「只靠 inode 比對」，因為 resolve→stat 之間的替換會讓 stat 與 open 一起看到被換掉的目錄）。
    之後 list 用 `os.scandir(fd)`、query 用 `os.open(name, flags, dir_fd=fd)`（平台支援時；否則退回路徑版）。fd 一律 try/finally 關閉。
 9a. list：非遞迴 scandir；只收「非符號連結的一般檔、小寫 `.csv`、非隱藏、可印字元、合 L0 檔名規則」；
    怪檔名**被過濾**而非使整體失敗（含 `st_nlink > 1` 的硬連結檔：`entry.stat(follow_symlinks=False)` 失敗亦跳過，
    使「被列出的一定能被查」）；排序；合格檔 > `MAX_LIST_FILENAMES` 或掃描項 > `MAX_SCAN_ENTRIES` → `dir_invalid`
    （**不截斷**：截斷會讓使用者以為清單完整，違反 §1；L0 回應無「已截斷」旗標，故 fail loud）
 9b. query：檔名不合規（同 list 規則）→ `file_invalid`；`resolve()` 後在 repo／cwd 內 → `dir_inside_repo`；
    不在受控目錄下、或與 `受控目錄/檔名` 不同（含任何符號連結）→ `file_invalid`；
    `os.open(O_RDONLY|O_NOFOLLOW|O_CLOEXEC|O_NONBLOCK|O_BINARY，若平台有)` → `fstat` 非一般檔 → `file_not_regular`；
    `st_nlink > 1`（硬連結：可能是 repo 內檔案的另一個名字）→ `file_invalid`；
    `st_size`／實讀 > `MAX_FILE_BYTES` → `file_too_large`；其餘 OSError（含開檔時才發現的符號連結 ELOOP、檔不存在）→ `file_unreadable`
 10. 解析：`parse_local_ohlcv_csv` 非 OK（含 NO_DATA）→ `parse_failed` ＋ MISSING 態 vm（`close=None`；不稱「查無此股」；不補 0）
 11. 組裝：`rows_to_bars_frame` → `build_stock_research_facts(..., basis_verified=False)`（**關鍵字、明傳 False**；本機匯入口徑
     只是使用者聲明）→ `staleness_days(as_of, today=台北日) > STALE_DAYS_DAILY` → `build_quote_view(fetched_at=None)` →
     `build_local_lookup_result(as_of=ISO 字串, source_user_declared=True)`。組裝中的 ValueError／ArithmeticError → `parse_failed`
     ＋ MISSING 態 vm（不以 ok 呈現）；quote 非 OK／STALE（例如收盤超出顯示範圍）亦同。

═══ 取得日 ═══
`fetched_at` 一律 None → 畫面「抓取時間未知」。**不讀 mtime、不用匯入時間、不接受 acquired_on。**

═══ 據實限制（NV）═══
- **中間目錄元件競態**：檔名以 dir_fd＋O_NOFOLLOW 開啟，fd 取得之後的目錄替換無效。「`Path.resolve()` → `stat(ctrl)`」之間
  的替換會讓 stat 與 open 一起看到被換掉的目錄，inode 比對抓不到，所以**唯一的防線是 Linux `/proc/self/fd` 真實路徑二次檢查**；
  **其餘平台（含 macOS）一律拒絕（`dir_invalid`）**，暫不支援，待實機驗證後再擴（不加入未實測的 F_GETPATH）。
- **Linux 上仍存在的更窄競態**：(a) readlink 比對通過之後，fd 所指的目錄若被 rename 到別處，fd 仍指向同一個 inode，讀到的仍是該目錄原本的內容
  （內容不變，但路徑已不是 ctrl）；(b) 能在受控目錄的上層搬動目錄的惡意者，可在 resolve 之後把**別處（含 repo 外）**的目錄 rename 到 ctrl 路徑，
  此時 readlink 回報的正是 ctrl，本檔看不出來——這種攻擊者本來就擁有受控目錄的寫入權，不在威脅模型內，但**未防**；
  (c) `/proc` 在 chroot／unshare mount namespace 下的路徑可能與 resolve 結果不同 → 只會多拒，不會多放。
- 目錄 fd 比對與 /proc 二次檢查**只在 POSIX**（`os_name == "posix"`）；非 POSIX 一律 `not_enabled`，本檔未於 Windows／macOS 實測。
- 硬連結：`st_nlink > 1` 一律拒（含使用者自己合法的硬連結檔）；`st_nlink == 1` 但內容是 repo 檔的**複製**無從得知。
- 託管標記清單（`HOSTED_*`）是推測的最小集，未對真實託管環境驗證。
- 本機性的**正向**證明只有 L5 提供的 proof 欄位；L3 只重驗欄位值，無法確認 L5 取值本身可信。
"""
from __future__ import annotations

import os
import stat
from collections.abc import Mapping
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from shared.staleness import STALE_DAYS_DAILY, staleness_days
from shared.ui2_contract.local_lookup_request import (
    OP_LIST,
    OP_QUERY,
    REASON_BAD_REQUEST,
    REASON_BIND_NOT_LOOPBACK,
    REASON_DIR_INSIDE_REPO,
    REASON_DIR_INVALID,
    REASON_FILE_INVALID,
    REASON_FILE_NOT_REGULAR,
    REASON_FILE_TOO_LARGE,
    REASON_FILE_UNREADABLE,
    REASON_HOSTED_RUNTIME,
    REASON_HOST_NOT_LOOPBACK,
    REASON_NOT_ENABLED,
    REASON_NO_REQUEST_CONTEXT,
    REASON_PARSE_FAILED,
    REASON_PROXY_HEADERS_PRESENT,
    LocalLookupRequest,
    LocalLookupResponse,
    LocalProof,
)
from shared.ui2_contract.local_lookup_result import build_local_lookup_result
from shared.ui2_contract.quote_view import VALUE_BEARING, build_quote_view
from shared.ui2_contract.target_selection import parse_ticker_input
from src.compute.strategy.stock_research_facts import build_stock_research_facts
from src.data.stock.stock_latest_ohlcv import (
    STATE_INVALID_SYMBOL,
    STATE_OK,
    TAIPEI_UTC_OFFSET_HOURS,
    rows_to_bars_frame,
)
from src.data.stock.stock_local_ohlcv import MAX_FILE_BYTES, parse_local_ohlcv_csv

# ── 具名常數 ────────────────────────────────────────────────────────────
#: 啟用開關＋受控資料夾（絕對路徑）的環境變數名。
ENV_LOCAL_OHLCV_DIR = "UI2_LOCAL_OHLCV_DIR"
#: 視為「本機」的位址／Host（精確比對；`::1:8501` 這類未括號 IPv6 不在其中）。
LOOPBACK_ADDRESSES: frozenset[str] = frozenset({"127.0.0.1", "localhost", "::1"})
#: 託管負向證據（NV：推測的最小集，未對真實託管環境驗證；只能多拒，不能單獨當隔離）。
HOSTED_CWD_PREFIXES: tuple[str, ...] = ("/mount/src",)
HOSTED_ENV_MARKERS: tuple[str, ...] = ("STREAMLIT_SHARING_MODE", "STREAMLIT_RUNTIME_ENV")
#: 清單上限：合格 CSV 檔數超過即 fail loud（不截斷）。
MAX_LIST_FILENAMES = 500
#: 掃描項上限（含非 CSV）：超過即 fail loud；防止對巨大資料夾做無界掃描。
MAX_SCAN_ENTRIES = 5000
#: Windows 保留裝置名（不分大小寫；含附加副檔名如 con.csv 亦保留）。list／query 共用的檔名述詞會拒絕。
WINDOWS_RESERVED_NAMES: frozenset[str] = frozenset({
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9"})
#: 唯一視為「已有路徑安全測試」的平台。
SUPPORTED_OS_NAME = "posix"
#: 檔名副檔名（小寫精確）。
CSV_SUFFIX = ".csv"
#: 讀檔分塊大小（bytes）。
_READ_CHUNK = 64 * 1024
_TAIPEI_TZ = timezone(timedelta(hours=TAIPEI_UTC_OFFSET_HOURS))

#: os.open 旗標（平台沒有的旗標為 0；Windows 無 O_NOFOLLOW／O_NONBLOCK，見模組 docstring）。
_OPEN_FLAGS = (os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
               | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_BINARY", 0))
#: 目錄 fd 的開啟旗標（平台沒有的旗標為 0）。
_DIR_FLAGS = (os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
              | getattr(os, "O_CLOEXEC", 0))
#: 平台是否支援以目錄 fd 開檔／scandir（不支援則退回路徑版；POSIX 之外本來就 `not_enabled`）。
_HAS_DIR_FD = (os.open in os.supports_dir_fd) and (os.scandir in os.supports_fd)
#: `LocalProof` 必備欄位（`object.__new__` 建出的空殼會缺欄位 → `bad_request`，不 raise）。
_PROOF_FIELDS = ("bind_address", "headers_present", "request_host", "proxy_header_names")
#: 本檔內部「通過」哨兵（不外洩）。
_OK = None


def _fail(op: str, code: str, vm=None) -> LocalLookupResponse:
    return LocalLookupResponse(op=op, ok=False, reason_code=code, vm=vm)


# ── A. 啟用與本機正向證明 ────────────────────────────────────────────────
def _hosted(environ: Mapping[str, str], cwd: object, roots: tuple[Path, Path] | None) -> bool:
    candidates = [os.fspath(cwd)]
    if roots is not None:
        candidates += [str(roots[0]), str(roots[1])]                # repo_root／cwd resolve 後
    if any(c.startswith(p) for c in candidates for p in HOSTED_CWD_PREFIXES):
        return True
    for key in HOSTED_ENV_MARKERS:
        v = environ.get(key)
        if v is not None and v != "":
            return True
    return False


def _is_loopback(value: object) -> bool:
    return type(value) is str and value in LOOPBACK_ADDRESSES      # 型別嚴格：非 str（含 list、str 子類別）一律不是本機


def _check_proof(proof: LocalProof) -> str | None:
    if not _is_loopback(proof.bind_address):
        return REASON_BIND_NOT_LOOPBACK
    if proof.headers_present is not True:
        return REASON_NO_REQUEST_CONTEXT
    if not _is_loopback(proof.request_host):
        return REASON_HOST_NOT_LOOPBACK
    if proof.proxy_header_names:
        return REASON_PROXY_HEADERS_PRESENT
    return _OK


# ── B. 受控目錄 ─────────────────────────────────────────────────────────
def _related(a: Path, b: Path) -> bool:
    """相等、a 是 b 的祖先、或 a 是 b 的子孫。"""
    return a == b or a.is_relative_to(b) or b.is_relative_to(a)


def _resolve_roots(repo_root: object, cwd: object) -> tuple[Path, Path] | None:
    try:
        return Path(repo_root).resolve(), Path(cwd).resolve()
    except (OSError, RuntimeError, ValueError, TypeError):
        return None


def _controlled_dir(raw: object, roots: tuple[Path, Path] | None) -> tuple[Path | None, str | None]:
    if not isinstance(raw, str) or "\x00" in raw or not os.path.isabs(raw) or roots is None:
        return None, REASON_DIR_INVALID
    try:
        resolved = Path(raw).resolve(strict=True)
        if not resolved.is_dir():
            return None, REASON_DIR_INVALID
    except (OSError, RuntimeError, ValueError):
        return None, REASON_DIR_INVALID
    if any(_related(resolved, root) for root in roots):
        return None, REASON_DIR_INSIDE_REPO
    return resolved, _OK


# ── 檔名規則（list 與 query 共用：被列出的檔名一定能被查）──────────────────
def _name_ok(name: object) -> bool:
    if type(name) is not str or name in ("", ".", ".."):
        return False
    if name.startswith(".") or not name.endswith(CSV_SUFFIX):
        return False
    if "/" in name or "\\" in name or "\x00" in name:
        return False
    if ":" in name:                                               # Windows ADS／磁碟機代號（C:x.csv）；結尾空白或點已被 endswith(".csv") 涵蓋
        return False
    if name.split(".", 1)[0].rstrip(" ").upper() in WINDOWS_RESERVED_NAMES:   # con.csv、COM1.csv…
        return False
    return all(c.isprintable() for c in name)             # 含孤立 surrogate（非 UTF-8 檔名經 surrogateescape）：不可印 → 拒


# ── C. list ─────────────────────────────────────────────────────────────
def _list_names(dir_fd: int, ctrl: Path) -> tuple[tuple[str, ...] | None, str | None]:
    names: list[str] = []
    scanned = 0
    try:
        with os.scandir(dir_fd if _HAS_DIR_FD else ctrl) as it:
            for entry in it:
                scanned += 1
                if scanned > MAX_SCAN_ENTRIES:
                    return None, REASON_DIR_INVALID
                name = entry.name
                if not _name_ok(name):
                    continue
                try:
                    regular = entry.is_file(follow_symlinks=False)
                    linked = entry.stat(follow_symlinks=False).st_nlink > 1 if regular else False
                except OSError:
                    continue                                      # stat 失敗＝跳過該檔
                if not regular or linked:                         # 硬連結檔 query 必拒 → 不列出
                    continue
                names.append(name)
                if len(names) > MAX_LIST_FILENAMES:
                    return None, REASON_DIR_INVALID
    except OSError:
        return None, REASON_DIR_INVALID
    return tuple(sorted(names)), _OK


# ── 目錄 fd（防 resolve 與 open 之間的目錄元件替換；見模組 docstring「據實限制」）────────────
def _stat_dir(path: Path) -> os.stat_result:
    return os.stat(path)


def _fd_realpath(fd: int) -> str | None:
    """Linux：fd 的真實路徑（`/proc/self/fd/<fd>`）。取不到（非 Linux／無 /proc、`OSError`／`ValueError`），
    或 `readlink` 回的不是 str（bytes／int／None…），一律回 None → 呼叫端 fail closed（`dir_invalid`）。永不 raise。"""
    try:
        out = os.readlink(f"/proc/self/fd/{fd}")
    except (OSError, ValueError):
        return None
    return out if isinstance(out, str) else None


def _open_dir(ctrl: Path, roots: tuple[Path, Path]) -> tuple[int | None, str | None]:
    """開受控目錄 fd 並驗證它就是 resolve 時看到的那個目錄。成功回 fd（呼叫端負責關閉）。"""
    try:
        pre = _stat_dir(ctrl)
        fd = os.open(os.fspath(ctrl), _DIR_FLAGS)
    except OSError:
        return None, REASON_DIR_INVALID
    keep = False
    try:
        try:
            st = os.fstat(fd)
        except OSError:
            return None, REASON_DIR_INVALID
        if not stat.S_ISDIR(st.st_mode) or (st.st_dev, st.st_ino) != (pre.st_dev, pre.st_ino):
            return None, REASON_DIR_INVALID
        real = _fd_realpath(fd)
        if real is None:                                      # 取不到真實路徑：unknown≠safe → fail closed
            return None, REASON_DIR_INVALID
        real_path = Path(real)
        if any(_related(real_path, root) for root in roots):
            return None, REASON_DIR_INSIDE_REPO
        if real_path != ctrl:
            return None, REASON_DIR_INVALID
        keep = True
        return fd, _OK
    finally:
        if not keep:
            os.close(fd)


# ── D. query：開檔與讀取 ─────────────────────────────────────────────────
def _read_bytes(dir_fd: int, ctrl: Path, name: str,
                roots: tuple[Path, Path]) -> tuple[bytes | None, str | None]:
    cand = ctrl / name
    try:
        real = cand.resolve()
    except (OSError, RuntimeError, ValueError):
        return None, REASON_FILE_INVALID
    if any(_related(real, root) for root in roots):
        return None, REASON_DIR_INSIDE_REPO
    if not real.is_relative_to(ctrl) or real != cand:       # 符號連結逃逸（或受控目錄內的任何符號連結）
        return None, REASON_FILE_INVALID
    try:
        if _HAS_DIR_FD:                                      # 不用 exists()/is_file() 再開（TOCTOU）
            fd = os.open(name, _OPEN_FLAGS, dir_fd=dir_fd)   # 相對於已驗證的目錄 fd；O_NOFOLLOW 擋最後一段
        else:
            fd = os.open(os.fspath(cand), _OPEN_FLAGS)
    except OSError:
        return None, REASON_FILE_UNREADABLE                  # 含 ELOOP（開檔時才被換成符號連結）、不存在；不帶 errno 文字
    try:
        try:
            st = os.fstat(fd)
            if not stat.S_ISREG(st.st_mode):
                return None, REASON_FILE_NOT_REGULAR
            if st.st_nlink > 1:                              # 硬連結：可能是 repo 內檔案的另一個名字
                return None, REASON_FILE_INVALID
            if st.st_size > MAX_FILE_BYTES:
                return None, REASON_FILE_TOO_LARGE
            chunks: list[bytes] = []
            total = 0
            while total <= MAX_FILE_BYTES:
                block = os.read(fd, min(_READ_CHUNK, MAX_FILE_BYTES + 1 - total))
                if not block:
                    break
                chunks.append(block)
                total += len(block)
        except OSError:
            return None, REASON_FILE_UNREADABLE
    finally:
        os.close(fd)
    if total > MAX_FILE_BYTES:
        return None, REASON_FILE_TOO_LARGE
    return b"".join(chunks), _OK


# ── E. 組裝 ─────────────────────────────────────────────────────────────
def _no_value_vm(symbol: object, source: object):
    """MISSING 態 vm：`close=None`、不補 0、不稱「查無此股」（P-M2g：parse 非 ok → MISSING＋parse_failed）。"""
    quote = build_quote_view(parse_ticker_input(symbol), loaded=True, fetch_error=None, close=None,
                             trade_date=None, fetched_at=None, source=source, is_stale=False)
    return _empty_result(quote)


def _empty_result(quote):
    return build_local_lookup_result(
        quote, open_=None, high=None, low=None, close=None, volume=None, as_of=None, ma20=None, ma240=None,
        bias20_pct=None, vol_ratio5=None, support=None, resistance=None, support_resistance_bars=None,
        source_user_declared=True)


def _assemble(data: bytes, symbol: str, today: date) -> LocalLookupResponse:
    imp = parse_local_ohlcv_csv(data, symbol, today=today)
    if imp.state == STATE_INVALID_SYMBOL:
        return _fail(OP_QUERY, REASON_BAD_REQUEST)
    if imp.state != STATE_OK or imp.latest is None or imp.as_of is None:
        return _fail(OP_QUERY, REASON_PARSE_FAILED, vm=_no_value_vm(imp.symbol, imp.source))
    try:
        latest = imp.latest
        bars = rows_to_bars_frame(imp.rows)
        # R23.55 SF1：本機匯入口徑只是使用者聲明、系統未驗證 → 必須明傳 basis_verified=False（關鍵字）。
        facts = build_stock_research_facts(bars, as_of=imp.as_of, basis_verified=False)
        days = staleness_days(imp.as_of, today=today)
        is_stale = days is None or days > STALE_DAYS_DAILY    # 無法判定新鮮度 → 視為過期（不假裝新鮮）
        quote = build_quote_view(
            parse_ticker_input(imp.symbol), loaded=True, fetch_error=None, close=latest.close,
            trade_date=imp.as_of.isoformat(), fetched_at=None, source=imp.source, is_stale=is_stale)
        if quote.state not in VALUE_BEARING:                  # 例如收盤超出顯示範圍：不以 ok 呈現
            return _fail(OP_QUERY, REASON_PARSE_FAILED, vm=_empty_result(quote))
        vm = build_local_lookup_result(
            quote, open_=latest.open, high=latest.high, low=latest.low, close=latest.close,
            volume=latest.volume_shares, as_of=imp.as_of.isoformat(),
            ma20=facts.ma.get(20), ma240=facts.ma.get(240), bias20_pct=facts.bias20_pct,
            vol_ratio5=facts.volume_ratio5, support=facts.support_20d, resistance=facts.resistance_20d,
            support_resistance_bars=facts.support_resistance_bars, source_user_declared=True)
    except (ValueError, ArithmeticError):
        return _fail(OP_QUERY, REASON_PARSE_FAILED, vm=_no_value_vm(imp.symbol, imp.source))
    return LocalLookupResponse(op=OP_QUERY, ok=True, vm=vm)


# ── 公開 API ────────────────────────────────────────────────────────────
def _taipei_today(now: datetime) -> date:
    return now.astimezone(_TAIPEI_TZ).date()


def _is_aware(now: object) -> bool:
    return isinstance(now, datetime) and now.tzinfo is not None and now.utcoffset() is not None


def _fspath_str(value: object) -> str | None:
    """`os.fspath(value)` 且結果必須是 str；bytes／拋例外／非 PathLike → None。只呼叫一次，之後一律用回傳值。"""
    try:
        out = os.fspath(value)                                # type: ignore[arg-type]
    except Exception:                                         # noqa: BLE001 — 任何 __fspath__ 例外都視為型別不符
        return None
    return out if isinstance(out, str) else None


def run_local_lookup(request: LocalLookupRequest, *, environ: Mapping[str, str] | None = None,
                     now: datetime | None = None, repo_root: object = None, cwd: object = None,
                     os_name: str | None = None) -> LocalLookupResponse:
    """見模組 docstring「判定順序」。全部參數皆可注入（測試用）；預設取 `os.environ`／當下／本檔推導的 repo 根／
    `os.getcwd()`／`os.name`。`request` 非 `LocalLookupRequest` 才 raise TypeError；其餘注入型別不符一律回 `bad_request`。"""
    if not isinstance(request, LocalLookupRequest):
        raise TypeError("request 必須是 LocalLookupRequest")
    op = getattr(request, "op", None)
    if op not in (OP_LIST, OP_QUERY):
        return _fail(OP_LIST, REASON_BAD_REQUEST)
    proof = getattr(request, "proof", None)
    env = os.environ if environ is None else environ
    cwd_given = None if cwd is None else _fspath_str(cwd)
    repo_given = None if repo_root is None else _fspath_str(repo_root)
    if (not isinstance(proof, LocalProof) or not all(hasattr(proof, f) for f in _PROOF_FIELDS)
            or not isinstance(env, Mapping)
            or (now is not None and not _is_aware(now))
            or (cwd is not None and cwd_given is None)
            or (repo_root is not None and repo_given is None)):
        return _fail(op, REASON_BAD_REQUEST)
    platform = os.name if os_name is None else os_name
    if type(platform) is not str or platform != SUPPORTED_OS_NAME:
        return _fail(op, REASON_NOT_ENABLED)                  # 非 POSIX：尚無路徑安全測試 → 視為未啟用（先於 env 判斷）
    raw_dir = env.get(ENV_LOCAL_OHLCV_DIR)
    if raw_dir is None or raw_dir == "":
        return _fail(op, REASON_NOT_ENABLED)                  # 此前未碰任何檔案系統
    try:
        cwd_value = os.getcwd() if cwd_given is None else cwd_given
    except OSError:
        return _fail(op, REASON_DIR_INVALID)                  # cwd 不可取＝無法排除託管／repo 關係 → fail closed
    reason = _check_proof(proof)
    if reason is not None:
        return _fail(op, reason)
    repo = Path(__file__).resolve().parents[2] if repo_given is None else repo_given
    roots = _resolve_roots(repo, cwd_value)
    if _hosted(env, cwd_value, roots):
        return _fail(op, REASON_HOSTED_RUNTIME)

    today: date | None = None
    if op == OP_QUERY:
        today = _taipei_today(datetime.now(timezone.utc) if now is None else now)
        probe = parse_local_ohlcv_csv(b"", request.symbol, today=today)   # 只為代號驗證（SSOT）；不碰檔案系統
        if probe.state == STATE_INVALID_SYMBOL:
            return _fail(op, REASON_BAD_REQUEST)

    ctrl, reason = _controlled_dir(raw_dir, roots)
    if reason is not None or ctrl is None or roots is None:
        return _fail(op, reason or REASON_DIR_INVALID)
    dir_fd, reason = _open_dir(ctrl, roots)
    if reason is not None or dir_fd is None:
        return _fail(op, reason or REASON_DIR_INVALID)
    try:
        if op == OP_LIST:
            names, reason = _list_names(dir_fd, ctrl)
            if reason is not None or names is None:
                return _fail(op, reason or REASON_DIR_INVALID)
            return LocalLookupResponse(op=OP_LIST, ok=True, filenames=names)
        filename = request.filename
        if filename is None or not _name_ok(filename):
            return _fail(op, REASON_FILE_INVALID)
        data, reason = _read_bytes(dir_fd, ctrl, filename, roots)
    finally:
        os.close(dir_fd)
    if reason is not None or data is None:
        return _fail(op, reason or REASON_FILE_UNREADABLE)
    if today is None or request.symbol is None:               # query 必有（L0 保證）；縱深防禦
        return _fail(op, REASON_BAD_REQUEST)
    return _assemble(data, request.symbol, today)
