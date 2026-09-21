# UI_PAGE_TODAY —— 「🚦 今天」頁完整版面（第 3 份）

**基準**：線框 `docs/v2/wireframe/wf_page_today.js`（客戶審過）＝版面來源；元件一律引用第 2 份 `UI_COMPONENTS.md`、token 一律引用第 1 份 `UI_TOKENS.md`（⛔ 本檔不改這兩份、⛔ 不新造元件類型）。
實作對照 `src/ui/views/page_today.py::render_page_today()`。斷點沿用第 2 份 `≤640 / 641–880 / ≥881`（CSS 現況不一致已由第 2 份登記為實作待修，本檔不重述）。
⚠️ 本檔為 UI 設計組 WF 單組產出，未經第二組複驗（§-2 規則 6）；**全檔免責只講這一次**。

⚠️ **行號引用會漂（2026-09-21 據實揭露，規格組 WS1）**：本檔、`src/ui_v2/page_today.py`、`tests/ui_v2/test_today_page.py`、`src/ui_v2/components.py` 之間大量以 `UI_PAGE_TODAY.md:NN` 互相引用。~~**2026-09-21 本輪在 ①（第二層層級網格、`today.holdings` 的 `cols`）與 ③（尚未判定 U-1）插入內容，本檔 `:28` 之後的行號整體下移** ⇒ **既有的 `:NN` 引用有一部分已指錯行**。~~
🔴 **2026-09-21 事實更正 —— 有意識的更正，⛔ 不是漏刪。決策者 AI 總管；提出者引用修復組 WX，WX2 獨立複驗成立。**
**上面畫掉那句有一個具體錯誤**：本輪 diff 的第一個 hunk 起點是 `@@ -6,0 +7,4 @@`（實測）——在舊檔第 6 行之後插入 4 行 ⇒ **舊檔第 7 行起就已經整體 +4**，也就是 **① 四層結構表（舊檔第 12~18 行）早就漂了**，而告示卻寫「`:28` 之後」。
**舉證（兩個已固定的檔案狀態互比，⛔ 不是拿去對現在的檔案）**：上一個 commit `fa54fd1` 的本檔**第 14 行**＝四層結構表「葉外」列；**本更正插入之前**的工作區本檔**第 14 行**卻是「⚠️ 線框 `n0` 為**葉外 chrome**…」—— **完全是另一句話**。⇒ 照舊句「只檢查 `:28` 以後」的人**會漏掉整張四層表**。
⚠️ **這兩個數字只是歷史舉證**（要證明漂移就必須指出漂到哪），⛔ **不是可以拿去引用的指標** ——而且**插入本段之後，行號又漂了一次**，⇒ 現在的第 14 行既不是「葉外」列、也不是那句 `n0` 註解。**這正好就是本更正要講的事。**
✅ **現行讀法（⛔ 刻意不帶行號）**：**本檔行號已於 2026-09-21 整體變動，⛔ 任何指向本檔的行號引用一律視為失效**，請改用**章節名**（必要時 ＋ 該處逐字引文）。守衛見 `tests/ui_v2/test_components.py::test_no_spec_reference_is_written_as_a_line_number`。
**兩邊理由並陳**：
- **舊句的用意至今成立** —— 它要提醒讀者「行號會漂、⛔ 不要盲信」，這個提醒本身是對的，⛔ 不是寫錯方向。
- **被權衡掉的只是「用一個具體行號來表達」這個形式**。⛔ **刻意不改成「`:7` 之後」** —— 那只是把同一顆炸彈往前挪，下一次插入的位置不同，這句話又會錯。**一個會過期的告示，本身就是 `CLAUDE.md §8.2.A.0 規則 1` 禁止的東西**（行號是「保證會過期的資訊」）。
**本輪⛔ 未全面重編行號**，理由：跨檔引用同時散在 `components.py`／`test_components.py` 等**本輪檔案邊界外**的檔案，只改一半會變成「有些對、有些錯、而且看不出哪個是哪個」，比全錯更危險。
⇒ **讀到 `:NN` 時請以「**同段的引文字串**」為準、⛔ 不要只信行號**（對照 `CLAUDE.md §8.2.A.0 規則 1`：行號是「保證會過期的資訊」）。~~本輪新寫的引用已盡量改用**章節名 ＋ 標日期的行號**。~~
🔴 **2026-09-21 事實更正 —— 有意識的更正，⛔ 不是漏刪；決策者 AI 總管（WX2 提出）。**
**畫掉的是「＋ 標日期的行號」這半句** ——「**標了日期的行號**」與同日落地的守衛「**⛔ 沒有白名單，也不得加**」**正面牴觸**。
**兩邊理由並陳**：
- **舊句的理由仍然成立** —— 它寫下時守衛還不存在，「標日期」是當時能想到的最誠實作法（對照 `CLAUDE.md §8.2.A.0` **規則 4**：會漂移的量測值一律標日期或不寫）。⛔ 不是寫錯方向。
- **被權衡掉的原因** —— 守衛落地後，`.md`／`.html`／`.js`／`.py` 的 `檔名:行號` 形式**一律紅燈、⛔ 無白名單**。留著這句會讓下一個人以為「**標了日期就可以寫行號**」，而那正是總管裁示「不留白名單」時點名的「**留但書等於留引用點**」（`CLAUDE.md §-2` 規則 6）。
✅ **現行讀法**：一律寫**章節名**（必要時 ＋ 該處逐字引文）；⛔ 不得寫行號、⛔ **即使標了日期也不行**。

## ① 四層結構

