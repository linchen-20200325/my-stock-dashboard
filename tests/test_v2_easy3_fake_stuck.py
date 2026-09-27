"""三處「假卡住／假說明」文案（B9 ⑤、B9 ⑧、Q4-r1）—— 只刪不加（K1）。

① B9 ⑤ `page_hold.build_vix_card` 例外分支的 where：刪掉「是那一支 L3 自己載不進來」——
   那句只對 import 失敗成立，對 L3 的 runtime bug 是假的。
② B9 ⑧ `page_find._load_trend` 失敗訊息：`repr(e)` → `str(e).strip() or UNKNOWN_ERROR_TEXT`
   —— 紅卡事實列不再出現「RuntimeError()」這種程式字樣；回傳值恆不為空（失敗旗標靠它）。
③ Q4-r1 配息「持有列缺張數」：`REASON_NO_LOTS_ROWS` 與「涵蓋範圍」列刪掉「觀察清單…」的
   括號說明 —— 那句把「持有列缺張數」誤說成觀察清單，而觀察清單本來就不算持有列。
"""
from __future__ import annotations

import pytest

import src.services.fundamental_screener_service as S
import src.services.portfolio_deep_service as PDS
from shared.ui_state import UI_EMPTY, UI_FAILED
from src.ui.views import page_find as PF
from src.ui.views import page_hold as PH

# ══════════════════════════════════════════════════════════════════
# ① B9 ⑤ VIX 例外分支 where
# ══════════════════════════════════════════════════════════════════
_VIX_EXC_WHERE = (f"{PH.NO_EXIT_MARKER} —— 這不是取數失敗（L3 取不到時回的是"
                  "「沒有值」而不是例外）；請把上面那行訊息回報給維護者")


@pytest.mark.parametrize("err", [
    "ModuleNotFoundError(\"No module named 'x'\")",   # import 失敗
    "KeyError('close')",                                # L3 runtime bug
])
def test_vix_exception_where_holds_for_import_and_runtime_errors(err):
    card = PH.build_vix_card(PH.VixReadout(requested=True, error=err))[0]
    assert card.state == UI_FAILED and card.note.now == PH.VIX_FAILED_NOW
    assert card.note.where == _VIX_EXC_WHERE
    assert "載不進來" not in card.note.where, "對 runtime bug 不成立的那句又回來了"
    # v2 短句仍是原文摘錄（查不到會 KeyError）
    short, _full = PH.v2_short_rows(card)
    assert short


# ══════════════════════════════════════════════════════════════════
# ② B9 ⑧ 跨季轉強失敗訊息
# ══════════════════════════════════════════════════════════════════
def _trend_raises(exc):
    def _f(**_k):
        raise exc
    return _f


@pytest.mark.parametrize("exc, want", [
    (RuntimeError(), PF.UNKNOWN_ERROR_TEXT),
    (RuntimeError("   "), PF.UNKNOWN_ERROR_TEXT),
    (ValueError("季快照欄位漂移：缺 eps"), "季快照欄位漂移：缺 eps"),
])
def test_trend_failure_message_is_text_not_repr_and_never_empty(monkeypatch, exc, want):
    monkeypatch.setattr(S, "build_trend_map", _trend_raises(exc))
    got, err = PF._load_trend(("trend",))
    assert got is None
    assert err == want and err, "失敗訊息空字串 ＝ 本頁語意的「沒有錯誤」→ 失敗旗標會掉"
    assert "RuntimeError(" not in err and "ValueError(" not in err


def test_trend_failure_still_flags_the_factor_and_scrubs_secrets(monkeypatch):
    """事實列走 `build_screen_result_card` 的 `scrub_secrets` —— `str(e)` 一樣被洗。"""
    monkeypatch.setattr(S, "build_trend_map",
                        _trend_raises(RuntimeError("GET https://x/api?token=SECRET123 失敗")))
    got, err = PF._load_trend(("trend",))
    assert err
    req = PF.ScreenRequest(submitted=True, factors=("trend",))
    res = PF.ScreenResult(requested=True, rows=0,
                          aux_errors=(("跨季轉強", f"失敗，該因子不計入綜合分：{err}"),),
                          factor_input_failed=("trend",))
    card, facts = PF.build_screen_result_card(res, req)
    assert card.state == UI_FAILED
    assert "SECRET123" not in dict(facts)["跨季轉強"]


def test_trend_not_ticked_is_not_a_failure():
    assert PF._load_trend(("pe_low",)) == (None, "")


# ══════════════════════════════════════════════════════════════════
# ③ Q4-r1 配息「缺張數」
# ══════════════════════════════════════════════════════════════════
def _cash(**kw):
    base = dict(computed=True, gross_twd=30000.0, net_after_nhi_twd=30000.0, payouts_n=8,
                tw_n=1, lots_n=1, held_n=2, shares_total=1000.0, coverage_pct=50.0,
                excluded_tickers=("2330.TW",))
    return PDS.DividendCashResult(**{**base, **kw})


def _deep(cash):
    return PH.DeepReadout(requested=True, submitted=True, bound=True, holdings_n=2,
                          has_station_rows=True, cash=cash)


def test_reason_no_lots_rows_is_the_trimmed_sentence():
    assert PDS.REASON_NO_LOTS_ROWS == "沒有任何一列有張數"


def test_coverage_row_no_longer_blames_the_watchlist():
    built = PH.build_dividend_cash_card(_deep(_cash()))
    assert built[0].state != UI_FAILED
    cover = dict(built[1])["涵蓋範圍"]
    assert cover == "2 檔持有列裡納入了 1 檔 —— 沒有張數的列不算"
    assert "觀察清單" not in cover


def test_no_lots_card_carries_the_trimmed_reason():
    card = PH.build_dividend_cash_card(_deep(_cash(
        computed=False, gross_twd=0.0, net_after_nhi_twd=0.0, payouts_n=0, lots_n=0,
        coverage_pct=0.0, excluded_tickers=(), reason=PDS.REASON_NO_LOTS_ROWS)))[0]
    assert card.state == UI_EMPTY
    assert PDS.REASON_NO_LOTS_ROWS in card.note.why
    assert "觀察清單" not in card.note.why and "三欄" not in card.note.why


def test_l3_really_returns_the_reason_for_rows_without_lots():
    """持有列缺張數（真的走 L3）→ 回這句原因，且沒提觀察清單。"""
    row = {"代號": "2330", "張數": None, "均價": None, "現價": 900.0, "held": True}
    res = PDS.get_dividend_cash_flow([row])
    assert res.computed is False
    assert res.reason == PDS.REASON_NO_LOTS_ROWS


class _BadStr(RuntimeError):
    def __str__(self):
        raise ValueError("__str__ 自己壞了")


def test_trend_exception_whose_str_raises_does_not_blow_up_the_page(monkeypatch):
    """`__str__` 自己拋錯 → 退回 `UNKNOWN_ERROR_TEXT`，失敗旗標照舊、卡片紅、整頁不炸。"""
    monkeypatch.setattr(S, "build_trend_map", _trend_raises(_BadStr()))
    assert PF._load_trend(("trend",)) == (None, PF.UNKNOWN_ERROR_TEXT)
    req = PF.ScreenRequest(submitted=True, factors=("trend",))
    res = PF.load_screen_result(req)          # ⛔ 不得拋
    assert "trend" in res.factor_input_failed
    card, facts = PF.build_screen_result_card(res, req)
    assert card.state == UI_FAILED
    assert dict(facts)["跨季轉強"].endswith(PF.UNKNOWN_ERROR_TEXT)
