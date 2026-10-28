"""tests/test_nav1_default_mode_text.py — NAV-1 回修（QA MAJOR-1）：預設（新四頁）模式的**頁內文字**不得含死路／legacy 字樣。

背景：預設模式下舊版入口（側欄「不使用」radio、舊頁籤）對一般使用者不存在（DEC-097），但 `page_me`／`page_market`／`page_hold`
原本寫給 D2 殼的「切回舊版…」「側欄選『不使用』…」「與『🚦 今天』頁同一份」「AI 問答請到…」成了死路。
回修只動**呈現層**（旗標 `_nav4_legacy` 明確為 False 才分流）；legacy 模式（True）或旗標不存在 ⇒ **原句逐字不變**。

守什麼：
  1. 三個 view 內的旗標 key 字面值＝`shared/ia_nav4.LEGACY_SESSION_KEY`（view 不得 import ia_nav4，故各抄一份，這裡釘相等）。
  2. 分流語意：旗標 缺／True ⇒ 原句；False ⇒ 誠實句。legacy 斷言一字不放寬。
  3. 預設模式整頁實際渲染文字（四頁＋標的第二葉；未登入與已登入綁 Sheet 兩種狀態）不含 legacy 字樣。
  4. 新 UI 檔沒有 import ia_nav4 / shell_nav4（legacy 路徑零依賴新模組）。

⚠️ 揭露（本批不改，併 I-1 另批）：`ia_nav.where_to_find` 產生的路徑名（🛡️持股›…、📊 大盤›🚦 今天、🩺 資料中心›📖 憑什麼）
在預設模式仍會出現於 `page_hold`／`page_market` 的少數句子（牽動 ia_nav 46 字上限與 revert chain）。本檔第 3 組守衛
因此**只禁**「舊版／不使用／🆕／組合管理／legacy／切回／側欄選／與「🚦 今天」／AI 問答請到」，**不禁** `where_to_find` 的
路徑名；那些殘留的路徑名以 `KNOWN_RESIDUAL_PATH_NAMES` 明列並釘「僅限這幾個」，增加就紅。
"""
from __future__ import annotations

import ast
import pathlib
import re

import pytest

from shared import ia_nav, ia_nav4

_ROOT = pathlib.Path(__file__).resolve().parent.parent
_VIEWS = ("page_me", "page_market", "page_hold")

#: 預設模式整頁文字**不得**出現（legacy／死路字樣；不含 where_to_find 路徑名，見檔頭揭露）。
FORBIDDEN = ("舊版", "不使用", "🆕", "📁 組合管理", "legacy", "Legacy", "切回", "側欄選", "側欄「",
             "與「🚦 今天」", "AI 問答請到", "新版戰情室（試用中）")
#: 已知殘留（本批不改；where_to_find 路徑名）。預設模式文字中允許出現，但**僅限這些**。
KNOWN_RESIDUAL_PATH_NAMES = ("資料中心", "憑什麼", "🚦 今天")
#: 另一個已知殘留：`page_today.REGIME_SCOPE_NOTE`（📊 市場頁位階卡的出處說明，經 page_today 的共用 helper 渲染）含一句
#: 「舊版「🌍 市場環境」分頁另有未經這個仲裁的平行判讀…」。`page_today.py` 不在本批回修範圍（只准動 page_me／market／hold），
#: 且該句由 `tests/test_p01_today_view.py::TestNoGlobalUniquenessClaim` 反向釘住 ⇒ 本批**揭露、不改**（需後續批次處理）。
KNOWN_RESIDUAL_LEGACY_SENTENCES = ("舊版「🌍 市場環境」分頁另有",)
#: 再一個（不是指路句）：`page_hold` 葉 2 的**章節標題**「葉2 · 組合設定（＝組合管理＋Sheet 綁定）」只是描述這一葉的前身名稱，
#: 不帶 📁 與「去哪」；本批不改標題（牽動 `SECTION_LABELS`／既有標題守衛）。守衛因此禁的是「📁 組合管理」而不是裸字。
KNOWN_RESIDUAL_HEADINGS = ("（＝組合管理＋Sheet 綁定）",)


def _contents():
    from types import SimpleNamespace as NS
    return NS(portfolios={"核心": 1}, watchlists={"觀察": 1}, portfolio_issue=None, portfolio_error=None,
              watchlist_issue=None, watchlist_error=None,
              selection=NS(portfolio="核心", watchlist="觀察", watchlist_skip=False))


