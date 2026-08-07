"""src/ui/tabs/stock_sections/section_financial_leading.py — C 財報領先指標 section(v18.406 U4 Phase 2-C).

從 tab_stock.py:2182-2257 抽出。
對齊 docs/TAB_STOCK_AUDIT.md Phase 2 低風險 section batch。

§8.2 layer:L5 UI Tab section helper。

對外 API:
- render_financial_leading_section(sid2, cl2, cx2, _cl_src2, _cx_src2, _fin_errs2) -> None
"""
from __future__ import annotations

import streamlit as st

from shared.colors import TRAFFIC_GREEN, TRAFFIC_NEUTRAL, TRAFFIC_YELLOW
from shared.signal_thresholds import (
    CAPEX_TO_EQUITY_RATIO_THRESHOLD_PCT,
    CONTRACT_LIABILITY_TO_EQUITY_RATIO_THRESHOLD_PCT,
)
from src.ui.render import STRATEGY_VALUATION, kpi, strategy_conclusion  # v19.174 去識別化


def _ratio_to_equity_pct(value, capital):
    """value(元) 佔股本(元)的百分比。任一未知 / 非正 → None（§1：不猜）。"""
    try:
        _v = float(value)
        _c = float(capital)
    except (TypeError, ValueError):
        return None
    if _v <= 0 or _c <= 0 or _v != _v or _c != _c:
        return None
    return _v / _c * 100


def evaluate_leading_gates(cl_twd, cx_twd, capital_twd) -> dict:
    """合約負債 / 資本支出 **佔股本比** → 是否達龍多門檻（純函式）。

    Returns:
        dict::

            {'cl_pct': float|None, 'cx_pct': float|None,
             'cl_lead': bool, 'cx_lead': bool, 'ratio_known': bool}

        `*_pct is None` = 算不出（缺股本或缺該項財報）→ `*_lead` 必為 False，
        但語意是「**未評估**」而非「未達標」；`ratio_known` 用來區分這兩者。

    D1 v19.185 抽出的理由：舊判定式是 `cl > 0 and cx > 0`（只要抓得到數字
    就算「高」），而畫面副標宣稱門檻是「>股本50%」「>股本80%」。抽成純函式
    後，「有值但比例不到門檻 → 不得亮綠」這條可以被測試直接釘住。
    """
    _cl_pct = _ratio_to_equity_pct(cl_twd, capital_twd)
    _cx_pct = _ratio_to_equity_pct(cx_twd, capital_twd)
    return {
        'cl_pct': _cl_pct,
        'cx_pct': _cx_pct,
        'cl_lead': (_cl_pct is not None
                    and _cl_pct >= CONTRACT_LIABILITY_TO_EQUITY_RATIO_THRESHOLD_PCT),
        'cx_lead': (_cx_pct is not None
                    and _cx_pct >= CAPEX_TO_EQUITY_RATIO_THRESHOLD_PCT),
        'ratio_known': _cl_pct is not None or _cx_pct is not None,
    }


