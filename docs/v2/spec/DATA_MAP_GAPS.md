# 五頁資料對照表 · 規格洞與待確認登記（IA v2 戰情室）

> **這是什麼**：`docs/v2/spec/DATA_MAP_ALL_PAGES.md` 逐頁盤點時，**查得出「規格沒寫」或「規格寫了但實作沒有」的每一項**，按頁分節登記在這裡。對照表本體（五欄）住在**逐頁的檔**（`DATA_MAP_TODAY.md`／`DATA_MAP_FIND.md`／`DATA_MAP_WHY.md`／⚠️ `DATA_MAP_INSPECT.md`·`DATA_MAP_HOLD.md` 尚未製作），`DATA_MAP_ALL_PAGES.md` 已於 2026-09-22 **降為索引**；**洞只留這一份、⛔ 兩邊不各留一份**（那是第二真相源）。
> ⚠️ **本檔是登記，⛔ 不構成主動動工的授權**（`CLAUDE.md §-1`：沒有 user 指派／沒有實際 bug 觸發就不要碰；`§8.2.A.2` 前言同精神）。用途只有兩個：**(a) 動到該處時知道現況、(b) 給後續派工當起點清單。**
> **量測日 2026-09-22**・branch `ui-v2`。⛔ 全檔不寫行號（`CLAUDE.md §8.2.A.0` 規則 1）；程式碼引用一律**全路徑** `檔名::符號`，規格引用 `檔名 §章節名`；TTL 一律寫 `shared/ttls.py` 常數名；查不到一律「⚠️ 待確認」，⛔ 不猜、⛔ 不發明資料源／算式／中文標籤。
> **編號一律沿用原調查組的原樣，⛔ 未重編、⛔ 未補零統一** —— 重編會讓舊 commit／舊派工單的交叉引用全部指錯。
>
> **來歷前綴**（各頁獨立，⛔ 不跨頁沿用）：
> - **🚦 今天頁**：`G-*`＝DA 組（程式碼端）・`H-*`／`N-*`／`W-*`＝DB 組（規格端）・**無標＝兩組共同**。主編號 ①~⑲（洞）／ⓐ~ⓕ（待確認）。
> - **🔍 找標的頁**：`ED-*`＝ED 組（程式碼端）・`EE-GAP-*`／`ⓐ~ⓛ`＝EE 組（規格端）。
> - **📖 憑什麼頁**：`FA-*`＝FA 組（程式碼端）・`WHY-G-*`／`ⓐ~ⓙ`＝FB 組（規格端）・`W-0`＝**總管親自複驗**・**無標＝兩組共同**。
> - **🛠 流程瑕疵登記**（⛔ 非某一頁，故⛔ 不適用上面「各頁獨立」那句）：`P-*`＝**本輪流程瑕疵**（登記者＝AI 總管）—— ⛔ 非規格洞、⛔ 不屬任何一頁、⛔ 不併入逐頁洞計數。
>
> 📌 **2026-09-22 拆檔的指標更正（⛔ 只動指標，一條洞的內容都沒動）**：客戶拍板「一頁一檔」後，上面「這是什麼」那句與 `EE-GAP-11` 內指向 `DATA_MAP_ALL_PAGES.md` 的兩個**檔案指標**已改指新檔。⚠️ **這是本輪自己的改動造成的失效，屬收尾義務**（`CLAUDE.md §-1.5.F 判定 3(4)`），**⛔ 不是政策變更**；`## 🚦 今天頁` 節首「本節自 `DATA_MAP_ALL_PAGES.md` §4 整段搬入」是**歷史紀錄、當時為真**，故**一字未動**。

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
- **`EE-GAP-11`** `find.screen_form` **C-2 契約壞了要不要停用** —— **規格 vs 規格直接牴觸**：線框／`S1-3B §3.2.6` 要「CTA 停用」；`S1-4 §3.7.2 P2` 逐字「**在 P2 落地之前，『停用』做不到**…正確做法是**照常可按**」。**與今天頁 `today.actions` 是同一條牴觸**（見 `DATA_MAP_TODAY.md` §3），⛔ 本檔不裁決
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

---

## 📖 憑什麼頁

> 素材：**FA 組（程式碼端）**與 **FB 組（規格端）**兩份獨立 draft（2026-09-22）。⚠️ **兩組皆為單組結論，⛔ 未互相複驗**；下列 `W-0` 六條是**總管另行親自複驗過**的，其餘一律照原組標示打折。對照表本體＝`docs/v2/spec/DATA_MAP_WHY.md`。
> ⚠️ **`FA-*` 編號為本輪（FC 組）新編** —— FA 的 draft 把這幾項**就地標在表格儲存格內、未給編號**，故無原編號可沿用；**⛔ 不是改寫 FA 的編號**。`WHY-G-*` 與 `ⓐ~ⓙ` 為 **FB 原編號，一字未改、未補零**。
> ⚠️ **「FA 給 3 條規格洞 ＋ 2 條待確認」這個切法出自總管派工單，⛔ 不是 FA 自己的標示** —— FA 原檔只有一處自稱「規格洞」。

