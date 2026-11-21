"""System Action Aggregator A-T8 parity（M-A2；Architecture Gate §4.6.8）。

PORT 原則（Gate §5.1 第 2 點）：`station_cards` 的判全／計數／巡航 gate 與 `risk_cap_gate.has_system_risk_cap`
在 L3 另建（L3 不得 import L4／L5），Old UI 原檔一字不改；本檔以 golden 夾具釘兩處同輸出，
並與 `page_hold.load_station`（真的跑，只把 L3 取數換成固定列）的 judged／total／`unjudged_rows`／
tally／巡航句逐一對照。突變證明見 `tests/test_system_action_aggregator_mutation.py`。
"""
from __future__ import annotations

import pytest

from shared import system_action_contract as C
from src.services import system_action_aggregator as A
from tests import _system_action_checks as K


def test_a_t8_parity_golden():
    assert K.check_t8_parity(A, C) > 200


# ── 已知差異（⛔ 自行改哪一邊；送總管裁定）───────────────────────────────────
# 既有 page_hold「該做什麼」卡的 add_n／cut_n 取自 digest：`cut_n=len(digest["reds"])`（健檢 🔴，
# **含觀察清單**、且 ETF 的 🔴 可能來自健檢 C 而非 cut 分支）、`add_n=len(digest["adds"])`（持有＋add 分支，
# 不看資料異常）。Aggregator 依凍結契約：今日需處理只計持有列（W-5 portfolio action）、
# unjudged（資料異常）→ undeterminable 不計入。兩者在下列夾具上**不一致** —— 以 strict xfail 釘住現況，
# 任何一邊被改都會轉紅、逼回到 Gate 裁定。
def _page_hold_reduce_like(rows):
    ph, _ = K._patched_page_hold(rows)
    return ph.add_n, ph.cut_n


def _agg_reduce_like(rows):
    st = K.run(A, C, rows)
    add = sum(1 for i in st.items if i.counts_toward_today and i.group == C.GROUP_ADD)
    cut = sum(1 for i in st.items if i.counts_toward_today and i.group in (C.GROUP_SWAP, C.GROUP_REDUCE))
    return add, cut


@pytest.mark.xfail(strict=True, reason="已知差異送總管裁定：digest reds 含觀察清單 🔴；Aggregator 只計持有列")
def test_known_divergence_watchlist_red_counts():
    rows = K.golden_scenarios()["watchlist"]
    assert _page_hold_reduce_like(rows) == _agg_reduce_like(rows)


@pytest.mark.xfail(strict=True, reason="已知差異送總管裁定：資料異常的 cut 列 digest 仍算 reds；Aggregator→undeterminable")
def test_known_divergence_invalid_inputs_cut():
    rows = K.golden_scenarios()["invalid_inputs_cut"]
    assert _page_hold_reduce_like(rows) == _agg_reduce_like(rows)


@pytest.mark.xfail(strict=True, reason="已知差異送總管裁定：digest reds＝健檢 🔴（只計 🔴 換出與汰弱以外的停利不在 reds）")
def test_known_divergence_take_profit_not_in_reds():
    rows = [K.etf_row("take_profit_force", "0050"), K.etf_row("take_profit_partial", "0056")]
    assert _page_hold_reduce_like(rows) == _agg_reduce_like(rows)


def test_divergence_documented_values():
    """把上面三個差異的實際數字釘住（給總管報告用；改了就要重新送裁定）。"""
    g = K.golden_scenarios()
    assert _page_hold_reduce_like(g["watchlist"]) == (0, 2)
    assert _agg_reduce_like(g["watchlist"]) == (0, 0)
    assert _page_hold_reduce_like(g["invalid_inputs_cut"]) == (0, 1)
    assert _agg_reduce_like(g["invalid_inputs_cut"]) == (0, 0)
    rows = [K.etf_row("take_profit_force", "0050"), K.etf_row("take_profit_partial", "0056")]
    assert _page_hold_reduce_like(rows) == (0, 0)
    assert _agg_reduce_like(rows) == (0, 2)