class TestFlagLiteral:
    @pytest.mark.parametrize("mod", _VIEWS)
    def test_literal_equals_the_l0_constant(self, mod):
        m = __import__(f"src.ui.views.{mod}", fromlist=["x"])
        assert m._NAV4_LEGACY_SESSION_KEY == ia_nav4.LEGACY_SESSION_KEY

    @pytest.mark.parametrize("mod", _VIEWS)
    def test_views_do_not_import_the_nav4_modules(self, mod):
        t = ast.parse((_ROOT / "src/ui/views" / f"{mod}.py").read_text(encoding="utf-8"))
        for n in ast.walk(t):
            if isinstance(n, ast.ImportFrom):
                assert (n.module or "") not in ("shared.ia_nav4", "src.ui.views.shell_nav4")
                assert not any(a.name in ("ia_nav4", "shell_nav4") for a in n.names)
            if isinstance(n, ast.Import):
                assert not any("ia_nav4" in a.name or "shell_nav4" in a.name for a in n.names)

    @pytest.mark.parametrize("mod", _VIEWS)
    def test_default_mode_means_flag_is_explicitly_false(self, mod, monkeypatch):
        m = __import__(f"src.ui.views.{mod}", fromlist=["x"])
        for flag, expect in ((False, True), (True, False), (None, False)):
            _ss = {} if flag is None else {ia_nav4.LEGACY_SESSION_KEY: flag}
            monkeypatch.setattr(m.st, "session_state", _ss, raising=False)
            assert m._in_default_nav() is expect, (mod, flag)


class TestLegacyTextIsVerbatim:
    """legacy 模式（旗標 True）與「旗標不存在」：輸出必須是原句。⛔ 不放寬。"""

    @pytest.fixture(params=[None, True])
    def legacy_ss(self, request, monkeypatch):
        import streamlit as st
        monkeypatch.setattr(st, "session_state",
                            {} if request.param is None else {ia_nav4.LEGACY_SESSION_KEY: True}, raising=False)

    def test_market_pointers(self, legacy_ss):
        from src.ui.views import page_market as M
        assert M._old_ui_pointer() == M.OLD_UI_POINTER
        assert M._x3_text() == M.X3_TEXT
        assert "（與「🚦 今天」頁同一份）" in M.report_pointer(None)
        assert "（與「🚦 今天」頁同一份報告）" in M.report_pointer(object())

    def test_hold_mode_text_is_identity(self, legacy_ss):
        from src.ui.views import page_hold as H
        _s = f"把持股補齊：{ia_nav.CONTENT_EDIT_OLD_UI_WHERE}　{H._V2_OLD_UI}"
        assert H._mode_text(_s) == _s

    def test_me_card_caption_is_the_clients_sentence(self, legacy_ss):
        from src.ui.views import page_me as P
        assert P.EDIT_CONTENT_WHERE.endswith(ia_nav.CONTENT_EDIT_OLD_UI_WHERE)
        _card = P.build_content_card(_contents(), logged_in=True, active_ok=True)
        assert _card.captions == (P.EDIT_CONTENT_WHERE,)


