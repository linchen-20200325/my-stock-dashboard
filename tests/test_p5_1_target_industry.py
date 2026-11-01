"""tests/test_p5_1_target_industry.py — Phase 5 PR1（🎯 標的頁第一區「產業機會」Primary）守衛。

客戶 DEC-121：Q1=A（產業 Top 5 橫條，依既有欄位 `x_yi`＝近 5 日法人累計淨流入由大到小；缺值最後、⬜、絕不補 0）、
Q3=A（排序依據句維持說明句、Primary 圖下方恰一個「▸ 為什麼／來源／限制／去哪補」）。
線框 `docs/vnext/PHASE5_TARGET_PAGE_WIREFRAME_2026-10-31.md` §10 C1-3／C1-4／C2-1／C2-3／C3-1／C3-2／N2。

寫法：**契約檢查函式**（`_check_*`）＋**mutation 風格守衛**——把實作換成「錯的版本」（換排序鍵、缺值補 0／排前、全量被切、
說明句被改、冷啟動取數、舊外露字串不在『查看全部』），契約檢查必須**轉紅**（`pytest.raises(AssertionError)`），
證明這些守衛真的咬得到東西，而不是永遠綠的裝飾。
"""
from __future__ import annotations

import dataclasses
import html as _html
import math
import re

import pandas as pd
import pytest

from shared.sector_flow_thresholds import SECTOR_FLOW_TWSE_ONLY_NOTE
from src.ui.views import _target_blocks as B
from src.ui.views import page_find as F
from src.ui_v2 import compact as cp
from tests import uit_fakes as U
from tests.test_uit_target_page import _click, _matrix_df, _new, _walk

#: 客戶原句（逐字；故意寫成字面常數而不是引用 `B.ZONE1_SORT_NOTE`，這樣常數被改就會紅）。
SORT_NOTE_LITERAL = "排序依據：法人資金動能，非產業趨勢。"

#: 9 個板塊：Top 5 應為 電機 > 半導體 > 金融 > 鋼鐵 > 塑膠；紡織標 unavailable 但 x_yi 帶了 99（⛔ 不得因此排最前）。
SECTORS9 = (
    {"sector": "半導體業", "x_yi": 120.5, "quadrant": "漲潮", "n_days": 20},
    {"sector": "航運業", "x_yi": -40.0, "quadrant": "退潮", "n_days": 20},
    {"sector": "生技醫療", "x_yi": None, "quadrant": "未取得", "unavailable": True, "n_days": 12},
    {"sector": "塑膠工業", "x_yi": 1.0, "quadrant": "資料不足", "insufficient": True, "n_days": 3},
    {"sector": "金融保險", "x_yi": 55.2, "quadrant": "輪動", "n_days": 20},
    {"sector": "鋼鐵工業", "x_yi": 8.8, "quadrant": "觀望", "n_days": 20},
    {"sector": "電機機械", "x_yi": 300.0, "quadrant": "漲潮", "n_days": 20},
    {"sector": "食品工業", "x_yi": -3.3, "quadrant": "退潮", "n_days": 20},
    {"sector": "紡織纖維", "x_yi": 99.0, "quadrant": "未取得", "unavailable": True, "n_days": 12},
)
EXPECT_TOP5 = ["電機機械", "半導體業", "金融保險", "鋼鐵工業", "塑膠工業"]


def _flow9(**kw):
    _base = U.make_flow(**kw)
    return dataclasses.replace(_base, sectors=SECTORS9, unavailable=("生技醫療", "紡織纖維"),
                               quadrant_counts=(("漲潮", 2), ("退潮", 2)))


