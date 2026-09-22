# 五頁資料對照表 · 規格洞與待確認登記（IA v2 戰情室）

> **這是什麼**：`docs/v2/spec/DATA_MAP_ALL_PAGES.md` 逐頁盤點時，**查得出「規格沒寫」或「規格寫了但實作沒有」的每一項**，按頁分節登記在這裡。對照表本體（五欄）留在 `DATA_MAP_ALL_PAGES.md`，**洞只留這一份、⛔ 兩邊不各留一份**（那是第二真相源）。
> ⚠️ **本檔是登記，⛔ 不構成主動動工的授權**（`CLAUDE.md §-1`：沒有 user 指派／沒有實際 bug 觸發就不要碰；`§8.2.A.2` 前言同精神）。用途只有兩個：**(a) 動到該處時知道現況、(b) 給後續派工當起點清單。**
> **量測日 2026-09-22**・branch `ui-v2`。⛔ 全檔不寫行號（`CLAUDE.md §8.2.A.0` 規則 1）；程式碼引用一律**全路徑** `檔名::符號`，規格引用 `檔名 §章節名`；TTL 一律寫 `shared/ttls.py` 常數名；查不到一律「⚠️ 待確認」，⛔ 不猜、⛔ 不發明資料源／算式／中文標籤。
> **編號一律沿用原調查組的原樣，⛔ 未重編、⛔ 未補零統一** —— 重編會讓舊 commit／舊派工單的交叉引用全部指錯。
>
> **來歷前綴**（各頁獨立，⛔ 不跨頁沿用）：
> - **🚦 今天頁**：`G-*`＝DA 組（程式碼端）・`H-*`／`N-*`／`W-*`＝DB 組（規格端）・**無標＝兩組共同**。主編號 ①~⑲（洞）／ⓐ~ⓕ（待確認）。
> - **🔍 找標的頁**：`ED-*`＝ED 組（程式碼端）・`EE-GAP-*`／`ⓐ~ⓛ`＝EE 組（規格端）。

---

## 🚦 今天頁

> 本節自 `DATA_MAP_ALL_PAGES.md` §4 **整段搬入**（2026-09-22），內容一字未改，只把原本被 ≤50 行逼成連排的項目**展開成一項一行**。

### 規格未給（①~⑩）

- **①** 全 8 block 的 **TTL／頻率／fallback 三欄，頁級規格 0 命中**（總管複驗五頁 `UI_PAGE_*.md` 皆 0；`S2-ENG_SPEC §3.3` 自陳「**備援鏈跑到第幾層這個資訊在 repo 裡不存在**」）⇒ 本表該三欄**一律由程式碼端補**〔H-1/2/3〕
- **②** **交易日格無任何來源**：全 repo 無交易日曆實作、`CLAUDE.md §4.5` 明文不用 calendar lib，而 `S2-UI_SPEC §5.4 ★-05`／`§5.5` 反而**禁用**相關判詞 ⇒ 畫面要印「✅ 交易日」卻無合規來源〔G-3＝H-4〕
- **③** Sheet 綁定格**未指名 fetcher 符號**（`src/data/portfolio/gsheet_portfolio.py` 存在但規格未綁）〔H-5〕
- **④** `today.key_banner` 在 `docs/v2/spec/` **0 命中**（`collect_key_alerts`／`key_alerts_banner`／`threshold_scanned`）⇒ 規格目錄內無資料源、無編號〔H-6／N-1〕
- **⑤** `today.warroom` 來源／推導式／AI endpoint **全未給**〔G-4＝H-7／N-2〕
- **⑥** 16 盞**逐盞 endpoint 未對映**（`S1-1 §1.1` 只給 registry 總量）〔H-9〕
- **⑦** `statusbar`／`key_banner`／`actions`／`holdings` **四塊無徽章清單**〔G-6＝H-10〕
- **⑧** `coverage_pct`／`n_unclassified` **規格算式段未給**（只有 `DECISION_RULES §4` 一個範例值）〔H-8〕
- **⑨** 等權假設揭露句標「**必填**」卻**未給逐字文案**（現行那句是實作組草擬）〔G-7〕
- **⑩** `today.summary` 動能欄無資料源 —— **刻意的洞**（客戶「exposure 不是動能，不搬」），⛔ 不是漏寫〔H-12〕

