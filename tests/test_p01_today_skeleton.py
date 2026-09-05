"""tests/test_p01_today_skeleton.py — 🚦 今天（五頁 IA 第 1 頁）骨架守衛。

規格：`docs/wireframes/stock_ia_v1.html` 的 `PAGES[0]`（客戶 2026-09-05 拍板）。

═══ 粒度：**一張卡就是一個測試** ══════════════════════════════════════
四態與三要素掛在 `Card` 上，本檔的參數化也以**卡**為單位 ——
所以「只弄壞其中一張卡」會有**且只有**那一條轉紅，鄰居全綠。

⚠️ 這是本檔存在的主要理由。以「一級標題」或「整個區塊」為單位的守衛，
在同一段裡只要還有別的卡是誠實的，壞掉的那張就會被替它通過。

═══ 本檔**守不到**什麼（據實揭露，不要當成「已經守住了」）═══════════
兩個維度目前擋不住，兩者都已登記在姊妹 repo `my-Fund-dashboard` 的憲法
（`P-GREYSCENARIO-1` / `P-WHERECONTENT-1`），**台股端同樣適用**：

1. **情境維**：斷言只覆蓋「契約全有」「契約全無」兩個 session 端點，
   中間那些半有半無的組合沒有窮舉。
2. **語意維**：只驗「這個符號在不在」「三要素是不是非空」，
   **不驗那句話講的是不是真的** —— 例如 `where` 指向的分區是否真的
   存在於畫面上、`why` 說的原因是否真的是那個原因，本檔一概驗不到。
3. **欄數只擋字面值**：`test_no_literal_columns_above_three` 掃的是
   `st.columns(4)` 這種寫法；`st.columns(n)` 以變數傳欄數的**掃不到**。
   本檔改守 `_grid` 的 `per_row` 預設值當第二道，但那只覆蓋走 `_grid` 的
   路徑 —— 有人繞過 `_grid` 直接開欄，兩道都攔不住。
4. **docstring 放行**：SSOT 手抄守衛刻意跳過 docstring（它不渲染），
   所以 docstring 裡引用的分頁名／按鈕名一樣會過期，本檔驗不到。

**不宣稱本頁的誠實呈現已經被守住。**
"""
from __future__ import annotations

import ast
import pathlib

import pytest

from shared import ia_nav
from shared.ui_state import UI_LIVE, UI_STATES, UI_UNWIRED
from src.ui.tabs import tab_today as T

_REPO = pathlib.Path(__file__).resolve().parent.parent
_VIEW = _REPO / "src" / "ui" / "tabs" / "tab_today.py"
_WIREFRAME = _REPO / "docs" / "wireframes" / "stock_ia_v1.html"


def _all_cards():
    """本頁在**冷啟動**（契約全無）下的每一張卡。"""
    for _b in T.build_today_blocks():
        for _c in _b.cards:
            yield _b, _c


_CARDS = list(_all_cards())
_CARD_IDS = [f"{_b.key}::{_c.key}" for _b, _c in _CARDS]


# ══════════════════════════════════════════════════════════════════
# A. 逐卡守衛 —— 一張卡一條測試
# ══════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("block,card", _CARDS, ids=_CARD_IDS)
class TestEachCardIsHonest:

    def test_state_is_a_known_ui_state(self, block, card):
        assert card.state in UI_STATES, (
            f"{card.key} 的狀態 {card.state!r} 不在 L0 SSOT 的七態裡 —— "
            "本頁不得自創狀態名")

    def test_non_live_card_carries_all_three_elements(self, block, card):
        if card.state == UI_LIVE:
            pytest.skip("正常態給結論，不需要三要素")
        assert card.note is not None, f"{card.key} 非正常態卻沒有 Note"
        for _f in ("now", "why", "where"):
            assert str(getattr(card.note, _f)).strip(), (
                f"{card.key} 的 Note.{_f} 是空的 —— 鐵律 4 三要素缺一不可")

    def test_only_live_card_may_state_a_conclusion(self, block, card):
        if card.state == UI_LIVE:
            return
        assert not card.value, (
            f"{card.key} 不是正常態卻帶了結論文字 {card.value!r} —— "
            "線框 §02：只有正常態能給結論文字")

    def test_unwired_card_does_not_promise_a_user_action(self, block, card):
        """未接線態**沒有使用者可執行的出口**（線框葉2 unwired 原文）。

        給一句「按更新就好」是說謊：本頁根本沒有那塊的取數程式碼，
        按一百次也不會變。
        """
        if card.state != UI_UNWIRED:
            pytest.skip("只約束未接線態")
        assert "沒有你可以執行的出口" in card.note.where, (
            f"{card.key} 是未接線態，`where` 卻沒有寫明「沒有可執行的出口」")


