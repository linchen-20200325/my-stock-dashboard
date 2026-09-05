"""tests/test_p01_today_skeleton.py — 🚦 今天（五頁 IA 第 1 頁）骨架守衛。

規格：`docs/wireframes/stock_ia_v1.html` 的 `PAGES[0]`（客戶 2026-09-05 拍板）。

═══ 粒度：**一張卡就是一個測試** ══════════════════════════════════════
四態與三要素掛在 `Card` 上，本檔的參數化也以**卡**為單位 ——
所以「只弄壞其中一張卡」會有**且只有**那一條轉紅，鄰居全綠。

⚠️ 這是本檔存在的主要理由。以「一級標題」或「整個區塊」為單位的守衛，
在同一段裡只要還有別的卡是誠實的，壞掉的那張就會被替它通過。

═══ 本檔**守不到**什麼（據實揭露，不要當成「已經守住了」）═══════════
下列各項都擋不住。**其中第 1、2 項**已登記在姊妹 repo `my-Fund-dashboard`
的憲法（`P-GREYSCENARIO-1` / `P-WHERECONTENT-1`），**台股端同樣適用**；
**第 3~8 項是本批自己的缺口**，不在那兩條登記裡，由總管裁定排到下一批
（需要在**渲染層**攔截，不是檢查資料層物件；下一批填真內容時本來就要重寫）。

1. **情境維**：斷言只覆蓋「契約全有」「契約全無」兩個 session 端點，
   中間那些半有半無的組合沒有窮舉。
2. **語意維**：只驗「這個符號在不在」「三要素是不是非空」，
   **不驗那句話講的是不是真的** —— 例如 `where` 指向的分區是否真的
   存在於畫面上、`why` 說的原因是否真的是那個原因，本檔一概驗不到。
3. **欄數只擋字面值**：`test_no_literal_columns_above_three` 掃的是
   `st.columns(4)` 這種寫法；`st.columns(n)` 以變數傳欄數的**掃不到**。
   `_grid` 已拿掉覆寫參數、呼叫點也有 AST 守衛，但**繞過 `_grid` 直接
   `st.columns(n)`（n 為變數）仍然攔不住**。
4. **docstring 放行**：SSOT 手抄守衛刻意跳過 docstring（它不渲染），
   所以 docstring 裡引用的分頁名／按鈕名一樣會過期，本檔驗不到。
5. **手抄守衛的射程只有 `tab_today.py` 一個檔。** 稽核逐項實測：直接寫字串
   ✅ 轉紅、放進 dict ✅ 轉紅；**字串拼接／f-string 夾空插值／`"".join()`／
   bytes 字面值 decode／把字串搬到隔壁新模組 ❌ 全部繞得過**。
   最後一項最實際 —— `shared/ia_nav.py` 自己都不在掃描範圍內。
6. **文案內容完全不設防**：假結論寫進 `now`、假承諾與全形數字寫進 `why`／
   `where`，全部驗不到 —— `Card` 的檢查只看 `value` 欄，而 `_render_card`
   把三要素原樣渲染出去。
7. **手刻 `st.markdown()` 完全在守衛視野外**：所有守衛的輸入都是
   `build_today_blocks()` 的回傳值，繞過那個函式直接畫東西一條都攔不到。
8. **四態只有兩態被真的渲染過**：冷啟動畫的是 `idle` 與 `unwired`；
   `degraded` / `failed` / `live` 只在單元測試裡構造過，**沒有經過 AppTest**。

**不宣稱本頁的誠實呈現已經被守住。**
"""
from __future__ import annotations

import ast
import pathlib

import pytest

