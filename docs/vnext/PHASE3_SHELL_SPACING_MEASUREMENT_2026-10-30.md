# Phase 3 步驟 3：站殼間距內部量測報告（只量測，不改）

- **日期**：2026-10-30　**依據**：Migration Plan §16.2 步驟 3、線框 §3.11、`docs/DECISIONS.md` DEC-115（站殼：先內部實測；~~局部變更內部自決，整體 layout 變更才送客戶並附推薦方案~~ → 📌 2026-10-30 QA 輪更正（有意識的更正，不是漏刪）：**DEC-115 本文（`docs/DECISIONS.md` 站殼間距條）只寫「先內部實測…若屬整體 layout 變更再送客戶裁示；本 DEC 不核准任何站殼改動」**；「局部變更內部自決」**不是 DEC-115 原文**，僅見於 Migration Plan §16.2 的轉述，本檔初版把轉述當成 DEC 原文引用，特此更正）
- **範圍**：`src/`、`tests/`、`app.py` **0 diff**。唯一新增＝本檔＋`tools/phase3_measure/*.js`（量測腳本，不被 app／test import）。
- ⚠️ **揭露（`CLAUDE.md` §-2 規則 6）**：本檔初版為單組量測與判定；📌 2026-10-30 QA 輪：像素值已有**兩組 QA 獨立重現**（見 §7，含候選 R 實跑 135.19），「局部／整體」判定**已被 AI 總管改判**（見 §5）；影響面推論（z60、受鏈、`:has()` 支援度）仍屬待驗事項，不得當前提。

## 1. 量測方法與限制

| 項 | 內容 |
|---|---|
| 工具 | Playwright 1.63.0＋chromium-1243（`/opt/pw-browsers`），`getBoundingClientRect`／`getComputedStyle` 直接量真實 DOM |
| 視窗 | 1440×900、390×844（無 DPR 縮放） |
| Streamlit | 1.59.2（本機實跑；`requirements.txt` floor 1.56，**1.56～1.58 未量**） |
| 啟動 | `streamlit run app.py --server.headless true`，**無 secrets、無外網資料**；頁面為「冷啟動／尚未載入」狀態（殼與資料狀態無關，H2 y 在冷／熱相同＝契約原敘述，**熱態未實測**） |
| 字型 | 沙箱只有 1 個 CJK／Noto 類字型；字寬可能與使用者機器不同。**垂直間距由 padding／gap 決定、與字寬無關**；僅站標列高（31.2px）與 line-height 有字型相依性 |
| 候選 CSS | 以 `page.addStyleTag` 在瀏覽器內假裝套用，**未寫入任何 repo 檔**；各候選為**單點量測**，非多次平均 |
| 未驗 | Safari／Firefox（`:has()` 支援度另述）、手機實機、Streamlit Cloud、列印版面、側欄展開／收合各狀態的全組合 |

腳本：`tools/phase3_measure/measure_shell.js`（基本量測＋截圖）、`measure_children.js`（主區第一層子節點 y／高／gap）、`measure_variants.js`（候選 CSS 前後對照）。用法：`NODE_PATH=/opt/node-tools/node_modules node tools/phase3_measure/<檔> http://localhost:8599`。

## 2. 實測 px 表（V0＝現況）

### 2.1 頁面 H2 起點（nav4 預設模式）

| 視窗 | `stHeader` | `stMainBlockContainer` padding-top | 站標列 top | 站標列高 | 頁面 H2「📊 市場」y | H2 以下第一屏剩餘 |
|---|---|---|---|---|---|---|
| 1440×900 | 60px（absolute 覆蓋層） | **96px**（Streamlit 預設 6rem） | 128 | 31.2（內層 div 47.2 含 padding 4/8） | **223.2**（24.8% 屏高） | 676.8px（75.2%） |
| 390×844 | 60px | 96px | 128 | 31.2 | **223.2**（26.4%） | 620.8px（73.6%） |

