# UI_COMPONENTS —— 戰情室 v2 元件設計（第 2 份）

## 0. SSOT 宣告（客戶 2026-09-21 裁示）⛔ 先讀這段

**客戶裁示逐字**：「UI_TOKENS.md 是 SSOT（顏色/字級/間距/圓角）。UI_COMPONENTS.md 只引用 token，不自己寫數字。若有衝突，以 UI_TOKENS.md 為準，UI_COMPONENTS.md 改為引用。改完之後，UI 14 條裁定裡 12 條「改規格」的實際動值才能執行。寫進 UI_COMPONENTS.md 開頭。」

**① SSOT 歸屬**：顏色／字級／間距／圓角的唯一真相源＝`docs/v2/spec/UI_TOKENS.md`；本檔**只引用 token、⛔ 不自己寫數字**。

**② 衝突解決** ⚠️ **（本項是總管判讀、非客戶原話，客戶一句話可推翻）**：「以 `UI_TOKENS.md` 為準」是**架構規則**（數字只准住在一個地方），**不是內容規則**（⛔ 不等於 TOKENS 現有的值一律勝出）；衝突的**具體值須逐案判定** —— 若 TOKENS 的值**從未被任何實作採用**，應把**實際在用的值收編成 token**，而非讓死值勝出。
**已實測的唯一衝突正屬此類**：`UI_TOKENS.md:93` 卡片內距 `9px 11px`（≤640 `6px 9px`）與 `:95` 卡片間距 `margin-top:9px`（≤640 `6px`），在本檔與原型 `docs/v2/prototype/ui_prototype_today.html` **各 0 命中**（四層化之前的單層模型殘留）；本檔 §1 的四層階梯才是原型 `.blk.t1`~`.t4` 實跑的值。
⇒ **正解＝把四層階梯的值收編成具名 token，讓 `:93`／`:95` 兩列退場**（新 token 例如 `--pad-t1`／`--gap-t1` —— ⚠️ 兩者**尚未存在、待建立**）；⛔ **不是**把卡片內距改成從未被實作的 `9px 11px` —— 那會直接廢掉四層密度階梯，與客戶同日對 `UI_PRINCIPLES` 第 12／13 條「整體上移重訂、密度階梯保留」的裁定正面矛盾。

**③ 現況揭露（據實，⛔ 不粉飾）**：本檔**目前還沒有**做到「只引用 token」—— §1 的 t1 `15px 17px`、t3 `6px 9px`、t4 `5px 9px` 與 `margin-top:15/10/6/5px`，以及 §3~§5 多數幾何值，都是**裸數字**；**完整**走 token 的只有 t2（`--sp-4` `--sp-5`，對應原型 `.blk.t2{padding:var(--sp-4) var(--sp-5)}`），t3 只有半邊（`--sp-2` ＋裸 `9px`）。

**④ 相依關係**：`UI_PRINCIPLES.md` 14 條裁定中的 12 條「改規格」，其中**第 12／13 條（內距／間距階梯）必須等本 SSOT 收編完成才能動值**（客戶原話：「改完之後…實際動值才能執行」；該檔第 12／13 條亦自陳「SSOT 未定前不得動值」）。

**⑤ 本輪範圍**：⛔ **只立規則、不動值** —— 本輪未改本檔任何既有數值。把裸數字換成 token 引用、把四層階梯收編進 `UI_TOKENS.md`，屬**後續任務**，依 `CLAUDE.md` §-1 未經指派不動工。

---

**基準**：token 一律引用第 1 份 `docs/v2/spec/UI_TOKENS.md`（⛔ 本檔不改它）；幾何值取自線框
`docs/v2/wireframe/warroom_ia_v2.html` `<style>`（唯一 style 區塊）實際 CSS。
**落地位置**：`src/ui/views/`（新頁），不繼承 `app.py` 既有樣式。
**全域圓角＝2px**（卡）／`3px`（面板·徽章·按鈕）：新頁不繼承 `app.py` 那 75 處 `8px`，遷移成本為零；
方角讓數字密集的表格邊界對齊網格。
**`.streamlit/config.toml` 的 `backgroundColor` → `#0e141b`**，排進「第一個 view 落地」的同一批、⛔ 不單獨改：
它是全域鍵，現在改只會讓未遷移的舊頁背景位移而拿不到好處。
**斷點＝`≤640 手機 / 641–880 平板 / ≥881 桌機`**（線框 JS `BP` 宣告版）。⚠️ CSS 現況是 `640 / 940 / 560`，
`880`／`881` 在 `@media` 零命中 → **登記為實作待修，不是規格待決**。
⚠️ 本檔為 UI 設計組 WC 單組產出，未經第二組複驗（§-2 規則 6）；**全檔免責只講這一次**。
表格每列即「規格＋範例」兩者。

