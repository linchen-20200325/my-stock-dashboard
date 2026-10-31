"""tests/test_p4_2_market_charts.py — Phase 4 P4-2：📊 市場頁圖區（客戶 DEC-117 Q4=P-B／Q3=A／Q8a 已核准線框）。

對應線框 `docs/vnext/PHASE4_MARKET_PAGE_WIREFRAME_2026-10-30.md` §10 的 P4-2 條目（每條測試名帶條目號）：
  C3-1 四張圖各恰一個「▸ 為什麼／來源／限制／去哪補」（四段固定順序、不留白；圖 C 兩句各在指定段逐字；「去哪補」指向的
       L2 展開區真的存在）；C4-1 圖 A＝Primary，正式原生圖＋MA 參考線＋y 軸＋圖例，恰 1；C4-2 國際 5 系列＝small multiples
       一組、格數 5、缺系列既有 placeholder、不做切換列；C4-3 小倍數不顯示數字、不用 `st.html` 掛 svg；C4-4 詳細數值仍在 L2；
       C4-5 台股／國際趨勢位置顯示「⬜ 尚未定義」、兩條護欄各自獨立 chip；C4-6 Primary 冷啟動同高、Secondary 缺資料縮一行；
       C8-a 圖 C 外露只剩標題＋「研究框架，未啟用」＋`CHART_C_EMPTY`；C8-0 外露→摺疊的字串在新頁全部可取得；
       C6-5 圖 D 的「未評估不等於安全」留在外露層（比渲染後文字）；C1-7 Primary 緊接 AI／資料狀態行（P4-1 守衛仍綠）。
判讀一律用 AppTest **渲染後**的元素樹；文字比渲染後字串（⛔ 比原始碼）。
"""
from __future__ import annotations

import ast
import json
import math
import pathlib
import re

import pandas as pd
import pytest

from src.services import market_twii_view_service as S
from src.ui.views import _market_blocks as B
from src.ui.views import page_market as PM
from src.ui_v2 import compact as cp
from tests.test_market_blocks import _all_up, _five
from tests.test_p4_1_market_first_screen import _events, _inside, _is_chart_header, _report, _top
from tests.test_uim_market_page import _LOADED, _run, _view

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_MB_SRC = (_ROOT / "src" / "ui" / "views" / "_market_blocks.py").read_text(encoding="utf-8")
_PM_SRC = (_ROOT / "src" / "ui" / "views" / "page_market.py").read_text(encoding="utf-8")
_MB_TREE = ast.parse(_MB_SRC)
_PM_TREE = ast.parse(_PM_SRC)

_KEYS = {"A": B.P4M_PRIMARY_KEY, "B": f"{B.P4M_SECONDARY_KEY_PREFIX}intl",
         "D": f"{B.P4M_SECONDARY_KEY_PREFIX}d", "C": f"{B.P4M_SECONDARY_KEY_PREFIX}c"}
_ZONE_ORDER = ["A", "B", "D", "C"]       # 線框 §4.1：Primary → 國際小倍數 → 圖 D → 圖 C
_IDX = pd.to_datetime(["2026-10-21", "2026-10-22", "2026-10-23"])


@pytest.fixture(autouse=True)
def _fixed_twii_view(monkeypatch):
    """圖 A 的指數線來自本地快取（環境相依）⇒ 全檔固定一個確定的 3 點視圖；個別測試自行覆寫。"""
    monkeypatch.setattr(S, "get_twii_trend_view", lambda n: _view())


def _fn(tree, name):
    return next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name)


def _full_intl_session():
    """5 個系列都有資料（IXIC／SOX 也有），資料日全同 ⇒ 組級 chip 寫一次。"""
    def _df(vals):
        return pd.DataFrame({"close": vals}, index=_IDX)
    _s = dict(_LOADED)
    _cl = dict(_LOADED["cl_data"])
    _cl["intl"] = {"道瓊工業 DJI": _df([40000.0, 40100.0, 39900.0]), "納斯達克 IXIC": _df([17000.0, 17100.0, 17250.0]),
                   "費城半導體 SOX": _df([5000.0, 4950.0, 5100.0]), "10Y公債殖利率": _df([4.1, 4.2, 4.3]),
                   "美元指數 DXY": _df([99.0, 99.5, 100.0])}
    _s["cl_data"] = _cl
    return _s


def _zone(evs, which):
    """某張圖所在具名容器內（含摺疊）的全部事件。"""
    return [e for e in evs if _KEYS[which] in e[3]]


def _fold_sections(evs, which):
    """`{段名: [(kind, text)]}`：該圖摺疊內，以 `**段名**` 標題切段。"""
    _out: dict[str, list[tuple[str, str]]] = {}
    _cur = None
    for _k, _t, _e, _keys in _zone(evs, which):
        if _e != B.FOLD_LABEL or _k == "Expander":
            continue
        if _k == "Markdown" and _t in {f"**{n}**" for n in B.FOLD_SECTIONS}:
            _cur = _t.strip("*")
            _out[_cur] = []
        elif _cur is not None:
            _out[_cur].append((_k, _t))
    return _out


def _all_text(evs):
    return [_t for _k, _t, _e, _ in evs if _k in ("Markdown", "Caption", "Error", "Warning", "Success", "Info", "Text")]


