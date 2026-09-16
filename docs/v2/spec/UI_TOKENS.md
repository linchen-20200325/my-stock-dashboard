# UI_TOKENS —— 戰情室 v2 設計 token（第 1 份）

**基準：線框稿 `docs/v2/wireframe/warroom_ia_v2.html:root` 色票**（客戶逐條審過、自帶深色覆寫與等寬字欄寬，
而 app 現況是三套狀態色／四種灰／兩種黑並存的累積漂移）。**深色為實際運行模式，dark 值為主要交付；light 值次要。**
⚠️ 本檔為 UI 設計組 WB 單組產出，未經第二組複驗（§-2 規則 6）；全檔免責只講這一次。

## 0. 落地位置與兩個既有約束

| 項目 | 規定 |
|---|---|
| token 落地 | **新訂** `shared/ui_tokens_v2.py`（本 repo 自有）＋ 單一 `<style>:root{}` 注入；⛔ 不得改 `shared/colors.py` |
| `shared/colors.py` | 檔頭自陳 AUTO-SYNCED FROM my-fund-dashboard；本 repo 改了會被 `scripts/sync_to_stock.sh` 蓋掉 → **維持鏡像不動** |
| `.streamlit/config.toml` | 釘死 `base="dark"`。`backgroundColor` 現為 `#0e1117`，與線框 `--paper` dark `#0e141b` 差 3 碼 → **須改的那一鍵＝`backgroundColor` = `#0e141b`**（⛔ 本檔不動它） |
| 同檔後續鍵 | `secondaryBackgroundColor`→`#151d26`、`textColor`→`#dbe5ef`、`primaryColor`→`#d59a5e`；`font="sans serif"` 是 Streamlit 列舉值、**不是**字型堆疊，堆疊只能由 §B 的 CSS 提供 |
| `--review-*` | **只在審稿模式渲染**（客戶 2026-09-16 明令）；正式畫面 `[data-review-only]` 一律 `hidden` |

## A. 色彩 token

### A-1 主色／輔色／面與墨

| token | dark | light | 用途 | 配套圖示/文字 | 對應現況 |
|---|---|---|---|---|---|
| `--ochre` | `#d59a5e` | `#96591f` | 主色：強調、待辦標記 | 文字標籤 | `app.py:.strategy-card` border-left `#ffd700` |
| `--ochre-bg` / `--ochre-line` | `#2a2013` / `#8a6234` | `#f6ecdf` / `#c08a4e` | 主色底／框 | — | 新訂 |
| `--focus` | `#8fc0ff` | `#14508f` | 輔色：焦點環、連結 | — | `app.py:.stTabs [aria-selected]` `#1f6feb` |
| `--paper` / `--panel` / `--panel-2` | `#0e141b` / `#151d26` / `#1b242f` | `#f6f5f1` / `#fffefc` / `#edece7` | 畫布／卡面／次卡面 | — | `.streamlit/config.toml:backgroundColor` `#0e1117` |
| `--grid` / `--rule` / `--rule-2` | `#1a242e` / `#2e3b48` / `#46545f` | `#e5e3dc` / `#c6ccd2` / `#9aa4af` | 圖表格線／分隔線／強分隔線 | — | `macro/section_short.py:yaxis.gridcolor` `#21262d` |
| `--ink` / `--ink-2` | `#dbe5ef` / `#9fb0c1` | `#15293f` / `#4b5b6d` | 主文字／次文字 | — | `config.toml:textColor` `#e6edf3`；`macro_helpers.py:'color'` `#8b949e` |
| `--ink-3` | `#73838f` | **`#626f7a`** | 三級文字（說明） | — | 線框 light 原 `#7d8b99`，對 `--paper` 僅 3.19:1 → 本組下修至 4.72:1 |
| `--review-bg`/`-line`/`-ink` | `#1d1b28`/`#8b82b4`/`#c3bbe4` | `#eceaf2`/`#6f6790`/`#4a4270` | 治理標記（**僅審稿模式**） | ★📌 ＋文字 | 新訂 |

### A-2 狀態色（保留色：⛔ 不得挪用為圖表第 N 條線；⛔ 一律配圖示＋文字，不得只靠顏色）

| token | dark ink / bg | light ink / bg | 用途 | 配套圖示＋文字 | 對應現況 |
|---|---|---|---|---|---|
| `--sig-green` | `#57b985` / `#11241a` | `#1c6f43` / `#e3f0e9` | 正常 | 🟢「正常」 | `shared/colors.py:TRAFFIC_GREEN` `#22c55e` |
| `--sig-amber` | `#d3a43c` / `#292110` | `#87600a` / `#f6efdb` | 警告 | 🟡「警告」 | `shared/colors.py:TRAFFIC_YELLOW` `#eab308` |
| `--sig-red` | `#e8706b` / `#2b1615` | `#ae2f2b` / `#f8e7e5` | 錯誤 | 🔴「出錯了」 | `shared/colors.py:TRAFFIC_RED` `#ef4444` |
| `--sig-blue` | **`#4b8efe`** / `#141f2b` | **`#044cb6`** / `#e4ecf3` | **已評估·結論中性** | ◆「已評估 · 中性」 | **新訂**（線框無此格） |
| `--sig-grey` | `#8b98a4` / `#1b232b` | **`#586470`** / `#eae9e4` | **缺漏／不適用／未評估** | ⚪「還沒載入 · 不適用」 | `macro_v2_cards.py:STATE_META["missing"]` `#8a8e96` |

