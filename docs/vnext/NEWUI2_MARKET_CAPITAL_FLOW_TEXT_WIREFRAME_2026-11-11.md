# New UI2 市場頁「市場資金與籌碼」文字線框草案（OneBrain 下方；390／1440）— 2026-11-11

> **狀態：草案，待客戶正式拍板。本文件不授權任何實作。**
> - **基準**：`origin/main` `5eef8863`（PR #1135 已合併）；量測日 2026-11-11。
> - **授權**：Issue #1136（客戶裁示轉錄，**非逐字**；客戶在對話回覆「同意」四項建議，不是逐字展開說明）。步驟 1 僅核准 docs-only 文字線框草案；草稿完成後回客戶**正式拍板**。
> - **效力順序（衝突時）**：客戶原文（Issue #1136、DEC-133／DEC-157／DEC-162 fence）＞ `NEWUI2_ACTIVE_PRESENTATION_CONTRACT_2026-11-03.md`（Active Contract，AI 整理文件）＞ 本文件。與 Active Contract 衝突處一律列「B 上報點」，**不自行折衷、不改 freeze**。
> - **不授權施工清單**：不改 production code／tests／UI2 VM／feed／section；不接資料、不改 fetcher／source／API；不改 PIT／公式／權重／燈號、Risk Cap、D1–D5、EPS、OAuth／Sheet、Digest v2、P-1、OneBrain、Actions、cron／Secrets；#1119 HOLD；資料 PR #1124～#1126 不處置。**不得進入 A2 步驟 2。**
> - ⚠️ **本線框不是經驗證畫面。未做真機／Cloud／瀏覽器視覺驗收（NOT VERIFIED）。** 線框所有數值一律為佔位符（〈±N,NNN.N 億元〉〈YYYY-MM-DD〉…），**不是真資料**，也不是示意數值。
> - **證據級別**：`FACT`＝讀碼／讀檔直接確認；`INFERENCE`＝推得未實測；`NOT VERIFIED`＝未驗。引用只寫 `path::symbol`，不寫行號。
> - docs 組**單組**撰寫，未經第二組獨立複驗。
- **ASCII 示意，欄寬以語意為準，不代表像素**（CJK 全形字寬在框線內可能輕微錯位，非設計差異）。
> - 承接：`docs/vnext/NEWUI2_MARKET_CHIPS_OLD_UI_FIRST_MAPPING_2026-11-11.md`（DEC-162）；本文**不取代**它。

---

## A. 現況（FACT，讀 `src/ui2/views/market.py::render` 與 `shared/ui2_contract/text.py`）

**渲染順序（市場頁）**：標題 → `market_l1_html`（CTA → 結論 → 狀態／Risk Cap／是否需要行動／下一步 → 今日主要風險）→ `kbar_chart_html`（VM 有 `kbar`）或 `primary_slot_html`（空槽）→ `render_cards`（`MARKET_CARD_IDS` 固定 6 張）→ OneBrain（`div.ui2-m-onebrain`）→ `render_sections(skip={onebrain})`。

