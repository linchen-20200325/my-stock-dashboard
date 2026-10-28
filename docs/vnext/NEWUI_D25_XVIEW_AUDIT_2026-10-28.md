# Cross-View Data Consistency Audit（跨頁資料一致性稽核）正式報告

- **日期**：2026-10-28　**基準**：main `739fa361`　**性質**：唯讀稽核彙整（docs-only，本文件不改任何程式）
- **來源**：三組獨立稽核（A 價格路徑／B 快取・缺值・fallback・幣別・AI 層／C 標的身分）＋一組獨立複驗（V）。
- **裁決順位**：**V 與 A／B／C 衝突處，一律以 V 為準。** 未被 V 覆核的項目逐項標「**單組結論，未經第二組複驗**」。
- **標記**：**FACT**＝讀碼或離線探針實測；**INFERENCE**＝由事實推論、未實測；**未驗**＝沙箱跑不到（需部署端網路或 Streamlit Cloud）。
- **誠實揭露（CLAUDE.md §-2 規則 6）**：本文件的全稱句（「只有兩條價格路徑」「沒有清除路徑」「0 production caller」）多為 grep 結論；V 組本身也只是**一組**複驗。這些句子只能當待驗事項，不得當成後續動作的前提。完整清單見 §6。

---

## §1 範圍與方法

### 1.1 組別與分工

| 組 | 範圍 | 方法 | 是否實跑 |
|---|---|---|---|
| **A** | 台股個股／ETF「價格／收盤／as_of」取數路徑，逐使用位置追到 L1 | 讀碼＋探針 `probe_a.py`（monkeypatch fetcher，記錄實際呼叫參數） | 部分（見 §6 外連揭露） |
| **B** | 快取新鮮度、缺值處理、fallback 標示、幣別級別、AI 層 | 讀碼＋探針 `probe_prompt.py`（AST 抽出 `build_summary_prompt` 實跑） | 只跑純函式 |
| **C** | 標的身分（代號正規化、上市／上櫃判定、判型、去重、鍵） | grep＋逐檔閱讀＋離線探針 `probe.py`（stub yfinance／streamlit／gspread） | 只跑純函式 |
| **V** | 對 A／B／C 的 10 個承重項逐項複驗 | 讀原始碼（不採信三份報告）＋探針 `verify/*.py`；socket 層 connect／getaddrinfo 一律拋錯，**零網路請求** | 只跑純函式 |

### 1.2 範圍邊界

- 稽核對象：NAV-1 四頁實際掛載的 view —— `page_market`／`page_find`／`page_inspect`／`page_hold`／`page_me`（`shared/ia_nav4.py::LEGACY_ONLY_VIEWS = (PAGE_TODAY, PAGE_WHY)`）；`page_market` 重用的 `page_today` loader 一併看。
- **未稽核**：`page_why`（AI 問答 `ai_qa_service.run_agent`，legacy-only）的完整行為；legacy 七頁籤逐一輸入框；`scripts/` 其餘腳本。A 組有讀 `ai_qa_service` 的取價工具，但僅限取數路徑。
- **基金不適用**（FACT，B 組 grep）：`ls src/data/` = `core daily etf macro news notify portfolio proxy risk_cap sector_flow stock`，無 `fund/`；`基金|fund` 命中只有文字說明與「對齊 Fund repo」出處註記。基金屬姊妹 repo `my-Fund-dashboard`。→ **基金 NAV／級別／累積型 vs 配息型口徑，本 repo 不適用、不列入不一致清單。**（但有**海外美元標的**問題，見 XV-H3。）

### 1.3 限制（沙箱跑不到、未驗）

| 限制 | 影響哪些結論 |
|---|---|
| 沙箱沒有部署端網路、沒有 Streamlit Cloud、沒有真 streamlit／yfinance（探針中 `cache_data` 是 no-op） | 所有快取行為皆為讀碼推得 |
| yfinance 部署版本 `download`／`history` 的預設 `auto_adjust` 行為 | XV-X7（還原口徑）、XV-ASOF |
| yfinance 盤中是否回當日未收盤 K | XV-X1、XV-ASOF（FinMind 換源＝前一日收盤） |
| 部署伺服器時區 | XV-X8 |
| FinMind SDK 遇 402、yfinance 遇 429 是 raise 還是回空 | XV-M3 |
| 停牌股／轉市股在 Yahoo／FinMind 的最後一筆日期行為 | XV-C13、XV-C13b |
| 使用者 Sheet 是否真有美股代號、均價以何幣別輸入 | XV-H3（條件式） |
| V 組「釘住測試」為 grep＋閱讀所得，**沒有實際跑 pytest** | §4.1 安全小修的測試同步範圍 |

---

## §2 Cross-View Data Source Matrix（使用位置 × 取數口徑）

### 2.1 兩條核心 L1 價格路徑（A 組；「其他位置都匯到這兩條」為單組全稱句，見 §6）

| 欄 | **P-ETF** | **P-STK** |
|---|---|---|
| L1 檔＋符號 | `src/data/etf/etf_fetch.py::fetch_etf_price` → `_fetch_etf_price_max` → `_fetch_etf_price_max_cached` | `src/data/core/data_loader.py::StockDataLoader.get_combined_data` → `_get_combined_data_cached` → `_get_combined_data_body` |
| provider／endpoint | Yahoo `yf.Ticker(t).history('max', auto_adjust=True)` | ① Yahoo `yf.download(.TW→.TWO, auto_adjust=True)`；② FinMind `taiwan_stock_daily` 原始價（試以 Yahoo `Adj Close` 比例還原）；③ Yahoo `yf.download`（預設參數） |
| 欄位 | `Close` | `close`（另含 volume／法人／融資融券） |
| as_of 決定方式 | **無**；`index.max()` 即最後一根，不比對預期交易日 | **無**；`end_date=datetime.date.today()`（伺服器時區） |
| 時區 | 未處理（Yahoo 原樣） | 伺服器本地 `today()`（時區未驗） |
| 幣別 | 原幣（台股 TWD；美股代號＝USD，見 XV-H3） | TWD |
| 還原口徑 | 還原（`attrs["price_basis"]="adjusted"`） | **依成功的腿而異**：①還原；②在 yfinance≥0.2.51 拿不到 `Adj Close` 時變原始價，`adj_ratio.fillna(1.0)`（INFERENCE＋未驗） |
| 盤中／收盤 | 盤中可能含當日未收盤 K（INFERENCE，未驗） | ①同左；②FinMind 盤中只到前一交易日（V：INFERENCE，視時段） |
| 快取 TTL／key | `@st.cache_data(ttl=TTL_1HOUR, max_entries=20)`；key＝**只有 ticker**，period 在記憶體切片 | `@st.cache_data(ttl=TTL_1HOUR, max_entries=64)`；key＝`(stock_id, days, use_adjusted)`，**days 不同即不同項目**、不含日期 |
| fallback 與標示 | 僅 Yahoo；`.TW→.TWO` 由 caller 試；`df.ffill()` 補過的日期記在 `attrs["close_ffilled_days"]`（`fetch_metrics` 不讀；唯一 consumer 是 VaR，V FACT） | 三腿鏈；`attrs["price_src"]`（`yahoo_adj`／`finmind_sdk`／`finmind_raw`／`yahoo_fallback`）有寫，但下游 `fetch_metrics` 丟掉（V FACT） |
| 失敗呈現 | 失敗不入快取；冷卻期回空 df＋`attrs[fetch_failed]`；傳 `failed=` 才拿得到說明 | 暫時性失敗：`strict=False` 回 `(None, err, None)`、`strict=True` 往上拋；查無資料回 `"❌ 查無資料"` 並**快取 1h**（XV-M3） |

外層包裝：`src/data/stock/app_stock_fetchers.py::fetch_price_data(sid, days)` ＝ 本地 pkl（0.5h，14 日曆日連假容忍）＋`@st.cache_data(ttl=TTL_30MIN)` → `get_combined_data(sid, days+60, True)`。

### 2.2 使用位置矩陣

