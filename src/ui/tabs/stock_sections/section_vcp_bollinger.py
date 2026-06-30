"""src/ui/tabs/stock_sections/section_vcp_bollinger.py — E. VCP+布林 section(v18.409 U4 Phase 3-E).

從 tab_stock.py:1067-1149 抽出。
- VCP 型態結論 + 卡片(Mark Minervini 波幅收縮)
- 布林通道卡片(策略 3,4 KPI:現價/上軌/帶寬/下軌 + 條件 signal_box)
- VCP+布林 動態建議 banner + 安全結論

§8.2 layer:L5 UI Tab section helper(中風險:83 LOC + signal_box / kpi 組合)。

對外 API:
- render_vcp_bollinger_section(sid2, vcp2, bb2) -> None
"""
from __future__ import annotations

import streamlit as st

from shared.colors import TRAFFIC_GREEN, TRAFFIC_RED, TRAFFIC_YELLOW
from shared.signal_thresholds import (  # Phase 2 Batch 5b v18.429:布林帶寬收縮 2-tier SSOT
    BB_BW_SHRINK_ACTION_RATIO,
    BB_BW_SHRINK_WARN_RATIO,
)
from src.ui.render import kpi, signal_box, teacher_conclusion
from src.ui.render.tab_sections import border_left_banner


