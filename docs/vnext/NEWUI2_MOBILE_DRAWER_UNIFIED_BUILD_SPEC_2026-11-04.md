# New UI2 手機抽屜：統一施工規格（治理採用版）— 2026-11-04

> **治理採用的施工規格（單組撰寫＋獨立 QA）；正式 JS 未核准；本批不授權施工；非客戶視覺驗收。**
> - 性質：把 #1015（線框）、#1016（ChatGPT 獨立審查）、#1017（施工前驗證）三份文件的**有效結論**整合成一份施工時只需讀的規格，並逐條標出舊文字中**已過期**的部分。**不新增 DEC、不改任何 DEC 原文、不建立第二套產品憲法。**
> - 配套文件：JS 安全設計 `NEWUI2_MOBILE_DRAWER_JS_SAFETY_DESIGN_2026-11-04.md`；測試與驗收規格 `NEWUI2_MOBILE_DRAWER_TEST_AND_ACCEPTANCE_SPEC_2026-11-04.md`。
> - 撰寫狀態：docs 組**單組撰寫，待獨立 QA**（`CLAUDE.md` §-2 規則 4／6）。文中所有瀏覽器行為、秒數、像素數字都來自研究組（單組）在 Chromium headless 的原型結果，**本文撰寫者未重跑**；「已驗」一律限於 Chromium headless × Streamlit 1.56.0／1.59.2，**iOS Safari、Android 真機、Streamlit Community Cloud（含 Manage app）、CSP、VoiceOver、TalkBack、Firefox、WebKit 全部未驗，永不宣稱 PASS**。
> - 效力：本檔低於客戶原文（DEC-081／117／119／122／124／127～136 fence）與 `NEWUI2_ACTIVE_PRESENTATION_CONTRACT_2026-11-03.md`。**DEC-128～134 與 Active Contract 一字未動。** 與舊線框衝突時，本檔的「過期條文對照表」（§2）說明誰贏；舊文不刪。

## 1. 「本輪治理採用」記錄（來源必須讀對）

下列六項是 **ChatGPT／客戶側的治理方向**（透過總管轉達本輪派工），**不是**使用者親眼看過視覺稿後的驗收（使用者在 #1016 自述「我看不到圖片，只能聽你建議了」），**也不是** DEC：**DEC 尚未落盤，是否落盤由 ChatGPT／客戶決定**，本檔不新增 DEC。

| # | 治理方向（本輪採用） | 在本規格的落點 |
|---|---|---|
| G-1 | 抽屜開啟時背景不可被 Tab 或輔助科技操作，採**精準作用範圍 inert**（不停用抽屜或 ☰ 自身） | §4 R-07；JS 設計 §3 |
| G-2 | 點「目前所在頁」也要收合抽屜 | §4 R-05 |
| G-3 | C+JS 為**首選施工候選**；**正式 JS 尚未核准**（BACKLOG `NUI2-DRAWER-NEW-JS-GATE` 維持 open） | §3、JS 設計 §0 |
| G-4 | J-6 採 B「⬜ 尚未提供」，**歸屬 Capability 軸**（不是「狀態」欄）；登入鈕 disabled、原因句「登入與 Sheet 操作尚未開放」；不作真實登入判斷，不讀 `ui2_account`／`ui2_dev`／query | §7 |
| G-5 | ☰ 貼 `top:0; left:0`、44px、占既有 `padding-top:2.75rem` 頂部空間；第一屏餘裕 ≥160px（基準＝距舊導覽線 791＝視窗底扣 53px 保留帶）；**已證實不合格的 52px／8px 配置（unavailable 154.5）不可用** | §5 |
| G-6 | 正式圖表、OneBrain、Risk Cap、System Action、OAuth、Digest 契約不變 | §9 |

⚠️ 因此：本檔**不得**被引用為「客戶已核准抽屜」「客戶已核准 JS」「J-6 已由客戶裁示」。J-6／H-11 在 BACKLOG 仍是 `blocked-on-customer`（見 BACKLOG 補註）；G-4 是治理層採用的**施工前提方向**，客戶若回答不同，以客戶為準。

## 2. 過期條文對照表（舊文保留不刪；現行以本規格為準）

