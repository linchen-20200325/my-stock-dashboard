# Final UI Contract Freeze（vNext Final UI Convergence＋Headless Decision Digest＋OneBrain 的正式契約）

- **狀態**：**客戶拍板版**（客戶 2026-11-02 裁示「Q1：A Q2：A Q3：A 依此正式完成 Final UI Contract Freeze」；逐字見 DEC-122）。Q1～Q3 已裁示，條文化見 **§0.1**；**Stage A 須待 Freeze 獨立驗收（含必要 QA）PASS 後才能開始**（2026-11-02 客戶裁示 Q1～Q3 後更新；有意識的更新，不是漏刪；決策者 客戶（DEC-122 裁示）；原文刪除線保留）。<br>~~**客戶指示 A 生效；Freeze 內容待客戶拍板（含 Q1～Q3）**（2026-11-02）。本檔是送客戶拍板的 Freeze 草案，**不是 Approved 規格**；本檔內「凍結」字樣一律指「Freeze 草案條款」，客戶拍板前不得當已核准規格引用。與 Q1／Q2／Q3 有關的條款另標 **PENDING**（見 §20）。**PENDING 條款在裁示前一律以「較嚴、不放寬風控」的讀法暫行**（寫在各條內）。~~
- **日期**：2026-11-02　**基準**：`origin/main`＝`ce8422d`（cron；最後非 cron 合併＝#994 `4e4aa5e`）；撰寫組 2026-11-02 `git fetch origin main` 實查。⚠️ cron 會推進 main，**一律以當下 `git fetch` 後的 `origin/main` 為準**（DEC-118），不得引用本欄當最新 main。
- 📌 **客戶拍板收斂批基準**：`origin/main`＝`c1e10a6`（PR #995 Freeze 草案合併點；撰寫組 2026-11-02 `git fetch` 實查）；同樣以當下 `git fetch` 為準。
- **決策來源**：客戶 2026-11-02 指示全文＋「A」裁示（**逐字收錄於 `docs/DECISIONS.md` DEC-122**）。本檔把該指示整理成可追溯規格；**客戶原文以 DEC-122 fence 為準**，本檔與原文有出入時以原文為準。
- **配套文件**：舊→新能力對照＝`docs/vnext/FINAL_UI_CAPABILITY_MAP_2026-11-02.md`；取代關係＝`docs/vnext/FINAL_UI_SUPERSEDE_MAP_2026-11-02.md`。
- **位階**：`CLAUDE.md` > `PROCESS.md` > `PROJECT_RULES.md`＋`docs/governance/*` > 最新有效客戶 DEC（本檔的上位＝DEC-122）> 本檔＝正式 vNext 契約（與 Presentation Contract、Decision Digest Contract、ONEBRAIN 文件同層；**衝突處以本檔為準，僅限 supersede map 明列的條目**，其餘仍以原契約為準）。
- **標記**：**〔客戶 §n〕**＝客戶 2026-11-02 指示第 n 節原文要求（無編號段落以「§0／§1／§2／§3／Stage X」標示）；**〔裁示 n〕**＝客戶「A」裁示第 n 點；**FACT**＝撰寫組或兩份調查（invA 衝突盤點、invB 能力盤點，皆 2026-11-02、單組）讀碼／grep 實查；**INFERENCE**＝推論；**AI 總管暫定**＝內部技術自決（`CLAUDE.md` v3 §03-1），客戶可推翻。
- **不授權施工**：本檔**不修改** production UI、資料層、公式、Risk Cap、OneBrain runtime〔裁示 4〕；~~**客戶拍板本 Freeze＋裁示 Q1～Q3 後**，才能開始 Stage A〔裁示 6〕。~~ **客戶已拍板（2026-11-02）；Stage A 須待 Freeze 獨立驗收與必要 QA 通過後才能開始**（客戶原文「不得因本裁示直接跳過 Freeze 驗收」）（2026-11-02 客戶裁示 Q1～Q3 後更新；有意識的更新，不是漏刪；決策者 客戶（DEC-122 裁示）；原文刪除線保留）。登記≠動工授權（`CLAUDE.md` §-1）。
- ⚠️ **揭露（`CLAUDE.md` §-2 規則 6）**：本檔由單一撰寫組依兩份單組調查（invA／invB）撰寫，**未經第二組獨立驗證**。文中「0 命中／不存在／沒有」皆為 grep 結果、**非窮舉**；其中三句承重宣稱——「持股資料無現金／總資產欄」「新四頁無數值型未校準機率」「現行 grounding 無 Risk Cap 一致性檢查」——**只能當待驗事項**，Stage D／G 開工前須另組複驗（BACKLOG `FUI-FREEZE-SECOND-AUDIT`）。

---

## §0 怎麼讀

| 節 | 主題 | 客戶出處 | 狀態 |
|---|---|---|---|
| §1 | 三條 invariant | 〔客戶 §51〕 | ~~待客戶拍板~~ 客戶拍板 |
| §2 | 四頁 Final UI Blueprint（L1／L2／L3） | 〔客戶 §6～§27〕 | ~~待客戶拍板~~ 客戶拍板（各頁開工前仍出逐頁細線框，見 §2.0） |
| §3 | 標的雙模式＋Ad-hoc Session Isolation＋加入觀察 CTA | 〔客戶 §10～§13〕 | ~~待客戶拍板~~ 客戶拍板 |
| §4 | Semantic Chip Contract | 〔客戶 §4〕 | ~~待客戶拍板~~ 客戶拍板 |
| §5 | 四態契約（Missing／Stale／Unavailable／Not evaluated） | 〔客戶 §5〕 | ~~待客戶拍板~~ 客戶拍板 |
| §6 | Single Action Authority | 〔客戶 §20、§23、§35、§38、§51-2〕 | ~~待客戶拍板~~ 客戶拍板；~~**動作詞彙 PENDING Q2**~~ **Q2=A 已裁示** |
| §7 | No Uncalibrated Probability | 〔客戶 §36〕 | ~~待客戶拍板~~ 客戶拍板 |
| §8 | Risk Cap Enforcement | 〔客戶 §19、§38〕 | 規則形狀 ~~待客戶拍板~~ 客戶拍板；~~**曝險分母／數值啟用 PENDING Q1**~~ **Q1=A 已裁示（數值另開 Gate）** |
| §9 | Field-level Freshness／Provenance | 〔客戶 §7、§31〕 | ~~待客戶拍板~~ 客戶拍板 |
| §10 | 單檔 Valuation Contract | 〔客戶 §16、§17〕 | ~~待客戶拍板~~ 客戶拍板 |
| §11 | 大盤 EPS×PE 與單檔估值分離治理 | 〔客戶 §43〕 | ~~待客戶拍板~~ 客戶拍板 |
| §12 | Decision Digest Viewer／唯讀 Rule Registry | 〔客戶 §25～§27〕 | ~~待客戶拍板~~ 客戶拍板 |
| §13 | Presentation Slice ≠ Decision Context | 〔客戶 §11、§32、§51-1／3〕 | ~~待客戶拍板~~ 客戶拍板 |
| §14 | Headless Decision Digest prerequisite | 〔客戶 Stage F §28～§32〕 | ~~待客戶拍板~~ 客戶拍板 |
| §15 | OneBrain 僅解釋／反證 | 〔客戶 §18、§23、Stage G §33～§37〕 | ~~待客戶拍板~~ 客戶拍板；詞彙值域延後 Stage G Gate |
| §16 | Desktop／Mobile L1 Blueprint（文字線框） | 〔客戶 §6、§40、§41〕 | ~~待客戶拍板~~ 客戶拍板；~~**市場頁手機第一屏 PENDING Q3**~~ **Q3=A 已裁示**（版面細節逐頁 Stage 前實測） |
| §17 | Stage A–J 順序、Model×Effort、Stage A 範圍與 DoD | 〔客戶 §0、§2、§3、Stage A、§52〕 | ~~待客戶拍板~~ 客戶拍板 |
| §18 | 每批驗收、Visual Gate 加嚴、輸出規則 | 〔客戶 §1、§41、§44～§49〕 | ~~待客戶拍板~~ 客戶拍板 |
| §19 | 完成定義 | 〔客戶 §50〕 | ~~待客戶拍板~~ 客戶拍板 |
| §20 | Decision Gate：Q1／Q2／Q3 | 〔裁示 5〕 | ~~**PENDING**~~ **已裁示 Q1=A／Q2=A／Q3=A** |
| §21 | 術語統一表 | 〔客戶 §39〕 | AI 總管暫定 |
| **§0.1** | **客戶拍板與永久要求（產品方向、架構鏈、6 條 invariant、Q1～Q3 條文）** | 〔裁示 Q1～Q3，2026-11-02〕 | **客戶拍板；與他節衝突時以本節為準** |
| §22 | 未驗與限制 | — | — |


## §0.1 客戶拍板與永久要求（客戶 2026-11-02 裁示 Q1=A／Q2=A／Q3=A；逐字見 DEC-122；**與本檔他節衝突時以本節為準**）

> 標記：〔裁示 Qn-k〕＝客戶 2026-11-02 Q1～Q3 裁示「補充永久要求」第 n 題第 k 點（依原文順序編號，編號為撰寫組所加）。

### §0.1.1 產品方向（客戶原文，再次確認）

**「簡化 UI，但不簡化 Decision Context。」** 前台只呈現真正需要決策的資訊；完整資料不得因 UI 精簡而裁掉。

### §0.1.2 正式架構鏈（客戶原文）

**Canonical Data → Deterministic Rules／Formulas → Risk Cap／Hard Constraints → System Action State → Decision Digest → OneBrain → UI**

- 與 §14 Pipeline（Canonical Services → Canonical Snapshot → Deterministic Rules → Risk Cap → System Action → Decision Digest）**同向**：本鏈把 OneBrain 與 UI 明確放在 Digest 下游；**UI 是 consumer，不是 data producer**；OneBrain 只讀 Digest（§15.1）。
- Risk Cap／Hard Constraints 在 System Action State **上游**生效：**被封鎖的動作不會成為 System Action；Digest 仍保存原始 rule result 與 Risk Cap 封鎖紀錄（§14 第 4 點）**，讓 Viewer、OneBrain 解釋與稽核看得到「哪條規則想動、被哪個上限擋下」；grounding 只是第二道檢查（§15.4）。

### §0.1.3 永久 invariant（6 條；擴充 §1 三條，§1 原文保留）

1. UI 越簡潔，Decision Context 不能越少。
2. Presentation Slice ≠ Decision Context ≠ AI Output。
3. System Action State 是唯一正式動作權威。
4. OneBrain 只負責 reasoning、summary、explanation、counter-evidence、limitations。
5. OneBrain 不得創造第二套 portfolio action，不得覆寫 deterministic action，不得繞過 Risk Cap。
6. **OneBrain 應讀完整 Decision Digest，而不是只讀 UI 顯示的 Top-N／摘要資料。**

### §0.1.4 Q1=A｜Risk Cap（取代 §8、§20 的裁示前暫行讀法）

1. 本次只凍結 Risk Cap 的**規則形狀**〔裁示 Q1-1〕。
2. 超限時必須「**禁止新增曝險**」〔Q1-2〕；顯示 `🔴 Risk Cap 超限 · 禁止新增曝險`（文字須與 `🔴 取得失敗`／`🔴 來源目前不可用` 不同，§4.1）。
3. **目前曝險或有效 Risk Cap 任一資料不足 → 一律顯示 `⬜ 無法判定`**〔Q1-3〕；有效上限的判定沿用 DEC-044／048／051（§8.1 第 5 點）。
4. **unavailable／not evaluated 不得解讀成 safe，也不得因此允許加碼**〔Q1-4〕：Risk Cap `⬜ 無法判定` 時，加碼類動作 ⛔ 以無上限呈現、⛔ 當作允許（同列標「Risk Cap 無法判定」）。
5. ⛔ **自行發明曝險分母、現金、總資產或任何替代值**〔Q1-5〕（含以持股市值合計充當分母、以 session 輸入的總資金充當正式來源）。
6. Risk Cap 數值正式啟用、曝險分母與現金／總資產來源 → **另開正式 Decision Gate**〔Q1-6〕（BACKLOG `FUI-RC-NUMERIC-GATE`）。
7. 💼 持股頁既有已核准的建議持股區間（卡⑤，DEC-051／PQ-C6-3）**先維持**，不因本次 Freeze 擅自修改〔Q1-7〕；📊 市場頁維持隱藏（DEC-081 Q2-2／`RC-VISIBILITY`），統一與否併入上述 Gate。

