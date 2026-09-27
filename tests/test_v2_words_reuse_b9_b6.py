"""客戶 2026-09-27 裁示「補字 8：套現有字樣照做」—— B9 ⑨（D11）與 B6-r1。

只准重用既有字樣（或刪字）。每一項：(a) 修後行為、(b) 字樣全出自既有來源、(c) 突變 → 必須紅。
"""
from __future__ import annotations

import json

from shared.ui_state import UI_FAILED, UI_EMPTY
from src.ui.views import page_find as PF
from tests.test_v2_silent_fail_b12_b6 import _flow_card, _mutant
from tests.test_v2_silent_fail_b5_find import _break, _run

# fixture 以屬性指派重用（不 import 名稱 → pyflakes 不報 redefinition）
from tests import test_v2_silent_fail_b5_find as _B5  # noqa: E402
from tests import test_v2_silent_fail_b12_b6 as _B12  # noqa: E402
world = _B5.world
flow_dir = _B12.flow_dir

_PE = "估值（本益比）"
_SUFFIX = "失敗，該因子不計入綜合分"


# ══════════════════════════════════════════════════════════════════
# B9 ⑨：估值只少半邊 → facts 點名是哪個市場
# ══════════════════════════════════════════════════════════════════
class TestB9n9MarketNamed:
    def test_tpex_half_missing_names_tpex(self, world):
        _break(world, "pe_tpex")
        res, card, facts = _run(PF, ("pe_low", "eps_high"))
        assert card.state == UI_FAILED
        assert dict(facts)[_PE] == f"上櫃 TPEX{_SUFFIX}"

    def test_twse_half_missing_names_twse(self, world):
        _break(world, "pe_twse")
        res, _card, facts = _run(PF, ("pe_low",))
        assert dict(facts)[_PE] == f"上市 TWSE{_SUFFIX}"

    def test_both_missing_keeps_existing_empty_why(self, world):
        _break(world, "pe_both")
        _res, _card, facts = _run(PF, ("pe_low",))
        assert dict(facts)[_PE] == PF.PE_EMPTY_WHY

    def test_nothing_missing_adds_no_row(self, world):
        _res, _card, facts = _run(PF, ("pe_low",))
        assert not any(v.endswith(_SUFFIX) for k, v in facts if k == _PE)

    def test_wording_is_existing(self):
        src = open(PF.__file__, encoding="utf-8").read()
        assert src.count(f"{_SUFFIX}：") == 3, "三支掃描既有那句仍在（本批只重用它）"
        assert "上櫃 TPEX" in PF.PE_EMPTY_WHY and "上市 TWSE" in PF.PE_EMPTY_WHY

    def test_mutation_drop_branch_loses_market(self, world):
        m = _mutant(PF, ("    elif _pe_failed_markets:\n", "    elif False:\n"))
        _break(world, "pe_tpex")
        _res, _card, facts = _run(m, ("pe_low", "eps_high"))
        assert not any(v.endswith(_SUFFIX) for k, v in facts if k == _PE), \
            "突變體退回修前（沒點名市場）→ 上面那條會紅"


# ══════════════════════════════════════════════════════════════════
# B6-r1：泡泡圖壞檔紅卡 where ⛔ 不再指網路／proxy，改指灰態既有那一句
# ══════════════════════════════════════════════════════════════════
class TestB6r1FlowWhere:
    def test_corrupt_file_points_to_regen(self, flow_dir):
        (flow_dir / "bubble_latest.json").write_text("{not json", encoding="utf-8")
        c = _flow_card()
        assert c.state == UI_FAILED and c.note.where == PF.FLOW_REGEN_WHERE
        assert "proxy" not in c.note.where

    def test_empty_state_where_byte_identical(self, flow_dir):
        c = _flow_card()
        assert c.state == UI_EMPTY
        assert c.note.where == ("等當日盤後的「Update Sector Flow」排程；"
                                "或在 GitHub Actions 手動跑一次該工作流程")

    def test_short_row_reuses_empty_short(self):
        rows = PF.V2_SHORT_ROWS
        assert (rows[("find.sector_flow", PF.FLOW_FAILED_NOW)][2]
                == rows[("find.sector_flow", PF.FLOW_EMPTY_NOW)][2])

    def test_mutation_old_where_is_caught(self, flow_dir):
        m = _mutant(PF, ("                     where=FLOW_REGEN_WHERE)",
                         "                     where=\"先確認網路／proxy\")"))
        (flow_dir / "bubble_latest.json").write_text(json.dumps({"sectors": "x"}),
                                                     encoding="utf-8")
        assert _flow_card(mod=m).note.where != PF.FLOW_REGEN_WHERE
