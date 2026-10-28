"""tests/test_nav1_app_routing.py — NAV-1 `app.py` 路由守衛（靜態 fast ＋ 行為 slow）。

客戶 DEC-097＋2026-10-28 指示：預設＝新版固定四頁主導覽；舊 UI（D2 側欄雙層 radio ＋ 舊 7 頁籤）＝ legacy 模式，
只能用 `?legacy=1` 進入；legacy 入口不得出現在一般使用者導覽；舊程式碼不刪、不破壞 rollback。

守什麼（逐條對應總管規格 D／E／F）：
  靜態（fast）
    S1 旗標在 `st.set_page_config` **之前**算；新 import 全在函式內（late import）；`app.py` module 層沒有 `shared.ia_nav4`／`shell_nav4` import。
    S2 預設分支（`if not _NAV4_LEGACY:`）在 legacy 分支與 `st.tabs(...)` 之前，且內含 `_render_tab_isolated`、`_render_footer`、`st.stop()`。
    S3 legacy 的 D2 radio ＋ 第二層 ＋ 圖例 **包在 `if _NAV4_LEGACY:` 裡，AST 與 HEAD 原文逐節點相同**（只多一層縮排＝一字不變的機械證據）。
    S4 預設模式分支的任何字串常數都不含 legacy／舊版字樣（入口不外洩）。
    S5 `_nav4_reconcile(_IA_VIEWS)` 有呼叫。
  行為（slow，AppTest 整支 app.py）
    B1 預設：新導覽、無舊 radio／「不使用」、無 7 頁籤、無置底條、有免責聲明；既有側欄控制（強制刷新／測試連線／連線狀態）照常。
    B2 四頁各自選到 → 對應 view 被呼叫（view 用假模組替身計數）；🎯 標的 的葉；切頁狀態保留。
    B3 `?legacy=1` → 舊畫面（7 頁籤、D2 radio），且**一個 nav4 模組都沒 import**（rollback 不依賴新元件健康）。
    B4 旗標耐 rerun（網址參數消失仍維持）；`?legacy=0` 清除；空值／亂值不進 legacy。
    B5 導覽元件壞掉 → 紅態顯示，頁面仍渲染（不白屏、不靜默退回舊 UI）。
"""
from __future__ import annotations

import ast
import pathlib
import sys
import types

import pytest

from shared import ia_nav, ia_nav4

_ROOT = pathlib.Path(__file__).resolve().parent.parent
_APP = _ROOT / "app.py"
_SRC = _APP.read_text(encoding="utf-8")
_TREE = ast.parse(_SRC)

#: HEAD（NAV-1 之前）app.py 側欄 D2 導覽區塊的**逐字快照**（第二來源；dedent 後）。
#: 本檔只比 AST（忽略縮排與註解）—— 縮排多一層是 `if _NAV4_LEGACY:` 造成的唯一差異。
_LEGACY_BLOCK_SNAPSHOT = """\
_IA_NAV_CHOICE = st.radio(
    '🆕 新版戰情室（試用中）', _IA_NAV_OPTIONS, index=0, key=_IA_NAV_KEY,
    help='選任一方向 → 主畫面整片換成新版那一頁；選「不使用」→ 回到原本的 7 個頁籤')
_IA_DIR = _ia_nav.direction_from_option(_IA_NAV_CHOICE)
if _IA_DIR is not None:
    _ia_leaves = _ia_nav.NAV_TREE[_IA_DIR]
    if len(_ia_leaves) == 1:
        # 單頁方向(🛡️／👤／⚡)沒有第二層。
        _IA_PAGE = _ia_leaves[0]
    else:
        st.caption(_ia_nav.leaf_subtitle(_IA_DIR))
        _ia_leaf_opts = _ia_nav.leaf_options(_IA_DIR)
        _ia_last = st.session_state.get(_IA_LEAF_LAST_KEY, {})
        _ia_first = _ia_nav.first_built_page(_IA_DIR)
        _ia_start = _ia_last.get(_IA_DIR, _ia_first)
        _ia_idx = _ia_leaves.index(_ia_start) if _ia_start in _ia_leaves else _ia_leaves.index(_ia_first)
        _ia_leaf_choice = st.radio(
            _ia_nav.leaf_subtitle(_IA_DIR), _ia_leaf_opts, index=_ia_idx,
            key=f'{_IA_LEAF_KEY_PREFIX}{_IA_DIR}', label_visibility='collapsed')
        _IA_PAGE = _ia_nav.page_from_leaf_option(_IA_DIR, _ia_leaf_choice)
        if _IA_PAGE is None:
            # §1 Fail Loud:第二層選值對不到任何頁 ⇒ 不靜默退回預設頁。
            raise RuntimeError(
                f'第二層選值 {_ia_leaf_choice!r} 不在 {_IA_DIR!r} 底下:{_ia_leaf_opts}')
        _ia_last = dict(_ia_last)
        _ia_last[_IA_DIR] = _IA_PAGE
        st.session_state[_IA_LEAF_LAST_KEY] = _ia_last
st.caption(_ia_nav.NAV_LEGEND)   # ⬜ ＝ 尚未建置(DEC-090 ③)
st.caption('ⓘ 驗收完成後，這區會取代上方頁籤')
"""


