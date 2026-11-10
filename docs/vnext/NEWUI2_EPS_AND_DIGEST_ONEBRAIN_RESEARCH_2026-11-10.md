# 大盤 EPS 預估研究 ＋ Digest Stage F／OneBrain Stage G 最小可驗收能力研究（2026-11-10）

> **性質**：docs-only 唯讀研究。授權：Issue #1121。基準：`origin/main` `f4d86b4f`。
> **不是**：施工授權、資料源核准、公式核准、Gate 裁示、`DEC-*` 條文。本檔**不新增**任何資料來源、API、公式、runtime，**不宣稱**任何估值或指數預測已可計算。
> **標註規則**：每個斷言標 **FACT**（附 `path:line` 或 `path::symbol`，讀碼或讀文件所得）／**INFERENCE**（撰寫組推論）／**RECOMMENDATION**（AI 推薦，**非客戶裁示**）。查不到寫 **NOT FOUND**；未能驗證寫 **NOT VERIFIED**。
> **揭露（`CLAUDE.md` §-2 規則 6）**：本檔為**單一研究組**產出，**沒有第二組獨立複驗**。全稱句（「全 repo 只有 X」「0 caller」）皆為 grep 結果，非窮舉證明，只能當待驗事項，**不得**當後續動作的前提。
> **未讀取**：Issue #1121 原文（本檔不連網）；「Stage F／G 暫列切換前置」之為客戶裁示，依派工規格轉述，**NOT VERIFIED 於 Issue 原文**。
> **不確定清單**見文末 §9。

---

# Part 1　大盤 EPS 預估（EPS×PE 大盤情境估值）

## 1.1 一句話結論

- **FACT**：大盤層 forward EPS／大盤 PE 在產品碼**不存在**；只有**個股層**的 EPS（財報）與個股 PE（TWSE／TPEX 日報）。出處：`docs/BACKLOG.md:637`（`VN1-MT-VALUATION`）、`docs/vnext/FINAL_UI_CONTRACT_FREEZE_2026-11-02.md:373`（grep `forward_?eps|NTM|FY20xxE|consensus|forwardPE` 於 `src`／`shared`／`scripts`／`app.py` 0 命中）。
- **FACT（本次複查）**：我重跑 `grep -rniE "forward_?eps|consensus|forwardPE|NTM" src shared scripts app.py` ＝ **0 命中**（`origin/main` `f4d86b4f`）。
- **INFERENCE**：因此現階段任何「大盤合理區間」數字都只能是**客戶提供或第三方來源的情境輸入**，不是 repo 算得出的結果。

## 1.2 repo 內既有的相關概念與位置（盤點）

| # | 概念 | 位置 | 狀態 | 證據 |
|---|---|---|---|---|
| 1 | 大盤 EPS×PE 為客戶研究框架之一，**維持 Research Gate**；EPS×PE ≠ 完整市場趨勢判斷 | `docs/BACKLOG.md:637`（`VN1-MT-VALUATION`）、`:921`（`DEC092-EPSPE-HIGH-GATE`，`not started`）、`:914`（`DEC091-EPSPE-HIGH-GATE` 舊列由前者承接）、`docs/vnext/MARKET_TREND_RESEARCH_BASELINE_2026-11-03.md:43,153-157` | FACT；Research，非 Approved | 同左 |
| 2 | Pending 子列：來源／公式 | `docs/BACKLOG.md:1378`（`MKT-RB-EPS-SOURCE`：repo 無此資料源）、`:1383`（`MKT-RB-FORMULA`：⛔ 由 EPS×PE 直接產生買賣 action、⛔ productionize） | FACT；Pending／High Gate | 同左 |
| 3 | 另兩列相關 | `docs/BACKLOG.md:639`（`VN1-MT-CAPEX-EPS`，capex→EPS 傳導，Research）、`:1228`（`FUI-FORWARD-EPS-SOURCE-GATE`，P3，Forward EPS 資料源不存在→不可呈現，需新資料源 Decision Gate） | FACT | 同左 |
| 4 | 舊 UI 圖 C（市場頁） | `src/ui/views/_market_blocks.py:147-153`：`CHART_C_TITLE`「圖C 💰 大盤合理區間」、`CHART_C_TAG`「研究框架，未啟用」、`CHART_C_EMPTY`「需先核准：EPS 資料來源、PE 情境、計算公式、更新頻率。核准前這個區塊不畫任何圖形、區間或指數位置。」；`:1330-1334` 渲染只畫標題＋chip＋第一句；`:1324` 摺疊「來源」＝「此區塊未啟用，沒有使用任何資料」 | FACT：**空槽**，不畫任何圖 | 同左 |
| 5 | 客戶歷次裁示的邊界 | `docs/DECISIONS.md:2693`（DEC-081）第 10 點「本批禁止：…新增 EPS 來源…」；DEC-092 設計方向核准（保留 Research Framework，正式公式仍需 High Gate）：`docs/BACKLOG.md:914,921`；DEC-009 新資料源＝必須停下裁示：`docs/DECISIONS.md:86-88` | FACT | 同左 |
| 6 | 估值三層的語意區隔 | `valuation_level` 參數存在但**無人產生**：`src/compute/risk/risk_radar.py:522`（參數）、`:546`（docstring「便宜／合理／偏貴／極貴」）、`:669-683`（overlay）；`grep -rn valuation_level src shared` 僅此檔命中 | FACT：介面存在、資料源 NOT FOUND | 同左 |
| 7 | Digest 契約的固定態 | `src/services/decision_digest_builder.py:422`：`valuation=DefinitionSection(definition=DefinitionState.RESEARCH_ONLY)`；`:35` 註明「永遠是 AB-0 固定的定義狀態段，不填」 | FACT：Digest 內估值段永遠 RESEARCH_ONLY | 同左 |
| 8 | 情境估值的研究素材（**非資料源**） | `docs/vnext/NEWUI2_XIAO_PDF_MARKET_RESEARCH_EXTRACTION_2026-11-06.md:21-24`：簡報 P42 引凱基 EPS×本益比矩陣（2027 獲利年增 0～35%、PE 15～21、情境指數約 29,523～56,862，來源標註「凱基整理與預估，2026/8/11」）；形式 `ScenarioIndex(g,pe)=EPS_base*(1+g)*pe`；**「未取得正式 EPS_base/forward EPS 時，絕不能用簡報情境數字填入正式市場趨勢或 Risk Cap」**；`:57-60`「沒有提供 repo 可自動更新的合法大盤 forward EPS 時序」 | FACT：該檔已被標為「歷史／研究材料，不是現行施工依據」（`:1-3`） | 同左 |
| 9 | OneBrain 對大盤 EPS 的處理 | `docs/vnext/ONEBRAIN_EVIDENCE_COVERAGE_SCHEMA_CANDIDATE_2026-11-06.md:§五`「大盤 EPS×PE：若無大盤 forward EPS 的正式來源，研究情境只能保留 assumptions、來源、期別、估值倍數和完整性狀態，不能提供正式價位」 | FACT（候選草案，未核准 schema） | 同左 |