# ══════════════════════════════════════════════════════════════════
# B. 區塊清單對得上線框
# ══════════════════════════════════════════════════════════════════
class TestBlocksMatchWireframe:

    def test_wireframe_file_exists(self):
        assert _WIREFRAME.exists(), (
            "線框不在 repo 裡 —— 本頁的規格來源不見了，"
            "後面幾條對照就沒有意義")

    def test_seven_blocks_two_leaves(self):
        _bs = T.build_today_blocks()
        assert len(_bs) == 7, (
            f"線框 PAGES[0].blocks 是 7 塊，本頁做了 {len(_bs)} 塊")
        assert {_b.leaf for _b in _bs} == {T.LEAF_CONCLUSION, T.LEAF_DETAIL}, (
            "線框 leaves 是 2 葉（今日結論 / 指標明細）")

    def test_seven_detail_segments_are_quoted_from_the_wireframe(self):
        """葉2 七段的段名必須逐字出現在線框裡。

        線框改段名 → 這條轉紅。這是本檔唯一一條真的把規格與實作綁在一起的
        斷言（其餘都只驗結構）。
        """
        _text = _WIREFRAME.read_text(encoding="utf-8")
        for _k, _label in T.DETAIL_SEGMENTS:
            assert _label in _text, (
                f"葉2 段名 {_label!r} 在線框裡找不到 —— "
                "要嘛抄錯，要嘛線框改了而本頁沒跟上")

    def test_submit_label_is_quoted_from_the_wireframe(self):
        _text = _WIREFRAME.read_text(encoding="utf-8")
        _label = ia_nav.action_label(ia_nav.ACTION_UPDATE_TODAY)
        assert _label in _text, (
            f"submit 名稱 {_label!r} 在線框裡找不到")


# ══════════════════════════════════════════════════════════════════
# C. 鐵律 1：3 欄自適應網格
# ══════════════════════════════════════════════════════════════════
class TestThreeColumnGrid:

    def test_grid_default_is_three(self):
        import inspect
        _p = inspect.signature(T._grid).parameters["per_row"]
        assert _p.default == 3, "鐵律 1：一列上限 3 欄"

    def test_no_literal_columns_above_three(self):
        """AST 掃本檔：不得出現 `st.columns(n)` 且 n > 3 的字面寫法。"""
        _tree = ast.parse(_VIEW.read_text(encoding="utf-8"))
        for _n in ast.walk(_tree):
            if (isinstance(_n, ast.Call)
                    and isinstance(_n.func, ast.Attribute)
                    and _n.func.attr == "columns"
                    and _n.args
                    and isinstance(_n.args[0], ast.Constant)
                    and isinstance(_n.args[0].value, int)):
                assert _n.args[0].value <= 3, (
                    f"{_VIEW.name}:{_n.lineno} 用了 {_n.args[0].value} 欄 —— "
                    "鐵律 1：格子多於 3 個要換行排第二排，不是加欄")


# ══════════════════════════════════════════════════════════════════
# D. 鐵律 2：Form 封裝 —— 當下值 / 已套用值分家
# ══════════════════════════════════════════════════════════════════
def _func_node(name: str) -> ast.FunctionDef:
    _tree = ast.parse(_VIEW.read_text(encoding="utf-8"))
    for _n in ast.walk(_tree):
        if isinstance(_n, ast.FunctionDef) and _n.name == name:
            return _n
    raise AssertionError(f"{_VIEW.name} 裡找不到函式 {name!r}")


