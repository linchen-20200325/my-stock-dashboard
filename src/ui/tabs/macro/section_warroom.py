"""src/ui/tabs/macro/section_warroom.py — 今日作戰室(P3-D7 v18.390 抽出)。

原 tab_macro.py:341-493 inline。「最重要:一眼看清今天該做什麼」。

包含:
- 標題卡(refresh 中隱藏)
- 今日唯一行動建議(以紅綠燈 regime 為主)
- 5 分鐘清單(大盤燈號 / 外資 / 融資 / 年線 / 持股)
- 風險警示(融資 / 年線 / 外資賣超 / 廣度)
- 月虧損強制停機(<-10%)
- 空狀態(資料未載入 + 非 refresh 中)

closure params:
- _tl_eff_reg: str | None   紅綠燈有效 regime
- _show_market_data: bool   資料載入 gate
- do_refresh: bool          按鈕觸發 flag(refresh 中隱藏標題 + 空狀態)

session_state 讀(0 寫):
- monthly_loss_pct(月虧損強制停機)
- via load_section_inputs:mkt_info / cl_data / bias_info / m1b_m2_info / cl_ts / futures_net
"""
from __future__ import annotations

import streamlit as st

from shared.colors import TRAFFIC_GREEN, TRAFFIC_RED, TRAFFIC_YELLOW
from shared.signal_thresholds import (
    MARGIN_BALANCE_OVERHEAT_THRESHOLD_YI,
    MARGIN_BALANCE_WARN_THRESHOLD_YI,
)


