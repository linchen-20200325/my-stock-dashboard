# New UI2 手機抽屜：A／B／C 方案驗證報告（2026-11-04，執行 AI，唯讀 repo）

> 單組結論，沒有第二組獨立複驗。範圍：Chromium headless（Playwright 1.64，Chromium 153，`is_mobile`+touch 390×844、桌機 1440×900）× Streamlit 1.59.2（系統）與 1.56.0（`/tmp/v156`）。
> iOS Safari／Android 真機／Streamlit Cloud（含 Manage app）／VoiceOver／TalkBack 一律未驗。repo 零修改（原型與副本全在本資料夾）。
> 基準說明：本機 repo HEAD＝df163827（含抽屜線框 docs）；任務寫的 f106a6af 在本 checkout 不是 HEAD 的祖先，副本取自 HEAD（git archive）。

## 0. 先講最重要的三個發現

1. **C 案純 CSS 做不到 Esc 與焦點回 ☰（實測確認，兩版皆然）**：Esc 無作用；開啟後焦點留在 ☰、關閉後掉到 BODY。B（session 控制）同樣沒有 Esc、焦點不回。A（原生 sidebar）也沒有。
2. **「零自訂 JS」其實有一條路：HTML Popover API 當狀態載體**（`c_pop`）。`popover`／`popovertarget`／`commandfor`／`command`／`aria-expanded` 屬性在 `st.markdown(unsafe_allow_html=True)` 兩版都**不會被 sanitizer 剝除**（`<script>`、`onkeydown`、`onclick`、`autofocus` 會被剝或不執行）。以 `<button popovertarget>` + 隱形 `<div popover>` 當開關狀態，CSS 用 `:has(#pop:popover-open)` 顯示真正的 Streamlit 抽屜：**Esc 原生可關（1.56／1.59 皆 ✓）、點遮罩原生 light-dismiss ✓、切頁自動收合 ✓、Tab 下一格即進抽屜 ✓**。仍缺：開啟後焦點不會自動進抽屜、焦點在抽屜內按 Esc 後焦點掉 BODY（不回 ☰）。→ 條件 (4) 可零 JS 達成，條件 (5) 的「開啟後焦點進抽屜、關閉後回 ☰」**零 JS 做不到**。
3. **線框的「☰ 列 8px＋44px」會讓 p2_nav_margin_160 失守**（客戶 (19) 門檻、未達要停手）：以真實 harness 量得基準 stale 181.6／unavailable 162.5；☰ 以 top:8px 並把 padding-top 加 8px → **173.6／154.5（unavailable <160 ✗）**；padding-top 4rem → 161.6／142.5 ✗。**☰ 貼齊左上角（top:0,left:0、44px 高；既有 `.block-container padding-top:2.75rem=44px` 不變）→ 181.6／162.5，與基準逐位相同 ✓**（1.56／1.59 皆然；內容不被 ☰ 遮到，見截圖）。施工線框須改成「☰ 占既有 44px 頂部保留帶」。

## 1. 三方案 × 九條件

A＝原生 `st.sidebar`（+最少 CSS）；B＝session 控制自訂抽屜（`ui2_drawer_open`）；C＝CSS-only checkbox 抽屜。
另列兩個「補強版」：**C+JS**＝C + `st.html(unsafe_allow_javascript=True)` 約 25 行（`c_js2`）；**C-pop**＝C 改用 Popover API 當狀態（零 JS，`c_pop`）；**C-pop+JS**＝C-pop + 約 15 行 JS 只管焦點（`c_pop_js`）。