⛔ `--sig-grey` 是缺漏態**專用**，與「數值 0」及 `--sig-green` 不共用任何視覺；`--sig-blue` 與 `--sig-grey`
在 dark 的未模擬 ΔE 15.8、light 16.3（均 ≥15 門檻）→ **「缺漏」與「判過了但中性」眼睛分得開**（D-15／N-7）。
light `--sig-grey` 自線框 `#6c7883` 下修（原對自身 bg 僅 3.71:1）。

### A-3 圖表序列識別色（7 槽，固定順序、⛔ 不循環；第 8 條以上折成「其他」或分面）

| 槽 | dark | light | 用途 | 對應現況（⛔ 全部**被取代**，非沿用） |
|---|---|---|---|---|
| 1 | `#2e64a6` | `#2482eb` | 序列 1 | `shared/colors.py:COLORS_7[0]` `#58a6ff` |
| 2 | `#c7843c` | `#b47227` | 序列 2 | `COLORS_7[2]` `#ffd700` |
| 3 | `#209993` | `#1b9690` | 序列 3 | `COLORS_7[5]` `#79c0ff` |
| 4 | `#c15dde` | `#b118a5` | 序列 4 | `COLORS_7[4]` `#bc8cff` |
| 5 | `#6f650d` | `#5b5e00` | 序列 5 | `COLORS_7[1]` `#22c55e` |
| 6 | `#934d6b` | `#ff3282` | 序列 6 | `COLORS_7[3]` `#ef4444` |
| 7 | `#7a3ae2` | `#7612e0` | 序列 7 | `COLORS_7[6]` `#ff9f43` |

**框架：這不是「3 槽擴 7 槽」，是把一組不合格的色整組換掉** —— 現行 `COLORS_7` 實跑自己 FAIL 三項：明度帶 7 之 6 出界、CVD `#bc8cff↔#58a6ff` ΔE 2.7、**一般視覺 `#79c0ff↔#58a6ff` ΔE 8.1**（驗證器註「低於 15，連全色覺的人都分不出來」）。
**驗證器實跑**（`validate_palette.js --pairs all`）：dark（surface `#0e141b`）**5/5 PASS**（最差 protan/deutan 槽 4↔7 ΔE 8.3、一般視覺 15.4）、light（`#f6f5f1`）**5/5 PASS**（最差 protan/deutan 槽 2↔6 ΔE 9.4、一般視覺 槽 4↔7 ΔE 16.0）；
狀態色五枚 ink-on-own-bg WCAG AA 4.5:1 **dark 5/5、light 5/5 PASS**；`--sig-blue` vs 序列槽 1 ΔE 17.0 **PASS**。**無 FAIL 殘留**（修過才過的槽 1 自 `#4996f5` 改 `#2e64a6`；light `--sig-grey`／`--ink-3` 兩處見 A-1／A-2）。
🔴 **有拘束力的附帶條件（必須實作；客戶 2026-09-16 裁示，門檻自「第 6、7 槽」下修）**：**同時使用 ≥4 槽時，一律強制直接標籤或紋理（`dash`／`dot`），⛔ 不得只靠顏色區分。**（≤3 槽**僅 dark 免除**：實測前 3 槽最差 protan/deutan 11.3、tritan 12.5，不在帶內；**light 不適用此免除**，見下行。）
實測落在 **6–8 下限帶**的對（dark，`--pairs all`）：**槽 2↔4** `#c7843c↔#c15dde` tritan **6.6**（⚠️ 一用到槽 4 就進帶，前 4／5／6／7 槽的最差 tritan 都是這一對）、**槽 5↔6** `#6f650d↔#934d6b` tritan **7.9**；另 **槽 4↔7** `#c15dde↔#7a3ae2` protan **8.3** 貼著門檻（剛過 8.0 目標，其自身 tritan 為 17.3）。驗證器明文「落在該帶只有配合次要編碼（直接標籤／間隙／紋理）時才合法」。
light **無任何對落在 6–8 帶**（最差 protan/deutan 9.4，槽 2↔6）；但**凍結的槽 1↔3** `#2482eb↔#1b9690` tritan **3.5、低於 6**，自 3 槽起就存在 —— 非新槽引入，且 tritan 不在驗證器五項門檻內（故仍 5/5 PASS）→ **light 畫滿 3 槽即已須次要編碼，⛔ 不得引用上面的 ≤3 槽免除。**
狀態色分離：**新增 4 槽**對狀態色最差 ΔE dark **18.5**、light **16.2**（槽 4/6/7）；⚠️ **light 槽 5 `#5b5e00` 對 `--sig-amber` 僅 7.8** —— light 狀態色已佔滿綠／琥珀／紅／藍／灰五色族，橄欖色無處可退，與既有槽 2 對 `--sig-amber` 9.9 同一性質，靠 A-2「⛔ 一律配圖示＋文字」擋。
⚠️ 狀態色的 dark 值是**線框自己選出來的一套**，非 light 值翻轉；綠/紅在 deuteranopia 下 ΔE 3.9 無法靠色相分辨 —— 這正是「⛔ 一律配圖示＋文字」在本專案是硬規則、不是建議的原因。

