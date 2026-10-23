# Data Health Audit（2026-10-23）

> **用途**：盤點本 repo 投資判斷所用資料的健康狀態，作為資料中心（DEC-072「🩺 資料中心」輔助入口）與全站資料健康狀態列的現況證據。
> **不是什麼**：⛔ 不是施工授權（`CLAUDE.md` §-1；DEC-002、DEC-015）；⛔ 不是 Approved 規格；⛔ 不核准任何新資料源、公式、門檻或綜合分數；⛔ 研究候選不得因登記在本檔而升格。資料中心與狀態列的畫面屬 UI 變更，施工前須先出文字線框送客戶拍板（DEC-003 ①）。
> **待辦落點**：只在 `docs/BACKLOG.md` 5.1.7（`DH-*`）；摘要見 `docs/PROJECT_STATE.md` §25。
> **量測**：2026-10-23；`origin/main`＝`1bfca551`（#905；撰寫組 `git fetch origin main` 實查），cron 會推進 tip，引用前重查。本檔不寫行號（`CLAUDE.md` §8.2.A.0 規則 1）。

## 1. 方法與限制

**方法**（總管轉述；撰寫組只彙整並抽查部分符號是否存在）
- 四組依領域／橫向切分的唯讀稽核：台股總經、國際、個股／ETF／持股、橫向（時區、例外處理、額度用罄）。
- 兩組獨立複驗：讀原碼並重現關鍵宣稱（例：以本地 parquet 重建 ADL 與旌旗序列、重現中國 regime 恆「資料不足」、更正 357 配息對持股健檢的影響範圍）。
- 各列狀態由總管定案；撰寫組未改判。

**限制**（必讀）
- **沙箱無外網**：「最新資料日」只量**本地 `data_cache/`**（cron 產物）；⛔ **不是 production 畫面上的值**。
- **FinMind API 403、未實測**：凡標「FinMind 口徑未實測」「FinMind 欄名未實測」者，結論依 FinMind 公開文件與原碼推論，未以真實回應驗證。
- Yahoo、TWSE、TAIFEX 等外部源同樣未在沙箱實連；可達性判斷來自 cron 產物與原碼。
- 「0 caller」「0 讀取」「無 fetcher」「無資料流」類全稱句為 grep／AST 結果，**未追動態 import**，未經第三組驗證（`CLAUDE.md` §-2 規則 6）；只能當待驗事項，⛔ 不得作為實作批的前提（實作前須重查）。
- 標「推論」者未以資料重現。

## 2. 分類定義

| 狀態 | 名稱 | 定義（客戶原文逐字；經總管轉交） |
|---|---|---|
| 🟢 | HEALTHY | 「= 真實且可追溯來源、日期語意正確、missing 正確、目前可正式使用。」 |
| 🟡 | LIMITED | 「= 可以使用，但存在延遲、代理值、coverage、穩定性或其他限制。」 |
| 🔴 | BROKEN / MISLEADING | 「= 資料流斷裂、名稱與實際內容不符、錯誤 fallback、公式／日期／語意有實質疑慮。」 |
| ⬜ | UNAVAILABLE | 「= 現在沒有可靠資料。」 |

客戶原文另附：「禁止把 missing 當 0、neutral、false 或正常。」

## 3. 總表

> 「處理方式」只用四種：**可自行修復**／**需研究替代來源/API/MCP**／**需客戶裁示**／**暫不處理**（可並列）。「可自行修復」只表示屬內部自決範圍（`CLAUDE.md` §-1.5.D §03-1），⛔ **仍須客戶指派才動工**（§-1）。總管未指定處理方式的 🟢／🟡 列，撰寫組填「暫不處理」。
> 「（新版沒接）」＝repo 有資料與程式，但新 UI（`src/ui/views/`）沒有讀；「（舊 UI 限定）」＝只有舊 UI 讀。

### 3.1 台股總經