| 條件 | A 原生 sidebar | B session 抽屜 | C CSS-only | C-pop（零 JS） | C+JS（建議） |
|---|---|---|---|---|---|
| (1) ☰ 開關 | ⚠️ 預設 ☰ **看不見**（repo 的 `stToolbar{display:none}` 連 ☰ 一起藏，`a_plain_*`）；還原 toolbar 後 ☰ 僅 28×28、收合鈕 32×28，開關 ✓ | ✅ ☰＋遮罩＋✕ 皆可（遮罩鈕需修 CSS 才吃到整面，已修） | ✅ | ✅ | ✅ |
| (2) 四頁可切 | ✅（還原 toolbar 後） | ✅ 四頁 | ✅ 四頁 | ✅ | ✅ |
| (3) 切頁自動收合 | ❌ 兩版皆不收；`set_page_config(initial_sidebar_state)` 翻轉法無效（第 1 次嘗試失敗，已換方向） | ✅（on_change 設旗標，每次開關一次 rerun） | ✅ 但靠「包裝標籤隨頁輪替→React 重建」hack（兩版、點擊與方向鍵皆 ✓） | ✅ 同 hack＋點外面原生 light-dismiss | ✅ 同 C |
| (4) Esc 關閉 | ❌ | ❌ | ❌（兩版實測） | ✅ 原生（兩版） | ✅（需 JS） |
| (5) 焦點／SR | ❌ 開啟後焦點 BODY；☰ `aria-label=""` | ⚠️ 焦點留在 ☰、不進抽屜、不回；SR 結構正常（button／radiogroup／disabled） | ⚠️ ☰＝`switch "主選單" [checked]` ✓、關閉時抽屜不在 a11y tree ✓；焦點不進、不回 ❌ | ⚠️ Tab 一格進抽屜 ✓；焦點在抽屜內 Esc→BODY ❌；`aria-expanded` 靜態值會說謊（須移除或由 JS 更新），隱含 expanded 狀態在 Chromium aria_snapshot 看不到（未驗 SR） | ✅（Chromium）開啟→焦點進當前頁 radio；Esc／切頁後→焦點回 ☰（點擊與鍵盤、兩版）。殘留：無 focus trap（Tab 會穿到遮罩後的頁面）；VoiceOver／TalkBack 未驗 |
| (6) Google 區 disabled 固定占位 | ✅ 可做 | ✅ 靜態占位（`role=button aria-disabled`＋「⬜ 尚未登入」＋「登入與 Sheet 操作尚未開放」），不讀 `ui2_account`／`ui2_dev`／query | ✅ 同左 | ✅ | ✅ 原型即此做法；字樣是否改「尚未提供」＝客戶 J-6 |
| (7) 手機首屏與 160 餘裕 | ⚠️ 未量（需重做頂部） | ✅ 條件式：☰ 貼齊 44px 頂部保留帶 → 181.6／162.5（量測證據見 §3）；8px 版 ❌ | ✅ 同左 | ✅ 同左 | ✅ 同左（`c_js2` 實測 181.6／162.5，兩版） |
| (8) 桌機 11rem rail | ⚠️ 需覆寫內部 testid（寬 176 可行，但 `aria-expanded=false` 與實況不符、依賴 `stSidebar*` 內部名） | ✅ 176px、4 項、☰ 隱藏、無水平捲動 | ✅ 同左 | ✅ | ✅ |
| (9) 不宣稱解決 Manage app | ⚠️ 未驗 | ⚠️ 未驗 | ⚠️ 未驗 | ⚠️ 未驗 | ⚠️ 未驗 |

(9) 說明：沙箱完全無法重現 Manage app。設計上 ☰ 在左上、無底部固定列、內容底部保留量維持；**這是推論，不是證明**，須 Cloud／Android 真機驗收。

## 2. 其他方案（st.popover／st.dialog／st.navigation）

| 方案 | 實測 | 結論 |
|---|---|---|
| `st.popover("☰")`（`mini_pop.py?v=pop`） | 1.59：`aria-expanded`／`aria-haspopup=dialog` ✓、Esc ✓、焦點回按鈕 ✓；1.56：無 aria-expanded、Esc 後焦點 BODY。面板是 320px 浮動卡（非左抽屜、不固定）、**切頁不關**（兩版） | 不採 |
| `@st.dialog`（`?v=dlg`） | Esc ✓、焦點進對話框／關閉後回 ☰ ✓（兩版）、`st.rerun()` 換頁後關閉 ✓。CSS 改成左抽屜：**1.56 成功、1.59 版面疊壞**（兩版 DOM 不同：react-aria vs BaseWeb；只試 1 次，不再追）。桌機仍需第二份 radio（同 key 會重複 widget）、開啟＝一次 rerun | 不採；只當 a11y 行為參考 |
| 原生 `<dialog commandfor>`（靜態頁驗證） | 焦點進入 ✓、Esc ✓、焦點回 invoker ✓，**零 JS** —— 但內容只能是原始 HTML，Streamlit radio 放不進去；改用連結＝整頁重載、session 重置 | 不採（對 iOS Safari Invoker Commands 支援度亦未驗） |
| `st.navigation` | 前人實測：變 URL 路由、sidebar 不自動收合；會改寫既有導覽測試 | 不採（本輪未重測） |

