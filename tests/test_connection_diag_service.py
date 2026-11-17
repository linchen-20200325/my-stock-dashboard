"""連線診斷服務（#1110 D-T2）：全部 mock requests＋socket guard，不連外。"""
from __future__ import annotations

import ast
import dataclasses
import inspect
import json
import pathlib
import socket
import threading

import pytest
import requests

from shared.ui2_contract import diag as D
from src.services import connection_diag_service as S

ROOT = pathlib.Path(__file__).resolve().parents[1]
SERVICE_SRC = (ROOT / "src" / "services" / "connection_diag_service.py").read_text(encoding="utf-8")
SECRET_KEY = "SECRET-KEY-VALUE-123"
SECRET_TOKEN = "FINMIND-TOKEN-XYZ"
NAS_HOST = "nas-secret-host.example.invalid"


class _Resp:
    def __init__(self, code):
        self.status_code = code

    def close(self):
        pass


@pytest.fixture(autouse=True)
def _guard(monkeypatch):
    """socket guard＋重置模組層 cooldown 狀態；預設所有設定 getter 回「未設定」。"""
    def deny(*a, **k):
        raise AssertionError("connection diag 測試不得連外")
    monkeypatch.setattr(socket.socket, "connect", deny)
    monkeypatch.setattr(socket, "create_connection", deny)
    S._STATE["last_report"] = None
    S._STATE["last_finished"] = None
    calls = []
    monkeypatch.setattr(S.requests, "get", lambda *a, **k: (_ for _ in ()).throw(AssertionError("unexpected get")))
    import src.data.proxy.proxy_helper as PH
    import src.config as C
    monkeypatch.setattr(PH, "get_nas_relay", lambda: None)
    monkeypatch.setattr(PH, "get_proxy_config", lambda: None)
    monkeypatch.setattr(C, "get_finmind_token", lambda: "")
    yield calls
    S._STATE["last_report"] = None
    S._STATE["last_finished"] = None


def _setup(monkeypatch, *, nas=None, proxy=None, token="", responder=None):
    import src.data.proxy.proxy_helper as PH
    import src.config as C
    monkeypatch.setattr(PH, "get_nas_relay", lambda: nas)
    monkeypatch.setattr(PH, "get_proxy_config", lambda: proxy)
    monkeypatch.setattr(C, "get_finmind_token", lambda: token)
    log = []

    def fake_get(url, **kw):
        log.append((url, kw))
        r = responder(url, kw) if responder else 200
        if isinstance(r, BaseException):
            raise r
        return _Resp(r)
    monkeypatch.setattr(S.requests, "get", fake_get)
    return log


def _blob(report) -> str:
    return json.dumps(dataclasses.asdict(report), default=lambda o: o.value, ensure_ascii=False)


# ── 不按不連網／全未設定 ──────────────────────────────────────────────
def test_import_and_render_does_not_call_network(monkeypatch):
    log = _setup(monkeypatch)
    import importlib
    importlib.reload(S)       # 重新 import 不得有副作用外連（requests.get 被換成 raising 的 fake 前已 patch）
    assert log == []


def test_nothing_configured_runs_only_direct_probes_for_yahoo_twse(monkeypatch):
    log = _setup(monkeypatch)
    rep = S.run_connection_check()
    assert rep.nas_relay.status is D.DiagStatus.NOT_CONFIGURED
    assert rep.nas_proxy.status is D.DiagStatus.NOT_CONFIGURED
    assert rep.finmind.status is D.DiagStatus.NOT_CONFIGURED
    assert rep.yahoo.status is D.DiagStatus.SUCCESS and rep.twse.status is D.DiagStatus.NOT_CHECKED
    assert [u for u, _ in log] == [S.YAHOO_PROBE_URL]
    assert all(kw["proxies"] == {"http": None, "https": None} for _, kw in log)


# ── NAS 中繼站 ───────────────────────────────────────────────────────
def _nas_responder(root=200, nokey=401, withkey=422):
    def r(url, kw):
        if url.endswith("/proxy"):
            return withkey if "X-API-Key" in (kw.get("headers") or {}) else nokey
        return root
    return r