**契約／線框「H2 起於 y≈223，桌／手皆是」＝實測成立（223.2）。** 但線框 §3.11 預估「B 方案約可收 40～50px」與實測拆解不同，見 2.2。

### 2.2 y=223.2 的完整拆解（桌機＝手機，同一結構）

主區第一層為 flex column，`row-gap=16px`。**零高度元素每個仍吃 16px gap**：

| # | 元素（自上而下） | y | 高 | 說明 |
|---|---|---|---|---|
| — | `stMainBlockContainer` padding-top | 0→96 | 96 | Streamlit 預設；header 只佔 60 → **多出 36px 餘量** |
| 1 | `st.markdown(<style>…)`（`app.py` 全域 CSS） | 96 | 0 | 零高度，仍＋16 gap |
| 2 | `st.markdown(PRINT_CSS)` | 112 | 0 | 零高度，＋16 gap |
| 3 | **站標列** `📊 台股 AI 戰情室 v3.0` | 128 | 31.2 | `app.py` 主標題，兩模式共用 |
| 4 | nav4 `NAV4_CSS` 的 `st.markdown(<style>)` | 175.2 | 0 | 零高度，＋16 |
| 5 | `stLayoutWrapper`（`st-key-nav4_bottom` 容器） | 191.2 | 0 | 桌機 `display:none` 只作用在**內層**，外層 wrapper 仍佔 1 個 gap；手機為 `position:fixed` 亦 0 高 |
| 6 | 另一個 `<style>` 容器 | 207.2 | 0 | 零高度，＋16 |
| 7 | **頁面 H2** | **223.2** | 59.2 | |

算式：96＋(16×2)＋31.2＋(16×4)＝**223.2**。可歸類：**padding-top 餘量 36px**（96−header 60）＋**零高度 `<style>` 容器造成的 gap 共 64px**（元素 1、2、4、6 各 16；元素 5 的 16 為 wrapper，另計）。**站標列本身（31.2px）並不是主因。**

### 2.3 候選 CSS 前後對照（H2 y；括號＝相對現況）

| 候選 | 1440×900 nav4 | 390×844 nav4 | 說明 |
|---|---|---|---|
| V0 現況 | 223.2 | 223.2 | |
| V1 padding-top 96→**60**（＝header 高） | 187.2（−36） | 187.2（−36） | 純 padding，站標緊貼 header 下緣（站標文字 top≈64） |
| V2 padding-top 96→**72** | 199.2（−24） | 199.2（−24） | 留 12px 呼吸 |
| V3 只隱藏「僅含 `<style>` 的 element-container」 | 159.2（−64） | 159.2（−64） | 不動 padding；站標 top 100 |
| V4 = V1＋V3 | 123.2（−100） | 123.2（−100） | 加成性與 V1、V3 單獨值吻合（−36−64） |
| V5 = V4＋桌機隱藏 `st-key-nav4_bottom` 外層 wrapper | 107.2（−116） | 123.2（−100，手機該 wrapper 為 fixed，無差） | 桌機專屬再 −16 |
| **建議 R = padding-top 72＋V3**（由 V2、V3 加成推算，**未單獨實跑**） | ≈135.2（−88） | ≈135.2（−88） | 見 §4 |

H2 以下第一屏剩餘空間：V0 677／621px → V1 713／657 → R 765／709（≈85%／84%）→ V4 777／721。

**視覺驗證**：V4 套用後截圖（390×844）站標、H1 與卡片正常；`<style>` 容器被 `display:none` 後樣式仍生效（`stSidebar` 背景 `rgb(22,27,34)`、字色不變，前後一致）。手機底部固定四按鈕列不受影響。

### 2.4 `?legacy=1`

| 視窗 | 站標列 top／高 | `stMainBlockContainer` padding-top | 第一個內容（總經指南針 expander）y |
|---|---|---|---|
| 1440×900 | 128／31.2 | 96px | 231.2；`st.tabs` 頂 359.2 |
| 390×844 | 128／31.2 | 96px | 第一個 tab 列 y≈436 |

