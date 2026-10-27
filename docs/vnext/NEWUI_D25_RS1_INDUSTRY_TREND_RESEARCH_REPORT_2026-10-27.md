# D2.5 RS-1｜產業趨勢研究報告（客戶 Q5，DEC-092）

- **日期**：2026-10-27　**基準**：main `beee6230`　**性質**：**研究報告（docs-only）**。0 程式碼、0 測試、0 導覽變更；**未導入 production、未接入任何新外部來源、未新增 API／MCP**。
- **對應計畫**：`docs/vnext/NEWUI_D25_RS1_INDUSTRY_TREND_RESEARCH_PLAN_2026-10-27.md`（本報告即其 §7.1 的產出物，驗收對照見 §9）。
- **證據標記**：
  - **FACT[檔:符號／實測指令]**＝本輪唯讀實測或讀碼所得；
  - **INFERENCE**＝由事實推得、未驗；
  - **MISSING**＝repo 查無，不猜；
  - **UNVERIFIED**＝外部來源，本輪未能連線或未讀原文。
- **誠實揭露（CLAUDE.md §-2 規則 6）**：本報告為**單組研究**（四個子研究 Ra／Rb／Rc／Rd 的彙整），**未經第二組獨立複驗**；沙箱**未連網**（官方站 `openapi.twse.com.tw`、`data.gov.tw`、`moea.gov.tw` 皆無法解析）；`data_cache/` 讀的是 **git 追蹤版**，非 production 部署上的實際內容。所有「沒有／查無／0 命中」皆為**待驗事項**，不可當成已證實的全稱句。
- **本報告不做的事**：不訂任何門檻、公式、權重、最小樣本數；不宣告任何產業「變強／轉弱／興衰／世代更替」；所有「建議」一律標 INFERENCE，且皆需客戶 Gate 同意才可行動。

---

## §1 一頁結論（給客戶）

**客戶的問題**：repo 現有資料，能不能判斷「產業長期是否正在變強、轉弱、或發生世代結構變化」？

**誠實答案：目前不能。** 現有資料只能做兩件事：

1. **baseline（基準觀察）**：把個股的單季營收年增率（YoY）按產業彙整成「中位數＋成長廣度＋覆蓋率」。這已實測可算，但**只有 2 個時間點**（115Q1、115Q2），無法形成序列，更談不上「長期」。
2. **資金動能觀察**：產業層的法人淨買超金額（億元），目前只有 **27 個交易日**（約 5 週，2026-09-11→2026-10-22）。這是「近期錢往哪走」，**不是**產業趨勢，也不是價格強弱。

**長期判斷尚缺什麼（重點三項，細節見 §6）**：

| 缺口 | 現況 | 為什麼重要 |
|---|---|---|
| **歷史長度** | 季報快照僅 6 季（114Q1～115Q2）；法人流量 27 日；估值只有當日值 | 6 季不足 2 個完整年度，分不出「景氣循環」與「結構改變」 |
| **產業層的價格與需求資料** | 無類股指數歷史；無產業別景氣／外銷訂單／工業生產指數；無產業層資本支出 | 營收與資金流只是「財務與籌碼面」，缺價格面與需求面交叉驗證 |
| **「世代結構變化」的資料與定義** | 11 項代理指標中僅 2 項可機械計算且各有偏誤；其餘需新資料或人工研究；客戶尚未定義範圍 | 世代更替是因果敘事，統計代理只能顯示「某些財務結構變了」，不能識別原因 |

**八項盤點一句話結果**（詳見 §2）：可直接使用的只有「個股單季營收 YoY」「產業法人資金流量（27 日）」「總體 PMI／M1B-M2」；其餘多為「需轉換」或「缺資料」。

**AI 的界線**：正式產業規則完成以前，One AI Brain 對任何產業興衰、強弱、世代變化的提問，一律回答「**資料不足／尚未定義**」（§8）。

**建議（INFERENCE，需客戶同意才開）**：先由客戶補「世代變化」的範圍與 2–3 個可事後驗證的歷史案例，並先做「官方端點可用性查證」與「歷史回補可行性評估」，再談正式規則（§7）。**目前沒有任何門檻或公式被定案。**

---

## §2 八項盤點總表

> 分類為撰寫組判定（單組），客戶可否決。「可直接使用」＝現有輸出已是產業層且口徑明確；「需轉換」＝個股層／原料齊但需新聚合（屬新規則模組，正式化前須 `rule_id＋版本＋獨立測試`，`PROJECT_RULES.md` §19.4）；「缺資料」＝現有資料無法支撐；「新來源候選」＝僅研究。

| # | 項目 | repo 既有可追溯資料 | 歷史長度與頻率 | 分類 | 主要偏誤 |
|---|---|---|---|---|---|
| 1 | 產業營收 YoY／成長廣度 | `data_cache/fundamentals/{sii,otc}_*.parquet` 的 `revenue`（年初至今累計）；`ytd_to_single_quarter`、`revenue_yoy`（個股）；`ticker_sector.json` | 6 季（114Q1～115Q2），季頻；**單季 YoY 僅 2 點** | 個股 YoY：**可直接使用**；產業中位數／廣度／覆蓋率：**需轉換**；產業序列：**缺資料** | 基期效應、極端值、存活者偏誤、小樣本產業、同義雙名未併、金融業無營收口徑 |
| 2 | EPS／獲利趨勢 | 快照 `eps／net_income／op_income／gross_profit`（皆累計） | 6 季；單季 YoY 同樣僅 2 點 | **需轉換**（EPS／淨利未單季化）；長期趨勢：**缺資料** | 虧轉盈 YoY 無定義（約 42% 檔）、股本變動、龍頭主導加總、存活者偏誤 |
| 3 | 產業相對強弱 | 法人資金流（`sector_flow/daily_net.parquet`）；`rs_leader_screener`（L2 純函式，對 `^TWII`）；10 檔代表股熱力圖 | 資金流 27 交易日；`twii_ohlcv` 2006 起（大盤） | 資金動能：**可直接使用**（口徑限定）；價格強弱：**缺資料**／**需轉換**；類股指數：**新來源候選** | 資金流≠價格趨勢；非類股指數；板塊標籤雙名；存活者偏誤 |
| 4 | 法人配置／籌碼 | 產業層外資／投信／自營淨買超（億元）；市場層 `finmind_inst`（僅外資一欄） | 產業層 27 日；市場層 2006 起 | 流量：**可直接使用**；存量（持股比重）：**缺資料**／**新來源候選** | 只有流量沒有存量；淨額以收盤價估金額；ETF 申贖混入；3 板塊資料缺 12～19 日 |
| 5 | 資本支出 | 單檔 FinMind CashFlows（`fetch_5_years_cash_flow`）；全市場季快照**無** capex 欄 | 單檔 5 年（僅 5 年加總，無逐年序列） | 全市場：**缺資料**；單檔：**需轉換**；MOPS 現金流彙總：**新來源候選** | 逐檔抓取配額壓力；缺值回 `0.0` 無法區分真零與缺；fuzzy 比對有誤加總風險 |
| 6 | 景氣／終端需求 | `tw_pmi.parquet`、`finmind_m1m2.parquet`；NDC（live 取數，未落地）；出口（僅單點 YoY） | PMI 2012-07 起（171 列）；M1B/M2 2006-11 起（238 列），皆月頻 | 總體 PMI／M1B-M2：**可直接使用**；NDC：**需轉換**；出口：**缺資料**；產業別需求：**缺資料**／**新來源候選** | 皆非產業別；NDC 預設只回 18 月；無外銷訂單／工業生產指數 |
| 7 | 估值 | `yield_pe_fetcher`（TWSE `BWIBBU_d`、TPEx）當日全市場 PE／PB／殖利率 | **只有當日值**，無歷史落地 | 當日產業中位數：**需轉換**；歷史分位：**缺資料**（需自行每日累積＝新資料資產） | 虧損股 PE 缺值導致母體偏向獲利公司；金融股口徑不同；中位數與市值加權差異 |
| 8 | 結構性技術／產業世代變化 | 無次產業／供應鏈／技術分類資料；毛利率、營收集中度可由個股資料算 | 6 季 | 11 項代理指標中 **僅 a3、a4 可機械算**（皆有偏誤）；其餘**缺資料**／**新來源候選**／需人工研究 | 代理變數≠世代變化；無法識別因果；存活者偏誤；客戶尚未定義範圍 |