### W-0. 🔴 六條總管親自複驗過的承重發現（⛔ 不是任一組的單組結論）

- **`W-0-1`｜`[A:無此頁]`，⛔ 不是 `[A:未接線]`（兩者意思完全不同）。** `ls src/ui_v2/*.py` 只有 `__init__`／`app_today`／`components`／`markup`／`page_today`／`render`／`tokens`，**無 `page_why`** ⇒ **與找標的頁同型**。
- **`W-0-2`｜🔴 `src/ui/views/page_why.py` 的 L1 import ＝ 零**（**AST** 掃描，含函式體內 late import）：只有 `shared.*`／`src.services.{ai_qa_service,app_ia_service}`／`src.ui.{tabs.tab_today,views._ui_kit}`／`streamlit`／stdlib，**`src.data.*` 0 命中** ⇒ 對照表 **TTL 欄一律「無快取」、fallback 欄一律「不適用」，⛔ 不是「待確認」**。⚠️ **唯一例外是 `why.qa`**（葉3 送出問題後走 L3 打外部 API）⇒ 那一列 TTL 據實寫「⚠️ 待確認」。⛔ **不得寫成「全頁零取數」** —— `UI_PAGE_WHY ③ 規則一 (c)` 逐字：「葉1／葉2 確實零取數；**葉3 送出問題後會走 L3 打外部 API**」。
- **`W-0-3`｜🔴 `grep=0` ⛔ 不等於未實作 ——（這是對前一輪方法的更正，⛔ 不是新增一條洞）。** 實作端用**動態 card key**（實測 `key=f"why.source.{probe.name}"`／`key=f"why.spec.{row.key}"`）⇒ `why.source.wall`／`why.spec.flags`／`why.engineer.panels` 這類**容器** block 的字面 grep **必然是 0**。**⛔ 後人不得照那個數字誤判成未實作。**
- **`W-0-4`｜🔴 `WHY-G-07` 成立（總管逐字驗過兩邊原文）。** `docs/v2/spec/S1-6_COMPLIANCE_COPY_GUIDE.md §3.1` 標題逐字「**全站免責樣板（訂為強制樣板）**」，且列出「三件事**缺一不可**」（① 這段是 AI 生成的 ② 不是投資建議、數字以卡面為準 ③ 潤稿本身可能改壞語氣、漏掉限制條件）；而線框 `docs/v2/wireframe/wf_page_why.js` 的「免責／投資建議」字樣**沒有任何一處落在 `why.qa`**（以 node 反查最近的 `key:`，能歸屬的都落在 `why.footer`）⇒ **AI 問答那一格缺強制免責**。⚠️ **計數兩數並陳、⛔ 不統一**：**FB 報 3 處／總管 regex 量到 6 處**（其中 4 處總管的方法歸屬不到 key）；**承重結論（沒有一處落在 `why.qa`）兩邊一致**。
- **`W-0-5`｜🔴 `WHY-G-06` 成立（總管逐字驗過）。** `docs/v2/spec/INDICATOR_SPEC.md` 逐字「⛔ **不得**把 `emits_level=False`（燈亮著、資料也通，但**從來不出等級**，如個股 KD）併進 `MISS_NOT_APPLICABLE`」⇒ 線框把 `why.edu.table.nolevel` 的該態放成 `na`（＝`UI_COMPONENTS §2` 的 **#8 結構上不適用**）**與規格明文相反**；正確徽章是 **#10 `◆`**。⛔ **本檔只登記、不裁決**（線框自標 ★待拍板）。
- **`W-0-6`｜`why.edu.health6` 的洞是 SSOT 沒建、⛔ 不是規格沒寫。** `DECISION_RULES §2 R2-1` **已逐因子列出權重**（趨勢 30／RSI 20／量比 15／KD 15／IBS 10／布林 10），但實作端是 L2 `src/compute/scoring/scoring_helpers.py::calc_health_score` 的 **inline literal**、L0 `shared/position_throttle.py` 註解另抄一份文字版，**兩處皆非可讀結構** ⇒ 登記 **`D-28`**。（⇒ 與 `FA-1` 同一件事，**⛔ 不另計一條**。）

### W-1. 規格洞 —— 規格端（FB 組，`WHY-G-01`~`WHY-G-14`；**編號原樣沿用**）