### 規格 vs 實作落差（⑪~⑲）

- **⑪** `today.holdings` **整塊無實作**（`src/ui/` 0 命中，只活在契約常數 ＋ 原型 demo）〔G-1〕
- **⑫** 它也**不在 `INDICATOR_SPEC §3`**（表內「籌碼集中度」是**另一個量**，⛔ 不得混用）〔G-2＝N-3〕
- **⑬** 線框**七段 vs 實作五桶**：「A 市場狀態」「G 跨桶裁決」**無對應的燈**、「F 全球風險」只被三盞部分涵蓋〔G-5〕
- **⑭** **#2「載入中」規格有、實作未接**（`in_flight`／`st.spinner` 在 `src/ui/views/page_today.py` 0 命中）；**#9 partial** L3 未給分子分母 ⇒ 恆降級 #7〔G-8／G-9〕
- **⑮** `chrome.asof` **已撤回**（L3 契約 9 key 無 `as_of`，readiness 側車亦無逐指標時點）—— ⛔ **不是待補**，⛔ 不編一個時間出來〔G-10〕
- **⑯** `fetch_us10y_block` docstring 宣告 Tier 0＋Tier 1、**實測只有 Tier 0**；`fetch_vix_block` **無 `CLAUDE.md §2.1` 宣告的 CBOE 備援**〔G-11／G-12〕
- **⑰** **同一個 card key 兩種事實**：`verdict.exposure`／`key_banner.alerts` 在 `src/ui/tabs/tab_today.py::build_today_blocks` 是 `_staged_card`（未接線）、在 `src/ui/views/page_today.py` 是真取數〔G-13〕
- **⑱** `key_banner` **門檻層在今天頁主 CTA 射程外**（寫入點在舊「🌍 總經」分頁）⇒ 那半「重按不會好」〔G-14〕
- **⑲** **分母句子項數不一致**：規格寫**兩個**子項、production `Coverage.text()` 輸出**四個**〔H-11〕

### ⚠️ 待確認（ⓐ~ⓕ；查不到，⛔ 未猜）

- **ⓐ** 逐 block 的 TTL／fallback 順序在規格端查無（查過 `UI_PAGE_TODAY`／`S2-ENG_SPEC §4.1`／`S1-1 §4`／`S1-2` 各指標表）〔W-1／W-2〕
- **ⓑ** 線框示意值 `M1B-M2 +1.2` 的**算式歸屬**無規格綁定〔W-8，DB 專有〕
- **ⓒ** `today.verdict`「一句話結論」的**字串來源**（規格說「新寫的字串」、⛔ 不得由三卡合成，但未指定出處）〔DA 專有〕
- **ⓓ** `today.statusbar` **逐格「可否重試」**規格未逐格指定〔DB 專有〕
- **ⓔ** `today.key_banner`／`today.warroom` 的**計算式與門檻**規格端完全沒有〔W-3／W-5〕
- **ⓕ** `fetch_vix_block` 是否為**全站唯一一路** VIX 取數 —— DA **未窮舉**，⛔ 不宣稱〔DA 專有〕

---

## 🔍 找標的頁

> 素材：**ED 組（程式碼端）**與 **EE 組（規格端）**兩份獨立 draft（2026-09-22）。⚠️ **兩組皆為單組結論，⛔ 未互相複驗**；下列 `F-0` 三條是**總管另行親自查證過**的，其餘一律照原組標示打折。

### F-0. 🔴 三條總管親自複驗過的承重發現（⛔ 不是任一組的單組結論）

