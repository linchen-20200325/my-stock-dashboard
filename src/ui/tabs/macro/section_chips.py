"""src/ui/tabs/macro/section_chips.py — Section 3(§三)大戶籌碼全貌 v18.388(B-S8-A 抽出)。

🧩 籌碼｜🧮 大戶籌碼全貌：法人聰明錢 × 融資融券 × 先行指標

closure params(explicit pass,§-1 minimal):
- inst: dict  三大法人 net/buy/sell({外資/陸資, 投信, 自營商: {'net': ...}})
- margin: number | None  融資餘額(億元)
- cd: dict  _job_macro 回傳的合併結果(用來偵測「是否曾嘗試載入」)
"""
from __future__ import annotations

import streamlit as st

from shared.colors import (
    TRAFFIC_GREEN, TRAFFIC_NEUTRAL, TRAFFIC_RED, TRAFFIC_YELLOW,
)
from shared.signal_thresholds import (
    MARGIN_BALANCE_OVERHEAT_THRESHOLD_YI,
    MARGIN_BALANCE_WARN_THRESHOLD_YI,
)
from src.compute.strategy import V4StrategyEngine
from src.data.macro import render_leading_table
from src.ui.render.macro_ui_components import section_header
from src.ui.render.ui_widgets import teacher_conclusion
from src.ui.tabs.tab_helpers import safe_get


