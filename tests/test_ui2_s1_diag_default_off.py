"""S1：資料頁「🔌 連線診斷」功能開關預設關（`ui2_diag_enabled`／`UI2_DIAG_ENABLE`）＋ S3 特徵化。

預設（旗標 OFF）：入口不注入 `run_connection_check`（按鈕保留但 disabled、區塊內多一行固定說明、不探測、不連外）。
旗標 ON：與先前行為一致（點擊才探測、冷卻、固定安全原因類別）。全部離線：socket／requests／urllib 一律封鎖或 stub。
"""
from __future__ import annotations

import ast
import os
import pathlib
import socket
import urllib.request

import pytest
import requests
from streamlit.testing.v1 import AppTest

from shared.ui2_contract import diag as D
from shared.ui2_contract.pages import P4_DATA, PAGE_IDS
from shared.ui2_contract.text import (PREVIEW_BANNER_TEXT, REAL_PREVIEW_BANNER_NOTE,
                                      REAL_PREVIEW_BANNER_TEXT)
from src.services import connection_diag_service as S
from src.ui2.shell.app import lookup_flag_on

ROOT = pathlib.Path(__file__).resolve().parents[1]
APP_UI2 = ROOT / "app_ui2.py"
BTN = "ui2_diag_run"
CANARY = {"FINMIND_TOKEN": "FAKE_CANARY_FINMIND", "NAS_API_KEY": "FAKE_CANARY_NASKEY",
          "NAS_BASE_URL": "https://FAKE_CANARY_NASHOST.invalid", "PROXY_URL": "http://FAKE_CANARY_PROXY.invalid:3128"}
_OK = D.ProbeResult(D.DiagStatus.SUCCESS)
_SAFE = D.DiagReport(_OK, _OK, _OK, _OK, _OK)


# ── 共用 ─────────────────────────────────────────────────────────────
@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    monkeypatch.delenv("UI2_DIAG_ENABLE", raising=False)
    S._STATE["last_report"] = None
    S._STATE["last_finished"] = None
    yield
    S._STATE["last_report"] = None
    S._STATE["last_finished"] = None


@pytest.fixture
def counter(monkeypatch):
    """以計數函式取代 `S.run_connection_check`（app_ui2.py 在 AppTest 啟動時才 import，會取到這個）。"""
    box = {"n": 0}

    def fake():
        box["n"] += 1
        return _SAFE
    monkeypatch.setattr(S, "run_connection_check", fake)
    return box


@pytest.fixture
def net_block(monkeypatch):
    """封鎖所有外連入口並記錄嘗試；不實際連線。"""
    attempts: list[str] = []

    def mk(name):
        def blocked(*a, **k):
            attempts.append(name)
            raise AssertionError(f"offline test: {name} blocked")
        return blocked
    monkeypatch.setattr(socket.socket, "connect", mk("socket.connect"))
    monkeypatch.setattr(socket, "create_connection", mk("socket.create_connection"))
    monkeypatch.setattr(socket, "getaddrinfo", mk("socket.getaddrinfo"))
    monkeypatch.setattr(requests.Session, "request", mk("requests.Session.request"))
    monkeypatch.setattr(urllib.request, "urlopen", mk("urllib.request.urlopen"))
    return attempts


def _app(*, secret=None, query=None) -> AppTest:
    at = AppTest.from_file(str(APP_UI2), default_timeout=60)
    if secret is not None:
        at.secrets["ui2_diag_enabled"] = secret
    if query:
        for k, v in query.items():
            at.query_params[k] = v
    return at


def _data_page(at: AppTest) -> AppTest:
    at.run(timeout=60)
    at.radio(key="ui2_page").set_value(P4_DATA).run(timeout=60)
    assert not at.exception
    return at


def _blob(at) -> str:
    return "\n".join(m.value for m in at.markdown if not m.value.lstrip().startswith("<style>"))


def _diag_block(at) -> str:
    return next(m.value for m in at.markdown if 'class="ui2-diag"' in m.value)


def _all_text(at) -> str:
    return _blob(at) + repr([e.value for e in at.error]) + repr([w.value for w in at.warning]) + repr(
        [b.label for b in at.button]) + repr(at.session_state.filtered_state)