## B. 字型 token（⚠️ app 端幾乎空白：無全域 `font-family`、無字級 ramp、`11px` 用了 158 次卻從未具名 → 本節**大部分新訂**）

| 類 | `font-family` | `font-size` | `line-height` | `font-weight` | 對應現況 |
|---|---|---|---|---|---|
| 標題 L1 | `--sans` | `clamp(26px,4.4vw,40px)` | `1.15` | `900` | 新訂（線框 `h1`） |
| 標題 L2 | `--sans` | `clamp(20px,2.6vw,27px)` | `1.3` | `800` | 新訂（線框 `h2`） |
| 標題 L3（卡標） | `--sans` | `17.5px` | `1.5` | `700` | 新訂（線框 `.blk.t1 .bt .t`） |
| 內文 | `--sans` | `14.5px` | `1.72` | `400` | 新訂（線框 `body`） |
| 數值（等寬） | `--mono` ＋ `font-variant-numeric:tabular-nums` ＋ `white-space:nowrap` | `13px` | `1.5` | `500` | `macro_v2_cards.py:.v2-src`；其餘 7 處為裸 `monospace` |
| 說明 | `--mono` | `11.5px` | `1.45` | `400`（色 `--ink-3`） | 新訂（線框 `.bpnote`） |
| 徽章 | `--sans` | `11.5px` | `1.45` | `600` | 新訂（線框 `.bdg`） |

`--sans` = `"Noto Sans TC","PingFang TC","Microsoft JhengHei",system-ui,-apple-system,"Helvetica Neue",sans-serif`
`--mono` = `"IBM Plex Mono",ui-monospace,SFMono-Regular,Menlo,Consolas,monospace`（線框 30 處，**數值一律走這條**）

## C. 間距 token（⚠️ app 端零 token、零 SSOT，僅 8 處 `st.columns(gap=)` → 本節**大部分新訂**）

| token | 值 | 用途 | 對應現況 |
|---|---|---|---|
| `--sp-1` / `--sp-2` / `--sp-3` | `4px` / `6px` / `8px` | 徽章內距、行內元素 gap | 新訂 |
| `--sp-4` / `--sp-5` / `--sp-6` | `10px` / `12px` / `16px` | 元件間距 | 新訂 |
| `--sp-7` / `--sp-8` | `22px` / `26px` | 頁首、主網格欄距 | 新訂 |
| **卡片內距** | `9px 11px`（≤640px：`6px 9px`） | `.blk` 卡片 | `app.py:.strategy-card{padding:10px 14px}` |
| **面板內距** | `12px 14px` | `.pan` 面板 | `app.py:.health-A/B/C{padding:16px}` |
| **卡片間距** | `margin-top:9px`（≤640px：`6px`） | 同層卡片垂直堆疊 | `app.py:.strategy-card{margin:6px 0}` |
| **區塊間距** | `margin-top:12px`；網格 `gap:12px` | 段落／`.two`／`.three` 之間 | `st.columns(gap="medium")` |
| **主網格** | `gap:26px`；`margin-top:22px` | 側欄＋內容 `.shell` | 新訂 |
| **圓角** | `2px`（卡）／`3px`（面板·徽章）／`999px`（膠囊） | ⚠️ 遠比 app 現況銳利 | `app.py` `8px`(75 次)／`.health-*` `12px` |
| **欄寬下限** | `--col-min:308px`（含金額）／`--col-min-text:260px`（兩欄）／`--col-min-text-s:210px`（三欄） | 自適應網格 | 新訂 |

---
⚠️ **本檔的查證分級**：**總管實查**＝`.streamlit/config.toml` 三鍵（`base`/`backgroundColor` 等）、`shared/colors.py` 第 1 行不可編輯、線框稿 token 存在、**A-3 dark 七槽驗證器實跑**。
**WD-1 實跑（2026-09-16）**＝**A-3 light 七槽**（含新挑的槽 4~7）與上列其餘驗證器數字、WCAG 對比值。**INV-2 單組盤點（未複驗）**＝「對應現況」欄的次數與 SSOT 判讀、「app 無全域 font-family」「間距無 SSOT」三句全稱句。
**原「最站不住腳的一處」（序列色只給 3 槽、`COLORS_7` 有 4 條無色可對）已解**：本輪擴為 7 槽（兩模式），與 `UI_COMPONENTS` §6 逐字對齊，⛔ 不需折成「其他」或分面。
