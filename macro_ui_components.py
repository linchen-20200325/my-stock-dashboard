"""macro_ui_components.py — 總經 tab 用的 plotly + HTML 渲染元件 (L4 Render)。

v18.344 PR-N1 從 daily_checklist.py 抽出純 UI 元件部分:
- _hex2rgba / _base_layout: plotly 配色/版型 helper
- sparkline / multi_chart / bar_chart_institutional: plotly 圖表 builder
- stat_card / margin_card / section_header: HTML string builder

§8.2 L4 Render 層,**不**得直呼 L1 fetch / 不寫 session_state。
只純函式 in→out,UI 配色從 shared.colors / shared.signal_thresholds SSOT 取。
"""
from __future__ import annotations

import plotly.graph_objects as go

from shared.colors import TRAFFIC_GREEN, TRAFFIC_RED, TRAFFIC_YELLOW
from shared.signal_thresholds import (
    MARGIN_BALANCE_OVERHEAT_THRESHOLD_YI,
    MARGIN_BALANCE_WARN_THRESHOLD_YI,
)


COLORS_7 = [
    "#58a6ff", TRAFFIC_GREEN, "#ffd700", TRAFFIC_RED,
    "#bc8cff", "#79c0ff", "#ff9f43",
]


def _hex2rgba(color, alpha=0.12):
    try:
        c = color.lstrip('#')
        r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
        return f"rgba({r},{g},{b},{alpha})"
    except Exception:
        return "rgba(88,166,255,0.12)"


def _base_layout(title: str = "", height: int = 260):
    return dict(
        title=dict(text=title, font=dict(color="#8b949e", size=12)),
        height=height, plot_bgcolor="#0e1117", paper_bgcolor="#0e1117",
        font=dict(color="#e6edf3", size=11),
        margin=dict(l=8, r=8, t=35, b=20),
        xaxis=dict(gridcolor="#21262d", showgrid=True, zeroline=False),
        yaxis=dict(gridcolor="#21262d", showgrid=True, zeroline=False),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=10)),
    )


def sparkline(df, title: str = "", color: str = "#58a6ff"):
    col = next((c for c in ['close', 'Close'] if c in df.columns), None)
    if col is None:
        return go.Figure()
    s = df[col].dropna().tail(45)
    fig = go.Figure(go.Scatter(
        x=list(s.index), y=list(s.values), mode='lines',
        line=dict(color=color, width=2), fill='tozeroy',
        fillcolor=_hex2rgba(color) if color.startswith('#') else color,
    ))
    fig.update_layout(**_base_layout(title, 200))
    return fig


def multi_chart(data_dict, title: str = "", norm: bool = False, height: int = 250):
    fig = go.Figure()
    for i, (name, df) in enumerate(data_dict.items()):
        col = next((c for c in ['close', 'Close'] if c in df.columns), None)
        if col is None:
            continue
        s = df[col].dropna().tail(45)
        y = (s / s.iloc[0] * 100).round(2) if (norm and len(s) > 0) else s
        fig.add_trace(go.Scatter(
            x=list(s.index), y=list(y.values), mode='lines', name=name,
            line=dict(color=COLORS_7[i % len(COLORS_7)], width=2),
        ))
    fig.update_layout(**_base_layout(title, height))
    return fig


