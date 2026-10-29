# tools/visual_fidelity — Visual Fidelity Gate 截圖與量測工具（開發用）

> **定位**：開發／QA 工具，**不是產品程式、不是測試**。供 `docs/governance/UI_VISUAL_FIDELITY_GATE.md`
> （客戶 DEC-109）要求的「每個 UI PR 附實際截圖（desktop＋mobile 390px）＋與 blueprint 對照 11 項」重現用。
> 2026-10-29 由 Phase 1（SSOT Reset／Contract Freeze）自 Inv-3 visual gap audit 的暫存腳本整理入庫（只改路徑參數化與檔頭說明，量測算法未改）。

## ⛔ 邊界

- **不得**被 `app.py`、`src/**`、`shared/**`、`tests/**` import；本目錄任何檔案都不是 production 依賴。
- 檔名**不以 `test_` 開頭**、也**不在 `tests/`**；`pytest.ini` 的 `testpaths = tests` 不會收集本目錄。
- `harness_app.py` 只在本 process 內 monkeypatch L3 service／loader 回傳假資料：不寫 repo、不寫 Sheet、不打外部 API。
- 假資料數字是**版型量測用示意值**；截圖上的任何數字都**不得**被引用成投資結論或資料證據。
- 截圖只證明「畫面長什麼樣」，**不**證明資料正確；資料語意仍由各批 tests／QA 負責。

## 檔案

| 檔 | 用途 |
|---|---|
| `harness_app.py` | Streamlit harness：以 `runpy` 跑**真 `app.py`**（站殼、側欄、手機底部導覽），L3 層換成假資料，呈現三頁「已載入」狀態。查詢參數：`?p=market\|target\|hold`、`&cold=1`（冷啟動）、`&report=1\|partial`（📊 預置更新報告）、`&realflow=1`（🎯 用 repo 內真本地板塊快取） |
| `measure_app.js` | Playwright：開 harness，（🎯 依序點「🗺️ 載入板塊地圖 → 🎯 開始選股 → 🔍 查看此檔」），截 1440×900 與 390×844 **第一屏**＋**全頁長圖**，量 DOM（大綱、元素 y／h、圖表、表格、expander、按鈕、首屏墨水比例） |
| `measure_mock.js` | Playwright：渲染 blueprint `docs/vnext/d25_wireframes/{market,target,holdings}.html` 的桌機框與手機框，量區塊／卡片／svg／表格／CTA 位置並截第一屏 |
| `mock_ink.js` | blueprint 第一屏墨水比例（與 `measure_app.js` 同一 6px 格點算法） |
| `count_eng_words.js` | 📊／💼 可見文字（收合中的 expander 不算）裡工程字樣（線框／SSOT／L3／digest／widget…）的出現次數 |
| `summarize.py` | 把 `measure_app.js` 的 JSON 彙整成文字摘要 |

## 前置

- Python：`streamlit`（版本依 `requirements.txt`；Inv-3 量測時沙箱為 1.59.2，**1.56 floor 未驗**）、`numpy`、`pandas`、`pytest`（harness 借用 `_pytest.monkeypatch.MonkeyPatch` 與 `tests/uit_fakes.py`）。
- Node：`playwright`＋chromium（`npx playwright install chromium`）。若 playwright 是全域安裝，執行時加 `NODE_PATH=$(npm root -g)`。

## 用法

```bash
# 1) 啟動 harness（repo 根目錄執行）
python3 -m streamlit run tools/visual_fidelity/harness_app.py \
  --server.headless true --server.port 8571 --browser.gatherUsageStats false &

# 2) 量測三頁已載入狀態（輸出目錄自訂；建議放暫存區，不要直接放進 repo）
OUT=/path/to/out
node tools/visual_fidelity/measure_app.js $OUT market   > $OUT/app_market.json
EXTRA=report=1 TAG=_reportok node tools/visual_fidelity/measure_app.js $OUT market > $OUT/app_market_reportok.json
node tools/visual_fidelity/measure_app.js $OUT target   > $OUT/app_target.json
EXTRA=realflow=1 TAG=_realflow node tools/visual_fidelity/measure_app.js $OUT target > $OUT/app_target_realflow.json
node tools/visual_fidelity/measure_app.js $OUT hold     > $OUT/app_hold.json
node tools/visual_fidelity/measure_app.js $OUT market cold > $OUT/app_market_cold.json   # 冷啟動

# 3) blueprint 量測與墨水比例
node tools/visual_fidelity/measure_mock.js $OUT > $OUT/mock.json
node tools/visual_fidelity/mock_ink.js
node tools/visual_fidelity/count_eng_words.js       # 需 harness 仍在跑

# 4) 文字摘要
python3 tools/visual_fidelity/summarize.py $OUT/app_market.json
```

環境變數：`PORT`（harness 埠，預設 8571）、`EXTRA`（附加 query）、`TAG`（輸出檔名後綴）。

## 輸出格式

- 截圖：`app_<page>[_cold]<TAG>_<1440|390>.png`（第一屏）、`..._tall.png`（全頁，viewport 拉高到 scrollHeight，上限 30000px）；`mock_<page>_<1440|390>.png`。
- `measure_app.js` JSON（每個 viewport 一組）：`scrollH`、`mainTop`、`sidebarW`、`bottomNav`、`inkRatioFirst`（首屏墨水比例，INFERENCE 級代理指標）、`vertCoverFirst`、`outline[]`（頂層區塊 kind／y／h／chars／charts）、`leaves[]`、`charts[]`、`dfs[]`、`tables[]`、`expanders[]`、`buttons[]`、`totalVisibleChars`、`errors[]`、`tallH`。座標 y 為**頁面絕對座標**。
- `measure_mock.js` JSON：`{market|target|holdings: {1440|390: {contentH, blocks[], allCards[], svgs[], tables[], details[], ctas[], totalChars}}}`；y **相對於 mockup 框**（與 app 比較時改用「相對頁面 H2 的位移」）。

## 放進 PR 的截圖規格

依 Gate 文件 §3：desktop 1440×900 與 mobile 390×844、第一屏＋全頁、冷啟動＋已載入兩態；放 PR 或
`docs/vnext/visual_fidelity/<stage>/`，**單張 < 300KB**（全頁長圖可縮放、或 PNG 256 色量化；Phase 1 baseline 範例見
`docs/vnext/visual_fidelity/phase1_baseline/`）。

## 已知限制

- 沙箱無真外部資料：高度數字依賴夾具（產業數、持股檔數、文字長度）；真資料下候選表預設 50 列的狀態夾具**未覆蓋**。
- 收合中 expander 的內容不量；💼 持股按下 ⑦ AI（付費）後的狀態、「組合設定」葉未覆蓋。
- 手機實機（iOS／Android）、Streamlit Cloud、`requirements.txt` floor 1.56 實機行為：本工具**驗不到**，Gate 報告須照實標「未驗」。