## 3. 實測資料

### 3.1 核心行為（`results/*.json`，腳本 `proto/probe_core.py`）
| 變體 | 開啟後焦點 | Esc | Esc 後焦點 | 切頁收合 | 切頁後焦點 | 備註 |
|---|---|---|---|---|---|---|
| c_hack（C） | ☰（checkbox） | ✗ | 不變 | ✓ | BODY | 1.56／1.59 同 |
| b_sess（B） | ☰（button） | ✗ | 不變 | ✓ | BODY | 1.56／1.59 同 |
| c_pop（C-pop） | ☰（tap）；Tab→radio | ✓ | tap 路徑留在 ☰；從抽屜內按→BODY | ✓ | BODY | 1.56／1.59 同 |
| c_js2（C+JS） | **進 radio** | ✓ | **回 ☰** | ✓ | **回 ☰（兩版、點擊與方向鍵）** | 見 §4 |
| c_pop_js | 進 radio | ✓ | 回 ☰ | ✓ | 鍵盤 ✓；點擊切頁 → BODY（1.59／1.56 皆） | 觸控點擊路徑未回焦 |
| c_js_c1（components.v1.html iframe JS） | 進 radio | 焦點在 iframe 時 ✗ | — | ✓ | — | iframe 進 Tab 順序（`IFRAME.stIFrame`，無 title）→ 不採 |
首次開啟時間（本機、FAKE）：C ≈0.17 s（含 .2s 動畫）、B ≈0.26 s（含一次 rerun）；Cloud 往返與 Real feed 重讀未量。reduced-motion：`emulate reduced_motion=reduce` 時抽屜 `transition-duration=0s`（✓，Chromium）。

### 3.2 手機首屏餘裕（`proto/probe_margin.py`＋真實 `tests/ui2_viewport/measure_viewport.py` 基準 `results/harness_pristine*`）
真實 harness 基準（pristine，70 狀態 70 過）：stale 181.6／unavailable 162.5／loaded 205.5（＝距 791 線）。
| ☰ 擺法 | stale | unavailable | 判定 |
|---|---|---|---|
| top:0,left:0；padding-top 2.75rem 不變（`c_js2`/`c_pop_js`/`b_sess`，1.56＋1.59） | 181.6 | **162.5** | ✅ 與基準逐位相同 |
| top:.5rem；padding-top 3.25rem（線框「8＋44」） | 173.6 | **154.5** | ❌ <160 |
| top:.5rem；padding-top 4rem | 161.6 | **142.5** | ❌ |
注意：標記元件放在內容之後、CSS 併入既有 CSS 區塊（沿前人 QA 結論）；`st.html` JS 元素高 0。若移到內容前仍須重量。

### 3.3 JS 能力與副作用（`proto/t1_caps.py`）
- `st.markdown(unsafe_allow_html)`：`<script>` 存在於 DOM 但**不執行**；`onkeydown`／`onclick`／`onerror`／`autofocus` 被剝；`input`／`label for`／`role`／`aria-*`／`popover`／`popovertarget`／`commandfor`／`closedby`／`tabindex` 保留（1.56＋1.59）。
- `st.html(...)`：預設剝 script；`unsafe_allow_javascript=True` **在主文件執行**（`window` 即頁面，無 iframe 隔離；官方參數，floor 1.56 即有）。
- `components.v1.html`：srcdoc iframe，sandbox 含 `allow-same-origin allow-scripts`，可 `window.parent`（可行但會進 Tab 順序、Esc 在 iframe 焦點時漏接）。
- `components.v2`：JS 在主文件執行（可行，未深測）。
- 副作用（`proto/probe_js_fx.py`）：`st.html` 的 script **每次 rerun 重新執行**（6 次切頁後執行 7 次），以全域旗標守衛後監聽只註冊一次 ✓；Esc 在抽屜關閉時無副作用；html 元素高 0、無 iframe；JS 只依賴自家 class（`.ui2-dr-toggle`、`.st-key-ui2_nav`、`[data-ui2-page]`），**不依賴 Streamlit 內部 testid**。

