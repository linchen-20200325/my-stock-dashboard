> **歷史／適用性引言（2026-11-07 抽出）**：本檔自 Draft PR #1030（head 1e5afee1） 原內容抽出保存（來源分支 `docs/newui2-data-page-trend-onebrain-pdf-20261106`），抽出日期 2026-11-07。
> 此為歷史草案／研究材料，**不是現行施工依據**；現行方向以 DEC-142／DEC-146 與 `NEWUI2_TOP_FIVE_APPROVED_VISUAL_AND_SAFETY_GATE_2026-11-07.md` 為準。
> 補註：3／6／9 個月固定時域已被 `ONEBRAIN_EVIDENCE_COVERAGE_TOKEN_BUDGET_SHORT_MED_LONG_2026-11-06.md` 的短／中／長取代（DEC-142）；輸入隔離原則部分仍可參考。

# New UI2｜籌碼、前夜美股、短中長視角與 OneBrain 完整情報藍圖 v0.1

> **PROPOSED／docs-only／待資料及視覺 Gate**。本文件是 2026-11-06 客戶需求「其他投資頁精簡，但 AI 要看到新聞、缺貨與大量訂單等完整研究」的施工前規格，不是正式預測模型、資料來源或 AI runtime 授權。主軸仍為「台股趨勢／國際趨勢」兩條，與市場位階、Risk Cap、System Action 分離。

## 1. 產品層：五頁而不是四頁

| 頁面 | 主要用戶可見內容 | 資料狀態處理 |
|---|---|---|
| 📊 市場 | 市場結論（無正式趨勢定義則保留尚未定義）、短中長三視角的**研究摘要**、台股主圖、前夜美股領先訊號、外資/融資籌碼小卡與國際圖 | 具體數字旁保留必要 missing/as_of；不再顯示全站資料來源健康總表 |
| 🎯 標的 | A 成長動能／B 價值錯殺、個股基本面/估值、法人持股、集保散戶人數／大戶比例、籌碼趨勢、產業訂單證據（有來源才顯示） | 缺的指標逐格誠實標，資料抓取明細在「資料」 |
| 💼 持股 | 組合風險、正式 action、曝險及個股籌碼警示；#1028 已核准 W-11 純空槽不退化 | 不把未登入當 0 檔、不用缺資料代替無風險 |
| 👤 我的 | 帳戶、Sheet、設定、通知、權限、只讀稽核入口 | 不重複全站健康列表 |
| 🗂 資料（新） | **全部來源總覽、失敗清單、過期、尚未接線、最後成功/失敗原因、受影響頁面與欄位** | 唯一完整來源健康度列表；細節脫敏；Capability/Data/Judgement 不混 |

## 2. 舊 UI 與現有服務證據（必須保留來源，不是等於可以立即接 UI2）

| 功能 | repo 既有證據 | 正式狀態／安全限制 |
|---|---|---|
| 外資現貨買賣超／投信／自營商 | `src/ui/tabs/macro/section_chips.py`、`src/services/macro_refresh_service.py` inst、`shared/data_categories.py` | 有讀取/呈現線索；須逐欄查 production producer→canonical→UI2 VM；未觀測不得 L1 預填 0 冒充真值 |
| 外資期貨/PCR/籌碼先行 | `section_chips.py` | 先引用既有字樣和單位；部分估算 proxy 必明標，不直接沿用舊 UI 行動文案或門檻 |
| 融資餘額與 ETF 散戶流 | `shared/data_categories.py` 有台股融資；PDF P39/40 是研究來源 | PDF 的散戶 ETF 申購額不是 repo 已有的正式每日散戶持股比例來源 |
| 集保大戶/散戶結構 | `src/ui/tabs/chip_radar.py`（散戶人數、大戶比例）→ `src/data/stock/chip_concentration_fetcher.py` L1 | **散戶比例尚需分母、持股級距定義與真來源**；禁止把「散戶人數」標成「散戶持股%」 |
| 前夜美股 → 台股 | `shared/global_lead_markets.py` 既有完整夜盤/隔日對齊清冊與風險研究；`src/ui/tabs/macro/section_long.py` 有 SOX/DXY 舊 UI 研判；`src/services/macro_refresh_service.py` 有 DJI/NASDAQ/SOX/10Y/DXY | 以**美股最近一個已完成收盤**對台灣下一交易日，不以台灣日曆前一天硬對，並處理時區、美台休市、資料源延遲、夜間期貨和現貨差異；既有舊 UI 動作語句不得直接變新正式 action |