## 1.3 已存在的資料表／欄位（皆為**個股層**，無大盤層）

> 下表只列「已存在」者。**沒有任何一列是大盤層 EPS 或 forward EPS。**

| 資料 | path::symbol | 欄位／單位 | 頻率 | as_of／公告日 | PIT 風險 | 證據 |
|---|---|---|---|---|---|---|
| **A. FinMind 季損益表（單檔）** | `src/data/core/financial_statements_fetcher.py::fetch_financial_statements`（dataset 常數 `DATASET_INCOME_STATEMENT="TaiwanStockFinancialStatements"`，`:31-33`）；EPS 取值 `:263-265`（別名清單：`BasicEarningsPerShare`／基本每股盈餘／稀釋每股盈餘…），最新季 `_lat = _dates[-1]`（`:161`）；輸出 `"EPS": round(eps_v,2)`（`:650`） | EPS：**元／股**（FinMind long-form 季值） | 季 | 列日期＝`date`（FinMind 季別日期）；**無公告日欄** | **有**：以季末日對齊、非公告日；見 §1.4 | 同左 |
| **B. 缺貨選股用季序列** | `src/data/stock/quarterly_financials_fetcher.py`（docstring `:1-22`、記錄 `"date": _d` `:205`） | 營收／毛利／成本／合約負債／存貨（**無 EPS 欄**於此檔輸出）；FinMind 季值**一律視為單季**（`:19-22` 的專案假設） | 季 | `date`＝季別日期，**無公告日** | 同上 | 同左 |
| **C. 個股 TTM EPS（河流圖／PE 區間判讀）** | `src/ui/tabs/tab_stock_picker.py::_check_pe_zone`（`:839-861`，「近 4 季 EPS 加總」，不足 4 季回 ❓）；`src/ui/tabs/stock_sections/section_357_valuation.py:318-320`（`rolling(4,min_periods=4).sum()` 為逐季 TTM EPS） | EPS（元）→ 4 季加總＝**trailing** | 季→逐日河流 | 無公告日對齊 | **有**（同 A） | 同左 |
| **D. 全市場 MOPS 季快照** | `src/data/stock/mops_bulk_fetcher.py::fetch_mops_income_bulk`（`:190-194`；EPS 欄位別名 `:51`；輸出帶 `roc_year`／`season`／`source`／`fetched_at`，`:183-187`）；落地 `data_cache/fundamentals/{sii,otc}_{民國年}Q{季}.parquet` ＋ `latest.json`（欄位 `roc_year`／`season`／`updated_at`／`coverage`） | EPS：**年初至今累計**（Q2＝上半年、Q4＝全年；`src/compute/screener/cross_quarter_trends.py:7-9`）；營收等金額單位**千元**（同檔 `:11-12`） | 季 | `updated_at`（批次寫檔時戳）＋`fetched_at`；**無逐檔公告日** | **有**，且與 A 的「單季」口徑**不一致**（見 §1.4 (c)） | 同左；parquet 實際欄位 **NOT VERIFIED**（本環境無 pyarrow，未能開檔） |
| **E. 個股 PE／殖利率／PBR（TWSE／TPEX 日報）** | `src/data/stock/yield_pe_fetcher.py`：`TWSE_BWIBBU_URL`＝`openapi.twse.com.tw/v1/exchangeReport/BWIBBU_d`（`:58`）、`TPEX_PERATIO_URL`（`:60`）；欄位 `PEratio→本益比` 等（`:130-135`）；`@st.cache_data(ttl=TTL_1DAY)`（`:103,179`）；`fetch_pe_name_maps` 本益比 ≤0 不放 key（`:259`） | 本益比：**倍**；官方 trailing 定義＝**NOT VERIFIED**（repo 內無該官方定義文字） | 日（交易日盤後） | 官方日報日期；repo 取數不保存歷史序列（僅 TTL 1 天快取） | 低（官方當日值）；但**無歷史序列** → 無法在 repo 內做歷史 PE 分位 | 同左 |
| **F. 來源登錄表** | `src/data/core/data_registry.py:155`（TWSE 個股 PE／殖利率／PBR）、`:266-270`（FinMind「季財報（IS）」，`usage:'EPS / 毛利率 / 營業利益率'`） | — | — | — | — | 同左 |

- **INFERENCE（小瑕疵）**：`data_registry.py:267` 登錄的 identifier 為 `TaiwanStockFinancialStatement`（單數），而 fetcher 常數為 `TaiwanStockFinancialStatements`（複數，`financial_statements_fetcher.py:33`）。哪一個是 FinMind 官方正名＝**NOT VERIFIED**（不連網）。僅作登錄表一致性待查，本檔不處理。

## 1.4 缺口與 PIT（Point-in-Time）問題

**缺的是什麼（FACT／INFERENCE 分開）**

| # | 缺口 | 類別 | 說明 |
|---|---|---|---|
| a | 大盤層 **forward EPS（預估值）**來源 | FACT：NOT FOUND | 1.1 的 grep 0 命中；`docs/BACKLOG.md:1378` 明寫 repo 無此資料源。 |
| b | 大盤層 **trailing EPS／指數 PE** 來源 | FACT：NOT FOUND（於 repo） | 我只找到個股 PE（E）。**加權指數本身的 PE 或 EPS 時序**在 repo 內 `grep` 不到；官方是否提供＝**NOT VERIFIED**（不連網）。 |
| c | 把個股 EPS 聚合成大盤 EPS 的方法 | INFERENCE | 需要：成分權重（指數權重或市值）、指數除數／成分調整、單季 vs 累計的口徑統一。**repo 內無任何一項**（成分權重＝NOT FOUND）。自行聚合＝新公式＋新資料語意＝Decision Gate（DEC-009）。 |
| d | PE **情境**（合理倍數區間） | FACT：未定義 | `CHART_C_EMPTY` 明寫需先核准「PE 情境」；客戶未給定。簡報的 15～21 倍只是講者／券商的素材。 |
| e | **歷史 PE 序列**（若要做分位） | FACT：NOT FOUND | E 只有當日值＋TTL 快取，沒有落地歷史（`yield_pe_fetcher.py:103,179`）。 |
| f | 更新頻率與責任歸屬 | FACT：未定義 | 同 `CHART_C_EMPTY`。 |

