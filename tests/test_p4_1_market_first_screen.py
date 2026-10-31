"""tests/test_p4_1_market_first_screen.py — Phase 4 P4-1：📊 市場頁第一屏（客戶 DEC-117 已核准線框）。

對應線框 `docs/vnext/PHASE4_MARKET_PAGE_WIREFRAME_2026-10-30.md` §10 的 P4-1 條目（每條測試名帶條目號）：
  C1-1／C1-7／C1-9 區塊順序與「CTA→結論」「AI 行→圖區」之間不得插隊；C1-2 結論句逐字；C1-3 核心狀態恰 3 個；
  C1-4 頁首主 CTA＋form 語意；C1-5 手機 2＋1 規則；C2 指路三要素；C3-2 tile／⚡ 各只有一個「🔍 查看依據」且 hover-only
  出處併入六欄；C6-1～C6-5 風險縮短行／整句下沉／退化句外露逐字／覆蓋率外露／不新造「未評估不等於安全」；
  C8-b 更新選項；C8-c ⚡ 一行 bar；N1～N3 不變量（N4 還原鏈見 `tests/test_p4_revert_chain.py`）。
C1-6／C1-8／C1-10／C1-11 屬 Gate 量測（`docs/vnext/phase4_market/p4_1/measure_p4_1.js`），本檔只守其結構前提。

判讀一律用 AppTest **渲染後**的元素樹（文字比渲染後字串，⛔ 比原始碼字串；C6-3 明文要求）。
"""
from __future__ import annotations

import ast
import pathlib
from types import SimpleNamespace

import pytest

from shared import ia_nav
from shared.macro_buckets import BUCKET_ORDER
from src.services import macro_refresh_service as RS
from src.ui.views import _market_blocks as B
from src.ui.views import page_today as P
from tests.test_market_blocks import _all_up, _five, _readout
from tests.test_uim_market_page import _LOADED, _run

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_PM_SRC = (_ROOT / "src" / "ui" / "views" / "page_market.py").read_text(encoding="utf-8")
_MB_SRC = (_ROOT / "src" / "ui" / "views" / "_market_blocks.py").read_text(encoding="utf-8")
_PM_TREE = ast.parse(_PM_SRC)
_MB_TREE = ast.parse(_MB_SRC)
_TEXT = ("Markdown", "Caption", "Error", "Warning", "Success", "Info", "Text", "Code")


def _fn(tree, name):
    return next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name)


# ══════════════════════════════════════════════════════════════════
# AppTest 樹 → 文件順序事件
# ══════════════════════════════════════════════════════════════════
def _events(block, exp=None, keys=()):
    """`(kind, text, 所在 expander 標題或 None, 外層具名容器 key 們)`；Expander 本身也是一個事件（text＝標題）。"""
    for _ch in block.children.values():
        _t = type(_ch).__name__
        if _t == "Expander":
            yield ("Expander", _ch.label, exp, keys)
            yield from _events(_ch, _ch.label, keys)
            continue
        if hasattr(_ch, "children"):
            _id = str(getattr(getattr(_ch, "proto", None), "id", "") or "")
            yield from _events(_ch, exp, keys + ((_id.rsplit("-", 1)[-1],) if _id else ()))
            continue
        if _t in _TEXT:
            yield (_t, str(getattr(_ch, "value", "")), exp, keys)
        elif _t in ("Button", "FormSubmitButton", "Radio"):
            yield (_t, str(getattr(_ch, "label", "")), exp, keys)
        else:
            yield (_t, "", exp, keys)


def _expanded_flags(block, out=None):
    out = [] if out is None else out
    for _ch in block.children.values():
        if type(_ch).__name__ == "Expander":
            out.append((_ch.label, bool(_ch.proto.expanded)))
        if hasattr(_ch, "children"):
            _expanded_flags(_ch, out)
    return out


_SUBMIT = ia_nav.action_label(ia_nav.ACTION_UPDATE_TODAY)

#: L1 錨點（名稱, 事件判定）。只認**外露**（不在 expander 內）的元素，除了「更新選項」本身就是 expander 標題。
_ANCHORS = (
    ("H2", lambda k, t, e: k == "Markdown" and t == f"## {B.PAGE_TITLE}" and e is None),
    ("更新選項", lambda k, t, e: k == "Expander" and t == B.UPDATE_OPTIONS_LABEL),
    ("更新鈕", lambda k, t, e: k in ("Button", "FormSubmitButton") and t == _SUBMIT and e is None),
    ("結論標題", lambda k, t, e: k == "Markdown" and t == "#### 今日結論（五項各自判斷，只並列，不合成）" and e is None),
    ("結論句", lambda k, t, e: k == "Markdown" and t.startswith("市場位階：") and e is None),
    ("tile位階", lambda k, t, e: k == "Markdown" and t == f"**{B.REGIME_TILE_LABEL}**" and e is None),
    ("tile水位", lambda k, t, e: k == "Markdown" and t == f"**{B.WATER_TITLE}**" and e is None),
    ("tile風險", lambda k, t, e: k == "Markdown" and t == f"**{B.HERO_RISK_TITLE}**" and e is None),
    ("⚡bar", lambda k, t, e: k in _TEXT and t.startswith(f"**{B.ALERTS_TITLE}**") and e is None),
    ("AI行", lambda k, t, e: k == "Caption" and t.startswith(B.HERO_AI_PLACEHOLDER) and e is None),
    ("圖A", lambda k, t, e: k == "Markdown" and t == f"**{B.CHART_A_TITLE}**" and e is None),
)
_ORDER = [_n for _n, _ in _ANCHORS]


def _anchor_index(evs):
    _idx = {}
    for _i, (_k, _t, _e, _keys) in enumerate(evs):
        for _n, _f in _ANCHORS:
            if _n not in _idx and _f(_k, _t, _e):
                _idx[_n] = _i
    return _idx


def _report_empties_only():
    """只有「回空」（`empties`）、沒有任何 `failures` 的報告（QA 第二輪：Z 判斷式拿掉 empties 必須轉紅）。"""
    _r = RS.MacroRefreshReport(
        mode=RS.MODE_WARM, started_at="2026-10-29 13:45", elapsed_s=3.2,
        sources=tuple(RS.SourceResult(k, True, "1.0s") for k in RS.SOURCE_LABELS), steps=(),
        contents=(RS.SourceContent("tw", 0, 1, "檔"),), written_keys=("cl_data",), popped_keys=(), cleared=())
    assert _r.empties and not _r.failures
    return _r


def _report(*, failed: bool = False):
    return RS.MacroRefreshReport(
        mode=RS.MODE_WARM, started_at="2026-10-29 13:45", elapsed_s=3.2,
        sources=tuple(RS.SourceResult(k, True, "1.0s") for k in RS.SOURCE_LABELS),
        steps=((RS.StepResult(RS.STEP_CONTENT_AUDIT, False, "5/7 桶完整", partial=True),) if failed else ()),
        contents=(RS.SourceContent("tw", 1, 1, "檔"),), written_keys=("cl_data",), popped_keys=(), cleared=())


def _top(evs):
    return [_t for _k, _t, _e, _ in evs if _e is None and _k in _TEXT]


def _inside(evs, label=None):
    return [_t for _k, _t, _e, _ in evs if _e is not None and (label is None or _e == label) and _k in _TEXT]


