"""B-UI2-PUBLIC-QUOTE-VIEW-CONTRACT-1：公開股票報價畫面狀態契約（純合成、離線；數值皆虛構示例）。"""
from __future__ import annotations

import ast
import dataclasses
import itertools
import math
import pathlib
import re

import pytest

from shared.ui2_contract import quote_view as QV
from shared.ui2_contract.quote_view import QuoteViewState as V, build_quote_view, is_valid_iso_date
from shared.ui2_contract.target_selection import QuoteReadiness as R, parse_ticker_input, quote_readiness
from shared.ui2_contract.tones import ChipTone
from tests.test_ui2_guards import check_capability_marker_scope, check_vm_purity

SRC = pathlib.Path(QV.__file__)
REL = "shared/ui2_contract/quote_view.py"
GOOD = dict(loaded=True, fetch_error=None, close=188.55, trade_date="2026-11-20",
            fetched_at="2026-11-21T09:30:00+08:00", source="合成來源", is_stale=False)


def bq(sym="0050", **kw):
    a = dict(GOOD)
    a.update(kw)
    return build_quote_view(parse_ticker_input(sym), **a)


# ── 各狀態 ───────────────────────────────────────────────────────────
@pytest.mark.parametrize("sym", ["0050", "00980A", "2330", "00631L"])
def test_ok_keeps_symbol_verbatim(sym):
    v = bq(sym)
    assert v.state is V.OK and v.symbol == sym and v.fact.symbol == sym
    assert v.value_text == "188.55" and v.reason is None
    assert v.trade_date_text == "交易日 2026-11-20"
    assert v.fetched_at_text == "抓取時間 2026-11-21T09:30:00+08:00"
    assert v.source_text == "來源 合成來源"
    assert v.chip_text == "資料正常" and v.tone is ChipTone.POSITIVE


def test_leading_zero_not_numerified():
    v = bq("0050", close=50.0)
    assert v.symbol == "0050" and v.symbol != "50" and v.fact.symbol == "0050"
    assert v.value_text == "50.00"
    assert bq("50").state is V.SELECTION_INVALID           # 50 不會被補成 0050


def test_not_loaded():
    v = bq(loaded=False, close=None, trade_date=None, source=None)
    assert v.state is V.NOT_LOADED and v.value_text is None and v.tone is ChipTone.NEUTRAL_INFO


def test_fetch_failed_is_danger_and_beats_not_loaded():
    v = bq(fetch_error="timeout", loaded=False)
    assert v.state is V.FETCH_FAILED and v.reason == "fetch_failed" and v.tone is ChipTone.DANGER
    assert bq(fetch_error="").reason == QV.REASON_FETCH_FAILED and bq(fetch_error="").state is V.FETCH_FAILED


@pytest.mark.parametrize("err", [
    "line1\nline2\r\n", "x" * 5000, "token=sk-LEAKME123", "password: hunter2", "/home/user/.secrets/key.json",
    "HTTPError 401 Bearer abc.def.ghi", "C:\\Users\\a\\token.txt", "\x00\x1b[31m",
])
def test_fetch_error_text_never_leaks_into_any_output(err):
    v = bq(fetch_error=err)
    assert v.state is V.FETCH_FAILED and v.reason == "fetch_failed"
    for f in dataclasses.fields(v):
        out = getattr(v, f.name)
        if isinstance(out, str):
            for frag in ("token", "password", "hunter2", "sk-LEAKME123", "/home", "line1", "Bearer", "\x1b", "xxxxx"):
                assert frag not in out.replace("fetch_failed", ""), (f.name, frag)
            assert len(out) < 200


