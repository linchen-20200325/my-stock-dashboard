"""tests/test_ia_nav_shell.py — D2 導覽殼（DEC-089 G1＝C／DEC-090 形式 (b)）的守衛。

涵蓋：六方向 × 葉對映完整無漏、佔位頁文案（逐字依線框 §4 ＋ ⑨）、`where_to_find` 新增方向層、
`reconcile_nav` 的 RuntimeError 守衛、殼的畫面態（slow lane 跑整支 app.py）。

⚠️ 期望值**寫死在本檔當第二來源**，不從被測模組讀出來自己比自己。
"""
from __future__ import annotations

import ast
import pathlib

import pytest

from shared import ia_nav
from shared.ia_nav4 import LEGACY_SESSION_KEY

_ROOT = pathlib.Path(__file__).resolve().parents[1]

#: 客戶核准的對映（線框 §3.1）。寫死。
_TREE = {
    "dir_market": ("market", "today"),
    "dir_target": ("find", "inspect"),
    "dir_action": ("action",),
    "dir_hold": ("hold",),
    "dir_me": ("me",),
    "dir_data": ("why", "data_center"),
}
_DIR_LABELS = ["📊 大盤", "🎯 標的", "⚡ 行動", "🛡️ 持股", "👤 我的", "🩺 資料中心"]
_VIEW_IDS = {"market", "today", "find", "inspect", "hold", "why", "me"}


# ══ 六方向 × 葉 ═══════════════════════════════════════════════════════════
class TestSixDirectionsTree:
    def test_directions_order_and_labels(self):
        assert list(ia_nav.DIRECTION_LABELS.values()) == _DIR_LABELS
        assert list(ia_nav.NAV_TREE) == list(_TREE)

    def test_tree_is_exactly_the_approved_mapping(self):
        assert {d: tuple(p) for d, p in ia_nav.NAV_TREE.items()} == _TREE

    def test_all_seven_current_pages_are_leaves_exactly_once_none_dropped(self):
        _flat = [p for ps in ia_nav.NAV_TREE.values() for p in ps]
        assert set(ia_nav.PAGE_LABELS) == _VIEW_IDS, "現行 7 頁被動過"
        assert _VIEW_IDS <= set(_flat), f"漏接的頁：{_VIEW_IDS - set(_flat)}"
        assert len(_flat) == len(set(_flat)) == 9      # 7 頁 + 2 佔位
        assert set(_flat) - _VIEW_IDS == {"action", "data_center"}

    def test_built_before_unbuilt_inside_each_direction_and_default_landing(self):
        assert ia_nav.first_built_page("dir_data") == "why"         # 進 🩺 先落在 📖 憑什麼（線框 §3.7 S7）
        assert ia_nav.first_built_page("dir_market") == "market"
        assert ia_nav.first_built_page("dir_target") == "find"
        assert ia_nav.NAV_TREE["dir_data"][-1] == "data_center"     # 未建的排後面

    def test_unbuilt_marks(self):
        assert ia_nav.direction_options() == (
            "📊 大盤", "🎯 標的", "⚡ 行動 ⬜", "🛡️ 持股", "👤 我的", "🩺 資料中心")
        assert ia_nav.leaf_options("dir_data") == ("📖 憑什麼", "🩺 資料中心 ⬜")
        assert ia_nav.leaf_options("dir_market") == ("📊 大盤", "🚦 今天")
        assert ia_nav.NAV_LEGEND == "⬜ ＝ 尚未建置"
        assert ia_nav.leaf_subtitle("dir_target") == "🎯 標的 底下："

    def test_option_reverse_lookup_roundtrip_and_off_is_none(self):
        for _d, _o in zip(ia_nav.NAV_TREE, ia_nav.direction_options()):
            assert ia_nav.direction_from_option(_o) == _d
        assert ia_nav.direction_from_option("不使用（用下方原功能）") is None
        for _d in ia_nav.NAV_TREE:
            for _p, _o in zip(ia_nav.NAV_TREE[_d], ia_nav.leaf_options(_d)):
                assert ia_nav.page_from_leaf_option(_d, _o) == _p
        assert ia_nav.page_from_leaf_option("dir_target", "🚦 今天") is None   # 不得靜默改用預設頁

    def test_position_text(self):
        assert ia_nav.position_text("inspect") == "📍 位置：🎯 標的 › 🔬 查一檔"
        assert ia_nav.position_text("hold") == "📍 位置：🛡️ 持股 › 💼 我的持股"
        assert ia_nav.position_text("action") == "📍 位置：⚡ 行動"
        assert ia_nav.position_text("data_center") == "📍 位置：🩺 資料中心 › 🩺 資料中心"

    def test_today_notice_is_the_wireframe_sentence(self):
        assert ia_nav.today_notice() == (
            "ⓘ 🚦 今天 是舊版頁面，暫時保留。新版的大盤請到側欄「📊 大盤」第一個頁。")


