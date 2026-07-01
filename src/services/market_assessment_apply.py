"""src/services/market_assessment_apply.py — 市場評估 apply + mkt_info write(P3-D13 v18.392)。

從 tab_macro inline 抽出(原 line 368-420,~53 LOC)。

職責(L3 service):
- 從已載入的 inst / tw_raw / m1b_m2_info 算出 market_regime
- get_market_assessment 主路徑;失敗時備援 df_index=None 重抓
- 融資 signals append(SSOT thresholds:MARGIN_BALANCE_OVERHEAT/WARN)
- 寫 st.session_state['mkt_info']

§8.2 L3:純 compute(call L2 get_market_assessment)+ session write。
"""
from __future__ import annotations

import traceback

import streamlit as st

from shared.signal_thresholds import (
    MARGIN_BALANCE_OVERHEAT_THRESHOLD_YI,
    MARGIN_BALANCE_WARN_THRESHOLD_YI,
)


def compute_and_apply_market_assessment(
    *,
    inst: dict,
    tw_raw: dict,
    margin,
    df_adl=None,
) -> None:
    """計算市場狀態 + 寫 st.session_state['mkt_info']。

    參數:
        inst: 三大法人 dict({外資/陸資, 投信, 自營商: {'net': ...}})
        tw_raw: 台股 raw OHLCV dict(由 fetch_macro_bundle 取)
        margin: 融資餘額(億)或 None
        df_adl: ADL DataFrame(由 fetch_adl 取得,含 `ad_ratio` 欄位)或 None。
                v18.449 新增:市場廣度真值來源;None = 不納入評分(§1 寧缺勿假,
                不塞假中性值)。

    內部處理:
        - 從 inst 取「外資」淨買賣 net(億)→ 乘 1e8 還原元
        - tw_raw.get('台股加權指數')→ 大盤 DF
        - session_state.m1b_m2_info → M1B-M2 gap
        - df_adl 最後一列的 ad_ratio → 市場廣度(選填)
        - get_market_assessment(...)主路徑,空時 df_index=None 備援
        - 融資 signals append 三段燈
        - 寫 mkt_info session_state

    §1 Fail Loud:全敗時 print exception + 不寫(不蓋既有 stale)。
    """
    from src.services import get_market_assessment

    try:
        _foreign_net_loaded = 0  # 0 = 尚無資料(market_regime 會顯示「待更新」)
        for _k, _v in inst.items():
            if '外資' in _k:
                _net_v = _v.get('net')
                if _net_v is not None:
                    _foreign_net_loaded = float(_net_v) * 1e8
                break
        _twii_df_loaded = tw_raw.get('台股加權指數')
        print(f'[市場評估] 大盤DF shape={getattr(_twii_df_loaded,"shape",None)}, '
              f'columns={list(getattr(_twii_df_loaded,"columns",[]))}, '
              f'外資淨={_foreign_net_loaded/1e8:.1f}億')
        # 取得 M1B-M2 資金活水資料(宏爺評分維度)
        _m1b2 = st.session_state.get('m1b_m2_info') or {}
        _m1b2_gap = (round(float(_m1b2['m1b_yoy']) - float(_m1b2['m2_yoy']), 2)
                     if _m1b2.get('m1b_yoy') is not None and _m1b2.get('m2_yoy') is not None
                     else None)
        _m1b2_prev = _m1b2.get('m1b_m2_gap_prev')  # 上月 gap(若有)
        # 市場廣度真值(v18.449):df_adl 最後一列的 ad_ratio(0-100% 上漲家數佔比)。
        # 無資料/空值 → None(不納入評分,§1 寧缺勿假,不塞假中性值)。
        _ad_ratio_loaded = None
        try:
            if df_adl is not None and not df_adl.empty and 'ad_ratio' in df_adl.columns:
                _v_adr = df_adl['ad_ratio'].iloc[-1]
                if _v_adr == _v_adr:  # NaN 自身不等於自身
                    _ad_ratio_loaded = float(_v_adr)
        except Exception as _e_adr:
            print(f'[市場評估] ad_ratio 解析失敗(不納入評分):{type(_e_adr).__name__}: {_e_adr}')
        _mkt_loaded = get_market_assessment(
            df_index=_twii_df_loaded,
            foreign_net=_foreign_net_loaded,
            m1b_m2_gap=_m1b2_gap,
            m1b_m2_prev=_m1b2_prev,
            ad_ratio=_ad_ratio_loaded,
        )
        if _mkt_loaded:
            _append_margin_signals(_mkt_loaded, margin)
            st.session_state['mkt_info'] = _mkt_loaded
            print(f'[市場評估] 成功:{_mkt_loaded.get("label")} 評分{_mkt_loaded.get("score")}')
        else:
            # 備援:直接用 yfinance 重抓
            print('[市場評估] df_index 失敗,用 yfinance 備援')
            _mkt_fb = get_market_assessment(df_index=None, foreign_net=_foreign_net_loaded,
                                            ad_ratio=_ad_ratio_loaded)
            if _mkt_fb:
                _append_margin_signals(_mkt_fb, margin)
                st.session_state['mkt_info'] = _mkt_fb
                print(f'[市場評估] 備援成功:{_mkt_fb.get("label")}')
    except Exception as _me:
        print(f'[市場評估 ERROR] {_me}')
        traceback.print_exc()


def _append_margin_signals(mkt_dict: dict, margin) -> None:
    """融資餘額三段燈號 append 到 mkt_dict['signals']。"""
    if not margin:
        return
    if margin > MARGIN_BALANCE_OVERHEAT_THRESHOLD_YI:
        mkt_dict['signals'].append('🔴 融資極度危險（>3400億）')
    elif margin > MARGIN_BALANCE_WARN_THRESHOLD_YI:
        mkt_dict['signals'].append('⚠️ 融資警戒（>2500億）')
    else:
        mkt_dict['signals'].append(f'✅ 融資安全（{margin:.0f}億）')
