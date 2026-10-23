"""DEC-074 B／DEC-075 批 A（客戶 2026-10-23）—— 代理廣度不計分、健康分／位階未評估、MA200 不以現價頂替。

計畫：`docs/vnext/DATA_HEALTH_REPAIR_PLAN_2026-10-23.md` §1.7「新測試」。
不變量（計畫 §1.1）：
  I-1 任何計分路徑不得吃 proxy breadth 數值；
  I-2 breadth 缺席 ⇒ 健康分 None（不是 0、不是 50、不是只剩大盤分重新歸一）；
  I-3 健康分 None ⇒ 姿態帶不給結論；
  I-4 「⬜ 未評估」文案不得暗示「重跑就會有」；
  I-5 proxy 值可以顯示，但須帶代理標記。

每一組都附**突變測試**（v3 §03-1「拔掉修復邏輯必須轉為紅燈」）：用 monkeypatch 把修復邏輯拔掉，
斷言同一支檢查函式在突變下**會失敗**（＝守衛真的守到東西，不是恆真式）。
"""
from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import pandas as pd
import pytest

REPO = Path(__file__).resolve().parents[1]

#: I-4：未評估文案不得出現的「重跑就會有」指引字樣。
_RETRY_PHRASES = ("重新抓取", "重新載入", "一鍵更新")


# ══════════════════════════════════════════════════════════════════
# 1. L2 calc_traffic_light：代理旌旗 ⇒ 健康分未評估
# ══════════════════════════════════════════════════════════════════
_MKT = {"score": 3, "max_score": 4, "regime": "bull"}


def _tl(jq):
    from src.compute.macro.macro_helpers import calc_traffic_light
    return calc_traffic_light(dict(_MKT), jq, {}, None)


def _check_proxy_jingqi_unevaluated() -> None:
    from shared.regime_arbiter import SOURCE_UNEVALUATED_BREADTH
    tl = _tl({"avg": 55.0, "is_proxy": True, "source": "ADL"})
    assert tl["jqavg"] is None
    assert tl["health"] is None
    assert tl["light"] == "⬜"
    assert tl["effective_regime"] == "unknown"
    assert tl["regime_source"] == SOURCE_UNEVALUATED_BREADTH
    assert tl["health_partial"] is True
    assert tl["health_unavailable_reason"] == "breadth"
    assert any("廣度" in m for m in tl["missing_sources"]), tl["missing_sources"]


class TestCalcTrafficLightBreadthGate:
    def test_proxy_jingqi_unevaluated(self):
        _check_proxy_jingqi_unevaluated()

    def test_real_jingqi_still_scores(self):
        """無旗標（＝真值）照舊計分，逐位同修前公式（零回歸）。"""
        from shared.signal_thresholds import HEALTH_WEIGHT_JQ, HEALTH_WEIGHT_SCORE
        tl = _tl({"avg": 55.0})
        assert tl["health"] == pytest.approx(
            round(55.0 * HEALTH_WEIGHT_JQ + 75.0 * HEALTH_WEIGHT_SCORE, 1))
        assert tl["health_unavailable_reason"] is None

    def test_missing_jingqi_not_renormalised(self):
        """I-2：旌旗整包缺席 ⇒ None，⛔ 不是只剩大盤分 75（舊歸一）、⛔ 不是 60（舊捏 50）。"""
        tl = _tl(None)
        assert tl["health"] is None

    def test_both_legs_missing_stays_unloaded(self):
        """大盤評分也缺 ⇒ 既有 SOURCE_UNLOADED（其餘輸入也缺，重抓仍可能補上），不冒充 breadth 原因。"""
        from shared.regime_arbiter import SOURCE_UNLOADED
        from src.compute.macro.macro_helpers import calc_traffic_light
        tl = calc_traffic_light({}, {"avg": 55.0, "is_proxy": True}, {"x": 1}, None)
        assert tl["health"] is None
        assert tl["regime_source"] == SOURCE_UNLOADED

    def test_score_missing_real_jingqi_keeps_d3_renormalisation(self):
        """D-3（內部拍板）：大盤評分缺席而旌旗真值在 ⇒ 既有歸一不動（非受 breadth 影響）。"""
        from src.compute.macro.macro_helpers import calc_traffic_light
        tl = calc_traffic_light({"regime": "neutral"}, {"avg": 55.0}, {"x": 1}, None)
        assert tl["health"] == pytest.approx(55.0)

    def test_mutant_remove_jingqi_for_scoring_turns_red(self, monkeypatch):
        """突變：`jingqi_for_scoring` 換回直讀（不擋代理）⇒ 檢查必紅。"""
        import src.compute.macro.macro_helpers as MH
        monkeypatch.setattr(MH, "_jingqi_for_scoring", lambda info: info)
        with pytest.raises(AssertionError):
            _check_proxy_jingqi_unevaluated()

    def test_mutant_scoring_flag_on_turns_red(self, monkeypatch):
        """突變：L0 計分開關翻 True ⇒ 代理又進健康分 ⇒ 檢查必紅（開關真的是開關）。"""
        import shared.signal_thresholds as STH
        monkeypatch.setattr(STH, "BREADTH_PROXY_SCORING_ENABLED", True)
        with pytest.raises(AssertionError):
            _check_proxy_jingqi_unevaluated()


