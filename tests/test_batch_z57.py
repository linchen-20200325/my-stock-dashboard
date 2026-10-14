"""批 Z57 —— 批 Z56（#843）獨立 QA 三條低嚴重度觀察的內部自修（修正錯誤，非改設計）。

n1｜對帳卡全 ⬜ 灰態的「為什麼」與程式行為逐字相符：
    · 程式條件是 `if _jq_info:` ⇒ `jingqi_info` 不存在**或為空**（`None`、空 dict）都改讀 warroom；
    · 原句「依讀取順序」不實（`health_inputs` 先取 `warroom_summary` 再取 `jingqi_info`）⇒ 改「依對帳列順序」。
n2｜灰態 key 清單與 L3 實際讀取共用 SSOT：L3 `reconcile_service.RECONCILE_SESSION_KEYS`；
    本檔以**記錄式假 session**（dict 子類，記下 `__getitem__`／`get` 讀過的 key）實跑各分支守衛。
n3｜「拿掉等值檢查」突變補卡片層整合守衛：`build_qa_card` 產出的 `_InvalidDataNote`，若 `invalid_items`
    與 why 不一致 ⇒ 卡面只放通用段（不含項目名），全文仍在摺疊區。
"""
from __future__ import annotations

import dataclasses
import pathlib

import pandas as pd
import pytest

import src.services.reconcile_service as RS
from shared.station_specs import invalid_data_text
from shared.ui_state import UI_FAILED, UI_LIVE, UI_MISSING_RETRYABLE
from src.ui.views import page_why as P

NAN, INF = float("nan"), float("inf")
_REQ = P.EngineerRequest(opened=True)
ROOT = pathlib.Path(__file__).resolve().parents[1]


# ══════════════════════════════════════════════════════════════════
# 記錄式假 session
# ══════════════════════════════════════════════════════════════════
class _Rec(dict):
    """dict 子類：記下每一次 `__getitem__`／`get` 讀的 key（含巢狀路徑）到共用 log。

    巢狀 dict 在建構時一併包成 `_Rec`（共用同一份 log、帶路徑），其他值（DataFrame 等）原樣。
    """

    def __init__(self, data, log=None, path=()):
        self.log = [] if log is None else log
        self.path = tuple(path)
        super().__init__({k: (_Rec(v, self.log, self.path + (k,)) if type(v) is dict else v)
                          for k, v in data.items()})

    def __getitem__(self, key):
        self.log.append(self.path + (key,))
        return super().__getitem__(key)

    def get(self, key, default=None):
        self.log.append(self.path + (key,))
        return super().get(key, default)

    def top_keys(self):
        return {p[0] for p in self.log if len(p) == 1}


def _tnx(v):
    return pd.DataFrame({"close": [4.0, v]})


def _full(**over):
    s = {"macro_info": {"us10y": {"value": 4.25}},
         "cl_data": {"intl": {"10Y公債殖利率": _tnx(4.27)},
                     "inst": {"外資及陸資": {"net": 35.2}}},
         "jingqi_info": {"avg": 62.0},
         "mkt_info": {"score": 3, "max_score": 5},
         "t2_data": {"rev_yoy_self": 10.0, "rev_yoy_finmind": 10.1},
         "warroom_summary": {"jingqi_avg": 50.0}}
    s.update(over)
    return {k: v for k, v in s.items() if v is not _DROP}


_DROP = object()

#: 各分支（含 n1 點名的三種 `jingqi_info` 狀態）。
_BRANCHES = {
    "empty": {},
    "full_with_jingqi_info": _full(),
    "jingqi_info_empty_dict": _full(jingqi_info={}),
    "jingqi_info_none": _full(jingqi_info=None),
    "no_jingqi_info": _full(jingqi_info=_DROP),
    "jingqi_info_without_avg": _full(jingqi_info={"x": 1}),
    "invalid_values": _full(macro_info={"us10y": {"value": NAN}}, jingqi_info={"avg": INF},
                            t2_data={"rev_yoy_self": NAN}),
    "only_mkt": {"mkt_info": {"score": 3}},
}

