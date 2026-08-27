"""tests/test_macro_v2_dual_axis.py — L4 `macro_v2_cards` 雙軸走勢卡（卡 A）。

## 這張卡有一種錯法，錯了畫面**完全看不出來**

卡 A 左軸是 DXY（~105）、右軸是台幣（~32）。plotly 在省略 `yref` 時一律把
門檻線綁到**主軸**，所以右軸那條「黃線 32.0」會被畫在**左軸的 32** —— 圖底
某處。它是一條標籤正確、顏色正確、線型正確的虛線，只有位置是錯的，而位置
正是它唯一要傳達的資訊（§1：畫面說 A、內容是 B，兩邊都看起來正常）。

沒有任何肉眼檢查抓得到這件事，所以它只能靠這裡釘住：
  · `test_right_axis_thresholds_bind_to_y2` —— 右軸門檻的 `yref` 必須是 `y2`
  · `test_..._annotation_binds_to_the_same_axis_as_its_line` —— 標籤也要跟著搬
  · `test_degrade_to_single_axis_moves_thresholds_back_to_primary` —— 降級成
    單軸後 `y2` 消失，門檻**必須跟著搬回 `y`**，否則 plotly 會憑空生一條隱形
    副軸把門檻畫在上面（同一種錯，換一個入口）

## 原料一律取真 SSOT

`left` 用 `SPECS_BY_KEY["dxy"]`（high_bad，2 條門檻線）、`right` 用
`SPECS_BY_KEY["ndc_signal"]`（band，**4** 條門檻線，且門檻數字 32/38 正好落在
台幣的量級）—— 手捏 spec 只驗得到「我以為的契約」。

⚠️ 本檔不啟動 Streamlit runtime；`render_*` 用假 st 離線驗。
"""
from __future__ import annotations

import ast
import dataclasses
import inspect
import math
import pathlib

import plotly.graph_objects as go
import pytest

from shared.colors import COLORS_7, TRAFFIC_RED, TRAFFIC_YELLOW
from shared.macro_buckets import SPECS_BY_KEY
from src.ui.render import macro_v2_cards as C

_SRC = pathlib.Path(C.__file__)

_LEFT_SPEC = SPECS_BY_KEY["dxy"]          # high_bad：黃 105 / 紅 110
_RIGHT_SPEC = SPECS_BY_KEY["ndc_signal"]  # band：黃 32 / 紅 38 / 黃下 23 / 紅下 16


def _row(key: str, label: str, value: float | None, *, band: str = "green",
         unit: str = "", decimals: int = 1) -> C.Row:
    return C.Row(key=key, label=label, bucket="mid", unit=unit, value=value,
                 band=band, state="live", reason=None, hit_source="test",
                 thr_text="—", source="TEST", note="", decimals=decimals)


def _xs(n: int) -> list[str]:
    return [f"2026-08-{i + 1:02d}" for i in range(n)]


def _left(n: int = 5, **kw) -> C.AxisSeries:
    return C.AxisSeries(row=_row("dxy", "美元指數 DXY", 104.0),
                        spec=_LEFT_SPEC, xs=_xs(n),
                        ys=[100.0 + i for i in range(n)], **kw)


def _right(n: int = 5, **kw) -> C.AxisSeries:
    return C.AxisSeries(row=_row("usdtwd", "美元兌台幣", 31.8, decimals=2),
                        spec=_RIGHT_SPEC, xs=_xs(n),
                        ys=[31.0 + i * 0.1 for i in range(n)], **kw)


def _empty(series: C.AxisSeries, reason: str = "") -> C.AxisSeries:
    return dataclasses.replace(series, xs=[], ys=[], miss_reason=reason)


def _layout(fig: go.Figure) -> dict:
    return fig.to_dict()["layout"]


def _shapes(fig: go.Figure) -> list[dict]:
    return list(_layout(fig).get("shapes", ()))


def _annos(fig: go.Figure) -> list[dict]:
    return list(_layout(fig).get("annotations", ()))


