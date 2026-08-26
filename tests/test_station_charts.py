"""L4 `src/ui/render/station_charts.py` —— 週線走勢圖（週K vs 均線 / 布林 z）。

L4 是純渲染,**離線可驗**:不需要 Streamlit runtime 就能檢查 `go.Figure` 物件。
本檔的原料一律由 **L3 真函式** `_weekly_series_payload` 生出來（不手捏 dict）——
手捏的 payload 只會驗到「我以為的契約」,驗不到真契約漂移。

守的四件事:
  1. 三條均線都在、線數正確（少畫一條 = 使用者在圖上找不到燈的依據）。
  2. 門檻線 y 值**跟著 L0 常數動**（有人 inline 寫死 → 轉紅,見
     `test_threshold_y_follows_l0_when_constant_changes`）。
  3. §1 五種降級各自的行為（不畫空圖 / 文案走 L0 / NaN 破洞保持斷線 / 例外只隔離一張）。
  4. §8.2 分層紅線:本檔不得 import `src.data.*` / `src.compute.*`,不得碰 session_state。
"""
from __future__ import annotations

import ast
import math
import pathlib
import re

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import pytest

from shared import dividend_station_thresholds as T
from shared import station_specs as SS
from shared.colors import TRAFFIC_GREEN, TRAFFIC_ORANGE, TRAFFIC_RED, TRAFFIC_YELLOW
from src.services.dividend_station_service import _weekly_series_payload
from src.ui.render import station_charts as C

_SRC = pathlib.Path(C.__file__)


def _close(n: int, *, flat: bool = False) -> pd.Series:
    """n 週的週五收盤序列（index = 週五,與 L3 的形狀一致）。"""
    idx = pd.date_range("2021-01-01", periods=n, freq="W-FRI")
    if flat:
        return pd.Series([50.0] * n, index=idx)
    return pd.Series(np.linspace(50.0, 80.0, n) + np.sin(np.arange(n)), index=idx)


def _payload(n: int, **kw) -> dict:
    return _weekly_series_payload(_close(n, **kw))


def _names(fig: go.Figure) -> list[str]:
    return [t.name for t in fig.data]


def _hline_ys(fig: go.Figure) -> list[float]:
    """`add_hline` 落在 layout.shapes（y0 == y1）。"""
    return [float(s.y0) for s in fig.layout.shapes]


class _FakeST:
    """記錄 st.* 呼叫的假物件（L4 渲染離線可驗,不需要 runtime）。"""

    def __init__(self, *, plotly_raises: bool = False):
        self.calls: list[tuple[str, str]] = []
        self._plotly_raises = plotly_raises

    def markdown(self, body, **kw):
        self.calls.append(("markdown", str(body)))

    def caption(self, body, **kw):
        self.calls.append(("caption", str(body)))

    def info(self, body, **kw):
        self.calls.append(("info", str(body)))

    def plotly_chart(self, fig, **kw):
        if self._plotly_raises:
            raise RuntimeError("plotly 壞了")
        self.calls.append(("plotly_chart", str(kw.get("key", ""))))

    def texts(self, kind: str) -> list[str]:
        return [b for k, b in self.calls if k == kind]

    def kinds(self) -> list[str]:
        return [k for k, _ in self.calls]


# ══════════════════════════════════════════════════════════════════════
# 一、週K vs 均線
# ══════════════════════════════════════════════════════════════════════

