"""src/ui/tabs/stock_sections/section_revenue.py — D 月營收趨勢 section(v18.406 U4 Phase 2-D).

從 tab_stock.py:2259-2302 抽出(L5 → L5,純 render 函式重構)。
對齊 docs/TAB_STOCK_AUDIT.md Phase 2 低風險 section batch。

§8.2 layer:L5 UI Tab section helper(類比 macro/section_*.py 模式)。

對外 API:
- render_revenue_trend_section(sid2, name2, rev2, qtr2, _rev2_cached, _qtr2_cached) -> None
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from shared.colors import TRAFFIC_GREEN
from src.ui.render import (  # v19.174 去識別化：改吃策略代號常數 + 新函式名
    STRATEGY_VALUATION,
    plot_quarterly_chart,
    plot_revenue_chart,
    strategy_conclusion,
)


def render_revenue_trend_section(sid2: str, name2: str, rev2, qtr2,
                                  _rev2_cached: bool = False,
                                  _qtr2_cached: bool = False) -> None:
    """D. 公司每月賺多少錢?(月營收趨勢 + 季財報 charts)。

    Args:
        sid2: 股票代碼
        name2: 股票名稱
        rev2: 月營收 DataFrame(或 None)
        qtr2: 季財報 DataFrame(或 None)
        _rev2_cached: 月營收是否為快取資料
        _qtr2_cached: 季財報是否為快取資料
    """
    # ══ D. 月營收 + 季毛利率 ══════════════════════════════
    st.markdown('---')
    st.markdown('#### 📈 D. 公司每月賺多少錢？（營收趨勢）')
    _d_ind = f'{sid2} 月營收YoY%'
    _da = '月營收數據尚未載入'
    _db = ''
    if rev2 is not None and not rev2.empty and len(rev2) >= 3:
        _yoy_col = next((c for c in rev2.columns
                         if 'yoy' in str(c).lower() or '年增' in str(c) or 'YoY' in str(c)), None)
        if _yoy_col:
            _yoy3 = pd.to_numeric(rev2[_yoy_col].tail(3), errors='coerce').dropna()
            if len(_yoy3) >= 2:
                _avg_y = float(_yoy3.mean())
                _last_y = float(_yoy3.iloc[-1])
                _d_ind = f'{sid2} 近3月平均YoY {_avg_y:+.1f}%'
                if _avg_y > 15 and (_yoy3 > 0).all():
                    _da = f'近3月YoY平均 {_avg_y:+.1f}%（最新 {_last_y:+.1f}%），業績爆發，重點關注'
                    _db = '配合技術面買點可進場'
                elif _avg_y > 0:
                    _da = f'近3月YoY平均 {_avg_y:+.1f}%，溫和成長'
                    _db = '持續追蹤，等待加速跡象'
                else:
                    _da = f'近3月YoY平均 {_avg_y:+.1f}%，業績衰退'
                    _db = '不管K線多好看，先觀望'
    st.markdown(strategy_conclusion(STRATEGY_VALUATION, _d_ind, _da, _db), unsafe_allow_html=True)
    st.markdown(
        f'<div style="background:#0a1628;border-left:3px solid {TRAFFIC_GREEN};padding:8px 12px;'
        'border-radius:0 6px 6px 0;margin-bottom:8px;font-size:12px;color:#c9d1d9;">'
        '💡 月營收年增率（YoY%）= 今年這個月比去年同月多賺了幾%'
        # D1 v19.185（形狀 #5 畫面宣稱門檻 ≠ 判定式）：原文寫「連續3個月YoY>15%」，
        # 但上方判定式是 `近3月平均 > 15% 且三個月皆為正`——例如 [+50, +1, +1]
        # 只有一個月超過 15%，卻會被判「業績爆發，重點關注」。這裡改寫成
        # **實際在跑的規則**（判定式本身是合理的，說謊的是這段說明文字）。
        '<br>🟢 <b>近3個月YoY平均 &gt;15% 且三個月都是正成長</b> = 業績爆發，股價可能跟著漲'
        '<br>🔴 <b>近3個月YoY平均 ≤0%</b> = 業績衰退，要小心'
        '</div>', unsafe_allow_html=True)
    if rev2 is not None and not rev2.empty:
        if _rev2_cached:
            st.caption('⚠️ 月營收使用快取資料（本次 API 未回應）')
        st.plotly_chart(plot_revenue_chart(rev2, sid2, name2),
                        width='stretch', config={'displayModeBar': False})
    else:
        st.warning('⚠️ 月營收數據暫無（請確認 FINMIND_TOKEN 是否正確，或重新載入）')
        st.caption('💡 首次查詢需網路抓取，若持續失敗請檢查 Token 或稍後重試')
    if qtr2 is not None and not qtr2.empty:
        if _qtr2_cached:
            st.caption('⚠️ 季財報使用快取資料（本次 API 未回應）')
        st.plotly_chart(plot_quarterly_chart(qtr2, sid2, name2),
                        width='stretch', config={'displayModeBar': False})