class _FakeST:
    """記錄 st.* 呼叫的假物件（L4 渲染離線可驗，不需要 runtime）。"""

    def __init__(self):
        self.calls: list[tuple[str, str]] = []
        self.figs: list[go.Figure] = []

    def markdown(self, body, **kw):
        self.calls.append(("markdown", str(body)))

    def caption(self, body, **kw):
        self.calls.append(("caption", str(body)))

    def plotly_chart(self, fig, **kw):
        self.figs.append(fig)
        self.calls.append(("plotly_chart", str(kw.get("key", ""))))

    def container(self, **kw):
        return _NullCtx()

    def texts(self, kind: str) -> list[str]:
        return [b for k, b in self.calls if k == kind]

    def kinds(self) -> list[str]:
        return [k for k, _ in self.calls]


class _NullCtx:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


# ══════════════════════════════════════════════════════════════════════
# 一、前提檢查（這些一鬆掉，下面整組會變成永遠綠的空殼）
# ══════════════════════════════════════════════════════════════════════

class TestPremises:

    def test_specs_used_here_really_have_thresholds(self):
        """兩個 spec 若哪天沒門檻了，綁軸的斷言會全部空跑而永遠綠。"""
        assert (_LEFT_SPEC.yellow, _LEFT_SPEC.red) != (None, None)
        assert _RIGHT_SPEC.yellow_lo is not None and _RIGHT_SPEC.red_lo is not None, (
            "右邊刻意選 band spec 是為了同時驗到上下四條線 —— 它不再是 band 了"
        )

    def test_left_and_right_are_different_magnitudes(self):
        """卡 A 存在的整個理由。兩軸量級若接近，這張卡就不該用雙軸。"""
        assert _LEFT_SPEC.yellow / _RIGHT_SPEC.yellow > 2.0


# ══════════════════════════════════════════════════════════════════════
# 二、門檻線綁軸 —— 本檔的主角
# ══════════════════════════════════════════════════════════════════════

class TestThresholdAxisBinding:

    def test_left_axis_thresholds_stay_on_primary(self):
        fig = C.build_dual_axis_figure(_left(), _right()).fig
        left_ys = {_LEFT_SPEC.yellow, _LEFT_SPEC.red}
        got = {s["y0"] for s in _shapes(fig) if s.get("yref") == "y"}
        assert got == left_ys

    def test_right_axis_thresholds_bind_to_y2(self):
        """★ 本檔的核心。右軸門檻**必須**綁 y2。

        漏了的話「黃線 32.0」會畫在左軸的 32（DXY 圖底某處），而畫面上它
        就是一條正常虛線 —— 沒有任何肉眼檢查抓得到。
        """
        fig = C.build_dual_axis_figure(_left(), _right()).fig
        right_ys = {_RIGHT_SPEC.yellow, _RIGHT_SPEC.red,
                    _RIGHT_SPEC.yellow_lo, _RIGHT_SPEC.red_lo}
        on_y2 = {s["y0"] for s in _shapes(fig) if s.get("yref") == "y2"}
        assert on_y2 == right_ys, (
            f"右軸門檻沒有全部綁在 y2：實際 {on_y2}，應為 {right_ys}"
        )

    def test_no_threshold_line_is_left_unbound(self):
        """每一條線都要明確綁一條軸；沒有第三種 yref，也不能有 None。"""
        fig = C.build_dual_axis_figure(_left(), _right()).fig
        refs = [s.get("yref") for s in _shapes(fig)]
        assert refs and set(refs) == {"y", "y2"}
        assert len(refs) == 2 + 4, "左 2 條 + 右 4 條，數量對不上代表有線沒畫出來"

    def test_annotation_binds_to_the_same_axis_as_its_line(self):
        """標籤也要跟著搬。只搬線不搬標籤 = 一個浮在別處的數字。"""
        fig = C.build_dual_axis_figure(_left(), _right()).fig
        line_by_y = {s["y0"]: s.get("yref") for s in _shapes(fig)}
        for a in _annos(fig):
            assert a.get("yref") == line_by_y[a["y"]], (
                f"門檻 {a['y']} 的線綁 {line_by_y[a['y']]}，標籤卻綁 {a.get('yref')}"
            )

    def test_annotations_sit_beside_their_own_axis(self):
        """左軸的標註靠左、右軸的靠右 —— 疊在同一側就看不出誰是誰的。"""
        fig = C.build_dual_axis_figure(_left(), _right()).fig
        for a in _annos(fig):
            assert a.get("xref") == "paper"
            if a.get("yref") == "y":
                assert math.isclose(a["x"], 0.0) and a.get("xanchor") == "right"
            else:
                assert math.isclose(a["x"], 1.0) and a.get("xanchor") == "left"

    def test_yref_is_a_required_keyword(self):
        """`_threshold_lines_ssot` 的 `yref` **不給預設值** —— 「忘了傳」要在
        語法層就寫不出來（既有 `_threshold_lines` 給預設值是為了既有 caller
        零行為變更，新 caller 全在畫雙軸，同一個預設值在那裡是陷阱）。"""
        p = inspect.signature(C._threshold_lines_ssot).parameters["yref"]
        assert p.kind is inspect.Parameter.KEYWORD_ONLY
        assert p.default is inspect.Parameter.empty, "yref 不該有預設值"
        with pytest.raises(TypeError):
            C._threshold_lines_ssot(go.Figure(), _LEFT_SPEC)   # type: ignore[call-arg]