class TestFormEncapsulation:

    def test_form_body_has_exactly_one_submit_and_no_button(self):
        """線框 F11：form 內放 `st.button` 實跑即拋 `StreamlitAPIException`。"""
        _fn = _func_node("_render_update_form")
        _with = [_n for _n in ast.walk(_fn) if isinstance(_n, ast.With)]
        assert _with, "② 操作列沒有 `with st.form(...)`"
        _body_calls = [
            _c for _w in _with for _n in _w.body for _c in ast.walk(_n)
            if isinstance(_c, ast.Call) and isinstance(_c.func, ast.Attribute)
        ]
        _submits = [_c for _c in _body_calls
                    if _c.func.attr == "form_submit_button"]
        _buttons = [_c for _c in _body_calls if _c.func.attr == "button"]
        assert len(_submits) == 1, (
            f"form 內應恰有 1 顆 submit，實際 {len(_submits)} 顆")
        assert not _buttons, (
            "form 內出現 `st.button` —— 線框 F11：實跑即拋 "
            "StreamlitAPIException")

    def test_widget_key_is_only_touched_inside_the_form(self):
        """**鐵律 2 的本體**：下游不得讀 widget 的當下值。

        只包 form 只擋得住互動 rerun；真正省下重運算的，是
        「當下值」與「已套用值」分成兩個東西、下游只讀後者。
        """
        _tree = ast.parse(_VIEW.read_text(encoding="utf-8"))
        _offenders = []
        for _n in ast.walk(_tree):
            if not isinstance(_n, ast.FunctionDef):
                continue
            if _n.name == "_render_update_form":
                continue
            for _s in ast.walk(_n):
                if isinstance(_s, ast.Name) and _s.id == "_SS_MODE_WIDGET":
                    _offenders.append(f"{_n.name}:{_s.lineno}")
        assert not _offenders, (
            f"widget 當下值被 form 以外的地方讀了：{_offenders} —— "
            "下游只准讀已套用值 `_SS_APPLIED`")

    def test_applied_mode_reads_the_applied_value_not_the_widget(self):
        assert T.applied_update_mode({}) is None, (
            "沒送出過就不該有已套用值")
        assert T.applied_update_mode(
            {T._SS_MODE_WIDGET: T.MODE_FORCE}) is None, (
            "只動了 widget 當下值就回報「已套用」—— 鐵律 2 被繞過了")
        assert T.applied_update_mode(
            {T._SS_APPLIED: {"mode": T.MODE_FORCE}}) == T.MODE_FORCE

    def test_gate_flag_is_written_only_by_the_submit_handler(self):
        """`requested` 只能由上游帶下來，禁止由 `if not data:` 推導。"""
        _tree = ast.parse(_VIEW.read_text(encoding="utf-8"))
        _writers = set()
        for _n in ast.walk(_tree):
            if not isinstance(_n, ast.FunctionDef):
                continue
            for _s in ast.walk(_n):
                if (isinstance(_s, ast.Assign)
                        and any(isinstance(_t, ast.Subscript)
                                and isinstance(_t.slice, ast.Name)
                                and _t.slice.id == "_SS_REQUESTED"
                                for _t in _s.targets)):
                    _writers.add(_n.name)
        assert _writers <= {"_render_update_form"}, (
            f"gate 旗標被這些地方寫入：{sorted(_writers)} —— "
            "只有 submit handler 可以寫")