| 項目 | 現況 |
|---|---|
| 既有元件 | `.ui2-section-title`、`field_row_html`（`.ui2-row`：label｜value｜chip｜detail）、`metric_card_html`、`empty_state_html` |
| L1 字樣（`shared/ui2_contract/text.py`） | `⬜ 資料未取得`／`⬜ 資料未備`／`⬜ 資料日未提供`／`⚠ 過期 {n} 天`／`⚠ 可能已過期`／`🔴 來源目前不可用`（後接原因）／`⬜ 尚未評估`／`⬜ 尚未定義`／`⬜ 尚未載入`／`⬜ 無法判定`／`⬜ 尚未提供` |
| 數值／日期格式 | 數值 `f"{x:,.2f}"`；資料日 `YYYY-MM-DD`；SPEC 行『SPEC｜<來源>｜資料日 <日期>｜缺值不補』 |
| chip 四族 | POSITIVE ✅／WARNING ⚠／DANGER 🔴／NEUTRAL_INFO ℹ（符號為第二載體）；`shared/ui2_contract/tones.py` 僅稱 Positive／Allowed 為『真正正向的 deterministic state』（FACT） |
| **INFERENCE** | 『淨買超／正值不得用 Positive 綠』是**本文推論**，非 tones.py 原文：依 tones.py 對 Positive 的定義（真正正向）與 `FINAL_UI_CONTRACT_FREEZE_2026-11-02.md` §4.1 四種語意 tone，淨買超屬客觀資金方向、不是『確定性正向』，故本線框改用 NEUTRAL_INFO ℹ。待客戶確認 |
| 色彩 | Dark-only：背景 `#0e1117`、次背景 `#161b22`、文字 `#e6edf3`、`.ui2-chip--neutral` opacity .85；K 棒紅綠僅限收盤對開盤，**不得沿用到本區塊** |
| 視窗 | 手機 390×844：內容寬 361.2、頂部導覽 85px、可用高 791；桌機 1440×900：內容寬 1280、導覽 73px、≥769px 三 tile；換行 `overflow-wrap:anywhere`、無水平捲動 |
| 現行實測（Real，手機） | `nav_margin_after_risk=168.8`、`scroll_end_bottom=763.8`（≤791）；OneBrain 位置 1525～1602（手機）／1031～1072（桌機）；來源 `docs/vnext/newui2_realfeed/viewport_measurements.json`，**本批未重測** |
| 正負號慣例 | UI2 無正負號格式化慣例（grep 0 命中，**單組**） |
| 三項資料在 UI2 | 0 命中（見 Mapping 文件 §1）；FAKE 六場景無對應假資料 |

---

## B. 衝突核對與上報點（逐條列，不自行折衷）

| # | 項目 | 內容 | 處置 |
|---|---|---|---|
| ① | Active Contract §3.1「📊 整頁 0 個 evidence expander」 | 本線框**預設不折疊**，三項直接外露。若客戶要折疊，需客戶**例外**＋改 `SHOWN_FOLDS`（`views/_page.py`），屬後續 | 上報 G-2 |
| ② | 位置：OneBrain **下方** | 客戶 Issue #1136 指定；與 Mapping 文件 §4 AI 推薦（日 K 之後）**不同，以客戶指定為準**。對首屏錨點（風險後餘裕）**無影響**；**會影響** `scroll_end_bottom` 與 `market_stress_reachable`，須實作後實測（INFERENCE） | 以客戶為準；實測列 F |
| ③ | 不新增第 7 張核心卡 | `MARKET_CARD_IDS` 固定 6 張（多或少即 raise）；本區塊為 **L1 SectionVM**（proposed id 例 `market_capital_flow`，名稱待定），不進 `render_cards` | 設計決定 |
| ④ | Visual Budget（B1～B6：每頁 1 Primary、Secondary ≤3） | 本區塊**不放圖表、不算 Primary**；是否算 Secondary **未明** | 上報 G-7 |
| ⑤ | 配色 | 中性色＋**明確正負號**＋文字標籤；chip 用 NEUTRAL_INFO ℹ；**不用紅綠**、不沿用舊 UI 負值紅與外資藍／投信綠／自營金；不把負值當危險或賣出訊號 | 照 Issue 第 4 項 |
| ⑥ | 板塊顯示方案 | Top／Bottom N 屬**新排名語意**，依 Issue 需另 Gate；方案 A 的計數與合計屬**衍生聚合**（非來源直接提供之淨額），與 Issue『優先展示來源提供的客觀淨額』有張力（見 C.4 ③） | 上報 G-3 |
| ⑦ | 融資『資料疑義』旗標 | 資料層缺逐列旗標（Mapping §1.2，FACT）；**線框不得寫死『資料疑義』固定句**（不論資料是否乾淨皆顯示＝誤導） | 缺口，後續 Gate |
| ⑧ | 稱呼 | 『外資淨買賣超（僅外資）』；**不得稱『三大法人』**、不補投信／自營商（`finmind_inst.parquet` 只有外資） | 照 Issue 第 3 項 |
| ⑨ | 舊門檻與判讀語言 | 不使用 3400／2500；不使用買賣建議、法人強弱、四象限、動能、排名訊號、±100 億結論卡 | 照 Issue 第 3 項 |
| ⑩ | 板塊 `net_amt_yi` 口徑 | FACT（已驗證 `data_cache/sector_flow/daily_net.parquet`）：`net_amt_yi = foreign_yi + trust_yi + dealer_yi`（最大誤差 2e-13，三分項皆無 NaN）＝**三大法人合計**；源自 TWSE T86／TPEX 三大法人**張數×收盤價**（`src/compute/sector_flow.py`：`net_amt_yuan = lots × SHARES_PER_LOT × close`，÷`YUAN_PER_YI`）。與同頁項目 ①『外資（僅外資）』**口徑不同**，只稱『淨額』易被混讀 | 線框明寫口徑與差異對照；上報 G-10 |

