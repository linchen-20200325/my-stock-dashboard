# New UI2 手機抽屜：施工前驗證結果（2026-11-04）

> **不授權施工；單組撰寫＋一組獨立複驗；非客戶核准。** 本檔只記錄實驗證據與推薦，不建立第二套規則／SSOT，不改任何 DEC。
> 對應線框：`NEWUI2_MOBILE_DRAWER_TEXT_WIREFRAME_2026-11-04.md`；治理建議：`NEWUI2_P6_DRAWER_INDEPENDENT_REVIEW_2026-11-04.md`。
> 基準：origin/main `e674ee5a`（#1016）。實驗在 repo 副本進行，repo 本體零修改。

## 1. 環境與方法

- Chromium headless（Playwright 1.64／Chromium 153，`is_mobile`＋touch 390×844；桌機 1440×900）。
- Streamlit **1.56.0**（requirements floor）與 **1.59.2**（系統版）各跑一輪。
- 撰寫組單組做原型與量測；**另一組獨立複驗**（重做核心行為、邊界、延遲、margin、既有 harness）。
- **皆非真機。** 未驗項見 §8。

## 2. 方案 × 客戶最低條件九項

A＝原生 `st.sidebar`；B＝session 控制自訂抽屜；C＝CSS-only checkbox 抽屜；C-pop＝C 改用 HTML Popover API 當狀態（零 JS）；C+JS＝C＋`st.html(unsafe_allow_javascript=True)` 約 25 行。

| 條件 | A | B | C | C-pop | C+JS |
|---|---|---|---|---|---|
| (1) ☰ 開關 | ⚠️ 預設 ☰ 看不見（既有 `stToolbar{display:none}`）；還原後僅 28×28 | ✅ | ✅ | ✅ | ✅ |
| (2) 四頁可切 | ✅（還原 toolbar 後） | ✅ | ✅ | ✅ | ✅ |
| (3) 切頁自動收合 | ❌ 兩版皆不收 | ✅（on_change 旗標） | ✅（依 React 重建 hack；依賴 server 往返） | ✅（同 hack；點遮罩原生 light-dismiss） | ✅（同 C） |
| (4) Esc 關閉 | ❌ | ❌ | ❌ | ✅ 原生 | ✅（JS） |
| (5) 焦點進／回 | ❌ 焦點 BODY | ⚠️ 焦點留 ☰、不進不回 | ⚠️ 不進不回 | ⚠️ 部分：Tab 一格進抽屜；抽屜內 Esc 後焦點掉 BODY | ✅ Chromium：開→焦點進當前頁 radio；Esc／切頁→回 ☰。**無 focus trap** |
| (6) Google 區 disabled 占位 | ✅ | ✅ | ✅ | ✅ | ✅（靜態 `aria-disabled`，不讀帳號狀態） |
| (7) 手機首屏 160 餘裕 | ⚠️ 未量 | ✅ 條件式（見 §4） | ✅ 條件式 | ✅ 條件式 | ✅ 條件式 |
| (8) 桌機 11rem rail | ⚠️ 需覆寫內部 testid | ✅ 176px | ✅ | ✅ | ✅ |
| (9) 不宣稱解 Manage app | ⚠️ 未驗 | ⚠️ 未驗 | ⚠️ 未驗 | ⚠️ 未驗 | ⚠️ 未驗 |

## 3. 關鍵發現

1. **純 CSS（C）不可能 Esc、也不可能焦點進出**（兩版實測）。B、A 同樣沒有。不可宣稱純 C 滿足客戶最低條件。
2. **Popover 零 JS 可 Esc 與 light-dismiss**（`popovertarget` 等屬性兩版 sanitizer 皆保留；`<script>`／`onclick`／`autofocus` 被剝或不執行）。缺口：開啟後焦點不自動進抽屜；抽屜內 Esc 後焦點掉 BODY；`aria-expanded` 為靜態值會說謊（須移除或由 JS 更新）；點當前頁也會收合；快速連點被遮罩擋。
3. **C+JS 達成 (1)–(5)**（Chromium）。限制：無 focus trap（Tab 會穿到遮罩後頁面）；`st.html` script **每次 rerun 重跑**，須全域旗標守衛（`window.__ui2drJS2`），**已做變異測試：移除旗標後監聽重複註冊，旗標有效**；JS 在主文件執行、無 iframe 隔離；JS 只依賴自家 class，不依賴 Streamlit 內部 testid。`components.v1.html` iframe 方案進 Tab 順序、焦點在 iframe 時漏接 Esc，不採。
4. **C 與 C+JS 點當前頁不收合；收合依賴 server 往返**（複驗人為延遲 1.5s，實測收合 1.7s）。Popover 路徑點當前頁會收合，與前者行為不一致，施工前需客戶／治理定義預期。
5. **其他方案不採**：`st.popover`（浮動卡、切頁不關）、`@st.dialog`（1.56 可改左抽屜、1.59 版面疊壞）、原生 `<dialog commandfor>`（內容只能是原始 HTML，放不進 Streamlit radio）、`st.navigation`（變 URL 路由、改寫既有導覽測試；本輪未重測）。

## 4. 手機首屏 160px 餘裕（真實 harness，pristine 70 狀態 70 過）