來源簡稱：**WF**＝`NEWUI2_MOBILE_DRAWER_TEXT_WIREFRAME_2026-11-04.md`（#1015）；**REV**＝`NEWUI2_P6_DRAWER_INDEPENDENT_REVIEW_2026-11-04.md`（#1016）；**VER**＝`NEWUI2_MOBILE_DRAWER_PREIMPLEMENTATION_VERIFICATION_2026-11-04.md`（#1017）；**P6**＝`NEWUI2_P6_DATA_HEALTH_TEXT_WIREFRAME_2026-11-04.md`。

| # | 舊文位置與舊條文 | 為何過期 | 現行以本規格為準 |
|---|---|---|---|
| S-1 | WF §B.3「推薦：**C 純 CSS-only 抽屜**」；WF §B.2 評分表把 C 評為最高（34 分）；PROJECT_STATE §65「撰寫組推薦 C（CSS-only）」 | VER §3.1 實測 **純 CSS 做不到 Esc 與焦點進出**；治理方向 G-1 又要求背景 inert（CSS 無法達成）。現行首選候選＝**C+JS**（JS 未核准） | §3、§4 |
| S-2 | WF §I「Esc 關閉／焦點回 ☰：**第一批先不做**（需 JS、首次引入），記為已知限制」；WF §G 表 Esc／焦點列的「補強需 JS 或接受現況」 | Esc、焦點進入當前頁 radio、焦點返回 ☰ 已升為**必要行為**（VER §7、REV §2「施工前強制驗收」）。若 JS Gate 不核准＝**無法滿足必要行為，須 STOP 呈報**，不得默默降級回「已知限制」 | §4 R-02／R-08／R-09、§3 末段 |
| S-3 | WF §I 末「若採用 JS 補強（Esc、焦點回 ☰）：須**另開 Gate**……**不併入第一個施工批**」 | 「另開 Gate」仍成立（`NUI2-DRAWER-NEW-JS-GATE` open）；但「JS 不併入第一批」已過期——JS 若核准，抽屜殼與 JS 必須**同一施工批、同批驗收**（殼的 DOM 與 JS 的 selector 互相綁定；單做殼會留下 Esc／inert 缺口） | §10 |
| S-4 | WF §C-1／C-2 ASCII 與 §C 說明「☰ 固定左上 **(8,8)**」「頂部保留量＝☰ 列（8＋44＝**52px**）」；WF §H 表 `first_screen_within_usable_height` 列「頂緣 ≥ ☰ 列底緣」所依的 52px 列 | VER §4 實測：8px＋`padding-top:3.25rem` → unavailable **154.5**（<160）；8px＋4rem → **142.5**。現行＝☰ `top:0; left:0`、高 44px，**占既有 `padding-top:2.75rem`（=44px）**，餘裕與基準逐位相同（stale 181.6／unavailable 162.5） | §5 |
| S-5 | WF §C-3 ③「點**目前所在頁**：radio 無變更、不 rerun → 抽屜**不會**自動收合 → 以 ✕／遮罩／再點 ☰ 關閉（需於驗收明列）」；§C-5 同 | 治理方向 G-2：點當前頁**也要收合**。候選 JS 以 `click`（capture）委派達成。VER §3.4 已指出此行為差異 | §4 R-05 |
| S-6 | WF §F 表狀態欄「`⬜ 尚未登入`」與 §F「字樣守衛先行：統一顯示『⬜ 尚未登入』前須先擴字樣表」；WF §J-6 AI 推薦 **A**；P6 §H-11 推薦 A；P6 §F／ASCII 圖的「⬜ 尚未登入」；BACKLOG／PROJECT_STATE §65／HANDOFF 的「推薦 A」敘述 | 治理採用 **B「⬜ 尚未提供」**，且歸 **Capability 軸**（非「狀態」欄）。`TEXT_NOT_PROVIDED` 已存在於 `shared/ui2_contract/text.py`，B **不需擴字樣表**，`NUI2-AUTH-STATUS-TEXT-GUARD` 對 B **不是前置**。⚠️ DEC-129 的「⬜ 尚未登入」**字面**僅在**正式 auth contract 具備後**適用，本規格**不撤銷** DEC-129 | §7 |
| S-7 | WF §B.3 末「⚠️ DOM 位置陷阱」：「另開獨立 `<style>` 元素放內容後＝**199.5px**；標記放內容前＝**183.5px**；**皆 ≥160px**」 | 這兩個數字是**距視窗底**，而 160 門檻定義是**距舊導覽線 791**（＝視窗底扣 53px）。換算：199.5−53＝**146.5**、183.5−53＝**130.5**，**皆 <160**。只有「CSS 併入既有區塊、標記放內容後」的 215.5（距線 791 為 **162.5**）合格 | §5 R-14 |
| S-8 | WF §B.3 第一點與 §G 表：「`role=switch`＋**`aria-controls`**」；WF §B.1 C 列「`aria-controls`」 | `st.container` 無法設 id，`aria-controls` **指不到整個抽屜＝無效關聯**（WF §G 自己也承認「不構成控制關聯」）。現行：**刪除 `aria-controls`**；採 switch＋原生 `checked` 狀態，**不留靜態 `aria-expanded`**（靜態值會說謊，VER §3.2） | §6 A-2／A-3 |
| S-9 | WF §G 表「關閉態不可聚焦／不被讀：✓（`aria_snapshot` 空）」；VER 對應「關閉時抽屜不在 a11y tree ✓」 | 研究組以 **CDP AXTree** 實測：關閉態下 radio 不在 tree，但**抽屜內「Google 登入」disabled 帳戶區塊與「📊 市場」文字仍在 a11y tree**（某 emotion class 使 `visibility:visible`）。且 Playwright `aria_snapshot` **不反映 inert**，不可作證據 | §8 L-4、§6 A-7 |
| S-10 | WF §G 表／VER §3.3「C+JS **無 focus trap**（Tab 會穿到遮罩後頁面）」 | 候選 JS_V3 以**精準範圍 inert** 達成等效隔離（背景 Tab 0 次、背景具名 a11y 節點 13→0，Chromium）。注意**仍有殘餘缺口**（§8 L-1～L-3），且未驗真機／SR | §4 R-07、§8 |
| S-11 | VER §7／BACKLOG `NUI2-DRAWER-NEW-JS-GATE`「約 25 行」「`window.__ui2drJS2`」 | 候選 JS 現為 **46 行／3592 bytes**，去重旗標為 `window.__ui2drJS3`；JS_V3 全文與 sha256 見 JS 安全設計 §1 | JS 設計 §1 |
| S-12 | WF §H 表「新增：抽屜行為（Playwright）」「先 xfail strict」未規定如何**強制 CI 真的跑瀏覽器** | 現況 CI 兩個 job 都沒裝 playwright，現有真瀏覽器測試是 `@slow`＋`importorskip`＋缺 Chromium 時 `pytest.skip`＝**永遠不阻擋**。skip≠PASS 要靠強制 lane | 測試規格 §2 |
| S-13 | WF §J 表 J-6 列推薦 A、REV §1 H-11／J-6 列 B 的「建議層級」字樣 | REV 的 B 是建議；本輪治理已**採用** B（仍非客戶裁示、DEC 未落盤） | §1、§7 |

