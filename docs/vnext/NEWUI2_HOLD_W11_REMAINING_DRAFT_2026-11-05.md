> **歷史／適用性引言（2026-11-07 抽出）**：本檔自 Draft PR #1027（head d3556ada） 原內容抽出保存（來源分支 `docs/newui2-hold-w11-draft-20261105`），抽出日期 2026-11-07。
> 此為歷史草案／研究材料，**不是現行施工依據**；現行方向以 DEC-142／DEC-146 與 `NEWUI2_TOP_FIVE_APPROVED_VISUAL_AND_SAFETY_GATE_2026-11-07.md` 為準。
> 補註：W-11 批 1 已合併（#1028）；§2 線框以桌機 rail 為前提，屬歷史基線，已被 DEC-142／DEC-146 取代；§8 為 DEC-141 的客戶 Q1~Q8 裁示來源，仍有效。

# 💼 持股 W-11 未完成部分：文字線框草稿＋資料契約草稿 v0.1（2026-11-05）

> **狀態：DRAFT／待視覺核准。docs-only。不授權任何施工**（不動 `src/`、`tests/`、JS、證據檔；核准前 ⛔ 寫任何 💼 UI code）。
> **用途**：DEC-138 要求「💼 完整 W-11 與 🎯 精選須先出線框草稿裁示」；本檔是 💼 這一半。客戶裁示後才登記新 DEC，之後才由 Claude Code 依核准版施工（DEC-139）。
> **誠實標示（§-2 規則 6）**：初稿由 AI 單組產出；**v0.2 已經第二組獨立複驗並依其發現修正 5 點**（見 §7），但複驗不保證窮舉。凡「全稱句」（「沒有」「只有」「無來源」）都是我 grep 後的觀察，列在 §7 作待驗事項，後續不得當既定前提。

## 0. 與其他文件的關係（先看這段）

| 對象 | 關係 |
|---|---|
| **PR #1022**（`docs/newui2-unified-blueprint-20261105`，ChatGPT 統一藍圖，open／draft／未核准） | **不重複、不取代、不矛盾**。#1022 §4「💼 持股」只有**段落級**描述（首屏／第二眼／需核准三行），**沒有 💼 的文字線框**；§7 把 💼 列為 **V-04**（「W-11 完整主圖／八欄表／資料日行／需處理單行及手機轉列」）。**本檔就是 V-04 的線框與資料契約補充**：只做差異／補充，並以「#1022 §4」「#1022 §7 V-04」「#1022 §2」引用其章節，不複製其全站 skin（V-01）、帳戶入口（V-06）等。#1022 未合併，若其章節編號日後改動，以其最終版為準。⚠️ **合併順序**：本批與 #1022 都在 `docs/BACKLOG.md` 末尾 append（重疊區），後合併者需先 rebase 並保留雙方補註（append-only，不得覆蓋對方）。|
| PR #1023／#1025（資料血緣／死碼唯讀盤點） | 檔案**無重疊**（它們只動 `docs/vnext/DATA_*.md`、`scripts/audit_*`、`tests/test_audit_*`）。本檔 §3 的「canonical 來源」是我自己 grep 現行 main 所得，**未引用**其結論；#1023 對「未接線≠死碼」的立場（`src/ui2/` 未接 Real 的圖槽為 NOT DEAD）與本檔一致。|
| DEC-138／139／140 | DEC-138：W-11 的 Primary 圖／⑤ 建議持股區間／持股表**尚未完成，不得宣稱整頁完成**；本檔不宣稱完成。DEC-139：設計歸文件、程式歸 Claude Code；本檔不含程式。DEC-140：資料分層清理是 ChatGPT 的特例任務，與本檔無交集；若日後同檔衝突，Claude 既有工作優先。|
| 既有有效規格 | `NEWUI2_WIREFRAMES_2026-11-02.md` §4.1／§4.2／W-5／W-6／W-11／§9（客戶 Q3，DEC-123）、`NEWUI2_UI_EXECUTION_SPEC_2026-11-04.md` §4、`NEWUI2_VISUAL_REFERENCE_AND_PAGE_EXPANSION_2026-11-04.md`（DEC-135／136）、`NEWUI2_ACTIVE_PRESENTATION_CONTRACT_2026-11-03.md`（DEC-128／129）。**衝突時以這些與 Active Contract 為準**。本檔不覆蓋任何已核准 W 點、風險語意、公式、資料來源。|
| 本檔不碰 | 全站 skin／亮暗（V-01，DEC-138 維持 Dark-only）、帳戶入口（V-06）、📊／🎯／👤 各頁、JS_V4、Auth、P6、OneBrain runtime、Risk Cap 數值。|

