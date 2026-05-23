"""🎯 智慧選股 TAB — 三階段濾網（基本面 / 籌碼技術 / AI 綜合建議）

Per CLAUDE.md §2 設計：使用者輸入觀察清單 10-30 檔，按鈕觸發批次跑（不全市場掃描避免 API 風暴）

三階段邏輯（MVP 第一版 — 12 項條件中 7 項即時實作 + 5 項 placeholder ⏳ 待補）
==========================================================================

Stage 1：基本面防禦與成長
- ✅ 負債比 < 50%（FinMind 資產負債表）
- ✅ 三率三升 YoY（毛利率 / 營益率 / 淨利率）
- ✅ 連續 5 年配息 + 平均殖利率 > 7%（yfinance.dividends）
- ✅ PE 河流圖區間（便宜 / 合理 / 昂貴 — 與 tab_stock 同邏輯）
- ⏳ 應收周轉 / 存貨周轉 / 合約負債 YoY / 資本支出 / 清算價值（後續 PR 補）

Stage 2：籌碼與技術面鎖定
- ✅ 股價站穩 MA20 + 月線翻揚
- ✅ MACD 綠轉紅 / 柱狀體收斂轉發散
- ✅ KD 低檔黃金交叉（K < 20）
- ⏳ 投信連續 5 日買超（後續 PR 補）
- ⏳ 大戶 400 張持股 2 週增加 / 布林開口（後續 PR 補）

Stage 3：AI 綜合建議
- ✅ Gemini Markdown 報告 — 積極型 / 保守型 / 止損紀律三型分析

呼叫端
======
- app.py 經 tab_screener 旁邊新 tab `🎯 智慧選股` 取用
"""
from __future__ import annotations

import streamlit as st