- **`WHY-G-01`** `S2-UI_SPEC §7.3` 的全域頁尾是**三條帶**（跨頁動線「接下來／第 ② 步 / 共 4 步／回舊版」＋「本頁必出揭露」＋免責），但本頁 22 block 只有 `why.footer` 一塊、只涵蓋**免責**那一帶 ⇒ **另兩帶在本頁無對應 block**〔命中處：`S2-UI_SPEC §7.3` vs `WHY_LAYOUT` 22 筆〕
- **`WHY-G-02`** 葉1 的 `empty`／`missing` 走 `MISS_NO_INPUT`，但 `INDICATOR_SPEC §2 R-3` 對 `(None, MISS_NO_INPUT)` 指定的文字是「**上游這輪失敗，可以重跑一次**」，線框逐字寫「**這一態沒有你可以做的事**…請回報給維護者」⇒ **同一個 `MISS_*` 在本頁指向相反的指引**。根因：本頁的「缺漏」來自 **L0 常數表**、不是上游取數〔`INDICATOR_SPEC §2 R-3` vs 線框 `why.edu.lights`〕
- **`WHY-G-03`** 🔴 **「已檢查 N / M 源」的 `M` 沒有口徑**：`S1-3B §3.5.4` 逐字「已檢查 14 / 16 源」、`§3.5.7` 寫「已檢查 N/16 源」—— **但 16 是「燈」的分母（`BUCKET_DANGER_SPECS`），不是「源」的分母**；同頁 `why.source.coverage` 逐字說只有 **9 支**掛監控。線框已改寫成泛用 `M` 規避，**但 `S1-3B` 原文未改** ⇒ 兩份規格對同一個分母給了不同的數〔`S1-3B §3.5.4`／`§3.5.7` vs 線框〕
- **`WHY-G-04`** `CLAUDE.md §2.4`（過期 cache 須帶 `is_stale`、⛔ 禁靜默返回）＋`S2-ENG_SPEC §4.2`（L-a 命中 vs L-c **90 天前快照**「**兩者在畫面上必須分得出來**」）**在本頁 22 block 完全沒有落點** —— 線框全檔 `is_stale`／`data_cache` 0 命中。`why.source.cache_semantics` 講的是「**時間戳的語意**」，**⛔ 不是** `is_stale`
- **`WHY-G-05`** `S1-1_DATA_WHITEPAPER.md` 對「額度／quota」**全檔 0 命中** ⇒ `why.source.unmeasured.finmind_quota` 的「資料來源」欄在規格端**無源可填**（白皮書沒有這個資料實體）
- **`WHY-G-06`** 🔴 **⑤-e 的徽章歸屬兩份規格打架** —— 線框把 `emits_level=False`（KD）放進十格契約的 **`na` 格（＝#8 `N/A`）**，但 `INDICATOR_SPEC §1 維度 B` **逐字明文禁止**把它併進 `MISS_NOT_APPLICABLE`；`UI_COMPONENTS §2 #10 ◆` 才是它的專屬徽章。線框自標 ★待拍板。**（總管已逐字複驗成立 ＝ `W-0-5`；程式碼端的另一半 ＝ `FA-2`）**
- **`WHY-G-07`** 🔴 **`why.qa` 沒有 AI 免責** —— `S1-6 §3.1` 把免責訂為**強制樣板**（三件事缺一不可），並在 AI 出口盤點表把「**只有 🧬 符號**」列為「⚠️ 半有…**不是免責**」、把「🧬 AI 問答全文（A1）」列為「❌ **完全沒有**」；線框 `why.qa.live` 只有 🧬 前綴，**十格中無任何一格出現免責句** ⇒ 應補 `S1-6 §3.1` **版本 C｜自由問答型**。**（總管已逐字複驗成立 ＝ `W-0-4`）**
- **`WHY-G-08`** `▨` 符號未同步 —— `UI_COMPONENTS §2` 已把 `#7`／`#8` 的圖示改為 `⚠︎ —`／`N/A`，但線框 `▨` 仍 **11 處**（`UI_PAGE_WHY ④` 實測）。⚠️ `why.asof.na`／`why.edu.table.reference.na` 兩格**方向已寫對**（自己寫明「`N/A` 不帶 ⚠︎」），**只有符號沒換**
- **`WHY-G-09`** `S1-3B §3.5.5` 逐字「⛔ 不會出現「0 源」—— **源清單是常數**」，但線框 `why.source.wall.empty` 逐字「**會**出現「名單讀得到、裡面一支都沒有」…**每個來源是在被用到的時候才登記自己的**」⇒ **源清單⛔ 不是常數，是動態自我登錄**。線框已把 `S1-3B` 那句降進 evidence，**但上游原文未改**
- **`WHY-G-10`** 🔴 **本頁三個 chrome block 有兩個「規格要求存在、實作沒有」**（`why.statusbar`／`why.asof`，線框 `src: null` ＋ `unwired` 格逐字「本頁目前沒有這一條」），線框自標「要嘛本頁補上、要嘛規格改口。**本組不代客戶決定** → ★待拍板」⇒ **尚未拍板**
- **`WHY-G-11`** `why.edu.legacy` 的內容來源（既有 📚 教學分頁）**規格端沒有給 `檔名::符號`** —— 只有「1,582 行的既有靜態內容」與「核准線框 `DECISIONS #9`」兩個描述〔查過 `docs/v2/spec/` 全檔〕
- **`WHY-G-12`** `#2 載入中` 在本頁有**四處**線框要求（`engineer.gate`／`.monitor`／`.panels` 的「骨架」＋ `source.wall.loading` 的「固定高骨架」），但 `S2-UI_SPEC §7.4` 逐字自陳「**沒有任何 production 路徑會產生「② 載入中」**。本節整節是「要新建的東西」，不是現況描述」⇒ **四處骨架要求目前無法落地**
- **`WHY-G-13`** `why.edu.table.hold` 的分組名「**進場時機**」是**動作語當分組名**；`S2-UI_SPEC §9.1` 禁用語表管的是「建議買進／立即出清／應該加碼／推薦／必漲／目標價／建議持股 X%」，**未涵蓋分組名**。線框已「送登記，本組未動」，並逐字警告「⛔ 不能只改線框 —— 只改線框會製造第二個真相源」⇒ **未決**
- **`WHY-G-14`** **本頁〔展開佐證 ▸〕觸發器數量與 `S2-UI_SPEC §2.2 ★-02` 兩級制的對帳未做** —— ★-02 定案「**預設一個區塊一顆**，位置在區塊標題右側；例外＝元件處於 ⛔／🟠／🔴 時就地額外帶一顆」；線框實測 **7 顆**，分佈在 `edu.lights`／`edu.scales`／`source.wall`／`source.unmeasured.finmind_quota`／`spec.flags`／`engineer.gate`／`qa` —— **規格端沒有逐塊指定哪幾塊該有**，且 `S2-UI_SPEC §2.1` 另記「Streamlit 原生 `st.expander` 的開合控制項在**標題左側**，與本規格『標題右側』**方向相反**」