# ══════════════════════════════════════════════════════════════════════
# 三、門檻數字與色票都不是打字打出來的
# ══════════════════════════════════════════════════════════════════════

class TestThresholdsFollowSSOT:

    def test_threshold_colors_come_from_shared_colors(self):
        fig = C.build_dual_axis_figure(_left(), _right()).fig
        colors = {s["line"]["color"] for s in _shapes(fig)}
        assert colors == {TRAFFIC_YELLOW, TRAFFIC_RED}

    def test_legacy_inline_hex_is_not_copied_into_the_new_card(self):
        """既有 `_threshold_lines` 的 inline `#b8860b` / `#d03b3b` 是既有瑕疵，
        姊妹檔 `station_charts` 已明文記載刻意不抄。新卡不得複製一份。"""
        fig = C.build_dual_axis_figure(_left(), _right()).fig
        colors = {s["line"]["color"].lower() for s in _shapes(fig)}
        assert not (colors & {"#b8860b", "#d03b3b"})

    def test_series_colors_come_from_l0_palette(self):
        """線色（「這是資料」）走 L0 `COLORS_7`，且左右不同色。"""
        fig = C.build_dual_axis_figure(_left(), _right()).fig
        used = [t.line.color for t in fig.data if t.mode == "lines"]
        assert used == [COLORS_7[0], COLORS_7[4]]
        assert len(set(used)) == 2

    def test_threshold_y_follows_the_spec_when_it_changes(self):
        """有人把數字 inline 寫死 → 這條轉紅。"""
        moved = dataclasses.replace(_RIGHT_SPEC, yellow=_RIGHT_SPEC.yellow + 7.0)
        fig = C.build_dual_axis_figure(
            _left(), dataclasses.replace(_right(), spec=moved)).fig
        on_y2 = {s["y0"] for s in _shapes(fig) if s.get("yref") == "y2"}
        assert moved.yellow in on_y2 and _RIGHT_SPEC.yellow not in on_y2


# ══════════════════════════════════════════════════════════════════════
# 四、雙軸本體
# ══════════════════════════════════════════════════════════════════════

class TestDualMode:

    def test_two_series_land_on_two_different_axes(self):
        plot = C.build_dual_axis_figure(_left(), _right())
        assert plot.mode == C.MODE_DUAL and not plot.notes
        lines = [t for t in plot.fig.data if t.mode == "lines"]
        assert [t.yaxis for t in lines] == ["y", "y2"]

    def test_secondary_axis_overlays_on_the_right(self):
        lay = _layout(C.build_dual_axis_figure(_left(), _right()).fig)
        assert lay["yaxis2"]["overlaying"] == "y"
        assert lay["yaxis2"]["side"] == "right"

    def test_values_are_passed_through_not_recomputed(self):
        """L4 不算任何值：畫出來的 y 必須逐點等於傳進來的序列。"""
        left, right = _left(), _right()
        lines = [t for t in C.build_dual_axis_figure(left, right).fig.data
                 if t.mode == "lines"]
        assert list(lines[0].y) == left.ys
        assert list(lines[1].y) == right.ys

    def test_layout_is_transparent_and_never_hardcodes_a_background(self):
        """硬碼背景塞進 `st.container(border=True)` 會出現色塊接縫，且亮/暗
        佈景必有一邊不能看（同 `station_charts` 檔頭）。"""
        lay = _layout(C.build_dual_axis_figure(_left(), _right()).fig)
        assert lay["plot_bgcolor"] == "rgba(0,0,0,0)"
        assert lay["paper_bgcolor"] == "rgba(0,0,0,0)"

    def test_both_margins_leave_room_for_the_threshold_labels(self):
        """標註掛在圖外左右兩側，margin 收掉就會被裁掉（看不到門檻數字）。"""
        m = _layout(C.build_dual_axis_figure(_left(), _right()).fig)["margin"]
        assert m["l"] >= 40 and m["r"] >= 40