### 前夜美股顯示方式（提案）

台股頁一張「美股前夜對台股的觀察」卡：費半 SOX、NASDAQ、S&P500、DJI 與可用領先市場（已核准清冊才可列）；每項顯示最近完整收盤變化、相對台股下個交易日、`market_session_date`、`as_of`、source、freshness、是否有多市場共振。顯示 **「傾向風險/有利背景/方向未明/資料不足」** 等研究敘述前先具現有正式 RuleID 或另過 Trend Definition Gate；不可在欄位缺失時直接預言明日開盤或報出概率。

**重大警示**：`shared/global_lead_markets.py` 自述的有限樣本已觀察到「費半單跌不等於台股必跌」、台股本土因素能造成大跌；要讀它的異常日、交易日配對、非市場日與實證限制。舊 `SOX×DXY` 關於「重壓/減碼」等用字不是本批授權的決策規則。

## 3. 短中長是三個「觀察時窗」，不是三個獨立 Risk Cap

**建議視窗（全部 PROPOSED，待客戶確認）**：
- **短期**：未來數日～數週（例 1～20 個交易日），問題：「前夜美股與本地籌碼使近日波動/方向有哪些風險？」證據：SOX/IXIC/SPX/DJI 前夜、三大法人、外資期貨、融資變化、新聞事件與市場流動性。
- **中期**：未來 1～3 個月，問題：「基本面與資金動能是否同步改善？」證據：月營收 YoY、EPS 修正、財報 guidance、法人籌碼趨勢、利率/景氣領先指標與產業訂單節奏。
- **長期**：未來 6～24 個月，問題：「新技術供應鏈是否有可兌現的結構性成長？」證據：產能、良率、缺貨及價格、客戶正式訂單/法說、CSP CAPEX 兌現、FCF、庫存/毛利與對手擴產、產業世代替代風險。

每窗輸出候選：`horizon`、`state`（未經正式定義僅研究/尚未定義）、`supporting_evidence`、`counter_evidence`、`source`、`as_of`、`freshness`、`coverage`、`limitations`、`next_verification`；不新增 scalar confidence/% 或把看多看空直接翻成加碼減碼。短弱、中強、長多是**可容許共存的解釋**，由 Single Action Authority 與正式 Risk Cap 另行約束實際動作。

## 4. OneBrain 的完整情報/資料層分工

```text
[市場/股市/籌碼/公告/財報/新聞來源]───(已授權來源才可擷取)
  ↓
L1 取得＋L2 標準化＋來源/時間/去重/錯誤/版權限制
  ↓
Canonical Facts / Event Facts ── 不讓新聞敘事變成未驗證客觀事實
  ↓
Validated deterministic rules / Risk Cap / System Action authority
  ↓
Headless Complete Evidence / Decision Digest（含反證、缺資料、provenance）
  ├── Human UI 五頁：少量結論、合法圖/必要限制；總資料健康在「資料」
  └── OneBrain：全量證據語意 coverage＋按需溯源檢索，不靠 UI Top-N
          ↓
    短／中／長觀察解讀、待核實催化劑、反面情境、
    持股風險／候選研究（不得捏造正式 action 或 backwrite）
```