# ══════════════════════════════════════════════════════════════════
# C3-1：四張圖各恰一個四段摺疊
# ══════════════════════════════════════════════════════════════════
class TestC31:
    @pytest.mark.parametrize("session", (None, _LOADED), ids=("cold", "loaded"))
    def test_c3_1_each_chart_has_exactly_one_four_section_fold(self, tmp_path, session):
        _at = _run(tmp_path, session)
        assert not _at.exception, _at.exception
        _evs = list(_events(_at.main))
        for _w in _ZONE_ORDER:
            _exps = [e[1] for e in _zone(_evs, _w) if e[0] == "Expander"]
            assert _exps == [B.FOLD_LABEL], (_w, _exps)                   # 恰一個，且沒有舊的「🔍 查看依據」
            _sec = _fold_sections(_evs, _w)
            assert list(_sec) == list(B.FOLD_SECTIONS), (_w, list(_sec))   # 四段、固定順序
            assert all(_sec[_n] for _n in _sec), (_w, _sec)                # 每段都有內容（不適用寫「—」並說明）

    def test_c3_1_fold_label_and_sections_are_the_customer_words(self):
        assert B.FOLD_LABEL == "▸ 為什麼／來源／限制／去哪補"
        assert B.FOLD_SECTIONS == ("為什麼", "來源", "限制", "去哪補")
        assert B.FOLD_LABEL.removeprefix("▸ ").split("／") == list(B.FOLD_SECTIONS)

    def test_c3_1_fold_is_collapsed_by_default(self, tmp_path):
        _at = _run(tmp_path, _LOADED)
        from tests.test_p4_1_market_first_screen import _expanded_flags
        _fold = [f for f in _expanded_flags(_at.main) if f[0] == B.FOLD_LABEL]
        assert len(_fold) == 4 and not any(_open for _, _open in _fold)

    def test_c3_1_empty_section_raises_instead_of_hiding(self):
        _ok = (("md", "x"),)
        with pytest.raises(ValueError, match="不得留白"):
            B.ChartFold(why=_ok, source=_ok, limit=(), where=_ok).sections()
        with pytest.raises(ValueError, match="不得留白"):
            B.ChartFold(why=_ok, source=_ok, limit=_ok, where=(("md", "  "),)).sections()
        with pytest.raises(ValueError, match="tone"):
            B.ChartFold(why=_ok, source=_ok, limit=_ok, where=(("html", "x"),)).sections()

    def test_c3_1_six_field_basis_is_split_losslessly_into_four_sections(self):
        """線框 §3.5：六欄 Basis 的每一欄逐字出現在對應段（規則／AI→為什麼；資料／日期→來源；missing／confidence→限制）。"""
        _b = B.Basis(data_used="D", as_of="A", rule="R", missing="M", confidence="C", ai="I")
        _f = B.chart_fold(_b, where=(("caption", "W"),))
        _s = dict(_f.sections())
        assert "R" in _s["為什麼"][0][1] and "I" in _s["為什麼"][0][1]
        assert "D" in _s["來源"][0][1] and "A" in _s["來源"][0][1]
        assert "M" in _s["限制"][0][1] and "C" in _s["限制"][0][1]
        assert [t for _, t in _s["去哪補"]] == ["W"]

    def test_c3_1_where_points_at_the_real_l2_expander_of_each_chart(self, tmp_path):
        """「去哪補」指向的展開區標題必須是頁上真的存在的 L2 展開區標題（⛔ 指向不存在的地方）。"""
        _at = _run(tmp_path, _LOADED)
        _evs = list(_events(_at.main))
        _labels = {e[1] for e in _evs if e[0] == "Expander"}
        _expect = {"A": f"台股盤勢（{PM.RAW_DATA_SUFFIX}）", "B": f"國際市場（{PM.RAW_DATA_SUFFIX}）",
                   "D": B.LAMP_DETAIL_EXPANDER_LABEL, "C": PM.X9_TITLE}
        for _w, _label in _expect.items():
            assert _label in _labels, (_w, _label)
            _where = " ".join(t for _, t in _fold_sections(_evs, _w)["去哪補"])
            assert f"「{_label}」" in _where, (_w, _where)

    def test_c3_1_no_chart_uses_the_tile_basis_label(self, tmp_path):
        """tile／⚡ 維持「🔍 查看依據」、圖用四段（Q3=A：兩者是不同資訊物件）—— 不可互相借用。"""
        _at = _run(tmp_path, _LOADED)
        _evs = list(_events(_at.main))
        for _w in _ZONE_ORDER:
            assert B.BASIS_EXPANDER_LABEL not in [e[1] for e in _zone(_evs, _w) if e[0] == "Expander"]
        _tiles = [e for e in _evs if e[0] == "Expander" and e[1] == B.BASIS_EXPANDER_LABEL]
        assert len(_tiles) == 4 and not any(_k in e[3] for e in _tiles for _k in _KEYS.values())


# ══════════════════════════════════════════════════════════════════
# 區塊順序：Primary → 國際 → 圖 D → 圖 C；圖區內不得被插隊
# ══════════════════════════════════════════════════════════════════
class TestZone:
    @pytest.mark.parametrize("session", (None, _LOADED), ids=("cold", "loaded"))
    def test_chart_zone_order_and_nothing_between(self, tmp_path, session):
        _at = _run(tmp_path, session)
        _evs = list(_events(_at.main))
        _first = {_w: next(i for i, e in enumerate(_evs) if _KEYS[_w] in e[3]) for _w in _ZONE_ORDER}
        _last = {_w: max(i for i, e in enumerate(_evs) if _KEYS[_w] in e[3]) for _w in _ZONE_ORDER}
        assert [_first[w] for w in _ZONE_ORDER] == sorted(_first.values())
        for _a, _b in zip(_ZONE_ORDER, _ZONE_ORDER[1:]):
            assert _first[_b] == _last[_a] + 1, (_a, _b)      # 兩張圖之間沒有任何元素（⛔ 插入 L2／L3 長內容）
        # 圖區之後第一個元素是「以下為可展開區塊」說明；圖 C 容器是圖區最後一塊
        assert _all_text([_evs[_last["C"] + 1]]) == ["以下為可展開區塊（預設收合）。"]

    def test_chart_zone_contains_no_widgets_and_no_l2_expanders(self, tmp_path):
        """C4-2：不做切換列 —— 圖區任一容器內不得有 widget（按鈕／radio／selectbox／勾選…），摺疊只有四段那一個。"""
        for _s in (None, _LOADED):
            _evs = list(_events(_run(tmp_path, _s).main))
            for _w in _ZONE_ORDER:
                _bad = [e[:2] for e in _zone(_evs, _w) if e[0] not in (
                    "Markdown", "Caption", "Error", "Warning", "Success", "Info", "Text", "Code", "Expander",
                    "Dataframe", "Table", "UnknownElement", "Empty")]
                assert not _bad, (_w, _bad)

    def test_c4_2_no_switcher_widget_is_called_by_the_market_page(self):
        _banned = {"segmented_control", "pills", "tabs", "select_slider", "selectbox", "option_menu", "toggle"}
        for _src in (_MB_SRC, _PM_SRC):
            for _n in ast.walk(ast.parse(_src)):
                if isinstance(_n, ast.Call) and isinstance(_n.func, ast.Attribute):
                    assert _n.func.attr not in _banned, ast.unparse(_n)[:80]


# ══════════════════════════════════════════════════════════════════
# C4-1：圖 A＝Primary，正式主圖（DEC-119：自訂 vega-lite spec，取代 st.line_chart）
# ══════════════════════════════════════════════════════════════════
#: 手機 390px 視窗下圖 A 的實測寬（`_measure_p4_5_legend`：326px；守衛用它估算圖例右緣，不得超過）。
MOBILE_CHART_WIDTH_PX = 326
_SERIES_FULL = [B.TWII_COLUMN, "MA5（最新值，參考）", "MA60（最新值，參考）", "MA120（最新值，參考）"]
_SERIES_FULL5 = [B.TWII_COLUMN] + [f"{_n}（最新值，參考）" for _n in ("MA5", "MA60", "MA120", "MA200")]


def _chart_spec_and_data(at):
    """AppTest 渲染後的圖 A：`(spec dict, 資料表 dict[col → list])`；恰一個 vega_lite_chart。"""
    import io

    import pyarrow as pa
    _ch = at.get("vega_lite_chart")
    assert len(_ch) == 1, len(_ch)
    _pr = _ch[0].proto
    _tbl = pa.ipc.open_stream(io.BytesIO(_pr.data.data)).read_all()
    return json.loads(_pr.spec), _tbl.to_pydict()


def _chart_spec_and_series(at):
    _spec, _data = _chart_spec_and_data(at)
    return _spec, sorted(set(_data["series"]))


def _legend_labels(spec):
    """圖例上實際顯示的文字：color scale domain 各項，套 `labelExpr` 的 replace(限定語, '')。"""
    _c = spec["encoding"]["color"]
    _expr = _c["legend"].get("labelExpr", "")
    _m = re.fullmatch(r"replace\(datum\.label, '(.*)', ''\)", _expr)
    return [_n.replace(_m.group(1), "", 1) if _m else _n for _n in _c["scale"]["domain"]]


def _est_text_px(text, font_px):
    """全形字＝1em、ASCII＝0.6em 的保守估算（只供圖例寬度守衛；實測見 p4_5 腳本）。"""
    return sum(font_px if ord(_ch) > 0x2E80 else 0.6 * font_px for _ch in text)


def _estimate_legend_width_px(spec):
    """圖例橫向總寬估算 ＝ 欄數 × 單欄寬（符號＋6px 間隙＋最寬標籤）＋欄距；title 另計，取兩者較大。"""
    _lg = spec["encoding"]["color"]["legend"]
    _font = _lg["labelFontSize"]
    _col = _lg["symbolSize"] ** 0.5 + 6 + max(_est_text_px(_t, _font) for _t in _legend_labels(spec))
    _cols = min(_lg["columns"], len(spec["encoding"]["color"]["scale"]["domain"]))
    _w = _cols * _col + (_cols - 1) * _lg["columnPadding"]
    return max(_w, _est_text_px(_lg["title"], _lg["titleFontSize"]))