## 1. 現況盤點（origin/main `1548cc5b`；規格依據逐項附）

`#1020`（`481ae083`）已合併，含 💼 桌機首屏局部重排。以下以 main 程式為準（`src/ui2/views/hold.py`、`src/ui2/components/html.py::hold_l1_html`、`src/ui2/shell/css.py` `.ui2-h-l1`、`src/services/ui2/real_canonical.py::_hold`）。

| # | 項目 | main 現況 | 規格依據 | 狀態 |
|---|---|---|---|---|
| 1 | header 列：標題＋主 CTA「🚀 更新持股戰情」（disabled，原因保留） | 桌機已排成 header 列；手機維持堆疊 | Wireframes §4.2；W-11；DEC-123 | **已做** |
| 2 | 三 tile：Risk Cap／目前曝險／組合狀態 | 已做（桌機 3 欄；Risk Cap 恆 `⬜ 無法判定`、曝險恆 `⬜ 資料未備`、組合狀態 `⬜ 尚未提供`） | §4.2；Q1=A（Risk Cap 數值仍⬜） | **已做**（內容是誠實空槽） |
| 3 | 「組合名稱 · N 檔 · 資料日 · 判得出 M／N」行 | **無**（#1020 獨立 QA 偏離 ②） | §4.1 ①、§4.2 header 列；BACKLOG `NUI2-VISUAL-BATCH1` | **未做** |
| 4 | 今日需處理：**一行**（加·換·減·暫停加碼｜留｜⬜ N 檔尚未評估） | 現為「是否需要行動」＋「下一步」**兩列**（偏離 ③）；且動作欄恆 `⬜ 尚未提供（待系統動作整合）` | §4.2；W-5（Q2=A）；W-10（Aggregator 前維持 transitional） | **未做**（版面未做；內容受 Aggregator 未實作限制） |
| 5 | 🤖 OneBrain 持股摘要槽 | 已有槽，`⬜ 尚未提供` | §4.1／§4.2；DEC-129／136；Stage G | **已做**（空槽） |
| 6 | **Primary 圖**（W-11 線框：產業曝險／集中度圖） | **無** | §4.2；W-11；#1022 §4 寫「Portfolio Overview Primary（績效／benchmark）」——**兩份文字內容不同，見 Q2** | **未做（B 類，需裁示）** |
| 7 | **⑤ 建議持股區間**（卡標題沿用「建議持股水位（市場端）」） | **無**（UI2 無此卡；legacy `src/ui/views/page_hold.py::build_position_cap_card` 有） | §4.2；W-11（DEC-051／PQ-C6-3）；§9 | **未做（B 類，需裁示）** |
| 8 | **持股表**（桌機 L1 八欄；手機 4 欄＋每列展開） | UI2 只有一張占位卡「持股清單」`⬜ 尚未提供` | W-6；§4.1／§4.2；Execution Spec §4 | **未做（B 類，需裁示）** |
| 9 | 今日需處理**清單**（加碼列標「Risk Cap 無法判定」） | **無** | §4.1 第一屏下；Q1-4 | 未做 |
| 10 | performance／benchmark | **無** | §4.2 末行（`⬜ 資料未備`） | 未做 |

DEC-138 同時要求其餘限制保留；**本檔不關閉 BACKLOG／HANDOFF 任何 open 項**。

## 2. 文字線框

> 符號：`[空槽]`＝無正式資料時的誠實呈現（`⬜ …`＋原因），**不畫假走勢、假線、0**。所有數字僅為排版示意，**不是**行情、持股或建議。⑤ 與 Risk Cap 語意分離（W-11 §9：⛔ 把建議持股區間寫成已啟用的 Portfolio Risk Cap）。

### 2.1 桌機 1440×900 — 方案 A（推薦，對齊已核准 W-11）

