"""B 線「離線可用」收斂（#1199 comment 6988310131）：🗂 資料頁「🔌 連線診斷」兩個離線可重現的使用者阻礙。

* G-B1：冷卻提示「請稍後再試」是**那次點擊**的結果，不得在其後任何 rerun／換頁再回來時仍掛著（過期的錯誤導引）。
* G-B2：`diag_check` 回來的 `DiagReport` 形狀不對（欄位不是 `ProbeResult`／列舉）時，必須 fail closed 成固定「連線失敗／其他」，
  不得原樣存進 session 後讓資料頁每次 rerun 都崩潰。

只用 AppTest＋monkeypatch 注入假 `run_connection_check`；socket 一律禁止，不連外。不改版面、不加文案、不動 Schema。
"""
from __future__ import annotations

import pathlib
import socket
from dataclasses import replace

import pytest
from streamlit.testing.v1 import AppTest

from shared.ui2_contract import diag as D
from shared.ui2_contract.pages import P4_DATA, P4_MARKET
from src.services import connection_diag_service as S

ROOT = pathlib.Path(__file__).resolve().parents[1]
APP_UI2 = ROOT / "app_ui2.py"
_OK = D.ProbeResult(D.DiagStatus.SUCCESS)
_GOOD = D.DiagReport(_OK, _OK, _OK, _OK, _OK)
_WAIT = D.DiagNotice.WAIT.value


@pytest.fixture
def stub(monkeypatch):
    def deny(*a, **k):
        raise AssertionError("離線測試不得連外")
    monkeypatch.setattr(socket.socket, "connect", deny)
    monkeypatch.setattr(socket, "create_connection", deny)
    box = {"result": _GOOD, "calls": 0}

    def fake():
        box["calls"] += 1
        r = box["result"]
        if isinstance(r, BaseException):
            raise r
        return r
    monkeypatch.setattr(S, "run_connection_check", fake)
    return box


def _data_page(**ss) -> AppTest:
    at = AppTest.from_file(str(APP_UI2), default_timeout=60)
    for k, v in ss.items():
        at.session_state[k] = v
    at.run(timeout=60)
    at.radio(key="ui2_page").set_value(P4_DATA).run(timeout=60)
    return at


def _blob(at) -> str:
    return "\n".join(m.value for m in at.markdown if not m.value.lstrip().startswith("<style>"))


def _goto(at, page):
    at.radio(key="ui2_page").set_value(page).run(timeout=60)


def test_wait_notice_shows_on_the_click_that_produced_it(stub):
    stub["result"] = replace(_GOOD, notice=D.DiagNotice.WAIT)
    at = _data_page()
    assert _WAIT not in _blob(at)
    at.button(key="ui2_diag_run").click().run(timeout=60)
    assert not at.exception
    assert _WAIT in _blob(at)                          # 控制組：點擊當次要看得到


def test_wait_notice_does_not_linger_after_plain_rerun_or_page_change(stub):
    stub["result"] = replace(_GOOD, notice=D.DiagNotice.WAIT)
    at = _data_page()
    at.button(key="ui2_diag_run").click().run(timeout=60)
    assert _WAIT in _blob(at)
    at.run(timeout=60)                                 # 無點擊的 rerun
    assert _WAIT not in _blob(at)
    _goto(at, P4_MARKET)
    _goto(at, P4_DATA)                                 # 換頁再回來
    assert not at.exception and _WAIT not in _blob(at)
    assert stub["calls"] == 1                          # 其間不得再探測
    # 狀態列（上次檢查結果）仍保留：只丟掉過期提示，不丟結果
    assert _blob(at).count(D.DiagStatus.SUCCESS.value) >= 5
    assert at.session_state["ui2_diag_report"].notice is D.DiagNotice.NONE


def test_wait_notice_reappears_when_user_clicks_again(stub):
    stub["result"] = replace(_GOOD, notice=D.DiagNotice.WAIT)
    at = _data_page()
    at.button(key="ui2_diag_run").click().run(timeout=60)
    at.run(timeout=60)
    assert _WAIT not in _blob(at)
    at.button(key="ui2_diag_run").click().run(timeout=60)
    assert _WAIT in _blob(at) and stub["calls"] == 2


_MALFORMED = [
    pytest.param(D.DiagReport("x", "y", "z", "w", "v"), id="fields-are-strings"),
    pytest.param(D.DiagReport(_OK, _OK, _OK, _OK, D.ProbeResult("連線成功", D.DiagReason.NONE)), id="status-not-enum"),
    pytest.param(D.DiagReport(_OK, _OK, _OK, _OK, D.ProbeResult(D.DiagStatus.FAILED, "逾時")), id="reason-not-enum"),
    pytest.param(replace(_GOOD, notice="請稍後再試"), id="notice-not-enum"),
    pytest.param(D.DiagReport(None, _OK, _OK, _OK, _OK), id="field-none"),
]


@pytest.mark.parametrize("bad", _MALFORMED)
def test_malformed_report_from_check_fails_closed_to_fixed_failure(stub, bad):
    stub["result"] = bad
    at = _data_page()
    at.button(key="ui2_diag_run").click().run(timeout=60)
    assert not at.exception
    blk = next(m.value for m in at.markdown if 'class="ui2-diag"' in m.value)
    assert blk.count(D.DiagStatus.FAILED.value) == 5                      # 與「回傳非 DiagReport」同一個固定結果
    assert D.DiagReason.OTHER.value in _blob(at)
    # 其後任何 rerun／換頁再回來都不得崩潰
    at.run(timeout=60)
    _goto(at, P4_MARKET)
    _goto(at, P4_DATA)
    assert not at.exception
    rep = at.session_state["ui2_diag_report"]
    assert all(isinstance(p.status, D.DiagStatus) and isinstance(p.reason, D.DiagReason)
               for p in (rep.nas_relay, rep.nas_proxy, rep.finmind, rep.yahoo, rep.twse))


def test_malformed_report_already_in_session_is_shown_as_not_checked(stub):
    at = _data_page(ui2_diag_report=D.DiagReport("x", "y", "z", "w", "v"))
    assert not at.exception
    blk = next(m.value for m in at.markdown if 'class="ui2-diag"' in m.value)
    assert blk.count(D.DiagStatus.NOT_CHECKED.value) == 5 and stub["calls"] == 0


def test_non_report_and_exception_results_still_fixed_other(stub):
    for r in (None, "junk", RuntimeError("secret-token-123")):
        stub["result"] = r
        at = _data_page()
        at.button(key="ui2_diag_run").click().run(timeout=60)
        assert not at.exception
        assert "secret-token-123" not in _blob(at)
        blk = next(m.value for m in at.markdown if 'class="ui2-diag"' in m.value)
        assert blk.count(D.DiagStatus.FAILED.value) == 5


def test_valid_mixed_report_is_stored_and_rendered_unchanged(stub):
    mixed = D.DiagReport(
        D.ProbeResult(D.DiagStatus.FAILED, D.DiagReason.TIMEOUT), D.ProbeResult(D.DiagStatus.NOT_CONFIGURED),
        D.ProbeResult(D.DiagStatus.NOT_CHECKED), D.ProbeResult(D.DiagStatus.AUTH_UNVERIFIED, D.DiagReason.KEY_MISSING),
        D.ProbeResult(D.DiagStatus.NOT_CHECKED))
    stub["result"] = mixed
    at = _data_page()
    at.button(key="ui2_diag_run").click().run(timeout=60)
    assert at.session_state["ui2_diag_report"] == mixed
    assert D.DiagReason.TIMEOUT.value in _blob(at) and D.DiagReason.KEY_MISSING.value in _blob(at)