### §0.1.5 Q2=A｜持股動作（取代 §6 第 5 點、§20 的裁示前暫行讀法）

1. 第一版**沿用現有 deterministic rule 的正式分支與原名稱**〔Q2-1〕（ETF `action_branch` 七分支、個股 `swap_level` 四級）。
2. UI 可依「**加／留／換／減**」整理呈現，但**不得藉分類創造新的投資語意**〔Q2-2〕：分組只是排版，分支名照原名寫；⛔ 因分組改變任何分支的觸發條件、優先序、比例或解讀。§20 Q2 推薦 A 的分組清單（暫停加碼、高溢價、🟡 留意歸「留」等）是**總管提案**，Stage D 線框仍須客戶確認分組外觀，⛔ 讀成新規則。
3. **只有沒有需要處理的正式動作時**才可顯示「今日無需調整」〔Q2-3〕。
4. **資料不足／未評估不得算成「今日無需調整」**〔Q2-4〕（⚪ 資料不足、`⬜ 尚未評估`、任一燈判不出 → 顯示判不出，沿用 `cruise_or_gap` gate 精神）。
5. 「減碼 1/2」「全出」**目前不得自行映射或產生**〔Q2-5〕（UI、Digest、OneBrain、推播皆同）。
6. 比例 Action 只有在**正式規則、驗證、必要回測／Shadow 與 Decision Gate** 完成後才能啟用〔Q2-6〕（DEC-053 同向；BACKLOG `FUI-PROPORTIONAL-ACTION-RULES`）。

### §0.1.6 Q3=A｜📊 市場頁 Mobile-first（取代 §16.1 手機的裁示前讀法）

1. 市場頁 **Mobile-first**〔Q3-1〕。
2. 手機第一屏**不用滑**就看到：**市場目前狀態**、**Risk Cap**、**是否需要行動**、**主 Update CTA**〔Q3-2〕。
3. 「**今日主要風險**」緊接第一屏之後，**仍屬 L1**，⛔ 被 L2／L3 插隊〔Q3-3〕。
4. **正式 supersede** 與此衝突的 DEC-117 Q1 手機 2＋1、DEC-118 問題 1=A、相關 DEC-120 mobile exception（A10／A11），落點＝`docs/vnext/FINAL_UI_SUPERSEDE_MAP_2026-11-02.md` S10／S11〔Q3-4〕。另見 S11：DEC-120 **A4 手機部分**（三卡均高、手機卡面字數）一併失去前提、Stage B 重量＝**AI 總管內部收緊判定**（客戶可推翻）；A4 桌機部分仍有效。
5. 實際能否放下**未實測**；Stage B 第一步以當時 main 實測（BACKLOG `FUI-MARKET-MOBILE-FIRST-SCREEN`），放不下 → 依 §16.5 先縮字句／合併成一行，仍不行則停在 Decision Gate，⛔ 自行把第一屏必要項移出。**四必要項＋今日結論放不下時，任一項（含今日結論）都不得自行移出，一律交 Decision Gate**（今日結論在第一屏＝DEC-081 Q2-1／DEC-109 仍有效的既有裁示，與 Q3 四必要項同屬客戶要求）。

### §0.1.7 工作模式（客戶原文要點）

Silent Autonomous Cruise；每批 ≤3 個安全項目；只在客戶裁示、人工操作、Model／Effort change、Safe Handoff、完整 Stage 完成時輸出。**執行途中判斷 Model 或 Effort 不足、需要切換 → 必須立即停下來通知客戶（說明建議的新 Model＋Effort 與原因），等客戶修改後才能繼續；不得自行切換後繼續施工。** 開始前重做 GitHub Verification Gate。

---

## §1 三條 invariant（整個施工期間永遠不可破）〔客戶 §51，逐字〕

> 📌 **已由客戶 2026-11-02 擴充為 6 條永久 invariant（§0.1.3）**；下列三條原文保留、全部仍有效（2026-11-02 客戶裁示 Q1～Q3 後更新；有意識的更新，不是漏刪；決策者 客戶（DEC-122 裁示）；原文刪除線保留）。

1. **UI 越簡潔，Decision Context 不能越少。**
2. **Deterministic System 是唯一動作權威；OneBrain 只能推理、解釋與反證。**
3. **Presentation Slice ≠ Decision Context ≠ AI Output。**

與既有條文：同向（DEC-109 十五～十七「Presentation Simplification must never reduce AI Decision Context」「Data View ≠ Decision Context ≠ AI Output」、DEC-054 第 2／4／6 點、DEC-092 Q4、ADR-OB-001）。**FACT**：DEC-109 十五～十七原文仍有效，本節不取代、只重申並升為 Final UI 主線 invariant。

---

## §2 四頁 Final UI Blueprint

### §2.0 共通規則

- **IA 不變**：📊 市場／🎯 標的／💼 持股／👤 我的（DEC-091 §二、DEC-097、`shared/ia_nav4.PAGE4_LABELS`）；⛔ 增減頂層頁（DEC-109 十）。
- **三層**：L1＝結論與狀態（第一眼）；L2＝為什麼、反證、freshness、source（第二眼）；L3＝raw table、完整明細、工程診斷（需要時才展開）〔客戶 §9〕。L1 ≠ 第一屏：L1 可延伸到第一屏下方，但第一屏必須放得下該頁 §16 列的「不用滑」項目〔客戶 §40〕。
- **草稿先行仍適用**（`CLAUDE.md` v3 §03-2 ①）：本節是**結構藍圖**；各頁 Stage（B～E）開工的第一步仍以當時 main 實測並出逐頁細線框（含量測）送客戶拍板，⛔ 拍板前寫該頁 UI code。**AI 總管暫定**：若客戶表示本藍圖即足，可免逐頁細線框。
- **能力守恆**：每一項舊能力的落點見 capability map；新 UI 看起來簡潔 ≠ 功能消失〔客戶 §42〕。
- **每卡四欄**：value、short state、as_of、source（見 §9）〔客戶 §7〕。

### §2.1 📊 市場頁〔客戶 Stage B、§6～§9〕

**頁責任（客戶原文）**：「現在市場環境如何？風險多大？目前可以多積極？」

| 層 | 內容 | 現行資料來源（FACT） | 缺口／狀態 |
|---|---|---|---|
| **L1 市場總結**〔§6〕 | Regime、Risk Cap、System Action State、OneBrain Outlook、是否需行動；⛔ 塞大量說明 | Regime＝市場位階 tile（`page_today.build_verdict_tiles`）；Risk Cap＝`allocation_service.get_allocation`（現行卡面 `_market_blocks.WATER_VALUE`「⬜ 尚未核准／無法判定」）；是否需行動＝`blocks.render_alerts_block`（⚡） | **System Action State（市場層）無正式來源**（invB M03，critical；grep `system_action` 0 命中，非窮舉）→ 只能 `⬜ 尚未提供`；~~**Risk Cap 數值 PENDING Q1**~~ **Risk Cap 數值：Q1=A 已裁示——只凍結規則形狀，數值另開 Gate（§0.1.4）**（2026-11-02 Freeze 獨立驗收修正；有意識的更新，不是漏刪；決策者 客戶（DEC-122 裁示）＋AI 總管〔驗收修正〕；原文刪除線保留）；OneBrain Outlook＝`🤖 ⬜ 尚未提供`（Stage G 前） |
| L1（續） | **今日主要風險**（DEC-092 Q3、DEC-117 Q1／Q6 仍有效；新 L1 清單用「包含」，INFERENCE：非封閉清單） | `blocks.render_chart_d`、主要風險 tile | 手機位置見 §16.1 |
| **L1 核心指標卡**〔§7〕 | 台股、VIX、US 10Y、利差、DXY、PMI／景氣、其他已正式存在且重要的指標；每卡 value／short state／as_of／source | 16 燈（`today.build_indicator_tiles`）、`INTL_GROUPS`、L3 原始表（`page_market` 的 `X7_FIELDS`） | 現行**無 L1 指標卡**；`get_macro_state` 無逐指標 as_of（Digest 契約 §4 `AS_OF_NOT_IN_CONTRACT`）→ 缺者 `⬜ 資料日未提供`，⛔ 共用全域更新時間 |
| **L1 Charts**〔§8〕 | 台股主圖（index＋**正式**趨勢線／均線＋Regime annotation）；Volatility（VIX＋正式門檻帶）；International small multiples（DJI、NASDAQ、SOX、DXY、Yield）；Macro mini chart／sparkline／multi-series 取代大段文字 | 圖 A（加權＋MA 最新值水平參考線）、圖 B（`INTL_GROUPS`） | **正式趨勢線不存在**（DEC-092 Q2：台股趨勢＝`⬜ 尚未定義`，均線只是參考線）→ 維持；**Regime 歷史序列不存在**（grep `regime_history` 0 命中）→ 只能標當下位階或 ⬜；**VIX 圖不存在**→新增，門檻帶只能引既有 SSOT（`VIX_MEDIUM_RISK_THRESHOLD`、`shared/macro_buckets` VIX red），⛔ 新門檻；Macro mini chart 不存在→新增（純呈現） |
| **L2**〔§9〕 | 為什麼、counter evidence、data freshness、source | 位階「為什麼」、五桶、X3、資料來源與完整度 | counter evidence 段不存在（新增；內容只能取 Digest／規則輸出，⛔ AI 自寫） |
| **L3**〔§9〕 | raw table、full macro detail、engineering diagnostics | 16 燈明細、台股／國際／總經／籌碼原始表、X9 | ⛔ 把舊市場頁數千字搬回 L1 |
| L2 Research | 圖 C 大盤 EPS×PE＝**Research**（見 §11） | `render_chart_c` 研究框架空槽 | 維持 |

### §2.2 🎯 標的頁〔客戶 Stage C、§10～§18〕

**頁責任（客戶原文）**：「A. 系統替我找；B. 我指定一檔研究。必須明確切開。」雙模式、Session 隔離、CTA 見 §3。

| 模式 | 層 | 內容 | 現行（FACT） | 缺口 |
|---|---|---|---|---|
| 市場精選 | L1 | 產業機會 Top N（bar＋score/state＋freshness）；候選 Top N（presentation only，完整 universe 不丟） | 產業 Top 5 橫條（DEC-121 Q1=A）、候選 Top 10＋查看全部＋CSV（DEC-121 Q2=B；`DEFAULT_TOP_N=50` 不變） | 存活池（排名上限外）逐檔可見性待查（invB T04） |
| 市場精選 | L2／L3 | 選股條件（收合＋一行摘要）、6 欄完整表、產業趨勢維度（`⬜ 尚未建置`）、全台股跨季趨勢 | 部分 | 產業趨勢定義未核准（DEC-092 Q5） |
| 即時查一檔 | L1 | 搜尋（**代碼／名稱**）→ 研究 workspace：Header → **6 維 Snapshot** → Primary Price Chart | 只收代碼；判型 chip＋3 摘要 tile；K 線為灰色 placeholder | **名稱搜尋＝新能力**（`stock_names.get_stock_name` 只 code→name）；6 維只有 3 維；主圖未接 |
| 即時查一檔 | L2 | Fundamental → Valuation（§10）→ Institution／Chip → Industry → Risk → OneBrain Research Explanation（§15） | 財報體檢、357、近 20 日籌碼＋爆量 | Industry 區、個股 Risk（`⬜ 個股風險指標尚未提供`）、OneBrain 皆缺 |
| 即時查一檔 | L3 | 完整分析明細、raw | 「▸ 完整分析」 | — |

**6 維 Snapshot**〔§15〕：基本面、估值、籌碼、趨勢、產業、市場環境；每維 state＋short text，⛔ 大段 prose。**FACT**：「趨勢」「產業」無正式定義（DEC-092 Q2／Q5）→ 必為 `⬜ 尚未定義`；「市場環境」引市場位階（同一份 market context，§13、Stage H）。

### §2.3 💼 持股頁〔客戶 Stage D、§19～§23〕（「Phase 6 最重要頁」）

