"""`tests/_p25_info_conservation.py` 共用判定器本身的單元測試（Phase 2 步驟 2 QA-A 補強，2026-10-30，tests-only）。

判定器是『第二把尺』，它自己若鬆了，p02～p05 所有守衛一起鬆 —— 所以這裡用**手造的 HTML 片段**
釘正反例（不讀任何 production 卡面）。
"""
from __future__ import annotations

import html

import pytest

from tests import _p25_info_conservation as C


def _row(k: str, v: str) -> str:
    return (f'<span class="blk-fact-k">{html.escape(k)}</span>'
            f'<span class="blk-fact-v">{html.escape(v)}</span>')


def _card(face: list[tuple[str, str]], fold: list[tuple[str, str]] = ()) -> str:
    out = '<div class="blk">' + "".join(_row(k, v) for k, v in face)
    if fold:
        out += ('<input type="checkbox" class="blk-fold-i" id="fold-x">'
                '<div class="blk-fold">' + "".join(_row(k, v) for k, v in fold) + "</div>")
    return out + "</div>"


# ── misleading_face_problems ───────────────────────────────────────────────
@pytest.mark.parametrize("value", ["0", "０", "0.0", "0%", "中性", "正常", "續抱", "安全",
                                   "無異常", "沒問題", "穩定", "無風險", "０％"])
def test_whole_value_misleading_is_flagged(value):
    out = _card([("狀態", value)])
    assert C.misleading_face_problems(out, ["缺值的來源文字"]) != []


@pytest.mark.parametrize("sentence", [
    "目前讀數是０，沒有資料",           # 全形零
    "目前讀數是 0.0 沒有資料",          # 句中 0.0
    "目前讀數是 0.00% 沒有資料",
    "目前讀數是０．０ 沒有資料",        # 全形 0.0（NFKC 後 0.0）
    "這一檔無異常",
    "這一檔沒問題",
    "這一檔穩定",
    "這一檔無風險",
])
def test_sentence_level_misleading_is_flagged_when_source_has_none(sentence):
    out = _card([("說明", sentence)])
    assert C.misleading_face_problems(out, ["來源裡完全沒有這些字"]) != []


@pytest.mark.parametrize("sentence", [
    "代號 00878 殖利率 0.5%", "10 檔、30–50%", "更新於 00:00", "價格 10.0 元", "版本 0.0.1",
    "比例 0.05", "共 100 筆", "2330 收 600.0",
])
def test_ordinary_numbers_are_not_flagged(sentence):
    out = _card([("說明", sentence)])
    assert C.misleading_face_problems(out, ["來源"]) == []


def test_source_that_really_has_the_word_allows_the_same_count():
    """否定句裡的詞是合法的：來源有幾次，卡面就准有幾次；多一次就紅。"""
    src = ["本站不以「中性」代替未評估"]
    assert C.misleading_face_problems(_card([("為什麼", "不以「中性」代替未評估")]), src) == []
    assert C.misleading_face_problems(
        _card([("為什麼", "不以「中性」代替未評估，結論中性")]), src) != []


def test_own_value_whitelist_is_nfkc_aware():
    out = _card([("最後一次回了幾列", "０")])
    assert C.misleading_face_problems(out, ["最後一次回了幾列\n0"], own_values=["0"]) == []
    assert C.misleading_face_problems(out, ["x"], own_values=[]) != []


def test_fold_is_not_judged_as_face():
    out = _card([("現在", "尚無資料")], [("為什麼", "全文：目前讀數是 0.0，沒問題")])
    assert C.misleading_face_problems(out, ["x"]) == []


# ── split_face_fold 哨兵 ───────────────────────────────────────────────────
def test_sentinel_passes_a_normal_folded_card_and_a_card_without_fold():
    assert C.fold_sentinel_problems(_card([("a", "1")], [("a", "1 全文")])) == []
    assert C.fold_sentinel_problems(_card([("a", "1")])) == []


def test_sentinel_flags_a_toggle_without_a_fold_region():
    bad = '<div class="blk">' + _row("a", "1") + '<input type="checkbox" class="blk-fold-i" id="f">'
    assert C.fold_sentinel_problems(bad) != []


def test_sentinel_flags_a_fold_with_unreadable_rows():
    bad = ('<div class="blk"><input type="checkbox" class="blk-fold-i" id="f">'
           '<div class="blk-fold"><b>no rows</b></div></div>')
    assert C.fold_sentinel_problems(bad) != []


def test_split_face_fold_really_splits():
    face, fold = C.split_face_fold(_card([("a", "1")], [("b", "2")]))
    assert C.rows_of(face) == [("a", "1")] and C.rows_of(fold) == [("b", "2")]


# ── drop_note_rows 前提 ────────────────────────────────────────────────────
_KEYS = ("現在", "為什麼", "去哪補")


class _N:
    now, why, where = "NOW", "WHY", "WHERE"