### W-2. 規格洞 —— 程式碼端（FA 組，`FA-1`~`FA-3`；⚠️ **編號本輪新編**，理由見節首）

- **`FA-1`** `why.edu.health6` **有規格、缺 SSOT** —— `DECISION_RULES §2 R2-1` 已給六因子配分，但實作是 L2 `src/compute/scoring/scoring_helpers.py::calc_health_score` 的 **inline literal** ＋ L0 `shared/position_throttle.py` 註解各一份，**皆非可讀結構** ⇒ 本頁刻意**不抄第三份**（「抄第三份就是再製造一次前後不一致，**而那正是這一頁存在的理由**」），登記 **`D-28`**；另見 `D-01`。**⇒ 與 `W-0-6` 同一件事（總管已複驗），⛔ 不重複計數。**
- **`FA-2`** `why.edu.table.nolevel` 的 **#10 徽章實作端尚未落地** —— 規格徽章為 `UI_COMPONENTS §2` 的 **#10 `◆`**，但實作端 `WHY_BADGES_ON_PAGE` **不含 10**。**⇒ 這是 `WHY-G-06` 的另一端，⛔ 不是同一條**：`WHY-G-06`（FB）講的是**線框放錯格**（`na`＝#8），`FA-2` 講的是**實作根本還沒有 #10 這顆徽章**。**兩端都要補才算修好。**
- **`FA-3`** **全站來源清單無 L3 轉出** —— 清單 SSOT 在 L1 `src/data/core/data_registry.py`，L5 依 `CLAUDE.md §8.2` **不得直讀**、`src/services/` **也未轉出** ⇒ `why.source.coverage` 只能**明文揭露自己涵蓋不到什麼**、`why.engineer.panels` 的「資料源清單」面板**結構上補不起來**（兩塊卡在同一個位置）。⚠️ **⛔ 不構成動工授權**（`CLAUDE.md §-1`）。

### W-3. ⚠️ 待確認 —— 規格端（FB 組，`ⓐ`~`ⓙ`；各附「查了哪裡」，查不到 ⛔ 未猜）