_ROW_FNS = {RS.ROW_US10Y: RS._us10y_row, RS.ROW_REV_YOY: RS._rev_yoy_row,
            RS.ROW_HEALTH: RS._health_row}


def _const_keys(const=None) -> set[str]:
    return {k for e in (RS.RECONCILE_SESSION_KEYS if const is None else const) for k in e.keys}


def _reads(fn, data) -> _Rec:
    s = _Rec(data)
    fn(s)
    return s


# ══════════════════════════════════════════════════════════════════
# n2｜L3 唯讀 SSOT ↔ 實際讀取
# ══════════════════════════════════════════════════════════════════
def _assert_reads_subset(const):
    for name, data in _BRANCHES.items():
        got = _reads(RS.compute_reconcile, data).top_keys()
        assert got <= _const_keys(const), (name, got - _const_keys(const))


def _assert_no_dead_entries(const):
    seen: set[str] = set()
    for data in _BRANCHES.values():
        seen |= _reads(RS.compute_reconcile, data).top_keys()
    for e in const:
        for k in e.keys:
            assert k in seen, f"死條目：{k!r}（{e.desc}）在任何分支都沒被讀到"


class TestSessionKeysSsot:
    def test_constant_is_a_readonly_tuple_of_named_entries(self):
        c = RS.RECONCILE_SESSION_KEYS
        assert isinstance(c, tuple) and c
        for e in c:
            assert isinstance(e, tuple) and isinstance(e, RS.SessionRead)
            assert e.row in _ROW_FNS and isinstance(e.keys, tuple) and e.keys and e.desc
            with pytest.raises(AttributeError):
                e.desc = "x"   # NamedTuple：唯讀

    def test_recorder_really_records(self):
        """反證：記錄器不是空轉（否則 ⊆ 永遠成立）。"""
        s = _reads(RS.compute_reconcile, _full())
        assert {"macro_info", "cl_data", "t2_data", "mkt_info"} <= s.top_keys()
        assert ("macro_info", "us10y") in s.log and ("cl_data", "inst") in s.log

    def test_actual_top_level_reads_are_a_subset_of_the_constant(self):
        _assert_reads_subset(RS.RECONCILE_SESSION_KEYS)

    def test_every_constant_key_is_read_in_some_branch(self):
        _assert_no_dead_entries(RS.RECONCILE_SESSION_KEYS)

    @pytest.mark.parametrize("branch", sorted(_BRANCHES))
    def test_each_row_reads_exactly_its_own_entries(self, branch):
        for row, fn in _ROW_FNS.items():
            want = {k for e in RS.RECONCILE_SESSION_KEYS if e.row == row for k in e.keys}
            assert _reads(fn, _BRANCHES[branch]).top_keys() == want, (branch, row)

    def test_entries_follow_reconcile_row_order(self):
        """畫面寫「依對帳列順序」⇒ 常數的排列必須照 `compute_reconcile` 的列順序。"""
        order = [r.name for r in RS.compute_reconcile({}).rows]
        idx = [order.index(e.row) for e in RS.RECONCILE_SESSION_KEYS]
        assert idx == sorted(idx)
        assert set(idx) == set(range(len(order)))   # 每一列都有條目

    def test_mutation_missing_entry_turns_red(self):
        mutated = tuple(e for e in RS.RECONCILE_SESSION_KEYS if "jingqi_info" not in e.keys)
        with pytest.raises(AssertionError):
            _assert_reads_subset(mutated)

    def test_mutation_dead_entry_turns_red(self):
        mutated = RS.RECONCILE_SESSION_KEYS + (RS.SessionRead(RS.ROW_HEALTH, ("ghost_key",), "`x`"),)
        with pytest.raises(AssertionError):
            _assert_no_dead_entries(mutated)


