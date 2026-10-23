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
        tl = _tl({"avg": 55.0, "is_proxy": False})
        assert tl["health"] == pytest.approx(
            round(55.0 * HEALTH_WEIGHT_JQ + 75.0 * HEALTH_WEIGHT_SCORE, 1))
        assert tl["health_unavailable_reason"] is None

    def test_missing_jingqi_not_renormalised(self):
        """I-2：旌旗整包缺席 ⇒ None，⛔ 不是只剩大盤分 75（舊歸一）、⛔ 不是 60（舊捏 50）。"""
        tl = _tl(None)
        assert tl["health"] is None

    def test_jingqi_and_score_absent_l2_keeps_unloaded_but_l3_unevaluated(self, _fresh_file):
        """旌旗整包缺席＋大盤分缺、`cl_data` 非空（只有非廣度來源）⇒ L2 照舊標 SOURCE_UNLOADED；
        L3 `get_macro_state` 依 DEC-075 D-1(a) 仍回未評估、⛔ 不退 `macro_state.json`。

        ⚠️ 2026-10-23 QA3 MUST-R1 更正（有意識的修改，⛔ 不是漏刪）：本支舊名
        `test_no_breadth_input_and_no_score_stays_unloaded`、舊 docstring 寫「F1（三源全空、連代理都沒有）」——
        **不實**：輸入 `cl_data={"x": 1}` 不是三源全空（真正的 F1 三源全空會讓 `calc_traffic_light` 直接回 None，
        不會產生 warroom）。本態實際是 ^TWII 全滅那一族（旌旗缺、大盤分缺、其他來源還在）。
        舊斷言（L2 原因＝UNLOADED）照留：L2 原因標記本批刻意不改（QA3 實測放寬 L2 會讓失敗態 golden 變紅）；
        新增 L3 斷言：這一態舊碼會退檔案規則引擎位階（＝DEC-075 不採用的 (b)），自 MUST-R1 起改為未評估。
        """
        from shared.regime_arbiter import SOURCE_UNEVALUATED_BREADTH, SOURCE_UNLOADED
        from src.compute.macro.macro_helpers import calc_traffic_light
        from src.compute.macro.warroom_summary import build_warroom_summary
        from src.services.macro_state_locker import get_macro_state
        tl = calc_traffic_light({}, None, {"x": 1}, None)
        assert tl["health"] is None
        assert tl["regime_source"] == SOURCE_UNLOADED
        st = get_macro_state(build_warroom_summary(tl, {}), state_file_path=_fresh_file)
        assert st["regime"] == "unknown" and st["is_loaded"] is False, st
        assert st["source"] == SOURCE_UNEVALUATED_BREADTH

    def test_proxy_with_score_missing_is_breadth(self):
        """QA1 MUST-1：代理廣度被擋下 ⇒ 一律標 breadth（不看大盤分在不在）。"""
        from shared.regime_arbiter import SOURCE_UNEVALUATED_BREADTH
        from src.compute.macro.macro_helpers import calc_traffic_light
        for mkt in ({}, {"regime": "bull"}):
            tl = calc_traffic_light(mkt, {"avg": 55.0, "is_proxy": True}, {"x": 1}, None)
            assert tl["health"] is None
            assert tl["regime_source"] == SOURCE_UNEVALUATED_BREADTH, mkt

    def test_absent_jingqi_copy_does_not_claim_proxy(self):
        """NIT-1：旌旗整包缺席（沒有代理值）時，文案不說「代理估算值不計分」。"""
        from shared.regime_arbiter import SOURCE_UNEVALUATED_BREADTH
        tl = _tl(None)
        assert tl["regime_source"] == SOURCE_UNEVALUATED_BREADTH
        assert "代理" not in tl["action"] and "廣度" in tl["action"]
        assert "代理" in _tl({"avg": 55.0, "is_proxy": True})["action"]

    def test_score_missing_real_jingqi_keeps_d3_renormalisation(self):
        """D-3（內部拍板）：大盤評分缺席而旌旗真值在 ⇒ 既有歸一不動（非受 breadth 影響）。"""
        from src.compute.macro.macro_helpers import calc_traffic_light
        tl = calc_traffic_light({"regime": "neutral"}, {"avg": 55.0, "is_proxy": False}, {"x": 1}, None)
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

    def test_other_reason_unevaluated_when_proxy_scoring_off(self, _fresh_file):
        """warroom 在、health 非有限、原因標 SOURCE_UNLOADED ⇒ 代理不計分（旗標 False）時也未評估、⛔ 不退檔。

        ⚠️ 2026-10-23 QA3 MUST-R1（DEC-075 D-1(a)，行為變更，有意識的修改，⛔ 不是漏刪）：本支舊名
        `test_other_reason_still_falls_back_to_file`，舊斷言「非 breadth 原因 ⇒ 照舊退檔案位階（C1 v19.182 其餘語意）」。
        舊理由在**旗標開（代理計分）**時仍成立 —— 改由下一支 `..._when_proxy_scoring_on` 守；
        旗標關時 repo 沒有任何真實廣度，health 非有限必然受缺廣度所限 ⇒ 退檔＝DEC-075 不採用的 (b)。
        """
        from shared.regime_arbiter import SOURCE_UNEVALUATED_BREADTH, SOURCE_UNLOADED
        from src.services.macro_state_locker import get_macro_state
        for health in (None, float("nan"), float("inf")):
            st = get_macro_state({"health_score": health, "regime_source": SOURCE_UNLOADED},
                                 state_file_path=_fresh_file)
            assert st["regime"] == "unknown" and st["is_loaded"] is False, (health, st)
            assert st["source"] == SOURCE_UNEVALUATED_BREADTH and st["health"] is None

    def test_other_reason_falls_back_to_file_when_proxy_scoring_on(self, _fresh_file, monkeypatch):
        """旗標 True（未來真的有可計分廣度）⇒ MUST-R1 新分支不觸發 ⇒ 非 breadth 原因照舊退檔案位階。

        防的是把未來「真實廣度到位、health None 屬其他來源故障」的情境一起鎖死成未評估。
        """
        import shared.signal_thresholds as STH
        from shared.regime_arbiter import SOURCE_FILE_RULE_ENGINE, SOURCE_UNEVALUATED_BREADTH, SOURCE_UNLOADED
        from src.services.macro_state_locker import get_macro_state
        monkeypatch.setattr(STH, "BREADTH_PROXY_SCORING_ENABLED", True)
        st = get_macro_state({"health_score": None, "regime_source": SOURCE_UNLOADED},
                             state_file_path=_fresh_file)
        assert st["source"] == SOURCE_FILE_RULE_ENGINE and st["is_loaded"] is True
        assert st["regime"] == "bull"
        # 既有 breadth 原因分支與旗標無關（照舊未評估）
        st2 = get_macro_state({"health_score": None, "regime_source": SOURCE_UNEVALUATED_BREADTH},
                              state_file_path=_fresh_file)
        assert st2["regime"] == "unknown" and st2["is_loaded"] is False

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
        """突變：移除原因判斷（常數對不上 ⇒ 守衛失效）⇒ 退回檔案位階 ⇒ 必紅。

        📌 2026-10-23 QA3 MUST-R1：L3 另加了「代理不計分 ⇒ health 非有限一律未評估」的分支（`_wr_no_real_breadth`），
        旗標關時它會把本突變也接住（縱深防禦）。為了只量「原因判斷」這一條守衛，本突變同時把旗標翻 True
        讓新分支不觸發；新分支自己的突變見 `TestMustR1TwiiDeadNoFileFallback`。
        """
        import shared.regime_arbiter as RA
        import shared.signal_thresholds as STH
        _orig = RA.SOURCE_UNEVALUATED_BREADTH
        monkeypatch.setattr(RA, "SOURCE_UNEVALUATED_BREADTH", "__mutant__")
        monkeypatch.setattr(STH, "BREADTH_PROXY_SCORING_ENABLED", True)
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
        _out, det, rd = _five({"avg": 35.0, "is_proxy": False}, pd.DataFrame({"ad_ratio": [35.0], "is_proxy": [False]}))
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
    assert "and not jingqi_for_scoring(_jq_info)" in rs


