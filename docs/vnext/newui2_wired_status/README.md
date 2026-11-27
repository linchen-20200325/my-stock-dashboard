# 📊 市場頁尾「接入狀態」— 真 app 截圖與量測

**這是實作證據，不是驗收通過聲明。** 不代表 QA PASS、Design Gate PASS、CI PASS 或任何 Ready／merge 授權。

- 分支：`claude/b-ui2-market-wired-status`（base＝origin/main `2fd0773e120d27f2093078dae67404eded333fc5`）。
- 授權與設計出處（#1199）：客戶 comment 7167315139（授權施工）；最終 Copy／線框／顯示條件／allowlist／N1–N11＝7160953590；三點守衛補強＝7162031909；兩條測試定位＝7164432247；Work 設計 PASS 與兩條最小修正＝7165666659。
- production 只改 `src/services/ui2/real_canonical.py`：📊 sections 尾端附加一個 L1 區塊 `market_wired_status`（標題＝既有「接入狀態」，恰 2 欄）。`src/ui2/**`、`app_ui2.py`、`measure_viewport.py` 零變更 ⇒ `measure_viewport.source_hash` 仍為 `2a62b4e197829d7d9d798e83bff5995531a7253f4a5a31dae2de00442b6f3c1a`（以 `source_hash()` 重算確認）。
- 擷取日：2026-11-25；Streamlit **1.59.2**（`v159` venv）與 **1.56.0**（`v156` venv，`requirements.txt` floor）、Playwright 1.64.1、Chromium 157.0.8103.78 headless、deviceScaleFactor=1；Python 3.13（CI 為 3.11，未驗）。PNG 量化 128 色，最大 70,938 bytes（≤70 KiB）。
- 畫面是真 `app_ui2.py`（預設 Real 入口、不開 `?ui2_dev=1`，產品畫面無開發面），不是 HTML 草稿。

## 資料誠實註記（請先讀）

- 沙箱的 Real 是**快取資料**：台股日 K 最新資料日 **2026-11-09**（本機 git 追蹤 `data_cache/twii_ohlcv.parquet`，今天畫面顯示「⚠ 過期 17 天」，這是 Real 現況，不是本批造成；DEC-137 既有 JSON 擷取時為 16 天，差一天純屬日期推進）；市場位階為「未載入」（沙箱無 macro 狀態檔）。
- `live`＝完全不覆寫的真 Real 現況。**其餘各組態是在真 feed 讀到的 snapshot 上覆寫幾個欄位**（`tests/ui2_viewport/wired_status_launcher.py`；覆寫的是 snapshot，不是畫面），用來讓各種顯示條件分支可被拍到——它們**不是**真實出現過的資料狀態。覆寫內容：
  - `loaded`：台股 `is_stale=False, age_days=0`（卡片與日 K 同步）＋位階 `bull`（注入）；
  - `stale`：`is_stale=True, age_days=5`；
  - `missing`：台股 `ok=False`、無收盤／資料日（卡片「⬜ 資料未取得」）；
  - `no_new_data`／`undetermined`：上游狀態 `NO_NEW_DATA`／`UNDETERMINED`；
  - `unavailable`：台股 `None`＋錯誤代碼 `OSError`；
  - `fetch_failed`：上游 `FETCH_FAILED`（含 `has_upstream_error`）；
  - `legacy_upstream_error`：上游狀態空字串但 `has_upstream_error=True`（舊讀法）；
  - `degraded`：`read_real_snapshot` 整體 raise（同 `degraded_launcher.py` 路徑）。

## 檔名規則：`<tag>_<組態>_<視窗寬>_<tail|full>.png`