legacy 與 nav4 的站標列 y（128）、padding-top（96）、元素 1～3 完全相同；**legacy 無元素 4～6**（nav4 專屬），故其 H2 前較短。

## 3. 選擇器歸屬：legacy 是否共用？

| 造成留白的來源 | 所在 | nav4 | legacy | 結論 |
|---|---|---|---|---|
| `[data-testid="stMainBlockContainer"]` 的 padding-top 96px | **Streamlit 預設**（repo 內 `grep` 全 repo `.py` 無任何 `padding-top` 覆寫此元素；`src/ui/render/print_css.py` 明言不動它） | ✔ | ✔ | **共用**；全域改＝動 legacy |
| 站標列 `<div … font-size:22px …>` | `app.py` 第 651 行，**無條件**輸出 | ✔ | ✔ | **共用**；改字級／padding 必動 `app.py` |
| 元素 1、2（`<style>`／`PRINT_CSS` 容器） | `app.py` 全域 `st.markdown` | ✔ | ✔ | 共用 |
| 元素 4～6（`NAV4_CSS`、`st-key-nav4_bottom` wrapper） | `src/ui/views/shell_nav4.py::render_bottom_nav`（僅 nav4 路徑 late import；legacy 連 import 都不做） | ✔ | ✘ | **nav4 專屬** |
| `.streamlit/config.toml` | 僅 theme／server，**無任何留白設定** | — | — | 與留白無關 |
| `shared/ia_nav4.py` | 純字串常數，無 CSS | — | — | 與留白無關 |

**關鍵結論**：造成留白的兩個主因（Streamlit 預設 padding、`app.py` 站標列）**legacy 與 nav4 共用同一組選擇器**。要做到「`?legacy=1` 逐 byte 不變」，覆寫 CSS 必須**只從 nav4 路徑注入**（`shell_nav4.py` 的 `_CSS_TEMPLATE`），不能寫在 `app.py`（兩模式都會載入）。實測驗證：以 V1 全域套用時 legacy 同樣上移 36px（`st.tabs` 359.2→323.2），證明共用；只要該 CSS 不出現在 legacy 路徑就不會影響它（nav4 專屬注入點＝既有的 `render_bottom_nav`，legacy 從不呼叫）。

## 4. 最小改動方案（只在 nav4 模式生效）

**R：在 `src/ui/views/shell_nav4.py::_CSS_TEMPLATE` 加兩條規則（nav4 專屬注入，不動 `app.py`、不動 legacy）**

```css
/* 站殼間距（Phase 3 步驟 3 量測結論；僅 nav4 模式注入） */
[data-testid="stMainBlockContainer"]{padding-top:72px !important;}   /* 96→72，仍高於 stHeader 60px */
[data-testid="stMainBlockContainer"] > [data-testid="stVerticalBlock"] > [data-testid="stElementContainer"]:has([data-testid="stMarkdownContainer"] > style:only-child){display:none !important;}
```

- **可收**：H2 223.2 → ≈135.2（**−88px**，約佔屏高 9.8%／10.4%）；若 padding 取 60 則 −100。
- **不改**：站標字級／文字／`PAGE_LABELS`／導覽語意／側欄／底部列／legacy 入口；沒有任何元件新增、刪除、換位。
- **不選**：改站標列本身（需動 `app.py`，進 z60 且 legacy 共用，風險高、收益僅約 8px）；併站標進頂欄（線框 §3.11 已移除選項 C，屬殼／IA 變更）。
- **必須同步的守衛**：
  - `tests/test_nav1_shell_nav4.py::TestCss`：現有斷言「`display:none` 不得出現在 `@media` 之外」（CSS 失效降級良性）→ 第二條規則是**無條件** `display:none`，會紅燈。兩個處置：把兩條都包進 `@media (min-width:0px)`（無意義）不可取；建議**改斷言**為「`display:none` 只允許命中 `stElementContainer` 且僅限 `<style>` 純容器的規則，導覽本體不得被藏」，並新增斷言 padding-top ≥ 60（不得低於 `stHeader` 高度）。屬測試改動，**需獨立 QA 看這個放寬是否合理**。
  - 只動 padding-top（不含第二條）則無此衝突，是更保守的子集（H2 → 199.2，−24）。