## 1. 卡片（四層密度）

`.blk` 基準：`background:var(--panel)`；`border:1px solid var(--rule-2)`；`border-radius:2px`。
四層由 `layers[].n` 自動掛，⛔ 非逐塊手選。

| 層 | 內距 | 圓角 | 邊框 | 陰影 | 卡間距 | 標題字級 | 範例 |
|---|---|---|---|---|---|---|---|
| t1 結論 | `15px 17px`（≤640：`11px 12px`） | `2px` | **2px** solid `--rule-2` | 無（線框 0 命中） | `margin-top:15px` | `17.5px/700` | 今日總結卡 |
| t2 核心 | `10px 12px`（`--sp-4` `--sp-5`） | `2px` | 1px solid `--rule-2` | 無（線框 0 命中） | `margin-top:10px`（`--sp-4`） | `14.5px/700` | 單一燈號卡 |
| t3 操作 | `6px 9px`（`--sp-2` ＋ 9px） | `2px` | 1px solid `--rule-2` | 無（線框 0 命中） | `margin-top:6px`（`--sp-2`） | `13px/700` | 明細列、手機卡片流 |
| t4 佐證 | `5px 9px` | `2px` | 1px **dashed** `--rule-2` | 無（線框 0 命中） | `margin-top:5px` | `12.5px/700` `--ink-2` | 展開後的出處區 |

**層級只靠 border-width／dashed／padding 三個通道區分，⛔ 不得發明陰影。**
面板 `.pan`：`padding:12px 14px`；`border-radius:3px`；`1px solid var(--rule)`；`background:var(--panel)`。
標記態 `.blk.flagged`：`border-color:var(--ochre-line)` ＋ `dashed`（產品模式下改回 solid）。

## 2. 徽章（10 種）

**基底＝既有 L0 `shared/ui_state.py` 七態 SSOT**（已接線，12 個 caller，含 `views/page_today.py`、`page_find.py`；
`views/_ui_kit.py` 明寫「不定義狀態，唯一真相源是它」）。
**幾何**（線框 `.bdg`，10 種共用）：`display:inline-flex; gap:4px; border-radius:3px; padding:1px 7px;
font-size:11.5px; font-weight:600; white-space:nowrap; border:1px solid`。
卡片主徽章用 `.sbadge` 四尺寸（`b1` 14.5px/`10px 22px`/min-h 46/border 2px；`b2` 12.5px/`5px 13px`/min-h 36；
`b3` 11px/`2px 10px`/min-h 28/radius 3px；`b4` 10.5px/`2px 5px`/min-h 26/border 0），依所在卡層 t1→b1 … t4→b4。

