"""tab_etf_margin_simulator.py — ETF 質借倒金字塔加碼模擬器 UI (v18.162).

接 etf_margin_simulator 引擎 + yfinance 歷史價，提供：
- 4 風格 preset 選擇 + 景氣階段對應建議
- ETF 標的選擇（預設 0050 / 006208 / 00878 / 00919）
- 模擬期間 + 初始本金設定
- 4 卡（總報酬 / 最大回撤 / 爆倉次數 / 平均槓桿率）
- Plotly 雙軸圖（價格 + 借款餘額疊圖 + 爆倉紅點）
- CSV 下載
"""
from __future__ import annotations

import datetime as _dt

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from shared.colors import TRAFFIC_GREEN, TRAFFIC_RED, TRAFFIC_YELLOW
from etf_margin_simulator import (
    LEVERAGE_PRESETS,
    LIQUIDATION_RATIO,
    MARGIN_CALL_RATIO,
    PHASE_RECOMMENDATION,
    SimulationParams,
    result_to_dataframe,
    simulate_margin_strategy,
)

# 預設 ETF 候選清單（高知名度 + 月配/季配代表）
_DEFAULT_ETFS = {
    "0050.TW":  "元大台灣50",
    "006208.TW": "富邦台50",
    "00878.TW":  "國泰永續高股息",
    "00919.TW":  "群益台灣精選高息",
    "0056.TW":   "元大高股息",
}


@st.cache_data(ttl=3600, show_spinner=False)
def _fetch_etf_history(symbol: str, years: int) -> pd.Series | None:
    """從 yfinance 抓 ETF 收盤價歷史；TTL 1 小時。"""
    try:
        import yfinance as yf
        end = _dt.date.today()
        start = end - _dt.timedelta(days=years * 365 + 30)
        df = yf.download(symbol, start=start, end=end, progress=False,
                          auto_adjust=True)
        if df is None or df.empty:
            return None
        # yfinance 新版回 MultiIndex columns
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        close = df["Close"].dropna()
        return close
    except Exception as e:
        st.error(f"❌ yfinance 抓 {symbol} 失敗：{type(e).__name__}: {e}")
        return None


def _render_phase_recommendation() -> str | None:
    """景氣階段 selectbox + 推薦 preset hint，回傳推薦 preset_key 或 None。"""
    st.markdown("#### 1️⃣ 景氣階段（美林時鐘）")
    phases = list(PHASE_RECOMMENDATION.keys())
    selected_phase = st.selectbox(
        "目前景氣階段",
        options=["（不指定）"] + phases,
        index=0,
        key="margin_sim_phase",
        help="依美林時鐘四象限對應建議 preset；不指定則自由選 preset。",
    )
    if selected_phase == "（不指定）":
        return None
    rec_key = PHASE_RECOMMENDATION[selected_phase]
    rec_label = LEVERAGE_PRESETS[rec_key]["label"]
    st.info(f"💡 **{selected_phase}** 階段推薦 → **{rec_label}**")
    return rec_key


def _render_preset_picker(default_key: str | None) -> str:
    """4 風格 preset selectbox，回傳 preset_key。"""
    st.markdown("#### 2️⃣ 加碼風格 preset")
    keys = list(LEVERAGE_PRESETS.keys())
    labels = [LEVERAGE_PRESETS[k]["label"] for k in keys]
    default_idx = keys.index(default_key) if default_key in keys else 1  # balanced
    selected_label = st.selectbox(
        "選擇加碼節奏",
        options=labels,
        index=default_idx,
        key="margin_sim_preset",
    )
    preset_key = keys[labels.index(selected_label)]
    preset = LEVERAGE_PRESETS[preset_key]
    st.caption(f"📖 {preset['desc']}")
    # 顯示觸發表
    trig_df = pd.DataFrame(preset["triggers"])
    trig_df.columns = ["回撤觸發 %", "質借加碼 %（初始本金）"]
    st.dataframe(trig_df, hide_index=True, use_container_width=True)
    return preset_key


def _render_target_picker() -> tuple[str, int, float]:
    """ETF 標的 + 年數 + 初始本金，回傳 (symbol, years, initial_capital)。"""
    st.markdown("#### 3️⃣ ETF 標的 + 模擬參數")
    col_etf, col_years, col_cap = st.columns([2, 1, 1])
    with col_etf:
        symbol_label_map = {f"{sym} {name}": sym
                            for sym, name in _DEFAULT_ETFS.items()}
        selected_label = st.selectbox(
            "ETF 標的",
            options=list(symbol_label_map.keys()),
            index=0,
            key="margin_sim_symbol",
        )
        symbol = symbol_label_map[selected_label]
    with col_years:
        years = st.slider("歷史年數", min_value=3, max_value=15, value=10,
                          step=1, key="margin_sim_years")
    with col_cap:
        initial_capital = st.number_input(
            "初始本金（萬）", min_value=10.0, max_value=10_000.0,
            value=100.0, step=10.0, key="margin_sim_capital",
        ) * 10_000
    return symbol, years, initial_capital


