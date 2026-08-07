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
# B4-b:產業熱力圖區間口徑 / 缺值呈現 / 台股代表股揭露 SSOT(L4 → L0)。
from shared.sector_heatmap import (
    HEATMAP_MISSING_TEXT, SECTOR_LOOKBACK_TRADING_DAYS, SECTOR_PERIOD_LABELS,
    SECTOR_YF_DOWNLOAD_WINDOW, TW_SINGLE_STOCK_PROXY_DISCLOSURE,
    color_span_pct, direction_label, hover_value_text, node_area,
    sector_display_name, sort_key_desc,
)


# ── 總經連動配置建議表 ────────────────────────────────────────
# ⚠️ v19.170 DEPRECATED(P0-1):這張靜態表與主決策脫鉤(bull 一律股票 70%),是稽核
# 「同畫面 6 套矛盾持股建議」的其中一套。配置數字一律改由
# `allocation_service.get_allocation_sleeves()`(依最終建議持股中值推導)提供;
# 本表僅保留給尚未遷移的 caller(etf_tab_ai._generate_report 的 prompt 文案)作 fallback,
# **新程式碼請勿再引用**。
MACRO_ALLOC = {
    'bull':    {'股票型ETF': 70, '債券型ETF': 15, '貨幣/現金': 15},
    'neutral': {'股票型ETF': 50, '債券型ETF': 30, '貨幣/現金': 20},
    'bear':    {'股票型ETF': 20, '債券型ETF': 50, '貨幣/現金': 30},
}
# ⚠️ v19.171 DEPRECATED（🟡-2）:`macro_allocation_banner` 已改用
# `_alloc_banner_desc()`（依最終持股中值生成），**本表在本 repo 內已無任何實質
# caller** —— 唯一剩下的引用是 `src/ui/etf/etf_dashboard.py:40` 的
# `# noqa: F401` re-export shim（向後相容用，不讀值）。與 `MACRO_ALLOC` 同理保留，
# 待確認無外部 caller 後可一併刪除。**新程式碼請勿引用。**
MACRO_DESC = {
    'bull':    '🟢 多頭市場：加大股票型ETF比重，可佈局成長型/科技型ETF',
    'neutral': '🟡 中性市場：股債平衡，降低單一類型集中度',
    'bear':    '🔴 空頭市場：大幅降低股票曝險，增加投資級債券ETF + 現金',
}

# ── 配置文案分段（v19.171 🟡-2：文案 / 顏色 / 數字三者同源）─────────────
# (最終持股中值上界, 燈號, 文案, 底色, 框色)
# 為什麼要分段而不是查 regime：實機 2026-08-05 ETF 分頁同一張卡上出現
#   「建議持股 20%　🔒 上限 20%（三環第一環）」＋「🟢 多頭市場：加大股票型ETF比重」
# —— 數字已吃 SSOT，文案卻還在查 `MACRO_DESC[regime]`，於是總經多頭時
# 永遠喊「加大比重」，跟被硬否決壓到 20% 的數字當場打臉。
# 分段門檻對齊 §3.2 語意帶（防禦 ≤20 = DEFENSE_HI_PCT / 保守 ≤50 / 平衡 ≤80 / 積極 >80）。
_ALLOC_DESC_BANDS: tuple[tuple[int, str, str, str, str], ...] = (
    (20,  '🔴', '防禦配置：優先保本 —— 股票型ETF 壓到最低，其餘停泊投資級債與現金',
     '#2a0d0d', TRAFFIC_RED),
    (50,  '🟡', '保守配置：控制股票曝險 —— 只留核心市值型ETF，主題／槓桿型暫不加碼',
     '#1e1a00', TRAFFIC_YELLOW),
    (80,  '🔵', '平衡配置：股債並重 —— 核心市值型ETF 為主，衛星部位小額試單',
     '#0a1628', '#1f6feb'),
    (100, '🟢', '積極配置：可加大股票型ETF 比重，並佈局成長型／科技型ETF',
     '#0d2618', '#2ea043'),
)


