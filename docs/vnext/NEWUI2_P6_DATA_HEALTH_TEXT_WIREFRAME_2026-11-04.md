# New UI2 P6 文字線框＋資料欄位盤點（👤 我的／資料健康度）— 2026-11-04

> **已過獨立 QA，待 ChatGPT／客戶線框審查；本輪不授權施工（尚未取得客戶核准）。** 依客戶 2026-11-04 指示 (20)（摘要逐條，見 scratchpad `customer_directive_2026-11-02.md` 第 (20) 段；正式落盤由總管統一同步）：本輪只授權「P6 線框＋資料欄位盤點」，**不授權 P6 或導航程式施工**，停在線框驗收點。
> 本文件**不是**新的 Decision、**不是**第二套產品憲法、**不是** Auth／Real Feed／OneBrain／Digest 授權。基準：`origin/main` `801fe60e`（含 DEC-134）。測量日 2026-11-04（`data_cache/metadata.json` 等會漂移的量測值一律標日期）。
> 效力順序（衝突時）：客戶原文（DEC-081／117／119／122／124／127～134 fence）＞ `NEWUI2_ACTIVE_PRESENTATION_CONTRACT_2026-11-03.md`（下稱 Active Contract）＞ `NEWUI2_UI_EXECUTION_SPEC_2026-11-04.md` ＞ 本文件。
> **驗證方式（據實）**：欄位盤點以**讀碼**為準（逐檔 grep／讀原始碼，標出處「檔案:行」）；僅執行一次 `AppTest.from_file("app_ui2.py")` 取 👤 現況 DOM。**未**對各 service 實際呼叫、**未**量測任何 px、**未**截圖。「未驗」寫在 §I。
> **本文只提線框與盤點，不新增客戶裁示、不升格 Active Contract §11 的撰寫組暫定三項（Level 1／2 預設展開收合、Level 3 只准遮罩後診斷碼、Unavailable 顏色）——它們在 §H 以 A／B 並列、標推薦與理由，待客戶裁示。**

---

## A. 現況（P1～P3 後的 👤 我的；基準 `801fe60e`）

**取得方式**：`AppTest.from_file("app_ui2.py")` 預設頁（FAKE）→ `ui2_page=p4_me`，逐個 `st.markdown` 取文字；程式讀點 `src/ui2/views/me.py:16-20`（`render`）、`src/ui2/views/_page.py`（`render_sections`／`SHOWN_FOLDS`）、`src/services/ui2/scenarios.py:131`（`_me_sections`）、`src/services/ui2/real_canonical.py:407`（`_me`）。

### A.1 手機／桌機同一單欄順序（桌機兩欄 P6 ① 與 Account Area P7 皆尚未施工；rail／抽屜現況不在本檔範圍）

| # | 現況元素（由上而下） | 出處 |
|---|---|---|
| 1 | 單行標示「示意資料（FAKE）」（Real 為 Real-data 單行標示） | shell；P1 |
| 2 | 頁首「👤 我的」 | `render_title` |
| 3 | `first_screen`：連線狀態／連線異常／下一步（冷啟動各為 `⬜ 尚未載入`＋原因句）＋主 CTA（signed_in 為「切換 Sheet」，disabled，原因「登入與 Sheet 操作尚未開放」） | `first_screen_html` |
| 4 | 帳戶動作列「帳戶管理（示意狀態：已登入）」：切換 Sheet／選組合／選觀察清單／Google 登出（皆 disabled）＋**同一原因句再出現一次** | `account_actions_html`（`html.py:314`）；僅 FAKE（Real `account=None`） |
| 5 | 4 張資料卡：Google／Sheet（末 6 碼）／組合／觀察清單（各自 chip＋原因句＋`⬜ 資料日未提供`） | `render_cards` |
| 6 | 「一般設定」L1：Strategy／Notifications／Display preference 皆 `⬜ 尚未提供` | `_me_sections` |
| 7 | 兩個預設收合 expander：「Audit：Decision Digest」「Audit：Rule Registry（唯讀）」（內容為 `⬜ 尚未提供` 占位） | `SHOWN_FOLDS`（`_page.py:54`）；DEC-130 (b) |
| — | **不渲染（VM 完整保留）**：「Audit：Data Freshness」「Audit：System Information」 | DEC-132 一.1、`NUI2-P3-FRESH-SYSINFO-HIDDEN`（BACKLOG §5.1.26） |

**Real 模式現況**：`real_canonical._me()`（`real_canonical.py:407`）全部欄位為 `⬜ 尚未提供`（Capability；原因「需登入 Google 才能顯示，目前尚未開放」），無 `account`（⛔ 假裝 signed-in／out）。

**現況的三處重複（對應 BACKLOG P6 ③「移除重複連線卡／CTA」）**：① 連線狀態一句與 4 張卡說同一件事；② 「切換 Sheet」同時是主 CTA 與動作列第一顆；③ 原因句「登入與 Sheet 操作尚未開放」出現兩次。

**被隱藏、等 P6 承接**：Data Freshness、System Information（DEC-132）；L0 市場位階**完整說明**（`shared/regime_arbiter.py:153 NOT_LOADED_PENDING_BREADTH_EXPLAIN`、`:120 UNEVALUATED_BREADTH_EXPLAIN`）——VM `why` section 仍逐字保留，Human UI 只畫一句 `REGIME_SEE_WHY`（`real_canonical.py:176`），過渡期限制見 Active Contract §11、BACKLOG `NUI2-P1-L0-EXPLAIN-WITHHELD`。

---

## B. 文字線框

### B.0 設計原則（只引用既有元件；不自創視覺系統）

1. **區塊順序（Active Contract §3.4／Execution Spec §5）**：帳號與資料來源（連線狀態＋唯一主 CTA）→ 一般設定 → **資料健康度** → 稽核（Digest Viewer／Rule Registry，預設收合）。桌機依 Wireframes §5.2 保留「一般設定｜稽核」並排，資料健康度整列在下（H-6）。
2. **登入狀態與 CTA 不重複**：👤 內**只有一個**連線狀態區與**至多一個**主 CTA；登入按鈕本體在殼（桌機 rail Account Area／手機抽屜），👤 不再放第二顆登入鈕（H-5，詳 §E）。
3. **兩軸分離（DEC-130，硬規則）**：每列有獨立的「狀態」（Data State，只有五態）與「接線」（Capability）兩欄；`⬜ 尚未接線` **只在「接線」欄**；尚未接線列的「狀態」欄寫「（不適用）」，⛔ 填五態中任何一個。Not Evaluated 另以既有字樣（`⬜ 尚未評估`／`⬜ 尚未載入`／`⬜ 尚未定義`）呈現，不併入 `⬜ 尚未接線`。
4. **Level 1 符號是資料健康度面的「顯示別名」**（Active Contract §5.1）：`✅ 正常`＝OK、`◷ 可能過期`＝Stale、`◇ 資料未備`＝Missing、`⛔ 來源不可用`＝Unavailable；VM 的 `status_text` 與全站字樣（`⚠ 過期 N 天`／`⬜ 資料未備`／`🔴 來源目前不可用`）**不變**，別名只在本面的 view 層轉換（`shared/ui2_contract/text.py:79 ALLOWED_STATUS_PREFIXES` 與 guard 不動）。
5. **色調**（沿 `ChipTone` 四族，`src/ui2/components/html.py:20 STATE_TONE`）：Stale＝Warning 琥珀；Unavailable＝Danger 紅（顏色屬 Pending，H-4）；Missing／Not Evaluated／Capability＝Neutral 灰；OK 的 `✅ 正常` 建議用 **Neutral／Info 外觀＋✅ 文字**，不用 Positive 綠，避免與投資狀態 Positive 混讀（Wireframes §0.3：「`✅ 可讀`〔資料狀態〕與 Positive 投資狀態文字必須可區分」）。顏色不是唯一載體，文字同列。
6. **不外露**：API key、secret、env var 名、raw exception、traceback、module path、credential detail、internal stack；Sheet ID 只顯示末 6 碼；一律過 `shared/secret_scrub.py:1329 scrub_secrets`。靜態來源註冊 `DATA_REGISTRY`（`src/data/core/data_registry.py:68`）的 `requires_key`（＝env var 名）與 `ping_url`、`endpoint` **不得**進任何 Human 層（Level 3 亦限遮罩後識別碼，H-8）。
7. **新增元件僅兩個**（其餘全沿用）：「資料健康度兩欄列」與「總覽一行」。它們屬新版型，**本線框即其草稿 Gate**（`CLAUDE.md` v3 §03-2 ①）。

### B.1 區塊順序總表

| # | 區塊 | 手機 390 | 桌機 1440 | VM 來源（P6 後；VM 一律保留） |
|---|---|---|---|---|
| 1 | 頁首「👤 我的」 | 單欄 | 主內容區頂 | `PageVM.title` |
| 2 | 帳號與資料來源（連線狀態＋4 項摘要＋唯一主 CTA／指引；連線異常、下一步**僅有異常或待辦時**出現） | 單欄 | 整列（full width） | 既有 `first_screen`＋`cards`（render policy 去重，**不刪 VM**） |
| 3 | 一般設定（Strategy／Notifications／Display preference，沿現況 `⬜ 尚未提供`） | 單欄 | 左欄 | 既有 `settings` section |
| 4 | 稽核：Decision Digest Viewer、Rule Registry（預設收合，沿現況） | 在資料健康度**之後** | 右欄（與一般設定並排，Wireframes §5.2） | 既有 `digest`／`registry` |
| 5 | **資料健康度**：總覽一行 → Level 1 兩欄列 →「▸ 來源與日期明細」（Level 2）→「▸ 開發診斷」（Level 3，預設收合） | 單欄 | 整列在下（H-6） | **新增** section（建議 `health`／`health_detail`／`health_dev`）；既有 `fresh`／`sysinfo` 不動、內容由新區塊承接 |

