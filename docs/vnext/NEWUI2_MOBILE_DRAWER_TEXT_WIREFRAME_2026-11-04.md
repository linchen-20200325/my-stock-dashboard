# New UI2 手機左側抽屜導覽：文字線框＋實作可行性比較（2026-11-04）

> **狀態：已過獨立 QA，待 ChatGPT／客戶線框審查；本輪不授權施工**（尚未取得客戶核准）（不授權任何程式／CSS／測試修改；客戶 (20)「本輪不授權 P6 或導航程式施工」；DEC-134「裁示已記錄、線框待驗收、不授權實作」）。
> 本檔是 `NEWUI2_MOBILE_DRAWER_NAV_CONTRACT_2026-11-04.md` Gate 1（先提 390／1440 文字線框）與 Gate 6（自動關閉＋桌機 rail 並存）的回應；**不新增客戶裁示**，只提出推薦與待確認項。
> 任何「已驗」都限於 **Chromium headless（Playwright 1.64、`is_mobile`＋touch 模擬）× Streamlit 1.59.2 與 1.56.0**；**iOS Safari、Android 真機、Streamlit Community Cloud（含 Manage app 浮層）一律未驗**。實驗檔皆在 scratchpad（不在 repo；見附錄），repo 零修改。

## A. 客戶確認的設計（引用，不改寫）

| 來源 | 內容 |
|---|---|
| DEC-134（`docs/DECISIONS.md`；客戶 2026-11-04「好」） | 選 B：**可收合左側抽屜**（四主頁＋Google 帳號入口）；取代「手機只有底部固定四格」的**位置與顯示方式**；四頁、桌機 rail、DEC-129 Account Area、DEC-127 順序、DEC-130 誠實規則**不變**。**未授權**：抽屜像素尺寸、真 OAuth、正式 auth state、資料來源、VM schema、投資語意。 |
| 客戶 (20)（scratchpad `customer_directive_2026-11-02.md` 第 (20) 段摘要） | 手機左上 ☰；展開後 📊 市場／🎯 標的／💼 持股／👤 我的；同一抽屜內有 Google 登入入口；**預設收合、內容維持手機全寬**；不再依賴被 Manage app 遮擋的底部四格；桌機保留固定左側導航與帳戶區。先比較三種實作；線框須處理開／關／切頁／重開、390px 內容寬度與安全區、Manage app 存在時能否操作、登入未接線呈現、Android／iOS／觸控／鍵盤／無障礙、桌機 1440 rail、現有導覽測試與 160px 餘裕如何更新（**不能直接刪守衛**）。 |
| 契約附件 Gate 4／7 | 僅允許「導航殼＋誠實 disabled 登入入口」；⛔ OAuth／session 身分判斷／Sheet／canonical／VM schema／Risk Cap／System Action／Digest；⛔ query／`ui2_dev`／FAKE account 當登入證據（正式 auth＝`NUI2-AUTH-CONTRACT-GATE`，Opus 5.5＋High）。 |
| 兩份線框交界（客戶 (20)） | 抽屜＝**快速登入入口＋簡短狀態**；👤 我的＝完整 Google／Sheet 管理＋資料健康度；**同一 auth truth、不得有兩個主要登入流程**。 |

## B. 實作方案比較（實測為主）

### B.0 實測方法（可重跑）

同一份真實內容（`src/ui2/views` ＋ `get_preview_page_vm`＋repo 的 `CSS`）放進六支最小應用，各自換掉導覽殼；Playwright（Chromium headless，390×844，`is_mobile`＋`has_touch`；桌機 1440×900）對 **1.59.2（預設 venv）與 1.56.0（`/tmp/v156`）各跑一次**。除另註明外兩版結果相同。檔案與腳本見附錄。

### B.1 逐案實測結果

