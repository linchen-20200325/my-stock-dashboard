"""批 Y3（2026-10-03）：只動測試／註解的兩條守衛。

  · **S7-n2** 全 repo 掃描類測試 `ast.parse` 凍結副本 `tests/fixtures/secret_scrub_{792c7a2,bf0ada3}.py` 時，
    那一則已知的 `invalid escape sequence '\\/'` 警告只在 `tests/_frozen_fixtures.parse_source` 壓掉
    （副本 sha256 凍結、⛔ 不得改）。這裡釘住：兩個掃描端真的走它、它只壓那兩份副本的那一則。
  · **D4-n7** `shared/macro_buckets.py` 三盞燈的 `source` 字串裡有**寫死**的門檻文字（不是插值）：
    ism_pmi「<50 收縮／<46 嚴重收縮」、fut_net「空單超過 1 萬口…超過 2 萬口」、margin「歷史 P95」。
    常數改了、字沒跟著改 ⇒ 畫面上的出處說明與燈號門檻不一致。本檔把寫死的數字解析出來、逐一對常數。
    ⛔ 本批不改 `shared/macro_buckets.py`（改字串產生方式屬另案），只加守衛。
"""
from __future__ import annotations

import ast
import pathlib
import re
import types
import warnings

import pytest

from tests import _frozen_fixtures as FF

_ROOT = pathlib.Path(__file__).resolve().parent.parent
_FIX = _ROOT / "tests" / "fixtures"
_FROZEN = sorted(_FIX / n for n in FF.FROZEN_ESCAPE_FIXTURES)


def _escape_warnings(fn) -> list[str]:
    with warnings.catch_warnings(record=True) as rec:
        warnings.simplefilter("always")
        fn()
    return [str(w.message) for w in rec if "invalid escape sequence" in str(w.message)]


# ══════════════════════════════════════════════════════════════════
# S7-n2
# ══════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("path", _FROZEN, ids=lambda p: p.name)
def test_frozen_fixture_still_needs_the_filter(path):
    """前提：直接 `ast.parse` 副本仍會發這則警告（若哪天不再發，壓警告那段就可以拿掉）。"""
    text = path.read_text(encoding="utf-8")
    try:
        warned = _escape_warnings(lambda: ast.parse(text))
    except SyntaxError as e:                              # 日後 Python 若把無效跳脫升級成錯誤
        pytest.skip(f"本版 Python 對 {path.name} 直接報 SyntaxError（{e.msg}）—— 前提已不同，另案處理")
    assert warned, path.name


@pytest.mark.parametrize("path", _FROZEN, ids=lambda p: p.name)
def test_parse_source_silences_only_that_warning_for_the_fixture(path):
    text = path.read_text(encoding="utf-8")
    assert _escape_warnings(lambda: FF.parse_source(text, path)) == []
    # 同一段文字放在別的路徑 ⇒ 照常警告（⛔ 不是全面關掉）。
    other = _ROOT / "tests" / "not_a_fixture.py"
    assert _escape_warnings(lambda: FF.parse_source(text, other))


def test_parse_source_keeps_other_warnings_for_the_fixture(monkeypatch):
    """副本路徑上其他訊息的警告照常（只比對 invalid escape sequence 那一則）。"""
    def _fake_parse(text, **kw):
        warnings.warn("invalid escape sequence '\\/'", DeprecationWarning)
        warnings.warn("some other deprecation", DeprecationWarning)
        warnings.warn("some other syntax warning", SyntaxWarning)
        return ast.Module(body=[], type_ignores=[])
    # 只換掉 `tests/_frozen_fixtures` 模組裡的 `ast` 名字（⛔ 不動全域 `ast.parse` —— pytest 自己報錯時也要用）。
    monkeypatch.setattr(FF, "ast", types.SimpleNamespace(parse=_fake_parse))
    with warnings.catch_warnings(record=True) as rec:
        warnings.simplefilter("always")
        FF.parse_source("", _FROZEN[0])
    assert sorted(str(w.message) for w in rec) == ["some other deprecation", "some other syntax warning"]


