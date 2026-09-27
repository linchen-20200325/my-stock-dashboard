"""客戶 2026-09-27 逐字提供的四句（B9 ⑪／Q2-r3／SA-r3／E3-r1）。

⛔ 下列字串是**客戶原文逐字貼上**，⛔ 不得改寫、⛔ 不得從常數反推（那樣常數被改時測試跟著變、守不到）。
每一句守兩件事：(1) 常數逐字等於客戶原文；(2) 對應的那一態卡片真的把它印出來（長句＋卡面短句）。
"""
from __future__ import annotations

from shared.ui_state import UI_EMPTY, UI_FAILED
from src.ui.views import page_find as PF
from src.ui.views import page_hold as PH
from src.ui.views import page_inspect as PI

#: ── 客戶原文（逐字）──────────────────────────────────────────────
B9_11 = "先放寬條件（少勾幾個因子）再按「🎯 開始選股」；若仍失敗，稍後再試一次。"
Q2_R3 = "這檔查不到報價 —— 可能是已下市，也可能是上游這輪抓取失敗。本站分不出這兩種，不替你猜。"
SA_R3 = "先確認代號是否正確；確認後重新載入，仍抓不到就是上游沒給這檔的日線。"
E3_R1 = "到「💼 我的持股 › 組合設定」，在你的持股表新增至少一列持股（要有代號、張數、均價）。"


def test_constants_are_the_client_strings_verbatim():
    assert PF.SCREEN_FACTOR_RELAX_WHERE == B9_11
    assert PH.NO_PRICE_WHY == Q2_R3
    assert PI.VALUATION_NO_PRICE_WHERE == SA_R3
    assert PH.CASH_WATCHLIST_ONLY_WHERE == E3_R1


# ── B9 ⑪：找股頁 估值／RS／跨季轉強 因子失敗紅卡 ─────────────────────
class _Frame:
    def __init__(self, n: int) -> None:
        self._n = n

    def __len__(self) -> int:
        return self._n


def _screen(factors):
    req = PF.ScreenRequest(submitted=True, factors=tuple(factors))
    return PF.build_screen_result_card(
        PF.ScreenResult(requested=True, df=_Frame(0), rows=0, survivors_n=3,
                        factor_input_failed=tuple(factors)), req)


def test_b9_11_three_factor_red_card_where_and_face():
    for factors in (("pe_low",), ("rs_leader",), ("trend",), ("pe_low", "rs_leader", "trend")):
        card, facts = _screen(factors)
        assert card.state == UI_FAILED and card.note.now == PF.SCREEN_ABORTED_NOW, factors
        assert card.note.where == B9_11, factors
        assert dict(PF.v2_short_rows(card)[0])[PF.V2_GUIDE_FACT_KEY] == B9_11
        assert B9_11 in PF.v2_card_html(card, facts)


def test_b9_11_does_not_leak_into_shortage_or_mixed():
    assert _screen(("shortage",))[0].note.where == PF.SCREEN_ABORTED_WHERE
    assert _screen(("shortage", "trend"))[0].note.where == PF.SCREEN_NO_PARTIAL_WHERE


# ── Q2-r3：持股頁 持有列查不到現價 → why ────────────────────────────
_NO_PX = {"代號": "2454", "種類": "個股", "held": True, "現價": None, "均價": 100.0,
          "損益%": None, "_detail": {}}
_PX = {"代號": "2330", "種類": "個股", "held": True, "現價": 103.0, "均價": 100.0,
       "損益%": 3.0, "_detail": {}}


def test_q2_r3_no_price_why_on_hold_cards():
    st_ = PH.StationReadout(requested=True, submitted=True, bound=True, holdings_n=2,
                            rows=(_PX, _NO_PX))
    for build in (PH.build_take_profit_card, PH.build_allocation_split_card,
                  PH.build_core_satellite_card):
        built = build(st_)
        card = built[0]
        assert card.state == UI_FAILED, build.__name__
        assert card.note.why == f"2454：{Q2_R3}", build.__name__
        assert dict(PH.v2_short_rows(card)[0])[PH.V2_WHY_FACT_KEY] == Q2_R3
        PH.v2_card_html(*built)       # 摘錄對不上會 KeyError