# ══════════════════════════════════════════════════════════════════════
# 五、降級（§1：不留看起來正常的空殼）
# ══════════════════════════════════════════════════════════════════════

class TestDegrade:

    def test_right_missing_leaves_no_empty_secondary_axis(self):
        """留一條沒有資料的 y2，畫面會出現一排刻度而沒有線 —— 讀的人會以為
        那條線的值是 0（貼在軸底），而不是「根本沒抓到」。"""
        plot = C.build_dual_axis_figure(_left(), _empty(_right(), "上游 403"))
        assert plot.mode == C.MODE_LEFT_ONLY
        assert "yaxis2" not in _layout(plot.fig), "降級後仍留著一個空的右軸"
        assert len([t for t in plot.fig.data if t.mode == "lines"]) == 1

    def test_degrade_to_single_axis_moves_thresholds_back_to_primary(self):
        """★ 右邊獨活時，它住在**主軸**上，門檻必須跟著搬回 `y`。

        還綁 `y2` 的話 plotly 會憑空生一條隱形副軸，把門檻畫在那條軸的座標上
        —— 又是一條位置錯誤但外觀正常的虛線。
        """
        plot = C.build_dual_axis_figure(_empty(_left(), "FRED 當機"), _right())
        assert plot.mode == C.MODE_RIGHT_ONLY
        assert "yaxis2" not in _layout(plot.fig)
        refs = {s.get("yref") for s in _shapes(plot.fig)}
        assert refs == {"y"}, f"降級後門檻沒有搬回主軸：{refs}"
        assert {s["y0"] for s in _shapes(plot.fig)} == {
            _RIGHT_SPEC.yellow, _RIGHT_SPEC.red,
            _RIGHT_SPEC.yellow_lo, _RIGHT_SPEC.red_lo}

    def test_degrade_says_which_line_is_missing_and_why(self):
        plot = C.build_dual_axis_figure(_left(), _empty(_right(), "MoneyDJ 403"))
        assert len(plot.notes) == 1
        assert "美元兌台幣" in plot.notes[0] and "MoneyDJ 403" in plot.notes[0]

    def test_missing_reason_is_never_invented(self):
        """§1：上游沒交代原因就說「程式要修」，不編一個聽起來合理的理由。"""
        plot = C.build_dual_axis_figure(_left(), _empty(_right()))
        assert C.NO_REASON_TEXT in plot.notes[0]

    def test_both_missing_draws_nothing(self):
        plot = C.build_dual_axis_figure(_empty(_left(), "A"), _empty(_right(), "B"))
        assert plot.mode == C.MODE_NONE and plot.fig is None
        assert len(plot.notes) == 2


# ══════════════════════════════════════════════════════════════════════
# 六、邊界（空 / 單筆）
# ══════════════════════════════════════════════════════════════════════

class TestEdgeCases:

    def test_single_point_series_still_draws_line_and_marker(self):
        """單筆不該炸（`xs[-1]` / `ys[-1]` 是末點圓點的取法）。"""
        plot = C.build_dual_axis_figure(_left(1), _right(1))
        assert plot.mode == C.MODE_DUAL
        assert len(plot.fig.data) == 4          # 2 條線 + 2 個末點
        markers = [t for t in plot.fig.data if t.mode == "markers"]
        assert [list(t.y) for t in markers] == [[100.0], [31.0]]

    def test_value_none_renders_as_no_data_not_zero(self):
        """§1：值是 None 就顯示「無資料」，不代 0。"""
        s = dataclasses.replace(_left(), row=_row("dxy", "DXY", None))
        assert "無資料" in C._axis_value_html(s)
        assert ">0<" not in C._axis_value_html(s)


# ══════════════════════════════════════════════════════════════════════
# 七、渲染（離線，用假 st）
# ══════════════════════════════════════════════════════════════════════

