"""Phase 2 步驟 1 守衛：共用層「可選參數」——預設輸出逐 byte 不變，新參數行為受測。

對應 `docs/vnext/PRESENTATION_MIGRATION_PLAN_2026-10-29.md` §4 步驟 1／§6 M5·M6·M13。

三個被加參數的函式：
  · `src/ui_v2/markup.py::card_html`            （chips／summary／fold_label／spark）
  · `src/ui/views/_ui_kit.py::single_submit_form`（options_label）
  · `src/ui/views/_ui_kit.py::render_card`       （compact）

═══ 第 A 部：golden（預設輸出不變）═══
GOLDEN_* 的 sha256（card_html 矩陣 1950 組、form 13 組、render_card 135 組）是在**修改任何 src 之前**，對當時的 main（e552f12）實測得到、
再貼進本檔，⛔ 不是改完才產生。矩陣由本檔 `_card_html_matrix()` 等函式窮舉
（含會 raise 的組合——raise 的型別與訊息也納入摘要），任何 1 byte 的預設輸出漂移
都會讓對應 digest 紅（M5）。

═══ 第 B 部：新參數行為 ═══
Fail Loud、Missing 不補 0、chips 不經訊號文字頻道、fold_label 呼叫時解析、
spark 空字串 raise、compact 下 Note 三段全在、預設收合。

注意：截至本檔，沒有任何 production caller 使用新參數（Phase 2 步驟 1 僅加參數）。
"""
from __future__ import annotations

import hashlib
import itertools
import json
from contextlib import contextmanager

import pytest

from shared.ui_state import (
    UI_DEGRADED, UI_EMPTY, UI_FAILED, UI_IDLE, UI_LIVE, UI_UNWIRED,
)
from src.ui.tabs.tab_today import Card, Note
from src.ui.views import _ui_kit
from src.ui_v2 import markup


