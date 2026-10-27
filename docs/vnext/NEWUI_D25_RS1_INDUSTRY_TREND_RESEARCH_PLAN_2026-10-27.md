# D2.5 RS-1｜產業趨勢研究計畫（客戶 Q5，DEC-092）

- **日期**：2026-10-27　**基準**：main `a985eb20`　**性質**：**研究計畫（docs-only 批次）**。0 程式碼、0 測試、0 導覽變更、**不導入 production、不接入任何新外部來源、不新增 API／MCP**。
- **標記**：FACT[檔:符號]＝本輪（2026-10-27）已重新讀碼／讀資料檔／抽查；INFERENCE＝由事實推得、未驗；MISSING＝repo 查無，不猜。
- **誠實揭露（CLAUDE.md §-2 規則 6）**：本檔 FACT 為單組讀碼＋抽查（沿用 C §6 與 R2 結論，並自行重新 grep／讀 parquet 抽查關鍵點，見 §3 末的「本輪抽查清單」），**未連網、未跑 App、未經第二組獨立複驗**；所有「沒有／查無／0 命中」皆為待驗事項，開工前須由獨立一組重驗。外部來源的可用性、授權、成本**一律未驗**。
- **上位文件**：`NEWUI_D25_PLAN_2026-10-27.md`（§5 批次表第 1 序）、`NEWUI_D25_C_AI_BRAIN_DATA_2026-10-27.md` §6（摘要）、`docs/DECISIONS.md` DEC-092 Q5（客戶原文，具約束力）。

---

## §1 目標與邊界（DEC-092 Q5 逐字意旨）

### 1.1 客戶要判斷什麼
較長期的：**「產業是否正在變強／轉弱／發生世代結構變化？」**

### 1.2 客戶的裁示（本研究的約束）
1. 「產業單季營收 YoY 中位數＋覆蓋率」可作為**第一個候選維度／baseline research**，但**不得直接定義為正式「產業趨勢」**。
2. **先開研究，不導入 production。**
3. 研究**至少**盤點八項：①產業營收 YoY／成長廣度 ②EPS／獲利趨勢 ③產業相對強弱 ④法人配置／籌碼 ⑤資本支出 ⑥景氣／終端需求 ⑦估值 ⑧結構性技術／產業世代變化。
4. **先盤點 repo 已有可追溯資料**，再提出：**可直接使用／需要轉換／缺資料／新來源候選**。
5. **新外部來源目前只研究**：不得接入 production、不得新增 API／MCP，**正式導入前另開 Customer Gate**。
6. **AI 在正式產業規則完成以前不得自行判定產業興衰。**

### 1.3 本計畫不做的事
- 不寫任何 production code；不新增 `data_registry` 來源登記、不改 `requirements.txt`、不新增 MCP／API 呼叫。
- 不定義「正式產業趨勢」的規則、門檻、權重、公式（那是研究之後的 High Gate）。
- 不讓 AI／Digest 產生任何「變強／轉弱／衰退／崛起」結論。
- 不改現有畫面（標的頁第一區「產業機會」沿用 A §4.2.1 的 ⬜ 呈現）。

---

## §2 方法與分類定義

**步驟**：(1) 盤點 repo 可追溯資料（FACT[檔:符號]）→ (2) 逐項分類 → (3) 為每項定驗證方法 → (4) 對「缺資料」項研究新來源候選（只研究）→ (5) 產出研究報告（§7）供客戶 Gate。

| 分類 | 定義 |
|---|---|
| **可直接使用** | 現有輸出已是產業層（或可直接當產業層維度用），口徑與覆蓋明確，不需新計算 |
| **需要轉換** | 個股層／原料資料齊，但需新聚合或單季化等計算才得產業層；屬**新規則模組**（正式化前須 `rule_id＋版本＋獨立測試`，`PROJECT_RULES.md` §19.4） |
| **缺資料** | repo 現有資料無法支撐該維度 |
| **新來源候選** | 缺資料項的外部資料候選（**僅研究**，附可信度／授權／成本，見 §6） |

---

## §3 共同基礎事實（本輪抽查，2026-10-27）

