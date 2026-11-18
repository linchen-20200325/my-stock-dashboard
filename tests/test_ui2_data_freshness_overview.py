"""🗂 資料新鮮度總覽首屏（DEC-177；使用者 2026-11-18 核准方案 C／Q1=A／D-5）。

純函式測試（無 streamlit 執行期／網路／時鐘）。本檔鎖定：
1. 計數導出規則（只來自既有台股卡／位階 spec；#1206 的未來日／契約違反自動沿用；a+b+c+d+e+n=K）；
2. Q1=A 補償控制（D-4）：`WIRED_PATHS` 對 allowlist 內路徑整個放行，所以四列的「路徑＋key＋label＋形狀＋核准 detail」在此精確鎖定；
3. 僅 Real 軸有摘要，FAKE 軸不冒稱；
4. 其餘路徑／其他頁／同路徑非法形狀仍被擋（反向注入）；
5. D-5：降級頁「未評估」守衛的精確局部例外。
"""
from __future__ import annotations

import dataclasses
import re

import pytest

from shared import regime_arbiter as RA
from shared.ui2_contract.models import CapabilityState, FieldState, FieldVM, FreshnessInfo, JudgementState, PageVM
from shared.ui2_contract.pages import P4_DATA, P4_HOLD, P4_MARKET, P4_ME, P4_TARGET
from src.services.ui2 import data_page as DP
from src.services.ui2.preview_feed import get_preview_page_vm
from src.services.ui2.real_canonical import (
    CONTRACT_ERROR, FUTURE_AS_OF_ERROR, RealFeedContractError, RealFeedSnapshot, RegimeFact, TwiiFact,
    freshness_states, get_real_page_vm, item_state_of_spec,
)
from tests import test_ui2_real_feed as RF


# ── fixtures ────────────────────────────────────────────────────────
def twii(**kw) -> TwiiFact:
    base = dict(ok=True, close=(23456.78,), as_of="2026-11-13", is_stale=False, stale_reason="", age_days=0,
                has_upstream_error=False, error_type="", failed=False, source="TWII", upstream_state="")
    base.update(kw)
    return TwiiFact(**base)


def regime(kind: str) -> RegimeFact:
    return {
        "unloaded": RegimeFact("unknown", "gray", RA.SOURCE_UNLOADED, False),
        "breadth": RegimeFact("unknown", "gray", RA.SOURCE_UNEVALUATED_BREADTH, False),
        "bull": RegimeFact("bull", "green", RA.SOURCE_BULL_SCORE, True),
    }[kind]


def snap(t=None, t_err="", r=None, r_err="") -> RealFeedSnapshot:
    return RealFeedSnapshot.of(t, t_err, r, r_err)


def counts(s: RealFeedSnapshot) -> DP.FreshnessCounts:
    return DP.counts_from_states(freshness_states(s))


def rows(s: RealFeedSnapshot) -> list[FieldVM]:
    return list(get_real_page_vm(P4_DATA, s).context.first_screen.context_rows)


TWII_COMBOS = {
    "fresh": (twii(), ""), "stale": (twii(is_stale=True, age_days=5), ""),
    "stale_none": (twii(is_stale=None, age_days=None), ""), "no_date": (twii(as_of=None), ""),
    "missing": (twii(ok=False, close=(), as_of=None, is_stale=None), ""),
    "failed": (twii(ok=False, close=(), as_of=None, failed=True, error_type="OSError"), ""),
    "future": (None, FUTURE_AS_OF_ERROR), "contract": (None, CONTRACT_ERROR), "exception": (None, "OSError"),
}
REGIME_COMBOS = {"unloaded": (regime("unloaded"), ""), "breadth": (regime("breadth"), ""),
                 "bull": (regime("bull"), ""), "exception": (None, "OSError"), "contract": (None, CONTRACT_ERROR)}
ALL_SNAPS = {f"{tn}|{rn}": snap(t, te, r, re_) for tn, (t, te) in TWII_COMBOS.items()
             for rn, (r, re_) in REGIME_COMBOS.items()}