def render_tab_stock_picker(gemini_fn=None):
    # ─ Late imports（避免循環 import + 啟動時間）─
    import datetime as _dt_sp
    import pandas as pd
    import yfinance as yf

    st.markdown('### 🎯 智慧選股 — 三階段濾網')
    st.caption('專業台股投資策略：① 基本面防禦 → ② 籌碼技術 → ③ AI 綜合建議。'
               '輸入觀察清單 10-30 檔，系統自動跑三階段篩選並提供配置建議。')
    st.caption('💡 MVP 第一版：實作 7 項即時條件 + 5 項「⏳ 待補」placeholder（後續 PR 補實）。')

    # ── Section 1：輸入觀察清單（沿用組合配置 data_editor 慣例）─────
    st.markdown('#### 📋 輸入觀察清單（股票代號 4 位數，10-30 檔）')
    _default = pd.DataFrame({
        '股票代號': ['2330', '0050', '00878', '2412', '2454'],
        '備註':     ['台積電', '元大台灣50', '國泰永續高股息', '中華電', '聯發科'],
    })
    edited_df = st.data_editor(
        _default, num_rows='dynamic', hide_index=True,
        use_container_width=True, key='picker_table',
        column_config={
            '股票代號': st.column_config.TextColumn('股票代號', required=True, width='small',
                                                   help='4 位數台股代號（不需 .TW 後綴）'),
            '備註':    st.column_config.TextColumn('備註', width='medium',
                                                   help='公司名稱或標籤'),
        })

    if not st.button('🎯 開始三階段篩選', key='picker_btn',
                     use_container_width=True, type='primary'):
        st.info('💡 填好上方觀察清單後按「🎯 開始三階段篩選」')
        return

    # ── 解析清單 ─────────────────────────────────────────────
    _tickers: list[str] = []
    for _, _row in edited_df.iterrows():
        _tk = str(_row.get('股票代號') or '').strip()
        _tk = ''.join(c for c in _tk if c.isdigit())  # 只留數字
        if len(_tk) >= 4 and _tk not in _tickers:
            _tickers.append(_tk)
    if not _tickers:
        st.error('❌ 請至少輸入一筆有效 4 位數股票代號')
        return
    if len(_tickers) > 30:
        st.warning(f'⚠️ 超過 30 檔（{len(_tickers)}），僅取前 30 檔避免 API 風暴')
        _tickers = _tickers[:30]

    # ── 跑三階段篩選 ─────────────────────────────────────────
    _today = _dt_sp.date.today()
    results: list[dict] = []
    with st.spinner(f'三階段篩選中（{len(_tickers)} 檔）...'):
        for _tk in _tickers:
            _r = _check_one_stock(_tk, _today, yf)
            results.append(_r)

    # ── Stage 1：基本面表 ─────────────────────────────────────
    st.markdown('---')
    st.markdown('#### 📊 Stage 1：基本面防禦與成長')
    _s1_df = pd.DataFrame([{
        '代號':         r['ticker'],
        '備註':         r.get('note', ''),
        '負債比':       r['debt_ratio_label'],
        '三率三升':     r['three_rate_label'],
        '5 年配息':     r['div_5y_label'],
        'PE 區間':      r['pe_zone_label'],
        '應收/存貨':    '⏳ 待補',
        '合約負債/Capex': '⏳ 待補',
        '清算價值':     '⏳ 待補',
        'S1 通過':      f"{r['s1_pass_cnt']}/4",
    } for r in results])
    st.dataframe(_s1_df, hide_index=True, use_container_width=True)
    st.caption('💡 通過數 = 4 項實作條件中過的個數；3+ 通過視為基本面健康。')

    # ── Stage 2：籌碼 + 技術 ──────────────────────────────────
    st.markdown('#### ⚡ Stage 2：籌碼與技術面鎖定（發動訊號）')
    _s2_df = pd.DataFrame([{
        '代號':       r['ticker'],
        '備註':       r.get('note', ''),
        'MA20 站穩':  r['ma20_label'],
        'MACD 翻紅':  r['macd_label'],
        'KD 黃叉':    r['kd_label'],
        '投信買超':   '⏳ 待補',
        '大戶/布林':  '⏳ 待補',
        'S2 通過':    f"{r['s2_pass_cnt']}/3",
    } for r in results])
    st.dataframe(_s2_df, hide_index=True, use_container_width=True)
    st.caption('💡 S1 ≥ 3 且 S2 ≥ 2 → 進入 Stage 3 AI 重點分析。')

    # ── 通過清單 ─────────────────────────────────────────────
    _qualified = [r for r in results if r['s1_pass_cnt'] >= 3 and r['s2_pass_cnt'] >= 2]
    if _qualified:
        st.success(f'✅ 通過兩階段濾網：{len(_qualified)} 檔 → {[r["ticker"] for r in _qualified]}')
    else:
        st.warning('⚠️ 觀察清單中沒有同時通過 Stage 1 (3/4) + Stage 2 (2/3) 的標的')

    # ── Stage 3：AI 綜合建議 ──────────────────────────────────
    st.markdown('---')
    st.markdown('#### 🧠 Stage 3：AI 綜合操作建議')
    if not gemini_fn:
        st.warning('⚠️ 未設定 GEMINI_API_KEY，無法生成 AI 建議')
        return
    if not _qualified:
        st.info('💡 無通過標的可生成 AI 建議；可嘗試擴大觀察清單或放寬條件')
        return
    if st.button('🤖 生成 AI 三型建議報告（積極 / 保守 / 止損紀律）',
                 key='picker_ai_btn', use_container_width=True, type='primary'):
        with st.spinner('AI 三型策略分析中（約 8-12 秒）...'):
            _md = _generate_ai_report(gemini_fn, _qualified, results)
        st.markdown(_md)


# ══════════════════════════════════════════════════════════════
# 主檢測函式：對單檔個股跑完所有可實作條件
# ══════════════════════════════════════════════════════════════

