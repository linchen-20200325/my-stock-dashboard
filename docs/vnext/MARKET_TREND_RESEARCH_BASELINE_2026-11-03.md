# 市場趨勢 Research Baseline（台股趨勢／國際趨勢）— 正式 vNext research／market spec

> 2026-11-03 新增（append-only 文件）。決策者 **客戶**（2026-11-03 指示 (10) A 節 A1～A5，逐字見 `docs/DECISIONS.md` DEC-125）；撰寫＝文件組（單組產出，**未經第二組獨立複驗**，`CLAUDE.md` §-2 規則 6）。
> **性質**：Research Baseline ＋ 市場產品主軸規格。**不是** production rule、**不是** Decision（DEC-125 才是）、**不是**動工授權（`CLAUDE.md` §-1）。
> **不建立第二份 SSOT**：本檔只做「維度清單＋定位＋禁止事項＋Pending＋現況盤點」的**收斂索引**；下列既有落盤原樣有效，本檔只 cross-reference，不改其一字：
>
> | 既有落盤（原樣有效） | 保存什麼 |
> |---|---|
> | `docs/DECISIONS.md` DEC-071（客戶 2026-10-22） | 研究只保留**兩主軸**（台股趨勢、國際趨勢）；「大盤」字樣；研究框架非 Approved |
> | `docs/PROJECT_STATE.md` §22（22.2～22.4） | 客戶 2026-10-22 研究框架原文逐條（含 EPS×PE、外資籌碼、AI/CSP capex、長債殖利率×景氣領先指標）＋四概念分離＋「研究框架 → repo 對照」簡表 |
> | `docs/DECISIONS.md` DEC-091(g)／DEC-092 | EPS×PE 保留 Research Framework、正式公式仍需 High Gate；示意值不得當 production |
> | `docs/BACKLOG.md` `VN1-MT-TREND-DEF`／`VN1-MT-VALUATION`／`VN1-MT-YIELD-CLI`／`VN1-MT-CAPEX-EPS`／`VN1-MT-LEGACY-GAP`／`DEC092-EPSPE-HIGH-GATE`／`NSR-*` | 各項 Pending／Decision Gate |
> | `docs/vnext/FINAL_UI_CONTRACT_FREEZE_2026-11-02.md` §11（客戶 §43） | 大盤 EPS×PE 與單檔估值**分開治理**、大盤維持 Research |
> | `docs/vnext/MARKET_PAGE_DECISION_GATE_2026-10-24.md` X5～X9／J01／G11 | 📊 市場頁原始資料層與「研究中」純說明槽 |
>
> **本檔新補（既有落盤沒有的）**：① A1／A2 維度清單**以客戶 2026-11-03 原文為準**的完整版（舊落盤只涵蓋其中一部分，見 §2 對照）；② 每個維度的**定位**（objective input／research dimension／context overlay）；③ 「不得自行」清單的**正式位置**；④ 現況盤點（FACT／INFERENCE）；⑤ A3 產品主軸規則；⑥ 與 A4 中性命名的銜接（規則本體在 `PROJECT_RULES.md` 第 28 節）。

---

## 1. 永久語意（客戶 (10) A1／A2／A3，逐字處見 DEC-125）

1. **EPS × PE 只是台股大盤情境估值方法之一，不等於完整市場趨勢判斷。**（客戶 A1）
2. 台股趨勢、國際趨勢的各維度**只能**作 **objective input／research dimension／context overlay**；除非 repo 已有正式 validated deterministic contract，**禁止**自行重新組成多頭／空頭公式、scoring model、Risk Cap rule、System Action、probability。（客戶 A2）
3. **正式市場趨勢只保留兩條主軸：1. 台股趨勢　2. 國際趨勢。**Old UI／Legacy New UI 只作 **capability／logic／source reference**，**不得**重新增加第三、第四套市場主軸。（客戶 A3）
4. 尚未正式核准的 source／formula／horizon／update frequency／PE rationale **保持 Pending／Decision Gate**。（客戶 A1）

