# Phase 3 共用視覺元件｜文字線框草稿＋客戶裁示表（Phase 3 步驟 0）

- **狀態**：**草稿 rev3（rev2 經複審後再修訂），待客戶拍板**（出處：Migration Plan §15.6「不論共用元件是否掛頁，寫 UI code 前先出文字線框」；契約 §22；`CLAUDE.md` §-1.5.D v3 §03-2 ① 草稿先行）。**本檔核准前不得寫任何 UI code**；客戶不裁示的項目依各題「不裁示預設」（見 §6 開頭）。
- **修訂紀錄（rev2，2026-10-30，有意識的更新，不是漏刪；決策者 AI 總管（內部））**：rev1 的裁示表 D1～D9 經 QA-B（合規）／QA-A（事實）兩組獨立檢視後重編為 **D1a、D1b、D3、D5、D6、D8、D10**（七題）；對應見 §6 開頭「題號對照」。D2 併入 D1b；D4、D9 移除（契約／內部自決已定）；D7 改為內部先量測、量到真值後才另送。
- **修訂紀錄（rev3，2026-10-30，有意識的更新，不是漏刪；決策者 AI 總管（內部））**：依複審 N1～N7 修訂——裁示表題幹與選項去除內部代號、D8 技術前提移到 §3.9／§7、出處引用移到文末腳註（N1）；tile 內允許一顆「窗口」chip 並補 chip 合計上限（N2，§3.5／§3.6／M2／M19）；D6 補契約字面調整註記並新增 B 方案冷啟動線框（N3）；D8 改述為舊頁程式註解記載的偏好（N4）；「不等距」改放摺疊「限制」段並補邊界說明（N5）；補 D10 (b) 已載入線框與合併護欄 chip 的 kind 規則（N6）；D1b／D6 題幹補強（DEC-109 二十四、DEC-108 轉交註記）。修訂版未經第三輪獨立驗證。
- **日期／基準**：2026-10-30；main `2acf4ee`（`src/`、`tests/` 乾淨）。量測日一律 2026-10-30，不寫行號（`CLAUDE.md` §8.2.A.0 規則 1）。
- **決策來源**：Phase 3 清單＝客戶 DEC-109 三十一（只管 Phase 3 清單，**不是**「線框先行」的出處；「線框先行」出處見上方「狀態」）、`CLAUDE.md` v3 §03-2 ①；元件規格、量化上限、R8～R10、R15、W1＝Presentation Contract §4、§6、§8、§10、§11、§14、§19、§20、§22（客戶原文＋DEC-110 內部決定）；本檔的方案設計、推薦、API 草案＝**AI 總管內部（DEC-110 同層）**，客戶可推翻。
- **上位**：`CLAUDE.md` > `PROCESS.md` > `PROJECT_RULES.md`＋`docs/governance/*` > 最新有效 DEC > Presentation Contract／Migration Plan／Visual Fidelity Gate > 本檔。本檔**不改**契約與 DEC 一個字，只在契約留白處提方案。
- ⚠️ **揭露（`CLAUDE.md` §-2 規則 6）**：rev1 為**單一撰寫組**產出；rev2 的修訂依據是兩組獨立 QA 的發現，rev3 依複審發現，**修訂版本身尚未經下一輪驗證**；§2 的 FACT 來自讀碼／grep／執行 `page_css()`／靜態掃 Streamlit 1.56.0 wheel 原始碼，**沒有跑瀏覽器、沒有實機**；§3 的 px 數字是「依契約 §19 上限＋CJK 字寬估算」的**預算**，不是量測。所有「沒有／只有／全部」的全稱句是待驗事項。示意文字與數字一律標 ※示意，**⛔ 不得被引用為投資結論**。

---

## §1 範圍與不做清單（Scope Guard）

### 1.1 Phase 3 做什麼（本草稿核准後的步驟 1 之後才做）

| # | 項目 | 性質 | 畫面影響 |
|---|---|---|---|
| a | 純字串模組（建議 `src/ui_v2/compact.py`，不 import streamlit、不 import `src.data`／`src.services`）：metadata chip、chart header、Missing placeholder、compact KPI tile、sparkline、small multiples 版面、Top-N 切片、segmented 選項標準化、`compact_css()` | 純加性新模組 | **0**（沒有任何頁面 import 它） |
| b | `_ui_kit` 薄封裝：公開 status chip、`render_fold`（證據摺疊）；`Basis` 兩份合併為超集（H31，舊名 alias） | 加性 | **0**（既有 caller 輸出逐 byte 不變，沿用 Phase 2 golden 手法） |
| c | tokens 收斂（`P1R-TOKENS-CONVERGE`）——**範圍取決於裁示 D1a／D1b**；推薦方案＝只加幾何 token（含契約 §14.2 已定的 14px 圓角 token，只新增、Phase 3 不套用）、不改任何既有色值 | 加性（推薦方案） | 推薦方案 **0**；D1b=A 方案會動既有頁 |
| d | 站殼間距子項——**先做內部量測（步驟 1 前置工作項，無需客戶）**；量到真值後才另送客戶「A 不做／B 最小」，不核准則不做（見 §3.11） | 動 `app.py`（僅在核准後） | 全站（nav4 模式）第一屏上緣 |

### 1.2 不做清單（⛔）

- ⛔ **不掛任何頁**：`page_market`／`page_target`／`page_hold`／`page_me`／`page_today` 等一個字不動；元件首個 caller 在 Phase 4（📊）。
- ⛔ **不改既有頁畫面**：`markup.page_css()` 輸出逐 byte 不變（實測基準見 §2.5）；`compact_css()` 與 `page_css()` 分開，由日後掛頁的 phase 自行注入。
- ⛔ 不新增資料源、公式、門檻、TTL、投資語意；不碰 Risk Cap、EPS×PE、趨勢定義（`NOT_DEFINED`「⬜ 尚未定義」維持）；不碰 Decision Digest／One AI Brain（Phase 7；已確認 `DECISION_DIGEST_CONTRACT` §6／`ONE_AI_BRAIN_BOUNDARY` §3 的「UI Top-N／收合不影響 Digest」與本 phase 只提供**顯示切片**一致）。
- ⛔ 不改 `BADGES`（封閉 11 種，禁第 12 種）、`UI_STATE_META` 十態、`MAX_COLS=3`、`Note` 契約、`V2_SHORT_ROWS`；不改 `PAGE_LABELS`／導覽殼語意／legacy 入口；不新增或刪除頂層頁（DEC-109 十）。
- ⛔ 不處理 W2～W9（見 §4）；`CV1-DR-12`（KPI 欄數）**不在本 phase 判定**，tile 的「列欄數」維持待裁。
- ⛔ 不在 app 內掛預覽頁、不增減頂層頁（DEC-109 十）；元件預覽以離線 HTML＋截圖附 PR（內部自決；想要 app 內預覽須另案，屬 IA 邊界）。
- ⛔ 不使用 floor 1.56 上未實跑驗證的 API 於 production 路徑（`P1R-FLOOR-156-API`）。

### 1.3 站殼子項單獨列

站殼間距是本 phase **唯一可能改現有畫面**的項目，且 `app.py` 受 `tests/test_batch_z60.py` 91 檔目錄指紋守衛、與 legacy 模式共用。**先量測、量後才另送客戶、獨立 PR、獨立全 Gate**（§5.1）；不核准就整項不做，不影響 a～c。

---

## §2 現況實測（2026-10-30，main `2acf4ee`）

> 標記：**FACT**＝讀碼／執行／grep 可重現；**INFERENCE**＝推論。方法限制見 §7。

### 2.1 既有共用層盤點（FACT）

| 面 | 現況 |
|---|---|
| `src/ui_v2/tokens.py` | `DARK`／`LIGHT` 同一組 token 名；狀態色 6 對（green／amber／red／blue／grey／neutral）；`SERIES_DARK`／`SERIES_LIGHT` 7 槽（0 consumer）；間距 `--sp-1…8`＝4／6／8／10／12／16／22／26px。`TBD` 哨兵機制保留。 |
| 客戶裁示色（檔內註解自陳） | `--sig-neutral` dark `#8fa3b8`（客戶 2026-09-21）、`--sig-neutral-bg` dark `#26313d`（客戶 2026-09-21 採納總管建議值）；`--cta-primary-bg` dark `#1f6feb`／light `#044cb6`（客戶 2026-09-22）。⚠️ `--sig-neutral`／`-bg` 的 **light 值是 AI 總管選的 B 組、檔內明寫「可被客戶一句話推翻」**，不是客戶指定值——所以 W1 的「客戶裁示色」其實分兩級（**INFERENCE**：註解文字是 FACT，但「哪些 token 屬客戶裁示」的歸屬判斷為單組讀碼，契約 §14.2 亦自陳未經第二組驗證）。 |
| `src/ui_v2/components.py` | `CARD_BASE` 圓角 2px；`CARD_TIERS` t1～t4（內距 15/17→5/9、t4 虛線）；`BADGES` **11 枚封閉**（`BADGE_BASE` 圓角 3px、字 11.5px、內距 1/7）；`CARD_VALUE` 24px 等寬；`BREAKPOINTS` 640／880；`MAX_COLS=3`。 |
| `src/ui_v2/markup.py` | `page_css(mode)` 只含 root／grid／card／badge／fold／breakpoint 規則。`card_html` 已有可選參數 `chips`／`summary`／`fold_label`／`spark`（Phase 2 步驟 1），**production caller＝0**，且 **`.blk-chips`／`.blk-chip`／`.blk-summary`／`.blk-spark` 沒有任何 CSS**（grep 僅命中 docstring 與 HTML 組裝處）。摺疊字樣 `FOLD_SUMMARY_TEXT`＝「▸ 詳細」（純 CSS checkbox 機制）。 |
| `src/ui_v2/blocks.py` | `PAGES` 登記處；`tier_for_block` 對未登記 block 拋 `KeyError`——`card_html` 因此**綁頁**，不能拿來做未掛頁的元件預覽。 |
| `src/ui/views/_ui_kit.py` | `_chip(text, color)` **私有**（inline style 膠囊：padding 1/8px、圓角 999px、字 11.5px、框色＝傳入色＋55 透明），僅 `render_card` 內 2 處用；`grid()` 夾 `MAX_COLS`；`single_submit_form(options_label)`、`render_card(compact)`；`assert_signal_text_clean` 以「`UI_STATE_META` glyph ∪ `LEVEL_EMOJI`」子字串比對。**沒有** `render_fold`、公開 `status_chip`。 |
| `_market_blocks` ／ `_target_blocks` | 各有一份 `Basis`＋`render_basis`（`st.expander("🔍 查看依據", expanded=False)`）。**兩份不只欄位名不同**：市場版 6 欄全必填、欄標「使用的資料／資料日期／規則／計算結果／missing／confidence／availability／AI 是否參與」，`AI_NOT_INVOLVED`＝「不參與（本區由規則／資料顯示產生，本頁沒有 AI 呼叫）」；標的版第一欄叫 `sources`、`ai` 有預設、欄標「規則」、`AI_NOT_INVOLVED`＝「否（本區是既有規則與資料的直接呈現，沒有 AI 參與）」。合併超集要保兩邊字串各自 byte 不變（Migration Plan §12.4 的同一判斷）。 |
| `st.line_chart` 使用處 | `_market_blocks.render_chart_a`（1 張，預設高度）、`render_chart_b`（每系列 1 張，`INTL_GROUPS` 3 組共 5 系列，群組以 `st.markdown` 粗體小標分隔）；`page_market`（1 處，位於 16 燈明細區）；legacy `app_render` 有 `col.line_chart(..., height=80)` 先例。 |
| 內嵌 SVG 先例 | `src/ui/render/app_render.py` 的儀表（`<svg viewBox="0 0 200 110">`）——repo 已有在 HTML 內嵌 SVG 的做法；**新 UI 層（`src/ui_v2`、`src/ui/views`）沒有** sparkline／小倍數／Top-N 切片／segmented 的共用實作；**legacy 另有三份 sparkline 實作**：`src/ui/render/macro_ui_components.sparkline`、`shared/macro_card.make_sparkline`（plotly）、`src/ui/tabs/macro/helpers._make_radar_sparkline`（grep 結果，非窮舉；皆非「內嵌 SVG 純字串」形態，不直接沿用）。 |
| 既有 Top-N 先例 | `HERO_RISK_MAX_ITEMS=3`＋`HERO_RISK_MORE_FMT`「另 {n} 項見圖 D」（`_market_blocks`）；`page_find.TOP_N_OPTIONS=(20,50,100)`／`DEFAULT_TOP_N=50`（L3 請求參數，維持）；`_target_blocks.SCREEN_EXPANDER` `expanded=True`（DEC-107，維持）。 |
| 既有 Missing 字串 | `NOT_LOADED`「⬜ 尚未載入，請按更新」、`NOT_DEFINED`「⬜ 尚未定義」、`DATA_DATE_NOT_PROVIDED`「⬜ 資料日未提供」、`UNDETERMINED`「⬜ 無法判定」、`INSUFFICIENT_TEXT`「⬜ 資料不足／無法判定」、`CHART_C_EMPTY`；L0 `UI_STATE_META`（`⬜ 尚未載入`、`▨ 無資料`、`🔴 取得失敗`…）。**Phase 3 元件只能引用它們，不可另造字串。** |
| 逐字客戶句 | `CHART_A_SAY`（31 字）、`CHART_B_SAY`、`CHART_A_MA_DISCLAIMER`「均線為參考，不等於正式台股趨勢判斷。」（18 字，含標點）、`FX_PARTIAL_TEXT`、`FX_TP_UNJUDGED_*`、`ZONE1_SORT_NOTE`。 |
| `TWII_SOURCE_TEXT` | 「本地加權指數歷史快取（來源 Yahoo，每日更新）」——**長句，不是 chip 字**；chip 的 `來源` 要用 `shared/price_asof_label.SOURCE_DISPLAY` 的短名（例 `Yahoo`），不得截斷長句。 |

