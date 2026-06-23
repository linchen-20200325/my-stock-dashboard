"""美林時鐘景氣循環圖（PMI YoY × CPI YoY）— Stock 端總經快照組件。

四象限邏輯：
    成長（PMI YoY Δ > 0 expand / ≤ 0 contract）  ×
    通膨（CPI YoY > 2.0% rising / ≤ 2.0% falling，2% 為 Fed 目標）

    → 過熱 / 復甦 / 停滯 / 衰退 四象限 + 對應資產配置建議。

資料來源：
- PMI 歷史：FinMind TaiwanEconomicIndicator（透過 tw_macro.fetch_pmi_history,
  v18.243 S-H4 已下沉至 L1 Data,本檔屬 L2 不可直接 import proxy_helper）
- CPI YoY：由呼叫端從 macro_info['us_core_cpi'] 傳入（避免重複抓）

v18.243 S-H4(CLAUDE.md §8.2 修正):原 `fetch_pmi_history` + `_get_finmind_token`
在本檔(L2 Compute)直接 import `proxy_helper`(L1),違反「L2 不得 import
requests/proxy_helper」硬規則。已將 fetcher 下沉至 `tw_macro.py`(L1),本檔
透過 `from tw_macro import fetch_pmi_history` 取資料,token 統一從
`config.FINMIND_TOKEN`(EX-L0-1 例外:已登記 secrets bootstrap)。
"""
from __future__ import annotations
import pandas as pd
from shared.colors import TRAFFIC_GREEN, TRAFFIC_RED, TRAFFIC_YELLOW

# 階段名 → (建議資產, 配色)。配色與既有 GitHub 風格對齊。
_QUADRANT_MAP = {
    ('expand', 'rising'):    ('過熱 Overheat',    '大宗商品 / 能源', TRAFFIC_RED),
    ('expand', 'falling'):   ('復甦 Recovery',    '股票',           TRAFFIC_GREEN),
    ('contract', 'rising'):  ('停滯 Stagflation', '現金 / 黃金',     TRAFFIC_YELLOW),
    ('contract', 'falling'): ('衰退 Recession',   '債券',           '#42a5f5'),
}

# 各階段資產配置建議表（加碼 / 中性 / 減碼）
_ASSET_TABLE: dict[str, dict[str, str]] = {
    '過熱 Overheat': {
        '股票':     '⚖️ 中性（接近循環頂）',
        '債券':     '🔻 減碼（利率走升）',
        '現金':     '⚖️ 中性',
        '大宗商品': '🔺 加碼（通膨受益）',
    },
    '復甦 Recovery': {
        '股票':     '🔺 加碼（最有利環境）',
        '債券':     '⚖️ 中性',
        '現金':     '🔻 減碼',
        '大宗商品': '⚖️ 中性',
    },
    '停滯 Stagflation': {
        '股票':     '🔻 減碼（盈餘收縮）',
        '債券':     '🔻 減碼（殖利率風險）',
        '現金':     '🔺 加碼（避險）',
        '大宗商品': '🔺 加碼（黃金/能源避通膨）',
    },
    '衰退 Recession': {
        '股票':     '🔻 減碼（盈餘下修）',
        '債券':     '🔺 加碼（降息受益）',
        '現金':     '⚖️ 中性',
        '大宗商品': '🔻 減碼（需求疲弱）',
    },
}

# 通膨基準（Fed 目標 2%；高於此視為 rising）
_CPI_THRESHOLD = 2.0


# S-H4 v18.243:`fetch_pmi_history` + `_get_finmind_token` 已下沉至 `tw_macro.py`(L1)。
# 本檔僅做純函式計算 + UI render,符合 L2 Compute / L4 Render 邊界。