| 層 | 內容 | 現行（FACT；`page_hold` 仍為 IA v2 版，Phase 6 未開工） | 缺口 |
|---|---|---|---|
| **L1 第一屏** | Portfolio Risk Cap、目前曝險、System Action State、今日需處理 | 無首屏 Risk Cap；`build_position_cap_card` 在 ⑤ 依 DEC-051／PQ-C6-3（客戶 2026-10-16 核准）外露市場端建議持股區間 `range_text`（已核准顯示，**非違規**）；① `build_action_card` 只列汰弱／加碼計數或巡航句 | **曝險無資料**（`gsheet_portfolio._HEADERS`＝name／ticker／lots／avg_price／updated_at，無現金／總資產；單組 grep）~~→ **PENDING Q1**；動作詞彙 **PENDING Q2**~~ → **Q1=A 已裁示（§0.1.4）**；動作詞彙 **Q2=A 已裁示（§0.1.5）**（2026-11-02 Freeze 獨立驗收修正；有意識的更新，不是漏刪；決策者 客戶（DEC-122 裁示）＋AI 總管〔驗收修正〕；原文刪除線保留） |
| L1 | Portfolio Overview charts：performance、benchmark、sector exposure、strategy distribution、concentration（能圖就不要長表） | 0 張圖 | performance／benchmark 無組合歷史淨值（資料缺口，INFERENCE 非窮舉）→ placeholder；sector exposure／concentration 有既有算法（`compute/risk/concentration.py`、產業集中度）；strategy distribution 在 HI-5 前全為 `⬜ 未分類` |
| **L1 Holdings Table** | 代碼、名稱、持股比例、成本、現價、報酬、策略、System Action | 無逐檔表（只有燈牆） | 「持股比例」：外幣列依 DEC-101(1) ⛔ 與 TWD 加總 → 排除並揭露；「策略」：AB-4w（HI-5）前 `⬜ 未分類` |
| L2 | fundamental、risk、chip、evidence、rule IDs；兩套刻度揭露（DEC-017 葉1 ② 仍有效，Stage D 線框待拍板 `P1R-P6-WF-TWO-SCALES`）；80/20、停利、換股、VaR／壓測／配息 | ②～⑥ | 再平衡、葡萄串為 `UnwiredSpec` |
| L2 | **OneBrain 持股摘要**（§15）：只解釋 system actions、共同風險、portfolio context、反證；System Action＝禁止加碼時 AI 文字也必須遵守；automated grounding check | ⑦ 直呼 `app_ai_service.gemini_call`（輸入＝station digest，非 Decision Digest、無 grounding） | **現行 ⑦ 列為違反本契約，待 Stage G 處理**（BACKLOG `FUI-HOLD-GEMINI-DIRECT`）；Stage G 前不擴充、不新增其他 AI 出口 |

### §2.4 👤 我的／Audit〔客戶 Stage E、§24～§27〕

| 區 | 內容 | 現行（FACT） | 缺口 |
|---|---|---|---|
| L1 一般設定〔§24〕 | Google、Sheet、Portfolio、Watchlist、Strategy、Notifications、Display preference（依既有正式能力） | `page_me` ①②③（Google／Sheet／組合與觀察清單選擇器；選定只活在 session） | Strategy／Notifications／Display 無；CRUD 屬 DEC-083 Q2 P2（不變） |
| L1 Audit 入口〔§25〕 | Decision Digest、Rule Registry、Data Freshness、System Information | 無 | 全部新增；Viewer 依賴 Stage F（§12、§14） |
| L2／L3 | Digest raw structured snapshot、Registry 明細、資料健康牆、工程診斷（唯讀部分） | `page_why` 葉在預設模式到不了；側欄 `render_sidebar_data_health` | — |

---

## §3 標的雙模式＋Ad-hoc Session Isolation＋加入觀察 CTA〔客戶 §10～§13〕

### §3.1 雙模式

1. 頁頂兩個模式：**[ 市場精選 ] [ 即時查一檔 ]**；⛔ 兩者同時完整展開〔§10〕。
2. 查詢後自動把市場精選收合／隱藏／退到另一個 tab〔§12〕。**AI 總管暫定**：搜尋框在兩模式都外露於模式切換下方（手機第一屏需要，§16.2）；送出查詢 → 切到「即時查一檔」並收合精選。切換元件外觀沿用 DEC-115 D8=B 膠囊式（floor 1.56 未驗則退回 A）。
3. **「市場精選」內從候選選一檔**（DEC-107 2A「選一檔＋🔍 查看此檔」仍有效）＝進入同一個研究 workspace 的入口；結果與手動查詢共用 workspace，Session 規則相同（§3.2）。
4. 模式切換是**頁內元件**，⛔ 新 IA 層、⛔ 回到 NAV-1 葉選擇器（`NAV4_TARGET_LEAF_KEY`；DEC-099 第 1、2 點仍有效）。

### §3.2 Ad-hoc Session Isolation〔§13〕

查一檔＝**session-only**。⛔ 自動：加入持股、加入觀察、加入 candidate pool、改 strategy、寫 Sheet、改 Risk Cap、改 ranking。
- 現行同向（FACT）：DEC-107 補充邊界「不寫 Sheet」、`_target_blocks` 0 寫入、session 世代 memo（`UIT-RESULT-MEMO-NOT-REFRESHED`）。
- **加嚴**：Stage C 須為上列 7 項各補一條守衛測試（新 UI 寫入面黑名單＋排名／候選池／Risk Cap 輸入不受 ad-hoc 查詢影響），BACKLOG `FUI-ADHOC-ISOLATION-GUARDS`。

### §3.3 「加入觀察」CTA

- 客戶規則：只有顯式 CTA「加入觀察」才能寫入**既有正式** watchlist 流程；流程尚未正式存在 → **CTA disabled／not available；⛔ 臨時造寫入邏輯**〔§13〕。
- **FACT**：舊 UI 寫入流程存在（`app.py` 選股網 → `src/services/watchlist_service.add_picks_to_watchlist` → `gsheet_portfolio.add_to_stock_watchlist`）；新 UI 未接（`_target_blocks.UNCOVERED_ITEMS`「會寫入您的 Google Sheet，新版尚未接上」）；新 UI 寫入面屬 DEC-083 Q2 P2／HI-5 未核准。
- **判定（INFERENCE：依 DEC-083 Q2「觀察清單 CRUD 留 P2」的較嚴讀法；客戶可推翻）**：對**新 UI** 而言正式寫入流程**尚未存在** → CTA 以 `加入觀察（尚未提供）` disabled 呈現，L2 一句說明＋指向舊版仍有此功能的事實（不放 legacy 連結，DEC-097）。啟用＝另開 ME-P2／HI-5 Gate（沿用 DEC-021 逐筆、預覽、二次確認、同本重複阻擋）。

---

## §4 Semantic Chip Contract〔客戶 §4〕

### §4.1 四種語意 tone（客戶原文分類）

| tone | 用途（客戶原文） | 符號／色（AI 總管暫定，Stage A 落常數） | ⛔ |
|---|---|---|---|
| **Positive／Allowed** | 真正正向的 deterministic state | ✅＋綠系 | 拿來表示「資料可讀」以外的非確定性正向（AI 看多、趨勢偏多等） |
| **Warning** | 需注意 | ⚠＋琥珀 | 塗紅 |
| **Danger** | deterministic violation／Risk Cap | 🔴＋紅＋**違規專用文字**（例 `🔴 Risk Cap 超限 · 禁止新增曝險`） | 用於非確定性判斷；只靠顏色區分 |
| **Neutral／Info** | 類型、產業、計數、估值口徑、資料來源 | 無狀態符號或 ℹ；細外框 | 用護欄族或警告族承載 |

- **紅色兩義必須文字不同**：系統真錯誤（`🔴 取得失敗`／§5 Unavailable）與確定性違規（`🔴 Risk Cap 超限`）⛔ 只靠顏色區分（`PROJECT_RULES.md` §13 D12「顏色不是唯一載體」）。
- **未載入＝灰**、**系統真出錯＝紅**（`CLAUDE.md` §1.A 第 4 點）**不變**；stale 用琥珀（Presentation §6 R8）**不變**。

### §4.2 `guard_chip` 收窄

- `src/ui_v2/compact.guard_chip` **只限客戶護欄逐字句**（例 `_market_blocks.CHART_A_MA_DISCLAIMER`、`CHART_C_TAG`、`CHART_D_WORSENING`——FACT：市場頁 3 處用法正確）。
- ⛔ 以 `guard_chip` 表示：半導體（產業）、3 項（計數）、PE（估值口徑）、股票（判型）〔客戶 §4 原句〕。
- **FACT**：`src/ui/views/_target_blocks.py` 以 `guard_chip` 承載判型 chip（`kind_chip_text`）、計數 chip（`HIT_CHIP_FMT`／`MISS_CHIP_FMT`／`PARTIAL_NOT_EVALUATED_FMT`）、估值口徑 chip（`PE_BASIS_CHIP`）＝**違反本契約**；BACKLOG `P5-CHIP-KIND-NAMES` 的「或維持」選項**被本契約否決**。Stage A 新增 Neutral／Info 自由文字 kind（**只加不改**，同步 `tests/ui_v2/test_compact.py` 封閉集對帳）後，Stage C 遷移上列用法。

### §4.3 與 `compact.META_KINDS`／DEC-115 D3 的關係

- **兩軸正交**（INFERENCE，本契約採用）：本節四 tone＝**語意軸**；DEC-115 D3 三族（資訊／狀態／護欄）＝**外觀 family 軸**。對映：Neutral/Info→資訊族；Warning→狀態族 ⚠（或護欄族中的 `data_quality`／`estimated`／`proxy`／`imputed`）；Positive→狀態族 ✅（僅限確定性正向）；**Danger＝新增**。
- DEC-115 D3 末句「不得新增會與既有 Missing／限制語意混淆的第四套視覺語言」→ **部分取代**：Danger／Positive tone 由客戶 §4 明示新增；其「不得與 Missing／限制語意混淆」的**目的仍有效**（Danger ⛔ 用 ⬜、⛔ 與取得失敗同字）。
- `META_KINDS` 封閉集（20 kinds，以 Presentation Contract §6 表對帳）**不刪**；新 kind 只加不改，並在 §6 表登記。
- `readable`「✅ 可讀」是**資料狀態**，不是 Positive 投資狀態；Stage A 須讓兩者文字可區分。

---

## §5 四態契約（Missing／Stale／Unavailable／Not evaluated）〔客戶 §5〕

### §5.1 定義與 L1 字樣（全站統一；四者不得混用）

| 語意態 | 定義（客戶原文） | L1 外露字樣 | 色 |
|---|---|---|---|
| **Missing** | 資料未取得／資料未備 | `⬜ 資料未取得`（應有輸入但這次沒拿到）／`⬜ 資料未備`（來源尚未發布、歷史長度不足、不適用）〔字樣＝客戶原文〕 | 灰 |
| **Stale** | 有資料，但已超過 freshness tolerance | 沿用 `⚠ 過期 N 天`／`⚠ 可能已過期`（既有 `stale` chip） | 琥珀 |
| **Unavailable** | 來源目前不可用 | `🔴 來源目前不可用`＋一句原因（AI 總管暫定字樣；L2 保留既有 `🔴 取得失敗` 子原因） | 紅（系統真錯誤） |
| **Not evaluated** | 尚未評估 | `⬜ 尚未評估`；子原因字樣沿用 `⬜ 尚未定義`、`⬜ 尚未核准／無法判定`、`⬜ 尚未載入`，以及**客戶逐字字樣 `⬜ 未評估／資料不足`（DEC-074、DEC-075；保留原字樣，⛔ 改寫）** | 灰 |

**永遠**〔客戶原文〕：missing ≠ 0；missing ≠ HOLD；missing ≠ neutral；unavailable ≠ safe；not evaluated ≠ safe。（同向既有：DEC-026、DEC-031、DEC-040、DEC-054 第 3 點、DEC-101(2)、Presentation §8、`PROJECT_RULES.md` §19.8、OneBrain G2。）

- **⬜ 共用時以文字區分**：Missing 與 Not evaluated 同用 ⬜，⛔ 只靠符號判讀；L1 字樣必須含「資料未取得／資料未備」或「尚未評估（／尚未定義／尚未核准／尚未載入）」其中之一。
- **FACT**：`資料未取得`／`資料未備` 作為狀態 chip 字樣在 `shared`、`src/ui_v2`、`src/ui/views` **無**；`src/` 他處（舊 UI、`allocation_service`、`financial_health_engine`）有散文用法，非狀態 chip（grep，非窮舉）。

### §5.2 與 `shared/ui_state.UI_STATE_META` 十態的對映（十態＝L0 細分類，**保留、不改符號**；四態＝語意層）