class TestWeeklyMaFigure:

    def test_three_ma_lines_plus_close(self):
        """user 核准畫**三條**:只畫季線的話,燈一（破月線）與燈三（破年線）
        亮起來時使用者在圖上找不到依據。"""
        fig = C.build_weekly_ma_figure(_payload(120))
        assert len(fig.data) == len(C.MA_WINDOWS) + 1      # 3 條均線 + 週收
        assert _names(fig) == ["週收", "4 週月線", "13 週季線", "52 週年線"]

    def test_ma_windows_and_labels_come_from_l0(self):
        """線名裡的週數不是打字打出來的 —— 全部由 L0 常數代入。"""
        assert C.MA_WINDOWS == (T.MA_MONTH_WEEKS, T.MA_QUARTER_WEEKS, T.MA_YEAR_WEEKS)
        for _w in C.MA_WINDOWS:
            assert C.ma_line_label(_w).startswith(f"{_w} 週")

    def test_line_colors_are_shared_colors_ssot(self):
        """§3.3:線色走 `shared.colors`,不是本檔 inline 的 hex。
        規則 = 這條線對應哪一盞燈（月/季/年 → 燈一/二/三）。"""
        fig = C.build_weekly_ma_figure(_payload(120))
        got = {t.name: t.line.color for t in fig.data}
        assert got["4 週月線"] == TRAFFIC_GREEN
        assert got["13 週季線"] == TRAFFIC_YELLOW
        assert got["52 週年線"] == TRAFFIC_RED

    def test_close_values_are_passed_through_not_recomputed(self):
        """L4 不算任何值:畫出來的 y 必須逐點等於 L3 給的序列。"""
        p = _payload(120)
        fig = C.build_weekly_ma_figure(p)
        y = list(fig.data[0].y)
        assert len(y) == len(p["close"])
        assert all(math.isclose(a, b, rel_tol=1e-12)
                   for a, b in zip(y, list(p["close"].values)))

    def test_ma_values_are_passed_through_not_recomputed(self):
        p = _payload(120)
        fig = C.build_weekly_ma_figure(p)
        y = list(fig.data[2].y)                      # 13 週季線
        src = list(p["ma"][T.MA_QUARTER_WEEKS].values)
        assert len(y) == len(src)
        assert all((math.isnan(a) and math.isnan(b)) or math.isclose(a, b, rel_tol=1e-12)
                   for a, b in zip(y, src))

    def test_short_history_drops_only_the_year_line(self):
        """30 週 → 只有年線缺,月線 / 季線照畫（不是整張圖砍掉）。"""
        p = _payload(30)
        assert p["ma_miss"] == {T.MA_YEAR_WEEKS: SS.MISS_NOT_ENOUGH}
        fig = C.build_weekly_ma_figure(p)
        assert _names(fig) == ["週收", "4 週月線", "13 週季線"]
        assert len(fig.data) == len(C.MA_WINDOWS)    # 少一條,不是少一張圖

    def test_missing_line_note_text_comes_from_l0(self):
        """缺線的說明**不是本層編的**,逐字取自 L0 `MISS_TEXT`。"""
        notes = C.missing_line_notes(_payload(30))
        assert len(notes) == 1
        assert C.ma_line_label(T.MA_YEAR_WEEKS) in notes[0]
        assert SS.MISS_TEXT[SS.MISS_NOT_ENOUGH] in notes[0]

    def test_drawable_lines_get_no_note(self):
        """能畫的線不列進缺值說明（列進去會讓人以為它也缺）。"""
        assert C.missing_line_notes(_payload(120)) == []

    def test_nan_gap_stays_broken(self):
        """§1:NaN 破洞保持斷線。連起來 = 用視覺捏造一段不存在的資料。"""
        p = _payload(120)
        p["close"].iloc[40:45] = float("nan")
        fig = C.build_weekly_ma_figure(p)
        for t in fig.data:
            assert t.connectgaps is not True
        assert any(math.isnan(v) for v in fig.data[0].y)   # 破洞真的還在

    def test_ma_leading_nan_is_preserved(self):
        """均線前 N−1 週是 L3 刻意遮的 NaN —— 本層不得補值。"""
        fig = C.build_weekly_ma_figure(_payload(120))
        y = list(fig.data[3].y)                            # 52 週年線
        assert math.isnan(y[0]) and not math.isnan(y[-1])

    @pytest.mark.parametrize("reason", [SS.MISS_NOT_APPLICABLE, SS.MISS_FETCH_FAILED])
    def test_no_figure_when_whole_series_missing(self, reason):
        """§1 不畫空圖:整組沒有序列 → **不產生 figure**。"""
        p = _weekly_series_payload(None, unavailable=reason)
        assert C.weekly_ma_miss_reason(p) == reason
        assert C.build_weekly_ma_figure(p) is None

    def test_broken_contract_is_named_drift_not_missing(self):
        """形狀不對 ≠ 沒資料。標成缺資料會讓契約漂移偽裝成「等時間累積」。"""
        assert C.weekly_ma_miss_reason({"nope": 1}) == SS.MISS_CONTRACT_DRIFT
        assert C.weekly_ma_miss_reason(None) == SS.MISS_CONTRACT_DRIFT
        p = _payload(120)
        p["close"] = pd.Series(dtype="float64")            # 宣稱有序列卻是空的
        assert C.weekly_ma_miss_reason(p) == SS.MISS_CONTRACT_DRIFT