# ══════════════════════════════════════════════════════════════════
# C1：順序、CTA、tile 數、手機 2＋1
# ══════════════════════════════════════════════════════════════════
class TestC1Order:
    @pytest.mark.parametrize("session", (None, _LOADED), ids=("cold", "loaded"))
    def test_c1_1_block_order_is_dec117_q5(self, tmp_path, session):
        """C1-1：頁首 → 更新 CTA → 今日結論 → 3 個核心狀態 → ⚡ → AI／資料狀態 → Primary（圖 A）。"""
        _at = _run(tmp_path, session)
        assert not _at.exception, _at.exception
        _idx = _anchor_index(list(_events(_at.main)))
        assert list(_idx) and set(_idx) == set(_ORDER), sorted(set(_ORDER) - set(_idx))
        assert sorted(_idx, key=_idx.get) == _ORDER

    def test_c1_1_order_holds_with_a_report(self, tmp_path):
        _at = _run(tmp_path, {**_LOADED, P.SS_REFRESH_REPORT: _report()})
        assert not _at.exception, _at.exception
        _evs = list(_events(_at.main))
        _idx = _anchor_index(_evs)
        assert sorted(_idx, key=_idx.get) == _ORDER

    def test_c1_7_primary_follows_ai_line_with_nothing_in_between(self, tmp_path):
        """C1-7：圖區（Primary）緊接 L1 決策區：AI／資料狀態行的**下一個事件**就是圖 A 標題（⛔ expander／長內容插隊）。"""
        _at = _run(tmp_path, _LOADED)
        _evs = list(_events(_at.main))
        _idx = _anchor_index(_evs)
        assert _idx["圖A"] == _idx["AI行"] + 1, _evs[_idx["AI行"]: _idx["圖A"] + 1]

    @pytest.mark.parametrize("session", (None, _LOADED), ids=("cold", "loaded"))
    def test_c1_10_alerts_bar_follows_the_three_tiles_with_nothing_in_between(self, tmp_path, session):
        """C1-10（DEC-118 問題 1=A；客戶 2026-10-30）：⚡ 列為手機 mobile exception，但必須**緊接 3 核心狀態之後**，
        中間不得有任何 L2／L3 內容 —— 風險 tile（最後一張）裡最後一個元素的下一個「tile 容器外」事件就是 ⚡ bar。"""
        _at = _run(tmp_path, session)
        _evs = list(_events(_at.main))
        _idx = _anchor_index(_evs)
        _last_tile = max(i for i, e in enumerate(_evs) if B.P4M_CORE_TILES_KEY in e[3])
        assert _idx["⚡bar"] == _last_tile + 1, _evs[_last_tile + 1: _idx["⚡bar"] + 1]
        assert _evs[_last_tile + 1][2] is None and B.P4M_L1_KEY in _evs[_last_tile + 1][3]

    @pytest.mark.parametrize("session", (_LOADED, None), ids=("loaded", "cold"))
    def test_c1_9_between_cta_and_conclusion_only_collapsed_report_expander(self, tmp_path, session):
        """C1-9：更新鈕 → 今日結論之間只允許「更新報告」expander（預設收合）及其內容；無報告時什麼都沒有。"""
        _sess = dict(session or {})
        for _rep in (None, _report()):
            if _rep is not None:
                _sess[P.SS_REFRESH_REPORT] = _rep
            _at = _run(tmp_path, _sess, name=f"_c19_{_rep is None}.py")
            _evs = list(_events(_at.main))
            _idx = _anchor_index(_evs)
            _between = _evs[_idx["更新鈕"] + 1: _idx["結論標題"]]
            _outside = [_e for _e in _between if _e[2] is None and _e[0] != "Expander"]
            assert not _outside, _outside
            _exps = [_e[1] for _e in _between if _e[0] == "Expander" and _e[2] is None]
            if _rep is None:
                assert _exps == []
            else:
                assert len(_exps) == 1 and "上一次更新的結果" in _exps[0]
                assert dict(_expanded_flags(_at.main))[_exps[0]] is False

    @pytest.mark.parametrize("session", (_LOADED, None), ids=("loaded", "cold"))
    def test_c1_9_strict_nothing_exposed_between_cta_and_conclusion_in_any_state(self, tmp_path, session):
        """C1-9 嚴格化（DEC-118 D1）：無報告／乾淨報告／**有真錯誤的報告**三態，更新鈕與今日結論標題之間都**沒有任何外露元素**；
        有真錯誤時那一段連報告標題都沒有（整份報告移到結論正下方，總管判定 Z）。"""
        for _name, _rep in (("none", None), ("clean", _report()), ("failed", _report(failed=True))):
            _sess = dict(session or {})
            if _rep is not None:
                _sess[P.SS_REFRESH_REPORT] = _rep
            _at = _run(tmp_path, _sess, name=f"_c19s_{_name}.py")
            _evs = list(_events(_at.main))
            _idx = _anchor_index(_evs)
            _between = _evs[_idx["更新鈕"] + 1: _idx["結論標題"]]
            assert not [e for e in _between if e[2] is None and e[0] != "Expander"], (_name, _between)
            _exps = [e[1] for e in _between if e[0] == "Expander" and e[2] is None]
            assert len(_exps) == (1 if _name == "clean" else 0), (_name, _exps)
            assert all("上一次更新的結果" in x and dict(_expanded_flags(_at.main))[x] is False for x in _exps)

    @pytest.mark.parametrize("session", (_LOADED, None), ids=("loaded", "cold"))
    def test_d1_partial_true_errors_are_exposed_directly_below_the_conclusion(self, tmp_path, session):
        """DEC-118 問題 2=D1：更新部分失敗 ⇒ 報告的真錯誤外露（不在 expander 內）、**緊接今日結論句**；
        其後是同一份報告的收合標題，再其後**緊接** 3 tile（中間無其他 L2／L3）；⚡ 仍緊接 tile。"""
        _at = _run(tmp_path, {**(session or {}), P.SS_REFRESH_REPORT: _report(failed=True)})
        assert not _at.exception, _at.exception
        _evs = list(_events(_at.main))
        _idx = _anchor_index(_evs)
        assert sorted(_idx, key=_idx.get) == _ORDER
        _first = _evs[_idx["結論句"] + 1]
        assert _first[0] == "Error" and _first[2] is None and "這一輪有取不到的來源" in _first[1]
        _gap = _evs[_idx["結論句"] + 1: _idx["tile位階"]]
        _top_level = [e for e in _gap if e[2] is None]
        assert all((e[0] == "Error") or (e[0] == "Expander" and "上一次更新的結果" in e[1]) for e in _top_level), _top_level
        assert [e[1] for e in _top_level if e[0] == "Expander"] and dict(_expanded_flags(_at.main))[
            next(e[1] for e in _top_level if e[0] == "Expander")] is False
        # 結論句與第一張 tile 之間只有「這份報告」：外露真錯誤、報告標題、報告標題內（含巢狀）的內容 —— 沒有別的東西
        _report_exps = {e[1] for e in _gap if e[0] == "Expander"}
        assert all(e[2] is None or e[2] in _report_exps for e in _gap), [e for e in _gap if e[2] not in _report_exps]
        assert _report_exps <= {e[1] for e in _gap if e[0] == "Expander" and ("上一次更新的結果" in e[1] or e[2])}
        _last_tile = max(i for i, e in enumerate(_evs) if B.P4M_CORE_TILES_KEY in e[3])
        assert _idx["⚡bar"] == _last_tile + 1