| 項目 | 事實 | 標記 |
|---|---|---|
| 產業分類體系 | TWSE／TPEx 官方產業別代碼；`shared/industry_codes.py:OFFICIAL_INDUSTRY_CODE_NAMES` 共 **37** 個代碼鍵、37 個不重複名稱（本輪實測載入） | FACT |
| 個股→產業對映檔 | `data_cache/sector_flow/ticker_sector.json`：**3167** 筆、**55** 種不重複標籤（本輪實測）；含 ETF／ETN／存託憑證／`其他`／`所有證券`／`Index` 等非產業標籤（標籤內容沿用 C §6.1，未逐一重列）；對映來源 `market_close_fetcher.fetch_industry_map_bulk`（官方 `t187ap03_L`／`mopsfin_t187ap03_O` 為主，FinMind `TaiwanStockInfo` 為輔） | FACT |
| 已知對映缺口（沿用 C §6.1） | 非產業標籤（`其他` 133 檔等）；同義雙名未併（`電子工業`／`其他電子類`／`其他電子業` 等）；無次產業／供應鏈分類；無 GICS 對映（ETF 曝險另用 `_ETF_SECTOR_MAP`，口徑不同勿統一） | FACT（沿用，未重列逐檔） |
| 季報快照 | `data_cache/fundamentals/{sii,otc}_{114Q1…115Q2}.parquet`＝**12 檔／6 季**，全部列數合計 **11784**；`latest.json`：roc_year=115、season=2、updated_at=2026-09-18、coverage `sii=1083／otc=891／total=1974`、`prev_total=1968` | FACT |
| 快照欄位 | `stock_id／revenue／gross_profit／op_income／net_income／eps／market／roc_year／season／source／fetched_at／total_assets／total_liab／current_assets／total_equity`（以 `sii_115Q2.parquet` 實測）；**損益欄為年初至今累計** | FACT |
| 單季化 | `src/compute/screener/cross_quarter_trends.py:ytd_to_single_quarter` 只涵蓋 `YTD_FLOW_COLS`＝revenue／gross_profit／op_income（輸出 `sq_revenue／sq_gross_profit／sq_op_income／sq_break`）；**`eps`、`net_income` 未單季化** | FACT |
| 個股層 YoY | `compute_cross_quarter_trends` 輸出含 `revenue_yoy`（註解：單季營收 vs 去年同季單季營收，PQ-C4-1 起）；`describe_snapshot_coverage`（`fundamental_screener_service`）回 `possibly_incomplete` | FACT |
| 產業資金流 | `data_cache/sector_flow/daily_net.parquet`：欄 `date／sector／net_amt_yi／foreign_yi／trust_yi／dealer_yi／n_stocks／twse_ok／tpex_ok／source`；**27 個交易日（2026-09-11→2026-10-22）、48 個 sector 標籤**；`bubble_latest.json`：**40 板塊**、含 `window_size／n_trading_days_used／tpex_complete`；讀取層 `src/data/sector_flow/reader.py:read_sector_flow_cache` | FACT |
| 大盤歷史 | `twii_ohlcv.parquet` 4903 列；`tw_pmi.parquet` 171 列（2012-07→2026-09）；`finmind_m1m2.parquet` 238 列 | FACT |
| 6 季可得的 YoY 點數 | 114Q1～115Q2 共 6 季；單季 YoY 需「去年同季」→ 僅 **115Q1、115Q2 兩個 YoY 點**（算術推得，需先單季化各季） | INFERENCE |
| 存活者偏誤 | 快照只含「現存公司」（沿用 A §4.2.1、C §6.1） | FACT（沿用） |
| PIT | 公告季 ≠ 交易日 ≠ 當日 PE，三者 `as_of` 須分開標示（CLAUDE.md §2.3；沿用 C §6.4） | FACT（規則） |

**本輪抽查清單**（自行重新 grep／讀檔，非轉述）：產業代碼數、`ticker_sector.json` 筆數與標籤數、12 個季快照檔與總列數、`latest.json` coverage、`sii_115Q2` 欄位、`daily_net.parquet` 日數與 sector 標籤數、`bubble_latest.json` 板塊數、`tw_pmi`／`twii`／`m1m2` 列數與日期、`YTD_FLOW_COLS` 單季化範圍、`revenue_yoy` 定義、`fetch_batch_monthly_revenue` docstring（FinMind 帶 18 月歷史；備援僅最新月快照）、`fetch_5_years_cash_flow` 資本支出欄、`TW_SECTOR_SINGLE_STOCK_PROXY=True`（`shared/sector_heatmap.py`）、FinMind dataset 使用清單。**未抽查**：外部來源端點、授權、成本；`data_cache/` 於 production 部署的實際內容（沙箱讀 git 追蹤版）。

