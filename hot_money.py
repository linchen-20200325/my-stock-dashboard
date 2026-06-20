from data_config import CACHE_TTL
# -*- coding: utf-8 -*-
"""hot_money.py ???梢??葫嚗?閫漱??憭? ? ?舐?嚗?+ ??菜葫

?游???user 銝??`a731802d-app.py`嚗??Streamlit demo嚗?靽?蝝撘?+
build_signals ?摩嚗I render ?典???tab_macro.py ?Ｘ?鞈?皞?銴 yfinance
TWD=X DataFrame + ?Ｘ? finmind_get fetcher嚗??踹????澆 FinMind??

閮剛?嚗? CLAUDE.md 禮2 銝?湛?嚗?
- 蝝撘?`build_signals` / `_twd_df_to_series` ??streamlit 靘陷嚗皜?
- `render_hot_money_section` ?交 caller 撌脫???_twd_df + token嚗??鞈?series
- FinMind 憭望? / 蝛箄???敺??券?蝝?憿舐內 warning + ?迫蝜芸?嚗?
"""
from __future__ import annotations

import datetime as _dt

import numpy as np
import pandas as pd
import streamlit as st

# ??閰梯圾霈嚗???璆剛???
STATE_TEXT = {
    "?郊瘚": "憭?鞈?甇???亥撣?銝血?甇交??啣馳?????嗾瘛具???湛???閮???,
    "?郊瘚": "憭?敺撣?綽??啣撟??甇亥粥鞎嗯????箄???蝣綽??征??,
    "?嚚?Ｗ?瘜撣?: "?啣馳?＊?潘?雿?鞈蒂?芸?甇亥眺頞撣虜隞?”?梢撌脣?乓?瘜?臬?閫??"
                          "撠?脣??敺?航???憟??澆???霅西死??,
    "?嚚眺?日??抵?": "憭??刻眺頞撣??啣馳?餃韏啗眸?眺?文?質◤?箏???舀??嗡?鞈?憭??抵?嚗?
                            "?舐?閮?鋡怎????雓寞?閫????,
    "?嚚撣???: "?啣馳?＊韏啗眸嚗??∪????箇撠?鞈??????賣迤敺撣?銵?ｇ?"
                      "???∪??臬?賢?????,
    "皞怠?瘚": "憭?撠?鞎瑁?嚗?之?湔?撟喉?鞈?皞怠???雿???撘瑯?,
    "皞怠?瘚": "憭?撠?鞈??嚗?之?湔?撟喉?鞈?皞怠??征雿???撘瑯?,
    "銝剜改?閫??: "憭?鞎瑁都???⊥?憿舀??鞈??閫???怎皜?閮???,
}
DIVERGENCE_STATES = {"?嚚?Ｗ?瘜撣?, "?嚚眺?日??抵?", "?嚚撣???}