class TestC41:
    def test_c4_1_primary_is_the_custom_vega_chart_with_ma_lines_legend_and_y_axis(self, tmp_path):
        _at = _run(tmp_path, _LOADED)
        _spec, _series = _chart_spec_and_series(_at)
        # 指數＋三條 MA 水平參考線（ma200 歷史不足 ⇒ 不畫、不補 0，缺項在摺疊「限制」列出）；系列名逐字（含限定語）留在資料
        assert _series == sorted(_SERIES_FULL)
        _enc = _spec["encoding"]
        assert _enc["y"]["type"] == "quantitative" and isinstance(_enc["y"].get("axis"), dict)   # y 軸沒被隱藏
        for _flag in ("labels", "ticks", "domain", "grid"):
            assert _enc["y"]["axis"].get(_flag, True) is not False or _flag == "grid", _flag
        assert _enc["y"]["axis"].get("grid") is True
        assert _enc["x"]["type"] == "temporal" and _enc["x"].get("axis") is not None
        assert _enc["color"]["legend"] is not None                                             # 圖例保留（且不是 None／False）
        assert _spec["mark"]["type"] == "line"

    def test_c4_1_legend_lists_every_series_and_keeps_the_qualifier_somewhere_readable(self, tmp_path):
        """DEC-119：5 項圖例都在 legend；縮短系列名時「最新值，參考」限定語移到圖例標題，完整系列名逐字留在資料／tooltip。"""
        _spec, _data = _chart_spec_and_data(_run(tmp_path, _LOADED))
        _c = _spec["encoding"]["color"]
        assert _c["scale"]["domain"] == _SERIES_FULL                       # 圖例項＝資料系列（固定順序：指數、MA5、MA60、MA120）
        assert _legend_labels(_spec) == [B.TWII_COLUMN, "MA5", "MA60", "MA120"]
        assert "最新值，參考" in _c["legend"]["title"] == B.TWII_LEGEND_TITLE
        assert all(_n in set(_data["series"]) for _n in _SERIES_FULL)       # 完整系列名逐字在資料
        _tips = {_t["field"] for _t in _spec["encoding"]["tooltip"]}
        assert {"date", "series", "value"} <= _tips                        # tooltip 帶完整系列名＋數值＋日期

    def test_c4_1_five_series_all_present_in_legend_when_ma200_is_available(self):
        _spec = B.twii_chart_spec(_SERIES_FULL5, height=220)
        assert _legend_labels(_spec) == [B.TWII_COLUMN, "MA5", "MA60", "MA120", "MA200"]
        assert len(set(_spec["encoding"]["color"]["scale"]["range"])) == 5

    def test_c4_1_legend_fits_inside_the_390_phone_chart_width(self, tmp_path):
        """右緣不超過手機圖寬（DEC-119 題 1：5 項全部可見、不遮圖）；欄數過多／標籤帶回限定語都會超出。"""
        for _names in (_SERIES_FULL, _SERIES_FULL5):
            _spec = B.twii_chart_spec(_names, height=220)
            assert _estimate_legend_width_px(_spec) <= MOBILE_CHART_WIDTH_PX, (_names, _estimate_legend_width_px(_spec))
            assert _spec["encoding"]["color"]["legend"]["orient"] == "bottom"
        _rendered, _ = _chart_spec_and_data(_run(tmp_path, _LOADED))
        assert _estimate_legend_width_px(_rendered) <= MOBILE_CHART_WIDTH_PX

    def test_c4_1_spec_is_a_full_chart_not_a_sparkline_and_does_no_transform(self, tmp_path):
        _spec, _ = _chart_spec_and_data(_run(tmp_path, _LOADED))
        assert "transform" not in _spec and "layer" not in _spec or all("transform" not in _l for _l in _spec["layer"])
        _blob = json.dumps(_spec, ensure_ascii=False)
        for _bad in ('"stack"', '"normalize"', '"window"', '"joinaggregate"', '"aggregate"', '"bin"', '"timeUnit"',
                     '"fold"', '"calculate"', '"impute"', '"loess"', '"regression"'):
            assert _bad not in _blob, _bad                                 # ⛔ 正規化／滾動／補值／聚合
        assert _spec["encoding"]["y"].get("scale", {}).get("type", "linear") == "linear"
        assert "width" not in _spec                                        # 沒有縮小寬度的 mini chart
        assert _spec["height"] == 220 and _spec["autosize"]["type"] == "fit"
        assert _spec["mark"].get("strokeWidth", 1) >= 1 and _spec["mark"]["type"] == "line"
        for _ax in ("x", "y"):
            _a = _spec["encoding"][_ax]["axis"]
            assert _a is not None and all(_a.get(_k, True) is not False for _k in ("labels", "ticks", "domain"))

    def test_c4_1_golden_chart_data_equals_the_view_close_and_the_ma_reference_values(self, tmp_path):
        """固定資料 → spec 的 data values 逐值相等：指數＝view.close；每條 MA＝同一個最新值（水平線）；ma200 缺 ⇒ 無列、不補 0。"""
        _spec, _d = _chart_spec_and_data(_run(tmp_path, _LOADED))
        _v = _view()
        _rows = list(zip(_d["date"], _d["series"], _d["value"]))
        _idx = [r for r in _rows if r[1] == B.TWII_COLUMN]
        assert [r[2] for r in _idx] == list(_v.close)
        assert [str(r[0])[:10] for r in _idx] == list(_v.xs)
        _refs, _ = B.ma_reference_values(_LOADED["mkt_info"])
        for _name, _val in _refs:
            _ma = [r for r in _rows if r[1] == f"{_name}（最新值，參考）"]
            assert len(_ma) == len(_v.close) and {r[2] for r in _ma} == {_val}, _name
        assert not [r for r in _rows if "MA200" in r[1]]
        assert len(_rows) == len(_v.close) * (1 + len(_refs)) and all(r[2] is not None for r in _rows)

    def test_c4_1_long_frame_keeps_gaps_as_nulls_no_fill_no_normalize(self):
        _df = pd.DataFrame({B.TWII_COLUMN: [22000.0, float("nan"), 22200.0], "MA5（最新值，參考）": [22100.0] * 3},
                           index=pd.to_datetime(["2026-10-21", "2026-10-22", "2026-10-23"]))
        _long = B.twii_chart_long(_df)
        assert list(_long.columns) == list(B.TWII_LONG_COLUMNS) and len(_long) == 6
        _ix = _long[_long.series == B.TWII_COLUMN].value.tolist()
        assert _ix[0] == 22000.0 and _ix[2] == 22200.0 and math.isnan(_ix[1])      # 缺口留缺口（⛔ ffill／fillna(0)）
        assert _long[_long.series == "MA5（最新值，參考）"].value.tolist() == [22100.0] * 3

    def test_c4_1_series_colors_are_a_fixed_mapping_per_series(self):
        _spec = B.twii_chart_spec(_SERIES_FULL5, height=220)
        _sc = _spec["encoding"]["color"]["scale"]
        assert dict(zip(_sc["domain"], _sc["range"])) == dict(zip(_SERIES_FULL5, (
            "#2563eb", "#f59e0b", "#10b981", "#a855f7", "#ef4444")))

    def test_c4_1_primary_height_is_the_contract_cap_and_the_cold_slot_uses_the_same_height(self):
        assert B.PRIMARY_CHART_HEIGHT_PX == cp.SLOT_HEIGHT_MAX_PX == 220
        _src = ast.unparse(_fn(_MB_TREE, "render_chart_a"))
        _uses = [n for n in ast.walk(_fn(_MB_TREE, "render_chart_a")) if isinstance(n, ast.Name) and n.id == "PRIMARY_CHART_HEIGHT_PX"]
        assert len(_uses) == 2                                                  # 圖與冷啟動槽同一個名字（C4-6）
        assert "render_twii_chart(twii_chart_frame(_view, _refs), height=PRIMARY_CHART_HEIGHT_PX)" in _src
        assert "st.container(height=PRIMARY_CHART_HEIGHT_PX, border=True)" in _src
        _r = ast.unparse(_fn(_MB_TREE, "render_twii_chart"))                     # 高度同時給 spec 與元件（兩處一致）
        assert "twii_chart_spec(list(frame.columns), height=height)" in _r and "height=height" in _r

    def test_c4_1_chart_call_does_not_hide_axes_or_legend(self):
        _call = next(n for n in ast.walk(_fn(_MB_TREE, "render_twii_chart"))
                     if isinstance(n, ast.Call) and ast.unparse(n.func) == "st.vega_lite_chart")
        assert {k.arg for k in _call.keywords} == {"width", "height"}          # ⛔ theme／selection／key 等花樣
        assert len(_call.args) == 2
        assert not any(ast.unparse(n.func) == "st.line_chart" for n in ast.walk(_MB_TREE) if isinstance(n, ast.Call))

    def test_c4_1_exactly_one_native_chart_on_the_page_and_it_is_in_the_primary_container(self, tmp_path):
        _at = _run(tmp_path, _full_intl_session())
        assert len(_at.get("vega_lite_chart")) == 1
        _evs = list(_events(_at.main))
        assert any(e[0] == "UnknownElement" for e in _zone(_evs, "A"))       # AppTest 把 vega_lite_chart 列為 UnknownElement
        assert not any(e[0] == "UnknownElement" for _w in "BDC" for e in _zone(_evs, _w))

    def test_c4_1_layout_css_never_selects_chart_internals(self):
        _css = B.P4M_LAYOUT_CSS.lower() + cp.compact_css().lower()
        for _w in ("vega", "role-axis", "stvegalitechart", "legend", "canvas"):
            assert _w not in _css, _w

    def test_c4_1_frame_has_index_plus_one_column_per_available_ma(self):
        _v = _view()
        _refs, _bad = B.ma_reference_values(_LOADED["mkt_info"])
        _df = B.twii_chart_frame(_v, _refs)
        assert list(_df.columns) == [B.TWII_COLUMN, "MA5（最新值，參考）", "MA60（最新值，參考）", "MA120（最新值，參考）"]
        assert _bad == [("MA200", "無資料（歷史不足）")]
        assert (_df["MA5（最新值，參考）"] == 22100.0).all()           # 水平線＝同一個值（本頁不自行算滾動均線）

    def test_c4_1_primary_cold_and_unreadable_keep_a_slot_not_a_missing_chart(self, tmp_path, monkeypatch):
        _cold = list(_events(_run(tmp_path).main))
        assert B.NOT_LOADED in _inside(_cold, None) or any(e[1] == B.NOT_LOADED for e in _zone(_cold, "A"))
        assert not any(e[0] == "UnknownElement" for e in _zone(_cold, "A"))
        monkeypatch.setattr(S, "get_twii_trend_view", lambda n: S.TwiiTrendView(ok=False, error="快取讀不到"))
        _evs = list(_events(_run(tmp_path, _LOADED).main))
        assert any(e[1].startswith("⬜ 台股指數歷史暫時讀不到") for e in _zone(_evs, "A"))

    def test_c4_1_chart_a_header_chips_are_two_guards_then_facts_and_readable_last(self):
        _chips = B.chart_a_chips(_view(is_stale=False), today_date=pd.Timestamp("2026-10-30").date())
        _kinds = [c.kind for c in _chips]
        assert _kinds[:2] == ["guard_text", "not_defined"]            # 護欄在左（兩條各自獨立）
        assert _kinds[-1] == "readable" and "asof" in _kinds and "window" in _kinds
        assert [c.kind for c in B.chart_a_chips(None)] == ["guard_text", "not_defined"]   # 冷啟動只放護欄
        assert "stale" in [c.kind for c in B.chart_a_chips(_view(is_stale=True, age_days=4))]
        # 新鮮度未判定 ⇒ 不給 ✅ 可讀
        assert "readable" not in [c.kind for c in B.chart_a_chips(_view(is_stale=None))]