def test_nas_enforced_auth_with_key_is_success_and_key_only_over_https(monkeypatch):
    log = _setup(monkeypatch, nas=(f"https://{NAS_HOST}", SECRET_KEY), responder=_nas_responder())
    res = S._probe_nas_relay()
    assert res == D.ProbeResult(D.DiagStatus.SUCCESS)
    urls = [u for u, _ in log]
    assert urls == [f"https://{NAS_HOST}/", f"https://{NAS_HOST}/proxy", f"https://{NAS_HOST}/proxy"]
    assert all("url=" not in u and "?" not in u for u in urls)           # 不帶 url 參數
    sent = [kw.get("headers") for _, kw in log]
    assert sent[0] is None and sent[1] is None and sent[2] == {"X-API-Key": SECRET_KEY}


def test_nas_http_base_is_auth_unverified_and_sends_nothing(monkeypatch):
    log = _setup(monkeypatch, nas=(f"http://{NAS_HOST}", SECRET_KEY), responder=_nas_responder())
    assert S._probe_nas_relay() == D.ProbeResult(D.DiagStatus.AUTH_UNVERIFIED, D.DiagReason.PLAIN_HTTP)
    assert log == []                                                      # 不送 key、不發請求


def test_nas_key_missing_is_auth_unverified(monkeypatch):
    log = _setup(monkeypatch, nas=(f"https://{NAS_HOST}", ""), responder=_nas_responder())
    assert S._probe_nas_relay() == D.ProbeResult(D.DiagStatus.AUTH_UNVERIFIED, D.DiagReason.KEY_MISSING)
    assert not any("X-API-Key" in (kw.get("headers") or {}) for _, kw in log)


@pytest.mark.parametrize("nokey", [200, 404, 422])
def test_nas_server_not_enforcing_auth_is_auth_unverified_and_key_never_sent(monkeypatch, nokey):
    log = _setup(monkeypatch, nas=(f"https://{NAS_HOST}", SECRET_KEY), responder=_nas_responder(nokey=nokey))
    assert S._probe_nas_relay() == D.ProbeResult(D.DiagStatus.AUTH_UNVERIFIED, D.DiagReason.AUTH_NOT_ENFORCED)
    assert not any("X-API-Key" in (kw.get("headers") or {}) for _, kw in log)


@pytest.mark.parametrize("withkey", [401, 403])
def test_nas_key_rejected_is_failed_auth(monkeypatch, withkey):
    _setup(monkeypatch, nas=(f"https://{NAS_HOST}", SECRET_KEY), responder=_nas_responder(withkey=withkey))
    assert S._probe_nas_relay() == D.ProbeResult(D.DiagStatus.FAILED, D.DiagReason.AUTH)


def test_nas_root_5xx_is_failed_server(monkeypatch):
    _setup(monkeypatch, nas=(f"https://{NAS_HOST}", SECRET_KEY), responder=_nas_responder(root=503))
    assert S._probe_nas_relay() == D.ProbeResult(D.DiagStatus.FAILED, D.DiagReason.SERVER)


# ── 例外／狀態碼 → 固定類別 ───────────────────────────────────────────
@pytest.mark.parametrize("exc,reason", [
    (requests.exceptions.ConnectTimeout("x"), D.DiagReason.TIMEOUT),
    (requests.exceptions.ReadTimeout("x"), D.DiagReason.TIMEOUT),
    (requests.exceptions.ProxyError("x"), D.DiagReason.PROXY),
    (requests.exceptions.SSLError("x"), D.DiagReason.TLS),
    (requests.exceptions.ConnectionError("x"), D.DiagReason.CONNECTION),
    (ValueError("x"), D.DiagReason.OTHER),
])
def test_exception_types_map_to_fixed_reasons(monkeypatch, exc, reason):
    _setup(monkeypatch, responder=lambda u, kw: exc)
    assert S._http_probe(S.YAHOO_PROBE_URL) == D.ProbeResult(D.DiagStatus.FAILED, reason)


@pytest.mark.parametrize("code,expect", [
    (200, D.ProbeResult(D.DiagStatus.SUCCESS)), (301, D.ProbeResult(D.DiagStatus.SUCCESS)),
    (401, D.ProbeResult(D.DiagStatus.FAILED, D.DiagReason.AUTH)),
    (403, D.ProbeResult(D.DiagStatus.FAILED, D.DiagReason.AUTH)),
    (404, D.ProbeResult(D.DiagStatus.FAILED, D.DiagReason.OTHER)),
    (503, D.ProbeResult(D.DiagStatus.FAILED, D.DiagReason.SERVER)),
])
def test_status_codes_map_to_fixed_reasons(monkeypatch, code, expect):
    _setup(monkeypatch, responder=lambda u, kw: code)
    assert S._http_probe(S.YAHOO_PROBE_URL) == expect


