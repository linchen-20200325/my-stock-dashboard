"""src/ui/etf/etf_tab_smart.py — ETF 標準差買賣帶 + 分散度分析 UI（L5）

職責（單一）：渲染兩個獨立 expander：
  1. 📐 標準差買賣參考帶
  2. 🔗 ETF 分散度分析（三維相關係數）

§8.2 架構：
  - L5 UI — 僅渲染，禁止業務邏輯
  - 資料取自 L1 fetcher（EX-PASSTHRU-1 / EX-CACHE-1 例外）
  - 計算走 L2 etf_smart_analysis
  - @st.cache_data 依 EX-CACHE-1 標準寫法
"""
from __future__ import annotations

import math
from typing import TYPE_CHECKING

import streamlit as st

if TYPE_CHECKING:  # 僅供 "pd.DataFrame" 字串型別註解解析用，不在 runtime import（L5 無 pandas 依賴）
    import pandas as pd

# L5 UI 模組 — streamlit 永遠可用，不需 no-op fallback
# @st.cache_data 供跨 session 共享 + TTL 自動失效（EX-PASSTHRU-1 / EX-CACHE-1 精神）


@st.cache_data(ttl=1800, show_spinner=False)
def _cached_price(ticker: str) -> "pd.DataFrame":
    from src.data.etf.etf_fetch import fetch_etf_price  # EX-PASSTHRU-1
    return fetch_etf_price(ticker, period='2y')


@st.cache_data(ttl=3600, show_spinner=False)
def _cached_peer_prices(tickers_tuple: tuple) -> "pd.DataFrame":
    from src.data.etf.etf_fetch import fetch_etf_peer_history  # EX-PASSTHRU-1
    return fetch_etf_peer_history(tickers_tuple, period='2y')


@st.cache_data(ttl=3600, show_spinner=False)
def _cached_holdings(ticker: str) -> list:
    try:
        from src.data.etf.etf_fetch import fetch_etf_holdings  # EX-PASSTHRU-1
        result = fetch_etf_holdings(ticker)
        return result if result else []
    except Exception as _e:
        print(f'[etf_tab_smart] holdings fetch failed {ticker}: {_e}')
        return []


@st.cache_data(ttl=7200, show_spinner=False)
def _cached_price_long(ticker: str) -> "pd.DataFrame":
    """取 5 年歷史（供 3-3-3 成立年數 / 3 年報酬計算）。"""
    from src.data.etf.etf_fetch import fetch_etf_price  # EX-PASSTHRU-1
    return fetch_etf_price(ticker, period='5y')


@st.cache_data(ttl=86400, show_spinner=False)
def _cached_zh_name(ticker: str) -> str:
    try:
        from src.data.etf import fetch_etf_zh_name  # EX-PASSTHRU-1
        return fetch_etf_zh_name(ticker) or ticker
    except Exception:
        return ticker


def _normalize(t: str) -> str:
    t = (t or '').strip()
    if t and '.' not in t:
        return f'{t}.TW'
    return t


# 三個 smart 區塊共用的「請先輸入代號」提示（單檔頁吃上方診斷代號；組合頁吃共用輸入框）
_SMART_NO_TICKER_HINT = (
    '💡 請於上方輸入 ETF 代號（單檔頁點「🔍 開始診斷」；組合頁於下方三項分析上方輸入）'
)


def render_smart_ticker_input(key_suffix: str = '', *, default: str = '0050') -> str:
    """組合頁專用：單一 ETF 代號輸入框，供下方「標準差帶 / 分散度 / 3-3-3」三項分析共用。

    取代原本三個區塊各自的獨立輸入框（收斂成一個）。單檔頁不用此函式，
    而是由呼叫端傳入上方「開始診斷」的代號（session_state['etf_s_active']）。

    回傳：正規化後代號（含 .TW），無有效輸入時回傳 ''。
    """
    _raw = st.text_input(
        'ETF 代號（下方 標準差帶 / 分散度 / 3-3-3 三項分析共用）',
        value=default,
        key=f'etf_smart_shared{key_suffix}_ticker',
        placeholder='如 0050 或 00878',
    )
    return _normalize(_raw)


