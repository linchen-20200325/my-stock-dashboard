"""QA-4 S-1（2026-10-23）：「缺真實市場廣度 ⇒ 未評估」的新 UI 文案，在兩種情境各講屬實的那一句。

情境（區分依據來自資料：紅綠燈當輪吃的 `jingqi_info` ／ `cl_data['adl']`，
經 L0 `shared.macro_provenance.breadth_proxy_held_back` → L3 `section_inputs.breadth_proxy_presence`
→ 橋 `allocation_service.get_breadth_proxy_presence`）：

  · A ＝ 有被擋下的代理值（旌旗只有加權指數推估的代理值，依 DEC-074 不計分）；
  · B ＝ 本輪沒有任何代理值（^TWII 全滅：旌旗與 ADL 都沒有；法人還在 ⇒ warroom 仍存在）。

每個讀點兩態各一：斷言出現對的那一句，且**不出現對方情境的不實句**；
另有突變（拔掉選擇邏輯 ⇒ 紅）。凍結的舊 UI 不在本檔範圍。
"""
from __future__ import annotations

import types

import pytest

import src.services.allocation_service as AL
from shared import regime_arbiter as RA
from shared.macro_provenance import breadth_proxy_held_back
from shared.ui_state import UI_EMPTY
from src.compute.macro.macro_helpers import calc_traffic_light
from src.compute.macro.warroom_summary import build_warroom_summary
from src.services.section_inputs import breadth_proxy_presence
from src.ui.views import page_hold as PH
from src.ui.views import page_today as P

#: 情境 A 才屬實、在 B 不實的句子。
_A_ONLY = ("目前只有由加權指數推估的代理值", "目前只有加權指數推估的代理值")
#: 情境 B 才屬實、在 A 不實的句子。
_B_ONLY = ("也沒有任何廣度資料", "代理值也沒有")
#: 兩種情境下都不屬實（QA-4 S-1 點名）的舊句。
_NEVER = ("不是這一輪沒抓到", "已經去讀過")

_MKT_A = {"regime": "bull", "score": 4}
_JQ_A = {"avg": 55.0, "is_proxy": True}
_CD_B = {"inst": {"外資及陸資": {"net": 12.3}}}


def _session(scenario: str) -> dict:
    """真的走 L2 `calc_traffic_light` → `build_warroom_summary`，組出該情境的 session。"""
    if scenario == "A":
        _tl = calc_traffic_light(_MKT_A, dict(_JQ_A), {}, None)
        return {"warroom_summary": build_warroom_summary(_tl, _MKT_A),
                "mkt_info": dict(_MKT_A), "jingqi_info": dict(_JQ_A), "cl_data": {}}
    _tl = calc_traffic_light({}, {}, dict(_CD_B), None)
    return {"warroom_summary": build_warroom_summary(_tl, {}), "cl_data": dict(_CD_B)}


@pytest.fixture
def ss(tmp_path, monkeypatch):
    """CWD → tmp（不讀 repo 根的 `macro_state.json`）；session 換成 dict。回傳設定 session 的函式。"""
    monkeypatch.chdir(tmp_path)

    def _set(scenario: str) -> dict:
        _s = _session(scenario)
        monkeypatch.setattr(AL, "st", types.SimpleNamespace(session_state=_s))
        return _s
    return _set


def _assert_scenario(text: str, scenario: str) -> None:
    for _bad in _NEVER:
        assert _bad not in text, (_bad, text)
    if scenario == "A":
        assert any(_ok in text for _ok in _A_ONLY), text
        for _bad in _B_ONLY:
            assert _bad not in text, (_bad, text)
    else:
        assert any(_ok in text for _ok in _B_ONLY), text
        for _bad in _A_ONLY:
            assert _bad not in text, (_bad, text)