# ══════════════════════════════════════════════════════════════════════
# 二、布林 z
# ══════════════════════════════════════════════════════════════════════

class TestBollZFigure:

    def test_five_threshold_lines_drawn(self):
        """加碼 3 條 + 停利 2 條。停利線非畫不可:它與加碼線走同一條 z 軸、
        由同一支 `light_235` 判 —— 不畫的話 💰 亮起來時圖上沒有依據。"""
        fig = C.build_boll_z_figure(_payload(120))
        assert len(_hline_ys(fig)) == 5
        assert len(fig.data) == 1                          # z 序列本身只有一條

    def test_threshold_y_values_equal_l0_constants(self):
        """門檻線 y 值 == L0 常數（逐一比對,不是比個數）。"""
        fig = C.build_boll_z_figure(_payload(120))
        assert sorted(_hline_ys(fig)) == sorted([
            T.Z_LIGHT1, T.Z_LIGHT2, T.Z_LIGHT3,
            T.Z_TAKE_PROFIT_PARTIAL, T.Z_TAKE_PROFIT_FORCE,
        ])

    def test_threshold_y_follows_l0_when_constant_changes(self, monkeypatch):
        """**這條才是反 inline 的守衛。**上一條在有人把 −1.0 寫死時照樣會綠
        （寫死的值剛好等於常數）。這裡改 L0 常數:圖上的線沒跟著動 → 轉紅。"""
        monkeypatch.setattr(T, "Z_LIGHT1", -1.234)
        monkeypatch.setattr(T, "Z_TAKE_PROFIT_FORCE", 3.456)
        fig = C.build_boll_z_figure(_payload(120))
        ys = _hline_ys(fig)
        assert -1.234 in ys, "燈一門檻沒跟著 L0 動 = 有人在 L4 寫死了數字"
        assert 3.456 in ys, "強制停利門檻沒跟著 L0 動 = 有人在 L4 寫死了數字"

    def test_threshold_colors_are_shared_colors_ssot(self):
        """§3.3:門檻線色走 `shared.colors`。
        （姊妹檔 `macro_v2_cards._threshold_lines` 的 `#b8860b` / `#d03b3b`
        是 inline literal —— 那個瑕疵刻意不抄過來。）"""
        allowed = {TRAFFIC_GREEN, TRAFFIC_YELLOW, TRAFFIC_RED, TRAFFIC_ORANGE}
        fig = C.build_boll_z_figure(_payload(120))
        assert {s.line.color for s in fig.layout.shapes} <= allowed
        by_y = {float(s.y0): s.line.color for s in fig.layout.shapes}
        assert by_y[T.Z_LIGHT1] == TRAFFIC_GREEN            # 燈一 🟢
        assert by_y[T.Z_LIGHT2] == TRAFFIC_YELLOW           # 燈二 🟡
        assert by_y[T.Z_LIGHT3] == TRAFFIC_RED              # 燈三 🔴
        assert by_y[T.Z_TAKE_PROFIT_PARTIAL] == TRAFFIC_ORANGE
        assert by_y[T.Z_TAKE_PROFIT_FORCE] == TRAFFIC_ORANGE

    def test_threshold_labels_use_l0_light_icons(self):
        """標註的圖示取自 L0 `LIGHT_META`,不在本層另編一套。"""
        labels = [s.label for s in C.threshold_line_specs()]
        assert labels[0].startswith(T.LIGHT_META[T.LIGHT_3]["icon"])
        assert labels[2].startswith(T.LIGHT_META[T.LIGHT_1]["icon"])
        assert labels[4].startswith(T.LIGHT_META[T.LIGHT_TAKE_PROFIT]["icon"])

    def test_z_values_are_passed_through_not_recomputed(self):
        p = _payload(120)
        fig = C.build_boll_z_figure(p)
        y, src = list(fig.data[0].y), list(p["boll_z"].values)
        assert len(y) == len(src)
        assert all((math.isnan(a) and math.isnan(b)) or math.isclose(a, b, rel_tol=1e-12)
                   for a, b in zip(y, src))

    def test_nan_gap_stays_broken(self):
        p = _payload(120)
        p["boll_z"].iloc[60:66] = float("nan")
        fig = C.build_boll_z_figure(p)
        assert fig.data[0].connectgaps is not True
        assert any(math.isnan(v) for v in fig.data[0].y)

    def test_no_figure_when_history_too_short(self):
        """< 20 週 → L3 標 `MISS_NOT_ENOUGH`,這張圖不畫（§1）。"""
        p = _payload(10)
        assert p["boll_z_miss"] == SS.MISS_NOT_ENOUGH
        assert C.boll_z_miss_reason(p) == SS.MISS_NOT_ENOUGH
        assert C.build_boll_z_figure(p) is None

    def test_no_figure_when_flat_prices(self):
        """整段零波動 → std≈0,z 整條算不出來（L3 標 `MISS_NO_INPUT`）。"""
        p = _payload(60, flat=True)
        assert p["boll_z_miss"] == SS.MISS_NO_INPUT
        assert C.build_boll_z_figure(p) is None

    def test_most_fundamental_reason_wins(self):
        """整組缺 + 這條缺同時成立 → 走 L0 `most_fundamental_miss`,
        不在本層自訂優先序。"""
        p = _weekly_series_payload(None, unavailable=SS.MISS_FETCH_FAILED)
        p["boll_z_miss"] = SS.MISS_NOT_APPLICABLE
        assert C.boll_z_miss_reason(p) == SS.MISS_FETCH_FAILED

    def test_ma_chart_survives_when_only_z_is_missing(self):
        """z 算不出來**不該**連累週K 圖 —— 兩張圖各自降級。"""
        p = _payload(60, flat=True)
        assert C.build_boll_z_figure(p) is None
        assert C.build_weekly_ma_figure(p) is not None