# ══════════════════════════════════════════════════════════════════
# n1｜灰態「為什麼」與程式行為逐字相符
# ══════════════════════════════════════════════════════════════════
class TestGreyWhyMatchesBehaviour:
    @pytest.mark.parametrize("branch,falls_back", [
        ("full_with_jingqi_info", False),
        ("jingqi_info_without_avg", False),   # 非空但沒有 avg ⇒ 缺值，⛔ 不退回 warroom
        ("jingqi_info_empty_dict", True),     # n1：空 dict 也改讀 warroom
        ("jingqi_info_none", True),
        ("no_jingqi_info", True),
    ])
    def test_warroom_subkey_is_read_only_when_jingqi_info_absent_or_empty(self, branch, falls_back):
        s = _reads(RS._health_row, _BRANCHES[branch])
        assert (("warroom_summary", "jingqi_avg") in s.log) is falls_back, branch
        assert (("jingqi_info", "avg") in s.log) is (not falls_back), branch

    def test_text_states_the_real_condition_and_no_false_order_claim(self):
        why = P.reconcile_not_triggered_why(RS.RECONCILE_SESSION_KEYS)
        # 批 Z58（Z57-n1）：「為空」→「為假值（如 …）」—— `if _jq_info:` 對任何假值都改讀 warroom。
        assert "`jingqi_info` 不存在或為假值（如 `None`、空 dict）時改讀 `warroom_summary['jingqi_avg']`" in why
        assert "依讀取順序" not in why and "不存在時讀" not in why
        assert "（依對帳列順序）" in why

    def test_l3_docstrings_no_longer_say_only_when_absent(self):
        text = (ROOT / "src" / "services" / "reconcile_service.py").read_text(encoding="utf-8")
        assert "`jingqi_info` 不存在時才讀" not in text
        assert "只在 `jingqi_info`\n   不存在時才用" not in text

    @pytest.mark.parametrize("session", [{}, {"mkt_info": {"score": 3}},
                                         {"jingqi_info": None, "warroom_summary": {"jingqi_avg": 50.0}}])
    def test_grey_card_why_is_composed_from_the_l3_constant(self, session):
        r = P.load_reconcile(_REQ, session)
        assert r.session_reads == RS.RECONCILE_SESSION_KEYS
        card = P.build_reconcile_card(r)[0]
        assert card.state == UI_MISSING_RETRYABLE
        assert card.note.why == (P.RECONCILE_NOT_TRIGGERED_WHY_HEAD
                                 + "、".join(e.desc for e in RS.RECONCILE_SESSION_KEYS))
        assert card.note.now == P.RECONCILE_NOT_TRIGGERED_NOW
        assert card.note.where == P.REGISTRY_NOT_WRITTEN_WHERE

    def test_grey_why_full_text_golden(self):
        assert P.reconcile_not_triggered_why(RS.RECONCILE_SESSION_KEYS) == (
            "三列對帳都是「未觸發」—— 每一列都至少缺一邊的值。對帳讀的是（依對帳列順序）："
            "`macro_info['us10y']['value']`、`cl_data['intl']['10Y公債殖利率']`、"
            "`t2_data['rev_yoy_self']`／`t2_data['rev_yoy_finmind']`、"
            "`jingqi_info['avg']`（`jingqi_info` 不存在或為假值（如 `None`、空 dict）時改讀 "
            "`warroom_summary['jingqi_avg']`）、"
            "`mkt_info['score']`、`mkt_info['max_score']`、`cl_data['inst']` 外資 net")

    def test_grey_face_excerpt_unchanged(self):
        card = P.build_reconcile_card(P.load_reconcile(_REQ, {}))[0]
        assert dict(P.v2_short_rows(card)[0])[P.V2_WHY_FACT_KEY] == \
            "三列對帳都是「未觸發」—— 每一列都至少缺一邊的值"

    @pytest.mark.parametrize("bad", [(), None, (RS.SessionRead(RS.ROW_US10Y, ("x",), ""),)])
    def test_empty_key_list_fails_loud(self, bad):
        with pytest.raises(ValueError):
            P.reconcile_not_triggered_why(bad)

    def test_grey_readout_without_keys_fails_loud_not_silently(self):
        report = RS.compute_reconcile({})
        with pytest.raises(ValueError):
            P.build_reconcile_card(P.ReconcileReadout(requested=True, report=report))

    def test_live_path_does_not_depend_on_the_key_list(self):
        """正常（非灰）路徑：輸出與 `session_reads` 無關（逐字相同）。"""
        report = RS.compute_reconcile(_full())
        a = P.build_reconcile_card(P.ReconcileReadout(requested=True, report=report))
        b = P.build_reconcile_card(P.ReconcileReadout(
            requested=True, report=report, session_reads=RS.RECONCILE_SESSION_KEYS))
        assert a[0].state == UI_LIVE and a == b
        assert P.v2_card_html(*a) == P.v2_card_html(*b)