- `tag`：`st159`＝Streamlit 1.59.2；`st156`＝Streamlit 1.56.0。
- 組態：**畫**＝`live`／`loaded`／`stale`／`missing`／`no_new_data`／`undetermined`；**不畫**＝`unavailable`／`fetch_failed`／`legacy_upstream_error`／`degraded`（這四組的圖就是「📊 頁尾沒有該區塊」的證據）。
- `tail`：捲到頁尾的視窗截圖（含新區塊；不畫的組態則是頁尾 OneBrain 之後空白）。`full`：把視窗高度暫時放大到內容高度（≤3000px）的整頁截圖，只截 390 寬。
- 覆蓋範圍：1.59.2＝全部 10 組態 × 3 寬（390×844／1280×900／1440×900）的 `tail`，加 390 的 `full`；1.56.0＝全部 10 組態的 390 `tail`＋`full`，另 `loaded`／`no_new_data`／`unavailable` 在 1280／1440 的 `tail`。共 66 張 PNG。
- `wired_status_measurements.json`：`st159`／`st156`（本分支）與 `base_st159`／`base_st156`（origin/main `2fd0773e`，同工具、同組態，不截圖）四組量測；數值取到小數 1 位。

## 重現

於 repo 根目錄、用 Streamlit＋playwright＋Chromium＋Pillow 的 venv：

```
PYTHONDONTWRITEBYTECODE=1 <venv>/bin/python -m tests.ui2_viewport.wired_status_shots --python <venv>/bin/python --tag st159 --out <dir> --json <file>
# base 對照（沒有該區塊；只量不拍）
PYTHONDONTWRITEBYTECODE=1 <venv>/bin/python -m tests.ui2_viewport.wired_status_shots --python <venv>/bin/python --repo <base checkout> --tag base_st159 --no-shots --json <file>
# 1.56：把 --python 換成 floor 的 venv、--tag 改 st156；只跑部分：--cases live,loaded --viewports 390,1280 --full ''
```

`tests/ui2_viewport/wired_status_shots.py`、`wired_status_launcher.py` 非 pytest 測試（檔名不以 `test_` 開頭），不在 `measure_viewport.source_files()` 內，不影響 DEC-137 JSON 的 `source_hash`。

## 新區塊量測（px；本分支 vs base）

欄位說明：「值／detail 行」＝該列 value 與 detail 文字的視覺行數（`/0`、`/1` 各一欄）；「頁高」＝`stMain.scrollHeight`（base → 本分支）；「截斷／重疊／橫向」＝區塊內任何子元素 `scrollWidth>clientWidth` 且 overflow 非 visible、列與列相交、右緣超出視窗，加整頁水平捲動，任一成立即「有」；「標題次數」＝「接入狀態」在 `document.body.innerText` 的出現次數；「DOM 順序」＝錨點頂緣由上到下（`primary_or_kbar`＝日 K 主圖／誠實空槽、`delta`＝今日變化、`grid`＝核心指標卡、`onebrain`、`wired_status`＝新區塊標題）。