# ──────────────────────────────────────────────────────────────────────────────
# Section 1：標準差買賣參考帶
# ──────────────────────────────────────────────────────────────────────────────

def render_std_band_section(ticker: str | None = None, key_suffix: str = '') -> None:
    """在目前頁面渲染 ETF 標準差買賣參考帶（expandable）。

    ticker: 由呼叫端傳入的分析標的（單檔頁＝上方「開始診斷」代號；
    組合頁＝共用輸入框代號）。不再於本區塊內開獨立輸入框。
    """
    from src.compute.etf.etf_smart_analysis import compute_std_bands

    _key = f'etf_smart_std{key_suffix}'
    with st.expander('📐 標準差買賣參考帶', expanded=True):
        st.caption(
            '根據過去 252 個交易日（約一年）的滾動均值與標準差，判斷目前價格處於哪個區間。'
            '越靠近 -2σ = 歷史相對低點，可能買進時機；越靠近 +2σ = 相對高點，注意風險。'
        )

        _ticker = _normalize(ticker) if ticker else ''
        if not _ticker:
            st.info(_SMART_NO_TICKER_HINT)
            return
        st.caption(f'📌 分析標的：**{_ticker}**')

        _win = st.selectbox(
            '觀察窗口（交易日）',
            options=[120, 252, 500],
            index=1,
            format_func=lambda x: {120: '半年 (120)', 252: '一年 (252)', 500: '兩年 (500)'}[x],
            key=f'{_key}_window',
        )

        # 自動計算(不需按鈕):代號由上方帶入即算,融入診斷結果
        with st.spinner(f'載入 {_ticker} 價格中...'):
            try:
                _df = _cached_price(_ticker)
            except Exception as _e:
                st.error(f'價格資料載入失敗：{_e}')
                return

        if _df is None or _df.empty:
            st.error(f'❌ 找不到 {_ticker} 的價格資料，請確認代號')
            return

        _close = _df['Close'] if 'Close' in _df.columns else _df.iloc[:, 0]
        _res   = compute_std_bands(_close, window=int(_win))

        if not _res.get('has_data'):
            st.warning(f'⚠️ {_ticker} 歷史資料不足（少於 20 筆），無法計算標準差帶')
            return

        # ── 信號卡 ──
        _zh = _cached_zh_name(_ticker)
        _lbl = _res['signal_label']
        _icon = _res['signal_icon']
        _z = _res['sigma_z']
        _color = _res['signal_color']
        st.markdown(
            f'<div style="background:{_color}22;border-left:4px solid {_color};'
            f'padding:10px 16px;border-radius:6px;margin-bottom:12px;">'
            f'<b>{_icon} {_lbl}</b> &nbsp;|&nbsp; {_zh} ({_ticker})'
            f'&nbsp; z = {_z:+.2f}σ &nbsp;|&nbsp; 距均線 {_res["pct_from_mu"]:+.1f}%'
            '</div>',
            unsafe_allow_html=True,
        )

        # ── 數值表 ──
        _cur = _res['current']
        _mu  = _res['mu']
        _sig = _res['sigma']
        _tbl_data = {
            '區間': ['強買 (-2σ)', '買進 (-1σ)', '均線 (μ)', '注意 (+1σ)', '減碼 (+2σ)', '⬛ 現價'],
            '價格': [
                f'{_res["lower_2s"]:.2f}',
                f'{_res["lower_1s"]:.2f}',
                f'{_mu:.2f}',
                f'{_res["upper_1s"]:.2f}',
                f'{_res["upper_2s"]:.2f}',
                f'{_cur:.2f}',
            ],
            '距現價': [
                f'{(_res["lower_2s"] - _cur) / _cur * 100:+.1f}%',
                f'{(_res["lower_1s"] - _cur) / _cur * 100:+.1f}%',
                f'{(_mu - _cur) / _cur * 100:+.1f}%',
                f'{(_res["upper_1s"] - _cur) / _cur * 100:+.1f}%',
                f'{(_res["upper_2s"] - _cur) / _cur * 100:+.1f}%',
                '—',
            ],
        }
        import pandas as _pd
        st.dataframe(_pd.DataFrame(_tbl_data), use_container_width=True, hide_index=True)

        # ── 走勢圖（近 2 年） ──
        try:
            import plotly.graph_objects as go
            _close_trim = _close.dropna().iloc[-_win * 2:]  # 只顯示近 2 個觀察窗口
            _mu_s  = _res['series_mu'].iloc[-_win * 2:]
            _u2    = _res['series_u2'].iloc[-_win * 2:]
            _u1    = _res['series_u1'].iloc[-_win * 2:]
            _l1    = _res['series_l1'].iloc[-_win * 2:]
            _l2    = _res['series_l2'].iloc[-_win * 2:]
            _idx   = _close_trim.index

            fig = go.Figure()
            # 帶狀底色
            fig.add_trace(go.Scatter(
                x=list(_idx) + list(_idx[::-1]),
                y=list(_u2.values) + list(_l2.values[::-1]),
                fill='toself', fillcolor='rgba(231,76,60,0.07)',
                line=dict(width=0), name='±2σ 區', showlegend=True,
            ))
            fig.add_trace(go.Scatter(
                x=list(_idx) + list(_idx[::-1]),
                y=list(_u1.values) + list(_l1.values[::-1]),
                fill='toself', fillcolor='rgba(26,188,156,0.10)',
                line=dict(width=0), name='±1σ 區', showlegend=True,
            ))
            # 均線
            fig.add_trace(go.Scatter(
                x=_idx, y=_mu_s.values, name='均線 μ',
                line=dict(color='#3498db', dash='dot', width=1.5),
            ))
            # 上下邊界線
            for _s, _c, _n in [(_u2, '#e74c3c', '+2σ'), (_u1, '#e67e22', '+1σ'),
                                 (_l1, '#1abc9c', '-1σ'), (_l2, '#16a085', '-2σ')]:
                fig.add_trace(go.Scatter(
                    x=_idx, y=_s.values, name=_n,
                    line=dict(color=_c, width=0.8, dash='dash'), showlegend=True,
                ))
            # 收盤價
            fig.add_trace(go.Scatter(
                x=_idx, y=_close_trim.values, name='收盤價',
                line=dict(color='#ecf0f1', width=2),
            ))
            fig.update_layout(
                template='plotly_dark',
                height=360,
                margin=dict(l=10, r=10, t=30, b=20),
                title=f'{_zh} ({_ticker}) — 標準差帶',
                legend=dict(orientation='h', y=1.05),
            )
            st.plotly_chart(fig, use_container_width=True)
        except ImportError:
            st.caption('⚠️ plotly 未安裝，跳過圖表')
        except Exception as _fe:
            st.caption(f'圖表渲染失敗：{_fe}')


