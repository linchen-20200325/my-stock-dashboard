# Phase 3 共用視覺元件｜離線靜態預覽（Migration Plan §16.2 步驟 5）

- **日期／基準**：2026-10-30；分支 `ccr-c8ef17de-9tw7yt`（= origin/main `6012c1e`）；初版預覽時 `src/`、`tests/` 0 diff；同日修正輪後 `src/ui_v2/compact.py`、`tests/ui_v2/test_compact.py` 有 diff（見 §3）。
- **範圍**：只做「離線靜態預覽」——不掛頁、不新增 app 頁或導覽（DEC-109 十）。元件 HTML 一律由 `src/ui_v2/compact.py` 產出，樣式＝`markup.page_css(mode)`＋`compact.compact_css()`；`pv-` 前綴 CSS／文字為預覽外殼（外框、標註、靜態展開示意區、原生圖灰框），**不是元件**，頁面橫幅已標明。
- ⚠️ **揭露（`CLAUDE.md` §-2 規則 6）**：本檔與下方「發現」「Gate 自評」為**單組（產生預覽的同一組）看圖＋DOM 量測**的結論，**沒有第二組獨立複驗**；「全稱句」（例如『無橫向溢出』）只代表本次量到的頁面。依 §-2，只能當待驗事項，不得當成 Gate 已過。所有數字、日期、系列名為夾具（※示意），⛔ 不得當投資結論。夾具逐字句已與 `_market_blocks` 常數對帳（5 條相等；腳本執行時 import 對帳，失敗會印出）。

## 1. 產生方式

```bash
# repo 根目錄；不 commit
python tools/phase3_preview/gen.py                                   # 寫 docs/vnext/phase3_preview/*.html
PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node tools/phase3_preview/shoot.js   # 1440x900、390x844 fullPage 截圖＋DOM 量測(_measure.json)
python tools/phase3_preview/compress.py                              # PNG>280KB 才量化壓縮（本次無一張需要）
```

- 腳本不被 app／test import，檔名非 `test_*`，不被 pytest 收集；不改 `src/`。
- 瀏覽器＝沙箱既有 Playwright 1.63＋chromium 1243（headless Linux）。字型＝WenQuanYi Zen Hei＋Noto Color Emoji＋DejaVu，**與真實使用者裝置字型不同**（見 §5 限制）。
- 19 張 PNG 皆 < 300KB（最大約 175KB，量測見 `ls -l`）；`_measure.json`＝每張的 DOM 量測原始值（元件寬高、橫向溢出、tile 自然高度、`[title]` 屬性數）。

## 2. 產出清單與預期對照（依線框 §3；每張圖內含冷啟動與已載入兩態，各態以藍點標題區隔）