def test_reconcile_health_inputs_drop_proxy():
    """健康分對帳（新 UI 憑什麼頁的對帳列）同樣是計分路徑：代理 ⇒ jq 缺值，⛔ 不退回 warroom。"""
    from src.services.reconcile_service import health_inputs
    s = {"jingqi_info": {"avg": 55.0, "is_proxy": True}, "warroom_summary": {"jingqi_avg": 55.0}}
    assert health_inputs(s)["jq"] is None
    assert health_inputs({"jingqi_info": {"avg": 55.0, "is_proxy": False}})["jq"] == 55.0
    assert health_inputs({"jingqi_info": {"avg": 55.0}})["jq"] is None      # 缺旗標＝代理（S-6 fail-safe）


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
        """突變守衛（原始碼，AST）：`get_market_assessment` 內任何對 `ma200` 的賦值用到 `current_price` ⇒ 紅。

        回修 QA2 N-1：舊版正規式只擋 `ma200 = … else current_price`；`else:` 區塊內 `ma200 = current_price` 繞得過。
        """
        tree = ast.parse((REPO / "src/services/market_strategy.py").read_text(encoding="utf-8"))
        fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "get_market_assessment")
        bad = []
        for n in ast.walk(fn):
            if isinstance(n, (ast.Assign, ast.AnnAssign)):
                tgts = n.targets if isinstance(n, ast.Assign) else [n.target]
                if any(isinstance(t, ast.Name) and t.id == "ma200" for t in tgts) and n.value is not None:
                    if any(isinstance(x, ast.Name) and x.id == "current_price" for x in ast.walk(n.value)):
                        bad.append(n.lineno)
        assert not bad, f"ma200 又以現價頂替：行 {bad}"

    def test_ma200_window_with_nan_is_unevaluated(self):
        """QA2 N-2：≥200 根但視窗內含 NaN ⇒ ma200 None＋原因，status／confidence None。"""
        from src.services.market_strategy import get_market_assessment
        df = _df_index(260)
        df.iloc[-50, df.columns.get_loc("Close")] = float("nan")
        r = get_market_assessment(df_index=df, foreign_net=1e9)
        if r is None:   # MA120 閘也吃到 NaN ⇒ 整包 None（既有行為），⛔ 不得出現現價頂替的年線
            return
        assert r["ma200"] is None and r["ma200_status"] and "缺值" in r["ma200_status"]
        assert r["status"] is None and r["confidence"] is None

    def test_ma200_constant_lives_in_l0(self):
        """QA2 S-2：常數在 L0、值 200 未變。"""
        import shared.signal_thresholds as STH
        import src.services.market_strategy as MS
        assert STH.MA200_WINDOW_DAYS == 200 and MS.MA200_WINDOW_DAYS is STH.MA200_WINDOW_DAYS