---

## §3 逐項細節

### 3.1 產業營收 YoY 與成長廣度

**FACT 資料底座**
- FACT[`ls data_cache/fundamentals`]：12 個季快照檔（`{sii,otc}_{114Q1…115Q2}.parquet`）＋ `latest.json`（roc 115／season 2／updated 2026-09-18／total 1974）。
- FACT[實測 groupby]：每季股票數（上市＋上櫃）114Q1 1934；114Q2 1968；114Q3 1970；114Q4 1969；115Q1 1969；115Q2 1974。總 11,784 列，`(stock_id, roc_year, season)` 0 重複。來源 `MOPS:t163sb04`。
- FACT[實測 2330]：`revenue` 114Q1..Q4 = 0.84e9 / 1.77e9 / 2.76e9 / 3.81e9（逐季遞增，Q4＝全年），115Q1 = 1.13e9（重置）→ **損益欄為年初至今累計**，不可直接當單季。
- FACT[`cross_quarter_trends.py:ytd_to_single_quarter`、`YTD_FLOW_COLS`]：只單季化 `revenue／gross_profit／op_income`；單季營收 < 0 → NaN 並記 `sq_break`；不跨年相減；重複鍵 raise。
- FACT[實測 `sq_break` 計數]：114Q2 2、114Q3 3、114Q4 2、115Q2 1，其餘 0。

**實測：單季營收 YoY 只有 2 個時間點**
- FACT[算術＋實算]：快照最早 114Q1，114 年各季沒有 113 年基期，所以可算的單季 YoY 只有 **115Q1（vs 114Q1）與 115Q2（vs 114Q2）**。口徑與 `_revenue_yoy` 同式：單季／去年同季單季 − 1，分母 ≤ 0 → NaN。
- FACT[全市場，描述性統計，非門檻]：
  - 115Q1：有值 1,886 檔，中位數 +4.5%，YoY > 0 占 60.3%。
  - 115Q2：有值 1,884 檔，中位數 +9.7%，YoY > 0 占 68.7%。無值原因（115Q2）：當季單季 NaN 55、去年同季單季 NaN 84、去年同季單季 ≤ 0 共 1。
- FACT[極端值與基期效應]：115Q2 YoY 的 mean +63%、max +24,853%、min −100%、p1／p99 = −76%／+558%。**平均數不可用**；中位數與廣度較穩健，但仍受低基期影響。兩點之間多數產業 115Q2 中位數高於 115Q1，可能是基期（114Q2 較低）而非實質改變，**未驗**。

**實測：產業層聚合示範（115Q2；n＝快照股票數，n2＝有 YoY 檔數；僅為描述，不構成產業結論）**

| 標籤 | n | n2 | 覆蓋率 | YoY 中位數 | YoY>0 比例 |
|---|---|---|---|---|---|
| 半導體業 | 206 | 201 | 97.6% | +19.4% | 83.6% |
| 電子零組件業 | 210 | 208 | 99.0% | +19.1% | 75.5% |
| 電腦及週邊設備業 | 109 | 108 | 99.1% | +18.4% | 70.4% |
| 光電業 | 115 | 115 | 100% | +4.6% | 60.0% |
| 生技醫療業 | 159 | 148 | 93.1% | +5.9% | 64.9% |
| 水泥工業 | 7 | 7 | — | −8.6% | 14% |
| 金融保險業 | 9 | **1** | 11% | — | — |
| 金融保險（雙名之一） | 31 | **0** | 0% | — | — |

（其餘標籤見子研究 Ra 原表；此處節選，數字取自單組實算。）

**小樣本與標籤品質問題（FACT）**
- 快照 1,974 檔全部可在 `ticker_sector.json` 找到對映（獨立重驗：未對映為 0），對映到 **40 個標籤**。有效 YoY 檔數 n2 < 10 者共 **7 個標籤**（含 0 檔 YoY 的「金融保險」），n2 < 5 者共 **3 個標籤**（農業科技業 4、金融保險業 1、金融保險 0；另如玻璃陶瓷 5、水泥工業 7、造紙工業 7、運動休閒類 8 屬 n2 < 10）。此處的 10、5 只是**描述分群**，不是建議門檻。
- **同義雙名未併**：綠能環保(31)／綠能環保類(15)、數位雲端(22)／數位雲端類(18)、居家生活(15)／居家生活類(21)、運動休閒(19)／運動休閒類(8)、其他電子業(54)／其他電子類(41)、金融保險(31)／金融保險業(9)。未併前每個產業被切成較小樣本。（對照：`sector_flow` 層已有別名表 `SECTOR_CANONICAL_ALIASES`，見 §3.3；營收層尚未套用。）
- **金融業 `revenue` 為空**：金融保險 31+9＝40 檔，YoY 覆蓋合計僅 1/40。這代表「無營收口徑」，**不可補 0**，應標「口徑不適用」。