### 2.2 Phase 3 清單項：已存在 vs 全新（FACT）

| Phase 3 項 | 狀態 | 說明 |
|---|---|---|
| metadata chips（asof／source／window／stale…） | **全新** | 只有 `card_html` 的 `<span class="blk-chip">` 殼（無 CSS）與 `_chip` 私有函式；沒有 kind 封閉集合。 |
| status chips | **部分** | 狀態詞彙已在 `UI_STATE_META`／`BADGES`；缺公開、與 meta chip 同幾何的 chip builder。 |
| chart header（標題→chip→1 句→圖→摺疊） | **全新** | 現況 `render_chart_a`：標題→1 句→圖→多行 caption／粗體聲明／結論→依據，順序與數量都不同。 |
| evidence expander | **部分** | `Basis`×2＋「🔍 查看依據」；主圖摺疊字樣 `▸ 為什麼／來源／限制／去哪補` 全新。 |
| Missing placeholder | **部分** | 字串齊全，**沒有共用的「圖槽」元件**（圖槽高度、不畫線點）。 |
| compact KPI card | **部分** | `card_html` 參數在、CSS 無；無獨立 tile。 |
| sparkline | **全新** | — |
| small multiples | **全新** | 現況＝每系列一張 `st.line_chart` 垂直疊放。 |
| Top-N 切片 | **部分** | 有先例常數與字樣，無共用切片器。 |
| segmented switcher | **全新（新 UI 層）** | repo 內目前**只有註解**提到 `st.segmented_control`；legacy `tab_macro_v2` 刻意用 `st.radio(horizontal=True)`（user 2026-08-27「視覺一致優先」）。 |
| tokens 收斂 | **部分** | 見 §3.10。 |
| 站殼間距 | **全新** | 見 §3.11。 |

### 2.3 技術限制（FACT／INFERENCE）

1. **FACT** 原生 `st.line_chart`（Vega）**不能嵌進 raw HTML**。因此：Primary 主圖＝原生圖（需要軸、互動）＋上方 HTML header＋下方 `st.expander`，三者放同一個 `st.container(border=True)`；sparkline／小倍數／mini＝**內嵌 SVG**（由 `compact.py` 產出，版面用 CSS grid）。
2. **FACT** `st.columns` 在手機塌單欄（契約 §14.1 已登記）——小倍數需要「手機 2 欄」，故用 HTML／CSS grid，不用 `st.columns`。
3. **FACT**（靜態掃 `streamlit==1.56.0` wheel 原始碼，**未跑 runtime**）：`st.segmented_control`、`st.pills`、`st.badge`、`st.html`、`st.metric(chart_data=)`、`st.bar_chart(horizontal=)`、`st.line_chart(height=)`、`st.expander(icon=)`、`st.container(height=)` 在 floor 1.56 的原始碼都存在。**INFERENCE**：存在不等於行為一致；`P1R-FLOOR-156-API` 要的 floor wheel 實跑仍未做。守衛 `tests/test_macro_v2_tab.py::TestStreamlitFloorCompatibility` 從 `requirements.txt` 反解 floor（現為 `>=1.56.0,<1.60.0`）並 AST 掃超出 floor 的 API。
4. **FACT** 表單內 `st.expander` 在沙箱 1.59.2 可用（Migration Plan §13.5）；floor 1.56 未驗。
5. **FACT** Streamlit expander body 每次 rerun 都執行（R10）——`render_fold` 內容只能是已算好的字串，不得放重運算。

### 2.4 現況 Visual Gap 與 Phase 3 相關的量測（FACT，Phase 1 baseline，夾具、已載入）

頁面 H2 起於 y=223（1440 與 390 皆是；持股頁 207）；站標帶占 y 128～159；約占第一屏 25%／26%。市場頁「主要判讀句頂端」相對 H2 約 +998（契約 Q11 ≤ +200／+260）。（出處：`VISUAL_GAP_AUDIT_2026-10-29.md`；Streamlit 1.59.2；**未重量**。）

### 2.5 今天頁 CSS 必須 byte-identical 的基準（FACT，本日執行 `markup.page_css()`）

| mode | 長度 | sha256 前 16 碼 |
|---|---|---|
| dark | 6391 | `432d88ab064e5144` |
| light | 6391 | `2ad61fd99eea422c` |

- 注入點（grep）：`page_today`、`page_find`、`page_hold`、`page_inspect`、`page_why`、`_target_blocks` 皆以 `page_css(mode)` 加各頁自有 CSS 注入。→ **新元件 CSS 不得進 `page_css()`**；`compact_css()` 另供，掛頁時各頁自行附加（與現有「每頁附加一段頁面 CSS」同模式）。
- 其他不得動的 golden：Phase 2 的 `card_html`／`single_submit_form`／`render_card` golden；`tokens.DARK`／`LIGHT` 映射（推薦方案下不變）。

### 2.6 三個背景色來源（FACT，D1b 的背景資訊）

| 來源 | 頁底色 |
|---|---|
| `.streamlit/config.toml` `[theme]`（Streamlit 原生） | `#0e1117`，次級 `#161b22`，主色 `#1f6feb` |
| `src/ui_v2/tokens.py` `--paper` | `#0e141b` |
| blueprint `market.html` `--bg` | `#0a0e16` |

三者本來就不同，與 Phase 3 無關；**統一任何一個都會改全站外觀**。

---

## §3 元件逐項文字線框

### 3.0 閱讀約定與共通預算

- 桌機框＝主欄示意，**非等比**；高度以 px 標註。手機框＝390 寬、左右 16px 邊距（內寬 358px）。
- `( … )`＝chip；`░░`＝圖區（原生圖或 SVG）；`▸`＝摺疊入口；`※示意`＝示意數字／文字，非實際資料。為避免全形對不齊，框只畫左線。
- 所有示意文案優先使用**既有常數**（§2.1），沒有既有常數的才用 ※示意。
- CJK 字寬以 1em 估算；`px` 為預算（INFERENCE），截圖 Gate 時以實量為準。

**共通尺寸與密度（契約 §19／§2，Visual Gate 對照）**

| 項 | 上限 | 對應 Gate |
|---|---|---|
| Primary 圖本體 | 桌 ≤ 220px／手 ≤ 140px | A6 |
| small multiple／mini 圖 | ≤ 96px／格；手機 2 欄 | A6 |
| sparkline | ≤ 64px 高，無軸無圖例 | A6 |
| KPI tile 高 | 96～160px，同列高差 ≤ 16px；手機首列整塊 ≤ 340px | A4、A5、A11 |
| 主卡卡面字數 | ≤ 60 字（客戶原句另計、不截） | A4 |
| 主值 | ≤ 12 字（超過改 chip）——⚠️ 見 §3.5 手機 2 欄寬度註 | — |
| 1 句 | ≤ 32 字（客戶原句豁免） | V4（頁級 ≤1 句另計） |
| chip 文字 | ≤ 12 字／顆（逐字客戶句豁免；手機可換行） | 契約 Q9／§6（≠ Gate V8；V8 管 chip 文字化＋紅色／頻道） |
| 圖 header 的 chip | 3～5 顆（契約 §4；圖 A 的 6 顆見 D10） | V3 不計 metadata |
| 圓餅／donut | Phase 3 **不提供**（B6） | V5 |

**單一 Primary 的垂直預算（INFERENCE）**：桌機＝標題 24＋chip 列 28＋1 句 20＋圖 ≤220＋摺疊 32＋內距 24 ≈ **348px**；手機＝24＋chip 列 52（2 行）＋1 句 40（2 行）＋圖 ≤140＋摺疊 32＋內距 24 ≈ **312px**（占 844 屏高 37%，< Gate A11 的 50%）。

---

### 3.1 metadata／status chips

**用途**：取代每張卡重複寫的「資料來自…目前資料日…」（契約 §6）。獨立家族，**⛔ 不進 `BADGES`、⛔ 不走訊號文字頻道**。

**與既有的關係**

- 狀態詞彙（`⬜ 尚未載入`、`▨ 無資料`、`⛔ 未接線`、`◧ N／M 計入`、`⟳`／`⊘`、`🔴 取得失敗`，即 `UI_STATE_META` 十態）**直接讀 `UI_STATE_META`／既有徽章字**（同 `BADGES` #11 手法），不另造符號；chip 只是同字不同幾何（膠囊）。
- **`unavailable` kind 不另造 chip 樣式**：契約 §6 表已定「沿用既有徽章族」——`⛔ 未接線`（`UI_STATE_META[UI_UNWIRED]`）、「尚未提供」沿用 `🤖 AI 投資總結：⬜ 尚未提供`。實作上走 `status_chip(ui_state)`，不走 `meta_chip`；`META_KINDS` 的 `unavailable` 條目只登記「委派給 status_chip」，不含自有文字。
- 契約 §6 表的其餘 kind（`asof`、`asof_missing`、`source`、`retrieved_at`、`window`、`readable`、`stale`、`freshness`、`coverage`、`not_defined`、`not_approved`、`estimated`、`proxy`、`imputed`、`data_quality`、`fx_partial`、`fx_tp`、`pretax`、`ai`）＝**封閉集合常數**，未登記 kind → `ValueError`（M2）。**M2 對帳規則**：`META_KINDS` 的鍵集合必須與契約 §6 表的 kind 欄（含 `unavailable`）逐一相等；測試從契約表內容抽 kind（或測試內以常數釘住並註明出處），契約表與常數任一方變動而另一方未同步 → 紅燈（呼應 `CLAUDE.md` §8.2.A.0 規則 3）。
- **合併護欄 chip 的 kind 規則（D10 (b) 的配套，N6）**：合併 chip **仍屬護欄單一族（tone=guard），不新增 kind**；文字＝兩句**逐字串接**（中間以全形空格），各句字不改、不截；`Chip` 以 `parts` 記錄被併入的各原 kind（例 `not_defined` 與逐字護欄句的 kind），只有護欄族 kind 可互相合併，其他族傳入 → `ValueError`。M2 對帳對 `parts` 逐一核對（每個 part 的 kind 都必須屬 `META_KINDS`），合併 chip 本身不另佔 `META_KINDS` 條目；排序與溢出時視為 1 顆護欄 chip（計入外露上限 1 顆）。
- 訊號文字頻道不碰：chip 走獨立 HTML；紅色只給 `failed`；`stale`＝琥珀 ⚠；`readable` 只在 live 態；degraded／partial 不得掛 ✅。