| UI_STATE_META（L0） | 既有字樣 | 四態語意層 | L1 外露 | 備註 |
|---|---|---|---|---|
| idle | `⬜ 尚未載入` | Not evaluated（子原因：尚未載入） | `⬜ 尚未載入` 維持 | `CLAUDE.md` §1.A 第 4 點：未點擊＝灰色說明（AI 總管暫定：idle 歸 Not evaluated） |
| loading | `⏳ 載入中` | 四態之外（過渡態） | 維持 | — |
| failed | `🔴 取得失敗` | **Unavailable** | `🔴 來源目前不可用` | L2 保留 `🔴 取得失敗`＋原因 |
| empty | `▨ 無資料` | Missing（資料未備） | `⬜ 資料未備` | `▨` 留 L2 子原因 |
| missing_retryable | `⟳ 缺漏 · 可重跑` | Missing（資料未取得） | `⬜ 資料未取得` | 「可重跑」留 L2（客戶 2026-09-23 D-3(a) 符號保留在 L0／L2） |
| not_applicable | `⊘ 不適用 · 重跑無效` | Missing（資料未備） | `⬜ 資料未備` | 「重跑無效」留 L2 |
| partial | `◧ N／M 計入` | 部分 Missing（覆蓋） | `coverage` chip＋缺項各自標 Missing | ⛔ 寫成 confidence |
| degraded | `🟠 門檻已失準` | 四態之外（計算品質旗標） | 維持 | ⛔ 拿來當 Stale |
| unwired | `⛔ 未接線` | 四態之外：**功能尚未提供** | 維持 | 見 §5.3 |
| live | `🟢 運作中` | 正常（非四態） | 維持 | — |
| metadata `stale` | `⚠ 過期 N 天` | Stale | 維持 | — |
| metadata `asof_missing` | `⬜ 資料日未提供` | Missing（欄位級：資料日） | 維持 | §9 |
| metadata `not_defined`／`not_approved` | `⬜ 尚未定義`／`⬜ 尚未核准／無法判定` | Not evaluated | 維持 | — |
| Digest `DataStatus` ok／stale／missing／proxy／failed／invalid | — | ok／Stale／Missing／ok＋proxy 旗標／Unavailable／Missing（子原因：驗證未過，INFERENCE） | — | `MissingReason.NOT_DEFINED`→Not evaluated；`NOT_WIRED`→功能尚未提供 |

- **DEC-110 R8「十態不另造」繼續有效**：本契約不新增第 11 態；四態是語意分類層。
- 客戶 2026-09-23 D-3(a) 的 ⟳／⊘ L1 外露字樣 → **部分取代**（只限 L1 外露字樣；L0 與 L2 保留）。⚠️ 若客戶希望 L1 仍見「⟳ 可重跑」，屬客戶可推翻的呈現細節。

### §5.3 `unavailable` 舊義改名處置

- **FACT**：Presentation Contract §6 表 `unavailable` kind＝**委派到 `⛔ 未接線`**（功能沒做）；與客戶新 Unavailable（來源壞了）語意不同。
- **處置（凍結）**：自本契約起，文件中「Unavailable」一律指**來源目前不可用**；舊義改稱「**功能尚未提供（未接線）**」，符號 `⛔ 未接線` 不變。程式識別名 `compact` 的 `unavailable` kind 於 **Stage A** 改名（建議 `unwired`；與 §6 表、`tests/ui_v2/test_compact.py::_contract_kinds` 同一 PR 同步，因該測試以 §6 表列對帳 `META_KINDS` 20 項）；改名前視為**舊義別名**，⛔ 用來表示來源不可用。BACKLOG `FUI-UNAVAILABLE-KIND-RENAME`。
- 📌 **2026-11-02 New UI2 Batch 1 註記（append-only；AI 總管暫定，待覆核）**：New UI2 契約（`shared/ui2_contract`）實作「功能尚未提供」用字樣 `⬜ 尚未提供`（第 6 態 `NOT_PROVIDED`，四態之外），**不是**本節舊義別名 `⛔ 未接線`；兩者是否合併／是否保留第 6 態待第二組覆核（BACKLOG `NUI2-STATE-NOT-PROVIDED-AUDIT`）。

---

## §6 Single Action Authority〔客戶 §20、§23、§35、§38、§51-2〕

1. **唯一動作權威＝Deterministic System**。System Action 只能來自正式 deterministic action state；OneBrain、UI、文案 ⛔ 產生 independent action〔§35〕。
2. **今日需處理**只呈現真正 Action；**沒有動作時顯示「今日無需調整」**〔§20 原文〕；⛔ 硬填 action。「沒事」與「判不出」必須分開（既有 `cruise_or_gap` gate 同向）：判不出＝`⬜ 尚未評估`，⛔ 寫成「今日無需調整」。
3. **AI 文字必須遵守 System Action**：System Action＝禁止加碼時，任何頁、推播、OneBrain 文字 ⛔ 出現 unrestricted Add〔§23、§38〕；由 automated grounding check 強制（§15.4）。
4. **FACT（現行正式動作來源）**：ETF 軌 `src/compute/etf/dividend_station.action_branch` 七分支（汰弱 `cut`／強制停利 `take_profit_force`（>+3σ）／分批停利 `take_profit_partial`（>+2σ）／暫停加碼 `pause_add`／加碼 `add`／高溢價 `premium`／巡航 `cruise`）；個股軌 `StockAssessment.swap_level`（🔴換出／🟡留意／🟢續抱／⚪資料不足）；Digest 允許名單 `shared/decision_digest_rules.RULE_ID_ALLOWLIST` 只收 `risk_cap`＋前五個分支碼（`action_branch.v1`，DEC-094：內部命名、非客戶核准版本）。**「減碼 1/2」「全出」不存在任何正式規則**；分批停利沒有定義為 1/2。
5. ~~**動作詞彙 → PENDING Q2**（§20）。~~ **Q2=A 已裁示：見 §0.1.5（正式條文）**（2026-11-02 客戶裁示 Q1～Q3 後更新；有意識的更新，不是漏刪；決策者 客戶（DEC-122 裁示）；原文刪除線保留）。舊文：裁示前暫行（較嚴）：L1 只用既有分支原名；「減碼 1/2」「全出」⛔ 產生、⛔ 顯示。DEC-053（正式加減碼比例須經資料驗證→規則設計→回測／Shadow→客戶裁示）、DEC-092 Q4（不新增續抱／注意／減碼／換股四態）、DEC-054 七種 Action 名稱 **繼續有效**，⛔ 讀成已被 §20 取代。
6. **System Action State 需要一個 deterministic 組裝層**（Risk Cap → System Action → Digest，§14）；它只**彙整**既有分支與 Risk Cap 封鎖結果，⛔ 新規則。現況無此層（invB H02／M03 critical）。

---

## §7 No Uncalibrated Probability〔客戶 §36〕

1. 任何 UI、Digest、OneBrain output ⛔ 出現**未經校準的預測機率／勝率／confidence 數值**；grounding 必須擋偽 probability〔§36〕。同向既有：Digest 契約 §4「不得創造新的 confidence 語意」、OneBrain G8。
2. **現況（FACT，grep `機率|勝率|probab|logit`，只掃字串、非窮舉）**：新四頁預設模式**未見**數值型預測機率。
   - `page_market` 市場位階「為什麼」面板有標籤 **「信心度」**＝`confidence_pct`（說明寫「紅綠燈資料來源的齊備程度」）＝**資料齊備度，不是機率**；標籤易誤讀 → **改名列 Stage B 待辦**（建議「資料齊備度」；BACKLOG `FUI-CONFIDENCE-LABEL-RENAME`）。不改數字、不改語意。
   - `page_hold.build_confidence_card` 的「**訊號可信度**」（`aggregate_judged()`／`tally_states()` 的 N／M 判得出比例，分母動態）同屬可判定覆蓋度、不是機率；同一 BACKLOG 列處理（Stage D），不改數字與語意。
   - `page_hold` VaR 句「機率約 95%」＝VaR 信賴水準定義，非預測（INFERENCE：合規）。
   - `src/data/macro/macro_core.recession_probability`（10Y-3M logit；係數 `shared/signal_thresholds.RECESSION_LOGIT_COEF_*`，docstring「對齊 Fund 端」，**無校準證據**）：0 production caller；只在舊 UI 教學（`tab_edu`／`shared/edu_tokens`）。**⛔ 上新 UI、⛔ 進 Digest、⛔ 給 OneBrain 引用**，除非另經校準＋客戶 Gate（BACKLOG `FUI-RECESSION-LOGIT-GUARD`）。
   - 舊 UI「機率高」類定性句：凍結（DEC-019），不改；Stage J 盤點時不得搬到新 UI。

---

## §8 Risk Cap Enforcement〔客戶 §19、§38〕~~（規則形狀凍結；數值 **PENDING Q1**）~~ （規則形狀凍結；**數值：Q1=A 已裁示，另開 Gate**）

> 📌 **Q1=A 已裁示（2026-11-02）：正式條文見 §0.1.4**；本節 §8.1 形狀與 §8.3「裁示前」維持現狀的讀法即為裁示結果（持股頁區間維持、市場頁隱藏、數值另開 Gate）；與 §0.1.4 衝突處以 §0.1.4 為準（2026-11-02 客戶裁示 Q1～Q3 後更新；有意識的更新，不是漏刪；決策者 客戶（DEC-122 裁示）；原文刪除線保留）。

### §8.1 規則形狀（凍結，客戶原文）

1. 若 **Exposure > Cap** → 立即顯示 **`🔴 Risk Cap 超限 · 禁止新增曝險`**，**而不是**「AI 看多 加碼」〔§19〕。
2. 同一 Snapshot 下 Risk Cap blocked → 市場、標的、持股、OneBrain **任何地方不得出現 unrestricted Add**〔§38〕。
3. 🔴 Danger 文字必須與 `🔴 取得失敗`／`🔴 來源目前不可用` **文字不同**（§4.1）。
4. **目前曝險或有效上限任一不可得 → `⬜ Risk Cap 無法判定`**；依 not evaluated ≠ safe，此時加碼類動作 ⛔ 以「無上限」呈現，必須同列標「Risk Cap 無法判定」~~（**PENDING Q1 的推薦暫行讀法**）~~ （**Q1=A 已裁示：正式條文 §0.1.4 第 3、4 點**）（2026-11-02 Freeze 獨立驗收修正；有意識的更新，不是漏刪；決策者 客戶（DEC-122 裁示）＋AI 總管〔驗收修正〕；原文刪除線保留）。
5. 「有效上限」的判定沿用既有規則：**DEC-044**（Risk Cap 既有細項維持現行）、**DEC-048**（Required Core＝VIX、PMI 當期、PMI 前月、外資期貨＋MA5；Core 缺→上限無效）、**DEC-051**（卡面揭露 Optional 資料完整性、中性措辭）**全部仍有效**，本契約不改。

### §8.2 現況（FACT）

- Risk Cap 規則存在：`macro_state_locker.calculate_system_state` → `risk_cap_apply`（寫 `risk_cap_state.json`）→ `shared/risk_cap_policy`（`risk_cap.v2`）→ `allocation_service.get_allocation`（`build_allocation_decision` 取最低）→ `src/ui/views/risk_cap_gate.has_system_risk_cap`。產出＝**建議總持股上限**，**不產生** System Action，**沒有**「實際曝險 > 上限 → 禁止新增」規則（grep 0 相關命中，非窮舉）。
- **顯示未核准**：DEC-081 Q2-2「風險上限／獨立顯示待 C2b＋RC-VISIBILITY Gate」逐字仍有效；BACKLOG `RC-VISIBILITY` blocked-on-customer；市場頁 `WATER_VALUE`＝`⬜ 尚未核准／無法判定`。
- **跨頁呈現差異（FACT，讀碼，未實機）**：市場頁水位卡隱藏數字（DEC-081 Q2-2／`RC-VISIBILITY`）；持股頁 ⑤ `build_position_cap_card` 有有效上限時卡面外露建議持股區間 `range_text`——這是 **DEC-051／PQ-C6-3（客戶 2026-10-16 核准線框）已核准的顯示，不是違規**。兩頁差異是否統一（統一成哪一邊）＝**併入 Q1 請客戶一併決定**；裁示前**維持現狀**（持股頁保留區間、市場頁維持隱藏）（BACKLOG `FUI-RISKCAP-CROSSPAGE`）。
- **曝險分母不存在**：`build_position_cap_card` 明寫 Risk Cap 分母是「整體資產」；持股 Sheet 表頭無現金／總資產（單組 grep，**待驗**）→「目前曝險 %」**算不出來**。

### §8.3 ~~PENDING Q1（見 §20）~~ Q1=A 已裁示（見 §0.1.4）