| 資料名稱 | 狀態 | 最新資料日 | 來源 | 問題 | 影響功能 | 處理方式 | BACKLOG ID |
|---|---|---|---|---|---|---|---|
| ^TWII 日線 | 🔴 | 2026-10-22（cron parquet） | Yahoo（單源） | 9mo 約 179 根 <200 ⇒ `ma200` 退回現價（假值替代）、`market_score` 恆「跌破年線」（score 被 `market_regime` 蓋掉，但殘留 status／confidence／ma200，`etf_tab_ai` 把假 ma200 餵 AI prompt）；盤中可能取到未收盤值；近 18 列 volume NaN（9/24 起） | 指數技術趨勢、Risk Cap、ETF AI 分析 | 可自行修復（ma200 不足時標未評估）＋需客戶裁示（DEC-070 盤後版實作指派） | `DH-TWII-MA200`；關聯 `VN1-PG-PIT-CONSISTENCY`、`VN1-PG-L-TWII-DROPNA-LOG` |
| 指數跌破 MA5（Required Core） | 🔴 | — | ^TWII 推算 | 無收盤判定；缺棒時跨日配對；落後 3 交易日仍判 FRESH；未與外資期貨同日檢查 | Risk Cap 紅線三 | 需客戶裁示（實作指派） | 關聯 `VN1-PG-PIT-CONSISTENCY` |
| BIAS240 | 🔴 | — | ^TWII 推算（估算值） | `is_estimated` 不被 `dated_inputs.extract_bias240` 讀取，估算值照樣計分；違反 DEC-062 Q5「代理值只顯示、不計分」（同樣適用於總經彙總燈） | Risk Cap（Optional） | 可自行修復（會改 Risk Cap 分數，實作需客戶指派） | `DH-BIAS240-EST` |
| 市場廣度 ADL | 🔴 | — | ^TWII 日內漲跌線性推估（代理） | `daily_data_fetchers.fetch_adl` 100% 推估（`is_proxy` 恆 True；docstring「精確值覆蓋」不實）；`end=today` 不含當日 ⇒ 落後 1 交易日（複驗以 parquet 重建：live 4/4、backfill 8/11 等於前一日）；`market_assessment_apply` 註解稱「市場廣度真值」並在 `market_regime` 計分；燈名「漲跌家數比」 | 市場位階、總經健康分、廣度燈 | 可自行修復（off-by-one、標示）＋需研究替代來源/API/MCP（真實家數）＋需客戶裁示（移除代理廣度計分後健康分怎麼處置 → `DH-GATE-BREADTH`） | `DH-ADL-PROXY`；關聯 `VN1-MT-SSOT-ADL-LABEL`、`DH-GATE-BREADTH` |
| 真實漲跌家數（TWSE MI_INDEX）（新版沒接） | 🟡 | — | TWSE MI_INDEX | `tw_macro.fetch_twse_breadth` 只舊 UI 用；`fetch_adl` 註解稱 MI_INDEX 永久停用，但 sector_flow cron 10-22 仍讀到 MI_INDEX，矛盾待查 | 舊 UI 廣度；新版廣度替代候選 | 需研究替代來源/API/MCP（先驗可達性） | 關聯 `DH-GATE-BREADTH` |
| 旌旗／總經健康分 | 🔴 | — | 代理 ADL 5 日均＋大盤評分 | 旌旗繼承代理＋D−1（`source='ADL'` 被當非代理）；健康分＝0.6×旌旗＋0.4×大盤分 → `arbitrate_regime` 位階、`compute_position_throttle` 建議持股；重建全期 jqavg 平均 49.6、標準差 3.3，≥60 僅 0.45% 天數 ⇒ 60% 權重近似常數；權重在收盤對收盤版本校準，線上為日內＋落後一日，未驗證；大盤分缺時重新歸一成只剩旌旗、趨勢補 neutral；`health_partial` 新 UI 0 讀取 | 市場位階、建議持股姿態帶 | 需客戶裁示 | `DH-JINGQI-HEALTH`；`DH-GATE-BREADTH` |
| 更新今日戰情沿用舊 session 值 | 🔴 | — | （流程） | `refresh_macro_now` 不 reset；ADL 失敗時舊 `jingqi_info`（無時間戳）留存；`li_latest` 沿用，`li_retain_meta`／`_is_stale` 新 UI 不讀；外資期貨防禦與三環天花板吃到舊值；只有當次刷新報告列 `not_written_keys` | 新 UI 大盤／今天頁全部燈、Risk Cap | 可自行修復 | `DH-REFRESH-STALE` |
| 外資現貨 | 🔴 | 2026-10-22 | BFI82U → FinMind | 主路徑 BFI82U 正確（未觀測不補 0、帶日期），僅 FinMind 備援 buy/sell 缺值時發生：`macro_fetch_orchestrator` 備援路徑 fillna(0) 算假淨額；只有 foreign_net 燈讀未觀測旗標；新 UI 不顯示資料日 | 外資燈 | 可自行修復 | `DH-FOREIGN-FILL0` |
| 外資期貨淨口（Required Core） | 🟡 | — | TAIFEX／FinMind | 缺腿記 None、帶 `_date`；PIT 與 MA5 同日未檢查 | Risk Cap 紅線三 | 需客戶裁示（PIT 實作） | 關聯 `VN1-PG-PIT-CONSISTENCY` |
| 投信／自營（大盤）（新版沒接） | 🔴 | — | TWSE → FinMind | 主路徑 BFI82U 正確，僅 FinMind 備援 buy/sell 缺值時發生：`macro_fetch_orchestrator` 備援路徑 fillna(0) 算假淨額；只有 foreign_net 燈讀未觀測旗標 | 舊 UI | 可自行修復 | `DH-FOREIGN-FILL0` |
| 融資餘額 | 🟡 | 2026-10-22 | TWSE → HiStock → Wearn | 只回 float、無資料日；3400 億門檻 356 天超過、近 196 天連續，燈恆紅（discriminative=False）；舊 UI 據此每日產「🔴 融資極度危險」與「今日禁止操作」 | 融資燈、舊 UI 警示 | 可自行修復（帶日期）＋需客戶裁示（門檻） | — |
| 融券（新版沒接） | 🔴 | — | TWSE | `_to_yi_mg` 依數值大小猜單位（違 `CLAUDE.md` §1.A 第 2 點） | 舊 UI | 暫不處理（舊 UI 凍結） | `DH-SHORT-UNIT` |
| PCR（Optional） | 🔴 | — | TAIFEX；不可達時 FinMind TXO 法人 OI 估算 | 估算值無來源欄，仍以全市場刻度門檻計分；違反 DEC-062 Q5「代理值只顯示、不計分」 | Risk Cap（Optional） | 可自行修復（會改 Risk Cap 分數，實作需客戶指派） | `DH-PCR-PROXY` |
| NDC 景氣燈號 | 🟡 | — | FinMind `TaiwanBusinessIndicator` → StockFeel → MacroMicro | StockFeel 備援正則可能錯配年月 | NDC 燈 | 暫不處理 | — |
| NDC 領先指標（新版沒接） | 🟡 | — | `tw_macro.fetch_ndc_leading_index` | — | 舊 UI | 暫不處理 | 關聯 `VN1-MT-LEGACY-GAP` |
| M1B／M2 | 🟡 | 2026-08 | CBC EF15M01；FRED 備援 | 腿已停用（DEC-049）；FRED 備援 `sort_order=asc` 實為死路 | M1B／M2 顯示（不計分） | 暫不處理 | — |
| 台灣出口（名實不符） | 🔴 | — | stat.gov.tw（第一順位）→ MOF 海關；FRED OECD 備援 | 燈名「台灣出口訂單 YoY」實為海關出口金額 YoY；FRED OECD 備援已停更 | 出口燈 | 可自行修復（UI 文字是否需線框依 `CLAUDE.md` §-1.5.A-8 判） | `DH-EXPORT-LABEL` |
| 台灣 PMI 當月／前月（Required Core） | 🟢 | 2026-09／2026-08 | data.gov.tw 6100 | 前月取真正前一資料月；🟢 指資料本身；16 燈不看 stale 見「指標危險度 16 燈」列；限制：session key 叫 `ism_pmi`、引擎鍵 `ISM_PMI_or_OECD_CLI` 名稱誤導 | PMI 燈、Risk Cap | 暫不處理 | 關聯 `VN1-MT-SSOT-ISM` |
| Sahm | ⬜ | — | 無 | 無來源，紅線一永不觸發（已揭露） | Risk Cap 紅線一 | 需研究替代來源/API/MCP | `DH-SAHM` |