**chip 排序與溢出規則（契約 §4 的可執行化）**：優先序＝**語意護欄 chip**（`not_defined`、`not_approved`、`fx_*`、`data_quality`、`estimated`／`proxy`／`imputed`、逐字客戶句）＞ **狀態 chip**（readable／stale／freshness／unavailable／missing）＞ `asof` ＞ `window` ＞ `source` ＞ `retrieved_at`。超過 5 顆時**由低優先序往下移入摺疊「來源」段**；護欄 chip 本身超過 5 顆 → `ValueError`（不靜默丟；先嘗試依 D10 (b) 合併）。

⚠️ **排序與客戶範例順序不同（明說）**：客戶 DEC-109 五的範例順序是 `資料日 → 來源 → 窗口 → ✅ 可讀`（護欄 chip 範例中沒有）。本檔的排序是「護欄＞狀態＞asof＞window＞source」，是**溢出時的移出優先序**（誰最後被移走），契約 §4「語意護欄 chip 優先保留」的可執行化；**不一定等於視覺由左到右的順序**。視覺順序是否照客戶範例（資料日→來源→窗口→可讀，護欄置於其後或前）屬 Phase 4 線框確認事項，本草稿的線框為示意。來源被移出的情形見 D10。

**桌機 1440×900（chip 列，寬約 600px、高 24～28px）**

```
冷啟動（未載入）
│ ( ⬜ 尚未定義 )  ←  護欄 chip；「⬜ 尚未載入」由圖槽／主值槽本身承載（二選一，見 3.4），chip 列不重複
│                          （若該處沒有槽，才由 chip 列承載 ( ⬜ 尚未載入 )）；不放資料日／窗口
已載入（live）
│ ( 🕒 資料 10/28 ) ( 來源 Yahoo ) ( 近 252 日 ) ( ✅ 可讀 )      ※示意
已載入（過期）
│ ( 🕒 資料 10/21 ) ( ⚠ 過期 7 天 ) ( 近 252 日 )                   ← 琥珀，不是紅
系統真錯誤
│ ( 🔴 取得失敗 )  ＋ 1 句原因（句子不在 chip 內）
```

**手機 390×844（內寬 358px；換行，不橫捲）**

```
冷啟動
│ ( ⬜ 尚未定義 )                                        ← 1 行 ≈ 26px（未載入字樣在槽內）
已載入（含逐字護欄）
│ ( 均線為參考，不等於正式台股趨勢判斷。 ) ( ⬜ 尚未定義 )  ← 逐字句獨占較寬，可自行換行
│ ( 🕒 資料 10/28 ) ( 近 252 日 ) ( ✅ 可讀 )                ← 2 行 ≈ 52px
```

**外觀（取決於 D3）**：推薦方案＝三族並存——資訊 chip（資料日／來源／窗口）＝外框膠囊、次要墨色；狀態 chip（✅／⚠／⬜／⛔）＝淡底膠囊（綠／琥珀／灰），一律 icon＋字；護欄 chip＝**實線粗框**膠囊（與資訊 chip 一眼可分，且不能被收進摺疊）。⚠️ 護欄**不採虛線**的原因見 D3：repo 內虛線已有「低層級／未接線／示意、未啟用」的語意。顏色全取既有 token；護欄樣式是可被客戶推翻的選項。

**API 草案（內部，可調）**

```python
# src/ui_v2/compact.py  —— L5 純字串，無 streamlit
META_KINDS: Final[Mapping[str, "MetaKindSpec"]]            # 契約 §6 表的封閉集合
@dataclass(frozen=True)
class Chip: kind: str; text: str; tone: str  # tone ∈ {"info","guard"} ∪ UI_STATE_META 十態鍵（不自訂第二套狀態詞彙）
def meta_chip(kind: str, value: str | None = None, *, verbatim: str | None = None) -> Chip
def status_chip(ui_state: str, *, n: int | None = None, m: int | None = None) -> Chip  # 讀 UI_STATE_META 十態；tone 對應十態（見 3.4）
def chips_html(chips: Sequence[Chip], *, max_chips: int = 5) -> tuple[str, tuple[Chip, ...]]  # (html, 溢出者→摺疊)
```

---

### 3.2 chart header（標題→chip 列→1 句→圖→摺疊）

**固定順序**（契約 §4，M7）：標題（既有常數，不改字）→ chip 列（3～5）→ 1 句 → 圖 → 恰一個摺疊入口。⛔ 圖上方放整篇說明。

**桌機 1440×900（Primary，以圖 A 為例；字串皆既有常數，數字 ※示意）**

```
冷啟動
│ 圖A 🇹🇼 台股趨勢
│ ( ⬜ 尚未定義 ) ( 均線為參考，不等於正式台股趨勢判斷。 )      ← 護欄 chip；「尚未載入」只寫在圖槽內（二選一）
│ 看台股目前是在長期上升、整理還是轉弱；趨勢與短期波動分開判斷。
│ ┌ 圖槽 220px（Missing，見 3.4）────────────┐
│ │            ⬜ 尚未載入，請按更新            │
│ └─────────────────────────────────────────┘
│ ▸ 為什麼／來源／限制／去哪補
已載入
│ 圖A 🇹🇼 台股趨勢
│ ( 均線為參考，不等於正式台股趨勢判斷。 ) ( ⬜ 尚未定義 ) ( 🕒 資料 10/28 ) ( 近 252 日 ) ( ✅ 可讀 )
│ 看台股目前是在長期上升、整理還是轉弱；趨勢與短期波動分開判斷。
│ ░░░░░ 原生折線圖（指數＋均線水平參考線），高 ≤220px ░░░░░
│ ▸ 為什麼／來源／限制／去哪補         ← 預設收合；若 D10=(a)，「來源 Yahoo」在此段；D10=(b) 則來源外露（此示意畫的是 (a)）
```

**D10=(b) 版已載入（桌機；外露 5 顆：資料日、來源、窗口、可讀＋合併護欄；※示意）**

```
│ 圖A 🇹🇼 台股趨勢
│ ( 🕒 資料 10/28 ) ( 來源 Yahoo ) ( 近 252 日 ) ( ✅ 可讀 )
│ ( 均線為參考，不等於正式台股趨勢判斷。　⬜ 尚未定義 )   ← 合併護欄 1 顆（粗實線框，兩句逐字）；桌機寬度不足時整顆換到第 2 行
│ 看台股目前是在長期上升、整理還是轉弱；趨勢與短期波動分開判斷。
│ ░░░░░ 原生折線圖 ≤220px ░░░░░
│ ▸ 為什麼／來源／限制／去哪補         ← 來源段仍列完整來源說明（外露 chip 不取代摺疊內容）
```

**手機 390×844**

```
冷啟動
│ 圖A 🇹🇼 台股趨勢
│ ( ⬜ 尚未定義 )
│ ( 均線為參考，不等於正式台股趨勢判斷。 )
│ 看台股目前是在長期上升、整理
│ 還是轉弱；趨勢與短期波動分開判斷。
│ ┌ 圖槽 140px ┐  ⬜ 尚未載入，請按更新
│ ▸ 為什麼／來源／限制／去哪補
已載入
│ 圖A 🇹🇼 台股趨勢
│ ( 均線為參考，不等於正式台股趨勢判斷。 ) ( ⬜ 尚未定義 )
│ ( 🕒 資料 10/28 ) ( 近 252 日 ) ( ✅ 可讀 )
│ （1 句，2 行）
│ ░░░░ 原生折線圖 ≤140px ░░░░
│ ▸ 為什麼／來源／限制／去哪補
D10=(b) 版已載入（手機；合併護欄換行，逐字不變）
│ 圖A 🇹🇼 台股趨勢
│ ( 🕒 資料 10/28 ) ( 來源 Yahoo )
│ ( 近 252 日 ) ( ✅ 可讀 )
│ ( 均線為參考，不等於正式台股趨勢判斷。
│   ⬜ 尚未定義 )                      ← 1 顆、2 行；chip 列合計約 3 行 ≈ 80px
│ （1 句，2 行）
│ ░░░░ 原生折線圖 ≤140px ░░░░
│ ▸ 為什麼／來源／限制／去哪補
```

**設計發現（升為客戶裁示 D10）**：圖 A 的「客戶範例（DEC-109 五）4 顆（資料日／來源／窗口／可讀）＋2 顆逐字護欄（`CHART_A_MA_DISCLAIMER`、`⬜ 尚未定義`）」＝6 顆 > 契約 §4 的 3～5 顆。契約機械規則（護欄以外移入摺疊）會讓 **`來源` 落在摺疊「來源」段**，這與客戶範例把「來源」列為外露 chip 不同；到底接受哪種，是客戶看得見的取捨，故不再當成已決定事項，改列 D10（三個方案）。

**readable 與 ⬜ 並排（Phase 4 線框待處理）**：圖 A 的「✅ 可讀」（資料讀得到）與「⬜ 尚未定義」（趨勢結論尚未定義）並排在同一 chip 列時，讀者可能誤讀為矛盾或誤把「可讀」當成「趨勢可信」。本草稿不判；兩者的措辭與是否同列，留 Phase 4 線框（登 BACKLOG `P1R-P3-READABLE-VS-UNDEFINED`）。

**摺疊四段（固定，不適用寫「—」並說明）**：為什麼（`Note.why`／判讀說明）｜來源（source、as_of、TTL 說明引用 `shared/ttls.py`、被擠出的 chip）｜限制（窗口、口徑、估算／代理）｜去哪補（`Note.where`、`V2_EXIT_PHRASES`／`NO_EXIT_MARKER`）。

**API 草案**

```python
def chart_header_html(*, title: str, chips: Sequence[Chip], say: str | None, max_chips: int = 5) -> tuple[str, tuple[Chip, ...]]
# 回傳 (header HTML, 溢出 chip)；溢出 chip 由呼叫端交給 render_fold 的「來源」段
```

---

### 3.3 evidence expander／`render_fold`

**用途**：主圖與卡片下方**恰一個**預設收合入口；字樣 `▸ 為什麼／來源／限制／去哪補`（客戶 DEC-109 五）。卡片摺疊「▸ 詳細」、各頁「🔍 查看依據」、具名 expander（例 `指標明細（16 項）`）**維持有效**，是否統一換字＝W3，**本 phase 不判**（`label` 為可選參數，預設不變）。

**與既有關係**：`_ui_kit.render_fold(label, rows, *, expanded=False)` 為 `st.expander` 薄封裝；`rows`＝`(標籤, 內容)` 序列，沿用 `Basis` 六欄的「不得留白、沒有就寫 ⬜ 與原因」檢查；`Basis` 合併超集後兩份 `render_basis` 輸出逐 byte 不變。R10：收合不省運算，內容只放已算好的字串。⛔ 資訊只活在 `title=`（M13）。

**桌機 1440×900**

```
冷啟動／已載入（預設收合，兩態外觀相同）
│ ▸ 為什麼／來源／限制／去哪補                                   ← 高 32px
展開後（點開才看）
│ ▾ 為什麼／來源／限制／去哪補
│   為什麼　　……（Note.why 全文）
│   來源　　　Yahoo；資料日 10/28；快取 TTL 依 shared/ttls   ※示意
│   限制　　　近 252 日；均線為最新值水平參考線，不是歷史均線
│   去哪補　　請按頁首「🚀 更新」…（或 NO_EXIT_MARKER，不改寫成指路）
```

