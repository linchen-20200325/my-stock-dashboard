# D2.5 C 部｜One AI Brain 架構、Decision Digest、11 題可答性、產業趨勢資料盤點（2026-10-27）

> 狀態：**規劃／草稿，非實作授權**。基準 main `a4ab3450`（量測日 2026-10-27）。本檔只做文件，不改 code、tests、治理檔。
> 約束來源：客戶指定版 D2.5 規格（2026-10-27）§三、§七、§九、§十；`PROJECT_RULES.md` §16.1（Data ≠ AI Reasoning）、§19（長久 UI 原則）；DEC-054、DEC-074／075、DEC-080、DEC-084。
> 標記：**FACT[檔:符號]**＝讀碼／讀資料檔所見；**INFERENCE**＝由事實推得、未驗；**MISSING**＝repo 查無，不猜。
> **誠實揭露（CLAUDE.md §-2 規則 6）**：本檔的 FACT 來自五組唯讀盤點（市場／標的產業／持股／AI 現況／治理衝突）的單組讀碼，**未跑 runtime、未連網、未開 App、未經第二組獨立複驗**。所有「沒有／查無／0 命中」都是單組 grep，只能當待驗事項，**不得當實作前提**。外部資料來源的可用性、授權、端點是否存在**一律未驗**。
> 本檔**不提出**任何 Risk Cap、門檻、權重、趨勢定義、估值公式的修改；missing 語意不變（missing ≠ 0、≠ neutral、≠ normal、≠ HOLD；proxy ≠ real；stale ≠ current）。

---

## §1 摘要

1. **現有 AI summary 只是技術基礎，不等於全站 AI 總管。** repo 有 N 個各自組 prompt、各自呼叫 Gemini 的孤立出口；Digest 概念只存在於存股戰情表一處；**沒有輸出後驗證**；傳輸層至少四條彼此不等價（清單見 §2.7）。（§2.7 列差距 8 項。）
2. **One AI Brain 的核心是單向管線**：`Data → Rule/Calculation → 各頁 Structured Result → Decision Digest → One AI Brain → Investment Summary`。AI 只整合、比較、解釋、排序、生成摘要；**不抓資料、不生數字、不補 missing、不設門檻、不定義公式、不發明股票或產業趨勢**。
3. **Decision Digest 是新的資料契約**（逐來源 `as_of／source／status`、`rule_id＋rule_version`、`evidence_refs[]`）。repo 已有可重用零件（canonical 總經契約、`FreshnessVerdict`、`input_provenance_policy` 兩軸、`MISS_*`／`UI_*` 缺值狀態、`build_station_digest`），但**沒有被串起來**，且全站沒有統一的 DataPoint／provenance 物件。
4. **客戶 11 題現況**（§5）：「現在可做到」僅少數（總體市場位階、持股所在板塊、候選標的清單等有既有規則輸出）；**多數為「部分」或「資料不足」**；台股趨勢／國際趨勢**沒有正式定義**（DEC-081 Q3＝A）、建議持股水位的獨立數字未經核准顯示（DEC-081 Q2-2）、大盤 EPS×PE 資料全缺且屬 Research、**「本期 1–3 個行動」沒有選取／排序規則**（HI-1 未核准）。
5. **產業趨勢是最大的缺口**（§6）：產業層營收／EPS／估值**全無聚合**；「技術世代／結構變化」**無任何資料**；真類股指數序列**無**。個股層原料大多有，**不需新外部來源即可聚合（INFERENCE）**，但聚合定義是方法決策，需客戶 Gate。**明文：不得用 LLM 常識宣告某產業已衰退或崛起。**
6. **策略分類（存股／資本利得）沒有任何欄位**（§7）。現行「核心／衛星」是由代號規則推導的近似（ETF→core、個股→satellite），**與客戶要求的「依投資目的分類」直接衝突**。在客戶提供正式分類前，所有持股一律「未分類」。
7. **實作順序**（§8）：先做不碰 UI 的契約與規則層（可獨立於導覽殼），UI 層（AI 總結卡、查看依據）等 D2 Cloud 啟動事故結案、導覽殼重畫後再做。新外部來源、策略分類寫入、EPS×PE、Risk Cap 顯示皆為 High／Customer Gate，**本檔不預設通過**。
8. 客戶 Gate 統一為全套 **Q1–Q6**（§10，與 A／PLAN 一致，各附推薦與理由）；原按鈕觸發、persona 兩題降為內部拍板。

---

## §2 One AI Brain 架構

### 2.1 文字流程圖

```
┌──────────────────────────────────────────────────────────────────────────┐
│ L0/L1 Data Layer（既有）                                                 │
│  acquire / clean / normalize / validate / provenance                     │
│  職責邊界：只負責「取得且可追溯」；不做投資結論、不呼叫 LLM              │
└───────────────────────────────┬──────────────────────────────────────────┘
                                │ 帶 source / as_of / fetched_at / status
                                ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ L2/L3 Rule / Calculation Layer（既有規則 SSOT，本計畫不改）              │
│  市場位階 · 指標危險度 · Risk Cap · 235 燈 · 財報體檢 · 集中度 · 換股規則 │
│  職責邊界：所有數字與狀態在此產生；每個輸出帶 rule_id＋rule_version      │
└───────────────────────────────┬──────────────────────────────────────────┘
                                │ 各頁 Structured Result（既有 L3 輸出）
                                ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ Decision Digest Builder（新，L3，純聚合）                                │
│  只「引用／搬運」既有結構化輸出，不重算、不補值、不估值                  │
│  → 一份 Decision Digest（全站唯一；各頁共用同一份）                      │
└───────────────────────────────┬──────────────────────────────────────────┘
                                │ Digest（唯一輸入）
                                ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ One AI Brain（新，L3，唯一 AI 出口）                                     │
│  輸入＝Digest；任務＝整合、比較、解釋、排序、摘要                        │
│  輸出＝五段 Investment Summary 草稿                                      │
└───────────────────────────────┬──────────────────────────────────────────┘
                                │ 草稿
                                ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ Output Grounding Validator（新，L3，規則式，非 LLM）                     │
│  通過 → 顯示 AI 摘要；不通過 → 退回「規則式摘要」（不含 AI 文字）        │
└───────────────────────────────┬──────────────────────────────────────────┘
                                ▼
                   🤖 AI 投資總結（五段，每段可「查看依據」）
```

### 2.2 各層職責與邊界

| 層 | 現有／新增 | 職責 | 不得做 |
|---|---|---|---|
| Data（L0／L1） | 既有 | 取得、清洗、標準化、驗證、provenance（`PROJECT_RULES.md` §16.1） | 不呼叫 LLM；不產生投資結論 |
| Rule／Calculation（L2／L3） | 既有 | 產生所有數字與狀態；缺資料時回「無法判定」「未評估」 | 不因 UI 需要而改門檻／權重／公式（§19.9） |
| 各頁 Structured Result | 既有 | 各 L3 service 的結構化輸出（例：`get_macro_state`、`get_allocation`、`build_station_digest`、`compute_industry_concentration`） | 不各自拼自然語言餵 LLM |
| **Decision Digest** | **新（契約）** | 把上列輸出**無損搬運**成單一結構，附逐來源 `as_of／source／status` | 不重算、不補值、不把 missing 轉成 0／neutral |
| **One AI Brain** | **新（出口統一）** | 以 Digest 為唯一輸入，生成五段摘要；可排序、比較、解釋 | 不抓資料、不補 missing、不設門檻、不定義公式、不發明股票／產業／趨勢 |
| **Grounding Validator** | **新（規則式）** | 檢查 AI 輸出是否只引用 Digest 內欄位且數字一致 | 不由 LLM 自己驗自己 |

### 2.3 禁止的資料流

- ❌ `Data → LLM → LLM 自己決定數字`（客戶規格 §十；`PROJECT_RULES.md` §16.1 / D3 / D4）。
- ❌ AI 自行抓取、自行查詢（含「問答式 tool-calling」於本 Brain 內擴張成資料取得管道；現有 `ai_qa_service.run_agent` 的 6 個唯讀工具屬獨立功能，不併入 Brain，見 §2.7）。
- ❌ AI 輸出被寫回任何客觀資料欄位或 Digest（只讀，不回寫）。
- ❌ 以 AI 輸出作為 Risk Cap、燈號、位階的來源（`PROJECT_RULES.md` §19.5：AI 不得成為 deterministic rule 的唯一來源）。
- ❌ 各頁各自再建一個 AI 出口（客戶規格 §三）。

### 2.4 輸出驗證／grounding 草案

**現況**：FACT[R4 §1.3] repo 內 `validate_ai|grounding|citation` 等關鍵字 0 命中（單次 grep，非窮舉）；防線 100% 靠 prompt 文字。FACT[`src/ui/views/page_why.py:_render_qa_leaf`] 問答頁的 `QaReadout.tool_calls` 只保留工具名稱，丟掉 args／result／provenance。

**草案規則**（全部由規則式程式執行，不由 LLM 執行；具體實作屬後續批次，閾值類參數**不在本草案內決定**）：