| # | 使用位置 | provider／路徑 | 參數／快取鍵 | 欄位口徑 | as_of 顯示 | fallback 標示 | 失敗呈現 |
|---|---|---|---|---|---|---|---|
| 1 | 🎯 `page_inspect.py::load_stock_readout` → L3 `dividend_station_service.fetch_metrics(code,'stock',failed=)` → `_fetch_stock_metrics` | P-STK | `(code, 360, True)`, strict=True（FACT 探針） | `close` 末值 → `current_price` | **無**（無日期／時間／來源） | 無 | `failed[FAILED_PRICE]` → 紅；查無 → 「無股價」 |
| 2 | 🎯 ETF：`load_etf_readout`／批次 `_batch_row` → `fetch_metrics(code,'etf')` | P-ETF | `fetch_etf_price(code.TW,'5y')`，空再 `.TWO` | 還原 `Close` 末值 | 無 | 無 | 無日線 → raise → 紅 |
| 3 | 🎯 357 估值 `load_valuation_readout` | 沿用 #1 的現價，不重抓 | 同 #1 | 同 #1 | 「這一輪用的現價」，無日期 | — | None → `zone_code='na'` |
| 4 | 🎯 近 20 日籌碼 `stock_chips_service.get_chips_readout` | P-STK 經 `fetch_price_data`（含 pkl 0.5h） | `(code, period+60)`；period=120 → 180 | 法人／量（不顯示價格） | — | — | — |
| 5 | 🎯 批次 `_batch_row`（個股） | 同 #1，**未傳 `failed=`** | 360 | 同 #1 | 無 | 無 | 抓取失敗與查無資料**同形**皆「—」（XV-X5，V CONFIRMED） |
| 6 | 💼 `page_hold.py::load_station` → `get_station_rows` → `build_station_rows(metrics_fn=fetch_metrics)` | 個股 P-STK／ETF P-ETF | 個股 `(code,360,True)` strict=False；ETF 同 #2 | `現價`／`市值=張數×現價`／`損益%=(現價/均價−1)`（價差，不含已領息） | **無** | 無 | 個股現價 None → UI 層 `_split_uncounted` 判「現價抓不到」→ 紅 |
| 7 | 💼 `holdings_service.get_holdings` | **不抓價**；Sheet lots／avg_price | `@st.cache_data(ttl=TTL_15MIN)` | 均價＝使用者輸入原始成本（幣別未定義，V FACT） | — | — | 空格 → None |
| 8 | 💼 ⑥ VaR／壓測 `portfolio_deep_service` | 權重取 #6；日報酬**一律** P-ETF（個股亦然，`_fetch_price_with_otc_fallback`） | `(t,'2y')` | 還原報酬、只取共同交易日、不補 0 不 ffill | — | 揭露「原幣別、未含匯率」 | strict → `fetch_errors` → 紅 |
| 9 | 💼 ⑦ AI 戰情總結 `build_summary_prompt` | 不送價格；送 `損益%`、`allocation` | — | — | prompt 無價格日期 | — | 分配卡紅時拿掉 `allocation`；`take_profit` 照送（XV-H1） |
| 10 | 組合／存股 舊 UI `ui/etf/etf_tab_dividend_station.py` | 同 #6 | 同 #6 | 同 #6 | 無 | — | 結果存 `st.session_state["_station_rows"]`，不隨 TTL 更新（XV-X6） |
| 11 | `compute/strategy/portfolio_manager.py`、`ui/tabs/portfolio_manager.py` | 不抓價（caller 傳 `price=`） | — | — | — | — | — |
| 12 | 📊 `page_market.py` | 不顯示個股價；`cl_data` 的 `TW_MAP={^TWII, TWD=X}`、美股巨頭；總經走 session 快照 | session | — | **有**「資料日」（`frame_last_close`） | — | — |
| 13 | 🧭 `page_find.py` | 選股／RS：`picker_fetcher.fetch_stock_history_1y`（Yahoo `cached_history`）＋`fetch_yf_close('^TWII')`；估值 `yield_pe_fetcher` | — | 明說「已收盤日線」 | 板塊資金有「快取更新於」 | `is_stale` → degraded | 估值缺寫「沒有數字」 |
| 14 | Decision Digest `decision_digest_builder.build_decision_digest` | 不讀價格，日期只接 `SourceStamp` | — | — | builder 不發明日期 | — | **0 production caller**（V FACT，grep 範圍 src／shared／scripts／app.py／mcp_server／tools／infra） |
| 15 | AI 問答 `ai_qa_service._tool_get_stock_score`／`_tool_get_risk_plan`（🧠 page_why） | P-STK，每次新建 `StockDataLoader()` | `days=400`／`120` | `entry_price=close.iloc[-1]` | **有**：`provenance.as_of=df.date[-1]`＋`_annotate_staleness` | — | ok=false 結構化錯誤 |
| 16 | `app_ai_service.build_llm_context` | 只有總經，無個股價 | — | — | — | — | 0 production caller（檔內自陳，A 組未全 repo 複驗） |
| 17 | 💼 VIX（`dividend_station_service.fetch_vix` → `fetch_yf_close`） vs 📊 VIX（session 快照） | module `_YF_CLOSE_CACHE` 1h vs session（無 TTL） | — | — | — | — | **同一指標兩頁兩個時點**（XV-H2） |

### 2.3 快取盤點與刷新覆蓋（B 組；側欄 🔄 欄經 V CONFIRMED 並補正）

| 資料 | 取數函式 | 快取層 | TTL | 側欄 🔄 | 📊 強制更新 | 👤 重新讀取 |
|---|---|---|---|---|---|---|
| 總經快照（📊、allocation、regime、💼④） | session `macro_info`／`warroom_summary`／`li_latest`…（`macro_refresh_service.refresh_macro_now` 寫入） | session_state | 至下一次更新 | ✗ | 重寫（失敗留舊值） | ✗ |
| VIX／^TNX／^GSPC／^TWII／TWD=X | `macro_core.fetch_yf_close` | module `_YF_CLOSE_CACHE` | 1h | ✗ | **✗**（XV-M1） | ✗ |
| FRED 系列 | `macro_core.fetch_fred` | module `_FRED_CACHE` | 30min | ✗ | **✗**（XV-M1） | ✗ |
| HTTP 回應 | `proxy_helper.fetch_url` | module `_URL_CACHE`（只存 200） | 5min | ✗（V：側欄未清） | ✓ | ✗ |
| 個股日線（🔬 籌碼路徑） | `app_stock_fetchers.fetch_price_data` | **本地 pkl** 0.5h＋st.cache_data | 0.5h | **✗（pkl 未清，V 補正）** | ✓ | ✗ |
| 建議持股 | `allocation_service.get_allocation` | session `_alloc_decision_cache`（簽章鍵） | 隨輸入失效 | 間接 | 間接 | ✗ |
| 持股／觀察清單 | `gsheet_portfolio._*_cached` | st.cache_data（身分＋B5 世代） | 15min | ✓ | ✓ | ✓（本人×這本） |
| ETF 日線／配息／iNAV | `etf_fetch.fetch_etf_price` 等 | st.cache_data | 1h（部分 1d／7d／15min） | ✓ | ✓ | ✗ |
| 個股日線＋法人＋融資（🔬 現價、💼） | `StockDataLoader._get_combined_data_body` | st.cache_data（暫時性失敗不入快取） | 1h | ✓ | ✓ | ✗ |
| 財報 | `financial_statements_fetcher` | st.cache_data | 1h | ✓ | ✓ | ✗ |
| 本益比對照表（🔎 估值） | `yield_pe_fetcher.fetch_twse/tpex_yield_pe` | st.cache_data（**失敗也快取**，XV-M2） | 1d | ✓ | ✓ | ✗ |
| 選股排名 | `fundamental_screener_service.get_ranked_picks` | st.cache_data | 1d | ✓ | ✓ | ✗ |
| RS／缺貨掃描 | `rs_leader_service`／`shortage_screener_service` | st.cache_data（失敗 raise 不入快取） | 1h／1d | ✓ | ✓ | ✗ |

---

## §3 Canonical mapping

### 3.1 Canonical field／source／as_of mapping（現行 canonical 來源與缺口）