# ──────────────────────────────────────────────────────────────────────────────
# Section 2：ETF 分散度分析
# ──────────────────────────────────────────────────────────────────────────────

def render_correlation_finder(ticker: str | None = None, key_suffix: str = '') -> None:
    """在目前頁面渲染 ETF 三維分散度分析（expandable）。

    ticker: 由呼叫端傳入的分析標的（同 render_std_band_section）。
    """
    from src.compute.etf.etf_categories import ETF_PEER_GROUPS
    from src.compute.etf.etf_smart_analysis import build_holdings_set, find_best_diversifiers

    with st.expander('🔗 ETF 分散度分析 — 找最佳互補標的', expanded=True):
        st.caption(
            '以目前標的為基準，系統從台灣主要 ETF 中找出三維度（價格相關、持股重疊、產業類別）'
            '綜合最不相關的前 10 檔，作為投資組合分散的候選標的。'
        )

        _ticker = _normalize(ticker) if ticker else ''
        if not _ticker:
            st.info(_SMART_NO_TICKER_HINT)
            return
        st.caption(f'📌 分析標的：**{_ticker}**')

        # 自動計算(不需按鈕);此區塊會抓 ~30 檔 ETF,首次約 10-20 秒,之後走 cache
        # ── 建立 universe（ETF_PEER_GROUPS 所有 + 輸入本身）──
        _universe: set[str] = {_ticker}
        for _lst in ETF_PEER_GROUPS.values():
            _universe.update(_lst)
        _universe_tuple = tuple(sorted(_universe))

        with st.spinner(f'載入 {len(_universe_tuple)} 檔 ETF 歷史資料…（約 10-20 秒）'):
            try:
                _price_pivot = _cached_peer_prices(_universe_tuple)
            except Exception as _e:
                st.error(f'批次價格資料載入失敗：{_e}')
                return

        if _price_pivot is None or _price_pivot.empty:
            st.error('❌ 無法取得 ETF 價格資料，請稍後再試')
            return

        if _ticker not in _price_pivot.columns:
            st.error(f'❌ {_ticker} 無歷史資料，請確認代號（台灣 ETF 需加 .TW）')
            return

        # ── 取得持股（非同步，容錯）──
        _peers_in_pivot = [c for c in _price_pivot.columns if c != _ticker]
        _tickers_to_fetch = [_ticker] + _peers_in_pivot[:30]  # 最多30檔避免太慢
        _holdings_map: dict[str, set] = {}

        _prog = st.progress(0, '取得持股資料中...')
        for _i, _t in enumerate(_tickers_to_fetch):
            _prog.progress((_i + 1) / len(_tickers_to_fetch), f'取得 {_t} 持股...')
            _raw_h = _cached_holdings(_t)
            _holdings_map[_t] = build_holdings_set(_raw_h, top_n=15)
        _prog.empty()

        # ── 計算分散度 ──
        with st.spinner('計算三維分散度...'):
            _result_df = find_best_diversifiers(
                ticker=_ticker,
                price_pivot=_price_pivot,
                holdings_map=_holdings_map,
                top_n=10,
            )

        if _result_df is None or _result_df.empty:
            st.warning('⚠️ 資料不足，無法計算分散度（需至少 20 個共同交易日）')
            return

        # ── 查 ETF 中文名稱 ──
        import pandas as _pd
        _zh_names = []
        for _t in _result_df['ticker']:
            _zh_names.append(_cached_zh_name(_t))
        _result_df.insert(1, '名稱', _zh_names)

        # 格式化顯示
        _display = _result_df.copy()
        _display['分散指數'] = _display['分散指數'].apply(lambda x: f'{x:.3f}')
        _display['價格相關'] = _display['價格相關'].apply(lambda x: f'{x:+.3f}')
        _display['持股重疊%'] = _display['持股重疊%'].apply(
            lambda x: f'{x:.1f}%' if x is not None and not (isinstance(x, float) and math.isnan(x)) else '—'
        )
        _display['類別差異'] = _display['類別差異'].apply(lambda x: f'{x:.3f}')
        _display = _display.drop(columns=['可用維度'])

        _input_zh = _cached_zh_name(_ticker)
        st.markdown(f'#### 🏆 與 {_input_zh} ({_ticker}) 最不相關的 10 檔 ETF')
        st.caption(
            '分散指數越高（接近 1）= 與您輸入的 ETF 越不相關，加入組合後分散效果越好。'
            '| 價格相關：越接近 -1 越好 | 持股重疊%：越低越好 | 類別差異：越接近 1 越好'
        )
        st.dataframe(_display, use_container_width=True, hide_index=True)

        # ── 橫向 bar chart ──
        try:
            import plotly.graph_objects as go
            _vals = [float(_result_df['分散指數'].iloc[i]) for i in range(len(_result_df))]
            _labels = [
                f"{_result_df['ticker'].iloc[i]}<br>{_result_df['名稱'].iloc[i]}"
                for i in range(len(_result_df))
            ]
            _colors = [
                '#16a085' if v >= 0.7 else '#1abc9c' if v >= 0.5 else '#3498db'
                for v in _vals
            ]
            fig2 = go.Figure(go.Bar(
                y=list(reversed(_labels)),
                x=list(reversed(_vals)),
                orientation='h',
                marker_color=list(reversed(_colors)),
                text=[f'{v:.3f}' for v in reversed(_vals)],
                textposition='outside',
            ))
            fig2.update_layout(
                template='plotly_dark',
                height=380,
                margin=dict(l=10, r=60, t=30, b=20),
                xaxis_title='分散指數（越高越好）',
                title=f'vs {_ticker} — 最佳分散標的前 10',
                xaxis=dict(range=[0, 1.05]),
            )
            st.plotly_chart(fig2, use_container_width=True)
        except ImportError:
            pass
        except Exception as _fe2:
            st.caption(f'圖表渲染失敗：{_fe2}')