### 3.2 國際

| 資料名稱 | 狀態 | 最新資料日 | 來源 | 問題 | 影響功能 | 處理方式 | BACKLOG ID |
|---|---|---|---|---|---|---|---|
| VIX（Required Core） | 🔴 | — | yfinance ^VIX | 取最後一根，台北傍晚為美股未收盤暫定值；`fetched_at` 被丟、判 FRESH；VIX 燈路徑無 CBOE 備援（`risk_radar` 另抓 CBOE VIX3M）；`CLAUDE.md` §2.1「VIX：Yahoo 主、CBOE CDN 備」敘述不實（只登記） | Risk Cap、VIX 燈 | 需客戶裁示（實作指派） | 關聯 `VN1-PG-VIX-ASOF`；`DH-DOC-VIX-CBOE` |
| 台灣 PMI 教學對映 `_EDU_KEY["ism_pmi"]="NAPM"` | 🔴 | — | （對映） | 台灣 PMI 燈套到美國 ISM 的教學與歷史數字 | PMI 燈教學說明 | 可自行修復 | 關聯 `VN1-MT-SSOT-ISM` |
| 美國 ISM PMI | ⬜ | — | repo 有 `fetch_ism_pmi`、0 production caller（FRED NAPM 自 2016 停更） | repo 有 fetcher 但未接 | — | 暫不處理 | — |
| 美國核心 CPI | 🟢 | — | FRED | 小瑕疵：registry 備援 ID 誤標 CUUR0000SA0；門檻兩套 | CPI 燈 | 暫不處理 | — |
| 美 10Y（DGS10／^TNX） | 🟡 | — | FRED DGS10；Yahoo ^TNX | 晚一日、無 as_of；指南針與 `fetch_macro_snapshot` 無 ^TNX 刻度防護；門檻三套 | 10Y 燈、指南針 | 暫不處理 | — |
| 美 2Y／10Y−2Y／10Y−3M | ⬜ | — | 無 fetcher | `MACRO_THRESHOLDS` 的 YIELD_10Y2Y／YIELD_10Y3M／M2_YOY／FED_BS_YOY／HY_SPREAD 0 消費者 | — | 暫不處理 | — |
| DXY | 🟡 | — | Yahoo DX=F（期貨代理，已標） | 盤中值；門檻兩套 | DXY 燈 | 暫不處理 | — |
| Fed Funds | 🟡 | — | FRED | 月均有效利率，非目標利率 | 利率顯示 | 暫不處理 | — |
| 國際指數 INTL_MAP／TECH_MAP | 🟡 | — | Yahoo | registry 標 ^GSPC 屬 `cl_data.intl` 但不在 INTL_MAP；HG=F 有登錄無 fetcher | 國際指數（舊 UI） | 暫不處理 | — |
| 總經指南針（舊 UI 限定） | 🟡 | — | `macro_core.fetch_macro_compass` | — | 舊 UI | 暫不處理 | 關聯 `VN1-MT-LEGACY-GAP` |
| 全球風險雷達 9 燈（舊 UI 限定） | 🟡 | — | `risk_radar.detect_risk_radar` | 無資料日；「亞洲夜盤」名不符實；門檻寫死在 L2 | 舊 UI | 暫不處理 | 關聯 `VN1-MT-LEGACY-GAP`、`V-RADAR-1`（`CLAUDE.md` §8.2.A.2） |
| 跨資產資金流（舊 UI 限定） | 🟡 | — | ETF 代理（已標） | — | 舊 UI | 暫不處理 | 關聯 `VN1-MT-LEGACY-GAP` |
| 中國 CLI／China Drag | 🔴 | — | FRED OECD CLI（中國） | `_render_china_drag_panel` 把 subscore 傳給 `classify_china_regime` ⇒ regime 恆「資料不足」、fx_alert 丟失；BCI zone 用舊 key `CHN_PMI` 恆中性（已重現）；舊 UI 唯讀面板 | 舊 UI 中國面板 | 可自行修復 | `DH-CHINA-DRAG` |
| 今日關鍵門檻層 `macro_alerts` | 🟡 | — | （session） | 只舊 UI 寫；同 session 先開舊頁時新頁沿用，門檻與 16 燈不同套 | 新舊 UI 警示 | 暫不處理 | — |
| 教學頁資料來源地圖 | 🔴 | — | （文件） | 宣稱 FRED NAPM／DGS2／DGS3MO／M2SL／WALCL／UNRATE／PPIACO 與 CBOE CDN，production 無資料流；「logistic 衰退機率」0 caller | 舊 UI 教學頁 | 可自行修復 | 關聯 `VN1-MT-SSOT-EDU-CLAIM` |
| 新 UI「憑什麼」FRED 健康燈（假綠燈） | 🔴 | — | （健康監測） | `page_why::NAMED_SOURCES` 監測 `fetch_fred`，但 16 燈的 CPI／DGS10／FEDFUNDS 走 fredgraph.csv | 新 UI 資料體檢 | 可自行修復 | `DH-WHY-FRED-LAMP` |
| 總經前進式驗證 | 🔴 | 2026-10-22（41 列） | cron 寫入 | 只寫不讀（`load_signals`／`evaluate_rows`／`summarise` 0 production caller；接讀屬新功能）；`inputs_as_of` 標 ^TWII 當日，但 jqavg／ad_ratio 是前一日（日期標示不實） | 總經訊號驗證 | 可自行修復（日期） | `DH-MACRO-FWD-ASOF`；關聯 `VN1-MT-SSOT-MACRO-FWD` |
| 指標危險度 16 燈日期語意 | 🔴 | — | （彙整） | 不看 `is_stale`（PMI／出口 90 天 stale cache 照判燈）；不顯示 as-of | 指標危險度 | 可自行修復 | `DH-LAMP-STALE` |