# ══════════════════════════════════════════════════════════════════
# 小工具
# ══════════════════════════════════════════════════════════════════
def _is_name(n, ident):
    return isinstance(n, ast.Name) and n.id == ident


def _module_if_not_legacy() -> ast.If:
    _hits = [n for n in _TREE.body if isinstance(n, ast.If)
             and isinstance(n.test, ast.UnaryOp) and isinstance(n.test.op, ast.Not)
             and _is_name(n.test.operand, "_NAV4_LEGACY")]
    assert len(_hits) == 1, f"module 層 `if not _NAV4_LEGACY:` 應恰一支，實得 {len(_hits)}"
    return _hits[0]


def _legacy_if_in_sidebar() -> ast.If:
    """側欄裡包住 D2 radio 的 `if _NAV4_LEGACY:`（else 分支＝新模式導覽）。"""
    _hits = []
    for w in [n for n in _TREE.body if isinstance(n, ast.With)]:
        for n in w.body:
            if isinstance(n, ast.If) and _is_name(n.test, "_NAV4_LEGACY"):
                _hits.append(n)
    assert len(_hits) == 1, f"側欄內 `if _NAV4_LEGACY:` 應恰一支，實得 {len(_hits)}"
    return _hits[0]


def _lineno_of(needle: str) -> int:
    assert _SRC.count(needle) == 1, (needle, _SRC.count(needle))
    return _SRC[:_SRC.index(needle)].count("\n") + 1