**PIT／時間點問題**

| # | 問題 | 類別 | 內容 |
|---|---|---|---|
| (a) | **EPS 修正** | INFERENCE | 預估 EPS 隨時間被上修／下修；若不保存「預估當時的值＋預估日」，之後回看會把後來的修正值當成當時已知（lookahead）。repo 現有 EPS 路徑全部是「抓當下最新」，**不保存 vintage**（grep `vintage`／`revision` 於 EPS 路徑 **NOT FOUND**）。參照：`CLAUDE.md §2.3`「FinMind 季財報＝審計修正」。 |
| (b) | **公告日 vs 季末** | FACT＋INFERENCE | FACT：A／B／C 以 FinMind 季別日期（`"date": _d`，`quarterly_financials_fetcher.py:205`）對齊，欄位中**無公告日**（本次 grep `公告|announce|release_date|PIT` 於 `quarterly_financials_fetcher.py`／`financial_statements_fetcher.py`／`mops_bulk_fetcher.py`／`fundamentals_snapshot_loader.py` ＝ **0 命中**）。`CLAUDE.md §2.3`／§6 要求季財報用「公告日」（約季後 45 天）對齊。INFERENCE：把這些季值直接放進任何「歷史上某日的大盤 EPS」會 lookahead。 |
| (c) | **單季 vs 累計口徑不一致** | FACT | A／B／C 視 FinMind 季值為「單季」（`quarterly_financials_fetcher.py:19-22`）；D 的 MOPS EPS 為「年初至今累計」（`cross_quarter_trends.py:7-9`）。兩者**不可直接混加**；任何聚合前必須先統一口徑（D 欄的 EPS 專案內「不單季化」：`cross_quarter_trends.py:16`）。 |
| (d) | **預估期別** | INFERENCE | 「2027 年 EPS」「NTM」「FY」不同期別不可混；簡報素材也只標年度。需 `period_kind`（point／quarter／TTM／forward）——與 `ONEBRAIN_EVIDENCE_COVERAGE_SCHEMA_CANDIDATE` §二一致。 |
| (e) | **預估日 vs 抓取日** | INFERENCE | 簡報矩陣標「2026/8/11」，抓取日是之後；兩者必須分欄（`CLAUDE.md §2.2` 的 `as_of` ≠ `fetched_at`）。 |
| (f) | **成分口徑** | INFERENCE | 「加權指數成分」vs「全上市櫃」會得出不同 EPS；簡報素材 `EPS_base` 的「成分口徑必須由合法源提供」（研究摘要 `:24`）。 |
| (g) | **幣別／單位** | FACT | 個股 EPS 為「元／股」；指數是「點」，二者之間沒有 repo 內的轉換因子（見缺口 c）。 |

## 1.5 若未來客戶要做：需客戶裁示的 Decision Gate 與方案比較

> **前提（FACT）**：以下每一項都落在 `docs/DECISIONS.md:86-88`（DEC-009）「新／替換資料來源」「新投資公式」「新資料語意」之內，且 `docs/BACKLOG.md:921`（`DEC092-EPSPE-HIGH-GATE`）規定「EPS 資料來源／PE 情境／計算公式／更新頻率須經正式 High Gate」。**本節是方案研究，不是送題；客戶尚未指派。**
> **RECOMMENDATION 標示**＝AI 推薦，**非裁示**。

### Gate E-0：要不要啟動

| 方案 | 優點 | 缺點 | 風險 |
|---|---|---|---|
| E-0-a **維持現況（Research 空槽）** | 零風險；與 DEC-081 第 10 點、DEC-092 完全一致；圖 C 已誠實顯示「未啟用」 | 客戶研究框架（EPS×PE）無法被產品使用 | 無 |
| E-0-b **只做文件級研究批**（把來源候選、口徑、PIT 設計寫清楚，不寫 code） | 為 High Gate 備好可裁示的題目；不產生任何資料或畫面 | 有人力成本；仍不能用 | 低：若寫成「已可計算」會誤導（本檔已禁） |
| E-0-c **直接開 High Gate 做 MVP** | 最快見到畫面 | 來源／公式／PE 情境都未定，MVP 易變成「示意值上線」；違反 `docs/BACKLOG.md:914` 的「不做：以示意值上線」 | 高 |

**RECOMMENDATION（AI 推薦，非裁示）**：E-0-a 為預設；客戶若要推進，走 E-0-b，先把 E-1～E-4 的題目送審。

### Gate E-1：EPS 資料來源（＝新資料源 Gate；`MKT-RB-EPS-SOURCE`）

| 方案 | 優點 | 缺點 | 風險／成本 |
|---|---|---|---|
| E-1-a **客戶／總管手動輸入一組情境假設**（EPS_base、成長率 g、PE 區間皆為「使用者輸入」，每個輸入附來源、預估日、期別） | 不需新外部 API；可追溯到客戶提供的來源；符合「不自估 EPS／PE」（`docs/BACKLOG.md:637`） | 要人工維護；不能自動更新；輸入需 UI／儲存位置（屬新功能，需 Gate） | 中：輸入錯誤無法由 repo 驗證；須標「客戶輸入、未驗證」 |
| E-1-b **第三方一致預期（付費或授權資料）** | 自動、涵蓋廣、有修正歷史（若授權包含） | 新付費來源＝Secret／Cost／Provider Gate；授權與再散佈條款未知（**NOT VERIFIED**）；T2 商用聚合分級（`CLAUDE.md §2.1`）需 key | 高：成本、授權、來源穩定性；repo 目前無此類 vendor |
| E-1-c **官方來源的大盤／指數 trailing 資料**（若存在） | 官方（T1）、可追溯 | 只有 trailing，不是「預估」；是否存在、欄位、歷史長度＝**NOT VERIFIED**；無 forward | 中：可能滿足「現況」但無法回答「預估大盤」 |
| E-1-d **由個股 EPS 自行聚合** | 理論上完全自控 | 缺成分權重與指數除數（見 §1.4 c）；個股 forward EPS 也不存在；口徑不一致（§1.4 c）；等同自創公式 | 高：極易產生「看似精確、實為自估」的數字；與 `docs/BACKLOG.md:637`「⛔ 不自估 EPS／PE」衝突 |

