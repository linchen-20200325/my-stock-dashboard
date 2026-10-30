"""tests/test_nav1_shell_nav4.py — NAV-1 L5 `src/ui/views/shell_nav4.py` 守衛（fast lane）。

守什麼：
  1. **單一 SSOT**：頁狀態只有 `_nav4_page` 一格；兩個導覽 widget（桌機側欄／手機底部）都只經 `on_change` 寫它，
     且任一邊選頁，另一邊顯示值同步（AppTest.from_function，不跑整支 app.py）。
  2. 🎯 標的 的第二層（葉）選擇：只在標的頁出現；切頁再切回仍保留。
  3. 元件邊界：無取數、無紅色錯誤框、無 legacy／舊版字樣（DEC-097：legacy 入口不得出現在一般使用者導覽）。
  4. CSS 注入字串守衛：key class、position:fixed、media query、safe-area、print 隱藏，
     且**失效降級良性**（`display:none` 只在桌機／print 的 media 內；預設沒有「靠 CSS 才顯示」的規則）。
"""
from __future__ import annotations

import ast
import pathlib
import re

import pytest

from shared import ia_nav, ia_nav4

_ROOT = pathlib.Path(__file__).resolve().parent.parent
_SHELL = _ROOT / "src" / "ui" / "views" / "shell_nav4.py"
_SRC = _SHELL.read_text(encoding="utf-8")
_TREE = ast.parse(_SRC)


# ══════════════════════════════════════════════════════════════════
# 靜態：邊界
# ══════════════════════════════════════════════════════════════════
def _imports() -> set[str]:
    out = set()
    for n in ast.walk(_TREE):
        if isinstance(n, ast.Import):
            out |= {a.name for a in n.names}
        elif isinstance(n, ast.ImportFrom):
            out.add(n.module or "")
    return out


class TestBoundary:
    def test_imports_are_only_streamlit_l0_and_tokens(self):
        """無取數：不得 import `src.data.*` / requests / proxy / pandas（沿用 shell_nav 的邊界）。"""
        assert _imports() <= {"__future__", "streamlit", "shared", "src.ui_v2.tokens", "sys"}, _imports()

    def test_no_red_error_boxes(self):
        _bad = [n.func.attr for n in ast.walk(_TREE)
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and isinstance(n.func.value, ast.Name) and n.func.value.id == "st"
                and n.func.attr in ("error", "exception", "warning")]
        assert _bad == [], f"導覽元件不得用紅／黃框：{_bad}"

    def test_no_legacy_wording_in_any_string_the_component_can_render(self):
        """DEC-097：legacy／rollback 入口不得出現在一般使用者導覽。docstring / 註解不算（不會被渲染）；其餘字串常數全掃。"""
        _doc_ids = set()
        for n in ast.walk(_TREE):
            if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef)):
                _d = ast.get_docstring(n, clean=False)
                if _d is not None and n.body and isinstance(n.body[0], ast.Expr):
                    _doc_ids.add(id(n.body[0].value))
        for n in ast.walk(_TREE):
            if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in _doc_ids:
                _low = n.value.lower()
                assert "legacy" not in _low and "舊版" not in n.value and "舊 ui" not in _low, (
                    f"元件含 legacy／舊版字樣：{n.value[:60]!r}")

    def test_the_page_state_is_written_only_by_the_declared_functions(self):
        """SSOT 只有一格，且只有 `current_page4`（缺省初始化）與 `_on_nav_change`（回呼）寫它。"""
        _writers = set()
        for fn in [n for n in _TREE.body if isinstance(n, ast.FunctionDef)]:
            for n in ast.walk(fn):
                if (isinstance(n, ast.Assign) and any(
                        isinstance(t, ast.Subscript) and isinstance(t.value, ast.Attribute)
                        and t.value.attr == "session_state"
                        and isinstance(t.slice, ast.Attribute) and t.slice.attr == "NAV4_PAGE_KEY"
                        for t in n.targets)):
                    _writers.add(fn.name)
        assert _writers == {"current_page4", "_on_nav_change"}, _writers

    def test_both_nav_widgets_share_one_callback(self):
        """兩個導覽 widget（側欄、底部）的 `on_change` 同一支 `_on_nav_change`。"""
        _cbs = []
        for n in ast.walk(_TREE):
            if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "radio"):
                for k in n.keywords:
                    if k.arg == "on_change" and isinstance(k.value, ast.Name):
                        _cbs.append(k.value.id)
        # UI-T（2026-10-29）：第三個 widget（標的頁子選單）與其回呼 `_on_leaf_change` 已隨過渡切換移除；兩個導覽 widget 仍共用同一支。
        assert sorted(_cbs) == ["_on_nav_change", "_on_nav_change"], _cbs

    def test_no_streamlit_import_side_effect_at_module_level_besides_css(self):
        """模組層沒有任何 `st.*` 呼叫（import 它不得畫東西）。"""
        for n in _TREE.body:
            for sub in ast.walk(n) if not isinstance(n, ast.FunctionDef) else ():
                assert not (isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute)
                            and isinstance(sub.func.value, ast.Name) and sub.func.value.id == "st"), (
                    f"模組層有 st.{sub.func.attr}(...)")


