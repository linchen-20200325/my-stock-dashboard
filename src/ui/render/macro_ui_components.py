"""src/ui/render/macro_ui_components.py — 總經 tab 用的 plotly + HTML 渲染元件 (L4 Render)。

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
    # v19.105(第九份 Bug4):API 回傳字串型數字時 pct>0 / abs(pct) 直接 TypeError
    # 炸整張卡。coerce 失敗回 0(中性顯示,§1 不炸不腦補方向)。
    try:
        pct = float(stats.get('pct', 0))
    except (TypeError, ValueError):
        pct = 0.0
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
                '<div style="font-size:10px;color:#484f58;margin-top:4px;">收盤後點「🚀 一鍵更新全部數據」重試</div></div>')
    # v19.105(第九份 Bug4):字串型 margin 比較即 TypeError。coerce 失敗視同
    # 未取得(走 None 卡片,誠實顯示抓取中而非炸卡)。
    try:
        margin = float(margin)
    except (TypeError, ValueError):
        return margin_card(None)
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


def key_alerts_banner(result: dict) -> str:
    """⚡ 今日關鍵橫幅 HTML(v19.108;資料來自 L2 daily_key_alerts,純渲染)。

    - 有異常:紅/黃左框橫條,item 以 chip 併排(hover title=白話 detail)。
    - 無異常:細綠條「今日無異常」— 誠實顯示掃描過而非硬擠內容(§1)。
    """
    items = (result or {}).get('items') or []
    if not items:
        return ('<div style="background:#0d2318;border-left:3px solid '
                f'{TRAFFIC_GREEN};border-radius:0 6px 6px 0;padding:6px 14px;'
                'margin:4px 0 10px 0;">'
                f'<span style="color:{TRAFFIC_GREEN};font-size:12px;">'
                '✅ 今日關鍵：門檻＋急變雙層掃描無異常</span></div>')
    _n_red = (result or {}).get('n_red', 0)
    _bc = TRAFFIC_RED if _n_red else TRAFFIC_YELLOW
    _bg = '#2d1b1b' if _n_red else '#2d2208'
    _chips = ''.join(
        f'<span title="{i.get("detail", "")}" '
        f'style="display:inline-block;background:#161b22;border:1px solid #30363d;'
        f'border-radius:6px;padding:2px 8px;margin:2px 6px 2px 0;font-size:12px;'
        f'color:#e6edf3;cursor:help;">{i.get("emoji", "")} {i.get("text", "")}</span>'
        for i in items)
    return (f'<div style="background:{_bg};border-left:3px solid {_bc};'
            'border-radius:0 6px 6px 0;padding:8px 14px;margin:4px 0 10px 0;">'
            f'<span style="color:{_bc};font-weight:700;font-size:13px;">'
            f'⚡ 今日關鍵（{len(items)} 項）</span><br>{_chips}'
            '<div style="font-size:10px;color:#8b949e;margin-top:2px;">'
            '滑鼠停在項目上看白話說明｜門檻層=總經警示規則命中｜急變層=單期變化超限'
            '</div></div>')


# ════════════════════════════════════════════════════════════════
# 統一指標卡(v19.109,第 5 步試點 — 燈號+俗名+原理+燈義 四要素固定格式)
# band 表收 shared/signal_thresholds SSOT → 判定與燈義文字同源不漂移(§3.3)
# ════════════════════════════════════════════════════════════════

_BAND_HEX: dict = {
    'red': TRAFFIC_RED, 'yellow': TRAFFIC_YELLOW, 'green': TRAFFIC_GREEN,
    'blue': '#58a6ff', 'gray': '#484f58',
}


def resolve_band(value, bands) -> tuple:
    """依 band 表(降冪 lo)取第一個 value >= lo 的 (色鍵, 燈標籤, 燈義)。

    value 非數 → gray「資料異常」(§1 不腦補方向)。
    """
    try:
        _v = float(value)
    except (TypeError, ValueError):
        return ('gray', '⬜ 資料異常', '值非數值,無法判定燈號')
    for lo, color_key, label, meaning in bands:
        if _v >= lo:
            return (color_key, label, meaning)
    return ('gray', '⬜ 資料異常', 'band 表無兜底項')   # bands 末項 -inf 時不會到


def bands_caption(bands, unit: str = '') -> str:
    """band 表 → 一行門檻帶說明,如「🔴≥38｜🟡≥32｜🟢≥23｜🔵≥17｜🔵<17」。

    與 resolve_band 讀同一張表 → 顯示的門檻永遠 = 實際判定門檻。
    """
    parts = []
    prev_lo = None
    for lo, _c, label, _m in bands:
        _emoji = label.split(' ')[0] if label else '⬜'
        if lo == float('-inf'):
            parts.append(f'{_emoji}<{prev_lo:g}{unit}' if prev_lo is not None
                         else f'{_emoji}其他')
        else:
            parts.append(f'{_emoji}≥{lo:g}{unit}')
            prev_lo = lo
    return '｜'.join(parts)


def unified_indicator_card(*, title: str, nickname: str, value_str: str,
                           band: tuple, bands, principle: str,
                           unit: str = '', date: str = '',
                           extra: str = '') -> str:
    """統一指標卡 HTML:燈號+俗名+原理+燈義 四要素固定版位。

    Args:
        title: 指標正式名(卡片主標)。
        nickname: 俗名/白話名(小字前綴,新手第一眼)。
        value_str: 已格式化的當前值字串。
        band: resolve_band 回傳的 (色鍵, 燈標籤, 燈義)。
        bands: band 表(產生門檻帶說明行,與判定同源)。
        principle: 原理一句(這指標怎麼來/量什麼)。
        unit: 門檻帶單位(顯示用)。
        date: 資料日期(可空)。
        extra: 額外一行(如上月趨勢),可空。
    """
    _ck, _label, _meaning = band
    _c = _BAND_HEX.get(_ck, '#484f58')
    _date_html = (f'<span style="color:#484f58;font-size:9px;"> ({date})</span>'
                  if date else '')
    _extra_html = (f'<div style="font-size:10px;color:#8b949e;margin-top:2px;">'
                   f'{extra}</div>' if extra else '')
    return (
        f'<div style="background:#0d1117;border:1px solid #21262d;'
        f'border-left:3px solid {_c};border-radius:8px;padding:10px 12px;margin:2px 0;">'
        f'<div style="font-size:10px;color:#8b949e;">{nickname}</div>'
        f'<div style="font-size:12px;font-weight:700;color:#c9d1d9;">{title}{_date_html}</div>'
        f'<div style="font-size:20px;font-weight:900;color:{_c};margin:2px 0;">{value_str}'
        f' <span style="font-size:11px;font-weight:700;">{_label}</span></div>'
        f'<div style="font-size:11px;color:{_c};">燈義：{_meaning}</div>'
        f'{_extra_html}'
        f'<div style="font-size:10px;color:#8b949e;margin-top:4px;border-top:1px solid #21262d;'
        f'padding-top:3px;">原理：{principle}</div>'
        f'<div style="font-size:9px;color:#484f58;margin-top:2px;">'
        f'門檻帶：{bands_caption(bands, unit)}</div>'
        f'</div>')


def unified_indicator_card_pending(*, title: str, nickname: str,
                                   principle: str, source_note: str = '') -> str:
    """統一指標卡「待取得」灰態(結構同正式卡,§1 誠實顯示未載入)。"""
    _note = (f'<div style="font-size:10px;color:#484f58;margin-top:2px;">'
             f'{source_note}</div>' if source_note else '')
    return (
        f'<div style="background:#0d1117;border:1px solid #21262d;'
        f'border-left:3px solid #484f58;border-radius:8px;padding:10px 12px;'
        f'margin:2px 0;opacity:0.75;">'
        f'<div style="font-size:10px;color:#8b949e;">{nickname}</div>'
        f'<div style="font-size:12px;font-weight:700;color:#c9d1d9;">{title}</div>'
        f'<div style="font-size:20px;font-weight:900;color:#484f58;margin:2px 0;">待取得</div>'
        f'{_note}'
        f'<div style="font-size:10px;color:#8b949e;margin-top:4px;border-top:1px solid #21262d;'
        f'padding-top:3px;">原理：{principle}</div>'
        f'</div>')