def bar_chart_institutional(inst_dict, title: str = "三大法人買賣超（堆疊柱狀圖）", height: int = 300):
    """升級版:堆疊柱狀圖(三大法人各自一欄,顏色區分)。"""
    _inst_keys = ['外資', '投信', '自營商']
    _inst_colors = {'外資': '#58a6ff', '投信': TRAFFIC_GREEN, '自營商': '#bc8cff'}
    _data_by = {k: 0.0 for k in _inst_keys}
    if inst_dict and isinstance(inst_dict, dict):
        for _name, _val in inst_dict.items():
            if '合計' in _name:
                continue
            if not isinstance(_val, dict):
                continue
            _matched = next((k for k in _inst_keys if k in str(_name)), None)
            if _matched:
                try:
                    _data_by[_matched] = float(_val.get('net', 0) or 0)
                except (ValueError, TypeError) as _e_inst:
                    print(f"[macro_ui inst-flow] {_matched} net 解析失敗:{_e_inst}")
    fig = go.Figure()
    for _ik in _inst_keys:
        _v = float(_data_by.get(_ik, 0.0))
        _c = '#da3633' if _v > 0 else ('#2ea043' if _v < 0 else '#388bfd')
        fig.add_trace(go.Bar(
            name=_ik, x=[_ik], y=[_v],
            marker_color=_inst_colors.get(_ik, _c),
            text=[f'{_v:+.1f}億'],
            textposition='outside',
            cliponaxis=False,
            opacity=0.9,
        ))
    _total = sum(float(v) for v in _data_by.values())
    _all_zero = all(v == 0.0 for v in _data_by.values())
    _layout = _base_layout(title, height)
    _layout.update({
        'barmode': 'group',
        'showlegend': True,
        'legend': {'orientation': 'h', 'y': 1.08, 'font': {'size': 10, 'color': '#8b949e'}},
        'shapes': [{'type': 'line', 'x0': -0.5, 'x1': 2.5, 'y0': 0, 'y1': 0,
                    'line': {'color': '#484f58', 'width': 1, 'dash': 'dot'}}],
        'annotations': [{'text': f'合計: {_total:+.1f}億',
                         'xref': 'paper', 'yref': 'paper', 'x': 0.98, 'y': 0.95,
                         'showarrow': False,
                         'font': {'size': 12,
                                  'color': '#da3633' if _total > 0
                                  else ('#2ea043' if _total < 0 else '#388bfd')}}],
    })
    if _all_zero:
        for _ik in _inst_keys:
            fig.add_trace(go.Bar(
                name=_ik, x=[_ik], y=[0.001],
                marker_color='#21262d', opacity=0.3,
                showlegend=False,
            ))
        _layout['annotations'] = [{
            'text': '⚠️ 資料待更新（收盤後 15:30 取得）',
            'xref': 'paper', 'yref': 'paper', 'x': 0.5, 'y': 0.5,
            'showarrow': False, 'font': {'size': 13, 'color': TRAFFIC_YELLOW},
        }]
    fig.update_layout(**_layout)
    return fig


def stat_card(name: str, stats, unit: str = "", has_data: bool = True):
    if not has_data or stats is None:
        return (f'<div style="background:#161b22;border:1px solid #21262d;border-radius:8px;'
                f'padding:12px;text-align:center;opacity:0.5;">'
                f'<div style="font-size:10px;color:#484f58;">{name}</div>'
                f'<div style="font-size:13px;color:#484f58;">載入中...</div></div>')
    pct = stats.get('pct', 0)
    pc = '#da3633' if pct > 0 else ('#2ea043' if pct < 0 else '#388bfd')
    arrow = '▲' if pct > 0 else ('▼' if pct < 0 else '─')
    return (f'<div style="background:#161b22;border:1px solid #21262d;border-radius:8px;'
            f'padding:12px;text-align:center;">'
            f'<div style="font-size:10px;color:#484f58;">{name}</div>'
            f'<div style="font-size:18px;font-weight:900;color:#e6edf3;">{stats.get("last","?")} '
            f'<span style="font-size:10px;color:#8b949e;">{unit}</span></div>'
            f'<div style="font-size:12px;font-weight:700;color:{pc};">{arrow} {abs(pct):.2f}%</div>'
            f'<div style="font-size:10px;color:#484f58;">{stats.get("status","")}</div></div>')


def margin_card(margin):
    if margin is None:
        return ('<div style="background:#161b22;border:1px solid #21262d;border-radius:8px;padding:14px;">'
                '<div style="font-size:11px;color:#484f58;">融資餘額</div>'
                f'<div style="font-size:12px;color:{TRAFFIC_YELLOW};margin-top:6px;">⏳ 抓取中（TWSE 15:30後更新）</div>'
                '<div style="font-size:10px;color:#484f58;margin-top:4px;">收盤後點「更新全部總經數據」重試</div></div>')
    mc = (TRAFFIC_RED if margin > MARGIN_BALANCE_OVERHEAT_THRESHOLD_YI
          else (TRAFFIC_YELLOW if margin > MARGIN_BALANCE_WARN_THRESHOLD_YI else TRAFFIC_GREEN))
    label = ('🔴超過3400億高危' if margin > MARGIN_BALANCE_OVERHEAT_THRESHOLD_YI
             else ('⚡超過2500億警戒' if margin > MARGIN_BALANCE_WARN_THRESHOLD_YI
                   else '✅安全水位'))
    return (f'<div style="background:#161b22;border:1px solid #21262d;border-radius:8px;padding:14px;">'
            f'<div style="font-size:11px;color:#484f58;">融資餘額</div>'
            f'<div style="font-size:28px;font-weight:900;color:{mc};">{margin:.0f}'
            f'<span style="font-size:12px;">億</span></div>'
            f'<div style="font-size:10px;color:#8b949e;">{label}</div></div>')


def section_header(num, title: str, icon: str = ""):
    return (f'<div style="background:linear-gradient(90deg,#161b22,transparent);'
            f'border-left:3px solid #1f6feb;border-radius:0 6px 6px 0;'
            f'padding:8px 14px;margin:16px 0 10px 0;">'
            f'<span style="color:#1f6feb;font-weight:700;">{icon} {num}、{title}</span></div>')