| PNG（`docs/vnext/phase3_preview/`） | 元件 | 狀態 | 線框 §3 的預期 | 看圖結果 |
|---|---|---|---|---|
| `chips_1440/390.png`、`chips_light_1440.png`（light 附帶） | §3.1 chips 三族 | 冷啟動（護欄單獨）、live、過期、護欄並排、十態各態、failed、fx_partial 長 chip | 資訊＝細外框；狀態＝淡底＋icon＋字；護欄＝**實線粗框**；stale 琥珀不是紅；紅只給 failed；手機換行不橫捲 | ✅ 三族一眼可分；stale 琥珀、failed 紅（僅此一處紅）；手機 390 換行正常，`hOverflow=false`。🟡 見發現 F6／F8 |
| `chart_header_1440/390.png` | §3.2 圖 A／圖 B header | 圖 A 冷啟動（2 chip，Primary 圖槽 220／140）；圖 A 已載入（傳入 6 顆→外露 5 顆，`來源 Yahoo` 溢出進靜態展開示意區，D10=a）；圖 B 已載入 | 標題→chip→1 句→圖→摺疊，順序固定；外露 ≤5；來源進摺疊；手機 chip 2 行 | ✅ 順序正確；外露 5 顆＝2 護欄＋資料日＋窗口＋可讀，來源在摺疊「來源」段。⚠️ 冷啟動只有 2 顆 chip（契約 §4 下限 3），元件不報錯（F9） |
| `missing_slot_1440/390.png` | §3.4 Missing 槽 | Primary：idle／empty／failed／unwired；Secondary 縮一行：idle／empty／retryable／not_applicable／failed／partial 3／5；長原因換行 | Primary 保留同高（桌 220／手 140）、不畫線點；Secondary 縮一行（D6=B）；符號讀 `UI_STATE_META`；只有 failed 紅 | ✅ 量測 Primary 882×220（桌）、332×140（手）；Secondary 單行 33px，長原因手機 54px（2 行）完整可見；未畫任何線點 |
| `kpi_tile_1440.png`、`kpi_tile_m_390.png`（手機＝2 欄示意） | §3.5 KPI tile | 已載入（含 sparkline、估算 chip、窗口 chip）；冷啟動（主值留白＋原因 chip）；邊界：8 字主值、過期 | 高 96～160px；同列高差 ≤16；留白仍 ≥96；2 欄手機主值 ≤2 行 | ✅ 高 96～154（≤160）；⚠️ **自然高度差 58px**（F2）；⚠️ 冷啟動 VIX tile 重複出現「尚未載入」（F3）；⚠️ 2 欄手機 8 字主值折行並孤字（F4，U2 屬實） |
| `sparkline_1440/390.png` | §3.6 sparkline | 連續、中段缺口、`[1,2,nan]`、`[1,nan,3]`、`[3,nan,1,nan,2]`、等值；全 NaN／`[1,nan,nan]`／空序列＝placeholder；h=64 最大 | 缺口斷線、x 不位移；`[1,nan,3]`＝2 個孤立點；有效點 <2＝placeholder、不畫線點、不顯示數字 | ✅ 行為與預期一致，無任何數字。🟡 孤立點很小（F5）；placeholder 在 100px 寬換 2 行 |
| `small_multiples_1440/390.png` | §3.7 小倍數 | 已載入 5 格含缺系列格；格內窗口 chip；冷啟動（整組縮一行，D6=B）；對照：每格各自 Missing | 桌 3 欄／手 2 欄；各自座標；格內無資料日、無數字；缺系列＝placeholder | ✅ 欄數、格內無數字、缺系列格皆正確；⚠️ SVG 為固定 160px 寬、桌機格寬 289px 只占約 55%（F1） |
| `topn_1440/390.png` | §3.8 Top-N | Top-5／共 36；`n` 大於總數；空清單 | 保序、「另 K 筆」＋「查看全部（N 筆）」；hidden=0 時兩者不出現；空清單須另做 Missing | ✅ 5 列、`more_text`／`all_label` 正確、n>總數時皆為 None；⚠️ 「另 K 筆」chip 無 builder（F10） |
| `segment_1440/390.png` | §3.9 segmented（只示意資料） | 去重保序結果、default 不在 options 的 `ValueError`、預覽外殼自繪膠囊（非 st 元件） | 只輸出資料；widget 不在 compact | ✅ `('台股','海外市場','利率','美元')`、default index 0、非法 default 被擋。膠囊為預覽外殼示意（≥44px 觸控高） |
| `palette_1440/390.png` | §3.10 色票並排表 | D1a 維持（客戶裁示色）；D1b 現況三套頁底色 `#0e1117`／`#0e141b`／`#0a0e16` 並排各放同一組 chip＋Missing 槽；對比表（dark／light） | D1a=A 不改；D1b=B 不收斂（僅供對照） | ✅ 三底色上的元件皆可辨；⚠️ 邊框對比 <3（F6） |

DOM 量測彙整（`_measure.json`）：所有頁 `hOverflow=false`、`clipped=[]`（chip／tile／槽沒有被裁字）；`[title]` 屬性數＝0；sparkline `svg` 高 48／64（≤64）。

## 3. 看圖發現的問題（初版預覽時 ⛔ 未改 src；**修正輪（同日）已改 `src/ui_v2/compact.py` 修 F1～F6、F9、F10**，各列開頭【】為現況）

