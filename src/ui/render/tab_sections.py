"""src/ui/render/tab_sections.py — L4 通用 UI section helper(U2 v18.401).

收 tab_stock.py / tab_macro.py 等散落的 inline HTML 樣式 pattern。
所有 helper 都回 HTML 字串(caller 用 `st.markdown(..., unsafe_allow_html=True)`),
或直接接 `streamlit.markdown` 注入(視 helper 而定,有標 docstring)。

§8.2 layer:L4 Render — 純樣式產出,無業務邏輯,無 I/O。

對外 API:
- `box_wrapper_open(theme='neutral', padding=10) -> str`:容器框開頭 HTML
- `box_wrapper_close() -> str`:容器框收尾 HTML(`</div>`)
- `section_header(title, subtitle='', emoji='') -> str`:H3 標題列(統一風格)
- `alert_box(level, title, text) -> str`:警示框(border-left + 圖示)
- `traffic_light_card(label, color, value='') -> str`:紅綠燈卡片

色票來源:`shared.colors` SSOT(TRAFFIC_*)
"""
from __future__ import annotations

from typing import Literal

# 色票 SSOT — 對齊現有 shared/colors.py
_BOX_THEMES = {
    'neutral':   {'bg': '#0d1117', 'border': '#21262d', 'radius': 8},
    'primary':   {'bg': '#0a1628', 'border': '#1f6feb', 'radius': 10},
    'success':   {'bg': '#0d2818', 'border': '#2ea043', 'radius': 8},
    'warning':   {'bg': '#2d1f00', 'border': '#d29922', 'radius': 8},
    'error':     {'bg': '#2d0a14', 'border': '#f85149', 'radius': 8},
}

_ALERT_ICONS = {
    'info':    'ℹ️',
    'warning': '⚠️',
    'error':   '🔴',
    'success': '✅',
}

_ALERT_BORDER_COLORS = {
    'info':    '#1f6feb',
    'warning': '#d29922',
    'error':   '#f85149',
    'success': '#2ea043',
}

BoxTheme = Literal['neutral', 'primary', 'success', 'warning', 'error']
AlertLevel = Literal['info', 'warning', 'error', 'success']


def box_wrapper_open(theme: BoxTheme = 'neutral', padding: int = 10) -> str:
    """容器框開頭 HTML — 統一 tab_stock 散落的 `<div style="background...">` pattern。

    Args:
        theme: 主題色(預設 neutral 深灰)
        padding: 內距 px(預設 10)

    Returns:
        `<div style="...">` HTML 字串(caller 自行 `st.markdown(unsafe_allow_html=True)`)

    用法:
        st.markdown(box_wrapper_open('primary'), unsafe_allow_html=True)
        # ... content ...
        st.markdown(box_wrapper_close(), unsafe_allow_html=True)
    """
    _t = _BOX_THEMES.get(theme, _BOX_THEMES['neutral'])
    return (
        f'<div style="background:{_t["bg"]};border:1px solid {_t["border"]};'
        f'border-radius:{_t["radius"]}px;padding:{padding}px;">'
    )


def box_wrapper_close() -> str:
    """容器框收尾 HTML。"""
    return '</div>'


def section_header(title: str, subtitle: str = '', emoji: str = '') -> str:
    """H3 標題列(統一風格,取代各檔自定 `### xxx` 樣式)。

    Args:
        title: 主標題文字
        subtitle: 副標(灰色小字,可選)
        emoji: 前綴 emoji(可選)

    Returns:
        Markdown / HTML 混合字串(caller 用 st.markdown(unsafe_allow_html=True))
    """
    _prefix = f'{emoji} ' if emoji else ''
    _sub_html = (
        f'<div style="font-size:12px;color:#8b949e;margin-top:2px;">{subtitle}</div>'
        if subtitle else ''
    )
    return (
        f'<div style="margin:12px 0 8px;">'
        f'<div style="font-size:18px;font-weight:700;color:#c9d1d9;">{_prefix}{title}</div>'
        f'{_sub_html}'
        f'</div>'
    )


def alert_box(level: AlertLevel, title: str, text: str = '') -> str:
    """警示框(border-left 4px + icon + 標題 + 內文)。

    Args:
        level: 'info' / 'warning' / 'error' / 'success'
        title: 標題文字
        text: 內文(可空,留標題版)

    Returns:
        HTML 字串(caller 用 st.markdown(unsafe_allow_html=True))
    """
    _icon = _ALERT_ICONS.get(level, 'ℹ️')
    _border = _ALERT_BORDER_COLORS.get(level, '#1f6feb')
    _body_html = (
        f'<div style="font-size:13px;color:#c9d1d9;margin-top:4px;">{text}</div>'
        if text else ''
    )
    return (
        f'<div style="background:#161b22;border-left:4px solid {_border};'
        f'border-radius:4px;padding:10px 12px;margin:8px 0;">'
        f'<div style="font-size:14px;font-weight:600;color:#c9d1d9;">'
        f'{_icon} {title}</div>'
        f'{_body_html}'
        f'</div>'
    )


def border_left_banner(color: str, text: str, *,
                       border_width: int = 3, font_size: int = 12,
                       padding_y: int = 8, padding_x: int = 12,
                       margin_y: int = 4, bold: bool = False,
                       bg: str = '#0d1117') -> str:
    """色帶 banner(border-left N px + 圓角右側 + 內距文字),取代 tab_stock.py
    L900/L1503/L1627 重複的 `<div style="border-left:Npx solid {color};...">` pattern。

    Args:
        color: border 色 + 文字色(對齊 traffic light:TRAFFIC_RED/YELLOW/GREEN)
        text: 內文(HTML 字串,caller 可含 <b>/<span> 等子標籤)
        border_width: 左 border 寬 px(預設 3)
        font_size: 文字大小 px(預設 12)
        padding_y / padding_x: 內距 px(預設 8/12)
        margin_y: 外距 px(預設 4)
        bold: True → font-weight:700(預設 False)
        bg: 背景色(預設 #0d1117 深灰)

    Returns:
        HTML 字串(caller 用 `st.markdown(unsafe_allow_html=True)`)
    """
    _weight = ';font-weight:700' if bold else ''
    return (
        f'<div style="border-left:{border_width}px solid {color};'
        f'padding:{padding_y}px {padding_x}px;background:{bg};'
        f'border-radius:0 6px 6px 0;font-size:{font_size}px;color:{color};'
        f'margin:{margin_y}px 0{_weight};">{text}</div>'
    )


def traffic_light_card(label: str, color: str, value: str = '') -> str:
    """紅綠燈卡片(取代各檔自定 traffic light 樣式)。

    Args:
        label: 標籤(如「短線」/「中線」)
        color: 燈號色(直接吃 shared.colors.TRAFFIC_* 值,或 HEX)
        value: 卡內主值文字(可選)

    Returns:
        HTML 字串(caller 用 st.markdown(unsafe_allow_html=True))
    """
    _value_html = (
        f'<div style="font-size:20px;font-weight:900;color:{color};">{value}</div>'
        if value else ''
    )
    return (
        f'<div style="background:#0d1117;border:1px solid {color};border-radius:8px;'
        f'padding:8px;text-align:center;">'
        f'<div style="font-size:11px;color:#8b949e;margin-bottom:4px;">{label}</div>'
        f'{_value_html}'
        f'</div>'
    )