from shared import ia_nav
from shared.ui_state import UI_LIVE, UI_STATES, UI_UNWIRED, state_meta
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
    """⚠️ **本類刻意不使用 `pytest.skip` 做狀態過濾。**

    稽核實測（必修-4）：上一版把葉2 七段的 `state` 從 `UI_UNWIRED` 改成
    `"idle"`、`where` 一字不動 → **74 passed, 9 skipped, 0 failed**。
    七條守衛**靜默地從「執行」變成「跳過」**，畫面上卻會出現
    「尚未載入」配「沒有你可以執行的出口」這種自相矛盾的卡，零紅燈。

    **`skip` 讓「改掉狀態」等於「關掉守衛」。** 現在每一條都對所有狀態成立，
    分支寫在斷言裡、不寫在 `skip` 裡。
    """

    def test_state_is_a_known_ui_state(self, block, card):
        assert card.state in UI_STATES, (
            f"{card.key} 的狀態 {card.state!r} 不在 L0 SSOT 的七態裡 —— "
            "本頁不得自創狀態名")

    def test_card_shape_matches_its_state(self, block, card):
        """正常態 ⇒ 有結論、無 Note；非正常態 ⇒ 三要素齊備、無結論。

        兩個分支都斷言，**沒有一個狀態會讓這條測試變成不執行**。
        """
        if card.state == UI_LIVE:
            assert card.value, f"{card.key} 是正常態卻沒有結論文字"
            assert card.note is None, (
                f"{card.key} 是正常態卻還帶著空狀態引導的三要素")
            return
        assert not card.value, (
            f"{card.key} 不是正常態卻帶了結論文字 {card.value!r} —— "
            "線框 §02：只有正常態能給結論文字")
        assert card.note is not None, f"{card.key} 非正常態卻沒有 Note"
        for _f in ("now", "why", "where"):
            assert str(getattr(card.note, _f)).strip(), (
                f"{card.key} 的 Note.{_f} 是空的 —— 鐵律 4 三要素缺一不可")

    def test_card_does_not_promise_an_action_this_batch_cannot_deliver(
            self, block, card):
        """**本批按下更新鈕不會改變任何一張卡**，所以每張卡都要照實說。

        必修-1：上一版只約束 `unwired`，於是狀態列的 `idle` 卡寫著
        「到「🚦 今天」按「🚀 更新今日戰情」」—— 稽核用 AppTest 連按兩次，
        **文字逐字不變**：submit handler 只寫 session、不觸發任何取數，
        而本頁沒有任何程式碼會填 `warroom_summary`。那是一句假指路。
        （順帶：它還寫「**到**「🚦 今天」」，而使用者當下就在這一頁。）
        """
        if card.state == UI_LIVE:
            return
        assert T.NO_EXIT_MARKER in card.note.where, (
            f"{card.key}（{card.state}）的 `where` 沒有 "
            f"{T.NO_EXIT_MARKER!r} —— 本批交付不出任何「按了就會變」的出口，"
            "寫成好像可以就是假指路")

    def test_no_state_glyph_is_hand_written_into_the_text(self, block, card):
        """必修-2：一個狀態只准有一個 glyph，而它由 L0 SSOT 供給。

        稽核實測：chip 印「⛔ 未接線」、body 同時印「⬜ … 尚未接線」——
        同一張卡上兩個互相矛盾的灰態 glyph。
        """
        if card.note is None:
            return
        for _f in ("now", "why", "where"):
            _v = str(getattr(card.note, _f))
            _bad = sorted(_g for _g in T._STATE_GLYPHS if _g in _v)
            assert not _bad, (
                f"{card.key} 的 Note.{_f} 手寫了狀態 glyph {_bad}；"
                f"這張卡的狀態是 {card.state}，SSOT 給的 glyph 是 "
                f"{state_meta(card.state)[1]!r}")


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

    def test_detail_has_exactly_seven_segments(self):
        """**必修-5：一個名字裡寫著「七」的測試，必須真的數過七。**

        稽核實測：把 `DETAIL_SEGMENTS` **整個清空** → 53 passed、0 failed。
        下面那條逐段比對是 `for ... in DETAIL_SEGMENTS`，清空就變成迴圈空轉、
        **vacuous pass** —— 整個葉2 從畫面上消失而測試全綠。
        """
        assert len(T.DETAIL_SEGMENTS) == 7, (
            f"葉2 應為七段，實際 {len(T.DETAIL_SEGMENTS)} 段：線框原文是 "
            "「A 市場狀態 / B 長期 / C 中期 / D 短線 / E 籌碼 / F 全球風險 / G 跨桶裁決」")
        assert len({_k for _k, _ in T.DETAIL_SEGMENTS}) == 7, "段 key 有重複"

    def test_seven_detail_segments_are_quoted_from_the_wireframe(self):
        """葉2 七段的段名必須逐字出現在線框裡。

        線框改段名 → 這條轉紅。⚠️ 它**只驗內容、不驗數量** ——
        數量由上面那條 `test_detail_has_exactly_seven_segments` 負責。
        兩條缺一，刪一段就沒人會發現。
        """
        _text = _WIREFRAME.read_text(encoding="utf-8")
        assert T.DETAIL_SEGMENTS, "葉2 一段都沒有 —— 這條會空轉，先看上一條"
        for _k, _label in T.DETAIL_SEGMENTS:
            assert _label in _text, (
                f"葉2 段名 {_label!r} 在線框裡找不到 —— "
                "要嘛抄錯，要嘛線框改了而本頁沒跟上")

    def test_submit_label_is_quoted_from_the_wireframe(self):
        _text = _WIREFRAME.read_text(encoding="utf-8")
        _label = ia_nav.action_label(ia_nav.ACTION_UPDATE_TODAY)
        assert _label in _text, (
            f"submit 名稱 {_label!r} 在線框裡找不到")