| 欄位 | 現行 canonical 來源（FACT） | 缺口 | 相關 ID |
|---|---|---|---|
| **現價** | 個股：P-STK `close.iloc[-1]`；ETF：P-ETF 還原 `Close` 末值；經 L3 `dividend_station_service.fetch_metrics` 的 `current_price` 供 🎯／💼 共用 | 不帶日期、來源、stale 旗標；ffill 值無法剔除；個股快取鍵含 days → 同檔多值 | XV-ASOF、XV-X1 |
| **收盤** | 同上（未區分盤中 vs 收盤） | 盤中可能是未收盤 K，名稱一律叫「現價」 | XV-ASOF |
| **as_of** | 只有 `ai_qa_service`（`provenance.as_of=df.date[-1]`）與 📊 `frame_last_close` 有；L3 總經契約明說無逐指標 as_of（`page_today.AS_OF_NOT_IN_CONTRACT`） | 🎯／💼／🔎 價格類一律無 as_of | XV-ASOF、XV-H2 |
| **交易日** | `shared/staleness.expected_latest_trading_day()` 存在 | 兩條價格路徑都**未**拿最後一根比對它 | XV-ASOF、XV-C13 |
| **時區** | P-STK `datetime.date.today()`、`fetch_metrics` `pd.Timestamp.today()`（伺服器時區） | 部署時區未驗；報酬窗錨在今天而非最後一根 K | XV-X8 |
| **幣別** | 無欄位；`portfolio_fx.holding_currency` 只看後綴（裸碼台股被判 USD）；FX 機制 `portfolio_fx.convert_rows_to_twd` 只有舊 UI 在用 | 💼 新路徑無幣別、無 FX，USD 與 TWD 直接相加 | XV-H3 |
| **還原口徑** | P-ETF 標 `price_basis="adjusted"`；P-STK 依成功腿而異 | 下游不知走了哪一腿 | XV-X7 |
| **盤中／收盤** | 無標示 | — | XV-ASOF |
| **source** | L1 有 `attrs["price_src"]`／`*_fetched_at`／`source`；總經 `get_macro_state` 有 `source` | 在 L3 station row（`fetch_metrics`）與 `get_station_macro` 被丟掉 | XV-ASOF、XV-M8 |
| **cache freshness** | `shared/ttls.py` SSOT；`is_stale` 只在 🔎 板塊資金落地 | 成功快取命中不帶 `is_stale`；刷新無 SSOT（側欄 vs `clear_macro_caches` 兩份） | XV-H2、XV-M1 |

### 3.2 Canonical identity 對照表（C 組；判型差異經 C 探針實測，V 未逐列複驗 → **單組結論，未經第二組複驗**，C-03／C-05／C-08 除外）

| # | 使用位置（file:符號） | 正規化 | 輸出形式 | 市場判定 |
|---|---|---|---|---|
| 1 | `gsheet_portfolio.py::_all_records`／`_sheet_record`／`parse_portfolio_records` | 只 `strip()`（不轉大小寫） | 原字串 | 無 |
| 1w | 同檔 `save_portfolio`／`save_stock_watchlist` | `strip().upper()`，RAW 寫入 | 大寫原字串（保留前導零） | 無 |
| 2 | `holdings_service.py::get_holdings` → `_row` | `strip().upper()`；**只有觀察清單**用 L0 `normalize_ticker` 去重 | 大寫、保留後綴 | 判型用 L0 |
| 3 | `gsheet_sa_reader.py::read_holdings`（cron） | L0 `normalize_ticker` 為鍵去重，保留首見 | 原字串 | 無 |
| 4 | `scripts/push_holdings_daily.py::_build_entries` | L0 去重（持股優先） | 原字串 | L0 判型 |
| 5 | `shared/dividend_station_thresholds.py::normalize_ticker` | `strip().upper()`＋去結尾 `.TWO`／`.TW` | 裸碼大寫 | — |
| 6 | 同檔 `classify_asset_kind` | 先走 #5 | `etf`／`stock`（兩值；認不得一律 etf） | 代號規則 |
| 7 | `src/compute/etf/asset_lag.py::classify_asset_kind` | `bare_etf_code` | `etf`／`stock`／`unknown`（三值） | 代號規則 |
| 8 | `shared/etf_codes.py::bare_etf_code` | `upper()`＋先去 `.TWO` 再去 `.TW`（不限結尾） | 裸碼 | — |
| 9 | `src/compute/etf/etf_helpers.py::normalize_etf_ticker` | 符合 `^\d{4,6}[A-Z]?$` 才補 `.TW` | `XXXX.TW`；其他原樣 | 一律假設上市 |
| 10 | `dividend_station_service.py::fetch_metrics`（ETF） | #9 | `.TW`，空再 `.TWO`，之後配息／折溢價沿用同一代號 | 試誤 |
| 11 | 同檔 `_fetch_stock_metrics` | inline 去後綴 | 裸碼 → `StockDataLoader` | 交給 #12 |
| 12 | `data_loader.py::StockDataLoader.get_combined_data` | **不正規化**（假設裸碼） | `.TW` 空才 `.TWO`；FinMind 裸碼 | 試誤（空才換） |
| 13 | `picker_fetcher.py::_fetch_stock_history_1y_with_status` | 無 | `.TW` → `.TWO`（**少於 60 筆也換**）；FinMind 備援回裸碼 | 試誤（以筆數） |
| 14 | `portfolio_deep_service.py::_resolve_yf_ticker`／`_fetch_price_with_otc_fallback` | #9 | 對外鍵 `.TW`，上游可能 `.TWO` | 試誤（結尾 `.TW` 才換） |
| 15 | `watchlist_health_service.py::_resolve_and_fetch` | `upper()`＋#8 | `.TW` → `.TWO` | 試誤 |
| 16 | `app_stock_fetchers.py::_fetch_dividend_data_body`（yf 備援 2） | 無 | 只打 `.TW` | 無 `.TWO` |
| 17 | `dividend_fetcher.py::fetch_annual_dividends` | 無後綴補 `.TW`（美股也被補成 `VOO.TW`） | `.TW` | 只打 `.TW` |
| 18 | `portfolio_fx.py::holding_currency` | `upper().strip()` | 結尾 `.TW`／`.TWO` → TWD，其餘 USD（裸碼台股也 USD，檔內自陳） | 只看後綴 |
| 19 | `page_inspect.py::_clean_code` | `strip().upper()`，刻意不補後綴 | 原樣 → #7 判型 | 交 L3 |
| 20 | `sector_flow_service.py::_normalize_code` | 第三份 inline 去後綴 | 裸碼 | — |
| 21 | `dividend_station_service.py::_pick_candidates` | exclude 走 #5；候選 `_code` 只 `strip().upper()` | 裸碼比對 | — |
| 22 | `shared/strategy_class_schema.py::build_holding_keys`／`parse_strategy_records` | 只 strip，不改寫；`HoldingKey` 驗證（NFKC、控制字元） | `HoldingKey(pfv1-hash, 原字串)` | — |
| 23 | `decision_digest_builder.py::_ticker_of`／`_key_for` | 無；`holding_keys.get(ticker)` 精確比對 | `HoldingKey` 或 None | — |
| 24 | `ai_qa_service.py::_tool_get_stock_score` 等 | 無 | 直交 #12 | — |
| 24b | 同檔 `_tool_get_etf_quality` | #9 | `.TW` | 假設上市 |
| 25 | `shared/parse_helpers.py::parse_stocks` | regex `^\d{4,6}[A-Z]?$`，不合格**靜默丟掉** | 裸碼 | — |
| 26 | `etf_smart_analysis.py::_normalize_ticker`／`etf_tab_smart.py::_normalize` | 只 strip；無 `.` 就補 `.TW`（不轉大寫） | `voo.TW`、`^TWII.TW` | 假設上市 |

**判型探針（C 組 FACT）節錄**：

| 輸入 | L0 kind | L2 kind | normalize_etf | ccy | HoldingKey |
|---|---|---|---|---|---|
| `2330` | stock | stock | 2330.TW | **USD** | ok |
| `50` | **etf** | **stock** | 50 | USD | ok |
| `VOO` | **etf** | **unknown** | VOO | USD | ok |
| `^TWII` | **etf** | **unknown** | ^TWII | USD | ok |
| `2330.TW.TW` | **etf** | **stock** | 2330.TW.TW | TWD | ok |
| `1234567` | **etf** | **stock** | 1234567 | USD | ok |
| `２３３０`（全形） | stock | stock | ２３３０.TW | USD | REJ |

**身分追蹤鏈（C 組 FACT）**：Sheet `2330` → L1 `'2330'` → L3 upper `'2330'` → station `代號='2330'` → `fetch_metrics` 去後綴 → `StockDataLoader` 打 `2330.TW`（空才 `.TWO`）→ `portfolio_deep_service` 對外 `2330.TW` → sector_flow `2330` → Digest（未接線）`holding_keys['2330']`。**可追溯，但靠每一站各自正規化，沒有 canonical id 貫穿全程。**

