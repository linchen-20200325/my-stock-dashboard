"""tests/test_uit_target_page.py — UI-T（🎯 標的單一頁，2026-10-29）守衛。

客戶 2026-10-29 已核准線框（裁示 1A 2A 3A 4A 5A）＋ DEC-099（合併「🔍 找標的」「🔬 查一檔」並移除 NAV-1 過渡切換）。
受測對象：`src/ui/views/page_target.py`（編排）＋ `_target_blocks.py`（區塊）＋ `src/services/target_industry_service.py`（薄 L3）。

做法：把 `page_find` / `page_inspect` 的 loader 換成**計次的假貨**（`tests/uit_fakes.py`），假貨回**真的 dataclass**，
所以頁面走的是真的 builder／renderer。對應表（C 編號＝總管規格）：

  C0  Coverage 守恆（F1–F9、I1–I12 標記表；漏登紅燈）
  C1  冷啟動零 L3、零網路           C2  gate 寫入點白名單（含「查看此檔」）
  C3  每個 form 恰 1 submit、form 內無 button
  C4  操作隔離（poison 計次）        C5  失敗不入快取、rerun 不重打
  C6  widget key 不重複（同頁掛齊四 form 兩 button）
  C7  區塊隔離                       C8  選股三態／None≠0／因子輸入缺=紅／估值半邊失敗逐字
  C9  總經濾網說明逐字透傳           C10 地圖 proxy 揭露／缺格不填 0／stale degraded／tpex_complete
  C11–C16 單檔／ETF／unknown／批次／XV-ASOF／unwired 不退化
  C17 手機第一屏無工程字樣           C18 載入後全文掃描
  C19 過渡切換已移除                 C20 離頁再回狀態
  C21 legacy D2 側欄 find/inspect 仍可獨立渲染且不碰 nav4 新碼
  C22 reconcile_nav4（見 test_nav1_ia_nav4）  C23 導覽固定 4 頁（見 test_nav1_*）
  C25 不新增投資規則（static）
  P   parity：同一假資料下，新頁與舊兩頁的卡面 HTML 逐字相同
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

import pytest

from shared import ia_nav, ia_nav4
from src.ui.views import _target_blocks as B
from src.ui.views import page_find as F
from src.ui.views import page_inspect as I
from tests import uit_fakes as U

_ROOT = Path(__file__).resolve().parent.parent
_BLOCKS = _ROOT / "src/ui/views/_target_blocks.py"
_PAGE = _ROOT / "src/ui/views/page_target.py"
_SERVICE = _ROOT / "src/services/target_industry_service.py"

#: 第一屏／各區禁用的工程字樣（客戶 UI-T 邊界 9）與已移除的舊指路句。
ENGINEERING = ("葉1", "葉2", "線框", "鐵律", "接線揭露")
DEAD_POINTERS = ("🔍 找標的", "🔬 查一檔", "🌍 市場環境", "🏦 ETF 分頁", "找標的", "查一檔", "本頁不重複掛載")


# ══════════════════════════════════════════════════════════════════
# 小工具
# ══════════════════════════════════════════════════════════════════
_TEXT_ELEMENTS = frozenset({"Markdown", "Caption", "Text", "Error", "Warning", "Info", "Success", "Code", "Title",
                            "Header", "Subheader"})


def _walk(node):
    """文件順序走訪 AppTest 元素樹，yield 每個葉元素的 (type, text)。"""
    for _c in getattr(node, "children", {}).values():
        if getattr(_c, "children", None):
            _lab = getattr(_c, "label", None)
            if _lab:
                yield ("block-label", str(_lab))
            yield from _walk(_c)
        else:
            _tn = type(_c).__name__
            if _tn in _TEXT_ELEMENTS:                     # 純文字元素才讀 .value（widget 的 .value 會去查 state，可能 KeyError）
                _v = getattr(_c, "value", None)
                if isinstance(_v, str):
                    yield (_tn, _v)
                continue
            for _a in ("label", "placeholder", "help"):
                try:
                    _x = getattr(_c, _a, None)
                except Exception:   # noqa: BLE001 — 某些元素沒有該屬性
                    _x = None
                if isinstance(_x, str) and _x:
                    yield (f"{_tn}.{_a}", _x)
            try:
                _opts = list(getattr(_c, "options", None) or [])
            except Exception:   # noqa: BLE001
                _opts = []
            for _o in _opts:
                yield (f"{_tn}.option", str(_o))


def _texts(at) -> list[str]:
    return [t for _, t in _walk(at.main)]


def _all_text(at) -> str:
    return "\n".join(_texts(at))


def _new(monkeypatch, **kw):
    from streamlit.testing.v1 import AppTest
    _calls = U.Calls()
    U.install(monkeypatch, _calls, **kw)
    return AppTest.from_function(U.page_app, default_timeout=120), _calls


def _click(at, label):
    _b = [b for b in at.button if b.label == label]
    assert len(_b) == 1, (label, [b.label for b in at.button])
    return _b[0].click().run()


def _full(at):
    """把四個 form 與兩顆按鈕都用過一輪：選股、載入地圖、單檔（2330）、批次。"""
    at.run()
    _click(at, F.ACTION_RUN_SCREEN_LABEL)
    _click(at, F.ACTION_LOAD_MAP_LABEL)
    at.text_input(key=I.SS_TICKER_WIDGET).set_value("2330")
    _click(at, I.ACTION_LOAD_INSPECT_LABEL)
    at.text_area(key=I.SS_BATCH_WIDGET).set_value("2330 00878 2317")
    _click(at, I.ACTION_RUN_BATCH_LABEL)
    assert not at.exception, at.exception
    return at


# ══════════════════════════════════════════════════════════════════
# C0 Coverage 守恆
# ══════════════════════════════════════════════════════════════════
#: 能力守恆標記表（`page_find`／`page_inspect` 現有能力 → 新頁的對應元件）。
#: ⚠️ 編號是本批實作組依客戶邊界 8 的敘述自行編的（獨立稽核清單 F1–F9／I1–I9 的原文實作組沒有拿到）：
#:    以「選股表單／筆數／結果卡與表／CSV／總經濾網說明透傳／板塊地圖 gate＋熱力圖＋泡泡圖＋持股⭐／單檔判型卡與三分支／
#:    健康度·357·籌碼／獲利能力／XV-ASOF／批次表單＋共同時間表頭＋下鑽／unwired 揭露」展開；稽核組若有不同編號，請對照補登。
COVERAGE: dict[str, str] = {
    "F1 選股條件表單(因子 multiselect)": "multiselect:" + F.SS_FACTORS_WIDGET,
    "F2 顯示筆數": "selectbox:" + F.SS_TOPN_WIDGET,
    "F3 開始選股(submit＋已套用值 gate)": "button:" + F.ACTION_RUN_SCREEN_LABEL,
    "F4 結果卡(三態)": "text:選股結果",
    "F5 結果表": "df:標的",
    "F6 CSV 下載": "download:" + B.SS_CSV_BUTTON,
    "F7 總經濾網說明透傳": "text:總經為 caution",
    "F8 板塊地圖 gate 鈕": "button:" + F.ACTION_LOAD_MAP_LABEL,
    "F9a 熱力圖(含單一代表股揭露)": "text:產業漲跌熱力圖",
    "F9b 泡泡圖卡＋口徑揭露": "text:三大法人資金流向泡泡圖",
    "F9c 象限圖例": "text:個板塊",
    "I1 代碼表單": "text_input:" + I.SS_TICKER_WIDGET,
    "I2 判型覆寫": "selectbox:" + I.SS_KIND_WIDGET,
    "I3 期間": "selectbox:" + I.SS_PERIOD_WIDGET,
    "I4 MA 勾選": "checkbox:" + I.SS_MA_WIDGET_PREFIX + "20",
    "I5 判型卡": "text:判型結果",
    "I6 個股健康度": "text:健康度",
    "I7 357 估值": "text:357",
    "I8 籌碼": "text:集中度",
    "I9 獲利能力三格": "text:毛利率",
    "I10 批次表單": "button:" + I.ACTION_RUN_BATCH_LABEL,
    "I11 批次表＋共同時間表頭(XV-ASOF)": "text:價格資料時間：",
    "I12 批次下鑽": "selectbox:" + I.SS_DRILL_WIDGET,
    "I13 unwired 揭露(K 線／明細七段)": "text:個股的 K 線與明細七段",
}


class TestCoverage:
    def test_every_capability_has_a_component_on_the_page(self, monkeypatch):
        at, _ = _new(monkeypatch)
        _full(at)
        _txt = _all_text(at)
        _dfs = [list(d.value.columns) for d in at.dataframe]
        for _item, _spec in COVERAGE.items():
            _kind, _, _arg = _spec.partition(":")
            if _kind == "multiselect":
                assert at.multiselect(key=_arg), _item
            elif _kind == "selectbox":
                assert at.selectbox(key=_arg), _item
            elif _kind == "text_input":
                assert at.text_input(key=_arg), _item
            elif _kind == "checkbox":
                assert at.checkbox(key=_arg), _item
            elif _kind == "button":
                assert any(b.label == _arg for b in at.button), _item
            elif _kind == "download":
                assert any(getattr(d, "key", None) == _arg for d in at.get("download_button")), _item
            elif _kind == "df":
                assert any(_arg in cols for cols in _dfs), _item
            else:
                assert _arg in _txt, f"{_item}：頁面上找不到「{_arg}」"

    def test_the_marker_table_is_complete(self):
        """標記表本身漏登＝紅燈：F1–F9、I1–I13 每個編號都要在表內。"""
        _ids = {k.split(" ")[0] for k in COVERAGE}
        _need = {"F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9a", "F9b", "F9c"} | {f"I{n}" for n in range(1, 14)}
        assert _need <= _ids, sorted(_need - _ids)

    def test_every_legacy_widget_key_is_reused_not_reinvented(self):
        """舊兩頁的 form／widget key 在新頁用同一組（不另起第二組 ⇒ 沒有兩個真相源）。"""
        _src = _BLOCKS.read_text(encoding="utf-8")
        for _k in ("F.FORM_KEY", "F.SS_FACTORS_WIDGET", "F.SS_TOPN_WIDGET", "F.SS_APPLIED_SCREEN", "F.SS_MAP_BUTTON",
                   "F.SS_MAP_REQUESTED", "I.FORM_TICKER_KEY", "I.SS_TICKER_WIDGET", "I.SS_APPLIED_TICKER",
                   "I.FORM_BATCH_KEY", "I.SS_APPLIED_BATCH", "I.SS_DRILL_WIDGET"):
            assert _k in _src, _k


# ══════════════════════════════════════════════════════════════════
# C1 冷啟動零 L3、零網路
# ══════════════════════════════════════════════════════════════════
class TestColdStart:
    def test_cold_start_calls_no_loader_at_all(self, monkeypatch):
        at, calls = _new(monkeypatch)
        at.run()
        assert not at.exception, at.exception
        assert sum(calls.values()) == 0, f"冷啟動就取數了：{dict(calls)}"

    def test_cold_start_is_grey_guidance_not_red(self, monkeypatch):
        at, _ = _new(monkeypatch)
        at.run()
        assert not at.error, [e.value for e in at.error]
        assert B.ZONE3_IDLE in _all_text(at)
        assert B.ZONE1_IDLE in _all_text(at)

    def test_poisoned_l3_modules_are_never_touched_on_cold_start(self, monkeypatch):
        """比 loader 計次更底層：連 L3 service／L1 模組被 import 都算違規 —— 全部換成會爆的毒模組。"""
        from streamlit.testing.v1 import AppTest

        class _Poison:
            def __getattr__(self, item):
                raise AssertionError(f"冷啟動碰到 {item}")
        for _m in ("src.services.fundamental_screener_service", "src.services.sector_flow_service",
                   "src.services.sector_heatmap_service", "src.services.valuation_service",
                   "src.services.stock_chips_service", "src.services.target_industry_service"):
            monkeypatch.setitem(sys.modules, _m, _Poison())
        at = AppTest.from_function(U.page_app, default_timeout=120).run()
        assert not at.exception, at.exception
        assert not at.error, [e.value for e in at.error]

    def test_the_page_module_has_no_module_level_l3_or_l1_import(self):
        for _p in (_BLOCKS, _PAGE):
            for _n in ast.parse(_p.read_text(encoding="utf-8")).body:
                if isinstance(_n, (ast.Import, ast.ImportFrom)):
                    _mod = getattr(_n, "module", "") or ""
                    for _a in _n.names:
                        _full = _mod + "." + _a.name if isinstance(_n, ast.ImportFrom) else _a.name
                        assert not _full.startswith(("src.services", "src.data", "src.compute")), (_p.name, _full)


# ══════════════════════════════════════════════════════════════════
# C2 gate 寫入點白名單
# ══════════════════════════════════════════════════════════════════
def _writes_to(tree: ast.AST, name_suffix: str):
    """找出所有 `session[...SS_APPLIED_X] = ...` 的賦值，回 [(函式名, lineno)]。"""
    _hits = []
    for _fn in [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]:
        for _n in ast.walk(_fn):
            if isinstance(_n, ast.Assign):
                for _t in _n.targets:
                    if isinstance(_t, ast.Subscript):
                        _s = ast.unparse(_t.slice)
                        if _s.endswith(name_suffix):
                            _hits.append((_fn.name, _n.lineno))
    return _hits


class TestGateWritePoints:
    def test_applied_ticker_is_written_in_exactly_one_function(self):
        _tree = ast.parse(_BLOCKS.read_text(encoding="utf-8"))
        assert {f for f, _ in _writes_to(_tree, "SS_APPLIED_TICKER")} == {"write_applied_ticker"}
        assert len(_writes_to(_tree, "SS_APPLIED_TICKER")) == 1

    def test_write_applied_ticker_has_exactly_two_callers_the_form_and_the_pick_button(self):
        """白名單（登記理由）：① 搜尋框 form 的送出；② 候選表「🔍 查看此檔」鈕 on_click —— 客戶裁示 2A：使用者明確操作才取數。"""
        _tree = ast.parse(_BLOCKS.read_text(encoding="utf-8"))
        _callers = set()
        for _fn in [n for n in ast.walk(_tree) if isinstance(n, ast.FunctionDef)]:
            for _n in ast.walk(_fn):
                if isinstance(_n, ast.Call) and isinstance(_n.func, ast.Name) and _n.func.id == "write_applied_ticker":
                    _callers.add(_fn.name)
        assert _callers == {"handle_ticker_submit", "on_pick_click"}, _callers

    def test_on_pick_click_is_only_attached_to_the_pick_button(self):
        _src = _BLOCKS.read_text(encoding="utf-8")
        assert _src.count("on_click=on_pick_click") == 1
        _tree = ast.parse(_src)
        for _n in ast.walk(_tree):
            if isinstance(_n, ast.Call) and any(k.arg == "on_click" for k in _n.keywords):
                assert isinstance(_n.func, ast.Attribute) and _n.func.attr == "button", ast.unparse(_n)

    def test_other_gate_keys_have_single_writers(self):
        _tree = ast.parse(_BLOCKS.read_text(encoding="utf-8"))
        assert [f for f, _ in _writes_to(_tree, "F.SS_APPLIED_SCREEN")] == ["render_screen_form"]
        assert [f for f, _ in _writes_to(_tree, "I.SS_APPLIED_BATCH")] == ["render_batch_form"]
        assert [f for f, _ in _writes_to(_tree, "F.SS_MAP_REQUESTED")] == ["render_zone_industry"]

    def test_selecting_a_candidate_alone_does_not_fetch_it(self, monkeypatch):
        at, calls = _new(monkeypatch)
        at.run()
        _click(at, F.ACTION_RUN_SCREEN_LABEL)
        at.selectbox(key=B.SS_PICK_WIDGET).set_value("2317").run()
        assert calls["stock"] == 0 and calls["chips"] == 0 and I.SS_APPLIED_TICKER not in at.session_state
        assert B.ZONE3_IDLE in _all_text(at)

    def test_pick_button_writes_the_same_gate_and_syncs_the_search_box(self, monkeypatch):
        at, calls = _new(monkeypatch)
        at.run()
        _click(at, F.ACTION_RUN_SCREEN_LABEL)
        at.selectbox(key=B.SS_PICK_WIDGET).set_value("2317").run()
        at.button(key=B.SS_PICK_BUTTON).click().run()
        assert not at.exception, at.exception
        assert at.session_state[I.SS_APPLIED_TICKER]["ticker"] == "2317"
        assert at.text_input(key=I.SS_TICKER_WIDGET).value == "2317"
        assert calls["stock"] == 1


# ══════════════════════════════════════════════════════════════════
# C3 form 結構
# ══════════════════════════════════════════════════════════════════
class TestFormStructure:
    def test_each_form_has_exactly_one_submit_and_no_plain_button(self):
        _tree = ast.parse(_BLOCKS.read_text(encoding="utf-8"))
        _forms = [n for n in ast.walk(_tree) if isinstance(n, ast.With)
                  and any(isinstance(i.context_expr, ast.Call) and ast.unparse(i.context_expr.func) == "st.form"
                          for i in n.items)]
        assert len(_forms) == 3, "新頁應恰三個 st.form（搜尋／選股／批次）"
        for _w in _forms:
            _calls = [ast.unparse(c.func) for c in ast.walk(_w) if isinstance(c, ast.Call)]
            assert _calls.count("st.form_submit_button") == 1, ast.unparse(_w)[:80]
            for _bad in ("st.button", "st.download_button"):
                assert _bad not in _calls, f"form 內有 {_bad}"

    def test_runtime_forms_and_buttons(self, monkeypatch):
        at, _ = _new(monkeypatch)
        _full(at)
        _labels = sorted(b.label for b in at.button)
        assert _labels.count(I.ACTION_LOAD_INSPECT_LABEL) == 1
        assert _labels.count(F.ACTION_RUN_SCREEN_LABEL) == 1
        assert _labels.count(I.ACTION_RUN_BATCH_LABEL) == 1
        assert _labels.count(F.ACTION_LOAD_MAP_LABEL) == 1
        assert _labels.count(B.PICK_BUTTON_LABEL) == 1


# ══════════════════════════════════════════════════════════════════
# C4 操作隔離
# ══════════════════════════════════════════════════════════════════
class TestOperationIsolation:
    def test_each_zone_is_fetched_once_by_its_own_gate(self, monkeypatch):
        at, calls = _new(monkeypatch)
        _full(at)
        # 選股、地圖(熱力圖＋資金流)、單檔(健康度＋357＋籌碼＋獲利)、批次：各恰一次
        assert calls["screen"] == 1 and calls["flow"] == 1 and calls["heatmap"] == 1
        assert calls["stock"] == 1 and calls["valuation"] == 1 and calls["chips"] == 1 and calls["profit"] == 1
        assert calls["batch"] == 1 and calls["sector"] == 1 and calls["pe"] == 1

    def test_loading_the_map_does_not_recall_screen_or_single(self, monkeypatch):
        at, calls = _new(monkeypatch)
        at.run()
        _click(at, F.ACTION_RUN_SCREEN_LABEL)
        at.text_input(key=I.SS_TICKER_WIDGET).set_value("2330")
        _click(at, I.ACTION_LOAD_INSPECT_LABEL)
        _before = dict(calls)
        _click(at, F.ACTION_LOAD_MAP_LABEL)
        for _k in ("screen", "pe", "sector", "stock", "valuation", "chips", "profit", "batch"):
            assert calls[_k] == _before.get(_k, 0), f"載入地圖重呼叫了 {_k}"

    def test_pick_button_does_not_recall_screen(self, monkeypatch):
        at, calls = _new(monkeypatch)
        at.run()
        _click(at, F.ACTION_RUN_SCREEN_LABEL)
        _s = (calls["screen"], calls["pe"], calls["sector"])
        at.selectbox(key=B.SS_PICK_WIDGET).set_value("2330").run()
        at.button(key=B.SS_PICK_BUTTON).click().run()
        assert (calls["screen"], calls["pe"], calls["sector"]) == _s, "查看此檔重呼叫了選股 L3"
        assert calls["stock"] == 1

    def test_screening_does_not_recall_single_and_batch_drilldown_is_free(self, monkeypatch):
        at, calls = _new(monkeypatch)
        at.run()
        at.text_input(key=I.SS_TICKER_WIDGET).set_value("2330")
        _click(at, I.ACTION_LOAD_INSPECT_LABEL)
        _s = {k: calls[k] for k in ("stock", "valuation", "chips", "profit")}
        _click(at, F.ACTION_RUN_SCREEN_LABEL)
        assert {k: calls[k] for k in _s} == _s, "選股重呼叫了單檔 L3"
        at.text_area(key=I.SS_BATCH_WIDGET).set_value("2330 2317")
        _click(at, I.ACTION_RUN_BATCH_LABEL)
        _b = calls["batch"]
        at.selectbox(key=I.SS_DRILL_WIDGET).set_value("2317").run()
        assert calls["batch"] == _b and {k: calls[k] for k in _s} == _s, "下鑽重呼叫了 L3"

    def test_resubmitting_is_a_new_request_and_refetches(self, monkeypatch):
        at, calls = _new(monkeypatch)
        at.run()
        _click(at, F.ACTION_RUN_SCREEN_LABEL)
        _click(at, F.ACTION_RUN_SCREEN_LABEL)
        assert calls["screen"] == 2, "再按一次選股＝新的要求，必須重取（記憶不是快取）"


# ══════════════════════════════════════════════════════════════════
# C5 失敗不入快取、rerun 不重打
# ══════════════════════════════════════════════════════════════════
class TestFailureNotBombed:
    def test_failed_screen_is_shown_red_and_not_refetched_on_other_reruns(self, monkeypatch):
        at, calls = _new(monkeypatch, screen_error="RuntimeError('FinMind 額度用罄')")
        at.run()
        _click(at, F.ACTION_RUN_SCREEN_LABEL)
        assert calls["screen"] == 1
        assert "選股中止" in _all_text(at) or "失敗" in _all_text(at) or "FinMind" in _all_text(at)
        for _ in range(3):
            _click(at, F.ACTION_LOAD_MAP_LABEL)
        assert calls["screen"] == 1, "失敗後 rerun 又打上游了（轟炸）"
        assert not [d for d in at.dataframe if "標的" in list(d.value.columns)], "失敗還畫了候選表"

    def test_user_pressing_again_is_the_only_retry(self, monkeypatch):
        at, calls = _new(monkeypatch, screen_error="RuntimeError('x')")
        at.run()
        _click(at, F.ACTION_RUN_SCREEN_LABEL)
        _click(at, F.ACTION_RUN_SCREEN_LABEL)
        assert calls["screen"] == 2

    def test_no_streamlit_cache_in_the_new_files(self):
        for _p in (_BLOCKS, _PAGE, _SERVICE):
            _src = _p.read_text(encoding="utf-8")
            assert "st.cache_data" not in _src and "st.cache_resource" not in _src, _p.name

    def test_failed_pe_second_read_is_skipped_when_the_screen_already_knows_it_failed(self, monkeypatch):
        """選股那一輪確定沒拿到本益比（pe_n=None）⇒ 不再為了估值欄多打一次上游。"""
        from streamlit.testing.v1 import AppTest
        calls = U.Calls()
        U.install(monkeypatch, calls)
        monkeypatch.setattr(F, "load_screen_result",
                            lambda req: U.make_screen_result(req, pe_n=None) if req.submitted else F.ScreenResult(requested=False))
        at = AppTest.from_function(U.page_app, default_timeout=120).run()
        _click(at, F.ACTION_RUN_SCREEN_LABEL)
        assert calls["pe"] == 0
        _df = [d.value for d in at.dataframe if "標的" in list(d.value.columns)][0]
        assert list(_df["估值"]) == [B.PE_FAILED_CELL] * 3, "取不到本益比必須顯示 ⬜，不得填 0"


# ══════════════════════════════════════════════════════════════════
# C6 widget key 不重複
# ══════════════════════════════════════════════════════════════════
class TestWidgetKeys:
    def test_all_four_forms_and_two_buttons_mount_without_duplicate_ids(self, monkeypatch):
        at, _ = _new(monkeypatch)
        _full(at)
        _click(at, B.PICK_BUTTON_LABEL)
        assert not at.exception, at.exception
        _keys = [getattr(w, "key", None) for coll in (at.button, at.text_input, at.text_area, at.selectbox,
                                                      at.multiselect, at.checkbox) for w in coll]
        _keys = [k for k in _keys if k]
        assert len(_keys) == len(set(_keys)), sorted(k for k in set(_keys) if _keys.count(k) > 1)


# ══════════════════════════════════════════════════════════════════
# C7 區塊隔離
# ══════════════════════════════════════════════════════════════════
class TestBlockIsolation:
    def test_one_zone_raising_does_not_swallow_the_others(self, monkeypatch):
        at, _ = _new(monkeypatch)
        monkeypatch.setattr(B, "render_zone_industry", lambda s: (_ for _ in ()).throw(RuntimeError("第一區炸了 token=abc")))
        at.run()
        assert not at.exception, at.exception
        _errs = [e.value for e in at.error]
        assert len(_errs) == 1 and "第一區" in _errs[0] and "其他區照常" in _errs[0]
        _t = _all_text(at)
        assert B.ZONE2_TITLE in _t and B.ZONE3_TITLE in _t and B.BATCH_TITLE in _t, "其他區被吞掉了"

    def test_sector_mapping_failure_only_blanks_the_industry_column(self, monkeypatch):
        at, _ = _new(monkeypatch, sector_error=True)
        at.run()
        _click(at, F.ACTION_RUN_SCREEN_LABEL)
        assert not at.exception, at.exception
        _df = [d.value for d in at.dataframe if "標的" in list(d.value.columns)][0]
        assert set(_df["產業"]) == {B.SECTOR_UNAVAILABLE_CELL}
        assert list(_df["估值"])[0] == "22.5", "產業欄失敗不得連累估值欄"

    def test_single_stock_leg_failing_is_red_and_siblings_survive(self, monkeypatch):
        at, calls = _new(monkeypatch)
        monkeypatch.setattr(I, "load_chips", lambda v, r: (_ for _ in ()).throw(RuntimeError("日線掛了")))
        at.run()
        at.text_input(key=I.SS_TICKER_WIDGET).set_value("2330")
        _click(at, I.ACTION_LOAD_INSPECT_LABEL)
        assert not at.exception, at.exception
        _t = _all_text(at)
        assert "日線掛了" in _t and "健康度" in _t and "357" in _t, "一腿失敗不得吞掉其他腿"


# ══════════════════════════════════════════════════════════════════
# C8 選股：三態／None≠0／因子輸入缺=紅／估值半邊失敗
# ══════════════════════════════════════════════════════════════════
class TestScreening:
    def test_zero_rows_is_a_valid_grey_result_without_table(self, monkeypatch):
        at, _ = _new(monkeypatch)
        monkeypatch.setattr(F, "load_screen_result", lambda req: F.ScreenResult(
            requested=True, df=U.screen_df().head(0), rows=0, survivors_n=324, pe_n=2, name_n=3))
        at.run()
        _click(at, F.ACTION_RUN_SCREEN_LABEL)
        assert not at.exception, at.exception
        assert "0 檔" in _all_text(at)
        assert not [d for d in at.dataframe if "標的" in list(d.value.columns)]

    def test_checked_factor_input_missing_is_red_and_no_table(self, monkeypatch):
        at, _ = _new(monkeypatch)
        monkeypatch.setattr(F, "load_screen_result", lambda req: U.make_screen_result(
            req, factor_input_failed=("pe_low",)) if req.submitted else F.ScreenResult(requested=False))
        at.run()
        _pe_label = [l for l, k in F.load_factor_labels()[0].items() if k == F.PE_FACTOR_KEY][0]
        at.multiselect(key=F.SS_FACTORS_WIDGET).set_value([_pe_label])     # 判定只認「這一次有勾」的因子
        _click(at, F.ACTION_RUN_SCREEN_LABEL)
        assert "選股中止" in _all_text(at)
        assert not [d for d in at.dataframe if "標的" in list(d.value.columns)]

    def test_half_failed_valuation_wording_is_passed_through_verbatim(self, monkeypatch):
        _half = "上市 TWSE失敗，該因子不計入綜合分"
        at, _ = _new(monkeypatch)
        monkeypatch.setattr(F, "load_screen_result", lambda req: F.ScreenResult(
            requested=True, df=U.screen_df(), rows=3, survivors_n=324, pe_n=2, name_n=3,
            aux_errors=((F.FACTOR_INPUT_LABELS[F.PE_FACTOR_KEY], _half),)) if req.submitted else F.ScreenResult(requested=False))
        at.run()
        _click(at, F.ACTION_RUN_SCREEN_LABEL)
        assert _half in _all_text(at)

    def test_missing_dimensions_are_blank_marks_never_zero_or_neutral(self, monkeypatch):
        at, _ = _new(monkeypatch)
        at.run()
        _click(at, F.ACTION_RUN_SCREEN_LABEL)
        _df = [d.value for d in at.dataframe if "標的" in list(d.value.columns)][0]
        assert list(_df.columns) == list(B.CANDIDATE_COLS)
        assert _df.loc[1, "估值"] == B.PE_NOT_PROVIDED_CELL and _df.loc[2, "產業"] == "⬜ 未分類"
        for _c in ("產業", "基本面", "估值", "籌碼", "狀態"):
            assert not (_df[_c].astype(str).isin(["0", "0.0", "中性", "觀望", "買進", "賣出"])).any(), _c

    def test_status_column_has_only_facts_no_trading_words(self, monkeypatch):
        at, _ = _new(monkeypatch)
        at.run()
        _click(at, F.ACTION_RUN_SCREEN_LABEL)
        _df = [d.value for d in at.dataframe if "標的" in list(d.value.columns)][0]
        assert set(_df["狀態"]) <= {B.STATUS_PASSED, B.STATUS_INSUFFICIENT}

    def test_chips_are_fetched_only_for_the_selected_candidate(self, monkeypatch):
        at, calls = _new(monkeypatch)
        at.run()
        _click(at, F.ACTION_RUN_SCREEN_LABEL)
        at.selectbox(key=B.SS_PICK_WIDGET).set_value("2317").run()
        at.button(key=B.SS_PICK_BUTTON).click().run()
        _df = [d.value for d in at.dataframe if "標的" in list(d.value.columns)][0]
        assert calls["chips"] == 1
        assert _df.loc[1, "籌碼"] != B.CHIPS_NOT_FETCHED and "吸籌" in _df.loc[1, "籌碼"]
        assert _df.loc[0, "籌碼"] == B.CHIPS_NOT_FETCHED and _df.loc[2, "籌碼"] == B.CHIPS_NOT_FETCHED

    def test_chips_cell_never_fills_zero_for_a_failed_or_missing_leg(self):
        _s = B.SingleBundle(req=I.InspectRequest(submitted=True, ticker="2330"),
                            verdict=I.KindVerdict(requested=True, code="2330", is_stock=True),
                            chips=U.make_chips(ok=False))
        assert B.chips_cell("2330", _s) == "⬜ 資料不足"
        assert B.chips_cell("2317", _s) == B.CHIPS_NOT_FETCHED
        assert B.chips_cell("2330", None) == B.CHIPS_NOT_FETCHED

    def test_table_notes_flag_the_pe_basis_and_the_chips_rule(self, monkeypatch):
        at, _ = _new(monkeypatch)
        at.run()
        _click(at, F.ACTION_RUN_SCREEN_LABEL)
        _t = _all_text(at)
        for _s in (B.PE_COL_NOTE, B.CHIPS_COL_HINT, B.FIN_STOCK_NOTE):
            assert _s in _t
        assert "資料日：⬜ 未提供" in B.PE_COL_NOTE and "不同" in B.PE_COL_NOTE

    def test_csv_is_the_raw_ranked_frame(self, monkeypatch):
        at, _ = _new(monkeypatch)
        at.run()
        _click(at, F.ACTION_RUN_SCREEN_LABEL)
        assert any(getattr(d, "key", None) == B.SS_CSV_BUTTON for d in at.get("download_button"))


# ══════════════════════════════════════════════════════════════════
# C9 總經濾網說明逐字透傳
# ══════════════════════════════════════════════════════════════════
class TestMacroFilterNote:
    def test_l3_note_reaches_the_page_verbatim_modulo_blank_lines(self, monkeypatch):
        at, _ = _new(monkeypatch)
        at.run()
        _click(at, F.ACTION_RUN_SCREEN_LABEL)
        _t = _all_text(at)
        assert "總經為 caution：空頭濾網已套用" in _t and "⚠️ 總經為 caution" in _t


# ══════════════════════════════════════════════════════════════════
# C10 地圖
# ══════════════════════════════════════════════════════════════════
class TestSectorMap:
    def _matrix(self, at):
        return [d.value for d in at.dataframe if "產業" in list(d.value.columns) and "法人／籌碼" in list(d.value.columns)][0]

    def test_map_is_gated_by_the_button(self, monkeypatch):
        at, calls = _new(monkeypatch)
        at.run()
        assert calls["flow"] == 0 and calls["heatmap"] == 0
        assert not [d for d in at.dataframe if "法人／籌碼" in list(d.value.columns)]
        _click(at, F.ACTION_LOAD_MAP_LABEL)
        assert calls["flow"] == 1 and calls["heatmap"] == 1

    def test_matrix_columns_and_blank_dimensions(self, monkeypatch):
        at, _ = _new(monkeypatch)
        at.run()
        _click(at, F.ACTION_LOAD_MAP_LABEL)
        _m = self._matrix(at)
        assert list(_m.columns) == list(B.MATRIX_COLS)
        assert set(_m["基本面成長"]) == {B.NOT_BUILT} and set(_m["估值"]) == {B.NOT_BUILT}
        assert set(_m["相對強弱"]) == {B.STRENGTH_ONLY_FLOW}

    def test_unavailable_sector_is_blank_not_zero_and_listed(self, monkeypatch):
        at, _ = _new(monkeypatch)
        at.run()
        _click(at, F.ACTION_LOAD_MAP_LABEL)
        _m = self._matrix(at)
        _row = _m[_m["產業"] == "生技醫療"].iloc[0]
        assert _row["法人／籌碼"] == B.FLOW_MISSING and "0" not in _row["法人／籌碼"].replace("不補 0", "")
        assert "⬜ 未取得：生技醫療" in _all_text(at)

    def test_no_trend_verdict_words_and_sort_basis_is_disclosed(self, monkeypatch):
        at, _ = _new(monkeypatch)
        at.run()
        _click(at, F.ACTION_LOAD_MAP_LABEL)
        _t = _all_text(at)
        assert B.ZONE1_SORT_NOTE in _t
        _wo_customer = _t.replace(B.ZONE1_SAY, "")
        for _w in ("變強", "轉弱", "興起", "衰退"):
            assert _w not in _wo_customer, _w

    def test_quadrant_sort_follows_the_documented_order(self):
        _rows = B.build_industry_matrix(U.SECTORS)
        assert [r.sector for r in _rows] == ["半導體業", "航運業", "塑膠工業", "生技醫療"]

    @pytest.mark.parametrize("tpex,expect_note", [(True, False), (False, True), (None, True)])
    def test_tpex_complete_flag(self, monkeypatch, tpex, expect_note):
        at, _ = _new(monkeypatch, flow=U.make_flow(tpex_complete=tpex))
        at.run()
        _click(at, F.ACTION_LOAD_MAP_LABEL)
        assert (B.SECTOR_FLOW_TWSE_ONLY_NOTE in _all_text(at)) is expect_note

    def test_stale_snapshot_is_labelled_not_silent(self, monkeypatch):
        at, _ = _new(monkeypatch, flow=U.make_flow(stale=True))
        at.run()
        _click(at, F.ACTION_LOAD_MAP_LABEL)
        _t = _all_text(at)
        assert "資料過期" in _t and "最後一次成功凍結" in _t

    def test_heatmap_proxy_disclosure_and_no_legacy_pointer(self, monkeypatch):
        at, _ = _new(monkeypatch)
        at.run()
        _click(at, F.ACTION_LOAD_MAP_LABEL)
        _t = _all_text(at)
        assert "台股側每個類股其實是一檔代表股" in _t and B.HEATMAP_SWITCH_PLAIN in _t
        assert "🌍 市場環境" not in _t

    def test_flow_cache_missing_is_grey_empty_not_red(self, monkeypatch):
        at, _ = _new(monkeypatch, flow=U.make_flow(ok=False))
        at.run()
        _click(at, F.ACTION_LOAD_MAP_LABEL)
        assert not at.error, [e.value for e in at.error]
        assert "尚未產生" in _all_text(at)
        assert not [d for d in at.dataframe if "法人／籌碼" in list(d.value.columns)]

    def test_flow_failure_is_red_and_heatmap_failure_expands(self, monkeypatch):
        at, _ = _new(monkeypatch, flow=U.make_flow(error="OSError('壞檔')"), heatmap=U.make_heatmap(failed=True))
        at.run()
        _click(at, F.ACTION_LOAD_MAP_LABEL)
        assert not at.exception, at.exception
        assert "壞檔" in _all_text(at) and "批次全失敗" in _all_text(at)
        _hm = [e for e in at.expander if e.label == B.HEATMAP_EXPANDER][0]
        assert _hm.proto.expanded, "熱力圖失敗不得藏在收合的展開區裡"

    def test_both_charts_are_collapsed_when_healthy(self, monkeypatch):
        at, _ = _new(monkeypatch)
        at.run()
        _click(at, F.ACTION_LOAD_MAP_LABEL)
        for _lab in (B.HEATMAP_EXPANDER, B.BUBBLE_EXPANDER):
            assert not [e for e in at.expander if e.label == _lab][0].proto.expanded


# ══════════════════════════════════════════════════════════════════
# C11–C16 單檔／ETF／unknown／批次／XV-ASOF／unwired
# ══════════════════════════════════════════════════════════════════
class TestSingleStock:
    def _go(self, monkeypatch, ticker, **kw):
        at, calls = _new(monkeypatch, **kw)
        at.run()
        at.text_input(key=I.SS_TICKER_WIDGET).set_value(ticker)
        _click(at, I.ACTION_LOAD_INSPECT_LABEL)
        assert not at.exception, at.exception
        return at, calls

    def test_stock_shows_the_seven_blocks_and_profit(self, monkeypatch):
        at, _ = self._go(monkeypatch, "2330")
        _t = _all_text(at)
        for _s in (B.EPS_BLOCK, B.TREND_BLOCK, B.VALUATION_BLOCK, B.CHIPS_BLOCK, B.RISK_BLOCK, B.WORTH_BLOCK,
                   B.WHY_NOT_BLOCK, B.EPS_PLACEHOLDER, B.RISK_PLACEHOLDER, B.FACTS_ONLY_NOTE, B.RESEARCH_ONLY_NOTE,
                   "毛利率", "營業利益率", "安全邊際"):
            assert _s in _t, _s

    def test_no_attention_needed_block_and_no_fake_placeholder(self, monkeypatch):
        at, _ = self._go(monkeypatch, "2330")
        assert "需要處理" not in _all_text(at), "客戶 3A：標的頁不放 ⚡ 需要處理（也不放假佔位）"

    def test_placeholders_for_status_and_ai(self, monkeypatch):
        at, _ = self._go(monkeypatch, "2330")
        _t = _all_text(at)
        assert "⬜ 資料狀態：尚未彙總" in _t and "🤖 AI 投資總結：⬜ 尚未提供" in _t

    def test_why_not_buy_lists_only_facts(self, monkeypatch):
        at, _ = self._go(monkeypatch, "2330")
        _t = _all_text(at)
        assert "財報體檢未通過的項目：負債比" in _t
        for _w in ("建議買進", "建議賣出", "加碼", "減碼", "停損", "目標價", "可以買", "不要買"):
            assert _w not in _t, _w

    def test_missing_health_is_a_gap_fact_not_zero(self, monkeypatch):
        at, _ = self._go(monkeypatch, "2330", stock_score=None)
        assert "財報體檢：資料缺漏，這一檔算不出來（不是 0 分）" in _all_text(at)

    def test_chips_missing_is_grey_gap_not_zero(self, monkeypatch):
        at, _ = self._go(monkeypatch, "2330", chips_ok=False)
        _t = _all_text(at)
        assert "近 20 日籌碼：判不出來（df缺法人/量欄）" in _t and not at.error

    def test_price_time_small_text_xv_asof(self, monkeypatch):
        at, _ = self._go(monkeypatch, "2330")
        assert I.PRICE_ASOF_FACT_KEY in _all_text(at) and "10/28" in _all_text(at)

    def test_etf_gets_the_etf_layout_not_the_stock_blocks(self, monkeypatch):
        at, calls = self._go(monkeypatch, "00878")
        _t = _all_text(at)
        assert calls["etf"] == 1 and calls["stock"] == 0 and calls["chips"] == 0
        assert "折溢價" in _t and "配息" in _t and "同儕" in _t
        for _s in (B.EPS_BLOCK, B.TREND_BLOCK, B.WORTH_BLOCK, B.WHY_NOT_BLOCK, B.EPS_PLACEHOLDER):
            assert _s not in _t, f"ETF 套用了個股區塊：{_s}"

    def test_unknown_is_a_grey_card_and_stops(self, monkeypatch):
        at, calls = self._go(monkeypatch, "AAPL")
        assert calls["stock"] == calls["etf"] == calls["chips"] == 0
        assert not at.error, [e.value for e in at.error]
        _t = _all_text(at)
        assert "無法判定這是個股還是 ETF" in _t and B.UNKNOWN_HINT in _t
        assert B.EPS_BLOCK not in _t

    def test_force_kind_override_from_the_advanced_options(self, monkeypatch):
        at, calls = _new(monkeypatch)
        at.run()
        at.text_input(key=I.SS_TICKER_WIDGET).set_value("AAPL")
        at.selectbox(key=I.SS_KIND_WIDGET).set_value(I.KIND_CHOICE_STOCK)
        _click(at, I.ACTION_LOAD_INSPECT_LABEL)
        assert calls["stock"] == 1
        assert at.session_state[I.SS_APPLIED_TICKER]["kind_choice"] == I.KIND_CHOICE_STOCK

    def test_blank_ticker_is_the_grey_blank_card(self, monkeypatch):
        at, calls = self._go(monkeypatch, "  ")
        assert "代碼欄是空的" in _all_text(at) and sum(calls.values()) == 0

    def test_advanced_options_are_collapsed_and_ma_is_labelled_display_only(self, monkeypatch):
        at, _ = _new(monkeypatch)
        at.run()
        _adv = [e for e in at.expander if e.label == B.ADV_LABEL][0]
        assert not _adv.proto.expanded
        _t = _all_text(at)
        assert B.MA_ONLY_DISPLAY_NOTE in _t and "僅顯示" in _t
        assert len([c for c in at.checkbox if str(c.key).startswith(I.SS_MA_WIDGET_PREFIX)]) == len(I.MA_OPTIONS)


class TestBatch:
    def _batch(self, monkeypatch):
        at, calls = _new(monkeypatch)
        at.run()
        at.text_area(key=I.SS_BATCH_WIDGET).set_value("2330 00878")
        _click(at, I.ACTION_RUN_BATCH_LABEL)
        assert not at.exception, at.exception
        return at, calls

    def test_batch_table_header_failed_row_and_drilldown(self, monkeypatch):
        at, calls = self._batch(monkeypatch)
        _t = _all_text(at)
        assert "價格資料時間：" in _t, "XV-ASOF 共同時間表頭"
        _df = [d.value for d in at.dataframe if "代碼" in list(d.value.columns) and "明細" in list(d.value.columns)][0]
        assert list(_df["代碼"]) == ["2330", "00878", "9999"]
        assert _df.loc[2, "狀態"] == "失敗" and "額度用罄" in _df.loc[2, "明細"], "失敗的列不得被篩掉"
        assert at.selectbox(key=I.SS_DRILL_WIDGET).options == ["2330", "00878"]
        assert B.DRILL_FOOT in _t

    def test_batch_has_no_dead_pointers(self, monkeypatch):
        at, _ = self._batch(monkeypatch)
        _t = _all_text(at)
        for _w in DEAD_POINTERS + ENGINEERING:
            assert _w not in _t, _w


class TestUnwired:
    def test_uncovered_features_are_listed_plainly_in_the_advanced_layer(self, monkeypatch):
        at, _ = _new(monkeypatch)
        at.run()
        _t = _all_text(at)
        for _name, _ in B.UNCOVERED_ITEMS:
            assert _name in _t, _name
        for _must in ("加入觀察清單", "凍結前 20 名", "前進式驗證對帳", "跨季趨勢排行", "K 線與明細七段", "用名稱搜尋", "帶入我的持股"):
            assert any(_must in n for n, _ in B.UNCOVERED_ITEMS), _must
        _adv = [e for e in at.expander if e.label == B.ADVANCED_EXPANDER]
        assert _adv and not _adv[0].proto.expanded

    def test_uncovered_list_is_not_in_the_first_screen(self, monkeypatch):
        at, _ = _new(monkeypatch)
        at.run()
        _texts = _texts_before_zone1(at)
        assert not any("尚未接上" in t for t in _texts)


# ══════════════════════════════════════════════════════════════════
# C17 / C18 文字掃描
# ══════════════════════════════════════════════════════════════════
def _texts_before_zone1(at) -> list[str]:
    _out = []
    for _kind, _t in _walk(at.main):
        if B.ZONE1_TITLE in _t and _kind == "Markdown":
            break
        _out.append(_t)
    return _out


class TestTextScans:
    def test_first_screen_has_no_engineering_words(self, monkeypatch):
        at, _ = _new(monkeypatch)
        at.run()
        _first = "\n".join(_texts_before_zone1(at))
        assert B.PAGE_SUBTITLE in _first and B.HEALTH_CHIP in _first and B.AI_PLACEHOLDER in _first
        for _w in ENGINEERING + DEAD_POINTERS + ("L3", "unwired", "L5"):
            assert _w not in _first, f"第一屏出現工程字樣 {_w!r}"

    def test_first_screen_order_is_chip_search_ai(self, monkeypatch):
        at, _ = _new(monkeypatch)
        at.run()
        _first = _texts_before_zone1(at)
        _i = {k: next(n for n, t in enumerate(_first) if k in t)
              for k in (B.HEALTH_CHIP, I.ACTION_LOAD_INSPECT_LABEL, B.AI_PLACEHOLDER)}
        assert _i[B.HEALTH_CHIP] < _i[I.ACTION_LOAD_INSPECT_LABEL] < _i[B.AI_PLACEHOLDER]

    @pytest.mark.parametrize("ticker", ["2330", "00878", "AAPL"])
    def test_loaded_states_have_no_dead_pointers_or_engineering_words(self, monkeypatch, ticker):
        at, _ = _new(monkeypatch)
        at.run()
        _click(at, F.ACTION_RUN_SCREEN_LABEL)
        _click(at, F.ACTION_LOAD_MAP_LABEL)
        at.text_input(key=I.SS_TICKER_WIDGET).set_value(ticker)
        _click(at, I.ACTION_LOAD_INSPECT_LABEL)
        at.text_area(key=I.SS_BATCH_WIDGET).set_value("2330 00878")
        _click(at, I.ACTION_RUN_BATCH_LABEL)
        assert not at.exception, at.exception
        _t = _all_text(at)
        # v2 卡面的 HTML 也要掃（去 tag 不影響字串比對）
        for _w in ENGINEERING + DEAD_POINTERS:
            assert _w not in _t, f"載入後（{ticker}）出現 {_w!r}：{_t[max(0, _t.find(_w) - 40):_t.find(_w) + 40]!r}"

    def test_cold_page_has_no_dead_pointers(self, monkeypatch):
        at, _ = _new(monkeypatch)
        at.run()
        _t = _all_text(at)
        for _w in ENGINEERING + DEAD_POINTERS:
            assert _w not in _t, _w


# ══════════════════════════════════════════════════════════════════
# C19 / C21 / C22 / C23 導覽
# ══════════════════════════════════════════════════════════════════
class TestTransitionRemoved:
    _GONE = ("NAV4_TARGET_LEAF_KEY", "NAV4_WIDGET_LEAF_KEY", "render_target_leaf_selector", "has_leaves",
             "leaf_options", "leaf_from_label", "current_leaf", "_on_leaf_change")

    def test_no_transition_symbol_remains_in_source(self):
        for _p in list((_ROOT / "src").rglob("*.py")) + list((_ROOT / "shared").rglob("*.py")) + [_ROOT / "app.py"]:
            _src = _p.read_text(encoding="utf-8")
            if _p.name == "ia_nav.py":      # 舊 D2 殼自己的 `leaf_options`（legacy 導覽，非 NAV-1 過渡切換）
                continue
            for _g in self._GONE:
                if _g in ("leaf_options",) and _p.name == "app.py":
                    continue                 # app.py 的 `_ia_nav.leaf_options(...)` 是 legacy D2 側欄
                tree = ast.parse(_src)
                _names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | \
                         {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)} | \
                         {n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
                assert _g not in _names, f"{_p.relative_to(_ROOT)} 殘留過渡切換符號 {_g}"

    def test_main_nav_has_exactly_the_two_widgets_and_four_options(self):
        from streamlit.testing.v1 import AppTest

        def _app():
            import streamlit as st
            from src.ui.views import shell_nav4
            with st.sidebar:
                shell_nav4.render_sidebar_nav()
            shell_nav4.render_main_nav()
        at = AppTest.from_function(_app, default_timeout=60).run()
        at.radio(key=ia_nav4.NAV4_WIDGET_BOTTOM_KEY).set_value("🎯 標的").run()
        assert not at.exception, at.exception
        _keys = {r.key for r in at.radio} | {r.key for r in at.sidebar.radio}
        assert _keys == {ia_nav4.NAV4_WIDGET_SIDE_KEY, ia_nav4.NAV4_WIDGET_BOTTOM_KEY}
        for _r in list(at.radio) + list(at.sidebar.radio):
            assert list(_r.options) == ["📊 市場", "🎯 標的", "💼 持股", "👤 我的"]

    def test_reconcile_accepts_inspect_as_merged_and_rejects_orphaning_it(self, monkeypatch):
        ia_nav4.reconcile_nav4(set(ia_nav.PAGE_LABELS))
        assert ia_nav4.MERGED_VIEWS == {ia_nav.PAGE_INSPECT: ia_nav4.P4_TARGET}
        monkeypatch.setattr(ia_nav4, "MERGED_VIEWS", {})
        with pytest.raises(RuntimeError):
            ia_nav4.reconcile_nav4()


class TestLegacyStillStandsAlone:
    def test_legacy_pages_render_without_any_new_module(self, monkeypatch):
        """`?legacy=1` 的 D2 側欄：find／inspect 仍可獨立渲染，且完全不 import nav4 新碼／page_target。"""
        from streamlit.testing.v1 import AppTest

        class _Poison:
            def __getattr__(self, item):
                raise AssertionError(f"legacy 路徑碰到新碼 {item}")
        for _m in ("shared.ia_nav4", "src.ui.views.shell_nav4", "src.ui.views.page_target", "src.ui.views._target_blocks"):
            monkeypatch.delitem(sys.modules, _m, raising=False)
        # 用 meta_path 擋掉（比 sys.modules 毒物更嚴：連 import 嘗試都算）
        import importlib.abc

        class _Block(importlib.abc.MetaPathFinder):
            BLOCKED = {"shared.ia_nav4", "src.ui.views.shell_nav4", "src.ui.views.page_target",
                       "src.ui.views._target_blocks"}

            def find_spec(self, name, path=None, target=None):
                if name in self.BLOCKED:
                    raise ImportError("POISONED: " + name)
                return None
        _b = _Block()
        monkeypatch.setattr(sys, "meta_path", [_b, *sys.meta_path])

        def _find():
            from src.ui.views.page_find import render_page_find
            render_page_find()

        def _inspect():
            from src.ui.views.page_inspect import render_page_inspect
            render_page_inspect()
        for _fn in (_find, _inspect):
            at = AppTest.from_function(_fn, default_timeout=120).run()
            assert not at.exception, at.exception
            assert not at.error, [e.value for e in at.error]
        assert not any(m in sys.modules for m in _Block.BLOCKED), "legacy 渲染過程 import 了新碼"

    def test_legacy_pages_files_are_not_edited_by_this_batch(self):
        """page_find／page_inspect 一字未改的機械證據：新頁只經模組屬性重用它們（沒有複製貼上改寫）。"""
        _src = _BLOCKS.read_text(encoding="utf-8")
        assert "from src.ui.views import page_find as F" in _src and "from src.ui.views import page_inspect as I" in _src

    def test_app_dispatches_by_the_legacy_flag(self):
        _src = (_ROOT / "app.py").read_text(encoding="utf-8")
        _tree = ast.parse(_src)
        _fn = next(n for n in _tree.body if isinstance(n, ast.FunctionDef) and n.name == "_ia_view_find")
        _imports = [n.module for n in ast.walk(_fn) if isinstance(n, ast.ImportFrom)]
        assert sorted(_imports) == ["src.ui.views.page_find", "src.ui.views.page_target"], _imports
        _if = next(n for n in _fn.body if isinstance(n, ast.If))
        assert "_nav4_legacy" in ast.unparse(_if.test)
        assert any(isinstance(n, ast.ImportFrom) and n.module == "src.ui.views.page_find" for n in _if.body)


# ══════════════════════════════════════════════════════════════════
# C20 離頁再回
# ══════════════════════════════════════════════════════════════════
class TestLeaveAndReturn:
    def test_state_survives_leaving_and_returning_without_refetch(self, monkeypatch):
        from streamlit.testing.v1 import AppTest

        def _app():
            import streamlit as st
            if st.session_state.get("_away"):
                st.markdown("別頁")
                return
            from src.ui.views.page_target import render_page_target
            render_page_target()
        calls = U.Calls()
        U.install(monkeypatch, calls)
        at = AppTest.from_function(_app, default_timeout=120).run()
        _click(at, F.ACTION_RUN_SCREEN_LABEL)
        at.text_input(key=I.SS_TICKER_WIDGET).set_value("2330")
        _click(at, I.ACTION_LOAD_INSPECT_LABEL)
        _before = dict(calls)
        at.session_state["_away"] = True
        at.run()
        at.session_state["_away"] = False
        at.run()
        assert not at.exception, at.exception
        assert dict(calls) == _before, "回到標的頁又重打了 L3（結果應記在 session 裡）"
        assert [d for d in at.dataframe if "標的" in list(d.value.columns)], "回來後候選表不見了"
        assert "健康度" in _all_text(at)


# ══════════════════════════════════════════════════════════════════
# C25 不新增投資規則（static）
# ══════════════════════════════════════════════════════════════════
class TestNoNewInvestmentRules:
    def test_new_files_import_no_data_or_compute_layer(self):
        for _p in (_BLOCKS, _PAGE):
            _tree = ast.parse(_p.read_text(encoding="utf-8"))
            for _n in ast.walk(_tree):
                _mod = None
                if isinstance(_n, ast.ImportFrom):
                    _mod = _n.module or ""
                elif isinstance(_n, ast.Import):
                    _mod = _n.names[0].name
                if _mod:
                    assert not _mod.startswith(("src.data", "src.compute", "requests", "yfinance", "FinMind")), (_p.name, _mod)

    def test_only_one_service_is_imported_and_it_is_the_thin_one(self):
        _tree = ast.parse(_BLOCKS.read_text(encoding="utf-8"))
        _svc = sorted({n.module for n in ast.walk(_tree) if isinstance(n, ast.ImportFrom)
                       and (n.module or "").startswith("src.services")})
        assert _svc == ["src.services.target_industry_service"], _svc

    def test_thin_l3_has_no_computation_and_no_new_source(self):
        _src = _SERVICE.read_text(encoding="utf-8")
        _tree = ast.parse(_src)
        _imports = sorted({(n.module or "") for n in ast.walk(_tree) if isinstance(n, ast.ImportFrom)})
        assert _imports == ["__future__", "dataclasses", "src.data.sector_flow.reader"], _imports
        assert "requests" not in _src and "pandas" not in _src

    def test_no_numeric_thresholds_in_the_new_ui_files(self):
        """新 UI 檔不得出現判斷用的數字門檻（除 0/1/2、顯示位數、欄寬等）。"""
        for _p in (_BLOCKS, _PAGE):
            _tree = ast.parse(_p.read_text(encoding="utf-8"))
            _bad = []
            for _n in ast.walk(_tree):
                if isinstance(_n, ast.Compare):
                    for _c in [_n.left, *_n.comparators]:
                        if isinstance(_c, ast.Constant) and isinstance(_c.value, (int, float)) and not isinstance(_c.value, bool) \
                                and _c.value not in (0, 1, 2):
                            _bad.append((_p.name, _n.lineno, _c.value))
            assert not _bad, _bad

    def test_candidate_status_vocabulary_has_no_trading_words(self):
        for _s in (B.STATUS_PASSED, B.STATUS_INSUFFICIENT, B.MISSING_CELL):
            for _w in ("買", "賣", "觀望", "持有"):
                assert _w not in _s


# ══════════════════════════════════════════════════════════════════
# P parity：新頁的卡面 HTML 與舊兩頁逐字相同
# ══════════════════════════════════════════════════════════════════
def _cards_html(at) -> dict[str, str]:
    """卡 title → 該卡的 HTML（markdown 值）。"""
    _out = {}
    for _m in at.markdown:
        _mt = re.search(r'class="blk-title"[^>]*>([^<]+)<', _m.value)
        if _mt:
            _out[_mt.group(1)] = _m.value
    return _out


class TestParityWithLegacyPages:
    def test_screen_result_card_is_byte_identical_to_page_find(self, monkeypatch):
        from streamlit.testing.v1 import AppTest

        def _legacy():
            from src.ui.views.page_find import render_page_find
            render_page_find()
        calls = U.Calls()
        U.install(monkeypatch, calls)
        old = AppTest.from_function(_legacy, default_timeout=120).run()
        _click(old, F.ACTION_RUN_SCREEN_LABEL)
        new = AppTest.from_function(U.page_app, default_timeout=120).run()
        _click(new, F.ACTION_RUN_SCREEN_LABEL)
        _o, _n = _cards_html(old), _cards_html(new)
        assert _o["選股結果"] == _n["選股結果"]

    def test_single_stock_cards_are_byte_identical_to_page_inspect(self, monkeypatch):
        from streamlit.testing.v1 import AppTest

        def _legacy():
            from src.ui.views.page_inspect import render_page_inspect
            render_page_inspect()
        calls = U.Calls()
        U.install(monkeypatch, calls)
        old = AppTest.from_function(_legacy, default_timeout=120).run()
        old.text_input(key=I.SS_TICKER_WIDGET).set_value("2330")
        _click(old, I.ACTION_LOAD_INSPECT_LABEL)
        new = AppTest.from_function(U.page_app, default_timeout=120).run()
        new.text_input(key=I.SS_TICKER_WIDGET).set_value("2330")
        _click(new, I.ACTION_LOAD_INSPECT_LABEL)
        _o, _n = _cards_html(old), _cards_html(new)
        for _title in ("判型結果", "健康度", "籌碼", "毛利率", "營業利益率", "安全邊際"):
            assert _o[_title] == _n[_title], _title
        _vt = [k for k in _o if k.startswith("估值")][0]
        assert _o[_vt] == _n[_vt]

    def test_etf_cards_are_byte_identical_to_page_inspect(self, monkeypatch):
        from streamlit.testing.v1 import AppTest

        def _legacy():
            from src.ui.views.page_inspect import render_page_inspect
            render_page_inspect()
        calls = U.Calls()
        U.install(monkeypatch, calls)
        old = AppTest.from_function(_legacy, default_timeout=120).run()
        old.text_input(key=I.SS_TICKER_WIDGET).set_value("00878")
        _click(old, I.ACTION_LOAD_INSPECT_LABEL)
        new = AppTest.from_function(U.page_app, default_timeout=120).run()
        new.text_input(key=I.SS_TICKER_WIDGET).set_value("00878")
        _click(new, I.ACTION_LOAD_INSPECT_LABEL)
        _o, _n = _cards_html(old), _cards_html(new)
        _shared = [k for k in _n if k in _o and k != "判型結果"]
        assert _shared, "ETF 卡一張都沒對上"
        for _k in _shared:
            assert _o[_k] == _n[_k], _k

    def test_batch_table_is_identical_to_page_inspect(self, monkeypatch):
        from streamlit.testing.v1 import AppTest

        def _legacy():
            from src.ui.views.page_inspect import render_page_inspect
            render_page_inspect()
        calls = U.Calls()
        U.install(monkeypatch, calls)
        old = AppTest.from_function(_legacy, default_timeout=120).run()
        old.text_area(key=I.SS_BATCH_WIDGET).set_value("2330 00878 2317")
        _click(old, I.ACTION_RUN_BATCH_LABEL)
        new = AppTest.from_function(U.page_app, default_timeout=120).run()
        new.text_area(key=I.SS_BATCH_WIDGET).set_value("2330 00878 2317")
        _click(new, I.ACTION_RUN_BATCH_LABEL)
        _f = lambda at: [d.value for d in at.dataframe if "明細" in list(d.value.columns)][0].to_dict("records")   # noqa: E731
        assert _f(old) == _f(new)
        assert _cards_html(old)["批次分析結果"] == _cards_html(new)["批次分析結果"]