#: 冷啟動（契約全無）下**每一張卡的 key → 狀態**，逐格釘死。
#:
#: 為什麼要有這張表（必修-4 ＋ 必修-5，兩個稽核發現的共同解藥）：
#:   · 稽核把七段的 `state` 由 `unwired` 改成 `"idle"` → 舊守衛靜默 skip、零紅燈；
#:   · 稽核刪掉 `summary.risk` 整段（三欄變兩欄）→ 77 passed、零紅燈；
#:   · 稽核從 `DETAIL_SEGMENTS` 刪掉一段 → 77 passed、零紅燈。
#: 逐項參數化只驗「存在的卡是不是誠實的」，**驗不到「有沒有卡不見了」**。
#: 這張表把「有哪些卡、各自什麼狀態」變成一個會被比對的事實。
#: ⚠️ 下一批接線時**本表會變**，那是刻意的：改它要顯式改，不能默默漂。
EXPECTED_COLD_START_STATES: dict[str, str] = {
    "statusbar.trading_day": UI_UNWIRED,
    "statusbar.macro": "idle",
    "statusbar.sheet": UI_UNWIRED,
    "verdict.exposure": UI_UNWIRED,
    "summary.regime": "idle",
    "summary.momentum": UI_UNWIRED,
    "summary.risk": UI_UNWIRED,
    "key_banner.alerts": UI_UNWIRED,
    "warroom.todo": UI_UNWIRED,
    "warroom.ai": UI_UNWIRED,
    "detail.a_state": UI_UNWIRED,
    "detail.b_long": UI_UNWIRED,
    "detail.c_mid": UI_UNWIRED,
    "detail.d_short": UI_UNWIRED,
    "detail.e_chips": UI_UNWIRED,
    "detail.f_global_risk": UI_UNWIRED,
    "detail.g_cross": UI_UNWIRED,
}


class TestStructureCannotBeDeletedSilently:
    """必修-5：整塊結構被刪掉時，必須有東西轉紅。"""

    def test_cold_start_card_set_and_states_are_pinned(self):
        _actual = {_c.key: _c.state for _b, _c in _all_cards()}
        assert _actual == EXPECTED_COLD_START_STATES, (
            "冷啟動的卡片組成或狀態變了。\n"
            f"少了：{sorted(set(EXPECTED_COLD_START_STATES) - set(_actual))}\n"
            f"多了：{sorted(set(_actual) - set(EXPECTED_COLD_START_STATES))}\n"
            "狀態不同："
            f"{ {k: (EXPECTED_COLD_START_STATES[k], _actual[k]) for k in _actual.keys() & EXPECTED_COLD_START_STATES.keys() if _actual[k] != EXPECTED_COLD_START_STATES[k]} }\n"
            "接線改變它是正常的 —— 但要**顯式**改這張表，不能默默漂。")

    def test_summary_block_is_three_columns_worth(self):
        """線框 ③ 是「三欄摘要」。刪掉一格 → 這條轉紅。"""
        _b = {_x.key: _x for _x in T.build_today_blocks()}["today.summary"]
        assert len(_b.cards) == 3, (
            f"三欄摘要應有 3 格（位階／動能／風險），實際 {len(_b.cards)} 格")

    def test_status_bar_has_all_three_elements(self):
        """線框 ⑦ 的 grey 原文是「⬜ 總經未評估　|　🔗 尚未綁定 Sheet」，
        live 還有交易日 —— **三個元素**，不是一個。

        必修-3：上一版只做了「總經」一格，另外兩個**連未接線都沒標**。
        """
        _b = {_x.key: _x for _x in T.build_today_blocks()}["today.statusbar"]
        assert {_c.key for _c in _b.cards} == {
            "statusbar.trading_day", "statusbar.macro", "statusbar.sheet"}, (
            f"頂部狀態列元素不齊：{[_c.key for _c in _b.cards]}")

    def test_sheet_element_points_at_the_ssot_destination(self):
        """`ia_nav.SECTION_HOLD_PORTFOLIO_SETUP` 必須真的被用到。

        它上一版定義了卻**零引用** —— 那正是「線框元素沒做」的旁證。
        """
        _cards = {_c.key: _c for _b, _c in _all_cards()}
        _where = _cards["statusbar.sheet"].note.where
        assert ia_nav.where_to_find(
            ia_nav.SECTION_HOLD_PORTFOLIO_SETUP) in _where


