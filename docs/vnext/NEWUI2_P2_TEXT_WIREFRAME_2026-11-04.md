# New UI2 P2 最小差異文字線框（📊 市場：OneBrain 位置＋台股 Primary 主圖誠實空槽）— 2026-11-04

> 📌 **狀態更新（2026-11-04，客戶 DEC-133／(19)）：線框有條件通過（G-1＝A、G-2＝B、G-3＝A）；P2 已施工**（見 `docs/DECISIONS.md` DEC-133、BACKLOG §5.1.26「P2 完成補記」）。有意識的狀態更新，不是漏刪；下方原文保留。
> ~~**狀態：待客戶驗收。本文件不授權實作。**~~ 待客戶驗收（已由 DEC-133 通過）。本文件不授權實作（原宣告；實作授權來自 DEC-133，不來自本文件）。
> 依客戶 2026-11-04 正式覆核 (18)（逐字見 `docs/DECISIONS.md` DEC-132 fence；第二節「P2 文字線框先行」、第三節「資料串接邊界」）：本輪**只授權提出線框與驗證資料欄位**，**不授權直接實作新版面**；客戶確認線框後，才進入 P2 程式施工。
> **不是**新 Decision、**不是**第二套產品憲法、**不是** Real Feed／OneBrain／Digest 授權。基準：`origin/main` `cac19304`（#1009 P3 已合併）。
> docs 組單組撰寫、待總管複驗；全稱句的驗證方式逐處標明；「未驗」見文末。
> 效力順序（衝突時）：客戶原文（DEC-081／117／119／122／127／128～132 fence）＞ `NEWUI2_ACTIVE_PRESENTATION_CONTRACT_2026-11-03.md`（Active Contract，AI 整理文件）＞ 本文件。

**P2 範圍（客戶 (18) 二，僅兩項）**：① 🤖 OneBrain Outlook 位置調整；② 台股 Primary 主圖區塊＋短 SPEC 的**誠實空槽**（沒有正式歷史圖表資料時**不繪製假走勢線**）。
**要求保留**（客戶 (18) 二）：已核准的市場頁首屏順序與主 CTA；市場狀態、Risk Cap、是否需要行動、今日主要風險；既有圖表、卡片與資訊層級；手機四格導航、桌機原有布局。

---

## A. 現況首屏（以現行程式與已核准草稿為基準）

**現況取得方式**（驗證）：`PYTHONPATH=. AppTest.from_file("app_ui2.py")` 預設頁（📊，FAKE 冷啟動）逐個 `st.markdown` 取 `data-ui2-*` 錨點，得 DOM 順序 `[CTA q4, concl, q1, ctx, q2, q3]`（`market_l1`）→ `main_risk` → 指標卡 `ui2-grid` → `🤖 OneBrain Outlook`；程式讀點：`src/ui2/views/market.py:15-19`（`render`：`render_title` → `market_l1_html` → `render_cards` → `render_sections`）、`src/ui2/components/html.py:178`（`first_screen_html(cta_first=True)`）、`:228`（`market_l1_html`：四問區塊後**緊接** `main_risk_html`）、`src/ui2/shell/css.py:120-131`（桌機三 tile grid）、`src/services/ui2/scenarios.py:114-125`（`_sections_market`：`onebrain` 為 VM `sections` 第一個，L1）與 `src/services/ui2/real_canonical.py:307`（Real 同）。L2／L3（為什麼／指標明細／原始資料表）自 P3 起 Human UI 不渲染（DEC-131）。

### A.1 手機 390px 現況（由上而下）

| # | 元素 | 出處（條文／程式） |
|---|---|---|
| 1 | 頁首「📊 市場」 | `render_title`；Wireframes §2.1 |
| 2 | 🚀 更新今日戰情 CTA（含不可用原因，同列） | DEC-127、DEC-117 Q5；`first_screen_html(cta_first=True)` |
| 3 | 今日結論 | DEC-081 Q2-1／DEC-117 Q5；`conclusion_row_html` |
| 4 | 市場目前狀態（五態） | Wireframes §2.1；`q1` |
| 5 | Risk Cap `⬜ 無法判定` | Wireframes §2.1（Q1=A）；`ctx` 列 |
| 6 | 是否需要行動（W-10：Aggregator 前 `⬜ 尚未提供（待系統動作整合）`） | DEC-122 Q3=A；`q2` |
| 7 | 下一步 | `q3` |
| 8 | **今日主要風險**（L1，緊接，⛔ 被插隊） | DEC-122 Q3=A、DEC-117 Q6；`main_risk_html`（與 1–7 同一個 `ui2-m-l1` 容器內，不可能被其他元素插隊） |
| 9 | 核心指標卡（2 欄堆疊）：台股·VIX·US 10Y·利差·DXY·PMI／景氣 | Wireframes §2.1；`render_cards`（`ui2-grid`，`repeat(auto-fit,minmax(150px,1fr))`，`css.py:24`） |
| 10 | **🤖 OneBrain Outlook `⬜ 尚未提供`**（目前在最底） | `render_sections` 畫 VM L1 section `onebrain` |
| — | （無）台股 Primary 主圖／國際 small multiples／VIX 門檻帶／Macro mini／圖 C | VM 無這些區塊（`_sections_market` 只有 onebrain／why／detail／raw）；Wireframes §2.1 有，**本批不補**（見 C 末「不含」） |

