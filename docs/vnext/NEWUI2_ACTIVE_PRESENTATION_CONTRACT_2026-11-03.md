# New UI2 Active Presentation Contract（現行唯一有效的 presentation contract；2026-11-03）

> ## ⛔ 讀我先：這是**現行唯一有效**的 New UI2 presentation contract
>
> **與其他文件衝突時，以本文件與 `docs/DECISIONS.md` DEC-128 為準。** 不得要求任何 session 自己猜「哪一段比較新」：下列舊條文**全部已降為 `SUPERSEDED / HISTORICAL — NOT ACTIVE`**（歷史證據保留、原文一字不刪），其清單見 §10 與 DEC-128 §二（S21～S35）。**⛔ 不得依舊 Wireframes／Freeze／Presentation Contract 內「▸ 為什麼（L2）」「▸ 指標明細（16 項）（L3）」「▸ 原始資料表／工程診斷（L3）」等 L2／L3 expander 條文施工。**
>
> ### Active interpretation（11 點；客戶 2026-11-03 (14) §4；新 session 只能得到這一套）
>
> 1. Presentation Compression ≠ Information Loss　2. 簡單但不能失去判讀能力　3. Chart-first　4. 主要圖表提供精簡 SPEC　5. 四個主要投資頁不承載完整 L2／L3 diagnostics　6. 完整 Evidence 仍保留　7. 👤 我的 → 資料健康度　8. UI ViewModel ≠ Decision Digest　9. OneBrain 讀完整正式 Evidence（⛔ 只能讀 UI slice 的讀法不是 Active）　10. **桌機左側有 Login＋Auth Status（compact Account Area，§2.5）**　11. **手機仍只有四格導航**
>
> - **決策來源**：客戶 2026-11-03 指示 (13)（逐字見 DEC-128 fence）與追加裁示 (14)（逐字見 DEC-129 fence；**優先於 (13) 衝突處**）。**本文件不是新的客戶裁示**：凡標「⚠ PROVISIONAL」者是 AI 總管暫定讀法，客戶可推翻（DEC-128 §四）。
> - **src 註解與 docstring 若與本契約衝突，以本契約為準**（現存過時註解已登記 `docs/BACKLOG.md` §5.1.26 `NUI2-COMMENT-DOCSTRING-SYNC`，待 UI 批 P1／P3 改；本批不改 src）。
> - **範圍**：只管 New UI2（`src/ui2/**`、`src/services/ui2/**`、`shared/ui2_contract/**`、`app_ui2.py`）的**四個正式投資頁** Human Presentation 與其周邊（資料健康度、Preview 控制、OneBrain Outlook 區塊、projection 邊界）。Old UI／Legacy New UI 不在範圍（凍結，不刪不改）。
> - **不改**：資料語意（DEC-124）、Single Action Authority、Risk Cap、System Action 語意、Decision Digest schema、任何公式／門檻／source。
> - **本批沒有改任何 UI 程式**（只改 docs 與測試清理，DEC-129 §四）：現行 Preview 與本文件有落差，屬 **implementation deviation**（§9），由後續 UI correction 批（`docs/BACKLOG.md` §5.1.26）修正；**⛔ 不得反過來改本文件去配合現行 UI**（客戶 (12)-6）。

---

## §1 最高原則：Presentation Compression ≠ Information Loss

1. UI 越簡潔，Decision Context **不能**越少。簡單，但不能失去判讀能力。
2. New UI2 Human UI＝**簡潔、Chart-first、關鍵判斷優先、少量必要 evidence、source／as_of／freshness micro-tag、不堆完整資料清單**。
3. 完整資料仍保存在 backend Evidence／Decision Context；「從 UI 移除」**不等於**刪資料（§8 清單）。
4. 判讀能力的檢驗：看完第一屏，使用者仍答得出「現在狀態？要不要行動？依據是什麼？資料可信嗎？」——這四問的**答案**留在 Human UI，**推導過程的全部明細**移到資料健康度／Evidence。

## §2 四頁正式 Human UI 與每頁優先順序

正式主頁只有四個：**1. 📊 市場　2. 🎯 標的　3. 💼 持股　4. 👤 我的**（不得新增第五頁／第五導覽項）。

每頁由上到下的優先順序（客戶 (13)-2；與 Wireframes §1 第一屏四問、DEC-127 順序**相容**）：