# ── T1：旗標 OFF（預設） ─────────────────────────────────────────────
def test_t1_default_off_button_disabled_callable_never_called_and_copy_shown(counter):
    at = _data_page(_app())
    assert at.button(key=BTN).disabled and at.button(key=BTN).label == D.TEXT_DIAG_BUTTON
    at.button(key=BTN).click().run(timeout=60)           # 即使（測試環境）送出點擊，也不得探測
    for _ in range(3):
        at.run(timeout=60)
    assert counter["n"] == 0 and "ui2_diag_report" not in at.session_state
    blk = _diag_block(at)
    assert D.TEXT_DIAG_PREVIEW_UNAVAILABLE == "連線診斷暫不提供（預覽模式）"
    assert blk.count(D.TEXT_DIAG_PREVIEW_UNAVAILABLE) == 1
    # 位置：同區塊、說明句之後、狀態列之前
    assert blk.index(D.TEXT_DIAG_NOTE) < blk.index(D.TEXT_DIAG_PREVIEW_UNAVAILABLE) < blk.index(D.TEXT_DIAG_LABEL_NAS_RELAY)
    assert f'<div class="ui2-diag__note">{D.TEXT_DIAG_PREVIEW_UNAVAILABLE}</div>' in blk
    # 其餘診斷列原樣
    assert blk.count(D.DiagStatus.NOT_CHECKED.value) == 5 and D.TEXT_DIAG_PUBLICATION_VALUE in blk
    for s in (D.TEXT_DIAG_TITLE, D.TEXT_DIAG_NOTE, D.TEXT_DIAG_LABEL_NAS_RELAY, D.TEXT_DIAG_LABEL_NAS_PROXY,
              D.TEXT_DIAG_LABEL_EXTERNAL, D.TEXT_DIAG_LABEL_FINMIND, D.TEXT_DIAG_LABEL_YAHOO,
              D.TEXT_DIAG_LABEL_TWSE, D.TEXT_DIAG_LABEL_PUBLICATION):
        assert s in blk
    assert not [m for m in at.markdown if '<div class="ui2-diag__reason">' in m.value]   # 固定原因類別區沒有任何原因文字


def test_t1_flag_on_html_has_no_unavailable_note(counter):
    at = _data_page(_app(secret="1"))
    assert D.TEXT_DIAG_PREVIEW_UNAVAILABLE not in _diag_block(at) and not at.button(key=BTN).disabled


def test_t1_block_html_flag_on_is_byte_identical_to_legacy_shape():
    from src.ui2.views import data as V
    on, off = V._block_html(D.INITIAL_REPORT), V._block_html(D.INITIAL_REPORT, preview_unavailable=True)
    assert on == V._block_html(D.INITIAL_REPORT, preview_unavailable=False)
    note = f'<div class="ui2-diag__note">{D.TEXT_DIAG_PREVIEW_UNAVAILABLE}</div>'
    assert off.replace(note, "", 1) == on and note not in on


# ── T2：旗標 OFF＋封網＋假 canary ────────────────────────────────────
def test_t2_blocking_has_teeth_positive_control(net_block):
    for fn in (lambda: socket.create_connection(("127.0.0.1", 9)), lambda: socket.getaddrinfo("x.invalid", 80),
               lambda: requests.Session().request("GET", "http://x.invalid"), lambda: urllib.request.urlopen("http://x.invalid"),
               lambda: socket.socket().connect(("127.0.0.1", 9))):
        with pytest.raises(AssertionError):
            fn()
    assert set(net_block) == {"socket.create_connection", "socket.getaddrinfo", "requests.Session.request",
                              "urllib.request.urlopen", "socket.connect"}