**成長廣度可否算**：可。YoY > 0 家數／有 YoY 家數已實算。repo 無現成產業聚合函式（單組觀察，未窮舉）。

**月營收更長序列？**
- FACT[`monthly_revenue_fetcher.fetch_batch_monthly_revenue`]：FinMind `TaiwanStockMonthRevenue` 全市場，`months=18` 預設；成功才快取（`TTL_6HOUR`），失敗退避；備援 TWSE／TPEx OpenAPI 只給最新單月快照。
- FACT[`git ls-files data_cache | grep -i rev|month` 無輸出；`scripts/export_stock_db.py:442–459` 的 `write_monthly_revenue` 呼叫 `fetch_batch_monthly_revenue`，以 `if_exists="replace"` 每日覆寫 SQLite `monthly_revenue` 表（`export_db.yml` 每日 21:00 UTC，force-push 到 data 分支）]：`data_cache` 無累積歷史；`export_stock_db.py` 每日覆寫一份近 18 個月快照（**非累積**）。
- INFERENCE：18 月只能得約 6 個月的 YoY（需 12 月基期）。`months` 參數可調大，但 FinMind 實際可回溯年限、全市場回應量與配額、月營收後續修正，**本輪未實抓＝MISSING**；月營收單位（元）與季快照（千元）口徑不同，需對帳，**未驗**。

### 3.2 EPS／獲利趨勢

- FACT：`eps`、`net_income` 為累計值，**未單季化**；差分技術上可算（`eps` 第 2 季減第 1 季可算檔數：114 年 1,934、115 年 1,966），但 repo 無現成函式。
- FACT[季數]：6 季，單季 YoY 同樣只有 115Q1、115Q2 兩點；不足 2 個完整年度。
- **虧轉盈 YoY 無定義的比例**：FACT[net_income 單季 YoY，115Q2 vs 114Q2]：全市場 1,934 檔有單季淨利；去年同季單季淨利 > 0 者 1,123（**58%**）；**虧損轉盈 442 檔**（基期 ≤ 0，YoY 無定義）；盈轉虧 84 檔。→ 約 **42% 的檔數無法算 YoY**，不可補 0；產業層結果會偏向「去年賺錢的公司」（倖存／選擇偏誤）。
- FACT[累計 net_income ≤ 0]：114Q2 累計 659 檔；115Q2 累計 460 檔。
- **股本變動**：FACT：以 `net_income／eps` 隱含股數，115Q2 對 114Q2 變動 > 5% 者 781／1,921 檔（獨立重驗得 824／1,964，兩者口徑未統一，僅作警示）。**但**淨利可能含非控制權益而 eps 為歸屬母公司，此比不等於股數，僅作警示；本輪**無法區分增減資與口徑差**。
- INFERENCE[聚合口徑]：EPS 為每股值，跨公司不可加總。可行口徑為 (i) 單季 EPS YoY 中位數／廣度（無定義者獨立計數）、(ii) 產業淨利加總（需先單季化）。兩者都有偏誤：中位數忽略規模、加總被龍頭主導（半導體業尤其）。
- **缺值語意**：FACT：`net_income` 為 int64，實測無 0 值，**無法從欄位區分「0」與「缺」**（缺會是整列不存在）；`eps` 無 NaN；`eps==0` 各季（114Q1～115Q2）10／8／1／3／14／5 檔。

### 3.3 相對強弱

- **法人資金動能（可用，口徑限定）**：
  - FACT[`daily_net.parquet`]：1,254 列、13 欄；**27 個交易日**（2026-09-11→2026-10-22）；每日 45–47 個板塊；標籤 **48 個**。13 欄無 NaN；缺值語意是「該日該板塊無此列」。
  - **48 → 40 別名併合**：FACT[`shared/sector_flow_thresholds.py:SECTOR_CANONICAL_ALIASES`（版本 z43-v1）]：8 個原始標籤併入同義標準標籤（上櫃ETF→ETF、金融保險業→金融保險、其他電子類→其他電子業、居家生活類→居家生活、運動休閒類→運動休閒、綠能環保類→綠能環保、數位雲端類→數位雲端、指數投資證券(ETN)→ETN）；48 − 8 = 40，與 `bubble_latest.json` 的 40 個板塊吻合。**直接對 `daily_net.sector` 做 groupby 會把同一產業拆成兩半。**
  - **單位**：`net_amt_yi`＝三大法人淨買超（張）×1000×收盤價（元），單位「億元」（FACT[`src/compute/sector_flow.py:compute_sector_daily_net`]）；外幣交易 ETF 已排除。為「淨額」，非買進／賣出分項。
  - FACT：泡泡圖定義（X＝近 5 日淨額合計；Y＝近 5 日均減前 5 日均；size＝近 20 日淨額絕對值）、3 個板塊 `unavailable`（化學生技醫療缺 19 日、未分類缺 12 日、受益證券缺 1 日），不可進排名。
- **非類股指數**：
  - FACT[`shared/sector_heatmap.py`：`TW_SECTOR_SINGLE_STOCK_PROXY=True`]：熱力圖僅 10 個產業、各以一檔代表股近似，不是類股指數。
  - FACT[`data_cache/` 清單]：無類股指數 parquet；TWSE `MI_INDEX` 類股指數已標「永久停用」；FinMind 無類股指數 dataset。
  - FACT：個股價格歷史非落地資料集（即時 fetch，約 1 年）；`data_cache/` 無全市場價格 parquet。
- **`rs_leader_screener`**：
  - FACT[`src/compute/screener/rs_leader_screener.py`，L2 純函式]：個股區間報酬對 `^TWII` 的相對強弱，RS(σ)＝(r_i − r_m)/σ_m，預設回看 60 交易日；基準是**大盤，不是產業**。
  - INFERENCE：函式只吃收盤價序列，故產業層聚合（對每檔 RS 取中位數／廣度）或餵入「產業指數序列」在技術上可行；但**需先有序列，且屬新規則模組**，口徑與門檻不在此定案。
- **偏誤**：資金流＝法人淨買超金額，不是價格趨勢，也不是持股存量；法人買超可與股價走弱並存。現值產業分類為官方現況快照，歷史換類與下市股不在內（存活者偏誤）。ETF 板塊的買賣超含申贖影響（INFERENCE）。

### 3.4 法人籌碼

