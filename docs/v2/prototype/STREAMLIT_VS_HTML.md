# 獨立 HTML 原型 vs Streamlit 實際渲染（量測日 2026-09-21，分支 `ui-v2`）
比對對象：`docs/v2/prototype/ui_prototype_today.html` ↔ `src/ui_v2/{app_today,render,markup}.py`。實測環境 streamlit 1.59.2（`requirements.txt` 宣告 `>=1.56,<1.60`）；`.streamlit/config.toml` `[theme] base="dark" / backgroundColor="#0e1117" / secondaryBackgroundColor="#161b22" / primaryColor="#1f6feb" / textColor="#e6edf3" / font="sans serif"`。
⛔ **本文沒有開過瀏覽器**（此環境開不了）：標**實測**＝讀 code／CSS 逐條比對出的事實；標**推論**＝未跑過畫面，請以你眼睛看到的為準。

## 1. 哪些樣式在 Streamlit 會被覆蓋
- **頁面底色／預設文字色／基準字級／行距（實測）**：原型 `body{background:var(--paper);color:var(--ink);font-size:14.5px;line-height:1.72}`，但 `markup.page_css()` 只產出 `:root` 變數 ＋ `.grd/.lyr/.blk/.bdg/@media` —— **全檔無 `body`、無 `.stApp`、無 `html` 規則** ⇒ 這四項一律由 `config.toml` ＋ Streamlit 基準樣式決定，我們的 token 管不到。
- **主 CTA（實測）**：`render._render_main_cta` 用真 `st.button(type="primary")` ⇒ 吃 `primaryColor`，⛔ 不吃 `--ink`／`--ochre`。
- **中文字族（實測）**：`--sans` 在 `src/ui_v2/` **0 命中**（`components.FONT_STACKS` 只落地 `--mono`，`markup._root_rule` docstring 自陳字型 token 尚未落地）⇒ 原型的 `"Noto Sans TC","PingFang TC","Microsoft JhengHei"` 在 Streamlit 端**根本沒被宣告**。
- **原型獨有、page_css 完全沒有的（實測）**：`.wrap{max-width:1180px}` 限寬、`:focus-visible{outline:2px solid var(--focus)}` 焦點環、`h1/h2` 字級 ramp、`.note` 小字樣式。

## 2. 哪些在 HTML 對、Streamlit 可能不對（每條附「會看到什麼症狀」）
1. **主 CTA 顏色差最多（實測）**：原型 `.cta` ＝ `background:var(--ink)`＋`color:var(--paper)` ⇒ **淺灰白底、深色字、2px 同色框**，hover 轉赭色 `--ochre #d59a5e`。Streamlit 會畫成 **`#1f6feb` 藍底白字、圓角、hover 仍是藍**。⚠️ 不是 Streamlit 預設的紅，是 config 指定的藍。
2. **左右留白比 HTML 寬、卡片更長條（推論）**：原型靠 `.wrap` 置中限寬 1180px；Streamlit 端沒有這條，又設了 `layout="wide"` ⇒ 內容會拉到接近視窗全寬。寬螢幕上第二層 3 欄的每一欄都會比原型寬，卡內文字行長變長。
3. **頁面沒有大標題（實測）**：原型有 `<h1>🚦 今天</h1>`；`render_page_today()` 只吐 style＋各層網格＋CTA，**不吐任何標題** ⇒ 畫面直接從第一層卡開始，上方只有 Streamlit 自己的 header 留白。
4. **CTA 下方說明字偏大、不是灰色小字（實測）**：原型走 `.note`（11.5px 等寬、`--ink-3`）；render 走 `st.markdown(note)` ⇒ 一般內文大小的比例字體、顏色是 `textColor`。
5. **卡內文字略大、行距不同（推論）**：Streamlit 基準約 16px／行距約 1.6，原型是 14.5px／1.72 ⇒ 同一張卡在 Streamlit 會**更鬆、更高**，密度階梯（t1→t4）的落差看起來比原型小。只有大數字 `.blk-val` 明確掛了 `--mono`＋`tabular-nums`，這一項兩邊一致。
6. **底色其實幾乎對，但那是巧合（實測＋推論）**：`.stApp` 的 `#0e1117` vs `--paper #0e141b` 只差 3/256，**肉眼應該分不出來**。⚠️ 對的原因是 config 剛好也鎖深色，⛔ 不是我們的 CSS 在保證 —— 卡片有自己的 `background:var(--panel)`，所以 config 一旦改成 light，會變成「白底頁面＋深色卡」。
7. **主文字色（實測）**：`--ink #dbe5ef` 被宣告了但**沒有任何規則套用它**（只有 `--ink-2` 用在 `.blk-lvl`／`.blk-fact-k`），卡內主文字實際吃 `textColor #e6edf3` —— 兩者都近白，**預期看不出差別**，記在這裡是因為它是「靠 config 補上的」而不是「我們畫對的」。

## 3. 我驗收時要注意什麼
- **桌機（視窗 ≥881px）**：看第二層 `today.summary / today.key_banner / today.holdings` —— **並排 3 張＝對**；上下堆疊或 2 張＝錯（層級網格沒生效）。
- **平板（641–880px）**：第二層應變 **2 欄**；**手機（≤640px）**：應變 **1 欄**。從寬拉到窄要看到 3→2→1 兩次變化；若 3 欄直接跳 1 欄、中間沒有 2 欄那一段＝斷點錯。
- **卡與卡之間**：只該有網格間距，**不該出現整段空白**。看到明顯空行＝Streamlit 在子元素間插了 `<p>`（總管已實測本版應無，看到就是回歸，請回報）。
- **主 CTA**：藍底白字是**已知差異、不是 bug**（見 2-1）。要決定的是「接受 Streamlit 藍」還是「另想辦法套赭色」—— 驗收時請當「待拍板」記著，⛔ 不要當成畫錯退回。
- **卡上的數字**：本輪全部卡應為徽章 **#5「這項還沒做」**、大字區**留白**。⛔ 出現任何數字就是違規（本輪沒有接資料，有數字＝假資料）。
- **未驗證，看到請回報**：若 Streamlit 設定選單能切 Light，`.stApp` 會轉白、而卡片仍是 dark token ⇒ 白底配深卡、徽章顏色全花。本輪沒有驗過這條路徑。