def compute_clock_state(pmi_yoy_chg: float, cpi_yoy: float) -> dict:
    """依 PMI YoY 變化（points）+ CPI YoY（%）定四象限。

    Parameters
    ----------
    pmi_yoy_chg : float
        PMI 今值 - 12 個月前值（points，正號=成長加速）。
    cpi_yoy : float
        CPI 同比變化率（%，正號=通膨上升）。

    Returns
    -------
    dict
      {'phase', 'asset_keynote', 'color',
       'growth_dir', 'infl_dir',
       'pmi_yoy_chg', 'cpi_yoy'}
    """
    _growth = 'expand' if pmi_yoy_chg > 0 else 'contract'
    _infl = 'rising' if cpi_yoy > _CPI_THRESHOLD else 'falling'
    _phase, _asset, _color = _QUADRANT_MAP[(_growth, _infl)]
    return {
        'phase': _phase,
        'asset_keynote': _asset,
        'color': _color,
        'growth_dir': _growth,
        'infl_dir': _infl,
        'pmi_yoy_chg': round(pmi_yoy_chg, 2),
        'cpi_yoy': round(cpi_yoy, 2),
    }


def _build_quadrant_fig(pmi_yoy_chg: float, cpi_yoy: float, state: dict):
    """plotly 4 象限散布圖；x = PMI YoY Δ、y = CPI YoY。"""
    import plotly.graph_objects as _go
    _fig = _go.Figure()
    # 四象限填色（淡）
    _ranges = max(abs(pmi_yoy_chg) * 1.5, 5)
    _y_lo, _y_hi = max(0, cpi_yoy - 3), max(cpi_yoy + 3, _CPI_THRESHOLD + 2)
    _shapes = [
        # 過熱：x>0, y>2
        dict(type='rect', x0=0, x1=_ranges, y0=_CPI_THRESHOLD, y1=_y_hi,
             fillcolor='rgba(248,81,73,0.12)', line_width=0),
        # 復甦：x>0, y<=2
        dict(type='rect', x0=0, x1=_ranges, y0=_y_lo, y1=_CPI_THRESHOLD,
             fillcolor='rgba(63,185,80,0.12)', line_width=0),
        # 停滯：x<=0, y>2
        dict(type='rect', x0=-_ranges, x1=0, y0=_CPI_THRESHOLD, y1=_y_hi,
             fillcolor='rgba(210,153,34,0.12)', line_width=0),
        # 衰退：x<=0, y<=2
        dict(type='rect', x0=-_ranges, x1=0, y0=_y_lo, y1=_CPI_THRESHOLD,
             fillcolor='rgba(66,165,245,0.12)', line_width=0),
    ]
    # 軸十字線
    _shapes += [
        dict(type='line', x0=0, x1=0, y0=_y_lo, y1=_y_hi,
             line=dict(color='#6e7681', width=1, dash='dash')),
        dict(type='line', x0=-_ranges, x1=_ranges, y0=_CPI_THRESHOLD, y1=_CPI_THRESHOLD,
             line=dict(color='#6e7681', width=1, dash='dash')),
    ]
    # 當前位置紅點
    _fig.add_trace(_go.Scatter(
        x=[pmi_yoy_chg], y=[cpi_yoy], mode='markers+text',
        marker=dict(size=18, color=state['color'], line=dict(color='white', width=2)),
        text=[f"  ◀ 當前：{state['phase']}"],
        textposition='middle right', textfont=dict(color=state['color'], size=12),
        hovertemplate=(f"PMI YoY Δ: {pmi_yoy_chg:+.2f} pts<br>"
                       f"CPI YoY: {cpi_yoy:+.2f}%<extra></extra>"),
        showlegend=False,
    ))
    # 四象限標籤
    _labels = [
        (_ranges * 0.6, _y_hi * 0.85, '過熱', TRAFFIC_RED),
        (_ranges * 0.6, _y_lo + (_CPI_THRESHOLD - _y_lo) * 0.3, '復甦', TRAFFIC_GREEN),
        (-_ranges * 0.6, _y_hi * 0.85, '停滯', TRAFFIC_YELLOW),
        (-_ranges * 0.6, _y_lo + (_CPI_THRESHOLD - _y_lo) * 0.3, '衰退', '#42a5f5'),
    ]
    for _x, _y, _name, _c in _labels:
        _fig.add_annotation(x=_x, y=_y, text=f'<b>{_name}</b>',
                            showarrow=False,
                            font=dict(color=_c, size=13))
    _fig.update_layout(
        shapes=_shapes,
        xaxis=dict(title='PMI YoY Δ（points，成長動能）', range=[-_ranges, _ranges],
                   gridcolor='#21262d'),
        yaxis=dict(title='CPI YoY %（通膨壓力）', range=[_y_lo, _y_hi],
                   gridcolor='#21262d'),
        height=380, margin=dict(l=50, r=20, t=20, b=50),
        paper_bgcolor='#0d1117', plot_bgcolor='#0d1117',
        font=dict(color='#e6edf3'),
    )
    return _fig