- FACT[產業層]：外資／投信／自營淨買超（億元），27 日、40–48 個板塊；**只有流量，沒有存量**。
- FACT[市場層]：`finmind_inst.parquet` 4,929 列（2006-09-29→2026-10-22），僅「外資」一欄；`finmind_margin.parquet` 同為大盤總量。兩者 `metadata` 的 `last_error` 為「抓取結果為空」但 `last_updated` 為 2026-10-22，含義待查＝MISSING。
- FACT[個股級，即時、非落地]：`stock_chips_service.get_chips_readout`（近 20 日）、FinMind `TaiwanStockHoldingSharesPer`（單檔，近 60 天）、`chip_radar.py`（第三方網站，單檔週更）。
- MISSING[grep 零命中，單組]：外資持股比重／庫存張數（TWSE 外資持股統計類）、投信／自營庫存、產業層融資融券、集保全市場股權分散的落地。
- 更新機制：FACT[`scripts/update_sector_flow.py`＋`.github/workflows/update_sector_flow.yml`，cron `30 9 * * *` UTC，支援 `--bootstrap --days N`，預設 30]；git 首次提交 `daily_net` 為 2026-10-22。窗口外是否有更早可回補之上限，**未查**。

### 3.5 資本支出

- FACT[`tw_stock_data_fetcher.fetch_5_years_cash_flow`]：單檔、FinMind `TaiwanStockCashFlowsStatement`，只留 12 月（Q4 累計）年度列，取最近 ≤ 5 年；少於 3 年回 `insufficient_data`；`capex_5y` 是 5 年**加總**絕對值，**不含逐年序列**。
- FACT：capex 以約 25 個科目別名比對；別名 miss 時走 fuzzy（含「不動產／廠房／設備／Capital」等關鍵字之列**全數加總**）→ 有誤加總風險（INFERENCE）。
- FACT[`data_cache/fundamentals/*.parquet` 欄位]：僅 `stock_id／revenue／gross_profit／op_income／net_income／eps／market／roc_year／season／source／fetched_at／total_assets／total_liab／current_assets／total_equity`。**無 capex、無現金流、無固定資產、無合約負債欄**。
- FACT：個股 `capex_intensity`、`合約負債`、`固定資產(千)` 只在個股層（評分與 shortage_screener）；**全 repo 無產業層 capex 聚合函式、無 capex 歷史落地檔**（單組 grep）。`docs/PROJECT_STATE.md` 自述 AI／CSP capex 大盤層「不存在」。
- **缺值回 0.0 的風險**：FACT：`fetch_5_years_cash_flow` 以 `0.0` 作別名 miss 初值，`_sum` 回 `0.0` 無法區分「真零」與「科目缺」（INFERENCE：capex 真為 0 的公司會被當成缺資料）。**聚合前必須改為顯式缺值旗標**，否則會違反 CLAUDE.md §1。
- 配額：INFERENCE：產業聚合需逐檔 1 次 CF 呼叫（約 2,000 檔）；repo 註解稱全市場批次需 sponsor tier（`shortage_screener_service.py`）。實際額度＝MISSING。

### 3.6 景氣／終端需求

| 資料 | 落地 | 長度、頻率 | 分類 |
|---|---|---|---|
| 台灣製造業 PMI | `tw_pmi.parquet`（cron 每日更新） | 171 列，2012-07→2026-09，月頻 | 可直接使用（總體） |
| M1B／M2 | `finmind_m1m2.parquet`（CBC EF15M01） | 238 列，2006-11→2026-08，月頻 | 可直接使用（總體） |
| NDC 景氣燈號／領先指標 | **未落地**；live 取數 `tw_macro.fetch_business_indicator_series`，預設回 18 月 | 更長歷史是否可取＝MISSING | 需轉換 |
| 出口 | **未落地**；`macro_snapshot.fetch_export_block` 只回單一 `{yoy, date, source}`（海關總值 YoY） | 單點，無貨品別、無歷史 | 缺資料 |
| 外銷訂單／工業生產指數／製造業銷售量值 | **無**（grep 僅命中「非經濟部外銷訂單」的正名註解） | — | 缺資料／新來源候選 |
| 全球半導體銷售、出貨、CSP capex | **無** | — | 缺資料／新來源候選 |

- FACT：缺值語意合規——`fetch_export_block` 全敗回 `{'_err_export': ...}`，不捏造數值；NDC 失敗回 None＋錯誤標記；PMI 有 last-good 快照並標 `is_proxy`。
- 結論：PMI 與 M1B/M2 **都不是產業別**，不能直接拿來判斷單一產業的需求。

### 3.7 估值

- FACT[`yield_pe_fetcher.fetch_twse_yield_pe／fetch_tpex_yield_pe`]：TWSE `BWIBBU_d`＋TPEx `peratio_analysis`，欄位本益比／殖利率／股價淨值比，`TTL_1DAY`；**只取當日全市場一張快照**，未見保留日期欄＝MISSING。
- FACT：repo 無 PE／PB 歷史落地檔（`ls data_cache`、grep `TaiwanStockPER` 0 命中，單組）；季快照有 `eps`、`total_equity` 但**無股價、股數、市值**，無法離線回推歷史 PE／PB（INFERENCE）。
- FACT[docstring]：`BWIBBU_d` 殖利率空字串約 24%（2026-08-05 前 410 檔實測 99 檔空），已改為保留 NaN。虧損股本益比的實際缺值比例本輪**未實測**＝MISSING。
- INFERENCE[產業層偏誤]：虧損股 PE 缺值 → 只算正 EPS 母體（存活偏誤）；微利股極端 PE；金融股口徑不同；市值加權與中位數的差異；**單日值無法判斷貴或便宜，必須有自身歷史分位**。
- **新資料資產提示（需告知客戶）**：目前沒有歷史，若要有分位，只能**從開始每日累積那天起算**。這是一份新的資料資產（需長期維運、儲存與知會），屬新增資料流，須走 Gate。
- 與 DEC-071 大盤 EPS×PE 框架：兩者共用個股 EPS／PE 為底層素材，大盤層是單一序列、產業層是中間聚合；repo 兩者皆未實作。DEC-081 第 10 點禁止新增 EPS 來源，任何新 EPS／PE 來源須先經 Gate。

### 3.8 結構性技術／產業世代變化

**原則**：代理變數**不等於**世代變化本身；任何一項單獨或組合都不構成「世代更替」證據，其解讀需人工研究。