**RECOMMENDATION（AI 推薦，非裁示）**：若客戶要做，先選 **E-1-a**（客戶輸入、明標來源與預估日）；E-1-c 作為並列的「可行性查證」項（先查官方是否有、不先做）；**不推薦 E-1-d**。E-1-b 屬成本題，待客戶有預算意願再提。

### Gate E-2：EPS 口徑

候選維度（客戶選）：(i) trailing（TTM）vs forward（NTM／年度）；(ii) 加權指數成分 vs 全上市櫃；(iii) 單季累計口徑統一規則；(iv) 修正歷史是否保留。

| 方案 | 優點 | 缺點 | 風險 |
|---|---|---|---|
| E-2-a **只顯示來源給定的原始期別，不轉換** | 不引入換算公式 | 不同來源期別可能無法並列 | 低 |
| E-2-b **統一成「年度 forward」並自行滾動** | 與券商情境表一致 | 需要滾動／加權公式＝新公式 | 高 |
| E-2-c **只用 trailing** | 可用官方日報類資料 | 不是「預估」，與客戶 A1「EPS 預估大盤」定位可能不符（**客戶意圖 NOT VERIFIED**） | 中 |

**RECOMMENDATION**：E-2-a。

### Gate E-3：PE 情境

| 方案 | 優點 | 缺點 | 風險 |
|---|---|---|---|
| E-3-a **客戶自訂 PE 區間（含理由）** | 最可追溯；不會被誤認為 repo 計算 | 主觀；需 UI 輸入 | 低～中 |
| E-3-b **歷史 PE 分位** | 較客觀 | repo 無歷史 PE 序列（§1.4 e）；需新資料落地＝新資料源；又有 PIT 與口徑問題 | 高 |
| E-3-c **直接採券商矩陣的 PE 範圍（15～21）** | 立即可用 | 來源是第三方簡報、時點是 2026/8；`NEWUI2_XIAO_PDF…:24` 已明禁填入正式市場趨勢或 Risk Cap | 高 |

**RECOMMENDATION**：E-3-a（若與 E-1-a 同批）。

### Gate E-4：計算公式（＝`MKT-RB-FORMULA`，High Gate）

候選形式（**研究素材中的形式化，非核准公式**）：`ScenarioIndex(g, pe) = EPS_base × (1+g) × pe`（`NEWUI2_XIAO_PDF…:24`）。

| 方案 | 優點 | 缺點 | 風險 |
|---|---|---|---|
| E-4-a **僅顯示「情境表」（EPS_base、g、pe 皆為輸入，輸出為乘積格）** | 公式極簡、可 property-test | 仍是新公式，需 Gate；輸出不得被當預測 | 中：表格易被誤讀為目標價 |
| E-4-b **加入區間判讀（便宜／合理／偏貴）** | 與舊圖 C 文案相容（`_market_blocks.py:149`） | 判讀門檻＝新投資語意 | 高（會撞 `valuation_level` 語意，見 §1.2 #6） |

**RECOMMENDATION**：E-4-a，且輸出標「情境假設，非預測」。

### Gate E-5：更新頻率與 PIT 規則

候選：事件驅動（每次客戶更新輸入）／月／季。必須同時裁示「是否保存每次輸入的 vintage（預估日＋值）」。**RECOMMENDATION**：事件驅動＋保存 vintage（append-only），避免之後回看被修正值污染。

### Gate E-6：呈現與耦合範圍（UI 與 Risk Cap）

| 方案 | 說明 | RECOMMENDATION |
|---|---|---|
| E-6-a 僅在既有「圖 C」槽內顯示（不增減版面元件） | 若新增輸入控制項則屬版面異動，需文字線框先行（`CLAUDE.md §-1.5.D` v3 §03-2 ①） | 推薦起點 |
| E-6-b 與 Risk Cap／趨勢／行動耦合 | **不可**（見 §1.6） | 不推薦 |

## 1.6 明確的「不可做」清單（DEC-081 邊界與同向裁示）

> **FACT**：下列各項皆有 repo 文件出處；**⛔ 在客戶開 High Gate 並核准前一律不可做**。

1. ⛔ **新增 EPS 來源**（DEC-081 第 10 點；`docs/DECISIONS.md:2693` 區段；DEC-009 新資料源 Gate `docs/DECISIONS.md:86`）。
2. ⛔ **自行估算 EPS／PE／forward EPS**（`docs/BACKLOG.md:637`「⛔ 不自估 EPS／PE」；`:1378`「⛔ 不得自估或使用示意值」）。
3. ⛔ **以示意值或簡報情境數字上線**（`docs/BACKLOG.md:914,921`；`NEWUI2_XIAO_PDF…:24`「絕不能用簡報情境數字填入正式市場趨勢或 Risk Cap」）。
4. ⛔ **由 EPS×PE 直接產生買賣 action／productionize**（`docs/BACKLOG.md:1383`）。
5. ⛔ **併入 Risk Cap 計算、scoring eligibility、Required Core、公式、權重、門檻**（DEC-081 第 10 點）。
6. ⛔ **自行定義「台股趨勢」並以 EPS×PE 當結論**（EPS×PE ≠ 完整市場趨勢判斷，`docs/vnext/MARKET_TREND_RESEARCH_BASELINE_2026-11-03.md:157`；`VN1-MT-TREND-DEF` blocked-on-customer，`docs/BACKLOG.md:635`）。
7. ⛔ **把 `risk_radar.synthesize_dual_verdict` 的 `valuation_level` 接上任何自產值**（`src/compute/risk/risk_radar.py:522`；無人產生，`docs/BACKLOG.md:637`）。
8. ⛔ **把缺資料當 0／中性**（`CLAUDE.md §1`；`ONEBRAIN_AI_GOVERNANCE_2026-10-31.md` G2）。
9. ⛔ **在 Digest 內把 `valuation` 從 `RESEARCH_ONLY` 改成已定義**（`src/services/decision_digest_builder.py:422`；`docs/vnext/DECISION_DIGEST_CONTRACT_vNext_2026-10-29.md` §5「`DefinitionSection` 綁定…估值＝`RESEARCH_ONLY` 直到正式 Gate」）。
10. ⛔ **讓 OneBrain 讀到或推論大盤 EPS 數字**（Stage G 前不存在；AI 不得創造數字，`ONE_AI_BRAIN_BOUNDARY_vNext_2026-10-29.md` §3）。
11. ⛔ **刪舊 UI／刪舊圖 C 空槽**（DEC-081 第 10 點；DEC-019／020）。
12. ⛔ **以講師姓名命名 UI 文案**（`NEWUI2_XIAO_PDF…:3` 補註：研究材料非 UI 文案）。