---

## §4 不一致清單

### 4.0 總表（共 38 項：HIGH 4／MED 15／LOW 19）

> 「V 判定」欄：CONFIRMED／PARTIAL／REFUTED（部分）＝經 V 複驗；「單組」＝**單組結論，未經第二組複驗**。
> 嚴重度已依 V 的修正調整（例：B-M4 融資「0 張」部分 REFUTED，維持 MED 但只就法人部分成立）。

| ID（原 ID） | 位置（file:符號） | 一句話 | 嚴重度 | V 判定 | 處置分類 |
|---|---|---|---|---|---|
| **XV-H1**（B-H1／A-X4） | `dividend_station_service.py::build_summary_prompt`；`page_hold.py::load_ai_summary`；`scripts/push_holdings_daily.py::_maybe_ai_summary` | 全數失敗／燈全⚪／現價 None／部分失敗時，AI prompt 仍指示「續抱、定期定額即可」 | HIGH | CONFIRMED（範圍更大：LINE AI 段落同源） | 最小版 → **本批安全小修 S1**；擴大版 → **需 Gate G2** |
| **XV-H2**（B-H2） | `app.py` 側欄 `_sb_force_refresh` | 只清 `st.cache_data`；help「清除所有快取」不實；📊 仍舊值、🔬 籌碼 pkl 未清 | HIGH | CONFIRMED（補正 pkl） | help 文字 → **S2**；行為 → **T6**（M1）；as_of 顯示 → **G3** |
| **XV-H3**（B-H3） | `dividend_station_service.py::fetch_metrics`／`build_station_rows`／`compute_portfolio_totals`／`compute_allocation_split` | 美股代號以 USD 價與 TWD 持股直接相加、×1000 股、算入 80/20 | HIGH（條件式） | CONFIRMED（條件式） | **需 Gate G1** |
| **XV-ASOF**（A-X2／B-M6） | `dividend_station_service.py::fetch_metrics`／`_fetch_stock_metrics` | 現價無 as_of／來源／stale；ffill 值、換源皆靜默 | HIGH | PARTIAL（丟資訊 FACT；「FinMind＝前一日收盤」為視時段推論，未驗） | 非顯示鍵 → 內部；顯示 → **G3**；stale 計不計入 → **G4** |
| XV-X1（A-X1） | `data_loader.py::_get_combined_data_body` 快取鍵含 days；caller 360／180／400／120 | 同檔個股不同位置不同快取鍵 → 盤中可能兩個現價 | MED | 單組 | **需內部技術 Gate T1** |
| XV-M1（B-M1） | `macro_core.py::_YF_CLOSE_CACHE`／`_FRED_CACHE`；`macro_refresh_service.py::clear_macro_caches` | module 成功快取無 production 清除路徑 | MED | CONFIRMED（併 XV-H2 (b)） | **T6** |
| XV-M2（B-M2） | `src/data/stock/yield_pe_fetcher.py::fetch_twse_yield_pe`／`fetch_tpex_yield_pe` | 失敗回空表被快取 1 天（違 v3 §02「只快取成功」） | MED | CONFIRMED | **本批安全小修 S5** |
| XV-M3（B-M3） | `data_loader.py::_get_combined_data_body`；`_fetch_finmind_price_raw` | 「❌ 查無資料」當確定性負結果快取 1h；FinMind 402 空表與真空無法區分 | MED | PARTIAL（非 200 回空 FACT；Yahoo 429 回空推論） | **T7**（需部署端實測） |
| XV-M4（B-M4） | `data_loader.py::_get_combined_data_body` 第 6 段數據清洗；`shared/macro_compute.py::analyze_20d_chips_from_df` | 法人 `fillna(0)` 無旗標，計入 20 日合計／正買超天數 | MED | PARTIAL（法人 CONFIRMED；融資「顯示成 0 張」**在目前 consumer 不成立**） | **T8**（改變籌碼計算，屬資料語意） |
| XV-M5（B-M5） | `dividend_station_service.py::fetch_metrics`（`ensure_etf_rf_injected`）；`compute/etf/dividend_station.py::health_b` | 無風險利率取不到時退回固定值或 0，不揭露；夏普偏寬 | MED | 單組 | **T9** |
| XV-M7（B-M7） | `page_hold.py::build_action_card`／`_totals_facts`；`compute_portfolio_totals` | 部分列失敗時 ① 照畫金額無 partial；⑤⑥ 轉紅 → 同頁兩說 | MED | 單組 | 登記（建議日後以同一把尺統一） |
| XV-M8（B-M8） | `dividend_station_service.py::get_station_macro` | 位階退讀 `macro_state.json` 時不帶 source／日期 | MED | 單組（並存情境未驗） | 登記 |
| XV-C01（C-01） | L0 `shared/dividend_station_thresholds.py::classify_asset_kind` vs L2 `src/compute/etf/asset_lag.py::classify_asset_kind` | 判型雙 SSOT，值域不同；💼 與 🎯 對同一輸入判不同種類 | MED | 單組 | **T3** |
| XV-C02（C-02） | `data_loader.py`（多處）、`picker_fetcher.py`、`portfolio_deep_service.py`、`watchlist_health_service.py`、`financial_statements_fetcher.py`、`stock_names_fetcher.py`、`etf_fetch.py` | 無上市／上櫃判定 SSOT，≥8 份試誤實作且規則不同 | MED | 單組 | **T2** |
| XV-C03（C-03） | `holdings_service.get_holdings`；`portfolio_deep_service._weights`；`gsheet_sa_reader.read_holdings`＋`push_holdings_daily._build_entries` | 同代號兩列：UI 兩列、深度風險相加、cron 保留首見 | MED | CONFIRMED（**更正：UI 與深度風險總額一致，只有 cron 推播少算**） | **T4** |
| XV-C04（C-04） | UI `holdings_service`（選定本）vs cron `gsheet_sa_reader.read_holdings`（全組合聯集） | 推播與 UI 持股範圍不同 | MED | 單組 | **T5** |
| XV-C05（C-05） | `strategy_class_schema.build_holding_keys`；`decision_digest_builder._key_for`／`_action_candidates`；`holdings_service`（upper） vs L1（原字串） | Digest／AB-4r 鍵大小寫不一致；對不上的行動被 `continue` 丟掉無揭露 | MED（潛在；接線時 HIGH） | CONFIRMED（0 production caller） | **T11（接線批前必修）** |
| XV-C13（C-13） | `_fetch_stock_metrics` `current_price=close.iloc[-1]`；ETF `_cur=_close.iloc[-1]` | 停牌／下市／改名無處理；舊收盤被當現價 | MED | 單組（未驗） | **T10**（stale 是否計入 → G4） |
| XV-C13b（C-13b） | `picker_fetcher.py`：`.TW` <60 筆即改 `.TWO` | 轉市股可能拿到舊序列；新上市股跨頁有／無不一致 | MED | 單組（未驗） | 登記（隨 T2 一併解） |
| XV-X3（A-X3） | `portfolio_deep_service._fetch_price_with_otc_fallback` | 個股現價走 P-STK、VaR 走 P-ETF → 同頁一有一紅（已標紅，非靜默） | LOW | 單組 | 登記 |
| XV-X5（A-X5） | `page_inspect.py::_batch_row` | 葉2 個股抓取失敗與查無資料同形「—」 | LOW | CONFIRMED（財報腿失敗亦「—」） | **本批安全小修 S3** |
| XV-X6（A-X6） | `ui/etf/etf_tab_dividend_station.py`（session `_station_rows`） | 舊 UI 存 session、無時間戳 | LOW（legacy） | 單組 | 登記 |
| XV-X7（A-X7） | P-STK FinMind 腿 `adj_ratio.fillna(1.0)` | 還原口徑依腿而異，KD／均線除權息附近可能不同 | LOW（未驗，可能升 MED） | 單組 | 登記 |
| XV-X8（A-X8／B-L4） | `fetch_metrics` `_as_of=pd.Timestamp.today().normalize()` | 報酬窗錨在今天而非最後一根 K | LOW | 單組 | 登記 |
| XV-L1（B-L1） | `compute/etf/dividend_station.py::suggest_action`／`action_branch` | 燈全⚪ 落入「⚪ 巡航：維持定期定額」（餵 LINE 推播） | LOW | 單組 | 登記（決策併入 G2） |
| XV-L2（B-L2） | `app.py` 側欄 `st.cache_data.clear()` | 全 process、所有使用者共用（效能／成本，非資料錯） | LOW | 單組 | 登記 |
| XV-L3（B-L3） | `app_ai_service.py::generate_ai_comment`（legacy） | `rsi or 50`、`score` 預設 0 把缺值洗成中性 | LOW（不在新四頁） | 單組 | 登記 |
| XV-C02b（C-02b） | `app_stock_fetchers._fetch_dividend_data_body`；`dividend_fetcher.fetch_annual_dividends` | 只打 `.TW`，美股被補成 `.TW` | LOW | 單組 | 登記 |
| XV-C06（C-06） | 全 repo 無 `zfill`／前導零偵測 | Sheet `0050` 被存成 `50` → 判型、幣別全錯 | LOW | 單組 | 登記 |
| XV-C07（C-07） | 代號輸入端無 NFKC 檢查 | 全形 `２３３０` 送上游；`HoldingKey` 拒收、`parse_stocks` 照收 | LOW | 單組 | 登記 |
| **XV-C08**（C-08） | `src/compute/etf/etf_smart_analysis.py`（同儕比對兩處）、`src/ui/render/sector_heatmap_render.py`（子項顯示名） | `.replace('.TW','').replace('.TWO','')` 順序錯：`00679B.TWO`→`00679BO` | LOW（潛在） | CONFIRMED（3 處） | **本批安全小修 S4** |
| XV-C09（C-09） | `etf_smart_analysis._normalize_ticker`、`etf_tab_smart._normalize` | 不轉大寫、對美股／指數補 `.TW` | LOW | 單組 | 登記 |
| XV-C10（C-10） | `dividend_station_service._pick_candidates` | 註解說候選 normalize，程式只 `strip().upper()` | LOW | 單組 | 登記 |
| XV-C11（C-11） | `shared/parse_helpers.py::parse_stocks` | 帶後綴與小寫靜默丟掉、不去重、收全形 | LOW | 單組 | 登記 |
| XV-C12（C-12） | `ai_qa_service` 個股工具 | `stock_id` 未正規化，`2330.TW` → 打 `2330.TW.TW`（回錯誤，非錯數） | LOW | 單組 | 登記 |
| XV-C14（C-14） | `sector_flow_service._normalize_code`、`resolve_holding_names`、`_fetch_stock_metrics` | ≥3 份 inline 去後綴，邊界結果不同 | LOW | 單組 | 登記 |
| XV-C15（C-15） | `picker_fetcher` FinMind 備援 resolved | 回裸碼 vs Yahoo 帶後綴，回傳契約不一致 | LOW | 單組 | 登記 |
| XV-V1（V 新增） | `src/data/etf/etf_fetch.py`（8 處）、`src/ui/pages/health_inspector.py`（1 處）`.replace('.tw','.TW')` | 小寫 `00679b.two` → `00679b.TWo`（後綴未正規化，非錯碼） | LOW | V 單組發現 | 登記 |