| 案 | 做法 | 實測（390×844；除註明外 1.56／1.59 相同） |
|---|---|---|
| **A 原生 `st.sidebar`**（`e1_sidebar.py`） | `initial_sidebar_state="collapsed"`；radio 放 sidebar | ① 預設收合 ✓（sidebar x=−300）。② ⚠️ **repo 現行 CSS 把 `[data-testid="stToolbar"]` 設 `display:none !important`，而兩版的 ☰ 展開鈕（`stExpandSidebarButton`）都在 `stToolbar` 內 → 直接套用時 ☰ 完全看不見**（bbox 0×0，Playwright 判 not visible）；需另寫例外（只隱藏 `stToolbarActions`／Deploy／MainMenu）才出現。③ 展開＝**覆蓋 300px、不擠壓**（`.block-container` 仍 x=0,w=390）。④ **切頁後不自動收合**（兩版皆 `aria-expanded=true`）。⑤ **Esc 不關**。⑥ ☰ 鈕 **28×28px（<44）、`aria-label=""`（無可及名稱）**；sidebar 本體有 `aria-expanded`。⑦ 桌機預設（collapsed）收合；以 CSS 強制 `width:11rem; transform:none` ＋隱藏收合鈕可變成 176px 固定 rail（兩版皆成功，`.block-container` x=176）——但**依賴 `stSidebar` 等內部 testid**，違背既有 `test_w1_nav_css_does_not_depend_on_streamlit_internal_classes` 的精神。⑧ AppTest：`at.sidebar.radio(key="ui2_page")` 可用（兩版跑過）。 |
| **A＋JS**（`e1_sidebar.py?v=js`；`st.html(..., unsafe_allow_javascript=True)`，兩版皆有此參數） | 以小段 JS 補 Esc／切頁收合 | Esc 收合 ✓（兩版）；切頁後收合：**1.56 ✓、1.59 ✗（本次仍 `aria-expanded=true`）**——行為隨版本不同；且 New UI2 目前**零 JS 先例**。僅列為可行性，不推薦。 |
| **B 自訂抽屜（session 控制）**（`e2_custom.py`） | `st.container(key)` 固定定位抽屜；☰＝`st.button`；遮罩＝`st.button`；`ui2_drawer_open` 存 session；radio `on_change` 關閉 | 預設收合 ✓（`visibility:hidden`，不可 Tab）；☰ 71×44（1.56：77×44）；開啟 **0.36～0.39 s**（每次開／關＝一次完整 rerun）；展開 320px **覆蓋不擠壓**；radio 項 48px 高；**切頁後自動收合 ✓**（0.17～0.19 s）；點遮罩收合 ✓、✕ 收合 ✓、重新開啟 ✓；**Esc ✗**；**關閉後焦點掉到 `BODY`（不回 ☰）**；Tab 順序：遮罩鈕先於抽屜（DOM 順序，需調整）；桌機同一容器變 176px rail、☰ 消失 ✓、無水平捲動。AppTest：`at.button(key=…).click()`、`at.radio(key="ui2_page")` 可驅動，`ui2_drawer_open` 開→關可斷言（兩版）。⚠️ **新增 session key `ui2_drawer_open` 會被 `tests/test_ui2_real_feed.py:503 ALLOWED_UI2_WRITES`（目前 5 個 key）拒絕**，須明列擴充（屬守衛變更）。 |
| **C CSS-only checkbox 抽屜**（`e4_cssonly.py`、`e4b_switch.py`） | `st.markdown(unsafe_allow_html)` 放 `<input type=checkbox role=switch>`＋`<label for>`（☰、遮罩）；抽屜＝**同一個** `st.container(key)` 以 `:has(.toggle:checked)` 控制；零 session key | `<input>`／`<label for>`／`role`／`aria-*` **未被 sanitizer 移除**（兩版）；點 ☰ **即時開啟（無 rerun，350 ms 內已就位）**；展開 320px 覆蓋不擠壓；點遮罩收合 ✓；鍵盤：Tab 到 ☰（checkbox）→ **Space 開／關 ✓** → 再 Tab 進 radio ✓ → ArrowDown 換頁 ✓；**Esc ✗**；焦點回 ☰ ✗；a11y tree：☰＝`switch "主選單" [checked]`，**關閉時抽屜不在 a11y tree**、開啟時＝`radiogroup "導覽"`＋4 radio＋disabled button（`aria_snapshot`）；**切頁後預設不收合**（checkbox 狀態是 client DOM）→ **「換包裝標籤」技巧**：把 checkbox 外層 tag 隨當前頁輪替（div／section／article／aside），React 因元素型別改變而重建 → checkbox 重置 → **自動收合 ✓（兩版）**（⚠️ 依賴 React 重建行為，屬 hack）。桌機：☰／遮罩 `display:none`，同一容器＝176px rail。AppTest：開／關**無法**測（非 Streamlit 元件），只能測 radio＋markdown 結構＋Playwright。無新 session key；radio 仍是 `key="ui2_page"`，既有 `at.radio(key="ui2_page")` 測試不動。 |
| **D `st.popover("☰")`**（`e3_misc.py?v=popover`） | popover 內放 radio | 有原生 `aria-expanded/aria-haspopup`、Esc 關 ✓；但面板是**浮在按鈕下的 320px 卡片**（非左側抽屜）、**不固定**（隨頁捲）、**切頁後不關**；且桌機 rail 需另一份 radio（同 key 會重複 widget）→ **不採**。 |
| **E `@st.dialog`**（`?v=dialog2`） | 對話框內 radio；選取後 `st.session_state` 寫入＋`st.rerun()` | 原生 Esc ✓、`aria-labelledby`、焦點進對話框、切頁後**關閉並換頁 ✓**（需 `st.rerun()`，否則 fragment 只重跑對話框、主內容不換——實測 `?v=dialog` 版未換頁）；但是**置中 358px 浮窗**（非左抽屜）、關閉鈕 18×18、開啟＝一次 rerun、桌機仍需第二份 radio → **不採為主案**（可當 a11y 備援想法）。 |
| **F `st.navigation`**（`e6_nav.py`） | 多頁路由 | 變成 URL 路由（`/p4_target`）；sidebar 切頁**不自動收合**（`aria-expanded=true`）；等於重寫「單頁＋`ui2_page` radio」架構，既有 `at.radio(key="ui2_page")` 導覽測試全需重寫 → **不採**。`position="top"` 在 390 未能取得有效結果（**未驗**）。 |

### B.2 評分（1～5，5＝最好；回歸風險以「風險低＝高分」計）

| 準則 | A 原生 sidebar | B 自訂＋session | **C CSS-only（推薦）** | D popover | E dialog |
|---|:-:|:-:|:-:|:-:|:-:|
| 正確性（符合 DEC-134：左抽屜、預設收合、全寬、切頁收合） | 3 | 4 | 4 | 2 | 3 |
| 手機可用性（觸控、即時性、a11y） | 2 | 4 | **5** | 2 | 3 |
| 實作時間（估計） | 4 | 3 | 4 | 4 | 3 |
| 維護成本 | 2（內部 testid、版本差異） | 3 | 3（hack：raw `<input>`、換標籤、`:has`） | 3 | 2 |
| Token 成本（估計） | 4 | 3 | 4 | 4 | 3 |
| 回歸風險 | 2（工具列、桌機 rail hack） | 3（守衛白名單、rerun 成本） | 4（零新 key、radio 不動） | 3 | 3 |
| 可逆性 | 4 | 4 | 5（純殼 CSS＋一段 markdown） | 4 | 3 |
| 與桌機 rail 並存 | 2 | 5 | 5 | 1 | 1 |
| **合計** | 23 | 29 | **34** | 21 | 18 |

> 分數與「實作時間／Token」欄為**撰寫組估計**，非實測；其餘有上表實測支撐。

### B.3 推薦與備案