- **影響面**：
  - **z60 `_BASE_DIGEST`**（`tests/test_batch_z60.py::TestOldFilesUntouched`）：指紋範圍＝`src/ui/{tabs,etf,pages,render}/**/*.py`＋`app.py`（91 檔）。`src/ui/views/shell_nav4.py` **不在範圍內** ⇒ 方案 R **不需**改 `_BASE_DIGEST`。若改走 `app.py` 路線才需。
  - **受鏈守衛**：Plan §5／§12.2 列的還原鏈檔為 `page_*.py`、`risk_cap_gate.py`；`shell_nav4.py` 不在其中（`grep shell_nav4` 僅見於 `test_nav1_*`、`test_boot_import_smoke`、`test_uit_target_page` 的 import 隔離守衛）。這是 grep 結論，**開工時須以當時 main 重測**。
  - **四頁 Gate**：四頁第一屏整體上移同一常數（−88px），頁內相對版面不變；但**所有頁的第一屏像素位置都變**，須對四頁各做 Visual Fidelity Gate §5 例外流程的前後截圖比對；`page_css('dark'|'light')` sha 不受影響（未動頁面 CSS）。
  - **既有測試**：`test_nav1_shell_nav4`（見上）；`test_boot_import_smoke`／`test_nav1_app_routing` 的 import 隔離不受影響（不加 import）。
  - `:has()` 相依：Chrome 105+、Safari 15.4+、Firefox 121+；不支援時退化＝規則不生效、版面回到現況（良性降級）。
- **風險**：
  1. 依賴 Streamlit 非公開 `data-testid`（`stMainBlockContainer` 為 shell_nav4 既有先例；`stElementContainer`／`stMarkdownContainer`／`stVerticalBlock` 為新增依賴）；僅量過 1.59.2，floor 1.56 未驗。
  2. padding 取 60 時站標緊貼 header（文字 top≈64），Deploy／選單按鈕與站標視覺間距縮小；故建議 72。
  3. `:only-child` 條件下若 Streamlit 日後在 markdown 容器內插入其他子節點，規則停止命中（良性失效）。
  4. 未驗：站標下的 `st.warning`／橫幅出現時（頁面內容更長）、側欄展開動畫、列印。

## 5. 判定：局部或整體 layout 變更？

~~**判定：局部變更（內部自決，不送客戶）——單組判斷，待獨立 QA 複核。**~~
**📌 2026-10-30 AI 總管判定（有意識的更正，不是漏刪；決策者：AI 總管，依 DEC-115 的「整體 layout 變更才送客戶」門檻）**：
**AI 總管判定：屬整體 layout 變更**——nav4 全站每頁第一屏統一上移 88px（H2 y 223→約 135；H2 以下第一屏可用空間約 75%→約 85%）。依 DEC-115 **送客戶裁示並附推薦方案 R**（見下）；實測前後並排示意：H2 y 223.2→≈135.2、剩餘第一屏 75%→≈85%。

**舊判定與其理由（保留）**：初版（單組）判為「局部」，理由——方案 R 只改 `padding-top` 與隱藏「不含可見內容的 `<style>` 容器」；0 個可見元件新增／刪除／換位；不改 `PAGE_LABELS`、導覽殼語意、側欄、底部列、legacy 入口（契約 §19 站殼註記的 ⛔ 範圍皆未觸及）；`?legacy=1` 因只從 nav4 注入而逐 byte 不變；四頁以同一常數整體上移屬「間距」而非「版面結構」。**這些事實仍成立。**
**為何被權衡掉**：改動雖不增減元件，但**每一頁第一屏的所有內容位置都被統一移動 88px**（約 10% 屏高），客戶眼睛看到的版面位置全面改變；這正是 `CLAUDE.md` v3 §03-2 ①「版面佈局異動」與 §-1.5.A-8「改變設計（非修正錯誤）」的射程；且初版自己也承認其「局部」判定要靠一條 DEC-115 **原文沒有**的「局部內部自決」才站得住（見檔首更正）。判不準時取嚴：送客戶。