| tag | 組態 | 視窗 | 區塊 | 區塊頂（頁內） | 區塊高 | `/0` 值／detail 行 | `/1` 值／detail 行 | 頁高 | 截斷／重疊／橫向 | 標題次數 | DOM 順序 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| st159 | live | 390x844 | 畫 | 1744.5 | 198.7 | 1／0 | 1／2 | 1809 → 2007 | 無 | 1 | primary_or_kbar → delta → grid → onebrain → wired_status |
| st159 | live | 1280x900 | 畫 | 1170.7 | 178.2 | 1／0 | 1／1 | 1187 → 1365 | 無 | 1 | primary_or_kbar → delta → grid → onebrain → wired_status |
| st159 | live | 1440x900 | 畫 | 1151.5 | 178.2 | 1／0 | 1／1 | 1168 → 1346 | 無 | 1 | primary_or_kbar → delta → grid → onebrain → wired_status |
| st159 | loaded | 390x844 | 畫 | 1656.0 | 198.7 | 1／0 | 1／2 | 1720 → 1919 | 無 | 1 | primary_or_kbar → delta → grid → onebrain → wired_status |
| st159 | loaded | 1280x900 | 畫 | 1124.4 | 178.2 | 1／0 | 1／1 | 1140 → 1319 | 無 | 1 | primary_or_kbar → delta → grid → onebrain → wired_status |
| st159 | loaded | 1440x900 | 畫 | 1124.4 | 178.2 | 1／0 | 1／1 | 1140 → 1319 | 無 | 1 | primary_or_kbar → delta → grid → onebrain → wired_status |
| st159 | stale | 390x844 | 畫 | 1744.5 | 198.7 | 1／0 | 1／2 | 1809 → 2007 | 無 | 1 | primary_or_kbar → delta → grid → onebrain → wired_status |
| st159 | stale | 1280x900 | 畫 | 1170.7 | 178.2 | 1／0 | 1／1 | 1187 → 1365 | 無 | 1 | primary_or_kbar → delta → grid → onebrain → wired_status |
| st159 | stale | 1440x900 | 畫 | 1151.5 | 178.2 | 1／0 | 1／1 | 1168 → 1346 | 無 | 1 | primary_or_kbar → delta → grid → onebrain → wired_status |
| st159 | missing | 390x844 | 畫 | 1575.7 | 198.7 | 1／0 | 1／2 | 1640 → 1838 | 無 | 1 | primary_or_kbar → delta → grid → onebrain → wired_status |
| st159 | missing | 1280x900 | 畫 | 957.0 | 178.2 | 1／0 | 1／1 | 973 → 1151 | 無 | 1 | primary_or_kbar → delta → grid → onebrain → wired_status |
| st159 | missing | 1440x900 | 畫 | 937.8 | 178.2 | 1／0 | 1／1 | 954 → 1132 | 無 | 1 | primary_or_kbar → delta → grid → onebrain → wired_status |
| st159 | no_new_data | 390x844 | 畫 | 1832.4 | 198.7 | 1／0 | 1／2 | 1896 → 2095 | 無 | 1 | primary_or_kbar → delta → grid → onebrain → wired_status |
| st159 | no_new_data | 1280x900 | 畫 | 1195.7 | 178.2 | 1／0 | 1／1 | 1212 → 1390 | 無 | 1 | primary_or_kbar → delta → grid → onebrain → wired_status |
| st159 | no_new_data | 1440x900 | 畫 | 1176.5 | 178.2 | 1／0 | 1／1 | 1193 → 1371 | 無 | 1 | primary_or_kbar → delta → grid → onebrain → wired_status |
| st159 | undetermined | 390x844 | 畫 | 1787.4 | 198.7 | 1／0 | 1／2 | 1851 → 2050 | 無 | 1 | primary_or_kbar → delta → grid → onebrain → wired_status |
| st159 | undetermined | 1280x900 | 畫 | 1175.2 | 178.2 | 1／0 | 1／1 | 1191 → 1369 | 無 | 1 | primary_or_kbar → delta → grid → onebrain → wired_status |
| st159 | undetermined | 1440x900 | 畫 | 1156.0 | 178.2 | 1／0 | 1／1 | 1172 → 1350 | 無 | 1 | primary_or_kbar → delta → grid → onebrain → wired_status |
| st159 | unavailable | 390x844 | 不畫 | — | — | — | — | 1574 → 1574 | 無 | 0 | primary_or_kbar → delta → grid → onebrain |
| st159 | unavailable | 1280x900 | 不畫 | — | — | — | — | 928 → 928 | 無 | 0 | primary_or_kbar → delta → grid → onebrain |
| st159 | unavailable | 1440x900 | 不畫 | — | — | — | — | 908 → 908 | 無 | 0 | primary_or_kbar → delta → grid → onebrain |
| st159 | fetch_failed | 390x844 | 不畫 | — | — | — | — | 1831 → 1831 | 無 | 0 | primary_or_kbar → delta → grid → onebrain |
| st159 | fetch_failed | 1280x900 | 不畫 | — | — | — | — | 1191 → 1191 | 無 | 0 | primary_or_kbar → delta → grid → onebrain |
| st159 | fetch_failed | 1440x900 | 不畫 | — | — | — | — | 1172 → 1172 | 無 | 0 | primary_or_kbar → delta → grid → onebrain |
| st159 | legacy_upstream_error | 390x844 | 不畫 | — | — | — | — | 1831 → 1831 | 無 | 0 | primary_or_kbar → delta → grid → onebrain |
| st159 | legacy_upstream_error | 1280x900 | 不畫 | — | — | — | — | 1191 → 1191 | 無 | 0 | primary_or_kbar → delta → grid → onebrain |
| st159 | legacy_upstream_error | 1440x900 | 不畫 | — | — | — | — | 1172 → 1172 | 無 | 0 | primary_or_kbar → delta → grid → onebrain |
| st159 | degraded | 390x844 | 不畫 | — | — | — | — | 1456 → 1456 | 無 | 0 | primary_or_kbar → delta → grid → onebrain |
| st159 | degraded | 1280x900 | 不畫 | — | — | — | — | 932 → 932 | 無 | 0 | primary_or_kbar → delta → grid → onebrain |
| st159 | degraded | 1440x900 | 不畫 | — | — | — | — | 932 → 932 | 無 | 0 | primary_or_kbar → delta → grid → onebrain |
| st156 | live | 390x844 | 畫 | 1744.5 | 198.7 | 1／0 | 1／2 | 1809 → 2007 | 無 | 1 | primary_or_kbar → delta → grid → onebrain → wired_status |
| st156 | loaded | 390x844 | 畫 | 1656.0 | 198.7 | 1／0 | 1／2 | 1720 → 1919 | 無 | 1 | primary_or_kbar → delta → grid → onebrain → wired_status |
| st156 | stale | 390x844 | 畫 | 1744.5 | 198.7 | 1／0 | 1／2 | 1809 → 2007 | 無 | 1 | primary_or_kbar → delta → grid → onebrain → wired_status |
| st156 | missing | 390x844 | 畫 | 1575.7 | 198.7 | 1／0 | 1／2 | 1640 → 1838 | 無 | 1 | primary_or_kbar → delta → grid → onebrain → wired_status |
| st156 | no_new_data | 390x844 | 畫 | 1832.4 | 198.7 | 1／0 | 1／2 | 1896 → 2095 | 無 | 1 | primary_or_kbar → delta → grid → onebrain → wired_status |
| st156 | undetermined | 390x844 | 畫 | 1787.4 | 198.7 | 1／0 | 1／2 | 1851 → 2050 | 無 | 1 | primary_or_kbar → delta → grid → onebrain → wired_status |
| st156 | unavailable | 390x844 | 不畫 | — | — | — | — | 1574 → 1574 | 無 | 0 | primary_or_kbar → delta → grid → onebrain |
| st156 | fetch_failed | 390x844 | 不畫 | — | — | — | — | 1831 → 1831 | 無 | 0 | primary_or_kbar → delta → grid → onebrain |
| st156 | legacy_upstream_error | 390x844 | 不畫 | — | — | — | — | 1831 → 1831 | 無 | 0 | primary_or_kbar → delta → grid → onebrain |
| st156 | degraded | 390x844 | 不畫 | — | — | — | — | 1456 → 1456 | 無 | 0 | primary_or_kbar → delta → grid → onebrain |
| st156 | loaded | 1280x900 | 畫 | 1124.4 | 178.2 | 1／0 | 1／1 | 1140 → 1319 | 無 | 1 | primary_or_kbar → delta → grid → onebrain → wired_status |
| st156 | loaded | 1440x900 | 畫 | 1124.4 | 178.2 | 1／0 | 1／1 | 1140 → 1319 | 無 | 1 | primary_or_kbar → delta → grid → onebrain → wired_status |
| st156 | no_new_data | 1280x900 | 畫 | 1195.7 | 178.2 | 1／0 | 1／1 | 1212 → 1390 | 無 | 1 | primary_or_kbar → delta → grid → onebrain → wired_status |
| st156 | no_new_data | 1440x900 | 畫 | 1176.5 | 178.2 | 1／0 | 1／1 | 1193 → 1371 | 無 | 1 | primary_or_kbar → delta → grid → onebrain → wired_status |
| st156 | unavailable | 1280x900 | 不畫 | — | — | — | — | 928 → 928 | 無 | 0 | primary_or_kbar → delta → grid → onebrain |
| st156 | unavailable | 1440x900 | 不畫 | — | — | — | — | 908 → 908 | 無 | 0 | primary_or_kbar → delta → grid → onebrain |

