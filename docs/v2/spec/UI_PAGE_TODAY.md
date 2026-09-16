# UI_PAGE_TODAY —— 「🚦 今天」頁完整版面（第 3 份）

**基準**：線框 `docs/v2/wireframe/wf_page_today.js`（客戶審過）＝版面來源；元件一律引用第 2 份 `UI_COMPONENTS.md`、token 一律引用第 1 份 `UI_TOKENS.md`（⛔ 本檔不改這兩份、⛔ 不新造元件類型）。
實作對照 `src/ui/views/page_today.py::render_page_today()`。斷點沿用第 2 份 `≤640 / 641–880 / ≥881`（CSS 現況不一致已由第 2 份登記為實作待修，本檔不重述）。
⚠️ 本檔為 UI 設計組 WF 單組產出，未經第二組複驗（§-2 規則 6）；**全檔免責只講這一次**。

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

**第一層 `today.verdict`**（線框 `cols 1/1/1`）：徽章 #1／#3／#4／#5／#6／#7。⚠️ 線框是 **1 格結論燈**、實作是 **3 張並排卡** —— 兩種形狀的分歧見 ③，本層排列依客戶拍板結果定。

**第二層**（`⛔ 卡片本身不可點`，線框 n2 層標籤逐字）：⛔ 本層不得放任何按鈕、連結、`st.popover`。
- `today.summary` 三欄摘要（位階／動能／風險），線框 `cols 3/2/1`，徽章 #1／#3／#4／#5／#6／#7／#8／#9。
- `today.key_banner` 今日關鍵橫幅，線框 `cols 1/1/1`，實作 `_render_tiles(..., cols=1)`。
- 🆕 **`today.holdings` 持倉健檢 —— 新訂**（線框 `n2` **未定義**此 block；`持倉健檢` 全 repo 0 命中）。
  填入線框 n2 自己寫的「核心大卡片 **3~4 格**」預留位；⛔ 不得寫得像既有元件。
  組成**只用既有元件**：卡 `.blk.t2` ＋ `.sbadge b2` ＋ `UI_COMPONENTS` §2 徽章，⛔ 無按鈕（不可點）。
  🔴 **資料限制（硬規則）**：持股來源 `stock_watchlist` 的 schema **只有 `name`／`ticker`／`updated_at` 三欄**（`src/data/portfolio/gsheet_portfolio.py:88`，`:85` 註解逐字「§1 反捏造:此分頁**只**存 name/ticker/updated_at 三欄,無張數/均價」）⇒ **這張卡拿不到部位大小**。`src/compute/risk/concentration.py` 因此一律 `basis='equal_weight'`（`:68 BASIS_EQUAL_WEIGHT`）並要求 UI 揭露該假設（`:136` 欄註「UI **必須**據此標註假設」）。
  **可顯示**（皆由檔數推得）：`n_total`／`n_classified`／`n_unclassified`／`n_industries`／`coverage_pct`／`top1_pct`／`top3_pct`／`hhi`／`n_eff`，**＋ 等權假設揭露句一行（必填，`--ink-3` `11.5px` 說明字級）**。
  ⛔ **不得顯示**：損益、部位佔比、金額、張數、均價，或任何需要張數／均價才算得出來的量。
  ⚠️ `top1_pct` 標籤逐字為「**最大單一產業（檔數等權）**」，⛔ 不得標成「部位佔比」。
  `is_computable=False`（`n_classified==0`）→ 徽章 **#7 缺漏 · 可重跑**，⛔ 不得顯示 `0` 或「完美分散」。

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

**同一 block 兩種形狀（設計分歧，⛔ 本檔不選邊，待客戶拍板）**
`today.verdict`：**線框讀法**＝`cols 1/1/1`、`name` 逐字「① 結論燈」，一格一顆燈，`t1` 密度最大化單一結論；**實作讀法**＝**3 張並排卡**（`verdict.exposure`／`verdict.danger`／`verdict.regime`，`:1357/:1393/:1432`），
docstring 逐字「**不平均、不取 worst、不合成一顆燈**」，依據是 `overall_verdict()`（危險度，不含方向）與 `get_macro_regime()`（市場位階）實跑燈色不一致 39.5%、方向相反 18 組，客戶 2026-08-27 裁示**並列揭露、不得調和**。
⇒ 兩種讀法**不可兼得**：合成一顆燈會踩到「不得調和」；維持三張卡則線框 `cols 1/1/1` 與 `name` 要改。
**客戶拍板前，第一層排列與卡數懸而未定。**

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
**總管實查**＝線框 `layers` 結構（4 層／8 block／`states` 10 鍵，node 實際解析）與 `mainCTA` 逐字、`持倉健檢` 全 repo 0 命中、`stock_watchlist` 三欄 schema。
**WF 本組實查（2026-09-16）**＝`classify_ui_state` 序 3 可產生 `loading`、`in_flight`／`st.spinner`／`emits_level` 在 `page_today.py` 皆 0 命中、`MAX_COLS＝3`、`render_card` 26px／32px chrome。
**WF 本組推導（⛔ 不是量測，⛔ 不得當實測引用）**＝654／532px 應然網格值 —— 其排版模型（CSS auto-fit）不適用本頁（`st.columns`），理由見 ① 「排列（三斷點）」段。
**INV-5 單組（未複驗，⛔ 不得當前提）**＝其餘盤點與所有「0 命中」類全稱句（皆單次 grep，**未做 AST**）、線框與實作的差異清單、「首屏三斷點算不出來」該項判定。
**轉錄（非任何一組實測）**＝`CHECKPOINT.md:87` 的 12,075 字。