### A.2 桌機 1440px 現況

`ui2-m-l1` 以 grid 排：列 1 CTA（獨立緊湊列）→ 列 2 今日結論 → 列 3 **三 tile：市場目前狀態｜Risk Cap｜今日主要風險** → 列 4 是否需要行動 → 列 5 下一步（`css.py:120-131`；DEC-117 Q1／Q5 桌機部分仍有效）；之後 → 指標卡列 → 🤖 OneBrain Outlook（最底）。桌機左側 Navigation Rail＝既有（本批不動）。

---

## B. 「今日主要風險／是否需要行動」排序差異核對（客戶特別要求）

### B.1 逐字引用

| 來源 | 排序（逐字） |
|---|---|
| **Active Contract §3.1**（表頭「應有（順序依 Wireframes §2.1／§2.2 與 DEC-127；`KEEP`）」） | 「頁首 → 🚀 更新今日戰情 CTA（含不可用原因）→ 今日結論（逐字）→ 市場目前狀態（五態；⛔ 偏多／中性／偏空）／Risk Cap（`⬜ 無法判定`）／今日主要風險（L1；退化句逐字）→ **是否需要行動** → `🤖 OneBrain Outlook`（§7）→ Primary 台股主圖（+SPEC）→ 核心指標卡…」 |
| **Wireframes §2.1 手機**（ASCII） | …「Risk Cap ⬜ 無法判定」→「**是否需要行動** … ② 不用滑」→（第一屏底）→「**今日主要風險**（L1，緊接，⛔ 插隊）← Q3-3；退化句逐字（DEC-117 Q6）」→「🤖 OneBrain Outlook ⬜ 尚未提供 …」→「Primary：台股主圖（約 220px）」→「核心指標卡…」 |
| **Wireframes §2.2 桌機**（ASCII） | 「┌市場目前狀態┐┌Risk Cap┐┌**今日主要風險**┐」→「**是否需要行動** …」→「🤖 OneBrain Outlook …」→「Primary：台股主圖＋MA 參考線（上緣入第一屏）」；並註：「桌機三 tile 排法沿用 DEC-117 Q1／Q5 桌機部分（仍有效）；手機依 Q3=A：『今日主要風險』移到第一屏後、緊接、⛔ 插隊（supersede map S10／S11）。」 |
| **DEC-117 Q1**（客戶，桌機） | 「桌機採 3 個核心狀態 tile：市場位階／建議總持股水位／今日主要風險」（手機 2＋1 部分已被 DEC-122 Q3=A 取代，只限手機） |
| **DEC-117 Q5**（客戶） | 「頁首 → 更新 CTA → 今日結論 → 3 個核心狀態 → ⚡需要處理 → AI／資料狀態 → Primary Visual」 |
| **DEC-117 Q6**（客戶） | 主要風險外露層採縮短行；「未評估不等於安全／資料不足／無法判定／尚未載入／真錯誤」退化／護欄句逐字外露（只管**內容**，不管順序） |
| **DEC-117 Q7**（客戶） | 手機第一屏優先順序：「今日結論 > 核心狀態 > 是否需行動 > Primary Visual」 |
| **DEC-122 Q3=A**（客戶，手機） | 手機第一屏不用滑：「市場目前狀態／Risk Cap／是否需要行動／主 Update CTA」；「『今日主要風險』緊接第一屏之後，仍屬 L1，不得被 L2／L3 插隊」；正式 supersede DEC-117 Q1 手機 2＋1 |
| **DEC-127**（客戶） | 「頁首 → 🚀 更新今日戰情 CTA → 今日結論 → 3 個核心狀態 tile」；四問是資訊需求，不代表 DOM 須固定 ①→④；「frozen visual contract 優先決定此頁 CTA 位置」 |
| **W-10 / Wireframes §9**（客戶 Q3 核准） | 「⚡ N」為 transitional contract，來源／範圍須標明；不改順序 |
| **Execution Spec §2 第 2 點**（AI 撰寫附件） | 「…→ 是否需行動（W-10…）→ 今日主要風險；**維持 DEC-127 已核准手機首屏順序與例外**。」 |
| **現行程式**（驗證：A 節 AppTest DOM 序＋`css.py:120-131`） | 手機＝CTA→結論→狀態→Risk Cap→**是否需要行動**→下一步→**今日主要風險**；桌機＝CTA→結論→**三 tile（含今日主要風險）**→是否需要行動→下一步 |

### B.2 判斷

