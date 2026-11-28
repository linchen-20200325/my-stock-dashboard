"""L3 `src/services/stock_local_lookup_service.run_local_lookup` 的離線測試（P-M2g；GitHub #1199 R23.52～R23.58）。

全離線：用 pytest `tmp_path` 建立 **repo 外**的合成 CSV 目錄；環境／時間／repo_root／cwd 全由參數注入，不依賴真環境變數。
使用真的 L1 parser、L2 facts、L0 builder（不 mock 它們）；只有「spy」與「故障注入」包住真函式。
"""
from __future__ import annotations

import ast
import errno
import os
import stat
import threading
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

import src.services.stock_local_lookup_service as svc
from shared.staleness import STALE_DAYS_DAILY, expected_latest_trading_day
from shared.ui2_contract.local_lookup_request import (
    OP_LIST,
    OP_QUERY,
    REASON_BAD_REQUEST,
    REASON_BIND_NOT_LOOPBACK,
    REASON_CODE_SET,
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
    LocalProof,
)
from shared.ui2_contract.local_lookup_result import TEXT_MISSING
from shared.ui2_contract.quote_view import QuoteViewState
from src.data.stock.stock_local_ohlcv import MAX_FILE_BYTES

ROOT = Path(__file__).resolve().parent.parent
SVC_PATH = ROOT / "src" / "services" / "stock_local_lookup_service.py"
ENV = svc.ENV_LOCAL_OHLCV_DIR
NOW = datetime(2026, 7, 1, 2, 0, tzinfo=timezone.utc)          # 台北 2026-07-01（週三）10:00
TODAY_TPE = date(2026, 7, 1)
END = date(2026, 6, 30)                                          # 預設 CSV 末列日期（距今 1 天）


# ── 小工具 ──────────────────────────────────────────────────────────────
def _csv(symbol: str = "0050", n: int = 30, end: date = END, volume_last: float | None = None,
         extra_header: str = "", extra_cell: str = "", volume_all: str | None = None) -> bytes:
    """合成日K：第 i 列（0 起）open=100+i、high=102+i、low=99+i、close=101+i、volume=1000+i；末列日期＝end。"""
    lines = ["stock_id,date,open,high,low,close,volume" + extra_header]
    for i in range(n):
        d = end - timedelta(days=(n - 1 - i))
        vol = 1000 + i if (volume_last is None or i < n - 1) else volume_last
        vol_text = volume_all if volume_all is not None else str(vol)
        lines.append(f"{symbol},{d.isoformat()},{100 + i},{102 + i},{99 + i},{101 + i},{vol_text}" + extra_cell)
    return ("\n".join(lines) + "\n").encode("utf-8")


def _proof(bind="127.0.0.1", present=True, host="localhost", proxies=()) -> LocalProof:
    if not present:
        return LocalProof(bind_address=bind, headers_present=False, request_host=None, proxy_header_names=())
    return LocalProof(bind_address=bind, headers_present=True, request_host=host, proxy_header_names=proxies)


def _list(proof=None) -> LocalLookupRequest:
    return LocalLookupRequest(op=OP_LIST, proof=proof or _proof())


def _query(filename="a.csv", symbol="0050", proof=None) -> LocalLookupRequest:
    return LocalLookupRequest(op=OP_QUERY, proof=proof or _proof(), symbol=symbol, filename=filename)


@pytest.fixture
def world(tmp_path):
    """data（受控目錄）、repo、cwd、outside 皆為 tmp_path 下互不相關的兄弟目錄。"""
    w = {k: tmp_path / k for k in ("data", "repo", "cwd", "outside")}
    for p in w.values():
        p.mkdir()
    w["tmp"] = tmp_path
    return w


def _run(world, request, *, environ=None, now=NOW, repo_root="__default__", cwd="__default__"):
    env = {ENV: str(world["data"])} if environ is None else environ
    return svc.run_local_lookup(
        request, environ=env, now=now,
        repo_root=world["repo"] if repo_root == "__default__" else repo_root,
        cwd=world["cwd"] if cwd == "__default__" else cwd)


def _put(world, name="a.csv", data: bytes | None = None):
    (world["data"] / name).write_bytes(_csv() if data is None else data)


def _within(seconds, fn, *args, unblock=None, **kw):
    """在 daemon thread 內執行，逾時就解除阻塞並讓測試**可見地失敗**（而不是掛住整個套件）。"""
    box: dict = {}

    def target():
        try:
            box["r"] = fn(*args, **kw)
        except BaseException as e:                     # noqa: BLE001 — 回傳給主執行緒重拋
            box["e"] = e

    t = threading.Thread(target=target, daemon=True)
    t.start()
    t.join(seconds)
    if t.is_alive():
        if unblock is not None:
            unblock()
            t.join(2)
        pytest.fail(f"run_local_lookup 在 {seconds}s 內沒有返回（疑似阻塞在 FIFO open）")
    if "e" in box:
        raise box["e"]
    return box["r"]


def _unblock_fifo(path):
    def go():
        try:
            fd = os.open(path, os.O_WRONLY | os.O_NONBLOCK)
            os.close(fd)
        except OSError:
            pass
    return go


def _all_text(resp) -> str:
    """回應的所有可見面：repr＋每個欄位＋vm 的 repr。"""
    parts = [repr(resp), str(resp.reason_code), repr(resp.filenames), repr(resp.vm)]
    return "\n".join(parts)


# ═══ 1. 證明矩陣 ═══════════════════════════════════════════════════════
class TestProofMatrix:
    def test_all_conditions_hold_query_and_list(self, world):
        _put(world)
        assert _run(world, _list()).ok is True
        assert _run(world, _query()).ok is True

    @pytest.mark.parametrize("bind", ["127.0.0.1", "localhost", "::1"])
    def test_bind_loopback_accepted(self, world, bind):
        assert _run(world, _list(_proof(bind=bind))).ok is True

    @pytest.mark.parametrize("host", ["127.0.0.1", "localhost", "::1"])
    def test_host_loopback_accepted(self, world, host):
        assert _run(world, _list(_proof(host=host))).ok is True

    @pytest.mark.parametrize("op_req", [_list, _query])
    @pytest.mark.parametrize("bind", [None, "", "0.0.0.0", "192.168.1.5", "example.com", "LOCALHOST",
                                      "127.0.0.2", "::", "127.0.0.1 ", "localhost.evil.com", "127"])
    def test_bind_not_loopback(self, world, op_req, bind):
        _put(world)
        r = _run(world, op_req(proof=_proof(bind=bind)))
        assert (r.ok, r.reason_code) == (False, REASON_BIND_NOT_LOOPBACK)

    @pytest.mark.parametrize("op_req", [_list, _query])
    def test_no_request_context(self, world, op_req):
        _put(world)
        r = _run(world, op_req(proof=_proof(present=False)))
        assert r.reason_code == REASON_NO_REQUEST_CONTEXT

    @pytest.mark.parametrize("op_req", [_list, _query])
    @pytest.mark.parametrize("host", [None, "example.com", "192.168.1.5", "::1:8501", "127.0.0.2", "0.0.0.0",
                                      "localhost.evil.com", "my-nas"])
    def test_host_not_loopback(self, world, op_req, host):
        _put(world)
        r = _run(world, op_req(proof=_proof(host=host)))
        assert r.reason_code == REASON_HOST_NOT_LOOPBACK

    @pytest.mark.parametrize("op_req", [_list, _query])
    @pytest.mark.parametrize("names", [("x-forwarded-for",), ("forwarded",), ("via",), ("x-real-ip",),
                                       ("forwarded", "x-forwarded-host")])
    def test_proxy_headers(self, world, op_req, names):
        _put(world)
        r = _run(world, op_req(proof=_proof(proxies=names)))
        assert r.reason_code == REASON_PROXY_HEADERS_PRESENT

    @pytest.mark.parametrize("op_req", [_list, _query])
    @pytest.mark.parametrize("cwd", ["/mount/src", "/mount/src/my-app", "/mount/src/x/y"])
    def test_hosted_cwd(self, world, op_req, cwd):
        _put(world)
        assert _run(world, op_req(), cwd=cwd).reason_code == REASON_HOSTED_RUNTIME

    @pytest.mark.parametrize("op_req", [_list, _query])
    @pytest.mark.parametrize("key", ["STREAMLIT_SHARING_MODE", "STREAMLIT_RUNTIME_ENV"])
    def test_hosted_env(self, world, op_req, key):
        _put(world)
        r = _run(world, op_req(), environ={ENV: str(world["data"]), key: "1"})
        assert r.reason_code == REASON_HOSTED_RUNTIME

    @pytest.mark.parametrize("key", ["STREAMLIT_SHARING_MODE", "STREAMLIT_RUNTIME_ENV"])
    def test_hosted_env_empty_value_is_not_a_marker(self, world, key):
        r = _run(world, _list(), environ={ENV: str(world["data"]), key: ""})
        assert r.ok is True

    def test_hosted_cwd_prefix_only_at_start(self, world):
        assert _run(world, _list(), cwd="/home/mount/src").ok is True

    def test_proof_fields_revalidated_not_trusting_truthiness(self, world):
        p = _proof()
        object.__setattr__(p, "headers_present", 1)           # truthy 但不是 True
        assert _run(world, _list(p)).reason_code == REASON_NO_REQUEST_CONTEXT

    @pytest.mark.parametrize("field,value,code", [
        ("bind_address", ["127.0.0.1"], REASON_BIND_NOT_LOOPBACK),
        ("request_host", ["localhost"], REASON_HOST_NOT_LOOPBACK),
        ("request_host", 7, REASON_HOST_NOT_LOOPBACK),
    ])
    def test_unhashable_or_wrong_type_proof_values_fail_closed(self, world, field, value, code):
        p = _proof()
        object.__setattr__(p, field, value)
        assert _run(world, _list(p)).reason_code == code

    def test_proxy_names_revalidated_even_if_tuple_swapped(self, world):
        p = _proof()
        object.__setattr__(p, "proxy_header_names", ["via"])    # 非空 list
        assert _run(world, _list(p)).reason_code == REASON_PROXY_HEADERS_PRESENT