### 3.3 個股／ETF／持股

| 資料名稱 | 狀態 | 最新資料日 | 來源 | 問題 | 影響功能 | 處理方式 | BACKLOG ID |
|---|---|---|---|---|---|---|---|
| 全市場季財報快照 | 🟢 | 115Q2（抓取 2026-09-18，1974 檔） | FinMind | 小瑕疵：「三率 YoY」實為累計比 | 選股網 | 暫不處理 | — |
| 跨季趨勢 | 🟡 | — | 季快照 | 保險業 IFRS 17 斷層；無方法版本欄 | 選股網趨勢 | 暫不處理 | — |
| 選股頁財報季別 | 🟡 | — | （呈現） | `page_find` 丟棄 meta，不顯示季別／抓取時間／涵蓋率 | 新 UI 找標的 | 可自行修復 | — |
| 個股財報體檢 | 🔴 | — | FinMind | 現金流量表為累計；A 項現金流量比率與 C 項再投資比率未年化即對年度門檻；Q1/Q2 股利 0 使 C 偏高；盈餘含金量為累計 OCF÷單季 NI；查無科目回 0；Q1 對前季可能出現假惡化進入 `trend_verdict`（推論）；B 項 insufficient_data 判 Fail（舊 UI 路徑） | 新 UI 查一檔「健康度」、舊 UI 體檢 | 可自行修復（FinMind 口徑未實測） | `DH-FIN-HEALTH-CF` |
| 月營收 | 🔴 | — | FinMind → MOPS → Goodinfo；OpenAPI 備援 | 未分三態；OpenAPI 備援只一個月、算不出 YoY 時缺貨因子記 0 分（把 missing 當 0） | 選股、缺貨篩選 | 可自行修復（記 0 分）＋需研究替代來源/API/MCP（三態公告日來源） | `DH-REVENUE-ZERO` |
| 個股 K 線／還原價 | 🔴 | — | yfinance → FinMind | yfinance 1.7 `auto_adjust=True` 無 Adj Close ⇒ FinMind 備援上市上櫃皆未還原、無旗標，新頁固定寫「K 線一律用還原價」；`picker_fetcher` 同類混用；無停牌偵測 | 個股 K 線、技術指標、推播 | 可自行修復 | `DH-KLINE-ADJ` |
| 個股三大法人 | 🔴 | — | FinMind；TWSE/TPEx 備援 | 備援約 10 交易日，其餘 `fillna(0)` 無 `is_imputed` ⇒ 連續性上限 50%、「大戶吸籌」結構上不可能；`data_loader` 對 open/high/low 與融資融券也 fillna(0) | 籌碼分析、評分 | 可自行修復 | `DH-INST-FILL0` |
| 集保股權分散（舊 UI 限定） | 🟡 | — | 第三方爬蟲 | 失敗結果被快取 | 舊 UI | 需研究替代來源/API/MCP（TDCC） | — |
| 個股融資融券（舊 UI 限定） | 🔴 | — | FinMind | 缺值補 0 畫成 0（`data_loader` fillna(0)，與三大法人同一根因） | 舊 UI | 可自行修復 | 關聯 `DH-INST-FILL0` |
| 借券 | ⬜ | — | repo 0 來源 | — | — | 需研究替代來源/API/MCP | `DH-SBL` |
| 本益比／殖利率／PB（BWIBBU） | 🟡 | — | TWSE BWIBBU | 無資料日；前兩批凍結名稱 12/20 空白；上櫃 PB 未用 TPEx 官方 | 估值、選股 | 可自行修復 | — |
| 357 殖利率配息 | 🔴 | — | FinMind 股利 | `_fetch_dividend_data_body` 現金股利候選欄 `CashDividend`／`cash_dividend`／`StockEarningsDistribution`，FinMind 正式為 `CashEarningsDistribution`（＋`CashStatutorySurplus`）⇒ 實際讀到股票股利；上櫃只配現金者顯示「近 5 年沒配息」；tests fixture 捏造 `CashDividend` 遮住 bug；持股健檢／換股不受影響（複驗更正） | 357 殖利率判讀 | 可自行修復（FinMind 欄名未實測） | `DH-357-DIV-FIELD` |
| ETF 價／報酬 | 🔴 | — | `_fetch_etf_price_max_cached` | 整張 `ffill()`，尾端 NaN 以前日收盤當現價；`close_ffilled_days` 只 VaR 讀；as_of 用今天 | ETF 報酬、VaR | 可自行修復 | `DH-ETF-FFILL` |
| ETF iNAV 折溢價 | 🟡 | — | — | 守門完整；卡片無資料日 | ETF 折溢價卡 | 暫不處理 | — |
| ETF 配息 | 🟡 | — | yfinance（單源） | — | ETF 配息站 | 暫不處理 | — |
| ETF 成分股 | 🟡 | — | 爬蟲 | 失敗結果被快取 | ETF 成分、重疊度 | 暫不處理 | — |
| ETF 品質 | 🟡 | — | — | — | ETF 品質 | 暫不處理 | — |
| 持股 Google Sheets（OAuth／SA） | 🟢 | — | Google Sheets | — | 持股 | 暫不處理 | — |
| 張→股換算 | 🟢 | — | — | — | 持股 | 暫不處理 | — |
| 壓測／VaR | 🟡 | — | — | 美元持股未含匯率（已揭露） | 持股風險 | 暫不處理 | — |
| 前進式驗證凍結 | 🟢 | 2026-10-02 批 | `data_cache/forward_test/picks.parquet` | — | 前進式驗證 | 暫不處理 | — |
| 前進式驗證對帳 | 🔴 | — | 凍結批＋事後價格 | 選股為純價格報酬、0050 為含息（偏向 0050）；未處理減資分割；FinMind 備援未還原；基準只一年（2027-07 起最舊批次無基準） | 「選股是否贏 0050」 | 可自行修復 | `DH-FWD-RECON` |
| 板塊資金潮汐 | 🟢 | 2026-10-22 | TWSE MI_INDEX（cron） | — | 板塊潮汐 | 暫不處理 | — |
| 健康度歷史 | ⬜ | — | 機制存在 | 追蹤清單空、排程停用 | — | 需客戶裁示（是否啟用） | `DH-HEALTH-HISTORY` |