## 1.7 Part 1 小結（FACT／INFERENCE／RECOMMENDATION）

- **FACT**：大盤層 EPS／PE／forward EPS＝**NOT FOUND**（產品碼）；個股層 EPS（FinMind／MOPS）與個股 PE（TWSE／TPEX）存在但**無公告日、無 vintage、單季／累計口徑並存**。
- **INFERENCE**：即使客戶批准，也**不能**用現有個股資料「聚合」出大盤 forward EPS；必須先有來源 Gate。
- **RECOMMENDATION**：維持 Research 空槽；若客戶要推進，先走「客戶輸入情境、明標來源與預估日、只顯示情境乘積表、不接 Risk Cap／行動」的最小路線，並保存 vintage。

---

# Part 2　Digest Stage F／OneBrain Stage G（及 H、I）最小可驗收能力研究

> **關於前置規則**：派工規格載明「**Stage F／G 暫列切換前置**」是客戶於 Issue #1121 的裁示。**本檔不改前置規則**，也不重新詮釋它。對照 FACT：`docs/vnext/NEWUI2_MIGRATION_CUTOVER_CONTRACT_2026-11-02.md:53` 原寫「AI 總管讀法：是…客戶可推翻；接近 cutover 時若欲讓 F／G 不再是前置…另送客戶裁示」——與派工所述裁示方向一致；Issue 原文 **NOT VERIFIED**。

## 2.1 F → G → H → I 各 Stage 定義與現況

**定義（FACT：`docs/BACKLOG.md:1201-1204`；順序依賴同列「依賴」欄）**

| Stage | 定義（BACKLOG 原意摘要） | 依賴 | 建議 Effort／備註 |
|---|---|---|---|
| **F** Headless Decision Digest | Pipeline：Canonical Services → Snapshot → Rules → Risk Cap → System Action → Digest；§31 必存欄位；§32 Scenario A–D 測試；承接 `P1R-FIVE-BUCKET-L3`／`P1R-DIGEST-HEADLESS-ASSEMBLY`／`P1R-DIGEST-V2-A1..A8`（`:1201`） | Stage E | Opus 5.5＋High；升 `decision_digest.v2`＋獨立 QA |
| **G** OneBrain Runtime | 只讀 Digest；provider-neutral；Shadow first；structured output；grounding gate；deterministic fallback；semantic fingerprint cache（`:1202`） | **Stage F 合格**（客戶：不得在 Headless Digest 合格前開始）；AB-2b（`BP-DR-20`，`:550`）；`FUI-ONEBRAIN-VOCAB-GATE`（`:1233`） | Opus 5.5＋High；paid call 須另經 Secret／Cost／Provider Gate |
| **H** Cross-page Consistency | 同一 market context；Action Consistency（Risk Cap blocked→無 unrestricted Add，含推播）；術語統一（`:1203`） | Stage G | Opus 5.5＋High |
| **I** Real-data／Mobile Acceptance | Desktop 真資料、Mobile 真機／正式 viewport、Cold Start／Partial Data／Stale／API Failure／AI Failure（`:1204`） | Stage H | 需客戶或可連線環境；夾具不足以驗收 |

- **FACT**：`FUI-STAGE-A` 已 paused／superseded（DEC-123，施工改走 New UI2）；F～J 的 Stage 順序在 DEC-123 下保留（`NEWUI2_MIGRATION_CUTOVER_CONTRACT…:53` 欄「DEC-123 Stage F～J 保留」）。
- **FACT**：BACKLOG 的 Cutover 前置清單把 Digest 與 OneBrain 分別列為第 6、7 項（`docs/BACKLOG.md:1286-1287`）：Digest 依賴 Aggregator 契約（M-A5）；OneBrain 依賴 Stage F 合格。

**現況：契約／程式／caller／測試（FACT，逐項附證據）**

