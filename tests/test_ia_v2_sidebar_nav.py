"""tests/test_ia_v2_sidebar_nav.py — FE-35 側欄導覽守衛（客戶 2026-09-08 拍板方案 A）。

═══ 這支存在的理由（是一次真實的線上事故，不是潔癖）════════════════════
FE-7~FE-16 把 IA v2 五頁**掛成第 1~5 個頂層頁籤**與舊的 7 個並存。
**程式碼一行都沒刪**（12 個頁籤全都在、全都渲染），但客戶在手機上看到頁籤列
7→12、舊的 7 個被擠出可視範圍，回報「**很多 Tab 不見了**」。

⇒ **雙軌並行保住了程式碼，沒保住畫面。** 那一輪每一支測試都是綠的 ——
因為當時沒有任何一支在看「客戶原本的 7 個頁籤還在不在、還是不是那個順序」。

客戶核定的修法（方案 A）三件事，本檔逐件釘住：
  1. 頂層頁籤列**還原成客戶原本的 7 個**（名稱 / 順序 / 變數名照舊）。
  2. 五頁改由側欄 radio 導覽，預設「不使用」＝ 畫面完全等同 FE-7 之前。
  3. **沒選就一行都不跑**（lazy）；選了新頁則**整條全域置底條不渲染**。

═══ 第 3 件為什麼非釘不可（§1 Fail Loud）══════════════════════════════
全域置底常駐條讀的 `warroom_summary` 是在 `with tab_market:` 裡的
`render_traffic_light_top()` 才寫入的。舊頁籤不渲染時那個 key 不存在 ⇒
bar **必然**退回「⬜ 總經未評估 / 建議持股 --」。`app.py` 的 `_gl_slot` 病史
註解記載那正是 **v19.171 🔴-1** 那次線上實機驗收抓到的事故形態
（「置底條實質永遠停在『未評估』」）。在新頁上掛一條屬於舊 IA、而且必然
說假話的 bar，就是 §1 的假訊息 ⇒ 整條不出現，不是畫成灰色、也不是改文案。

═══ 兩個 lane，刻意分開 ═══════════════════════════════════════════════
· **靜態（預設 lane）**：AST 掃 `app.py`。跑得快、每次 CI 都跑，
  擋的是「有人把頁籤順序改回去 / 把 view import 提到 module level」。
· **行為（`@pytest.mark.slow`）**：真的用 `AppTest` 跑整支 `app.py`。
  擋的是靜態掃不到的事 —— 五頁**真的**沒有被執行、置底條**真的**沒有畫出來。
  毒藥手法比照 `tests/test_p04_hold_view.py::TestTheAiCostsNothingUntilYouPress`
  （`_PoisonModule` 一被取屬性就爆，且**不繼承 `Exception`** —— 繼承的話會被
  `_render_tab_isolated` 的 `except Exception` 吞掉，測試照樣綠而其實已經跑過了）。

⚠️ **本檔的 7 個頁籤名是寫死的第二來源，刻意不從 `app.py` 讀出來自己比自己。**
   從被測檔讀出來再比，等於「改壞了兩邊一起改」—— 那正是 FE-7 那一輪的失效模式。
"""
from __future__ import annotations

import ast
import pathlib
import sys

import pytest

from shared.ia_nav import PAGE_LABELS

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_APP = _ROOT / "app.py"
_SRC = _APP.read_text(encoding="utf-8")
_TREE = ast.parse(_SRC, filename=str(_APP))

#: **客戶原本就有的 7 個頂層頁籤**（FE-7 之前的畫面）。
#: 寫死在這裡當第二來源 —— 名稱、順序都算，改任一個都要當場紅燈。
_CLIENT_TABS = (
    "🌍 市場環境",
    "🔬 選股",
    "🏦 ETF",
    "🔧 工具箱",
    "💼 我的持股戰情室",
    "📁 組合管理",
    "🧬 AI 問答",
)

#: 這 7 個頁籤的**變數名**同樣照舊 —— 下游 `with tab_X:` 全靠它們。
_CLIENT_TAB_VARS = (
    "tab_market", "tab_stocks", "tab_etf_main", "tab_tools",
    "tab_warroom", "tab_mgmt", "tab_ai",
)

#: 側欄 radio 的 key 與「不使用」選項（顯示字串屬客戶核定線框，一併釘住）。
_NAV_KEY = "_sb_ia_page"
_NAV_OFF = "不使用（用下方原功能）"

