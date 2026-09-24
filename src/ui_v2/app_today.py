"""「🚦 今天」頁的 `streamlit run` 進入點 —— **零邏輯**，只把渲染層接起來。

    streamlit run src/ui_v2/app_today.py

⚠️ **本輪畫的是「尚未接線」的頁面**，⛔ 不是示範資料：每張卡都是徽章 #5
   「這項還沒做」、大字區一律留白（見 `render.unwired_view_model` 的 docstring）。
   要看的是**版面／密度階梯／斷點**，⛔ 不是數字 —— 這一輪本來就沒有數字。

⛔ **這裡不得長出任何邏輯。** 組 view model 是 `render.py` 的事、產字串是
   `markup.py` 的事。進入點一旦開始判斷，下一個人就會在這裡接資料，
   而這個檔**不在任何測試的射程內**（`tests/ui_v2/` 測的是 `markup` / `render`）。

   ⚠️ **`st.set_page_config()` 是這條紀律的唯一例外**（2026-09-21 補）——
   它在本質上是 **host／頁面容器設定**，不是頁面邏輯：它不讀資料、不做判斷、
   不影響任何一張卡畫出什麼。⛔ 這個例外**不得被引用**來在此新增第二件事。
"""
import streamlit as st

from src.ui_v2.render import render_page_today, unwired_view_model

# 🔴 **必須是本檔的第一個 Streamlit 呼叫** —— Streamlit 規定 `set_page_config()`
#    之前不得有任何 st 指令，否則整頁直接炸在啟動。
#    （`import streamlit` 與 `from src.ui_v2.render import …` 都只是 import，
#      不發出任何 st 指令，所以擺在上面是安全的。）
#
# **為什麼要 `layout="wide"`（理由逐字保留，⛔ 不要改寫成「比較好看」）**：
#   客戶 2026-09-16 已裁示「第二層＝**3 張並排卡**」，層級網格 `3/2/1` 也已寫進規格
#   （`page_today.LAYER_GRID_COLS`）。**窄欄會讓那個已核准的版面根本畫不出來**
#   ⇒ 加 `layout="wide"` **不是新的版面設計，是讓已核准的版面能被畫出來的前提**。
#   Streamlit 預設是窄置中欄（`layout="centered"`），第二層的 3 欄會被擠掉。
#
# ⚠️ **這是 AI 總管 2026-09-21 的判斷，客戶可一句話推翻。**
#   依 CLAUDE.md §-1.5.F 判定 7／§-1.5.A-8：「用什麼手段讓已核准的版面畫得出來」
#   屬內部自決；**「畫面長什麼樣」才要走草稿先行**。本行**沒有改變畫面結構** ——
#   它讓規格裡已經拍板的 3 欄真的排成 3 欄。若客戶認為連這個都該先看草稿，以客戶為準。
st.set_page_config(layout="wide")

render_page_today(unwired_view_model())