> **處置方式**：舊線框主檔、P6 線框檔頭與 J 表處已**只追加**註記指向本規格；原文一字未動。若發現本表漏列過期條文，請**追加**列，不得改舊文。

## 3. 路線決定與降級

- **首選施工候選：C+JS**＝CSS checkbox 抽屜（沿用單一 `st.container(key="ui2_nav")`＋單一 `st.radio(key="ui2_page")`，手機＝抽屜、桌機＝176px rail，同一份 DOM）＋ `st.html(DRAWER_JS_HTML, unsafe_allow_javascript=True)` 一段固定常數 JS。
- **JS 狀態**：候選 JS_V3 全文與安全設計在 JS 設計文件；**正式 JS 未核准**。核准前不得進入 repo 的任何可執行檔（`.py`／`.js`／`.html`）。
- **核准條件**（`NUI2-DRAWER-NEW-JS-GATE`）：治理／客戶裁示 ＋ 該文件 §7 的 Gate 清單（白名單差異、1.56／1.59 行為矩陣、殘留測試、獨立 QA）。
- **降級（只在 JS 被擋時）**：保留「換包裝標籤」輪替 hack（切頁後 React 重建 checkbox → 收合）。此時**沒有** Esc、焦點管理、inert、點當前頁收合——**不滿足 G-1／G-2 及必要行為 R-02／R-05／R-07／R-08／R-09**。因此 JS 被擋＝**STOP 並回報治理**，不得把降級狀態當作「已完成」交付。VER 提過的 C-pop（Popover，零 JS，條件 (5) 部分達成）是治理若不接受 JS 時的**另一條需重新裁示的路線**，本規格不預設採用。
- 其他方案（A 原生 sidebar、B session 控制、popover、dialog、`st.navigation`）不採，理由見 VER §3.5／WF §B.1；B 會觸發 G9 與 `ALLOWED_UI2_WRITES` 變更，無優勢。