| 面向 | Stage F（Digest） | Stage G（OneBrain） |
|---|---|---|
| **契約** | `docs/vnext/DECISION_DIGEST_CONTRACT_vNext_2026-10-29.md`（凍結：最低概念契約 §4、加性 v2 計畫 A1～A8 §6、依賴順序 §8、驗收 §9）；DEC-109 十六～十八 | `ONE_AI_BRAIN_BOUNDARY_vNext_2026-10-29.md`（邊界 §2、禁止 §3、slice §4、輸出格式 §5、出口盤點 §6、驗收 §8）；`ONEBRAIN_ARCHITECTURE_DECISION_2026-10-31.md`（ADR-OB-001：Claude 為未來 Primary、Provider-neutral、Shadow 分階段）；`docs/governance/ONEBRAIN_AI_GOVERNANCE_2026-10-31.md`（G1～G10） |
| **程式** | 已有 L0 契約＋L3 builder＋純函式驗證：`shared/decision_digest.py`（`SCHEMA_VERSION="decision_digest.v1"` `:75`、`MAX_ACTIONS=3` `:78`）、`shared/decision_digest_rules.py`、`_terms.py`、`_validator.py::assess_digest`（`:295`）、`_grounding.py`（G1～G6）；`src/services/decision_digest_builder.py::build_decision_digest`（`:405`，純函式，`ai_participation=RULE_ONLY` `:427`）；`src/services/decision_digest_summary.py::build_rule_summary`（`:128`，無 AI 規則式摘要） | **不存在**。`grep -rniE "onebrain" src shared app_ui2.py` 僅命中 UI2 的**空槽文案**與 VM 欄位：`src/services/ui2/real_canonical.py:515-516,603-604`（`_not_provided(…, _R_STAGE_G)`，`_R_STAGE_G="此功能尚未開放"` `:496`）、`src/ui2/views/market.py:22,36`。無 Provider、無 prompt 治理、無 cache、無 trace |
| **caller（production）** | **0 個**：`grep -rln decision_digest --include=*.py`（排除 tests）僅命中 `shared/decision_digest*.py`、`shared/strategy_class_schema.py`、`src/services/decision_digest_{builder,summary}.py` 自身；AST 守衛 `tests/test_decision_digest_builder.py::test_builder_not_imported_directly_by_app_or_ia_nav`（`:793`）鎖定不被 `app`／`ia_nav` 直接 import | N/A（不存在）；現行 AI 出口全為 legacy（`gemini_call`、`post_gemini`、`build_ai_summary` 等，`ONE_AI_BRAIN_BOUNDARY…` §6 表）。`FUI-HOLD-GEMINI-DIRECT`：`page_hold` ⑦ 直呼 `gemini_call`（非 Digest、無 grounding，`docs/BACKLOG.md:1234`） |
| **測試** | `tests/test_decision_digest_{contract,builder,rules,grounding,validator,round2,summary}.py`、`tests/decision_digest_factory.py`、`tests/test_ui2_p3_evidence_preservation.py`、`tests/test_strategy_class_{schema,reader}.py`；builder 守衛含 `test_builder_imports_no_streamlit_ui_or_network`（`:783`）、`test_builder_signature_does_not_accept_industry_or_picks`（`:123`）。（測試**通過與否**＝**NOT VERIFIED**，本研究未執行 pytest） | 契約文件 §8 列 8 項「Phase 7 寫成測試」＝**尚未寫**（NOT FOUND 對應測試檔） |
| **已知缺口（FACT）** | (1) 市場段依賴 session warroom，`page_market` 只讀不寫（契約 §2.1）→ `P1R-DIGEST-HEADLESS-ASSEMBLY`（`:1090`）；(2) 五桶 worst-of 只在 L5 `tab_macro_v2` → `P1R-FIVE-BUCKET-L3`（`:1089`）；(3) builder 在 Digest 形成前就把行動截至 `MAX_ACTIONS`（`decision_digest_builder.py:344` `chosen = ordered[:MAX_ACTIONS]`）→ 候選草案要求省略揭露（`ONEBRAIN_EVIDENCE_COVERAGE…` §三）；(4) 策略分類未接 builder（`AB4R-WIRE-BUILDER`，`:942`，且接線前須修 `XV-C05`）；(5) 程式寫死五段 vs R12 新輸出格式 → `P1R-AB2A-FIVE-SECTION-REWIRE`（`:1092`） | (1) G1～G6 是**封閉句型白名單**，不涵蓋客戶 §35 自由結構輸出（`reasons[]`／`counter_evidence[]`）→ `FUI-GROUNDING-RISKCAP`（`:1235`）；(2) AB-2b Gate 未裁示（AI 只選句型填 slot vs 自然語言潤飾）→ AI 出口不得接 production（`ONE_AI_BRAIN_BOUNDARY…` §9）；(3) `outlook`／`signal_consistency` 值域撞既有裁示 → `FUI-ONEBRAIN-VOCAB-GATE`（`:1233`）；(4) 「最大 1～3 變化」無正式選取規則（W8，`P1R-P7-WF-CHANGE-RANK`）；(5) ADR 明列未決：model 名、價格、月預算、fallback 順序、production enablement（`ONEBRAIN_ARCHITECTURE_DECISION…` Explicit non-decisions） |
| **H／I 現況** | H：`NUI2-ACC-CROSS-PAGE`＝`FUI-STAGE-H`，open 未開始；LINE 與 App 位階來源不一致已登記（`NUI2-LINE-REGIME-SOURCE`，`docs/BACKLOG.md:1268`）。I：`FUI-STAGE-I` open；需真資料與真機，**沙箱無法驗收** | |

## 2.2 「最小可驗收能力」候選（**研究候選，非施工授權**）

> 通則（來自既有凍結文件，**FACT**）：任何 Stage 失敗時的降級＝**deterministic 輸出**；**missing ≠ 0／中性／安全**（`CLAUDE.md §1`；`ONEBRAIN_AI_GOVERNANCE…` G2；`ONEBRAIN_ARCHITECTURE_DECISION…` Decision 8）。
> 本表每個「驗收準則」皆**取自既有文件的驗收清單**（契約 §9、Brain §8、Cutover §1.1），**不是新發明**；其中哪些要寫成測試仍須 Gate。

### Stage F 候選（F-min）

| 項 | 內容 |
|---|---|
| **輸入證據** | 既有 canonical 輸出：`get_macro_state`（市場）、`allocation_service`（位階／成數）、`dividend_station` rows（行動）、`holdings_service` rows、`SourceStamp`（如 `build_decision_digest` 簽名，`decision_digest_builder.py:405-412`）。**不讀 `st.session_state`**（契約 §9-1） |
| **輸出** | `DecisionDigest`（v1 起步；A1／A2／A6／A7 等加性欄位升 v2 才算 F 完整，契約 §6）＋`assess_digest` 四態＋`build_rule_summary`（無 AI） |
| **驗收準則** | 契約 §9：(1) AST：組裝點不 import `streamlit`／`src.ui.*`／`app`；(2) 簽名不接 `top_n`／`expanded`；(3) **不變性**：UI Top-3 vs 全量、expander 收／展、是否載入市場頁，`digest.to_dict()` 完全相同；(4) **headless**：無 session 冷啟動時市場段由 canonical 路徑組出或誠實 MISSING；(5) 列舉鎖，**無 confidence 列舉**；(6) candidates G1 反例（若含 A3） |
| **失敗降級** | 上游缺值→各段 `Availability`／`MissingReason`；Digest 不合規→`SummaryState.INVALID`，摘要不帶任何段落（`decision_digest_summary.py:136-137`）；**不補 0、不編造**；估值段維持 `RESEARCH_ONLY` |
| **前置（FACT）** | `P1R-FIVE-BUCKET-L3`→`P1R-DIGEST-HEADLESS-ASSEMBLY`（`:1089-1090`）；Aggregator 契約（M-A5，`:1286`）；`AB4R-WIRE-BUILDER` 前先修 `XV-C05`（`:942`） |
| **成本／範圍（INFERENCE）** | 屬 High（L3、新 runtime component、Digest schema）；不需要任何付費 Provider |

### Stage G 候選（G-min）

| 項 | 內容 |
|---|---|
| **輸入證據** | **只**讀一份通過 `assess_digest` 的 `DecisionDigest`（Brain §2-1）；Provider 抽象下的 **fake provider** |
| **輸出** | provider-neutral 的結構化結果（先 Shadow：不顯示給使用者，只落 trace）；任何對外文字必過 `check_summary`，只採 `surviving`（Brain §2-2） |
| **驗收準則** | Brain §8：AST 守衛擴到 Brain；簽名守衛；不變性；headless；slice（Local Summary 每句 ⊂ 全文 lines 逐字）；查看依據只從 Digest／`evidence_refs` 渲染＋突變（自由文字被 `check_summary` 拒）；列舉鎖；candidates G1 反例。Governance：G5 fingerprint 忽略 presentation state、G6 trace 欄位、G7 budget 介面、G10 production enablement 另裁 |
| **失敗降級** | AI 不可用／被拒／預算耗盡→**退回 `build_rule_summary`**（Brain §2-2；ADR Decision 8）；**AI unavailable ≠ SAFE／HOLD／neutral**；失敗不快取、退避（`CLAUDE.md §1.A` 第 3 點） |
| **前置（FACT）** | Stage F 合格；AB-2b Gate（`BP-DR-20`）；`FUI-ONEBRAIN-VOCAB-GATE`；`FUI-GROUNDING-RISKCAP`；真 Provider＝Secret／Cost／Provider Gate |
| **成本／範圍（INFERENCE）** | G-min 若只做「介面＋fake provider＋cache／trace／budget 介面」，**零付費呼叫**，對應 ADR Decision 9 的前兩階段 |