class TestD1Fallbacks:
    """QA 第二輪（DEC-118 D1／總管判定 Z 的 fallback）：任何會畫出紅字的報告，紅字都不得落在 CTA 與今日結論之間。"""

    def _between_and_after(self, at):
        _evs = list(_events(at.main))
        _idx = _anchor_index(_evs)
        _between = [e for e in _evs[_idx["更新鈕"] + 1: _idx["結論標題"]] if e[2] is None and e[0] in _TEXT]
        return _evs, _idx, _between

    def test_empties_only_report_goes_below_the_conclusion(self, tmp_path):
        _at = _run(tmp_path, {**_LOADED, P.SS_REFRESH_REPORT: _report_empties_only()})
        _evs, _idx, _between = self._between_and_after(_at)
        assert not _between and not [e for e in _evs[_idx["更新鈕"] + 1: _idx["結論標題"]] if e[0] == "Expander"]
        _first = _evs[_idx["結論句"] + 1]
        assert _first[0] == "Error" and _first[2] is None and "這幾個來源這一輪回空" in _first[1]

    def test_old_format_report_is_cleared_and_announced_below_the_conclusion(self, tmp_path):
        _at = _run(tmp_path, {**_LOADED, P.SS_REFRESH_REPORT: SimpleNamespace(started_at="10/30 09:00")})
        assert not _at.exception, _at.exception
        _evs, _idx, _between = self._between_and_after(_at)
        assert not _between
        _first = _evs[_idx["結論句"] + 1]
        assert _first[0] == "Error" and _first[1].startswith("上一次更新的報告畫不出來") and _first[2] is None
        assert P.SS_REFRESH_REPORT not in _at.session_state

    def test_non_current_report_type_is_treated_as_true_error_even_if_it_renders(self, tmp_path):
        """不是現行 `MacroRefreshReport` 的物件（例：熱重載後殘留的舊類別實例），即使欄位齊全、畫得出來，也一律移到
        結論下方（Z fallback）；CTA 與結論之間不留任何東西。"""
        _rep = _report()
        _names = ("ok", "failures", "empties", "partials", "skipped", "mode", "started_at", "elapsed_s", "sources",
                  "steps", "contents", "written_keys", "not_written_keys", "popped_keys", "cleared", "untouched")
        _fake = SimpleNamespace(**{_n: getattr(_rep, _n) for _n in _names})
        _at = _run(tmp_path, {**_LOADED, P.SS_REFRESH_REPORT: _fake})
        assert not _at.exception, _at.exception
        _evs = list(_events(_at.main))
        _idx = _anchor_index(_evs)
        assert not [e for e in _evs[_idx["更新鈕"] + 1: _idx["結論標題"]] if e[2] is None]
        _below = [e for e in _evs[_idx["結論句"] + 1: _idx["tile位階"]] if e[0] == "Expander" and e[2] is None]
        assert _below and "上一次更新的結果" in _below[0][1]

    def test_clean_report_that_raises_while_rendering_moves_below_the_conclusion(self, tmp_path, monkeypatch):
        def _boom(report):
            st_ = __import__("streamlit")
            st_.caption("畫到一半的內容")
            raise RuntimeError("渲染壞")
        monkeypatch.setattr(P, "_render_refresh_report", _boom)
        _at = _run(tmp_path, {**_LOADED, P.SS_REFRESH_REPORT: _report()})
        assert not _at.exception, _at.exception
        _evs, _idx, _between = self._between_and_after(_at)
        assert not _between, _between                                     # 半份內容已清掉
        # 結論下方由 `_render_report_guarded` 再畫一次：夾具的「半份內容」（同一次呼叫）＋紅字，緊接結論句
        _next2 = _evs[_idx["結論句"] + 1: _idx["結論句"] + 3]
        assert [e[1] for e in _next2][0] == "畫到一半的內容"
        assert _next2[1][0] == "Error" and _next2[1][1].startswith("上一次更新的報告畫不出來") and "渲染壞" in _next2[1][1]
        assert sum(1 for e in _evs if e[1] == "畫到一半的內容") == 1           # CTA 區那半份已清掉