### 1.1 三個定位詞（本檔用法；客戶原文只用這三詞，下列釋義為文件組讀法〔INFERENCE〕）

| 定位 | 讀法 | 允許 | 不允許 |
|---|---|---|---|
| **objective input** | 已存在、可追溯來源的客觀數值（事實層） | 原樣呈現（帶來源、as-of、單位、五態資料語意）；作為既有正式 contract 的**既有**輸入 | 在本層新增門檻、加權、合成 |
| **research dimension** | 研究時值得觀察的面向（尚無正式判讀規則） | 文字說明、原始數據並列、研究報告 | 產生結論、燈色、多空字樣 |
| **context overlay** | 疊在主圖／主卡旁幫助理解的脈絡（非判定） | 並列顯示、標註「不構成判斷」 | 影響 System Action／Risk Cap／任何 verdict |

---

## 2. A1 台股趨勢 Research Baseline

客戶原文維度（A1，逐項）與已落盤對照（FACT＝文件內查得；對照依據＝2026-11-03 對 `PROJECT_RULES.md`／`docs/DECISIONS.md`／`docs/BACKLOG.md`／`docs/PROJECT_STATE.md`／`docs/vnext/*.md` 的關鍵字 grep，**單組、未窮舉**）：

| # | 維度（客戶 A1 原文） | 定位 | 舊落盤 | 本檔補 |
|---|---|---|---|---|
| 1 | EPS × 合理 PE 的加權指數情境估值 | research dimension（**Research Gate**） | ✅ DEC-091(g)／DEC-092／Freeze §11／BACKLOG `DEC092-EPSPE-HIGH-GATE`、`VN1-MT-VALUATION`／PROJECT_STATE §22.2 | 永久語意、Pending 清單（§4）、與單檔估值分離（§6） |
| 2 | 外資籌碼 | objective input（既有燈）＋research dimension | ✅ PROJECT_STATE §22.2「外資籌碼是台股趨勢的重要觀察面向」；§22.4 對照 | 定位 |
| 3 | 融資 | objective input（既有 `margin` 燈；單位混用「資料疑義」） | ⚠️ 只在 Gate 檔 X8／F10、CLAUDE.md §1.A 資料疑義規則；**未**列為趨勢研究維度 | **新補**為趨勢 research dimension |
| 4 | 市場擁擠度 | research dimension（**無定義**） | ❌ 無（grep「擁擠」只命中與本題無關之處；`docs/vnext` 無市場擁擠度定義） | **新補**＋Pending（§4 `MKT-RB-CROWDING`） |
| 5 | 回撤／市場風險 | research dimension；相鄰既有物件見 §5（不得混同） | ❌ 無（grep「回撤」於 PROJECT_RULES／docs 0 命中） | **新補**＋Pending（`MKT-RB-DRAWDOWN`） |
| 6 | 市場廣度 | objective input（既有 `adl`、`jingqi` 燈）＋research dimension | ⚠️ 只散見 Gate 檔 C06／X5、BACKLOG `VN1-MT-SSOT-ADL-LABEL`、`NSR-*`（真實廣度）；**未**列為趨勢研究維度 | **新補**為趨勢 research dimension |

### 2.1 客戶 2026-10-22 原有研究框架（仍有效，不重複抄錄）

PROJECT_STATE §22.2「台股」四條：短期修正與長期趨勢分開閱讀；EPS×PE 情境估值矩陣；外資籌碼；AI／CSP capex 傳導（含 capex 過高、現金流下降的反面風險）。**A1 清單與之取聯集**：A1 六項（本節表）＋§22.2 的「短期 vs 長期分開閱讀」「AI/CSP capex 傳導」兩項（後者續由 `VN1-MT-CAPEX-EPS` 承接）。**兩份清單不互相取代。**

---

## 3. A2 國際趨勢 Research Baseline

客戶原文維度（A2，逐項；全部只能是 objective input／research dimension／context overlay）：

