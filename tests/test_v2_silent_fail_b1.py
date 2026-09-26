"""批次 1：「取數失敗」與「結果真的是 0」必須分得開（客戶 2026-09-26 裁示）。

三張卡，每張三條：
  (a) 上游失敗 → ⛔ 不得再畫成 `UI_EMPTY`，⛔ 不得再說「這是一個有效的結果」；
  (b) 真的 0 → 仍是**原封不動**的 `UI_EMPTY` 卡（now / why / where 一字未改）；
  (c) 突變：把本批新加的那一條判定拿掉（改原始碼、重新載入模組）→ (a) 必須轉紅。

⚠️ `hold.switch`（`SWITCH_EMPTY_NOW`）**本批未修**：本頁拿不到任何能分辨兩者的訊號
（L3 `get_switch_in_candidates` 對例外與空表都回 `[]`，且把 `get_ranked_picks` 的 note 丟掉），
在頁面檔內修不了 —— 已依裁示停手上報，故本檔**沒有**它的測試。
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys
import types

import pytest

from shared.station_specs import MISS_FETCH_FAILED, MISS_TEXT
from shared.ui_state import UI_EMPTY, UI_FAILED, UI_LIVE
from src.ui.views import page_find as PF
from src.ui.views import page_hold as PH

_VALID = "有效的結果"


class _Frame:
    def __init__(self, n: int) -> None:
        self._n = n

    def __len__(self) -> int:
        return self._n


def _mutant(mod: types.ModuleType, old: str, new: str) -> types.ModuleType:
    """把 `mod` 的原始碼裡**恰好一處** `old` 換成 `new`，載成一個獨立的新模組。"""
    src = pathlib.Path(mod.__file__).read_text(encoding="utf-8")
    assert src.count(old) == 1, f"突變點不唯一或已不存在：{old!r}"
    name = f"_mutant_{mod.__name__.rsplit('.', 1)[-1]}"
    spec = importlib.util.spec_from_loader(name, loader=None)
    m = importlib.util.module_from_spec(spec)
    m.__file__ = mod.__file__
    sys.modules[name] = m
    try:
        exec(compile(src.replace(old, new), mod.__file__, "exec"), m.__dict__)
    finally:
        sys.modules.pop(name, None)
    return m


# ══════════════════════════════════════════════════════════════════
# find.screen_result（SCREEN_EMPTY_NOW）
# ══════════════════════════════════════════════════════════════════
_SURV_ERR = "RuntimeError('fundamentals snapshot missing')"


def _screen(P, **kw):
    req = P.ScreenRequest(submitted=True, factors=("eps_high",))
    return P.build_screen_result_card(P.ScreenResult(requested=True, **kw), req)


def _find_surv_failed(P):
    return _screen(P, df=_Frame(0), rows=0, survivors_n=None,
                   survivors_error=_SURV_ERR,
                   note="基本面存活池為空（季快照未就緒）。")


class TestFindScreenResult:
    def test_a_survivors_failure_is_not_a_valid_zero(self):
        card, facts = _find_surv_failed(PF)
        assert card.state == UI_FAILED
        assert card.state != UI_EMPTY
        assert card.note.now == PF.SCREEN_ABORTED_NOW
        assert card.note.now != PF.SCREEN_EMPTY_NOW
        assert _VALID not in card.note.why
        # 出處講對（存活池那一支），原始例外看得見。
        assert "fundamentals snapshot missing" in card.note.why
        assert PF.SRC_SURVIVORS.split("（")[0] in card.note.why
        # 卡面照樣畫得出來（短句表查得到）。
        html = PF.v2_card_html(card, facts)
        assert PF.SCREEN_EMPTY_NOW.strip("*") not in html

    def test_a_face_names_the_survivors_source_not_the_ranking(self):
        card, _ = _find_surv_failed(PF)
        face = dict(PF.v2_short_rows(card)[0])
        why = face[PF.V2_WHY_FACT_KEY]
        assert why.startswith("L3 基本面存活池") and why.endswith("拋出例外"), why
        assert "選股編排" not in why

    def test_b_ranking_raise_face_is_the_existing_phrase(self):
        card, _ = _screen(PF, error='RuntimeError("finmind quota")')
        face = dict(PF.v2_short_rows(card)[0])
        assert face[PF.V2_WHY_FACT_KEY] == "L3 選股編排拋出例外（原文在詳細）"

    def test_a_survivors_wording_inside_a_ranking_error_does_not_pick_it(self):
        """排名本身拋例外、而例外訊息裡碰巧含存活池那段字 → 仍是既有那一句。"""
        _msg = "RuntimeError('L3 基本面存活池 upstream 拋出例外 again')"
        card, _ = _screen(PF, error=_msg)
        assert "L3 基本面存活池" in PF.v2_plain(card.note.why)   # 前提：字真的在原文裡
        face = dict(PF.v2_short_rows(card)[0])
        assert face[PF.V2_WHY_FACT_KEY] == "L3 選股編排拋出例外（原文在詳細）"

    def test_a_through_the_loader(self, monkeypatch):
        """真的走 `load_screen_result`：本頁存活池失敗、L3 回空表 → 紅，不是「0 檔」。"""
        import src.services.fundamental_screener_service as S

        def _boom():
            raise RuntimeError("fundamentals snapshot missing")

        monkeypatch.setattr(S, "get_fundamental_survivors", lambda **_k: _boom())
        monkeypatch.setattr(S, "get_ranked_picks", lambda *a, **k: (
            _Frame(0), "基本面存活池為空（季快照未就緒）。"))
        monkeypatch.setattr(PF, "_load_pe_name_maps", lambda: ({"1": 1.0}, {"1": "x"}, ""))
        monkeypatch.setattr(PF, "_load_regime", lambda: ("bull", ""))
        monkeypatch.setattr(PF, "_load_trend", lambda f: (None, ""))
        monkeypatch.setattr(PF, "_summarize_hits", lambda *a, **k: ((), ""))
        req = PF.ScreenRequest(submitted=True, factors=("eps_high",))
        res = PF.load_screen_result(req)
        assert res.rows == 0 and res.survivors_error
        card, _ = PF.build_screen_result_card(res, req)
        assert card.state == UI_FAILED
        assert _VALID not in card.note.why

    def test_b_genuine_zero_is_unchanged(self):
        card, _ = _screen(PF, df=_Frame(0), rows=0, survivors_n=274)
        assert card.state == UI_EMPTY
        assert card.note.now == PF.SCREEN_EMPTY_NOW
        assert _VALID in card.note.why

    def test_b_other_aux_failures_still_leave_a_valid_zero(self):
        """存活池拿到了、只是某個因子掃描失敗 → 那是「該因子不計入」，0 檔仍是有效結果。"""
        card, _ = _screen(PF, df=_Frame(0), rows=0, survivors_n=274,
                          aux_errors=(("缺貨掃描", "失敗，該因子不計入綜合分：E"),))
        assert card.state == UI_EMPTY and card.note.now == PF.SCREEN_EMPTY_NOW

    def test_b_survivors_failed_but_l3_retry_picked_rows_stays_live(self):
        card, _ = _screen(PF, df=_Frame(3), rows=3, survivors_n=None,
                          survivors_error=_SURV_ERR)
        assert card.state == UI_LIVE

    def test_c_mutation_removing_the_check_turns_a_red(self):
        m = _mutant(PF, "else MISS_FETCH_FAILED if _surv_failed", 'else "" if _surv_failed')
        card, _ = _find_surv_failed(m)
        assert card.state == UI_EMPTY and _VALID in card.note.why, (
            "拿掉新判定後 (a) 必須失敗 —— 否則 (a) 沒有守到東西")


# ══════════════════════════════════════════════════════════════════
# hold.take_profit（TP_EMPTY_NOW）
# ══════════════════════════════════════════════════════════════════
def _station(P, rows):
    return P.StationReadout(requested=True, submitted=True, bound=True,
                            holdings_n=len(rows), rows=tuple(rows))


_SAT_OK = {"代號": "2330", "種類": "個股", "held": True, "損益%": 3.0, "_detail": {}}
_SAT_ERR = {"代號": "2454", "種類": "個股", "held": True,
            "_detail": {"error": "HTTPError 502"}}


def _tp_failed(P):
    return P.build_take_profit_card(_station(P, (_SAT_OK, _SAT_ERR)))


class TestHoldTakeProfit:
    def test_a_a_satellite_fetch_error_is_not_a_valid_empty(self):
        built = _tp_failed(PH)
        card = built[0]
        assert card.state == UI_FAILED
        assert card.note.now == PH.TP_FAILED_NOW
        assert card.note.now != PH.TP_EMPTY_NOW
        assert _VALID not in card.note.why
        assert "2454" in card.note.why
        assert MISS_TEXT[MISS_FETCH_FAILED].removeprefix("這一檔") in card.note.why
        assert card.note.where == PH.STATION_ERROR_WHERE
        html = PH.v2_card_html(*built)       # 短句表的第二個候選對得上原文
        assert PH.TP_EMPTY_NOW.strip("*") not in html

    def test_a_several_codes_are_not_called_one(self):
        """多檔失敗時⛔ 不得寫成單數「這一檔」（只刪 L0 原文開頭，不改寫）。"""
        _other = dict(_SAT_ERR, 代號="3008")
        card = PH.build_take_profit_card(_station(PH, (_SAT_OK, _SAT_ERR, _other)))[0]
        assert card.note.why.startswith("2454、3008：整批抓取失敗")
        assert "這一檔" not in card.note.why
        face = PH.v2_short_rows(card)[0]
        assert "這一檔" not in face[1][1] and face[1][1].startswith("整批抓取失敗")

    def test_b_genuine_none_hit_is_unchanged(self):
        card = PH.build_take_profit_card(_station(PH, (_SAT_OK,)))[0]
        assert card.state == UI_EMPTY
        assert card.note.now == PH.TP_EMPTY_NOW
        assert _VALID in card.note.why

    @pytest.mark.parametrize("row", [
        {"代號": "0056", "種類": "ETF", "held": True, "_detail": {"error": "E"}},
        {"代號": "2454", "種類": "個股", "held": False, "_detail": {"error": "E"}},
    ], ids=["held_etf_error", "watchlist_stock_error"])
    def test_b_errors_outside_the_take_profit_scope_keep_the_valid_empty(self, row):
        """L3 本來就不對 ETF／觀察清單判停利 → 它們抓不到不影響「0 檔達標」。"""
        card = PH.build_take_profit_card(_station(PH, (_SAT_OK, row)))[0]
        assert card.state == UI_EMPTY and card.note.now == PH.TP_EMPTY_NOW

    def test_b_a_hit_alongside_an_error_row_stays_live(self):
        card = PH.build_take_profit_card(PH.StationReadout(
            requested=True, submitted=True, bound=True, holdings_n=2,
            rows=(_SAT_OK, _SAT_ERR),
            take_profit=({"代號": "2330", "損益%": 22.0},)))[0]
        assert card.state == UI_LIVE

    def test_c_mutation_removing_the_check_turns_a_red(self):
        m = _mutant(PH, 'reason=MISS_FETCH_FAILED if _fetch_failed else "")', 'reason="")')
        card = _tp_failed(m)[0]
        assert card.state == UI_EMPTY and _VALID in card.note.why, (
            "拿掉新判定後 (a) 必須失敗 —— 否則 (a) 沒有守到東西")
