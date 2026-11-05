# New UI2｜設計 → Claude Code 分批施工交接（2026-11-06）

> **本檔為設計與執行交接清單，不等於已核准所有 Layout、來源或 OneBrain runtime。** 客戶指示：「目前就先這樣規劃，後續藍圖寫入、讓專案 AI 寫 code 的陸續工作交給 ChatGPT。」ChatGPT 負責藍圖／規格治理、獨立驗收與 Claude Code 的分批施工提示；Claude Code 負責 New UI2 產品施工。**不能藉此委派自行越過既有 Gate。**
>
> 基準 main `343f0e0e`（2026-11-06 查核）。目前 Draft：#1022 統一藍圖、#1027 W-11、#1029 市場/標的線框、#1030 本批擴充；#1023/#1025 是另一組資料架構工作，優先避免共同檔案及契約衝突。#1028 已合併（W-11 presentation-only）。開工前必須重新檢查最新 main／Open-Draft PR／diff／CI／branches，以下 SHA 與編號不是永遠最新。

## 一、已確立的產品方向（仍需依最新正式 DEC 逐項核對）

1. 五頁：📊 市場／🎯 標的／💼 持股／👤 我的／🗂 資料。**獨立資料頁**集中來源健康總表與抓不到的清單；其他投資頁只保留判讀必需的缺值/日期/來源，不放完整診斷牆。
2. 💼 產業曝險/集中度對**個股與 ETF**皆適用；直接持股分類與 ETF 成分股 Look-through 分開，若成分權重來源/日期不足，不得假冒完整穿透曝險；正式計算與來源另 Gate。
3. 財報體檢：第一版 `financial_health_engine.py`、`shared/financial_health_thresholds.py`、`fin_trend_score.py`、`fin_health_diff.py` 既有財務能力保留。🎯 個股頁只顯示最重要財務安全/獲利/趨勢/警示；完整證據給獨立、headless Digest，不改既有財務公式或門檻，不用姓名命名功能。
4. 📊 前夜美股（SOX/IXIC/SPX/DJI 等）＋外資/散戶籌碼；整合 PDF 的**研究方法**而非當下價格。美股最近完整收盤與下一台股交易日需正確對齊，不能因一個市場下跌就預言台股必跌。
5. OneBrain 所有回覆**白話文**；分頁專家入口（市場／標的／持股／資料；👤 設定優先）、加總結 OneBrain。每頁可做 scoped evidence 分析，最終總結需回查同一個 Evidence Ledger 的來源和反證；不是把各 AI 文章再丟給第二個 AI 讓錯誤放大。
6. 前瞻顯示 **短期／中期／長期**，不是「3／6／9 個月」固定時間。時間窗精確界線、推理/模型規則未核准前不可自造百分比、期望報酬或買賣結論。
7. **資料/AI 嚴格隔離**：OneBrain 禁止自行連外、爬取、搜尋新聞、呼叫未授權 API，不能直接讀 UI Session/DOM 或回寫資料；所有資料只能由治理核准的資料層 adapter 提供，並經驗證標準化後成為可追溯 Evidence/Digest。缺資料則部分分析／無法判定。
8. **Token 防遺漏**：Required Evidence Manifest、各域引用報告、分批/按需 internal read-only retrieval、負面證據保留、確定性 coverage Gate、快取的資料版本與時效核對；不得 silent truncate。Digest semantic completeness 與 UI compression 分軌 QA。
9. Dark-only（DEC-138）；手機現有 ☰/JS_V4與 390×844 ≥160px 守衛不可退化。💼 W-11 已核准手機序：⑤市場端水位 → OneBrain → 產業集中度 Primary → 持股表；不得復活過時 W-11 排列。

## 二、分批優先順序及授權邊界

