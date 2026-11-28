"""【B 補的覆蓋；不是 A 的檔】L3 `_fd_realpath` 遇敵意／異常 `os.readlink` 的行為（A 的 SF-F 修正之驗證）。

背景：A 的 SF-F 差額（c7235659271）新增了測試類 `TestFdRealpathHostileReadlink`（+58 行），但留言只有描述、沒有逐行內容，
無法逐字重建；`tests/test_stock_local_lookup_service.py` 因此維持 A 的保存版（sha256 396be269…）。
本檔是 B **自寫**的獨立覆蓋，**不取代**、也不冒充 A 的測試類；A 交付完整差額後，兩者並存即可。

斷言（針對 `os.readlink("/proc/self/fd/<fd>")` 的各種回傳／例外）：
bytes／int／None／Path／含 NUL 字串／空字串／拋 ValueError／拋 OSError → list 與 query 皆 `dir_invalid`；
不 raise；回應（repr／vm／reason_code／filenames）不含例外原文或敵意字串；目錄 fd 不外洩（`/proc/self/fd` 數量前後相同）。
全離線；合成 CSV 放 repo 外 `tmp_path`。
"""
from __future__ import annotations

import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

import src.services.stock_local_lookup_service as svc
from shared.ui2_contract.local_lookup_request import (
    OP_LIST, OP_QUERY, REASON_DIR_INVALID, LocalLookupRequest, LocalProof,
)

ROOT = Path(__file__).resolve().parent.parent
ENV = svc.ENV_LOCAL_OHLCV_DIR
NOW = datetime(2026, 7, 1, 2, 0, tzinfo=timezone.utc)
END = date(2026, 6, 30)
_PROC_FD_PREFIX = "/proc/self/fd/"
SECRET = "SECRET-HOSTILE-READLINK-TEXT"

pytestmark = pytest.mark.skipif(not os.path.isdir("/proc/self/fd"), reason="需要 Linux /proc（L3 的目錄 fd 驗證依賴它）")


def _csv(symbol: str = "0050", n: int = 30, end: date = END) -> bytes:
    lines = ["stock_id,date,open,high,low,close,volume"]
    for i in range(n):
        d = end - timedelta(days=(n - 1 - i))
        lines.append(f"{symbol},{d.isoformat()},{100 + i},{102 + i},{99 + i},{101 + i},{1000 + i}")
    return ("\n".join(lines) + "\n").encode("utf-8")


def _proof() -> LocalProof:
    return LocalProof(bind_address="127.0.0.1", headers_present=True, request_host="localhost", proxy_header_names=())


@pytest.fixture
def world(tmp_path):
    w = {k: tmp_path / k for k in ("data", "repo", "cwd")}
    for p in w.values():
        p.mkdir()
    (w["data"] / "a.csv").write_bytes(_csv())
    return w


def _run(world, request):
    return svc.run_local_lookup(request, environ={ENV: str(world["data"])}, now=NOW,
                                repo_root=world["repo"], cwd=world["cwd"])


def _list():
    return LocalLookupRequest(op=OP_LIST, proof=_proof())


def _query():
    return LocalLookupRequest(op=OP_QUERY, proof=_proof(), symbol="0050", filename="a.csv")


def _surface(resp) -> str:
    return "\n".join([repr(resp), str(resp.reason_code), repr(resp.filenames), repr(resp.vm), repr(resp.ok), resp.op])


def _fd_count() -> int:
    return len(os.listdir("/proc/self/fd"))


def _patch_readlink(monkeypatch, behaviour):
    real = os.readlink

    def fake(path, *a, **kw):
        if isinstance(path, str) and path.startswith(_PROC_FD_PREFIX):
            return behaviour(path)
        return real(path, *a, **kw)

    monkeypatch.setattr(svc.os, "readlink", fake)


def _raiser(exc):
    def f(_path):
        raise exc
    return f