### 3.4 既有測試／守衛衝擊（在副本 `drawer_verify` 跑 `tests/test_ui2_*.py` 共 1263 通過／37 失敗／3 xfailed；基準副本以 -x 跑無失敗）
- **C 類（含 JS）會紅的**：`test_ui2_batch2.py::test_w1_mobile_nav_is_bottom_fixed_53px`、`::test_w1_desktop_nav_is_left_column`（區塊切片假設）、`::test_w1_current_page_is_marked_beyond_color`（要 `border-top-color`）、`test_ui2_batch3.py::test_nav_margin_content_bottom_reserve…`（要特定 padding-bottom 字串）＝**4 個 CSS 字串測試需同 PR 改寫**。`test_ui2_contract_teeth_pending`（ui2_nav＋position:fixed）、`test_ui2_p2_primary_slot`、`test_ui2_real_feed`（ALLOWED_UI2_WRITES）、`test_ui2_registration_and_boot` **未紅**。AppTest：`at.radio(key="ui2_page")` 兩版皆可切頁、無例外。**開關狀態 AppTest 驗不到**（client 端），須 Playwright lane（skipped≠passed）。
- **B 會多紅的**：`test_g9_*`（`check_not_a_producer` 擋 `session_state.update()`——原型用 lambda 觸發，約 35 個參數化案例全紅，因 `clean` 斷言失敗）＋新 key `ui2_drawer_open` 須擴 `ALLOWED_UI2_WRITES`＋`measure_viewport` 的 4 格導覽判定器。B 另有 AppTest 可測開關旗標（open→True、close→False 兩版 ✓）的優點。
- **目前沒有任何既有守衛禁止 `st.html(unsafe_allow_javascript=True)`、raw `<input>`／`popover` 屬性** → 這是新增攻擊／回歸面，必須新增守衛（見 §5）。
- `measure_viewport` 的 `nav_fixed_four`／`first_screen_above_nav`／導覽點擊流程需改寫（它用 `.st-key-ui2_nav [role=radiogroup] > label` 直接 click；抽屜收合時不可見，harness 對 drawer 變體逾時）。

## 4. 建議

**建議：C+JS（`c_js2`）——「C 抽屜（同一份 `ui2_nav` container＋`ui2_page` radio＋桌機同 DOM 變 rail）＋ `st.html(unsafe_allow_javascript=True)` 約 25 行」，列為『新 JS＋安全白名單 Gate』。**
理由：只有這一個變體在 1.56＋1.59 同時達成 (1)(2)(3)(4) 且 (5) 的「進抽屜／回 ☰」（Chromium 實測）；零新 session key、不動 `ALLOWED_UI2_WRITES`／G9；`ui2_page` radio 與既有 AppTest 不動；JS 不依賴 Streamlit 內部 DOM；☰ 貼齊 44px 保留帶可守住 160 餘裕。
不因成本最低選 C：純 C（無 JS）在條件 (4)(5) 失敗，**不可宣稱滿足客戶最低條件**。
**若治理不接受任何自訂 JS**：退而求其次用 **C-pop（零 JS）**，可滿足 (1)(2)(3)(4)，(5) 只能標「部分」（焦點進／回需 JS，Tab 順序合理）。B 沒有優勢（同樣無 Esc、還要動 G9／白名單／rerun）。A 不可行（(3)(4)(5) 兩版皆失敗、☰ 28px、依賴 `stToolbar`／`stSidebar*` 內部名）。
最小 JS 範圍：`c_js2` 原型＝(a) `keydown Escape`：若 `.ui2-dr-toggle:checked` → 取消勾選、`dispatchEvent(change)`、`focus()` ☰；(b) toggle `change` checked → 260ms 後 focus 當前頁 radio；(c) 觀察 `[data-ui2-page]` 變化且焦點原在抽屜 → 去抖 250ms 後 focus ☰；(d) `window.__ui2drJS2` 旗標防重複註冊。程式見 `proto/patch.py`（`JS_V2`）。
**未解／殘留**：無 focus trap；包裝標籤輪替依賴 React 重建（hack）；`<input>` 存活依賴 sanitizer（現兩版保留，日後版本可能變）；`:has()`／Popover 需 Safari 15.4+／17+（未驗）。