---

## §4 八項逐項盤點

> 格式：客戶問題｜repo 可追溯資料（FACT）｜分類｜轉換／缺口｜驗證方法。分類為撰寫組判定（單組）。

### 4.1 產業營收 YoY／成長廣度
- **客戶問題**：這個產業的營收是否普遍在成長（不只靠少數龍頭）？
- **repo 資料**：FACT[`data_cache/fundamentals/*.parquet` 的 `revenue`（年初至今累計，6 季）]；FACT[`ytd_to_single_quarter`、`compute_cross_quarter_trends.revenue_yoy`（個股層單季 YoY）]；FACT[月營收 `monthly_revenue_fetcher.fetch_batch_monthly_revenue(months=18)`：FinMind 帶 18 月歷史，備援 OpenAPI 僅最新單月快照]；FACT[產業對映 `ticker_sector.json`／`shared/industry_codes`]。
- **分類**：**需要轉換**。個股 YoY 已有；產業聚合（中位數／加總／加權）、**成長廣度**（YoY>0 的家數占比＝新計算）、覆蓋率均無現成函式（單組 grep，待驗）。
- **缺口／偏誤**：僅 2 個 YoY 點（INFERENCE）；存活者偏誤；金融業等無營收口徑；非產業標籤須排除；樣本太小的產業如何處置＝新門檻（研究階段只報告分布，不訂門檻）。
- **驗證方法**：(a) 抽 5 檔個股，手算單季營收 YoY 對 `revenue_yoy`；(b) 產業內家數加總＝對映檔該產業家數＝快照列數（覆蓋率自洽）；(c) 中位數 vs 加總 vs 家數加權三種口徑並列，檢查結論是否互相矛盾（口徑敏感度）；(d) 與月營收 FinMind 18 月序列交叉（同產業至少 3 檔）；(e) 排除 `sq_break`＝True 列並計數。

### 4.2 EPS／獲利趨勢
- **客戶問題**：產業獲利是在擴張還是收縮？
- **repo 資料**：FACT[快照 `eps／net_income／op_income／gross_profit`（累計）]；FACT[單季化只涵蓋 revenue／gross_profit／op_income]；FACT[`compute_cross_quarter_trends` 毛利率／營益率斜率（個股層）]。
- **分類**：**需要轉換**（EPS、net_income 需先單季化；產業層 EPS 聚合定義＝加總淨利 vs 中位數 EPS，屬方法決策）。
- **缺口**：EPS 為每股值，跨公司加總無意義（不得直接加總 EPS，INFERENCE）；虧損公司與一次性損益；股本變動（增資、減資）使 EPS 跨期不可比。
- **驗證方法**：(a) 對 5 檔手算 EPS 單季差分並對照季報原文；(b) 單季化後 Q4 = 全年 − 前三季累計的恆等式檢查；(c) 以 `net_income` 單季化為主、EPS 為輔，口徑並列；(d) 股本變動公司清單標旗。

### 4.3 產業相對強弱
- **客戶問題**：這個產業的股價是否相對大盤變強？
- **repo 資料**：FACT[①法人資金流泡泡圖（40 板塊，20 交易日窗；`bubble_latest.json`）；②熱力圖＝10 個「單一代表股」近似，`TW_SECTOR_SINGLE_STOCK_PROXY=True`（`shared/sector_heatmap.py`），**非類股指數**]；FACT[`daily_checklist.py:DISABLE_TWSE=True`、`daily_data_fetchers.py` 註解：TWSE MI_INDEX「已永久停用」]；FACT[FinMind `TaiwanStockPrice` 已登記於 `data_registry`]。
- **分類**：**缺資料（價格面相對強弱）**；**需要轉換**（INFERENCE：可用 `TaiwanStockPrice` 逐檔收盤價 × 對映自算等權產業指數，屬新資料流）。資金動能面為現有資料（見 4.4），**不可冒充價格相對強弱**。
- **驗證方法**：(a) 抽 3 個產業，自算等權指數與已知類股指數（若可取得）對照方向一致性（INFERENCE，需外部對照源）；(b) 比較「資金流象限」與「自算價格相對強弱」的一致率（兩者口徑不同，不一致本身是資訊，不是錯誤）；(c) 存活者／下市股對等權指數的偏誤估計（以現存公司為限，只能標旗）。

