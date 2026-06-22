"""ETF 多檔批次評分比較 Tab (v18.223)。

UI：textarea 多檔輸入（最多 10 檔，台股可省 .TW）→ ThreadPool 並行抓 5y →
    7 維度標準化加權 → 5 星評等排序表。

複用既有層（零重算）：
- etf_fetch: fetch_etf_price / fetch_etf_dividends / fetch_etf_info
- etf_calc: calc_total_return_1y / calc_current_yield / calc_sharpe / calc_mdd / calc_cagr
- etf_quality.compute_etf_quality: 借用 yield_cv 子分（殖利率穩定度）
- etf_scoring_helpers.compute_etf_composite_score: 7 維度合成
"""
from __future__ import annotations

import re as _re
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import streamlit as st

from etf_fetch import fetch_etf_price, fetch_etf_dividends, fetch_etf_info
from etf_calc import (
    calc_total_return_1y, calc_current_yield,
    calc_sharpe, calc_mdd, calc_cagr,
    calc_avg_yield, calc_premium_discount,
)
from etf_quality import compute_etf_quality
from etf_scoring_helpers import compute_etf_composite_score
from etf_helpers import normalize_etf_ticker
from shared.thresholds import YIELD_HIGH, YIELD_MID, YIELD_LOW

_TOKEN_RE = _re.compile(r'[A-Za-z0-9.]+')


def parse_etf_codes(raw: str, limit: int = 10) -> list[str]:
    """解析多檔 ETF（逗號/空格/換行）。共用 normalize_etf_ticker SSOT — 台股純 4-6 碼自動補 .TW。"""
    if not raw:
        return []
    _out: list[str] = []
    _seen: set = set()
    for _t in _TOKEN_RE.findall(raw):
        _t = normalize_etf_ticker(_t)
        if not _t or _t in _seen:
            continue
        _seen.add(_t)
        _out.append(_t)
        if len(_out) >= limit:
            break
    return _out


def _yield_valuation_zone(cur_yield: float | None, avg_yield: float | None) -> str:
    """7% 存股估值買賣點 — 鏡像 etf_tab_single L262-298 孫慶龍策略。

    需 5y 平均殖利率有值才判定，否則 "—"。
    """
    if not avg_yield or avg_yield <= 0 or cur_yield is None:
        return '—'
    if cur_yield >= YIELD_HIGH:
        return '🟢 強烈買進'
    if cur_yield <= YIELD_LOW:
        return '🔴 獲利了結'
    if cur_yield <= YIELD_MID:
        return '🟡 適度減碼'
    return '⚪ 中性持有'


def _dividend_health_label(cur_yield: float | None,
                           total_ret_1y: float | None,
                           cagr_3y: float | None) -> str:
    """配息健康度 — 鏡像 etf_tab_single L231-246 MK 框架 #1+#2。

    含息報酬 ≥ 殖利率 = 雙贏 ✅；含息 < 殖利率 = 本金侵蝕 🔴；
    無配息直接看 3Y CAGR ≥ 7% 達標 ✅ 否則 🟡。
    """
    if cur_yield is None or cur_yield <= 0:
        if cagr_3y is None:
            return '⬜ 資料不足'
        return '✅ 無息但達標' if cagr_3y >= 7 else '🟡 無息且未達標'
    if total_ret_1y is None:
        return '⬜ 1Y 報酬缺'
    if total_ret_1y < cur_yield:
        return f'🔴 吃本金 {total_ret_1y - cur_yield:+.1f}pp'
    return f'✅ 雙贏 {total_ret_1y - cur_yield:+.1f}pp'