曝險分母、數值啟用時點、是否新增現金／總資產輸入、兩頁區間顯示是否統一——**裁示前**：Freeze 只定 §8.1 形狀；「Exposure vs Cap」閘門狀態一律 `⬜ 無法判定`；**既有顯示維持現狀**：市場頁 `⬜ 尚未核准／無法判定` 維持隱藏、持股頁 ⑤ 依 DEC-051／PQ-C6-3 已核准外露的建議持股區間維持；⛔ **新增**任何 Risk Cap 百分比顯示面（含把市場頁解除隱藏）；⛔ 修改 Risk Cap 公式／門檻（〔客戶 §46〕Risk Cap modification → Decision Gate）。

### §8.4 與既有條文

- `ONE_AI_BRAIN_BOUNDARY` §3「⛔ 把 Risk Cap 連到具體行動」→ **部分取代**：只限「超限 → 禁止新增曝險／不得出現 unrestricted Add」這一條（客戶明示）；其他「Risk Cap → 具體行動」（例：自動減碼比例）仍屬新規則（HI-1／HI-4），⛔。
- D13（缺有效 Cap → 建議持股「無法判定」）、DEC-040～052（含 **DEC-044／048／051**）、DEC-070、PQ-C6-3（DR-2026-10-16-4）**繼續有效**。

---

## §9 Field-level Freshness／Provenance〔客戶 §7、§31〕

1. **每張卡**（含市場指標卡、標的 6 維、持股欄）帶 **value／state／as_of／source** 四欄〔§7〕。
2. ⛔ **共用假的全域更新時間**〔§7〕；⛔ 以按鈕時間冒充資料日（Presentation §6 第 6 點，仍有效）。頁首「按更新時間」只能標為「按更新時間」，⛔ 當資料日。
3. 欄位缺 as_of → `⬜ 資料日未提供`（`asof_missing`），⛔ 補推估日期；缺 source → 不顯示來源 chip 並在 L2 說明，⛔ 寫服務名冒充資料源（Digest 契約 §4：`Provenance.source` 現為服務名，A1 缺口）。
4. **FACT 缺口**：`get_macro_state` 無逐指標 as_of（`AS_OF_NOT_IN_CONTRACT`）；候選表估值資料日 `⬜ 未提供`（`UIT-PE-ASOF-MISSING`）。補齊屬 Stage F（Digest A1／A2）與各頁 Stage；**補不到就誠實 ⬜**。
5. 取值只能讀既有 SSOT（`shared/staleness`、`shared/price_asof_label`、各 fetcher `source`／`fetched_at`；`CLAUDE.md` §2.2）。同向既有：DEC-028、029、040、080（provenance／freshness 兩軸）、DEC-101 XV-ASOF、DEC-102、`PROJECT_RULES.md` §13 D8。

---

## §10 單檔 Valuation Contract〔客戶 §16、§17〕

| 類 | 客戶規則 | 現況（FACT） | 凍結處置 |
|---|---|---|---|
| **Current** | PE、PB、existing valuation metrics | TWSE 當日 PE（`valuation_service.get_pe_name_maps`）；357 殖利率估值（`valuation_service.get_stock_dividends`）；**PB 新 UI 無**（舊 UI 有） | 外露 Current；PB 補接屬 Stage C（既有資料，⛔ 新公式） |
| **Historical** | 歷史估值區間圖 | 舊 UI `section_357_valuation`（殖利率／PE／PB 三河流圖）；新 UI 無（invB T16，**critical**、舊獨有） | Stage C 承接「歷史區間」純歷史呈現；若帶 357 低／中／高倍數帶＝HI-3 未核准 → 只畫歷史實際值、⛔ 帶情境線 |
| **Forward** | 只有資料真的存在才能使用 | **Forward EPS 資料源不存在**（grep `forward_?eps|NTM|FY20xxE|consensus|forwardPE` 於 `src`／`shared`／`scripts`／`app.py` 0 命中；`VN1-MT-VALUATION` 同記） | **不可呈現**；槽位 `⬜ 資料未備（無 Forward EPS 資料源）`；接資料源＝新資料源 Decision Gate（DEC-009／DEC-092 Q5；BACKLOG `FUI-FORWARD-EPS-SOURCE-GATE`） |
| **Scenario** | 只有 approved deterministic assumptions 才能呈現 | 357 PE 帶屬 HI-3（未核准） | **不可呈現**；`⬜ 尚未核准` |

**必須外露（L2）**〔§16〕：EPS basis、EPS source、EPS as_of、PE multiple、PE source／policy、calculation。現況只有 TTM／當日 PE 一種 basis（INFERENCE）。候選表 PE（當日本益比）與 357（殖利率口徑）**兩口徑不能互相驗證**（DEC-107 4A 補充，仍有效）。

**EPS 時間軸標示規則**〔§17〕（凍結；任何 `Fair Value = EPS × PE` 呈現都適用，含日後 Forward 啟用時）：
1. EPS 必須標時間軸代碼之一：`FY2026E`／`FY2027E`（會計年度預估）、`NTM`（未來 12 個月）、`Forward 1Y`、`TTM`（近四季實績；現行唯一可得）。
2. ⛔ 只寫「EPS 45 × PE 24」而不標時間軸〔客戶原文例〕。
3. 同一算式的 EPS basis 與 PE basis 必須同一時間軸（例：NTM EPS 不得配 TTM PE），否則 L2 明示「口徑不一致」並不出 Fair Value（INFERENCE，AI 總管暫定）。
4. 「E」字樣只在有實際預估資料源時出現；⛔ 用 TTM 外推冒充 `FY2026E`。

---

## §11 大盤 EPS×PE 與單檔估值分離治理〔客戶 §43〕

| 契約 | 公式（客戶原文） | 輸出 | 現況 |
|---|---|---|---|
| **大盤** | Market EPS × Reasonable Market PE | index scenario／range | **Research Gate**（DEC-091(g)、DEC-092「EPS×PE 保留 Research Framework，正式公式仍需 High Gate」、BACKLOG `DEC092-EPSPE-HIGH-GATE` not started）；`render_chart_c`「研究框架，未啟用」、零數值 |
| **個股** | Company EPS × Company valuation multiple | company valuation | §10 |

- 兩者 **source、horizon、methodology、threshold 分開治理**；⛔ 共用常數、⛔ 一個頁面的估值卡同時引用兩者而不標契約名〔§43〕。
- 大盤模型仍在 Research Gate → **保持 Research**；⛔ 為 UI 順便 productionize〔§43 原文〕。

---

## §12 Decision Digest Viewer／唯讀 Rule Registry〔客戶 §25～§27〕

### §12.1 Rule Registry（唯讀）

- 欄位〔§26〕：Rule ID、parameter、current value、version、effective_from、decision/source。⛔ slider、editable text、direct save。
- **只能顯示已存在的 id**：**FACT** 現行唯一正式 rule id 集合＝`shared/decision_digest_rules.RULE_ID_ALLOWLIST`（**6 id**：`risk_cap`、`cut`、`take_profit_force`、`take_profit_partial`、`pause_add`、`add`；量測日 2026-11-02）。客戶範例的 `R-VIX-02` 類 ID **不存在**（grep `R-VIX` 產品碼 0 命中）。
- **⛔ 編造 rule id**（同 §15.4「不創造 Rule ID」）。為既有 SSOT 門檻（例 `shared/macro_buckets.DangerSpec` 16 燈、`MACRO_THRESHOLDS`）建立 rule id＝**新規格**（命名規則、版本、effective_from 來源），屬 Stage E／F 的內部規格＋獨立 QA；若命名會被客戶當成投資規則名稱外露，先出草稿（BACKLOG `FUI-RULE-ID-SPEC`）。
- version／effective_from 多數不可得（`DangerSpec` 無此欄）→ 誠實 `⬜ 資料未備`，⛔ 補日期。
- 門檻數值**只從 SSOT 常數渲染**；Digest ⛔ 搬門檻值（Digest 契約 §6 A8 仍有效）。

### §12.2 Decision Digest Viewer

- **L1 human-readable**〔§27〕：例 `VIX 32.4　R-VIX-02　→ 高波動狀態`（客戶範例；R-VIX-02 現不存在 → 實作時只能顯示 Registry 內 id，無 id 者顯示事實＋狀態、不顯示 id 欄）。
- **L2 raw structured snapshot**。
- ⛔ 顯示 API key、secret、token、OAuth credential〔§27〕；輸出前過 `shared/secret_scrub.scrub_secrets`（FACT：模組存在且已廣泛使用）＋Sheet ID 只顯示末 6 碼（沿 `page_me` 現行）。
- **依賴 Stage F**：FACT `decision_digest_builder.build_decision_digest` **0 production caller** → 現在沒有正式 Digest 可顯示。Stage E 先做殼＋`⬜ 尚未提供（待 Headless Digest）`，Stage F 合格後接真資料（INFERENCE：順序張力已登記）。
- 與 Digest 契約 §4「市場事實刻意不帶 rule（維持）」→ **部分取代（INFERENCE：客戶 §27 範例「VIX 32.4　R-VIX-02」推得市場事實要帶 rule id；客戶未逐字點名 Digest 契約 §4，客戶可推翻）**：市場事實**可以**帶 Registry 產生、對映既有 SSOT 門檻的 rule id；「Registry 外 id 一律違規」「Digest 不搬門檻值」仍有效；屬改契約 → Stage F 升 `SCHEMA_VERSION`。

---

## §13 Presentation Slice ≠ Decision Context〔客戶 §11、§32、§51〕

1. Top N、收合、tab、mobile stack 只是**呈現切片**；完整 candidate universe、所有相關事實仍在 Decision Context〔§11〕。同向既有：DEC-109 十五～十七、Presentation §9／§10 R9、DEC-121 Q2（`DEFAULT_TOP_N=50` 不變）。
2. **Stage F §32 Presentation Slice Independence Test（四情境定義，凍結）**：對**同一份 canonical state**：
   - **Scenario A**：UI 顯示 Top 5。
   - **Scenario B**：UI 顯示 Top 10。
   - **Scenario C**：相關 section collapsed。
   - **Scenario D**：頁面從未 render（headless）。
   - **判準**：四情境產生的 Decision Digest **semantically equivalent**——AI 總管暫定實作判準：`to_dict()` 去除 `generated_at` 類時間戳後**逐欄相等**（含 candidates 全量、industries、missing state、provenance）；任一不等＝測試紅燈。並加 mutation：讓 Digest 讀 UI 的 top_n／expanded → 必須轉紅。（與 Digest 契約 §9 驗收 1～4 同向、加嚴。）

---

## §14 Headless Decision Digest prerequisite〔客戶 Stage F §28～§32〕

1. **正式 invariant（客戶原文）**：Decision Digest must exist without rendering any Streamlit page.
2. Digest assembly ⛔ 依賴：`st.session_state`、market page render、holding page render、expander open、chart render、tab selected。**UI 是 consumer，不是 data producer。**
3. **Pipeline**：Canonical Services → Canonical Snapshot → Deterministic Rules → **Risk Cap** → **System Action** → Decision Digest。（現行鏈為「Rules／Indicators／Risk Cap → Digest」，System Action 未獨立成層——INFERENCE；Stage F 新增。）
4. **Digest 至少保存**〔§31〕：all relevant raw values、normalized values、missing state、provenance、as_of、freshness、rule result、Risk Cap、System Action、portfolio context、candidates、industries、market state。**FACT 缺口**：現行 builder 只搬 market／risk_cap／holdings／actions（`MAX_ACTIONS=3` 截斷），**不搬** raw 指標值、candidates（A3 計畫中）、**industries（無段）**；raw values＝觀測值，不是門檻（與 A8「不搬門檻值」不衝突，INFERENCE）。
5. **現況（FACT）**：`P1R-DIGEST-HEADLESS-ASSEMBLY`（P1 open，依賴 `P1R-FIVE-BUCKET-L3`）；市場段依賴 session warroom；builder 0 production caller。
6. **前置關係（凍結）**：Digest Viewer 的真資料（Stage E 後段）、OneBrain runtime（Stage G）、Cross-page consistency（Stage H）**全部依賴 Stage F 合格**。⛔ Headless Digest 合格前開始 Stage G〔客戶 Stage G 原文〕。
7. **Ad-hoc 研究 Digest 變體**（INFERENCE，內部架構）：單檔查詢（§3.2 session-only）若要給 OneBrain 研究解釋，需一份「session-only、不持久、不併入 canonical」的研究 Digest 變體；⛔ 併入 candidate pool／canonical Digest。Stage F／G 內部設計（BACKLOG `FUI-ADHOC-RESEARCH-DIGEST`）。

---