- **差異的實質**：只有一處、且只在**手機**。Active Contract §3.1 把「市場目前狀態／Risk Cap／今日主要風險」寫成**同一格（以斜線連接）並排在「是否需要行動」之前**——這正是**桌機三 tile 排法**（Wireframes §2.2、DEC-117 Q1 桌機）；套到手機就與 Wireframes §2.1／DEC-122 Q3=A（手機：是否需要行動在前、今日主要風險緊接其後）相反。桌機沒有差異。
- **哪個是客戶已核准的視覺契約**：Wireframes §2.1／§2.2 經客戶 Q3「四頁 wireframe 核准」（DEC-123；Wireframes §9），手機順序另由客戶 DEC-122 Q3=A、DEC-127 裁示明確；三者皆為客戶原文依據。Active Contract 是 AI 撰寫的整理文件，其檔頭自述「**本文件不是新的客戶裁示**」，§3.1 表頭又自述「順序依 Wireframes §2.1／§2.2 與 DEC-127」——即它**委託**排序給 Wireframes，不是另立一套；§12 第 3 點也規定與客戶原文不一致時以原文為準。
- **現行實作與已核准契約一致**（B.1 末列）；Active Contract §3.1 該格不是客戶裁示，不得因整理而變更頁面責任。

### B.3 結論

> **以 Wireframes §2.1（手機）／§2.2（桌機）＋DEC-122 Q3=A＋DEC-127＋DEC-117 Q1／Q5 桌機部分為準。無兩處客戶原文互相矛盾，故不列為待客戶裁示。**
> 手機：…→ Risk Cap → 是否需要行動 → 下一步 → 今日主要風險 → **（P2）OneBrain → Primary 槽** → 指標卡；桌機：…→ 三 tile → 是否需要行動 → 下一步 → **（P2）OneBrain → Primary 槽** → 指標卡。
> 佐證：DEC-127 是客戶對 #1001 的整體接受，而 #1001 的手機順序即現行順序（是否需要行動在前、今日主要風險緊接其後）。本結論為**單組判斷、待客戶確認**（併入 G 開頭的線框確認）。
> 頁面責任不變；**P2 不改上述任何順序**（只在今日主要風險之後插入 OneBrain 與 Primary 槽）。

### B.4 最小勘誤提案（**僅提案，未套用到 Active Contract**）

Active Contract §3.1 為 AI 整理文件、且屬扁平轉述（非單純筆誤——它在桌機語意下是對的），故**不由本批直接改**。提案由總管在客戶驗收本線框後一併處理（內部文字勘誤，不需客戶裁示）：在 §3.1 該格之後加一句 📌「**手機**：是否需要行動 → 今日主要風險（DEC-122 Q3=A）；**桌機**：三 tile（狀態／Risk Cap／今日主要風險）→ 是否需要行動（Wireframes §2.2）。本格斜線表同 tile 並列，非手機 DOM 順序。」原文保留不刪。落盤處：`BACKLOG` `NUI2-ACTIVE-CONTRACT-VS-WIREFRAME-RISK-ORDER`（本批已更新為「已判定：以 Wireframes／DEC-122／DEC-127 為準；勘誤待套用」）。

---

## C. P2 最小差異（只兩項）

**線框約定**：左＝現況，右＝P2 提議；只標差異（`◀ 移動` `◀ 新增`）；未標者＝未動。字樣只用既有字樣表（`shared/ui2_contract/text.py`：`⬜ 尚未提供` 等）與既有核准用語。

### C.1 手機 390px

```
現況                              P2 提議
┌────────────────────────┐        ┌────────────────────────┐
│ 📊 市場                 │        │ 📊 市場                 │
│ [🚀 更新今日戰情] 原因  │        │ [🚀 更新今日戰情] 原因  │
│ 今日結論 …              │        │ 今日結論 …              │
│ 市場目前狀態 …          │        │ 市場目前狀態 …          │
│ Risk Cap ⬜ 無法判定    │        │ Risk Cap ⬜ 無法判定    │
│ 是否需要行動 …          │        │ 是否需要行動 …          │
│ 下一步 …                │        │ 下一步 …                │
│ 今日主要風險 …          │        │ 今日主要風險 …          │
│                        │        ├────────────────────────┤
│                        │        │ 🤖 OneBrain Outlook    │ ◀ 移動
│                        │        │   ⬜ 尚未提供          │   （自最底上移）
│                        │        ├────────────────────────┤
│                        │        │ 🇹🇼 台股趨勢            │ ◀ 新增（空槽）
│                        │        │  ⬜ 尚未提供            │
│                        │        │  此項目尚未開放         │
│                        │        │  （灰底說明，無走勢線） │
│                        │        │ SPEC｜<來源>｜資料日    │
│                        │        │  資料日 <日期>｜缺值不補│
│ 台股 │ VIX             │        │ 台股 │ VIX             │
│ US10Y│ 利差            │        │ US10Y│ 利差            │
│ DXY  │ PMI／景氣       │        │ DXY  │ PMI／景氣       │
│                        │        │                        │
│ 🤖 OneBrain Outlook    │        │ （已上移）              │
│   ⬜ 尚未提供          │        │                        │
└────────────────────────┘        └────────────────────────┘
```

### C.2 桌機 1440px