## 4. 行為需求（R 系列；施工與驗收都以此編號）

> 適用：手機寬度（`max-width:768px`）。桌機（>768px）無 ☰／遮罩，固定 176px rail（R-12）。

| ID | 需求 | 驗證層級（見測試規格） |
|---|---|---|
| R-01 開關 | 點 ☰（或焦點在 ☰ 時按 **Space**）開啟；再點 ☰ 或點遮罩關閉。狀態唯一來源＝`.ui2-dr-toggle` 的 `checked` | Playwright |
| R-02 焦點進入 | 開啟後焦點移到**當前頁**的 radio（同步 focus，不靠計時） | Playwright |
| R-03 四頁切換 | 抽屜內恰四項（📊 市場／🎯 標的／💼 持股／👤 我的），全 DOM 僅一個頁面 radiogroup（防雙主導覽）；切到他頁後主內容換頁 | AppTest＋Playwright |
| R-04 切頁自動收合 | 點他頁 → **立即**收合（不等 server 往返）；rerun 後輪替 hack 重建 ☰ 狀態也為收合；焦點回 ☰ | Playwright |
| R-05 點當前頁收合 | 點目前所在頁：radio 值不變、不 rerun，仍須收合（JS `click` capture 委派；bubble 階段被 React／BaseWeb 擋，必須 capture） | Playwright |
| R-06 遮罩點擊關閉 | 點半透明遮罩 label 原生切換 checkbox 關閉；焦點在 ☰ | Playwright |
| R-07 背景 inert | 開啟時，**不在 {抽屜, ☰ 外層} 祖先路徑上的 sibling** 設 `inert`（手機實測 10 個元素），☰ 與抽屜自身、其祖先**不** inert；關閉、改 1440、rerun 殘留、頁面重載後 inert 一律歸零。驗證要用 CDP `Accessibility.getFullAXTree`（背景具名節點歸零）與 Tab×20／Shift+Tab×20 | Playwright＋CDP |
| R-08 Esc | 抽屜開啟時按 Esc 關閉，焦點回 ☰ | Playwright |
| R-09 焦點返回 | 以任何方式關閉（Esc／遮罩／切頁／點當前頁／方向鍵選取）後焦點回 ☰（點 label 的預設動作會把焦點拉走，故 `setTimeout 0` 再 focus；切頁重建後焦點落 BODY 由 observer 在 rAF 還給 ☰） | Playwright |
| R-10 方向鍵 | 焦點在抽屜 radio 時，方向鍵／**Enter**／**Space** 選取並關閉（BaseWeb 以內部狀態選取，不發 click／change，故須攔 keydown） | Playwright |
| R-11 ☰ 的 Enter | **Enter 不支援**（原生 checkbox 只吃 Space；APG `role=switch` 也只要求 Space）。列為**已知限制**，不加 JS 補（要補須走 JS Gate 差異） | 文件揭露 |
| R-12 桌機 | >768px：☰、toggle、遮罩 `display:none`；rail 寬 176px；內容 `padding-left:12.5rem`（沿用現行）；mq 變更時 JS `sync()` 取消勾選並移除全部 inert（開啟中從 390 拉到 1440 → 無殘留；縮回 390 抽屜為關閉） | Playwright |
| R-13 去重 | `st.html` 的 script 每次 rerun 都重跑；以 `window.__ui2drJS3` 旗標去重。30 次 rerun 後 document 的 keydown 監聽 6→6、MutationObserver 1→1（click 的增加是 Streamlit 自己所為，基準線同） | Playwright 計數器 |
| R-14 第一屏餘裕 | ≥160px，定義見 §5 | measure_viewport |
| R-15 無水平捲動 | 390／360／320 寬皆無；抽屜寬 `min(82vw, 320px)`（提案值，J-10 待客戶接受） | Playwright |
| R-16 減少動態 | `prefers-reduced-motion: reduce` 時抽屜 `transition:none`（原型已加，**未用 emulate_media 驗**） | Playwright（待補） |

## 5. 尺寸與餘裕定義（G-5）