def _alloc_banner_desc(alloc) -> tuple[str, str, str]:
    """由 `AllocationDecision` 生成配置文案 + 視覺色（與畫面數字同源）。

    v19.171 🟡-2 取代 `MACRO_DESC.get(regime, ...)`。

    規則:
      1. **方向由最終持股中值 `final_mid` 決定**（與 `get_allocation_sleeves()`
         吃同一個輸入）→ 文案與三桶數字不可能再打架。
      2. 帶上姿態 `posture`（油門在講「該多積極」）。
      3. `capped=True` 時明講「總經 X 但被 <天花板> 壓制」，使用者才看得懂
         「為何總經多頭卻只給 20%」。
      4. `regime` 只作**輔助語氣**（括號內的總經背景），不得單獨決定方向。

    C1 v19.182：`alloc.regime`（→ `alloc.regime_text`）現在來自
    `shared.regime_arbiter` 的**生效結論**，不再是 raw `mkt_info['regime']`。
    以前的破口：總經紅綠燈判 🔴 空頭防禦、持股被壓到 20% 的那天，本函式
    仍會在括號裡寫「總經多頭」——因為它讀到的是趨勢面輸入。現在
    「數字（final_mid）」與「總經背景（regime_text）」出自同一次仲裁。

    Args:
        alloc: `allocation_service.get_allocation()` 的回傳（`is_loaded=True`）。

    Returns:
        (desc, bg, brd)
    """
    _mid = alloc.final_mid
    if _mid is None:   # is_loaded=True 理論上必有值；防禦性降級為 SSOT 一句話結論
        return alloc.headline(), '#1a1f2e', '#1f6feb'
    _icon, _text, _bg, _brd = _ALLOC_DESC_BANDS[-1][1:]
    for _hi, _i, _t, _b, _r in _ALLOC_DESC_BANDS:
        if _mid <= _hi:
            _icon, _text, _bg, _brd = _i, _t, _b, _r
            break
    _tail = f'總經{alloc.regime_text}、姿態「{alloc.posture}」'
    if alloc.capped:
        _tail += f'，但被「{alloc.cap_name}」壓制 → 先控制股票曝險'
    return f'{_icon} {_text}｜{_tail}', _bg, _brd