class TestC1Structure:
    def test_c1_2_conclusion_sentence_is_identical_to_pre_p4(self):
        """C1-2：結論句與標題逐字不變 —— 組句的 `try` 區塊（含輸入 `regime_clause`／`danger_clause` 與紅字路徑）
        與 P4-1 之前（還原鏈基底）的 AST 完全相同；渲染結果另由 `test_uim_market_page` 對 UI-M 之前基底逐字比對。"""
        from tests.test_p4_revert_chain import p4_revert_for
        _base = ast.parse(p4_revert_for("src/ui/views/page_market.py", _PM_SRC))

        def _try(tree):
            _fn_p = _fn(tree, "render_page_market")
            _ts = [t for t in ast.walk(_fn_p) if isinstance(t, ast.Try) and "build_market_conclusion" in ast.unparse(t)]
            assert len(_ts) == 1
            return ast.dump(_ts[0])
        assert _try(_PM_TREE) == _try(_base)
        assert ast.unparse(_PM_TREE).count("section_header(CONCLUSION_HEADING)") == 1
        from src.ui.views import page_market as M
        assert M.CONCLUSION_HEADING == "今日結論（五項各自判斷，只並列，不合成）"

    def test_c1_2_conclusion_failure_is_red_and_named(self, tmp_path, monkeypatch):
        from src.ui.views import page_market as M

        def _boom(**_k):
            raise ValueError("測試用")
        monkeypatch.setattr(M, "build_market_conclusion", _boom)
        _at = _run(tmp_path, _LOADED)
        # QA 修正輪：只認**外露層**（不在任何 expander 內），且落在 L1 決策區、結論標題之後。
        _evs = list(_events(_at.main))
        _hits = [i for i, e in enumerate(_evs) if e[0] == "Error" and e[1].startswith("結論句組不出來：測試用")]
        assert len(_hits) == 1 and _evs[_hits[0]][2] is None and B.P4M_L1_KEY in _evs[_hits[0]][3]
        _head = next(i for i, e in enumerate(_evs) if e[1].startswith("#### 今日結論"))
        assert _hits[0] == _head + 1

    def test_c1_3_exactly_three_core_tiles_and_update_is_not_a_tile(self):
        _fn_t = _fn(_MB_TREE, "render_core_tiles")
        _cols = [c for c in ast.walk(_fn_t) if isinstance(c, ast.Call) and ast.unparse(c.func) == "st.columns"]
        assert [ast.unparse(c) for c in _cols] == ["st.columns(3)"]
        _src = ast.unparse(_fn_t)
        for _tok in ("render_update_cta", "single_submit_form", "form_submit_button", "_render_update_form"):
            assert _tok not in _src, _tok
        for _tree in (_PM_TREE, _MB_TREE):
            assert not [ast.unparse(c) for c in ast.walk(_tree) if isinstance(c, ast.Call)
                        and ast.unparse(c.func) == "st.columns" and ast.unparse(c.args[0]) == "4"]
        assert not any(isinstance(n, ast.FunctionDef) and n.name == "render_hero" for n in _MB_TREE.body)

    def test_c1_3_tiles_live_inside_the_keyed_container(self, tmp_path):
        _at = _run(tmp_path, _LOADED)
        _evs = list(_events(_at.main))
        for _title in (B.REGIME_TILE_LABEL, B.WATER_TITLE, B.HERO_RISK_TITLE):
            _hit = [e for e in _evs if e[0] == "Markdown" and e[1] == f"**{_title}**"]
            assert len(_hit) == 1 and B.P4M_CORE_TILES_KEY in _hit[0][3], (_title, _hit)
        assert not any(B.P4M_CORE_TILES_KEY in e[3] for e in _evs if e[0] in ("Button", "FormSubmitButton"))

    def test_c1_4_cta_is_in_the_header_before_the_conclusion(self):
        _fn_p = _fn(_PM_TREE, "render_page_market")
        _src = ast.unparse(_fn_p)
        assert _src.index("blocks.render_update_cta(") < _src.index("section_header(CONCLUSION_HEADING)")
        assert "today._render_update_form" not in _src
        # 頁首同列：CTA 畫在頁首欄位（`_head[1]`）裡
        _with = [w for w in ast.walk(_fn_p) if isinstance(w, ast.With)
                 and any(ast.unparse(i.context_expr) == "_head[1]" for i in w.items)]
        assert len(_with) == 1 and "blocks.render_update_cta(_session)" in ast.unparse(_with[0])

    def test_c1_4_cta_uses_the_same_form_and_session_keys_as_today(self):
        _src = ast.unparse(_fn(_MB_TREE, "render_update_cta"))
        for _tok in ("today.FORM_KEY", "today.MODE_LABELS", "today.SS_MODE_WIDGET", "today.SS_APPLIED_MODE",
                     "today.UPDATE_MODE_TO_REFRESH_MODE", "today._run_refresh_now", "today.SS_REFRESH_REPORT",
                     "ia_nav.action_label(ia_nav.ACTION_UPDATE_TODAY)", "st.rerun()"):
            assert _tok in _src, _tok

    def test_c1_4_only_submit_triggers_refresh_radio_does_not(self, tmp_path, monkeypatch):
        """C1-4／C8-b：form 語意不變 —— 改 radio 不重抓；按 🚀 才以對映模式重抓一次並 rerun。"""
        _calls: list[str] = []

        def _fake(mode):
            _calls.append(mode)
            return _report()
        monkeypatch.setattr(P, "_run_refresh_now", _fake)
        _at = _run(tmp_path, _LOADED)
        _radio = _at.radio(key=P.SS_MODE_WIDGET)
        _force = next(o for o in P.MODE_LABELS if o != _radio.value)
        _radio.set_value(_force).run()
        assert _calls == []
        _at.button[0].click().run()
        assert not _at.exception, _at.exception
        assert _calls == [P.UPDATE_MODE_TO_REFRESH_MODE[_force]]
        assert _at.session_state[P.SS_APPLIED_MODE] == {"mode": _force}
        assert any("上一次更新的結果" in e.label for e in _at.expander)

    def test_c1_5_mobile_two_plus_one_rule_is_scoped(self):
        _css = B.P4M_LAYOUT_CSS
        _media = _css[_css.index("@media (max-width: 640px){"):]
        _k = f".st-key-{B.P4M_CORE_TILES_KEY}"
        assert f'{_k} [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(-n+2)' in _media
        assert "calc(50% - 0.25rem)" in _media
        assert f'{_k} [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(3)' in _media
        assert "min-width:100%" in _media
        _src = ast.unparse(_fn(_MB_TREE, "render_core_tiles"))
        assert "st.container(key=P4M_CORE_TILES_KEY)" in _src

    def test_c1_5_layout_css_declarations_are_whitelisted(self):
        """QA 修正輪：禁字清單 → **屬性白名單**。版面 CSS 只准排版／換行屬性，任何能把內容藏起來的寫法
        （font-size:0、position、clip、transform、color／opacity、visibility、display、height、overflow、負位移…）一律紅。"""
        _assert_layout_css_only_lays_out(B.P4M_LAYOUT_CSS)

    @pytest.mark.parametrize("bad", (
        "font-size:0", "font-size:0.1rem", "position:absolute", "clip:rect(0 0 0 0)", "transform:scale(0)",
        "color:transparent", "left:-9999px", "display:none", "visibility:hidden", "height:0", "opacity:0",
        "overflow:hidden", "max-height:0", "margin-left:-9999px", "clip-path:inset(50%)", "text-indent:-9999px",
        # QA 第二輪
        "margin-left:-.5rem", "padding:calc(0px - 9999px)", "margin-top:calc(100vh)", "gap:99rem", "padding:500px",
        "padding-top:3rem", "margin:-(1rem)"))
    def test_c1_5_whitelist_rejects_hiding_tricks(self, bad):
        _evil = B.P4M_LAYOUT_CSS.replace("gap:0.5rem !important;", f"gap:0.5rem !important;{bad} !important;", 1)
        assert _evil != B.P4M_LAYOUT_CSS
        with pytest.raises(AssertionError):
            _assert_layout_css_only_lays_out(_evil)

    def test_c1_5_fold_contents_wrap_instead_of_overflowing(self):
        """QA 修正輪（目視 bug：手機位階摺疊內長 inline code 溢出蓋到水位 tile）：L1 內 expander 內容一律可任意處換行
        （規則在 @media 外，桌機手機都適用）；實量見 `docs/vnext/phase4_market/p4_1/_measure_p4_1_overflow.json`。"""
        _css = B.P4M_LAYOUT_CSS
        _rule = _css[:_css.index("@media")]
        assert f'.st-key-{B.P4M_L1_KEY} [data-testid="stExpander"] details *' in _rule
        assert "overflow-wrap:anywhere" in _rule and "word-break:break-word" in _rule


_CSS_ALLOWED = frozenset({
    "gap", "padding", "padding-top", "padding-bottom", "padding-left", "padding-right",
    "margin", "margin-top", "margin-bottom", "margin-left", "margin-right",
    "flex", "flex-wrap", "width", "min-width", "overflow-wrap", "word-break", "font-size"})
#: 字級下限（rem）：再小就等於藏字。
_CSS_FONT_MIN_REM = 0.875
#: 唯一允許的 calc（手機 2＋1 兩欄寬）。
_CSS_ALLOWED_CALC = "calc(50% - 0.25rem)"
#: 間距（padding／margin／gap）上限：再大就等於把內容推出畫面。
_CSS_SPACE_MAX_REM = 2.0
_CSS_SPACE_MAX_PX = 32.0


def _assert_layout_css_only_lays_out(css: str) -> None:
    import re
    assert css.count("@media") == 1 and "@media (max-width: 640px){" in css
    for _bad in ("::before", "::after", "content", "@import", "url(", "expression"):
        assert _bad not in css, _bad
    _blocks = re.findall(r"\{([^{}]*)\}", css)
    assert _blocks
    for _blk in _blocks:
        for _decl in filter(None, (d.strip() for d in _blk.split(";"))):
            _prop, _, _val = _decl.partition(":")
            _prop, _val = _prop.strip().lower(), _val.replace("!important", "").strip().lower()
            assert _prop in _CSS_ALLOWED, f"不在白名單的 CSS 屬性：{_decl!r}"
            # QA 第二輪：唯一允許的 calc 是 `calc(50% - 0.25rem)`；其餘任何 calc、任何負號（含 `-.5`、`-(`）一律紅。
            _rest = _val.replace(_CSS_ALLOWED_CALC, "")
            assert "calc(" not in _rest, f"不在白名單的 calc：{_decl!r}"
            assert "-" not in _rest.replace("break-word", "").replace("-n+2", ""), f"負值（可能把內容推出畫面）：{_decl!r}"
            if _prop.startswith(("padding", "margin")) or _prop == "gap":
                for _num, _unit in re.findall(r"([0-9.]+)(rem|px|em)?", _val):
                    _limit = {"rem": _CSS_SPACE_MAX_REM, "em": _CSS_SPACE_MAX_REM, "px": _CSS_SPACE_MAX_PX}.get(_unit, 0.0)
                    assert float(_num) <= _limit, f"間距超過上限（{_CSS_SPACE_MAX_REM}rem／{_CSS_SPACE_MAX_PX}px）：{_decl!r}"
            for _w in ("transparent", "hidden", "none", "0px)"):
                assert _w not in _val, _decl
            if _prop == "font-size":
                _m = re.fullmatch(r"([0-9.]+)rem", _val)
                assert _m and float(_m.group(1)) >= _CSS_FONT_MIN_REM, f"字級過小或非 rem：{_decl!r}"
            if _prop in ("width", "min-width"):
                assert _val == "0" and _prop == "min-width" or re.fullmatch(
                    r"(100%|calc\(50% - 0\.25rem\))", _val), _decl