- **推薦：C「CSS-only 抽屜」**——保留現有**單一** `st.container(key="ui2_nav")`＋`st.radio(key="ui2_page")`（四頁只有一份 widget、手機＝抽屜、桌機＝176px rail，**同一份 DOM 兩種呈現**，符合「避免兩套真相」與 DEC-134「單一主導航」）；開／關為 client 端即時（不觸發 rerun、不增 session key、不碰 `ALLOWED_UI2_WRITES`）；a11y 語意較原生 sidebar 完整（`switch`＋`aria-controls`、關閉時移出 a11y tree、☰ ≥44px）。
- **已知弱點（誠實揭露）**：(1) 依賴 `st.markdown(unsafe_allow_html)` 保留 `<input>`（1.56／1.59 實測保留；日後 Streamlit sanitizer 若改變會失效）；(2) 自動收合依賴「換包裝標籤→React 重建」hack；(3) 無 Esc、焦點不回 ☰（見 G）；(4) 抽屜開／關無法用 AppTest 測，只能靠 CSS 字串斷言＋Playwright；(5) 本案新增 New UI2 **第一個 raw 互動 HTML**（現有守衛 `test_disabled_cta_is_not_actionable_html` 等只管元件 HTML，不涵蓋殼，需新增白名單守衛）。
- **備案（降級）**：若獨立 QA 發現 (1)(2) 在 Cloud／iOS 不穩 → 改 **B（session 控制）**：行為最確定（切頁收合由 `on_change` 保證），代價＝每次開關一次 rerun（Real feed 每 rerun 重讀快取）＋明列擴充 `ALLOWED_UI2_WRITES`＋Tab 順序修正。**不建議**以 A＋JS、popover、dialog、`st.navigation` 為主案（理由見 B.1）。
- ⚠️ **DOM 位置陷阱（QA 真 app 副本實測；副本實驗、FAKE、390 寬、非最終實作、單組結論）**：量「market 頁 unavailable 場景，今日主要風險後第一區塊頂緣距**視窗底**」（基線＝現行底部導覽版換算 215.5px）：抽屜標記放內容**後**且 CSS **併入既有 CSS 區塊**＝**215.5px（零位移；距舊導覽線 791 仍為 162.5px）**；另開獨立 `<style>` 元素放內容後＝199.5px；標記放內容**前**＝183.5px；**皆 ≥160px**。位移來源是**額外 element container（各約 16px gap）**，不是抽屜本身。→ 施工須「**CSS 併入既有 CSS 區塊、不在內容前新增任何元素**」。（早先撰寫組以無 banner 最小應用做的相對差外推〔≈179／≈147px〕已由本 QA 實測**取代**，不再引用。）

## C. 手機 390px 文字線框（ASCII）

> 數值為**提案**（客戶未核准像素）：☰ 觸控區 ≥44×44；抽屜寬 `min(82vw, 320px)`（390→320、360→295、320→262，右側留 58～70px 遮罩可點）；項目高 48px；頂部保留量＝☰ 列（8＋44＝52px）；內容水平 padding 沿用現行 `.9rem`（⛔ 不因抽屜改變）。

```
C-1 收合態（預設；內容全寬 390px）
┌──────────────────────────────────────┐ ← safe-area-inset-top（瀏海／狀態列）
│ [☰ 選單]                              │ ← 固定左上 (8,8)；≥44×44；`role=switch`、aria-controls
│ ┌──────────────────────────────────┐ │   top 52px 保留量：內容標題不得被 ☰ 遮住
│ │ 🧪 示意資料（Preview banner，既有）│ │
│ └──────────────────────────────────┘ │
│ 📊 市場                      (頁標題) │ ← 當前頁標題＝頁面自己的 `.ui2-pagetitle`
│ ┌ 更新 CTA／今日結論／風險 …（既有）┐ │   內容寬度＝390 − 2×14.4px；無水平捲動
│ │ …（四頁內容原樣，⛔ 不重新設計）…  │ │
│ └──────────────────────────────────┘ │
│                                      │ ← 底部：⛔ 無固定主導覽；
│   （內容底部留白 ≥ X，見 E、I 節）      │   留白保留給 Manage app／家的指示條
└──────────────────────────────────────┘ ← safe-area-inset-bottom

C-2 展開態（點 ☰／按 Space）
┌───────────────────────────┬──────────┐
│ 台股 AI 戰情室     [✕ 關閉]│ ░░░░░░░░ │ ← 抽屜 320px 覆蓋；右側 70px 半透明遮罩
│ ─────────────────────────  │ ░░遮罩░░ │   （點遮罩＝關閉）
│ ▌● 📊 市場      ← 當前頁   │ ░░░░░░░░ │ ← 當前頁：粗體＋左色條＋●（不靠顏色單獨表達）
│    ○ 🎯 標的               │ ░░░░░░░░ │   每項高 48px、全寬可點
│    ○ 💼 持股               │ ░░░░░░░░ │   恰四項（`radiogroup "導覽"`；⛔ 第五項）
│    ○ 👤 我的               │ ░░░░░░░░ │
│ ─────────────────────────  │ ░░░░░░░░ │
│ Google 帳號                │ ░░░░░░░░ │ ← 帳戶摘要區（F）
│ ⬜ 尚未登入                │ ░░░░░░░░ │   狀態（資料語意軸）
│ [ Google 登入 ]（disabled） │ ░░░░░░░░ │   ⛔ 不可點；灰＋虛線
│ 登入與 Sheet 操作尚未開放   │ ░░░░░░░░ │   原因行（既有字樣）
│                            │ ░░░░░░░░ │   （完整 Google／Sheet 管理 → 👤 我的）
│ …（高度不足時抽屜自身可捲動）│ ░░░░░░░░ │   `overflow-y:auto`；保留 safe-area-inset-left/bottom
└───────────────────────────┴──────────┘

C-3 切頁（點「🎯 標的」）
  ① radio 變更 → 既有 rerun → 主內容換成 🎯 標的
  ② 抽屜**自動收合**（回到 C-1，標題＝🎯 標的）  實測：C 案 ✓（換標籤技巧）、B 案 ✓（on_change）
  ③ 點**目前所在頁**：radio 無變更、不 rerun → 抽屜不會自動收合 → 以 ✕／遮罩／再點 ☰ 關閉（需於驗收明列）

C-4 重新開啟
  再點 ☰ → 回到 C-2，**當前頁標示＝🎯 標的**（radio 保留 `ui2_page`）；抽屜開／關狀態**不跨 reload 保存**（reload＝預設收合）

C-5 關閉方式
  ✕ 關閉鈕｜點遮罩｜再點 ☰（同一個 switch）｜切頁自動收合｜Esc（**C／B 案皆未原生支援，列 I 節／G**）
```