def _check_one_stock(ticker: str, today, yf) -> dict:
    """對單檔個股跑完 Stage 1 (4 項) + Stage 2 (3 項) — 失敗條件統一回灰色 ❓ 不阻斷流程。"""
    _r = {
        'ticker': ticker,
        'note':   '',
        # Stage 1 labels
        'debt_ratio_label':  '❓ N/A',
        'three_rate_label':  '❓ N/A',
        'div_5y_label':      '❓ N/A',
        'pe_zone_label':     '❓ N/A',
        's1_pass_cnt':       0,
        # Stage 2 labels
        'ma20_label':        '❓ N/A',
        'macd_label':        '❓ N/A',
        'kd_label':          '❓ N/A',
        's2_pass_cnt':       0,
    }
    # ── 抓 K 線（yfinance + .TW / .TWO 雙後綴重試）──
    _df = None
    for _sfx in ('.TW', '.TWO'):
        try:
            _t_yf = yf.Ticker(f'{ticker}{_sfx}')
            _df_tmp = _t_yf.history(period='1y')
            if _df_tmp is not None and not _df_tmp.empty and len(_df_tmp) >= 60:
                _df = _df_tmp
                break
        except Exception:
            continue
    if _df is None:
        _r['ma20_label'] = '❌ 抓不到 K 線'
        _r['macd_label'] = '❌ 抓不到 K 線'
        _r['kd_label'] = '❌ 抓不到 K 線'
        return _r

    # ── Stage 1 條件 ──────────────────────────────────────────
    _r['debt_ratio_label'] = _check_debt_ratio(ticker)
    _r['three_rate_label'] = _check_three_rate_growth(ticker)
    _r['div_5y_label']     = _check_dividend_5y(_df, _t_yf)
    _r['pe_zone_label']    = _check_pe_zone(ticker, _df)
    _r['s1_pass_cnt'] = sum(1 for k in ('debt_ratio_label', 'three_rate_label',
                                          'div_5y_label', 'pe_zone_label')
                              if _r[k].startswith('✅'))

    # ── Stage 2 條件 ──────────────────────────────────────────
    _r['ma20_label'] = _check_ma20_uptrend(_df)
    _r['macd_label'] = _check_macd_bullish(_df)
    _r['kd_label']   = _check_kd_golden_cross(_df)
    _r['s2_pass_cnt'] = sum(1 for k in ('ma20_label', 'macd_label', 'kd_label')
                              if _r[k].startswith('✅'))
    return _r


# ══════════════════════════════════════════════════════════════
# Stage 1 純函式（基本面）
# ══════════════════════════════════════════════════════════════

def _check_debt_ratio(stock_id: str) -> str:
    """負債比 < 50%（金融股例外，但本版簡化不分業）。"""
    try:
        from data_loader import fetch_financial_statements
        _fs = fetch_financial_statements(stock_id)
        _bs = _fs.get('balance_sheet') if isinstance(_fs, dict) else None
        if _bs is None or (hasattr(_bs, 'empty') and _bs.empty):
            return '❓ N/A'
        # 找最近一期：總負債 / 總資產
        _liab = _assets = None
        for _col in _bs.columns:
            _cs = str(_col)
            if '總負債' in _cs or 'Total Liabilities' in _cs:
                _liab = float(_bs[_col].iloc[0])
            if '總資產' in _cs or 'Total Assets' in _cs:
                _assets = float(_bs[_col].iloc[0])
        if _liab is None or _assets is None or _assets <= 0:
            return '❓ 找不到欄位'
        _ratio = _liab / _assets * 100
        return f'✅ {_ratio:.1f}%' if _ratio < 50 else f'❌ {_ratio:.1f}%'
    except Exception as _e:
        return f'❓ {type(_e).__name__}'


def _check_three_rate_growth(stock_id: str) -> str:
    """三率三升：毛利率 / 營益率 / 淨利率近季 YoY 同步成長。"""
    try:
        from data_loader import fetch_financial_statements
        _fs = fetch_financial_statements(stock_id)
        _is_df = _fs.get('income_statement') if isinstance(_fs, dict) else None
        if _is_df is None or (hasattr(_is_df, 'empty') and _is_df.empty) or len(_is_df) < 5:
            return '❓ 不足 5 季'
        # 假設 _is_df rows = 季度由近到遠；計算近 1Q vs 4Q 前同期
        # 簡化：直接從欄位取毛利率/營益率/淨利率（FinMind 提供率值或計算）
        _ups = 0
        for _kw in ('毛利率', '營業利益率', '稅後淨利率'):
            for _col in _is_df.columns:
                if _kw in str(_col):
                    _v_now = float(_is_df[_col].iloc[0])
                    _v_yoy = float(_is_df[_col].iloc[4])
                    if _v_now > _v_yoy:
                        _ups += 1
                    break
        return f'✅ {_ups}/3 升' if _ups == 3 else f'❌ {_ups}/3 升'
    except Exception as _e:
        return f'❓ {type(_e).__name__}'