# ══════════════════════════════════════════════════════════════════
# C4-2／C4-3：國際 small multiples
# ══════════════════════════════════════════════════════════════════
def _grid_html(at):
    return next(t for t in _top(list(_events(at.main))) if t.startswith('<div class="cp-sm '))


def _visible_text_of_grid(html: str) -> str:
    """去掉 svg 與系列名之後的可見文字（小倍數格內不得有數字）。"""
    _t = re.sub(r"<svg.*?</svg>", "", html, flags=re.S)
    _t = re.sub(r'<div class="cp-sm-name">.*?</div>', "", _t)
    return re.sub(r"<[^>]+>", "", _t)


class TestC42C43:
    def test_c4_2_five_cells_in_fixed_order_even_when_series_are_missing(self, tmp_path):
        _grid = _grid_html(_run(tmp_path, _LOADED))
        _names = re.findall(r'<div class="cp-sm-name">(.*?)</div>', _grid)
        assert _names == ["道瓊工業 DJI", "那指 IXIC", "費半 SOX", "10Y公債殖利率", "美元指數 DXY"]
        assert _grid.count('class="cp-sm-cell"') == 5
        assert _grid.count(f'class="cp-sm-missing">{B.SM_MISSING_ABSENT}</div>') == 2   # 缺系列 ⇒ 既有字樣，不留空格、不畫線
        assert _grid.count("<svg") == 3

    def test_c4_2_all_five_present_draws_five_sparklines(self, tmp_path):
        _grid = _grid_html(_run(tmp_path, _full_intl_session()))
        assert _grid.count("<svg") == 5 and "cp-sm-missing" not in _grid

    def test_c4_2_cell_count_is_the_five_intl_groups_series_and_other_series_are_not_cells(self):
        assert sum(len(_ns) for _, _ns in B.INTL_GROUPS) == 5
        _series = [B.IntlSeries(_g, _n, "ok", pd.Series([1.0, 2.0], index=["2026-10-22", "2026-10-23"]))
                   for _g, _ns in B.INTL_GROUPS for _n in _ns]
        _series.append(B.IntlSeries(B.INTL_OTHER_GROUP, "其他系列", "ok", pd.Series([1.0, 2.0], index=["2026-10-22", "2026-10-23"])))
        _, _cells = B.chart_b_parts(_series)
        assert len(_cells) == 5
        assert B.intl_core_series([]) and len(B.intl_core_series([])) == 5           # 空 ⇒ 5 格全 absent，⛔ 少格
        # 其他（未分組）系列不進格，但在摺疊「來源」逐列列出（只下沉）
        _src = dict(B.chart_b_fold(_series, source_note="n", where_label="x").sections())["來源"]
        assert any("其他系列" in t for _, t in _src)

    def test_c4_2_cold_collapses_to_one_line_and_no_grid(self, tmp_path):
        _evs = list(_events(_run(tmp_path).main))
        _z = [e for e in _zone(_evs, "B") if e[2] is None]
        assert [e[0] for e in _z if e[0] != "Expander"] == ["Markdown", "Caption"]
        assert _z[1][1] == B.NOT_LOADED and not any(e[1].startswith('<div class="cp-sm ') for e in _z)

    def test_c4_2_placeholder_wording_for_empty_and_too_short_series(self):
        _ix = pd.to_datetime(["2026-10-22", "2026-10-23"])
        _s = [B.IntlSeries("海外市場", "道瓊工業 DJI", "empty"),
              B.IntlSeries("海外市場", "納斯達克 IXIC", "ok", pd.Series([1.0], index=_ix[:1])),
              B.IntlSeries("海外市場", "費城半導體 SOX", "ok", pd.Series([1.0, 2.0], index=_ix))]
        _, _cells = B.chart_b_parts(_s)
        assert _cells[0].missing_verbatim == B.SM_MISSING_EMPTY
        assert _cells[1].missing_verbatim == B.INSUFFICIENT_TEXT               # 1 點畫不出線 ⇒ 誠實 placeholder
        assert _cells[2].svg is not None
        assert _cells[3].missing_verbatim == B.SM_MISSING_ABSENT and _cells[4].missing_verbatim == B.SM_MISSING_ABSENT

    def test_c4_2_non_finite_close_becomes_placeholder_not_a_fake_line(self, capsys):
        _ix = pd.to_datetime(["2026-10-22", "2026-10-23"])
        _s = [B.IntlSeries("海外市場", "道瓊工業 DJI", "ok", pd.Series([1.0, float("inf")], index=_ix))]
        _, _cells = B.chart_b_parts(_s)
        assert _cells[0].svg is None and _cells[0].missing_verbatim == B.INSUFFICIENT_TEXT
        assert "畫不出小圖" in capsys.readouterr().out                       # 講出來（log），不是靜默

    def test_c4_3_small_multiples_show_no_numbers(self, tmp_path):
        for _sess in (_LOADED, _full_intl_session()):
            _vis = _visible_text_of_grid(_grid_html(_run(tmp_path, _sess)))
            assert not any(ch.isdigit() for ch in _vis), _vis
            assert "%" not in _vis

    def test_c4_3_svg_title_and_aria_label_are_exactly_the_formal_series_name_and_no_svg_text(self, tmp_path):
        """QA MAJOR 1：只掃可見文字不夠 —— svg 的 `<title>`／`aria-label`（讀屏與 hover 會讀出）也不得夾帶數字或任何別的字：
        必須逐字等於該格**正式系列名**（非顯示名），且 svg 內沒有 `<text>`。"""
        _grid = _grid_html(_run(tmp_path, _full_intl_session()))
        _svgs = re.findall(r"<svg.*?</svg>", _grid, flags=re.S)
        assert len(_svgs) == 5
        _formal = [n for _, ns in B.INTL_GROUPS for n in ns]
        for _svg, _name in zip(_svgs, _formal):
            assert re.findall(r"<title>(.*?)</title>", _svg) == [_name]
            assert re.findall(r'aria-label="(.*?)"', _svg) == [_name]
            assert "<text" not in _svg

    def test_c4_3_golden_polyline_direction_and_group_window_chip(self, tmp_path):
        """QA MAJOR 2：固定 3 點遞增 ⇒ polyline y 座標單調**遞減**（SVG y 向下）；組級窗口 chip 文字＝`近 {n} 日`（n＝輸入窗口）。"""
        _ix = pd.to_datetime(["2026-10-21", "2026-10-22", "2026-10-23"])
        _series = [B.IntlSeries(_g, _n, "ok", pd.Series([1.0, 2.0, 3.0], index=_ix)) for _g, _ns in B.INTL_GROUPS for _n in _ns]
        _chips, _cells = B.chart_b_parts(_series, today_date=pd.Timestamp("2026-10-30").date())
        _win = [c for c in _chips if c.kind == "window"]
        assert len(_win) == 1 and _win[0].text.endswith("近 3 日"), [c.text for c in _chips]
        _html = cp.small_multiples_html(_cells, cols_desktop=3, cols_mobile=2)
        _pts = re.findall(r'<polyline[^>]*points="([^"]+)"', _html)
        assert len(_pts) == 5
        for _p in _pts:
            _ys = [float(pt.split(",")[1]) for pt in _p.split()]
            assert len(_ys) == 3 and _ys[0] > _ys[1] > _ys[2], _ys
        # 頁面層：窗口 chip 實際出現在 header、n 對輸入
        _sess = dict(_LOADED)
        _cl = dict(_LOADED["cl_data"])
        _cl["intl"] = {n: pd.DataFrame({"close": [1.0, 2.0, 3.0]}, index=_ix) for _, ns in B.INTL_GROUPS for n in ns}
        _sess["cl_data"] = _cl
        _evs = list(_events(_run(tmp_path, _sess).main))
        _head = next(e[1] for e in _zone(_evs, "B") if _is_chart_header(e[1], B.CHART_B_TITLE))
        assert 'data-kind="window">近 3 日</span>' in _head

    def test_c4_3_small_multiples_container_has_no_extra_text_besides_header_grid_and_fold(self, tmp_path):
        """QA MINOR 3：小倍數容器外露層只有 header、格子（單一 HTML 元素）；其餘文字只能在摺疊內。"""
        _evs = list(_events(_run(tmp_path, _full_intl_session()).main))
        _outer = [e for e in _zone(_evs, "B") if e[2] is None and e[0] != "Expander"]
        assert [e[0] for e in _outer] == ["Markdown", "Markdown"]
        assert _is_chart_header(_outer[0][1], B.CHART_B_TITLE) and _outer[1][1].startswith('<div class="cp-sm ')

    def test_c4_3_cell_with_a_value_text_is_rejected_by_the_component(self):
        _svg = cp.sparkline_svg([1.0, 2.0, 3.0], w=B.SM_SPARK_W, h=B.SM_SPARK_H, title="x",
                                missing_state="empty", missing_text="x")
        for _bad in ("⬜ 最新 22000", "⬜ 沒有 3 筆"):
            with pytest.raises(ValueError, match="數字"):
                cp.small_multiples_html([cp.SmCell("x", missing_verbatim=_bad)])
        assert cp.small_multiples_html([cp.SmCell("x", svg=_svg)])

    def test_c4_3_missing_verbatim_contract(self):
        for _bad in ("本輪沒有這個系列", "⬜ ", "⬜ 沒有 🔴 兩個符號", "⬜ a\nb", ""):
            with pytest.raises(ValueError):
                cp.small_multiples_html([cp.SmCell("x", missing_verbatim=_bad)])
        with pytest.raises(ValueError, match="互斥"):
            cp.small_multiples_html([cp.SmCell("x", missing_verbatim="⬜ a", missing_state="empty", missing_text="b")])

    def test_c4_3_svg_is_mounted_by_markdown_never_st_html(self):
        """F-4：`st.html` 會剝行內 svg。兩個市場頁檔案不得呼叫 `st.html`（svg 一律 `st.markdown(unsafe_allow_html=True)`）。"""
        for _src in (_MB_SRC, _PM_SRC):
            _calls = [ast.unparse(n.func) for n in ast.walk(ast.parse(_src)) if isinstance(n, ast.Call)]
            assert "st.html" not in _calls
        _call = next(n for n in ast.walk(_fn(_MB_TREE, "render_chart_b"))
                     if isinstance(n, ast.Call) and ast.unparse(n.func) == "st.markdown"
                     and "small_multiples_html" in ast.unparse(n))
        assert any(k.arg == "unsafe_allow_html" for k in _call.keywords)

    def test_c4_3_every_series_name_fits_the_8_char_cap_and_full_names_stay_in_the_fold_and_l2(self, tmp_path):
        for _g, _ns in B.INTL_GROUPS:
            for _n in _ns:
                assert len(B.intl_display_name(_n)) <= cp.SM_NAME_MAX_CHARS, _n
        # 顯示名只對映超過上限的兩個；其餘原名（⛔ 改正式名）
        assert set(B.INTL_DISPLAY_NAMES) == {"納斯達克 IXIC", "費城半導體 SOX"}
        assert all(len(_k) > cp.SM_NAME_MAX_CHARS for _k in B.INTL_DISPLAY_NAMES)
        assert all(len(_v) <= cp.SM_NAME_MAX_CHARS for _v in B.INTL_DISPLAY_NAMES.values())
        _evs = list(_events(_run(tmp_path, _full_intl_session()).main))
        _src = " ".join(t for _, t in _fold_sections(_evs, "B")["來源"])
        assert "納斯達克 IXIC" in _src and "費城半導體 SOX" in _src          # 正式全名在摺疊「來源」

    def test_asof_chip_value_returns_none_when_unparseable_and_formats_by_year(self):
        """QA MINOR 4：解析失敗 ⇒ None（⛔ 猜一個日期）；同年 `MM/DD`、跨年 `YYYY/MM/DD`。"""
        _t = pd.Timestamp("2026-10-30").date()
        for _bad in (None, "", "未提供", "2026/10/23", "10-23", "not a date", 20261023):
            assert B.asof_chip_value(_bad, today_date=_t) is None, _bad
        assert B.asof_chip_value("2026-10-23", today_date=_t) == "10/23"
        assert B.asof_chip_value("2025-12-31T00:00:00", today_date=_t) == "2025/12/31"

    def test_c4_5_group_chips_say_not_defined_once_and_dates_only_when_uniform(self):
        _ix = pd.to_datetime(["2026-10-22", "2026-10-23"])
        _mk = lambda n, d: B.IntlSeries("g", n, "ok", pd.Series([1.0, 2.0], index=pd.to_datetime(d)))   # noqa: E731
        _same = [_mk("道瓊工業 DJI", ["2026-10-22", "2026-10-23"]), _mk("美元指數 DXY", ["2026-10-22", "2026-10-23"])]
        _chips, _cells = B.chart_b_parts(_same, today_date=pd.Timestamp("2026-10-30").date())
        assert [c.kind for c in _chips] == ["not_defined", "asof", "window"]
        _diff = [_mk("道瓊工業 DJI", ["2026-10-22", "2026-10-23"]), _mk("美元指數 DXY", ["2026-10-21", "2026-10-22"])]
        _chips2, _ = B.chart_b_parts(_diff, today_date=pd.Timestamp("2026-10-30").date())
        assert "asof" not in [c.kind for c in _chips2]                   # 各系列資料日不同 ⇒ 不寫一個假的共同日期
        assert B.chart_b_parts(None)[0][0].kind == "not_defined" and B.chart_b_parts(None)[1] == []