### B.2 手機 390px（Pending-A：Level 1 展開、Level 2／3 收合；推薦案）

> 手機頂列 ☰ 與抽屜屬 DEC-134 導覽殼（另案線框，本檔不改）；底部不再有固定四格。以下列項為**示意狀態**（FAKE），非實測；真實 Real 預期見 §C。

```
┌──────────────────────────────┐
│ ☰  台股 AI 戰情室 · 👤 我的     │ ← 導覽殼（DEC-134；不在 P6）
│ ℹ 示意資料（FAKE）             │ ← 既有單行標示（僅 FAKE）
│ 👤 我的                        │
│ ── 帳號與資料來源 ──            │
│ Google   ⬜ 尚未登入            │ ← 連線事實；Real 無 auth 契約 →「⬜ 尚未提供」沿現況
│ Sheet    …a1b2c3（末 6 碼）     │   未登入時依賴登入的欄位＝⬜ 資料未備（沿現況語意；◇ 別名僅限資料健康度面）
│ 組合 <名稱> · 觀察清單 <名稱>    │
│ Google 登入入口在左上角 ☰（目前尚未開放）│ ← 未登入：指引句（不放第二顆登入鈕；H-5=A）
│ [切換 Sheet][選組合][選觀察清單]  │ ← 已登入才出現；disabled；共用一句原因（去重）
│ [Google 登出]                   │
├─────────── 第一屏底 ───────────┤
│ ── 一般設定 ──                  │
│ Strategy ⬜ 尚未提供            │
│ Notifications ⬜ 尚未提供       │
│ Display preference ⬜ 尚未提供  │
│ ── 資料健康度 ──                │
│ 資料 1／4 正常 · 另 15 項尚未接線 │ ← 總覽一行（分母＝已接線列；H-10）
│ ┌ 台股大盤 ────────────────┐ │
│ │ 狀態 ✅ 正常   接線 已接線   │ │ ← 每列兩個獨立欄位（兩個小標＋兩個 chip）
│ │ 來源 本地加權指數歷史快取（來源 Yahoo，每日更新）│ │   來源＋資料日＝既有 freshness micro-tag
│ │ 資料日 2026-11-03           │ │
│ └──────────────────────────┘ │
│ ┌ 產業 ────────────────────┐ │
│ │ 狀態 ◷ 可能過期  接線 已接線  │ │ ← 示意
│ │ 資料日 2026-11-01           │ │
│ └──────────────────────────┘ │
│ ┌ 法人／籌碼／融資 ───────────┐ │
│ │ 狀態 ⛔ 來源不可用 接線 已接線 │ │ ← 示意（真錯誤才紅）
│ └──────────────────────────┘ │
│ ┌ 基本面 ──────────────────┐ │
│ │ 狀態 ◇ 資料未備  接線 已接線  │ │ ← 示意
│ └──────────────────────────┘ │
│ ┌ VIX ─────────────────────┐ │
│ │ 狀態 （不適用） 接線 ⬜ 尚未接線│ │ ← 未接線列：狀態欄不填五態
│ └──────────────────────────┘ │
│   …（其餘列同格式；完整列見 §C）  │
│ ▸ 來源與日期明細                │ ← Level 2（預設收合）
│ ▸ 開發診斷                      │ ← Level 3（預設收合；遮罩）
│ ── 稽核 ──                      │
│ ▸ Decision Digest              │ ← 預設收合（沿現況）
│ ▸ Rule Registry（唯讀）         │
└──────────────────────────────┘
```

**手機要點**：① 一列＝一張兩行小卡，「狀態」「接線」是**兩個獨立元素**（各帶 `data-ui2-col`，見 §G），不合併成單一 chip；② 長清單（約 17～20 列）會把「稽核」推到第二屏以下——稽核本來就預設收合，可接受（未量測，§I）；③ 資料健康度整區在第一屏底之下，**不增高第一屏**。

### B.3 手機 390px（Pending-B：Level 1 預設也收合）

```
│ ── 資料健康度 ──                │
│ 資料 1／4 正常 · 另 15 項尚未接線 │ ← 總覽一行永遠可見
│ ▸ 展開資料健康度總覽（19 項）     │ ← Level 1 收合；展開後同 B.2
│ ▸ 來源與日期明細                │
│ ▸ 開發診斷                      │
```
Level 1／2 預設展開收合共 4 種組合（L1∈{展開,收合}×L2∈{展開,收合}）；本檔畫推薦案（B.2：展開／收合）與對照案（B.3：收合／收合）。**不升格任一案**（H-1）。

### B.4 Level 2／Level 3 展開示意（手機）

```
│ ▾ 來源與日期明細                │
│ ┌ 台股大盤 ────────────────┐ │
│ │ 來源       本地加權指數歷史快取（來源 Yahoo，每日更新）│
│ │ 資料日     2026-11-03          │
│ │ 取得時間   ⬜ 尚未提供          │ ← canonical 無此欄 → DG-01，⛔ 補 now()
│ │ 新鮮度     最新（距今 1 天）     │ ← 取自既有 is_stale／age_days
│ │ 來源性質   ⬜ 尚未提供          │ ← 無統一 provenance／proxy 欄 → DG-04
│ │ 缺值原因   —（無缺值）          │
│ │ 來源健康   ⬜ 尚未提供          │ ← DG-03
│ └──────────────────────────┘ │
│ ┌ 市場位階（說明）─────────────┐ │ ← 見 B.6
│ │ 判定  ⬜ 未評估／資料不足       │
│ │ 資料日 ⬜ 資料日未提供（市場位階未提供資料日）│
│ │ 簡要原因 原因：尚缺正式的市場廣度（漲跌家數）資料│ ← 既有 REGIME_SEE_WHY
│ │ （註：冷啟動 SOURCE_UNLOADED＝Not Evaluated「⬜ 尚未載入」；廣度不足才是 Unable to Determine「⬜ 未評估／資料不足」；上列示意為後者）
│ │ 完整說明 〈使用者可讀版本，H-2〉  │
│ └──────────────────────────┘ │
│ ┌ 系統資訊 ─────────────────┐ │ ← System Information 承接（見 C-17b）
│ │ 門檻校準  校準日 …｜方法 …｜生效值與檔內值 一致／不一致│
│ │ 系統版本／部署  ⬜ 尚未提供    │ ← DG-18
│ └──────────────────────────┘ │
│ ▾ 開發診斷                      │
│ （僅遮罩後識別碼，預設收合；見 B.7）│
```

### B.5 桌機 1440px（推薦案：Wireframes §5.2 兩欄不動，資料健康度整列在下；L1 展開／L2、L3 收合）

> 左側 rail 的 Logo／登入／四頁屬 DEC-129／P7（不在 P6）；畫出只為標示登入按鈕的唯一位置。列項為示意狀態。

```
┌─────────────┬───────────────────────────────────────────────────────────────────────────┐
│ [Logo]      │ ℹ 示意資料（FAKE） 非真實行情、持股或建議                                    │
│ 登入        │ 👤 我的                                                                      │
│ ⬜ 尚未登入   │ ┌ 帳號與資料來源 ────────────────────────────────────────────────────────┐ │
│ 📊 市場      │ │ Google ⬜ 尚未登入 ｜ Sheet …a1b2c3 ｜ 組合 <名稱> ｜ 觀察清單 <名稱>        │ │
│ 🎯 標的      │ │ Google 登入入口在左側（目前尚未開放）        （已登入時：[切換 Sheet][選組合][選觀察清單][登出]）│ │
│ 💼 持股      │ └────────────────────────────────────────────────────────────────────────┘ │
│ 👤 我的 ●    │ ┌ 一般設定 ───────────────────┐ ┌ 稽核（預設收合）──────────────────────────┐ │
│             │ │ Strategy ⬜ 尚未提供          │ │ ▸ Decision Digest   ▸ Rule Registry（唯讀）│ │
│             │ │ Notifications ⬜ 尚未提供     │ └─────────────────────────────────────────┘ │
│             │ │ Display preference ⬜ 尚未提供│                                              │
│             │ └──────────────────────────────┘                                              │
│             │ ┌ 資料健康度 ────────────────────────────────────────────────────────────────┐ │
│             │ │ 資料 1／4 正常 · 另 15 項尚未接線                                            │ │
│             │ │ 項目             │ 狀態         │ 接線        │ 來源                │ 資料日   │ │
│             │ │ 台股大盤          │ ✅ 正常       │ 已接線      │ 本地加權指數歷史快取（來源 Yahoo，每日更新）│ 11/03  │ │
│             │ │ 產業             │ ◷ 可能過期    │ 已接線      │ ⬜ 尚未提供           │ 11/01  │ │ ← 示意
│             │ │ 法人／籌碼／融資    │ ⛔ 來源不可用  │ 已接線      │ —                  │ —      │ │ ← 示意
│             │ │ 基本面            │ ◇ 資料未備    │ 已接線      │ —                  │ —      │ │ ← 示意
│             │ │ VIX              │ （不適用）     │ ⬜ 尚未接線  │ —                  │ —      │ │
│             │ │ 市場廣度          │ （不適用）     │ ⬜ 尚未接線  │ —                  │ —      │ │
│             │ │ …（其餘列同格式）                                                          │ │
│             │ │ ▸ 來源與日期明細                          ▸ 開發診斷                       │ │
│             │ └──────────────────────────────────────────────────────────────────────────┘ │
└─────────────┴───────────────────────────────────────────────────────────────────────────┘
```

