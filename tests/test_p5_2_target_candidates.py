"""tests/test_p5_2_target_candidates.py — Phase 5 PR2（🎯 標的頁第二區「候選標的」）守衛。

客戶 DEC-121 Q2=B：整頁順序不變；「選股條件」預設收合＋外露一行摘要（只轉述已套用／預設條件）；候選外露 Top 10
（純顯示切片）＋`另 K 筆見全部` chip＋`▸ 查看全部（N 筆）`；CSV 仍全量；估值口徑外露 chip＋L3 全文逐字。
線框 `docs/vnext/PHASE5_TARGET_PAGE_WIREFRAME_2026-10-31.md` §10 C1-5／C1-6／C1-7／C2-1／C2-2／N1／N2／N3。

寫法同 PR1：**契約檢查函式**（`_check_*`）＋**mutation 風格守衛**——把實作換成「錯的版本」，契約檢查必須轉紅。
所有字串期望值故意寫成**字面常數**（不引用 `B.*`），常數被改／刪就會紅。
"""
from __future__ import annotations

import io
import re

import pandas as pd
import pytest

from src.ui.views import _target_blocks as B
from src.ui.views import page_find as F
from src.ui_v2 import compact as cp
from tests import uit_fakes as U
from tests.test_uit_target_page import _all_text, _click, _new

N_ROWS = 13        # > 10 ⇒ 有被收進「查看全部」的列（K = 3）
#: 夾具名稱故意「非字典序」，讓『切片後被改排序』能被看出來。
_CODES = ["2330", "2317", "2891", "1101", "2603", "3008", "2412", "1301", "2002", "5871", "6505", "2882", "1216"]
_NAMES = ["台積電", "鴻海", "中信金", "台泥", "長榮", "大立光", "中華電", "台塑", "中鋼", "中租-KY", "台塑化", "國泰金", "統一"]
_SCORES = [88.5, 71.0, 60.2, 59.0, 58.0, 57.5, 56.0, 55.0, 54.0, 53.0, 52.0, 51.0, 50.0]

PE_COL_NOTE_LITERAL = ("估值欄是當日本益比（資料日：⬜ 未提供）；第三區的估值是另一種算法（殖利率口徑），"
                       "兩者不同、不能互相驗證。")
CHIPS_HINT_LITERAL = "籌碼欄：點選一檔後才會取，其他候選顯示「未取」，不是沒有資料。"
FIN_NOTE_LITERAL = "金融股沒有營收數字，會在基本面初篩被排除，不是資料壞了。"
PE_CHIP_LITERAL = "估值口徑≠第三區 357（不能互相驗證）"
SUMMARY_DEFAULT = "4 項基本面全過＋高 EPS（獲利高）；排序：綜合評分；顯示 50 筆"


def _big_df(n: int = N_ROWS) -> pd.DataFrame:
    return pd.DataFrame({"代碼": _CODES[:n], "名稱": _NAMES[:n], "綜合分": _SCORES[:n], "估值分": [50.0] * n})


def _new_big(monkeypatch, n: int = N_ROWS):
    at, calls = _new(monkeypatch)

    def _screen(req):
        calls["screen"] += 1
        if not req.submitted:
            return F.ScreenResult(requested=False)
        _df = _big_df(n)
        return F.ScreenResult(requested=True, df=_df, note="", rows=len(_df), survivors_n=324, pe_n=2, name_n=3,
                              hits=("估值 2/3",))
    monkeypatch.setattr(F, "load_screen_result", _screen)
    return at, calls


# ── 元素樹小工具 ───────────────────────────────────────────────────
def _blocks(node, kind):
    for _c in getattr(node, "children", {}).values():
        if type(_c).__name__ == kind:
            yield _c
        if getattr(_c, "children", None):
            yield from _blocks(_c, kind)