# ══════════════════════════════════════════════════════════════════
# 2. 文案守衛（I-4）
# ══════════════════════════════════════════════════════════════════
class TestCopyNeverSaysRetry:
    def test_traffic_light_copy(self):
        from shared.regime_arbiter import SOURCE_UNEVALUATED_BREADTH
        from src.compute.macro.macro_helpers import _TL_COPY_BY_SOURCE
        _txt = "".join(str(x) for x in _TL_COPY_BY_SOURCE[SOURCE_UNEVALUATED_BREADTH])
        assert not any(p in _txt for p in _RETRY_PHRASES), _txt
        assert "未評估" in _txt and "DEC-074" in _txt

    def test_page_today_breadth_copy(self):
        from src.ui.views import page_today as P
        for _txt in (P.EXIT_WAIT_BREADTH_SOURCE, P.BREADTH_UNEVALUATED_WHY):
            assert not any(p in _txt for p in _RETRY_PHRASES), _txt
        assert P.EXIT_WAIT_BREADTH_SOURCE in dict(P.V2_EXIT_PHRASES), "出口未登記短語（渲染當下會 KeyError）"

    def test_old_ui_handler_no_false_renormalisation_claim(self):
        """舊 UI handlers：health 為 None 的分支不得再說「權重已重新歸一化」（只改字）。"""
        src = (REPO / "src/ui/tabs/macro/handlers.py").read_text(encoding="utf-8")
        fn = next(n for n in ast.walk(ast.parse(src))
                  if isinstance(n, ast.FunctionDef) and n.name == "_render_traffic_light")
        seg = "\n".join(l for l in ast.get_source_segment(src, fn).splitlines()
                        if not l.lstrip().startswith("#"))
        assert "綜合健康度未評估" in seg
        # 「重新歸一化」只能出現在 health 有值（D-3 大盤分缺席）的那一支
        assert seg.count("權重已重新歸一化") == 1


# ══════════════════════════════════════════════════════════════════
# 3. L3 jingqi_calc：寫 is_proxy
# ══════════════════════════════════════════════════════════════════
def _run_jingqi(monkeypatch, df_adl, cl_data=None):
    from types import SimpleNamespace

    from src.services import jingqi_calc as J
    _stub = SimpleNamespace(session_state={})
    if cl_data is not None:
        _stub.session_state["cl_data"] = cl_data
    monkeypatch.setattr(J, "st", _stub)
    J.compute_and_store_jingqi(df_adl)
    return _stub.session_state.get("jingqi_info")


def _check_jingqi_flags(monkeypatch) -> None:
    info = _run_jingqi(monkeypatch, pd.DataFrame(
        {"ad_ratio": [50.0, 52.0, 54.0, 56.0, 58.0], "is_proxy": [True] * 5}))
    assert info["is_proxy"] is True
    assert info["avg"] == pytest.approx(54.0)      # I-5：值照算供顯示


