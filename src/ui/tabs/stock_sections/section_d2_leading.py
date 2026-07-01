"""src/ui/tabs/stock_sections/section_d2_leading.py — D2. 基本面先行 6 大指標 section(v18.408 U4 Phase 3-D2).

從 tab_stock.py:1348-1561 抽出。
- 6 大先行指標 grid display(模組一~四,含對帳 chip + 來源 chip)
- 動態投資建議(基於指標合成 stance:bull / bear / neutral / event / na)

§8.2 layer:L5 UI Tab section helper(中-高風險:213 LOC + 4 module group display)。

對外 API:
- render_d2_leading_section(rev2, qtr2, qtr_extra2) -> None
"""
from __future__ import annotations

import logging as _li_log

import streamlit as st

from shared.colors import TRAFFIC_GREEN, TRAFFIC_RED, TRAFFIC_YELLOW

_logger = _li_log.getLogger(__name__)

# 各模組白話說明（D12:新手友善說明文字）
_LI_MODULE_DESCS = {
    '模組一': '月營收年增率（YoY%）走勢與加速度，可比股價早 1-3 個月反映業績轉向',
    '模組二': '合約負債（預收款）預示未來營收；資本支出方向反映管理層擴產意願',
    '模組三': '存貨去化速度；快速下降代表需求上升，常為景氣回暖前兆',
    '模組四': '籌碼集中度與外資動向，主力積累往往出現在股價啟動之前',
}