class TestEnableAndOrder:
    @pytest.mark.parametrize("env", [{}, {ENV: ""}, {"OTHER": "x"}])
    @pytest.mark.parametrize("op_req", [_list, _query])
    def test_not_enabled(self, world, env, op_req):
        r = _run(world, op_req(), environ=env)
        assert (r.ok, r.reason_code, r.filenames, r.vm) == (False, REASON_NOT_ENABLED, (), None)

    @pytest.mark.parametrize("op_req", [_list, _query])
    def test_not_enabled_touches_no_filesystem(self, world, monkeypatch, op_req):
        def boom(*a, **k):
            raise AssertionError("filesystem access while not enabled")
        with monkeypatch.context() as m:
            for name in ("getcwd", "stat", "lstat", "scandir", "listdir", "open", "fstat", "readlink",
                         "access", "read"):
                m.setattr(os, name, boom)
            for name in ("resolve", "is_dir", "exists", "stat", "iterdir", "is_file"):
                m.setattr(Path, name, boom)
            r = svc.run_local_lookup(op_req(), environ={}, now=NOW)
        assert r.reason_code == REASON_NOT_ENABLED

    def test_not_enabled_beats_every_other_failure(self, world):
        bad = _proof(bind="0.0.0.0", present=True, host="example.com", proxies=("via",))
        r = _run(world, _list(bad), environ={}, cwd="/mount/src")
        assert r.reason_code == REASON_NOT_ENABLED

    # 條件依序：每一個 breaker 單獨成立 → 對應碼；兩個以上同時成立 → 取較前者
    BREAKERS = [
        (REASON_BIND_NOT_LOOPBACK, dict(bind="0.0.0.0")),
        (REASON_NO_REQUEST_CONTEXT, dict(present=False)),
        (REASON_HOST_NOT_LOOPBACK, dict(host="example.com")),
        (REASON_PROXY_HEADERS_PRESENT, dict(proxies=("via",))),
    ]

    def test_fixed_order_of_proof_conditions(self, world):
        for i, (code_i, kw_i) in enumerate(self.BREAKERS):
            for code_j, kw_j in self.BREAKERS[i + 1:]:
                kw = dict(kw_i)
                kw.update(kw_j)
                if kw.get("present") is False:
                    kw.pop("host", None)
                    kw.pop("proxies", None)
                r = _run(world, _list(_proof(**kw)))
                assert r.reason_code == code_i, (code_i, code_j)

    def test_hosted_comes_after_proof_conditions(self, world):
        r = _run(world, _list(_proof(host="example.com")), cwd="/mount/src")
        assert r.reason_code == REASON_HOST_NOT_LOOPBACK
        r = _run(world, _list(_proof(proxies=("via",))), environ={ENV: str(world["data"]),
                                                                  "STREAMLIT_SHARING_MODE": "1"})
        assert r.reason_code == REASON_PROXY_HEADERS_PRESENT

    def test_proof_checked_before_bad_symbol_and_before_dir(self, world):
        r = _run(world, _query(symbol="not a symbol", proof=_proof(bind="0.0.0.0")))
        assert r.reason_code == REASON_BIND_NOT_LOOPBACK
        r = _run(world, _list(_proof(bind="0.0.0.0")), environ={ENV: "relative/dir"})
        assert r.reason_code == REASON_BIND_NOT_LOOPBACK

    def test_symbol_checked_before_directory(self, world):
        r = _run(world, _query(symbol="12"), environ={ENV: str(world["tmp"] / "does_not_exist")})
        assert r.reason_code == REASON_BAD_REQUEST

    def test_directory_checked_before_filename(self, world):
        r = _run(world, _query(filename="../x.csv"), environ={ENV: str(world["tmp"] / "nope")})
        assert r.reason_code == REASON_DIR_INVALID

    def test_unknown_op_is_bad_request(self, world):
        req = _list()
        object.__setattr__(req, "op", "bogus")
        r = _run(world, req)
        assert (r.op, r.ok, r.reason_code) == (OP_LIST, False, REASON_BAD_REQUEST)

    def test_type_violations_raise_fixed_messages(self, world):
        with pytest.raises(TypeError):
            svc.run_local_lookup("not a request", environ={})        # type: ignore[arg-type]
        with pytest.raises(TypeError):
            svc.run_local_lookup(None, environ={})                    # type: ignore[arg-type]
        with pytest.raises(TypeError):
            svc.run_local_lookup(_proof(), environ={})                # type: ignore[arg-type]

    def test_every_failure_code_is_in_fixed_set(self, world):
        for kw in (dict(bind=None), dict(present=False), dict(host=None), dict(proxies=("via",))):
            assert _run(world, _list(_proof(**kw))).reason_code in REASON_CODE_SET


# ═══ 2. 受控目錄 ═══════════════════════════════════════════════════════
class TestControlledDirectory:
    @pytest.mark.parametrize("op_req", [_list, lambda: _query()])
    def test_relative_path(self, world, monkeypatch, op_req):
        monkeypatch.chdir(world["tmp"])                              # 「data」相對於真 cwd 其實存在
        r = _run(world, op_req(), environ={ENV: "data"})
        assert r.reason_code == REASON_DIR_INVALID

    @pytest.mark.parametrize("op_req", [_list, lambda: _query()])
    def test_nonexistent(self, world, op_req):
        r = _run(world, op_req(), environ={ENV: str(world["tmp"] / "nope")})
        assert r.reason_code == REASON_DIR_INVALID

    @pytest.mark.parametrize("op_req", [_list, lambda: _query()])
    def test_path_is_a_file_not_dir(self, world, op_req):
        f = world["tmp"] / "afile"
        f.write_bytes(b"x")
        assert _run(world, op_req(), environ={ENV: str(f)}).reason_code == REASON_DIR_INVALID

    @pytest.mark.parametrize("value", ["/tmp/x\x00y", 123, b"/tmp", ["/tmp"]])
    def test_bad_env_values(self, world, value):
        assert _run(world, _list(), environ={ENV: value}).reason_code == REASON_DIR_INVALID

    def test_whitespace_only_is_invalid_not_disabled(self, world):
        assert _run(world, _list(), environ={ENV: " "}).reason_code == REASON_DIR_INVALID

    @pytest.mark.parametrize("op_req", [_list, lambda: _query()])
    @pytest.mark.parametrize("proc", [True, False])
    @pytest.mark.parametrize("rel", ["", "data_cache", "data_cache/forward_test", "sub"])
    def test_inside_repo_root(self, world, monkeypatch, op_req, rel, proc):
        if not proc:                                                  # 非 Linux 的情形：只剩路徑版檢查也必須擋住
            monkeypatch.setattr(svc, "_fd_realpath", lambda fd: None)
        d = world["repo"] / rel if rel else world["repo"]
        d.mkdir(parents=True, exist_ok=True)
        assert _run(world, op_req(), environ={ENV: str(d)}).reason_code == REASON_DIR_INSIDE_REPO

    def test_ancestor_of_repo_is_rejected(self, world):
        assert _run(world, _list(), environ={ENV: str(world["tmp"])}).reason_code == REASON_DIR_INSIDE_REPO

    @pytest.mark.parametrize("op_req", [_list, lambda: _query()])
    def test_inside_cwd_or_equal_or_ancestor(self, world, op_req):
        inner = world["cwd"] / "inner"
        inner.mkdir()
        for d in (inner, world["cwd"], world["tmp"]):
            assert _run(world, op_req(), environ={ENV: str(d)}).reason_code == REASON_DIR_INSIDE_REPO

    def test_symlink_dir_into_repo_rejected(self, world):
        link = world["tmp"] / "linkdir"
        link.symlink_to(world["repo"], target_is_directory=True)
        assert _run(world, _list(), environ={ENV: str(link)}).reason_code == REASON_DIR_INSIDE_REPO

    def test_symlink_dir_into_cwd_rejected(self, world):
        link = world["tmp"] / "linkdir2"
        link.symlink_to(world["cwd"], target_is_directory=True)
        assert _run(world, _list(), environ={ENV: str(link)}).reason_code == REASON_DIR_INSIDE_REPO

    def test_symlink_dir_to_legit_dir_is_resolved_and_accepted(self, world):
        _put(world)
        link = world["tmp"] / "okdir"
        link.symlink_to(world["data"], target_is_directory=True)
        r = _run(world, _list(), environ={ENV: str(link)})
        assert (r.ok, r.filenames) == (True, ("a.csv",))

    def test_default_repo_root_is_derived_from_module_location(self, world):
        real_repo = Path(svc.__file__).resolve().parents[2]
        assert (real_repo / "tests").is_dir()
        r = svc.run_local_lookup(_list(), environ={ENV: str(real_repo / "tests")}, now=NOW, cwd=world["cwd"])
        assert r.reason_code == REASON_DIR_INSIDE_REPO
        r = svc.run_local_lookup(_list(), environ={ENV: str(real_repo / "tests")}, now=NOW, cwd=world["cwd"],
                                 repo_root=None)
        assert r.reason_code == REASON_DIR_INSIDE_REPO

    def test_defaults_work_for_unrelated_tmp_dir(self, world):
        _put(world)
        r = svc.run_local_lookup(_query(), environ={ENV: str(world["data"])}, now=NOW)
        assert r.ok is True

    def test_default_cwd_is_os_getcwd(self, world, monkeypatch):
        _put(world)
        monkeypatch.chdir(world["data"])                       # 真 cwd＝受控目錄 → 必須被當成 cwd 內
        r = svc.run_local_lookup(_list(), environ={ENV: str(world["data"])}, now=NOW,
                                 repo_root=world["repo"])
        assert r.reason_code == REASON_DIR_INSIDE_REPO

    def test_getcwd_failure_fails_closed(self, world, monkeypatch):
        def boom():
            raise FileNotFoundError
        monkeypatch.setattr(svc.os, "getcwd", boom)
        r = svc.run_local_lookup(_list(), environ={ENV: str(world["data"])}, now=NOW, repo_root=world["repo"])
        assert r.reason_code == REASON_DIR_INVALID

    def test_unresolvable_repo_root_fails_closed(self, world):
        r = _run(world, _list(), repo_root="a\x00b")
        assert r.reason_code == REASON_DIR_INVALID