| ☰ 擺法 | stale | unavailable | 判定 |
|---|---|---|---|
| 基準（無 ☰） | 181.6 | 162.5 | — |
| ☰ top:0,left:0、44px 高，占既有 `.block-container padding-top:2.75rem` | 181.6 | **162.5** | ✅ 與基準逐位相同（1.56／1.59 皆然，複驗組同值） |
| 線框原案：☰ top:8px＋padding-top 3.25rem | 173.6 | **154.5** | ❌ <160 |
| top:8px＋padding-top 4rem | 161.6 | **142.5** | ❌ |

→ 線框須由「☰ 列 8px＋44px」改為「**☰ 列 52px／占既有 44px 頂部保留帶**」，並重寫 160 餘裕定義（以視窗底扣 53px 帶為基準）。

## 5. 複驗組指出的原報告誇大／遺漏（三項）

1. **開啟延遲只量首次（C≈0.17s、B≈0.26s）**，未量「切頁→收合」；複驗實測依 server 往返，延遲 1.5s 時收合 1.7s（Real feed 下 B 的 rerun 延遲仍未量）。
2. **「切頁自動收合 ✓」未區分點當前頁**：C／C+JS 不收合，Popover 會收合，行為不一致。
3. **Popover 被讀成接近完整**：未載明 `aria-expanded` 靜態會說謊、抽屜內 Esc 後焦點掉 BODY、快速連點被遮罩擋。

（上列三項為依複驗結果檔 `drawer_qa/res/*.json` 與撰寫組 REPORT 差異整理；若要逐字對應複驗組原文，以 `newui2_drawer_preimpl/writer_REPORT.md` 與 `qa_res/` 對照為準；三項分類為本檔整理者歸納。）

## 6. 既有測試衝擊（撰寫組副本實測：`tests/test_ui2_*.py` 1263 過／37 失敗／3 xfailed）

- **C 類（含 JS）**須在同 PR **改寫** 4 個 CSS 字串測試：`test_ui2_batch2.py::test_w1_mobile_nav_is_bottom_fixed_53px`、`::test_w1_desktop_nav_is_left_column`、`::test_w1_current_page_is_marked_beyond_color`，與 `test_ui2_batch3.py::test_nav_margin_content_bottom_reserve…`；`tests/ui2_viewport/measure_viewport.py` 的 `nav_fixed_four`／`first_screen_above_nav`／導覽點擊判定器須改（抽屜收合時 radio 不可見，對 drawer 變體逾時）。
- **B 類**會觸發 G9 `check_not_a_producer`（`session_state.update()`），約 33 失敗（撰寫組副本實測）＋新 key `ui2_drawer_open` 須擴 `ALLOWED_UI2_WRITES`。
- **不得只刪守衛**；開關狀態 AppTest 驗不到（client 端），須 Playwright lane（skipped 不等於 passed）。
- 目前**沒有任何守衛**禁止 `st.html(unsafe_allow_javascript=True)`、raw `<input>`／popover 屬性 → 新增攻擊／回歸面。

## 7. 推薦與備案（撰寫組＋複驗組一致；非裁示）

- **推薦 C+JS**，列為「**新 JS＋安全白名單 Gate**」，最小守衛：AST 只准一處 `st.html(..., unsafe_allow_javascript=True)`，參數須為模組層常數字串（禁 f-string／變數／使用者資料）；JS 字串禁用清單（`fetch`／`XMLHttpRequest`／`localStorage`／`document.cookie`／`eval`／`window.open`／`postMessage`）＋雜湊釘住原文；raw 互動 HTML 白名單只准抽屜 toggle 一處；Playwright 行為測試（開／關／Esc／焦點回／切頁收合／四頁／桌機 rail／1.56＋1.59）先 strict xfail 再翻綠。
- **若治理不接受任何自訂 JS → C-pop**，條件 (5) 標「部分」。A 不可行；B 無優勢（同樣無 Esc，還要動 G9／白名單）。
- **Auth Gate 不需要**：只有靜態 disabled 占位，不讀 `ui2_account`／`ui2_dev`／query；任何依帳號狀態顯示登入態另走 `NUI2-AUTH-CONTRACT-GATE`。
- **下一批能否施工＝技術可行，但前置條件**：① 客戶／治理核准抽屜線框與新 JS Gate；② 線框改 ☰ 占既有 44px 保留帶並重寫 160 餘裕定義；③ J-6 字樣（#1016 建議 B「⬜ 尚未提供」，客戶尚未裁示）；④ 施工 PR 同批改寫 §6 的測試與 harness，不得只刪。

## 8. 未驗（不得宣稱已解決）

iOS Safari（`:has()`、Popover、`label for`、`env()`）；Android 真機；Streamlit Community Cloud 與 Manage app 遮擋；VoiceOver／TalkBack；Firefox／WebKit；Cloud CSP 對 `st.html` JS 的影響；Real feed 下 B 的延遲。

## 9. 證據位置

`docs/vnext/newui2_drawer_preimpl/`：`writer_REPORT.md`（撰寫組原報告，單組、保留原文含其誇大處）、`qa_res/*.json`（複驗組核心行為／邊界／margin／Popover 原始量測）、`qa_res/harness_base159.log`（Streamlit 1.59 基準 harness 日誌）。原型程式與截圖未入庫；需重現時依 §1 方法重做。
