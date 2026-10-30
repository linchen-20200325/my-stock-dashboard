"""取消選取回退模式實測（1.56.0）：on_change 回呼把 key 寫回最後有效值。不被 repo import。"""
import streamlit as st
OPTS = ["a", "b", "c"]
st.session_state.setdefault("last_ok", "b")
st.session_state.setdefault("seg", "b")          # 以 session_state 播種，不傳 default=（避免雙重指定警告）
def _restore():
    v = st.session_state.get("seg")
    if v is None:
        st.session_state["seg"] = st.session_state["last_ok"]   # 回呼內改寫自己的 key 合法（回呼先於腳本重跑）
    else:
        st.session_state["last_ok"] = v
st.segmented_control("seg", OPTS, key="seg", on_change=_restore)
eff = st.session_state["seg"] if st.session_state["seg"] is not None else st.session_state["last_ok"]
st.write(f"EFF={eff} RAW={st.session_state['seg']!r}")
with st.form("f"):
    st.segmented_control("fseg", OPTS, default="a", key="fseg")
    ok = st.form_submit_button("go")
if ok:
    v = st.session_state["fseg"]
    st.session_state["applied"] = v if v is not None else st.session_state.get("applied", OPTS[0])
st.write(f"APPLIED={st.session_state.get('applied')!r}")
