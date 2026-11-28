"""tests/test_nas_server_auth_fail_closed.py — A-SEC-1110(#1110)NAS 中繼站認證 fail closed + 502 脫敏。

授權範圍(#1199 comment 7032645702 §3):僅 `src/data/proxy/nas_server.py` 兩處 ——
  ① `_auth`:`NAS_API_KEY` 未設 ⇒ fail closed(503 固定文案,不得匿名放行);
     key 已設 ⇒ `hmac.compare_digest` 常數時間比對,錯/缺 key ⇒ 401。
  ② `/proxy` 例外時的 502 回應 ⇒ 固定脫敏文案,不含 URL / 例外原文 / 內網 IP。

本檔為「CI 必跑」那一路:以**記錄型 stub** 的 fastapi / pydantic 載入 nas_server 原始碼
(沿用 tests/test_batch_z40.py 的 stub 載入手法;CI requirements 未裝 fastapi,故不能 importorskip),
直接呼叫 `_auth` / `proxy_relay` / `fetch`,並用 AST 釘住路由仍掛 `Depends(_auth)`。
真實 FastAPI 的 TestClient 整合測試在 tests/test_nas_server_auth_testclient.py(缺 fastapi/httpx 時 skip,
與 tests/test_nas_server_coverage.py 同機制)。

零真實網路:`requests.get` 一律以假上游取代;`_assert_public_url` 只用 IP 字面值(不觸發 DNS)或被置換。
"""
from __future__ import annotations

import ast
import pathlib
import types

import pytest
import requests

_ROOT = pathlib.Path(__file__).resolve().parent.parent
_NAS = _ROOT / "src" / "data" / "proxy" / "nas_server.py"

_FIXED_502 = "中繼失敗"
_FIXED_503 = "Service unavailable: server auth not configured"


class _HTTPException(Exception):
    """記錄型 stub:保留 status_code / detail(test_batch_z40 的 stub 會吞掉它們)。"""

    def __init__(self, status_code=500, detail=None):
        super().__init__(f"{status_code}: {detail}")
        self.status_code = status_code
        self.detail = detail


class _Response:
    def __init__(self, content=b"", status_code=200, media_type=None):
        self.content = content
        self.status_code = status_code
        self.media_type = media_type


def _load(mp, *, env_key=None):
    """以 stub fastapi/pydantic 載入 nas_server 原始碼(獨立模組物件,不動 sys.modules 既有項目)。"""
    import sys

    fa = types.ModuleType("fastapi")

    class _App:
        def __init__(self, *a, **k):
            pass

        def __getattr__(self, _n):
            return lambda *a, **k: (lambda f: f)

    fa.FastAPI = _App
    fa.HTTPException = _HTTPException
    fa.Depends = lambda *a, **k: None
    fa.Header = lambda *a, **k: None
    far = types.ModuleType("fastapi.responses")
    far.Response = _Response
    pd_ = types.ModuleType("pydantic")
    pd_.BaseModel = object
    mp.setitem(sys.modules, "fastapi", fa)
    mp.setitem(sys.modules, "fastapi.responses", far)
    mp.setitem(sys.modules, "pydantic", pd_)
    if env_key is None:
        mp.delenv("NAS_API_KEY", raising=False)
    else:
        mp.setenv("NAS_API_KEY", env_key)
    m = types.ModuleType("_a_sec_1110_nas")
    m.__file__ = str(_NAS)
    exec(compile(_NAS.read_text(encoding="utf-8"), str(_NAS), "exec"), m.__dict__)
    return m


@pytest.fixture
def nas(monkeypatch):
    return _load(monkeypatch)


class _Up:
    """假上游 response(requests.Response 的最小替身)。"""

    def __init__(self, content=b"ok", status_code=200, headers=None, redirect_to=None):
        self.content = content
        self.status_code = status_code
        self.headers = dict(headers or {"Content-Type": "text/plain"})
        if redirect_to:
            self.headers["Location"] = redirect_to
        self.is_redirect = bool(redirect_to)


def _fake_requests(get):
    return types.SimpleNamespace(get=get, compat=requests.compat)