**桌機要點**：①「一般設定｜稽核」兩欄沿 Wireframes §5.2 不動；② 兩欄表欄序 `項目｜狀態｜接線｜來源｜資料日`＝Active Contract §5.1 範例表；③ 桌機 DOM 與手機**同一份**（Streamlit 無法依視窗切換 DOM），表格在手機由 CSS 疊成 B.2 的小卡（`data-ui2-col` 標記兩種版面同樣存在）。

### B.6 桌機 Level 2 展開示意

```
│ ▾ 來源與日期明細                                                                    │
│ 項目       │ 來源              │ 資料日  │ 取得時間      │ 新鮮度       │ 來源性質      │ 缺值原因  │ 來源健康      │
│ 台股大盤    │ 本地加權指數歷史快取（來源 Yahoo，每日更新）│ 11/03 │ ⬜ 尚未提供   │ 最新（1 天）  │ ⬜ 尚未提供   │ —        │ ⬜ 尚未提供   │
│ 產業        │ ⬜ 尚未提供        │ 11/01 │ 11/03 16:56  │ 可能過期      │ 部分涵蓋│ —      │ ⬜ 尚未提供   │ ← 示意；「部分涵蓋」取自既有 tpex_complete 旗標
│ 市場位階（說明）：判定 ⬜ 未評估／資料不足 ｜ 簡要原因 … ｜ 完整說明 〈H-2〉                  │
│ 系統資訊：門檻校準 …｜系統版本／部署 ⬜ 尚未提供                                          │
```

### B.7 Level 3 「開發診斷」（預設收合；遮罩；禁曝險清單）

```
│ ▾ 開發診斷                                                                         │
│ 資料集識別碼    twii_ohlcv、finmind_inst、finmind_margin、finmind_m1m2、tw_pmi        │ ← 非 module path／env var
│ 讀取結果碼      台股大盤: ok｜法人: ok｜景氣: 抓取結果為空（快取後設資料 last_error，已 scrub）│
│ （以下為規格註記，非畫面文字）不顯示  ⛔ API key／secret／token／env var 名／raw exception／traceback／module path／credential／內部堆疊│
```
**限制**：L3 內容必須**避開 `tests/test_ui2_p1_human_text.py:36 ENGINEERING_VOCAB` 與 `tests/test_ui2_contract_teeth_pending.py:35 _ENGINEERING_TOKENS`**（`Gate`／`Stage`／`PORT`／`.py`／`src.`／`Exception`／`DEC-`／`macro_state` 等），或在測試端做**限區 allowlist**（§G.1 T-P6-1）。L0 逐字常數含 `DEC-074／075` 與 `macro_state.json`，因此**不放進 Level 2**（H-2）。

### B.8 帳號與資料來源區塊：各狀態（render policy；VM 不刪）

**現況→提案**：現況預設 FAKE 道 `ui2_account` 預設 signed_in（`app.py:84-85`），故 👤 預設顯示「已登入（FAKE）」，Real 顯示 `⬜ 尚未提供`，rail／抽屜則固定「⬜ 尚未登入」占位——三處不一致。提案（H-11）：正式 auth 契約前三處由同一固定占位來源渲染；以下 signed_in／signed_out／unavailable 三態僅屬 FAKE 場景 VM 與 `?ui2_dev=1` 開發面，預設道不出現。

```
signed_out（FAKE）：
  Google ⬜ 尚未登入 ｜ Sheet ⬜ 資料未備（需先登入）｜ 組合 ⬜ 資料未備 ｜ 觀察清單 ⬜ 資料未備
  下一步：手機『Google 登入入口在左上角 ☰（目前尚未開放）』／桌機『Google 登入入口在左側（目前尚未開放）』      ← 指引句，無第二顆登入鈕
signed_in（FAKE）：
  Google ✅ 已登入（ab***@gmail.com）｜ Sheet …a1b2c3 ｜ 組合 <名稱> ｜ 觀察清單 <名稱>
  [切換 Sheet][選組合][選觀察清單][Google 登出]（disabled，一句共用原因）
unavailable（FAKE）：
  Google ✅ 已登入 ｜ Sheet 🔴 Sheet 讀取失敗（FAKE 示意）｜ 組合 ⬜ 資料未取得 ｜ 觀察清單 ⬜ 資料未取得
  下一步：重新讀取，或重新綁定 Sheet；[重新讀取]（disabled）
Real（無正式 auth 契約）：
  連線狀態 ⬜ 尚未提供（沿現況；原因「需登入 Google 才能顯示，目前尚未開放」）— ⛔ 假裝已登入／未登入
```
連線異常／下一步在「無異常」（`連線異常＝無異常`且`下一步＝無需處理`）時隱藏；冷啟動、signed_out、unavailable **不**隱藏（`⬜ 尚未載入`等是誠實說明，不是「無異常」）。此為 render policy，`first_screen` 仍完整留在 VM（P3 baseline 守衛：列數不得減少）。

### B.9 市場位階完整說明的使用者可讀位置（客戶 (20) 明列）

- **位置**：Level 2「來源與日期明細」內的「市場位階（說明）」卡（Active Contract §8：「資料健康度·市場位階項 L2」）。Level 1 兩欄表**不放位階列**（H-7=A：位階是「判定結果」，不屬五態資料源——見 DG-06）；位階相關的資料源列是「市場廣度」（`⬜ 尚未接線`）。
- **現況事實**：兩個 L0 常數**逐字**如下（客戶裁示原文，teeth 鎖定，**不得改**）：
  - `NOT_LOADED_PENDING_BREADTH_EXPLAIN`（`regime_arbiter.py:153`）：「總經尚未載入：這一次使用中還沒有紅綠燈結果。可以按更新載入今日資料，但在正式的市場廣度（漲跌家數）資料來源接上前，載入後市場位階仍為未評估 —— 由加權指數推估的代理值依客戶裁示（DEC-074）不計分，市場位階依 DEC-075 也不改用另一套規則引擎（`macro_state.json`）補出」
  - `UNEVALUATED_BREADTH_EXPLAIN`（`regime_arbiter.py:120`）：「總經未評估：缺真實市場廣度（漲跌家數）—— 由加權指數推估的代理值即使取得，依客戶裁示（DEC-074）也只顯示、不計分，健康分因此算不出來；市場位階依 DEC-075 一併未評估，不改用另一套規則引擎補出位階。更新資料不會改變這個狀態，要等正式的廣度資料來源接上」
