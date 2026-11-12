# PROJECT_STATE 歷史分冊（2026-11-12 搬入；⛔ 非 SSOT、非現行規則、非接手點）

> **來源**：`docs/PROJECT_STATE.md`（main `a2926c8e`，完整 SHA `a2926c8e3f9962119f9c3ffbcb0903bd1eb500b1`）原 L613–L621、L709–L717、L766–L773、L885–L901、L916–L928、L1110–L1116、L1122–L1124，共 7 節、7 個連續區段；**逐字、依原順序**以 `## ` 標題切節、行切片搬入，未改字、未重排、未摘要。**搬移日**：2026-11-12。**依據**：客戶 DEC-173 Q2「PROJECT_STATE 指定歷史段可分冊歸檔。但不得只留下空標題而遺失仍有效的知識；有效架構、限制、產品狀態及 Decision 關係必須留在可直接查閱的現行內容。」與 Q6（逐字搬至 repo 內正式歷史分冊、保留 Git 歷史與可還原路徑）。
> **定位**：本檔為歷史分冊，非 SSOT、非現行規則、非接手點；現行狀態與仍有效的專案知識以 `docs/PROJECT_STATE.md`（其餘各節）、`docs/DECISIONS.md`、`docs/BACKLOG.md`、`docs/HANDOFF.md` 與 GitHub 實況為準。文中「本節」「上文」「見 §NN」等相對指涉，一律指搬移前的 `docs/PROJECT_STATE.md`。
> **還原**：每節以 `PROJECT_STATE_HISTORY_SEGMENT` 註解夾住、標原行號；把該節 BEGIN 註解與其後一個空行之後、END 註解之前的行，依原行號順序串接，放回主檔對應 `PROJECT_STATE_HISTORY_INDEX` 區塊（BEGIN 至 END 及其後一個空行；區塊上標 `lines=` 原行號）的位置，即逐位元組還原；或 `git show a2926c8e:docs/PROJECT_STATE.md`。

<a id="ps-hist-34"></a>
<!-- PROJECT_STATE_HISTORY_SEGMENT:BEGIN src=docs/PROJECT_STATE.md base=a2926c8e lines=613-621 -->

## 34. 📊 大盤頁 Decision Gate 草稿（2026-10-24；append-only；~~**非 Approved**~~ **Q1～Q4 已裁示 DEC-081**（2026-10-25 有意識的更新，不是漏刪，決策者 客戶；DEC-081））

> 2026-10-24 新增（決策者 AI 總管（事實更新））。本節**只放 pointer**，不是新 SSOT、不是裁示。全文：`docs/vnext/MARKET_PAGE_DECISION_GATE_2026-10-24.md`（~~v2~~ v3，commit `ab8b8342`，v3.1 措辭修正進行中（2026-10-25 有意識的更新，不是漏刪，決策者 AI 總管（事實更新））；基準 main `ea176b8d`）。

- **內容**：大盤相關舊→新能力覆蓋矩陣（§3，含 §3.15 舊 UI 結論句「首批一律不以結論承接」）、首屏文字線框與規則（§1）、可施工清單 W1～W13（§4，零語意變更）、被卡住清單 G*（§5~~，含 Risk Cap 卡位契約：卡面不顯示數字~~）；**Risk Cap 卡位**自 v3 起不再是 §5 預設契約，改為「刻意未接」併入 **Q2**、等客戶核准（2026-10-25 有意識的更新，不是漏刪，決策者 AI 總管（事實更新））、客戶裁示題 Q1～Q4（§6）、文件矛盾（附錄 B）、獨立複驗（附錄 C）。
- **狀態**：~~⛔ **未核准**；等客戶裁示 Q1～Q4 後才可開大盤頁實作批（DEC-003 ① 線框 gate）。未裁示前，該檔的推薦與「新版層級」欄只是 RECOMMENDATION。~~ **Q1～Q4 已裁示（DEC-081，客戶 2026-10-25）**；大盤頁實作批進行中（總管轉述）；Risk Cap 卡面措辭以客戶原文為準（見 §35）（2026-10-25 有意識的更新，不是漏刪，決策者 客戶；DEC-081）。
- **限制**（`CLAUDE.md` §-2 規則 6）：矩陣「沒有遺漏」**未證明**（撰寫組兩份單組盤點＋一組獨立複驗，皆單組）~~；v2 修訂未經第二輪複驗~~；已完成三輪獨立複驗（第三輪：剩餘項皆為措辭、修正中），每輪皆單組，完整性仍未證明（2026-10-25 有意識的更新，不是漏刪，決策者 AI 總管（事實更新））。
- **待辦落點**：`docs/BACKLOG.md` `VN1-MT-IA`、`VN1-MT-HOME`、`UIM-INVENTORY`、`UIM-MAPPING`、`UIM-COVERAGE-MATRIX`（各列 2026-10-24 補註）、`UIM-MKTGATE-DOC-DRIFT`（附錄 B 未登記矛盾）。