---

## C. 版型（ASCII；只標 ◀ 新增；既有區塊以占位表示）

**約定**：`〈…〉`＝佔位符，**不是資料**。**ASCII 示意，欄寬以語意為準，不代表像素。**字樣只用既有 L1 字樣；需新字樣者標「（待客戶確認）」。

### C.1 區塊標題與說明（兩種視窗共用）

```
市場資金與籌碼                      ◀ 新增（標題文案待客戶確認，G-1）
客觀數據，不構成買賣建議；缺值不補      ◀ 新增（說明文案待客戶確認，G-1）
```

### C.2 手機 390px（單欄由上而下；每項一個 `.ui2-row`）

```
┌────────────────────────────┐
│ （既有，不動）標題＋L1 首屏  │
│ （既有，不動）今日主要風險   │
│ （既有，不動）台股日 K／空槽 │
│ （既有，不動）六張核心卡     │
│ （既有，不動）🤖 OneBrain    │
├────────────────────────────┤
│ 市場資金與籌碼               │ ◀ 新增
│ 客觀數據，不構成買賣建議；   │
│ 缺值不補                     │
│ ┌────────────────────────┐ │
│ │ 外資淨買賣超（僅外資）    │ │ ◀ 項目 ①
│ │ 〈＋／−N,NNN.N 億元〉     │ │   主值（大）
│ │ 〈淨買超／淨賣超〉 ℹ      │ │   文字標籤＋中性 chip
│ │ 外資及陸資，不含外資自營商│ │   口徑小字
│ │ 資料日〈YYYY-MM-DD〉｜     │ │   freshness 行
│ │ 來源〈finmind_inst〉      │ │
│ └────────────────────────┘ │
│ ┌────────────────────────┐ │
│ │ 融資餘額（大盤）          │ │ ◀ 項目 ②
│ │ 〈N,NNN 億元〉            │ │
│ │ ℹ（中性，無紅黃綠）       │ │
│ │ 單位：億元                │ │
│ │ 資料日〈YYYY-MM-DD〉｜來源 │ │
│ │ 〈finmind_margin〉        │ │
│ └────────────────────────┘ │
│ ┌────────────────────────┐ │
│ │ 板塊資金流（最新交易日淨額）│ │ ◀ 項目 ③（方案 A 示意；採否待 G-3）
│ │ 口徑：三大法人合計（外資＋  │ │
│ │ 投信＋自營），張數×收盤價  │ │
│ │ 資料日〈YYYY-MM-DD〉       │ │
│ │ 涵蓋板塊 〈n〉/〈N〉        │ │
│ │ 全體淨額合計〈±N,NNN.N 億元〉│ │
│ │ 淨額為正的板塊〈a〉個／     │ │
│ │ 淨額為負的板塊〈b〉個       │ │
│ │ 來源〈sector_flow〉        │ │
│ └────────────────────────┘ │
│ （既有，不動）頁尾           │
└────────────────────────────┘
```

