# -*- coding: utf-8 -*-
"""tests/test_ui2_d1_kbar_yaxis_floor.py — D1（#1199 總管裁示 1，comment 7011701691）：📊 日 K y 軸不得出現負刻度。

缺陷（修前）：`src/ui2/components/html.py::_kbar_svg` 以 `lo - pad` 當 y 軸下限；當 pad > lo（一筆極端離群低價把 span 撐大）時，
即使全部 OHLC 都是有限正值，也會畫出「負的台股指數刻度」並把圖壓扁。

修法的合約（本檔斷言）：
1. 最低顯示界線夾在 ≥ 0（0 可作軸刻度，不代表實際值為 0）；ticks／座標以**新 domain** 重算（⛔ 只把負 tick 字串藏起來而維持負域）。
2. 保留相對資料：K 棒數、日期、顏色方向、刻度順序與點數（5 個 tick）不變。
3. 一般正常窗（lo - pad ≥ 0）輸出與修前**逐字相同**（無意外縮放／截斷）；全常數（零寬 span）不除以零。
4. 不改真數據／取樣／比例政策／K 根數／L0 價格與離群驗證（離群自動棄用屬另案）。

測試分三層：純 SVG 層（直接給 VM）、端到端（真 L1 parquet → 真 feed → canonical → VM → html）、反向（獨立重算 domain 對座標）。
"""
from __future__ import annotations

import datetime as dt
import math
import re

import pandas as pd
import pytest

from shared.ui2_contract.models import CandleVM, FieldState, FieldVM, KbarChartVM
from src.ui2.components import html as H

_PLOT_H = H.KBAR_PLOT_H
_Y0, _Y1 = H._KB_TOP, H.KBAR_PLOT_H - H._KB_BOTTOM_PAD
_TICKS_N = H._KB_TICKS


# ── helpers ──────────────────────────────────────────────────────────────
def _vm(closes, *, spread: float = 0.0) -> KbarChartVM:
    """每根 O=C（可加 high/low 上下影線 `spread`）；日期連續遞增（唯一）。"""
    cs = []
    for i, c in enumerate(closes):
        d = dt.date(2026, 10, 1) + dt.timedelta(days=i)
        cs.append(CandleVM(d.isoformat(), c, c + spread, c - spread, c))
    return KbarChartVM(FieldVM("台股加權指數日 K", FieldState.OK, "1.00"), tuple(cs), target_n=max(20, len(cs)))


def _yaxis(svg_html: str):
    """回傳 [(tick_value, text_y)]（由上到下），數值取自畫面上的刻度字串。"""
    m = re.search(r'<svg class="ui2-kbar__yaxis"[^>]*>(.*?)</svg>', svg_html, re.S)
    assert m, "找不到 y 軸 svg"
    out = []
    for y, label in re.findall(r'<text x="[\d.]+" y="(-?[\d.]+)"[^>]*>([^<]*)</text>', m.group(1)):
        out.append((float(label.replace(",", "")), float(y)))
    return out


def _grid_ys(svg_html: str) -> list[float]:
    return [float(y) for y in re.findall(r'<line x1="0" x2="100%" y1="(-?[\d.]+)" y2="[\d.-]+"', svg_html)]


def _bars(svg_html: str):
    """[(date, wick_y_top, wick_y_bot, rect_y, rect_h, dir)]"""
    out = []
    for g in re.findall(r'<g class="ui2-kbar__c[^"]*" data-kbar-dir="(\w+)" data-kbar-date="([\d-]+)">(.*?)</g>',
                        svg_html, re.S):
        d, date, inner = g
        w = re.search(r'<line x1="[\d.]+%" x2="[\d.]+%" y1="(-?[\d.]+)" y2="(-?[\d.]+)"', inner)
        r = re.search(r'<rect x="[\d.-]+%" y="(-?[\d.]+)" width="[\d.]+%" height="(-?[\d.]+)"', inner)
        out.append((date, float(w.group(1)), float(w.group(2)), float(r.group(1)), float(r.group(2)), d))
    return out


def _all_numbers_in_svg_are_finite(svg_html: str) -> None:
    for tok in re.findall(r'(?<![\w#])-?(?:nan|inf)\b', svg_html, re.I):
        raise AssertionError(f"SVG 出現非有限數字 {tok!r}")
    for n in re.findall(r'="(-?[\d.]+)%?"', svg_html):
        assert math.isfinite(float(n))