**內容寬度與安全區**（提案；iOS 未驗）：
- 抽屜：`padding-left: calc(.75rem + env(safe-area-inset-left,0px))`、`padding-bottom: calc(1rem + env(safe-area-inset-bottom,0px))`；☰：`top/left` 加 `env(safe-area-inset-top/left,0px)`。
- ⚠️ Streamlit 兩版的 `<meta name="viewport">` 都是 `width=device-width, initial-scale=1, shrink-to-fit=no`，**無 `viewport-fit=cover`**（實測 `static/index.html`）。依一般行為推論：此時 iOS Safari 在直式下通常把頁面排在安全區內、`env(safe-area-inset-*)` 多半為 0，橫向有瀏海時才可能非 0——**這是推論，未驗**（沿用 `NUI2-NAV-SAFEAREA-IOS-UNVERIFIED`，範圍由「底部」改為「頂／左」）。
- 實測的其他視窗：360×640 → 抽屜 295px、無水平捲動；320×568 → 262px、無水平捲動；740×360（橫向小機）→ 抽屜 320px、高度＝視窗（360）、內容不溢出；**844×390（橫向）> 768px 斷點 → 變成 176px rail（沿用現行 `@media (max-width:768px)` 行為），rail 內容高 405 > 視窗 390，靠 `overflow-y:auto` 捲動**——施工時 rail 帳戶區須能捲動／精簡；文字放大 200% → 抽屜 320px、無水平捲動、☰ 寬 128px（Chromium 模擬，非真機）。

## D. 桌機 1440px 線框

```
┌────────────┬──────────────────────────────────────────────────────────┐
│ 台股AI戰情室│  🧪 示意資料（Preview banner，既有）                        │
│ ────────── │  📊 市場                                                   │
│ Google 帳號 │  ┌ …內容（既有桌機版面；⛔ 不重新設計）──────────────────┐ │
│ ⬜ 尚未登入 │  │                                                      │ │
│ [Google登入]│  └──────────────────────────────────────────────────────┘ │
│ (disabled) │                                                            │
│ ────────── │   無 ☰、無遮罩；rail 固定 176px（11rem）、內容 padding-left │
│ ▌● 📊 市場 │   12.5rem（沿用現行）                                      │
│    ○ 🎯 標的│                                                            │
│    ○ 💼 持股│                                                            │
│    ○ 👤 我的│                                                            │
└────────────┴──────────────────────────────────────────────────────────┘
```

- **順序**＝DEC-129／Active Contract §2.5：Product／Logo → **Login／Auth Status（compact Account Area）** → 📊🎯💼👤。⚠️ 現況 repo **尚無桌機 Account Area 實作**（`src/ui2/shell/app.py` 只有 radio；BACKLOG `NUI2-UI-CORRECTION-P7` 仍 open）——本抽屜的帳戶摘要與 P7 的 Account Area **必須是同一個元件／同一份 AccountVM**（手機放在抽屜、桌機放在 rail），**⛔ 兩套各寫一份**。
- **不出現 ☰**（實測 C／B 案桌機 `display:none`；rail 176px；`document` 無水平捲動；`.block-container` 仍讓出 12.5rem）。
- **同一份導覽來源**：手機抽屜與桌機 rail＝同一個 `ui2_nav` 容器、同一個 `st.radio(key="ui2_page")`（只靠 CSS media query 換呈現）；不需要第二份 radio（第二份同 key 會 duplicate widget／ID 衝突，D／E 案的結構性缺點）。
- **順序差異（P2-3）**：手機抽屜為「四頁 → 帳號」，桌機 rail 為「帳號 → 四頁」（DEC-129）；同一份 DOM 以 CSS `order` 呈現兩種順序，施工須在手機與桌機各驗 **Tab 順序與螢幕閱讀器朗讀順序**（視覺順序≠DOM 順序的風險）。
- 斷點沿用現行 768／769px。⚠️ 帳戶區放進 rail 後，rail 在低高度視窗（如 844×390 橫向）需可捲動（見 C 末段實測）。

## E. Manage app 浮層

- **誠實揭露**：Manage app 是 **Streamlit Community Cloud 的平台浮層**，本地 `streamlit run` **不會出現**；客戶截圖顯示它遮擋底部（契約附件：「尚未重現」）。**本檔所有結論皆無法在沙箱證實對它有效**，也**不以 CSS 隱藏平台 UI 當保證**（契約 Gate 3）。
- **推論（未驗）**：Manage app 位於**右下**；本設計的唯一固定控制項 ☰ 在**左上**，抽屜開啟時操作點（四頁、登入入口）集中在**左側 320px 與上半部**（390 寬時右側只剩 70px 遮罩），因此互不重疊——前提是 Manage app 只占右下角一小塊。若它在展開態蓋住右側遮罩的下方，只影響「點遮罩關閉」的一部分區域，✕ 與切頁仍可用。
- **內容尾端**：移除底部導覽後，內容仍可能被右下浮層蓋住最後一行 → 建議**保留**一段底部留白（現行 `padding-bottom: calc(5rem + env(safe-area-inset-bottom,0px))`，見 `src/ui2/shell/css.py`），數值待真機調整（I 節內部拍板項）。
- **帳戶區位置**：抽屜內帳戶區置於**上半部**（四頁項目之下、非抽屜底部），避免被右下浮層遮擋。
- **驗收條件（需 Cloud／真機，沙箱不可驗）**：① Android Chrome＋Cloud：☰ 可點、不被 Manage app 或系統列遮擋；② 抽屜展開後四頁與（disabled）登入入口可見可點；③ 頁尾最後一個區塊可捲到 Manage app 之上；④ iOS Safari：頂部（瀏海）與底部（家的指示條）不遮 ☰／抽屜；⑤ 1.56／1.59 在 Cloud 皆通過。

## F. 登入入口與狀態

**呈現（抽屜與桌機 rail 的帳戶摘要共用）**

| 項 | 內容 | 說明 |
|---|---|---|
| 標題 | `Google 帳號` | 既有 `scenarios.py` 的 `Google` 欄名 |
| 狀態（資料語意軸） | `⬜ 尚未登入` | Wireframes 例示字樣、客戶 DEC-129 已採用；**見 J-6 待確認**（Preview 沒有任何 auth 通路，故此字樣在現階段是否構成「宣稱一個無法驗證的狀態」需客戶一句話） |
| 動作 | `Google 登入` 按鈕 **disabled**（`aria-disabled`、不可聚焦或聚焦也不觸發） | 既有 CTA 字樣（`scenarios.py`：`"Google 登入"`）；⛔ 不可點、不連結、不呼叫 OAuth |
| 原因行（Capability 軸，另列） | `登入與 Sheet 操作尚未開放` | 既有字樣（`scenarios.py`／`real_canonical.py` 的 `disabled_reason`）；需要全站同源字樣時用 `⬜ 尚未提供`（`shared/ui2_contract/text.py` `TEXT_NOT_PROVIDED`）；`⬜ 尚未接線` 是 DEC-130 的 Capability 字樣，**不得**放進「狀態」欄 |
| 去向 | 一行小字「完整設定在 👤 我的」 | 不是第二個登入流程；僅指向 |