**手機 390×844**

```
│ ▸ 為什麼／來源／限制／去哪補      ← 整條 ≥44px 觸控區；字可換 2 行
展開後：四段各一行標籤＋內容（標籤在上、內容在下），無橫捲
```

**API 草案**：`render_fold(label: str | None = None, *, rows: Sequence[tuple[str, str]], expanded: bool = False) -> None`（`label=None` → 預設字樣常數）。

---

### 3.4 Missing placeholder（圖槽／數值槽／清單槽）

**規則（契約 §8，Gate A9／V9）**：missing ≠ 0／中性／HOLD；圖槽**保留同一 compact 高度**，內畫「<符號> <原因>」，**不畫任何線、點、軸、格線**；未載入＝灰、真錯誤＝🔴＋1 句原因；完整原因與去處在摺疊「去哪補」。

**符號與字由呼叫端傳入 `UI_STATE_META` 的 state（rev2 修訂）**：元件**不自用 ⬜**。符號／文字一律沿用既有十態（契約 §8-1、R8-2「⛔ 同一狀態出現兩種符號」）：`idle`＝⬜ 尚未載入、`empty`＝▨ 無資料、`missing_retryable`＝⟳ 缺漏 · 可重跑、`not_applicable`＝⊘ 不適用 · 重跑無效、`partial`＝◧ N／M 計入、`unwired`＝⛔ 未接線、`failed`＝🔴 取得失敗、`loading`＝⏳ 載入中。⬜ 只在 `idle`（以及既有字樣 `NOT_DEFINED`／`WATER_VALUE` 這類既有徽章族沒有的「尚未定義／尚未核准」）使用。

**冷啟動：chip 與槽內文字二選一**：同一個「尚未載入」不得同時出現在 chip 列與槽內（契約 §6-5 同一事實最多外露一次）。有圖槽／主值槽時由**槽**承載、chip 列只放護欄；沒有槽時才由 chip 列承載。

**主值留白時 tile 高度仍 ≥ 96px**（契約 Q1 下限；留白不得讓 tile 縮到下限以下，否則同列高差會超 16px）。

**桌機 1440×900**

```
冷啟動（尚未按更新）                       已載入但此源讀不到（符號依 state，例 ▨／⟳）
│ ┌ 圖槽 220px ──────────────┐             │ ┌ 圖槽 220px ──────────────┐
│ │   ⬜ 尚未載入，請按更新    │             │ │ ▨ 無資料：<原因>（state=empty） │
│ └──────────────────────────┘             │ └──────────────────────────┘
系統真錯誤                                 數值槽（KPI 主值）
│ ┌ 圖槽 220px ──────────────┐             │ 主值：留白（不放 0／—％／中性字）
│ │ 🔴 取得失敗：<1 句原因>   │             │ ( ⬜ 尚未核准／無法判定 )
│ └──────────────────────────┘
```

**手機 390×844**：同上，圖槽 140px，文字可換 2 行；錯誤原因 1 句，不放 `repr(e)`（`repr(e)` 進摺疊，H6 既有判斷）。

**⚠️ 設計張力（見 D6）**：契約要「冷啟動圖槽保留同高」，但冷啟動頁面會因此出現多個 140～220px 的灰色空槽（Gate A5 的「無 > 120px 無內容空洞」只在**已載入**量測，冷啟動不判，但客戶抱怨過「空白太多」）。D6 讓客戶決定 Secondary／mini 是否縮成一行。

**API 草案**：`chart_slot_missing_html(ui_state: str, reason: str, *, height_px: int) -> str`——`ui_state` 為 `UI_STATE_META` 的鍵（十態皆可，未知鍵 `ValueError`），符號與狀態字由元件**讀 `UI_STATE_META`**，`reason` 必填（呼叫端傳既有常數字），**⛔ 元件不自造符號或原因字**；`failed` 才用紅，其餘一律灰。

---

### 3.5 compact KPI card（tile）

**用途**：第一屏 3～5 個核心數字／狀態（B3）；高 96～160px，同列高差 ≤16px；卡面 ≤60 字；主值 ≤12 字。**列欄數（3／4／2×2）＝`CV1-DR-12`／W9，本 phase 不判**。

**結構（由上而下）**：標籤（13px，次要墨）→ 主值（大字；缺值留白）→ chip（合計 ≤2：≤1 顆「窗口」＋≤1 顆狀態／護欄）→ ≤1 句（Note 原文子字串，K1）→ 可選 sparkline（≤64px）。三要素全文與 facts 在該 tile 的摺疊（`▸ 詳細`／W3 待定）。

**tile 內的 chip 規則（rev3，採方案 (i)；契約 §6-5「同一 metadata 事實外露層最多一次」）**：

- **資料日（`asof`／`asof_missing`）、`source`、`retrieved_at`、`readable` 不在 tile 內重複**——寫在最近的共同容器（**頁級／組級 chip 列**，一列 tile 共用一次）；傳入即 `ValueError`。
- **「窗口」chip 允許在 tile 內出現一顆**，因為各 tile 的資料窗口可以不同（例 近 30 日 vs 近 252 日）。但**窗口僅限該 tile 自己的資料窗口**：若與組級窗口相同，改放組級、tile 內不得重複（傳入重複窗口 → `ValueError`）。有 sparkline 的 tile，其可見窗口 chip 即此顆（見 3.6）。
- 其餘 tile chip 只收**狀態或護欄**（例 `⚠ 過期 N 天`、`≈ 估算值`、`⬜ 尚未定義`、`fx_*`），每 tile ≤1 顆。
- **單頁 tile／chip 合計上限（與契約上限對齊）**：每 tile chip 合計 ≤2（≤1 窗口＋≤1 狀態／護欄）；每頁 tile ≤5（B3）→ **tile 內 chip 全頁合計 ≤10**；**頁級／組級 chip 列另計**，仍受 chip 列 3～5 顆上限；每顆 chip 文字 ≤12 字（Q9，逐字句豁免）；tile 內 chip 文字**計入該 tile 卡面 ≤60 字**（Q6）。

**桌機 1440×900（單一 tile 寬 ≈ 250～320px；高 ≤160px）**

```
頁級 chip 列（整列 tile 共用，只寫一次）：( 🕒 資料 10/28 ) ( ✅ 可讀 )      ※示意

冷啟動（建議總持股水位，Q2-2 逐字）            已載入（市場位階，※示意）
│ 建議總持股水位                              │ 市場位階
│                                            │ 震盪                              ※示意
│ ⬜ 尚未核准／無法判定  （主值槽=既有字樣）    │ 市場位階，不是台股趨勢
│ 風險上限／獨立顯示待 C2b＋RC-VISIBILITY Gate │ ▸ 詳細
│ ▸ 詳細                                      │
```

**手機 390×844（tile 寬 358px 單欄示意；2×2 或其他排法待 W9）**

```
│ 建議總持股水位
│ ⬜ 尚未核准／無法判定
│ 風險上限／獨立顯示待 C2b＋RC-VISIBILITY Gate
│ ▸ 詳細                                        （高 ≈ 110px）
若 W9 裁成 2 欄：tile 寬 ≈ 173px、內寬 ≈ 149px
│ 主值 20px 字：全形約 7 字/行 → 「⬜ 尚未核准／無法判定」換 2 行；
│ tile 高 ≈ 標籤16＋主值50＋句 2 行36＋摺疊32＋內距24 ≈ 158px（INFERENCE，≤164px 預算內）
```

**設計發現（寫入 §7 U2）**：契約 Q7「主值 ≤12 字」以全形字估算，2 欄手機 tile 內寬只容 ≈7 個全形字（20px）→ 12 字主值必換 2 行；若要單行，主值需 ≤7 全形字或改 chip。Phase 4 選欄數前，tile 先支援「主值最多 2 行」，不縮字級。

**與既有關係**：不用 `BADGES` 做 metadata；tile 的**狀態徽章**仍可用既有 `badge_html`（#1～#11）；tile 與 `card_html` 並存（`card_html` 綁頁、含三階層與 Note machinery；tile 是獨立簡版，避免為了預覽去登記 `blocks.PAGES`）。Phase 4 若要讓同一 tile 同時吃 `Note`，再決定是否改走 `card_html(chips=,summary=,spark=)`——內部決定，不在本草稿。

**API 草案**：`kpi_tile_html(*, label, value: str | None, chips: Sequence[Chip] = (), say: str | None = None, spark: SafeHtml | None = None, state_badge_n: int | None = None) -> str`；`value=None` → 主值槽留白（⛔ 不補 0）；`chips` 只收「窗口（≤1，且與組級不同）」與狀態／護欄 kind（其他 kind、重複窗口、超過 2 顆 → `ValueError`）；留白時 tile 高度仍 ≥ 96px。

---

### 3.6 sparkline

**規則**：≤64px 高、無軸無圖例；**NaN／None 不補 0、不插值，且 ⛔ 不跨缺口連線**（M1，rev2 修訂）：有效點之間若隔著 NaN／None，線在缺口處**斷開成多段**，各段只連相鄰的有效點；**x 位置保留原索引**（缺口佔掉它該有的水平空間，**不壓縮、不位移**）；若原序列不等距（例日期不連續），須在摺疊「限制」段標明「不等距」（`<title>` 亦附，但不算外露）；⛔ 「不等距」不放進窗口 chip（窗口 chip 只寫窗口，例「近 30 日」）。**孤立單點**（兩側皆缺）以小圓點呈現、不連線。**邊界（明寫）**：**有效點 ≥2 才畫（線段或圓點）；有效點 <2（含全 NaN、只剩 1 個有效點）→ placeholder**，不畫線也不畫點。例：`[1, 2, nan]`＝1 段 2 點的線；**`[1, nan, 3]`＝2 個有效點、中間缺口 → 畫成 2 個孤立小圓點（x 在第 1 格與第 3 格），不連線、不補中間點**；`[1, nan, nan]`／`[nan, nan, nan]`＝placeholder。單色中性線（不以紅綠暗示好壞——避免被讀成結論，契約風險「mini 圖被讀成結論」）；SVG 附 `<title>`（名稱、窗口、資料日）供讀屏與追溯，**但 `<title>` 不算外露**（螢幕上看不到）——sparkline 旁**必須有可見的窗口 chip**（該 tile 窗口與組級相同 → 放組級／頁級 chip 列；不同 → 放 tile 內那一顆窗口 chip，見 3.5；不可只靠 `<title>`）；**不顯示 hover-only 資訊**。

**桌機 1440×900（嵌在 tile 右下，寬 ≈ 96～120px、高 ≤ 64px）**

```
已載入、無缺口（VIX，※示意）               有缺口（中間 NaN）→ 斷線成多段，x 不位移
│ VIX                      ╱╲  ╱╲___       │ ╱╲╱╲     ╱‾╲_        ← 缺口處空白，兩側各自成段
│ ※18.4                   ╱  ╲╱      ‾‾    │         ↑ 缺口（保留原本寬度）
│ ( 近 30 日 )  ← 可見窗口 chip（必備）      │ ( 近 30 日 )   ※「不等距」若有，寫在摺疊「限制」段
冷啟動／全 NaN／有效點 <2
│ 同槽尺寸，不畫任何線／點；符號與字由呼叫端傳 UI_STATE_META state：
│   未載入 ⬜ 尚未載入／無資料 ▨ 無資料（chip 與槽內文字二選一，見 3.4）
```

**手機 390×844**：同上，寬 ≈ 100px，緊貼主值右側；視窗不足時移到主值下方整列（高度仍 ≤64px）。

**端點數值是否顯示＝D5**（推薦：不顯示；主值已在 tile 文字裡）。