def render_d2_leading_section(rev2, qtr2, qtr_extra2) -> None:
    """D2. 基本面先行指標(6 大指標 + 動態投資建議)。

    Args:
        rev2: 月營收 DataFrame
        qtr2: 季財報 DataFrame
        qtr_extra2: 季 BS/CF 時序 DataFrame
    """
    # ══ D2. 基本面先行指標(6大指標)══════════════════════
    st.markdown('---')
    st.markdown('#### 🔬 D2. 基本面先行指標（6大指標）')

    # B10: 計算一次，grid + 建議兩處共用，避免雙倍 FinMind API 請求
    _li_results = None
    try:
        from src.compute.scoring import calc_leading_indicators_detail as _cli_fn
        _li_results = _cli_fn(rev_df=rev2, qtr_df=qtr2, bs_cf_df=qtr_extra2)
    except Exception as _eli_err:
        _logger.warning('[先行指標-D2] 指標計算失敗: %s', _eli_err)

    # ── 分模組 grid 顯示 ──────────────────────────────
    if _li_results is not None:
        try:
            _li_green = sum(1 for _r in _li_results if _r['signal'] == '🟢')
            _li_yellow = sum(1 for _r in _li_results if _r['signal'] == '🟡')
            _li_red = sum(1 for _r in _li_results if _r['signal'] == '🔴')
            _li_total_scored = _li_green + _li_yellow + _li_red
            if _li_total_scored > 0:
                _li_bar_c = TRAFFIC_GREEN if _li_green >= _li_total_scored * 0.6 else (
                             TRAFFIC_YELLOW if _li_green >= _li_total_scored * 0.3 else TRAFFIC_RED)
                st.markdown(
                    f'<div style="background:#0d1117;border-left:3px solid {_li_bar_c};'
                    f'padding:6px 12px;border-radius:0 6px 6px 0;margin:4px 0 8px 0;">'
                    f'<span style="font-size:11px;color:#8b949e;">📊 基本面先行指標總覽</span>　'
                    f'<span style="font-size:13px;font-weight:700;color:{_li_bar_c};">'
                    f'🟢×{_li_green}  🟡×{_li_yellow}  🔴×{_li_red}</span>'
                    f'</div>', unsafe_allow_html=True
                )
            # 分模組顯示
            _li_modules = {}
            for _r in _li_results:
                _li_modules.setdefault(_r['module'], []).append(_r)
            _li_module_list = ['模組一', '模組二', '模組三', '模組四']
            _li_module_labels = {
                '模組一': '📈 模組一：高頻業績前瞻（月營收）',
                '模組二': '🏗️ 模組二：資產負債前瞻（季頻）',
                '模組三': '📦 模組三：存貨週期',
                '模組四': '👔 模組四：籌碼深度前瞻',
            }
            _li_col1, _li_col2 = st.columns(2)
            _li_cols = [_li_col1, _li_col2]
            _li_col_idx = 0
            for _mod in _li_module_list:
                if _mod not in _li_modules:
                    continue
                with _li_cols[_li_col_idx % 2]:
                    st.markdown(f'**{_li_module_labels.get(_mod, _mod)}**')
                    # D12: 白話說明，讓新手也能快速理解各模組用途
                    _mod_desc = _LI_MODULE_DESCS.get(_mod)
                    if _mod_desc:
                        st.caption(_mod_desc)
                    for _ind in _li_modules[_mod]:
                        _ic = (TRAFFIC_GREEN if _ind['signal'] == '🟢' else
                               TRAFFIC_YELLOW if _ind['signal'] == '🟡' else
                               TRAFFIC_RED if _ind['signal'] == '🔴' else '#8b949e')
                        # S-RECON-1 v18.303: 月營收 YoY 對帳 chip
                        # I1 carries `reconcile` dict when self_calc vs FinMind 都有值
                        _recon_chip = ''
                        _rec = _ind.get('reconcile') if isinstance(_ind, dict) else None
                        if _rec is not None:
                            _rec_status = _rec.get('status', '')
                            _rec_a = _rec.get('value_a')
                            _rec_b = _rec.get('value_b')
                            if _rec_status == 'agree':
                                _recon_chip = (
                                    f'<div style="font-size:10px;color:{TRAFFIC_GREEN};margin-top:2px;">'
                                    f'✅ 雙源對帳:自算 {_rec_a:+.2f}% ≈ FinMind {_rec_b:+.2f}%'
                                    f'</div>'
                                )
                            elif _rec_status == 'disagree':
                                _recon_chip = (
                                    f'<div style="font-size:10px;color:{TRAFFIC_YELLOW};margin-top:2px;">'
                                    f'⚠️ 雙源分歧:自算 {_rec_a:+.2f}% vs FinMind {_rec_b:+.2f}%'
                                    f' (Δ={_rec.get("delta_abs",0):.2f}pct)'
                                    f'</div>'
                                )
                        # S-PROV-1 PR-J1 v18.338: 資料來源 chip(§2.2 provenance)
                        _src_chip = ''
                        _src = _ind.get('source_chain') if isinstance(_ind, dict) else None
                        if _src:
                            _src_chip = (
                                f'<div style="font-size:10px;color:#6e7681;margin-top:2px;'
                                f'font-style:italic;">📡 來源:{_src}</div>'
                            )
                        st.markdown(
                            f'<div style="background:#0d1117;border-left:3px solid {_ic};'
                            f'padding:6px 10px;border-radius:0 4px 4px 0;margin:3px 0;">'
                            f'<div style="font-size:12px;font-weight:700;color:{_ic};">'
                            f'{_ind["signal"]} {_ind["name"]}</div>'
                            f'<div style="font-size:11px;color:#e6edf3;margin:1px 0;">{_ind["value"]}</div>'
                            f'<div style="font-size:10px;color:#8b949e;">{_ind["detail"]}</div>'
                            f'{_recon_chip}'
                            f'{_src_chip}'
                            f'</div>', unsafe_allow_html=True
                        )
                _li_col_idx += 1
        except Exception as _eli_err:
            _logger.warning('[先行指標-D2] 顯示錯誤: %s', _eli_err, exc_info=True)

    # ── D2 動態投資建議(基於6大先行指標合成)──────────────
    if _li_results is not None:
        try:
            _li2 = _li_results  # B10: 重用已計算的結果，不重複呼叫 API
            _li2_map = {r['id']: r for r in _li2}

            # ── 蒐集信號 ─────────────────────────────────────
            _pros = []   # 多方理由
            _cons = []   # 空方理由
            _notes = []  # 注意事項(事件驅動/中性)
            _event_driven_flags = []

            # I1 月營收YoY加速
            _r1 = _li2_map.get('I1', {})
            if _r1.get('signal') == '🟢':
                _pros.append(f"月營收YoY連續加速（{_r1.get('value','').split(':')[-1].strip()}），業績動能確立")
            elif _r1.get('signal') == '🔴':
                _cons.append('月營收年減中，基本面走弱')

            # I2 均線交叉
            _r2 = _li2_map.get('I2', {})
            if _r2.get('signal') == '🟢':
                _pros.append(f"月營收3M均線位於12M均線之上（{_r2.get('value','').split(':')[-1].strip()}），中期動能向上")
            elif _r2.get('signal') == '🔴':
                _cons.append('月營收均線死叉，中期趨勢轉弱')

            # I3 合約負債
            _r3 = _li2_map.get('I3', {})
            if _r3.get('signal') == '🟢':
                _v3 = _r3.get('value', '')
                _pros.append(f"合約負債持續增加（{_v3}），未來營收能見度高")
            elif _r3.get('signal') == '🔴':
                _cons.append('合約負債減少，訂單能見度下降')

            # I4 CapEx(含事件驅動判斷)
            _r4 = _li2_map.get('I4', {})
            if '事件驅動' in _r4.get('detail', ''):
                _event_driven_flags.append('資本支出比較基期因重大資產處分失真')
                _notes.append(f"⚠️ CapEx：{_r4.get('detail','')}")
            elif _r4.get('signal') == '🟢':
                _pros.append(f"資本支出強度提升（{_r4.get('value','')}），積極擴產佈局未來")
            elif _r4.get('signal') == '🔴':
                _cons.append(f"資本支出大幅縮減（{_r4.get('value','')}），擴張意願低")

            # I5 存貨去化(含事件驅動)
            _r5 = _li2_map.get('I5', {})
            if '事件驅動' in _r5.get('detail', ''):
                _event_driven_flags.append('存貨急降原因待確認（資產處分可能帶走存貨）')
                _notes.append(f"⚠️ 存貨：{_r5.get('detail','')}")
            elif _r5.get('signal') == '🟢':
                _pros.append(f"存貨持續去化（{_r5.get('value','')}），供需關係改善")
            elif _r5.get('signal') == '🔴':
                _cons.append(f"存貨積壓風險（{_r5.get('value','')}），景氣下行壓力")

            # ── 綜合評估 ────────────────────────────────────
            _n_green = sum(1 for r in _li2 if r['signal'] == '🟢')
            _n_red = sum(1 for r in _li2 if r['signal'] == '🔴')
            _n_scored = sum(1 for r in _li2 if r['signal'] in ('🟢', '🟡', '🔴'))

            if _event_driven_flags:
                _stance = 'event'
                _stance_label = '⚠️ 事件驅動觀察'
                _stance_color = TRAFFIC_YELLOW
                _stance_desc = '偵測到重大資產處分，部分指標基期失真。建議關注重組後的資本配置方向與營運重啟節奏，暫不適用純基本面成長框架評估。'
            elif _n_scored == 0:
                _stance = 'na'
                _stance_label = '⚪ 資料不足'
                _stance_color = '#8b949e'
                _stance_desc = '基本面先行指標資料尚未完整載入，無法生成投資建議。'
            elif _n_green >= _n_scored * 0.6:
                _stance = 'bull'
                _stance_label = '🟢 多方偏多'
                _stance_color = TRAFFIC_GREEN
                _stance_desc = f'{_n_green}/{_n_scored} 項指標偏多，基本面動能強勁。'
            elif _n_red >= _n_scored * 0.6:
                _stance = 'bear'
                _stance_label = '🔴 基本面偏弱'
                _stance_color = TRAFFIC_RED
                _stance_desc = f'{_n_red}/{_n_scored} 項指標偏空，基本面壓力明顯。'
            else:
                _stance = 'neutral'
                _stance_label = '🟡 中性觀察'
                _stance_color = TRAFFIC_YELLOW
                _stance_desc = f'多空指標交錯（🟢{_n_green}/🔴{_n_red}），基本面尚未形成明確方向。'

            # ── 建議行動 ────────────────────────────────────
            _action_map = {
                'bull':    '基本面動能向上，可搭配技術面（VCP/布林）確認進場時機，適合中長線佈局。',
                'bear':    '基本面呈現壓力，建議降低曝險或觀望，等待指標轉向後再評估。',
                'neutral': '基本面方向尚不明朗，建議輕倉或等待更多季度數據確認後再行動。',
                'event':   '轉機股需追蹤：①後續資本支出重建節奏 ②新業務（如HBM後段）訂單能見度 ③毛利率是否回升至正常水位。',
                'na':      '請確認 FINMIND_TOKEN 是否正確，並重新載入後查看建議。',
            }
            _action = _action_map.get(_stance, '')

            # ── 渲染 ────────────────────────────────────────
            _pros_html = ''.join(f'<li style="margin:2px 0;">✅ {p}</li>' for p in _pros) if _pros else ''
            _cons_html = ''.join(f'<li style="margin:2px 0;">⛔ {c}</li>' for c in _cons) if _cons else ''
            _notes_html = ''.join(f'<li style="margin:2px 0;">{n}</li>' for n in _notes) if _notes else ''

            _pros_section = (f'<div style="margin-top:6px;"><span style="font-size:11px;color:{TRAFFIC_GREEN};font-weight:600;">多方因素</span>'
                              f'<ul style="margin:2px 0 0 12px;padding:0;font-size:11px;color:#e6edf3;">{_pros_html}</ul></div>') if _pros_html else ''
            _cons_section = (f'<div style="margin-top:4px;"><span style="font-size:11px;color:{TRAFFIC_RED};font-weight:600;">風險因素</span>'
                              f'<ul style="margin:2px 0 0 12px;padding:0;font-size:11px;color:#e6edf3;">{_cons_html}</ul></div>') if _cons_html else ''
            _notes_section = (f'<div style="margin-top:4px;"><span style="font-size:11px;color:{TRAFFIC_YELLOW};font-weight:600;">注意事項</span>'
                              f'<ul style="margin:2px 0 0 12px;padding:0;font-size:11px;color:#8b949e;">{_notes_html}</ul></div>') if _notes_html else ''

            st.markdown(
                f'<div style="background:#161b22;border:1px solid {_stance_color};border-left:4px solid {_stance_color};'
                f'padding:10px 14px;border-radius:6px;margin:8px 0;">'
                f'<div style="font-size:12px;color:#8b949e;margin-bottom:4px;">💡 基本面先行指標 · 動態投資建議</div>'
                f'<div style="font-size:15px;font-weight:700;color:{_stance_color};">{_stance_label}</div>'
                f'<div style="font-size:12px;color:#e6edf3;margin-top:4px;">{_stance_desc}</div>'
                f'{_pros_section}{_cons_section}{_notes_section}'
                f'<div style="margin-top:8px;padding-top:6px;border-top:1px solid #30363d;">'
                f'<span style="font-size:11px;color:#8b949e;">📌 建議行動：</span>'
                f'<span style="font-size:12px;color:#e6edf3;">{_action}</span>'
                f'</div>'
                f'</div>', unsafe_allow_html=True
            )
        except Exception as _eli2_err:
            _logger.warning('[先行指標-建議] 顯示錯誤: %s', _eli2_err, exc_info=True)