| # | 代理指標 | repo 現況 | 判定 |
|---|---|---|---|
| a1 | 研發費用率 | 快照無研發費欄；grep 0 命中（單組） | 需新資料；官方彙總是否含該欄＝UNVERIFIED |
| a2 | 資本支出／折舊比 | 僅單檔 CF；無折舊欄 | 需新資料（產業層） |
| a3 | 毛利率結構變化（分布漂移，非僅中位數） | `gross_profit／revenue` 有；個股層斜率已有 | **既有可算**（需新聚合）；僅 6 季，分不出週期與結構（INFERENCE） |
| a4 | 營收集中度（CR-n／HHI） | 個股 `revenue`＋對映可得 | **既有可算**（需新聚合）；僅涵蓋現存上市櫃，未上市與海外同業不在內，集中度被低估（INFERENCE） |
| a5 | 市占變化 | 需全產業分母 | MISSING |
| a6 | 成分股新進／退出 | 快照只含現存公司；對映為單時點 | 需新資料（歷史對映／下市名單） |
| a7 | 產業分類變動 | `industry_raw.json` 無歷史 | 需新資料（需累積各期對映） |
| a8 | 終端需求結構（如外銷訂單貨品結構） | 無產業別 | 需新來源 |
| a9 | 專利／技術分類事件 | 無 | MISSING；可得性與授權 UNVERIFIED |
| a10 | 重大訊息事件 | 無（新聞僅 T4 RSS，非數值） | 需新資料＋人工閱讀；文字事件無法機械歸類為「世代」 |
| a11 | 供應鏈／題材分類 | 無（計畫稱 grep 命中 4 檔，推測為說明字串，UNVERIFIED） | MISSING；第三方題材分類屬 T3 且主觀 |

**誠實界線**
1. 11 項中**可機械計算的僅 a3、a4**，且各有偏誤；a1／a2／a6／a7／a8 要新資料；a5／a9／a10／a11 無法由機械資料「判斷」世代變化，只能當人工研究的輸入。
2. 「世代更替」帶有因果與時間尺度（新技術取代舊技術）；統計代理只能顯示財務結構變了，**不能識別原因**。（INFERENCE）
3. 不得用 LLM 常識或訓練記憶宣告任何產業的興衰或世代交替；AI 一律回「資料不足，無法判斷」（§8）。
4. 客戶尚未定義範圍前，任何來源只評「是否可機械取得」，不評結論。事後可驗基準（客戶提供 2–3 個歷史案例）是評估代理指標「當時看得見嗎」的唯一辦法，**需客戶提供**。

---

## §4 baseline「產業單季營收 YoY 中位數＋覆蓋率」的定位

**定位（客戶 Q5 裁示）**：**候選維度／baseline research**。**不是**正式的產業趨勢；不得用於畫面的方向性結論、不得進 Decision Digest `industry_trend[]` 的方向欄、不得由 AI 引用為趨勢結論。

**已實測可行**（§3.1）：計算透明、口徑可追溯（`revenue_yoy`、`ytd_to_single_quarter` 既有）；中位數對產業內極端值較穩健；覆蓋率揭露缺值，符合 fail-loud；不依賴新來源。

**偏誤與限制（INFERENCE，除已標 FACT 者）**
1. 只有 2 個時間點，無法區分趨勢、季節與單次跳動（FACT）。
2. 存活者偏誤：快照只含現存公司，下市／合併公司缺席。
3. 單一維度（營收）：營收成長可由併購、匯率、價格上漲或一次性認列造成。
4. 中位數對產業內分化不敏感，丟失規模權重。
5. 小產業中位數不穩（FACT：7 個標籤 n2 < 10，含 0 檔 YoY 的「金融保險」）；非產業標籤、同義雙名、金融業口徑問題（FACT）。
6. 低基期使 YoY 失真（FACT：max +24,853%）。
7. 公告季、交易日、當日估值的 `as_of` 須分開（CLAUDE.md §2.3）。

**升級為正式規則所需六項要件，逐項對應客戶 Q2 裁示的六項**

> 說明：客戶 Q2 裁示指出，正式趨勢定義（台股趨勢、國際趨勢，另列 High Gate）需包含下列六項。Q5 的產業趨勢尚無獨立六項原文；子研究 Rd 稱手邊未見此六項原文，**本報告以 `docs/DECISIONS.md` DEC-092 Q2 條文為準補上**，並**類推適用**於產業趨勢（INFERENCE：此類推需客戶確認）。

| Q2 六項 | 對應 baseline 升級時至少要回答的問題（不訂數值） | 目前狀態 |
|---|---|---|
| ① 判斷資料 | 用哪些維度（營收只是其一）？是否多維合成？產業分類基礎（官方代碼／併雙名／排除非產業標籤）？ | 僅營收一維；分類有雙名問題；其餘七項多為缺資料 |
| ② 時間尺度 | 「長期」是幾季／幾年？短（季）、中（年）、長（多年）如何區分？結構變化須比 YoY 更長且排除景氣循環（INFERENCE） | 客戶未定義；現有資料僅 6 季 |
| ③ 規則／公式 | 中位數、加總、加權的取捨；廣度如何定義；樣本量下限；規則須有 `rule_id＋版本＋獨立測試` | **本報告不定**；屬 High Gate |
| ④ missing semantics | 缺值一律 MISSING／⬜，不補 0、不填中性；覆蓋率過低時輸出「資料不足」；`sq_break` 排除數揭露；金融業標「口徑不適用」；停業／新上市三態（CLAUDE.md §4.6） | 方向明確，但具體下限屬新門檻，待 Gate |
| ⑤ 驗證／回測 | 以公告日對齊避免 lookahead；處理存活者偏誤（含下市名單）；口徑敏感度；用客戶提供的歷史案例檢驗「當時看得見嗎」 | 缺歷史長度、缺下市名單、缺客戶案例 |
| ⑥ AI 可使用範圍 | AI 只能引用已完成規則的輸出與其 `rule_id／version`；規則完成前一律「資料不足／尚未定義」 | 已由客戶 Q5 裁示約束（§8） |

---

## §5 新外部來源候選表（僅研究，不得導入）

**共同限制**
- 沙箱 WebFetch 對 `openapi.twse.com.tw`、`data.gov.tw`、`moea.gov.tw` 皆無法解析；以下端點、欄位、頻率、歷史長度、授權條款**一律 UNVERIFIED**，部分描述僅來自 **WebSearch 摘要（二手，非原文）**。
- 依 CLAUDE.md §2.1：官方＝T1；FinMind／DBnomics／Yahoo＝T2；第三方網站＝T3。與既有源衝突時取第一命中、**禁止平均**。
- **全部新來源接入需另開 Customer Gate**（v3 §03-2 ②）；不得註冊 `data_registry`、不得改 `requirements.txt`、不得新增 API／MCP。
- 政府資料開放授權條款第 1 版（OGDL-Taiwan-1.0）：搜尋摘要指可重製、再授權、須標示來源；**未讀原文，對各資料集的具體條款 UNVERIFIED**。