def _fetch_one_etf(ticker: str) -> dict:
    """單檔 ETF 5y 抓取 + 7 維度指標 + 4 SSOT 補欄（折溢價/7%估值/配息健康/品質）。線程安全：無 st.* 直呼。"""
    _r = {
        'ticker': ticker, 'name': '', 'error': None,
        'price': None, 'total_ret_1y': None, 'cagr_3y': None,
        'sharpe': None, 'mdd': None,
        'expense_ratio': None, 'aum': None,
        'div_yield': None, 'beta': None, 'quality': None,
        # v18.224：補單檔分析的 4 SSOT 欄
        'premium_pct': None, 'stale_nav': False,
        'avg_yield_5y': None, 'valuation_zone': '—',
        'dividend_health': '⬜ 資料不足',
    }
    try:
        _df = fetch_etf_price(ticker, period='5y')
        if _df is None or _df.empty or 'Close' not in _df.columns:
            _r['error'] = '無 K 線資料'
            return _r
        _divs = fetch_etf_dividends(ticker)
        _info = fetch_etf_info(ticker) or {}
        _r['name'] = (_info.get('shortName') or _info.get('longName')
                      or ticker)[:30]
        _r['price'] = round(float(_df['Close'].iloc[-1]), 2)
        _r['total_ret_1y'] = calc_total_return_1y(_df, _divs)
        _r['div_yield'] = calc_current_yield(_df, _divs)
        _r['cagr_3y'] = calc_cagr(_df)
        _r['sharpe'] = calc_sharpe(_df)
        _r['mdd'] = calc_mdd(_df)
        _r['expense_ratio'] = _info.get('annualReportExpenseRatio')
        _r['aum'] = _info.get('totalAssets')
        _r['beta'] = _info.get('beta') or _info.get('beta3Year')
        # compute_etf_quality 有 @st.cache_data(ttl=TTL_1DAY) — 線程內呼叫安全（Streamlit cache 自帶 lock）
        _r['quality'] = compute_etf_quality(ticker)

        # v18.224：4 SSOT 補欄（折溢價 / 7% 估值 / 配息健康度）
        try:
            _pd_res = calc_premium_discount(_info, _df, ticker)
            _r['premium_pct'] = _pd_res.get('premium_pct')
            _r['stale_nav'] = bool(_pd_res.get('stale_nav'))
        except Exception:
            pass
        try:
            _r['avg_yield_5y'] = calc_avg_yield(_df, _divs, years=5)
        except Exception:
            pass
        _r['valuation_zone'] = _yield_valuation_zone(
            _r['div_yield'], _r['avg_yield_5y'])
        _r['dividend_health'] = _dividend_health_label(
            _r['div_yield'], _r['total_ret_1y'], _r['cagr_3y'])
    except Exception as _e:
        _r['error'] = f'{type(_e).__name__}: {str(_e)[:50]}'
    return _r


