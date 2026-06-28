"""src/ui/tabs/macro/section_cross_ai.py — Section 九 跨桶 AI 投資決策(B-S8-B 抽出,P2 v18.389 rename)。

🧠 跨桶｜總經 AI 投資決策分析(五維度卡:景氣位階 / 配置 / 貨幣 / 美股 / 結論)

closure params(explicit pass):
- tech_s: dict  美股 calc_stats 結果(SOX / NVDA / 大盤 TWII)
- tw_s:   dict  台股 calc_stats 結果(台股加權指數 fallback)

session_state 讀(0 寫):
- macro_info     §八 警示看板原始(_m8_vix/_m8_pmi/_m8_exp/_m8_cpi 來源)
- m1b_m2_info    M1B/M2 YoY + Gap
- bias_info      年線乖離(bias_240)

備註:本檔的 'ai' 桶群組 banner 同時 group §九 + §十一,故 banner setup 留在本檔
頭部(原 tab_macro:2233-2235),§十一 render_section_news_ai() 在外層接續呼叫,不重複 emit。
"""
from __future__ import annotations

import streamlit as st

from shared.colors import TRAFFIC_GREEN, TRAFFIC_RED, TRAFFIC_YELLOW
from src.ui.render.macro_ui_components import section_header


def render_section_cross_ai(tech_s: dict, tw_s: dict) -> None:
    """渲染§九 跨桶 AI 投資決策分析(原 tab_macro line 2233-2452)。"""
    # v18.310 桶群組 banner：AI 綜合(跨桶 AI §九 + 新聞 AI 裁決 §十一)
    from shared.macro_buckets import bucket_group_banner_html as _bgb
    st.markdown(_bgb('ai', 6), unsafe_allow_html=True)
    st.markdown(section_header('九', '🧠 跨桶｜總經 AI 投資決策分析', '🧠'), unsafe_allow_html=True)

    # ── 安全取數 ────────────────────────────────────────────────
    # v18.388:B-4 (1ee60c3) 把 _m8_* 隨 §八 section 抽至 section_mid local,§九 此處
    # 仍 reference → render 期 NameError。重抓 macro_info 以保持與 section_mid:58-64 同源。
    _macro_info_for_s9 = st.session_state.get('macro_info') or {}
    _m8_vix = _macro_info_for_s9.get('vix')
    _m8_pmi = _macro_info_for_s9.get('ism_pmi')
    _m8_exp = _macro_info_for_s9.get('tw_export')
    _m8_cpi = _macro_info_for_s9.get('us_core_cpi')
    _ai_vix  = float(_m8_vix.get('current', 0))  if _m8_vix else None
    _ai_vma  = float(_m8_vix.get('ma20', 0))     if _m8_vix else None
    _ai_is_cli = bool(_m8_pmi.get('is_oecd_cli', False)) if _m8_pmi else False
    _ai_cli  = float(_m8_pmi.get('value', 100))  if (_m8_pmi and _ai_is_cli) else None
    _ai_pmi  = float(_m8_pmi.get('value', 50))   if (_m8_pmi and not _ai_is_cli) else None
    _ai_exp  = float(_m8_exp.get('yoy', 0))      if _m8_exp else None
    _ai_cpi  = float(_m8_cpi.get('yoy', 0))      if _m8_cpi else None
    _ai_mi8  = st.session_state.get('m1b_m2_info') or {}
    _ai_m1b  = float(_ai_mi8['m1b_yoy']) if _ai_mi8.get('m1b_yoy') is not None else None
    _ai_m2   = float(_ai_mi8['m2_yoy'])  if _ai_mi8.get('m2_yoy') is not None else None
    _ai_gap  = round(_ai_m1b - _ai_m2, 2) if (_ai_m1b is not None and _ai_m2 is not None) else None
    _ai_bias = float(st.session_state.get('bias_info', {}).get('bias_240', 0))
    _ai_sox  = float((tech_s.get('費城半導體 SOX') or {}).get('pct') or 0)
    _ai_nvda = float((tech_s.get('輝達 NVDA') or {}).get('pct') or 0)
    _ai_twii_pct = float((tech_s.get('大盤 TWII') or tw_s.get('台股加權指數') or {}).get('pct') or 0)

    # ── ① 目前總經位階 ──────────────────────────────────────────
    _ai1_lbl, _ai1_clr, _ai1_desc, _ai1_cyc = '資料載入中', '#484f58', '請點擊更新總經拼圖', None
    _cycle_ref = _ai_cli if _ai_cli is not None else (_ai_pmi if _ai_pmi is not None else None)
    _cycle_exp = (_cycle_ref >= 100.0) if (_ai_cli is not None) else (_cycle_ref >= 50.0 if _cycle_ref is not None else None)
    if _ai_exp is not None:
        _exp_str = f'外銷訂單YoY={_ai_exp:+.1f}%'
        _cli_str = (f'OECD CLI={_ai_cli:.2f}' if _ai_cli is not None else
                    f'台灣 PMI={_ai_pmi:.1f}' if _ai_pmi is not None else '')
        if _cycle_exp and _ai_exp >= 10:
            _ai1_lbl, _ai1_clr, _ai1_cyc = '景氣擴張強勢期 📈', TRAFFIC_RED, 'bull'
            _ai1_desc = f'{_cli_str}（擴張）× {_exp_str}（強勁需求）— 主升段格局，基本面充分支撐'
        elif _cycle_exp and _ai_exp > 0:
            _ai1_lbl, _ai1_clr, _ai1_cyc = '景氣溫和擴張 🟢', TRAFFIC_GREEN, 'bull'
            _ai1_desc = f'{_cli_str}（擴張）× {_exp_str}— 穩步復甦，基本面有撐，持股安全'
        elif _cycle_exp and _ai_exp <= 0:
            _ai1_lbl, _ai1_clr, _ai1_cyc = '景氣高峰震盪 ⚡', TRAFFIC_YELLOW, 'peak'
            _ai1_desc = f'{_cli_str}（微擴張）× {_exp_str}— 高位整理，需求疲軟，留意反轉訊號'
        elif not _cycle_exp and _ai_exp >= 5:
            _ai1_lbl, _ai1_clr, _ai1_cyc = '景氣觸底回升 💎', '#58a6ff', 'recovery'
            _ai1_desc = f'{_cli_str}（收縮但出口反彈）× {_exp_str}— 左側佈局黃金窗口'
        elif not _cycle_exp and _ai_exp < 0:
            _ai1_lbl, _ai1_clr, _ai1_cyc = '景氣收縮期 📉', '#8b949e', 'bear'
            _ai1_desc = f'{_cli_str}（收縮）× {_exp_str}— 多看少做，等待出口數據翻正'
        else:
            _ai1_lbl, _ai1_clr, _ai1_cyc = '景氣整理期 🟡', TRAFFIC_YELLOW, 'neutral'
            _ai1_desc = f'{_cli_str} × {_exp_str}— 方向待確認，保守持股'
    elif _cycle_ref is not None:
        _cli_str = f'OECD CLI={_ai_cli:.2f}' if _ai_cli is not None else f'台灣 PMI={_ai_pmi:.1f}'
        _ai1_lbl = '景氣擴張（出口待確認）' if _cycle_exp else '景氣趨緩（出口待確認）'
        _ai1_clr = TRAFFIC_GREEN if _cycle_exp else TRAFFIC_YELLOW
        _ai1_cyc = 'bull' if _cycle_exp else 'neutral'
        _ai1_desc = f'{_cli_str} — 外銷訂單數據載入中'

    # ── ② 建議配置 ──────────────────────────────────────────────
    _ai2_lbl, _ai2_clr, _ai2_desc = '計算中', '#484f58', '等待 VIX 及資金數據'
    if _ai_vix is not None:
        _r1_ok  = _ai_vix < 20
        _r2_exp = _ai_exp is not None and _ai_exp >= 10
        _r2_gap = _ai_gap is not None and _ai_gap >= 1.0
        _r2_cnt = int(_r2_exp) + int(_r2_gap)
        _r3_sox = _ai_sox >= 1.5 or _ai_nvda >= 2.0
        _r3_tw  = _ai_twii_pct > 0
        _r3_cnt = int(_r3_sox) + int(_r3_tw)
        _fuel_str = ((' 出口+' if _r2_exp else '') + (' M1B-M2+' if _r2_gap else '')).strip(' +') or '—'
        if not _r1_ok:
            _ai2_lbl, _ai2_clr = '⛔ 防禦模式 持股0~20%', TRAFFIC_RED
            _ai2_desc = f'VIX={_ai_vix:.1f}≥20，大環境風險偏高，現金為王，等待 VIX<20 才考慮進場'
        elif _r2_cnt >= 2 and _r3_cnt >= 1:
            _ai2_lbl, _ai2_clr = '🚀 積極進攻 持股80~100%', '#f0e040'
            _ai2_desc = f'VIX={_ai_vix:.1f}安全 × 燃料充足（{_fuel_str}）× 點火訊號啟動 — 三環齊備，重壓主流'
        elif _r2_cnt >= 1 and _r3_cnt >= 1:
            _ai2_lbl, _ai2_clr = '🔥 標準多頭 持股60~80%', TRAFFIC_RED
            _ai2_desc = f'VIX={_ai_vix:.1f}安全，燃料（{_fuel_str}）有效，順勢佈局強勢個股，跌破10MA停損'
        elif _r3_cnt >= 1:
            _ai2_lbl, _ai2_clr = '🛡️ 試探建倉 持股30~50%', TRAFFIC_YELLOW
            _ai2_desc = '短線點火訊號存在但燃料不足，打帶跑策略，見好就收，嚴設停損'
        else:
            _ai2_lbl, _ai2_clr = '⏸️ 保守觀望 持股30%以下', '#8b949e'
            _ai2_desc = '三環條件均不足，保留現金等待更明確訊號，避免追高'

    # ── ③ 目前貨幣流向 ──────────────────────────────────────────
    _ai3_lbl, _ai3_clr, _ai3_desc = '待取得 M1B/M2', '#484f58', '央行貨幣數據載入中'
    if _ai_gap is not None:
        _gap_str = f'M1B={_ai_m1b:.1f}% M2={_ai_m2:.1f}% Gap={_ai_gap:+.2f}%'
        if _ai_gap >= 2.0:
            _ai3_lbl, _ai3_clr = '🔥 熱錢大量流入股市', TRAFFIC_RED
            _ai3_desc = f'{_gap_str} — 黃金交叉大幅擴散，投機資金湧入，活絡貨幣遠超廣義貨幣'
        elif _ai_gap >= 1.0:
            _ai3_lbl, _ai3_clr = '✅ 資金動能轉強', TRAFFIC_GREEN
            _ai3_desc = f'{_gap_str} — 活絡資金超越廣義貨幣，熱錢進場訊號確立，行情可期'
        elif _ai_gap >= 0:
            _ai3_lbl, _ai3_clr = '🟡 資金溫和偏多', TRAFFIC_YELLOW
            _ai3_desc = f'{_gap_str} — M1B微幅領先，資金偏多但動能尚未爆發，需等待 Gap≥1% 確認'
        elif _ai_gap > -1.0:
            _ai3_lbl, _ai3_clr = '⚠️ 資金略偏保守', TRAFFIC_YELLOW
            _ai3_desc = f'{_gap_str} — M2相對偏高，部分資金仍停留在定存，股市吸引力不足'
        else:
            _ai3_lbl, _ai3_clr = '📉 資金明顯外逃', '#8b949e'
            _ai3_desc = f'{_gap_str} — 死亡交叉，資金轉向固定收益，股市失血，謹慎操作'
    elif _ai_m1b is not None:
        _ai3_lbl, _ai3_clr = f'M1B={_ai_m1b:.1f}% M2待取得', '#484f58'
        _ai3_desc = 'M2 數據未就緒，暫無法判斷 Gap'

    # ── ④ 美股動態 ──────────────────────────────────────────────
    _ai4_lbl, _ai4_clr, _ai4_desc = '待取得', '#484f58', 'VIX / CPI 數據載入中'
    if _ai_vix is not None:
        _cpi_ok  = _ai_cpi is None or _ai_cpi < 3.0
        _cpi_wrm = _ai_cpi is not None and 3.0 <= _ai_cpi < 4.0
        _cpi_hot = _ai_cpi is not None and _ai_cpi >= 4.0
        _cpi_s   = f' CPI={_ai_cpi:.1f}%' if _ai_cpi is not None else ''
        _sox_s   = f' SOX={_ai_sox:+.1f}%' if _ai_sox else ''
        _vma_s   = f' MA20={_ai_vma:.1f}' if _ai_vma else ''
        if _ai_vix < 20 and _cpi_ok and (_ai_sox >= 1.5 or _ai_nvda >= 2.0):
            _ai4_lbl, _ai4_clr = '🚀 美股強勢，科技領漲', TRAFFIC_RED
            _ai4_desc = f'VIX={_ai_vix:.1f}（恐慌低）{_sox_s}（半導體點火）{_cpi_s} — 台股跟漲機率高，可積極佈局科技'
        elif _ai_vix < 20 and _cpi_ok:
            _ai4_lbl, _ai4_clr = '🟢 美股平穩，降息預期支撐', TRAFFIC_GREEN
            _ai4_desc = f'VIX={_ai_vix:.1f}{_vma_s}（安全）{_cpi_s} — 無系統性風險，有利個股選股表現'
        elif _ai_vix < 20 and _cpi_wrm:
            _ai4_lbl, _ai4_clr = '🟡 美股震盪，通膨黏性制約', TRAFFIC_YELLOW
            _ai4_desc = f'VIX={_ai_vix:.1f}尚可但{_cpi_s}偏高 — Fed降息預期受壓，資金轉向謹慎，避免過度加槓桿'
        elif _ai_vix < 20 and _cpi_hot:
            _ai4_lbl, _ai4_clr = '⚠️ 美股承壓，Fed鷹派升溫', TRAFFIC_YELLOW
            _ai4_desc = f'VIX={_ai_vix:.1f}{_cpi_s}超標 — 高利率環境延續，外資提款風險升高，注意匯率走勢'
        elif _ai_vix < 30:
            _ai4_lbl, _ai4_clr = '🟡 美股波動加劇，謹慎操作', TRAFFIC_YELLOW
            _ai4_desc = f'VIX={_ai_vix:.1f}（警戒區間 20~30）{_vma_s} — 市場情緒不確定，控制倉位，勿追高'
        else:
            _ai4_lbl, _ai4_clr = '🔴 美股恐慌模式，流動性危機', TRAFFIC_RED
            _ai4_desc = f'VIX={_ai_vix:.1f}≥30 — 全球流動性急凍，強制防禦，任何技術面買訊均視為誘多'

    # ── ⑤ 結論 ──────────────────────────────────────────────────
    _ai5_pts = []
    if _ai1_cyc == 'bull':
        _ai5_pts.append('景氣擴張有基本面支撐')
    elif _ai1_cyc == 'recovery':
        _ai5_pts.append('景氣觸底，左側佈局機會')
    elif _ai1_cyc == 'peak':
        _ai5_pts.append('高位整理，防範反轉')
    elif _ai1_cyc == 'bear':
        _ai5_pts.append('景氣收縮，防禦優先')
    if _ai_gap is not None:
        if _ai_gap >= 1.0:
            _ai5_pts.append(f'M1B-M2 Gap=+{_ai_gap:.1f}% 資金動能正向共振')
        elif _ai_gap < 0:
            _ai5_pts.append('M1B-M2死亡交叉，貨幣資金外逃')
    if _ai_vix is not None:
        if _ai_vix < 15:
            _ai5_pts.append(f'VIX={_ai_vix:.1f} 極度平靜')
        elif _ai_vix < 20:
            _ai5_pts.append(f'VIX={_ai_vix:.1f} 安全窗口')
        elif _ai_vix >= 30:
            _ai5_pts.append(f'VIX={_ai_vix:.1f} 觸發危機，暫停攻擊')
    if _ai_bias >= 15:
        _ai5_pts.append(f'年線乖離+{_ai_bias:.1f}% 高估值需嚴設停損')
    elif _ai_bias <= -5:
        _ai5_pts.append(f'年線乖離{_ai_bias:.1f}% 超跌逢低佈局')
    if _ai_exp is not None:
        if _ai_exp >= 10:
            _ai5_pts.append(f'外銷訂單YoY={_ai_exp:+.1f}% 出口強勁')
        elif _ai_exp < -5:
            _ai5_pts.append(f'外銷訂單YoY={_ai_exp:+.1f}% 出口衰退警訊')

    if _ai5_pts:
        _ai5_txt = '；'.join(_ai5_pts) + '。'
        _bull_score = (int(_ai1_cyc in ('bull', 'recovery')) +
                       int(_ai_gap is not None and _ai_gap >= 1.0) +
                       int(_ai_vix is not None and _ai_vix < 20) +
                       int(_ai_exp is not None and _ai_exp >= 0))
        _bear_score = (int(_ai1_cyc == 'bear') +
                       int(_ai_gap is not None and _ai_gap < 0) +
                       int(_ai_vix is not None and _ai_vix >= 30))
        if _bull_score >= 3 and _bear_score == 0:
            _ai5_clr, _ai5_icon = TRAFFIC_GREEN, '✅ 整體偏多，積極操作'
        elif _bear_score >= 2 or (_ai_vix is not None and _ai_vix >= 30):
            _ai5_clr, _ai5_icon = TRAFFIC_RED, '🚨 整體偏空，防禦為主'
        elif _bull_score >= 2:
            _ai5_clr, _ai5_icon = TRAFFIC_YELLOW, '🟡 溫和偏多，精選個股'
        else:
            _ai5_clr, _ai5_icon = '#8b949e', '⏸️ 中性觀望，等待訊號'
    else:
        _ai5_txt  = '請點擊「更新總經拼圖」載入資料後自動生成結論。'
        _ai5_clr, _ai5_icon = '#484f58', '⏳ 等待資料'

    # ── 渲染五維度卡片 ────────────────────────────────────────────
    _aic1, _aic2, _aic3 = st.columns(3)
    def _ai_card(title, label, desc, color):
        return (f'<div style="background:#0d1117;border:1px solid {color}44;border-radius:8px;'
                f'padding:12px;min-height:110px;">'
                f'<div style="font-size:10px;color:#484f58;margin-bottom:4px;">{title}</div>'
                f'<div style="font-size:13px;font-weight:700;color:{color};line-height:1.3;">{label}</div>'
                f'<div style="font-size:11px;color:#8b949e;margin-top:6px;line-height:1.5;">{desc}</div>'
                f'</div>')
    with _aic1:
        st.markdown(_ai_card('① 目前總經位階', _ai1_lbl, _ai1_desc, _ai1_clr), unsafe_allow_html=True)
    with _aic2:
        st.markdown(_ai_card('② 建議配置', _ai2_lbl, _ai2_desc, _ai2_clr), unsafe_allow_html=True)
    with _aic3:
        st.markdown(_ai_card('③ 目前貨幣流向', _ai3_lbl, _ai3_desc, _ai3_clr), unsafe_allow_html=True)

    _aic4, _aic5 = st.columns(2)
    with _aic4:
        st.markdown(_ai_card('④ 美股動態', _ai4_lbl, _ai4_desc, _ai4_clr), unsafe_allow_html=True)
    with _aic5:
        st.markdown(
            f'<div style="background:#0d1117;border:2px solid {_ai5_clr};border-radius:8px;'
            f'padding:12px;min-height:110px;">'
            f'<div style="font-size:10px;color:#484f58;margin-bottom:4px;">⑤ 結論</div>'
            f'<div style="font-size:14px;font-weight:900;color:{_ai5_clr};">{_ai5_icon}</div>'
            f'<div style="font-size:12px;color:#c9d1d9;margin-top:6px;line-height:1.6;">{_ai5_txt}</div>'
            f'</div>', unsafe_allow_html=True)