# ═══ 3. list ═══════════════════════════════════════════════════════════
class TestList:
    def test_empty_dir(self, world):
        r = _run(world, _list())
        assert (r.ok, r.filenames, r.vm) == (True, (), None)

    def test_sorted_and_only_csv(self, world):
        for n in ("b.csv", "a.csv", "c.csv", "notes.txt", "x.csv.bak", "z.CSV", ".hidden.csv", ".csv"):
            (world["data"] / n).write_bytes(b"x")
        r = _run(world, _list())
        assert r.filenames == ("a.csv", "b.csv", "c.csv")

    def test_result_is_sorted_regardless_of_scandir_order(self, world, monkeypatch):
        for n in ("b.csv", "a.csv", "c.csv"):
            (world["data"] / n).write_bytes(b"x")
        real_scandir = os.scandir

        class _Ctx:
            def __enter__(self):
                self._it = real_scandir(world["data"])
                return iter(sorted(self._it.__enter__(), key=lambda e: e.name, reverse=True))

            def __exit__(self, *a):
                return self._it.__exit__(*a)

        monkeypatch.setattr(svc.os, "scandir", lambda p: _Ctx())
        assert _run(world, _list()).filenames == ("a.csv", "b.csv", "c.csv")

    def test_not_recursive(self, world):
        sub = world["data"] / "sub"
        sub.mkdir()
        (sub / "deep.csv").write_bytes(b"x")
        (world["data"] / "top.csv").write_bytes(b"x")
        assert _run(world, _list()).filenames == ("top.csv",)

    def test_strange_names_are_filtered_not_fatal(self, world):
        d = world["data"]
        (d / "ok.csv").write_bytes(b"x")
        (d / "a\\b.csv").write_bytes(b"x")               # POSIX 合法、L0 回應會拒 → L3 必須先過濾
        (d / "new\nline.csv").write_bytes(b"x")
        (d / "ctl\x01.csv").write_bytes(b"x")
        with open(os.path.join(os.fsencode(d), b"\xff\xfe.csv"), "wb") as fh:
            fh.write(b"x")
        (d / "dir.csv").mkdir()
        os.mkfifo(d / "fifo.csv")
        (world["outside"] / "t.csv").write_bytes(b"x")
        (d / "link_out.csv").symlink_to(world["outside"] / "t.csv")
        (world["repo"] / "r.csv").write_bytes(b"x")
        (d / "link_repo.csv").symlink_to(world["repo"] / "r.csv")
        (d / "link_in.csv").symlink_to(d / "ok.csv")
        (d / "dangling.csv").symlink_to(d / "missing")
        r = _run(world, _list())
        assert (r.ok, r.filenames) == (True, ("ok.csv",))

    def test_listing_does_not_read_file_contents(self, world, monkeypatch):
        _put(world)
        calls = []
        real_read = os.read
        monkeypatch.setattr(svc.os, "read", lambda *a, **k: calls.append(a) or real_read(*a, **k))
        real_open = os.open

        def only_dirs(path, flags, *a, **k):
            if not flags & getattr(os, "O_DIRECTORY", 0):
                pytest.fail("non-directory open while listing")
            return real_open(path, flags, *a, **k)

        monkeypatch.setattr(svc.os, "open", only_dirs)
        assert _run(world, _list()).ok is True
        assert calls == []

    def test_list_limit_exact_ok_and_over_fails_loud_no_truncation(self, world):
        for i in range(svc.MAX_LIST_FILENAMES):
            (world["data"] / f"f{i:04d}.csv").write_bytes(b"x")
        r = _run(world, _list())
        assert r.ok is True and len(r.filenames) == svc.MAX_LIST_FILENAMES
        (world["data"] / "one_more.csv").write_bytes(b"x")
        r = _run(world, _list())
        assert (r.ok, r.reason_code, r.filenames) == (False, REASON_DIR_INVALID, ())

    def test_list_limit_constant_is_500(self):
        assert svc.MAX_LIST_FILENAMES == 500

    def test_scan_limit_counts_non_csv_entries(self, world, monkeypatch):
        monkeypatch.setattr(svc, "MAX_SCAN_ENTRIES", 5)
        for i in range(5):
            (world["data"] / f"n{i}.txt").write_bytes(b"x")
        assert _run(world, _list()).ok is True
        (world["data"] / "n5.txt").write_bytes(b"x")
        assert _run(world, _list()).reason_code == REASON_DIR_INVALID

    def test_scandir_oserror_is_dir_invalid(self, world, monkeypatch):
        def boom(*a, **k):
            raise PermissionError(errno.EACCES, "SECRETPATH")
        monkeypatch.setattr(svc.os, "scandir", boom)
        r = _run(world, _list())
        assert r.reason_code == REASON_DIR_INVALID
        assert "SECRETPATH" not in _all_text(r)

    def test_entry_is_file_oserror_skips_entry_only(self, world, monkeypatch):
        _put(world, "good.csv")
        _put(world, "bad.csv")
        real_scandir = os.scandir

        class _Entry:
            def __init__(self, e):
                self._e, self.name = e, e.name

            def is_file(self, follow_symlinks=True):
                if self.name == "bad.csv":
                    raise OSError(errno.EIO, "x")
                return self._e.is_file(follow_symlinks=follow_symlinks)

            def stat(self, follow_symlinks=True):
                return self._e.stat(follow_symlinks=follow_symlinks)

        class _Ctx:
            def __enter__(self):
                self._it = real_scandir(world["data"])
                return (_Entry(e) for e in self._it.__enter__())

            def __exit__(self, *a):
                return self._it.__exit__(*a)

        monkeypatch.setattr(svc.os, "scandir", lambda p: _Ctx())
        assert _run(world, _list()).filenames == ("good.csv",)


# ═══ 4. query：檔名與檔案 ═══════════════════════════════════════════════
class TestQueryFilename:
    @pytest.mark.parametrize("name", [
        "/abs/a.csv", "../a.csv", "..", ".", "sub/a.csv", "a\\b.csv", "a\x00.csv", ".hidden.csv", ".csv",
        "a.txt", "a.CSV", "a.Csv", "a.csv.bak", "a", "C:a.csv", "new\nline.csv", "a.csv ", "a\x01.csv",
        "\udcff.csv",
    ])
    def test_invalid_filenames(self, world, name):
        _put(world)
        r = _run(world, _query(filename=name))
        assert (r.ok, r.reason_code, r.vm) == (False, REASON_FILE_INVALID, None)

    def test_directory_masquerading_as_csv(self, world):
        (world["data"] / "d.csv").mkdir()
        assert _run(world, _query("d.csv")).reason_code == REASON_FILE_NOT_REGULAR

    def test_fifo_is_not_regular_and_does_not_hang(self, world):
        fifo = world["data"] / "p.csv"
        os.mkfifo(fifo)
        r = _within(5, _run, world, _query("p.csv"), unblock=_unblock_fifo(fifo))
        assert r.reason_code == REASON_FILE_NOT_REGULAR

    def test_missing_file_is_unreadable(self, world):
        assert _run(world, _query("nope.csv")).reason_code == REASON_FILE_UNREADABLE

    def test_symlink_to_repo_file_rejected(self, world):
        (world["repo"] / "secret.csv").write_bytes(_csv())
        (world["data"] / "l.csv").symlink_to(world["repo"] / "secret.csv")
        r = _run(world, _query("l.csv"))
        assert (r.ok, r.reason_code) == (False, REASON_DIR_INSIDE_REPO)

    def test_symlink_to_outside_controlled_dir_rejected(self, world):
        (world["outside"] / "o.csv").write_bytes(_csv())
        (world["data"] / "l.csv").symlink_to(world["outside"] / "o.csv")
        r = _run(world, _query("l.csv"))
        assert (r.ok, r.reason_code) == (False, REASON_FILE_INVALID)

    def test_symlink_inside_controlled_dir_also_rejected(self, world):
        _put(world, "real.csv")
        (world["data"] / "l.csv").symlink_to(world["data"] / "real.csv")
        assert _run(world, _query("l.csv")).reason_code == REASON_FILE_INVALID

    def test_dangling_symlink_rejected(self, world):
        (world["data"] / "l.csv").symlink_to(world["outside"] / "gone.csv")
        assert _run(world, _query("l.csv")).reason_code == REASON_FILE_INVALID

    def test_swap_to_symlink_after_checks_is_blocked_by_o_nofollow(self, world, monkeypatch):
        _put(world, "f.csv")
        secret = world["outside"] / "target.csv"
        secret.write_bytes(_csv())                                  # 若被跟隨會讀成功
        real_open = os.open
        swapped = []

        def swapping_open(path, flags, *a, **k):
            if str(path).endswith("f.csv") and not swapped:
                swapped.append(1)
                target = world["data"] / "f.csv"
                os.remove(target)
                os.symlink(secret, target)
            return real_open(path, flags, *a, **k)

        monkeypatch.setattr(svc.os, "open", swapping_open)
        r = _run(world, _query("f.csv"))
        assert swapped and r.ok is False and r.reason_code == REASON_FILE_UNREADABLE

    def test_oflags_include_nofollow_cloexec_nonblock_where_available(self):
        assert svc._OPEN_FLAGS & os.O_RDONLY == os.O_RDONLY
        for name in ("O_NOFOLLOW", "O_CLOEXEC", "O_NONBLOCK"):
            if hasattr(os, name):
                assert svc._OPEN_FLAGS & getattr(os, name), name

    def test_no_exists_then_open_pattern(self):
        src = SVC_PATH.read_text(encoding="utf-8")
        for bad in (".exists(", ".is_file(", "os.path.exists", "os.path.isfile"):
            if bad == ".is_file(":
                assert "entry.is_file(follow_symlinks=False)" in src
                assert src.count(".is_file(") == 1                    # 只有 scandir 項目用，不用於 query 路徑
            else:
                assert bad not in src, bad

    def test_fd_is_closed_on_every_path(self, world, monkeypatch):
        opened, closed = [], []
        real_open, real_close = os.open, os.close

        def o(*a, **k):
            fd = real_open(*a, **k)
            opened.append(fd)
            return fd

        def c(fd):
            closed.append(fd)
            return real_close(fd)

        monkeypatch.setattr(svc.os, "open", o)
        monkeypatch.setattr(svc.os, "close", c)
        (world["data"] / "d.csv").mkdir()
        big = world["data"] / "big.csv"
        big.write_bytes(b"x" * (MAX_FILE_BYTES + 1))
        _put(world, "ok.csv")
        for n in ("d.csv", "big.csv", "ok.csv"):
            _run(world, _query(n))
        assert opened and sorted(opened) == sorted(closed)

    def test_fstat_oserror_is_unreadable_and_closes(self, world, monkeypatch):
        _put(world)
        opened, closed = [], []
        real_open, real_close, real_fstat = os.open, os.close, os.fstat

        def fs(fd):
            st = real_fstat(fd)
            if stat.S_ISDIR(st.st_mode):
                return st
            raise OSError(errno.EIO, "SECRET")

        def o(*a, **k):
            fd = real_open(*a, **k)
            opened.append(fd)
            return fd

        monkeypatch.setattr(svc.os, "fstat", fs)
        monkeypatch.setattr(svc.os, "open", o)
        monkeypatch.setattr(svc.os, "close", lambda fd: (closed.append(fd), real_close(fd))[1])
        r = _run(world, _query())
        assert r.reason_code == REASON_FILE_UNREADABLE and len(opened) == 2 and sorted(opened) == sorted(closed)
        assert "SECRET" not in _all_text(r)

    def test_read_oserror_is_unreadable(self, world, monkeypatch):
        _put(world)
        monkeypatch.setattr(svc.os, "read", lambda *a, **k: (_ for _ in ()).throw(OSError(errno.EIO, "SECRET")))
        r = _run(world, _query())
        assert r.reason_code == REASON_FILE_UNREADABLE


