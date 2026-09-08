"""IA v2 五頁「檔案裡描述自己怎麼被掛載」的敘述守衛（跨五頁，故用 `p0x`）。

═══ 這支存在的理由（2026-09-08 FE-36）═══════════════════════════════
`src/ui/views/page_*.py` 的檔頭各寫了一段「`app.py` 現在怎麼掛我」。
那種敘述有一個結構性弱點：**它描述的是別的檔案**，所以掛載一改，
它就**靜悄悄地變成假話，而且沒有任何機制會發現**。實際發生過兩輪：

  1. 五頁剛落地時寫「本檔沒有 production caller」→ 接線的批次沒有回頭改它，
     **四個檔一起漂了整整一批**（FE-32 只修了 `page_find` 檔頭那一句，
     連同一個檔的 `render_page_find()` docstring 都沒修到）。
  2. FE-32 補的「`app.py` 現在確實掛著本頁（`with tab_find:`）、本頁每一次
     app run 都會被執行」→ `b5bdb36` 把掛載改成側欄 radio ＋ lazy 渲染，
     **當天就變成假的**：`tab_find` 這個變數已經不存在，沒被選到時
     那個檔連 import 都不會發生。

兩輪都不是「有人寫錯」，是**沒有東西在看**。本檔就是那個東西。

═══ 它守什麼、不守什麼（先講清楚射程）═════════════════════════════
✅ **守得到**：`app.py` 的**掛載形態**（五頁是不是頂層頁籤、是不是走
   函式體內 late import、選到新頁那一輪會不會在建立舊頁籤**之前** `st.stop()`、
   入口是不是側欄 radio）。掛載再改一次 → 這裡**當場紅**，而紅燈訊息會
   指名叫下一個人去複驗那五個檔的檔頭敘述。
✅ **守得到**：那幾句**已知失真、已經修掉**的話**不准原封不動長回來**
   （下方 `STALE_CLAIMS`），除非放進 `~~ ~~`（本 repo 記錄病史的標準寫法）。
⛔ **守不到**：散文語意。沒有任何測試讀得懂「這段中文現在還對不對」。
   本檔**不**去 grep 檔頭有沒有寫「側欄」之類的字 —— 那種寫法會在下一個人
   換句話說時亂紅，而**一支會亂紅的守衛比沒有守衛更糟**（下一個人會把它 `-k` 掉）。
   本檔的設計是：**掛載一變就紅在 app.py 這一側**，由人去複驗散文。
   ⚠️ 這是有意識的取捨，不是漏做。

═══ 為什麼不是恆真式（重點）═══════════════════════════════════════
下方每一條的**期望值都寫死在本檔裡**（`PAGES` / `LEGACY_TAB_VARS` /
`SIDEBAR_NAV_KEY`），**受測對象是 `app.py`** —— 兩個不同的檔案，
不是「從同一個來源讀兩次自己比自己」。
同一個理由讓 `test_no_view_reasserts_a_stale_mount_claim` 讀的是
`src/ui/views/**`、比對的是本檔的字面常數。
沿用 `tests/test_ia_v2_sidebar_nav.py::TestTheSevenTabsAreExactlyTheClientsOnes`
的既有作法（「把字串寫死在測試裡當第二來源」）。

═══ fail loud（`CLAUDE.md` §1）═════════════════════════════════════
`app.py` 不見 / 讀不到 / `ast.parse` 失敗 / 一個 view 都沒掃到
→ 一律 `AssertionError`，**不 skip、不靜默通過**。
另有 `TestTheGuardItself`，用合成字串證明它抓得到真違規、也不會被
`~~ ~~` 以外的無關字眼騙。
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

_TESTS_DIR = Path(__file__).resolve().parent
_REPO = _TESTS_DIR.parent
_APP_REL = "app.py"
_VIEWS_REL = "src/ui/views"

# ══════════════════════════════════════════════════════════════════════
# 期望值（**第二來源**：寫死在本檔，不從 app.py 讀出來自己比自己）
# ══════════════════════════════════════════════════════════════════════
#: (view 檔名, `app.py` 端的 late-import wrapper, 該頁的 render 函式)
PAGES: tuple[tuple[str, str, str], ...] = (
    ("page_today.py", "_ia_view_today", "render_page_today"),
    ("page_find.py", "_ia_view_find", "render_page_find"),
    ("page_inspect.py", "_ia_view_inspect", "render_page_inspect"),
    ("page_hold.py", "_ia_view_hold", "render_page_hold"),
    ("page_why.py", "_ia_view_why", "render_page_why"),
)

#: FE-7~FE-16 期間五頁掛成頂層頁籤時用過的變數名。`b5bdb36` 之後**一個都不該在**。
#: 它們回來 = 掛載又變回頁籤 = 五頁檔頭那幾段 FE-36 更正全部作廢。
LEGACY_TAB_VARS: tuple[str, ...] = (
    "tab_today", "tab_find", "tab_inspect", "tab_hold", "tab_why")

#: 側欄 radio 的 widget key（`app.py` 從 `shared/ia_nav` 取頁 id，但這個 key
#: 是 `app.py` 自己的字面常數）。它換掉 = 導覽入口被改過 = 一樣要回頭複驗。
SIDEBAR_NAV_KEY: str = "_sb_ia_page"

#: 建立舊 7 個頁籤的那一行的第一個變數名（用來定位「頁籤是在哪一行才生出來的」）。
FIRST_LEGACY_TAB_VAR: str = "tab_market"

#: 已知失真、已經修掉的敘述。**原句要留 → 包進 `~~ ~~`**（病史保留的標準寫法）。
#: ⚠️ 只收**斷言句**，不收更正文裡需要引用的片語 ——
#: 例如「每一次 app run 都會被執行」故意**不在**這張表：FE-36 的更正文必須
#: 引用它才講得清楚在更正什麼，收進來等於逼人把更正文本身也劃掉。
#: 那一句由上面 `test_*` 的結構性斷言負責（lazy 掛載一改就紅）。
STALE_CLAIMS: tuple[tuple[str, str], ...] = (
    ("本檔沒有 production caller",
     "五頁都已由 `app.py` 的 `_ia_view_*` wrapper 掛上，這句是假的"),
    ("本批無 production caller",
     "同上；FE-32 那輪只修了檔頭、漏掉 render 函式的 docstring"),
    ("with tab_today", "五頁已不是頂層頁籤（`b5bdb36`）"),
    ("with tab_find", "五頁已不是頂層頁籤（`b5bdb36`）"),
    ("with tab_inspect", "五頁已不是頂層頁籤（`b5bdb36`）"),
    ("with tab_hold", "五頁已不是頂層頁籤（`b5bdb36`）"),
    ("with tab_why", "五頁已不是頂層頁籤（`b5bdb36`）"),
    ("的分頁列", "掛載點是側欄 radio，不是分頁列（`b5bdb36`）"),
)

#: 掛載形態變了的時候要印給人看的話 —— 紅燈訊息**必須**把人送到那五個檔，
#: 否則這支守衛只會讓人來改測試（把它改綠），而散文照樣是假的。
_GO_FIX_THE_VIEWS = (
    "\n\n⚠️ **掛載形態變了。** 這代表 `src/ui/views/page_*.py` 檔頭那幾段"
    "「`app.py` 怎麼掛我」的敘述**現在可能全是假的** —— 那正是本檔存在的理由"
    "（歷史上已經漂過兩輪）。請逐檔複驗並照 repo 慣例更正"
    "（**原文加刪除線保留 + 註明日期與原因**，不要整段刪掉），再回來更新本檔的期望值。"
)


# ══════════════════════════════════════════════════════════════════════
# 讀取（一律 `read_text(encoding="utf-8")`）
# ══════════════════════════════════════════════════════════════════════
def _read(rel: str) -> str:
    _p = _REPO / rel
    assert _p.is_file(), f"{rel} 不見了 —— 本檔的受測對象消失，不是綠燈，是紅燈"
    _s = _p.read_text(encoding="utf-8")
    assert _s.strip(), f"{rel} 是空的"
    return _s


def _app_tree() -> ast.Module:
    _src = _read(_APP_REL)
    try:
        return ast.parse(_src)
    except SyntaxError as _e:  # pragma: no cover - 真壞掉時才會走到
        raise AssertionError(f"{_APP_REL} 解析失敗，無法驗證掛載形態：{_e}") from _e


def _with_var_names(tree: ast.Module) -> set[str]:
    """所有 `with <Name>:` 的那個 `<Name>`（`with tab_market:` → `tab_market`）。"""
    _names: set[str] = set()
    for _n in ast.walk(tree):
        if isinstance(_n, (ast.With, ast.AsyncWith)):
            for _item in _n.items:
                if isinstance(_item.context_expr, ast.Name):
                    _names.add(_item.context_expr.id)
    return _names


def _view_imports(tree: ast.Module) -> dict[str, list[tuple[int, bool]]]:
    """`src.ui.views.page_*` 的 import → [(行號, 是否在函式體內)]。"""
    _inside: set[int] = set()
    for _n in ast.walk(tree):
        if isinstance(_n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for _sub in ast.walk(_n):
                if isinstance(_sub, ast.ImportFrom):
                    _inside.add(id(_sub))
    _out: dict[str, list[tuple[int, bool]]] = {}
    for _n in ast.walk(tree):
        if isinstance(_n, ast.ImportFrom) and (_n.module or "").startswith(
                "src.ui.views.page_"):
            _out.setdefault(_n.module, []).append((_n.lineno, id(_n) in _inside))
    return _out


def _call_linenos(tree: ast.Module, obj: str, attr: str) -> list[int]:
    """`<obj>.<attr>(...)` 的行號（`st.stop()` / `st.tabs(...)`）。"""
    _out: list[int] = []
    for _n in ast.walk(tree):
        if (isinstance(_n, ast.Call) and isinstance(_n.func, ast.Attribute)
                and _n.func.attr == attr
                and isinstance(_n.func.value, ast.Name)
                and _n.func.value.id == obj):
            _out.append(_n.lineno)
    return _out


def _strip_struck(text: str) -> str:
    """去掉 `~~ ... ~~` 的內容（可跨行）—— 病史保留區不算「還在主張」。"""
    return re.sub(r"~~.*?~~", "", text, flags=re.S)


# ══════════════════════════════════════════════════════════════════════
class TestTheMountFormIsStillWhatTheViewsDescribe:
    """`app.py` 這一側的**結構性**事實。任一條紅 → 去複驗五頁檔頭的散文。"""

    def test_the_five_pages_are_not_top_level_tabs(self):
        _clash = sorted(_with_var_names(_app_tree()) & set(LEGACY_TAB_VARS))
        assert not _clash, (
            f"`app.py` 又出現 `with {_clash[0]}:` 這種頂層頁籤掛法（命中 {_clash}）。"
            + _GO_FIX_THE_VIEWS)

    @pytest.mark.parametrize("view_file,wrapper,render_fn", PAGES)
    def test_every_view_is_imported_lazily_inside_a_function(
            self, view_file: str, wrapper: str, render_fn: str):
        """五頁**都有** production caller，而且**都是 late import**。

        這一條同時釘住兩件事，缺一不可：
          · **有 caller** —— 「本檔沒有 production caller」那一族假話的反面；
          · **lazy** —— 沒被選到就連 import 都不發生（本次改動的成本前提）。
        """
        _mod = f"src.ui.views.{view_file[:-3]}"
        _hits = _view_imports(_app_tree()).get(_mod, [])
        assert _hits, (
            f"`app.py` 已經不 import `{_mod}` 了 —— 這一頁沒有 production caller。"
            + _GO_FIX_THE_VIEWS)
        _module_level = [_ln for _ln, _in_fn in _hits if not _in_fn]
        assert not _module_level, (
            f"`{_mod}` 在 `app.py` 的 module level 被 import（行 {_module_level}）—— "
            "那就不是 lazy 了，「沒選到就一行都不跑」這個保證當場失效。"
            + _GO_FIX_THE_VIEWS)

    @pytest.mark.parametrize("view_file,wrapper,render_fn", PAGES)
    def test_the_wrapper_exists_and_calls_that_pages_render_fn(
            self, view_file: str, wrapper: str, render_fn: str):
        _fn = next(
            (_n for _n in ast.walk(_app_tree())
             if isinstance(_n, ast.FunctionDef) and _n.name == wrapper), None)
        assert _fn is not None, (
            f"`app.py` 裡找不到 `{wrapper}()` —— 掛載入口換過了。"
            + _GO_FIX_THE_VIEWS)
        _called = {
            _c.func.id for _c in ast.walk(_fn)
            if isinstance(_c, ast.Call) and isinstance(_c.func, ast.Name)}
        assert render_fn in _called, (
            f"`{wrapper}()` 沒有呼叫 `{render_fn}()`（實際呼叫 {sorted(_called)}）。"
            + _GO_FIX_THE_VIEWS)

    def test_choosing_a_new_page_stops_before_the_old_tabs_are_built(self):
        """選到新頁那一輪 `st.stop()`，且它在**建立舊頁籤之前**。

        這一條是「新頁與舊 7 個頁籤**不會同輪渲染**」的機械證據 ——
        五頁那幾段「同時掛上會撞 `DuplicateWidgetID`」的更正文，前提就是它。
        """
        _tree = _app_tree()
        _stops = _call_linenos(_tree, "st", "stop")
        assert _stops, (
            "`app.py` 已經沒有 `st.stop()` —— 選到新頁時舊 7 個頁籤會照樣被建立，"
            "兩邊回到同一個 script run，「不同輪」那個前提失效。" + _GO_FIX_THE_VIEWS)

        _tabs_line = None
        for _n in ast.walk(_tree):
            if isinstance(_n, ast.Assign) and isinstance(_n.value, ast.Call):
                _f = _n.value.func
                if (isinstance(_f, ast.Attribute) and _f.attr == "tabs"
                        and isinstance(_f.value, ast.Name) and _f.value.id == "st"):
                    _names = [
                        _t.id for _tgt in _n.targets
                        for _t in ast.walk(_tgt) if isinstance(_t, ast.Name)]
                    if FIRST_LEGACY_TAB_VAR in _names:
                        _tabs_line = _n.lineno
                        break
        assert _tabs_line is not None, (
            f"找不到建立舊頁籤那一行（`{FIRST_LEGACY_TAB_VAR}, ... = st.tabs([...])`）。"
            + _GO_FIX_THE_VIEWS)
        assert min(_stops) < _tabs_line, (
            f"`st.stop()` 在第 {min(_stops)} 行、舊頁籤在第 {_tabs_line} 行 —— "
            "順序反了，新頁那一輪會連舊頁籤一起建立。" + _GO_FIX_THE_VIEWS)

    def test_the_entry_point_is_a_sidebar_radio(self):
        """入口是側欄的 `st.radio`（不是頁籤、不是主畫面的按鈕）。"""
        _tree = _app_tree()
        _sidebar_lines: list[tuple[int, int]] = []
        for _n in ast.walk(_tree):
            if isinstance(_n, ast.With):
                for _item in _n.items:
                    _e = _item.context_expr
                    if (isinstance(_e, ast.Attribute) and _e.attr == "sidebar"
                            and isinstance(_e.value, ast.Name)
                            and _e.value.id == "st"):
                        _sidebar_lines.append(
                            (_n.lineno, max(
                                getattr(_s, "end_lineno", _n.lineno) or _n.lineno
                                for _s in _n.body)))
        assert _sidebar_lines, (
            "`app.py` 已經沒有 `with st.sidebar:` 區塊。" + _GO_FIX_THE_VIEWS)

        _radios = [
            _n for _n in ast.walk(_tree)
            if isinstance(_n, ast.Call) and isinstance(_n.func, ast.Attribute)
            and _n.func.attr == "radio" and isinstance(_n.func.value, ast.Name)
            and _n.func.value.id == "st"
            and any(_lo <= _n.lineno <= _hi for _lo, _hi in _sidebar_lines)]
        assert _radios, (
            "側欄裡已經沒有 `st.radio(...)` —— 五頁的導覽入口換掉了。"
            + _GO_FIX_THE_VIEWS)
        assert SIDEBAR_NAV_KEY in _read(_APP_REL), (
            f"`app.py` 裡找不到側欄導覽的 widget key {SIDEBAR_NAV_KEY!r} —— "
            "五頁檔頭引用了這個 key，它換名就要一起改。" + _GO_FIX_THE_VIEWS)

    def test_the_matcher_is_not_matching_everything(self):
        """**反證**：上面幾條若因為比對器什麼都比得上而綠，那綠燈不算數。"""
        _tree = _app_tree()
        assert not _view_imports(_tree).get("src.ui.views.page_does_not_exist")
        assert "tab_this_never_existed" not in _with_var_names(_tree)
        assert not _call_linenos(_tree, "st", "no_such_streamlit_api")


# ══════════════════════════════════════════════════════════════════════
class TestNoViewReassertsAStaleMountClaim:
    """那幾句已經修掉的話**不准原封不動長回來**（要留 → 包進 `~~ ~~`）。"""

    def _view_files(self) -> list[Path]:
        _d = _REPO / _VIEWS_REL
        assert _d.is_dir(), f"{_VIEWS_REL} 不見了"
        _files = sorted(_d.glob("page_*.py"))
        assert _files, f"{_VIEWS_REL} 底下一個 `page_*.py` 都沒掃到 —— 不是綠燈"
        return _files

    def test_the_five_pages_in_this_guard_are_all_of_them(self):
        """新開第六頁時本檔要一起更新，不然它會靜靜地不被守到。"""
        _actual = {_p.name for _p in self._view_files()}
        _known = {_f for _f, _w, _r in PAGES}
        assert _actual == _known, (
            f"`{_VIEWS_REL}` 的頁面清單變了（多出 {sorted(_actual - _known)}、"
            f"少了 {sorted(_known - _actual)}）—— 請同步本檔的 `PAGES`，"
            "並確認新頁的檔頭沒有抄一份過期的掛載敘述。")

    @pytest.mark.parametrize("view_file,wrapper,render_fn", PAGES)
    def test_no_stale_claim_outside_a_strikethrough(
            self, view_file: str, wrapper: str, render_fn: str):
        _text = _strip_struck(_read(f"{_VIEWS_REL}/{view_file}"))
        _hits = [(_p, _why) for _p, _why in STALE_CLAIMS if _p in _text]
        assert not _hits, (
            f"{view_file} 又出現已知失真的掛載敘述：\n"
            + "\n".join(f"  · {_p!r} —— {_why}" for _p, _why in _hits)
            + "\n\n要保留舊句當病史 → 包進 `~~ ~~`（本 repo 的標準寫法），"
            "並在旁邊寫明更正日期與原因；不要直接刪掉，下一個人要看得出這裡曾經是那樣。")


# ══════════════════════════════════════════════════════════════════════
class TestTheGuardItself:
    """守衛的自證。**一支永遠綠的守衛比沒有守衛更危險。**"""

    def test_it_catches_a_bare_stale_claim(self):
        _text = _strip_struck("檔頭：**本檔沒有 production caller**（本批不接線）。")
        assert any(_p in _text for _p, _ in STALE_CLAIMS)

    def test_a_struck_out_history_line_is_allowed(self):
        _text = _strip_struck("~~**本檔沒有 production caller**~~ 已於 FE-36 更正。")
        assert not any(_p in _text for _p, _ in STALE_CLAIMS)

    def test_the_stripper_handles_a_multi_line_block(self):
        _text = _strip_struck("前~~第一行\n第二行 with tab_find: x\n第三行~~後")
        assert "with tab_find" not in _text and "前" in _text and "後" in _text

    def test_it_is_not_fooled_by_a_merely_similar_sentence(self):
        """不相干的句子不准判紅 —— 會亂紅的守衛最後一定會被關掉。"""
        _text = _strip_struck(
            "本頁的 caller 在 `app.py`；production 走 L3，本檔不自己取數。")
        assert not any(_p in _text for _p, _ in STALE_CLAIMS)

    def test_the_five_real_view_files_are_readable(self):
        for _f, _w, _r in PAGES:
            assert _read(f"{_VIEWS_REL}/{_f}").strip()