### 4.1 本批安全小修（只列這 5 項）

> 原則：不新增 provider／API／schema，不改投資語意、公式或版面。以下「安全」為 V 組讀碼判斷，**未實作、未跑測試**；實作後仍須獨立 QA（§-2 規則 4）與突變測試（v3 §03-1）。

| # | ID | 修法（最小版） | 輸出變化 | 根因 | 必須同步／補的測試 |
|---|---|---|---|---|---|
| **S1** | XV-H1（最小版） | `build_summary_prompt`：「續抱」那句的拿掉條件由 `_inv` 改為 `(_inv or int(digest.get("total") or 0) <= 0)`。與 LINE 規則式正文既有 `total<=0` 防線同一把尺；同一支函式被 `_maybe_ai_summary` 共用 → LINE AI 段落一併修好 | 只有「全部抓取失敗（total=0）」時 ⑦ 與 LINE AI prompt 少一句；total>0 逐字不變 | prompt 的「續抱」條件只看 invalid，沒看 total／errors／燈可判性 | 補 case A（total=0）不含「續抱」＋突變測試；V 讀碼判斷不會碰到 z51／z52 normal case 與 `test_summary_prompt_contains_facts_and_hold_instruction`（三者 total>0）——**未跑 pytest 驗證** |
| **S2** | XV-H2（文字） | 只改 `app.py` 側欄按鈕 `help=` 為據實文字，例如「清除抓取快取（不含 📊 市場的總經快照）；總經請在 📊 市場按『更新今日戰情』」 | 只有 tooltip 文字 | 無全站刷新 SSOT；help 宣稱超過實作 | `tests/test_nav1_app_routing.py` 只檢查 key、不檢查文字（V 讀碼） |
| **S3** | XV-X5 | `page_inspect._batch_row` 對**個股**傳 `failed=_f`；`FAILED_PRICE in _f` 時回 `BatchRow(..., error=_f[FAILED_PRICE])`，沿用 ETF 既有整列錯誤態。ETF 不傳（本來就 raise）；財報腿失敗先維持「—」並列為已知限制 | 個股暫時性失敗由「—」改紅色錯誤列（屬「修正錯誤」非「改變設計」，A-8）；`failed=` 走 strict 同快取鍵與退避，不多打上游 | 葉2 未傳既有參數 | 改寫 `tests/test_v2_silent_fail_b6_inspect.py::test_b_batch_leaf_does_not_ask_for_failures` 的範圍宣告 docstring；補「暫時性失敗→error／查無資料→—」成對測試＋突變測試 |
| **S4** | XV-C08 | 三處改為 `.replace('.TWO','').replace('.TW','')`（只對調順序）。**不**換成 `bare_etf_code`（它另做 `upper()`，會放寬 smart 同儕比對，多帶一個行為變更） | 只有帶 `.TWO` 的字串不同；熱力圖 87 子項皆無 `.TWO`（V exec 實測）→ 畫面零變化 | inline 複製 | 純字串單元測試（`00679B.TWO`→`00679B`）＋grep 守衛（禁止 `.TW` 先於 `.TWO` 的 replace 鏈） |
| **S5** | XV-M2 | 兩支 fetcher 本體改為內層（掛 `@st.cache_data`，失敗 **raise**）；公開名稱改外層 wrapper（catch → print → 回 `pd.DataFrame()`，3 個 caller 不改）；**必須**加 `shared.fail_cooldown` 退避（v3 §02(b) 不轟炸） | 上游恢復後估值較早回來；失敗期間畫面不變 | 失敗結果被當正常值快取 | ⚠️ `tests/test_tpex_yield_pe.py::_clear_fetcher_cache`、`test_e2_yield_pe_layering.py`、`test_b6b_screener_audit.py::_clear_pe_caches` 對**公開名稱** `.clear()` 且包 `try/except: pass` → 改名後會**靜默失效**，必須改清內層；補「失敗不入快取」「退避」測試＋突變測試 |

### 4.2 需 Gate（客戶裁示：業務語意／版面）

> 依 v3 §03-2：請示須附總管推薦方案與具體原因。以下推薦為本報告彙整者依 A／B／C／V 證據提出，**未經客戶確認**。