class TestFileSize:
    @staticmethod
    def _sized(n: int) -> bytes:
        """一份**有效**且長度恰為 n bytes 的 CSV（以忽略欄補長）。"""
        base = _csv(extra_header=",pad", extra_cell=",")
        pad = n - len(base)
        assert pad >= 0
        lines = base.decode("utf-8").split("\n")
        rows = [i for i, ln in enumerate(lines) if ln.endswith(",") and not ln.startswith("stock_id")]
        share, extra = divmod(pad, len(rows))                       # csv 單格有 128KiB 上限 → 平均分散到各列
        for k, i in enumerate(rows):
            lines[i] = lines[i] + "p" * (share + (1 if k < extra else 0))
        out = "\n".join(lines).encode("utf-8")
        assert len(out) == n
        return out

    def test_exactly_max_bytes_is_accepted(self, world):
        _put(world, data=self._sized(MAX_FILE_BYTES))
        r = _run(world, _query())
        assert (r.ok, r.reason_code) == (True, None)

    def test_one_byte_over_is_too_large(self, world):
        _put(world, data=self._sized(MAX_FILE_BYTES) + b"\n")
        r = _run(world, _query())
        assert (r.ok, r.reason_code, r.vm) == (False, REASON_FILE_TOO_LARGE, None)

    def test_huge_file_is_rejected_without_reading_everything(self, world, monkeypatch):
        _put(world, data=b"x" * (MAX_FILE_BYTES * 2))
        reads = []
        real_read = os.read
        monkeypatch.setattr(svc.os, "read", lambda *a, **k: reads.append(1) or real_read(*a, **k))
        assert _run(world, _query()).reason_code == REASON_FILE_TOO_LARGE
        assert reads == []                                         # fstat 先擋，連 read 都沒呼叫

    def test_read_cap_when_fstat_lies_about_size(self, world, monkeypatch):
        _put(world, data=b"x" * (MAX_FILE_BYTES + 10))
        real_fstat = os.fstat

        class _St:
            st_mode = stat.S_IFREG | 0o644
            st_size = 1
            st_nlink = 1

        def lying(fd):
            real = real_fstat(fd)
            return real if stat.S_ISDIR(real.st_mode) else _St()

        monkeypatch.setattr(svc.os, "fstat", lying)
        total = []
        real_read = os.read
        monkeypatch.setattr(svc.os, "read", lambda fd, n: (lambda b: (total.append(len(b)), b)[1])(real_read(fd, n)))
        r = _run(world, _query())
        assert r.reason_code == REASON_FILE_TOO_LARGE
        assert sum(total) == MAX_FILE_BYTES + 1                    # 最多讀 MAX+1

    def test_constant_is_from_l1(self):
        assert svc.MAX_FILE_BYTES == MAX_FILE_BYTES == 2 * 1024 * 1024


# ═══ 5. 組裝 ═══════════════════════════════════════════════════════════
class TestAssemble:
    def test_ok_vm_mapping_against_independent_arithmetic(self, world):
        _put(world)
        r = _run(world, _query())
        assert (r.op, r.ok, r.reason_code, r.filenames) == (OP_QUERY, True, None, ())
        vm = r.vm
        assert vm.state is QuoteViewState.OK and vm.has_data is True
        assert vm.symbol == "0050"
        assert vm.close_text == "130.00"
        assert vm.as_of_text == "資料日 2026-06-30"
        assert [(c.key, c.value_text) for c in vm.ohlcv] == [
            ("open", "129.00"), ("high", "131.00"), ("low", "128.00"), ("close", "130.00"), ("volume", "1,029")]
        ind = {c.key: c for c in vm.indicators}
        assert ind["ma20"].value_text == "120.50"                  # mean(111..130)
        assert ind["bias20"].value_text == "+7.88%"                # (130-120.5)/120.5
        assert ind["vol_ratio5"].value_text == "1.00 倍"           # 1029 / mean(1024..1028)
        assert ind["support"].value_text == "109.00" and ind["support"].label == "支撐（近20日）"
        assert ind["resistance"].value_text == "131.00" and ind["resistance"].label == "壓力（近20日）"
        assert ind["ma240"].is_missing and ind["ma240"].value_text == TEXT_MISSING   # 30 根 → 缺值，不是 0
        assert not any(c.is_missing for c in vm.ohlcv)

    def test_source_is_declared_by_user_and_fetched_at_unknown(self, world):
        _put(world)
        vm = _run(world, _query()).vm
        assert vm.source_text.endswith("｜使用者自述，未經系統驗證")
        assert "本機匯入" in vm.source_text
        assert vm.fetched_at_text == "抓取時間未知"

    def test_no_import_time_or_mtime_anywhere(self, world):
        _put(world)
        p = world["data"] / "a.csv"
        os.utime(p, (1_000_000_000, 1_000_000_000))                # mtime＝2001-09-09
        text = _all_text(_run(world, _query()))
        for frag in ("2001", "1000000000", "匯入時間", "mtime"):
            assert frag not in text
        stamp = (NOW).isoformat()[:10]
        assert "抓取時間 " not in text and f"抓取時間 {stamp}" not in text

    def test_leading_zero_symbol_preserved(self, world):
        _put(world, data=_csv("0050"))
        assert _run(world, _query(symbol="0050")).vm.symbol == "0050"
        assert _run(world, _query(symbol="0050")).vm.symbol != "50"

    def test_alphanumeric_symbol_and_lowercase_input(self, world):
        _put(world, data=_csv("00631L"))
        assert _run(world, _query(symbol="00631l")).vm.symbol == "00631L"

    def test_zero_volume_is_real_zero_not_missing(self, world):
        _put(world, data=_csv(volume_last=0))
        vol = _run(world, _query()).vm.ohlcv[4]
        assert (vol.value_text, vol.is_missing) == ("0", False)

    @pytest.mark.parametrize("symbol", ["12", "abc", "0050.TW", "0 050", "ＡＢＣＤ", "A050", "1234567"])
    def test_bad_symbol_is_bad_request_without_filesystem(self, world, symbol):
        _put(world)
        r = _run(world, _query(symbol=symbol), environ={ENV: str(world["tmp"] / "nope")})
        assert (r.ok, r.reason_code, r.vm) == (False, REASON_BAD_REQUEST, None)

    def test_bad_symbol_with_existing_file_is_still_bad_request(self, world):
        _put(world)
        assert _run(world, _query(symbol="12")).reason_code == REASON_BAD_REQUEST

    @pytest.mark.parametrize("label,data", [
        ("bad_value", _csv().replace(b",101,", b",abc,", 1)),
        ("missing_value", _csv().replace(b",101,", b",,", 1)),
        ("missing_column", b"stock_id,date,open,close\n0050,2026-06-30,1,1\n"),
        ("stock_id_mismatch", _csv("2330")),
        ("big5", "stock_id,date,open,high,low,close,volume\n中文,2026-06-30,1,1,1,1,1\n".encode("big5")),
        ("header_only_no_data", b"stock_id,date,open,high,low,close,volume\n"),
        ("empty_file", b""),
        ("nul_byte", b"stock_id,date\x00"),
        ("future_date", _csv(end=date(2026, 7, 2))),
        ("duplicate_dates", _csv().replace(b"2026-06-29", b"2026-06-30", 1)),
        ("price_zero", _csv().replace(b",129,", b",0,", 1)),
        ("ohlc_violation", _csv().replace(b",131,", b",120,", 1)),
    ])
    def test_parse_failures_give_missing_vm_and_parse_failed(self, world, label, data):
        _put(world, data=data)
        r = _run(world, _query())
        assert (r.ok, r.reason_code) == (False, REASON_PARSE_FAILED), label
        vm = r.vm
        assert vm is not None and vm.state is QuoteViewState.MISSING
        assert vm.has_data is False and vm.close_text is None and vm.ohlcv == () and vm.indicators == ()
        text = _all_text(r)
        assert "查無" not in text and "0.00" not in text
        assert vm.notice_text == "資料未備（非 0）"

    def test_out_of_display_range_close_is_not_presented_as_ok(self, world):
        rows = _csv().decode("utf-8").split("\n")
        rows[-2] = f"0050,{END.isoformat()},2000000,2000001,1999999,2000000,5"
        _put(world, data="\n".join(rows).encode("utf-8"))
        r = _run(world, _query())
        assert (r.ok, r.reason_code) == (False, REASON_PARSE_FAILED)
        assert r.vm.state is QuoteViewState.MISSING and r.vm.has_data is False

    @pytest.mark.parametrize("exc", [ValueError("SECRETX"), ArithmeticError("SECRETX"), OverflowError("SECRETX")])
    def test_assembly_errors_become_parse_failed_without_leak(self, world, monkeypatch, exc):
        _put(world)

        def boom(rows):
            raise exc

        monkeypatch.setattr(svc, "rows_to_bars_frame", boom)
        r = _run(world, _query())
        assert (r.ok, r.reason_code) == (False, REASON_PARSE_FAILED)
        assert r.vm.state is QuoteViewState.MISSING
        assert "SECRETX" not in _all_text(r)

    def test_invalid_symbol_reported_by_main_parse_is_bad_request(self, world, monkeypatch):
        """縱深防禦：探測通過後，主解析若仍回 INVALID_SYMBOL → bad_request（不是 parse_failed）。"""
        _put(world)
        real = svc.parse_local_ohlcv_csv
        monkeypatch.setattr(svc, "parse_local_ohlcv_csv",
                            lambda b, s, *, today: real(b, s if b == b"" else "x", today=today))
        r = _run(world, _query())
        assert (r.ok, r.reason_code, r.vm) == (False, REASON_BAD_REQUEST, None)

    def test_facts_input_error_becomes_parse_failed(self, world, monkeypatch):
        from src.compute.strategy.stock_research_facts import StockResearchFactsInputError
        _put(world)

        def boom(bars, **kw):
            raise StockResearchFactsInputError("SECRETX")

        monkeypatch.setattr(svc, "build_stock_research_facts", boom)
        r = _run(world, _query())
        assert (r.ok, r.reason_code) == (False, REASON_PARSE_FAILED)

    def test_programming_errors_other_than_value_arithmetic_are_not_swallowed(self, world, monkeypatch):
        _put(world)
        monkeypatch.setattr(svc, "rows_to_bars_frame", lambda rows: (_ for _ in ()).throw(KeyError("x")))
        with pytest.raises(KeyError):
            _run(world, _query())

    def test_basis_verified_is_passed_as_keyword_false(self, world, monkeypatch):
        _put(world)
        calls = []
        real = svc.build_stock_research_facts

        def spy(*args, **kw):
            calls.append((args, kw))
            return real(*args, **kw)

        monkeypatch.setattr(svc, "build_stock_research_facts", spy)
        assert _run(world, _query()).ok is True
        assert len(calls) == 1
        args, kw = calls[0]
        assert len(args) == 1 and "basis_verified" in kw and kw["basis_verified"] is False
        assert kw["as_of"] == END

    def test_facts_limitations_reflect_unverified_basis(self, world, monkeypatch):
        """端到端：真 facts 回 `price_basis_verified=False`（若漏傳會是 True）。"""
        _put(world)
        seen = []
        real = svc.build_stock_research_facts

        def spy(*a, **kw):
            f = real(*a, **kw)
            seen.append(f)
            return f

        monkeypatch.setattr(svc, "build_stock_research_facts", spy)
        _run(world, _query())
        assert seen[0].price_basis_verified is False and seen[0].price_basis == "unadjusted_declared"

    def test_builder_calls_use_declared_source_and_no_fetched_at(self, world, monkeypatch):
        _put(world)
        seen = {}
        rq, rr = svc.build_quote_view, svc.build_local_lookup_result

        def q(*a, **kw):
            seen["quote"] = kw
            return rq(*a, **kw)

        def r_(*a, **kw):
            seen["result"] = kw
            return rr(*a, **kw)

        monkeypatch.setattr(svc, "build_quote_view", q)
        monkeypatch.setattr(svc, "build_local_lookup_result", r_)
        _run(world, _query())
        assert seen["quote"]["fetched_at"] is None and seen["quote"]["loaded"] is True
        assert seen["quote"]["fetch_error"] is None
        assert seen["result"]["source_user_declared"] is True
        assert seen["result"]["as_of"] == "2026-06-30" and isinstance(seen["result"]["as_of"], str)
        assert seen["result"]["volume"] == 1029 and seen["result"]["open_"] == 129

    def test_missing_vm_also_declares_user_source(self, world, monkeypatch):
        _put(world, data=_csv().replace(b",101,", b",abc,", 1))
        seen = []
        rr = svc.build_local_lookup_result
        monkeypatch.setattr(svc, "build_local_lookup_result", lambda *a, **kw: (seen.append(kw), rr(*a, **kw))[1])
        _run(world, _query())
        assert seen and seen[0]["source_user_declared"] is True

    def test_parse_receives_taipei_today(self, world, monkeypatch):
        _put(world)
        seen = []
        real = svc.parse_local_ohlcv_csv
        monkeypatch.setattr(svc, "parse_local_ohlcv_csv", lambda b, s, *, today: (seen.append(today), real(b, s, today=today))[1])
        _run(world, _query())
        assert seen[-1] == TODAY_TPE


