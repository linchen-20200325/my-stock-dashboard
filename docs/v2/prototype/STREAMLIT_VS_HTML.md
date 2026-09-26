# 靜態原型 `today_v2.html` vs Streamlit 實際渲染（量測日 2026-09-21，分支 `ui-v2`）
比對對象：`docs/v2/prototype/today_v2.html`（本輪**機器產生**的靜態快照，來源 `src/ui_v2/` @ commit `b4cb83e`）↔ `src/ui_v2/{app_today,render,markup}.py`。實測 streamlit 1.59.2（`requirements.txt` 宣告 `>=1.56,<1.60`）;`.streamlit/config.toml` `[theme] base="dark" / backgroundColor="#0e1117" / secondaryBackgroundColor="#161b22" / primaryColor="#1f6feb" / textColor="#e6edf3" / font="sans serif"`。⚠️ 舊的手寫原型 `ui_prototype_today.html` **已不是比對基準**，本文所有「原型」一律指 `today_v2.html`。
⛔ **本文沒有開過瀏覽器**（此環境開不了）：標**實測**＝讀 code／CSS ＋實際跑 `markup` 函式比對出的事實;標**推論**＝未跑過畫面，請以你眼睛看到的為準。

## 1. Streamlit 端「沒有」或「管不到」的東西（先看這段，否則下面每條都會誤讀）
- 🔴 **卡片張數與內容不同，而且這是預期的（實測）**：原型 15 張卡（t1×1／t2×5／t3×4／t4×5），有中文標題、7 張有大數字、12 張帶「資料來源 ＝ ⚠️ 示意值 · 未接線」;Streamlit 走 `render.unwired_view_model()` ⇒ **每個 block 只畫 1 張卡、全頁共 8 張**，標題就是 block key 本身（`today.verdict`…），徽章全 #5、值／等級／facts **一律留白**。⛔ 不是漏畫。
- **整層「原型外殼」Streamlit 都沒有（實測）**：示意橫幅、`🚦 今天` 大標＋出處說明、每層的層標籤＋密度數值說明、深／淺色切換鈕、頁尾、附錄徽章總覽（9 種 × 4 尺寸）。它們走原型自己的 `.pv-*` CSS，`markup.page_css()` **不產**、`render.py` **不吐**。
- **字級／行距／頁面底色（實測）**：`page_css()` 47 條選擇器裡**零 `body`／`html`／`.stApp` 規則**;原型的 `body{…}` 也是外殼自己補的，且**刻意不設字級與行高**（字型 token 尚未落地 `tokens.py`，`components.FONT_STACKS` 只有 `--mono`）⇒ 兩邊都退回各自宿主的預設，我們的 token 管不到。中文字族兩邊**都沒有宣告**（`--sans` 在 `src/ui_v2/` 0 命中），這點反而一致。
- **主 CTA 配色與焦點環（實測；底色／字色 2026-09-22 改值）**：`components.BUTTONS['primary_cta']`（底 ~~`--ink`~~ **`--cta-primary-bg`**／字 ~~`--paper`~~ **`--cta-primary-fg`**／2px 同色框／hover `--ochre`）與 `components.FOCUS_RING`（2px `--focus`、offset 2px）**都是契約值**，原型逐欄展開套上了;但 `page_css()` 兩者都不輸出，Streamlit 端 CTA 是真 `st.button(type="primary")` ⇒ 吃 `primaryColor`，焦點環吃 Streamlit 預設。
  ⚠️ **上面那條刪除線是有意識的政策變更，⛔ 不是漏刪；2026-09-22；決策者客戶**（新 token 見 `docs/v2/spec/UI_TOKENS.md` §A-4，dark `#1f6feb`／light `#044cb6`，字色兩模式皆 `#ffffff`）。
  ✅ **契約現已對齊 config 藍 ⇒ 這一項的落差已收斂**；⚠️ 但 `page_css()` **仍⛔ 不輸出按鈕規則**、Streamlit 端**仍是真 `st.button` 吃 `primaryColor`** —— **對齊的是值，⛔ 不是機制。**
  ⇒ config 的 `primaryColor` 一旦被改成別的顏色，畫面**還是會立刻跟契約脫鉤**（因為兩邊不是同一個來源，只是目前**數值相同**）。