# ══════════════════════════════════════════════════════════════════
# 批 1'（DEC-075）：DH-FOREIGN-FILL0／DH-EXPORT-LABEL／ISM 教學對映
# ══════════════════════════════════════════════════════════════════
class TestForeignFill0:
    def _inst(self, monkeypatch, rows):
        """跑真的 `fetch_macro_bundle`（TWSE inst 回空 ⇒ FinMind 補救段），離線 stub（同 lamp 測試的 runner）。"""
        from tests.test_lamp_foreign_net_wiring import _finmind_bundle
        return _finmind_bundle(monkeypatch, rows)["inst"]

    def test_foreign_missing_buy_is_none_not_minus_sell(self, monkeypatch):
        """外資 buy 缺值 ⇒ net 為 None（⛔ 不是 fillna(0) 推出的 −sell）＋未觀測旗標照舊。"""
        from shared.inst_net import is_net_observed
        inst = self._inst(monkeypatch, [
            {"date": "2026-10-22", "name": "Foreign_Investor", "buy": None, "sell": 30_000_000_000},
            {"date": "2026-10-22", "name": "Investment_Trust", "buy": 2_000_000_000, "sell": 1_000_000_000},
        ])
        assert inst["外資及陸資"]["net"] is None
        assert inst["外資及陸資"]["net"] != 0
        assert not is_net_observed(inst, "外資及陸資")
        assert inst["投信"]["net"] == 10.0               # 觀測值逐位不變

    def test_observed_values_unchanged(self, monkeypatch):
        inst = self._inst(monkeypatch, [
            {"date": "2026-10-22", "name": "Foreign_Investor", "buy": 50_000_000_000, "sell": 30_000_000_000},
        ])
        assert inst["外資及陸資"]["net"] == 200.0

    def test_source_guard_no_fillna0(self):
        """突變守衛（原始碼，AST）：`fetch_macro_bundle` 內任何 `.fillna(...)` 以 0 填值 ⇒ 紅。

        回修 QA2 N-1：舊版是正規式，`.fillna(value=0)` 繞得過；改 AST，位置參數與 `value=` 都看。
        """
        tree = ast.parse((REPO / "src/services/macro_fetch_orchestrator.py").read_text(encoding="utf-8"))
        fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "fetch_macro_bundle")
        bad = []
        for n in ast.walk(fn):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "fillna":
                vals = list(n.args) + [k.value for k in n.keywords if k.arg in (None, "value")]
                if any(isinstance(v, ast.Constant) and v.value == 0 for v in vals):
                    bad.append(n.lineno)
        assert not bad, f"fetch_macro_bundle 又出現以 0 填值的 fillna：行 {bad}"


class TestExportLabel:
    def test_label_is_customs_export_value(self):
        from shared.macro_buckets import SPECS_BY_KEY
        lbl = SPECS_BY_KEY["tw_export"].label
        assert "出口金額" in lbl and "海關" in lbl
        assert "訂單" not in lbl

    def test_thresholds_unchanged(self):
        """只改名稱：門檻／方向一字未動（⛔ 不改計算）。"""
        from shared.macro_buckets import SPECS_BY_KEY
        s = SPECS_BY_KEY["tw_export"]
        assert (s.direction, s.yellow, s.red) == ("low_bad", 0.0, -5.0)