- **問題**：兩句含 `DEC-074`／`DEC-075`／`macro_state.json`／反引號，命中 `shared/ui2_contract/text.py` 的 `is_dev_only_text`（`DEC-\d+`、`macro_state.json`、`` ` ``）與 `ENGINEERING_VOCAB`（`DEC-`、`macro_state`），故 Human UI 不渲染。**是否需要「使用者可讀版本」＝客戶裁示（H-2）**；任一案都**不改 L0 常數**，逐字原句續存 VM（Level 3 不放，避免擴大 allowlist）。

### B.10 沿用元件清單（只引用，不新建視覺語言）

| 用途 | 既有元件（`src/ui2/components/html.py` 等） |
|---|---|
| 區塊標題 | `.ui2-section-title`（`section_l1_html`） |
| 狀態 chip（三軸各自樣式） | `chip_html(text, tone, axis=, state=)`、`status_chip_html`；Capability chip 先例＝`primary_slot_html`（`axis="capability"`） |
| 來源／資料日 micro-tag | `freshness_html`（`資料日 …`＋Neutral 來源 chip；缺 as_of → `⬜ 資料日未提供`） |
| 空／未提供說明 | `empty_state_html` |
| disabled 動作 | `cta_html`（`aria-disabled="true"`＋原因句） |
| 預設收合容器 | `st.expander`（`_page.render_sections` 的 `SHOWN_FOLDS` 白名單機制） |
| 單行標示 | `banner_html` |
| **新增** | 資料健康度兩欄列、總覽一行（本線框為草稿 Gate） |

---

## C. 逐欄核對表（資料健康度涵蓋項目）

**圖例**（欄位存在度）：● New UI2 或 L3 現成可讀；◐ 存在於 L1／L2／session，**無 L3 出口**（P6 不得直讀，需 thin L3＝PORT）；○ 無此欄；— 不適用。**分類**（對應 #1007 的 A–E）：**可立即呈現**＝A 已接／B 唯讀 service 現成且 P6 不增欄位；**需 PORT**＝C；**需新契約 Gate**＝E／D 中涉新欄位或 Auth；**無來源**＝D。證據出處＝檔案:行；`NUI2-*`／`SG-*` 見 BACKLOG §5.1.26 與 `NEWUI2_REAL_FEED_MAPPING_2026-11-03.md` §6。

### C.1 欄位存在度矩陣（讀碼結論）

| 項目 | source | as_of | retrieved_at | freshness | provenance／來源性質 | missing reason | proxy／estimated | source health |
|---|---|---|---|---|---|---|---|---|
| 台股大盤 | ●（固定句） | ● | ◐（`metadata.json` 批次 `updated_at`） | ●（is_stale／age_days） | ○ | ● | — | ◐（`upstream_error` 僅布林） |
| VIX | ◐ | ◐ | ◐（L1 `fetched_at`） | ◐ | ◐（Risk Cap shadow） | ◐（readiness `reason`） | ○ | ○ |
| 殖利率（US10Y） | ◐ | ◐ | ◐ | ○ | ○ | ◐（`_err`） | ○ | ○ |
| 國際市場／DXY | ◐（`Series.attrs`） | ◐ | ◐ | ○ | ○ | ○ | ○ | ○（session 形狀未驗） |
| PMI／景氣 | ◐（標籤） | ◐ | ○ | ◐ | ◐（L0 標籤表） | ◐ | ○ | ◐（`last_error`） |
| 市場廣度 | ○ | ○ | ○ | ○ | ○ | ○ | ◐（`is_breadth_proxy`） | ○ |
| 產業 | ○ | ◐（`updated_at` 時戳） | ◐（`meta_updated_at`） | ● | ○ | ● | ◐（`tpex_complete`） | ○ |
| 法人／籌碼／融資（市場級快取） | ○ | ◐ | ◐ | ◐ | ○ | ◐ | ○ | ◐（`last_error`） |
| 個股價格／籌碼 | ◐（`df.attrs`） | ◐ | ◐（`df.attrs`） | ○ | ○ | ●（`miss_reason`／`error`） | ○ | ○ |
| 基本面（快照） | ○ | ●（民國年季） | ●（`updated_at`） | ○ | ○ | ●（涵蓋率） | ○ | ○ |
| 估值（357） | ●（備援段） | ○ | ○ | ○ | ● | ● | ○ | ○ |
| 持股／portfolio | ○ | ○ | ○ | ○ | ○ | ●（issue 代碼） | — | ◐（issue 代碼） |
| Risk Cap 輸入 | ◐（`source_id`） | ◐ | ○ | ◐ | ◐（五值） | ◐ | ◐ | ○ |
| Sheet／設定 | ○ | ○ | ○ | ○ | ○ | ●（issue 代碼） | — | ◐（`error` repr，須 scrub） |

### C.2 逐項核對

| 項目 | canonical service／contract（實查） | 回傳欄位：存在／缺（Data Gap） | Data State 如何由既有欄位映射 | Capability（P6 預期）與分類 | SG／BACKLOG |
|---|---|---|---|---|---|
| **1 台股大盤** | `src/services/market_twii_view_service.py:68 get_twii_trend_view` → `TwiiTrendView`（:27）；New UI2：`src/services/ui2/real_feed.py:44 _read_twii` → `real_canonical.py:93 TwiiFact`／`:244 twii_card_spec` | 存在：`ok`、`as_of`、`is_stale`、`age_days`、`stale_reason`、`failed`／`error`、`source`（**固定說明句**，非逐次來源）。`upstream_error` 在 `TwiiFact` 壓成布林 `has_upstream_error`（原文只 log）。缺：retrieved_at（DG-01）、結構化 source health（DG-03） | **已有正式映射**（`twii_card_spec`）：ok＋fresh→OK；`is_stale True`→Stale；`is_stale None`→Stale（「新鮮度未判定」；**AI 總管內部判準，可推翻**）；`failed`→Unavailable；`ok False`→Missing | **已接線**；**可立即呈現**（A） | `NUI2-TWII-TWO-PATHS` |
| **2 國際市場** | 無 L3 canonical。L1：`src/data/macro/macro_core.py:575-579` `fetch_yf_close` 的 `Series.attrs["source"]="Yahoo:<ticker>"`／`["fetched_at"]`；session `cl_data['intl']` | 存在於 L1：source、fetched_at。缺：L3 出口（DG-08）；`cl_data['intl']` 鍵集與形狀**未驗** | 無既有映射 | `⬜ 尚未接線`；**需 PORT**（逐圖待確認，mapping「國際比較」列 B/C） | `NUI2-PORT-READINESS-L3` |
| **3 VIX** | 無 L3 canonical。L1 `macro_snapshot.py:171 fetch_vix_block`（`current,ma20,dates,values,date,source='yfinance:^VIX:3mo:1d',fetched_at`；失敗 `_err_vix`）；L2 readiness 側車 `compute_five_bucket_summary(readiness_out=)`（`macro_helpers.py` ~1688；`state ok|missing`、`reason MISSING_*`、`hit_source`、`candidates`、`rejected`、`wired`）；Risk Cap `INPUT_POLICY['VIX_Index']`＝secondary（`input_provenance_policy.py:198`） | 存在（L1／L2）：source、as_of(`date`)、fetched_at、missing reason。缺：L3 出口（DG-02／08）；值只存在 🚀 更新後的 session，Preview 恆冷（SG-01）；兩條路徑（`dividend_station_service.fetch_vix` 無 as_of） | 無既有映射（readiness `state ok|missing` 是 L2 側車，非 FieldState） | `⬜ 尚未接線`；**需 PORT** | `NUI2-PORT-READINESS-L3`、`NUI2-VIX-TWO-PATHS`、SG-01 |
| **4a 殖利率（US10Y）** | 無 L3 canonical。L1 `macro_snapshot.py:668 fetch_us10y_block`（`current,date,value,source='FRED/fredgraph.csv:DGS10',series_id,fetched_at`；失敗 `{'_err':…,'current':None}`） | 存在（L1）：source、as_of、fetched_at、錯誤字串（**不得上畫面**）。缺：L3 出口 | 無既有映射 | `⬜ 尚未接線`；**需 PORT** | `NUI2-PORT-READINESS-L3` |
| **4b 利差** | **無 canonical 欄**：`shared/macro_buckets.py` `DangerSpec` 無利差；`macro_core.spread_series` 無 production consumer（mapping SG-02 補證據） | 全缺（DG-09）：10Y-2Y／10Y-3M／M1B-M2 定義未選 | — | `⬜ 尚未接線`；**無來源／需新契約 Gate** | SG-02、SG-14 |
| **5 DXY** | 無 L3 canonical；readiness `dxy` 取自 `cl_data['intl']`（`macro_helpers.py` P0-B 註解） | 同 2 | 無 | `⬜ 尚未接線`；**需 PORT** | `NUI2-PORT-READINESS-L3` |
| **6a 台灣 PMI** | L1 `macro_snapshot.py:814 fetch_tw_pmi_block`；`macro_cache_reader.py:240 load_tw_pmi_history`（`tw_pmi.parquet`）；`data_cache/metadata.json` `tw_pmi`（`last_updated`、`row_count`、`last_error`；測量日 2026-11-04：`last_updated=2026-10-01`、`last_error="抓取結果為空"`）；L0 `PMI_LABEL_PROVENANCE`（official／secondary）；L2 `infer_input_provenance`（`input_provenance.py:378`）；Risk Cap 鍵 `ISM_PMI_or_OECD_CLI`／`PMI_Prev_Month` | 存在：source 標籤、as_of、provenance（L0／L2）、`last_error`。缺：parquet 無 `is_stale`（mapping M13）；L3 出口（DG-08）；與景氣語意未定（DG-10） | 無既有映射 | `⬜ 尚未接線`；**需 PORT／需新契約 Gate**（SG-03 先選語意） | SG-03 |
| **6b 景氣燈號** | L1 `macro_snapshot.py:862 fetch_ndc_block`；session `macro_info['ndc_signal']` | 同 6a（台灣 PMI≠NDC 景氣燈號，須分來源與頻率） | 無 | `⬜ 尚未接線`；**需 PORT** | SG-03 |
| **7 市場廣度** | **無正式廣度來源**（L0 說明原文「正式的市場廣度（漲跌家數）資料來源接上前」）。代理值：`shared/macro_provenance.py:148 is_breadth_proxy`、`src/services/section_inputs.py:120 breadth_proxy_presence`（True／False／None） | 代理旗標存在（◐）；代理值依客戶裁示**只顯示、不計分**（DEC-074）。缺：正式來源（DG-11） | Data State 不適用（無正式輸入）；代理 → 旗標，非 Data State | `⬜ 尚未接線`（正式來源）；**無來源**（新 source＝Gate） | 位階 `SOURCE_UNEVALUATED_BREADTH` |
| **8 產業** | `src/services/sector_flow_service.py:88 get_sector_flow_view` → `src/data/sector_flow/reader.py:73 read_sector_flow_cache` | 存在：`ok`／`reason`、`updated_at`、`meta_updated_at`（≈ cron 時刻）、`is_stale`／`stale_reason`、`window_size`、`n_trading_days_used`、`tpex_complete`、`n_absent_cells`、`sectors[].unavailable／n_missing_days`。缺：source 名（DG-07）、交易日 as_of（只有時戳） | 無 UI2 先例；可沿 `twii_card_spec` 模式：`ok False`→Missing（strict 壞檔例外→Unavailable）、`is_stale True`→Stale、其餘 OK；`tpex_complete is False`→來源性質「部分涵蓋」；`None`（舊 JSON 缺鍵）→`⬜ 尚未提供`。**映射規則須明寫，且 ⛔ 新增門檻（SG-14）** | `⬜ 尚未接線`→P6 可接；**可立即呈現**（B；呼叫參數須避免觸發 Sheet 讀取，`stock_sheet_id=None`／`include_stock_watchlists=False` 時跳過——**未驗實際分支**） | — |
| **9a 法人／籌碼／融資（市場級快取）** | L1 `macro_cache_reader.py:94 compute_cache_staleness`（`dataset∈CACHE_DATASET_CADENCE`〔:60〕：`twii_ohlcv／finmind_inst／finmind_margin／finmind_m1m2`；回 `is_stale,reason,as_of,age_days,periods_behind,upstream_error`）＋`read_cache_metadata`（:68） | 存在（L1）：as_of、freshness、`last_error`、`row_count`、`updated_at`。缺：**無 L3 wrapper**（BACKLOG `NUI2-PLAN1007-METADATA-NO-L3`）；source 名（metadata 只有 dataset id） | 可由 `is_stale`／`upstream_error` 映射（同上，須明寫） | `⬜ 尚未接線`→需 thin L3 後可接；**需 PORT**（欄位限既有） | `NUI2-PLAN1007-METADATA-NO-L3` |
| **9b 個股籌碼** | `src/services/stock_chips_service.py:277 get_chips_readout` → `ChipsReadout`（:127：`rows,days,miss_reason,error,outlier_*`） | 存在：`miss_reason`／`error`。缺：source／as_of／fetched_at——L1 `df.attrs` 有（`app_stock_fetchers.py:161-166`）但 L3 **丟失**（DG-15） | `error`→Unavailable；`miss_reason`→Missing | 屬 🎯 個股，非市場級；P6 資料健康度是否列入個股級＝**待定**（建議不列，只列市場級） | — |
| **10 個股價格** | L1 `app_stock_fetchers.py:109 fetch_price_data`（`df.attrs source／fetched_at`、`INST_FETCH_FAILED_ATTR`）；🎯 查一檔 canonical 未驗（mapping T10–T12 C/D） | 同 9b | 未驗 | **需 PORT／未驗** | mapping T10–T12 |
| **11 基本面** | L1 `data_cache/fundamentals/latest.json`（`roc_year,season,updated_at,coverage{sii,otc,total,prev_total}`，測量日 2026-11-04：`115/Q2`、`updated_at=2026-09-18`）；L3 `fundamental_screener_service.py:67 get_fundamental_prescreen` → `(df, meta)`、`:179 describe_snapshot_coverage(meta)` → `{text,possibly_incomplete,total,prev_total}` | 存在：資料季別、抓取日、涵蓋率、可能不完整旗標。缺：source 名；逐檔 EPS 口徑（mapping 另案） | 無先例；`possibly_incomplete` 是**完整性**非新鮮度，不得當 Stale | `⬜ 尚未接線`→可接；**可立即呈現**（B；`get_fundamental_prescreen` 會跑初篩，成本與副作用**未驗**，僅需 meta 時應評估 thin 讀取） | — |
| **12 估值** | L3 `valuation_service.py:85 get_pe_name_maps`（pass-through）、`:164 get_stock_dividends` → `StockDividends`（:115：`avg_div_twd,paying_years,years,source∈{FinMind,yfinance,TWSE,''},invalid`） | 存在：source（備援段）、缺值語意（None≠0）。缺：as_of、fetched_at；Forward EPS／PE 基期（DG-16，SG-08） | `invalid`／`has_record False`→Missing | `⬜ 尚未接線`；**需 PORT／需新契約 Gate**（SG-08） | SG-08 |
| **13 持股／portfolio** | L3 `holdings_service.py:213 get_holdings` → `HoldingsResult`（:100：`bound,logged_in,login_expired,portfolio_issue,watchlist_issue/error,*_selection,portfolio_names_n,…`）；`portfolio_binding_service.py:294 ActiveSheet`、`:354 get_active_selection` | 存在：連線／選定／issue 代碼。缺：as_of、retrieved_at、source health（DG-12）；讀取連 Google（OAuth） | issue 代碼→Missing／Unavailable 需逐碼定義（新映射） | `⬜ 尚未接線`；**需新契約 Gate**（Auth，SG-11） | SG-11、`NUI2-AUTH-CONTRACT-GATE` |
| **14 Risk Cap 輸入** | 寫入端 `src/services/risk_cap_apply.py:111 INPUT_PROVENANCE_SHADOW_KEY="input_provenance_shadow"`／`:348 _input_provenance_shadow`；L2 `input_provenance.py:378 infer_input_provenance`（逐項 `RECORD_FIELDS`〔:77〕：`provenance,provenance_detail,provenance_basis,freshness,as_of,source_id,exists,fresh,displayable,scoring_eligible,riskcap_eligible,actual_scored`）；L0 `Provenance`（official／secondary／estimated／proxy／unavailable，`input_provenance_policy.py:61`）、`FreshnessAxis`（fresh／stale／carried_forward，:71）；`INPUT_POLICY` 九鍵（:198） | **全站唯一已有 provenance／proxy／estimated 正式欄位的鏈**。缺：**無 L3 reader**（只有寫入端定義 schema）；`macro_state.json`／`risk_cap_state.json` 未入 git（runtime，Preview 不存在，`git ls-files` 僅 `macro_state_locker.py` 及其測試）；`scoring_eligible／riskcap_eligible／actual_scored` 屬 Risk Cap 語意，**不得**上資料健康度（SG-06）（DG-13） | `freshness stale`→Stale；`exists False／provenance unavailable`→Missing；映射須另定 | `⬜ 尚未接線`；**需新契約 Gate**（Opus High） | SG-06、`NUI2-DATA-HEALTH-FIELD-GAPS` |
| **15 System Action 輸入** | System Action Aggregator 未建（mapping SG-07） | 全缺（DG-14） | — | `⬜ 尚未接線`；**無來源** | SG-07 |
| **16a Sheet／帳號** | L3 `me_account_service.py:78 get_account` → `AccountView`（:69：`state∈{not_configured,logged_out,expired,logged_in,read_failed}`、`email_masked`、`login_url`、`error`）；`:118 get_sheet_view` → `SheetView`（:105）；`:229 get_sheet_contents` → `SheetContents`（:198） | 存在：連線狀態碼、issue 代碼。缺：as_of、retrieved_at、source health（DG-12）。**副作用**：`get_account` 未登入時 `build_login_url` 會登記 nonce（寫 `_oauth_state`，mapping §3）；`get_sheet_view` 連 Google | 狀態碼→五態需逐碼定義（新映射） | `⬜ 尚未接線`；**需新契約 Gate**（Auth） | SG-11、`NUI2-AUTH-CONTRACT-GATE` |
| **16b 設定（Strategy／Notifications／Display）** | 未找到正式 canonical settings contract（mapping E8–E10；兩組皆未窮舉） | 全缺（DG-19） | — | `⬜ 尚未接線`；**無來源**（沿現況 `⬜ 尚未提供`） | — |
| **17a 其他：資料登錄中心摘要（＝舊 Data Freshness 的 canonical 候選）** | L3 `data_registry_summary_service.py:106 summarize_data_registry(session)` → `RegistrySummary{written, groups[RegistryGroup{category,count,missing,latest}]}`；靜態來源註冊 L1 `data_registry.py:68 DATA_REGISTRY`（`category,name,source,endpoint,frequency,requires_key,…`） | 存在：每類別筆數、缺漏數、最新更新日。缺：逐來源 source 欄（只有 category）（DG-07）。資料由 🚀 更新寫入 `session['data_registry']`——Preview 恆 `written=False`（SG-01） | `written=False`→Not Evaluated（`⬜ 尚未載入`）；缺漏數>0→Missing 需逐項定義 | `⬜ 尚未接線`；**需 PORT**（session 相依） | SG-01 |
| **17b 其他：門檻校準（＝System Information 的 canonical 候選）** | L3 `calibration_status_service.py:46 get_calibration_status` → `CalibrationStatus{effective_*, file_*, last_calibrated, method, consistent}`（session-free、零網路） | 存在：生效值／檔內值、校準日、方法、是否一致。缺：系統版本／部署資訊**無 SSOT**（DG-18） | 不當「資料源列」；以事實列呈現，不映射五態 | 可接；**可立即呈現**（B） | mapping E14 |
| **17c 其他：稽核入口** | `src/services/decision_digest_builder.py:405 build_decision_digest`（0 production caller）；L0 `shared/decision_digest_rules.py:77 RULE_ID_ALLOWLIST` | 非資料源列；沿 DEC-130 (b) 預設收合、占位 | — | 沿現況 | Digest Stage F |

### C.3 彙整 Data Gap 清單（⛔ 自行新增資料來源或契約；缺欄一律顯示 `⬜ 尚未提供`／（不適用）並登記）

| 編號 | 一句話 | 證據／來源 | 處理 |
|---|---|---|---|
| **DG-01** | 台股 canonical 無 retrieved_at；僅 `metadata.json` 批次級 `updated_at`（整批 cron 時刻，非逐來源取得時刻）存在 L1 | `TwiiTrendView`（無此欄）；`macro_cache_reader.py:68`；測量日 `updated_at=2026-11-03T16:56:16+00:00` | `NUI2-DATA-HEALTH-FIELD-GAPS`（Opus High） |
| **DG-02** | VIX／US10Y 等 L1 `fetched_at` 存在，但無 L3 出口，且僅 🚀 更新後存在於 session | `macro_snapshot.py:226,707` | `NUI2-PORT-READINESS-L3` |
| **DG-03** | source health 全站無統一欄位；僅零散（`last_error` 原文→`TwiiFact` 壓成布林；readiness `reason`；`_err*`；`ChipsReadout.error`；issue 代碼） | `real_feed.py:49-52`；`macro_helpers.py` readiness | FIELD-GAPS（需定義） |
| **DG-04** | proxy／estimated 無統一欄；僅 Risk Cap shadow 五值與零散旗標（`is_m1b_m2_proxy`、`is_breadth_proxy`、bias `is_estimated`、sector `tpex_complete`） | `macro_provenance.py:57,148`；`input_provenance_policy.py:61` | FIELD-GAPS |
| **DG-05** | 市場位階無 as_of（`source` 是規則分支 id，非行情來源） | `RegimeFact`（`real_canonical.py:117`）；SG-10 | 客戶 Gate |
| **DG-06** | 位階「判定結果」（Unable to Determine）不屬 Data State 五態，兩欄表無處安放 | DEC-124；`JudgementState`（`models.py:40`） | H-7 |
| **DG-07** | 缺 source 名：產業、法人／籌碼快取、資料登錄中心（只有 category）、持股／Sheet | `reader.py:73`；`summarize_data_registry` | 顯示 `⬜ 尚未提供`；不自編 |
| **DG-08** | 國際市場／VIX／US10Y／DXY／PMI／景氣：無 L3 canonical；Preview 恆冷 | `NUI2-PORT-READINESS-L3`；SG-01 | PORT 批 |
| **DG-09** | 利差無 canonical 欄 | SG-02 | Data Gate |
| **DG-10** | 台灣 PMI 與 NDC 景氣燈號語意未定義（選源／合併卡） | SG-03 | Data Gate |
| **DG-11** | 無正式市場廣度來源（位階未評估的根因；代理值依客戶裁示不計分） | `regime_arbiter.py:120,153` | 新 source Gate |
| **DG-12** | 持股／Sheet 無 as_of／retrieved_at／來源健康；讀取需 Auth | `HoldingsResult`、`AccountView`、`SheetView` | `NUI2-AUTH-CONTRACT-GATE` |
| **DG-13** | Risk Cap 輸入 provenance shadow 無 L3 reader、檔案非 git 追蹤，且 `riskcap_eligible` 屬 Risk Cap 語意 | `risk_cap_apply.py:111,348`；SG-06 | Opus High Gate |
| **DG-14** | System Action 輸入無來源 | SG-07 | 等 Aggregator |
| **DG-15** | 個股價格／籌碼的 `df.attrs source／fetched_at` 在 L3 `ChipsReadout` 丟失 | `app_stock_fetchers.py:161-166` vs `stock_chips_service.py:127` | PORT 批 |
| **DG-16** | 估值／基本面：`StockDividends` 無 as_of／fetched_at；PE map 無 as_of；Forward EPS 無；基本面快照有季別與抓取日但無來源名 | `valuation_service.py:115`；SG-08 | SG-08 |
| **DG-17** | 新鮮度判定規則不統一（各源自有 `is_stale`）；無 `is_stale` 的來源**不得**以 now()−as_of 自訂門檻（新門檻＝SG-14）；`is_stale=None→Stale` 為 AI 總管內部判準 | `real_canonical.py:244`；`shared/staleness.py` | 每列明寫映射、不新增門檻 |
| **DG-18** | 系統版本／部署資訊無 SSOT（System Information 僅門檻校準有 canonical） | grep `APP_VERSION`／`RELEASE_VERSION` 0 命中（src／shared／app.py） | 顯示 `⬜ 尚未提供` |
| **DG-19** | 設定（Strategy／Notifications／Display）無 canonical | mapping E8–E10 | 沿現況 |
| **DG-20** | VM 槽位缺口：`FreshnessInfo` 只有 `as_of`／`source`（`models.py:76`）；retrieved_at、來源性質、缺值原因、來源健康在 `FieldVM` **無結構化槽位**。擴充＝VM schema 變更（Active Contract §8：須先過 Gate）；降級＝以單句 `detail` 承載（不結構化） | `models.py:76-134` | 見 §G.2 |
| **DG-21** | Digest 無資料健康度區塊（`NUI2-DIGEST-DATAHEALTH-XREF`）；Digest `market.health` 是**總經健康分**，不是資料健康度。P6 不得先自建第二套 health facts，兩個 projection 應來自同一 evidence | `decision_digest_builder.py:200-210`；BACKLOG | Opus High Gate |

---

## D. Level 1／2／3 展收行為

| 層 | 內容（欄位以 §C 為準） | 預設 | 狀態 |
|---|---|---|---|
| 總覽一行 | `資料 N／M 正常 · 另 K 項尚未接線`（DEC-091 §二先例：「資料 8/9 正常 · 1 項待更新」）。**分母 M＝已接線列數**，N＝其中狀態 OK 者；尚未接線列另計 K（恆黃的警告等於沒有警告，見 `shared/macro_buckets.py:223-231` `wired` 的教訓） | 永遠可見 | 撰寫組暫定（H-10） |
| **Level 1** 使用者可讀摘要：`項目｜狀態｜接線｜來源｜資料日` | 兩欄分離；別名符號（B.0-4） | **Pending**（H-1）：A 展開／B 收合；**推薦 A** | ⚠ 撰寫組暫定，未經客戶覆核 |
| **Level 2**「來源與日期明細」：來源、資料日、取得時間、新鮮度、來源性質、缺值原因、來源健康；另含「市場位階（說明）」「系統資訊」兩卡（**承接 Data Freshness／System Information**） | 只顯示 canonical 真有的欄位；無欄位寫 `⬜ 尚未提供`（⛔ 補推估值） | **Pending**（H-1）：A 收合／B 展開；**推薦收合** | ⚠ 撰寫組暫定 |
| **Level 3**「開發診斷」 | 預設收合；遮罩後識別碼；禁曝險清單 | **收合（客戶原文）** | 內容邊界 Pending（H-8） |

**推薦與理由（H-1）**：L1 展開、L2 收合。理由：L1 才是客戶要的「使用者可讀摘要」，收起來頁面看起來像空的；L2 欄位多半是 `⬜ 尚未提供`（DG-01／03／04），預設展開會讓「缺欄」比「有值」更顯眼，違背 Presentation Compression。對照案（L1 收合／L2 收合）：首屏更短，代價是使用者要多一次點擊才看到健康狀態。

**實作可行性註記**（不決定、供施工組參考）：Streamlit `st.expander` 在 AppTest／DOM 中**收合時內容仍存在**——掃描 DOM 的測試（T_new_2、P1 詞彙）會掃到 L2／L3 內容（§G.1 T-P6-1）；`<details>` 在 `st.markdown(unsafe_allow_html=True)` 內是否可用、狀態在 rerun 後是否保留，**未驗**（§I）。

---

## E. 帳戶資訊架構（與手機抽屜同一套）

| 面 | 登入入口（按鈕） | 狀態顯示 | 管理（Sheet／組合／觀察清單／登出） | 資料健康度 |
|---|---|---|---|---|
| 桌機 rail Account Area（P7，DEC-129） | **唯一桌機登入鈕** | compact：`登入`＋`⬜ 尚未登入`／`✅ 已登入`＋識別＋登出入口（登出屬狀態區入口，非 Sheet 管理） | Sheet 管理：無 | 無 |
| 手機抽屜（DEC-134） | **唯一手機登入鈕**（Google 登入入口） | 簡短狀態 | 無 | 無 |
| 👤 我的（P6） | **無第二顆登入鈕**；未登入時為指引句（手機「Google 登入入口在左上角 ☰（目前尚未開放）」／桌機「Google 登入入口在左側（目前尚未開放）」） | 完整連線事實（Google／Sheet 末 6 碼／組合／觀察清單） | **完整管理**（切換 Sheet／選組合／選觀察清單／登出；現皆 disabled） | **完整** Level 1／2／3 |

**一致性規則**：① 三處讀**同一個**正式 auth contract（`NUI2-AUTH-CONTRACT-GATE`）；契約未具備前，狀態一律誠實：Real 顯示 `⬜ 尚未提供`（沿現況），FAKE 場景只在開發面；**預設 FAKE 道 `ui2_account` 預設 signed_in（`src/ui2/shell/app.py:84-85`）與 rail／抽屜固定占位衝突，處置見客戶確認項 H-11**；② 登入「動作」只有一個 handler（登入鈕只在殼）；③ `ui2_dev`／`ui2_account`（FAKE account）／任何 query parameter **不得**當登入證據（DEC-130 (c)、`tests/test_ui2_guards.py` `check_ui2_dev_not_auth`）；④ 按鈕在正式 auth 契約具備前一律 `aria-disabled="true"`＋一句原因（DEC-134）；③′ 『⬜ 尚未登入』『✅ 已登入』需先完成 BACKLOG `NUI2-AUTH-STATUS-TEXT-GUARD`（字樣表現無此二字；現行 VM 值為「尚未登入」〔OK 態事實〕，見 `scenarios.py` 與 `NUI2-ME-SIGNEDOUT-CLASSIFICATION-REVIEW`）；⑤ 三處不得出現不同的帳號文字（同一 `AccountView` 來源，遮罩規則同 `me_account_service.mask_email`）。

**需 Auth Gate（Opus 5.5＋High）才能接的部分**：(1) 正式 Authentication State 來源；(2) 登入鈕啟用與 Google OAuth 流程（`get_account` 未登入時組登入網址會在 server 端登記 nonce、寫 `_oauth_state`）；(3) 登出；(4) Sheet 綁定／切換／選組合／選觀察清單（寫 session）；(5) 讀 Sheet 型資料健康列（持股／portfolio／Sheet，OAuth＋配額＋副作用）；(6) 正式「Sheet／Portfolio selection compact status」（Active Contract §2.5：僅限已有正式 contract）。**不需 Auth Gate、P6 可先做的**：版面重排、兩欄表骨架、FAKE 場景全五態、Real 模式「未接線」列、去重 render policy、disabled 占位。

---

## F. 保留清單（P6 不得修改）

- 📊 市場、🎯 標的、💼 持股三頁的內容、順序與資訊層級；P2 已核准的市場頁首屏順序與 OneBrain／Primary 位置。
- Risk Cap（恆 `⬜ 無法判定`）、System Action（待 Aggregator）、OneBrain（`⬜ 尚未提供`）、Decision Digest schema、資料層、正式資料來源、OAuth／Sheet 契約。
- 手機導覽（DEC-134 抽屜）與桌機 rail／Account Area（P7）——P6 不動 `shell/app.py`；導覽規格變更不得重新設計四頁內容。
- 👤 的 VM 完整保留：`first_screen`、4 張 `cards`、`settings`、`digest`、`registry`、**`fresh`、`sysinfo`**（`tests/test_ui2_p3_evidence_preservation.py` baseline：section 不得消失、欄位不得減少）；去重與隱藏只准是 **render policy**。
- 稽核入口（Digest Viewer、Rule Registry）維持預設收合；`SHOWN_FOLDS` 既有三項不移除。
- `regime_arbiter.*_EXPLAIN` L0 逐字常數、`REGIME_SEE_WHY` 一句、`is_dev_only_text` 的治理參照句規則（Human UI 不畫 `DEC-\d+`／`macro_state.json`／反引號）。
- `?ui2_dev=1` 開發面維持；預設道 0 個 Preview 控制。
- 全站字樣表與 guard（`ALLOWED_STATUS_PREFIXES`、`CAPABILITY_STATUS_PREFIXES`、`check_axis_separation`）；Level 1 別名只在資料健康度 view 層。

---

## G. 驗收準則與施工邊界

### G.1 P6 施工後的驗收與測試

**驗收（DEC-130／Execution Spec §8）**：手機 390px、桌機 1440px 真實截圖＋Visual Fidelity；FAKE／Real × `cold／loaded／missing／stale／unavailable／not_evaluated`、signed_in／signed_out／unavailable；無水平捲動；缺值不補 0；Unavailable 才紅；`✅ 正常` 不用投資 Positive 綠；P3 VM／Evidence preservation、Risk Cap、System Action、Digest、Auth 守衛不退化；第一屏不因 P6 增高（資料健康度位於第一屏底之下）。

| 測試 | 現況（實查） | P6 定義 |
|---|---|---|
| **T_new_3** `test_T_new_3_me_page_has_layered_data_health_section`（`test_ui2_contract_teeth_pending.py:163`，strict xfail P6） | 斷言 `get_preview_page_vm("p4_me","loaded")` 的任一 `context.sections` 標題含「資料健康度」 | **轉綠定義**：VM 新增標題含「資料健康度」的 section（建議 `section_id="health"`，L1；Level 2／3 為 `health_detail`／`health_dev`，標題「來源與日期明細」「開發診斷」，避開 `為什麼／指標明細／原始資料／工程診斷`）。移除 `@_xfail("P6")`、登記 `GRADUATED_TEETH`、`test_pending_teeth_are_strict_xfail…` 的 `n == 3`（:356）與 `test_strict_xfail_count_is_three_after_p2`（:830）改為剩 T_new_7 的數量 |
| **T_new_8**（:199，strict xfail `_xfail130("P6")`） | 在 👤 DOM 以 regex 抓 `data-ui2-col="data-state"` 與 `"capability"`：兩者皆非空且**數量相等**；`data-state` 欄內不得含「尚未接線」 | **轉綠定義**：每列兩個標記元素都在（含手機疊卡版）；`⬜ 尚未接線` 只出現在 capability 欄；尚未接線列的 data-state 欄為「（不適用）」。DOM 標記名（暫擬 `data-ui2-col`、`data-ui2-health-row`）於 P6 定案時同步本測試（該測試 docstring 已預告）；regex 抓到第一個 `</` 為止，故單元格內若有巢狀 `<span>` 須確認抓得到文字——施工時以突變驗證 |
| 新增 teeth（建議） | — | (1) Data State 欄允許字樣＝{`✅ 正常`,`◷ 可能過期`,`◇ 資料未備`,`⛔ 來源不可用`, Not Evaluated 既有字樣, `（不適用）`}；(2) 突變：把 `⬜ 尚未接線` 塞進 data-state 欄必紅；(3) 同列 `state` 與 `capability=NOT_PROVIDED` 互斥（既有 `FieldVM` 已強制，`models.py:100-135`）；(4) 注入 key／token 樣式字串於 `detail`／錯誤碼 → Level 2／3 不得外露（過 `scrub_secrets`）；(5) Level 3 預設收合；(6) 掃描 Level 3 無 env var 名／`traceback`／`src.`／`.py`／`Exception`；(7) 👤 頁主 CTA ≤1 且（H-5=A）無登入鈕；(8) P3 baseline 對 `p4_me` 只增不減 |

**必須調整的現行測試（不得直接刪守衛，改成對等或更嚴）**

- **T-P6-1 詞彙衝突（新發現）**：`tests/test_ui2_p1_human_text.py:36 ENGINEERING_VOCAB` 含 `"尚未接線"`、`"接線"`，掃描四頁 VM 可見字串與 AppTest 整頁 markdown；但客戶 (13)(15) **明定** Level 1 Capability 欄為 `⬜ 尚未接線`／「接線」。施工必須把這組字樣改成**限區 allowlist**（僅資料健康度容器 `data-ui2-health` 內；其餘位置仍禁），並加 teeth 防止其他頁出現。Level 3 若含 `DEC-`／`macro_state` 等亦同（建議不含，避免擴大 allowlist）。**VM 掃描端 allowlist 以 section_id 為 `health*` 判定；DOM 掃描端才用 `data-ui2-health` 容器**（ENGINEERING_VOCAB 的 VM 測試走 `_walk_strings`，無 DOM 容器概念）。DG-20 降級的 `detail` 不得含 Capability 軸字樣；`_axis_violations`（`test_ui2_p1_human_text.py` ~:168-186）與 `check_axis_separation`(4)（`test_ui2_guards.py` ~:1212-1241）一併列入「必須同步調整」。登記候選 ID：`NUI2-P6-VOCAB-VS-CAPABILITY-TEXT`（待總管登記）。
- `tests/test_ui2_p3_evidence_preservation.py`：`EXPECTED_SHOWN_FOLDS`（:51）與 `_page.py:54 SHOWN_FOLDS` 同步新增 `("p4_me","health_detail")`、`("p4_me","health_dev")`；baseline 重建僅**新增** `health*` sections（`compare` 對既有 section／cards／first_screen 列數「減少」會報錯，故去重必須是 render policy）。
- `tests/test_ui2_batch3.py:465 _PRIMARY`、`:test_me_page_switches_account_in_the_real_app`：若 H-5=A，signed_out 在**頁面層**不再出現「Google 登入」CTA（VM 的 `primary_cta` 仍保留）；斷言改為「VM 層 CTA 不變＋頁面層出現指引句且無第二顆登入鈕」。
- `test_me_page_audit_surface_exception_does_not_allow_evidence_expanders`：新 expander 標題須避開 `為什麼／指標明細／原始資料／工程診斷`。
- `tests/test_ui2_active_contract_docs.py`：P6 完成補記（BACKLOG／PROJECT_STATE／HANDOFF／DEC）同步斷言。
- `tests/ui2_viewport/measure_viewport.py`：若量測 👤，更新量測點；**導覽餘裕 ≥160px 判準**原綁底部四格，DEC-134 後由抽屜批定義對等安全區——P6 不在第一屏增高，不碰該判準，**不得默默移除 viewport 檢查**。

### G.2 Model／Effort 邊界

| 範圍 | 建議 | 理由 |
|---|---|---|
| 兩欄表／總覽行／L1·L2·L3 容器／別名轉換／去重 render policy／桌機版面／FAKE 場景全五態／Real「未接線」列／測試與 CSS | **Sonnet 5.5＋Medium** | 純 presentation，欄位全取自既有 `FieldVM` |
| Real 讀點接 台股大盤（沿 `twii_card_spec`） | Sonnet 5.5＋Medium | 已有正式映射先例 |
| 新增 thin L3 唯讀 reader（9a 快取新鮮度、產業、基本面涵蓋率、門檻校準；欄位限既有） | Sonnet 5.5＋Medium，**但**屬「新 Real Feed 接線」：須擴 `real_feed` 讀點與 G2F 守衛、每接線批 ≤3 項並雙向驗證（Execution Spec §8.4／mapping） | 不新增欄位、不改 canonical；仍需獨立 QA |
| `retrieved_at`、source health、proxy／estimated 新欄位（DG-01／03／04／20）；`FreshnessInfo` 擴充 | **Opus 5.5＋High Gate** | 新資料 contract／VM schema 變更 |
| Auth（E 節 (1)–(6)） | **Opus 5.5＋High Gate** | `NUI2-AUTH-CONTRACT-GATE` |
| Risk Cap 輸入 provenance 呈現（DG-13）、System Action 輸入、Digest 補資料健康度區塊（DG-21） | **Opus 5.5＋High Gate** | SG-06／SG-07／`NUI2-DIGEST-DATAHEALTH-XREF` |
| 國際市場／VIX／US10Y／DXY／PMI／景氣 PORT | Opus 5.5＋High 或總管 PORT 批裁定（`NUI2-PORT-READINESS-L3`、SG-12） | 舊 L5／session 運算轉 L3，且受 SG-01 限制 |

### G.3 建議批次（撰寫組暫定，每批 ≤3 項；與 BACKLOG §5.1.26 P6 列對齊，不取代）

- **P6-a（純 presentation）**：① 👤 去重＋桌機 §5.2 兩欄（render policy）；② 資料健康度 Level 1 兩欄列＋總覽行（新 VM section、別名 renderer、FAKE 全五態、Real 未接線列＋台股大盤）；③ T_new_3／T_new_8 轉綠＋T-P6-1 allowlist 與新 teeth。
- **P6-b（承接與位階說明）**：① Level 2「來源與日期明細」容器與列；② 「市場位階（說明）」卡（依 H-2）與「系統資訊」卡（門檻校準）；③ Level 3「開發診斷」（遮罩）。
- **P6-c（接線，逐項 Gate／裁定）**：thin L3 reader（快取新鮮度、產業、基本面涵蓋率）≤3 項。
- **另案（Opus High）**：FIELD-GAPS 新欄位契約、Auth、Digest 資料健康度區塊、readiness PORT。
- **與抽屜批的關係**：P6 動 `src/ui2/views/me.py`、`components/html.py`、`scenarios.py`／`real_canonical._me`／VM、tests；抽屜批動 `shell/app.py`、`css.py`——`css.py` 兩批都會碰，**序列化**、不平行寫入；同一序列化清單另含 `tests/ui2_viewport/measure_viewport.py`、`tests/test_ui2_batch3.py`、`tests/test_ui2_contract_teeth_pending.py`、BACKLOG，以及 P7 的 `T_new_7`／`data-ui2-account-area`。

---

## H. 待客戶確認／裁示項（每項 A／B 與 AI 推薦；本文件不替客戶決定）

| # | 問題（一句話） | A | B | 推薦與理由 |
|---|---|---|---|---|
| **H-1** | 資料健康度 Level 1／Level 2 預設展開或收合？（Active Contract §11 撰寫組暫定；**客戶原文只規定 Level 3 預設收合**） | L1 展開、L2 收合 | L1 收合、L2 收合（只見總覽一行） | **推薦 A**：L1 是使用者可讀摘要，收起來頁面像空的；L2 多為 `⬜ 尚未提供`，預設展開會放大「缺欄」。見 D |
| **H-2** | 市場位階完整說明要不要有「使用者可讀版本」？（兩個 L0 逐字常數含 `DEC-074／075`、`macro_state.json`，Human UI 現不畫） | **改寫成使用者可讀版**放 Level 2「市場位階（說明）」；L0 常數與 teeth 不動、逐字續存 VM（Level 3 不放，避免擴大 allowlist） | 逐字**只放 Level 3**（開發診斷；需擴 allowlist，與 H-8 推薦理由相衝）；Level 2 只放 `REGIME_SEE_WHY` 一句（零新文字，但一般使用者看不到完整說明） | **推薦 A**：客戶 (20) 要的是「使用者可讀位置」，B 等於沒有；改寫須客戶確認語意。**撰寫組草稿（未經客戶確認，語意未驗）**：①「總經尚未載入：這一次使用中還沒有紅綠燈結果。可以按更新載入今日資料，但在正式的市場廣度（漲跌家數）資料來源接上前，載入後市場位階仍為未評估——由加權指數推估的代理值依客戶裁示只顯示、不計分，市場位階也不會改用另一套規則補出。」（比 L0 原句多了「只顯示」）②「總經未評估：缺真實市場廣度（漲跌家數）。由加權指數推估的代理值即使取得，也只顯示、不計分，因此健康分算不出來，市場位階一併未評估，也不會改用另一套規則補出位階。更新資料不會改變這個狀態，要等正式的廣度資料來源接上。」（刪去 DEC 編號、`macro_state.json`、「引擎」） |
| **H-3** | Data Gap（retrieved_at、來源健康、來源性質…）怎麼處理？ | P6 先以 `⬜ 尚未提供` 誠實上線，新欄位契約**另批**走 Opus High Gate | 先過 Gate 取得新欄位，再做 P6 | **推薦 A**：P6 不被新契約卡住；缺欄誠實可見，也符合「缺資料就說缺」。新契約批次登記 `NUI2-DATA-HEALTH-FIELD-GAPS` |
| **H-4** | `⛔ 來源不可用` 在資料健康度用什麼顏色？（Active Contract §11 撰寫組暫定：沿 Unavailable 紅） | 紅（沿全站 Unavailable 紅＝系統真錯誤；`⛔` 在本面為「來源不可用」新義） | 灰／琥珀（避免健康度頁滿版紅） | **推薦 A**：與 `CLAUDE.md` §1.A-4 一致（紅只給真錯誤、未載入為灰）；`ChipTone.DANGER` 現已如此（`html.py:20`）。風險：真有多個來源壞時整頁偏紅——那正是該提醒的事 |
| **H-5** | 👤 頁要不要保留自己的「Google 登入」按鈕？（登入鈕已在 rail／抽屜） | 不放；未登入時顯示指引句（手機「點左上角 ☰」／桌機「由左側『登入』」） | 手機保留一顆、桌機不放 | **推薦 A**：唯一符合「不得製造重複的主要登入流程」。B 需依視窗寬度切換，Streamlit 無法在伺服端判斷，CSS 隱藏會留下重複 DOM（測試與無障礙會視為兩顆）。代價：手機未登入者要先開 ☰ |
| **H-6** | 桌機資料健康度的版面位置？ | 沿 Wireframes §5.2「一般設定｜稽核」兩欄不動，**資料健康度整列在下** | 左欄放一般設定＋稽核、右欄放寬幅資料健康度 | **推薦 A**：最小差異，不動已核准的兩欄；兩欄表需要寬度，整列最好讀。代價：桌機順序是「設定｜稽核→健康度」，與手機「設定→健康度→稽核」不同（Active Contract §3.4 順序以手機單欄為準） |
| **H-7** | 市場位階（「判定結果」，非五態資料源）怎麼放進資料健康度？ | 不入兩欄表；放 Level 2 說明卡，兩欄表只放「市場廣度」等資料源列 | 入兩欄表，狀態欄寫 Not Evaluated／（不適用），判定 chip 另放 L2 | **推薦 A**：DEC-124 禁止把 Unable to Determine 併入 Not Evaluated；B 必須在狀態欄放五態以外的東西或誤填 |
| **H-8** | Level 3 內容是否限「遮罩後診斷碼／識別碼」？（Active Contract §11 撰寫組暫定，比客戶原文嚴） | 限遮罩後識別碼（資料集 id、讀取結果碼、規則分支 id） | 只依客戶原文清單禁曝險項（key／secret／env var 名／raw exception／traceback／module path／credential／內部堆疊），其餘開發資訊可放 | **推薦 A**：與 P1 詞彙 teeth 相容、避免擴大 allowlist；開發者真要更多資訊走 `?ui2_dev=1` |
| **H-9** | 兩欄表欄名是否附英文括號？（Active Contract 寫 `狀態(Data State)`、`接線(Capability)`） | 畫面只寫「狀態」「接線」；英文軸名只放 DOM 標記與文件 | 畫面保留英文括號 | **推薦 A**：英文括號屬工程詞；且「接線」二字須納入 T-P6-1 限區 allowlist |
| **H-10** | 總覽一行 `資料 N／M 正常` 的分母？ | M＝已接線列；未接線另計「另 K 項尚未接線」 | M＝全部列 | **推薦 A**：避免未接線項把比例永遠壓低（恆黃＝無訊號） |
| **H-11** | 正式 auth 契約前，桌機 rail、手機抽屜、👤 三處登入狀態怎麼顯示？（現況：預設 FAKE 道 `ui2_account` 預設 signed_in，👤 顯示「已登入（FAKE）」，rail／抽屜卻固定「⬜ 尚未登入」，三處不一致） | 三處由**同一固定占位來源**渲染（Real 與 FAKE 預設道相同）：登入鈕 disabled、原因句「登入與 Sheet 操作尚未開放」；狀態字樣「⬜ 尚未登入」（DEC-129 字面，需先完成 `NUI2-AUTH-STATUS-TEXT-GUARD` 擴字樣表）；FAKE 帳戶三態只留在 `?ui2_dev=1` 與 FAKE 場景 VM，預設道不再出現「已登入（FAKE）」（需改 `ui2_account` 預設值，待總管／客戶確認） | 同上，但狀態字樣用「⬜ 尚未提供」 | **推薦 A**：符合 DEC-129 字面與「同一 auth truth」 |
| **H-12** | TWII 來源字串含「每日更新」「歷史」字面（`TWII_SOURCE_TEXT`＝「本地加權指數歷史快取（來源 Yahoo，每日更新）」），資料健康度是否原樣呈現？ | 原樣（與 P2 SPEC 一致） | 另訂顯示名（需新文案） | **推薦 A** |

> 以上只是撰寫組暫定與推薦；H-1、H-4、H-8 對應 Active Contract §11 的三項撰寫組暫定，**維持 Pending，不得由本文自動升格**（第四項「🎯 跨季趨勢」與 P6 無關，不列）。

---

## I. 未驗與限制

- **單組撰寫，待獨立 QA**；本文所有「全稱式」說法（例：「全站唯一已有 provenance／proxy 正式欄位的鏈」「無統一 source health 欄」）是撰寫組 grep 的結論，**未經第二組複驗**，只能當待驗事項。
- **px 全部未實測**、無截圖；手機長清單高度與稽核落在第二屏之下為估計。
- 僅執行 AppTest 取 👤 現況；各 service 的回傳欄位以**讀碼**為準，**未實際呼叫**。
- 未驗：`cl_data['intl']`／session `macro_info` 的實際鍵集與 `attrs` 形狀（只讀 L1 docstring 與 return）；`get_sector_flow_view` 的參數組合是否一定不觸發 Sheet 讀取；`get_fundamental_prescreen` 成本與副作用；`macro_helpers.compute_five_bucket_summary` readiness 的完整欄位（只讀註解與 `_rec`）；legacy `compute_tab_coverage`（L5）輸出語意未逐欄對帳。
- `data_cache/metadata.json`、`fundamentals/latest.json` 的數值為 2026-11-04 測量值（會漂移）。
- `◷ ◇ ⛔ ✅ ⬜` 在 Android／iOS／Windows 字型的呈現未驗（顏色不是唯一載體，文字同列）。
- Streamlit 1.56／1.59 下 `st.expander`／`<details>` 的預設狀態保留、AppTest DOM 掃描收合內容的行為：僅依既有測試推論，未專門驗證。
- Digest 是否涵蓋資料健康度：**否（`decision_digest_builder.py` 只有總經健康分 `market.health`）**；與資料健康度 UI 的兩個 projection 同源問題見 DG-21。
- 本文未改任何其他檔；BACKLOG／DECISIONS／PROJECT_STATE／HANDOFF 的落盤（含候選 ID `NUI2-P6-VOCAB-VS-CAPABILITY-TEXT`、DG-01～21 登記）由總管統一同步。