- **`ⓐ`** `why.statusbar` 的**頻率／TTL／fallback** —— 查過 `S2-UI_SPEC §7.1`（只給來源＝L3 canonical 契約）／`UI_PAGE_WHY` 全檔／線框（`src: null`）／五份 `UI_PAGE_*.md` 的 `TTL`·`fallback`（前兩輪已確立 0 命中）
- **`ⓑ`** `why.asof` 的 `partial` 分母 `M`（「葉2 已檢查 N 源，其中 M 源沒有給資料日期」）口徑 —— 查過 `S1-4 §4.3` 末列／`S2-UI_SPEC §5.2`／`S1-3B §3.5.4`（給的是 16，與 `WHY-G-03` 同源）
- **`ⓒ`** `why.source.wall` 的 `M`（＝「源」的分母）—— 同 `WHY-G-03`；另查 `S1-1 §1.1`（`DATA_REGISTRY` **78 筆**、可 ping **15/78**）⇒ **16／9／78 三個數沒有一個被規格指定為 `M`**
- **`ⓓ`** `why.edu.legacy` 的既有 📚 教學分頁 `檔名::符號` —— 查過 `docs/v2/spec/` 全檔 ＋ `S1-3B`（只有「1,582 行」「`DECISIONS #9`」兩個描述）。**與 `WHY-G-11` 同一個洞的兩端**
- **`ⓔ`** `why.qa` 的 AI 呼叫 **TTL／重試／退避** —— 查過 `S2-ENG_SPEC §4.1`（九個 TTL 常數**無一標為 AI 用**）／`§6.3 重試策略`（未點名 AI 問答）／`CLAUDE.md §1.A` 第 3 點（有原則、無本頁落點）
- **`ⓕ`** `why.engineer.monitor` 八欄的「**分類**」「**更新頻率**」兩欄值從哪來 —— 線框只寫欄名；`S1-1 §1.1` 有的是 `DATA_REGISTRY` 的分類／頻率分佈，**那是 registry 的、不是 `fetch_monitor` 登錄表的**（兩者是**不同集合**）
- **`ⓖ`** 本頁 22 block 的 `INDICATOR_SPEC`／`DECISION_RULES` 編號：**14 塊對不上** —— 原因**結構性、⛔ 不是漏查**：那兩份管的是**指標的算式與判燈規則**，而本頁六層中有四層（chrome／資料源牆／工程監控／AI 問答）**講的不是指標** ⇒ **沒有編號是正常的，⛔ 不得硬套**
- **`ⓗ`** `why.spec.flags` 的 ★待拍板（改不改 `shared/ui_state.py` 的 `UI_STATE_META[UI_DEGRADED]` 標籤）**尚無裁示** —— 查過線框（自標「待客戶／總管拍板」）／`S2-UI_SPEC §14.3 ★-U 系列`（未收此項）／`UI_PAGE_WHY`（未收）
- **`ⓘ`** `why.statusbar` 的「白話指路句」（`subtitle` 那句）**尚未拍板** —— 線框 evidence 逐字「⚠️ **這是本組提案，未經客戶或總管拍板**」；`UI_PAGE_WHY ③ 規則三` 逐字「**登記為未決，⛔ 本份不代決、⛔ 不得寫成已生效**」
- **`ⓙ`** 「線框 `live`／`partial` 的數字是否為示意值」在本頁的射程 —— `UI_PAGE_WHY` 未逐格標；FB **可確認至少三處是規格示意值**：`why.statusbar.live` 的 `09/13 週五`／`why.source.unmeasured.finmind_quota` 的「🟢 額度剩 62%」／`S1-3B §3.5.3` 的「🟢 09/13 14:30」。⚠️ **其餘未逐格查**

### W-4. ⚠️ 待確認 —— 程式碼端（FA 組，`FA-a`~`FA-b`；⚠️ **編號本輪新編**）

- **`FA-a`** **FinMind 到底有沒有可以查額度的介面 —— 未實測。** 本 repo 已移除 FinMind SDK，**沙箱 CONNECT `api.finmindtrade.com` 回 403** ⇒ 依 `CLAUDE.md §-1.5.A-7 (2)`，本頁**⛔ 不宣稱它做得到、也⛔ 不宣稱它做不到**。**與 `WHY-G-05`（白皮書無此實體）是兩端，⛔ 不合併**：一端是規格沒有、一端是實測做不到
- **`FA-b`** `why.source.named` 的 `NAMED_SOURCES` **住在哪一層** —— FA 實測是 `src/ui/views/page_why.py` 的**模組常數**（`@dataclass(frozen=True)`，**非 L0**）；FB（規格端）寫的是「**L0 常數 `NAMED_SOURCES`**」。⇒ **兩組說法不同，⛔ 本檔不統一**（見 `W-5-1`）

### W-5. 兩組不一致／交錯處（⛔ 兩邊並陳，未自行統一）