def test_note_rows_lead_passes_when_note_comes_first():
    out = _card([("現在", "NOW"), ("為什麼", "WHY"), ("去哪補", "WHERE"), ("為什麼", "fact")])
    assert C.note_rows_lead_problems(out, _N, _KEYS) == []


def test_note_rows_lead_flags_a_fact_before_the_note_and_drop_would_misfire():
    """前提被打破的實例：fact 的標籤也叫『為什麼』且排在 Note 前 → `drop_note_rows` 會扣錯列，
    所以前提檢查必須先紅。"""
    out = _card([("為什麼", "fact"), ("現在", "NOW"), ("為什麼", "WHY"), ("去哪補", "WHERE")])
    assert C.note_rows_lead_problems(out, _N, _KEYS) != []
    left = C.drop_note_rows(C.face_rows(out), _N, _KEYS, str, exact=False)
    assert ("為什麼", "WHY") in left, "前提不成立時 drop_note_rows 確實會扣錯（這就是要守前提的理由）"


# ── face_order_problems ────────────────────────────────────────────────────
_FACTS = (("甲", "1"), ("乙", "2"), ("丙", "3"))


def test_order_ok_and_missing_fold_only_fact_is_ok():
    ok = _card([("現在", "NOW"), ("為什麼", "WHY"), ("去哪補", "WHERE"), ("甲", "1"), ("丙", "3")])
    assert C.face_order_problems(ok, _FACTS, note=_N, keys=_KEYS, plain=str) == []


def test_order_flags_swapped_facts():
    bad = _card([("現在", "NOW"), ("為什麼", "WHY"), ("去哪補", "WHERE"),
                 ("乙", "2"), ("甲", "1"), ("丙", "3")])
    assert C.face_order_problems(bad, _FACTS, note=_N, keys=_KEYS, plain=str) != []


def test_order_flags_a_fact_between_note_rows():
    bad = _card([("現在", "NOW"), ("甲", "1"), ("為什麼", "WHY"), ("去哪補", "WHERE"),
                 ("乙", "2"), ("丙", "3")])
    assert C.face_order_problems(bad, _FACTS, note=_N, keys=_KEYS, plain=str) != []


def test_order_is_not_tied_to_an_absolute_position():
    moved = _card([("甲", "1"), ("乙", "2"), ("現在", "NOW"), ("為什麼", "WHY"),
                   ("去哪補", "WHERE"), ("丙", "3")])
    assert C.face_order_problems(moved, _FACTS, note=_N, keys=_KEYS, plain=str) == []


def test_order_without_a_note_only_checks_facts():
    assert C.face_order_problems(_card([("甲", "1"), ("乙", "2")]), _FACTS, note=None,
                                 keys=_KEYS, plain=str) == []
    assert C.face_order_problems(_card([("乙", "2"), ("甲", "1")]), _FACTS, note=None,
                                 keys=_KEYS, plain=str) != []


# ── negation_on_face_problems ──────────────────────────────────────────────
class _N2:
    now, why, where = "尚未載入", "這不是故障，是還沒查", "請按載入"


def test_negation_kept_ok_dropped_red_and_unsourced_not_required():
    pins = [("為什麼", "這不是故障"), ("現在", "尚未載入"), ("去哪補", "不存在於原文的詞")]
    kept = _card([("現在", "尚未載入"), ("為什麼", "這不是故障"), ("去哪補", "請按載入")])
    probs, n = C.negation_on_face_problems(kept, _N2, pins, keys=_KEYS, plain=str)
    assert probs == [] and n == 2, "原文沒有的片語不得被要求（n 只算原文含的）"
    dropped = _card([("現在", "尚未載入"), ("為什麼", "是還沒查"), ("去哪補", "請按載入")])
    probs, n = C.negation_on_face_problems(dropped, _N2, pins, keys=_KEYS, plain=str)
    assert len(probs) == 1 and "這不是故障" in probs[0]


def test_negation_only_in_the_fold_does_not_count_as_on_the_face():
    out = _card([("現在", "尚未載入"), ("為什麼", "是還沒查"), ("去哪補", "請按載入")],
                [("為什麼", "這不是故障，是還沒查")])
    probs, _n = C.negation_on_face_problems(out, _N2, [("為什麼", "這不是故障")],
                                            keys=_KEYS, plain=str)
    assert probs != []


# ── escape ─────────────────────────────────────────────────────────────────
def test_escape_problems_flags_raw_html_and_passes_escaped():
    evil = '"><script>alert(1)</script>' + "x" * 50
    tricky = "a<b & c\"q\" 'r'"
    good = _card([("a", "1")], [(evil, evil), (tricky, tricky)])
    assert C.escape_problems(good, evil=evil, tricky=tricky) == []
    raw = good + "<script>alert(1)</script>"
    assert C.escape_problems(raw, evil=evil, tricky=tricky) != []
    unescaped = good.replace(html.escape(tricky), tricky)
    assert C.escape_problems(unescaped, evil=evil, tricky=tricky) != []
    swallowed = _card([("a", "1")], [(tricky, tricky)])
    assert C.escape_problems(swallowed, evil=evil, tricky=tricky) != []
