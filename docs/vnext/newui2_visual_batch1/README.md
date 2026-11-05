# New UI2 視覺完善 Batch 1 — 前後對照證據

- **基準 sha（before）**：`fb466d156e1003b0450053344934962007be07a4`（origin/main）；**after** ＝同 sha 上的未 commit 工作樹（`git_sha` meta 讀 HEAD，故兩邊 JSON 同為 `fb466d15`；差異以 `source_hash` 區分）。
- **環境**：Streamlit 1.59.2（截圖與主量測）、1.56.0（`viewport_measurements_streamlit156.json`）；Playwright 1.64.1；Chromium 153.0.8010.12 headless；theme＝`.streamlit/config.toml` dark base。
- **資料性質**：**全部為 FAKE scenario（`app_ui2.py` Preview；頁首 banner「示意資料（FAKE）」）**。圖中數字（12,345.67／VIX 12.34…）是示意，不是行情、持股或建議。**未擷取 Real-data feed 的截圖**（Real 僅做 11 態量測，見下）。
- **不宣稱 pixel parity**：原始四面板參考圖不在 repo（DEC-135／136 自陳圖片本體為對話附件，未上傳）；本批依據是 Wireframes §4.2／W-11（客戶 Q3 核准）與 Exec Spec §1／§4 的**文字**，不是逐像素比對。
- **emoji 字型缺失備註**：擷取環境的 Chromium 無彩色 emoji 字型，📊／🎯／💼／🚀／⬜／🔴 等符號在圖中可能呈現為方塊或缺字（before／after 皆同）；這是擷取環境限制，不代表產品畫面，真機字型未驗。
- 擷取指令（repo 既有工具）：`python -m tests.ui2_viewport.measure_viewport --out <dir> --shots all`；場景切換為 `?ui2_dev=1` 純 UI 操作，截圖時開發面隱藏。

## 內容

`before/`、`after/`：同檔名＝同頁、同寬（`mobile`＝390×844、`desktop`＝1440×900）、同場景。**只收錄有像素差異（>8/255 的像素存在）的 26 組，外加 1 組對照 `mobile_p4_hold_loaded`（修正 2 的手機版面不變證明，兩圖逐像素相同）**；其餘 37 張兩邊逐像素相同（或僅 ≤8/255 的渲染雜訊），未重複收錄。

| 修正 | 影響的圖 |
|---|---|
| 修正 1：chip 文字色（`.ui2-chip--positive/--warning/--danger`） | 凡有 Stale（⚠，warning）／Unavailable（🔴，danger）chip 的場景：`*_stale`、`*_unavailable`、`me_loaded_unavailable`（手機與桌機） |
| 修正 2：💼 持股桌機首屏（≥769px） | `desktop_p4_hold_*` 六個場景（cold／loaded／missing／stale／unavailable／not_evaluated） |

## 修正內容

1. **chip 文字色**（`src/ui2/shell/css.py`）：`#1a7f37→#3fb950`（對底 3.72→7.44；疊 tint 3.38→6.77）、`#b7791f→#d29922`（5.19→7.49；4.43→6.39）、`#c62828→#ff7b72`（3.36→7.49；3.14→7.00）。底色＝`.streamlit/config.toml` `#0e1117`；tint rgba 與 chip 尺寸不動。守衛 `tests/test_ui2_chip_contrast.py`（純 CSS 解析＋負向突變）。
   ⚠ 限制：新色只為深色底調整；若使用者手動切 Light theme，這三色對白底對比會下降（`.streamlit/config.toml` 固定 dark，Light 未驗）。
2. **💼 持股桌機首屏**（`html.py::hold_l1_html`／`page_title_html`、`views/hold.py`、`css.py` `.ui2-h-l1`）：標題＋第一屏放同一容器；桌機＝header 列（標題＋主 CTA「更新持股戰情」，仍 disabled）→ 三 tile（Risk Cap／目前曝險／組合狀態）→ 是否需要行動／下一步各一列。元件、欄位、字樣、`data-ui2-*` 錨點不增不減；手機只補回舊版兩個 Streamlit 元素容器之間的 16px 間距。守衛 `tests/test_ui2_hold_header.py`。

## 量測（`measure_viewport`，FAKE）

| 項目 | before（fb466d15） | after |
|---|---|---|
| FAKE 70 態（1.59.2） | 70/70 | 70/70 |
| FAKE 70 態（1.56.0） | （既有證據 70/70） | 70/70 |
| Real 11 態（1.59.2／1.56.0） | （既有證據 11/11） | 11/11／11/11 |
| 📊 手機 stale／unavailable 導覽餘裕（守衛 ≥160） | 181.6／162.5 | 181.6／162.5（逐位相同） |
| 💼 桌機三 tile 頂緣（loaded） | 單欄堆疊 | 三者同為 159.9（差 0px） |
| 💼 桌機主 CTA | 在卡尾（y≈430） | header 列 top 95.9、bottom 158.6（≤ tile 頂緣 159.9，不重疊） |
| 💼 手機 6 場景 | — | 與「只換 chip 色」基準逐像素比對：`hold_loaded` 0 個差異像素；其餘最多 1～3 個像素差 1/255（渲染雜訊，其他未改動頁面亦有同等雜訊） |

證據 JSON 已隨本批重生（`docs/vnext/newui2_batch3b/`、`docs/vnext/newui2_realfeed/` 各 1.59.2／1.56.0 兩份）：因 `tests/test_ui2_real_feed.py::test_dec137_evidence_meta_is_fresh` 要求 `meta.source_hash` 與現算相符；重生前後只有 `p4_hold`（FAKE 桌機 6 態、Real 桌機 1 態）的量測結果與 meta（`git_sha`／`source_hash`／`generated_at`）改變，其餘頁面結果一字不變。舊 PNG 未動。

## 未驗證

iOS Safari／Android 真機、Streamlit Cloud（含 Manage app）、Firefox／WebKit、Streamlit 1.56／1.59 以外版本、Real-data feed 的視覺截圖、Light theme、彩色 emoji 字型下的實際外觀、與原始參考圖的逐像素比對（無原圖）。

## 未做／未驗證（獨立 QA 後補註，2026-11-05；DEC-138）

**未做**：W-11 Primary 圖、⑤ 建議持股區間、持股表、header 的「組合名稱·資料日·判得出」行；今日需處理仍為兩列（非線框一行）；A2（👤 去重 CTA）判 B 未動。**維持 Dark-only，未新增 Light 支援**（Light 現無可達途徑；若可達，新三色疊 tint 後約 2.1～2.2 不合格，須停手回報）。另有 P3：三 tile／CTA 位置幾何守衛缺口（突變 3 欄改 2 欄仍綠）、CTA 變可用時須重評視覺與 DOM 順序。真機／Cloud／iOS／Firefox／WebKit／Real feed 視覺截圖／彩色 emoji 字型仍未驗。

### Visual Fidelity Gate 記錄
| 範圍 | 結果 |
|---|---|
| chip 對比（局部修正） | **PASS** |
| 💼 桌機 W-11 header／三 tile | **部分 PASS＋輕微偏離**（CTA 與 tile 間距 1.3px；缺資料日行；今日需處理兩列） |
| **整頁 Visual Fidelity** | **未達**：A2／V1 在 Primary 圖補上前**不 PASS** |
| pixel parity | **否**（非 pixel parity，無原圖） |

獨立 QA：0 FAIL，可合併；局部修正、非整頁完成。
