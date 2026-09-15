/* ════════════════════════════════════════════════════════════════════════
   wf_page_fund.js — 線框資料檔（純資料，無渲染邏輯）

   🔴🔴 ⚠️ 檔名與內容自 2026-09-14 起**刻意不一致**，讀本檔請**一律以「內容」為準**：

      【現況】本檔**只有一頁**：`id:'rebalance'` ⚖️ ETF 再平衡偏離提示。
              **⛔ 不含任何基金頁面、⛔ 不含任何基金資料**（2026-09-15 實測：
              本檔 `window.WF_PAGES.push` 之後的**資料段**掃「基金」→ **0 命中**）。
              檔名裡的 `fund` **只剩歷史意義** —— 它記錄的是「這個檔曾經裝過哪一頁」。

      【為什麼不改名 —— 四條，⛔ 一條都沒有失效】
        (1) 🔴 **改名會讓組裝失敗（最硬的一條）** —— 組裝腳本以**字面路徑**
            `'./wf_page_fund.js'` require 本檔（實測 `_assemble2.js:2-3` 的 FILES 陣列
            ＋ `_assemble.js:2` ＋ `_assemble_live.js:3-4`，**三支都寫死**）。
            改名 ⇒ `LOAD FAIL` ⇒ 整份草稿組不出來。
        (2) **改名動到別組的檔案邊界** —— 那三支組裝腳本不是本組的檔。
        (3) **改名是純 cosmetic、卻要動到每一個 caller** —— 正是 CLAUDE.md §8.1 step 6
            點名的反例（用不到的抽象／為整齊而動全場）。
        (4) **改名沒有經過 §8.4 step 4 的範圍 gate** —— 那是「要不要順便做」的範圍問題，
            **範圍問客戶**，⛔ 不是內部順手可以決定的。

      ⛔ **不要依檔名推測內容**；⛔ **也不要為了「名實相符」順手改名。**
      ⚠️ **這個誘惑在 2026-09-15 之後變大了**（本檔已經一點基金都不剩，
      「順手改個名字」看起來更無害）—— **看起來無害 ⛔ 不等於在射程內**。
      要改名就照 (4) 另外提案。

   內含一頁：
     id:'rebalance' ⚖️ ETF 再平衡偏離提示
                    落點：股票/ETF 戰情室 › 頁4「💼 我的持股」› 葉1 ⑤-b
                    （本頁是戰情室內的一個區塊，不是獨立分頁）

   ────────────────────────────────────────────────────────────────────────
   修訂紀錄
   ────────────────────────────────────────────────────────────────────────
   2026-09-15｜🔴 **基金清除組（本輪，最新）** —— ⭐ **只清字樣與檔頭，⛔ 不是設計變更。**

     ⛔ **未動任何設計**：版面、元件、狀態模型、徽章一格未改；本頁 `id`／`tab`／`subtitle`／
        `mainCTA`／`leaves`／`cols`／`flags`／全部 block 的 `key`／`name`／`states` 十格
        **一格未改**。⛔ 未動 repo 任何檔案、⛔ 未 git 寫入、⛔ 未動 `warroom_ia_v2.html`。
        `node --check wf_page_fund.js` 通過；`node _assemble2.js` 契約健檢全過、
        本頁區塊數 **18 未變**。

     🔴 **來歷：客戶 2026-09-15 第二次明示「移除基金」** ＋「偏離表與已知限制…
        是內部文件，不應出現在使用者介面」。
        ⭐ **解讀：客戶要的是「畫面上看不到基金」，⛔ 不是「把查證過的事實銷毀」。**

     ✅ **⛔ 未移除 ⚖️ 再平衡頁** —— 依客戶母法「**所有 ETF 實體與運算歸屬股票／ETF 戰情室**」，
        再平衡是 **ETF**、⛔ 不是基金。本輪**一個 block 都沒有刪**。

     🔧 **本輪只動兩個 block 的 `evidence` 與 `src`**（**畫面文字 `states` ⛔ 一格未動**）：
        · `rebalance.l4.cost_basis`            — evidence ＋ src
        · `rebalance.l4.cross_site_unrealized` — evidence ＋ src
        兩者的 evidence 原本在**記錄 2026-09-14 那次改寫的來歷**，因而寫出了另一站的頁名。
        本輪把頁名改成「**另一站／其所屬頁面已不在本稿範圍內**」，並指向封存檔。
        ⭐⭐ **被改寫的只有「頁名」，⛔ 不是事實** —— 兩條 evidence 的
        **台股側 file:line 實測、⛔ 未擱置的宣告、處置來歷 (a)(b) 的區分、單組未複驗揭露**
        **一字未減**；改寫前的**逐字原文**存於封存檔
        `scratchpad/wf_fund_archive.md`（D 段，含恢復條件）。

     📌 **檔頭（本註解）的「基金」字樣 ⛔ 刻意保留，這不是漏清**：
        (a) **檔頭是 JS 註解，⛔ 不會被組裝、⛔ 不會被渲染** —— 客戶在畫面上看不到它
            （`_assemble2.js` 只讀執行期的 `window.WF_*` 物件）；
        (b) **檔名叫 `fund`，檔頭必須解釋為什麼** —— 把這裡也清掉，
            下一個人會完全看不懂這個檔為什麼叫這個名字；
        (c) **⛔ 不改別組的修訂紀錄** —— 下方 2026-09-14 那一輪的紀錄是**別組的紀錄**，
            本輪一字未動。
        ⇒ **本輪的「0 命中」宣稱只涵蓋「會被組裝進草稿的資料段」**，
        ⛔ **不涵蓋本註解**。（CLAUDE.md §-2 規則 6：⛔ 不寫沒查證的全稱句。）

     ⚠️ **本輪由基金清除組單組執行，未經第二組複驗**（CLAUDE.md §-2 規則 6）。

   ────────────────────────────────────────────────────────────────────────
   2026-09-14｜範圍變更落實組（前輪）

     🔴 **移除 id:'fund'（🧾 基金儀表板）整頁 —— 原 22 個 block 全數自本稿移除。**
        **來歷：客戶 2026-09-14 明示指令，逐字「移除基金」。**
        ⚠️ 這是**客戶明示**，⛔ 不是總管拍板 —— 兩者的來歷不同，⛔ 不得混寫
        （CLAUDE.md §-2 規則 6）。本項已登記於 `wf_global.js` 的 WF_DEVIATIONS。

     ✅ **保留 id:'rebalance'（⚖️ 再平衡偏離提示）。**
        依客戶母法「**所有 ETF 實體與運算歸屬股票／ETF 戰情室**」，再平衡是 **ETF**、
        不是基金；它的落點本來就在戰情室 頁4 葉1 ⑤-b（見 rebalance.page.position，
        該 block 的 evidence 附 page_hold.py 逐字實測）。
        ⚠️ **來歷不同，據實標明**：「移除基金」是**客戶明示**；
        「再平衡不隨基金一起移除」是**總管依母法的解讀**，客戶本輪未就此逐字表示。
        ⇒ 這一句只能當**總管解讀**，若解讀有誤請客戶直接推翻。

     🔧 **連帶改寫兩個 block**（原因：它們原本引用的對象已不存在）：
        · `rebalance.l4.cost_basis`            — 由「兩站都放（★-14a）」改寫為**單站版**
        · `rebalance.l4.cross_site_unrealized` — 由「跨站同名不同義」改寫為**單站限制**
        ⭐ **兩者被改寫的都只有「跨站」那一半；台股站自己的限制依然成立，
           內容 ⛔ 未被擱置、⛔ 未被刪除。** 原文與改寫理由逐格寫在該 block 的 evidence。

     📌 **Deep Link 動線（基金站 → 戰情室）：本頁沒有引用，故本輪無須改寫。**
        射程：本組對本檔 rebalance 段（改版前的 500–890 行）grep 了
        `Deep Link` / `deeplink` / `跨站` / `兩站` / `基金` / `fund.` 六個字串，
        除上述兩個 block 外 **0 命中**。
        ⚠️ **單組、單次、六個關鍵字，非窮舉** —— 依 §-2 規則 6，這句只能當待驗事項。
        🔴 **「Deep Link 目前是斷的」這個技術事實 ⛔ 沒有被刪掉** ——
        接收端只認純數字代號、且收下來全 repo 0 處讀取，**那仍然是 repo 現況**，
        只是**不再因為基金站而需要修**。已保留並註明於 `wf_global.js` 的 WF_LIMITS。

     ⛔ 本輪 ⛔ 未動任何 repo 檔案、⛔ 未執行任何 git 寫入、⛔ 未動其他 `wf_*.js`、
        ⛔ 未動 `warroom_ia_v2.html`（別組的檔案邊界）。

   內容來源（唯一依據，本檔不發明畫面）：
     主  scratchpad/S1-3B_FULL_DRAFT_SPEC.md  Part 5（再平衡）
     輔  S1-5_HOLDINGS_MODEL.md ／ S1-4_STATE_MATRIX.md(v2) ／ S1-6_COMPLIANCE_COPY_GUIDE.md
     碼  股票 repo /home/user/my-stock-dashboard
     ⚠️ 原檔的「Part 4（基金站）」與「基金 repo（唯讀，HEAD 9cbf037）」兩項來源，
        已隨基金頁移除而不再是本檔的依據。
        ⛔ **但那不代表當初讀到的事實是假的** —— 已查證的基金側事實（同類型平均不是
        中位數、基金站未實現損益含匯兌、四頁待實地盤點…）**已保存**於
        `wf_global.js` 的 WF_LIMITS，標記「因基金站移除而擱置」，日後恢復時可取回。

   母法釘死的分工（不得改）：
     **所有 ETF 實體與運算歸屬股票／ETF 戰情室。** —— 這半句仍然有效，本頁即依它保留。
     ⚠️ 同一句的後半「基金儀表板只以收益視角摘要卡片唯讀引用持倉、呈現配息與佔比、
     點擊 Deep Link 跳轉到戰情室看明細」，在本稿**已無載體**（基金頁已移除）。
     ⛔ **這不是本組判定它失效** —— 那一半何時恢復，取決於基金站是否回來，
     不在本輪的射程內（基金 repo 不在本 session 範圍內）。

   states 十鍵 ＝ S1-3B Part 2.5.1 的十種呈現情況（不適用者填 null）：
     live 正常／loading 載入中／idle 未載入／empty 查無資料／missing 缺漏／
     partial 涵蓋不全／degraded 門檻失準／unwired 未接線／na 結構不適用／error 錯誤

   cols ＝ S1-3B Part 2.8 定案表：>1280→3、881-1280→3、641-880→2、<=640→1

   ⚠️ 本檔由線框資料組單組產出，未經第二組複驗（CLAUDE.md §-2 規則 6）。
      evidence 欄內「實測」字樣者為產出組親自讀出；「規格」字樣者為轉錄；
      兩者請分開看待。**本輪（範圍變更）同為單組產出，同樣未經第二組複驗。**
   ════════════════════════════════════════════════════════════════════════ */

