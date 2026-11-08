"""tests/test_b2_consumer_consistency.py — D3 B2（DEC-148）空抓取三態：消費端一致性。

B1（producer）已讓 metadata 在「空抓取」時帶 `fetch_outcome`／`fetch_evidence`；B2 讓讀取端、校準閘門、畫面文案、PR 文案
走**同一個**判定（`shared/upstream_state.py::classify_upstream`）。

要鎖的行為（客戶 2026-11-08 核准）：
 (1) FETCH_FAILED 不得被 `check_inputs_fresh` 放行（含 last_error 仍是空抓取標記的矛盾情境）；
 (2) NO_NEW_DATA 不得變成來源故障，也不得重設觀測日（as_of／is_stale／meta_last_updated 與三態無關）；
 (3) UNDETERMINED 保持無法判定：閘門不放行、文案不稱成功也不稱失敗；
 (4) 舊 metadata 缺 fetch_outcome：純標記字串 → UNDETERMINED（不預設成功）；
 (5) last_error／fetch_outcome／freshness 各自表達自己的語意；
 (6) UI 文案三態分流，僅文字。
"""
from __future__ import annotations

import datetime as dt
import json

import pandas as pd
import pytest

import scripts.publish_data_pr as pdp
from shared.fetch_outcome import FetchOutcome
from shared.staleness import EMPTY_FETCH_MARKER
from shared.upstream_state import (
    UPSTREAM_TEXT_FETCH_FAILED, UPSTREAM_TEXT_NO_NEW_DATA, UPSTREAM_TEXT_UNDETERMINED,
    classify_upstream, gate_allows, upstream_state_text, upstream_state_value,
)
from tests.test_dl_f1_s6_s7_calibrate_gate import (
    _REQUIRED, _gate, _write_daily, _write_m1m2, _write_meta,
)

NND, FF, UND = FetchOutcome.NO_NEW_DATA, FetchOutcome.FETCH_FAILED, FetchOutcome.UNDETERMINED
_EV = "FinMind inst: HTTP 500"
_TODAY = dt.date(2026, 9, 27)          # 週日；資料停在 9/25（週五）＝不過期


# ═════════════════════════════════════════════════════════════════════════════
# 1. 判定表（唯一的 SSOT）
# ═════════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("last_error,outcome,evidence,expect", [
    # 無錯誤
    (None, None, None, None),
    ("", None, None, None),
    (None, "NO_NEW_DATA", "e", None),                       # 空 last_error 配 NO_NEW_DATA：不憑空造故障
    # 空抓取標記 × 三態
    (EMPTY_FETCH_MARKER, "NO_NEW_DATA", "e", NND),
    (EMPTY_FETCH_MARKER, "FETCH_FAILED", _EV, FF),          # B1 缺口：標記 + FETCH_FAILED 必須是失敗
    (EMPTY_FETCH_MARKER, "UNDETERMINED", "e", UND),
    # 舊 metadata／壞值／缺證據 → UNDETERMINED（不預設成功，也不預設失敗）
    (EMPTY_FETCH_MARKER, None, None, UND),
    (EMPTY_FETCH_MARKER, "MAYBE", "e", UND),
    (EMPTY_FETCH_MARKER, "", "e", UND),
    (EMPTY_FETCH_MARKER, "FETCH_FAILED", "", UND),          # 失敗但沒證據 → 降為無法判定
    (EMPTY_FETCH_MARKER, "FETCH_FAILED", None, UND),
    # 其他任何非空 last_error → 失敗，不論 outcome 寫什麼（複合字串＝既有檔已知不合格）
    ("RuntimeError: x", None, None, FF),
    ("HTTPError: 503", "NO_NEW_DATA", "e", FF),
    ("抓取結果為空；既有檔 sanity 不過,待重建", "NO_NEW_DATA", "e", FF),
    ("抓取結果為空；既有檔 sanity 不過,待重建", None, None, FF),
    ("FINMIND_TOKEN 未設定", None, None, FF),
    (EMPTY_FETCH_MARKER + " ", "NO_NEW_DATA", "e", FF),     # 只認完全相等
    (" " + EMPTY_FETCH_MARKER, "NO_NEW_DATA", "e", FF),
    # 矛盾 metadata：last_error 空但 outcome 自陳失敗／無法判定 → 照該態（不得被當成功）
    (None, "FETCH_FAILED", _EV, FF),
    (None, "UNDETERMINED", "e", UND),
])
def test_classify_upstream_table(last_error, outcome, evidence, expect):
    assert classify_upstream(last_error, outcome, evidence)[0] is expect