**API 草案**

```python
sparkline_svg(values: Sequence[float | None], *, w: int = 100, h: int = 48,
              title: str, missing_state: str, missing_text: str) -> SafeHtml
```

`values` 的索引即 x 位置（缺口保留）；`missing_state`（`UI_STATE_META` 鍵）與 `missing_text` **必填**，元件不自判「未載入 vs 無資料」；回傳型別 `SafeHtml`（`str` 子類標記）以解 `P1R-SPARK-TRUSTED-HTML`（`card_html(spark=)` 之後只收 `SafeHtml`，屬 Phase 3 內部測試，不影響 Phase 2 golden）。

---

### 3.7 small multiples（小倍數）

**規則**：每個系列**各一格、各自座標，⛔ 疊軸、⛔ 正規化**（`CHART_B_NOTE`）；一組算 1 個 Secondary（B2）；每格 ≤96px 高；桌機 3 欄、手機 2 欄（HTML／CSS grid，不用 `st.columns`）；格內：系列名（≤8 字）＋SVG 折線；**資料日與窗口寫在組級 chip 列一次**（各格窗口相同時；不同時才在格內標），格內不重複 asof；缺系列的格＝placeholder（`⬜ 本輪沒有這個系列`，既有字樣）。圖 B 的 5 系列沿用 `INTL_GROUPS` 分組（海外市場 3／利率 1／美元 1）。

**桌機 1440×900（主欄寬約 940px，每格約 300px）**

```
冷啟動
│ 圖B 🌍 國際趨勢
│ ( ⬜ 尚未定義 )                      ← 「尚未載入」只寫在各格內（二選一）
│ 看海外市場、利率與美元是否正在幫助或壓抑台股風險偏好。
│ ┌ 海外市場 ┐┌ 利率 ┐┌ 美元 ┐       ← 每格 ≤96px，內寫 ⬜ 尚未載入
已載入（5 格，※示意）
│ 道瓊 DJI    │ 那指 IXIC   │ 費半 SOX
│ ░ 折線 ░    │ ░ 折線 ░    │ ░ 折線 ░          各格自己的座標
│ 美債 10Y    │ 美元 DXY    │                   ← 第 2 列 2 格（桌機 3 欄）
│ ( 資料 10/28 ) ( 近 120 日 )     ← 組級 chip 列只寫一次；格內不重複資料日／窗口
│ ▸ 為什麼／來源／限制／去哪補
```

**D6=B 方案冷啟動（次要圖／小倍數縮成一行，載入後撐開；對照上方 A＝契約字面的 96px 空格）**

```
桌機 1440×900                                   手機 390×844
│ 圖B 🌍 國際趨勢                                │ 圖B 🌍 國際趨勢
│ ( ⬜ 尚未定義 )                                 │ ( ⬜ 尚未定義 )
│ 看海外市場、利率與美元是否正在幫助或壓抑台股…   │ 看海外市場、利率與美元是否…（2 行）
│ ⬜ 尚未載入，請按更新      ← 單行 ≈ 32px         │ ⬜ 尚未載入，請按更新   ← 單行 ≈ 32px（整組不再占 3 列 ≈ 300px）
│ ▸ 為什麼／來源／限制／去哪補                    │ ▸ 為什麼／來源／限制／去哪補
載入後：這一行撐開成 3 欄（桌）／2 欄（手）格，其下內容下移一次；主圖（Primary）冷啟動仍保持同高
```

**手機 390×844（2 欄，格寬 ≈ 173px、高 ≤96px）**

```
│ 道瓊 DJI      │ 那指 IXIC
│ ░ 折線 ░      │ ░ 折線 ░
│ 費半 SOX      │ 美債 10Y
│ 美元 DXY      │ （空格不補圖）
整組高 ≈ 3 列 × 100 = 300px；若要壓 ≤ 210px 需 Phase 4 改為 switcher（見 3.9）
```

**設計發現（§7 U4）**：圖 B 5 系列在手機 2 欄需 3 列 ≈ 300px，超過 Primary 的手機 140px 預算，但小倍數屬 Secondary（無 Primary 高度上限，僅 mini 格 ≤96px）。是否與 switcher 取捨（契約 §12.1「擇一」）留 Phase 4 線框。

**API 草案**：`small_multiples_html(cells: Sequence[SmCell], *, cols_desktop: int = 3, cols_mobile: int = 2) -> str`；`SmCell(name, svg: SafeHtml | None, window_chip: Chip | None, missing_state: str | None, missing_text: str | None)`（`window_chip` 僅在該格窗口與組級不同時才給）。

---

### 3.8 Top-N 切片

**規則（契約 §10 R9）**：**只是顯示切片**——保序、保物件同一性（回傳元素 `is` 原元素）、⛔ 改排序／篩選／重算；L3 請求參數（`TOP_N_OPTIONS`／`DEFAULT_TOP_N`）不動；Digest 與 AI 不受影響；外露 Top-N 下恰一個「▸ 查看全部（N 筆）」；截斷時 chip「另 K 筆見全部」（沿用 `HERO_RISK_MORE_FMT` 模式）；排序依據寫一次（說明句 vs header chip＝W6，Phase 5 判）。預設 N：產業 5、候選 10 列、風險 3、持股需處理 5、例外代號 5（可調）。

**桌機 1440×900（以「產業」示意，列為 ※示意，非實際排名）**

```
冷啟動（尚未載入矩陣）
│ ⬜ 尚未載入，請按更新                         （清單槽不展開）
已載入
│ 排序依據：法人資金動能，非產業趨勢。            ← `ZONE1_SORT_NOTE` 現況說明句，逐字，寫一次（維持現況，**不畫成 chip**；
│                                                    改 chip 與否＝W6，Phase 5 拍板，本框僅示意槽位）
│ ( 🕒 資料 10/28 )                                ← 組級 chip 列，寫一次（契約 §6-5）；每列不重複
│ 1  產業 A   資金動能 ※示意
│ 2  產業 B   …
│ 3  產業 C   …            ← 共 5 列，每列 ≈ 36px；列內無 🕒／✅ 可讀
│ ( 另 31 筆見全部 )   ▸ 查看全部（36 筆）
```

**手機 390×844**：每列 2 行（名稱一行、次要數字一行）≈ 52px；5 列 ≈ 260px；「▸ 查看全部」整條觸控區 ≥44px。

**API 草案**：`topn_view(rows: Sequence[T], n: int) -> TopN[T]`；`TopN(shown: tuple[T,...], hidden: int, total: int)`；`n<=0` 或 `n` 非 int → `ValueError`；`rows` 非序列（generator）→ `ValueError`（避免被消耗後 `total` 不準）。

---

### 3.9 segmented switcher

**規則**：一組 switcher 內的多張候選圖算 1 個 Primary（B1），一次只顯示一張；預設項由呼叫端明確指定；⛔ 預設選項被取消後無結果（必須有預設回退）；`options` 標準化（去重、保序、空字串報錯）。**實際 widget 外觀＝D8**。⚠️ 切換＝一次 rerun（R10；legacy `tab_macro_v2` 註解亦記載：切換一次會讓 app.py 七個頂層 tab 的 body 全部重跑）——Phase 4 掛頁時需評估是否包 `st.fragment`（floor 1.56 有，但**行為未驗**）。

**桌機 1440×900（圖 A 主圖的切換列，※選項取自契約 §12.1：台股｜海外市場｜利率｜美元）**

```
冷啟動
│ [ 台股 ]  海外市場   利率   美元      ← 預設台股；切換列可操作
│ （其下圖槽顯示 ⬜ 尚未載入，請按更新）
已載入
│ [ 台股 ]  海外市場   利率   美元
│ ░ 只畫被選的那一張 ░（每項各自 header＋chip 列＋1 句；摺疊共用一個入口）
```

**手機 390×844**：切換列 4 項等寬（每項 ≈ 85px，字 ≤4 全形字不換行）；高 ≥44px；不橫捲。選項超過 4 項 → 改為兩列或下拉（Phase 4 再訂）。

**海外市場在 switcher 單圖內不可疊軸（rev2 補）**：「海外市場」選項含 3 個系列（道瓊／那指／費半），但 switcher 一次只顯示一張圖。**⛔ 不得把 3 系列疊在同一軸或正規化**（`CHART_B_NOTE`）；Phase 4 須二擇一：(i) 該選項內改用 3 格 small multiples（各自座標），或 (ii) switcher 拆成逐系列選項。本草稿不判，登 Phase 4 線框待確認。

**D8 的技術前提（內部，不進裁示表）**：若客戶選 B（膠囊式）或 C（pills），需 `st.segmented_control`／`st.pills`；這兩個 API 在最低支援版本（`requirements.txt` floor，現為 `>=1.56.0,<1.60.0`）上的**行為**必須先實跑驗證（`P1R-FLOOR-156-API`，目前只做過原始碼靜態掃描，見 §2.3）；實跑不過 → 退回 A（`st.radio(horizontal=True)`），並通知客戶。D8 的歷史背景（舊總經頁用 `st.radio` 的理由、出處為舊頁程式註解）見 §7。

**API 草案**：`segment_options(options: Sequence[str], default: str) -> SegmentSpec`（純標準化＋驗證）；widget 呼叫在 `_ui_kit` 薄封裝，**不在 compact.py**（compact 無 streamlit）。

---

### 3.10 tokens 收斂

**問題（FACT，見 §2.6／契約 §14.2）**：blueprint 與 tokens 色值全面不同（頁底 `#0a0e16` vs `#0e141b`；面板 `#0f1521` vs `#151d26`；卡 `#151d2c` vs `#1b242f`；線、墨、語意色都不同），Streamlit 原生主題又是第三套。**把 tokens 改成 blueprint 色＝改變所有既有 v2 頁的外觀，並使 `page_css()` 輸出變動，與「今天頁 CSS 逐 byte 不變」衝突。**

**契約已有的規定（rev2 必須先講清楚）**：契約 §14 **R15（DEC-110，AI 總管內部決定）** 與契約 §14.2 差異表本就規定「色值不一致時 **blueprint 為準，tokens 於 Phase 3 收斂**（`P1R-TOKENS-CONVERGE`）——客戶裁示的色值除外」；圓角等幾何值「blueprint 為準（**以加性 token 新增，不改既有值**）」。因此本節拆兩題，不再把「全部不改」當成理所當然的預設：

- **D1a（客戶裁示色）**：CTA 主按鈕藍（客戶 2026-09-22）、`--sig-neutral`／`-bg` dark（客戶 2026-09-21）——維持或改？另注明 `--sig-neutral`／`-bg` 的 **light 值是 AI 總管選的暫值、可被推翻**。
- **D1b（非客戶色）**：頁底／面板／卡／線／文字／語意色——依 R15 **Phase 3 全站一次收斂**，還是**延到 Phase 4～6 逐頁**？⚠️ 選「延後」＝**調整 R15 的時程**（不是遵守契約），已在 D1b 明寫；另注明 **blueprint 只有 dark 版，light 沒有基準色**，收斂 light 需另定來源。
- **圓角（原 D2）併入 D1b 的幾何子項**：契約 §14.2 已定 blueprint 14px 圓角以**加性 token** 新增。Phase 3 **只新增 token、不套用**；`compact_css()` 內 tile 暫沿用現行 `CARD_BASE` 2px 與既有頁一致；Phase 4 線框（看得到整頁組合時）再確認是否套 14px。這與契約同向，不是推薦與契約相反的做法。

**不論 D1a／D1b 怎麼選，一律先做的加性幾何 token（不覆寫既有）**