class TestDefaultModeTextIsHonest:
    @pytest.fixture()
    def default_ss(self, monkeypatch):
        import streamlit as st
        monkeypatch.setattr(st, "session_state", {ia_nav4.LEGACY_SESSION_KEY: False}, raising=False)

    def test_market_pointers(self, default_ss):
        from src.ui.views import page_market as M
        assert M._old_ui_pointer() == M.DEFAULT_MODE_NOT_YET
        assert "🚦 今天" not in M._x3_text()
        for r in (None, object()):
            assert "🚦 今天" not in M.report_pointer(r)

    def test_hold_mode_text_replaces_both_forms(self, default_ss):
        from src.ui.views import page_hold as H
        out = H._mode_text(f"A：{ia_nav.CONTENT_EDIT_OLD_UI_WHERE}　B：{H._V2_OLD_UI}…回本頁")
        assert out == f"A：{H.DEFAULT_MODE_NOT_YET}　B：{H.DEFAULT_MODE_NOT_YET_SHORT}…回本頁"
        for w in FORBIDDEN:
            assert w not in out

    @pytest.mark.parametrize("flag,replaced", [(False, True), (True, False), (None, False)])
    def test_hold_card_emission_funnel_applies_mode_text(self, monkeypatch, flag, replaced):
        """`_render_one_v2` 是 page_hold 所有 v2 卡面送進畫面的唯一出口：預設模式在這裡換句，其餘原樣。"""
        import streamlit as st

        from src.ui.views import page_hold as H
        _ss = {} if flag is None else {ia_nav4.LEGACY_SESSION_KEY: flag}
        monkeypatch.setattr(st, "session_state", _ss, raising=False)
        _sent = f"把持股補齊：{ia_nav.CONTENT_EDIT_OLD_UI_WHERE}；或 {H._V2_OLD_UI}"
        monkeypatch.setattr(H, "v2_card_html", lambda *a, **k: f"<div>{_sent}</div>")
        _out = []
        monkeypatch.setattr(st, "markdown", lambda body, **k: _out.append(body))
        H._render_one_v2(object())
        assert len(_out) == 1
        if replaced:
            assert "切回舊版" not in _out[0] and H.DEFAULT_MODE_NOT_YET in _out[0]
        else:
            assert _sent in _out[0], "legacy／無旗標：卡面句子必須原樣"

    def test_hold_readonly_caption_applies_mode_text(self, monkeypatch):
        import streamlit as st

        from src.ui.views import page_hold as H
        for flag, replaced in ((False, True), (True, False)):
            monkeypatch.setattr(st, "session_state", {ia_nav4.LEGACY_SESSION_KEY: flag}, raising=False)
            _caps = []
            monkeypatch.setattr(st, "caption", lambda body, **k: _caps.append(body))
            monkeypatch.setattr(st, "dataframe", lambda *a, **k: None)
            _h = type("Hs", (), {"has_holdings": True, "rows": ()})()
            try:
                H._render_holdings_preview(_h)
            except Exception:  # noqa: BLE001 — 只關心 caption 那一行；後面的表格細節與本測試無關
                pass
            assert _caps, "沒走到唯讀 caption"
            assert ("切回舊版" not in _caps[0]) is replaced, (flag, _caps[0])

    def test_me_card_caption_and_limits(self, default_ss):
        from src.ui.views import page_me as P
        _card = P.build_content_card(_contents(), logged_in=True, active_ok=True)
        assert _card.captions == (P.EDIT_CONTENT_WHERE_DEFAULT_MODE,)
        for txt in (P.EDIT_CONTENT_WHERE_DEFAULT_MODE, P.CREATE_SHEET_WHERE_DEFAULT_MODE, P.DETAIL_TITLE_DEFAULT_MODE,
                    *P.KNOWN_LIMITS_DEFAULT_MODE, *P.USED_BY_LINES_DEFAULT_MODE):
            for w in FORBIDDEN:
                assert w not in txt, (w, txt)
        assert not any("🚦" in l or "⚡" in l for l in P.USED_BY_LINES_DEFAULT_MODE)

    def test_original_constants_are_untouched(self):
        """呈現層分流，不改原常數（含客戶逐字句）。"""
        from src.ui.views import page_me as P
        assert ia_nav.CONTENT_EDIT_OLD_UI_WHERE == "目前請切回舊版 → 📁 組合管理；新版 CRUD 會在下一階段處理。"
        assert P.SWITCH_BACK_TEXT.startswith("切回舊版：側欄「") and "不使用" in P.SWITCH_BACK_TEXT
        assert P.DETAIL_TITLE == "▸ 詳細：切回舊版、已知限制"


# ══════════════════════════════════════════════════════════════════
# 整頁實際渲染（slow）：預設模式四頁（＋標的第二葉）
# ══════════════════════════════════════════════════════════════════
def _page_texts(at) -> list[str]:
    out = []
    for coll in ("markdown", "caption", "text", "warning", "info", "error", "success"):
        out += [str(getattr(e, "value", "")) for e in getattr(at, coll)]
    for e in at.expander:
        out.append(str(getattr(e, "label", "")))
    for coll in ("button", "radio", "selectbox", "text_input", "checkbox", "multiselect"):
        for e in getattr(at, coll):
            out.append(str(getattr(e, "label", "") or ""))
            out += [str(o) for o in (getattr(e, "options", None) or [])]
            out.append(str(getattr(e, "placeholder", "") or ""))
            out.append(str(getattr(e, "help", "") or ""))
    return out