### 4.4 法人配置／籌碼
- **客戶問題**：法人是否在持續配置這個產業？
- **repo 資料**：FACT[`daily_net.parquet`：外資／投信／自營產業淨買超金額（億），NaN 不補 0，`twse_ok／tpex_ok`；27 交易日]；FACT[`read_sector_flow_cache`→`is_stale／stale_reason／window_size／n_trading_days_used／tpex_complete`]；FACT[個股 20 日 `stock_chips_service.get_chips_readout`]；FACT[單檔集保大戶：`tab_stock_picker.py` 以 FinMind `TaiwanStockHoldingSharesPer` 查詢]；FACT[大盤層 `finmind_inst.parquet`（foreign_buy）、`finmind_margin.parquet`]。
- **分類**：**流量＝可直接使用**（口徑：淨買超金額，非持股比重）；**存量（配置占比）＝缺資料／新來源候選**；產業層融資融券＝缺資料。
- **缺口**：僅 27 個交易日，無法判斷「持續」；`tpex_complete=False` 日僅含上市。
- **驗證方法**：(a) 產業淨買超加總 vs 全市場法人淨買超（`finmind_inst`）對帳（容差口徑須先定義）；(b) 抽 3 日手算（個股淨買超 × 對映）對照 `daily_net`；(c) 計 `tpex_complete=False` 日數並分開統計。

### 4.5 資本支出
- **客戶問題**：產業是否在擴產／投資加速？
- **repo 資料**：FACT[`tw_stock_data_fetcher.fetch_5_years_cash_flow`（單檔，FinMind CashFlows，5 年；取「取得不動產、廠房及設備」等科目為 capex）]；FACT[全市場季快照無 capex 欄]。
- **分類**：**缺資料（產業層）**；單檔層可取（需逐檔抓取，配額壓力）；**新來源候選**：MOPS 現金流量表彙總端點（是否存在＝未驗，§6）。
- **驗證方法**：(a) 抽 5 檔手對 FinMind 現金流量表與公開資訊觀測站原文；(b) 估算全市場逐檔抓取所需請求數與 FinMind 配額（只估算，不實抓）；(c) 科目名稱別名（`shared/finmind_subject_aliases`）覆蓋率抽查。

### 4.6 景氣／終端需求
- **客戶問題**：產業所處的景氣位置與終端需求趨勢？
- **repo 資料**：FACT[總體：`tw_pmi.parquet`（171 列）、NDC 景氣燈號／領先指標（FinMind `TaiwanBusinessIndicator`，`tw_macro.py`）、`finmind_m1m2.parquet`、MOF 進出口（CLAUDE.md §2.3 列）]；FACT[`tw_macro.py` 註解：FinMind `TaiwanMacroEconomics` **不存在**（v19.85 更正）→ 不得當候選]。
- **分類**：總體＝可直接使用（但**非產業別**）；**產業別景氣／終端需求＝缺資料／新來源候選**（工業生產指數、外銷訂單、製造業銷售量值、海關進出口分類貨品；PMI 產業細項）。
- **驗證方法**：(a) 候選端點是否含產業細分（以官方文件／欄位清單確認，只讀）；(b) 發布延遲與修正頻率（CLAUDE.md §2.3 PIT 表格式登錄）；(c) 與本產業營收 YoY 做同期對照的可行性（落差、領先落後）。

### 4.7 估值
- **客戶問題**：產業估值相對自身歷史是貴還是便宜？
- **repo 資料**：FACT[`yield_pe_fetcher.fetch_twse_yield_pe`（TWSE `BWIBBU_d`）、`fetch_tpex_yield_pe`：當日全市場 PE／殖利率／PB，`TTL_1DAY`]；FACT[357 殖利率位階（個股）]。
- **分類**：當日產業估值＝**需要轉換**（對映後取中位數）；**歷史分位＝缺資料**（未見歷史落地，單組 grep；只能自開始累積起算，PIT 友善）。
- **缺口**：金融／虧損股 PE 缺值處理；中位數對極端值穩健但對權值股失真。
- **驗證方法**：(a) 抽 5 檔 PE 對 TWSE 官網數；(b) 虧損股／PE 缺值計數與處理規則並列；(c) 若日後累積歷史，定義最短可信窗口（屬新門檻，由客戶 Gate 決定，不在本研究訂定）。