| # | 名稱 | 既有常數 | 底色 | 文字色 | 邊框 | 圖示 | 文字 | 範例 |
|---|---|---|---|---|---|---|---|---|
| 1 | 正常 | `UI_LIVE` | `--sig-green-bg` | `--sig-green` | 1px solid `--sig-green` | 🟢 | 運作中 | VIX 18.4 |
| 2 | 載入中 | `UI_LOADING` | `--sig-grey-bg` | `--sig-grey` | 1px solid `--rule-2` | ⏳ | 載入中 | 按鈕點下、spinner 生命週期內 |
| 3 | 還沒載入 | `UI_IDLE` | `--sig-grey-bg` | `--sig-grey` | 1px solid `--rule-2` | ⬜ | 尚未載入 | 進頁未點「載入總經資料」 |
| 4 | 門檻已失準 | `UI_DEGRADED` | `--sig-amber-bg` | `--sig-amber` | 1px solid `--sig-amber` | 🟠 | 門檻已失準 | 門檻帶在本區間無判別力 |
| 5 | 這項還沒做 | `UI_UNWIRED` | `--sig-grey-bg` | `--sig-grey` | 1px **dashed** `--rule-2` | ⛔ | 未接線 | 決策端刻意沒接的燈 |
| 6 | 出錯了 | `UI_FAILED` | `--sig-red-bg` | `--sig-red` | 1px solid `--sig-red` | 🔴 | 取得失敗 | FRED 連線失敗 |
| 7 | 缺漏 | `UI_EMPTY` ＋ `MISS_NO_INPUT` | `--sig-grey-bg` | `--sig-grey` | 1px solid `--rule-2` | **`⚠︎ —`** | **缺漏 · 可重跑** | 上游這輪失敗 |
| 8 | 結構上不適用 | `UI_EMPTY` ＋ `MISS_NOT_APPLICABLE` | `--sig-grey-bg` | `--sig-grey` | 1px solid `--rule-2` | **`N/A`** | **不適用 · 重跑無效** | 個股沒有折溢價 |
| 9 | 資料不完整 | **新訂**（七態無 partial） | `--sig-neutral-bg`（中性底） | `--sig-neutral` | 1px **dashed** `--sig-blue` | **`◧`** | **N／M 計入** | 12／18 檔有報價 |
| 10 | **只描述不判等級** | `emits_level=False` | `--sig-blue-bg` | `--sig-blue` | 1px solid `--sig-blue` | ◆ | **只描述，不判等級** | 個股 KD |

**拆 `UI_EMPTY` 的依據（#7／#8）**：該模組檔頭自陳「無資料」在某些情況是假話（不是沒有資料，是沒有人去要）；
拆法照 `INDICATOR_SPEC` 三態 —— 缺漏（該有但沒拿到，重試有用）vs 結構上不適用（`MISS_NOT_APPLICABLE`，重試無用）。
⚠️ 兩者同屬灰系 → **圖示已分離（依 `INDICATOR_SPEC` R-3 逐字：缺漏 `⚠︎ —`／不適用 `N/A` 灰），文字仍為必填、⛔ 不得省略或縮寫。**
R-3 明文「灰系**內部**的『不適用』與『缺漏』必須再以符號與 tooltip 分辨，⛔ 不得只靠顏色 —— 只差顏色等於把兩態併回一態」。
**#9「資料不完整」⛔ 不得長得像 #1「正常」**：依 R-3「⛔ 三態不得共用符號或顏色」，#9 與 #1 **不共用任何一個色 token** ——
改中性底 `--panel-2` ＋ 具名前景 `--sig-blue`（實測對比 dark 4.93:1／light 6.54:1，均過 AA），圖示改 `◧`
（線框 §00 圖示表既有：「`◧` 使用者視角『資料不完整』這一類的圖示」，⛔ 非本檔發明），⛔ 不沿用 🟢。
⛔ **硬規則（fail-safe）**：**「N／M」的分子分母若拿不到 → 一律降級顯示為 #7『缺漏 · 可重跑』，⛔ 不得退回 #1『正常』** —— 缺資訊時往保守側退，往「看起來沒事」退就是假綠燈。
⚠️ #9 與 #10 共用 `--sig-blue` 前景（R-3 要求中性結論用「具名標籤＋非灰色」），靠 `◧` vs `◆`、文字、實線 vs 虛線三通道分辨；
其中**圖示與文字在 `.sbadge b4`（`border:0`）下仍存在**，⛔ 不得把虛線當唯一分辨通道。