### 3.4 橫向

| 資料名稱 | 狀態 | 最新資料日 | 來源 | 問題 | 影響功能 | 處理方式 | BACKLOG ID |
|---|---|---|---|---|---|---|---|
| 時區 | 🟡 | — | （伺服器） | 用伺服器本地時間（推定 UTC），台北 00–08 時差一天 | 日期判定全站 | 暫不處理 | — |
| scoring 例外回中性 50 | 🔴 | — | （計分） | 例外時回中性 50（把 missing 當 neutral） | 個股評分 | 可自行修復 | `DH-SCORE-NEUTRAL50` |
| FinMind 額度用罄 | 🟡 | — | FinMind | `data_loader` 靜默改走備援，掉進上表備援的坑（未還原價、法人補 0 等） | 個股全線 | 暫不處理 | — |

## 4. 「真正沒有資料來源」vs「repo 有、新版沒接」

**真正沒有資料來源**（repo 無 fetcher 或無資料流；一律 Research Candidate／缺資料，⛔ 不得升格 Approved）
- Sahm
- 美 2Y、10Y−2Y、10Y−3M
- 美 30Y
- TIPS（`calc_real_rate` 是政策利率−CPI，不是 TIPS）
- 美國／台灣／全球 OECD CLI（只有中國有）
- 借券
- 大盤 EPS×PE、大盤 forward EPS
- AI／CSP CAPEX