> **修正輪聲明**：修正者與看圖者為同一組（單組），修前後 PNG 由本組自己 Read 確認缺陷消失；對 F1／F3／F6 做過臨時 mutation（還原 CSS／拔掉檢查 → 對應測試轉紅，再還原）。**未經第二組獨立複驗**（§-2 規則 6）。F7（字級 token 命名）、F8（chip 1px 高差）、F11（呼叫端規範）**待修／不在本輪範圍**。下方「發現」欄為初版原文，未改寫。

| # | 嚴重度 | 發現（證據） | 建議修法（不在本批動 src） |
|---|---|---|---|
| **F1** | 🟡 中 | **【✅ 已修（部分）：`.cp-sm-cell .cp-spark{width:100%;height:auto;max-height:var(--cp-mini-h)}`，SVG 隨格寬縮放；受 96px 高度上限與 viewBox 等比，桌機 289px 格內圖寬約 240px 置中，不再固定 160px 靠左（`small_multiples_1440.png` 前後對照）】** **小倍數 SVG 不隨格寬縮放**：`small_multiples_html` 的 SVG 帶固定 `width/height` 屬性（預覽取 160×64），`.cp-spark` 沒有 `width:100%`；桌機格寬 289px，圖只占約 55% 靠左，3 欄顯得參差；手機格寬 162 對 160 勉強。`small_multiples_*.png` 可見 | `compact_css` 加 `.cp-sm-cell .cp-spark{width:100%;height:auto;max-height:var(--cp-mini-h)}`（SVG 已有 `viewBox`，可等比）；或在線框確認「固定寬靠左」是否即預期 |
| **F2** | 🟡 中 | **【✅ 已修：`.cp-tile` 改 flex column、spark 以 `margin-top:auto` 貼底（DOM 不變）；同列 tile 在 stretch 宿主下等高（`kpi_tile_m_390.png`）。⚠️ 宿主格網必須 stretch 仍須 Phase 4 線框寫明】** **tile 自然高度差 58px**（桌機一列 96／154／124；手機 2 欄 96／154／124…；`_measure.json:tileNatural`）。若宿主格網 `align-items:stretch`，視覺高度一致但短 tile 底部留白約 58px；若宿主不 stretch，Gate A5「同列高差 ≤16px」會 ❌。元件本身沒有決定這件事 | `.cp-tile{display:flex;flex-direction:column;height:100%}`，並在掛頁線框（Phase 4）寫明宿主格網必須 stretch；或收斂內容（chip／say／spark 擇一）讓自然高度差收斂 |
| **F3** | 🟡 中 | **【✅ 已修：選擇 Fail Loud——`kpi_tile_html` 在 `value=None` 且 `spark` 為 placeholder 時 `ValueError`；預覽冷啟動 VIX tile 不再傳 spark，「尚未載入」只出現一次】** **冷啟動 tile 重複說「尚未載入」**：主值留白時元件強制要有原因 chip（`⬜ 尚未載入`），但同 tile 的 sparkline placeholder 又寫一次「⬜ 尚未載入：請按更新」，且在 100px 寬被折成 2 行（`kpi_tile_1440.png` 中列第 2 張）。違反線框 §3.4 與契約 §6-5「同一事實外露層最多一次」。`kpi_tile_html` 目前接受 placeholder spark | 冷啟動且 chip 已說明原因時，呼叫端不傳 `spark`；或 `kpi_tile_html` 在 `value=None` 且 `spark.placeholder` 時拒絕／忽略 spark（需線框確認） |
| **F4** | 🟡 低 | **【✅ 已修：`.cp-tile-value{text-wrap:balance}`；8 字主值於 2 欄手機折成「高檔震盪／偏弱格局」，無孤字（`kpi_tile_m_390.png`）。⚠️ 預覽 Chromium 支援 `text-wrap:balance`；不支援的舊瀏覽器退化為原折行，未驗】** **2 欄手機 tile 主值折行並出現孤字**：8 字主值「高檔震盪偏弱格局」在 173px 寬（內寬約 149px）折成「高檔震盪偏弱格／局」。證實線框 U2（12 字上限在 2 欄手機放不下）。`kpi_tile_m_390.png` | CSS 加 `text-wrap:balance`（或 `word-break:keep-all` 搭配手動斷點）；或 Phase 4 選欄數（W9／CV1-DR-12）時一併處理；元件已能撐 2 行，不是崩壞 |
| **F5** | 🟡 低 | **【✅ 已修：孤立點 ~~`r=2.2`~~ → QA 看圖後再加大為 `r=2.5`（📌 2026-10-30 QA 輪，有意識的調整，不是漏刪；2.2 在 390 手機上仍偏小）；同輪 `<polyline>` 加 `vector-effect="non-scaling-stroke"`（屬性＋CSS 皆有；小倍數 SVG 被 `width:100%` 縮放時線寬不隨之變化），golden sha 已更新】** **孤立點太小**：`[1,nan,3]` 的兩個孤立點是 `r=1.5`（直徑 3px），在 100×48 的 sparkline 上只是兩顆小黑點，手機上近乎看不見，易被讀成「沒畫出來」。`sparkline_390.png` | `r` 取 2～2.5；或孤立點加 1px 外圈；不改缺口不連線語意 |
| **F6** | 🟡 低 | **【✅ 已修：`.cp-info` 邊框改引既有 `--ink-3`（對 `--panel` dark 4.97／light 5.34，≥3:1；測試以 WCAG 公式驗算兩模式；未新增 token、未改既有值）】** **資訊 chip 細邊框對比不足**：`--rule-2` 對 `--panel` dark 2.18:1／light 2.51:1（<3:1，WCAG 1.4.11 非文字對比）。但 chip 文字對比 dark 7.65／light 6.91、語意靠 icon＋字，不依賴邊框，故判 🟡；然而「資訊 chip 與其他族一眼可分」目前主要靠這條邊框。`palette_1440.png` 對比表 | 邊框改用 `--ink-3`（4.97／5.34）或維持並在 Phase 4 判定；對比值為本預覽腳本以 WCAG 公式計算，未經第二組複算 |
| **F7** | ⚪ 已知 | `.cp-ch-title` 以 `--sp-6`（16px）當字級（間距 token 借作字級，BACKLOG 已登）。視覺上標題 16px 可讀，不影響畫面，僅命名不當 | 新增字級 token（例 `--cp-title-fs`） |
| **F8** | ⚪ 極輕 | chip 實高：資訊／狀態 22px、護欄 23px（2px 粗框使內容超過 `min-height:22`）。同行 `align-items` 預設 stretch 看不出，手機換行混排時偶有 1px 差 | 護欄 `padding-block` 減 1px 或 `min-height:23px` 全族統一 |
| **F9** | 🟡 低 | **【✅ 已修（文件）：`chart_header_html` docstring 與線框 §3.2 一致——下限由呼叫端負責，冷啟動 2 顆為唯一合法例外】** **冷啟動 header 只有 2 顆 chip**（`chart_header_html` 只擋上限，下限由呼叫端負責；契約 §4 要 3～5）。線框 §3.2 冷啟動示意本來就畫 2 顆，兩者自相矛盾；元件不報錯，易被忽略 | 線框 Phase 4 明定冷啟動 chip 下限例外（2 顆即可），或元件提供 `min_chips` 參數 |
| **F10** | 🟡 低 | **【✅ 已修：`TopN.more_chip()` 回傳 `Chip(kind="topn_more", tone="info")`（資訊族、文字＝`TOPN_MORE_FMT`；不進 `META_KINDS` 封閉集合，放 `_EXTRA_KINDS`；hidden=0 → `ValueError`；同列最多一顆）】** **Top-N「另 K 筆見全部」沒有 chip builder**：`TopN.more_text` 只給字串，無對應 chip kind；預覽只能手寫 `cp-chip cp-info`。各頁日後各寫一份，樣式／重複外露規則（M19）無統一把關。`topn_390.png` | 提供 `topn_more_chip(topn)`（沿用資訊族、不新增 kind 或明列為例外），納入 chip 去重檢查 |
| **F11** | ⚪ 觀察 | 冷啟動時小倍數「整組縮一行」（D6=B）與「每格各自縮一行」兩種呈現，後者佔 3 列約 120px，前者 33px；若採 D6=B，呼叫端須用前者。`small_multiples_*.png` 最後兩段對照 | 線框／呼叫端規範寫明：冷啟動小倍數用整組單行，不要逐格 Missing |