# ══ reconcile 守衛（Fail Loud，且是 RuntimeError 不是 assert）══════════════════
class TestReconcileGuard:
    def test_passes_with_the_real_dispatch_ids(self):
        ia_nav.reconcile_nav(_VIEW_IDS)

    def test_missing_dispatch_page_raises_runtime_error(self):
        with pytest.raises(RuntimeError):
            ia_nav.reconcile_nav(_VIEW_IDS - {"why"})

    def test_extra_dispatch_page_raises_runtime_error(self):
        with pytest.raises(RuntimeError):
            ia_nav.reconcile_nav(_VIEW_IDS | {"data_center"})   # 佔位頁不得有 renderer

    def test_tree_dropping_a_page_raises(self, monkeypatch):
        _t = {d: tuple(p for p in ps if p != "inspect") for d, ps in ia_nav.NAV_TREE.items()}
        monkeypatch.setattr(ia_nav, "NAV_TREE", _t)
        with pytest.raises(RuntimeError):
            ia_nav.reconcile_nav(_VIEW_IDS)

    def test_page_in_two_directions_raises(self, monkeypatch):
        _t = dict(ia_nav.NAV_TREE)
        _t["dir_me"] = ("me", "today")
        monkeypatch.setattr(ia_nav, "NAV_TREE", _t)
        with pytest.raises(RuntimeError):
            ia_nav.reconcile_nav(_VIEW_IDS)

    def test_unbuilt_before_built_raises(self, monkeypatch):
        _t = dict(ia_nav.NAV_TREE)
        _t["dir_data"] = ("data_center", "why")
        monkeypatch.setattr(ia_nav, "NAV_TREE", _t)
        with pytest.raises(RuntimeError):
            ia_nav.reconcile_nav(_VIEW_IDS)

    def test_direction_without_tree_entry_raises(self, monkeypatch):
        _t = dict(ia_nav.NAV_TREE)
        _t.pop("dir_action")
        monkeypatch.setattr(ia_nav, "NAV_TREE", _t)
        with pytest.raises(RuntimeError):
            ia_nav.reconcile_nav(_VIEW_IDS)

    def test_app_calls_the_reconcile_and_keeps_the_old_one(self):
        _src = (_ROOT / "app.py").read_text(encoding="utf-8")
        _tree = ast.parse(_src)
        _calls = [n for n in _tree.body if isinstance(n, ast.Expr) and isinstance(n.value, ast.Call)
                  and isinstance(n.value.func, ast.Attribute) and n.value.func.attr == "reconcile_nav"
                  and isinstance(n.value.func.value, ast.Name) and n.value.func.value.id == "_ia_nav"
                  and [getattr(a, "id", None) for a in n.value.args] == ["_IA_VIEWS"]]
        assert len(_calls) == 1, "app.py module 層沒有（或不只一個）`_ia_nav.reconcile_nav(_IA_VIEWS)` 呼叫節點（註解掉不算）"
        assert "if set(_IA_VIEWS) != set(_IA_PAGE_LABELS):" in _src and "raise RuntimeError(" in _src

    def test_unknown_ids_still_fail_loud(self):
        for _f in (ia_nav.page_label, ia_nav.where_to_find, ia_nav.page_direction,
                   ia_nav.is_built, ia_nav.path_text):
            with pytest.raises(ValueError):
                _f("nope")