class TestJingqiCalcFlag:
    def test_proxy_df_flagged_avg_kept(self, monkeypatch):
        _check_jingqi_flags(monkeypatch)

    def test_real_rows_not_flagged(self, monkeypatch):
        info = _run_jingqi(monkeypatch, pd.DataFrame(
            {"ad_ratio": [50.0, 52.0, 54.0, 56.0, 58.0, 60.0],
             "is_proxy": [True, False, False, False, False, False]}))
        assert info["is_proxy"] is False           # 被平均的 5 列全為真值

    def test_missing_column_fail_safe(self, monkeypatch):
        info = _run_jingqi(monkeypatch, pd.DataFrame({"ad_ratio": [50.0, 60.0]}))
        assert info["is_proxy"] is True

    def test_twii_estimate_flagged(self, monkeypatch):
        twii = pd.DataFrame({"close": [100.0, 101.0, 102.0, 101.5, 103.0, 104.0]})
        info = _run_jingqi(monkeypatch, None, cl_data={"tw": {"台股加權指數": twii}})
        assert info["source"] == "大盤估算" and info["is_proxy"] is True

    def test_mutant_drop_flag_write_turns_red(self, monkeypatch):
        """突變：旗標判定恆回 False（等同拿掉旗標寫入）⇒ 檢查必紅。"""
        from src.services import jingqi_calc as J
        monkeypatch.setattr(J, "adl_rows_any_proxy", lambda df, n: False)
        with pytest.raises(AssertionError):
            _check_jingqi_flags(monkeypatch)


# ══════════════════════════════════════════════════════════════════
# 4. L3 market_assessment_apply／market_regime：代理 ad_ratio 不計分
# ══════════════════════════════════════════════════════════════════
def _regime(**kw):
    from src.services.market_strategy import market_regime
    return market_regime(17000.0, 16000.0, 15500.0, 1e9, **kw)


def _check_market_regime_proxy() -> None:
    r = _regime(ad_ratio=70.0, ad_ratio_is_proxy=True)
    assert r["max_score"] == 4.0
    assert "市場廣度" not in r["missing_factors"]
    assert any("代理" in s and "不計分" in s and "70.0%" in s for s in r["signals"]), r["signals"]


def _apply_capture(monkeypatch, df_adl):
    from types import SimpleNamespace

    import src.services.market_assessment_apply as maa
    captured: dict = {}

    def _fake_gma(**kw):
        captured.update(kw)
        return {"signals": [], "label": "x", "score": 1}
    monkeypatch.setattr("src.services.get_market_assessment", _fake_gma)
    monkeypatch.setattr(maa, "st", SimpleNamespace(session_state={}))
    maa.compute_and_apply_market_assessment(
        inst={"外資及陸資": {"net": 10.0}},
        tw_raw={"台股加權指數": pd.DataFrame({"close": [1.0]})}, margin=None, df_adl=df_adl)
    return captured


def _check_apply_proxy(monkeypatch) -> None:
    cap = _apply_capture(monkeypatch, pd.DataFrame({"ad_ratio": [40.0, 61.0], "is_proxy": [True, True]}))
    assert cap["ad_ratio"] is None
    assert cap["ad_ratio_is_proxy"] is True
    assert cap["ad_ratio_display"] == pytest.approx(61.0)