📌 **#9 改引用 `--sig-neutral-bg`／`--sig-neutral`（客戶 2026-09-21 指定）後的可分辨性複查** —— ⚠️ **量測值的 SSOT 在 `UI_TOKENS.md` §A-2.1，本處只引述、⛔ 不另訂值**：
現況 **#9**＝`--sig-neutral-bg` 底 ＋ `--sig-neutral` 字 ＋ **dashed** 框（框色仍 `--sig-blue`，客戶只指定底色與文字色，⛔ 未動框色）；
**#10**＝`--sig-blue-bg` 底 ＋ `--sig-blue` 字 ＋ **solid** 框。
**據實**：兩者**底色** ΔE2000 僅 **3.45**（幾乎同色，⛔ 底色不構成有效分辨通道），但**前景色已不同**（`--sig-neutral` vs `--sig-blue`）＋ **框線樣式不同**（dashed vs solid）＋ **圖示不同**（`◧` vs `◆`）＋ 文字不同
⇒ **不再只靠虛線一個通道分辨**：上一段「#9 與 #10 **共用** `--sig-blue` 前景」這個前提自本次改動起**已不成立**，該段的「⛔ 不得把虛線當唯一分辨通道」之**顧慮點已解除**。
⚠️ **但該禁令本身仍然有效、⛔ 不得據此鬆綁**：`.sbadge b4` 是 `border:0`，框線在該尺寸**整條不存在** —— 真正扛分辨的仍是**圖示＋文字**（§2 硬規則「⛔ 一律配圖示＋文字」未被本次改動觸及）。
⚠️ **本次改動換掉的是問題、不是消掉問題（WE2 自算，單組未複驗，⛔ 不得當既定前提）**：新前景 `--sig-neutral` `#8fa3b8` 與 `--sig-grey` `#8b98a4` 的 ΔE2000 僅 **4.85**，**低於 `UI_TOKENS` A-2 自訂的 ≥15 可辨門檻**；而本表 **#2／#3／#5／#7／#8 五列前景全是 `--sig-grey`** ⇒ #9 與 #10 拉開了，卻與**灰系五列**靠近了。同樣靠「圖示＋文字」擋，⛔ 不得讓 #9 與灰系任一列同框而只靠顏色分辨。
⚠️ **殘留不一致（據實揭露，本輪依指派「既有內容零刪除」而未改）**：上方「**#9「資料不完整」⛔ 不得長得像 #1「正常」**」段仍寫 `--panel-2` ＋ `--sig-blue` 與「實測對比 dark 4.93:1／light 6.54:1」，**那是本次改動前的值**；`--sig-neutral` on `--sig-neutral-bg` 的現行實測為 **5.61:1**（dark；**light 兩碼客戶尚未指定＝待訂**）。**該段文字待後續任務同步**，⛔ 在同步前不得引用其中的舊 token 名與舊對比值。
🔴 **第 10 種：客戶 9 種清單未涵蓋；依 2026-08-26 裁示不得併入任何一種，故補列。**
該裁示明文「`wired`／`discriminative`／`emits_level` **三者互相獨立、不可互相替代**」，
理由是把 KD 標成「不適用」在畫面上**是假話**（KD 完全適用、值照抓照印，缺的是判燈規則本身）。
客戶若不要，可一句話刪掉本列。
**硬規則**：狀態色**一律配圖示＋文字，⛔ 不得只靠顏色** —— 依據第 1 份實測「綠/紅在 deuteranopia 下 ΔE 3.9 無解」。
**硬規則**：狀態頻道出「圖示＋中文」，訊號頻道**只出中文標籤**（兩邊都有 🔴，同卡出兩顆等於沒有資訊）；
`_ui_kit.assert_signal_text_clean()` 已在建構期擋這件事。
**色票銜接**：`shared/ui_state.py` 回 `TRAFFIC_*` **語意常數**（⛔ 不動跨 repo 同步檔），
**呈現層在 render 時把語意映射到 `--sig-*` CSS token**。兩者是同一語意的兩種載體，不是兩套色。

## 3. 按鈕

| 類 | 高度 | 內距 | 字級 | 圓角 | 底色 | 框色 | hover | 範例 |
|---|---|---|---|---|---|---|---|---|
| 主 CTA（**全站唯一一顆**） | `min-height:40px` | `6px 16px` | `13.5px/700` | `3px` | `--ink` | 2px solid `--ink` | bg＋框 → `--ochre`，字 `--paper` | 「載入今日戰情」 |
| 次級（說明） | `min-height:40px` | `6px 16px` | `13.5px/700` | `3px` | `transparent` | 1px solid `--ink` | bg `--panel-2`，框 `--rule-2` | 「這張卡怎麼讀」 |
| 次級（展開佐證） | `min-height:44px`／`min-width:44px` | `7px 9px` | `12.5px/600` | `3px` | `transparent` | 1px solid `transparent` | bg `--panel-2`，字 `--ink`，框 `--rule` | 「▸ 展開佐證（3）」 |
| 文字按鈕（表頭明細） | `min-height:28px` | `2px 11px` | `11px/600` | `999px` | `transparent` | 1px solid `--rule` | 字 `--ink`，框 `--rule-2` | 表頭狀態列「看明細」 |
| 停用態（無主 CTA 時） | `min-height:40px` | `6px 16px` | `13.5px/500` | `3px` | `transparent` | 1px **dashed** `--rule-2`，字 `--sig-grey` | 無 | 「本頁目前沒有主 CTA」 |

