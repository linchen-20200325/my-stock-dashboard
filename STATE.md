# 重構狀態看板(深層拔毒 v18.369+)

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

## 🚀 目前狀態(v18.460 — LOW 稽核修正 + 綜合重新檢查)

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
