# 重構狀態看板(深層拔毒 v18.369+)

## 📈 2026-07-10 B8 健康度歷史 repo 快照 + A-2 批次抓取真平行（v19.77）

> user 拍板:B8 選「repo 快照 + cron」;A 類只做「批次抓取平行化」(K線快取試點/N+1 未選,不動)。

**B8 健康度走勢後端持久化**(原只存 session_state,App 重啟歸零,趨勢圖累積不起來):
- **cron script** `scripts/update_health_history.py`:對 `data_cache/health_watchlist.json` 清單逐檔 `get_combined_data(360)` → 同一組 L2 指標 → `calc_health_score` — **零新公式**(SSOT,shortage_cli 薄殼精神,單機分數與網頁保證一致)。寫 `data_cache/health_history.parquet`,**冪等** (date,sid) 重跑覆蓋;§2.3 PIT 鍵 = 該檔最後一根 K 的**交易日**(非執行日,連假重跑不重複)。§4.2 寫出前斷言 health∈[0,100]/close>0。meta json 記成功/失敗清單(§5)。
- **workflow** `.github/workflows/update_health_history.yml`:工作日 UTC 09:30 = TW 17:30(盤後 TWSE 17:00 資料齊,§4.5;對齊 update_macro_history 同時段慣例)+ 手動 dispatch(可指定代碼)。
- **L3 service** `src/services/health_history_service.py`:`load_health_history(sid, days)`(讀 parquet,檔缺/壞 → [] + log)+ `merge_score_history`(純函式:cron 底稿 + session 盤中即時點覆蓋同日)。路徑常數 repo-root 相對定位(對齊 fundamentals_snapshot_loader 模式),script 亦 import 同常數(路徑 SSOT)。
- **UI** `section_kline_chart`:score_hist 底稿改讀快照(L5→L3,合 §8.2 硬規則),快照缺 → 行為同舊(session 累積),§1 不造假。
- **watchlist 出廠為空**(§1 不腦補持股):填入代碼 commit 後功能才啟動;script 空清單顯式訊息 + exit 0 不 commit。

**A-2 批次抓取真平行**(`section_batch_fetcher`,review 點名):
- 原全域 Lock 串行保護「FinMind dl 非線程安全」→ K 線抓取實質序列(3 worker 名存實亡)。改 **thread-local loader**(每 worker 各持實例,無共享可變狀態 → 免鎖);`@st.cache_data` 鍵 (stock_id, days) 跨實例共享,快取效益不變;max_workers=3 維持(FinMind 禮貌上限)。
- 移除計算迴圈尾 0.2 秒固定 sleep(純本地計算段,I/O 已在 ThreadPool 完成,固定延遲無限流意義)— N 檔省 0.2×N 秒。
- **保守不動**:計算階段維持序列(CPU-bound,GIL 下 ThreadPool 無益;向量化屬大改另議)。

**驗證**:`tests/test_health_history_b8.py` 17 test(公式重用煙霧:多頭>空頭 / PIT 交易日鍵 / (date,sid) 冪等覆蓋 / §4.2 越界拒寫 / watchlist 三態 / service 讀取+同日覆蓋合併 / script main 全離線 e2e + 單檔炸不連坐 / A-2 源碼守衛 + thread-local 隔離行為)全綠;批次 provenance 12 test 無 regression;全套件全綠。

---

## 🩹 2026-07-10 CI 收官：RSS 雙後端契約統一（v19.76，main CI 最後 2 紅）

> v19.74 治綠後 CI run #428/#430 只剩 2 敗:`test_news_fetcher_coverage` 兩測寫的是 **ET 備援語意**,CI 有 feedparser(主路徑,寬容解析)行為不同必炸;本沙箱原裝不了 feedparser(sgmllib3k build 失敗)所以測不到,手動裝入後 1:1 重現。

- **production 修**:`rss_items_from_bytes` feedparser 主路徑補「無 title / 空 title 條目一律略過」(ET 備援本就如此;原樣回傳會讓空標題新聞流入下游渲染與關鍵字統計 — 真 bug,非只是測試紅)。
- **測試修**:`test_malformed_xml` 改後端相依契約 — feedparser 寬容解析殘缺 feed 為 feature(real-world RSS 常輕微 malformed,全丟=掉真新聞),ET 嚴格回 [];共同不變量:回 list、不 raise、無空 title。
- **驗證**:兩後端都跑(有 feedparser 16/16 + meta_path 遮蔽模擬 ET 備援 16/16);全套件 2,885 passed / 0 failed(沙箱補裝 feedparser 後與 CI 依賴面一致)。

---

## 🧰 2026-07-10 review B/D 類收斂：診斷盲區登錄 + pandera 阻擋 + cache 可攜（v19.75）

> user 核准「B+C+D 請繼續」(A 類大重構不動)。B=監控盲區、D=低 ROI 清理;C 類複查在 Fund 側記錄。

**B5 診斷盲區登錄 data_registry**(review:籌碼集中度/股本/現金流量比壞掉不亮紅):
- producer 端 meta stash(只存元資料不存 df 本體):`chip_radar` 寫 `chip_conc_meta`、`tab_stock` 寫 `t2_xsec_meta`;5年現金流量比率讀財報健檢**既有** `_fin_raw_{sid}` stash,零新 producer。
- `data_registry_scanner` 統一登錄 3 格:籌碼集中度(weekly,TDCC 週五更)/ 股本(quarterly,fetcher 失敗回 0.0 → missing 亮紅)/ 5年現金流量允當比率(yearly,status!=ok → missing)。只在 user 查過該股後登錄,避免固定清單膨脹。

**D13 月營收 pandera log-mode → blocking**(user 核准的資料政策變更):
- 新 `schemas.validate_or_reject()`:schema 違反 → **整檔棄用回空** + stderr log(§1 錯值比缺值危險;刻意不丟壞列 — 部分刪列會讓資料「看似完整」= 掩蓋)。pandera 未裝 → 放行(對齊 try_validate 語意),絕不 raise。
- `monthly_revenue_fetcher` 單檔+batch 兩處接線(batch 取首檔 36 列樣本,樣本違反 = 系統性 shape 問題 → 整批棄用)。
- **防誤殺**:revenue 先強轉 float64(FinMind JSON 整數營收會推成 int64,違反 schema float 契約 → blocking 整檔誤殺;Fund repo v19.172 FRED 同型教訓)。

**D14b cache 路徑可攜化**(review:/tmp/stock_cache 寫死,Windows 本機炸):
- 6 檔統一 `env STK_PKL_DIR 優先 + tempfile.gettempdir() 預設`(cache_layer/data_config/app_cache/leading_indicators/daily_data_fetchers/tab_macro)。Linux/Streamlit Cloud 結果不變(=/tmp/stock_cache),行為 0 變。
- ADL 除錯 log 路徑抽 `shared/cache_layer.ADL_LOG_PATH` SSOT(原 daily_data_fetchers 寫 + tab_macro 讀各自寫死字面值 = 跨檔隱性契約)。

**D14c 月營收無 token 靜默回空 → 補 log**(§5 可觀測性,診斷可分辨「無 token」vs「API 失敗」)。

**D 類不動項(維持並說明)**:三層快取 TTL(30min pkl/30min cache_data 外層 + 1h loader 內層)為刻意兩層設計非 bug;`data_loader` 減 `.copy()` 屬高風險 perf 重構;兩處配息 fetcher 用途不同(yfinance 年度 vs 4-fallback 明細)不強併。**B8 健康度走勢後端持久化**:涉存儲選型(GSheet / repo 快照 / tmp),§8.1 先提案待 user 拍板,未實作。

**驗證**:`tests/test_review_bcd_v19_75.py` 15 test(blocking 不誤殺 NaN 停業態/負營收整檔棄用/int64 強轉存活/no-token log/scanner 3 格登錄+missing/未查不登錄/可攜路徑源碼守衛+Linux 值不變)全綠;全套件無 regression。

---

## 🛠️ 2026-07-10 外部 code review P0/P1/P2 修正（v19.74）

> 使用者提交外部深度 code review 報告（dashboard_code_review.md），指示「根據建議修改，不適合的列清單」。逐項核對現行代碼後修 7 項，其餘列不修清單（詳 PR 描述）。

**P0-1 三大法人 BFI82U 欄位寫死**（`daily_data_fetchers.py`）:
- `row[3]` 寫死 → 抽 `_parse_bfi82u_rows(fields, data)` 純函式,買賣超欄用 fields 欄名「買賣差額/買賣超」定位（對齊同檔 MI_MARGN 既有模式）。TWSE 改版欄序位移時回 None + log,不再靜默回錯欄（§1 Fail Loud;原行為 isdigit 過 → 反向籌碼結論最危險）。

**P0-2 融資餘額 FinMind 區間猜單位**（`daily_data_fetchers.py`）:
- 廢除「億/元/千元/萬元」四分支數值區間猜測 → `_finmind_margin_to_yi()` 固定仟元÷1e5=億（FinMind 鏡射 TWSE MI_MARGN,單位固定仟元;同檔方案A 註解同源印證）。
- 新增 §3.2 sanity 區間 SSOT:`MARGIN_BALANCE_SANITY_MIN/MAX_YI`（500~10000 億,shared/signal_thresholds.py）,6 路 fallback 全走 `_margin_sanity_ok()`（原 inline `100<x<30_000` 過鬆,10× 誤判可穿過）。超區間 → log + 棄用改走下一 fallback。

**P0-3 goodinfo 快取鍵不可雜湊**（`tw_stock_data_fetcher.py`）:`fetch_goodinfo_metrics(proxies: dict)` → `_proxies`（@st.cache_data 略過底線參數;原簽章傳非 None 即 UnhashableParamError）。

**P1-1 連假強制重抓撞限流**（`app_stock_fetchers.py`）:價格快取容忍窗 5 → `PRICE_CACHE_HOLIDAY_TOLERANCE_CALENDAR_DAYS=14`（SSOT）。春節封關最長 13 日曆日（2025:1/21→2/3）,原 5 天窗連假期間每次冷啟動全檔強制重抓（拿到同樣舊資料,純燒 FinMind/yfinance 配額）。真新鮮度仍由 pkl 0.5h + cache_data 30min TTL 把關;gap>5 天沿用快取時 print 留跡（§5）。

**P2-1 MOPS fallback 零值假財報**（`tw_stock_data_fetcher.py`）:MOPS 長格式塞進 Goodinfo 寬表計算 → 全零 dict 餵下游誤判「財務崩壞」。加核心科目全零偵測 → 回 `{"error":"mops_parse_failed"}` 走 insufficient_data（對齊同檔 OCF=0 防禦）;`fuzzy_get_from_df` 補 `str(c)`（MOPS read_html 整數欄名原直接 TypeError）。

**P2-2 cache 無上界 OOM**:5 處以 stock_id 為鍵的 `@st.cache_data` 補 `max_entries=64`（data_loader `get_combined_data`/`get_monthly_revenue` + tw_stock_data_fetcher `_fetch`/`fetch_5_years_cash_flow`/`fetch_goodinfo_metrics`）。

**UI bug CSS 字面大括號**（`tab_stock.py:1087/1099/1111`）:f-string 內 `"{TRAFFIC_GREEN}18"` 寫在引號內不插值 → 渲染字面文字,獲利 5 卡背景/邊框色壞掉 → 改 `{TRAFFIC_GREEN if ok else TRAFFIC_RED}18`（對齊同段 1124 行既有正確寫法）。另移除 `tech_indicators.calc_bollinger` 恆真 `'bw' in dir()` dead code。

**驗證**:新增 `tests/test_review_fixes_v19_74.py` 18 測試（欄序位移/缺欄/單位錯 10×/邊界/全零偵測/源碼守衛）全綠;受影響套件（pr_n3/pr_n5/risk_radar/rs_leader/china 等 2,800+ 測試）無新增 regression。

**附帶:治綠 main CI（pr-check fast lane 自 7/3 起全紅,merge 前收拾）**:
- `test_china_macro_stock` 2 項:CHN_PMI → CHN_BCI 對齊 macro_core.py:241 v18.459 刻意改名（BSCICP03CNM665S = OECD Business Confidence 非 PMI）,測試原漏同步。
- `test_resample_audit` 1 項:v18.461 週K `'W'`→`'W-SUN'` 後 inventory 未重盤;擴 regex 捕 anchored alias + expected 更新,並依該測試 docstring 要求同步 CLAUDE.md §4.5 一行（W→W-SUN 註記）。
- **collection 全滅根因**（CI run #422 起 `Interrupted: errors during collection` exit 2,一個測試都沒跑）:`test_data_coverage`/`test_macro_classroom` 在**收集(import)階段**把 `sys.modules['streamlit']` 換成 stub(非 package),字母序在後的 `test_rs_leader_ui`(v19.70)+`test_macro_cross_ai_button_and_state`(v19.72)模組層 `from streamlit.testing.v1 import AppTest` 直接 ModuleNotFoundError。修法對齊同套件 `test_pe_river_merge_dtype`/`test_render_smoke` 既有慣例:AppTest e2e 測試歸 `@pytest.mark.slow` + 測試內 lazy import + setup 偵測不可用即 skip;按鈕名 source-scan 測試不需 AppTest,留 fast lane。（曾試「踢 stub 重載真 streamlit」免疫段,實測會翻掉其後 49 個依賴 stub 生態的測試 → 棄用,回歸 pe_river 模式。）
- 全部為「代碼是對的、測試過期/測試互相污染」方向,無 production 行為變更。既有「4 項 risk_radar 全套件連跑 order-dependent 失敗」(單獨執行全過,test-infra lazy-forward vs patch 目標歧異)為 main 既有議題,不在本 PR 範圍,已知悉待議。

---

## 🐛 2026-07-10 §十一 新聞：加獨立「📰 掃描新聞」按鈕（v19.73）

