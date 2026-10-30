"""膠囊最小點擊高度 CSS 覆寫可行性（1.56.0）。不被 repo import。"""
import streamlit as st
st.markdown("""<style>
[data-testid="stBaseButton-segmented_control"],[data-testid="stBaseButton-segmented_controlActive"]{min-height:44px !important}
</style>""", unsafe_allow_html=True)
O5 = ["近1月", "近3月", "近6月", "近1年", "全部"]
st.segmented_control("seg5", O5, default="近1年", key="seg5")
with st.form("f"):
    st.segmented_control("fseg", O5, default="近1年", key="fseg")
    st.form_submit_button("套用")