### 3.1 看圖發現（QA 輪，2026-10-30；皆**不在 Phase 3 範圍修**，列待 Phase 4 線框／宿主決定）

> 看圖者為 QA 組＋本輪修正組；同樣屬於看 PNG 的主觀判讀，需 Phase 4 以真實 app 再驗。

- **Q1 護欄與資訊 chip 難分辨**：D3=A 護欄＝實線粗框、資訊＝細外框（F6 改 `--ink-3` 後兩者都偏淺灰），`palette_1440.png`／`chips_1440.png` 並排時要靠邊框粗細與字才分得出（例：`尚未定義` 護欄與 `資料 10/28` 資訊）。這是 **D3 設計的代價**（不得用紅／虛線區分），非元件缺陷；Phase 4 線框須請客戶確認是否接受，或另提區分手段（例如護欄固定置於 chip 列最前並與其他族留間距）。
- **Q2 Top-N「查看全部」不像入口**：`topn_*.png` 的「另 K 筆」chip 與「查看全部（N 筆）」目前只是文字／資訊 chip，視覺上不像可點入口；真正入口形式（連結／按鈕／展開）待 Phase 4 線框。
- **Q3 flex 等高的前提**：F2 的 tile 等高依賴宿主格網 `align-items:stretch`；宿主不 stretch 時 tile 自然高度差仍約 58px。**Phase 4 宿主格網必須 stretch**，須寫入各頁線框。
- **Q4 placeholder 100px 寬折兩行**：`sparkline_*.png` 冷啟動／缺值 placeholder 在 100px 寬被折成兩行（「請按／更新」），可讀但不精緻；是否放寬寬度或縮短原因字留 Phase 4。
- **Q5 ⬜ 兩種語意同符號**：狀態 idle（尚未載入）與護欄 `尚未定義` 都用 ⬜；靠邊框粗細＋字區分（見 V8／V9 列）。這是 `UI_STATE_META`／既有護欄句的既定符號，元件不得自改；若客戶覺得混淆須改符號體系（另案）。

