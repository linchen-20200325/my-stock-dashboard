"""`src/ui_v2` —— 戰情室 v2 UI 的**純資料契約層**（分支 `ui-v2`）。

三個模組，由低到高：
  `tokens.py`      設計 token（顏色／字級／間距／圓角）—— SSOT `docs/v2/spec/UI_TOKENS.md`
  `components.py`  元件規格（卡片四階／徽章 10 種／按鈕五類／斷點）—— SSOT `UI_COMPONENTS.md`
  `page_today.py`  「🚦 今天」頁版面與狀態契約 —— SSOT `UI_PAGE_TODAY.md`

⛔ **全層不 import streamlit**：這三個模組是框架無關的純資料結構＋純函式，
   要能在沒有 Streamlit runtime 的沙箱裡單測。渲染層（`st.*`）留到下一輪，
   屆時由 UI 層引用本層，⛔ 不得反向依賴。

⛔ **不重新宣告狀態常數**：七態 SSOT 是既有 L0 `shared/ui_state.py`；
   本套件只存**常數名字串**（`"UI_LIVE"` …），⛔ 不在此長出第二份（CLAUDE.md §2.1）。
"""

__all__ = ["tokens", "components", "page_today"]