# ══════════════════════════════════════════════════════════════════════════
# ① 認證
# ══════════════════════════════════════════════════════════════════════════
class TestAuthFailClosedWhenKeyMissing:
    @pytest.mark.parametrize("hdr", [None, "", "anything", "x" * 500, "é中"])
    def test_no_server_key_always_503_never_passes(self, nas, monkeypatch, hdr):
        monkeypatch.setattr(nas, "_API_KEY", "")
        with pytest.raises(_HTTPException) as ei:
            nas._auth(hdr)
        assert ei.value.status_code == 503
        assert ei.value.detail == _FIXED_503

    def test_empty_header_does_not_match_empty_server_key(self, nas, monkeypatch):
        """'' == '' 不得被當成「認證通過」(舊 `if _API_KEY and …` 的 fail-open 根源)。"""
        monkeypatch.setattr(nas, "_API_KEY", "")
        with pytest.raises(_HTTPException) as ei:
            nas._auth("")
        assert ei.value.status_code == 503

    def test_env_unset_at_import_time_means_503(self, monkeypatch):
        """端到端:環境變數 NAS_API_KEY 未設、載入模組後(不手動改 _API_KEY)即 fail closed。"""
        mod = _load(monkeypatch, env_key=None)
        assert mod._API_KEY == ""
        with pytest.raises(_HTTPException) as ei:
            mod._auth(None)
        assert ei.value.status_code == 503

    def test_503_detail_has_no_sensitive_content(self, nas, monkeypatch):
        monkeypatch.setattr(nas, "_API_KEY", "")
        with pytest.raises(_HTTPException) as ei:
            nas._auth("whatever-secret")
        assert "whatever-secret" not in str(ei.value.detail)

    def test_startup_warning_printed_when_key_missing(self, monkeypatch, capsys):
        _load(monkeypatch, env_key=None)
        out = capsys.readouterr().out
        assert "NAS_API_KEY" in out and "503" in out

    def test_no_startup_warning_when_key_set(self, monkeypatch, capsys):
        _load(monkeypatch, env_key="s3cret-key")
        assert "NAS 安全警告" not in capsys.readouterr().out


class TestAuthWithKeySet:
    KEY = "s3cret-Key_2026"

    @pytest.fixture(autouse=True)
    def _key(self, nas, monkeypatch):
        monkeypatch.setattr(nas, "_API_KEY", self.KEY)

    def test_correct_key_passes(self, nas):
        assert nas._auth(self.KEY) is None

    @pytest.mark.parametrize("hdr", [None, "", "wrong", "s3cret-Key_2026 ", " s3cret-Key_2026",
                                     "S3CRET-KEY_2026", "s3cret-Key_202", "s3cret-Key_20266",
                                     "x" * 10_000, "é中文", "s3cret-Key_2026\x00"])
    def test_missing_or_wrong_key_is_401(self, nas, hdr):
        with pytest.raises(_HTTPException) as ei:
            nas._auth(hdr)
        assert ei.value.status_code == 401
        assert ei.value.detail == "Invalid API Key"

    def test_different_length_keys_do_not_crash(self, nas):
        for n in (0, 1, len(self.KEY) - 1, len(self.KEY) + 1, 4096):
            with pytest.raises(_HTTPException) as ei:
                nas._auth("a" * n)
            assert ei.value.status_code == 401

    def test_non_ascii_header_is_401_not_typeerror(self, nas):
        """hmac.compare_digest(str, str) 遇非 ASCII 會 TypeError ⇒ 必須以 bytes 比對。"""
        with pytest.raises(_HTTPException) as ei:
            nas._auth("密鑰-é")
        assert ei.value.status_code == 401

    @pytest.mark.parametrize("special", ["p@ss:w0rd/+=%#?&", "密鑰é2026", "a b\tc", "quote'\"back\\slash", "0"])
    def test_special_character_keys_roundtrip(self, nas, monkeypatch, special):
        monkeypatch.setattr(nas, "_API_KEY", special)
        assert nas._auth(special) is None
        with pytest.raises(_HTTPException) as ei:
            nas._auth(special + "x")
        assert ei.value.status_code == 401

    def test_uses_constant_time_compare(self, nas, monkeypatch):
        """釘住以 hmac.compare_digest(bytes, bytes) 比對(非 `!=`)。"""
        calls = []

        def spy(a, b):
            calls.append((a, b))
            return a == b

        monkeypatch.setattr(nas, "hmac", types.SimpleNamespace(compare_digest=spy))
        nas._auth(self.KEY)
        with pytest.raises(_HTTPException):
            nas._auth("nope")
        assert len(calls) == 2
        assert all(isinstance(a, bytes) and isinstance(b, bytes) for a, b in calls)
        assert calls[0] == (self.KEY.encode(), self.KEY.encode())

    def test_missing_header_short_circuits_before_compare(self, nas, monkeypatch):
        """None header 不得送進 compare_digest(None 會 TypeError)。"""
        def boom(a, b):  # pragma: no cover - 被呼叫即失敗
            raise AssertionError("compare_digest 不應被呼叫")

        monkeypatch.setattr(nas, "hmac", types.SimpleNamespace(compare_digest=boom))
        with pytest.raises(_HTTPException) as ei:
            nas._auth(None)
        assert ei.value.status_code == 401