class TestIsmEduMapping:
    def test_tw_pmi_lamp_gets_tw_pmi_edu(self):
        from src.services.macro_v2_service import _EDU_KEY, get_edu
        assert _EDU_KEY["ism_pmi"] != "NAPM"
        e = get_edu("ism_pmi")
        assert "台灣" in e["meaning"] and "CIER" in e["meaning"]
        assert "33.1" not in e["historical_anchor"]          # 美國 ISM 2008 低點不得再出現
        # how_to_read 一行未動（⛔ 不改門檻）：仍是同一組 PMI token
        from src.data.core.data_registry import EDU_GUIDE
        assert [c for c, _ in EDU_GUIDE["TW_PMI"]["how_to_read"]] == [
            "> §§PMI_YELLOW§§", "= §§PMI_YELLOW§§", "< §§PMI_YELLOW§§",
            "≤ §§PMI_RED§§", "≤ §§PMI_RED§§ 持續 3 月"]
        assert "NAPM" not in EDU_GUIDE      # 美國 ISM 那一篇已無讀者，不留第二份


# ══════════════════════════════════════════════════════════════════
# 回修（QA1／QA2，2026-10-23）
# ══════════════════════════════════════════════════════════════════
def _wr_from(mkt, jq, cl=None):
    """真的 L2 → warroom（同 `warroom_apply` 的組法），給 get_macro_state 用。"""
    from src.compute.macro.macro_helpers import calc_traffic_light
    from src.compute.macro.warroom_summary import build_warroom_summary
    tl = calc_traffic_light(mkt, jq, cl if cl is not None else {"x": 1}, None)
    return build_warroom_summary(tl, mkt)


class TestMust1ProxyAndScoreMissingNoFileFallback:
    """QA1 MUST-1：代理旌旗＋大盤分缺（^TWII 掛）⇒ 位階仍未評估、⛔ 不退 macro_state.json。"""

    @pytest.mark.parametrize("mkt", [{}, {"regime": "bull"}])
    @pytest.mark.parametrize("kw", [{}, {"strict": True}, {"require_valid_risk_cap": True},
                                    {"strict": True, "require_valid_risk_cap": True}])
    def test_no_file_fallback(self, _fresh_file, mkt, kw):
        from shared.regime_arbiter import SOURCE_UNEVALUATED_BREADTH
        from src.services.macro_state_locker import get_macro_state
        wr = _wr_from(mkt, {"avg": 55.0, "is_proxy": True})
        st = get_macro_state(wr, state_file_path=_fresh_file, **kw)
        assert st["regime"] == "unknown" and st["is_loaded"] is False, st
        assert st["source"] == SOURCE_UNEVALUATED_BREADTH

    def test_card3_not_degraded(self, _fresh_file):
        from src.services.macro_state_locker import get_macro_state
        wr = _wr_from({"regime": "bull"}, {"avg": 55.0, "is_proxy": True})
        reg = get_macro_state(wr, state_file_path=_fresh_file)
        P, cards = _verdict_tiles(reg)
        assert cards["verdict.regime"].state not in (P.UI_LIVE, P.UI_DEGRADED)
        assert cards["verdict.regime"].note.where is P.EXIT_WAIT_BREADTH_SOURCE

    def test_mutant_old_score_condition_turns_red(self, _fresh_file, monkeypatch):
        """突變：把原因判定改回「只在大盤分在時才標 breadth」⇒ 退檔 ⇒ 必紅。"""
        import src.compute.macro.macro_helpers as MH
        from src.services.macro_state_locker import get_macro_state
        src = (REPO / "src/compute/macro/macro_helpers.py").read_text(encoding="utf-8")
        anchor = "and (_jq_proxy_dropped or _score_pct is not None)) else None)"
        assert src.count(anchor) == 1
        mut = src.replace(anchor, "and (_score_pct is not None)) else None)")
        import types
        m = types.ModuleType("_mh_mut")
        m.__file__ = MH.__file__
        exec(compile(mut, MH.__file__, "exec"), m.__dict__)
        from src.compute.macro.warroom_summary import build_warroom_summary
        tl = m.calc_traffic_light({"regime": "bull"}, {"avg": 55.0, "is_proxy": True}, {"x": 1}, None)
        # 📌 2026-10-23 QA3 MUST-R1（有意識的修改，⛔ 不是漏刪）：舊斷言「突變下 get_macro_state 退檔（bull）」
        #   已不成立 —— L3 新增「代理不計分 ⇒ health 非有限一律未評估」分支，旗標關時把本突變也接住（縱深防禦）。
        #   改量兩件事：(1) L2 原因確實被突變打回 UNLOADED（L2 守衛有效；`test_proxy_with_score_missing_is_breadth` 會紅）；
        #   (2) L3 仍未評估；只有旗標 True（新分支不觸發）時才退檔 ⇒ L2 守衛在旗標開時仍是唯一防線。
        from shared.regime_arbiter import SOURCE_UNLOADED
        import shared.signal_thresholds as STH
        assert tl["regime_source"] == SOURCE_UNLOADED
        wr = build_warroom_summary(tl, {"regime": "bull"})
        st = get_macro_state(wr, state_file_path=_fresh_file)
        assert st["regime"] == "unknown" and st["is_loaded"] is False
        monkeypatch.setattr(STH, "BREADTH_PROXY_SCORING_ENABLED", True)
        st_on = get_macro_state(wr, state_file_path=_fresh_file)
        assert st_on["regime"] == "bull" and st_on["is_loaded"] is True   # 新分支不在時確實退檔