<!-- PROJECT_STATE_HISTORY_SEGMENT:END lines=613-621 -->

<a id="ps-hist-43"></a>
<!-- PROJECT_STATE_HISTORY_SEGMENT:BEGIN src=docs/PROJECT_STATE.md base=a2926c8e lines=709-717 -->

## 43. 新 UI Stage B 設計草稿（DEC-082 Stage B；2026-10-26；append-only；~~**草稿，待 Stage C 客戶 Gate**~~ **historical：已由 DEC-089 核准，其六向 IA 再被 DEC-091／092 四頁取代**（2026-10-29 有意識的更新，不是漏刪，決策者 AI 總管（事實更新）；上一值刪除線保留））

- 交付物：`docs/vnext/NEWUI_STAGE_B_DRAFT_2026-10-26.md`（基準 main `0ad07fd7`）：IA 草稿（責任方向↔現行 nav 三個候選）、六個責任方向頁面責任卡、🛡️／🎯／⚡／🩺 文字線框與互動對映、跨頁互動、Old→New Interaction Coverage 202 列收斂、S1～S28 收斂（B9）、獨立 QA 修正紀錄（B10）。
- 狀態：Stage B **草稿已交付（待 PR）**；單組撰寫＋三組獨立 QA 複驗後已逐項修正（B10），**修正後尚未再經獨立複驗**；Stage C 正式客戶 Gate **尚未呈現**。
- 待客戶：**G1**（導覽架構：A 沿用／B 六向重組／C 六向殼）、**G2**（🎯 找＋查同頁 X／兩頁 Y）、**G3**（⚡ 是否建、最小版本）、**G4**（🩺 第一版範圍與全站一行狀態）、**G5**（可點跨頁跳轉）、**G6**（🛡️ 逐檔表）、**G7**（High 待開事項是否另開）；另需明確回覆「線框套件（B3～B7）整體核准／退回／指定修改處」與「⚑／結構性自決項確認表」逐項同意／推翻。**沉默不得視為同意**，未回覆＝維持現況／暫行。總管自決 D-1～D-41、輕量確認 Q1～Q4、High 待開清單 HI-1～HI-6（未決，不擬答案）。
- ⛔ **Stage C 核准前不得施工**：0 程式碼、0 測試、0 navigation 變更、不刪舊 UI、不開 P2、不改投資公式／門檻／Risk Cap／趨勢或估值定義、不新增資料來源或 Action 語彙。
- 規則落點／依據：DEC-082（Stage A→B→C→D）、DEC-085／`PROJECT_RULES.md` 第 19 節（責任方向≠現行 nav 命名、SSOT、Coverage 四狀態、Missing 語意）；DEC-088 已記於第 42 節。
- ⚠️ 草稿內的程式碼層級宣稱，除各處標 `FACT` 並附 `file::symbol` 者外，均為 `INFERENCE`／未複驗；總管推薦（RECOMMENDATION）不是已選。

<!-- PROJECT_STATE_HISTORY_SEGMENT:END lines=709-717 -->

<a id="ps-hist-47"></a>
<!-- PROJECT_STATE_HISTORY_SEGMENT:BEGIN src=docs/PROJECT_STATE.md base=a2926c8e lines=766-773 -->

## 47. UI-CORRECTION 新 UI 視覺修正線框草稿（DEC-108，客戶 2026-10-29；append-only；**SUPERSEDED BY DEC-109**（2026-10-29 有意識的更新，不是漏刪，決策者 客戶（DEC-109）；上一值刪除線保留））