def test_squid_finmind_twse_send_no_request_and_are_not_checked(monkeypatch):
    """GPT 定稿：無核准低副作用健康端點者不得探測、不得自行更換 → 固定『尚未檢查』（無設定者仍『未設定』）。"""
    cfg = {"http": "http://user:pass@squid-host:3128", "https": "http://user:pass@squid-host:3128"}
    log = _setup(monkeypatch, proxy=cfg, token=SECRET_TOKEN, responder=lambda u, kw: 200)
    assert S._probe_nas_proxy() == D.ProbeResult(D.DiagStatus.NOT_CHECKED)
    assert S._probe_finmind() == D.ProbeResult(D.DiagStatus.NOT_CHECKED)
    rep = S.run_connection_check()
    assert rep.twse == D.ProbeResult(D.DiagStatus.NOT_CHECKED) and rep.finmind.status is D.DiagStatus.NOT_CHECKED
    assert rep.nas_proxy.status is D.DiagStatus.NOT_CHECKED
    assert [u for u, _ in log] == [S.YAHOO_PROBE_URL]            # 唯一請求＝Yahoo；token／proxy 認證不外送
    assert not any("Authorization" in (kw.get("headers") or {}) for _, kw in log)
    log2 = _setup(monkeypatch, proxy=None, token="", responder=lambda u, kw: 200)
    assert S._probe_nas_proxy().status is D.DiagStatus.NOT_CONFIGURED
    assert S._probe_finmind().status is D.DiagStatus.NOT_CONFIGURED and log2 == []


def test_removed_data_endpoints_are_gone_from_service_source():
    assert not hasattr(S, "TWSE_PROBE_URL") and not hasattr(S, "FINMIND_PROBE_URL")
    for bad in ("twse.com.tw", "finmindtrade", "STOCK_DAY_AVG_ALL", "TaiwanStockInfo"):
        assert bad not in SERVICE_SRC, bad


def test_every_request_is_https_verified_bounded_no_redirect(monkeypatch):
    log = _setup(monkeypatch, nas=(f"https://{NAS_HOST}", SECRET_KEY), proxy={"https": "http://p:1"},
                 token=SECRET_TOKEN, responder=_nas_responder())
    S.run_connection_check()
    assert 0 < len(log) <= S.MAX_REQUESTS <= 7 and len(log) == 4      # NAS 3 ＋ Yahoo 1
    for url, kw in log:
        assert url.startswith("https://")
        assert kw["verify"] is True and kw["allow_redirects"] is False and kw["stream"] is True
        assert kw["timeout"] == (S.CONNECT_TIMEOUT_S, S.READ_TIMEOUT_S) == (3, 5)


def test_gemini_and_fred_are_never_probed(monkeypatch):
    log = _setup(monkeypatch, nas=(f"https://{NAS_HOST}", SECRET_KEY), proxy={"https": "http://p:1"},
                 token=SECRET_TOKEN, responder=_nas_responder())
    S.run_connection_check()
    urls = " ".join(u for u, _ in log).lower()
    assert "googleapis" not in urls and "stlouisfed" not in urls and "gemini" not in urls and "fred" not in urls
    assert "googleapis" not in SERVICE_SRC and "stlouisfed" not in SERVICE_SRC


# ── 輸出不外洩 ───────────────────────────────────────────────────────
def test_report_serialization_has_no_secrets_hosts_or_raw_exceptions(monkeypatch):
    def responder(url, kw):
        return requests.exceptions.SSLError(f"cert fail {NAS_HOST} {SECRET_KEY} Traceback http://x 10.0.0.5")
    _setup(monkeypatch, nas=(f"https://{NAS_HOST}", SECRET_KEY),
           proxy={"https": "http://user:pw@10.1.2.3:3128"}, token=SECRET_TOKEN, responder=responder)
    rep = S.run_connection_check()
    blob = _blob(rep)
    for bad in (SECRET_KEY, SECRET_TOKEN, NAS_HOST, "10.", "http", "Traceback", "cert fail", "user:pw", "@"):
        assert bad not in blob, bad
    assert D.DiagReason.TLS.value in blob and rep.nas_relay == D.ProbeResult(D.DiagStatus.FAILED, D.DiagReason.TLS)