# ── 六種輸入情境（Q5＋#1206）─────────────────────────────────────────
def test_all_missing():
    c = counts(snap(twii(ok=False, close=(), as_of=None, is_stale=None), "", regime("bull")))
    assert (c.total, c.wired, c.not_provided) == (8, 2, 6)
    assert (c.in_rule, c.stale, c.missing, c.unavailable, c.not_evaluated, c.undeterminable) == (0, 0, 2, 0, 0, 0)


def test_loaded_without_a_date_is_missing_not_in_rule():
    c = counts(snap(twii(as_of=None), "", regime("bull")))
    assert (c.in_rule, c.missing) == (0, 2)


def test_stale_and_unknown_freshness_both_count_as_stale_never_ok():
    assert counts(snap(twii(is_stale=True, age_days=5), "", regime("unloaded"))).stale == 1
    c = counts(snap(twii(is_stale=None, age_days=None), "", regime("unloaded")))
    assert c.stale == 1 and c.in_rule == 0


@pytest.mark.parametrize("err", [FUTURE_AS_OF_ERROR, CONTRACT_ERROR, "OSError", "Exception"])
def test_future_format_error_and_exceptions_follow_the_card_unavailable(err):
    c = counts(snap(None, err, regime("unloaded")))
    assert (c.unavailable, c.in_rule, c.missing, c.stale) == (1, 0, 0, 0) and c.not_evaluated == 1


def test_a_future_fact_that_bypasses_the_feed_fails_loud_like_the_card():
    with pytest.raises(RealFeedContractError):
        freshness_states(snap(twii(as_of="2026-11-20", as_of_future=True), "", regime("unloaded")))


def test_mixed_with_undeterminable_is_reported_separately():
    s = snap(twii(is_stale=True, age_days=3), "", regime("breadth"))
    c = counts(s)
    assert (c.stale, c.undeterminable) == (1, 1) and c.in_rule == c.missing == c.unavailable == c.not_evaluated == 0
    r = rows(s)
    assert r[3].detail == DP.FRESHNESS_DISCLAIMER + "　另有 1 項判定結果為無法判定，不計入上列"
    assert r[2].value_text == "資料日在規則內 0 項｜⚠ 過期或可能已過期 1 項｜⬜ 資料未備 0 項"


# ── 免責句字面釘死（QA #1211：不得與 DP.FRESHNESS_DISCLAIMER 自比）──────
_DISCLAIMER_LITERAL = "資料日在規則內只表示資料日未超過規則，不是買賣訊號。"
_NSENTENCE_RE = re.compile(r"^　另有 ([1-9]\d*) 項判定結果為無法判定，不計入上列$")


def _assert_row4_literal(s: RealFeedSnapshot) -> None:
    n = counts(s).undeterminable
    detail = rows(s)[3].detail
    if n == 0:
        assert detail == _DISCLAIMER_LITERAL
        assert "另有" not in detail and "無法判定" not in detail
    else:
        assert detail == _DISCLAIMER_LITERAL + f"　另有 {n} 項判定結果為無法判定，不計入上列"


def test_disclaimer_literal_is_row4_detail_of_real_page():
    s = snap(twii(), "", regime("unloaded"))
    assert counts(s).undeterminable == 0
    assert rows(s)[3].detail == "資料日在規則內只表示資料日未超過規則，不是買賣訊號。"


def test_n_sentence_literal_with_fullwidth_space_when_n_positive():
    s = snap(twii(is_stale=True, age_days=3), "", regime("breadth"))
    n = counts(s).undeterminable
    assert n > 0
    detail = rows(s)[3].detail
    assert detail.startswith(_DISCLAIMER_LITERAL)
    tail = detail[len(_DISCLAIMER_LITERAL):]
    assert tail[0] == "\u3000" and " " not in _DISCLAIMER_LITERAL + tail[:1]
    m = _NSENTENCE_RE.match(tail)
    assert m and int(m.group(1)) == n
    assert detail == f"資料日在規則內只表示資料日未超過規則，不是買賣訊號。　另有 {n} 項判定結果為無法判定，不計入上列"