- **狀態**：~~線框草稿 `docs/vnext/NEWUI_D25_UI_CORRECTION_WIREFRAME_2026-10-29.md` 已撰寫（docs-only；截圖 `docs/vnext/ui_correction_assets/`），**待客戶核准**（`waiting_for_customer＝true`，僅限此線框 5 題）；未回覆＝不核准、不動工。~~ **現行**：被 DEC-109 取代——5 題撤回、`waiting_for_customer＝false`；線框檔與截圖已自本分支移除（原貌只保存在 PR #970 commit `06a7a3e5`）；有效部分已吸收（見 §48）（2026-10-29 有意識的更新，不是漏刪，決策者 客戶（DEC-109）；上一值刪除線保留）。
- **凍結**：~~UI-H 其餘與 UI-ME 的正式視覺實作暫停，直到線框核准（DEC-108）。~~ **現行**：凍結解除條件已由 DEC-109 改寫為「Phase 1 契約合併後依 Phase 2→7 推進，每個 UI phase 過 Visual Fidelity Gate」（見 §48）（2026-10-29 有意識的更新，不是漏刪，決策者 客戶（DEC-109 一）；上一值刪除線保留）。已合併的 UI-M／UI-T 不自動回退。
- **內容摘要**：全站首屏結構／卡片／圖表／文字／圖示規則（§A）、三頁 BEFORE／AFTER 線框（§B）、偏差對照（§C）、能力守恆（§D）、施工順序 E0→E4（§E）、客戶 5 題（A 推薦／B）。
- **限制**：偏差量測為冷啟動 FACT（沙箱無真資料；已載入後圖／表高度為 INFERENCE）；手機實機、Streamlit Cloud 未驗；單組撰寫未經第二組驗。
- **下一步**：~~客戶回覆「1 A｜2 A｜…」→ 依 §E 順序施工，每批獨立 QA 對照 §D。~~ 見 §48（2026-10-29 有意識的更新，不是漏刪，決策者 客戶（DEC-109）；上一值刪除線保留）。

<!-- PROJECT_STATE_HISTORY_SEGMENT:END lines=766-773 -->

<a id="ps-hist-52"></a>
<!-- PROJECT_STATE_HISTORY_SEGMENT:BEGIN src=docs/PROJECT_STATE.md base=a2926c8e lines=885-901 -->

## 52. New UI2 Batch 1：Guard 登記／VM boundary 骨架／Preview 入口骨架（2026-11-02；append-only；實作組單組、待總管複驗）