# ──────────────────────────────────────────────────────────────────────────────
# Section 3：MK 3-3-3 原則評估
# ──────────────────────────────────────────────────────────────────────────────

def _render_333_result(ticker: str, r: dict) -> None:
    """渲染 3-3-3 評估結果卡片（僅純 HTML + st.markdown）。"""
    def _icon(flag) -> str:
        if flag is True:  return '✅'
        if flag is False: return '❌'
        return '❓'

    def _pct_str(v) -> str:
        return f'{v * 100:.1f}%' if v is not None else 'N/A'

    overall = r.get('overall_pass')
    if overall is True:
        bcolor  = '#16a085'
        header  = '🏆 三項全過！符合 MK 3-3-3 優質標的標準'
    elif overall is False:
        bcolor  = '#c0392b'
        header  = '⚠️ 未達 3-3-3 標準 — 至少一項條件未通過'
    else:
        bcolor  = '#586069'
        header  = '📊 評估完成（部分條件因資料不足無法判定）'

    age   = r.get('c1_age_years')
    ret3y = r.get('c2_return_3y')
    rank  = r.get('c3_peer_rank_pct')

    age_str  = f'{age:.1f} 年' if age is not None else 'N/A'
    ret_str  = _pct_str(ret3y)
    rank_str = f'前 {rank * 100:.0f}%' if rank is not None else 'N/A（未啟用同儕排名）'

    st.markdown(
        f'<div style="border-left:4px solid {bcolor};padding:14px 18px;'
        f'border-radius:6px;margin:10px 0;background:rgba(0,0,0,0.12);">'
        f'<div style="font-size:1.08em;font-weight:bold;margin-bottom:10px;">{header}</div>'
        '<table style="width:100%;border-collapse:collapse;font-size:0.97em;">'
        f'<tr><td style="padding:5px 0;color:#8b949e;width:55%">① 成立時間 &gt; 3 年</td>'
        f'<td>{_icon(r.get("c1_pass"))} &nbsp;<b>{age_str}</b></td></tr>'
        f'<tr><td style="padding:5px 0;color:#8b949e;">② 3 年年化報酬率 &gt; 7%</td>'
        f'<td>{_icon(r.get("c2_pass"))} &nbsp;<b>{ret_str}</b></td></tr>'
        f'<tr><td style="padding:5px 0;color:#8b949e;">③ 同儕排名前 1/3</td>'
        f'<td>{_icon(r.get("c3_pass"))} &nbsp;<b>{rank_str}</b></td></tr>'
        '</table></div>',
        unsafe_allow_html=True,
    )

    # 輔助說明
    if ret3y is not None and r.get('c2_pass') is False:
        gap = 0.07 - ret3y
        st.caption(f'❗ 距離 7% 年化目標還差 {gap * 100:.1f} 個百分點')
    if age is not None and r.get('c1_pass') is False:
        remain = 3.0 - age
        st.caption(f'⏳ 距離 3 年門檻還需 {remain:.1f} 年（{int(remain * 12)} 個月）')