# ══════════════════════════════════════════════════════════════════
# C4-4：詳細數值仍在 L2
# ══════════════════════════════════════════════════════════════════
class TestC44:
    def test_c4_4_raw_data_expanders_keep_their_titles_and_contents_with_the_numbers(self, tmp_path):
        _at = _run(tmp_path, _full_intl_session())
        _evs = list(_events(_at.main))
        _intl = f"國際市場（{PM.RAW_DATA_SUFFIX}）"
        _tw = f"台股盤勢（{PM.RAW_DATA_SUFFIX}）"
        assert _intl in {e[1] for e in _evs if e[0] == "Expander"} and _tw in {e[1] for e in _evs if e[0] == "Expander"}
        # L2 原始資料表（逐系列最後收盤）仍在：小倍數拿掉的數字在這裡
        _all = {e[1] for e in _evs if e[2] == _intl or e[2] == _tw}
        assert any(e[2] == _intl for e in _evs)
        assert _all, "L2 原始資料展開區是空的"


# ══════════════════════════════════════════════════════════════════
# C4-5：趨勢結論位置「⬜ 尚未定義」；兩條護欄各自獨立
# ══════════════════════════════════════════════════════════════════
class TestC45:
    @pytest.mark.parametrize("session", (None, _LOADED), ids=("cold", "loaded"))
    def test_c4_5_not_defined_is_shown_outside_the_fold_for_tw_and_intl_and_guards_are_separate_chips(self, tmp_path, session):
        _evs = list(_events(_run(tmp_path, session).main))
        _a = next(e[1] for e in _zone(_evs, "A") if e[0] == "Markdown" and _is_chart_header(e[1], B.CHART_A_TITLE))
        _b = next(e[1] for e in _zone(_evs, "B") if e[0] == "Markdown" and _is_chart_header(e[1], B.CHART_B_TITLE))
        for _h in (_a, _b):
            assert f'data-kind="not_defined">{B.NOT_DEFINED}</span>' in _h
        # 均線聲明與「⬜ 尚未定義」是兩顆**各自獨立**的 chip（DEC-115 D10(a)），⛔ 合併成一顆
        assert f'<span class="cp-chip cp-guard" data-kind="guard_text">{B.CHART_A_MA_DISCLAIMER}</span>' in _a
        assert _a.count('class="cp-chip cp-guard"') == 2
        assert B.CHART_A_MA_DISCLAIMER not in _b
        # 結論句原句下沉到摺疊「為什麼」（逐字）
        assert B.CHART_A_CONCLUSION in " ".join(t for _, t in _fold_sections(_evs, "A")["為什麼"])
        assert B.CHART_B_CONCLUSION in " ".join(t for _, t in _fold_sections(_evs, "B")["為什麼"])
        assert B.CHART_A_CONCLUSION == "台股趨勢結論：⬜ 尚未定義" and B.CHART_B_CONCLUSION == "國際趨勢結論：⬜ 尚未定義"

    def test_c4_5_ma_disclaimer_text_is_verbatim_and_the_customer_sentences_are_verbatim(self, tmp_path):
        assert B.CHART_A_MA_DISCLAIMER == "均線為參考，不等於正式台股趨勢判斷。"
        assert B.CHART_A_SAY == "看台股目前是在長期上升、整理還是轉弱；趨勢與短期波動分開判斷。"
        assert B.CHART_B_SAY == "看海外市場、利率與美元是否正在幫助或壓抑台股風險偏好。"
        _evs = list(_events(_run(tmp_path, _LOADED).main))
        _a = next(e[1] for e in _zone(_evs, "A") if _is_chart_header(e[1], B.CHART_A_TITLE))
        assert f'<div class="cp-ch-say">{B.CHART_A_SAY}</div>' in _a

    def test_c4_5_no_new_formula_in_the_chart_zone(self):
        """零新公式：圖區程式沒有任何滾動／統計運算（趨勢定義不得被 compact 顯示改掉）。"""
        _banned = {"rolling", "ewm", "pct_change", "diff", "mean", "std", "cumsum", "shift", "ta", "ma"}
        _zone_fns = ["render_chart_a", "chart_a_chips", "chart_a_fold", "chart_b_parts", "chart_b_fold", "render_chart_b",
                     "render_chart_c", "chart_c_fold", "render_chart_d", "chart_d_fold", "chart_d_table_rows",
                     "twii_chart_frame"]
        for _name in _zone_fns:
            for _n in ast.walk(_fn(_MB_TREE, _name)):
                if isinstance(_n, ast.Attribute):
                    assert _n.attr not in _banned, (_name, _n.attr)