# ══════════════════════════════════════════════════════════════════════
# 三、缺值文案 —— 本層不編字
# ══════════════════════════════════════════════════════════════════════

class TestMissText:

    @pytest.mark.parametrize("reason", sorted(SS.MISS_TEXT))
    def test_every_reason_uses_l0_text_verbatim(self, reason):
        assert C.miss_text_for(reason) == SS.MISS_TEXT[reason]

    def test_unknown_reason_is_not_guessed(self):
        """認不得的原因**不猜**（挑錯一個就會給出「重跑一次就好」這種錯指引）。"""
        got = C.miss_text_for("__nope__")
        assert "__nope__" in got and "程式要修" in got
        assert got not in SS.MISS_TEXT.values()


# ══════════════════════════════════════════════════════════════════════
# 四、渲染層的五種降級（假 st,離線）
# ══════════════════════════════════════════════════════════════════════

class TestRenderDegradation:

    def test_missing_series_prints_l0_text_and_no_chart(self, monkeypatch):
        """降級 1:`miss_reason` 非空 → 整張圖不畫,印 L0 文案。"""
        fake = _FakeST()
        monkeypatch.setattr(C, "st", fake)
        p = _weekly_series_payload(None, unavailable=SS.MISS_NOT_APPLICABLE)
        C.render_weekly_ma_chart(p, ticker="2330")
        assert "plotly_chart" not in fake.kinds()
        assert fake.texts("info") == [SS.MISS_TEXT[SS.MISS_NOT_APPLICABLE]]

    def test_missing_line_prints_note_and_still_draws(self, monkeypatch):
        """降級 2:某條均線缺 → 那條不畫、其餘照畫 + 逐條交代原因。"""
        fake = _FakeST()
        monkeypatch.setattr(C, "st", fake)
        C.render_weekly_ma_chart(_payload(30), ticker="0056")
        assert "plotly_chart" in fake.kinds()
        assert any(SS.MISS_TEXT[SS.MISS_NOT_ENOUGH] in t for t in fake.texts("caption"))

    def test_boll_missing_prints_l0_text_and_no_chart(self, monkeypatch):
        """降級 3:`boll_z_miss` 非空 → 布林圖不畫,印原因。"""
        fake = _FakeST()
        monkeypatch.setattr(C, "st", fake)
        C.render_boll_z_chart(_payload(10), ticker="00878")
        assert "plotly_chart" not in fake.kinds()
        assert fake.texts("info") == [SS.MISS_TEXT[SS.MISS_NOT_ENOUGH]]

    def test_render_exception_is_isolated_and_logged(self, monkeypatch, capsys):
        """降級 5:畫圖丟例外 → 只隔離這一張,不炸整頁;而且**一定 log**。"""
        fake = _FakeST(plotly_raises=True)
        monkeypatch.setattr(C, "st", fake)
        C.render_weekly_ma_chart(_payload(120), ticker="2330")     # 不得往外炸
        out = capsys.readouterr().out
        assert "[station_charts]" in out and "RuntimeError" in out
        assert any("畫不出來" in t for t in fake.texts("caption"))

    def test_footer_numbers_come_from_payload_and_l0(self, monkeypatch):
        """圖說裡的週數 / 布林週期不是寫死的。"""
        fake = _FakeST()
        monkeypatch.setattr(C, "st", fake)
        C.render_boll_z_chart(_payload(120), ticker="2330")
        assert any(f"{T.BOLL_PERIOD_WEEKS} 週布林" in t for t in fake.texts("caption"))