def test_gate_allows_only_none_or_no_new_data():
    assert gate_allows(None) and gate_allows("") and gate_allows("NO_NEW_DATA") and gate_allows(NND)
    for bad in ("FETCH_FAILED", "UNDETERMINED", "MAYBE", FF, UND):
        assert not gate_allows(bad), bad


def test_texts_are_three_distinct_sentences_and_only_failed_says_failure():
    assert upstream_state_text(FF) == UPSTREAM_TEXT_FETCH_FAILED == "上游最近一次抓取失敗"
    assert upstream_state_text(NND) == UPSTREAM_TEXT_NO_NEW_DATA == "最近一次抓取成功，來源無新資料（不代表資料最新）"
    assert upstream_state_text(UND) == UPSTREAM_TEXT_UNDETERMINED == "最近一次抓取結果無法判定"
    assert "失敗" not in UPSTREAM_TEXT_NO_NEW_DATA and "失敗" not in UPSTREAM_TEXT_UNDETERMINED
    assert upstream_state_text(None) == "" and upstream_state_text("") == "" and upstream_state_text("MAYBE") == ""


# ═════════════════════════════════════════════════════════════════════════════
# 2. reader：compute_cache_staleness／attrs
# ═════════════════════════════════════════════════════════════════════════════
def _entry(last_error=EMPTY_FETCH_MARKER, outcome=None, evidence=None, last_updated="2026-09-25"):
    d = {"name": "finmind_inst", "last_updated": last_updated, "row_count": 30, "last_error": last_error}
    if outcome is not None:
        d["fetch_outcome"] = outcome
    if evidence is not None:
        d["fetch_evidence"] = evidence
    return d


def _staleness(tmp_path, entry, today=_TODAY):
    from src.data.macro.macro_cache_reader import compute_cache_staleness
    _write_daily(tmp_path, "finmind_inst", dt.date(2026, 9, 25))
    _write_meta(tmp_path, {"finmind_inst": entry})
    return compute_cache_staleness("finmind_inst", cache_dir=tmp_path, today=today)


@pytest.mark.parametrize("entry,state", [
    (_entry(outcome="NO_NEW_DATA", evidence="HTTP 200, data=[]"), "NO_NEW_DATA"),
    (_entry(outcome="FETCH_FAILED", evidence=_EV), "FETCH_FAILED"),
    (_entry(outcome="UNDETERMINED", evidence="e"), "UNDETERMINED"),
    (_entry(), "UNDETERMINED"),                                        # 舊 metadata 缺欄
    (_entry(last_error=None), ""),
    (_entry(last_error="RuntimeError: x"), "FETCH_FAILED"),
])
def test_reader_reports_upstream_state(tmp_path, entry, state):
    assert _staleness(tmp_path, entry)["upstream_state"] == state


def test_reader_passes_through_raw_fields_unchanged(tmp_path):
    st = _staleness(tmp_path, _entry(outcome="FETCH_FAILED", evidence=_EV))
    assert st["upstream_error"] == EMPTY_FETCH_MARKER            # last_error 原樣、不被改寫
    assert st["fetch_outcome"] == "FETCH_FAILED" and st["fetch_evidence"] == _EV
    legacy = _staleness(tmp_path, _entry())
    assert legacy["fetch_outcome"] is None and legacy["fetch_evidence"] == ""