def _sha(obj: object) -> str:
    return hashlib.sha256(
        json.dumps(obj, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


# ══════════════════════════════════════════════════════════════════
# 矩陣 1：card_html
# ══════════════════════════════════════════════════════════════════
_LONG = "長" * 120      # 超過 FACT_VALUE_MAX_CHARS，觸發截斷＋title
_NASTY = 'a<b>&"c\''    # 需 escape
_BLOCKS = ("today.verdict", "find.screen_result", "hold.scales",
           "inspect.kind", "today.detail", "hold.deep.var")
_STATES = ("live", "degraded", "failed", "idle", "empty", "unwired", "partial")
_FACTS = (
    (),
    (("門檻帶", "0.5～1.0"),),
    (("a", _LONG), ("b", _NASTY), ("c", "")),
)
_FOLDED = (
    (),
    (("口徑", "x"),),
    (("完整", _LONG), ("引號", _NASTY)),
)


def _card_html_matrix() -> list[tuple[str, str]]:
    """(組合描述, 輸出或 `RAISE:<Type>:<msg>`)。"""
    out: list[tuple[str, str]] = []
    badge_ns = (1, 5, 10, 11, 99)
    for (blk, st_, f, ff, trunc, bn) in itertools.product(
            _BLOCKS, _STATES, _FACTS, _FOLDED, (True, False), badge_ns):
        # 只在 live 組合展開 facts／folded／truncate／badge 全交叉；
        # 其餘狀態抽樣，避免矩陣膨脹但仍覆蓋各態分支。
        if st_ != "live" and not (f is _FACTS[1] and bn == 1 and trunc):
            continue
        for value, level in ((None, None), ("52.3", "偏多"), ("0", "")):
            fold_id = "fold-x-1" if ff else None
            desc = f"{blk}|{st_}|{len(f)}|{len(ff)}|{trunc}|{bn}|{value}|{level}"
            try:
                html_ = markup.card_html(
                    block=blk, state=st_, title=_NASTY if bn == 5 else "標題",
                    value=value, level=level, badge_n=bn,
                    facts=f, folded_facts=ff, fold_id=fold_id,
                    fold_truncate=trunc)
            except Exception as e:  # noqa: BLE001 — golden 要記錄 raise 的樣子
                html_ = f"RAISE:{type(e).__name__}:{e}"
            out.append((desc, html_))
    # 錯誤路徑：有摺疊列卻沒 fold_id／fold_id 非法、未知 block／state
    for fid in (None, "Bad_ID", "ok-id"):
        try:
            r = markup.card_html(block="today.verdict", state="live",
                                 title="t", badge_n=1,
                                 folded_facts=(("k", "v"),), fold_id=fid)
        except Exception as e:  # noqa: BLE001
            r = f"RAISE:{type(e).__name__}:{e}"
        out.append((f"fold_id={fid}", r))
    for blk, stt in (("nope.block", "live"), ("today.verdict", "bogus")):
        try:
            r = markup.card_html(block=blk, state=stt, title="t", badge_n=1)
        except Exception as e:  # noqa: BLE001
            r = f"RAISE:{type(e).__name__}:{e}"
        out.append((f"{blk}|{stt}", r))
    # facts／folded 給 generator（Iterable 契約）
    out.append(("gen", markup.card_html(
        block="today.verdict", state="live", title="t", badge_n=1,
        facts=(x for x in (("k", "v"),)),
        folded_facts=(x for x in (("k2", "v2"),)), fold_id="fold-g")))
    return out


# ══════════════════════════════════════════════════════════════════
# FakeST：記錄 `_ui_kit` 對 streamlit 的呼叫序列
# ══════════════════════════════════════════════════════════════════
class _Ctx:
    def __init__(self, fake: "FakeST", name: str, args: tuple, kw: dict):
        self._f, self._n, self._a, self._k = fake, name, args, kw

    def __enter__(self):
        self._f.log.append(("enter", self._n, _norm(self._a), _norm(self._k)))
        return self

    def __exit__(self, *exc):
        self._f.log.append(("exit", self._n))
        return False


def _norm(x: object) -> object:
    if callable(x):
        return "<callable>"
    if isinstance(x, dict):
        return {str(k): _norm(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_norm(v) for v in x]
    return x if isinstance(x, (str, int, float, bool, type(None))) else repr(x)


class FakeST:
    def __init__(self, submit: bool = False):
        self.log: list = []
        self.session_state: dict = {}
        self._submit = submit

    def _rec(self, name, args, kw):
        self.log.append((name, _norm(args), _norm(kw)))

    def markdown(self, *a, **k):
        self._rec("markdown", a, k)

    def caption(self, *a, **k):
        self._rec("caption", a, k)

    def radio(self, *a, **k):
        # 把 format_func 實際套在每個 option 上，納入 digest
        fn = k.get("format_func")
        labels = [fn(o) for o in k.get("options", [])] if fn else None
        self._rec("radio", a, {**k, "_formatted": labels})
        return (k.get("options") or [None])[0]

    def form_submit_button(self, *a, **k):
        self._rec("form_submit_button", a, k)
        return self._submit

    def form(self, *a, **k):
        return _Ctx(self, "form", a, k)

    def expander(self, *a, **k):
        return _Ctx(self, "expander", a, k)

    def columns(self, *a, **k):  # pragma: no cover — 本矩陣不走
        raise AssertionError("columns 不該被呼叫")


@contextmanager
def _fake_st(submit: bool = False):
    fake = FakeST(submit)
    old = _ui_kit.st
    _ui_kit.st = fake
    try:
        yield fake
    finally:
        _ui_kit.st = old


# ══════════════════════════════════════════════════════════════════
# 矩陣 2：single_submit_form
# ══════════════════════════════════════════════════════════════════
def _form_matrix() -> list:
    out = []
    labels = {"a": "甲", "b": "乙"}
    for submit, opts in itertools.product((False, True), (("a", "b"), ("a",), ())):
        for pre in (None, "b"):
            with _fake_st(submit) as fk:
                if pre:
                    fk.session_state["w"] = pre
                try:
                    ret = _ui_kit.single_submit_form(
                        "fk", submit_label="送出", radio_label="模式",
                        options=opts, option_labels=labels,
                        widget_key="w", applied_key="ap")
                    res = ("ret", ret)
                except Exception as e:  # noqa: BLE001
                    res = ("RAISE", type(e).__name__, str(e))
            out.append([submit, list(opts), pre, res, fk.log, fk.session_state])
    # options 缺 label
    with _fake_st() as fk:
        try:
            _ui_kit.single_submit_form(
                "fk", submit_label="s", radio_label="r", options=("a", "z"),
                option_labels=labels, widget_key="w", applied_key="ap")
            res = "noraise"
        except Exception as e:  # noqa: BLE001
            res = f"{type(e).__name__}:{e}"
    out.append(["missing-label", res, fk.log])
    return out


# ══════════════════════════════════════════════════════════════════
# 矩陣 3：render_card
# ══════════════════════════════════════════════════════════════════
def _cards() -> list[Card]:
    note = Note(now="現況一句話", why="為什麼沒有", where="去哪補")
    return [
        Card(key="k.live", label="標籤", state=UI_LIVE, value="52.3"),
        Card(key="k.live_nov", label="標籤", state=UI_LIVE),
        Card(key="k.live_note", label="標<籤>&", state=UI_LIVE, value="", note=note),
        Card(key="k.live_val_note", label="標籤", state=UI_LIVE, value="9", note=note),
        Card(key="k.failed", label="標籤", state=UI_FAILED, note=note),
        Card(key="k.idle", label="標籤", state=UI_IDLE, note=note),
        Card(key="k.empty", label="標籤", state=UI_EMPTY, note=note),
        Card(key="k.unwired", label="標籤", state=UI_UNWIRED, note=note),
        Card(key="k.degraded", label="標籤", state=UI_DEGRADED, note=note),
    ]


def _render_card_matrix() -> list:
    out = []
    facts_opts = ((), (("門檻帶", "0.5"),), (("a", "b"), ("c", _LONG)))
    sig_opts = (("", ""), ("偏多", ""), ("偏多", "#112233"), ("🔴 紅", ""), ("🟢", "#fff"))
    for card, facts, (sig, col) in itertools.product(_cards(), facts_opts, sig_opts):
        with _fake_st() as fk:
            try:
                _ui_kit.render_card(card, signal_text=sig, signal_color=col,
                                    facts=facts)
                res = "ok"
            except Exception as e:  # noqa: BLE001
                res = f"{type(e).__name__}:{e}"
        out.append([card.key, list(facts), sig, col, res, fk.log])
    return out


# ══════════════════════════════════════════════════════════════════
# 第 A 部：golden（修改前實測）
# ══════════════════════════════════════════════════════════════════
GOLDEN_CARD_HTML = "c9122edcd72e45b1c94a1451333646c9185f5dd1e59f8905f9ac8dcab82949e3"
GOLDEN_FORM = "049e0f80d4d18077ee133246a5d18330ab8c95c5ccb4412f5afbddfeeff3d3a7"
GOLDEN_RENDER_CARD = "95e22e684afb543738db53600b9537165e1f8ef4f441193464db8a1416221557"


class TestGoldenDefaultOutputUnchanged:
    """M5：新參數（就算沒人用）若讓預設輸出變 1 byte，這裡必紅。"""

    def test_matrix_sizes_are_not_trivially_small(self):
        # 等於修改前實測的實際組數（不是下限）：矩陣被悄悄縮小＝golden 變鬆。
        assert len(_card_html_matrix()) == 1950
        assert len(_form_matrix()) == 13
        assert len(_render_card_matrix()) == 135

    def test_card_html_default_output_golden(self):
        assert _sha(_card_html_matrix()) == GOLDEN_CARD_HTML

    def test_single_submit_form_default_calls_golden(self):
        assert _sha(_form_matrix()) == GOLDEN_FORM

    def test_render_card_default_calls_golden(self):
        assert _sha(_render_card_matrix()) == GOLDEN_RENDER_CARD


# ══════════════════════════════════════════════════════════════════
# 第 B 部：新參數行為
# ══════════════════════════════════════════════════════════════════
def _card(**kw):
    base = dict(block="today.verdict", state="live", title="標題",
                value="52.3", level="偏多", badge_n=1)
    base.update(kw)
    return markup.card_html(**base)


class TestCardHtmlChips:
    def test_default_has_no_chip_row(self):
        h = _card()
        assert "blk-chips" not in h and "blk-chip" not in h

    def test_empty_sequences_equal_default(self):
        assert _card(chips=()) == _card() == _card(chips=[])

    def test_chips_rendered_after_header_before_value_and_facts(self):
        h = _card(chips=["🕒 資料 10/28", "來源 TWSE"], facts=(("k", "v"),))
        assert h.count('<span class="blk-chip">') == 2
        i_head = h.index('<div class="blk-head">')
        i_chips = h.index('<div class="blk-chips">')
        i_val = h.index('<div class="blk-val">')
        i_facts = h.index('<div class="blk-facts">')
        assert i_head < i_chips < i_val < i_facts

    def test_chip_text_is_escaped(self):
        h = _card(chips=['<b>x</b>&"'])
        assert "<b>x</b>" not in h
        assert "&lt;b&gt;x&lt;/b&gt;&amp;&quot;" in h

    @pytest.mark.parametrize("bad", [
        [""], ["   "], [None], [1], ["ok", ""], "abc", b"x",
        [b"x"], (b"a", b"b"),              # bytes 序列：元素非 str
        None,                               # chips=None（不得當成「沒給」）
        {"a": 1}, {"a": "x"},               # dict／Mapping：迭代只得 key，語意含糊
    ])
    def test_bad_chips_raise_value_error_not_dropped(self, bad):
        with pytest.raises(ValueError):
            _card(chips=bad)

    def test_chips_do_not_go_through_signal_text_channel(self):
        # ⬜／⚠／🔴 在訊號文字頻道會被 assert_signal_text_clean 拒；chip 是獨立通道。
        glyph_chips = ["⬜ 資料日未提供", "⚠ 過期 3 天", "🔴 取得失敗"]
        # 訊號頻道至少會拒其中被禁的 glyph（🔴 必拒；是否拒 ⬜／⚠ 取決於 L0 SSOT 現況）。
        with pytest.raises(ValueError):
            _ui_kit.assert_signal_text_clean("t", glyph_chips[2])
        # 2026-10-30 實測釘住現況：⬜ 進訊號文字會 raise；⚠ 目前不 raise。
        # ⚠️ 這是「現況」不是「承諾」——L0 SSOT（UI_STATE_META glyph ∪ LEVEL_EMOJI）日後若
        # 把 ⚠ 加進禁表，本斷言會紅，屆時改斷言即可；chip 獨立通道的理由是語意，不是靠 ValueError。
        with pytest.raises(ValueError):
            _ui_kit.assert_signal_text_clean("t", glyph_chips[0])
        _ui_kit.assert_signal_text_clean("t", glyph_chips[1])   # 目前不 raise
        h = _card(chips=glyph_chips)     # 不 raise
        assert all(c in h for c in glyph_chips)

    def test_chips_do_not_leak_into_title_attributes(self):
        assert "title=" not in _card(chips=["來源 TWSE"])

    def test_missing_value_stays_blank_not_zero_with_new_params(self):
        h = _card(state="failed", value="0", level="x", chips=["⬜ 尚未載入"],
                  summary="一句話")
        assert "blk-val" not in h and "blk-lvl" not in h
        h2 = _card(value=None, level=None, chips=["c"], summary="s", spark="<svg/>")
        assert "blk-val" not in h2 and ">0<" not in h2


class TestCardHtmlSummary:
    def test_default_none_no_row(self):
        assert "blk-summary" not in _card()

    def test_summary_row_escaped(self):
        h = _card(summary="<i>一句</i>")
        assert '<div class="blk-summary">&lt;i&gt;一句&lt;/i&gt;</div>' in h

    @pytest.mark.parametrize("bad", ["", "  ", 1, b"x"])
    def test_bad_summary_raises(self, bad):
        with pytest.raises(ValueError):
            _card(summary=bad)


class TestCardHtmlFoldLabel:
    FOLDED = dict(folded_facts=(("k", "v"),), fold_id="fold-t")

    def test_none_uses_default_text(self):
        assert f'>{markup.FOLD_SUMMARY_TEXT}</label>' in _card(**self.FOLDED)
        assert _card(fold_label=None, **self.FOLDED) == _card(**self.FOLDED)

    def test_label_resolved_at_call_time_not_def_time(self, monkeypatch):
        monkeypatch.setattr(markup, "FOLD_SUMMARY_TEXT", "▸ 測試字")
        h = _card(**self.FOLDED)
        assert ">▸ 測試字</label>" in h and "▸ 詳細" not in h

    def test_custom_label_replaces_and_is_escaped(self):
        h = _card(fold_label="<展開>", **self.FOLDED)
        assert ">&lt;展開&gt;</label>" in h and "▸ 詳細" not in h

    def test_empty_label_falls_back_to_default(self):
        assert _card(fold_label="", **self.FOLDED) == _card(**self.FOLDED)

    @pytest.mark.parametrize("bad", [" ", "   ", "\t", "\n", " \u3000 "])
    def test_whitespace_only_label_raises(self, bad):
        # 空字串 "" ＝ 視同未給；全空白 ＝ 給了看不見的字 ⇒ Fail Loud（兩者刻意不同）。
        with pytest.raises(ValueError):
            _card(fold_label=bad, **self.FOLDED)
        with pytest.raises(ValueError):          # 沒有 folded_facts 時同樣檢查（一致）
            _card(fold_label=bad)

    def test_non_str_label_raises(self):
        with pytest.raises(ValueError):
            _card(fold_label=3, **self.FOLDED)

    def test_no_fold_no_effect(self):
        assert _card(fold_label="x") == _card()


class TestCardHtmlSpark:
    def test_default_none_no_spark(self):
        assert "blk-spark" not in _card()

    def test_trusted_html_not_escaped(self):
        h = _card(spark='<svg viewBox="0 0 1 1"></svg>')
        assert '<div class="blk-spark"><svg viewBox="0 0 1 1"></svg></div>' in h

    @pytest.mark.parametrize("bad", ["", "   ", 0, b"x"])
    def test_empty_or_non_str_spark_raises(self, bad):
        with pytest.raises(ValueError):
            _card(spark=bad)


_H_HEAD = ('<div class="blk blk-t1"><div class="blk-head"><span class="blk-title">標題</span>'
           '<span class="bdg bdg-1 sb-b1"><span aria-hidden="true">🟢</span><span>運作中</span></span></div>')
_H_VAL = '<div class="blk-val">52.3</div><div class="blk-lvl">偏多</div>'


class TestNonDefaultOutputByteGolden:
    """非預設輸出的 byte 級 golden：整串 `==`（不是 in／index），
    使「chips 列 div 後多空白」「順序換位」這類 mutation 必紅。"""

    def test_chips_only(self):
        assert _card(chips=["a", "<b>"]) == (
            _H_HEAD
            + '<div class="blk-chips"><span class="blk-chip">a</span>'
              '<span class="blk-chip">&lt;b&gt;</span></div>'
            + _H_VAL + '</div>')

    def test_summary_only(self):
        assert _card(summary="一句") == (
            _H_HEAD + '<div class="blk-summary">一句</div>' + _H_VAL + '</div>')

    def test_spark_only(self):
        assert _card(spark="<svg/>") == (
            _H_HEAD + _H_VAL + '<div class="blk-spark"><svg/></div></div>')

    def test_fold_label_only(self):
        assert _card(folded_facts=(("k", "v"),), fold_id="fold-t", fold_label="開") == (
            '<div class="blk blk-t1"><div class="blk-head"><span class="blk-title" id="fold-t_t">標題</span>'
            '<span class="bdg bdg-1 sb-b1"><span aria-hidden="true">🟢</span><span>運作中</span></span></div>'
            + _H_VAL
            + '<div class="blk-fold"><input type="checkbox" class="blk-fold-i" id="fold-t"'
              ' aria-labelledby="fold-t_s fold-t_t" aria-controls="fold-t_b">'
              '<label class="blk-fold-s" id="fold-t_s" for="fold-t">開</label>'
              '<div class="blk-fold-b" id="fold-t_b"><div class="blk-facts"><div class="blk-fact">'
              '<span class="blk-fact-k">k</span><span class="blk-fact-v">v</span></div></div></div></div></div>')

    def test_all_combined(self):
        assert _card(chips=["a", "b"], summary="s", spark="<svg/>",
                     folded_facts=(("k", "v"),), fold_id="fold-t", fold_label="開") == (
            '<div class="blk blk-t1"><div class="blk-head"><span class="blk-title" id="fold-t_t">標題</span>'
            '<span class="bdg bdg-1 sb-b1"><span aria-hidden="true">🟢</span><span>運作中</span></span></div>'
            '<div class="blk-chips"><span class="blk-chip">a</span><span class="blk-chip">b</span></div>'
            '<div class="blk-summary">s</div>'
            + _H_VAL
            + '<div class="blk-spark"><svg/></div>'
              '<div class="blk-fold"><input type="checkbox" class="blk-fold-i" id="fold-t"'
              ' aria-labelledby="fold-t_s fold-t_t" aria-controls="fold-t_b">'
              '<label class="blk-fold-s" id="fold-t_s" for="fold-t">開</label>'
              '<div class="blk-fold-b" id="fold-t_b"><div class="blk-facts"><div class="blk-fact">'
              '<span class="blk-fact-k">k</span><span class="blk-fact-v">v</span></div></div></div></div></div>')


class TestFoldStaysCollapsedAndComplete:
    """M6／M13 的 card_html 側守衛（既有 test_lamp_card_fold 之外的第二道）。"""

    def test_fold_checkbox_never_checked_by_default(self):
        h = _card(folded_facts=(("k", "v"),), fold_id="fold-a", chips=["c"],
                  summary="s", spark="<svg/>", fold_label="詳")
        assert "checked" not in h.split('class="blk-fold"', 1)[1]
        assert "open" not in h.split('class="blk-fold"', 1)[1].split("<input", 1)[0]

    def test_full_text_is_in_fold_body_not_only_in_title_attr(self):
        long = "全文" * 60
        h = _card(folded_facts=(("口徑", long),), fold_id="fold-b",
                  fold_truncate=False)
        body = h.split('class="blk-fold-b"', 1)[1]
        # 去掉所有 title="..." 之後，全文仍在
        import re
        assert long in re.sub(r'title="[^"]*"', "", body)

    def test_truncated_fold_keeps_original_in_hover_only_as_before(self):
        long = "全" * 100
        h = _card(folded_facts=(("口徑", long),), fold_id="fold-c")
        assert f'title="{long}"' in h


class TestSingleSubmitFormOptionsLabel:
    KW = dict(submit_label="送出", radio_label="模式", options=("a", "b"),
              option_labels={"a": "甲", "b": "乙"}, widget_key="w", applied_key="ap")

    def test_default_has_no_expander(self):
        with _fake_st() as fk:
            _ui_kit.single_submit_form("f", **self.KW)
        assert not [c for c in fk.log if c[1] == "expander"]

    def test_none_same_calls_as_omitted(self):
        with _fake_st() as a:
            _ui_kit.single_submit_form("f", **self.KW)
        with _fake_st() as b:
            _ui_kit.single_submit_form("f", options_label=None, **self.KW)
        assert a.log == b.log

    def test_label_wraps_radio_in_collapsed_expander_inside_form(self):
        with _fake_st() as fk:
            _ui_kit.single_submit_form("f", options_label="更多選項", **self.KW)
        names = [(c[0], c[1]) for c in fk.log]
        i_form = names.index(("enter", "form"))
        i_exp = names.index(("enter", "expander"))
        i_exp_end = names.index(("exit", "expander"))
        i_radio = [i for i, c in enumerate(fk.log) if c[0] == "radio"][0]
        i_submit = [i for i, c in enumerate(fk.log) if c[0] == "form_submit_button"][0]
        assert i_form < i_exp < i_radio < i_exp_end < i_submit
        exp = fk.log[i_exp]
        assert exp[2] == ["更多選項"] and exp[3] == {"expanded": False}
        assert sum(1 for c in fk.log if c[0] == "form_submit_button") == 1

    @pytest.mark.parametrize("bad", ["", "  ", 3])
    def test_bad_label_raises(self, bad):
        with _fake_st():
            with pytest.raises(ValueError):
                _ui_kit.single_submit_form("f", options_label=bad, **self.KW)

    def test_real_streamlit_form_expander_works_and_value_submits(self):
        """AppTest 實證：目前 requirements 的 streamlit 下 form 內 expander 可用。"""
        from streamlit.testing.v1 import AppTest

        def app():
            import streamlit as st
            from src.ui.views import _ui_kit as k
            sub = k.single_submit_form(
                "f", submit_label="送出", radio_label="模式", options=("a", "b"),
                option_labels={"a": "甲", "b": "乙"}, widget_key="w",
                applied_key="ap", options_label="更多選項")
            st.write("SUB" if sub else "IDLE")

        at = AppTest.from_function(app).run()
        assert not at.exception
        assert [e.label for e in at.expander] == ["更多選項"]
        at.radio[0].set_value("b")
        at.button[0].click().run()
        assert not at.exception
        assert at.session_state["ap"] == {"mode": "b"}


def _note():
    return Note(now="現況一句話", why="為什麼沒有", where="去哪補")


class TestRenderCardCompact:
    def test_default_false_equals_omitted(self):
        c = Card(key="k", label="L", state=UI_FAILED, note=_note())
        with _fake_st() as a:
            _ui_kit.render_card(c, facts=(("a", "b"),))
        with _fake_st() as b:
            _ui_kit.render_card(c, facts=(("a", "b"),), compact=False)
        assert a.log == b.log
        assert not [x for x in a.log if x[1] == "expander"]

    def test_compact_moves_facts_and_all_three_note_parts_into_collapsed_expander(self):
        c = Card(key="k", label="L", state=UI_FAILED, note=_note())
        with _fake_st() as fk:
            _ui_kit.render_card(c, facts=(("門檻", "0.5"),), compact=True)
        log = fk.log
        i_in = [i for i, x in enumerate(log) if x[:2] == ("enter", "expander")][0]
        i_out = [i for i, x in enumerate(log) if x[:2] == ("exit", "expander")][0]
        assert log[i_in][2] == [markup.FOLD_SUMMARY_TEXT]
        assert log[i_in][3] == {"expanded": False}
        inside = json.dumps(log[i_in + 1:i_out], ensure_ascii=False)
        for part in ("現況一句話", "為什麼沒有", "去哪補", "門檻"):
            assert part in inside
        outside = json.dumps(log[:i_in] + log[i_out + 1:], ensure_ascii=False)
        for part in ("現況一句話", "為什麼沒有", "去哪補", "門檻"):
            assert part not in outside
        # 卡面（標題）仍在 expander 之外
        assert "L" in outside

    def test_compact_live_note_not_dropped(self):
        c = Card(key="k", label="L", state=UI_LIVE, value="", note=_note())
        with _fake_st() as fk:
            _ui_kit.render_card(c, compact=True)
        flat = json.dumps(fk.log, ensure_ascii=False)
        assert all(p in flat for p in ("現況一句話", "為什麼沒有", "去哪補"))

    def test_compact_without_facts_or_note_opens_no_expander(self):
        c = Card(key="k", label="L", state=UI_LIVE, value="1")
        with _fake_st() as fk:
            _ui_kit.render_card(c, compact=True)
        assert not [x for x in fk.log if x[1] == "expander"]

    def test_collision_guard_still_runs_under_compact(self):
        c = Card(key="k", label="L", state=UI_LIVE, value="1")
        with _fake_st():
            with pytest.raises(ValueError):
                _ui_kit.render_card(c, signal_text="🔴 紅", compact=True)

    def test_label_resolved_at_call_time(self, monkeypatch):
        monkeypatch.setattr(markup, "FOLD_SUMMARY_TEXT", "▸ 另一個字")
        c = Card(key="k", label="L", state=UI_FAILED, note=_note())
        with _fake_st() as fk:
            _ui_kit.render_card(c, compact=True)
        ex = [x for x in fk.log if x[:2] == ("enter", "expander")][0]
        assert ex[2] == ["▸ 另一個字"]

    def test_docstring_keeps_degraded_rule_keywords(self):
        d = _ui_kit.render_card.__doc__
        for kw in ("degraded", "觀測", "判決", "留白", "未評估 ≠ 綠", "compact"):
            assert kw in d

    def test_real_streamlit_compact_expander_collapsed(self):
        from streamlit.testing.v1 import AppTest

        def app():
            from shared.ui_state import UI_FAILED
            from src.ui.tabs.tab_today import Card, Note
            from src.ui.views import _ui_kit as k
            k.render_card(Card(key="k", label="L", state=UI_FAILED,
                               note=Note(now="現況X", why="為何Y", where="去哪Z")),
                          facts=(("門檻", "0.5"),), compact=True)

        at = AppTest.from_function(app).run()
        assert not at.exception
        assert len(at.expander) == 1
        assert at.expander[0].proto.expanded is False
        flat = " ".join(m.value for m in at.expander[0].markdown) + " ".join(
            c.value for c in at.expander[0].caption)
        assert "現況X" in flat and "為何Y" in flat and "去哪Z" in flat and "門檻" in flat