- **F-0-1｜`D-7` ≠ `D-07`，兩套同名不同義的編號本頁都用到。** `docs/v2/spec/S2-UI_SPEC.md` 的 **`D-7`** ＝「口徑揭露（X／Y／泡泡＝什麼、**面積不等於權重**）」；`docs/v2/spec/INDICATOR_SPEC.md` 的 **`D-07`** ＝「兩支分級函式的分界應真正一致」。⇒ **⛔ 逐字照抄出處的寫法，⛔ 不得「順手補零統一」** —— 補零就指到另一條規則。同理 `D-8`（`S2-UI_SPEC §9.3`，本頁 Deep Link 現況，已擱置）≠ `D-08`（`INDICATOR_SPEC`，PE 兩種「沒有」）。**規格端無人宣告這兩套並存**（＝ `EE-GAP-02`）。
- **F-0-2｜徽章編號三套並存且撞號，規格端沒有任何一處寫出對照表。** `docs/v2/spec/UI_COMPONENTS.md §2` 是 **#1~#10**（**#5＝這項還沒做／未接線・#8＝結構上不適用・#9＝資料不完整**）；`docs/v2/spec/S2-UI_SPEC.md` 是 **①~⑩**（**⑧＝未接線・⑨＝結構不適用**）；`docs/v2/spec/S1-4_STATE_MATRIX.md` 另有「呈現層 1~8」。⇒ **同一個數字 8，兩套裡意思相反**（⑧未接線 vs #8不適用），9 也撞。**⇒ 對照表欄位一律用 `UI_COMPONENTS §2` 的 `#n`**（與今天頁一致）；若出處寫的是 `①~⑩`，**逐字照抄並標明是哪一套，⛔ 不自行換算。** ⚠️ EE 組推了一張對映表（`⑥=#9`／`⑦=#4`／`⑧=#5`／`⑨=#8`／`⑩=#6`）—— **總管只驗了「撞號成立」這件事，⛔ 沒有驗那張對映本身**；引用時**必須標明「EE 單組推得、未經複驗」**，⛔ 不得當事實。（＝ `EE-GAP-01`）
- **F-0-3｜🔴 `D-08` 照規格寫法做不出來（總管讀 code 驗證，比 ED 的推論更確定）。** `src/data/stock/yield_pe_fetcher.py::fetch_pe_name_maps` 逐字 `if _pe != _pe or _pe <= 0: continue` —— **NaN（沒這個數字）與 ≤0（虧損）走同一個 `continue`**，下游只拿得到「key 不在 `pe_map` 裡」。**這個合流與上游送什麼無關**（⚠️ ED 組推的是「上游本來就不吐 ≤0 所以補旗標也沒用」，那一步仍是**未經 endpoint 實測的推論**；總管驗證的是**更上游的一條**：合流發生在本機，與上游送什麼無關）。⇒ 要分辨兩種「沒有」**需要第二個資訊源（EPS）**，現行兩支 endpoint 生不出來。**規格端佐證**：`docs/v2/spec/S1-2_METRIC_SSOT.md §1.3` 逐字「code 裡**沒有 EPS 這個輸入**，所以**無法區分「虧損」與「來源空值」**」。⚠️ **排程狀態⛔ 不得寫成「已排程」或「已核准」**：該檔屬資料層，受 `CLAUDE.md §-1.2` 資料層凍結拘束，**是否解凍＝等 UI 全部做完後由客戶再評估**。

### F-1. 規格洞 —— 程式碼端（ED 組，`ED-1`~`ED-10`）