焦點環：全站唯一一條 `:focus-visible{outline:2px solid var(--focus);outline-offset:2px}`，⛔ 不准個別 `outline:none`。
⚠️ **次級按鈕整類為新訂**：INV-4 實測 app 端 `type="secondary"` **0 處使用**；線框 `.cta.sec` 有 CSS 但查無渲染處，
線框主 CTA 本身渲染為 `<span>`（非互動元素），故上表主／次的**高度與 hover 皆為新訂**（由 padding＋border＋行高推得 39px，進位 40）。

## 4. 表格

`.tw` 外層：`overflow-x:auto`；`border:1px solid var(--rule)`；`border-radius:3px`；`background:var(--panel)`；`margin-top:12px`。
**對齊規則（三斷點共通）**：文字欄 `text-align:start`；**數值欄一律 `text-align:end` ＋ `--mono` ＋
`font-variant-numeric:tabular-nums` ＋ `white-space:nowrap`**（第 1 份「數值（等寬）」字型 token）。

| 斷點 | 表頭 | 列高 | 欄寬 | 範例 |
|---|---|---|---|---|
| 桌機 ≥881 | `min-height:36px`；`12px/700` `--ink-2`；bg `--panel-2`；`padding:7px 10px`；nowrap | `38px`（`td padding:7px 10px` ＋ `13px/1.72`） | `table{min-width:460px}`；數值欄 `min-width:88px`；識別欄 `min-width:132px` | 選股結果 8 欄表 |
| 平板 641–880 | 同桌機 | 同桌機 | 同桌機；容器不足時 `.tw` 橫向捲動（**頁面本體不得橫捲**） | 同上，捲動查看 |
| 手機 ≤640 | **不畫表頭**（欄名降為卡內標籤） | 一列＝一張卡 | 單欄滿版 | 見下方卡片流 |

**手機卡片流（新訂）**：一列 → 一張 `.blk.t3`（`padding:6px 9px`；`radius:2px`；`margin-top:6px`）。
**升為標題**：① 識別欄（代號／名稱）→ `.bt .t` `13px/700`；② 主數值欄一欄 → 卡內 `24px/700` `--mono` tabular-nums。
**降為佐證**：其餘全部 → `key　value` 成對；key `--mono` `9.5px` `--ink-3` uppercase `letter-spacing:.14em`，
value `11.5px/700`；每卡至多顯示 **4 對**，其餘收進「展開佐證」按鈕（44×44）。
⚠️ **key 的 `--ink-3` 2026-09-16 改值（與 `UI_TOKENS` A-1 逐字對齊）：dark `#7d8d99`／light `#5f6c77`。** 本卡片流的底是 `.blk.t3` ＝ **`--panel`**，⛔ 不是 `--paper` —— 舊值 `#73838f`／`#626f7a` 只對 `--paper` 調校過，在 `--panel`／`--panel-2` 上實測 dark **4.35／4.01 FAIL**、light **4.36 FAIL**（六格中三格 FAIL）。
新值六格（三背景 × 兩模式）實算：dark **5.41／4.97／4.58**、light **4.94／5.34／4.55** → **全 ≥ 4.5 PASS**。⛔ key 是 `9.5px`，**不得**套 WCAG 大字 3:1 寬鬆標準（大字門檻 18.66px bold／24px）；⛔ 改一邊就要改另一邊。
⚠️ **本塊多為新訂**：線框沒有表格轉卡片流的 `@media`（只有 `.tw{overflow-x:auto}`），卡片流規則只寫在 JS 散文。

## 5. 圖表容器（⛔ 只寫容器，不畫圖表本身）