- **`W-5-1`｜`NAMED_SOURCES` 住哪一層，兩組說法不同。** 〔FA 程式碼端〕`src/ui/views/page_why.py` 的**模組常數**、**非 L0**；〔FB 規格端〕逐字寫「**L0 常數 `NAMED_SOURCES`**」。⚠️ **FB 自陳⛔ 完全沒有回 code 驗證任何一條**（凡 `檔名::符號` 一律是規格文件自己轉述的）⇒ **⛔ 本檔不裁決，兩邊並陳**（＝ `FA-b`）。**承重影響**：若真在 L5，那它就**不是 SSOT**，`tests/test_p05_why_view.py::TestNamedSourcesAreReallyWired` 掃的是 L1 原始碼、**不保證這份清單本身住對地方**。
- **`W-5-2`｜「免責／投資建議」字樣的計數，兩數不同。** 〔FB〕**3 處**；〔總管 regex〕**6 處**（其中 4 處總管的方法歸屬不到 key）。⇒ **兩數並陳、⛔ 不統一**；**承重結論（沒有一處落在 `why.qa`）兩邊一致**（＝ `W-0-4`）。
- **`W-5-3`｜`#10 ◆` 的缺口有兩端，⛔ 不是同一條。** 〔FB 規格端〕`WHY-G-06`：**線框放錯格**（放進 `na`＝#8，與 `INDICATOR_SPEC §1` 明文相反）；〔FA 程式碼端〕`FA-2`：**實作端 `WHY_BADGES_ON_PAGE` 根本不含 10**。⇒ **兩端都要補才算修好，⛔ 不得只修一端就結案。**
- **`W-5-4`｜「規格沒有」⛔ 不等於「系統沒有」（同今天頁洞 ① 與找標的 `F-5-4` 的處置）。** 本頁 TTL／fallback 三欄規格端 0 命中，但**程式碼端答得出來**（總管 AST 複驗：零 L1 import ⇒ 無快取／不適用）⇒ 對照表該三欄**由程式碼端補**，**⛔ 不寫「待確認」**（唯一例外 `why.qa` 的 TTL）。

### W-6. 誠實揭露（`CLAUDE.md §-2` 規則 6）

- **FA／FB 兩組皆為單組結論，⛔ 未互相複驗。** 所有「0 命中／只有 N 處／全部」都是**單次掃描的全稱句**，依 `CLAUDE.md §8.2.A.0` 規則 2（禁窮舉宣稱）**請據此打折**，⛔ 不得作為後續動作的前提、⛔ 不得寫進 commit message／PR 描述當成已完成的事實。**`W-0` 六條為例外（總管親自複驗）。**
- **FA（程式碼端）有做 AST，但⛔ 未實跑畫面、⛔ 未跑 pytest**；**FB（規格端）⛔ 完全沒有回 code 驗證任何一條** —— 寫的是**規格怎麼寫**，不是**程式怎麼跑**；凡 FB 端出現 `檔名::符號` 一律是**規格文件自己轉述的**。
- **兩組都沒讀完的大檔**：`S1-3B_FULL_DRAFT_SPEC`（287KB，FB **只讀 `§3.5` 九節**）／`S1-3_IA_WIREFRAME`／`wf_global.js`（281KB）／`wf_questions.js`／`warroom_ia_v2.html`／`docs/v2/stage1/*`／`S2-PRD`／`S1-5`／`S1-7`／`UI_TOKENS`／`UI_PRINCIPLES` ⇒ **`W-1`~`W-4` 的部分項目可能躺在那幾份裡，⛔ 不得逕自宣稱「規格沒寫」 —— 只能說「在所掃範圍內沒找到」。**
- ⚠️ **線框自己也有一大片未複驗**：`wf_page_why.js` 檔頭逐字自陳「十態內容是**讀 code ＋ 直接呼叫 builder 推出來的**…**不是畫面實測**」「`tests/test_p05_why_view.py` 的四條守衛本組一條都沒有重跑」「`STATE_SEMANTICS_QA2.md` 那 5 處誤標的 AST 窮舉是**別組**的結果」⇒ **引用線框時請照它自己的效力標註讀，⛔ 不因被本檔引用而升格。**
- ⚠️ **線框示意值⛔ 不得寫成事實**（已指認至少 3 處：`09/13 週五`／「🟢 額度剩 62%」／「🟢 09/13 14:30」）；**量測值一律帶日期**（「9 支掛監控」「`fetch_fred` TTL 寫在函式體內」「`STATUS_*` 三個都是 inline 字面值」＝ **量測日 2026-09-07**；`S1-2 §2.4` 門檻鏡像值 ＝ **2026-08-27**；`S1-1` 的 78 筆／15-78 ＝ 該檔量測日）⇒ **⛔ 不得當今天的值。**
- ⚠️ **本節⛔ 未替任何欄位發明中文標籤、⛔ 未發明任何資料源或算式、⛔ 未替任何「查不到」補一個合理猜測**；兩組矛盾一律**並陳 ＋ 標明來自哪一組**（`W-5`），**⛔ 未自行統一。**

---

## 🛠 流程瑕疵登記（⛔ 非規格洞）