**repo 有、新版沒接**（完整清單見 `docs/PROJECT_STATE.md` §23；接回須先出線框（DEC-003）且須客戶指派）
- 真實漲跌家數（`tw_macro.fetch_twse_breadth`；可達性待查，見 3.1）
- 美國 ISM fetcher（`fetch_ism_pmi`；上游 FRED NAPM 已停更）
- NDC 領先指標
- 投信／自營（大盤）
- 融券
- 全球風險雷達、跨資產資金流、總經指南針
- 中國 CLI（面板另有 🔴 問題）
- 集保股權分散
- 前進式驗證對帳
- 跨季排行等

⛔ 共同約束：研究候選不得升格；「市場位階」「指標危險度」「Risk Cap」「台股趨勢」四概念不合併（DEC-071；`docs/PROJECT_STATE.md` §22.3）；缺資料不得補值、不得當中性（DEC-026、DEC-041、`CLAUDE.md` §1）。

## 5. 重大問題（會讓目前投資結論不可信）

1. **市場位階與建議持股姿態帶受代理廣度主導**：旌旗／健康分的 60% 權重來自 ^TWII 推估的 ADL，近似常數且落後一日；代理值計分本身已不符 DEC-062 Q5（「代理值只顯示、不計分」，適用總經彙總燈）；BIAS240、PCR 估算值計分同類（`DH-BIAS240-EST`、`DH-PCR-PROXY`）。移除代理廣度後健康分怎麼辦待客戶裁示（`DH-GATE-BREADTH`）。
2. **Risk Cap 核心輸入 VIX、MA5 的 PIT 未實作**：新 UI 寫出的 `risk_cap_state.json` 仍判 VALID（正式 Sheet 寫入已關，`PRODUCTION_WRITE_APPROVED`＝`False`）（`VN1-PG-VIX-ASOF`、`VN1-PG-PIT-CONSISTENCY`）。
3. **刷新失敗沿用舊值而無揭露**（`DH-REFRESH-STALE`）。
4. **個股／ETF**：357 配息欄位錯、財報體檢現金流未年化、法人與融資融券補 0、未還原價無旗標、月營收算不出 YoY 記 0 分、評分例外回中性 50、ETF 尾端 ffill 當現價（`DH-357-DIV-FIELD`、`DH-FIN-HEALTH-CF`、`DH-INST-FILL0`、`DH-KLINE-ADJ`、`DH-REVENUE-ZERO`、`DH-SCORE-NEUTRAL50`、`DH-ETF-FFILL`）。
5. **前進式驗證對帳口徑不一**：影響「選股是否贏 0050」（`DH-FWD-RECON`）。

