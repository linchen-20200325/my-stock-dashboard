"""🗂 資料頁「🔌 連線診斷」view（#1110 D-T2）：AppTest；mock requests＋socket guard，不連外。"""
from __future__ import annotations

import inspect
import pathlib
import re
import socket

import pytest
import requests
from streamlit.testing.v1 import AppTest

from shared.ui2_contract import diag as D
from shared.ui2_contract.pages import P4_DATA, P4_MARKET, PAGE_IDS
from src.services import connection_diag_service as S
from src.ui2.views import VIEWS, data as DATA_VIEW

ROOT = pathlib.Path(__file__).resolve().parents[1]
APP_UI2 = ROOT / "app_ui2.py"
SECRET = "TOP-SECRET-VALUE-9"


class _Resp:
    def __init__(self, code):
        self.status_code = code

    def close(self):
        pass


@pytest.fixture
def net(monkeypatch):
    """requests.get 全 mock（記次數）；socket guard；設定 getter 預設全『未設定』；重置跨 session 狀態。"""
    def deny(*a, **k):
        raise AssertionError("view 測試不得連外")
    monkeypatch.setattr(socket.socket, "connect", deny)
    monkeypatch.setattr(socket, "create_connection", deny)
    import src.data.proxy.proxy_helper as PH
    import src.config as C
    monkeypatch.setattr(PH, "get_nas_relay", lambda: None)
    monkeypatch.setattr(PH, "get_proxy_config", lambda: None)
    monkeypatch.setattr(C, "get_finmind_token", lambda: "")
    S._STATE["last_report"] = None
    S._STATE["last_finished"] = None
    calls: list[str] = []
    behaviour = {"fn": lambda url, kw: 200}

    def fake_get(url, **kw):
        calls.append(url)
        r = behaviour["fn"](url, kw)
        if isinstance(r, BaseException):
            raise r
        return _Resp(r)
    monkeypatch.setattr(requests, "get", fake_get)
    yield calls, behaviour
    S._STATE["last_report"] = None
    S._STATE["last_finished"] = None


def _app() -> AppTest:
    return AppTest.from_file(str(APP_UI2), default_timeout=60)


def _data_page(at: AppTest) -> AppTest:
    at.run(timeout=60)
    at.radio(key="ui2_page").set_value(P4_DATA).run(timeout=60)
    assert not at.exception
    return at


def _blob(at) -> str:
    return "\n".join(m.value for m in at.markdown if not m.value.lstrip().startswith("<style>"))   # 排除 CSS 註解


def _diag_block(at) -> str:
    return next(m.value for m in at.markdown if 'class="ui2-diag"' in m.value)


def test_initial_state_all_not_checked_and_no_network_over_many_reruns(net):
    calls, _ = net
    at = _data_page(_app())
    for _ in range(4):
        at.run(timeout=60)                          # 多次 rerun（含 widget 互動以外）
    assert calls == []
    blk = _diag_block(at)
    assert blk.count(D.DiagStatus.NOT_CHECKED.value) == 5 and D.TEXT_DIAG_PUBLICATION_VALUE in blk
    for s in (D.TEXT_DIAG_TITLE, D.TEXT_DIAG_NOTE, D.TEXT_DIAG_LABEL_NAS_RELAY, D.TEXT_DIAG_LABEL_NAS_PROXY,
              D.TEXT_DIAG_LABEL_EXTERNAL, D.TEXT_DIAG_LABEL_FINMIND, D.TEXT_DIAG_LABEL_YAHOO,
              D.TEXT_DIAG_LABEL_TWSE, D.TEXT_DIAG_LABEL_PUBLICATION):
        assert s in blk
    # 順序＝GPT 定稿
    labels = [D.TEXT_DIAG_LABEL_NAS_RELAY, D.TEXT_DIAG_LABEL_NAS_PROXY, D.TEXT_DIAG_LABEL_EXTERNAL,
              D.TEXT_DIAG_LABEL_FINMIND, D.TEXT_DIAG_LABEL_YAHOO, D.TEXT_DIAG_LABEL_TWSE, D.TEXT_DIAG_LABEL_PUBLICATION]
    pos = [blk.index(x) for x in labels]
    assert pos == sorted(pos)
    assert 'role="group"' in blk and f'aria-label="{D.TEXT_DIAG_ARIA}"' in blk
    assert at.button(key="ui2_diag_run").label == D.TEXT_DIAG_BUTTON
    assert not at.button(key="ui2_diag_run").disabled
    assert "ui2_diag_report" not in at.session_state


def test_no_date_or_timestamp_in_diag_block_before_and_after_click(net):
    at = _data_page(_app())
    at.button(key="ui2_diag_run").click().run(timeout=60)
    blk = _diag_block(at)
    assert not re.search(r"\d{4}[-/年]\d{1,2}", blk) and not re.search(r"\d{1,2}:\d{2}", blk)
    assert D.TEXT_DIAG_PUBLICATION_VALUE in blk


def test_page_order_first_screen_then_diag_then_rest(net):
    at = _data_page(_app())
    full = _blob(at)
    i_first, i_diag, i_rest = full.index("現在狀態"), full.index(D.TEXT_DIAG_TITLE), full.index("資料來源與連線")
    assert i_first < i_diag < i_rest


