"""
ETF 渲染層（render layer）
從 etf_dashboard.py 抽出的 Streamlit / Plotly UI 元件：橫幅 / 走勢圖 / BIAS / 蒙地卡羅 / 類股熱力圖
依賴：etf_fetch（新聞 + 類股漲跌）；不被 fetch / calc 反向依賴。
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go

# v18.396 P5-B1:L4 → L3 → L1,收斂 cache.clear() anti-pattern。
# 原 `from src.data.etf import _fetch_news_for, _fetch_sector_returns` 改走 L3 wrapper。
from src.services.etf_sector_service import get_news_for, get_sector_returns
from src.services.ai_structured_summary import build_structured_summary_prompt  # v18.361 F-6.5:直打 submod 避 services↔ui.render circular
from shared.calc_helpers import calc_bias_pct, calc_bias_pct_series  # R-CALC-3 v18.412 / #23 v18.436
from shared.colors import TRAFFIC_GREEN, TRAFFIC_RED, TRAFFIC_YELLOW


# ── 總經連動配置建議表 ────────────────────────────────────────
MACRO_ALLOC = {
    'bull':    {'股票型ETF': 70, '債券型ETF': 15, '貨幣/現金': 15},
    'neutral': {'股票型ETF': 50, '債券型ETF': 30, '貨幣/現金': 20},
    'bear':    {'股票型ETF': 20, '債券型ETF': 50, '貨幣/現金': 30},
}
MACRO_DESC = {
    'bull':    '🟢 多頭市場：加大股票型ETF比重，可佈局成長型/科技型ETF',
    'neutral': '🟡 中性市場：股債平衡，降低單一類型集中度',
    'bear':    '🔴 空頭市場：大幅降低股票曝險，增加投資級債券ETF + 現金',
}


def macro_allocation_banner(regime: str) -> None:
    """總經連動配置建議橫幅"""
    alloc = MACRO_ALLOC.get(regime, MACRO_ALLOC['neutral'])
    desc  = MACRO_DESC.get(regime, MACRO_DESC['neutral'])
    bg_map  = {'bull': '#0d2618', 'neutral': '#1e1a00', 'bear': '#2a0d0d'}
    brd_map = {'bull': '#2ea043',  'neutral': TRAFFIC_YELLOW,  'bear': TRAFFIC_RED}
    bg  = bg_map.get(regime, '#1a1f2e')
    brd = brd_map.get(regime, '#1f6feb')
    alloc_html = ' &nbsp;|&nbsp; '.join(
        f'<b>{k}</b>&nbsp;<span style="color:#58a6ff;">{v}%</span>'
        for k, v in alloc.items()
    )
    st.markdown(
        f'''<div style="background:{bg};border:1px solid {brd};border-radius:10px;
padding:10px 16px;margin-bottom:14px;">
<div style="font-size:12px;font-weight:700;color:#8b949e;margin-bottom:2px;">
📡 總經連動配置建議（來源：Tab① 市場評估）</div>
<div style="font-size:13px;color:#c9d1d9;">{desc}</div>
<div style="font-size:13px;margin-top:6px;">{alloc_html}</div>
</div>''', unsafe_allow_html=True)


def _colored_box(text: str, color: str = 'green') -> None:
    """統一彩色提示框"""
    cfg = {
        'green':  ('#0d2618', '#2ea043'),
        'yellow': ('#1e1a00', TRAFFIC_YELLOW),
        'red':    ('#2a0d0d', TRAFFIC_RED),
        'blue':   ('#0a1628', '#1f6feb'),
    }
    bg, brd = cfg.get(color, cfg['blue'])
    st.markdown(
        f'<div style="background:{bg};border:1px solid {brd};border-radius:8px;'
        f'padding:10px 14px;margin:6px 0;">{text}</div>',
        unsafe_allow_html=True)


def _teacher_conclusion(teacher: str, indicator_val: str, conclusion: str,
                        action: str = '', color: str | None = None) -> None:
    """ETF dashboard 策略結論卡 — sink shim,委派 ui_widgets.teacher_conclusion SSOT。

    v18.427 Phase 2 Batch 4(D10):原私有副本含 _neg_kw/_pos_kw + HTML 字串建構,
    與 ui_widgets.teacher_conclusion 1:1 重複(差別僅 4 個 ETF 脈絡關鍵字 +
    sink:st.markdown vs string return)。
    SSOT 收斂:ui_widgets 補上 4 個關鍵字後本檔改 thin shim,簽名不變 24 個 caller 無感。
    """
    from src.ui.render.ui_widgets import teacher_conclusion as _ui_tc
    st.markdown(_ui_tc(teacher, indicator_val, conclusion, action, color),
                unsafe_allow_html=True)


def _plot_etf_chart(df: pd.DataFrame, ticker: str,
                    benchmark: str, bench_df: pd.DataFrame) -> None:
    """ETF 走勢圖 + MA50/MA200 + 標準化基準（Y軸：漲幅%，以起始日為0%）"""
    fig   = go.Figure()
    close = df['Close']
    base  = float(close.iloc[0])   # 起始價，用來換算漲幅%

    def _pct(s): return ((s / base) - 1) * 100   # → 相對起始點的漲幅%

    _hover = '%{x|%Y-%m-%d}  %{y:.2f}%<extra></extra>'
    fig.add_trace(go.Scatter(x=df.index, y=_pct(close).round(2),
                              name=ticker, line=dict(color='#58a6ff', width=2),
                              hovertemplate=_hover))
    fig.add_trace(go.Scatter(x=df.index, y=_pct(close.rolling(50).mean()).round(2),
                              name='MA50', line=dict(color='#ffa657', width=1, dash='dot'),
                              hovertemplate=_hover))
    fig.add_trace(go.Scatter(x=df.index, y=_pct(close.rolling(200).mean()).round(2),
                              name='MA200', line=dict(color=TRAFFIC_RED, width=1, dash='dash'),
                              hovertemplate=_hover))
    if not bench_df.empty:
        _bc   = bench_df['Close'].reindex(df.index).ffill().dropna()
        _bc_b = float(_bc.iloc[0])
        _bc_pct = ((_bc / _bc_b) - 1) * 100   # 基準也從0%起算
        fig.add_trace(go.Scatter(x=_bc.index, y=_bc_pct.round(2),
                                  name=f'{benchmark}（基準）',
                                  line=dict(color=TRAFFIC_GREEN, width=1.2, dash='dash'),
                                  hovertemplate=_hover))
    fig.update_layout(
        template='plotly_dark', height=380,
        margin=dict(l=0, r=0, t=20, b=0),
        paper_bgcolor='#0d1117', plot_bgcolor='#0d1117',
        legend=dict(orientation='h', yanchor='bottom', y=1.01),
        yaxis=dict(title='漲幅 (%)', ticksuffix='%', zeroline=True,
                   zerolinecolor='#444', zerolinewidth=1),
    )
    st.plotly_chart(fig, width='stretch')


def _plot_correlation(corr: pd.DataFrame) -> None:
    """相關係數熱力圖"""
    labels = list(corr.columns)
    z      = corr.values.tolist()
    text   = [[f'{v:.2f}' for v in row] for row in z]
    fig = go.Figure(go.Heatmap(
        z=z, x=labels, y=labels,
        text=text, texttemplate='%{text}',
        colorscale='RdBu_r', zmid=0, zmin=-1, zmax=1,
        colorbar=dict(thickness=10),
    ))
    fig.update_layout(
        template='plotly_dark', height=320,
        margin=dict(l=0, r=0, t=10, b=0),
        paper_bgcolor='#0d1117', plot_bgcolor='#0d1117',
    )
    st.plotly_chart(fig, width='stretch')


def _plot_holdings_overlap(mat: pd.DataFrame, title: str = '') -> None:
    """持股 Overlap 熱力圖：0-100% 單向配色（白→紅，越紅越重疊）。

    與 `_plot_correlation` 的差異：
      - 值域 0-100（非 -1 到 1）；不需 zmid
      - 單向 colorscale（紅色越深越同質），跟報酬相關矩陣視覺區分
      - NaN 灰色顯示（資料拿不到的 ETF）
    """
    labels = list(mat.columns)
    z      = mat.values.tolist()
    text   = [[(f'{v:.1f}' if pd.notna(v) else 'N/A') for v in row] for row in z]
    fig = go.Figure(go.Heatmap(
        z=z, x=labels, y=labels,
        text=text, texttemplate='%{text}',
        colorscale=[[0.0, '#0d1117'], [0.3, '#5a2a1e'],
                    [0.6, '#a73c2a'], [1.0, TRAFFIC_RED]],
        zmin=0, zmax=100,
        hoverongaps=False,
        colorbar=dict(thickness=10, title=dict(text='%', font=dict(size=11))),
    ))
    fig.update_layout(
        template='plotly_dark', height=320,
        title=title if title else None,
        margin=dict(l=0, r=0, t=30 if title else 10, b=0),
        paper_bgcolor='#0d1117', plot_bgcolor='#0d1117',
    )
    st.plotly_chart(fig, width='stretch')


def _render_weakness_table(rows) -> None:
    """主動 ETF 弱勢度檢測表格（Gemini「淘汰不適任經理人」邏輯）

    rows: List[dict] from etf_calc.compute_etf_weakness_row()
    顯示欄位：代號 / 名稱 / 主被動 / 經理人 / 任期 / 大跌弱勢率% / 反彈弱勢率% /
              連敗季數 / TE% / 燈號 / 動作建議
    """
    if not rows:
        st.info('無資料可顯示')
        return
    df = pd.DataFrame(rows)
    _display_cols = ['代號', '名稱', '主被動', '經理人', '任期',
                     '大跌弱勢率%', '反彈弱勢率%', '連敗季數', 'TE%',
                     '燈號', '動作建議']
    _cols = [c for c in _display_cols if c in df.columns]
    st.dataframe(
        df[_cols],
        use_container_width=True, hide_index=True,
        column_config={
            '大跌弱勢率%': st.column_config.ProgressColumn(
                '大跌弱勢率%', help='大盤跌日中該 ETF 跌更深的比例',
                format='%.1f%%', min_value=0, max_value=100,
            ),
            '反彈弱勢率%': st.column_config.ProgressColumn(
                '反彈弱勢率%', help='大盤漲日中該 ETF 漲更慢的比例',
                format='%.1f%%', min_value=0, max_value=100,
            ),
            '連敗季數': st.column_config.NumberColumn(
                '連敗季數', help='最近連續輸盤季數（≥2 觸發換股警示）',
            ),
            'TE%': st.column_config.NumberColumn(
                'TE%', help='Tracking error 年化%（主動式越高代表偏離指數越多）',
                format='%.2f%%',
            ),
        },
    )


def _render_bias(df: pd.DataFrame, ticker: str) -> None:
    """BIAS 乖離率：(Close - MAn) / MAn × 100%，顯示 MA20/MA60/MA120"""
    if df is None or len(df) < 20:
        st.info('資料不足，無法計算 BIAS')
        return
    close = df['Close'] if 'Close' in df.columns else df['close']
    bias_rows = []
    for n, label in [(20, 'MA20'), (60, 'MA60'), (120, 'MA120')]:
        if len(close) >= n:
            ma  = float(close.rolling(n).mean().iloc[-1])
            cur = float(close.iloc[-1])
            bias = calc_bias_pct(cur, ma) or 0.0  # R-CALC-3 SSOT
            if bias > 10:
                hint = '🔴 嚴重高估，注意拉回'
            elif bias > 5:
                hint = '🟡 偏高，謹慎追高'
            elif bias < -10:
                hint = '🟢 嚴重低估，逢低佈局機會'
            elif bias < -5:
                hint = '🟡 偏低，可分批承接'
            else:
                hint = '⚪ 中性偏離，正常波動'
            bias_rows.append({'均線': label, 'MA值': f'{ma:.2f}',
                               'BIAS(%)': f'{bias:+.2f}%', '訊號': hint})
    if bias_rows:
        st.dataframe(pd.DataFrame(bias_rows), use_container_width=True, hide_index=True)
        # 視覺化近60日 BIAS(MA20)
        if len(close) >= 60:
            ma20 = close.rolling(20).mean()
            b20  = calc_bias_pct_series(close, ma20)  # #23 v18.436:series SSOT(原 inline)
            b20  = b20.dropna().tail(60)
            fig  = go.Figure(go.Bar(
                x=b20.index, y=b20.values,
                marker_color=[TRAFFIC_RED if v > 0 else TRAFFIC_GREEN for v in b20.values],
                name='BIAS(MA20)',
            ))
            fig.add_hline(y=10,  line_dash='dot', line_color=TRAFFIC_RED,
                          annotation_text='+10%')
            fig.add_hline(y=-10, line_dash='dot', line_color=TRAFFIC_GREEN,
                          annotation_text='-10%')
            fig.update_layout(
                template='plotly_dark', height=220,
                yaxis_title='BIAS %', margin=dict(l=0, r=0, t=20, b=0),
                paper_bgcolor='#0d1117', plot_bgcolor='#0d1117',
            )
            st.plotly_chart(fig, width='stretch')


def render_etf_holdings(ticker: str, holdings: dict = None, top_n: int = 15,
                        key: str = None) -> None:
    """列出 ETF 成分股（持股名稱 → 權重%）：前 top_n 大權重長條圖 + 完整表格。

    holdings 可由呼叫端預先以 fetch_etf_holdings 抓好傳入（避免重複抓取）；
    為 None 時自行抓取。抓不到時顯示友善 ⚪ 提示。
    key：呼叫端傳入唯一識別（組合頁迴圈、單一頁同頁渲染避免 plotly/dataframe
         元件 ID 衝突 StreamlitDuplicateElementId）；未傳則以 ticker 當基底。
    """
    if holdings is None:
        from src.data.etf import fetch_etf_holdings
        with st.spinner(f'抓取 {ticker} 成分股清單...'):
            holdings = fetch_etf_holdings(ticker)
    if not holdings:
        st.caption(f'⚪ {ticker} 成分股清單暫時抓不到（海外 IP 受限或 MoneyDJ/yfinance 端點變動）。'
                   '可至投信官網或公開說明書查閱前十大持股。')
        return
    _k = key or ticker or 'etf'
    _items   = sorted(holdings.items(), key=lambda kv: kv[1], reverse=True)
    _total_w = sum(w for _, w in _items)
    # ── 前 top_n 大權重長條圖（最大者置頂）──
    _top   = _items[:top_n]
    _names = [n for n, _ in _top][::-1]
    _ws    = [w for _, w in _top][::-1]
    fig = go.Figure(go.Bar(
        x=_ws, y=_names, orientation='h',
        marker_color='#1f6feb',
        text=[f'{w:.2f}%' for w in _ws], textposition='outside',
        hovertemplate='%{y}：%{x:.2f}%<extra></extra>',
    ))
    fig.update_layout(
        template='plotly_dark', height=max(240, 26 * len(_top) + 70),
        title=dict(text=f'{ticker} 前 {len(_top)} 大成分股權重',
                   font=dict(size=13, color='#8b949e')),
        xaxis_title='權重 %', margin=dict(l=0, r=40, t=40, b=10),
        paper_bgcolor='#0d1117', plot_bgcolor='#0d1117',
    )
    st.plotly_chart(fig, width='stretch', key=f'etfhold_chart_{_k}')
    # ── 完整成分股表格 ──
    _df = pd.DataFrame(
        [{'排名': i + 1, '成分股': n, '權重(%)': f'{w:.2f}'}
         for i, (n, w) in enumerate(_items)]
    )
    st.dataframe(_df, use_container_width=True, hide_index=True,
                 key=f'etfhold_tbl_{_k}')
    st.caption(f'共 {len(_items)} 檔成分股，合計權重 {_total_w:.1f}%'
               + ('（多數來源僅提供前十大持股，故未達 100%）' if _total_w < 60 else ''))


# ETF → GICS 類股對照（僅涵蓋常見 ETF，未知 ETF 歸入「其他」）
_ETF_SECTOR_MAP = {
    'XLK': '資訊科技', 'QQQ': '資訊科技', '00631L.TW': '資訊科技',
    'XLF': '金融', 'KBE': '金融',
    'XLE': '能源',
    'XLV': '醫療保健',
    'XLI': '工業',
    'XLP': '必需消費', 'XLY': '非必需消費',
    'XLU': '公用事業',
    'XLB': '原材料',
    'XLRE': '房地產', '00712.TW': '房地產',
    'XLC': '通訊服務',
    'SPY': '廣泛市場', 'IVV': '廣泛市場', 'VOO': '廣泛市場',
    '0050.TW': '廣泛市場', '00646.TW': '廣泛市場',
    'BND': '債券', 'AGG': '債券', 'TLT': '債券',
    '00678.TW': '債券', '00720B.TW': '債券',
    '00878.TW': '高股息', '00713.TW': '高股息', '0056.TW': '高股息',
    'GLD': '黃金/原物料', 'IAU': '黃金/原物料',
}


def _check_sector_exposure(rows: list, total_value: float) -> None:
    """計算各 GICS 類股曝險，標記超過 30% 的集中風險"""
    sector_vals: dict = {}
    for r in rows:
        sector = _ETF_SECTOR_MAP.get(r['ticker'], '其他')
        sector_vals[sector] = sector_vals.get(sector, 0) + r['current_value']

    sector_rows = []
    warnings = []
    for sec, val in sorted(sector_vals.items(), key=lambda x: -x[1]):
        pct = val / total_value * 100
        flag = '⚠️ 超限' if pct > 30 else '✅'
        sector_rows.append({'類股': sec, '合計現值(元)': f'{val:,.0f}',
                             '佔比': f'{pct:.1f}%', '狀態': flag})
        if pct > 30:
            warnings.append((sec, pct))

    st.dataframe(pd.DataFrame(sector_rows), use_container_width=True, hide_index=True)
    if warnings:
        for sec, pct in warnings:
            _colored_box(
                f'⚠️ <b>{sec}</b> 類股佔比 <b>{pct:.1f}%</b> 超過 30% 上限，'
                f'建議分散至其他類股或降低持倉', 'red')
    else:
        _colored_box('✅ 所有類股曝險均在 30% 以內，產業分散度良好', 'green')


# ── 美股 11 大 GICS 類股 ETF ─────────────────────────────────
_US_SECTORS = {
    'XLK':  {'name': '科技',        'sub': ['AAPL','MSFT','NVDA','AVGO','AMD']},
    'XLF':  {'name': '金融',        'sub': ['JPM','BAC','WFC','GS','MS']},
    'XLE':  {'name': '能源',        'sub': ['XOM','CVX','COP','SLB','MPC']},
    'XLV':  {'name': '醫療',        'sub': ['LLY','UNH','JNJ','ABBV','MRK']},
    'XLI':  {'name': '工業',        'sub': ['GE','CAT','HON','UPS','BA']},
    'XLP':  {'name': '必需消費',    'sub': ['PG','KO','PEP','COST','WMT']},
    'XLU':  {'name': '公用事業',    'sub': ['NEE','SO','DUK','AEP','D']},
    'XLB':  {'name': '原物料',      'sub': ['LIN','APD','ECL','NEM','FCX']},
    'XLRE': {'name': '房地產',      'sub': ['PLD','AMT','EQIX','CCI','SPG']},
    'XLY':  {'name': '非必需消費',  'sub': ['AMZN','TSLA','HD','MCD','NKE']},
    'XLC':  {'name': '通訊服務',    'sub': ['META','GOOGL','NFLX','DIS','T']},
}

# ── 台股類股代表 ETF/指數成分 ────────────────────────────────
_TW_SECTORS = {
    '2330.TW': {'name': '半導體',    'sub': ['2303.TW','2308.TW','2454.TW','3711.TW','2379.TW']},
    '2317.TW': {'name': '電子製造',  'sub': ['2354.TW','2356.TW','3008.TW','2382.TW','3034.TW']},
    '2412.TW': {'name': '電信',      'sub': ['3045.TW','4904.TW','2409.TW']},
    '2882.TW': {'name': '金融',      'sub': ['2881.TW','2883.TW','2884.TW','2886.TW','2891.TW']},
    '1301.TW': {'name': '塑化',      'sub': ['1303.TW','1326.TW','1402.TW']},
    '2002.TW': {'name': '鋼鐵',      'sub': ['2006.TW','2007.TW','2010.TW']},
    '1216.TW': {'name': '食品',      'sub': ['1201.TW','1210.TW','1225.TW']},
    '2603.TW': {'name': '航運',      'sub': ['2609.TW','2615.TW','2617.TW']},
    '9910.TW': {'name': '觀光',      'sub': ['2706.TW','2707.TW','2727.TW']},
    '3008.TW': {'name': '光電',      'sub': ['2409.TW','3481.TW','2475.TW']},
}

_PERIOD_MAP = {'1日': '5d', '5日': '1mo', '1月': '3mo', '3月': '6mo'}


def _build_treemap_data(sectors: dict, returns: dict, market: str) -> go.Figure:
    """建立 Plotly Treemap 熱力圖"""
    ids, labels, parents, values, texts, colors = [], [], [], [], [], []

    # root
    ids.append(market)
    labels.append(market)
    parents.append('')
    values.append(0)
    texts.append('')
    colors.append(0)

    for ticker, meta in sectors.items():
        sec_ret = returns.get(ticker)
        sec_label = f"{meta['name']}<br>{sec_ret:+.1f}%" if sec_ret is not None else meta['name']
        ids.append(ticker)
        labels.append(sec_label)
        parents.append(market)
        values.append(max(abs(sec_ret) if sec_ret is not None else 1, 0.5))
        texts.append(ticker)
        colors.append(sec_ret if sec_ret is not None else 0)

        # sub-items
        for sub in meta.get('sub', []):
            sub_ret = returns.get(sub)
            sub_label = f"{sub.replace('.TW','')}<br>{sub_ret:+.1f}%" if sub_ret is not None else sub
            ids.append(f'{ticker}/{sub}')
            labels.append(sub_label)
            parents.append(ticker)
            values.append(max(abs(sub_ret) if sub_ret is not None else 0.5, 0.3))
            texts.append(sub)
            colors.append(sub_ret if sub_ret is not None else 0)

    # 顏色：最大值對稱
    max_abs = max(abs(c) for c in colors if c != 0) or 5
    fig = go.Figure(go.Treemap(
        ids=ids, labels=labels, parents=parents,
        values=values, text=texts,
        textinfo='label',
        marker=dict(
            colors=colors,
            colorscale=[[0, '#0f5132'], [0.35, '#1a6e36'], [0.5, '#1e2530'],
                        [0.65, '#c0392b'], [1, '#7b1212']],  # 台灣慣例：漲=紅 跌=綠
            cmid=0, cmin=-max_abs, cmax=max_abs,
            colorbar=dict(title='漲跌%', thickness=12),
            line=dict(width=1, color='#0d1117'),
        ),
        hovertemplate='<b>%{text}</b><br>漲跌：%{marker.color:+.2f}%<extra></extra>',
    ))
    fig.update_layout(
        template='plotly_dark',
        height=600,
        margin=dict(l=0, r=0, t=30, b=0),
        paper_bgcolor='#0d1117',
    )
    return fig


def render_sector_heatmap(gemini_fn=None):
    st.markdown('### 🗺️ 產業熱力圖')
    st.caption('即時抓取各類股漲跌幅，紅=漲 / 綠=跌（台灣慣例）。點選區塊可展開子類股。')
    with st.expander('💡 怎麼用產業熱力圖？', expanded=False):
        st.markdown(
            '**這是什麼**：把各產業/類股的漲跌幅用顏色塊呈現（紅漲綠跌、面積≈權重），一眼看出**資金正流向哪個產業**。\n\n'
            '**實戰看法**：\n'
            '- **強弱輪動**：普綠中某類股獨紅 → 逆勢強勢、資金避風港；普紅中某類股獨綠 → 該產業有壓力。\n'
            '- **類股輪動**：資金常在產業間輪動，連續多日領漲的產業可留意其龍頭股；領跌產業則避開或等落底。\n'
            '- **搭配總經**：升息/通膨 → 金融、能源偏強；降息/復甦 → 科技、成長股偏強（可對照「美林時鐘」）。\n\n'
            '🎯 用途：由上而下選股的第一步 —— **先選對產業，再從強勢產業裡挑個股**。'
        )

    col_m, col_p, col_r = st.columns([2, 2, 1])
    market = col_m.selectbox('市場', ['🇺🇸 美股（GICS 11大類）', '🇹🇼 台股（主要類股）'],
                              key='heatmap_market')
    period_label = col_p.selectbox('計算區間', list(_PERIOD_MAP.keys()),
                                    index=0, key='heatmap_period')
    col_r.markdown('<br>', unsafe_allow_html=True)
    refresh = col_r.button('🔄 刷新', key='heatmap_refresh', use_container_width=True)

    is_us = '美股' in market
    sectors = _US_SECTORS if is_us else _TW_SECTORS
    period  = _PERIOD_MAP[period_label]

    # 收集所有需抓取的 ticker（類股代表 + 子成分）
    all_tickers = list(sectors.keys())
    for meta in sectors.values():
        all_tickers.extend(meta.get('sub', []))
    all_tickers = tuple(set(all_tickers))

    # v19.132 效能:此 tab body 每次 app run 都執行(Streamlit 全 tab body 都跑),
    # 數十檔 batch 冷抓在首次載入就跑(即使 user 當下沒看熱力圖)。改 opt-in:
    # 首次只顯示載入按鈕不冷抓;點過後 session 記住,之後 rerun 走 @st.cache_data
    # 快取即時回。改市場/區間仍會依新 cache key 重抓;🔄 刷新視同載入。
    _loaded_key = 'heatmap_loaded'
    if refresh:
        st.session_state[_loaded_key] = True
    if not st.session_state.get(_loaded_key):
        if st.button('🗺️ 載入產業熱力圖', key='heatmap_load', use_container_width=True):
            st.session_state[_loaded_key] = True
            st.rerun()
        st.info('點上方按鈕載入：批次抓取數十檔類股代表的漲跌幅（首次較久，之後走快取；'
                '改市場/區間會依新條件重抓）。')
        return

    with st.spinner(f'抓取 {len(all_tickers)} 個標的資料（{period_label}）...'):
        # v18.396 P5-B1:cache.clear() 邏輯下沉至 L3 wrapper(refresh kwarg)。
        returns = get_sector_returns(all_tickers, period, refresh=refresh)

    if not returns:
        st.error('❌ 無法取得任何類股資料，請確認網路連線')
        return

    # ── Treemap 主圖 ──────────────────────────────────────────
    market_label = '美股 GICS' if is_us else '台股類股'
    fig = _build_treemap_data(sectors, returns, market_label)
    st.plotly_chart(fig, width='stretch')

    # ── 數值排行表（補充用）──────────────────────────────────
    st.markdown(f'#### 📊 {market_label} 類股漲跌排行（{period_label}）')
    rank_rows = []
    for ticker, meta in sectors.items():
        ret = returns.get(ticker)
        rank_rows.append({
            '類股': meta['name'],
            '代號': ticker,
            f'{period_label}漲跌%': ret if ret is not None else 'N/A',
            '方向': ('📈 上漲' if ret and ret > 0 else ('📉 下跌' if ret and ret < 0 else '➡️ 持平')),
        })
    rank_rows.sort(key=lambda x: x[f'{period_label}漲跌%']
                   if isinstance(x[f'{period_label}漲跌%'], float) else 0, reverse=True)
    rank_df = pd.DataFrame(rank_rows)
    st.dataframe(rank_df, use_container_width=True, hide_index=True)

    # 覆蓋率說明
    fetched = sum(1 for t in sectors if returns.get(t) is not None)
    total_s = len(sectors)
    if fetched < total_s:
        _colored_box(
            f'⚠️ 僅取得 {fetched}/{total_s} 個類股資料，部分可能因 yfinance 限速或市場休市而缺失',
            'yellow')
    else:
        _colored_box(f'✅ 全部 {total_s} 個類股資料取得完整', 'green')

    # ── AI 白話總結 ──────────────────────────────────────────
    if gemini_fn:
        st.markdown('---')
        clicked = st.button('🤖 生成 AI 白話總結', key='sector_ai_btn')
        if clicked:
            # 只取有數據的類股，依漲跌幅排序（最強→最弱）
            valued = [r for r in rank_rows
                      if isinstance(r[f'{period_label}漲跌%'], float)]
            ranking = '、'.join(
                f"{r['類股']} {r[f'{period_label}漲跌%']:+.2f}%" for r in valued
            ) or '目前沒有可用的漲跌資料'

            ups = [r for r in valued if r[f'{period_label}漲跌%'] > 0]
            downs = [r for r in valued if r[f'{period_label}漲跌%'] < 0]
            if valued:
                strongest = valued[0]
                weakest = valued[-1]
                flow = (
                    f"上漲的有 {len(ups)} 個產業、下跌的有 {len(downs)} 個產業。"
                    f"今天最受青睞（漲最多）的是「{strongest['類股']}」"
                    f"（{strongest[f'{period_label}漲跌%']:+.2f}%），"
                    f"最被冷落（跌最多）的是「{weakest['類股']}」"
                    f"（{weakest[f'{period_label}漲跌%']:+.2f}%）。"
                )
            else:
                flow = '目前沒有足夠的資料判斷資金流向。'

            sections = [
                {'name': '今天哪些產業在漲、哪些在跌', 'data': ranking},
                {'name': '錢正在往哪裡跑（資金流向的感覺）', 'data': flow},
            ]
            news_text = get_news_for('台股', '台股 類股 輪動 產業 盤勢', 5)
            prompt = build_structured_summary_prompt(
                subject_title=f'今天的{market_label}產業表現',
                sections=sections,
                news_text=news_text,
                overall_question='現在資金比較偏好哪些產業、有沒有明顯的輪動、一般人可以怎麼看。',
            )
            with st.spinner('AI 正在用白話幫你整理產業輪動...'):
                md = gemini_fn(prompt, max_tokens=1300)
            st.session_state['_sector_ai_md'] = md
            st.markdown(md)
        elif st.session_state.get('_sector_ai_md'):
            st.markdown(st.session_state['_sector_ai_md'])