- **深／淺色切換（實測）**：原型內含四條規則（`:root` dark ＋ `@media (prefers-color-scheme: light)` ＋ `:root[data-theme="dark"]` ＋ `:root[data-theme="light"]`），兩個方向都切得動;Streamlit 端 `render_page_today` 只注入 `page_css(mode)` **單一模式**（`unwired_view_model` 預設 `dark`）⇒ 淺色路徑在 Streamlit **根本沒有被宣告**。

## 2. 哪些在原型對、Streamlit 可能不對（每條附「會看到什麼症狀」）
1. ~~**主 CTA 顏色差最多（實測）**：原型 ＝ 淺灰白底（`--ink`）＋深色字＋2px 同色框，hover 轉赭 `--ochre #d59a5e`;Streamlit 會畫成 **`#1f6feb` 藍底白字、圓角、hover 仍藍**。⚠️ 不是 Streamlit 預設的紅，是 config 指定的藍;且這次差掉的是**契約值**（`components.BUTTONS`），不只是原型長相。~~
   🔵 **已決（客戶 2026-09-22 裁示）—— 有意識的政策變更，⛔ 不是漏刪；決策者客戶。**
   契約已改為 **config 藍底白字**（`--cta-primary-bg` dark `#1f6feb`／light `#044cb6`；`--cta-primary-fg` `#ffffff`）⇒ **原型與 Streamlit 的底色與字色現在一致**，本條不再是「差最多」的那一條。
   ⚠️ **仍有落差，⛔ 不得讀成「這條已全部對齊」**：**(a) hover** —— 契約是 `--ochre`（原型畫得出來），Streamlit 端 hover **仍是藍**；**(b) 焦點環** —— 契約 `--focus`，Streamlit 端仍吃預設。
   **兩邊理由並陳**：舊句的判斷（「這是全檔差最多的一條」）**在它寫下的當天完全成立**，⛔ 不是寫錯 —— 被權衡掉的只是它的**前提**（契約值當時是 `--ink`）。
2. 🔴 **`today.summary` / `today.detail` 會出現「一張窄卡＋大片空白」（HTML 結構為實測、畫面為推論）**：兩者的 `BLOCK_COLS` 都是 `(3,2,1)`，而 Streamlit 那格**只有 1 張卡**。`today.summary` 又被層網格 `lg-3-2-1` 包住 ⇒ 桌機上那張卡只佔**整列約 1/9 寬**、右邊空 2/3;`today.detail`（第四層無層網格）約佔 **1/3 寬**、右邊空 2/3。原型因為塞滿了卡（3 張／4 張）看不到這個洞 —— 但原型自己把這層巢狀網格登記為**未判定的 U-1 矛盾**（線框說卡內三欄、舊原型畫成層網格三卡），⛔ 本文不代為裁決。**接線補滿卡後這片空白就該消失;補滿後仍空 → 那才是 bug。**
3. **頁面直接從第一張卡開始（實測）**：`render_page_today()` 只吐 style ＋各層網格 ＋CTA，**不吐任何標題、層標籤或分隔線** ⇒ 原型上用來分層的那些標籤在 Streamlit 全部消失，四個密度階（t1→t4）少了文字提示，只能靠框線粗細與內距自己看。
4. **CTA 下方目前「一個字都沒有」（實測）**：`page_today.main_cta_state()` 無參數時回 `{'enabled': True, 'note': None}` ⇒ `render` 裡的 `st.markdown(note)` **整段不執行**。原型的說明小字走 `.pv-meta`（11.5px ＋ `--ink-3`）。⚠️ 連帶問題：`--ink` 與 `--ink-3` 在 `page_css()` 中**各 0 次使用**（只有原型外殼在用）⇒ 之後真要畫說明字時會是**一般內文大小 ＋ `textColor`**，⛔ 不會自動變成灰色小字。
5. **同一張卡在 Streamlit 更鬆、更高（推論）**：兩邊都沒宣告字級行高，但宿主預設不同（瀏覽器 `line-height:normal` vs Streamlit 自有基準約 1.6）⇒ 卡會變高，**密度階梯 t1→t4 的落差看起來比原型小**。只有大數字 `.blk-val` 明確掛了 `--mono` ＋ `tabular-nums`，這一項兩邊一致。
6. **底色幾乎對，但那是巧合（實測＋推論）**：`.stApp` `#0e1117` vs `--paper #0e141b` 只差 3/256，**肉眼應分不出**。⚠️ 對的原因是 config 剛好也鎖深色，⛔ 不是我們的 CSS 在保證 —— 卡片自己掛 `background:var(--panel)`，config 一旦改 light 就會變成「白底頁面＋深色卡」。
7. ~~左右留白比原型寬、卡片更長條~~ **這條已不成立（實測）**：新原型**刻意不加 `max-width` 限寬容器**（理由：多一個限寬會讓「全檔只有 640／880 兩個斷點」不成立，也會讓欄數變化對不上真正的視窗寬）⇒ 兩邊都是滿版，剩下的留白差只來自 Streamlit 自己的 block-container 內距 vs 原型 `body` 的 16px（推論）。