- **`ED-1`** `find.statusbar` 整塊無實作 —— 且 `app.py` IA v2 分支**刻意**不渲染舊全域常駐條（註解逐字：那條讀的 `warroom_summary` 在舊頁籤不渲染時必然退回「⬜ 總經未評估」＝ `CLAUDE.md §1` 假訊息）⇒ **不是漏接，是設計上被移掉了、新的還沒做**
- **`ED-2`** `chrome.asof` 整塊無實作，且今天頁已判「已撤回」 ⇒ **跨頁不一致**（見 `ED-b`；⚠️ EE 組對此有相反意見，見 `F-5-2`）
- **`ED-3`** `find.pe_two_kinds` 整塊無實作 —— 客戶 2026-09-16 已裁示「UI 層先誠實顯示『本機分不出』」，**該誠實句尚未落地**
- **`ED-4`** 🆕 **`D-08` 的可行性前提未經查證** —— 規格 `UI_PAGE_FIND ④(c)` 假設 L1 能把 `PE<=0` 判成 `MISS_NOT_APPLICABLE`，但 `src/data/stock/yield_pe_fetcher.py::fetch_pe_name_maps` docstring 自陳**兩支 OpenAPI 現在根本不吐 ≤0**（TWSE 空字串／TPEX `'-'`，都已是 NaN）⇒ 只靠這兩支源補旗標補不出「不適用」，需第二個資訊源。⚠️ **ED 標為單組推論、未以實際 API 回應驗證**；總管另循一條更上游的路徑複驗同一結論，見 `F-0-3`
- **`ED-5`** `find.csv` 的「0 列停用態」在實作端**不可達** —— 0 列＝`UI_EMPTY` ⇒ `_render_screen_leaf` 早退，**按鈕整顆不畫**，⛔ 不是停用
- **`ED-6`** `find.wiring_disclosure` 的「常駐」不成立 —— L3 因子清單載不進來時整段被跳過 ⇒ **最需要它的時候它不在**（實作端已自陳、登記未修）
- **`ED-7`** `#2 loading` 全頁 0 處傳 `in_flight=`，但葉2 **已有** `st.spinner("批次抓取類股代表的日線收盤…")` ⇒ **spinner 有了、徽章沒接**（`UI_PAGE_FIND ② 處置 1`）
- **`ED-8`** `#9 partial` 的分母母體對不上 —— L3 `_cov_bits` 分母＝**存活池全體**，表上只有 `top_n` 列 ⇒ **兩個母體差一個數量級，⛔ 不得直接貼**（`UI_PAGE_FIND ② 處置 4` 已登記，ED 程式碼端複驗成立）
- **`ED-9`** 🆕 **第 2 頁的 `ACTION_*`／`LEAF_*` 不在 `shared/ia_nav.py`** —— 實測 `ACTION_LABELS` **只有 `update_today` 一項** ⇒ 按鈕名與指路句**跨頁缺一份 SSOT**；本頁以「檔內定義一次、兩邊讀同一個常數」折衷（檔內已列交接事項）
- **`ED-10`** 🆕 **本頁版面定義不在契約層** —— `docs/v2/prototype/gen_today_v2.py::FIND_LAYOUT` 住在產生器，**非** `src/ui_v2/`、**無** `tests/ui_v2/` 守護（產生器自己逐字揭露）⇒ **改壞了沒有任何測試會攔**

### F-2. 規格洞 —— 規格端（EE 組，`EE-GAP-01`~`EE-GAP-12`）