| # | 維度（客戶 A2 原文） | 定位 | 舊落盤 | 本檔補 |
|---|---|---|---|---|
| 1 | 長債殖利率 | objective input（既有 `us10y` 燈＝FRED DGS10 單點） | ✅ PROJECT_STATE §22.2／22.4、`VN1-MT-YIELD-CLI` | 定位 |
| 2 | 殖利率曲線 | research dimension | ⚠️ `NSR-YIELD-SPREADS`／`NSR-US2Y`（新資料源研究）；教學字串 `tab_edu.py` 提及 10Y-2Y／10Y-3M；**無**趨勢維度落盤 | **新補**為維度 |
| 3 | Leading Indicators | objective input（NDC 領先指標〔台灣〕）＋research dimension（景氣領先指標；美國／全球 CLI 不存在） | ✅ PROJECT_STATE §22.2／22.4、`VN1-MT-YIELD-CLI`、`VN1-MT-LEGACY-GAP` | 定位；⚠️ 同名陷阱見 §5 |
| 4 | PMI | objective input（既有 `ism_pmi` 燈＝顯示名「台灣 PMI」；美國 PMI 有 FRED NAPM 取數） | ⚠️ `VN1-MT-YIELD-CLI` 只寫「PMI 是否涵蓋待研究」 | **新補**為維度 |
| 5 | Inflation | objective input（既有 `us_core_cpi` 燈＝美國核心 CPI YoY） | ❌ 無趨勢維度落盤 | **新補**為維度 |
| 6 | Fed／monetary policy | research dimension／context overlay（FEDFUNDS 已有 fetcher） | ❌ 無趨勢維度落盤 | **新補**為維度 |
| 7 | Real Yield | research dimension（**資料源不存在**） | ⚠️ 僅 `NSR-TIPS`（新資料源研究） | **新補**＋Pending（`MKT-RB-REALYIELD`） |
| 8 | VIX | objective input（既有 `vix` 燈） | ❌ 無趨勢維度落盤 | **新補**為維度 |
| 9 | Credit Spread | objective input／research dimension（既有 HY OAS 取數僅在 `risk_radar`，**V-RADAR-1** 待修範圍） | ❌ 無趨勢維度落盤 | **新補**為維度＋Pending（`MKT-RB-CREDIT`） |
| 10 | USD | objective input（既有 `dxy` 燈＝美元指數） | ❌ 無趨勢維度落盤 | **新補**為維度 |
| 11 | Major Equity Markets | objective input／context overlay（既有 `^GSPC`／`^VIX`／`^TNX` 取數；其他指數見 §5） | ⚠️ Gate 檔 X6 國際市場原始資料 | 定位；**主要股市清單未定義**（`MKT-RB-MAJOREQ`） |

### 3.1 客戶 2026-10-22 原有國際研究框架（仍有效）

PROJECT_STATE §22.2「國際」四條：長天期公債殖利率×景氣領先指標且兼看**方向**；歷史泡沫案例只作研究比較、不成門檻；國際景氣／利率 → 企業投資／AI-CSP CAPEX → 台灣企業獲利／EPS → 台股。**與 A2 取聯集。**

---

## 4. 「不得自行」清單與 Pending／Decision Gate

### 4.1 不得自行（客戶 A1／A2；永久）

1. 核准 EPS source。
2. 核准 PE multiple（含「合理 PE」區間與其 rationale）。
3. 發明 growth assumption。
4. 新增 production formula。
5. 由 EPS×PE 直接產生買賣 action。
6. （國際趨勢）自行組成多頭／空頭公式、scoring model、Risk Cap rule、System Action、probability——**除非** repo 已有正式 validated deterministic contract（§5 如實列出現有哪些）。
7. 為 UI 順便 productionize 大盤 EPS×PE（Freeze §11 / 客戶 §43 原文）。
8. 把台股趨勢／國際趨勢與市場位階／指標危險度／Risk Cap 合併（DEC-071；PROJECT_STATE §22.3）。

### 4.2 Pending／Decision Gate（全部 **未核准**；本檔 ⛔ 替客戶決定；BACKLOG 逐項獨立列 `MKT-RB-*`，見 `docs/BACKLOG.md` §5.1.23）