def test_n_sentence_absent_when_n_zero():
    s = snap(twii(), "", regime("bull"))
    assert counts(s).undeterminable == 0
    assert rows(s)[3].detail == _DISCLAIMER_LITERAL


@pytest.mark.parametrize("key", list(ALL_SNAPS))
def test_row4_literal_holds_on_every_real_combination(key):
    _assert_row4_literal(ALL_SNAPS[key])


def test_rewording_the_constant_turns_the_literal_pin_red(monkeypatch):
    s = snap(twii(is_stale=True, age_days=3), "", regime("breadth"))
    _assert_row4_literal(s)  # baseline green
    monkeypatch.setattr(DP, "FRESHNESS_DISCLAIMER", "資料日在規則內表示未超過規則，不是買賣訊號。")
    with pytest.raises(AssertionError):
        _assert_row4_literal(s)
    with pytest.raises(AssertionError):
        _assert_row4_literal(snap(twii(), "", regime("bull")))
    monkeypatch.setattr(DP, "FRESHNESS_UNDETERMINABLE_FMT", "另有 {n} 項無法判定")
    with pytest.raises(AssertionError):
        _assert_row4_literal(s)


def test_fake_axis_has_no_summary_and_keeps_honest_copy():
    for sc in ("cold", "loaded", "stale", "unavailable", "missing", "not_evaluated"):
        vm = get_preview_page_vm(P4_DATA, sc)
        assert vm.context.first_screen.context_rows == ()
        blob = repr(vm)
        assert "固定清單" not in blob and "資料新鮮度總覽" not in blob and "接入狀態" not in blob
        fs = vm.context.first_screen
        assert fs.current_state.detail == DP.R_DATA_NOT_WIRED          # 原文案，不冒稱「本頁先顯示摘要」
        assert fs.next_step.detail == "資料健康度清單開放後才可查看"
        assert fs.primary_cta.disabled_reason == "資料健康度尚未開放"


# ── 導出規則本身 ────────────────────────────────────────────────────
@pytest.mark.parametrize("spec, want", [
    ({"state": "unavailable"}, DP.S_UNAVAILABLE), ({"state": "not_evaluated"}, DP.S_NOT_EVALUATED),
    ({"state": "undeterminable"}, DP.S_UNDETERMINABLE), ({"state": "stale", "value": "1", "as_of": None}, DP.S_STALE),
    ({"state": None, "value": None, "as_of": "2026-11-13"}, DP.S_MISSING),
    ({"state": None, "value": "1", "as_of": None}, DP.S_MISSING),
    ({"state": None, "value": "1", "as_of": "2026-11-13"}, DP.S_IN_RULE),
])
def test_item_state_of_spec(spec, want):
    assert item_state_of_spec(spec) == want


def test_unknown_spec_state_is_rejected_not_defaulted():
    with pytest.raises(ValueError):
        item_state_of_spec({"state": "weird", "value": "1", "as_of": "2026-11-13"})


def test_n_and_k_come_from_the_list_and_unwired_never_enter_states():
    assert len(DP.FRESHNESS_ITEMS) == DP.FRESHNESS_N == 8 and DP.WIRED_ITEM_KEYS == {"twii", "regime"}
    assert set(freshness_states(snap(twii(), "", regime("unloaded")))) == DP.WIRED_ITEM_KEYS
    with pytest.raises(ValueError):
        DP.counts_from_states({"twii": DP.S_IN_RULE})
    with pytest.raises(ValueError):
        DP.counts_from_states({"twii": DP.S_IN_RULE, "regime": DP.S_IN_RULE, "pmi": DP.S_IN_RULE})
    with pytest.raises(ValueError):
        DP.counts_from_states({"twii": "ok", "regime": DP.S_IN_RULE})
    with pytest.raises(ValueError):
        DP.FreshnessCounts(8, 2, 1, 0, 0, 0, 0, 0)