1. **狀態／結論**
2. **是否需注意／正式 Action State**（只呈現來自正式 deterministic action state 的動作；無動作＝「今日無需調整」或 `⬜`，⛔ 硬填）
3. **主要圖表**（Chart-first，§4）
4. **關鍵 evidence**（少量必要；例：兩套刻度、價格資料日、Risk Cap 完整性 chip、外幣逐字句——Presentation Contract §16 保留者）
5. **必要數字**
6. **簡短 source／as_of／limitation**（micro-tag；一行）

> 四問是**資訊需求**，不要求視覺 DOM 逐字 1→2→3→4（DEC-127 第 1 點）；frozen visual contract 優先決定排版。

### §2.5 桌機左側 Navigation Rail 與 compact Account Area（客戶 (14) §1；DEC-129）

- **桌機（1440）結構**：Product／Logo → Login／Auth Status（compact Account Area）→ 📊 市場 → 🎯 標的 → 💼 持股 → 👤 我的。**手機仍固定底部四格**，登入主要由 👤 我的承接（Wireframes §0.4 手機部分、DEC-127 導覽餘裕不變）。
- **未登入**：「登入」＋「⬜ 尚未登入」（客戶明示採用該字面）；**已登入**：「✅ 已登入」＋必要使用者識別＋登出入口。可選一行 Sheet／Portfolio selection compact status——**僅限已有正式 contract**，⛔ 新語意。
- **Account Area 不算第五頁、不增第五個主導航；⛔ 顯示 secret／credential；⛔ 從 URL／query parameter 猜登入狀態。**
- **Authentication State 必須來自正式 auth contract。⚠ 目前 repo 沒有 New UI2 用的正式 auth contract**：Preview 殼的 `ui2_account` selectbox（signed_out／signed_in／unavailable）只是**開發面 FAKE 場景**，**不是 auth contract**，不得當登入狀態來源；真實 auth 架構（OAuth 本體）屬 Opus 5.5＋High Gate（`NUI2-AUTH-CONTRACT-GATE`），本文件**不設計它**。
- 與 👤 我的頁內「連線狀態」的分工：頁內連線卡只出現一次（§3.4）；Account Area 只放 compact 狀態，兩者資料來源須同一個 auth contract（避免兩套登入狀態）。

## §3 各頁「應有／不應有」（L1 為主；L2／L3 明細移出的內容改放哪裡）

> **形態規則**（📊🎯💼 整頁 0 個完整 evidence expander；👤 的稽核面入口〔Digest Viewer L1、Rule Registry，預設收合〕為明列例外〔⚠ PROVISIONAL (b)①〕，但 👤 同樣不得有「為什麼／指標明細／原始資料／工程診斷」類 evidence expander）：四頁 Human VM 的 `SectionVM.level` 只允許 `L1` 與「關鍵 evidence 精簡層」；**⛔ 不得出現任何標示 L2／L3 的 expander、標題或標籤**（資料健康度的 Level 3 developer diagnostics 除外，見 §5）。「精簡 evidence」＝單行／小 chip／圖下方 SPEC 行／必要數字旁的 micro-tag，**不是**被摺起來的段落。

### 3.1 📊 市場

| 應有（順序依 Wireframes §2.1／§2.2 與 DEC-127；`KEEP`） | 不應有（Human UI） | 移出內容的新去處 |
|---|---|---|
| 頁首 → 🚀 更新今日戰情 CTA（含不可用原因）→ 今日結論（逐字）→ 市場目前狀態（五態；⛔ 偏多／中性／偏空）／Risk Cap（`⬜ 無法判定`）／今日主要風險（L1；退化句逐字）→ 是否需要行動 → `🤖 OneBrain Outlook`（§7）→ Primary 台股主圖（+SPEC）→ 核心指標卡（台股、VIX、US10Y、利差、DXY、PMI／景氣；每卡值·短狀態·as_of·源）→ 國際 small multiples → VIX＋既有門檻帶 → Macro mini → 圖 C Research 空槽 | `▸ 為什麼（L2）`／`▸ 指標明細（16 項）（L3）`／`▸ 原始資料表／工程診斷（L3）` 三個 expander；L0 位階完整說明（`NOT_LOADED_PENDING_BREADTH_EXPLAIN` 等）整段；工程字樣（PORT／Gate／Stage／Aggregator／路徑 C／nonce／規則分支 id…）；大量 Missing 清單；題號鷹架「①②③④」可見文字（⚠ INFERENCE：它們是線框註記，不是產品文字；`data-ui2-q` 錨點保留） | 位階完整說明→**資料健康度·市場位階項 Level 2**；16 項逐格明細→Evidence／Digest ＋資料健康度摘要（例「14／16 可讀」）；原始資料表→backend（不上 UI）；工程診斷→**資料健康度 Level 3**；counter evidence→🤖 OneBrain Outlook（§7）＋Digest；Missing 清單→資料健康度 |