| 項 | 狀態 | 備註 |
|---|---|---|
| EPS source（大盤 EPS／forward EPS） | **Pending**（repo 無大盤 EPS／forward EPS 資料源；FACT 見 Freeze §10「Forward EPS 資料源不存在」） | 新資料源＝Decision Gate（DEC-009／`PROJECT_RULES.md` §4 #3） |
| PE multiple 與 rationale | **Pending** | 示意值不得當 production（DEC-091(g)） |
| growth assumption | **Pending**（⛔ 不得發明） | |
| horizon | **Pending** | |
| update frequency | **Pending** | |
| formula | **Pending**（正式公式需 High Gate，`DEC092-EPSPE-HIGH-GATE`） | |
| 台股趨勢／國際趨勢正式定義 | **Pending**（`VN1-MT-TREND-DEF`） | 現況 UI 只顯示「尚未定義」 |
| 市場擁擠度、回撤／市場風險 的定義 | **Pending**（本檔新登） | |
| 殖利率曲線／Real Yield／Credit Spread／Fed／Major Equity 的資料口徑與是否納入 | **Pending**（本檔新登） | |

---

## 5. 現況盤點（repo 已有什麼；**單組、未窮舉**；FACT＝指令實查，INFERENCE＝讀法）

> 量測：2026-11-03，`origin/main`＝`e5f9a0d7`；方法＝對 `shared/`、`src/` 的 grep 與讀檔。cron 會推進 tip，引用前重查。

### 5.1 repo 已存在的正式 deterministic contract（FACT）

| 契約 | 位置 | 是什麼 | 為何**不是**台股／國際趨勢 |
|---|---|---|---|
| 市場位階 | `src/services/allocation_service.py::get_macro_regime`（仲裁 `shared/regime_arbiter.py::arbitrate_regime`） | 多空位階（SPEC.md §16.5） | DEC-071／PROJECT_STATE §22.3：四概念分離；UI 已加字樣「市場位階，不是台股趨勢」 |
| 指標危險度（16 燈） | `shared/macro_buckets.py::BUCKET_DANGER_SPECS`（FACT：含 `vix`、`us10y`、`dxy`、`us_core_cpi`、`ism_pmi`、`ndc_signal`、`m1b_m2_gap`、`margin`、`foreign_net`、`fut_net`、`adl`、`jingqi`、`bias_240` 等；另有 reference 桶 `usdtwd`、`taiex`） | 單指標危險度（不含方向）＋worst-of | 並列不合成（SPEC.md §16.5） |
| Risk Cap | `src/services/macro_state_locker.py::calculate_system_state`（`risk_cap.v2`） | 建議持股上限 | 與趨勢分離（DEC-071） |
| 行動規則 id 允許名單 | `shared/decision_digest_rules.py::RULE_ID_ALLOWLIST`（FACT：`risk_cap` ＋ `ACTION_CUT／ACTION_TAKE_PROFIT_FORCE／ACTION_TAKE_PROFIT_PARTIAL／ACTION_PAUSE_ADD／ACTION_ADD`） | 持股層既有分支原名 | 無任何台股／國際趨勢 rule id |
| 趨勢「定義狀態」 | `shared/decision_digest.py`（`tw_trend`／`intl_trend`＝`NOT_DEFINED`「尚未定義」；`valuation`＝`RESEARCH_ONLY`） | 只有定義狀態，沒有結論欄位 | 即：**台股趨勢／國際趨勢沒有任何已核准 contract** |

**結論（FACT＋INFERENCE）**：repo **沒有**任何已核准的「台股趨勢」「國際趨勢」validated deterministic contract（定義狀態為 `NOT_DEFINED`；`VN1-MT-TREND-DEF` 未裁示）。上表前三者是**相鄰但不同**的既有正式概念，**不得**被拿來冒充或組成趨勢結論。因此 A2 的「除非已有正式 contract」在國際趨勢維度上**目前不成立任何例外**＝**一律不得自行組合**。