- **☰ 版位**：`position:fixed; top:0; left:0`；**高度 44px**（觸控目標 ≥44×44；寬度 ≥44px，是否加「選單」二字由 J-8 決定，客戶未裁示；無論有無文字都不得改變 44px 高與 160px 量測）；它**占既有 `.block-container padding-top:2.75rem`（=44px）** 的頂部空間，**不新增任何位移**。⚠️ ≥44px 是 Apple HIG／WCAG 2.5.5／Material 的通用準則，**不是客戶裁示**（J-10 待確認）。
- **「第一屏餘裕 ≥160px」的唯一定義**（沿用 DEC-133／客戶 (19)，未撤銷）：市場頁 stale／unavailable 場景、390×844 手機，「**今日主要風險後第一區塊頂緣**」距「**舊導覽線 791**」（＝視窗高 844 − 53px 底部保留帶；保留帶現在代表 Manage app／家的指示條可能遮擋區，不再是導覽高）≥160px。
- **基準（FAKE，390 寬，Chromium，1.56／1.59 同值）**：stale **181.6**、unavailable **162.5**。☰ top:0／44px 配置的量測**必須逐位相同**；不相同＝未達標，停手回報（客戶 (19)「未達就停止，不擅自更改設計」）。
- **R-14／已證實不合格配置**（寫死，禁止再用）：
  | 配置 | stale | unavailable | 判定 |
  |---|---|---|---|
  | 基準（無 ☰） | 181.6 | 162.5 | — |
  | **☰ top:0,left:0、44px、占既有 2.75rem** | 181.6 | **162.5** | ✅ |
  | ☰ top:8px＋padding-top 3.25rem（WF 原案） | 173.6 | **154.5** | ❌ |
  | ☰ top:8px＋padding-top 4rem | 161.6 | **142.5** | ❌ |
  | 另開獨立 `<style>` 放內容後（WF B.3） | — | 距視窗底 199.5＝距線 791 **146.5** | ❌ |
  | 抽屜標記放內容前（WF B.3） | — | 距視窗底 183.5＝距線 791 **130.5** | ❌ |
- **位移來源**是額外 element container（各約 16px gap），不是抽屜本身。→ 施工硬規則：**CSS 併入既有 CSS 區塊；抽屜標記放內容之後；不在內容前新增任何元素；不另開 `<style>`**。這些量測是 QA 副本實驗（FAKE、390、非最終實作、單組）；正式量測以 `tests/ui2_viewport/measure_viewport.py` 為準。

## 6. 無障礙（A 系列）

| ID | 規格 |
|---|---|
| A-1 | ☰ 可及名稱：`aria-label="主選單"`，☰ 符號本身 `aria-hidden="true"`（避免朗讀「三條線」） |
| A-2 | 採 `role=switch`＋原生 `checked` 狀態；**不留靜態 `aria-expanded`**（靜態值不會隨狀態更新＝說謊） |
| A-3 | **刪除 `aria-controls`**（`st.container` 無法設 id，指不到整個抽屜＝無效關聯） |
| A-4 | 導覽維持 `radiogroup "導覽"`＋4 `radio`；當前頁＝`checked`，並以粗體＋左色條＋●（不單靠顏色）標示 |
| A-5 | 登入鈕 `aria-disabled`，不可觸發 |
| A-6 | **接受限制（待真機）**：☰ 標記置於 **DOM 末端**（內容之後，避免推位移），故 Tab／朗讀順序在內容之後才到 ☰；視覺順序≠DOM 順序。VoiceOver／TalkBack 實際朗讀**未驗** |
| A-7 | 關閉態 a11y 乾淨：見 §8 L-4 的零 JS 修法 |
| A-8 | 驗 inert 一律用 CDP AXTree；**不可**用 Playwright `aria_snapshot()`（不反映 inert） |

## 7. 登入入口與 J-6 採 B（G-4）