@pytest.mark.parametrize("outcome", [None, "NO_NEW_DATA", "FETCH_FAILED", "UNDETERMINED"])
def test_outcome_never_changes_freshness_or_observation_date(tmp_path, outcome):
    """freshness／觀測日只由資料本身決定；三態不得重設 as_of、不得讓過期變新鮮或新鮮變過期。"""
    base = _staleness(tmp_path, _entry(last_error=None))
    got = _staleness(tmp_path, _entry(outcome=outcome, evidence="e" if outcome else None))
    for k in ("is_stale", "as_of", "age_days", "reason", "meta_last_updated"):
        assert got[k] == base[k], (outcome, k)
    # 過期資料：NO_NEW_DATA 不使它變新鮮
    stale_day = dt.date(2026, 10, 30)
    s = _staleness(tmp_path, _entry(outcome="NO_NEW_DATA", evidence="e"), today=stale_day)
    assert s["is_stale"] is True and s["as_of"] == dt.date(2026, 9, 25)


def test_attrs_carry_upstream_state_and_evidence(tmp_path):
    from src.data.macro.macro_cache_reader import _attach_staleness
    _write_daily(tmp_path, "finmind_inst", dt.date(2026, 9, 25))
    _write_meta(tmp_path, {"finmind_inst": _entry(outcome="FETCH_FAILED", evidence=_EV)})
    s = _attach_staleness(pd.Series([1.0]), "finmind_inst", cache_dir=tmp_path, today=_TODAY)
    assert s.attrs["upstream_state"] == "FETCH_FAILED" and s.attrs["fetch_evidence"] == _EV
    assert s.attrs["upstream_error"] == EMPTY_FETCH_MARKER


# ═════════════════════════════════════════════════════════════════════════════
# 3. 校準閘門 check_inputs_fresh
# ═════════════════════════════════════════════════════════════════════════════
def _gate_inputs(tmp_path, entry_by_name, daily_last=dt.date(2026, 9, 25)):
    _write_daily(tmp_path, "twii_ohlcv", daily_last)
    _write_daily(tmp_path, "finmind_inst", daily_last)
    _write_m1m2(tmp_path, dt.date(2026, 8, 1))
    ds = {n: {"name": n, "last_updated": None, "row_count": 1, "last_error": None} for n in _REQUIRED}
    ds.update(entry_by_name)
    _write_meta(tmp_path, ds)
    return [b["dataset"] for b in _gate().check_inputs_fresh(tmp_path, today=_TODAY)]


@pytest.mark.parametrize("entry,blocked", [
    (_entry(outcome="NO_NEW_DATA", evidence="e"), False),
    (_entry(outcome="FETCH_FAILED", evidence=_EV), True),     # (1) 標記 + FETCH_FAILED：B1 時仍被放行
    (_entry(outcome="UNDETERMINED", evidence="e"), True),     # (3)
    (_entry(), True),                                          # (4) 舊 metadata 缺欄
    (_entry(outcome="FETCH_FAILED", evidence=""), True),       # 失敗缺證據 → 無法判定 → 擋
    (_entry(outcome="MAYBE", evidence="e"), True),
    (_entry(last_error="抓取結果為空；既有檔 sanity 不過,待重建", outcome="NO_NEW_DATA", evidence="e"), True),
    (_entry(last_error="RuntimeError: x"), True),
    (_entry(last_error=None), False),
])
def test_gate_matrix_fresh_data(tmp_path, entry, blocked):
    got = _gate_inputs(tmp_path, {"finmind_inst": entry})
    assert got == (["finmind_inst"] if blocked else [])


def test_gate_stale_data_blocked_even_with_no_new_data(tmp_path):
    """NO_NEW_DATA 只代表那一次抓取沒新列，不代表資料新鮮：過期照擋。"""
    got = _gate_inputs(tmp_path, {"finmind_inst": _entry(outcome="NO_NEW_DATA", evidence="e")},
                       daily_last=dt.date(2026, 9, 1))
    assert "finmind_inst" in got