### 4.8 結構性技術／產業世代變化
- **客戶問題**：產業是否發生世代更替（新技術取代舊技術、供應鏈位移）？
- **repo 資料**：**MISSING**。無次產業／供應鏈分類；grep 「供應鏈／題材」命中 4 檔（`overextension.py`、`section_long.py`、`tab_stock_picker.py`、`data_registry.py`），**未逐一讀，INFERENCE 為說明字串而非資料集**（待驗）。
- **分類**：**缺資料**；新來源候選＝多為商用或第三方整理（授權、可信度未驗）；**需客戶先定義「世代變化」的範圍與可觀測代理**（否則任何資料都是臆測）。
- **驗證方法**：(a) 先與客戶界定 2–3 個具體案例（例：某技術世代交替的歷史事件）作為「事後可驗」的基準；(b) 候選來源以該案例回溯是否「當時就看得見」（lookahead 檢查）；(c) **在客戶定義範圍前，任何來源只列「是否可機械取得」，不評估結論。**

### 4.9 八項總表
| # | 項目 | 可直接使用 | 需要轉換 | 缺資料 | 新來源候選 |
|---|---|---|---|---|---|
| 1 | 營收 YoY／成長廣度 | 個股 YoY | 產業聚合、廣度、覆蓋率 | 更長歷史（>6 季） | 回補更早季別（同一 MOPS 端點，舊季是否可用＝未驗） |
| 2 | EPS／獲利 | — | EPS／淨利單季化、產業聚合 | — | — |
| 3 | 相對強弱 | 資金動能（非價格） | 自算等權產業價格指數 | 真類股指數 | 官方類股指數序列（端點未驗） |
| 4 | 法人配置／籌碼 | 產業淨買超流量（27 日） | — | 存量（持股比重）、產業融資融券、更長歷史 | 外資持股統計、集保股權分散（官方開放資料） |
| 5 | 資本支出 | 單檔現金流量表 | 逐檔聚合（配額壓力） | 產業層 | MOPS 現金流量表彙總 |
| 6 | 景氣／終端需求 | 總體 PMI／NDC／M1B-M2 | — | 產業別 | 經濟部統計處、海關、CIER 產業細項 |
| 7 | 估值 | 個股當日 | 產業當日中位數 | 歷史序列／分位 | 無需新來源（自行累積落地＝新資料資產，需知會） |
| 8 | 技術／產業世代 | — | — | 全缺 | 商用題材／供應鏈資料庫（授權未驗；需先定義範圍） |

---

## §5 Baseline 候選維度：「營收 YoY 中位數＋覆蓋率」的定位

- **定位（客戶裁示）**：**候選維度／baseline research**，不是正式產業趨勢，**不得**用於畫面「變強／轉弱」結論、不得進 Digest `industry_trend[]` 的方向欄、不得由 AI 引用為趨勢結論。
- **候選定義（僅供量測，非規則）**：單季化營收 → 個股單季 YoY（沿用 `revenue_yoy` 語意）→ 依官方產業別分組 → 取中位數；同時報告**覆蓋率**（有效 YoY 家數／產業家數）、**存活者偏誤旗標**、**期別**（公告季）、`sq_break` 排除數。
- **為什麼只是 baseline**：(1) 僅 2 個 YoY 點，無法談「趨勢」（INFERENCE）；(2) 單一維度（營收）；(3) 存活者偏誤；(4) 中位數對產業內分化不敏感；(5) 其他七項尚未盤點完。
- **本批做什麼**：RS-1 **只在報告中說明量測方法與預期的樣本結構**；若客戶要看實際量測值，需另批（**RS-2 候選，離線研究腳本、不進 production、不接線**，尚未提案，需客戶同意）。
- **最小樣本門檻（min n）**：屬新門檻（magic number），**本計畫不訂**；研究報告只呈現各產業家數分布，由後續 Gate 決定。