### 3.2 🎯 標的

| 應有 | 不應有 | 新去處 |
|---|---|---|
| 模式膠囊（市場精選／即時查一檔）→ 搜尋 → 查詢摘要 → W-4 context 行（輕量、Neutral／Info）→ **精選**：產業機會 Top 5、候選 Top 10、**查看全部候選／CSV／`› 查看此檔`**（使用者功能，DEC-121 Q2=B）、選股條件＋一行摘要（使用者功能；⚠ PROVISIONAL (b)②）→ **查一檔**：Header＋chips → 6 維 Snapshot → Primary 價格圖（+SPEC）→ 基本面／估值（EPS basis·source·as_of·PE multiple 壓成一行 SPEC，Freeze §10）／籌碼／產業／風險的**精簡 chart-first 卡** → `🤖 研究解釋` 槽 → 加入觀察（disabled，直到寫入 Gate） | 標題含「（L2）」「（L3）」的 expander；`▸ 完整 6 欄表／跨季趨勢（L3）` 作為 **evidence** 摺疊（「查看全部」是使用者功能，保留）；「Legacy UI 層…第二套規則…PORT 至 L3」類工程句；大量 Missing 清單 | 跨季趨勢／完整分析明細→Evidence／Digest（⚠ PROVISIONAL：是否保留為使用者「完整分析」功能待客戶確認）；來源／口徑／公式→資料健康度 Level 2 |

### 3.3 💼 持股

| 應有 | 不應有 | 新去處 |
|---|---|---|
| 頁首＋主 CTA（依 Wireframes §4.1 在 header 列）→ Portfolio 狀態／Risk Cap／今日需處理（只放正式 Action）→ Portfolio Overview 圖（performance、benchmark、sector exposure、strategy distribution、concentration）→ Holdings Table L1 八欄（代碼、名稱、持股比例、成本、現價、報酬、策略、System Action）→ 建議持股水位（市場端）卡 → OneBrain 持股摘要槽 | `▸ L2 明細`（fundamental、risk、chip、**evidence、rule IDs**）與 `▸ L3 原始明細` 作為頁內 expander；工程句 | evidence／rule IDs→**Decision Digest／Evidence**；兩套刻度、80/20、停利、換股、VaR 等**使用者分析**以精簡 chart-first 形態保留（Freeze §2.3），不以 expander 摺疊；原始明細→backend |

### 3.4 👤 我的

| 應有 | 不應有 | 新去處 |
|---|---|---|
| 連線狀態（Google／Sheet）＋主 CTA（**各只出現一次**）→ 一般設定（Portfolio、Watchlist、Strategy、Notifications、Display）→ **資料健康度**（§5，新增／預留）→ **稽核面**（Audit：Decision Digest Viewer L1 句型、Rule Registry 唯讀；預設收合；⚠ PROVISIONAL (b)①） | 同一連線狀態或 CTA 重複出現；「OAuth…nonce…路徑 C」等工程句；Digest 的 raw structured snapshot／Registry 明細／工程診斷放在 Audit 一般層 | Data Freshness、System Information→**資料健康度 Level 1／2**；Digest raw snapshot、工程診斷→**資料健康度 Level 3（預設收合）**；過 `scrub_secrets`，⛔ 外露 §5 禁曝險清單 |

## §4 Chart-first＋Chart SPEC

**何時用圖**：能用圖表清楚表達**趨勢、比較、強弱、歷史位置、配置、風險**時優先用圖表（Presentation Contract §24.1：圖表＞數字＞短句＞長文字）。

**⛔ 不得**：(a) 為漂亮新增沒有正式語意的圖；(b) 不同單位硬疊在同一座標；(c) 用雙軸造成誤導；(d) 讓圖表自行產生 investment semantics（圖只畫既有正式事實；門檻帶只引既有 SSOT 門檻，⛔ 新門檻）。

**每個主要 chart 附一行精簡 SPEC**（"SPEC 必須短"）。格式：

```
SPEC｜<頻率>｜<來源>｜資料日 <MM/DD>｜<缺值處理>        ← 最小集（客戶範例）
SPEC｜日頻｜TWSE｜資料日 11/03｜缺值不補                  ← 範例 1（台股主圖）
SPEC｜日頻｜<標的> vs 0050｜base=100（<期間起點>）｜資料日 11/03｜缺值不補   ← 範例 2（比較圖，normalized）
SPEC｜日頻｜FRED｜單位 %｜資料日 11/02（T+1）｜缺值不補     ← 範例 3（利率／殖利率）
```