def render_section_chips(inst: dict, margin, cd: dict) -> None:
    """渲染§三 籌碼桶(原 tab_macro line 2229-2788)。"""
    import os
    import pandas as pd

    # ════════════════════════════════════════════════════════════════════
    # 三、大戶籌碼全貌：法人聰明錢 × 融資融券 × 先行指標
    # ════════════════════════════════════════════════════════════════════
    from shared.macro_buckets import bucket_group_banner_html as _bgb  # v18.310 桶群組 banner
    st.markdown(_bgb('chips', 4), unsafe_allow_html=True)
    st.markdown(section_header('三','🧩 籌碼｜🧮 大戶籌碼全貌：法人聰明錢 × 融資融券 × 先行指標','🧮'),unsafe_allow_html=True)

    # ── v18.336 §1 Fail Loud：三源(法人/融資/先行指標)全空時明確診斷,不靜默空白 ──
    # user 2026-06-28「§三 籌碼 資料不見了」：三源在缺 FINMIND_TOKEN / 來源無回應時全敗,
    # 原本 `if inst:` / `if margin:` 靜默跳過 → 整區空白。改為:全空時印診斷卡指出原因 + 救法。
    _li_probe3 = st.session_state.get('li_latest')
    _chips_all_empty3 = (not inst) and (not margin) and (
        _li_probe3 is None or getattr(_li_probe3, 'empty', True))
    if _chips_all_empty3:
        from shared.macro_buckets import chips_empty_state_html as _ces3
        _attempted3 = bool(st.session_state.get('cl_ts')) or bool(
            st.session_state.get('chips_loaded'))
        try:
            _fm_present3 = bool((getattr(st, 'secrets', {}) or {}).get('FINMIND_TOKEN')
                                or os.environ.get('FINMIND_TOKEN', ''))
        except Exception:
            _fm_present3 = bool(os.environ.get('FINMIND_TOKEN', ''))
        st.markdown(_ces3(attempted=_attempted3, token_present=_fm_present3),
                    unsafe_allow_html=True)

    if inst:
        _fk3 = next((k for k in inst if '外資' in k and '陸資' in k), None) or next((k for k in inst if '外資' in k), None)
        _tk3 = next((k for k in inst if '投信' in k), None)
        _fn3 = inst[_fk3]['net'] if _fk3 else 0
        _tn3 = inst[_tk3]['net'] if _tk3 else 0
        if _fn3 >= 100:
            _hye_c = TRAFFIC_GREEN
            _hye_ind = f'外資大買超 {_fn3:.1f}億'
            _hye_concl = '大戶點火，跟著大戶走 → 積極加碼'
            _hye_act = '趁拉回布局，持股 80~100%'
        elif _fn3 <= -100:
            _hye_c = TRAFFIC_RED
            _hye_ind = f'外資大賣超 {abs(_fn3):.1f}億'
            _hye_concl = '大戶倒貨，嚴格減碼 → 離場為上'
            _hye_act = '持股降至 0~30%，停損優先'
        else:
            _hye_c = '#8b949e'
            _hye_ind = f'外資 {_fn3:+.1f}億（觀望區間）'
            _hye_concl = '資金觀望，區間操作'
            _hye_act = '持股 50%，高出低進等方向'
        st.markdown(teacher_conclusion('宏爺', _hye_ind, _hye_concl, color=_hye_c), unsafe_allow_html=True)
        st.markdown(f'<div style="color:#8b949e;font-size:11px;padding:1px 8px 6px 8px;">→ 建議行動：{_hye_act}</div>', unsafe_allow_html=True)
        if _tn3 > 5:
            st.markdown(f'<div style="color:#58a6ff;font-size:12px;padding:2px 6px;">• 投信買超 {_tn3:.1f}億 → 連續買超是加碼訊號</div>', unsafe_allow_html=True)
        # 三大法人買賣超柱狀圖（直接用 plotly，繞過 st.bar_chart→altair 相容性問題）
        _zk3 = next((k for k in inst if '自營' in k), None)
        _bc_vals = [float(_fn3 or 0),
                    float(_tn3 or 0),
                    float((inst.get(_zk3) or {}).get('net', 0) or 0)]
        _bc_colors = ['#58a6ff' if v >= 0 else TRAFFIC_RED for v in _bc_vals] + \
                     [TRAFFIC_GREEN if _bc_vals[1] >= 0 else TRAFFIC_RED,
                      '#ffd700' if _bc_vals[2] >= 0 else TRAFFIC_RED]
        _bc_colors = ['#58a6ff' if _bc_vals[0] >= 0 else TRAFFIC_RED,
                      TRAFFIC_GREEN if _bc_vals[1] >= 0 else TRAFFIC_RED,
                      '#ffd700' if _bc_vals[2] >= 0 else TRAFFIC_RED]
        try:
            import plotly.graph_objects as _go_bc
            _fig_bc = _go_bc.Figure(_go_bc.Bar(
                x=['外資', '投信', '自營商'], y=_bc_vals,
                marker_color=_bc_colors, text=[f'{v:+.1f}億' for v in _bc_vals],
                textposition='outside'))
            _fig_bc.update_layout(
                height=200, margin=dict(t=30, b=10, l=10, r=10),
                paper_bgcolor='#0d1117', plot_bgcolor='#0d1117',
                font=dict(color='#e6edf3', size=12),
                yaxis=dict(showgrid=False, zeroline=True,
                           zerolinecolor='#484f58', showticklabels=False))
            st.plotly_chart(_fig_bc, use_container_width=True,
                            config={'displayModeBar': False})
        except Exception as _bc_err:
            st.caption(f'外資 {_bc_vals[0]:+.1f}億 ｜ 投信 {_bc_vals[1]:+.1f}億 ｜ 自營商 {_bc_vals[2]:+.1f}億')
    if margin:
        if margin >= MARGIN_BALANCE_OVERHEAT_THRESHOLD_YI:
            _sql_mc = TRAFFIC_RED
            _sql_mind = f'融資餘額 {margin:.0f}億'
            _sql_mconcl = '極度危險，嚴防多殺多 → 行情尾端'
            _sql_mact = '全面減碼，勿追高，準備逃命'
        elif margin >= MARGIN_BALANCE_WARN_THRESHOLD_YI:
            _sql_mc = TRAFFIC_YELLOW
            _sql_mind = f'融資餘額 {margin:.0f}億'
            _sql_mconcl = '水位偏高，籌碼凌亂 → 警戒操作'
            _sql_mact = '持股降至 50% 以下，避免重倉'
        else:
            _sql_mc = TRAFFIC_GREEN
            _sql_mind = f'融資餘額 {margin:.0f}億'
            _sql_mconcl = '籌碼乾淨，安全水位 → 可積極布局'
            _sql_mact = '健康多頭格局，持股 70~100%'
        st.markdown(teacher_conclusion('孫慶龍', _sql_mind, _sql_mconcl, color=_sql_mc), unsafe_allow_html=True)
        st.markdown(f'<div style="color:#8b949e;font-size:11px;padding:1px 8px 6px 8px;">→ 建議行動：{_sql_mact}</div>', unsafe_allow_html=True)
    st.markdown('<hr style="border-color:#21262d;margin:10px 0;">', unsafe_allow_html=True)

    # ── 宏爺外資期貨（先行指標快速結論）─────────────────────────────────
    _li4 = st.session_state.get('li_latest')
    if _li4 is not None and not _li4.empty:
        _fut4 = (float(_li4.iloc[-1].get('外資大小', 0)) if '外資大小' in _li4.columns else None)
        _pcr4 = (float(_li4.iloc[-1].get('選PCR', 0)) if '選PCR' in _li4.columns else None)
        if _fut4 is not None:
            _pcr_txt = f' | PCR {_pcr4:.1f}' if _pcr4 else ''
            _l4_ind = f'外資期貨 {_fut4:,.0f}口{_pcr_txt}'
            # 宏爺絕對口數門檻（容錯率最高）
            if _fut4 <= -30000:
                _l4c = f'外資期貨空單 {abs(_fut4):,.0f}口 > 3萬口，啟動強制防禦，強制減倉至20%以下，等待空單回補'
                _l4a = '強制減倉至 20% 以下，嚴禁追高攤平，保護本金'
            elif _fut4 <= -15000:
                _l4c = f'外資期貨空單 {abs(_fut4):,.0f}口，空單累積中，大戶動向保守，逢高調節'
                _l4a = '收回資金，持股降至 50%，等待明確表態'
            elif _fut4 > 0:
                _l4c = f'外資期貨多單 {_fut4:,.0f}口，外資期貨翻多，燃料充足，積極作多'
                _l4a = '順勢重壓強勢股，持股 80~100%'
            else:
                _l4c = f'外資期貨微空 {abs(_fut4):,.0f}口，水位正常，依個股技術面操作'
                _l4a = '持股 70%，現金 30% 備用'
        else:
            _l4c = '先行指標欄位異常，請確認 FinMind Token'
            _l4a = ''
            _l4_ind = '外資期貨留倉'
    else:
        _l4c = '先行指標尚未載入，請點擊「🚀 一鍵更新全部數據」'
        _l4a = ''
        _l4_ind = '外資期貨留倉'
    # v18.336：三源全空時上方已有 fail-loud 診斷卡,此處不重複「尚未載入」(避免點過更新仍喊更新)
    if not _chips_all_empty3:
        st.markdown(teacher_conclusion('宏爺', _l4_ind, _l4c, _l4a), unsafe_allow_html=True)

    # ── 副標籤：欄位確認列（v12 風格）─────────────────────────────────
    st.markdown("""<div style="font-size:11px;color:#484f58;margin:-6px 0 10px 0;">
✅ 外資期貨留倉口數 &nbsp;｜&nbsp; ✅ 前五大/前十大交易人 &nbsp;｜&nbsp; ✅ 外資選擇權金額 &nbsp;｜&nbsp; ✅ 韭菜指數 &nbsp;｜&nbsp; ✅ PCR
</div>""", unsafe_allow_html=True)

    # 先行指標隨更新大盤自動載入（執行緒快取版，build_leading_fast）
    df_li_show = st.session_state.get('li_latest')

    if df_li_show is not None and not df_li_show.empty:
        # v18.342 PR-L2:預存 is_stale 旗標(copy 前讀,copy 後 attrs 可能丟失)
        _is_stale_li = bool(getattr(df_li_show, 'attrs', {}).get('is_stale', False))
        _stale_age_li = getattr(df_li_show, 'attrs', {}).get('stale_age_min')
        # 向前填補 NaN（各欄位用最後一次有效數值補齊，避免 API 部分失敗造成空格）
        _li_num_cols = [c for c in df_li_show.columns if c != '日期']
        df_li_show = df_li_show.copy()
        df_li_show[_li_num_cols] = df_li_show[_li_num_cols].ffill()

        # ── ① 資料期間 caption ─────────────────────────────────────────
        _li_dates = df_li_show['日期'].tolist() if '日期' in df_li_show.columns else []
        if _li_dates:
            _d0 = _li_dates[0]
            _d1 = _li_dates[-1]
            st.caption(
                f'📅 資料期間：{_d0} ~ {_d1}  共 {len(df_li_show)} 筆  '
                f'｜外資空單>3萬⚠️  前五大>1萬⚠️  PCR<100偏空'
            )
            # v18.342 PR-L2:stale fallback 顯示「📦 上次有效資料」chip(§2.4)
            if _is_stale_li:
                _age_txt = f'{_stale_age_li:.0f} 分鐘前' if isinstance(
                    _stale_age_li, (int, float)) else '較早'
                st.markdown(
                    f'<div style="display:inline-block;font-size:11px;color:#f0883e;'
                    f'background:#0d1117;border:1px solid #f0883e;border-radius:4px;'
                    f'padding:3px 9px;margin:2px 0 8px 0;">'
                    f'📦 顯示上次有效資料({_age_txt}抓的)— 當次 FinMind 無新資料'
                    f'(週末/假日/API 額度) → 數值非今日最新</div>',
                    unsafe_allow_html=True)

        # S-PROV-1 UI chip v18.265 — provenance(source + fetched_at,從 df 末筆讀)
        try:
            _li_prov_src = None
            _li_prov_at = None
            if "source" in df_li_show.columns and not df_li_show.empty:
                _li_prov_src = str(df_li_show["source"].iloc[-1])
            if "fetched_at" in df_li_show.columns and not df_li_show.empty:
                _li_prov_at = str(df_li_show["fetched_at"].iloc[-1])[:19]
            if _li_prov_src or _li_prov_at:
                st.markdown(
                    f"<div style='font-size:10px;color:#888;padding:3px 8px;"
                    f"background:#0d1117;border-radius:4px;margin:2px 0 6px 0'>"
                    f"📍 來源:{_li_prov_src or '—'}　🕐 抓取:{_li_prov_at or '—'} UTC"
                    f"</div>",
                    unsafe_allow_html=True,
                )
        except Exception:
            pass

        # ── ② 主表格（render_leading_table，已內含深色主題CSS）──────────
        st.markdown(render_leading_table(df_li_show), unsafe_allow_html=True)

        # 欄位說明 → 已移至 Tab 5 策略手冊



        # ── ③ 進階警示訊號（依建議加入5個條件）──────────────────────────
        _last_row = df_li_show.iloc[-1] if not df_li_show.empty else {}
        _fut_net  = _last_row.get('外資大小')
        _pcr      = _last_row.get('選PCR')
        _opt_net  = _last_row.get('外(選)')
        _leek     = _last_row.get('韭菜指數')
        _foreign  = _last_row.get('外資')  # 現貨外資買賣
        _trust    = _last_row.get('投信')  # 投信買賣
        _warnings = []

        # 訊號 1：期權同向崩盤訊號（最強烈）
        # 期貨大空 + 選擇權外資淨空 → 不惜成本避險
        try:
            if _fut_net is not None and float(_fut_net) < -20000:
                if _opt_net is not None and float(_opt_net) < 0:
                    _warnings.append(('🔴', '期權同向崩盤警戒',
                        f'期貨空{abs(float(_fut_net)):,.0f}口 + 選擇權外資淨空{float(_opt_net):,.0f}千元',
                        '外資「不惜成本」雙向避險，高機率隨即殺盤，建議降倉至30%以下'))
                elif _fut_net is not None and float(_fut_net) < -30000:
                    _warnings.append(('🟡', '期貨大空警戒',
                        f'外資期貨空單 {abs(float(_fut_net)):,.0f} 口（>3萬口門檻）',
                        '注意流向：若每日持續增加空單才是真訊號；若空單縮減則危機解除'))
        except Exception:
            pass

        # 訊號 2：韭菜指數極端值
        try:
            if _leek is not None:
                _leek_f = float(_leek)
                if _leek_f > 30:
                    _warnings.append(('🔴', '散戶過度樂觀（韭菜極端多）',
                        f'法人空多比 +{_leek_f:.1f}%（超過+30%警戒線）',
                        '散戶一面倒看多，短線見頂訊號，主力容易在此出貨'))
                elif _leek_f < -30:
                    _warnings.append(('🟢', '軋空動能極強（韭菜極端空）',
                        f'法人空多比 {_leek_f:.1f}%（超過-30%機會線）',
                        '散戶爭相放空，軋空動能強，千萬不要在此放空，逆勢做多機會'))
        except Exception:
            pass

        # 訊號 3：外資投信同買（最強籌碼訊號）
        try:
            if _foreign is not None and _trust is not None:
                _f2 = float(_foreign)
                _t2 = float(_trust)
                if _f2 > 50 and _t2 > 5:
                    _warnings.append(('🟢', '外資投信同買（籌碼共鳴）',
                        f'外資+{_f2:.0f}億 + 投信+{_t2:.1f}億 同步買超',
                        '外投同買的股票漲幅連續性最強，現貨籌碼最乾淨'))
                elif _f2 < -100 and _t2 < -5:
                    _warnings.append(('🔴', '外資投信同賣（籌碼潰散）',
                        f'外資{_f2:.0f}億 + 投信{_t2:.1f}億 同步賣超',
                        '雙主力同步出場，下跌壓力沉重'))
        except Exception:
            pass

        # 訊號 4：PCR 極端值判斷
        try:
            if _pcr is not None:
                _pcr_f = float(_pcr)
                if _pcr_f < 80:
                    _warnings.append(('🔴', '選擇權Put/Call偏低（市場過樂觀）',
                        f'PCR={_pcr_f:.1f}（<80偏危險，市場保護不足）',
                        '選擇權市場無人買保護，通常出現在短線頂部'))
                elif _pcr_f > 150:
                    _warnings.append(('🟢', '選擇權Put/Call偏高（恐慌區）',
                        f'PCR={_pcr_f:.1f}（>150偏多，市場過度悲觀）',
                        '大量買保護代表市場恐慌，通常是逆向布局訊號'))
        except Exception:
            pass

        # 訊號 5：成交量萎縮（市場觀望）
        try:
            # P4: vectorized str → numeric，避免逐列 Python 呼叫
            _vols = (pd.to_numeric(
                df_li_show['成交量'].tail(5).astype(str).str.replace('億','', regex=False),
                errors='coerce').dropna().tolist()
                if '成交量' in df_li_show.columns else [])
            if len(_vols) >= 3:
                _avg_vol = sum(_vols[:-1]) / len(_vols[:-1])
                _last_vol = _vols[-1]
                if _last_vol < _avg_vol * 0.7:
                    _warnings.append(('🟡', '成交量急萎縮（市場觀望）',
                        f'今日成交量{_last_vol:.0f}億（前{len(_vols)-1}日均量{_avg_vol:.0f}億的{_last_vol/_avg_vol*100:.0f}%）',
                        '量縮超過30%代表市場觀望，方向選擇前勿輕易追高'))
                elif _last_vol > _avg_vol * 1.5:
                    _warnings.append(('🔵', '成交量急放（趨勢加速）',
                        f'今日成交量{_last_vol:.0f}億（前均量{_avg_vol:.0f}億的{_last_vol/_avg_vol*100:.0f}%）',
                        '成交量暴增50%以上，趨勢加速，注意是否配合方向'))
        except Exception:
            pass

        if _warnings:
            for _wc, _wt, _wd, _wa in _warnings:
                _wcolor = ('#2ea043' if _wc == '🟢' else
                           '#da3633' if _wc == '🔴' else
                           TRAFFIC_YELLOW if _wc == '🟡' else '#388bfd')
                st.markdown(
                    f'<div style="border-left:5px solid {_wcolor};background:#0d1117;'
                    f'padding:9px 14px;border-radius:0 8px 8px 0;margin:4px 0;">'
                    f'<span style="font-size:11px;color:{TRAFFIC_NEUTRAL};">⚡ 進階警示</span><br>'
                    f'<span style="font-size:14px;font-weight:900;color:{_wcolor};">{_wc} {_wt}</span><br>'
                    f'<span style="font-size:12px;color:#c9d1d9;">{_wd}</span><br>'
                    f'<span style="font-size:11px;color:#8b949e;">→ {_wa}</span>'
                    f'</div>',
                    unsafe_allow_html=True
                )


        # ── ⑤ v4.0 總經一票否決 (Task 2) ─────────────────────────────
        try:
            _v4_pcr = float(_last_row.get('選PCR') or 100)
            _v4_fut = float(_last_row.get('外資大小') or 0)
            _v4_mac = V4StrategyEngine.__new__(V4StrategyEngine)
            _v4_mac.macro = {'vix': 15, 'foreign_futures': _v4_fut, 'pcr': _v4_pcr}
            _v4_veto = _v4_mac.check_macro_veto()
            _v4_c = _v4_veto['color']
            st.markdown(
                f'<div style="border-left:5px solid {_v4_c};background:#0d1117;'
                f'padding:9px 14px;border-radius:0 8px 8px 0;margin:6px 0;">'
                f'<span style="font-size:11px;color:{TRAFFIC_NEUTRAL};">🏛️ v4.0 總經否決權</span><br>'
                f'<span style="font-size:14px;font-weight:900;color:{_v4_c};">'
                f'{_v4_veto["status"]} — 最大建議持股 {_v4_veto["max_position"]}%</span><br>'
                f'<span style="font-size:12px;color:#c9d1d9;">{_v4_veto["msg"]}</span>'
                f'</div>',
                unsafe_allow_html=True
            )
        except Exception as _v4e:
            pass


        # ── v5.0 動態資產配置建議（純現金策略，無 ETF）────────────────
        try:
            _v5_fut = float(_last_row.get('外資大小') or 0)
            if _v5_fut <= -30000:
                _v5_stock, _v5_cash = 20, 80
                _v5_strategy = '嚴禁追高攤平，保護本金優先；可留意低基期高殖利率個股'
                _v5_color = TRAFFIC_RED
            elif _v5_fut <= -15000:
                _v5_stock, _v5_cash = 50, 50
                _v5_strategy = '收回資金，逢高減碼漲多個股，等待期空回補訊號'
                _v5_color = TRAFFIC_YELLOW
            elif _v5_fut > 0:
                _v5_stock, _v5_cash = 90, 10
                _v5_strategy = '期貨翻多，順勢重壓強勢股，外投同買個股優先布局'
                _v5_color = TRAFFIC_GREEN
            else:
                _v5_stock, _v5_cash = 70, 30
                _v5_strategy = '水位中性，依個股技術面操作，保留現金彈藥'
                _v5_color = '#58a6ff'
            st.markdown(
                f'<div style="border-left:5px solid {_v5_color};background:#0d1117;'
                f'padding:9px 14px;border-radius:0 8px 8px 0;margin:6px 0;">'
                f'<span style="font-size:11px;color:{TRAFFIC_NEUTRAL};">💰 v5 動態配置</span><br>'
                f'<span style="font-size:14px;font-weight:900;color:{_v5_color};">'
                f'建議股票 {_v5_stock}% ／現金 {_v5_cash}%</span><br>'
                f'<span style="font-size:12px;color:#c9d1d9;">📌 {_v5_strategy}</span>'
                f'</div>',
                unsafe_allow_html=True
            )
        except Exception:
            pass