### Stage H 候選（H-min）

| 項 | 內容 |
|---|---|
| **輸入證據** | 同一份 market context（Digest／Aggregator 輸出），供 UI 與 LINE 等所有消費者共用 |
| **輸出** | 一致性檢查結果（測試或唯讀報告） |
| **驗收準則** | Cutover §1.1 C6：同一 market context；Risk Cap blocked／無法判定時任何頁 ⛔ unrestricted Add；術語統一；市場 ⚡ 與持股今日需處理同源（Aggregator 完成後） |
| **失敗降級** | Aggregator 完成前沿用 W-10 並列揭露（`NEWUI2_MIGRATION_CUTOVER_CONTRACT…:§1.1 C6` 同時註明 transitional 不得延續到 cutover） |
| **前置** | Stage G 之後；LINE 改動另批另 Gate（`NUI2-LINE-UI-ACTION-CONVERGENCE`，`docs/BACKLOG.md:1288`） |

### Stage I 候選（I-min）

| 項 | 內容 |
|---|---|
| **輸入證據** | 真資料（非夾具）、真機／正式 viewport |
| **驗收準則** | Cutover §1.1 C5：Cold Start／Partial Data／Stale／API Failure／AI Failure 下仍安全顯示 deterministic output；C3：390×844 與 1440×900 第一屏「不用滑」 |
| **失敗降級** | 四態字樣與色正確，missing ≠ 0／HOLD／neutral，unavailable ≠ safe（C4） |
| **限制（FACT）** | 沙箱無法完成（`docs/BACKLOG.md:1204`「需客戶或可連線環境」）；**任何在沙箱宣稱 I 通過＝不實**（`CLAUDE.md §-1.5.A-7`） |

## 2.3 資料層（Evidence）與 AI 層（Digest／Outlook）分離檢查

> 鏈（FACT，DEC-109 十六／`DECISION_DIGEST_CONTRACT…` §1）：Raw Sources → Canonical Data → Deterministic Rules／Risk Cap → **Decision Digest** → **One AI Brain** → UI Local Summary。另 DEC-128：Digest／OneBrain 是 Complete Evidence Layer 的 projection，UI 與 OneBrain 互不決定對方（契約檔頭註）。

| # | 檢查項 | 結果 | 證據 |
|---|---|---|---|
| S1 | Digest 組裝層不 import streamlit／網路／UI | **通過（守衛存在）**；測試實跑結果 NOT VERIFIED | `tests/test_decision_digest_builder.py:783` |
| S2 | builder 簽名不接受 UI 參數、不接受產業／picks | 守衛存在（同上 `:123`） | 同左 |
| S3 | Digest 的「定義型」段（趨勢／估值／產業）不由 AI 或 builder 填寫 | **通過**：固定 `NOT_DEFINED`×3、`RESEARCH_ONLY` | `decision_digest_builder.py:420-423` |
| S4 | Digest 不含 confidence 語意 | **通過（設計）**：契約明禁，`DataStatus` 無 neutral | 契約 §4、§5 |
| S5 | 現行 AI 摘要有沒有繞過 Digest | **未通過（legacy，已登記）**：`page_hold` ⑦ 直呼 `gemini_call`；LINE 走 `post_gemini` 不同 persona／溫度 | `docs/BACKLOG.md:1234`；`ONE_AI_BRAIN_BOUNDARY…` §6 |
| S6 | Evidence 層（Registry）存在與否 | **NOT IMPLEMENTED**：候選草案自述「此層在 repo 內尚無已確認 production 實作；不等於 `RULE_ID_ALLOWLIST`」 | `ONEBRAIN_EVIDENCE_COVERAGE…` §一 |
| S7 | **Digest 市場段仍依賴 session**（Evidence→Digest 方向的耦合） | **缺口（FACT）**：第一優先來源為呼叫端傳入的 `warroom_summary`；僅今天頁更新鈕寫入 | 契約 §2.1 |
| S8 | Digest 在形成前截斷行動至 3，OneBrain 讀不到被省略的候選 | **缺口（FACT）**：`chosen = ordered[:MAX_ACTIONS]`；無 `omitted_count` 欄 | `decision_digest_builder.py:344`；`ONEBRAIN_EVIDENCE_COVERAGE…` §三 |
| S9 | G1～G6 與「OneBrain 結構化輸出」之間的缺口 | **缺口（FACT）**：封閉句型白名單不涵蓋自由結構欄位 | `docs/BACKLOG.md:1235` |
| S10 | AI 不得回寫 Risk Cap／System Action | 設計規則已明文（G9、Boundary §3）；因 OneBrain 不存在，**尚無實作可驗** | `ONEBRAIN_AI_GOVERNANCE…` G9 |
| S11 | Stage 順序與依賴一致性 | **一致**：F→G→H→I；G 不得早於 F 合格 | `docs/BACKLOG.md:1201-1204` |

- **INFERENCE**：S7、S8 是「資料層（Evidence）→ Digest」方向最實質的兩個缺口；S9 是「Digest → AI」方向最實質的缺口。這三項不修，F 不算「headless、完整、可追溯」，G 也無法安全啟動。
- **INFERENCE**：本檔檢查的是**文件與符號層**；**未執行**任何測試或 mutation，故「通過」僅指設計／守衛存在。

## 2.4 方案比較（至少 3 個）

> 成本標示為相對量級（INFERENCE，未估工時）。所有方案**都不改**「F／G 暫列切換前置」的規則；方案只決定**如何走到前置條件被滿足**。