- **`EE-GAP-01`** **全 14 block 的徽章編號** —— 三套編號並存、規格端無人寫出對照表，且同一個阿拉伯數字在兩套裡意思相反（總管已複驗「撞號成立」，見 `F-0-2`）
- **`EE-GAP-02`** **`D-*` 編號** —— `D-7`/`D-07`、`D-8`/`D-08` 同名不同義且本頁兩套都用到，規格端無人宣告（總管已複驗，見 `F-0-1`）
- **`EE-GAP-03`** `find.screen_form` **因子清單來源** —— 規格端未指名 L3 符號／endpoint；只知道取不到時改畫 `src/ui/views/page_find.py::build_form_unavailable_card`。⚠️ **ED 程式碼端補得出來**：`src/services/fundamental_screener_service.py::SCREEN_ANGLE_LABELS`（見對照表）
- **`EE-GAP-04`** `find.screen_form` **「① 基本面優選　四項全過」的四項是什麼** —— `存活池`／`基本面優選`／`四項全過` 在 `docs/v2/spec/` **只命中 `UI_PAGE_FIND.md` 自己**；`S1-2_METRIC_SSOT` 無此節；`INDICATOR_SPEC §4` 的「基本面四維」綁的是另一個函式，**規格端未把它綁到本表單**，⛔ 不得逕自對映
- **`EE-GAP-05`** `find.pick_reason` **整塊** —— 線框 evidence 逐字「在 `stock_ia_v1.html` 與 `S1-3B §3.2` 九節裡都沒有被單獨畫出來」；「命中／未命中」的分界規格端未給
- **`EE-GAP-06`** `find.heatmap` **整塊資料源＋色階** —— `熱力圖`／`heatmap`／`類股代表` 在 `docs/v2/spec/` 幾乎 0 命中（唯二命中是 `UI_PAGE_FIND` 層表與 `S1-6_COMPLIANCE_COPY_GUIDE` 的**免責缺口清單**）；色階規則規格端不存在。⚠️ **ED 程式碼端補得出完整 L3→L1 鏈**（見對照表）—— **規格沒有 ≠ 程式沒有**
- **`EE-GAP-07`** `find.sector_flow` **「動能變化」（Y 軸）算式** —— `動能變化`／`四象限` 在 `docs/v2/spec/` **0 命中**，只有 caption 的白話描述。⚠️ **ED 程式碼端從 L0 `shared/sector_flow_thresholds.py` 補得出視窗常數**（見對照表）
- **`EE-GAP-08`** `find.scenario_quickpick` **整塊** —— 線框 evidence 逐字「這一塊在 code 與規格裡都不存在」；「低基期＝距一年低點近」的三個定義（哪個價／窗口／門檻 %）**客戶尚未給**（線框標 ★待拍板）
- **`EE-GAP-09`** **全 14 block 的「頻率／TTL／fallback」** —— `UI_PAGE_FIND.md` 全檔 7 個關鍵字（`TTL`／`fallback`／`頻率`／`endpoint`／`備援`／`cache`／`快取`）**全 0 命中**；`S2-ENG_SPEC §3.3` 自陳備援層數資訊 repo 內不存在。**與今天頁洞 ① 同型**
- **`EE-GAP-10`** `find.statusbar` **交易日格** —— 要印「✅ 交易日」卻**無合規來源**：`S1-4 §4.5`／`S2-UI_SPEC §5.5` 禁用需交易日曆才能判的字眼，而 `S1-4 §4.4(d)` 實測全 repo 無交易日曆。**與今天頁洞 ② 同源**
- **`EE-GAP-11`** `find.screen_form` **C-2 契約壞了要不要停用** —— **規格 vs 規格直接牴觸**：線框／`S1-3B §3.2.6` 要「CTA 停用」；`S1-4 §3.7.2 P2` 逐字「**在 P2 落地之前，『停用』做不到**…正確做法是**照常可按**」。**與今天頁 `today.actions` 是同一條牴觸**（見 `DATA_MAP_ALL_PAGES.md` 今天頁 §3），⛔ 本檔不裁決
- **`EE-GAP-12`** `find.screen_summary` **empty 的第 4 種原因** —— 線框自陳「有候選但因子缺太多排不出名次」目前與「0 檔」混在一起顯示；成因是涵蓋門檻 `SCREENER_MIN_FACTOR_COVERAGE_RATIO`，**規格端只登記、未給畫法**

### F-3. ⚠️ 待確認 —— 程式碼端（`ED-a`~`ED-f`；查不到，⛔ 未猜）