### C.3 桌機 1440px（≥769px：三欄 tile 並排；全寬）

```
（既有，不動）L1 首屏／今日主要風險／日 K／六張核心卡／🤖 OneBrain（全寬）
────────────────────────────────────────────────────────────────────────────
市場資金與籌碼                                                    ◀ 新增
客觀數據，不構成買賣建議；缺值不補
┌──────────────────────┐┌──────────────────────┐┌──────────────────────┐
│ 外資淨買賣超（僅外資）  ││ 融資餘額（大盤）       ││ 板塊資金流（最新交易日 │
│ 〈＋／−N,NNN.N 億元〉   ││ 〈N,NNN 億元〉         ││ 淨額）                │
│ 〈淨買超／淨賣超〉 ℹ    ││ ℹ                      ││ 資料日〈YYYY-MM-DD〉   │
│ 外資及陸資，不含外資    ││ 單位：億元             ││ 涵蓋板塊〈n〉/〈N〉     │
│ 自營商                 ││ 資料日〈YYYY-MM-DD〉   ││ 口徑：三大法人合計     │
│ 資料日〈YYYY-MM-DD〉    ││ 來源〈finmind_margin〉 ││ 全體淨額合計〈±N,NNN.N │
│ 來源〈finmind_inst〉   ││                        ││ 億元〉｜淨額為正〈a〉個 │
│                        ││                        ││ ／淨額為負〈b〉個       │
└──────────────────────┘└──────────────────────┘└──────────────────────┘      ◀ 三項新增
```

### C.4 三項內容規格

**① 外資淨買賣超（僅外資）**
- 主值〈＋／−N,NNN.N 億元〉＋文字標籤『淨買超』或『淨賣超』（事實描述，**不是看多空**）。
- 口徑小字『外資及陸資，不含外資自營商』；freshness『資料日 〈YYYY-MM-DD〉｜來源 〈finmind_inst〉』。
- 僅最新一個交易日。不顯示投信、自營商；不顯示 ±100 億結論或『加碼／減碼』文字。
- 口徑風險（FACT，Mapping §1.1）：parquet `source` 欄 `…:Foreign`（舊口徑，2017-12-18 前含外資自營商）與 `…:Foreign_Investor`；最新列落在新口徑，本批僅顯示最新一列，不跨斷點。

**② 融資餘額（大盤）**
- 主值〈N,NNN 億元〉（元 → 億，÷1e8；須通過 (500, 10000) 億**開區間** sanity，沿用 `shared/margin_schema.py` 既有防線）。
- **無**門檻線、**無**紅黃綠、**無**『高危／安全』、**無**建議。口徑小字『單位：億元』；freshness 同上。
- sanity 不過 → 顯示 `⬜ 資料未取得`＋原因句。**原因句字樣待客戶確認**（現有 L1 字樣無「單位檢查未過」，不自創，G-5）。
- 不寫死『資料疑義』固定句（B-⑦）。

**③ 板塊資金流（最新交易日淨額）**

**口徑說明（FACT，已驗證 `daily_net.parquet`）**：板塊 `net_amt_yi = foreign_yi + trust_yi + dealer_yi`（最大誤差 2e-13，三分項皆無 NaN），即**三大法人合計**；源自 TWSE T86／TPEX 三大法人張數×收盤價（`src/compute/sector_flow.py`：`net_amt_yuan = lots × SHARES_PER_LOT × close`，÷`YUAN_PER_YI`），再彙總至板塊。
- 線框板塊項須明寫：『**口徑：三大法人合計（外資＋投信＋自營），依個股張數×收盤價彙總至板塊**』（**措辭待客戶確認**，G-10）。
- 與同頁項目 ①（僅外資）的口徑差異對照：

