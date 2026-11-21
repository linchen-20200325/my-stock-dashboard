"""tests/test_nas_server_auth_testclient.py — A-SEC-1110(#1110)真實 FastAPI TestClient 整合測試。

與 tests/test_nas_server_coverage.py 同機制:fastapi / httpx 只裝在 NAS host,CI requirements 未含,
缺套件時整檔 graceful SKIP(不新增任何依賴、不改 requirements.txt)。
CI 必跑的等價守衛(stub 載入 + AST)在 tests/test_nas_server_auth_fail_closed.py。

驗證項目(真實 Depends / 驗證順序 / 序列化後的 body):
- NAS_API_KEY 未設 ⇒ `/proxy`(GET/POST)與 `/api/fetch` 一律 503 固定訊息(含:帶 key header、缺 url 參數、壞 body)。
- key 已設 ⇒ 缺 / 錯 header 401;正確 key 放行。
- `/proxy` 例外 ⇒ 502 body 恰為固定脫敏 JSON,不含 URL / 例外原文 / 內網 IP。
- `/`(health)維持無認證(行為未改)。
零真實網路:上游一律 monkeypatch;SSRF 案例只用 IP 字面值(不觸發 DNS)。
"""
from __future__ import annotations

import types

import pytest
import requests

pytest.importorskip("fastapi", reason="fastapi 僅裝於 NAS host,非 dashboard/CI 依賴")
pytest.importorskip("pydantic", reason="pydantic 僅裝於 NAS host")
pytest.importorskip("httpx", reason="TestClient 需要 httpx,僅裝於 NAS host / 本機驗證環境")

import src.data.proxy as _proxy_pkg  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from src.data.proxy import nas_server  # noqa: E402

# 同 tests/test_nas_server_coverage.py:拆掉 import 副作用長出的 package 屬性,避免遮蔽 PEP 562 lazy forward。
vars(_proxy_pkg).pop("nas_server", None)

KEY = "s3cret-Key_2026"
FIXED_502 = {"detail": "中繼失敗"}
FIXED_503 = {"detail": "Service unavailable: server auth not configured"}

_SECRET_URL = "https://internal-host.example.invalid:8443/secret/path?token=SUPERSECRET-123"
_EXC_TEXT = "HTTPConnectionPool(host='10.1.2.3', port=8080): refused /secret/path?token=SUPERSECRET-123"


class _Up:
    def __init__(self, content=b"upstream-ok", status_code=200, ctype="text/plain"):
        self.content = content
        self.status_code = status_code
        self.headers = {"Content-Type": ctype}
        self.is_redirect = False


def _patch_upstream(mp, get):
    mp.setattr(nas_server, "requests", types.SimpleNamespace(get=get, compat=requests.compat))
    mp.setattr(nas_server, "_assert_public_url", lambda u: None)


@pytest.fixture
def client():
    return TestClient(nas_server.app, raise_server_exceptions=False)


@pytest.fixture
def key_unset(monkeypatch):
    monkeypatch.setattr(nas_server, "_API_KEY", "")


@pytest.fixture
def key_set(monkeypatch):
    monkeypatch.setattr(nas_server, "_API_KEY", KEY)


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    """任何漏網的真實 requests.get 都直接失敗(不得打外網)。"""
    def _blocked(*a, **k):  # pragma: no cover
        raise AssertionError("測試不得發真實網路請求")

    monkeypatch.setattr(requests, "get", _blocked)


class TestKeyMissingFailsClosed:
    @pytest.mark.parametrize("hdrs", [None, {}, {"X-API-Key": ""}, {"X-API-Key": "anything"}, {"X-API-Key": KEY}])
    def test_proxy_get_503(self, client, key_unset, hdrs):
        r = client.get("/proxy", params={"url": "https://example.com/"}, headers=hdrs)
        assert r.status_code == 503 and r.json() == FIXED_503

    def test_proxy_post_503(self, client, key_unset):
        r = client.post("/proxy", params={"url": "https://example.com/"})
        assert r.status_code == 503 and r.json() == FIXED_503

    def test_proxy_without_url_param_is_503_not_422(self, client, key_unset):
        """認證在參數驗證之前:缺 url 也先 503(connection_diag 的無 url 探測依賴此順序)。"""
        r = client.get("/proxy")
        assert r.status_code == 503 and r.json() == FIXED_503

    @pytest.mark.parametrize("hdrs", [None, {"X-API-Key": ""}, {"X-API-Key": KEY}])
    def test_api_fetch_503(self, client, key_unset, hdrs):
        r = client.post("/api/fetch", json={"action": "export_yoy"}, headers=hdrs)
        assert r.status_code == 503 and r.json() == FIXED_503

    def test_no_upstream_call_when_key_missing(self, client, key_unset, monkeypatch):
        called = []
        _patch_upstream(monkeypatch, lambda *a, **k: called.append(1) or _Up())
        monkeypatch.setattr(nas_server, "_fetch_export_yoy", lambda: called.append(2) or {"value": 1})
        client.get("/proxy", params={"url": "https://example.com/"})
        client.post("/api/fetch", json={"action": "export_yoy"})
        assert called == []

    def test_health_still_open(self, client, key_unset):
        r = client.get("/")
        assert r.status_code == 200 and r.json()["status"] == "ok"