def test_t2_default_off_zero_egress_with_canary_secrets(monkeypatch, net_block, counter):
    for k, v in CANARY.items():
        monkeypatch.setenv(k, v)
    at = _app()
    for k, v in CANARY.items():
        at.secrets[k] = v
    at.run(timeout=60)
    assert not at.exception
    for p in PAGE_IDS:                                     # 五頁都渲染
        at.radio(key="ui2_page").set_value(p).run(timeout=60)
        assert not at.exception, p
        assert not any(c in _all_text(at) for c in CANARY.values()), p
    at.radio(key="ui2_page").set_value(P4_DATA).run(timeout=60)
    assert at.button(key=BTN).disabled
    at.button(key=BTN).click().run(timeout=60)             # 嘗試點擊停用按鈕
    assert not at.exception
    assert "ui2_diag_report" not in at.session_state       # 沒有探測報告
    assert net_block == [] and counter["n"] == 0
    assert not any(c in _all_text(at) for c in CANARY.values())


# ── T3：旗標 ON（secrets／env 兩種來源） ──────────────────────────────
def _assert_on_behaviour(at, counter):
    assert not at.button(key=BTN).disabled
    assert counter["n"] == 0                               # 不點不探測
    at.run(timeout=60)
    assert counter["n"] == 0
    at.button(key=BTN).click().run(timeout=60)
    assert not at.exception and counter["n"] == 1          # 點擊恰呼叫一次
    assert at.session_state["ui2_diag_report"] == _SAFE
    blk = _diag_block(at)
    assert D.TEXT_DIAG_PREVIEW_UNAVAILABLE not in blk and blk.count(D.DiagStatus.SUCCESS.value) >= 5
    at.run(timeout=60)
    assert counter["n"] == 1                               # 其後 rerun 不再探測


def test_t3_flag_on_via_secrets(counter):
    _assert_on_behaviour(_data_page(_app(secret="1")), counter)


def test_t3_flag_on_via_env(monkeypatch, counter):
    monkeypatch.setenv("UI2_DIAG_ENABLE", "true")
    _assert_on_behaviour(_data_page(_app()), counter)


# ── T4：旗標解析 ─────────────────────────────────────────────────────
_CASES = [("1", True), ("true", True), ("TRUE", True), ("0", False), ("", False), ("false", False),
          (None, False), ("yes", False), ("on", False)]


@pytest.mark.parametrize("v,want", _CASES)
def test_t4_lookup_flag_on_semantics(v, want):
    assert lookup_flag_on(v) is want


@pytest.mark.parametrize("v,want", _CASES)
def test_t4_env_values_end_to_end(monkeypatch, counter, v, want):
    if v is not None:
        monkeypatch.setenv("UI2_DIAG_ENABLE", v)
    at = _data_page(_app())
    assert at.button(key=BTN).disabled is (not want)


@pytest.mark.parametrize("sec,env,want", [("0", "1", False), ("1", "0", True), ("", "1", False), ("true", None, True)])
def test_t4_secrets_take_priority_over_env(monkeypatch, counter, sec, env, want):
    if env is not None:
        monkeypatch.setenv("UI2_DIAG_ENABLE", env)
    at = _data_page(_app(secret=sec))
    assert at.button(key=BTN).disabled is (not want)


def _load_read_diag_flag(fake_st, environ=None):
    """從 app_ui2.py 的 AST 單獨取出 `_read_diag_flag` 執行（不跑整個 script），以便注入會丟例外的 secrets／environ。"""
    fn = next(n for n in ast.parse(APP_UI2.read_text(encoding="utf-8")).body
              if isinstance(n, ast.FunctionDef) and n.name == "_read_diag_flag")
    mod = ast.Module(body=[fn], type_ignores=[])
    ns = {"st": fake_st, "os": environ or os, "lookup_flag_on": lookup_flag_on}
    exec(compile(ast.fix_missing_locations(mod), "app_ui2.py", "exec"), ns)
    return ns["_read_diag_flag"]


class _Secrets:
    def __init__(self, data=None, boom=False):
        self.data, self.boom = data or {}, boom

    def __contains__(self, k):
        if self.boom:
            raise RuntimeError("no secrets file")
        return k in self.data

    def __getitem__(self, k):
        if self.boom:
            raise RuntimeError("no secrets file")
        return self.data[k]


class _St:
    def __init__(self, secrets):
        self.secrets = secrets


