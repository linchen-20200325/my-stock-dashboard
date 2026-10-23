"""DH-REGIME-NOWARROOM（2026-10-23，PR #910）—— warroom **不存在**時位階不得退 `macro_state.json` 規則引擎位階。

客戶 DEC-075 D-1(a) 原文：「不允許在使用者無法清楚辨識的情況下，靜默 fallback 到另一套規則引擎產生位階結論」。
總管依兩組獨立調查裁定冷啟動（session 尚未載入）與 warroom 被 pop（`calc_traffic_light` 三源全空）兩條路徑屬該射程。

本檔守四件事：
  1. 契約：`get_macro_state` 在 warroom 不可用 ＋ 檔案有效 ＋ 代理廣度不計分（`BREADTH_PROXY_SCORING_ENABLED` False）時回
     `UNLOADED_VERDICT`（unknown／⬜／`SOURCE_UNLOADED`）、`is_loaded=False`；strict 不拋（有效檔不是「讀壞了」）；
     旗標 True ⇒ 舊語意（`SOURCE_FILE_RULE_ENGINE`、`is_loaded=True`）逐鍵不變；Risk Cap `exposure_limit_pct` 兩態相同。
  2. 下游：AI 評分閘拒評、`_tool_get_market_state` ok=False、找標的頁不套濾網、持股頁卡④ 非 live 且不印 bull／bear、
     換股 stance 非 aggressive／defensive、今天頁卡①③ 與狀態列為灰（idle）。
  3. 文案：上列讀點出現新句、不出現舊的不實句（「macro_state.json 無可用的鎖定快照」「四條來源本輪皆無值」「再重跑一次」）。
  4. 突變：把新條件拔掉 ⇒ 行為測試轉紅。
"""
from __future__ import annotations

import copy
import json
import types
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
_MSL_REL = "src/services/macro_state_locker.py"

_OLD_QA_ERR = "macro_state.json 無可用的鎖定快照"
_OLD_DRIVER = "總經尚未評估（warroom_summary / macro_state.json 皆無有效值）"
_OLD_FOUR_SOURCES = "四條來源本輪皆無值"
_OLD_GATE_RETRY = "再重跑一次批次分析"


# ══════════════════════════════════════════════════════════════════
# 共用
# ══════════════════════════════════════════════════════════════════
def _write_files(d: Path, regime_zh: str = "多頭", cap: int = 60) -> None:
    """有效的 `macro_state.json`（規則引擎多空）＋有效的 `risk_cap_state.json`（新 UI 上限快照）。"""
    from shared import risk_cap_policy as RP
    from src.services.macro_state_locker import _now_str
    base = {"market_regime": regime_zh, "systemic_risk_level": "安全", "exposure_limit_pct": cap,
            "Macro_Phase": "環境正常", "timestamp": _now_str()}
    (d / "macro_state.json").write_text(json.dumps(base, ensure_ascii=False), encoding="utf-8")
    snap = dict(base, **{"not_evaluated": [], "disabled_inputs": ["M1B_YoY_pct", "M2_YoY_pct"],
                         "input_detail": {}, "red_lines": {"sahm": {"status": "no_source"}},
                         RP.REQUIRED_CORE_OK_KEY: True,
                         RP.RISK_CAP_RULESET_VERSION_KEY: RP.RISK_CAP_RULESET_VERSION})
    (d / RP.RISK_CAP_STATE_FILE).write_text(json.dumps(snap, ensure_ascii=False), encoding="utf-8")


@pytest.fixture(params=[("多頭", "bull"), ("空頭", "bear")], ids=["bull_file", "bear_file"])
def files(request, tmp_path, monkeypatch):
    zh, en = request.param
    _write_files(tmp_path, zh)
    monkeypatch.chdir(tmp_path)
    return tmp_path, en


def _flag(monkeypatch, value: bool) -> None:
    import shared.signal_thresholds as STH
    monkeypatch.setattr(STH, "BREADTH_PROXY_SCORING_ENABLED", value)


def _fake_session(monkeypatch, session: dict | None = None):
    """allocation_service（全站 regime 橋樑）改讀一份假 session；回傳該假 st（共用給 warroom_apply）。"""
    from src.services import allocation_service as AS
    from tests.test_m2n2_no_zero_fill import _FakeST
    fake = _FakeST(copy.deepcopy(session or {}))
    monkeypatch.setattr(AS, "st", fake)
    return fake


_KW = [{}, {"strict": True}, {"require_valid_risk_cap": True},
       {"strict": True, "require_valid_risk_cap": True}]