依需求可含：標的、期間、normalized base、單位、頻率、最新資料日、Missing handling、comparison rule、source。**單行**；欄位值只能取自該圖的 `FieldVM.freshness`／既有 SSOT（⛔ 手寫日期、⛔ 寫服務名冒充資料源；缺 as_of 顯示 `⬜ 資料日未提供`）。長度上限在 UI 批以 390px 實測決定（`T-new-6`），本文件不釘死數字。

## §5 👤 我的 → 資料健康度（完整資料診斷的唯一集中處）

**定位**：完整資料診斷**集中**至此，不再散落四個投資頁（四頁只留 micro-tag 與一行狀態入口，點擊導向本區；⚠ PROVISIONAL (b)④）。

**涵蓋項目（適用者）**：台股大盤、國際市場、VIX、利率／殖利率／利差、DXY、PMI／景氣、市場廣度、產業、法人／籌碼／融資、個股價格、基本面、估值、持股／portfolio、Risk Cap inputs、System Action inputs、Sheet／settings、其他正式 canonical sources。（尚無 canonical 的項目顯示 `⬜ 尚未接線`，⛔ 捏造來源。）

**每項可含的欄位**：資料名稱｜status｜是否取得｜source｜as_of｜retrieved_at｜freshness｜Missing／failed reason｜proxy／estimated｜source health。（缺的欄位顯示缺，⛔ 補推估值；`retrieved_at`、`source health` 若 canonical 尚無＝資料契約缺口，登記 `NUI2-DATA-HEALTH-FIELD-GAPS`，⛔ 本批自行新增資料 contract。）

**三層**：

| 層 | 內容 | 預設 |
|---|---|---|
| **Level 1 使用者可讀摘要** | 逐項 status，符號：`✅ 正常`、`◷ 可能過期`、`◇ 資料未備`、`⛔ 來源不可用`、`⬜ 尚未接線`；頂端一行總計（例「資料 8／9 正常 · 1 項待更新」，DEC-091 §二） | 展開可見（⚠ PROVISIONAL：預設展開是撰寫組暫定） |
| **Level 2 來源／日期／provenance／freshness** | source、as_of、retrieved_at、freshness、Missing／failed reason、proxy／estimated | 預設收合或點開（⚠ PROVISIONAL：預設展開／收合是撰寫組暫定，客戶原文只規定 Level 3 預設收合） |
| **Level 3 developer diagnostics** | 供 QA／工程；**預設收合**；仍受下列禁曝險清單約束（⚠ 「Level 3 只准遮罩後診斷代碼」**比客戶原文嚴格**，屬 PROVISIONAL；客戶原文只禁清單所列項目） | 收合 |

**⛔ 不得一般曝光（任何層、任何 Human 面；⚠ 「Level 3 只准遮罩後診斷代碼」比客戶原文嚴格，PROVISIONAL）**：API key、secret、token、env var 名、raw exception、traceback、module path、credential detail、internal stack、OAuth credential（Sheet ID 只顯示末 6 碼）。一律過 `scrub_secrets`。

**⚠ PROVISIONAL (a)——Level 1 符號是「資料健康度面的別名」**（DEC-128 §四 (a)）：

| Level 1 符號 | 對映既有資料語意（DEC-124／Freeze §5.1） | 備註 |
|---|---|---|
| `✅ 正常` | OK | |
| `◷ 可能過期` | Stale（全站字樣 `⚠ 過期 N 天／⚠ 可能已過期`） | 別名僅限本面 |
| `◇ 資料未備` | Missing（全站字樣 `⬜ 資料未備`／`⬜ 資料未取得`） | 別名僅限本面 |
| `⛔ 來源不可用` | Unavailable（全站字樣 `🔴 來源目前不可用`） | **本面 `⛔`＝來源不可用（新義）**；Freeze §5.3 舊義「功能未接」在其他頁不變；色暫沿 Unavailable 紅 |
| `⬜ 尚未接線` | capability 尚未接線（全站字樣 `⬜ 尚未提供`） | 屬 capability 軸，**不是**資料語意第 6 態 |

> 不新增第 6 個資料語意態；不改全站字樣與 `text.py`／guard；全站統一需客戶另裁示。

## §6 Preview 控制的去向（FAKE／Real 切換、場景、帳戶）