# ── 獨立算式：由「卡片／位階欄位本身（VM）」另算一次，與四列比對（a+b+c+d+e+n=K）──────────
def _independent_counts(s: RealFeedSnapshot) -> dict[str, int]:
    vm = get_real_page_vm(P4_MARKET, s)
    tw = next(c.field for c in vm.context.cards if c.card_id == "twii")
    rg = vm.context.first_screen.current_state
    out = dict(a=0, b=0, c=0, d=0, e=0, n=0)
    if tw.state is FieldState.UNAVAILABLE:
        out["d"] += 1
    elif tw.state is FieldState.STALE:
        out["b"] += 1
    elif tw.state is FieldState.MISSING or tw.freshness.as_of is None:
        out["c"] += 1
    else:
        out["a"] += 1
    if rg.state is FieldState.UNAVAILABLE:
        out["d"] += 1
    elif rg.state is FieldState.NOT_EVALUATED:
        out["e"] += 1
    elif rg.state is JudgementState.UNDETERMINABLE:
        out["n"] += 1
    else:                                     # 已載入：位階契約沒有 as_of → 資料未備
        assert rg.state is FieldState.OK and rg.freshness.as_of is None
        out["c"] += 1
    return out


_NUMS = re.compile(r"(\d+) 項")


def _parse(s: RealFeedSnapshot) -> dict[str, int]:
    r = rows(s)
    n_line = re.search(r"另有 (\d+) 項", r[3].detail or "")
    a, b, c = (int(x) for x in _NUMS.findall(r[2].value_text))
    d, e = (int(x) for x in _NUMS.findall(r[3].value_text))
    return dict(total=int(_NUMS.findall(r[0].value_text)[0]), k=int(_NUMS.findall(r[1].value_text)[0]),
                np=int(_NUMS.findall(r[1].value_text)[1]), a=a, b=b, c=c, d=d, e=e, n=int(n_line.group(1)) if n_line else 0)


@pytest.mark.parametrize("key", sorted(ALL_SNAPS))
def test_rows_arithmetic_matches_the_two_existing_facts(key):
    p = _parse(ALL_SNAPS[key])
    assert (p["total"], p["k"], p["np"]) == (8, 2, 6)
    assert p["a"] + p["b"] + p["c"] + p["d"] + p["e"] + p["n"] == p["k"]
    assert {x: p[x] for x in "abcden"} == _independent_counts(ALL_SNAPS[key])


def test_real_counts_follow_the_snapshot_not_a_constant():
    assert len({tuple(vars(counts(s)).values()) for s in ALL_SNAPS.values()}) > 5


def test_k_line_and_kbar_are_not_double_counted():
    # 台股日 K（kbar）的任何狀態都不改變計數（不是第 9 個 dataset）
    a = counts(snap(twii(), "", regime("unloaded")))
    s2 = RealFeedSnapshot.of(twii(), "", regime("unloaded"), "", kbar=None, kbar_error="OSError")
    assert counts(s2) == a


# ── D-4 補償控制：四列的精確形狀（路徑＋key＋label＋值＋detail）──────────────────
_VALUE_RX = (re.compile(r"^固定清單 8 項$"), re.compile(r"^已接入畫面 \d+ 項｜尚未提供 \d+ 項$"),
             re.compile(r"^資料日在規則內 \d+ 項｜⚠ 過期或可能已過期 \d+ 項｜⬜ 資料未備 \d+ 項$"),
             re.compile(r"^🔴 來源目前不可用或資料異常 \d+ 項｜⬜ 尚未評估 \d+ 項$"))