```
┌ rail ┬──────────────────────────────────────────────────────────────────────────┐
│ 📊   │ 💼 持股                                                  [🚀 更新持股戰情]│ ← 已做（CTA disabled）
│ 🎯   │ 組合：<名稱> · 12 檔 · 資料日 <日期> · 判得出 10／12                      │ ← 【新】status 行（未做項 3）
│ 💼   │ ┌Portfolio Risk Cap─┐┌目前曝險───────┐┌組合狀態──────────────┐              │ ← 已做（三 tile）
│ 👤   │ │ ⬜ 無法判定       ││ ⬜ 資料未備    ││ 12 檔 · 判得出 10／12 │              │
│      │ └───────────────────┘└────────────────┘└──────────────────────┘              │
│      │ 今日需處理 3（加1·換1·減0·暫停加碼1）｜留 7｜⬜ 2 檔尚未評估   › 看清單      │ ← 【新】單行（項 4）；未接 Aggregator 時＝一行 `⬜ 尚未提供`
│      │ 🤖 OneBrain 持股摘要  ⬜ 尚未提供                                          │ ← 已做
│      │ ┌ Primary（唯一主視覺）──────────────────┐┌ 建議持股水位（市場端）──────┐ │ ← 【新】項 6／7
│      │ │ [空槽] ⬜ 資料未備                      ││ xx～yy%                      │ │
│      │ │ 一行 SPEC：頻率／單位／source／as_of     ││ 缺有效上限 → 「無法判定」     │ │
│      │ └─────────────────────────────────────────┘│ 分母：整體資產（市場端上限）  │ │
│      │                                            └──────────────────────────────┘ │
├──────┴──────────────────────────────────────────────────────────────── 第一屏底 ──┤
│ 今日需處理清單（加碼列標「⚠ Risk Cap 無法判定」；⛔ 當作無上限）                    │ ← 項 9
│ 持股表（L1 八欄）代碼｜名稱｜持股比例｜成本｜現價｜報酬｜策略(⬜ 未分類)｜System Action│ ← 項 8；外幣列 ⛔ 與 TWD 加總（DEC-101(1)）
│ performance／benchmark  ⬜ 資料未備                                                │ ← 項 10
└────────────────────────────────────────────────────────────────────────────────────┘
```
一屏內新增高度估計（**估計，未量測**）：status 行＋約 28px；單行需處理取代兩列約 −40～−50px；Primary＋⑤ 並排，Primary 保留 #1022 §2 要求的「維持高度」＝約 220～260px。1440×900 首屏仍容得下到 Primary，持股表在摺線下，符合 W-11。

### 2.2 手機 390×844 — 方案 A

```
┌ ☰ 44px 保留帶 ────────────────┐ ← DEC-137，不動
│ 💼 持股            [🚀 更新持股戰情]│ ← 既有（CTA 在標題列右側／堆疊維持現狀）
│ 組合：<名稱> · 12 檔 · 資料日 …   │ ← 【新】status 行（390 寬若放不下：名稱截斷省略，資料日不得截斷）
│ 判得出 10／12（2 檔 ⬜ 尚未評估）  │
├────────────────────────────────┤
│ Risk Cap   ⬜ 無法判定            │ ← 既有
│ 目前曝險   ⬜ 資料未備            │
│ 組合狀態   …                      │
│ 今日需處理 3（加1·換1·暫停1）留 7  │ ← 【新】壓成 1～2 行（取代「是否需要行動／下一步」兩列）
│  ⬜ 2 檔尚未評估      › 看清單     │
├──────────── 第一屏底（估） ─────┤
│ 建議持股水位（市場端）xx～yy%     │ ← 項 7（約 100px）
│ 🤖 OneBrain 持股摘要 ⬜ 尚未提供  │
│ Primary：[空槽] 收斂為「一行 ⬜ + SPEC」（手機不留大空框）│ ← 項 6；#1022 §2 允許小圖收斂；Primary 是否也收斂見 Q3
│ 持股精簡卡（4 欄：代碼｜名稱｜報酬｜System Action）│ ← 項 8；▸ 每列展開：比例 成本 現價 策略
└────────────────────────────────┘
```

**首屏高度預算（手機）**：
- ≥160px 守衛（`tests/ui2_viewport` 的「導覽餘裕」）**只量 📊 市場頁**（unavailable 場景現為 **162.5px**，餘裕僅 2.5px）；💼 **不在該守衛內**，但本批若動共用 shell／CSS 必須重量 📊，不得退化。
- 💼 現況（FAKE，`docs/vnext/newui2_batch3b/viewport_measurements.json`，git sha `fb466d15`，**早於 #1020**；#1020 只改桌機，手機像素宣稱不變）：頁標題頂約 100px；第一屏四問區塊約 146→475px（q4＝CTA 約 401→475）；L1 卡 grid 起於約 500px，高 97～139px；844px 視窗尚餘約 369px。
- 新增估計：status 行＋約 28～56px（1～2 行）；需處理壓縮 −35～−55px；⑤ 約 100px；故第一屏預算約**持平**，⑤ 落在摺線附近。**以上全是估計**，施工批必須以 `measure_viewport` 重量 390×844 並附 before/after。

### 2.3 方案 B（W-11 已被客戶 Q3 否決的備選；僅為完整列出）

桌機：Holdings Table 提到第一屏（status 行與三 tile 之下），Primary 圖與 ⑤ 下移到表之後。手機：持股精簡卡直接接在需處理之後。**客戶 Q3（2026-11-02）已選「依 Freeze，備選不採用」**——若要採用須重新取得裁示。

### 2.4 方案 C（A 的手機順序變體）

