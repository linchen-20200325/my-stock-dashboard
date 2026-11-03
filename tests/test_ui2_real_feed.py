"""New UI2 NUI2-REAL-FEED A3：Real-data shadow acceptance（read-only；一般道，**不連網**）。

客戶 2026-11-03 (11) A3：loaded／missing／stale／unavailable／partial／source failure／as_of／source provenance／
cross-page same-field consistency；Preview 明確標示「Real-data Preview／非正式 production default」。
⚠️ 本檔是 **shadow** acceptance（不切 production default）——**不等於** Migration Contract C5「real-data acceptance」
通過（C5 依 Cutover 鏈在四頁逐頁驗收〔含 Aggregator〕之後）。

範圍：只接 2 個事實（台股加權指數、市場位階）；其餘欄位 ⬜＋原因。
- §1 台股：真 git 追蹤 parquet（相對斷言，⛔ 寫死數值／is_stale）＋注入 missing／failed／例外／stale／is_stale=None／壞契約。
- §2 位階：unloaded／unevaluated（缺真實廣度）／failed（strict 真讀壞檔）／未知 source raise／loaded／契約矛盾 raise。
- §3 provenance：source／as_of 存在或明示未提供；real ⛔ FAKE、fake 必 FAKE（雙向）。
- §4 跨頁一致：同一 snapshot 下位階三處 value／state／字樣／as_of 相同；Risk Cap 三頁同為無法判定；單一呼叫。
- §5 Real／Fake 區分與契約不變量（Risk Cap、動作欄、禁用字樣、capability 必附原因）。
- §6 no-write proof：(2) AppTest runtime session 寫入紀錄＝只有明列的 `ui2_` 鍵；(3) git status＋data_cache／狀態檔
  hash／mtime 不變；(4) socket connect guard＝0 次連線。〔(1) AST 守衛＋mutation 見 `test_ui2_guards.py` G2F／G9。〕
- §7 AppTest：預設仍 FAKE；Real 模式四頁 banner／無例外／每 rerun 只讀一次。
- §8 viewport 判定器（real 模式新增判定）teeth。
"""
from __future__ import annotations

import copy
import dataclasses
import hashlib
import math
import pathlib
import re
import socket

import numpy as np
import pytest

from shared import regime_arbiter as RA
from shared.allocation_decision import REGIME_LABEL
from shared.ui2_contract import text as T
from shared.ui2_contract.models import CapabilityState, FieldState, FieldVM, JudgementState, PageVM
from shared.ui2_contract.pages import (
    FEED_IDS, P4_HOLD, P4_ME, P4_MARKET, P4_TARGET, PAGE_IDS, SCENARIO_IDS, SCENARIO_REAL,
)
from src.services import allocation_service, market_twii_view_service as TWS
from src.services.market_twii_view_service import TWII_SOURCE_TEXT, TwiiTrendView
from src.services.ui2 import real_canonical as RC, real_feed as RF, vm_common
from src.services.ui2.preview_feed import get_preview_page_vm
from src.services.ui2.real_canonical import RealFeedSnapshot, RegimeFact, TwiiFact, get_real_page_vm
from tests.test_ui2_guards import _FORBIDDEN_ACTION_WORDS, _FORBIDDEN_TERMS, _all_fields, _texts
from tests.ui2_viewport import measure_viewport as MV

ROOT = pathlib.Path(__file__).resolve().parents[1]
APP_UI2 = ROOT / "app_ui2.py"


# ── helpers ──────────────────────────────────────────────────────────────
def _twii_view(**kw) -> TwiiTrendView:
    d = dict(ok=True, xs=("2026-01-02",), close=(23456.789,), n_available=10, as_of="2026-01-02",
             is_stale=False, stale_reason="", age_days=1, upstream_error="", error="", failed=False)
    d.update(kw)
    return TwiiTrendView(**d)


def _regime(regime="unknown", source=RA.SOURCE_UNLOADED, is_loaded=False, **extra) -> dict:
    d = {"regime": regime, "light": RA.REGIME_LIGHT.get(regime, "⬜"), "source": source, "trend_regime": None,
         "health": None, "defense": False, "exposure_limit_pct": None, "traffic_light": None,
         "is_loaded": is_loaded, "risk_cap_disclosure": None}
    d.update(extra)
    return d


def _feed(monkeypatch, *, twii=None, twii_exc=None, regime=None, regime_exc=None, calls=None) -> RealFeedSnapshot:
    """經 **真 feed**（`read_real_snapshot`）跑：只把兩個 canonical service 換成注入版本。"""
    calls = calls if calls is not None else {}

    def fake_twii(n):
        calls["twii"] = calls.get("twii", 0) + 1
        calls["twii_args"] = n
        if twii_exc:
            raise twii_exc
        return twii if twii is not None else _twii_view()

    def fake_regime(**kw):
        calls["regime"] = calls.get("regime", 0) + 1
        calls["regime_kw"] = kw
        if regime_exc:
            raise regime_exc
        return regime if regime is not None else _regime()

    monkeypatch.setattr(TWS, "get_twii_trend_view", fake_twii)
    monkeypatch.setattr(allocation_service, "get_macro_regime", fake_regime)
    return RF.read_real_snapshot()


def _vms(snap: RealFeedSnapshot) -> dict[str, PageVM]:
    return {p: get_real_page_vm(p, snap) for p in PAGE_IDS}


def _twii_field(snap) -> FieldVM:
    return get_real_page_vm(P4_MARKET, snap).context.cards[0].field


def _regime_triplet(vms: dict[str, PageVM]) -> tuple[FieldVM, FieldVM, FieldVM]:
    m = vms[P4_MARKET].context.first_screen.current_state
    t = next(r for r in vms[P4_TARGET].context.first_screen.context_rows if r.label == "市場位階")
    d = next(f for f in vms[P4_TARGET].context.target.lookup.snapshot if f.label == "市場環境")
    return m, t, d


def _why_regime(vm: PageVM) -> FieldVM:
    why = next(s for s in vm.context.sections if s.section_id == "why")
    return next(f for f in why.fields if f.label == "位階說明")


# ════════════════════════════════════════════════════════════════════
# §1 台股加權指數
# ════════════════════════════════════════════════════════════════════
def test_twii_parquet_is_the_real_local_cache_and_feed_reads_it_without_hardcoding():
    # 「git 追蹤」由 `git ls-files data_cache/twii_ohlcv.parquet` 人工實查（mapping §3）；本測試⛔ 呼叫外部程式
    # （tests/test_zz_test_portability.py），只驗檔在 repo 內且 feed 讀的就是它（與 canonical service 直接結果相同）。
    assert (ROOT / "data_cache" / "twii_ohlcv.parquet").is_file()
    snap = RF.read_real_snapshot()
    direct = TWS.get_twii_trend_view(1)                     # 同一個 canonical service 的直接結果（相對斷言基準）
    assert snap.twii is not None and snap.twii_error == ""
    t = snap.twii
    assert (t.ok, t.close, t.as_of, t.is_stale, t.age_days) == (
        direct.ok, direct.close, direct.as_of, direct.is_stale, direct.age_days)
    f = _twii_field(snap)
    if not t.ok:                                            # 檔壞／缺：只能是 Missing／Unavailable（⛔ OK）
        assert f.state in (FieldState.MISSING, FieldState.UNAVAILABLE) and f.value_text is None
        return
    assert f.value_text == f"{t.close[-1]:,.2f}" and math.isfinite(t.close[-1])
    assert f.freshness.as_of == t.as_of and f.freshness.source == TWII_SOURCE_TEXT
    assert f.state is (FieldState.OK if t.is_stale is False else FieldState.STALE)