# ══════════════════════════════════════════════════════════════════
# C2：指路句
# ══════════════════════════════════════════════════════════════════
class TestC2Pointer:
    def test_c2_three_literal_elements_and_length(self):
        for _w in ("指標危險度", "指標明細（16 項）", "最上方"):
            assert _w in B.DANGER_POINTER, _w
        assert len(B.DANGER_POINTER) <= B.DANGER_POINTER_MAX_CHARS == 32
        assert B.LAMP_DETAIL_EXPANDER_LABEL == "指標明細（16 項）"

    @pytest.mark.parametrize("session", (None, _LOADED), ids=("cold", "hot"))
    def test_c2_pointer_in_risk_tile_and_chart_d_outside_folds(self, tmp_path, session):
        _at = _run(tmp_path, session)
        _evs = list(_events(_at.main))
        _hits = [e for e in _evs if e[1] == B.DANGER_POINTER and e[2] is None]
        assert len(_hits) == 2
        assert sum(B.P4M_CORE_TILES_KEY in e[3] for e in _hits) == 1           # 一處在風險 tile
        assert B.DANGER_POINTER_UIM in _inside(_evs, B.BASIS_EXPANDER_LABEL)    # UI-M 原句只下沉

    def test_c2_no_pointer_chip_kind_was_added(self):
        from src.ui_v2 import compact
        assert not any("指路" in k or "pointer" in k for k in (*compact.META_KINDS, *compact._EXTRA_KINDS))


# ══════════════════════════════════════════════════════════════════
# C3-2：每張 tile／⚡ 只有一個「🔍 查看依據」；hover-only 出處併入六欄
# ══════════════════════════════════════════════════════════════════
class TestC3Basis:
    def test_c3_2_each_tile_and_alerts_has_exactly_one_basis_expander(self):
        _fn_t = _fn(_MB_TREE, "render_core_tiles")
        _with_cols = [w for w in ast.walk(_fn_t) if isinstance(w, ast.With)
                      and any(ast.unparse(i.context_expr).startswith("_cols[") for i in w.items)]
        assert len(_with_cols) == 3
        for _w in _with_cols:
            _calls = [ast.unparse(c.func) for c in ast.walk(_w) if isinstance(c, ast.Call)]
            assert _calls.count("render_basis") == 1, ast.unparse(_w)[:80]
            assert "st.expander" not in _calls
        _al = [ast.unparse(c.func) for c in ast.walk(_fn(_MB_TREE, "render_alerts_block")) if isinstance(c, ast.Call)]
        assert _al.count("render_basis") == 1 and "st.expander" not in _al

    def test_c3_2_page_basis_expanders_count_and_no_second_label(self, tmp_path):
        _at = _run(tmp_path, _LOADED)
        _evs = list(_events(_at.main))
        _labels = [e[1] for e in _evs if e[0] == "Expander"]
        # tile 3 ＋ ⚡ 1 ＋ 圖 A／B／D 各 1（圖區 P4-2 才動）
        assert _labels.count(B.BASIS_EXPANDER_LABEL) == 7
        for _bad in ("▸ 詳細", "詳細", "▸ 查看清單", "查看清單"):
            assert _bad not in _labels
        _l1 = [e for e in _evs if e[0] == "Expander" and B.P4M_L1_KEY in e[3]]
        assert {e[1] for e in _l1} <= {B.BASIS_EXPANDER_LABEL, B.UPDATE_OPTIONS_LABEL} | {
            e[1] for e in _l1 if "上一次更新的結果" in e[1]}

    def test_c3_2_hover_only_regime_provenance_is_visible_text_in_the_basis(self, tmp_path, monkeypatch):
        from tests.test_page_market import _SCENARIOS
        monkeypatch.setattr(P, "_load_regime", lambda: _SCENARIOS["live_no_cap"]["regime"])
        _at = _run(tmp_path, _LOADED)
        _in = "\n".join(_inside(list(_events(_at.main)), B.BASIS_EXPANDER_LABEL))
        assert f"卡片原標題「{P.REGIME_CARD_LABEL}」" in _in and "（總經契約）" in _in
        assert f"生效分支：warroom" in _in
        assert f"{P.REGIME_SCOPE_FACT_KEY}：" in _in
        assert "本頁一律取自 L3 總經契約" in _in      # REGIME_SCOPE_NOTE 原為 title= hover-only

    def test_n3_regime_basis_carries_every_fact_verbatim(self):
        _tile = SimpleNamespace(
            card=SimpleNamespace(label="市場位階（總經契約）", state="live", note=None),
            facts=(("生效分支", "warroom"), (P.REGIME_SCOPE_FACT_KEY, P.REGIME_SCOPE_NOTE)))
        _b = B.basis_regime(_tile)
        assert P.REGIME_SCOPE_NOTE in _b.rule and "生效分支：warroom" in _b.rule
        assert all(v.strip() for _, v in B.basis_rows(_b))


