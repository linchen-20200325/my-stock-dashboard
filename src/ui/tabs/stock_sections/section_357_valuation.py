"""src/ui/tabs/stock_sections/section_357_valuation.py — B 357 殖利率評價 + 3 河流圖(v18.407 U4 Phase 3-B).

從 tab_stock.py:1365-1787 + L128-161 抽出。含:
- 357 殖利率分類文案 + 4 KPI 卡 + 近 5 年股利長條圖
- 殖利率河流圖(逐日 TTM 365D rolling)
- PE 本益比河流圖(逐日 TTM EPS,3 種 PE 區間 selectbox)
- PB 股價淨值比河流圖(產業別動態閾值 + 3 段資料源 chain)
- _fetch_pbratio_from_twse 私有 helper(原 tab_stock.py:128,搬入避免循環 import)

§8.2 layer:L5 UI Tab section helper(中-高風險:422+ LOC,內含多 plotly + 3 估值河流)。

對外 API:
- render_357_valuation_section(...) -> None
"""
from __future__ import annotations

import datetime

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from shared.colors import TRAFFIC_GREEN, TRAFFIC_RED, TRAFFIC_YELLOW
from shared.stock_buckets import get_pb_bands as _get_pb_bands_ssot
from shared.stock_buckets import pb_bands_label as _pb_bands_label_ssot
from shared.thresholds import (
    YIELD_HIGH_DEC,
    YIELD_LOW_DEC,
    YIELD_MID_DEC,
    classify_stock_357_price,  # Batch 9 v18.418:357 SSOT helper
)
from src.ui.render.tab_sections import border_left_banner  # R-UI-1 v18.412
from shared.ttls import TTL_1DAY
from src.data.core import fetch_bps, fetch_industry_category
from src.data.core.provenance import prov_log
from src.ui.render import kpi, teacher_conclusion


@st.cache_data(ttl=TTL_1DAY, show_spinner=False)
def _fetch_pbratio_from_twse(sid: str) -> float:
    """v18.175:從 TWSE OpenAPI BWIBBU_d 直取個股 P/B 股價淨值比(伺服器端權威值)。

    重用既有 yield_screener.fetch_twse_yield_pe() 1 日快取的全市場 DataFrame,
    過濾出指定 sid 的「股價淨值比」欄位。涵蓋全 TWSE 上市股(TPEx 退 FinMind)。
    """
    try:
        from src.ui.tabs import fetch_twse_yield_pe
        _df = fetch_twse_yield_pe()
        if _df is None or _df.empty:
            return 0.0
        _hit = _df[_df['代碼'].astype(str) == str(sid)]
        if _hit.empty:
            return 0.0
        _pb = _hit.iloc[0].get('股價淨值比')
        if _pb is None:
            return 0.0
        _pb_v = float(_pb)
        if not (0.01 < _pb_v < 100):
            return 0.0
        # v18.356 PR-Q5b S-PROV-1 phase 19:success-path provenance
        prov_log('_fetch_pbratio_from_twse', 'TWSE:OpenAPI:BWIBBU_d(via yield_screener)',
                 f'float:{_pb_v}', ticker=sid)
        return _pb_v
    except Exception as _e:
        import sys as _sys
        print(f'[_fetch_pbratio_from_twse] swallow: {type(_e).__name__}: {_e}',
              file=_sys.stderr)
        return 0.0