def test_unexpected_internal_error_is_fixed_other_without_text(monkeypatch):
    _setup(monkeypatch, responder=lambda u, kw: 200)

    def boom():
        raise RuntimeError(f"leak {SECRET_KEY}")
    monkeypatch.setattr(S, "_probe_finmind", boom)
    rep = S.run_connection_check()
    assert rep.finmind == D.ProbeResult(D.DiagStatus.FAILED, D.DiagReason.OTHER) and SECRET_KEY not in _blob(rep)


def test_only_enum_fields_and_no_timestamp_fields():
    for cls in (D.DiagReport, D.ProbeResult):
        for f in dataclasses.fields(cls):
            assert f.type in ("ProbeResult", "DiagNotice", "DiagStatus", "DiagReason"), (cls, f)
            assert not any(w in f.name.lower() for w in ("time", "date", "at", "stamp", "asof", "ts")) or f.name in ("status",), f.name
    assert "datetime" not in inspect.getsource(D) and "time" not in {n.split(".")[0] for n in
        (a.name for x in ast.walk(ast.parse(inspect.getsource(D))) if isinstance(x, ast.Import) for a in x.names)}


# ── AST 結構守衛 ─────────────────────────────────────────────────────
def _tree():
    return ast.parse(SERVICE_SRC)


def _identifiers(tree) -> set[str]:
    out = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Name):
            out.add(n.id)
        elif isinstance(n, ast.Attribute):
            out.add(n.attr)
        elif isinstance(n, (ast.Import, ast.ImportFrom)):
            out |= {a.name.split(".")[-1] for a in n.names} | ({n.module} if getattr(n, "module", None) else set())
    return out


def test_service_ast_never_disables_tls_and_avoids_unsafe_helpers():
    for n in ast.walk(_tree()):
        if isinstance(n, ast.keyword) and n.arg == "verify":
            assert isinstance(n.value, ast.Constant) and n.value.value is True      # 只准字面 True
        if isinstance(n, ast.Attribute) and n.attr == "verify":
            assert not isinstance(n.ctx, ast.Store)                                  # `.verify = ...`
        if isinstance(n, ast.Assign):
            assert not any(isinstance(t, ast.Attribute) and t.attr == "verify" for t in n.targets)
    ids = _identifiers(_tree())
    for banned in ("fetch_url", "nas_relay_fetch", "build_unverified_proxy_session", "urlopen", "Session",
                   "make_retry_session", "disable_warnings"):
        assert banned not in ids, banned


def test_ast_detector_catches_verify_false_and_banned_helpers():
    """負測：偵測規則本身要有牙（同一套規則套在壞原始碼上必須判違規）。"""
    def violations(src):
        t = ast.parse(src)
        v = [n for n in ast.walk(t) if isinstance(n, ast.keyword) and n.arg == "verify"
             and not (isinstance(n.value, ast.Constant) and n.value.value is True)]
        v += [n for n in ast.walk(t) if isinstance(n, ast.Attribute) and n.attr == "verify" and isinstance(n.ctx, ast.Store)]
        v += [n for n in ast.walk(t) if isinstance(n, ast.Name) and n.id in {"fetch_url", "nas_relay_fetch",
              "build_unverified_proxy_session"}]
        return v
    assert violations(SERVICE_SRC) == []
    for bad in ("requests.get(u, verify=False)", "s.verify = False", "fetch_url(u)", "nas_relay_fetch(u)",
                "build_unverified_proxy_session()", "requests.get(u, verify=v)"):
        assert violations(bad), bad


