"""tests/test_macro_v2_candlestick.py — L4 `macro_v2_cards` K 線卡（卡 B）。

## 這張卡的兩種錯法都不會讓畫面壞掉

1. **缺欄時 fallback 成折線。** 標題寫「日 K」、畫出來卻是一條收盤折線，
   使用者會以為那就是 K 線的形狀，看不出自己少了高低影線（§1：畫面說 A、
   內容是 B）。所以四欄缺任一就**不畫**，並說出缺哪一欄。
2. **長度對不上照畫。** plotly 會把短的那欄補空，畫出一排位置錯開的 K 棒，
   而且完全看不出來。那是上游契約漂移，不是缺資料，一樣擋掉。

另外兩件客戶已拍板、必須被釘住的事：
  · **不畫成交量** —— `volume` 欄自 2026-07-09 起連續 33 個交易日全為 0，
    畫出來就是一整排零。
  · **關掉 rangeslider** —— plotly Candlestick 預設會長縮放條，在 height=210
    的小卡上吃掉近一半。

⚠️ 本檔不啟動 Streamlit runtime；`render_*` 用假 st 離線驗。
"""
from __future__ import annotations

import dataclasses
import inspect

import plotly.graph_objects as go
import pytest

from shared.colors import TRAFFIC_GREEN, TRAFFIC_RED
from shared.macro_buckets import SPECS_BY_KEY
from src.ui.render import macro_v2_cards as C

_SPEC = SPECS_BY_KEY["dxy"]      # high_bad：黃 105 / 紅 110


def _row(value: float | None = 24000.0, band: str = "green") -> C.Row:
    return C.Row(key="taiex", label="加權指數", bucket="mid", unit="",
                 value=value, band=band, state="live", reason=None,
                 hit_source="test", thr_text="—", source="TEST", note="",
                 decimals=0)


def _ohlc(n: int = 5) -> C.OHLC:
    return C.OHLC(
        xs=[f"2026-08-{i + 1:02d}" for i in range(n)],
        open=[100.0 + i for i in range(n)],
        high=[102.0 + i for i in range(n)],
        low=[99.0 + i for i in range(n)],
        close=[101.0 + i for i in range(n)],
    )


class _FakeST:
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

    def columns(self, *a, **kw):
        return (_NullCtx(), _NullCtx())

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
# 一、正常路徑
# ══════════════════════════════════════════════════════════════════════

class TestHappyPath:

    def test_draws_exactly_one_candlestick_trace(self):
        fig = C.build_candlestick_figure(_ohlc(), _SPEC)
        assert len(fig.data) == 1
        assert fig.data[0].type == "candlestick"

    def test_all_four_series_are_passed_through_not_recomputed(self):
        """L4 不算任何值：四條都要逐點等於傳進來的序列。"""
        o = _ohlc()
        t = C.build_candlestick_figure(o, _SPEC).data[0]
        assert list(t.open) == o.open
        assert list(t.high) == o.high
        assert list(t.low) == o.low
        assert list(t.close) == o.close

    def test_up_down_colors_follow_taiwan_convention_from_ssot(self):
        """台股紅漲綠跌（與美股相反），色票走 `shared.colors`，
        與 repo 既有台股 K 線同一組常數。"""
        t = C.build_candlestick_figure(_ohlc(), _SPEC).data[0]
        assert t.increasing.line.color == TRAFFIC_RED
        assert t.decreasing.line.color == TRAFFIC_GREEN

    def test_thresholds_are_drawn_on_the_primary_axis(self):
        """單軸圖 —— 門檻綁 `y`；數字仍來自 spec，不寫死。"""
        lay = C.build_candlestick_figure(_ohlc(), _SPEC).to_dict()["layout"]
        shapes = lay["shapes"]
        assert {s["y0"] for s in shapes} == {_SPEC.yellow, _SPEC.red}
        assert {s.get("yref") for s in shapes} == {"y"}

    def test_layout_stays_transparent(self):
        lay = C.build_candlestick_figure(_ohlc(), _SPEC).to_dict()["layout"]
        assert lay["plot_bgcolor"] == "rgba(0,0,0,0)"
        assert lay["paper_bgcolor"] == "rgba(0,0,0,0)"


# ══════════════════════════════════════════════════════════════════════
# 二、客戶拍板的兩件事
# ══════════════════════════════════════════════════════════════════════

class TestClientDecisions:

    def test_rangeslider_is_off(self):
        """plotly Candlestick 預設**會**長縮放條 —— 沒有顯式關掉這條就紅。"""
        lay = C.build_candlestick_figure(_ohlc(), _SPEC).to_dict()["layout"]
        assert lay["xaxis"]["rangeslider"]["visible"] is False

    def test_rangeslider_default_really_is_on(self):
        """前提檢查：若哪天 plotly 改成預設關閉，上面那條會變成空殼綠燈。"""
        f = go.Figure(go.Candlestick(x=[1], open=[1], high=[2], low=[0], close=[1]))
        assert f.to_dict()["layout"].get("xaxis", {}).get("rangeslider") is None, (
            "本前提假設 plotly 不會主動把 rangeslider 設成 False"
        )

    def test_no_volume_trace_is_drawn(self):
        """`volume` 自 2026-07-09 起連續 33 個交易日全為 0，畫出來是一排零。"""
        fig = C.build_candlestick_figure(_ohlc(), _SPEC)
        assert all(t.type == "candlestick" for t in fig.data)
        assert not any(t.type in ("bar", "scatter") for t in fig.data)

    def test_ohlc_type_has_no_volume_field(self):
        """量不是「畫不畫」的選項，是根本不收 —— 收了就會有人哪天畫上去。"""
        names = {f.name for f in dataclasses.fields(C.OHLC)}
        assert "volume" not in names
        assert names == {"xs", "open", "high", "low", "close"}