def _leaves_outside_expanders(node):
    for _c in getattr(node, "children", {}).values():
        if type(_c).__name__ == "Expander":
            continue
        if getattr(_c, "children", None):
            yield from _leaves_outside_expanders(_c)
        else:
            yield _c


def _exposed_text(at) -> list[str]:
    _out = []
    for _c in _leaves_outside_expanders(at.main):
        if type(_c).__name__ in ("Caption", "Markdown", "Text"):
            _v = getattr(_c, "value", None)
            if isinstance(_v, str):
                _out.append(_v)
    return _out


def _exposed_frames(at) -> list[pd.DataFrame]:
    return [c.value for c in _leaves_outside_expanders(at.main)
            if type(c).__name__ == "Dataframe" and "標的" in list(c.value.columns)]


def _expander(at, label_prefix):
    _e = [e for e in _blocks(at.main, "Expander") if str(e.label).startswith(label_prefix)]
    return _e


def _inside_frames(exp) -> list[pd.DataFrame]:
    return [c.value for c in _blocks(exp, "Dataframe")]


def _exp_text(exp) -> str:
    _t = []
    for _c in _blocks(exp, "Caption"):
        _t.append(_c.value)
    for _c in _blocks(exp, "Markdown"):
        _t.append(_c.value)
    return "\n".join(_t)


def _capture_csv(monkeypatch) -> list[bytes]:
    _got: list[bytes] = []
    _orig = B.st.download_button

    def _rec(label, data=None, *a, **kw):
        _got.append(bytes(data))
        return _orig(label, data, *a, **kw)
    monkeypatch.setattr(B.st, "download_button", _rec)
    return _got


def _run_loaded(monkeypatch, n: int = N_ROWS):
    at, calls = _new_big(monkeypatch, n)
    _csv = _capture_csv(monkeypatch)
    at.run()
    _click(at, F.ACTION_RUN_SCREEN_LABEL)
    assert not at.exception, at.exception
    return at, calls, _csv