# ????????????????????????????????????????????????????????????????????????
# 蝝撘?靽∟?閮?嚗 streamlit 靘陷嚗?
# ????????????????????????????????????????????????????????????????????????
def build_signals(flow_df: pd.DataFrame, fx_df: pd.DataFrame,
                   window: int, flow_thr: float, fx_thr: float) -> pd.DataFrame:
    """?蔥蝐Ⅳ???蝞遝???蒂???????????

    Args:
        flow_df: columns=[date, foreign_net_yi]嚗?鞈眺鞈?? ??嚗?
        fx_df:   columns=[date, usdtwd]嚗SD/TWD ?單??舐?嚗?
        window:  皛曉?蝒鈭斗??交
        flow_thr: 憭?蝝航?鞎瑁都頞?瑼鳴???嚗?
        fx_thr:  ?啣馳蝝航??眸?瑼鳴?%嚗?

    Returns:
        DataFrame[date, foreign_net_yi, usdtwd, twd_apprec, roll_flow,
                  roll_apprec, flow_sig, fx_sig, state, is_divergence,
                  interpretation]
    """
    cols = ["date", "foreign_net_yi", "usdtwd", "twd_apprec", "roll_flow",
            "roll_apprec", "flow_sig", "fx_sig", "state", "is_divergence",
            "interpretation"]
    if flow_df.empty or fx_df.empty:
        return pd.DataFrame(columns=cols)

    df = pd.merge(flow_df, fx_df, on="date", how="inner").sort_values("date").reset_index(drop=True)
    if df.empty:
        return pd.DataFrame(columns=cols)

    # ?啣馳?眸 (%)嚗SD/TWD 銝? = ?啣馳?潘?????甇?潔誨銵典??潘??渲死嚗?
    df["twd_apprec"] = -df["usdtwd"].pct_change() * 100.0
    df["roll_flow"]   = df["foreign_net_yi"].rolling(window, min_periods=1).sum()
    df["roll_apprec"] = df["twd_apprec"].rolling(window, min_periods=1).sum()

    f = np.sign(np.where(df["roll_flow"].abs() >= flow_thr, df["roll_flow"], 0)).astype(int)
    x = np.sign(np.where(df["roll_apprec"].abs() >= fx_thr, df["roll_apprec"], 0)).astype(int)
    df["flow_sig"], df["fx_sig"] = f, x

    conds = [
        (f == 1) & (x == 1),
        (f == -1) & (x == -1),
        (x == 1) & (f <= 0),     # ???臬?嚗撟??雿?鞈?鞎?
        (f == 1) & (x == -1),    # ??抵?嚗?鞈眺雿撟?眸
        (x == -1) & (f >= 0),    # ?臬??嚗撟?眸雿撣鞈??
        (f == 1) & (x == 0),
        (f == -1) & (x == 0),
    ]
    labels = ["?郊瘚", "?郊瘚", "?嚚?Ｗ?瘜撣?, "?嚚眺?日??抵?",
              "?嚚撣???, "皞怠?瘚", "皞怠?瘚"]
    df["state"] = np.select(conds, labels, default="銝剜改?閫??)
    df["is_divergence"] = df["state"].isin(DIVERGENCE_STATES)
    df["interpretation"] = df["state"].map(STATE_TEXT)
    return df


def _twd_df_to_series(twd_df: pd.DataFrame) -> pd.DataFrame:
    """yfinance TWD=X DataFrame ??璅? [date, usdtwd] ?澆???

    ?舀憭車 column ??'close' / 'Close' / 'Adj Close'嚗? datetime index??
    憯撓?????征 DataFrame嚗aller 憿舐內 warning嚗?
    """
    if twd_df is None or twd_df.empty:
        return pd.DataFrame(columns=["date", "usdtwd"])
    df = twd_df.copy()
    # column 璅???
    close_col = None
    for c in ("close", "Close", "Adj Close", "adj_close"):
        if c in df.columns:
            close_col = c
            break
    if close_col is None:
        return pd.DataFrame(columns=["date", "usdtwd"])
    # index ?舀????reset ?箔?
    if df.index.name in (None, "Date", "date") and not pd.api.types.is_integer_dtype(df.index):
        df = df.reset_index()
    # ??date column
    date_col = None
    for c in ("date", "Date", "index"):
        if c in df.columns:
            date_col = c
            break
    if date_col is None:
        return pd.DataFrame(columns=["date", "usdtwd"])
    out = df[[date_col, close_col]].copy()
    out.columns = ["date", "usdtwd"]
    out["date"] = pd.to_datetime(out["date"]).dt.tz_localize(None)
    out["usdtwd"] = pd.to_numeric(out["usdtwd"], errors="coerce")
    out = out.dropna(subset=["usdtwd"])
    out = out[out["usdtwd"] > 0]   # ?蕪? / -1 蝻箏?
    return out.sort_values("date").reset_index(drop=True)


# ????????????????????????????????????????????????????????????????????????
# 鞈???嚗??冽??finmind_get嚗eading_indicators.py嚗?
# ????????????????????????????????????????????????????????????????????????
@st.cache_data(ttl=CACHE_TTL["financial_data"], show_spinner=False)
def fetch_foreign_flow_series(days: int, token: str) -> tuple[pd.DataFrame, str]:
    """??餈?N 憭拙?鞈眺鞈??嚗???leading_indicators.finmind_get嚗?

    Returns:
        (df[date, foreign_net_yi ??], error_msg or "")
    """
    try:
        from leading_indicators import finmind_get
        end_d = _dt.date.today()
        start_d = end_d - _dt.timedelta(days=days + 14)   # 憭?撟曉予鞎瑟??vs 鈭斗??亦楨銵?
        df = finmind_get("TaiwanStockTotalInstitutionalInvestors",
                          "", start_d.strftime("%Y%m%d"),
                          end_d.strftime("%Y%m%d"), token or "")
    except Exception as e:
        return pd.DataFrame(columns=["date", "foreign_net_yi"]), f"FinMind ??憭望?嚗e}"

    if df is None or df.empty:
        return pd.DataFrame(columns=["date", "foreign_net_yi"]), "?∟????喉??航?粹?鈭斗??亙???"

    # ?蕪??鞈??伐???Foreign_Investor / 憭??鞈?蝑?擃?
    name_col = next((c for c in ("name", "institutional_investors") if c in df.columns), None)
    if name_col is None:
        return pd.DataFrame(columns=["date", "foreign_net_yi"]), f"FinMind 蝻粹??交?嚗ols={list(df.columns)[:8]}嚗?
    mask = df[name_col].astype(str).str.contains("Foreign|憭?", case=False, na=False, regex=True)
    fdf = df.loc[mask].copy()
    if fdf.empty:
        return pd.DataFrame(columns=["date", "foreign_net_yi"]), "FinMind ??Foreign 憿鞈?"

    fdf["net"] = pd.to_numeric(fdf["buy"], errors="coerce") - pd.to_numeric(fdf["sell"], errors="coerce")
    out = (fdf.groupby("date", as_index=False)["net"].sum()
              .assign(foreign_net_yi=lambda d: d["net"] / 1e8)
              .loc[:, ["date", "foreign_net_yi"]])
    out["date"] = pd.to_datetime(out["date"])
    return out.sort_values("date").reset_index(drop=True), ""


# ????????????????????????????????????????????????????????????????????????
# v1.2 蝝??惜 helper嚗???啁?Ｙ?????streamlit 皜脫?嚗策 AI prompt ?剁?
# ????????????????????????????????????????????????????????????????????????
def get_latest_hot_money_state(twd_df: pd.DataFrame, token: str = "",
                                days: int = 180, window: int = 5,
                                flow_thr: float = 50.0,
                                fx_thr: float = 0.5) -> dict | None:
    """蝝??惜嚗???啁?Ｖ?閫漱?霈嚗?靘陷 streamlit??

    ?箔?暻澆??剁?tab_macro ??AI 擐葉蝮賜???撣?prompt ?閬?Ｘ?閬?
    雿?`render_hot_money_section` ?批 st.markdown / st.spinner 蝑葡??
    ?⊥??湔銴? helper ?賢蝝?蝞?頛胯?

    Returns:
        dict | None:
            {
              'state':           '皞怠?瘚' / '?郊瘚' / ...,
              'interpretation':  閰?state ?閰梯圾霈嚗?哨?,
              'foreign_net_yi':  ??啣?鞈眺鞈??嚗???,
              'roll_flow':       餈?window ?亦敞閮?鞈???嚗?
              'usdtwd':          ???USD/TWD,
              'roll_apprec':     餈?window ?亙撟?敞閮?鞎塚?%嚗?
              'date':            'YYYY-MM-DD',
            }
            twd_df / FinMind 憭望???None??
    """
    fx_df = _twd_df_to_series(twd_df)
    if fx_df.empty:
        return None
    flow_df, _err = fetch_foreign_flow_series(days, token)
    if flow_df.empty:
        return None
    sig = build_signals(flow_df, fx_df, window, flow_thr, fx_thr)
    if sig.empty:
        return None
    latest = sig.iloc[-1]
    return {
        'state':           str(latest['state']),
        'interpretation':  str(latest.get('interpretation', '')),
        'foreign_net_yi':  float(latest['foreign_net_yi']),
        'roll_flow':       float(latest['roll_flow']),
        'usdtwd':          float(latest['usdtwd']),
        'roll_apprec':     float(latest['roll_apprec']),
        'date':            str(pd.Timestamp(latest['date']).date()),
    }


# ????????????????????????????????????????????????????????????????????????
# UI render嚗 caller expander ?折＊蝷箏??港?閫漱????
# ????????????????????????????????????????????????????????????????????????
def render_hot_money_section(twd_df: pd.DataFrame, token: str = "",
                                key_prefix: str = "hot_money") -> None:
    """皜脫??梢銝?鈭文?瘛勗漲閬???

    Args:
        twd_df: caller 撌脫???yfinance TWD=X DataFrame嚗tw2.get('?啣撟???)嚗?
        token:  FinMind token
        key_prefix: widget key ?韌?踹?銵?
    """
    fx_df = _twd_df_to_series(twd_df)
    if fx_df.empty:
        st.warning("?? ?⊥?啣馳?舐?鞈?嚗aller ?歇??TWD=X嚗??⊥?閮??梢閮???)
        return

    # ?批 panel ????inline columns 銝情??sidebar
    cc1, cc2, cc3, cc4 = st.columns([1, 1, 1, 1])
    days = cc1.slider("??憭拇", 60, 365, 180, step=30,
                       key=f"{key_prefix}_days",
                       help="??餈?N ????鞈?+ ?舐?")
    window = cc2.slider("閫撖??潘?鈭斗??伐?", 3, 20, 5,
                          key=f"{key_prefix}_window",
                          help="餈?N ?亦敞閮?瑟??)
    flow_thr = cc3.slider("憭?蝝航??瑼鳴???", 10, 300, 50, step=10,
                            key=f"{key_prefix}_flow_thr")
    fx_thr = cc4.slider("?啣馳?眸?瑼鳴?%嚗?, 0.1, 2.0, 0.5, step=0.1,
                          key=f"{key_prefix}_fx_thr")

    with st.spinner("? ??FinMind 憭?鞎瑁都頞?.."):
        flow_df, ferr = fetch_foreign_flow_series(days, token)
    if ferr:
        st.warning(ferr)
    if flow_df.empty:
        st.info("?⊥???憭?鞈?嚗?蝣箄? FINMIND_TOKEN ?雯頝胯?)
        return

    sig = build_signals(flow_df, fx_df, window, flow_thr, fx_thr)
    if sig.empty:
        st.info("憭??????????鈭斗??伐???云?哨?嚗?)
        return

    latest = sig.iloc[-1]

    # ??啣霈
    st.markdown(f"**?? ??啣霈嚗pd.Timestamp(latest['date']).date()}嚗?*")
    box = (st.warning if latest["is_divergence"]
           else (st.success if latest["state"] == "?郊瘚"
                 else st.error if latest["state"] == "?郊瘚"
                 else st.info))
    box(f"**{latest['state']}**??{latest['interpretation']}")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("??啣?鞈眺鞈??", f"{latest['foreign_net_yi']:.1f} ??,
                help="甇??鞎瑁?(鞈??脰撣?嚗?嚗都頞?)
    m2.metric(f"餈window}?亦敞閮?鞈?, f"{latest['roll_flow']:.0f} ??)
    m3.metric("??啁????啣馳", f"{latest['usdtwd']:.3f}",
                help="?詨?銝?嚗撟???潦?)
    m4.metric(f"餈window}?亙撟??鞎?, f"{latest['roll_apprec']:+.2f} %")

    # 銝?鈭文?鞊⊿???
    st.markdown("**?妣 銝?鈭文?鞊⊿???*")
    st.caption("璈怨遘嚗?鞈敞閮眺鞈??嚗萵頠賂??啣馳蝝航??眸?銝??郊瘚嚗椰銝??郊瘚嚗?
                "撌虫?/?喃?撠??嚗??Ｕ??脰敶ｇ???唬?蝵柴?)
    plot = sig.dropna(subset=["roll_flow", "roll_apprec"]).copy()
    try:
        import altair as alt
        scale = alt.Scale(
            domain=["?郊瘚", "?郊瘚", "?嚚?Ｗ?瘜撣?, "?嚚眺?日??抵?",
                    "?嚚撣???, "皞怠?瘚", "皞怠?瘚", "銝剜改?閫??],
            range=["#16a34a", "#dc2626", "#f59e0b", "#f97316", "#eab308",
                   "#86efac", "#fca5a5", "#94a3b8"])
        pts = alt.Chart(plot).mark_circle(size=70, opacity=0.55).encode(
            x=alt.X("roll_flow:Q", title=f"餈window}?亙?鞈敞閮眺鞈??(??"),
            y=alt.Y("roll_apprec:Q", title=f"餈window}?亙撟??鞎?%)"),
            color=alt.Color("state:N", scale=scale, title="???),
            tooltip=[alt.Tooltip("date:T", title="?交?"),
                     alt.Tooltip("roll_flow:Q", title="蝝航?鞎瑁都頞???", format=".0f"),
                     alt.Tooltip("roll_apprec:Q", title="蝝航??眸(%)", format=".2f"),
                     alt.Tooltip("state:N", title="???)])
        v = alt.Chart(pd.DataFrame({"x": [0]})).mark_rule(strokeDash=[4, 4], color="#888").encode(x="x:Q")
        h = alt.Chart(pd.DataFrame({"y": [0]})).mark_rule(strokeDash=[4, 4], color="#888").encode(y="y:Q")
        last = alt.Chart(plot.tail(1)).mark_point(
            size=320, shape="diamond", filled=True, color="black").encode(
                x="roll_flow:Q", y="roll_apprec:Q")
        st.altair_chart((pts + v + h + last).properties(height=360),
                          use_container_width=True)
    except Exception as _ce:
        # ??抒′??撠? fund v18.240嚗?altair 憭望?????fallback
        # st.scatter_chart嚗?撅支? altair ???賂?嚗蝝”?潮?蝝?
        st.caption(f"?? 鞊⊿??葡?仃??{type(_ce).__name__}嚗??寥＊蝷箏?憪?”嚗?)
        _t = plot.tail(20)[["date", "roll_flow", "roll_apprec", "state"]].copy()
        _t["date"] = pd.to_datetime(_t["date"]).dt.date
        st.dataframe(
            _t.rename(columns={"date": "?交?", "roll_flow": f"餈window}?亙?鞈???",
                                  "roll_apprec": f"餈window}?亙?鞎?%)", "state": "???}),
            use_container_width=True, hide_index=True, height=320)

    # ???????迎?bar/line 摨惜銋 altair ??銝雿菟??
    cc_a, cc_b = st.columns(2)
    with cc_a:
        st.markdown("**憭?瘥鞎瑁都頞???嚗?*")
        try:
            st.bar_chart(sig.set_index("date")["foreign_net_yi"], height=220)
        except Exception as _be:
            st.caption(f"?? bar chart 憭望?嚗type(_be).__name__}嚗??寥＊蝷箏偏畾菜??")
            st.dataframe(sig[["date", "foreign_net_yi"]].tail(10),
                          use_container_width=True, hide_index=True)
    with cc_b:
        st.markdown("**蝢?/?啣馳嚗????啣馳?潘?**")
        try:
            st.line_chart(sig.set_index("date")["usdtwd"], height=220)
        except Exception as _le:
            st.caption(f"?? line chart 憭望?嚗type(_le).__name__}嚗??寥＊蝷箏偏畾菜??")
            st.dataframe(sig[["date", "usdtwd"]].tail(10),
                          use_container_width=True, hide_index=True)

    # ?鈭辣皜
    st.markdown("**?? 餈??鈭辣**")
    div = sig[sig["is_divergence"]].copy()
    if div.empty:
        st.success("閫撖???芸皜砍?＊?嚗????之?港??氬?)
    else:
        show = div.sort_values("date", ascending=False).head(15).copy()
        show["?交?"] = show["date"].dt.date
        show = show.rename(columns={
            "state": "???,
            "roll_flow": f"餈window}?亙?鞈???",
            "roll_apprec": f"餈window}?亙?鞎?%)",
            "interpretation": "閫??",
        })
        show[f"餈window}?亙?鞈???"] = show[f"餈window}?亙?鞈???"].round(0)
        show[f"餈window}?亙?鞎?%)"] = show[f"餈window}?亙?鞎?%)"].round(2)
        st.dataframe(
            show[["?交?", "???, f"餈window}?亙?鞈???", f"餈window}?亙?鞎?%)", "閫??"]],
            use_container_width=True, hide_index=True)