未發現：橫向溢出、被裁字（`clipped` 全空）、紅色誤用（紅只出現在 failed）、`title=` 屬性（`[title]` 0 個）、虛線護欄。

## 4. Visual Fidelity Gate 元件層自評（`docs/governance/UI_VISUAL_FIDELITY_GATE.md` §2；本預覽只涵蓋元件層，頁面層 N/A）

> 依 Gate §5.1：頁面層（A1～A5、A7、A10、A11、V1～V7）**N/A**——Phase 3 不掛頁，0 頁 import `compact`。以下為**單組自評**，判定者仍須獨立 QA（≥2 組）＋總管複驗抽樣；**不得**由本表宣稱 Gate 通過。

| 項 | 自評 | 證據與保留 |
|---|---|---|
| **A6 尺寸** | ✅（元件本身）／🟡（原生圖未驗） | Primary 圖槽量測 882×220（桌）、332×140（手）＝上限整；sparkline `svg` 48／64 ≤64；小倍數格 SVG 64 ≤96；tile 最高 154 ≤160。🟡 Primary **原生折線圖**在預覽中是灰框示意（Streamlit 原生圖無法放進靜態 HTML），220／140 上限對真圖的符合度**未驗**（線框 U5） |
| **V8 chip 文字化** | ✅ | 每顆 chip 皆 icon＋字（無純色塊）；紅只出現在 `failed` chip／Missing 槽，stale 為琥珀；chip 模組不經訊號文字頻道（`compact.py` 不 import `_ui_kit`，AST 守衛在 `tests/ui_v2/test_compact.py`，**本次未重跑測試**）。🟡 `⬜ 尚未載入`（狀態）與護欄 `⬜ 尚未定義` 用同一方框 glyph，只靠邊框粗細＋字分辨——設計如此（V9 規定），但看圖時需讀字（`chips_1440.png`） |
| **V9 Missing 符號** | ✅ 🟡 | 預覽出現的 idle ⬜／empty ▨／retryable ⟳／not_applicable ⊘／partial ◧ 3／5／unwired ⛔／failed 🔴 全部來自 `UI_STATE_META`，無同一狀態兩種符號；Missing 槽與 sparkline placeholder 皆未畫線點軸格線。🟡 F3：同一 tile 內「尚未載入」外露兩次（chip＋placeholder） |
| **V10 工程字樣** | ✅（元件）／🟡（預覽外殼） | `compact.py` 預設文案、各元件輸出的可見文字 0 命中契約 §18 清單。~~我的預覽夾具未帶工程字。「C2b＋RC-VISIBILITY Gate」若出現屬契約 §18 的客戶自訂措辭例外（DEC-081 Q2-2），本預覽未使用。~~ **📌 2026-10-30 QA 更正（有意識的更正，不是漏刪；原自評與事實不符）**：`kpi_tile` 冷啟動第三張 tile（建議總持股水位）**使用了**客戶逐字例外句「風險上限／獨立顯示待 C2b＋RC-VISIBILITY Gate」（契約 §18／DEC-081 Q2-2），含工程字樣 `C2b`／`RC-VISIBILITY`，屬客戶自訂措辭例外；`gen.py` 現以 `say_verbatim=True` 傳入（逐字、不計入卡面 60 字、不截），`kpi_tile.html` 內該句出現 1 次。🟡 預覽外殼的標註文字（如 `UI_STATE_META`、`render_fold`、`TopN.empty`）含工程字樣，但在 `pv-note`／`pv-state` 註解區，**不屬元件輸出**，若要逐字掃描 PNG 需排除 |
| **V11 無 hover 依賴** | ✅ 🟡 | 全預覽 `[title]` 屬性＝0；元件資訊皆可見文字。🟡 sparkline `<svg>` 內 `<title>` 與 `aria-label` 帶名稱＋窗口，**只有**「窗口 chip 在可見處」才算不依賴 hover——`sparkline_svg` 單獨使用時不保證（`kpi_tile_html` 有擋，小倍數由組級 chip 負責）；hover 行為本預覽**未實測**（headless 無 pointer 互動） |