桌機同 A。手機改成「需處理 → **持股精簡卡** → ⑤ → Primary 空槽」，理由是 Primary 在無資料時只是一行空槽，讓真正有內容的持股卡更早出現。代價：偏離 §4.1「建議持股、OneBrain 在 Holdings 之前」的已核准手機順序，需重新核准順序。

### 2.5 Decision Gate 表

| 方案 | 優點 | 缺點 | 風險 | 總管推薦 |
|---|---|---|---|---|
| **A**（W-11 原案：status 行＋單行需處理＋Primary＋⑤ 在首屏，表在下） | 完全沿用客戶 Q3 已核准結構；只補三個已知缺口；新增元件都是現有規格已列的 | 目前 Primary 無資料，首屏會有一塊誠實空槽（桌機佔 ~220px 以上） | 手機首屏被 status 行與 ⑤ 擠高（待量測）；空槽被誤讀為「壞掉」→ 必須有明確 `⬜` 與原因 | **推薦** |
| B（表優先） | 持有者最想看的列表更早出現 | 已被 Q3 否決；表尚無資料（見 §3，`holdings_table` 無 UI2 來源）→ 第一屏變一張空表 | 與已核准契約衝突、需重核准 | 不採 |
| C（手機順序變體） | 手機有內容的區塊更靠前 | 偏離已核准手機順序 | 順序變更需重核准；與 #1022 §4 描述順序不一致 | 不採（無資料前沒有收益） |

**推薦理由**：目前 💼 在 UI2 幾乎全是空槽（見 §3），版面順序選哪個都不會讓資料變多；A 是唯一不需要重新核准結構、且可以逐項（≤3 項／批）施工的方案。

## 3. 資料契約草稿

### 3.0 共通規則（沿用，不新造）

- 三軸：`FieldState`（OK／Missing／Stale／Unavailable／Not Evaluated）、`CapabilityState`（PROVIDED／NOT_PROVIDED）、`JudgementState`（UNDETERMINABLE），見 `shared/ui2_contract/models.py`；DEC-124：三軸互斥、不混查字樣表。
- `missing ≠ 0 ≠ 中性 ≠ HOLD ≠ 安全`；非 OK／STALE 態 `value_text` 必為 `None`。
- **Risk Cap 與 System Action 只呈現、不計算**：Risk Cap 數值仍 ⬜（Q1=A），動作欄待 System Action Aggregator（W-10）；VM 不得創造動作（`vm_common.PAGES_ACTION_FROM_AGGREGATOR_ONLY` 含 `p4_hold`）。
- **OneBrain 讀完整 Decision Digest，不讀 UI 卡片、不 Top-N 截斷**（DEC-129／136）。持股表手機只顯示 4 欄是**呈現壓縮**，VM／canonical／Digest 輸入必須保留全部列與全部欄（含 `lots`／`avg_price`／成本／現價／各燈）。
- 不提新外部來源。
- ⛔ 不得從 UI2 feed 呼叫 `get_holdings`、`get_account`、`get_allocation`（寫 `_alloc_*` session）等（`real_feed.py` G2F 檔頭明列）。

### 3.1 逐區塊欄位

「現有 canonical」＝我在 main 上 grep 到的位置；**UI2 目前能否取用**欄分兩層：(a) 有無 canonical 實作；(b) UI2 feed 規則是否允許（G2F／G2／G4 導入限制）。

