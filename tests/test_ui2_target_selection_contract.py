"""B-UI2-PUBLIC-TICKER-CONTRACT-MINSLICE-1：公開股票選取／跨頁代號 identity 小契約（純合成、離線）。"""
from __future__ import annotations

import ast
import dataclasses
import itertools
import pathlib
import re

import pytest

from shared.ui2_contract import target_selection as TS
from shared.ui2_contract.target_selection import (
    QuoteReadiness as R, SelectionStatus as S, TickerSelection, parse_ticker_input, parse_ticker_list,
    quote_readiness,
)
from tests.test_ui2_guards import check_capability_marker_scope, check_vm_purity

SRC = pathlib.Path(TS.__file__)
REL = "shared/ui2_contract/target_selection.py"


# ── parse_ticker_input ───────────────────────────────────────────────
@pytest.mark.parametrize("raw,sym", [
    ("0050", "0050"), ("2330", "2330"), ("00631L", "00631L"), ("00980A", "00980A"),
    ("  2330  ", "2330"), ("\t0050\n", "0050"),
    ("2330a", "2330A"),            # 小寫＝唯一的規格化（大寫化），非補零／猜測
    ("00631l", "00631L"),
])
def test_selected(raw, sym):
    r = parse_ticker_input(raw)
    assert (r.status, r.symbol, r.reason, r.raw) == (S.SELECTED, sym, None, raw)


@pytest.mark.parametrize("raw", [None, "", "   ", "\t\n", "　"])
def test_empty(raw):
    r = parse_ticker_input(raw)
    assert (r.status, r.symbol, r.reason) == (S.EMPTY, None, None)


@pytest.mark.parametrize("raw,reason", [
    ("50", TS.REASON_TOO_SHORT),            # 不補零
    ("050", TS.REASON_TOO_SHORT),
    ("2330.TW", TS.REASON_SUFFIX), ("2330.TWO", TS.REASON_SUFFIX), ("2330.tw", TS.REASON_SUFFIX),
    ("0050.TW", TS.REASON_SUFFIX),
    ("２３３０", TS.REASON_NON_ASCII),       # 全形
    ("2330ı", TS.REASON_NON_ASCII),         # upper() 會變 ASCII 'I' 的陷阱
    ("23 30", TS.REASON_INTERNAL_WHITESPACE),
    ("2330-A", TS.REASON_BAD_CHARS), ("23@0", TS.REASON_BAD_CHARS), ("2330.HK", TS.REASON_BAD_CHARS),
    ("1234567", TS.REASON_TOO_LONG), ("00631L1", TS.REASON_TOO_LONG),
    ("A123", TS.REASON_FIRST_NOT_DIGIT), ("TSMC", TS.REASON_FIRST_NOT_DIGIT),
    (50, TS.REASON_NOT_TEXT), (b"0050", TS.REASON_NOT_TEXT), (2330.0, TS.REASON_NOT_TEXT),
    (["2330"], TS.REASON_NOT_TEXT), (True, TS.REASON_NOT_TEXT),
])
def test_invalid(raw, reason):
    r = parse_ticker_input(raw)
    assert r.status is S.INVALID and r.symbol is None and r.reason == reason
    assert r.raw is raw or r.raw == raw


def test_no_zero_fill_or_strip():
    assert parse_ticker_input("50").symbol is None
    assert parse_ticker_input("0050").symbol == "0050"       # 不去零
    assert parse_ticker_input("2330.TW").symbol is None      # 不去後綴
    assert parse_ticker_input("2330").symbol == "2330"       # 不補後綴


def test_frozen():
    r = parse_ticker_input("2330")
    with pytest.raises(dataclasses.FrozenInstanceError):
        r.symbol = "0050"  # type: ignore[misc]


# ── parse_ticker_list ────────────────────────────────────────────────
def test_list_duplicates_disclosed_ordered():
    r = parse_ticker_list(["2330", "0050", "2330"])
    assert r.selected == ("2330", "0050") and r.duplicates == ("2330",)
    assert r.invalid == () and r.empty_count == 0


def test_list_duplicates_after_normalisation_and_once_each():
    r = parse_ticker_list(["2330a", " 2330A ", "0050", "0050", "2330A"])
    assert r.selected == ("2330A", "0050") and r.duplicates == ("2330A", "0050")