#: 五頁的 view 模組（**顯示名 SSOT 在 L0 `shared/ia_nav.PAGE_LABELS`**，不在這裡抄）。
_VIEW_MODULES = (
    "src.ui.views.page_today",
    "src.ui.views.page_find",
    "src.ui.views.page_inspect",
    "src.ui.views.page_hold",
    "src.ui.views.page_why",
)


# ══════════════════════════════════════════════════════════════════
# 共用小工具（AST）
# ══════════════════════════════════════════════════════════════════
def _is_st_call(node: ast.AST, attr: str) -> bool:
    return (isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == attr
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "st")


def _top_level_tabs_assign() -> ast.Assign:
    """module 層唯一的 `... = st.tabs([...])`（子分頁那幾支都在 `with` 裡，不會命中）。"""
    _hits = [n for n in _TREE.body
             if isinstance(n, ast.Assign) and _is_st_call(n.value, "tabs")]
    assert len(_hits) == 1, (
        f"module 層的 `st.tabs(...)` 應該只有一支（頂層頁籤列），實得 {len(_hits)} 支")
    return _hits[0]


def _nav_branch() -> ast.If:
    """module 層的 `if _IA_PAGE is not None:` —— 新版戰情室的整片換頁分支。"""
    _hits = []
    for _n in _TREE.body:
        if not isinstance(_n, ast.If) or not isinstance(_n.test, ast.Compare):
            continue
        _t = _n.test
        if (isinstance(_t.left, ast.Name) and _t.left.id == "_IA_PAGE"
                and len(_t.ops) == 1 and isinstance(_t.ops[0], ast.IsNot)
                and isinstance(_t.comparators[0], ast.Constant)
                and _t.comparators[0].value is None):
            _hits.append(_n)
    assert len(_hits) == 1, (
        f"找不到（或找到多支）`if _IA_PAGE is not None:` 分支，實得 {len(_hits)}")
    return _hits[0]


def _module_level_funcs() -> dict[str, ast.FunctionDef]:
    return {n.name: n for n in _TREE.body if isinstance(n, ast.FunctionDef)}


# ══════════════════════════════════════════════════════════════════
# ① 客戶原本的 7 個頁籤 —— 名稱、順序、變數名
# ══════════════════════════════════════════════════════════════════
class TestTheSevenTabsAreExactlyTheClientsOnes:
    """**FE-7 那一輪唯一沒有人在看的東西。**

    ⚠️ 這一組的期望值寫死在本檔（`_CLIENT_TABS`），**不從 `app.py` 讀** ——
    從被測檔取值再比，是「自己比自己」，改壞了照樣綠。
    """

    def test_the_tab_labels_and_their_order_are_unchanged(self):
        _call = _top_level_tabs_assign().value
        assert len(_call.args) == 1 and isinstance(_call.args[0], ast.List), (
            "頂層 `st.tabs(...)` 的參數不再是一個字面 list —— "
            "改成變數/推導式會讓本守衛看不到頁籤名，請改回字面 list")
        _labels = []
        for _el in _call.args[0].elts:
            assert isinstance(_el, ast.Constant) and isinstance(_el.value, str), (
                f"頁籤名不是字串字面值：{ast.dump(_el)[:120]}")
            _labels.append(_el.value)
        assert tuple(_labels) == _CLIENT_TABS, (
            f"頂層頁籤列與客戶原本的 7 個對不起來。\n"
            f"  現在：{_labels}\n  客戶原本：{list(_CLIENT_TABS)}\n"
            f"⚠️ 名稱、順序都算。客戶 2026-09-08 拍板方案 A 就是要它一字不動。")

    def test_the_tab_variable_names_are_unchanged(self):
        """變數名照舊 —— 下游每一個 `with tab_X:` 都綁在這些名字上。"""
        _targets = _top_level_tabs_assign().targets
        assert len(_targets) == 1 and isinstance(_targets[0], ast.Tuple)
        _names = [n.id for n in _targets[0].elts if isinstance(n, ast.Name)]
        assert tuple(_names) == _CLIENT_TAB_VARS, (
            f"頁籤變數名變了：{_names} != {list(_CLIENT_TAB_VARS)}")

    def test_every_tab_variable_still_has_a_with_block(self):
        """有頁籤沒有 `with` 區塊 ＝ 空白分頁（v18.439 那次事故的形態）。"""
        for _v in _CLIENT_TAB_VARS:
            assert f"with {_v}:" in _SRC, f"app.py 缺 `with {_v}:` → 該分頁空白"

    def test_the_five_new_pages_are_not_top_level_tabs_any_more(self):
        """**這一條就是客戶回報的那個 bug 的反向釘子。**

        五頁的名字**不准**再出現在頂層頁籤列裡 —— 掛回去 = 頁籤列又變 12 個，
        手機上舊的 7 個又會被擠出畫面。
        """
        _labels = [e.value for e in _top_level_tabs_assign().value.args[0].elts]
        _back = sorted(set(_labels) & set(PAGE_LABELS.values()))
        assert _back == [], (
            f"五頁又被掛回頂層頁籤列：{_back} —— 那正是客戶回報「很多 Tab 不見了」的成因")
        assert len(_labels) == 7, f"頂層頁籤應為 7 個，實得 {len(_labels)}"


