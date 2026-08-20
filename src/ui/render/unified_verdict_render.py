"""src/ui/render/unified_verdict_render.py — 統一裁決徽章 HTML(L4 render,v19.201)。

把 L2 `UnifiedVerdict` 渲染成「統一三態徽章 + 各軸並陳 + 背離加註 + 估值/總經並陳」的
HTML 字串。純字串建構、零 streamlit、零 I/O → 可 golden test。

§設計「新增不取代」:本徽章是**額外**一塊,不取代各 tab 既有的原生裁決顯示。
"""
from __future__ import annotations

from shared.colors import (
    TRAFFIC_GREEN,
    TRAFFIC_NEUTRAL,
    TRAFFIC_RED,
    TRAFFIC_YELLOW,
)
from shared.unified_verdict_thresholds import (
    VERDICT_CUT,
    VERDICT_KEEP,
    VERDICT_NA,
    VERDICT_WATCH,
)
from src.compute.scoring.unified_verdict import UnifiedVerdict

_VERDICT_COLOR = {
    VERDICT_KEEP: TRAFFIC_GREEN,
    VERDICT_WATCH: TRAFFIC_YELLOW,
    VERDICT_CUT: TRAFFIC_RED,
    VERDICT_NA: TRAFFIC_NEUTRAL,
}
_STATE_ICON = {
    VERDICT_KEEP: '🟢',
    VERDICT_WATCH: '🟡',
    VERDICT_CUT: '🔴',
    None: '⚪',
}


def _fmt_value(val) -> str:
    """軸原值格式化:float→2 位、其餘→str(grade/int 原樣)。"""
    if isinstance(val, float):
        return f'{val:.2f}'
    return str(val)


def render_unified_verdict_html(v: UnifiedVerdict, *, title: str = '🧭 統一裁決') -> str:
    """UnifiedVerdict → 徽章 HTML 字串(dark theme,對齊既有卡片風格)。"""
    color = _VERDICT_COLOR.get(v.verdict, TRAFFIC_NEUTRAL)

    # 各軸並陳(主軸標(主))
    _axis_bits = []
    for a in v.axes:
        _icon = _STATE_ICON.get(a.get('state'), '⚪')
        _tag = '（主）' if a.get('is_primary') else ''
        _axis_bits.append(
            f'<span style="color:#c9d1d9;">{a["name"]} '
            f'<b>{_fmt_value(a["value"])}</b>{_icon}{_tag}</span>')
    _axes_html = ' · '.join(_axis_bits) if _axis_bits else '（無可並陳軸）'

    # 背離加註
    _div_html = (
        f'<div style="font-size:11px;color:{TRAFFIC_YELLOW};margin-top:4px;">'
        f'⚠️ 背離：{v.divergence}</div>' if v.divergence else '')

    # 估值(獨立軸)
    _val_html = (
        f'<span style="color:#8b949e;">｜估值 {v.valuation_label}（獨立軸,不改三態）</span>'
        if v.valuation_label else '')

    # 總經 context(並陳)
    _macro_html = ''
    if v.macro_ctx:
        _reg = v.macro_ctx.get('regime') or v.macro_ctx.get('light') or ''
        if _reg:
            _macro_html = f'<span style="color:#8b949e;">｜總經 {_reg}（context）</span>'

    # coverage 提示(缺軸誠實揭露)
    _cov_html = ''
    if v.verdict == VERDICT_NA:
        _cov_html = ('<div style="font-size:10px;color:#8b949e;margin-top:4px;">'
                     '主軸資料不足,無法評分（§1 不腦補）</div>')

    return (
        f'<div style="background:{color}12;border:1px solid {color};border-left:4px solid {color};'
        f'border-radius:8px;padding:12px 14px;margin:8px 0;">'
        f'<div style="display:flex;align-items:center;gap:10px;">'
        f'<span style="font-size:13px;font-weight:800;color:#8b949e;">{title}</span>'
        f'<span style="font-size:16px;font-weight:900;color:{color};">{v.label}</span>'
        f'</div>'
        f'<div style="font-size:12px;margin-top:6px;">{_axes_html}{_val_html}{_macro_html}</div>'
        f'{_div_html}{_cov_html}'
        f'</div>')