def test_list_mixed():
    r = parse_ticker_list(["2330", "", None, "50", 50, "00631L", "2330.TW"])
    assert r.selected == ("2330", "00631L") and r.empty_count == 2
    assert [i.reason for i in r.invalid] == [TS.REASON_TOO_SHORT, TS.REASON_NOT_TEXT, TS.REASON_SUFFIX]


def test_list_all_invalid_and_empty_list():
    r = parse_ticker_list(["x", "50", "２３３０"])
    assert r.selected == () and r.duplicates == () and len(r.invalid) == 3
    e = parse_ticker_list([])
    assert (e.selected, e.duplicates, e.invalid, e.empty_count) == ((), (), (), 0)


@pytest.mark.parametrize("raws", [None, "2330", b"2330", 2330, {"2330"}])
def test_list_non_list_is_invalid_not_guessed(raws):
    r = parse_ticker_list(raws)
    assert r.selected == () and len(r.invalid) == 1 and r.invalid[0].reason == TS.REASON_NOT_A_LIST


def test_list_tuple_accepted():
    assert parse_ticker_list(("0050", "2330")).selected == ("0050", "2330")


# ── quote_readiness 優先序 ───────────────────────────────────────────
SEL = parse_ticker_input("2330")
BAD = parse_ticker_input("50")
EMP = parse_ticker_input("")


def _expected(valid, loaded, src, asof, stale):
    if not valid:
        return R.SELECTION_INVALID
    if not loaded:
        return R.NOT_LOADED
    if not src:
        return R.SOURCE_UNAVAILABLE
    if not asof:
        return R.AS_OF_UNKNOWN
    if stale:
        return R.STALE
    return R.READY


@pytest.mark.parametrize("valid,loaded,src,asof,stale", list(itertools.product([True, False], repeat=5)))
def test_readiness_full_table(valid, loaded, src, asof, stale):
    sel = SEL if valid else BAD
    got = quote_readiness(sel, loaded=loaded, source_present=src, as_of_known=asof, is_stale=stale)
    assert got is _expected(valid, loaded, src, asof, stale)
    if got is R.READY:
        assert valid and loaded and src and asof and not stale


def test_readiness_each_layer_reachable_and_ready_unique():
    seen = {quote_readiness(s, loaded=a, source_present=b, as_of_known=c, is_stale=d)
            for s in (SEL, BAD) for a, b, c, d in itertools.product([True, False], repeat=4)}
    assert seen == set(R)


def test_readiness_empty_and_foreign_selection_invalid():
    kw = dict(loaded=True, source_present=True, as_of_known=True, is_stale=False)
    assert quote_readiness(EMP, **kw) is R.SELECTION_INVALID
    assert quote_readiness("2330", **kw) is R.SELECTION_INVALID  # type: ignore[arg-type]


@pytest.mark.parametrize("bad", [1, 0, None, "yes"])
def test_readiness_non_bool_flag_raises(bad):
    for name in ("loaded", "source_present", "as_of_known", "is_stale"):
        kw = dict(loaded=True, source_present=True, as_of_known=True, is_stale=False)
        kw[name] = bad
        with pytest.raises(TypeError):
            quote_readiness(SEL, **kw)


# ── 結構／純度守衛 ───────────────────────────────────────────────────
_HOLD_TOKENS = {"hold", "holds", "holding", "holdings", "held", "own", "owns", "owned", "owner", "ownership",
                "position", "positions", "portfolio", "持有", "持股"}


def _tokens(name: str) -> set[str]:
    return set(re.split(r"[_\W]+", name.lower()))


def test_no_holding_concept_in_structure():
    for cls in (TickerSelection, TS.TickerSelectionSet):
        for f in dataclasses.fields(cls):
            assert not (_tokens(f.name) & _HOLD_TOKENS), f.name
    assert {f.name for f in dataclasses.fields(TickerSelection)} == {"raw", "symbol", "status", "reason"}
    tree = ast.parse(SRC.read_text(encoding="utf-8"))
    names = set()
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.ClassDef)):
            names.add(n.name)
        elif isinstance(n, ast.arg):
            names.add(n.arg)
        elif isinstance(n, ast.Name):
            names.add(n.id)
        elif isinstance(n, ast.Attribute):
            names.add(n.attr)
    assert not [x for x in names if _tokens(x) & _HOLD_TOKENS]
    assert not any(_tokens(m.name) & _HOLD_TOKENS for m in itertools.chain(S, R))


_BANNED_MODS = ("streamlit", "time", "datetime", "os", "requests", "pathlib", "random", "src", "importlib",
                "subprocess", "socket", "pandas")