| 候選 | 對應項 | 內容 | 頻率／歷史 | 取得方式 | 授權 | 成本 | T 級 | 整合複雜度 | 主要風險 | Customer Gate |
|---|---|---|---|---|---|---|---|---|---|---|
| **b-1** TWSE／TPEx OpenAPI 損益／資產負債彙總（t187ap06／07 系列、上櫃 mopsfin_*）及舊季回補 | 1、2、8 | 個股季損益、資產負債；是否含研發費、折舊欄＝UNVERIFIED | 季；歷史長度 UNVERIFIED（通常只給最新一期，INFERENCE）；腳本 `update_fundamentals_snapshot.py` 支援 `--roc-year --season`，舊季是否仍回傳＝UNVERIFIED | 官方 REST JSON | OGDL（摘要，UNVERIFIED） | 免費（預期） | T1 | 低（既有 fetcher 模式） | 欄位名變動；端點只存最新期；未公告修正（PIT 用公告日） | 需 |
| **b-2** MOPS 財報彙總／重大訊息／現金流量表彙總 | 5、8 | 全市場彙總報表；重大訊息為文字 | 季報理論可回補（UNVERIFIED）；全市場現金流端點是否存在＝UNVERIFIED | 網頁查詢／下載，非穩定 API；repo 既有 MOPS 備援 | UNVERIFIED | 免費（預期） | T1 | 中高 | 反爬、改版、流量限制；重大訊息需 NLP 屬 LLM 風險，不得據以宣告趨勢 | 需 |
| **b-3** 經濟部統計處：工業生產指數、外銷訂單、製造業銷售量值 | 6、8 | 產業別景氣與需求（細業別程度 UNVERIFIED） | 月（INFERENCE，依首頁發布）；歷史長度 UNVERIFIED | 資料庫查詢／檔案下載，格式 UNVERIFIED，可能需網頁抓取 | 多採 OGDL v1（摘要，UNVERIFIED） | 免費 | T1 | 中高 | 業別分類（行業標準分類）與 TWSE 產業別不同，對映是新規則；修正頻率；data.gov.tw 上「台灣經濟論衡附表」已停更不可用 | 需 |
| **b-4** 財政部／海關進出口，依貨品分類 | 6、8 | 摘要稱 data.gov.tw 有海關進出口通關貨物總值月資料集（CSV，NT$ 千元）及財政部統計處進出口貿易值（美元） | 月；HS 貨品細項是否開放下載＝UNVERIFIED | CSV 下載 | OGDL v1（摘要） | 免費 | T1 | 中高 | 貨品→產業對映為新規則；總值粒度不足以判斷產業內世代 | 需 |
| **b-5** TWSE 外資持股統計（日）／集保股權分散表（週） | 4 | 持股比重與庫存（存量） | 端點、歷史 UNVERIFIED | 官方開放資料 | UNVERIFIED | 免費（預期） | T1 | 中 | 端點穩定性；repo 目前僅單檔用 FinMind `TaiwanStockHoldingSharesPer` | 需 |
| **b-6** 官方類股指數歷史（TWSE／TPEx） | 3 | 類股價格指數 | UNVERIFIED | repo 標 `MI_INDEX` 永久停用（`DISABLE_TWSE=True`）；是否有其他官方端點 UNVERIFIED | UNVERIFIED | 免費（預期） | T1 | 未知 | 推翻停用決策須另 Gate；對世代議題價值低 | 需 |
| **b-7** 主計總處（DGBAS）、央行 | 6、8 | 產業統計、工商及服務業普查（五年一次，INFERENCE，未查證） | 低頻；端點、條款 UNVERIFIED | UNVERIFIED | UNVERIFIED | 免費（預期） | T1 | 未知 | 頻率低；對「較長期結構」可能較適合但查證尚未做 | 需 |
| **b-8** WSTS／SEMI 公開統計 | 6、8 | 全球半導體銷售（僅半導體、非台灣） | 月；WSTS 摘要稱 Historical Billings Report 可免登入下載（舊版快取頁，現行 UNVERIFIED） | 下載 | **站方聲明版權屬 WSTS，未經書面許可不得複製**（UNVERIFIED 是否現行）；SEMI 細表多需付費（UNVERIFIED） | 未知 | 類 T3（INFERENCE） | 中 | 轉載授權風險，不可入庫再顯示 | 需＋法務 |
| **b-9** FinMind（已註冊 T2）：`TaiwanStockPrice` 自算等權產業指數／CashFlows／MonthRevenue 長歷史 | 1、3、5 | 逐檔資料 | 視 `months` 參數；全市場可回溯年限 UNVERIFIED | 現有 token | 現有 | 配額壓力（逐檔約 2,000+ 請求） | T2 | 中 | 屬**新資料流**而非新來源；存活者偏誤；還原權息價是否還原本輪未核對 | 需（新增資料流） |
| **b-10** CIER 產業細項指標 | 6 | 產業細項景氣 | UNVERIFIED | 爬取 | UNVERIFIED | 免費（預期） | T3 | 高 | 爬取穩定性差；repo 現僅取總指數 | 需 |
| **b-11** 商用題材／供應鏈／專利資料庫 | 8 | 次產業、供應鏈、技術分類 | UNVERIFIED | UNVERIFIED | UNVERIFIED，多為商用 | 未知 | T2／T3 | 未知 | 題材標籤常為事後貼上（lookahead）；主觀分類 | 需；**建議客戶定義範圍前不評估**（INFERENCE） |

整合複雜度排序（INFERENCE）：b-1（低）< b-9（中，配額）< b-3／b-4（中高，抓檔＋對映）< b-2（高，網頁／文字）。

---

## §6 到「能判斷長期」至少還缺什麼

> 全部為 INFERENCE，屬研究建議；不構成門檻或公式。

**A. 歷史長度**
1. 季報：目前 6 季。至少要回補到 113Q1 以前，才能有 ≥ 6 個連續單季 YoY 點與 ≥ 2 年循環；是否要 3～5 年以涵蓋完整景氣循環，**由客戶定義「長期」後決定**。舊季端點可行性＝UNVERIFIED。
2. 法人流量：目前 27 日；季度、年度尺度不可談。
3. 價格面：產業層無任何長期序列（類股指數或自建）。
4. 估值：無歷史；**需從開始累積那天起算**。

