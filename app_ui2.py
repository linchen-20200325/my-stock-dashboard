"""New UI2 Preview 的 `streamlit run` 入口（L6）—— 只接 `src.ui2`。

    streamlit run app_ui2.py

⚠️ 這是 **Preview 入口**，不是 production default：`app.py` 不引用本檔、不加路由、不加 `?ui=2`
（Architecture Gate §7／§8；Cutover 另走 Gate）。資料一律為 FAKE scenario。

⛔ 本檔不得 import `app.py`／Legacy UI（`src.ui.*`、`src.ui_v2`）。
`st.set_page_config()` 必須是第一個 Streamlit 呼叫（host 設定，不屬頁面邏輯）。
入口放 repo 根以避開 `sys.path` 問題（Gate §7.2）。
"""
import streamlit as st

st.set_page_config(page_title="New UI2 Preview", page_icon="🧪", layout="wide")

from src.ui2.shell import run  # noqa: E402

run()