def test_stale_shows_last_close():
    v = bq(is_stale=True)
    assert v.state is V.STALE and v.value_text == "188.55" and v.tone is ChipTone.WARNING
    assert v.chip_text == "資料過期" and "仍顯示最後收盤" in v.notice_text
    # 同一筆過期 0050：身分、兩個日期、來源與 fact 皆與輸入一致
    assert v.symbol == "0050" and v.fact.symbol == "0050"
    assert v.trade_date_text == "交易日 2026-11-20"
    assert v.fetched_at_text == "抓取時間 2026-11-21T09:30:00+08:00"
    assert "2026-11-21" not in v.trade_date_text and "2026-11-20" not in v.fetched_at_text
    assert v.source_text == "來源 合成來源"
    assert (v.fact.trade_date, v.fact.fetched_at, v.fact.source) == (
        GOOD["trade_date"], GOOD["fetched_at"], GOOD["source"])
    # 過期分支不得以抓取日覆寫交易日；兩個日期各自出現且不同
    v2 = bq("00980A", is_stale=True, trade_date="2026-11-12", fetched_at="2026-11-21T09:30:00+08:00")
    assert v2.symbol == "00980A" and v2.fact.symbol == "00980A"
    assert v2.trade_date_text == "交易日 2026-11-12" and v2.fetched_at_text == "抓取時間 2026-11-21T09:30:00+08:00"
    assert "2026-11-21" not in v2.trade_date_text and "2026-11-12" not in v2.fetched_at_text
    assert v2.source_text == "來源 合成來源" and v2.value_text == "188.55"


@pytest.mark.parametrize("raw", ["", "   ", "x", None, 50, b"0050"])
def test_selection_invalid_or_empty(raw):
    v = build_quote_view(parse_ticker_input(raw), **GOOD)
    assert v.state is V.SELECTION_INVALID and v.value_text is None and v.symbol is None
    assert v.tone is ChipTone.NEUTRAL_INFO                 # 灰色說明，非紅色錯誤


def test_selection_invalid_foreign_object():
    v = build_quote_view("0050", **GOOD)                   # type: ignore[arg-type]
    assert v.state is V.SELECTION_INVALID


# ── 缺值 ────────────────────────────────────────────────────────────
@pytest.mark.parametrize("close", [None, 0, 0.0, -1, -0.01, math.nan, math.inf, -math.inf, True, False,
                                   "123", "188.5", b"1", [1], {"a": 1}])
def test_bad_close_is_missing_never_zero(close):
    v = bq(close=close)
    assert v.state is V.MISSING and v.value_text is None and v.fact is None
    assert v.reason in (QV.REASON_CLOSE_MISSING, QV.REASON_CLOSE_INVALID)
    assert v.chip_text == "資料未備" and "非 0" in v.notice_text


@pytest.mark.parametrize("td", ["2026-02-30", "2026/11/20", "20261120", "2026-1-2", "", " ", "2026-13-01",
                                "2026-00-10", "2026-11-00", "２０２６-１１-２０", "2026-11-20T00:00:00",
                                "2025-02-29", 20261120, b"2026-11-20"])
def test_bad_trade_date_is_missing(td):
    v = bq(trade_date=td)
    assert v.state is V.MISSING and v.reason == QV.REASON_TRADE_DATE_INVALID and v.value_text is None


@pytest.mark.parametrize("close", [10**400, -(10**400), float("1e309"), -float("1e309")])
def test_huge_close_missing_never_raises(close):
    v = bq(close=close)
    assert v.state is V.MISSING and v.reason == QV.REASON_CLOSE_INVALID and v.value_text is None


@pytest.mark.parametrize("close,ok", [
    (0.004, False), (1e-300, False), (1e308, False), (0.005, True), (0.0049999, False),
    (QV.CLOSE_DISPLAY_MAX, True), (QV.CLOSE_DISPLAY_MAX + 0.01, False), (QV.CLOSE_DISPLAY_MAX * 1.0000001, False),
    (10**7, False), (1_000_000, True), (188, True),
])
def test_display_range(close, ok):
    v = bq(close=close)
    if ok:
        assert v.state is V.OK and v.value_text not in (None, "0.00") and float(v.value_text.replace(",", "")) > 0
    else:
        assert v.state is V.MISSING and v.reason == QV.REASON_CLOSE_OUT_OF_RANGE and v.value_text is None