**引用來源的更正**：「局部變更內部自決」**不是 DEC-115 本文**。DEC-115 本文只有「先內部實測，取得實際像素差與最小改動方案後，若屬整體 layout 變更再送客戶裁示；本 DEC 不核准任何站殼改動」。該句僅見於 Migration Plan §16.2 步驟 3 的轉述（Plan 另有「~~局部也須先拍板~~」被劃線的舊句，見該處）。線框 §3.11 第 2 點（rev2）「量到真值後才另送客戶一題」與 Plan 轉述的出入，因本次改判為整體而**不再衝突**——一律送客戶。

**送客戶的推薦方案（總管推薦，附理由）**：推薦 **R**（nav4 專屬注入 `padding-top:72px`＋隱藏 style-only 容器；H2 y ≈135、第一屏可用約 85%；不動 `app.py`、不動 z60 指紋、`?legacy=1` 逐 byte 不變）。理由：收益最大（−88px）且不增減任何可見元件、風險可退化（`:has()` 不支援時回到現況）。替代：**只做 padding 96→72（−24px）**，更保守、無守衛衝突；**不做（維持現況）**亦可。實作需另開 PR（nav4 專屬 CSS＋測試放寬＋四頁前後截圖），**客戶裁示前一行 `src/` 都不改**。

## 6. 回報摘要（給總管）

1. **實測**：H2 y＝223.2（1440／390 皆同）；拆解＝padding-top 96＋零高度 `<style>` 容器的 flex gap 共 64＋站標列 31.2＋其餘 gap；站標列本身不是主因。
2. **最小改動**：nav4 專屬注入 `padding-top:72px`＋隱藏 style-only 容器 → H2 ≈135（−88）；只做 padding 則 −24。不動 `app.py`、不動 z60 指紋。
3. **legacy**：主因（Streamlit 預設 padding、`app.py` 站標列）與 nav4 共用；僅 nav4 專屬注入可保 legacy 逐 byte 不變。
4. ~~**判定**：局部（內部自決），附兩個灰區與一個需改的既有守衛（`display:none` 位置斷言）。~~ → **📌 2026-10-30 改判：整體 layout 變更，送客戶裁示並附推薦方案 R（見 §5）**；仍需改的既有守衛（`display:none` 位置斷言）不變。

## 7. QA 獨立重現（2026-10-30 QA 輪）

> 以下為 AI 總管派出的兩組獨立 QA 的回報；**本檔作者未重跑這些量測**，數值照 QA 回報轉錄（依 §-2 規則 6，只能當 QA 回報，非作者自驗）。

- 兩組 QA 各自以 `tools/phase3_measure/*.js` 對 Streamlit 實跑，重現 §2 的實測值：V0 H2 y＝223.2（1440／390 皆同）、拆解算式 96＋16×2＋31.2＋16×4＝223.2、V1／V2／V3／V4 的差值與本檔 §2.3 吻合。
- **候選 R（padding-top 72＋隱藏 style-only 容器）QA 實跑 H2 y＝135.19**（本檔初版的 ≈135.2 為加成推算、未單獨實跑；此為首次實跑值，與推算差 0.01px，在量測誤差內）。H2 以下第一屏剩餘約 85%。
- 限制不變：Streamlit 1.59.2 實跑；1.56～1.58 未量；冷啟動狀態；沙箱單一 CJK 字型；Safari／Firefox／實機未驗。