## 6. 資料中心 schema 草案（⛔ 草案，未核准、未實作）

| 欄位 | 說明 |
|---|---|
| 資料名稱 | 對使用者的名稱；須與實際資料語意一致 |
| 狀態 | 🟢／🟡／🔴／⬜（判定規則見下） |
| 最新資料日 | **as-of**：該筆觀測所屬日期（DEC-028），**不是抓取時間** |
| 抓取時間 | `fetched_at` |
| 來源 | 含是否代理值（`is_proxy`／估算） |
| 問題 | 一兩句 |
| 影響功能 | 哪些頁／卡／燈會受影響 |
| 處理方式 | 可自行修復／需研究替代來源/API/MCP／需客戶裁示／暫不處理 |

**狀態判定規則（草案）**
- 缺 as-of ⇒ 不得為 🟢。
- 代理值 ⇒ 至多 🟡。
- 名實不符 ⇒ 🔴。
- 無來源 ⇒ ⬜。

📌 草案規則「缺 as-of 不得 🟢」指資料中心顯示，不是判資料本身（總管裁定）。外資現貨／投信自營資料本身帶日期；主路徑 BFI82U 正確，但 FinMind 備援路徑 buy/sell 缺值補 0，依「補 0 一律判 🔴」改判 🔴（`DH-FOREIGN-FILL0`）。總表「最新資料日」欄留「—」的列，是本次沙箱未量到該日期，不代表資料本身沒有日期。

