"""src/ui/render/sector_flow_render.py — 板塊資金泡泡圖繪製(L4 Render).

把 L3 sector_flow_service 的 view['sectors']（bubble_latest.json 座標）畫成 Plotly 泡泡圖:
  X = 近 5 交易日累計淨流入(億,linear 軸,可正可負)   — 資金潮汐
  Y = 動能變化(近 5 日均 − 前 5 日均,億/天,可正可負)  — 加速度
  size = 近 20 交易日淨額規模(億)                        — 泡泡大小
四象限著色 + x=0 / y=0 分界線;使用者持股所在板塊 → 金色外環 + 「你的持股」標註。

§8.2 L4:**純繪圖,零 I/O**,資料由 caller 傳入,不 import streamlit / 不抓資料 / 不算指標。
回 `plotly.graph_objects.Figure`(對齊 chart_plotter.py 慣例),caller(L5)自行 st.plotly_chart。
§1:insufficient(交易日 < 10、Y 不可算)板塊 **不硬塞象限位置**,改以角落標註計數。
§3.3:配色走 shared.colors SSOT;泡泡像素下限/上限為本檔頂具名常數(純呈現參數)。
"""
from __future__ import annotations

import math

import plotly.graph_objects as go

from shared.colors import (
    TRAFFIC_GREEN,
    TRAFFIC_NEUTRAL,
    TRAFFIC_RED,
    TRAFFIC_YELLOW,
)
from shared.sector_flow_thresholds import (
    QUADRANT_EBBING,
    QUADRANT_INSUFFICIENT,
    QUADRANT_RISING,
    QUADRANT_ROTATING,
    QUADRANT_WATCHING,
)

# ── 泡泡像素映射(§3.3 具名下限/上限;面積 ∝ |size_yi| → 半徑 ∝ sqrt)──────────
#: 防 0/負:size 一律取 abs,再以下列像素區間映射(size=0 → 最小泡泡,仍可見)。
_BUBBLE_MIN_PX: float = 9.0
_BUBBLE_MAX_PX: float = 64.0

# ── 配色(§3.3 走 shared.colors SSOT;藍/金為 COLORS_7 同款,無 named 常數故就地標註)──
_QUADRANT_BLUE: str = "#58a6ff"     # = shared.colors.COLORS_7[0];觀望象限(觸底觀察)
_HIGHLIGHT_GOLD: str = "#ffd700"    # = shared.colors.COLORS_7[2];持股外環/標註

#: 象限 → 顏色(台灣慣例 紅漲綠跌,與產業熱力圖一致:紅=最強流入+加速、黃=流入但轉弱、
#: 藍=流出但回升觀察、綠=流出加速)。
_QUADRANT_COLOR: dict = {
    QUADRANT_RISING: TRAFFIC_RED,        # 漲潮:X≥0, Y≥0(紅=資金流入+加速,台灣紅漲)
    QUADRANT_ROTATING: TRAFFIC_YELLOW,   # 輪動:X≥0, Y<0
    QUADRANT_WATCHING: _QUADRANT_BLUE,   # 觀望:X<0, Y≥0
    QUADRANT_EBBING: TRAFFIC_GREEN,      # 退潮:X<0, Y<0(綠=資金流出+加速,台灣綠跌)
    QUADRANT_INSUFFICIENT: TRAFFIC_NEUTRAL,
}
#: 圖例顯示順序 + 每象限一句白話(圖例標明語意,對齊需求)。
_QUADRANT_ORDER: tuple = (
    QUADRANT_RISING, QUADRANT_ROTATING, QUADRANT_WATCHING, QUADRANT_EBBING,
)
_QUADRANT_DESC: dict = {
    QUADRANT_RISING: "淨流入 + 動能增強",
    QUADRANT_ROTATING: "淨流入但動能轉弱",
    QUADRANT_WATCHING: "淨流出但動能回升(觸底觀察)",
    QUADRANT_EBBING: "淨流出且加速",
}


def _is_missing(v) -> bool:
    """None 或 NaN(insufficient 板塊的 y_yi,JSON allow_nan 讀回為 float nan)。"""
    return v is None or (isinstance(v, float) and math.isnan(v))


def _size_px(size_yi, max_abs: float) -> float:
    """|size_yi| → 泡泡像素直徑(面積 ∝ size → 直徑 ∝ sqrt)。max_abs<=0 → 最小值。"""
    s = abs(float(size_yi or 0.0))
    if max_abs <= 0:
        return _BUBBLE_MIN_PX
    return _BUBBLE_MIN_PX + (_BUBBLE_MAX_PX - _BUBBLE_MIN_PX) * math.sqrt(s / max_abs)