## §15 OneBrain 僅解釋／反證，不產生第二套動作〔客戶 §18、§23、Stage G §33～§37〕

### §15.1 唯一輸入〔§33〕

OneBrain production reasoning **只讀 Decision Digest**。⛔ UI scraping、session scraping、自己呼叫 source、自己查 Sheet、自己抓 Yahoo、自己改 portfolio。（同向：`ONE_AI_BRAIN_BOUNDARY` §2／§3、ADR-OB-001。）

### §15.2 Output schema（最低集，凍結）〔§35〕

`summary`、`outlook`、`signal_consistency`、`reasons[]`、`counter_evidence[]`、`limitations[]`、`evidence_refs[]`；如有 action explanation：`system_action_ref`。**AI 不產生 independent action。**
- `ONEBRAIN_ARCHITECTURE` §11 概念 schema → **部分取代**（以本欄位為最低集）；其硬規則（只用既有正式詞彙、新詞走 Customer Gate、evidence 回指 Digest／RuleRef、raw text 不是 final result）**繼續有效**；`confidence` 依 §7 **不納入**。
- **`outlook`、`signal_consistency` 的值域未定義**：若用方向詞（偏多／偏空）會撞 DEC-092 Q2、DEC-105 2A、OneBrain G8 → **延後到 Stage G 線框與 AB-2b（`BP-DR-20`）一併送客戶 Gate**（BACKLOG `FUI-ONEBRAIN-VOCAB-GATE`）；Stage G 前 L1「OneBrain Outlook」槽位＝`🤖 ⬜ 尚未提供`。
- Ad-hoc 研究輸出〔§18〕：研究展望、信號一致性、核心理由、最大反證、資料限制；⛔「買進 30%」「今天加碼」「賣出一半」，除非 deterministic action contract 正式允許。Ad-hoc research 不是 portfolio action engine。

### §15.3 Provider neutral〔§34〕

Domain ⛔ hardcode Claude：OneBrain → Provider interface（Claude／Fake／future providers）（同 `ONEBRAIN_ARCHITECTURE` §4）。Claude API 未經 Secret／Cost／Provider Gate → **先 Shadow**；⛔ 偷偷上 production paid call（OB-3 shadow 需 key Decision、OB-6 須另行客戶裁示——仍有效）。

### §15.4 Grounding Gate〔§36〕

所有 output 必須通過 grounding check，至少檢查：evidence refs 存在、不引用不存在數值、不創造 Rule ID、**不違反 Risk Cap**、**不產生禁用 action**、**不產生偽 probability**。**Failure → fallback deterministic summary**（現行 `src/services/decision_digest_summary.build_rule_summary`）。
- **現況（總管稽核轉述，撰寫組未逐條讀實作）**：現行 `shared/decision_digest_grounding` G1～G6 是**封閉句型白名單**（AI 只能選句型填 slot），**不涵蓋 §15.2 的自由結構輸出**（`reasons[]`、`counter_evidence[]` 等）→ Stage G 須另建結構化 grounding（BACKLOG `FUI-GROUNDING-RISKCAP`）。
- **Risk Cap 封鎖必須在 System Action 層上游生效**（§14 Pipeline：Risk Cap → System Action → Digest）：~~被封鎖的加碼在 Digest 裡就不存在；~~ 被封鎖的加碼不會成為 System Action；Digest 仍保存原始 rule result 與 Risk Cap 封鎖紀錄（§14 第 4 點）（2026-11-02 Freeze 獨立驗收修正；有意識的更新，不是漏刪；決策者 客戶（DEC-122 裁示）＋AI 總管〔驗收修正〕；原文刪除線保留）；grounding 只是第二道檢查，⛔ 以 grounding 作為唯一防線。

### §15.5 Cache／Cost〔§37〕

只對相同 **semantic fingerprint** cache；Digest 變更 → 重新計算；⛔ 因 tab switch、rerender、mobile layout、expander 重複付費呼叫。Paid call 原則：explicit refresh／new canonical state，不是 navigation。（同向 `ONEBRAIN_ARCHITECTURE` §7、G5。）

### §15.6 現行違反（列管，不在 Freeze 修）

- **`page_hold` ⑦ AI 戰情總結**：按鈕 → `dividend_station_service.build_ai_summary(digest, app_ai_service.gemini_call)`＝付費 Gemini、輸入非 Decision Digest、無 grounding（FACT）→ **違反 §15.1／§15.4；待 Stage G 替換**（BACKLOG `FUI-HOLD-GEMINI-DIRECT`）。Stage G 前維持現狀、⛔ 擴充。
- legacy AI 出口（`ai_qa_service`、舊頁 Gemini）：舊 UI 凍結，Stage J 盤點。

---

## §16 Desktop／Mobile L1 Blueprint（文字線框）〔客戶 §6、§40、§41〕

> 視窗：桌機 1440×900；手機 390×844（第一屏可用高約 791px，扣底部導覽 53px；Gate §3）。**以下為結構線框，px 未實測**；各頁 Stage 第一步以當時 main 實測，放不下時依 §16.5 處理。⛔ 第一屏被 20 張 cards、大表、工程文字、raw JSON 塞滿（Decision Density）；重要頁順序＝結論 → 圖 → 細節（Text Reduction）〔§41〕。

### §16.1 📊 市場

```
桌機 1440×900                                   │ 手機 390×844（「不用滑」：市場狀態、Risk Cap、是否行動、refresh）
┌─────────────────────────────────────────────┐ │ ┌──────────────────────────┐
│ 📊 市場  問句            [🚀 更新今日戰情]   │ │ │ 📊 市場     [🚀 更新]     │
│ 今日結論（一句，逐字 DEC-081 Q2-1）          │ │ │ 今日結論（一句）          │
│ ┌Regime 市場位階┐┌Risk Cap 水位┐┌今日主要風險┐│ │ │ ┌Regime┐┌Risk Cap ⬜ Q1┐ │
│ └───────────────┘└⬜ PENDING Q1┘└───────────┘│ │ │ └──────┘└──────────────┘ │
│ System Action：今日無需調整｜⚡ N 項需處理   │ │ │ System Action／是否行動 1 行│
│ 🤖 OneBrain Outlook ⬜ 尚未提供｜資料狀態    │ │ ├──────── 第一屏底 ────────┤
│ ┌Primary：台股主圖＋MA 參考線（上緣入第一屏）┐│ │ │ 今日主要風險（L1，緊接）  │
└─────────────────────────────────────────────┘ │ │ 🤖 Outlook ⬜｜資料狀態   │
  ↓ 核心指標卡列（台股/VIX/US10Y/利差/DXY/PMI）  │ │ Primary 台股主圖          │
  ↓ 國際 small multiples → VIX＋門檻帶 → Macro mini│ │ 指標卡（2 欄堆疊）…       │
  ↓ 圖 D 主要風險 → 圖 C Research → L2／L3 摺疊   │ └──────────────────────────┘
```
> 📌 上圖「`⬜ PENDING Q1`」為裁示前字樣（線框圖內無法加刪除線，原圖保留）：**Q1=A 已裁示**，Risk Cap 卡面＝`⬜ 尚未核准／無法判定`（數值另開 Gate）；手機欄以 §16.1-M 為準（2026-11-02 Freeze 獨立驗收修正；有意識的更新，不是漏刪；決策者 客戶（DEC-122 裁示）＋AI 總管〔驗收修正〕；原文刪除線保留）。

- **桌機**：沿用 DEC-117 Q5 已核准順序（頁首→CTA→結論→3 核心狀態→⚡→AI／資料狀態→Primary）；**AI 總管暫定**：「System Action State」與「是否需行動」併成 ⚡ 列一行（不加第 4 張 tile，維持 DEC-117 Q1 三 tile）；核心指標卡列放在 Primary 之後（避免把 Primary 擠出第一屏，契約 B1）。
- **手機（~~PENDING Q3~~ Q3=A 已裁示，正式條文見 §0.1.6；下段為裁示前敘述，保留作歷史）**：§40 要求「是否行動」不用滑，與客戶 2026-10-30 **知情**選的 DEC-118 問題 1=A（⚡ 位於第一屏之後的 mobile exception）相反，且需改 DEC-117 Q1 手機「2＋1」→ **送 Q3**。上方手機線框＝Q3 推薦 A 的樣子（是否行動進第一屏、今日主要風險卡緊接第一屏之後）；**裁示前 DEC-118 問題 1=A、DEC-117 Q1、DEC-120 A10／A11 全部維持**。**「今日主要風險」無論 Q3 結果都仍屬 L1**（DEC-092 Q3「第一層」＝L1，L1 ≠ 第一屏，INFERENCE），⛔ 被 L2／L3 插隊。實際能否放下**未實測**，Stage B 第一步實測（BACKLOG `FUI-MARKET-MOBILE-FIRST-SCREEN`）。

**§16.1-M 📊 市場手機線框（客戶拍板版，Q3=A，2026-11-02；取代上方手機欄的裁示前讀法；px 未實測）**

```
手機 390×844（第一屏可用約 791px）
┌──────────────────────────────┐
│ 📊 市場            [🚀 更新]  │ ← 主 Update CTA（不用滑）
│ 今日結論（一句；逐字）         │
│ 市場目前狀態（市場位階）       │ ← 不用滑
│ Risk Cap：⬜ 無法判定／🔴 超限  │ ← 不用滑（數值未啟用前不顯示 %）
│ 是否需要行動：⚡ N 項／今日無需調整│ ← 不用滑（判不出 → ⬜，⛔ 寫無需調整）
├────────── 第一屏底 ───────────┤
│ 今日主要風險（L1，緊接，⛔ 插隊）│
│ 🤖 OneBrain Outlook ⬜｜資料狀態 │
│ Primary 台股主圖（約 220px）    │
│ 核心指標卡（2 欄堆疊）…         │
│ ▸ L2／L3 摺疊                  │
└──────────────────────────────┘
```
- 取代 DEC-117 Q1 手機 2＋1、DEC-118 問題 1=A、DEC-120 A10／A11（supersede map S10／S11）；桌機（左欄）不變。
- 「今日結論」是否留在第一屏：DEC-081 Q2-1／DEC-109「今日結論必須在第一屏可見」仍有效 → 保留；四個必要項＋結論能否同時放下待 Stage B 實測（INFERENCE）。**放不下時任一項不得自行移出，一律交 Decision Gate**（§0.1.6 第 5 點）。

### §16.2 🎯 標的

```
桌機                                            │ 手機（不用滑：mode、search、查詢摘要）
┌─────────────────────────────────────────────┐ │ ┌──────────────────────────┐
│ 🎯 標的  問句                                │ │ │ 🎯 標的                   │
│ [ 市場精選 ][ 即時查一檔 ]                   │ │ │ [市場精選][即時查一檔]    │
│ 🔍 代碼／名稱 ______ [查詢]                  │ │ │ 🔍 代碼／名稱 ___ [查詢]  │
│ ── 市場精選模式 ──                           │ │ │ 查詢摘要／精選摘要 1～2 行│
│ 資料狀態 chip｜🤖 ⬜                          │ │ ├──────── 第一屏底 ────────┤
│ 產業 Top 5 橫條（Primary）                   │ │ │ 產業 Top 5（精選模式）    │
│ 候選 Top 10 ＋ 查看全部 ＋ CSV               │ │ │ 或 Header＋6 維（查一檔）│
│ ── 即時查一檔模式（查詢後，精選收合）──      │ │ └──────────────────────────┘
│ Header（代碼 名稱 判型 chip〔Neutral/Info〕）│ │
│ 6 維 Snapshot（state＋短句；趨勢/產業 ⬜）   │ │
│ Primary Price Chart                           │ │
└─────────────────────────────────────────────┘ │
  ↓ L2：基本面→估值(§10)→籌碼→產業→風險→🤖研究解釋；加入觀察（尚未提供，disabled）
```

- DEC-107 1A 單頁全展開順序、DEC-121 Q2「整頁已核准順序不變」→ **部分取代**（改雙模式）；DEC-121 Q1、Q3、Q2 其餘（選股條件收合、Top 10 切片、`DEFAULT_TOP_N=50`）、DEC-107 2A～5A 與補充邊界 **繼續有效**。DEC-117～120 的例外**不繼承**（DEC-121 效力邊界，仍有效）。

### §16.3 💼 持股