| # | 決策題（商業語言） | 涉及 ID | 證據摘要 | 推薦方案 | 為何需客戶 |
|---|---|---|---|---|---|
| **G1** | 持股表裡有美股（VOO、BND 等）時，總市值／損益／核心衛星比例要怎麼算？ | XV-H3（＋XV-C06、§3.2 身分表 #18 幣別判定） | V 探針 `v3_fx.py`：0050×10＠180＋VOO×10＠550（USD，均價 17000 假設 TWD）→ `value_twd=7,300,000` 混加、VOO 損益 **−96.8%**、核心 100%；Sheet schema 無均價幣別欄；FX 機制只接在舊 UI | **先排除並標紅列出**：美股列不計入金額與 80/20，走既有 uncounted 機制列出代號；**不自行換算、不猜匯率**。日後若要計入，需另加幣別欄＋FX 來源（含 source＋as_of） | 「換算 vs 排除」與均價幣別是業務語意（§-1.5.A-4） |
| **G2** | 部分持股抓不到、燈號全判不出（⚪）、或現價缺時，AI 與 LINE 還要不要說「續抱、定期定額即可」？ | XV-H1（擴大版）、XV-L1 | V 探針 case B（全⚪）、C（現價 None）、D（部分失敗）prompt 皆帶「續抱」；LINE 規則式正文 B／C／D 印「📭 今日無需動作：續抱」；全數失敗時 LINE 正文寫「未能判斷」、AI 段卻說「續抱」 | **拿掉**：只在每一盞適用燈都判得出、且無抓取失敗時才說「續抱」，否則改寫事實句「N 檔判不出／抓取失敗，不下續抱結論」（與 💼 ① `cruise_or_gap` 同一把尺） | ⚠️ **受 Z51／Z52 約束**：`tests/test_batch_z52.py::test_prompt_normal_and_missing_identical_to_pre`、`tests/test_batch_z51.py::test_prompt_normal_identical_and_keeps_instruction`、`tests/test_dividend_station_service.py::test_summary_prompt_contains_facts_and_hold_instruction` 釘住「缺值仍帶續抱」，源自客戶 2026-10-13 裁示「正常資料路徑不得改變…不擴大修改」；改了等於變更 AI 與推播語意 |
| **G3** | 新四頁的現價／總經數字旁，要不要顯示「資料日期」與「來源」？ | XV-ASOF、XV-H2（as_of）、XV-M6、XV-M8、XV-M5（rf 來源上畫面） | FACT：`page_find`／`page_inspect`／`page_hold` 價格類無 as_of；L1 有 `price_src`／`fetched_at`，在 L3 被丟掉 | **要**：先在 L3 加非顯示鍵（`price_as_of`／`price_src`，加性、內部可做），再出**文字線框草稿**決定顯示位置與樣式 | 欄位增減屬 v3 §03-2 ①，**須先線框** |
| **G4** | 價格已過期（停牌、上游凍結、超過預期交易日）時，還要不要算進市值、損益與停利？ | XV-ASOF、XV-C13 | FACT：兩條價格路徑皆不比對 `expected_latest_trading_day()`；P-ETF ffill 到最後一列，`fetch_metrics` 剔不掉 | **不計入**：標「資料過期」、轉入 uncounted 並列出，不拿舊價下停利判斷（§1「錯誤的數字比沒有數字更危險」） | 投資判讀語意；且會動卡面 |

### 4.3 需內部技術 Gate（§8 完整流程＋獨立 QA，不需客戶）

> 依 §8：搬遷／跨檔改動一律走 §8.1 架構規劃 → §8.4 盤點 → §8.5 一次一模組＋§6 自審；動工觸發仍受 §-1 拘束（有任務碰到時才做）。

| # | ID | 修法方向 | 根因 | 前置／注意 |
|---|---|---|---|---|
| **T1** | XV-X1 P-STK 快取鍵 | 比照 `fetch_etf_price`：單一 key 抓固定長窗、記憶體切片；或至少回傳 `price_as_of` | 快取鍵含 days、`end_date=today()` 在函式內算 | 動 L1 快取結構，caller 多 |
| **T2** | XV-C02 上市／上櫃判定 SSOT | 立一份 `resolve_tw_market(code)`（可用 FinMind `TaiwanStockInfo.type` 或 TWSE／TPEx 清單＋快取），其餘改呼叫；短期先統一「空 vs 少於 N 筆」規則；連帶解 XV-C13b | ≥8 份試誤實作 | 若改用新清單源，屬新增取數，須另評 §2.1 分級 |
| **T3** | XV-C01 判型雙 SSOT | 定一份判型 SSOT、另一份委派；L0 加「無法判定」路徑或至少兩頁同答 | 同名函式兩份、值域不同 | L0 判型是 💼 分母與巡航 gate 依據；若卡面改變需回 G 類 |
| **T4** | XV-C03 cron 同代號兩列只留第一列 | 三處共用同一規則（張數相加；均價按張數加權，或 fail loud 請客戶合併） | 三條路各自決定 | **C 組原判為客戶 Gate**（均價合併屬業務語意）。依 V 更正只剩 cron 少算 → 先以「cron 對齊 UI 相加」或 fail loud 內部處理；若要定均價加權規則仍須問客戶 |
| **T5** | XV-C04 推播全組合聯集 vs UI 選定本 | 推播改讀同一份選定組合（需持久化選擇），或推播內註明「全部組合聯集」 | 推播無「選定組合」概念 | **C 組原判為客戶 Gate**（推播涵蓋範圍是業務範圍）；「加註說明」可內部做，「改範圍」需問客戶 |
| **T6** | XV-M1／XV-H2（行為） | `macro_core` 加 `clear_module_caches()`，**只清**成功快取 `_YF_CLOSE_CACHE`／`_FRED_CACHE`（持鎖），**不清**失敗退避表；由側欄與 `clear_macro_caches` 呼叫；session 總經快照標 stale（不刪） | module 快取無清除路徑；刷新無 SSOT | 同步 `tests/test_p01_macro_refresh.py` 新舊兩份清除對帳（舊分頁 `handlers._on_force_clear_click` 不准動）；上游流量會增加 |
| **T7** | XV-M3 FinMind 402 空表被快取 | `_fetch_finmind_price_raw` 加 `failed=` 旗標；FinMind 失敗且 Yahoo 空時 raise `_CombinedDataError`（沿用不快取＋退避） | 非 200 與 200 空無法區分 | **需部署端實測** SDK 402／yfinance 429 行為；配額用罄時灰「查無資料」會變紅；同步 `tests/test_d3d_kline_fail_cache.py` 等 |
| **T8** | XV-M4 法人 `fillna(0)` | L1 在 `df.attrs` 帶逐欄被填補的日期；L2／L3 20 日窗遇到填補日降級或排除。建議範圍：先只做 attrs 揭露 | 刻意取捨，無 `is_imputed` | **改變籌碼計算，屬資料語意，需 Gate**（影響 legacy 多頁與 scoring；§8.4 step 4 範圍問題須附推薦方案） |
| **T9** | XV-M5 無風險利率退回固定值 | rf 來源（live／fallback／0）帶進 row `_detail`；rf=0 時健檢 B 落 degraded | fallback 只 print | 若上畫面 → G3 |
| **T10** | XV-C13 停牌／下市／改名 | 最後一筆日期與 `expected_latest_trading_day` 比對，超過容忍標「停牌／資料過期」 | §4.6 停牌旗標未落地 | 計不計入市值 → G4；加狀態會動卡面 |
| **T11** | XV-C05 AB-4r／Digest 鍵大小寫 | 接線時規定 `holding_keys` 一律用 `holdings_service` 輸出的同一字串建；strategy_class 比對前定大小寫與後綴政策；行動被丟時加計數揭露 | 鍵正規化責任交給上游，上游有兩種字串形式 | **接線批前必修**（目前 0 production caller；接線即成 HIGH）。「客戶在 Sheet 上寫什麼字串」的規則若需定，屬業務 → 問客戶 |

### 4.4 登記即可（其餘；不主動動工，依 §-1 待任務碰到時處理）

XV-M7、XV-M8（MED，單組）；XV-C13b（MED，隨 T2）；XV-X3、XV-X6、XV-X7、XV-X8、XV-L1、XV-L2、XV-L3、XV-C02b、XV-C06、XV-C07、XV-C09、XV-C10、XV-C11、XV-C12、XV-C14、XV-C15、XV-V1（LOW）。各項位置、證據、建議修法見 §4.0 總表與 §4.5。

### 4.5 各項證據與建議修法補充（登記項與 Gate 項的細節）