# ══════════════════════════════════════════════════════════════════
# C. 鐵律 1：3 欄自適應網格
# ══════════════════════════════════════════════════════════════════
class TestThreeColumnGrid:

    def test_grid_takes_no_column_override(self):
        """必修-6：`_grid` 原本有 `per_row: int = 3`，`_grid(cards, 7)`
        一行就開出 7 欄而**全部守衛照樣綠** —— 「繞過 `_grid`」根本不必繞。
        現在欄數只由 `MAX_COLS` 決定，呼叫端沒有覆寫它的語法。
        """
        import inspect
        assert list(inspect.signature(T._grid).parameters) == ["items"], (
            "`_grid` 多了一個參數 —— 只要它能被呼叫端覆寫，鐵律 1 就是可選的")
        assert T.MAX_COLS == 3, "鐵律 1：一列上限 3 欄"

    def test_every_grid_call_passes_only_the_items(self):
        """AST 掃本檔的每一個 `_grid(...)` 呼叫點：恰好 1 個位置引數、0 個關鍵字。

        簽名守衛擋掉「加回參數」，這一條擋掉「用位置引數硬塞第二個值」。
        """
        _tree = ast.parse(_VIEW.read_text(encoding="utf-8"))
        _calls = [_n for _n in ast.walk(_tree)
                  if isinstance(_n, ast.Call)
                  and isinstance(_n.func, ast.Name) and _n.func.id == "_grid"]
        assert _calls, "view 裡找不到任何 `_grid(...)` 呼叫 —— 版面是誰排的？"
        for _c in _calls:
            assert len(_c.args) == 1 and not _c.keywords, (
                f"{_VIEW.name}:{_c.lineno} `_grid` 被傳了額外的引數 —— "
                "欄數只能由 MAX_COLS 決定")

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

    @pytest.mark.parametrize(
        "glyph", sorted(T._STATE_GLYPHS),
        ids=[f"glyph-{_g}" for _g in sorted(T._STATE_GLYPHS)])
    def test_upstream_error_with_a_glyph_still_paints_a_red_card(self, glyph):
        """必修-A：**上游訊息帶 glyph 時，紅卡照畫，不得改成拋例外。**

        `Note` 禁收 glyph（必修-2）是對的 —— 它擋的是**人手抄**。
        但 `failed` 分支把上游例外訊息原樣插進 `why`，於是一個
        「`🔴 FRED 連線失敗`」會在 `Note.__post_init__` 變成 `ValueError`，
        一路穿過 `build_today_blocks` → `render_tab_today` 成為**整頁崩潰**，
        而不是那張紅色「取得失敗」卡。
        **「紅態要看得見，不是換一種炸法」從另一道門走回來了。**
        """
        _c = T.build_status_bar_card(None, error=f"{glyph} 上游掛了")
        assert _c.state == "failed", "帶 glyph 的錯誤訊息把紅態弄丟了"
        assert "上游掛了" in _c.note.why, "原始訊息被整段吃掉了"
        assert glyph not in _c.note.why, "glyph 沒有被移除"
        assert "已移除" in _c.note.why, (
            "移除了東西卻沒說 —— §1：修改過的訊息不能假裝自己是原文")

    def test_whole_page_survives_a_glyph_laden_upstream_error(self):
        """半徑證明：整頁組裝也不能炸（`build_today_blocks` 是真正的路徑）。"""
        _blocks = T.build_today_blocks(
            macro_error="🔴 FRED 連線失敗 ▨ 空表 ⬜")
        _bar = {_c.key: _c for _b in _blocks for _c in _b.cards}["statusbar.macro"]
        assert _bar.state == "failed"

    def test_scrub_reports_how_many_it_removed(self):
        _clean, _n = T.scrub_state_glyphs("🔴 a ▨ b 🟢")
        assert _n == 3 and "a" in _clean and "b" in _clean
        assert not (set(_clean) & T._STATE_GLYPHS)

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

    def test_note_rejects_a_hand_written_state_glyph(self):
        """必修-2 的結構化版本：文案自己帶 glyph 一律當場炸。

        不是只靠測試掃 —— `Note` 自己拒收，所以任何路徑造出來的卡都擋得到。
        """
        for _kw in ({"now": "⬜ 尚未載入"}, {"why": "⛔ 未接線"},
                    {"where": "🟢 好了"}):
            _args = {"now": "a", "why": "b", "where": "c"} | _kw
            with pytest.raises(ValueError, match="glyph"):
                T.Note(**_args)

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
    assert T.NO_EXIT_MARKER in _md, "誠實揭露（沒有可執行出口）沒有畫出來"
    for _label in ("交易日", "Sheet 綁定"):
        assert _label in _md, (
            f"頂部狀態列的「{_label}」元素沒有畫出來（必修-3）")


