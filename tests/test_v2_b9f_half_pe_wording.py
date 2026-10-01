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
_COND = "    if _pe_half_idx is not None and _pe_scored(_df):\n"


def _twse_disjoint() -> pd.DataFrame:
    """上市那半邊有有效本益比，但代碼**一檔都不在存活池**（QA 1a）。"""
    return pd.DataFrame({"代碼": ["9998", "9999"], "名稱": ["甲", "乙"],
                         "本益比": [11.0, 13.0]})


def _break_disjoint(world) -> None:
    _break(world, "pe_tpex")
    world.setattr(_B5.YPF, "fetch_twse_yield_pe", _twse_disjoint)


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
        assert _OLD_LINE in src, "原句一字未改地留在原位（只在排名後條件式刪子句）"
        assert PF.PE_EXCLUDED_CLAUSE == _DELETED

    # ── QA 1a：剩下那半邊與存活池不相交 → L3 整個因子不計 → 原句成立、照留 ──
    def test_premise_disjoint_l3_drops_factor(self, world):
        _break_disjoint(world)
        res, _card, _facts = _run(PF, ("pe_low", "eps_high"))
        assert res.pe_n == 2, "前提：剩下那半邊確實有有效本益比"
        assert res.df["估值分"].isna().all(), "前提：L3 對每一檔都沒給估值分"

    def test_disjoint_keeps_original_clause(self, world):
        _break_disjoint(world)
        _res, _card, facts = _run(PF, ("pe_low", "eps_high"))
        rows = _pe_rows(facts)
        assert _OLD_ROW in rows, rows
        assert _NEW_ROW not in rows

    def test_pe_not_ticked_keeps_original_clause(self, world):
        """沒勾估值 → 結果表沒有「估值分」欄 → 該因子本來就不計 → 原句照留。"""
        _break(world, "pe_tpex")
        _res, _card, facts = _run(PF, ("eps_high",))
        assert _OLD_ROW in _pe_rows(facts)

    def test_pe_scored_helper(self):
        assert PF._pe_scored(None) is False
        assert PF._pe_scored(pd.DataFrame({"代碼": ["1"]})) is False
        assert PF._pe_scored(pd.DataFrame({"估值分": [None, float("nan")]})) is False
        assert PF._pe_scored(pd.DataFrame({"估值分": [None, 50.0]})) is True

    # ── 突變：新條件拔掉任一半 → 必須紅 ──
    def test_mutation_never_delete_is_caught(self, world):
        m = _mutant(PF, (_COND, "    if False:\n"))
        _break(world, "pe_tpex")
        _res, _card, facts = _run(m, ("pe_low", "eps_high"))
        rows = _pe_rows(facts)
        assert _NEW_ROW not in rows and _OLD_ROW in rows, \
            "突變體永不刪 → test_half_missing_row_drops_clause 會紅"

    def test_mutation_always_delete_is_caught(self, world):
        m = _mutant(PF, (_COND, "    if _pe_half_idx is not None:\n"))
        _break_disjoint(world)
        _res, _card, facts = _run(m, ("pe_low", "eps_high"))
        rows = _pe_rows(facts)
        assert _OLD_ROW not in rows and _NEW_ROW in rows, \
            "突變體一律刪 → test_disjoint_keeps_original_clause 會紅"
