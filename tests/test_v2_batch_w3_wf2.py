"""批 W3：W-f2 —— 查一檔估值灰卡「無股價**且**無配息源」時 why／where 指向一致。

修前：why 走 `VALUATION_NO_SOURCE_WHY`（講配息備援鏈），where 走 `VALUATION_NO_PRICE_WHERE`
（講日線）—— 同一張卡兩欄指向不一。修後：沒股價時 why 改讀 L2 自己的原因句（「無股價，…」），
與 where 同指日線。⛔ 不新增文案（K1）：兩句都是既有字串。
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys
import types

from shared.ui_state import UI_EMPTY
from src.compute.strategy.v5_modules import calc_dividend_yield_357
from src.ui.views import page_inspect as P

# 從 L2 真的取一次「無股價」msg（不在測試裡手抄第二份字串）。
_L2_NO_PRICE_MSG = calc_dividend_yield_357(0.0, avg_div_twd=None)["msg"]
assert _L2_NO_PRICE_MSG.startswith("無股價")


def _mutant(mod: types.ModuleType, old: str, new: str) -> types.ModuleType:
    src = pathlib.Path(mod.__file__).read_text(encoding="utf-8")
    assert src.count(old) == 1, f"突變點不唯一或已不存在：{old!r}"
    src = src.replace(old, new)
    name = "_mutant_w3_page_inspect"
    spec = importlib.util.spec_from_loader(name, loader=None)
    m = importlib.util.module_from_spec(spec)
    m.__file__ = mod.__file__
    sys.modules[name] = m
    try:
        exec(compile(src, mod.__file__, "exec"), m.__dict__)
    finally:
        sys.modules.pop(name, None)
    return m


def _card(P_, **kw):
    base = dict(requested=True, zone_code="na", price=None, msg=_L2_NO_PRICE_MSG)
    base.update(kw)
    return P_.build_valuation_card(P_.ValuationReadout(**base))


def test_no_price_and_no_source_why_and_where_both_point_to_daily_line():
    card = _card(P)[0]
    assert card.state == UI_EMPTY
    assert card.note.why == _L2_NO_PRICE_MSG + P.VALUATION_WHY_TAIL
    assert not card.note.why.startswith(P.VALUATION_NO_SOURCE_WHY.split("**", 1)[0])
    assert card.note.where == P.VALUATION_NO_PRICE_WHERE


def test_zero_price_counts_as_no_price():
    card = _card(P, price=0.0)[0]
    assert card.note.why.startswith("無股價")
    assert card.note.where == P.VALUATION_NO_PRICE_WHERE


def test_v2_face_renders():
    built = _card(P)
    rows = dict(P.v2_short_rows(built[0])[0])
    assert rows[P.V2_GUIDE_FACT_KEY] == P.VALUATION_NO_PRICE_WHERE
    P.v2_card_html(*built)    # 摘錄對不上會 KeyError


def test_unchanged_has_price_no_source_keeps_dividend_why():
    card = P.build_valuation_card(P.ValuationReadout(
        requested=True, zone_code="na", price=600.0,
        msg="無配息記錄，357 殖利率法則不適用（不以 0% 代替，避免誤判為超貴）"))[0]
    assert card.note.why.startswith(P.VALUATION_NO_SOURCE_WHY.split("**", 1)[0])
    assert card.note.where == P.VALUATION_WHERE


def test_unchanged_no_price_without_l2_msg_falls_back():
    """L2 沒給 msg（空字串）→ 不拿空字串當原因，退回原判斷。"""
    card = _card(P, msg="")[0]
    assert card.note.why.startswith(P.VALUATION_NO_SOURCE_WHY.split("**", 1)[0])


def test_unchanged_no_price_with_source_uses_l2_msg():
    card = _card(P, avg_div_twd=6.85, paying_years=5, source="FinMind", years_n=5)[0]
    assert card.note.why == _L2_NO_PRICE_MSG + P.VALUATION_WHY_TAIL


def test_no_new_wording():
    """K1：why 全由既有字串組成（L2 msg ＋ 既有 tail）。"""
    card = _card(P)[0]
    assert card.note.why.removesuffix(P.VALUATION_WHY_TAIL) == _L2_NO_PRICE_MSG


def test_mutation_reverting_fix_is_caught():
    m = _mutant(P, "        if _no_price and _l2_why:\n", "        if False:\n")
    card = _card(m)[0]
    assert card.note.why != _L2_NO_PRICE_MSG + m.VALUATION_WHY_TAIL, "突變體應回到舊行為"
    assert card.note.why.startswith(m.VALUATION_NO_SOURCE_WHY.split("**", 1)[0])