def test_all_requests_calls_have_timeout_verify_and_constant_urls():
    calls = [n for n in ast.walk(_tree()) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
             and isinstance(n.func.value, ast.Name) and n.func.value.id == "requests"
             and n.func.attr in {"get", "post", "request", "head", "put", "delete", "Session"}]
    assert len(calls) == 1
    kws = {k.arg: k.value for k in calls[0].keywords}
    assert {"timeout", "verify", "allow_redirects", "stream"} <= set(kws)
    assert isinstance(kws["verify"], ast.Constant) and kws["verify"].value is True
    assert isinstance(kws["allow_redirects"], ast.Constant) and kws["allow_redirects"].value is False
    # 唯一請求點的呼叫者：URL 只能是模組 UPPER 常數，或 f"{base}{UPPER_CONST_PATH}"
    consts = {t.id for n in _tree().body if isinstance(n, ast.Assign) for t in n.targets if isinstance(t, ast.Name)}
    callers = [n for n in ast.walk(_tree()) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
               and n.func.id in {"_get", "_http_probe"}]
    assert callers
    for c in callers:
        a = c.args[0]
        if isinstance(a, ast.Name):
            assert a.id in consts and a.id.isupper() or a.id == "url", ast.unparse(c)
        else:
            assert isinstance(a, ast.JoinedStr), ast.unparse(c)
            vals = [v.value for v in a.values if isinstance(v, ast.FormattedValue)]
            assert [ast.unparse(v) for v in vals] == ["base", "NAS_ROOT_PATH"] or \
                   [ast.unparse(v) for v in vals] == ["base", "NAS_PROXY_PATH"], ast.unparse(c)


def test_run_connection_check_has_no_parameters():
    assert list(inspect.signature(S.run_connection_check).parameters) == []


# ── 全進程鎖＋冷卻（跨 session）─────────────────────────────────────
def test_cooldown_blocks_second_call_across_sessions_and_returns_previous(monkeypatch):
    log = _setup(monkeypatch, responder=lambda u, kw: 200)
    first = S.run_connection_check()
    n = len(log)
    second = S.run_connection_check()          # 另一個 session（同進程模組層狀態）
    assert len(log) == n, "冷卻內不得再探測"
    assert second.notice is D.DiagNotice.WAIT and dataclasses.replace(second, notice=D.DiagNotice.NONE) == first


def test_cooldown_expires_after_window(monkeypatch):
    log = _setup(monkeypatch, responder=lambda u, kw: 200)
    S.run_connection_check()
    n = len(log)
    S._STATE["last_finished"] -= S.COOLDOWN_S + 1
    rep = S.run_connection_check()
    assert len(log) == 2 * n and rep.notice is D.DiagNotice.NONE
    assert S.COOLDOWN_S >= 20


def test_concurrent_call_is_nonblocking_and_returns_wait(monkeypatch):
    log = _setup(monkeypatch, responder=lambda u, kw: 200)
    assert S._LOCK.acquire(blocking=False)
    try:
        out = []
        t = threading.Thread(target=lambda: out.append(S.run_connection_check()))
        t.start(); t.join(2)
        assert not t.is_alive() and out[0].notice is D.DiagNotice.WAIT and log == []
        assert out[0].nas_relay.status is D.DiagStatus.NOT_CHECKED          # 無前次結果 → 初始態
    finally:
        S._LOCK.release()


def test_lock_is_released_even_if_probe_raises(monkeypatch):
    _setup(monkeypatch)
    monkeypatch.setattr(S, "_probe_all", lambda: (_ for _ in ()).throw(RuntimeError("x")))
    with pytest.raises(RuntimeError):
        S.run_connection_check()
    assert S._LOCK.acquire(blocking=False)
    S._LOCK.release()


# ── parity：與舊 UI 分類語意一致（SSLError／407 為新增，單獨列）────────
def test_classifier_parity_with_legacy_api_diagnostic():
    from src.ui.pages import api_diagnostic as A
    for code in range(100, 600):
        old, new = A._classify_status(code), S._classify_status(code)
        assert (old is None) == (new is None) and (old is None or old == new.value), code
    ex = requests.exceptions
    for e in (ex.ProxyError("x"), ex.ConnectTimeout("x"), ex.ReadTimeout("x"), ex.ConnectionError("x"),
              ex.HTTPError("x"), ValueError("x"), RuntimeError("x")):
        assert A._classify_exception(e) == S._classify_exception(e).value, type(e)
    # 新增（刻意與舊 UI 不同）：SSLError → TLS；舊 UI 歸「連線失敗」
    assert A._classify_exception(ex.SSLError("x")) == "連線失敗" and S._classify_exception(ex.SSLError("x")) is D.DiagReason.TLS
    # 舊 UI 錯誤類別字樣皆在新契約內（字樣同源）
    assert set(A.ERROR_CATEGORIES) <= {r.value for r in D.DiagReason}