**DEC-130 兩軸**：「狀態」（Data State／連線事實）與「能力（尚未接線）」**分欄顯示、不混成單一 status**；⛔ 不新增第六態；`⬜ 尚未接線／尚未提供` 不放在 Data State 欄。

**⛔ 不得做的事（逐條對應守衛）**
- 不得把 **FAKE account**（`ui2_account` selectbox，開發面）、**`ui2_dev`**、**query parameter** 當登入證據（Active Contract §2.5／§6、DEC-130(c)、`check_ui2_dev_not_auth`、`T_new_9`）。抽屜帳戶區的資料來源只能是**同一個 AccountVM／正式 auth contract**；正式 contract 尚未具備時，一律呈現上表的「尚未登入／尚未開放」，**不隨 `ui2_account` 變化**。
- ⚠️ **現況衝突（需總管與 P6 組對齊）**：`src/ui2/shell/app.py:85` 把 `ui2_account` **預設值設為 `ACCOUNT_SIGNED_IN`**，使 FAKE 預設情境的 👤 我的頁顯示「Google 已登入（FAKE 帳號）」。若抽屜直接讀同一個 FAKE VM，預設畫面會在抽屜顯示「已登入（FAKE）」，與本節「尚未登入」互相矛盾。本檔建議：抽屜／rail 帳戶摘要在正式 auth contract 前**固定顯示未接線占位**，FAKE 帳戶場景只留在開發面與 👤 的 FAKE 示意；此取捨列 **J-6**（與 P6 線框 H-11 為**同一題**，客戶一次回答兩份同時適用），不由本檔裁決。
- **字樣守衛先行**：統一顯示「⬜ 尚未登入」前，須先擴字樣表並過 `NUI2-AUTH-STATUS-TEXT-GUARD`（BACKLOG:1615）。⚠️ **Real 模式今天顯示的是「⬜ 尚未提供」**；統一成「⬜ 尚未登入」等於**宣稱一個無法驗證的狀態**（無 auth contract）——故 P6 H-11 的 B（同一固定占位，但狀態字樣用「⬜ 尚未提供」、不宣稱已／未登入）是合理備案。
- **與 👤 我的同一 auth truth**：兩處都由同一個 AccountVM 渲染；抽屜只有「簡短狀態＋唯一一顆（disabled）Google 入口」，👤 我的才有完整 Google／Sheet 管理；**全站不得出現兩個可用的主要登入入口**（正式 auth 接線後也只有一個動作來源，由 `NUI2-AUTH-CONTRACT-GATE` 決定）。

## G. Android／iOS／觸控／鍵盤／無障礙需求

> 「≥44px」是 **Apple HIG／WCAG 2.5.5（AAA）／Material 的通用準則，不是客戶裁示**；本檔採用為提案，待客戶／治理確認（J-10 併入「提案數值」）。

| 需求 | 提案 | C 案實測 | 驗證層級 |
|---|---|---|---|
| 觸控目標 ≥44×44px | ☰、✕、四個導覽項、（disabled）登入鈕 | ☰ 77×44；導覽項 48px 高；原生 sidebar ☰ 僅 28×28（A 案缺點） | 沙箱可量；真機手感**未驗** |
| 焦點進入 | 開啟後焦點應移入抽屜（第一個導覽項或標題） | **未達**：C 案開啟後焦點仍在 ☰；需 Tab 一次進 radio（B 案同）。另：☰ 標記置於 **DOM 末端**（內容之後，以免推位移），故 Tab／朗讀順序在**內容之後**才到 ☰ | 沙箱可測；**補強需 JS 或接受現況（I 節）**；真機 VoiceOver／TalkBack **未驗** |
| 關閉後焦點回 ☰ | 應回到 ☰ | **未達**：切頁收合後焦點落在 `BODY`（B、C 皆然） | 同上 |
| `aria-expanded`／`aria-controls` | ☰ 控制抽屜 | C：`role=switch`＋原生 checked 狀態（`switch "主選單" [checked]`）＋`aria-controls`。⚠️ `st.container` **無法設 id**，`aria-controls` 只能指向抽屜**內**自設 id 的標題元素，**不構成整個抽屜的控制關聯**；語意靠 switch 的 checked 狀態。**無 `aria-expanded`**（靜態屬性無法隨狀態更新）；B：`st.button` 無法加 aria 屬性 | 沙箱可測（`aria_snapshot`）；螢幕閱讀器朗讀**未驗** |
| Esc 關閉 | 應可 Esc 關 | **未達**（C、B；A 原生也無；popover／dialog 有） | 沙箱可測；補強需 JS（I 節） |
| 關閉態不可聚焦／不被讀 | 收合時抽屜不可 Tab、不在 a11y tree | ✓（`visibility:hidden`＋transition delay；`aria_snapshot` 空） | 沙箱可測 |
| 螢幕閱讀器 | 導覽＝`radiogroup "導覽"`＋4 `radio`；當前頁＝`checked` | ✓ 結構正確（沿用現行 radio）；VoiceOver／TalkBack 實際朗讀**未驗** | 真機 |
| `prefers-reduced-motion` | 抽屜滑入動畫應關閉 | 原型已加 `@media (prefers-reduced-motion: reduce){transition:none}`；**未用模擬驗證該媒體查詢** | 沙箱可測（`emulate_media`）；本輪未跑 |
| 虛擬鍵盤不遮擋 | 抽屜內無輸入框（登入鈕 disabled），目前無此風險；⛔ 若日後抽屜放搜尋框須重驗 | 不適用（本批無輸入） | 真機 |
| 橫向／大字級 | 見 C 末段（740×360、844×390、200% 字級） | 無水平捲動；rail／抽屜可捲 | 沙箱模擬 ✓；真機未驗 |
| Android Chrome | `:has()`、`label for`、`position:fixed` | Chromium 模擬 ✓；真機＋Cloud **未驗** | 真機 |
| iOS Safari | `:has()`（Safari 15.4+；**現行導覽已用 `label:has(input:checked)`，非新增基準**）、hidden checkbox 的 label 點擊、`env()`、100vh／動態工具列 | **全未驗** | 真機 |