def render_357_valuation_section(sid2: str, name2: str, df2, price2,
                                  qtr2, yearly2, avg_div2, cl2, t2d: dict) -> None:
    """B. 357 殖利率評價 + 3 河流圖。

    Args:
        sid2 / name2: 股票代碼 / 名稱
        df2: 股價 DataFrame(含 close / date / EPS / 年度 / 季度)
        price2: 當前股價
        qtr2: 季財報 DataFrame
        yearly2: 近 5 年配息 list[dict]
        avg_div2: 5 年平均配息
        cl2: 合約負債(此 section 未直接用,但保留 caller arg 對稱性)
        t2d: tab2 data dict(從 session_state)用於 div_src
    """
    # ══ B. 357 評價 ════════════════════════════════════════
    # Batch 9 v18.418:走 SSOT(shared/thresholds.classify_stock_357_price)。
    # 原 inline 兩段重複 if-elif(計算 cheap/fair/dear 二次 + 分級判斷二次)收為一次,
    # 各 caller-side label dict 對應各自 UX 措辭(教師結論 vs 結論卡)。
    st.markdown('---')
    st.markdown('#### 💰 B. 357殖利率評價 [策略1]')
    _code357, _targets = classify_stock_357_price(price2, avg_div2)
    # 教師結論文案(arg: range 描述 + 操作建議)
    _TEACHER_LABELS = {
        'cheap':      lambda p, t: (
            f'現價 {p:.1f} ≤ 便宜價 {t["cheap"]:.1f}（殖利率>7%），積極買進區',
            '可大膽買進，股息都進口袋'),
        'fair':       lambda p, t: (
            f'現價 {p:.1f} 在合理區 {t["cheap"]:.1f}–{t["fair"]:.1f}（殖利率5-7%）',
            '可分批布局，勿一次梭哈'),
        'dear':       lambda p, t: (
            f'現價 {p:.1f} 在昂貴區 {t["fair"]:.1f}–{t["dear"]:.1f}（殖利率3-5%）',
            '謹慎，等回調至合理價再進場'),
        'overpriced': lambda p, t: (
            f'現價 {p:.1f} > 昂貴價 {t["dear"]:.1f}（殖利率<3%），嚴禁追高',
            '放下，等大跌再看'),
        'na':         lambda p, t: (
            '無股利資料，無法套用357評價',
            '以技術面健康度為主要判斷'),
    }
    _ba, _bb = _TEACHER_LABELS[_code357](price2, _targets)
    st.markdown(teacher_conclusion('孫慶龍', f'{sid2} 現價{price2:.1f} vs 357區間', _ba, _bb),
                unsafe_allow_html=True)
    if _code357 != 'na':
        # 結論卡 sig/顏色
        _BOX_LABELS = {
            'cheap':      ('🟢便宜價 — 積極買進',  TRAFFIC_GREEN),
            'fair':       ('🟡合理價 — 可分批布局', TRAFFIC_YELLOW),
            'dear':       ('🔴昂貴價 — 謹慎操作',   TRAFFIC_RED),
            'overpriced': ('🔴超過昂貴 — 避免追高', TRAFFIC_RED),
        }
        sig2, sc2 = _BOX_LABELS[_code357]
        st.markdown(f"""<div style="background:#161b22;border:2px solid {sc2};border-radius:10px;
padding:12px 16px;margin:8px 0;">
<div style="font-size:16px;font-weight:900;color:{sc2};">{sig2}</div>
<div style="font-size:11px;color:#8b949e;margin-top:4px;">
  {sid2} {name2} | 現價 <b style="color:#58a6ff;">{price2:.2f}</b> |
  近5年均股利 <b style="color:#ffd700;">{avg_div2:.2f}元</b> ({t2d.get('div_src', '')})
</div></div>""", unsafe_allow_html=True)
        v1, v2, v3, v4 = st.columns(4)
        for vc, vl, vp, vcol in [(v1, '現價', price2, '#58a6ff'),
                                  (v2, '🟢便宜(7%)', _targets['cheap'], TRAFFIC_GREEN),
                                  (v3, '🟡合理(5%)', _targets['fair'],  TRAFFIC_YELLOW),
                                  (v4, '🔴昂貴(3%)', _targets['dear'],  TRAFFIC_RED)]:
            with vc:
                st.markdown(kpi(vl, f'{vp:.1f}', '', vcol, vcol), unsafe_allow_html=True)
        if yearly2:
            fig_d = go.Figure(go.Bar(
                x=[str(int(y['year'])) for y in yearly2],
                y=[y['cash'] for y in yearly2],
                marker_color='#ffd700',
                text=[f'{y["cash"]:.2f}' for y in yearly2], textposition='auto'))
            fig_d.update_layout(height=180, plot_bgcolor='#0e1117', paper_bgcolor='#0e1117',
                                font=dict(color='white'), margin=dict(l=20, r=20, t=30, b=20),
                                title=dict(text=f'{sid2} 近5年現金股利', font=dict(color='#ffd700', size=12)),
                                yaxis=dict(gridcolor='#333'), xaxis=dict(gridcolor='#333'))
            st.plotly_chart(fig_d, width='stretch', config={'displayModeBar': False})
    else:
        st.warning('⚠️ 無配息記錄（成長股）— 建議改用本益比評估')
    # ── 357 動態建議 ──
    _asset_type = '📈 大盤' if sid2 in ('^TWII', 'TAIEX') else '📊 個股'
    if avg_div2 > 0:
        _grade = ("便宜價🟢 — 策略1：積極買進！" if price2 <= cheap2
                  else ("合理價🟡 — 策略1：可分批布局，等殖利率拉升再加碼" if price2 <= fair2
                        else ("昂貴價🔴 — 策略1：謹慎操作，等待回檔再進場" if price2 <= dear2
                              else "超過昂貴價🔴 — 策略1：絕對不追高，等待大幅修正")))
        _357_verdict = f'**{sid2} {name2}** 現價 {price2:.1f} 處於 {_grade}，近5年均股利 {avg_div2:.2f} 元'
        _357_c = TRAFFIC_GREEN if price2 <= cheap2 else (TRAFFIC_YELLOW if price2 <= fair2 else TRAFFIC_RED)
        st.markdown(
            f'{_asset_type} **`{sid2}` {name2}** ｜ 策略1·357法則判斷'
        )
        # R-UI-1 v18.412:inline `<div border-left>` → border_left_banner SSOT
        st.markdown(border_left_banner(
            _357_c, _357_verdict,
            border_width=4, padding_y=10, padding_x=14, font_size=13, margin_y=6,
            bold=True, bg='#161b22',
        ), unsafe_allow_html=True)
        # 357結論:直接顯示當前評估,不導向策略手冊
        st.markdown(border_left_banner(
            _357_c,
            f'<span style="font-size:12px;color:#8b949e;">{_asset_type} <code>{sid2}</code> {name2} ｜ 🎓 策略1 · 357法則判斷</span><br>'
            f'<span style="font-size:14px;font-weight:800;">{_357_verdict}</span><br>'
            f'<span style="font-size:11px;color:#8b949e;">判讀邏輯：殖利率≥7%=便宜大買；5-7%=合理；3-5%=偏貴持有；&lt;3%=昂貴停利</span>',
            border_width=4, padding_y=10, padding_x=14, margin_y=6,
        ), unsafe_allow_html=True)

    # ── 估值河流圖(357殖利率河流,逐日 TTM)────────────────────
    st.caption('🔰 河流圖怎麼看：把「便宜／合理／昂貴」三種估值水位畫成色帶，看股價（線）落在哪一條 —— '
               '靠下緣＝相對便宜、靠上緣＝相對貴。下方三張用不同角度估值：'
               '殖利率河流（用配息，殖利率高＝便宜）、本益比河流（用每股盈餘 EPS，適合穩定獲利公司）、'
               '股價淨值比河流（用每股淨值 BPS，適合資產股或虧損沒 EPS 時）。')
    if df2 is not None and not df2.empty:
        _render_dividend_river(sid2, name2, df2, yearly2, avg_div2)

    # ── 估值河流圖(PE 本益比河流,逐日 TTM EPS)───────────────────
    _has_eps = (qtr2 is not None and not qtr2.empty
                and 'EPS' in qtr2.columns and 'date' in qtr2.columns)
    _eps_q_clean = (pd.to_numeric(qtr2['EPS'], errors='coerce').dropna()
                    if _has_eps else pd.Series(dtype=float))

    if df2 is not None and not df2.empty and _has_eps and len(_eps_q_clean) >= 4:
        _render_pe_river(sid2, name2, df2, qtr2)
    elif df2 is not None and not df2.empty:
        st.info(f'ℹ️ {sid2} 季報 EPS 資料不足 4 季（取得 {len(_eps_q_clean)} 季），無法繪製本益比河流圖。')

    # ── 估值河流圖(PB 股價淨值比河流)─────────────────────────
    _render_pb_river(sid2, name2, df2)