def test_portability_scanner_routes_through_parse_source():
    from tests import test_zz_test_portability as TZ
    for path in _FROZEN:
        assert _escape_warnings(lambda: TZ._scan(path)) == [], path.name


def test_ui_state_scanner_routes_through_parse_source():
    from tests.test_ui_state_model import TestNoDerivedRequested
    assert _escape_warnings(lambda: list(TestNoDerivedRequested()._calls())) == []


# ══════════════════════════════════════════════════════════════════
# D4-n7
# ══════════════════════════════════════════════════════════════════
def _spec(key: str):
    from shared.macro_buckets import SPECS_BY_KEY
    return SPECS_BY_KEY[key]


def test_ism_pmi_fixed_text_matches_thresholds():
    from src.data.macro import MACRO_THRESHOLDS
    spec = _spec("ism_pmi")
    # 批 Z19：寫死的「<50 收縮／<46 嚴重收縮」由 source 括號移入 note（「… / <50 收縮 / ≤46 嚴重收縮」；
    #   ≤46 依 Q-r9d 等號歸較差側，與 classify_danger 一致），守衛跟著改釘 note 的寫死數字（同一組比對，未放寬）。
    m = re.search(r"<(\d+(?:\.\d+)?) 收縮 / ≤(\d+(?:\.\d+)?) 嚴重收縮", spec.note)
    assert m, spec.note
    yellow_txt, red_txt = float(m.group(1)), float(m.group(2))
    assert (yellow_txt, red_txt) == (spec.yellow, spec.red), spec.note
    pmi = MACRO_THRESHOLDS["PMI"]
    assert (yellow_txt, red_txt) == (float(pmi["yellow_below"]), float(pmi["red_below"]))


def test_fut_net_fixed_text_matches_lot_constants():
    from shared.signal_thresholds import (
        FOREIGN_FUTURES_HIGH_RISK_THRESHOLD_LOTS,
        FOREIGN_FUTURES_MEDIUM_RISK_THRESHOLD_LOTS,
    )
    spec = _spec("fut_net")
    m = re.search(r"空單超過 (\d+) 萬口 黃燈／超過 (\d+) 萬口 紅燈", spec.source)
    assert m, spec.source
    yellow_lots, red_lots = -int(m.group(1)) * 10_000, -int(m.group(2)) * 10_000
    assert yellow_lots == FOREIGN_FUTURES_MEDIUM_RISK_THRESHOLD_LOTS == spec.yellow, spec.source
    assert red_lots == FOREIGN_FUTURES_HIGH_RISK_THRESHOLD_LOTS == spec.red, spec.source


def _margin_overheat_docstring() -> str:
    """`shared/signal_thresholds.py` 裡緊跟在 `MARGIN_BALANCE_OVERHEAT_THRESHOLD_YI` 指派後的字串（常數說明）。"""
    tree = ast.parse((_ROOT / "shared" / "signal_thresholds.py").read_text(encoding="utf-8"))
    body = tree.body
    for i, node in enumerate(body):
        if (isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
                and node.target.id == "MARGIN_BALANCE_OVERHEAT_THRESHOLD_YI"):
            nxt = body[i + 1]
            assert isinstance(nxt, ast.Expr) and isinstance(nxt.value, ast.Constant)
            return nxt.value.value
    raise AssertionError("找不到 MARGIN_BALANCE_OVERHEAT_THRESHOLD_YI")