| 區塊 | ViewModel 欄位（草稿） | 三軸／狀態 | 現有 canonical 來源（grep 結果） | UI2 能否取用 | 資料日／stale／missing 表現 |
|---|---|---|---|---|---|
| **status 行：組合名稱** | `portfolio_name: str`（FieldVM `value_text`） | Capability（NOT_PROVIDED 至 Auth／綁定契約具備）；之後 Field | `src/services/holdings_service.py::HoldingsResult.portfolio_name`（L3，需 Google 綁定與選定 `SELECTION_OK`） | **否**——需登入；UI2 目前**尚無正式 auth contract、僅有占位**（#1022 §3「目前正式登入能力尚無 contract，維持 capability 占位」；`src/services/ui2/vm_common.py::account_from_canonical` 的文案「登入與 Sheet 操作尚未開放」），feed 禁呼叫 `get_holdings` | `⬜ 尚未提供（登入與 Sheet 操作尚未開放，同 `vm_common.account_from_canonical` 既有文案）`；**不得**用 FAKE／query 假裝；也不得顯示 Sheet ID 全碼 |
| **status 行：N 檔** | `held_count: int \| None` | 同上 | `HoldingsResult.held`（`held=True` 的列）；空清單是有效結果≠故障 | 否（同上） | 未綁＝`⬜ 尚未提供`；已綁且空＝「0 檔」是有效值（灰），**不得**混為同一態 |
| **status 行：資料日** | `portfolio_as_of: date \| None` | Field（Missing 預設） | **查無「組合層」資料日**：只有逐檔價格 as_of（`dividend_station_service._price_asof_fields`，列內 `_detail`）。「最舊／最新」哪個代表整組是**新資料定義** | **否，且需客戶確認**（Q4；legacy 已有 DEC-102 逐檔分組先例） | 確認前一律顯示 `⬜ 資料日未提供`（`TEXT_ASOF_MISSING`）；⛔ 用抓取時間或今日頂替 |
| **status 行：判得出 M／N** | `judged: int`、`total_lights: int`、`unjudged_rows: int` | JudgementState／coverage；**⛔ 寫成可信度／機率**（§4.1） | 計算在 legacy **L4／L5**：`src/ui/render/station_cards.py::aggregate_judged`／`tally_states` 與 `src/ui/views/page_hold.py::load_station`；底層列來自 L3 `dividend_station_service.get_station_rows` | **否**——UI2 禁 import `src.ui.*`；L3 尚無等價純函式（需先下沉 L3，屬程式批） | 分母動態（ETF 8 盞／個股 3 盞），0／0＝「無可算」≠可信；N 檔未評估＝`⬜ 尚未評估` |
| **今日需處理（單行）** | `act_add`、`act_swap`、`act_reduce`、`act_pause_add`、`stay_n`、`unassessed_n`（皆 `int \| None`） | Field + Capability；Aggregator 前＝NOT_PROVIDED | 動作 id：`src/compute/etf/dividend_station.py`（`ACTION_PAUSE_ADD="pause_add"`）；digest：`dividend_station_service.build_station_digest`；`shared/decision_digest_rules.py::RULE_ID_ALLOWLIST`。**跨頁彙整（W-5／W-10）的 Aggregator 尚未實作**（`vm_common.aggregator_pending_field`） | **否** | Aggregator 前：維持 `⬜ 尚未提供（待系統動作整合）`（現況）。「今日無需調整」只在計入組皆 0 **且** 0 檔未評估；⛔ 未評估混進「無需調整」；⛔ 缺動作＝全部續抱 |
| **⑤ 建議持股水位（市場端）** | `range_text: str`、`posture: str`、`cap_name: str`、`risk_cap_disclosure`、`has_risk_cap: bool` | Field／Judgement（缺有效上限＝`無法判定`，字串逐字取 `risk_cap_gate`） | `allocation_service.get_allocation()` → `shared/allocation_decision.AllocationDecision`（`final_lo/hi`、`range_text` 由 L3 供給）；legacy 讀法見 `page_hold.build_position_cap_card` | **現有 feed 不可**：`get_allocation()` **寫入** `_alloc_decision_cache` 等 session key，違反 `real_feed.py` 唯讀規則。唯讀替代 `get_macro_regime(strict=True, require_valid_risk_cap=True)` 回傳含 `exposure_limit_pct`，但 `real_canonical` 目前明文**不收**該欄（Risk Cap 恆 ⬜）。→ **要不要開這條路屬 Risk Cap 語意決策，不是 UI 決策**（Q5） | 位階契約**無 as_of**（`real_canonical` 檔頭）→ `⬜ 資料日未提供`；⛔ 與 Portfolio Risk Cap 並排或互相引用；⛔ 卡面放 DEC 編號；標題固定「建議持股水位（市場端）」 |
| **Primary 圖** | 取決於 Q2：A) `industry_weights: tuple[(industry, weight_pct)]` + `unclassified_n`；B) `perf_series`／`benchmark_series` | Field（Missing 預設） | A) `src/compute/risk/concentration.py::compute_industry_concentration`（L2 純函式；查不到產業別不歸桶）+ L3 `stock_grp_service.get_industry_category`（取產業別）；B) `src/compute/etf/etf_calc.py::compute_portfolio_vs_benchmark`（L2）；`portfolio_deep_service` 檔頭自陳**不做匯率換算**。兩者的輸入皆為持股列→**同樣需要登入後的持股** | **否**（輸入＝持股，無 auth） | **無可被 UI2 取用的來源→僅能誠實空槽**：`⬜ 資料未備`＋原因，維持高度（桌機）；⛔ 假走勢／假橫條／0 長度；⛔ 以「無持股」冒充「0%」。一行 SPEC：頻率／單位／source／as_of／缺值規則 |
| **持股表** | 每列：`ticker`、`name`、`held`、`asset_kind`、`asset_class`、`lots: float\|None`、`avg_price: float\|None`、`weight_pct`、`cost`、`price`、`return_pct`、`strategy_class`、`system_action`；外幣列標幣別 | 逐格 FieldState；`lots`／`avg_price` 缺＝`None`（**觀察清單列本來就無**，不是 0） | `holdings_service.get_holdings()`（列形狀見其 docstring）→ `dividend_station_service.get_station_rows`／`compute_portfolio_totals`（含張→股→元換算，`SHARES_PER_LOT`）；策略分類 `src/data/portfolio/strategy_class_reader.py`；System Action 待 Aggregator | **否**（需登入；且 System Action 無來源） | 無列＝`⬜`＋原因（未綁／空／登入逾時三種指路句不同，沿用 legacy `HoldingsReadout` 分流）；外幣列 ⛔ 與 TWD 加總（DEC-101(1)）；報酬缺價＝`⬜`不填 0；`⬜ 未分類` 為策略欄既有字樣 |
| **今日需處理清單** | 列：分支原名（加／換／減／暫停加碼…）＋標的＋「⚠ Risk Cap 無法判定」旗標 | 同需處理 | 同需處理；`dividend_station_service.flag_take_profit`、`build_switch_advice` | 否 | 同需處理 |
| **OneBrain 持股摘要** | 保持現有槽 | Capability NOT_PROVIDED | 無（Stage G；`Digest` 完整 coverage 稽核獨立：`ONEBRAIN_FULL_EVIDENCE_COVERAGE_AUDIT_PLAN_2026-11-04.md`） | 否 | `⬜ 尚未提供`；⛔ 現行 Gemini 直呼路徑 |
| **performance／benchmark** | 同 Primary 方案 B | Field | 同上 | 否 | `⬜ 資料未備` |