def _no_retry(txt):
    return not any(p in txt for p in _RETRY_PHRASES)


class TestMust2DownstreamCopy:
    """QA1 MUST-2：持股頁④⑤、AI 問答、姿態帶 drivers 在 breadth 原因時不得叫人重抓、不得說檔案無快照。"""

    def test_allocation_driver_and_headline(self):
        from shared.allocation_decision import build_allocation_decision
        from shared.regime_arbiter import SOURCE_UNEVALUATED_BREADTH
        d = build_allocation_decision(_contract(SOURCE_UNEVALUATED_BREADTH))
        assert d.unevaluated_reason == "breadth"
        assert "皆無有效值" not in "".join(d.drivers) and "廣度" in "".join(d.drivers)
        assert _no_retry(d.headline()) and _no_retry("".join(d.drivers))
        d2 = build_allocation_decision(_contract("unloaded"))
        assert d2.unevaluated_reason == "" and "一鍵更新" in d2.headline()      # 其餘原因照舊

    def test_page_hold_cards(self):
        from src.ui.views import page_hold as PH
        mac = PH.build_macro_stage_card(PH.MacroReadout(requested=True, loaded=False, breadth_unevaluated=True))[0]
        cap = PH.build_position_cap_card(PH.AllocationReadout(requested=True, is_loaded=False,
                                                              breadth_unevaluated=True))[0]
        for c in (mac, cap):
            assert _no_retry(c.note.why + c.note.where) and "更新總經" not in c.note.where
            assert "廣度" in c.note.why
        mac0 = PH.build_macro_stage_card(PH.MacroReadout(requested=True, loaded=False))[0]
        assert "更新總經" in mac0.note.where                                    # 其餘原因照舊

    def test_page_hold_loaders_carry_flag(self, monkeypatch):
        from shared.regime_arbiter import SOURCE_UNEVALUATED_BREADTH
        import src.services.allocation_service as AS
        import src.services.dividend_station_service as DS
        from src.ui.views import page_hold as PH
        monkeypatch.setattr(AS, "get_macro_regime", lambda **k: _contract(SOURCE_UNEVALUATED_BREADTH))
        assert DS.get_station_macro(strict=True)["breadth_unevaluated"] is True
        assert PH.load_macro(PH.HoldRequest(submitted=True)).breadth_unevaluated is True

    def test_ai_qa_market_state_and_score(self, monkeypatch):
        from shared.regime_arbiter import SOURCE_UNEVALUATED_BREADTH
        from shared.scoring_regime_gate import resolve_scoring_regime
        import src.services.ai_qa_service as Q
        monkeypatch.setattr(Q, "_macro_state", lambda **k: _contract(SOURCE_UNEVALUATED_BREADTH))
        r = Q._tool_get_market_state(require_valid_risk_cap=True)
        assert r["ok"] is False and _no_retry(r["error"]) and "macro_state.json 無" not in r["error"]
        dec = resolve_scoring_regime(_contract(SOURCE_UNEVALUATED_BREADTH))
        assert dec.breadth_unevaluated and _no_retry(Q._regime_blocked_error(dec)) and _no_retry(dec.notice())
        dec0 = resolve_scoring_regime(_contract("unloaded"))
        assert "一鍵更新" in Q._regime_blocked_error(dec0)                     # 其餘原因照舊

    def test_old_ui_handler_breadth_only_no_retry(self):
        """QA2 S-4：舊 UI 燈號卡在「只缺廣度」時不再前句叫人更新、後句說更新沒用。"""
        from tests.test_batch_z35 import _render_gate
        li = pd.DataFrame({"外資大小": [1.0], "韭菜指數": [1.0]})
        from src.compute.macro.macro_helpers import calc_traffic_light
        tl = calc_traffic_light({"score": 3, "max_score": 4, "regime": "bull"},
                                {"avg": 55.0, "is_proxy": True},
                                {"inst": {"外資": {"net": 1.0}},
                                 "adl": pd.DataFrame({"ad_ratio": [55.0], "is_proxy": [True]})}, li)
        txt = _render_gate(tl)
        assert "更新資料不會改變" in txt and "一鍵更新" not in txt and "權重已重新歸一化" not in txt
        assert "兩條腿" not in txt and "取得失敗" not in txt


