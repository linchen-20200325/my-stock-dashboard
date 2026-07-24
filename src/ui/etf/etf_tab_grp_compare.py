"""ETF 多檔批次評分比較 Tab (v18.223)。

UI：textarea 多檔輸入（最多 10 檔，台股可省 .TW）→ ThreadPool 並行抓 5y →
    7 維度標準化加權 → 5 星評等排序表。

複用既有層（零重算）：
- etf_fetch: fetch_etf_price / fetch_etf_dividends / fetch_etf_info
- **etf_scoring_helpers.build_etf_score_row(v19.166)**:每檔 5y row 的所有指標計算
  (含息報酬 / CAGR / 夏普 / MDD / 折溢價 / 5y均殖 / 7%估值 / 配息健康 / σ帶 / 流動性)
  下沉此 L2 SSOT,單檔頁 🚦研判卡與本多檔表**共用同一份 row**(去重);本檔只做 I/O
  (價格 / 股利 / info / 中文名 / compute_etf_quality / 追蹤誤差 benchmark)再餵進去。
- etf_scoring_helpers.compute_etf_composite_score: 7 維度合成 → 星等排序。
"""
from __future__ import annotations

import re as _re
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import streamlit as st

# v18.406 R4:3 fetcher L3 wrapper(EX-PASSTHRU-1 Group A 升級觸發)。
from src.services.etf_grp_compare_service import (
    get_etf_price as fetch_etf_price,
    get_etf_dividends as fetch_etf_dividends,
    get_etf_info as fetch_etf_info,
)
# v18.452:中文名優先 MoneyDJ(fetch_etf_zh_name),與 etf_tab_single.py 同一 SSOT 抓法。
# 舊寫法只用 yfinance shortName/longName,對台股 ETF 常回發行商英文名(如 "Yuanta")
# 而非商品名 —— production bug:00981A.TW 名稱欄顯示錯誤。
from src.data.etf import fetch_etf_zh_name as _fetch_zh_n
from src.compute.etf import (
    # 追蹤誤差 benchmark I/O 仍在 _fetch_one_etf(v18.333 PR-H1)
    auto_detect_benchmark, calc_tracking_error,
    compute_etf_quality, compute_etf_composite_score, recommend_etf_actions,
    normalize_etf_ticker,
    # v19.166:每檔 row 計算下沉 L2 SSOT(單檔/多檔共用);原 calc_* / valuation / health
    # 引用移入 build_etf_score_row,本檔不再直接呼叫(去重)。
    build_etf_score_row,
)
from src.data.core.provenance import prov_log

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


# v18.329 PR-D:_yield_valuation_zone / _dividend_health_label 已抽到 etf_helpers.py SSOT
# (上方 import 重新命名為 _ 前綴維持本檔內呼叫者不變)


