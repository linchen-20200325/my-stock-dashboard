"""src/ui/tabs/chip_radar.py — 💠 集保籌碼大戶雷達（自建爬蟲版）

資料來源：norway.twsthr.info `StockHolders.aspx?stock={代號}`（集保戶股權分散表，每週更新）

設計重點
========
- 連線：走既有 `proxy_helper.fetch_url()`（NAS Squid Proxy → 自動降級直連 +
  3 次重試 + 20s timeout + Storm Shield 300s 快取），外加隨機 User-Agent 防爬。
- 解析：`pandas.read_html` 取所有表格 → **自適應**用關鍵字偵測「大戶比例 / 散戶人數 /
  日期」欄位（不硬編脆弱欄名，網站改版也能盡量存活）。
- 快取：`@st.cache_data(ttl=TTL_1DAY)` 一日一抓，降低中繼站負擔。
- 防呆：任何失敗一律回「空 df + 錯誤訊息 + 診斷資料」，UI 端顯示提示，**不拋例外、不死迴圈**。
- 診斷：回傳 read_html 原始表格結構（shape / columns / 前幾列），雲端跑一次即可
  讓使用者/開發者看到實際欄位、必要時再把自適應解析改成精準解析。

回傳契約（dict，cache-safe — 不依賴 DataFrame.attrs 在快取後存活）
    {
        'df':        DataFrame（欄位：日期 / 大戶比例 / 散戶人數；失敗為空）,
        'err':       str（''=成功）,
        'tables':    list[dict]（診斷：每個 read_html 表格的 shape/columns/preview）,
        'html_head': str（read_html 失敗時保留 HTML 開頭片段）,
    }
"""
from __future__ import annotations

import streamlit as st
import pandas as pd

# v18.426 Phase 2 Batch 3b:fetch_chip_concentration + 7 parsing helpers + 2 constants
# 下沉 L1(src/data/stock/chip_concentration_fetcher.py)解 R-UI-FETCH-2 §8.2 違規。
# 本 re-export 維持 backward compat,既有 caller(render_chip_radar)無需改 import path。
from src.data.stock.chip_concentration_fetcher import (  # noqa: F401
    fetch_chip_concentration,
    TWSTHR_URL,
    _UA_POOL,
    _flatten_cols,
    _to_num,
    _find_col,
    _find_major_col,
    _parse_date_series,
    _adaptive_parse,
    _table_diag,
)

# ══════════════════════════════════════════════════════════════════════════════
# Streamlit UI
# ══════════════════════════════════════════════════════════════════════════════
def _plot_chip(df: pd.DataFrame, ticker: str) -> None:
    """Plotly 雙 Y 軸：左=散戶人數(bar)、右=大戶比例(line)。"""
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    _fig = make_subplots(specs=[[{'secondary_y': True}]])
    _has_retail = df['散戶人數'].notna().any()
    _has_major = df['大戶比例'].notna().any()
    _x = df['日期'] if df['日期'].notna().any() else list(range(len(df)))

    if _has_retail:
        _fig.add_trace(
            go.Bar(x=_x, y=df['散戶人數'], name='散戶持股人數',
                   marker_color='#4a9eff', opacity=0.55),
            secondary_y=False)
    if _has_major:
        _fig.add_trace(
            go.Scatter(x=_x, y=df['大戶比例'], name='大戶持股比例 (%)',
                       mode='lines+markers',
                       line=dict(color='#ff6b6b', width=2)),
            secondary_y=True)

    _fig.update_layout(
        title=f'{ticker} 集保籌碼分布（散戶人數 vs 大戶比例）',
        height=440, hovermode='x unified',
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
        margin=dict(t=60, b=40, l=10, r=10))
    _fig.update_yaxes(title_text='散戶持股人數', secondary_y=False)
    _fig.update_yaxes(title_text='大戶持股比例 (%)', secondary_y=True)
    st.plotly_chart(_fig, use_container_width=True)