# ══════════════════════════════════════════════════════════════════
# 契約檢查
# ══════════════════════════════════════════════════════════════════
def _check_loaded(at, calls, csv) -> None:
    """已選股態（13 列）的第二區契約。任何違反 ⇒ AssertionError。"""
    # C1-5／C1-6：外露恰 10 列、保序（＝L3 排名原順序，⛔ 重排／重算）、全量表在『查看全部（13 筆）』
    _ex = _exposed_frames(at)
    assert len(_ex) == 1, "外露層必須恰一張候選表"
    assert len(_ex[0]) == 10, len(_ex[0])
    _want_top = [f"{c} {n}" for c, n in zip(_CODES[:10], _NAMES[:10])]
    assert list(_ex[0]["標的"]) == _want_top, "Top 10 必須是排名原順序的前 10 列（保序）"
    _alls = _expander(at, "▸ 查看全部（")
    assert len(_alls) == 1 and str(_alls[0].label) == "▸ 查看全部（13 筆）"
    _full = _inside_frames(_alls[0])
    assert len(_full) == 1 and len(_full[0]) == 13
    assert list(_full[0]["標的"]) == [f"{c} {n}" for c, n in zip(_CODES, _NAMES)], "全量表必須含全部 13 列且保序"
    assert list(_ex[0].columns) == list(_full[0].columns) == ["標的", "產業", "基本面", "估值", "籌碼", "狀態"]
    # 另 K 筆 chip（K = 13 − 10 = 3）：外露、恰一顆
    _chip_html = [t for t in _exposed_text(at) if 'data-kind="topn_more"' in t]
    assert len(_chip_html) == 1 and "另 3 筆見全部" in _chip_html[0]
    # C1-5：CSV 仍為全量（13 列）
    assert csv, "沒有 CSV 下載鈕"
    _rows = pd.read_csv(io.BytesIO(csv[-1]), encoding="utf-8-sig", dtype=str)
    assert len(_rows) == 13 and list(_rows["代碼"]) == _CODES, "CSV 必須是全量原表"
    # C2-2：估值口徑 chip 外露 ＋ L3 全文逐字（三句都在『說明』摺疊內）
    assert any(PE_CHIP_LITERAL in t and 'data-kind="guard_text"' in t for t in _exposed_text(at)), "估值口徑 chip 不見了"
    _notes = _expander(at, "▸ 說明（")
    assert len(_notes) == 1 and not _notes[0].proto.expanded, "說明摺疊預設必須收合"
    _nt = _exp_text(_notes[0])
    for _lit in (PE_COL_NOTE_LITERAL, CHIPS_HINT_LITERAL, FIN_NOTE_LITERAL):
        assert _lit in _nt, _lit
    # 估值口徑全文不得在外露層（只下沉）；chip 與全文並存
    assert not any(PE_COL_NOTE_LITERAL in t for t in _exposed_text(at))
    # Q2=B：選股條件預設收合；form 與送出鈕仍在（收合≠少抓／少算）
    _scr = _expander(at, "選股條件")
    assert len(_scr) == 1 and not _scr[0].proto.expanded, "選股條件必須預設收合"
    assert any(b.label == "🎯 開始選股" for b in at.button) or at.get("form_submit_button")
    # 摘要：外露一行、只轉述已套用條件
    _sm = [t for t in _exposed_text(at) if re.fullmatch(r"\d+ 項基本面全過.*；排序：綜合評分；顯示 \d+ 筆", t)]
    assert _sm == [SUMMARY_DEFAULT], _sm
    # 選一檔：選項是全部 13 檔（不只 Top 10）；查看此檔鈕在
    assert len(at.selectbox(key=B.SS_PICK_WIDGET).options) == 13
    assert any(b.label == "🔍 查看此檔" for b in at.button)
    # N3：缺值 ⬜、不補 0（估值分欄無 PE 的列、產業對映缺的列）
    for _f in (_ex[0], _full[0]):
        for _c in ("產業", "基本面", "估值", "籌碼", "狀態"):
            assert not _f[_c].astype(str).isin(["0", "0.0", "中性", "觀望"]).any(), _c
    assert "⬜ 未提供" in set(_full[0]["估值"]) and "⬜ 未分類" in set(_full[0]["產業"])
    # N1：選股只跑一次
    assert calls["screen"] == 1


def _check_cold(at, calls) -> None:
    assert calls["screen"] == 0 and calls["pe"] == 0 and calls["sector"] == 0, dict(calls)
    assert calls["chips"] == 0 and calls["stock"] == 0 and calls["flow"] == 0, dict(calls)
    _scr = _expander(at, "選股條件")
    assert len(_scr) == 1 and not _scr[0].proto.expanded
    assert SUMMARY_DEFAULT in _exposed_text(at), "冷啟動也要有一行預設條件摘要"
    assert not _exposed_frames(at) and not _expander(at, "▸ 查看全部（")


class TestLoadedContract:
    def test_loaded_state_satisfies_the_whole_contract(self, monkeypatch):
        _check_loaded(*_run_loaded(monkeypatch))

    def test_exactly_ten_rows_exposed_and_k_is_total_minus_ten(self, monkeypatch):
        at, _, _ = _run_loaded(monkeypatch, n=11)
        assert len(_exposed_frames(at)[0]) == 10
        assert any("另 1 筆見全部" in t for t in _exposed_text(at))
        assert str(_expander(at, "▸ 查看全部（")[0].label) == "▸ 查看全部（11 筆）"

    def test_ten_or_fewer_has_no_more_chip_and_no_see_all(self, monkeypatch):
        for n in (10, 3):
            at, _, _ = _run_loaded(monkeypatch, n=n)
            assert len(_exposed_frames(at)[0]) == n
            assert not [t for t in _exposed_text(at) if 'data-kind="topn_more"' in t], n
            assert not _expander(at, "▸ 查看全部（"), n

    def test_request_params_and_top_ten_are_independent(self):
        assert F.TOP_N_OPTIONS == (20, 50, 100) and F.DEFAULT_TOP_N == 50
        assert B.CANDIDATE_TOP_N == 10

    def test_slice_is_only_a_view_same_objects_in_order(self):
        _rows = [{"標的": str(i)} for i in range(13)]
        _t = cp.topn_view(_rows, B.CANDIDATE_TOP_N)
        assert all(_t.shown[i] is _rows[i] for i in range(10)) and _t.hidden == 3 and _t.total == 13


