# NAV-1 四頁導覽殼替換（實作規格＋交付記錄）

- **日期**：2026-10-28　**基準**：main `4653515`　**批次**：PLAN §5 序 6「NAV-1 四頁導覽殼替換（UI）」
- **來源**：客戶 DEC-092 Q6／DEC-097＋2026-10-28 指示；`docs/BACKLOG.md` `NAV1-DEC097-REQS`；wireframe `docs/vnext/d25_wireframes/`（`index.html`／`market`／`target`／`holdings`／`mine`）。
- **標記**：FACT＝已讀原碼／已跑測試；INFERENCE＝推得未驗；MISSING＝查無。**未驗事項見 §8，不得當成已驗結論。**
- **誠實揭露（CLAUDE.md §-2 規則 6）**：本文件與程式由實作組單組產出；§5 的「語意不變」判斷與 §6 的「一字不變」是**實作組自己的結論**，其機械證據（AST 對照守衛、突變表）已列，但**尚未經第二組獨立複驗**。

## §1 一頁摘要

| 項目 | 結果 |
|---|---|
| 主導覽 | 固定 4 頁：📊 市場／🎯 標的／💼 持股／👤 我的（標籤逐字客戶指定） |
| 手機 | 底部固定 4 按鈕（`st.container(key="nav4_bottom")` ＋ CSS；`@media (max-width: 768px)` 才固定到底） |
| 桌機 | 左側欄單選（`st.sidebar` 內 `st.radio`，垂直；wireframe 左側欄） |
| 共用狀態 | **一個** session_state key `_nav4_page`；兩個元件只經 `on_change` 寫它 |
| 預設入口 | **翻轉**：預設＝新四頁；舊 UI（D2 側欄雙層 radio＋舊 7 頁籤）＝ legacy 模式 |
| rollback | 網址 `?legacy=1`（`?legacy=0` 清除）；**無任何可見入口**；舊程式碼一行未刪、未註解 |
| 不變 | `shared/ia_nav.py`（D2 事故模組）、`PAGE_LABELS`、`src/ui/tabs/**`、AB-2b／AB-4w、`shared/decision_digest*.py` |
| 新檔 | `shared/ia_nav4.py`（L0）、`src/ui/views/shell_nav4.py`（L5）、`tests/test_nav1_*.py`（4 支）、本文件 |
| 改檔 | `app.py`（只動路由）、`tests/test_boot_import_smoke.py`（只加、不削）、4 支既有測試（只加 legacy 旗標，斷言不動） |
| **需客戶／總管知悉** | §4「偏離表」與 §7「已知限制」第 1～3 項（預設翻轉後有一批頁內指路句懸空） |

## §2 架構（CLAUDE.md §8.1 六點，內部必答）

### 2.1 單一職責
把「固定四頁主導覽」做成**原生 Streamlit 單選元件**，讓手機底部列與桌機側欄**共用同一個頁狀態**，並用 routing 旗標把舊 UI 從預設畫面隱藏（不刪）。

### 2.2 模組切分

| 檔 | 層 | 職責 | 不做 |
|---|---|---|---|
| `shared/ia_nav4.py` | L0 | 四頁 id／標籤／`PAGE4_TO_VIEW` 對映、legacy 旗標純函式、key 名稱、`reconcile_nav4`（import 時自檢） | 不 import streamlit、不碰 session、不改 `ia_nav.py`（只 import 它的頁 id 常數） |
| `src/ui/views/shell_nav4.py` | L5 | 渲染側欄 radio／底部固定列 radio／標的頁葉選擇器；注入導覽 CSS；兩元件共用回呼 | 不取數、不畫數字／燈號、不用紅框、**不渲染任何 legacy／舊版字樣** |
| `app.py` | L6 | `_nav4_resolve_legacy()`（set_page_config 之前）；側欄 `if _NAV4_LEGACY:`（D2 radio 原樣）／`else:`（新導覽）；新模式主分支（導覽＋view＋footer＋`st.stop()`） | 不 import 新模組於 module 層（只在 `_ia_view_nav4` / `_nav4_*` 函式內 late import）；不改既有 `if _IA_PAGE is not None:` legacy 分支與舊 7 頁籤 |

### 2.3 資料流向