「四層」＝ `UI_COMPONENTS` §1 卡片四層密度 `.blk.t1~t4`，對映線框 `layers[].n`。
⚠️ 線框 `n0` 為**葉外 chrome**（五頁共用，不屬任何葉）→ **據實列出，不計入四層**。

| 層 | 線框 | block key | 卡密度 | 主徽章尺寸 | 卡標字級 |
|---|---|---|---|---|---|
| 葉外 | n0 | `today.statusbar`／`chrome.asof` | `t3` `6px 9px` | `.sbadge b3` `11px`／`2px 10px`／min-h 28 | `13px/700` |
| 第一層 結論燈 | n1 | `today.verdict` | `t1` `15px 17px`；border **2px** | `.sbadge b1` `14.5px`／`10px 22px`／min-h 46／border 2px | `17.5px/700` |
| 第二層 核心卡 | n2 | `today.summary`／`today.key_banner`／🆕`today.holdings` | `t2` `10px 12px` | `.sbadge b2` `12.5px`／`5px 13px`／min-h 36 | `14.5px/700` |
| 第三層 操作列 | n3 | `today.actions`（主 CTA） | `t3` `6px 9px` | `.sbadge b3` | `13px/700` |
| 第四層 展開佐證 | n3 | `today.warroom`／`today.detail` | `t4` `5px 9px`；border 1px **dashed** | `.sbadge b4` `10.5px`／`2px 5px`／min-h 26／border 0 | `12.5px/700` `--ink-2` |

**葉外 chrome**（`cols 1/1/1` 三斷點皆滿版）：`today.statusbar` ＝ 3 張狀態卡（交易日／總經／Sheet），實作 `page_today.py:1892` `render_cards(build_status_bar_cards(...))`；`chrome.asof` 見 ③（已撤回）。

**第一層 `today.verdict`**（線框 `cols 1/1/1`）：徽章 #1／#3／#4／#5／#6／#7。
✅ **已決（`user 2026-09-16 裁示`）：第一層＝單一結論燈 ＋ 一句話結論**，線框 `n1`、卡密度 `t1`、一格滿版。
⛔ 第一層**不再是 3 張並排卡**；實作現行 3 卡依裁示歸位第二層，歸位落點見 ③。

**第二層**（`⛔ 卡片本身不可點`，線框 n2 層標籤逐字）：⛔ 本層不得放任何按鈕、連結、`st.popover`。
✅ **已決（`user 2026-09-16 裁示`）：第二層＝下列 3 張並排卡** —— `today.summary`／`today.key_banner`／🆕`today.holdings`。

🆕 **層級網格（那 3 張卡在三斷點怎麼排）＝ `3 / 2 / 1`**（2026-09-21 補，總管拍板）。客戶 2026-09-16 只裁到「**3 張並排卡**」（`:27` ＋ ③「`today.verdict` 形狀」段的裁決逐字，量測日 2026-09-21 為 `:135`），**缺的只是「三個斷點各排幾張」** ⇒ 本段補上：**≥881 三欄／641–880 兩欄／≤640 單欄**。
**來歷（原型 `.g3` CSS 實測，總管複驗）**：`docs/v2/prototype/ui_prototype_today.html:128` 基準 `grid-template-columns:1fr`；`:195` `@media (min-width:641px) and (max-width:880px)` → `repeat(2,minmax(0,1fr))`；`:199` `@media (min-width:881px)` → `repeat(3,minmax(0,1fr))`；該段 `:127` 註解逐字「網格：第二層 3 卡＝ ≥881 三欄 / 641–880 兩欄 / ≤640 單欄」。
⚠️ **原型的地位＝「內部既有產物」，⛔ 不是「客戶已核准的形狀」**（誠實揭露，對抗查證組提出、總管採納）：`STATE.md` 對「原型」／`prototype` **皆 0 命中**（量測日 2026-09-21）；兩個 commit（`d21d1ca` 2026-09-16、`159e264` 2026-09-21）的訊息只記**總管實機量測**與**內部修補**；且 `docs/v2/HANDOFF_UI_2026-09-16.md:34` 把「**客戶確認今天頁原型的視覺方向**」列為「**← 停在這裡**」的待辦。⇒ 拿它當**佐證**可以，⛔ 不得升格成客戶裁示或核准。
🔴 **必讀的區別 —— 這是兩個不同的網格，⛔ 不要混用**：
  - **層級網格**（本段 `3/2/1`）＝ 同一層的**幾個 block 彼此**怎麼並排；
  - **block `cols`**（下面各 block 各自的 `cols`）＝ **單一 block 內部**一列放幾格，多的**換行排下一列**（見本節「排列（三斷點）」段）。
  ⇒ 🆕 `today.holdings` 的 `cols 1/1/1` 指的是**卡內**一列一格，⛔ **不是**「它獨佔一列、堆在最下面」。
  **把 holdings 畫成第三張全寬卡疊在底部 ＝ 正面違反客戶「第二層＝3 張並排卡」的裁示**（③「`today.verdict` 形狀」段裁決逐字），而且⛔ **沒有任何徽章／狀態測試會抓到它** —— 守衛因此寫在 `tests/ui_v2/test_today_page.py` 的 **C-9** 段（`rows_of_layer(2, 1440) == 1`）。
⚠️ **本段只登記第二層**：其餘各層的層級網格**無來源**（客戶未裁、原型該處非 `.g3` 通用結構）⇒ ⛔ 不得為它們發明一組（§1 反捏造）；`page_today.blocks_per_row()` 問到未登記的層一律 **raise**，⛔ 不回一個猜的值。