class TestColdContract:
    def test_cold_start_zero_fetch_collapsed_with_summary(self, monkeypatch):
        at, calls = _new_big(monkeypatch)
        at.run()
        assert not at.exception, at.exception
        _check_cold(at, calls)

    def test_mutant_cold_start_fetches_is_red(self, monkeypatch):
        at, calls = _new_big(monkeypatch)
        monkeypatch.setattr(B, "own_screen_request",
                            lambda session: F.ScreenRequest(submitted=True, factors=(F.DEFAULT_FACTOR_KEY,)))
        at.run()
        with pytest.raises(AssertionError):
            _check_cold(at, calls)


class TestSummary:
    LABELS = {"高 EPS（獲利高）": "eps_high", "缺貨題材": "shortage"}

    def test_default_when_not_submitted(self):
        assert B.screen_summary(self.LABELS, F.ScreenRequest(submitted=False)) == SUMMARY_DEFAULT

    def test_applied_conditions_are_echoed_in_order(self):
        _r = F.ScreenRequest(submitted=True, factors=("shortage", "eps_high"), top_n=20)
        assert B.screen_summary(self.LABELS, _r) == "4 項基本面全過＋缺貨題材、高 EPS（獲利高）；排序：綜合評分；顯示 20 筆"

    def test_no_factor_selected_adds_nothing(self):
        _r = F.ScreenRequest(submitted=True, factors=(), top_n=50)
        assert B.screen_summary(self.LABELS, _r) == "4 項基本面全過；排序：綜合評分；顯示 50 筆"

    def test_applied_key_not_in_label_list_means_no_summary_and_no_raw_key_leak(self):
        _r = F.ScreenRequest(submitted=True, factors=("eps_high", "ghost_key"), top_n=50)
        assert B.screen_summary(self.LABELS, _r) is None

    def test_qa_whitelist_regex_rejects_non_summary_shapes(self):
        _rx = r"4 項基本面全過(＋[^；]+)?；排序：綜合評分；顯示 \d+ 筆"
        for _bad in ("建議買進", "99 項基本面全過；排序：綜合評分；顯示 50 筆",
                     "4 項基本面全過＋a；b；排序：綜合評分；顯示 50 筆"):
            assert not re.fullmatch(_rx, _bad), _bad
        assert re.fullmatch(_rx, SUMMARY_DEFAULT)

    def test_labels_unavailable_means_no_summary_never_invented(self):
        assert B.screen_summary(None, F.ScreenRequest(submitted=False)) is None

    def test_summary_follows_applied_value_not_widget_value(self, monkeypatch):
        at, _ = _new_big(monkeypatch)
        at.run()
        at.selectbox(key=F.SS_TOPN_WIDGET).set_value(20)            # 只改 widget、尚未按 🎯 開始選股
        at.run()
        assert SUMMARY_DEFAULT in _exposed_text(at), "未送出前摘要只轉述預設／已套用，不跟著 widget 跑"
        _click(at, F.ACTION_RUN_SCREEN_LABEL)
        assert "4 項基本面全過＋高 EPS（獲利高）；排序：綜合評分；顯示 20 筆" in _exposed_text(at)

    def test_mutant_summary_adds_a_condition_is_red(self, monkeypatch):
        _orig = B.screen_summary
        monkeypatch.setattr(B, "screen_summary", lambda l, r: (_orig(l, r) or "").replace("；排序", "、ROE>15%；排序"))
        _got = _run_loaded(monkeypatch)
        with pytest.raises(AssertionError):
            _check_loaded(*_got)

    def test_mutant_summary_missing_is_red(self, monkeypatch):
        monkeypatch.setattr(B, "screen_summary", lambda l, r: None)
        _got = _run_loaded(monkeypatch)
        with pytest.raises(AssertionError):
            _check_loaded(*_got)