```
現況                                           P2 提議
┌──────────────────────────────────────────┐   ┌──────────────────────────────────────────┐
│ [🚀 更新今日戰情] 原因                     │   │ [🚀 更新今日戰情] 原因                     │
│ 今日結論 …                                │   │ 今日結論 …                                │
│ ┌市場狀態┐┌Risk Cap┐┌今日主要風險┐         │   │ ┌市場狀態┐┌Risk Cap┐┌今日主要風險┐         │
│ 是否需要行動 …                             │   │ 是否需要行動 …                             │
│ 下一步 …                                  │   │ 下一步 …                                  │
│                                          │   │ 🤖 OneBrain Outlook ⬜ 尚未提供            │ ◀ 移動
│                                          │   │ ┌🇹🇼 台股趨勢 ⬜ 尚未提供 · 此項目尚未開放┐ │ ◀ 新增
│                                          │   │ │ （灰底說明，無走勢線）                  │ │   （空槽，全寬）
│                                          │   │ │ SPEC｜<來源>｜資料日 <日期>｜缺值不補      │ │
│                                          │   │ └────────────────────────────────────┘ │
│ 台股 VIX US10Y 利差 DXY PMI／景氣 (卡列)   │   │ 台股 VIX US10Y 利差 DXY PMI／景氣 (卡列)   │
│ 🤖 OneBrain Outlook ⬜ 尚未提供            │   │ （已上移）                                  │
└──────────────────────────────────────────┘   └──────────────────────────────────────────┘
```

### C.3 項目 ①：🤖 OneBrain Outlook 位置

| 項 | 內容 | 條文依據 |
|---|---|---|
| 現位置 | 指標卡**之後**（頁面最底的 L1 section） | 驗證：A 節 DOM 序 |
| 提議位置（手機） | **今日主要風險之後、Primary 槽之前、指標卡之前** | Wireframes §2.1（「今日主要風險 → 🤖 OneBrain Outlook → Primary → 核心指標卡」）；Active Contract §7（「位置依 Wireframes §2.1／§2.2〔今日主要風險之後、Primary 圖之前〕」）；Execution Spec §2 第 3 點 |
| 提議位置（桌機） | **是否需要行動／下一步之後（三 tile 已含今日主要風險）、Primary 槽之前、指標卡之前**，單行 | Wireframes §2.2（「是否需要行動 → 🤖 OneBrain Outlook → Primary」）；DEC-117 Q5（「…⚡需要處理 → AI／資料狀態 → Primary Visual」） |
| 內容 | **不變**：標題「🤖 OneBrain Outlook」＋`⬜ 尚未提供`（capability）＋原因句；不新增文案 | Active Contract §7（未啟用前＝`⬜ 尚未提供`）；DEC-124（`⬜ 尚未提供`＝Capability，⛔ 第六態、⛔ confidence） |
| 與核准草稿核對 | 位置與 Wireframes §2.1／§2.2 **一致**——即把現況的實作偏離（置底）修回已核准位置，**不是新版型**（Wireframes 草稿本就有此位置；Active Contract §12 第 4 點「把壞畫面修回 contract 不在此限」，惟客戶要求仍先出線框，故本批照做） | 驗證：逐字對照 B.1 |
| **不含** | Wireframes 所畫的「資料狀態 ✅ 14／16 可讀」coverage chip：VM 無對應欄、需 Digest coverage（`NUI2-P3-DIGEST-CLOSURE-STATIC-ONLY` 維持 open），**本批不加**，仍是現行偏離，登記不變 | 客戶 (18)「VM 保存≠Digest 已有」 |

### C.4 項目 ②：台股 Primary 主圖區塊＋一行 SPEC（誠實空槽）