### 3.2 結論（單組、待驗）

0. **補正（獨立複驗發現）**：repo 內**存在不經瀏覽器登入的持股讀取路徑**——`src/data/portfolio/gsheet_sa_reader.py`（L1，headless Service Account）的 `load_sa_credentials()`／`read_holdings(sheet_id, creds_dict)`／`read_watchlist(sheet_id, creds_dict)`；憑證與 Sheet 來自環境變數 `GCP_SERVICE_ACCOUNT_JSON`、`PORTFOLIO_SHEET_ID`、`STOCK_PORTFOLIO_SHEET_ID`；無 streamlit、不寫 session；使用者是 `scripts/push_holdings_daily.py` 與 `.github/workflows/push_holdings_daily.yml`（每日推播 cron）。**但 UI2 不可直接取用**：(a) 它是 L1，UI2 守衛 G2F（real feed 禁 `src.data`）與 G4（UI2 獨立性）都不允許；(b) 需要 secrets，Streamlit Cloud 不一定配置，且 SA 需被分享 Sheet；(c) 涉及個人持股隱私，且繞過尚未定案的 Auth Gate（誰的持股、誰能看）。故下面「無來源」一律讀作「**無可被 UI2 直接取用的來源**」，而非「repo 內完全沒有不登入的讀法」。是否開放此路徑或日後的 snapshot 檔作持股來源 → **Q8**。
1. **現行 repo 有對應的 canonical 計算**（L3 `holdings_service`／`dividend_station_service`／`allocation_service`、L2 `concentration`／`etf_calc`），但**全部以「登入後的持股」為輸入**（SA 路徑見上方第 0 點，UI2 不可直接用）；UI2 目前**尚無正式 auth contract**，Real feed 也明文禁止呼叫持股／帳戶／會寫 session 的函式。
2. 因此在 Auth 契約與 feed 規則改變前，💼 的 Primary 圖、持股表、需處理、status 行 **「無可被 UI2 直接取用的來源→僅能誠實空槽」**；線框與 VM 欄位可以先定，**但施工只能是「版面＋空槽＋欄位契約」，不是接資料**。
3. 少數「與持股無關、只與市場有關」的候選是 ⑤（市場端），其唯讀取用方式需 Q5 裁示。
4. 另有兩個**要先下沉才可取用**的點：判得出 M／N（目前在 legacy L4／L5）、跨頁 Aggregator（尚未實作）。兩者是程式批，不在本草稿。

## 4. 需客戶裁示的問題（商業語言＋推薦）