class TestMarketRegimeBreadthGate:
    def test_market_regime_proxy_not_scored(self):
        _check_market_regime_proxy()
        r_real = _regime(ad_ratio=70.0)
        assert r_real["max_score"] == 5.0          # 真值照舊進分母

    def test_apply_forwards_proxy_as_display_only(self, monkeypatch):
        _check_apply_proxy(monkeypatch)

    def test_apply_missing_column_fail_safe(self, monkeypatch):
        cap = _apply_capture(monkeypatch, pd.DataFrame({"ad_ratio": [40.0, 61.0]}))
        assert cap["ad_ratio"] is None and cap["ad_ratio_is_proxy"] is True

    def test_mutant_scoring_flag_on_turns_red(self, monkeypatch):
        """突變：拿掉 is_proxy 判斷（L3 端開關恆開）⇒ max_score 回 5 ⇒ 必紅。"""
        import src.services.market_strategy as MS
        monkeypatch.setattr(MS, "BREADTH_PROXY_SCORING_ENABLED", True)
        with pytest.raises(AssertionError):
            _check_market_regime_proxy()

    def test_mutant_apply_is_proxy_check_removed_turns_red(self, monkeypatch):
        import src.services.market_assessment_apply as maa
        monkeypatch.setattr(maa, "adl_df_is_proxy", lambda df: False)
        with pytest.raises(AssertionError):
            _check_apply_proxy(monkeypatch)


# ══════════════════════════════════════════════════════════════════
# 5. L3 get_macro_state：D-1(a) breadth 原因不退檔案位階（MUST-A1）
# ══════════════════════════════════════════════════════════════════
@pytest.fixture
def _fresh_file(tmp_path):
    from src.services.macro_state_locker import _now_str
    p = tmp_path / "macro_state.json"
    p.write_text(json.dumps({"market_regime": "多頭", "exposure_limit_pct": 60,
                             "timestamp": _now_str()}, ensure_ascii=False), encoding="utf-8")
    return str(p)


def _check_breadth_no_file_fallback(path: str) -> None:
    from shared.regime_arbiter import SOURCE_UNEVALUATED_BREADTH
    from src.services.macro_state_locker import get_macro_state
    st = get_macro_state({"health_score": None, "regime_source": SOURCE_UNEVALUATED_BREADTH},
                         state_file_path=path)
    assert st["regime"] == "unknown"
    assert st["is_loaded"] is False
    assert st["source"] == SOURCE_UNEVALUATED_BREADTH
    assert st["health"] is None


class TestGetMacroStateD1a:
    def test_breadth_reason_no_file_fallback(self, _fresh_file):
        _check_breadth_no_file_fallback(_fresh_file)

    def test_strict_does_not_raise(self, _fresh_file):
        from shared.regime_arbiter import SOURCE_UNEVALUATED_BREADTH
        from src.services.macro_state_locker import get_macro_state
        st = get_macro_state({"health_score": None, "regime_source": SOURCE_UNEVALUATED_BREADTH},
                             state_file_path=_fresh_file, strict=True)
        assert st["regime"] == "unknown" and st["is_loaded"] is False

    def test_other_reason_still_falls_back_to_file(self, _fresh_file):
        """非 breadth 原因（F1 三源全敗 = SOURCE_UNLOADED）⇒ 照舊退檔案位階（C1 v19.182 其餘語意）。"""
        from shared.regime_arbiter import SOURCE_FILE_RULE_ENGINE, SOURCE_UNLOADED
        from src.services.macro_state_locker import get_macro_state
        st = get_macro_state({"health_score": None, "regime_source": SOURCE_UNLOADED},
                             state_file_path=_fresh_file)
        assert st["source"] == SOURCE_FILE_RULE_ENGINE and st["is_loaded"] is True
        assert st["regime"] == "bull"

    def test_allocation_unevaluated(self, _fresh_file):
        """I-3：位階未評估 ⇒ 姿態帶不給結論（既有路徑）。"""
        from shared.allocation_decision import build_allocation_decision
        from shared.regime_arbiter import SOURCE_UNEVALUATED_BREADTH
        from src.services.macro_state_locker import get_macro_state
        st = get_macro_state({"health_score": None, "regime_source": SOURCE_UNEVALUATED_BREADTH},
                             state_file_path=_fresh_file)
        d = build_allocation_decision(st)
        assert d.is_loaded is False and d.icon == "⬜"

    def test_mutant_remove_reason_guard_turns_red(self, _fresh_file, monkeypatch):
        """突變：移除原因判斷（常數對不上 ⇒ 守衛失效）⇒ 退回檔案位階 ⇒ 必紅。"""
        import shared.regime_arbiter as RA
        _orig = RA.SOURCE_UNEVALUATED_BREADTH
        monkeypatch.setattr(RA, "SOURCE_UNEVALUATED_BREADTH", "__mutant__")
        from src.services.macro_state_locker import get_macro_state
        st = get_macro_state({"health_score": None, "regime_source": _orig},
                             state_file_path=_fresh_file)
        assert st["regime"] == "bull"           # 突變下確實退檔（守衛就是它擋的）
        with pytest.raises(AssertionError):
            _check_breadth_no_file_fallback(_fresh_file)