- `today.summary` 三欄摘要（位階／動能／風險），線框 `cols 3/2/1`，徽章 #1／#3／#4／#5／#6／#7／#8／#9。（⚠️ 這個 `3/2/1` 是**卡內欄數還是層網格**，線框與原型**互相矛盾**、本輪**只登記不解** —— 見 ③ 末「尚未判定」。）
- `today.key_banner` 今日關鍵橫幅，線框 `cols 1/1/1`，實作 `_render_tiles(..., cols=1)`。
- 🆕 **`today.holdings` 持倉健檢 —— 新訂**（線框 `n2` **未定義**此 block；~~`持倉健檢` 全 repo 0 命中~~）。
  ⚠️ **2026-09-21 事實更正，⛔ 不是漏刪**（決策者 AI 總管）：刪除線那半句**自 2026-09-16 15:20 起不成立** —— 實測 `grep -rn 持倉健檢` 命中 `docs/v2/prototype/ui_prototype_today.html:337`／`:340`（本檔自身、`src/ui_v2/page_today.py`、`tests/ui_v2/test_today_page.py` 的命中屬本規格自我引用，不計）。
  **⛔ 不要讀成「當時寫錯」**：本句由 commit `eec3c70`（2026-09-16 **10:19**）寫下，**在那一刻它是真的**；原型 `d21d1ca`（2026-09-16 **15:20**）把「持倉健檢」帶進 repo，**同一天、5 小時後**才讓它失效（`159e264` 2026-09-21 之後只搬動／改寫該段，⛔ 不是它帶進來的）。
  **兩邊理由並陳**：舊句的用意是「這是**全新**的 block，⛔ 沒有既有元件可抄」—— **該用意至今成立**，只是它當時選了一個**會過期的量測值**來表達（對照 `CLAUDE.md §8.2.A.0 規則 4`：會漂移的量測值一律標日期或不寫）。**現行讀法**：本 block 仍是新訂；「0 命中」該句**只能當 2026-09-16 10:19 的歷史量測**，⛔ 不得再被引用為現況。
  填入線框 n2 自己寫的「核心大卡片 **3~4 格**」預留位；⛔ 不得寫得像既有元件。
  組成**只用既有元件**：卡 `.blk.t2` ＋ `.sbadge b2` ＋ `UI_COMPONENTS` §2 徽章，⛔ 無按鈕（不可點）。
  🔴 **資料限制（硬規則）**：持股來源 `stock_watchlist` 的 schema **只有 `name`／`ticker`／`updated_at` 三欄**（`src/data/portfolio/gsheet_portfolio.py:88`，`:85` 註解逐字「§1 反捏造:此分頁**只**存 name/ticker/updated_at 三欄,無張數/均價」）⇒ **這張卡拿不到部位大小**。`src/compute/risk/concentration.py` 因此一律 `basis='equal_weight'`（`:68 BASIS_EQUAL_WEIGHT`）並要求 UI 揭露該假設（`:136` 欄註「UI **必須**據此標註假設」）。
  **可顯示**（皆由檔數推得）：`n_total`／`n_classified`／`n_unclassified`／`n_industries`／`coverage_pct`／`top1_pct`／`top3_pct`／`hhi`／`n_eff`，**＋ 等權假設揭露句一行（必填，`--ink-3` `11.5px` 說明字級）**。
  ⚠️ **「可顯示」＝ 白名單／准許清單，⛔ 不是必填清單**（2026-09-21 消歧義，**非政策變更**、原文未動）：上一行**只有後半**「＋ 等權假設揭露句一行」標了**必填**；九項是**至多**這些、**不是至少**這些。**渲染端可以只畫子集** —— 原型 `ui_prototype_today.html:337-355` 這張卡實際只畫 **4 條** key-value（持股檔數／已分類檔數／產業數／最大單一產業）。守衛：`page_today.unknown_holdings_fields()` ＋ `tests/ui_v2/test_today_page.py` C-7「`test_any_subset_of_the_whitelist_is_legal`」。
  ⚠️ **`UI_COMPONENTS.md` §4「每卡至多顯示 4 對」⛔ 射程外，9 項 vs 4 對⛔ 不構成衝突**（2026-09-21 澄清）：該句的主語鏈是 `UI_COMPONENTS.md:114` `## 4. 表格` → `:124` 手機 ≤640「一列＝一張卡」→ `:126`「**手機卡片流**」→ `:128-129`「降為佐證…每卡至多顯示 **4 對**」⇒ 它管的是「**表格在 ≤640px 降級成的卡片流**」，那種卡是 `.blk.t3`。`today.holdings` 是第二層 `.blk.t2` **核心卡**、**不是表格的一列** ⇒ ⛔ 不得把「4 對」當卡內列數的通則套到本卡。
  ⛔ **不得顯示**：損益、部位佔比、金額、張數、均價，或任何需要張數／均價才算得出來的量。
  ⚠️ `top1_pct` 標籤逐字為「**最大單一產業（檔數等權）**」，⛔ 不得標成「部位佔比」。
  `is_computable=False`（`n_classified==0`）→ 徽章 **#7 缺漏 · 可重跑**，⛔ 不得顯示 `0` 或「完美分散」。

  🆕 **`today.holdings` 的 `cols` ＝ `(1, 1, 1)`**（2026-09-21 補上規格洞；下稱「**§① holdings cols 段**」，程式端註解即指回本段）。
  **語意**：`cols` ＝ **block 內部一列放幾格**，⛔ **不是**「這個 block 佔頁面幾欄」。⇒ `1/1/1` ＝ 這張卡**內部不開網格**，一列一格。
  🔴 **來歷（本檔最需要被看見的一行）：這是 `AI 總管` 2026-09-21 的推導值，⛔ 不是線框值。** 線框 `n2` 確實**未定義**此 block 的 `cols`（本 block 是新訂）。⇒ 程式端 `src/ui_v2/page_today.py` 的 `BLOCK_COLS` 內，本筆**⛔ 不得**比照其餘七筆掛 `# UI_PAGE_TODAY.md:NN` 的**線框出處註解**；它另掛 `# ⚠️ 總管推導值（非線框）` 並登記在 `COLS_PROVENANCE`／`DERIVED_COLS`／`COLS_DERIVATION` 三個**機器可驗**的結構裡（⛔ 只寫註解不算 —— 註解驗不到）。
  **推導鏈（三條）**：
  1. **`cols` 的語意 ＝ block 內部一列幾格** —— `src/ui/views/_ui_kit.py:145` `grid()` 以 `min(cols, MAX_COLS)` 切塊、每塊各開一次 `st.columns(len(chunk))`，多的**換行排下一列**；`src/ui_v2/components.py` 的 `MAX_COLS` 註解與 `resolve_cols()` 同義（「多於 3 格換行排下一列，**不是加欄**」）。
  2. **原型已經畫出這張卡的形狀**（`docs/v2/prototype/ui_prototype_today.html:337-355`，總管實測）：**一張 `.blk.t2` ＋ 一顆 `b2` 徽章（`s7`）＋ 卡內一個 `.stack` 裝 4 條 `.rowline` key-value ＋ 一行 `.note` 揭露句**，內部**沒有網格**（無 `.g3`、無 `st.columns` 對應物）。
  3. **本檔同一段、同一句法裡的刻意差異**：④ 反例自檢 A 的第二層段（量測日 2026-09-21 為 `:165-166`）對 `today.summary` 寫「三格**各自** #6（**逐格獨立判態**）」、對 `today.holdings` 寫**整塊一顆 #7**；`src/ui_v2/page_today.py` 的 `holdings_badge(*, n_classified)` 簽名裡也**沒有「第幾格」這個參數**。⇒ 這張卡是**一個判態單位**，不是三格。
  ⛔ **被打掉的第四條，⛔ 不得補回去**：「本條目上方『組成只用既有元件：卡 `.blk.t2` …』那句的『卡』是**單數**所以只有一張卡」—— **中文不標複數，這條推不出來**（對抗查證組已推翻；本檔 `:16` 就是拿 `t2` 當**型別**用）。守衛：`tests/ui_v2/test_today_page.py::test_rejected_singular_noun_argument_is_not_in_the_derivation_chain`。
  ⚠️ **再說一次（最容易踩的誤讀）**：`1/1/1` 是**卡內**，⛔ **不是**「它獨佔一列、堆在最下面」。三張卡怎麼並排由**層級網格 `3/2/1`** 決定（見上方第二層段）。

