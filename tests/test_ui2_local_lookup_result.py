"""即時查一檔結果區 VM（`shared/ui2_contract/local_lookup_result.py`）與 HTML（`local_lookup_result_html`）。

純合成、離線；數值皆虛構示例。本批未接線，無 production caller。
"""
from __future__ import annotations

import ast
import dataclasses
import math
import pathlib
import re

import pytest

from shared.ui2_contract import local_lookup_result as LL
from shared.ui2_contract.local_lookup_result import build_local_lookup_result as build
from shared.ui2_contract.quote_view import QuoteViewState as V, build_quote_view
from shared.ui2_contract.target_selection import parse_ticker_input
from shared.ui2_contract.tones import ChipTone
from src.ui2.components import html as H
from tests.test_ui2_guards import check_capability_marker_scope, check_vm_purity
from tests.test_ui2_p1_human_text import ENGINEERING_VOCAB, hits_in

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = pathlib.Path(LL.__file__)
REL = "shared/ui2_contract/local_lookup_result.py"

QGOOD = dict(loaded=True, fetch_error=None, close=188.55, trade_date="2026-11-20",
             fetched_at="2026-11-21T09:30:00+08:00", source="合成來源", is_stale=False)
IGOOD = dict(open_=187.0, high=190.0, low=186.0, close=188.55, volume=1234567.0, as_of="2026-11-20",
             ma20=180.1, ma240=170.5, bias20_pct=4.7, vol_ratio5=1.23, support=179.0, resistance=195.0,
             support_resistance_bars=20)


def q(sym="0050", **kw):
    a = dict(QGOOD)
    a.update(kw)
    return build_quote_view(parse_ticker_input(sym), **a)


def vm(quote=None, **kw):
    a = dict(IGOOD)
    a.update(kw)
    return build(quote if quote is not None else q(), **a)


def cell(v, key):
    return next(c for c in (*v.ohlcv, *v.indicators) if c.key == key)


# ── 六態 ─────────────────────────────────────────────────────────────
def test_ok_full_data():
    v = vm()
    assert v.state is V.OK and v.has_data and v.symbol == "0050" and v.tone is ChipTone.POSITIVE
    assert v.close_text == "188.55" and v.as_of_text == "資料日 2026-11-20"
    assert v.fetched_at_text == "抓取時間 2026-11-21T09:30:00+08:00"
    assert v.source_text == f"來源 合成來源｜{LL.TEXT_SOURCE_USER_DECLARED}"
    assert [c.key for c in v.ohlcv] == list(LL.OHLCV_KEYS)
    assert [c.key for c in v.indicators] == list(LL.INDICATOR_KEYS)
    assert not any(c.is_missing for c in (*v.ohlcv, *v.indicators))
    assert [c.value_text for c in v.ohlcv] == ["187.00", "190.00", "186.00", "188.55", "1,234,567"]
    assert [c.value_text for c in v.indicators] == ["180.10", "170.50", "+4.70%", "1.23 倍", "179.00", "195.00"]
    assert v.notes == (LL.TEXT_LIMIT_UNADJUSTED, LL.TEXT_LIMIT_NOT_REALTIME)
    assert v.research_text == "🤖 研究解釋：尚未啟用 ⬜"


def test_stale_shows_data_with_warning_chip():
    v = vm(q(is_stale=True))
    assert v.state is V.STALE and v.has_data and v.tone is ChipTone.WARNING
    assert v.chip_text == "資料過期" and "仍顯示最後收盤" in v.notice_text and v.close_text == "188.55"


@pytest.mark.parametrize("quote,state,tone", [
    (q(loaded=False), V.NOT_LOADED, ChipTone.NEUTRAL_INFO),
    (q("50"), V.SELECTION_INVALID, ChipTone.NEUTRAL_INFO),
    (q(fetch_error="boom"), V.FETCH_FAILED, ChipTone.DANGER),
    (q(close=None), V.MISSING, ChipTone.WARNING),
])
def test_non_data_states_show_no_numbers(quote, state, tone):
    v = vm(quote)
    assert v.state is state and v.tone is tone and not v.has_data
    assert v.close_text is None and v.as_of_text is None and v.fetched_at_text is None and v.source_text is None
    assert v.ohlcv == () and v.indicators == () and v.notes == ()
    assert v.chip_text == quote.chip_text and v.notice_text == quote.notice_text
    assert v.research_text == LL.TEXT_RESEARCH_DISABLED


def test_only_fetch_failed_is_danger():
    quotes = {V.OK: q(), V.STALE: q(is_stale=True), V.NOT_LOADED: q(loaded=False), V.SELECTION_INVALID: q("x"),
              V.MISSING: q(close=None), V.FETCH_FAILED: q(fetch_error="e")}
    assert {s: vm(x).tone is ChipTone.DANGER for s, x in quotes.items()} == {
        s: s is V.FETCH_FAILED for s in V}