| 項 | 提議 | 條文依據 |
|---|---|---|
| 位置（手機） | OneBrain 之後、指標卡之前；**不得**被其他內容插隊 | Wireframes §2.1；DEC-117 Q7（「Primary 必須緊接 L1 決策區後方，不得被其他 L2／L3 長內容插隊」） |
| 位置（桌機） | OneBrain 之後、指標卡列之前，全寬 | Wireframes §2.2（「Primary：台股主圖…（上緣入第一屏）」）；Execution Spec §2「Primary 主圖優先露出」 |
| 尺寸原則 | **不自創 px**。條文已有者：真圖時手機約 220px（DEC-119／DEC-117 Q4 註），桌機上緣入第一屏（Wireframes §2.2）；**空槽本批依內容高度**（標題＋一行說明＋SPEC 行），不預留 220px 空框（避免把「尚未提供」畫成「載入中的圖」）；≥769px 全寬 | 條文引用；空槽高度是否採內容高度＝**G-1 待確認** |
| 標題 | 「🇹🇼 台股趨勢」（客戶 DEC-117 Q4 原詞：「🇹🇼 台股趨勢＝Primary Visual」；「Primary」為內部詞，不上畫面） | DEC-117 Q4 |
| 空槽文案 | 狀態用既有 Capability 字樣 **`⬜ 尚未提供`**（`TEXT_NOT_PROVIDED`）＋既有原因句家族「此項目尚未開放」（同 `scenarios._R_EMPTY`／`real_canonical._R_PORT`）；**灰底說明，⛔ 紅**（Wireframes §6 冷啟動「圖槽灰底說明（⛔ 紅）」）；**不新造字樣**；⛔ 不畫假走勢線／假 sparkline／假 MA；⛔ 用 `⬜ 資料未取得`（那是資料語意 Missing，與 Capability 正交，DEC-124／DEC-130） | `shared/ui2_contract/text.py`；Wireframes §6；DEC-124 |
| SPEC 行格式 | `SPEC｜<來源>｜資料日 <日期>｜缺值不補`（範式取 Active Contract §4 最小集 `SPEC｜<頻率>｜<來源>｜資料日 <MM/DD>｜<缺值處理>`，**本批省略頻率欄**，見 G-2）。**規則：欄位值只取 TWII 指標卡既有 `freshness`，無正式欄位的值不手寫**：`<來源>`＝卡的 `freshness.source`；`<日期>`＝卡的 `freshness.as_of`（缺 → `⬜ 資料日未提供`，`TEXT_ASOF_MISSING`）；「缺值不補」是政策字樣（非資料值）；⛔ 手寫日期、⛔ 寫服務名冒充資料源。**`<來源>` 缺值**（FAKE 冷啟動時 TWII 卡 source＝None）：`shared/ui2_contract/text.py` **沒有**「來源缺值」既有字樣（`TEXT_ASOF_MISSING` 只管資料日），故**不自創**——列為 G-2 待確認；確認前的最小處理＝該欄整段省略（與 `freshness_html` 對缺 source 的現行處理一致：不畫來源 chip），⛔ 補預設來源。**日期格式**：卡的 as_of 是 ISO `YYYY-MM-DD`（`market_twii_view_service._iso`），`freshness_html` 現行原樣顯示；範例的 `MM/DD` 只是範式。本線框採**原樣帶出 ISO、不轉換**（與卡一致、避免第二套日期格式）；若要轉 `MM/DD`，轉換規則由施工決定，並**列入 G-2 讓客戶確認** | Active Contract §4；`html.freshness_html` |
| ⚠ 與範例的兩處差異（據實） | (a) **來源不是「TWSE」**：範例的 `TWSE` 只是範式；TWII 卡實際 source＝`TWII_SOURCE_TEXT`＝「本地加權指數歷史快取（來源 Yahoo，每日更新）」（`src/services/market_twii_view_service.py:23`），SPEC 必須照卡原樣帶出，⛔ 改寫成 TWSE。(b) **「日頻」不採用為預設**：卡沒有頻率欄；佐證只有 service 註解「parquet 每一列就是一個交易日」＋`TWII_SOURCE_TEXT`「每日更新」，不是正式欄位，依本節規則（無正式欄位的值不手寫）**本批省略頻率欄**；手寫「日頻」須客戶於 G-2 **明示同意**（沉默不等於同意） | 驗證：讀 `market_twii_view_service.py:23,68-98` |
| 空槽的 SPEC 在說什麼 | SPEC 描述的是**這個槽將使用的正式資料來源／資料日**（取自已接線的 TWII 最新收盤事實），**不代表歷史序列已接**；空槽本體文案已明講 `⬜ 尚未提供`。避免誤導：SPEC 行不得出現「近 N 日」「MA」等區間／指標欄位（本批沒有序列，不自造） | `TWII 最新收盤值≠歷史圖表資料`（客戶 (18) 三） |
| TWII 冷啟動／失敗時 | 卡為 Missing／Unavailable 時，SPEC 的來源／資料日依卡原樣（缺 → `⬜ 資料日未提供`）；槽本體仍是 `⬜ 尚未提供`；不因卡 Unavailable 把槽改紅（槽是 Capability，與卡的 Data State 正交） | DEC-124／DEC-130 |
| **不含（本批不做）** | 歷史序列、MA 參考線、y 軸、圖例、護欄句（Wireframes §2.1「加權＋MA『參考線』＋護欄句」＝真圖才有）；國際 small multiples／VIX 門檻帶／Macro mini／圖 C 空槽（VM 無區塊，非 P2 兩項）；micro-tag 統一（原批次表 ③）；coverage chip | 客戶 (18) 二「本次只規劃」兩項 |

---

## D. 保留清單核對

| 客戶要求保留 | 是否動到 | 驗證方式 |
|---|---|---|
| 已核准市場頁首屏順序（頁首→CTA→今日結論→…） | **未動** | P2 只在 `market_l1_html` 容器**之後**插入；容器內 DOM／CSS 不改（`html.py:178-231`、`css.py:120-131` 不在變更集） |
| 主 CTA（🚀 更新今日戰情；位置、不可用原因同列） | **未動** | 同上 |
| 市場目前狀態／Risk Cap `⬜ 無法判定`／是否需要行動／今日主要風險（含 DEC-117 Q6 退化句、W-10 transitional） | **未動** | 同上；VM／canonical 0 變更 |
| 既有圖表／卡片／資訊層級（指標卡 6 張、每卡值·短狀態·as_of·源） | 卡片本身與其相對順序、樣式**未動**；⚠ **但手機上卡片的垂直位置會下移**（上方多出 OneBrain＋空槽）：QA 實測原型——手機 cold 指標卡 grid 頂緣 560→798px（>導覽上緣 791，約 +240px，卡片被推到第一屏之下）；桌機 475→688px 仍在第一屏；stale／unavailable 導覽餘裕 166.5→162.5px（逼近 160px 底線，空槽高度會再縮餘裕）。→ **「第一屏不增不減」不實，已更正**，列 **G-3 待客戶確認** | `render_cards` 不改；位置變化為獨立 QA 原型實測（本檔未重測） |
| 手機底部四格導航、桌機左側 Rail（含 compact Account Area 的現況） | **未動** | shell 不在變更集；DEC-127 導覽餘裕判定器須維持綠（見 F） |
| 沒有正式歷史圖表資料時不繪製假走勢線 | **遵守**：空槽 0 個 svg／vega／polyline／canvas | F 的新守衛 |
| Single Action Authority／Risk Cap／System Action／Digest／OAuth | **未動** | 變更集不含 `src/services`、`shared`（選項 ii）；見 E |