**第三層 `today.actions`**（線框 `cols 1/1/1`）：主 CTA ＝ `st.form_submit_button("🚀 更新今日戰情", type="primary")`，經 `_ui_kit.py:single_submit_form`，
字串 SSOT `shared/ia_nav.py:83 ACTION_LABELS[ACTION_UPDATE_TODAY]`，與線框 `mainCTA.label` **逐字相同**。
按鈕規格取 `UI_COMPONENTS` §3 主 CTA：`min-height:40px`／`padding:6px 16px`／`13.5px/700`／`radius:3px`／底 `--ink`／框 `2px solid --ink`／hover 底＋框 `--ochre`、字 `--paper`；焦點環 `2px solid --focus` `offset:2px`。
同 form 內有 `st.radio("更新模式", horizontal=True)` 兩選項 `正常更新（吃暖快取）`／`強制重抓（清快取）`（`src/ui/tabs/tab_today.py:103-106`）。**全頁 `st.button` 0 命中 ⇒ 全站唯一一顆主 CTA 的規定在本頁成立。**
停用態（線框 `loading`／`error`-契約漂移）走 §3「停用態」：`13.5px/500`＋`1px dashed --rule-2`＋字 `--sig-grey`。

**第四層**：`today.warroom`（線框 `cols 1/1/1`，徽章 #1／#3／#5／#6／#7）、`today.detail`（線框 `cols 3/2/1`，徽章 #1／#3／#4／#5／#6／#7／#8／#9）。

**排列（三斷點）**：欄數一律取線框 `cols`，並硬夾在 `tab_today.MAX_COLS＝3`（`:86`）——
多於 3 格**換行排下一列，不是加欄**（`_ui_kit.py:145 min(cols, MAX_COLS)`）。
⚠️ **以下 654／532px 為「應然網格值」，非本頁實測、非本頁現行行為**：由第 1 份欄寬 token 推導的內容寬下限 —— 桌機 3 欄 `--col-min-text-s:210px`×3 ＋ `gap:12px`×2 ＝ **654px**；平板 2 欄 `--col-min-text:260px`×2 ＋ 12px ＝ **532px**；手機 1 欄滿版（含金額欄改 `--col-min:308px`；本頁三格核心卡皆不含金額，⛔ 見上「不得顯示金額」）。
**為何不適用本頁（兩條，缺一不可）**：(a) 那組 token 是給線框 HTML 的 CSS **auto-fit 網格**用的，本頁排版走 `st.columns` —— **按比例切寬、不認 CSS `min-width`**，⇒ **模型就不對**；(b) 本頁 `src/ui/views/*.py` 的 `var(--` **0 命中**，**尚未採用該 token 組**。
⛔ **不得引用本列數字作為本頁實際欄寬或首屏依據**；本頁三斷點的實際排版**仍為「需實機量測」**（實際可用寬 ＝ 視窗寬 − Streamlit 預設 padding，該值不在 repo；`CHECKPOINT.md` 另記「<640px 自動堆疊」且**自標待查證**）。

