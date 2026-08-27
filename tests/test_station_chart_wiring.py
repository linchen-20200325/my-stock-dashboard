"""L5 接線 —— 週線走勢圖掛進「選列右側面板」（`etf_tab_dividend_station`）。

L2 / L3 / L4 各自有自己的測試（`test_dividend_station_series` / `test_dividend_station_service`
/ `test_station_charts`）。本檔守的是**只有接線這一步會壞掉**的三件事,而且三件都
**不會讓畫面「看起來」壞掉** —— 沒有測試就沒有人會發現:

  1. **plotly key 換列會跟著換**。撞 key 時 Streamlit 沿用前一個元件 → 面板標題寫
     A、圖畫的是 B。這是本次接線最容易出的 bug（紅線 7）。
  2. **L5 不做第二把尺**。個股列 / 抓取失敗列該不該畫圖、缺值印哪一句,整套判斷在
     L4（`weekly_ma_miss_reason` / `miss_text_for` + L0 `MISS_TEXT`）。L5 只要出現
     任何 `MISS_*` 判斷或自編的中文缺值敘述,同一件事就有兩份答案（§2.1 SSOT / §1）。
  3. **圖沒有被包進 `st.expander` / `st.tabs`**。兩者的 body 每次 app run 都會執行
     （收合只是前端）—— 那正是 STATE.md v19.132 產業熱力圖冷抓事故的入口,階段 B2
     把「每列一個 expander」拆掉就是為了這件事。

「沒選列 → 0 張圖」「四種列型各自畫幾張」屬 runtime 行為,走 AppTest,在
`tests/test_dividend_station_mounted.py`（slow lane）。
"""
from __future__ import annotations

import ast
import pathlib

import pytest

from src.ui.etf import etf_tab_dividend_station as L5

_SRC = pathlib.Path(L5.__file__)
_TREE = ast.parse(_SRC.read_text(encoding="utf-8"))


def _fn(name: str) -> ast.FunctionDef:
    for _n in ast.walk(_TREE):
        if isinstance(_n, ast.FunctionDef) and _n.name == name:
            return _n
    raise AssertionError(f"{_SRC.name} 找不到 {name}()")


# ══════════════════════════════════════════════════════════════════════
# 一、plotly key —— 換列一定要換 key（紅線 7）
# ══════════════════════════════════════════════════════════════════════

class TestChartRowKey:

    def test_key_differs_between_two_rows(self):
        """最基本的一條:選第 0 列與選第 1 列,key 不可以一樣。"""
        _a = L5._chart_row_key({"代號": "0050.TW"}, 0)
        _b = L5._chart_row_key({"代號": "0056.TW"}, 1)
        assert _a != _b

    def test_key_differs_for_the_same_ticker_held_and_watched(self):
        """同一檔同時在 📁 Portfolio 與 Watchlist → **兩列同代號**。

        只用 `代號` 組 key 的話這兩列會撞 key,換列時 plotly 沿用上一張圖。
        """
        _held = L5._chart_row_key({"代號": "0050.TW"}, 0)
        _watch = L5._chart_row_key({"代號": "0050.TW"}, 4)
        assert _held != _watch, "同代號不同列撞 key —— 換列會沿用上一檔的圖"

    def test_key_differs_when_the_same_slot_holds_another_ticker(self):
        """重跑戰情室後同一個列序換成別檔 → 只用列序組 key 同樣會沿用舊圖。"""
        assert L5._chart_row_key({"代號": "0050.TW"}, 0) != \
            L5._chart_row_key({"代號": "2330"}, 0)

    def test_key_is_stable_for_the_same_row(self):
        """同一列重畫要拿到同一個 key（否則每次 rerun 都是新元件,狀態全丟）。"""
        _r = {"代號": "0056.TW", "名稱": "高股息"}
        assert L5._chart_row_key(_r, 2) == L5._chart_row_key(dict(_r), 2)

    @pytest.mark.parametrize("bad", [None, "", 0])
    def test_key_survives_a_blank_ticker(self, bad):
        """代號缺漏不該炸（§1 由 L4 決定畫不畫,key 這一步只要不 raise）。"""
        assert isinstance(L5._chart_row_key({"代號": bad}, 1), str)