# ══════════════════════════════════════════════════════════════════════
# 三、缺欄降級（§1）
# ══════════════════════════════════════════════════════════════════════

class TestMissingField:

    @pytest.mark.parametrize("field", ["open", "high", "low", "close"])
    def test_any_missing_field_blocks_the_chart(self, field):
        broken = dataclasses.replace(_ohlc(), **{field: None})
        assert C.build_candlestick_figure(broken, _SPEC) is None

    @pytest.mark.parametrize("field,zh", list(C.OHLC_FIELDS))
    def test_the_message_names_the_field_that_is_actually_missing(self, field, zh):
        """說錯欄位比不說更糟 —— 會有人去查一個沒壞的欄位。"""
        broken = dataclasses.replace(_ohlc(), **{field: None})
        probs = C.ohlc_problems(broken)
        assert len(probs) == 1
        assert field in probs[0] and zh in probs[0]

    @pytest.mark.parametrize("field", ["open", "high", "low", "close"])
    def test_empty_list_counts_as_missing_too(self, field):
        """給了欄位但裡面沒東西，與沒給是同一件事。"""
        broken = dataclasses.replace(_ohlc(), **{field: []})
        assert C.build_candlestick_figure(broken, _SPEC) is None

    def test_missing_xs_is_reported(self):
        assert C.ohlc_problems(dataclasses.replace(_ohlc(), xs=None))

    def test_all_missing_lists_every_field(self):
        probs = C.ohlc_problems(C.OHLC())
        assert len(probs) == 1 + len(C.OHLC_FIELDS)   # xs + 四欄

    def test_never_falls_back_to_a_line(self, monkeypatch):
        """★ 標題寫「日 K」卻畫折線 = 說 A 做 B。缺欄時**一條線都不准畫**。"""
        fake = _FakeST()
        monkeypatch.setattr(C, "st", fake)
        C.render_candlestick_card(_row(), _SPEC,
                                  dataclasses.replace(_ohlc(), low=None))
        assert "plotly_chart" not in fake.kinds(), "缺欄卻還是畫了一張圖"
        assert not fake.figs

    def test_render_says_which_field_is_missing(self, monkeypatch):
        fake = _FakeST()
        monkeypatch.setattr(C, "st", fake)
        C.render_candlestick_card(_row(), _SPEC,
                                  dataclasses.replace(_ohlc(), high=None))
        blob = "".join(fake.texts("caption"))
        assert "high" in blob and "最高" in blob


# ══════════════════════════════════════════════════════════════════════
# 四、契約漂移與邊界
# ══════════════════════════════════════════════════════════════════════

class TestContractDriftAndEdges:

    def test_length_mismatch_is_blocked_not_silently_drawn(self):
        """plotly 會把短的那欄補空，畫出一排位置錯開的 K 棒而看不出來。"""
        o = _ohlc()
        broken = dataclasses.replace(o, low=o.low[:-1])
        probs = C.ohlc_problems(broken)
        assert probs and "契約漂移" in probs[0]
        assert C.build_candlestick_figure(broken, _SPEC) is None

    def test_xs_length_mismatch_is_blocked(self):
        o = _ohlc()
        assert C.build_candlestick_figure(
            dataclasses.replace(o, xs=o.xs[:-2]), _SPEC) is None

    def test_empty_ohlc_draws_nothing(self):
        assert C.build_candlestick_figure(C.OHLC(), _SPEC) is None

    def test_single_bar_still_draws(self):
        """單筆不該炸，也不該被誤判成缺資料。"""
        fig = C.build_candlestick_figure(_ohlc(1), _SPEC)
        assert fig is not None and len(fig.data[0].open) == 1

    def test_value_none_shows_no_data_not_zero(self, monkeypatch):
        """§1：現值是 None 就顯示「無資料」，不代 0。"""
        fake = _FakeST()
        monkeypatch.setattr(C, "st", fake)
        C.render_candlestick_card(_row(value=None), _SPEC, _ohlc())
        assert "無資料" in "".join(fake.texts("markdown"))


# ══════════════════════════════════════════════════════════════════════
# 五、單一真相源 / 建圖與渲染分離
# ══════════════════════════════════════════════════════════════════════

class TestSSOTAndSeparation:

    def test_field_table_matches_the_dataclass(self):
        """欄名寫兩個地方就會出現「檢查了 low、訊息卻說 close」。"""
        table = {f for f, _ in C.OHLC_FIELDS}
        cls = {f.name for f in dataclasses.fields(C.OHLC)} - {"xs"}
        assert table == cls

    def test_build_figure_does_not_touch_streamlit(self):
        """建圖與渲染分離，Figure 才能在測試裡直接斷言（既有
        `render_chart_card` 把 fig 建在函式體內、外面拿不到）。"""
        assert "st." not in inspect.getsource(C.build_candlestick_figure)
        assert "st." not in inspect.getsource(C.ohlc_problems)

    def test_happy_path_render_draws_one_chart(self, monkeypatch):
        fake = _FakeST()
        monkeypatch.setattr(C, "st", fake)
        C.render_candlestick_card(_row(), _SPEC, _ohlc())
        assert fake.kinds().count("plotly_chart") == 1
        assert fake.figs[0].data[0].type == "candlestick"