def _render_dividend_river(sid2: str, name2: str, df2,
                            yearly2, avg_div2) -> None:
    """殖利率河流圖(逐日 TTM 365D rolling)。"""
    # ── 1. 將 yearly2 轉成「ex-div 事件序列」(年中 7/1 為合成除息日) ──
    # 防護:合成日期若 > 今天 → 跳過(避免 365D rolling 涵蓋不到)
    _today_ts = pd.Timestamp(datetime.date.today())
    _riv_events = []
    if yearly2:
        for _y in yearly2:
            try:
                _y_cash = float(_y.get('cash', 0) or 0)
                if _y_cash > 0:
                    _ev_dt = pd.Timestamp(int(_y['year']), 7, 1)
                    if _ev_dt > _today_ts:
                        continue
                    _riv_events.append({'date': _ev_dt, 'div': _y_cash})
            except Exception:
                pass
    # 若無逐年資料,用 avg_div2 補「去年 7/1」(不是今年 — 避免落在未來)
    if not _riv_events and avg_div2 and avg_div2 > 0:
        _riv_events.append({
            'date': pd.Timestamp(datetime.date.today().year - 1, 7, 1),
            'div':  float(avg_div2)
        })

    if not _riv_events:
        return

    # ── 2. 對 df2 每個交易日做 365D rolling sum (TTM 股利) ──
    _rdates_s = pd.to_datetime(
        df2['date'] if 'date' in df2.columns else pd.RangeIndex(len(df2)))
    _rclose_riv = pd.to_numeric(df2['close'], errors='coerce').reset_index(drop=True)
    _rdates_riv = _rdates_s.reset_index(drop=True)

    _ev_df = pd.DataFrame(_riv_events).sort_values('date').reset_index(drop=True)
    _ev_df['kind'] = 'ev'
    _td_df = pd.DataFrame({'date': _rdates_riv, 'div': 0.0, 'kind': 'td'})
    _all_df = (pd.concat([_ev_df, _td_df], ignore_index=True)
               .sort_values('date')
               .reset_index(drop=True))
    _all_df['ttm'] = (_all_df.set_index('date')['div']
                      .rolling('365D', min_periods=1).sum().values)

    _td_only = _all_df[_all_df['kind'] == 'td'].copy()
    _td_only['ttm'] = _td_only['ttm'].mask(_td_only['ttm'] <= 0).ffill()
    _ttm_series = pd.to_numeric(_td_only['ttm'], errors='coerce').reset_index(drop=True)

    # ── 安全網:TTM 整段全 0 / NaN(過去 12 月真的沒除息)→ 退回 avg_div2 橫帶 ──
    _ttm_valid = _ttm_series.dropna()
    _is_fallback_flat = (_ttm_valid.empty or float(_ttm_valid.max()) <= 0) \
        and avg_div2 and avg_div2 > 0
    if _is_fallback_flat:
        _ttm_series = pd.Series([float(avg_div2)] * len(_rdates_riv))

    # ── 3. 計算河流帶:P = TTM 股利 / 殖利率閾值(逐日) ──
    _band7_riv = (_ttm_series / YIELD_HIGH_DEC).round(2)
    _band5_riv = (_ttm_series / YIELD_MID_DEC).round(2)
    _band3_riv = (_ttm_series / YIELD_LOW_DEC).round(2)

    _cur_div_riv = float(_ttm_series.dropna().iloc[-1]) if not _ttm_series.dropna().empty else 0
    _p7r = float(_band7_riv.dropna().iloc[-1]) if not _band7_riv.dropna().empty else 0
    _p5r = float(_band5_riv.dropna().iloc[-1]) if not _band5_riv.dropna().empty else 0
    _p3r = float(_band3_riv.dropna().iloc[-1]) if not _band3_riv.dropna().empty else 0

    # ── 5. 繪圖 ──
    _fig_riv = go.Figure()
    _fig_riv.add_trace(go.Scatter(
        x=_rdates_riv, y=_rclose_riv, name='收盤價',
        line=dict(color='#e6edf3', width=2.5),
        hovertemplate='%{x|%Y-%m-%d}<br>%{y:.2f}<extra></extra>'))

    for _bs, _lbl_base, _last_val, _col in [
        (_band7_riv, '7%便宜', _p7r, TRAFFIC_GREEN),
        (_band5_riv, '5%合理', _p5r, TRAFFIC_YELLOW),
        (_band3_riv, '3%昂貴', _p3r, TRAFFIC_RED)
    ]:
        _lbl = f'{_lbl_base}:{_last_val:.0f}' if _last_val > 0 else _lbl_base
        _fig_riv.add_trace(go.Scatter(
            x=_rdates_riv, y=_bs, name=_lbl,
            line=dict(color=_col, width=1.5, dash='dot'),
            hovertemplate=f'{_lbl_base}: %{{y:.0f}}<extra></extra>'))

    _b7_last = float(_band7_riv.dropna().iloc[-1]) if not _band7_riv.dropna().empty else 0
    _b5_last = float(_band5_riv.dropna().iloc[-1]) if not _band5_riv.dropna().empty else 0
    _b3_last = float(_band3_riv.dropna().iloc[-1]) if not _band3_riv.dropna().empty else 0
    if _b7_last > 0:
        _fig_riv.add_hrect(y0=0, y1=_b7_last, fillcolor='rgba(63,185,80,0.07)', line_width=0)
    if _b5_last > _b7_last:
        _fig_riv.add_hrect(y0=_b7_last, y1=_b5_last, fillcolor='rgba(210,153,34,0.07)', line_width=0)
    if _b3_last > _b5_last:
        _fig_riv.add_hrect(y0=_b5_last, y1=_b3_last, fillcolor='rgba(248,81,73,0.05)', line_width=0)

    _all_riv_vals = (
        list(_rclose_riv.dropna()) +
        list(_band3_riv.dropna()) +
        list(_band7_riv.dropna())
    )
    _ymax_riv = max(_all_riv_vals) * 1.05 if _all_riv_vals else 100
    _ymin_riv = max(0, min(_all_riv_vals) * 0.7) if _all_riv_vals else 0

    _div_label = '近5年均股利' if _is_fallback_flat else 'TTM 股利'
    _fig_riv.update_layout(
        title=dict(
            text=f'📊 {sid2} {name2} 殖利率河流圖（{_div_label} {_cur_div_riv:.2f}元）',
            font=dict(color='#8b949e', size=12)),
        height=300, plot_bgcolor='#0e1117', paper_bgcolor='#0e1117',
        font=dict(color='white', size=11),
        margin=dict(l=10, r=10, t=40, b=10),
        xaxis=dict(gridcolor='#21262d'),
        yaxis=dict(range=[_ymin_riv, _ymax_riv], gridcolor='#21262d'),
        hovermode='x unified', showlegend=True,
        legend=dict(orientation='h', y=1.08, x=0, font=dict(size=10)))
    st.plotly_chart(_fig_riv, width='stretch', config={'displayModeBar': False})

    _cur_price_riv = float(_rclose_riv.dropna().iloc[-1]) if not _rclose_riv.dropna().empty else 0
    if _is_fallback_flat:
        st.caption(
            f'📊 歷史參考帶（{_div_label} {_cur_div_riv:.2f}元，非即時 TTM）　'
            f'7%≤{_p7r:.0f} / 5%≤{_p5r:.0f} / 3%≤{_p3r:.0f}　現價 {_cur_price_riv:.0f}')
        st.info('ℹ️ 此股近 12 個月無除息事件，殖利率河流退化為 5 年均股利橫帶（僅作歷史對照），**不適合作為即時估值依據**。建議改用本益比 / 股價淨值比等其他估值工具。')
    else:
        _cur_zone = ('🟢 便宜區' if _cur_price_riv < _p7r else
                     '🟡 合理區' if _cur_price_riv < _p5r else
                     '🔴 昂貴區' if _cur_price_riv < _p3r else '⛔ 超昂貴')
        st.caption(
            f'目前位於 {_cur_zone}（現價 {_cur_price_riv:.0f} / '
            f'便宜≤{_p7r:.0f} / 合理≤{_p5r:.0f} / 昂貴≤{_p3r:.0f}）'
            f'　{_div_label} {_cur_div_riv:.2f}元')
        if _cur_div_riv < 0.5:
            st.info('ℹ️ 此股近年現金股利極低（< 0.5元），殖利率河流圖參考意義有限，建議搭配本益比等其他估值工具。')