def build_sector_flow_figure(sectors, *, highlight_sectors=None,
                             title: str = "🌊 板塊資金潮汐") -> go.Figure:
    """由 sectors(list[dict],bubble_latest.json 的 sectors)建泡泡圖 Figure。

    Args:
        sectors: 每項 = {sector, x_yi, y_yi, size_yi, quadrant, n_days, insufficient}。
        highlight_sectors: 使用者持股所在板塊集合(str);這些板塊加金色外環 + 標註。
        title: 圖標題。

    Returns:
        plotly.graph_objects.Figure(caller 自行 st.plotly_chart)。空/全 insufficient →
        回帶「尚無足夠資料」註解的空圖(不炸)。
    """
    _hl = {str(s).strip() for s in (highlight_sectors or set())}
    rows = list(sectors or [])
    # 可畫者:非 insufficient 且 Y 可算(§1:資料不足不硬塞象限位置)
    plot = [r for r in rows
            if not r.get("insufficient") and not _is_missing(r.get("y_yi"))]
    insuf = [r for r in rows
             if r.get("insufficient") or _is_missing(r.get("y_yi"))]

    fig = go.Figure()

    if not plot:
        fig.add_annotation(
            text="尚無足夠資料可繪製(交易日不足或快取為空)",
            xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False,
            font=dict(size=14, color=TRAFFIC_NEUTRAL),
        )
        fig.update_layout(title=title, height=520)
        return fig

    _max_abs = max((abs(float(r.get("size_yi") or 0.0)) for r in plot), default=0.0)

    # 象限分界線(x=0 / y=0)
    fig.add_hline(y=0, line=dict(color="#888888", width=1, dash="dash"))
    fig.add_vline(x=0, line=dict(color="#888888", width=1, dash="dash"))

    # 每象限一條 trace(圖例分色 + 標名)
    for _q in _QUADRANT_ORDER:
        _pts = [r for r in plot if str(r.get("quadrant")) == _q]
        if not _pts:
            continue
        fig.add_trace(go.Scatter(
            x=[float(r.get("x_yi") or 0.0) for r in _pts],
            y=[float(r.get("y_yi") or 0.0) for r in _pts],
            mode="markers",
            name=f"{_q}（{_QUADRANT_DESC.get(_q, '')}）",
            text=[str(r.get("sector")) for r in _pts],
            marker=dict(
                size=[_size_px(r.get("size_yi"), _max_abs) for r in _pts],
                color=_QUADRANT_COLOR.get(_q, TRAFFIC_NEUTRAL),
                opacity=0.72,
                line=dict(width=1, color="rgba(255,255,255,0.55)"),
            ),
            customdata=[[float(r.get("size_yi") or 0.0),
                         int(r.get("n_days") or 0),
                         str(r.get("quadrant"))] for r in _pts],
            hovertemplate=(
                "<b>%{text}</b><br>"
                "X 近5日累計淨流入：%{x:.1f} 億<br>"
                "Y 動能(近5均−前5均)：%{y:.2f} 億/天<br>"
                "規模(近20日 |淨額|)：%{customdata[0]:.1f} 億<br>"
                "交易日數：%{customdata[1]}<br>"
                "象限：%{customdata[2]}<extra></extra>"
            ),
        ))

    # 持股高亮:金色外環 + 「你的持股」標註(不硬塞;只框已畫出的板塊)
    _hpts = [r for r in plot if str(r.get("sector")).strip() in _hl]
    if _hpts:
        fig.add_trace(go.Scatter(
            x=[float(r.get("x_yi") or 0.0) for r in _hpts],
            y=[float(r.get("y_yi") or 0.0) for r in _hpts],
            mode="markers+text",
            name="⭐ 你的持股",
            text=["你的持股"] * len(_hpts),
            textposition="top center",
            textfont=dict(color=_HIGHLIGHT_GOLD, size=11),
            marker=dict(
                symbol="circle-open",
                size=[_size_px(r.get("size_yi"), _max_abs) + 8 for r in _hpts],
                color="rgba(0,0,0,0)",
                line=dict(width=3, color=_HIGHLIGHT_GOLD),
            ),
            hoverinfo="skip",
        ))

    if insuf:
        fig.add_annotation(
            text=f"🕓 {len(insuf)} 個板塊交易日不足,未列入象限",
            xref="paper", yref="paper", x=0.0, y=1.05, xanchor="left",
            showarrow=False, font=dict(size=11, color=TRAFFIC_NEUTRAL),
        )

    fig.update_layout(
        title=title,
        xaxis=dict(title="← 淨流出　　近 5 交易日累計淨流入(億)　　淨流入 →",
                   type="linear", zeroline=False),
        yaxis=dict(title="← 動能轉弱　　動能變化(億/天)　　動能增強 →", zeroline=False),
        height=560,
        legend=dict(orientation="h", yanchor="bottom", y=-0.30,
                    xanchor="center", x=0.5),
        hovermode="closest",
        margin=dict(l=80, r=30, t=70, b=100),
    )
    return fig