## H. 測試與守衛更新計畫（不得直接刪守衛）

**原則**：舊守衛在施工 PR 內**同批改寫成對等判準，不先刪、不先 skip**；先行新增的「抽屜行為」測試以 `xfail(strict=True)` 標記，施工批落地時**同一 PR 翻綠**（strict 使「提前意外通過／從未實作」都會紅燈）。以下逐項對應。

**strict-xfail 與 browser lane 說明**：新增的 Playwright 行為測試依賴 Chromium；若某環境沒有瀏覽器而整條 lane 被 **skip**，`xfail(strict)` **不會**因此翻綠也不會紅燈——**skipped ≠ passed**。施工批 CI 必須有「瀏覽器 lane 實際執行」的證據（非 skip），且 strict-xfail 在該 lane 內才有意義；無瀏覽器環境只能跑結構／CSS 字串斷言，並在交付報告揭露「行為測試未執行」。

| 現有守衛／判定器（出處） | 現在守的是什麼 | 抽屜版「對等判準」 | 處置 |
|---|---|---|---|
| `test_mobile_nav_stays_four_cells_in_css`（`tests/test_ui2_contract_teeth_pending.py:96`） | `ui2_nav` 在 CSS、有 `position:fixed`（名稱仍寫「四格」，內容很弱） | 抽屜容器仍用 `ui2_nav` 錨點＋`position:fixed`；另新增 `…_mobile_nav_is_one_drawer_with_four_items`：手機 `@media` 內抽屜 `transform/visibility` 隱藏態存在、☰ 規則存在、**無** `bottom:0;height:53px` | 保留；施工批改名＋補斷言（⛔ 刪除） |
| `test_w1_mobile_nav_is_bottom_fixed_53px`（`test_ui2_batch2.py:57`） | 手機底部固定 53px、`padding-bottom:5rem` | 手機：抽屜寬 `min(82vw,320px)`、☰ ≥44px、關閉態 `visibility:hidden`；內容底部留白仍存在（見下 nav_margin 列） | 施工批**同 PR 改寫**；改寫前保持綠 |
| `test_w1_nav_is_exactly_four_fixed_pages_no_fifth`（:38）、`…keyed_container_with_ui2_prefixed_radio`（:43）、`…page_switch_still_works_via_app_test`（:85） | 四頁恰四項、`KEY_NAV="ui2_nav"`、`ui2_page` radio、AppTest 換頁 | **原封不動**（C 案保留同一容器與 radio，AppTest 仍可 `at.radio(key="ui2_page")`；兩版已驗） | 保持 |
| `test_w1_nav_css_does_not_depend_on_streamlit_internal_classes`（:79） | 導覽 CSS 不得含 `emotion`／`data-baseweb`／`stRadioOption`；**掃描範圍＝W-1 區段（`/* ── W-1`）之後**，P1 的 `stToolbar` 隱藏規則在區段之前、**不在此限** | 抽屜 CSS（位於 W-1 區段之後）同樣禁（並建議加禁 `stSidebar`／`stToolbar` testid——A 案已證明依賴它們會脆） | 保持＋加嚴 |
| `test_w1_desktop_nav_is_left_column`（:65） | 桌機左欄 `top:0;left:0;bottom:0`、`padding-left:12.5rem` | **不變**（桌機 rail 保留）；另加「桌機 ☰／遮罩 `display:none`」 | 保持＋補 |
| `NAV_MOBILE_H == 53 and 844-53 == 791`（`test_ui2_batch2.py:337`）／`measure_viewport.py:40` | 第一屏可用高＝844−53＝791（Freeze §16） | **可用高維持 791**（以「視窗底扣底部保留帶 53px」表達；待客戶確認）；舊常數保留並改註「底部保留帶（代表 Manage app／家指示條遮擋區），非導覽高」；☰ 列另加「元素頂緣 ≥ ☰ 列底緣」判準 | 同 PR 改寫常數與斷言 |
| `first_screen_within_usable_height`（`measure_viewport.py` THRESHOLDS） | 第一屏四問底緣 ≤ 791 | 底緣 ≤ **791（＝844 扣底部保留帶 53px；數值等同今天，不放寬）**，且頂緣 ≥ ☰ 列底緣 | 同 PR 改寫 |
| `first_screen_above_nav`／`nav_fixed_four`（`measure_viewport.py:60、173`；`test_ui2_batch2.py:357` 評估器 teeth） | 手機：元素底緣 ≤ 導覽上緣；導覽恰 4 項、貼底 53px、4 格同列 | 「第一屏元素不與 ☰ 矩形相交」＋「**關閉態**抽屜完全在視窗外且不可見」＋「**展開態**抽屜內 `radiogroup` 恰 4 項、全 DOM 僅 **1** 個頁面 radiogroup（防雙主導覽）」＋「視窗底部 0 個 `position:fixed` 主導覽」；評估器 teeth（突變：把導覽放回底部／多放第二組 radio）須轉紅 | 同 PR 改寫；保留突變測試精神 |
| `test_nav_margin_content_bottom_reserve_covers_nav_height_and_safe_area`（`test_ui2_batch3.py:959`） | 內容底部留白 5rem＋`env()` ≥ 導覽 53px | 改為「內容底部留白 ≥ **Manage app／家的指示條保留量**（暫維持 `5rem + env(safe-area-inset-bottom)`，**數值待真機**）」；仍斷言帶 `env()` 項 | 同 PR 改寫 |
| `nav_margin_after_risk`／`market_main_risk_nav_margin`（`measure_viewport.py:80、383、624`；`test_ui2_batch3.py:798、981、999`；證據 JSON `docs/vnext/newui2_*/…viewport_measurements*.json`） | 手機市場頁六場景：今日主要風險後第一區塊頂緣距**導覽上緣** ≥ 1 行行高 | 改為距「**視窗底扣底部保留帶（暫定 53px）**」（＝線 791）≥ 1 行行高；證據 JSON 以新量測**另存新檔**（⛔ 覆寫舊證據） | 同 PR 改寫；舊 JSON 留存為歷史 |
| `p2_nav_margin_160`（`measure_viewport.py:129、229`；`test_ui2_p2_primary_slot.py:286`；客戶 (19)「未達就停止，不擅自更改設計」） | 手機 stale／unavailable：風險後第一區塊頂緣距導覽上緣 ≥ **160px**（現況僅 **162.5px**，BACKLOG:1797-1800） | **等價判準（建議）**：距「**視窗底扣底部保留帶（暫定 53px＝舊導覽高，代表 Manage app／家指示條遮擋區）**」≥ 160px——數值等同今天的 162.5／181.6px，**不放寬**。QA 副本實測（見 B.3「DOM 位置陷阱」；副本實驗、FAKE、390 寬、非最終實作、單組結論）：標記放內容後且 CSS 併入既有區塊＝零位移（距線 791 仍 162.5）；另開 style 元素 199.5（距視窗底）；放內容前 183.5；皆 ≥160。施工批仍須以 `measure_viewport.py` 正式量測。 | 同 PR 改寫；未達＝停手回報（維持客戶原條款） |
| `NUI2-NAV-SAFE-AREA`（BACKLOG:1357；釘 53px）／`NUI2-NAV-SAFEAREA-IOS-UNVERIFIED`（:1463） | 底部導覽高度與 iOS 安全區 | 前者標「已由 DEC-134 取代」並由 ☰ 44px＋頂／左 safe-area 項承接；後者**保持 open**，範圍改為頂／左 inset 與 `viewport-fit` 現況 | 文件更新；不關閉 iOS 未驗 |
| G9／`ALLOWED_UI2_WRITES`（`test_ui2_real_feed.py:503`）、`check_ui2_dev_not_auth`（`test_ui2_guards.py:1301`）、`T_new_9` | session key 限 ui2_ 且白名單；`ui2_dev`／query 不得當登入證據 | C 案**不新增 key → 不動**；B 案須擴充白名單（明列、獨立 QA）。另**新增**：抽屜／帳戶摘要原始碼不得讀 `ui2_account`／`st.query_params` 決定登入狀態（AST 守衛，沿用 `check_ui2_dev_not_auth` 風格）；殼內 raw `<input>` 只准白名單（id＝抽屜 toggle）一處 | 新增（先 xfail strict，施工批翻綠） |
| 新增：抽屜行為（Playwright，`tests/ui2_viewport` 或新檔） | — | 390×844：預設收合、內容寬＝390−padding、點 ☰ 開（抽屜 x=0、寬≤320、遮罩在）、點遮罩關、切頁自動收合（四頁各一次）、重開後當前頁標示正確、無水平捲動、Tab／Space／ArrowDown 可操作；1440×900：☰ 不存在、rail 176px、四項；**1.56／1.59 × FAKE／Real 各一輪**（契約 Gate 3） | 新增，先 xfail strict |
| 新增：頁底可捲到底 | — | 捲到最底時最後一個區塊底緣 ≤ 視窗底 −（保留量）；四頁各量 | 新增 |