## 結論（實測；非驗收）

- **位置**：新區塊恆在 `onebrain` 之後、頁尾；所有「畫」的組態 DOM 順序皆為 `primary_or_kbar → delta → grid → onebrain → wired_status`，其餘錨點順序與 base 相同（46 筆逐筆比對：去掉 `wired_status` 後與 base 順序逐一相同）。「接入狀態」在整頁恰 1 次。
- **高度**：390 寬區塊高 **198.7px**（標題 25.6＋`/0` 59.1＋`/1` 100.0；`/1` 的 detail 折 2 行，value 與標題皆單行），1280／1440 寬 **178.2px**（detail 單行）。規格估算為 ≈210px，實測較小。頁高恰增加一個區塊高度（例：Real `live` 390 的 1809 → 2007；不畫的組態頁高與 base 完全相同）。
- **無截斷／重疊／橫向捲動**：全部 46 筆（含 1.56.0）皆為「無」。無 chip；`expanders` 於量測 JSON 逐筆記錄。
- **不畫的組態**（`unavailable`／`fetch_failed`／`legacy_upstream_error`／`degraded`）：頁高、DOM 順序與 base 完全相同，「接入狀態」0 次。
- 兩版 Streamlit 的區塊高度、行數、順序一致。

## DEC-137 量測（`measure_viewport --shots none`，兩版 Streamlit）