def _assert_d1_contract(vm: KbarChartVM) -> str:
    html = H._kbar_svg(vm)
    _all_numbers_in_svg_are_finite(html)
    ticks = _yaxis(html)
    assert len(ticks) == _TICKS_N                                       # 刻度點數不變
    values = [v for v, _ in ticks]
    assert all(v >= 0 for v in values), f"y 軸出現負刻度：{values}"          # ≥ 0（0 可作軸刻度）
    assert values == sorted(values, reverse=True)                        # 刻度順序：由高到低
    if values[0] - values[-1] >= 100:                                    # 刻度等距（標籤四捨五入 ±1）＝ticks 由同一個 domain 等分算出，
        steps = [a - b for a, b in zip(values, values[1:])]              # ⛔ 只把負字串改成 0/隱藏而維持負域
        assert max(steps) - min(steps) <= 2 and min(steps) > 0, f"刻度不等距：{values}"
    ys = [y for _, y in ticks]
    assert ys == sorted(ys)                                              # 座標由上到下
    grid = _grid_ys(html)
    assert len(grid) == _TICKS_N and all(_Y0 - 0.01 <= g <= _Y1 + 0.01 for g in grid)
    assert grid[0] == pytest.approx(_Y0, abs=0.01) and grid[-1] == pytest.approx(_Y1, abs=0.01)   # domain 撐滿繪圖區
    bars = _bars(html)
    assert [b[0] for b in bars] == [c.date for c in vm.candles]            # 日期／根數／順序全保留
    for date, wt, wb, ry, rh, _d in bars:                                # 所有有效正 K 棒可視（皆落在繪圖區）
        assert _Y0 - 0.01 <= wt <= wb <= _Y1 + 0.01, (date, wt, wb)
        assert _Y0 - 0.01 <= ry and ry + rh <= _Y1 + 2.0, (date, ry, rh)  # 實體最小可見高度 1.5px 可略越界
    return html


# ── 1. 純 SVG 層：極端離群（缺陷重現）──────────────────────────────────────
_OUTLIER = [23000.0] * 10 + [230.0] + [23100.0] * 9               # 總管裁示的重現例
_OUTLIER_TINY = [23000.0] * 19 + [1.0]                            # 巡檢另一例（修前為 -1,379）


@pytest.mark.parametrize("closes", [_OUTLIER, _OUTLIER_TINY], ids=["close230", "close1"])
def test_extreme_low_outlier_never_produces_negative_axis(closes):
    _assert_d1_contract(_vm(closes))


def test_extreme_outlier_axis_floor_is_exactly_zero_and_domain_is_recomputed():
    """下界夾在 0（最低 tick＝0、貼繪圖區底）；其餘 tick 以新 domain [0, hi_p] 等分（⛔ 只藏負字串）。"""
    vm = _vm(_OUTLIER)
    html = _assert_d1_contract(vm)
    ticks = _yaxis(html)
    hi = max(c.high for c in vm.candles)
    lo = min(c.low for c in vm.candles)
    pad = (hi - lo) * 0.06
    hi_p = hi + pad
    assert ticks[-1][0] == 0.0
    expected = [round(hi_p - i * hi_p / (_TICKS_N - 1)) for i in range(_TICKS_N)]
    assert [v for v, _ in ticks] == expected
    # 座標與新 domain 一致：低價 230 的那根，其影線底端 y 必須等於 domain [0, hi_p] 線性投影的位置
    want_y = _Y0 + (hi_p - lo) / hi_p * (_Y1 - _Y0)
    bar230 = [b for b in _bars(html) if b[0] == vm.candles[10].date][0]
    assert bar230[2] == pytest.approx(want_y, abs=0.01)
    assert bar230[2] < _Y1                                             # 在軸線之上、看得見（不貼死底緣之外）


def test_outlier_neighbours_keep_relative_order_and_direction():
    """相對資料保留：離群那根最低、其餘同價；方向色不變（O=C → flat）。"""
    html = H._kbar_svg(_vm(_OUTLIER))
    bars = _bars(html)
    assert {b[5] for b in bars} == {"flat"}
    ys = [b[2] for b in bars]
    assert ys[10] == max(ys)                                           # 最低價 ⇒ 最大 y（最靠下）
    assert len({round(y, 2) for i, y in enumerate(ys) if i != 10 and i < 10}) == 1