| # | 檢查 | 說明 | 違反時 |
|---|---|---|---|
| G1 | **引用封閉** | AI 輸出中每一個標的代號、產業名稱、狀態詞，必須出現在 Digest 的允許名單（`holdings[]`、`candidates[]`、`industry_trend[]`）內 | 退回規則式摘要 |
| G2 | **數字一致** | AI 輸出中所有數值 token，必須能在 Digest 對應欄位中找到**字面一致**的值（含單位與小數位）；AI 不得自行換算、四捨五入、推估 | 退回規則式摘要 |
| G3 | **狀態不可升級** | Digest 欄位 `status ∈ {missing, stale, proxy, failed}` 時，AI 輸出該項不得使用確定語氣；`missing` 必須出現「無法判定／資料不足」；不得出現「中性」「正常」「維持」「續抱」等看似已判斷的字眼（`PROJECT_RULES.md` §16.1：missing ≠ neutral／normal／HOLD） | 退回規則式摘要 |
| G4 | **不得新增結論類別** | AI 不得輸出 Digest `actions[]` 以外的行動；不得宣告 Digest 無對應欄位的產業「變強／轉弱／衰退／崛起」 | 退回規則式摘要 |
| G5 | **段落完整** | 五段皆須存在；資料不足的段落必須以「資料不足」明示，不得省略或以通用文字填充 | 該段退回規則式 |
| G6 | **依據可回溯** | 每個結論句必須綁定至少一個 `evidence_refs[]`；無綁定的結論句不顯示 | 該句丟棄 |
| G7 | **輸出過濾** | 沿用既有 secret／URL query 清洗（FACT[`scrub_*` 家族]），但**明確承認**那不是內容驗證 | — |

> INFERENCE：G1～G6 的「字面一致」比對需要把 AI 輸出做結構化（例如要求 AI 以「句子＋引用 id 列表」格式輸出），這屬 prompt／輸出格式設計，屬實作批次內決策。若 AI 輸出無法解析成結構，**視為驗證失敗**，退回規則式摘要。
> ⚠️ 「查看依據」展開內容**必須由 Digest 與 `evidence_refs` 直接渲染**，不得由 AI 轉述（否則等同無法驗證，FACT／INFERENCE：R4 §6）。

### 2.5 降級（無金鑰／失敗／資料不足）

| 情境 | 行為 | 現有基礎 |
|---|---|---|
| 無金鑰 | 顯示**規則式摘要**（由 Digest 模板化生成，無 AI 文字）＋灰色提示「AI 摘要未啟用」；**不是紅色錯誤** | FACT[page_hold ⑦ `error_kind`、問答頁 `key_missing`；§02 灰 vs 紅分離] |
| AI 呼叫失敗（429／5xx／逾時） | 同上，改標「AI 暫時無法使用」；失敗**不快取**、退避不連續轟炸 | FACT[CLAUDE.md §1.A-3；`post_gemini` 有 retry-after／退避] |
| Grounding 驗證失敗 | 退回規則式摘要；Digest 內記錄 `ai_participation.validation=failed` 與失敗規則 id（供「查看依據」顯示） | 新增 |
| Digest 資料不足（Required 項缺） | 該段直接顯示「資料不足」與缺哪些（來自 Digest 的 `status`／`missing_reason`）；**不呼叫 AI 去補** | FACT[page_hold 上游紅／空不呼叫、不花錢] |
| Digest 整份不可用 | 整個 AI 總結區顯示「無法產生總結」，各頁其餘內容照常 | — |

> 原則：**規則層結論在 AI 缺席時仍必須能獨立呈現**（FACT[R4 §4]：日／週推播與財報 AI 已有此設計）。AI 是可替換、可缺席的層（`PROJECT_RULES.md` §19.5）。

### 2.6 成本與觸發

- FACT[R4 §4]：`gemini_call` 為付費 API；Streamlit 每次互動重跑整頁，故全站採「**按鈕觸發才呼叫**」，並有測試守衛（`TestTheAiCostsNothingUntilYouPress`）；結果只存 `st.session_state`，換 session 即重算（無伺服器端結果快取）。
- 本 Brain 的建議觸發：
  1. **按鈕觸發**（預設）：「🤖 產生 AI 投資總結」；Digest 先出（規則式摘要立即可見），AI 潤稿按了才呼叫。
  2. **cron 預產（選項）**：與推播同源，預產一份已通過 Grounding 的摘要供開頁顯示。**屬新的自動 AI 行為，第一版內部拍板為按鈕觸發（§10 內部拍板表；cron 預產另案）**；BP-DR-20（AI 解釋層自動 vs 按了才生成）原本即為待客戶 Decision（FACT[VNEXT_PRODUCT_BLUEPRINT §14.3]）。
  3. 不做：背景輪詢、每次 rerun 自動呼叫。
- 成本風險（INFERENCE）：若 Brain 走 `gemini_call` 金鑰池、而舊 UI 其他出口也走，額度共用且**無用量計數**（grep 未見 token 計量，未窮舉）；統一出口後建議同時補用量計量（屬實作批次）。

### 2.7 與現有各 AI 出口的關係；差距 8 項

**現有出口（FACT[R4 §1]，摘要）**：總經頁新聞 AI、個股頁 AI 總結、個股組合 AI、選股網 AI、ETF 單檔／組合／產業輪動 AI、存股戰情室 AI 戰情總結（最接近 Digest）、AI 問答（tool-calling，唯一「AI 只能呼叫工具取數」設計）、每日／週推播 AI、新聞情緒判讀、財報體檢 AI insight、總經 AI 裁決鎖。傳輸層至少四條（2026-10-27 補清單並 grep 複核，單組 INFERENCE）：
  1. `src/services/app_ai_service.py::gemini_call`（金鑰池、v1beta、失敗回 `⚠️` 字串）；
  2. `src/services/ai_fetcher.py::post_gemini`（單 key、model fallback、失敗回 `(None, err)`）；
  3. `src/services/ai_qa_service.py::_make_default_http`（AI 問答，自帶 `_GEMINI_URL`）；
  4. `src/ui/pages/sidebar_health.py::_call_gemini_brief`（側欄健康簡述，內嵌 URL）。
  另 `src/ui/pages/api_diagnostic.py` 只對 models 清單做**連線診斷**，不是生成傳輸，不計入四條。其餘含 gemini 字樣的檔（`ai_structured_summary`、`weekly_review_service`、各 `*_service`、各 tab）是否各自再發 HTTP、或皆經上述四條之一，**本檔未逐檔驗**。
  **視覺稿**：`docs/vnext/d25_wireframes/ai_summary.html`（及同目錄其餘頁）為給客戶看的示意視覺稿，非實作授權。
  `src/ui_v2/` 為 git 追蹤的新 UI 視覺 token／元件模組（`page_today`／`page_find` 等 import 之），本檔未盤點其內容，與 Brain 資料契約無直接依賴（INFERENCE）。

**關係**：本 Brain 是**新的、唯一的全站投資決策總管**；現有出口在 Brain 落地前**一律保留不動**（舊 UI 不刪；`PROJECT_RULES.md` §19.6）。現有出口可重用的是**設計模式**而非程式：
- `build_station_digest` → 「規則式事實＋AI 只潤稿」模式；
- `ai_qa_service` → 「ok=false 必須明講無法判斷」「provenance 隨結果」模式；
- `macro_state_locker` → 「理科（Python）先算、文科（AI）後寫」模式；
- 按鈕 gate、AI 缺席時規則層照常輸出。

**差距 8 項（現有 AI summary → One AI Brain）**：

| # | 差距 | 現況（FACT） | Brain 需要 |
|---|---|---|---|
| 1 | **無單一入口** | N 個出口各自組 prompt；Digest 僅存股戰情表一處 | 單一出口、單一 Digest |
| 2 | **輸入非結構化、無依據欄** | 輸入是「章節名＋字串」；日期／狀態靠字串約定（`[STALE:Nd]`），不可機讀；缺值格式不一（中文括號、`—`、`N/A`、`0`） | 帶 `value／as_of／source／status` 的物件 |
| 3 | **仍有缺值被當 0 的路徑** | `section_ai_portfolio` 的 `.get('foreign_buy',0) or 0` → 印「賣超0張」；`etf_tab_ai` 的 `capital_gain_pct,0` 等（既有行為，本檔不建議修，僅列證據） | Digest 內 missing 一律以 `status=missing` 表達，不得為 0 |
| 4 | **無輸出後驗證** | 防線全在 prompt；問答頁 UI 層丟棄 provenance | §2.4 Grounding Validator |
| 5 | **11 題缺規則輸出** | 持股比提高／維持／降低、本期 1–3 行動、新產業、長期持有適合度等為 MISSING | §5 逐題；缺者 Digest 標 missing，不由 AI 補 |
| 6 | **傳輸層四套、模型清單多份、單／多 key 不一、失敗型別不統一** | 模型清單在 4 處各自寫死（INFERENCE：非 SSOT，與 §19.5 有距離）；失敗以 `⚠️`／`❌` 字串、`(None,err)`、`QAResult(ok=False)` 混用 | 單一傳輸層＋統一「AI 不可用」型別（實作批次，不改舊出口） |
| 7 | **persona 與 DEC-054 第 6 點張力** | FACT[`TAIWAN_ADVISOR_PERSONA`] 第 1 條仍寫「請給出明確的動作與情緒形容」；`CV1-FU-06` open | Brain 不沿用該 persona；改全站 persona 範圍過大，Brain 用獨立 prompt＝內部拍板（§10 內部拍板表） |
| 8 | **跨頁一致性僅部分** | regime 已走 `get_macro_regime()` 單一仲裁點；但月頻 STALE 前綴只接總經／個股兩處 prompt | Digest 內統一 freshness 表達，全站共用 |

> 「查看依據」需求補充：FACT[R4]『`build_llm_context` 設計良好但 0 production caller』——不建議直接復活，而是以 Digest 取代其職責。

---

## §3 AI 投資總結固定五段輸出

> 對應客戶規格 §九。每個結論旁必須能「查看依據」。**資料不足時必須明說不知道**（第②段）。以下「資料與規則來源」只列**既有或需新增的規則輸出**，不指定任何門檻。

### 3.1 五段的資料與規則來源