- **依據**：客戶 (7)（Sonnet 5.5＋Medium 後第一個 implementation batch，≤3 項；`docs/vnext/NEWUI2_ARCHITECTURE_GATE_2026-11-02.md` §4／§6／§7／§9）。基準 `origin/main`＝`ebb093be`（#997 合併點；實作組 `git fetch` 實查）。**未 commit／push（由總管處理）**。
- **做了什麼（0 投資語意）**：
  - **L0** `shared/ui2_contract/`：frozen dataclass VM（`FieldVM`／`CardVM`／`FirstScreenVM`／`PageVM`＝`context`＋`slice`）、`FieldState`（OK＋Freeze 四態＋`NOT_PROVIDED`）、`ChipTone` 四族、L1 字樣常數（逐字取 Freeze §5.1）；四頁 id／顯示名**重用** `shared.ia_nav4`（未複製第二份）。
  - **L3** `src/services/ui2/`：`vm_common`（canonical spec→VM，純函式）、`market_vm`（市場頁第一屏 builder）、`skeleton_vm`（標的／持股／我的）、`scenarios`（**FAKE**：四頁×六場景 cold／loaded／missing／stale／unavailable／not_evaluated）、`preview_feed`（Preview 期 FAKE feed）。**不聚合動作、不實作 System Action Aggregator**：市場／持股動作欄恆 `⬜ 尚未提供（待 System Action Aggregator）`；canonical 若夾帶 `action_needed` → raise。
  - **L5** `src/ui2/{shell,components,views}`：四頁 nav（📊🎯💼👤，只此四頁）、metric card／狀態 chip／freshness micro-tag／Preview banner／disabled CTA、第一屏四問（① 現在狀態 ② 是否需要行動 ③ 下一步 ④ 主 CTA）、L1／L2／L3 區塊。頁首固定標示「New UI2 Preview（fake data）」。
  - **L6** `app_ui2.py`（repo 根）：`set_page_config` 後只 `from src.ui2.shell import run`；`app.py` 不引用（測試釘住）、無 `?ui=2`、無路由。
  - **c3 guard**（加性）：`_PATH_LAYERS` `src/ui2/`→L5、`_MODULE_LAYERS` `src.ui2`→L5／`app_ui2`→L6、`_SCAN_FILES` 納入 `app_ui2.py`、`_layer_of_file` 認 `app_ui2.py`＝L6；**既有斷言一字未改**。
  - **新測試**：`tests/test_ui2_guards.py`（G2 VM 純度、G4 獨立性、G4b L5 只讀 `src.services.ui2`、G9 producer／`ui2_` key、chip 語意、G5 四態、G3 切片獨立、動作字樣／術語／Risk Cap／FAKE 標示）、`tests/test_ui2_registration_and_boot.py`（G1 meta＋c3 規則對 UI2 有牙、`app.py` 0 引用 ui2、G10 floor 掃 `app_ui2.py`、AppTest 四頁×六場景、乾淨行程冷啟動）。檢查器皆吃原始碼字串／callable，並有「注入違規必紅」的 teeth 測試。
  - **文件**：`CLAUDE.md` §8.2 七層表既有四列（L0／L3／L5／L6）的代表檔儲存格追加內容（未動既有條文）；BACKLOG §5.1.20＋三列狀態更新；`docs/vnext/NEWUI2_MIGRATION_CUTOVER_CONTRACT_2026-11-02.md` §6；`docs/vnext/NEWUI2_AUDIT_ACCEPTANCE_CHECKLIST_2026-11-02.md` §14；HANDOFF Safe Handoff（Batch 1）。
- **驗證（實作組實測；單組）**：新測試與 c3／`test_views_no_unverified_universal_claims.py` 綠；`streamlit==1.56.0` venv 跑 UI2 測試綠；mutation 15 項（拔 c3 登記、移出 `_SCAN_FILES`、VM 層 import streamlit、L5 import Legacy views、寫非 `ui2_` session key、`top_n` 影響 context、缺值補 0、四態字樣重複、未評估塗紅、拔動作注入防線、L5 用 `guard_chip`、Risk Cap 改字樣、拿掉 Preview 標示、`app.py` 引用 ui2、`app_ui2` import `app`）**全部轉紅**後已還原。截圖證據：`docs/vnext/newui2_batch1/`（390×844＋1440×900；cold／loaded／stale；**僅存證據，非 Visual Fidelity Gate 判定**；FAKE 資料）。
- **限制（誠實揭露）**：(1) 未實機（手機真機、Streamlit Cloud、真登入）；(2) 第一屏「不用滑」**未量測 y 座標**，只目視；(3) 導覽用 Streamlit 原生頂部水平 radio，**與已核准 W-1（底部固定列／左側欄）有落差**（`NUI2-NAV-W1-FIDELITY`）；(4) `src/services/__init__.py` eager import 使 Preview 行程載入 L1 模組（不呼叫；`NUI2-SERVICES-INIT-EAGER`）；(5) 第 6 態 `NOT_PROVIDED` 與 Risk Cap→Not evaluated 歸類為 AI 總管暫定（`NUI2-STATE-NOT-PROVIDED-AUDIT`）；(6) 截圖腳本為一次性、不在 repo（`tools/` 禁動；`NUI2-VF-UI2-SUPPORT`）；(7) 守衛是 AST／原始碼層級，非 import graph／runtime 層級；(8) 全部 FAKE，無真資料驗證（Stage I）。
- **未碰（硬限制）**：`app.py`、`requirements.txt`、`src/ui/**`、`src/ui_v2/**`、`src/data`、`src/compute`、`tools`、`scripts`、`.github`；System Action Aggregator／Risk Cap／Decision Digest／OneBrain runtime；LINE production。
- **下一步**：見 HANDOFF Safe Handoff（Batch 1）；`NUI2-PREVIEW-APP-MANUAL` **未發** Manual Action Gate（客戶：需要時才通知，⛔ 提前要求）。
- 📌 **2026-11-02 DEC-124 後註（append-only；本節上文一字未改）**：上文「`FieldState`（OK＋Freeze 四態＋`NOT_PROVIDED`）」「第 6 態 `NOT_PROVIDED` 與 Risk Cap→Not evaluated 歸類」已由客戶 (8) 裁示修正——`⬜ 尚未提供`＝capability state（⛔ 第 6 資料態）、Risk Cap `⬜ 無法判定`＝Unable to Determine；現況見 §53（有意識的更新，不是漏刪；決策者 客戶（DEC-124））。