_KW_IDS = ["default", "strict", "rvrc", "strict_rvrc"]


def _assert_unloaded(st: dict) -> None:
    from shared.regime_arbiter import SOURCE_FILE_RULE_ENGINE, SOURCE_UNLOADED
    assert st["regime"] == "unknown" and st["light"] == "⬜", st
    assert st["source"] == SOURCE_UNLOADED and st["source"] != SOURCE_FILE_RULE_ENGINE, st
    assert st["is_loaded"] is False, st
    assert st["defense"] is False and st["health"] is None, st
    assert "file_error" not in st, st


# ══════════════════════════════════════════════════════════════════
# 1. 契約
# ══════════════════════════════════════════════════════════════════
class TestContract:

    @pytest.mark.parametrize("kw", _KW, ids=_KW_IDS)
    @pytest.mark.parametrize("wr", [None, {}], ids=["cold_none", "cold_empty"])
    def test_cold_start_valid_file_is_unloaded(self, files, kw, wr):
        from src.services.macro_state_locker import get_macro_state
        d, _en = files
        _assert_unloaded(get_macro_state(wr, state_file_path=str(d / "macro_state.json"), **kw))

    @pytest.mark.parametrize("kw", _KW, ids=_KW_IDS)
    def test_flag_on_old_semantics_unchanged(self, files, kw, monkeypatch):
        """旗標 True（代理計分）⇒ 舊語意：退檔案規則引擎位階、`is_loaded=True`。"""
        from shared.regime_arbiter import SOURCE_FILE_RULE_ENGINE
        from src.services.macro_state_locker import get_macro_state
        d, en = files
        _flag(monkeypatch, True)
        st = get_macro_state(None, state_file_path=str(d / "macro_state.json"), **kw)
        assert st["source"] == SOURCE_FILE_RULE_ENGINE and st["is_loaded"] is True
        assert st["regime"] == en

    @pytest.mark.parametrize("kw", _KW, ids=_KW_IDS)
    def test_risk_cap_identical_between_flag_states(self, files, kw, monkeypatch):
        """Risk Cap（DEC-044／048）不受本修法影響：`exposure_limit_pct`（與揭露）兩態相同、且有值。"""
        from src.services.macro_state_locker import get_macro_state
        d, _en = files
        p = str(d / "macro_state.json")
        off = get_macro_state(None, state_file_path=p, **kw)
        _flag(monkeypatch, True)
        on = get_macro_state(None, state_file_path=p, **kw)
        assert off["exposure_limit_pct"] == on["exposure_limit_pct"] == 60
        assert off.get("risk_cap_disclosure") == on.get("risk_cap_disclosure")

    def test_only_regime_keys_change_vs_flag_on(self, files, monkeypatch):
        """兩態只差位階那幾個鍵（regime／light／source／is_loaded／defense），其餘逐鍵相同。"""
        from src.services.macro_state_locker import get_macro_state
        d, _en = files
        p = str(d / "macro_state.json")
        off = get_macro_state(None, state_file_path=p, require_valid_risk_cap=True)
        _flag(monkeypatch, True)
        on = get_macro_state(None, state_file_path=p, require_valid_risk_cap=True)
        assert off.keys() == on.keys()
        diff = {k for k in off if off[k] != on[k]}
        assert diff <= {"regime", "light", "source", "is_loaded", "defense"}, diff
        assert {"regime", "source", "is_loaded"} <= diff

    @pytest.mark.parametrize("content", ["{not json", json.dumps({"market_regime": "系統異常"})],
                             ids=["corrupt", "ai_failsafe"])
    def test_invalid_file_strict_still_raises(self, tmp_path, content):
        """檔案無效／損毀 ⇒ 既有 strict 拋錯不變（新條件只在檔案有效時成立）。"""
        from src.services.macro_state_locker import get_macro_state
        p = tmp_path / "macro_state.json"
        p.write_text(content, encoding="utf-8")
        with pytest.raises(RuntimeError):
            get_macro_state(None, state_file_path=str(p), strict=True)
        st = get_macro_state(None, state_file_path=str(p))
        assert st["is_loaded"] is False and st["regime"] == "unknown"

    def test_no_file_unchanged(self, tmp_path):
        from src.services.macro_state_locker import get_macro_state
        _assert_unloaded(get_macro_state(None, state_file_path=str(tmp_path / "macro_state.json"),
                                         strict=True))

    def test_warroom_live_unaffected(self, files):
        """warroom 可用（健康分有限）⇒ 照舊走 warroom（本修法不碰）。"""
        from src.services.macro_state_locker import get_macro_state
        d, _en = files
        wr = {"traffic_light": "🟡 震盪整理", "health_score": 55.0, "regime": "neutral",
              "effective_regime": "neutral", "light": "🟡", "regime_source": "test"}
        st = get_macro_state(wr, state_file_path=str(d / "macro_state.json"))
        assert st["is_loaded"] is True and st["regime"] == "neutral" and st["source"] == "test"

    def test_flag_read_at_call_time_from_l0(self):
        src = (REPO / _MSL_REL).read_text(encoding="utf-8")
        assert "_nowr_no_real_breadth = (not _wr_ok and not _wr_breadth and _file_ok" in src
        assert "and not _ST.BREADTH_PROXY_SCORING_ENABLED)" in src