| 段 | 內容 | 資料／規則來源（FACT 為既有；MISSING 為需補） | 資料不足時的輸出 |
|---|---|---|---|
| **① 市場** | 台股趨勢、國際趨勢、總體風險、建議總持股水位 | **總體市場位階**：FACT[`allocation_service.get_macro_regime`→`macro_state_locker.get_macro_state`；`regime_arbiter`]。**總體風險**：FACT[`compute_five_bucket_summary`／`BUCKET_DANGER_SPECS`、16 燈、`_load_key_alerts`]。**建議總持股水位**：FACT[`get_allocation()`→`AllocationDecision.final_lo/hi`；`get_macro_state()['exposure_limit_pct']`，缺有效 Cap → None＝「無法判定」，D13]。**台股趨勢／國際趨勢**：**MISSING 正式定義**（`VN1-MT-TREND-DEF` blocked-on-customer；DEC-081 Q3＝A 現只顯示「尚未定義」） | 「無法判定」＋缺什麼；趨勢兩項固定為「尚未定義」，**不由 AI 補** |
| **② 產業** | 變強產業、轉弱產業、結構性變化 | FACT 僅**資金流**層面：`sector_flow` 40 板塊泡泡圖象限（漲潮／輪動／退潮／觀望／資料不足／未取得）、熱力圖 10 檔代表股（proxy，非類股指數）。**產業層營收／EPS／估值／資本支出／景氣／技術世代＝MISSING**（§6） | 預設輸出「**資料不足，無法判斷產業趨勢**」，僅可列「資金流象限」並標明口徑；**結構性變化一律「不知道」** |
| **③ 存股** | 是否繼續持有、基本面／現金流是否惡化、是否需降低配置 | 前提：**策略分類＝存股**（§7；現 MISSING → 全部「未分類」）。基本面：FACT[`financial_health_engine`／`fetch_metrics` 財報體檢、`trend_verdict`]、配息：FACT[`portfolio_deep_service.get_dividend_cash_flow`（近 1 年）]。**「適合長期持有」單一判定欄＝MISSING**（只有燈號／健檢分項） | 無策略分類 → 本段顯示「尚未設定投資策略分類，無法判定」；有分類但缺欄 → 逐檔 missing |
| **④ 資本利得** | 哪些續抱／減碼／換股、候選產業／候選標的 | 前提：策略分類＝資本利得（§7）。換股：FACT[`build_switch_advice`、`get_switch_in_candidates`、`flag_take_profit`（衛星停利，門檻 `SATELLITE_TAKE_PROFIT_PCT`）]。候選標的：FACT[`fundamental_screener_service.get_ranked_picks`]。**統一「續抱／注意／減碼」分級＝MISSING**；**候選產業＝MISSING**（§6） | 同上；候選產業固定「資料不足」 |
| **⑤ 本期行動（1–3 項）** | 只給最重要 1–3 項 | **MISSING 選取／排序規則**（無行動排序；VN-09 Action Layer 未實作；HI-1 未核准；DEC-054 允許方向性 Action 但須由既有可追溯規則支持，強 Action 不得只靠生成式 AI） | 資料或規則不足 → 顯示「本期無可判定的行動」，**不得為了有答案而湊數**（`PROJECT_RULES.md` §16.1） |

> ⑤ 的設計原則（INFERENCE，待 §10 Q4 裁示）：`actions[]` 由**規則層**產生候選與來源，Brain 只可在候選內「排序與解釋」，不可新增。規則層目前只有既有的 deterministic 項目（如 `held_reds`、`adds`、`take_profit`、換股建議、Risk Cap 降水位）可被**引用**；把它們合成「最重要 1–3 項」的優先序規則屬投資語意，**必須客戶 Gate（HI-1）**。

### 3.2 「查看依據」展開內容規格

每個結論句旁一個「查看依據」，**預設收合**（Level 3，客戶規格 §一）。展開內容（**由 Digest 直接渲染，非 AI 轉述**）：

| 區塊 | 內容 | Digest 來源欄位 |
|---|---|---|
| 1. 使用的資料 | 列出該結論引用的每個資料項：名稱、值、單位 | `evidence_refs[]` → 對應來源物件 |
| 2. 資料日期 | 每項的 `as_of`（資料歸屬日）與 `fetched_at`；**判定日 ≠ 資料日**，兩者分開標示（FACT[`FreshnessVerdict.evaluated_on` 是判定日]） | `as_of`、`fetched_at` |
| 3. 規則與計算結果 | `rule_id＋rule_version`、規則輸出（例如「Risk Cap 規則 `risk_cap.v2` → 無法判定」）；**不重述公式細節給一般使用者**，公式細節在進階層 | `rule_id`、`rule_version`、規則輸出 |
| 4. Missing | 缺哪些項、原因（`MISS_*`：無輸入／抓取失敗／歷史不足／不適用／契約漂移）；以及「怎麼辦」（FACT[`MISS_TEXT`]） | `status`、`missing_reason` |
| 5. confidence／availability | 資料可得性（例：「可信度 N/M」＝已評估項數／應評估項數，FACT[存股戰情 ① 結論三卡已有 N/M]）；**不使用 AI 自評機率** | `availability` |
| 6. AI 是否參與 | 明示：「規則式（無 AI）」「AI 整合文字（已通過驗證）」「AI 文字被退回，改顯示規則式」 | `ai_participation` |

> 注意：**不得**在「查看依據」內放入 HI-3 範圍內容（停損／停利／目標價／三維出場語意）。HI-1～HI-6 一律未核准（§9）。

---

## §4 Decision Digest schema 草案

> 本節是**契約草案**，不是實作。欄位名稱為暫定；落地前需經 §8 AB-0 的契約審查與客戶對 §10 Q1–Q6 的裁示。
> **缺值語意（全表通用）**：任何欄位缺值＝`null`＋`status ∈ {missing, stale, proxy, failed}`＋`missing_reason`；**禁止**以 `0`、`"neutral"`、`"normal"`、`"HOLD"`、空字串代替（`PROJECT_RULES.md` §16.1／§19.8）。「未評估」≠「安全」。

### 4.1 欄位表

**頂層**

| 欄位 | 型別 | 說明 | 缺值語意 |
|---|---|---|---|
| `digest_version` | string | Digest schema 版本 | 必填，不可缺 |
| `generated_at` | datetime（UTC，TZ-aware） | Digest 組裝時間（≠ 任一資料的 `as_of`） | 必填 |
| `sources[]` | array<SourceStatus> | 逐來源狀態（見下） | 空陣列＝「沒有任何來源被登錄」，視為 `failed` |
| `market` | MarketBlock | 市場總結 | 見下 |
| `tw_trend` | TrendBlock | 台股趨勢 | 現況固定 `status=missing, missing_reason=NOT_DEFINED`（`VN1-MT-TREND-DEF` 未核准） |
| `intl_trend` | TrendBlock | 國際趨勢 | 同上 |
| `valuation` | ValuationBlock | 大盤合理區間（**研究框架狀態**） | 現況固定 `framework_status=research`，無數字 |
| `industry_trend[]` | array<IndustryBlock> | 產業趨勢（逐產業、逐維度） | 無維度資料 → 該維度 `status=missing` |
| `candidates[]` | array<CandidateBlock> | 候選標的（**允許名單**） | 空＝無候選或無法判定，須區分 |
| `holdings[]` | array<HoldingBlock> | 持股（含策略分類） | 讀取失敗與「未綁定」須區分 |
| `risk_cap` | RiskCapRef | **只引用**既有 Risk Cap 輸出，不重算 | 無有效 Cap → `value=null, status=missing`（＝「無法判定」） |
| `actions[]` | array<ActionRef>（長度 0..3） | 本期行動候選（**由規則層產生**，Brain 只可排序與解釋） | 空＝「無可判定行動」；**不得湊數** |
| `availability` | Availability | 全 Digest 可得性摘要（已評估／應評估） | 必填 |
| `ai_participation` | AiParticipation | AI 是否參與、驗證結果 | 必填 |

**SourceStatus（逐來源）**

| 欄位 | 型別 | 說明 | 缺值語意 |
|---|---|---|---|
| `source_id` | string | 來源識別（例 `FRED:<series>`、`TWSE:<dataset>`；沿用 §2.2 命名） | 必填 |
| `source` | string | 來源名稱／端點識別 | 必填 |
| `as_of` | date \| null | **資料歸屬日**（≠ 抓取日、≠ 判定日） | `null` 時 `status` 不得為 `ok` |
| `fetched_at` | datetime \| null | 抓取時間 | 可缺但須有 `status` |
| `status` | enum | `ok` \| `stale` \| `missing` \| `proxy` \| `failed` | 必填；`proxy`＝代理／估算值，不得以正式資料身分顯示或計分（DEC-037／074／080） |
| `missing_reason` | enum \| null | `NO_INPUT／FETCH_FAILED／NOT_ENOUGH_HISTORY／NOT_APPLICABLE／CONTRACT_DRIFT／NOT_DEFINED／NOT_WIRED`（沿用 `MISS_*`，另加後兩項） | `status ∈ {missing, failed}` 必填 |
| `provenance` | enum | `official／secondary／estimated／proxy／unavailable`（沿用 DEC-080） | 必填 |
| `freshness` | enum | `fresh／stale／carried_forward`（沿用 DEC-080 兩軸；`carried_forward` 無正式發布期定義＝`PENDING_SPEC`） | 必填 |

**MarketBlock**