> 使用者回報「新聞這邊沒有任何讀取按鈕跟 ai」。查因：新聞 RSS 原本**只在按「🔒 執行 AI 裁決」時順便抓**（section_news_ai.py:64），且該鈕需 Gemini 金鑰 → 沒金鑰的人等於沒有能單獨載新聞的鈕，「新聞整體狀態」永遠「未掃描」。

- 加獨立 **「📰 掃描新聞」** 鈕（`btn_scan_news`）：只抓 RSS（`_fetch_macro_news`）、**免 Gemini 金鑰、不跑 AI**，寫入與 AI 裁決同一 stash key `_macro_news_items` → 上方「新聞整體狀態」燈號即更新。原「執行 AI 裁決」「清除報告」不動。
- 描述文案改標清楚：「📰 掃描新聞」只抓新聞（免金鑰）；「🔒 執行 AI 裁決」需 `GEMINI_API_KEY`。
- §8：純 L5 UI 加一鈕 + handler（mirror 既有 verdict handler 的 stash 機制）；無跨層/計算變動。
- 驗證：4 新測試（按鈕存在 / handler 抓 RSS 且不呼叫 gemini / AI 鈕未誤刪 / 模組編譯）+ 13 render smoke(slow) 無 regression 全綠。
- 註：AI 報告仍需**使用者自行**在 Streamlit Secrets 設 `GEMINI_API_KEY`（金鑰在 user 帳號，非程式可解）。

---

## 🐛 2026-07-10 §九 跨桶 AI：更新按鈕名對錯 + ①景氣位階 fail-loud（v19.72）

> 使用者截圖：②③④⑤總經卡都跑出真資料了，只有①「目前總經位階」還顯示「請點擊更新總經拼圖」，且**找不到那顆按鈕**。

**兩個真 bug**
1. **按鈕名不符（找不到按鈕）**：實際按鈕是 `tab_macro.py:144`「🚀 一鍵更新全部數據」，但多處佔位文字卻寫「更新總經拼圖」/「🔄 更新全部總經數據」— 指向不存在的按鈕名。6 處全改對：`section_cross_ai`(卡①預設 + 卡⑤預設)、`section_news_ai:178`、`app.py:532`、`macro_alert.py:360`、`macro_ui_components.py:163`。
2. **卡①誤導**：卡①需「外銷訂單 YoY 或 台灣 PMI/OECD CLI」才算得出景氣位階；此兩個 T3 來源（CIER/經濟部）本次抓取失敗，但卡①仍顯示「請點擊更新」（讓已更新的人困惑）。改 fail-loud（§1/§5）：偵測「其餘總經已載入（VIX/M1B/CPI 有值）卻缺這兩源」→ 顯示「景氣位階資料未就緒：缺外銷訂單+PMI，這兩來源本次抓取失敗（CIER/經濟部第三方網站暫不可用）」，講實情而非叫他再按更新。

**§8**：純 UI 文案 + 一段 render 判斷，無跨層/計算變動；6 處按鈕名收斂為同一正確字串（消除 divergent label）。
**驗證**：3 新測試（全 production 碼無殘留錯誤按鈕名的 guard / 卡①「已載入但缺源」顯示 fail-loud 診斷（復現截圖）/ 全空時指向正確按鈕）+ 14 macro render 相關測試無 regression 全綠。

---

## 📦 2026-07-10 基本面存活池：每季第二趟延遲補抓 + 涵蓋率診斷（v19.71）

> 使用者：「全台股每季重掃一次 OK，只是有些公司財報發布較慢，要怎樣確保都被抓到？」根因：cron 只在「截止+1週」抓一次，慢公布/展延申報者那趟抓不到，又不會回頭補 → 缺到下一季。

**A. 每季第二趟延遲補抓（真正解決）**
- `.github/workflows/update_fundamentals.yml` 加 4 條 cron（截止+約5週）：Q4→5/5、Q1→6/19、Q2→9/18、Q3→12/19。
- auto 模式 `latest_published_quarter` 判成同一季 → 重抓覆蓋同檔 parquet（腳本 §5 冪等已支援）；MOPS 彙總累加，晚交者這趟即補進。

**B. 涵蓋率診斷（§5 可觀測性，讓缺口看得見）**
- **script**：`_write_latest_json` 加 `_count_quarter`，把 `coverage{sii/otc/total/prev_total}` 寫進 `latest.json`（現有 115Q1 已回填：1,969＝上市1,078+上櫃891，去年同季1,934，保留原 updated_at）。
- **L0**：`SNAPSHOT_COVERAGE_WARN_RATIO=0.90`（本季 total < 去年同季 × 0.9 → 標「可能尚缺慢公布」，以去年同季自我參照，不硬編期望總數魔數）。
- **L3**：`describe_snapshot_coverage(meta)`（純函式，完整/偏低/舊版無 coverage 三態）+ `get_snapshot_coverage_note()`（快照缺 → 空字串不炸）。
- **L5**：選股網初篩面板 + RS 抗跌掃描 + 缺貨掃描 caption 都顯示「📦 存活池快照：民國115Q1 涵蓋 1,969 檔…每季兩趟抓取確保慢公布納入」；偏低時初篩面板轉 st.warning。

**§8**：script(L1 cron) + L0 常數 + L3 純 helper + L5 三處 caption，無跨層違規；covers 為 schema-additive（舊 caller 無感）。
**驗證**：10 新測試（_count_quarter / _write_latest_json 寫 coverage / describe 三態 + 比例邊界 / get_note fail-safe）+ 127 相關既有測試（RS/缺貨/初篩/loader）無 regression 全綠。

---

## 🛡️ 2026-07-10 抗跌 / 逆勢贏大盤選股（大盤下跌時仍贏過大盤的 RS 前 50）（v19.70）

> 使用者要「大盤下跌時（例如 2020 疫情）仍贏過大盤(RS)的前 50 名個股」。§7/§8 對齊後選「兩者都要（先即時）」+「免費基本面存活池 ~324 檔」。**Phase 1 = 即時模式**（歷史視窗模式為 Phase 2，待接）。

**計分口徑（σ 標準化超額報酬 = Mansfield 式）**
- 個股區間報酬 − 大盤(^TWII)同期報酬 = 超額（>0＝贏過大盤）；再 ÷ 大盤日報酬σ → **RS(σ)**；依 RS 降冪取前 50。
- ⚠️ 刻意**不用**官方 SSOT `calc_rs_score` 的比值法（`r_i/|r_m|` 在大盤負報酬時語意失真），改沿用 `v5_modules.calc_relative_strength`（逆勢強股語意）。
- **分級**：🔴 逆勢強股(≥+1σ)｜🟡 偏強抗跌(≥+0.3σ)｜⚪ 同步(−0.3~0.3)｜🟢 落後(<−0.3σ)。

**分層（沿用缺貨選股同一套，不重造）**
- **L0** `shared/signal_thresholds.py` 補 `RS_SIGMA_LEAD_MIN/MILD_MIN/LAG_MAX`（1.0/0.3/−0.3，**收 v5_modules 3 處 inline 魔數** → §3.3）；`calc_relative_strength` 改 import + schema-additive 回 `avg_stock_ret/avg_market_ret`（顯示用）。新 `shared/rs_screen_thresholds.py`（top50 / lookback 預設 / 分級標籤 / 掃描上限）。
- **L2** `src/compute/screener/rs_leader_screener.py`（純函式）：個股/大盤**日曆日對齊**（tz 統一：yfinance 個股 tz-aware vs fetch_yf_close 大盤 tz-naive，同 VIX/3M 教訓）→ reuse σ 公式 → 排序取前 50。
- **L1 重用**：`fetch_stock_history_1y`（threaded，無 st.cache）+ `fetch_yf_close('^TWII')` + `get_survivor_ids`。
- **L3** `src/services/rs_leader_service.py`：存活池 → 並行抓價 → L2 排名 + **市場漲/跌情境判定**（大盤在漲時明示「抗跌語意不成立」）+ §5 診斷；`build_rs_ai_prompt` 三型。
- **L5** `src/ui/tabs/rs_leader_ui.py`（lookback 選擇 20/60/120 + 只留贏過大盤 + 排行表 + 情境橫幅 + 誠實揭露 + AI 三型按鈕）；app.py 選股網加 expander「🛡️ 抗跌 / 逆勢贏大盤選股（RS 前 50）」。

**§1 fail-loud**：大盤抓不到 / 存活池空 / 全資料不足 → 回空 + 精準 note，不炸不造假。**誠實揭露**：只掃免費存活池（非全上市）、相對強弱非買點、已收盤日線、大盤漲時抗跌語意不成立。
**驗證**：39 新測試（L2 15 + L3 9 + L5 AppTest 2，含 tz-aware 對齊 / 市場漲跌橫幅 / SSOT 邊界 / fail-loud）+ 缺貨/render smoke 無 regression 全綠。

---

## 🐛 2026-07-10 VIX/VIX3M 期限結構「對齊後不足 2 筆」修（v19.69）

> 使用者截圖:短線風險雷達「VIX/3M」卡片顯示「⬜ 無資料 / VIX/VIX3M 對齊後不足 2 筆」,label 為 `Yahoo ^VIX / Yahoo ^VIX3M`（兩源皆非空卻對不上）。

**真 bug**:`risk_radar._signal_vix_term_struct` 用 Yahoo **原始 timestamp**（含時分秒、非午夜）直接 `concat(axis=1).dropna()`。同市場日線本該以「日曆日」為對齊鍵,但 ^VIX 與 ^VIX3M 常各停在不同 intraday 時刻（或 VIX3M 走 CBOE 備援 = 00:00 date-only）→ 秒級不等 → `dropna()` **全清空** → 誤報「對齊後不足 2 筆」。

- 修:兩支收盤 series 先 `pd.to_datetime(idx).normalize()` 到日曆日 + `~duplicated(keep='last')`（同日多筆取最後）再 join;`concat(..., sort=True)` 明確時序（消 Pandas4 warning）。
- §5 可觀測性:對齊後**真的**無重疊時,note 改攤開「VIX 至 YYYY-MM-DD／VIX3M 至 YYYY-MM-DD，源疑停更」而非只丟「不足 2 筆」,供資料診斷判讀。
- §8:單一 L2 純函式 bug fix,無跨層/介面變動。
- 驗證:78 risk_radar 測試（+3 新:intraday 時間戳不同仍對齊 / Yahoo 盤中戳 × CBOE 00:00 對齊 / 真無重疊時攤開最後日期）全綠。

---

## 🐛 2026-07-09 缺貨掃描「一檔都抓不到」修:免費版財報 dataset 無 s + 診斷（v19.68）

> 使用者實測:掃描全跳「存活池深掃後無可評分」,一檔都不剩。

**真 bug**:`fetch_quarterly_shortage_frame` 抓損益表只試 `TaiwanStockFinancialStatements`(有 s,付費版)。**免費/backer 版 dataset 名是 `TaiwanStockFinancialStatement`(無 s)** → 免費方案每檔回 0 季 → 全部「資料不足」。(既有 `data_loader.get_quarterly_data:1068` 早就兩個都試,新 fetcher 漏了。)

- 修:抽 `_finmind_rows_first(datasets, ...)` helper,損益表**無 s 優先、有 s 備援**兩個都試(對齊既有慣例);資產負債表加 try/except。
- 診斷(§5 可觀測性):`_score_and_diagnose` + `_diagnose`——無可評分時 note 攤開「資料不足 N 檔（其中 M 檔 FinMind 回 0 季 → 指向方案權限/配額,非程式 bug）、金融股 K 檔」,不再只丟一句「缺科目」。
- 驗證:46 缺貨測試(+2:免費版無 s dataset 路徑 / diagnose 攤 0 季原因)全綠。

---

## 🖥️ 2026-07-09 缺貨選股單機 CLI（scripts/shortage_cli.py）（v19.67）

> 使用者要一支「跟 dashboard 完全一致」的單機 CLI（他處 AI 產的獨立腳本有 3 個雷:revenue_percentage 當 YoY / 原始營收判遞增 / 缺科目填 0）。

- `scripts/shortage_cli.py`:**薄殼 driver**,直接 import dashboard 的 L1 抓取器（`fetch_quarterly_shortage_frame` + `fetch_monthly_revenue`）+ L2 計分（`rank_shortage` / `score_shortage`）+ `compute_yoy_mom`,**不重寫任何公式/門檻**（SSOT）→ 單機與網頁分數保證一致。修掉那 3 個雷（自算 YoY、判 YoY 加速、缺科目 None 不填 0）。
- 用法:`export FINMIND_TOKEN=xxx; python scripts/shortage_cli.py 2330 2317`；支援 `--file 清單.txt` / `--json`。金融股(28/58)不抓省額度;抓不到顯式標「資料不足/無科目」不造假。
- §8.2:歸 `scripts/` 維運 CLI,只 I/O + 呼叫既有 L1/L2,無自有計算。
- 驗證:9 CLI 測試(format/JSON/輸入組裝/金融股略抓/main 流程/no-token)+ 既有 35 缺貨測試全綠;實跑 entry point(no-token 提示 / dummy token → fail-loud 資料不足,不 crash)。

---

## 🔧 2026-07-09 缺貨選股：候選池相容免費 FinMind + AI 三型建議報告（v19.66）

> 使用者實測回報「finmind token 沒有」+ 截圖:側邊欄 FinMind ✅ 但缺貨掃描報「月營收全市場資料無法取得」。

**真 bug 診斷（不是 token）**
- app.py:89/92-93 已把 `st.secrets` 的 token 推進 `os.environ`,抓取器讀得到（側邊欄 ✅ 正確）。
- 真正失敗是候選池用的**「全市場月營收批次（不帶 data_id）」需 FinMind sponsor tier**,免費/backer 方案不支援 → 回空 → 原錯誤訊息誤標「token/quota?」。

**修法:候選池改「基本面存活池」優先（相容免費方案）**
- L3 `shortage_screener_service`:候選池**①優先用選股網那份免費離線基本面存活池**（`get_survivor_ids`,四項全過,你的環境確定能跑）→ 逐檔**單股**（data_id,低 tier 也支援）抓月營收 + 合約負債/毛利/存貨;**②僅存活池空時才 fallback** 需 sponsor 的全市場月營收批次。錯誤訊息改精準（區分「快照為空」vs「批次需 sponsor」）。
- 沿用 L1:`fetch_quarterly_shortage_frame`（季報）+ `fetch_monthly_revenue`（單股月營收,補 C4 的 YoY）。