def _scan(at, where):
    _txt = "\n".join(_page_texts(at))
    _txt_no_resid = _txt
    for r in KNOWN_RESIDUAL_LEGACY_SENTENCES + KNOWN_RESIDUAL_HEADINGS:
        _txt_no_resid = _txt_no_resid.replace(r, "")
    for r in KNOWN_RESIDUAL_PATH_NAMES:
        _txt_no_resid = _txt_no_resid.replace(r, "")
    for w in FORBIDDEN:
        assert w not in _txt_no_resid, f"預設模式 {where} 含死路／legacy 字樣 {w!r}：{_ctx(_txt, w)}"
    # 殘留路徑名只准是已知那幾個（防止新增）
    for m in re.finditer(r"「[^」]*›[^」]*」", _txt):
        _seg = m.group(0)
        assert any(r in _seg for r in KNOWN_RESIDUAL_PATH_NAMES + ("👤 我的", "💼", "🔬", "🔍", "📊")), _seg


def _ctx(txt, w):
    i = txt.find(w)
    return txt[max(0, i - 40): i + 60].replace("\n", " ")


@pytest.mark.usefixtures("stub_trading_day_status")
@pytest.mark.slow
class TestRenderedDefaultModePages:
    def _walk(self, at):
        from shared.ia_nav4 import NAV4_WIDGET_BOTTOM_KEY as B, NAV4_WIDGET_LEAF_KEY as L
        _scan(at, "市場")
        for label, where in (("🎯 標的", "標的/找標的"), ("💼 持股", "持股"), ("👤 我的", "我的")):
            at.radio(key=B).set_value(label).run()
            assert not at.exception, (where, at.exception)
            _scan(at, where)
        at.radio(key=B).set_value("🎯 標的").run()
        at.radio(key=L).set_value(ia_nav.page_label("inspect")).run()
        assert not at.exception, at.exception
        _scan(at, "標的/查一檔")

    def test_logged_out(self):
        from streamlit.testing.v1 import AppTest
        at = AppTest.from_file(str(_ROOT / "app.py"), default_timeout=300).run()
        assert not at.exception, at.exception
        self._walk(at)

    def test_logged_in_with_a_bound_sheet(self, monkeypatch):
        from streamlit.testing.v1 import AppTest

        import tests.sheet_safety_rw_fakes as F
        from shared import sheet_id as S
        from src.data.portfolio import gsheet_portfolio as gsp
        A = "AAAABOOK1234567890abcdef"
        c = F.FakeClient()
        c.books[A] = {"portfolios": [["name", "ticker", "lots", "avg_price", "updated_at"],
                                     ["核心", "0050", "1", "100", "t"]]}
        monkeypatch.setattr(gsp, "_build_client", lambda: c)
        monkeypatch.setattr(gsp, "list_user_folders", lambda: [])
        monkeypatch.setattr(gsp, "list_user_sheets", lambda folder_id="": [{"id": A, "name": "甲本"}])
        gsp.clear_read_cache()
        at = AppTest.from_file(str(_ROOT / "app.py"), default_timeout=300)
        at.session_state["custom_oauth_cfg"] = dict(F.OAUTH_CFG)
        at.session_state["gsheet_tokens"] = dict(F.TOKENS)
        at.session_state["gsheet_email"] = "qa@example.com"
        at.session_state["portfolio_sheet_id"] = A
        at.session_state["stock_portfolio_sheet_id"] = A
        at.session_state[S.ACTIVE_PORTFOLIO_SESSION_KEY] = {"sheet_id": A, "name": "核心", "skip": False}
        at.query_params["sheet"] = A
        at.run()
        assert not at.exception, at.exception
        try:
            self._walk(at)
        finally:
            gsp.clear_read_cache()

    def test_legacy_mode_still_shows_the_original_sentences(self):
        """對照組（鑑別力）：同一個 `👤 我的` 頁，在 legacy 模式（D2 殼）仍是原句 —— 證明上面的乾淨不是掃描器太鬆。"""
        from streamlit.testing.v1 import AppTest
        at = AppTest.from_file(str(_ROOT / "app.py"), default_timeout=300)
        at.session_state[ia_nav4.LEGACY_SESSION_KEY] = True
        at.session_state["_sb_ia_page"] = ia_nav.direction_options()[list(ia_nav.NAV_TREE).index(ia_nav.DIR_ME)]
        at.run()
        assert not at.exception, at.exception
        _txt = "\n".join(_page_texts(at))
        assert "切回舊版" in _txt and "不使用" in _txt, "對照組失效：legacy 的 👤 我的 應仍含原句"


# ══════════════════════════════════════════════════════════════════
# 第三組複驗回修：page_market 範圍的精準斷言（不被「資料中心／憑什麼」允許殘留豁免）
# ══════════════════════════════════════════════════════════════════
_MARKET_DEAD_END_PHRASES = ("資料健康：請到", "健康狀態與根因")