| | ① 外資淨買賣超 | ③ 板塊資金流 |
|---|---|---|
| 法人範圍 | **僅外資**（外資及陸資，不含外資自營商） | **三大法人合計**（外資＋投信＋自營商） |
| 計算 | `finmind_inst.parquet` `foreign_buy`（億元） | 個股張數×收盤價，彙總至板塊 |
| 對象 | 大盤單一數字 | 各板塊；全體合計＝各板塊加總 |

- 因兩者金額**不可直接比較或相加減**，同頁並列時兩項各自須顯示口徑小字，不得只稱『淨額』。
- 是否另拆外資／投信／自營分項顯示＝**更多欄位，需另 Gate**（G-10），本批不做。

**衍生聚合風險（方案 A 須明寫）**：方案 A 的『淨額為正的板塊〈a〉個／淨額為負的板塊〈b〉個』與『全體淨額合計』是**本系統對各板塊淨額再做的衍生聚合**，**不是來源直接提供的淨額**，與 Issue『優先展示來源提供的客觀淨額』有張力；措辭已改為中性『淨額為正／為負』，避免『流入／流出』帶方向感。是否保留衍生聚合列入 G-3。

| 方案 | 內容 | 排序／排名語意 | 取捨 |
|---|---|---|---|
| **A 摘要** | 『資料日〈YYYY-MM-DD〉｜涵蓋板塊〈n〉/〈N〉｜全體淨額合計〈±N,NNN.N 億元〉｜淨額為正的板塊〈a〉個／淨額為負的板塊〈b〉個』 | **無**排名、無象限、無動能 | 短、省捲動；但**屬衍生聚合**（見上），僅在客戶接受衍生聚合時採用 |
| **B 全列** | 全部板塊逐列『板塊名｜〈±N,NNN.N 億元〉』，**固定順序＝官方產業代碼序或名稱序，不依金額排序、不截斷**；手機單欄長列／桌機兩欄 | 無（固定序） | 最貼近 Issue『來源提供的客觀淨額』，無衍生聚合；但列長，增加捲動與 `market_stress_reachable` 風險 |
| C Top／Bottom N | 依金額取前／後 N | **新排名語意，需另 Gate**；易被讀成推薦清單 | **不建議本批** |

**AI 推薦（非裁示）**：**B（全列、固定順序、不截斷）**；**A 僅在客戶接受衍生聚合時採用**。理由：B 最貼近 Issue 的『來源提供的客觀淨額』且不引入衍生數字，代價是長列；A 短但屬衍生聚合。推薦不等於裁示，沉默不等於同意。

```
方案 B 手機示意            方案 B 桌機示意（兩欄）
板塊名 A｜〈±N,NNN.N 億元〉   板塊名 A｜〈…〉   板塊名 M｜〈…〉
板塊名 B｜〈±N,NNN.N 億元〉   板塊名 B｜〈…〉   板塊名 N｜〈…〉
…（固定順序，全列）           …（固定順序，全列）
```

- coverage：`tpex_complete≠True` → 『目前僅含上市資料』（partial chip ⚠）；`n_absent_cells` → 『部分板塊當日無資料〈n〉格』。
- 不含象限、動能 Y、白話、持股高亮（`highlight_sectors` 須剝離）。

### C.5 狀態矩陣（每項 × 手機／桌機文字稿）