# ══════════════════════════════════════════════════════════════════
# C6：風險 tile
# ══════════════════════════════════════════════════════════════════
class TestC6RiskTile:
    def test_c6_1_short_line_is_lamp_color_bucket_lamp_direction(self):
        _r = B.build_market_risks(_five({"long": "red", "short": "yellow", "chips": "yellow", "news": "red"}), _all_up())
        _items, _more = B.hero_risk_items(_r)
        _face = B.hero_risk_face_lines(_r)
        _short = [x for t, x in _face if t == "item"]
        assert len(_short) == len(_items) == 3 and _more == 1
        for _row, _s in zip(_items, _short):
            assert _s == f"{B.LEVEL_EMOJI[_row.level]} {_row.title}：{_row.lamp_label}　{_row.direction_word}"
            assert "｜方向：" not in _s and "同級並列" not in _s and _row.level_text not in _s
        assert ("note", "另 1 項見圖 D") in _face
        assert not any(x == B.HERO_RISK_NO_RANKING_NOTE for _, x in _face)

    def test_c6_1_short_lines_use_the_same_rows_as_chart_d(self):
        _r = B.build_market_risks(_five({"mid": "yellow", "chips": "red"}), _all_up())
        _panel = B.risk_panel_rows(_r)
        for _row in B.hero_risk_items(_r)[0]:
            _p = _panel[BUCKET_ORDER.index(_row.bucket)]
            assert _row.lamp_label in _p[0] and _row.direction_word == _p[1]

    def test_c6_2_full_sentences_are_all_kept_in_the_fold(self):
        _ro = _five({"long": "red", "mid": "yellow", "short": "gray"})
        _ro.summary["mid"]["details"] = [{"key": "mid_a", "label": "燈A", "value_str": "1", "danger": "yellow", "note": ""},
                                         {"key": "mid_b", "label": "燈B", "value_str": "2", "danger": "yellow", "note": ""}]
        _r = B.build_market_risks(_ro, _all_up())
        assert B.hero_risk_fold_lines(_r) == B.hero_risk_lines(_r)       # UI-M 外露的整份，逐字
        _fold = [x for _, x in B.hero_risk_fold_lines(_r)]
        assert any("同級並列 2 項" in x for x in _fold) and B.HERO_RISK_NO_RANKING_NOTE in _fold
        for _i, _row in enumerate(B.hero_risk_items(_r)[0]):
            assert B.risk_item_text(_row, index=_i) in _fold

    def test_c6_2_full_sentences_are_in_the_risk_basis_on_the_page(self, tmp_path):
        _at = _run(tmp_path, _LOADED)
        _evs = list(_events(_at.main))
        _full = [t for t in _inside(_evs, B.BASIS_EXPANDER_LABEL) if t[:1] in "①②③"]
        _short = [e[1] for e in _evs if e[2] is None and B.P4M_CORE_TILES_KEY in e[3]
                  and e[0] == "Markdown" and e[1][:1] in "🟡🔴"]
        assert _full and len(_full) == len(_short)
        for _f, _s in zip(_full, _short):
            _lamp = _s.split("：", 1)[1].split("　", 1)[0]
            _dir = _s.rsplit("　", 1)[1]
            assert _lamp in _f and f"｜方向：{_dir}" in _f
        assert B.HERO_RISK_NO_RANKING_NOTE in _inside(_evs, B.BASIS_EXPANDER_LABEL)
        assert B.HERO_RISK_NO_RANKING_NOTE not in _top(_evs)

    @pytest.mark.parametrize("levels, needle", (
        ({}, "不代表安全"),
        ({_b: "gray" for _b in BUCKET_ORDER}, f"{B.UNDETERMINED}（五桶資料皆不足）"),
        ({"long": "gray"}, "本輪沒有非綠桶可列；另有 1 桶資料不足、無法判定（不代表安全）"),
        ({"long": "gray", "mid": "red"}, "另有 1 桶資料不足、無法判定（見圖 D）"),
    ), ids=("all_green", "all_insufficient", "partial_insufficient", "items_plus_insufficient"))
    def test_c6_3_degenerate_and_guard_sentences_are_exposed_verbatim(self, levels, needle):
        _r = B.build_market_risks(_five(levels), _all_up())
        _face = [x for _, x in B.hero_risk_face_lines(_r)]
        _full = [x for _, x in B.hero_risk_lines(_r)]
        assert any(needle in x for x in _face)
        if not B.hero_risk_items(_r)[0]:
            assert B.hero_risk_face_lines(_r) == B.hero_risk_lines(_r)      # 退化分支：外露層＝全文逐字
        assert all(x in _full or x.startswith(tuple(B.LEVEL_EMOJI.values())) for x in _face)

    def test_c6_3_cold_and_failed_on_the_page(self, tmp_path, monkeypatch):
        _cold = _run(tmp_path, None, name="_c63c.py")
        _cold_evs = list(_events(_cold.main))
        _tile = [e for e in _cold_evs if e[2] is None and B.P4M_CORE_TILES_KEY in e[3] and e[0] in _TEXT]
        assert any(e[1] == B.NOT_LOADED and e[0] == "Caption" for e in _tile)          # 灰
        assert not _cold.error
        monkeypatch.setattr(P, "load_macro_readout",
                            lambda s: SimpleNamespace(requested=True, error="RuntimeError('壞')", summary={},
                                                      readiness={}))
        _bad = _run(tmp_path, _LOADED, name="_c63f.py")
        _errs = [e for e in _events(_bad.main) if e[0] == "Error" and e[2] is None]
        assert any(e[1].startswith("五桶風險摘要算不出來：") and B.P4M_CORE_TILES_KEY in e[3] for e in _errs)

    def test_c6_3_other_true_errors_stay_outside_folds(self, tmp_path, monkeypatch):
        from src.services import market_twii_view_service as S
        monkeypatch.setattr(S, "get_twii_trend_view",
                            lambda n: S.TwiiTrendView(ok=False, failed=True, error="OSError: disk"))
        _at = _run(tmp_path, _LOADED)
        _errs = [e[1] for e in _events(_at.main) if e[0] == "Error" and e[2] is None]
        assert any(t.startswith("台股指數歷史讀取失敗：") for t in _errs)

    def test_c6_4_coverage_is_exposed_in_the_risk_tile_and_split_is_lossless(self, tmp_path):
        from src.ui.views import page_market as M
        _line = M.status_line(None, None)
        _time, _cov = _line.split("｜", 1)
        assert f"{_time}｜{_cov}" == _line and _cov.startswith("指標危險度覆蓋：")
        _at = _run(tmp_path, _LOADED)
        _evs = list(_events(_at.main))
        _covs = [e for e in _evs if e[1].startswith("指標危險度覆蓋：") and e[2] is None]
        assert len(_covs) == 1 and B.P4M_CORE_TILES_KEY in _covs[0][3] and "項有資料" in _covs[0][1]
        for _w in ("風險低", "安全", "沒事"):
            assert _w not in _covs[0][1]
        assert any(t.startswith(f"{M.NO_REFRESH_YET}｜") for t in _top(_evs))      # 更新時間那半在頁首

    def test_c6_4_report_state_split_keeps_both_halves_verbatim(self, tmp_path):
        """QA 修正輪：有報告時（時間那半含送出時間）也恰好拆成兩半，各在原位。"""
        from src.ui.views import page_market as M
        _rep = _report()
        _line = M.status_line(_rep, None)
        assert _line.count("｜") == 1
        _time, _cov = _line.split("｜")
        assert _rep.started_at in _time and M.REFRESH_TIME_NOTE in _time
        _at = _run(tmp_path, {**_LOADED, P.SS_REFRESH_REPORT: _rep})
        _evs = list(_events(_at.main))
        assert any(e[2] is None and e[1].startswith(f"{_time}｜") and B.P4M_CORE_TILES_KEY not in e[3] for e in _evs)
        assert any(e[2] is None and e[1].startswith("指標危險度覆蓋：") and B.P4M_CORE_TILES_KEY in e[3] for e in _evs)

    def test_c6_4_status_line_with_extra_separator_fails_loud(self, tmp_path, monkeypatch):
        from src.ui.views import page_market as M
        monkeypatch.setattr(M, "status_line", lambda r, d: "本頁更新於 a｜b｜指標危險度覆蓋：尚未載入")
        _at = _run(tmp_path, _LOADED)
        assert _at.exception and "恰含一個「｜」" in _at.exception[0].message

    def test_c6_4_cold_coverage_says_not_loaded_not_zero(self, tmp_path):
        _at = _run(tmp_path, None)
        _covs = [t for t in _top(list(_events(_at.main))) if t.startswith("指標危險度覆蓋：")]
        assert _covs == ["指標危險度覆蓋：尚未載入"]

    def test_c6_5_tile_never_adds_new_unevaluated_wording_and_chart_d_keeps_it_outside(self, tmp_path):
        for _lv in ({}, {"long": "gray"}, {"long": "red"}, {_b: "gray" for _b in BUCKET_ORDER}):
            _r = B.build_market_risks(_five(_lv), _all_up())
            assert not any("未評估不等於安全" in x for _, x in B.hero_risk_face_lines(_r))
        _at = _run(tmp_path, _LOADED)
        _top_texts = _top(list(_events(_at.main)))
        assert any("項未評估" in t and "未評估不等於安全" in t for t in _top_texts)