def macro_allocation_banner(regime: str) -> None:
    """總經連動配置橫幅(v19.170 P0-1:改吃建議持股 SSOT)。

    Args:
        regime: **僅為舊介面相容而保留,函式內已完全不使用**(v19.171 🟡-2)。
            數字來自 `get_allocation_sleeves()`;文案 / 顏色來自
            `_alloc_banner_desc()`(吃 `get_allocation().final_mid`)。
            保留參數是為了不打破現有 caller 簽章,移除屬另案。

    Note:
        §1 Fail Loud:總經未評估 → 誠實顯示「未評估」並指路,
        **不**退回 `MACRO_ALLOC['neutral']` 假裝有一份配置建議。
    """
    del regime  # 明示「刻意不使用」,避免日後誤以為它還在影響畫面(v19.171)
    # v19.170:股/債/現金三桶由最終建議持股中值推導,與 🎚️ 建議持股油門 永不矛盾。
    from src.services.allocation_service import get_allocation, get_allocation_sleeves
    _alloc = get_allocation()
    alloc = get_allocation_sleeves()
    _sub = '📡 總經連動配置（同步自 🎚️ 建議持股油門）'
    if alloc is None:
        st.markdown(
            f'''<div style="background:#1a1f2e;border:1px solid #484f58;border-radius:10px;
padding:10px 16px;margin-bottom:14px;">
<div style="font-size:12px;font-weight:700;color:#8b949e;margin-bottom:2px;">{_sub}</div>
<div style="font-size:13px;color:#c9d1d9;">
⬜ 總經未評估，請先到「🌍 市場環境」按一鍵更新</div>
</div>''', unsafe_allow_html=True)
        return
    _cap_suffix = f'　{_alloc.cap_text}' if _alloc.capped else ''
    # v19.171 🟡-2:文案 + 底色 + 框色全部改由**最終持股中值**推導,與上方
    # 「建議持股 X%」及下方三桶數字同源。`regime` 參數(以及 _alloc.regime)
    # 只在 `_alloc_banner_desc` 內作輔助語氣,不再單獨決定文案方向 / 顏色。
    desc, bg, brd = _alloc_banner_desc(_alloc)
    alloc_html = ' &nbsp;|&nbsp; '.join(
        f'<b>{k}</b>&nbsp;<span style="color:#58a6ff;">{v}%</span>'
        for k, v in alloc.items()
    )
    st.markdown(
        f'''<div style="background:{bg};border:1px solid {brd};border-radius:10px;
padding:10px 16px;margin-bottom:14px;">
<div style="font-size:12px;font-weight:700;color:#8b949e;margin-bottom:2px;">
{_sub}　建議持股 {_alloc.range_text}{_cap_suffix}</div>
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


def _strategy_conclusion(strategy: str, indicator_val: str, conclusion: str,
                         action: str = '', color: str | None = None) -> None:
    """ETF dashboard 策略結論卡 — sink shim,委派 ui_widgets.strategy_conclusion SSOT。

    v18.427 Phase 2 Batch 4(D10):原私有副本含 _neg_kw/_pos_kw + HTML 字串建構,
    與 ui_widgets 版本 1:1 重複(差別僅 4 個 ETF 脈絡關鍵字 +
    sink:st.markdown vs string return)。
    SSOT 收斂:ui_widgets 補上 4 個關鍵字後本檔改 thin shim,簽名不變 24 個 caller 無感。

    v19.174 去識別化:舊名 `_teacher_conclusion`,第一參數舊為人名字串;
    現改為策略代號(`STRATEGY_VALUATION` / `STRATEGY_FINANCIAL` / `STRATEGY_TECHNICAL`)。
    """
    from src.ui.render.ui_widgets import strategy_conclusion as _ui_sc
    st.markdown(_ui_sc(strategy, indicator_val, conclusion, action, color),
                unsafe_allow_html=True)


# v19.174 過渡期 alias（caller 全部遷移完成後移除）
_teacher_conclusion = _strategy_conclusion


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


def _plot_portfolio_vs_benchmark(result: dict, benchmark_label: str = '0050') -> bool:
    """組合(加權)＋ 個別持股 vs 基準(0050)累積報酬疊圖(Y:累積報酬%)。

    result: etf_calc.compute_portfolio_vs_benchmark() 的回傳 dict(曲線皆小數,此處 ×100 顯示 %)。
    組合粗實線 + 0050 粗虛線(綠,視覺區隔)+ 個別持股細線(半透明墊底)。
    §1:benchmark_ok=False / 空曲線 → 不畫、回傳 False,交 caller 顯示 fail-loud 訊息(不畫假曲線)。
    """
    port  = result.get('portfolio_cum')
    bench = result.get('benchmark_cum')
    if not result.get('benchmark_ok') or port is None or getattr(port, 'empty', True) \
            or bench is None or getattr(bench, 'empty', True):
        return False
    fig = go.Figure()
    _hover = '%{x|%Y-%m-%d}  %{y:.2f}%<extra>%{fullData.name}</extra>'
    # 個別持股(細線,先畫墊底)
    for t, s in (result.get('per_asset_cum') or {}).items():
        if s is None or s.empty:
            continue
        fig.add_trace(go.Scatter(
            x=s.index, y=(s * 100).round(2), name=str(t), mode='lines',
            line=dict(width=1), opacity=0.55, hovertemplate=_hover))
    # 基準 0050(粗虛線,綠)
    fig.add_trace(go.Scatter(
        x=bench.index, y=(bench * 100).round(2), name=f'{benchmark_label}（基準）',
        mode='lines', line=dict(color=TRAFFIC_GREEN, width=3, dash='dash'),
        hovertemplate=_hover))
    # 組合(粗實線,亮藍)
    fig.add_trace(go.Scatter(
        x=port.index, y=(port * 100).round(2), name='組合（加權）',
        mode='lines', line=dict(color='#58a6ff', width=3),
        hovertemplate=_hover))
    fig.update_layout(
        template='plotly_dark', height=420,
        margin=dict(l=0, r=0, t=20, b=0),
        paper_bgcolor='#0d1117', plot_bgcolor='#0d1117',
        legend=dict(orientation='h', yanchor='bottom', y=1.01),
        yaxis=dict(title='累積報酬 (%)', ticksuffix='%', zeroline=True,
                   zerolinecolor='#444', zerolinewidth=1),
        hovermode='x unified',
    )
    st.plotly_chart(fig, width='stretch')
    return True


def _plot_efficient_frontier(result: dict) -> bool:
    """效率前緣（風險-報酬地圖）散點圖 —— **描述性**視覺化(§7),非規範性最佳化。

    result: etf_calc.compute_efficient_frontier() 回傳 dict(vol/ret 皆年化小數,此處 ×100 → %)。
    圖層(由底到頂):蒙地卡羅隨機配置雲(依 Sharpe 上色)→ 前緣參考線 → 每檔持股點 →
    min-var / max-Sharpe 歷史估計參考點(非建議)→ 使用者「目前組合」星號(最顯眼)。
    軸:X=年化波動度(%),Y=年化報酬(%)。主題 plotly_dark,與其他圖一致。
    §1:ok=False / 空雲 → 不畫、回 False,交 caller 顯示 fail-loud 訊息(不畫假圖)。
    """
    if not result or not result.get('ok'):
        return False
    cloud = result.get('cloud') or {}
    vols = cloud.get('vol') or []
    rets = cloud.get('ret') or []
    if not vols or not rets:
        return False

    def _pct(xs):
        return [x * 100 for x in xs]

    fig = go.Figure()
    # 1) 蒙地卡羅隨機配置雲(依 Sharpe 上色;None→nan 不著色,實務幾乎不觸發 vol=0)
    _sh = [(s if s is not None else float('nan')) for s in (cloud.get('sharpe') or [])]
    fig.add_trace(go.Scattergl(
        x=_pct(vols), y=_pct(rets), mode='markers', showlegend=False,
        name='隨機配置雲',
        marker=dict(size=4, opacity=0.45, color=_sh, colorscale='Viridis',
                    showscale=True, colorbar=dict(title='Sharpe', thickness=10)),
        hovertemplate='波動 %{x:.2f}%　報酬 %{y:.2f}%<extra></extra>'))
    # 2) 前緣參考線(歷史估計上緣,非建議)
    fr = result.get('frontier') or {}
    if fr.get('vol') and fr.get('ret'):
        fig.add_trace(go.Scatter(
            x=_pct(fr['vol']), y=_pct(fr['ret']), mode='lines',
            name='效率前緣（歷史估計參考線）',
            line=dict(color='#f0f6fc', width=2, dash='dash'),
            hovertemplate='波動 %{x:.2f}%　報酬 %{y:.2f}%<extra>前緣參考</extra>'))
    # 3) 每檔持股點(diamond + 代號標籤)
    pap = result.get('per_asset_points') or {}
    if pap:
        _tk = list(pap.keys())
        fig.add_trace(go.Scatter(
            x=[pap[t]['vol'] * 100 for t in _tk], y=[pap[t]['ret'] * 100 for t in _tk],
            mode='markers+text', name='個別持股', text=_tk, textposition='top center',
            textfont=dict(size=10, color='#c9d1d9'),
            marker=dict(symbol='diamond', size=10, color='#ffa657',
                        line=dict(color='#0d1117', width=1)),
            hovertemplate='%{text}<br>波動 %{x:.2f}%　報酬 %{y:.2f}%<extra></extra>'))
    # 4) min-var / max-Sharpe 歷史估計參考點(非建議)
    mv = result.get('min_var_point')
    if mv:
        fig.add_trace(go.Scatter(
            x=[mv['vol'] * 100], y=[mv['ret'] * 100], mode='markers',
            name='最小變異（歷史估計參考點,非建議）',
            marker=dict(symbol='triangle-up', size=13, color=TRAFFIC_GREEN,
                        line=dict(color='#0d1117', width=1)),
            hovertemplate='最小變異參考點<br>波動 %{x:.2f}%　報酬 %{y:.2f}%<extra></extra>'))
    ms = result.get('max_sharpe_point')
    if ms:
        fig.add_trace(go.Scatter(
            x=[ms['vol'] * 100], y=[ms['ret'] * 100], mode='markers',
            name='最大夏普（歷史估計參考點,非建議）',
            marker=dict(symbol='star-diamond', size=14, color=TRAFFIC_YELLOW,
                        line=dict(color='#0d1117', width=1)),
            hovertemplate='最大夏普參考點<br>波動 %{x:.2f}%　報酬 %{y:.2f}%<extra></extra>'))
    # 5) 使用者「目前組合」星號(最顯眼,最後畫置頂)
    cp = result.get('current_point')
    if cp:
        fig.add_trace(go.Scatter(
            x=[cp['vol'] * 100], y=[cp['ret'] * 100], mode='markers+text',
            name='你的組合（目前）', text=['你的組合'], textposition='bottom center',
            textfont=dict(size=12, color='#ff7b72'),
            marker=dict(symbol='star', size=20, color='#ff7b72',
                        line=dict(color='#0d1117', width=1)),
            hovertemplate='你的組合（目前）<br>波動 %{x:.2f}%　報酬 %{y:.2f}%<extra></extra>'))
    fig.update_layout(
        template='plotly_dark', height=460,
        margin=dict(l=0, r=0, t=20, b=0),
        paper_bgcolor='#0d1117', plot_bgcolor='#0d1117',
        legend=dict(orientation='h', yanchor='bottom', y=1.01, font=dict(size=10)),
        xaxis=dict(title='年化波動度 (%)', ticksuffix='%'),
        yaxis=dict(title='年化報酬 (%)', ticksuffix='%', zeroline=True,
                   zerolinecolor='#444', zerolinewidth=1),
    )
    st.plotly_chart(fig, width='stretch')
    return True


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

# ── 台股「類股」代表股 ────────────────────────────────────────
# ⚠️ B4-b H-2 揭露:以下 key **全部是個股**,不是類股指數、也不是成分股平均。
# 台股側沒有可用的類股指數日線資料源(查證結果見下),因此走「單一代表權值股近似」,
# 並在 UI 標籤 / caption / AI prompt 三處**明確揭露**(§1 寧可誠實標示,
# 不可讓使用者以為那是類股平均)。渲染時一律經
# `shared.sector_heatmap.sector_display_name(..., single_stock_proxy=True)`
# 產生「半導體（代表股 2330）」這種標籤。
#
# 【資料源查證】為什麼不改用真類股指數:
# - yfinance:無 TWSE 類股指數 ticker(僅 ^TWII 大盤 / ^TWOII 櫃買),拿不到日線序列。
# - TWSE `MI_INDEX`:確實含 29 檔類股指數,但**一次只回一個交易日**;要湊 63 根
#   bar 需 63 次 request,且本專案已在 `daily_data_fetchers.py:324` 標記
#   「🚫 TWSE MI_INDEX 已永久停用」(穩定性不足)。
# - FinMind:無類股指數 dataset(`TaiwanStockInfo.industry_category` 只有分類欄位,
#   要自行對數百檔成分股加權 → 屬新 L1 模組 + 新資料流,依 §8.1 需先送架構審。
# - 台股類股 ETF:僅科技(0052)/ 金融(0055)/ 電子(0053)等 3~4 個產業有,
#   塑化 / 鋼鐵 / 食品 / 航運 / 觀光 / 光電**沒有**對應 ETF,無法覆蓋整張圖。
# → 結論:走揭露路線。升級觸發條件:若日後接上可用的類股指數日線源,
#   把本表換成指數代號並將 `_TW_SECTOR_SINGLE_STOCK_PROXY` 改 False 即可。
#
# 【B4-b 一併修掉的重複計數 / 錯分類 / 已下市】
# - `3008.TW`(大立光)原同時是「光電」母層 + 「電子製造」子成分 → 自電子製造移除。
# - `2409.TW`(友達,面板廠)原同時掛「電信」與「光電」→ 自電信移除(本就非電信股)。
# - `2475.TW`(華映)2019 已下市,永遠抓不到 → 移除(不猜替代標的)。
# - `9910.TW`(豐泰)是製鞋廠卻掛在「觀光」→ 母層改 `2707.TW`(晶華酒店)。
_TW_SECTORS = {
    '2330.TW': {'name': '半導體',    'sub': ['2303.TW','2308.TW','2454.TW','3711.TW','2379.TW']},
    '2317.TW': {'name': '電子製造',  'sub': ['2354.TW','2356.TW','2382.TW','3034.TW']},
    '2412.TW': {'name': '電信',      'sub': ['3045.TW','4904.TW']},
    '2882.TW': {'name': '金融',      'sub': ['2881.TW','2883.TW','2884.TW','2886.TW','2891.TW']},
    '1301.TW': {'name': '塑化',      'sub': ['1303.TW','1326.TW','1402.TW']},
    '2002.TW': {'name': '鋼鐵',      'sub': ['2006.TW','2007.TW','2010.TW']},
    '1216.TW': {'name': '食品',      'sub': ['1201.TW','1210.TW','1225.TW']},
    '2603.TW': {'name': '航運',      'sub': ['2609.TW','2615.TW','2617.TW']},
    '2707.TW': {'name': '觀光',      'sub': ['2731.TW','2727.TW']},
    '3008.TW': {'name': '光電',      'sub': ['2409.TW','3481.TW']},
}

#: 該市場的「類股」是否為單一代表股近似(H-2 揭露開關)。
#: 美股走真 GICS 類股 ETF(XLK/XLF…)→ False;台股走代表股 → True。
_US_SECTOR_SINGLE_STOCK_PROXY = False
_TW_SECTOR_SINGLE_STOCK_PROXY = True

# ⚠️ B4-b DEPRECATED:原 `_PERIOD_MAP = {'1日':'5d','5日':'1mo','1月':'3mo','3月':'6mo'}`
# 正是 H-1 缺陷的根源 —— 它只是 yfinance **下載窗**,卻被 `_fetch_sector_returns`
# 當成「計算區間」(用整個窗的第一根當基期),導致「1日」實際算 ≈4 個交易日。
# 現在區間口徑 SSOT 在 `shared/sector_heatmap.py`(下載窗 / 交易日根數分開兩張表)。
# 本名保留純粹是 `src/ui/etf/etf_dashboard.py:46` 的 re-export shim 相容性,
# 值指向「下載窗」對照表(**已不是計算區間**)。**新程式碼請勿引用。**
_PERIOD_MAP = dict(SECTOR_YF_DOWNLOAD_WINDOW)


def _build_treemap_data(sectors: dict, returns: dict, market: str,
                        *, single_stock_proxy: bool = False,
                        period_label: str = '') -> go.Figure:
    """建立 Plotly Treemap 熱力圖。

    B4-b 修正:
    - **H-3 缺值不再填 0**:`colors` 缺值傳 `None`(Plotly 留白),hover 文字改走
      `customdata` 顯示「無資料」;原本 `colors.append(0)` + `%{marker.color:+.2f}%`
      會讓「從未抓到的標的」顯示成「+0.00%」,與真實持平長得一模一樣(§1 造假)。
    - **H-3 缺值面積縮小**:原缺值母層給 1.0 / 子層給 0.5,比一檔真實 ±0.5% 的
      類股還大。改走 `node_area()`,缺值面積嚴格小於任何有資料節點。
    - **H-9 空序列**:原 `max(abs(c) for c in colors if c != 0) or 5` 在「全部為 0」
      時炸 `ValueError: max() arg is an empty sequence`(整頁白掉)。改 `color_span_pct()`。
    - **H-2 揭露**:`single_stock_proxy=True` 時類股名帶上代表股代號。

    Args:
        sectors: `{ticker: {'name': str, 'sub': [ticker, ...]}}`。
        returns: `{ticker: rate_pct}`;取不到的 ticker **不在** dict 內。
        market: root 節點標籤。
        single_stock_proxy: 該市場的「類股」是否為單一代表股近似(台股 True)。
        period_label: 區間標籤,只用於 hover 文案(如 '1日')。
    """
    ids, labels, parents, values, texts, colors, hovers = [], [], [], [], [], [], []

    # root
    ids.append(market)
    labels.append(market)
    parents.append('')
    values.append(0)
    texts.append(market)
    colors.append(None)      # root 不參與色階(H-9:也不會被 color_span_pct 誤算)
    hovers.append('—')

    for ticker, meta in sectors.items():
        sec_ret = returns.get(ticker)
        _disp = sector_display_name(meta['name'], ticker,
                                    single_stock_proxy=single_stock_proxy)
        sec_label = (f"{_disp}<br>{sec_ret:+.1f}%" if sec_ret is not None
                     else f"{_disp}<br>{HEATMAP_MISSING_TEXT}")
        ids.append(ticker)
        labels.append(sec_label)
        parents.append(market)
        values.append(node_area(sec_ret, is_parent=True))
        texts.append(f'{_disp} [{ticker}]')
        colors.append(sec_ret)          # ← None 保留成 None,Plotly 留白
        hovers.append(hover_value_text(sec_ret))

        # sub-items
        for sub in meta.get('sub', []):
            sub_ret = returns.get(sub)
            _sub_disp = sub.replace('.TW', '').replace('.TWO', '')
            sub_label = (f"{_sub_disp}<br>{sub_ret:+.1f}%" if sub_ret is not None
                         else f"{_sub_disp}<br>{HEATMAP_MISSING_TEXT}")
            ids.append(f'{ticker}/{sub}')
            labels.append(sub_label)
            parents.append(ticker)
            values.append(node_area(sub_ret, is_parent=False))
            texts.append(sub)
            colors.append(sub_ret)      # ← 同上,不填 0
            hovers.append(hover_value_text(sub_ret))

    # 顏色：最大值對稱(H-9:全缺 / 全 0 時回預設跨度,不炸 max() 空序列)
    max_abs = color_span_pct(colors)
    _hover_prefix = f'{period_label}漲跌' if period_label else '漲跌'
    fig = go.Figure(go.Treemap(
        ids=ids, labels=labels, parents=parents,
        values=values, text=texts, customdata=hovers,
        textinfo='label',
        marker=dict(
            colors=colors,
            colorscale=[[0, '#0f5132'], [0.35, '#1a6e36'], [0.5, '#1e2530'],
                        [0.65, '#c0392b'], [1, '#7b1212']],  # 台灣慣例：漲=紅 跌=綠
            cmid=0, cmin=-max_abs, cmax=max_abs,
            colorbar=dict(title='漲跌%', thickness=12),
            line=dict(width=1, color='#0d1117'),
        ),
        # H-3:hover 走 customdata 字串,缺值吐「無資料」而非 %{marker.color} 的 +0.00%
        hovertemplate=f'<b>%{{text}}</b><br>{_hover_prefix}：%{{customdata}}<extra></extra>',
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
    # B4-b H-5:原文案寫「即時抓取」是假話 —— 實際是 yfinance 日線收盤 + 本頁
    # TTL_30MIN 快取,盤中不會反映當下報價。
    st.caption('各類股區間漲跌幅，紅=漲 / 綠=跌（台灣慣例）。點選區塊可展開子類股。')
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
    period_label = col_p.selectbox('計算區間', list(SECTOR_PERIOD_LABELS),
                                    index=0, key='heatmap_period')
    col_r.markdown('<br>', unsafe_allow_html=True)
    refresh = col_r.button('🔄 刷新', key='heatmap_refresh', use_container_width=True)

    is_us = '美股' in market
    sectors = _US_SECTORS if is_us else _TW_SECTORS
    single_stock_proxy = _US_SECTOR_SINGLE_STOCK_PROXY if is_us else _TW_SECTOR_SINGLE_STOCK_PROXY
    # B4-b H-1:傳給 L1 的是**區間標籤**(如 '1日'),不再是 yfinance 下載窗字串。
    # 下載窗與計算區間的對照 SSOT 在 shared/sector_heatmap.py,由 L1 自行查表。
    period  = period_label
    _n_bars = SECTOR_LOOKBACK_TRADING_DAYS[period_label]

    # B4-b H-1/H-5:口徑講清楚 —— 交易日 vs 日曆日、非即時報價。
    st.caption(
        f'口徑：**{period_label} ＝ 最新收盤 vs 往前 {_n_bars} 個「交易日」的收盤**'
        f'（不是 {_n_bars} 個日曆日）；已還原除權息（adjusted close）。'
        f'　資料來源：yfinance **日線收盤**（非即時報價，且本頁最多快取 30 分鐘）。'
    )
    if single_stock_proxy:
        # ⚠️ _colored_box 走 unsafe_allow_html,markdown `**` 不會被解析 → 用 <b>
        _colored_box(
            f'⚠️ <b>台股的「類股」其實是單一代表股，不是類股平均</b><br>'
            f'{TW_SINGLE_STOCK_PROXY_DISCLOSURE}', 'yellow')

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
    fig = _build_treemap_data(sectors, returns, market_label,
                              single_stock_proxy=single_stock_proxy,
                              period_label=period_label)
    st.plotly_chart(fig, width='stretch')

    # ── 數值排行表（補充用）──────────────────────────────────
    st.markdown(f'#### 📊 {market_label} 漲跌排行（{period_label} = {_n_bars} 個交易日）')
    _ret_col = f'{period_label}漲跌%'
    _name_col = '類股（代表股）' if single_stock_proxy else '類股'
    rank_rows = []
    for ticker, meta in sectors.items():
        ret = returns.get(ticker)
        rank_rows.append({
            # H-2:台股側欄名 + 內容都要帶出「這是單一代表股」
            _name_col: sector_display_name(meta['name'], ticker,
                                           single_stock_proxy=single_stock_proxy),
            '代號': ticker,
            # H-4:%欄與方向欄必須同源判斷,不可一格說沒資料、一格說持平
            _ret_col: ret if ret is not None else HEATMAP_MISSING_TEXT,
            '方向': direction_label(ret),
        })
    # H-4:缺值排最後(原本當 0.00% 插進真實報酬中間)
    rank_rows.sort(key=lambda r: sort_key_desc(
        r[_ret_col] if isinstance(r[_ret_col], (int, float)) else None), reverse=True)
    rank_df = pd.DataFrame(rank_rows)
    st.dataframe(rank_df, use_container_width=True, hide_index=True)

    # ── 覆蓋率（H-7:母層 + 子成分都要算,原本只數母層）─────────────
    _sub_tickers = [s for meta in sectors.values() for s in meta.get('sub', [])]
    fetched = sum(1 for t in sectors if returns.get(t) is not None)
    total_s = len(sectors)
    sub_fetched = sum(1 for t in _sub_tickers if returns.get(t) is not None)
    sub_total = len(_sub_tickers)
    _cov = (f'類股層 {fetched}/{total_s}、子成分 {sub_fetched}/{sub_total}'
            if sub_total else f'類股層 {fetched}/{total_s}')
    if fetched < total_s or sub_fetched < sub_total:
        _colored_box(
            f'⚠️ 資料覆蓋率：{_cov}。缺的格子在圖上會<b>留白</b>、排行表顯示'
            f'「{HEATMAP_MISSING_TEXT}」（<b>不會</b>填 0 冒充持平）；'
            f'常見原因：yfinance 限速、市場休市、標的停牌或已下市、'
            f'或上市未滿 {_n_bars + 1} 個交易日。',
            'yellow')
    else:
        _colored_box(f'✅ 資料覆蓋率：{_cov}，全部取得完整', 'green')

    # ── AI 白話總結 ──────────────────────────────────────────
    if gemini_fn:
        st.markdown('---')
        # H-6:session key 原本只有 '_sector_ai_md',不含 market / period
        # → 切 🇹🇼→🇺🇸 或 1日→3月 後,上一組的 AI 段落會原封不動留在下面。
        _ai_key = f'_sector_ai_md::{market_label}::{period_label}'
        clicked = st.button('🤖 生成 AI 白話總結', key='sector_ai_btn')
        if clicked:
            # 只取有數據的類股，依漲跌幅排序（最強→最弱）
            valued = [r for r in rank_rows if isinstance(r[_ret_col], (int, float))]
            ranking = '、'.join(
                f"{r[_name_col]} {r[_ret_col]:+.2f}%" for r in valued
            ) or '目前沒有可用的漲跌資料'

            ups = [r for r in valued if r[_ret_col] > 0]
            downs = [r for r in valued if r[_ret_col] < 0]
            _miss = len(rank_rows) - len(valued)
            if valued:
                strongest = valued[0]
                weakest = valued[-1]
                # H-1:區間標籤不再寫死「今天」—— 選 3月 時說「今天」是假話
                flow = (
                    f"上漲的有 {len(ups)} 個產業、下跌的有 {len(downs)} 個產業"
                    + (f"、另有 {_miss} 個產業沒有資料（不列入判斷）" if _miss else '')
                    + f"。這段期間（{period_label}，即 {_n_bars} 個交易日）"
                    f"最受青睞（漲最多）的是「{strongest[_name_col]}」"
                    f"（{strongest[_ret_col]:+.2f}%），"
                    f"最被冷落（跌最多）的是「{weakest[_name_col]}」"
                    f"（{weakest[_ret_col]:+.2f}%）。"
                )
            else:
                flow = '目前沒有足夠的資料判斷資金流向。'

            sections = [
                {'name': f'近 {period_label}（{_n_bars} 個交易日）哪些產業在漲、哪些在跌',
                 'data': ranking},
                {'name': '錢正在往哪裡跑（資金流向的感覺）', 'data': flow},
            ]
            if single_stock_proxy:
                # H-2:揭露必須跟著數字進 prompt,否則 AI 會把單一個股報酬敘事成「類股平均」
                sections.append({
                    'name': '⚠️ 這批數字的口徑限制（請務必在結論中如實反映）',
                    'data': TW_SINGLE_STOCK_PROXY_DISCLOSURE,   # SSOT 本身即純文字
                })
            _news_q = ('美股 類股 輪動 產業 盤勢' if is_us else '台股 類股 輪動 產業 盤勢')
            news_text = get_news_for('美股' if is_us else '台股', _news_q, 5)
            prompt = build_structured_summary_prompt(
                subject_title=f'近 {period_label}的{market_label}產業表現',
                sections=sections,
                news_text=news_text,
                overall_question='現在資金比較偏好哪些產業、有沒有明顯的輪動、一般人可以怎麼看。',
            )
            with st.spinner('AI 正在用白話幫你整理產業輪動...'):
                md = gemini_fn(prompt, max_tokens=1300)
            st.session_state[_ai_key] = md
            st.markdown(md)
        elif st.session_state.get(_ai_key):
            st.markdown(st.session_state[_ai_key])