| 狀態 | 觸發 | 文字稿（手機＝桌機，桌機 tile 內相同；佔位符） |
|---|---|---|
| **loaded** | 有最新列且未過期 | 主值〈…〉＋標籤＋ℹ；freshness『資料日〈YYYY-MM-DD〉｜來源〈…〉』 |
| **stale** | 外資／融資：`compute_cache_staleness` 超 7 日曆天；板塊：`metadata.last_updated` 距台北今日 >4 日曆天 | 仍顯示主值，並加 `⚠ 過期 {n} 天`（天數未知 → `⚠ 可能已過期`）；**不當 fresh** |
| **partial** | 板塊 `tpex_complete≠True` 或 `n_absent_cells>0` | 主值照顯示＋⚠ chip『目前僅含上市資料』／『部分板塊當日無資料〈n〉格』 |
| **missing** | 無資料或融資 sanity 不過 | `⬜ 資料未取得`（融資 sanity 不過另附原因句，待確認） |
| **unavailable** | 來源讀取錯誤 | `🔴 來源目前不可用`＋原因 |
| **not_provided** | Real 軸尚未接線（**現況**） | `⬜ 尚未提供`（Capability 字樣） |

- **FAKE 軸**：須以 **FAKE 標示**的占位呈現（見 F），不得填示意數值當真資料。
- **長文字／1.5× 放大（`market_stress_reachable`）**：長板塊名換行（`overflow-wrap:anywhere`）；數字不截斷；單位『億元』不換行脫離數字（建議數字與單位同一不換行單元，INFERENCE，待實測）；無水平捲動。
- **無障礙**：符號＋文字雙載體（淨買超／淨賣超不靠顏色）；chip 對比 ≥4.5:1（INFERENCE，待實測）；建議每項 `role="group"` 與 `aria-label`（如『外資淨買賣超，僅外資，資料日 …』）——**UI2 目前無資料區塊 aria-label 慣例**（現有 aria-label 僅見搜尋框與 K 棒 svg），標待確認 G-8。

### C.6 首屏／捲動驗證表

| 檢查 | 手機 390×844 | 桌機 1440×900 |
|---|---|---|
| 本區塊位置 | 日 K、六卡、OneBrain **之後**，在首屏之下 | 同左，在首屏之下 |
| 首屏四必要項 | **不動** | **不動** |
| 底部導覽不遮擋 | `scroll_end_bottom` 須 ≤791 | 須 ≤視窗高 |
| 預估高度 | INFERENCE：三 row 各約 4～6 行；**未量測** | INFERENCE：一列三 tile；**未量測** |
| `market_stress_reachable` | 實作後實測 | 實作後實測 |
| 真機／Cloud | **NOT VERIFIED** | **NOT VERIFIED** |

---

## D. 保留清單核對

| 客戶要求保留 | 是否動到 |
|---|---|
| 第一屏四必要項（結論、狀態、Risk Cap、是否需要行動＋主 CTA）及今日主要風險緊接 | **未動** |
| 六張核心卡（`MARKET_CARD_IDS`） | **未動**（不新增第 7 張） |
| OneBrain（位置、內容） | **未動**（新區塊在其下方） |
| 台股日 K／空槽 | **未動** |
| `SHOWN_FOLDS` 三項（`target.conditions`、`me.digest`、`me.registry`） | **未動**（本區塊預設不折疊） |
| Dark-only | **未動** |
| 手機四格／頂部兩列導覽（DEC-146）、桌機 ≥769px 三 tile 規則 | **未動** |

---

## E. 資料位置對照（全部 **proposed、未授權**；各上游授權／再散布 **NOT VERIFIED**）

通用鏈：git 追蹤 parquet／reader（唯讀，不呼叫 fetcher）→ proposed 唯讀 L3 service → VM 欄位 → 市場頁新 SectionVM。

| 項目 | source | proposed L3 | VM 欄位（proposed） | stale／sanity |
|---|---|---|---|---|
| 外資 | `data_cache/finmind_inst.parquet`：`foreign_buy`（億元）、`source`、`date` | `get_inst_foreign_fact_view`（名稱待定） | 值、as_of、source、state | `compute_cache_staleness('finmind_inst')`，7 日曆天 |
| 融資 | `data_cache/finmind_margin.parquet`：`margin_balance`（元）；經 `macro_cache_reader.load_v2_chart_series()['margin']` 最新點與 `.attrs` | `get_margin_fact_view`（名稱待定） | 值（億）、as_of、is_stale、state | 元→億 ÷1e8；(500, 10000) 開區間 sanity，不過回 None |
| 板塊 | `data_cache/sector_flow/daily_net.parquet`：`net_amt_yi`；`reader.read_sector_flow_cache`；`metadata.json` | `get_sector_flow_fact_view`（或直接 reader） | 資料日、coverage、合計、淨流入／出計數 | `metadata.last_updated` 距今 >4 日曆天為 stale；`observation_date`；coverage（`n_sectors`、`tpex_complete`、`n_absent_cells`） |