```
URL ?legacy=1|0 ──▶ _nav4_resolve_legacy() ──▶ session[_nav4_legacy] ──▶ _NAV4_LEGACY ──┐   （set_page_config 之前）
                                                                                       │
 ┌───────────────────────── 新（預設）模式 ──────────────────────────┐   ┌── legacy 模式（一字不變）──┐
 │ 側欄 radio(_nav4_w_side) ─┐ on_change                              │   │ D2 側欄雙層 radio          │
 │ 底部 radio(_nav4_w_bottom)┴▶ _on_nav_change ▶ session[_nav4_page]  │   │ 舊 7 頁籤、置底條、        │
 │   (每輪渲染前由 SSOT 預填兩 widget 顯示值)      │                  │   │ 我的組合列、總經指南針     │
 │ 標的葉 radio ▶ _on_leaf_change ▶ session[_nav4_target_leaf]        │   └────────────────────────────┘
 │ current_view() = PAGE4_TO_VIEW[_nav4_page] (+葉) = _IA_PAGE        │
 │ → _render_tab_isolated(導覽) → _render_tab_isolated(view) → footer → st.stop()
 └────────────────────────────────────────────────────────────────────┘
```

### 2.4 依賴方向（§8.2）
`app.py`(L6) → `shell_nav4`(L5) → `shared.ia_nav4`(L0) → `shared.ia_nav`(L0)；`shell_nav4` → `src.ui_v2.tokens`（L5，取色）。全部向下；L5 不 import L1／L2／L3；`tests/test_c3_layering_guard.py` 綠。

### 2.5 失敗降級

| 失敗 | 行為 |
|---|---|
| CSS 全失效（`st-key-` class 改名、`:has` 不支援…） | 底部那組退化為**主內容流中的橫排 radio**，仍可點、仍寫同一格 SSOT；桌機多出一組導覽（無害）。CSS 規則中**沒有「預設隱藏、靠 CSS 才顯示」**；`display:none` 只在桌機／print 的 media 內（`TestCss.test_failure_degradation_is_benign` 釘住） |
| 導覽元件 import／render 例外 | 紅態 `st.error`（含例外型別）＋ stderr traceback；`_IA_PAGE` 退到 📊 市場 ⇒ 頁面內容仍渲染；**不白屏、不靜默改走舊 UI** |
| view 例外 | 沿用既有 `_render_tab_isolated`（紅框＋traceback）；導覽不受影響 |
| session 內頁狀態壞值（非四頁 id） | `coerce_page4` **Fail Loud**（不靜默改回預設） |
| 網址 `?legacy=` 空值／亂值 | **維持目前旗標**（不 raise、不進 legacy） |
| 新模組壞掉但要 rollback | `?legacy=1` 路徑**不 import `shell_nav4`**（`test_b3_*` 以毒藥模組證明）；只依賴純 L0 `ia_nav4` 的旗標函式 |

### 2.6 自評過度設計（§8.1 step 6）

- **做**：L0 對映表＋`reconcile_nav4`（四頁對映漏接是這類殼最常見的靜默 bug，D2 已有同型守衛）；單一 SSOT key；兩元件共用回呼。
- **先不做，等真的需要再加**：(a) 深連結／把頁狀態鏡像到網址（`?page=`）——手機斷線重連目前回到 📊 市場，與 D2 殼行為同；(b) 桌機側欄收合時顯示底部列（需依賴 Streamlit 內部 `aria-expanded`）；(c) 第二個 secrets 旗標 `LEGACY_UI_DEFAULT`（規格：確實必要才加；目前 `?legacy=1` 足夠 rollback）；(d) 自訂 JS／`components.html`（不引入第二套前端）。

### 2.7 複雜度
導覽每輪渲染 O(4)（四個選項）＋常數次 session 讀寫；無資料取用。`reconcile_nav4` 僅 import 時與 app 啟動各跑一次，O(頁數)。

## §3 與 PLAN／A 規格的差異表