**B. 頻率**
- 月營收累積檔（每月累積、含發布日 `as_of`；現況僅有 `export_stock_db.py` 每日覆寫的近 18 個月非累積快照）可補 YoY 點密度；前提是先驗 FinMind 可回溯年限與修正頻率。

**C. 資料資產（部分屬新資料資產，需告知客戶）**
| 資料資產 | 為什麼需要 | 是否為「新資料資產」 |
|---|---|---|
| 每日估值（PE／PB／殖利率）累積檔 | 才有產業估值的自身歷史分位 | **是**（長期維運、儲存、知會） |
| 月營收累積歷史檔（含 `as_of`；現有每日覆寫快照非累積） | 補 YoY 點密度 | **是** |
| 產業對映的歷史版本（各期 `ticker_sector` 快照）與下市名單 | 處理存活者偏誤、a6／a7 | **是** |
| 產業層價格指數（官方類股指數或自建等權指數） | 價格強弱 | 是（新資料流） |
| 資本支出的逐年／逐季序列與產業聚合（須用顯式缺值旗標） | 擴產與投資節奏 | 是 |
| 外資／投信持股比重與庫存、產業融資融券 | 存量，而非僅流量 | 是 |
| 產業別需求面序列（外銷訂單、工業生產指數等） | 總體 PMI 不能分產業 | 是（新來源） |

**D. 分類與口徑品質**
- 產業標籤正規化（併同義雙名、排除非產業標籤、金融業口徑排除）；
- 淨利單季化、股本／權益歸屬一致性、非經常性損益旗標；
- 財報事後修正與公告日對齊（PIT）。

**E. 客戶側定義**
- 「長期」「變強／轉弱」「世代結構變化」各自的時間尺度與觀察範圍；
- 2–3 個事後可驗的歷史案例（用於回測「當時看得見嗎」）。

---

## §7 建議 RS-2 後續研究（INFERENCE；皆需客戶同意才開；無任何門檻公式定案）

| 序 | 項目 | 內容 | 性質 | 推薦理由（INFERENCE） |
|---|---|---|---|---|
| RS-2a | 離線量測 baseline | 只報告各產業單季 YoY 的分布、家數、覆蓋率、`sq_break` 數；不下結論 | 離線腳本，不進 production、不接線 | 把本報告的示範量測做成可重現紀錄；風險最低 |
| RS-2b | 官方端點可用性查證 | 在**連得到官方站**的環境，查 b-1 舊季回補、欄位含不含研發費／折舊；b-3 細業別；b-4 HS 細項；逐項引用授權原文 | 純文件／探針，不接線 | 目前所有外部 UNVERIFIED，是下一步決策的最大不確定 |
| RS-2c | 客戶定義「世代變化」範圍＋歷史案例 | 工作坊形式，由客戶提供 2–3 個案例 | 需客戶參與 | 沒有它，a1～a11 不可評，是最關鍵的前置輸入 |
| RS-2d | 分類基礎品質 | 雙名併合、非產業標籤排除清單、`ticker_sector` 歷史版本累積可行性 | 評估＋設計 | 這是所有產業聚合的共同地基 |
| RS-2e | 長歷史取得方案評估 | FinMind 全市場配額估算 vs 官方回補；只估算，不實抓 | 評估 | 決定歷史長度是否可補與成本 |
| RS-2f | 回測方法學草案 | 存活者偏誤處理、PIT 對齊、口徑敏感度；不訂門檻 | 設計文件 | 屬正式規則 High Gate 的前置 |
| RS-2g | 授權／法務確認清單 | WSTS 類受限來源；OGDL 條款原文 | 文件 | 避免日後轉載風險 |

**總推薦（INFERENCE）**：先開 **RS-2c＋RS-2b**（客戶定義範圍＋官方端點查證）；RS-2a 為低風險附帶；其餘待前兩者結果出來再決定。**正式「產業趨勢」規則（High Gate）不建議在 RS-2b／RS-2c 完成前啟動。**

---

## §8 對 One AI Brain 的限制

在正式產業規則完成以前：

1. One AI Brain 對「哪些產業變強／轉弱／發生結構性變化／下一個成長產業」一律回覆「**資料不足／尚未定義，無法判斷**」；不得用常識、訓練記憶或單一指標補成結論。
2. 可列示的僅有**已存在**的資金流象限事實，且必須標示口徑：「**法人資金動能，非產業趨勢**」。
3. Decision Digest `industry_trend[]` 不得含方向結論；各維度缺資料者 `status=missing`（`missing_reason=NOT_WIRED／NO_INPUT／NOT_DEFINED`），`rule_id／rule_version` 為 `null`。
4. Grounding Validator：AI 輸出若含 Digest 無對應欄位的產業方向宣告，整段退回規則式摘要。
5. baseline 營收 YoY 中位數若日後被量測，其數值**不得單獨出現在 AI 結論句**，只能作為「依據」並標「候選維度」。
6. AI 可做的僅限：搬運已引用的事實、標示缺資料、解釋各維度的定義與限制。

---

## §9 驗收對照與盲點

### 9.1 計畫書 §7.2 驗收標準逐條對照

| 驗收標準 | 結果 | 說明 |
|---|---|---|
| ☑ 八項皆有盤點，且每項有四分類結果（可為「無」，須明寫） | 通過 | §2 總表、§3 逐項；無的格明寫「缺資料」或「—」 |
| ☑ 每個 FACT 附 `[檔:符號]` 與抽查日；未抽查者標 INFERENCE | 部分通過 | FACT 多附檔／符號或實測指令，抽查日統一為 2026-10-27；個別子項（如單季手算）僅用快照內部一致性，已在文中標明 |
| ☑ 「營收 YoY 中位數＋覆蓋率」全文僅以「候選維度／baseline research」稱之 | 通過 | §4 明定；示範表只作描述 |
| ☑ 全文無「某產業變強／轉弱／衰退／崛起」的結論句 | 通過（待複驗） | 數字僅為描述性統計；單組自查，需獨立複驗 |
| ☑ 新來源逐項標可信度層級／授權／成本，未驗者標「未驗」；無任何來源被接入 | 通過 | §5；皆 UNVERIFIED／預期值，未接入 |
| ☑ 無新增 API／MCP、無 `requirements.txt`／`data_registry` 變更（`git diff --stat` 僅 docs） | 通過 | 僅 docs 異動（本檔新增＋BACKLOG／HANDOFF／PROJECT_STATE 三份同步） |
| ☑ 承重 FACT（尤其「0 命中」「無歷史落地」）由**獨立一組**重驗並記錄 | 已完成一輪 | 已完成一輪獨立重驗（約 30 條，成立約 22、部分 3、已修正 4–5 條），仍為單組重驗，且僅讀 git 追蹤版 data_cache |
| ☑ 缺值語意：報告內缺值一律寫 MISSING／⬜，不以 0 或「中性」代替 | 通過 | 見 §3.1、§3.2、§3.5 |
| ☑ 報告末列「未解事項」與「需客戶 Gate 的選項」，每個附推薦 | 通過 | §7（RS-2 選項附推薦）、本節 9.2 |