# ══════════════════════════════════════════════════════════════════
# 6. 五桶：jingqi／adl 代理 ⇒ 灰、顯示值帶徽章、側車 is_proxy
# ══════════════════════════════════════════════════════════════════
def _five(jq, adl_df):
    from src.compute.macro.macro_helpers import compute_five_bucket_summary
    rd: dict = {}
    out = compute_five_bucket_summary(jingqi_info=jq, cl_data={"adl": adl_df}, readiness_out=rd)
    det = {d["key"]: d for b in out.values() for d in b["details"]}
    return out, det, rd


def _check_five_bucket_proxy() -> None:
    from shared.macro_provenance import BREADTH_PROXY_VALUE_NOTE
    # 35 在兩盞的門檻下都是紅燈（low_bad：jingqi 紅 ≤40、adl 紅 ≤35）—— 代理時必須是灰。
    out, det, rd = _five({"avg": 35.0, "is_proxy": True},
                         pd.DataFrame({"ad_ratio": [35.0], "is_proxy": [True]}))
    for k in ("jingqi", "adl"):
        assert det[k]["danger"] == "gray", (k, det[k])
        assert det[k]["value_str"].endswith(BREADTH_PROXY_VALUE_NOTE), det[k]["value_str"]
        assert rd[k].get("is_proxy") is True
    assert out["chips"]["level"] != "red"


class TestFiveBucketBreadthGate:
    def test_proxy_lamps_gray(self):
        _check_five_bucket_proxy()

    def test_real_values_still_graded(self):
        _out, det, rd = _five({"avg": 35.0}, pd.DataFrame({"ad_ratio": [35.0], "is_proxy": [False]}))
        assert det["jingqi"]["danger"] == "red" and det["adl"]["danger"] == "red"
        assert "is_proxy" not in rd["jingqi"] and "is_proxy" not in rd["adl"]

    def test_v2_rows_gray_and_badge(self):
        """新 UI 指標危險度（`tab_macro_v2.build_rows`）讀同一個側車 —— 同樣灰、同樣帶註記。"""
        from shared.macro_provenance import BREADTH_PROXY_VALUE_NOTE
        from src.ui.tabs.tab_macro_v2 import build_rows
        _o, _d, rd = _five({"avg": 35.0, "is_proxy": True},
                           pd.DataFrame({"ad_ratio": [35.0], "is_proxy": [True]}))
        rows = {r.key: r for r in build_rows(rd)}
        for k in ("jingqi", "adl"):
            assert rows[k].band == "gray" and rows[k].value_note == BREADTH_PROXY_VALUE_NOTE

    def test_mutant_remove_gray_branch_turns_red(self, monkeypatch):
        """突變：拿掉五桶代理判定（`classify_danger(None)` 分支不觸發）⇒ 必紅。"""
        import shared.macro_provenance as MP
        monkeypatch.setattr(MP, "is_breadth_proxy", lambda info: False)
        monkeypatch.setattr(MP, "adl_df_is_proxy", lambda df: False)
        with pytest.raises(AssertionError):
            _check_five_bucket_proxy()