def test_display_range_constants():
    assert QV.CLOSE_DISPLAY_MIN == 0.005 and QV.CLOSE_DISPLAY_MAX == 1_000_000
    assert f"{QV.CLOSE_DISPLAY_MIN:.2f}" != "0.00"          # 下限本身不會被顯示成假 0


def test_iso_date_calendar_rules():
    assert is_valid_iso_date("2024-02-29") and not is_valid_iso_date("2023-02-29")
    assert is_valid_iso_date("2000-02-29") and not is_valid_iso_date("1900-02-29")
    assert is_valid_iso_date("2026-12-31") and not is_valid_iso_date("2026-04-31")


def test_future_trade_date_not_judged_no_clock():
    v = bq(trade_date="2999-01-01")
    assert v.state is V.OK                                 # 無時鐘：不判斷未來日（見 docstring）


@pytest.mark.parametrize("src", [None, "", "   ", 5])
def test_missing_source(src):
    v = bq(source=src)
    assert v.state is V.MISSING and v.reason == QV.REASON_SOURCE_MISSING


@pytest.mark.parametrize("miss", [m for n in (1, 2, 3) for m in itertools.combinations(("close", "trade_date", "source"), n)])
def test_missing_field_combinations(miss):
    v = bq(**{k: None for k in miss})
    assert v.state is V.MISSING and v.value_text is None
    expected = "+".join({"close": QV.REASON_CLOSE_MISSING, "trade_date": QV.REASON_TRADE_DATE_MISSING,
                         "source": QV.REASON_SOURCE_MISSING}[k]
                        for k in ("close", "trade_date", "source") if k in miss)
    assert v.reason == expected


def test_missing_beats_stale():
    assert bq(close=None, is_stale=True).state is V.MISSING


# ── 交易日與抓取時間分開 ─────────────────────────────────────────────
def test_only_fetched_at_without_trade_date_is_missing():
    v = bq(trade_date=None)
    assert v.state is V.MISSING and v.reason == QV.REASON_TRADE_DATE_MISSING
    assert v.trade_date_text is None                       # 不以抓取時間代填


def test_trade_date_without_fetched_at_ok_but_flagged_unknown():
    v = bq(fetched_at=None)
    assert v.state is V.OK and v.fetched_at_text == "抓取時間未知"
    assert "2026-11-20" not in v.fetched_at_text and v.fact.fetched_at is None


@pytest.mark.parametrize("fa", ["", "  ", "garbage", 123, "2026-02-30T00:00:00", "昨天", "2026-11-20T+++",
                                "2026-11-20T", "2026-11-20T25:00", "2026-11-20T10:60", "2026-11-20T10:00:61",
                                "2026-11-20T10:00+25:00", "2026-11-20T10:00+08", "2026-11-20 10", "2026-11-20Tx",
                                "2026-11-20T10:00:00Zjunk", "2026-11-20T10:00:00.", "2026-11-20\n", b"2026-11-20"])
def test_bad_fetched_at_unknown_not_echoed(fa):
    v = bq(fetched_at=fa)
    assert v.state is V.OK and v.fetched_at_text == "抓取時間未知"
    assert "+++" not in v.fetched_at_text and v.fact.fetched_at is None


@pytest.mark.parametrize("fa", ["2026-11-20", "2026-11-21T09:30", "2026-11-21 09:30:00", "2026-11-21T09:30:00.123",
                                "2026-11-21T09:30:00Z", "2026-11-21T09:30:00+08:00", "2026-11-21T23:59:59-05:30"])
def test_valid_fetched_at_formats(fa):
    v = bq(fetched_at=fa)
    assert v.fetched_at_text == f"抓取時間 {fa}" and v.fact.fetched_at == fa


