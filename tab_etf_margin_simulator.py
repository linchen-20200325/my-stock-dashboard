from data_config import CACHE_TTL
"""tab_etf_margin_simulator.py ??ETF 鞈芸?摮??Ⅳ璅⊥??UI (v18.162).

??etf_margin_simulator 撘? + yfinance 甇瑕?對???嚗?
- 4 憸冽 preset ?豢? + ?舀除?挾撠?撱箄降
- ETF 璅??豢?嚗?閮?0050 / 006208 / 00878 / 00919嚗?
- 璅⊥?? + ???祇?閮剖?
- 4 ?∴?蝮賢??/ ?憭批???/ ?活??/ 撟喳?瑽▼??
- Plotly ?遘???寞 + ?狡擗??? + ??暺?
- CSV 銝?
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

# ?身 ETF ?皜嚗??亙?摨?+ ??/摮??隞?”嚗?
_DEFAULT_ETFS = {
    "0050.TW":  "?之?啁50",
    "006208.TW": "撖??0",
    "00878.TW":  "?陸瘞貊?擃??,
    "00919.TW":  "蝢斤??啁蝎暸擃",
    "0056.TW":   "?之擃??,
}


@st.cache_data(ttl=CACHE_TTL["price_data"], show_spinner=False)
def _fetch_etf_history(symbol: str, years: int) -> pd.Series | None:
    """敺?yfinance ??ETF ?嗥?寞風?莎?TTL 1 撠???""
    try:
        import yfinance as yf
        end = _dt.date.today()
        start = end - _dt.timedelta(days=years * 365 + 30)
        df = yf.download(symbol, start=start, end=end, progress=False,
                          auto_adjust=True)
        if df is None or df.empty:
            return None
        # yfinance ?啁???MultiIndex columns
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        close = df["Close"].dropna()
        return close
    except Exception as e:
        st.error(f"??yfinance ??{symbol} 憭望?嚗type(e).__name__}: {e}")
        return None


def _render_phase_recommendation() -> str | None:
    """?舀除?挾 selectbox + ?刻 preset hint嚗??單??preset_key ??None??""
    st.markdown("#### 1儭 ?舀除?挾嚗?????")
    phases = list(PHASE_RECOMMENDATION.keys())
    selected_phase = st.selectbox(
        "?桀??舀除?挾",
        options=["嚗???嚗?] + phases,
        index=0,
        key="margin_sim_phase",
        help="靘?????鞊⊿?撠?撱箄降 preset嚗?????梢 preset??,
    )
    if selected_phase == "嚗???嚗?:
        return None
    rec_key = PHASE_RECOMMENDATION[selected_phase]
    rec_label = LEVERAGE_PRESETS[rec_key]["label"]
    st.info(f"? **{selected_phase}** ?挾?刻 ??**{rec_label}**")
    return rec_key


def _render_preset_picker(default_key: str | None) -> str:
    """4 憸冽 preset selectbox嚗???preset_key??""
    st.markdown("#### 2儭 ?Ⅳ憸冽 preset")
    keys = list(LEVERAGE_PRESETS.keys())
    labels = [LEVERAGE_PRESETS[k]["label"] for k in keys]
    default_idx = keys.index(default_key) if default_key in keys else 1  # balanced
    selected_label = st.selectbox(
        "?豢??Ⅳ蝭憟?,
        options=labels,
        index=default_idx,
        key="margin_sim_preset",
    )
    preset_key = keys[labels.index(selected_label)]
    preset = LEVERAGE_PRESETS[preset_key]
    st.caption(f"?? {preset['desc']}")
    # 憿舐內閫貊銵?
    trig_df = pd.DataFrame(preset["triggers"])
    trig_df.columns = ["?閫貊 %", "鞈芸?蝣?%嚗?憪??"]
    st.dataframe(trig_df, hide_index=True, use_container_width=True)
    return preset_key


def _render_target_picker() -> tuple[str, int, float]:
    """ETF 璅? + 撟湔 + ???祇?嚗???(symbol, years, initial_capital)??""
    st.markdown("#### 3儭 ETF 璅? + 璅⊥?")
    col_etf, col_years, col_cap = st.columns([2, 1, 1])
    with col_etf:
        symbol_label_map = {f"{sym} {name}": sym
                            for sym, name in _DEFAULT_ETFS.items()}
        selected_label = st.selectbox(
            "ETF 璅?",
            options=list(symbol_label_map.keys()),
            index=0,
            key="margin_sim_symbol",
        )
        symbol = symbol_label_map[selected_label]
    with col_years:
        years = st.slider("甇瑕撟湔", min_value=3, max_value=15, value=10,
                          step=1, key="margin_sim_years")
    with col_cap:
        initial_capital = st.number_input(
            "???祇?嚗嚗?, min_value=10.0, max_value=10_000.0,
            value=100.0, step=10.0, key="margin_sim_capital",
        ) * 10_000
    return symbol, years, initial_capital


def _render_summary_cards(result, symbol: str) -> None:
    """4 ?∴?蝮賢??/ ?憭批???/ ?活??/ 撟喳?瑽▼??""
    col1, col2, col3, col4 = st.columns(4)
    col1.metric(
        "蝮賢?祉?",
        f"{result.total_return_pct:+.2f}%",
        help=f"蝯?{result.final_equity:,.0f} vs ???祇? "
             f"{result.params.initial_capital:,.0f}",
    )
    col2.metric(
        "?憭批???,
        f"-{result.max_drawdown_pct:.2f}%",
        help="璅⊥??瘛典潮?暺雿???憭扯?撟?,
    )
    col3.metric(
        "? 撘瑕像甈⊥",
        result.liquidation_count,
        delta=f"?? 餈賜像 {result.margin_call_count}",
        delta_color="off",
        help=f"撘瑕像?瑼?{LIQUIDATION_RATIO}% / 餈賜像?瑼?{MARGIN_CALL_RATIO}%",
    )
    col4.metric(
        "撟喳?瑽▼??,
        f"{result.avg_leverage_ratio:.1f}%",
        help="?狡 / 瘛典?? 100嚗?狡?乩?閮",
    )
    triggered_labels = [f"L{i+1}" for i in result.triggered_levels]
    if triggered_labels:
        st.success(f"?? {symbol} 甇斗?閫貊?Ⅳ?０嚗?*{' ??'.join(triggered_labels)}**")
    else:
        st.info(f"?? {symbol} 甇斗??芾孛?潔遙雿?蝣潘??寞??芷? preset ?瑼鳴?")