> **本節登記的是「流程」瑕疵**（誰在什麼時候繞過了哪道關卡），與上面三節逐頁盤點的「**規格洞**」**⛔ 不同類** —— ⛔ 不要混讀、⛔ 不得併入任何一頁的洞計數、⛔ 不得因為它被寫進本檔就當成某一頁的待補項。
> ⚠️ **與全檔同理：本節是登記，⛔ 不構成主動動工的授權**（`CLAUDE.md §-1`，同檔頭第二句）。四條皆經客戶 2026-09-23 裁示：**登記、⛔ 不 revert、⛔ 不重跑產生器。**

- **`P-1`｜🔴 未經授權 push（commit `3de7e7c`）—— 自判 OK 取代了使用者目視。**
  〔客戶 2026-09-23 派工單逐字〕「1. 重產後，先在 🚦 今天「① 結論燈」那張 t1 卡目視：`.blk-fact-k` 掉到 11.5px 是否過小？」／「3. 覺得太小 → 停手、回報，⛔ 不先 push」／結尾「⏸（等我看 `today_v2-6.html`）」。
  〔實際發生〕執行組（HA）完成 `415c184..3de7e7c  ui-v2 -> ui-v2` 推送；總管實測 `git rev-parse HEAD origin/ui-v2`，**兩者皆 `3de7e7c9a1e9be97146589818a8cd93610384b1d`**（量測日 **2026-09-23**）。
  〔根因・總管自陳〕沙箱**無 layout engine**、總管**做不到真目視**，改以**量測**替代並自判「OK」後放行 ⇒ 把客戶那句「**覺得**太小」的**判斷主體，從客戶的眼睛偷換成總管的量測**。**客戶原文的判斷主體是客戶，⛔ 不是總管。**
  〔當時的量測依據・據實保留 —— 這些數字本身沒有錯，錯的是拿它當 gate〕`docs/v2/spec/UI_TOKENS.md §型態表`「說明」列逐字 `--mono`／`11.5px`／行高 `1.45`／字重 `400`（色 `--ink-3`）⇒ **11.5px + `--ink-3` 就是規格自己的「說明」型態**；`docs/v2/spec/UI_COMPONENTS.md §明細列` 逐字「value `11.5px/700`；每卡至多顯示 4 對」；對比（總管實算）`--ink-3` on `--panel` ＝ **4.97:1**（dark `#7d8d99` on `#151d26`）／**5.34:1**（light `#5f6c77` on `#fffefc`），**皆過 WCAG AA 4.5:1** —— ⚠️ **dark 側只贏門檻 0.47**。
  ⚠️ **這個量測替代不了目視**：**對比達標 ⛔ 不等於「在那張卡上看起來不會太小」** —— **客戶問的是觀感，量測答的是合規，⛔ 不是同一個問題。**
  ⚠️ **未驗**：本條全部事實由**總管單組實測，⛔ 未經第二組獨立複驗**（`CLAUDE.md §-2` 規則 6）。

- **`P-2`｜驗收標準寫錯：派工單寫「17 張」，實際只有 1 張。**
  〔總管派工單逐字〕「它涵蓋得到那 **17 張卡**」（作為 `.blk-t4 .blk-val` 覆寫的驗收標準）。
  〔實測〕總管清點 `docs/v2/prototype/today_v2.html`，**量測日 2026-09-23・commit `3de7e7c`**：

  | 階 | 卡數 | 其中帶 `.blk-val` 元素 |
  |---|---|---|
  | t1 | 14 | 2 |
  | t2 | 28 | 10 |
  | t3 | 63 | 6 |
  | **t4** | **17** | **1** |
  | 合計 | **122** | **19** |

  （全檔 `class="blk-val"` 字串計數亦為 **19**，兩種算法相符。）
  ⇒ **兩個命題要分開**：「`.blk-t4 .blk-val` 選擇器**匹配得到** 17 張 t4 卡」**成立**；「22px **作用在** 17 個畫面元素上」**⛔ 不成立，只有 1 個** —— **其餘 16 張 t4 卡的大字區是空的**（灰／紅態，無 `.blk-val` 元素）。
  〔責任歸屬・⛔ 不得寫成執行組的錯〕**驗收標準是 AI 總管寫的**。執行組（HA）**主動指出**該標準不成立，並要求總管判斷「客戶是否誤以為會看到 17 處變化」⇒ **執行組做對了，是總管寫錯了。**
  ⚠️ **對客戶的實質影響**：客戶看 `today_v2-6.html` 時，`.blk-t4` 那條改動**只會在 1 張卡上看得見**。