def render_financial_leading_section(sid2: str, cl2, cx2,
                                      _cl_src2: str = '',
                                      _cx_src2: str = '',
                                      _fin_errs2=None,
                                      *,
                                      capex=None,
                                      capital=None) -> None:
    """C. 公司真的在賺錢嗎?(財報領先指標:合約負債 + 固定資產/資本支出)。

    Args:
        sid2: 股票代碼
        cl2: 合約負債(元;None / 0 視為無資料)
        cx2: 固定資產(PP&E, BS 存量;None / 0 視為無資料)
        _cl_src2: 合約負債資料來源(FinMind / MOPS / ...)
        _cx_src2: 固定資產資料來源
        _fin_errs2: 抓取錯誤訊息 list(空 → 視為「不適用」)
        capex: CF 季資本支出(元;流量。優先於 cx2 PP&E 存量顯示)
        capital: 股本(元;`_precompute_xsec` 已算)。**判定龍多門檻的分母** ——
            None / 0 → 只顯示絕對金額,不宣稱是否達標(§1)。

    D1 v19.185（§5 畫面宣稱門檻 ≠ 判定式）
    ---------------------------------------
    舊碼的「✅ 龍多確認：合約負債**高**＋資本支出**高**」與「雙重確認龍多股」
    判定式其實只是 `cl2 > 0 and cx > 0` —— **只要抓得到數字就算「高」**。
    而同一張卡右下角的副標寫的是「>股本50%」「>股本80%」，也就是畫面自己
    宣告了兩個從來沒被執行過的門檻。實務後果：幾乎每一檔製造業都拿到
    「✅ 龍多確認」，同一頁上方真的照比例判定的「🏆 龍頭預警區」卻不亮 ——
    兩塊對同一個「龍多」概念給出相反結論。
    現在改用 SSOT 門檻（`CONTRACT_LIABILITY_TO_EQUITY_RATIO_THRESHOLD_PCT` 50%
    / `CAPEX_TO_EQUITY_RATIO_THRESHOLD_PCT` 80%，與 `section_dragon_alert` 同源）
    真的算比例；股本未取得 → ⬜ 未評估，不給綠燈也不給紅燈。
    """
    # v18.458: 優先用 CF 季資本支出顯示;cx2 為 PP&E 存量 fallback
    _cx_for_display = capex if (capex is not None and capex > 0) else cx2
    _cx_label = '季資本支出' if (capex is not None and capex > 0) else '固定資產/資本支出'
    _fin_errs2 = _fin_errs2 or []
    # 佔股本比（%）— None = 無法計算（缺股本或缺該項財報）
    _gates = evaluate_leading_gates(cl2, _cx_for_display, capital)
    _cl_pct, _cx_pct = _gates['cl_pct'], _gates['cx_pct']
    _cl_lead, _cx_lead = _gates['cl_lead'], _gates['cx_lead']
    _ratio_known = _gates['ratio_known']
    st.markdown('---')
    st.markdown('#### 🔬 C. 公司真的在賺錢嗎？（財報領先指標）')
    _cl_txt = f'合約負債 {cl2 / 1e8:.1f}億' + (f'（股本 {_cl_pct:.0f}%）' if _cl_pct is not None else '') \
        if (cl2 and cl2 > 0) else ''
    _cx_txt = f'{_cx_label} {_cx_for_display / 1e8:.1f}億' + (f'（股本 {_cx_pct:.0f}%）' if _cx_pct is not None else '') \
        if (_cx_for_display and _cx_for_display > 0) else ''
    if _cl_lead and _cx_lead:
        _ca = (f'{_cl_txt} + {_cx_txt} — 兩項皆達龍多門檻'
               f'（≥股本{CONTRACT_LIABILITY_TO_EQUITY_RATIO_THRESHOLD_PCT:g}% / '
               f'≥股本{CAPEX_TO_EQUITY_RATIO_THRESHOLD_PCT:g}%）')
        _cb = '基本面強勢，適合長期持有'
    elif _cl_lead or _cx_lead:
        _ca = (f'{_cl_txt}{"、" if _cl_txt and _cx_txt else ""}{_cx_txt} — '
               f'{"合約負債" if _cl_lead else "資本支出"}達龍多門檻，另一項未達')
        _cb = '單邊訊號，宜再觀察另一項是否跟上'
    elif _ratio_known:
        _ca = f'{_cl_txt}{"、" if _cl_txt and _cx_txt else ""}{_cx_txt} — 兩項皆未達龍多門檻'
        _cb = '一般水準，非龍多股特徵'
    elif (cl2 and cl2 > 0) or (_cx_for_display and _cx_for_display > 0):
        _ca = (f'{_cl_txt}{"、" if _cl_txt and _cx_txt else ""}{_cx_txt} — '
               '股本未取得，無法判定是否達龍多門檻')
        _cb = '僅供絕對金額參考，門檻判定待股本資料'
    else:
        _ca = '合約負債+資本支出均無資料（可能為金融股或資料源限制）'
        _cb = '請至 MOPS 或年報查閱'
    st.markdown(strategy_conclusion(STRATEGY_VALUATION, f'{sid2} 財報領先指標', _ca, _cb),
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
    cx_ok = _cx_for_display is not None and _cx_for_display > 0  # v18.458: 用 _cx_for_display
    with fc1:
        _cl_val_txt = f'{cl2 / 1e8:.1f}億' if cl_ok else '抓取失敗'
        # §1：卡片顏色跟著**門檻判定**走，不再是「抓得到就綠」。
        _cl_c = ('#2ea043' if _cl_lead
                 else ('#da3633' if not cl_ok
                       else (TRAFFIC_YELLOW if _cl_pct is not None else TRAFFIC_NEUTRAL)))
        _cl_sub = (f'佔股本 {_cl_pct:.0f}%（門檻 ≥{CONTRACT_LIABILITY_TO_EQUITY_RATIO_THRESHOLD_PCT:g}%'
                   f'→未來3-6月訂單保障）' if _cl_pct is not None
                   else f'門檻 ≥股本{CONTRACT_LIABILITY_TO_EQUITY_RATIO_THRESHOLD_PCT:g}%'
                        f'（股本未取得，未評估）')
        st.markdown(kpi('合約負債', _cl_val_txt, _cl_sub, _cl_c,
                        _cl_c if cl_ok else '#21262d'), unsafe_allow_html=True)
        if not cl_ok:
            st.caption('來源：FinMind — 抓取失敗或無此財報')
    with fc2:
        _cx_val_txt = f'{_cx_for_display / 1e8:.1f}億' if cx_ok else '抓取失敗'
        _cx_c = ('#2ea043' if _cx_lead
                 else ('#da3633' if not cx_ok
                       else (TRAFFIC_YELLOW if _cx_pct is not None else TRAFFIC_NEUTRAL)))
        _cx_sub = (f'佔股本 {_cx_pct:.0f}%（門檻 ≥{CAPEX_TO_EQUITY_RATIO_THRESHOLD_PCT:g}%'
                   f'→大擴廠看好未來需求）' if _cx_pct is not None
                   else f'門檻 ≥股本{CAPEX_TO_EQUITY_RATIO_THRESHOLD_PCT:g}%'
                        f'（股本未取得，未評估）')
        st.markdown(kpi(_cx_label, _cx_val_txt, _cx_sub, _cx_c,
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
    # 財報結論:依**佔股本比是否達門檻**給出判斷（D1 v19.185，原本只看 >0）
    if _cl_lead and _cx_lead:
        _fin_color = TRAFFIC_GREEN
        _fin_label = ('✅ 龍多確認：合約負債 ≥股本'
                      f'{CONTRACT_LIABILITY_TO_EQUITY_RATIO_THRESHOLD_PCT:g}%'
                      f' ＋ 資本支出 ≥股本{CAPEX_TO_EQUITY_RATIO_THRESHOLD_PCT:g}%'
                      ' = 訂單滿、擴廠中')
    elif _cl_lead or _cx_lead:
        _fin_color = TRAFFIC_YELLOW
        _fin_label = ('⚠️ 部分訊號：'
                      + ('合約負債達門檻，資本支出未達' if _cl_lead
                         else '資本支出達門檻，合約負債未達'))
    elif _ratio_known:
        _fin_color = TRAFFIC_NEUTRAL
        _fin_label = '⚪ 兩項佔股本比均未達龍多門檻（有資料，判定為一般水準）'
    else:
        _fin_color = '#484f58'
        _fin_label = ('⬜ 未評估：股本未取得，無法算「佔股本比」'
                      if (cl_ok or cx_ok) else '⚪ 資料不足，無法判斷')
    st.markdown(
        f'<div style="background:#0d1117;border-left:4px solid {_fin_color};'
        f'padding:10px 14px;border-radius:0 8px 8px 0;margin:6px 0;">'
        f'<span style="font-size:12px;color:#8b949e;">🎓 策略1 · 財報領先指標</span><br>'
        f'<span style="font-size:14px;font-weight:800;color:{_fin_color};">{_fin_label}</span><br>'
        f'<span style="font-size:11px;color:#8b949e;">兩指標均高 = 龍多股首選；詳細門檻見「策略手冊」Tab</span>'
        f'</div>',
        unsafe_allow_html=True
    )