def _render_pe_river(sid2: str, name2: str, df2, qtr2) -> None:
    """PE 本益比河流圖(逐日 TTM EPS,3 種 PE 區間 selectbox)。"""
    _pe_preset_label = st.selectbox(
        'PE 估值區間',
        ['通用 10/15/20', '保守 8/12/16（景氣循環股）', '成長 12/18/25'],
        index=0, key=f'pe_preset_{sid2}',
        help='通用：多數產業；保守：半導體代工/面板/DRAM 等高波動景氣循環股；成長：科技/消費/軟體股')
    _PE_BANDS = {
        '通用 10/15/20': (10, 15, 20),
        '保守 8/12/16（景氣循環股）': (8, 12, 16),
        '成長 12/18/25': (12, 18, 25),
    }
    _pe_low, _pe_mid, _pe_high = _PE_BANDS[_pe_preset_label]

    # ── 1. 計算逐季 TTM EPS(4 季 rolling sum) ──
    _qs = qtr2.sort_values(['年度', '季度']).reset_index(drop=True).copy()
    _qs['ttm_eps'] = pd.to_numeric(_qs['EPS'], errors='coerce').rolling(4, min_periods=4).sum()
    # 公告生效日:季末 + 60 天(涵蓋台股財報公告期 Q1=5/15、Q2=8/14、Q3=11/14、年報 3/31)
    _qs['announce'] = pd.to_datetime(_qs['date'], errors='coerce') + pd.Timedelta(days=60)
    _qa = _qs.dropna(subset=['ttm_eps', 'announce']).sort_values('announce').reset_index(drop=True)

    # ── 2. asof 對應到日線:每個交易日採用該日之前最後一筆已公告的 TTM EPS ──
    _rdates_pe = pd.to_datetime(
        df2['date'] if 'date' in df2.columns else pd.RangeIndex(len(df2)),
        errors='coerce').reset_index(drop=True)
    _rclose_pe = pd.to_numeric(df2['close'], errors='coerce').reset_index(drop=True)
    _df_p = pd.DataFrame({'date': _rdates_pe, 'close': _rclose_pe}).sort_values('date').reset_index(drop=True)
    _df_a = _qa[['announce', 'ttm_eps']].rename(columns={'announce': 'date'})
    _merged_pe = pd.merge_asof(_df_p, _df_a, on='date', direction='backward')
    _ttm_eps_series = _merged_pe['ttm_eps']

    # ── 3. 計算最新 TTM EPS + 虧損股檢查 ──
    _cur_eps_pe = float(_ttm_eps_series.dropna().iloc[-1]) if not _ttm_eps_series.dropna().empty else 0
    _cur_price_pe = float(_rclose_pe.dropna().iloc[-1]) if not _rclose_pe.dropna().empty else 0

    if _cur_eps_pe <= 0:
        st.warning(f'⚠️ {sid2} 近 4 季 TTM EPS = {_cur_eps_pe:.2f} 元（虧損），本益比估值不適用。請參考下方 P/B 股價淨值比河流圖。')
        return
    # ── 4. 計算河流帶(逐日) ──
    _band_pe_low = (_ttm_eps_series * _pe_low).round(2)
    _band_pe_mid = (_ttm_eps_series * _pe_mid).round(2)
    _band_pe_high = (_ttm_eps_series * _pe_high).round(2)
    _p_lo = float(_band_pe_low.dropna().iloc[-1]) if not _band_pe_low.dropna().empty else 0
    _p_mi = float(_band_pe_mid.dropna().iloc[-1]) if not _band_pe_mid.dropna().empty else 0
    _p_hi = float(_band_pe_high.dropna().iloc[-1]) if not _band_pe_high.dropna().empty else 0

    # ── 5. 繪圖 ──
    _fig_pe = go.Figure()
    _fig_pe.add_trace(go.Scatter(
        x=_rdates_pe, y=_rclose_pe, name='收盤價',
        line=dict(color='#e6edf3', width=2.5),
        hovertemplate='%{x|%Y-%m-%d}<br>%{y:.2f}<extra></extra>'))
    for _bs, _lbl_base, _last_val, _col in [
        (_band_pe_low,  f'PE{_pe_low}便宜',  _p_lo, TRAFFIC_GREEN),
        (_band_pe_mid,  f'PE{_pe_mid}合理',  _p_mi, TRAFFIC_YELLOW),
        (_band_pe_high, f'PE{_pe_high}昂貴', _p_hi, TRAFFIC_RED),
    ]:
        _lbl = f'{_lbl_base}:{_last_val:.0f}' if _last_val > 0 else _lbl_base
        _fig_pe.add_trace(go.Scatter(
            x=_rdates_pe, y=_bs, name=_lbl,
            line=dict(color=_col, width=1.5, dash='dot'),
            hovertemplate=f'{_lbl_base}: %{{y:.0f}}<extra></extra>'))
    if _p_lo > 0:
        _fig_pe.add_hrect(y0=0, y1=_p_lo, fillcolor='rgba(63,185,80,0.07)', line_width=0)
    if _p_mi > _p_lo:
        _fig_pe.add_hrect(y0=_p_lo, y1=_p_mi, fillcolor='rgba(210,153,34,0.07)', line_width=0)
    if _p_hi > _p_mi:
        _fig_pe.add_hrect(y0=_p_mi, y1=_p_hi, fillcolor='rgba(248,81,73,0.05)', line_width=0)

    _all_pe_vals = (list(_rclose_pe.dropna())
                    + list(_band_pe_high.dropna()) + list(_band_pe_low.dropna()))
    _ymax_pe = max(_all_pe_vals) * 1.05 if _all_pe_vals else 100
    _ymin_pe = max(0, min(_all_pe_vals) * 0.7) if _all_pe_vals else 0

    _fig_pe.update_layout(
        title=dict(
            text=f'📈 {sid2} {name2} 本益比河流圖（TTM EPS {_cur_eps_pe:.2f}元 × PE {_pe_low}/{_pe_mid}/{_pe_high}）',
            font=dict(color='#8b949e', size=12)),
        height=300, plot_bgcolor='#0e1117', paper_bgcolor='#0e1117',
        font=dict(color='white', size=11),
        margin=dict(l=10, r=10, t=40, b=10),
        xaxis=dict(gridcolor='#21262d'),
        yaxis=dict(range=[_ymin_pe, _ymax_pe], gridcolor='#21262d'),
        hovermode='x unified', showlegend=True,
        legend=dict(orientation='h', y=1.08, x=0, font=dict(size=10)))
    st.plotly_chart(_fig_pe, width='stretch', config={'displayModeBar': False})

    _cur_pe_ratio = _cur_price_pe / _cur_eps_pe if _cur_eps_pe > 0 else 0
    _cur_zone_pe = ('🟢 便宜區' if _cur_price_pe < _p_lo else
                    '🟡 合理區' if _cur_price_pe < _p_mi else
                    '🔴 昂貴區' if _cur_price_pe < _p_hi else '⛔ 超昂貴')
    st.caption(
        f'目前位於 {_cur_zone_pe}（現價 {_cur_price_pe:.0f} / '
        f'PE{_pe_low}≤{_p_lo:.0f} / PE{_pe_mid}≤{_p_mi:.0f} / PE{_pe_high}≤{_p_hi:.0f}）　'
        f'TTM EPS {_cur_eps_pe:.2f}元，當前 PE ≈ {_cur_pe_ratio:.1f} 倍')