**P2 餘裕風險重新評估（DEC-128～133；建議，待客戶／總管確認）**：原 160px 門檻的目的是「底部固定導覽不要蓋住第一屏之後的內容提示」。移除底部導覽後遮擋物消失，但 Manage app／家的指示條仍可能遮擋底部，故**建議保留 160px 數值，基準改為「視窗底扣底部保留帶（暫定 53px）」**，可用高維持 791（待客戶確認）——等於今天的判準，**不放寬**，也不因「不再有底部列」就取消（契約 Gate 5：不得默默移除 viewport 檢查；客戶 (19)「維持既有 ≥160px、未達就停止」未撤銷）。是否改用不同數值或保留帶＝**客戶決定**（J-9）。unavailable 僅 162.5px 的脆弱度**不會因本案惡化**，前提是「CSS 併入既有區塊、不在內容前新增元素」（B.3 實測）。

## I. 施工邊界與批次建議（本輪**不授權**）

- **建議第一個施工批（Sonnet 5.5 Medium；≤3 項）**：① 殼內抽屜（C 案）：☰＋遮罩＋`ui2_nav` 容器手機抽屜／桌機 rail CSS＋換標籤自動收合（**抽屜標記放內容之後**）；② 帳戶摘要 disabled 占位元件（**與 P7 桌機 Account Area 共用**；只讀固定占位，⛔ 不讀 `ui2_account`／query）；③ 守衛／viewport 判準改寫（H 表）＋新增 Playwright 行為測試（1.56／1.59）。
- **不在該批**：Google OAuth、真 session 身分判斷、Sheet、canonical、VM schema、Risk Cap、System Action、Digest、四頁內容重排、P6 資料健康度。**碰任一項＝Opus 5.5＋High**（契約 Gate 4／7；`NUI2-AUTH-CONTRACT-GATE`）。
- 若客戶／QA 改選 **B 案**：多一項「擴充 `ALLOWED_UI2_WRITES`」→ 屬守衛變更，須獨立 QA 與總管核准；仍可在 Sonnet 5.5 Medium 範圍，但需把它算進 3 項上限。
- 施工前 Gate（沿用契約附件 Gate 1～8）：本線框經客戶／治理驗收 → 先核對 GitHub 主幹與 open PR（與 P6 分批）→ Cloud／真機驗收條件（E）列入交付報告「限制」。
- 若採用 JS 補強（Esc、焦點回 ☰）：屬 New UI2 首次引入 JS，須**另開 Gate**（安全面、`unsafe_allow_javascript` 守衛、1.56／1.59 行為差異——實測 1.59 切頁收合失敗），不併入第一個施工批。

**內部拍板、報告揭露（原 J-1／J-5／J-7；不問客戶，施工交付報告須揭露）**
- 採哪種做法：推薦 C（CSS-only 抽屜），備案 B（session 控制）；技術取捨由總管拍板。
- Esc 關閉／焦點回 ☰：第一批先不做（需 JS、首次引入），記為已知限制，真機驗收後再議。
- 頁尾底部留白：暫保留 `5rem + safe-area`，真機再調。