def test_selection_invalid_does_not_echo_input():
    v = vm(q("<script>alert(1)</script>"))
    assert v.state is V.SELECTION_INVALID and v.symbol is None


# ── 缺值：全缺、真 0 ≠ 缺值 ────────────────────────────────────────────
ALL_NONE = dict(open_=None, high=None, low=None, close=None, volume=None, ma20=None, ma240=None,
                bias20_pct=None, vol_ratio5=None, support=None, resistance=None)


def test_all_missing_cells_use_missing_text_never_zero():
    v = vm(**ALL_NONE)
    for c in (*v.ohlcv, *v.indicators):
        if c.key == "close":                      # 收盤與價格區同源（quote），不因參數缺而缺
            assert not c.is_missing and c.value_text == "188.55"
            continue
        assert c.is_missing and c.value_text == LL.TEXT_MISSING == "⬜ 資料未備", c
        assert re.search(r"\d", c.value_text) is None


def test_true_zero_volume_is_not_missing():
    v = vm(volume=0)
    c = cell(v, "volume")
    assert c.value_text == "0" and not c.is_missing
    assert c.value_text != cell(vm(volume=None), "volume").value_text      # 真 0 與缺值可區分
    assert cell(vm(volume=None), "volume").is_missing


def test_true_zero_vol_ratio_and_bias_not_missing():
    v = vm(vol_ratio5=0.0, bias20_pct=0.0)
    assert cell(v, "vol_ratio5").value_text == "0.00 倍" and not cell(v, "vol_ratio5").is_missing
    assert cell(v, "bias20").value_text == "0.00%" and not cell(v, "bias20").is_missing


def test_tiny_negative_bias_has_no_negative_zero():
    assert cell(vm(bias20_pct=-0.001), "bias20").value_text == "0.00%"
    assert cell(vm(bias20_pct=-3.456), "bias20").value_text == "-3.46%"


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf, True, False, "187", b"1", [1], {"a": 1}, 10**400,
                                 -(10**400), 0, 0.0, -1.0, 0.004, 1_000_000.01])
def test_bad_price_inputs_become_missing_not_zero(bad):
    v = vm(open_=bad, high=bad, low=bad, ma20=bad, ma240=bad, support=bad, resistance=bad)
    for k in ("open", "high", "low", "ma20", "ma240", "support", "resistance"):
        c = cell(v, k)
        assert c.is_missing and c.value_text == LL.TEXT_MISSING, (k, bad)


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf, True, False, "5", None, -0.5, 10**400, 1e16])
def test_bad_volume_and_ratio_become_missing(bad):
    v = vm(volume=bad, vol_ratio5=bad)
    assert cell(v, "volume").is_missing and cell(v, "vol_ratio5").is_missing


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf, True, "1", None, 1000.01, -1000.01, 10**400])
def test_bad_bias_becomes_missing(bad):
    assert cell(vm(bias20_pct=bad), "bias20").is_missing


def test_numpy_scalars():
    import numpy as np
    v = vm(open_=np.float64(187.0), high=np.int64(190), low=np.bool_(True), ma20=np.float64("nan"), volume=np.int64(5))
    assert cell(v, "open").value_text == "187.00" and cell(v, "high").value_text == "190.00"
    assert cell(v, "low").is_missing and cell(v, "ma20").is_missing and cell(v, "volume").value_text == "5"


def test_missing_cell_does_not_hide_neighbours():
    v = vm(ma240=None)
    assert cell(v, "ma240").is_missing and not cell(v, "ma20").is_missing and cell(v, "ma20").value_text == "180.10"


def test_int_inputs_and_non_integer_volume():
    v = vm(open_=187, volume=12)
    assert cell(v, "open").value_text == "187.00" and cell(v, "volume").value_text == "12"
    assert cell(vm(volume=1234.5), "volume").value_text == "1,234.50"


def test_volume_has_no_unit_label():
    v = vm()
    blob = " ".join(c.label + c.value_text for c in v.ohlcv)
    assert "股" not in blob and "張" not in blob
    page = H.local_lookup_result_html(v)
    assert "股" not in page and "張" not in page


# ── 取得日缺失 ───────────────────────────────────────────────────────
@pytest.mark.parametrize("fa", [None, "", "garbage", 123, "2026-02-30T00:00:00"])
def test_missing_fetched_at_is_unknown_not_replaced(fa):
    v = vm(q(fetched_at=fa))
    assert v.state is V.OK and v.fetched_at_text == "抓取時間未知"
    assert "2026-11-20" not in v.fetched_at_text
    assert "抓取時間未知" in H.local_lookup_result_html(v)