# ══════════════════════════════════════════════════════════════════
# 純函式：排序鍵契約
# ══════════════════════════════════════════════════════════════════
def _check_rank_contract(rank) -> None:
    """DEC-121 Q1=A 的排序契約；任何違反都 AssertionError。"""
    _rows = rank(SECTORS9)
    _names = [r.sector for r in _rows]
    assert len(_rows) == len(SECTORS9), "不得增刪列（純顯示排序）"
    assert _names[:5] == EXPECT_TOP5, _names
    _valued = [r for r in _rows if r.x_yi is not None]
    assert [r.x_yi for r in _valued] == sorted((r.x_yi for r in _valued), reverse=True), "有值列必須由大到小"
    _tail = _rows[len(_valued):]
    assert {r.sector for r in _tail} == {"生技醫療", "紡織纖維"}, "缺值列（含 unavailable 但帶數字者）必須全在最後"
    assert all(r.x_yi is None for r in _tail), "缺值列不得被補成數字（尤其 0）"
    assert 0.0 not in [r.x_yi for r in _rows], "任何列都不得出現補出來的 0"
    assert next(r for r in _rows if r.sector == "航運業").x_yi == -40.0, "負值原樣保留，不得被截成 0"


class TestRankContract:
    def test_real_implementation_satisfies_the_contract(self):
        _check_rank_contract(B.rank_industries)

    # ── mutation：換掉排序鍵／補 0／排前／截斷／反向 ⇒ 契約必須轉紅 ──
    def test_mutant_name_order_is_red(self):
        def _m(sectors):
            return tuple(sorted(B.rank_industries(sectors), key=lambda r: r.sector))
        with pytest.raises(AssertionError):
            _check_rank_contract(_m)

    def test_mutant_quadrant_then_name_old_matrix_order_is_red(self):
        def _m(sectors):
            _by = {r.sector: r for r in B.rank_industries(sectors)}
            return tuple(_by[m.sector] for m in B.build_industry_matrix(sectors))
        with pytest.raises(AssertionError):
            _check_rank_contract(_m)

    def test_mutant_ascending_is_red(self):
        def _m(sectors):
            _r = list(B.rank_industries(sectors))
            _v = sorted((r for r in _r if r.x_yi is not None), key=lambda r: r.x_yi)
            return tuple(_v + [r for r in _r if r.x_yi is None])
        with pytest.raises(AssertionError):
            _check_rank_contract(_m)

    def test_mutant_missing_filled_with_zero_is_red(self):
        def _m(sectors):
            return tuple(dataclasses.replace(r, x_yi=0.0) if r.x_yi is None else r for r in B.rank_industries(sectors))
        with pytest.raises(AssertionError):
            _check_rank_contract(_m)

    def test_mutant_missing_first_is_red(self):
        def _m(sectors):
            _r = B.rank_industries(sectors)
            return tuple([r for r in _r if r.x_yi is None] + [r for r in _r if r.x_yi is not None])
        with pytest.raises(AssertionError):
            _check_rank_contract(_m)

    def test_mutant_unavailable_flag_ignored_is_red(self):
        def _m(sectors):                      # 只看 x_yi，無視 unavailable 旗標 ⇒ 紡織（99）會被排進前段
            _rows = [B.RankRow(sector=s["sector"], quadrant=s.get("quadrant", ""), x_yi=s.get("x_yi")) for s in sectors]
            _v = sorted((r for r in _rows if r.x_yi is not None), key=lambda r: -r.x_yi)
            return tuple(_v + [r for r in _rows if r.x_yi is None])
        with pytest.raises(AssertionError):
            _check_rank_contract(_m)

    def test_mutant_truncated_to_five_is_red(self):
        def _m(sectors):
            return B.rank_industries(sectors)[:5]
        with pytest.raises(AssertionError):
            _check_rank_contract(_m)

    @pytest.mark.parametrize("bad", [None, float("nan"), float("inf"), float("-inf"), "abc", True, [], {}])
    def test_non_finite_or_non_numeric_x_is_missing_never_zero(self, bad):
        _rows = B.rank_industries([{"sector": "甲", "x_yi": bad, "quadrant": "漲潮"},
                                   {"sector": "乙", "x_yi": -5.0, "quadrant": "退潮"}])
        assert [r.sector for r in _rows] == ["乙", "甲"] and _rows[1].x_yi is None

    def test_numeric_strings_are_accepted_like_floats_but_zero_is_a_real_value(self):
        _rows = B.rank_industries([{"sector": "甲", "x_yi": 0, "quadrant": "觀望"},
                                   {"sector": "乙", "x_yi": "3.5", "quadrant": "漲潮"},
                                   {"sector": "丙", "x_yi": None, "quadrant": "未取得"}])
        assert [(r.sector, r.x_yi) for r in _rows] == [("乙", 3.5), ("甲", 0.0), ("丙", None)]

    def test_input_is_not_mutated_and_empty_is_empty(self):
        _src = [dict(s) for s in SECTORS9]
        B.rank_industries(_src)
        assert _src == [dict(s) for s in SECTORS9]
        assert B.rank_industries(()) == () and B.rank_industries(None) == ()

    def test_ties_break_by_name_deterministically(self):
        _rows = B.rank_industries([{"sector": "丙", "x_yi": 1.0}, {"sector": "甲", "x_yi": 1.0}, {"sector": "乙", "x_yi": 1.0}])
        assert [r.sector for r in _rows] == sorted(["甲", "乙", "丙"])

    def test_old_matrix_order_is_untouched_by_the_display_sort(self):
        assert [r.sector for r in B.build_industry_matrix(U.SECTORS)] == ["半導體業", "航運業", "塑膠工業", "生技醫療"]

    def test_top_n_constants_unchanged_and_slice_is_only_a_view(self):
        assert B.ZONE1_TOP_N == 5
        _rows = B.rank_industries(SECTORS9)
        _top = cp.topn_view(_rows, B.ZONE1_TOP_N)
        assert all(_top.shown[i] is _rows[i] for i in range(5)) and _top.total == 9 and _top.hidden == 4

    def test_request_params_not_touched(self):
        assert F.TOP_N_OPTIONS == (20, 50, 100) and F.DEFAULT_TOP_N == 50