def test_margin_p95_text_is_attached_to_the_value_it_was_measured_for():
    """「歷史 P95」是寫死的字：它只對常數說明裡記載的那個金額成立 —— 常數改了而說明沒重量 ⇒ 紅。"""
    from shared.signal_thresholds import MARGIN_BALANCE_OVERHEAT_THRESHOLD_YI
    spec = _spec("margin")
    m = re.search(r"紅線 ([\d,]+) 億（歷史 P95 經驗值）", spec.source)
    assert m, spec.source
    red_txt = float(m.group(1).replace(",", ""))
    assert red_txt == MARGIN_BALANCE_OVERHEAT_THRESHOLD_YI == spec.red, spec.source
    doc = _margin_overheat_docstring()
    d = re.search(r"> (\d+(?:\.\d+)?) 億 →[^\n]*歷史 P95", doc)
    assert d, doc
    assert float(d.group(1)) == MARGIN_BALANCE_OVERHEAT_THRESHOLD_YI, \
        "「歷史 P95」記載的金額與常數不一致 —— P95 是否仍成立要重新量測"


# ── 批 Y3 QA 補強：`parse_source` 的四個存活突變（M25／M28／M29／M30）──────────────
def _fake_ast(monkeypatch, parse):
    """只換掉 `tests/_frozen_fixtures` 模組裡的 `ast` 名字（⛔ 不動全域 `ast.parse`）。"""
    monkeypatch.setattr(FF, "ast", types.SimpleNamespace(parse=parse))


def test_parse_source_silences_the_syntaxwarning_form_too(monkeypatch):
    """M25：Python 3.12+ 改發 `SyntaxWarning`。CI 是 3.11、真的 `ast.parse` 永遠不發 —— 用假的 parse
    在 `parse_source` 的過濾範圍內發一則 SyntaxWarning 版的同一訊息，拿掉 SyntaxWarning 那條過濾即紅。"""
    def _fake_parse(text, **kw):
        warnings.warn("invalid escape sequence '\\/'", SyntaxWarning)
        return ast.Module(body=[], type_ignores=[])
    _fake_ast(monkeypatch, _fake_parse)
    assert _escape_warnings(lambda: FF.parse_source("", _FROZEN[0])) == []


def _filters_snapshot():
    return list(warnings.filters)


def test_parse_source_does_not_leak_filters_on_success():
    """M28：過濾只在 `catch_warnings` 範圍內 —— 呼叫前後全域 `warnings.filters` 必須逐項相同。"""
    before = _filters_snapshot()
    FF.parse_source(_FROZEN[0].read_text(encoding="utf-8"), _FROZEN[0])
    assert _filters_snapshot() == before


def test_parse_source_does_not_leak_filters_on_syntax_error():
    before = _filters_snapshot()
    with pytest.raises(SyntaxError):
        FF.parse_source("def (:\n", _FROZEN[0])
    assert _filters_snapshot() == before


def test_parse_source_does_not_leak_filters_on_injected_error(monkeypatch):
    class _Boom(Exception):
        pass

    def _fake_parse(text, **kw):
        raise _Boom("injected")
    _fake_ast(monkeypatch, _fake_parse)
    before = _filters_snapshot()
    with pytest.raises(_Boom):
        FF.parse_source("", _FROZEN[0])
    assert _filters_snapshot() == before


_LOOKALIKES = [
    ("other", "fixtures"),            # M29：上一層不是 tests
    ("tests", "notfixtures"),         # M30：所在目錄不是 fixtures
    ("x", "tests", "fixtures_old"),
]


@pytest.mark.parametrize("parts", _LOOKALIKES, ids=lambda p: "/".join(p))
@pytest.mark.parametrize("path", _FROZEN, ids=lambda p: p.name)
def test_lookalike_paths_are_not_frozen_fixtures(parts, path):
    """M29／M30（QA-A Q11）：檔名相同、但不在 `tests/fixtures/` 底下 ⇒ 不是凍結副本、警告照常。"""
    fake = _ROOT.joinpath("scratch_lookalike", *parts, path.name)
    assert FF.is_frozen_escape_fixture(fake) is False
    text = path.read_text(encoding="utf-8")
    assert _escape_warnings(lambda: FF.parse_source(text, fake)), fake