def render_vcp_bollinger_section(sid2: str, vcp2, bb2) -> None:
    """E. VCP 波幅收縮 + 布林通道。

    Args:
        sid2: 股票代碼
        vcp2: VCP dict(swings / contracting)或 None
        bb2: Bollinger dict(price / upper / lower / bw / bw_mean / near_upper)或 None
    """
    # ══ E. VCP + 布林 ══════════════════════════════════════
    st.markdown('---')
    st.markdown('#### 🎯 E. VCP波幅收縮 + 布林通道')
    st.caption('🔰 指標白話：VCP＝股價波動一波比一波小（像彈簧壓緊），常是噴出前的整理；'
               '布林通道＝股價的上下軌道，帶寬收縮代表變盤在即、股價貼上軌偏強。')
    if vcp2 and vcp2.get('contracting'):
        _sw = vcp2.get('swings', [])
        _ea = f'VCP確認收縮（{len(_sw)}波段），量能萎縮，等待帶量突破進場'
        _eb = '突破前高且放量時買入，停損設前波低點'
    elif vcp2:
        _sw = vcp2.get('swings', [])
        _ea = f'VCP尚未形成（{len(_sw)}波段），波動仍大，不宜進場'
        _eb = '等待更多整理時間，耐心等候'
    else:
        _ea = '數據不足，VCP無法計算（需至少30日價格資料）'
        _eb = ''
    st.markdown(teacher_conclusion('朱家泓', f'{sid2} VCP型態', _ea, _eb),
                unsafe_allow_html=True)
    ec1, ec2 = st.columns(2)
    with ec1:
        st.markdown('**VCP [Mark Minervini]**')
        if vcp2:
            sw = ' → '.join([f'{s:.1f}%' for s in vcp2['swings']])
            vc = TRAFFIC_GREEN if vcp2['contracting'] else TRAFFIC_YELLOW
            st.markdown(kpi('VCP狀態', '✅符合收縮' if vcp2['contracting'] else '⚠️未收縮',
                            f'波幅：{sw}', vc, vc), unsafe_allow_html=True)
            if vcp2['contracting']:
                st.markdown(signal_box('🔴等待帶量突破頸線', 'green', '確認突破才進場'),
                            unsafe_allow_html=True)
        else:
            st.info('數據不足（需≥40日）')
    with ec2:
        st.markdown('**布林通道 [策略3]**')
        if bb2:
            b1, b2 = st.columns(2)
            with b1:
                st.markdown(kpi('現價', f'{bb2["price"]:.2f}', '', '#e6edf3'),
                            unsafe_allow_html=True)
                st.markdown(kpi('布林上軌', f'{bb2["upper"]:.2f}', '壓力', TRAFFIC_RED, TRAFFIC_RED),
                            unsafe_allow_html=True)
            with b2:
                bw_c = TRAFFIC_GREEN if bb2['bw'] < bb2['bw_mean'] * BB_BW_SHRINK_WARN_RATIO else TRAFFIC_YELLOW
                st.markdown(kpi('帶寬', f'{bb2["bw"]:.1f}%',
                                f'均值{bb2["bw_mean"]:.1f}% {"⬇️收縮" if bb2["bw"] < bb2["bw_mean"] else "⬆️擴張"}',
                                bw_c, bw_c), unsafe_allow_html=True)
                st.markdown(kpi('布林下軌', f'{bb2["lower"]:.2f}', '支撐', TRAFFIC_GREEN, TRAFFIC_GREEN),
                            unsafe_allow_html=True)
            if bb2['bw'] < bb2['bw_mean'] * BB_BW_SHRINK_ACTION_RATIO:
                st.markdown(signal_box('🔵布林帶寬極度收縮', 'blue', '即將爆發，注意量能方向'),
                            unsafe_allow_html=True)
            if bb2['near_upper']:
                st.markdown(signal_box('🟢股價黏近上軌', 'green', '強勢突破訊號，搭配大量更可信'),
                            unsafe_allow_html=True)
    # ── VCP+布林動態建議 ──
    _vcp_verdict = ''
    _bb_verdict = ''
    if vcp2:
        _vcp_verdict = ('✅ VCP確認收縮：等待帶量突破頸線，是高確信進場點 [策略3]'
                        if vcp2['contracting']
                        else '⚪ 波幅尚未收縮：等待整理完成後再觀察')
    if bb2:
        if bb2['bw'] < bb2['bw_mean'] * BB_BW_SHRINK_ACTION_RATIO:
            _bb_verdict = '🔵 布林帶寬極度收縮：即將爆發，注意量能確認方向 [策略3]'
        elif bb2['near_upper']:
            _bb_verdict = '🟢 股價黏近上軌＋強勢：搭配大量是突破確認訊號 [策略3]'
        else:
            _bb_verdict = f'⚪ 布林帶寬{bb2["bw"]:.1f}%（均值{bb2["bw_mean"]:.1f}%）：尚未到關鍵位置'
    if _vcp_verdict or _bb_verdict:
        for _msg in [m for m in [_vcp_verdict, _bb_verdict] if m]:
            _mc2 = TRAFFIC_GREEN if '✅' in _msg or '🟢' in _msg else ('#58a6ff' if '🔵' in _msg else '#8b949e')
            st.markdown(border_left_banner(_mc2, _msg), unsafe_allow_html=True)

    # VCP+布林結論(安全版:加入 _msg 預設值)
    # R-UI-1 v18.412:inline `<div border-left>` → border_left_banner SSOT
    _msg = _msg if '_msg' in dir() else '⚪ VCP/布林資料不足'
    _vcp_c = TRAFFIC_GREEN if '✅' in _msg or '🟢' in _msg else (TRAFFIC_YELLOW if '⚠️' in _msg else '#484f58')
    st.markdown(border_left_banner(
        _vcp_c,
        f'<span style="font-size:11px;color:#8b949e;">🎓 策略3 · VCP</span>　'
        f'<span style="font-weight:700;">{_msg}</span>',
        padding_y=7, font_size=13,
    ), unsafe_allow_html=True)
    if bb2:
        _bb_verdict_safe = _bb_verdict if '_bb_verdict' in dir() else '⚪ 布林資料不足'
        _bb_c = TRAFFIC_GREEN if '✅' in _bb_verdict_safe or '🟢' in _bb_verdict_safe else ('#3aa2f5' if '🔵' in _bb_verdict_safe else TRAFFIC_YELLOW)
        st.markdown(border_left_banner(
            _bb_c,
            f'<span style="font-size:11px;color:#8b949e;">🎓 策略3 · 布林</span>　'
            f'<span style="font-weight:700;">{_bb_verdict_safe}</span>',
            padding_y=7, font_size=13,
        ), unsafe_allow_html=True)