# ── 區分訊號本身 ────────────────────────────────────────────────────
class TestSignal:
    def test_l0_three_states(self):
        assert breadth_proxy_held_back({"avg": 55.0, "is_proxy": True}, None) is True
        assert breadth_proxy_held_back(None, None) is False
        assert breadth_proxy_held_back({"avg": None}, None) is False
        assert breadth_proxy_held_back({"avg": float("nan"), "is_proxy": True}, None) is False
        # 真值旌旗 ⇒ 不是「被擋下的代理值」，也不是「沒有任何廣度」⇒ 拿不準（中性句）。
        assert breadth_proxy_held_back({"avg": 55.0, "is_proxy": False}, None) is None

    def test_l0_adl_proxy_counts(self):
        import pandas as pd
        _adl = pd.DataFrame({"ad_ratio": [0.5], "is_proxy": [True]})
        assert breadth_proxy_held_back(None, _adl) is True
        _real = pd.DataFrame({"ad_ratio": [0.5], "is_proxy": [False]})
        assert breadth_proxy_held_back(None, _real) is None   # 有真值列 ⇒ 拿不準，⛔ 不猜成「沒有」

    def test_l3_presence_matches_scenarios(self, ss):
        assert breadth_proxy_presence(ss("A")) is True
        assert breadth_proxy_presence(ss("B")) is False
        assert breadth_proxy_presence(None) is None

    def test_contract_is_breadth_in_both(self, ss):
        """兩種情境都是「缺真實廣度 ⇒ 未評估」（前提成立，下面的文案測試才有意義）。"""
        for _sc in ("A", "B"):
            ss(_sc)
            assert RA.is_breadth_unevaluated(AL.get_macro_regime(require_valid_risk_cap=True)), _sc

    def test_bridge_reads_session(self, ss):
        ss("A")
        assert AL.get_breadth_proxy_presence() is True
        ss("B")
        assert AL.get_breadth_proxy_presence() is False


# ── 今天頁 ─────────────────────────────────────────────────────────
def _verdict(scenario: str):
    _reg = AL.get_macro_regime(require_valid_risk_cap=True)
    _tiles = P.build_verdict_tiles(
        alloc=AL.get_allocation(require_valid_risk_cap=True), alloc_error="",
        danger=None, danger_error="", danger_requested=False,
        regime=_reg, regime_error="", breadth_proxy=P._load_breadth_proxy())
    return {_t.card.key: _t.card for _t in _tiles}


class TestPageToday:
    @pytest.mark.parametrize("scenario", ["A", "B"])
    def test_cards_1_and_3(self, ss, scenario):
        ss(scenario)
        _cards = _verdict(scenario)
        for _key in ("verdict.exposure", "verdict.regime"):
            _n = _cards[_key].note
            assert _n.where is P.EXIT_WAIT_BREADTH_SOURCE, _key
            _assert_scenario(_n.why, scenario)
            for _bad in _NEVER + _A_ONLY + _B_ONLY:   # 出口兩態共用 ⇒ 兩邊的情境句都不得出現
                assert _bad not in _n.where, (_key, _bad)

    @pytest.mark.parametrize("scenario", ["A", "B"])
    def test_status_bar_and_summary_retarget(self, ss, scenario):
        ss(scenario)
        _reg = AL.get_macro_regime(require_valid_risk_cap=True)
        _card = P.Card(key="x", label="x", state=UI_EMPTY,
                       note=P.Note(now="n", why="w", where=P.CONTRACT_NO_EXIT_WHERE))
        _out = P.contract_exit_retargeted(_card, _reg, P._load_breadth_proxy())
        assert _out.note.where is P.EXIT_WAIT_BREADTH_SOURCE
        _assert_scenario(_out.note.why, scenario)

    def test_neutral_when_signal_unknown(self):
        """拿不到區分訊號（None）⇒ 中性句：兩種情境的情境句都不出現。"""
        for _txt in (P.breadth_unevaluated_why(None), P.EXIT_WAIT_BREADTH_SOURCE,
                     RA.unevaluated_breadth_explain(None), PH._breadth_empty_why(None),
                     PH._BREADTH_EMPTY_WHERE):
            for _bad in _NEVER + _A_ONLY + _B_ONLY:
                assert _bad not in _txt, (_bad, _txt)
            assert "更新資料不會改變" in _txt or "不計分" in _txt, _txt

    def test_mutant_selection_removed_turns_red(self, ss, monkeypatch):
        """突變：拔掉選擇邏輯（一律回中性句）⇒ 兩種情境的斷言都紅。"""
        monkeypatch.setattr(P, "breadth_unevaluated_why", lambda breadth_proxy=None: P.BREADTH_UNEVALUATED_WHY)
        for _sc in ("A", "B"):
            ss(_sc)
            with pytest.raises(AssertionError):
                _assert_scenario(_verdict(_sc)["verdict.regime"].note.why, _sc)