| 加性 token（新元件專用，不覆寫既有） | 值（來源） |
|---|---|
| chip 膠囊半徑 | 999px（blueprint `.pill`；`_chip` 既有 999px） |
| chip 高／字級／內距 | 22px／11.5px／2px×8px（沿用 `BADGE_BASE` 字級） |
| 卡圓角（blueprint） | 14px（契約 §14.2；**只新增，Phase 3 不套用**） |
| tile 內距、tile 圓角 | 取 `CARD_TIERS` t2（10×12）、圓角暫沿用現行 2px |
| 圖槽高 | 桌 220／手 140（Q3） |
| small multiple 格高、sparkline 高 | 96／64（Q4、Q5） |
| 觸控區最小高 | 44px |

**色值對照（FACT，供 D1a／D1b；對比值為本檔以 WCAG 公式計算）**

| 用途 | tokens（現行） | blueprint（僅 dark） | 備註 |
|---|---|---|---|
| 頁底／面板／卡 | `#0e141b`／`#151d26`／`#1b242f` | `#0a0e16`／`#0f1521`／`#151d2c` | 差異小但全站可見 |
| 主文字／次文字 | `#dbe5ef`／`#9fb0c1`（對面板 13.3／7.7:1） | `#e8edf7`／`#a9b5ca`（對卡 14.4／8.2:1） | 兩者皆過 AA |
| 琥珀／紅／綠／藍（文字色） | `#d3a43c`／`#e8706b`／`#57b985`／`#4b8efe` | `#f2b84b`／`#ff7a7a`／`#5fd18a`／`#5aa9ff` | blueprint 稍亮 |
| CTA 主鈕（D1a） | `#1f6feb`（白字 **4.63:1**，貼 AA 線 4.5）、light `#044cb6` | `#1f5fae`（白字 **6.35:1**） | 客戶 2026-09-22 裁示 `#1f6feb`，與 `config.toml` primaryColor 一致 |
| `--sig-neutral`／`-bg`（D1a） | dark `#8fa3b8`／`#26313d`（客戶 2026-09-21）；light `#1e3b4f`／`#d7dce1`（**AI 總管選，可推翻**） | 無對應 | — |
| light 版全部色 | 現行 `LIGHT` | **無基準**（blueprint 只有 dark） | D1b 收斂 light 須另定來源 |

**桌機／手機線框**：本項**無版面**；視覺證據＝「色票並排表」放在日後離線元件預覽（內部自決，見 §1.2）。**冷啟動／已載入態不適用**。推薦方案下 Phase 3 對任何既有頁**視覺 0 變化**。

---

### 3.11 站殼間距子項（內部先量測 → 量到真值後才另送客戶；唯一可能動既有畫面的項目）

**處置（rev2）**：rev1 把「要不要做」直接送客戶（D7）。但「約 50px」是 **INFERENCE、未量測**，拿未量測的數字請客戶裁示等於請客戶為一個猜測拍板。改為：

1. **步驟 1 的前置工作項（內部、無需客戶）**：以瀏覽器 DOM 量測 nav4 預設模式 1440／390 下，站標帶與頂部留白實際可收的 px，並量 `?legacy=1` 是否共用同一組 CSS 選擇器；結果寫回本檔或 Migration Plan。
2. **量到真值後才另送客戶**一題「A 不做／B 最小（只減新四頁模式的頂部留白）」，附實測數字與前後並排示意。
3. **已移除 rev1 的選項 C（把站標帶併進頂欄）**：那屬殼／IA 變更，契約 §19 站殼註記明列 ⛔（不得因此改 `PAGE_LABELS`／導覽殼語意／legacy 入口），也超出 Phase 3。

**問題**：站標帶（`app.py` 主標題 `📊 台股 AI 戰情室`）加 Streamlit 頂欄與預設上方留白，使頁面 H2 起於 y≈223（桌／手皆是），吃掉第一屏約 1/4。Q10～Q11（主要判讀句頂端 ≤ H2＋200／＋260px）在不壓縮站殼時可能達不到（Gate §5 把這類情形列為「技術上做不到」，處置為列最小必要改動與影響面）。

**範圍界線**：只動**站標高度與頂部留白**（容器上方 padding、標題列上下 padding）；⛔ 不改 `PAGE_LABELS`／導覽殼語意／側欄與底部列／legacy 入口。**必須只在 nav4（新四頁）模式生效，`?legacy=1` 逐 byte 不變**（DEC-019 凍結舊 UI）。`app.py` 在 z60 目錄指紋守衛內，核准改動須同步 `_BASE_DIGEST`。若獨立 QA 判屬 IA／殼語意變更 → **停手送客戶**（Migration Plan §7）。

**風險：高**——動全站殼、與 legacy 共用、受 z60 守衛；**必須走 Visual Fidelity Gate §5（例外流程）**與四頁全 Gate（§5.1）。

**桌機 1440×900（INFERENCE：下列數字為預估，待上述量測取代）**

```
現況                                         B 最小方案（預估）
y=0   ┌ Streamlit 頂欄 ┐                      y=0   ┌ 頂欄（不動）┐
y≈60  │ 上方預設留白    │                      y≈60  │ 留白縮減約 40～50px │
y≈128 │ 站標 📊 台股 AI 戰情室 (22px)         y≈85   │ 站標（高度、字級不變）
y≈223 │ 頁面 H2                               y≈170  │ 頁面 H2   （約提早 50px ≈ 5.5% 屏高）
```

**手機 390×844**：同結構，H2 y≈223 → ≈170（INFERENCE）。冷啟動／已載入外觀相同（殼與資料狀態無關）。

**重要限制**：即使做 B，也只提早約 50px；第一屏真正的主因是頁面本身的版面（市場頁判讀句 +998），那是 Phase 4 的工作。**B 的價值是「讓 Q11 有機會達標」，不是「解決 Q11」**。

---

## §4 與 W1～W9 的關係表

| W | 內容 | 與 Phase 3 | 本草稿處置 |
|---|---|---|---|
| **W1** | tokens 客戶裁示色值是否改 blueprint 色值（`P1R-P3-WF-CUSTOMER-COLORS`） | **Phase 3 項** | **裁示表 D1a**（客戶裁示色）；非客戶色的收斂時程＝D1b |
| W2 | 指標危險度指路說明句 vs chip | Phase 4 | 不在本 phase，維持現況；元件只**提供**能力（chip 可承載逐字句） |
| W3 | 卡片摺疊標籤「▸ 詳細」／「🔍 查看依據」是否統一為新字樣 | Phase 4～6 | 不在本 phase，維持現況；`render_fold`／`card_html` 的 `label` 為可選參數、預設不變 |
| W4 | 選股條件預設展開 vs 收合＋摘要 chip | Phase 5 | 不在本 phase，維持現況 |
| W5 | 1A 順序內候選如何提前 | Phase 5 | 不在本 phase，維持現況 |
| W6 | 排序依據說明句 → chip | Phase 5 | 不在本 phase，維持現況；Top-N 元件只提供「寫一次」的 chip 槽 |
| W7 | 兩套刻度常駐非摺疊 vs chip＋可展開 | Phase 6 | 不在本 phase，維持現況 |
| W8 | AI 投資總結「1～3 個變化」選取規則 | Phase 7 | 不在本 phase；Phase 3 不碰 Digest／Brain |
| W9 | KPI／Hero 欄數（`CV1-DR-12`） | Phase 4 | 不在本 phase，維持現況；tile 不假設欄數（§3.5） |

> ⚠️ **「W2～W9 維持現況」是待驗事項**：這些 W 點的「維持現況」處置來自契約 §22 與本檔單組判讀，**未經第二組獨立驗證**；尤其 W2（chip 承載指路句）、W6（Top-N 排序依據 chip）與本 phase 元件能力的邊界，Phase 4／5 線框時須再驗。
>
> 其他由本草稿**新增的待客戶決定點**＝D1b、D3、D5、D6、D8、D10（Phase 3 元件外觀／色彩收斂時程／切換樣式／chip 配額；非 W 系列）。

---

## §5 驗收與守衛計畫

### 5.1 Visual Fidelity Gate 對 Phase 3 的適用

| 面向 | 適用方式 |
|---|---|
| 頁面層（A1～A5、A7、A10、A11、V1～V7） | **N/A**：Phase 3 不掛頁、0 頁面畫面變更。PR 描述 Visual Fidelity 段寫「N/A（頁面）：0 頁 import `compact`；`page_css()` sha256 不變」。 |
| 元件層（A6 尺寸、V8 chip 文字化、V9 Missing 符號、V10 工程字樣、V11 無 hover 依賴） | **適用**，證據＝離線元件預覽（內部自決：離線 HTML＋截圖附 PR，不在 app 內、不加頁、不加導覽；想要 app 內預覽另案，屬 IA 邊界）：每元件 1440／390 × 冷啟動／已載入（夾具，註明 ※示意）；單張 <300KB。 |
| 截圖時機 | 元件實作完成後 1 次（步驟 1 之後，PR 內附）；**不是**現在。本草稿階段不截圖（沒有可截的實作）。 |
| 站殼子項（內部量測後客戶選 B 才有） | **全 Gate**（Gate §5 例外流程）：📊／🎯／💼／👤 四頁 × 1440／390 × 冷啟動／已載入，改前改後並排；另證 `?legacy=1` 輸出不變；重量冷啟動 baseline（`P1R-COLD-START-BASELINE`）。 |
| 判定者 | 獨立 QA（≥2 組不同角度，`CLAUDE.md` §-2 規則 4）；總管複驗 A6／V8／V9 的抽樣與 sha256 比對。 |

### 5.2 零變更證明（每個 phase PR 必附，Migration Plan §4）

(a) diff 僅 `src/ui_v2/**`、`src/ui/views/_ui_kit.py`、`tests/**`、docs（若站殼子項經量測並獲核准另含 `app.py`＋z60 digest）；`src/services|compute|data`、`shared/` 語意模組 0 行。(b) `page_css('dark'|'light')` sha256＝§2.5 基準；`card_html`／`single_submit_form`／`render_card` Phase 2 golden 不變；`tokens.DARK/LIGHT` 既有色值映射不變（D1a=A 且 D1b=B；若 D1b=A 則本條改為「變動僅限 D1b 列出的 token，並附前後對照」）。(c) AST：`compact.py` 只 import 標準庫與 `src.ui_v2.*`／`shared.ui_state`（L0）；不 import streamlit／`src.data`／`src.services`／`_ui_kit`；全 repo 0 個 production caller（grep 測試）。(d) mutation（下表）。(e) 分層守衛 `test_c3_layering_guard` 綠。

### 5.3 Mutation 對應（Migration Plan §6 M1～M4、M7～M10、M13；M5、M6 已於 Phase 2 驗）