- 外資 parquet 最新列落後交易日 2 天屬正常延遲；stale 門檻 7 日曆天，故 7 日內不標 stale（**INFERENCE**）。
- 融資『資料疑義』逐列旗標**資料層缺口**：未落實前不顯示該旗標。
- 授權與再散布（TWSE／TPEX／FinMind 等）：**NOT VERIFIED**，不能因檔案可讀就推論可上線。

---

## F. 驗收準則與 A2 步驟 2 最小施工 scope（**建議，非授權**）

**最小檔案清單（若日後授權；現不動）**
1. proposed 唯讀 L3 service 3 支（外資、融資、板塊）。
2. `src/services/ui2/real_feed.py`：`_read_*` 三支＋`RealFeedSnapshot` 欄位。
3. `G2F_IMPORT_ALLOWLIST` 白名單＋反向守衛（teeth）。
4. `real_canonical` spec。
5. `market_vm` 新增 L1 SectionVM 或 sections 規格（**不動 `MARKET_CARD_IDS`**）。
6. `views/market.py` 渲染順序確認（OneBrain 之後渲染本區塊；`render_sections` 的 skip 不得讓本區塊重複渲染）。
7. FAKE 軸占位（須帶 **FAKE 標示**）。
8. tests：四態映射；融資單位／sanity；外資口徑；板塊 coverage／stale；G2F teeth；FAKE／Real 對稱；`ui2-browser` 手機 390／桌機 1440 量測（含 `scroll_end_bottom`、stress）。

**回滾**：還原白名單與 feed；FAKE 軸不動；無需 feature flag（Real 由 `ui2_feed` 切換，`app.py` production 不引用）。

**驗收清單（逐條可勾）**
- [ ] 區塊位置在 OneBrain 之後，六卡／OneBrain／日 K 順序與內容不變
- [ ] `MARKET_CARD_IDS` 仍為 6 張
- [ ] 無 evidence expander；`SHOWN_FOLDS` 不變
- [ ] 外資稱『外資淨買賣超（僅外資）』，無『三大法人』、無投信／自營商
- [ ] 融資單位為億元，sanity 不過 → `⬜ 資料未取得`；無 3400／2500、無紅黃綠
- [ ] 板塊採客戶選定方案；無排名／象限／動能
- [ ] 正負號明確、不靠顏色；無紅綠、無舊 UI 負值紅
- [ ] 六種狀態文字稿皆有對應；stale 不當 fresh
- [ ] 手機 390 `scroll_end_bottom` ≤791；桌機不被導覽遮擋；無水平捲動
- [ ] `market_stress_reachable` 通過
- [ ] FAKE 軸帶 FAKE 標示、與 Real 結構對稱
- [ ] G2／G2F／G4／G9 守衛全綠
- [ ] 真機／Cloud 結果如實標註（未做則 NOT VERIFIED）

**不做清單**：排名、象限、動能、門檻、買賣建議、法人強弱、三大法人、投信／自營商、Digest、OneBrain、Risk Cap、新資料來源／fetcher／cron。

---

## G. 待客戶確認項（每項附 AI 推薦；**推薦非裁示，沉默不等於同意**）