- FAKE（`docs/vnext/newui2_batch3b` 兩份）：重量測 120／120 通過、failures 空；與已入庫 JSON 逐欄比對（>0.15px 或非數值差）**0 差異**，故未重產。
- Real（`docs/vnext/newui2_realfeed` 兩份）：19／19 通過、failures 空；Real 390 📊 的 `nav_margin_after_risk` 仍為 **109.8**；`p2_nav_margin_160`、`p2_real_nav_margin_109`、`w11_hold_layout` 無失敗。與已入庫 JSON 的差異共 12 欄／份，全部來自三類：
  1. 台股日 K 文字「過期 16 天」→「17 天」（日期推進，非本批）；
  2. 0.2–0.8px 的捲動尾端量測雜訊（`last_content_bottom`、`scroll_end_bottom`、`scroll_end_gap_to_nav`）；
  3. 手機 📊 壓力態的 `risk_bottom_at_scroll_end` −639.9 → −838.9（差 −199.0px＝新區塊 198.7px；該欄量的是「捲到頁尾時風險區塊底緣相對視窗」，頁尾多一個區塊所以風險區塊被推得更高，屬預期的尾端量測欄變化，無對應門檻失敗）。

  依既有程序以兩版 Streamlit 真重產這兩份 Real JSON 並一併入庫（未手改；`meta.git_sha` 為量測當下的 HEAD＝base `2fd0773e`，`source_hash` 不變）。

## 限制（NOT VERIFIED）

Cloud 實際畫面、手機實機、Python 3.11（CI）與本沙箱 Python 3.13 差異、`loaded` 等覆寫組態對應的**真實**資料（沙箱無此資料）均未驗；本目錄只有沙箱 Chromium headless 的畫面。