---

## E. 資料位置對照（對 #1007 計畫與 REAL_FEED_MAPPING）

分類沿用 #1007 計畫 §1（A 已接／B 已有 service 未接／C PORT／D Data Gap／E 正式限制）；Stop Gate 沿 REAL_FEED_MAPPING §6。

| 槽／欄位 | 現有 VM 欄位（檔案:符號） | canonical service | 分類 | Stop Gate／備註 |
|---|---|---|---|---|
| OneBrain 槽（標題＋`⬜ 尚未提供`） | `PageVM.context.sections` key `onebrain`（`scenarios.py:_sections_market`；`real_canonical.py:_market`） | 無（Stage G，產品碼 0 檔） | **E**（能力未核准）；本批只動**位置**，內容原樣 | SG-09；不碰 Digest／OneBrain runtime |
| OneBrain「資料狀態」coverage chip | **無** | 需 Digest evidence coverage | **D／E**（缺資料＋需新契約） | SG-09；`NUI2-P3-DIGEST-CLOSURE-STATIC-ONLY` 維持 open；**本批不加** |
| Primary 槽標題＋`⬜ 尚未提供`＋原因句 | **無對應 VM 欄**（Capability 標記，非資料） | 無 | 純 presentation 空槽 | 實作二選一見 F-5；不新增資料來源 |
| SPEC 資料日 | `CardVM(card_id="twii").field.freshness.as_of`（`html.freshness_html`）；來源鏈 `twii_card_spec` ← `TwiiFact.as_of` ← `TwiiTrendView.as_of` | `market_twii_view_service.get_twii_trend_view`（`:68`；新鮮度取自 `load_twii_close().attrs`） | **A 已接** | 缺 → `⬜ 資料日未提供`；⛔ 補今天 |
| SPEC 來源 | `…field.freshness.source` ← `TwiiFact.source` ← `TWII_SOURCE_TEXT`（`market_twii_view_service.py:23`） | 同上 | **A 已接** | 內容為「本地加權指數歷史快取（來源 Yahoo，每日更新）」，非 TWSE |
| SPEC 頻率 | **無欄位** | service 註解「parquet 每一列就是一個交易日」；來源字串「每日更新」 | D（無正式欄，僅註解佐證） | **本批省略頻率欄**；手寫「日頻」須客戶明示同意（G-2）；不新增來源 |
| SPEC 來源缺值字樣 | 卡 `freshness.source=None`（FAKE 冷啟動） | — | D（無既有字樣） | 不自創；待 G-2；暫以整欄省略 |
| SPEC 日期格式 | 卡 `freshness.as_of`＝ISO `YYYY-MM-DD` | `_iso()` | A | 原樣帶出；轉 MM/DD 列 G-2 |
| SPEC「缺值不補」 | 政策字樣（Active Contract §4），非資料 | — | 政策字樣 | 與 §1 Fail Loud 同向；不產生數值 |
| **歷史序列 xs／close** | `TwiiFact.close`（目前長度 1） | `get_twii_trend_view(n)` **已能回 n 日 xs/close**（`TwiiTrendView.xs/close`）；UI2 `real_feed.TWII_CARD_DAYS = 1`（`real_feed.py:30`）只呼叫 n=1 | **B 已有 service 未接** | **本批不接**：改 n、或把序列放進 VM＝接線批（依 #1007 §7／REAL_FEED_MAPPING；`NUI2-TWII-TWO-PATHS` 須先擇一：`twii_ohlcv.parquet` vs readiness `taiex`）；**TWII 最新收盤值≠歷史圖表資料**（客戶 (18) 三） |
| **MA（MA5／60／120／200）** | **無** | Legacy 圖 A 的 MA 是 `market_strategy.get_market_assessment` 算好、經 session `mkt_info` 傳入的**最新純量**水平參考線，非滾動序列（`src/ui/views/_market_blocks.py:224-226, 622`）；來源在 session，未 PORT | **C PORT** | **本批不接、不自造滾動算法**；若要新增滾動 MA＝新公式（SG-14，Opus High／Gate） |
| y 軸／圖例／護欄句 | 無 | 隨真圖 | 隨接線批 | 同上 |

**邊界（逐字落實客戶 (18) 三）**：不新增資料來源、MA 公式或圖表判斷；不改 Risk Cap、System Action、Digest schema、OAuth；不以 UI ViewModel 取代完整 Decision Digest。**VM 保存≠Digest 已有**：OneBrain 槽只是位置調整的誠實佔位，**不是** Digest／OneBrain 可讀完整資料的證據。
**未驗（據實）**：「`get_twii_trend_view(n)` 能回 n 日序列」依讀碼（`market_twii_view_service.py:68-98`）與 #1007 計畫；本批**未**對實際 parquet 做 n>1 runtime 驗證（也不該，因本批不接）。「MA 來源在 session」依讀碼 `_market_blocks.py` 註解與 #1007 QA 勘誤；未窮舉其他 caller。