# ── 持股頁 ─────────────────────────────────────────────────────────
_SUBMITTED = PH.HoldRequest(submitted=True)


class TestPageHold:
    @pytest.mark.parametrize("scenario", ["A", "B"])
    def test_macro_stage_and_position_cap(self, ss, scenario):
        ss(scenario)
        _stage = PH.build_macro_stage_card(PH.load_macro(_SUBMITTED))[0]
        _cap = PH.build_position_cap_card(PH.load_allocation(_SUBMITTED))[0]
        for _c in (_stage, _cap):
            assert _c.state == UI_EMPTY, (_c.key, _c.state)
            assert _c.note.where == PH._BREADTH_EMPTY_WHERE, _c.key
            assert "缺真實市場廣度" in _c.note.why
            _assert_scenario(_c.note.why, scenario)

    def test_mutant_selection_removed_turns_red(self, ss, monkeypatch):
        import shared.regime_arbiter as RA_m
        monkeypatch.setattr(RA_m, "unevaluated_breadth_explain",
                            lambda proxy_held_back=None: RA_m.UNEVALUATED_BREADTH_EXPLAIN)
        for _sc in ("A", "B"):
            ss(_sc)
            _c = PH.build_macro_stage_card(PH.load_macro(_SUBMITTED))[0]
            with pytest.raises(AssertionError):
                _assert_scenario(_c.note.why, _sc)


# ── AI 問答 ────────────────────────────────────────────────────────
class TestAiQa:
    @pytest.mark.parametrize("scenario", ["A", "B"])
    def test_market_state_error(self, ss, scenario):
        from src.services import ai_qa_service as AQ
        ss(scenario)
        _r = AQ._tool_get_market_state(require_valid_risk_cap=True)
        assert _r["ok"] is False
        _assert_scenario(_r["error"], scenario)

    def test_mutant_signal_removed_turns_red(self, ss, monkeypatch):
        from src.services import ai_qa_service as AQ
        monkeypatch.setattr(AL, "get_breadth_proxy_presence", lambda: None)
        for _sc in ("A", "B"):
            ss(_sc)
            with pytest.raises(AssertionError):
                _assert_scenario(AQ._tool_get_market_state(require_valid_risk_cap=True)["error"], _sc)


# ── allocation_decision（L0，拿不到區分訊號 ⇒ 中性句）──────────────────
class TestAllocationDrivers:
    @pytest.mark.parametrize("scenario", ["A", "B"])
    def test_drivers_neutral(self, ss, scenario):
        ss(scenario)
        _a = AL.get_allocation(require_valid_risk_cap=True)
        assert _a.unevaluated_reason == "breadth"
        for _d in _a.drivers:
            for _bad in _NEVER + _A_ONLY + _B_ONLY:
                assert _bad not in _d, (_bad, _d)


def test_page_today_render_wires_signal():
    """`render_page_today` 每一個廣度文案讀點都要把同一個 `_breadth_proxy` 傳下去（漏傳 ⇒ 退中性句，訊號白算）。

    結構守衛（AST）：渲染需要 Streamlit runtime，上面的行為測試直接呼叫 builder；這裡補「接線有沒有接上」。
    """
    import ast
    import inspect
    _tree = ast.parse(inspect.getsource(P.render_page_today))
    _need = {"build_verdict_tiles", "build_summary_tiles", "contract_exit_retargeted"}
    _seen: dict = {}
    for _node in ast.walk(_tree):
        if isinstance(_node, ast.Call) and isinstance(_node.func, ast.Name) and _node.func.id in _need:
            _passed = (any(_k.arg == "breadth_proxy" and isinstance(_k.value, ast.Name)
                           and _k.value.id == "_breadth_proxy" for _k in _node.keywords)
                       or any(isinstance(_a, ast.Name) and _a.id == "_breadth_proxy" for _a in _node.args))
            _seen.setdefault(_node.func.id, []).append(_passed)
    assert set(_seen) == _need, _seen
    assert all(all(_v) for _v in _seen.values()), _seen
    _assigns = [_n for _n in ast.walk(_tree) if isinstance(_n, ast.Assign)
                and any(isinstance(_t, ast.Name) and _t.id == "_breadth_proxy" for _t in _n.targets)]
    assert len(_assigns) == 1 and isinstance(_assigns[0].value, ast.Call) \
        and getattr(_assigns[0].value.func, "id", "") == "_load_breadth_proxy"