<!-- PROJECT_STATE_HISTORY_SEGMENT:END lines=885-901 -->

<a id="ps-hist-54"></a>
<!-- PROJECT_STATE_HISTORY_SEGMENT:BEGIN src=docs/PROJECT_STATE.md base=a2926c8e lines=916-928 -->

## 54. New UI2 Batch 2（W-1 導覽保真／共用元件三軸呈現／Mobile-first 第一屏＋viewport 量測；2026-11-03；append-only；實作組單組、待總管複驗）

- **依據**：客戶 (9) 指示（2026-11-03；Sonnet 5.5＋Medium；最多 3 項；純 presentation）。基準 `origin/main`＝`830e8ad3`（含 #998 Batch 1 與 #999 DEC-124 語意修正；分支 `ccr-a0b4e085-ijdaio`，實作組 `git status` 實查與之一致；cron 會推進 tip，以當下 `git fetch` 為準）。本批變更在工作樹，**commit／push／PR 由總管處理**（實作組未 commit）。**本批無新 DEC。**
- **做了什麼（0 投資語意；未新增 Risk Cap 規則或數值；未動 Aggregator／Digest／OneBrain／LINE／real-data／production default）**：
  - **① W-1 Navigation Fidelity**：`src/ui2/shell/app.py` 以 `st.container(key="ui2_nav")` 包 `st.radio(key="ui2_page")`（四頁固定、⛔ 第五頁；session key 仍 `ui2_` 前綴；AppTest 可 `set_value` 切頁）；`src/ui2/shell/css.py` 以 CSS 定位——手機（≤768px）底部固定列 53px（= Freeze §16／Gate §3 的 53px）、桌機左側欄 176px；內容區手機 `padding-bottom:5rem`、桌機 `padding-left:12.5rem`；當前頁＝粗體＋`● ` 符號（pseudo-element）＋色條＋原生 radio `checked`（⛔ 只靠顏色）。選擇器**不依賴** Streamlit 內部 emotion class／`data-baseweb`／`stRadioOption`（1.56 與 1.59 DOM 不同），只用 `.st-key-ui2_nav`＋`[role="radiogroup"] > label`＋`input:checked`／`:has()`。導覽放在內容之後（DOM 順序＝手機底部列 Tab 順序）。Batch 1 的頂部水平 radio 呈現已移除；`temporary implementation gap` 收斂。
  - **② 共用 Presentation Components**（`src/ui2/components/html.py`）：三語意軸 chip 加**樣式**第二載體——資料語意＝實線框、判定結果（無法判定）＝雙線框、capability（尚未提供）＝虛線框，並輸出 `data-axis`／`data-state` 屬性；字樣三表仍互斥（DEC-124）。新增 `empty_state_html`（空／冷／未提供區塊，取代空白）；卡片／列／第一屏列加 `data-axis`／`data-state`；第一屏加量測錨點 `data-ui2-q`（q1～q4／ctx）、頁標題加 `data-ui2-page`／`data-ui2-scenario`；disabled CTA 加 `role="button"`＋`aria-disabled="true"`（⛔ `<a>`／`<button>`／`href`／`onclick`）。source／as_of 維持 field-level（既有；測試證明 ⛔ 全域更新時間）。
  - **③ Mobile-first 第一屏＋viewport 量測**：版面沿既有四問（① 現在狀態／② 是否需要行動／③ 下一步／④ 主 CTA）＋Risk Cap／目前曝險 context 列；動作欄維持 `⬜ 尚未提供（待 System Action Aggregator）`（capability，⛔ 可行動）、Risk Cap 維持 `⬜ 無法判定`（判定結果，⛔ safe）。量測腳本 `tests/ui2_viewport/measure_viewport.py`（可重現；`python -m tests.ui2_viewport.measure_viewport --out docs/vnext/newui2_batch2`；`--python /tmp/v156/bin/python --json-name viewport_measurements_streamlit156.json --shots none` 驗 floor）；判定器 `evaluate()` 為純函式（對真量測綠、對注入違規的量測 dict 紅）；**門檻全部引用既有條文，未自創**（`THRESHOLDS` 逐條標出處：Freeze §16「可用高約 791px＝844−53」、§0.1.6-2、Gate §3、Wireframes §0.4／§7 W-1、Freeze §4.1）。