# ── SA-r3：查一檔頁 估值灰卡 無股價那一支 → where ──────────────────────
def _valuation(**kw):
    return PI.build_valuation_card(PI.ValuationReadout(
        requested=True, zone_code="na", signal="⚪ 未評估",
        msg="無股價，357 殖利率法則不適用（不以 0% 代替，避免誤判為超貴）",
        avg_div_twd=3.0, paying_years=5, source="FinMind", years_n=5, **kw))


def test_sa_r3_no_price_grey_card_where_and_face():
    built = _valuation(price=None)
    card = built[0]
    assert card.state == UI_EMPTY and card.note.now == PI.VALUATION_EMPTY_NOW
    assert card.note.where == SA_R3
    assert dict(PI.v2_short_rows(card)[0])[PI.V2_GUIDE_FACT_KEY] == SA_R3
    PI.v2_card_html(*built)


def test_sa_r3_zero_or_negative_price_is_also_no_price():
    """同 L2 `not price or price <= 0` → 「無股價」：0 與負價也要走客戶句（⛔ 不只看 `is None`）。"""
    for px in (0, 0.0, -1.0):
        built = _valuation(price=px)
        assert built[0].state == UI_EMPTY and built[0].note.where == SA_R3, px
        assert dict(PI.v2_short_rows(built[0])[0])[PI.V2_GUIDE_FACT_KEY] == SA_R3
        PI.v2_card_html(*built)


def test_sa_r3_mutation_is_none_only_is_caught():
    import importlib.util, sys
    src = open(PI.__file__, encoding="utf-8").read()
    old = "_no_price = not val.price or val.price <= 0"
    assert src.count(old) == 1, "突變點不唯一或已不存在"
    spec = importlib.util.spec_from_loader("_pi_mutant", loader=None)
    m = importlib.util.module_from_spec(spec)
    m.__file__ = PI.__file__
    sys.modules["_pi_mutant"] = m
    try:
        exec(compile(src.replace(old, "_no_price = val.price is None"), PI.__file__, "exec"),
             m.__dict__)
        built = m.build_valuation_card(m.ValuationReadout(
            requested=True, zone_code="na", msg="無股價，357 殖利率法則不適用",
            avg_div_twd=3.0, paying_years=5, source="FinMind", years_n=5, price=0.0))
        assert built[0].note.where != SA_R3, "突變後 price=0 不再走客戶句 —— 上一條要能抓到"
    finally:
        sys.modules.pop("_pi_mutant", None)


def test_sa_r3_priced_branch_keeps_the_existing_where():
    built = PI.build_valuation_card(PI.ValuationReadout(
        requested=True, zone_code="na", msg="無配息記錄，357 殖利率法則不適用",
        source="FinMind", years_n=5, price=100.0))
    assert built[0].state == UI_EMPTY and built[0].note.where == PI.VALUATION_WHERE != SA_R3


# ── E3-r1：持股頁 配息卡 只有觀察清單 ─────────────────────────────────
def _cash_card(held_n: int):
    from src.services.portfolio_deep_service import DividendCashResult
    res = DividendCashResult(reason="沒有任何一列有張數", held_n=held_n)
    return PH.build_dividend_cash_card(PH.DeepReadout(
        requested=True, submitted=True, bound=True, holdings_n=2, has_station_rows=True,
        cash=res))


def test_e3_r1_watchlist_only_shows_no_holdings_now_and_client_where():
    built = _cash_card(held_n=0)
    card = built[0]
    assert card.state == UI_EMPTY
    assert card.note.now == PH.CASH_NO_HOLDINGS_NOW
    assert card.note.now != PH.NO_ROWS_NOW and "戰情表一列都沒有回來" not in card.note.why
    assert card.note.where == E3_R1
    assert dict(PH.v2_short_rows(card)[0])[PH.V2_GUIDE_FACT_KEY] == E3_R1
    assert E3_R1 in PH.v2_card_html(*built)


def test_e3_r1_held_rows_without_lots_keep_the_existing_empty_note():
    card = _cash_card(held_n=2)[0]
    assert card.note.now == PH.CASH_EMPTY_NOW and card.note.where != E3_R1
