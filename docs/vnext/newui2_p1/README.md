# New UI2 UI Correction P1 證據（2026-11-03；實作組單組；QA 修正後重跑）
- `fake/`、`real/`：`python -m tests.ui2_viewport.measure_viewport --shots all [--feed real]`（自動以 `?ui2_dev=1` 開頁、截圖隱藏開發面＝產品畫面）。Streamlit 1.59.2：FAKE 70/70、Real 11/11。
- `real_states/`：Real 固定 snapshot × 四頁 × 兩 viewport＝56 態全綠（1.59.2）；截圖僅選 4 張。
- `dev/`：預設道 vs `?ui2_dev=1` 各 16 態檢查（`lanes_*.json`）＋開發面／預設道截圖。
- `v156/`：Streamlit 1.56.0 FAKE 70/70、Real 11/11；`dev/lanes_1.56.0.json` 16 態。
- 截圖為精選；目視清單見 `docs/PROJECT_STATE.md` §61。