# ── ④ 資料來源診斷（收合，供進階使用者確認）─────────────────────
        with st.expander('🔍 資料來源診斷（點此確認各欄數據正確性）', expanded=False):
            # v18.350 PR-P1:加 TTL + 備援優先級兩欄,SSOT 對齊「資料診斷 Tab」(app.py:1649
            # tab_diag),避免 user 誤把 30min 快取舊值當「即時」。dict 升級為 4-tuple:
            # (來源主鏈, 公式, TTL, 備援優先級或 single-source 標註)。
            _diag_cols = {
                '外資大小':       ('FinMind TX+MTX 期貨留倉',
                                   '外資大台淨口 + 外資小台淨口×0.25',
                                   '30 分(build_leading_fast pickle)',
                                   '① FinMind TX → ② FinMind MTX → ③ TAIFEX futContractsDate 備援'),
                '前五大留倉':     ('TAIFEX largeTraderFutQry POST',
                                   '前五大買方所有契約 − 賣方所有契約',
                                   '30 分(同上)',
                                   '單一源(免費 FinMind 無此資料)'),
                '前十大留倉':     ('TAIFEX largeTraderFutQry POST',
                                   '前十大買方所有契約 − 賣方所有契約',
                                   '30 分(同上)',
                                   '單一源'),
                '選PCR':          ('TAIFEX pcRatio POST',
                                   'Put未平倉量 / Call未平倉量 × 100',
                                   '30 分(同上)',
                                   '① TAIFEX → ② FinMind TXO 法人估算(備援)'),
                '外(選)':         ('TAIFEX callsAndPutsDate POST',
                                   'BC金額 − SC金額 − BP金額 + SP金額',
                                   '30 分(同上)',
                                   '單一源'),
                '韭菜指數':       ('TAIFEX futContractsDate+futDailyMarketReport',
                                   '(法人空方MTX OI − 法人多方MTX OI) / 全體MTX OI × 100',
                                   '30 分(同上)',
                                   '① TAIFEX → ② FinMind 法人空多比估算(備援)'),
                '外資/投信/自營': ('TWSE BFI82U(via Squid Proxy)',
                                   '三大法人現貨買賣差額(億元)',
                                   '10 分(TTL_CONFIG[institutional])',
                                   '① TWSE → ② FinMind → ③ pkl Cache(過期)'),
                '成交量':         ('TWSE FMTQIK 月報',
                                   '每日全市場成交金額(億元)',
                                   '10 分(TTL_CONFIG[volume])',
                                   '① TWSE OpenAPI → ② YFinance → ③ Cache'),
            }
            # 頂部全域註腳:cache 新鮮度告示
            st.markdown(
                '<div style="font-size:11px;color:#f0883e;background:#0d1117;'
                'padding:6px 10px;border-left:3px solid #f0883e;margin:4px 0 10px;">'
                '💡 <b>注意 cache 新鮮度</b>:本表所列指標多走 30 分鐘 pickle 快取 + '
                'st.cache_data。週末/假日 4 個 FinMind API 全空時 leading_fast 會 fallback '
                '到過期 pickle(已標 📦 stale chip)。「即時」≠「最新交易日」,以畫面上方'
                '「資料期間」caption 為準。</div>',
                unsafe_allow_html=True)
            for _col, _tup in _diag_cols.items():
                # 向下相容:舊 2-tuple 仍 fallback(避免外部 caller 改 dict 時崩)
                if len(_tup) == 4:
                    _src, _formula, _ttl, _fallback = _tup
                else:
                    _src, _formula = _tup[0], _tup[1]
                    _ttl, _fallback = '-', '-'
                st.markdown(
                    f'<div style="font-size:12px;color:#8b949e;padding:3px 0;">'
                    f'<b style="color:#c9d1d9;">{_col}</b> → 主來源:{_src}<br>'
                    f'&nbsp;&nbsp;&nbsp;公式:{_formula}<br>'
                    f'&nbsp;&nbsp;&nbsp;⏱ TTL:{_ttl}<br>'
                    f'&nbsp;&nbsp;&nbsp;🔀 備援優先級:{_fallback}</div>',
                    unsafe_allow_html=True
                )
            # [BUG FIX] 最新一筆原始值 - 用 pd.isna 確保 NaN 不造成 format error
            if len(df_li_show) > 0:
                _raw = df_li_show.iloc[-1]
                st.markdown('<br><b style="color:#c9d1d9;font-size:12px;">最新一筆原始值：</b>', unsafe_allow_html=True)
                _raw_items = []
                for _c in ['外資大小','前五大留倉','前十大留倉','選PCR','外(選)','韭菜指數','外資','投信','自營']:
                    _v = _raw.get(_c)
                    if _v is not None:
                        try:
                            import pandas as _pd_raw
                            if not _pd_raw.isna(_v):  # [BUG FIX] 過濾 NaN 避免 format 崩潰
                                _raw_items.append(f'{_c}={float(_v):+,.0f}')
                        except Exception:
                            _raw_items.append(f'{_c}={_v}')
                st.code(' | '.join(_raw_items), language=None)

        # ── ⑤ 下載按鈕（Base64 data URL，不依賴 WebSocket）──────
        try:
            import base64 as _b64_li
            _csv_li = df_li_show.to_csv(index=False, encoding='utf-8-sig')
            _b64_li_data = _b64_li.b64encode(_csv_li.encode('utf-8-sig')).decode()
            st.markdown(
                f'<a href="data:text/csv;charset=utf-8-sig;base64,{_b64_li_data}" '
                f'download="先行指標.csv" '
                f'style="display:inline-block;padding:5px 14px;background:#21262d;'
                f'color:#e6edf3;border:1px solid #30363d;border-radius:6px;'
                f'font-size:13px;text-decoration:none;">⬇️ 下載先行指標 CSV</a>',
                unsafe_allow_html=True
            )
        except Exception:
            pass

    else:
        # v18.340 §1 Fail Loud：對齊 PR #362 chips_empty_state 三狀態分流(table 專屬 helper)。
        # user 2026-06-28「原來的 table 呢?」(對比 6/14 截圖)→ 真正根因常是 FINMIND_TOKEN
        # 缺失/失效,舊文案沒明指,user 找不到救法。新 helper 明確分流:
        #   未載入(灰) / 已試+無token(橙明指 FINMIND_TOKEN) / 已試+有token(橙歸因額度/週末)。
        from shared.macro_buckets import leading_table_empty_state_html as _li_es
        _attempted_li = bool(cd) or bool(st.session_state.get('cl_ts')) or bool(
            st.session_state.get('chips_loaded'))
        try:
            _fm_present_li = bool((getattr(st, 'secrets', {}) or {}).get('FINMIND_TOKEN')
                                  or os.environ.get('FINMIND_TOKEN', ''))
        except Exception:
            _fm_present_li = bool(os.environ.get('FINMIND_TOKEN', ''))
        st.markdown(_li_es(attempted=_attempted_li, token_present=_fm_present_li),
                    unsafe_allow_html=True)

    # 宏爺判斷方式 → 已移至 Tab 5 策略手冊

    # ── 宏爺智能綜合結論 ─────────────────────────────────────────────────────
    _df_li_c = st.session_state.get('li_latest')
    if _df_li_c is not None and not _df_li_c.empty:
        _last_li = _df_li_c.iloc[-1]
        _fnet = safe_get(_last_li.get('外資大小'))
        _pcr  = safe_get(_last_li.get('選PCR'))
        _leek = safe_get(_last_li.get('韭菜指數'))
        _top5 = safe_get(_last_li.get('前五大留倉'))
        _opt  = safe_get(_last_li.get('外(選)'))
        _date = _last_li.get('日期','最新')

        _score = 0
        _sigs = []
        if _fnet is not None:
            if   _fnet < -30000:
                _score -= 2
                _sigs.append(f'🔴 期貨空單 {_fnet:,.0f}口（超越3萬危險線）')
            elif _fnet <      0:
                _score -= 1
                _sigs.append(f'⚠️ 期貨淨空 {_fnet:,.0f}口')
            else:
                _score += 1
                _sigs.append(f'✅ 期貨淨多 {_fnet:+,.0f}口')
        if _pcr is not None:
            if   _pcr > 130:
                _score += 1
                _sigs.append(f'🟢 PCR={_pcr:.0f}（>130強支撐）')
            elif _pcr > 100:
                _sigs.append(f'🔵 PCR={_pcr:.0f}（偏多）')
            else:
                _score -= 1
                _sigs.append(f'🔴 PCR={_pcr:.0f}（<100偏空）')
        if _opt is not None:
            if   _opt >  10000:
                _score += 1
                _sigs.append(f'🟢 外選 +{_opt:,.0f}千元（多方佈局）')
            elif _opt < -10000:
                _score -= 1
                _sigs.append(f'🔴 外選 {_opt:,.0f}千元（空方佈局）')
            else:
                _sigs.append(f'⚪ 外選 {_opt:+,.0f}千元（中性）')
        if _top5 is not None:
            if   _top5 < -10000:
                _score -= 1
                _sigs.append(f'🔴 前五大淨空 {_top5:,.0f}口（警戒）')
            elif _top5 >       0:
                _score += 1
                _sigs.append(f'✅ 前五大淨多 {_top5:+,.0f}口')
        if _leek is not None:
            if   _leek > 10:
                _score -= 1
                _sigs.append(f'🔴 韭菜指數{_leek:.1f}%（散戶過熱）')
            elif _leek < -5:
                _score += 1
                _sigs.append(f'✅ 韭菜指數{_leek:.1f}%（散戶悲觀）')
            else:
                _sigs.append(f'⚪ 韭菜指數{_leek:.1f}%（中性）')

        if   _score <= -3:
            _vd='🚨 強烈偏空'
            _vc=TRAFFIC_RED
            _va='建議大幅降倉，等待空單回補訊號'
        elif _score <= -1:
            _vd='🔴 偏空'
            _vc='#da6d3e'
            _va='籌碼不穩，建議觀望為主'
        elif _score ==  0:
            _vd='⚪ 多空分歧'
            _vc=TRAFFIC_YELLOW
            _va='訊號分歧，小倉觀察，詳見策略手冊'
        elif _score <=  2:
            _vd='🟢 偏多'
            _vc=TRAFFIC_GREEN
            _va='籌碼偏健康，可正常持倉'
        else:
            _vd='💚 強烈偏多'
            _vc='#2ea043'
            _va='聰明錢明顯佈多，積極持倉'

        st.markdown(
            f'<div style="background:#0d1117;border:2px solid {_vc}44;border-radius:10px;padding:14px 18px;margin:8px 0;">'
            f'<div style="font-size:11px;color:#8b949e;margin-bottom:4px;">🎯 {_date} 籌碼綜合判斷</div>'
            f'<div style="font-size:24px;font-weight:900;color:{_vc};">{_vd}</div>'
            f'<div style="font-size:13px;color:#c9d1d9;margin:6px 0 10px 0;">{_va}</div>'
            f'<div style="font-size:12px;color:#484f58;">{" ； ".join(_sigs)}</div>'
            f'</div>',
            unsafe_allow_html=True
        )


    st.markdown('<hr style="border-color:#21262d;margin:14px 0;">',unsafe_allow_html=True)