| 級 | 高度 | 內距（plotly `margin`） | 標題位置 | 圖例位置 | 範例 |
|---|---|---|---|---|---|
| sparkline | `80px` | `l=0, r=0, t=4, b=4` | **無標題**，由外層 `.blk .bt .t` 承載 | `showlegend=False` | 7 張科技股小倍數 |
| 標準 | `260px` | `l=8, r=8, t=35, b=20` | 圖內頂部靠左（`x=0, xanchor='left'`），`12px` `--ink-3` | 圖上方靠右（`orientation='h', y=1.02, x=1, xanchor='right'`），`10px` | 美債 10Y 走勢 |
| 大圖 | `420px` | `l=8, r=8, t=35, b=44` | 同標準 | 圖下方靠左（`orientation='h', y=-0.18, x=0`），`10px` | 科技股 7 線圖 |

容器外框走 `.blk` 該層規格；格線 `--grid`；`plot/paper_bgcolor` = `--paper`；圖例 `bgcolor` 透明。
⚠️ **本塊高度階梯為新訂**：線框完全空白（`.chart`／`.cht` 0 命中）；app 唯一共用版型是
`src/ui/render/macro_ui_components.py:_base_layout(title, height=260)`（`margin l8 r8 t35 b20`），
但 caller 各自覆寫、實測高度 **68–600 無階梯**。`260` 沿用該預設、`80` 取 app 實測既有值、`420` 為新訂。

## 6. 序列色：7 槽（未解項一，已解決）

**槽位**（`--pairs all` 五項全 PASS；與 `UI_TOKENS` A-3 **逐字對齊**，⛔ 改一邊就要改另一邊）：
**dark**（surface `#0e141b`）：`1 #2e64a6`／`2 #c7843c`／`3 #209993`／`4 #c15dde`／`5 #6f650d`／`6 #934d6b`／`7 #7a3ae2`
**light**（surface `#f6f5f1`）：`1 #2482eb`／`2 #b47227`／`3 #1b9690`／`4 #b118a5`／`5 #5b5e00`／`6 #ff3282`／`7 #7612e0`
**兩模式的前 3 槽原封不動，往後各加 4 槽。** 第 8 條以上折成「其他」或分面。

**驗證器實跑**（`validate_palette.js --pairs all`）：dark **5/5 PASS**（最差 protan/deutan 槽 4↔7 ΔE 8.3、一般視覺 15.4）、
light **5/5 PASS**（最差 protan/deutan 槽 2↔6 ΔE 9.4、一般視覺 槽 4↔7 ΔE 16.0）。**無 FAIL 殘留**（⚠️ **範圍＝本節七槽序列色本身，⛔ 非全檔宣告**；文字 token 的 AA 見 `UI_TOKENS` A-1 —— `--ink-3` 曾因只對 `--paper` 定錨而在卡面 FAIL，2026-09-16 已修）。

🔴 **有拘束力的附帶條件（必須實作；客戶 2026-09-16 裁示，門檻自「第 6、7 槽」下修）**：**同時使用 ≥4 槽時，一律強制直接標籤或紋理（`dash`／`dot`），⛔ 不得只靠顏色區分。**（≤3 槽**僅 dark 免除**：實測前 3 槽最差 protan/deutan 11.3、tritan 12.5，不在帶內；**light 不適用此免除**，見下行。）
實測落在 **6–8 下限帶**的對（dark，`--pairs all`）：**槽 2↔4** `#c7843c↔#c15dde` tritan **6.6**（⚠️ 一用到槽 4 就進帶，前 4／5／6／7 槽的最差 tritan 都是這一對）、**槽 5↔6** `#6f650d↔#934d6b` tritan **7.9**；另 **槽 4↔7** `#c15dde↔#7a3ae2` protan **8.3** 貼著門檻（剛過 8.0 目標，其自身 tritan 為 17.3）。驗證器明文「落在該帶只有配合次要編碼（直接標籤／間隙／紋理）時才合法」。
light **無任何對落在 6–8 帶**（最差 protan/deutan 9.4，槽 2↔6）；但**凍結的槽 1↔3** `#2482eb↔#1b9690` tritan **3.5、低於 6**，自 3 槽起就存在 —— 非新槽引入，且 tritan 不在驗證器五項門檻內（故仍 5/5 PASS）→ **light 畫滿 3 槽即已須次要編碼，⛔ 不得引用上面的 ≤3 槽免除。**