def render_merrill_clock(pmi_now: float | None, cpi_yoy: float | None):
    """主 entry：UI 渲染（plotly 圖 + 資產配置表）。

    呼叫端傳入當期 PMI 與當期 CPI YoY；本模組負責抓 PMI 歷史算 YoY。
    """
    import streamlit as _st
    from tw_macro import fetch_pmi_history as _fetch_pmi_history_l1
    from config import FINMIND_TOKEN as _FINMIND_TOKEN
    if pmi_now is None or cpi_yoy is None:
        _st.caption('⚪ 美林時鐘：缺 PMI 或 CPI 當期值，跳過')
        return
    _hist = _fetch_pmi_history_l1(months=18, token=_FINMIND_TOKEN)
    if _hist is None or len(_hist) < 13:
        _st.caption(f'⚪ 美林時鐘：PMI 歷史不足 12+ 月（目前 {len(_hist) if _hist is not None else 0}），跳過')
        return
    try:
        _pmi_12m = float(_hist['value'].iloc[-13])
        _pmi_chg = float(pmi_now) - _pmi_12m
    except Exception as _e:
        _st.caption(f'⚪ 美林時鐘：YoY 計算失敗（{type(_e).__name__}）')
        return
    _state = compute_clock_state(_pmi_chg, float(cpi_yoy))
    _st.markdown(f"#### ⛰️ 美林時鐘景氣循環　"
                 f"<span style='color:{_state['color']};font-weight:700'>"
                 f"{_state['phase']}</span>　"
                 f"<span style='color:#8b949e;font-size:12px'>建議重點：{_state['asset_keynote']}</span>",
                 unsafe_allow_html=True)
    with _st.expander('💡 美林時鐘怎麼看？（景氣四象限 × 資產輪動）', expanded=False):
        _st.markdown(
            '美林投資時鐘用兩個軸把景氣分成四階段，**不同階段該重押不同資產**：\n\n'
            '- **橫軸＝景氣動能（PMI YoY 變化）**：右邊＝景氣加速、左邊＝放緩。\n'
            '- **縱軸＝通膨（CPI YoY）**：上面＝通膨升、下面＝通膨降。\n\n'
            '| 象限 | 情境 | 偏強資產 |\n'
            '|---|---|---|\n'
            '| 🟢 復甦（動能↑·通膨↓）| 景氣回溫、利率仍低 | **股票（成長/科技）** |\n'
            '| 🔴 過熱（動能↑·通膨↑）| 景氣旺但通膨燙 | 原物料、能源、抗通膨 |\n'
            '| 🟠 停滯（動能↓·通膨↑）| 景氣降溫但物價高 | 現金、短債（防禦）|\n'
            '| 🔵 衰退（動能↓·通膨↓）| 景氣與物價齊跌 | **債券（長天期）** |\n\n'
            '🎯 用法：先看圓點落在哪一象限 → 對照下方資產配置表加減碼；'
            '再搭配 NDC 景氣燈號與旌旗指數綜合判斷，避免單一指標誤判。'
        )
    _fig = _build_quadrant_fig(_pmi_chg, float(cpi_yoy), _state)
    _st.plotly_chart(_fig, use_container_width=True)
    # 資產配置表
    _rows = [{'資產': _k, '建議': _v}
             for _k, _v in _ASSET_TABLE[_state['phase']].items()]
    _st.dataframe(pd.DataFrame(_rows), use_container_width=True, hide_index=True)
    _st.caption(f"📍 軸：PMI YoY Δ {_pmi_chg:+.2f} pts ｜ CPI YoY {cpi_yoy:+.2f}%　｜　"
                f"基準：通膨閾值 {_CPI_THRESHOLD}%（Fed 目標）。"
                f"資產配置僅參考，實際應結合 NDC 燈號與旌旗指數綜合判斷。")