# ══════════════════════════════════════════════════════════════════
# C8：下沉（只下沉、不刪）
# ══════════════════════════════════════════════════════════════════
class TestC8:
    def test_c8_b_radio_and_long_note_are_inside_update_options_collapsed(self, tmp_path):
        _at = _run(tmp_path, _LOADED)
        _evs = list(_events(_at.main))
        _radios = [e for e in _evs if e[0] == "Radio" and e[1] == "更新模式"]
        assert len(_radios) == 1 and _radios[0][2] == B.UPDATE_OPTIONS_LABEL
        _note = _inside(_evs, B.UPDATE_OPTIONS_LABEL)
        assert _note == [B.update_options_note({})]
        assert P.PAGE_REFRESH_SCOPE_WHY in _note[0] and P.REFRESH_SPEED_HINT in _note[0]
        assert "已套用的更新模式：**（尚未送出過）**" in _note[0]
        assert dict(_expanded_flags(_at.main))[B.UPDATE_OPTIONS_LABEL] is False
        assert not any(P.REFRESH_SPEED_HINT in t for t in _top(_evs))
        _btn = [e for e in _evs if e[0] in ("Button", "FormSubmitButton") and e[1] == _SUBMIT]
        assert len(_btn) == 1 and _btn[0][2] is None                      # 主鍵在摺疊外
        _r = _at.radio(key=P.SS_MODE_WIDGET)
        assert list(_r.options) == [P.MODE_LABELS[k] for k in P.MODE_LABELS]

    def test_c8_b_note_is_the_same_string_as_today_page(self):
        _sess = {P.SS_APPLIED_MODE: {"mode": next(iter(P.MODE_LABELS))}}
        _mode = next(iter(P.MODE_LABELS))
        assert B.update_options_note(_sess) == (
            f"已套用的更新模式：**{P.MODE_LABELS[_mode]}**　·　⚠️ {P.PAGE_REFRESH_SCOPE_WHY}。{P.REFRESH_SPEED_HINT}")

    def test_c8_b_options_note_contract_in_ui_kit(self):
        from src.ui.views import _ui_kit as K
        _kw = dict(submit_label="go", radio_label="r", options=("a",), option_labels={"a": "A"},
                   widget_key="w", applied_key="ap")
        with pytest.raises(ValueError):
            K.single_submit_form("f", options_note="說明", **_kw)          # 沒有 expander ⇒ 不准
        for _bad in ("", "  ", 3):
            with pytest.raises(ValueError):
                K.single_submit_form("f", options_label="更新選項", options_note=_bad, **_kw)

    def _tile(self, state, **kw):
        from shared.ui_state import UI_LIVE
        _note = kw.get("note")
        return SimpleNamespace(card=SimpleNamespace(label="今日關鍵", state=state, value=kw.get("value"),
                                                    note=_note if state != UI_LIVE else None))

    def test_c8_c_bar_line_states(self):
        from shared.ui_state import UI_DEGRADED, UI_EMPTY, UI_FAILED, UI_IDLE, UI_LIVE
        _n = lambda now: SimpleNamespace(now=now)
        _live = B.alerts_bar_line(self._tile(UI_LIVE, value="1 紅 · 1 黃"), {"items": [{"text": "x"}]}, None)
        assert _live == ("item", "**⚡ 需要處理**　今日關鍵：1 紅 · 1 黃")
        _clear = B.alerts_bar_line(self._tile(UI_LIVE, value="門檻層與急變層本輪皆無異常"), {"items": []}, None)
        assert _clear[0] == "item" and _clear[1].endswith(B.ALERTS_NO_SOURCE)      # 沒有可列來源 ⇒ 同一行明寫
        _deg = B.alerts_bar_line(self._tile(UI_DEGRADED, note=_n("今日關鍵　已列出異常，但**本列僅含急變層**")),
                                 {"items": [{"text": "x"}, {"text": "y"}, {"text": "z"}], "n_red": 2, "n_yellow": 1}, None)
        # QA 修正輪：degraded 帶上既有的紅／黃計數（格式同 live 態 value「N 紅 · M 黃」）；QA 第二輪：紅黃數不相等（對調必紅）
        assert _deg == ("item", "**⚡ 需要處理**　今日關鍵　已列出異常，但本列僅含急變層　2 紅 · 1 黃")
        _cold = B.alerts_bar_line(self._tile(UI_IDLE, note=_n("今日關鍵　尚未載入 —— **未評估 ≠ 無異常**")), None, None)
        assert _cold[0] == "grey" and "未評估 ≠ 無異常" in _cold[1] and B.ALERTS_NO_SOURCE in _cold[1]
        _empty = B.alerts_bar_line(self._tile(UI_EMPTY, note=_n("今日關鍵　**門檻掃描尚未完成**")), {"items": []}, None)
        assert _empty[0] == "grey"
        _fail = B.alerts_bar_line(self._tile(UI_FAILED, note=SimpleNamespace(
            now="今日關鍵　橫幅本身無法產生", why="L2 `compute.macro.daily_key_alerts`（今日關鍵）拋出例外：RuntimeError('x')")),
            None, None)
        assert _fail[0] == "error" and "拋出例外：RuntimeError('x')" in _fail[1]      # QA 修正輪：原因逐字外露
        _conf = B.alerts_bar_line(self._tile(UI_LIVE, value="0 紅"), {"items": []},
                                  SimpleNamespace(conflicts=("甲", "乙")))
        assert B.ALERTS_CONFLICTS_COUNT_FMT.format(n=2) in _conf[1] and B.ALERTS_NO_SOURCE not in _conf[1]
        for _t in (_live, _clear, _deg, _cold, _empty, _fail, _conf):
            for _w in ("沒有需要處理的事", "無風險", "一切正常"):
                assert _w not in _t[1]

    def test_c8_c_page_bar_is_one_line_and_full_list_is_in_the_fold(self, tmp_path, monkeypatch):
        from tests.test_page_market import _SCENARIOS, _fake_alloc
        _a = _fake_alloc(with_cap=False)
        _a.conflicts = ("某個與結論相反的既有提示",)
        monkeypatch.setattr(P, "_load_allocation", lambda: (_a, ""))
        monkeypatch.setattr(P, "_load_regime", lambda: _SCENARIOS["live_no_cap"]["regime"])
        _drawn: list[str] = []
        _real = P._render_one
        monkeypatch.setattr(P, "_render_one", lambda t: (_drawn.append(t.card.key), _real(t))[1])
        _at = _run(tmp_path, _LOADED)
        _evs = list(_events(_at.main))
        _bars = [e for e in _evs if e[1].startswith(f"**{B.ALERTS_TITLE}**") and e[2] is None]
        assert len(_bars) == 1 and "\n" not in _bars[0][1]
        assert B.ALERTS_CONFLICTS_COUNT_FMT.format(n=1) in _bars[0][1]
        _in = _inside(_evs, B.BASIS_EXPANDER_LABEL)
        assert "- 某個與結論相反的既有提示" in _in and B.ALERTS_CONFLICTS_NUMBER_NOTE in _in
        assert f"**{B.ALERTS_CONFLICTS_HEADING}**" in _in
        assert "- 某個與結論相反的既有提示" not in _top(_evs)
        assert "key_banner.alerts" in _drawn                                  # 原「今日關鍵」卡整張仍畫（在摺疊內）