### 5.2 各維度現有取數／呈現（FACT 為 grep 命中；對 UI 現況以 `src/ui/views/_market_blocks.py` 等讀檔）

| 維度 | 現有物件（檔案::符號） | 備註 |
|---|---|---|
| EPS×PE 大盤 | **無**（大盤層級不存在；EPS／本益比只在個股層） | `risk_radar.synthesize_dual_verdict` 的 `valuation_level` 無人產生；UI 圖 C「研究框架，未啟用」零數值 |
| 外資籌碼 | 燈 `foreign_net`、`fut_net`；`tw_macro.fetch_foreign_consecutive_days` | 連買舊 UI 有、新版未接（`UIX-MKT-FOREIGN-STREAK`） |
| 融資 | 燈 `margin`（門檻失準＋單位混用「資料疑義」） | 融券刻意不接（`DH-SHORT-UNIT`） |
| 市場擁擠度 | **無** | 定義與資料皆無 |
| 回撤／市場風險 | **無趨勢維度**；相鄰（INFERENCE）：`risk_control.py`／`health_calibration.py` 等含 drawdown／回撤／回檔字樣的個股／校準計算（grep 命中，未逐檔讀） | 不是大盤回撤定義；⛔ 未經客戶定義不得當原料 |
| 市場廣度 | 燈 `adl`（⚠️ ADL 是 ^TWII 推估卻標「市場廣度」，`VN1-MT-SSOT-ADL-LABEL`）、`jingqi` | 真實漲跌家數＝新資料源研究（`NSR-*`） |
| 長債殖利率 | 燈 `us10y`（FRED DGS10）；`^TNX` 取數（Yahoo，**不同源，禁混**） | |
| 殖利率曲線 | 10Y-3M 利差用於衰退機率 logit（`macro_core`／`signal_thresholds`）；2Y／利差系列不存在（`NSR-US2Y`／`NSR-YIELD-SPREADS`） | |
| Leading Indicators | `tw_macro.fetch_ndc_leading_index`、燈 `ndc_signal`；`FRED_CHN_OECD_CLI`（只中國）；美國／全球 CLI 不存在 | ⚠️ `src/data/macro/leading_indicators.py` 是**籌碼先行指標**，不是景氣領先指標（同名陷阱） |
| PMI | 燈 `ism_pmi`（台灣 PMI）；`FRED_NAPM`（美國 PMI 取數） | |
| Inflation | 燈 `us_core_cpi`（美國核心 CPI YoY） | |
| Fed／monetary policy | `macro_snapshot` 的 FEDFUNDS fetcher；`macro_helpers` 的 fed 利率變化敘述 | 無趨勢維度 |
| Real Yield | **無**（`NSR-TIPS` 研究候選） | |
| VIX | 燈 `vix`；`^VIX` 取數（`fetch_yf_close`） | |
| Credit Spread | `risk_radar.py` 取 FRED `BAMLH0A0HYM2`（HY OAS）；L2 內做 I/O＝**V-RADAR-1 待修** | 不得把 `risk_radar` 擴為趨勢來源 |
| USD | 燈 `dxy`；reference 桶 `usdtwd` | |
| Major Equity Markets | `^GSPC`（+60MA）取數；`macro_cache_reader` 提及 ^IXIC／^DJI／^SOX 的新聞歸檔字串 | 「主要股市」清單**未定義** |

### 5.3 UI 現況（FACT，讀檔）

Legacy New UI 市場頁（`src/ui/views/_market_blocks.py`）已有「圖A 🇹🇼 台股趨勢」「圖B 🌍 國際趨勢」，結論欄為「尚未定義」；圖 C 為大盤合理區間研究框架空槽（零數值）。**這是呈現層佔位，不是 contract。**New UI2 市場頁（`src/ui2/views/market.py`）依 DEC-123／124 只讀 fake／ViewModel。

---

## 6. 與 Freeze §43（§11）／DEC092-EPSPE-HIGH-GATE／VN1-MT-VALUATION 的關係