class TestStaleAndTaipeiDay:
    @staticmethod
    def _chip(world, now, end):
        _put(world, data=_csv(end=end))
        r = _run(world, _query(), now=now)
        assert r.ok is True
        return r.vm.chip_text, r.vm.state

    def test_weekday_boundary_uses_shared_constant(self, world):
        today = TODAY_TPE
        exp = expected_latest_trading_day(today=today)
        assert exp == today
        assert self._chip(world, NOW, exp - timedelta(days=STALE_DAYS_DAILY)) == ("資料正常", QuoteViewState.OK)
        assert self._chip(world, NOW, exp - timedelta(days=STALE_DAYS_DAILY + 1)) == ("資料過期", QuoteViewState.STALE)

    def test_weekend_uses_expected_trading_day(self, world):
        sat = datetime(2026, 6, 27, 4, 0, tzinfo=timezone.utc)      # 台北 2026-06-27 週六
        assert date(2026, 6, 27).weekday() == 5
        exp = expected_latest_trading_day(today=date(2026, 6, 27))
        assert exp == date(2026, 6, 26)
        assert self._chip(world, sat, exp - timedelta(days=STALE_DAYS_DAILY))[1] is QuoteViewState.OK
        assert self._chip(world, sat, exp - timedelta(days=STALE_DAYS_DAILY + 1))[1] is QuoteViewState.STALE

    def test_stale_still_shows_data(self, world):
        _put(world, data=_csv(end=date(2026, 6, 1)))
        r = _run(world, _query())
        assert r.ok is True and r.vm.has_data is True and r.vm.state is QuoteViewState.STALE

    def test_taipei_midnight_boundary(self, world):
        """UTC 還是 6/30，台北已是 7/1 00:30：末列 7/1 不算「未來日」。"""
        now = datetime(2026, 6, 30, 16, 30, tzinfo=timezone.utc)
        _put(world, data=_csv(end=date(2026, 7, 1)))
        assert _run(world, _query(), now=now).ok is True
        before = datetime(2026, 6, 30, 15, 59, tzinfo=timezone.utc)   # 台北 6/30 23:59
        r = _run(world, _query(), now=before)
        assert (r.ok, r.reason_code) == (False, REASON_PARSE_FAILED)

    def test_now_with_non_utc_offset(self, world):
        now = datetime(2026, 7, 1, 0, 30, tzinfo=timezone(timedelta(hours=8)))
        _put(world, data=_csv(end=date(2026, 7, 1)))
        assert _run(world, _query(), now=now).ok is True

    def test_default_now_is_real_clock_not_fixed(self, world):
        end = date.today()
        _put(world, data=_csv(end=end - timedelta(days=1)))
        r = svc.run_local_lookup(_query(), environ={ENV: str(world["data"])}, repo_root=world["repo"],
                                 cwd=world["cwd"])
        assert r.ok is True