```
桌機                                            │ 手機（不用滑：portfolio status、Risk Cap、是否需要處理）
┌─────────────────────────────────────────────┐ │ ┌──────────────────────────┐
│ 💼 持股  問句                    [🚀 跑戰情] │ │ │ 💼 持股        [🚀]       │
│ ┌Portfolio Risk Cap┐┌目前曝險┐┌組合狀態────┐│ │ │ 組合狀態 1 行             │
│ │⬜ 無法判定 Q1    ││⬜ Q1   ││            ││ │ │ Risk Cap ⬜／🔴 超限 1 行  │
│ └──────────────────┘└────────┘└────────────┘│ │ │ 今日需處理 N／今日無需調整│
│ 今日需處理：（正式分支；Q2）｜今日無需調整  │ │ ├──────── 第一屏底 ────────┤
│ 🤖 OneBrain 持股摘要 ⬜ 尚未提供（Stage G）  │ │ │ Holdings 精簡表（代碼／名稱│
│ Primary：sector exposure／concentration 圖   │ │ │ ／報酬／System Action）   │
└─────────────────────────────────────────────┘ │ └──────────────────────────┘
  ↓ Holdings Table L1 欄（代碼 名稱 比例 成本 現價 報酬 策略 System Action）
  ↓ performance／benchmark（無歷史淨值 → placeholder）→ L2 明細（兩套刻度、80/20、停利、換股、VaR…）
```

- `🔴 Risk Cap 超限 · 禁止新增曝險` 只在 Q1 裁示並啟用後才可能出現；裁示前「Exposure vs Cap」閘門一律 `⬜`，⑤ 依 DEC-051／PQ-C6-3 已核准的建議持股區間維持（§8.3）。
- DEC-089 G6=A 逐檔戰情表欄位集（張數、均價、市值、健檢等第、235 燈）→ **部分取代**：L1 欄改為客戶 §22 八欄，其餘下沉 L2；「欄位僅限已存在事實」「缺值不當 0」仍有效。

### §16.4 👤 我的

```
桌機                                            │ 手機（不用滑：connection state、primary management actions）
┌─────────────────────────────────────────────┐ │ ┌──────────────────────────┐
│ 👤 我的                                      │ │ │ 👤 我的                   │
│ 連線狀態：Google ✅／Sheet …末 6 碼／組合    │ │ │ 連線狀態 1～2 行          │
│ [切換 Sheet] [選組合] [選觀察清單]           │ │ │ [切換Sheet][選組合]       │
│ ── Audit ──                                  │ │ ├──────── 第一屏底 ────────┤
│ ▸ Decision Digest  ▸ Rule Registry           │ │ │ ▸ Audit 四入口            │
│ ▸ Data Freshness   ▸ System Information      │ │ └──────────────────────────┘
└─────────────────────────────────────────────┘ │
```

- **FACT**：我的頁**無量測基準**（`tools/visual_fidelity/harness_app.py` 只支援 `?p=market|target|hold`）→ Stage E／I 前補 harness（BACKLOG `FUI-ME-HARNESS`）。

### §16.5 放不下時

第一屏實測放不下「不用滑」項目時：優先縮短字句（只下沉、⛔ 刪除，DEC-109 七）→ 合併成一行計數 → 仍不行則該頁 Stage 停在 Decision Gate（版面＝客戶拍板，v3 §03-2 ①），⛔ 自行把客戶核准結構改掉。

---

## §17 Stage A–J 順序、Model×Effort、Stage A 範圍與 DoD〔客戶 §0、§2、§3、Stage A、§52〕

### §17.1 順序（嚴格）〔客戶 §2〕

A Shared Presentation Foundation → B 市場頁 → C 標的頁 → D 持股頁 → E 我的／Audit → F Headless Decision Digest → G OneBrain Runtime → H Cross-page Consistency → I Real-data／Mobile Acceptance → J Old UI Supersede／Removal Gate。
⛔「一邊改 UI、一邊提前接 LLM、一邊重構資料層」〔客戶原文〕。OB-1／OB-2（即使 fake provider／interfaces）也等 Stage G（INFERENCE）。
- 與 DEC-109 三十一 Phase 1～7 → **部分取代**（以 Stage A–J 為準）；「Digest contract 未凍結前不寫新 LLM prompt／glue」**仍有效**。Phase 4／5 已合併成果是 Stage B／C 的起點，不回退。

### §17.2 Model×Effort（客戶 §0 表為上限指引；Minimum Sufficient Effort）

| Stage | 預設 | 升級觸發（升 Opus 5.5＋High） | 出處 |
|---|---|---|---|
| A | Sonnet 5.5＋Medium（component／chip／CSS） | 四態對映若改 L0 語意層、Risk Cap alert 文字語意 | 客戶 §0 表；AI 總管暫定 |
| B | Sonnet 5.5＋Medium（layout／chart） | Risk Cap／System Action 呈現語意、freshness 語意 | 同上 |
| C | Sonnet 5.5＋Medium（含承接 Phase 5 自評 Gate 🟡3：A5 桌機、A4、A10——總管內部處理，不送題） | 估值公式／Forward EPS 語意、Session 隔離守衛 | 同上 |
| D | **Opus 5.5＋High**（Risk Cap／Action Authority 為本頁主體） | — | 客戶 §0 表 |
| E | Sonnet 5.5＋Medium | Rule ID 規格、secret 遮罩 | AI 總管暫定 |
| F | **Opus 5.5＋High** | — | 客戶 Stage F 原文 |
| G | **Opus 5.5＋High** | — | 客戶 Stage G 原文 |
| H | Opus 5.5＋High（跨頁語意一致） | — | AI 總管暫定 |
| I | Sonnet 5.5＋Medium（量測） | 失敗涉及語意 → Opus 5.5＋High | AI 總管暫定 |
| J | 文件 Sonnet 5.5＋Low／Medium；Gate 分析 Opus 5.5＋High | — | AI 總管暫定 |

- ⛔ 整個施工期固定使用 Opus〔客戶 §0〕。切換依 DEC-084／DEC-106（已符合時靜默繼續，不足時停手通知）。本表寫的模型名沿用客戶原文；`MODEL_EFFORT_POLICY` 的「文件整理優先 Haiku＋Low」對本主線**部分取代**為客戶表的 Sonnet＋Low／Medium（AI 總管讀法，supersede map S19）。

### §17.3 Batch 規則〔客戶 §1、§3〕

- 每批最多 **3 個安全工作項目**；每個 Stage 可拆多個 PR；避免四頁＋Digest＋Risk Cap＋OneBrain 同一 PR。
- 每批前重做 **GitHub Verification Gate**：`origin/main`、Open／Draft PR、active branches、relevant commit／diff、CI／QA、current BACKLOG／DECISIONS／STATE／HANDOFF；⛔ 引用上一輪 SHA 當最新 main。

### §17.4 Stage A 範圍（AI 總管暫定切批；開工時以當時 main 重判）

> 📌 **Stage A 暫停；施工路線由 New UI2 Architecture Gate 取代，semantic contracts 不變**（2026-11-02 有意識的政策變更，不是漏刪；決策者 **客戶**（DEC-123）；append-only，本節原文與下方既有 📌 一字未改）：客戶 2026-11-02 裁示 (5)「立即停止目前原本的 Stage A／現有 New UI 延續路線」「後續正式 UI 路線改為 New UI2 Greenfield Presentation Layer」（逐字見 DEC-123）。**被取代**：下表 A-1～A-3 作為「在現有 New UI／`src/ui_v2` 上施工」的批次安排、「優先 reuse `src/ui_v2`」的施工指引、Stage A DoD 的掛載條款。**仍有效（移作 New UI2 components 的需求）**：§4 Semantic Chip（Neutral／Info tone 只加不改、Danger 文字 ≠ 取得失敗）、§5 四態語意層與 `unavailable`→`unwired` 改名、§9 metric card 四欄與 freshness／source tag、§0.1.4 Risk Cap alert 兩態文字（只做元件、⛔ 接數值）、L1／L2／L3 層級；以及本檔**全部 semantic contracts**（New UI2 的 input）。兩邊理由：舊安排在已上線的 New UI 上補共用元件，改動小（當時成立）；新路線依客戶明示——現有 New UI 改為 Legacy New UI／Reuse Candidate，New UI2 為未來唯一主要 Presentation Layer。`src/ui_v2` 各模組是否沿用改依 `docs/vnext/NEWUI2_REUSE_MATRIX_2026-11-02.md` U1～U4；施工順序與完成條件見 `docs/vnext/NEWUI2_ARCHITECTURE_GATE_2026-11-02.md`（BACKLOG `FUI-STAGE-A` paused／superseded、§5.1.18 `NUI2-*`）。

> 📌 **Stage A 前置（2026-11-02 客戶拍板後）**：Freeze 已由客戶拍板，但**須先完成 Freeze 獨立驗收（含必要 QA）PASS**（BACKLOG `FUI-FREEZE-SECOND-AUDIT`；客戶原文「不得因本裁示直接跳過 Freeze 驗收」），才能依下表開 A-1。A-2 的 Risk Cap alert primitive 依 §0.1.4 只做 `⬜ 無法判定`／`🔴 超限 · 禁止新增曝險` 兩態文字，⛔ 接數值。

目標〔客戶原文〕：先建立四頁共用 presentation primitives；**優先 reuse `src/ui_v2` 與既有 common component**；⛔ 重寫整套 component library。

| 批 | 項目（≤3） | 依據 |
|---|---|---|
| A-1 | ① Neutral／Info chip kind（只加不改）＋§4 tone 常數；② 四態語意層 helper（§5.2 對映表、L1 字樣常數，十態不改）；③ `unavailable` kind 改名（§5.3，與契約 §6 表、`test_compact` 同 PR） | §4、§5 |
| A-2 | ① metric card（value／state／as_of／source 四欄，§9）；② freshness micro-tag＋source tag（沿用 `asof`／`source`／`stale` kind）；③ Risk Cap alert primitive（`⬜ 無法判定`／`🔴 超限 · 禁止新增曝險` 兩態文字，**只做元件、不接任何頁、不接數值**；Q1 裁示後才可掛載） | §8.1、§9 |
| A-3 | ① section header＋audit link；② chart container（沿用 `chart_header_html`／圖槽 compact 高度）；③ mobile stack＋expander hierarchy（L1／L2／L3 摺疊層級） | Stage A 清單 |

**Stage A DoD**（全部滿足才算 Stage A 完成）：
1. 每批 targeted tests＋mutation（拔掉新守衛必轉紅）；新元件預設不掛任何頁（或掛載時現有頁輸出 byte-identical，以既有還原鏈／z60 指紋守衛）。
2. **No investment semantic change**（PR 明示）；0 diff：`src/services|compute|data`、`shared/` 的投資語意常數、`app.py` 掛載點、`requirements.txt`。
3. 元件 preview（`tools/phase3_preview` 類）＋Visual Fidelity 檢查（V8 依 §4 新讀法、V9、V10）。
4. 獨立 QA（非實作組）＋CI 綠＋merge＋main verification；DECISIONS／BACKLOG／PROJECT_STATE／HANDOFF 同步。
5. 完成整個 Stage A 才回報（§18.4 格式）〔客戶 §52〕。

---

## §18 每批驗收、Visual Gate 加嚴、輸出規則

1. **每批 PR 驗收**〔客戶 §45〕：What changed? What did NOT change? Which contract? What tests? Any semantic change? Any missing capability? 只是 UI → 必須明示 **No investment semantic change**。
2. **QA 原則**〔§44〕：UI batch＝targeted tests；Data semantic／Digest／Risk Cap＝full relevant QA；真正 Risk Cap／action invariant＝High Effort＋full QA。
3. **Visual Fidelity Gate**〔§41〕：保留既有 A1～A11、V1～V11；**新增 Decision Density**（⛔ 第一屏被 20 張 cards、大表、工程文字、raw JSON 塞滿）與 **Text Reduction**（結論 → 圖 → 細節；⛔ 說明 → 說明 → 說明 → 圖）。V8「🔴 只用於系統真錯誤」→ 依 §4 改讀為「🔴 只用於系統真錯誤與確定性違規，兩者文字不同」。數值判準由 Stage A／B 內部定、寫進 Gate 報告。
4. **Stage 完成回報**〔§48〕：格式 `🟢 Stage X 完成`＋表（項目｜結果｜main SHA｜PR #｜Stage X｜Production behavior changed／unchanged｜Semantic change yes／no｜QA pass｜Visual Gate pass／accepted deviation｜Mobile status｜Remaining blocker｜Next handoff）；不要施工日誌。→ 對 Stage 完成回報**部分取代** DEC-060「一般完成回報 ≤5 行」；「完整技術／稽核證據留在 PR」仍有效。
5. **Auto-Ship**〔§46〕：只在既有 Safe Auto-Ship 規則內 commit／push／PR／QA／merge；new investment semantics、new threshold、Risk Cap modification、source change、irreversible migration、ambiguity → 停在 Decision Gate。
6. **Hard Output Gate**〔§47〕：只在 🔴 客戶裁示、🟡 Model／Effort change、🟡 Manual action、🟢 完整 Stage 完成、🟡 Safe Handoff required 時輸出（與 DEC-104 一致）。
7. **Safe Handoff**〔§49〕：worktree clean、PR known state、CI known、PROJECT_STATE／HANDOFF／BACKLOG／DECISIONS 依 repo 規則保存 → 🟡 建議切換新對話＋唯一接手點（`PROJECT_RULES.md` 第 20～22 節、SESSION_CONTINUITY C1～C4）。
8. **Stage H 射程**（INFERENCE，AI 總管暫定）：「四頁＋所有 Digest 消費者（含 LINE 推播 `push_holdings_daily.yml` 等）」；舊 UI（`?legacy=1`）凍結不改，以揭露處理（BACKLOG `FUI-PUSH-ACTION-CONSISTENCY`）。