# ══════════════════════════════════════════════════════════════════
# ② 側欄導覽區本身
# ══════════════════════════════════════════════════════════════════
class TestTheSidebarNav:
    """radio 的 key / 預設值 / 選項組成 —— 全部照客戶核定的線框。"""

    def _radio_call(self) -> ast.Call:
        _hits = [n for n in ast.walk(_TREE)
                 if _is_st_call(n, "radio")
                 and any(k.arg == "key" and isinstance(k.value, ast.Name)
                         and k.value.id == "_IA_NAV_KEY" for k in n.keywords)]
        assert len(_hits) == 1, f"找不到（或找到多支）新版戰情室導覽 radio：{len(_hits)}"
        return _hits[0]

    def test_the_session_key_is_the_declared_one_and_collides_with_nothing(self):
        """key 撞了就是**弄壞既有 widget**（Streamlit 會沿用前一個元件的狀態）。"""
        assert f"_IA_NAV_KEY = '{_NAV_KEY}'" in _SRC, (
            f"導覽 radio 的 key 常數不再是 {_NAV_KEY!r}")
        # 全 production 樹只准出現一次（就是那行常數定義）。
        _files = [_APP, *sorted((_ROOT / "src").rglob("*.py")),
                  *sorted((_ROOT / "shared").rglob("*.py"))]
        _hits = [(str(p.relative_to(_ROOT)), p.read_text(encoding="utf-8").count(_NAV_KEY))
                 for p in _files if _NAV_KEY in p.read_text(encoding="utf-8")]
        assert _hits == [("app.py", 1)], (
            f"{_NAV_KEY!r} 在 production 樹出現的位置不只常數定義一處：{_hits}")

    def test_the_default_is_the_off_option(self):
        """預設必須是「不使用」—— 預設選到新頁 = 客戶一開 app 就找不到原本的功能。"""
        assert f"_IA_NAV_OFF = '{_NAV_OFF}'" in _SRC, (
            f"「不使用」選項的文案變了（線框定的是 {_NAV_OFF!r}）")
        _idx = [k for k in self._radio_call().keywords if k.arg == "index"]
        assert len(_idx) == 1 and isinstance(_idx[0].value, ast.Constant), "radio 未釘 index"
        assert _idx[0].value.value == 0, "radio 預設不是第 0 個（＝「不使用」）"
        assert "_IA_NAV_OPTIONS = (_IA_NAV_OFF, *_IA_PAGE_LABELS.values())" in _SRC, (
            "選項組成變了：必須是「不使用」+ L0 `shared/ia_nav.PAGE_LABELS`（SSOT），"
            "不得在 app.py 手抄五頁名稱")

    def test_the_page_names_come_from_the_l0_ssot_not_a_hand_copy(self):
        """五頁顯示名只准有一份（§2.1）—— `app.py` 手抄第二份就會與 L0 漂移。"""
        _aliases = {a.name: a.asname for n in ast.walk(_TREE)
                    if isinstance(n, ast.ImportFrom) and n.module == "shared.ia_nav"
                    for a in n.names}
        assert _aliases.get("PAGE_LABELS") == "_IA_PAGE_LABELS", (
            f"app.py 沒有從 L0 `shared/ia_nav` 取 `PAGE_LABELS`：{_aliases}")
        for _label in PAGE_LABELS.values():
            assert f"'{_label}'" not in _SRC and f'"{_label}"' not in _SRC, (
                f"app.py 手抄了五頁顯示名 {_label!r} —— 名稱 SSOT 在 shared/ia_nav.py")