def render_section_warroom(_tl_eff_reg, _show_market_data: bool, do_refresh: bool) -> None:
    """渲染今日作戰室(原 tab_macro line 341-493)。"""
    from src.services import load_section_inputs as _load_si_wr
    from src.services import evaluate_market_status_v4_final

    # v18.334:抓取進行中隱藏標題(與下方空狀態一致,載入時只留 spinner)
    if not do_refresh:
        st.markdown('''<div style="background:linear-gradient(135deg,#0a1628,#0d2040);
border:2px solid #1f6feb;border-radius:14px;padding:16px;margin-bottom:14px;">
<div style="font-size:18px;font-weight:900;color:#58a6ff;margin-bottom:4px;">
🎯 今日作戰室 — 現在該做什麼？</div>
<div style="font-size:11px;color:#484f58;">每次操作前先看這裡，5分鐘掌握今日全局</div>
</div>''', unsafe_allow_html=True)

    # C1-C v18.289:走 section_inputs.load_section_inputs SSOT(對齊 5 桶 + 戰情概覽)
    _wr_inp = _load_si_wr(st.session_state)
    _wr_mkt = _wr_inp.mkt_info or {}
    _wr_cd = _wr_inp.cl_data or {}
    _wr_bias = _wr_inp.bias_info or {}
    _wr_m1b = _wr_inp.m1b_m2_info or {}
    _wr_inst = _wr_cd.get('inst', {})
    _wr_fk = next((k for k in _wr_inst if '外資' in k), None)
    if _wr_fk is None:
        _wr_fk = next((k for k in _wr_inst if '外資' in k), None)
    _wr_fnet = _wr_inst.get(_wr_fk, {}).get('net', None) if _wr_fk else None
    _wr_margin = _wr_cd.get('margin')
    _wr_adl = _wr_cd.get('adl')
    _wr_ts = _wr_inp.cl_ts
    # 以交通燈有效 regime 為主,確保與頂部卡片結論一致
    _wr_reg = _tl_eff_reg or (_wr_mkt.get('regime', 'neutral') if _wr_mkt else 'neutral')
    # v4 引擎:解耦趨勢與位階,取得精準操作建議
    _wr_fut_net = _wr_inp.futures_net
    _v4 = evaluate_market_status_v4_final(
        _wr_bias.get('price', 0) or 0,
        _wr_bias.get('ma240', 0) or 0,
        _wr_fut_net,
    )
    # 持股建議統一用紅綠燈/market_regime 的 exposure_pct(與 ①②一致,不再用 v4 區間)
    _wr_exp = _wr_mkt.get('exposure_pct', '--') if _wr_mkt else '--'

    if _show_market_data and (_wr_mkt or _wr_cd):
        # ── 今日唯一結論(大字顯示)──────────────────────────
        _wr_action = '請先更新總經數據'
        _wr_action_color = '#484f58'
        _wr_warns = []

        # 主結論統一以頂部紅綠燈 regime 為準(與燈號/戰情概覽一致,杜絕打架)
        _wr_reg_map = {
            'bull':    ('🟢 趨勢偏多 — 可逢回布局核心部位',   TRAFFIC_GREEN),
            'neutral': ('🟡 方向震盪 — 區間操作、控制部位',   TRAFFIC_YELLOW),
            'bear':    ('🔴 趨勢偏空 — 優先保留現金、嚴設停損', TRAFFIC_RED),
        }
        _wr_base, _wr_action_color = _wr_reg_map.get(_wr_reg, ('請先更新總經數據', '#484f58'))
        _wr_action = (f'{_wr_base}（建議持股 {_wr_exp}）'
                      if _wr_exp not in ('--', None, '') else _wr_base)
        # v4 年線位階資訊 → 降為補充提示,不再覆蓋主結論
        _v4_bits = [f'年線乖離 {_v4["Bias_240"]:+.1f}%']
        if not _v4.get('Is_Bull'):
            _v4_bits.append('股價在年線下')
        if _v4.get('Is_Overheated'):
            _v4_bits.append('乖離過熱')
        if _v4.get('Is_Foreign_Hedging'):
            _v4_bits.append('外資期貨避險')
        _wr_v4_hint = '｜'.join(_v4_bits)

        # 風險警示收集(v5:純融資餘額判斷)
        if _wr_margin and _wr_margin > MARGIN_BALANCE_OVERHEAT_THRESHOLD_YI:
            _wr_warns.append(('🔴', f'融資 {_wr_margin:.0f}億 極度危險，散戶過熱，不宜追高'))
        elif _wr_margin and _wr_margin > MARGIN_BALANCE_WARN_THRESHOLD_YI:
            _wr_warns.append(('🟡', f'融資 {_wr_margin:.0f}億 警戒，注意風險'))

        if _wr_bias:
            _b240 = _wr_bias.get('bias_240', 0)
            if _b240 > 20:
                _wr_warns.append(('🟡', f'年線乖離 {_b240:+.1f}%，大盤偏高，勿追買'))
            elif _b240 < -20:
                _wr_warns.append(('✅', f'年線負乖離 {_b240:+.1f}%，長期布局機會'))

        if _wr_fnet is not None and _wr_fnet < -20:
            _wr_warns.append(('🔴', f'外資賣超 {abs(_wr_fnet):.1f}億，主力離場，謹慎'))

        if _wr_adl is not None and not _wr_adl.empty and 'ad_ratio' in _wr_adl.columns:
            _adl_r = float(_wr_adl['ad_ratio'].iloc[-1])
            if _adl_r < 35:
                _wr_warns.append(('🔴', f'上漲股票僅 {_adl_r:.0f}%，市場廣度不足，觀望'))

        # 顯示今日結論
        st.markdown(
            f'<div style="background:#0a2818;border-left:5px solid {_wr_action_color};'
            f'border-radius:0 10px 10px 0;padding:14px 18px;margin:8px 0;">'
            f'<div style="font-size:11px;color:#484f58;margin-bottom:4px;">📌 今日唯一行動建議</div>'
            f'<div style="font-size:17px;font-weight:900;color:{_wr_action_color};">{_wr_action}</div>'
            + (f'<div style="font-size:11px;color:#8b949e;margin-top:4px;">📐 年線位階參考：{_wr_v4_hint}</div>' if _wr_v4_hint else '')
            + (f'<div style="font-size:11px;color:#484f58;margin-top:4px;">更新時間：{_wr_ts}</div>' if _wr_ts else '') +
            '</div>', unsafe_allow_html=True)

        # 今日5分鐘清單 — v18.318:5 列垂直清單 → 5 欄總結小卡(比照桶卡片視覺)
        st.markdown('##### ✅ 今日操作前 5 分鐘清單')
        _cl_items = [
            ('大盤燈號', '🟢 多頭' if _wr_reg == 'bull' else ('🔴 空頭防禦' if _wr_reg == 'bear' else '🟡 震盪'),
             _wr_reg == 'bull', '多頭才積極操作'),
            ('外資方向', f'{"買超" if (_wr_fnet or 0)>0 else "賣超"} {abs(_wr_fnet or 0):.0f}億' if _wr_fnet is not None else '未知',
             (_wr_fnet or 0) > 0, '外資買超=跟著走'),
            ('融資餘額',
             f'{_wr_margin:.0f}億' if _wr_margin else '未取得 (N/A)',
             not _wr_margin or _wr_margin <= MARGIN_BALANCE_WARN_THRESHOLD_YI,
             '>2500億警戒，>3400億極危'),
            ('年線位置', f'乖離{_wr_bias.get("bias_240",0):+.1f}%' if _wr_bias else '未知',
             not _wr_bias or abs(_wr_bias.get("bias_240", 0)) < 20, '超過±20%要警惕'),
            ('持股比例', f'建議{_wr_exp}', _wr_reg != 'bear', '按建議比例，不要滿倉'),
        ]
        _cl_cols = st.columns(len(_cl_items))
        for _ccol, (_name, _val, _ok, _tip) in zip(_cl_cols, _cl_items):
            _ic = '✅' if _ok else '⚠️'
            _vc = TRAFFIC_GREEN if _ok else TRAFFIC_RED
            with _ccol:
                st.markdown(
                    f"<div style='background:#0d1117;border:1px solid #21262d;"
                    f"border-top:3px solid {_vc};border-radius:8px;padding:8px 10px;"
                    f"margin:2px 0;min-height:108px;display:flex;flex-direction:column;"
                    f"justify-content:space-between;'>"
                    f"<div>"
                    f"<div style='font-size:11px;color:#8b949e;'>{_ic} {_name}</div>"
                    f"<div style='font-size:15px;font-weight:800;color:{_vc};"
                    f"margin:5px 0;line-height:1.25;'>{_val}</div>"
                    f"</div>"
                    f"<div style='font-size:10px;color:#484f58;line-height:1.3;'>{_tip}</div>"
                    f"</div>", unsafe_allow_html=True)

        # 風險警示
        if _wr_warns:
            st.markdown('##### ⚠️ 今日風險警示')
            for _wic, _wtxt in _wr_warns:
                _wbg = '#2a0d0d' if '🔴' in _wic else ('#2a1f00' if '🟡' in _wic else '#0a2818')
                st.markdown(
                    f'<div style="background:{_wbg};border-radius:6px;padding:7px 12px;margin:3px 0;'
                    f'font-size:13px;color:#c9d1d9;">{_wic} {_wtxt}</div>',
                    unsafe_allow_html=True)

        # 月虧損強制停機警示
        _monthly_loss = st.session_state.get('monthly_loss_pct', 0)
        if _monthly_loss < -10:
            st.markdown(
                f'<div style="background:#3a0000;border:2px solid {TRAFFIC_RED};border-radius:10px;'
                f'padding:14px;margin:10px 0;text-align:center;">'
                f'<div style="font-size:16px;font-weight:900;color:{TRAFFIC_RED};">⛔ 月虧損警示</div>'
                f'<div style="font-size:13px;color:#c9d1d9;margin-top:6px;">'
                f'本月虧損已達 {abs(_monthly_loss):.1f}%，建議暫停操作 7 天<br>'
                f'冷靜後重新評估選股邏輯</div></div>',
                unsafe_allow_html=True)

        st.markdown('<hr style="border-color:#21262d;margin:12px 0;">', unsafe_allow_html=True)
    elif not do_refresh:
        # v18.334:抓取進行中不顯示「點擊載入」空狀態(與標題一致,載入時只留 spinner)
        st.info('📡 點擊「🚀 一鍵更新全部數據」載入今日作戰室')
        st.markdown('<hr style="border-color:#21262d;margin:12px 0;">', unsafe_allow_html=True)