# ══ where_to_find 新增方向層 ════════════════════════════════════════════════
class TestWhereToFindCarriesTheDirection:
    def test_pages(self):
        assert ia_nav.where_to_find("today") == "「📊 大盤 › 🚦 今天」"
        assert ia_nav.where_to_find("find") == "「🎯 標的 › 🔍 找標的」"
        assert ia_nav.where_to_find("why") == "「🩺 資料中心 › 📖 憑什麼」"
        assert ia_nav.where_to_find("action") == "「⚡ 行動」"
        # 方向名與頁名相同 ⇒ 指路句折成一層（卡面短句有 46 字上限）；位置列不折（線框逐字）
        assert ia_nav.where_to_find("market") == "「📊 大盤」"
        assert ia_nav.where_to_find("me") == "「👤 我的」"
        assert ia_nav.where_to_find("hold") == "「🛡️ 持股 › 💼 我的持股」"
        assert ia_nav.where_to_find("data_center") == "「🩺 資料中心」"

    def test_sections_use_the_spec_example(self):
        assert ia_nav.where_to_find(ia_nav.SECTION_WHY_DATA_HEALTH) == "「🩺 資料中心 › 📖 憑什麼 › 資料體檢」"
        assert ia_nav.where_to_find(ia_nav.SECTION_ME_SHEET) == "「👤 我的 › 目前 Sheet」"   # 方向名＝頁名 ⇒ 指路句折成一層（字數上限，見 path_text）
        assert ia_nav.where_to_find(ia_nav.SECTION_HOLD_PORTFOLIO_SETUP) == "「🛡️ 持股 › 💼 我的持股 › 組合設定」"
        assert ia_nav.where_to_find(ia_nav.SECTION_HOLD_WARROOM) == "「🛡️ 持股 › 💼 我的持股 › 戰情室」"

    def test_every_id_resolves_and_starts_with_its_direction(self):
        for _pid in [*ia_nav.PAGE_LABELS, *ia_nav.PLACEHOLDER_LABELS, *ia_nav.SECTION_LABELS]:
            _w = ia_nav.where_to_find(_pid)
            _page = _pid.split(".", 1)[0]
            _dl = ia_nav.DIRECTION_LABELS[ia_nav.page_direction(_page)]
            assert _w.startswith(f"「{_dl}"), (_pid, _w)   # 折疊時仍以方向名開頭
            assert _w.endswith("」")

    def test_short_warroom_name_is_a_prefix_of_the_real_page_title(self):
        from src.ui.views import page_hold
        assert page_hold.LEAF_WARROOM_TITLE.startswith(ia_nav.SECTION_LABELS[ia_nav.SECTION_HOLD_WARROOM])

    def test_all_where_to_find_callers_in_production_use_the_ssot_function(self):
        """約 55～57 處 caller 全是 `ia_nav.where_to_find(...)` / `_ia_where_to_find(...)`，沒有人手拼方向。"""
        _bad = []
        for _p in list((_ROOT / "src").rglob("*.py")) + [_ROOT / "app.py"]:
            # 註解行不算（page_hold 有一行歷史註解引用舊指路句）；只看會被執行的碼 / 字串。
            _t = "\n".join(l for l in _p.read_text(encoding="utf-8").splitlines() if not l.lstrip().startswith("#"))
            for _name in ia_nav.DIRECTION_LABELS.values():
                if f"「{_name} › " in _t:
                    _bad.append((str(_p.relative_to(_ROOT)), _name))
        assert _bad == [], f"production 碼手抄了含方向的指路句：{_bad}"


# ══ 佔位頁文案（逐字依線框 §4；⑨ 補「側欄選『不使用』」）══════════════════════
_P1 = {
    "title": "⚡ 行動",
    "now": "⚡ 行動這個方向目前沒有任何內容。",
    "why": "這個方向已規劃但還沒開始建，不是故障，也不是資料出問題。這裡沒有內容，不代表目前沒有需要處理的事。",
    "where": (
        "目前還沒有集中的「行動」頁。持股的風險與配置檢查請到「🛡️ 持股 › 💼 我的持股 › 戰情室」（需先登入並選定組合）。",
        "目前請切回舊版（側欄選『不使用』）→ 💼 我的持股戰情室；新版 ⚡ 行動會在下一階段處理（尚未排定日期）。",
    ),
}
_P2 = {
    "title": "🩺 資料中心",
    "now": "資料中心本體目前沒有內容：這裡不會彙總各資料來源是否健康、是否過期、哪裡缺值。",
    "why": "本體要等後續步驟才會建立，不是故障。這裡沒有看到警示，不代表資料都正常。",
    "where": (
        "目前可到「🩺 資料中心 › 📖 憑什麼 › 資料體檢」查看，那裡的涵蓋範圍以該頁自己的揭露為準（不是全站體檢）。",
        "目前請切回舊版（側欄選『不使用』）→ 🔧 工具箱 › 🔎 資料診斷；新版資料中心會在下一階段處理。",
    ),
}