@pytest.mark.slow
def test_pressing_update_twice_does_not_change_any_card_text(tmp_path):
    """必修-1 的實跑證明：**按下更新鈕，畫面文字逐字不變。**

    ⚠️ **必須點兩次，點一次結構上什麼都看不到**（稽核必修-B）：
    Streamlit 的 `form_submit_button` 是在**該次 rerun 的頁面主體渲染完之後**
    才回 True，而 `render_tab_today` 在最頂端就把 `get_macro_state` 讀完了 ——
    handler 寫進 session 的東西**要到下一次 rerun 才看得見**。
    上一版只點一次，於是**任何經由 submit handler 的接線它都看不到**，
    只是把現況拍照存證；docstring 卻宣稱「接上就會轉紅」。
    **一條廣告自己有、實際沒有的保護，比沒有保護更危險。**

    修完已實跑驗證：把 handler 接上一份有效契約 → 第 2 次點擊後位階格變成
    「**🟢 位階 偏多**」→ **本條轉紅**。

    ⚠️ 它仍然**只看得到會浮到 `st.markdown` 上的變化**；
    不經 markdown 呈現的東西（例如只改了某個 metric 或圖）照樣看不到。
    """
    import textwrap

    from streamlit.testing.v1 import AppTest

    _script = tmp_path / "_p01_press.py"
    _script.write_text(textwrap.dedent("""
        from src.ui.tabs.tab_today import render_tab_today
        render_tab_today()
    """), encoding="utf-8")

    _at = AppTest.from_file(str(_script), default_timeout=60)
    _at.run()
    _before = [_m.value for _m in _at.markdown]

    _at.button[0].click().run()
    assert not _at.exception, f"第 1 次按下 submit 後炸了：{_at.exception}"
    _at.button[0].click().run()
    assert not _at.exception, f"第 2 次按下 submit 後炸了：{_at.exception}"
    _after = [_m.value for _m in _at.markdown]

    _diff = [(_b, _a) for _b, _a in zip(_before, _after) if _b != _a]
    assert _before == _after, (
        "按兩次更新鈕之後畫面文字變了 —— 本批的 submit 只寫 session、不取數；"
        "若這裡變了代表有東西被接上了，`CONTRACT_NO_EXIT_WHERE` 那句"
        "「按它不會讓這一格離開現在的狀態」就成了假話，必須一起改。\n"
        f"變動處：{_diff[:3]}")