class TestChartFrameAndSpec:
    def test_frame_labels_carry_name_quadrant_and_number_as_text(self):
        _top = cp.topn_view(B.rank_industries(SECTORS9), 5).shown
        _f = B.rank_chart_frame(_top)
        assert list(_f["row"]) == ["1. 電機機械｜漲潮｜300.0 億", "2. 半導體業｜漲潮｜120.5 億", "3. 金融保險｜輪動｜55.2 億",
                                   "4. 鋼鐵工業｜觀望｜8.8 億", "5. 塑膠工業｜資料不足｜1.0 億"]
        assert [float(v) for v in _f["x_yi"]] == [300.0, 120.5, 55.2, 8.8, 1.0]

    def test_missing_rows_have_null_x_and_a_hollow_square_label_not_zero(self):
        _f = B.rank_chart_frame(B.rank_industries(SECTORS9)[-2:])
        assert _f["x_yi"].isna().all(), "缺值列的 x 必須是空值，⛔ 不是 0"
        assert all("⬜ 資料不足" in r and "0" not in r.split("｜")[-1] for r in _f["row"])

    def test_spec_keeps_data_order_lists_every_row_and_has_visible_axis(self):
        _labels = ["1. 甲｜漲潮｜1.0 億", "2. 乙｜未取得｜⬜ 資料不足"]
        _s = B.rank_chart_spec(_labels)
        assert _s["encoding"]["y"]["sort"] is None and _s["encoding"]["y"]["scale"]["domain"] == _labels
        assert _s["encoding"]["x"]["field"] == "x_yi" and _s["encoding"]["x"].get("axis", {}).get("labels", True) is not False
        assert _s["encoding"]["y"]["axis"]["labelOverlap"] is False, "列標不得被自動隱藏（手機實測會吃掉第 2、4 列）"
        _blob = repr(_s)
        for _bad in ("normalize", "stack", "joinaggregate", "window"):
            assert _bad not in _blob
        assert _s["height"] <= cp.SLOT_HEIGHT_MAX_PX and B.ZONE1_CHART_HEIGHT_PX <= 140

    def test_row_label_never_prints_a_number_for_missing(self):
        assert B.rank_row_label(3, B.RankRow("甲", "未取得", None)) == "3. 甲｜未取得｜⬜ 資料不足"
        assert B.rank_row_label(1, B.RankRow("甲", "", 5.0)) == "1. 甲｜—｜5.0 億"


