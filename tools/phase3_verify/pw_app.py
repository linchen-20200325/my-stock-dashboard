"""最小 app：在 streamlit==1.56.0 獨立 venv 下手機視窗量測用。不被 repo import。"""
import streamlit as st
import pandas as pd
st.session_state["runs"] = st.session_state.get("runs", 0) + 1
st.write(f"RUNS={st.session_state['runs']}")
O5 = ["近1月", "近3月", "近6月", "近1年", "全部"]
O5L = ["總體經濟景氣", "股市資金動能", "利率與信用", "通膨與物價", "匯率與外資"]
v1 = st.segmented_control("seg5", O5, default="近1年", key="seg5")
st.write(f"SEG5={v1!r}")
v2 = st.segmented_control("seg5long", O5L, default=O5L[0], key="seg5long")
st.write(f"SEG5L={v2!r}")
v3 = st.segmented_control("seg3", ["日", "週", "月"], default="日", key="seg3")
st.write(f"SEG3={v3!r}")
v4 = st.pills("pills5", O5, default="近1年", key="pills5")
st.write(f"PILLS={v4!r}")
v5 = st.radio("radio5", O5, horizontal=True, key="radio5")
st.write(f"RADIO={v5!r}")
st.markdown("---FORM---")
with st.form("f"):
    fs = st.segmented_control("fseg", O5, default="近1年", key="fseg")
    fr = st.radio("fradio", O5, horizontal=True, key="fradio")
    sub = st.form_submit_button("套用")
st.write(f"FORM sub={sub} fseg={fs!r} fradio={fr!r}")
st.markdown("---OTHER---")
st.badge("OK", color="green", icon=":material/check:")
st.html("<div id='htmlbox' style='padding:4px;border:1px solid red'>html<svg width='20' height='10'><rect width='20' height='10'/></svg></div>")
c1, c2 = st.columns(2)
with c1:
    st.metric("sparkline", "1.2", delta="0.3", chart_data=[1.0, 2.0, 1.5, 3.0], chart_type="line", border=True)
with c2:
    st.metric("nan-spark", "1", chart_data=[1.0, float("nan"), 3.0], chart_type="line", border=True)
st.bar_chart(pd.DataFrame({"v": [3, 1, 2]}, index=["a", "b", "c"]), horizontal=True, height=180)
st.line_chart(pd.DataFrame({"v": [3, 1, 2, 4]}), height=140)
with st.expander("exp", icon=":material/info:"):
    st.write("inside")
with st.container(height=120, border=True):
    for i in range(10):
        st.write(f"row {i}")