| # | PLAN／A 規格原寫法 | 本批實作 | 理由 | 決策依據 |
|---|---|---|---|---|
| 1 | PLAN §3／§5 序 6、A §3.2 N2：**主畫面頂端** 4 項控制列（`segmented_control`／`pills`／horizontal radio） | 桌機＝**左側欄**；手機＝**底部固定列** | 客戶 DEC-097 指定手機底部固定 4 按鈕；wireframe（`index.html` 圖例「桌面左側欄、手機底部列」，四個頁面檔的 `<aside class="side">`／`<nav class="bn">`）桌機為左側欄。N2「頂端」與 DEC-097＋wireframe **衝突，以後者為準**（`NAV1-DEC097-REQS` 已預告此待查證項；DEC-097 效力邊界段亦要求揭露） | DEC-097；A §9 流程提醒「wireframe 為視覺基準」 |
| 2 | A §3.2 對 N2 的代價 (3)：「手機底部固定列需自訂 CSS 注入，易隨版本失效，不採用」 | 採用底部固定列，但**失效降級良性**（§2.5） | 客戶後續明示採底部固定 4 按鈕；風險以「CSS 只是加分、原生 radio 是本體」化解 | DEC-097 |
| 3 | PLAN §8.2 4／A §3.4：**預設入口不變**（舊 7 頁籤）；舊 UI 與預設入口不變 | **預設入口翻轉**為新四頁；舊 UI 變 legacy（`?legacy=1`） | 客戶 DEC-097 第 2 點：NAV-1 時舊 UI 從一般使用者預設畫面／導覽隱藏。**不等於通過 Old UI Removal Gate**（DEC-019／020、`UIM-REMOVAL-GATE` 不變）；舊程式碼未刪、rollback 保留 | DEC-097 |
| 4 | PLAN §5 序 6 範圍寫「改 `shared/ia_nav.py`」 | **不改** `shared/ia_nav.py`；新增 `shared/ia_nav4.py` | 事故模組（root cause 未確認）不碰；四頁表與六向 `NAV_TREE` 並存，legacy 仍用後者 | 總管拍板 A；DEC-092 Q6 |
| 5 | A §8.3 I-1：`PAGE_LABELS` 於實作批次一併改 | **未改** `PAGE_LABELS`（「📊 大盤」「💼 我的持股」） | 本批指示明列 I-1 未拍板、不碰 | 總管指示 (6) |
| 6 | D2 殼：位置列「📍 位置：…」、佔位頁 ⚡／🩺 | 新模式**不畫**位置列與佔位頁；這些只在 legacy 的 D2 殼 | 位置列是 D2 六向導覽的產物；佔位主頁設計已被 supersede（DEC-092 Q6） | DEC-092 Q6 |
| 7 | `st.set_page_config(initial_sidebar_state='collapsed')` | 新模式 `'auto'`（桌機展開、手機收合）；legacy 仍 `'collapsed'` | 桌機左側欄＝主導覽，預設收起會讓桌機找不到導覽 | wireframe 桌面左側欄 |
| 8 | PAGE4 ↔ view：🎯 標的＝🔍 找標的＋🔬 查一檔（A §2.1） | 標的頁內以**第二層（葉）radio**切換兩個現有 view（沿用 D2「同一方向內第二層」機制） | A §4.2 的「單一標的頁（產業機會→候選→單一股票同頁）」是 **UI-T 批次**內容；NAV-1 不重寫頁內容 | 總管拍板 C；見 §4 偏離 1 |

## §4 與 wireframe 的一致性逐項表（FACT：逐檔讀了 `index.html`／`market.html`／`target.html`／`holdings.html`／`mine.html` 的導覽 DOM／CSS）

wireframe 導覽事實：桌機 `<aside class="side">`（寬 150px、品牌字「投資儀表板」、4 個 `<a>`、底註「固定 4 個主導航」）；手機 `<nav class="bn">`（`grid-template-columns:repeat(4,1fr)`、每格 emoji 在上、文字在下、固定於手機框底部）；`aria-current` 標目前頁。

