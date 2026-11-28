"""New UI2 Preview 的 `streamlit run` 入口（L6）—— 只接 `src.ui2`。

    streamlit run app_ui2.py

⚠️ 這是 **Preview 入口**，不是 production default：`app.py` 不引用本檔、不加路由、不加 `?ui=2`
（Architecture Gate §7／§8；Cutover 另走 Gate）。一般入口（無 `?ui2_dev=1`）預設以 **Real-data Preview**（唯讀）呈現
（客戶 D2=A，#1199 comment 7052908287；本檔只在 session 尚無 `ui2_feed` 時播種為 Real，不覆蓋使用者／開發面已選的值）。
Real 缺值如實顯示（⬜／STALE），⛔ 不自動 fallback 到 FAKE。FAKE 場景、資料來源、帳戶示意態的切換
只在 `?ui2_dev=1` 開發面（一般畫面不顯示；`ui2_dev` 不是登入證據，見 `src/ui2/shell/app.py`）。

⛔ 本檔不得 import `app.py`／Legacy UI（`src.ui.*`、`src.ui_v2`）。
`st.set_page_config()` 必須是第一個 Streamlit 呼叫（host 設定，不屬頁面邏輯）。
入口放 repo 根以避開 `sys.path` 問題（Gate §7.2）。
"""
import os

import streamlit as st

st.set_page_config(page_title="New UI2 Preview", page_icon="🧪", layout="wide")

from src.services.connection_diag_service import run_connection_check  # noqa: E402  (唯一允許的非 src.ui2 import；#1110 D-T2)
from src.services.stock_local_lookup_service import run_local_lookup  # noqa: E402  (第二個精確例外；M2 本機日K查詢，R23.52 U2／R23.61)
from src.ui2.shell import run  # noqa: E402
from src.ui2.shell.app import FEED_REAL, lookup_flag_on  # noqa: E402  (常數取自 src.ui2；與 shared.ui2_contract.pages.FEED_REAL 同值，測試釘相等)

# D2=A：session 尚無 feed 選擇才播種為 Real（使用者／開發面已選的值與 rerun 持久性不被覆蓋）。
if "ui2_feed" not in st.session_state:
    st.session_state["ui2_feed"] = FEED_REAL



def _read_lookup_flag() -> bool:
    """標的頁股票代號輸入的功能開關（預設關）。來源：st.secrets 鍵 `ui2_lookup_input`，否則環境變數 `UI2_LOOKUP_INPUT`；
    值 '1'／'true' 才開（判讀見 `lookup_flag_on`）。任何讀取失敗＝視為該來源不存在（不會因失敗而開啟）。
    ⛔ 不使用 `?ui2_dev`（它不是授權）；開關只經參數注入 L5，L5 自己不讀 secrets／環境。"""
    try:
        if "ui2_lookup_input" in st.secrets:
            return lookup_flag_on(st.secrets["ui2_lookup_input"])
    except Exception:  # noqa: BLE001 — 無 secrets 檔／讀取失敗＝該來源不存在
        pass
    try:
        return lookup_flag_on(os.environ.get("UI2_LOOKUP_INPUT"))
    except Exception:  # noqa: BLE001
        return False


def _read_local_ohlcv_opt_in() -> bool:
    """本機日K查詢（M2）的 opt-in（預設關）：環境變數 `UI2_LOCAL_OHLCV_DIR` 已設且去除空白後非空才開（非安全隔離證明；L3 仍自行驗證；值本身此處不使用、不記錄）。
    ⛔ callable 存在不是 opt-in；⛔ 不使用 secrets／`?ui2_dev`。任何讀取失敗＝關。"""
    try:
        v = os.environ.get("UI2_LOCAL_OHLCV_DIR")
        return v is not None and v.strip() != ""          # 純空白（" "、"\t"、"\n"）不是 opt-in；L3 自己仍會再驗
    except Exception:  # noqa: BLE001
        return False


def _read_diag_flag() -> bool:
    """資料頁「連線診斷」的功能開關（預設關）。來源：st.secrets 鍵 `ui2_diag_enabled`，否則環境變數 `UI2_DIAG_ENABLE`；
    值 '1'／'true' 才開（判讀見 `lookup_flag_on`）。任何讀取失敗＝視為該來源不存在（不會因失敗而開啟）。
    關閉時不注入 `run_connection_check`（按鈕 disabled、不探測、不連外）。⛔ 開發面旗標不是授權，不參與判斷。"""
    try:
        if "ui2_diag_enabled" in st.secrets:
            return lookup_flag_on(st.secrets["ui2_diag_enabled"])
    except Exception:  # noqa: BLE001 — 無 secrets 檔／讀取失敗＝該來源不存在
        pass
    try:
        return lookup_flag_on(os.environ.get("UI2_DIAG_ENABLE"))
    except Exception:  # noqa: BLE001
        return False


run(diag_check=(run_connection_check if _read_diag_flag() else None), lookup_input=_read_lookup_flag(),
    local_lookup=(run_local_lookup if _read_local_ohlcv_opt_in() else None))