# ══════════════════════════════════════════════════════════════════
# C4-6：D6=B 冷啟動
# ══════════════════════════════════════════════════════════════════
class TestC46:
    def test_c4_6_cold_secondary_charts_are_one_liners_with_state_symbol_and_reason(self, tmp_path):
        _evs = list(_events(_run(tmp_path).main))
        for _w in "BD":
            _outer = [e for e in _zone(_evs, _w) if e[2] is None and e[0] != "Expander"]
            _txt = [e[1] for e in _outer if e[0] == "Caption"]
            assert B.NOT_LOADED in _txt, (_w, _txt)                   # ⬜ 尚未載入，請按更新（灰；不是 0、不是空白）
        assert not any(e[0] == "Error" for e in _evs)


# ══════════════════════════════════════════════════════════════════
# C8-a：圖 C
# ══════════════════════════════════════════════════════════════════
class TestC8a:
    @pytest.mark.parametrize("session", (None, _LOADED), ids=("cold", "loaded"))
    def test_c8_a_chart_c_outside_is_title_tag_and_one_line_only(self, tmp_path, session):
        _evs = list(_events(_run(tmp_path, session).main))
        _outside = [e for e in _zone(_evs, "C") if e[2] is None and e[0] != "Expander"]
        assert [e[0] for e in _outside] == ["Markdown", "Caption"]
        assert _is_chart_header(_outside[0][1], B.CHART_C_TITLE)
        assert f'data-kind="guard_text">{B.CHART_C_TAG}</span>' in _outside[0][1]
        # 📌 P4-4（A8，有意識的修改，⛔ 不是降強度）：外露一行由整句 `CHART_C_EMPTY`（50 字）縮成它的第一句 `CHART_C_EMPTY_FACE`
        #   （≤32 字、逐字取自原句前半）；整句逐字下沉「為什麼」（見下一條測試）。外露層**不得**再出現整句後半。
        assert _outside[1][1] == B.CHART_C_EMPTY_FACE and B.CHART_C_EMPTY.startswith(B.CHART_C_EMPTY_FACE)
        assert B.CHART_C_EMPTY not in " ".join(_all_text(_outside))
        assert B.CHART_C_SAY not in " ".join(_all_text(_outside))      # 子字串層級（header HTML 裡也不得夾帶客戶原句）
        assert B.CHART_C_BASIS not in " ".join(_all_text(_outside))

    def test_c8_a_say_is_verbatim_in_why_and_basis_verbatim_in_source(self, tmp_path):
        assert B.CHART_C_SAY == "用企業獲利 EPS 搭配不同合理本益比情境，觀察目前指數位在便宜、合理或偏貴區域。"
        assert B.CHART_C_BASIS == "查看依據：此區塊未啟用，沒有使用任何資料。"
        _evs = list(_events(_run(tmp_path, _LOADED).main))
        _sec = _fold_sections(_evs, "C")
        # 📌 P4-4（A8）：「為什麼」＝客戶原句 `CHART_C_SAY`（Q8a 逐字）＋ 外露縮短後下沉的整句 `CHART_C_EMPTY`（逐字，資訊不丟）。
        assert [t for _, t in _sec["為什麼"]] == [B.CHART_C_SAY, B.CHART_C_EMPTY]
        assert [t for _, t in _sec["來源"]] == [B.CHART_C_BASIS]
        assert [t for _, t in _sec["限制"]] == [B.CHART_C_LIMIT] and B.CHART_C_LIMIT.startswith("—（")
        assert "「" + PM.X9_TITLE + "」" in _sec["去哪補"][0][1]

    def test_c8_a_whole_block_has_no_number_chart_or_widget(self):
        for _t in B.chart_c_texts():
            assert not any(ch.isdigit() or ch == "%" for ch in _t), _t
        _calls = {ast.unparse(n.func) for _f in ("render_chart_c", "chart_c_fold") for n in ast.walk(_fn(_MB_TREE, _f))
                  if isinstance(n, ast.Call)}
        assert not {c for c in _calls if "chart" in c.lower() and c != "render_chart_header" and c != "render_chart_fold"
                    and c != "chart_fold" and c != "chart_c_fold"}, _calls