**首屏可見範圍**：**三個斷點一律「需實機量測」**。repo 內無 `vh`、無首屏高度基準；`src/ui/views/*.py` 的 `var(--` **0 命中**（本頁未引用第 1、2 份幾何）；`app.py` 唯一 `<style>` 的 `@media`
只有列印 ⇒ 排版全由 Streamlit 自身 CSS 決定，repo 內無從反解，⛔ 不猜。
**repo 內唯一可算的**：`_ui_kit.render_card()` 每卡固定 chrome ＝ border 1+1 ＋ padding 8+8 ＋ margin 4+4 ＝ **26px**；帶大字時再 ＋`24px/1.25`(=30px) ＋ `margin-top:2px` ＝ **32px**。
⚠️ 旁證（**轉錄，非本組實測**）：`docs/v2/audit/CHECKPOINT.md:87` AppTest 冷啟動全頁 12,075 字。

## ② 狀態覆蓋（線框 `states` ∪ 實作分支 → `UI_COMPONENTS` #1~#10）

| 線框鍵 | 常數（`shared/ui_state.py`） | 徽章 | 實作 |
|---|---|---|---|
| `live` | `UI_LIVE="live"` | **#1** | ✅ |
| `loading` | `UI_LOADING="loading"` | **#2** | ❌ 見落差 1 |
| `idle` | `UI_IDLE="idle"` | **#3** | ✅（`upstream_requested` gate） |
| `degraded` | `UI_DEGRADED="degraded"` | **#4** | ✅（`discriminative=False`） |
| `unwired` | `UI_UNWIRED="unwired"` | **#5** | ✅（`wired=False`） |
| `error` | `UI_FAILED=`**`"failed"`** | **#6** | ✅ 但字面不一致，見落差 5 |
| `empty` | `UI_EMPTY` ＋ `MISS_NO_INPUT`／`MISS_NOT_ENOUGH`／`MISS_NO_VARIATION` | **#7** | ✅ |
| `missing` | （無獨立常數，併入 `UI_EMPTY`） | **#7** | 見落差 2 |
| `na` | `UI_EMPTY` ＋ `MISS_NOT_APPLICABLE` | **#8** | ✅（靠 `miss_reason` 分辨） |
| `partial` | **七態無** | **#9** | ❌ 見落差 3 |
| （線框無此鍵） | `emits_level=False` | **#10** | ❌ 見落差 4 |

**四項對不上 ＋ 一項字面不一致，逐項處置**：
1. **#2 `loading`：實作待補（不是規格待決）。** 分類器**有能力**產生它（`ui_state.py:204 in_flight → UI_LOADING`），缺的是 caller —— `page_today.py` 的 `in_flight` **0 命中**、`st.spinner` **0 命中**。
   **處置**：取數段包 `st.spinner`，並把 `in_flight=True` 顯式傳進 5 個 `classify_ui_state` 呼叫點
   （`:873`／`:1108`／`:1180`／`:1342`／`:1381`）。⛔ 在補上之前，**不得**拿 #3「尚未載入」冒充載入中。
2. **#7 被 `empty`＋`missing` 兩鍵共用：規格待接線（線框端收斂）。** 兩鍵的線框文案本身也幾乎逐字相同
   （`today.summary`：`empty`／`missing` 兩格文字僅差「▨ 無資料 ＋ `—` ＋ ⚠︎」的同一句）。
   **處置**：兩鍵**都畫 #7**，⛔ 不得為了對齊線框鍵數而新造第 11 種徽章；⛔ 也不得把 `missing` 畫成 #8
   （#8 專屬 `MISS_NOT_APPLICABLE`，重跑無效，畫錯等於給錯指引）。
3. **#9 `partial`：規格待接線（上游 L3）。** 本頁 tile 層查無分子分母，`partial` 只出現在更新報告層
   （`report.partials`，`:1732`）。**處置**：依第 2 份 fail-safe **恆降級為 #7「缺漏 · 可重跑」**，
   ⛔ 不得退回 #1。⚠️ 但線框 `today.verdict.partial`／`today.summary.partial`／`today.detail.partial`
   都寫了 `*` 上標與「N／M 計入」→ **L3 補齊分子分母欄位後，這三處要接回 #9**，不是永久降級。
4. **#10 `emits_level=False`：本頁無此類指標，記為「不適用」而非待補。** `emits_level` 在本頁 **0 命中**，
   線框亦無對應鍵。**處置**：本頁**不畫 #10**；⛔ 但不得因此把 #10 併進 #8（2026-08-26 裁示三旗標互相獨立）。
   本頁日後若納入個股 KD 一類指標，再接。
5. **#6 字面不一致：實作端不動，規格端對照即可。** 線框鍵 `error` ↔ 常數值 `"failed"`。
   **處置**：以常數為準（L0 SSOT，12 個 caller），線框鍵名視為同義；⛔ 不得為對齊線框去改 `UI_FAILED` 的值。

## ③ 線框 vs 實作的差異