- 抽屜與桌機 rail 的帳戶摘要**固定占位**：標題 `Google 帳號`；能力軸（**Capability 軸**，不是「狀態」欄）字樣 `⬜ 尚未提供`（`shared/ui2_contract/text.py` 的 `TEXT_NOT_PROVIDED` 已存在，**B 不需擴字樣表**）；`Google 登入` 按鈕 **disabled**；原因句 `登入與 Sheet 操作尚未開放`；一行小字「完整設定在 👤 我的」（僅指向，非第二個登入流程）。
- **DEC-130 兩軸分離**：「狀態」（Data State 五態）與「接線／能力」（Capability）分欄；`⬜ 尚未提供／尚未接線` **不得放進「狀態」欄**、不新增第六態。
- **不讀** `ui2_account`／`ui2_dev`／`st.query_params` 決定任何登入狀態（AST 守衛沿用 `check_ui2_dev_not_auth` 風格新增）。
- **FAKE 預設影響隔離**：`src/ui2/shell/app.py` 把 `ui2_account` 預設設為 `ACCOUNT_SIGNED_IN`（FAKE 預設道 👤 顯示「已登入（FAKE）」）。**抽屜／rail 帳戶摘要固定占位，不隨 `ui2_account` 變化**；FAKE 帳戶情境只留在開發面（`?ui2_dev=1`）與 👤 的 FAKE 示意。三處（rail／抽屜／👤）不一致的處置屬 H-11（P6）——仍待客戶一次回答兩份適用。
- 🚫 DEC-129 的「⬜ 尚未登入」字面**僅在正式 auth contract 具備後**才適用（`NUI2-AUTH-CONTRACT-GATE`，Opus 5.5＋High）；本規格**不撤銷** DEC-129。正式 auth 前一律不宣稱「已登入／未登入」。
- 全站不得出現兩個可用的主要登入入口。

## 8. 殘餘缺口與接受限制（誠實揭露；皆單組結果）

| ID | 缺口 | 影響／處置 |
|---|---|---|
| L-1 | `section.stMain`（可捲動容器，保留路徑上的祖先）開啟中**仍可拿到一次 Tab 焦點**（嘗試 `overflow:hidden` 仍可聚焦，已放棄） | 內部已無可操作內容；對螢幕閱讀器的影響**未驗**；請治理判是否接受 |
| L-2 | 開啟中 React 新增的節點約 **1 frame** 未被 inert 保護（下一個 rAF 補上） | 已知限制，未量化 |
| L-3 | **不支援 `inert` 的瀏覽器**（Chrome<102、Safari<15.5、Firefox<112）：屬性被當普通屬性＝**無 trap 但無害**（降級＝無 inert）。候選**未內建** focusin 守衛 | 真機／舊瀏覽器未驗 |
| L-4 | **關閉態抽屜的帳戶區塊與「📊 市場」文字仍在 a11y tree**（`.st-key-ui2_nav{visibility:hidden}` 對該區塊無效；某 emotion class 內層 `visibility:visible`）。零 JS 修法：`.st-key-ui2_nav *{visibility:inherit !important}`（研究組實測：關閉後 tree 無 `Google`）。**單組結果**；套用後須重驗開啟態（disabled 登入鈕樣式、radio 可見性）與既有 CSS 字串守衛 | 施工批併入；前人「關閉時抽屜不在 a11y tree ✓」對 radio 成立、對帳戶區塊**不成立** |
| L-5 | 開啟中，body 層 portal／Cloud Manage app 浮層**不被 inert**（上界為 `.stApp`）→ 仍可能被 Tab 到 | 設計取捨；Cloud 未驗 |
| L-6 | ☰ 在 DOM 末端：Tab／朗讀順序在內容之後（A-6） | 接受限制，待真機 |
| L-7 | **Enter 不開 ☰**（R-11） | 已知限制 |
| L-8 | 1.59／1.56 在「快速連點多頁」的最終停留頁不同（1.59＝「我的」、1.56＝「持股」，原因未追，VER §5.4）；候選 JS 的結果相同性未再驗 | 施工批須以行為測試釘住預期 |
| L-9 | CSP／Streamlit Cloud 對 `st.html(unsafe_allow_javascript=True)` 的影響未驗 | 部署前最重要的未驗項之一 |
| L-10 | 候選 JS 的 `Escape` 僅在 `isOpen()` 時處理；若焦點在 iframe 內（本設計不使用 iframe）則漏接 | 無 iframe（VER：iframes=0） |

## 9. 不變項目（G-6）

正式圖表、OneBrain Outlook、Risk Cap、System Action、OAuth、Decision Digest 契約**不變**；四頁名稱、桌機 rail、DEC-127 順序、DEC-129 Account Area、DEC-130 兩軸、DEC-133 的 OneBrain 位置與 Primary 空槽**不變**；不得借抽屜批夾帶內容重排或 P6 資料健康度。DEC-135（頁數彈性）**不代表已新增頁**；新增頁須獨立任務＋線框＋資料契約＋核准。