class TestWarroomPopped:
    """`calc_traffic_light` 三源全空 ⇒ `warroom_apply` pop 掉 warroom ＋ 有效檔 ⇒ 同冷啟動結果（真實鏈）。"""

    def test_popped_then_contract_unloaded(self, files, monkeypatch):
        from src.services import allocation_service as AS
        from src.services import warroom_apply as WA
        stale = {"traffic_light": "上一輪", "health_score": 99.0, "regime": "bull",
                 "effective_regime": "bull", "light": "🟢", "regime_source": "上一輪"}
        fake = _fake_session(monkeypatch, {"cl_ts": "2026-10-23 09:00", "_is_refreshing": False,
                                           "chips_loaded": True, "warroom_summary": stale})
        monkeypatch.setattr(WA, "st", fake)
        res = WA.compute_and_store_warroom_summary()
        assert res.popped and not res.written and "warroom_summary" not in fake.session_state
        for kw in ({}, {"require_valid_risk_cap": True}):
            _assert_unloaded(AS.get_macro_regime(**kw))
        assert AS.get_macro_regime(strict=True)["is_loaded"] is False     # strict 不拋


# ══════════════════════════════════════════════════════════════════
# 2. 下游（冷啟動：空 session ＋ 有效檔）
# ══════════════════════════════════════════════════════════════════
class TestDownstreamColdStart:

    def test_ai_scoring_gate_refuses(self, files, monkeypatch):
        import src.services.ai_qa_service as Q
        _fake_session(monkeypatch)
        dec = Q._scoring_regime()
        assert dec.usable is False and dec.regime is None
        assert dec.not_loaded_pending_breadth is True and dec.breadth_unevaluated is False
        n = dec.notice()
        assert _OLD_GATE_RETRY not in n and "載入後市場位階仍為未評估" in n

    @pytest.mark.parametrize("rvrc", [False, True])
    def test_ai_market_state_not_ok(self, files, monkeypatch, rvrc):
        import src.services.ai_qa_service as Q
        from shared.regime_arbiter import NOT_LOADED_PENDING_BREADTH_EXPLAIN
        _fake_session(monkeypatch)
        r = Q._tool_get_market_state(require_valid_risk_cap=rvrc)
        assert r["ok"] is False and "data" not in r
        assert NOT_LOADED_PENDING_BREADTH_EXPLAIN in r["error"]
        assert _OLD_QA_ERR not in r["error"] and "bull" not in r["error"] and "bear" not in r["error"]

    def test_find_page_no_filter(self, files, monkeypatch):
        from src.ui.views import page_find as F
        _fake_session(monkeypatch)
        assert F._load_regime() == (None, "")

    def test_hold_card4_not_live_no_direction(self, files, monkeypatch):
        from shared.ui_state import UI_LIVE
        from src.ui.views import page_hold as H
        _fake_session(monkeypatch)
        mr = H.load_macro(H.HoldRequest(submitted=True))
        assert mr.loaded is False and mr.not_loaded_pending_breadth is True and not mr.error
        card, facts, chip = H.build_macro_stage_card(mr)
        assert card.state != UI_LIVE and card.value in ("", None) and chip == ""
        _blob = json.dumps([card.note.now, card.note.why, card.note.where, facts], ensure_ascii=False)
        assert "bull" not in _blob and "bear" not in _blob
        assert card.note.why == H.NOT_LOADED_PENDING_BREADTH_WHY_HOLD
        assert card.note.where == H.NOT_LOADED_PENDING_BREADTH_WHERE_HOLD
        assert "載入後位階仍為未評估" in card.note.where

    def test_switch_stance_unevaluated(self, files, monkeypatch):
        from src.services.dividend_station_service import build_switch_advice, get_station_macro
        _fake_session(monkeypatch)
        m = get_station_macro(strict=True)
        assert m["loaded"] is False and m["regime"] == "unknown" and m["defense"] is None
        adv = build_switch_advice([], m, [])
        assert adv["stance"] not in ("aggressive", "defensive")
        assert adv["stance"] == "unknown"

    def test_allocation_drivers_truthful(self, files, monkeypatch):
        from shared.regime_arbiter import NOT_LOADED_PENDING_BREADTH_EXPLAIN
        from src.services import allocation_service as AS
        _fake_session(monkeypatch)
        a = AS.get_allocation(strict=True, require_valid_risk_cap=True)
        assert a.is_loaded is False and a.regime == "unknown"
        assert a.drivers == (NOT_LOADED_PENDING_BREADTH_EXPLAIN,) and _OLD_DRIVER not in a.drivers
        assert a.unevaluated_reason == ""

    def test_today_cards_1_3_and_status_bar_idle_grey(self, files, monkeypatch):
        from shared.ui_state import UI_IDLE
        from src.services import allocation_service as AS
        from src.ui.tabs.tab_today import build_status_bar_cards
        from src.ui.views import page_today as P
        _fake_session(monkeypatch)
        alloc, regime = AS.get_allocation(), AS.get_macro_regime()
        tiles = {t.card.key: t for t in P.build_verdict_tiles(
            alloc=alloc, alloc_error="", danger=None, danger_error="",
            danger_requested=False, regime=regime, regime_error="")}
        why = P.not_loaded_pending_breadth_why()
        for key in ("verdict.exposure", "verdict.regime"):
            c = tiles[key].card
            assert c.state == UI_IDLE, (key, c.state)
            assert c.note.why == why and c.note.where is P.EXIT_LOAD_PENDING_BREADTH, key
            assert _OLD_FOUR_SOURCES not in c.note.why and "四條來源一條都沒寫進來" not in c.note.why
        bar = [P.contract_exit_retargeted(c, regime) for c in build_status_bar_cards(regime)]
        macro = next(c for c in bar if c.key == "statusbar.macro")
        assert macro.state == UI_IDLE and macro.note.why == why
        assert macro.note.where is P.EXIT_LOAD_PENDING_BREADTH and _OLD_FOUR_SOURCES not in macro.note.why
        # v2 卡面短語有登記（漏登＝渲染當下 KeyError＝紅卡）
        assert dict(P.V2_EXIT_PHRASES)[P.EXIT_LOAD_PENDING_BREADTH]

    def test_today_summary_regime_cell_retargeted(self, files, monkeypatch):
        from src.services import allocation_service as AS
        from src.ui.tabs.tab_today import build_status_bar_card
        from src.ui.views import page_today as P
        _fake_session(monkeypatch)
        regime = AS.get_macro_regime()
        c = P.contract_exit_retargeted(build_status_bar_card(regime), regime)
        assert c.note.why == P.not_loaded_pending_breadth_why()

    def test_flag_on_downstream_old_wording(self, files, monkeypatch):
        """旗標 True ⇒ 冷啟動照舊吃規則引擎位階（下游可評分）—— 新文案不觸發。"""
        import src.services.ai_qa_service as Q
        from src.ui.views import page_find as F
        d, en = files
        _flag(monkeypatch, True)
        _fake_session(monkeypatch)
        dec = Q._scoring_regime()
        assert dec.usable is True and dec.regime == en
        assert F._load_regime() == (en, "")
        assert Q._tool_get_market_state()["ok"] is True


