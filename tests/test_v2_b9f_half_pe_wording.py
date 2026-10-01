"""批 B9f（B9 ⑨-f1，2026-10-01）：估值只少上市或上櫃半邊時，facts 那一列純刪
「，該因子不計入綜合分」子句（K1：只刪不加）。

理由（L3 實跑，非推論）：半邊失敗時 `pe_map` 仍有另一半的本益比 →
`composite_rank_candidates` 照算「估值分」並計入綜合分；舊子句不成立，
且與同卡「N 檔有本益比」互相矛盾。

每一項：(a) 修後行為、(b) 只刪字、(c) 突變（還原舊子句）→ 必須紅。
"""
from __future__ import annotations

import pandas as pd

from src.ui.views import page_find as PF
from tests.test_v2_silent_fail_b12_b6 import _mutant
from tests.test_v2_silent_fail_b5_find import _break, _is_deletion_of, _run

from tests import test_v2_silent_fail_b5_find as _B5  # noqa: E402
world = _B5.world

_PE = "估值（本益比）"
_DELETED = "，該因子不計入綜合分"
_OLD_ROW = "上櫃 TPEX失敗，該因子不計入綜合分"
_NEW_ROW = "上櫃 TPEX失敗"
_OLD_LINE = 'f"{\'、\'.join(_pe_failed_markets)}失敗，該因子不計入綜合分"))'
_NEW_LINE = 'f"{\'、\'.join(_pe_failed_markets)}失敗"))'


def _pe_rows(facts):
    return [v for k, v in facts if k == _PE]


class TestB9fHalfPeWording:
    def test_premise_l3_still_scores_pe_on_remaining_half(self, world):
        """前提：半邊失敗時 L3 仍用剩下半邊算估值分 → 舊子句不成立。"""
        _break(world, "pe_tpex")
        res, _card, _facts = _run(PF, ("pe_low", "eps_high"))
        assert res.pe_n == 2
        scored = {str(c): v for c, v in zip(res.df["代碼"], res.df["估值分"])}
        assert pd.notna(scored["2330"]) and pd.notna(scored["2317"]), "剩下上市半邊照算估值分"
        assert pd.isna(scored.get("6488")), "缺的上櫃那檔沒有估值分（缺值不填 0）"
        assert res.df["綜合分"].notna().any()

    def test_half_missing_row_drops_clause(self, world):
        _break(world, "pe_tpex")
        _res, _card, facts = _run(PF, ("pe_low", "eps_high"))
        rows = _pe_rows(facts)
        assert _NEW_ROW in rows
        assert not any(_DELETED in v for v in rows), rows
        assert any("檔有本益比" in v for v in rows), "N 檔有本益比 那一列保留"

    def test_twse_half_missing_row_drops_clause(self, world):
        _break(world, "pe_twse")
        _res, _card, facts = _run(PF, ("pe_low",))
        rows = _pe_rows(facts)
        assert "上市 TWSE失敗" in rows
        assert not any(_DELETED in v for v in rows), rows

    def test_pure_deletion_k1(self):
        assert _is_deletion_of(_NEW_ROW, _OLD_ROW)
        assert _OLD_ROW.replace(_DELETED, "") == _NEW_ROW

    def test_other_branches_keep_clause(self):
        """拋例外與三支掃描那幾句（該因子確實整個不計）一字未動。"""
        src = open(PF.__file__, encoding="utf-8").read()
        assert src.count("失敗，該因子不計入綜合分：") == 3
        assert "；該因子不計入綜合分，「名稱」欄也會是空的" in src
        assert _NEW_LINE in src and _OLD_LINE not in src

    def test_mutation_restore_old_clause_is_caught(self, world):
        m = _mutant(PF, (_NEW_LINE, _OLD_LINE))
        _break(world, "pe_tpex")
        _res, _card, facts = _run(m, ("pe_low", "eps_high"))
        rows = _pe_rows(facts)
        assert _NEW_ROW not in rows and _OLD_ROW in rows, \
            "突變體還原舊子句 → 上面 test_half_missing_row_drops_clause 會紅"