---

## F. 驗收準則與施工邊界（供客戶確認後 P2 施工）

1. **T_new_6 現況**：`tests/test_ui2_contract_teeth_pending.py::test_T_new_6_main_chart_has_short_spec_line`（`@_xfail("P2")`，strict）＝ `at = _at(); assert "SPEC｜" in _blob(at)`——只檢查**預設頁（📊 FAKE 冷啟動）任一 markdown 含 `SPEC｜`**。施工後該字串出現 → strict XPASS → 轉紅 → **必須移除 xfail、畢業到 `GRADUATED_TEETH`**（`test_ui2_active_contract_docs.py` 的 xfail 計數斷言 `n == 4` 同步改 `3`，非降守衛）。
   **建議加強（不弱化）**：T_new_6 保持原斷言不放寬，另加具名測試鎖定 (a) `SPEC｜` 行的 DOM 位置**在 OneBrain 之後、指標卡 `ui2-grid` 之前**；(b) SPEC 行的 `<來源>`／`<資料日>` 與 TWII 卡 `freshness` **字面相等**（FAKE 與 Real 固定 snapshot 各一）；(c) 空槽 0 個 `svg／polyline／canvas／vega`、且含 `⬜ 尚未提供`。
2. **順序守衛**：新增 DOM 順序測試——`ui2-m-l1`（內含 CTA→結論→…→今日主要風險）< 🤖 OneBrain < `🇹🇼 台股趨勢`槽 < `ui2-grid`；既有 `tests/test_ui2_batch3.py::test_main_risk_is_not_interleaved_by_expanders_in_the_real_page`（`m-l1 < ui2-grid`、L1 之後首個元素非 expander）預期**不需改**仍綠（驗證：讀測試碼；施工時以實跑為準）。`tests/test_ui2_p1_human_text.py::test_market_page_has_each_first_screen_label_once_and_keeps_anchors`（`OneBrain Outlook` 只出現一次）須仍綠——OneBrain 移位不可造成重複渲染（實作注意：`render_sections` 不得再重畫已上移的 `onebrain` section；施工時 `market.render` **須保留對 `render_sections` 的呼叫**〔可加 skip 參數〕，否則 `tests/test_ui2_p3_evidence_preservation.py::test_render_policy_guard_has_teeth` 失去牙）。
3. **第一屏必要項不得退化（W-2）**：手機 390px 第一屏「今日結論＋狀態＋Risk Cap＋是否需要行動＋主 CTA」及其後「今日主要風險緊接」維持；**四必要項與今日結論不變**，但手機指標卡會被推到第一屏之下（見 D 表與 G-3）；**W-2／Wireframes §2.1 是否把指標卡算進第一屏必要項**——據實查證：W-2 與 §1 第一屏四問表列的必要項是「今日結論＋市場目前狀態＋Risk Cap＋是否需要行動＋主 CTA」（今日主要風險緊接其後），**未列指標卡**；Wireframes §2.1 的「第一屏底（≈791）」線畫在「是否需要行動」之後、今日主要風險之前，即連今日主要風險與其後的指標卡在該草稿中本就在第一屏線之下；DEC-117 Q7 亦接受 Primary 在手機第一屏下方。據此指標卡下移**看似**不違反條文，但這是單組讀法、**不自行定論**，交 G-3 由客戶確認。**新增驗收條件**：手機 stale／unavailable 導覽餘裕 **≥160px**，若施工後不達須**停手回報**，不得以縮字或刪資訊硬塞。`tests/ui2_viewport/measure_viewport.py` 既有判定（含 DEC-127 導覽餘裕、`p3_no_evidence_expander`）須維持全綠（FAKE 70 態＋Real 11 態；Streamlit 1.59.2 與 1.56.0 floor 各一輪）。
4. **截圖**：真實 390px 與 1440px 截圖（📊 × FAKE 冷啟動／已載入／Unavailable／Stale ＋ Real），**不只依 DOM**；目視確認：OneBrain 位置、空槽無走勢線、灰底非紅、SPEC 允許換行、**不橫向捲動**（SPEC 長度上限依 Active Contract §4 以 390px 實測決定，不釘死數字）、指標卡未被推出導覽可點區。
5. **實作形態（內部技術決策，§-1.5.A-4，不需客戶裁示；此處只登記推薦）**：(ii)（推薦）`views/market.py` 內以既有常數（`TEXT_NOT_PROVIDED`、既有原因句家族）組空槽，SPEC 從 TWII 卡 `freshness` 組；VM／canonical／scenarios／baseline **0 變更**，P3 evidence-preservation baseline 與 sha256 釘值不動；(i) 在 VM 新增 L1 section 承載空槽＝VM 內容變更，須重跑 baseline 並說明——較大改動面，不推薦。兩者畫面相同。無論哪種，`tests/test_ui2_guards.py`（G2／G2F／G4／G9／no-write／禁用字樣）須全綠。
6. **mutation（施工時必附，實測轉紅後還原）**：拿掉 SPEC 行 → T_new_6 紅；把 OneBrain 放回卡片之後 → 順序測試紅；空槽畫入 `<svg>`／`<polyline>` → 無假圖守衛紅；SPEC 來源改寫死 `TWSE` → 與卡 freshness 相等測試紅。
7. **需更新的測試（預期）**：`test_ui2_contract_teeth_pending.py`（T_new_6 去 xfail）、`test_ui2_active_contract_docs.py`（`GRADUATED_TEETH`＋1、xfail 計數 4→3、本批 DEC-132／線框文件守衛已先加）；其餘既有測試預期不改（不得改弱）。`PENDING_UI_CORRECTION_TESTS` 不受影響。
8. **Model×Effort**：**Sonnet 5.5＋Medium**。理由：純 presentation（排序與誠實空槽）、不改 VM schema／`level` 語意、不接真資料、不涉 Risk Cap／System Action／Digest／OAuth／公式／門檻，不觸 Opus Gate 條件（BACKLOG §5.1.26 候選 B；DEC-084）。**STOP → Opus 5.5＋High／Gate 的觸發**：施工中需改 `get_twii_trend_view` 呼叫期數、新增任何序列／MA、改 VM schema，或想在空槽顯示任何非 `⬜ 尚未提供` 的數值。
9. **仍禁止**：實作前未經客戶驗收本線框；任何歷史序列／MA／假圖；新增 Human UI expander；把 OneBrain 槽寫成「已可讀完整資料」；一批超過 3 項（P2 本批僅 ①②）。