def _all_text(at) -> str:
    return "\n".join(_page_texts(at))


@pytest.mark.usefixtures("stub_trading_day_status")
@pytest.mark.slow
class TestMarketPageHealthPointers:
    def test_default_mode_market_page_has_neither_health_pointer(self):
        from streamlit.testing.v1 import AppTest
        at = AppTest.from_file(str(_ROOT / "app.py"), default_timeout=300).run()
        assert not at.exception, at.exception
        _t = _all_text(at)
        assert "市場" in _t   # 確實渲染到市場頁
        for ph in _MARKET_DEAD_END_PHRASES:
            assert ph not in _t, f"預設模式 📊 市場頁仍含 {ph!r}（H11／H25 分流失效）"
        assert "請到 🩺 資料中心" not in _t and "請到 「🩺 資料中心" not in _t

    def test_legacy_mode_market_page_keeps_both_original_sentences(self):
        """對照組：legacy 的 📊 大盤頁仍含原句（證明上面的『不含』不是頁面沒畫）。"""
        from streamlit.testing.v1 import AppTest
        at = AppTest.from_file(str(_ROOT / "app.py"), default_timeout=300)
        at.session_state[ia_nav4.LEGACY_SESSION_KEY] = True
        at.session_state["_sb_ia_page"] = ia_nav.direction_options()[list(ia_nav.NAV_TREE).index(ia_nav.DIR_MARKET)]
        at.run()
        assert not at.exception, at.exception
        _t = _all_text(at)
        for ph in _MARKET_DEAD_END_PHRASES:
            assert ph in _t, f"legacy 模式 📊 大盤頁缺原句 {ph!r}"


# ══════════════════════════════════════════════════════════════════
# H18：`st.query_params.get` 拋例外 ⇒ 旗標維持原值、app 不炸
# ══════════════════════════════════════════════════════════════════
class TestQueryParamsFailureIsIsolated:
    def _resolver(self):
        import types
        t = ast.parse((_ROOT / "app.py").read_text(encoding="utf-8"))
        fn = next(f for f in t.body if isinstance(f, ast.FunctionDef) and f.name == "_nav4_resolve_legacy")
        src = ast.get_source_segment((_ROOT / "app.py").read_text(encoding="utf-8"), fn)
        return src, types

    @pytest.mark.parametrize("cur", [False, True])
    def test_get_raising_keeps_the_current_flag(self, cur):
        src, types = self._resolver()

        class _Boom:
            def get(self, *_a, **_k):
                raise RuntimeError("query_params exploded")
        _st = types.SimpleNamespace(session_state={ia_nav4.LEGACY_SESSION_KEY: cur}, query_params=_Boom())
        _g = {"st": _st}
        exec(src, _g)
        assert _g["_nav4_resolve_legacy"]() is cur
        assert _st.session_state[ia_nav4.LEGACY_SESSION_KEY] is cur

    def test_attribute_access_raising_keeps_the_flag_too(self):
        src, types = self._resolver()

        class _St:
            session_state = {ia_nav4.LEGACY_SESSION_KEY: True}

            @property
            def query_params(self):
                raise RuntimeError("no query_params")
        _g = {"st": _St()}
        exec(src, _g)
        assert _g["_nav4_resolve_legacy"]() is True

    @pytest.mark.slow
    @pytest.mark.usefixtures("stub_trading_day_status")
    @pytest.mark.parametrize("start_legacy", [False, True])
    def test_app_does_not_crash_and_keeps_its_mode_when_query_params_get_raises(self, monkeypatch, start_legacy):
        from streamlit.runtime.state.query_params_proxy import QueryParamsProxy
        from streamlit.testing.v1 import AppTest
        _orig = QueryParamsProxy.get

        def _get(self, key, default=None):
            if key == ia_nav4.LEGACY_QUERY_PARAM:
                raise RuntimeError("legacy param read exploded")
            return _orig(self, key, default)
        monkeypatch.setattr(QueryParamsProxy, "get", _get)
        at = AppTest.from_file(str(_ROOT / "app.py"), default_timeout=300)
        at.session_state[ia_nav4.LEGACY_SESSION_KEY] = start_legacy
        at.run()
        assert not at.exception, at.exception
        assert at.session_state[ia_nav4.LEGACY_SESSION_KEY] is start_legacy
        _labels = [getattr(t, "label", None) for t in at.tabs]
        assert ("🌍 市場環境" in _labels) is start_legacy