**線框有、實作無**
| 項目 | 應然（線框） | 現況 | 分類 |
|---|---|---|---|
| `chrome.asof` 資料時點揭露列 | 頁標題下第一行，5 態 | 整塊未實作（線框自己 `src:null`） | **已撤回，不是待補** —— `page_today.py:71-73` 逐字「原規格要求逐格顯示 as_of，**已撤回**」，因 `get_macro_state()` 只有 9 key、無 `as_of`；改以葉2 頁首 `AS_OF_NOT_IN_CONTRACT` 一句交代 |
| 「展開佐證 ▸」觸發器 | `today.verdict.live`／`today.summary.degraded`／`today.detail.live` 逐字 | `st.popover` 0 命中、字串「展開佐證」0 命中；facts 由 `_ui_kit.py:294-295` 無條件攤成 `st.caption` | **實作待補**（元件已在 `UI_COMPONENTS` §3 第 3 列：`min-height/width:44px`／`7px 9px`／`12.5px/600`） |
| `today.detail` 整列可點就地展開 | ★-02 拍板「**整列可點**」，且區塊標題右側〔展開佐證 ▸〕同時保留 | `st.dataframe`／`st.table` 本檔 0 命中；葉2 是 `_render_tiles` 卡牆，無表、無列、無點擊 | **實作待補**。⚠️ 線框自己註明可點的是**逐盞燈明細那張表的列**，⛔ 不是五桶卡牆（卡片仍不可點，與 n2 同規） |
| `loading` 固定高骨架卡 | 4 個 block 都寫了 | 查無骨架元件 | **實作待補**，與 ② 落差 1 同一根因 |

**實作有、線框無**
| 項目 | 現況 | 分類 |
|---|---|---|
| 頁首「上一次更新的結果」整段 | `_render_refresh_report`（`:1705-1789`），含**全頁唯一** `st.expander("這一輪碰了哪些資料？（逐鍵列出）")` ＋ failures／empties／partials／skipped 四段；線框 8 block 無對應 key | **設計變更**（誠實揭露上一輪結果，方向與 §1 一致）→ 須補進線框，建議掛 `n0` 葉外 chrome |
| 葉2「五桶摘要」獨立 section | `:1942-1943 build_bucket_tiles`；註解自陳「原葉1 ③ 搬到這裡」，但線框 `today.summary` 仍掛 `leaf:'l1'` | **設計變更**（葉歸屬改變）→ 線框 `leaf` 欄待同步 |

**`today.verdict` 形狀：✅ 已決（`user 2026-09-16 裁示`），原「1 燈 vs 3 卡」分歧結案**
裁決逐字：**`today.verdict` 改成兩者並存：第一層＝1 顆結論燈（一句話結論）；第二層＝3 張並排卡（三欄摘要、今日關鍵橫幅、持倉健檢）；線框是對的，實作的 3 卡歸位到第二層。**
⇒ 既然「**線框是對的**」，實作現況一律歸類為**實作待修**（⛔ 不是設計變更，⛔ 線框 `cols 1/1/1` 與 `name`「① 結論燈」不動）：現行 `page_today.py:1902 build_verdict_tiles` 在 `today.verdict`（`:1900`）渲染 **3 張並排卡** —— `verdict.exposure`「能不能出手 · 出手到幾成」（`:1357`，大字值＝`alloc.range_text` 持股區間）／`verdict.danger`「指標危險度（不含多空方向）」（`:1393`）／`verdict.regime`「市場位階（總經契約）」（`:1432`，`REGIME_CARD_LABEL` `:1264`）；docstring `:1324` 逐字「**不平均、不取 worst、不合成一顆燈**」（依據＝ 實跑燈色不一致 39.5%、方向相反 18 組、客戶 2026-08-27 裁示並列揭露不得調和 —— **沿用本檔原文，⛔ 本組未複驗該兩數**）。
✅ **已決（`客戶 2026-09-16 裁示`）：「3 卡歸位到第二層的哪一張」結案** —— 原「待客戶再裁」**撤銷**。裁示逐字（⛔ 不得改寫語意）：「**3 卡歸位：不要硬塞。位階 ← summary.regime（既有）／動能 ← 未接線（exposure 不是動能，不搬）／風險 ← danger（對得上，直接對映）**」。⇒ 下列兩行**是客戶據以裁示的依據，⛔ 不得刪**：
線框 `today.summary` 的 `name` 逐字＝「③ 三欄摘要（**位階／動能／風險**）」（`wf_page_today.js:171`，`src` 指 `page_today.py:1917`）；該三欄在實作中**已存在且非空位**（`tab_today.py:407-440`，經 `page_today.py:1917 render_cards(_summary.cards)` 渲染）：`summary.regime`「位階」**已接線**、`summary.momentum`「動能」／`summary.risk`「風險」為 `_staged_card` 未接線。
**三條對不上**：(a) `verdict.regime` 與 `summary.regime` **同源重複**（後者取 `statusbar.macro` 位階），搬過去是**撞欄不是填空**；(b) `verdict.exposure` ＝ **配置油門帶**（持股區間），⛔ **不是動能**（線框「動能」欄示意值為 `M1B-M2 +1.2`），三欄無一欄收得下；(c) **只有** `verdict.danger` ↔ `summary.risk` 語意相符。
⇒ **逐欄落地（依裁示逐字）**：(a)「位階」＝ `summary.regime` **既有、維持現接線**，⛔ 不得把 `verdict.regime` 搬過去（客戶明示「位階 ← summary.regime（既有）」）；(b)「動能」**維持未接線**，⛔ 不得拿 `verdict.exposure` 頂替（客戶明示「**exposure 不是動能，不搬**」）—— ⚠️ 本組延伸（⛔ 非客戶裁示）：未接線態依 ② 走 **#5**，⛔ 不得畫成 #1；(c)「風險」← `verdict.danger` **直接對映**。
⚠️ **`verdict.exposure` 與 `verdict.regime` 兩卡的最終去向＝開放項（⛔ 客戶未裁、⛔ 非本組判定）**：客戶只裁示「**不搬**」進 `today.summary`，**沒有裁示要刪**。⇒ ⛔ 不得自行判定刪除、⛔ 不得自行安排到第二層其他 block（`today.key_banner`／🆕`today.holdings`），**列為開放項待客戶裁示**。
⚠️ **「不得調和」未被本次裁決推翻**：第一層那顆燈的一句話結論是**新寫的字串**，⛔ 不得由三卡平均／取 worst／合成而來。