**序列化說明**：施工批的三項**依序**進行、寫入端一次一檔（`PROCESS.md §3`）——先 ① 殼內抽屜，再 ② 帳戶占位元件，最後 ③ 守衛／判準改寫與行為測試；每項各自經獨立 QA 複驗（CLAUDE.md §-2），不並行改同一檔（`src/ui2/shell/css.py`／`app.py` 為共用熱點）。

## J. 待客戶確認／裁示項（每項一句話即可；附 AI 推薦，非裁示）

> J-1（採哪案）、J-5（Esc／焦點回 ☰）、J-7（頁尾留白）屬技術性決定，已移到 **I 節「內部拍板、報告揭露」**；本表編號保留以免破壞引用，只留客戶可用業務語言回答的項目。

| # | 問題 | A | B | AI 推薦 |
|---|---|---|---|---|
| 2 | 桌機是否完全不顯示 ☰？ | 不顯示，固定 rail（現行） | 桌機也可收合 | **A**（DEC-134 保留桌機固定 rail） |
| 3 | 切頁後抽屜自動收合？ | 自動收合 | 保持開啟 | **A**（客戶 (20)／契約 Gate 6 已要求） |
| 4 | 展開時是否遮罩背景？ | 半透明遮罩，點遮罩可關 | 不遮罩 | **A**（多一個關閉方式；右側 58～70px 可點） |
| 6 | 抽屜帳戶狀態字樣與預設 FAKE 帳戶衝突如何處理？（**與 P6 線框 H-11 為同一題，客戶一次回答兩份同時適用**） | 抽屜／rail 在正式 auth 前固定顯示「⬜ 尚未登入」＋disabled 登入鈕＋原因「登入與 Sheet 操作尚未開放」（不隨 FAKE 帳戶變；⚠️ Real 模式今天顯示「⬜ 尚未提供」，統一＝宣稱無法驗證的狀態） | 備案（H-11 B）：同上（同一固定占位來源、登入鈕 disabled、原因句不變），但狀態字樣用「⬜ 尚未提供」，不宣稱已／未登入 | **A**（客戶 DEC-129 已採「⬜ 尚未登入」；但須先擴字樣表過 `NUI2-AUTH-STATUS-TEXT-GUARD`；B 為合理備案，措辭以 P6 H-11 為準） 📌 **2026-11-04 補註（#1016）**：ChatGPT 獨立審查（`NEWUI2_P6_DRAWER_INDEPENDENT_REVIEW_2026-11-04.md`）對本題改建議 **B**（同上固定占位，狀態字樣「⬜ 尚未提供」）；此為建議層級、**客戶尚未裁示**；#1016 合併後本題建議以該文件為準，上列推薦 A 原文保留不刪。 |
| 8 | ☰ 顯示「☰ 選單」還是只有「☰」？ | 「☰ 選單」（較易點、較易被讀） | 只有「☰」（更省空間） | **A**（客戶原話是 ☰；加字不改位置，僅增可及性） |
| 9 | 手機「第一屏下方餘裕 ≥160px」是否沿用、基準改為「視窗底扣底部保留帶（暫定 53px）」（可用高維持 791）？ | 沿用 160px 與 791（數值等同今天，不放寬） | 取消或改數值 | **A**（客戶 (19) 條款未撤銷；不默默移除檢查） |
| 10 | 提案像素（☰ ≥44px、抽屜寬 `min(82vw,320px)`、項目高 48px）是否接受？ | 接受作為施工起點 | 另給數值 | **A**（通用觸控準則，非客戶裁示；經此確認才算數） |

## 附錄 1：實測腳本與環境（scratchpad，非 repo；未 commit）

根目錄：`/tmp/claude-0/-home-user-my-stock-dashboard/63bda950-423d-54ee-a3a0-c173e0eb3d47/scratchpad/dr/`

| 檔 | 用途 |
|---|---|
| `common.py`／`run_srv.sh` | 共用內容（真實 `VIEWS`＋`CSS`）／啟動 1.59（系統）與 1.56（`/tmp/v156`）伺服器 |
| `e1_sidebar.py`＋`m1.py`、`q1.py` | A 原生 sidebar（plain／rail／js 三變體）；`stToolbar` 隱藏發現 |
| `e2_custom.py`＋`m2.py` | B session 控制抽屜 |
| `e4_cssonly.py`、`e4b_switch.py`＋`m4.py`、`m4k.py`、`m6.py` | C CSS-only 抽屜（含換標籤自動收合、鍵盤、`role=switch`、餘裕比較） |
| `e3_misc.py`＋`m3.py`、`m5.py` | sanitizer 測試、D popover、E dialog |
| `e6_nav.py` | F `st.navigation` |
| `e0_base.py` | 現行底部導覽基準（餘裕對照） |
| `at_t.py` | AppTest（A／B／C，1.56＋1.59） |

- 環境：Streamlit 1.59.2（系統）、1.56.0（`/tmp/v156`）；Playwright 1.64.1＋`/opt/pw-browsers/chromium_headless_shell-1243`（預設 build 缺，以 `executable_path` 指定）；`streamlit run`（cwd＝repo 以套用 `.streamlit/config.toml` dark theme）。實驗結束已 `pkill -f 'streamlit run'`。
- **未驗清單**：iOS Safari／Android 真機；Streamlit Cloud 與 Manage app；VoiceOver／TalkBack 朗讀；`prefers-reduced-motion` 實際生效；Real feed 下的開／關延遲（B 案 rerun 成本僅在 FAKE 內容量測）；`st.navigation(position="top")`；正式 `measure_viewport.py` 基準下的 160px 數值（本檔數字為相對差外推）。

## 附錄 2：本檔的限制（§-2 規則 6 誠實揭露）

1. **單組撰寫，無第二組獨立複驗**；全稱句（例如「`<input>` 在兩版皆未被 sanitizer 移除」「F 案不自動收合」）都只涵蓋本次最小應用與 Chromium 模擬，**不得**當成已複驗的事實引用。
2. 評分表、實作時間、Token 成本為**估計**。
3. 餘裕數值為 QA 真 app 副本實驗（FAKE、390 寬、非最終實作、單組結論），**不是**正式 `measure_viewport.py` 量測；撰寫組早先的外推（≈179／≈147px）已刪除。
4. 本檔未修改 repo 任一檔；與 P6 線框的交界（F 節的 FAKE 預設帳戶、Account Area 共用元件）需由總管統一核對兩份檔案。