window.WF_PAGES = window.WF_PAGES || [];

/* ──────────────────────────────────────────────────────────────────────
   本檔唯一一頁｜⚖️ 再平衡（偏離提示）
   （原標「頁二」—— 2026-09-14 移除另一頁後本檔只剩這一頁，標號隨之更正。
     ⚠️ 更正的只有標號：本頁的內容、落點、母法紅線一字未動。）
   位置：股票/ETF 戰情室 › 頁4「💼 我的持股」› 葉1 ⑤-b
   母法紅線：⛔ 一鍵再平衡　⛔ 預設最佳配置推估　✅ 只做偏離提示／客觀對照／情境試算
   ────────────────────────────────────────────────────────────────────── */
window.WF_PAGES.push({
  id: 'rebalance',
  tab: '⚖️ 再平衡（偏離提示）',
  subtitle: '你實際的比例 vs 你想要的比例。只做三件事：偏離提示、客觀對照、情境試算。⛔ 沒有一鍵再平衡按鈕、⛔ 系統不預填任何目標比例。',

  mainCTA: {
    label: '🚀 跑存股戰情室',
    src: 'my-stock-dashboard（股票 repo）src/ui/views/page_hold.py:388（ACTION_RUN_WARROOM_LABEL，實測逐字）'
  },

  leaves: [],

  layers: [

    /* ═══ 第 0 層｜區塊定位與頁尾 ═══ */
    { n: 0, label: '第○層｜區塊定位與頁級常駐', blocks: [

      {
        key: 'rebalance.page.position',
        name: '本區塊的位置（⑤-b，掛在戰情室葉1 之下，不是獨立分頁）',
        leaf: '葉1 戰情室（1️⃣~6️⃣ ＋ 80/20 配置偏離）',
        cols: { desktop: 1, tablet: 1, phone: 1 },
        states: {
          live:     '⑤ 上半 ＝ ⑤-a 80/20 配置偏離（目標來源：系統常數）；⑤ 下半 ＝ ⑤-b 逐檔再平衡偏離（目標來源：使用者自己填）',
          loading: null, idle: null, empty: null, missing: null,
          partial: null, degraded: null, unwired: null, na: null, error: null
        },
        asOf: null,
        evidence: '實測（股票 repo）葉名逐字：src/ui/views/page_hold.py:391 `LEAF_WARROOM_TITLE: str = "戰情室（1️⃣~6️⃣ ＋ 80/20 配置偏離）"`、:392 `LEAF_SETUP_TITLE`。⛔ 鐵律：不得把 ⑤-a 與 ⑤-b 的偏離數字放在同一張表 —— 讀者會以為 80/20 那個「目標」也是自己填的（S1-3B:2846）。',
        src: 'my-stock-dashboard（股票 repo）src/ui/views/page_hold.py:391-392；規格 scratchpad/S1-3B_FULL_DRAFT_SPEC.md:2834-2846',
        flags: []
      },

      {
        key: 'rebalance.page.footer_disclaimer',
        name: '頁尾免責（D-1，每頁常駐）',
        leaf: '葉1 戰情室（1️⃣~6️⃣ ＋ 80/20 配置偏離）',
        cols: { desktop: 1, tablet: 1, phone: 1 },
        states: {
          live:     '⚠️ 僅供學術研究，非投資建議，盈虧自負',
          loading: null, idle: null, empty: null, missing: null,
          partial: null, degraded: null, unwired: null, na: null, error: null
        },
        asOf: null,
        evidence: '規格 S1-3B:853 D-1。',
        src: 'scratchpad/S1-3B_FULL_DRAFT_SPEC.md:853',
        flags: []
      }

    ]},

    /* ═══ 第 1 層｜狀態分岔與結論句 ═══ */
    { n: 1, label: '第一層｜三分岔結論（依「有沒有目標比例」）', blocks: [

      {
        key: 'rebalance.l1.state_router',
        name: '結論句 ＋ 三分岔（A 未設定／B 已設定／C 總和≠100%）',
        leaf: '葉1 戰情室（1️⃣~6️⃣ ＋ 80/20 配置偏離）',
        cols: { desktop: 1, tablet: 1, phone: 1 },
        states: {
          live:     '🟠 N 檔裡有 M 檔偏離超過你設定的容忍範圍（±X.Xpp）。（純門檻關係句，無行動半）',
          loading:  '⏳ 載入中／「正在取報價計算目前比例…」⛔ 不顯示上一輪的偏離值',
          idle:     '⬜ 尚未執行 —— 按「🚀 跑存股戰情室」才會開始讀',
          empty:    '▨ 無資料：你的帳本裡沒有任何持股，沒有比例可以算 ＋ 指路「到本頁『組合設定』新增持股」',
          missing:  '▨ 狀態 A（尚未設定目標）或 狀態 C（總和≠100%）—— 兩者都⛔ 不顯示偏離數字，但文案不同（見第三層兩個獨立區塊）',
          partial:  '🟢 但值帶 * ：N 檔中 M 檔缺報價，目前比例以其餘檔重新歸一計算 ＋ 缺報價那幾檔單獨列出，⛔ 不靜默剔除',
          degraded: '🟠 容忍範圍的門檻已失準（若容忍值來自 SSOT 而該 spec 標 discriminative=False）：值照給，判讀語留白',
          unwired:  '⛔ 本區塊目前無此情況（偏離計算不走 DangerSpec）',
          na:       '▨ N/A：你的持股只有 1 檔，單一持股沒有再平衡的概念（比例恆為 100%）',
          error:    '🔴 取得失敗：報價來源連線失敗，無法計算目前比例 ＋「按『🚀 跑存股戰情室』重試」'
        },
        asOf: null,
        evidence: '規格 S1-3B:2560-2582（三分岔流程圖）＋ :2817-2832（⑤-b 逐狀態矩陣，十格逐字）。⚠️ Off-Market 那一格已由客戶拍板一撤下 → 改為時點揭露「以 MM-DD 收盤價計算比例」，放在情境試算的限制列與表格 footer（S1-3B:2832）。',
        src: 'scratchpad/S1-3B_FULL_DRAFT_SPEC.md:2560,2817,2832',
        flags: []
      },

      {
        key: 'rebalance.l1.no_fake_green',
        name: '⭐ 本區最重要的一條：沒有目標就沒有偏離（⛔ 不准印 0.00）',
        leaf: '葉1 戰情室（1️⃣~6️⃣ ＋ 80/20 配置偏離）',
        cols: { desktop: 1, tablet: 1, phone: 1 },
        states: {
          live:     '目標未填完之前，偏離欄一律 ▨ 未設定 —— ⛔ 不得顯示 0.00。舊分頁的失效模式是「拿現況當目標」→ 偏離度恆等於 0.0% → 永遠顯示綠燈，而那個綠燈代表「沒算」而不是「已平衡」',
          loading: null, idle: null, empty: null, missing: null,
          partial: null, degraded: null, unwired: null, na: null, error: null
        },
        asOf: null,
        evidence: '本組實測（股票 repo）src/ui/etf/etf_tab_portfolio.py:419-421 註解逐字「原碼:`target_pct = actual_pct` → `deviation` 恆 0 → 再平衡永遠印「✅ 所有標的偏離度均在 ±5% 內」。那個綠燈代表「沒算」不是「已平衡」。」；:297 現行已改為 `target_pct_user: _tgt_user,   # None = 使用者沒填(§1:不拿現況冒充目標)`；:298 `target_pct: None,  # 下方依 gate 結果決定要不要填`。⇒ 根因已修，本線框的任務是把「未設定」這個狀態在畫面上表達正確。憲法 §1：那個假綠燈是禁止的造假。',
        src: 'my-stock-dashboard（股票 repo）src/ui/etf/etf_tab_portfolio.py:297-298,419-421；規格 scratchpad/S1-3B_FULL_DRAFT_SPEC.md:2584-2587',
        flags: []
      }

    ]},

    /* ═══ 第 2 層｜客觀對照 ═══ */
    { n: 2, label: '第二層｜客觀對照（三個量測值，非買賣建議）', blocks: [

      {
        key: 'rebalance.l2.objective_compare',
        name: '客觀對照三列（容忍範圍／超出檔數／最大偏離）',
        leaf: '葉1 戰情室（1️⃣~6️⃣ ＋ 80/20 配置偏離）',
        cols: { desktop: 3, tablet: 2, phone: 1 },
        states: {
          live:     '· 你設定的容忍範圍：±X.Xpp（可於下方調整）　· 超出容忍的檔數：M / N　· 最大偏離：〈標的〉 +X.XXpp　⚠️ 以上為客觀對照，非買賣建議',
          loading:  '⏳ 載入中；三列值留空',
          idle:     '⬜ 尚未執行；三列值留空',
          empty:    '▨ 無資料：帳本內沒有持股',
          missing:  '▨ 狀態 A／C：三列一律不出現（沒有偏離可以統計）',
          partial:  '🟢＋* ：分母以「有報價的檔數」計，並在旁註明排除了哪幾檔',
          degraded: '🟠 容忍門檻已失準：容忍值照給，判讀語留白',
          unwired:  null,
          na:       '▨ N/A：單一持股沒有再平衡的概念',
          error:    '🔴 取得失敗；三列值留空'
        },
        asOf: null,
        evidence: '規格 S1-3B:2650-2655（客觀對照三列逐字 ＋ 末行「以上為客觀對照，非買賣建議」）。合規：三列都是量測值 ＋ 比較基準由讀者自己給（容忍範圍是使用者設的），行動半不存在 ⇒ 過 S1-6 §1.1 STEP 2 缺項填補測試；遮蔽檢查也過（遮住旁邊文字，「超出容忍 2 / 4」仍說得出判定門檻）。',
        src: 'scratchpad/S1-3B_FULL_DRAFT_SPEC.md:2650-2655',
        flags: []
      },

      {
        key: 'rebalance.l2.alloc_8020_coexist',
        name: '⑤-a 80/20 配置偏離（並存分層，與 ⑤-b 分屬兩張表）',
        leaf: '葉1 戰情室（1️⃣~6️⃣ ＋ 80/20 配置偏離）',
        cols: { desktop: 1, tablet: 1, phone: 1 },
        states: {
          live:     '⑤-a 的目標來源是系統常數（80/20），⑤-b 的目標來源是使用者輸入。兩者並存分層，⛔ 偏離數字不得放同一張表',
          loading: null, idle: null, empty: null, missing: null,
          partial: null, degraded: null, unwired: null,
          na:       '⑤-a 沒有「未設定目標」這個情況（目標是常數）；D-3 警語⛔ 不需要出現在 ⑤-a',
          error: null
        },
        asOf: null,
        evidence: '規格 S1-3B:2836-2846（⑤-a vs ⑤-b 對照表）＋ 附錄 B-10（:3070）：兩者是不同概念（資產類別配置 vs 個別標的權重），目標來源也不同（策略常數 vs 使用者輸入）；合併會讓「系統算出來的 80/20」與「你自己填的目標」在同一欄裡分不出來，正好踩到禁令 2。⚠️ B-10 自標「本判斷承重且未經第二組複驗」。⚠️ 另：⑤-a 現行文案有兩句直接命中禁用語，須一併改為偏離提示（S1-3B:2840、:3070）。',
        src: 'scratchpad/S1-3B_FULL_DRAFT_SPEC.md:2836-2846,3070',
        flags: ['★待拍板', '單組結論']
      }

    ]},

    /* ═══ 第 3 層｜三個狀態的表 ＋ 情境試算 ═══ */
    { n: 3, label: '第三層｜逐檔表（狀態 A／B／C）＋ 情境試算', blocks: [

      {
        key: 'rebalance.l3.state_a_unset',
        name: '狀態 A｜尚未設定目標比例（⛔ 一個偏離數字都不准出現）',
        leaf: '葉1 戰情室（1️⃣~6️⃣ ＋ 80/20 配置偏離）',
        cols: { desktop: 1, tablet: 1, phone: 1 },
        states: {
          live:     '欄位：標的／目前%／目標比例%（輸入欄）／偏離。現在怎樣：本區塊沒有任何偏離數字可以顯示。為什麼：再平衡是「你實際的比例」vs「你想要的比例」的比較，你的持股帳本目前只有 名稱／代號／張數／平均成本／更新時間 五欄，沒有「目標比例」。⛔ 系統不會替你預設一組目標比例 —— 那會變成一個沒有依據的配置推估。去哪補：在下方「目標比例%」欄自行填寫，總和需為 100%',
          loading:  '⏳ 表頭 ＋ 骨架列',
          idle:     '⬜ 尚未執行：不畫表頭',
          empty:    '▨ 帳本內沒有持股，表頭仍畫',
          missing:  '⭐ 本狀態即 ⑤ 缺漏：偏離欄一律 ▨ 未設定。⛔ 不得顯示 0.00、⛔ 不得顯示 —',
          partial:  null,
          degraded: null,
          unwired:  null,
          na:       '▨ N/A：單一持股沒有再平衡的概念',
          error:    '🔴 報價取得失敗，目前% 欄留空'
        },
        asOf: null,
        evidence: '規格 S1-3B:2589-2628（狀態 A 完整 ASCII 逐字）。⭐ 核心對比（:2625-2628）：合計列的「目標比例 0.00」是**真的算出來是 0**（四個空欄加總）；偏離欄**沒有值可以算**，所以是 ▨ 未設定。⛔ 偏離欄不得因為「反正是 0」就印 0.00 —— 那正是舊分頁的病。⛔ 輸入欄一律空白，不預填、不給參考配置（:2622-2623）。⛔ 不得有任何範例列：若要示範，用不可計算的佔位符〔＿＿＿＿〕，不放具名標的（:2699-2700）。',
        src: 'scratchpad/S1-3B_FULL_DRAFT_SPEC.md:2589-2628,2699',
        flags: []
      },

      {
        key: 'rebalance.l3.state_b_deviation',
        name: '狀態 B｜已設定目標比例（本區主體：偏離對照表）',
        leaf: '葉1 戰情室（1️⃣~6️⃣ ＋ 80/20 配置偏離）',
        cols: { desktop: 1, tablet: 1, phone: 1 },
        states: {
          live:     '欄位：標的／目前%／目標%／偏離(pp)／提示。提示欄只出三種：🟠 高於目標／🟠 低於目標／🟢 在容忍內 —— 全部是門檻關係，⛔ 不出現任何動作詞。合計列印 目前 100.00 ／ 目標 100.00 ／ 容忍 ±X.Xpp',
          loading:  '⏳ 表頭 ＋ 骨架列；⛔ 不顯示上一輪的偏離值',
          idle:     '⬜ 尚未執行：不畫表頭',
          empty:    '▨ 帳本內沒有持股',
          missing:  '該列缺報價 → 目前% 欄 ⚠︎ —，該列偏離欄 ▨ 不計算，並在表尾單獨列出',
          partial:  '🟢＋* ：目前% 以其餘有報價的檔數重新歸一，缺報價那幾檔單獨列出（⛔ 不靜默剔除）',
          degraded: '🟠 容忍門檻已失準：偏離值照給，提示欄留白',
          unwired:  null,
          na:       '▨ N/A：單一持股沒有再平衡的概念',
          error:    '🔴 逐列保留、列首標紅'
        },
        asOf: null,
        evidence: '規格 S1-3B:2630-2663（狀態 B 完整 ASCII 逐字）。⭐ 核心對比（:2647-2648）：偏離 0.00 是**有效的零**（真的剛好等於目標），與狀態 A 的 ▨ 未設定 長相完全不同 —— 這一組對比是本區的核心。合規：提示欄三種字面都只陳述「目前值相對於你設的目標落在哪一側」，過缺項填補測試。表尾必出時點揭露「以 MM-DD 收盤價計算比例」（:2832）。',
        src: 'scratchpad/S1-3B_FULL_DRAFT_SPEC.md:2630-2663,2832',
        flags: []
      },

      {
        key: 'rebalance.l3.state_c_sum_mismatch',
        name: '狀態 C｜目標比例總和 ≠ 100%（⛔ 不顯示偏離數字，文案與 A 不同）',
        leaf: '葉1 戰情室（1️⃣~6️⃣ ＋ 80/20 配置偏離）',
        cols: { desktop: 1, tablet: 1, phone: 1 },
        states: {
          live:     '▨ 目標比例總和是 XX.XX%，不是 100%。現在怎樣：本區塊⛔ 不顯示任何偏離數字。為什麼：目標比例要能構成一個完整組合才有意義；總和 92.00% 代表有 8.00% 沒有分配到任何標的 —— 在這種情況下算出來的「偏離」會系統性偏高，那不是你的組合真的偏離了，是目標本身還沒填完。去哪補：調整「目標比例%」欄使總和為 100.00%（容許 ±0.1pp）',
          loading:  '⏳ 表頭 ＋ 骨架列',
          idle:     '⬜ 尚未執行',
          empty:    '▨ 帳本內沒有持股',
          missing:  '⭐ 偏離欄一律 ▨ 不計算 —— ⛔ 不是 0.00、⛔ 不是 —。與狀態 A 的 ▨ 未設定 也不同：A ＝「你還沒填」；C ＝「你填了，但填的東西還不構成一個組合」。兩句話不同，⛔ 不得共用。合計列印 ⚠︎ 差 X.XX（缺漏符號 ＋ ⚠︎，因為那 X.XX% 該存在但不存在）',
          partial:  null,
          degraded: null,
          unwired:  null,
          na:       '▨ N/A：單一持股沒有再平衡的概念',
          error:    '🔴 報價取得失敗'
        },
        asOf: null,
        evidence: '規格 S1-3B:2774-2800（狀態 C 完整 ASCII ＋ :2796-2800 三句判準逐字）。實測（股票 repo）三態判定已在 L2 落地：src/ui/etf/etf_tab_portfolio.py:432-437 呼叫 src/compute/etf/portfolio_gates.evaluate_rebalance_gate，並以 STATUS_UNKNOWN 表達「沒設定 / 只設定一部分 / 總和 ≠ 100%」（:874-877 註解逐字「三態 —— 只有『已比對過使用者設定的目標且全部在容忍帶內』才給綠燈。沒設定目標 / 只設定一部分 / 總和 ≠ 100% → ⚪ 無法判定 + 明說缺什麼」）。⇒ 判定端已存在，本線框只規定它在畫面上長什麼樣。',
        src: 'my-stock-dashboard（股票 repo）src/ui/etf/etf_tab_portfolio.py:432-437,874-877；規格 scratchpad/S1-3B_FULL_DRAFT_SPEC.md:2774-2800',
        flags: []
      },

      {
        key: 'rebalance.l3.scenario_calc',
        name: '情境試算（Checkbox Gate：勾選後才計算，預設不跑）',
        leaf: '葉1 戰情室（1️⃣~6️⃣ ＋ 80/20 配置偏離）',
        cols: { desktop: 1, tablet: 1, phone: 1 },
        states: {
          live:     '☑ 顯示情境試算 → 表頭：標的／金額變化(TWD)／換算（參考）。首行必出「⚠️ 以下為試算，不是建議。系統⛔ 不產生下單清單，也⛔ 不代為執行。」題句寫成「若要讓每一檔回到你設定的目標比例，金額變化如下」—— 條件句，非祈使句',
          loading:  '⏳ 計算中；表格骨架',
          idle:     '☐ 顯示情境試算（未勾選）—— 灰色說明：勾選後才會開始計算，預設不跑',
          empty:    '▨ 帳本內沒有持股',
          missing:  '狀態 A／C 之下本區塊⛔ 不可勾選（沒有目標就沒有可試算的情境）',
          partial:  '缺報價的標的：該列金額變化 ⚠︎ —，並在表尾單獨列出',
          degraded: null,
          unwired:  null,
          na:       '▨ N/A：單一持股沒有再平衡的概念',
          error:    '🔴 報價取得失敗，本區塊不出數字'
        },
        asOf: null,
        evidence: '規格 S1-3B:2665-2690（情境試算完整 ASCII 逐字）＋ :2657-2659（預設不跑）。合規：題句是條件句（若要…則金額變化如下），把「要不要做」整個留給讀者，未代入任何讀者才有的變數 ⇒ 過 S1-6 §1.1 STEP 2。Checkbox Gate 屬 CLAUDE.md §-1.5.D §03-1 內部自決（畫面結構不變）。⛔ 本區沒有任何「一鍵套用」「全部再平衡」「產生委託單」按鈕（:2690）。',
        src: 'scratchpad/S1-3B_FULL_DRAFT_SPEC.md:2657,2665-2690',
        flags: []
      },

      {
        key: 'rebalance.l3.d3_notice',
        name: '⚠️ D-3 常駐警語：你在這裡填的目標比例目前不會被保存',
        leaf: '葉1 戰情室（1️⃣~6️⃣ ＋ 80/20 配置偏離）',
        cols: { desktop: 1, tablet: 1, phone: 1 },
        states: {
          live:     '完整版（桌機／平板）：⚠️ 你在這裡填的目標比例目前不會被保存 —— 重新整理頁面或關閉瀏覽器後需要重新填寫。（持股帳本目前沒有「目標比例」這個欄位，見下方佐證。）　｜　短版（手機 <640）：⚠️ 目標比例目前不會被保存（重新整理就要重填）　｜　情境試算展開區頂端：短版 ＋「本試算用的是你這一輪填的值」',
          loading: null, idle: null, empty: null,
          missing:  '狀態 A／B／C 三態都必出（本警語與偏離算不算得出來無關）',
          partial: null, degraded: null, unwired: null,
          na:       '⑤-a 80/20 不需要本警語（目標是系統常數，不需要保存）',
          error: null
        },
        asOf: null,
        evidence: '⭐ 客戶 2026-09-14 拍板二原話：「凡用到目標比例處，一律標明此限制尚未解除。」規格把警語從現況 2 處擴到 8 處（S1-3B:2738-2772 逐處列表：狀態 A／B／C 桌機各一、手機短版、平板完整版、情境試算頂端、葉2 組合設定持股列預覽、第四層佐證）。⚠️ 該八處是**依線框推導的落點，不是對 production 的窮舉**（S1-3B:2770-2772 自標單組；實測 grep target_pct src/ 另命中 portfolio_gates.py / portfolio_fx.py / etf_tab_portfolio.py 若干處未逐一判讀）—— 實作時請再獨立掃一次。',
        src: 'scratchpad/S1-3B_FULL_DRAFT_SPEC.md:855,2738-2772',
        flags: ['單組結論']
      }

    ]},

    /* ═══ 第 4 層｜展開佐證 ═══ */
    { n: 4, label: '第四層｜展開佐證（D-2／D-4 ＋ 技術原因完整版）', blocks: [

      {
        key: 'rebalance.l4.calc_limits',
        name: '▸ D-4　試算五條限制（必讀，試算表正下方）',
        leaf: '葉1 戰情室（1️⃣~6️⃣ ＋ 80/20 配置偏離）',
        cols: { desktop: 1, tablet: 1, phone: 1 },
        states: {
          live:     '· 未計入手續費、證交稅、匯費　· 未考慮最小交易單位（台股零股與整張的價差、流動性）　· 以 MM-DD 收盤價計算，實際成交價必然不同　· 此表不是下單清單。系統沒有下單功能，也不會有　· 試算不考慮稅務影響（已實現損益的課稅時點）',
          loading: null, idle: null, empty: null, missing: null,
          partial: null, degraded: null, unwired: null, na: null, error: null
        },
        asOf: null,
        evidence: '規格 S1-3B:2677-2688（五條逐字）＋ :858 D-4 落點表（情境試算展開後·第三層試算表正下方·展開後常駐）。',
        src: 'scratchpad/S1-3B_FULL_DRAFT_SPEC.md:858,2677-2688',
        flags: []
      },

      {
        key: 'rebalance.l4.why_not_saved',
        name: '▸ 為什麼目標比例不會被保存（技術原因完整版，D-3 第 8 處）',
        leaf: '葉1 戰情室（1️⃣~6️⃣ ＋ 80/20 配置偏離）',
        cols: { desktop: 1, tablet: 1, phone: 1 },
        states: {
          live:     '你的持股帳本（Google Sheet 的 portfolios 分頁）目前是 5 欄：名稱／代號／張數／平均成本／更新時間。沒有「目標比例」這一欄。⚠️ 而且即使加上第 6 欄，現行的存檔流程仍會把它清空 —— 存檔時是「整表清空、再照 5 欄重寫一次」，第 6 欄不在那 5 欄裡，所以每存一次就被擦掉一次，而且不會有任何錯誤訊息。⇒ 在存檔流程改成「依欄名取值」之前，這一欄只存在於你這一次的瀏覽器分頁裡。關掉就沒了。這不是你操作錯誤',
          loading: null, idle: null, empty: null, missing: null,
          partial: null, degraded: null, unwired: null, na: null, error: null
        },
        asOf: null,
        evidence: '🔴 本組獨立實測（股票 repo），三行逐字：src/data/portfolio/gsheet_portfolio.py:82 `_HEADERS = [name, ticker, lots, avg_price, updated_at]`（五欄，無 target_pct）；:381 `new_rows.append([name, tk, lots, avg, ts])`（**位置式、寫死 5 寬**）；:385-389 `ws.clear()` → `ws.append_row(_HEADERS)` → `ws.append_rows(keep_rows)` → `ws.append_rows(new_rows)`（整表清空再重寫）。⇒ header 若長成 6 欄而 :381 沒同步改，**每次存檔都會把剛編輯的那些列的第 6 欄清空，且沒有任何錯誤訊息**。⭐ 客戶已拍板「持股表加第 6 欄 target_pct」，但**此限制尚未解除**：規格把 M2 列為同一個 commit 的強制前置（改為 `[row_dict.get(h, "") for h in _HEADERS]`，依 header 取值非位置）。⚠️ 殘留風險無法用程式消除：舊版本 app（使用者另一台裝置、Streamlit Cloud 尚未 redeploy）仍跑舊碼，存檔時一樣會清空新欄 —— 這是部署期間的真實視窗，設計上無解。',
        src: 'my-stock-dashboard（股票 repo）src/data/portfolio/gsheet_portfolio.py:82,381,385-389；規格 scratchpad/S1-3B_FULL_DRAFT_SPEC.md:2702-2736,2754-2766；S1-5_HOLDINGS_MODEL.md:4.1 M1/M2',
        flags: ['★待拍板']
      },

      {
        key: 'rebalance.l4.cost_basis',
        name: '▸ D-2　加權移動平均法 vs FIFO（本站成本口徑揭露）',
        leaf: '葉1 戰情室（1️⃣~6️⃣ ＋ 80/20 配置偏離）',
        cols: { desktop: 1, tablet: 1, phone: 1 },
        states: {
          live:     '成本口徑揭露全文：本站的「成本」是用哪一種算法算出來的（加權移動平均法 vs FIFO），以及那會讓你看到的未實現損益差在哪裡',
          loading: null, idle: null, empty: null, missing: null,
          partial: null, degraded: null, unwired: null, na: null, error: null
        },
        asOf: null,
        evidence: '規格 S1-3B:854 D-2 落點表明列「Part 5 再平衡區塊」為必出位置之一 —— **該落點未受本輪範圍變更影響，本區塊照舊必出**。｜🔧 **2026-09-14 範圍變更改寫（據實標明改了什麼）**：原 name 與原 live 提到「**兩站都放（★-14a）**」，把本站的「成本」與**另一站**的「佔比」綁成同一份揭露。**那一站已於 2026-09-14 依客戶明示自本稿整頁移除**，「兩站都放」的另一邊已不存在，故改寫為單站版。**原 name／原 live 的逐字原文與該頁名，見封存檔 `wf_fund_archive.md`（D 段 ＋ B 段 DEV-24）**；2026-09-15 依客戶第二次明示，本欄不再寫出該頁名 —— ⭐ **移出畫面 ⛔ 不等於銷毀**。｜⭐ **被改寫的只有「跨站」那一半 —— D-2 對本站的要求一字未減**：本站的成本口徑該不該揭露，**與另一站在不在無關**（使用者看的是自己這本帳算出來的未實現損益）。｜⚠️ **★-14a（兩站都放）本身 ⛔ 未被推翻，它是「失去載體」** —— 該條已於 2026-09-15 **整條移入封存檔 `wf_fund_archive.md`（A 段，逐字全文 ＋ 恢復條件）**，**內容 ⛔ 未刪**；⛔ **不得讀成「已解決」** —— 它仍是未決的題目。那一站若恢復，該條與本 block 的跨站半段要一起取回。｜⚠️ **處置來歷（依 §-2 規則 6 據實標明）**：客戶 2026-09-14 的原話只有四個字（**逐字指令見封存檔 `wf_fund_archive.md`**）；**「本 block 改寫成單站版而不是整塊擱置」是執行組的處置判斷**，⛔ 不是客戶原話、⛔ 也不是總管逐字指示（總管當時只逐字點名了 `cross_site_unrealized` 那一條要拆半）。判準是：**D-2 對本站的揭露要求與另一站在不在無關**，整塊擱置會讓本站的必出揭露一起消失。✅ 總管已於 2026-09-14 事後確認。｜⚠️ 本改寫由本組單組執行，未經第二組複驗（CLAUDE.md §-2 規則 6）。',
        src: 'scratchpad/S1-3B_FULL_DRAFT_SPEC.md:854；改寫依據：客戶 2026-09-14 ＋ 2026-09-15 兩次明示的範圍變更指令（客戶明示，⛔ 非總管拍板）；逐字指令與原文見封存檔 wf_fund_archive.md',
        flags: ['範圍變更改寫']
      },

      {
        key: 'rebalance.l4.cross_site_unrealized',
        name: '▸ 本站「未實現損益」不含匯兌損益（結構性缺欄位，限制尚未解除）',
        leaf: '葉1 戰情室（1️⃣~6️⃣ ＋ 80/20 配置偏離）',
        cols: { desktop: 1, tablet: 1, phone: 1 },
        states: {
          live:     '本站的「未實現損益」**不含**匯兌損益：持股帳本沒有幣別欄、也沒有買入匯率欄，成本與現值都用**同一個今日匯率**換算。⇒ 你看到的是純價格報酬；你真實的匯兌損益取決於**當初買進時的換匯匯率**，本站沒有那個數字，算不出來。⛔ 不得把這個數字說成「你的總損益」',
          loading: null, idle: null, empty: null, missing: null,
          partial: null, degraded: null, unwired: null,
          na:       '本站的匯兌損益欄：N/A（灰字，不加 ⚠︎）—— 結構性缺欄位，不是這次沒拿到（判錯實例 E-7）',
          error: null
        },
        asOf: null,
        evidence: '⭐ **本條的台股側限制依然成立，與另一站在不在無關 —— ⛔ 未擱置、⛔ 未刪除，只把「跨站」那一半拿掉。**（⭐ 這一點是**總管 2026-09-14 逐字明示**的判準：「台股側『未實現損益不含匯兌』這個限制依然成立…請把它改寫成單站版本，**不要連帶擱置掉**」。）｜實測（股票 repo，原組親自讀出）：src/compute/etf/portfolio_fx.py:29-30 docstring 逐字「因此 capital_gain 是純價格報酬 × 今日匯率，不含匯兌損益 —— 使用者真實的匯兌損益取決於當初買進時的換匯匯率」；src/data/portfolio/gsheet_portfolio.py:82 `_HEADERS = [name, ticker, lots, avg_price, updated_at]` 五欄，**無幣別欄、無買入匯率欄** ⇒ 缺的是欄位本身，不是這一輪沒取到。｜🔧 **2026-09-14 範圍變更改寫（據實標明改了什麼）**：原 name 與原 live 末段講的是「**跨站同名不同義**」—— 本站「未實現損益」不含匯兌、**另一站的同名數字含匯兌**，並要求「⛔ 兩站都要標」；原 evidence 另回指一個已不存在的 block。**那一站已於 2026-09-14 依客戶明示自本稿整頁移除**，回指會變成斷鏈、「兩站都要標」也已無法執行，故改寫為單站版。**原 name／原 live／原回指的逐字原文見封存檔 `wf_fund_archive.md` D 段**；2026-09-15 依客戶第二次明示，本欄不再寫出該頁名。｜⭐ **⛔ 不是說另一站那個事實是假的** —— 它「未實現損益**含**匯兌」是原組回該 repo **親自實測**到的（含 file:line 與欄位逐字），該事實**已逐字保存**於封存檔 `wf_fund_archive.md`（C 段），⛔ **未被銷毀**；那一站若恢復可直接取回跨站半段。｜⚠️ **key 刻意沿用舊名 `cross_site_unrealized` 不改**：key 是組裝腳本的識別字，改名可能打到別組（`warroom_ia_v2.html` 由別組同時在改）—— 名實不符已在本條 name 與 evidence 交代，⛔ 不以順手改名處理。｜⚠️ **處置來歷（依 §-2 規則 6 據實標明，兩半來歷不同，⛔ 不得混寫）**：**(a) 「台股側依然成立、改寫成單站版留在線框裡、⛔ 不得連帶擱置」＝ 總管 2026-09-14 的明示指示**；**(b) 「另一站那一半只搬存、⛔ 不刪」＝ 執行組的處置判斷**（⛔ 非客戶原話、⛔ 非總管原話，總管只說了「不要直接刪」；總管已事後確認）。⚠️ **2026-09-15 更新存放位置**：該半段原存於 `wf_global.js` 的 `WF_LIMITS` C.6 段，客戶第二次明示後**已連同整個 C.6 段移入封存檔 `wf_fund_archive.md`（C 段）** —— **換的是存放位置，⛔ 不是存不存在**。｜⚠️ 本改寫由本組單組執行，未經第二組複驗（CLAUDE.md §-2 規則 6）。',
        src: 'my-stock-dashboard（股票 repo）src/compute/etf/portfolio_fx.py:29-30 ＋ src/data/portfolio/gsheet_portfolio.py:82；規格 scratchpad/S1-3B_FULL_DRAFT_SPEC.md:2546；改寫依據：客戶 2026-09-14 ＋ 2026-09-15 兩次明示的範圍變更指令（客戶明示，⛔ 非總管拍板）；逐字指令與原文見封存檔 wf_fund_archive.md',
        flags: ['範圍變更改寫']
      }

    ]},

    /* ═══ 附錄｜現況違規區塊與三條硬禁令 ═══ */
    { n: 5, label: '附錄｜三條硬禁令 ＋ 現況待移除區塊（登記）', blocks: [

      {
        key: 'rebalance.rules.three_prohibitions',
        name: '⛔ 三條硬禁令（逐條，不得以任何理由放寬）',
        leaf: '葉1 戰情室（1️⃣~6️⃣ ＋ 80/20 配置偏離）',
        cols: { desktop: 1, tablet: 1, phone: 1 },
        states: {
          live:     '1. ⛔ 禁止「一鍵再平衡」按鈕 —— 任何會產生下單清單、或一次套用全部調整的按鈕都不得存在。　2. ⛔ 禁止預設最佳配置 —— 目標比例只能由使用者自己填，系統不得預填、不得給「參考配置」。　3. ✅ 只做三件事：偏離提示／客觀對照／情境試算',
          loading: null, idle: null, empty: null, missing: null,
          partial: null, degraded: null, unwired: null, na: null, error: null
        },
        asOf: null,
        evidence: '客戶 2026-09-14 拍板三逐字（S1-3B:83、:2556、:2692-2697）。',
        src: 'scratchpad/S1-3B_FULL_DRAFT_SPEC.md:83,2556,2692-2697',
        flags: []
      },

      {
        key: 'rebalance.legacy.trade_instruction_table',
        name: '🔴 現況違規區塊：「⚖️ 再平衡交易指令」表 —— 線框裡不得出現，登記待移除',
        leaf: '葉1 戰情室（1️⃣~6️⃣ ＋ 80/20 配置偏離）',
        cols: { desktop: 1, tablet: 1, phone: 1 },
        states: {
          live: null, loading: null, idle: null, empty: null, missing: null,
          partial: null, degraded: null,
          unwired:  '登記事項（⛔ 線框裡不得畫出這一塊）：台股側現行有一張「⚖️ 再平衡交易指令」表，欄位名為「動作」與「建議股數」，並在表下逐檔印出一句帶方向動詞 ＋ 具體股數 ＋ 現價的句子。那是直接的買賣指示，命中客戶拍板三與三條硬禁令第 1 條。本線框以「偏離對照（目前比例 vs 目標比例 vs 差距）＋ 情境試算」取代之 —— 情境試算只印金額變化與張數換算，且題句為條件句、附五條限制、明說不是下單清單',
          na: null, error: null
        },
        asOf: null,
        evidence: '本組獨立實測（股票 repo）src/ui/etf/etf_tab_portfolio.py:822 `st.markdown("#### ⚖️ 再平衡交易指令")`；:845 dict 鍵含「動作」與「建議股數」；:857-859 DataFrame 欄名同上；:866-873 逐檔輸出一句含方向動詞 ＋ 股數 ＋ 現價 ＋ 預估金額 ＋ 偏離度。⇒ 以 S1-6 §1.1 判準：這是「系統對使用者說的話」（STEP 1 命中 st.* 輸出），且觀測→行動之間系統替讀者填掉了可投入資金、持有期間、風險承受度三個只有讀者才有的變數（STEP 2）⇒ 違規。⚠️ 另一個相關灰色地帶（S1-3B:2699）：:211-216 現行有一組**具名的範例持股列**（四檔代號 ＋ 張數 ＋ 均價），下游立刻對它跑核衛／再平衡／VaR ⇒ 功能上與「這是一個示範配置」難以區分；本線框規格為 ⑤-b 的目標比例欄一律空白、⛔ 不得有任何範例列，示範一律用不可計算的佔位符。⚠️ 動工觸發仍受 CLAUDE.md §-1 拘束：本格只登記現況，不構成主動動工的授權。',
        src: 'my-stock-dashboard（股票 repo）src/ui/etf/etf_tab_portfolio.py:211-216,822,845,857-859,866-873；規格 scratchpad/S1-3B_FULL_DRAFT_SPEC.md:2692-2700',
        flags: ['★待拍板', '偏離']
      },

      {
        key: 'rebalance.responsive.tablet_phone',
        name: '平板／手機降階規則',
        leaf: '葉1 戰情室（1️⃣~6️⃣ ＋ 80/20 配置偏離）',
        cols: { desktop: 3, tablet: 2, phone: 1 },
        states: {
          live:     '平板 641–1280：表格保留，放進橫向捲動容器；「目前% / 目標% / 偏離」三欄⛔ 不得縮字。手機 <640：轉卡片流，每檔一張卡（目前% / 目標%〔輸入欄仍空白〕/ 偏離）＋ D-3 短版。數值在卡片流內仍等寬、仍右對齊（這條最常在轉卡片時被忘掉）',
          loading: null, idle: null, empty: null,
          missing:  '手機卡片流的偏離欄同樣是 ▨ 未設定 —— ⛔ 不得因為版面小就變成 0.00',
          partial: null, degraded: null, unwired: null, na: null, error: null
        },
        asOf: null,
        evidence: '規格 S1-3B:2802-2815（平板／手機逐字）＋ Part 2.8 斷點定案表（:469-535）：≤480→1 欄、481–640→1 欄、641–880→2 欄、881–1280→3 欄、>1280→3 欄（⛔ 不加到 4）。每欄最小寬硬底線：197px（再窄水平溢出）／274px（再窄金額折行）。⚠️ 整個響應式層自標為 ★-06：核准線框 stock_ia_v1.html 全檔「手機／375／響應式／breakpoint／平板」皆 0 命中，從未經客戶拍板。⛔ 頁面本體在任何寬度都不得橫向捲動（只有表格容器可以）。',
        src: 'scratchpad/S1-3B_FULL_DRAFT_SPEC.md:469-535,2802-2815',
        flags: ['★待拍板']
      }

    ]}

  ]
});
