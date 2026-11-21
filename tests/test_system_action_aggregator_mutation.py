"""System Action Aggregator 突變驗證（M-A2；Gate §4.6.8「皆附 mutation：拔掉守衛邏輯必轉紅」）。

做法：讀原始碼 → 套字串替換（每筆**恰好命中一次**，否則是假的突變）→ exec 成新模組（不改 repo 檔）
→ 餵給 `tests/_system_action_checks.py` 的同一份檢查 → 必須失敗（AssertionError／建構期 ValueError／TypeError）。
A-T1 的突變（注入不純 import／呼叫）在 `test_system_action_aggregator_contract.py`。
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

from shared import system_action_contract as REAL_C
from src.services import system_action_aggregator as REAL_A
from tests import _system_action_checks as K

_ROOT = Path(__file__).resolve().parent.parent
_AGG = "src/services/system_action_aggregator.py"
_CON = "shared/system_action_contract.py"


def _mutant(rel: str, swaps) -> types.ModuleType:
    text = (_ROOT / rel).read_text(encoding="utf-8")
    for old, new in swaps:
        assert text.count(old) == 1, f"突變點在 {rel} 出現 {text.count(old)} 次（需恰好 1 次）：{old!r}"
        text = text.replace(old, new)
    name = f"_mutant_{rel.replace('/', '_').replace('.', '_')}_{abs(hash(tuple(swaps)))}"
    mod = types.ModuleType(name)
    mod.__file__ = str(_ROOT / rel)
    sys.modules[name] = mod           # @dataclass 解註解需要
    try:
        exec(compile(text, f"<mutant:{rel}>", "exec"), mod.__dict__)
    except Exception:
        sys.modules.pop(name, None)
        raise
    return mod


def _build(agg_swaps=(), con_swaps=()):
    C = _mutant(_CON, con_swaps) if con_swaps else REAL_C
    A = _mutant(_AGG, agg_swaps) if (agg_swaps or con_swaps) else REAL_A
    if con_swaps:
        A.C = C
    return A, C


# (A-T 編號, 說明, aggregator 替換, contract 替換, 檢查)
MUTANTS = [
    # ── A-T2 表格驅動 ──
    ("A-T2", "暫停加碼分組 留→加",
     [("C.BRANCH_PAUSE_ADD: (C.ACTION_CLASS_ACTIONABLE, C.GROUP_HOLD,",
       "C.BRANCH_PAUSE_ADD: (C.ACTION_CLASS_ACTIONABLE, C.GROUP_ADD,")], [], K.check_t2_table),
    ("A-T2", "⚪ 資料不足 undeterminable→not_evaluated（DEC-124 合併）",
     [("C.SWAP_INSUFFICIENT: (C.ACTION_CLASS_UNDETERMINABLE,",
       "C.SWAP_INSUFFICIENT: (C.ACTION_CLASS_NOT_EVALUATED,")], [], K.check_t2_data_short),
    ("A-T2", "unjudged 覆寫成 not_evaluated（DEC-124 合併）",
     [("        _cls, _grp, _today, _rid = C.ACTION_CLASS_UNDETERMINABLE, C.GROUP_NONE, False, \"\"",
       "        _cls, _grp, _today, _rid = C.ACTION_CLASS_NOT_EVALUATED, C.GROUP_NONE, False, \"\"")],
     [], K.check_t2_data_short),
    ("A-T2", "拔掉 unjudged→undeterminable 覆寫",
     [("    if _short == SHORT_UNJUDGED:", "    if False:")], [], K.check_t2_data_short),
    ("A-T2", "整批失敗 unavailable→not_evaluated",
     [("formal_label=_label, action_class=C.ACTION_CLASS_UNAVAILABLE,",
       "formal_label=_label, action_class=C.ACTION_CLASS_NOT_EVALUATED,")], [], K.check_t2_data_short),
    ("A-T2", "加碼 item 不帶 Risk Cap 標註",
     [("            if (_src_kind == C.SOURCE_KIND_ACTION_BRANCH and _rule == C.BRANCH_ADD",
       "            if (False and _rule == C.BRANCH_ADD")], [], K.check_t2_table),
    # ── A-T3 W-5 ──
    ("A-T3", "暫停加碼不計入",
     [("C.BRANCH_PAUSE_ADD: (C.ACTION_CLASS_ACTIONABLE, C.GROUP_HOLD, True,",
       "C.BRANCH_PAUSE_ADD: (C.ACTION_CLASS_ACTIONABLE, C.GROUP_HOLD, False,")], [], K.check_t3_w5),
    ("A-T3", "🟡 留意升格成 action",
     [("C.SWAP_WATCH: (C.ACTION_CLASS_NON_ACTIONABLE, C.GROUP_HOLD, False,",
       "C.SWAP_WATCH: (C.ACTION_CLASS_ACTIONABLE, C.GROUP_HOLD, True,")], [], K.check_t3_w5),
    ("A-T3", "巡航計入",
     [("C.BRANCH_CRUISE: (C.ACTION_CLASS_NON_ACTIONABLE, C.GROUP_HOLD, False,",
       "C.BRANCH_CRUISE: (C.ACTION_CLASS_ACTIONABLE, C.GROUP_HOLD, True,")], [], K.check_t3_w5),
    ("A-T3", "觀察清單計入今日",
     [("counts_toward_today=bool(_today and _held),", "counts_toward_today=bool(_today),")],
     [], K.check_t3_watchlist),
    # ── A-T4 day_status ──
    ("A-T4", "拔掉巡航 gate",
     [("    elif (_cruise_open and not _digest_short", "    elif (True and not _digest_short")],
     [], K.check_t4_day_status),
    ("A-T4", "拔掉 digest_data_short",
     [("    elif (_cruise_open and not _digest_short and", "    elif (_cruise_open and")],
     [], K.check_t4_day_status),
    ("A-T4", "拔掉巡航 gate＋契約縱深",
     [("    elif (_cruise_open and not _digest_short", "    elif (True and not _digest_short")],
     [("        if self.day_status == DAY_NO_ADJUSTMENT_TODAY and (", "        if False and (")],
     K.check_t4_day_status),
    ("A-T4", "契約縱深拔掉（no_adjustment 與判不出並存）",
     [], [("        if self.day_status == DAY_NO_ADJUSTMENT_TODAY and (", "        if False and (")],
     K.check_t4_contract_guard),
    # ── A-T5 禁用字樣／新 action code ──
    ("A-T5", "分批停利加「減碼 1/2」",
     [("formal_label=_label, action_class=_cls,",
       "formal_label=_label + ('（減碼 1/2）' if _rule == C.BRANCH_TAKE_PROFIT_PARTIAL else ''), "
       "action_class=_cls,")], [], K.check_t5_forbidden),
    ("A-T5", "Risk Cap 標註改成比例字樣",
     [], [('RISK_CAP_TAG_UNDETERMINABLE: str = "Risk Cap 無法判定"',
           'RISK_CAP_TAG_UNDETERMINABLE: str = "Risk Cap 無法判定，建議持股 50%"')], K.check_t5_forbidden),
    ("A-T5", "新 action code（巡航改名 hold）＋契約放行",
     [("C.BRANCH_CRUISE: (C.ACTION_CLASS_NON_ACTIONABLE, C.GROUP_HOLD, False, \"\"),",
       "C.BRANCH_CRUISE: (C.ACTION_CLASS_NON_ACTIONABLE, C.GROUP_HOLD, False, \"\"),\n    \"hold\": "
       "(C.ACTION_CLASS_NON_ACTIONABLE, C.GROUP_HOLD, False, \"\"),"),
      ("        _src_kind, _rule = C.SOURCE_KIND_ACTION_BRANCH, _r[\"_action\"]",
       "        _src_kind, _rule = C.SOURCE_KIND_ACTION_BRANCH, ('hold' if _r['_action'] == 'cruise' "
       "else _r['_action'])")],
     [('BRANCH_PAUSE_ADD, BRANCH_ADD, BRANCH_PREMIUM, BRANCH_CRUISE)',
       'BRANCH_PAUSE_ADD, BRANCH_ADD, BRANCH_PREMIUM, BRANCH_CRUISE, "hold")')], K.check_t5_forbidden),
    # ── A-T6 rule_id allowlist ──
    ("A-T6", "高溢價帶 rule_id premium（契約守衛亦拔）",
     [("C.BRANCH_PREMIUM: (C.ACTION_CLASS_NON_ACTIONABLE, C.GROUP_HOLD, False, \"\"),",
       "C.BRANCH_PREMIUM: (C.ACTION_CLASS_ACTIONABLE, C.GROUP_HOLD, False, \"premium\"),")],
     [('        if self.rule_id != "" and self.rule_id not in RULE_ID_ALLOWLIST_KEYS:', "        if False:")],
     K.check_t6_rule_ids),
    ("A-T6", "🔴 換出帶 rule_id swap_out（只拔 aggregator；契約擋下＝轉紅）",
     [("C.SWAP_OUT: (C.ACTION_CLASS_ACTIONABLE, C.GROUP_SWAP, True, \"\"),",
       "C.SWAP_OUT: (C.ACTION_CLASS_ACTIONABLE, C.GROUP_SWAP, True, \"swap_out\"),")], [], K.check_t6_rule_ids),
    # ── A-T7 原名逐字 ──
    ("A-T7", "formal_label 全形冒號改半形",
     [("formal_label=_label, action_class=_cls,", "formal_label=_label.replace('：', ':'), action_class=_cls,")],
     [], K.check_t7_verbatim),
    ("A-T7", "formal_label 去前後空白＋截 20 字",
     [("formal_label=_label, action_class=_cls,", "formal_label=_label.strip()[:20], action_class=_cls,")],
     [], K.check_t7_verbatim),
    # ── A-T8 parity（PORT 函式） ──
    ("A-T8", "judged_count 拔 state 白名單",
     [("    _num = sum(1 for c in _cs\n               if c.state in (SS.STATE_LIVE, SS.STATE_DEGRADED)\n"
       "               and c.level != C.LEVEL_UNJUDGED)",
       "    _num = sum(1 for c in _cs\n               if c.level != C.LEVEL_UNJUDGED)")], [], K.check_t8_parity),
    ("A-T8", "judged_count 拔 level 非空",
     [("               and c.level != C.LEVEL_UNJUDGED)", "               and True)")], [], K.check_t8_parity),
    ("A-T8", "分母不排除 emits_level=False",
     [("    return _spec is None or _spec.emits_level", "    return True")], [], K.check_t8_parity),
    ("A-T8", "is_fully_judged 空列回 True",
     [("    return _m > 0 and _n == _m", "    return _n == _m")], [], K.check_t8_parity),
    ("A-T8", "tally_states 不排除分母外格",
     [("            if not _in_judged_denominator(_c):\n                continue",
       "            if False:\n                continue")], [], K.check_t8_parity),
    ("A-T8", "cruise_or_gap 不看 all_rows_judged",
     [("    if all_rows_judged and total > 0 and judged == total:", "    if total > 0 and judged == total:")],
     [], K.check_t8_parity),
    ("A-T8", "incomplete_rows_n 不含資料不足列",
     [("if _sh or not is_fully_judged(_c))", "if not is_fully_judged(_c))")], [], K.check_t8_parity),
    ("A-T8", "digest_data_short 改成只看 errors",
     [("    _digest_short = bool(digest_data_short(station_digest))",
       "    _digest_short = bool(station_digest.get('errors'))")], [], K.check_t8_parity),
    ("A-T8", "has_system_risk_cap 判反",
     [("    return any(getattr(c, \"name\", None) == C.SYSTEM_RISK_CAP_NAME for c in (caps or ()))",
       "    return any(getattr(c, \"name\", None) != C.SYSTEM_RISK_CAP_NAME for c in (caps or ()))")],
     [], K.check_t8_parity),
    # ── A-T9 Presentation Slice ──
    ("A-T9", "items 截斷 top 20",
     [("    _items = tuple(_classify_row(_row, station_stamp) for _row in station_rows)",
       "    _items = tuple(_classify_row(_row, station_stamp) for _row in station_rows[:20])")],
     [], K.check_t9_slice_independent),
    ("A-T9", "新增 top_n 參數",
     [("                             station_stamp: C.ActionSourceStamp) -> C.SystemActionState:",
       "                             station_stamp: C.ActionSourceStamp, top_n: int = 3) -> C.SystemActionState:")],
     [], K.check_t9_slice_independent),
    ("A-T9", "items 依 ticker 重排",
     [("    _items = tuple(_classify_row(_row, station_stamp) for _row in station_rows)",
       "    _items = tuple(sorted((_classify_row(_row, station_stamp) for _row in station_rows), "
       "key=lambda i: i.ticker, reverse=True))")], [], K.check_t9_slice_independent),
    # ── A-T10 Risk Cap ──
    ("A-T10", "Risk Cap state 被改寫成 missing",
     [("        risk_cap_state=risk_cap,", "        risk_cap_state=C.RiskCapState(status=C.RISK_CAP_MISSING, "
       "stamp=risk_cap.stamp),")], [], K.check_t10_risk_cap),
    ("A-T10", "exposure_gate 依 Risk Cap 自判（契約守衛亦拔）",
     [("        exposure_gate=C.ExposureGate(),",
       "        exposure_gate=C.ExposureGate(status='blocked' if risk_cap.status == C.RISK_CAP_VALID "
       "else C.EXPOSURE_GATE_UNDETERMINABLE),")],
     [("        if self.status != EXPOSURE_GATE_UNDETERMINABLE:", "        if False:")], K.check_t10_risk_cap),
    # ── 公開欄位＝凍結 O1～O5（#1199 總管裁定：day_basis 移出公開輸出） ──
    ("O1-O5", "day_basis 加回公開 SystemActionState（有預設值，Aggregator 仍可建構）",
     [], [("    provenance: ActionProvenance\n", "    provenance: ActionProvenance\n    day_basis: Any = None\n")],
     K.check_o1_o5_public_fields),
    ("O1-O5", "day_basis 加回且 Aggregator 建構時傳入該欄",
     [("        provenance=C.ActionProvenance(inputs=((\"station\", station_stamp), (\"risk_cap\", risk_cap.stamp))))\n",
       "        provenance=C.ActionProvenance(inputs=((\"station\", station_stamp), (\"risk_cap\", risk_cap.stamp))),\n"
       "        day_basis=None)\n")],
     [("    provenance: ActionProvenance\n", "    provenance: ActionProvenance\n    day_basis: Any = None\n")],
     K.check_o1_o5_public_fields),
    ("A-T10", "valid 時自行補 pct（改寫值）",
     [("    return C.RiskCapState(status=C.RISK_CAP_VALID, system_cap_pct=_sys[0].pct,",
       "    return C.RiskCapState(status=C.RISK_CAP_VALID, system_cap_pct=min(_sys[0].pct, 30),")],
     [], K.check_t10_risk_cap),
]


@pytest.mark.parametrize("at, desc, agg_swaps, con_swaps, check", MUTANTS,
                         ids=[f"{m[0]}:{m[1]}" for m in MUTANTS])
def test_mutant_turns_red(at, desc, agg_swaps, con_swaps, check):
    try:
        A, C = _build(agg_swaps, con_swaps)
    except (ValueError, TypeError) as e:          # 模組載入期就被契約擋下 ⇒ 亦屬轉紅
        pytest.fail(f"突變在載入期即失敗（請改用可載入的突變）：{e!r}")
    with pytest.raises((AssertionError, ValueError, TypeError)):
        check(A, C)


def test_unmutated_baseline_passes_every_check():
    """對照組：未突變的模組，上面用到的每個檢查都通過（否則突變「轉紅」沒有意義）。"""
    for chk in {m[4] for m in MUTANTS}:
        chk(REAL_A, REAL_C)


def test_mutant_count_per_at():
    from collections import Counter
    c = Counter(m[0] for m in MUTANTS)
    assert all(c[k] >= 2 for k in ("A-T2", "A-T3", "A-T4", "A-T5", "A-T6", "A-T7", "A-T8", "A-T9", "A-T10",
                                   "O1-O5")), c
