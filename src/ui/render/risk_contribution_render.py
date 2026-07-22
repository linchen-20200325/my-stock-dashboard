"""src/ui/render/risk_contribution_render.py — 風險貢獻分解面板(L4 Render).

把 L2 `compute_risk_contribution` 的結果渲染成「市值% vs 風險%」表 + 風險集中警示。
ETF 組合 / 個股組合 兩頁共用(DRY,單一來源)。

§8.2:L4 Render —— 可用 streamlit,無資料抓取/計算(僅呈現 L2 結果)。
"""
from __future__ import annotations

from src.compute.risk.risk_contribution import RiskContributionResult

try:
    import streamlit as st
except ImportError:            # 純 .py 測試環境:import 不炸
    st = None                  # noqa: N816


def render_risk_contribution_panel(
    result: RiskContributionResult,
    *,
    warn_box=None,
    show_header: bool = True,
) -> None:
    """渲染風險貢獻面板。

    Args:
        result: L2 compute_risk_contribution 的回傳。
        warn_box: 選填 callable(msg:str) 自訂「風險集中」警示樣式(如 ETF 頁的
                  紅色 _colored_box);預設用 st.error。
        show_header: 是否印標題 + 說明(預設 True;巢狀場景可關)。
    """
    if st is None:             # 無 streamlit(測試 import)→ no-op
        return
    if show_header:
        st.markdown('#### 🎚️ 風險貢獻分解（市值佔比 vs 風險佔比）')
        st.caption('💡 揭露「風險其實壓在哪幾檔」：某檔市值只佔 40%，卻可能扛了 60% 的組合波動 '
                   '—— 分散效果被高估。用日報酬共變異數做 Euler 分解，風險佔比加總 = 100%。')
    if not result.ok:
        st.info(f'⚪ 暫無法計算風險貢獻：{result.note or "資料不足（需至少 1 檔有價格歷史）"}')
        return
    _disp = result.table.rename(columns={
        'ticker': '代碼', 'weight_pct': '市值%', 'risk_pct': '風險%', 'gap_pct': '風險−市值(差)',
    })[['代碼', '市值%', '風險%', '風險−市值(差)']]
    st.dataframe(_disp, hide_index=True, use_container_width=True)
    _conf = '（樣本偏少，僅供參考）' if result.low_confidence else ''
    st.caption(f'組合年化波動 σ ≈ {result.portfolio_vol_annual_pct:.1f}%'
               f'｜採 {result.n_obs} 個交易日{_conf}')
    _hot = result.table[result.table['concentrated']]
    if not _hot.empty:
        _msg = '、'.join(
            f"{_r['ticker']}（市值 {_r['weight_pct']:.0f}% → 風險 {_r['risk_pct']:.0f}%）"
            for _, _r in _hot.iterrows())
        _full = (f'⚠️ 風險集中：{_msg} —— 風險佔比明顯高於市值佔比，'
                 f'分散效果被高估，這幾檔才是波動的主要來源')
        if warn_box is not None:
            warn_box(_full)
        else:
            st.error(_full)
    if result.note:
        st.caption(f'ℹ️ {result.note}')