# ══════════════════════════════════════════════════════════════════
# n3｜卡片層：invalid_items 與 why 不一致 ⇒ 卡面只放通用段
# ══════════════════════════════════════════════════════════════════
_GENERIC = "資料異常，無法計算，不下結論。"


def _qa_built(items):
    return P.build_qa_card(P.QaReadout(
        asked=True, error="".join(invalid_data_text(_i) for _i in items),
        tool_calls=("get_market_leading",), invalid_items=tuple(items)))


def _with_items(built, items):
    card = built[0]
    return (dataclasses.replace(card, note=dataclasses.replace(card.note, invalid_items=tuple(items))),
            built[1], built[2])


_MISMATCH = [
    (("外資",), ("投信",)),                 # 項目換掉
    (("外資",), ("外資", "投信")),          # 多一項
    (("外資", "投信"), ("投信", "外資")),   # 順序不同
    (("外資", "投信"), ("外資",)),          # 少一項
]


def _assert_mismatch_shows_generic_only(built_items, note_items):
    built = _with_items(_qa_built(built_items), note_items)
    card = built[0]
    assert type(card.note) is P._InvalidDataNote and card.state == UI_FAILED
    full_why = "".join(invalid_data_text(_i) for _i in built_items)
    assert card.note.why == full_why and card.note.invalid_items == tuple(note_items)
    short, full = P.v2_short_rows(card)
    face = dict(short)[P.V2_WHY_FACT_KEY]
    assert face == _GENERIC, face
    for item in set(built_items) | set(note_items):
        assert item not in face
    assert dict(full)[P.V2_WHY_FACT_KEY] == P.v2_plain(full_why)
    assert P.v2_plain(full_why) in P.v2_card_html(*built)   # 全文仍在摺疊區


class TestQaCardMismatchedItems:
    def test_control_consistent_items_show_whole_sentence(self):
        """對照組：一致時卡面整句（含項目名）—— 證明下面的「通用段」不是因為整句候選壞掉。"""
        card = _qa_built(("外資",))[0]
        assert type(card.note) is P._InvalidDataNote
        assert dict(P.v2_short_rows(card)[0])[P.V2_WHY_FACT_KEY] == "外資" + _GENERIC

    @pytest.mark.parametrize("built_items,note_items", _MISMATCH)
    def test_mismatch_shows_only_the_generic_excerpt(self, built_items, note_items):
        _assert_mismatch_shows_generic_only(built_items, note_items)

    def test_mutation_dropping_the_equality_check_turns_red(self, monkeypatch):
        """突變：整句候選拿掉「與重組句相等」⇒ 不一致時整句（含項目名）上卡面 ⇒ 守衛轉紅。"""
        key = ("why.qa", P.QA_FAILED_NOW)
        now, why, where = P.V2_SHORT_ROWS[key]

        def _no_equality(full, note):
            _items = tuple(getattr(note, "invalid_items", ()) or ()) \
                if isinstance(note, P._InvalidDataNote) else ()
            return bool(_items) and len(full) <= P.v2_markup.FACT_VALUE_MAX_CHARS

        mutant = P._V2WholeIfFits(accept=_no_equality, name=P._V2_INVALID_WHOLE.name)
        monkeypatch.setitem(P.V2_SHORT_ROWS, key, (now, tuple(
            mutant if c is P._V2_INVALID_WHOLE else c for c in why), where))
        for built_items, note_items in _MISMATCH:
            with pytest.raises(AssertionError):
                _assert_mismatch_shows_generic_only(built_items, note_items)