| # | 問題 | 推薦 | 理由 |
|---|---|---|---|
| **Q1** | 版面用哪一案？（A 原案／B 表優先／C 手機順序變體） | **A** | 已是客戶 Q3 核准結構；B／C 需重核准且目前沒有資料可讓它們更好 |
| **Q2** | Primary 圖要畫什麼？原線框寫「產業曝險／集中度圖」；#1022／Visual Reference 寫「績效／benchmark」。 | **產業曝險／集中度**（沿 W-11 已核准線框；績效／benchmark 另放 L1 之下的 `⬜ 資料未備` 行） | 兩者都需持股資料，但前者算式在 L2 已存在（`compute_industry_concentration`），後者受 `portfolio_deep_service` 自陳「不做匯率換算」限制；沿用已核准文字少一次重核准 |
| **Q3** | 手機上，Primary 無資料時是否收斂成**一行**空槽（#1022 §2 對「小圖」允許，對 Primary 要求維持高度）？ | **手機收斂為一行、桌機維持高度** | 手機垂直空間貴；兩者都明確標 `⬜` 與原因，不假裝是圖 |
| **Q4** | 「資料日」要怎麼呈現？**legacy 已有客戶核准先例（DEC-102，XV-ASOF，2026-10-28）**：`src/ui/views/page_hold.py` 約 2177–2232 行（`_hold_asof_items`／`_price_asof_facts`、常數 `HOLD_ASOF_*`）逐檔取 `PAL.PriceAsOf`（`shared/price_asof_label.py`），以**字樣分組**：嚴格過半者為「多數字樣（N 檔）」，其餘以「例外字樣＋代號清單」另列；無過半則寫「各檔不一致，逐組列在下面」。程式**沒有**算出單一組合日期（觀察所得；我未在 DEC-102／線框文字中找到「刻意不採」的明句）。選項：①沿用 DEC-102「多數＋例外分組」／②「最舊一檔價格日」單一日期／③僅顯示 `⬜ 資料日未提供`。 | **①沿用 DEC-102 分組**（**需客戶確認**把它延伸到 UI2 💼 status 行）；**確認前一律顯示 `⬜ 資料日未提供`**。⚠️ 初稿曾推薦「最舊一檔」——**與已核准的 DEC-102 設計不同**，已撤回該推薦 | 分組已被客戶核准且逐檔真值可追溯；單一「最舊」日期是新資料定義，會把「多數是今天、一檔是上週」壓成一個日期而丟掉例外資訊（為何 DEC-102 不用單一日期是**我的推測**）；status 行篇幅有限，可能只放多數字樣＋「另有例外」指回下方，細節待線框確認 |
| **Q5** | ⑤「建議持股水位（市場端）」要不要在 UI2 💼 先接上？現有唯讀路徑會碰 Risk Cap 欄位（`exposure_limit_pct`），而 UI2 現在是刻意不收。 | **先不接，維持空槽 `⬜`**；Risk Cap 數值 Gate（Q1=A 的後續）定案後再一起接 | 避免在 Risk Cap 未定案前，把「建議區間」讀成「已啟用上限」（W-11 §9 明文禁止） |
| **Q6** | 「今日需處理」在 Aggregator 未完成前，是維持兩列 `⬜`（現況）還是先合成**一行 `⬜ 尚未提供`**？ | **合成一行**（只改版面，內容仍 `⬜`） | 對齊線框、省 ~40px；不增加任何動作邏輯 |
| **Q7** | 持股表在沒有登入資料時，是顯示一張**空表頭＋原因**，還是維持現在一張占位卡？ | **空表頭（欄名可見）＋原因句** | 讓客戶一眼看到欄位結構，不會誤以為少了功能；不畫假列 |
| **Q8** | 是否允許 UI2 💼 日後以 **Service Account 路徑**（`gsheet_sa_reader`）或**由 cron 產出的 snapshot 檔**當持股來源？（涉及隱私、secrets、Auth Gate 與「誰的持股」） | **先不開放，維持誠實空槽**；待 Auth contract 與隱私模型定案後再議 | 避免繞過登入把個人持股暴露給未驗證的瀏覽者；SA 路徑是單一使用者 cron 設計，非多使用者 Web 契約 |

## 5. 不在本批（B／C 類，需另行 Gate）

- **B（需另批視覺裁示）**：全站 skin（V-01）、手機帳戶 popover 與抽屜互斥（V-06）、🎯 精選線框（DEC-138 同列的另一半）。
- **C（需 High／獨立 Gate）**：Auth 真接線與持股讀取契約、System Action Aggregator、Risk Cap 數值 Gate、OneBrain Digest coverage／runtime、P6 資料健康度、把判得出 M／N 下沉 L3、組合層資料日定義。
- 本草稿**不產生**任何 `src/`／`tests/`／JS 變更；核准後的第一個施工批建議上限 ≤3 項（建議：①status 行空槽＋單行需處理、②⑤ 空槽卡、③持股表空表頭＋Primary 空槽），每批附 390×844／1440×900 前後圖與獨立 QA。

## 6. 驗收要點（供日後施工批引用，非本檔授權）