class TestM1TodayTileProxyGray:
    """QA2 M-1：新 UI 今天頁燈卡（`build_indicator_tile`）代理廣度 ⇒ 灰＋註記；真值照舊判燈。"""

    @staticmethod
    def _tile(key, rec):
        from src.ui.views import page_today as P
        bands = {"green": ("綠", "#0"), "yellow": ("黃", "#1"), "red": ("紅", "#2"), "gray": ("無資料", "#3")}
        return P.build_indicator_tile(key, rec, requested=True, error="",
                                      band_label=lambda b, _s: bands[b], thr_text=None)

    def _check(self):
        from shared.macro_provenance import BREADTH_PROXY_VALUE_NOTE
        for key in ("jingqi", "adl"):
            t = self._tile(key, {"state": "ok", "value": 30.0, "is_proxy": True})
            assert t.signal_text == "無資料", (key, t.signal_text)
            assert t.card.value.endswith(BREADTH_PROXY_VALUE_NOTE)
            r = self._tile(key, {"state": "ok", "value": 30.0})
            assert r.signal_text == "紅" and BREADTH_PROXY_VALUE_NOTE not in r.card.value

    def test_proxy_gray_with_note(self):
        self._check()

    def test_mutant_remove_branch_turns_red(self, monkeypatch):
        from src.ui.views import page_today as P
        monkeypatch.setattr(P, "BREADTH_LAMP_KEYS", frozenset())
        with pytest.raises(AssertionError):
            self._check()


class TestS1RefreshStepDetail:
    """QA2 S-1：更新報告 STEP_WARROOM 的說明在 breadth 原因時據實。"""

    def _check(self):
        from shared.regime_arbiter import SOURCE_UNEVALUATED_BREADTH
        from src.services.macro_refresh_service import warroom_written_detail
        d = warroom_written_detail(True, SOURCE_UNEVALUATED_BREADTH)
        assert "兩條腿都缺" not in d and "會改讀它" not in d and "廣度" in d and _no_retry(d)

    def test_breadth_detail(self, monkeypatch):
        self._check()
        from src.services.macro_refresh_service import warroom_written_detail
        # 📌 QA-4 S-1 連帶（2026-10-23，有意識的修改，⛔ 不是漏刪）：~~`"unloaded"` ⇒ 舊句逐字照舊（無條件）~~ ——
        #   DEC-075 D-1(a) 回修（QA3 MUST-R1）起，旗標關時 warroom 在而健康分缺 ⇒ 位階一律未評估、不改讀檔，
        #   舊句「會改讀它」在旗標關時不屬實。舊句只在代理計分開啟時仍成立 ⇒ 該斷言改在旗標開時做；旗標關另斷言據實句。
        import shared.signal_thresholds as STH
        _d_off = warroom_written_detail(True, "unloaded")
        assert "兩條腿都缺" not in _d_off and "會改讀它" not in _d_off and "廣度" in _d_off and _no_retry(_d_off)
        monkeypatch.setattr(STH, "BREADTH_PROXY_SCORING_ENABLED", True)
        assert "兩條腿都缺" in warroom_written_detail(True, "unloaded")   # 旗標開：其餘原因逐字照舊
        assert warroom_written_detail(False, None) == "寫入 warroom_summary"

    def test_mutant_turns_red(self, monkeypatch):
        import shared.regime_arbiter as RA
        import shared.signal_thresholds as STH
        _orig = RA.SOURCE_UNEVALUATED_BREADTH
        monkeypatch.setattr(RA, "SOURCE_UNEVALUATED_BREADTH", "__mutant__")
        # QA-4 S-1 連帶：旗標關時本函式另以旗標判 breadth ⇒ 本突變要在旗標開時才看得出差別。
        monkeypatch.setattr(STH, "BREADTH_PROXY_SCORING_ENABLED", True)
        from src.services.macro_refresh_service import warroom_written_detail
        assert "兩條腿都缺" in warroom_written_detail(True, _orig)