# ══════════════════════════════════════════════════════════════════
# 頁面層：契約檢查（AppTest）
# ══════════════════════════════════════════════════════════════════
def _exposed(node, _in_expander=False):
    """外露層文字：不進任何 Expander（收合內容是『下沉』，不算外露）。"""
    for _c in getattr(node, "children", {}).values():
        if type(_c).__name__ == "Expander":
            continue
        if getattr(_c, "children", None):
            yield from _exposed(_c)
        elif type(_c).__name__ in ("Caption", "Markdown", "Text", "Header", "Subheader"):
            _v = getattr(_c, "value", None)
            if isinstance(_v, str):
                yield _v


def _expander_blocks(node):
    for _c in getattr(node, "children", {}).values():
        if type(_c).__name__ == "Expander":
            yield _c
        if getattr(_c, "children", None):
            yield from _expander_blocks(_c)


def _expander_text(exp) -> str:
    return "\n".join(t for _, t in _walk(exp))


def _fold_expanders(at):
    return [e for e in _expander_blocks(at.main) if str(e.label) == B.FOLD_LABEL]


def _all_expanders(at, prefix):
    return [e for e in _expander_blocks(at.main) if str(e.label).startswith(prefix)]


def _loaded(monkeypatch, flow=None):
    at, calls = _new(monkeypatch, flow=flow if flow is not None else _flow9())
    frames: list[pd.DataFrame] = []
    _orig = B.render_industry_chart

    def _rec(frame):
        frames.append(frame.copy())
        return _orig(frame)
    monkeypatch.setattr(B, "render_industry_chart", _rec)
    at.run()
    _click(at, F.ACTION_LOAD_MAP_LABEL)
    assert not at.exception, at.exception
    return at, calls, frames


def _check_loaded_zone1(at, calls, frames) -> None:
    """已載入態的第一區契約（C1-3／C1-4／C2-1／C2-3／C3-1／C3-2）。任何違反 ⇒ AssertionError。"""
    # Q1=A：圖的資料＝恰 5 列、依 x_yi 由大到小
    assert frames, "Primary 橫條沒有被畫"
    _f = frames[-1]
    assert len(_f) == 5, len(_f)
    assert [_r.split("｜")[0].split(". ", 1)[1] for _r in _f["row"]] == EXPECT_TOP5
    assert [float(v) for v in _f["x_yi"]] == [300.0, 120.5, 55.2, 8.8, 1.0]
    # Q3=A：說明句逐字、外露；非產業趨勢字面恆在
    _ex = list(_exposed(at.main))
    assert SORT_NOTE_LITERAL in _ex and "非產業趨勢" in SORT_NOTE_LITERAL
    # Q3=A：Primary 圖下方恰一個四段摺疊，且四段齊全
    _folds = _fold_expanders(at)
    assert len(_folds) == 1, [str(e.label) for e in _expander_blocks(at.main)]
    _ft = _expander_text(_folds[0])
    for _sec in ("**為什麼**", "**來源**", "**限制**", "**去哪補**"):
        assert _sec in _ft, _sec
    assert B.ZONE1_NO_TREND_NOTE in _ft, "趨勢未定義說明必須在『為什麼』"
    # 區塊級 Missing：外露層只一句、不逐列重複
    assert sum(t.count("尚未建置") for t in _ex) == 1, [t for t in _ex if "尚未建置" in t]
    assert B.ZONE1_MISSING_DIMS in _ex
    # 資訊守恆：「▸ 查看全部（N 個產業）」內有原 6 欄表逐列＋未取得名單＋TWSE-only 註
    _alls = _all_expanders(at, "▸ 查看全部（")
    assert len(_alls) == 1 and str(_alls[0].label) == B.ZONE1_ALL_LABEL_FMT.format(n=9)
    _at = _expander_text(_alls[0])
    _html_tbl = [t for _, t in _walk(_alls[0]) if 'class="ptg-mx-t"' in t]
    assert len(_html_tbl) == 1
    _names = [_html.unescape(n) for n in re.findall(r'data-label="產業">(.*?)</td>', _html_tbl[0])]
    assert sorted(_names) == sorted(s["sector"] for s in SECTORS9), "全量表不得被 Top 5 切片"
    for _c in B.MATRIX_COLS:
        assert f'data-label="{_c}"' in _html_tbl[0]
    assert "⬜ 未取得：生技醫療、紡織纖維" in _at
    # 沒有任何舊外露矩陣在外露層
    assert not any('class="ptg-mx-t"' in t for t in _ex), "6 欄表不得外露"
    # 取數閘：載入只打一次
    assert calls["flow"] == 1 and calls["heatmap"] == 1