def _render_summary_cards(result, symbol: str) -> None:
    """4 卡：總報酬 / 最大回撤 / 爆倉次數 / 平均槓桿率。"""
    col1, col2, col3, col4 = st.columns(4)
    col1.metric(
        "總報酬率",
        f"{result.total_return_pct:+.2f}%",
        help=f"終值 {result.final_equity:,.0f} vs 初始本金 "
             f"{result.params.initial_capital:,.0f}",
    )
    col2.metric(
        "最大回撤",
        f"-{result.max_drawdown_pct:.2f}%",
        help="模擬期間淨值高點到低點的最大跌幅",
    )
    col3.metric(
        "💥 強平次數",
        result.liquidation_count,
        delta=f"⚠️ 追繳 {result.margin_call_count}",
        delta_color="off",
        help=f"強平門檻 {LIQUIDATION_RATIO}% / 追繳門檻 {MARGIN_CALL_RATIO}%",
    )
    col4.metric(
        "平均槓桿率",
        f"{result.avg_leverage_ratio:.1f}%",
        help="借款 / 淨值 × 100；無借款日不計入",
    )
    triggered_labels = [f"L{i+1}" for i in result.triggered_levels]
    if triggered_labels:
        st.success(f"📊 {symbol} 此期觸發加碼階梯：**{' → '.join(triggered_labels)}**")
    else:
        st.info(f"📊 {symbol} 此期未觸發任何加碼（價格回撤未達 preset 門檻）")


def _render_chart(result, symbol: str) -> None:
    """雙軸圖：價格（左軸）+ 借款餘額（右軸）+ 爆倉紅點。"""
    df = result_to_dataframe(result)
    if df.empty:
        return
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["date"], y=df["price"], mode="lines",
        name=f"{symbol} 收盤價", line=dict(color="#58a6ff", width=2),
        yaxis="y",
    ))
    fig.add_trace(go.Scatter(
        x=df["date"], y=df["borrowed"], mode="lines",
        name="借款餘額", line=dict(color=TRAFFIC_YELLOW, width=1, dash="dot"),
        yaxis="y2", fill="tozeroy", opacity=0.3,
    ))
    # 爆倉紅點
    liq_df = df[df["status"] == "liquidated"]
    if not liq_df.empty:
        fig.add_trace(go.Scatter(
            x=liq_df["date"], y=liq_df["price"], mode="markers",
            name="💥 強制平倉", marker=dict(color=TRAFFIC_RED, size=12,
                                          symbol="x"),
            yaxis="y",
        ))
    # 加碼觸發綠點
    add_df = df[df["event"].str.contains("觸發 L", na=False)]
    if not add_df.empty:
        fig.add_trace(go.Scatter(
            x=add_df["date"], y=add_df["price"], mode="markers",
            name="🟢 加碼觸發", marker=dict(color=TRAFFIC_GREEN, size=10,
                                          symbol="triangle-down"),
            yaxis="y",
        ))
    fig.update_layout(
        title=f"{symbol} 價格 vs 借款餘額（{result.params.preset_key} preset）",
        xaxis_title="日期",
        yaxis=dict(title="收盤價 (TWD)", side="left"),
        yaxis2=dict(title="借款餘額 (TWD)", side="right", overlaying="y",
                    showgrid=False),
        height=420,
        hovermode="x unified",
        template="plotly_dark",
        legend=dict(orientation="h", y=1.02),
    )
    st.plotly_chart(fig, use_container_width=True)


def render_etf_margin_simulator() -> None:
    """ETF 質借倒金字塔加碼模擬器主入口（給 app.py with tab 區塊呼叫）。"""
    st.markdown("## 💰 ETF 質借倒金字塔加碼模擬器")
    st.caption(
        "📌 **策略邏輯**：價格從歷史高點回撤 X% → 依 preset 質借 Y% 本金加碼。"
        f"擔保維持率 < {MARGIN_CALL_RATIO}% **追繳保證金**、< {LIQUIDATION_RATIO}% "
        "**強制平倉**。模擬假設無利息成本、忽略交易手續費，僅作策略概念驗證。"
    )

    rec_key = _render_phase_recommendation()
    preset_key = _render_preset_picker(rec_key)
    symbol, years, initial_capital = _render_target_picker()

    if not st.button("🚀 跑模擬", type="primary", key="margin_sim_run",
                     use_container_width=True):
        st.info("👆 點上方按鈕開始模擬")
        return

    with st.spinner(f"抓 {symbol} 近 {years} 年歷史價..."):
        price_series = _fetch_etf_history(symbol, years)
    if price_series is None or len(price_series) == 0:
        st.error("❌ 無法取得歷史價，請換 ETF 或減少年數重試")
        return

    params = SimulationParams(
        preset_key=preset_key,
        initial_capital=initial_capital,
        margin_call_ratio=MARGIN_CALL_RATIO,
        liquidation_ratio=LIQUIDATION_RATIO,
    )
    result = simulate_margin_strategy(price_series, params)

    st.markdown("---")
    st.markdown("### 📊 模擬結果")
    _render_summary_cards(result, symbol)
    _render_chart(result, symbol)

    # 明細表 + CSV
    with st.expander("📋 逐日明細（含事件 log）"):
        df = result_to_dataframe(result)
        st.dataframe(
            df[df["event"] != ""][["date", "price", "drawdown_pct",
                                    "borrowed", "maintenance_ratio",
                                    "status", "event"]],
            hide_index=True, use_container_width=True,
        )
        st.download_button(
            "📥 下載完整逐日 CSV",
            data=df.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"margin_sim_{symbol}_{preset_key}_{years}y.csv",
            mime="text/csv",
            key="margin_sim_csv",
        )