### 尚未判定（**只登記、本輪⛔ 不解**）

> 定義照 `CLAUDE.md §8.3`：「尚未判定」＝ **還沒判**，⛔ 不是「判了但沒做」。一旦判出結果就搬走。

**U-1｜`today.summary` 的 `cols 3/2/1` 到底是「block 內部欄數」還是「層級網格」—— 線框與原型的真矛盾**（2026-09-21 **登記，未判定**；登記者 WS1 規格組，⛔ 未經第二組複驗）

- **矛盾的一端（線框）**：`docs/v2/wireframe/wf_page_today.js:172` 逐字 `cols: { desktop: 3, tablet: 2, phone: 1 }`；同 block 的 `evidence`（`:186`）逐字「**【斷點】3 欄只在 >1280px 與 881–1280px 成立；641–880px 降成 2＋1（第三張自己一列佔滿寬），≤640px 單欄。上面 `cols.tablet:2` 指的是 641–880 那一段（881–1280 仍是 3）**」⇒ 讀起來是「**三格／三張東西在一個 block 內並排**」。
- **矛盾的另一端（原型）**：`docs/v2/prototype/ui_prototype_today.html:307-322` 把 `today.summary` 畫成 **一張 `.blk.t2` 卡**（`<section class="blk t2" aria-labelledby="s-t">`），卡內一個 `.stack` 裝 **3 條 `.rowline`（位階／動能／風險）垂直堆疊**，且該卡本身是 `.g3` 的**第一個子元素**（`:304` `<div class="g3">`）⇒ 讀起來是「**`3/2/1` 描述的是 `.g3` 這個層網格**，卡內根本沒有三欄」。
- **兩端都不是猜的**：兩處皆為本組逐行實測（非轉錄）。
- ⚠️ **相鄰的第三個資料點（同一個語意問題、本輪一併登記，⛔ 本輪不動其值）**：`today.statusbar` 線框 `cols 1/1/1`（本檔 `:20`）、內容卻是「**3 張狀態卡**」；實作 `page_today.py:1892 render_cards(build_status_bar_cards(...))` **未傳 `cols`**，吃 `_ui_kit.py:360` 的預設 `cols=MAX_COLS`＝**3**，原型 `:239` 也把這三張放進 `.g3`（3 up）。⇒ **`cols` 的語意在 `today.statusbar` 上同樣對不起來。** 本輪**只記錄**，⛔ 不動 `BLOCK_COLS["today.statusbar"]`、⛔ 不據此推翻任何既有值。
- 🔴 **為什麼本輪不解**：解它會**改變 `today.summary` 的形狀**（一張卡內三條 vs 三張並排卡），屬 `CLAUDE.md §-1.5.D §03-2 ①`「**任何版面佈局（Layout）、欄位增減或分頁動線異動**」⇒ **必須先出文字線框草稿送客戶拍板**，⛔ 不是內部自決項。
- ⛔ **不得**以「規格要統一 `cols` 語意」為由逕自改掉任一端 —— 那正是 §03-2 ① 要擋的事。
- ✅ **本輪對 `today.holdings` 的填補不受本矛盾影響**：兩種讀法下它都是 `1/1/1`（卡內無網格；而「層網格」是**層**的屬性、不是單一 block 的屬性）—— 但這句話本身是 **WS1 單組判定，⛔ 未經第二組複驗**（`CLAUDE.md §-2` 規則 6）。
- **下一步（⛔ 非本輪動作）**：依 `CLAUDE.md §-2` 規則 4，**由獨立一組**（⛔ 不可是想動手的那一組）先查證兩端何者為客戶核准過的形狀，再依 §03-2 ① 出草稿。

## ④ 反例自檢

**A. 資料全部抓取失敗**（上游皆拋例外 ⇒ `requested=True` ＋ `error` ⇒ 序 4 `UI_FAILED`）
- 葉外 `today.statusbar`：🔴 總經狀態讀取失敗（附錯誤型別）；Sheet 欄位維持原樣。
- 第一層 `today.verdict`：**#6 🔴 取得失敗**，大字區**留白**（`render_card` 灰態與紅態一律留白），
  ⛔ 不得顯示 `0` 或上一輪殘值；分母句照出（`_cov.text()`）。
- 第二層：`today.summary` 三格各自 #6（**逐格獨立判態**，一格壞不染色另兩格）；`today.key_banner` #6；
  🆕 `today.holdings` 取不到清單 ⇒ `n_classified==0` ⇒ **#7 缺漏 · 可重跑**（Sheet 失敗可重試），
  ⛔ 不得顯示「完美分散」或 `0`。
- 第三層 `today.actions`：主 CTA **可按**，說明字「**可以重試** —— 上游這輪失敗，不是程式錯誤。」
  ⚠️ 例外：`MISS_CONTRACT_DRIFT`（契約漂移，在 `FAILED_REASONS` 內）⇒ 按鈕**停用**＋
  「🔴 重按不會好，程式要修，請回報。」⛔ 不得對契約漂移給「可重跑」指引。
- 第四層：`today.warroom` #6；`today.detail` 五桶**逐桶**判態，一桶失敗**其餘四桶維持原樣**，
  ⛔ 不拿估計值頂替（`INDICATOR_SPEC` R-2「任一輸入是缺漏時不得往下算」）。