| ID | 證據（FACT／INFERENCE） | 建議修法 |
|---|---|---|
| XV-H1 | FACT（V `v1_prompt.py`）：case A total=0／errors=2、B 全⚪ total=3、C 現價 None total=1、D 一失敗一正常 total=1，**四案皆帶「續抱」**。`SS.is_invalid_number(None)` 回 False（`shared/station_specs.py`）；`load_station` 全數失敗也不設 `station.error`、digest `{"total":0,…}` 非空 → 照樣付費呼叫 AI | S1（最小）；G2（擴大）。⚠️ V 指出「閘門改成 total==0 不呼叫 AI」會落入 `_station_note` 的 NO_ROWS「這不該發生…回報給維護者」錯誤文案，**不屬最小安全**，需另案寫卡面文字 |
| XV-H2 | FACT：按鈕在頂層 `with st.sidebar:`，位於 `if not _NAV4_LEGACY:` 之前、中間無 `st.stop()` → 新四頁看得到；未清 session 快照、module 快取、pkl、`_URL_CACHE` | S2／T6／G3 |
| XV-H3 | FACT：`classify_asset_kind` docstring 明寫美股 → ETF；`save_portfolio` 不檢查代號格式；`compute_portfolio_totals` 一律 ×`SHARES_PER_LOT`=1000 | G1 |
| XV-ASOF | FACT：`fetch_metrics` 檔內 grep `attrs|_src|fetched_at` 只命中配息失敗旗標；`close_ffilled_days` 唯一 consumer 是 VaR。INFERENCE（未驗）：盤中換源＝前一日收盤 | G3／G4；非顯示鍵 `price_as_of`／`price_src`／`is_stale` 屬加性內部改動 |
| XV-M4 | FACT：欄位不存在時不補（`if col in df.columns`），只有左合併未命中日變 0。融資：`chart_plotter` 濾 `>0`、`scoring_engine` 券資比取最後一列 `>0`、`stock_chips_service` 不讀融資 → **不會畫成 0 張**（V REFUTED 該子宣稱），但值本身是假 0 | T8 |
| XV-M7 | 單組 FACT：`compute_portfolio_totals` 先跳過 `_detail.error` 列再數 `held_n` → 3 持有 1 失敗得 `partial=False`；`err_n` 混算觀察清單 | `_totals_facts` 比照 `_split_uncounted`；`err_n` 拆持有／觀察 |
| XV-M8 | 單組 FACT：`get_macro_state` 有 `source`，在 `get_station_macro` 被丟掉；INFERENCE：代理廣度旗標 True 時 📊「未載入」與 💼④ 套快照位階可能並存（未驗） | 透傳 `source`＋快照 timestamp |
| XV-X3 | 單組 FACT | VaR 個股改走 P-STK，或報告註明兩路不同源 |
| XV-X6 | 單組 FACT | 舊分頁加「計算時間」caption，或不處理（legacy） |
| XV-X7 | INFERENCE＋未驗（yfinance 版本） | `fetch_metrics` 回 `price_basis`；是否因此不判 KD 屬判讀語意 |
| XV-X8 | 單組 FACT；部署時區未驗 | 錨改 `_close.index[-1]`（數值小幅變動，需回歸測試） |
| XV-C02b | 單組 FACT；回空的下游語意未驗 | 補 `.TWO` 備援；美股不補後綴 |
| XV-C06 | 單組 FACT（探針） | 2～3 位純數字代號 fail loud「疑似少了前導零」，**不自動 zfill** |
| XV-C07 | 單組 FACT（探針） | 輸入端偵測非 ASCII 數字給明確錯誤，不靜默轉換 |
| XV-C09 | 單組 FACT（探針）；peer_prices 欄名格式未驗 | 改呼叫 `normalize_etf_ticker` |
| XV-C10 | 單組 FACT；排名表代碼格式未驗 | `_code` 也過 `normalize_ticker` |
| XV-C11 | 單組 FACT（探針）：`'2330.TW, 00631l, ２３３０, 2330, 2330'` → `['２３３０','2330','2330']` | 先正規化再驗證，列出被丟的 token |
| XV-C12 | 單組 FACT | 工具入口先過 `normalize_ticker` |
| XV-C14 | 單組 FACT：`'0050 .TW'` → L0 `'0050 '`、sector `'0050'` | 改呼叫 L0 |
| XV-C15 | 單組 FACT；caller 未查 | FinMind 命中時回 None 或明確標記 |
| XV-V1 | V FACT（探針） | 後綴正規化改用大小寫不敏感處理 |

---

## §5 原則符合度 PASS 清單（A／B／C 的 PASS，經 V 未推翻者）

> V 未逐條複驗 PASS 項；以下為「V 未推翻」而非「V 已證實」。

| 項目 | 原則 | 出處組 |
|---|---|---|
| 💼 戰情表與 🔬 查一檔對同一檔 ETF 都走 `fetch_etf_price(t,'5y')`（key＝ticker）、個股都走 `get_combined_data(code,360,True)` → 同一份資料；strict 不影響成功時快取 | 同源 | A |
| 357 估值沿用個股那一輪的現價，不另抓 | 同源 | A |
| Decision Digest builder 不讀價格、不編日期；無 `SourceStamp` 標 `MISSING`＋`NO_INPUT`；`unknown`／`⬜` 不映成中性；真 0 是 0、None 是 missing；回傳前 `assert_strict` | 不造假 | A、B |
| 總經契約 `get_macro_state`：未評估回 `'unknown'`／`⬜`，不回 `'neutral'`；有 `source`；strict「讀壞 ≠ 未評估」 | missing ≠ neutral | B |
| `allocation_service._derive_intrinsic_caps`：VIX 或期貨未知時不套天花板，但登記 conflict「數字可能偏樂觀」 | 揭露 | B |
| 💼 巡航閘門 `station_cards.cruise_or_gap`：每盞燈都判得出才說「今天沒有需要動作」，否則「N/M 個依據可用」 | missing ≠ HOLD（畫面端） | B |
| 💼 金額 `compute_portfolio_totals`／`compute_allocation_split` 全無值回 None、不顯示 0；NaN／inf 走 `KEY_INVALID_INPUTS` | 不造假 | B |
| 💼 AI ⑦：按鈕才付費；上游紅態原樣帶；回傳型別漂移／服務不可用／空白一律轉紅；⑤⑥ 紅時不帶配置比例；prompt 明令嚴禁杜撰（但見 XV-H1） | AI 不修補資料 | B |
| ETF 折溢價 `calc_premium_discount` 要求同日 iNAV＋三道守門員；拿不到顯示「沒有淨值」而非 0%；市價與淨值不混用 | 口徑一致 | B |
| 抓取失敗不入快取＋退避：`fetch_yf_close`（`_YF_CLOSE_EMPTY_FAIL_CACHE`）、`fetch_fred`、`get_combined_data`（`_CombinedDataError`、法人腿退避）、`rs_leader_service`、`shortage_screener_service` | v3 §02 | B |
| `proxy_helper._URL_CACHE` 只快取 HTTP 200 | v3 §02 | B |
| Sheet 快取 B5 失效世代只失效本人×那本；👤 重新讀取不 `.clear()` | 快取隔離 | B |
| 🔎 板塊資金 `is_stale` 降級 degraded 並顯示「快取更新於」；持股標示與 💼 讀同一份「👤 我的」選定（DEC-083 Q7） | freshness 揭露 | B |
| 🔎 估值缺寫「沒有數字，不拿 0 分頂替」；因子全空不計入平均 | 不造假 | B |
| 🔬 籌碼 `stock_chips_service` 最新一日 0 歸 `UNKNOWN` 非 `NORMAL` | missing ≠ neutral | B |
| 💼 VaR 只取共同交易日、不補 0、不 ffill，並揭露原幣別限制 | 不造假＋揭露 | B |
| `gsheet_portfolio` 寫入 RAW（`0050` 不變 50）；讀取 `_TEXT_COLS` 保留字串；`build_holding_keys` 拒收非 str | 身分不失真 | C |
| `holdings_service` 觀察清單 vs 持股去重走 L0 `normalize_ticker` | 身分 SSOT | C |
| `get_switch_in_candidates` exclude 走 L0 正規化（防已持有被推換入） | 身分 SSOT | C |
| `portfolio_deep_service` 單一後綴判定入口；VaR／Beta／配息共用同後綴；重複代號權重相加非覆蓋；解不出後綴留在分母交覆蓋率揭露 | 一致＋揭露 | C（相加行為經 V C-03 確認） |
| `fetch_metrics`（ETF）`.TWO` 命中後配息與折溢價沿用同代號 | 同列同市場 | C |
| `normalize_asset_kind` 白名單收斂、髒值重判；`strategy_class_schema.unmatched_keys` 會揭露孤兒列；`page_inspect._clean_code` 不另立後綴規則；`sector_flow_service` 用裸碼不誤標未分類 | 身分 | C |
| 基金：本 repo 無基金資料 → 不存在跨頁基金級別或累積／配息型不一致 | 不適用 | B |

---

## §6 揭露

### 6.1 全稱句（皆為 grep／單組結論，不得當前提）

