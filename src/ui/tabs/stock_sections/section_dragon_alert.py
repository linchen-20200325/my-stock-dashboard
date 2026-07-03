"""src/ui/tabs/stock_sections/section_dragon_alert.py — 龍頭預警區 section(v18.411 U4 Phase 3-Dragon).

從 tab_stock.py:802-829 抽出。
- 孫慶龍龍多策略最高等級「龍頭預警區」
- 合約負債 / 股本 ≥ 50% → 未來 3-6 月訂單保障
- 資本支出(CF,季實際支出) / 股本 ≥ 80% → 大擴廠,看好未來需求

§8.2 layer:L5 UI Tab section helper(低風險,純展示)。

對外 API:
- render_dragon_alert_section(cl2, cx2, capital, *, capex=None) -> None
"""
from __future__ import annotations

import streamlit as st


def render_dragon_alert_section(cl2, cx2, capital: float, *, capex=None) -> None:
    """龍頭預警區 — 孫慶龍龍多策略最高等級。

    cl2 / cx2 為 FinMind 原始元值;對「股本」算真實比例(取代舊版 >0 假判斷)。

    Args:
        cl2:    合約負債(元),None / 0 代表無資料
        cx2:    固定資產存量(BS PropertyPlantAndEquipment,元)，僅供 fallback
        capital: 股本(元),由 _precompute_xsec 預算後傳入
        capex:  CF 資本支出(季實際支出,元) — v18.457 Task#20 新增，用於「大擴廠」判斷
                若 None，退回 cx2(cx2 可能已 fallback 為 capex，見 app_stock_fetchers.py)
    """
    # v18.457: 龍多「大擴廠」用 CF 資本支出(季流量)比較，不用 PP&E 存量
    # PP&E 存量是幾十年的累積，製造業幾乎永遠 ≥ 股本；capex 是本季實際花錢，才能反映擴產意願
    _cx_for_dragon = capex if (capex is not None and capex > 0) else cx2

    _is_dragon = False
    _dragon_reasons = []
    try:
        if capital > 0:
            if cl2 is not None and cl2 > 0 and cl2 / capital >= 0.5:
                _dragon_reasons.append(
                    f'合約負債 {cl2/1e8:.1f}億（達股本 {cl2/capital*100:.0f}% → 未來3-6月訂單保障）')
                _is_dragon = True
            if _cx_for_dragon is not None and _cx_for_dragon > 0 and _cx_for_dragon / capital >= 0.8:
                _src_label = '季資本支出' if (capex is not None and capex > 0) else '固定資產'
                _dragon_reasons.append(
                    f'{_src_label} {_cx_for_dragon/1e8:.1f}億（達股本 {_cx_for_dragon/capital*100:.0f}% → 大擴廠，看好未來需求）')
                _is_dragon = True
    except Exception:
        pass

    if _is_dragon:
        st.markdown(
            '<div style="background:linear-gradient(135deg,#2a1f00,#3d2d00);'
            'border:2px solid #ffd700;border-radius:10px;padding:12px 16px;margin-bottom:10px;">'
            '<div style="font-size:14px;font-weight:900;color:#ffd700;margin-bottom:6px;">'
            '🏆 龍頭預警區 — 極稀有高成長標的</div>' +
            ''.join(f'<div style="font-size:12px;color:#ffe066;padding:2px 0;">• {r}</div>' for r in _dragon_reasons) +
            '<div style="font-size:11px;color:#997a00;margin-top:4px;">'
            '策略1：「不要聽老闆說什麼，要看他做什麼」— 最誠實的領先指標</div>'
            '</div>', unsafe_allow_html=True)