def _check_dividend_5y(df, yf_ticker) -> str:
    """連續 5 年配息 + 平均殖利率 > 7%。"""
    try:
        _divs = yf_ticker.dividends
        if _divs is None or _divs.empty or len(_divs) < 5:
            return '❌ 配息 <5 次'
        # 年度化 — 最近 5 年除息總額
        import pandas as _pd_d
        _divs.index = _pd_d.to_datetime(_divs.index)
        try:
            _divs.index = _divs.index.tz_localize(None)
        except Exception:
            pass
        _last5y = _divs.last('5Y') if hasattr(_divs, 'last') else _divs.tail(5)
        # 5 年平均年配
        _avg_annual_div = _last5y.sum() / 5 if len(_last5y) > 0 else 0
        _cur_price = float(df['Close'].iloc[-1])
        _yield_pct = (_avg_annual_div / _cur_price * 100) if _cur_price > 0 else 0
        if len(_divs.last('5Y') if hasattr(_divs, 'last') else _divs) >= 5 and _yield_pct > 7:
            return f'✅ {_yield_pct:.2f}%'
        elif _yield_pct > 0:
            return f'❌ {_yield_pct:.2f}%'
        else:
            return '❌ 無配息'
    except Exception as _e:
        return f'❓ {type(_e).__name__}'


def _check_pe_zone(stock_id: str, df) -> str:
    """PE 河流圖區間（簡化：用近 1Y PE 三分位判讀便宜/合理/昂貴）。"""
    try:
        from data_loader import fetch_financial_statements
        _fs = fetch_financial_statements(stock_id)
        _is_df = _fs.get('income_statement') if isinstance(_fs, dict) else None
        if _is_df is None or (hasattr(_is_df, 'empty') and _is_df.empty):
            return '❓ N/A EPS'
        # TTM EPS = 近 4 季 EPS 加總
        _eps_col = next((c for c in _is_df.columns if 'EPS' in str(c) or '每股盈餘' in str(c)), None)
        if _eps_col is None:
            return '❓ 找不到 EPS'
        _eps_ttm = sum(float(_is_df[_eps_col].iloc[i]) for i in range(min(4, len(_is_df))))
        if _eps_ttm <= 0:
            return '⚠️ 虧損股'
        _cur_price = float(df['Close'].iloc[-1])
        _pe = _cur_price / _eps_ttm
        # 三分位閾值（通用：10 / 15 / 20）
        if _pe < 10:
            return f'✅ 便宜 {_pe:.1f}'
        elif _pe < 15:
            return f'✅ 合理 {_pe:.1f}'
        elif _pe < 20:
            return f'❌ 昂貴 {_pe:.1f}'
        else:
            return f'❌ 超昂貴 {_pe:.1f}'
    except Exception as _e:
        return f'❓ {type(_e).__name__}'


# ══════════════════════════════════════════════════════════════
# Stage 2 純函式（籌碼 + 技術）
# ══════════════════════════════════════════════════════════════

def _check_ma20_uptrend(df) -> str:
    """股價 > MA20 且 MA20 翻揚（近 5 日 MA20 斜率為正）。"""
    try:
        _ma20 = df['Close'].rolling(20).mean()
        if len(_ma20.dropna()) < 5:
            return '❓ 不足 25 日'
        _cur = float(df['Close'].iloc[-1])
        _ma20_now = float(_ma20.iloc[-1])
        _ma20_5d_ago = float(_ma20.iloc[-6])
        _above = _cur > _ma20_now
        _rising = _ma20_now > _ma20_5d_ago
        if _above and _rising:
            return '✅ 站穩翻揚'
        elif _above:
            return '⚠️ 站穩未翻揚'
        else:
            return '❌ 跌破'
    except Exception as _e:
        return f'❓ {type(_e).__name__}'