# ══════════════════════════════════════════════════════════════════════
# 五、§8.2 分層紅線
# ══════════════════════════════════════════════════════════════════════

class TestLayeringGuard:
    """L4 不取數、不上行依賴 L2、不碰 session_state。

    ⚠️ `EX-PASSTHRU-1` 的「L4 Render lazy fallback」**不適用於走勢圖**:
    那條的前提是「該 fetcher 無對應 L3 service 且 caller 只是取數」,
    走勢圖兩個前提都不成立（有對應 L3、序列要經過計算）。故本檔 0 例外。
    """

    def test_grep_no_data_or_compute_import(self):
        """grep 式守衛:錨在行首的 import 陳述,不會被 docstring 裡的散文誤判。"""
        hits = re.findall(r"(?m)^\s*(?:from|import)\s+src\.(?:data|compute)\b",
                          _SRC.read_text(encoding="utf-8"))
        assert hits == [], f"L4 不得 import L1/L2:{hits}"

    def test_ast_no_data_or_compute_import_anywhere(self):
        """AST 版（比 grep 強）:連函式體內的 lazy import 也一起抓。"""
        bad: list[str] = []
        for node in ast.walk(ast.parse(_SRC.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                bad += [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                bad.append(node.module or "")
        offenders = [m for m in bad
                     if m.startswith("src.data") or m.startswith("src.compute")]
        assert offenders == [], f"L4 不得 import L1/L2:{offenders}"

    def test_no_session_state(self):
        """沿用 `station_cards` 檔頭同一份契約:不碰 session_state。

        比對 `st.session_state` 這個**取用式**而非裸字串 —— 檔頭那句
        「不碰 session_state」的宣告本身不該把守衛弄紅。
        """
        hits = re.findall(r"\bst\s*\.\s*session_state\b",
                          _SRC.read_text(encoding="utf-8"))
        assert hits == [], f"L4 不得碰 session_state:{hits}"

    def test_imports_only_l0_and_libs(self):
        """實際 import 只有 L0 `shared.*` 與第三方（plotly / streamlit）。"""
        mods: list[str] = []
        for node in ast.walk(ast.parse(_SRC.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                mods += [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                mods.append(node.module or "")
        for m in mods:
            assert m.startswith("shared") or m in (
                "__future__", "dataclasses", "plotly.graph_objects", "streamlit"), m