- **量測結果（Chromium headless，390×844 與 1440×900；四頁 × cold／loaded／missing／stale／unavailable／not_evaluated＝每 viewport 24 態、共 48 態；FAKE 資料）**：Streamlit 1.59.2 **48/48 通過**、Streamlit 1.56.0（`/tmp/v156` venv，floor）**48/48 通過**。手機各頁各元素底緣 y（px，跨六場景範圍；可用高 791）：📊 市場 ① 248–268、Risk Cap 304–324、② 399–419、③ 471–491、④ 562–582；🎯 標的 ① 248–272、Risk Cap 304–328、② 375–400、③ 428–453、④ 518–543；💼 持股 ① 248–268、目前曝險 358–378、② 454–474、③ 526–546、④ 616–636（全站最大）；👤 我的 ① 248–272、② 301–339、③ 354–411、④ 444–502。元素高度最大：①～③ ≤ 96px、④ ≤ 90px。導覽：手機 top=791／bottom=844／全寬／四格同列（各 97.5px 寬）；桌機 left=0、寬 176px、四項垂直。水平捲動：document／stMain `scrollWidth` = `clientWidth`（390／1440），第一屏區塊無橫向裁切。頁底內容不被導覽遮住。完整原始數值見 `docs/vnext/newui2_batch2/viewport_measurements.json`（及 `_streamlit156.json`）；截圖（手機全部 24 張＋桌機 cold／loaded 8 張）同目錄 `*.png`，**手機截圖已逐張目視**：標題無重疊、chip 列完整、底部列未遮內容。
- **驗證（實作組實測；單組）**：新測試 `tests/test_ui2_batch2.py`（94 passed＋1 slow 真瀏覽器）；`tests/test_ui2_*.py`＋既有守衛於 Streamlit 1.59.2 與 1.56.0 皆綠；mutation 10 項實測轉紅後還原（拔底部固定導覽［靜態＋真瀏覽器］、導覽第五頁、chip 無文字（只靠顏色）、capability 字樣併入資料五態、判定結果 chip 以資料軸渲染、chip 軸別樣式拔除、disabled CTA 變可行動、頁面注入全域假更新時間、拔頁底留白［靜態；真瀏覽器以 Playwright 例外轉紅，見 BACKLOG `NUI2-VIEWPORT-M8-NOISY-RED`］、第一屏下移 300px［真瀏覽器斷言式轉紅］）。**注意：這 10 項 mutation 中部分為靜態／單元層轉紅，並非全部由真瀏覽器斷言轉紅**（真瀏覽器斷言式轉紅僅「拔底部固定導覽」「第一屏下移」兩項；「拔頁底留白」為 Playwright 例外轉紅）；且僅單組驗證，獨立 QA 未全數重跑。全 repo 序列結果見 HANDOFF Safe Handoff（Batch 2）。
- **限制（誠實揭露）**：(1) 量測全在 **FAKE 字串**；真資料文字較長會改變高度（餘裕：手機 ④ 最大 636 vs 791）；(2) 只測 Chromium headless 兩個 viewport；Safari／Firefox／真機／iOS 安全區／360px 未測；(3) 無螢幕閱讀器驗證，「aria-current 類」以原生 radio `checked`＋符號等價實現；(4) 導覽自帶深色底（Streamlit 無公開主題變數），使用者切 Light theme 時不一致；(5) 凍結線框第一屏的「今日結論」「mode 切換＋搜尋」等**未做**（BACKLOG `NUI2-WIREFRAME-FIRST-SCREEN-EXTRAS`）；(6) CI slow lane 是否有 Chromium 未確認；(7) 導覽 CSS 依賴 `.st-key-*` class 與 `:has()`，Streamlit 升版需重量。
- **未碰（硬限制；`git diff --name-only HEAD -- app.py requirements.txt tools scripts .github src/ui src/ui_v2 src/data src/compute` 實查為空）**：`app.py`、`requirements.txt`、`tools/`、`scripts/`、`.github/`、`src/ui/**`、`src/ui_v2/**`、`src/data`、`src/compute`；System Action Aggregator、Risk Cap 規則／數值／runtime、Decision Digest、OneBrain、LINE、real-data wiring、production default、Old UI／Legacy New UI。
- **§27 檢查**：新 Rule＝無（既有 Freeze §4.1／DEC-124 三軸邊界原樣適用；量測門檻不自創屬既有 PROJECT_RULES 精神）；新 Decision＝無（實作選擇屬 `CLAUDE.md` v3 §03-1 內部自決）；Audit finding／Limitation／Backlog／Migration debt／Acceptance item 已寫入 BACKLOG §5.1.22、Audit Checklist §16、Migration Contract §8、HANDOFF Safe Handoff。