**框架：這不是「3 槽擴 7 槽」，是把一組不合格的色整組換掉** —— 現行 `shared/colors.py:COLORS_7` 實跑自己 FAIL 三項：明度帶 7 之 6 出界、CVD `#bc8cff↔#58a6ff` ΔE 2.7、**一般視覺 `#79c0ff↔#58a6ff` ΔE 8.1**（驗證器註「低於 15，連全色覺的人都分不出來」）。
現況實際最多同時 **7 條**（`src/ui/tabs/macro/section_long.py` 科技股 7 線圖、`daily_checklist.py:TECH_MAP` 7 檔）→ 7 槽剛好覆蓋，⛔ 不需折成「其他」或分面。
✅ **`UI_TOKENS` A-3 已同步為 7 槽（2026-09-16，客戶裁示）**：兩份的槽位（dark 七＋light 七）與 **≥4 槽**附帶條件**逐字一致**，⛔ 無殘留不一致。
⛔ 狀態色（`--sig-*`）仍是保留色，不得挪用為圖表第 N 條線：**新增 4 槽**對狀態色最差 ΔE dark **18.5**、light **16.2**（槽 4/6/7）；⚠️ **light 槽 5 `#5b5e00` 對 `--sig-amber` 僅 7.8**（light 狀態色已佔滿綠／琥珀／紅／藍／灰五色族，橄欖色無處可退），與既有槽 2 對 `--sig-amber` 9.9 同一性質 —— 靠 §2「⛔ 一律配圖示＋文字」擋。⚠️ **原文「各槽對狀態色最差 ΔE ≥18.5」是錯的全稱句**（該數只涵蓋 dark 新增 4 槽；dark 槽 2 實測 8.6），本輪據實改寫。

---
⚠️ **複驗分級**：
**總管實查**＝卡片四層 CSS 值（`.blk.t1`~`.t4`）、七態 SSOT 與其 caller、斷點 CSS 不一致（`640/940/560` vs `880/881`）、
**dark** 七槽與 `COLORS_7` 的驗證器結果、2026-08-26 三旗標裁示。**WD-1 實跑（2026-09-16）**＝**light 七槽**（槽 4~7 為本輪新挑）。**WK 實算（2026-09-16，單組未複驗）**＝§4 卡片流 key 的 `--ink-3` 改值與其六格 WCAG 對比；同輪 `validate_palette.js` 複跑確認 §6 七槽未受影響（dark／light 5/5 PASS、exit 0）。
**單組調查（未複驗）**＝INV-3／INV-4 的其餘盤點與計數（app 端 63 顆按鈕／`type="secondary"` 0 處／70 處 `st.dataframe`／
圖表高度 68–600 分佈／`box-shadow` 與圖表 class 的 0 命中結論／`COLORS_7` caller 表），皆屬單次 grep 的全稱句，⛔ 不得當前提。
**原「最站不住腳的一處」已修（2026-09-16，非待驗事項）**：#9 原本與 #1 同底色／同文字色／同圖示（🟢），
只靠虛線框與上標 `*` 分辨 —— 該虛線在 `.sbadge b4`（`border:0`）根本不存在，且違反 `INDICATOR_SPEC` R-3。
**三處已改**：(a) 圖示 🟢→`◧`（線框圖示表既有）；(b) 色改中性底 `--panel-2` ＋ 具名前景 `--sig-blue`，
與 #1 零共用色 token、亦不撞 #4 amber／#6 red；(c) 退化方向寫死為 fail-safe ——
**「N／M」的分子分母若拿不到 → 一律降級顯示為 #7『缺漏 · 可重跑』，⛔ 不得退回 #1『正常』。**
同輪一併修掉 #7／#8 共用 `▨` 的問題（改為 R-3 逐字的 `⚠︎ —` 與 `N/A`）。
⚠️ **本節仍存的已知限制**（非缺陷，是上游依賴）：L3 現況只有 `partial`／`coverage` 兩個 dict 鍵、無分子分母欄位，
故 #9 在 L3 補齊前會**恆走上面那條 fail-safe 降級為 #7**；這是設計上的安全預設，不是退化。