| M | 在 Phase 3 的測試（必須先紅後綠） |
|---|---|
| M1 sparkline NaN 補 0／跨缺口連線 | 輸入 `[1, nan, 3]`／`[None, 2, 4]`：輸出路徑點數＝有效點數、不含 y 軸基線座標；**缺口兩側不連線（`[1, nan, 3]` 產生 2 段／孤立點，不是 1 條直線）、有效點的 x 保留原索引、不位移**（`[1, nan, 3]` 的 3 其 x 在第 3 格而非第 2 格）；全 NaN／<2 有效點 → 回 placeholder（含 `missing_text`），**不含 `<polyline>`／`<path>`**；窗口 chip 必須在可見 HTML 中（`<title>` 不算）；**邊界**：`[1, nan, nan]`／全 NaN → placeholder（有效點 <2）、`[1, 2, nan]` → 1 段線、`[1, nan, 3]` → 2 個孤立圓點（無 `<polyline>`）；「不等距」字樣只出現在 `render_fold` 的「限制」段，不在窗口 chip 文字內 |
| M2 chip 接受未登記 kind | `meta_chip("made_up")` → `ValueError`；`META_KINDS` 鍵集合 == 契約 §6 表（對帳測試）；**合併護欄 chip**：`parts` 每個 kind 都屬 `META_KINDS` 且屬護欄族，合併 chip 文字＝各 part 逐字串接，非護欄族互併 → `ValueError`，`META_KINDS` 不因合併新增條目 |
| M3 新 kind 與 `BADGES` 重名 | 斷言 `META_KINDS` 鍵與 `BADGES[*]["name"]`／`state_const` 零交集；`BADGES` 長度仍 11；狀態 chip 的 icon＋字 == `UI_STATE_META`（讀同源） |
| M4 Top-N 回傳複製／改序 | `topn_view(rows, n).shown[i] is rows[i]`；順序一致；`hidden == len(rows)-len(shown)`；`n` 大於長度時 `hidden==0`；L3 `TOP_N_OPTIONS`／`DEFAULT_TOP_N` 所在檔 0 diff |
| M7 說明句放在 chip 之前 | header HTML 內 `title` < `chips` < `say` < 圖槽／svg < 摺疊入口 的 index 嚴格遞增 |
| M8 新模組 import `src.services` | AST 白名單 import 測試（見 5.2 c） |
| M9 stale chip 用紅色 | stale chip 的 class 對應 CSS 規則只引用 `--sig-amber*`，`compact_css()` 中 stale 規則不得出現 `--sig-red`；`failed` 才允許紅 |
| M10 chip 經訊號文字頻道 | chip HTML 內含 `⬜`／`🔴` 時**不會**呼叫 `assert_signal_text_clean`（模組不 import `_ui_kit`）；`card_html(chips=…)` 既有三條 M10 測試續綠 |
| M13 摺疊內容只留 `title=` | `render_fold` 以 AppTest：expander 預設收合（`expanded=False`）、展開後四段文字都在 body；全頁掃描 `title=` 屬性內容不得獨有任何四段文字 |

**建議新增（待登記進 Migration Plan §6，M14～M20）**：M14 Missing 圖槽畫出線／點／軸；M15 `kpi_tile_html(value=None)` 補 0 或中性字；M16 chip 列超過 `max_chips` 靜默截斷（應 `ValueError`／溢出回傳）；M17 溢出時把**護欄 chip** 移入摺疊（應只移低優先序）；M18 逐字客戶句（`CHART_A_MA_DISCLAIMER`、`FX_PARTIAL_TEXT`）被截斷或改寫；**M19 同一 `asof`（或 source／readable／窗口）在同一頁／組內重複外露**（tile／Top-N 列再放 `🕒 資料 …` 應 `ValueError` 或測試紅）；**tile 內允許一顆「窗口」chip，但窗口與組級相同時放入 tile 應 `ValueError`、tile 內 chip 超過 2 顆（>1 窗口、>1 狀態／護欄）應 `ValueError`**；**M20 Missing 圖槽／主值槽自用 ⬜ 而非依傳入 state 讀 `UI_STATE_META` 的符號**（例 state=empty 卻畫 ⬜）。

### 5.4 其他守衛

- floor 守衛：新元件若呼叫 `st.segmented_control` 等，`TestStreamlitFloorCompatibility` 必須仍綠；並補一次 **floor 1.56 wheel 實跑**（`P1R-FLOOR-156-API`）。
- 反例測試：未登記 `kind`、空字串 chip、空 `reason`、`rows` 為 generator、`options` 含空字串／重複、`spark` 非 `SafeHtml`。
- 資訊守恆：`render_fold` 的四段標籤與內容在 `card ∪ fold` 守恆判定器（`tests/_p25_info_conservation.py`）可重用。
- 工程字樣：元件預設文案 0 命中契約 §18 清單。
- CI：fast＋slow 雙綠。QA 分工建議：QA-A＝差分＋mutation；QA-B＝契約／逐字句／glyph 碰撞稽核；QA-C＝元件預覽截圖逐項對 A6／V8／V9。

---

## §6 客戶裁示表（Decision Gate）

> 共 **7 題**（D1a、D1b、D3、D5、D6、D8、D10），只列需要客戶決定的外觀／色彩收斂時程／切換樣式／chip 配額。**技術細節不進本表**（檔名、函式、版本驗證、預覽方式、測試、內部代號）由 AI 總管內部拍板；出處引用放文末腳註。每題格式：問題｜方案表（優點／缺點／風險）｜AI 總管推薦｜理由｜不裁示預設。**D3 無現況可維持**（chip 目前沒有任何樣式，不裁示則以推薦為準）。

### D1a 您已裁示的顏色，要維持還是改？[^1]

涉及：主要操作按鈕的藍色（您 2026-09-22 裁示 `#1f6feb`；淺色版 `#044cb6`）、中性灰藍（您 2026-09-21 裁示 深色版 `#8fa3b8`／底 `#26313d`）。另：中性灰藍的**淺色版（`#1e3b4f`／`#d7dce1`）是 AI 總管自己選的暫值，不是您指定的，可被推翻**。

| 方案 | 優點 | 缺點 | 風險 |
|---|---|---|---|
| **A 全部維持**（含淺色版中性暫值） | 不動您已裁示的事項；與整體介面主色一致 | 按鈕白字對比 4.6（貼近可讀下限 4.5）；與 mockup 的按鈕色有差 | 低 |
| B 只把按鈕藍改為 mockup 值（`#1f6feb`→`#1f5fae`） | 白字對比升到 6.4，較易讀；更貼 mockup | 動到您已裁示的色；需您明確回覆 | 中：變更已裁示事項 |
| C 維持深色版、請您指定淺色版中性色 | 把 AI 暫選的值換成您的決定 | 需要您給色或看色票 | 低 |

**AI 總管推薦：A。** 理由：您已裁示的事項非經您新的裁示不更動；mockup 沒有對應的中性色，只有按鈕色有可比較的值，而 4.6 對比仍過 AA。若您覺得淺色版中性色不順眼，可直接選 C。**不裁示預設＝A。**

### D1b 不回應＝契約 R15 改為逐頁收斂：您沒有裁示過的顏色與圓角，要在 Phase 3 全站一次收斂成 mockup 的值，還是延到各頁重做時逐頁收斂？[^2]

背景：您核准的 mockup 已定為視覺基準（DEC-109 二十四：blueprint＝Visual SSOT）；契約 R15 原本規定「色值不一致時以 mockup 為準，Phase 3 全站收斂」。選 B（延後）＝把 R15 的時程由「Phase 3 全站」改為「Phase 4～6 逐頁」，**代價：過渡期內，尚未重做的既有頁面與視覺基準不一致**。涉及：頁底、面板、卡片、線、文字、琥珀／紅／綠／藍（色值差異見本檔色值對照表）。mockup **只有深色版，淺色版沒有基準色**，所以淺色要收斂需另定來源。圓角：mockup 的 14px 已定以「新增規格」方式加入；Phase 3 **只新增、不套用**，Phase 4 線框（看得到整頁組合時）再確認要不要套到卡片。

| 方案 | 優點 | 缺點 | 風險 |
|---|---|---|---|
| A Phase 3 全站一次收斂（照 R15 原時程） | 新舊頁立刻同色；與 mockup 一致最早 | **所有既有頁（市場、標的、持股、我的）外觀同時改變**，需逐頁前後對照；淺色版無基準要另決；底色仍有第三套（系統預設主題）對不齊 | 中：可見變動範圍大 |
| **B 延到 Phase 4～6 逐頁收斂**（各頁重做時一併換色，屆時有該頁完整驗收） | 每次只動一頁、可逐頁對照；Phase 3 對既有頁視覺 0 變化 | **＝調整 R15 的時程**；過渡期既有頁與視覺基準（mockup）不一致、新舊頁可能並存兩套近似色 | 低 |

**AI 總管推薦：B。** 理由：全站換色等於重做一輪外觀驗收，且 Phase 3 沒有任何頁面掛新元件，無法證明換色後第一屏仍符合驗收；新四頁本來就在 Phase 4～6 逐頁重寫，換色順勢進行成本最低。R15 本身是 AI 總管的內部決定，但 mockup 是您核准的視覺基準，故此時程調整仍請您知悉。**不裁示預設＝B**（保守：Phase 3 不改既有頁；Phase 4 各頁線框再逐頁確認）。

### D3 標籤膠囊（chip）的視覺區分：三種外觀，還是全部同一種中性膠囊？

三族＝資訊（資料日／來源／窗口）、狀態（✅／⚠／⬜）、護欄（⬜ 尚未定義、逐字聲明）。⚠️ **護欄若用虛線外框，會與畫面上既有的虛線語意衝突**：低層級卡片用虛線外框、「⛔ 未接線」徽章用虛線、mockup 的虛線用於示意標籤與「研究框架，未啟用」的卡。護欄是您指定必須讓人看見的東西，不應長得像「低層級／未啟用」。

| 方案 | 優點 | 缺點 | 風險 |
|---|---|---|---|
| **A 三族；護欄＝實線粗框**（資訊＝細外框；狀態＝淡底色；護欄＝粗實線外框） | 一眼分「有沒有問題」與「哪顆不能漏看」；不與虛線既有語意衝突 | 三種樣式要學；多一個樣式規範 | 低 |
| B 三族；護欄＝虛線外框 | 與資訊 chip 一眼可分 | 與低層級卡片、未接線徽章、mockup 示意標籤的虛線語意衝突，可能被讀成次要／未啟用 | 中：逐字聲明被當成次要 |
| C 全部同一種中性膠囊，只靠圖示＋字區分 | 最單純 | 護欄聲明容易被當成普通資訊略過 | 中：逐字聲明被忽略 |

**AI 總管推薦：A。** 理由：逐字護欄（如「均線為參考，不等於正式台股趨勢判斷。」）必須讓人看見，用實線粗框讓它不被淹沒、又不借用「低層級」的虛線；任何一族都同時有圖示＋文字（不靠顏色）。紅色仍只給「系統真出錯」，過期用琥珀。**護欄樣式是可被您推翻的選項**（想要虛線也可選 B）。**不裁示預設＝A**（此題沒有「現況」可維持——現況 chip 還沒有任何樣式——故以推薦為準，並可在 Phase 4 線框再改）。

### D5 迷你趨勢線與小倍數要不要顯示數字？

| 方案 | 優點 | 缺點 | 風險 |
|---|---|---|---|
| **A 都不顯示數字**：迷你線與小倍數的每格都只有單色中性線（卡片主值已有最新數字；小倍數每格只有系列名） | 最乾淨；不會因紅綠或端點被讀成結論 | 小倍數格看不到各系列的最新值 | 低 |
| B 迷你線不加、**小倍數每格加最新值文字**（無紅綠） | 5 個系列各自的水位一眼可比 | 與組級資料日並列時文字變多，手機 2 欄格寬僅約 173px | 低：密度略升 |
| C 加最新／最高／最低三個數字（迷你線與小倍數皆然） | 資訊最多 | 迷你圖變成報表小格，與「圖表 > 數字」衝突 | 中：密度上升 |

**AI 總管推薦：A。** 理由：迷你圖只回答「大致往哪走」，窗口已用標籤標明；判斷用的數字放在主值或摺疊。**不裁示預設＝A。**

### D6 冷啟動（還沒按更新）時，次要圖的空槽要縮小嗎？[^3]

| 方案 | 優點 | 缺點 | 風險 |
|---|---|---|---|
| A 所有圖槽冷啟動也保持同高（契約字面） | 載入後版面不跳動 | 冷啟動頁面出現多塊 96～220px 灰色空槽 | 低（但「空白太多」感） |
| **B 主圖（Primary）保持同高；次要圖／小倍數縮成一行「⬜ 尚未載入」，載入後撐開**（線框見本檔冷啟動示意） | 冷啟動更緊湊、第一屏主圖位置穩定 | 載入後下方內容會往下移一次 | 低 |
| C 全部都縮成一行 | 最緊湊 | 主圖也會在載入時跳動，第一屏位置會變 | 中 |