# ══════════════════════════════════════════════════════════════════
# E. 鐵律 4：指路一律走 SSOT，不得手抄字串
# ══════════════════════════════════════════════════════════════════
class TestWhereGoesThroughSsot:

    #: 這些字串一旦在 view 裡以**字面值**出現，就是手抄 —— 改名時不會跟著動。
    _FORBIDDEN = tuple(ia_nav.PAGE_LABELS.values()) + tuple(
        ia_nav.ACTION_LABELS.values()) + tuple(ia_nav.SECTION_LABELS.values())

    @staticmethod
    def _docstring_ids(tree: ast.AST) -> set[int]:
        """docstring 的 Constant 節點 id。

        ⚠️ **刻意放行 docstring**：它不會被渲染，所以不會出現「畫面指向
        一顆不存在的按鈕」那種錯。**但這是一個真實的守衛缺口** ——
        docstring 裡引用的名稱一樣會過期，本檔驗不到。
        """
        _ids = set()
        for _n in ast.walk(tree):
            if not isinstance(_n, (ast.Module, ast.ClassDef,
                                   ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            _body = getattr(_n, "body", None)
            if (_body and isinstance(_body[0], ast.Expr)
                    and isinstance(_body[0].value, ast.Constant)
                    and isinstance(_body[0].value.value, str)):
                _ids.add(id(_body[0].value))
        return _ids

    def test_view_contains_no_hand_copied_page_or_button_names(self):
        _tree = ast.parse(_VIEW.read_text(encoding="utf-8"))
        _skip = self._docstring_ids(_tree)
        _bad = []
        for _n in ast.walk(_tree):
            if not (isinstance(_n, ast.Constant) and isinstance(_n.value, str)):
                continue
            if id(_n) in _skip:
                continue
            for _lit in self._FORBIDDEN:
                if _lit in _n.value:
                    _bad.append(f"{_VIEW.name}:{_n.lineno} 含 {_lit!r}")
        assert not _bad, (
            f"view 裡手抄了 SSOT 名稱：{_bad} —— "
            "分頁名 / 按鈕名一律走 `shared.ia_nav`，"
            "否則改名時指路句會指向不存在的東西"
            "（`macro_ui_components.key_alerts_banner` 就是這個 bug 的現例）")

    def test_ia_nav_fails_loud_on_unknown_ids(self):
        for _fn, _arg in ((ia_nav.page_label, "nope"),
                          (ia_nav.where_to_find, "nope"),
                          (ia_nav.action_label, "nope"),
                          (ia_nav.where_to_press, "nope")):
            with pytest.raises(ValueError):
                _fn(_arg)

    def test_where_to_find_composes_parent_page_name(self):
        assert ia_nav.where_to_find(ia_nav.SECTION_WHY_DATA_HEALTH) == (
            "「📖 憑什麼 › 資料體檢」")


# ══════════════════════════════════════════════════════════════════
# F. 鐵律 3：四態 —— 契約的三條分支各判各的
# ══════════════════════════════════════════════════════════════════
class TestFourStatesFromTheContract:

    def test_unloaded_contract_is_grey_not_neutral(self):
        from shared import regime_arbiter as RA
        _c = T.build_status_bar_card(
            {"source": RA.SOURCE_UNLOADED, "is_loaded": False,
             "regime": "unknown"})
        assert _c.state != UI_LIVE
        assert not _c.value, "未評估不得給結論"
        assert "unknown" in _c.note.why or "neutral" in _c.note.why

    def test_ai_snapshot_branch_is_degraded_not_green(self):
        """線框 N4：走 `macro_state.json` 快照時 `is_loaded=True`、
        畫面會長得像正常的 🟢 —— 但那是**上一次**鎖的結論。"""
        from shared import regime_arbiter as RA
        _c = T.build_status_bar_card(
            {"source": RA.SOURCE_FILE_RULE_ENGINE, "is_loaded": True,
             "regime": "bull", "light": "🟢"})
        assert _c.state != UI_LIVE, (
            "AI 鎖定快照被畫成正常態 —— 那是把上一次的結論當成這一輪的")
        assert "快照" in _c.note.now

    def test_degraded_does_not_invent_a_timestamp(self):
        """契約只有 9 個 key、不含 timestamp。**寧可寫「時間不明」，
        也不編一個時間出來**（線框 N4 原文）。"""
        from shared import regime_arbiter as RA
        _c = T.build_status_bar_card(
            {"source": RA.SOURCE_FILE_RULE_ENGINE, "is_loaded": True,
             "regime": "bull"})
        assert "時間不明" in _c.note.now

    def test_contract_read_failure_is_red(self):
        _c = T.build_status_bar_card(None, error=RuntimeError("boom"))
        assert _c.state == "failed"
        assert "boom" in _c.note.why

    def test_live_contract_gives_a_conclusion(self):
        from shared import regime_arbiter as RA
        _c = T.build_status_bar_card(
            {"source": RA.SOURCE_BULL_SCORE, "is_loaded": True,
             "regime": "bull", "light": "🟢"})
        assert _c.state == UI_LIVE
        assert _c.value

    def test_live_prefers_the_contracts_own_chinese_label(self):
        """位階的中文說法讀契約的 `traffic_light`，本檔不自建對照表。

        自建 regime→中文 對照 = 第二份真相源，一定會跟燈號卡漂開。
        """
        from shared import regime_arbiter as RA
        _c = T.build_status_bar_card(
            {"source": RA.SOURCE_BULL_SCORE, "is_loaded": True,
             "regime": "bull", "light": "🟢", "traffic_light": "偏多"})
        assert "偏多" in _c.value
        assert "bull" not in _c.value

    def test_summary_cells_are_judged_independently(self):
        """線框 ③ note：**逐格獨立判態** —— 一格壞不把另外兩格一起染色。"""
        from shared import regime_arbiter as RA
        _blocks = {_b.key: _b for _b in T.build_today_blocks(
            macro_state={"source": RA.SOURCE_BULL_SCORE, "is_loaded": True,
                         "regime": "bull", "light": "🟢"})}
        _states = [_c.state for _c in _blocks["today.summary"].cards]
        assert _states[0] == UI_LIVE, "位階已接線，契約有值時應為正常態"
        assert set(_states[1:]) == {UI_UNWIRED}, (
            "動能／風險本批未接線，不得被位階的正常態一起染綠")


# ══════════════════════════════════════════════════════════════════
# G. Fail Loud：三要素缺一 / 非正常態帶結論，一律當場炸
# ══════════════════════════════════════════════════════════════════
class TestFailLoud:

    def test_note_rejects_empty_element(self):
        for _kw in ({"now": ""}, {"why": ""}, {"where": ""}):
            _args = {"now": "a", "why": "b", "where": "c"} | _kw
            with pytest.raises(ValueError):
                T.Note(**_args)

    def test_card_rejects_non_live_without_note(self):
        with pytest.raises(ValueError):
            T.Card(key="k", label="l", state=UI_UNWIRED)

    def test_card_rejects_conclusion_on_non_live(self):
        with pytest.raises(ValueError):
            T.Card(key="k", label="l", state=UI_UNWIRED,
                   note=T.Note(now="a", why="b", where="c"),
                   value="（測試用假結論；它出現在畫面上就是 bug）")


# ══════════════════════════════════════════════════════════════════
# H. 冒煙：這一頁真的畫得出來（slow lane）
# ══════════════════════════════════════════════════════════════════
@pytest.mark.slow
def test_page_mounts_clean(tmp_path):
    """本頁是全 repo **第一個** `st.form` —— F11 那個例外要實跑才擋得掉。"""
    import textwrap

    from streamlit.testing.v1 import AppTest

    _script = tmp_path / "_p01.py"
    _script.write_text(textwrap.dedent("""
        from src.ui.tabs.tab_today import render_tab_today
        render_tab_today()
    """), encoding="utf-8")

    _at = AppTest.from_file(str(_script), default_timeout=60)
    _at.run()
    assert not _at.exception, f"🚦 今天 mount 有 uncaught exception: {_at.exception}"

    _labels = [_b.label for _b in _at.button]
    assert ia_nav.action_label(ia_nav.ACTION_UPDATE_TODAY) in _labels, (
        f"submit 沒畫出來；實際按鈕：{_labels}")
    _md = "\n".join(_m.value for _m in _at.markdown)
    assert "沒有你可以執行的出口" in _md, "未接線態的誠實揭露沒有畫出來"