def _render_pb_river(sid2: str, name2: str, df2) -> None:
    """PB 股價淨值比河流圖(產業別動態閾值 + 3 段資料源 chain)。"""
    _rdates_pb_pre = pd.to_datetime(
        df2['date'] if 'date' in df2.columns else pd.RangeIndex(len(df2)),
        errors='coerce').reset_index(drop=True) if df2 is not None else None
    _rclose_pb_pre = (pd.to_numeric(df2['close'], errors='coerce').reset_index(drop=True)
                      if df2 is not None and 'close' in df2.columns else None)
    _cur_price_pb_pre = (float(_rclose_pb_pre.dropna().iloc[-1])
                          if _rclose_pb_pre is not None and not _rclose_pb_pre.dropna().empty else 0.0)

    # PRIMARY: TWSE 官方 PBratio → BPS 反推
    _twse_pb = _fetch_pbratio_from_twse(sid2)
    _bps_val = 0.0
    _bps_source = ''
    if _twse_pb > 0 and _cur_price_pb_pre > 0:
        _bps_val = _cur_price_pb_pre / _twse_pb
        _bps_source = 'TWSE BWIBBU_d 官方 PBratio 反推'
    else:
        _bps_val = fetch_bps(sid2)
        if _bps_val > 0:
            _bps_source = 'FinMind TaiwanStockBalanceSheet 季度 / yfinance bookValue'

    # 產業別閾值(SSOT: shared.stock_buckets + data_loader.fetch_industry_category)
    _industry = fetch_industry_category(sid2)
    _PB_LOW, _PB_MID, _PB_HIGH = _get_pb_bands_ssot(_industry)
    _industry_label = _pb_bands_label_ssot(_industry)

    if df2 is None or df2.empty or _bps_val <= 0:
        if df2 is not None and not df2.empty:
            st.caption('ℹ️ 股價淨值比河流圖：TWSE/FinMind/yfinance 三路徑皆無 BPS 資料，跳過。')
        return

    _b_lo_pb = round(_bps_val * _PB_LOW, 2)
    _b_mi_pb = round(_bps_val * _PB_MID, 2)
    _b_hi_pb = round(_bps_val * _PB_HIGH, 2)

    _rdates_pb = _rdates_pb_pre if _rdates_pb_pre is not None else pd.to_datetime(
        df2['date'] if 'date' in df2.columns else pd.RangeIndex(len(df2)),
        errors='coerce').reset_index(drop=True)
    _rclose_pb = (_rclose_pb_pre if _rclose_pb_pre is not None
                  else pd.to_numeric(df2['close'], errors='coerce').reset_index(drop=True))

    _fig_pb = go.Figure()
    _fig_pb.add_trace(go.Scatter(
        x=_rdates_pb, y=_rclose_pb, name='收盤價',
        line=dict(color='#e6edf3', width=2.5),
        hovertemplate='%{x|%Y-%m-%d}<br>%{y:.2f}<extra></extra>'))
    for _v_pb, _lbl_pb, _col_pb in [
        (_b_lo_pb, f'PB{_PB_LOW}便宜:{_b_lo_pb:.0f}',  TRAFFIC_GREEN),
        (_b_mi_pb, f'PB{_PB_MID}合理:{_b_mi_pb:.0f}',  TRAFFIC_YELLOW),
        (_b_hi_pb, f'PB{_PB_HIGH}昂貴:{_b_hi_pb:.0f}', TRAFFIC_RED),
    ]:
        _fig_pb.add_hline(y=_v_pb, line=dict(color=_col_pb, width=1.5, dash='dot'),
                          annotation_text=_lbl_pb, annotation_position='right',
                          annotation_font=dict(color=_col_pb, size=10))
    _fig_pb.add_hrect(y0=0, y1=_b_lo_pb, fillcolor='rgba(63,185,80,0.07)', line_width=0)
    _fig_pb.add_hrect(y0=_b_lo_pb, y1=_b_mi_pb, fillcolor='rgba(210,153,34,0.07)', line_width=0)
    _fig_pb.add_hrect(y0=_b_mi_pb, y1=_b_hi_pb, fillcolor='rgba(248,81,73,0.05)', line_width=0)

    _all_pb_vals = list(_rclose_pb.dropna()) + [_b_hi_pb, _b_lo_pb]
    _ymax_pb = max(_all_pb_vals) * 1.05 if _all_pb_vals else 100
    _ymin_pb = max(0, min(_all_pb_vals) * 0.7) if _all_pb_vals else 0
    _cur_price_pb = float(_rclose_pb.dropna().iloc[-1]) if not _rclose_pb.dropna().empty else 0
    # v18.175:若有 TWSE 官方 PBratio 用官方值,否則自算
    _cur_pb_ratio = _twse_pb if _twse_pb > 0 else (
        _cur_price_pb / _bps_val if _bps_val > 0 else 0)

    _fig_pb.update_layout(
        title=dict(
            text=f'📐 {sid2} {name2} 股價淨值比河流圖（BPS {_bps_val:.2f}元 × PB {_PB_LOW}/{_PB_MID}/{_PB_HIGH} · {_industry_label}）',
            font=dict(color='#8b949e', size=12)),
        height=280, plot_bgcolor='#0e1117', paper_bgcolor='#0e1117',
        font=dict(color='white', size=11),
        margin=dict(l=10, r=10, t=40, b=10),
        xaxis=dict(gridcolor='#21262d'),
        yaxis=dict(range=[_ymin_pb, _ymax_pb], gridcolor='#21262d'),
        hovermode='x unified', showlegend=False)
    st.plotly_chart(_fig_pb, width='stretch', config={'displayModeBar': False})

    _cur_zone_pb = ('🟢 便宜區' if _cur_price_pb < _b_lo_pb else
                    '🟡 合理區' if _cur_price_pb < _b_mi_pb else
                    '🔴 昂貴區' if _cur_price_pb < _b_hi_pb else '⛔ 超昂貴')
    st.caption(
        f'目前位於 {_cur_zone_pb}（現價 {_cur_price_pb:.0f} / '
        f'PB{_PB_LOW}≤{_b_lo_pb:.0f} / PB{_PB_MID}≤{_b_mi_pb:.0f} / PB{_PB_HIGH}≤{_b_hi_pb:.0f}）　'
        f'BPS {_bps_val:.2f}元，當前 PB ≈ {_cur_pb_ratio:.2f} 倍')
    st.info(
        f'ℹ️ **P/B 資料源**：{_bps_source}（v18.175 三段 chain：TWSE BWIBBU_d → FinMind BS → yfinance）。  \n'
        f'**BPS 公式**：股東權益總額 ÷ 流通在外股數（= 普通股股本 ÷ 10 元面額）；或由 TWSE 官方 PBratio 反推（BPS = 股價 / PBratio）。  \n'
        f'**閾值依據**：{_industry_label} → PB {_PB_LOW}/{_PB_MID}/{_PB_HIGH}（v18.175 產業別動態：金融 0.5/0.9/1.2 / 成長科技 1.5/2.5/4.0 / 製造業 0.8/1.5/2.5）。本圖採最新值作橫帶（非逐日 rolling）。'
    )