- 手機 390×844 無水平捲動；📊 導覽餘裕 ≥160px 守衛不退化（量測重跑）；💼 首屏高度 before/after 記錄。
- 狀態互斥守衛：Capability／Field／Judgement 字樣不混；`missing≠0`；Risk Cap 恆 `⬜ 無法判定`、動作欄不由 canonical 提供（既有守衛 `test_ui2_guards`）。
- Evidence 保留守衛：VM 不因呈現壓縮而刪欄（Presentation Compression ≠ Information Loss，DEC-128／129）。
- Visual Fidelity 與 Evidence／Digest coverage **分軌驗收**（DEC-136）。

## 7. 已知限制與待驗事項（誠實標示）

0. **本草稿已經第二組獨立複驗，本版（v0.2）的 5 項修正（SA 讀取路徑、DEC-102 資料日先例、auth 引用、合併順序、用詞）皆來自該複驗。** 但**複驗不等於窮舉**：以下觀察仍須視為待驗。
1. **初稿單組產出，修正版僅經一組複驗，未窮舉。** 下列全稱觀察皆為 grep 結果，不得當既定前提：
   - 「UI2 現無任何**可直接取用**的持股／Primary／持股表來源」（複驗已發現漏列 `gsheet_sa_reader`，故此句也可能仍有遺漏）——我只搜了 `src/data`、`src/services`、`shared/ui2_contract`、`src/services/ui2`、`src/ui/views/page_hold.py`、`src/compute/risk`，**未窮舉**其他目錄。
   - 「組合層沒有資料日定義」——只在 `holdings_service`／`dividend_station_service`／`page_hold.py` 搜過。
   - 「Aggregator 未實作」依 `vm_common.py` 與 `real_canonical.py` 檔頭文字，未檢查全 repo 是否另有實作。
2. 手機高度數字來自 **FAKE** 量測（`fb466d15`，早於 #1020）；「新增高度」皆為估計。
3. #1022 是未合併 draft，其章節引用以其當時內容為準（head 為 2026-11-05 取得的版本）。
4. 未驗：真機／Streamlit Cloud／iOS／Firefox／WebKit／Light theme（DEC-138 維持 Dark-only）。非 pixel parity（參考圖不在 repo）。
5. 本檔不是視覺稿；ASCII 僅示意區塊順序與位置。

## 8. 客戶裁示 Q1~Q8 與施工授權範圍（2026-11-05；只追加，§1~§7 原文未動）

> **DEC-141**（`docs/DECISIONS.md`）。決策者：客戶。本節把 §4 的 Q1~Q8 轉成「核准條件」。**核准的是純版面施工；不授權任何正式資料接線。**

| Q | 客戶裁示 | 核准條件（施工須遵守） |
|---|---|---|
| Q1 | **A** | Primary 與 ⑤ 建議持股區間在上、持股表在下；手機沿用已核准順序（不採 B／C） |
| Q2 | 產業曝險／集中度為 Primary 主圖 | 績效／benchmark 放次要區，**不取代** Primary |
| Q3 | 手機無資料時 Primary 收成**一行**明確空槽；桌機維持預定高度 | 施工後**重新實測**手機首屏（390×844） |
| Q4 | 資料日沿用 DEC-102「多數＋例外分組」 | ⛔ 不得取最舊一檔／今日／抓取時間冒充；未接線前顯示 `⬜ 資料日未提供`；⛔ 不授權新增組合層日期計算或來源 |
| Q5 | ⑤「建議持股水位（市場端）」**僅空槽** | ⛔ 不讀 Risk Cap 數值、⛔ 不呼叫會寫 session 的服務、⛔ 不得讓人誤以為已有投資上限 |
| Q6 | 「今日需處理」合為**一行** | Aggregator 完成前維持 `⬜ 尚未提供`；⛔ 不計算動作、⛔ 不顯示「今日無需調整」 |
| Q7 | 持股表：欄名＋原因 | 桌機八欄結構、手機四欄＋展開欄位；無登入資料 ⛔ 假列／假成本／假報酬；⛔ 把未登入判為持股 0 檔 |
| Q8 | 不開放 `gsheet_sa_reader`／cron 快照／Service Account 接入 UI2 | 維持誠實空槽 |

**施工授權範圍**：僅「版面／欄位結構／空槽」。⛔ 不含資料接線、Auth、Risk Cap、System Action、OneBrain、Digest、正式資料來源、投資公式。欄名只取自 Wireframes §4.1／§4.2／W-6 既有定義；規格未明定欄名即停手回報。**W-11 只有通過施工與獨立 QA 驗收者才能標完成**；空槽施工完成 ≠ W-11 完成。
**本 PR（#1027）維持 draft，不合併**；合併前須處理與 #1022 在 `docs/BACKLOG.md` 末尾 append 的衝突（另行處理）。