def test_gate_block_message_distinguishes_failed_from_undetermined(tmp_path, monkeypatch):
    mod = _gate()
    _gate_inputs(tmp_path, {"finmind_inst": _entry(outcome="FETCH_FAILED", evidence=_EV),
                            "twii_ohlcv": _entry(outcome="UNDETERMINED", evidence="e")})
    states = mod.check_inputs_fresh(tmp_path, today=_TODAY)
    monkeypatch.setattr(mod, "_CACHE", tmp_path)
    monkeypatch.setattr(mod, "check_inputs_fresh", lambda *a, **k: states)
    with pytest.raises(SystemExit) as ei:
        mod.main()
    lines = str(ei.value).splitlines()
    _inst = next(ln for ln in lines if "finmind_inst" in ln)
    _twii = next(ln for ln in lines if "twii_ohlcv" in ln)
    assert "抓取失敗" in _inst and "FETCH_FAILED" in _inst and "判為過期" not in _inst
    assert "無法判定" in _twii and "抓取失敗" not in _twii and "UNDETERMINED" in _twii
    assert "NO_NEW_DATA" in next(ln for ln in lines if "修法" in ln)


# ═════════════════════════════════════════════════════════════════════════════
# 4. 畫面文案：service → ui2 card → legacy basis
# ═════════════════════════════════════════════════════════════════════════════
def _series_with(**attrs):
    s = pd.Series([23456.789], index=pd.to_datetime(["2026-09-25"]))
    s.attrs.update({"is_stale": False, "stale_reason": "", "as_of": dt.date(2026, 9, 25), "age_days": 2, **attrs})
    return s


@pytest.mark.parametrize("attrs,state", [
    ({"upstream_error": EMPTY_FETCH_MARKER, "upstream_state": "NO_NEW_DATA"}, "NO_NEW_DATA"),
    ({"upstream_error": EMPTY_FETCH_MARKER, "upstream_state": "FETCH_FAILED"}, "FETCH_FAILED"),
    ({"upstream_error": EMPTY_FETCH_MARKER, "upstream_state": "UNDETERMINED"}, "UNDETERMINED"),
    ({"upstream_error": EMPTY_FETCH_MARKER}, "UNDETERMINED"),         # attrs 沒 state 的舊讀取路徑：純標記不預設成功
    ({"upstream_error": "HTTPError: 500"}, "FETCH_FAILED"),
    ({}, ""),
])
def test_service_view_upstream_state(monkeypatch, attrs, state):
    import src.data.macro.macro_cache_reader as R
    from src.services.market_twii_view_service import get_twii_trend_view
    monkeypatch.setattr(R, "load_twii_close", lambda: _series_with(**attrs))
    v = get_twii_trend_view(1)
    assert v.upstream_state == state
    assert v.upstream_error == attrs.get("upstream_error", "")          # 原樣轉述
    assert v.is_stale is False and v.as_of == "2026-09-25"             # freshness 不受三態影響


def _card_reason(monkeypatch, **view_kw):
    from src.services import market_twii_view_service as TWS
    from src.services.ui2 import real_feed as RF
    from src.services.ui2.real_canonical import twii_card_spec
    from tests.test_ui2_real_feed import _feed, _twii_view
    snap = _feed(monkeypatch, twii=_twii_view(**view_kw))
    assert TWS  # noqa
    assert RF
    return twii_card_spec(snap)