# ══════════════════════════════════════════════════════════════════
# ③ 沒選就一行都不跑（靜態半）
# ══════════════════════════════════════════════════════════════════
class TestNothingRunsUntilYouPickStatic:
    """`import` 一旦提到 module level，五頁就會在**每一次** app run 全部載入。

    那不只是慢：五頁的 module import 會把整條 L3/L2 依賴鏈拉起來，
    等於「不使用」也付新版的成本 —— 客戶核定的行為是「完全等同今天之前的樣子」。
    """

    def test_no_module_level_import_of_any_view(self):
        _fn_nodes = {id(n) for f in _module_level_funcs().values()
                     for n in ast.walk(f)}
        _bad = [n.module for n in ast.walk(_TREE)
                if isinstance(n, ast.ImportFrom)
                and (n.module or "").startswith("src.ui.views")
                and id(n) not in _fn_nodes]
        assert _bad == [], f"app.py 在函式外 import 了 view：{_bad}（每次 rerun 都會載入）"

    def test_each_view_import_lives_in_its_own_wrapper(self):
        _funcs = _module_level_funcs()
        for _mod in _VIEW_MODULES:
            _owners = [name for name, f in _funcs.items()
                       if any(isinstance(n, ast.ImportFrom) and n.module == _mod
                              for n in ast.walk(f))]
            assert len(_owners) == 1 and _owners[0].startswith("_ia_view_"), (
                f"{_mod} 的 import 不在唯一的 `_ia_view_*` wrapper 裡：{_owners}")

    def test_the_dispatch_table_is_only_read_inside_the_branch(self):
        """`_IA_VIEWS[...]` 只准在 `if _IA_PAGE is not None:` 裡被取用。"""
        assert _SRC.count("_IA_VIEWS[") == 1, (
            f"`_IA_VIEWS[` 出現 {_SRC.count('_IA_VIEWS[')} 次 —— "
            "多一處取用就多一條繞過 gate 的路")
        _branch = _nav_branch()
        assert any(isinstance(n, ast.Subscript) and isinstance(n.value, ast.Name)
                   and n.value.id == "_IA_VIEWS" for n in ast.walk(_branch)), (
            "`_IA_VIEWS[...]` 不在 `if _IA_PAGE is not None:` 分支內")

    def test_the_dispatch_table_is_reconciled_with_the_l0_ssot(self):
        """漏一頁要當場炸（§1），不是靜默少一個選項。"""
        assert "if set(_IA_VIEWS) != set(_IA_PAGE_LABELS):" in _SRC, (
            "app.py 少了 `_IA_VIEWS` 與 `PAGE_LABELS` 的對帳")
        assert "raise RuntimeError(" in _SRC, (
            "對帳改回 `assert` 了 —— `python -O` 會把它整條拿掉，等於這道防線消失")
        # 頁 id 也不准手抄（SSOT 在 shared/ia_nav.py）
        for _pid in PAGE_LABELS:
            assert f"'{_pid}': _ia_view_" not in _SRC, (
                f"`_IA_VIEWS` 手抄了頁 id {_pid!r} —— 請用 shared/ia_nav 的常數")

    def test_the_branch_uses_the_existing_isolator_not_a_second_one(self):
        """§1：import / render 失敗要**紅態顯示**，且沿用既有隔離器（不另立第二套）。"""
        _branch = _nav_branch()
        _calls = [n.func.id for n in ast.walk(_branch)
                  if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)]
        assert "_render_tab_isolated" in _calls, (
            "新頁沒有走既有的 `_render_tab_isolated` —— "
            "import 失敗會白屏全站，或被人另寫一套隔離器")
        assert "_render_footer" in _calls, "新頁少了頁尾免責聲明（法遵文字不分頁面）"
        # 隔離器本體沒有被改寬（吞掉錯誤就不是 fail loud 了）
        _iso = _module_level_funcs()["_render_tab_isolated"]
        _src_iso = ast.get_source_segment(_SRC, _iso) or ""
        assert "st.error(" in _src_iso, "隔離器不再用 st.error 紅態顯示"
        assert "format_exc()" in _src_iso, "隔離器不再印完整 traceback"