# ══════════════════════════════════════════════════════════════════
# C6-5：圖 D
# ══════════════════════════════════════════════════════════════════
class TestChartD:
    def test_c6_5_unevaluated_is_not_safe_stays_outside_the_fold_in_chart_d(self, tmp_path):
        _evs = list(_events(_run(tmp_path, _LOADED).main))
        _outer = [e[1] for e in _zone(_evs, "D") if e[2] is None and e[0] == "Markdown"]
        _line = [t for t in _outer if "項未評估" in t]
        assert len(_line) == 1
        _plain = _line[0].replace("**", "")          # 渲染後文字（客戶看到的字；⛔ 比原始碼，C6-3 明文）：粗體記號不算字
        assert re.fullmatch(r"\d+ 項未評估（共 \d+ 項燈；未評估不等於安全）", _plain), _plain
        assert "未評估不等於安全" not in " ".join(t for _, t in sum(_fold_sections(_evs, "D").values(), []))

    def test_chart_d_header_says_worsening_not_defined_once_and_table_is_two_columns(self, tmp_path):
        _evs = list(_events(_run(tmp_path, _LOADED).main))
        _head = next(e[1] for e in _zone(_evs, "D") if _is_chart_header(e[1], B.CHART_D_TITLE))
        assert f'data-kind="guard_text">{B.CHART_D_WORSENING}</span>' in _head
        _tbl = next(e[1] for e in _zone(_evs, "D") if e[1].startswith("| 風險桶"))
        _lines = _tbl.splitlines()
        assert _lines[0] == "| 風險桶（每桶一項） | 方向 |" and len(_lines) == 2 + 5
        assert B.CHART_D_WORSENING not in _tbl                      # 「是否惡化」寫一次在 header，不在每列重複
        assert B.DANGER_POINTER in [e[1] for e in _zone(_evs, "D") if e[0] == "Caption" and e[2] is None]
        assert B.CHART_D_ALL_LAMPS_POINTER in [t for _, t in _fold_sections(_evs, "D")["去哪補"]]

    def test_chart_d_table_rows_are_the_first_two_columns_of_risk_panel_rows(self):
        for _lv in ({}, {"long": "gray"}, {"long": "red", "chips": "yellow"}, {_b: "gray" for _b in
                                                                             __import__("shared.macro_buckets", fromlist=["x"]).BUCKET_ORDER}):
            _r = B.build_market_risks(_five(_lv), _all_up())
            _three = B.risk_panel_rows(_r)
            assert B.chart_d_table_rows(_r) == [(b, d) for b, d, _ in _three]
        # 第三欄若出現預期外的內容（不是「是否惡化：⬜ 尚未定義」、也不是與方向同字的「資料不足」）⇒ fail loud，⛔ 靜默併掉資訊
        _real = B.risk_panel_rows
        try:
            B.risk_panel_rows = lambda r: [("🌳 長期", "→ 持平", "是否惡化：惡化中")]
            with pytest.raises(ValueError, match="第三欄"):
                B.chart_d_table_rows(_r)
        finally:
            B.risk_panel_rows = _real

    def test_chart_d_cold_and_failed_paths_are_kept(self, tmp_path, monkeypatch):
        _evs = list(_events(_run(tmp_path).main))
        _d = [e for e in _zone(_evs, "D") if e[2] is None]
        assert any(e[0] == "Caption" and e[1] == B.NOT_LOADED for e in _d)
        assert not any(e[1].startswith("**") and "項未評估" in e[1] for e in _d)      # 冷啟動不宣稱 0 項未評估
        monkeypatch.setattr(B, "build_market_risks", lambda *a, **k: B.MarketRisks(
            rows=(), n_lamps=0, n_unevaluated=0, cold=False, failed=True, error="boom"))
        _evs2 = list(_events(_run(tmp_path, _LOADED).main))
        assert any(e[0] == "Error" and e[1].startswith("五桶風險摘要算不出來：") for e in _zone(_evs2, "D"))


