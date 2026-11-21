"""B-UI2-LOOKUP-P1-INPUT-1：標的頁「股票代號輸入」P1（功能開關預設關；不接資料；純合成）。

涵蓋：開關判讀、flag-off 與現行渲染逐元素相同（golden＝改動前以 AppTest 擷取）、flag-on 的輸入／驗證／灰色狀態、
P1 不產生任何資料態、session key 紀律、以及突變 has-teeth。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from shared.ui2_contract.pages import MODE_CURATED, MODE_LOOKUP, P4_TARGET
from shared.ui2_contract.quote_view import CHIP_TEXT, NOTICE_TEXT, QuoteViewState as V
from src.ui2.components import html as H
from src.ui2.shell.app import lookup_flag_on
from src.ui2.views import target as TG

ROOT = Path(__file__).resolve().parent.parent
GOLDEN = ROOT / "tests" / "fixtures" / "ui2_lookup_p1_flag_off_golden.json"
_DATA_STATES = {V.OK.value, V.STALE.value, V.MISSING.value, V.FETCH_FAILED.value}


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv("UI2_LOOKUP_INPUT", raising=False)


def _app(*, env=None, secret=None, scenario="cold", mode=MODE_CURATED, monkeypatch=None) -> AppTest:
    if env is not None:
        monkeypatch.setenv("UI2_LOOKUP_INPUT", env)
    at = AppTest.from_file(str(ROOT / "app_ui2.py"), default_timeout=60)
    at.session_state["ui2_feed"] = "fake"
    at.session_state["ui2_page"] = P4_TARGET
    at.session_state["ui2_scenario"] = scenario
    at.session_state["ui2_target_mode"] = mode
    if secret is not None:
        at.secrets["ui2_lookup_input"] = secret
    at.run(timeout=60)
    assert not at.exception
    return at


def _snapshot(at: AppTest) -> list[list[str]]:
    return [[type(n).__name__, str(getattr(n, "value", None)), str(getattr(n, "label", None))] for n in at.main]


def _status(at: AppTest) -> list[str]:
    return [m.value for m in at.markdown if "ui2-lookup-status" in m.value]


def _has_input(at: AppTest) -> bool:
    return any(w.key == "ui2_lookup_text" for w in at.text_input)


def _submit(at: AppTest, text: str) -> AppTest:
    at.text_input(key="ui2_lookup_text").set_value(text)
    at.button[0].click().run(timeout=60)
    assert not at.exception
    return at


# ── 開關判讀 ─────────────────────────────────────────────────────────
@pytest.mark.parametrize("v,want", [
    ("1", True), ("true", True), ("TRUE", True), ("True", True), (" 1 ", True),
    ("", False), ("0", False), ("false", False), ("yes", False), ("on", False), ("2", False), ("truee", False),
    (None, False), (1, False), (True, False), (["1"], False), (b"1", False),
])
def test_flag_parse(v, want):
    assert lookup_flag_on(v) is want


@pytest.mark.parametrize("env", ["1", "true", "TRUE"])
def test_env_on(monkeypatch, env):
    assert _has_input(_app(env=env, monkeypatch=monkeypatch))


@pytest.mark.parametrize("env", ["", "0", "false", "garbage", "no"])
def test_env_off(monkeypatch, env):
    assert not _has_input(_app(env=env, monkeypatch=monkeypatch))


def test_default_off_no_config():
    assert not _has_input(_app())


@pytest.mark.parametrize("sec,want", [("1", True), ("true", True), ("0", False), ("false", False), ("x", False), (1, False)])
def test_secrets_switch(sec, want):
    assert _has_input(_app(secret=sec)) is want


def test_secrets_read_error_is_off(monkeypatch):
    import streamlit.runtime.secrets as S

    def boom(self, key):
        raise RuntimeError("secrets broken")
    monkeypatch.setattr(S.Secrets, "__contains__", boom)
    assert not _has_input(_app())                          # 讀取失敗不會開啟
    assert not _has_input(_app(env="0", monkeypatch=monkeypatch))


def test_ui2_dev_is_not_an_authorization(monkeypatch):
    at = AppTest.from_file(str(ROOT / "app_ui2.py"), default_timeout=60)
    at.session_state["ui2_feed"] = "fake"
    at.session_state["ui2_page"] = P4_TARGET
    at.query_params["ui2_dev"] = "1"
    at.run(timeout=60)
    assert not at.exception and not _has_input(at)


# ── flag-off：與現行渲染逐元素相同（golden 於改動前擷取）──────────────────
def _golden() -> dict:
    return json.loads(GOLDEN.read_text(encoding="utf-8"))


@pytest.mark.parametrize("scenario", ["cold", "loaded", "missing", "unavailable"])
@pytest.mark.parametrize("mode", [MODE_CURATED, MODE_LOOKUP])
def test_flag_off_identical_to_golden(scenario, mode):
    got = _snapshot(_app(scenario=scenario, mode=mode))
    assert got == _golden()[f"{scenario}|{mode}"]
    assert any('role="searchbox"' in row[1] for row in got)           # 仍是現行 disabled searchbox


# ── flag-on：輸入元件 ─────────────────────────────────────────────────
def test_on_replaces_disabled_searchbox_at_top(monkeypatch):
    at = _app(env="1", monkeypatch=monkeypatch)
    assert not any('role="searchbox"' in m.value for m in at.markdown)
    types = [type(n).__name__ for n in at.main]
    assert types.index("Radio") < types.index("TextInput") < types.index("Button")   # 模式切換之下、頂端
    assert at.button[0].label == "查詢"


def test_unsubmitted_is_grey_not_loaded(monkeypatch):
    at = _app(env="1", monkeypatch=monkeypatch)
    (st_html,) = _status(at)
    assert f'data-ui2-lookup-state="{V.NOT_LOADED.value}"' in st_html
    assert CHIP_TEXT[V.NOT_LOADED] in st_html and NOTICE_TEXT[V.NOT_LOADED] in st_html
    assert "ui2-chip--neutral" in st_html and "danger" not in st_html and "ui2-lookup-status__symbol" not in st_html


def test_unsubmitted_never_parses(monkeypatch):
    calls, builds = [], []
    real = TG.parse_ticker_input
    real_build = TG.build_quote_view
    monkeypatch.setattr(TG, "parse_ticker_input", lambda raw: (calls.append(raw), real(raw))[1])
    monkeypatch.setattr(TG, "build_quote_view", lambda *a, **k: (builds.append(1), real_build(*a, **k))[1])
    at = _app(env="1", monkeypatch=monkeypatch)
    at.run(timeout=60)                                             # 再 rerun 一次仍未提交
    assert calls == [] and builds == []                            # 未送出不觸發（parse／build 皆 0 次）
    _submit(at, "0050")
    assert calls == ["0050"] and builds == [1]                     # 只在提交時處理一次


def test_render_signature_unchanged_and_flag_off_path_is_render():
    import inspect
    assert list(inspect.signature(TG.render).parameters) == ["vm"]
    assert list(inspect.signature(TG.render_with_lookup).parameters) == ["vm"]
    import src.ui2.views as views
    assert views.VIEWS[P4_TARGET] is TG.render                      # 旗標關：派發表仍是現行 render(vm)


def test_p1_shows_no_price_or_staleness_text(monkeypatch):
    """P1 不顯示價格；7 日過期門檻、價格顯示範圍 0.005～1,000,000 沿用既有契約（A1 已核准，P2 才實作），P1 不重寫。"""
    at = _submit(_app(env="1", monkeypatch=monkeypatch), "0050")
    h = _status(at)[0]
    assert "收盤價" not in h and "交易日" not in h and "過期" not in h and "抓取時間" not in h


@pytest.mark.parametrize("raw", ["", "   ", "50", "2330.TW", "２３３０", "1234567", "A123", "23 30", "x" * 5000])
def test_invalid_input_is_selection_invalid_grey(monkeypatch, raw):
    at = _submit(_app(env="1", monkeypatch=monkeypatch), raw)
    (h,) = _status(at)
    assert f'data-ui2-lookup-state="{V.SELECTION_INVALID.value}"' in h
    assert CHIP_TEXT[V.SELECTION_INVALID] in h and NOTICE_TEXT[V.SELECTION_INVALID] in h
    assert "ui2-chip--neutral" in h and "danger" not in h and "ui2-lookup-status__symbol" not in h
    assert raw.strip() == "" or raw in NOTICE_TEXT[V.SELECTION_INVALID] or raw not in h                       # 不回顯原輸入
    assert at.session_state["ui2_lookup_symbol"] == ""


@pytest.mark.parametrize("raw,sym", [("0050", "0050"), ("00980A", "00980A"), ("00631l", "00631L"), (" 2330 ", "2330")])
def test_valid_shows_symbol_verbatim_and_not_loaded(monkeypatch, raw, sym):
    at = _submit(_app(env="1", monkeypatch=monkeypatch), raw)
    (h,) = _status(at)
    assert f'<strong class="ui2-lookup-status__symbol">{sym}</strong>' in h
    assert f'data-ui2-lookup-state="{V.NOT_LOADED.value}"' in h and "danger" not in h
    assert at.session_state["ui2_lookup_symbol"] == sym
    at.run(timeout=60)                                             # 後續 rerun 保留
    assert sym in _status(at)[0]


def test_no_data_state_ever(monkeypatch):
    at = _app(env="1", monkeypatch=monkeypatch)
    for raw in ("0050", "", "50", "00980A", "2330.TW"):
        _submit(at, raw)
        html = "".join(m.value for m in at.markdown)
        assert not any(s in html for s in _DATA_STATES)
        assert at.session_state["ui2_lookup_state"] in (V.NOT_LOADED.value, V.SELECTION_INVALID.value)
        for txt in (CHIP_TEXT[V.OK], CHIP_TEXT[V.STALE], CHIP_TEXT[V.MISSING], CHIP_TEXT[V.FETCH_FAILED]):
            assert txt not in _status(at)[0]


def test_session_keys_are_ui2_prefixed_strings_only(monkeypatch):
    at = _submit(_app(env="1", monkeypatch=monkeypatch), "0050")
    keys = [k for k in at.session_state.filtered_state if "lookup" in k and not k.startswith("FormSubmitter:")]
    assert keys and all(k.startswith("ui2_") for k in keys)
    for k in keys:
        assert isinstance(at.session_state[k], str)
    assert not [k for k in at.session_state.filtered_state if re.search(r"hold|strategy|sheet|portfolio", k, re.I)]


def test_add_watch_stays_disabled_and_note_kept(monkeypatch):
    at = _app(env="1", scenario="loaded", mode=MODE_LOOKUP, monkeypatch=monkeypatch)
    off = _app(scenario="loaded", mode=MODE_LOOKUP)
    assert [m.value for m in at.markdown if "ui2-lookup__add" in m.value] == [m.value for m in off.markdown if "ui2-lookup__add" in m.value]
    assert [b.label for b in at.button] == ["查詢"]                # 唯一按鈕是表單提交；加入觀察是 disabled HTML


# ── 純函式 ───────────────────────────────────────────────────────────
@pytest.mark.parametrize("raw,state", [("0050", V.NOT_LOADED), ("", V.SELECTION_INVALID), (None, V.SELECTION_INVALID),
                                       ("50", V.SELECTION_INVALID), (50, V.SELECTION_INVALID)])
def test_submission_view(raw, state):
    v = TG.lookup_submission_view(raw)
    assert v.state is state and v.value_text is None and v.fact is None


@pytest.mark.parametrize("state", [V.OK, V.STALE, V.MISSING, V.FETCH_FAILED])
def test_status_html_fails_closed_to_not_loaded(state):
    h = H.lookup_status_html(state, "0050")
    assert V.NOT_LOADED.value in h and "0050" not in h and "danger" not in h


def test_status_html_escapes():
    assert "<script>" not in H.lookup_status_html(V.NOT_LOADED, "<script>")


# ── 突變 has-teeth（以 monkeypatch 注入壞實作，同一檢查器必須轉紅）──────────
def _viol_flag_off() -> list[str]:
    return [f"{sc}|{m}" for sc in ("cold", "loaded") for m in (MODE_CURATED, MODE_LOOKUP)
            if _snapshot(_app(scenario=sc, mode=m)) != _golden()[f"{sc}|{m}"]]


def _viol_invalid_red(monkeypatch) -> list[str]:
    h = H.lookup_status_html(V.SELECTION_INVALID)
    at = _submit(_app(env="1", monkeypatch=monkeypatch), "50")
    return [x for x in ([h] + _status(at)) if "danger" in x or "ui2-chip--neutral" not in x]


def _viol_leading_zero(monkeypatch) -> list[str]:
    at = _submit(_app(env="1", monkeypatch=monkeypatch), "0050")
    return [] if at.session_state["ui2_lookup_symbol"] == "0050" and "0050" in _status(at)[0] else ["leading zero lost"]


def _viol_unsubmitted_parse(monkeypatch) -> list[str]:
    calls = []
    real = TG.parse_ticker_input
    monkeypatch.setattr(TG, "parse_ticker_input", lambda raw: (calls.append(raw), real(raw))[1])
    _app(env="1", monkeypatch=monkeypatch)
    return calls


def test_checkers_are_clean_on_real_impl(monkeypatch):
    assert _viol_flag_off() == []
    assert _viol_invalid_red(monkeypatch) == []
    assert _viol_leading_zero(monkeypatch) == []
    assert _viol_unsubmitted_parse(monkeypatch) == []


def test_mutant_flag_gate_removed(monkeypatch):
    import src.ui2.views as views
    monkeypatch.setitem(views.VIEWS, P4_TARGET, TG.render_with_lookup)      # 旗標關也走輸入入口＝gate 被拿掉
    assert _viol_flag_off()


def test_mutant_invalid_rendered_red(monkeypatch):
    from shared.ui2_contract.tones import ChipTone
    monkeypatch.setattr(H, "CHIP_TONE", {**H.CHIP_TONE, V.SELECTION_INVALID: ChipTone.DANGER})
    assert _viol_invalid_red(monkeypatch)


def test_mutant_numerified_symbol(monkeypatch):
    real = TG.parse_ticker_input
    from dataclasses import replace

    def numerify(raw):
        s = real(raw)
        return replace(s, symbol=str(int(s.symbol))) if s.symbol and s.symbol.isdigit() else s
    monkeypatch.setattr(TG, "parse_ticker_input", numerify)
    assert _viol_leading_zero(monkeypatch)


def test_mutant_validates_without_submit(monkeypatch):
    import streamlit as st
    monkeypatch.setattr(st, "form_submit_button", lambda *a, **k: True)
    assert _viol_unsubmitted_parse(monkeypatch)