---

## §19 完成定義〔客戶 §50，逐項〕

| 面 | 必須 |
|---|---|
| 市場 | clean chart-first、Regime、Risk Cap、provenance、OneBrain outlook |
| 標的 | 精選／Ad-hoc dual mode、single-stock research、valuation、freshness、no auto-write |
| 持股 | Single Action Authority、Risk Cap enforcement、clear actions、portfolio risk |
| 我的 | connection/settings、Digest audit、Rule registry |
| Architecture | Headless Digest、Presentation Slice ≠ Decision Context、OneBrain only consumes Digest、grounding、deterministic fallback |
| UX | Desktop accepted、Mobile accepted、real data accepted、missing/stale accepted |
| Governance | no hidden capability loss、old/new map complete、SSOT synchronized |

**Stage J 提出 Old UI Removal Decision Gate 的六條件**〔客戶 Stage J〕：四頁能力 coverage 完成、mobile acceptance、real data acceptance、audit coverage、user final acceptance、old/new capability map 無 critical gap。**現況：第 6 條不成立**（capability map 列 critical 7 列；量測日 2026-11-02）。舊 UI 現階段 ⛔ 提前刪（DEC-019／020 仍有效）。**與 DEC-083 第 11 點 E 段 Removal Gate（capability inventory → Old→New mapping → 實作 → coverage validation → regression → customer approval 等七步）取聯集**：兩組條件都成立才能提出 Removal Decision Gate。

---

## §20 Decision Gate（~~**PENDING**，待客戶裁示~~ **已裁示：Q1=A／Q2=A／Q3=A（客戶 2026-11-02）**；共 3 題〔裁示 5：最多 2～3 題〕）

> 📌 **三題已全數裁示 A**；正式條文見 §0.1.4～§0.1.6。下列題文為送題當時的版本，保留作歷史；「裁示前暫行」各句已失效（2026-11-02 客戶裁示 Q1～Q3 後更新；有意識的更新，不是漏刪；決策者 客戶（DEC-122 裁示）；原文刪除線保留）。

> 判題原則：客戶指示已寫明者不問；技術細節不問；只問投資語意／門檻／版面，且指示沒寫到、或與另一條**客戶**裁示互撞者。OneBrain 詞彙值域延後 Stage G Gate、新版加入觀察是否啟用延後 ME-P2／HI-5 Gate，**不送題**。
~~> **本 Freeze 整體也待客戶拍板**：客戶拍板 Freeze＋裁示 Q1～Q3 後，才開始 Stage A。~~ **Freeze 已由客戶拍板、Q1～Q3 已裁示（2026-11-02）；Stage A 須待 Freeze 獨立驗收（含必要 QA）PASS 後才能開始**（2026-11-02 Freeze 獨立驗收修正；有意識的更新，不是漏刪；決策者 客戶（DEC-122 裁示）＋AI 總管〔驗收修正〕；原文刪除線保留）。

### Q1｜Risk Cap 閘門：「目前曝險」用什麼分母？數值何時開始真的生效？兩頁的區間顯示要不要統一？〔投資語意＋門檻〕

- **為什麼要問**：你要求「曝險 > 上限 → 🔴 禁止新增曝險」。但 (1) 上限數字在 📊 市場頁依 DEC-081 Q2-2／RC-VISIBILITY 仍「尚未核准、不顯示」；(2) 💼 持股頁卡⑤則依 **DEC-051／PQ-C6-3（你 2026-10-16 核准）已外露建議持股區間**——兩頁目前不一致；(3) 上限的分母是「整體資產」，而持股資料沒有現金／總資產，算不出「目前曝險」；(4) 你也指示 Risk Cap 變更要停在 Decision Gate。
- **A（總管推薦）**：本次 Freeze **只定規則形狀**——超限 → 禁止新增曝險；目前曝險或有效上限任一不可得 → `⬜ 無法判定`，且加碼類動作**不得被當成沒有上限**（同列標「Risk Cap 無法判定」）。**數字啟用另開 Risk Cap Gate**（解 RC-VISIBILITY＋定義曝險分母與現金／總資產輸入）。兩頁區間顯示：**維持現狀**（持股頁保留已核准區間、市場頁維持隱藏），統一方式在 RC Gate 一併決定。理由：不碰 Risk Cap 公式、不放寬風控、不撤回你已核准的顯示、符合「未評估 ≠ 安全」。
- **B**：現在就定「分母＝持股市值合計（不含現金）」並啟用超限判定。代價：沒有現金時曝險恆為 100%，與 Risk Cap「整體資產」口徑不同，可能長期顯示超限。
- **C**：先補「現金／總資產」輸入再啟用——在 Google Sheet 新增「現金」欄，**或由 👤 我的 頁輸入總資產／現金**（舊 UI 有 session 版總資金輸入可參考〔FACT，2026-11-02 grep：`src/ui/tabs/stock_sections/section_when_buy_sell.py` 的 `render_when_buy_sell_section` 內 `st.number_input`「💰 你的總資金（元）— 填了才會算『建議買幾張 + 真 ATR 停損』」，session key `_pos_capital`、跨股共用，供 `calculate_position_size` 算建議張數；只存 session、不寫 Sheet〕）。代價：需要你維護一個數字；新增 Sheet 欄位或新 UI 輸入屬寫入面／schema 變更，須另過 Sheet Safety／HI-5。
- **另請一併決定**：持股頁⑤已核准外露的建議持股區間，Final UI 是否保留（推薦：保留，市場頁何時解除隱藏留給 RC Gate）。

### Q2｜持股「今日需處理」顯示哪些動作詞？既有動作怎麼對到你的五個詞？〔投資語意〕

- **為什麼要問**：你要的是「加碼／持有／減碼 1/2／全出」＋沒事時「今日無需調整」。現行正式規則只有：ETF 七分支（汰弱、**強制停利 >+3σ**、**分批停利 >+2σ**、**暫停加碼**、加碼、高溢價、巡航）與個股換股四級（**🔴 換出**／🟡 留意／🟢 續抱／⚪ 資料不足）；**沒有任何規則定義「減碼一半」或「全出」**。另外 DEC-109 十三（你 2026-10-29）把持股頁第一屏寫成「**加／留／換／減**」摘要——「換」（換股）在你這次的五個詞裡沒有對應。把既有分支改名成新詞是新的行動語意；「1/2」是正式比例，依 DEC-053 須先驗證＋回測／Shadow。
- **A（總管推薦）**：第一版**沿用既有分支原名**顯示，依 DEC-109 十三「加／留／換／減」分組（**分組為總管提案，待客戶裁示**；分支名一律**原名照寫**）：加＝加碼；留＝巡航、🟢 續抱、暫停加碼、高溢價、🟡 留意（沒有任何動作時整列顯示「今日無需調整」）；換＝🔴 換出（個股軌）；減＝強制停利（>+3σ）、分批停利（>+2σ）、汰弱（⛔ 改叫「減碼 1/2」「全出」）；⚪ 資料不足＝`⬜ 尚未評估`，⛔ 當成「今日無需調整」；「減碼 1/2」「全出」在走完 DEC-053 驗證回測前**不產生、不顯示**。理由：完全來自正式 deterministic state，不新增投資語意，也與你 10-29 的「加／留／換／減」一致。
- **B**：建立「既有分支 → 五詞」對映表（例：分批停利→減碼 1/2、強制停利或汰弱或 🔴 換出→全出、暫停加碼→持有），無對應者不顯示。代價：等於替既有規則賦予新的比例語意，未經回測；「換」會被併進「全出」。
- **C**：另開投資規則研究批（Investment Logic Audit 範圍），研究完成前「今日需處理」只顯示「N 檔需處理」計數。

### Q3｜📊 市場頁手機第一屏：「是否行動」要不要不用滑就看得到？〔版面，與你 10-30 的裁示相反〕

- **為什麼要問**：你這次 §40 要求手機市場頁「不用滑：市場狀態、Risk Cap、是否行動、refresh」。但你 2026-10-30 在看過「手機第一屏一定看得到是否需行動」這個選項後，**選了 DEC-118 問題 1=A**（⚡ 需要處理放在第一屏**緊接之後**，作為手機例外；總管轉述，題幹見 DEC-118 送審附錄）。兩者相反；而且要放得下，必須改 DEC-117 Q1 的手機「2＋1」核心狀態排法（第三格「今日主要風險」移到第一屏之後）。
- **A（總管推薦）**：照 §40——「是否行動」進手機第一屏，「今日主要風險」卡**緊接第一屏之後**（仍屬第一層，⛔ 被其他內容插隊）；正式改 DEC-117 Q1 手機排法與 DEC-118 問題 1；DEC-120 的 A10／A11 例外隨之重量。Stage B 第一步實測，放不下再回報。理由：這是你最新、最明確的手機要求。
- **B**：維持 DEC-118 問題 1=A（⚡ 緊接第一屏之後），§40 在市場頁改讀為「緊接第一屏」；DEC-117 Q1 手機 2＋1 與 DEC-120 例外照舊。理由：已實作、已通過 Phase 4 Gate，改動最小。

**裁示前暫行**：§6 第 5 點、§8.3（較嚴讀法）；手機市場頁維持 DEC-118 問題 1=A／DEC-117 Q1／DEC-120 現狀。**裁示後**：結果寫入 DEC-122 補註與本節；**客戶拍板本 Freeze＋Q1～Q3 後**才開始 Stage A〔裁示 6〕。

---
## §21 術語統一表〔客戶 §39〕（AI 總管暫定；客戶可推翻）

| 統一概念（客戶用語） | 全站顯示字樣 | 程式／Digest 鍵 | 備註 |
|---|---|---|---|
| Regime | 市場位階 | `regime` | **維持「市場位階」＝AI 總管依 DEC-105 2A（客戶核准字樣）自決，客戶可推翻**；五態字樣不變；⛔ 映射偏多／中性／偏空 |
| Risk Cap | Risk Cap（風險上限） | `risk_cap` | DEC-081 Q2-2 卡面措辭逐字有效 |
| Missing | 資料未取得／資料未備 | `missing` | §5 |
| Freshness | 資料日／過期 | `as_of`／`stale` | §9 |
| System Action | 系統動作 | `system_action` | ~~§6；詞彙 PENDING Q2~~ §6；詞彙 Q2=A 已裁示（§0.1.5） |
| OneBrain | 🤖 OneBrain | `onebrain` | 取代「AI 投資總結」入口名與否＝Stage G 線框 |
| Strategy | 策略（存股／資本利得／未分類） | `strategy_class` | AB-4w 前一律未分類 |
| Valuation | 估值 | `valuation` | §10／§11 兩契約分開 |

⛔ 每頁各叫不同名字；Stage H 驗收（BACKLOG `FUI-TERMINOLOGY`）。

---

## §22 未驗與限制

- 全文單組撰寫；invA／invB 皆單組；「0 命中」皆 grep、非窮舉；未跑 runtime、未在 Streamlit Cloud／手機實機／真資料驗。
- §16 線框 px 未實測；手機市場頁第一屏能否放下「是否行動」未知（Phase 4 實量：⚡ 頂端 loaded y1016 > 791，夾具）。
- 撰寫組只讀本地 `origin/main` `ce8422d`；open PR／遠端分支以 GitHub 實查為準。
- 客戶原文取自總管轉交之逐字檔；撰寫組未見客戶原訊息本身（DEC-122 揭露）。
- 待第二組獨立驗證後，本註保留作 provenance（BACKLOG `FUI-FREEZE-SECOND-AUDIT`）。