def _check_small_flow(at, calls, frames) -> None:
    """夾具 4 列（3 有值＋1 缺值）：缺值列必須排最後、x 為空值、列標是 ⬜（缺值落在 Top-N 內才看得到補 0／排前的錯）。"""
    _f = frames[-1]
    assert len(_f) == 4
    assert [float(v) for v in _f["x_yi"].iloc[:3]] == [120.5, 1.0, -40.0]
    assert math.isnan(float(_f["x_yi"].iloc[3])), "缺值列不得被補成數字（尤其 0）"
    assert _f["row"].iloc[3].startswith("4. 生技醫療") and _f["row"].iloc[3].endswith("⬜ 資料不足")


class TestLoadedPrimary:
    def test_loaded_state_satisfies_the_whole_contract(self, monkeypatch):
        at, calls, frames = _loaded(monkeypatch)
        _check_loaded_zone1(at, calls, frames)

    def test_exactly_five_rows_exposed_even_with_nine_industries_and_all_nine_in_full_list(self, monkeypatch):
        at, _, frames = _loaded(monkeypatch)
        assert len(frames[-1]) == 5
        assert len(_matrix_df(at)) == 9

    def test_fewer_than_five_valued_missing_goes_last_with_hollow_square(self, monkeypatch):
        at, _, frames = _loaded(monkeypatch, flow=U.make_flow())          # 夾具 4 列：3 有值＋1 缺值
        _f = frames[-1]
        assert len(_f) == 4 and math.isnan(float(_f["x_yi"].iloc[-1]))
        assert _f["row"].iloc[-1].endswith("⬜ 資料不足") and _f["row"].iloc[0].startswith("1. 半導體業｜漲潮｜120.5 億")
        assert [float(v) for v in _f["x_yi"].iloc[:3]] == [120.5, 1.0, -40.0]

    def test_header_chips_stale_wins_over_coverage_and_are_not_color_only(self, monkeypatch):
        at, _, _ = _loaded(monkeypatch, flow=_flow9(stale=True))
        _hdr = [t for t in _exposed(at.main) if "cp-chart-header" in t]
        assert len(_hdr) == 1
        assert "⚠ 可能已過期" in _hdr[0] and "近 5 日" in _hdr[0] and "資料 10/28" in _hdr[0]
        assert "項有資料" not in _hdr[0], "狀態類 chip 同列互斥：過期優先，覆蓋數改在摺疊『限制』"
        _ft = _expander_text(_fold_expanders(at)[0])
        assert "有資料的產業：7／9" in _ft and "資料過期（載入當下判定）" in _ft

    def test_header_shows_coverage_chip_when_not_stale(self, monkeypatch):
        at, _, _ = _loaded(monkeypatch)
        _hdr = [t for t in _exposed(at.main) if "cp-chart-header" in t][0]
        assert "7／9 項有資料" in _hdr and "抓取" in _hdr

    def test_freshness_full_sentence_sank_into_fold_limit_not_dropped(self, monkeypatch):
        at, _, _ = _loaded(monkeypatch)
        assert not any("此結果載入於" in t for t in _exposed(at.main) if "載入板塊地圖" in t)
        _ft = _expander_text(_fold_expanders(at)[0])
        assert "此結果載入於" in _ft and "再按「🗺️ 載入板塊地圖」重新載入" in _ft

    def test_fold_four_sections_each_non_empty_and_six_basis_fields_all_present(self, monkeypatch):
        at, _, _ = _loaded(monkeypatch)
        _ft = _expander_text(_fold_expanders(at)[0])
        for _label, _ in B.BASIS_FIELDS:
            assert f"**{_label}**：" in _ft, _label

    def test_chart_fold_blank_section_raises(self):
        _b = B.basis_industry(None)
        _ok = B.chart_fold(_b, where=["x"])
        assert len(_ok.sections()) == 4
        with pytest.raises(ValueError):
            B.chart_fold(_b, where=[]).sections()
        with pytest.raises(ValueError):
            B.chart_fold(dataclasses.replace(_b, missing="  "))

    def test_heatmap_and_bubble_still_collapsed_expanders_in_place(self, monkeypatch):
        at, _, _ = _loaded(monkeypatch)
        _labels = [str(e.label) for e in _expander_blocks(at.main)]
        _i = {k: next(i for i, l in enumerate(_labels) if l.startswith(k)) for k in
              (B.FOLD_LABEL, "▸ 查看全部（", B.HEATMAP_EXPANDER, B.BUBBLE_EXPANDER)}
        assert _i[B.FOLD_LABEL] < _i["▸ 查看全部（"] < _i[B.HEATMAP_EXPANDER] < _i[B.BUBBLE_EXPANDER]

    def test_not_ok_flow_keeps_status_card_and_fold_no_chart(self, monkeypatch):
        at, calls, frames = _loaded(monkeypatch, flow=U.make_flow(ok=False))
        assert not frames and len(_fold_expanders(at)) == 1
        assert not _all_expanders(at, "▸ 查看全部（")
        assert "板塊資金快取尚未產生" in "\n".join(t for _, t in _walk(at.main))

    def test_failed_flow_is_red_not_grey(self, monkeypatch):
        at, _, frames = _loaded(monkeypatch, flow=U.make_flow(error="boom token=abc"))
        assert not frames and len(_fold_expanders(at)) == 1
        assert "token=abc" not in "\n".join(t for _, t in _walk(at.main)), "秘密必須被洗掉"

    def test_empty_sectors_is_a_missing_slot_not_an_empty_chart(self, monkeypatch):
        _fl = dataclasses.replace(U.make_flow(), sectors=(), unavailable=(), highlight=(), quadrant_counts=())
        at, _, frames = _loaded(monkeypatch, flow=_fl)
        assert not frames
        assert any('data-state="empty"' in t for t in _exposed(at.main))