# ══════════════════════════════════════════════════════════════════
# CSS 字串守衛
# ══════════════════════════════════════════════════════════════════
def _media_blocks(css: str) -> dict[str, str]:
    """`@media (...) { ... }` → {條件: 區塊本文}（本檔 CSS 只有一層巢狀）。"""
    out = {}
    for m in re.finditer(r"@media\s*([^{]+)\{", css):
        depth, i = 1, m.end()
        while depth and i < len(css):
            depth += {"{": 1, "}": -1}.get(css[i], 0)
            i += 1
        out[m.group(1).strip()] = css[m.end():i - 1]
    return out


class TestCss:
    from src.ui.views.shell_nav4 import NAV4_CSS as _CSS   # noqa: E402

    def test_no_unreplaced_placeholder(self):
        assert "@@" not in self._CSS

    def test_uses_the_container_key_class(self):
        assert f".st-key-{ia_nav4.NAV4_BOTTOM_CONTAINER_KEY}" in self._CSS

    def test_fixed_bottom_bar_only_inside_the_narrow_media(self):
        _b = _media_blocks(self._CSS)
        _narrow = next(v for k, v in _b.items() if "max-width" in k)
        _bar_rule = re.search(r"\.st-key-nav4_bottom\{([^}]*)\}", _narrow).group(1)
        assert "env(safe-area-inset-bottom" in _bar_rule, "底部固定列本身必須吃 safe-area（不是只有主內容）"
        for needle in ("position:fixed", "bottom:0", "left:0", "right:0", "z-index",
                       "env(safe-area-inset-bottom", "padding-bottom", "flex-wrap:nowrap"):
            assert needle in _narrow, f"窄螢幕規則缺 {needle}"
        # position:fixed 絕不在任何 media 之外（否則桌機 / CSS 部分失效時也固定）
        _outside = re.sub(r"@media[^{]+\{(?:[^{}]|\{[^{}]*\})*\}", "", self._CSS, flags=re.S)
        assert "position:fixed" not in _outside

    def test_main_content_gets_bottom_padding_so_the_footer_is_not_covered(self):
        _narrow = next(v for k, v in _media_blocks(self._CSS).items() if "max-width" in k)
        assert "stMainBlockContainer" in _narrow and "padding-bottom" in _narrow

    def test_desktop_hides_the_bottom_bar_and_print_hides_it_everywhere(self):
        _b = _media_blocks(self._CSS)
        _desk = next(v for k, v in _b.items() if "min-width" in k)
        assert "display:none" in _desk
        _print = next(v for k, v in _b.items() if k.startswith("print"))
        assert "display:none" in _print

    def test_breakpoints_are_complementary_no_gap(self):
        _b = _media_blocks(self._CSS)
        _mx = int(re.search(r"max-width:\s*(\d+)px", next(k for k in _b if "max-width" in k)).group(1))
        _mn = int(re.search(r"min-width:\s*(\d+)px", next(k for k in _b if "min-width" in k)).group(1))
        assert _mn == _mx + 1, "手機／桌機斷點不互補（會出現兩邊都沒規則或重疊的寬度）"

    # ── 站殼間距（D7=B，DEC-116）：兩條無 media 規則。守衛「規則失效＝回到現況」＋「放寬只到這一條」 ──
    _MAIN = '[data-testid="stMainBlockContainer"]'

    @classmethod
    def _outside_media(cls) -> str:
        return re.sub(r"@media[^{]+\{(?:[^{}]|\{[^{}]*\})*\}", "", re.sub(r"/\*.*?\*/", "", cls._CSS.replace("<style>", "").replace("</style>", ""), flags=re.S), flags=re.S)

    @classmethod
    def _rules(cls, css: str):
        return [(m.group(1).strip(), m.group(2)) for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", css)]

    def test_failure_degradation_is_benign(self):
        """CSS 完全失效 ⇒ 沒有任何規則把導覽藏起來：預設（無 media）**唯一**允許的 `display:none` 是 D7=B 的
        「隱藏 style-only 空容器」那一條（選擇器必須命中 stElementContainer 且帶 `:has(… style:only-child)`；
        導覽本體〔`.st-key-nav4_bottom`／radio〕不是 style-only，不會命中）。其餘 `display:none` 仍只在 media 內。"""
        _outside = self._outside_media()
        for sel, body in self._rules(_outside):
            if "display:none" in body.replace(" ", ""):
                assert "stElementContainer" in sel and ":has(" in sel and "style:only-child" in sel, \
                    f"無 media 的 display:none 只允許 style-only 空容器那一條：{sel}"
                assert "nav4" not in sel and "radio" not in sel and "stSidebar" not in sel, f"不得藏導覽：{sel}"
        _narrow = next(v for k, v in _media_blocks(self._CSS).items() if "max-width" in k)
        # 窄螢幕內只允許「隱藏 radio 圓點」那一條 display:none（導覽本體不得被藏）
        for rule in re.findall(r"([^{}]+)\{[^{}]*display:none[^{}]*\}", _narrow):
            assert "first-child" in rule, f"窄螢幕內不應隱藏導覽本體：{rule.strip()}"

    def test_shell_spacing_padding_top_rule_exists_and_clears_the_header(self):
        """上留白規則必須存在、無 media（桌機＋手機都生效）、且 ≥ stHeader 高度 60px（否則站標被頂欄蓋住）。"""
        _hits = [(s, b) for s, b in self._rules(self._outside_media()) if s == self._MAIN and "padding-top" in b]
        assert len(_hits) == 1, f"應恰有一條無 media 的 stMainBlockContainer padding-top 規則，得 {len(_hits)}"
        _px = int(re.search(r"padding-top:\s*(\d+)px", _hits[0][1]).group(1))
        assert _px >= 60, f"padding-top {_px}px < stHeader 60px，站標會被頂欄蓋住"
        assert "!important" in _hits[0][1]

    def test_shell_spacing_hide_rule_is_scoped_under_main_block_and_style_only(self):
        """隱藏規則：必須 scope 在 stMainBlockContainer 底下（不得是全站裸選擇器）、只命中 style-only 容器。"""
        _hits = [(s, b) for s, b in self._rules(self._outside_media()) if "display:none" in b.replace(" ", "")]
        assert len(_hits) == 1, f"無 media 的 display:none 應恰一條，得 {len(_hits)}"
        _sel = _hits[0][0]
        assert _sel.startswith(self._MAIN), f"隱藏規則必須 scope 在 stMainBlockContainer 底下：{_sel}"
        assert re.search(r'stElementContainer"\]:has\(\[data-testid="stMarkdownContainer"\]\s*>\s*style:only-child\)\s*$', _sel), \
            f"隱藏規則必須只命中 style-only 的 markdown 容器：{_sel}"

    def test_no_rule_depends_on_css_to_show_content(self):
        """沒有「預設隱藏、靠 CSS 才顯示」的規則：無 media 的規則裡，除了那一條 display:none 之外不得有任何 `display:`
        （尤其不得有 display:block/flex/revert 之類把東西「顯示回來」的規則——那代表隱藏是預設、顯示要靠 CSS）。"""
        _disp = [(s, b) for s, b in self._rules(self._outside_media()) if "display:" in b.replace(" ", "")]
        assert len(_disp) == 1 and "display:none" in _disp[0][1].replace(" ", ""), f"無 media 的 display 規則只允許那一條 none：{_disp}"

    def test_colors_come_from_tokens_not_hardcoded_hex_literals_in_the_template(self):
        from src.ui.views import shell_nav4
        assert not re.search(r"#[0-9a-fA-F]{3,8}\b", shell_nav4._CSS_TEMPLATE), "模板內有寫死色碼（應走 ui_v2 token）"


# ══════════════════════════════════════════════════════════════════
# 行為（AppTest.from_function；不載入整支 app.py）
# ══════════════════════════════════════════════════════════════════
def _nav_app():
    import streamlit as st
    from src.ui.views import shell_nav4
    with st.sidebar:
        _v = shell_nav4.render_sidebar_nav()
    shell_nav4.render_main_nav()
    st.markdown(f"VIEW={_v}")
    st.markdown(f"PAGE={st.session_state['_nav4_page']}")


def _run(at=None):
    from streamlit.testing.v1 import AppTest
    _at = at or AppTest.from_function(_nav_app, default_timeout=60)
    _at.run()
    assert not _at.exception, _at.exception
    return _at


def _md(at) -> str:
    return "\n".join(m.value for m in at.markdown)


class TestSingleSsot:
    def test_default_is_market_and_both_widgets_agree(self):
        at = _run()
        assert at.session_state[ia_nav4.NAV4_PAGE_KEY] == ia_nav4.P4_MARKET
        assert at.sidebar.radio(key=ia_nav4.NAV4_WIDGET_SIDE_KEY).value == "📊 市場"
        assert at.radio(key=ia_nav4.NAV4_WIDGET_BOTTOM_KEY).value == "📊 市場"
        assert "VIEW=market" in _md(at)

    def test_options_are_the_clients_four_labels_on_both_widgets(self):
        at = _run()
        _want = ["📊 市場", "🎯 標的", "💼 持股", "👤 我的"]
        assert list(at.sidebar.radio(key=ia_nav4.NAV4_WIDGET_SIDE_KEY).options) == _want
        assert list(at.radio(key=ia_nav4.NAV4_WIDGET_BOTTOM_KEY).options) == _want

    @pytest.mark.parametrize("via", [ia_nav4.NAV4_WIDGET_SIDE_KEY, ia_nav4.NAV4_WIDGET_BOTTOM_KEY])
    @pytest.mark.parametrize("label,page4,view", [
        ("🎯 標的", ia_nav4.P4_TARGET, "find"),
        ("💼 持股", ia_nav4.P4_HOLD, "hold"),
        ("👤 我的", ia_nav4.P4_ME, "me"),
        ("📊 市場", ia_nav4.P4_MARKET, "market"),
    ])
    def test_picking_on_either_widget_writes_the_one_key_and_syncs_the_other(self, via, label, page4, view):
        at = _run()
        (at.sidebar.radio if via == ia_nav4.NAV4_WIDGET_SIDE_KEY else at.radio)(key=via).set_value(label)
        _run(at)
        assert at.session_state[ia_nav4.NAV4_PAGE_KEY] == page4
        assert at.sidebar.radio(key=ia_nav4.NAV4_WIDGET_SIDE_KEY).value == label
        assert at.radio(key=ia_nav4.NAV4_WIDGET_BOTTOM_KEY).value == label
        assert f"VIEW={view}" in _md(at)

    def test_programmatic_ssot_change_is_reflected_in_both_widgets(self):
        """SSOT 被別處改（例如將來的深連結）⇒ 兩個 widget 下一輪都跟著（不是各自記各自的）。"""
        at = _run()
        at.session_state[ia_nav4.NAV4_PAGE_KEY] = ia_nav4.P4_HOLD
        _run(at)
        assert at.sidebar.radio(key=ia_nav4.NAV4_WIDGET_SIDE_KEY).value == "💼 持股"
        assert at.radio(key=ia_nav4.NAV4_WIDGET_BOTTOM_KEY).value == "💼 持股"

    @pytest.mark.parametrize("bad", ["garbage", 123, "", ["x"], "market", 5, {"a": 1}, 1.5, False])
    def test_a_corrupt_ssot_value_is_reset_to_the_default_and_logged_nav_stays(self, bad, capsys):
        """QA 回修 m-1：壞值（垃圾字串／數字／空字串／list／view id 殘值）⇒ 重設為 📊 市場並 log，導覽不消失、
        頁面與導覽狀態一致（原本 Fail Loud 會讓導覽整個消失）。L0 `coerce_page4` 本身仍 Fail Loud（見 test_nav1_ia_nav4）。"""
        from streamlit.testing.v1 import AppTest
        at = AppTest.from_function(_nav_app, default_timeout=60)
        at.session_state[ia_nav4.NAV4_PAGE_KEY] = bad
        at.run()
        assert not at.exception, at.exception
        assert at.session_state[ia_nav4.NAV4_PAGE_KEY] == ia_nav4.P4_MARKET
        assert at.sidebar.radio(key=ia_nav4.NAV4_WIDGET_SIDE_KEY).value == "📊 市場"
        assert at.radio(key=ia_nav4.NAV4_WIDGET_BOTTOM_KEY).value == "📊 市場"
        assert "VIEW=market" in _md(at)
        assert "[nav4]" in capsys.readouterr().err, "重設壞狀態必須留 log"

    def test_a_leftover_leaf_value_from_a_previous_version_is_ignored(self):
        """UI-T（2026-10-29）：舊版 session 若還留著 `_nav4_target_leaf`（NAV-1 過渡切換的殘值），新版必須忽略它、直接渲染 `find`。

        取代舊 `test_a_corrupt_leaf_value_is_reset_to_the_default_leaf_and_logged`：葉機制已移除，壞葉值不再有「重設」可言，
        但「舊殘值不得讓標的頁渲染到別的 view」這個意旨仍要守。
        """
        from streamlit.testing.v1 import AppTest
        at = AppTest.from_function(_nav_app, default_timeout=60)
        at.session_state[ia_nav4.NAV4_PAGE_KEY] = ia_nav4.P4_TARGET
        at.session_state["_nav4_target_leaf"] = "inspect"
        at.run()
        assert not at.exception, at.exception
        assert "VIEW=find" in _md(at) and "VIEW=inspect" not in _md(at)

    def test_no_streamlit_warning_about_session_state_defaults(self):
        at = _run()
        _w = [w.value for w in at.warning]
        assert _w == [], f"導覽觸發 Streamlit 警告（預填值與 default 衝突？）：{_w}"


class TestTargetLeaf:
    """UI-T（2026-10-29，客戶 DEC-099）：NAV-1 過渡切換（標的頁葉選擇器）已移除；標的頁是單一頁。

    原 `test_leaf_selector_only_on_target_page` / `test_leaf_pick_switches_view_and_survives_leaving_and_returning` 作廢
    （它們守的是已被客戶裁示移除的過渡機制），改守「它真的不在了」：沒有子選單 widget、沒有第二組 radio、
    標的頁永遠渲染同一個 view。
    """

    def _to_target(self):
        at = _run()
        at.radio(key=ia_nav4.NAV4_WIDGET_BOTTOM_KEY).set_value("🎯 標的")
        return _run(at)

    def test_no_leaf_selector_anywhere_and_target_is_one_view(self):
        at = _run()
        assert not [r for r in at.radio if "leaf" in str(r.key)]
        at = self._to_target()
        assert not [r for r in at.radio if "leaf" in str(r.key)], "標的頁出現了子選單 radio —— 過渡切換殘留"
        _radios = {r.key for r in at.radio} | {r.key for r in at.sidebar.radio}
        assert _radios == {ia_nav4.NAV4_WIDGET_SIDE_KEY, ia_nav4.NAV4_WIDGET_BOTTOM_KEY}
        assert "VIEW=find" in _md(at)

    def test_target_page_survives_leaving_and_returning(self):
        at = self._to_target()
        at.radio(key=ia_nav4.NAV4_WIDGET_BOTTOM_KEY).set_value("💼 持股")
        _run(at)
        assert "VIEW=hold" in _md(at)
        at.sidebar.radio(key=ia_nav4.NAV4_WIDGET_SIDE_KEY).set_value("🎯 標的")
        _run(at)
        assert "VIEW=find" in _md(at)

    def test_no_red_error_anywhere_in_the_nav(self):
        at = self._to_target()
        assert not at.error