def _render_chart(result, symbol: str) -> None:
    """?遘???寞嚗椰頠賂?+ ?狡擗?嚗頠賂?+ ??暺?""
    df = result_to_dataframe(result)
    if df.empty:
        return
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["date"], y=df["price"], mode="lines",
        name=f"{symbol} ?嗥??, line=dict(color="#58a6ff", width=2),
        yaxis="y",
    ))
    fig.add_trace(go.Scatter(
        x=df["date"], y=df["borrowed"], mode="lines",
        name="?狡擗?", line=dict(color=TRAFFIC_YELLOW, width=1, dash="dot"),
        yaxis="y2", fill="tozeroy", opacity=0.3,
    ))
    # ??暺?
    liq_df = df[df["status"] == "liquidated"]
    if not liq_df.empty:
        fig.add_trace(go.Scatter(
            x=liq_df["date"], y=liq_df["price"], mode="markers",
            name="? 撘瑕撟喳?, marker=dict(color=TRAFFIC_RED, size=12,
                                          symbol="x"),
            yaxis="y",
        ))
    # ?Ⅳ閫貊蝬?
    add_df = df[df["event"].str.contains("閫貊 L", na=False)]
    if not add_df.empty:
        fig.add_trace(go.Scatter(
            x=add_df["date"], y=add_df["price"], mode="markers",
            name="? ?Ⅳ閫貊", marker=dict(color=TRAFFIC_GREEN, size=10,
                                          symbol="triangle-down"),
            yaxis="y",
        ))
    fig.update_layout(
        title=f"{symbol} ?寞 vs ?狡擗?嚗result.params.preset_key} preset嚗?,
        xaxis_title="?交?",
        yaxis=dict(title="?嗥??(TWD)", side="left"),
        yaxis2=dict(title="?狡擗? (TWD)", side="right", overlaying="y",
                    showgrid=False),
        height=420,
        hovermode="x unified",
        template="plotly_dark",
        legend=dict(orientation="h", y=1.02),
    )
    st.plotly_chart(fig, use_container_width=True)


def render_etf_margin_simulator() -> None:
    """ETF 鞈芸?摮??Ⅳ璅⊥?其蜓?亙嚗策 app.py with tab ?憛?恬???""
    st.markdown("## ? ETF 鞈芸?摮??Ⅳ璅⊥??)
    st.caption(
        "?? **蝑?摩**嚗?澆?甇瑕擃?? X% ??靘?preset 鞈芸?Y% ?祇??Ⅳ??
        f"??蝬剜???< {MARGIN_CALL_RATIO}% **餈賜像靽???*?? {LIQUIDATION_RATIO}% "
        "**撘瑕撟喳?*?芋?砍?閮剔?拇??蕭?乩漱??蝥祥嚗?雿??交?敹菟?霅?
    )

    rec_key = _render_phase_recommendation()
    preset_key = _render_preset_picker(rec_key)
    symbol, years, initial_capital = _render_target_picker()

    if not st.button("?? 頝芋??, type="primary", key="margin_sim_run",
                     use_container_width=True):
        st.info("?? 暺??寞???憪芋??)
        return

    with st.spinner(f"??{symbol} 餈?{years} 撟湔風?脣..."):
        price_series = _fetch_etf_history(symbol, years)
    if price_series is None or len(price_series) == 0:
        st.error("???⊥???甇瑕?對?隢? ETF ??撠僑?賊?閰?)
        return

    params = SimulationParams(
        preset_key=preset_key,
        initial_capital=initial_capital,
        margin_call_ratio=MARGIN_CALL_RATIO,
        liquidation_ratio=LIQUIDATION_RATIO,
    )
    result = simulate_margin_strategy(price_series, params)

    st.markdown("---")
    st.markdown("### ?? 璅⊥蝯?")
    _render_summary_cards(result, symbol)
    _render_chart(result, symbol)

    # ?敦銵?+ CSV
    with st.expander("?? ??敦嚗鈭辣 log嚗?):
        df = result_to_dataframe(result)
        st.dataframe(
            df[df["event"] != ""][["date", "price", "drawdown_pct",
                                    "borrowed", "maintenance_ratio",
                                    "status", "event"]],
            hide_index=True, use_container_width=True,
        )
        st.download_button(
            "? 銝?摰? CSV",
            data=df.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"margin_sim_{symbol}_{preset_key}_{years}y.csv",
            mime="text/csv",
            key="margin_sim_csv",
        )