# ── 2. 一般正常窗：與修前逐字相同 ────────────────────────────────────────
def test_normal_window_is_unchanged_from_pre_fix_formula():
    """lo - pad ≥ 0 的正常窗：domain＝[lo - pad, hi + pad]（修前公式），刻度字串與修前完全相同。"""
    closes = [19000.0 + i * (1000.0 / 19) for i in range(20)]
    vm = _vm(closes, spread=0.0)
    html = _assert_d1_contract(vm)
    lo, hi = min(closes), max(closes)
    pad = (hi - lo) * 0.06
    lo_p, hi_p = lo - pad, hi + pad
    want = [round(hi_p - i * (hi_p - lo_p) / (_TICKS_N - 1)) for i in range(_TICKS_N)]
    assert [v for v, _ in _yaxis(html)] == want
    assert want == [20060, 19780, 19500, 19220, 18940]               # 手算固定值（防兩邊同錯）


def test_normal_window_with_wicks_keeps_all_bars_visible():
    closes = [20000.0 + 25 * ((-1) ** i) * (i % 7) for i in range(20)]
    _assert_d1_contract(_vm(closes, spread=40.0))


# ── 3. 全常數（零寬 span）──────────────────────────────────────────────────
@pytest.mark.parametrize("px", [23000.0, 1234.5, 100.0, 1.0, 0.5, 0.01])
def test_constant_window_zero_span_does_not_divide_by_zero(px):
    vm = _vm([px] * 20)
    html = _assert_d1_contract(vm)
    bars = _bars(html)
    assert len({(b[1], b[2]) for b in bars}) == 1                      # 全常數 ⇒ 每根位置相同、不炸


def test_constant_large_price_keeps_the_pre_fix_symmetric_padding():
    html = H._kbar_svg(_vm([23000.0] * 20))
    assert [v for v, _ in _yaxis(html)] == [23023, 23012, 23000, 22988, 22977]


def test_single_candle_window():
    _assert_d1_contract(_vm([22000.0]))


# ── 4. 端到端：真 L1 parquet → 真 feed → canonical → VM → html（總管重現例）─────────────
def _e2e_kbar_vm(tmp_path, monkeypatch, closes):
    from shared import regime_arbiter as RA  # noqa: F401
    from src.data.macro import macro_cache_reader as R
    from src.services import allocation_service, market_twii_view_service as S
    from src.services.ui2 import real_feed as RF
    from src.services.ui2.real_canonical import get_real_page_vm
    from shared.ui2_contract.pages import P4_MARKET

    today = dt.date(2026, 11, 11)
    dates = [today - dt.timedelta(days=len(closes) - i) for i in range(len(closes))]
    df = pd.DataFrame({"date": pd.to_datetime(dates), "close": closes})
    df["open"] = df["high"] = df["low"] = df["close"]
    df["volume"] = 1000
    df["fetched_at"] = [f"{d.isoformat()}T10:00:00+00:00" for d in dates]
    df.to_parquet(tmp_path / "twii_ohlcv.parquet")
    oc, oo = R.load_twii_close, R.load_twii_ohlc
    monkeypatch.setattr(R, "load_twii_close", lambda *a, **k: oc(cache_dir=tmp_path, **k))
    monkeypatch.setattr(R, "load_twii_ohlc", lambda *a, **k: oo(cache_dir=tmp_path, **k))
    monkeypatch.setattr(S, "_taipei_today", lambda: today)
    monkeypatch.setattr(allocation_service, "get_macro_regime", lambda **kw: {
        "regime": "bull", "light": "🟢", "source": RA.SOURCE_BULL_SCORE, "trend_regime": None, "health": None,
        "defense": False, "exposure_limit_pct": None, "traffic_light": None, "is_loaded": True,
        "risk_cap_disclosure": None})
    snap = RF.read_real_snapshot()
    k = get_real_page_vm(P4_MARKET, snap).context.kbar
    assert k is not None and k.candles, "端到端：這組資料理應畫出日 K（離群不屬 L0 驗證範圍，屬另案）"
    return k


@pytest.mark.parametrize("closes", [_OUTLIER, _OUTLIER_TINY], ids=["close230", "close1"])
def test_end_to_end_real_parquet_outlier_has_no_negative_axis(tmp_path, monkeypatch, closes):
    k = _e2e_kbar_vm(tmp_path, monkeypatch, closes)
    assert len(k.candles) == 20
    html = H.kbar_chart_html(k)
    _all_numbers_in_svg_are_finite(html)
    assert all(v >= 0 for v, _ in _yaxis(html))
    assert len(_bars(html)) == 20


def test_end_to_end_constant_real_parquet(tmp_path, monkeypatch):
    k = _e2e_kbar_vm(tmp_path, monkeypatch, [22000.0] * 20)
    html = H.kbar_chart_html(k)
    assert all(v >= 0 for v, _ in _yaxis(html)) and len(_bars(html)) == 20