# ══════════════════════════════════════════════════════════════════
# 靜態
# ══════════════════════════════════════════════════════════════════
class TestStatic:
    def test_s1_flag_is_resolved_before_set_page_config(self):
        assert _lineno_of("_NAV4_LEGACY = _nav4_resolve_legacy()") < _lineno_of("st.set_page_config(")

    def test_s1_page_config_keeps_collapsed_for_legacy_and_opens_the_sidebar_for_new_mode(self):
        assert "initial_sidebar_state=('collapsed' if _NAV4_LEGACY else 'auto')" in _SRC

    def test_s1_new_imports_are_late_only(self):
        _fn_nodes = {id(n) for f in ast.walk(_TREE) if isinstance(f, ast.FunctionDef) for n in ast.walk(f)}
        for n in ast.walk(_TREE):
            if isinstance(n, ast.ImportFrom) and (n.module or "") in ("shared.ia_nav4", "src.ui.views.shell_nav4"):
                assert id(n) in _fn_nodes, f"{n.module} 在 module 層被 import（boot 範圍的既有守則：只准函式內 late import）"
        _mods = {n.module for n in ast.walk(_TREE) if isinstance(n, ast.ImportFrom)}
        assert "shared.ia_nav4" in _mods and "src.ui.views.shell_nav4" in _mods, "掃描器壞了：找不到 nav4 import"

    def test_s1_shell_nav4_import_lives_in_exactly_one_ia_view_wrapper(self):
        _owners = [f.name for f in _TREE.body if isinstance(f, ast.FunctionDef)
                   and any(isinstance(n, ast.ImportFrom) and n.module == "src.ui.views.shell_nav4" for n in ast.walk(f))]
        assert _owners == ["_ia_view_nav4"], _owners

    def test_s2_default_branch_precedes_legacy_branch_and_tabs_and_is_isolated(self):
        _b = _module_if_not_legacy()
        _calls = {n.func.id for n in ast.walk(_b) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
        assert {"_render_tab_isolated", "_render_footer"} <= _calls
        _stops = [n for n in ast.walk(_b) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                  and n.func.attr == "stop" and _is_name(n.func.value, "st")]
        assert len(_stops) == 1
        assert _b.lineno < _lineno_of("if _IA_PAGE is not None:") < _lineno_of("tab_market, tab_stocks")
        assert _stops[0].lineno < _lineno_of("_gl_slot = st.empty()")

    def test_s2_default_branch_uses_get_not_subscript_on_the_dispatch_table(self):
        _b = _module_if_not_legacy()
        assert not [n for n in ast.walk(_b) if isinstance(n, ast.Subscript) and _is_name(n.value, "_IA_VIEWS")]
        assert any(isinstance(n, ast.Attribute) and n.attr == "get" and _is_name(n.value, "_IA_VIEWS")
                   for n in ast.walk(_b))

    def test_s2_default_branch_fails_loud_on_an_unknown_view(self):
        _b = _module_if_not_legacy()
        assert any(isinstance(n, ast.Raise) for n in ast.walk(_b))

    def test_s3_legacy_d2_block_is_ast_identical_to_head(self):
        _if = _legacy_if_in_sidebar()
        _now = [ast.dump(n) for n in _if.body]
        _head = [ast.dump(n) for n in ast.parse(_LEGACY_BLOCK_SNAPSHOT).body]
        assert _now == _head, "legacy 模式的 D2 導覽區塊與 HEAD 不同 —— 『legacy＝今天的行為一字不變』被破壞"

    def test_s3_the_d2_radio_exists_only_under_the_legacy_guard(self):
        _radios = [n for n in ast.walk(_TREE) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                   and n.func.attr == "radio" and _is_name(n.func.value, "st")
                   and any(k.arg == "key" and _is_name(k.value, "_IA_NAV_KEY") for k in n.keywords)]
        assert len(_radios) == 1
        _inside = {id(n) for n in ast.walk(_legacy_if_in_sidebar())}
        assert id(_radios[0]) in _inside, "D2 radio 不在 `if _NAV4_LEGACY:` 之內 —— 預設模式會渲染舊 radio"

    def test_s3_new_mode_sidebar_else_branch_sets_ia_page_and_isolates_nav_errors(self):
        _e = _legacy_if_in_sidebar().orelse
        assert _e, "側欄缺新模式分支"
        _t = [n for n in _e if isinstance(n, ast.Try)]
        assert len(_t) == 1
        _assigns = [n.targets[0].id for n in ast.walk(_t[0]) if isinstance(n, ast.Assign)
                    and isinstance(n.targets[0], ast.Name)]
        assert _assigns.count("_IA_PAGE") == 2, "新模式側欄 `_IA_PAGE` 應有『正常解析』與『出錯後退到市場頁』兩處賦值"

    def test_s4_no_legacy_wording_leaks_into_the_default_mode_paths(self):
        def _strings(nodes):
            for top in nodes:
                for n in ast.walk(top):
                    if isinstance(n, ast.Constant) and isinstance(n.value, str):
                        yield n.value
        _paths = [_module_if_not_legacy()] + list(_legacy_if_in_sidebar().orelse)
        for s in _strings(_paths):
            _low = s.lower()
            assert "legacy" not in _low and "舊版" not in s and "不使用" not in s, f"預設模式路徑含 legacy 字樣：{s[:60]!r}"
        _wrapper = next(f for f in _TREE.body if isinstance(f, ast.FunctionDef) and f.name == "_ia_view_nav4")
        for s in _strings([_wrapper]):
            assert "legacy" not in s.lower()

    def test_s5_reconcile_is_called_with_the_dispatch_table(self):
        assert "_nav4_reconcile(_IA_VIEWS)" in _SRC

    def test_the_legacy_param_is_not_a_visible_link_anywhere(self):
        """`?legacy=` 只准出現在註解 / docstring；任何會被渲染的字串都不得含它。"""
        for n in ast.walk(_TREE):
            if isinstance(n, ast.Constant) and isinstance(n.value, str) and "legacy=" in n.value.lower():
                # 唯一允許：函式 docstring（不會被渲染）
                assert len(n.value) > 80, f"疑似可見字串含 legacy 參數：{n.value[:60]!r}"


# ══════════════════════════════════════════════════════════════════
# 行為（slow）
# ══════════════════════════════════════════════════════════════════
_VIEW_MODS = {
    "src.ui.views.page_market": "render_page_market",
    "src.ui.views.page_today": "render_page_today",
    "src.ui.views.page_find": "render_page_find",
    "src.ui.views.page_inspect": "render_page_inspect",
    "src.ui.views.page_hold": "render_page_hold",
    "src.ui.views.page_why": "render_page_why",
    "src.ui.views.page_me": "render_page_me",
}
_SHELL_NAV4 = "src.ui.views.shell_nav4"
_TABS7 = ("🌍 市場環境", "🔬 選股", "🏦 ETF", "🔧 工具箱", "💼 我的持股戰情室", "📁 組合管理", "🧬 AI 問答")


class _Boom(Exception):
    """毒藥：繼承 Exception（理由同 tests/test_ia_v2_sidebar_nav.py::_ViewTouched —— BaseException 會讓 AppTest 卡死）。"""


class _Poison:
    def __init__(self, name):
        self.__name__ = name

    def __getattr__(self, item):
        raise _Boom(f"{self.__name__}.{item} 被碰到了")


@pytest.fixture()
def fake_views(monkeypatch):
    """七個 view 換成假模組：render 只寫一個標記並記一筆（證明『選到哪頁 → 哪頁被呼叫』）。"""
    calls: list[str] = []
    for mod, fn in _VIEW_MODS.items():
        name = mod.rsplit(".", 1)[1]

        def _render(_n=name):
            calls.append(_n)
            import streamlit as _st
            _st.markdown(f"RENDERED={_n}")
            _st.session_state[f"_probe_{_n}"] = _st.session_state.get(f"_probe_{_n}", 0) + 1
        m = types.ModuleType(mod)
        setattr(m, fn, _render)
        monkeypatch.setitem(sys.modules, mod, m)
    return calls


def _app(legacy=None, qp=None):
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(_APP), default_timeout=300)
    if legacy is not None:
        at.session_state[ia_nav4.LEGACY_SESSION_KEY] = legacy
    for k, v in (qp or {}).items():
        at.query_params[k] = v
    return at