def render_etf_grp_compare() -> None:
    """多檔 ETF 批次評分比較主入口 — 7 維度加權 5 星制 PK 表。"""
    st.markdown('### 📊 多檔 ETF 評分比較 — 7 維度加權 5 星評等')
    st.caption(
        '輸入最多 10 檔 ETF（逗號/空格/換行；台股純數字自動補 .TW），'
        '系統並行抓 5y 數據 + 算 7 維度（1Y 累積 / 3Y CAGR / 夏普 / MDD / '
        '費用率 / AUM / 殖利率穩定度）→ 加權 → 1~5 星評等橫向 PK。'
    )

    raw = st.text_area(
        'ETF 代碼（逗號/空格/換行；最多 10 檔）',
        value='0050 0056 00878 00919 00929',
        height=80, key='_etf_grp_input',
    )
    tickers = parse_etf_codes(raw, limit=10)
    if not tickers:
        st.info('請輸入至少 1 檔 ETF 代碼。')
        return
    st.caption(f'📋 待評分：{", ".join(tickers)}（共 {len(tickers)} 檔）')

    if not st.button('🎯 開始批次評分', type='primary',
                     use_container_width=True, key='_etf_grp_run'):
        st.info('💡 點上方按鈕並行抓 5y 數據 + 計算 7 維度（首次 ~20s，已快取秒回）。')
        return

    # 快取防 rerun 重跑（key 含 tickers tuple）
    _cache_key = f'_etf_grp_results_{hash(tuple(tickers))}'
    rows = st.session_state.get(_cache_key)
    if rows is None:
        rows = []
        prog = st.progress(0.0, text=f'批次評分中（{len(tickers)} 檔並行）...')
        with ThreadPoolExecutor(max_workers=5) as _ex:
            _futs = {_ex.submit(_fetch_one_etf, _t): _t for _t in tickers}
            _done = 0
            for _fut in as_completed(_futs):
                _done += 1
                prog.progress(_done / len(tickers),
                              text=f'[{_done}/{len(tickers)}] 完成')
                try:
                    rows.append(_fut.result())
                except Exception as _e:
                    rows.append({'ticker': _futs[_fut],
                                 'error': f'{type(_e).__name__}: {str(_e)[:50]}'})
        prog.empty()
        # 維持輸入順序排列（as_completed 是完成順序）
        _order = {_t: _i for _i, _t in enumerate(tickers)}
        rows.sort(key=lambda r: _order.get(r['ticker'], 999))
        st.session_state[_cache_key] = rows

    # 合成評分
    for _r in rows:
        if _r.get('error'):
            _r['composite'] = None
            _r['stars'] = None
            continue
        _r['composite'], _r['stars'] = compute_etf_composite_score(_r)

    # ── 統計卡 ──
    _n_ok = sum(1 for r in rows if r.get('stars'))
    _n_5 = sum(1 for r in rows if r.get('stars') == 5)
    _n_4 = sum(1 for r in rows if r.get('stars') == 4)
    _n_3 = sum(1 for r in rows if r.get('stars') == 3)
    _n_low = sum(1 for r in rows if r.get('stars') and r['stars'] <= 2)
    cols = st.columns(5)
    cols[0].metric('🌟 5 星', _n_5)
    cols[1].metric('⭐ 4 星', _n_4)
    cols[2].metric('✨ 3 星', _n_3)
    cols[3].metric('💧 ≤2 星', _n_low)
    cols[4].metric('❌ 抓取失敗', len(rows) - _n_ok)

    # ── 評分表 ──
    def _stars_str(s):
        return ('★' * s + '☆' * (5 - s)) if s else '—'

    df = pd.DataFrame([{
        '代號':     r['ticker'],
        '名稱':     r.get('name', ''),
        '星等':     _stars_str(r.get('stars')),
        '綜合分':   r.get('composite'),
        '市價':     r.get('price'),
        # v18.224：折溢價 SSOT（stale 時帶 ⚠️）
        '折溢價%':  ('⚠️ NAV stale' if r.get('stale_nav')
                    else r.get('premium_pct')),
        '1Y 累積%': r.get('total_ret_1y'),
        '3Y CAGR%': r.get('cagr_3y'),
        '夏普值':   r.get('sharpe'),
        'MDD%':     r.get('mdd'),
        '費用率%':  (r['expense_ratio'] * 100
                    if r.get('expense_ratio') is not None else None),
        'AUM(億)':  (r['aum'] / 1e8
                    if r.get('aum') and r['aum'] > 0 else None),
        '殖利率%':  r.get('div_yield'),
        '5Y均殖%':  r.get('avg_yield_5y'),
        '7%估值':   r.get('valuation_zone', '—'),
        '配息健康': r.get('dividend_health', '⬜'),
        '備註':     r.get('error') or '',
    } for r in rows])

    # 排序：綜合分高→低（None 殿後）
    df = df.sort_values(
        by='綜合分', ascending=False, na_position='last', kind='stable',
    )
    st.dataframe(
        df, hide_index=True, use_container_width=True,
        column_config={
            '綜合分':   st.column_config.NumberColumn('綜合分', format='%.2f'),
            '折溢價%':  st.column_config.Column(
                '折溢價%',
                help='(市價 − NAV) / NAV × 100；> +1% 警示。主動式 ETF NAV stale 顯示 ⚠️'),
            '1Y 累積%': st.column_config.NumberColumn('1Y 累積%', format='%.2f'),
            '3Y CAGR%': st.column_config.NumberColumn('3Y CAGR%', format='%.2f'),
            '夏普值':   st.column_config.NumberColumn('夏普值', format='%.2f'),
            'MDD%':     st.column_config.NumberColumn('MDD%', format='%.2f'),
            '費用率%':  st.column_config.NumberColumn('費用率%', format='%.2f'),
            'AUM(億)':  st.column_config.NumberColumn('AUM(億)', format='%,.1f'),
            '殖利率%':  st.column_config.NumberColumn('殖利率%', format='%.2f'),
            '5Y均殖%':  st.column_config.NumberColumn(
                '5Y均殖%', format='%.2f',
                help='近 5 年平均殖利率（孫慶龍 7% 存股聖經估值基準）'),
            '7%估值':   st.column_config.TextColumn(
                '7%估值',
                help='孫慶龍策略：殖利率≥7%🟢強烈買進 / 5%~7%⚪中性 / 3%~5%🟡減碼 / ≤3%🔴獲利了結'),
            '配息健康': st.column_config.TextColumn(
                '配息健康',
                help='MK 框架 #1+#2：含息報酬 ≥ 殖利率 = ✅雙贏；< 殖利率 = 🔴吃本金'),
        },
    )
    st.caption(
        '💡 **7 維權重**：1Y 累積 25% / 3Y CAGR 20% / 夏普 15% / MDD 15% / '
        '費用率 12% / AUM 8% / 殖利率穩定度 5%。'
        '**星等映射**（綜合分）：≥0.80 5★、≥0.65 4★、≥0.50 3★、≥0.35 2★、<0.35 1★。'
        '缺資料因子自動 rescale 有效權重。'
        '**4 SSOT 補欄**：折溢價（calc_premium_discount）/ 7%估值（calc_avg_yield + 孫慶龍策略）'
        '/ 配息健康（MK 框架 #1+#2 ✅雙贏/🔴吃本金）/ 品質星等（已含於綜合分）。'
    )