# ── 支撐壓力窗口標籤 ─────────────────────────────────────────────────
@pytest.mark.parametrize("bars,label", [(20, "（近20日）"), (7, "（近7根日K）"), (None, ""), (0, ""), (True, ""), ("20", "")])
def test_support_resistance_label_honest(bars, label):
    v = vm(support_resistance_bars=bars)
    assert cell(v, "support").label == f"支撐{label}" and cell(v, "resistance").label == f"壓力{label}"


# ── 來源註記 ─────────────────────────────────────────────────────────
def test_source_flag_false_drops_label_true_keeps_it():
    assert LL.TEXT_SOURCE_USER_DECLARED not in vm(source_user_declared=False).source_text
    assert LL.TEXT_SOURCE_USER_DECLARED in vm().source_text


# ── fail loud：矛盾輸入 ──────────────────────────────────────────────
def test_as_of_mismatch_raises_and_none_is_allowed():
    with pytest.raises(ValueError, match="as_of_mismatch"):
        vm(as_of="2026-11-19")
    assert vm(as_of=None).has_data


def test_close_mismatch_raises():
    with pytest.raises(ValueError, match="close_mismatch"):
        vm(close=100.0)
    assert vm(close=None).has_data and vm(close=math.nan).has_data


@pytest.mark.parametrize("kw", [dict(high=185.0, low=186.0), dict(open_=200.0), dict(open_=100.0),
                                dict(low=189.0, high=191.0)])
def test_inconsistent_ohlc_raises(kw):
    with pytest.raises(ValueError, match="ohlc_inconsistent"):
        vm(**kw)


def test_bad_types_raise():
    with pytest.raises(TypeError):
        build("0050", **IGOOD)                                # type: ignore[arg-type]
    with pytest.raises(TypeError):
        vm(source_user_declared=1)                            # type: ignore[arg-type]


def test_non_data_state_ignores_inconsistent_numbers():
    assert not vm(q(loaded=False), as_of="1999-01-01", close=1.0, high=1.0, low=2.0).has_data


# ── HTML ─────────────────────────────────────────────────────────────
def test_html_contains_required_text_and_structure():
    h = H.local_lookup_result_html(vm())
    for s in ("188.55", "資料日 2026-11-20", "抓取時間 2026-11-21T09:30:00+08:00", "來源 合成來源",
              LL.TEXT_SOURCE_USER_DECLARED, LL.TEXT_LIMIT_UNADJUSTED, LL.TEXT_LIMIT_NOT_REALTIME,
              LL.TEXT_RESEARCH_DISABLED, "資料正常", "MA20", "MA240", "乖離20", "量比5", "支撐", "壓力", "1,234,567"):
        assert s in h, s
    assert "ui2-ll__col--left" in h and "ui2-ll__col--right" in h and "ui2-ll__cols" in h
    assert h.index("ui2-ll__col--left") < h.index("ui2-ll__col--right")
    left, right = h.split("ui2-ll__col--right")
    assert "data-ll-block=\"ohlcv\"" in left and "data-ll-block=\"source\"" in left
    assert "data-ll-block=\"indicators\"" in right and "data-ll-block=\"notes\"" in right
    assert "\n" not in h


def test_html_missing_cells_show_missing_text_with_flag():
    h = H.local_lookup_result_html(vm(**ALL_NONE))
    assert h.count(LL.TEXT_MISSING) == 10                     # 11 格缺 → 收盤不缺（quote 同源）
    assert h.count('data-ll-missing="1"') == 10
    h0 = H.local_lookup_result_html(vm(volume=0))
    assert 'data-ll-key="volume" data-ll-missing="0"><span class="ui2-ll__k">量</span><span class="ui2-ll__v">0</span>' in h0


@pytest.mark.parametrize("quote", [q(loaded=False), q("x"), q(fetch_error="e"), q(close=None)])
def test_html_non_data_states_only_status_and_research(quote):
    h = H.local_lookup_result_html(vm(quote))
    assert "ui2-ll__cols" not in h and "data-ll-key" not in h and 'data-ll-has-data="0"' in h
    assert quote.chip_text in h and LL.TEXT_RESEARCH_DISABLED in h
    assert LL.TEXT_MISSING not in h or quote.state is V.MISSING     # 「⬜ 資料未備」只可能來自 chip 說明，不是一排缺值格


def test_html_danger_class_only_for_fetch_failed():
    assert "ui2-chip--danger" in H.local_lookup_result_html(vm(q(fetch_error="e")))
    for quote in (q(), q(loaded=False), q("x"), q(close=None), q(is_stale=True)):
        assert "ui2-chip--danger" not in H.local_lookup_result_html(vm(quote))