- **`ED-a`** **逐 block 的徽章清單**（`find.statusbar`／`chrome.asof`／`find.wiring_disclosure`／`find.csv`／`find.map_cta`／`find.map_scale_disclosure` 六塊該畫第幾號）—— 查過：`UI_PAGE_FIND ②` 是**以線框十鍵為軸**、不是以 block 為軸；`UI_COMPONENTS §2` 給的是 10 種徽章本身；那六塊在 `src/ui/views/page_find.py` **沒有 Card 物件** ⇒ 程式碼端沒有 `state=` 可讀。**兩端都查不到逐 block 對映**
- **`ED-b`** **`chrome.asof` 在本頁到底算不算「已撤回」** —— 查過：`src/ui_v2/page_today.py::WITHDRAWN_BLOCKS` 只涵蓋**今天頁**；`docs/v2/prototype/gen_today_v2.py::FIND_LAYOUT` 仍列本頁有它；`UI_PAGE_FIND ①` 也仍列它。**三處不一致，⛔ 不裁決**
- **`ED-c`** **`find.statusbar` 的 3 張卡（如果有的話）分別是什麼** —— 查過：今天頁是交易日／總經／Sheet 綁定三格；`UI_PAGE_FIND ①` 只寫「葉外 chrome」＋ cols `1/1/1`，**未列格數與格名**；程式碼端 0 命中
- **`ED-d`** **`find.screen_result` vs `find.screen_summary` 哪個是對的 key** —— 查過：`FIND_LAYOUT` 寫 `find.screen_summary`；`src/ui/views/page_find.py` 三處寫 `find.screen_result`。**⛔ 兩邊都沒有寫「另一個是舊名」**；線框 `docs/v2/wireframe/wf_page_find.js` 的 `states` 節點是否同時有兩個名字**未查證**
- **`ED-e`** **`fetch_stock_history_1y` 有沒有別處的快取** —— 查過：`src/data/stock/picker_fetcher.py` 實測 `grep cache_data` = **0**；上層 `run_rs_leader_scan` 是 `TTL_1HOUR`。**ED 未窮舉該函式的其他 caller**，⛔ 不宣稱「全站只有一層快取」
- **`ED-f`** **三大法人／美債／匯率是否真的全站只有一處取數實作** —— 查過：本輪**只追了本頁用到的路徑**；`CLAUDE.md §8.3` 自陳美債與匯率**從未掃過**。⛔ 不宣稱

### F-4. ⚠️ 待確認 —— 規格端（`ⓐ`~`ⓛ`；各附「查了哪裡」）

- **ⓐ** 逐 block 的 **TTL** —— 查過 `UI_PAGE_FIND.md`（`TTL` 0）／`S2-ENG_SPEC §4.1 TTL SSOT`（只給常數清單，未對映到 block）／`S1-1 §4`／`S1-2` 各指標表
- **ⓑ** 逐 block 的 **fallback 順序** —— 查過 `UI_PAGE_FIND.md`（`fallback`／`備援` 各 0）／`S2-ENG_SPEC §3.3`（自陳資訊不存在）／`S1-1 §1.1 來源總覽`
- **ⓒ** 逐 block 的 **取數頻率** —— 查過 `UI_PAGE_FIND.md`（`頻率` 0）；**唯一有的是 `find.sector_flow`**（`S1-1 §1.2 實體 I`：daily／cron `30 9 * * *` UTC ＝ TW 17:30）
- **ⓓ** `find.heatmap` 的 **endpoint／欄位／色階** —— 查過 `docs/v2/spec/*.md` 全檔 grep `熱力圖`／`heatmap`／`類股代表`／`漲跌熱力`／`色階`
- **ⓔ** `find.sector_flow` **Y 軸「動能變化」算式** —— 查過 `S1-2_METRIC_SSOT`（§2.11 是「法人集中度」＝另一個量）／`INDICATOR_SPEC §3`／grep `動能變化`／`四象限`
- **ⓕ** `find.scenario_quickpick` **「低基期＝距一年低點近」的定義** —— 線框 evidence 自陳「這三個都是客戶定義的一部分尚未給 → ★待拍板」；`docs/v2/spec/` grep `低基期`／`一年低點`
- **ⓖ** `find.screen_form` **「四項全過」的四項** —— 查過 `docs/v2/spec/` grep `存活池`／`基本面優選`／`四項全過`；`S1-2` 章節清單（無此節）
- **ⓗ** `find.pick_reason` **逐列因子命中明細拿不拿得到** —— 線框 evidence 自陳「本組**未查**」；規格端無
- **ⓘ** 各 block 的**徽章清單**（哪幾個徽章在這一塊會出現）—— `UI_PAGE_FIND ②` 只給**全頁**的十鍵覆蓋、**未逐 block 拆**；`UI_COMPONENTS §2` 只定義徽章本身。**與 `ED-a` 同一個洞的兩端**
- **ⓙ** `find.statusbar`／`chrome.asof`／`find.wiring_disclosure`／`find.pick_reason`／`find.map_cta`／`find.heatmap`／`find.sector_flow` 七塊的 **`INDICATOR_SPEC`／`DECISION_RULES` 編號** —— 查過 `INDICATOR_SPEC §3／§4／§5` 全表、`DECISION_RULES §1~§9` 全表：**對不到，⛔ 不湊**（同今天頁 `today.key_banner`／`today.warroom`，⛔ 不得拿語意相近的編號頂替）
- **ⓚ** `find.map_cta` 的「停用」可行性 —— `S1-4 §3.7.2 P2` 講的是 `src/ui/views/_ui_kit.py::single_submit_form`（form submit），**本鈕是 `st.button`**，該條是否適用規格端未講
- **ⓛ** `find.statusbar` **空頭濾網**的判定式 —— 線框 evidence 只講行為（失敗→濾網不套用），**未給算式**；`INDICATOR_SPEC §3`／`DECISION_RULES` 無此列