_KEYS = ("fresh_total", "fresh_wired", "fresh_a", "fresh_b")
_LABELS = ("資料新鮮度總覽", "接入狀態", "新鮮度", "其他狀態")
_DETAIL_OK = re.compile(re.escape(DP.FRESHNESS_DISCLAIMER) + r"(　另有 [1-9]\d* 項判定結果為無法判定，不計入上列)?")
_FORBIDDEN = ("fetched_at", "published_at", "抓取時間", "發布時間", "freshness_policy", "STALE_DAYS", "MAX_LAG", "門檻",
              "更新時間", "cached_at", "retrieved_at")


def check_freshness_shapes(vm: PageVM) -> list[str]:
    bad: list[str] = []
    fs = vm.context.first_screen
    rs = fs.context_rows
    if len(rs) != 4:
        return [f"context_rows 必須恰四列，收到 {len(rs)}"]
    for i, f in enumerate(rs):
        if f.label != _LABELS[i]:
            bad.append(f"#{i}: label 不符 {f.label!r}")
        if not (f.state is FieldState.OK and f.status_text is None and f.capability is CapabilityState.PROVIDED):
            bad.append(f"#{i}: 必須是 OK 態純文字")
        if f.freshness.as_of is not None or f.freshness.source is not None:
            bad.append(f"#{i}: 不得帶 as_of／source")
        if not _VALUE_RX[i].fullmatch(f.value_text or ""):
            bad.append(f"#{i}: value 形狀不符 {f.value_text!r}")
        if i < 3 and f.detail is not None:
            bad.append(f"#{i}: 只有第 4 列可有 detail")
        if i == 3 and not _DETAIL_OK.fullmatch(f.detail or ""):
            bad.append(f"#{i}: detail 不是核准文案 {f.detail!r}")
        blob = f"{f.label}{f.value_text}{f.detail}"
        if any(w in blob for w in _FORBIDDEN) or re.search(r"\d{4}-\d{2}-\d{2}|\d{1,2}:\d{2}", blob):
            bad.append(f"#{i}: 出現規則名／時間戳／日期")
    return bad


def test_vm_keys_come_from_canonical_rows():
    from src.services.ui2.real_canonical import real_canonical
    c = real_canonical(P4_DATA, snap(twii(), "", regime("unloaded")))
    assert tuple(r["key"] for r in c["context_rows"]) == _KEYS


@pytest.mark.parametrize("key", sorted(ALL_SNAPS))
def test_shapes_hold_on_every_real_combination(key):
    assert check_freshness_shapes(get_real_page_vm(P4_DATA, ALL_SNAPS[key])) == []


def _with_row(vm: PageVM, i: int, **kw) -> PageVM:
    fs = vm.context.first_screen
    rs = list(fs.context_rows)
    rs[i] = dataclasses.replace(rs[i], **kw)
    return dataclasses.replace(vm, context=dataclasses.replace(
        vm.context, first_screen=dataclasses.replace(fs, context_rows=tuple(rs))))


def _base_vm():
    return get_real_page_vm(P4_DATA, snap(twii(), "", regime("unloaded")))


@pytest.mark.parametrize("what, mutate", [
    ("row0 帶 as_of", lambda v: _with_row(v, 0, freshness=FreshnessInfo(as_of="2026-11-13"))),
    ("row1 帶 source", lambda v: _with_row(v, 1, freshness=FreshnessInfo(source="TWII"))),
    ("row2 value 含日期", lambda v: _with_row(v, 2, value_text="資料日在規則內 1 項｜⚠ 過期或可能已過期 0 項｜⬜ 資料未備 0 項 2026-11-13")),
    ("row2 value 為原始收盤值", lambda v: _with_row(v, 2, value_text="23,456.78")),
    ("row3 detail 含 fetched_at", lambda v: _with_row(v, 3, detail=DP.FRESHNESS_DISCLAIMER + " fetched_at")),
    ("row3 detail 被改字", lambda v: _with_row(v, 3, detail="資料日在規則內代表安全。")),
    ("row3 detail 缺免責句", lambda v: _with_row(v, 3, detail=None)),
    ("row0 帶 detail", lambda v: _with_row(v, 0, detail="x")),
    ("row1 label 被改", lambda v: _with_row(v, 1, label="已接入")),
    ("row0 改為 STALE 態", lambda v: _with_row(v, 0, state=FieldState.STALE, status_text="⚠ 可能已過期")),
    ("row0 改為 capability", lambda v: _with_row(v, 0, state=None, value_text=None, status_text=DP.TEXT_NOT_PROVIDED,
                                                 capability=CapabilityState.NOT_PROVIDED)),
    ("row0 value 帶規則名", lambda v: _with_row(v, 0, value_text="固定清單 8 項 STALE_DAYS")),
])
def test_same_path_illegal_data_fails_the_shape_compensation(what, mutate):
    assert check_freshness_shapes(mutate(_base_vm())), what