### 9.2 需客戶 Gate 的選項（皆附推薦，INFERENCE）

1. **是否開 RS-2c（客戶定義範圍＋歷史案例）**：推薦開。理由：它是評估世代變化代理指標的唯一基準。
2. **是否開 RS-2b（官方端點查證）**：推薦開。理由：目前所有外部來源皆 UNVERIFIED，查證前不應談任何導入。
3. **是否同意類推 Q2 六項要件至產業趨勢**：推薦同意。理由：避免正式規則缺少 missing semantics 或驗證章節。
4. **是否同意「每日累積估值」「月營收落地」「對映歷史版本」等新資料資產**：推薦**暫緩**，待 RS-2b／RS-2e 結果出來後再提；需先告知客戶成本與維運責任。
5. **是否啟動正式「產業趨勢」High Gate**：推薦**暫不啟動**，待前述 1～2 完成。

### 9.3 盲點與未驗證項

1. 全部為**單組研究**（Ra／Rb／Rc／Rd 四個子研究彙整），僅經一輪單組獨立重驗（見 §9.1）；尤其「無產業層聚合函式」「無歷史 PE 落地」「無月營收累積歷史（export_stock_db.py 僅每日覆寫近 18 個月快照）」「無供應鏈資料」「grep 0 命中」皆為單組觀察，不可當全稱句使用。
2. **未連網**：外部來源的端點、欄位、頻率、歷史長度、授權、成本全為 UNVERIFIED；§5 部分內容來自 WebSearch 摘要（二手）。
3. 沙箱讀的是 **git 追蹤版 `data_cache/`**，production 部署上的實際內容未驗。
4. 實測數字（§3.1、§3.2）來自一次性唯讀腳本（子研究 Ra），**未對 MOPS 原文逐筆核對**；5 檔抽查僅比對快照內部一致性。
5. FinMind 實際回傳內容、科目覆蓋率、配額、月營收可回溯年限、NDC 可取歷史長度、BWIBBU_d 虧損股 PE 缺值比例，本輪皆未實打＝MISSING。
6. 「Q2 六項要件類推至產業趨勢」為本報告的類推（INFERENCE），需客戶確認；子研究 Rd 未見此六項原文，本報告以 `docs/DECISIONS.md` DEC-092 Q2 條文為準。
7. 分類（可直接使用／需轉換／缺資料）為撰寫組判定，客戶可否決。

---

## 附錄 A　工程細節與證據索引（供工程查核）

**A.1 主要檔案與符號**
- `src/compute/screener/cross_quarter_trends.py`：`ytd_to_single_quarter`、`YTD_FLOW_COLS=(revenue, gross_profit, op_income)`、`compute_cross_quarter_trends`（輸出 `revenue_yoy`、`sq_break`）。
- `src/compute/screener/rs_leader_screener.py`：RS(σ)＝(r_i − r_m)/σ_m；`RS_DEFAULT_LOOKBACK=60`、`RS_MIN_ALIGNED_ROWS=20`、版本 `rs_leader_v1`；σ 公式沿用 `src/compute/strategy/v5_modules.py:calc_relative_strength`。
- `src/compute/sector_flow.py:compute_sector_daily_net`；`shared/sector_flow_thresholds.py:SECTOR_CANONICAL_ALIASES`（z43-v1）；`src/data/sector_flow/reader.py:read_sector_flow_cache`。
- `scripts/update_sector_flow.py`、`.github/workflows/update_sector_flow.yml`（cron `30 9 * * *` UTC）。
- `scripts/update_fundamentals_snapshot.py`（`--roc-year --season`；來源 `MOPS:t163sb04`）。
- `shared/sector_heatmap.py`：`TW_SECTOR_SINGLE_STOCK_PROXY=True`。
- `shared/industry_codes.py:OFFICIAL_INDUSTRY_CODE_NAMES`：37 個官方代碼。
- `src/data/stock/monthly_revenue_fetcher.py:fetch_batch_monthly_revenue`（`months=18`）。
- `tw_stock_data_fetcher.fetch_5_years_cash_flow`；`financial_statements_fetcher`；`scoring_engine`（`capex_intensity`）。
- `yield_pe_fetcher.fetch_twse_yield_pe／fetch_tpex_yield_pe`；`macro_snapshot.fetch_export_block`；`tw_macro.fetch_business_indicator_series`。

**A.2 資料檔實測摘要（2026-10-27，git 追蹤版）**
| 檔案 | 列數 | 範圍 | 備註 |
|---|---|---|---|
| `data_cache/fundamentals/*.parquet`（12 檔） | 11,784 | 114Q1～115Q2 | 損益欄為年初至今累計；`latest.json` total 1,974 |
| `data_cache/sector_flow/daily_net.parquet` | 1,254 | 2026-09-11→2026-10-22（27 交易日） | 48 標籤；13 欄無 NaN |
| `data_cache/sector_flow/bubble_latest.json` | 40 板塊 | 窗口 20 日 | 3 板塊 unavailable；`n_absent_cells=32` |
| `data_cache/sector_flow/ticker_sector.json` | 3,167 筆 | 55 種標籤 | 含 ETF／ETN／其他等非產業標籤 |
| `data_cache/twii_ohlcv.parquet` | 4,903 | 2006-09-29→2026-10-22 | 大盤 |
| `data_cache/finmind_inst.parquet`／`finmind_margin.parquet` | 各 4,929 | 2006-09-29→2026-10-22 | 市場層；`finmind_inst` 僅外資一欄 |
| `data_cache/tw_pmi.parquet` | 171 | 2012-07→2026-09 | 月頻 |
| `data_cache/finmind_m1m2.parquet` | 238 | 2006-11→2026-08 | 月頻；`metadata.last_error`「抓取結果為空」含義待查 |

**A.3 本報告引用的實測指令類型**：`ls data_cache/...`、parquet groupby／dtypes／NaN 計數、`git ls-files data_cache | grep -i rev|month`、`grep -rn`（另 `scripts/export_stock_db.py` 經重驗補查） 於 `src/ shared/ scripts/`；皆為唯讀（python `-I`），repo 零寫入。
