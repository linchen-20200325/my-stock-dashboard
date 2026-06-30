"""src/ui/tabs/stock_sections/section_financial_leading.py — C 財報領先指標 section(v18.406 U4 Phase 2-C).

從 tab_stock.py:2182-2257 抽出。
對齊 TAB_STOCK_AUDIT.md Phase 2 低風險 section batch。

§8.2 layer:L5 UI Tab section helper。

對外 API:
- render_financial_leading_section(sid2, cl2, cx2, _cl_src2, _cx_src2, _fin_errs2) -> None
"""
from __future__ import annotations

import streamlit as st

from shared.colors import TRAFFIC_GREEN, TRAFFIC_YELLOW
from src.ui.render import kpi, teacher_conclusion


def render_financial_leading_section(sid2: str, cl2, cx2,
                                      _cl_src2: str = '',
                                      _cx_src2: str = '',
                                      _fin_errs2=None) -> None:
    """C. 公司真的在賺錢嗎?(財報領先指標:合約負債 + 固定資產/資本支出)。

    Args:
        sid2: 股票代碼
        cl2: 合約負債(元;None / 0 視為無資料)
        cx2: 固定資產/資本支出(元;None / 0 視為無資料)
        _cl_src2: 合約負債資料來源(FinMind / MOPS / ...)
        _cx_src2: 固定資產資料來源
        _fin_errs2: 抓取錯誤訊息 list(空 → 視為「不適用」)
    """
    _fin_errs2 = _fin_errs2 or []
    st.markdown('---')
    st.markdown('#### 🔬 C. 公司真的在賺錢嗎？（財報領先指標）')
    if cl2 and cl2 > 0 and cx2 and cx2 > 0:
        _ca = f'合約負債 {cl2 / 1e8:.1f}億 + 資本支出 {cx2 / 1e8:.1f}億，雙重確認龍多股'
        _cb = '基本面強勢，適合長期持有'
    elif cl2 and cl2 > 0:
        _ca = f'合約負債 {cl2 / 1e8:.1f}億（訂單豐沛），資本支出資料不足'
        _cb = '基本面良好，但擴廠意願待確認'
    elif cx2 and cx2 > 0:
        _ca = f'資本支出 {cx2 / 1e8:.1f}億（積極擴產），合約負債資料不足'
        _cb = '擴廠意願強，但訂單能見度待確認'
    else:
        _ca = '合約負債+資本支出均無資料（可能為金融股或資料源限制）'
        _cb = '請至 MOPS 或年報查閱'
    st.markdown(teacher_conclusion('孫慶龍', f'{sid2} 財報領先指標', _ca, _cb),
                unsafe_allow_html=True)
    st.markdown(
        '<div style="background:#0a1628;border-left:3px solid #bc8cff;padding:8px 12px;'
        'border-radius:0 6px 6px 0;margin-bottom:8px;font-size:12px;color:#c9d1d9;">'
        '💡 這兩個財報數字能預測未來3-6個月的獲利方向：'
        '<br>📌 <b>合約負債</b> = 客戶已付錢但還沒出貨的訂單 → 越高代表訂單很多、業績有保障'
        '<br>📌 <b>資本支出</b> = 公司花錢蓋廠房買設備 → 越高代表看好未來、準備大幅擴產'
        '<br>⭐ 兩個都很高 = 策略1所說的「龍多股」，是存股首選'
        '</div>', unsafe_allow_html=True)
    fc1, fc2 = st.columns(2)
    cl_ok = cl2 is not None and cl2 > 0
    cx_ok = cx2 is not None and cx2 > 0
    with fc1:
        _cl_val_txt = f'{cl2 / 1e8:.1f}億' if cl_ok else '抓取失敗'
        _cl_c = '#2ea043' if cl_ok else '#da3633'
        st.markdown(kpi('合約負債', _cl_val_txt,
                        '>股本50%→未來3-6月訂單保障', _cl_c,
                        _cl_c if cl_ok else '#21262d'), unsafe_allow_html=True)
        if not cl_ok:
            st.caption('來源：FinMind — 抓取失敗或無此財報')
    with fc2:
        _cx_val_txt = f'{cx2 / 1e8:.1f}億' if cx_ok else '抓取失敗'
        _cx_c = '#2ea043' if cx_ok else '#da3633'
        st.markdown(kpi('固定資產/資本支出', _cx_val_txt,
                        '>股本80%→大擴廠看好未來需求', _cx_c,
                        _cx_c if cx_ok else '#21262d'), unsafe_allow_html=True)
        if not cx_ok:
            st.caption(f'來源：{_cl_src2 or _cx_src2 or "未知"}')
    if not cl_ok and not cx_ok:
        _na = (not _fin_errs2 and not cl_ok and not cx_ok)
        _fe = bool(_fin_errs2)
        if _na:
            st.info('ℹ️ 此產業（金融/保險等）不適用合約負債/固定資產指標，可跳過')
        elif _fe:
            # 顯示具體錯誤給使用者
            _err_src = (_cl_src2 + '/' + _cx_src2).strip('/')
            _err_msg = '; '.join(_fin_errs2) if _fin_errs2 else '抓取失敗'
            st.error(f'❌ 財報資料抓取失敗 — 來源:{_err_src or "三源均未命中"} | 錯誤:{_err_msg}')
            st.caption('💡 可能原因：① FinMind Token 失效 ② MOPS 暫時無回應 ③ 個股無此財報')
        else:
            st.info('ℹ️ 查無揭露：服務業/軟體業通常無此數據，可跳過')
            st.caption(f'來源：{_cl_src2 or _cx_src2 or "未知"}')
    # 財報結論:依合約負債+固定資產狀態給出判斷
    _fin_color = TRAFFIC_GREEN if cl_ok and cx_ok else (
        TRAFFIC_YELLOW if cl_ok or cx_ok else '#484f58')
    _fin_label = ('✅ 龍多確認：合約負債高＋資本支出高 = 訂單滿、擴廠中' if cl_ok and cx_ok
                  else ('⚠️ 部分訊號：' + ('合約負債充裕' if cl_ok else '資本支出積極')
                        if cl_ok or cx_ok else '⚪ 資料不足，無法判斷'))
    st.markdown(
        f'<div style="background:#0d1117;border-left:4px solid {_fin_color};'
        f'padding:10px 14px;border-radius:0 8px 8px 0;margin:6px 0;">'
        f'<span style="font-size:12px;color:#8b949e;">🎓 策略1 · 財報領先指標</span><br>'
        f'<span style="font-size:14px;font-weight:800;color:{_fin_color};">{_fin_label}</span><br>'
        f'<span style="font-size:11px;color:#8b949e;">兩指標均高 = 龍多股首選；詳細門檻見「策略手冊」Tab</span>'
        f'</div>',
        unsafe_allow_html=True
    )
