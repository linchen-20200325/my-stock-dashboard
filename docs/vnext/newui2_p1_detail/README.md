# P-1：🎯／💼 detail 對齊 📊 — 真 app 截圖與量測

**這是實作證據，不是驗收通過聲明。** 不代表 QA PASS、Design Gate PASS、CI PASS 或任何 Ready／merge 授權。

- 分支：`claude/b-ui2-p1-detail-parity`（base＝origin/main `8d6e50be`）；授權依據：#1199 comment 7148847917「P-1 A」。
- 範圍：只改 `src/ui2/components/html.py`（`ctxline_html`、`hold_action_row_html`）與 `src/ui2/shell/css.py`（一條規則）。`snapshot_html`（🎯 六維格）**未改**。
- 擷取日：2026-11-25；Streamlit **1.59.2**（`v159` venv）、Playwright 1.64.1、Chromium 157.0.8103.78 headless、deviceScaleFactor=1；PNG 量化為 128 色（每張 ≤ 70KB，最大 54,046 bytes）。
- 畫面是真 `app_ui2.py`（`?ui2_dev=1` 只用於切資料來源／場景，截圖時開發面隱藏），不是 HTML 草稿。
- **Real 日 K 資料日**：2026-11-09（本機 git 追蹤 `data_cache/twii_ohlcv.parquet`，畫面「⚠ 過期 16 天」是 Real 現況，非本批造成）。Real 場景的市場位階為「未載入」（沙箱無 macro 狀態檔），所以 Real 🎯 的市場位階列帶一句長原因（既有 VM `detail`，非本批新增）。

## 檔名規則：`<場景>_<頁>_<視窗寬>.png`

| 場景 | 說明 |
|---|---|
| `fake_ok_*` | FAKE 場景 `loaded`（市場位階有值、無 detail；Risk Cap／動作列有 detail） |
| `fake_stale_*`／`fake_unavailable_*` | FAKE 場景「過期」「來源不可用」 |
| `real_*` | Real-data Preview（預設入口） |
| `real_degraded_*` | Real 讀取整體失敗（`tests/ui2_viewport/degraded_launcher.py`；降級警示在導覽之後） |

頁：`target`＝🎯 標的（精選模式第一屏）、`hold`＝💼 持股。視窗寬：390×844、1280×900、1440×900。每張為捲到頂端的視窗截圖，共 **30 張 PNG**（5 場景 × 2 頁 × 3 寬）。

## 重現

於 repo 根目錄、用 Streamlit 1.59.2＋playwright 1.64.1＋Chromium＋Pillow 的 venv：

```
PYTHONDONTWRITEBYTECODE=1 <venv>/bin/python -m tests.ui2_viewport.p1_detail_shots --out <dir> --json <file>
# base 對照（同一把尺量另一個 checkout，例如 origin/main 的 worktree）
PYTHONDONTWRITEBYTECODE=1 <venv>/bin/python -m tests.ui2_viewport.p1_detail_shots --json <file> --repo <base checkout>
```

- `p1_detail_measurements.json`：本分支；`p1_detail_base_measurements.json`：origin/main `8d6e50be`（同工具、`--repo` 指向 base worktree，不截圖）。
- `tests/ui2_viewport/p1_detail_shots.py` 非 pytest 測試（檔名不以 `test_` 開頭），不在 `measure_viewport.source_files()` 內，不影響 DEC-137 JSON 的 `source_hash`。

## 前後對照（px；base → 本分支）

「新增高度」＝該區塊（🎯 `.ui2-ctxline`／💼 `[data-ui2-q="q2"]`）高度差；`.ui2-qa` 為整個第一屏區塊高度。「截斷／重疊／橫向溢出」＝該區塊內任何子元素 `scrollWidth>clientWidth` 且 overflow 非 visible、子元素相互相交、右緣超出視窗，加整頁水平捲動，任一成立即「有」。