- **不是正式產品資訊架構**；⛔ 不得讓它看起來像四頁的產品內容（⚠ PROVISIONAL (c)）。
- **去向**：開發／測試專用面——僅當 `?ui2_dev=1`（或等價的開發旗標）時顯示；明顯標示「非產品內容」；外觀與產品區隔（虛線框、等寬字）；不用 sidebar（與桌機 W-1 左導覽衝突）、不開第五導覽項。
- 預設道（無旗標）**0 個** Preview 控制（含 `ui2_account` 帳戶場景——它只屬開發面 FAKE，非 auth contract）；預設 feed＝FAKE 不變。session key 仍限 `ui2_` 前綴（`ALLOWED_UI2_WRITES` 不擴）。
- FAKE／Real 與場景維度（loaded／cold／missing／stale／unavailable／not_evaluated）、帳戶三態**保留供測試**，不屬 production presentation contract；cutover 前移除（`NUI2-PREVIEW-CONTROL-AXES` 不變）。
- 橫幅（「New UI2 Preview（fake data）」／Real 版）屬 Preview 標示，保留至 cutover（客戶 (11) A3）。
- ⚠ 未驗：AppTest `query_params` 在 Streamlit 1.56／1.59 的支援；Cloud 上 Streamlit Deploy／⋮ 按鈕可見性。

## §7 `🤖 OneBrain Outlook` 區塊

- **一般使用者只看適合人的精簡結果**：summary、outlook、signal consistency／可判定覆蓋資訊（依 Freeze §15.2 正式 contract）、主要 reasons、重要 counter-evidence、limitations。完整底層 evidence **不必**全部展示。
- 未啟用前（Stage G 前）＝ `🤖 OneBrain Outlook ⬜ 尚未提供`＋資料狀態 coverage chip（⛔ 寫成 confidence）。位置依 Wireframes §2.1／§2.2（今日主要風險之後、Primary 圖之前）。
- **OneBrain 不得**：創造 canonical data、自己重算正式投資規則、覆寫 System Action、覆寫 Risk Cap、建立第二套 action authority（Single Action Authority 不變）。
- **OneBrain 不是 UI Summary Bot**：它讀**完整 Decision Digest**（市場、標的、持股、portfolio、events、data health／freshness、deterministic rules、Risk Cap、System Action、counter-evidence、所有已核准正式 evidence），不是摘要畫面（§8）。Digest 是否補 data health／freshness 區塊＝需另案 Opus High Gate（`NUI2-DIGEST-DATAHEALTH-XREF`），本文件不授權。

## §8 Projection 邊界與「UI 移除不得刪」清單

```
Data / Sources → Validation / Normalization → Domain / Deterministic Logic
   → Risk Cap / System Action → Complete Evidence Layer
                                   ├─ projection A：Human UI ViewModel（簡化、Chart-first、關鍵 evidence、少量文字）
                                   └─ projection B：Decision Digest / OneBrain Context（完整 evidence、Missing、provenance、
                                      source、as_of、freshness、deterministic results、Risk Cap、System Action、
                                      counter-evidence、limitations、cross-page context）
```

**永久 invariant**：**UI 沒顯示的資料，不代表 OneBrain 不得讀；OneBrain 能讀的資料，也不代表 UI 必須全部呈現。** 兩個 projection 彼此不決定對方；現行 `PageVM`／`PageContext` 的 `context` 是「Human UI 全量」，**不是** Decision Context（Digest 由 canonical services headless 組裝，不由 UI2 VM sections 衍生，Freeze §14）。

**從 Human UI 移除時，⛔ 不得刪除（必須仍可供 OneBrain／Audit／QA 取得）**：adapter、canonical data、deterministic result、health result、provenance、source、as_of、retrieved_at、freshness、Missing／Stale／Unavailable、tests、RuleIDs、Risk Cap evidence、System Action evidence、Decision Context、未來 Digest input、OneBrain 未來需要的 evidence。

**機制**：只改 views 的 render policy（例如 `render_sections` 只畫 L1）；**不改** `PageVM`／`PageContext.sections` 內容、`real_canonical`、`real_feed`、`scenarios`。若需把「給人看的一句話」與「debug detail」分開成兩個欄位，屬 VM schema 變更，須先過 Gate。