# ══════════════════════════════════════════════════════════════════
# C8-0：資訊守恆（外露 → 摺疊的每個字串，在新頁全部文字中仍可取得）
# ══════════════════════════════════════════════════════════════════
#: P4-2 前圖區外露的客戶可見字串（FACT：P4-1 的 `_market_blocks` 圖 A～D 外露層，逐一列出）。
_OLD_EXPOSED = (
    B.CHART_A_CONCLUSION, B.CHART_A_MA_NOTE, B.TREND_DEFINITION_NOTE, B.CHART_B_CONCLUSION, B.CHART_B_NOTE,
    B.CHART_C_SAY, B.CHART_C_BASIS, B.CHART_D_ALL_LAMPS_POINTER, B.CHART_D_WORSENING, B.CHART_A_MA_DISCLAIMER,
    B.CHART_A_SAY, B.CHART_B_SAY, B.CHART_C_EMPTY, B.CHART_D_NOTE, B.DANGER_POINTER,
)


class TestC80:
    def test_c8_0_every_old_exposed_chart_string_is_still_somewhere_on_the_loaded_page(self, tmp_path):
        _at = _run(tmp_path, _full_intl_session())
        _blob = "\n".join(_all_text(list(_events(_at.main))))
        for _s in _OLD_EXPOSED:
            assert _s in _blob, _s

    def test_c8_0_old_group_headings_series_windows_and_source_note_are_in_chart_b_source(self, tmp_path):
        _evs = list(_events(_run(tmp_path, _full_intl_session()).main))
        _src = [t for _, t in _fold_sections(_evs, "B")["來源"]]
        for _g in ("**海外市場**", "**利率**", "**美元**"):
            assert _g in _src
        for _n in ("道瓊工業 DJI", "納斯達克 IXIC", "費城半導體 SOX", "10Y公債殖利率", "美元指數 DXY"):
            assert f"{_n}　·　近 3 日，資料至 2026-10-23" in _src
        assert PM.FRAME_SOURCE_NOTE["intl"] in _src

    def test_c8_0_chart_a_source_caption_ma_gaps_and_stale_warning_are_in_the_fold(self, tmp_path, monkeypatch):
        monkeypatch.setattr(S, "get_twii_trend_view", lambda n: _view(is_stale=True, stale_reason="落後 4 個交易日"))
        _evs = list(_events(_run(tmp_path, _LOADED).main))
        _sec = _fold_sections(_evs, "A")
        assert ("Caption", "近 3 日，資料至 2026-10-23　·　" + S.TWII_SOURCE_TEXT) in _sec["來源"]
        assert ("Caption", "⬜ 缺少的均線：MA200：無資料（歷史不足）") in _sec["限制"]
        assert ("Caption", B.CHART_A_MA_NOTE) in _sec["限制"] and ("Caption", B.TREND_DEFINITION_NOTE) in _sec["限制"]
        assert any(k == "Warning" and "已過期" in t and "落後 4 個交易日" in t for k, t in _sec["限制"])

    def test_c8_0_chart_a_unknown_freshness_and_not_loaded_lines_are_in_the_fold(self, tmp_path, monkeypatch):
        monkeypatch.setattr(S, "get_twii_trend_view", lambda n: _view(is_stale=None))
        _sec = _fold_sections(list(_events(_run(tmp_path, _LOADED).main)), "A")
        assert ("Caption", "⬜ 台股指數歷史快取的新鮮度未判定") in _sec["限制"]
        _cold = _fold_sections(list(_events(_run(tmp_path).main)), "A")
        assert ("Caption", f"⬜ 均線：{B.NOT_LOADED}") in _cold["限制"]
        assert ("Caption", B.NOT_LOADED) in _cold["去哪補"]

    def test_c8_0_secrets_in_errors_are_scrubbed_in_the_fold_too(self, tmp_path, monkeypatch):
        _secret = "AIza" + "A" * 35
        monkeypatch.setattr(S, "get_twii_trend_view", lambda n: _view(is_stale=True, stale_reason=f"key={_secret}"))
        _blob = "\n".join(_all_text(list(_events(_run(tmp_path, _LOADED).main))))
        assert _secret not in _blob


# ══════════════════════════════════════════════════════════════════
# 其他頁／分層：P4-2 不得外溢
# ══════════════════════════════════════════════════════════════════
class TestScope:
    def test_p4_2_imports_nothing_new_from_the_data_compute_or_other_pages(self):
        """「改動範圍」的純 Python 版（portability 守衛：測試不得呼叫外部 `git`）：兩個市場頁檔案的 `src.*`／`shared.*` import
        只能是 P4-1 已有的那一組（UI／ui_v2／services／既有 L0 常數）；⛔ 新增任何 data／其他頁／compute 的 import。
        （「0 diff：`app.py`／`page_today.py`／`shared`／`services`…」由 PR 的 `git diff --stat` 與 z60 指紋守衛承擔，見 PR_NOTES。）"""
        _allowed_prefixes = ("shared.", "src.services", "src.ui.views", "src.ui_v2", "src.compute.macro.lamp_direction",
                             "src.compute.macro.macro_helpers")
        for _src in (_MB_SRC, _PM_SRC):
            for _n in ast.walk(ast.parse(_src)):
                _mods = ([_n.module] if isinstance(_n, ast.ImportFrom) and _n.module else
                         [a.name for a in _n.names] if isinstance(_n, ast.Import) else [])
                for _m in _mods:
                    if _m.split(".")[0] in ("src", "shared", "app"):
                        assert _m == "shared" or _m == "src.services" or _m == "src.ui.views" or _m.startswith(_allowed_prefixes), _m
                        assert "page_today_" not in _m and not _m.startswith(("src.ui.tabs", "src.ui.etf", "src.ui.pages"))

    def test_compact_additions_are_additive_the_default_path_is_unchanged(self):
        _a = cp.small_multiples_html([cp.SmCell("x", missing_state="empty", missing_text="沒有資料")])
        assert 'class="cp-sm-missing"' in _a
        assert cp.SmCell("x", svg=None, missing_state="empty", missing_text="y").missing_verbatim is None

    def test_page_market_imports_no_data_layer(self):
        for _src in (_MB_SRC, _PM_SRC):
            for _n in ast.walk(ast.parse(_src)):
                if isinstance(_n, ast.ImportFrom) and _n.module:
                    assert not _n.module.startswith("src.data"), _n.module


def test_report_fixture_still_renders_the_chart_zone(tmp_path):
    """有更新報告（含真錯誤）時圖區仍完整、順序不變（D1 把報告放到結論下方，不影響圖區）。"""
    from shared import ia_nav
    from src.ui.views import page_today as P
    _evs = list(_events(_run(tmp_path, {**_LOADED, P.SS_REFRESH_REPORT: _report(failed=True)}).main))
    for _w in _ZONE_ORDER:
        assert [e[1] for e in _zone(_evs, _w) if e[0] == "Expander"] == [B.FOLD_LABEL]
    assert ia_nav.action_label(ia_nav.ACTION_UPDATE_TODAY)