### F-5. 兩組不一致／交錯處（⛔ 兩邊並陳，未自行統一）

- **`F-5-1`｜「有幾個 block key 在程式碼裡命中」計數單位不同，⛔ 不是矛盾。** **ED 組**：「14 個裡**只有 3 個**真的出現在 `src/`」（`find.screen_form`／`find.heatmap`／`find.sector_flow`）。**總管原始 grep**：`chrome.asof` **2**／`find.screen_form` **1**／`find.heatmap` **2**／`find.sector_flow` **3**，其餘 10 個皆 **0** ⇒ 看起來是「**4 塊有命中**」。**兩者不衝突**：`chrome.asof` 那 2 處**不是本頁實作**，是 `src/ui_v2/page_today.py::WITHDRAWN_BLOCKS`（逐字「**已撤回、不是待補**」）。⇒ **本頁有實作的是 3 塊**，`chrome.asof` 的命中屬**今天頁的撤回登記**。
- **`F-5-2`｜`chrome.asof` 在本頁算不算「已撤回」，兩組方向相反。** **ED（程式碼端）**：今天頁已判「已撤回」，但 `FIND_LAYOUT` 仍把它列進本頁 14 塊 ⇒ **跨頁不一致，就地標明、⛔ 不裁決**（`ED-b`）。**EE（規格端）**：⛔ **不得把今天頁的「撤回」結論套到本頁** —— 今天頁撤回的理由是 L3 契約 9 key 無 `as_of`，而**本頁的來源是序列型資料、有 `date` 欄**（`S1-4 §4.4(a)`：`date` 欄／`DatetimeIndex` 是現行唯一可靠的歸屬日來源）。⇒ **兩邊都在檯面上，⛔ 本檔不裁決。**
- **`F-5-3`｜`find.wiring_disclosure` 的「常駐」。** **EE（規格端）**：線框 `S1-3B §3.2.7` 矩陣**十態全部寫「常駐」**，`idle` 原文「⛔ 不隨狀態消失」。**ED（程式碼端實測）**：**不成立** —— 該句長在 `_render_screen_form` 最後一行，而 L3 因子清單載不進來時 `_render_screen_leaf` **整支跳過**它 ⇒ **最需要它的時候它不在**（`ED-6`）。⇒ **規格要常駐、實作做不到，登記未修。**
- **`F-5-4`｜`find.heatmap`／`find.sector_flow` 的資料源。** **EE**：規格端 0 命中（`EE-GAP-06`／`EE-GAP-07`）。**ED**：程式碼端追得出完整 L3→L1 鏈與 L0 常數 SSOT。⇒ **「規格沒有」不等於「系統沒有」** —— 對照表該兩列的來源欄**由程式碼端補**（同今天頁洞 ① 的處置）。
- **`F-5-5`｜`find.csv` 按鈕字串兩份真相源。** **EE**：線框／`S1-3B` 寫「**⬇ 下載結果 CSV**」，production／線框 `states.live` 寫「**💾 下載選股結果 CSV**」；`UI_PAGE_FIND ⑥` 推薦取 production 那串、線框改齊，**⛔ 不得兩邊各留一份**。**ED**：程式碼端實測就是「💾 下載選股結果 CSV」。⇒ **待客戶拍板**，⛔ 本檔不裁決。
- **`F-5-6`｜`find.screen_summary` vs `find.screen_result`。** **ED**：實作端 Card key 是 `find.screen_result`（`src/ui/views/page_find.py` 三處），**不在 `FIND_LAYOUT` 的 14 個裡**；原型用 `find.screen_summary`。**總管已親自複驗此事實成立**（`Card(key="find.screen_result", label="選股結果")` 兩處）。**EE**：只走規格端，未觸及此事 ⇒ **不是兩組矛盾，是 EE 射程外**。哪個是對的 key 見 `ED-d`。