# ══════════════════════════════════════════════════════════════════
# 冷啟動
# ══════════════════════════════════════════════════════════════════
def _check_cold_zone1(at, calls, frames) -> None:
    assert calls["flow"] == 0 and calls["heatmap"] == 0, dict(calls)            # 冷啟動零取數
    assert not frames
    _ex = list(_exposed(at.main))
    assert SORT_NOTE_LITERAL in _ex
    _slot = [t for t in _ex if "cp-slot-primary" in t and 'data-state="idle"' in t]
    assert len(_slot) == 1, "冷啟動 Primary 槽必須是灰色（idle）placeholder，同高"
    assert f"--cp-slot-h:{B.ZONE1_CHART_HEIGHT_PX}px" in _slot[0] and "cp-s-grey" in _slot[0] and "尚未載入" in _slot[0]
    assert "cp-s-red" not in _slot[0] and 'role="alert"' not in _slot[0], "尚未點擊不得畫紅"
    assert len(_fold_expanders(at)) == 1
    assert not _all_expanders(at, "▸ 查看全部（")


class TestColdStart:
    def test_cold_page_contract(self, monkeypatch):
        at, calls = _new(monkeypatch, flow=_flow9())
        frames: list = []
        monkeypatch.setattr(B, "render_industry_chart", lambda f: frames.append(f))
        at.run()
        assert not at.exception, at.exception
        _check_cold_zone1(at, calls, frames)

    def test_cold_idle_sentence_is_still_on_the_page(self, monkeypatch):
        at, _ = _new(monkeypatch)
        at.run()
        assert B.ZONE1_IDLE in "\n".join(_html.unescape(t) for t in _exposed(at.main))

    def test_mutant_cold_start_fetches_is_red(self, monkeypatch):
        at, calls = _new(monkeypatch, flow=_flow9())
        monkeypatch.setattr(B, "own_map_requested", lambda session: True)       # 取消 gate
        frames: list = []
        monkeypatch.setattr(B, "render_industry_chart", lambda f: frames.append(f))
        at.run()
        with pytest.raises(AssertionError):
            _check_cold_zone1(at, calls, frames)