def _purity_violations(source: str) -> list[str]:
    tree = ast.parse(source)
    bad = []
    for n in ast.walk(tree):
        mods = []
        if isinstance(n, ast.Import):
            mods = [a.name for a in n.names]
        elif isinstance(n, ast.ImportFrom):
            if n.level:
                bad.append("relative import")
            mods = [n.module or ""]
        for m in mods:
            if m.split(".")[0] in _BANNED_MODS:
                bad.append(f"import {m}")
        if isinstance(n, ast.Name) and n.id in {"session_state", "open", "eval", "exec", "__import__"}:
            bad.append(n.id)
        if isinstance(n, ast.Attribute) and n.attr in {"session_state", "now", "today", "utcnow"}:
            bad.append(n.attr)
    return bad


def test_ast_purity_real_file():
    src = SRC.read_text(encoding="utf-8")
    assert _purity_violations(src) == []
    assert check_vm_purity(src) == []                      # 與 G2 同一支檢查器
    assert check_capability_marker_scope(src, REL) == []   # 無 DEC-124 capability marker


@pytest.mark.parametrize("inj", [
    "import streamlit as st\n", "import time\n", "from datetime import datetime\n", "import os\n",
    "import requests\n", "from src.data.core import data_loader\n", "x = st.session_state\n",
    "x = open('f')\n", "from .x import y\n", "x = d.now()\n",
])
def test_purity_guard_has_teeth(inj):
    src = SRC.read_text(encoding="utf-8")
    assert _purity_violations(inj + src)
    if "datetime" not in inj:                 # G2 只擋時鐘「呼叫」，不擋 import datetime；本檔守衛另擋
        assert check_vm_purity(inj + src)


def test_no_capability_marker_wording():
    src = SRC.read_text(encoding="utf-8")
    for w in ("NOT_PROVIDED", "TEXT_NOT_PROVIDED", "not_provided", "尚未提供"):
        assert w not in src


def test_no_new_fieldstate_and_no_partial_unknown_states():
    from shared.ui2_contract.models import FieldState
    assert {m.value for m in FieldState}.isdisjoint({m.value for m in itertools.chain(S, R)})
    assert not {"partial", "unknown"} & {m.value for m in itertools.chain(S, R)}


# ── 突變式 has-teeth：行為測試對寬鬆實作必須轉紅 ──────────────────────
def test_pattern_mutation_loosened_pattern_turns_suite_red(monkeypatch):
    """放寬 pattern（允許任意長度）→ 刻意的短代號 "50" 仍被長度分支擋；但縱深 fullmatch 檢查失效不應放行非法字元。
    這裡直接驗證：換成寬鬆 pattern 後，與 pattern 一致性斷言會偵測到差異。"""
    strict = TS.TICKER_PATTERN
    for good in ("0050", "2330", "00631L", "00980A"):
        assert strict.fullmatch(good)
    for bad in ("50", "A123", "1234567", "2330.TW", "23 30"):
        assert not strict.fullmatch(bad)
    loose = re.compile(r"[0-9A-Z.]+")
    assert any(loose.fullmatch(b) for b in ("50", "A123", "1234567", "2330.TW"))   # 寬鬆版會放行 → 測試能分辨
    monkeypatch.setattr(TS, "TICKER_PATTERN", loose)
    # 契約行為不得依賴被替換的 pattern 放行非法輸入（分支先擋）：驗證 "50" 仍 invalid，
    # 且上面「strict 對 bad 全拒、loose 放行」的斷言就是會在 pattern 被放寬時轉紅的牙齒。
    assert parse_ticker_input("50").status is S.INVALID


def test_mutation_zero_fill_would_be_caught():
    # 自製「補零」突變實作：50→0050。契約斷言必須能偵測它
    def mutant(raw):
        return TickerSelection(raw, str(raw).zfill(4), S.SELECTED, None)
    assert mutant("50").symbol == "0050"
    assert parse_ticker_input("50").symbol != mutant("50").symbol


def test_mutation_silent_dedupe_would_be_caught():
    def mutant_dedupe(raws):
        return tuple(dict.fromkeys(raws))
    real = parse_ticker_list(["2330", "0050", "2330"])
    assert real.selected == mutant_dedupe(["2330", "0050", "2330"]) and real.duplicates == ("2330",)
    assert real.duplicates != ()   # 突變（只去重、不揭露）會讓此斷言轉紅