# ══════════════════════════════════════════════════════════════════
# 3. 文案（旗標兩態）
# ══════════════════════════════════════════════════════════════════
class TestWording:

    def test_explain_is_grey_not_error_and_no_promise(self):
        from shared.regime_arbiter import NOT_LOADED_PENDING_BREADTH_EXPLAIN as S
        assert "尚未載入" in S and "載入後市場位階仍為未評估" in S and "正式的市場廣度" in S
        for bad in ("錯誤", "失敗", "無可用的鎖定快照", "就會有"):
            assert bad not in S, bad

    def test_helper_flag_on_is_false(self, monkeypatch):
        from shared.regime_arbiter import SOURCE_UNLOADED, is_not_loaded_pending_breadth
        st = {"is_loaded": False, "source": SOURCE_UNLOADED}
        assert is_not_loaded_pending_breadth(st) is True
        assert is_not_loaded_pending_breadth({}) is False                  # 缺 source ⇒ 不推定
        assert is_not_loaded_pending_breadth(None) is False
        assert is_not_loaded_pending_breadth(dict(st, is_loaded=True)) is False
        _flag(monkeypatch, True)
        assert is_not_loaded_pending_breadth(st) is False

    def test_gate_notice_flag_on_unchanged(self, monkeypatch):
        from shared.regime_arbiter import SOURCE_UNLOADED
        from shared.scoring_regime_gate import resolve_scoring_regime
        st = {"is_loaded": False, "source": SOURCE_UNLOADED, "regime": "unknown"}
        assert _OLD_GATE_RETRY not in resolve_scoring_regime(st).notice()
        _flag(monkeypatch, True)
        dec = resolve_scoring_regime(st)
        assert dec.not_loaded_pending_breadth is False and _OLD_GATE_RETRY in dec.notice()

    def test_allocation_driver_flag_on_unchanged(self, monkeypatch):
        from shared.allocation_decision import build_allocation_decision
        from shared.regime_arbiter import SOURCE_UNLOADED
        st = {"is_loaded": False, "source": SOURCE_UNLOADED, "regime": "unknown"}
        assert build_allocation_decision(st).drivers != (_OLD_DRIVER,)
        _flag(monkeypatch, True)
        assert build_allocation_decision(st).drivers == (_OLD_DRIVER,)
        assert build_allocation_decision(None).drivers == (_OLD_DRIVER,)   # 非契約輸入照舊

    def test_ai_qa_flag_on_old_error(self, tmp_path, monkeypatch):
        import src.services.ai_qa_service as Q
        monkeypatch.chdir(tmp_path)                    # 沒有檔 ⇒ 未評估
        _flag(monkeypatch, True)
        _fake_session(monkeypatch)
        r = Q._tool_get_market_state()
        assert r["ok"] is False and _OLD_QA_ERR in r["error"]

    def test_today_card3_flag_on_old_why(self, tmp_path, monkeypatch):
        from src.services import allocation_service as AS
        from src.ui.views import page_today as P
        monkeypatch.chdir(tmp_path)
        _flag(monkeypatch, True)
        _fake_session(monkeypatch)
        tiles = {t.card.key: t for t in P.build_verdict_tiles(
            alloc=AS.get_allocation(), alloc_error="", danger=None, danger_error="",
            danger_requested=False, regime=AS.get_macro_regime(), regime_error="")}
        c = tiles["verdict.regime"].card
        assert _OLD_FOUR_SOURCES in c.note.why and c.note.where is P.EXIT_RETRY_HERE