| 圖檔 | 視窗 | 區塊 | base 高 | 新高 | 新增高度 | 新增 detail 行數 | `.ui2-qa` 高 | 截斷／重疊／橫向溢出 |
|---|---|---|---|---|---|---|---|---|
| `real_target_390.png` | 390x844 | 🎯 context 行 | 35.7 | 139.2 | +103.5 | 2 | 233.6 → 337.1 | 無 |
| `real_hold_390.png` | 390x844 | 💼 今日需處理列 | 35.7 | 54.9 | +19.2 | 1 | 289.2 → 308.3 | 無 |
| `fake_ok_target_390.png` | 390x844 | 🎯 context 行 | 35.7 | 54.9 | +19.2 | 1 | 175.3 → 194.5 | 無 |
| `fake_ok_hold_390.png` | 390x844 | 💼 今日需處理列 | 35.7 | 54.9 | +19.2 | 1 | 269.2 → 288.4 | 無 |
| `fake_stale_target_390.png` | 390x844 | 🎯 context 行 | 35.7 | 81.6 | +45.9 | 1 | 200.1 → 246.0 | 無 |
| `fake_stale_hold_390.png` | 390x844 | 💼 今日需處理列 | 35.7 | 54.9 | +19.2 | 1 | 270.0 → 289.2 | 無 |
| `fake_unavailable_target_390.png` | 390x844 | 🎯 context 行 | 35.7 | 100.8 | +65.1 | 2 | 195.2 → 260.3 | 無 |
| `fake_unavailable_hold_390.png` | 390x844 | 💼 今日需處理列 | 35.7 | 54.9 | +19.2 | 1 | 289.2 → 308.3 | 無 |
| `real_target_1280.png` | 1280x900 | 🎯 context 行 | 35.7 | 54.9 | +19.2 | 2 | 214.4 → 233.6 | 無 |
| `real_hold_1280.png` | 1280x900 | 💼 今日需處理列 | 38.7 | 57.9 | +19.2 | 1 | 105.6 → 124.8 | 無 |
| `fake_ok_target_1280.png` | 1280x900 | 🎯 context 行 | 35.7 | 54.9 | +19.2 | 1 | 175.3 → 194.5 | 無 |
| `fake_ok_hold_1280.png` | 1280x900 | 💼 今日需處理列 | 38.7 | 57.9 | +19.2 | 1 | 105.6 → 124.8 | 無 |
| `fake_stale_target_1280.png` | 1280x900 | 🎯 context 行 | 35.7 | 54.9 | +19.2 | 1 | 176.1 → 195.2 | 無 |
| `fake_stale_hold_1280.png` | 1280x900 | 💼 今日需處理列 | 38.7 | 57.9 | +19.2 | 1 | 105.6 → 124.8 | 無 |
| `fake_unavailable_target_1280.png` | 1280x900 | 🎯 context 行 | 35.7 | 54.9 | +19.2 | 2 | 195.2 → 214.4 | 無 |
| `fake_unavailable_hold_1280.png` | 1280x900 | 💼 今日需處理列 | 38.7 | 57.9 | +19.2 | 1 | 105.6 → 124.8 | 無 |
| `real_target_1440.png` | 1440x900 | 🎯 context 行 | 35.7 | 54.9 | +19.2 | 2 | 214.4 → 233.6 | 無 |
| `real_hold_1440.png` | 1440x900 | 💼 今日需處理列 | 38.7 | 57.9 | +19.2 | 1 | 105.6 → 124.8 | 無 |
| `fake_ok_target_1440.png` | 1440x900 | 🎯 context 行 | 35.7 | 54.9 | +19.2 | 1 | 175.3 → 194.5 | 無 |
| `fake_ok_hold_1440.png` | 1440x900 | 💼 今日需處理列 | 38.7 | 57.9 | +19.2 | 1 | 105.6 → 124.8 | 無 |
| `fake_stale_target_1440.png` | 1440x900 | 🎯 context 行 | 35.7 | 54.9 | +19.2 | 1 | 176.1 → 195.2 | 無 |
| `fake_stale_hold_1440.png` | 1440x900 | 💼 今日需處理列 | 38.7 | 57.9 | +19.2 | 1 | 105.6 → 124.8 | 無 |
| `fake_unavailable_target_1440.png` | 1440x900 | 🎯 context 行 | 35.7 | 54.9 | +19.2 | 2 | 195.2 → 214.4 | 無 |
| `fake_unavailable_hold_1440.png` | 1440x900 | 💼 今日需處理列 | 38.7 | 57.9 | +19.2 | 1 | 105.6 → 124.8 | 無 |
| `real_degraded_target_390.png` | 390x844 | 🎯 context 行 | 35.7 | 100.8 | +65.1 | 2 | 233.6 → 298.7 | 無 |
| `real_degraded_hold_390.png` | 390x844 | 💼 今日需處理列 | 35.7 | 54.9 | +19.2 | 1 | 289.2 → 308.3 | 無 |
| `real_degraded_target_1280.png` | 1280x900 | 🎯 context 行 | 35.7 | 54.9 | +19.2 | 2 | 214.4 → 233.6 | 無 |
| `real_degraded_hold_1280.png` | 1280x900 | 💼 今日需處理列 | 38.7 | 57.9 | +19.2 | 1 | 105.6 → 124.8 | 無 |
| `real_degraded_target_1440.png` | 1440x900 | 🎯 context 行 | 35.7 | 54.9 | +19.2 | 2 | 214.4 → 233.6 | 無 |
| `real_degraded_hold_1440.png` | 1440x900 | 💼 今日需處理列 | 38.7 | 57.9 | +19.2 | 1 | 105.6 → 124.8 | 無 |

DOM 順序（兩頁、全部 shot 一致）：區塊內依序 `label → chip →（新增）detail`；`data-ui2-q` 錨點序列不變（🎯 `q1, ctx, q2, q3`；💼 `q1, ctx, ctx, q2, q4`）。base 與本分支的子元素序列見兩份 JSON 的 `ctxline.item_children`／`action_row.children`。

## 內容摘要

- 🎯：市場位階／Risk Cap 兩項各自在 chip 之後、同一個 `.ui2-ctxline__item` 內補畫該欄位**既有** `detail`（`<div class="ui2-row__detail">`，與 📊 `qa_row_html` 同 class、同 escape、同 `shown()` 過濾）。FAKE `loaded` 的市場位階無 detail → 該項與 base 逐位相同。
- 💼：「今日需處理」列在 chip 之後補畫 VM 既有 detail「動作判斷功能尚未開放」。
- 一條 CSS 規則：`.ui2-ctxline__item .ui2-row__detail{white-space:normal}`。**必要性已實測**：未加時，Real 390 的 🎯 因 `.ui2-ctxline__item{white-space:nowrap}` 使長 detail 不換行，造成整頁水平捲動（`hscroll=True`、item 右緣超出視窗）；加上後全部 30 個 shot 無水平捲動、無截斷、無重疊。
- 未改：`snapshot_html`、📊 任何輸出、VM／文案／資料來源。📊／👤／🗂 於 DEC-137 四份 JSON 內相對 base 逐欄 0 差異（>0.15px 或非數值差）。

## 限制（NOT VERIFIED）

Cloud 實際畫面、手機實機、Python 3.11（CI）與本沙箱 Python 版本差異均未驗；本目錄只有沙箱 Chromium headless 的畫面。