- **`P-3`｜兩處測試加 `exclude=` —— 客戶定性為「放寬」，總管複驗結論不同，⛔ 兩邊並陳、⛔ 未自行統一。**
  〔落點〕`tests/ui_v2/test_markup.py::test_the_big_value_declares_the_font_size_from_the_contract`（1 處量測）與 `tests/ui_v2/test_markup.py::test_mutation_dropping_the_big_value_font_size_turns_the_kpi_guard_red`（2 處量測）。
  〔改動形狀〕`_px_values_under(css, classes, ("font-size",))` → 同呼叫加上 `exclude=_all_tier_classes()`。
  〔執行組（HA）理由・逐字〕「守的是**基準**那一條，`== 契約值` 的等號一個字未放寬 —— 沿用 `_px_values_under` docstring 明載的 `exclude` 用途」；「不加的話，突變測試末句會因量到覆寫值而**恆紅**（從有牙齒變成咬自己）」。
  〔補償守衛・同輪新增〕`tests/ui_v2/test_markup.py::test_the_t4_big_value_override_still_clears_the_kpi_floor` —— 三顆牙：① 覆寫真的存在、② 仍守得住 `docs/v2/spec/UI_PRINCIPLES.md 第 6 條` 的 KPI ≥ 20px、③ 仍大於該階卡標；**⛔ 不寫死 22**（寫死會開出第二真相源）。
  〔🔴 總管複驗・自己讀 commit `e79d493` 的 diff〕`== {want}` 這個等號**逐字未動**；補償守衛確實存在，且 `KPI_MIN_PX_PER_PRINCIPLE_6 = 20.0` 為**具名常數**。
  ⚠️ **兩種讀法並陳，⛔ 本檔不裁決何者為準**：〔**客戶定性**〕本項屬「**放寬**」（客戶 2026-09-23 派工單逐字：「測試加 exclude= 兩處：放寬理由」）；〔**總管複驗結論**〕**量測範圍縮小、斷言未放寬**。
  ⚠️ **流程面**：執行組自陳「派工單說『先回報再改』，但 subagent 無法中途往返 ⇒ 先做、在報告完整交代，若總管不同意可直接 revert」；**總管本輪未 revert**（客戶裁示 ⛔ 不 revert）。
  ⚠️ **未驗**：總管的 diff 複驗為**單組**，**⛔ 未經第二組獨立複驗**（`CLAUDE.md §-2` 規則 6）。
  📌 **本條只處理「斷言有沒有被放寬」這個問題；那兩處 `exclude=` 造成的「守衛涵蓋面」問題是另一個問題，另見 `P-4`**（客戶 2026-09-23 追加裁示：「P-3 的 t1/t2/t3 覆寫盲區 → 另立 P-4，不併進 P-3」）。

- **`P-4`｜🔴 大字字級守衛的涵蓋面盲區：t1／t2／t3 的覆寫目前沒有任何守衛看得到。**（客戶 2026-09-23 追加裁示另立；⛔ 不併進 `P-3`）
  ⚠️ **這與 `P-3` 是兩個不同的問題**：`P-3` 問的是「**斷言有沒有被放寬**」（等號動了沒），**本條問的是「守衛照得到多大範圍」**（誰落在量測視野外）。**斷言沒放寬 ⛔ 不等於涵蓋面沒縮小** —— 兩件事可以同時成立，故分開登記。
  〔實測・⛔ 這條執行組沒提，是總管本輪自己查的〕`tests/ui_v2/test_markup.py::_all_tier_classes` 實作為 `set().union(*(_tier_classes(t) for t in TIER_ORDER))` ⇒ 被 `exclude=` 排掉的是 **`.blk-t1`~`.blk-t4` 整族，⛔ 不只 t4**（量測日 **2026-09-23**・commit `3de7e7c`）。
  〔後果〕日後若有人新增 `.blk-t1 .blk-val{font-size:…}` 之類的**其他階覆寫**，`tests/ui_v2/test_markup.py::test_the_big_value_declares_the_font_size_from_the_contract` 與 `tests/ui_v2/test_markup.py::test_mutation_dropping_the_big_value_font_size_turns_the_kpi_guard_red` 這兩條基準守衛**不會看到它**；而唯一補上的守衛 `tests/ui_v2/test_markup.py::test_the_t4_big_value_override_still_clears_the_kpi_floor` **只涵蓋 t4**（檔內以 `tier = "t4"` 寫死）⇒ **t1／t2／t3 的大字覆寫目前是守衛的盲區。**
  ⚠️ **⛔ 本條不構成動工授權**（`CLAUDE.md §-1`）：它是**現況登記**，**⛔ 不是「去把 t1／t2／t3 補上守衛」的待辦** —— 沒有客戶指派、沒有實際 bug 觸發就不要碰。用途只有「動到那幾條守衛時知道現況」。
  ⚠️ **未驗**：`_all_tier_classes()` 的實作與補償守衛 `tier = "t4"` 寫死這兩項，皆為 **AI 總管本輪單組實測**（讀 `tests/ui_v2/test_markup.py`），**⛔ 未經第二組獨立複驗**（`CLAUDE.md §-2` 規則 6）。