def _check_macd_bullish(df) -> str:
    """MACD 綠轉紅（DIF-DEA 由負轉正）or 柱狀體由收斂轉發散。"""
    try:
        _close = df['Close']
        _ema12 = _close.ewm(span=12).mean()
        _ema26 = _close.ewm(span=26).mean()
        _dif   = _ema12 - _ema26
        _dea   = _dif.ewm(span=9).mean()
        _macd  = _dif - _dea
        if len(_macd.dropna()) < 3:
            return '❓ 不足 30 日'
        _now = float(_macd.iloc[-1])
        _prev = float(_macd.iloc[-2])
        _prev2 = float(_macd.iloc[-3])
        # 綠轉紅：前一日負今日正
        if _prev < 0 and _now > 0:
            return '✅ 綠轉紅'
        # 柱狀體放大（已紅且擴大）
        if _now > 0 and _now > _prev > _prev2:
            return '✅ 柱狀放大'
        if _now > 0:
            return '⚠️ 紅但收斂'
        return '❌ 仍綠'
    except Exception as _e:
        return f'❓ {type(_e).__name__}'


def _check_kd_golden_cross(df) -> str:
    """KD 低檔（K<20）黃金交叉。"""
    try:
        from tech_indicators import calc_kd
        # 確保欄位名一致（calc_kd 接受 close/high/low 小寫）
        _df_kd = df.rename(columns={'Close': 'close', 'High': 'high', 'Low': 'low'})
        _k, _d = calc_kd(_df_kd, period=9)
        if _k is None or _d is None or len(_k) < 2:
            return '❓ 不足 9 日'
        _k_now, _d_now = float(_k.iloc[-1]), float(_d.iloc[-1])
        _k_prev, _d_prev = float(_k.iloc[-2]), float(_d.iloc[-2])
        _golden = _k_prev < _d_prev and _k_now > _d_now
        if _golden and _k_now < 20:
            return f'✅ 低檔黃叉 K={_k_now:.1f}'
        if _golden:
            return f'⚠️ 黃叉 K={_k_now:.1f}'
        if _k_now > 80:
            return f'⚠️ 高檔 K={_k_now:.1f}'
        return f'❌ K={_k_now:.1f}'
    except Exception as _e:
        return f'❓ {type(_e).__name__}'


# ══════════════════════════════════════════════════════════════
# Stage 3 — Gemini AI 三型建議報告
# ══════════════════════════════════════════════════════════════

def _generate_ai_report(gemini_fn, qualified: list[dict], all_results: list[dict]) -> str:
    """生成 Markdown 戰情報告：積極型 / 保守型 / 止損紀律。"""
    _lines = ['以下為通過二階段濾網的候選個股清單，請依「積極型 / 保守型 / 止損紀律」三型給出操作建議：\n']
    for r in qualified:
        _lines.append(
            f'- **{r["ticker"]} {r.get("note","")}**：'
            f'S1=`{r["s1_pass_cnt"]}/4`（債{r["debt_ratio_label"]} · 三率{r["three_rate_label"]} '
            f'· 5Y配息{r["div_5y_label"]} · PE{r["pe_zone_label"]}）'
            f' / S2=`{r["s2_pass_cnt"]}/3`（MA20{r["ma20_label"]} · MACD{r["macd_label"]} · KD{r["kd_label"]}）'
        )
    _prompt = (
        '你是一位擁有 20 年台股經驗的「台股AI戰情室」首席策略師。'
        '依下方候選名單，輸出 Markdown 結構戰情報告：\n\n'
        + '\n'.join(_lines)
        + '\n\n請依以下結構回覆：\n\n'
        '## 🎯 三階段選股建議\n\n'
        '### 🔥 積極型投資人優先佈局\n'
        '（選 1-2 檔，說明技術面表態 + 短期催化劑）\n\n'
        '### 🛡️ 保守型存股族防禦配置\n'
        '（選 1-2 檔，說明價值安全邊際 + 殖利率支撐）\n\n'
        '### ⚠️ 限制與風險提醒\n'
        '（每檔的潛在風險：景氣循環 / 老闆畫餅 / 客戶集中等）\n\n'
        '### 📉 止損紀律建議\n'
        '（建議跌破月線出場 or 虧損 15% 出場 + 加碼條件）\n\n'
        '請務必包含上述四個章節，每項分析含具體理由。'
    )
    try:
        _r = gemini_fn(_prompt)
        return _r if _r else '⚠️ AI 回傳為空，請確認 GEMINI_API_KEY'
    except Exception as e:
        return f'❌ AI 生成失敗：{type(e).__name__}: {e}'