- **大盤 EPS×PE** 與 **單檔估值（Company EPS × Company valuation multiple）** 是**兩個 contract**，source／horizon／methodology／threshold 分開治理；⛔ 共用常數、⛔ 同一估值卡同時引用兩者而不標契約名（Freeze §11）。本檔**不改**此裁示，只把「大盤那一半」的**維度位置**放進台股趨勢 research baseline（A1 第 1 項）。
- 大盤模型**維持 Research Gate**：`DEC092-EPSPE-HIGH-GATE`（not started）仍是唯一的正式 Gate 列；`VN1-MT-VALUATION` 仍是研究候選列。本檔**不新增**重複的 EPS×PE Gate 列，Pending 細項改以 `MKT-RB-*` 子列分拆並 cross-reference 上述兩列。
- **A1 永久語意補強**：EPS×PE ≠ 完整市場趨勢判斷（PROJECT_STATE §22.2 與 `VN1-MT-VALUATION` 已有同義句；本檔升為客戶 2026-11-03 再確認的永久語意）。

## 7. A3 市場產品主軸（規格）

1. 正式市場趨勢**只有兩條主軸**：台股趨勢、國際趨勢（DEC-071 第 5 點的客戶再確認）。
2. Old UI（`app.py` 舊頁籤）／Legacy New UI（`src/ui/views/`、`src/ui/tabs/`）的功能、判讀邏輯、資料來源**只作** capability／logic／source reference（既有 `VN1-MT-LEGACY-GAP`、`NEWUI2_REUSE_MATRIX` 的語意）；⛔ 不得因其存在而在 New UI2 或任何新規格中新增「第三套」「第四套」市場主軸（例：獨立的「籌碼頁」「總經頁」「產業趨勢市場主軸」）。
3. ⚠️ **不破壞既有 IA**：本規則針對「市場趨勢」主軸。🎯 標的頁的產業趨勢（DEC-091／092 Q5「產業趨勢先研究」、`NEWUI_D25_RS1_*`）是**標的層**研究線，**不是**市場趨勢主軸；兩者的關係屬撰寫組讀法（INFERENCE），若客戶認為 A3 同時意指不得有「產業趨勢」這個主軸，請客戶裁示（見 DEC-125 疑點）。**Mapping（獨立複驗補，2026-11-03）**：`shared/decision_digest.py` 的 industry 區段（`NOT_DEFINED`）屬**標的層**產業趨勢；市場頁 Macro mini／sparkline 區塊屬**國際趨勢的 context overlay**，不構成第三主軸。此 mapping 併入 `MKT-RB-AXES-INDUSTRY-READING` 請客戶一併確認。
4. 四主導航（📊 市場／🎯 標的／💼 持股／👤 我的）不受影響。

## 8. A4 銜接

中性命名永久規則的規則本體在 `PROJECT_RULES.md` 第 28 節；本檔 §2／§3 的維度命名皆為中性產品語意（例：「台股大盤情境估值」「EPS × PE 情境矩陣」「市場估值區間」）。研究文件與 provenance 可保存原始作者／來源人物（本檔不重複列人名；來源見 PROJECT_STATE §22.2）。命名違反盤點見 `docs/BACKLOG.md` §5.1.23 `MKT-RB-NAMING-*`。

## 9. 未驗與限制（`PROJECT_RULES.md` 第 27 節 4）

1. §2／§3「舊落盤」欄與 §5 現況盤點為文件組**單組** grep／讀檔結論，**非窮舉**、未經第二組複驗。
2. 「台股趨勢／國際趨勢無任何已核准 contract」依據：`shared/decision_digest.py` 的 `NOT_DEFINED` 綁定、`VN1-MT-TREND-DEF` 未裁示、UI 結論欄「尚未定義」；若有 repo 外的客戶核准未落盤，以客戶為準並請補錄。
3. §1.1 三個定位詞的釋義、§7.3 的 IA 讀法為 INFERENCE，客戶可推翻。
4. 本檔未查證各 fetcher 的實際線上可用性（沙箱不連外）；只依程式碼存在判定「有取數」。