def _fetch_one_etf(ticker: str) -> dict:
    """單檔 ETF 5y 抓取 + 組 row(v19.166:純計算下沉 L2 `build_etf_score_row`,單檔/多檔共用 SSOT)。

    線程安全:無 st.* 直呼。此處只做 I/O(價格 / 股利 / info / 中文名 / 品質 /
    追蹤誤差 benchmark),把已抓資料交給 build_etf_score_row 算欄位(§8.1 免重複抓取)。
    """
    try:
        _df = fetch_etf_price(ticker, period='5y')
        if _df is None or _df.empty or 'Close' not in _df.columns:
            _r = build_etf_score_row(ticker, None, None, None)   # error='無 K 線資料'
        else:
            _divs = fetch_etf_dividends(ticker)
            _info = fetch_etf_info(ticker) or {}
            # 中文名優先 MoneyDJ(同 etf_tab_single.py SSOT)→ fallback yfinance → ticker
            _zh_name = _fetch_zh_n(ticker)
            # compute_etf_quality 有 @st.cache_data — 線程內呼叫安全(Streamlit cache 自帶 lock)
            _quality = compute_etf_quality(ticker)
            # 追蹤誤差(vs auto_detect_benchmark — 台股→0050.TW;美股→^GSPC):失敗不阻斷整列
            _te = None
            try:
                _bench = auto_detect_benchmark(ticker)
                if _bench and _bench != ticker:
                    _bench_df = fetch_etf_price(_bench, period='5y')
                    if _bench_df is not None and not _bench_df.empty:
                        _te = calc_tracking_error(_df, _bench_df)
            except Exception as _e_te:
                print(f'[_fetch_one_etf] {ticker} 追蹤誤差計算失敗:'
                      f'{type(_e_te).__name__}: {_e_te}')
            _r = build_etf_score_row(ticker, _df, _divs, _info,
                                     quality=_quality, tracking_error=_te, zh_name=_zh_name)
    except Exception as _e:
        _r = build_etf_score_row(ticker, None, None, None)
        _r['error'] = f'{type(_e).__name__}: {str(_e)[:50]}'
    # v18.356 PR-Q5b S-PROV-1 phase 19:aggregator 級 audit trail
    prov_log('_fetch_one_etf', 'etf_fetch(7-metrics aggregator)',
             f'dict:error={_r.get("error") or "OK"}', ticker=ticker)
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
        # v19.106 ⑨:夏普 rf 動態化 — 批次前經 L3 service 注入即時 FEDFUNDS
        # (1h cache;失敗維持 SSOT fallback 5.33,夏普行為與動態化前相同)
        from src.services.etf_grp_compare_service import ensure_etf_rf_injected
        _rf_live = ensure_etf_rf_injected()
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

    # 留/觀察/換 建議(讀既有分數,不重算;含同類重疊偵測)—— 需在 composite 算完後
    _verdicts = recommend_etf_actions(rows)
    for _r, _v in zip(rows, _verdicts):
        _r['rec_verdict'] = f"{_v['icon']} {_v['verdict']}"
        _r['rec_reason'] = _v.get('reason_text', '')

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
        '🚦 建議':  r.get('rec_verdict', ''),
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
        # v18.333 PR-H1:流動性 + 追蹤誤差 SSOT
        '流動性':   r.get('liquidity_level', '⚪'),
        '追蹤誤差%': r.get('tracking_error'),
        # 標準差建議買賣價位(σ 買賣帶)
        'σ強買≤':   r.get('sigma_buy'),
        'σ減碼≥':   r.get('sigma_sell'),
        'σ位階':    r.get('sigma_z'),
        '建議理由': r.get('rec_reason', ''),
        '備註':     r.get('error') or '',
    } for r in rows])

    # 排序：綜合分高→低（None 殿後）
    df = df.sort_values(
        by='綜合分', ascending=False, na_position='last', kind='stable',
    )
    _full_col_config = {
            '🚦 建議':  st.column_config.TextColumn(
                '🚦 建議',
                help='由既有分數彙整(不重算):綜合分≥0.65(4★)且無紅旗=✅留下;'
                     '<0.35(1★)或紅旗=🔻考慮換;其餘=⚠️觀察。'
                     '紅旗=流動性高風險🔴 / 配息吃本金🔴。詳見「建議理由」欄。'),
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
            # v18.333 PR-H1:流動性 + 追蹤誤差(R-2 audit P1)
            '流動性':   st.column_config.TextColumn(
                '流動性',
                help='綜合 20 日均量 + AUM 規模:🟢 雙健康 / 🟡 偏弱 / 🔴 高風險 / ⚪ 資料不足'),
            '追蹤誤差%': st.column_config.NumberColumn(
                '追蹤誤差%', format='%.2f',
                help='vs 自動偵測基準(台股→0050.TW / 美股→^GSPC):'
                     '> 1.5% 警示;被動式 ETF 應越低越好'),
            'σ強買≤':   st.column_config.NumberColumn(
                'σ強買≤', format='%.2f',
                help='標準差建議「強力買進」價位(252 日滾動 μ−2σ);市價 ≤ 此價 = 歷史相對低點'),
            'σ減碼≥':   st.column_config.NumberColumn(
                'σ減碼≥', format='%.2f',
                help='標準差建議「減碼」價位(μ+2σ);市價 ≥ 此價 = 歷史相對高點'),
            'σ位階':    st.column_config.NumberColumn(
                'σ位階', format='%+.2f',
                help='現價離均線幾個 σ:負=偏低(便宜)、正=偏高(貴);約 ±2 為極端'),
            '建議理由': st.column_config.TextColumn(
                '建議理由', width='large',
                help='彙整綜合分 / 紅旗 / 加碼時機 / 同類重疊的一句話說明'),
    }

    # ── 版面重排(v19.166):主表只留 11 個決策核心欄,完整 24 欄收進下方 expander ──
    # §「整理不減料」:所有欄位仍在(expander 內完整呈現),只是主視圖不再一次攤 24 欄。
    _CORE_COLS = ['代號', '名稱', '🚦 建議', '綜合分', '市價', '費用率%',
                  '殖利率%', '夏普值', 'MDD%', '流動性', '建議理由']
    _core_cols_present = [c for c in _CORE_COLS if c in df.columns]
    st.dataframe(
        df[_core_cols_present], hide_index=True, use_container_width=True,
        column_config={k: v for k, v in _full_col_config.items()
                       if k in _core_cols_present},
    )
    st.caption('👆 主表為 11 個決策核心欄;折溢價 / 1Y·3Y 報酬 / AUM / 5Y均殖 / '
               '7%估值 / 配息健康 / 追蹤誤差 / σ 買賣帶等完整指標見下方 ⬇️')
    with st.expander(f'📊 完整指標({len(df.columns)} 欄:星等 / 折溢價 / 1Y·3Y 報酬 / '
                     'AUM / 5Y均殖 / 7%估值 / 配息健康 / 追蹤誤差 / σ 買賣帶 / 備註)'):
        st.dataframe(
            df, hide_index=True, use_container_width=True,
            column_config=_full_col_config,
        )
    st.caption(
        '💡 **7 維權重**：1Y 累積 25% / 3Y CAGR 20% / 夏普 15% / MDD 15% / '
        '費用率 12% / AUM 8% / 殖利率穩定度 5%。'
        '**星等映射**（綜合分）：≥0.80 5★、≥0.65 4★、≥0.50 3★、≥0.35 2★、<0.35 1★。'
        '缺資料因子自動 rescale 有效權重。'
        '**6 SSOT 補欄**：折溢價（calc_premium_discount）/ 7%估值（calc_avg_yield + 孫慶龍策略）'
        '/ 配息健康（MK 框架 #1+#2 ✅雙贏/🔴吃本金）/ 品質星等（已含於綜合分）'
        '/ 流動性（calc_liquidity_score 20D 均量+AUM）'
        '/ 追蹤誤差（calc_tracking_error vs 自動偵測 benchmark）。'
        ' **σ 建議買賣價位**（compute_std_bands 252 日）：σ強買≤（μ−2σ 相對低點）'
        '/ σ減碼≥（μ+2σ 相對高點）/ σ位階（現價離均線幾個 σ）。'
    )
    st.info(
        '🚦 **怎麼看「留 / 觀察 / 換」**（把上面各欄一句話收斂,**不是投資建議**,決策仍在你）：\n\n'
        '- **✅ 留下**：綜合分 ≥0.65（4★↑）且沒紅旗 —— 體質好,續抱；價位偏低時可分批加碼。\n'
        '- **⚠️ 觀察**：綜合分中段（2★~3★),或體質好但踩到 1 個紅旗 —— 先別加碼,下一季再看。\n'
        '- **🔻 考慮換**：綜合分 <0.35（1★）或紅旗嚴重 —— 想想有沒有同類更好的可替換。\n'
        '- **紅旗**：流動性🔴（量小/規模小不好進出）、配息🔴吃本金（領到的息 < 賠掉的價差）。\n'
        '- **同類重疊**：若你同一類（如高股息、市值型）買了 2 檔以上,系統會提示「留分數最高那檔、其餘擇一」'
        '—— 真正的抗跌分散來自**不同資產類別（股 vs 債 vs 現金）**,不是多買幾檔同質 ETF。\n\n'
        '⚠️ 綜合分只評「體質」,沒把你的**買進成本 / 資產配置需求**算進去；'
        '真的要賣前,請一併看「7%估值 / σ位階（是不是剛好貴）」與你的整體股債比。'
    )