def render_333_section(ticker: str | None = None, key_suffix: str = '') -> None:
    """在目前頁面渲染 MK 3-3-3 原則評估（expandable）。

    ticker: 由呼叫端傳入的分析標的（同 render_std_band_section）。

    C1: 成立 > 3 年
    C2: 過去 3 年年化報酬 > 7%
    C3: 同儕排名前 1/3（勾選才執行，較耗時）
    """
    from src.compute.etf.etf_smart_analysis import check_333_criteria

    _key = f'etf_smart_333{key_suffix}'
    with st.expander('🎯 MK 3-3-3 優質標的篩選', expanded=True):
        st.caption(
            '郭俊宏（MK）老師核心篩選原則：'
            '**① 成立 >3 年**（歷經牛熊考驗）｜'
            '**② 3 年年化報酬 >7%**（真正的定存替代品）｜'
            '**③ 同儕前 1/3**（績效中前段，有上升潛力）'
        )

        _ticker = _normalize(ticker) if ticker else ''
        if not _ticker:
            st.info(_SMART_NO_TICKER_HINT)
            return
        st.caption(f'📌 分析標的：**{_ticker}**')

        _run_peer = st.checkbox(
            '啟用同儕排名（較慢）',
            value=False,
            key=f'{_key}_peer',
            help='啟用後會下載同類 ETF 的歷史報酬進行排名比較，約需 15-30 秒',
        )

        # 自動計算(不需按鈕):C1/C2 即算;C3 同儕排名較慢,預設關,勾選才跑
        # 取歷史（5 年）
        with st.spinner(f'載入 {_ticker} 5 年歷史資料中…'):
            try:
                _price_df = _cached_price_long(_ticker)
            except Exception as _e:
                st.error(f'價格資料載入失敗：{_e}')
                return

        if _price_df is None or _price_df.empty:
            st.error(f'❌ 找不到 {_ticker} 的歷史資料，請確認代號')
            return

        # 同儕資料（可選）
        _peer_prices = None
        if _run_peer:
            from src.compute.etf.etf_categories import ETF_PEER_GROUPS
            _universe: set[str] = {_ticker}
            for _lst in ETF_PEER_GROUPS.values():
                _universe.update(_lst)
            _universe_tuple = tuple(sorted(_universe))
            with st.spinner(f'下載 {len(_universe_tuple)} 檔同儕歷史（需 15-30 秒）…'):
                try:
                    _peer_prices = _cached_peer_prices(_universe_tuple)
                except Exception as _e2:
                    st.warning(f'同儕資料載入失敗（{_e2}），跳過 C3 排名')

        # 計算
        with st.spinner('計算 3-3-3 指標中…'):
            _result = check_333_criteria(_ticker, _price_df, _peer_prices)

        _zh = _cached_zh_name(_ticker)
        st.markdown(f'**{_zh}（{_ticker}）**')
        _render_333_result(_ticker, _result)

        # 說明
        with st.expander('📖 3-3-3 原則說明', expanded=False):
            st.markdown(
                '**① 成立 > 3 年** — 足以歷經一個完整牛熊循環，才有足夠資本利得作為配息後盾，'
                '並能在歷史中驗證其抗跌能力。\n\n'
                '**② 3 年年化報酬 > 7%** — MK 的目標是找到 7% 以上的定存替代品。'
                '長期穩定 7%+ 代表能透過資本利得+股息完全覆蓋配息，實現「穩健領息不吃本金」。\n\n'
                '**③ 同儕排名前 1/3** — 晨星 3 顆星以上，即同類前 40 名。'
                '中前段班比頂尖更有持續上升空間，費率、風控和績效已達標，不是資優生但有韌性。'
            )