# ══════════════════════════════════════════════════════════════════════
# 二、L5 不做第二把尺
# ══════════════════════════════════════════════════════════════════════

class TestNoSecondRuler:

    def test_l5_never_references_a_miss_constant(self):
        """全檔（AST）不得出現任何 `MISS_*` 名稱 —— 註解裡提到不算。

        `MISS_*` 一旦進到 L5,就代表這裡開始自己判「該不該畫 / 為什麼沒有」,
        而那套判斷 L4 已經有一份（`weekly_ma_miss_reason` / `boll_z_miss_reason`
        + L0 `MISS_TEXT`）。兩份遲早會漂移,而畫面看起來都正常。
        """
        _hits = [
            _n.attr if isinstance(_n, ast.Attribute) else _n.id
            for _n in ast.walk(_TREE)
            if (isinstance(_n, ast.Attribute) and _n.attr.startswith("MISS_"))
            or (isinstance(_n, ast.Name) and _n.id.startswith("MISS_"))
        ]
        assert _hits == [], f"L5 出現 MISS_* 判斷（第二把尺）：{_hits}"

    def test_l5_never_calls_the_l4_miss_helpers(self):
        """也不得自己呼叫 L4 的缺值判斷 —— 那是 L4 渲染函式自己內部的事。"""
        _banned = {"miss_text_for", "weekly_ma_miss_reason", "boll_z_miss_reason",
                   "missing_line_notes", "most_fundamental_miss",
                   "build_weekly_ma_figure", "build_boll_z_figure"}
        _called = {
            _n.func.id if isinstance(_n.func, ast.Name) else _n.func.attr
            for _n in ast.walk(_TREE)
            if isinstance(_n, ast.Call)
            and isinstance(_n.func, (ast.Name, ast.Attribute))
        }
        assert not (_called & _banned), \
            f"L5 自己判缺值 / 自己組圖：{sorted(_called & _banned)}"

    def test_l5_only_imports_the_two_render_entrypoints(self):
        """從 L4 走勢圖模組只准拿兩支**渲染**函式進來。"""
        _got = {
            _a.name
            for _n in ast.walk(_TREE)
            if isinstance(_n, ast.ImportFrom)
            and (_n.module or "").endswith("station_charts")
            for _a in _n.names
        }
        assert _got == {"render_weekly_ma_chart", "render_boll_z_chart"}, _got


# ══════════════════════════════════════════════════════════════════════
# 三、擺法 —— 不准包 expander / tabs
# ══════════════════════════════════════════════════════════════════════

class TestPanelPlacement:

    def test_light_detail_uses_no_expander_or_tabs(self):
        """`_render_light_detail` 內不得出現 `st.expander` / `st.tabs`。

        兩者的 body 每次 app run 都執行 —— 把圖包進去等於「收起來也在畫」,
        成本前提（沒選列就 0 張圖）當場失效。
        """
        _bad = [
            _n.func.attr
            for _n in ast.walk(_fn("_render_light_detail"))
            if isinstance(_n, ast.Call) and isinstance(_n.func, ast.Attribute)
            and _n.func.attr in ("expander", "tabs")
        ]
        assert _bad == [], f"選列面板裡出現 {_bad} —— body 每次 app run 都會執行"

    def test_charts_render_after_the_light_detail_in_the_panel(self):
        """圖排在 `render_holding_detail` **之後**（身分歸屬:「### 代號 名稱」
        這個標題在它最上面,圖排它前面就會變成「畫面說 A、圖是 B」）。"""
        _order = [
            (_n.lineno, _n.func.id)
            for _n in ast.walk(_fn("_render_light_detail"))
            if isinstance(_n, ast.Call) and isinstance(_n.func, ast.Name)
            and _n.func.id in ("render_holding_detail", "render_weekly_ma_chart",
                               "render_boll_z_chart")
        ]
        _seq = [_name for _, _name in sorted(_order)]
        assert _seq == ["render_holding_detail", "render_weekly_ma_chart",
                        "render_boll_z_chart"], _seq