class TestKeySet:
    def test_missing_header_401(self, client, key_set):
        assert client.get("/proxy", params={"url": "https://example.com/"}).status_code == 401
        assert client.post("/api/fetch", json={"action": "export_yoy"}).status_code == 401

    @pytest.mark.parametrize("bad", ["", "wrong", KEY + "x", KEY[:-1], KEY.upper(), "x" * 5000])
    def test_wrong_header_401(self, client, key_set, bad):
        r = client.get("/proxy", params={"url": "https://example.com/"}, headers={"X-API-Key": bad})
        assert r.status_code == 401 and r.json() == {"detail": "Invalid API Key"}
        r = client.post("/api/fetch", json={"action": "export_yoy"}, headers={"X-API-Key": bad})
        assert r.status_code == 401

    def test_non_ascii_header_401_not_500(self, client, key_set):
        r = client.get("/proxy", params={"url": "https://example.com/"},
                       headers={"X-API-Key": "密鑰".encode("utf-8")})
        assert r.status_code == 401

    def test_no_url_param_without_key_is_401(self, client, key_set):
        """connection_diag 探測(無 url、無 key)在已設 key 的伺服器上仍得 401。"""
        assert client.get("/proxy").status_code == 401

    def test_correct_key_proxy_passes_through(self, client, key_set, monkeypatch):
        seen = []
        _patch_upstream(monkeypatch, lambda url, **k: seen.append(url) or _Up(b'{"a": 1}', 200, "application/json"))
        r = client.get("/proxy", params={"url": "https://www.twse.com.tw/x"}, headers={"X-API-Key": KEY})
        assert r.status_code == 200 and r.json() == {"a": 1}
        assert r.headers["content-type"].startswith("application/json")
        assert seen == ["https://www.twse.com.tw/x"]

    def test_correct_key_post_proxy_and_upstream_status_passthrough(self, client, key_set, monkeypatch):
        _patch_upstream(monkeypatch, lambda url, **k: _Up(b"nf", 404))
        r = client.post("/proxy", params={"url": "https://example.com/x"}, headers={"X-API-Key": KEY})
        assert r.status_code == 404 and r.content == b"nf"

    def test_correct_key_api_fetch_passes(self, client, key_set, monkeypatch):
        monkeypatch.setattr(nas_server, "_fetch_export_yoy", lambda: {"value": 2.0, "date": "2026-09"})
        r = client.post("/api/fetch", json={"action": "export_yoy"}, headers={"X-API-Key": KEY})
        assert r.status_code == 200
        assert r.json() == {"status": "ok", "data": {"value": 2.0, "date": "2026-09"}, "action": "export_yoy"}

    def test_special_char_key(self, client, monkeypatch):
        monkeypatch.setattr(nas_server, "_API_KEY", "p@ss:w0rd/+=%#?&")
        monkeypatch.setattr(nas_server, "_fetch_export_yoy", lambda: {"value": 1})
        ok = client.post("/api/fetch", json={"action": "export_yoy"}, headers={"X-API-Key": "p@ss:w0rd/+=%#?&"})
        bad = client.post("/api/fetch", json={"action": "export_yoy"}, headers={"X-API-Key": "p@ss:w0rd/+=%#?"})
        assert ok.status_code == 200 and bad.status_code == 401

    def test_health_still_open_with_key_set(self, client, key_set):
        assert client.get("/").status_code == 200


class TestProxy502Body:
    def _boom(self, mp, exc):
        def get(*a, **k):
            raise exc

        _patch_upstream(mp, get)

    @pytest.mark.parametrize("exc", [requests.ConnectionError(_EXC_TEXT), requests.Timeout(_EXC_TEXT),
                                     ValueError(_SECRET_URL), RuntimeError(_EXC_TEXT)])
    def test_exception_body_is_fixed_and_clean(self, client, key_set, monkeypatch, exc):
        self._boom(monkeypatch, exc)
        r = client.get("/proxy", params={"url": _SECRET_URL}, headers={"X-API-Key": KEY})
        assert r.status_code == 502
        assert r.json() == FIXED_502
        for leak in ("SUPERSECRET", "internal-host", "10.1.2.3", "/secret/path", "HTTPConnectionPool", "8443"):
            assert leak not in r.text

    @pytest.mark.parametrize("bad_url, leak", [
        ("http://127.0.0.1:9999/admin", "127.0.0.1"),
        ("http://169.254.169.254/latest/meta-data", "169.254"),
        ("http://10.0.0.5/x", "10.0.0.5"),
        ("ftp://example.com/x", "ftp"),
    ])
    def test_ssrf_block_is_502_fixed_without_reason(self, client, key_set, monkeypatch, bad_url, leak):
        monkeypatch.setattr(nas_server, "requests", types.SimpleNamespace(
            get=lambda *a, **k: pytest.fail("SSRF 目標不應被抓取"), compat=requests.compat))
        r = client.get("/proxy", params={"url": bad_url}, headers={"X-API-Key": KEY})
        assert r.status_code == 502 and r.json() == FIXED_502
        assert leak not in r.text and "SSRF" not in r.text

    def test_post_proxy_502_also_fixed(self, client, key_set, monkeypatch):
        self._boom(monkeypatch, requests.ConnectionError(_EXC_TEXT))
        r = client.post("/proxy", params={"url": _SECRET_URL}, headers={"X-API-Key": KEY})
        assert r.status_code == 502 and r.json() == FIXED_502


class TestApiFetchOtherResponsePaths:
    """/api/fetch 其他回應路徑盤點(釘住現況:未外洩例外原文)。"""

    def test_uncaught_handler_exception_is_generic_500(self, client, key_set):
        # date 格式錯 ⇒ _fetch_institutional 內 strptime 在 try 之外 raise ValueError ⇒ 框架泛用 500。
        r = client.post("/api/fetch", json={"action": "institutional", "date": "not-a-date"},
                        headers={"X-API-Key": KEY})
        assert r.status_code == 500
        assert "not-a-date" not in r.text and "strptime" not in r.text and "ValueError" not in r.text

    def test_unknown_action_400(self, client, key_set):
        r = client.post("/api/fetch", json={"action": "nope"}, headers={"X-API-Key": KEY})
        assert r.status_code == 400
