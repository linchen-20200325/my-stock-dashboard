# Delta Strip BELOW（唯讀、恆不可比較）— 真 app 截圖與量測

**這是實作證據，不是驗收通過聲明。** 不代表 QA PASS、Design Gate PASS、CI PASS 或任何 Ready／merge 授權。

- 分支：`claude/b-ui2-delta-below-ui`；授權依據：#1199 comment 7131915767、7132044876（B 單一寫入；D1＝BELOW；D4＝專用唯讀欄位；D5＝既有合法文案；僅「不可比較」）。
- 擷取日：2026-11-24；Streamlit **1.59.2**（`v159` venv）、Playwright 1.64.1 Chromium、deviceScaleFactor=1；PNG 量化為 128 色以壓在 300KB 內（每張 ≤ 70KB）。
- 畫面是真 `app_ui2.py`（`?ui2_dev=1` 只用於切資料來源／場景，截圖時開發面隱藏），不是 HTML 草稿。
- **Real 日 K 資料日**：2026-11-09（本機 git 追蹤 `data_cache/twii_ohlcv.parquet`；畫面顯示「⚠ 過期 15 天」，這是 Real 現況，不是本批造成）。

## 檔名規則：`<場景>_<頁>_<視窗寬>_<view|full>.png`

| 場景 | 說明 |
|---|---|
| `real_*` | Real-data Preview（預設入口），視窗 390×844／1280×900／1440×900 |
| `fake_stale_*`／`fake_unavailable_*` | FAKE 場景「過期」「來源不可用」，視窗 390×844 |
| `real_degraded_*` | Real 讀取整體失敗（`tests/ui2_viewport/degraded_launcher.py`），視窗 390×844 |

頁：`market`＝📊 市場、`hold`＝💼 持股。`view`＝捲動到頂端的視窗截圖；`full`＝暫時把視窗高度放大到整頁內容高度（≤3000px）的整頁截圖，用來看 Delta 列在整頁的位置（📊 的 Delta 在 Primary 之後，手機首屏之外）。

`delta_measurements.json`：每張圖的 Delta 列 top／bottom／height／是否單行／是否截斷／是否出首屏、頁面水平捲動、主 CTA 可達（390）。

## 重現

```
S=<venv>; $S/bin/python -I <scratch>/tools/delta_shots.py <out_dir> <meas.json>   # 需設 WM=<worktree>
```
（腳本只重用 `tests/ui2_viewport/measure_viewport.py` 的 `start_server`／`launch_chromium`／`_select_box`／`click_nav`／`_screenshot` 與 `degraded.py`；沒有改任何產品程式。）

## 內容摘要

- 📊：主 CTA／今日結論／狀態／Risk Cap／動作／下一步／今日主要風險 → 台股 Primary（日 K 或誠實空槽）→ **今日變化** → 核心指標卡 → OneBrain Outlook（DEC-157 順序不變）。
- 💼：標題／組合狀態行／第一屏（含主 CTA 列）→ **今日變化**（同一 `.ui2-h-l1` 容器）→ 建議持股水位／OneBrain／Primary／持股表。
- Delta 列文字固定：「今日變化」＋`⬜ 尚未提供`（capability 軸、虛線 chip）＋「今日變化比較功能尚未開放」；無數字、無箭頭、無「無變化」「今日無重大訊號變更」。