**完整不是丟全部 raw blob 給模型**：完整 required-field coverage、原始來源索引、時間與證據引用、反證不丟、缺值不補；昂貴詳情用按需 retrieval。新 AI 來源只在經授權後的 extractor/normalizer 進資料層；AI 不直接寫 canonical 或自行抓資料。

### 新聞／缺貨／大單事件：必需的證據等級（proposal）

| 狀態 | 例子 | 是否可下結論 |
|---|---|---|
| `RUMOR` 待核實 | 社群轉貼「缺貨」或未具名客戶大單 | 只可放「待查」，不得視為 confirmed demand |
| `REPORTED` 已報導 | 可追溯媒體稿及發布/事件時間、發言人、具體產品/公司 | 可引用為報導，但不能寫「訂單已確認」 |
| `CONFIRMED` 一手證據 | 公司公告/正式法說/監管申報/審核可追溯重大合約 | 可標已確認，但仍需確認訂單時間、產能和營收認列 |
| `VALIDATED_IMPACT` 財報驗證 | 連續營收/毛利/庫存/交期與訂單兌現相互驗證 | 才能提升「產業趨勢已反映獲利」的研究可信性；仍非自動投資動作 |

以上是**提議研究標籤，不是新正式 enum/資料契約或 RuleID**；需正式設計/來源 Gate 才落實。任何題材都要有 negative evidence：取消訂單、客戶砍 CAPEX、競爭供給開出、庫存上升、良率/驗證延後、訂單未兌現與估值過高。

**產業範圍**：半導體先進製程、先進封裝、伺服器、記憶體、散熱、電源、PCB/ABF/連接器等（PDF P29、P54 的研究線索）；並保留跨產業世代演變監控。不得從 PDF 的市場排名自動映射上市櫃公司/訂單關係。

## 5. 必須先過的 Gate / QA

1. **第五主頁**：正式增加導航和將 P6 健康列表搬到「資料」前，視覺/整體契約＋mobile 44px/JS_V4/a11y/五頁導覽測試。不得僅修改一個 labels 常數或把 P6 複製成第二份資料健康 SSOT。
2. **資料真值**：籌碼、散戶分級、前夜美股逐欄 lineage；來源缺欄明列，資料日與台灣交易日連接必須正確；避免連續休市／美台假日/夏令時/look-ahead。
3. **趨勢定義**：現有 `MARKET_TREND_RESEARCH_BASELINE_2026-11-03.md` 與 `VN1-MT-TREND-DEF` 仍是 **Research/Pending**。不新增短中長買賣門檻、概率、加權公式；若提出正式模型須時間切片/OOS、樣本外、揭露 regime drift 與成本。
4. **OneBrain Digest**：對每域列 required/available/missing/blocked counts，bidirectional evidence lineage；AI 用到的新聞必有 publication_time/event_time/來源 URL 或證據 ID、claim/state、適用公司/產業、正反證、是否更新/撤稿；避免資料洩漏/隱私。
5. **PDF 授權**：研究素材不是最新行情自動來源，文內頁碼與研究內容可作內部筆記，不能大量複製原圖表或將報告價位當正式預測。

## 6. 待客戶確認的最小集合

- **U-01**：新增第五主頁「資料」並把完整健康總表移出「我的」（客戶方向已明確；剩下導航位置與視覺稿未核准）。
- **U-02**：短／中／長的視窗先用「數日～數週／1～3 月／6～24 月」作研究表述（非承諾模型），是否符合使用者期待？
- **U-03**：「散戶比例」需先確認想看的是集保**散戶人數/持股比例**，還是交易所/集保定義的散戶交易占比。三者不一樣，不許自行混稱；先把已存在的「散戶人數、大戶比例」接回設計。
- **U-04**：OneBrain 新聞與訂單/缺貨監控只先規劃 sources+verification+Digest coverage；新來源、付費、事件 enum、通知及真實 AI 運轉待獨立授權。