# ══════════════════════════════════════════════════════════════════
# N：不變量
# ══════════════════════════════════════════════════════════════════
class TestInvariants:
    @pytest.mark.parametrize("session", (None, _LOADED), ids=("cold", "loaded"))
    def test_n1_water_tile_has_no_number_and_verbatim_guards(self, tmp_path, monkeypatch, session):
        from tests.test_page_market import _SCENARIOS, _fake_alloc
        monkeypatch.setattr(P, "_load_allocation", lambda: (_fake_alloc(with_cap=True), ""))
        monkeypatch.setattr(P, "_load_regime", lambda: _SCENARIOS["live_with_cap"]["regime"])
        _at = _run(tmp_path, session)
        _evs = list(_events(_at.main))
        _tile = [e[1] for e in _evs if e[2] is None and B.P4M_CORE_TILES_KEY in e[3] and e[0] in _TEXT]
        assert f"**{B.WATER_VALUE}**" in _tile
        assert "風險上限：獨立顯示待 C2b＋RC-VISIBILITY Gate" in _tile
        assert not any(("%" in t or "％" in t) for t in _tile if not t.startswith("<"))
        _in = _inside(_evs, B.BASIS_EXPANDER_LABEL)
        assert B.WATER_WHY in _in and B.WATER_BASIS_NOTE in _in               # 只下沉
        assert any("40%～60%" in t for t in _inside(_evs))

    def test_n2_cold_first_screen_has_no_red_and_no_zero_standins(self, tmp_path):
        _at = _run(tmp_path, None)
        assert not _at.exception and not _at.error
        _l1 = [e[1] for e in _events(_at.main) if e[2] is None and B.P4M_L1_KEY in e[3] and e[0] in _TEXT]
        for _bad in ("0／16", "0/16", "無風險", "沒有需要處理", "中性", "續抱"):
            assert not any(_bad in t for t in _l1), _bad

    @pytest.mark.parametrize("scenario", ("cold", "live_no_cap", "alloc_error"))
    def test_n3_regime_tile_face_equals_conclusion_clause(self, tmp_path, monkeypatch, scenario):
        from src.ui.views import page_market as M
        from tests.test_page_market import _SCENARIOS
        _sc = _SCENARIOS[scenario]
        monkeypatch.setattr(P, "_load_allocation", lambda: _sc["alloc"])
        monkeypatch.setattr(P, "_load_regime", lambda: _sc["regime"])
        _faces: list[str] = []
        _real = B._render_regime_face
        monkeypatch.setattr(B, "_render_regime_face", lambda t, f, b, e="": (_faces.append(f), _real(t, f, b, e))[1])
        _clauses: list[str] = []
        _rc = M.regime_clause
        monkeypatch.setattr(M, "regime_clause", lambda *a, **k: (_clauses.append(_rc(*a, **k)), _clauses[-1])[1])
        _at = _run(tmp_path, _LOADED if scenario != "cold" else None)
        assert not _at.exception, _at.exception
        assert len(_faces) == 1 and _faces[0] in _clauses
        _tile = [e[1] for e in _events(_at.main) if e[2] is None and B.P4M_CORE_TILES_KEY in e[3]]
        assert B.REGIME_SCOPE_CAPTION in _tile
        for _w in ("偏多", "偏空", "中性"):
            assert not any(_w in t for t in _tile if t.startswith("**多頭") or t == _faces[0])

    def test_n3_regime_contract_failure_is_red(self, tmp_path, monkeypatch):
        monkeypatch.setattr(P, "_load_regime", lambda: (None, "RuntimeError('契約壞')"))
        _at = _run(tmp_path, _LOADED)
        _evs = list(_events(_at.main))
        # QA 修正輪：只認**外露層**（不在 expander 內）＋位階 tile 內；原因句與 X1 那句**逐字相同**。
        _x1 = [e[1] for e in _evs if e[0] == "Error" and e[2] == "市場位階：為什麼？"]
        assert len(_x1) == 1 and _x1[0].startswith("市場位階契約讀不出來：")
        _tile = [e for e in _evs if e[0] == "Error" and e[2] is None and B.P4M_CORE_TILES_KEY in e[3]]
        assert len(_tile) == 1, "位階契約讀取失敗時，位階 tile 外露值必須是紅（真錯誤）"
        assert _tile[0][1].endswith(_x1[0]) and "契約壞" in _tile[0][1]

    def test_n3_regime_degraded_is_bold_value_with_badge_not_grey(self, tmp_path, monkeypatch):
        """QA 修正輪：degraded（有值、門檻已失準）＝粗體外露值＋徽章字，⛔ 灰 caption、⛔ 紅。"""
        from shared import regime_arbiter as RA
        from src.ui.views import page_market as M
        _reg = {"regime": "bull", "light": "🟢", "source": RA.SOURCE_FILE_RULE_ENGINE, "health": 60,
                "is_loaded": True, "trend_regime": None, "defense": False, "exposure_limit_pct": None,
                "traffic_light": None}
        monkeypatch.setattr(P, "_load_regime", lambda: (_reg, ""))
        _tiles: list = []
        _real = B._render_regime_face
        monkeypatch.setattr(B, "_render_regime_face", lambda t, f, b, e="": (_tiles.append(t), _real(t, f, b, e))[1])
        _at = _run(tmp_path, _LOADED)
        assert not _at.exception, _at.exception
        from shared.ui_state import UI_DEGRADED
        assert _tiles and _tiles[0].card.state == UI_DEGRADED
        _badge = M.card_badge_text(_tiles[0])
        _evs = [e for e in _events(_at.main) if e[2] is None and B.P4M_CORE_TILES_KEY in e[3]]
        _i = next(i for i, e in enumerate(_evs) if e[1] == f"**{B.REGIME_TILE_LABEL}**")
        _k, _t = _evs[_i + 1][0], _evs[_i + 1][1]
        assert _k == "Markdown" and _t.startswith("**") and _badge and _badge in _t, (_k, _t, _badge)

    def test_n3_live_regime_tile_shows_the_card_badge(self, tmp_path, monkeypatch):
        """QA 修正輪：live 位階 tile 外露值旁必帶卡片徽章字（與原卡同一支 `card_badge_text`）。"""
        from src.ui.views import page_market as M
        from tests.test_page_market import _SCENARIOS
        monkeypatch.setattr(P, "_load_regime", lambda: _SCENARIOS["live_no_cap"]["regime"])
        _tiles: list = []
        _real = B._render_regime_face
        monkeypatch.setattr(B, "_render_regime_face", lambda t, f, b, e="": (_tiles.append((t, b)), _real(t, f, b, e))[1])
        _at = _run(tmp_path, _LOADED)
        _tile, _b = _tiles[0]
        assert _b and _b == M.card_badge_text(_tile)
        _evs = [e for e in _events(_at.main) if e[2] is None and B.P4M_CORE_TILES_KEY in e[3]]
        _i = next(i for i, e in enumerate(_evs) if e[1] == f"**{B.REGIME_TILE_LABEL}**")
        assert _evs[_i + 1][1] == f"**{_tile.card.value}**　{_b}"

    def test_c6_3_alerts_failed_bar_is_red_with_reason_outside(self, tmp_path, monkeypatch):
        monkeypatch.setattr(P, "_load_key_alerts", lambda s: (None, False, "RuntimeError('警示壞')"))
        _at = _run(tmp_path, _LOADED)
        _bars = [e for e in _events(_at.main) if e[1].startswith(f"**{B.ALERTS_TITLE}**") and e[2] is None]
        assert len(_bars) == 1 and _bars[0][0] == "Error"
        assert "拋出例外" in _bars[0][1] and "警示壞" in _bars[0][1]

    def test_layering_no_data_layer_and_no_digest_import(self):
        for _tree in (_PM_TREE, _MB_TREE):
            for _n in ast.walk(_tree):
                if isinstance(_n, ast.ImportFrom):
                    _m = _n.module or ""
                    assert not _m.startswith("src.data") and "digest" not in _m and "brain" not in _m, _m