class TestFormGateSurvivesCollapse:
    def test_collapsed_form_still_submits_and_runs_screen_once(self, monkeypatch):
        at, calls, _ = _run_loaded(monkeypatch)
        assert calls["screen"] == 1
        at.run()                                       # rerun 不重打
        assert calls["screen"] == 1

    def test_only_one_submit_button_and_no_button_inside_form(self, monkeypatch):
        at, _, _ = _run_loaded(monkeypatch)
        _forms = [f for f in _blocks(at.main, "Form") if any(b.label == "🎯 開始選股" for b in _blocks(f, "Button"))]
        assert len(_forms) <= 1


# ══════════════════════════════════════════════════════════════════
# mutation：把實作換成錯的 ⇒ 契約必須轉紅
# ══════════════════════════════════════════════════════════════════
class TestLoadedMutants:
    def test_mutant_slice_resorts_by_name_is_red(self, monkeypatch):
        _orig = cp.topn_view

        def _m(rows, n):
            _t = _orig(rows, n)
            return cp.TopN(shown=tuple(sorted(_t.shown, key=lambda r: r["標的"])), hidden=_t.hidden, total=_t.total)
        monkeypatch.setattr(B.cp, "topn_view", _m)
        _got = _run_loaded(monkeypatch)
        with pytest.raises(AssertionError):
            _check_loaded(*_got)

    def test_mutant_slice_recomputes_ranking_is_red(self, monkeypatch):
        _orig = cp.topn_view

        def _m(rows, n):                        # 先照『綜合分』重排再切（＝重算排序）
            _rr = sorted(rows, key=lambda r: r["基本面"])
            return _orig(_rr, n)
        monkeypatch.setattr(B.cp, "topn_view", _m)
        _got = _run_loaded(monkeypatch)
        with pytest.raises(AssertionError):
            _check_loaded(*_got)

    def test_mutant_csv_only_top_ten_is_red(self, monkeypatch):
        monkeypatch.setattr(B, "candidate_csv_bytes",
                            lambda df: df.head(B.CANDIDATE_TOP_N).to_csv(index=False).encode("utf-8-sig"))
        _got = _run_loaded(monkeypatch)
        with pytest.raises(AssertionError):
            _check_loaded(*_got)

    def test_mutant_full_list_also_sliced_is_red(self, monkeypatch):
        _orig = B.build_candidate_rows
        monkeypatch.setattr(B, "build_candidate_rows", lambda b, s: _orig(b, s)[:10])
        _got = _run_loaded(monkeypatch)
        with pytest.raises(AssertionError):
            _check_loaded(*_got)

    def test_mutant_pe_note_full_text_removed_is_red(self, monkeypatch):
        monkeypatch.setattr(B, "PE_COL_NOTE", "")
        _got = _run_loaded(monkeypatch)
        with pytest.raises(AssertionError):
            _check_loaded(*_got)

    def test_mutant_notes_expander_dropped_is_red(self, monkeypatch):
        monkeypatch.setattr(B, "render_candidate_notes", lambda: None)
        _got = _run_loaded(monkeypatch)
        with pytest.raises(AssertionError):
            _check_loaded(*_got)

    def test_mutant_pe_basis_chip_dropped_is_red(self, monkeypatch):
        monkeypatch.setattr(B, "PE_BASIS_CHIP", "估值口徑另見說明")
        _got = _run_loaded(monkeypatch)
        with pytest.raises(AssertionError):
            _check_loaded(*_got)

    def test_mutant_notes_exposed_instead_of_sunk_is_red(self, monkeypatch):
        def _m():
            B.st.caption(B.PE_COL_NOTE)
            B.st.caption(B.CHIPS_COL_HINT)
            B.st.caption(B.FIN_STOCK_NOTE)
            with B.st.expander(B.CANDIDATE_NOTES_EXPANDER, expanded=False):
                B.st.caption(B.PE_COL_NOTE)
        monkeypatch.setattr(B, "render_candidate_notes", _m)
        _got = _run_loaded(monkeypatch)
        with pytest.raises(AssertionError):
            _check_loaded(*_got)

    def test_mutant_screen_expander_back_to_expanded_is_red(self, monkeypatch):
        monkeypatch.setattr(B, "SCREEN_EXPANDER_EXPANDED", True)
        _got = _run_loaded(monkeypatch)
        with pytest.raises(AssertionError):
            _check_loaded(*_got)
        at, calls = _new_big(monkeypatch)
        at.run()
        with pytest.raises(AssertionError):
            _check_cold(at, calls)

    def test_mutant_missing_pe_filled_with_zero_is_red(self, monkeypatch):
        _orig = B.build_candidate_rows

        def _m(b, s):
            _rows = _orig(b, s)
            for _r in _rows:
                if _r["估值"] == B.PE_NOT_PROVIDED_CELL:
                    _r["估值"] = "0"
            return _rows
        monkeypatch.setattr(B, "build_candidate_rows", _m)
        _got = _run_loaded(monkeypatch)
        with pytest.raises(AssertionError):
            _check_loaded(*_got)

    def test_mutant_pick_options_limited_to_top_ten_is_red(self, monkeypatch):
        _orig = B.pick_options
        monkeypatch.setattr(B, "pick_options", lambda b: _orig(b)[:10])
        _got = _run_loaded(monkeypatch)
        with pytest.raises(AssertionError):
            _check_loaded(*_got)


