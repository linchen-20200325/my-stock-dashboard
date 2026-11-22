# S1 附加視覺證據（390×844＋1280×900）— **非 DEC-137 正式欄位**

- 目的：B-UI2-SAFE-PREVIEW-S1-DESIGN-1 之附加證據（#1199 7075802544 B-2）。正式 DEC-137 證據仍為 `docs/vnext/newui2_realfeed`、`newui2_batch3b` 各 2 份 JSON（390×844＋1440×900）。
- 產生方式：repo 外 wrapper 於**執行期覆寫** `measure_viewport.VIEWPORTS`（未改 `tests/ui2_viewport/measure_viewport.py`），旗標預設 OFF，隔離環境（無 Secrets、HTTP(S)_PROXY 指向不可達本機埠、不點診斷按鈕）。
- 版本：Python 3.13.18、Playwright 1.64.1、Chromium 157.0.8103.78、Streamlit 1.59.2／1.56.0。
- 各 JSON 頂層 `supplement.dec137_formal=false`；`meta` 內有 git_sha（產生當時 HEAD）、source_hash（`48baf09d…`）、generated_at。
- 為控制體積，`*_156` 子目錄只保留 JSON，PNG 省略（1.59.2 子目錄保留 core PNG）；`data_page_diag/` 為資料頁「連線診斷暫不提供（預覽模式）」可見性檢查（Streamlit 兩版 × real／fake × 390／1280／1440，共 12 組）。
- 限制：本機 headless，**不是 Cloud 實機**；Cloud SHA／Main file／entrypoint NOT VERIFIED；不代表零 Secrets（啟動仍讀 FINMIND_TOKEN 入記憶體，不外送）。