| 項 | wireframe | 實作 | 一致？ |
|---|---|---|---|
| 4 項標籤與順序 | 📊 市場／🎯 標的／💼 持股／👤 我的 | 逐字相同（測試以寫死第二來源釘住） | ✅ |
| 桌機位置 | 左側欄 | `st.sidebar` 內垂直 radio（`initial_sidebar_state='auto'`） | ✅（見偏離 3：側欄另含既有控制項） |
| 手機位置 | 底部固定、4 等寬 | `.st-key-nav4_bottom{position:fixed;bottom:0…}`、4 格 `flex:1 1 0`、`nowrap` | ✅ |
| 目前頁標示 | `aria-current`＋左／上強調線 | radio 選中態＋CSS `inset 0 2px 0 <focus>`（CSS 失效時為原生 radio 圓點） | ✅（樣式近似，非像素級） |
| 單行不換行 | 是 | `flex-wrap:nowrap`、`white-space:nowrap`；標籤 ≤6 字（`reconcile_nav4` 檢查） | ✅（實機未驗，見 §7） |
| safe-area／遮頁尾 | wireframe 未涉及 | `env(safe-area-inset-bottom)`＋主內容 `padding-bottom` | ➕ 技術補強 |
| 列印 | 未涉及 | `@media print` 隱藏 | ➕ |
| 資料健康 chip／AI 總結卡／頁首問句 | 在各頁主內容 | **不在 NAV-1 範圍**（UI-M／T／H／ME、AB-5／6） | — |

### 偏離表（**不是我可定案的項目；列給總管／客戶審**）

| # | 偏離 | 為何發生 | 影響 | 建議 |
|---|---|---|---|---|
| 1 | 🎯 標的頁多一個「🔍 找標的／🔬 查一檔」**第二層橫排 radio**（wireframe 標的頁是單一頁、無此控制） | 現有 `page_find`／`page_inspect` 仍是兩個 view；A §4.2 的合併版屬 UI-T。依總管拍板 C 沿用 D2 葉機制 | 畫面多一條過渡控制 | **過渡項**，UI-T 落地時連同 `NAV4_TARGET_LEAF_KEY`、`render_target_leaf_selector` 一併移除；若客戶認為這屬「版面佈局異動」需先審草稿，請於合併前裁示 |
| 2 | 手機底部列每格為「📊 市場」**單行**（wireframe：emoji 在上、字在下兩行） | 要求「4 按鈕單行不換行」；radio 標籤不易拆兩行且標籤須逐字 | 視覺較矮、較密 | 可接受；若要完全照 wireframe 需改成自訂 HTML 按鈕（失效降級較差），不建議 |
| 3 | 桌機左側欄除 4 項導覽外，**仍含**既有 Google 帳號／連線狀態／🔄 強制刷新／資料健康等控制（wireframe 側欄只有導覽） | D-39：側欄既有控制在新模式照常顯示、不搬不動；本批只動 routing | 側欄比 wireframe 長 | 後續 UI-ME／資料健康批次再整理；本批不動 |
| 4 | 無 wireframe 的「投資儀表板」品牌字與「固定 4 個主導航」底註 | 側欄已有既有標題「📊 台股AI戰情室 v3.0」 | 無功能影響 | 無需處理 |
| 5 | **頁面標題與導覽標籤不一致**：導覽「📊 市場」「💼 持股」，view 內標題仍為「📊 大盤」「💼 我的持股」 | `PAGE_LABELS` 未改（I-1 未拍板） | 使用者點「📊 市場」看到標題「📊 大盤」 | 需客戶／總管拍板 I-1 後由後續批次改 `PAGE_LABELS`（牽動 `tests/test_page_*` 與指路句字串） |

## §5 既有測試同步清單（預設翻轉 ⇒ 受影響測試改在 legacy 模式跑；**斷言一字未動、未放寬、未刪**）

做法：這些測試守的是 D2 側欄／舊 7 頁籤＝legacy 行為，故在建立 `AppTest` 後加 `at.session_state[LEGACY_SESSION_KEY] = True`（`shared.ia_nav4.LEGACY_SESSION_KEY`）。**新預設模式的對應守衛**另在 `tests/test_nav1_*.py`。