# ══════════════════════════════════════════════════════════════════
# ④ 選新頁 → 頁籤列與置底條都不渲染（靜態半）
# ══════════════════════════════════════════════════════════════════
class TestTheOldChromeIsNotRenderedOnANewPage:
    """`st.stop()` 之後的 module 層敘述在該分支下**執行不到** —— 這是靜態可證的部分。"""

    def _stop_lineno(self) -> int:
        _stops = [n for n in ast.walk(_nav_branch()) if _is_st_call(n, "stop")]
        assert len(_stops) == 1, f"分支內的 `st.stop()` 應有且僅有一支，實得 {len(_stops)}"
        return _stops[0].lineno

    def test_the_tab_bar_is_created_after_the_stop(self):
        assert _top_level_tabs_assign().lineno > self._stop_lineno(), (
            "`st.tabs(...)` 跑在 `st.stop()` 之前 —— 選了新頁還是會畫出頁籤列")

    def test_the_bottom_bar_is_both_created_and_filled_after_the_stop(self):
        """置底條的**佔位**與**填充**都要在 stop 之後（只擋一半 = 空白 bar 或假訊息）。"""
        _stop = self._stop_lineno()
        for _needle, _why in (("_gl_slot = st.empty()", "置底條的佔位"),
                              ("_gl_slot.markdown(", "置底條的填充")):
            _line = _SRC[:_SRC.index(_needle)].count("\n") + 1
            assert _line > _stop, (
                f"{_why}（{_needle}）在 `st.stop()` 之前 —— 選新頁時它會渲染，"
                "而 `warroom_summary` 不存在 ⇒ 必然印「⬜ 總經未評估」＝ §1 假訊息")

    def test_the_bottom_bar_reader_is_still_the_deferred_one(self):
        """反向釘子：v19.171 的延後填充手法沒有被改回 module 層當場算。"""
        assert "_gl_slot = st.empty()" in _SRC and "_gl_slot.markdown(" in _SRC


# ══════════════════════════════════════════════════════════════════
# ⑤ 行為 lane（slow）：真的跑一遍 app.py
# ══════════════════════════════════════════════════════════════════
class _ViewTouched(Exception):
    """毒藥：view 模組一被取屬性就引爆。

    ═══ 為什麼**繼承 `Exception`**，而不是照 `tests/test_p04_hold_view.py`
        `TestTheAiCostsNothingUntilYouPress` 那樣用 `BaseException` ═══════
    那一支毒藥不繼承 `Exception`，是為了穿過被測函式自己的 `except Exception`
    （不然「其實打了、但被吞成一則錯誤字串」會假綠燈）。**那個理由在這裡不成立，
    而且反效果**：本檔是拿 `AppTest` 跑整支 `app.py`，而 Streamlit 的
    `exec_func_with_error_handling`（`runtime/scriptrunner/exec_code.py`）也只
    `except Exception` —— `BaseException` 會直接打死 script thread，
    `AppTest.run()` 收不到完成事件而**無限期卡住**。
    ⚠️ 2026-09-08 實測：把「預設就跑頁1」這個突變裝上去、配 `BaseException` 版毒藥，
    該測試跑超過 5 分鐘仍未回，`default_timeout=300` 也沒有把它拉回來 ——
    **守衛從「當場紅燈」退化成「CI 掛住」**，那不是更嚴格，是更差。

    ⚠️ **改用 `Exception` 版沒有放寬檢查**，因為本檔的斷言同時看**兩條通道**：
      · `at.exception` —— 沒有被任何 try 包住的取用（例如 module level import）；
      · `at.error`     —— 被 `_render_tab_isolated` 接住、印成紅字的取用。
    兩條都乾淨才算「一行都沒跑」。單看 `at.exception` 才會有那個假綠燈。
    """


class _PoisonModule:
    """任何屬性取用都當場引爆的假模組（同 `tests/test_p04_hold_view.py`）。"""

    def __init__(self, name: str) -> None:
        self.__name__ = name

    def __getattr__(self, item: str):
        raise _ViewTouched(f"{self.__name__}.{item} 被碰到了")


#: 置底條那一段 HTML 獨有的特徵（「更新：<時間>」靠右那一格）。
_BOTTOM_BAR_MARK = 'margin-left:auto;">更新：'
#: 讓置底條的 gate（`if (_mkt_top or _jq_top) and not _is_refreshing`）成立的最小 session。
#: 不塞這個的話冷啟動兩條路徑都不會畫 bar，測試就沒有鑑別力。
_SEED = {"mkt_info": {"regime": "unknown"}, "jingqi_info": {"avg": 50.0},
         "cl_ts": "2026-09-08 10:00"}


def _run_app(page: str | None = None, seed: bool = False):
    from streamlit.testing.v1 import AppTest

    _at = AppTest.from_file(str(_APP), default_timeout=300)
    if seed:
        for _k, _v in _SEED.items():
            _at.session_state[_k] = _v
    if page is not None:
        _at.session_state[_NAV_KEY] = page
    _at.run()
    return _at