@pytest.mark.parametrize("view,exc,state,status,detail_has", [
    (_twii_view(ok=False, close=(), as_of=None, error="加權指數歷史快取讀不到"), None,
     FieldState.MISSING, T.TEXT_MISSING_NOT_FETCHED, "讀不到"),
    (_twii_view(ok=False, close=(), as_of=None, failed=True, error="OSError: disk"), None,
     FieldState.UNAVAILABLE, T.TEXT_UNAVAILABLE, "OSError"),
    (None, RuntimeError("boom-twii"), FieldState.UNAVAILABLE, T.TEXT_UNAVAILABLE, "RuntimeError"),
    (_twii_view(is_stale=True, age_days=3, stale_reason="快取超過 3 天"), None,
     FieldState.STALE, "⚠ 過期 3 天", "快取超過 3 天"),
    (_twii_view(is_stale=True, age_days=None), None, FieldState.STALE, T.TEXT_STALE_UNKNOWN, None),
    (_twii_view(is_stale=None, age_days=None), None, FieldState.STALE, T.TEXT_STALE_UNKNOWN, "新鮮度未判定"),
    (_twii_view(is_stale=False, upstream_error="HTTP 500"), None, FieldState.OK, None, "上游最近一次抓取失敗"),
])
def test_twii_states_are_mapped_without_inventing_values(monkeypatch, view, exc, state, status, detail_has):
    snap = _feed(monkeypatch, twii=view, twii_exc=exc)
    f = _twii_field(snap)
    assert f.state is state and f.status_text == status
    if state in (FieldState.OK, FieldState.STALE):
        assert f.value_text == f"{23456.789:,.2f}"
    else:
        assert f.value_text is None                       # missing ≠ 0；unavailable ≠ safe
    if detail_has:
        assert detail_has in (f.detail or "")


def test_twii_unknown_freshness_is_never_ok(monkeypatch):
    """is_stale=None（新鮮度未知）⛔ 當 OK（AI 總管內部判準，可推翻；service 檔頭明文 ⛔ 不當成新鮮）。"""
    f = _twii_field(_feed(monkeypatch, twii=_twii_view(is_stale=None)))
    assert f.state is FieldState.STALE and f.state is not FieldState.OK


@pytest.mark.parametrize("bad", [
    _twii_view(close=()), _twii_view(close=(float("nan"),)), _twii_view(close=(float("inf"),)),
    _twii_view(is_stale="yes"),
])
def test_twii_broken_contract_is_loud_and_isolated(monkeypatch, capsys, bad):
    """契約違反：讀取期接住 → 該欄紅色 Unavailable「資料格式異常，暫時無法顯示」＋log（P1：去掉「契約」等工程字樣）；位階照常（⛔ 默默落態、⛔ 整頁崩）。"""
    snap = _feed(monkeypatch, twii=bad, regime=_regime("bull", RA.SOURCE_BULL_SCORE, True))
    assert snap.twii is None and snap.twii_error == RC.CONTRACT_ERROR
    f = _twii_field(snap)
    assert f.state is FieldState.UNAVAILABLE and "資料格式異常" in f.detail and f.value_text is None
    assert "RealFeedContractError" in capsys.readouterr().out                 # 全文進 log
    assert _vms(snap)[P4_MARKET].context.first_screen.current_state.value_text == REGIME_LABEL["bull"]


@pytest.mark.parametrize("bad", [
    TwiiFact(True, (), "2026-01-01", False, "", 1, False, "", False, "s"),
    TwiiFact(True, (float("nan"),), "2026-01-01", False, "", 1, False, "", False, "s"),
])
def test_pure_converter_still_raises_on_a_bad_fact(bad):
    """防呆：純轉換直接收到壞 fact 仍 fail loud（feed 已在讀取期擋下）。"""
    snap = RealFeedSnapshot(twii=bad, twii_error="", regime=RegimeFact("unknown", "⬜", RA.SOURCE_UNLOADED, False),
                            regime_error="")
    with pytest.raises(RC.RealFeedContractError):
        get_real_page_vm(P4_MARKET, snap)


@pytest.mark.parametrize("is_stale", [1, 1.0, 0, "yes", np.True_, np.False_])
def test_twii_is_stale_must_be_exactly_true_false_or_none(monkeypatch, is_stale):
    """複驗 P2-1：`1`／`1.0`／`np.True_`／`0` 會被 `== True／False` 當真；只認 `True`／`False`／`None` 本身。"""
    snap = _feed(monkeypatch, twii=_twii_view(is_stale=is_stale))
    assert snap.twii is None and snap.twii_error == RC.CONTRACT_ERROR
    assert _twii_field(snap).state is FieldState.UNAVAILABLE


def test_twii_ok_and_failed_together_is_a_contract_violation(monkeypatch):
    snap = _feed(monkeypatch, twii=_twii_view(ok=True, failed=True, error="OSError: x"))
    assert snap.twii is None and snap.twii_error == RC.CONTRACT_ERROR


def test_twii_takes_the_last_close_when_several_are_returned(monkeypatch):
    f = _twii_field(_feed(monkeypatch, twii=_twii_view(xs=("a", "b", "c"), close=(100.0, 200.5, 300.25))))
    assert f.value_text == "300.25"


def test_twii_reads_exactly_one_trading_day(monkeypatch):
    calls = {}
    _feed(monkeypatch, calls=calls)
    assert calls["twii_args"] == RF.TWII_CARD_DAYS == 1


# ════════════════════════════════════════════════════════════════════
# §2 市場位階
# ════════════════════════════════════════════════════════════════════
def test_regime_call_is_strict_and_matches_legacy_new_ui(monkeypatch):
    calls = {}
    _feed(monkeypatch, calls=calls)
    assert calls["regime_kw"] == {"strict": True, "require_valid_risk_cap": True}


