# OneBrain 持股 FAKE 示範：A2 scratch 離線證據

> **tests-only 離線示範，非 DEC-137 正式存證。** 不稱 Cloud 已驗、不進 CI、不代表任何正式驗收。
> 對應 PR #1268 的 head `711142ce38c5cdae07144ae164a72a3bb0f9df6a`（本證據分支以它為基底）。
> 本分支只供獨立取得與重算，**不開 PR、不進 main**。

## 內容

| 路徑 | 說明 |
|---|---|
| `streamlit_1.56.0/`、`streamlit_1.59.2/` | 兩版 Streamlit 各一組：5 案例（R1／L1／L2／L3／FAILCLOSED）× 3 視窗（390×844／1280×900／1440×900）的 PNG、各案例 JSON、`summary.json` |
| `*/baseline_unmodified_css/` | 未改 CSS 的現況（baseline）。本證據**不含**預覽 CSS 補充比較，也不含深色截圖 |
| `MANIFEST.json` | 版本、四個 A1 檔的雜湊（含 #1268 head 與 A2 修改後 runner 的 blob SHA）、每個檔案的相對路徑／SHA-256／位元組數、已遮罩的命令列 |
| `SHA256SUMS` | `sha256sum` 格式、相對路徑，涵蓋本目錄除自身外的所有檔案 |

檔名規則：`<案例>_baseline_<視窗>_<種類>.png`。

- `viewport`：視窗截圖，預設隱藏開發面（`.st-key-ui2_dev_surface`）。
- `slot`／`testinfo`：OneBrain 槽、槽外測試輸入說明（caption）各自的元素截圖。
- `clip`：槽上緣 −120px 到說明下緣 ＋120px（無說明的 FAILCLOSED：槽上下緣各 ±120px），開發面隱藏。
- `clip_devshown`：僅 L3 與 FAILCLOSED；開發面顯示。下緣另延伸到開發面下緣（若較低）＋120px，所以 FAILCLOSED 版看得到開發面。
- `REALFEED`：僅 R1；同一 server 切回 Real 的對照。
- `NODEMO`：不注入示範的首屏對照（用於 `first_screen_equals_nodemo`）。

## 判定（runner 內建，任一為假即以失敗結束）

原有 12 項判定不變，A2 增補兩項：

- `no_fake_t_above_slot`：排除槽外測試輸入說明後，整頁文字不含 `FAKE-T`，且槽文字含 `FAKE`。
- `caption_after_slot`：說明在槽外，且 `testinfo.top ≥ slot.bottom`；FAILCLOSED 必須沒有說明、並有固定句。

每個案例 JSON 的 `a2.new_checks` 逐視窗記錄這兩項結果；`a2.clips` 記錄 clip 的座標與相對位置。

## 如何重算 SHA

```
cd docs/vnext/onebrain_a2_scratch_evidence
sha256sum -c SHA256SUMS
python ../../../tests/ui2_viewport/a2_evidence_privacy_scan.py .
```

第二行會再檢查 MANIFEST 與實檔一致、PNG 結構、封網計數、內容守衛與結果守衛。

## 如何重跑

需求：Playwright（記錄版本見 MANIFEST）、Chromium，以及要測的 Streamlit 版本所在的 venv。從 repo 根：

```
PYTHONPATH=. <venv>/bin/python -m tests.ui2_viewport.onebrain_hold_demo_evidence \
  --out <OUT_DIR> --python <venv>/bin/python --a2
PYTHONPATH=. python -m tests.ui2_viewport.onebrain_hold_demo_evidence \
  --a2-assemble <EVIDENCE_DIR> --a2-base-sha 711142ce38c5cdae07144ae164a72a3bb0f9df6a
```

`<OUT_DIR>` 必須在 repo 之外（runner 預設拒絕 repo 內輸出）。時間戳與 Chromium 版本會隨環境不同，PNG 位元組不保證逐位元重現；判定結果與版面數值預期一致。

## 與 #1268 head 的差異

- 其餘三個 A1 檔（VM、launcher、測試檔）與 #1268 head 逐位元相同（MANIFEST 以 git blob SHA 列證）。
- runner（`tests/ui2_viewport/onebrain_hold_demo_evidence.py`）只在這個 scratch 分支被增補，檔頭有「A2 scratch 增補」註記；未加 `--a2` 時行為與 #1268 head 相同。
- 新增 `tests/ui2_viewport/a2_evidence_privacy_scan.py`（唯讀掃描腳本）。
- `measure_viewport.py`、`src/`、`app_ui2.py` 均未改。

## 已知限制

- 僅本地離線、Linux、headless Chromium；沒有 Cloud 環境、沒有原生 CI 覆蓋（NOT VERIFIED）。
- 封網只在本進程 Python socket 層與瀏覽器 route 層，不是作業系統層；計數見各案例 JSON 的 `meta.network_sealed`。
- clip 圖以暫時加高的視窗（同寬）截取，只為把上下文放進同一張圖；版面判定仍以原視窗量測為準。
- `viewport` 圖預設隱藏開發面；開發面顯示時的位置請看 `clip_devshown`。
- 沒有逐像素比對基準圖；PNG 是證據，不是回歸基準。