| 欄位 | 型別 | 說明 | 缺值語意 |
|---|---|---|---|
| `regime` | enum | `bull／neutral／caution／bear／unknown`（沿用 `get_macro_state` 契約） | `unknown`＝未評估，**不是** neutral（`is_loaded=false`） |
| `light` | string | 燈號 | 同上 |
| `danger_summary` | object | 五桶危險度摘要（worst-of） | 缺桶 → 該桶 `status=missing` |
| `top_risks[]` | array（≤3） | 今日主要風險（只引用既有 key alerts／危險度，不新增判斷） | 空＝無警示 **或** 無法判定，須以 `availability` 區分 |
| `suggested_exposure` | object | 建議總持股水位（引用 `AllocationDecision.final_lo/hi`；Risk Cap 見 `risk_cap`） | 無 → `status=missing`；DEC-081 Q2-2 未核准顯示前，UI 不得把它畫成 Risk Cap 獨立數字 |
| `rule_id`／`rule_version` | string | 產生 regime 的規則識別與版本（例：Risk Cap 為 `risk_cap.v2`） | 必填 |
| `evidence_refs[]` | array<string> | 指向 `sources[].source_id` 或規則輸出 id | 必填（可為空陣列＝無依據→該結論不顯示） |

**TrendBlock／ValuationBlock**

| 欄位 | 型別 | 說明 | 缺值語意 |
|---|---|---|---|
| `defined` | bool | 趨勢是否有客戶核准的正式定義 | 現況 `false` |
| `verdict` | enum \| null | 僅 `defined=true` 時才有值 | `null` |
| `series_ref` | string \| null | 圖表序列引用（只引用已存在序列，如 `twii_ohlcv`） | 缺 → `status=missing` |
| `framework_status`（Valuation） | enum | `research`（現況）\| `approved` | **`research` 時不得含 EPS／PE／區間數值**（EPS 來源、PE 情境、公式、更新頻率未經 High Gate 核准） |

**IndustryBlock（逐產業）**

| 欄位 | 型別 | 說明 | 缺值語意 |
|---|---|---|---|
| `industry_code`／`industry_name` | string | 沿用 TWSE／TPEx 官方產業別代碼與名稱（FACT[`shared/industry_codes.py`]）；不得由 AI 命名 | 必填；標籤不屬官方 35 類者標 `NOT_APPLICABLE` |
| `dimensions` | map<dimension, DimensionValue> | 維度：`revenue_growth／earnings_growth／capex／relative_strength／institutional_flow／chips／valuation／cycle／events／tech_generation` | **每個維度獨立 `status`**；沒有正式資料的維度＝`missing`，**不得讓 AI 補** |
| `coverage` | object | 聚合覆蓋率（檔數／總檔數）與「存活者偏誤」標記 | 必填（聚合類維度） |
| `rule_id`／`rule_version` | string | 聚合規則識別（現 MISSING；需客戶 Gate 核准聚合定義後才有） | 無規則 → 不產生產業方向結論 |

**CandidateBlock（候選標的，允許名單）**

| 欄位 | 型別 | 說明 | 缺值語意 |
|---|---|---|---|
| `ticker`／`name` | string | 來源必為 `get_ranked_picks` 等既有輸出；**AI 不得新增** | 必填 |
| `industry_code` | string \| null | 個股→產業對映（FACT[`ticker_sector.json`]） | 對映缺 → `null`＋`NOT_APPLICABLE` 或 `NO_INPUT` |
| `fundamental`／`valuation`／`chips` | StatusValue | 基本面、估值、籌碼狀態 | 各自 `status` |
| `snapshot_ref` | string | 引用快照期別（FACT[`latest.json` roc_year／season／updated_at]） | 必填；PIT 注意：公告季 ≠ 交易日 ≠ 當日 PE |

**HoldingBlock（持股）**

| 欄位 | 型別 | 說明 | 缺值語意 |
|---|---|---|---|
| `ticker`／`name` | string | 來源＝`holdings_service`（只讀已選定的那一本組合） | 必填 |
| `strategy_type` | enum | `存股／資本利得／未分類` | **預設且唯一合法預設＝`未分類`**；不得 AI 猜；不得由 ETF／個股推導（§7） |
| `strategy_type_source` | string \| null | 分類來源（客戶設定的位置／版本） | `未分類` 時為 `null` |
| `asset_kind`／`legacy_asset_class` | string | 既有 `asset_kind`、代號推導的 `core／satellite`（**僅供對照，標示為近似，不得當策略分類**） | — |
| `lots`／`avg_price`／`price`／`pnl_pct` | StatusValue | 張數、均價、現價、損益% | 缺 → `null`＋`missing`；NaN／inf → `invalid`（D11），不參與計算 |
| `health`／`lights` | StatusValue | 健檢等第、235 燈（僅 ETF）、個股 4 盞汰換燈 | 個股無 235 燈＝`NOT_APPLICABLE` |
| `industry_code` | string \| null | 所屬產業 | 同上 |
| `rule_id`／`rule_version`／`evidence_refs[]` | — | 同上 | — |

**RiskCapRef（只引用，不重算）**

| 欄位 | 型別 | 說明 | 缺值語意 |
|---|---|---|---|
| `value_pct` | number \| null | 引用 `exposure_limit_pct` | 缺有效 Cap → `null`（D13：「無法判定」），**不是 0、不是 100** |
| `rule_id`／`rule_version` | string | `risk_cap`／`risk_cap.v2`（引用，非新設） | 必填 |
| `disclosure` | string \| null | 引用 `risk_cap_disclosure`（7 天沿用須揭露，DEC-080） | — |
| `industry_exposure` | StatusValue | 引用 `compute_industry_concentration`（等權假設、未分類不入分母、附 `coverage_pct`；無門檻） | 「是否過度曝險」**不得由 Digest／AI 判定**（無門檻，且本檔不提議） |

**ActionRef**

| 欄位 | 型別 | 說明 | 缺值語意 |
|---|---|---|---|
| `action_id` | string | 規則層產生的行動識別 | 必填 |
| `kind` | enum | 限既有 deterministic 項目類型（例：換股候選、衛星停利、降水位；**不新增行動語彙**，HI-1） | 必填 |
| `target` | string | 標的或範圍（必須在 `holdings[]`／`candidates[]`） | 必填 |
| `source_rule`／`rule_version` | string | 產生此行動的既有規則 | 必填；無規則來源 → 不得成為 action |
| `priority_rank` | int \| null | 排序（**現無正式排序規則 → 一律 `null`**，待 §10 Q4） | `null` |
| `evidence_refs[]` | array | 依據 | 必填 |

**Availability／AiParticipation**

| 欄位 | 型別 | 說明 | 缺值語意 |
|---|---|---|---|
| `evaluated`／`expected` | int | 已評估項數／應評估項數（沿用 N/M 概念） | 必填；`evaluated<expected` 時 UI 不得顯示「正常」 |
| `by_section` | map | 五段各自可得性 | 必填 |
| `ai_participation.mode` | enum | `rule_only／ai_assisted／ai_rejected` | 必填 |
| `ai_participation.validation` | object | 通過／失敗規則 id（G1～G6） | `ai_assisted` 時必填 |

### 4.2 JSON 範例

> **示意，非實際數據。** 以下所有值皆為佔位（`<…>`、`null`、`YYYY-MM-DD`），**不得**當成任何真實市場數字、日期或結論引用。

```json
{
  "_note": "示意，非實際數據",
  "digest_version": "<示意>",
  "generated_at": "YYYY-MM-DDTHH:MM:SSZ",
  "sources": [
    {
      "source_id": "<SOURCE_ID_A>",
      "source": "<示意來源>",
      "as_of": "YYYY-MM-DD",
      "fetched_at": "YYYY-MM-DDTHH:MM:SSZ",
      "status": "ok",
      "missing_reason": null,
      "provenance": "official",
      "freshness": "fresh"
    },
    {
      "source_id": "<SOURCE_ID_B>",
      "source": "<示意來源>",
      "as_of": null,
      "fetched_at": null,
      "status": "missing",
      "missing_reason": "FETCH_FAILED",
      "provenance": "unavailable",
      "freshness": "stale"
    },
    {
      "source_id": "<SOURCE_ID_C>",
      "source": "<示意代理來源>",
      "as_of": "YYYY-MM-DD",
      "fetched_at": "YYYY-MM-DDTHH:MM:SSZ",
      "status": "proxy",
      "missing_reason": null,
      "provenance": "proxy",
      "freshness": "fresh"
    }
  ],
  "market": {
    "regime": "<bull|neutral|caution|bear|unknown>",
    "danger_summary": { "status": "<ok|missing>", "buckets": "<示意>" },
    "top_risks": ["<示意：既有警示 id>"],
    "suggested_exposure": { "lo": null, "hi": null, "status": "missing", "missing_reason": "NO_INPUT" },
    "rule_id": "<示意 rule id>",
    "rule_version": "<示意 version>",
    "evidence_refs": ["<SOURCE_ID_A>"]
  },
  "tw_trend": { "defined": false, "verdict": null, "series_ref": null, "status": "missing", "missing_reason": "NOT_DEFINED" },
  "intl_trend": { "defined": false, "verdict": null, "series_ref": null, "status": "missing", "missing_reason": "NOT_DEFINED" },
  "valuation": { "framework_status": "research", "eps": null, "pe_scenarios": null, "range": null, "status": "missing", "missing_reason": "NOT_DEFINED" },
  "industry_trend": [
    {
      "industry_code": "<官方產業別代碼>",
      "industry_name": "<官方產業別名稱>",
      "dimensions": {
        "institutional_flow": { "status": "<ok|stale|missing>", "value_ref": "<示意>", "as_of": "YYYY-MM-DD" },
        "revenue_growth": { "status": "missing", "missing_reason": "NOT_WIRED" },
        "tech_generation": { "status": "missing", "missing_reason": "NO_INPUT" }
      },
      "coverage": { "covered": "<n>", "total": "<N>", "survivorship_bias_flag": true },
      "rule_id": null,
      "rule_version": null
    }
  ],
  "candidates": [
    {
      "ticker": "<TICKER_PLACEHOLDER>",
      "name": "<NAME_PLACEHOLDER>",
      "industry_code": "<官方產業別代碼|null>",
      "fundamental": { "status": "<ok|missing>" },
      "valuation": { "status": "<ok|missing>" },
      "chips": { "status": "<ok|missing>" },
      "snapshot_ref": "<roc_year/season/updated_at 示意>"
    }
  ],
  "holdings": [
    {
      "ticker": "<TICKER_PLACEHOLDER>",
      "name": "<NAME_PLACEHOLDER>",
      "strategy_type": "未分類",
      "strategy_type_source": null,
      "asset_kind": "<etf|stock>",
      "legacy_asset_class": "<core|satellite（僅對照，非策略分類）>",
      "lots": { "value": null, "status": "missing", "missing_reason": "NO_INPUT" },
      "pnl_pct": { "value": null, "status": "missing", "missing_reason": "NO_INPUT" },
      "health": { "status": "<ok|missing>" },
      "industry_code": "<官方產業別代碼|null>",
      "rule_id": "<示意>",
      "rule_version": "<示意>",
      "evidence_refs": ["<SOURCE_ID_A>"]
    }
  ],
  "risk_cap": {
    "value_pct": null,
    "status": "missing",
    "rule_id": "risk_cap",
    "rule_version": "risk_cap.v2",
    "disclosure": null,
    "industry_exposure": { "basis": "equal_weight", "coverage_pct": null, "status": "<ok|missing>" }
  },
  "actions": [
    {
      "action_id": "<示意>",
      "kind": "<既有 deterministic 項目類型>",
      "target": "<TICKER_PLACEHOLDER>",
      "source_rule": "<示意>",
      "rule_version": "<示意>",
      "priority_rank": null,
      "evidence_refs": ["<SOURCE_ID_A>"]
    }
  ],
  "availability": { "evaluated": "<n>", "expected": "<N>", "by_section": { "market": "<示意>", "industry": "missing", "buy_and_hold": "missing", "capital_gain": "missing", "actions": "<示意>" } },
  "ai_participation": { "mode": "rule_only", "validation": null }
}
```