# ══════════════════════════════════════════════════════════════════
# 4. 突變：拔掉新條件 ⇒ 行為測試轉紅
# ══════════════════════════════════════════════════════════════════
_ANCHOR = "    _nowr_no_real_breadth = (not _wr_ok and not _wr_breadth and _file_ok"


def _mutant_get_macro_state():
    import src.services.macro_state_locker as MSL
    src = (REPO / _MSL_REL).read_text(encoding="utf-8")
    assert src.count(_ANCHOR) == 1
    mut = src.replace(_ANCHOR, "    _nowr_no_real_breadth = False and (not _wr_ok and not _wr_breadth and _file_ok")
    m = types.ModuleType("_msl_nowr_mut")
    m.__file__ = MSL.__file__
    exec(compile(mut, MSL.__file__, "exec"), m.__dict__)
    return m.get_macro_state


class TestMutation:

    def test_remove_new_condition_falls_back_to_rule_engine(self, files):
        from shared.regime_arbiter import SOURCE_FILE_RULE_ENGINE
        d, en = files
        mut = _mutant_get_macro_state()
        st = mut(None, state_file_path=str(d / "macro_state.json"))
        assert st["source"] == SOURCE_FILE_RULE_ENGINE and st["regime"] == en and st["is_loaded"] is True
        with pytest.raises(AssertionError):
            _assert_unloaded(st)

    def test_remove_new_condition_downstream_turns_red(self, files, monkeypatch):
        """突變體接進全站 regime 橋樑 ⇒ AI 評分閘重新放行（＝行為測試會紅）。"""
        import src.services.ai_qa_service as Q
        import src.services.macro_state_locker as MSL
        _fake_session(monkeypatch)
        monkeypatch.setattr(MSL, "get_macro_state", _mutant_get_macro_state())
        assert Q._scoring_regime().usable is True
        with pytest.raises(AssertionError):
            TestDownstreamColdStart().test_ai_scoring_gate_refuses(files, monkeypatch)