---

## §6 新外部來源研究（僅研究；官方優先）

> **硬性邊界**：不得接入 production、不得新增 API／MCP、不得註冊到 `data_registry`、不得改 `requirements.txt`；導入前另開 Customer Gate（v3 §03-2 ②；CLAUDE.md §2.1 來源註冊）。以下可信度層級對照 CLAUDE.md §2.1（T1 官方／T2 商用 API／T3 第三方網站）。**可信度、授權、成本皆為撰寫者已知、未驗證，研究報告須逐項查證後填入。**

| 候選 | 對應項 | 層級 | 可信度（待驗） | 授權（待驗） | 成本（待驗） | 研究要回答 | 是否含產業細分 |
|---|---|---|---|---|---|---|---|
| 經濟部統計處：工業生產指數、製造業銷售量值、外銷訂單 | 6 | T1 | 官方，高 | 政府開放資料，條款待查 | 免費（預期） | 有無穩定 API／檔案下載？產業細分程度？發布延遲與修正？ | 待查 |
| 財政部關務署／海關進出口統計（依貨品分類） | 6 | T1 | 官方，高 | 政府開放資料，待查 | 免費（預期） | 貨品分類與產業別如何對映（對映本身是新規則）？ | 待查 |
| TWSE 外資及陸資持股統計（日）／集保股權分散表（週） | 4 | T1 | 官方，高 | 待查 | 免費（預期） | 端點穩定性？可否取得產業或個股層歷史？repo 現僅單檔用 FinMind `TaiwanStockHoldingSharesPer`（FACT） | 個股層（可經對映聚合） |
| MOPS 現金流量表彙總（全市場） | 5 | T1 | 官方，高 | 待查 | 免費（預期） | 是否存在全市場彙總端點？舊季可回補？ | 個股層 |
| 更早季別 MOPS 損益彙總（回補 >6 季） | 1、2 | T1 | 官方，高 | 同現有 | 免費 | `update_fundamentals_snapshot.py --roc-year --season` 對舊季是否仍可用（FACT：腳本支援參數；舊季端點可用性＝未驗） | 個股層 |
| 官方類股指數歷史（TWSE／TPEx） | 3 | T1 | 官方，高 | 待查 | 免費（預期） | repo 標 `MI_INDEX` 永久停用（FACT：`daily_checklist.py:DISABLE_TWSE`）；是否有其他官方端點？推翻停用決策須另 Gate | 是（類股） |
| FinMind `TaiwanStockPrice`（逐檔價格，已登記）自算等權產業指數 | 3 | T2 | 中高 | 現有 token | 配額壓力 | 全市場逐檔歷史請求量估算；**屬新資料流（非新來源）** | 經對映 |
| CIER（中經院）產業細項指標 | 6 | T3 | 中，爬取穩定性差 | 待查 | 免費（預期） | 授權與穩定性；repo 現僅取總指數 | 是 |
| 商用題材／供應鏈資料庫、專利／技術分類資料 | 8 | T2/T3 | 未知 | 多為商用，待查 | 未知 | 是否可機械取得「世代」代理變數？**需先由客戶定義範圍** | 未知 |

**研究產出要求**：每個候選須填：端點／檔案 URL、格式、更新頻率、發布延遲、歷史長度、修正風險、授權條款（原文引用）、成本、穩定性觀察、與現有 `data_registry` 的衝突（CLAUDE.md §2.1「衝突裁決」：多源取第一命中、禁止平均）、PIT 對齊鍵。查不到者標 MISSING，不猜。

---

## §7 產出物與驗收標準

### 7.1 產出物
1. **研究報告** `docs/vnext/NEWUI_D25_RS1_REPORT_<日期>.md`（docs-only，本計畫核准執行後產出）。固定章節：
   1. 摘要（≤1 頁：八項的四分類結果、最重要的 3 個缺口、建議的下一個 Gate 選項並附推薦方案）
   2. 資料盤點表（八項 × 四分類，逐格附 FACT[檔:符號] 與抽查日）
   3. Baseline 說明（營收 YoY 中位數＋覆蓋率的量測方法、樣本結構、偏誤清單；**無趨勢結論**）
   4. 驗證結果（§4 各項「驗證方法」的執行紀錄與差異）
   5. 新來源評估表（§6 格式，逐項查證結果）
   6. 缺口與建議（供客戶 Gate：要不要補哪個來源、是否開 RS-2、是否開「正式產業趨勢規則」High Gate；**每個選項附推薦與具體原因**，不丟選擇題）
   7. 未驗證事項與盲點