def test_regime_unloaded_is_not_evaluated_with_the_l0_explanation(monkeypatch):
    vms = _vms(_feed(monkeypatch, regime=_regime()))
    for f in _regime_triplet(vms):
        assert f.state is FieldState.NOT_EVALUATED and f.status_text == T.TEXT_NOT_LOADED and f.value_text is None
        assert T.TEXT_ASOF_MISSING in f.detail                     # 位階契約無 as_of → 明示未提供
    w = _why_regime(vms[P4_MARKET])
    from shared import signal_thresholds as ST
    if not ST.BREADTH_PROXY_SCORING_ENABLED:
        assert RA.NOT_LOADED_PENDING_BREADTH_EXPLAIN in w.detail      # 既有 L0 說明逐字（⛔ 另寫一份）
        # L0 句說「可以按更新」；Preview 沒有更新入口 ⇒ 連接句必須說清楚（QA P3：⛔ 兩句互相矛盾、⛔ 改 L0）
        assert RC.PREVIEW_NO_REFRESH_NOTE in w.detail
        assert w.detail.index(RA.NOT_LOADED_PENDING_BREADTH_EXPLAIN) < w.detail.index(RC.PREVIEW_NO_REFRESH_NOTE)
    assert w.state is FieldState.NOT_EVALUATED


def test_regime_breadth_unevaluated_is_unable_to_determine_not_not_evaluated(monkeypatch):
    vms = _vms(_feed(monkeypatch, regime=_regime(source=RA.SOURCE_UNEVALUATED_BREADTH)))
    for f in _regime_triplet(vms):
        assert f.state is JudgementState.UNDETERMINABLE and f.state != FieldState.NOT_EVALUATED
        assert f.status_text == T.TEXT_NOT_EVALUATED_DATA_SHORT and f.value_text is None
    assert RA.UNEVALUATED_BREADTH_EXPLAIN in _why_regime(vms[P4_MARKET]).detail


def test_regime_read_failure_is_unavailable_not_unevaluated(monkeypatch):
    vms = _vms(_feed(monkeypatch, regime_exc=RuntimeError("macro_state.json: JSONDecodeError")))
    for f in _regime_triplet(vms):
        assert f.state is FieldState.UNAVAILABLE and f.status_text == T.TEXT_UNAVAILABLE
        assert "RuntimeError" in f.detail and "JSONDecodeError" not in f.detail     # 畫面只放型別名