# ═══ 6. 洩漏 ═══════════════════════════════════════════════════════════
class TestNoLeak:
    MARK = "ZZSECRETMARKZZ"

    def _scenario_world(self, tmp_path):
        d = tmp_path / f"dir_{self.MARK}"
        d.mkdir()
        (tmp_path / "repo").mkdir()
        (tmp_path / "cwd").mkdir()
        return d

    def _go(self, tmp_path, request, **kw):
        d = self._scenario_world(tmp_path) if not (tmp_path / f"dir_{self.MARK}").exists() \
            else tmp_path / f"dir_{self.MARK}"
        env = kw.pop("environ", {ENV: str(d)})
        return d, svc.run_local_lookup(request, environ=env, now=NOW, repo_root=tmp_path / "repo",
                                       cwd=tmp_path / "cwd", **kw)

    @pytest.mark.parametrize("variant", [
        "bad_cell", "bad_header", "big5", "missing_file", "dir_named_csv", "oversize", "mismatch",
    ])
    def test_failures_expose_no_path_name_or_content(self, tmp_path, caplog, capsys, variant):
        caplog.set_level("DEBUG")
        d = self._scenario_world(tmp_path)
        name = f"file_{self.MARK}.csv"
        body = {
            "bad_cell": _csv().replace(b",101,", f",{self.MARK},".encode(), 1),
            "bad_header": f"{self.MARK},date\n{self.MARK},{self.MARK}\n".encode(),
            "big5": f"stock_id,date\n{self.MARK}中文,x\n".encode("big5"),
            "mismatch": _csv(symbol="2330"),
        }.get(variant)
        if variant == "dir_named_csv":
            (d / name).mkdir()
        elif variant == "oversize":
            (d / name).write_bytes(self.MARK.encode() * (MAX_FILE_BYTES // 5))
        elif body is not None:
            (d / name).write_bytes(body)
        _, r = self._go(tmp_path, _query(filename=name))
        assert r.ok is False and r.reason_code in REASON_CODE_SET
        cap = capsys.readouterr()
        blob = _all_text(r) + caplog.text + cap.out + cap.err
        assert self.MARK not in blob and str(tmp_path) not in blob and "dir_" not in blob

    def test_success_exposes_no_path_or_filename(self, tmp_path, caplog, capsys):
        caplog.set_level("DEBUG")
        d = self._scenario_world(tmp_path)
        name = f"file_{self.MARK}.csv"
        (d / name).write_bytes(_csv())
        _, r = self._go(tmp_path, _query(filename=name))
        assert r.ok is True
        blob = _all_text(r) + caplog.text + capsys.readouterr().out
        assert self.MARK not in blob and str(tmp_path) not in blob

    def test_list_exposes_filenames_only_not_directory(self, tmp_path, caplog, capsys):
        caplog.set_level("DEBUG")
        d = self._scenario_world(tmp_path)
        (d / "ok.csv").write_bytes(b"x")
        _, r = self._go(tmp_path, _list())
        assert r.filenames == ("ok.csv",)
        blob = _all_text(r) + caplog.text + capsys.readouterr().out
        assert self.MARK not in blob and str(tmp_path) not in blob

    @pytest.mark.parametrize("which", ["dir_invalid", "inside_repo", "scandir_error"])
    def test_directory_failures_expose_nothing(self, tmp_path, caplog, capsys, which, monkeypatch):
        caplog.set_level("DEBUG")
        d = self._scenario_world(tmp_path)
        env = {ENV: str(tmp_path / f"missing_{self.MARK}")}
        if which == "inside_repo":
            env = {ENV: str(tmp_path / "repo")}
        elif which == "scandir_error":
            env = {ENV: str(d)}
            monkeypatch.setattr(svc.os, "scandir",
                                lambda p: (_ for _ in ()).throw(PermissionError(13, self.MARK, str(d))))
        _, r = self._go(tmp_path, _list(), environ=env)
        assert r.ok is False
        blob = _all_text(r) + caplog.text + capsys.readouterr().out
        assert self.MARK not in blob and str(tmp_path) not in blob

    def test_reason_codes_always_in_fixed_set(self, world):
        scenarios = [
            lambda: _run(world, _list(), environ={}),
            lambda: _run(world, _query("nope.csv")),
            lambda: _run(world, _query("../x.csv")),
            lambda: _run(world, _query(symbol="12")),
        ]
        for s in scenarios:
            assert s().reason_code in REASON_CODE_SET

    def test_repr_of_request_hides_secret_fields(self, world):
        text = repr(_query(filename="FILENAME_MARK.csv", symbol="0050"))
        assert "FILENAME_MARK" not in text and "0050" not in text


# ═══ 6b. R23.59／P-M2j：平台、檔名、短序列、目錄 fd、硬連結、型別 ═══════════════════
def _boom_fs(m):
    def boom(*a, **k):
        raise AssertionError("filesystem access")
    for name in ("getcwd", "stat", "lstat", "scandir", "listdir", "open", "fstat", "readlink", "access", "read"):
        m.setattr(os, name, boom)
    for name in ("resolve", "is_dir", "exists", "stat", "iterdir", "is_file"):
        m.setattr(Path, name, boom)


class TestPlatformGate:
    @pytest.mark.parametrize("op_req", [_list, _query])
    @pytest.mark.parametrize("name", ["nt", "java", "", "Posix", "posix ", "darwin", 5, b"posix", ["posix"]])
    def test_non_posix_os_name_is_not_enabled_without_fs_access(self, world, monkeypatch, op_req, name):
        with monkeypatch.context() as m:
            _boom_fs(m)
            r = svc.run_local_lookup(op_req(), environ={ENV: str(world["data"])}, now=NOW, os_name=name)
        assert (r.ok, r.reason_code, r.filenames, r.vm) == (False, REASON_NOT_ENABLED, (), None)

    @pytest.mark.parametrize("op_req", [_list, _query])
    @pytest.mark.parametrize("name", ["nt", "java", None, "", 5])
    def test_default_comes_from_os_name_and_unknown_is_not_safe(self, world, monkeypatch, op_req, name):
        with monkeypatch.context() as m:
            _boom_fs(m)
            m.setattr(os, "name", name)
            r = svc.run_local_lookup(op_req(), environ={ENV: str(world["data"])}, now=NOW)
        assert r.reason_code == REASON_NOT_ENABLED

    def test_posix_is_accepted(self, world):
        _put(world)
        assert svc.run_local_lookup(_list(), environ={ENV: str(world["data"])}, now=NOW, repo_root=world["repo"],
                                    cwd=world["cwd"], os_name="posix").ok is True

    def test_platform_is_checked_before_proof_and_env(self, world):
        r = svc.run_local_lookup(_list(_proof(bind="0.0.0.0")), environ={ENV: str(world["data"])}, now=NOW,
                                 os_name="nt")
        assert r.reason_code == REASON_NOT_ENABLED

    def test_type_checks_come_before_platform(self, world):
        r = svc.run_local_lookup(_list(), environ={ENV: str(world["data"])}, now="x", os_name="nt")  # type: ignore[arg-type]
        assert r.reason_code == REASON_BAD_REQUEST


class TestWindowsLikeNames:
    RESERVED = (["CON", "PRN", "AUX", "NUL"] + [f"COM{i}" for i in range(1, 10)] + [f"LPT{i}" for i in range(1, 10)])

    def test_reserved_set_is_exact(self):
        assert set(self.RESERVED) == set(svc.WINDOWS_RESERVED_NAMES) and len(svc.WINDOWS_RESERVED_NAMES) == 22

    @pytest.mark.parametrize("base", RESERVED)
    @pytest.mark.parametrize("variant", ["{}", "{}", "{l}", "{t}"])
    def test_reserved_names_rejected_for_query(self, world, base, variant):
        name = variant.format(base, l=base.lower(), t=base.title()) + ".csv"
        _put(world, name)
        assert _run(world, _query(name)).reason_code == REASON_FILE_INVALID

    def test_reserved_names_filtered_from_list_but_lookalikes_kept(self, world):
        for n in ("con.csv", "CON.csv", "Com1.csv", "lpt9.csv", "nul.csv", "aux.csv", "prn .csv", "con.x.csv",
                  "COM10.csv", "console.csv", "com.csv", "lpt0.csv", "a.con.csv", "x .csv", "acon.csv"):
            _put(world, n)
        r = _run(world, _list())
        assert r.filenames == ("COM10.csv", "a.con.csv", "acon.csv", "com.csv", "console.csv", "lpt0.csv", "x .csv")

    @pytest.mark.parametrize("name", ["a:b.csv", "a.csv:stream", "a.csv:$DATA", ":x.csv", "C:x.csv", "x.csv ", "x.csv.",
                                      "x.csv  ", "x .csv:"])
    def test_colon_and_trailing_space_or_dot_rejected(self, world, name):
        if "/" not in name:
            (world["data"] / name).write_bytes(_csv())
        assert _run(world, _query(name)).reason_code == REASON_FILE_INVALID
        assert name not in _run(world, _list()).filenames

    def test_predicate_directly(self):
        assert svc._name_ok("ok.csv") and svc._name_ok("x .csv") and svc._name_ok("COM10.csv")
        for bad in ("a:b.csv", "con.csv", "x.csv ", "x.csv.", "CON.CSV", "Aux.csv", "lpt1.csv", "nul .csv"):
            assert not svc._name_ok(bad), bad


class TestShortSequencesAreMissingNotZero:
    @staticmethod
    def _vm(world, n, **kw):
        _put(world, data=_csv(n=n, **kw))
        r = _run(world, _query())
        assert r.ok is True, (n, r.reason_code)
        return r.vm, {c.key: c for c in r.vm.indicators}

    @pytest.mark.parametrize("n,missing", [
        (5, {"ma20", "ma240", "bias20", "vol_ratio5"}),
        (10, {"ma20", "ma240", "bias20"}),
        (19, {"ma20", "ma240", "bias20"}),
        (20, {"ma240", "bias20"}),
        (21, {"ma240"}),
    ])
    def test_missing_cells_are_text_missing(self, world, n, missing):
        vm, ind = self._vm(world, n)
        for key in ("ma20", "ma240", "bias20", "vol_ratio5"):
            c = ind[key]
            if key in missing:
                assert (c.is_missing, c.value_text) == (True, TEXT_MISSING), (n, key)
            else:
                assert c.is_missing is False and c.value_text != TEXT_MISSING, (n, key)
        for key in missing:                                       # 絕不是 0／close／0 倍的偽值
            t = ind[key].value_text
            assert t not in ("0.00%", "+0.00%", "0.00 倍", "0.00", vm.close_text), (n, key, t)

    def test_values_when_present_are_real_numbers(self, world):
        vm, ind = self._vm(world, 21)
        assert ind["ma20"].value_text == "111.50"                  # mean(close 102..121)
        assert ind["bias20"].value_text.startswith("+") and ind["vol_ratio5"].value_text.endswith("倍")
        _, ind20 = self._vm(world, 20)
        assert ind20["ma20"].value_text == "110.50"                # mean(101..120)

    @pytest.mark.parametrize("n,label", [(5, "（近5根日K）"), (10, "（近10根日K）"), (19, "（近19根日K）"), (20, "（近20日）")])
    def test_support_resistance_label_tells_real_window(self, world, n, label):
        _, ind = self._vm(world, n)
        assert ind["support"].label == "支撐" + label and ind["resistance"].label == "壓力" + label
        assert not ind["support"].is_missing

    def test_f1_overflowing_volume_gives_missing_ratio_not_zero(self, world):
        vm, ind = self._vm(world, 30, volume_all="1.7e308")
        c = ind["vol_ratio5"]
        assert (c.is_missing, c.value_text) == (True, TEXT_MISSING)
        assert "0.0" not in c.value_text

    def test_f1_case_other_cells_still_fine(self, world):
        vm, ind = self._vm(world, 30, volume_all="1.7e308")
        assert ind["ma20"].is_missing is False and ind["bias20"].is_missing is False
        assert vm.ohlcv[3].value_text == "130.00"


def _race_world(world):
    data, evil_root = world["data"], world["repo"] / "sub"
    ctrl = data / "ext" / "x"
    ctrl.mkdir(parents=True)
    (ctrl / "a.csv").write_bytes(_csv())
    (evil_root / "x").mkdir(parents=True)
    (evil_root / "x" / "a.csv").write_bytes(_csv(n=40))          # 與原檔不同（收盤 140.00 vs 130.00）
    (evil_root / "x" / "evil.csv").write_bytes(_csv())

    def swap():
        os.rename(data / "ext", data / "ext_orig")
        os.symlink(evil_root, data / "ext")
    return ctrl, swap


needs_proc = pytest.mark.skipif(not os.path.isdir("/proc/self/fd"), reason="無 /proc/self/fd（非 Linux）")


class TestDirectoryFdRace:
    @pytest.mark.parametrize("op_req", [_list, _query])
    @pytest.mark.parametrize("proc", [True, False])
    def test_component_swapped_between_resolve_and_dir_open_fails_closed(self, world, monkeypatch, op_req, proc):
        ctrl, swap = _race_world(world)
        if not proc:
            monkeypatch.setattr(svc, "_fd_realpath", lambda fd: None)
        real_open, done = os.open, []

        def swapping_open(path, flags, *a, **k):
            if flags & getattr(os, "O_DIRECTORY", 0) and not done:
                done.append(1)
                swap()
            return real_open(path, flags, *a, **k)

        monkeypatch.setattr(svc.os, "open", swapping_open)
        r = _run(world, op_req(), environ={ENV: str(ctrl)})
        assert done and (r.ok, r.reason_code) == (False, REASON_DIR_INVALID)
        assert "140.00" not in _all_text(r)

    @needs_proc
    @pytest.mark.parametrize("op_req", [_list, _query])
    def test_swap_before_stat_is_caught_by_proc_realpath(self, world, monkeypatch, op_req):
        ctrl, swap = _race_world(world)
        real_stat, done = svc._stat_dir, []

        def swapping_stat(path):
            if not done:
                done.append(1)
                swap()
            return real_stat(path)

        monkeypatch.setattr(svc, "_stat_dir", swapping_stat)
        r = _run(world, op_req(), environ={ENV: str(ctrl)})
        assert done and (r.ok, r.reason_code) == (False, REASON_DIR_INSIDE_REPO)

    @pytest.mark.parametrize("op_req", [_list, _query])
    def test_swap_before_stat_without_proc_fails_closed(self, world, monkeypatch, op_req):
        """無 /proc（取不到 fd 真實路徑）時，resolve→stat 之間的替換 inode 比對看不到 → 一律 fail closed（unknown≠safe）。"""
        ctrl, swap = _race_world(world)
        monkeypatch.setattr(svc, "_fd_realpath", lambda fd: None)
        real_stat, done = svc._stat_dir, []

        def swapping_stat(path):
            if not done:
                done.append(1)
                swap()
            return real_stat(path)

        monkeypatch.setattr(svc, "_stat_dir", swapping_stat)
        r = _run(world, op_req(), environ={ENV: str(ctrl)})
        assert done and (r.ok, r.reason_code, r.filenames, r.vm) == (False, REASON_DIR_INVALID, (), None)
        assert "140.00" not in _all_text(r)

    @pytest.mark.parametrize("op_req", [_list, _query])
    def test_no_proc_means_dir_invalid_even_for_healthy_dir(self, world, monkeypatch, op_req):
        _put(world)
        monkeypatch.setattr(svc, "_fd_realpath", lambda fd: None)
        r = _run(world, op_req())
        assert (r.ok, r.reason_code) == (False, REASON_DIR_INVALID)

    def test_no_proc_closes_the_dir_fd(self, world, monkeypatch):
        _put(world)
        opened, closed = [], []
        real_open, real_close = os.open, os.close
        monkeypatch.setattr(svc, "_fd_realpath", lambda fd: None)
        monkeypatch.setattr(svc.os, "open", lambda *a, **k: (opened.append(real_open(*a, **k)), opened[-1])[1])
        monkeypatch.setattr(svc.os, "close", lambda fd: (closed.append(fd), real_close(fd))[1])
        _run(world, _list())
        assert opened and sorted(opened) == sorted(closed)

    @pytest.mark.parametrize("dev_delta,ino_delta", [(1, 0), (0, 1), (1, 1)])
    def test_inode_check_compares_both_dev_and_ino(self, world, monkeypatch, dev_delta, ino_delta):
        _put(world)
        real_stat = svc._stat_dir

        class _Fake:
            def __init__(self, st):
                self.st_dev, self.st_ino, self.st_mode = st.st_dev + dev_delta, st.st_ino + ino_delta, st.st_mode

        monkeypatch.setattr(svc, "_stat_dir", lambda path: _Fake(real_stat(path)))
        assert _run(world, _list()).reason_code == REASON_DIR_INVALID

    @needs_proc
    def test_proc_check_compares_against_both_repo_and_cwd(self, world, monkeypatch):
        _put(world)
        monkeypatch.setattr(svc, "_fd_realpath", lambda fd: str(world["cwd"] / "elsewhere"))       # cwd 內、repo 外
        assert _run(world, _list()).reason_code == REASON_DIR_INSIDE_REPO
        monkeypatch.setattr(svc, "_fd_realpath", lambda fd: str(world["repo"] / "elsewhere"))      # repo 內、cwd 外
        assert _run(world, _list()).reason_code == REASON_DIR_INSIDE_REPO

    @pytest.mark.skipif(os.scandir not in os.supports_fd, reason="平台無 scandir(fd)")
    def test_swap_after_fd_is_bound_does_not_change_what_is_listed(self, world, monkeypatch):
        ctrl, swap = _race_world(world)
        real_scandir, done = os.scandir, []

        def swapping_scandir(arg):
            if not done:
                done.append(1)
                swap()
            return real_scandir(arg)

        monkeypatch.setattr(svc.os, "scandir", swapping_scandir)
        r = _run(world, _list(), environ={ENV: str(ctrl)})
        assert done and r.ok is True and r.filenames == ("a.csv",)    # 不是 evil.csv

    @pytest.mark.skipif(os.open not in os.supports_dir_fd, reason="平台無 dir_fd")
    def test_swap_after_fd_is_bound_does_not_change_what_is_read(self, world, monkeypatch):
        ctrl, swap = _race_world(world)
        real_open, done = os.open, []

        def swapping_open(path, flags, *a, **k):
            if not flags & getattr(os, "O_DIRECTORY", 0) and not done:      # 檔案 open：目錄 fd 已綁定
                done.append(1)
                swap()
            return real_open(path, flags, *a, **k)

        monkeypatch.setattr(svc.os, "open", swapping_open)
        r = _run(world, _query(), environ={ENV: str(ctrl)})
        assert done and r.ok is True
        assert r.vm.close_text == "130.00" and "140.00" not in _all_text(r)

    def test_dir_fd_closed_on_every_failure(self, world, monkeypatch):
        ctrl, swap = _race_world(world)
        opened, closed = [], []
        real_open, real_close, done = os.open, os.close, []

        def o(path, flags, *a, **k):
            if flags & getattr(os, "O_DIRECTORY", 0) and not done:
                done.append(1)
                swap()
            fd = real_open(path, flags, *a, **k)
            opened.append(fd)
            return fd

        monkeypatch.setattr(svc.os, "open", o)
        monkeypatch.setattr(svc.os, "close", lambda fd: (closed.append(fd), real_close(fd))[1])
        assert _run(world, _list(), environ={ENV: str(ctrl)}).reason_code == REASON_DIR_INVALID
        assert opened and sorted(opened) == sorted(closed)

    def test_dir_open_flags(self):
        for name in ("O_DIRECTORY", "O_NOFOLLOW", "O_CLOEXEC"):
            if hasattr(os, name):
                assert svc._DIR_FLAGS & getattr(os, name), name

    @pytest.mark.parametrize("op_req", [_list, _query])
    def test_fstat_of_dir_oserror_fails_closed(self, world, monkeypatch, op_req):
        _put(world)
        monkeypatch.setattr(svc.os, "fstat", lambda fd: (_ for _ in ()).throw(OSError(errno.EIO, "SECRET")))
        r = _run(world, op_req())
        assert r.reason_code == REASON_DIR_INVALID and "SECRET" not in _all_text(r)

    def test_dir_open_oserror_fails_closed(self, world, monkeypatch):
        _put(world)
        real_open = os.open

        def o(path, flags, *a, **k):
            if flags & getattr(os, "O_DIRECTORY", 0):
                raise OSError(errno.EACCES, "SECRET")
            return real_open(path, flags, *a, **k)

        monkeypatch.setattr(svc.os, "open", o)
        assert _run(world, _list()).reason_code == REASON_DIR_INVALID

    @needs_proc
    def test_proc_realpath_mismatch_fails_closed(self, world, monkeypatch):
        _put(world)
        monkeypatch.setattr(svc, "_fd_realpath", lambda fd: str(world["outside"]))
        assert _run(world, _list()).reason_code == REASON_DIR_INVALID

    @needs_proc
    def test_proc_realpath_inside_repo_is_inside_repo(self, world, monkeypatch):
        _put(world)
        monkeypatch.setattr(svc, "_fd_realpath", lambda fd: str(world["repo"] / "x"))
        assert _run(world, _list()).reason_code == REASON_DIR_INSIDE_REPO

    @needs_proc
    def test_fd_realpath_helper_returns_real_path(self, world):
        fd = os.open(world["data"], os.O_RDONLY)
        try:
            assert svc._fd_realpath(fd) == str(world["data"].resolve())
        finally:
            os.close(fd)

    def test_fd_realpath_unavailable_is_none(self, monkeypatch):
        monkeypatch.setattr(svc.os, "readlink", lambda p: (_ for _ in ()).throw(OSError(errno.ENOENT, "x")))
        assert svc._fd_realpath(3) is None


class TestFspathNormalisation:
    class _Weird:
        def __init__(self, fn):
            self._fn = fn

        def __fspath__(self):
            return self._fn()

    def _boomed(self, world, monkeypatch, op_req, **kw):
        _put(world)
        with monkeypatch.context() as m:
            _boom_fs(m)
            return svc.run_local_lookup(op_req(), **{"environ": {ENV: str(world["data"])}, "now": NOW, **kw})

    @pytest.mark.parametrize("op_req", [_list, _query])
    @pytest.mark.parametrize("field", ["cwd", "repo_root"])
    def test_fspath_returning_bytes_is_bad_request(self, world, monkeypatch, op_req, field):
        r = self._boomed(world, monkeypatch, op_req, **{field: self._Weird(lambda: b"/tmp")})
        assert (r.ok, r.reason_code) == (False, REASON_BAD_REQUEST)

    @pytest.mark.parametrize("op_req", [_list, _query])
    @pytest.mark.parametrize("field", ["cwd", "repo_root"])
    @pytest.mark.parametrize("exc", [OSError("SECRETX"), ValueError("SECRETX"), RuntimeError("SECRETX"), ZeroDivisionError()])
    def test_fspath_raising_is_bad_request_without_leak(self, world, monkeypatch, op_req, field, exc):
        def boom():
            raise exc
        r = self._boomed(world, monkeypatch, op_req, **{field: self._Weird(boom)})
        assert (r.ok, r.reason_code) == (False, REASON_BAD_REQUEST) and "SECRETX" not in _all_text(r)

    @pytest.mark.parametrize("field", ["cwd", "repo_root"])
    def test_fspath_is_called_once_and_value_reused(self, world, field):
        """第二次呼叫會回 bytes：若實作重複呼叫 fspath，就會在後面炸掉或改變行為。"""
        _put(world)
        calls = []
        good = str(world["cwd"] if field == "cwd" else world["repo"])

        def fn():
            calls.append(1)
            return good if len(calls) == 1 else b"/changed"
        r = svc.run_local_lookup(_list(), environ={ENV: str(world["data"])}, now=NOW,
                                 **{"repo_root": world["repo"], "cwd": world["cwd"], field: self._Weird(fn)})
        assert r.ok is True and len(calls) == 1

    def test_fspath_rejected_before_platform_gate(self, world):
        r = svc.run_local_lookup(_list(), environ={}, os_name="nt", cwd=self._Weird(lambda: b"x"))
        assert r.reason_code == REASON_BAD_REQUEST


class TestHardLinks:
    def test_hardlink_to_repo_file_rejected(self, world):
        target = world["repo"] / "secret.csv"
        target.write_bytes(_csv())
        os.link(target, world["data"] / "h.csv")
        r = _run(world, _query("h.csv"))
        assert (r.ok, r.reason_code, r.vm) == (False, REASON_FILE_INVALID, None)

    def test_two_names_in_controlled_dir_both_rejected(self, world):
        _put(world, "a.csv")
        os.link(world["data"] / "a.csv", world["data"] / "b.csv")
        assert _run(world, _query("a.csv")).reason_code == REASON_FILE_INVALID
        assert _run(world, _query("b.csv")).reason_code == REASON_FILE_INVALID

    def test_single_link_still_fine(self, world):
        _put(world)
        assert _run(world, _query()).ok is True

    def test_hardlink_rejection_happens_before_size_check(self, world):
        target = world["repo"] / "big.csv"
        target.write_bytes(b"x" * (MAX_FILE_BYTES + 5))
        os.link(target, world["data"] / "h.csv")
        assert _run(world, _query("h.csv")).reason_code == REASON_FILE_INVALID


class TestListFiltersHardLinks:
    def test_hardlinked_files_not_listed_so_listed_implies_queryable(self, world):
        target = world["repo"] / "secret.csv"
        target.write_bytes(_csv())
        os.link(target, world["data"] / "h.csv")
        _put(world, "a.csv")
        os.link(world["data"] / "a.csv", world["data"] / "b.csv")
        _put(world, "solo.csv")
        r = _run(world, _list())
        assert r.filenames == ("solo.csv",)
        for n in r.filenames:
            assert _run(world, _query(n)).ok is True

    def test_every_listed_name_is_queryable_or_parse_failed_never_file_invalid(self, world):
        for n in ("ok.csv", "x .csv", "COM10.csv"):
            _put(world, n)
        for n in _run(world, _list()).filenames:
            assert _run(world, _query(n)).reason_code is None

    def test_entry_stat_failure_skips_only_that_entry(self, world, monkeypatch):
        _put(world, "good.csv")
        _put(world, "bad.csv")
        real_scandir = os.scandir

        class _Entry:
            def __init__(self, e):
                self._e, self.name = e, e.name

            def is_file(self, follow_symlinks=True):
                return self._e.is_file(follow_symlinks=follow_symlinks)

            def stat(self, follow_symlinks=True):
                if self.name == "bad.csv":
                    raise OSError(errno.EIO, "SECRET")
                return self._e.stat(follow_symlinks=follow_symlinks)

        class _Ctx:
            def __enter__(self):
                self._it = real_scandir(world["data"])
                return (_Entry(e) for e in self._it.__enter__())

            def __exit__(self, *a):
                return self._it.__exit__(*a)

        monkeypatch.setattr(svc.os, "scandir", lambda p: _Ctx())
        r = _run(world, _list())
        assert r.filenames == ("good.csv",) and "SECRET" not in _all_text(r)


class TestHostedViaRepoRoot:
    @pytest.mark.parametrize("op_req", [_list, _query])
    def test_repo_root_under_hosted_prefix(self, world, op_req):
        _put(world)
        assert _run(world, op_req(), repo_root="/mount/src/app").reason_code == REASON_HOSTED_RUNTIME

    def test_resolved_repo_root_symlink_counts(self, world, monkeypatch):
        zone = world["tmp"] / "hostedzone"
        (zone / "repo").mkdir(parents=True)
        link = world["tmp"] / "repo_link"
        link.symlink_to(zone / "repo", target_is_directory=True)
        monkeypatch.setattr(svc, "HOSTED_CWD_PREFIXES", (str(zone),))
        assert not str(link).startswith(str(zone))
        assert _run(world, _list(), repo_root=link).reason_code == REASON_HOSTED_RUNTIME

    def test_resolved_cwd_symlink_counts(self, world, monkeypatch):
        zone = world["tmp"] / "hostedzone"
        (zone / "cwd").mkdir(parents=True)
        link = world["tmp"] / "cwd_link"
        link.symlink_to(zone / "cwd", target_is_directory=True)
        monkeypatch.setattr(svc, "HOSTED_CWD_PREFIXES", (str(zone),))
        assert _run(world, _list(), cwd=link).reason_code == REASON_HOSTED_RUNTIME

    def test_proof_failures_still_win_over_hosted(self, world):
        r = _run(world, _list(_proof(bind="0.0.0.0")), repo_root="/mount/src/app")
        assert r.reason_code == REASON_BIND_NOT_LOOPBACK


class TestRequestAndInjectionTypes:
    def test_duck_typed_proof_is_bad_request(self, world):
        from types import SimpleNamespace
        _put(world)
        for op_req in (_list, _query):
            req = op_req()
            object.__setattr__(req, "proof", SimpleNamespace(bind_address="127.0.0.1", headers_present=True,
                                                             request_host="localhost", proxy_header_names=()))
            r = _run(world, req)
            assert (r.ok, r.reason_code) == (False, REASON_BAD_REQUEST)

    def test_object_new_request_without_fields_is_bad_request_not_raise(self, world):
        r = _run(world, object.__new__(LocalLookupRequest))
        assert (r.ok, r.reason_code) == (False, REASON_BAD_REQUEST)
        req = object.__new__(LocalLookupRequest)
        object.__setattr__(req, "op", OP_LIST)                       # 缺 proof
        r = _run(world, req)
        assert (r.op, r.reason_code) == (OP_LIST, REASON_BAD_REQUEST)

    def test_object_new_proof_is_bad_request(self, world):
        req = _list()
        object.__setattr__(req, "proof", object.__new__(LocalProof))
        assert _run(world, req).reason_code == REASON_BAD_REQUEST

    def test_str_subclass_cannot_impersonate_loopback(self, world):
        class SS(str):
            pass
        _put(world)
        r = _run(world, _list(_proof(bind=SS("127.0.0.1"))))
        assert r.reason_code == REASON_BIND_NOT_LOOPBACK
        r = _run(world, _list(_proof(host=SS("localhost"))))
        assert r.reason_code == REASON_HOST_NOT_LOOPBACK
        assert _run(world, _list(_proof(bind=SS("127.0.0.1"), host=SS("::1")))).ok is False

    @pytest.mark.parametrize("op_req", [_list, _query])
    @pytest.mark.parametrize("kw", [
        dict(environ=[("UI2_LOCAL_OHLCV_DIR", "/x")]), dict(environ="UI2_LOCAL_OHLCV_DIR"),
        dict(environ=type("D", (), {"get": lambda self, k, d=None: "/x"})()),
        dict(cwd=123), dict(cwd=b"/tmp"), dict(cwd=object()), dict(cwd=["/tmp"]),
        dict(repo_root=123), dict(repo_root=b"/tmp"), dict(repo_root=object()),
        dict(now="2026-07-01"), dict(now=12345), dict(now=datetime(2026, 7, 1, 2, 0)),
        dict(now=date(2026, 7, 1)),
    ])
    def test_wrong_injection_types_fail_closed_without_raising(self, world, monkeypatch, op_req, kw):
        _put(world)
        with monkeypatch.context() as m:
            _boom_fs(m)
            r = svc.run_local_lookup(op_req(), **{"environ": {ENV: str(world["data"])}, **kw})
        assert (r.ok, r.reason_code) == (False, REASON_BAD_REQUEST)

    def test_pathlike_cwd_and_repo_root_are_accepted(self, world):
        _put(world)
        r = svc.run_local_lookup(_list(), environ={ENV: str(world["data"])}, now=NOW, repo_root=world["repo"],
                                 cwd=str(world["cwd"]))
        assert r.ok is True

    def test_list_and_query_treat_bad_now_identically(self, world):
        _put(world)
        a = _run(world, _list(), now="x")                           # type: ignore[arg-type]
        b = _run(world, _query(), now="x")                          # type: ignore[arg-type]
        assert a.reason_code == b.reason_code == REASON_BAD_REQUEST


# ═══ 7. 靜態守衛（AST／grep）═══════════════════════════════════════════
def _tree() -> ast.Module:
    return ast.parse(SVC_PATH.read_text(encoding="utf-8"))


class TestStaticGuards:
    ALLOWED_STDLIB = {"__future__", "ntpath", "os", "stat", "collections.abc", "datetime", "pathlib"}
    ALLOWED_PROJECT_PREFIXES = ("shared.",)
    ALLOWED_PROJECT_MODULES = {
        "src.compute.strategy.stock_research_facts",
        "src.data.stock.stock_latest_ohlcv",
        "src.data.stock.stock_local_ohlcv",
    }

    def _imports(self):
        out = []
        for node in ast.walk(_tree()):
            if isinstance(node, ast.Import):
                out += [(a.name, None) for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                assert node.level == 0
                out += [(node.module, a.name) for a in node.names]
        return out

    def test_imports_are_whitelisted_and_never_private(self):
        for mod, name in self._imports():
            assert mod is not None
            ok = (mod in self.ALLOWED_STDLIB or mod in self.ALLOWED_PROJECT_MODULES
                  or mod.startswith(self.ALLOWED_PROJECT_PREFIXES))
            assert ok, mod
            assert name is None or not name.startswith("_"), (mod, name)

    @pytest.mark.parametrize("banned", ["streamlit", "requests", "logging", "app", "app_ui2", "src.ui", "src.ui2",
                                        "src.ui_v2", "urllib", "http", "socket", "subprocess", "shutil",
                                        "tempfile", "pickle", "sqlite3"])
    def test_banned_modules_not_imported(self, banned):
        for mod, _ in self._imports():
            assert mod != banned and not mod.startswith(banned + "."), mod

    def test_no_print_open_or_write_apis(self):
        banned_calls = {"print", "open", "exec", "eval", "__import__", "input"}
        banned_attrs = {"write_text", "write_bytes", "unlink", "remove", "rename", "mkdir", "makedirs", "rmdir",
                        "write", "replace", "touch", "symlink", "truncate", "ftruncate", "chmod", "chown",
                        "system", "popen", "urlopen", "environ"}
        for node in ast.walk(_tree()):
            if isinstance(node, ast.Call):
                f = node.func
                if isinstance(f, ast.Name):
                    assert f.id not in banned_calls, f.id
                if isinstance(f, ast.Attribute):
                    assert f.attr not in banned_attrs - {"environ"}, f.attr
        # os.environ 只允許作為預設值讀取（不寫入）：不得出現指派或 putenv
        src = SVC_PATH.read_text(encoding="utf-8")
        for bad in ("putenv", "os.environ[", "os.environ.update", "os.environ.setdefault"):
            assert bad not in src

    def test_os_open_is_read_only(self):
        assert "O_WRONLY" not in SVC_PATH.read_text(encoding="utf-8")
        assert "O_RDWR" not in SVC_PATH.read_text(encoding="utf-8")
        assert "O_CREAT" not in SVC_PATH.read_text(encoding="utf-8")
        assert "O_TRUNC" not in SVC_PATH.read_text(encoding="utf-8")

    def test_module_level_has_no_side_effects_or_mutable_state(self):
        allowed_value_calls = {"frozenset", "timezone", "timedelta", "getattr"}
        for node in _tree().body:
            if isinstance(node, (ast.Import, ast.ImportFrom, ast.FunctionDef)):
                continue
            if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
                continue                                              # docstring
            assert isinstance(node, (ast.Assign, ast.AnnAssign)), ast.dump(node)[:80]
            frozen_args = {id(a) for sub in ast.walk(node) if isinstance(sub, ast.Call)
                           and isinstance(sub.func, ast.Name) and sub.func.id == "frozenset" for a in sub.args}
            for sub in ast.walk(node):
                if id(sub) in frozen_args:
                    continue                                          # frozenset({...})：不可變
                assert not isinstance(sub, (ast.List, ast.Dict, ast.Set, ast.ListComp, ast.DictComp, ast.SetComp)), \
                    ast.dump(node)[:80]
                if isinstance(sub, ast.Call):
                    assert isinstance(sub.func, ast.Name) and sub.func.id in allowed_value_calls, ast.dump(sub)[:80]

    def test_no_global_statement_and_no_cache_decorators(self):
        for node in ast.walk(_tree()):
            assert not isinstance(node, (ast.Global, ast.Nonlocal))
            if isinstance(node, ast.FunctionDef):
                for d in node.decorator_list:
                    assert "cache" not in ast.dump(d).lower()

    def test_public_signature(self):
        import inspect
        sig = inspect.signature(svc.run_local_lookup)
        names = list(sig.parameters)
        assert names == ["request", "environ", "now", "repo_root", "cwd", "os_name"]
        assert all(sig.parameters[n].kind is inspect.Parameter.KEYWORD_ONLY for n in names[1:])

    def test_basis_verified_literal_false_in_source(self):
        src = SVC_PATH.read_text(encoding="utf-8")
        assert "basis_verified=False" in src and "basis_verified=True" not in src
        assert "source_user_declared=True" in src and "source_user_declared=False" not in src
        assert "fetched_at=None" in src
        for bad in ("st_mtime", "getmtime", "date.today(", "datetime.now()", "datetime.utcnow", "time.time"):
            assert bad not in src, bad


class TestNoProductionCaller:
    NAME = "stock_local_lookup_service"

    @staticmethod
    def _py_files():
        for base in ("src", "shared", "scripts"):
            yield from (ROOT / base).rglob("*.py")
        yield from ROOT.glob("app*.py")

    def test_no_production_module_imports_it(self):
        hits = [p.relative_to(ROOT).as_posix() for p in self._py_files()
                if p.resolve() != SVC_PATH and self.NAME in p.read_text(encoding="utf-8", errors="replace")]
        assert hits == []

    def test_workflows_and_export_script_do_not_reference_it(self):
        paths = list((ROOT / ".github" / "workflows").glob("*")) + [ROOT / "scripts" / "export_stock_db.py"]
        assert (ROOT / "scripts" / "export_stock_db.py").exists()
        for p in paths:
            if p.is_file():
                assert self.NAME not in p.read_text(encoding="utf-8", errors="replace"), p.name
                assert "UI2_LOCAL_OHLCV_DIR" not in p.read_text(encoding="utf-8", errors="replace"), p.name

    def test_env_var_name_not_referenced_by_other_production_code(self):
        hits = [p.relative_to(ROOT).as_posix() for p in self._py_files()
                if p.resolve() != SVC_PATH and "UI2_LOCAL_OHLCV_DIR" in p.read_text(encoding="utf-8", errors="replace")]
        assert hits == []


def test_module_import_is_side_effect_free_on_filesystem(monkeypatch):
    """重新載入模組不得做任何檔案系統操作（只有常數）。"""
    import importlib

    def boom(*a, **k):
        raise AssertionError("fs access at import")
    with monkeypatch.context() as m:
        for name in ("scandir", "listdir", "stat", "lstat"):
            m.setattr(os, name, boom)
        # 只重新執行本模組檔的頂層（不重載依賴，避免依賴自己讀檔）
        src = SVC_PATH.read_text(encoding="utf-8")
        code = compile(src, "<svc-copy>", "exec")
        ns = {"__name__": "svc_copy", "__file__": str(SVC_PATH)}
        exec(code, ns)                                              # noqa: S102 — 受測的是頂層無副作用
        assert callable(ns["run_local_lookup"])
    importlib.import_module("src.services.stock_local_lookup_service")