def test_shape_checker_rejects_row_count_and_order():
    vm = _base_vm()
    fs = vm.context.first_screen
    five = dataclasses.replace(vm, context=dataclasses.replace(vm.context, first_screen=dataclasses.replace(
        fs, context_rows=fs.context_rows + (fs.context_rows[0],))))
    swapped = dataclasses.replace(vm, context=dataclasses.replace(vm.context, first_screen=dataclasses.replace(
        fs, context_rows=(fs.context_rows[1], fs.context_rows[0]) + fs.context_rows[2:])))
    assert check_freshness_shapes(five) and check_freshness_shapes(swapped)


# ── Q1=A allowlist 的反向驗證：其餘路徑／頁面仍被拒絕 ───────────────────────────
_VALUED = FieldVM("x", FieldState.OK, "1 項", None, None)


def _real_vms():
    return RF._vms(snap(twii(), "", regime("unloaded")))


def _with_ctx(vm: PageVM, rows_: tuple) -> PageVM:
    fs = vm.context.first_screen
    return dataclasses.replace(vm, context=dataclasses.replace(vm.context, first_screen=dataclasses.replace(fs, context_rows=rows_)))


def _replace_section_field(vm: PageVM, section_id: str, index: int, new: FieldVM) -> PageVM:
    secs = []
    for s in vm.context.sections:
        if s.section_id == section_id:
            fs = list(s.fields)
            fs[index] = new
            s = dataclasses.replace(s, fields=tuple(fs))
        secs.append(s)
    return dataclasses.replace(vm, context=dataclasses.replace(vm.context, sections=tuple(secs)))


def test_baseline_real_vms_pass_the_allowlist_checker():
    assert RF.check_only_wired_fields_carry_data(_real_vms()) == []


def _fifth_row(v):
    d = v[P4_DATA]
    return {**v, P4_DATA: _with_ctx(d, d.context.first_screen.context_rows + (_VALUED,))}


@pytest.mark.parametrize("what, mutate", [
    ("🗂 舊區塊『資料日』帶值", lambda v: {**v, P4_DATA: _replace_section_field(v[P4_DATA], "data_overview", 1, _VALUED)}),
    ("🗂 舊區塊『來源健康度』帶值", lambda v: {**v, P4_DATA: _replace_section_field(v[P4_DATA], "data_overview", 0, _VALUED)}),
    ("🗂 第 5 列（first/context_rows/4）帶值", _fifth_row),
    ("S 路徑 sections/data_freshness/0 不被放行",
     lambda v: {**v, P4_DATA: dataclasses.replace(v[P4_DATA], context=dataclasses.replace(
         v[P4_DATA].context, sections=(dataclasses.replace(v[P4_DATA].context.sections[0], section_id="data_freshness",
                                                           fields=(_VALUED,) + v[P4_DATA].context.sections[0].fields[1:]),)))}),
    ("🗂 第一屏『現在狀態』帶值", lambda v: {**v, P4_DATA: dataclasses.replace(v[P4_DATA], context=dataclasses.replace(
        v[P4_DATA].context, first_screen=dataclasses.replace(v[P4_DATA].context.first_screen, current_state=_VALUED)))}),
    ("🗂 第一屏『下一步』帶值", lambda v: {**v, P4_DATA: dataclasses.replace(v[P4_DATA], context=dataclasses.replace(
        v[P4_DATA].context, first_screen=dataclasses.replace(v[P4_DATA].context.first_screen, next_step=_VALUED)))}),
    ("👤 我的頁 first/context_rows/0 帶值（同索引、他頁）", lambda v: {**v, P4_ME: _with_ctx(v[P4_ME], (_VALUED,))}),
    ("💼 持股頁 first/context_rows/2 帶值", lambda v: {**v, P4_HOLD: _with_ctx(v[P4_HOLD], v[P4_HOLD].context.first_screen.context_rows + (_VALUED,))}),
])
def test_every_other_field_stays_rejected(what, mutate):
    assert RF.check_only_wired_fields_carry_data(mutate(_real_vms())), what