def _md(at) -> str:
    return "\n".join(m.value for m in at.markdown)


def _tab_labels(at):
    return [getattr(t, "label", None) for t in at.tabs]


def _all_text(at) -> str:
    parts = [m.value for m in at.markdown] + [c.value for c in at.caption]
    parts += [str(getattr(r, "label", "")) + " ".join(map(str, getattr(r, "options", []))) for r in at.radio]
    parts += [b.label for b in at.button]
    return "\n".join(parts)


@pytest.mark.usefixtures("stub_trading_day_status")
@pytest.mark.slow
class TestDefaultMode:
    def test_b1_default_boots_into_the_four_page_nav(self, fake_views):
        at = _app().run()
        assert not at.exception, at.exception
        _errs = [e.value for e in at.error if not e.value.endswith("❌")]   # 側欄『🔌 連線狀態』燈（測試環境本來就沒有金鑰）不算
        assert not _errs, _errs
        _side = at.sidebar.radio(key=ia_nav4.NAV4_WIDGET_SIDE_KEY)
        assert list(_side.options) == ["📊 市場", "🎯 標的", "💼 持股", "👤 我的"] and _side.value == "📊 市場"
        _bot = at.radio(key=ia_nav4.NAV4_WIDGET_BOTTOM_KEY)
        assert list(_bot.options) == list(_side.options) and _bot.value == "📊 市場"
        assert fake_views == ["page_market"]
        assert "RENDERED=page_market" in _md(at)

    def test_b1_no_old_radio_no_off_option_no_seven_tabs_no_bottom_bar(self, fake_views):
        at = _app().run()
        assert not [r for r in at.radio if r.key in ("_sb_ia_page",) or str(r.key).startswith("_sb_ia_leaf_")], (
            "預設模式不得渲染 D2 導覽 radio（含『不使用』選項）")
        _t = _all_text(at) + "\n".join(c.value for c in at.sidebar.caption)
        assert "不使用（用下方原功能）" not in _t and "新版戰情室（試用中）" not in _t
        _labels = _tab_labels(at)
        for l in _TABS7:
            assert l not in _labels, f"預設模式不該渲染舊頁籤「{l}」"
        assert 'margin-left:auto;">更新：' not in _md(at), "預設模式不該渲染舊全域置底條（讀不到 warroom_summary ⇒ 假訊息）"
        assert "僅供學術研究" in _md(at), "新模式少了頁尾免責聲明"

    def test_b1_existing_sidebar_controls_are_untouched(self, fake_views):
        at = _app().run()
        _keys = {b.key for b in at.sidebar.button}
        assert {"_sb_force_refresh", "sb_conn_test"} <= _keys
        _md_side = "\n".join(m.value for m in at.sidebar.markdown)
        assert "🔐 Google 帳號" in _md_side and "🔌 連線狀態" in _md_side

    def test_b1_the_legacy_flag_does_not_leak_into_the_nav_dom(self, fake_views):
        at = _app().run()
        _nav_text = " ".join(
            " ".join(map(str, r.options)) + str(r.label)
            for r in at.radio if r.key in (ia_nav4.NAV4_WIDGET_SIDE_KEY, ia_nav4.NAV4_WIDGET_BOTTOM_KEY))
        _low = (_all_text(at) + "\n".join(c.value for c in at.sidebar.caption)).lower()
        assert "legacy" not in _low and "?legacy" not in _low
        assert "舊版" not in _nav_text and "legacy" not in _nav_text.lower()
        for l in at.link_button if hasattr(at, "link_button") else []:
            assert "legacy" not in str(getattr(l, "url", "")).lower()

    @pytest.mark.parametrize("label,expect", [
        ("🎯 標的", ["page_market", "page_find"]),
        ("💼 持股", ["page_market", "page_hold"]),
        ("👤 我的", ["page_market", "page_me"]),
    ])
    def test_b2_pick_a_page_calls_that_view_via_either_widget(self, fake_views, label, expect):
        for _w, _side in ((ia_nav4.NAV4_WIDGET_BOTTOM_KEY, False), (ia_nav4.NAV4_WIDGET_SIDE_KEY, True)):
            fake_views.clear()
            at = _app().run()
            fake_views.clear()
            (at.sidebar.radio if _side else at.radio)(key=_w).set_value(label).run()
            assert not at.exception, at.exception
            assert fake_views == [expect[1]], (label, _w, fake_views)

    def test_b2_today_and_why_are_not_reachable_from_the_four_page_nav(self, fake_views):
        at = _app().run()
        for _l in ia_nav4.page4_options():
            at.radio(key=ia_nav4.NAV4_WIDGET_BOTTOM_KEY).set_value(_l).run()
        assert "page_today" not in fake_views and "page_why" not in fake_views

    def test_b2_target_leaf_and_state_are_kept_across_pages(self, fake_views):
        at = _app().run()
        at.radio(key=ia_nav4.NAV4_WIDGET_BOTTOM_KEY).set_value("🎯 標的").run()
        at.radio(key=ia_nav4.NAV4_WIDGET_LEAF_KEY).set_value(ia_nav.page_label("inspect")).run()
        assert "RENDERED=page_inspect" in _md(at)
        at.radio(key=ia_nav4.NAV4_WIDGET_BOTTOM_KEY).set_value("💼 持股").run()
        assert "RENDERED=page_hold" in _md(at)
        assert at.session_state["_probe_page_inspect"] == 1      # 離開頁的 session 資料仍在
        at.sidebar.radio(key=ia_nav4.NAV4_WIDGET_SIDE_KEY).set_value("🎯 標的").run()
        assert "RENDERED=page_inspect" in _md(at), "回到標的頁沒有落在上次的葉"
        assert at.session_state[ia_nav4.NAV4_PAGE_KEY] == ia_nav4.P4_TARGET

    def test_b5_a_broken_nav_component_is_red_but_the_page_still_renders(self, fake_views, monkeypatch):
        monkeypatch.setitem(sys.modules, _SHELL_NAV4, _Poison(_SHELL_NAV4))
        at = _app().run()
        assert not at.exception, "導覽元件壞掉不得讓整頁白屏"
        _errs = " ".join(e.value for e in at.error)
        assert "主導覽" in _errs and _SHELL_NAV4 in _errs, _errs
        _side = " ".join(e.value for e in at.sidebar.error)
        assert "主導覽渲染異常" in _side, f"側欄導覽失敗必須紅態顯示：{_side!r}"
        assert "RENDERED=page_market" in _md(at), "導覽壞掉時頁面內容應仍渲染（退到市場頁）"
        for l in _TABS7:
            assert l not in _tab_labels(at), "導覽壞掉不得靜默退回舊 UI"

    def test_b5_a_broken_view_is_isolated_and_the_nav_survives(self, fake_views, monkeypatch):
        monkeypatch.setitem(sys.modules, "src.ui.views.page_market", _Poison("src.ui.views.page_market"))
        at = _app().run()
        assert not at.exception
        assert any("📊 大盤" in e.value for e in at.error)
        assert at.radio(key=ia_nav4.NAV4_WIDGET_BOTTOM_KEY).value == "📊 市場", "頁壞了不得吞掉導覽"