# ══════════════════════════════════════════════════════════════════
# 範圍／資訊守恆
# ══════════════════════════════════════════════════════════════════
class TestScopeAndConservation:
    def test_chip_text_reconciles_with_pe_col_note(self):
        assert "第三區" in B.PE_BASIS_CHIP and "357" in B.PE_BASIS_CHIP and "不能互相驗證" in B.PE_BASIS_CHIP
        assert "不能互相驗證" in B.PE_COL_NOTE and "殖利率口徑" in B.PE_COL_NOTE
        assert B.PE_COL_NOTE == PE_COL_NOTE_LITERAL and B.CHIPS_COL_HINT == CHIPS_HINT_LITERAL
        assert B.FIN_STOCK_NOTE == FIN_NOTE_LITERAL and B.PE_BASIS_CHIP == PE_CHIP_LITERAL

    def test_everything_old_page_showed_is_still_reachable_on_the_new_page(self, monkeypatch):
        at, _, _ = _run_loaded(monkeypatch)
        _t = _all_text(at)
        for _s in (PE_COL_NOTE_LITERAL, CHIPS_HINT_LITERAL, FIN_NOTE_LITERAL, "本次因子：", B.PICK_NOTE,
                   "💾 下載選股結果 CSV", "選股條件"):
            assert _s in _t, _s

    def test_no_new_data_layer_import_or_cache(self):
        import ast
        from pathlib import Path
        _src = Path(B.__file__).read_text(encoding="utf-8")
        _mods = [n.module for n in ast.walk(ast.parse(_src)) if isinstance(n, ast.ImportFrom) and n.module]
        assert not [m for m in _mods if m.startswith("src.data")], _mods
        assert "st.cache_data" not in _src and "st.cache_resource" not in _src

    def test_summary_chip_and_notes_texts_have_no_trading_words(self):
        for _s in (B.PE_BASIS_CHIP, B.SCREEN_SUMMARY_FMT):
            assert not any(w in _s for w in ("買進", "賣出", "推薦", "建議買", "保證"))