class TestPlaceholderCopy:
    def test_p1_verbatim(self):
        assert ia_nav.placeholder_copy("action") == _P1

    def test_p2_verbatim(self):
        assert ia_nav.placeholder_copy("data_center") == _P2

    def test_step_9_is_in_both_old_ui_sentences_and_only_there(self):
        for _p in ("action", "data_center"):
            assert "（側欄選『不使用』）" in ia_nav.placeholder_copy(_p)["where"][1]
        # ⑨ 只授權 P-1／P-2 與 §4 模板：客戶逐字句 `CONTENT_EDIT_OLD_UI_WHERE` 不得被動到。
        assert ia_nav.CONTENT_EDIT_OLD_UI_WHERE == "目前請切回舊版 → 📁 組合管理；新版 CRUD 會在下一階段處理。"

    def test_template_helper_matches_the_client_sentence_shape(self):
        assert ia_nav.old_ui_sentence("X", "Y") == "目前請切回舊版（側欄選『不使用』）→ X；新版Y會在下一階段處理。"

    def test_copy_has_no_digits_or_lights(self):
        for _p in ("action", "data_center"):
            _c = ia_nav.placeholder_copy(_p)
            _all = _c["now"] + _c["why"] + "".join(_c["where"])
            for _bad in ("🔴", "🟢", "🟡", "%", "0", "1", "2", "3", "4", "5", "6", "7", "8", "9"):
                assert _bad not in _all, (_p, _bad)

    def test_non_placeholder_is_rejected(self):
        with pytest.raises(ValueError):
            ia_nav.placeholder_copy("hold")

    def test_old_ui_names_still_exist_in_app_py(self):
        """舊頁籤名的 SSOT 仍在 app.py；ia_nav 內的是客戶句的一部分 ⇒ 改名要轉紅。"""
        _src = (_ROOT / "app.py").read_text(encoding="utf-8")
        assert f"'{ia_nav.OLD_UI_PATH_WARROOM}'" in _src
        _tools, _diag = ia_nav.OLD_UI_PATH_DIAGNOSTIC.split(" › ")
        assert f"'{_tools}'" in _src and f"'{_diag}'" in _src


class TestShellNavModule:
    _SRC = (_ROOT / "src/ui/views/shell_nav.py").read_text(encoding="utf-8")

    def test_no_red_no_fetch_no_cache(self):
        _tree = ast.parse(self._SRC)
        _attrs = {n.attr for n in ast.walk(_tree) if isinstance(n, ast.Attribute)}
        for _bad in ("error", "warning", "exception", "cache_data", "cache_resource", "session_state"):
            assert _bad not in _attrs, f"殼/佔位頁不得使用 st.{_bad}"
        _imports = [n.module for n in ast.walk(_tree) if isinstance(n, ast.ImportFrom)]
        assert not any((m or "").startswith("src.data") for m in _imports), "殼不得 import L1"

    def test_placeholder_renders_grey_without_exception(self):
        from streamlit.testing.v1 import AppTest

        def _app():
            from src.ui.views.shell_nav import render_shell
            render_shell("action")
            render_shell("data_center")

        _at = AppTest.from_function(_app).run()
        assert not _at.exception
        assert not _at.error and not _at.warning
        _cap = " ".join(c.value for c in _at.caption)
        assert "📍 位置：⚡ 行動" in _cap and "📍 位置：🩺 資料中心 › 🩺 資料中心" in _cap
        assert _P1["now"] in _cap and _P2["why"] in _cap
        assert "⬜ 尚未建置" in " ".join(m.value for m in _at.markdown)

    def test_built_page_gets_only_the_position_bar(self):
        from streamlit.testing.v1 import AppTest

        def _app():
            from src.ui.views.shell_nav import render_shell
            render_shell("hold")

        _at = AppTest.from_function(_app).run()
        assert [c.value for c in _at.caption] == ["📍 位置：🛡️ 持股 › 💼 我的持股"]
        assert not _at.markdown


# ══ 整支 app.py 的殼畫面態（slow）══════════════════════════════════════════
def _run(nav=None, leaf=None, leaf_dir=None, at=None):
    from streamlit.testing.v1 import AppTest
    _at = at or AppTest.from_file(str(_ROOT / "app.py"), default_timeout=300)
    # NAV-1（DEC-097）：預設入口翻轉為新版固定四頁導覽；本測試守的是 D2 側欄雙層導覽 / 舊 7 頁籤（＝ legacy 模式），
    # 故一律以 legacy session 旗標進入（斷言一字未動；新預設模式的對應守衛在 tests/test_nav1_*.py）。
    _at.session_state[LEGACY_SESSION_KEY] = True
    if nav is not None:
        _at.session_state["_sb_ia_page"] = nav
    if leaf is not None:
        _at.session_state[f"_sb_ia_leaf_{leaf_dir}"] = leaf
    _at.run()
    return _at


def _sb_captions(at):
    return [c.value for c in at.sidebar.caption]