def test_html_escapes_dynamic_strings():
    evil = '<img src=x onerror=alert(1)>"&'
    quote = q(source=evil)
    h = H.local_lookup_result_html(vm(quote))
    assert "<img" not in h and "onerror=alert(1)>" not in h and "&lt;img" in h and "&amp;" in h
    forged = dataclasses.replace(vm(), symbol="<b>x</b>", notice_text="<i>n</i>", close_text="<u>1</u>",
                                 fetched_at_text="<s>f</s>", research_text="<em>r</em>",
                                 ohlcv=(LL.LocalLookupCell("o<", "<l>", "<v>", True),), indicators=(),
                                 notes=("<n>",))
    h2 = H.local_lookup_result_html(forged)
    for tag in ("<b>", "<i>", "<u>", "<s>", "<em>", "<l>", "<v>", "<n>"):
        assert tag not in h2, tag
    assert "&lt;b&gt;x&lt;/b&gt;" in h2


def test_html_no_expander_no_interactive_no_chart():
    h = H.local_lookup_result_html(vm())
    for bad in ("<details", "<summary", "<button", "<input", "<svg", "<canvas", "<img", "<a ", "<script", "expander"):
        assert bad not in h, bad


def test_html_has_responsive_css_two_columns_at_desktop():
    css = H.LOCAL_LOOKUP_RESULT_CSS
    assert "min-width:769px" in css and ".ui2-ll__cols" in css and "repeat(2" in css
    assert "<" not in css and "expander" not in css


# ── 禁用字樣／工程詞 ─────────────────────────────────────────────────
_FORBIDDEN = ("查無此股", "買進", "賣出", "加碼", "減碼", "全出", "強烈出場", "建議", "今日無需調整")


def _all_vms():
    quotes = [q(), q(is_stale=True), q(loaded=False), q("x"), q(fetch_error="e"), q(close=None), q(fetched_at=None)]
    out = [vm(x) for x in quotes] + [vm(**ALL_NONE), vm(volume=0), vm(source_user_declared=False)]
    return out


def test_no_forbidden_or_engineering_text_in_vm_and_html():
    for v in _all_vms():
        blob = H.local_lookup_result_html(v) + "\n" + "\n".join(
            [v.chip_text, v.notice_text or "", v.close_text or "", v.as_of_text or "", v.fetched_at_text or "",
             v.source_text or "", v.research_text, *v.notes, *(f"{c.label}{c.value_text}" for c in (*v.ohlcv, *v.indicators))])
        for w in _FORBIDDEN:
            assert w not in blob, w
        # 去掉 HTML 的 class／屬性名後掃工程詞（屬性名如 data-ui2-l1 不是畫面文字）
        visible = re.sub(r"<[^>]*>", " ", blob)
        assert hits_in(visible) == [], hits_in(visible)
        assert [w for w in ENGINEERING_VOCAB if w in visible] == []
    for const in (LL.TEXT_LIMIT_UNADJUSTED, LL.TEXT_LIMIT_NOT_REALTIME, LL.TEXT_SOURCE_USER_DECLARED,
                  LL.TEXT_RESEARCH_DISABLED):
        assert hits_in(const) == []


def test_research_text_is_fixed_string_not_l2_content():
    assert {v.research_text for v in _all_vms()} == {"🤖 研究解釋：尚未啟用 ⬜"}


# ── 純度：無 session_state／無時鐘／無 I/O／無禁用 import ─────────────────
def test_module_purity_and_scope_guards():
    src = SRC.read_text(encoding="utf-8")
    assert check_vm_purity(src) == []
    assert check_capability_marker_scope(src, REL) == []
    assert "session_state" not in src
    tree = ast.parse(src)
    mods = {n.module if isinstance(n, ast.ImportFrom) else a.name
            for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))
            for a in (n.names if isinstance(n, ast.Import) else [n])}
    assert not any(m and (m.split(".")[0] in {"streamlit", "datetime", "time", "src", "os", "pathlib", "requests"})
                   for m in mods), mods
    assert not any(isinstance(n, ast.Attribute) and n.attr in {"now", "utcnow", "today"} for n in ast.walk(tree))


def test_html_function_has_no_session_state_or_clock():
    src = (ROOT / "src/ui2/components/html.py").read_text(encoding="utf-8")
    fn = next(n for n in ast.parse(src).body if isinstance(n, ast.FunctionDef) and n.name == "local_lookup_result_html")
    seg = ast.get_source_segment(src, fn)
    assert "session_state" not in seg and "datetime" not in seg and "time." not in seg


def test_vm_is_frozen_and_deterministic():
    v = vm()
    with pytest.raises(dataclasses.FrozenInstanceError):
        v.close_text = "0.00"                                  # type: ignore[misc]
    assert vm() == vm() and H.local_lookup_result_html(vm()) == H.local_lookup_result_html(vm())