---

## §5 客戶 11 題逐題可答性

結論欄圖例：**可做**＝現有資料與規則輸出可支撐、不需新來源／新規則；**部分**＝部分面向可答，其餘缺；**資料不足**＝關鍵資料或規則 MISSING；**需裁示**＝缺的是客戶定義／Gate，不是工程。

| # | 題 | 需要的資料與規則輸出 | repo 現況 | 結論 |
|---|---|---|---|---|
| 1 | 總體市場 | 市場位階、指標危險度、今日關鍵風險、freshness | FACT[`get_macro_state`（regime＋`is_loaded`，unknown≠neutral）、`regime_arbiter`、`compute_five_bucket_summary`、`_load_key_alerts`]。缺口：FACT[契約無逐指標 `as_of`（`AS_OF_NOT_IN_CONTRACT`）]；缺真實廣度時位階常為「未評估」（DEC-074／075）；新版頁冷啟動 session 為空，需按「更新」 | **部分**（規則輸出齊；as_of 需擴契約；常見「未評估」須誠實呈現） |
| 2 | 台股趨勢 | 「趨勢」的正式定義＋規則輸出＋指數序列 | FACT[`twii_ohlcv.parquet` 4903 列、2006-09-29→2026-10-22，可畫走勢]；**MISSING 趨勢定義**（`VN1-MT-TREND-DEF` blocked-on-customer；DEC-081 Q3＝A）。「長期上升／整理／轉弱」即是定義問題 | **需裁示**（資料足，定義缺；定義前只能標「走勢，不構成趨勢判斷」） |
| 3 | 國際趨勢 | 同上＋國際序列 | FACT[`cl_data['intl']`（DJI／IXIC／SOX／^TNX／DXY）僅 session 內短窗；VIX／US10Y／DXY 無落地長歷史；^GSPC 不在 INTL_MAP]；**MISSING 趨勢定義** | **資料不足＋需裁示** |
| 4 | 總持股比 提高／維持／降低 | 現行建議水位、Risk Cap、**方向性判定規則** | FACT[`get_allocation()`、`exposure_limit_pct`，缺有效 Cap → None（D13）；DEC-081 Q2-2：Risk Cap 獨立數字未核准顯示]。**MISSING「提高／維持／降低」方向判定規則**（DEC-054／D17：正式加減碼比例未經驗證不得進 production；VN-09 Action Layer 未實作；HI-1 未核准）。「維持」尤須防 missing≠HOLD | **資料不足＋需裁示**（可顯示「現行建議區間」；方向性不可由 AI 產生） |
| 5 | 哪些產業變強 | 產業相對強弱／基本面成長／法人／估值 | FACT[資金流泡泡圖 40 板塊象限；熱力圖 10 檔代表股（proxy，非類股指數，卡上已揭露）]；**產業營收／EPS／估值聚合 MISSING**；無真類股指數序列 | **部分**（僅資金流面向；「變強」沒有正式定義） |
| 6 | 哪些產業轉弱或結構性衰退 | 同上＋景氣循環＋技術世代＋事件 | FACT[泡泡圖有「退潮」象限]；**產業別景氣、技術世代、事件＝MISSING**；總體層有 PMI／NDC（FACT）但非產業別 | **資料不足**（「結構性衰退」**無任何可機械取得的資料**；不得由 LLM 常識宣告） |
| 7 | 持股是否過度曝險轉弱產業 | 持股→產業對映、市值加權曝險、「轉弱產業」清單、過度曝險判定 | FACT[`compute_industry_concentration`（**等權**、未分類不入分母、`coverage_pct`、**無門檻**——user 2026-08-14 裁示不設）；`sector_flow` 持股→板塊對映]；FACT[page_hold 未接]。**MISSING 市值加權、「轉弱產業」正式清單、「過度」判定規則** | **資料不足＋需裁示**（只能呈現「持股產業分布（等權）」；「是否過度」需客戶定義，本檔不提議） |
| 8 | 存股是否仍適合長期持有 | 策略分類＝存股、基本面／配息品質趨勢、「適合長期持有」判定 | FACT[財報體檢、`trend_verdict`、235 燈（僅 ETF）、`get_dividend_cash_flow` 近 1 年；配息率只作健檢 A 輸入，**不在 rows 欄位**]。**MISSING 策略分類欄位；MISSING「適合長期持有」單一判定欄**；現「存股」實作＝ETF 定期定額，個股在站內是「衛星／汰換」 | **資料不足**（先需 §7 策略分類） |
| 9 | 資本利得是否需換股／汰弱留強 | 策略分類＝資本利得、換股規則、停利、成長動能 | FACT[`build_switch_advice`、`flag_take_profit`（衛星≥門檻）、`get_switch_in_candidates`；個股汰弱依財報體檢＋趨勢＋KD]。**MISSING 策略分類；「續抱／注意／減碼」統一分級（現只有 `建議動作` 字串）；稅費／持有期完整模型未查證**（`dividend_tax_service` 未讀） | **部分**（換股／停利有既有規則輸出，但無分類與統一分級） |
| 10 | 是否有更適合的新產業／候選標的 | 候選標的（有）＋「新產業」層級候選（無） | FACT[`get_ranked_picks`（5 因子、存活池四項全過、MOPS 季快照 115Q2）、`get_switch_in_candidates`]。**MISSING「新產業」層級候選**（無產業層聚合、無技術世代資料） | **部分**（候選標的可；「新產業」資料不足） |
| 11 | 本期 1–3 個行動 | 行動候選＋排序規則 | **MISSING 選取／排序規則**；VN-09 未實作；HI-1 未核准；DEC-054 要求每個 Action 由可追溯規則支持、強 Action 不得只靠生成式 AI | **需裁示**（可列「規則層已存在的待處理項」引用；合成最重要 1–3 項屬 HI-1） |

> 小結：11 題中**沒有任何一題**可在「不新增規則、不新增來源、不需客戶裁示」下完整回答；第 1 題最接近。這是本計畫必須誠實面對的前提——Brain 的第一版價值在**統一、可追溯、誠實說不知道**，而不是「題題有答案」（`PROJECT_RULES.md` §16.1：不得為了讓產品有答案而製造結論）。

---

## §6 產業趨勢資料盤點

### 6.1 產業分類體系與個股→產業對映

- **分類體系**＝TWSE／TPEx 官方產業別代碼（兩位數，上市上櫃共用；約 35 類）。FACT[`shared/industry_codes.py:OFFICIAL_INDUSTRY_CODE_NAMES`]
- **對映來源**：FACT[`market_close_fetcher.fetch_industry_map_bulk`]：官方 `t187ap03_L`（上市）／`mopsfin_t187ap03_O`（上櫃）為主，FinMind `TaiwanStockInfo.industry_category` 為輔；原始紀錄 `industry_raw.json`（scheme `z43-official-code-v1`）。
- **對映檔**：FACT[`data_cache/sector_flow/ticker_sector.json`]：3167 筆、55 種標籤（含 ETF、ETN、存託憑證、`其他`、`所有證券`、`Index` 等非產業標籤）；泡泡圖再經別名表併為 40 板塊。
- **覆蓋率**：FACT（實測）115Q2 快照 1974 檔與其他 3 個季別皆 100% 在對映檔內。
- **缺口**：①非產業標籤（`其他` 133 檔等）；②同義雙名未併（例 `電子工業`／`其他電子類`／`其他電子業`、`居家生活`／`居家生活類`；別名表僅收有證據者，不因名稱相似就合併）；③**無次產業／供應鏈分類**（例如 AI 伺服器、先進封裝）＝MISSING；④**無 GICS 對映**（ETF 曝險檢查另用 `_ETF_SECTOR_MAP`，口徑不同，**勿統一**）；⑤存活者偏誤：快照只有現存公司。