# ══════════════════════════════════════════════════════════════════
# 已載入態的 mutation 守衛（把實作換成錯的 ⇒ 契約檢查必須紅）
# ══════════════════════════════════════════════════════════════════
class TestLoadedMutants:
    def test_mutant_sort_key_swapped_to_name_is_red(self, monkeypatch):
        _orig = B.rank_industries
        monkeypatch.setattr(B, "rank_industries", lambda s: tuple(sorted(_orig(s), key=lambda r: r.sector)))
        at, calls, frames = _loaded(monkeypatch)
        with pytest.raises(AssertionError):
            _check_loaded_zone1(at, calls, frames)

    def test_mutant_missing_filled_with_zero_and_ranked_is_red(self, monkeypatch):
        _orig = B.rank_industries

        def _m(s):
            _r = [dataclasses.replace(r, x_yi=0.0) if r.x_yi is None else r for r in _orig(s)]
            return tuple(sorted(_r, key=lambda r: (-r.x_yi, r.sector)))
        monkeypatch.setattr(B, "rank_industries", _m)
        at, calls, frames = _loaded(monkeypatch, flow=U.make_flow())
        with pytest.raises(AssertionError):
            _check_small_flow(at, calls, frames)

    def test_mutant_missing_ranked_first_is_red(self, monkeypatch):
        _orig = B.rank_industries

        def _m(s):
            _r = _orig(s)
            return tuple([r for r in _r if r.x_yi is None] + [r for r in _r if r.x_yi is not None])
        monkeypatch.setattr(B, "rank_industries", _m)
        at, calls, frames = _loaded(monkeypatch, flow=U.make_flow())
        with pytest.raises(AssertionError):
            _check_small_flow(at, calls, frames)

    def test_real_implementation_passes_small_flow_check(self, monkeypatch):
        at, calls, frames = _loaded(monkeypatch, flow=U.make_flow())
        _check_small_flow(at, calls, frames)

    def test_mutant_full_list_sliced_to_top_five_is_red(self, monkeypatch):
        _orig = B.build_industry_matrix
        monkeypatch.setattr(B, "build_industry_matrix", lambda s: _orig(s)[:5])
        at, calls, frames = _loaded(monkeypatch)
        with pytest.raises(AssertionError):
            _check_loaded_zone1(at, calls, frames)

    def test_mutant_sort_note_changed_is_red(self, monkeypatch):
        monkeypatch.setattr(B, "ZONE1_SORT_NOTE", "排序依據：近 5 日資金淨流入。")
        at, calls, frames = _loaded(monkeypatch)
        with pytest.raises(AssertionError):
            _check_loaded_zone1(at, calls, frames)

    def test_mutant_sort_note_turned_into_chip_is_red(self, monkeypatch):
        monkeypatch.setattr(B, "ZONE1_SORT_NOTE", "")
        at, calls, frames = _loaded(monkeypatch)
        with pytest.raises(AssertionError):
            _check_loaded_zone1(at, calls, frames)

    def test_mutant_old_exposed_strings_not_in_full_list_is_red(self, monkeypatch):
        monkeypatch.setattr(B, "render_all_industries", lambda flow, matrix: None)
        at, calls, frames = _loaded(monkeypatch)
        with pytest.raises(AssertionError):
            _check_loaded_zone1(at, calls, frames)

    def test_mutant_twse_only_and_unavailable_notes_dropped_is_red(self, monkeypatch):
        def _m(flow, matrix):
            with B.st.expander(B.ZONE1_ALL_LABEL_FMT.format(n=len(matrix)), expanded=False):
                B.st.markdown(B.matrix_html(matrix), unsafe_allow_html=True)
        monkeypatch.setattr(B, "render_all_industries", _m)
        at, calls, frames = _loaded(monkeypatch)
        with pytest.raises(AssertionError):
            _check_loaded_zone1(at, calls, frames)

    def test_mutant_row_missing_reasons_repeated_in_exposed_layer_is_red(self, monkeypatch):
        _orig_fold = B.render_chart_fold

        def _m(fold):
            B.st.caption(B.NOT_BUILT + " " + B.NOT_BUILT)         # 外露層重複 Missing
            _orig_fold(fold)
        monkeypatch.setattr(B, "render_chart_fold", _m)
        at, calls, frames = _loaded(monkeypatch)
        with pytest.raises(AssertionError):
            _check_loaded_zone1(at, calls, frames)

    def test_mutant_two_folds_is_red(self, monkeypatch):
        _orig_fold = B.render_chart_fold

        def _m(fold):
            _orig_fold(fold)
            _orig_fold(fold)
        monkeypatch.setattr(B, "render_chart_fold", _m)
        at, calls, frames = _loaded(monkeypatch)
        with pytest.raises(AssertionError):
            _check_loaded_zone1(at, calls, frames)

    def test_cold_never_reaches_map_bundle(self, monkeypatch):
        at, calls = _new(monkeypatch, flow=_flow9())
        monkeypatch.setattr(B, "map_bundle", lambda session: (_ for _ in ()).throw(AssertionError("冷啟動取數")))
        at.run()
        assert not at.exception       # gate 擋住 ⇒ 根本沒進 map_bundle
        assert calls["flow"] == 0


class TestScopeNoNewData:
    def test_module_has_no_data_layer_import_and_no_cache(self):
        import ast
        from pathlib import Path
        _tree = ast.parse(Path(B.__file__).read_text(encoding="utf-8"))
        _mods = [n.module for n in ast.walk(_tree) if isinstance(n, ast.ImportFrom) and n.module]
        assert not [m for m in _mods if m.startswith("src.data")], _mods
        _src = Path(B.__file__).read_text(encoding="utf-8")
        assert "st.cache_data" not in _src and "st.cache_resource" not in _src

    def test_sort_field_is_the_existing_l2_field(self):
        assert B.ZONE1_RANK_FIELD == "x_yi"

    def test_twse_only_note_sinks_into_fold_limit_when_tpex_incomplete(self):
        _fold = B.industry_fold(U.make_flow(tpex_complete=False), fresh_line=None, n_total=4)
        assert SECTOR_FLOW_TWSE_ONLY_NOTE in _fold.limit