## 10. 施工批切分（本批不授權）

沿用 WF §I 的序列化紀律（寫入端一次一檔，`PROCESS.md` §3），但依 S-3 更新：

1. （前置）JS Gate 核准、線框驗收、J-6 客戶答覆、CI 強制瀏覽器 lane 的 required check 設定（user 在 GitHub 做）。
2. 施工批（Sonnet 5.5＋Medium，若觸及 JS 安全面或 auth 則升 Opus 5.5＋High）：① 抽屜殼（☰＋遮罩＋CSS 併入既有區塊＋換標籤收合 hack＋§6 a11y＋L-4 CSS 修法）＋ `drawer_js.py`（JS_V3 固定常數）；② 帳戶摘要 disabled 占位（與 P7 共用元件）；③ 守衛／viewport 判準改寫＋新增行為測試（測試規格）。每項獨立 QA 複驗。
3. 施工 PR **同批改寫**舊守衛，不得只刪（測試規格 §1）。

## 11. 驗證矩陣

| 維度 | 值 | 備註 |
|---|---|---|
| Streamlit | **1.56.0**（floor，現場讀 `requirements.txt`）、**1.59.2** | 憲法不釘版本號（`CLAUDE.md` §-1.5.D 事實更正 1）；測試內斷言 `st.__version__` 等於 matrix 期望 |
| 視窗 | **390×844**（手機，`is_mobile`＋touch）、**1440×900**（桌機）；另 360×640、320×568、740×360、844×390（橫向走桌機 rail）為研究組已跑的邊界視窗 | 844×390 > 768 斷點，rail 內容高 405 > 視窗 390，靠 `overflow-y:auto` 捲動 |
| 資料道 | **FAKE**（預設，含 `ui2_account` 預設 signed_in 的影響隔離）、**Real**（固定 snapshot 五態＋活 feed 的 11 個量測態；兩種口徑勿混） | 抽屜帳戶區塊兩道輸出必須相同 |
| 瀏覽器 | Chromium headless（唯一已驗） | |

## 12. 未驗清單（永不宣稱 PASS）

iOS Safari（`:has()`、`label for`、`env()`、動態工具列）；Android 真機；Streamlit Community Cloud 與 **Manage app 浮層**（本檔不宣稱已解決遮擋）；CSP 對 `st.html` JS；VoiceOver；TalkBack；Firefox；WebKit；`prefers-reduced-motion` 實際生效；Real feed 下的開關延遲；`inert` 不支援瀏覽器的實際降級；真機觸控手感。

## 13. 下一個施工 Decision Gate 清單（等裁示，不得自行推進）

1. **JS Gate**：是否核准 `st.html(unsafe_allow_javascript=True)` 與 JS_V3（或其修訂版）——ChatGPT／客戶／治理（`NUI2-DRAWER-NEW-JS-GATE`）。
2. **線框驗收**：本規格＋WF 修訂後的 390／1440 線框由客戶／治理驗收（使用者看不到圖，採可在手機閱讀的短版文字流程＋真實 screenshot 審查清單，見 REV §3）。
3. **DEC 落盤**：本輪治理採用的兩項行為要求（inert、點當前頁收合）與 J-6 B 是否落成 DEC——**由 ChatGPT／客戶決定，本檔不新增**。
4. **CI required check**：新增 `ui2-browser`（建議 A＋D 方案，見測試規格 §2）後，**需 user 在 GitHub 的 branch protection 設定 required check**；工具（本 repo 的 AI 工作階段）無權限讀寫該設定。
5. **J 表客戶可答項**：J-2／3／4／6／8／9／10（J-1／5／7 已移內部拍板；J-5 的「Esc／焦點先不做」已依 S-2 作廢）。
6. P7（桌機 Account Area 殼）與 `NUI2-AUTH-CONTRACT-GATE`（Opus 5.5＋High）**未動**；不得自開抽屜／P6 程式批。

## 14. 本檔的限制

單組撰寫；未重跑任何研究組原型；像素與秒數為研究組單組結果；過期條文表（§2）可能漏列。`CLAUDE.md` §-2 規則 6：本檔任何全稱句（如「全 DOM 僅一個 radiogroup」「手機實測 10 個元素被 inert」）在獨立 QA 前只是待驗事項，不得當作後續動作的前提。
