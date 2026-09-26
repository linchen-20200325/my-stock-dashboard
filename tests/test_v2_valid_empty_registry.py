"""#11「▨ 無資料」登記處的守衛（客戶 2026-09-26 新增徽章 #11）。

登記處：`src/ui/views/page_today.py::V2_VALID_EMPTY_SPEC` → `v2_valid_empty_pairs()`。
只驗**登記處本身**的完整性；「畫出 #11 的卡＝登記表」的窮舉在各頁測試
（`tests/test_p04_hold_v2_cards.py`、`tests/test_p02_find_v2_cards.py`）。
"""
from __future__ import annotations

import importlib

import pytest

from shared import ui_state
from src.ui.tabs.tab_today import Card, Note
from src.ui.views import page_today as PT
from src.ui_v2 import blocks, components
from src.ui_v2 import page_today as V2


def test_every_registered_now_is_a_real_constant_not_a_copied_string():
    """每一列都解析得到**真的常數**，而且 `v2_valid_empty_pairs()` 用的是它的**值**。"""
    assert PT.V2_VALID_EMPTY_SPEC, "登記表不得為空（至少有 hold.portfolio_count）"
    _pairs = PT.v2_valid_empty_pairs()
    for _key, _mod, _const in PT.V2_VALID_EMPTY_SPEC:
        _val = getattr(importlib.import_module(_mod), _const)
        assert isinstance(_val, str) and _val.strip()
        assert _const.endswith("_NOW"), "登記的必須是 Note.now 常數"
        assert (_key, _val) in _pairs
    assert len(_pairs) == len(PT.V2_VALID_EMPTY_SPEC), "登記表有重複列"


def test_registered_keys_are_find_or_hold_blocks_never_today():
    """客戶裁示：今天頁的卡**一律排除**。登記的 key 必須是找標的／我的持股頁的已登記 block。"""
    for _key, _mod, _c in PT.V2_VALID_EMPTY_SPEC:
        assert _mod in ("src.ui.views.page_find", "src.ui.views.page_hold")
        assert blocks.page_of_block(_key) is not blocks.page_of_block("today.verdict")
        assert _key.startswith(("find.", "hold."))
        assert V2.VALID_EMPTY_BADGE not in blocks.badges_not_on_page(_key)


def test_exact_registry_contents():
    """登記表**逐列釘死**（手寫第二把尺）：新增或刪除一列都必須是一個看得見的決定。"""
    from src.ui.views import page_hold as PH
    assert PT.v2_valid_empty_pairs() == frozenset({
        ("hold.portfolio_count", PH.COUNT_EMPTY_NOW),
    })


def test_a_broken_registry_row_fails_loud(monkeypatch):
    monkeypatch.setattr(PT, "V2_VALID_EMPTY_SPEC",
                        (("hold.portfolio_count", "src.ui.views.page_hold", "NO_SUCH_NOW"),))
    monkeypatch.setattr(PT, "_V2_VALID_EMPTY_CACHE", [])
    with pytest.raises(RuntimeError, match="NO_SUCH_NOW"):
        PT.v2_valid_empty_pairs()


@pytest.mark.parametrize("state", [s for s in ui_state.UI_STATES if s != ui_state.UI_EMPTY])
def test_registered_pair_under_any_other_state_does_not_get_11(state):
    """即使 `(key, now)` 對上登記，只要 L0 態不是 `UI_EMPTY` —— ⛔ 不畫 #11。"""
    from src.ui.views import page_hold as PH
    try:
        card = Card(key="hold.portfolio_count", label="x", state=state,
                    note=Note(now=PH.COUNT_EMPTY_NOW, why="w", where="w"))
    except ValueError:
        pytest.skip("L0 不收這個組合")
    assert PT.v2_card_badge_n(card) != V2.VALID_EMPTY_BADGE


def test_registered_pair_under_empty_gets_11_and_its_face_is_the_l0_chip():
    from src.ui.views import page_hold as PH
    card = Card(key="hold.portfolio_count", label="x", state=ui_state.UI_EMPTY,
                note=Note(now=PH.COUNT_EMPTY_NOW, why="w", where="w"))
    n = PT.v2_card_badge_n(card)
    assert n == V2.VALID_EMPTY_BADGE == 11
    name, glyph, _hex = ui_state.UI_STATE_META[ui_state.UI_EMPTY]
    assert (components.badge(n)["icon"], components.badge(n)["text"]) == (glyph, name)


def test_unregistered_empty_card_still_gets_7():
    card = Card(key="hold.portfolio_count", label="x", state=ui_state.UI_EMPTY,
                note=Note(now="**別的句子**", why="w", where="w"))
    assert PT.v2_card_badge_n(card) == 7