**AI 三型建議報告（積極 / 穩健 / 保守）**
- L3 `build_shortage_ai_prompt(rows, top_n, news_text)` 純函式:缺貨排行 → 3 章節（排行/強弱分布/模型限制誠實揭露）+ 三型 overall_question → 重用 `build_structured_summary_prompt`（同個股 AI 報告元件）。
- L5 缺貨面板加「🤖 生成缺貨股 AI 三型建議報告」按鈕（app.py 傳 `gemini_call`）;best-effort 抓相關新聞;結果 session_state 快取。

**驗證**:35 缺貨測試（+3 新:survivor 路徑 / batch fallback / AI prompt）全綠;191 相關既有測試無 regression;Streamlit AppTest 實跑 render + 點 AI 按鈕產出報告無 crash。

---

## 🔥 2026-07-09 缺貨 / 供不應求選股（全市場掃描 + 四訊號計分）（v19.65）

> 使用者要「找到有缺貨的股票」,並貼了一份他處 AI 產的單股腳本。盤點後發現 dashboard 已有 8 成積木,
> 那份範例反而踩 3 條憲法紅線(補 0 造假 / inline 魔數 / 直接接 FinMind SDK 繞過分層)。改照本專案分層重做。

**四訊號計分（滿分 100）→ 🟥強 / 🟧中 / ⬜不明顯**
- ① 合約負債大增(35) ② 毛利率走揚(25) ③ 存貨週轉天數下降(20) ④ 月營收 YoY 連續成長(20)
- L0 `shared/shortage_screen_thresholds.py`:只放**新語意常數**(四權重 35/25/20/20 + 分級 65/40 + 月營收門檻 15 + 深掃上限 50 + DIO 年化 365)。訊號邊界值(CL YoY 15/30、QoQ 20)**重用** `signal_thresholds.py` 既有 SSOT,不重複定義。
- L2 `src/compute/screener/shortage_screener.py`(純函式):吃已對齊季度序列 + 月營收 YoY → 四訊號計分 + 分級 + 理由。DIO＝存貨 ÷(近 4 季成本 ÷ 365)年化(比範例單季 ×90 準)。**無合約負債科目 → 0 分並降級**(不補 0、不當壞事);金融股(28/58)不適用;不足 5 季標資料不足。絕不拋。
- L1 `src/data/stock/quarterly_financials_fetcher.py`:一次抓齊損益(營收/毛利/成本)+ 資產負債(合約負債/存貨),對齊成季度 frame。毛利缺→用營收−成本補(同 data_loader.py:2106,非造假)。EX-CACHE-1。
- L3 `src/services/shortage_screener_service.py`:**兩段式掃描**——全市場月營收 batch 圈「動能向上」候選池 → 深掃前 50 檔 → 呼叫 L2 排序。TTL_1DAY 快取。
- L5 `src/ui/tabs/shortage_screener_ui.py` + 選股網加 collapsed expander「🔥 缺貨/供不應求選股」(點按鈕才打 FinMind)。ProgressColumn 排行 + 白話計分規則 + **誠實揭露**(兩段式會漏極早期標的、財報 45 天延遲屬事後驗證、非買賣建議)。

**驗證**:32 新測試全綠(L2 計分各級距 + 邊界:空/不足/金融股/無合約負債/除零/garbage;L1 解析;L3 候選池+端到端)+ 188 相關既有測試無 regression;Streamlit AppTest 實跑 render 路徑(4 metrics + dataframe + column_config 無 crash)。

---

## 🟢 2026-07-05(下午) ETF 多檔「留/觀察/換」建議 + ETF 組合「每月配息明細」+ §4.1 混幣修（v19.64）

> 使用者兩個截圖回饋:①多檔比較「看不出哪些留哪些賣」②ETF 組合想看每月月配息(參考基金面板)。

**① ETF 多檔比較加「🚦 留/觀察/換」建議欄（PR 本批）**
- L0 `shared/etf_recommendation_thresholds.py`(留 0.65↑/換 0.35↓ 切點 + σ位階 ±1 加碼時機 + 同類重疊門檻 SSOT)。
- L2 `src/compute/etf/etf_recommendation.py`(純函式):`recommend_etf_actions(rows)` 讀既有分數(綜合分/流動性/配息健康/估值/σ)→ 留/觀察/換 + 紅旗降級(流動性🔴/吃本金🔴)+ **同類重疊偵測**(同類≥2 檔留分數最高、其餘擇一)。不重算指標。
- L5 `etf_tab_grp_compare.py` 加「🚦 建議」+「建議理由」兩欄 + 白話 st.info 說明。14 測試。

**② ETF 組合加「📅 每月配息明細（ETF × 12 月）」（PR 本批）**
- 基金面板(截圖 TLZF9/JFZN3)**不在本 repo**(那是共同基金,本 app 純 ETF)→ 照其精神用 ETF 積木自組。
- L0 `shared/dividend_frequency.py`(配息次數→月配/雙月配/季配/半年配/年配 門檻 SSOT)。
- L2 `src/compute/etf/etf_dividend_schedule.py`(純函式):`build_monthly_dividend_rows(holdings, usdtwd_rate)` → ETF×月矩陣 + 頻率 + 幣別 + 年合計。
- L5 `etf_tab_portfolio.py` 配息日曆段:新增每月明細矩陣(頻率/幣別/配息月份/1~12月/年合計+組合合計列)。15 測試。
- **§4.1 混幣 bug 修**:原碼把美元 ETF(BND)配息「當台幣」直接加進組合年現金流/殖利率/月度圖。改抓 USD/TWD(TWD=X)換算;抓不到→該檔標⚠️未換匯、不計入 TWD 總額(§1 fail loud)。全台股組合數值不變。

**驗證**:29 新測試全綠 + 347 ETF 測試無 regression;UI 矩陣塊實跑合成混幣資料(BND 換匯 3840、組合合計 5700 正確)。

---

## 🚀 2026-07-05 全台股基本面選股網完工 + 投資框架四層強化 + OAuth 修（v18.472→v19.63）

> 使用者一路回饋，本 session 交付：Phase 2 選股網、投資框架四層改進、多個實測 bug 修。

**A. 全台股基本面選股網（Phase 2 完工，PR #473~479）**
- 季快照 cron 改「公布截止 +1 週」自動每季重抓（4/7、5/22、8/21、11/21）；批次多抓去年同季供三率三升 YoY；`--season` 支援逗號分隔多季回補；MOPS fetcher 加重試+退避、3xx 轉址診斷。
- 後端 L0→L3：`shared/fundamental_prescreen_thresholds.py`（門檻 SSOT）+ `src/compute/screener/fundamental_prescreen.py`（L2 純函式 4 項）+ `src/data/stock/fundamentals_snapshot_loader.py`（L1）+ `src/services/fundamental_screener_service.py`（L3 + `gate_pool_by_fundamentals`）。
- 選股網入口從「估值前50」→ **全台股四項全過（負債比<50%/三率三升YoY/淨流動值>0/EPS>0）漏斗**（實測 1969→324 檔）；`tab_stock_picker` 加「自訂必過條件」15 項打勾 + 至少過 N；修「一動就消失要重按」（session_state 已跑過旗標）。

**B. 投資框架四層強化（框架討論後，PR #481~486）**
- **總經油門**：`shared/position_throttle.py` 健康分→建議持股區間（姿態非開關）+ regime 否決；總經頁紅綠燈下方油門儀表。
- **選股追高警示**：`src/compute/strategy/overextension.py`（乖離>25%/RSI>70）；選股網 S2 加「位階(追高)」欄。
- **加碼三問**：`position_throttle.assess_add_gate`（σ≤-1 + 趨勢沒壞 + 總經沒防守）；個股「什麼時候買/賣」加卡。
- **分散度**：`price_corr_warn_label`（價格高度同向）+ `_downside_corr_series`（空頭相關/危機失效）警示。
- **ETF 組合**：`src/compute/etf/portfolio_coherence.py` 股債比 + 總經一致性 + 核心/衛星拆解。

**C. 實測 bug 修**
- **OAuth 登入無限迴圈**（PR #484）：`oauth_state._oauth_state_ok` — session_state 在外部轉跳遺失時不再誤拒授權碼（仍擋真跨 session）。🚫 未寫死 secret、🚫 未關驗證。
- Google Sheet 讀取：診斷為「app 只認自己 `portfolios` schema / Sheets API 未開 / drive.file scope」→ 建議走「建立新 Sheet」；待使用者回報。

**未竟（使用者已知）**：ETF「平衡型/多資產」類別（TW 標的不足，WONTFIX）；工作分支刪除（環境 git proxy 403，需手動）。

**驗證**：本 session 新增 ~60 測試全綠（prescreen/loader/service/quarter/mops/picker/throttle/overextension/oauth/downside/coherence）。

---

## 🎨 2026-07-04 ETF UI 五連改（v18.467/468/469/470 + hotfix,使用者截圖回報）

- **v18.467**：ETF 三個智慧區塊(σ 買賣帶/分散度/MK 3-3-3)**去按鈕改自動計算**(輸入代號即算)、
  expander `expanded=True` 直接顯示;**AI 白話總結移到最下方**(單檔:`render_etf_single` 加
  `before_ai_hook` 於 AI 前呼叫;組合:`render_etf_ai` 移到 smart 之後)。
- **hotfix(PR #467)**：自動計算暴露 `build_holdings_set` KeyError 當機(對 DataFrame/dict 非
  預期格式 raise)→ 防彈化(list/DataFrame/dict/None 皆不 raise)+ 分散度迴圈 per-ETF try/except
  + `before_ai_hook()` 包 try/except(smart 出錯不拖垮整診斷)。另修 `update_fundamentals` workflow
  bs4 缺依賴(import mops_bulk_fetcher 觸發 stock `__init__` sibling eager import)→ 改
  `pip install -r requirements.txt`。
- **v18.468**：分散度分析改**按大類分組**(市值型/高股息/半導體/Smart Beta/債券,每類前 10)。
  L2 新增 `find_diversifiers_by_category`(純函式);UI 每類一張 bar chart + 明細 expander。
  ⚠️ 現有分類無「海外/平衡型」(使用者舉例),要加需擴充 `ETF_PEER_GROUPS`(待議)。
- **v18.469**：多檔 ETF 評分比較表補**標準差(σ)建議買賣價位 3 欄**(σ強買≤ μ−2σ / σ減碼≥ μ+2σ /
  σ位階)。`etf_tab_grp_compare._score_one_etf` 借用 L2 `compute_std_bands`(5y 價已抓),σ 算失敗 try/except 容錯。
- **v18.470**：`ETF_PEER_GROUPS` 分類**5 類 → 10 類**(全台股掛牌 ETF):新增 海外美股/海外陸股/
  原物料商品/不動產REITs/特別股(+ 債券補 00937B)。分散度分組自動多出這些類。48 不重複代號。
  ⚠️ 平衡型/多資產 TW-listed ETF 稀少,未建獨立類(標的不足)。原物料為期貨型('U' 後綴,yfinance
  可能無資料 → 抓不到自動略過)。

驗證:build_holdings 7 + diversifiers_by_category 4 + etf wiring + undefined-names 全綠;AppTest smoke;
compute_std_bands 回傳鍵實測正確。

---

## 🏗️ 2026-07-04 全台股基本面選股網（MOPS 路線）— 建置中（Phase 1a/1b 已上線）

> 使用者要求:選股網起始名單要涵蓋**全台股**(不是現在的上市 845 檔),用基本面篩選。
> POC 確認免費路線的天花板 + 資料源,分階段建。**此為跨 session 專案,進度記於此。**

### 可行性 POC 結論（GitHub Actions 實測，見 scripts/poc_*.py）
- **FinMind date-bulk 財報 = 免費 tier 不放行**（回 400「Your level is register」）→ 全 9 項免費 bulk 不可行。
- **MOPS 彙總報表可行**（免費、一次全市場、GitHub IP 不被 geo-block）:
  - 網域 `mopsov.twse.com.tw`(舊 `mops.twse.com.tw` 回錯誤頁)
  - `ajax_t163sb04` = **綜合損益表彙總**(營收/營業成本/毛利/營益/淨利/EPS)→ 三率#2 + 估值#4
  - `ajax_t163sb05` = **資產負債表彙總**(資產總計/負債總計/流動資產/權益總計)→ 負債比#1 + 淨值#8
  - POST `TYPEK`(sii/otc)+ `year`(民國)+ `season`(01-04);全市場(上市~1011/上櫃~740)