**B. 只有部分成功**
- 依 ② 落差 3：分子分母拿不到 ⇒ **恆降級 #7**，⛔ 不得退回 #1「正常」（缺資訊往保守側退）。
- 已有值的格子照畫 #1／#4；沒拿到的格子畫 #7（`⚠︎ —` 缺漏 · 可重跑）或 #8（`N/A` 不適用 · 重跑無效），
  **二者以 `miss_reason` 分辨、⛔ 不得只靠顏色**（兩者同屬灰系，`INDICATOR_SPEC` R-3）。
- `degraded` 的格子：**觀測照出、判決留白** —— 有值就印值 ＋ #4 🟠「門檻已失準」，
  ⛔ 不因為門檻失效就把值藏起來，也⛔ 不照失效門檻判燈。
- 冷啟動（`requested=False`）：一律 **#3 ⬜ 尚未載入** ＋ 灰色說明，
  ⛔ **不得畫成紅色錯誤**（`CLAUDE.md §1.A` 第 4 點：把「還沒載入」畫成故障＝捏造一個不存在的故障）。
- ⛔ 全域：缺值一律不顯示為 `0`；`(None, None)` 與 `(值, MISS_*)` 為非法二元組，收到當 `MISS_CONTRACT_DRIFT`。

---
⚠️ **複驗分級**
**客戶裁示（2026-09-16）＝ 已決，⛔ 非任何一組判定**＝③「3 卡歸位到第二層的哪一張」**已移出待裁**（原標「待客戶再裁」撤銷）：位階＝`summary.regime` 既有／動能維持未接線（`exposure` 不搬）／風險←`danger` 直接對映。⚠️ 下列 WG 實查的**三條事實**（`verdict.regime`↔`summary.regime` 同源、`exposure`＝持股區間非動能、只有 `danger`↔`risk` 相符）**正是客戶據以裁示的依據，⛔ 不得刪**；`exposure`／`regime` 兩卡去向**客戶未裁，為開放項**。
**總管實查**＝線框 `layers` 結構（4 層／8 block／`states` 10 鍵，node 實際解析）與 `mainCTA` 逐字、~~`持倉健檢` 全 repo 0 命中~~、`stock_watchlist` 三欄 schema。
⚠️ **2026-09-21 事實更正，⛔ 不是漏刪**（決策者 AI 總管）：刪除線該項**自 2026-09-16 15:20 起不成立**（原型 `d21d1ca` 帶入，現命中 `ui_prototype_today.html:337`／`:340`）。**⛔ 不要讀成「當時查錯」** —— 它在寫下的那一刻（`eec3c70`，2026-09-16 10:19）是真的，理由與現行讀法見 ① `today.holdings` 條目下的同一則更正。**該次實查的其餘三項未受影響。**
**總管實查（2026-09-21 本輪新增）**＝原型 `.g3` 三斷點 CSS（`ui_prototype_today.html:127-128`／`:195`／`:199`）；`持倉健檢` 現行命中點與其 commit 來歷（`d21d1ca` vs `159e264`）；`STATE.md` 對「原型」／`prototype` 0 命中；`docs/v2/HANDOFF_UI_2026-09-16.md:34`「客戶確認今天頁原型的視覺方向 ← 停在這裡」。
**WS1 規格組本輪實查（2026-09-21）**＝`_ui_kit.py:144-157` `grid()` 的 `min(cols, MAX_COLS)` ＋ 逐列 `st.columns(len(chunk))`；`_ui_kit.py:360 render_cards(cards, cols=MAX_COLS)` 的**預設值 3**；`UI_COMPONENTS.md:114`→`:124`→`:126`→`:128-129` 的「4 對」主語鏈；原型 `:239`／`:304`／`:399` 三處 `.g3` 的用法。
⚠️ **WS1 本輪的判定（⛔ 單組、未經第二組複驗，⛔ 不得當既定前提）**＝「`cols` ＝ block 內部一列幾格」這個語意在**全部八個 block 上一致**這件事 —— 本組實測到**一個反例**（`today.statusbar`），已列入下方「尚未判定」。
**WF 本組實查（2026-09-16）**＝`classify_ui_state` 序 3 可產生 `loading`、`in_flight`／`st.spinner`／`emits_level` 在 `page_today.py` 皆 0 命中、`MAX_COLS＝3`、`render_card` 26px／32px chrome。
**WG 本組實查（2026-09-16，修訂組）**＝③ 段 `today.verdict` 已決段所引的一切落點：線框 `today.summary` 的 `name`／`src`（`wf_page_today.js:171`）、實作 `summary.regime`／`summary.momentum`／`summary.risk` 三欄與其接線狀態（`tab_today.py:407-440` ＋ `page_today.py:1916-1917`）、`verdict.exposure`／`danger`／`regime` 三卡標籤與 docstring（`page_today.py:1324`／`:1357`／`:1393`／`:1432`／`:1264`）。⛔ 39.5%／18 組兩數為沿用原文，不在本組實查內。
**WF 本組推導（⛔ 不是量測，⛔ 不得當實測引用）**＝654／532px 應然網格值 —— 其排版模型（CSS auto-fit）不適用本頁（`st.columns`），理由見 ① 「排列（三斷點）」段。
**INV-5 單組（未複驗，⛔ 不得當前提）**＝其餘盤點與所有「0 命中」類全稱句（皆單次 grep，**未做 AST**）、線框與實作的差異清單、「首屏三斷點算不出來」該項判定。
**轉錄（非任何一組實測）**＝`CHECKPOINT.md:87` 的 12,075 字。
