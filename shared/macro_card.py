"""shared/macro_card.py — 總經指標純函式 utility(L0 shared)。

P1-4a v18.377 深層拔毒:
- 移除 streamlit import(L0 不該綁 UI lifecycle)
- 刪 6 個 0-caller dead fn(render_macro_card / render_macro_card_grid /
  build_cards_from_indicators / _esc / render_edu_markdown / _z_color)
- 留 caller(src/ui/tabs/tab_edu.py:158)實際用的 2 個 fn:
  - calc_z_score:純 z-score 計算
  - make_sparkline:Plotly Figure(plotly 是視覺化 lib,L0 可用,非 UI lifecycle)
"""
from __future__ import annotations

import plotly.graph_objects as go

from shared.colors import MATERIAL_GREEN, MATERIAL_ORANGE, MATERIAL_RED


def calc_z_score(series, current_value=None) -> float | None:
    """計算當前值的 z-score(相對於 series 的均值/標準差)。

    series 為 list / pd.Series;< 5 筆或 std=0 回 None。
    current_value 預設取 series 最後一筆。
    """
    if series is None:
        return None
    try:
        vals = [float(v) for v in series if v is not None]
    except (TypeError, ValueError):
        return None
    if len(vals) < 5:
        return None
    cur = float(current_value) if current_value is not None else vals[-1]
    mean = sum(vals) / len(vals)
    var = sum((v - mean) ** 2 for v in vals) / len(vals)
    std = var ** 0.5
    if std == 0:
        return None
    return (cur - mean) / std


def make_sparkline(
    values,
    dates=None,
    height: int = 80,
    line_color: str = MATERIAL_GREEN,
    threshold_warn: float | None = None,
    threshold_crit: float | None = None,
):
    """產生迷你 sparkline plotly Figure。

    threshold_warn/crit:選填水平線(警戒 MATERIAL_ORANGE / 嚴重 MATERIAL_RED)。
    """
    fig = go.Figure()
    _xs = dates if dates is not None else list(range(len(values)))
    fig.add_trace(go.Scatter(
        x=_xs, y=values, mode='lines',
        line=dict(color=line_color, width=2),
        showlegend=False, hoverinfo='skip',
    ))
    if values:
        fig.add_trace(go.Scatter(
            x=[_xs[-1]], y=[values[-1]], mode='markers',
            marker=dict(color=line_color, size=5),
            showlegend=False, hoverinfo='skip',
        ))
    if threshold_warn is not None:
        fig.add_hline(y=threshold_warn, line_dash="dot",
                      line_color=MATERIAL_ORANGE, line_width=1, opacity=0.6)
    if threshold_crit is not None:
        fig.add_hline(y=threshold_crit, line_dash="dash",
                      line_color=MATERIAL_RED, line_width=1, opacity=0.7)
    fig.update_layout(
        height=height,
        margin=dict(l=0, r=0, t=0, b=0),
        xaxis=dict(visible=False, fixedrange=True),
        yaxis=dict(visible=False, fixedrange=True),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        showlegend=False,
    )
    return fig