class _Env:
    def __init__(self, val=None, boom=False):
        self.val, self.boom = val, boom
        self.environ = self

    def get(self, k):
        if self.boom:
            raise RuntimeError("env boom")
        assert k == "UI2_DIAG_ENABLE"
        return self.val


def test_t4_read_exceptions_never_turn_it_on():
    # secrets 讀取例外＝該來源不存在；env 也無值 → OFF
    assert _load_read_diag_flag(_St(_Secrets(boom=True)), _Env(None))() is False
    # env 讀取例外 → OFF（即使 secrets 不存在）
    assert _load_read_diag_flag(_St(_Secrets()), _Env(boom=True))() is False
    # secrets 與 env 都丟例外 → OFF
    assert _load_read_diag_flag(_St(_Secrets(boom=True)), _Env(boom=True))() is False
    # 比照 `_read_lookup_flag`：secrets 例外時退回 env（env 明確為 '1' 才開）
    assert _load_read_diag_flag(_St(_Secrets(boom=True)), _Env("1"))() is True
    # secrets 有鍵且為關 → 不看 env
    assert _load_read_diag_flag(_St(_Secrets({"ui2_diag_enabled": "0"})), _Env("1"))() is False


def test_t4_ui2_dev_does_not_enable(counter):
    at = _app(query={"ui2_dev": "1"})
    at = _data_page(at)
    assert at.button(key=BTN).disabled and counter["n"] == 0
    at.button(key=BTN).click().run(timeout=60)
    assert counter["n"] == 0 and "ui2_diag_report" not in at.session_state
    # 旗標 ON 時 ui2_dev 與否都不改變「ON」（兩個條件互相獨立）
    at2 = _data_page(_app(secret="1", query={"ui2_dev": "1"}))
    assert not at2.button(key=BTN).disabled


# ── T5：靜態守衛 ─────────────────────────────────────────────────────
def test_t5_app_ui2_single_run_call_and_conditional_diag_check():
    tree = ast.parse(APP_UI2.read_text(encoding="utf-8"))
    runs = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "run"]
    assert len(runs) == 1
    kw = {k.arg: k.value for k in runs[0].keywords}
    v = kw["diag_check"]
    assert isinstance(v, ast.IfExp)                                    # 條件式，非無條件傳入
    assert isinstance(v.test, ast.Call) and getattr(v.test.func, "id", None) == "_read_diag_flag"
    assert isinstance(v.body, ast.Name) and v.body.id == "run_connection_check"
    assert isinstance(v.orelse, ast.Constant) and v.orelse.value is None
    # run_connection_check 只出現在 import 與上述 IfExp 兩處
    names = [n for n in ast.walk(tree) if isinstance(n, ast.Name) and n.id == "run_connection_check"]
    assert len(names) == 1 and names[0] is v.body
    assert not any(isinstance(n, ast.Attribute) and n.attr == "run_connection_check" for n in ast.walk(tree))


def test_t5_import_line_unchanged_and_unique():
    src = APP_UI2.read_text(encoding="utf-8")
    imps = [n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.ImportFrom)
            and n.module == "src.services.connection_diag_service"]
    assert len(imps) == 1 and [(a.name, a.asname) for a in imps[0].names] == [("run_connection_check", None)]
    assert src.count("from src.services.connection_diag_service import run_connection_check  # noqa: E402") == 1