def test_strict_really_raises_on_a_corrupt_state_file_end_to_end(tmp_path, monkeypatch):
    """不 mock service：壞的 macro_state.json → strict 拋 → Unavailable（非 strict 會吞成「未評估」＝§1 靜默失敗）。"""
    (tmp_path / "macro_state.json").write_text("{bad json", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    snap = RF.read_real_snapshot()
    assert snap.regime is None and snap.regime_error == "RuntimeError"
    m, t, d = _regime_triplet(_vms(snap))
    assert m.state is t.state is d.state is FieldState.UNAVAILABLE
    # 同一 cwd 下台股快取不存在 → Missing（partial：兩事實各自隔離，⛔ 互相拖垮）
    assert snap.twii is not None and _twii_field(snap).state is FieldState.MISSING


@pytest.mark.parametrize("regime,label", [(r, REGIME_LABEL[r]) for r in ("bull", "neutral", "caution", "bear")])
def test_regime_loaded_uses_the_site_wide_label(monkeypatch, regime, label):
    vms = _vms(_feed(monkeypatch, regime=_regime(regime, RA.SOURCE_BULL_SCORE, True)))
    for f in _regime_triplet(vms):
        assert f.state is FieldState.OK and f.value_text == label
        assert f.freshness.as_of is None and T.TEXT_ASOF_MISSING in f.detail   # ⛔ cl_ts 頂替


@pytest.mark.parametrize("regime", [
    _regime(source="mystery:branch"),                                   # 未知 source
    _regime("bull", "mystery:branch", True),
    _regime("bull", RA.SOURCE_UNLOADED, True),                          # 契約矛盾：loaded 但 unloaded 分支
    _regime("unknown", RA.SOURCE_BULL_SCORE, True),                     # loaded 但 regime 未知
    _regime("bull", RA.SOURCE_BULL_SCORE, False),                       # 未載入卻是已載入分支
])
def test_regime_unknown_or_contradictory_contract_is_loud_and_isolated(monkeypatch, capsys, regime):
    snap = _feed(monkeypatch, regime=regime)
    assert snap.regime is None and snap.regime_error == RC.CONTRACT_ERROR
    assert "RealFeedContractError" in capsys.readouterr().out
    vms = _vms(snap)
    for f in _regime_triplet(vms):
        assert f.state is FieldState.UNAVAILABLE and "資料格式異常" in f.detail          # ⛔ 默默落成未評估
    assert vms[P4_MARKET].context.cards[0].field.state is FieldState.OK            # 台股照常（隔離）


def test_pure_regime_converter_still_raises_on_an_unknown_source():
    snap = RealFeedSnapshot(twii=None, twii_error="OSError",
                            regime=RegimeFact("bull", "🟢", "mystery:branch", True), regime_error="")
    with pytest.raises(RC.RealFeedContractError):
        get_real_page_vm(P4_MARKET, snap)


def test_regime_fact_never_carries_risk_cap_fields():
    """Risk Cap 數值 Gate 前：snapshot ⛔ 收 exposure_limit_pct／risk_cap_disclosure（mutation：加欄位即紅）。"""
    assert {f.name for f in dataclasses.fields(RegimeFact)} == {"regime", "light", "source", "is_loaded", "has_file_error"}


def test_risk_cap_stays_undeterminable_even_if_the_contract_returns_a_cap(monkeypatch):
    snap = _feed(monkeypatch, regime=_regime("bull", RA.SOURCE_BULL_SCORE, True, exposure_limit_pct=50,
                                             risk_cap_disclosure=object()))
    for p in (P4_MARKET, P4_TARGET, P4_HOLD):
        rc = [f for f in _all_fields(get_real_page_vm(p, snap)) if f.label == "Risk Cap"]
        assert len(rc) == 1
        assert rc[0].state is JudgementState.UNDETERMINABLE and rc[0].value_text is None
        assert "50" not in (rc[0].detail or "") and "%" not in (rc[0].detail or "")


# ════════════════════════════════════════════════════════════════════
# §3 provenance（雙向：real ⛔ FAKE；fake 必 FAKE）
# ════════════════════════════════════════════════════════════════════
def _all_strings(obj) -> list[str]:
    out: list[str] = []
    if isinstance(obj, str):
        out.append(obj)
    elif dataclasses.is_dataclass(obj):
        for fld in dataclasses.fields(obj):
            out += _all_strings(getattr(obj, fld.name))
    elif isinstance(obj, (list, tuple)):
        for x in obj:
            out += _all_strings(x)
    return out


def test_real_vms_never_carry_fake_labels_anywhere():
    vms = _vms(RF.read_real_snapshot())
    for p, vm in vms.items():
        assert not vm.is_fake and vm.scenario_id == SCENARIO_REAL
        assert vm.banner_text == T.REAL_PREVIEW_BANNER_TEXT != T.PREVIEW_BANNER_TEXT
        for s in _all_strings(vm):
            assert "FAKE" not in s, f"{p}: real VM 出現 FAKE 字樣 {s!r}"
        for f in _all_fields(vm):
            for v in (f.freshness.source, f.freshness.as_of):
                assert v is None or not v.startswith(T.FAKE_SOURCE_PREFIX)


def test_fake_vms_still_carry_fake_labels():
    seen = 0
    for p in PAGE_IDS:
        for sc in SCENARIO_IDS:
            vm = get_preview_page_vm(p, sc)
            assert vm.is_fake and vm.banner_text == T.PREVIEW_BANNER_TEXT
            for f in _all_fields(vm):
                if f.freshness.source is not None:
                    seen += 1
                    assert f.freshness.source.startswith(T.FAKE_SOURCE_PREFIX)
    assert seen > 0


def test_real_provenance_is_present_or_explicitly_missing(monkeypatch):
    vms = _vms(_feed(monkeypatch))
    tw = vms[P4_MARKET].context.cards[0].field
    assert tw.freshness.source == TWII_SOURCE_TEXT and tw.freshness.as_of == "2026-01-02"
    for f in _regime_triplet(vms):
        assert f.freshness.as_of is None                                   # 契約無資料日 → ⬜ 資料日未提供
        assert f.freshness.source == RC.REGIME_SOURCE_FMT.format(source=RA.SOURCE_UNLOADED)
        assert "規則分支" in f.freshness.source and "非資料來源" in f.freshness.source
        assert f.freshness.source != TWII_SOURCE_TEXT


def test_every_unwired_real_field_states_its_reason():
    """未接線欄位＝capability `⬜ 尚未提供`＋原因（⛔ 空原因）；動作欄＝待 Aggregator。"""
    for p, vm in _vms(RF.read_real_snapshot()).items():
        for f in _all_fields(vm):
            if f.capability is CapabilityState.NOT_PROVIDED:
                assert f.detail, f"{p}/{f.label}: 未接線卻沒有原因"


# ════════════════════════════════════════════════════════════════════
# §4 跨頁一致性（同一 snapshot、同一次呼叫）
# ════════════════════════════════════════════════════════════════════
def _detail_core(f: FieldVM) -> str | None:
    """detail 去掉「說明見…」指引（📊 指本頁 L2、🎯 指 📊 市場頁 L2；QA P3）後的內容——其餘必須逐字相同。"""
    d = f.detail
    for ptr in (RC.REGIME_SEE_WHY_MARKET, RC.REGIME_SEE_WHY):
        d = d.replace(ptr, "<see-why>") if d else d
    return d


def check_cross_page_regime(vms: dict[str, PageVM]) -> list[str]:
    """位階三處（📊 current_state／🎯 market_regime／🎯 dim_market_env）value／state／字樣／freshness 必相同；
    detail 除「說明見…」指引外逐字相同（🎯 指向 📊 市場頁）。"""
    m, t, d = _regime_triplet(vms)
    key = lambda f: (f.state, f.value_text, f.status_text, _detail_core(f), f.freshness, f.capability)
    return [f"{name} 與 📊 不一致：{key(x)} vs {key(m)}" for name, x in (("🎯 market_regime", t), ("🎯 dim_market_env", d))
            if key(x) != key(m)]


_REGIME_VARIANTS = {
    "unloaded": dict(regime=_regime()),
    "unevaluated_breadth": dict(regime=_regime(source=RA.SOURCE_UNEVALUATED_BREADTH)),
    "failed": dict(regime_exc=RuntimeError("bad file")),
    "loaded": dict(regime=_regime("neutral", RA.SOURCE_NEUTRAL_FALLTHROUGH, True)),
}


@pytest.mark.parametrize("variant", list(_REGIME_VARIANTS))
def test_regime_is_identical_across_pages(monkeypatch, variant):
    vms = _vms(_feed(monkeypatch, **_REGIME_VARIANTS[variant]))
    assert check_cross_page_regime(vms) == []
    m_, t_, d_ = _regime_triplet(vms)
    # DEC-128／129：舊版在此強制「說明見『為什麼（L2）』」指引存在（保護已失效的頁內 L2 presentation）——已移除；
    # 跨頁一致性（值／態／字樣／freshness／除指引外 detail 逐字相同）由 check_cross_page_regime 照舊守住。
    w = _why_regime(vms[P4_MARKET])                          # L2 位階說明：同態同字樣（只 detail 較完整）
    m = vms[P4_MARKET].context.first_screen.current_state
    assert (w.state, w.value_text, w.status_text, w.freshness) == (m.state, m.value_text, m.status_text, m.freshness)


def test_cross_page_checker_has_teeth(monkeypatch):
    """mutation：🎯 改吃另一份 snapshot（＝位階分別讀取）→ 檢查器必紅。"""
    a = _feed(monkeypatch, regime=_regime())
    b = _feed(monkeypatch, regime=_regime("bull", RA.SOURCE_BULL_SCORE, True))
    mixed = {P4_MARKET: get_real_page_vm(P4_MARKET, a), P4_TARGET: get_real_page_vm(P4_TARGET, b)}
    assert check_cross_page_regime(mixed)


def test_one_snapshot_means_one_call_per_service(monkeypatch):
    calls = {}
    snap = _feed(monkeypatch, calls=calls)
    _vms(snap)                                               # 四頁 VM 都由同一份 snapshot 建（純函式，不再讀）
    assert calls["regime"] == 1 and calls["twii"] == 1


def test_risk_cap_and_action_fields_are_identical_across_pages_and_feeds():
    snap = RF.read_real_snapshot()
    real_rc = [next(f for f in _all_fields(get_real_page_vm(p, snap)) if f.label == "Risk Cap")
               for p in (P4_MARKET, P4_TARGET, P4_HOLD)]
    fake_rc = next(f for f in _all_fields(get_preview_page_vm(P4_MARKET, "loaded")) if f.label == "Risk Cap")
    assert all(f == fake_rc for f in real_rc)                # 契約固定欄：跨頁、跨 feed 同一字樣
    acts = [get_real_page_vm(p, snap).context.first_screen.action_needed for p in (P4_MARKET, P4_HOLD)]
    assert acts[0] == acts[1] == get_preview_page_vm(P4_MARKET, "loaded").context.first_screen.action_needed
    assert acts[0].status_text == T.TEXT_NOT_PROVIDED_AGGREGATOR
    ex = next(f for f in _all_fields(get_real_page_vm(P4_HOLD, snap)) if f.label == "目前曝險")
    assert ex.state is FieldState.MISSING and ex.value_text is None
    tgt = get_real_page_vm(P4_TARGET, snap).context.target.lookup.snapshot
    fake_tgt = get_preview_page_vm(P4_TARGET, "loaded").context.target.lookup.snapshot
    for lbl in ("趨勢", "產業"):
        assert next(f for f in tgt if f.label == lbl) == next(f for f in fake_tgt if f.label == lbl)


# ════════════════════════════════════════════════════════════════════
# §5 Real／Fake 區分與契約不變量
# ════════════════════════════════════════════════════════════════════
def test_real_scenario_axis_is_separate_from_fake_scenarios():
    assert SCENARIO_REAL not in SCENARIO_IDS and FEED_IDS == ("fake", "real")
    c = RC.real_canonical(P4_MARKET, RF.read_real_snapshot())
    bad_fake = dict(c, is_fake=True)
    with pytest.raises(ValueError):
        vm_common.build_page_vm(bad_fake)
    bad_real = dict(c, scenario="cold")
    with pytest.raises(ValueError):
        vm_common.build_page_vm(bad_real)


@pytest.mark.parametrize("page", PAGE_IDS)
def test_real_vms_create_no_actions_and_no_forbidden_terms(page):
    vm = get_real_page_vm(page, RF.read_real_snapshot())
    blob = "\n".join(_texts(vm)).replace(T.TEXT_NOT_PROVIDED_AGGREGATOR, "")
    for w in _FORBIDDEN_ACTION_WORDS + _FORBIDDEN_TERMS:
        assert w not in blob, f"{page}: 出現禁用字樣 {w!r}"
    assert vm.context.first_screen.primary_cta.enabled is False


def test_real_vm_context_is_independent_of_presentation_slice():
    snap = RF.read_real_snapshot()
    base = get_real_page_vm(P4_MARKET, snap)
    for n in (0, 2, 99):
        assert get_real_page_vm(P4_MARKET, snap, top_n=n).context == base.context


def test_real_me_page_does_not_pretend_to_know_the_account():
    vm = get_real_page_vm(P4_ME, RF.read_real_snapshot())
    assert vm.context.account is None
    assert vm.context.first_screen.current_state.capability is CapabilityState.NOT_PROVIDED


def test_snapshot_requires_exactly_value_or_error():
    tw = TwiiFact(True, (1.0,), "2026-01-01", False, "", 1, False, "", False, "s")
    rg = RegimeFact("unknown", "⬜", RA.SOURCE_UNLOADED, False)
    with pytest.raises(ValueError):
        RealFeedSnapshot(twii=None, twii_error="", regime=rg, regime_error="")
    with pytest.raises(ValueError):
        RealFeedSnapshot(twii=tw, twii_error="x", regime=rg, regime_error="")
    with pytest.raises(TypeError):
        RC.real_canonical(P4_MARKET, {"twii": None})
    with pytest.raises(ValueError):                           # 直接建構給壞代碼＝程式錯誤（fail loud）
        RealFeedSnapshot(twii=None, twii_error="OSError: /home/x token=SECRET", regime=rg, regime_error="")
    # 複驗 P3-4：feed 的建構入口 `of()` 降為 "Exception"（⛔ 在 try 外 raise 讓整頁崩、⛔ 原文進 snapshot）
    sn = RealFeedSnapshot.of(None, "OSError: /home/x token=SECRET", rg, "")
    assert sn.twii_error == "Exception" and "SECRET" not in repr(sn)
    assert RealFeedSnapshot.of(None, "x" * 200, rg, "").twii_error == "Exception"
    with pytest.raises(ValueError):
        TwiiFact(False, (), None, None, "", None, False, "OSError: token=SECRET", True, "s")


# ════════════════════════════════════════════════════════════════════
# §6 no-write proof（runtime／檔案系統／網路）
# ════════════════════════════════════════════════════════════════════
#: 殼允許寫入的 session key（純 UI 控制；明列）。其餘任何 key 的寫入＝失敗。
ALLOWED_UI2_WRITES = frozenset({"ui2_page", "ui2_scenario", "ui2_account", "ui2_feed", "ui2_target_mode"})


@pytest.fixture
def session_write_log(monkeypatch):
    from streamlit.runtime.state.session_state_proxy import SessionStateProxy
    log: list[tuple[str, str]] = []
    for meth in ("__setitem__", "__delitem__", "__setattr__", "__delattr__"):
        orig = getattr(SessionStateProxy, meth)

        def rec(self, key, *a, _orig=orig, _m=meth):
            log.append((_m, str(key)))
            return _orig(self, key, *a)
        monkeypatch.setattr(SessionStateProxy, meth, rec)
    return log


def _at(dev: bool = False):
    """`dev=True`：開啟開發面（`?ui2_dev=1`），才有資料來源／場景／帳戶控制可操作（P1）。"""
    from streamlit.testing.v1 import AppTest
    a = AppTest.from_file(str(APP_UI2), default_timeout=60)
    if dev:
        a.query_params["ui2_dev"] = "1"
    return a.run(timeout=60)


def test_runtime_real_mode_writes_no_session_state_beyond_listed_ui2_keys(session_write_log):
    at = _at(dev=True)
    # 紀錄器確實掛在 AppTest runtime 上：殼首跑寫入的預設 ui2_ 鍵必須被記到（否則下面的「0 次」不算數）
    assert ("__setitem__", "ui2_feed") in session_write_log and ("__setitem__", "ui2_page") in session_write_log
    assert {k for _, k in session_write_log} <= ALLOWED_UI2_WRITES, session_write_log
    at.selectbox(key="ui2_feed").set_value("real").run(timeout=60)
    session_write_log.clear()                                 # 從 Real 模式開始計：四頁＋模式切換
    for p in PAGE_IDS:
        at.radio(key="ui2_page").set_value(p).run(timeout=60)
        assert not at.exception, f"{p}: {at.exception}"
        if p == P4_TARGET:                                   # 標的頁再切『即時查一檔』（widget 狀態，不經 proxy）
            at.radio(key="ui2_target_mode").set_value("lookup").run(timeout=60)
            assert not at.exception
    assert session_write_log == [], f"Real 模式期間出現 session 寫入：{session_write_log}"
    assert set(at.session_state.filtered_state) <= ALLOWED_UI2_WRITES


def test_runtime_recorder_has_teeth(session_write_log):
    """mutation：feed 若寫 session（例：`get_allocation` 的 `_alloc_*` 快取），紀錄器必抓到。"""
    session_write_log.clear()
    from streamlit.runtime.state.session_state_proxy import SessionStateProxy
    import streamlit as st
    try:
        SessionStateProxy.__setitem__(st.session_state, "_alloc_decision_cache", 1)
    except Exception:          # bare 模式無 ScriptRunContext 可能丟例外；紀錄已先寫入
        pass
    assert ("__setitem__", "_alloc_decision_cache") in session_write_log


def test_bare_read_writes_no_session_state(session_write_log):
    RF.read_real_snapshot()
    _vms(RF.read_real_snapshot())
    assert session_write_log == []


_SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", "node_modules"}


def _fs_fingerprint() -> dict:
    """`data_cache/**`＋狀態檔：mtime＋sha256；其餘整個工作樹（含 git 忽略的檔，比 `git status` 更嚴）：mtime＋size。
    純 Python（⛔ 外部程式；tests/test_zz_test_portability.py）。"""
    fp: dict[str, tuple | None] = {}
    for p in sorted((ROOT / "data_cache").rglob("*")):
        if p.is_file():
            fp[p.relative_to(ROOT).as_posix()] = (p.stat().st_mtime_ns, hashlib.sha256(p.read_bytes()).hexdigest())
    for name in ("macro_state.json", "risk_cap_state.json", "macro_state.json.tmp"):
        p = ROOT / name
        fp[name] = (p.stat().st_mtime_ns, hashlib.sha256(p.read_bytes()).hexdigest()) if p.exists() else None
    tree: dict[str, tuple] = {}
    for p in ROOT.rglob("*"):
        rel = p.relative_to(ROOT)
        if any(part in _SKIP_DIRS for part in rel.parts) or not p.is_file():
            continue
        st_ = p.stat()
        tree[rel.as_posix()] = (st_.st_mtime_ns, st_.st_size)
    fp["__worktree__"] = tuple(sorted(tree.items()))
    return fp


def test_filesystem_unchanged_by_real_feed_and_real_mode_pages(monkeypatch):
    monkeypatch.chdir(ROOT)
    before = _fs_fingerprint()
    RF.read_real_snapshot()
    at = _at(dev=True)
    at.selectbox(key="ui2_feed").set_value("real").run(timeout=60)
    for p in PAGE_IDS:
        at.radio(key="ui2_page").set_value(p).run(timeout=60)
    assert not at.exception
    after = _fs_fingerprint()
    wt_b, wt_a = dict(before.pop("__worktree__")), dict(after.pop("__worktree__"))
    assert wt_a == wt_b, {k: (wt_b.get(k), wt_a.get(k)) for k in set(wt_b) | set(wt_a) if wt_b.get(k) != wt_a.get(k)}
    assert after == before, {k: (before.get(k), after.get(k)) for k in set(before) | set(after)
                             if before.get(k) != after.get(k)}


@pytest.fixture
def no_network(monkeypatch):
    attempts: list[str] = []

    def deny(*a, **k):
        attempts.append(repr(a)[:120])
        raise OSError("network disabled by test (NUI2-REAL-FEED no-network proof)")
    monkeypatch.setattr(socket.socket, "connect", deny)
    monkeypatch.setattr(socket.socket, "connect_ex", deny)
    monkeypatch.setattr(socket, "create_connection", deny)
    return attempts


def test_real_feed_makes_no_network_connection(no_network):
    snap = RF.read_real_snapshot()
    _vms(snap)
    assert no_network == [], no_network
    assert snap.twii is not None and snap.twii_error == ""        # 真讀本地檔仍成功（不是因為被擋才「沒連」）
    assert snap.regime is not None or snap.regime_error


def test_network_guard_has_teeth(no_network):
    with pytest.raises(OSError):
        socket.create_connection(("127.0.0.1", 9))
    assert no_network


# ════════════════════════════════════════════════════════════════════
# §7 AppTest：預設 FAKE 不變；Real 模式四頁
# ════════════════════════════════════════════════════════════════════
def _blob(at) -> str:
    return "\n".join(m.value for m in at.markdown)


def test_default_feed_is_still_fake():
    at = _at()
    assert not at.exception and at.session_state["ui2_feed"] == "fake"
    assert T.PREVIEW_BANNER_TEXT in _blob(at) and T.REAL_PREVIEW_BANNER_TEXT not in _blob(at)


def test_real_mode_renders_every_page_with_the_real_banner(monkeypatch):
    from src.ui2.shell import app as shell
    n = {"reads": 0}
    orig = shell.read_real_snapshot

    def counted():
        n["reads"] += 1
        return orig()
    monkeypatch.setattr(shell, "read_real_snapshot", counted)
    at = _at(dev=True)
    assert n["reads"] == 0                                     # FAKE 預設：不讀真資料
    at.selectbox(key="ui2_feed").set_value("real").run(timeout=60)
    for p in PAGE_IDS:
        before = n["reads"]
        at.radio(key="ui2_page").set_value(p).run(timeout=60)
        assert n["reads"] - before == 1, f"{p}: 一次 rerun 應只讀一次"
        blob = _blob(at)
        assert not at.exception
        assert T.REAL_PREVIEW_BANNER_TEXT in blob and T.REAL_PREVIEW_BANNER_NOTE in blob
        assert T.PREVIEW_BANNER_TEXT not in blob and "FAKE" not in blob
        assert blob.count('class="ui2-banner"') == 1           # P1：單行標示，只此一個
        assert f'data-ui2-scenario="{SCENARIO_REAL}"' in blob
    at.radio(key="ui2_page").set_value(P4_MARKET).run(timeout=60)
    assert 'data-card-id="twii"' in _blob(at)
    assert at.selectbox(key="ui2_scenario").disabled and at.selectbox(key="ui2_account").disabled
    # Real 模式：Preview 控制標題與（disabled）帳戶 widget 不顯示 fake 字樣（QA P3）
    # P1：Preview 控制已不是頁面 expander，而是 `?ui2_dev=1` 的開發面（虛線框區塊）；舊斷言「expander 標題」已隨之改為斷言
    # 開發面標題與控制 label：Real 模式不得顯示 fake 字樣（資料誠實性）。位置規則見 tests/test_ui2_contract_teeth_pending.py。
    assert [e.label for e in at.expander if e.label.startswith("Preview 控制")] == []
    assert "開發／測試工具（非產品內容）" in _blob(at)
    labels = [at.selectbox(key=k).label for k in ("ui2_feed", "ui2_scenario", "ui2_account")]
    assert all("fake" not in lb.lower() for lb in labels), labels


# ════════════════════════════════════════════════════════════════════
# §8 viewport 判定器（real 模式）teeth
# ════════════════════════════════════════════════════════════════════
_EVID = ROOT / "docs" / "vnext" / "newui2_realfeed"


def _evidence(name="viewport_measurements.json") -> dict:
    import json
    return json.loads((_EVID / name).read_text(encoding="utf-8"))


def test_real_threshold_registered_with_source():
    t = next(x for x in MV.THRESHOLDS if x["id"] == "real_feed_banner_on_top")
    assert "客戶 (11)" in t["source"]


@pytest.mark.parametrize("name", ["viewport_measurements.json", "viewport_measurements_streamlit156.json"])
def test_real_viewport_evidence_passed_and_is_real_mode(name):
    d = _evidence(name)
    assert d["meta"]["feed"] == "real"
    assert d["summary"]["failed"] == [] and d["summary"]["states"] == 11
    pages = {(r["viewport_name"], r["page"], r.get("mode")) for r in d["results"]}
    for vp in ("mobile", "desktop"):
        for p in PAGE_IDS:
            assert any(k[0] == vp and k[1] == p for k in pages)
    for r in d["results"]:
        if r.get("mode") != "stress":
            assert r["banner_text"].startswith(T.REAL_PREVIEW_BANNER_TEXT)


def _real_market_m() -> dict:
    d = _evidence()
    r = next(x for x in d["results"] if x["viewport_name"] == "mobile" and x["page"] == P4_MARKET
             and x.get("mode") is None)
    return r


def test_real_banner_evaluator_has_teeth():
    r = _real_market_m()
    base = _full_from_evidence(r)
    base.update(feed="real", banner_text=r["banner_text"])

    def fails(**kw):
        return MV.evaluate({**copy.deepcopy(base), **kw})["real_feed_banner_on_top"]
    assert fails() == []
    assert fails(banner_text=T.PREVIEW_BANNER_TEXT + " x")                    # FAKE 標示 → 紅
    assert fails(banner_text=None)                                             # 缺 banner → 紅
    assert fails(title=dict(base["title"], banner_bottom=base["title"]["top"] + 30))   # 不在頁首 → 紅
    assert MV.evaluate({**copy.deepcopy(base), "feed": "fake", "banner_text": None})["real_feed_banner_on_top"] == []


def _full_from_evidence(r: dict) -> dict:
    """由證據 JSON 的 mobile 市場頁量測組回 `evaluate()` 需要的 dict（缺的導覽細節以合法值補，只為驗 banner 判定）。"""
    nav = dict(r["nav"])
    nav.update(labels=list(MV.NAV_LABELS), label_tops=[nav["top"] + 2] * 4, label_lefts=[0, 97, 195, 292],
               label_heights=[50] * 4, checked_count=1, checked_index=0,
               marker_contents=['"● "', "none", "none", "none"])
    b3 = r["batch3"]
    return {"viewport": r["viewport"], "page": r["page"], "scenario": r["scenario"], "nav": nav,
            "elements": r["elements"], "hscroll": r["hscroll"], "title": r["title"],
            "last_content": {"bottom": r["last_content_bottom"], "left": 14.0},
            "risk": b3["risk"], "first_block_after_l1_top": b3["first_block_after_l1_top"],
            "risk_line_height": b3["risk_line_height"], "scroll_end_bottom": b3["scroll_end_bottom"]}


def test_real_me_evaluator_rejects_a_pretend_account():
    d = _evidence()
    r = next(x for x in d["results"] if x["viewport_name"] == "mobile" and x["page"] == P4_ME)
    m = _full_from_evidence(r)
    m.update(feed="real", banner_text=r["banner_text"], account=None)
    assert MV.evaluate(m)["me_account_state_first_screen"] == []
    m2 = dict(m, account={"top": 300.0, "bottom": 340.0, "state": "signed_in"})
    assert MV.evaluate(m2)["me_account_state_first_screen"]


# ════════════════════════════════════════════════════════════════════
# §9 只有已接事實可帶值（白名單不變量；QA 2026-11-03 必修 1）——跑在注入組合上，不只 sandbox 實況
# ════════════════════════════════════════════════════════════════════
#: 允許帶「資料」（value／source／as_of／資料語意或判定態）的欄位：以 **VM 位置路徑**判斷（⛔ 用 label；複驗 P3-2）。
WIRED_PATHS = frozenset({
    (P4_MARKET, "cards/twii"), (P4_MARKET, "first/current_state"), (P4_MARKET, "sections/why/0"),
    (P4_TARGET, "first/context_rows/0"), (P4_TARGET, "lookup/snapshot/5"),
})
#: 契約固定欄（位置 → 期望態／字樣）；無值、無 source／as_of。
FIXED_PATHS: dict[tuple[str, str], tuple[object, str]] = {
    (P4_MARKET, "first/context_rows/0"): (JudgementState.UNDETERMINABLE, T.TEXT_RISK_CAP_UNDETERMINABLE),
    (P4_TARGET, "first/context_rows/1"): (JudgementState.UNDETERMINABLE, T.TEXT_RISK_CAP_UNDETERMINABLE),
    (P4_HOLD, "first/context_rows/0"): (JudgementState.UNDETERMINABLE, T.TEXT_RISK_CAP_UNDETERMINABLE),
    (P4_HOLD, "first/context_rows/1"): (FieldState.MISSING, T.TEXT_MISSING_NOT_READY),
    (P4_TARGET, "lookup/snapshot/3"): (FieldState.NOT_EVALUATED, T.TEXT_NOT_DEFINED),
    (P4_TARGET, "lookup/snapshot/4"): (FieldState.NOT_EVALUATED, T.TEXT_NOT_DEFINED),
}
#: 未接線欄位的原因句不得出現數字樣式（防「把捏造值藏進原因句」）；原因句的合法數字（如「Top 10」「末 6 碼」）不是小數／百分比。
_NUMBER_LIKE = re.compile(r"\d+\.\d+|\d+\s*[%％]")


def _paths(vm: PageVM):
    fs = vm.context.first_screen
    yield "first/current_state", fs.current_state
    yield "first/action_needed", fs.action_needed
    yield "first/next_step", fs.next_step
    for i, f in enumerate(fs.context_rows):
        yield f"first/context_rows/{i}", f
    if fs.conclusion is not None:
        yield "first/conclusion", fs.conclusion
    if vm.context.main_risk is not None:
        yield "main_risk", vm.context.main_risk
    for c in vm.context.cards:
        yield f"cards/{c.card_id}", c.field
    for sec in vm.context.sections:
        for i, f in enumerate(sec.fields):
            yield f"sections/{sec.section_id}/{i}", f
    t = vm.context.target
    if t is not None:
        yield "search/name_search", t.search.name_search
        yield "lookup/summary", t.lookup.summary
        for i, f in enumerate(t.lookup.snapshot):
            yield f"lookup/snapshot/{i}", f
        for sec in t.lookup.sections:
            for i, f in enumerate(sec.fields):
                yield f"lookup/sections/{sec.section_id}/{i}", f


def check_only_wired_fields_carry_data(vms: dict[str, PageVM]) -> list[str]:
    bad: list[str] = []
    for page, vm in vms.items():
        for c in vm.context.cards:
            if c.chips and (page, f"cards/{c.card_id}") not in WIRED_PATHS:
                bad.append(f"{page}/cards/{c.card_id}: 未接線卡帶 chip")
        for path, f in _paths(vm):
            key = (page, path)
            if key in WIRED_PATHS:
                continue
            blank = f.value_text is None and f.freshness.source is None and f.freshness.as_of is None
            if key in FIXED_PATHS:
                st_, txt = FIXED_PATHS[key]
                if not (blank and f.state is st_ and f.status_text == txt):
                    bad.append(f"{page}/{path}（{f.label}）: 契約固定欄被改（state={f.state!r} value={f.value_text!r}）")
                continue
            if not (blank and f.capability is CapabilityState.NOT_PROVIDED and f.detail):
                bad.append(f"{page}/{path}（{f.label}）: 未接線欄位帶資料或缺原因（value={f.value_text!r} "
                           f"source={f.freshness.source!r} as_of={f.freshness.as_of!r} state={f.state!r}）")
            elif _NUMBER_LIKE.search(f.detail):
                bad.append(f"{page}/{path}（{f.label}）: 未接線欄位原因句含數字樣式 {f.detail!r}")
    return bad


_TWII_COMBOS = {
    "ok": dict(twii=_twii_view()),
    "missing": dict(twii=_twii_view(ok=False, close=(), as_of=None, error="讀不到")),
    "failed": dict(twii=_twii_view(ok=False, close=(), as_of=None, failed=True, error="OSError: x")),
    "stale": dict(twii=_twii_view(is_stale=True, age_days=5)),
    "stale_none": dict(twii=_twii_view(is_stale=None, age_days=None)),
    "exception": dict(twii_exc=RuntimeError("x")),
    "contract": dict(twii=_twii_view(close=())),
}
_REGIME_COMBOS = {
    "unloaded": dict(regime=_regime()),
    "breadth": dict(regime=_regime(source=RA.SOURCE_UNEVALUATED_BREADTH)),
    "failed": dict(regime_exc=RuntimeError("x")),
    "loaded_bull": dict(regime=_regime("bull", RA.SOURCE_BULL_SCORE, True, exposure_limit_pct=40)),
    "loaded_bear": dict(regime=_regime("bear", RA.SOURCE_BEAR_TREND, True)),
    "contract": dict(regime=_regime(source="mystery:branch")),
}


@pytest.mark.parametrize("tw", list(_TWII_COMBOS))
@pytest.mark.parametrize("rg", list(_REGIME_COMBOS))
def test_only_wired_fields_carry_data_across_injected_combinations(monkeypatch, tw, rg):
    snap = _feed(monkeypatch, **_TWII_COMBOS[tw], **_REGIME_COMBOS[rg])
    assert check_only_wired_fields_carry_data(_vms(snap)) == []


def test_only_wired_fields_carry_data_on_sandbox_reality():
    assert check_only_wired_fields_carry_data(_vms(RF.read_real_snapshot())) == []


@pytest.mark.parametrize("fake_value", ["0.00", "18.20"])
def test_whitelist_checker_has_teeth_against_a_fabricated_vix(monkeypatch, fake_value):
    """mutation：VIX 捏造值＋as_of＋source（例：補 0／中性或抄 FAKE 值）→ 檢查器必紅。"""
    orig = RC._market

    def fabricated(snap):
        c = orig(snap)
        c["cards"] = [({"key": "vix", "label": "VIX", "value": fake_value, "as_of": "2026-11-02", "source": "x"}
                       if x["key"] == "vix" else x) for x in c["cards"]]
        return c
    monkeypatch.setattr(RC, "_market", fabricated)
    bad = check_only_wired_fields_carry_data(_vms(_feed(monkeypatch)))
    assert any("VIX" in b for b in bad), bad


def test_whitelist_checker_is_by_position_not_label(monkeypatch):
    """複驗 P3-2：把未接線卡改名成「台股」也騙不過（以位置判斷）。"""
    orig = RC._market

    def relabeled(snap):
        c = orig(snap)
        c["cards"] = [({"key": "vix", "label": "台股", "value": "18.20", "as_of": "2026-11-02", "source": "x"}
                       if x["key"] == "vix" else x) for x in c["cards"]]
        return c
    monkeypatch.setattr(RC, "_market", relabeled)
    assert any("cards/vix" in b for b in check_only_wired_fields_carry_data(_vms(_feed(monkeypatch))))


@pytest.mark.parametrize("hidden", ["VIX 約 18.20", "利差 0.5%", "PMI 50.0"])
def test_whitelist_checker_rejects_numbers_hidden_in_reasons(monkeypatch, hidden):
    orig = RC._market

    def sneaky(snap):
        c = orig(snap)
        c["cards"] = [({**x, "reason": f"尚未接線（{hidden}）"} if x["key"] == "vix" else x) for x in c["cards"]]
        return c
    monkeypatch.setattr(RC, "_market", sneaky)
    assert any("數字樣式" in b for b in check_only_wired_fields_carry_data(_vms(_feed(monkeypatch))))


def test_whitelist_checker_has_teeth_against_a_valued_fixed_field(monkeypatch):
    orig = RC._risk_cap_row
    monkeypatch.setattr(RC, "_risk_cap_row", lambda: {**orig(), "value": "50%", "state": None})
    assert check_only_wired_fields_carry_data(_vms(_feed(monkeypatch)))


# ════════════════════════════════════════════════════════════════════
# §10 錯誤字串不上畫面（QA 2026-11-03 必修 2；NUI2-REALFEED-ERROR-SCRUB 收斂）
# ════════════════════════════════════════════════════════════════════
_SECRET = "token=SECRET123"


def _rendered_blob(vms: dict[str, PageVM]) -> str:
    return "\n".join(s for vm in vms.values() for s in _all_strings(vm))


@pytest.mark.parametrize("inject", [
    dict(twii=_twii_view(upstream_error=f"https://x.example/q?{_SECRET}")),
    dict(twii=_twii_view(ok=False, close=(), as_of=None, failed=True, error=f"OSError: /home/u/{_SECRET}")),
    dict(twii=_twii_view(ok=False, close=(), as_of=None, error=f"bad {_SECRET}")),
    dict(twii_exc=RuntimeError(f"fetch {_SECRET}")),
    dict(regime_exc=RuntimeError(f"macro_state.json {_SECRET}")),
    dict(regime=_regime(file_error=f"risk_cap_state.json {_SECRET}")),
    dict(regime=_regime(source=f"mystery {_SECRET}")),
])
def test_error_details_never_reach_the_screen_but_are_logged(monkeypatch, capsys, inject):
    snap = _feed(monkeypatch, **inject)
    assert _SECRET not in repr(snap)                                   # snapshot 本身就不收原文
    assert _SECRET not in _rendered_blob(_vms(snap))                   # 畫面不含
    assert _SECRET in capsys.readouterr().out                          # 全文只進 log


def test_upstream_error_is_shown_as_a_fixed_sentence(monkeypatch):
    f = _twii_field(_feed(monkeypatch, twii=_twii_view(upstream_error="x" * 5000)))
    assert f.detail == "上游最近一次抓取失敗" and f.state is FieldState.OK


def test_on_screen_error_text_is_bounded_even_for_huge_messages(monkeypatch):
    vms = _vms(_feed(monkeypatch, twii_exc=RuntimeError("y" * 10000), regime_exc=OSError("z" * 10000)))
    for f in (vms[P4_MARKET].context.cards[0].field, vms[P4_MARKET].context.first_screen.current_state):
        assert f.state is FieldState.UNAVAILABLE and len(f.detail) < 80 and "yyy" not in f.detail


def test_service_error_type_is_bounded_and_regex_checked():
    assert RF._type_of_service_error("OSError: disk") == "OSError"
    assert RF._type_of_service_error("bad name: x") == "ServiceError"
    assert RF._type_of_service_error("A" * 200 + ": x") == "ServiceError"
    assert RF._type_of_service_error("") == "ServiceError"


def test_exception_code_uses_class_name_without_dunder_access():
    import json as _json
    assert RC.exception_code(RuntimeError("x")) == "RuntimeError"
    assert RC.exception_code(_json.JSONDecodeError("m", "d", 0)) == "JSONDecodeError"
    assert RC.exception_code(RC.RealFeedContractError("x")) == RC.CONTRACT_ERROR == RC.RealFeedContractError.__name__