### 6.2 客戶列的十項逐項判定

| # | 項目 | 判定 | 事實／位置 | 缺口 |
|---|---|---|---|---|
| 1 | 產業營收 | **個股層有；產業層無** | FACT[全市場 MOPS 季彙總快照 `data_cache/fundamentals/*.parquet`，114Q1–115Q2 共 6 季，`revenue` 為**年初至今累計**；單季化 `ytd_to_single_quarter`（L2）；月營收 `monthly_revenue_fetcher`（全市場 OpenAPI 只回最新單月；歷史靠 FinMind 18 月）]。INFERENCE：`ticker_sector.json` × 季快照 join 後 groupby 可得產業單季營收 YoY | 無任何產業層聚合函式；6 季偏短；存活者偏誤；聚合定義（加總 vs 中位數）屬方法決策 |
| 2 | EPS／獲利成長 | **個股層有；產業層無** | FACT[快照 `eps／net_income／op_income／gross_profit`（累計）；跨季比率斜率 `compute_cross_quarter_trends`（個股層）]。EPS／net_income 未單季化 | 同上；產業層 EPS 聚合定義待客戶 |
| 3 | 資本支出 | **個股層部分；產業層無** | FACT[單檔 `fetch_5_years_cash_flow`（FinMind CashFlows，5 年）；全市場快照**無** capex 欄] | 產業層需逐檔抓約 1900 檔現金流量表（配額／時間成本高）；MOPS 彙總有無現金流量表端點＝未驗 |
| 4 | 產業相對強弱 | **部分** | FACT[①資金流泡泡圖 `bubble_latest.json`：40 板塊，20 交易日窗，`daily_net.parquet` 27 交易日（2026-09-11→2026-10-22）；②熱力圖 `TW_SECTORS` 10 檔「單一代表股」`TW_SECTOR_SINGLE_STOCK_PROXY=True`，**非類股指數**] | **無真類股指數價格序列**（yfinance 無；MI_INDEX 一次一日且 repo 標「已永久停用」；FinMind 無類股指數 dataset）。INFERENCE：可用 `TaiwanStockPrice`／收盤價 × 對映自算等權產業指數，屬新 L1／L2 |
| 5 | 法人配置 | **部分（流量有，存量無）** | FACT[`daily_net.parquet` 的外資／投信／自營淨買超金額（億），NaN 不補 0，`tpex_complete` 標記] | 只有流量，**無持股比重／配置占比**；歷史僅 27 日 |
| 6 | 籌碼 | **個股層有；產業層部分** | FACT[個股 20 日法人 `get_chips_readout`；融資 `finmind_margin.parquet`（大盤）；集保大戶爬第三方網站（T3）] | 產業層融資融券 MISSING；融資融券／大戶新 UI 標的頁未接（INFERENCE） |
| 7 | 估值 | **個股當日值有；產業層無；歷史無** | FACT[全市場 PE／殖利率／PB（TWSE `BWIBBU_d`＋TPEx）當日值，TTL_1DAY；357 殖利率位階（個股）] | **無歷史序列落地**（INFERENCE：未見 PE 歷史 parquet）→ 無法畫產業估值分位；金融／虧損股 PE 缺值處理待定 |
| 8 | 景氣循環 | **總體有；產業別無** | FACT[TW PMI（`tw_pmi.parquet` 171 列 2012-07→2026-09）、NDC 景氣燈號／領先指標（FinMind `TaiwanBusinessIndicator`）、M1B／M2] | 無工業生產指數、外銷訂單（grep 僅命中說明字串）、無產業別 PMI 細項（CIER 有，repo 只取總指數） |
| 9 | 產業事件 | **無** | MISSING | 無資料、無分類；新聞（T4）僅文本，**不得由 LLM 從新聞歸納成「產業事件」入 Digest** |
| 10 | 技術世代變化 | **無** | MISSING | 無正式資料源可機械取得；若要做需客戶先定義範圍；任何題材／供應鏈資料庫多為商用或第三方整理（授權／可信度未驗） |

### 6.3 來源候選（僅列，不導入）

> 判定欄「Gate」：**Y**＝新外部來源，需 Customer Gate（v3 §03-2 ②／CLAUDE.md §2.1 來源註冊）；**N**＝repo 既有來源重組，屬內部自決（但新增畫面元素仍須 UI 草稿 Gate）。可信度／授權／成本欄皆為撰寫者已知、**未驗證**，不得當事實。

| 需求 | 候選 | 可信度／授權／成本 | Gate |
|---|---|---|---|
| 產業營收／EPS 聚合 | **repo 既有**：MOPS 季彙總快照＋官方產業別對映（INFERENCE：不需新外部來源） | T1 官方；免費；已在跑；限制＝6 季、存活者偏誤 | N（聚合定義＝方法決策，建議列 §10 Q5） |
| 更長歷史（>6 季） | 同一 MOPS 端點回補更早季別（`update_fundamentals_snapshot.py --roc-year --season` 已支援） | T1；免費；舊季端點是否仍可用＝未驗 | N（屬資料回補作業，建議知會客戶） |
| 產業別資本支出 | FinMind `TaiwanStockCashFlowsStatement`（repo 已用於單檔）逐檔聚合 | T2；需 token＝配額壓力；全市場約 1900 檔×多季 | N（既有 dataset）／成本需評估 |
| 真類股指數序列 | 自算等權產業指數（FinMind `TaiwanStockPrice`＋對映）；或 TWSE `MI_INDEX`（repo 標永久停用） | 自算＝新 L1／L2；MI_INDEX 穩定性不足（repo 自陳） | 自算 N（但屬新資料流，需 §8.1 架構規劃＋UI Gate）；MI_INDEX 重啟需 Gate（推翻既有停用決策） |
| 產業景氣 | 經濟部統計處：工業生產指數、外銷訂單、製造業銷售量值；財政部海關進出口（repo §2.3 已列 MOF 進出口） | T1；免費；是否有穩定 API／是否含產業細分＝**未驗** | Y |
| 產業 PMI 細項 | CIER（中經院）細分產業指標 | T3 第三方網站爬取；授權未查；穩定性差 | Y（且列風險） |
| 產業估值歷史 | TWSE `BWIBBU_d` 每日抓＋自行落地累積（repo 已抓當日值、未落地） | T1；免費；無法回溯，只能從開始累積起算（PIT 友善） | N（新增落地檔＝新資料資產，建議知會） |
| 法人持股比重（產業層） | TWSE 外資及陸資持股統計（日）、集保戶股權分散表（週） | T1；免費；端點是否已在 `data_registry.py` 登記＝未驗 | Y（新端點） |
| 技術世代／結構變化 | 無機械化正式來源 | 不建議；AI 不得自創標籤 | Y（若要做，先由客戶定義） |
| 大盤 EPS／PE（§4 `valuation`） | 老師資料原件不在 repo；`VN1-MT-VALUATION` 研究中 | DEC-081 第 10 點明禁「新增 EPS 來源」 | Y（High Gate） |

### 6.4 不需新外部來源的聚合做法（全部標 INFERENCE，未驗）

- 產業單季營收 YoY：`季快照.revenue`（先單季化）× `ticker_sector.json` → groupby 產業。
- 產業獲利趨勢：同上，用 `net_income`／`gross_profit`／`op_income`（先單季化）；EPS 的產業聚合定義（加總淨利 vs 中位數 EPS）**屬方法決策，需客戶 Gate**。
- 產業估值（當日）：`BWIBBU_d` × 對映 → 中位數；**無歷史，不得宣稱分位**。
- 產業資金流：沿用 `daily_net.parquet`（已為產業層）。
- 這些聚合會是**新的規則模組**（`rule_id` 需新設、版本化、可獨立測試——`PROJECT_RULES.md` §19.4），**不是 UI 的簡化**。
- 聚合結果必須帶：覆蓋率、存活者偏誤旗標、期別（公告季 ≠ 交易日 ≠ 當日 PE，三者 `as_of` 分開標示）。

### 6.5 明文

> **不得用 LLM 常識宣告某產業已衰退或崛起。** 任一產業的「變強／轉弱／結構性衰退／下一個成長產業」結論，只能來自 Digest 內由規則層產生、帶 `rule_id＋rule_version＋evidence_refs` 的 `industry_trend[]`。資料不足時，Brain 必須說「不知道」。客戶規格 §七、§九②同向。

---

## §7 策略分類（存股／資本利得）最小資料契約需求

### 7.1 現況

- FACT[`gsheet_portfolio.py:_HEADERS`] 持股分頁僅 5 欄：`name(組合名)／ticker／lots／avg_price／updated_at`；觀察清單分頁 3 欄：`name／ticker／updated_at`。
- FACT[`holdings_service.py:_row`] `asset_class` **由代號規則推導**：ETF→`core`、個股→`satellite`，與所在清單脫鉤；docstring 自承「近似，主題型 ETF 會被算核心」。FACT[`dividend_station_service.compute_allocation_split`／`flag_take_profit`] 80/20 與衛星停利以 `種類=="個股"` 判衛星。
- FACT[grep `存股|資本利得|核心.*衛星|投資目的|strategy_type|purpose`]：**未見任何 Sheet 欄位或 session 欄位儲存「每檔的投資目的」**（單組 grep，未逐檔窮舉）。
- **MISSING**：每檔策略類型欄位、讀取、寫入；目標權重；買進日期／交易流水；使用者實領配息記錄。
- FACT[`page_me.py` 檔頭] 👤我的 P1 唯讀，「不搬 CRUD、不寫 Sheet 內容」；組合／觀察清單／持股列 CRUD 仍在舊「📁 組合管理」。選定只活在 session，不持久化。
- 衝突（INFERENCE）：現行「核心／衛星＝ETF／個股」與客戶「ETF 可以是資本利得、個股也可以是存股」**直接相反**；站內「存股」現實作＝ETF 定期定額。若 Digest 沿用 `legacy_asset_class` 當策略分類，會**系統性分錯類**——因此 §4 `HoldingBlock` 把它降為「僅供對照」。