def test_t5_forbidden_substrings_and_ordering():
    src = APP_UI2.read_text(encoding="utf-8")
    for bad in ("portfolio", "holdings", "OneBrain", "onebrain", "gsheet"):
        assert bad not in src, bad
    tree = ast.parse(src)
    first = next(n for n in tree.body if isinstance(n, ast.Expr) and isinstance(n.value, ast.Call)
                 and getattr(getattr(n.value.func, "value", None), "id", None) == "st")
    assert first.value.func.attr == "set_page_config"
    seed = next(i for i, n in enumerate(tree.body) if isinstance(n, ast.If) and "ui2_feed" in ast.unparse(n))
    run_i = next(i for i, n in enumerate(tree.body) if isinstance(n, ast.Expr) and "run(" in ast.unparse(n))
    assert seed < run_i
    assert "ui2_dev" not in ast.unparse(next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_read_diag_flag"))


# ── T6：S3 特徵化（旗標 ON；requests 層 stub，不連外） ────────────────
class _Resp:
    def __init__(self, code):
        self.status_code = code

    def close(self):
        pass


@pytest.fixture
def req(monkeypatch):
    def deny(*a, **k):
        raise AssertionError("不得連外")
    monkeypatch.setattr(socket.socket, "connect", deny)
    monkeypatch.setattr(socket, "create_connection", deny)
    import src.config as C
    import src.data.proxy.proxy_helper as PH
    monkeypatch.setattr(PH, "get_nas_relay", lambda: ("https://FAKE_CANARY_NASHOST.invalid", "FAKE_CANARY_NASKEY"))
    monkeypatch.setattr(PH, "get_proxy_config", lambda: None)
    monkeypatch.setattr(C, "get_finmind_token", lambda: "FAKE_CANARY_FINMIND")
    calls: list[tuple[str, dict]] = []
    beh = {"fn": lambda url, kw: 200}

    def fake_get(url, **kw):
        calls.append((url, kw))
        r = beh["fn"](url, kw)
        if isinstance(r, BaseException):
            raise r
        return _Resp(r)
    monkeypatch.setattr(requests, "get", fake_get)
    return calls, beh


def test_t6_request_only_on_click_when_flag_on(req):
    calls, _ = req
    at = _data_page(_app(secret="1"))
    for _ in range(3):
        at.run(timeout=60)
    assert calls == []                                     # 不點不發請求
    at.button(key=BTN).click().run(timeout=60)
    assert not at.exception and len(calls) >= 1            # 點了才發
    n = len(calls)
    at.run(timeout=60)
    assert len(calls) == n


@pytest.mark.parametrize("exc", [
    requests.exceptions.SSLError("boom https://FAKE_CANARY_NASHOST.invalid key=FAKE_CANARY_NASKEY FAKE_CANARY_FINMIND"),
    requests.exceptions.ConnectionError("http://FAKE_CANARY_PROXY.invalid:3128 FAKE_CANARY_NASKEY Traceback"),
    requests.exceptions.Timeout("FAKE_CANARY_NASHOST"),
    RuntimeError("FAKE_CANARY_NASKEY"),
])
def test_t6_failure_output_never_contains_url_key_or_canary(req, exc):
    _, beh = req
    beh["fn"] = lambda url, kw: exc
    at = _data_page(_app(secret="1"))
    at.button(key=BTN).click().run(timeout=60)
    assert not at.exception
    text = _all_text(at)
    for bad in ("FAKE_CANARY", "http://", "https://", "Traceback", "boom", "X-API-Key"):
        assert bad not in text.replace('xmlns="http://www.w3.org/2000/svg"', ""), bad
    assert D.DiagStatus.FAILED.value in _diag_block(at)


def test_t6_key_is_only_sent_as_header_never_in_ui(req):
    calls, beh = req
    beh["fn"] = lambda url, kw: 401 if "X-API-Key" not in (kw.get("headers") or {}) else 200
    at = _data_page(_app(secret="1"))
    at.button(key=BTN).click().run(timeout=60)
    assert any("X-API-Key" in (kw.get("headers") or {}) for _, kw in calls)      # 有送出（stub 內）
    assert "FAKE_CANARY" not in _all_text(at)


# ── T7：Real／FAKE 橫幅與過期揭露不變（旗標 OFF 預設） ─────────────────
def test_t7_real_banner_default_and_fake_banner_under_dev_scenario(counter):
    at = _app().run(timeout=60)
    assert not at.exception
    txt = _blob(at)
    assert REAL_PREVIEW_BANNER_TEXT in txt and REAL_PREVIEW_BANNER_NOTE in txt
    assert PREVIEW_BANNER_TEXT not in txt
    at2 = _app(query={"ui2_dev": "1"})
    at2.session_state["ui2_feed"] = "fake"
    at2.run(timeout=60)
    assert not at2.exception
    assert PREVIEW_BANNER_TEXT in _blob(at2) and REAL_PREVIEW_BANNER_TEXT not in _blob(at2)
    assert counter["n"] == 0