@pytest.mark.parametrize("src", ["x" * 65, "a\nb", "a\tb", "\x00", "a\u3000b", "line\r"])
def test_source_invalid(src):
    v = bq(source=src)
    assert v.state is V.MISSING and v.reason == QV.REASON_SOURCE_INVALID and v.source_text is None


def test_source_length_boundary():
    assert bq(source="x" * 64).state is V.OK and bq(source="x" * 65).state is V.MISSING


def test_tone_and_chip_table_per_state():
    assert set(QV.CHIP_TONE) == set(V) == set(QV.CHIP_TEXT)
    seen = {
        V.OK: bq(), V.STALE: bq(is_stale=True), V.MISSING: bq(close=None), V.FETCH_FAILED: bq(fetch_error="e"),
        V.NOT_LOADED: bq(loaded=False), V.SELECTION_INVALID: bq("50"),
    }
    for st, v in seen.items():
        assert v.state is st and v.tone is QV.CHIP_TONE[st] and v.chip_text == QV.CHIP_TEXT[st]
        assert (v.tone is ChipTone.POSITIVE) == (st is V.OK)
    assert seen[V.MISSING].tone is ChipTone.WARNING and seen[V.STALE].tone is ChipTone.WARNING
    assert seen[V.FETCH_FAILED].tone is ChipTone.DANGER
    assert seen[V.NOT_LOADED].tone is ChipTone.NEUTRAL_INFO and seen[V.SELECTION_INVALID].tone is ChipTone.NEUTRAL_INFO


def test_trade_date_and_fetched_at_independent():
    v = bq(trade_date="2026-11-19", fetched_at="2026-11-21")
    assert "2026-11-19" in v.trade_date_text and "2026-11-21" not in v.trade_date_text
    assert "2026-11-21" in v.fetched_at_text and "2026-11-19" not in v.fetched_at_text


# ── 優先序逐層 ───────────────────────────────────────────────────────
def test_priority_layers():
    worst = dict(loaded=False, fetch_error="boom", close=None, trade_date=None, source=None, is_stale=True)
    assert bq("50", **worst).state is V.SELECTION_INVALID
    assert bq("0050", **worst).state is V.FETCH_FAILED
    worst["fetch_error"] = None
    assert bq("0050", **worst).state is V.NOT_LOADED
    worst["loaded"] = True
    assert bq("0050", **worst).state is V.MISSING
    worst.update(close=1.0, trade_date="2026-11-20", source="s")
    assert bq("0050", **worst).state is V.STALE
    worst["is_stale"] = False
    assert bq("0050", **worst).state is V.OK


def test_non_bool_flags_raise():
    for k in ("loaded", "is_stale"):
        for bad in (1, None, "yes"):
            with pytest.raises(TypeError):
                bq(**{k: bad})


# ── value-bearing 與全域不變量（窮舉格點）─────────────────────────────
_GRID = list(itertools.product(
    ["0050", "50", ""], [True, False], [None, "err"], [188.5, None, 0, math.nan, True],
    ["2026-11-20", None, "2026-02-30"], ["2026-11-21", None], ["s", None], [True, False]))


def _all():
    for sym, loaded, err, close, td, fa, src, stale in _GRID:
        yield sym, bq(sym, loaded=loaded, fetch_error=err, close=close, trade_date=td, fetched_at=fa,
                      source=src, is_stale=stale), dict(loaded=loaded, fetch_error=err, close=close, trade_date=td,
                                                         source=src, is_stale=stale)


def test_value_text_only_on_value_bearing_states_and_ok_requires_everything():
    for sym, v, a in _all():
        assert (v.value_text is not None) == (v.state in QV.VALUE_BEARING)
        assert (v.fact is not None) == (v.state in QV.VALUE_BEARING)
        if v.state is V.OK:
            assert sym == "0050" and a["loaded"] and a["fetch_error"] is None and a["close"] == 188.5
            assert a["trade_date"] == "2026-11-20" and a["source"] == "s" and not a["is_stale"]
        if v.state is not V.OK:
            assert v.state is not V.OK
        if v.value_text is not None:
            assert float(v.value_text.replace(",", "")) > 0       # 絕不顯示 0
        assert v.chip_text == QV.CHIP_TEXT[v.state] and v.tone is QV.CHIP_TONE[v.state]