def _render_diag(result: dict) -> None:
    """解析診斷面板：read_html 原始表格結構（供雲端對齊欄位）。"""
    with st.expander('🔬 解析診斷（read_html 原始結構）', expanded=False):
        if result.get('html_head'):
            st.caption('HTML 開頭片段（read_html 失敗時保留）：')
            st.code(result['html_head'][:600])
        _tables = result.get('tables') or []
        if not _tables:
            st.info('無原始表格資料（多半是連線階段就失敗，未進到 read_html）。')
            return
        st.caption(f'read_html 共解析到 **{len(_tables)}** 個表格：')
        for _t in _tables:
            st.markdown(f"**表 #{_t['idx']}** — shape = {tuple(_t['shape'])}")
            if _t.get('columns'):
                st.write('欄位：', _t['columns'])
            _pv = _t.get('preview')
            if isinstance(_pv, pd.DataFrame) and not _pv.empty:
                st.dataframe(_pv, use_container_width=True, hide_index=True)


def render_chip_radar(ticker: str = '') -> str:
    """💠 集保籌碼大戶雷達。

    ticker 由呼叫端（個股 tab 主代碼 sid2）帶入，不再自建輸入框。
    回傳一段給「AI 首席顧問總結」引用的籌碼摘要字串（無資料回 ''）。
    """
    st.markdown('### 💠 集保籌碼大戶雷達')
    st.caption('資料來源：norway.twsthr.info 集保戶股權分散表（每週更新）；隨上方個股代碼自動查詢。')

    _tk = ''.join(c for c in str(ticker) if c.isalnum())
    if not _tk:
        st.info('💡 請在最上方輸入個股代碼並「載入完整分析」，這裡會自動顯示該檔集保籌碼。')
        return ''

    with st.spinner(f'抓取 {_tk} 集保股權分散表中…（NAS 代理 + 3 次重試）'):
        _result = fetch_chip_concentration(_tk)

    _df = _result.get('df', pd.DataFrame())
    _err = _result.get('err', '')

    if _df is None or _df.empty:
        st.warning('⚠️ 無法解析籌碼資料，請確認目標網站結構或連線狀態')
        if _err:
            st.caption(f'🛈 診斷訊息：{_err}')
        if st.button('🗑️ 清快取重試', key='chip_radar_clear'):
            fetch_chip_concentration.clear()
            st.rerun()
        _render_diag(_result)
        return ''

    # ── 摘要 metric ──
    _latest = _df.iloc[-1]
    _m1, _m2, _m3 = st.columns(3)
    with _m1:
        _d = _latest['日期']
        st.metric('最新資料日', _d.strftime('%Y-%m-%d') if pd.notna(_d) else '—')
    with _m2:
        _mj = _latest['大戶比例']
        st.metric('大戶持股比例', f'{_mj:.2f}%' if pd.notna(_mj) else '—')
    with _m3:
        _rt = _latest['散戶人數']
        st.metric('散戶持股人數', f'{int(_rt):,}' if pd.notna(_rt) else '—')

    # ── 雙 Y 軸圖 ──
    _plot_chip(_df, _tk)

    with st.expander('📑 原始解析資料表', expanded=False):
        st.dataframe(_df, use_container_width=True, hide_index=True)

    _render_diag(_result)

    # ── 給「AI 首席顧問總結」引用的籌碼摘要字串 ──
    _summary = ''
    try:
        _bits = []
        _mj_v = _latest['大戶比例']
        _rt_v = _latest['散戶人數']
        if pd.notna(_mj_v):
            _trend = ''
            if len(_df) >= 5 and pd.notna(_df['大戶比例'].iloc[-5]):
                _delta = float(_mj_v) - float(_df['大戶比例'].iloc[-5])
                _trend = f'（近5期{"↑增" if _delta > 0 else "↓減" if _delta < 0 else "持平"}{_delta:+.2f}%）'
            _bits.append(f'集保大戶持股比例={float(_mj_v):.2f}%{_trend}')
        if pd.notna(_rt_v):
            _bits.append(f'散戶人數={int(_rt_v):,}')
        if _bits:
            _summary = '集保籌碼：' + ' | '.join(_bits)
    except Exception:
        _summary = ''
    return _summary
