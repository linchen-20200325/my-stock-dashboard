"""New UI2（`src/ui2/`）的 L3 View Model 層。

⚠️ New UI2（`src/ui2/`）≠ Legacy New UI 的 `src/ui_v2/`。

- `*_vm.py`／`vm_common.py`：**純函式** VM builder（輸入＝canonical dict，輸出＝L0 VM 型別）。
  ⛔ streamlit、⛔ I/O、⛔ session_state、⛔ 讀時鐘、⛔ 聚合動作、⛔ 新增投資規則。
- `scenarios.py`：**FAKE** scenario canonical dict（Preview 用；不是真資料）。
- `preview_feed.py`：Preview 期的 feed（取 fake scenario）。日後換成呼叫既有 services 的
  真 feed 時，VM／畫面不需重做（Architecture Gate §10.2）。
"""