## 3. 我驗收時要注意什麼
- **桌機（≥881px）**：第二層 `today.summary / today.key_banner / today.holdings` **並排 3 欄＝對**;上下堆疊或 2 欄＝錯（層級網格沒生效）。**平板（641–880）應 2 欄、手機（≤640）應 1 欄**;從寬拉到窄要看到 3→2→1 兩次變化，中間少了 2 欄那一段＝斷點錯。兩邊斷點值相同（`components.BREAKPOINTS`），原型可以直接拉視窗對照。
- **卡與卡之間**：只該有網格間距，**不該出現整段空白**。看到明顯空行＝Streamlit 在子元素間插了 `<p>`（總管已實測本版應無，看到就是回歸，請回報）。⚠️ 第二層右半／第四層右半那種大片空白**不算**這一類，見 2-2。
- **主 CTA**：~~藍底白字是**已知差異、不是 bug**（見 2-1）。要決定的是「接受 Streamlit 藍」還是「另想辦法套契約指定的赭色」—— 驗收時請當**待拍板**記著，⛔ 不要當成畫錯退回。~~
  ✅ **已決（客戶 2026-09-22 裁示）—— 有意識的政策變更，⛔ 不是漏刪；決策者客戶。**
  **藍底白字就是契約值**（`--cta-primary-bg`／`--cta-primary-fg`），**⛔ 不再是已知差異**、也⛔ 不再需要拍板。
  ⇒ **驗收時要看的是另外兩項**：**① hover** —— 滑上去應轉赭 `--ochre`，**仍是藍＝尚未對齊**（已知，⛔ 不是新 bug）;**② 焦點環** —— Tab 鍵移到 CTA 應出現 2px `--focus` 外框 offset 2px，**看到 Streamlit 預設樣式＝尚未對齊**（已知）。
- 🔴 **卡上的數字：兩個產物、兩套規則，⛔ 不要互相對照著抓錯**。在 **Streamlit 頁**上：全卡應為徽章 #5（畫面文字「⛔ 未接線」）、大字區**留白**，**出現任何數字就是違規**（該頁走 `render.unwired_view_model`，全卡未接線，有數字＝假資料）。在 **`today_v2.html`** 上：**有數字才是對的** —— 它是 user 逐字指定的「純靜態、示意數字（標明「示意」）」靜態原型，每張帶數字的卡都有「⚠️ 示意值 · 未接線」那一列，頁首另有示意橫幅、頁尾另有快照聲明。⇒ 同時開兩個檔時，「HTML 有數字、Streamlit 全空」是**兩邊都對**，⛔ 不是其中一邊壞了。
- **未驗證，看到請回報**：Streamlit 設定選單切 Light 時，`.stApp` 會轉白而卡片仍是 dark token ⇒ 白底配深卡、徽章顏色全花。原型證明 token 層**做得到**淺色（四條規則齊全、切換鈕可當場驗），缺的是 `render` 沒把另一個模式的 `:root` 一起注入。