| 離開 Human UI 的內容 | 必須保留於 | 上游 |
|---|---|---|
| 📊 為什麼／指標明細／原始表／工程診斷 | VM `sections`（why／detail／raw）；資料健康度（市場位階項 L2、工程 L3） | `real_canonical._market`＋`regime_spec(brief=False)`；L0 `regime_arbiter.*_EXPLAIN` 常數；`shared/macro_buckets.DangerSpec`（16 項） |
| 位階規則分支 id 等 provenance | `FieldVM.freshness.source`；資料健康度 L2 | `RegimeFact.source` |
| 工程原因句（尚未接線／PORT／Gate／Stage…） | `FieldVM.detail`／`state`／`capability`／`layer`／`status_text`（capability marker 是 `NUI2-CAPABILITY-MARKER-CUTOVER-ZERO` 的追蹤標的）；資料健康度 L3 | `real_canonical._R_*`、`scenarios.py` |
| 卡片 microtag as_of／source | `FieldVM.freshness` | `TwiiFact` |
| Risk Cap 無法判定的 evidence | `context_rows[risk_cap]` | `_risk_cap_row()` |
| 持股 rule IDs／80/20／停利／VaR 明細 | `sections[why/raw]`；Digest | `RULE_ID_ALLOWLIST` |
| 👤 Audit 內容 | `sections[digest/registry/fresh/sysinfo]`；Digest 本體 | `decision_digest_builder` |
| FAKE／Real 標記 | `PageVM.is_fake`／`scenario_id`／`banner_text` | `preview_feed`／`real_canonical` |

## §9 目前 Preview 與本 contract 的落差（implementation deviation 快照；非規格）

> 來源：兩份獨立 Gap Audit（2026-11-03；組 A 讀碼、組 B Playwright 24 態＋74 張截圖；皆單組、未驗 FAKE 非 loaded 場景、Safari／iOS、Cloud）。**本批不修**；由 `docs/BACKLOG.md` §5.1.26 的 P1～P6 修正。

- 四頁共有：L2／L3 expander（📊 3、🎯 2～3、💼 2、👤 4〔Audit〕）；Real 模式 expander 內可見約 437 字（📊）；首屏工程字樣（Real：📊 13／32、👤 27／39 個 jargon token，手機／桌機）；題號鷹架可見；Preview 控制 expander 畫在頁面內（四頁皆是）；Streamlit Deploy／⋮ 外露。
- 📊 缺 Primary 圖／VIX／國際圖槽（只能先放 honest `⬜` 槽）；🤖 OneBrain 槽位置偏後。🎯 缺「查看全部候選」入口。💼 CTA 位置偏後、缺持股表／建議水位卡；桌機 W-11 三 tile 未實作。👤 重複連線卡／CTA、桌機兩欄未實作。
- ⚠ 缺的圖／持股表／候選清單需要資料或 VM 欄位，**不是純 presentation**（只能先放 honest `⬜` 槽；功能留在 `NUI2-COMPONENT-GAP` 與各 PORT 項）。

## §10 取代對照表（文件→段落→狀態；歷史證據保留，原文不刪）

> 狀態：**KEEP**＝仍有效｜**SUPERSEDE**＝歷史保存、已不是 active｜**REMOVE**＝從現行規格移除（原文以橫幅／刪除線保留）｜**MIGRATE**＝內容仍需要、落點改到資料健康度或 Evidence／Digest。表內 S 號＝DEC-128 §二／`FINAL_UI_SUPERSEDE_MAP` §1。單組實查；**非窮舉保證**。