class TestRender:

    def _render(self, monkeypatch, left, right, **kw) -> _FakeST:
        fake = _FakeST()
        monkeypatch.setattr(C, "st", fake)
        C.render_dual_axis_card("美元指數 / 台幣", left, right, **kw)
        return fake

    def test_happy_path_draws_one_chart(self, monkeypatch):
        fake = self._render(monkeypatch, _left(), _right())
        assert fake.kinds().count("plotly_chart") == 1

    def test_chart_key_is_unique_per_pair(self, monkeypatch):
        fake = self._render(monkeypatch, _left(), _right())
        key = [b for k, b in fake.calls if k == "plotly_chart"][0]
        assert "dxy" in key and "usdtwd" in key

    def test_nothing_to_draw_prints_why_and_draws_no_chart(self, monkeypatch):
        fake = self._render(monkeypatch, _empty(_left(), "A 掛了"),
                            _empty(_right(), "B 掛了"))
        assert "plotly_chart" not in fake.kinds()
        blob = "".join(fake.texts("caption"))
        assert "A 掛了" in blob and "B 掛了" in blob

    def test_degraded_chart_still_says_what_is_missing(self, monkeypatch):
        fake = self._render(monkeypatch, _left(), _empty(_right(), "TDCC 逾時"))
        assert fake.kinds().count("plotly_chart") == 1
        assert "TDCC 逾時" in "".join(fake.texts("caption"))


# ══════════════════════════════════════════════════════════════════════
# 八、版面第二份複本不准漂移
# ══════════════════════════════════════════════════════════════════════

class TestLayoutMatchesExistingCard:
    """`_v2_base_layout` 是既有 `render_chart_card` 那份 layout 的第二份複本。

    複本會漂移，而漂移的樣子是「同一頁的卡片視覺基調不一致」—— 不會壞、
    只會醜到沒人說得出哪裡怪。這裡逐鍵比對，任一邊改了而另一邊沒跟上就轉紅。
    """

    _SHARED_KEYS = ("height", "plot_bgcolor", "paper_bgcolor", "hovermode")

    def _existing_card_layout(self, monkeypatch) -> dict:
        fake = _FakeST()
        monkeypatch.setattr(C, "st", fake)
        monkeypatch.setattr(C.st, "columns", lambda *a, **k: (_NullCtx(), _NullCtx()),
                            raising=False)
        C.render_chart_card(_row("dxy", "DXY", 104.0), _LEFT_SPEC,
                            _xs(5), [100.0 + i for i in range(5)])
        assert fake.figs, "既有卡沒有畫出圖 —— 這組比對會變成空殼"
        return fake.figs[0].to_dict()["layout"]

    def test_shared_visual_keys_are_identical(self, monkeypatch):
        old = self._existing_card_layout(monkeypatch)
        new = _layout(C.build_dual_axis_figure(_left(), _right()).fig)
        for k in self._SHARED_KEYS:
            assert old[k] == new[k], f"版面鍵 {k} 兩份複本已經漂移"

    def test_grid_color_is_identical(self, monkeypatch):
        old = self._existing_card_layout(monkeypatch)
        new = _layout(C.build_dual_axis_figure(_left(), _right()).fig)
        assert old["yaxis"]["gridcolor"] == new["yaxis"]["gridcolor"]


# ══════════════════════════════════════════════════════════════════════
# 九、分層紅線
# ══════════════════════════════════════════════════════════════════════

class TestLayering:

    def test_l4_does_not_reach_into_data_or_compute(self):
        """§8.2：L4 不得取數、不得上行 import；本檔也不該自己讀檔（pandas）。"""
        tree = ast.parse(_SRC.read_text(encoding="utf-8"))
        mods: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                mods += [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                mods.append(node.module)
        bad = [m for m in mods
               if m.split(".")[0] in {"pandas", "requests", "httpx"}
               or m.startswith(("src.data", "src.compute", "src.services", "src.ui.tabs"))]
        assert not bad, f"L4 出現不該有的 import：{bad}"

    def test_build_figure_is_importable_without_streamlit_runtime(self):
        """建圖與渲染分離：`build_dual_axis_figure` 不碰 st.*，測試才驗得到 fig
        （既有 `render_chart_card` 把 fig 建在函式體內、外面拿不到 —— 那個瑕疵
        不在這裡沿用）。"""
        src = inspect.getsource(C.build_dual_axis_figure)
        assert "st." not in src
        assert isinstance(C.build_dual_axis_figure(_left(), _right()).fig, go.Figure)
