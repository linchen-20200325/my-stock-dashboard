"""src/ui/tabs/stock_sections/section_chips_20d.py — 籌碼定位 20 日 section(v18.411 U4 Phase 3-Chips20D).

從 tab_stock.py:843-889 抽出。
- 近 20 日外資+投信淨買 / 總成交量 集中度
- 延續性(買超日佔比)
- 動態 signal banner(吸籌 / 倒貨 / 中性)+ 雙 metric 進度條

§8.2 layer:L5 UI Tab section helper(低風險:47 LOC,純展示)。

註:原 comment「_con20/_cty20/_sig20 於 L3203 AI 摘要跨段引用」已 stale —
AI 摘要實際讀 `_xsec["con20"/"cty20"/"sig20"]`(_precompute_xsec 預算),
本 section 自己重算 local _chip20 不影響 AI 路徑。

對外 API:
- render_chips_20d_section(df2, sec_lv_chips) -> None
"""
from __future__ import annotations

import streamlit as st

from shared.colors import TRAFFIC_RED, TRAFFIC_YELLOW
from shared.stock_buckets import section_header_html
from src.services import analyze_20d_chips_from_df


def render_chips_20d_section(df2, sec_lv_chips: dict) -> None:
    """籌碼定位 — 近 20 日外資+投信 vs 總成交量。

    v18.196 直算(df2 已含三大法人欄)— 避免第二次 FinMind API 呼叫。

    Args:
        df2: 股價 DataFrame(含三大法人欄)
        sec_lv_chips: tab_helpers.compute_stock_section_levels 回傳的 chips 等級 dict
    """
    st.markdown('---')
    st.markdown(section_header_html("chips", **sec_lv_chips), unsafe_allow_html=True)
    st.caption('🔰 指標白話：集中度＝大戶（外資+投信）淨買量佔總成交量的比例，正值越高＝大戶默默吸貨（偏多）、'
               '負值＝倒貨；延續性＝最近多少比例的交易日持續買超。資料直接取自下方 K 線的三大法人/成交量。')
    _chip20 = analyze_20d_chips_from_df(df2)
    if _chip20.get('error'):
        st.caption(f'⚫ 籌碼集中度取得失敗：{_chip20["error"]}')
        return
    _sig20  = _chip20['signal']
    _con20  = _chip20['concentration']   # % 集中度
    _cty20  = _chip20['continuity']       # % 延續性
    _days20 = _chip20['days']
    _pos20  = _chip20['pos_days']
    _sig20_c = (TRAFFIC_RED if '吸籌' in _sig20
                else ('#da3633' if '倒貨' in _sig20 else TRAFFIC_YELLOW))
    st.markdown(
        f'<div style="background:#0d1117;border:1px solid {_sig20_c};'
        f'border-radius:8px;padding:10px 14px;margin:6px 0;">'
        f'<span style="font-size:14px;font-weight:900;color:{_sig20_c};">'
        f'{_sig20}</span>'
        f'<span style="font-size:11px;color:#8b949e;margin-left:12px;">'
        f'近 {_days20} 日 | 外+投累計 {_chip20["total_net_k"]:.1f}千張 | '
        f'成交量 {_chip20["total_vol_k"]:.1f}千張</span>'
        f'</div>', unsafe_allow_html=True)
    _g20c1, _g20c2 = st.columns(2)
    with _g20c1:
        st.metric(
            label='指標A：集中度（外+投淨買／總量）',
            value=f'{_con20:+.2f}%',
            delta='吸籌' if _con20 >= 0 else '倒貨',
            delta_color='normal' if _con20 >= 0 else 'inverse',
            help='> +5% 且延續性 > 50% → 大戶吸籌；< -5% → 大戶倒貨')
        st.progress(min(abs(_con20) / 20.0, 1.0),
                    text=f'集中度絕對值 {abs(_con20):.1f}% / 20%上限')
    with _g20c2:
        st.metric(
            label=f'指標B：延續性（{_days20}日中買超 {_pos20} 天）',
            value=f'{_cty20:.0f}%',
            help='> 50% 表示多數交易日外+投持續買超')
        st.progress(_cty20 / 100.0,
                    text=f'買超天數佔比 {_cty20:.0f}%')