整體：元件層無 ❌；🟡 項目＝F1～F5、F9、F10（需線框或後續步驟確認）。

## 5. 限制（這份預覽**沒有**證明的事）

1. **不是 Streamlit 渲染**：靜態 HTML＋`page_css`＋`compact_css`。真實頁面會被 Streamlit 的 markdown 容器 padding、段落 margin、基準字級與 `st.columns`／expander 包裹，實際間距、手機換行位置**可能不同**；掛頁（Phase 4）後必須以真實 app 重量。
2. **原生折線圖與 `st.expander`／`st.segmented_control` 都是外殼示意**（灰框、靜態展開區、手刻膠囊）；D8=B 在 floor 1.56 的實跑驗證（Plan §16 步驟 4）**未做**。
3. **字型與瀏覽器**：Linux headless chromium＋WenQuanYi／Noto Color Emoji；使用者裝置（iOS／Android／Windows）的 CJK 字寬、emoji 外觀（尤其 ⬜、🕒、✅）會不同，chip 換行點可能變動。
4. **色彩對比**：由 `gen.py` 以 WCAG 相對亮度公式算出（`palette_*.png`），未經第二組複算；light 模式只截 chips 一張（`chips_light_1440.png`），其餘元件 light 未截圖。
5. **夾具**：所有資料為合成（※示意），sparkline 曲線為正弦波，不代表任何真實行情；未測極端值（極大／極小／極長系列）的視覺行為（單元測試另有覆蓋，本預覽未看）。
6. **未驗**：D6=B 載入後撐開造成的位移量、站殼間距（Plan §16 步驟 3）、floor 1.56 實跑、觸控互動、hover。
7. 本預覽為單組產出；判定者獨立 QA 仍須各自看圖。
8. 副作用：`gen.py` 為對帳逐字句而 `import src.ui.views._market_blocks`，會拉起 streamlit／services 並印出無害的 `No runtime found` 警告；已確認未寫入任何 repo 檔案（`git status` 僅新增本批預覽目錄與 `tools/phase3_preview/`）。若不想 import，可刪除 `_verify_fixture_strings` 呼叫（只影響對帳訊息）。