- **MOPS 只能 cover 4/9 項**(彙總表只有摘要欄;應收#5/存貨#6/CapEx#7/合約負債#9 需明細,MOPS 無)。
- **決策:兩層漏斗** — 第一層 MOPS bulk 全市場 4 項基本面初篩 → survivors 取代現在的估值 pool;
  第二層對小名單跑完整 9 項+籌碼+殖利率(per-stock,量少不爆 API)。

### 進度
- ✅ **Phase 1a**(PR #463):`src/data/stock/mops_bulk_fetcher.py`(L1)— fetch_mops_income_bulk /
  fetch_mops_balance_bulk + `_parse_mops_aggregate` 純函式(多產業表格、金融業缺欄容錯)。4 測綠。
- ✅ **Phase 1b**(PR #464):`scripts/update_fundamentals_snapshot.py` + `.github/workflows/update_fundamentals.yml`
  — 抓上市+上櫃存 `data_cache/fundamentals/*.parquet`(子目錄不受 gitignore)+ latest.json;
  季 cron + 手動觸發;`latest_published_quarter` 依公告截止日推季別。3 測綠。
- ⬜ **待做:實機驗證**(手動觸發 update_fundamentals workflow 抓真 MOPS + 產生首份快取)
- ⬜ **Phase 2**:L2 `fundamental_prescreen.py`(讀 parquet 算 4 項 → 全市場通過名單)
- ⬜ **Phase 3**:L3 service + 接選股網 UI(取代估值 pool)+ 降級 fallback

---

## 🎯 2026-07-04 v18.466 — 選股網漏斗式 + ETF 單檔診斷代號統一（使用者回報 2 bug）

> 使用者截圖回報：① 選股網入口是「殖利率前50」不是全市場基本面；② ETF 單檔診斷下方 3 個
> 智慧區塊各自帶獨立輸入框（顯示 0050），沒吃上方「開始診斷」的代號（00981）。經對齊採
> 「漏斗式（受 FinMind API 額度限制的折衷）」+「單檔 & 組合都改」。

### 修正一：選股網「漏斗式」— 殖利率不再當入口排序閘門
- `app.py`（選股網組裝）：入口由 `nlargest(50, 殖利率)` → 改 `nsmallest(PICKER_DEEP_SCAN_N, 本益比)`。
  全市場 → 基本面/估值初篩（排除虧損/PE>100/殖利率<2%或>12%）→ **依估值便宜度**取前 50 深跑三階段
  → 殖利率移到最後的「殖利率確認」欄位（`render_yield_confirm` 已在，方向本就正確）。`source_label`
  由「高殖利率前50」→「估值優選」。
- `src/ui/tabs/tab_stock_picker.py`：新增 SSOT 常數 `PICKER_S1_MIN_PASS=6`（基本面門檻由 5/9→**6/9**，
  使用者要求更嚴）、`PICKER_S2_MIN_PASS=3`、`PICKER_DEEP_SCAN_N=50`。通過門檻與 3 處 caption 全改用常數。
- ⚠️ 物理限制：三階段每檔 ~7 支 API（2 yfinance + 5 FinMind），全市場 845 檔即時深跑會爆 FinMind
  額度，故深掃檔數仍設上限（multiselect ≤30）。真「全台股跑基本面」需批次快取（未採，工程較大）。
  此為使用者確認的漏斗式折衷。

### 修正二：ETF 單檔診斷下方 3 區塊統一吃「上方那一個代號」
- `src/ui/etf/etf_tab_smart.py`：`render_std_band_section` / `render_correlation_finder` /
  `render_333_section` 三函式簽名改 `(ticker, key_suffix)`，**移除各自的獨立 ETF 代號 text_input**
  與失效的 `etf_g_active` fallback；無代號時 fail-loud 顯示提示（不再顯示假的 0050）。
  新增 `render_smart_ticker_input()`：組合頁專用單一共用輸入框（3 框收斂成 1 框）。
- `app.py`：單檔頁三區塊改吃 `session_state['etf_s_active']`（上方「開始診斷」代號）；組合頁（無單一
  主代號，`etf_p_active` 只是布林旗標）改用 `render_smart_ticker_input('_grp')` 一個共用輸入框驅動三區塊。
- 順手修：`etf_tab_smart.py` 補 `TYPE_CHECKING import pandas`，清掉 693004c 遺留的 `test_no_undefined_names`
  紅測（`"pd.DataFrame"` 字串註解 undefined name ×3）。

### 驗證
- 新增 `tests/test_etf_smart_ticker_wiring.py`（4 測）+ `tests/test_picker_funnel.py`（3 測），全綠。
- AppTest 實機 smoke：ticker=None 顯示 3 提示不炸；組合頁只剩 1 共用輸入框；exception=0。
- 全套件：`test_no_undefined_names` 由紅轉綠；本次改動零新增失敗。剩餘紅測 = 既有（china macro
  CHN_BCI ×2 + resample audit ×1，屬 v18.459 改名遺留）+ risk_radar ×3（網路/測試順序污染，單獨跑全過）。

---

## 🔍 2026-07-03 全面稽核待修清單（跨 Tab 稽核）

> Claude 逐檔讀取所有 Tab 後彙整，對照 2026-07-03 真實市場數值確認。
> 修完一項請在前面改為 ✅，並在括號內標版本號。

### 🔴 HIGH（影響判斷正確性）

- ✅ **[H1] VIX 雙重綠燈** (v18.459) — `src/data/macro/macro_core.py:518` `_sig_vix()`：VIX > 30 改為 ⚫「極端恐慌（逢低加碼訊號）」`#8b949e` 深灰色，與正常平靜 🟢 明確區分。

- ✅ **[H2] Bloomberg RSS 靜默死亡** (v18.459) — `src/data/news/news_fetcher.py:97`：移除 `feeds.bloomberg.com/markets/news.rss`，並更新 docstring。

- ✅ **[H3] Investing.com RSS 封鎖** (N/A) — 稽核確認 stock dashboard 的 `news_fetcher.py` **從未包含** Investing.com；此項僅存在於 Fund dashboard（已在 Fund 端修除）。

### 🟡 MEDIUM（資料品質或門檻偏差）

- ✅ **[M1] CHN_PMI 標籤錯誤** (v18.459) — 修正為 CHN_BCI：
  - `macro_core.py:241` key 名 `CHN_PMI` → `CHN_BCI`（加版本 comment）
  - `macro_helpers.py:800` `_CHINA_SUBSCORE_THRESHOLDS` key 同步更新
  - `classify_china_regime()` 的 reason 字串 `PMI=xx` → `BCI=xx`（兩端）
  - China Drag 面板 caption 加 `⚠️ BCI=OECD 商業信心指數(BSCICP03CNM665S,基準值 100 ≠ PMI 50 榮枯線)` 說明

- ✅ **[M2] USDTWD 顏色盲區** (WONTFIX-cosmetic) — 稽核確認 `MACRO_THRESHOLDS['USDTWD']` 在 stock dashboard **未被任何 signal 渲染程式讀取**（USDTWD 訊號走 `calc_twd_trend()` 斜率邏輯，不用絕對閾值）。此 dict 僅文件參考，30.5-32.0 盲區不影響實際 UI 輸出。`MACRO_THRESHOLDS` 的 F-GRAY-4 注解說明此特性，故無需修。

- ⬜ **[M3] ISM PMI 備援刻度衝突** (WONTFIX — 稽核確認 `fetch_ism_pmi()` 為 dead code，UI 未呼叫) — `macro_core.py:609`：Production UI 的 `ism_pmi` session_state key 實際由 `fetch_tw_pmi_block()` 填入台灣 PMI（14 處讀取點），`fetch_ism_pmi()` 僅在 tests 有 ref。OECD 備援顯示問題不存在於實際 UI。無需修改。

- ⬜ **[M4] AAII 情緒調查抓取脆弱** (WONTFIX — 稽核確認 stock dashboard **從未使用 AAII**，grep 全 src/ 無任何 aaii/AAII 字串，此項為誤植。無需修改。)

- ⬜ **[M5] FT RSS 需訂閱** (WONTFIX — 稽核確認 `src/data/news/news_fetcher.py` **從未包含** FT RSS URL，此項為誤植。無需修改。)

### ⚪ LOW（邊界設計或 UX 微調）

- ✅ **[L1] CBC_RATE 永遠卡邊界** (v18.460) — `macro_core.py:236`：`yellow_above: 2.0 → 2.125`，現行 2.0% 不再卡邊界，下一升息步幅為 2.125%。

- ✅ **[L2] USDCNY 門檻長期無綠** (v18.460) — `macro_core.py:244`：`green_below: 7.0→7.1 / yellow_above: 7.2→7.3 / red_above: 7.4→7.45`，對齊人民幣 2022 後 7.1~7.35 實際區間。

- ✅ **[L3] Yahoo Finance RSS 格式待驗** (v18.460) — `news_fetcher.py:94`：`https://finance.yahoo.com/news/rssindex` 實測確認 HTTP 200 + application/xml，格式正確。同批亦發現 **鉅亨網 CNYES RSS 已死亡**（`/rss/cat/headline` 重定向至 `/twstock/error.htm` 404），改換 **中央社財經 RSS**（`https://www.cna.com.tw/rssfeed/news/afe.aspx`，台灣官方通訊社）。

---

## 🚀 目前狀態(v18.462 — OAuth 搶帳號漏洞修復)

✅ **v18.462(2026-07-04)**:修復 OAuth 搶帳號漏洞（嚴格 state 驗證）:
- **根因**:`handle_oauth_callback()` 舊版在「本 session 無 `_oauth_state`」時退回放行，讓未啟動 OAuth 的分頁能接受別的 session 的授權碼。
- **修法**:`src/data/portfolio/oauth_state.py` — 改為嚴格版：只要 URL 帶了 state 就必須完全相符，否則一律略過。

---

## 🚀 前一狀態(v18.460 — LOW 稽核修正 + 綜合重新檢查)

✅ **v18.460(2026-07-03)**:LOW 稽核項目修正 + 全面重新確認:
- **[L1] CBC_RATE 邊界**：`MACRO_THRESHOLDS["CBC_RATE"] yellow_above: 2.0→2.125`，現行 2.0% 顯示🟢，避免邊界跳動。`src/data/macro/macro_core.py`
- **[L2] USDCNY 門檻**：`MACRO_THRESHOLDS["USDCNY"]` 三區更新：`green_below 7.0→7.1 / yellow_above 7.2→7.3 / red_above 7.4→7.45`，對齊人民幣 2022 後實際弱勢區間。`src/data/macro/macro_core.py`
- **[M4] AAII**：稽核確認 stock dashboard 從未使用 AAII（grep 無命中），WONTFIX。
- **[M5] FT RSS**：稽核確認 news_fetcher.py 從未包含 FT RSS URL，WONTFIX。
- **[L3] Yahoo Finance RSS + CNYES 死亡**：Yahoo Finance `news/rssindex` 實測 HTTP 200 確認正常 ✅；同批發現 CNYES 鉅亨 `/rss/cat/headline` 重定向 404 死亡 → 改換中央社財經 RSS `https://www.cna.com.tw/rssfeed/news/afe.aspx`。`src/data/news/news_fetcher.py`

## 🚀 前一狀態(v18.459 — HIGH/MEDIUM 稽核修正)

✅ **v18.459(2026-07-03)**:稽核項目修正:
- **[H1] VIX 雙重綠燈**：`_sig_vix()` VIX > 30 改 ⚫「極端恐慌（逢低加碼訊號）」深灰色，與平靜 🟢 明確區分。`src/data/macro/macro_core.py`
- **[H2] Bloomberg RSS 死亡**：移除 `feeds.bloomberg.com/markets/news.rss`，更新 docstring 來源列表。`src/data/news/news_fetcher.py`
- **[M1] CHN_PMI→CHN_BCI**：`MACRO_THRESHOLDS` key 重命名、`_CHINA_SUBSCORE_THRESHOLDS` key 重命名、`classify_china_regime()` reason 字串全改 BCI、China Drag 面板 caption 加 OECD 刻度說明。`macro_core.py` + `macro_helpers.py` + `ui/tabs/macro/helpers.py`
- **[M2] USDTWD 盲區**：稽核確認為文件參考 dict，不影響實際 UI（訊號走斜率邏輯）。WONTFIX。

## 🚀 前一狀態(v18.458 — 財報領先指標 capex 顯示修正)

✅ **v18.458(2026-07-03)**:財報領先指標 section 標籤與數據修正:
- **`section_financial_leading` 仍顯示 PP&E 存量標榜「資本支出」**:Task#20 修復了龍頭預警(dragon_alert)的比較邏輯，但同一個 `_capex2`(CF 季資本支出)未傳給財報領先指標 section，UI 仍用 PP&E 存量(cx2)且標籤顯示「資本支出」造成誤導。
- **修法**:`render_financial_leading_section` 新增 `capex=None` kw-only 參數；若 capex > 0 則優先以「季資本支出」顯示，cx2 PP&E 作 fallback(標籤改為「固定資產/資本支出」)。tab_stock.py 呼叫端加 `capex=_capex2`(與 dragon_alert 一致)。`section_financial_leading.py` + `tab_stock.py`

## 🚀 前一狀態(v18.457 — t2_inst 修 + Reuters RSS 移除 + 龍頭預警 capex 修 + MJ bootstrap)

✅ **v18.457(2026-07-03)**:Stock dashboard 4 項修復:
- **Task#18 `t2_inst` session key 從未寫入**:`section_kline_chart`(K線敘事「外資買超/賣超」)與 `section_health_score`(v4 籌碼 foreign_net/trust_net)讀 `st.session_state['t2_inst']` 但整個 tab_stock.py 從未寫這個 key → K線敘事恆用 `_fnet_f=0`(顯示「外資中性」)，v4 籌碼欄位恆為 0。修法：在 `_xsec` 計算後、各 section 渲染前，從 df2(已含 T86/TPEX 外資/投信欄，單位張)取最後一日寫入 `t2_inst`。`src/ui/tabs/tab_stock.py`
- **Task#19 Reuters RSS dead**:`news_fetcher.py` 移除 `feeds.reuters.com/reuters/businessNews`(dead since 2020-06),每次新聞抓取白費 timeout。`src/data/news/news_fetcher.py`
- **Task#20 龍頭預警「大擴廠」用 PP&E 存量(cx2)而非 capex(季流量)**:製造業 PP&E 存量動輒數倍股本，幾乎永遠觸發龍頭預警(假正例)。fetch_financials 本就同時抓 BS PP&E 和 CF 資本支出，但 `_capex2`(CF 資本支出)被丟棄未存入 t2_data。修法：t2_data 加 `capex` 欄，傳給 `render_dragon_alert_section`；龍頭預警優先用 CF capex 比較，PP&E 作 fallback(當 CF 資料取不到時)。`tab_stock.py` + `section_dragon_alert.py`
- (含 v18.455/v18.456)ETF 中文名 + MJ 季財報 bootstrap 同批推送

## 🚀 前一狀態(v18.456 — ETF 中文名 attempts=1 bug 修 + MJ 季財報 bootstrap 修)

✅ **v18.456(2026-07-03)**:MJ 季財報分 bootstrap 修:
- **MJ 季財報分恆為 0 根因**:`data_cache/mj_snapshots/` 在 Streamlit Cloud 為 ephemeral 存儲,重啟即清空,永遠湊不齊 2 季 snapshot → `compute_mj_trend_subscore` 回 `(0.0, {"reason": "insufficient_snapshots"})`。
- **解法**:在 `fetch_financial_statements` return dict 加 `prev_period_data` 欄位(用同一個 730 天 FinMind call 裡 `_dates[-2]` 的資料計算上季關鍵指標,約 50 行,無額外 API call)。`compute_one_stock_trend` 保存本季快照後,若 `len(yms) < 2` 則立即用 `prev_period_data` 呼叫 `analyze_financial_health("", sid, prev_period_data, "")` 補存上季快照。每次重啟後第一次抓財報就能湊足 2 季 → `mj_trend` 正常計算。`src/data/core/data_loader.py` + `src/compute/health/mj_trend_score.py`。

✅ **v18.455 補強（PR #455,2026-07-03，另一 session）**:上條 attempts=2 已修 MoneyDJ 路徑;本 PR **另加**兩項:
- **ETF 中文名多一路官方來源**:`fetch_etf_zh_name` 改以 **FinMind `TaiwanStockInfo.stock_name`（官方結構化中文名）為 PRIMARY**、MoneyDJ `<title>` 降 fallback。理由:FinMind 為結構化 API（同 dataset 的 `industry_category` 早已穩定運作），不依賴 HTML `<title>` 格式或 proxy-403 降級,兩路互為備援更穩。`_fetch_etf_zh_name_finmind` 新增於 `etf_fetch.py`;token 選填、讀 secrets 失敗不中斷。
- **Beta 缺值回歸估算**:yfinance `.info` 對台股主動式 ETF 常無 beta（單檔頁顯示 N/A）。新增 L2 純函式 `calc_beta(df, bench_df)`（cov/var,自身 vs 自動偵測基準 0050.TW,inner-join 對齊交易日,有效重疊 <60 交易日回 None）。單檔頁 yfinance 無 beta 時採用,help text 標明來源。測試 `test_etf_zh_name_and_beta.py`（+9）。SSOT/§8.2:calc_beta 為 L2 純函式無 I/O;FinMind 查詢沿用 `FINMIND_API_URL` SSOT;無跨層反向 import。
- ⚠️ **注意**:main 上 `test_china_macro_stock.py`（2 個）+ `test_resample_audit.py`（1 個）為紅 —— 係 v18.459 `CHN_PMI`→`CHN_BCI` rename 後測試未同步更新（與本 ETF PR 無關,屬 china macro 稽核批的收尾項）。

✅ **v18.455（2026-07-03，attempts=2 修）**:ETF 中文名抓不到根因確認並修復:
- **ETF 中文名仍顯示英文名**:web_fetch MoneyDJ 確認標題格式 `元大台灣50-0050.TW-ETF淨值表格 - MoneyDJ理財網` 完全符合既有 regex,**非格式問題**。真正根因是 `fetch_etf_zh_name` 呼叫 `fetch_url(attempts=1)`,而 proxy_helper 降級直連邏輯需 `_block >= 2` 才觸發(line 172),`attempts=1` 在第一次 403 時 break 出迴圈(`_block=1`,未達 2),直連路徑永遠到不了。`fetch_url` default 是 `attempts=3`;ETF 中文名有 7 天 cache,延遲可接受。改 `attempts=2` 即可讓 proxy-403→直連正確運作。`src/data/etf/etf_fetch.py:1968`。

✅ **v18.454(PR #453,2026-07-01)**:user 回報 4 項 production 問題,2 個獨立 agent 交叉驗證後逐一 root cause,3 項可修即修 + 2 項需 user 協助(誠實回報,不猜測):
- **總經頁「M1B-M2 資金動能」頂部燈號恆顯示「—」**(但下方「策略3」區塊正確顯示 -12.63%):`tw_macro.fetch_cbc_m1b_m2()` 本就算好 `gap`,但 `macro_snapshot.fetch_m1b_m2_block()` 重新打包 dict 時,CBC/FRED/IMF 三個 return 路徑全部漏帶 `'gap'` 鍵 → `session_state['m1b_m2_info']` 從未有此鍵 → `macro_helpers.py` 算頂部燈號/KPI 卡(依 `.get('gap')`)恆得 None → 顯示「—」;「策略3」區塊是自己內聯重算 `m1b_yoy-m2_yoy`(不依賴此鍵)才不受影響。補回三路徑 `gap` 欄(schema-additive)。守衛 `test_m1b_m2_gap_wiring.py`(+4)。
- **「個股」分頁整頁 MergeError 崩潰**(`incompatible merge keys dtype('<M8[s]') and dtype('<M8[us]')`,v18.440 per-tab 隔離器攔到不拖垮其他分頁):`section_357_valuation.py:333` PE 本益比河流圖 `merge_asof` 兩側日期精度不同 —— 股價側(data_loader `.dt.date` 物件經 `pd.to_datetime` → `datetime64[s]`)vs 季報側(FinMind 字串日期 `pd.to_datetime` → `datetime64[us]`),兩側從未顯式對齊精度。pandas merge_asof 要求兩側 key dtype 完全一致(含精度),不同即炸。兩側補 `.astype('datetime64[ns]')`。守衛 `test_pe_river_merge_dtype.py`(+4 純邏輯 + 1 slow AppTest)。
- **ETF 多檔比較表「1Y累積%」對年輕 ETF 顯示假 212%**(user 截圖 00981A 上市僅 13 個月):與 v18.452 `calc_cagr` 同源根因 —— `calc_total_return_1y` 只看「有沒有資料」不看「是否真橫跨 1 年」,年輕 ETF 的 `p_start` 實為上市首日低價而非真 365 天前價格。新增可選 `require_full_period`,資料跨度不足 365 天 90% 回 None(§1 寧缺勿假);兩 ETF UI 呼叫端(single/grp_compare)補齊 None 顯示 N/A。守衛併入 `test_etf_grp_compare_young_etf_fix.py`(+5)。
- **MJ 季財報分恆為 0**(待定):需連續 2 季 snapshot 才能算 delta,但 snapshot 存本機 `data_cache/mj_snapshots/`(.gitignore,Streamlit Cloud 重啟即清空),永遠湊不齊 2 季 → 架構決策(改存 GitHub / Google Sheets 等持久層),待 user 定奪。
- 測試 2520 pass(fast lane)。SSOT/§8.2:無新增 SSOT 常數 / 無新增例外 / 無跨層反向 import;M1B-M2 修復為「正確透傳 tw_macro 早已算好的 gap」而非消費端重算。

---

## 🗂 前一階段(v18.452→453 — 6 處 undefined-name 崩潰 + ETF 假資料 + 個股組合負債比不一致,PR #451 已 merge)

✅ **v18.452→453(PR #451,2026-07-01)**:user 回報「個股」「總經」「個股組合」三分頁陸續出錯 + 附完整 production log,逐一 root cause 確認全部同一根因(大檔案抽出成獨立模組時漏搬 import/變數):
- **ETF 多檔比較假資料**:名稱欄只用 yfinance shortName(常回發行商英文名,非商品名)→ 改用既有 SSOT `fetch_etf_zh_name()`(MoneyDJ 中文名,原本只有 etf_tab_single.py 在用)。`calc_cagr`/`calc_avg_yield` 新增可選 `expected_years`/`require_full_years` 嚴格模式:年輕 ETF(如上市僅 13 個月)資料跨度不足宣稱年期時回 `None`(§1 寧缺勿假),不再外推出「00981A 假 191% 3Y CAGR」這類不可能數字。兩參數皆預設維持舊行為。
- **6 處 undefined-name 崩潰**(用 pyflakes 全域靜態掃描一次找出,而非等 production log 逐一現形):`section_short.py`(總經 §5 短線急殺桶)缺 `TRAFFIC_GREEN/RED/YELLOW`/`os`/`plotly.graph_objects`/`BREADTH_BULL_PCT`/`BREADTH_NEUTRAL_PCT`/`add_danger_hlines` 共 8 處 import,ADL 資料一載入就 100% 全頁炸;`section_357_valuation.py`(個股 357 評價)結尾殘留一段完全重複且用未定義 `cheap2/fair2/dear2` 寫死的舊邏輯,直接刪除;`tab_stock_picker.py` 的 `_check_dividend_5y` 傳入未定義 `_t_yf`,導致「智慧選股」Stage 1/2 兩張表對任何股票都 100% NameError、整檔回退成全 ❓N/A(v18.374 抽 L1 fetcher 時漏改)—— 改用 `fetch_stock_history_1y` 已解析出的正確後綴建構真正的 `yfinance.Ticker`。另 2 處(`section_news_ai.py` 缺 `json`/`datetime`、`section_state.py` 缺 `pd`)尚未在 production 現形但屬同一顆未爆彈,一併清除。新增 `tests/test_no_undefined_names.py`(pyflakes 全域靜態守衛,CI 補裝),較功能測試更早、更全面攔截此類回歸;每個修復皆用 `git stash` 驗證「還原前程式碼 → 測試精準重現原始錯誤」。
- **個股組合負債比判定不一致**:盤點 3 張健檢表格(批次財報體檢/MJ趨勢分數/智慧選股)後確認唯一真衝突是負債比 ——「批次財報體檢」用 40/60% 三級門檻,「智慧選股」Stage 1 獨立重算卻只用 <50% 二分,同一檔股票兩處顯示不同顏色。三率三升等其餘欄位盤點後確認是水準 vs 趨勢的不同面向,非同一事實重複,故不強行合併;Stage 2 六項籌碼技術指標與 MJ 月營收分皆為獨有資訊,維持現狀(user 核准此範圍,§8 對齊後才動工)。修法:`_check_debt_ratio` 新增可選 `fh_result` 參數,個股組合場景直接沿用 `analyze_financial_health()` 已算好的判定(該版本另有負債比為 0 時的重算 fallback,品質更完整);無 `fh_result` 的呼叫端(高息網等)行為不變。
- 測試 2508 pass(fast lane)+ 新增 34 個測試(ETF 10 + undefined-name 守衛 7 + picker 17)。SSOT/§8.2 影響:無新增 SSOT 常數(沿用既有 `shared.colors`/`shared.signal_thresholds`/`analyze_financial_health`),無新增例外,無跨層反向 import。

---

✅ **v18.449**:市場廣度(市場廣度 chip)真值接線 + 頂部燈號 vs 五桶關係說明。user 質疑「五桶全紅但頂部仍顯示多頭」是否矛盾 —— 查證後**非 bug**,是設計上刻意分工(頂部=短期戰術訊號,只看 MA120 趨勢 + health;五桶=多時域風險分層,任一項亮紅即整桶紅)。但查證過程中意外發現真技術債:`market_strategy.market_regime()` 的 `ad_ratio`(市場廣度)參數預設 `1.0` + 門檻 `>1.0`,兩者恰好同值 → 此因子**從未真正生效過**,UI 上「❌ 市場廣度偏弱」永遠是同一個寫死值,且 `get_market_assessment()` 從未有這個參數可傳。user 明確要求「我都要真值+判斷過的」。修法:①改 `ad_ratio=None` 選填(同 `m1b_m2_gap` 慣例,未接真值前誠實不計分,不塞假中性值);② SSOT `MARKET_BREADTH_NEUTRAL_PCT=50.0`(0-100% 百分比尺度,對齊 `fetch_adl` 真實資料源與五桶 `adl` DangerSpec,修正原碼「比值尺度門檻套百分比資料源」的尺度錯誤);③ 打通 `tab_macro.py`(`df_adl_raw`,早就抓到手但從未傳出)→ `compute_and_apply_market_assessment`→ `get_market_assessment`→ `market_regime` 全鏈路;④ 修正 `max_score` 分母(原碼 5/6 恆虛高 1,因 ad_ratio 從未真正達標過)。頂部卡片新增 `st.caption` 說明兩組指標評估範疇不同。測試 +10(`test_market_strategy.py` 6 + `test_market_assessment_apply.py` 4)。全 suite 2548 passed。

✅ **v18.447(PR #446)**:總經分頁全頁炸 `NameError: name 'render_section_mid' is not defined`(v18.440 per-tab 隔離器攔到,其他分頁不受影響)。根因:`section_long.py` 結尾殘留一行 F-7.1 B-4 抽出 `section_mid.py` 時沒清乾淨的雜物呼叫,該檔從未 import 它。真正呼叫鏈已在 `tab_macro.py`(orchestrator)正確存在。修:刪雜物呼叫(不補 import,否則重複渲染兩次)。掃描全部 macro section 檔案排除另 2 個誤判(皆為 docstring 內文字)。守衛 `test_macro_section_render_wiring.py`。

✅ **v18.443→446(#442-445,4 輪疊代)**:ETF 折溢價 endpoint 三次猜錯 + user 親自用 Chrome DevTools 抓包才找到真相的完整過程 ——
- v18.443/444:猜測 `openapi.twse.com.tw/v1/ETF/TaiwanStock*`(其實是 FinMind dataset 命名慣例,TWSE OpenAPI 無此路徑,一路 404)+ 修正代理機制誤用(`nas_relay_fetch` 只認 FastAPI 中繼站 `NAS_BASE_URL`,user 實際設的是 Squid `PROXY_URL`)。
- v18.445:改猜 `mis.twse.com.tw/stock/etf_nav.jsp`(舊站改版前路徑,新站已無)。
- **user 親自用 DevTools Network 面板**打開官方頁面「ETF發行單位變動及預估淨值揭露專區」,抓到背後真正呼叫的 API:`mis.twse.com.tw/stock/data/all_etf.txt`,並展開 JSON 用 0050/0051 真實數值驗算欄位對映(`g == (e-f)/f×100` 皆吻合)。
- v18.446:接上正確 endpoint。仍抓不到值 → v18.448 追查發現兩個真根因:①`fetch_url(attempts=1)` 既有 bug(403 降級直連需連續 2 次,attempts=1 時第 1 次 403 直接放棄永遠到不了直連);②TWSE MIS 是舊式 Java/Tomcat 系統,瀏覽器實測請求帶 `JSESSIONID` cookie,暗示資料端點需要有效 session。改自建 `requests.Session()`:先 GET 揭露頁面暖身建立 session,再用同 session 取 `all_etf.txt`,「Squid 代理→直連」兩層明確 fallback。
- **教訓**:endpoint 存在性/欄位語意純靠網路搜尋猜測風險極高(v18.443/444/445 三次全錯);user 親自用瀏覽器 DevTools 反查才是唯一可靠方法,之後遇到類似「資料抓不到」問題應優先請 user 協助抓包,而非繼續猜。

---

✅ **v18.442(PR #440)**:ETF 折溢價對 0050.TW 又顯示假 **+5.07%「🔴 嚴禁追高」**(wantgoo 同日 -0.13%)—— 與 v18.441 **不同一條**:即時來源(yfinance navPrice / goodinfo)回「最後已公告淨值」被 `fetch_etf_nav_history` 硬戳 `_last_bd`(今日),0050 案該 NAV 實為 104.03(=06/29 過時值)被戳成 07/01 → 與當日市價 109.3 **同日** inner-join 成功、日期守門員 G1/G3 全過(**日期被造假成同日,擋不到**),算出假 +5.07%。原 G2 上限守門員(|prem|>2%)只對**主動式**生效,被動式 0050 漏接。修:新增 SSOT `PASSIVE_ETF_PREMIUM_MAX_PCT=3.0` + L2 `etf_premium_sanity_max(is_active)`,`calc_premium_discount` Path A/B/B2 上限守門員擴及全 ETF(超限回 stale + `stale_reason='nav_value_stale'`,UI 顯示「⏳ NAV 資料延遲」而非假溢價);近期淨值表同步過濾 |折溢價%|>上限的假列。守衛 `test_premium_stale_guard.py`(+3 case)。**誠實備註**:修後 0050 折溢價卡會顯示 N/A(NAV 來源給的是過時值),等 FinMind/TWSE 更新到同日才顯示真 -0.13% —— §1 寧缺勿假,不再拿過時 NAV 假配。

---

✅ **v18.438→441 production 修復連鎖**(2026-06-30,已全 merge 到 main;起因:v18.437 清碼 merge 觸發 Streamlit 重新部署,暴露一批**久未執行/未綁定**的渲染路徑潛伏 bug。逐一 fail-loud 修 + 補守衛測試):
- **v18.438(PR #435)**:ETF 單檔/組合分頁 `ImportError: cannot import name '_colored_box'` —— `render_etf_single/portfolio` late-import 互相從「對方 tab」拉 21+15 個 helper,但這些 helper 實在 `etf_render`(L4)/`etf_calc`(L2)/`etf_fetch`(L1)。改指向真 SSOT 來源,打斷 tab↔tab 循環。守衛 `test_etf_tab_imports.py`。
- **v18.439(PR #436)**:總經/個股/個股組合/教學 **4 分頁全空白** —— `94a257d`「chore(dead): 刪 4 個 0-caller dead fn」誤把 `with tab_X: render_tab_X()` 綁定當死碼刪掉(pre-existing,早於本 session)。還原綁定(tab 內 lazy import 免循環 + 免 F401 再刪)。守衛 `test_app_tab_wiring.py`。
- **v18.440(PR #437)**:教學分頁 `render_tab_edu` → `make_sparkline` 傳了已移除的 `high_is_bad/lookback` → TypeError **拖垮全頁**。對齊簽章(`list(_series)[-60:]`)+ **4 分頁 per-tab try/except 隔離**(`_render_tab_isolated`:單分頁錯只在該 tab st.error,不再拖垮全頁)。
- **v18.441(PR #438)**:ETF 折溢價對 0050.TW 顯示假 **+5.16%**(實際 -0.12%)—— `calc_premium_discount` Path B2 假日兜底拿過時 NAV(06/29≈104)配當日市價(07/01≈109.45)硬配。加「NAV 早於市價 ≥1 天 → stale」守衛(與 G1 同原則)+ 全路徑回 `nav_date`/`price_date`,UI 標「NAV 最新日 X｜市價日 Y」。守衛 `test_premium_stale_guard.py`。
- **SSOT / §8.2 檢查**:4 修全數過 —— 沿用既有 SSOT(`calc_premium_discount_pct` D4 / render/calc/fetch 真來源)、無新 inline magic、L5→L4/L2/L1 與 L6→L5 皆 downward、L1 fetcher 屬 EX-PASSTHRU-1、無新增反向 import。測試 **2514→2522 pass / 0 fail**。
- **教訓**:這批 bug 都是「分頁久未綁定渲染 → code 與 helper 簽章漂移 + 空測試覆蓋走不到」造成;已補 per-tab 隔離(單分頁錯不拖垮全頁)+ 3 支守衛測試釘綁定/簽章。

---

## 🗂 前一階段(v18.437 — 清碼/死碼深掃 + SSOT 收斂批次)

✅ **v18.437 清碼/死碼深掃 + SSOT 收斂**(2026-06-30,branch `claude/dazzling-turing-QxI9m`,8 commit 已推送,測試 2514 pass / 0 fail):
- **死碼**(`47629fe`):真死碼 3 處刪(`build_ai_data_table` 0-caller / `get_proxies` 被末尾別名遮蔽的無快取 def / scoring_engine 不可達 `WEIGHT_TABLES`)+ ~53 未用 import 機械清(ruff F401,以 F821 + 全測試交叉驗)。**翻案排除**:tab_stock/tab_macro 87 個 import(被 source-string SSOT 守衛 + except handler `ThreadPoolExecutor` NameError 防護綁定,機械清會 regression)+ `emoji_to_hex`(跨 repo auto-sync 檔,DO NOT EDIT)。
- **D1/D2/D4 計算層重複公式 → SSOT**(`af7da37`,+12 測試,數值等價驗證):布林帶寬(scoring_engine 走 `calc_bollinger_width_series`)/ z-score(`macro_core` + `multi_factor` → `shared.stats_helpers.zscore`)/ ETF 折溢價(etf_calc → `calc_premium_discount_pct` 委派 calc_bias_pct,不另抄)。v5_modules 布林**翻案不收**(upper/lower 為回傳值,走 series helper 反成雙重計算)。
- **D3 pkl 磁碟快取 → cache_layer SSOT**(`6b54763`):`fetch_single` + `fetch_flow_snapshot` 收(同檔 fetch_institutional 模式,inline 30 分 magic → TTL_30MIN)。`fetch_adl`/`build_leading_fast` **翻案不收**(自訂 _alog / PR-L2 stale-fallback 富快取,非簡單樣板)。
- **D6 provenance log → prov_log SSOT**(`f052415`):8 站手寫多行 stderr provenance print 收斂為 `prov_log()`。
- **D5 FinMind client 正規重構**(`69a462a`/`732e0f5`/`4ccd09a`,+8 測試,§8 user 核准):新增 `src/data/core/finmind_client.py`(L1 SSOT,零行為漂移設計)+ `leading_indicators.finmind_get` 改 thin re-export;遷 4 站 plain-requests GET。**深查翻案(最重要)**:audit 原報「~12 站重複」,實測剩 ~14 站「看似重複、語意實不同」— Proxy Session 站(帶 NAS Squid 代理 + Retry + verify=False,geo-block 繞道核心)+ HTTP-status-gating 站(gate on resp.status_code 而非 JSON status)暫遷後 **7 測試紅 → 全還原**,確認**不可機械收斂**,理由寫入 finmind_client docstring「適用範圍」防再誤報。

✅ **Phase 2 全完成**(2026-06-30 PR #429~#433 共 5 PR 合併,base v18.429)。
✅ **post-merge 連續批次**(2026-06-30,branch `claude/dazzling-turing-QxI9m`,未開 PR):
- **v18.430-432**:scoring_helpers:239 BW shrink SSOT 漏網 + EX-OAUTH-1 正式登錄 + SSOT-BB-MULTI 2-tier(布林近上軌 0.97 LOOSE / 0.995 STRICT)
- **v18.433-434 pandera POC**:P1 落地 3 hot-path fetcher(OHLCV/ETF/月營收)+ P2 補 PMI/ForeignFlow schema + P3 補 4 macro 時序(cpi/unemp/discount/usdtwd)log-mode 驗證
- **v18.434 S-PROV-1 收尾**:ETF 2 + macro 3 漏網 fetcher prov;個股 4 fetcher prov(其餘大批 audit 重盤後確認 pre-existing 已 prov)
- **v18.435 WONTFIX 翻案(深挖)**:S-MED 仍 0 真 bug,但 §8.3 灰色地帶深挖找出 4 個真 latent bug 並修:
  - cache_layer sentinel violation(合法 None 被當 miss)
  - daily_data_fetchers pickle.load file handle leak(無 with block)
  - app.py _gemini_rr round-robin race(讀+寫非 atomic → 加 Lock)
  - stock_names_fetcher _dynamic_cache rebind race(改 .clear()+.update() in-place)
- **v18.436 全做 audit(7 維度 + 對抗驗證,78 候選→32 survived)**:
  - C:8 inline magic SSOT 化(外資期貨防禦/VPOC/經理任期/FGMS 退路/KD/IBS/量比/547 回測)
  - #21:health_inspector「待補抓」空承諾 → 誠實導引手動更新
  - #23:calc_bias_pct_series series SSOT(etf_render inline 收斂)
  - #22/#20:doc 對齊(inst_sanity helper 已落地待 consumer / foreign_net 單位外部阻斷)
  - #25:false-positive(R1 wrapper 5/5 在用,分散 section 檔)

✅ **架構淨檢(v18.436 全域 audit)**:§8.2 分層違規維度 = **0**(除已登錄 EX-* 例外)。

### 殘餘待辦(全 LOW / 非阻斷,§-1 預設停手)
- 測試覆蓋:9 模組(v4_strategy_engine 等核心 + L1 fetcher)無獨立測試 — v18.436 補測批進行中
- pandera P3 長尾:30+ dict-return fetcher 無 tabular shape,維持 WONTFIX(無法套 DataFrame schema)
- foreign_net 啟用:待外部確認 FinMind buy/sell 單位(非程式項)

## 📊 累計度量(v18.429)

| 度量 | 值 |
|---|---|
| tab_macro.py LOC | 5387 → 488(**-91%**) |
| tab_stock.py LOC | 3672 → 1621(**-55.9%**) |
| tab_stock_grp.py LOC | 3673 → 303(**-91.8%**, Phase 2 Batch 7 全 5 子批) |
| app.py LOC | 7300 → 642(pure router + orchestrator)|
| Dead code 清除 | -666 LOC(ai_engine -654 + fuzzy_get -12)|
| §3.3 反捏造違憲 | 0 |
| §8.2 hard rule 違憲 | 0(grep 驗證:L1 import streamlit 全 EX-CACHE-1 letter compliant;L2 無 I/O;0 反向 import)|
| §8.2.A active 例外 | 3(EX-L0-1 / EX-CACHE-1 7 處 / EX-PASSTHRU-1 25+ 處)+ 2 退役(EX-AI-1 / EX-RENDER-1)|
| §4.3 重算對帳 | 3 / 3 落地(US10Y / 月營收 / 健康評分)|
| §5 SSOT 收斂 | 6 處 magic SSOT(Batch 5a 停損 + 5b 布林帶寬 2-tier);乖離 / RSI / MA / 健康評分 / FinMind URL / TWSE URL 等已全 SSOT |
| pytest | 2294 pass / 10 skip / 14 deselected |
| Phase 2 累計 PR | #429~#433(5 PR 全 merged)+ 早期 #398~#428(34 PR)= 39 PR |

## 📋 Phase 2 全 batch PR 清單(#429-#433,5 PR + 早期 #428 起算 6 PR)

| PR | 主題 | 主要結果 |
|---|---|---|
| #429 | Phase 2 Batch 1(R-CALC-3 乖離 + R-CALC-1 RSI 雙 SSOT)| 乖離 inline 8 處 → calc_bias_pct SSOT;RSI thin wrapper |
| #430 | Phase 2 Batch 2+3+4(R-UI-1 border-left + R-FETCH-1 股本 + R-CALC-2 MA scalar)| inline HTML SSOT;_fetch_share_capital UI→L1 搬移;safe_ma 5 子批 |
| #431 | Phase 2 Batch 6+10(健康評分對帳 production + FinMind URL SSOT 17/37)| §4.3 health reconcile embed in calc_traffic_light;首批 17 處 URL |
| #432 | Phase 2 A+B+C(Batch 10b URL 收尾 + Batch 8 三大法人 WONTFIX + Batch 7-1 起步)| 12 檔 FinMind URL 全集中;tab_stock_grp section 化 51 LOC 抽出 |
| #433 | **Phase 2 全 5 batch 收尾**:tab_stock_grp 拆檔 + L0 helper + L1 fetcher + magic SSOT | 18 commit,9 個 batch 累計:Batch 7-2~7-5(-1117 LOC)+ Batch 8.1(BFI82U URL)+ Batch 9/9-2(357 殖利率 SSOT)+ Phase 2 V1/V2/L0/R-UI-FETCH/D10/magic 全做 |

## 🏁 PR #433(v18.429,merged 2026-06-30 commit bbb282b)

### 累計成果

**檔案搬移 / 新建**:
- ✅ 5 個 stock_grp_sections/ 模組(market_status / batch_fetcher / portfolio_summary / financial_health / ai_portfolio)
- ✅ 2 個 L0 shared helper:`shared/etf_codes.py`(bare_etf_code)+ `shared/etf_universe.py`(REGIONAL_ETFS + CROSS_ASSET_ETFS + all_symbols)
- ✅ 2 個 L1 fetcher 遷層:`src/data/macro/foreign_flow_fetcher.py`(R-UI-FETCH-1)+ `src/data/stock/chip_concentration_fetcher.py`(R-UI-FETCH-2)
- ✅ 新增 2 個 SSOT 常數:`BB_BW_SHRINK_WARN_RATIO=0.7` + `BB_BW_SHRINK_ACTION_RATIO=0.6`(布林帶寬 2-tier)
- ✅ ARCHITECTURE.md 升 v9.2 + §0.11 audit findings doc

**架構違規收斂**:
- ✅ §8.2 L1→L2 反向 import 9 處全消除(bare_etf_code + all_symbols 下沉 L0)
- ✅ §8.2 EX-CACHE-1 letter compliance:etf_calc / etf_quality 補 try/except + _NoOpST
- ✅ §8.2 R-UI-FETCH-1/2 違憲消除(2 個 L1 fetcher 從 UI 抽出)
- ✅ D10 真重複消除(etf_render._teacher_conclusion 委派 ui_widgets SSOT)
- ✅ 6 處 magic number 收 SSOT(停損 0.92 → STOP_LOSS_PCT;布林帶寬 0.7/0.6 × 5)

**audit 翻案 WONTFIX(documented 證據)**:
- ⊘ Batch 5 月營收 3 路(endpoint 已 SSOT,wrapper 差異有理由)
- ⊘ Batch 8 三大法人 dispatcher 統一(4 路真不同 endpoint)
- ⊘ Batch 9 cross-file 個股 vs ETF 殖利率(公式真不同)
- ⊘ R-FETCH-4 配息 base(output format / fallback chain 差異大)
- ⊘ R-UI-1 51 處 border-left 殘留(全 multi-line bespoke shapes)
- ⊘ 停損 0.93 / 0.07 / 布林近上軌 0.995 / 0.97(各自單 use + 不同概念)

### Post-merge audit ✅ PASS

| 項目 | 結果 |
|---|---|
| §8.2 hard rule violations | **0** |
| L1→L2 / L2→L3 / L3→L4+ 反向 import | **0** |
| 新檔 foreign_flow / chip_concentration | EX-CACHE-1 letter compliant + S-PROV-1 phase 19 ✅ |
| etf_render._teacher_conclusion shim | 23 caller 確認 ✅ |
| L0 helper re-export shim | backward compat ✅(無 caller 改動需要)|
| SSOT 微缺口(audit 候選,非阻斷)| 3 處 — 詳見下方「未做的 minor 候選」|

### 未做的 minor SSOT 候選(audit 找到但未動工,非緊急)

| ID | 位置 | 內容 | 建議 |
|---|---|---|---|
| **SSOT-BB-MULTI** | tech_indicators.py:118(0.97)+ v4_strategy_engine.py:338(0.99)+ v5_modules.py:247(0.995)| 3 個布林近上軌 inline 不同精度,`BB_NEAR_UPPER_RATIO=0.97` SSOT 已存但未全 caller 引用 | 翻案 candidate:可能 3 個精度故意分流;或統一至 SSOT |
| **scoring_helpers:239 漏網** | `bb['bw'] < bb['bw_mean'] * 0.7` | Batch 5b 漏掃的第 6 處 BB_BW_SHRINK_WARN_RATIO candidate | 直接替換,3 LOC + 1 import |
| **oauth_state.py L1 直 import streamlit** | src/data/portfolio/oauth_state.py:25 | 已 documented (D4 v18.400 歸位)但未正式登錄成 §8.2.A EX-OAUTH-1 例外 | doc-only:CLAUDE.md §8.2.A 補例外行 |

## 📋 早期 session PR 清單(#398-#428,33 PR — 歷史保留)

| PR | 主題 | 主要結果 |
|---|---|---|
| #398-#409 | governance + Dead code audit 6 輪 + pandera POC + S-MED | -666 LOC dead;详见前版 STATE |
| #410-#428 | F-Q / R / D / C / U 系列(structural refactor 收尾)| tab_macro/stock 拆檔大量結案 |
| #429-#433 | **Phase 2 全 5 batch(本批)**| 見上方詳述 |

詳細歷史見下方各 PR 區塊。

## 🏁 PR #400 v18.395(merged 2026-06-29)

## 🏁 PR #400 v18.395(merged 2026-06-29)
**P5 Batch1:C1+C2 AppTest 实機驗 + B6 version pin + A4 archive 精簡**

接 user「同時做」隊列首批,LOW risk 3 件套:

### C1+C2 AppTest 实機驗
- 靜態 AST 守衛(已存在)+ runtime AppTest(新增 4 case)雙層守護
- panel test ✅ 通過 = PR #399 实機驗成功(無需 user 手動部署)
- News AI test 在無 secrets 環境自動 skip(production 必有)

### B6 version pin
14 套件加 major version upper bound,實機 env 0 conflicts(不降級 production)

### A4 §十 archive 精簡
- 18 LOC 復活註解 → `ARCHIVED_FEATURES.md`(新檔)
- tab_macro 留 1 行導向標記
- tab_macro:488 → 471 LOC(-17,-3.5%)

### 驗證
pytest 2214 pass / 0 fail / 36 deselected (slow);slow lane 11 pass / 2 skip

### Batch 2~5 隊列
- A5 pandera POC
- B3 app.py 拆檔 audit + 第一批
- B5 雙演算法對帳 × 3
- B4 daily_checklist pkl 收尾
- 改判 4 項(A3 macro_validation 真刪 / B1 etf_render cache.clear 抽 L3 /
  B2 EX-PASSTHRU-1 12+ 補登錄 / D1 S-MED 710 重 audit)

---


## 🏁 PR #399 v18.394(merged 2026-06-29)
**data_registry live state — Path C panel + SSOT 11 emoji category**

### 任務 #4 接續(C 為主 + B 的 SSOT 修法)
深挖發現 `session_state['data_registry']` 是 dead state(P1-X scanner + P3-D8 patch
寫 ~80 entries 但 0 reader)+ 3-way category SSOT 漂移。

- **SSOT 11 emoji 集中**:新檔 `shared/data_categories.py`(L0)
  - 11 CAT_* constants 對齊 static `src.data.core.data_registry`
  - `category_for(name, fallback)` + `coverage_emoji_for(cat)`
- **scanner / patch 對齊**:`data_registry_scanner` + `macro_registry_patch` 8 處
  inline `'大盤'/'個股'/'ETF'` 改 CAT_* 常數(rebuild fallback 5-set 檢查)
- **Path C panel**:新檔 `src/ui/pages/data_registry_panel.py`(177 LOC)
  - `compute_registry_groups` + `_freshness_emoji` 純函式易測
  - 按 11 emoji 分組 expander;🟢🟡🔴⬜ frequency-aware freshness lamp
  - `app.py:1522-1527` hook 進 🔎 資料診斷 tab(coverage 之後)
- **15 新測試**:`tests/test_data_registry_panel.py`(category SSOT + freshness +
  groups + 靜態守衛防 SSOT 再漂移)

### 驗證
- pytest 2214 pass / 0 fail / 32 deselected(slow)
- baseline 2199 + 15 新測 = 2214,無回歸
- 留 user merge 後在 🔎 資料診斷 tab 看新 panel 实機

### Streamlit 实機未驗(留 user)
PR merge 後在 deployed app 點 🌐 總經 → 🚀 一鍵更新 → 切到 🔎 資料診斷
→ 看 ⓪ 4-row coverage 之後出現「📋 資料源完整清單」panel 渲染 50+ entries
按 SSOT 11 emoji category 分組。

---


## 🏁 PR #398 v18.393(merged 2026-06-29)
**深挖第三輪:1 真 bug + 1 大塊真不可抽 + 例外清單收齊**(3 件套)

### P0-FIX(真 bug)
- `tab_macro.py:749` `render_section_news_ai(_macro_info, ...)` `_macro_info` 從 D-12 後未定義
  → 走入 §十一 News AI 100% NameError 全頁炸
- 修:L749 前補 `_macro_info = st.session_state.get('macro_info') or {}`
- 新增 AST 守衛 `test_render_section_news_ai_args_defined_in_scope` 防同類再犯
- pytest 2220 case 全是 source-string assert,5 個 commit (B-4 → D-13) 沒抓到

### P1-X(真不可抽 第三次誤判 — 275 LOC 完全可抽)
- `tab_macro.py:373-647` inline DataRegistry 區塊(2 inner def + 8 for 迴圈掃 12 session_state key)
- 抽 `src/services/data_registry_scanner.py`(324 LOC)
  - `scan_and_write_data_registry(*, intl_map, tw_map, tech_map) -> None`
  - 8 phase:大盤(INTL/TW/TECH/ADL) → 籌碼 → 旌旗/乖離 → M1B/M2 → 6 宏觀 → LI 5 細項 → 個股+比較 → ETF 3 細項
- 對齊 macro_registry_patch / macro_fetch_orchestrator DI 風格
- tab_macro.py:**751 → 488 LOC(-263)**

### P2-EX(§8.2.A 例外收齊)
- **5 L1 letter-compliant**(原無條件 import streamlit 軟例外 → 補 try/except + `_NoOpST` fallback):
  etf_fetch / leading_indicators / yf_proxy / data_loader / tw_stock_data_fetcher
  fallback 含 cache_data / cache_resource / **secrets**(P2 新增屬性)三屬性
- **CLAUDE.md §8.2.A 表更新**:
  - EX-CACHE-1:列出 5 處 file:line(已 letter compliant)
  - EX-PASSTHRU-1:原 2 處 → 補登錄 7 處(etf_tab_grp_compare / tab_stock_grp / tab_stock / yield_screener / section_mid)
  - **EX-RENDER-1**(新例外候選):etf_render.py:11 L4 直 import L1 緩解策略
  - 標準寫法 code block 補 `secrets: dict = {}` 屬性

### 累計
- tab_macro.py:**5387 → 488 LOC(-91%)**
- §3.3 反捏造 0 項 / §8.2 高項違憲 0 項 / §8.2.A 例外全 letter compliant
- pytest 2199 pass / 0 fail / 32 deselected (slow)

### Streamlit 实機驗證(未做,留 user)
PR merge 後 fetch warm cache → 走 §十一 News AI render path 即驗 P0-FIX
+ 驗整個 DataRegistry 12 key 完整載入。

---


## 🏁 PR #397 v18.392(merged 2026-06-28)
**tab_macro.py 1012 → 751 LOC(−261,−26%)** — 5 commit。
- D-10 `f257d84`:雙視角 + 雷達準備 64 LOC → section_long_term
- D-11 `3eb2eeb`:旌旗指數 32 LOC → services/jingqi_calc
- D-12 `a13bb25`:outer trio executor 142 LOC → services/macro_trio_orchestrator
- D-13 `fcfe2a5`:市場評估 53 LOC → services/market_assessment_apply
- INDEX sync `03c175e`

累計 tab_macro 5387 → 751 LOC(-86%)。ROI 拐點已過。

---


## 🏁 PR #396 v18.391(merged 2026-06-28)
**tab_macro.py 1076 → 1012 LOC(−64)** — 認錯補做紅綠燈卡。
- D-9 `c1e8483`:紅綠燈卡 66 LOC → section_traffic_light(回傳 placeholder/show_market_data/tl_eff_reg 3-tuple)
- INDEX sync `d3f9a04`

**承認先前 verdict 錯誤**:之前以「placeholder 反模式」擋,但 B-S2 已跨 def 傳 placeholder,argument 自我矛盾。
累計 tab_macro 5387 → 1012 LOC(-81%)。

---


## 🏁 PR #395 v18.390(merged 2026-06-28)
**tab_macro.py 1445 → 1076 LOC(−369,−26%)** — 5 commit dashboard 三件套 + Registry patch。
- D-5 `ac06da7`:五桶 bar 43 LOC → section_summary_bar
- D-6 `89ab752`:戰情概覽 35 LOC → section_overview
- D-7 `98e8005`:今日作戰室 154 LOC → section_warroom
- D-8 `cfd521f`:Registry patch 161 LOC → services/macro_registry_patch
- INDEX sync `e9f2e23`

承認前次 deep-dive verdict 過嚴(誤標 5 段「不可抽」), 本 PR 確實抽 4 段。
全工作累計:tab_macro 5387 → 1076 LOC(−4311,−80%)。
殘餘 1076 LOC 真不可抽:紅綠燈 placeholder lifecycle(streamlit 反模式)。

---


## 🏁 PR #394 v18.389(merged into main 2026-06-28)
**tab_macro.py 5387 → 1445 LOC(−3942,−73%)** — 10 commit 累計成果。

### B-region(UI section 抽出)
- B-4 hotfix `38d7a10`:_m8_* NameError(production bug,section_mid 抽走後 §九 仍 ref)
- B-S8-A `b59b072`:§三 籌碼桶 558 LOC → `macro/section_chips.py`
- B-S8-B `bec36de`:§九 跨桶 AI 220 LOC → `macro/section_cross_ai.py`

### P1+P2(AI 導航優化)
- `6b4e443`:`macro/__init__.py` INDEX docstring(段落→子模組對照表)+
  section_ai_cross→section_cross_ai / section_ai→section_news_ai 並列命名

### P3 D-region(§8.2 分層治理)
- D-3 `28515db`:_job_bias 42 LOC → `macro_snapshot.compute_twii_bias`
- D-2 `221eb5f`:_job_m1b 89 LOC → `macro_snapshot.fetch_m1b_m2_block`(3-Tier)
- D-1 `9a32589`:_job_macro 604 LOC → 5 `fetch_*_block`(VIX/CPI/Fed/PMI/NDC/Export)
- D-4 `370a430`:7-job orchestrator 230 LOC → `services/macro_fetch_orchestrator.fetch_macro_bundle`

### 新增 / 強化模組
- `src/ui/tabs/macro/` 9 個 section_*.py
- `src/data/macro/macro_snapshot.py`:89 → 798 LOC(fetch 邏輯集中)
- `src/services/macro_fetch_orchestrator.py`:270 LOC(NEW)

### SSOT 檢查結論
0 新違憲。預先存在的 inline magic(100億 / -20000 期空 / 50/100 CLI/PMI 等)留待真實 bug 觸發再 SSOT 化(§-1)。

### 殘餘 tab_macro.py(1445 LOC)
- 紅綠燈卡(_tl_placeholder lifecycle,反模式不可抽)
- 戰情概覽 + 作戰室(過小 + closure 多)
- Registry patch(~165 LOC,可抽但 ROI 低)
- session_state writes 收尾(UI 邊界)

---


## ✅ 累計完成
- P0(4 batch / 4 commit):portfolio_exposure SSOT / RSI helper / stock_names L0→L1 / 4 dead fn
- P1(5 batch / 6 commit):3 處 UI yfinance→L1 / macro_snapshot L4→L1 / shared/macro_card 拔 streamlit / 6 dead fn / 6 dead fn cross 3 檔
- P2(2 batch / 2 commit):_prov_log SSOT / 2 inline magic 入 shared
- 跳過(honest stop,ROI 不對等):
  - P1-3 Gemini API 統一(4 caller payload/retry 分歧大)
  - P1-4b cache_layer PKL_DIR env(L0↔L0 hardcode 設計味道但 Python 不 crash)
  - P2-2 命名衝突分化(_safe_float/_num/_secret,改名影響 caller 多)
  - P2-4 pct_change YoY helper(各處 period 不一,強行 helper 破壞契約)
  - P2-5 to_json_rows generic(2 處不同 dataclass,Protocol 加抽 ROI 低)

## 已完成 commits(reverse chrono)

### E-2 (v18.387) — 20-period vol σ 抽 daily_return_rolling_std SSOT
- **檔案**: `shared/calc_helpers.py` + `src/compute/scoring/scoring_engine.py:122,240`
- **拔毒**: 2 處 `close.pct_change().rolling(20).std()` inline → `daily_return_rolling_std(close, window=20)`
- **驗證**: full pytest 2220/0 fail
- **commit**: 待 push

**E-1 honest stop**: `rolling(N).mean()` 15+ 處散落,use case 多樣(close/volume/hi-lo/revenue),且本身就是 pandas 內建單行 SSOT,抽 wrap helper 純 cosmetic 無實際 SSOT 價值。

### A1 (v18.386) — Gemini API 5 caller 統一至 ai_fetcher.py
- **檔案**: `src/services/ai_fetcher.py`(NEW)+ ai_engine.py × 3 caller + financial_health_engine.py × 1 + macro_state_locker.py × 1
- **拔毒**: 5 處散落 Gemini call(retry/payload/timeout/model fallback)→ 統一 `post_gemini(api_key, prompt, *, models, persona, temperature, max_tokens, timeout, retries_per_model, retry_after_parse, inter_model_sleep, extra_generation_config, safety_settings, headers)`
- **新拓展**: `extra_generation_config`(topP/topK)+ `safety_settings`(BLOCK_NONE × 4)涵蓋 ai_engine call 1 的特殊 payload
- **回傳 tuple**: `(text, model_used_or_error)` — caller 自決失敗訊息 / emoji header
- **驗證**: 4 unit test(_build_payload + _extract_text)+ full pytest 2220/0 fail
- **commit**: 待 push

### B-S2 (v18.385) — Section 2 拐點偵測抽至 macro/section_state.py
- **檔案**: `src/ui/tabs/tab_macro.py` + `src/ui/tabs/macro/section_state.py`(NEW)
- **拔毒**: render_tab_macro line 2186-2565(380 LOC)§二 拐點偵測 + 市場狀態卡抽出。tab_macro 3402 → 3025 LOC(-11%)
- **closure 4 個 explicit pass**: `_mkt_info, _mkt_placeholder, _tl_placeholder, cd`(extremely manageable)
- **F-7.1 累計**: 5387 → 3025 LOC(**-43.8%**)
- **test fix**: 3 處 source-string assert 改合集(tab_macro + section_state)
- **驗證**: full pytest 2220/0 fail
- **commit**: 待 push

### A4 (v18.384) — pct_change YoY helper 3 處統一
- **檔案**: `shared/calc_helpers.py`(NEW)+ macro_helpers.py:860 + scoring_engine.py:446 + msl_tw.py:191
- **拔毒**: 3 處 `series.pct_change(N) * 100.0` pattern → 抽 `pct_change_yoy(series, periods=12, multiplier=100.0)`
- **periods param**: 月頻 12(macro_helpers M2 / scoring revenue)+ 日頻 20(msl_tw TWII 20D 跌幅)
- **驗證**: full pytest 2220/0 fail
- **commit**: 待 push

### A2 (v18.383) — cache_layer PKL_DIR env 注入(解 L0↔L0)
- **檔案**: `shared/cache_layer.py` + `src/config/data_config.py`
- **拔毒**: 原 `from src.config import PKL_DIR` 反向 import L0(L0↔L0 hardcode 設計味道)→ 改 `os.environ.get('STK_PKL_DIR', '/tmp/stock_cache')`,兩 file 同源 env
- **caller 介面**: 完全不變(`from shared.cache_layer import ...` / `from src.config import PKL_DIR`)
- **驗證**: smoke + full pytest 2220/0 fail
- **commit**: 待 push

### C-1+C-2+C-3 (v18.382) — 5 個 inline magic 補抽 SSOT
- **檔案**: shared/signal_thresholds.py + scoring_helpers.py:165 + etf_calc.py:901-907 + macro_helpers.py:948-949
- **拔毒**:
  - C-1:RSI 50/40 入 `RSI_STRONG_LOW/RSI_NEUTRAL_WEAK_LOW`(70/30 已在 config.py)
  - C-2:ETF 上下漲日數 60 入 `ETF_UP_DOWN_DAYS_THRESHOLD`
  - C-3:USDCNY 7.2/7.4 補抽 `CHINA_USDCNY_NEUTRAL/WEAK`(P2-3 已抽 7.0)
- **驗證**: full pytest 2220/0 fail
- **commit**: 待 push

### P2-3 (v18.381) — 2 inline magic 入 SSOT
- **檔案**: `shared/signal_thresholds.py` + `src/compute/macro/macro_helpers.py:947` + `src/compute/scoring/scoring_helpers.py:183`
- **拔毒**: 加 `CHINA_USDCNY_STRONG=7.0` + `VOLUME_RATIO_SURGE_HIGH=3.0`,2 處 caller 改 lazy import
- **驗證**: full pytest 2213/0 fail
- **commit**: 待 push

### P2-1 (v18.380) — _prov_log 3 處統一至 provenance.py
- **檔案**: `src/data/core/provenance.py`(NEW)+ etf_fetch.py / daily_data_fetchers.py / nas_server.py 改 thin shim
- **拔毒**: 3 處同名異簽名 _prov_log → 統一 SSOT `prov_log(fn_name, source, result_summary, ticker='')`,3 caller 改 thin wrapper(backward compat)
- **驗證**: full pytest 2213/0 fail
- **commit**: 待 push

### P1-5bcd (v18.379) — 6 個 0-caller dead fn 跨 3 檔刪
- **檔案**:
  - `src/data/macro/leading_indicators.py`:刪 build_dataset(line 762)+ render_table(line 809),共 117 LOC
  - `src/services/daily_checklist.py`:刪 get_export_yoy(line 250)+ get_business_indicator(line 255),含 @st.cache_data decorator
  - `src/data/core/data_registry.py`:刪 get_pingable_endpoints(line 573)+ get_summary_stats(line 602)
- **拔毒**: 全 grep 確認 0 caller(任何形式)
- **驗證**: 3 檔 ast.parse + full pytest 2213/0 fail
- **commit**: 待 push

### P1-5a (v18.378) — financial_health_engine.py 刪 6 個 dead analyze_*_module
- **檔案**: `src/services/financial_health_engine.py`
- **拔毒**: 6 個 0-caller def(analyze_survival/operating/profitability/financial_structure/solvency/advanced_diagnostic_module),全 grep 確認 0 caller(含動態 import / multiprocessing)
- **R2 教訓**: R1 awk 過範圍把 _FINANCIAL_STRUCTURE_PROMPT 等 module-level const 也刪了(test golden 引用),revert + R2 精準 disjoint 4 range 刪 def 留 consts
- **LOC**: 1115 → 962 (-13.7%,刪 ~153 LOC dead)
- **驗證**: ast.parse + full pytest 2213/0 fail
- **commit**: 待 push

### P1-4a (v18.377) — shared/macro_card.py streamlit 移除 + 刪 6 dead fn
- **檔案**: `shared/macro_card.py`
- **拔毒**: L0 含 `import streamlit as st` 違憲 + 6 個 0-caller dead fn(render_macro_card / render_macro_card_grid / build_cards_from_indicators / _esc / render_edu_markdown / _z_color)
- **保留**: calc_z_score / make_sparkline(tab_edu.py:158 唯一 caller 真用)
- **LOC**: ~290 → 81(-72%)
- **驗證**: smoke(z + sparkline OK + dir 確認 dead 全刪)+ full pytest 2213/0 fail
- **commit**: 待 push

### P1-1c (v18.376) — tab_macro yfinance ^TWII 2y 抽 L1
- **檔案**: `src/ui/tabs/tab_macro.py` + `src/data/macro/macro_snapshot.py`
- **拔毒**: tab_macro.py:973 line `import yfinance as _yf_bias; yf.download('^TWII', period='2y')` 違憲 → 抽 `fetch_twii_2y_for_ma240()` 至 L1 macro_snapshot.py(同檔有 vix block 模式),tab_macro 改 lazy import + thin call
- **驗證**: ast.parse + full pytest 2213/0 fail
- **commit**: 待 push

### P1-1b (v18.375) — yield_screener fetch_dividend_history 抽 L1
- **檔案**: `src/ui/tabs/yield_screener.py` + `src/data/stock/dividend_fetcher.py`(NEW)
- **拔毒**: line 70-125 fetch_dividend_history 整段含 yfinance + NAS proxy 注入 + 配息聚合 → 整檔搬至 L1。yield_screener 留 thin re-export(`from src.data.stock.dividend_fetcher import fetch_annual_dividends as fetch_dividend_history`)
- **EX-CACHE-1 例外**: L1 fetcher 用 @st.cache_data,允許(只 cache 不用 session_state/UI)
- **驗證**: full pytest 2213/0 fail(1 test source 對齊改合集)
- **commit**: 待 push

### P1-1a (v18.374) — tab_stock_picker yfinance 直呼抽 L1
- **檔案**: `src/ui/tabs/tab_stock_picker.py` + `src/data/stock/picker_fetcher.py`(NEW)
- **拔毒**: line 283 L5 UI 內 `yf.Ticker(...).history(...)` HTTP I/O 違憲 → 抽 `fetch_stock_history_1y(ticker)` 至 L1。_check_one_stock 內改 call helper(yf param 保留 backward compat,內部 dead 不再用)
- **__init__ 同步**: src/data/stock/__init__.py 加 picker_fetcher 入 _SUBMODULES
- **驗證**: full pytest 2213/0 fail
- **commit**: 待 push

### P1-2 (v18.373) — macro_snapshot 整檔搬至 L1
- **檔案**: `src/ui/render/macro_snapshot.py` → `src/data/macro/macro_snapshot.py`
- **拔毒**: L4 render 含 yfinance.download HTTP I/O,檔頭自標 "L1 fetchers" 卻放 render/。git mv 整檔搬位 + 4 caller 改 import path
- **caller 改**: src/ui/tabs/tab_macro.py:1051 + tests/test_pr_q5c_singles.py:28,67 + tests/test_macro_snapshot.py:11,56
- **__init__ 同步**: src/ui/render/__init__.py 移除,src/data/macro/__init__.py 加入
- **驗證**: full pytest 2213/0 fail
- **commit**: 待 push

### P0-4 (v18.372) — app.py 4 個 dead fn 刪除
- **檔案**: `app.py`
- **拔毒**: 嚴格 grep 確認 0 caller(任何形式皆無)後刪 4 個 public/private fn:
  - `calc_jingqi` (line 1024, 51 LOC)
  - `render_market_overview` (line 1075, 32 LOC)
  - `render_top_rankings` (line 1107, 23 LOC)
  - `_run_llm_analysis` (line 1559, 78 LOC)
  - 共刪 184 LOC,app.py 1722→1538
- **驗證**: ast.parse OK + full pytest 2213/0 fail
- **commit**: 待 push

### P0-1 (v18.371) — stock_names.py I/O 抽 L1 fetcher
- **檔案**: `src/config/stock_names.py` + `src/data/core/stock_names_fetcher.py`(NEW)
- **拔毒**: L0 config 含 requests/yfinance HTTP I/O(嚴重違憲)→ I/O + cache 邏輯抽 L1 fetcher。stock_names.py 留 _STATIC_NAMES const + get_stock_name/refresh_name_cache thin shim(lazy import L1)
- **驗證**: smoke(static lookup 台積電 ✓ + unknown fallback ✓);full pytest 2213/0 fail
- **commit**: 待 push

### P0-3 (v18.370,commit a08786b) — RSI 計算抽 compute_rsi SSOT
- **檔案**: `src/compute/scoring/scoring_engine.py`
- **拔毒**: line 104-106 + 239-241 同檔重複 4 行 RSI 邏輯 → 抽 `compute_rsi(close, period=14)` 純函式,2 處 caller 改 1 行 call
- **驗證**: 全 pytest 2213/0 fail

### P0-2 (v18.369,commit 9b2f8f0) — portfolio_exposure SSOT 收攏
- **檔案**: `src/services/market_strategy.py`
- **拔毒**: 刪同名異實作 def(line 148-161),改 `from src.compute.risk.risk_control import portfolio_exposure`
- **SSOT**: L2 `risk_control.portfolio_exposure(regime)` 為唯一定義
- **驗證**: 全 pytest 2213/0 fail

## 待動 batch
- P0-1 stock_names.py I/O 抽 L1 fetcher
- P0-4 dead fn 驗證 + 刪(8 個候選)
- P1-1 ~ P1-5 結構性收乾
- P2-1 ~ P2-5 漸進命名 / SSOT 補