# ══════════════════════════════════════════════════════════════════
# 7. forward test：ruleset_hash 分得出旗標；health None 可落地
# ══════════════════════════════════════════════════════════════════
class TestForwardTestLedger:
    def test_hash_changes_with_flag(self, monkeypatch):
        import shared.signal_thresholds as STH
        from src.compute.macro.macro_forward_test import compute_ruleset_hash
        h0 = compute_ruleset_hash()
        monkeypatch.setattr(STH, "BREADTH_PROXY_SCORING_ENABLED", True)
        assert compute_ruleset_hash() != h0

    def test_schema_bumped(self):
        from shared.macro_forward_test_schema import MACRO_FWD_TEST_SCHEMA_VERSION
        assert MACRO_FWD_TEST_SCHEMA_VERSION == 3

    def test_signal_row_with_unevaluated_health(self):
        from src.compute.macro.macro_forward_test import build_signal_row
        tl = _tl({"avg": 55.0, "is_proxy": True})
        row = build_signal_row(tl, date="2026-10-22", captured_at="2026-10-23T17:00:00+08:00",
                               twii_close=17000.0)
        assert row["health"] is None and row["icon"] == "⬜"
        assert row["regime_source"] == "unevaluated:breadth_unavailable"


# ══════════════════════════════════════════════════════════════════
# 8. 原始碼掃描：計分端讀旌旗必經 jingqi_for_scoring
# ══════════════════════════════════════════════════════════════════
#: 讀 `jingqi_info` 的檔案白名單（理由逐條寫）。不在名單內的 `src/compute/**`／`src/services/**`
#: 一旦讀 `jingqi_info[...]` 或 `jingqi_info.get(...)` ⇒ 紅燈，逼新增者先決定「計分還是顯示」。
_JINGQI_READ_WHITELIST = {
    "src/compute/macro/macro_helpers.py",   # calc_traffic_light 經 jingqi_for_scoring；五桶為顯示＋灰燈
    "src/services/jingqi_calc.py",          # producer（寫入端）
    "src/services/section_inputs.py",       # 原樣轉交 dict 給 calc_traffic_light（不自己計分）
    "src/services/reconcile_service.py",    # 健康分對帳（計分）—— 經 jingqi_for_scoring
}


def test_scoring_reads_go_through_jingqi_for_scoring():
    offenders = []
    for base in ("src/compute", "src/services"):
        for p in sorted((REPO / base).rglob("*.py")):
            rel = p.relative_to(REPO).as_posix()
            src = p.read_text(encoding="utf-8")
            if re.search(r"jingqi_info\s*(\[|\.get\()", src) and rel not in _JINGQI_READ_WHITELIST:
                offenders.append(rel)
    assert not offenders, f"新的 jingqi_info 讀取點未登記（計分須經 jingqi_for_scoring）：{offenders}"
    mh = (REPO / "src/compute/macro/macro_helpers.py").read_text(encoding="utf-8")
    assert "_jingqi_for_scoring(jingqi_info)" in mh
    rs = (REPO / "src/services/reconcile_service.py").read_text(encoding="utf-8")
    assert "if not jingqi_for_scoring(_jq_info):" in rs


def test_reconcile_health_inputs_drop_proxy():
    """健康分對帳（新 UI 憑什麼頁的對帳列）同樣是計分路徑：代理 ⇒ jq 缺值，⛔ 不退回 warroom。"""
    from src.services.reconcile_service import health_inputs
    s = {"jingqi_info": {"avg": 55.0, "is_proxy": True}, "warroom_summary": {"jingqi_avg": 55.0}}
    assert health_inputs(s)["jq"] is None
    assert health_inputs({"jingqi_info": {"avg": 55.0}})["jq"] == 55.0


# ══════════════════════════════════════════════════════════════════
# 10. 新 UI page_today：breadth 原因 ⇒ 出口不是「可重抓」；其他原因照舊
# ══════════════════════════════════════════════════════════════════
def _contract(source):
    return {"regime": "unknown", "light": "⬜", "source": source, "trend_regime": None,
            "health": None, "defense": False, "exposure_limit_pct": None,
            "traffic_light": None, "is_loaded": False}


def _verdict_tiles(regime):
    from shared.allocation_decision import build_allocation_decision
    from src.ui.views import page_today as P
    tiles = P.build_verdict_tiles(
        alloc=build_allocation_decision(regime), alloc_error="", danger=None, danger_error="",
        danger_requested=False, regime=regime, regime_error="")
    return P, {t.card.key: t.card for t in tiles}