| 文件 | 段落 | 狀態 | S／備註 |
|---|---|---|---|
| `PROJECT_RULES.md` | §19.2 資料中心責任 | MIGRATE | S23 → 👤 資料健康度 |
| 〃 | §19.8 Missing 語意／DEC-124 五態三軸 | KEEP | 資料健康度符號為別名（PROVISIONAL a） |
| 〃 | §19.9／§19.4 Presentation vs Decision Logic 分離 | KEEP | |
| 〃 | §24.1 Presentation Contract 是呈現 SSOT | KEEP | 現行 SSOT＝本文件（見 §30） |
| 〃 | §24.2「第一屏三層答不出＝FAIL」 | SUPERSEDE | S21 |
| 〃 | §25.1 位階 | KEEP | 新 DEC 依位階第 4 點優先 |
| 〃 | §30（新） | KEEP（新增） | 永久規則 |
| `DECISIONS.md` | DEC-091 §一 Level 3；§二 憑什麼 | SUPERSEDE | S22 |
| 〃 | DEC-091 §二 資料健康小入口 | MIGRATE | S22／S23 |
| 〃 | DEC-072／DEC-076 §6 資料中心 | MIGRATE | S23 |
| 〃 | DEC-081 第 7 點「展開理由」 | SUPERSEDE | S23 |
| 〃 | DEC-081 第 7 點其餘互動完整性／Q4=C 資料中心分流 | KEEP／MIGRATE | S23 |
| 〃 | DEC-081 Q2-2 卡面客戶措辭 | KEEP | |
| 〃 | DEC-105 第 4 點／DEC-117 Q2 指路 | SUPERSEDE | S24 |
| 〃 | DEC-117 Q3／Q6／Q8 摺疊落點 | SUPERSEDE／MIGRATE | S25（Q6 退化句外露 KEEP） |
| 〃 | DEC-109 四 三層判準 | SUPERSEDE | S21（五問 KEEP） |
| 〃 | DEC-109 五／六／七 頁內摺疊／下沉／展開 | SUPERSEDE／MIGRATE | S26 |
| 〃 | DEC-109 十五～十七 | KEEP | invariant 前身 |
| 〃 | DEC-111／DEC-112（對 New UI2） | SUPERSEDE | S27（Legacy KEEP） |
| 〃 | DEC-121 Q2=B 查看全部／CSV | KEEP | 使用者功能 |
| 〃 | DEC-122 §9／§22／§25～§27 | SUPERSEDE／MIGRATE | S28 |
| 〃 | DEC-122 §0.1.3-6、§14、§15 | KEEP | |
| 〃 | DEC-123 (5)-6／(5)-8 | KEEP | audit presentation 落點改 👤 資料健康度／稽核面 |
| 〃 | DEC-124 | KEEP | |
| 〃 | DEC-127 | KEEP | |
| `PRESENTATION_CONTRACT_vNext` | §1、§2 Budget、§3 五問與 L1／L2 | KEEP | |
| 〃 | §3 L3 列；§4 摺疊入口；§5 下沉位置；§7；§8 第 2／5 點；§11 R7；§12.1 下沉；§12.2／§12.3 頁內 L2／L3 落點；§9 判準 (a)；§16 對應列；§17 落點欄 | SUPERSEDE／MIGRATE／REMOVE | S26 |
| 〃 | §8 Missing ≠ 0、§9、§11 R10、§12.4、§18 工程字樣 | KEEP | §18 擴及四頁全部 Human UI |
| `FINAL_UI_CONTRACT_FREEZE` | §0.1、§1、§5、§6～§9、§13～§15、§16.5 後半 | KEEP | |
| 〃 | §2.0 三層；§2.1～§2.4 L2／L3 列；§10 完整 calculation；§12.2 raw；§16.1～§16.4 摺疊線框 | SUPERSEDE／REMOVE／MIGRATE | S29 |
| 〃 | §16.5 「下沉」落點 | MIGRATE | 落點＝Evidence／資料健康度 |
| `NEWUI2_WIREFRAMES` | §0.1；§2.1／§2.2；§3.1～§3.3；§4.1／§4.2；§5.1／§5.2 的 L2／L3 `▸` 行 | REMOVE／MIGRATE | S30（版面其餘 KEEP） |
| 〃 | §1、§6、§9（W-1～W-11、DEC-127、W-4） | KEEP | |
| `FINAL_UI_CAPABILITY_MAP` | 落點欄 L2／L3（M06、M11～M17、T、H、E10 …） | MIGRATE | S31（能力不消失） |
| `NEWUI2_ARCHITECTURE_GATE` | §1.5 invariant、§4.2-6、§9 守衛 | KEEP | 加 projection 與 Preview 控制位置補註 |
| 〃 | §7 Preview strategy | KEEP＋新增 | S35 位置規則 |
| `NEWUI2_MIGRATION_CUTOVER_CONTRACT` | C2「L1／L2／L3」 | SUPERSEDE | S32 |
| 〃 | 新債 Preview 控制 cutover 前移除 | KEEP | |
| `NEWUI2_AUDIT_ACCEPTANCE_CHECKLIST` | §15 C2、§17 L2／L3 插隊、§19-2 | SUPERSEDE／MIGRATE | S32 |
| `NEWUI2_REUSE_MATRIX` | `src/ui2` 重用分類 | KEEP | 加 projection 補註（render policy 只改 views） |
| `NEWUI2_REAL_FEED_MAPPING` | M1b／M15～M17／E13／E14；§11-6；§11-9 | MIGRATE／REMOVE／SUPERSEDE | S33 |
| 〃 | 四頁 canonical 對映、跨頁一致性、白名單 | KEEP | |
| `docs/governance/UI_VISUAL_FIDELITY_GATE` | §1-3、V7 三層 | SUPERSEDE | S21（Decision Density KEEP） |
| `ME_PAGE_DRAFT_2026-10-25` | 資料健康→🩺 | SUPERSEDE（HISTORICAL） | S34 |
| Legacy New UI 時代文件：`PHASE3_SHARED_COMPONENTS_WIREFRAME`、`PHASE4_MARKET_PAGE_WIREFRAME`、`PHASE5_TARGET_PAGE_WIREFRAME`、`PRESENTATION_MIGRATION_PLAN`、`NEWUI_D25_A_FOUR_PAGE_SPEC`、`NEWUI_D25_UIT_WIREFRAME` | 頁內 L3 摺疊／「▸ 為什麼」／「查看依據」／16 項明細 | SUPERSEDE（對 New UI2；Legacy 凍結維持） | S26／S30 同源；頂端已加橫幅。其餘 Legacy 時代文件（`d25_wireframes/*.html` blueprint、`visual_fidelity/`、`phase4_market/`、`phase5_target/` 證據與量測檔、`INTERACTION_COVERAGE_MATRIX`、`MARKET_PAGE_DECISION_GATE`、`NEWUI_STAGE_B_DRAFT`、`NEWUI_D25_B／C／NAV1／PLAN／XVIEW`）**未逐檔加橫幅**：一律視為 Legacy 歷史證據，**對 New UI2 不是 active rule**（本表為準；見 DEC-128 §六「掃描範圍」） |
| `DECISION_DIGEST_CONTRACT_vNext` | §1 Data View ≠ Decision Context；A6 資料健康 | KEEP | (13)-8 要求 Digest 含 data health／freshness → `NUI2-DIGEST-DATAHEALTH-XREF`（另案 Gate） |
| `ONEBRAIN_ARCHITECTURE` | 「不把大量 raw 無差別塞 LLM」 | KEEP | Digest 是結構化，不是 raw dump |
| `BACKLOG.md` | `DH-DATA-CENTER`、`UIX-DATACENTER-CONTROLS`、`NEWUI-STAGE-D8-DATA-CENTER`、`NEWUI-STAGE-D10-SHARED-COMPONENTS`、`UIX-MKT-ENTRY-BUTTONS`、`NUI2-REALFEED-REGIME-L1-BRIEF` | MIGRATE／SUPERSEDE | S34 |
| 〃 | `NUI2-PREVIEW-CONTROL-AXES` | KEEP＋新增位置列 | S35 |
| `CLAUDE.md` §1.A-4 | 灰＝未載入、紅＝真錯誤 | KEEP（不動） | 與 `⛔ 來源不可用` 色張力見 PROVISIONAL (a) |