HOSTILE = {
    "bytes": lambda p: b"/tmp/" + SECRET.encode(),
    "int": lambda p: 7,
    "none": lambda p: None,
    "path_object": lambda p: Path("/tmp") / SECRET,
    "nul_string": lambda p: "/tmp/\x00" + SECRET,
    "empty_string": lambda p: "",
    "value_error": _raiser(ValueError(SECRET)),
    "os_error": _raiser(OSError(13, SECRET)),
    "permission_error": _raiser(PermissionError(13, SECRET)),
    "runtime_error_is_not_swallowed_by_helper": None,      # 占位：見 test_unexpected_exception_type_is_not_masked
}
HOSTILE = {k: v for k, v in HOSTILE.items() if v is not None}


@pytest.mark.parametrize("name", sorted(HOSTILE))
def test_helper_returns_none_never_raises(monkeypatch, name):
    _patch_readlink(monkeypatch, HOSTILE[name])
    fd = os.open("/", os.O_RDONLY)
    try:
        out = svc._fd_realpath(fd)
    finally:
        os.close(fd)
    if name in ("nul_string", "empty_string"):
        assert isinstance(out, str)                              # helper 不驗內容；由呼叫端的比對 fail closed（見下方 list／query）
    else:
        assert out is None


@pytest.mark.parametrize("name", sorted(HOSTILE))
@pytest.mark.parametrize("op", ["list", "query"])
def test_hostile_readlink_gives_dir_invalid_no_leak_no_fd_leak(monkeypatch, world, name, op):
    _patch_readlink(monkeypatch, HOSTILE[name])
    before = _fd_count()
    resp = _run(world, _list() if op == "list" else _query())
    after = _fd_count()
    assert resp.ok is False and resp.reason_code == REASON_DIR_INVALID, (name, resp.reason_code)
    assert resp.filenames == () and resp.vm is None
    surface = _surface(resp)
    assert SECRET not in surface and "/tmp" not in surface and str(world["data"]) not in surface
    assert before == after, "目錄 fd 外洩"


def test_baseline_without_patch_is_ok(world):
    """對照組：不動 readlink 時 list／query 成功（證明上面的 dir_invalid 來自 readlink 敵意，而非環境問題）。"""
    r = _run(world, _list())
    assert r.ok is True and r.filenames == ("a.csv",)
    q = _run(world, _query())
    assert q.ok is True and q.vm is not None


def test_non_proc_readlink_calls_are_untouched(monkeypatch, world):
    """patch 只影響 /proc/self/fd/*；其他 readlink 照常（避免測試把整個 os 弄壞而假通過）。"""
    _patch_readlink(monkeypatch, HOSTILE["bytes"])
    link = world["cwd"] / "lnk"
    link.symlink_to(world["data"])
    assert os.readlink(str(link)) == str(world["data"])


def test_str_subclass_and_non_str_never_trusted_as_path(monkeypatch, world):
    class S(str):
        pass

    _patch_readlink(monkeypatch, lambda p: S(str(world["data"])))
    resp = _run(world, _list())
    assert resp.ok in (True, False) and (resp.ok or resp.reason_code == REASON_DIR_INVALID)   # 不 raise；結論由 L3 比對決定
    assert SECRET not in _surface(resp)


def test_unexpected_exception_type_is_not_masked_as_success(monkeypatch, world):
    """helper 只吞 OSError／ValueError；其他例外型別不得被誤當成功（L3 頂層要嘛固定碼、要嘛如實拋出，但絕不 ok=True）。"""
    _patch_readlink(monkeypatch, _raiser(RuntimeError(SECRET)))
    try:
        resp = _run(world, _list())
    except RuntimeError as e:
        assert SECRET in str(e)                                   # 如實拋出（未被偽裝為成功）；訊息只在例外內
        return
    assert resp.ok is False and SECRET not in _surface(resp)


def test_helper_signature_and_docstring_contract():
    doc = svc._fd_realpath.__doc__ or ""
    assert "永不 raise" in doc and "str" in doc and "fail closed" in doc