def test_market_page_unwired_fields_still_rejected():
    v = _real_vms()
    vix = next(c for c in v[P4_MARKET].context.cards if c.card_id == "vix")
    bad = dataclasses.replace(vix, field=_VALUED)
    cards = tuple(bad if c.card_id == "vix" else c for c in v[P4_MARKET].context.cards)
    v2 = {**v, P4_MARKET: dataclasses.replace(v[P4_MARKET], context=dataclasses.replace(v[P4_MARKET].context, cards=cards))}
    assert RF.check_only_wired_fields_carry_data(v2)


def test_allowlist_has_exactly_four_new_context_row_tuples_and_removing_them_turns_red(monkeypatch):
    new = {k for k in RF.WIRED_PATHS if k[0] == P4_DATA}
    assert new == {(P4_DATA, f"first/context_rows/{i}") for i in range(4)}
    assert not any("*" in p or p.endswith("/") for _, p in RF.WIRED_PATHS)
    monkeypatch.setattr(RF, "WIRED_PATHS", frozenset(k for k in RF.WIRED_PATHS if k[0] != P4_DATA))
    assert len(RF.check_only_wired_fields_carry_data(_real_vms())) >= 4


# ── D-5：降級頁「未評估」守衛的精確局部例外 ─────────────────────────────────────
_DEG_ROW4 = DP.freshness_rows(DP.counts_from_states({"twii": DP.S_UNAVAILABLE, "regime": DP.S_UNAVAILABLE}))[3]["value"]


def test_d5_positive_data_page_row4_wording_is_excepted():
    assert "未評估" in _DEG_ROW4
    # C2：例外位置敏感，需真實 DOM（第 4 個 ctx 列 value）；裸字串不再放行（見 test_ui2_real_feed.py::test_c2_d5_*）
    assert RF.regime_label_residue(RF._degraded_data_page_blob(), P4_DATA) == []


@pytest.mark.parametrize("what, page, blob", [
    ("🗂 其他位置多一個『⬜ 尚未評估』", P4_DATA, f"{_DEG_ROW4}<div>⬜ 尚未評估</div>"),
    ("🗂 位階字『震盪』殘留", P4_DATA, f"{_DEG_ROW4}<div>震盪</div>"),
    ("🗂 第 4 列被改字（e 之外多字）", P4_DATA, _DEG_ROW4.replace("⬜ 尚未評估 0 項", "⬜ 尚未評估 0 項（未評估）")),
    ("📊 同一串文案出現在別頁", P4_MARKET, _DEG_ROW4),
    ("🎯 同一串文案出現在別頁", P4_TARGET, _DEG_ROW4),
    ("💼 同一串文案出現在別頁", P4_HOLD, _DEG_ROW4),
    ("👤 同一串文案出現在別頁", P4_ME, _DEG_ROW4),
    ("📊 位階字『未評估』", P4_MARKET, "未評估"),
])
def test_d5_reverse_injection_everything_else_still_fails(what, page, blob):
    assert RF.regime_label_residue(blob, page), what