| # | 待確認 | 選項 | AI 推薦 |
|---|---|---|---|
| G-1 | 區塊名稱與說明文案 | 『市場資金與籌碼』＋『客觀數據，不構成買賣建議；缺值不補』／自訂 | 採草案文案 |
| G-2 | 是否折疊 | 不折疊（採 Active Contract §3.1）／折疊（需例外＋改 `SHOWN_FOLDS`） | **不折疊** |
| G-3 | 板塊顯示方案（含『是否保留衍生聚合』：A 的『淨額為正／為負的板塊個數』與『合計』非來源直接淨額，與 Issue『優先展示來源提供的客觀淨額』有張力） | A 摘要（含衍生聚合）／B 全列固定序、不截斷（全為來源淨額，但長列）／C Top-Bottom N（新排名語意） | **B**；A 僅在客戶接受衍生聚合時採用（AI 推薦，非裁示） |
| G-4 | 正負號格式與『淨買超／淨賣超』標籤（UI2 無既有慣例） | 採草案／自訂 | 採草案（明確 ＋／−＋文字標籤） |
| G-5 | 新 L1 字樣（融資 sanity 未過原因句等） | 客戶指定字樣／暫以 `⬜ 資料未取得` 無原因句 | 客戶指定；未定前不自創 |
| G-6 | 外資落後交易日（約 2 天）是否需額外提示 | 需要／不需要 | **不需要**（資料日已外露） |
| G-7 | 本區塊是否算 Secondary Visual | 算／不算 | 不算（無圖表） |
| G-8 | aria-label 慣例（`role="group"`＋『外資淨買賣超，僅外資，資料日 …』） | 採用／不採用 | 採用 |
| G-9 | 是否授權 A2 步驟 2 施工 | 授權（附上述 scope）／暫不 | 待上述確認後再授權 |
| G-10 | 板塊口徑文字（『三大法人合計（外資＋投信＋自營），依個股張數×收盤價彙總至板塊』，措辭待確認）；是否另拆外資／投信／自營分項顯示（分項顯示＝更多欄位，**需另 Gate**） | 採草案口徑文字、不拆分項／自訂文字／另案拆分項 | 採草案口徑文字；不拆分項（本批） |

---

## 限制與未驗

- 本線框**不是經驗證畫面**；未做真機／Cloud／瀏覽器視覺驗收（NOT VERIFIED）。
- 線框所有數值為佔位符；任何高度、對比、換行行為皆 INFERENCE，待實作後實測。
- Real 軸 Streamlit 實際渲染高度 **NOT VERIFIED**；現行 `scroll_end_bottom` 等為既有量測值，本批未重測。
- 各上游（TWSE／TPEX／FinMind）授權與再散布 **NOT VERIFIED**。
- 「UI2 無正負號慣例」為單組 grep 結果。
- 本文件單組撰寫，未經第二組獨立複驗。

---

## 客戶短摘要（1 頁）

1. **要拍板**：市場頁 OneBrain 下方新增『市場資金與籌碼』文字線框（390／1440）。
2. **內容**：外資淨買賣超（僅外資，非三大法人）、融資餘額（億元，無門檻燈號）、板塊資金流（最新交易日淨額；**口徑為三大法人合計，與外資項不同**，G-10）。
3. **配色**：中性色＋明確正負號＋文字標籤，不用紅綠、不當買賣訊號。
4. **推薦**：不折疊（G-2）；板塊 AI 推薦方案 B（全列固定序，最貼近來源淨額）或方案 A（僅在您接受衍生聚合時），不做 Top／Bottom 排名（G-3，推薦非裁示）。
5. **位置**：依您指定在 OneBrain 下方；與先前 AI 建議（日 K 之後）不同，以您為準。
6. **風險**：新增捲動長度，`scroll_end_bottom` 與 stress 須實作後實測；本線框未經真機／Cloud 驗證。
7. **缺口**：融資『資料疑義』資料層旗標未落實，故不顯示固定句；上游授權未驗。
8. **請回覆**：G-1～G-10（尤其 G-3、G-5、G-9、G-10）。
9. **本批**：只有文件，不授權 A2 步驟 2 程式施工。