| 批次 | 工作 | 允許的安全範圍 | 必要 Gate / 驗收 |
|---|---|---|---|
| D1 | 統一藍圖收斂與 PR 衝突處理 | docs-only；對帳 #1022/#1027/#1029/#1030 與已核准 DEC；舊文字 append-only 註明 superseded | 確認最新主線、獨立 QA、文件一致，未核准 Layout 仍 PROPOSED |
| D2 | 五頁＋每頁 OneBrain 入口視覺線框 | 390/1440 HTML／文字線框、頁責任、空槽與元件位置；不動產品 src | 使用者視覺核准；手機 nav 第五項、a11y與抽屜安全 Gate |
| D3 | 財報 L1 精簡與籌碼/持股分類資料血緣 | read-only producer→canonical→VM→Digest coverage 及重用矩陣；不自建新門檻 | 資料契約/缺值/單位/時效/測試證據；不得觸 Work A 正在改的資料檔 |
| I1 | 已核准布局的小批 New UI2 presentation 實作 | 每批 ≤3 項，專用 Claude branch/PR；沿用正式資料可用性空槽 | 390／1440 實測、Visual Fidelity、獨立 QA、完整 CI；不含 Auth/新來源 |
| I2 | 五頁資料健康度的資料契約與顯示 | 共用單一可追溯 health source，移去「資料」頁，不複製二套真相 | 新導航/資料 Schema/權限 Gate；不能誤判 Source Health＝Market Safety |
| I3 | OneBrain 輸入證據覆蓋稽核 | read-only end-to-end lineage 與 deterministic Coverage Matrix | 無新 API/欄位、無 LLM 上線前可先稽核 |
| I4 | OneBrain scoped analysis/global summary runtime | **未授權實作**，先出架構與安全驗證計畫 | High Gate：Digest schema、內部 evidence store、Source allowlist、無外連能力、Token/成本、分域 cache、正反證、模型/權限測試 |
| I5 | ETF 穿透/新聞訂單/預測定義/實際投資動作 | **未授權實作**，需分別 Source/Domain/Risk Gate | 同步時間/資產曝險分母/事件查證/模型 OOS/正式 Risk Cap/Single Action Authority |

**Stop conditions**：新增/變更 Layout、不可逆操作、Auth、寫入、投資公式、Risk Cap、System Action、外部來源或資料契約、Digest schema、JS_V4、CI/QA 真錯誤、與 Claude/Work A 活躍工作相衝突，均依既有治理停手裁示，不自行繞過。

## 三、Claude Code 施工提示／合併治理

- ChatGPT 準備每批可複製的 Claude prompt，附 Model＋Effort；低風險 presentation/docs → Sonnet / Medium；跨資料源/Digest/安全/風控 → High（必要時 Opus）。
- **每次產出下一批提示前重新獨立查 GitHub Verification Gate**，HANDOFF/PROJECT_STATE 不能替代 main SHA/PR/diff/CI。
- ChatGPT Work 的 docs/資料清理支線與 Claude App 實作必須分工，遇衝突 Claude 優先；不直接推 main、不刪除他人歷史 branch。
- 每批 ≤3 項安全改動，獨立 PR，保留原有功能及完整 Evidence，先測試/獨立 QA/CI 再依治理合併。
- 完成的決策、未完成、差異與下一接手點同步現有 `docs/DECISIONS.md`、`docs/BACKLOG.md`、`docs/HANDOFF.md`，而非創建平行永久狀態檔。
- **自動持續跨時段執行不是本次對話的能力承諾**：本檔確保下一個 Claude 或 ChatGPT session 可接手；任何未完成工作不因本回覆被宣稱已做。

## 四、當前交接位置
- #1030 是設計追加 Draft，**不是已合併正式施工契約**；其設計檔可供檢閱，需避免直接 rebase 未經 QA 的分支而覆蓋 #1029/#1027 的 BACKLOG append。
- 本批文件與 #1030 新增設計互相引用；HTML 草稿仍是獨立 artifact，不代表 Streamlit 實作。
- 客戶目前表示「先依此規劃」，即規劃方向收斂；不能把所有細節（第五頁像素、各 AI 按鈕位置、正式資料與模型權限）自動視為施工批准。