@pytest.mark.usefixtures("stub_trading_day_status")
@pytest.mark.slow
class TestLegacyMode:
    def test_b3_query_param_enters_the_old_ui_and_never_touches_nav4_modules(self, fake_views, monkeypatch):
        monkeypatch.setitem(sys.modules, _SHELL_NAV4, _Poison(_SHELL_NAV4))
        at = _app(qp={"legacy": "1"}).run()
        assert not at.exception, at.exception
        assert all("shell_nav4" not in e.value for e in at.error)
        _labels = _tab_labels(at)
        for l in _TABS7:
            assert l in _labels, f"legacy 模式少了舊頁籤「{l}」"
        _r = at.sidebar.radio(key="_sb_ia_page")
        assert list(_r.options) == ["不使用（用下方原功能）", *ia_nav.direction_options()] and _r.index == 0
        assert not [r for r in at.radio if str(r.key).startswith("_nav4_w_")]
        assert fake_views == [], "legacy 預設（不使用）不得碰任何 view"
        _cap = [c.value for c in at.sidebar.caption]
        assert ia_nav.NAV_LEGEND in _cap and "ⓘ 驗收完成後，這區會取代上方頁籤" in _cap

    def test_b3_legacy_d2_navigation_still_works_end_to_end(self, fake_views):
        at = _app(legacy=True).run()
        at.sidebar.radio(key="_sb_ia_page").set_value(ia_nav.direction_options()[0]).run()
        assert not at.exception, at.exception
        assert fake_views[-1] in ("page_market",)
        assert any("📍 位置：" in c.value for c in at.caption)

    def test_b4_flag_survives_reruns_without_the_query_param(self, fake_views):
        at = _app(qp={"legacy": "1"}).run()
        assert at.session_state[ia_nav4.LEGACY_SESSION_KEY] is True
        del at.query_params["legacy"]
        at.run()
        assert at.session_state[ia_nav4.LEGACY_SESSION_KEY] is True
        for l in _TABS7:
            assert l in _tab_labels(at)

    def test_b4_legacy_zero_clears_the_flag(self, fake_views):
        at = _app(legacy=True).run()
        at.query_params["legacy"] = "0"
        at.run()
        assert at.session_state[ia_nav4.LEGACY_SESSION_KEY] is False
        assert at.sidebar.radio(key=ia_nav4.NAV4_WIDGET_SIDE_KEY).value == "📊 市場"
        for l in _TABS7:
            assert l not in _tab_labels(at)

    @pytest.mark.parametrize("val", ["", "yes", "true", "2"])
    def test_b4_empty_or_garbage_never_enters_legacy(self, fake_views, val):
        at = _app(qp={"legacy": val}).run()
        assert not at.exception
        assert at.session_state[ia_nav4.LEGACY_SESSION_KEY] is False
        assert "RENDERED=page_market" in _md(at)


@pytest.mark.usefixtures("stub_trading_day_status")
@pytest.mark.slow
class TestRealViewsMountUnderTheNewNav:
    """不用替身：四頁（含標的兩葉）在新導覽下用**真的 view** mount，不得有 uncaught exception 或被隔離器接住的紅框。"""

    def test_each_page_and_leaf_mounts_with_real_views(self):
        at = _app().run()
        assert not at.exception, at.exception
        def _isolated_errors():
            return [e.value for e in at.error if "分頁渲染異常" in e.value]
        assert not _isolated_errors(), _isolated_errors()
        _steps = [("🎯 標的", None), ("🎯 標的", ia_nav.page_label("inspect")), ("💼 持股", None), ("👤 我的", None), ("📊 市場", None)]
        for _page, _leaf in _steps:
            at.radio(key=ia_nav4.NAV4_WIDGET_BOTTOM_KEY).set_value(_page).run()
            if _leaf is not None:
                at.radio(key=ia_nav4.NAV4_WIDGET_LEAF_KEY).set_value(_leaf).run()
            assert not at.exception, (_page, _leaf, at.exception)
            assert not _isolated_errors(), (_page, _leaf, _isolated_errors())
            assert "僅供學術研究" in _md(at)