def test_consistent_with_quote_readiness():
    for sym, v, a in _all():
        sel = parse_ticker_input(sym)
        src_ok = (a["fetch_error"] is None and isinstance(a["source"], str) and a["source"].strip() != ""
                  and a["close"] == 188.5)
        rd = quote_readiness(sel, loaded=a["loaded"], source_present=src_ok,
                             as_of_known=a["trade_date"] == "2026-11-20", is_stale=a["is_stale"])
        assert (v.state is V.SELECTION_INVALID) == (rd is R.SELECTION_INVALID)
        assert (v.state is V.OK) == (rd is R.READY)
        assert (v.state is V.STALE) == (rd is R.STALE)
        if v.state not in (V.OK, V.STALE):
            assert rd not in (R.READY, R.STALE)


# ── 結構／純度守衛 ───────────────────────────────────────────────────
_HOLD = {"hold", "holds", "holding", "holdings", "held", "own", "owns", "owned", "owner", "ownership",
         "position", "positions", "portfolio"}


def _tokens(name: str) -> set[str]:
    return set(re.split(r"[_\W]+", name.lower()))


def test_frozen_and_no_holding_concept():
    v = bq()
    with pytest.raises(dataclasses.FrozenInstanceError):
        v.state = V.STALE  # type: ignore[misc]
    for cls in (QV.QuoteView, QV.QuoteFact):
        assert not any(_tokens(f.name) & _HOLD for f in dataclasses.fields(cls))
    tree = ast.parse(SRC.read_text(encoding="utf-8"))
    names = {n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
    names |= {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    names |= {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    assert not [x for x in names if _tokens(x) & _HOLD]


def test_enum_values_prefixed_and_no_new_fieldstate():
    from shared.ui2_contract.models import FieldState
    vals = {m.value for m in V}
    assert all(x.startswith("quote_view_") for x in vals)
    assert vals.isdisjoint({m.value for m in FieldState}) and not {"partial", "unknown"} & vals


_BANNED = ("streamlit", "time", "datetime", "os", "requests", "pathlib", "random", "src", "importlib",
           "subprocess", "socket", "pandas")


def _purity(source: str) -> list[str]:
    bad = []
    for n in ast.walk(ast.parse(source)):
        mods = []
        if isinstance(n, ast.Import):
            mods = [a.name for a in n.names]
        elif isinstance(n, ast.ImportFrom):
            if n.level:
                bad.append("relative")
            mods = [n.module or ""]
        bad += [m for m in mods if m.split(".")[0] in _BANNED]
        if isinstance(n, ast.Name) and n.id in {"session_state", "open", "eval", "exec", "__import__"}:
            bad.append(n.id)
        if isinstance(n, ast.Attribute) and n.attr in {"session_state", "now", "today", "utcnow"}:
            bad.append(n.attr)
    return bad


def test_ast_purity_real_file():
    src = SRC.read_text(encoding="utf-8")
    assert _purity(src) == [] and check_vm_purity(src) == [] and check_capability_marker_scope(src, REL) == []
    for w in ("NOT_PROVIDED", "not_provided", "尚未提供"):
        assert w not in src


@pytest.mark.parametrize("inj", ["import streamlit as st\n", "import time\n", "from datetime import datetime\n",
                                 "import os\n", "import requests\n", "from src.data.core import x\n",
                                 "x = st.session_state\n", "x = open('f')\n", "from .x import y\n", "x = d.now()\n"])
def test_purity_guard_has_teeth(inj):
    src = SRC.read_text(encoding="utf-8")
    assert _purity(inj + src)
    if "datetime" not in inj:
        assert check_vm_purity(inj + src)


# ── 突變式 has-teeth：以突變版 builder 跑同一組不變量，必須被抓到 ───────────
def _invariant_violations(builder) -> list[str]:
    """與上方核心斷言同義的可重用檢查器；對真實作須空、對突變須非空。"""
    bad = []
    s = parse_ticker_input("0050")
    kw = dict(GOOD)
    cases = [
        ("zero_close", dict(close=0), V.MISSING),
        ("missing_close", dict(close=None), V.MISSING),
        ("nan_close", dict(close=math.nan), V.MISSING),
        ("missing_source", dict(source=None), V.MISSING),
        ("no_trade_date", dict(trade_date=None), V.MISSING),
        ("bad_trade_date", dict(trade_date="2026-02-30"), V.MISSING),
        ("not_loaded", dict(loaded=False), V.NOT_LOADED),
        ("fetch_before_loaded", dict(loaded=False, fetch_error="e"), V.FETCH_FAILED),
        ("stale", dict(is_stale=True), V.STALE),
        ("missing_beats_stale", dict(is_stale=True, close=None), V.MISSING),
    ]
    for name, over, want in cases:
        v = builder(s, **{**kw, **over})
        if v.state is not want:
            bad.append(f"{name}: {v.state}")
        if v.state not in QV.VALUE_BEARING and v.value_text is not None:
            bad.append(f"{name}: value_text 洩漏")
    v = builder(s, **{**kw, "fetched_at": None})
    if v.state is V.OK and ("2026-11-20" in (v.fetched_at_text or "")):
        bad.append("fetched_at 以交易日代填")
    if v.fetched_at_text != "抓取時間未知":
        bad.append("fetched_at 未標未知")
    return bad


def test_invariant_checker_clean_on_real_impl():
    assert _invariant_violations(build_quote_view) == []


def _mut_zero_fill(sel, **kw):                            # 缺收盤價時補 0 並當作 OK
    if kw["close"] is None:
        return dataclasses.replace(build_quote_view(sel, **{**kw, "close": 1.0}), value_text="0.00")
    return build_quote_view(sel, **kw)


def _mut_missing_returns_ok(sel, **kw):
    v = build_quote_view(sel, **kw)
    if v.state is V.MISSING:
        return dataclasses.replace(v, state=V.OK, value_text="0.00", chip_text="資料正常")
    return v


def _mut_trade_date_filled_by_fetched_at(sel, **kw):
    if kw["trade_date"] is None:
        kw = {**kw, "trade_date": str(kw["fetched_at"])[:10]}
    return build_quote_view(sel, **kw)


def _mut_fetched_at_filled_by_trade_date(sel, **kw):
    v = build_quote_view(sel, **kw)
    if v.fetched_at_text == "抓取時間未知":
        return dataclasses.replace(v, fetched_at_text=f"抓取時間 {kw['trade_date']}")
    return v


def _mut_priority_swapped(sel, **kw):                     # 未載入排在讀取失敗之前
    if not kw["loaded"]:
        return build_quote_view(sel, **{**kw, "fetch_error": None})
    return build_quote_view(sel, **kw)


def _mut_stale_before_missing(sel, **kw):
    if kw["is_stale"]:
        return dataclasses.replace(build_quote_view(sel, **{**kw, "close": 1.0, "trade_date": "2026-11-20",
                                                              "source": "s"}))
    return build_quote_view(sel, **kw)


def _mut_value_on_not_loaded(sel, **kw):
    v = build_quote_view(sel, **kw)
    return dataclasses.replace(v, value_text="1.00") if v.state is V.NOT_LOADED else v


@pytest.mark.parametrize("mut", [_mut_zero_fill, _mut_missing_returns_ok, _mut_trade_date_filled_by_fetched_at,
                                 _mut_fetched_at_filled_by_trade_date, _mut_priority_swapped,
                                 _mut_stale_before_missing, _mut_value_on_not_loaded])
def test_mutants_are_caught(mut):
    assert _invariant_violations(mut), f"突變沒被抓到：{mut.__name__}"