@pytest.mark.usefixtures("stub_trading_day_status")
@pytest.mark.slow
class TestShellScreens:
    def test_s1_default_has_six_directions_no_second_layer_no_position_bar(self):
        _at = _run()
        assert not _at.exception
        _r = _at.sidebar.radio(key="_sb_ia_page")
        assert list(_r.options) == ["不使用（用下方原功能）", *ia_nav.direction_options()]
        assert _r.value == "不使用（用下方原功能）"
        assert not [r for r in _at.sidebar.radio if r.key.startswith("_sb_ia_leaf_")]
        assert "⬜ ＝ 尚未建置" in _sb_captions(_at)
        assert not [c for c in _at.caption if c.value.startswith("📍")]

    def test_s2_two_layer_pick_shows_subtitle_and_position(self):
        _at = _run(nav="🎯 標的")
        assert not _at.exception
        assert "🎯 標的 底下：" in _sb_captions(_at)
        _leaf = _at.sidebar.radio(key="_sb_ia_leaf_dir_target")
        assert list(_leaf.options) == ["🔍 找標的", "🔬 查一檔"] and _leaf.value == "🔍 找標的"
        assert "📍 位置：🎯 標的 › 🔍 找標的" in [c.value for c in _at.caption]

    def test_second_layer_pick_changes_page_and_is_remembered_in_session(self):
        _at = _run(nav="🎯 標的")
        _at.sidebar.radio(key="_sb_ia_leaf_dir_target").set_value("🔬 查一檔").run()
        assert not _at.exception
        assert "📍 位置：🎯 標的 › 🔬 查一檔" in [c.value for c in _at.caption]
        _at.sidebar.radio(key="_sb_ia_page").set_value("📊 大盤").run()
        assert "📍 位置：📊 大盤 › 📊 大盤" in [c.value for c in _at.caption]
        _at.sidebar.radio(key="_sb_ia_page").set_value("🎯 標的").run()
        assert _at.sidebar.radio(key="_sb_ia_leaf_dir_target").value == "🔬 查一檔"

    def test_single_page_direction_has_no_second_layer(self):
        for _opt, _pos in (("🛡️ 持股", "📍 位置：🛡️ 持股 › 💼 我的持股"), ("👤 我的", "📍 位置：👤 我的 › 👤 我的")):
            _at = _run(nav=_opt)
            assert not _at.exception
            assert not [r for r in _at.sidebar.radio if r.key.startswith("_sb_ia_leaf_")]
            assert _pos in [c.value for c in _at.caption]

    def test_s3_action_placeholder_is_grey_and_loads_no_view(self):
        _at = _run(nav="⚡ 行動 ⬜")
        assert not _at.exception
        # 主畫面不得有任何紅框（側欄的「FinMind ❌／Gemini ❌」是沙箱沒金鑰的既有連線燈，與殼無關）。
        assert not _at.main.error, [e.value for e in _at.main.error]
        _cap = [c.value for c in _at.caption]
        assert "📍 位置：⚡ 行動" in _cap
        assert f"現在怎樣：{_P1['now']}" in _cap
        assert f"去哪：{_P1['where'][0]}" in _cap
        assert "僅供學術研究" in " ".join(m.value for m in _at.markdown)   # 免責聲明照出

    def test_s3_data_center_default_lands_on_why_and_placeholder_is_second(self):
        _at = _run(nav="🩺 資料中心")
        assert not _at.exception
        _leaf = _at.sidebar.radio(key="_sb_ia_leaf_dir_data")
        assert list(_leaf.options) == ["📖 憑什麼", "🩺 資料中心 ⬜"] and _leaf.value == "📖 憑什麼"
        assert "📍 位置：🩺 資料中心 › 📖 憑什麼" in [c.value for c in _at.caption]
        _leaf.set_value("🩺 資料中心 ⬜").run()
        assert not _at.exception and not _at.main.error
        assert f"為什麼：{_P2['why']}" in [c.value for c in _at.caption]

    def test_s6_today_notice(self):
        _at = _run(nav="📊 大盤", leaf="🚦 今天", leaf_dir="dir_market")
        assert not _at.exception
        assert ia_nav.today_notice() in [c.value for c in _at.caption]

    def test_s4_back_to_off_restores_the_seven_tabs_and_drops_the_shell(self):
        _at = _run(nav="🎯 標的")
        _at.sidebar.radio(key="_sb_ia_page").set_value("不使用（用下方原功能）").run()
        assert not _at.exception
        assert not [r for r in _at.sidebar.radio if r.key.startswith("_sb_ia_leaf_")]
        assert not [c for c in _at.caption if c.value.startswith("📍")]
        _labels = [getattr(t, "label", None) for t in _at.tabs]
        for _l in ("🌍 市場環境", "🔬 選股", "🏦 ETF", "🔧 工具箱", "💼 我的持股戰情室", "📁 組合管理", "🧬 AI 問答"):
            assert _l in _labels