class TestShouldFixes:
    def test_s1_reconcile_panel_drops_proxy(self, monkeypatch):
        import src.ui.pages.reconcile_panel as RP
        sess = {"warroom_summary": {"jingqi_avg": None}, "mkt_info": {"score": 3, "max_score": 4},
                "jingqi_info": {"avg": 55.0, "is_proxy": True}, "cl_data": {}}
        monkeypatch.setattr(RP, "_ss", lambda k, d=None: sess.get(k, d))
        assert RP._get_health_params()[0] is None
        sess["jingqi_info"] = {"avg": 55.0, "is_proxy": False}
        assert RP._get_health_params()[0] == 55.0

    def test_s2_coverage_does_not_count_proxy(self):
        from src.ui.tabs.tab_macro_v2 import bucket_summary, build_rows, summary_coverage
        _o, _d, rd = _five({"avg": 35.0, "is_proxy": True},
                           pd.DataFrame({"ad_ratio": [35.0], "is_proxy": [True]}))
        n_proxy, m = summary_coverage(bucket_summary(build_rows(rd)))
        _o, _d, rd2 = _five({"avg": 35.0, "is_proxy": False},
                            pd.DataFrame({"ad_ratio": [35.0], "is_proxy": [False]}))
        n_real, m2 = summary_coverage(bucket_summary(build_rows(rd2)))
        assert m == m2 and n_real - n_proxy == 2

    def test_s5_conf_adl_proxy_same_as_jingqi(self):
        from src.compute.macro.macro_helpers import calc_traffic_light
        li = pd.DataFrame({"外資大小": [1.0], "韭菜指數": [1.0]})
        base = ({"score": 3, "max_score": 4, "regime": "bull"}, {"avg": 55.0, "is_proxy": False})
        real = calc_traffic_light(*base, {"inst": {"外資": {"net": 1.0}},
                                         "adl": pd.DataFrame({"ad_ratio": [55.0], "is_proxy": [False]})}, li)
        prox = calc_traffic_light(*base, {"inst": {"外資": {"net": 1.0}},
                                         "adl": pd.DataFrame({"ad_ratio": [55.0], "is_proxy": [True]})}, li)
        assert real["conf"] == 100 and prox["conf"] == 80
        assert any("ADL" in m and "代理" in m for m in prox["missing_sources"])

    @pytest.mark.parametrize("flag, proxy", [
        (False, False), (True, True), ("False", True), (0, True), (None, True), ("<missing>", True)])
    def test_s6_is_breadth_proxy_fail_safe(self, flag, proxy):
        from shared.macro_provenance import is_breadth_proxy
        info = {"avg": 55.0} if flag == "<missing>" else {"avg": 55.0, "is_proxy": flag}
        assert is_breadth_proxy(info) is proxy

    def test_s6_numpy_bools(self):
        import numpy as np
        from shared.macro_provenance import is_breadth_proxy
        assert is_breadth_proxy({"is_proxy": np.bool_(False)}) is False
        assert is_breadth_proxy({"is_proxy": np.bool_(True)}) is True
        tl = _tl({"avg": 55.0, "is_proxy": np.bool_(True)})
        assert tl["health"] is None


# ══════════════════════════════════════════════════════════════════
# 回修（QA3 MUST-R1，2026-10-23）：^TWII 全滅 ⇒ 位階仍未評估、⛔ 不退 macro_state.json
# ══════════════════════════════════════════════════════════════════
#: ^TWII 全滅（`F3_twii_dead_others_alive` 那一族）：ADL 與旌旗備援兩個代理廣度都源自 ^TWII ⇒ 旌旗整包缺、
#: 大盤分缺；法人與期貨還在。L2 沒有「被擋下的代理值」⇒ 原因標 SOURCE_UNLOADED（L2 本批刻意不改）。
_TWII_DEAD_CL = {"inst": {"外資及陸資": {"net": 50.0}}}


def _wr_twii_dead(mkt):
    from src.compute.macro.macro_helpers import calc_traffic_light
    from src.compute.macro.warroom_summary import build_warroom_summary
    li = pd.DataFrame({"外資期貨淨額": [5000.0, 6000.0, 7000.0, 8000.0]})
    tl = calc_traffic_light(dict(mkt), None, dict(_TWII_DEAD_CL), li)
    assert tl is not None and tl["health"] is None
    return tl, build_warroom_summary(tl, dict(mkt))


def _check_twii_dead_unevaluated(path: str, get_macro_state=None, **kw) -> None:
    from shared.regime_arbiter import SOURCE_FILE_RULE_ENGINE, SOURCE_UNEVALUATED_BREADTH
    if get_macro_state is None:
        from src.services.macro_state_locker import get_macro_state
    for mkt in ({}, {"regime": "bull"}):
        _tl0, wr = _wr_twii_dead(mkt)
        st = get_macro_state(wr, state_file_path=path, **kw)
        assert st["source"] != SOURCE_FILE_RULE_ENGINE, (mkt, st)
        assert st["regime"] == "unknown" and st["is_loaded"] is False, (mkt, st)
        assert st["source"] == SOURCE_UNEVALUATED_BREADTH and st["health"] is None, (mkt, st)