## 5. 是否需要新 JS／白名單／Auth Gate；下一批能否施工
- **新 JS Gate：需要**（C+JS）。最小守衛：AST 只准一處 `st.html(..., unsafe_allow_javascript=True)`、參數須為模組層常數字串（禁 f-string／變數／使用者資料）；JS 字串含禁用清單（`fetch`／`XMLHttpRequest`／`localStorage`／`document.cookie`／`eval`／`window.open`／`postMessage`）；雜湊釘住原文。新增 raw 互動 HTML 白名單（只准抽屜 toggle 一處 `<input>`／`<label for>`）。新增 Playwright 行為測試（開／關／Esc／焦點回／切頁收合／四頁／桌機 rail／1.56＋1.59×FAKE＋Real），先 `xfail(strict)` 同 PR 翻綠。
- **Auth Gate：不需要**（僅靜態 disabled 占位；不讀 `ui2_account`／`ui2_dev`／query）。任何依帳號狀態顯示登入態＝另走 `NUI2-AUTH-CONTRACT-GATE`。
- **能否進入下一批施工**：技術上可行，**須先過 Gate**：① 客戶／治理核准抽屜線框（DEC-134 仍「線框待驗收」）；② 治理明確核准「新 JS Gate」（或改採 C-pop 並接受 (5) 部分）；③ 線框改為「☰ 占既有 44px 頂部保留帶」並重寫 160 餘裕定義（基準＝視窗底扣 53px 帶）；④ J-6 字樣（尚未登入 vs 尚未提供）；⑤ 施工 PR 同批改寫 §3.4 的 4 個 CSS 測試與 harness 判定器（不得只刪）。
- 估計（撰寫組估計、非實測）：實作 1 批（CSS 約 40 行＋標記＋JS 約 25 行＋4 測試改寫＋新 Playwright／守衛），風險中低；token／工時約為「純 C」的 1.3–1.5 倍。

## 6. 未驗項（逐項）
iOS Safari（`:has()`、Popover、`label for` 點擊、`env()`、動態工具列）；Android Chrome 真機；Streamlit Community Cloud 與 Manage app 浮層（含右下遮擋是否影響頁尾、☰ 左上是否被系統列遮擋）；VoiceOver／TalkBack 朗讀與 Popover 隱含 expanded；Real feed 下 B 的 rerun 延遲；`st.navigation(position="top")`；Firefox／WebKit 引擎；Cloud 上 `st.html` JS 是否受 CSP 限制；螢幕閱讀器下 focus trap 缺口的實際影響；prefers-reduced-motion 僅以媒體查詢模擬驗證。

## 7. 檔案
- 原型與腳本：`proto/`（`patch.py` 產生變體殼、`probe_core.py`／`probe_margin.py`／`probe_a11y.py`／`probe_a.py`／`probe_dp.py`／`probe_js_fx.py`、`t1_caps.py`、`mini_*.py`、`at_probe.py`）；結果 `results/`；截圖 `shots/`。
- 重跑：`proto/patch.py`（改寫副本 `src/ui2/shell/{app,css}.py`）→ `proto/restart_all.sh` → `python proto/probe_core.py <variant> <port>`。
- 實驗結束已關閉所有 streamlit／瀏覽器行程。
