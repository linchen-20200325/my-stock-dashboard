"""批次 2：「💼 我的持股」換股卡 `hold.switch` —— 「取數失敗」與「真的沒有建議」必須分得開。

（客戶 2026-09-26 授權本批改 L3，限 `hold.switch` 與配息卡所需的判定。）

每條失敗路徑三件事：
  (a) 上游失敗 → 紅卡 `SWITCH_FAILED_NOW`；⛔ 不得是 `UI_EMPTY`「這是一個有效的結果」，
      ⛔ 不得是 live「換入 0 檔」；
  (b) 真的 0 → 原封不動（`SWITCH_EMPTY_NOW`、now / why 一字未改）；
  (c) 突變：拿掉本批新加的那一條判定 → (a) 必須失敗。

⚠️ 配息卡 `hold.deep.dividend_cash` **本批未修**：L1 `fetch_etf_dividends` 對例外與
「真的沒配息」都回同一個無 attrs 的空 Series，L3 手上沒有任何訊號分得出兩者 ——
需要改 L1，不在本批授權內，已停手上報，故本檔**沒有**它的測試。
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys
import types

import pandas as pd
import pytest

import src.services.dividend_station_service as DSS
import src.services.fundamental_screener_service as FSS
from shared.station_specs import MISS_FETCH_FAILED, MISS_TEXT
from shared.ui_state import UI_EMPTY, UI_FAILED, UI_LIVE
from src.ui.views import page_hold as PH

_VALID = "有效的結果"
_EMPTY_POOL_NOTE = "基本面存活池為空（季快照未就緒）。"


def _mutant(mod: types.ModuleType, old: str, new: str) -> types.ModuleType:
    """把 `mod` 的原始碼裡**恰好一處** `old` 換成 `new`，載成一個獨立的新模組。"""
    src = pathlib.Path(mod.__file__).read_text(encoding="utf-8")
    assert src.count(old) == 1, f"突變點不唯一或已不存在：{old!r}"
    name = f"_mutant_b2_{mod.__name__.rsplit('.', 1)[-1]}"
    spec = importlib.util.spec_from_loader(name, loader=None)
    m = importlib.util.module_from_spec(spec)
    m.__file__ = mod.__file__
    sys.modules[name] = m
    try:
        exec(compile(src.replace(old, new), mod.__file__, "exec"), m.__dict__)
    finally:
        sys.modules.pop(name, None)
    return m


_SURV = pd.DataFrame({"stock_id": ["1101", "2412"], "eps": [3.0, 5.0]})
_RANKED = pd.DataFrame({"代碼": ["2330", "2412"], "名稱": ["台積電", "中華電"],
                        "綜合分": [90.0, 80.0]})


def _boom(*_a, **_k):
    raise RuntimeError("fundamentals snapshot missing")


# ══════════════════════════════════════════════════════════════════
# L3 `get_switch_in_candidates(strict=True)`
# ══════════════════════════════════════════════════════════════════
class TestL3Strict:
    def test_a_survivors_exception_propagates(self, monkeypatch):
        monkeypatch.setattr(FSS, "get_fundamental_survivors", _boom)
        with pytest.raises(RuntimeError, match="fundamentals snapshot missing"):
            DSS.get_switch_in_candidates(strict=True)

    def test_a_empty_pool_raises_with_the_rankers_own_note(self, monkeypatch):
        monkeypatch.setattr(FSS, "get_fundamental_survivors",
                            lambda **_k: (pd.DataFrame(), {}))
        monkeypatch.setattr(FSS, "get_ranked_picks", _boom)   # 空池不得再去掃
        with pytest.raises(RuntimeError) as ei:
            DSS.get_switch_in_candidates(strict=True)
        assert str(ei.value) == _EMPTY_POOL_NOTE

    def test_b_genuine_zero_after_ranking_is_empty_list(self, monkeypatch):
        _seen = {}

        def _ranked(factors, **kw):
            _seen.update(kw)
            return pd.DataFrame(columns=["代碼", "名稱"]), "空頭濾網剔除全部"

        monkeypatch.setattr(FSS, "get_fundamental_survivors", lambda **_k: (_SURV, {}))
        monkeypatch.setattr(FSS, "get_ranked_picks", _ranked)
        assert DSS.get_switch_in_candidates(strict=True, regime="bear") == []
        assert _seen["survivors_df"] is _SURV      # 自己抓的池子有傳進去
        assert _seen["regime"] == "bear"

    def test_b_candidates_still_exclude_held(self, monkeypatch):
        monkeypatch.setattr(FSS, "get_fundamental_survivors", lambda **_k: (_SURV, {}))
        monkeypatch.setattr(FSS, "get_ranked_picks", lambda f, **kw: (_RANKED, ""))
        out = DSS.get_switch_in_candidates(strict=True, exclude=["2330.TW"])
        assert [c["代碼"] for c in out] == ["2412"]

    def test_b_default_non_strict_behaviour_unchanged(self, monkeypatch):
        """既有 caller（v1 ETF 分頁 / 推播腳本）不傳 strict → 失敗照舊回 []。"""
        monkeypatch.setattr(FSS, "get_ranked_picks", _boom)
        assert DSS.get_switch_in_candidates() == []
        monkeypatch.setattr(FSS, "get_ranked_picks",
                            lambda f, **kw: (pd.DataFrame(), _EMPTY_POOL_NOTE))
        assert DSS.get_switch_in_candidates() == []
        monkeypatch.setattr(FSS, "get_ranked_picks", lambda f, **kw: (_RANKED, ""))
        assert [c["代碼"] for c in DSS.get_switch_in_candidates(exclude=["2330"])] == ["2412"]

    def test_c_mutation_removing_the_raise_swallows_again(self, monkeypatch):
        m = _mutant(DSS, "factors=_factors)\n        raise RuntimeError(_note)\n",
                    "factors=_factors)\n        return None\n")
        monkeypatch.setattr(FSS, "get_fundamental_survivors",
                            lambda **_k: (pd.DataFrame(), {}))
        assert m.get_switch_in_candidates(strict=True) == [], (
            "拿掉 raise 後空池又會回 [] —— 否則上面的 (a) 沒有守到東西")


# ══════════════════════════════════════════════════════════════════
# L5 `load_switch` ＋ `build_switch_card`
# ══════════════════════════════════════════════════════════════════
_MACRO = PH.MacroReadout(requested=True, loaded=True, regime="bull", defense=False)
_HELD_RED = {"代號": "2330", "held": True, "健檢": "🔴", "建議動作": "汰弱", "_detail": {}}
_HELD_OK = {"代號": "0056", "held": True, "健檢": "🟢", "建議動作": "續抱", "_detail": {}}
_WATCH_GREEN = {"代號": "2412", "名稱": "中華電", "held": False, "健檢": "🟢", "_detail": {}}
_ROW_ERR = {"代號": "2454", "held": True, "健檢": "⚪",
            "建議動作": "⚠️ 資料不足/抓取失敗：HTTPError 502",
            "_detail": {"error": "HTTPError 502"}}


def _station(rows):
    return PH.StationReadout(requested=True, submitted=True, bound=True,
                             holdings_n=len(rows), rows=tuple(rows))


def _holdings(rows):
    return PH.HoldingsReadout(requested=True, submitted=True, bound=True, holdings=tuple(
        {"ticker": r["代號"], "held": r.get("held", False), "lots": 1, "avg_price": 1.0}
        for r in rows))


def _run(P, rows, monkeypatch, cands):
    """真的 L3 `build_switch_advice`（純函式）＋ 假的候選來源。"""
    _seen = {}

    def _fake(*, regime=None, exclude=None, top_n=5, strict=False):
        _seen["strict"] = strict
        if isinstance(cands, BaseException):
            raise cands
        return list(cands)

    monkeypatch.setattr(DSS, "get_switch_in_candidates", _fake)
    st = _station(rows)
    sw = P.load_switch(st, _MACRO, _holdings(rows))
    return P.build_switch_card(sw, st), sw, _seen


_POOL_ERR = RuntimeError("fundamentals snapshot missing")


class TestHoldSwitchPoolFailure:
    def test_page_asks_l3_to_be_strict(self, monkeypatch):
        _, _, seen = _run(PH, (_HELD_OK,), monkeypatch, [])
        assert seen["strict"] is True

    def test_a_pool_failure_with_nothing_to_switch_out_is_not_a_valid_empty(self, monkeypatch):
        built, sw, _ = _run(PH, (_HELD_OK,), monkeypatch, _POOL_ERR)
        card = built[0]
        assert card.state == UI_FAILED and card.state != UI_EMPTY
        assert card.note.now == PH.SWITCH_FAILED_NOW
        assert _VALID not in card.note.why
        assert "fundamentals snapshot missing" in card.note.why
        assert PH.SRC_SWITCH.split("（")[0] in card.note.why
        PH.v2_card_html(*built)                       # 短句表對得上

    def test_a_pool_failure_with_a_switch_out_is_not_live_switch_in_zero(self, monkeypatch):
        built, _, _ = _run(PH, (_HELD_RED,), monkeypatch, _POOL_ERR)
        card = built[0]
        assert card.state == UI_FAILED
        assert "換入 0 檔" not in (card.value or "")
        # 已算出的換出沒有被藏起來
        assert any("2330" in v for _, v in built[1])

    def test_b_pool_not_needed_when_watchlist_has_a_green(self, monkeypatch):
        """觀察清單有綠燈 → L3 根本不看選股池 → 選股池失敗不影響這一輪。"""
        built, sw, _ = _run(PH, (_HELD_RED, _WATCH_GREEN), monkeypatch, _POOL_ERR)
        assert not sw.error and sw.switch_in_src == "watchlist"
        assert built[0].state == UI_LIVE

    def test_b_genuine_zero_is_unchanged(self, monkeypatch):
        built, _, _ = _run(PH, (_HELD_OK,), monkeypatch, [])
        card = built[0]
        assert card.state == UI_EMPTY
        assert card.note.now == PH.SWITCH_EMPTY_NOW
        assert _VALID in card.note.why

    def test_b_genuine_switch_out_with_zero_in_stays_live(self, monkeypatch):
        built, _, _ = _run(PH, (_HELD_RED,), monkeypatch, [])
        assert built[0].state == UI_LIVE and "換入 0 檔" in built[0].value

    def test_a_end_to_end_through_the_real_l3(self, monkeypatch):
        monkeypatch.setattr(FSS, "get_fundamental_survivors", _boom)
        st = _station((_HELD_OK,))
        card = PH.build_switch_card(PH.load_switch(st, _MACRO, _holdings((_HELD_OK,))), st)[0]
        assert card.state == UI_FAILED and card.note.now == PH.SWITCH_FAILED_NOW

    def test_c_mutation_removing_the_check_turns_a_green_again(self, monkeypatch):
        m = _mutant(PH, '_in_failed = bool(_cands_err and _adv.get("switch_in_src") == "screener")',
                    "_in_failed = False")
        built, _, _ = _run(m, (_HELD_OK,), monkeypatch, _POOL_ERR)
        assert built[0].state == UI_EMPTY and _VALID in built[0].note.why, (
            "拿掉新判定後 (a) 必須失敗 —— 否則 (a) 沒有守到東西")


class TestHoldSwitchRowFetchFailure:
    def test_a_a_fetch_failed_row_is_not_a_valid_empty(self, monkeypatch):
        built, _, _ = _run(PH, (_HELD_OK, _ROW_ERR), monkeypatch, [])
        card = built[0]
        assert card.state == UI_FAILED
        assert card.note.now == PH.SWITCH_FAILED_NOW
        assert _VALID not in card.note.why
        assert card.note.why.startswith("2454：")
        # QA 修正 2：where 同 ⑤ 停利卡（原因多半是代號或來源 → 指路確認網路／授權），
        # ⛔ 不是呼叫期例外那一句「沒有你可以執行的出口」。
        assert card.note.where == PH.STATION_ERROR_WHERE
        assert MISS_TEXT[MISS_FETCH_FAILED].removeprefix("這一檔") in card.note.why
        face = PH.v2_short_rows(card)[0]
        assert face[1][1] == "整批抓取失敗 —— 看該列的錯誤訊息"
        assert face[2][1] == PH._V2_CHECK_NET
        PH.v2_card_html(*built)

    def test_a_a_fetch_failed_row_next_to_a_switch_out_is_not_live(self, monkeypatch):
        built, _, _ = _run(PH, (_HELD_RED, _ROW_ERR), monkeypatch, [])
        assert built[0].state == UI_FAILED
        assert any("2330" in v for _, v in built[1])   # 換出那檔仍列在 facts

    def test_a_watchlist_fetch_failure_counts_too(self, monkeypatch):
        """觀察清單那一檔若本來是綠燈，它會優先成為換入 —— 沒判過就不算完整。"""
        _w = dict(_ROW_ERR, 代號="3008", held=False)
        built, _, _ = _run(PH, (_HELD_OK, _w), monkeypatch, [])
        assert built[0].state == UI_FAILED and "3008" in built[0].note.why

    def test_b_the_exception_path_keeps_its_own_why(self, monkeypatch):
        built, _, _ = _run(PH, (_HELD_OK, _ROW_ERR), monkeypatch, _POOL_ERR)
        assert "fundamentals snapshot missing" in built[0].note.why

    def test_c_mutation_removing_the_check_turns_a_green_again(self, monkeypatch):
        m = _mutant(PH, "has_value=switch.has_advice and not _rows_failed,\n"
                        '        reason=MISS_FETCH_FAILED if _rows_failed else "")',
                    'has_value=switch.has_advice,\n        reason="")')
        built, _, _ = _run(m, (_HELD_OK, _ROW_ERR), monkeypatch, [])
        assert built[0].state == UI_EMPTY and _VALID in built[0].note.why
        built, _, _ = _run(m, (_HELD_RED, _ROW_ERR), monkeypatch, [])
        assert built[0].state == UI_LIVE

    def test_b_the_exception_path_keeps_its_own_where(self, monkeypatch):
        built, _, _ = _run(PH, (_HELD_OK,), monkeypatch, _POOL_ERR)
        assert PH.NO_EXIT_MARKER in built[0].note.where
        assert built[0].note.where != PH.STATION_ERROR_WHERE
        assert PH.v2_short_rows(built[0])[0][2][1] == PH._V2_NO_EXIT_REPORT

    def test_c_mutation_row_failure_where_falls_back_to_the_exception_where(self, monkeypatch):
        m = _mutant(PH, "        if switch.error:\n            _note = Note(now=SWITCH_FAILED_NOW,",
                    "        if True:\n            _note = Note(now=SWITCH_FAILED_NOW,")
        built, _, _ = _run(m, (_HELD_OK, _ROW_ERR), monkeypatch, [])
        assert built[0].note.where != PH.STATION_ERROR_WHERE


# ══════════════════════════════════════════════════════════════════
# QA 修正 1：⑦ AI 摘要與 ④ 卡看同一個失敗判定
# ══════════════════════════════════════════════════════════════════
class TestAiPayloadFollowsTheCard:
    def test_a_row_failure_drops_the_switch_section(self, monkeypatch):
        built, sw, _ = _run(PH, (_HELD_RED, _ROW_ERR), monkeypatch, [])
        assert built[0].state == UI_FAILED
        assert sw.failed and not sw.error
        assert PH._switch_payload(sw) is None

    def test_a_pool_failure_drops_the_switch_section(self, monkeypatch):
        _, sw, _ = _run(PH, (_HELD_RED,), monkeypatch, _POOL_ERR)
        assert PH._switch_payload(sw) is None

    def test_b_a_complete_round_still_carries_the_switch_section(self, monkeypatch):
        built, sw, _ = _run(PH, (_HELD_RED,), monkeypatch, [])
        assert built[0].state == UI_LIVE
        assert PH._switch_payload(sw)["switch_out"][0]["代號"] == "2330"

    def test_card_and_payload_agree_on_every_path(self, monkeypatch):
        for rows, cands in (((_HELD_RED,), []), ((_HELD_RED, _ROW_ERR), []),
                            ((_HELD_RED,), _POOL_ERR), ((_HELD_RED, _WATCH_GREEN), _POOL_ERR),
                            ((_HELD_OK, _ROW_ERR), [])):
            built, sw, _ = _run(PH, rows, monkeypatch, cands)
            assert (built[0].state == UI_FAILED) == sw.failed
            if sw.failed:
                assert PH._switch_payload(sw) is None

    def test_c_mutation_payload_checking_only_error_leaks_again(self, monkeypatch):
        m = _mutant(PH, "if switch.failed or not switch.has_advice:",
                    "if switch.error or not switch.has_advice:")
        _, sw, _ = _run(m, (_HELD_RED, _ROW_ERR), monkeypatch, [])
        assert m._switch_payload(sw) is not None


# ══════════════════════════════════════════════════════════════════
# QA 修正 3：選股池失敗但本輪沒用到（觀察清單有綠燈）→ 仍留 log
# ══════════════════════════════════════════════════════════════════
class TestUnusedPoolFailureIsLogged:
    def test_log_line_when_watchlist_green_masks_the_pool_failure(self, monkeypatch, capsys):
        built, sw, _ = _run(PH, (_HELD_RED, _WATCH_GREEN), monkeypatch, _POOL_ERR)
        assert built[0].state == UI_LIVE and not sw.failed          # 畫面不變
        assert "fundamentals snapshot missing" in capsys.readouterr().out

    def test_c_mutation_removing_the_log_is_caught(self, monkeypatch, capsys):
        m = _mutant(PH, "    elif _cands_err:\n        print(",
                    "    elif False:\n        print(")
        _run(m, (_HELD_RED, _WATCH_GREEN), monkeypatch, _POOL_ERR)
        assert "fundamentals snapshot missing" not in capsys.readouterr().out


# ══════════════════════════════════════════════════════════════════
# QA 修正 4：存活池有東西、但每一檔都因因子資料不足被排除
# ══════════════════════════════════════════════════════════════════
_SURV_NO_EPS = pd.DataFrame({"stock_id": ["1101", "2412"]})


def _all_unscored(factors, **kw):
    """真的排名器在「沒有任何因子有資料」時的回傳（drop_unscored=True → 全部排除）。"""
    return FSS.composite_rank_candidates(kw["survivors_df"], factors=list(factors),
                                         drop_unscored=True)


class TestL3StrictAllUnscored:
    def test_the_ranker_really_returns_empty_with_a_drop_note(self):
        df, note = FSS.composite_rank_candidates(_SURV_NO_EPS, factors=["eps_high"],
                                                 drop_unscored=True)
        assert df.empty and "2 檔未取得綜合分" in note

    @pytest.mark.parametrize("regime", [None, "bull", "neutral"])
    def test_a_non_bear_regime_raises_with_the_rankers_note(self, monkeypatch, regime):
        monkeypatch.setattr(FSS, "get_fundamental_survivors",
                            lambda **_k: (_SURV_NO_EPS, {}))
        monkeypatch.setattr(FSS, "get_ranked_picks", _all_unscored)
        with pytest.raises(RuntimeError, match="未取得綜合分"):
            DSS.get_switch_in_candidates(strict=True, regime=regime)

    @pytest.mark.parametrize("regime", ["bear", "caution"])
    def test_b_bear_regime_cannot_be_told_apart_so_it_stays_empty(self, monkeypatch, regime):
        """空頭 regime：濾網剔光（有效）與全部缺資料從回傳值分不出來 → 不猜，照舊回 []。"""
        monkeypatch.setattr(FSS, "get_fundamental_survivors",
                            lambda **_k: (_SURV_NO_EPS, {}))
        monkeypatch.setattr(FSS, "get_ranked_picks", _all_unscored)
        assert DSS.get_switch_in_candidates(strict=True, regime=regime) == []

    def test_a_page_turns_red(self, monkeypatch):
        monkeypatch.setattr(FSS, "get_fundamental_survivors",
                            lambda **_k: (_SURV_NO_EPS, {}))
        monkeypatch.setattr(FSS, "get_ranked_picks", _all_unscored)
        st = _station((_HELD_OK,))
        card = PH.build_switch_card(PH.load_switch(st, _MACRO, _holdings((_HELD_OK,))), st)[0]
        assert card.state == UI_FAILED and _VALID not in card.note.why

    def test_c_mutation_dropping_the_check_swallows_again(self, monkeypatch):
        m = _mutant(DSS, "and not _is_veto_regime(regime):", "and False:")
        monkeypatch.setattr(FSS, "get_fundamental_survivors",
                            lambda **_k: (_SURV_NO_EPS, {}))
        monkeypatch.setattr(FSS, "get_ranked_picks", _all_unscored)
        assert m.get_switch_in_candidates(strict=True) == []


# ══════════════════════════════════════════════════════════════════
# QA 補洞（2026-09-26）：`_is_veto_regime` 的 dict 分支原本沒有任何測試
#   （把 `regime = regime.get("regime")` 換成 `pass` 全綠）。
#   判定必須與選股網空頭濾網自己的 regime 判定**逐輸入一致**，否則兩邊會漂移：
#   濾網剔光（有效 0 檔）卻被 L3 當成「缺資料」raise，或反之。
# ══════════════════════════════════════════════════════════════════
def _fss_veto(regime) -> bool:
    """選股網濾網自己的 regime 判定（行為觀測，不讀原始碼）：

    `rs_rows=None` 時，否決態會加註「未套用空頭濾網」、非否決態原封不動回 note。
    """
    _note = "N"
    _, _out = FSS._apply_bear_market_filter(pd.DataFrame(), _note,
                                            regime=regime, rs_rows=None)
    return _out != _note


_VETO_INPUTS = [
    "bear", "caution", "bull", "neutral", "unknown", "", None,
    "BEAR", " bear", "Bear",                        # 大小寫 / 空白：兩邊都**不**正規化
    {"regime": "bear"}, {"regime": "caution"}, {"regime": "bull"},
    {"regime": None}, {}, {"light": "🔴"},          # 誤傳整個 macro-state dict
]


class TestVetoRegimeMatchesTheBearFilter:
    @pytest.mark.parametrize("regime", _VETO_INPUTS, ids=repr)
    def test_same_verdict_as_the_screeners_bear_filter(self, regime):
        assert DSS._is_veto_regime(regime) is _fss_veto(regime)

    @pytest.mark.parametrize("regime,expected", [
        ({"regime": "bear"}, True), ({"regime": "caution"}, True),
        ({"regime": "bull"}, False), ({}, False), (None, False),
        ("bear", True), ("caution", True), ("bull", False), ("BEAR", False),
    ], ids=repr)
    def test_explicit_truth_table(self, regime, expected):
        assert DSS._is_veto_regime(regime) is expected

    @pytest.mark.parametrize("regime", [["bear"], {"regime": ["bear"]}], ids=repr)
    def test_unhashable_is_not_veto_and_does_not_raise(self, regime):
        assert DSS._is_veto_regime(regime) is False

    def test_a_bear_dict_reaches_the_bear_branch_end_to_end(self, monkeypatch):
        """誤傳整個 dict 的空頭 regime 也走「分不出來 → 回 []」，⛔ 不 raise。"""
        monkeypatch.setattr(FSS, "get_fundamental_survivors",
                            lambda **_k: (_SURV_NO_EPS, {}))
        monkeypatch.setattr(FSS, "get_ranked_picks", _all_unscored)
        assert DSS.get_switch_in_candidates(strict=True,
                                            regime={"regime": "bear"}) == []
        with pytest.raises(RuntimeError, match="未取得綜合分"):
            DSS.get_switch_in_candidates(strict=True, regime={"regime": "bull"})

    def test_c_mutation_dropping_the_dict_branch_is_caught(self):
        m = _mutant(DSS, '        regime = regime.get("regime")\n',
                    "        pass\n")
        assert m._is_veto_regime({"regime": "bear"}) is False
        assert m._is_veto_regime({"regime": "bear"}) is not _fss_veto({"regime": "bear"})