class TestPageTodayBreadthExit:
    def test_breadth_exit_not_retry(self):
        from shared.regime_arbiter import SOURCE_UNEVALUATED_BREADTH
        P, cards = _verdict_tiles(_contract(SOURCE_UNEVALUATED_BREADTH))
        for key in ("verdict.exposure", "verdict.regime"):
            c = cards[key]
            assert c.state != P.UI_LIVE
            assert c.note.where is P.EXIT_WAIT_BREADTH_SOURCE, key
            assert c.note.where is not P.EXIT_RETRY_HERE, key
            assert "廣度" in c.note.why, (key, c.note.why)

    def test_status_bar_and_summary_retargeted(self):
        from shared.regime_arbiter import SOURCE_UNEVALUATED_BREADTH
        from src.ui.tabs.tab_today import build_status_bar_cards
        from src.ui.views import page_today as P
        reg = _contract(SOURCE_UNEVALUATED_BREADTH)
        bar = next(c for c in build_status_bar_cards(reg) if c.key == "statusbar.macro")
        out = P.contract_exit_retargeted(bar, reg)
        assert out.note.where is P.EXIT_WAIT_BREADTH_SOURCE
        assert out.note.why == P.BREADTH_UNEVALUATED_WHY
        # 不帶 regime（舊呼叫法）⇒ 與修前逐一相同
        assert P.contract_exit_retargeted(bar).note.where is P.EXIT_RETRY_HERE

    def test_non_breadth_unevaluated_still_retry(self):
        """SHOULD-A2：以**原因**分流 —— 非 breadth 的未評估照舊 `EXIT_RETRY_HERE`。"""
        from shared.regime_arbiter import SOURCE_UNLOADED
        P, cards = _verdict_tiles({**_contract(SOURCE_UNLOADED), "source": SOURCE_UNLOADED})
        for key in ("verdict.exposure", "verdict.regime"):
            assert cards[key].note.where is P.EXIT_RETRY_HERE, key


# ══════════════════════════════════════════════════════════════════
# 11. DH-TWII-MA200：<200 根 ⇒ ma200 None、status／confidence 不給假值
# ══════════════════════════════════════════════════════════════════
def _df_index(n):
    idx = pd.bdate_range(end=pd.Timestamp.now().normalize(), periods=n)
    close = pd.Series([15000.0 + i * 5 for i in range(n)], index=idx)
    return pd.DataFrame({"Close": close, "Volume": 1_000_000.0})


class TestMa200NotFabricated:
    def test_short_history_ma200_none(self):
        from src.services.market_strategy import get_market_assessment
        df = _df_index(150)
        r = get_market_assessment(df_index=df, foreign_net=1e9)
        assert r is not None
        assert r["ma200"] is None
        assert r["ma200"] != r["index_price"]      # ⛔ 不得是現價頂替
        assert r["status"] is None and r["confidence"] is None
        assert r["ma200_status"] and "200" in r["ma200_status"]

    def test_long_history_ma200_real(self):
        from src.services.market_strategy import get_market_assessment
        df = _df_index(260)
        r = get_market_assessment(df_index=df, foreign_net=1e9)
        assert r["ma200"] == pytest.approx(round(float(df["Close"].tail(200).mean()), 2))
        assert r["status"] in ("多頭", "盤整", "空頭") and r["ma200_status"] is None

    def test_market_score_none_ma200(self):
        from src.services.market_strategy import market_score
        r = market_score(17000.0, None, 1e9, 2000, 1000)
        assert r["status"] is None and r["confidence"] is None
        assert any("年線" in s and "未評估" in s for s in r["signals"])

    def test_source_guard_no_current_price_fallback(self):
        """突變守衛（原始碼）：恢復 `else current_price` 頂替年線 ⇒ 紅。"""
        src = (REPO / "src/services/market_strategy.py").read_text(encoding="utf-8")
        code = "\n".join(l for l in src.splitlines() if not l.lstrip().startswith("#"))
        assert not re.search(r"ma200\s*=.*else\s+current_price", code)