2. 本計畫（本檔）若有事實更正，就地更正並標日期。

### 7.2 驗收標準（逐條可檢查）
- [ ] 八項皆有盤點，且每項有四分類結果（可為「無」，須明寫）
- [ ] 每個 FACT 附 `[檔:符號]` 與抽查日；未抽查者標 INFERENCE
- [ ] 「營收 YoY 中位數＋覆蓋率」全文僅以「候選維度／baseline research」稱之，無「產業趨勢」結論用語
- [ ] 全文無「某產業變強／轉弱／衰退／崛起」的結論句（除非是引用現有資金流象限並標明口徑）
- [ ] 新來源逐項標可信度層級／授權／成本，未驗者標「未驗」；無任何來源被接入、註冊或寫入 code
- [ ] 無新增 API／MCP、無 `requirements.txt`／`data_registry` 變更（`git diff --stat` 僅 docs）
- [ ] 承重 FACT（尤其「0 命中」「無歷史落地」）由**獨立一組**重驗並記錄
- [ ] 缺值語意：報告內的缺值一律寫 MISSING／⬜，不以 0 或「中性」代替
- [ ] 報告末列「未解事項」與「需客戶 Gate 的選項」，每個附推薦

### 7.3 批次屬性
- **docs-only 批次**；不過 boot import smoke（無 `.py` 變更）；走 docs QA／獨立複驗／CI／Auto-Ship。
- **DEC-084 最小 Model×Effort**：Sonnet＋Medium（需判斷的研究文件；非 Rule 1 機械性）。若實際研究需連網閱讀官方文件，沿用同配置。
- **派工（CLAUDE.md §-2）**：研究與稽核由不同組；FACT 重驗至少一組獨立；總管複驗全稱句。
- **不夾帶**：HI-1～HI-6、Risk Cap／門檻／權重／趨勢定義／估值公式、任何 production code。

---

## §8 AI 與 Digest 的限制（至正式產業規則完成為止）

1. Decision Digest `industry_trend[]` 在正式產業規則完成前，**不得**含方向結論（變強／轉弱／結構性變化）；各維度缺資料者 `status=missing`（`missing_reason=NOT_WIRED／NO_INPUT／NOT_DEFINED`），`rule_id／rule_version` 為 `null`。
2. One AI Brain 對「哪些產業變強／轉弱／發生結構性變化／下一個成長產業」一律回「**資料不足，無法判斷**」；可列的僅有**已存在**的資金流象限事實（須標「口徑：法人資金動能，非產業趨勢」）。
3. Grounding Validator（C §2.4 G1／G4）：AI 輸出若含 Digest 無對應欄位的產業方向宣告，整段退回規則式摘要。
4. 營收 YoY 中位數若日後被量測，其數值不得單獨出現在 AI 輸出的「結論句」；只能作為「依據」並標「候選維度」。

---

## §9 盲點與未驗證項

1. 全部 FACT 單組讀碼＋抽查，未獨立複驗；「無產業層聚合函式」「無歷史 PE 落地」「無供應鏈資料」皆為單組 grep。
2. 外部來源一律未連網驗證；§6 表格的可信度／授權／成本是預期值，不是查證結果。
3. `data_cache/` 讀的是 git 追蹤版；production 部署上的實際內容未驗。
4. 分類（可直接使用／需轉換／缺資料）為撰寫組判定，客戶可否決。
5. 「僅 2 個 YoY 點」為算術推得，未實際單季化驗證 `sq_break` 排除後的有效點數。
6. `daily_net.parquet` 48 個 sector 標籤與 `bubble_latest.json` 40 板塊的差距（別名併合？）本輪未逐一比對，沿用 C 的 40 板塊口徑。
7. 本檔未改任何 code／tests／導覽；未動 DECISIONS／BACKLOG／STATE／HANDOFF／wireframe（由別組處理）；未 commit、未 push。