| 檔 | 改了什麼 | 為何語意不變 | 實測 |
|---|---|---|---|
| `tests/test_ia_v2_sidebar_nav.py` | `_run_app()` 內加 legacy 旗標＋ import 常數 | 該檔所有斷言（7 頁籤名稱／順序、radio key／index、毒藥模組、置底條有無、免責聲明）都是對 legacy 路徑；旗標讓它仍跑同一路徑 | 修前（無旗標）3 條 slow 紅；修後全綠 |
| `tests/test_ia_nav_shell.py` | `_run()` 內加 legacy 旗標＋ import | 同上（D2 六向殼畫面態） | 修前 8 條紅；修後全綠 |
| `tests/test_me_p1_logout_e2e.py` | `_start()` 內加 legacy 旗標＋ import | 側欄登出／「不使用 vs 新版模式」Sheet 框行為皆為 D2 路徑語意 | 修前 6 條紅；修後全綠 |
| `tests/test_sheet_safety_app_e2e.py` | `_app()` 內加 legacy 旗標＋ import | 同上 | 修前 3 條紅；修後全綠 |
| `tests/test_boot_import_smoke.py` | **只新增** 4 條（legacy 冷啟動、nav4 模組乾淨 import／L0 純度、app 對 nav4 的 import 皆 late、殘留舊 `shared.ia_nav4` 的偵測能力）；原 (a)(b)(c) 三組一字未動 | 不削弱：(a) 冷啟動現跑**新預設模式**；(b) 靜態契約自動涵蓋函式內 `from shared.ia_nav4 …`／`from src.ui.views.shell_nav4 …` 的名稱 | 全綠 |
| `tests/test_batch_z60.py` | 只更新 `_BASE_DIGEST`（舊 UI 檔指紋；`app.py` 在其涵蓋範圍），依該檔 docstring 既定協議：舊值加刪除線保留＋註明 NAV-1 核准改動（DEC-019 揭露）；`_BASE_COUNT` 仍 91 | 該守衛本意是「舊 UI 檔改動須經核准並揭露」；本次 `app.py` 改動即為客戶核准的 NAV-1 | 修前紅（唯一新增紅燈），修後綠 |
| 靜態守衛（`test_ia_v2_sidebar_nav`、`test_p0x_view_mount_claims`、`test_c3_layering_guard` 等）| **未改** | `app.py` 結構刻意保持相容：legacy 分支、`_IA_VIEWS` 取值僅一處、`st.stop()` 在建 `st.tabs` 之前 | 全綠（修 `_IA_VIEWS[` 註解字面一次，見 commit） |

**另新增**：`tests/test_nav1_ia_nav4.py`（L0）、`tests/test_nav1_shell_nav4.py`（元件／CSS）、`tests/test_nav1_app_routing.py`（路由靜態＋行為，含「legacy 區塊與 HEAD AST 逐節點相同」對照守衛）、`tests/test_nav1_default_mode_sidebar.py`（預設模式下側欄 Sheet ID 末 6 碼等語意）。

## §6 legacy 模式＝今天的行為（機械證據）

1. `tests/test_nav1_app_routing.py::TestStatic::test_s3_legacy_d2_block_is_ast_identical_to_head`：HEAD 的 D2 導覽區塊（radio＋第二層＋圖例，29 行）以**逐字快照**內嵌於測試，與 `if _NAV4_LEGACY:` 內的 AST 逐節點比對相同（只差一層縮排＝`git diff -w` 只多 `if`／`else`）。
2. 既有 4 支 AppTest 檔在 legacy 旗標下**全綠、斷言未動**（§5）。
3. `TestLegacyMode`：`?legacy=1` → 7 頁籤、`_sb_ia_page` radio 選項與 index 0 與今天相同、D2 圖例與「ⓘ 驗收完成後…」caption 存在、`shell_nav4` 被毒藥化也不受影響。
4. 冷啟動：`tests/test_boot_import_smoke.py::test_cold_boot_legacy_mode_*`。
5. ⚠️ **唯一已知的 legacy 行為差異**：旗標判斷發生在 `set_page_config` 之前，故 `legacy` 以外沒有差異；`initial_sidebar_state` 在 legacy 仍為 `'collapsed'`。

## §7 已知限制（請當成**未驗**）