---

## G. 待客戶確認項

**順序／頁面責任**：**無需新裁示**（B 節：現行實作與已核准契約一致；P2 不改任何既有順序，OneBrain 位置亦與 Wireframes §2.1／§2.2 一致）。⚠ 請注意：你確認「線框 OK」即**一併確認** B 節結論「以 Wireframes §2.1／§2.2＋DEC-122 Q3=A＋DEC-127 為準」——該結論為**單組判斷、待客戶確認**。若同意，請確認「線框 OK，進入 P2 施工」。

以下三點，Wireframes／Active Contract **沒有條文可直接套用**，請一句話確認（回覆如「G-1 A、G-2 B、G-3 A」）。**沉默不等於同意**：G-2 的 A 選項（手寫值）與 G-3 的接受須客戶明示；未回覆時只採 G-1 推薦與 G-2 B：

1. **G-1 空槽高度**：A＝依內容高度（標題＋一行說明＋SPEC 行）｜B＝預留手機約 220px／桌機與真圖同高的灰框。**推薦 A**：B 會把「尚未提供」畫成像載入中的圖、並把指標卡推下，違反誠實與第一屏後續可讀性；真圖接線批再採約 220px（DEC-119）。
2. **G-2 SPEC 欄位**：A＝顯示固定字樣「日頻」（依據：service 註解＋來源字串「每日更新」；屬手寫值，**須您明示同意**）｜B＝本批省略頻率欄，SPEC 只含 `來源｜資料日｜缺值不補`。**推薦 B**：本檔自定規則是「SPEC 欄位值只取卡 freshness、無正式欄位的值不手寫」，A 會自我矛盾；頻率於接線批有正式欄位時再補。附帶兩小點（施工預設已寫於 C.4，可不回覆）：(i) TWII 卡來源缺值時，既有字樣表沒有對應字樣，預設整欄省略、不自創；(ii) 日期預設原樣帶 ISO `YYYY-MM-DD`，若要改 `MM/DD` 請說明。
3. **G-3 手機指標卡下移**：P2 會把手機指標卡推到第一屏之下（QA 原型實測：cold 時卡片頂緣 560→798px，導覽上緣 791px；stale／unavailable 導覽餘裕 166.5→162.5px，須 ≥160px）；四必要項與今日結論不變；依 Wireframes §2.1 的第一屏線與 DEC-117 Q7，Primary 可在第一屏下方（W-2 未把指標卡列為第一屏必要項，單組讀法）。請選：A＝接受（OneBrain＋空槽如線框）｜B＝壓縮空槽高度（更貼近內容、仍在指標卡之前）｜C＝Primary 空槽放指標卡之後（OneBrain 仍上移）。**推薦 A**：位置與已核准草稿一致（Wireframes §2.1 Primary 在卡片前）、不縮字不刪資訊；B／C 偏離草稿順序或僅微幅改善。若餘裕實測 <160px，施工停手回報，屆時才考慮 B。
---

## 限制與未驗（據實）

- docs 組**單組**撰寫，未經第二組獨立複驗；B 節判斷（Active Contract §3.1 為桌機三 tile 的扁平轉述）是讀條文所得，**未**經客戶明示確認——但結論僅是「以客戶已核准者為準」，未新增任何決定。
- 線框為 ASCII 示意，**無 px 實測**（本批不實作）；390／1440 是否放得下、SPEC 單行是否撐破，須施工後截圖實測（F-4）。
- 現況 DOM 序以 FAKE 冷啟動 AppTest 驗得；Real 與其他場景的同序依讀碼（`render` 對所有場景同一路徑）推得，**未逐場景實跑**。
- 全稱句：「P2 不改任何既有順序／內容」＝依 `market.py` 讀碼與 C 節設計，施工後以 F 的守衛驗證；本檔不可當作已驗證。
- Safari／Firefox／真機／Cloud 未驗（沿 P1／P3 登記）。