@pytest.mark.parametrize("kw,expect", [
    (dict(upstream_error=EMPTY_FETCH_MARKER, upstream_state="FETCH_FAILED"), UPSTREAM_TEXT_FETCH_FAILED),
    (dict(upstream_error=EMPTY_FETCH_MARKER, upstream_state="NO_NEW_DATA"), UPSTREAM_TEXT_NO_NEW_DATA),
    (dict(upstream_error=EMPTY_FETCH_MARKER, upstream_state="UNDETERMINED"), UPSTREAM_TEXT_UNDETERMINED),
    (dict(upstream_error=EMPTY_FETCH_MARKER), UPSTREAM_TEXT_UNDETERMINED),           # view 沒 state → 由 last_error 判
    (dict(upstream_error="HTTP 500"), UPSTREAM_TEXT_FETCH_FAILED),
])
def test_ui2_card_sentence_by_state(monkeypatch, kw, expect):
    spec = _card_reason(monkeypatch, **kw)
    assert spec["reason"] == expect
    # freshness 與三態各自表達：卡片仍是未過期、值照舊
    assert spec.get("state") in (None, "ok") and spec["value"] == f"{23456.789:,.2f}"


def test_ui2_card_no_state_no_sentence(monkeypatch):
    assert _card_reason(monkeypatch)["reason"] is None


def test_ui2_card_stale_and_no_new_data_keep_both_facts(monkeypatch):
    spec = _card_reason(monkeypatch, is_stale=True, age_days=40, stale_reason="快取超過 40 天",
                        upstream_error=EMPTY_FETCH_MARKER, upstream_state="NO_NEW_DATA")
    assert spec["state"] == "stale"
    assert "快取超過 40 天" in spec["reason"] and UPSTREAM_TEXT_NO_NEW_DATA in spec["reason"]


def test_ui2_fact_rejects_unknown_upstream_state():
    from src.services.ui2.real_canonical import RealFeedContractError, TwiiFact, validate_twii_fact
    f = TwiiFact(True, (1.0,), "2026-01-01", False, "", 1, False, "", False, "s", upstream_state="MAYBE")
    with pytest.raises(RealFeedContractError):
        validate_twii_fact(f)


def _basis_missing(**kw):
    from src.services.market_twii_view_service import TwiiTrendView
    from src.ui.views import _market_blocks as B
    v = TwiiTrendView(ok=True, xs=("2026-09-25",), close=(1.0,), n_available=5, as_of="2026-09-25",
                      is_stale=False, age_days=2, **kw)
    return B.basis_chart_a(v, {}).missing


def test_legacy_basis_sentence_by_state():
    assert UPSTREAM_TEXT_NO_NEW_DATA in _basis_missing(upstream_error=EMPTY_FETCH_MARKER, upstream_state="NO_NEW_DATA")
    assert UPSTREAM_TEXT_UNDETERMINED in _basis_missing(upstream_error=EMPTY_FETCH_MARKER, upstream_state="UNDETERMINED")
    assert UPSTREAM_TEXT_UNDETERMINED in _basis_missing(upstream_error=EMPTY_FETCH_MARKER)
    assert UPSTREAM_TEXT_FETCH_FAILED in _basis_missing(upstream_error=EMPTY_FETCH_MARKER, upstream_state="FETCH_FAILED")
    # 具體錯誤字串仍原樣（洗過）顯示
    assert "上游最後一次錯誤：HTTPError: 500" in _basis_missing(upstream_error="HTTPError: 500", upstream_state="FETCH_FAILED")
    # 空抓取不再被寫成「上游最後一次錯誤：抓取結果為空」
    for st in ("NO_NEW_DATA", "UNDETERMINED", "FETCH_FAILED"):
        assert "上游最後一次錯誤：抓取結果為空" not in _basis_missing(upstream_error=EMPTY_FETCH_MARKER, upstream_state=st)
    assert "上游" not in _basis_missing()


# ═════════════════════════════════════════════════════════════════════════════
# 5. PR 文案與讀取端分流一致（同一份 metadata，兩個 consumer 對三態的歸類不得分歧）
# ═════════════════════════════════════════════════════════════════════════════
def _pr_state(entry):
    data = json.dumps({"updated_at": "x", "datasets": {"d": entry}}).encode()
    return pdp.assess_state({pdp.MACRO_META: data}, {}, "2026-11-09")