def test_click_runs_check_once_and_stores_only_safe_enum_report(net):
    calls, _ = net
    at = _data_page(_app())
    at.button(key="ui2_diag_run").click().run(timeout=60)
    assert not at.exception
    assert len(calls) == 1 and calls[0] == S.YAHOO_PROBE_URL         # 只有 Yahoo 首頁；TWSE／FinMind／代理不連網
    rep = at.session_state["ui2_diag_report"]
    assert isinstance(rep, D.DiagReport) and rep.yahoo.status is D.DiagStatus.SUCCESS
    blk = _diag_block(at)
    def chips(txt):          # 只數狀態 chip（固定說明句本身含「連線成功」字樣）
        return len(re.findall(r'<span class="ui2-chip[^>]*>[^<]*' + txt, blk))
    assert chips(D.DiagStatus.SUCCESS.value) == 1 and chips(D.DiagStatus.NOT_CONFIGURED.value) == 3
    assert chips(D.DiagStatus.NOT_CHECKED.value) == 1                # 臺灣證交所：不探測，維持尚未檢查
    # session_state 不得保存 callable／URL／文字例外
    for k, v in at.session_state.filtered_state.items():
        assert not callable(v), k
        if isinstance(v, str):
            assert "http" not in v.lower() and "Traceback" not in v, k
    # 其後無點擊的 rerun 不再探測
    at.run(timeout=60)
    assert len(calls) == 1


def test_second_click_within_cooldown_is_blocked_and_shows_wait(net):
    calls, _ = net
    at = _data_page(_app())
    at.button(key="ui2_diag_run").click().run(timeout=60)
    n = len(calls)
    at.button(key="ui2_diag_run").click().run(timeout=60)
    assert len(calls) == n
    assert D.DiagNotice.WAIT.value in _blob(at)


def test_cooldown_is_process_wide_across_sessions(net):
    calls, _ = net
    a, b = _data_page(_app()), _data_page(_app())
    a.button(key="ui2_diag_run").click().run(timeout=60)
    n = len(calls)
    b.button(key="ui2_diag_run").click().run(timeout=60)
    assert len(calls) == n and D.DiagNotice.WAIT.value in _blob(b)


def test_failures_show_fixed_categories_and_leak_nothing(net):
    calls, behaviour = net
    behaviour["fn"] = lambda url, kw: requests.exceptions.SSLError(f"boom {SECRET} http://10.0.0.1 Traceback")
    at = _data_page(_app())
    at.button(key="ui2_diag_run").click().run(timeout=60)
    assert not at.exception
    full = _blob(at) + "\n" + repr([e.value for e in at.error]) + repr([e.value for e in at.warning])
    assert D.DiagStatus.FAILED.value in _diag_block(at) and D.DiagReason.TLS.value in full
    for bad in (SECRET, "10.0.0.1", "Traceback", "boom"):
        assert bad not in full and bad not in repr(at.session_state["ui2_diag_report"])


@pytest.mark.parametrize("code,reason", [(401, D.DiagReason.AUTH), (403, D.DiagReason.AUTH),
                                         (503, D.DiagReason.SERVER)])
def test_http_status_failures_map_to_fixed_reason_text(net, code, reason):
    _, behaviour = net
    behaviour["fn"] = lambda url, kw: code
    at = _data_page(_app())
    at.button(key="ui2_diag_run").click().run(timeout=60)
    assert reason.value in _blob(at)


def test_check_callable_exception_is_swallowed_to_fixed_other(net, monkeypatch):
    def bad():
        raise RuntimeError(SECRET)
    monkeypatch.setattr(S, "run_connection_check", bad)
    at = _data_page(_app())
    at.button(key="ui2_diag_run").click().run(timeout=60)
    assert not at.exception and SECRET not in _blob(at)
    assert D.DiagReason.OTHER.value in _blob(at)


def test_other_pages_have_no_diag_block_and_never_probe(net):
    calls, _ = net
    at = _app().run(timeout=60)
    for p in PAGE_IDS:
        if p == P4_DATA:
            continue
        at.radio(key="ui2_page").set_value(p).run(timeout=60)
        assert not at.exception and D.TEXT_DIAG_TITLE not in _blob(at)
        assert not [b for b in at.button if b.key == "ui2_diag_run"]
    assert calls == []


def test_without_injected_callable_button_is_disabled_and_nothing_probes(net):
    calls, _ = net
    at = AppTest.from_string("import streamlit as st\nst.set_page_config(layout='wide')\n"
                             "from src.ui2.shell import run\nrun()", default_timeout=60).run(timeout=60)
    at.radio(key="ui2_page").set_value(P4_DATA).run(timeout=60)
    assert at.button(key="ui2_diag_run").disabled and calls == []


def test_dispatch_only_data_view_takes_diag_check():
    for pid, fn in VIEWS.items():
        params = list(inspect.signature(fn).parameters)
        assert (params == ["vm", "diag_check"]) if pid == P4_DATA else (params == ["vm"]), pid
    src = (ROOT / "src" / "ui2" / "views" / "data.py").read_text(encoding="utf-8")
    assert 'width="stretch"' in src and "KEY_DIAG_RUN" in src
    assert DATA_VIEW.KEY_DIAG_RUN == "ui2_diag_run" and DATA_VIEW.KEY_DIAG_REPORT == "ui2_diag_report"


def test_localized_copy_correction_is_minimal():
    from src.services.ui2.data_page import R_DATA_NOT_WIRED, data_page_canonical
    assert R_DATA_NOT_WIRED == "完整資料健康度尚未開放；本區僅檢查連線，不代表資料已更新" == D.TEXT_DIAG_HEALTH_NOT_OPEN
    c = data_page_canonical()
    assert "不顯示任何來源狀態" not in str(c)
    assert c["cta"]["disabled_reason"] == "資料健康度尚未開放"          # 其餘文案不動