### 程式／測試（本批不改；列為後續 UI correction 批的待改清單）

見 `docs/BACKLOG.md` §5.1.26「測試改動清單」與 `tests/test_ui2_active_contract_docs.py::PENDING_UI_CORRECTION_TESTS`。Legacy 測試（`test_uim_market_page.py`、`test_p4_1_market_first_screen.py`、`test_p4_2_market_charts.py`、`test_p05_why_v2_cards.py`、`test_uim_revert_chain.py`、`test_nav1_revert_chain.py`、`test_batch_z54.py`）鎖的是 **Legacy-only**，不是 New UI2 active contract，**保留不動**。

## §11 PROVISIONAL 與未驗

- **PROVISIONAL（AI 總管暫定、客戶可推翻）**：(a) 資料健康度 Level 1 符號為別名；(b) 稽核面保留在 👤／選股條件與查看全部保留／指標危險度指路改向／全站一行資料狀態入口；(c) Preview 控制去 `?ui2_dev=1` 開發面；其餘見 DEC-128 §四。
- **INFERENCE**：題號鷹架可見文字應移除；工程字樣擴及四頁全部 Human UI（PC §18 擴大）。
- **未驗**：FAKE 非 loaded 場景截圖；Safari／Firefox／iOS／真機；Cloud 上 Deploy 按鈕；AppTest query_params 支援；本文件由單組撰寫（獨立 QA 見 `docs/vnext/NEWUI2_AUDIT_ACCEPTANCE_CHECKLIST_2026-11-02.md` §20，**未自勾**）。

## §12 怎麼用（給新 session）

1. 先讀本文件＋DEC-128；再讀 `docs/PROJECT_STATE.md` §59、`docs/HANDOFF.md` 最末 Safe Handoff。
2. 要施工 UI：只依本文件與 `docs/BACKLOG.md` §5.1.26 的 P1～P6（每批 ≤3 項）；舊文件的 L2／L3 `▸` 行一律不照做。
3. 遇到衝突：本文件／DEC-128 > 其他文件。若本文件與客戶原文（DEC-128 fence）不一致，以 fence 為準並修本文件。
4. 版面結構（新區塊版型、桌機兩欄）仍須先出文字線框草稿（`CLAUDE.md` §-1.5.D v3 §03-2 ①）；把壞畫面修回本 contract 不在此限。