@pytest.mark.parametrize("entry", [
    _entry(outcome="NO_NEW_DATA", evidence="e"),
    _entry(outcome="FETCH_FAILED", evidence=_EV),
    _entry(outcome="UNDETERMINED", evidence="e"),
    _entry(),
    _entry(last_error="RuntimeError: x"),
    _entry(last_error="抓取結果為空；既有檔 sanity 不過,待重建", outcome="NO_NEW_DATA", evidence="e"),
    _entry(outcome="MAYBE", evidence="e"),
    _entry(outcome="FETCH_FAILED", evidence=""),
])
def test_pr_wording_and_reader_agree_on_bucket(entry):
    state, _ = classify_upstream(entry["last_error"], entry.get("fetch_outcome"), entry.get("fetch_evidence"))
    st = _pr_state(entry)
    in_failure = "d:" in st["failure"]
    in_no_new = "無新資料（來源讀取成功" in st["holiday"]
    in_undet = "無法判定（空抓取、證據不足" in st["holiday"]
    if state is NND:
        assert in_no_new and not in_failure
    elif state is UND:
        # PR 文案：無法判定（不論是缺欄／壞值／缺證據），legacy 缺欄在 PR 端維持「進失敗行」＝保守（不稱成功）；兩者都不稱成功
        assert not in_no_new
        assert in_undet or in_failure
    else:
        assert state is FF and in_failure and not in_no_new


def test_pr_marker_with_fetch_failed_is_failure_line_with_evidence():
    st = _pr_state(_entry(outcome="FETCH_FAILED", evidence=_EV))
    assert "d:" in st["failure"] and _EV in st["failure"]


# ═════════════════════════════════════════════════════════════════════════════
# 6. 端到端：producer → metadata → reader → gate（B1 缺口回歸）
# ═════════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("tag,evidence,blocked", [
    (NND, "HTTP 200, data=[]", False),
    (FF, "HTTP 500", True),
    (UND, "e", True),
    (None, "", True),                  # fetcher 沒標記 → UNDETERMINED
])
def test_producer_to_gate_roundtrip(monkeypatch, tmp_path, tag, evidence, blocked):
    import scripts.update_macro_history as umh
    from shared.fetch_outcome import tag_outcome

    def _fetch(*a, **k):
        df = pd.DataFrame()
        return tag_outcome(df, tag, evidence) if tag is not None else df

    _write_daily(tmp_path, "twii_ohlcv", dt.date(2026, 9, 25))
    _write_daily(tmp_path, "finmind_inst", dt.date(2026, 9, 25))
    _write_m1m2(tmp_path, dt.date(2026, 8, 1))
    monkeypatch.setattr(umh, "CACHE_DIR", tmp_path)
    for name in _REQUIRED:
        monkeypatch.setitem(umh.FETCHERS, name, (_fetch, umh.FETCHERS[name][1]))
    meta = {n: umh.update_one(n, _TODAY, False, 1, "tok") for n in _REQUIRED}
    _obs = {"twii_ohlcv": "2026-09-25", "finmind_inst": "2026-09-25", "finmind_m1m2": "2026-08-01"}
    for n, m in meta.items():
        assert m["last_error"] == EMPTY_FETCH_MARKER                      # producer 仍寫標記（既有契約不變）
        assert m["last_updated"] == _obs[n]                                # (2)(7) 觀測日＝磁碟上現有資料最後一天，不重設
    _write_meta(tmp_path, meta)
    got = [b["dataset"] for b in _gate().check_inputs_fresh(tmp_path, today=_TODAY)]
    assert got == (list(_REQUIRED) if blocked else [])


def test_upstream_state_value_roundtrip():
    assert upstream_state_value(None) == "" and upstream_state_value(FF) == "FETCH_FAILED"