### F-6. 誠實揭露（`CLAUDE.md §-2` 規則 6）

- **ED／EE 兩組皆為單組結論，⛔ 未經第二組複驗。** 所有「0 命中／只有 3 個／規格端沒有／唯一一處」都是**單次 grep 的全稱句**，依 `CLAUDE.md §8.2.A.0` 規則 2（禁窮舉宣稱）**請據此打折**，⛔ 不得作為後續動作的前提。
- **ED（程式碼端）⛔ 未做 AST 掃描**（全部是 grep ＋ 逐行讀 code）、**⛔ 未實跑任何程式、⛔ 未打過任何 endpoint、⛔ 未開過畫面** —— 「畫面會顯示什麼」全是讀 code 推得。**EE（規格端）⛔ 完全沒有回 code 驗證任何一條** —— 寫的是**規格怎麼寫**，不是**程式怎麼跑**；凡引 `檔名::符號` 者一律是**規格文件自己轉述的**。
- ⚠️ **線框 `wf_page_find.js` 自陳兩層不可靠**：(a) `UI_PAGE_FIND` 檔尾逐字「查到的是『每個 block 的 `src` 字串是什麼』，**不是**『每個 `src` 指的那一行內容對不對』」，已知內容漂移**兩例**（`find.statusbar`／`find.screen_table`）；(b) 線框 `live`／`partial` 的數字（`274`／`50`／`12/89`／`31/274`／`2330 87.5 18.20`）**全部是規格示意值、非實測**，⛔ **不得寫進對照表當事實**。
- ⚠️ **兩組都沒讀完的大檔**：`S1-3B_FULL_DRAFT_SPEC`（3,157 行）／`S1-3_IA_WIREFRAME`（1,597 行，EE **完全沒讀**）／`S1-6_COMPLIANCE_COPY_GUIDE`（1,355 行）／`S2-PRD`（EE **完全沒讀**）／`S1-5_HOLDINGS_MODEL`／`S1-7_PERMISSIONS_PII`／`UI_TOKENS`／`UI_PRINCIPLES`／`docs/v2/stage1/*` ⇒ **`F-1`~`F-4` 的部分項目可能躺在那幾份裡，⛔ 不得逕自宣稱規格沒寫。**
- ⚠️ **EE 未驗的等式**：「線框 14 block ＝ `FIND_LAYOUT` 14 block」**EE 組未驗**（EE 依派工約束未開產生器）；EE 從線框解析到的 14 個 key 與派工單給的 14 個**逐字一致**。
- ⚠️ **`S1-6 §7.3` 逐字把「v2 五頁的 `page_find.py`／`page_inspect.py`」列為合規盲點**（乙組自陳「基本沒有逐段讀」），且「`st.dataframe` 儲存格內容」靜態掃描本來就掃不到 ⇒ **⛔ 不得假設本頁目前沒有違規文案。**