class TestMustR1TwiiDeadNoFileFallback:
    """QA3 MUST-R1：^TWII 全滅 ⇒ `get_macro_state` 回 unknown、`is_loaded=False`、非 rule_engine（DEC-075 D-1(a)）。"""

    def test_premise_l2_reason_is_unloaded(self):
        """前提自證：此態 L2 原因確實是 UNLOADED（不是 breadth）—— 正是舊碼退檔的入口。"""
        from shared.regime_arbiter import SOURCE_UNLOADED
        for mkt in ({}, {"regime": "bull"}):
            tl, _wr = _wr_twii_dead(mkt)
            assert tl["regime_source"] == SOURCE_UNLOADED
            assert tl["health_unavailable_reason"] is None

    @pytest.mark.parametrize("kw", [{}, {"strict": True}, {"require_valid_risk_cap": True},
                                    {"strict": True, "require_valid_risk_cap": True}])
    def test_no_file_fallback(self, _fresh_file, kw):
        _check_twii_dead_unevaluated(_fresh_file, **kw)

    def test_downstream_scoring_and_find_filter_not_bear(self, tmp_path, monkeypatch):
        """下游：AI 多因子評分不拿到可用位階（不走空頭權重）；🎯 找標的頁不套空頭濾網。

        真實鏈：session `warroom_summary` ＋ cwd 下有效的 `macro_state.json`（寫空頭）→
        `allocation_service.get_macro_regime` → `ai_qa_service._scoring_regime` ／ `page_find._load_regime`。
        """
        import streamlit as st
        from src.services.macro_state_locker import _now_str
        (tmp_path / "macro_state.json").write_text(json.dumps(
            {"market_regime": "空頭", "exposure_limit_pct": 30, "timestamp": _now_str()},
            ensure_ascii=False), encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        _tl0, wr = _wr_twii_dead({})
        _had = "warroom_summary" in st.session_state
        _old = st.session_state.get("warroom_summary")
        st.session_state["warroom_summary"] = wr
        try:
            import src.services.ai_qa_service as Q
            from src.ui.views import page_find as F
            dec = Q._scoring_regime()
            assert dec.usable is False and dec.regime != "bear", dec
            assert Q._tool_get_market_state(require_valid_risk_cap=True).get("ok") is False
            assert F._load_regime() == (None, "")
            # ⚠️ 刻意**不**對「warroom 不存在」路徑下斷言：該路徑仍退 `macro_state.json`（本批不動），
            #   是否落入 D-1(a) 禁區待總管裁定 —— 不在這裡把現況鎖成合規。
        finally:
            if _had:
                st.session_state["warroom_summary"] = _old
            else:
                st.session_state.pop("warroom_summary", None)

    def test_mutant_remove_l3_branch_turns_red(self, _fresh_file):
        """突變：把 L3 新分支（`or _wr_no_real_breadth`）拔掉 ⇒ 退回檔案位階 ⇒ 檢查必紅。"""
        import types
        import src.services.macro_state_locker as MSL
        src = (REPO / "src/services/macro_state_locker.py").read_text(encoding="utf-8")
        anchor = "\n                        or _wr_no_real_breadth))"
        assert src.count(anchor) == 1
        m = types.ModuleType("_msl_mut")
        m.__file__ = MSL.__file__
        exec(compile(src.replace(anchor, "))"), MSL.__file__, "exec"), m.__dict__)
        _check_twii_dead_unevaluated(_fresh_file)                       # 原碼：綠
        _tl0, wr = _wr_twii_dead({})
        assert m.get_macro_state(wr, state_file_path=_fresh_file)["regime"] == "bull"   # 突變下確實退檔
        with pytest.raises(AssertionError):
            _check_twii_dead_unevaluated(_fresh_file, get_macro_state=m.get_macro_state)

    def test_flag_on_does_not_trigger_new_branch(self, _fresh_file, monkeypatch):
        """旗標 True ⇒ 新分支不觸發（同一份 ^TWII 全滅 warroom 照舊退檔），不把未來真實廣度情境鎖死。"""
        import shared.signal_thresholds as STH
        from shared.regime_arbiter import SOURCE_FILE_RULE_ENGINE
        from src.services.macro_state_locker import get_macro_state
        _tl0, wr = _wr_twii_dead({"regime": "bull"})        # 旗標 False 下組出的 warroom（只量 L3）
        monkeypatch.setattr(STH, "BREADTH_PROXY_SCORING_ENABLED", True)
        st = get_macro_state(wr, state_file_path=_fresh_file)
        assert st["source"] == SOURCE_FILE_RULE_ENGINE and st["is_loaded"] is True
        with pytest.raises(AssertionError):
            _check_twii_dead_unevaluated(_fresh_file)

    def test_flag_read_from_l0_not_hardcoded(self):
        """旗標從 `shared.signal_thresholds` 讀，不寫死。"""
        src = (REPO / "src/services/macro_state_locker.py").read_text(encoding="utf-8")
        assert "_ST.BREADTH_PROXY_SCORING_ENABLED" in src