# ══════════════════════════════════════════════════════════════════════════
# 路由仍掛 Depends(_auth)(AST;stub 載入看不出真實 Depends)
# ══════════════════════════════════════════════════════════════════════════
class TestRoutesStillGuarded:
    @staticmethod
    def _depends_names(func_name):
        tree = ast.parse(_NAS.read_text(encoding="utf-8"))
        fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == func_name)
        out = []
        for d in fn.args.defaults + [k for k in fn.args.kw_defaults if k is not None]:
            if (isinstance(d, ast.Call) and getattr(d.func, "id", "") == "Depends"
                    and d.args and isinstance(d.args[0], ast.Name)):
                out.append(d.args[0].id)
        return out

    @pytest.mark.parametrize("fn", ["proxy_relay", "fetch"])
    def test_guarded_endpoints_depend_on_auth(self, fn):
        assert "_auth" in self._depends_names(fn)

    def test_health_stays_unauthenticated(self):
        assert self._depends_names("health") == []


# ══════════════════════════════════════════════════════════════════════════
# ② /proxy 502 脫敏 + 正當呼叫不回歸
# ══════════════════════════════════════════════════════════════════════════
_SECRET_URL = "https://internal-host.example.invalid:8443/secret/path/etc/passwd?token=SUPERSECRET-123&k=v"
_EXC_TEXT = ("HTTPConnectionPool(host='10.1.2.3', port=8080): Max retries exceeded with url: "
             "/secret/path?token=SUPERSECRET-123 (Caused by /home/nas/.ssh/id_rsa)")


def _assert_sanitised(exc: _HTTPException, *extra_leaks):
    assert exc.status_code == 502
    assert exc.detail == _FIXED_502
    text = f"{exc.detail}|{exc}"
    for leak in ("SUPERSECRET", "internal-host", "10.1.2.3", "/secret/path", "/home/nas", "id_rsa",
                 "8443", "HTTPConnectionPool", "Max retries", "Traceback", ".py", *extra_leaks):
        assert leak not in text, f"502 回應外洩 {leak!r}: {text}"