1. ⚠️ **預設翻轉後，頁內「指路句」有一批指到預設模式不可達的目的地**（FACT：預設模式逐頁渲染後 grep 實測）：
   - `📊 市場` 頁有「🩺 資料中心 › 📖 憑什麼 › 資料體檢」「AI 問答請到 …」等指路（目的地 `page_why` 只在 legacy D2 殼可達）；`💼 持股` 頁的「到 📊 大盤 › 🚦 今天 按『🚀 更新今日戰情』」（`page_today` 只在 legacy 可達；`page_hold.py` 內此類指路約十餘處）。
   - `👤 我的` 頁文字：「切回舊版：側欄『🆕 新版戰情室（試用中）』選『不使用…』」「Google 登入轉跳回來…側欄導覽會回到『不使用…』」——預設模式**沒有**這些側欄控制（且 DEC-097 要求 legacy 入口不出現在一般導覽）；`page_me`／`page_hold` 的 `CONTENT_EDIT_OLD_UI_WHERE`「目前請切回舊版 → 📁 組合管理」同理。
   - 這些字串住在 `shared/ia_nav.py`（事故模組）與 `src/ui/views/page_*.py`，不屬本批「只動 routing」範圍，**本批未改**。屬 §1 同型的「指向畫面上不存在的東西」，需後續批次處理（建議與 I-1 頁名改寫、UI-M／UI-H／UI-ME 一併，或另開小批「指路句改指四頁」；範圍與是否需客戶審屬總管判斷）。
2. **🚦 今天／📖 憑什麼的入口在預設模式暫時不可見**。依 A §2.1 它們的能力（需要處理、資料健康、查看依據）要併入各頁，但那是後續批次（UI-M／AB-5／AB-6）；其功能在舊 7 頁籤（🔧 工具箱 › 🔎 資料診斷、🧬 AI 問答）仍在，經 `?legacy=1` 可達。**這是暫時缺口，不是「已併入」**。
3. **頁面標題與導覽標籤不一致**（§4 偏離 5）。
4. **Cloud 啟動與手機實機未於沙箱實測**（PLAN §8.2 3）：本批所有「底部固定」「safe-area」「窄螢幕單行」「抽屜疊放順序」「iOS／Android 行為」均**未驗**；768px 斷點是依 Streamlit 側欄抽屜斷點推估（INFERENCE）。需客戶實機點驗。
5. **CSS 依賴 Streamlit 的 `st-key-<key>` class、`[data-baseweb="radio"]`、`[data-testid="stMainBlockContainer"]` 與 `:has()`**，皆非公開保證；floor 1.56 是否具備、各版本 DOM 差異**未驗**（沙箱僅 1.59.2）。失效時退化行為見 §2.5。
6. **legacy 旗標與 query 還原互動**：
   - 旗標寫入 session；OAuth callback 的 `st.query_params.clear()` 清掉網址參數不影響本 session。
   - ⚠️ **Google 登入轉跳回來是新 session，網址不帶 `legacy` ⇒ 回到新（預設）模式**；若 rollback 使用者要在 legacy 下登入，登入後需再開 `?legacy=1`。
   - 手機斷線重連＝新 session：網址仍帶 `legacy=1` 才會維持 legacy；頁狀態（`_nav4_page`）不鏡像到網址，**重連後回 📊 市場**（與 D2 殼同）。
   - `?legacy=`（空）、`?legacy=yes` 等亂值**不進** legacy（維持目前旗標）。
   - 既有 `?sid=`、`?sheet=`、`?gs=` 還原邏輯未動；測試顯示與 `legacy` 參數互不干擾（`test_nav1_default_mode_sidebar.py` 帶 `?sheet=`）。
7. 桌機使用者手動收合側欄後導覽會消失（需點展開箭頭）；`@media (min-width: 769px)` 隱藏了底部列。若客戶要求「桌機側欄收合時也有導覽」需另案（依賴 `aria-expanded` 非公開屬性）。
8. 底部固定列在 DOM 上位於主內容最前，桌機因 `display:none` 不佔位，但 Streamlit 容器 `gap` 可能在內容頂端留 1 個間距（視覺細節，未實測）。
9. 沙箱缺 `FinMind` 套件、無外網；所有 AppTest 以既有 `stub_trading_day_status` fixture 避免連外；**真實資料路徑未測**。

## §8 未驗事項（§-2 規則 6 揭露）

- 本檔 §3～§7 的判斷由實作組單組產出，**未經第二組獨立複驗**；§4 的 wireframe 對照為讀 HTML 原始碼，未開瀏覽器渲染。
- 「預設模式不渲染任何 legacy 字樣」：元件／app 新分支的字串常數已以 AST 掃過；但頁內容（`page_*.py`）本身含「切回舊版」等字樣（見 §7-1），**不在本批掃描承諾內**。
- 突變表為實作組自跑，見 §9。