**AI 總管推薦：B。** 理由：您的第一個抱怨之一是「空白太多／資訊密度不對」（DEC-108，經總管轉交，非客戶逐字）；主圖維持位置，次要圖在第一屏之外，載入後的位移影響最小。**選 B＝調整契約 §8-4 冷啟動「圖槽保留同一 compact 高度」的字面（契約為 AI 總管內部決定；Gate A9 需同步註記）。** **不裁示預設＝A（契約字面，維持現況）。**

### D8 切換鈕（台股｜海外市場｜利率｜美元）要用哪種樣式？

背景：舊總經頁目前用圓點式單選；該頁程式註解記載當時的選擇理由是「視覺一致優先」，註解標為您 2026-08-27 的偏好，但**沒有對應的正式裁示紀錄**（總管無法確認原文）。這是舊頁的既有偏好，新四頁是否沿用，請裁示。

| 方案 | 優點 | 缺點 | 風險 |
|---|---|---|---|
| A 圓點式單選列（沿用舊頁的樣式） | 與舊頁一致；行為最熟悉 | 不像 mockup 的膠囊切換鈕 | 低 |
| **B 膠囊式切換鈕（像 mockup 的「檢視切換」）** | 貼近 mockup；觸控區大，手機好按 | 與舊頁（若仍並存）樣式不同 | 低～中：新舊頁過渡期兩種外觀並存 |
| C 標籤式（pills） | 輕量 | 與 mockup 差距較大 | 中：同上 |

**AI 總管推薦：B。** 理由：mockup 的切換就是膠囊鈕；新四頁在 Phase 4～6 逐頁取代舊頁，過渡期並存的時間有限。若 B／C 在部署環境驗證不過，總管會退回 A 並通知您。**不裁示預設＝A。**

### D10 圖 A 的標籤配額：您的範例 4 顆＋2 顆逐字護欄＝6 顆，「來源」放哪？[^4]

事實：您的範例標籤是 `資料 10/29`、`來源 TWSE`、`近 60 日`、`✅ 可讀`（4 顆）；圖 A 另有 2 顆必須外露的護欄（逐字 `均線為參考，不等於正式台股趨勢判斷。`、`⬜ 尚未定義`）→ **共 6 顆，超過原定的 3～5 顆上限**。

| 方案 | 優點 | 缺點 | 風險 |
|---|---|---|---|
| (a) **來源進摺疊**（護欄以外的標籤超額時移入摺疊；外露 5 顆＝資料日、窗口、可讀＋2 護欄） | 完全符合 3～5 顆上限；護欄全留 | 與您範例不同：外露層看不到「來源」，要點開摺疊 | 低：資訊仍在摺疊、可追溯 |
| (b) **兩顆護欄合併成 1 顆、來源外露**（外露 5 顆＝資料日、來源、窗口、可讀＋合併護欄；例「均線為參考，不等於正式台股趨勢判斷。　⬜ 尚未定義」；線框見本檔圖 A 示意） | 您範例的 4 顆全在外露層；仍 5 顆；兩句皆逐字保留 | 合併後標籤較長（逐字句豁免字數上限），手機會換行；「⬜ 尚未定義」不再是獨立標籤 | 低～中：兩個護欄擠在同一顆較易被略讀 |
| (c) 6 顆全部外露（超過 5 顆上限） | 範例與護欄全外露、不合併 | 違反「3～5 顆」；手機標籤列約 3 行，占高度 | 中：違反您自己的上限 |

**AI 總管推薦：(b)。** 理由：您的範例把「來源」列為外露標籤，而護欄是您指定必須讓人看見的，(b) 是唯一同時保住兩者又不超過上限的做法；代價是兩個護欄合併成一顆，逐字不變。若您認為「來源」不必外露，(a) 最單純。**不裁示預設＝(a)**（現行的機械規則）。

### 內部備註（非裁示題）

**題號對照（rev1 → rev2；rev3 題號不變）**

| rev1 | rev2／rev3 | 說明 |
|---|---|---|
| D1 | **D1a**（客戶裁示色）＋**D1b**（非客戶色） | 拆開：契約 §14 R15／DEC-110 本就規定 blueprint 為準、tokens 於 Phase 3 收斂；「全部不改」不是理所當然 |
| D2（圓角） | 併入 **D1b** 幾何子項 | 契約 §14.2 已定 14px 以加性 token 新增；Phase 3 只新增不套用 |
| D3 | **D3** | 補上虛線語意衝突 |
| D4（手機 chip 換行） | **移除** | 契約 Q9／§6 已定手機可換行，照原 A |
| D5 | **D5** | 擴及小倍數數值呈現 |
| D6 | **D6** | rev3 補契約字面調整註記 |
| D7（站殼間距） | **移出裁示表**，見 §3.11 | 先內部量測，量到真值後才另送 |
| D8 | **D8** | rev3 改述為舊頁程式註解記載的偏好（無對應 DEC） |
| D9（預覽方式） | **移除** | 內部自決：離線 HTML＋截圖附 PR |
| （新增） | **D10** | 圖 A chip 配額與「來源」去處 |

**D7（站殼間距）不在本表**：①「約 50px」是未量測的推論，不該請您為猜測拍板；② rev1 的選項 C（併站標帶進頂欄）屬殼／IA 變更，契約 §19 明列 ⛔。處置：內部先量測（步驟 1 前置工作項，無需客戶），量到真值後才另送您「A 不做／B 最小」。細節與風險（高；須走 Gate §5）見 §3.11。

---

## §7 未驗與限制（誠實揭露）

1. **rev1 單組撰寫；rev2 依兩組獨立 QA（QA-B 合規、QA-A 事實）修訂，修訂版本身未再經第三輪驗證**（§-2 規則 6）。§2 的「已存在／全新」判斷與 §3 的設計取捨仍屬待驗事項，尤其「0 production caller」「**新 UI 層**沒有 sparkline／小倍數／Top-N／segmented 共用實作（legacy 有三份 sparkline）」是 grep 結果、非窮舉。
2. **沒有跑瀏覽器、沒有實機**：§3 全部 ASCII 與 px 數字是**預算**（契約 §19 上限＋CJK 1em 字寬估算），不是量測；手機實機、Streamlit Cloud、`requirements.txt` floor 1.56 實跑**未驗**。
3. **floor 1.56 的 API 存在性只是靜態掃 wheel 原始碼**；`st.segmented_control`、`st.metric(chart_data=)`、`st.bar_chart(horizontal=)`、`st.line_chart(height=)`、表單內 `st.expander` 在 1.56 的實際行為未驗。
4. 讀檔範圍：契約、Migration Plan、Gate 文件**全文**；`DECISION_DIGEST`／`ONE_AI_BRAIN` 只確認 Phase 3 不碰（grep 關鍵段）；`docs/DECISIONS.md` 只讀 DEC-108／113 與契約引用的 DEC-092／105／107／109／110（未逐字重讀 DEC-109／110 全文，以契約轉錄為準）；blueprint 只讀 `market.html` 的樣式與首屏結構，**其餘五個 html 與 `docs/wireframes/stock_ia_v1.html` 未讀**；`docs/vnext/visual_fidelity/` 只讀目錄與 Visual Gap Audit 的站殼段。
5. 站殼 −50px、冷啟動 baseline 都是 **INFERENCE**；`P1R-COLD-START-BASELINE` 尚未重量。
6. 對比值（4.63、6.35 等）為本檔以 WCAG 相對亮度公式計算，未經第二組複算。
7. **不確定處**（交總管複驗）：
   - **U1** `--sig-neutral` light 值究竟算不算「客戶裁示色」：檔內註解寫「AI 總管選 B 組、可被客戶推翻」，而契約 §14.2 把它與 CTA 色並列為客戶裁示。rev2 處置：D1a 把 light 值明示為「AI 總管暫選、可推翻」；「哪些 token 屬客戶裁示」的歸屬判斷仍是 **INFERENCE**，請總管確認。
   - **U2** Q7「主值 ≤12 字」與 2 欄手機 tile 寬度的衝突（§3.5）。**回寫建議**：在契約 Q7 加註「以全形字估算，2 欄手機 tile 內寬約 7 個全形字（INFERENCE），主值最多 2 行；實測後調整」，並**併入 W9**（`CV1-DR-12` 選欄數時一併判）。⛔ 本草稿未改契約（契約須走 DEC 流程），此為建議。
   - **U3**（rev1 的「圖 A 6 顆 chip 溢出」）→ **已升為客戶裁示 D10**，不再是不確定處。
   - **U4** 圖 B 小倍數 vs switcher 的高度取捨（§3.7）；以及「海外市場」3 系列在 switcher 單圖內不可疊軸的排法（§3.9）。
   - **U5** Primary 為原生圖、其餘為 SVG，兩種繪圖路徑在同頁的視覺一致性（線寬、色、字級）需元件預覽時比對。
   - **U6** 站殼間距的「提早 50px」是否真的只影響 nav4 模式：已改為內部量測的步驟 1 前置工作項（§3.11），量到前不送客戶。
   - **U7** 「✅ 可讀」與「⬜ 尚未定義」並排的讀法（§3.2）；Phase 4 線框處理，登 BACKLOG。
8. **D8 出處與限制（N4）**：舊總經頁選 `st.radio(horizontal=True)` 的理由「視覺一致優先」，**唯一出處是 `src/ui/tabs/tab_macro_v2.py` 的程式註解**（註解標為 user 2026-08-27）；本檔**未在 `docs/DECISIONS.md` 找到對應 DEC**（單組 grep，非窮舉），故 §6 D8 僅敘述為「舊頁程式註解記載的偏好」，不稱為客戶正式裁示。floor 1.56 的 `st.segmented_control`／`st.pills` 行為未實跑（§3.9）。
9. **新發現（登 `docs/BACKLOG.md`，P2，不插隊）**：`P1R-P3-BG-THREE-SOURCES`（三個底色來源，D1b 背景）、`P1R-P3-KPI-VALUE-WIDTH`（Q7 與 2 欄手機寬度）、`P1R-P3-CHART-A-SIX-CHIPS`（圖 A 6 顆 chip；已升為 D10）、`P1R-P3-COLD-GAP`（冷啟動空槽 vs 「空白太多」，D6）、`P1R-P3-NATIVE-VS-SVG`（原生圖與 SVG 兩條繪圖路徑一致性）、`P1R-P3-SHELL-SCOPE`（站殼 padding 與 legacy／z60 共用；改為內部先量測）。rev2 新增：`P1R-P3-LEGACY-SPARKLINE-FORKS`（legacy 三份 sparkline 實作，只登記不動）、`P1R-P3-READABLE-VS-UNDEFINED`（✅ 可讀與 ⬜ 尚未定義並排的讀法，Phase 4 線框）。

---

## 腳註（§6 出處引用；放在文末以保持裁示表只談外觀與取捨）

[^1]: D1a 出處：中性灰藍＝客戶 2026-09-21（深色版 `--sig-neutral`／`-bg`；淺色版為 AI 總管暫選、檔內註解標明可被推翻）；主要按鈕藍＝客戶 2026-09-22（`--cta-primary-bg`）；「非經新 Decision 不改」＝`PROJECT_RULES.md` §0.1。歸屬判斷（哪些 token 屬客戶裁示）為 INFERENCE，見 §7 U1。
[^2]: D1b 出處：blueprint＝Visual SSOT／visual acceptance baseline＝客戶 DEC-109 二十四；「色值以 blueprint 為準、tokens 於 Phase 3 收斂」＝契約 §14 R15（DEC-110，AI 總管內部決定）與契約 §14.2。
[^3]: D6 出處：DEC-108「客戶自承偏差六點之三」（空白太多／資訊密度不對）——**經總管轉交，非客戶逐字**；冷啟動圖槽字面＝契約 §8-4（AI 總管內部決定）、Gate A9。
[^4]: D10 出處：客戶 DEC-109 五的 chip 範例；3～5 顆上限＝契約 §4；護欄逐字句＝DEC-092 Q2。