## 7. 全站狀態列規格草案（⛔ 草案，本批不實作）

- 文字：「🩺 資料健康：<最差燈>｜N 項需處理」（客戶示例：「🩺 資料健康：🟡｜3 項需處理」，DEC-072）。
- **N** ＝ 🔴＋⬜ 中，影響主流程（📊 大盤／🎯 標的／⚡ 行動／🛡️ 持股）的項數。
- 點擊後才進資料中心。
- 關係：DEC-062 Q5（最差燈＋N/M 揭露；代理值不計分；無資料來源不得宣稱通過）。
- ⛔ 畫面屬 UI 變更，須先出文字線框（DEC-003 ①）；「哪些項目算影響主流程」的對映表未定，屬實作批工作。

## 8. 未驗證事項

- FinMind 欄名與口徑（357 `CashEarningsDistribution`、財報體檢現金流量科目）：API 403，未以真實回應驗證。
- TWSE MI_INDEX 可達性：`fetch_adl` 註解稱永久停用，與 sector_flow cron 10-22 仍讀到 MI_INDEX 矛盾，未查清。
- Yahoo ^VIX／^TWII 未收盤值的實際行為（沙箱連不到 Yahoo；另見 `VN1-PG-YAHOO-PROBE`）。
- 財報體檢 Q1 假惡化進入 `trend_verdict`：推論，未以資料重現。
- 時區「推定 UTC」：未在 production 環境確認。
- 旌旗／健康分權重在線上口徑（日內＋落後一日）的效果：未重新驗證。
- 本檔所有「0 caller」「0 讀取」「無 fetcher」類全稱句：grep／AST 結果，未經第三組驗證。

## 9. 統計（量測日 2026-10-23，由本檔第 3 節表格列數以腳本計數，非手填）

| 狀態 | 列數 |
|---|---|
| 🟢 HEALTHY | 7 |
| 🟡 LIMITED | 25 |
| 🔴 BROKEN／MISLEADING | 27 |
| ⬜ UNAVAILABLE | 5 |
| 合計 | 64 |

⚠️ 一列可能合併數個相近資料（例：「美 2Y／10Y−2Y／10Y−3M」「ETF 品質」）；列數不等於資料源數。

## 10. 揭露（`CLAUDE.md` §-2 規則 6）

- 稽核與複驗為總管轉述；撰寫組只抽查部分符號存在（`fetch_adl`、`extract_bias240`、`refresh_macro_now`、`_render_china_drag_panel`、`NAMED_SOURCES`、`_fetch_dividend_data_body`、`close_ffilled_days` 等），**未逐列重查宣稱內容**。
- 第 2 節定義為客戶原文（經總管轉交，撰寫組未見原件）；第 6 節末段為總管裁定。