def _markdown(at) -> str:
    return "\n".join(m.value for m in at.markdown)


@pytest.fixture()
def poisoned(monkeypatch):
    for _m in _VIEW_MODULES:
        monkeypatch.setitem(sys.modules, _m, _PoisonModule(_m))
    return _VIEW_MODULES



@pytest.mark.slow
class TestNothingRunsUntilYouPick:
    """**靜態掃不到的那一半**：預設態下五頁一行都沒有真的被執行。"""

    def test_the_default_run_touches_no_view_at_all(self, poisoned):
        """**兩條通道都要乾淨**（只看其中一條就會有假綠燈，理由見 `_ViewTouched`）。"""
        _at = _run_app()
        assert not _at.exception, (
            f"預設「不使用」卻碰到了新版五頁（毒藥在 try 之外引爆）：{_at.exception}")
        _errs = " ".join(e.value for e in _at.error)
        for _m in _VIEW_MODULES:
            assert _m not in _errs, (
                f"預設「不使用」卻跑了 {_m} —— 毒藥被 `_render_tab_isolated` "
                f"接住印成紅字了：{_errs[:300]}")
        _labels = [getattr(t, "label", None) for t in _at.tabs]
        for _l in _CLIENT_TABS:
            assert _l in _labels, f"預設態少了客戶原本的頁籤「{_l}」"
        for _l in PAGE_LABELS.values():
            assert _l not in _labels, f"預設態不該渲染新版頁「{_l}」"

    def test_picking_a_page_really_reaches_the_view_and_fails_loud(
            self, poisoned):
        """**反證 ＋ §1 紅態**（一條打兩件事）。

        · 反證：同一組毒藥下，選了那一頁就一定走到 view 的 import ——
          上一條的「沒碰到」才不是因為毒藥根本沒裝上去。
        · §1：那個失敗**是紅色的**（`st.error`），而且**沒有**靜默退回
          「不使用」—— 退回去的話使用者會以為自己沒選到，而畫面又長得像沒事。
        """
        _at = _run_app(page=PAGE_LABELS["today"])
        _errs = " ".join(e.value for e in _at.error)
        assert "src.ui.views.page_today" in _errs, (
            f"選了「{PAGE_LABELS['today']}」卻沒走到該頁的 import，"
            f"或失敗沒有紅態顯示：errors={_errs!r} exception={_at.exception}")
        _labels = [getattr(t, "label", None) for t in _at.tabs]
        for _l in _CLIENT_TABS:
            assert _l not in _labels, (
                f"新頁掛掉後靜默退回了舊的 7 個頁籤（看到「{_l}」）—— "
                "§1：要紅態說出來，不是假裝使用者沒選")


@pytest.mark.slow
class TestPickingAPageReplacesTheWholeMainArea:
    """選新頁 → 頁籤列與置底條都不出現；免責聲明照出。"""

    def test_no_tab_bar_and_no_bottom_bar(self):
        _at = _run_app(page=PAGE_LABELS["today"], seed=True)
        assert not _at.exception, f"新頁 mount 有 uncaught exception：{_at.exception}"
        _labels = [getattr(t, "label", None) for t in _at.tabs]
        for _l in _CLIENT_TABS:
            assert _l not in _labels, f"選了新頁還是畫出頁籤「{_l}」"
        assert _BOTTOM_BAR_MARK not in _markdown(_at), (
            "選了新頁還是渲染了全域置底條 —— 它讀的 `warroom_summary` 這時不存在，"
            "必然顯示「⬜ 總經未評估」＝ §1 假訊息（v19.171 🔴-1 的事故形態）")

    def test_the_footer_disclaimer_survives(self):
        _at = _run_app(page=PAGE_LABELS["today"], seed=True)
        assert "僅供學術研究" in _markdown(_at), "新頁少了頁尾免責聲明"

    def test_the_bottom_bar_still_shows_on_the_default_path(self):
        """**鑑別力對照組**：同一份 seed 走「不使用」時 bar 是畫得出來的。

        沒有這一條的話，上面那個「bar 不見了」也可能只是 seed 沒生效。
        """
        _at = _run_app(seed=True)
        assert not _at.exception, f"預設路徑 mount 有 uncaught exception：{_at.exception}"
        assert _BOTTOM_BAR_MARK in _markdown(_at), (
            "「不使用」路徑的置底條不見了 —— 客戶核定的是『完全等同今天之前的樣子』")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