## §9 突變表（拔掉守衛的修復邏輯 ⇒ 必須轉紅）

| # | 突變 | 首個轉紅的守衛 |
|---|---|---|
| M1 | 拔掉 legacy 旗標判斷（永遠 False） | `TestLegacyMode::test_b3_query_param_enters_the_old_ui…` |
| M2 | 拔掉預設翻轉（預設仍為舊 UI） | `TestStatic::test_s1_flag_is_resolved_before_set_page_config` |
| M3 | 舊 D2 radio 不再隱藏 | `test_s3_legacy_d2_block_is_ast_identical_to_head` |
| M4 | SSOT 回呼不寫 SSOT | `TestBoundary::test_the_page_state_is_written_only_by_the_declared_functions` |
| M5 | `reconcile_nav4` 變空殼 | `TestReconcileHasTeeth::test_missing_view_in_dispatch_table` |
| M6 | 標籤被改（👤 我的→👤 帳號） | `TestLabels::test_labels_are_the_clients_four_verbatim_in_order` |
| M7 | CSS 拔掉 `position:fixed` | `TestCss::test_fixed_bottom_bar_only_inside_the_narrow_media` |
| M8 | CSS 加預設隱藏規則（降級不良性） | `TestCss::test_failure_degradation_is_benign` |
| M9 | app.py module 層 import ia_nav4（破壞 late-import） | `test_s1_new_imports_are_late_only` |
| M10 | 底部導覽不渲染 | `TestSingleSsot::test_default_is_market_and_both_widgets_agree` |
| M11 | 新模式分支拿掉 `st.stop()` | `test_s2_default_branch_precedes_legacy_branch_and_tabs_and_is_isolated` |
| M12 | 新模式側欄解析結果丟掉（`_IA_PAGE=None`） | `TestDefaultMode::test_b1_default_boots_into_the_four_page_nav` |
| M13 | `PAGE4_TO_VIEW` 標的少一個 view | import 時 `reconcile_nav4` 即 RuntimeError（collection error） |
| M14 | legacy 旗標空值視為 True | `TestLegacyFlag::test_truth_table[-False-False]` |
| M15 | 標的葉狀態不保留 | `TestTargetLeaf::test_leaf_pick_switches_view_and_survives…` |
| M16 | 新模式 sidebar 初始狀態改回 collapsed | `test_s1_page_config_keeps_collapsed_for_legacy_and_opens_the_sidebar_for_new_mode` |
| M17 | widget 預填同步失效 | `TestSingleSsot::test_picking_on_either_widget_writes_the_one_key_and_syncs_the_other` |
| M18 | 壞頁狀態改成靜默退回預設 | `TestLabels::test_unknown_label_and_id_fail_loud` |
| M19 | app 不再呼叫 `_nav4_reconcile` | `test_s5_reconcile_is_called_with_the_dispatch_table` |
| M20 | 導覽標籤洩漏 legacy 字樣 | `TestBoundary::test_no_legacy_wording_in_any_string…` |
| M21 | 新模式分支拿掉免責聲明 | `test_s2_default_branch_…`（footer 呼叫） |
| M22 | CSS 拔掉 print 隱藏 | `TestCss::test_desktop_hides_the_bottom_bar_and_print_hides_it_everywhere` |
| M23 | CSS 拔掉底部列 safe-area | **首跑 GREEN（守衛太弱，只查窄螢幕區塊任一處有 env()）→ 已加強為檢查列本身的 padding → RED** |
| M24 | CSS 拔掉主內容 padding-bottom | `TestCss::test_fixed_bottom_bar_only_inside_the_narrow_media` |
| M25 | 導覽元件壞掉時不紅態 | **首跑 GREEN（`主導覽` 錯誤另由主區隔離器產生，掩蓋了側欄紅框缺失）→ 已加強為檢查 `at.sidebar.error` → RED** |
| M26 | 兩導覽 widget 其一預填值分叉（SSOT 分叉） | `TestSingleSsot::test_picking_on_either_widget_…` |

26 項突變全數轉紅（M23／M25 首跑漏網，已補強守衛後重跑轉紅；突變在複製的工作樹內執行，未動 repo）。每項以 `pytest -x` 停在第一個失敗，故上表只列首個抓到的測試。