| 方案 | 範圍 | 優點 | 缺點 | 風險 | 成本 |
|---|---|---|---|---|---|
| **P-1　F 僅 deterministic digest＋G 空槽誠實顯示** | F：做 headless 組裝＋v2 必要加性欄位（至少 A1／A2／A6／A7）＋§9 驗收；**G 不實作**，OneBrain 槽維持「此功能尚未開放」（`real_canonical.py:496,515,603`），摘要走 `build_rule_summary`（無 AI） | 零 AI 成本；完全符合 deterministic-first（Governance G3）；所有失敗降級路徑與驗收清單都可在沙箱以測試證明；不觸發 AB-2b／Provider／Cost Gate | G 仍為前置時，**cutover 條件未滿足**（因 G 未做）；客戶若期待「看得到 AI 總結」會失望 | 低；風險是被誤解成「G 已完成」——UI 文案須維持「尚未開放」 | 低～中 |
| **P-2　F＋G 最小 grounded 摘要（Shadow＋fake provider）** | 在 P-1 之上，做 G-min：provider-neutral 介面、fake provider、cache／trace／budget 介面、`check_summary` 閘＋退回規則式摘要；**無真實 Provider、無付費呼叫、不顯示給使用者**（Shadow） | 把 G 的結構性風險（grounding 缺口、fallback、fingerprint）在無成本下先驗證；符合 ADR Decision 9 前兩階段；不需 Secret／Cost Gate | 需先解 AB-2b 與 `FUI-GROUNDING-RISKCAP`（結構化輸出的 grounding 設計）；介面設計若過度抽象會違反 §8.1 step 6（過度設計） | 中：fake provider 通過不代表真模型行為；Shadow 數據無法證明品質 | 中 |
| **P-3　全做（F＋G 含真 Provider＋H＋I）** | 含 Claude 真實呼叫、Shadow→受控整合、跨頁一致、真資料／真機驗收 | 一次到位、最接近客戶最終目標 | 需多個尚未裁示的 Gate：AB-2b、Vocab、Provider／model／預算／fallback（ADR 明列未決）、Secret／Cost；I 在沙箱不可驗；變更面極大，違反 `CLAUDE.md §8.4 step 4` 的範圍控制 | 高：付費、隱私（Digest 內容出站）、AI 與 Risk Cap 衝突、回歸面大 | 高 |
| **P-4　先只收斂 Evidence→Digest 缺口（S7＋S8），F 之後再議 G** | 只做 S7 headless 組裝與 S8 省略揭露（`total/shown/omitted_count`）；不升完整 v2 | 範圍最小；直接補前述最實質缺口；為任何後續方案共同前置 | 單獨做不產生可見價值；`omitted_*` 屬 Digest schema 變更，仍需版本化與 Gate | 低～中 | 低 |

**RECOMMENDATION（AI 推薦，非客戶裁示）**

1. 以 **P-4 → P-1** 為主線（P-4 是 P-1 的子集與前置）：先補 S7／S8，再完成 F 的 headless Digest 與驗收；G 維持誠實空槽。理由：F 是 G 的硬前置（`BACKLOG:1202`），且 F 的所有驗收都能在沙箱以測試證明；不依賴任何未裁示的 Provider／預算題。
2. **P-2 作為 F 合格後的下一個可選步驟**，且須先把 AB-2b 與 `FUI-GROUNDING-RISKCAP` 送客戶（附推薦方案），因為它們決定 G-min 的輸出型態。
3. **不推薦 P-3**：多個 Gate 未裁示、成本與隱私面大、I 無法在沙箱驗收。
4. 既然客戶已裁示「F／G 暫列切換前置」（依派工轉述），**P-1 單獨無法滿足 cutover**；若客戶之後想縮短路徑，應另送一題「是否讓 G 不再是前置」——**這是客戶才能決定的題目，本檔不預設答案**。

## 2.5 Digest／OneBrain 的「不可做」清單（既有裁示的複述，非新增規則）

1. ⛔ 在 Digest contract v2 定案前寫新的 LLM prompt／glue（DEC-109 三十一；契約 §8 末）。
2. ⛔ AI 從 UI 文字、顏色、widget、Top-N 反推資料（契約 §2）。
3. ⛔ 創造行動、四態、趨勢／產業結論、confidence、數字、門檻、公式、股票、策略分類（Boundary §3）。
4. ⛔ 把 Risk Cap 連到具體行動（除 DEC-122 部分取代所限定的那一條外，Boundary §3 末條及其註）。
5. ⛔ 在 RC-VISIBILITY 核准前讓摘要顯示 Risk Cap 數值（DEC-081 Q2-2）。
6. ⛔ 未經 Provider／Cost／Secret Gate 啟用任何真實 Provider；⛔ 把 `gemini_call`／`post_gemini` 提升為 OneBrain 核心（ADR「NOT promoted」清單）。
7. ⛔ 把 `MAX_ACTIONS` 調大而不先釐清它是安全限制還是 UI 呈現限制（`ONEBRAIN_EVIDENCE_COVERAGE…` §三）。
8. ⛔ 新增 `data_status` 第六態（`ONEBRAIN_EVIDENCE_COVERAGE…` §二）。
9. ⛔ 宣稱 Stage I 在沙箱通過。

---

## 9. 最不確定處與未驗證項

1. **Issue #1121 原文未讀**：「F／G 暫列切換前置」的措辭、範圍與例外，僅依派工轉述（NOT VERIFIED）。若原文對「前置」有更精確的條件，本檔 §2.4 的結論需重審。
2. **大盤／指數層是否有官方 trailing PE／EPS 來源**：repo 內 NOT FOUND；官方是否提供、欄位與歷史長度，**NOT VERIFIED**（不連網）。這決定 E-1-c 是否可行。
3. **TWSE `PEratio` 的官方定義**（trailing 的口徑、虧損股處理、更新頻率）：repo 內無官方定義文字，NOT VERIFIED。
4. **`data_cache/fundamentals/*.parquet` 的實際欄位**（是否含公告日）：本環境無 pyarrow，未開檔；僅依 `mops_bulk_fetcher.py` 輸出欄位（`roc_year`／`season`／`source`／`fetched_at`）與 `latest.json` 推斷「無逐檔公告日」。
5. **FinMind 季值是否真的是單季**：專案是「假設」（`quarterly_financials_fetcher.py:19-22`），並非本次驗證；與 MOPS 累計口徑的差異是否造成既有 TTM 計算錯誤＝NOT VERIFIED，本檔不判定。
6. **所有測試是否通過**：未執行 pytest／mutation；§2.3 的「通過」僅指設計或守衛存在。
7. **完整性**：grep 型盤點（EPS 概念散布處、Digest caller）皆為單組結果，可能漏掉別名、動態 import 或字串拼接呼叫；`CLAUDE.md §-2` 規則 6 要求此類全稱句在被獨立複驗前不得作為後續動作前提。
8. **方案成本**（低／中／高）為相對量級的 INFERENCE，未做工時估算。
9. **客戶「EPS 預估大盤」的真正意圖**（要 forward 預估，還是只要 trailing 估值定位）：**NOT VERIFIED**；E-2 的推薦依此不同而變。