### 7.2 最小資料契約需求（只列需求，不設計寫入）

1. 每個「持有列」可綁一個 `strategy_type ∈ {存股, 資本利得}`；**缺值讀成「未分類」**，不得預設成任一類，不得由 ETF／個股推導，不得 AI 猜（§1；客戶規格 §六）。
2. **鍵與作用範圍待客戶定**（§10 Q1）：**推薦以 `ticker` 為鍵（每檔一個分類）；替代案＝以 `組合×代號` 為鍵**（同一檔需同時兩種目的時才升級）。
3. 觀察清單是否需要「預定目的」＝待客戶。
4. 若要算「自買進起」績效（含息總報酬／XIRR／CAGR），另需買進日期（目前無）；**此為績效需求，不屬策略分類最小契約**，單列為缺口。
5. 現有 5 欄表頭不得被破壞：FACT[L1 對右側使用者自加欄「讀取不影響、寫入時原樣保留」；表頭不符 → `SheetSchemaMismatchError`，寫入前 raise]。
6. **寫入面屬新授權**：把分類設定放進「👤我的」＝新增寫入 Google Sheet（HI-5：寫入類與 Sheet CRUD，未核准）；也超出 👤我的 P1「唯讀」授權。需 High Gate。
7. **在客戶提供正式分類並核准寫入機制前**：Digest `holdings[].strategy_type` 一律 `未分類`；③存股、④資本利得兩段顯示「尚未設定投資策略分類，無法判定」。這是**誠實的第一版行為**，不是缺陷。

---

## §8 實作批次建議

> 本節為**建議**，不是排程授權。所有批次開工前須：①重新過 DEC-084 Model×Effort Gate（若建議配置與目前不同，須在 Safe Checkpoint 停手等客戶切換並回覆「改好了」）；②Old→New Coverage 對等驗收；③依 CLAUDE.md §-2 派工與獨立複驗；④不夾帶 HI-1～HI-6、不改 Risk Cap／門檻／權重／趨勢定義／估值公式。
> **順序前提**：
> - **D2 Cloud 啟動事故未結案**：FACT[BACKLOG `NEWUI-STAGE-D2-BOOT-INCIDENT`] 根因未確認、Cloud traceback 未提供、`waiting_for_customer`；D3～D5 凍結（客戶 2026-10-27 亦指示停止）。已補的 `tests/test_boot_import_smoke.py` 是守衛不是根因。候選假說（Cloud 殘留舊 `shared.ia_nav`、部署 commit 非 main、環境差異）皆未證實。
> - 因此：**凡會動 `shared/ia_nav.py`、`app.py`、`src/ui/views/shell_nav.py` 的批次，一律排在事故結案之後**。純新增 L0／L3 模組、不接線的批次，可先行，但每批 PR 須過 boot import smoke。
> - **High Gate 項目**（不預設通過）：EPS×PE 公式與資料來源、Risk Cap 核准顯示、策略分類寫入、新外部來源、行動排序規則（HI-1）。

| 批次 | 範圍 | 前置 | Gate | UI 草稿先行 | DEC-084 建議（Model×Effort） | 獨立於導覽殼 |
|---|---|---|---|---|---|---|
| **AB-0 Digest 契約** | L0 schema（欄位、`status`／`missing_reason` 枚舉、`rule_id／rule_version／evidence_refs` 規範）＋契約測試；**純契約、不接任何 UI、不取數** | **客戶另行明示授權本批實作**（DEC-091 未授權任何實作）；§4 草案獨立審查 | 新資料契約（建議 Opus 領域）；不涉及投資語意改動；不需 UI Gate | 否 | **Opus + Medium**（DEC-084：新資料契約屬 Opus；可逆且範圍受控 Medium） | **是** |
| **AB-1 Digest Builder（只聚合既有輸出）** | L3 builder：把 `get_macro_state`／`get_allocation`／`build_station_digest`／`compute_industry_concentration`／`get_ranked_picks` 等**既有輸出無損搬運**成 Digest；缺值以 `status` 表達；為既有輸出補 `as_of` 的**讀取側**映射（不改規則） | AB-0；§8.1 架構規劃（內部）；`as_of` 缺口（契約無逐指標 `as_of`）的處理方式需內部拍板並揭露 | 不新增來源；若需**擴充**既有契約（例如 `get_macro_state` 外露 `as_of`）→ 屬契約變更，須獨立 QA 並確認不改規則輸出 | 否 | **Sonnet + Medium**（一般跨模組 wiring）；若觸及 Risk Cap 讀端語意則停手重判 | **是** |
| **AB-2 Grounding Validator＋降級＋統一出口** | 規則式驗證（G1～G6）、規則式摘要模板（無 AI 版）、統一「AI 不可用」型別、單一傳輸層（**新增，不改舊出口**）、金鑰與用量計量 | AB-0、AB-1；內部拍板（按鈕觸發、Brain 獨立 persona） | 內部拍板（改全站 persona 才需 Gate，`CV1-FU-06`），**本批不改 persona**，Brain 使用自己的 system prompt；新增 AI 出口依 `PROJECT_RULES.md` §4 第 6 項屬 substantive AI behavior → Decision Gate（BP-DR-20） | 否（無畫面） | **Sonnet + Medium**；驗證規則設計若涉及輸出格式契約可升 Opus（屆時停手） | **是** |
| **AB-3 產業趨勢聚合（既有來源）** | 新 L2 規則模組：產業單季營收 YoY／獲利趨勢（用既有 MOPS 快照＋官方產業別對映）；產業資金流引用；覆蓋率與存活者偏誤旗標；`rule_id` 版本化 | **§10 Q5 聚合定義裁示**；§6.4；`ytd_to_single_quarter` 對 EPS 的單季化需先驗 | **High Gate**（新規則＝投資語意；聚合定義）；若需回補更長歷史（>6 季）→ 資料回補作業，知會客戶 | 否（本批無畫面；呈現在 AB-5 之後的標的頁） | **Opus + Medium/High**（DEC-084：投資核心語意；影響重大者 High） | **是** |
| **AB-4 策略分類契約** | L1 讀取側：從客戶指定位置讀 `strategy_type`，缺值＝未分類；**不含寫入** | **§10 Q1 裁示**（位置、鍵、粒度） | 讀取＝契約；**寫入（含放進 👤我的）＝HI-5 High Gate**，另批 | 若放進「我的」頁＝是（欄位增減） | **Opus + Medium**（資料契約＋Sheet schema 相容） | 讀取側**是**；寫入面否 |
| **AB-5 🤖 AI 投資總結卡（桌面＋手機）** | UI：全站唯一總結卡、五段、可展開；消費 AB-1 Digest 與 AB-2 輸出 | AB-0～AB-2；**導覽殼重畫（D2.5 4 頁 IA）已客戶核准**；**D2 Cloud 事故結案**；UI 線框（D2.5 A／B 部）客戶核准 | UI 草稿先行 Gate（v3 §03-2 ①，已含於 D2.5 線框；仍需客戶核准線框）；Customer Design Gate | **是（已隨 D2.5 提供，需核准）** | **Sonnet + Medium**（一般 UI） | **否**（依賴新殼） |
| **AB-6 「查看依據」元件** | 通用折疊元件，直接渲染 Digest 的 `evidence_refs`／`as_of`／`rule_id`／`missing`／`availability`／`ai_participation` | AB-5 同；A4 裁示（D-29 改寫） | 不得涵蓋 HI-3 內容；依據文字須讀 L0 規格表，不新寫門檻（DEC-085 §9／D-17） | 是 | **Sonnet + Medium** | **否** |
| **AB-7 新外部來源研究／導入** | 經濟部統計處、海關、集保股權分散、外資持股統計等候選的**研究清單**（端點、授權、穩定性）；導入另案 | §10 Q5 客戶是否開研究 | **Customer Gate（新外部來源）**＋CLAUDE.md §2.1 來源註冊 | 否 | 研究 **Sonnet + Medium**；導入視資料契約變更判定 | **是** |
| **（暫緩）大盤 EPS×PE 圖C** | `VN1-MT-VALUATION` | 老師資料原件、EPS 來源、PE 情境、公式、更新頻率的 High Gate 核准 | **High Gate**；DEC-081 第 10 點禁新增 EPS 來源 | 是 | Opus（投資核心語意） | 否 |
| **（暫緩）本期行動合成** | 行動選取／排序 | §10 Q4；HI-1 | **High Gate（HI-1）** | 視情況 | Opus | 否 |

**建議順序**：（建議順序，皆**需客戶另行授權**才開工）AB-0 → AB-1 → AB-2（三批皆為 L0／L3、不接線、可在事故調查期間進行，每批 PR 須過 boot import smoke）→ 等事故結案與 4 頁導覽核准 → AB-5／AB-6。AB-3、AB-4 讀取側與 AB-7 研究可平行（寫入端仍序列化，一次一檔，PROCESS.md §3）。

---

## §9 風險與 HI-1～HI-6 邊界

### 9.1 風險