<!-- PROJECT_STATE_HISTORY_SEGMENT:END lines=916-928 -->

<a id="ps-hist-69"></a>
<!-- PROJECT_STATE_HISTORY_SEGMENT:BEGIN src=docs/PROJECT_STATE.md base=a2926c8e lines=1110-1116 -->

## 69. New UI2 視覺完善 Batch 1（2026-11-05；presentation-only；實作組單組；獨立 QA 待做）

- **已做**：① chip 文字色對比（`src/ui2/shell/css.py`；對深色底與疊 tint 皆 ≥4.5:1；`tests/test_ui2_chip_contrast.py`，含負向突變）。② 💼 持股桌機首屏依 Wireframes §4.2／W-11 重排（`src/ui2/components/html.py::hold_l1_html`／`page_title_html`、`src/ui2/views/hold.py`、`css.py` `.ui2-h-l1`；`tests/test_ui2_hold_header.py`）。手機版面不變（`hold_loaded` 與「只換 chip 色」基準逐像素相同）。
- **實測（FAKE；Chromium headless）**：measure_viewport 70/70（1.59.2）、70/70（1.56.0）；Real 11/11（兩版）；📊 手機 stale 181.6／unavailable 162.5（與 before 逐位相同，≥160 守衛未退化）；`UI2_BROWSER_LANE=required` `ui2_browser` lane 52 passed（1.56.0）／52 passed（1.59.2）；`tests/test_ui2_*`＋c3＋portability 1470 passed。證據 JSON（`newui2_batch3b`／`newui2_realfeed`）因 source_hash 重生，僅 `p4_hold` 結果改變。
- **未動**：JS（`drawer_js.py`、JS_V4 hash、`tests/test_ui2_drawer_js_guard.py`）、資料來源、公式、Risk Cap、OneBrain、OAuth、A2／A3／B／C 類；DEC 未新增。
- **未驗**：iOS／Android 真機、Streamlit Cloud／Manage app、Firefox／WebKit、Light theme、Real feed 視覺截圖、1.56／1.59 以外版本；非 pixel parity（無原圖）。

<!-- PROJECT_STATE_HISTORY_SEGMENT:END lines=1110-1116 -->

<a id="ps-hist-69-note2"></a>
<!-- PROJECT_STATE_HISTORY_SEGMENT:BEGIN src=docs/PROJECT_STATE.md base=a2926c8e lines=1122-1124 -->

## 補註（2026-11-05｜💼 W-11 批 1 版面空槽）
- draft PR `ui2/hold-w11-batch1`：純版面空槽（狀態行／需處理單行／Primary 與建議持股水位空槽／持股表欄名）。W-11 仍 open（待獨立 QA＋資料接線）。守衛與證據見 BACKLOG `NUI2-HOLD-W11-BATCH1`。

<!-- PROJECT_STATE_HISTORY_SEGMENT:END lines=1122-1124 -->