class TestProxy502Sanitised:
    def test_upstream_exception_text_not_leaked(self, nas, monkeypatch):
        monkeypatch.setattr(nas, "_assert_public_url", lambda u: None)

        def boom(*a, **k):
            raise requests.ConnectionError(_EXC_TEXT)

        monkeypatch.setattr(nas, "requests", _fake_requests(boom))
        with pytest.raises(_HTTPException) as ei:
            nas.proxy_relay(_SECRET_URL)
        _assert_sanitised(ei.value)

    @pytest.mark.parametrize("exc", [requests.Timeout(_EXC_TEXT), ValueError(_EXC_TEXT), RuntimeError(_SECRET_URL),
                                     OSError(_EXC_TEXT), KeyError(_SECRET_URL)])
    def test_any_exception_type_is_sanitised(self, nas, monkeypatch, exc):
        monkeypatch.setattr(nas, "_assert_public_url", lambda u: None)

        def boom(*a, **k):
            raise exc

        monkeypatch.setattr(nas, "requests", _fake_requests(boom))
        with pytest.raises(_HTTPException) as ei:
            nas.proxy_relay(_SECRET_URL)
        _assert_sanitised(ei.value)

    @pytest.mark.parametrize("bad_url, leak", [
        ("http://127.0.0.1:9999/admin?token=SUPERSECRET-123", "127.0.0.1"),
        ("http://169.254.169.254/latest/meta-data", "169.254"),
        ("http://10.0.0.5/x", "10.0.0.5"),
        ("ftp://internal-host.example.invalid/secret/path", "ftp"),
        ("file:///etc/passwd", "file"),
    ])
    def test_ssrf_block_reason_not_leaked(self, nas, monkeypatch, bad_url, leak):
        """_assert_public_url 的 400/403(含內網 IP / scheme 原文)被外層 except 轉成 502 ⇒ 也須脫敏。"""
        def no_net(*a, **k):  # pragma: no cover - 被呼叫即代表 SSRF 防護失效
            raise AssertionError("SSRF 目標不應被抓取")

        monkeypatch.setattr(nas, "requests", _fake_requests(no_net))
        with pytest.raises(_HTTPException) as ei:
            nas.proxy_relay(bad_url)
        _assert_sanitised(ei.value, leak)

    def test_redirect_to_internal_is_blocked_and_sanitised(self, nas, monkeypatch):
        calls = []

        def get(url, **k):
            calls.append(url)
            return _Up(status_code=302, redirect_to="http://169.254.169.254/latest/meta-data")

        monkeypatch.setattr(nas, "requests", _fake_requests(get))
        with pytest.raises(_HTTPException) as ei:
            nas.proxy_relay("http://93.184.216.34/start")     # IP 字面值 ⇒ 不觸發 DNS
        _assert_sanitised(ei.value, "169.254")
        assert calls == ["http://93.184.216.34/start"]        # 內網那一跳沒有被抓

    def test_server_log_still_records_detail(self, nas, monkeypatch, capsys):
        """脫敏只針對對外回應;server 本機 log 仍保留診斷資訊(行為未改)。"""
        monkeypatch.setattr(nas, "_assert_public_url", lambda u: None)

        def boom(*a, **k):
            raise requests.ConnectionError("diag-detail-xyz")

        monkeypatch.setattr(nas, "requests", _fake_requests(boom))
        with pytest.raises(_HTTPException):
            nas.proxy_relay("https://example.com/a")
        assert "diag-detail-xyz" in capsys.readouterr().out


class TestLegitimateCallsNotRegressed:
    def test_proxy_passthrough_status_body_content_type(self, nas, monkeypatch):
        monkeypatch.setattr(nas, "_assert_public_url", lambda u: None)
        seen = {}

        def get(url, **k):
            seen["url"], seen["kw"] = url, k
            return _Up(content=b'{"a":1}', status_code=200, headers={"Content-Type": "application/json"})

        monkeypatch.setattr(nas, "requests", _fake_requests(get))
        r = nas.proxy_relay("https://www.twse.com.tw/x?y=1")
        assert (r.content, r.status_code, r.media_type) == (b'{"a":1}', 200, "application/json")
        assert seen["url"] == "https://www.twse.com.tw/x?y=1"
        assert seen["kw"]["allow_redirects"] is False and seen["kw"]["timeout"] == 20

    def test_upstream_error_status_is_passed_through_not_502(self, nas, monkeypatch):
        monkeypatch.setattr(nas, "_assert_public_url", lambda u: None)
        monkeypatch.setattr(nas, "requests", _fake_requests(lambda url, **k: _Up(content=b"nf", status_code=404)))
        r = nas.proxy_relay("https://example.com/missing")
        assert r.status_code == 404 and r.content == b"nf"

    def test_public_redirect_chain_followed(self, nas, monkeypatch):
        monkeypatch.setattr(nas, "_assert_public_url", lambda u: None)
        hops = iter([_Up(status_code=301, redirect_to="/final"), _Up(content=b"done")])
        monkeypatch.setattr(nas, "requests", _fake_requests(lambda url, **k: next(hops)))
        r = nas.proxy_relay("https://example.com/start")
        assert r.status_code == 200 and r.content == b"done"

    def test_api_fetch_dispatch_unchanged(self, nas, monkeypatch):
        monkeypatch.setattr(nas, "_fetch_export_yoy", lambda: {"value": 1.5, "date": "2026-09"})
        out = nas.fetch(types.SimpleNamespace(action="export_yoy", date=None))
        assert out == {"status": "ok", "data": {"value": 1.5, "date": "2026-09"}, "action": "export_yoy"}

    def test_api_fetch_failed_and_unknown_action_unchanged(self, nas, monkeypatch):
        monkeypatch.setattr(nas, "_fetch_export_yoy", lambda: None)
        assert nas.fetch(types.SimpleNamespace(action="export_yoy", date=None))["status"] == "failed"
        with pytest.raises(_HTTPException) as ei:
            nas.fetch(types.SimpleNamespace(action="nope", date=None))
        assert ei.value.status_code == 400