| # | 風險 | 說明 | 緩解 |
|---|---|---|---|
| R1 | **Digest 變成第二套真相** | 若 builder 重算或補值，會與規則層分叉（違 §19.3 SSOT） | Builder 只搬運；AB-0 契約測試：Digest 欄位值必須可追溯到單一上游輸出 |
| R2 | **缺值被轉成確定語氣** | 既有路徑已有 `.get(…,0)`（R4）；Brain 若沿用同寫法會「賣超0張」 | Digest 一律 `status`＋`null`；Grounding G3 |
| R3 | **「空答案壓力」** | 11 題多數資料不足，易誘發 AI 或模板「湊答案」 | §16.1「不得為有答案而製造結論」；G5 要求資料不足明示 |
| R4 | **產業結論由 LLM 常識產生** | 最容易發生，且最難被使用者察覺 | G1／G4；§6.5 明文 |
| R5 | **聚合偏誤** | 6 季、存活者偏誤、累計欄未單季化、公告季≠交易日 | `coverage`、偏誤旗標、期別 `as_of` 分開；方法裁示（§10 Q5） |
| R6 | **策略分類被推導** | 沿用 core／satellite 會系統性分錯類 | `strategy_type` 預設＝未分類；`legacy_asset_class` 僅對照 |
| R7 | **AI 成本失控／額度共用** | 金鑰池共用、無用量計量、每次 rerun 重算 | 按鈕觸發；用量計量；失敗不快取 |
| R8 | **persona 衝突** | 「給出明確動作」與 DEC-054 第 6 點張力（`CV1-FU-06` open） | Brain 不用該 persona；修改走 Gate |
| R9 | **動到出事故的模組** | `shared/ia_nav.py` 是 D2 Cloud 事故現場 | AB-0～AB-2 不碰；UI 批次待事故結案 |
| R10 | **大盤 as_of 缺口** | `get_macro_state` 契約無逐指標 `as_of` | AB-1 內部拍板處理並於報告揭露；不改規則輸出 |
| R11 | **單組盤點偏差** | 本檔 FACT 皆單組讀碼，未複驗 | 各批開工前由獨立一組重驗承重 FACT（尤其「0 命中」類） |
| R12 | **Level 3 洩漏到首屏** | 「查看依據」若預設展開會違反客戶資訊層級 | 預設收合；UI 守衛測試 |

### 9.2 HI-1～HI-6 邊界（FACT[BACKLOG `NEWUI-HIGH-HI1-6`]：全部 `not started`、**未核准**，DEC-089 條件 4：Stage D 各批不得夾帶）

| HI | 範圍 | 本計畫的擦邊點 | 邊界處理 |
|---|---|---|---|
| **HI-1** | 行動語彙／作戰室搬家 | ⑤「本期行動」、`actions[]`、各頁頂部「需要處理」 | `actions[]` 僅可**引用**既有 deterministic 項目；**不新增行動語彙**；合成／排序規則待 HI-1 核准；未核准前 `priority_rank=null`，⑤ 允許顯示「無可判定行動」 |
| **HI-2** | 逐檔加碼金 | 持股摘要、換股建議 | Digest／Brain 不含加碼金額 |
| **HI-3** | 三維出場與買賣語意（停損停利／目標價／部位大小） | 「查看依據」若涵蓋停損停利、資本利得「減碼」語意 | 「查看依據」**不得涵蓋** HI-3 內容；既有 `flag_take_profit` 僅作為已存在規則輸出被引用，不擴張 |
| **HI-4** | 再平衡與葡萄串 | 「是否需降低配置」「換股」 | 不產生再平衡指令；目標權重 MISSING |
| **HI-5** | 寫入類與 Sheet CRUD | 策略分類寫入、觀察清單寫入、AI 摘要落檔 | AB-4 僅做讀取；寫入另批 High Gate；Brain 不寫回任何 Sheet／檔案 |
| **HI-6** | 推播入口 | cron 預產摘要、推播 | 若日後改採 cron 預產，推播入口仍另案 |

---

## §10 客戶 Gate（全套統一 Q1–Q6）與內部拍板

> 2026-10-27 依獨立 QA 統一：客戶只被請示少量真正需決定的問題，全套文件（A／B／C／PLAN）同為 6 題。客戶可回「採推薦」。

| # | 題目 | 推薦 | 理由 |
|---|---|---|---|
| **Q1** | **投資策略分類（存股／資本利得）存在哪、怎麼寫入？** | **以 `ticker` 為鍵、每檔一個分類**，存於客戶 Google Sheet「獨立分頁（比照 `stock_watchlist`）或持股分頁右側新欄」，兩者皆可（以 A §8.2 為準）；**讀取側先做，寫入面另批（HI-5 High Gate）**。**替代案**：以 `組合×代號` 為鍵（同一檔在不同組合有不同目的時） | L1 已容忍右側自加欄、不破壞現有 5 欄表頭；單鍵最簡單；缺值＝「未分類」，不由 ETF／個股推導、不由 AI 猜。寫入屬新授權，不併入本批 |
| **Q2** | **台股／國際趨勢怎麼定義？圖A／圖B 要畫哪些線？**（併入 `VN1-MT-TREND-DEF`，**High**） | 推薦 (b)：圖A 畫既有 MA5／60／120／200 當「參考線，不構成趨勢判斷」、圖B 沿用 INTL_MAP 五條（按海外／利率／美元分組）；**趨勢「定義」仍待客戶**，定義前結論位維持「⬜ 尚未定義」。備案：(a) 只畫收盤＋現值卡；(c) 客戶指定定義與線 | 資料足（twii 日線可畫），缺的是定義；AI 不得補。屬投資語意 |
| **Q3** | **市場圖D 第一層 3–5 項怎麼挑？** | 推薦 R-A：五桶各取最差一項。備案：R-B 全 16 燈依危險度取前 N；R-C 客戶固定指定；R-D 只列最差等級上限 5 | 挑選即排序，屬業務語意；不由 AI 決定 |
| **Q4** | **持股四態（續抱／注意／減碼／換股候選）與「本期 1–3 個行動」的排序規則**（HI-1 邊界） | **暫不合成**：僅引用規則層既有待處理項，`priority_rank=null`，四態先只顯示現有「建議動作」；另開研究提案一套規則供客戶核准 | 由 AI 自行排序違反 DEC-054 第 6 點與 D4；新增標籤與排序均為投資語意，需 High Gate。先讓 ⑤ 誠實可用 |
| **Q5** | **產業趨勢口徑與排序；是否開啟新外部資料來源研究**（研究≠導入） | **口徑**：先做「產業單季營收 YoY（中位數）＋覆蓋率＋存活者偏誤旗標」，用既有 MOPS 6 季快照，不新增外部來源（聚合方式與排序仍由客戶核准）。**研究**：開研究清單（只研究端點／授權／穩定性，不導入） | 「結構性衰退」「新產業」沒有新來源只能「不知道」；先研究不導入，不增風險；導入另走 Customer Gate |
| **Q6** | **D2 殼／佔位頁／DEC-090 處置與 D2 重新驗收**（含 Cloud 啟動事故） | 由 D2.5 治理文件（A／PLAN）承接；事故結案前凡動 `shared/ia_nav.py`、`app.py`、`src/ui/views/shell_nav.py` 的批次一律不開工 | 見 §8 順序前提 |

**已知前置 Gate（非新題）**：大盤 EPS×PE 公式／資料來源／PE 情境（High；圖C 維持 Research、不顯示數字，`VN1-MT-VALUATION`）、正式 Risk Cap 核准顯示（DEC-081 Q2-2；待 C2b＋RC-VISIBILITY）。

**內部拍板表（客戶不需回答；依 §-1.5 第二條，交付報告揭露）**

| 項目 | 內部結論 | 理由 |
|---|---|---|
| AI 總結何時產生（原 §10-1） | **第一版按鈕觸發**：規則式摘要先出，AI 潤稿按了才呼叫；cron 預產另案（屬新自動 AI 行為，且牽涉 HI-6 推播） | 全站採按鈕 gate 控成本與 rerun 重算；保留日後升級空間 |
| Brain 的 persona 與既有 persona 衝突，`CV1-FU-06`（原 §10-5） | Brain 用獨立 system prompt，不沿用舊 persona，舊出口暫不動 | 同步改全站 persona 會動所有舊 AI 出口行為、擴大範圍（§-1） |

**其餘既定處置**：四向正式頁名、D2 殼與佔位頁退場等治理細節見 R5 衝突盤點 A1～A19，由其他部文件承接（其中需客戶決定者已併入 Q6）。

---

### 附：本檔未驗證事項（誠實揭露）

1. 全部 FACT 為單組讀碼／讀本地資料檔，**未跑測試、未連網、未開 App**；所有「0 命中／沒有」皆為單組 grep，未窮舉。
2. 外部來源（§6.3）可用性、授權、端點存在與否、成本**一律未驗**。
3. 台股趨勢／國際趨勢是否已有獨立輸出契約（`PROJECT_RULES.md` §19.4 提及的模組）**未查**；`judge_news_sentiment` 的 `label='中性'` 是否被下游當真中性使用**未查 caller**；`dividend_tax_service` 稅費是否足以支撐換股判斷**未讀**。
4. `data_cache/` 中 PE 無歷史序列、「個股風險 L3 不存在」「融資融券未接新 UI」為由 grep／檔頭推得的 INFERENCE。
5. §4 Digest 欄位與 §2.4 Grounding 規則為**草案**，尚未經獨立 QA；承重前提（尤其「現有 AI 無輸出後驗證」）開工前須由第二組複驗。
6. 本檔未提出、亦不授權任何 Risk Cap、門檻、權重、趨勢定義、估值公式修改；HI-1～HI-6 一律未核准。