| 全稱句 | 出處 | 第二組是否驗過 |
|---|---|---|
| 「只有兩條核心 L1 價格路徑，其他位置都匯到這兩條」 | A | **否** |
| 「`_YF_CLOSE_CACHE`／`_FRED_CACHE` 沒有任何 production 清除路徑」 | B | V grep 同結論（src／shared／scripts／app.py），仍是 grep 非窮舉 |
| 「Decision Digest／`build_holding_keys`／`strategy_class_reader` 0 production caller」 | A、B、C | V grep 同結論（範圍見 §2.2 #14） |
| 「`build_llm_context` 0 production caller」 | 檔內自陳 | **否**（A 只 grep src、app.py） |
| 「新四頁幾乎都不顯示 as_of」 | B（關鍵字 grep） | **否**；以別的措辭顯示日期會漏 |
| 「沒有上市／上櫃判定 SSOT」「≥8 份試誤實作」「≥3 份 inline 去後綴」 | C | **否**；C 自陳為下限非窮舉 |
| 「`.replace` 順序錯只有 3 處」 | C、V | V grep（src／shared／app.py／scripts） |
| 「停牌／下市／改名完全沒有處理」 | C | **否** |
| 「本 repo 無基金資料」 | B | **否**（`ls`＋grep） |
| 「本報告 38 項即全部不一致」 | 本彙整 | **否** —— 只是四份報告的聯集，不是窮舉 |

### 6.2 外連請求揭露

- **A 組探針曾意外送出外連請求**：`probe_a.py` 未 stub FEDFUNDS／MoneyDJ／SITCA 三段，實際送出數個外連請求，**全部被代理擋下（403），未取得任何資料**；A 組結論**未使用**這幾段的結果。此行為不符「不跑網路取數」要求，據實記錄。
- V 組 socket 層全擋，**零網路請求**（log 中 `[Proxy/tfw] 127.0.0.1 無法連線` 為被該層擋下的本機 proxy 探測）。B、C 組探針只跑純函式並 stub 外部套件。

### 6.3 未驗事項（逐條）

1. yfinance 部署版本 `download`／`history` 預設 `auto_adjust`；盤中是否回當日未收盤 K（XV-X1、XV-ASOF、XV-X7）。
2. A-X2「Yahoo 失敗改走 FinMind ＝ 盤中靜默換成前一日收盤」：換源靜默為 FACT，換到前一日收盤屬視時段的推論（V PARTIAL）。
3. Streamlit Cloud 伺服器時區（XV-X8）。
4. FinMind SDK 遇 402、yfinance 遇 429 是 raise 還是回空（XV-M3）。
5. 停牌股在 Yahoo／FinMind 的最後一筆日期行為；轉市股 `.TW`／`.TWO` 歷史樣態（XV-C13、XV-C13b）。
6. 使用者 Sheet 是否真有美股代號、均價輸入幣別（XV-H3 條件式）。
7. `get_ranked_picks` 代碼格式（XV-C10）、`peer_prices` 欄名格式（XV-C09）、`fetch_annual_dividends` 回空的下游語意（XV-C02b）、`picker_fetcher` resolved 的 caller（XV-C15）。
8. XV-M8 中 📊「未載入」與 💼④ 套快照位階並存的實際情境。
9. LINE 推播 `holdings_digest_message.py` 只經 V 部分探針；`page_why`／legacy 七頁籤／`scripts/` 其餘腳本未稽核。
10. V 的「釘住測試」清單（Z51／Z52 等）為 grep＋閱讀所得，**沒有實際跑 pytest**；§4.1 各項「不會碰到既有測試」同屬讀碼判斷。
11. 所有快取行為為讀碼推得（沙箱 `cache_data` 為 no-op）；H2／H3／M7 未以 Streamlit 實測。
12. 本報告所有未標 V 判定的項目（§4.0「單組」）均**未經第二組複驗**；§5 PASS 清單 V 未逐條複驗。
13. §4.2 各 Gate 的推薦方案、§4.3 的分類（含 T4／T5 由 C 組原判「客戶 Gate」改列內部技術 Gate 並附轉問條件）為本彙整者依總管派工規格整理，**未經客戶確認**。

---

## §7 本批安全小修實際處置結果（2026-10-28 補；加法式，上文一字未改）

> 本節記錄 §4.1 S1～S5 的**實際**處置（§4.1 原文為實作前的 V 讀碼建議，保留不改）。決策紀錄 `docs/DECISIONS.md` DEC-100（AI 總管內部，非客戶裁示）。狀態：隨 xview PR，implementation complete／waiting CI，**未合併**。

| # | ID | commit | 實際做法 | 與 §4.1 建議的差異／停手項 |
|---|---|---|---|---|
| **S1** | XV-H1（最小版） | `188c20e7`＋QA 回修 `183dbdc3` | `build_summary_prompt`：`total` 須為**有限值且 ≥1** 才放「續抱」句（缺／非數／NaN／inf／0／0.5 不放）；total>0 逐字不變；LINE `_maybe_ai_summary` 共用同支 prompt 同步受益 | 比 §4.1 `int(total or 0)<=0` 更嚴（QA MINOR 回修：inf／NaN／0.5 原會漏過）；部分失敗／燈全⚪／無現價**未動**（Z51／Z52）→ 客戶 Gate `XV-H1-EXT` |
| **S2** | XV-H2（文字） | `96880543`＋QA 回修 `183dbdc3` | 只改側欄按鈕 `help=`，據實列出不在清除範圍的模組自有暫存，結尾表明非完整清單；標籤／key／行為／版面不變 | QA MAJOR 回修：首版漏列個股股價與籌碼、台灣與美國總經（含 VIX、匯率）、多檔批次結果；按鈕兩模式共用 ⇒ legacy 亦可見（舊 UI digest 更新，DEC-019 揭露）；行為統一 → `XV-H2-EXT` |
| **S3** | XV-X5 | `7dbfaf4b` | `page_inspect._batch_row` 對個股傳 `failed=`，價格失敗沿用 `BatchRow.error` 整列錯誤態；查無資料仍「—」；L1 走 strict 同快取鍵與冷卻 | ⚠️ 取捨：同列財報分數一併被錯誤態蓋掉（已揭露）；財報腿失敗仍「—」（已知限制） |
| **S4** | XV-C08 | `8bc93e8e` | `sector_heatmap_render` 子項顯示名改先 `.TWO` 再 `.TW`；不換 helper、不改大小寫 | **只修 1／3 處（半項）**：`etf_smart_analysis` 兩處僅舊 UI 使用，依 DEC-019 停手 → BACKLOG `XV-ETFSMART-SUFFIX`；`etf_fetch` 小寫 `.two` → `XV-V1` |
| **S5** | XV-M2 | `99e10bc6`＋QA 回修 `183dbdc3` | 快取移內層、失敗 raise 不入快取；公開函式為外層 wrapper 照舊回空表（3 caller 不變）；接 `shared.fail_cooldown`（上市／上櫃各一份），成功即解除；公開 `.clear` 同清內層與冷卻；3 個測試 fixture 改直接 `.clear()`、不再吞例外 | QA MINOR 回修：補「晚到失敗不得覆蓋成功」測試；⚠️ INFERENCE：冷卻為模組層共用 ⇒ 冷卻期間所有使用者拿空表 |
| — | 守衛同步 | `3c1a7550` | 舊 UI 零改動 digest 更新（舊值刪除線保留＋DEC-019 揭露）；新增 `tests/test_xview_revert_chain.py`（接在 `sheet_safety_revert_for` 鏈頭） | — |

**QA 結果**：一組修正 QA 抓到 **1 MAJOR（S2 說明列不完整）＋2 MINOR（S1 total 判定、S5 success() 世代守衛測試）**，皆已於 `183dbdc3` 回修；**回修後未再經第二組複驗**（總管轉述）。突變測試由實作者與 QA **各自自列**，未獨立複跑。

**限制**：沙箱無部署端網路、Streamlit Cloud 未驗（快取與冷卻行為僅讀碼＋單元測試）；QA 時另發現兩項既有問題（非本批引入，總管轉述）：LINE `format_holdings_message` total=NaN／inf 拋例外（`XV-LINE-TOTAL-NAN`）、`tests/test_symmetry_phase1.py` c4 測試順序相依、基底 `739fa361` 亦重現（`XV-TEST-SYMMETRY-C4`）。撰寫組（本節）未重跑測試。

