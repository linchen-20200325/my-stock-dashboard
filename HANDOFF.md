# HANDOFF — `my-stock-dashboard` 專案交接

> **建立日期 2026-09-24**（本版為**全文重寫**；舊版只交接了「融資餘額燈」一條支線，
> 沒寫專案是什麼、文件該讀哪些、v2 UI 主線做到哪、環境有什麼坑）。
>
> **本檔的讀者是「一個完全沒有任何上下文的 AI」。**
> 因此：
> - 每個宣稱都附 **檔案路徑 + 符號名**，讓你能自己查證；依 `CLAUDE.md` §8.2.A.0 規則 1，**本檔不寫行號**。
> - 會漂移的量測值一律標「（量測日 2026-09-24）」或改寫成「請現場執行 `<指令>`」（§8.2.A.0 規則 4）。
> - **實測事實**與**未經第二組驗的判斷**分開標示，後者逐條標 ⚠️（§-2 規則 6）。
> - 專有名詞第一次出現時用一句話解釋。
>
> ⛔ **不得把本檔任何全稱句（「只有…」「全部…」「沒有其他…」）當成既定前提。**
> 本檔多數盤點是**單組**做的（見 §8 誠實揭露表），接手請自行複驗。

---

## ★ 未完成項目（唯一清單，每輪開工先讀）

> ⭐ **規則（客戶 2026-09-26）**：每一輪**先讀本節**；發現過期 → **先更新本節再動工**；項目結案 → 移到文末「已完成（近期）」並附 merge hash。
> ⛔ **全 repo 只有這一份現行待辦清單**；本檔其他段落（§3.2、§6.4、§6.5 等）的待辦／待裁表**保留為歷史紀錄**，一律以本節為準。
> **量測基準**：`origin/main` `f14c5fd`（PR #697；2026-09-26 更新，前一版基準為 `07f8800`＋#696 待合併）。「誰決定」＝客戶 or 總管；標 ⚠️ 者為**總管判讀**，客戶一句話可推翻。
> ⚠️ 本清單由**單組**彙整（§-2 規則 6），⛔ 不得當成「repo 已無其他待辦」的全稱前提。

**A. 本輪進行中**

（**無**）—— 原 A1（「▸ 詳細」a11y）、A2（方向列補 4 盞）已由 #697 `f14c5fd` 結案，見文末「已完成（近期）」與下方 **B3 子表**。

**下一步候選（總管可自主）**：（**無**）—— 2026-09-26 逐項檢查：B 區全部卡在客戶的規格／文案／新源／授權；C 區是總管已判「不做」或「僅登記、§-1 不主動動工」；D 區要實機或線上環境，沙箱做不到。B12 §9 ①② 的「由誰裁」屬總管職權、可先判歸屬，但即使裁了也因客戶「不動卡面」拍板而無可動工項。C5 的幾項小修（註解名不符、未用 import、`pr-check.yml` 失效觸發）技術上不需客戶輸入，但**無 bug 觸發**，依 §-1 只在任務碰到該檔時順手收尾，⛔ 不單獨開工。⚠️ 單組判讀。

**B. 等客戶（規格／文案／新源／授權）**

| # | 項目 | 現狀 | 卡在哪 | 下一步 | 誰決定 |
|---|---|---|---|---|---|
| B1 | 方向列 `us10y`（美債 10 年）—— ②需新源 | 「無資料」 | 燈只用單點 FRED；`^TNX` 是不同源 | 客戶指定可接受的新源 | 客戶 |
| B2 | 方向列 `dxy`（美元指數）—— ②需新源 | 「無資料」 | 本地無歷史可量平盤帶；備援 DX-Y.NYB→DX=F→UUP 尺度不同 | 同上 | 客戶 |
| B3 | 方向列其餘「無資料」—— **逐盞見下方 B3 子表**（含 #697 查證後維持無資料的 `health`／`jingqi`／`tw_export`） | 「無資料」 | 見子表 | 見子表 | 見子表 |
| B4 | 今天頁 6 塊未接線（§6.4 舊寫「7 塊」，「風險」格已由 #692 接上） | unwired | **交易日**：無台股假日曆（也需源）；**Sheet 綁定**：`bound_empty`／`failed` 無文案、live 需 sheet 名；**動能**：客戶裁示維持不接（無公式）；**今天該做的事**：無推導規格；**AI 摘要**：無 prompt／規格，須點擊才跑；**外資淨買賣**：單位未定 | 客戶給文案／規格（動能除外） | 客戶 |
| B5 | K1：燈卡「門檻出處」「命中來源」露出內部識別字（來源 §6.4；相關台帳 `docs/v2/prototype/FIELD_LABELS_TODO.md`） | 未修 | 客戶的 **16 盞白話對照表**未到；⛔ AI 不得自擬 | 等對照表 | 客戶 |
| B6 | 標記矛盾：#7「缺漏·可重跑」vs 文字「重按也一樣」／「有效的結果」—— hold／inspect／why 其餘卡**合一條**（客戶：不另開單）。含已修靜默失敗卡（`find.screen_result`／`hold.take_profit`／`hold.switch`／`hold.deep.dividend_cash`）尚未登記進 `V2_VALID_EMPTY_SPEC`（main `f14c5fd` 上仍只登記 `hold.portfolio_count`） | 未修 | 與持股頁同一根因；改 builder／文案需授權 | 客戶授權後一次修 | 客戶 |
| B7 | 資料污染：`finmind_margin.parquet` 單位混用；`finmind_m1m2.parquet` 負值；M1B-M2 退到代理層未標明（`is_proxy_tier` 被丟）（來源 §6.4／§6.5） | 未修 | FinMind token＋資料層凍結；刪資料可能**不可逆** | 客戶選 §6.5 (A) 給 token 重抓 / (B) 刪列 | 客戶 |
| B8 | 融資「趨勢燈」後續方向 (a′)(b)(c)（來源 §6.5） | 未動 | 相對分位實測無鑑別力 | 客戶決定要不要做、走哪條 | 客戶 |
| B9 | QA 殘留（需文案／需確認）：① `find` 唯一勾選因子自身輸入失敗 → 灰色「有效的結果」；② `hold.take_profit` 在 `current_price` 為 `None` 時；③ 配息卡 `why` 寫「L3…拋出例外」但錯在 L1（既有文案限制）；④ `vix` 平盤帶用 GitHub `datasets/finance-vix`（CBOE 鏡像，僅校準）量測 —— 請客戶確認源可接受 | 未修 | 需客戶文案／確認 | 等客戶 | 客戶 |
| B10 | 分支政策矛盾、PR #675（draft、base `v2`）（來源 §4.2～4.3） | 未處理 | 分支政策為客戶頒布 | 依 §4.4 格式附推薦請示 | 客戶 |
| B11 | `STRATEGY_INTAKE.md` §4 七項待裁（三套方法論納入與否等） | 未裁 | 客戶未回 | 等客戶 | 客戶 |
| B12 | 原型卡面內部程式符號（B 層 52／48／45 處，`docs/v2/prototype/FIELD_LABELS_TODO.md`）：客戶 2026-09-22 拍板「**不修、只登記**」；甲類 7 項規格已有中文標籤但依拍板不動卡面；乙類待補規格；丙類與 §7 家族等該檔 **§9 兩個裁示點**（① 線框 `name` 算不算「規格已給標籤」② 卡面是否同享「引述」例外）（2026-09-26 完整性複查補登；與 B5 同源不同射程：B5 管燈卡兩欄，本條管原型全卡面） | 只登記 | 不動卡面的拍板＋規格未補；§9 ①② 該檔自陳「不判定由誰裁」 | 客戶補規格／放行卡面後再動；⚠️ 量測釘在 `e8d3a75`（2026-09-22），其後 #687～#691 卡化已改卡面，數字可能已漂移（未重測） | 客戶（§9 ①② 歸屬未定） |

**B3 子表：方向列「無資料」逐盞**（2026-09-26；16 盞中 **11 盞無資料**；已有真方向 5 盞：`margin`／`bias_240`／`ism_pmi`／`vix`／`ndc_signal`，出處 `shared/lamp_direction_thresholds.py`）
類別：**①沒歷史 ②需新源 ③判斷未定 ④其他**。

| 燈 key | 類別 | 為什麼無資料 | 要解需要什麼 | 誰決定 |
|---|---|---|---|---|
| `health`（總經健康評分） | ④ | 唯一歷史是前進式驗證凍結檔 `data_cache/macro_forward_test/signals.parquet`：`date` 是 **cron 執行日**不是交易日（區間缺 4 個交易日、含週六列、09-22 過期重複列）；燈值 dict 不帶 `health_partial`、輸入不同（cron `fetch_macro_bundle` vs 頁面 session）；且 `src/ui/views/page_today.py::OUT_OF_REACH_LIGHT_KEYS` 本就列著 `health` | ⚠️ 需與燈值同源、按交易日落地的歷史（屬新增資料落地，§-1.2 資料層凍結）—— 編修組判讀 | ⚠️ 客戶 |
| `jingqi` | ④（雜訊） | 5 日均的 lag-20 自相關 **0.025**（`twii_ohlcv.parquet` 4,886 列）⇒ 20 日差是雜訊，同 `adl` | — | 總管：**不做**（同 C1） |
| `tw_export`（台灣出口） | ①／② | L1 只回最新一點；本機無出口 YoY 歷史、外部源 403；5 路 fallback 口徑不一；MOF 月資料回溯修正 ±5% | 可提供歷史的源；日後接須限定同一條 fallback、同一次抓取的相鄰兩月 | 客戶 |
| `m1b_m2_gap`（M1B-M2） | ④（資料損壞） | `finmind_m1m2.parquet` 負值，程式刻意不讀 | 先解 B7 | 客戶（同 B7） |
| `fut_net` | ① | ~~僅存 14 天~~ → L1 `src/data/macro/leading_indicators.py::build_leading_fast` 每次只**即時**抓近 ~14 天（TAIFEX 逐日、有 timeout 預算），`data_cache/` 無落地歷史 ⇒ **不會自己累積** | ~~等累積~~ → 需新增落地歷史或拉長抓取窗（動 L1，§-1.2） | ~~⚠️ 總管~~ → ⚠️ 客戶 |
| `us_core_cpi` | ② | 只有前值、無日期 | 帶日期的源 | 客戶 |
| `news_systemic` | ③ | 無數值序列、判準未定義（亦列於 `OUT_OF_REACH_LIGHT_KEYS`） | 判準規格 | 客戶 |
| `foreign_net` | ④（燈未接線） | 決策端未接線（燈永遠不亮，卡上不出此列）；FinMind 法人單位未確認（§4.1） | 先查證單位 | ⚠️ 總管 |
| `adl` | ④（雜訊） | 見 C1 | — | 總管：**不做**（C1） |
| `us10y`／`dxy` | ② | 見 B1／B2 | 見 B1／B2 | 客戶 |

⚠️ `fut_net` 列的更正（「等累積」→ 不會累積、誰決定改客戶）為**編修組 2026-09-26 程式閱讀**（`build_leading_fast` 的 14 天抓取窗＋`git ls-tree origin/main data_cache/` 無對應檔），**未經第二組驗**；原文保留加刪除線。類別歸屬中 `health`／`jingqi`／`tw_export` 依總管 2026-09-26 指示，其餘為編修組歸類。

**C. 登記不做／僅登記（總管）**

| # | 項目 | 理由 | 誰決定 |
|---|---|---|---|
| C1 | `adl`（騰落比）與 `jingqi` 方向列 **不做**，維持「無資料」（`jingqi` 2026-09-26 由 #697 量測後併入） | `adl`：`ad_ratio` 為單日估計，幾乎無自相關（`twii_ohlcv.parquet` lag-1 −0.028、lag-20 0.016）⇒ 20 日比較會誤導。`jingqi`：5 日均 lag-20 0.025，同理 | 總管（已記錄供客戶知悉） |
| C2 | `hold.switch` 嚴格模式：空頭／警戒下所有存活者都未評分時漏紅 | 不猜就分不出來 | 總管 |
| C3 | 配息：yfinance `.dividends` 空但未拋例外 ⇒ 仍視為「沒配息」 | 分不出來 | 總管 |
| C4 | `vix` L2 log 理由「沒有歷史序列」在序列被拒時不精確 | 僅 log | 總管 |
| C5 | `load_binding` 契約漂移（假設性）；`page_inspect.py` 未用的 `UI_EMPTY` import（既有 pyflakes）；`src/ui_v2/render.py` `grid_html`／`layer_html` 空行外露（僅原型路徑）；`markup.py` title／fold 空行只在頁面層擋；註解 `V2_VALID_EMPTY_PAIRS` 與實際符號 `V2_VALID_EMPTY_SPEC` 不符（§6.4）；`pr-check.yml` 觸發不存在的 `ui-v2`（§4.5） | 僅登記，§-1 不主動動工 | 總管 |
| C6 | §4.5 其他 8 條分支（`feat/v2-*`／`test/ui-v2-guards`／`wireframe/stock-ia-5pages`／`data`／`claude/my-stock-dashboard-ui-rewrite-r40gjc`）是否已合併、可否刪 —— **未查證**（§8 #14）（2026-09-26 完整性複查補登） | 僅登記；刪分支前須查證且屬不可逆，§-1 不主動動工 | 總管（查證）／客戶（刪） |

**D. 待線上／實機驗證（沙箱驗不到，§-1.5.A-7）**（2026-09-26 完整性複查補登）

| # | 項目 | 現狀 | 卡在哪 | 下一步 | 誰 |
|---|---|---|---|---|---|
| D1 | 「▸ 詳細」a11y（#697）在真 iPhone／VoiceOver 的朗讀與切換 | 程式＋5 頁 72 組截圖已驗（滑鼠／觸控零像素差）；**實機未驗** | 沙箱無 WebKit／VoiceOver | 客戶用手機試用時順帶確認 | 客戶 |
| D2 | `ndc_signal` 方向列（#697）對線上真資料 | 單元測試已驗；**未對真資料跑** | 沙箱連不到 FinMind／data.gov.tw；StockFeel／MacroMicro 分支只有單點 ⇒ 命中該分支時顯示「無資料」屬預期 | 部署後看今天頁該卡是否出「較上月」 | 客戶 |

**已完成（近期）**

| 項目 | merge |
|---|---|
| 找標的頁卡化 | #687 `83e0f47` |
| 我的持股頁卡化 | #688 `66e4fe0` |
| 標記 #11「▨ 無資料」（規格變更） | #689 `3e576ef` |
| 靜默失敗批 1（`find.screen_result`、`hold.take_profit`） | #690 `2a56483` |
| 查一檔、憑什麼兩頁卡化（§3.2「四頁待卡化」至此結案） | #691 `f38dbd4` |
| 今天頁「風險」格接上 danger | #692 `10f385c` |
| `hold.switch` 靜默失敗（L3）＋ 16 盞方向登錄（VIX 真值）＋ hover 空行修正 | #693 `ac96000` |
| 配息卡靜默失敗（L1 `fetch_etf_dividends`，失敗冷卻 180s）＝ 靜默失敗第 2 批 | #694 `d48709b` |
| 5 頁卡片文字空行破版 | #695 `07f8800` |
| 測試缺口補齊（僅測試） | #696 `6ec1cb9` |
| （原 A1）「▸ 詳細」a11y：可及名稱改為「▸ 詳細 ＋ 卡片標題」（`aria-labelledby`）、`aria-controls` 指向內容區、鍵盤焦點框 1px 點線 → 2px 實線並外移（`outline-offset:2px`，不壓「▸」）；⛔ 刻意不用 `aria-expanded`（無 JS 無法隨勾選更新，寫死會對朗讀說謊，§1）；5 頁滑鼠／觸控零像素差異。📌 開關在此之前**本來就能用鍵盤聚焦**（§6.4 舊「鍵盤點不到」已加註更正）。⚠️ 實機未驗 → D1 | #697 `f14c5fd` |
| （原 A2）方向列：`ndc_signal` 改真方向（官方整數 9–45、帶寬 0、「較上月」；L1 `fetch_ndc_block` 只在 FinMind／6099 分支從同一次抓取附帶上月值，純新增欄位、不新增抓取）；`health`／`jingqi`／`tw_export` 經量測＋獨立複查**維持「無資料」**（原因見 B3 子表）。⚠️ 未對真資料實測 → D2 | #697 `f14c5fd` |

---

## 0. 這個專案是什麼

> **這一節解決的疑問**：我接手的是什麼東西？誰在用？跑在哪裡？

**「台股 AI 戰情室」** —— 一位台股散戶（本專案的「**客戶**」本人）的**個人投資決策輔助儀表板**。
**Streamlit 單頁應用**，部署在 **Streamlit Cloud**（合併進 `main` 就自動重新部署）。

它要解的問題：把「**總經現在紅燈還綠燈 → 該不該加碼 → 買哪一檔 → 手上這些該不該換**」
這條決策鏈，從散落各網站的人工查詢，收斂成一個畫面。

**四大資料流**（出處：`DATASTATION.md` 檔頭逐字）：**總經狀態／個股評分／AI 分析／風控**。

| 面向 | 實測現況（量測日 2026-09-24） |
|---|---|
| 進入點 | 根目錄 `app.py`（Streamlit 主腳本） |
| **v1 線上 7 個頂層頁籤**（`app.py` 的 `st.tabs(...)`，逐字） | `🌍 市場環境`／`🔬 選股`／`🏦 ETF`／`🔧 工具箱`／`💼 我的持股戰情室`／`📁 組合管理`／`🧬 AI 問答` |
| 排程回寫 | `.github/workflows/` 共 **16 個** workflow 檔，其中 **12 個含 `schedule:`**（cron 自動跑、回寫 `data_cache/`）。另 1 支是 CI（`pr-check.yml`） |
| 台股資料來源 | 多走 **NAS Squid proxy**（`src/data/proxy/proxy_helper.py`） |
| 使用者持股帳本 | **Google Sheets**（`src/data/portfolio/gsheet_portfolio.py`，OAuth） |
| 測試 | `tests/` 底下 **374 支 `test_*.py`** |

⚠️ **根目錄沒有 `README.md`**（實測 `ls README.md` → No such file）。
但 `ARCHITECTURE.md` 的目錄樹仍把 `README.md` 列在裡面 ⇒ **`ARCHITECTURE.md` 該處已過期**。
⛔ 不要去找一份不存在的 README；**本檔就是入口**。

---

## 1. 接手第一天只讀這三份

> **這一節解決的疑問**：21 份根目錄文件 + 72 份 `docs/` 文件，我到底先讀哪個？

### ① `CLAUDE.md` 的**六節**（⛔ 不要整份 2,198 行讀完）

`CLAUDE.md` 是本專案的**憲法**，位階規則是「**數字越小、位階越高**」（§-2 > §-1.5 > §-1.2 > §-1 > §0~§8）。

| 節 | 一句話 | 為什麼非讀不可 |
|---|---|---|
| **§-2** | **每一件任務都要派 subagent 執行；總管不自己寫實作；總管必須自己複驗 subagent 的關鍵宣稱**；調查／稽核要**多組獨立**派工，不可自己查自己 | 這是本 repo 最常被違反、也最貴的一條 |
| **§-1** | **沒有客戶指派、沒有實際 bug 觸發 → 停手等指令**，不主動找事做 | ⛔ 看到任何「待修清單」都不是動工授權 |
| **§-1.2** | **分支政策** —— 客戶原文「新分支名 `v2`」「**`main` 保留 v1，不合併直到 v2 完成**」「v2 上線時直接合併 `main`」；資料層凍結 | 與實測現況有矛盾，見 **§4** |
| **§-1.5.D v3 §03** | **唯二能問客戶的事**：① UI 版面／欄位增減／分頁動線異動（**必須先出文字線框草稿**）② 商業邏輯衝突與不可逆操作。其餘（欄名、TTL、取數路徑、目錄命名、死碼何時刪）**一律內部拍板，且嚴禁拋選擇題**（要問必須附推薦方案） | 決定你什麼時候可以開口問客戶 |
| **§-1.5.H** | **回覆紀律**：每輪 ≤ 15 行、表格優先、結尾必加 `⏸ 等待你回覆：【明確問題】` 或 `✅ 本輪完成，無需回覆。` | 每一輪都會用到 |
| **§1** | **Fail Loud, Never Fake** —— ⛔ 禁 `fillna(0)`／沉默 `ffill`／dummy 資料／`except: pass`／自己估一個合理值。**錯的數字比沒有數字更危險** | 客戶的紅線 |

### ② **本檔**（`HANDOFF.md`）

### ③ `docs/v2/README.md` ＋ `docs/wireframes/stock_ia_v1.html`

後者是**五頁 IA（資訊架構）的線框 SSOT**（單一真相源）——
`shared/ia_nav.py` 的頁 id 與顯示名**直接沿用該 HTML 的 `PAGES` 資料結構**，⛔ 不另取名。

### 動工前補讀

- `PROCESS.md`（**64 行，很短**）—— 流程治理／PR 規範／Anti-Loop。
- `STATE.md` 的**最上面一段**。
  ⚠️ **`STATE.md` 有 4,594 行，往下全部是歷史紀錄，⛔ 不是待辦清單。**
  ⛔ 不要從裡面挑一條出來當任務做（違 §-1）。

---

## 2. 文件地圖

> **這一節解決的疑問**：哪份文件有用、哪份已過期、我遇到某個問題該翻哪一份？

**根目錄 21 份 `.md`，合計 14,151 行**（量測日 2026-09-24；請現場跑 `wc -l *.md` 複驗）。

### (a) 必讀

| 檔 | 行數 | 內容 | 何時讀 |
|---|---|---|---|
| `CLAUDE.md` | 2,198 | **專案憲法**（資料完整性 + 派工 + 溝通邊界 + 分層架構） | 第一天讀 §1 列的六節 |
| `PROCESS.md` | 64 | 流程治理、PR 規範、卡關救援 | 動工前 |
| `STATE.md` | 4,594 | 版本流水帳 | **只讀最上面一段**；⛔ 其餘是歷史 |
| **本檔** | — | 交接 | — |

### (b) 遇到才查

| 檔 | 行數 | 內容 | 何時讀 |
|---|---|---|---|
| `ARCHITECTURE.md` | 2,332 | 七層分層、模組住哪一層、依賴方向 | **找「某個檔屬於哪一層」時**。⚠️ **部分已過期**（例：目錄樹仍列不存在的 `README.md`） |
| `SPEC.md` | 1,460 | 功能規格、UI 字串、跨模組介面契約 | 改 UI 文案或跨模組介面時 |
| `DEAD_CODE.md` | 131 | **死碼登記簿（全 repo 唯一入口）**，編號 `D-0NN` | **刪任何東西前必查**（`CLAUDE.md` §8.2.A.3 客戶裁示）。⛔ 它**不是**全 repo 死碼的窮舉，「未登記 ≠ 不存在」 |
| `DATASTATION.md` | 545 | 各模組函式簽章與回傳結構（給外部 import 用） | 要從外部 import 本專案模組時 |
| `MACRO_MASTER.md` | 126 | **總經「五桶 16 盞燈」現況盤點** | 動總經燈之前 |
| `MACRO_HEALTH_REWEIGHT_PROPOSAL.md` | 104 | 健康評分權重調整提案 | 動權重時 |
| `STRATEGY_INTAKE.md` | 147 | 客戶一份外部策略提示語的**納入前盤點**，七項待客戶裁示 | 客戶提到「那份策略」時 |
| `HANDOFF_MARGIN_RELATIVE.md` | 112 | 融資餘額燈「相對分位」支線的完整細節 | 見本檔 **§6** |

**名詞：什麼是「五桶 16 盞燈」？**
`shared/macro_buckets.py` 的 `BUCKET_ORDER` 逐字 `["long", "mid", "short", "chips", "news"]` ——
把 16 個總經指標分成五個「桶」，每個指標算一盞紅／黃／綠燈：

| 桶 | 盞數 | 燈 key |
|---|---|---|
| 🌳 `long` 長期／結構・景氣位階 | 3 | `health`、`ndc_signal`、`m1b_m2_gap` |
| 📈 `mid` 中期／景氣循環 3–12 月 | 6 | `ism_pmi`、`us_core_cpi`、`tw_export`、`bias_240`、`us10y`、`dxy` |
| ⚡ `short` 短線急殺／即時 risk-off | 3 | `vix`、`adl`、`fut_net` |
| 🧩 `chips` 籌碼／大戶定位 | 3 | `margin`、`jingqi`、`foreign_net` |
| 📰 `news` 新聞／系統性風險 | 1 | `news_systemic` |

另有 **2 條「參考走勢」不算燈**（`usdtwd` 匯率、`taiex` 加權指數，掛 `REFERENCE_BUCKET`，
不進 x/16 分母）。**桶內用 worst-of 彙總**（紅 > 黃 > 綠），**桶間無權重**。
（出處：`MACRO_MASTER.md` §1，該組已引 `shared/macro_buckets.py` 的 `BUCKET_ORDER` / `aggregate_level` 逐字。）

### (c) ⛔ 不用讀（歷史／已過期／非規格）

| 檔 | 為什麼不用讀 |
|---|---|
| `HANDOFF_2026-08-15.md`（147 行） | 已過期的舊交接；內含 **Windows 本機路徑**，在本容器裡完全不適用 |
| `PLAN_T1_T2.md`（317）／`PLAN_T3.md`（240）／`PLAN_T4.md`（224） | 三份計畫**皆已執行完畢**，只剩歷史價值 |
| `BATCH_A_DELIVERY.md`（170） | 一次性交付紀錄 |
| `MACRO_CALIBRATION.md`（70） | 2026-07-12 自動產生的校準報告。⚠️ **它自己在「樣本不足／限制聲明」段寫明是 `TWII-only mode`** —— 只注入 `^TWII` OHLCV，**外資買賣超／ADL／外資期貨／M1B-M2／jingqi 全部以「中性預設」（0 / 1.0 / None）代入** ⇒ 報告裡的 precision／recall **不是完整系統的表現**。⛔ 不要引用它的數字下結論 |
| `STRATEGY_MANUAL.md`（909） | 檔頭自陳「**系統版本 v10.53.0，更新日期 2026-05-05**」，而**現行 code 已到 v19.x** ⇒ 僅供了解歷史設計背景 |
| `ARCHIVED_FEATURES.md`（92） | 已下架功能的存檔 |
| `MACRO_HEALTH_WEIGHT_PROPOSAL.md`（27） | 機器產物，~~待人工審查~~，非規格（📌 2026-09-26 註：檔內自陳「待人審」已過期 —— 權重已於 2026-07-11 採納，PR #517 `a8035c6`〔v19.102 Phase 3 收官，`STATE.md` 同日段〕；⛔ 非現行待辦） |

### (d) `docs/` 樹（**共 72 份 `.md`**，量測日 2026-09-24）

| 路徑 | 檔數 | 定位 |
|---|---|---|
| `docs/v2/README.md` | 1 | **v2 存檔的導讀頁，先讀它**（它自己說「先讀完這一頁再讀任何一份文件」） |
| `docs/v2/spec/` | 28 | **v2 規格庫** —— 含七份 `UI_PAGE_*`（五頁各一 + `UI_COMPONENTS` + `UI_TOKENS`）、六份 `DATA_MAP_*`（每頁的資料對映）、`DECISIONS_PENDING.md`（~~待客戶裁示~~ → 📌 2026-09-26 註：D-1~D-5 已於 2026-09-23 全數裁示、檔名沿用，見該檔末「裁示落地對照表」；⛔ 非現行待辦）、`DECISION_RULES.md`、`UI_PRINCIPLES.md`（客戶 24 條視覺原則） |
| `docs/v2/audit/` | 18 | ⛔ **稽核軌跡，不是規格，⛔ 不可照著做**。它記的是「誰查了什麼、查到什麼錯」 |
| `docs/v2/wireframe/` | 18 | 五頁線框的**原始碼**（`wf_page_*.js` + `assemble.js` Node 組裝器）。**組裝產物刻意不入庫** |
| `docs/v2/stage1/` | 4 | 含 **`INDICATOR_SSOT.md`** —— ⭐ **裡面的 `N-1`／`N-2`／`N-3` 三條根因，就是「為什麼要做 v2」的答案**（見下） |
| `docs/v2/prototype/` | 5 檔 + `__pycache__` | HTML 視覺原型與產生器，見 **§5** |
| `docs/wireframes/stock_ia_v1.html` | 1 | **五頁 IA 的線框 SSOT**（`shared/ia_nav.py` 的出處） |
| ⚠️ `docs/v2/HANDOFF_UI_2026-09-16.md` | 1 | **已過期**（它自己也標明「未經第二組複驗、不含新結論」） |

**⭐ `N-1`／`N-2`／`N-3` 是什麼**（`docs/v2/stage1/INDICATOR_SSOT.md` 逐字，⭐ v2 存在的理由）：

| 編號 | 缺陷 |
|---|---|
| **N-1** | `calc_fundamental_score` **量綱錯誤** —— `avg_div`（**元/股**）被當成**殖利率 %** 去比對 `YIELD_HIGH/MID/LOW` ⇒ **估值分與真實殖利率顛倒**（實測：真殖 1.80% 判「便宜區 >7%」、真殖 10.00% 判「偏貴 <3%」） |
| **N-2** | `calc_health_score` **缺值直接回 0** ⇒ 什麼都沒抓到的股票顯示「0 分 · 🔴 弱勢危險」。直接違反客戶紅線「缺失值不得填 0」 |
| **N-3** | `calc_sharpe` **回 `0.0` 繞過 ETF 綜合分的 rescale 機制** ⇒ 資料不足的 ETF 少一顆星，剛好跨過 `KEEP_COMPOSITE_MIN=0.65` ⇒ **「留下」翻成「觀察」** |

⚠️ 同一份文件還登記了 `N-4` ~ `N-14`（含兩條**憲法自己過期**的登記：`N-12` 指 `CLAUDE.md §3.3`
宣告「magic number ❌ 0 項」與實況不符、`N-14` 指 §8.2 寫錯 `exit_signals.py` 的所在目錄）。
⚠️ **這些是該組的單組結論，未經第二組獨立驗。**

---

## 3. 🔴 主線：v2 五頁戰情室 UI 重寫

> **這一節解決的疑問**：客戶真正在做的事是什麼？做到哪了？我加入時卡在哪一步？

**這才是專案主線。**（`CLAUDE.md` §-1.2 記載客戶拍板路線 A「**UI 全新重寫**」。）
舊版 7 個頁籤是「功能分類」導向；v2 五頁是「**決策問句**」導向。

### 3.1 五頁是哪五頁

**顯示名的 SSOT 在 `shared/ia_nav.py::PAGE_LABELS`（L0 層，純字串、零 I/O、零 streamlit）**，逐字：

| 頁 id | 顯示名 | 這一頁回答的問題 |
|---|---|---|
| `today` | `🚦 今天` | 今天整體環境如何？ |
| `find` | `🔍 找標的` | 該買哪一檔？ |
| `inspect` | `🔬 查一檔` | 這一檔到底好不好？ |
| `hold` | `💼 我的持股` | 手上這些該不該動？ |
| `why` | `📖 憑什麼` | 上面那些結論的依據是什麼？ |

⛔ **任何地方都不准手抄這些字串** —— `ia_nav.py` 的檔頭自陳，它存在的理由就是
「指路句裡的分頁名改了，指路句不會自己跟著改」這個已發生過的 bug。

### 3.2 各頁進度（量測日 2026-09-24）

> 📌 **現行待辦以文件開頭『未完成項目』為準**（2026-09-26）；本段保留為歷史紀錄。

五頁的實作檔在 **`src/ui/views/page_{today,find,inspect,hold,why}.py`**。

| 頁 | 卡面來源 | 狀態 |
|---|---|---|
| `page_today.py` | **v2 卡面** —— 實測 **20 處** `src.ui_v2` 引用，module 層 `from src.ui_v2 import components / markup / page_today` | **✅ 唯一已整頁卡化**。該檔自陳「手寫 12 列 ＋ SSOT 展開 21 列 ＝ **整頁 33 張卡**」（commit `383c933`，2026-09-24） |
| `page_find.py` | 舊 `_ui_kit` 卡面（**0 處** `src/ui_v2` 引用） | 仍待卡化 |
| `page_inspect.py` | 同上，0 處 | 仍待卡化 |
| `page_hold.py` | 同上，0 處 | 仍待卡化 |
| `page_why.py` | 同上，0 處 | 仍待卡化 |

⚠️ **重要澄清：五頁「都已經是卡片骨架頁」，⛔ 不是長文字牆。**
實測五頁**全部**都在用 `src/ui/views/_ui_kit.py` 的 `grid` / `render_card_isolated` / `section_header`
（每頁都有數處到十數處呼叫）。**差別只在卡面樣式是 v2 版還是舊版**，
⛔ 不要以為 `find`／`inspect`／`hold`／`why` 還沒開始做。

**名詞：什麼是「卡（card）」？** 畫面上一個獨立的資訊方塊，自帶標題、徽章（badge）與內容；
`render_card_isolated` 的「isolated」指**單張卡渲染失敗不會拖垮整頁**。

### 3.3 `src/ui_v2/` 契約層

這是 v2 卡面的**契約層**（定義「卡長什麼樣」的純資料與純字串），實測 **7 支 `.py`**（含 `__init__.py`）：

| 檔 | 職責 | 純度 |
|---|---|---|
| `tokens.py` | 設計 token（顏色／間距／字級） | **純層**（零 streamlit） |
| `components.py` | 元件契約，含 `BADGES`（徽章字典） | **純層** |
| `page_today.py` | 「今天」頁的**版面與狀態契約**，含 `_LAYER_PLAN`（層序） | **純層** |
| `markup.py` | 產 HTML/CSS 字串（`page_css` / `card_html`） | **純層** |
| `render.py` | ⚠️ **唯一 import streamlit 的** | `src/ui/views/page_today.py` 的註解**明文寫「⛔ 不得被 import」** |
| `app_today.py` | **demo 進入點**（`streamlit run src/ui_v2/app_today.py`） | 線上 `app.py` **走不到它** |

⚠️ **關於「`src/ui_v2/` 有沒有 production caller」**：PR #675 的描述（寫於 **2026-09-23**）說
「`src/ui_v2/` 至今仍 0 production caller」。**該敘述已被 2026-09-24 的改動推翻** ——
實測 `src/ui/views/page_today.py`（線上 `app.py` 會 import 的檔）**已經 import 了
`components` / `markup` / `page_today` 三支**。
⇒ **現況：`src/ui_v2/` 的四支純層有 production caller（只有「今天」一頁在用）；
`render.py` 與 `app_today.py` 仍無。**

### 3.4 五頁怎麼掛上去（⭐ 這是最容易搞錯的一段）

**不是頂層頁籤，是側欄 radio。** 實作在 `app.py`：

| 項目 | 實測值（逐字） |
|---|---|
| 元件 | `st.radio` in `st.sidebar` |
| 標題 | `🆕 新版戰情室（試用中）` |
| session key | `_sb_ia_page`（`app.py` 的 `_IA_NAV_KEY`） |
| 第一個選項 | `不使用（用下方原功能）`（`_IA_NAV_OFF`）—— **它不是一個頁 id** |
| 預設 | **`index=0` ⇒ 預設關閉**，畫面完全等同舊版 7 頁籤 |

**選到一頁之後會發生什麼**（`app.py` 的 `_IA_VIEWS` 分派區塊）：
主畫面**整片換成那一頁** → 呼叫 `_render_footer()`（免責聲明照出）→ **`st.stop()`**。
⇒ 舊 7 頁籤、全域置底常駐條、「🔗 我的組合」狀態列、「🧭 總經指南針」**都不渲染**。

**沒選時連 import 都不做**：五頁各有一支 late-import wrapper（`_ia_view_today` 等），
**只有被選到的那一支會被呼叫**。⛔ 刻意**不用 `importlib` 動態字串** ——
那會讓 `tests/test_c3_layering_guard.py` 的 AST 掃描看不見 `L6→L5` 這條依賴，等於把分層依賴藏起來。
另有一道 **Fail Loud 對帳**：`_IA_VIEWS` 的 key 集合與 `PAGE_LABELS` 對不起來就 `raise RuntimeError`
（**刻意用 `raise` 不用 `assert`**，因為 `assert` 在 `python -O` 下會被整條拿掉）。
守衛：`tests/test_ia_v2_sidebar_nav.py`。

⚠️ **歷史教訓（⛔ 不要重蹈）**：2026-09-07（PR #663～#665）曾把五頁掛成**頂層頁籤**，
變成 **12 個頁籤並排** → 手機上舊頁籤被擠出畫面 →
**2026-09-08 客戶拍板撤回，改成側欄 radio**（`app.py` 註解標記 FE-35）。

### 3.5 ⚠️ 新舊 UI 是**並存，不是取代**

- `CLAUDE.md` §-1.2 客戶原文逐字：「**舊版不刪，留在 `main`**」。
- `app.py` 註解逐字：五頁與舊 7 頁籤「**刻意並存，不得合併、不得改名**」，並逐條說明為什麼看似重複的其實是兩件事：
  - `🔬 查一檔`（新）＝「一個代碼進去、一份判決出來」 vs `🔬 選股`（舊）＝「篩一批出來」；
  - `💼 我的持股`（新）＝ IA v2 的**殼**（多數區塊仍標 `unwired`） vs `💼 我的持股戰情室`（舊）＝**線上已在跑的既有實作**；
  - `📖 憑什麼`（新）與舊的「🔎 資料診斷 / 📚 教學 / 🧬 AI 問答」三處功能重疊 —— **三處都保留、都沒動**。

**名詞：什麼是 `unwired`？** ＝「**版面已經畫出來，但還沒接上真實資料**」的區塊。
它會誠實顯示自己沒資料，⛔ 不是畫假數字（這是 `CLAUDE.md` §1 Fail Loud 的要求）。

**舊 UI 的規模**（量測日 2026-09-24）：`src/ui/tabs/` **22 支 `.py`**，
另有 `src/ui/etf/`、`src/ui/pages/`、`src/ui/render/`。

**名詞：`L0`~`L6` 是什麼？** `CLAUDE.md` §8.2 定義的**七層架構**，import 只能由高往低：

| 層 | 職責 | 代表目錄 |
|---|---|---|
| **L0** Infra | 常數／TTL／門檻／設定（被全層 import，⛔ 不得依賴任何 L1+） | `shared/`、`src/config/` |
| **L1** Data | 外部資料抓取／快取／proxy（⛔ 不得 import streamlit，除登記例外） | `src/data/` |
| **L2** Compute | **純函式**運算／評分／策略（⛔ 不得做 I/O） | `src/compute/` |
| **L3** Service | 業務邏輯編排／AI 整合 | `src/services/` |
| **L4** Render | 圖表生成／通用 UI 元件 | `src/ui/render/` |
| **L5** UI | Streamlit Tab / View 級組裝 | `src/ui/tabs/`、`src/ui/views/`、`src/ui/etf/`、`src/ui_v2/` |
| **L6** App | session 路由 + 全域編排 | `app.py` |

**名詞：`EX-PASSTHRU-1` 是什麼？** `CLAUDE.md` §8.2.A.1 登記的一條**分層豁免**：
L5/L6 本來不准直接呼叫 L1 的資料抓取函式，但若該函式**沒有對應的 L3 service**、
caller 端**只是取數**、且該函式**在 L1 內已自帶 `@st.cache_data`**，就豁免。
⛔ 但它**不涵蓋**「UI 檔內自己實作抓取」「UI 層自建 cache」「跨層直取底線開頭的私有符號」。
機械守衛：`tests/test_c3_layering_guard.py`。

---

## 4. 🔴 分支現況

> **這一節解決的疑問**：我該在哪條分支上工作？線上跑的是哪條？為什麼看起來有矛盾？
>
> ⛔ **本節只攤開事實與矛盾，⛔ 不下「應該怎麼做」的建議** ——
> 分支政策是**客戶頒布**的，可能另有本檔不知道的裁示。

### 4.1 三條線各是什麼

| 分支 | HEAD | 內容定位 |
|---|---|---|
| `origin/main` | `bcd46c7`（Merge PR #681） | **Streamlit Cloud 實際部署的線**。⚠️ 名義上是「v1」，但**實測已含 v2 的 code**（見 4.2 第 2 點） |
| `origin/v2` | `8f4a060`（2026-09-16，**純文件 commit**：「編入客戶 2026-09-16 分支政策」） | 客戶 2026-09-16 頒布分支政策時開的線。**vs `main`：ahead 14／behind 39** ⇒ **幾乎沒動過** |
| `claude/stock-dashboard-handoff-g9dtm0` | `10b6e5e` | **實際的開發線**（工作樹乾淨）。**vs `main`：ahead 91／behind 39** |

**PR #675**（量測日 2026-09-24）：`open`／**`draft`**／**base `v2`**／head 是上面那條開發線／
77 commits／90 changed files／`mergeable_state: clean`。

⚠️ **上表數字會漂移**，接手請現場重跑：
```
git fetch --all
git rev-list --left-right --count origin/main...HEAD
git rev-list --left-right --count origin/main...origin/v2
```

### 4.2 🔴 三者的矛盾（逐條攤開，⛔ 不下結論）

**以下四點同時為真：**

**1. 客戶 2026-09-16 的原文裁示**（`CLAUDE.md` §-1.2 逐字）：
> 「**新分支名 `v2`，從當前開發線 HEAD 開**」
> 「**`main` 保留 v1，不合併直到 v2 完成**」
> 「**v2 上線時直接合併 `main`**，Streamlit Cloud 自動重部署」

**2. 但實測 `main` 上已經有 v2 的 code。** `git ls-tree -r origin/main` 命中：
- `src/ui_v2/` **7 支 `.py` 全部在 `main`**
- `src/ui/views/page_{today,find,inspect,hold,why}.py` **五頁全部在 `main`**
- `shared/ia_nav.py` **在 `main`**

**它們是怎麼進去的**（`git log origin/main --diff-filter=A` 實測）：

| 進入物 | commit / PR | 日期 |
|---|---|---|
| `shared/ia_nav.py` | `50b6412`（PR #662） | **2026-09-05** |
| `src/ui/views/page_today.py` | `8f81e96`（PR #663） | **2026-09-07** |
| `src/ui/views/page_find.py` | `1e90d9d`（PR #664） | **2026-09-07** |
| `page_inspect.py` / `page_hold.py` / `page_why.py` | `340be68`（PR #665） | **2026-09-07** |
| `src/ui_v2/`（6 支 + `__init__`）與「今天」頁卡面 | `dbab9b1` / `0aaef3e` / `383c933`，經 PR **#678／#679／#680／#681** | **2026-09-23~24** |

⇒ **五頁與 `ia_nav` 是在 2026-09-16 分支政策頒布之前就進 `main` 的；
`src/ui_v2/` 則是在頒布之後（2026-09-24）才進 `main` 的。**

**3. 但實測 `main` 上幾乎沒有 v2 的文件。**
`origin/main` 的 `docs/v2/` **只有 2 個檔**（`spec/S1-6_COMPLIANCE_COPY_GUIDE.md` 與
`wireframe/wf_page_why.js`）—— **`docs/v2/prototype/`、`docs/v2/audit/`、`docs/v2/stage1/`
與 `docs/v2/README.md` 整個不在 `main`**。
根目錄同樣缺：`DEAD_CODE.md`／`MACRO_MASTER.md`／`STRATEGY_INTAKE.md`／
`HANDOFF.md`（本檔）／`HANDOFF_MARGIN_RELATIVE.md` **都不在 `main`**。
（`main` 根目錄只有 16 份 `.md`，開發線有 21 份。）

**4. 而實際開發沒有發生在 `v2` 上**，發生在 `claude/stock-dashboard-handoff-g9dtm0`；
**PR #675 的 base 卻指向 `v2`**（那條幾乎沒動過的線）。

> ⚠️ **本檔只陳述上述四點事實。⛔ 不判斷誰對誰錯、⛔ 不建議改 base、⛔ 不建議 merge。**
> ⚠️ **未查證**：是否有客戶在 2026-09-16 之後另外裁示放寬分支政策。
> 本組只查了 `CLAUDE.md` §-1.2 的文字，**沒有翻對話紀錄**（也無從翻）。

> 📌 **現行待辦以文件開頭『未完成項目』為準**（2026-09-26）；本段保留為歷史紀錄。

### 4.3 接手 AI 在分支上 ⛔ 不准自己決定的事

- ⛔ **不得自行 merge PR #675**、⛔ **不得轉 ready**、⛔ **不得改它的 base**。
- ⛔ **不得自行把開發線併進 `v2` 或 `main`**。
- ⛔ **不得因為「`main` 上已經有 v2 code」就推論「分支政策已作廢」。**

**理由**：`CLAUDE.md` §-1.5.D v3 §03-2 ② 把「**不可逆操作**」列為**必須請示客戶**的兩類之一；
merge 與改 base **直接影響線上部署**（`main` 一動，Streamlit Cloud 就重新部署）。

⚠️ **一個容易誤用的例外**：`CLAUDE.md` §-1.5.A-6 末項記載 `PROCESS.md §4` 有一條
「直接 merge PR」的**常設授權**。⛔ **不要拿它來合理化本節禁止的事** ——
那條授權涵蓋的是「一般 PR 走完流程後 merge 這個動作」，
⛔ **不涵蓋**「改 base」「把 draft 轉 ready」「在分支政策本身有矛盾時逕自選一邊」。
分支政策是客戶頒布的，⇒ 落在請示白名單。

### 4.4 需要時該怎麼問客戶（**格式範例**）

⚠️ `CLAUDE.md` §-1.5.D v3 §03-1 **嚴禁向客戶拋出選擇題**；§03-2 要求**必須附總管推薦方案與具體原因**。
⇒ ⛔ **不要問「要不要改 base？」**（那是純選擇題、且用了技術語言），而要用**業務語言 + 附推薦**，例如：

> 「目前新版 UI 的開發其實都在 `claude/…` 這條線上，你 9/16 開的 `v2` 那條幾乎沒動；
> 而線上實際跑的 `main`，已經有一部分新版程式了。
> **我建議把開發線直接併進 `main`（理由：那才是線上部署的線，`v2` 已經沒有承載開發）。**
> 你要維持原本『v2 完成才併 main』的規劃，還是改成這樣？」

⚠️ **上面那句「我建議」只是格式範例，⛔ 不是本檔的建議。**
接手 AI 必須**自己先查證、自己形成推薦**，再照這個格式問。

### 4.5 其他分支（一行帶過）

`origin/feat/v2-card-live`／`feat/v2-card-template`／`feat/v2-fullpage-cards`／`feat/v2-verdict-cards`／
`test/ui-v2-guards`／`wireframe/stock-ia-5pages`／`origin/data`／`origin/claude/my-stock-dashboard-ui-rewrite-r40gjc`。
⚠️ **未查證各自是否已合併、是否可刪。**

⚠️ **另一個實測到的小矛盾**：`.github/workflows/pr-check.yml` 的觸發分支寫
`branches: [main, v2, ui-v2]`，但 **`origin/ui-v2` 這條分支已不存在**
（`git rev-parse --verify origin/ui-v2` → `fatal: Needed a single revision`）。
⇒ 設定檔裡留著一條指向不存在分支的觸發規則。**⛔ 本檔只登記，不建議動它**（§-1：沒指派不動工）。

---

## 5. 環境與工具的坑

> **這一節解決的疑問**：這個容器裡什麼能用、什麼不能用、跑測試怎麼跑、什麼東西 CI 綠了也不算數？

| 坑 | 實測（量測日 2026-09-24） | 怎麼做 |
|---|---|---|
| **沒有 `gh` CLI** | `which gh` → 不存在 | 用 `mcp__github__*` MCP 工具，或直接打 GitHub REST API |
| **跑測試** | `pytest.ini` 逐字：`testpaths = tests`、`addopts = --strict-markers -m "not slow"` | `pytest` ＝ **fast lane**（預設排除 slow）；`pytest -m slow` ＝ **AppTest lane** |
| **CI 兩條 lane** | `.github/workflows/pr-check.yml`：`fast-checks` 跑 `pytest -v`（**失敗即阻擋 merge**）／`slow-tests` 跑 `pytest -v -m slow --tb=short`，且 **`continue-on-error: true`** | ⚠️ **slow lane 紅了不會擋 merge，也不會在 PR 上顯眼** ⇒ **要自己去看 job log** |
| ⭐ **原型：CI 綠不算數** | `CLAUDE.md` §8.2.A.5 客戶**逐字頒布**：「`docs/v2/prototype/` 的守衛只在手動執行時跑。CI 只跑 `tests/`。**改任何一份原型前，必須手動執行產生器，不能只看 CI 綠。**」<br>⚠️ **機制原因（即使 CI 現在真的會跑產生器，這條仍然成立）**：`tests/ui_v2/test_prototype_generator.py` 把產生器的輸出 **重導到 `tmp_path`** ⇒ 它**永遠不證明「入庫的 `today_v2.html` 與現行 `src/ui_v2/` 同源」**。真實案例：commit `57fc464`（2026-09-24）「重產 `today_v2.html` —— 修 provenance 檔頭對不上造成的 drift 紅燈」 | 改 `docs/v2/prototype/` 任何檔之後，跑：<br>`python docs/v2/prototype/gen_today_v2.py`<br>（就地覆寫 `today_v2.html`，尾端會印自驗摘要） |
| **沙箱驗不到的東西** | Streamlit Cloud 線上行為／NAS webhook／12 支 cron workflow 的實跑；`docs/` 整棵樹 **pytest 從不收集**（`testpaths = tests`） | `CLAUDE.md` §-1.5.A-7 要求「**無法沙箱驗的限制要誠實標明**」 ⇒ 交付時要寫出來，⛔ 不得吞掉 |
| **缺件（本容器）** | **無 `FINMIND_TOKEN` / `FINMIND_API_TOKEN`** 環境變數；**無 `.streamlit/secrets.toml`**；**無 FinMind SDK**（`import FinMind` → `ModuleNotFoundError`） | raw HTTP 仍可用，但需要 token 的路徑一律走不通 ⇒ 見 **§6 卡關點** |

⚠️ **一個量測值漂移的實例（拿來當「為什麼不寫死數字」的活教材）**：
`CLAUDE.md` §8.2.A.5 記載 `docs/v2/prototype/gen_today_v2.py` 有「**183 道 `assert`**」（量測日 2026-09-22）。
本組實測（2026-09-24）為 **194 道**。
⇒ **⛔ 不要引用憲法裡的這個數字**；需要時**現場跑 `grep -c "assert " docs/v2/prototype/gen_today_v2.py`**。
（憲法該節自己也寫明「本條的效力 ⛔ 不依賴這兩個數字」。）

---

## 6. 支線：融資餘額燈「相對分位」

> **這一節解決的疑問**：上一輪在做什麼？卡在哪？客戶還欠我一個什麼決定？
>
> ⚠️ **這是一條支線，⛔ 不是主線。** 主線是 §3 的 v2 UI 重寫。
> 完整細節見 `HANDOFF_MARGIN_RELATIVE.md`（112 行）。

### 6.1 客戶要解的問題

客戶要的是「**趨勢**」，不是「**水位**」。

**實測**：`shared/macro_buckets.py` 全檔 `pct_change|rolling|quantile|.diff(|.shift(|ewm`
**命中數 ＝ 0**（量測日 2026-09-24）⇒ **28 盞燈（總經 16 ＋ 持股 12）全部只判水位。**

### 6.2 已寫好但沒接線的解法

`shared/relative_thresholds.py`（**448 行**）已寫好、`tests/test_relative_thresholds.py` **33 個測試綠**。
主要符號：`classify_by_pct_rank(series, *, window=756, yellow=0.75, red=0.90, high_bad=True, min_periods=None)`、
`margin_leverage_ratio(margin_yi, market_cap_yi)`、`vol_normalized_bias`、`foreign_futures_share`。

⚠️ **前一版交接說「0 production caller」—— 本組實測發現這句話不精確，在此更正**：

| 符號 | production caller（排除 `tests/`） |
|---|---|
| `classify_by_pct_rank` | **0**（`shared/macro_buckets.py` 只在**註解**裡提到它） |
| `margin_leverage_ratio` | **0**（同上，只在註解） |
| `vol_normalized_bias` | **0** |
| `foreign_futures_share` | **0** |
| **`DEFAULT_BIAS_MA_LEN`** | ⚠️ **有 1 個** —— `src/data/macro/macro_cache_reader.py` 真的 `from shared.relative_thresholds import DEFAULT_BIAS_MA_LEN` 並實際使用 |

⇒ **正確說法：四個分類函式 0 production caller；但整個模組**不是**孤兒（有一個常數被真的用到）。**
⛔ 刪它之前務必看清楚這個差別（並先查 `DEAD_CODE.md`）。

`macro_buckets` 自陳逐字：「絕對門檻已被市值成長淹沒，實測 5,148 億早已穿透兩線 →
**燈號恆紅、鑑別力歸零**。相對化方案見 `shared/relative_thresholds`（**尚未接線，屬行為變更需另案**）。」

### 6.3 🔴 但預覽證明「相對分位」救不了

2026 年 122 個有結論日，**絕對門檻組與相對分位組都是 122/122 恆紅、0 轉態**。

**原因**：融資餘額 2026 **單邊創新高**（3,509.5 → 5,878.7 億），
而**單調上升序列的滾動分位恆等於 1.0**
（實測 2026 pct_rank 中位數 **0.9954**、**40/122 天 ＝ 1.0**、**122/122 天 ≥ 0.90 紅線**）。

⇒ `relative_thresholds.py` docstring 宣稱的「改成相對分位才有鑑別力」，
**在本 repo 實測資料上不成立**。唯一真實增益是 **B 組比 A 組早約一個月轉紅**
（2025-11-28 vs 2025-12-30）＝ **靈敏度差異，不是鑑別力**。

⚠️ 預覽腳本與圖**只存在於前一個 session 的 sandbox，未進 repo，已隨容器消失**。
要重現請依上述參數自行重跑。

### 6.4 🔴 順帶查出的資料污染

> 📌 **現行待辦以文件開頭『未完成項目』為準**（2026-09-26）；本段保留為歷史紀錄。

`data_cache/finmind_margin.parquet`（4,957 列）**單位混用**：

| 列數 | 量級 | 口徑 | sanity `[500, 10000]` 億 |
|---|---|---|---|
| **1,982** | 1e11~1e12 | **元**（`MarginPurchaseMoney`） | 通過 |
| **2,975** | 1e5~1e7 | **張數**（`MarginPurchaseVolume`） | — |

**逐日交錯混在整段歷史。** `source` 欄：4,930 列舊 buggy 路徑、27 列修好的路徑。
⚠️ **任何吃這份 parquet 的分析結論都不可信。**

**🔴 但 cron 的 code 已經修好了** —— `scripts/update_macro_history.py::fetch_finmind_margin`
**實測已 import 並呼叫** `shared/margin_schema.py` 的 `extract_margin_money_series` 與
`margin_twd_sanity_mask`；守衛 `tests/test_b3_margin_schema.py`。
修復後寫入的 27 列（`2026-08-06` → `2026-09-11`）**全部乾淨**。
⇒ **髒的是 2026-08-07 之前舊 code 留下的歷史積欠，⛔ 不是現在的程式。**

**另一份：`data_cache/finmind_m1m2.parquet` 損壞**（量測日 2026-09-24，`origin/main` `a59ff63`，**登記，未修**）：

| 項目 | 實測 |
|---|---|
| M1B／M2 出現**負值** | 例：`2026-06-01` `m1b=-125145`、`m2=-11301` |
| `m1b_m2_gap` 範圍 | 約 **-13,976 ～ +7,721**（對照該燈門檻帶：黃 ≤1.00／紅 ≤0.00） |
| 最後一列 | `2026-07-01` |

⚠️ 本分支（`claude/stock-dashboard-handoff-g9dtm0`）的同一檔**與 `main` 不同**（240 列 vs 238 列；
`2026-06-01` 為 `m1b=-119620`、`m2=-4349`；gap 上限約 +36,034）—— **兩邊都壞**，只是壞法不同。
**後果**：v2「🚦 今天」燈卡的「變化方向」列，**M1B-M2 固定顯示「無資料」**，程式刻意不讀此檔
（`shared/lamp_direction_thresholds.py` 檔頭）。**未修**（§-1：無客戶指派；且修法同 §6.5 需重抓歷史）。

> 📌 **現行待辦以文件開頭『未完成項目』為準**（2026-09-26）；本段保留為歷史紀錄。

**待辦：M1B-M2 燈「替代值未標明」**（**待辦，另開工單；客戶 2026-09-25 裁示**；**登記，未動工**）：

| 項目 | 內容 |
|---|---|
| 事實 | 線上 M1B-M2 現值走 `src/data/macro/macro_snapshot.py::fetch_m1b_m2_block` → `src/data/macro/tw_macro.py::fetch_cbc_m1b_m2`（CBC ms1.json → CPX EF15M01 → `^TWII` 代理）→ FRED → IMF |
| 問題 | 退到 `^TWII` 代理層時，卡片「現值」實為**加權指數動能推算**，但 `hit_source` 標籤仍是通用字串、`is_proxy_tier` 在 `fetch_m1b_m2_block` 重新打包時**被丟掉** ⇒ 使用者看不出是替代值（違 `CLAUDE.md` §1「任何填補必須在輸出帶旗標」精神） |
| 補充 | 卡片「缺值」文案（`shared/station_specs.py::MISS_TEXT[MISS_NO_INPUT]`，16 盞共用）經查證在**所有來源皆失敗時屬實**，客戶裁示**維持不改**；`docs/v2/prototype/lamp_preview.html` 中 M1B-M2 顯示的「沒抓到」為**預覽腳本自設狀態，非線上現象** |
| 處置 | 依 §-1：**只登記，未動工** |

⚠️ 上列事實為**程式閱讀，未實跑**；**單組結論，未經第二組驗**（§-2 規則 6），⛔ 不得當既定前提。

> 📌 **現行待辦以文件開頭『未完成項目』為準**（2026-09-26）；本段保留為歷史紀錄。

**~~待辦：~~ 已結案（#697 `f14c5fd`，2026-09-26）：今天頁燈卡「▸ 詳細」~~鍵盤／螢幕朗讀點不到~~ 鍵盤／螢幕朗讀 a11y**（**待補；客戶 2026-09-25 裁示：選 (b) 並接受此代價，登記待補**；~~**登記，未動工**~~ → **2026-09-26 客戶核准動工，#697 結案**）：

| 項目 | 內容 |
|---|---|
| 事實 | 今天頁燈卡「▸ 詳細」已由原生 `<details>` 改為樣式開關（checkbox＋label），~~改後鍵盤／螢幕朗讀點不到~~ |
| 📌 事實更正（2026-09-26；有意識的更正，⛔ 不是漏刪） | **「鍵盤點不到」不成立**：樣式開關自引入的 commit `6300672`（2026-09-25）起，input 就是**視覺隱藏、非 `display:none`**，可 Tab 聚焦、Space 切換，`:focus-visible` 已有 1px 點線焦點框（`src/ui_v2/markup.py::_fold_rules`；以 `git log -S` 核對）。當時真正的缺口在**朗讀與可見度**：① 16 個開關的朗讀名稱都只叫「▸ 詳細」、不帶卡片標題；② 無 `aria-controls`；③ 1px 點線焦點框在深色卡上幾乎看不見（②③ 依 #697 程式註解）。⇒ 被推翻的只有「鍵盤點不到」；朗讀面的擔心方向是對的，已由 #697 補上 |
| 背景 | 原生 `<details>` 在客戶 iPhone 上點不動（**真因未確認**，沙箱無 WebKit 可測），故改用樣式開關 |
| 補法方向 | （**僅登記、未驗**）input 保留可聚焦並加 `aria-expanded`／可見焦點樣式，或改回可存取元件 |
| 實際補法（#697） | `aria-labelledby`＝開關字＋卡標題 ⇒ 朗讀「▸ 詳細 〈卡標題〉」；`aria-controls` 指向內容區；焦點框改 2px 實線、`outline-offset:2px`（不壓「▸」）；⛔ **刻意不用 `aria-expanded`**（無 JS 無法隨勾選更新，寫死的值會對朗讀說謊，§1 —— 與上列「補法方向」不同，屬有意偏離）；5 頁 72 組截圖滑鼠／觸控逐像素一致。⚠️ **未在真 iPhone／VoiceOver 實測**（見文件開頭 D1） |
| 處置 | ~~依 §-1：**只登記，未動工**~~ → 2026-09-26 客戶核准動工，#697 `f14c5fd` 結案 |

> 📌 **現行待辦以文件開頭『未完成項目』為準**（2026-09-26）；本段保留為歷史紀錄。

**待辦：K1 在燈卡上復發 —— 「門檻出處」「命中來源」露出內部識別字**（**客戶 2026-09-25 裁示：K1 由「不修」升級為「需規格補 16 盞對照表」**；**登記，未動工**）：

| 項目 | 內容 |
|---|---|
| 事實 | K1 原登記於 `docs/v2/prototype/gen_today_v2.py::COPY_SPEC_GAPS`（鍵 `"K1"`），並渲染進 `docs/v2/prototype/today_v2.html`：「🔴 卡面上有內部函式名／模組名／enum 名，五頁全中 —— ⛔ 本輪不修，因為修它必須發明規格沒給的中文標籤」。2026-09-25 稽核 `origin/main` `8873c9e` 查出：「🚦 今天」→「指標明細」**16 盞燈卡**的「▸ 詳細」內（#685／#686 起），「**門檻出處**」直出 `shared/macro_buckets.py::BUCKET_DANGER_SPECS` 的 `source`（例 `SSOT:HEALTH_DEFENSE_THRESHOLD(35)+DESIGN(50)`、`SSOT:MACRO_THRESHOLDS.VIX`），「**命中來源**」直出 `src/compute/macro/macro_helpers.py::compute_five_bucket_summary` 經 `_traced` 產生的 `hit_source` 標籤（例 `macro_info.vix.current (Yahoo ^VIX → FRED VIXCLS)`）⇒ **K1 在燈卡上復發** |
| 客戶裁示 | K1 由「不修」升級為「**需規格補 16 盞對照表**」：規格須逐盞提供「門檻出處」與「命中來源」的**使用者白話文案**；⛔ **AI 不得自行發明文案**（＝捏造，違 `CLAUDE.md` §1） |
| 卡在哪 | **規格（16 盞對照表）尚未提供** |
| 優先序 | 客戶定序：**四頁卡化 ＞ 今天頁 7 塊未接線 ＞ K1** |
| 處置 | **本輪未修**；只登記，待規格到位後再動工 |

⚠️ 上列稽核為**單組、唯讀**結論，**未經第二組驗**（§-2 規則 6），⛔ 不得當既定前提。

> 📌 **現行待辦以文件開頭『未完成項目』為準**（2026-09-26）；本段保留為歷史紀錄。

**~~待辦：~~ 規格變更（⛔ 不是 bug fix）：標記矛盾：空白卡寫『這是一個有效的結果』卻顯示 #7『缺漏·可重跑』**（**客戶 2026-09-26 裁示：合併為一輪、另開工單，兩頁共用對照一起修；⛔ 不得併入持股頁卡化那一輪**；~~**登記，未動工**~~ → **2026-09-26 同日以規格變更處理（新增徽章 #11，見本條末「處理結果」表）—— ⚠️ 只處理了一部分，見下**）：

| 項目 | 內容 |
|---|---|
| 受影響卡 | **持股頁（PR #688，分支 `claude/v2-hold-cards` `57b5993`）**：`src/ui/views/page_hold.py` 的 `hold.switch`／`hold.macro_stage`／`hold.take_profit` 空白態（`else:   # UI_EMPTY`，`why` 寫「**這是一個有效的結果**」）。**找股頁**：`src/ui/views/page_find.py` 的 `find.screen_result` 空白態（`SCREEN_EMPTY_NOW`「選股已完成，符合條件的標的是 0 檔」，`why` 寫「這是一個有效的結果」）—— ~~既有「0 筆結果」徽章 #7 vs 文字「有效結果」（⚠️ 待確認：`src/` 內 grep 不到「0 筆結果」字面，該標籤字樣出處未查到）~~ → **更正（2026-09-26）**：「0 筆結果」是**轉述、不是畫面字面**；畫面上的真實文字是 `SCREEN_EMPTY_NOW`「**選股已完成，符合條件的標的是 0 檔**」（`src/ui/views/page_find.py`），徽章 #7 vs `why`「這是一個有效的結果」 |
| 真因 | 上列空白態的建構函式呼叫 `shared/ui_state.py::classify_ui_state()` **未帶 `reason`** ⇒ 判為 `UI_EMPTY`；共用對照 `src/ui/views/page_today.py::V2_STATE_VOCAB` 把 `UI_EMPTY` 翻成 `("empty", None)`；`src/ui_v2/page_today.py::resolve_badge()` 對 `empty` 且無 `MISS_NOT_APPLICABLE` ⇒ 回 **#7「缺漏 · 可重跑」**（`src/ui_v2/components.py`） |
| 徽章缺口 | 現有 10 顆徽章（`src/ui_v2/components.py` `_badge(1..10)`）**沒有一顆**表示「有效的空結果」；#8「不適用 · 重跑無效」語意也不對 |
| 既有揭露 | `page_today.py` 在 `V2_BADGE_AMBIGUOUS` 旁已註明：裸 `UI_EMPTY` 的徽章文字「比 L0 多講了一句話」（#7 宣稱可重跑），要改須先改 v2 契約層 |
| 修法方向 | 在**共用徽章集／`V2_STATE_VOCAB`** 層決定（⛔ 不在單頁另發明徽章）；屬**共用元件異動 ⇒ 動工前須客戶核准** |
| 附記 | 持股頁卡化那一輪的**手機截圖上傳失敗**（檔案過大／過長，伺服器回 400）；客戶表示**不阻擋任何事** |
| 處置 | ~~依 §-1：**只登記，未動工**~~ → 2026-09-26 客戶裁示動工，走**規格變更**（見下表） |

⚠️ 上列事實為**程式閱讀（grep `/home/user/msd-hold` 的 `src/`、`shared/`），未實跑**；**單組結論，未經第二組驗**（§-2 規則 6），⛔ 不得當既定前提。

**處理結果（2026-09-26；性質＝規格變更，⛔ 不是 bug fix；決策者：客戶）**：

| 項目 | 內容 |
|---|---|
| 規格變更 | `docs/v2/spec/UI_COMPONENTS.md §2` 徽章 ~~恰 10 種~~ → **11 種**：新增 **#11「▨ 無資料」**＝有效的空結果；圖示／文字**逐字沿用** L0 `shared/ui_state.py` `UI_STATE_META[UI_EMPTY]`（實作直接讀那一格，⛔ 不抄）。舊表述保留加刪除線，理由兩邊並陳於該段 |
| 射程 | **登記制**：`src/ui/views/page_today.py::V2_VALID_EMPTY_SPEC`，只列「上游成功算完、結果真的是 0／空」且**同一對 `(key, now)` 不會出現在任何缺漏／失敗路徑**的卡；L0 態須恰為 `UI_EMPTY`。其餘一律維持原徽章 |
| ✅ 納入（1） | `hold.portfolio_count` ＋ `COUNT_EMPTY_NOW`：Sheet 讀成功、`list_portfolios()` 長度 0（L3 `STATUS_BOUND_EMPTY`）；讀取失敗走 `None`＋`MISS_FETCH_FAILED`（紅）、未綁走 idle，兩者都不會產出這一態 |
| ⛔ 未納入：本條點名的四張卡 | **`find.screen_result`**：`_load_survivors()` 讀取失敗時 L3 回空表＋「季快照未就緒」，畫面同樣落到 `SCREEN_EMPTY_NOW` ⇒ 同一對 `(key, now)` 蓋著真缺漏。**`hold.switch`**：L3 `get_switch_in_candidates()` 讀選股池失敗時**吞例外回 `[]`**，換出端判不出來的燈也不會變紅 ⇒ 「沒有建議換股」可能來自失敗。**`hold.take_profit`**：L3 只判有損益% 的衛星，**全部缺均價時也回 0 檔**（`why` 自陳「也可能是…判不了」）。**`hold.macro_stage`**：「總經本輪未評估」＝未評估，客戶明文排除 |
| ⛔ 未納入：其他候選 | `hold.deep.dividend_cash`「近一年查不到任何一筆配息」（L3 自陳上游把「真的沒除息」與「抓不到配息」回成同一個空序列）；`hold.position_cap`（未評估）；`hold.deep.stress`／`var`／`dividend_cash` 的「算不出來」、`hold.alloc_split`／`deep.core_satellite`「算不出比例」（缺張數／均價＝真缺漏）；`hold.ai_summary`「AI 回了空白」（異常）；`NOT_BOUND_*`／`EMPTY_SHEET_*`／「這一輪沒有讀 Google Sheet」／`NO_ROWS_NOW`（漂移）／`hold.vix`（稍後再試）／`find.sector_flow`（快取未產生）；今天頁全部 |
| ⚠️ 原矛盾仍在 | 上列四張點名卡**仍畫 #7**，卡面仍寫「這是一個有效的結果」⇒ **矛盾對它們還沒解**。要讓它們畫 #11，須先在 builder／loader 把「真的是 0」與「失敗被吞成空」分成不同的 `now`（或讓 L3 不吞例外）—— **屬改卡面文案／builder／L3，不在本次授權**（客戶授權範圍＝共用對照表＋規格檔＋對應測試），**待客戶另行裁示** |
| 程式 | 分支 `claude/v2-badge-vocab`（基於 `66e4fe0`，未 commit）：`src/ui_v2/components.py`（#11）、`src/ui_v2/page_today.py`（`resolve_badge(valid_empty=)`，非 `empty` 態拒收）、`src/ui/views/page_today.py`（登記表＋三頁共用 `v2_card_badge_n()`）、`page_find.py`／`page_hold.py` 各改一個呼叫點＋import、`shared/ui_state.py`（僅註解）、測試 |

⚠️ 納入／排除判定為**單組程式閱讀＋列舉實跑**的結論，**未經第二組驗**（§-2 規則 6），⛔ 不得當既定前提。

> 📌 **現行待辦以文件開頭『未完成項目』為準**（2026-09-26）；本段保留為歷史紀錄。

**待辦：4 張卡「靜默失敗」—— 讓「抓取失敗」與「真的是 0」分開，才能畫 #11**（**客戶 2026-09-26 裁示：分兩批工單**；~~**登記，未動工**~~ → **2026-09-26 客戶裁示更新：第 1 批已動工，2/3 修好；第 2 批仍未動工**）：

| 項目 | 內容 |
|---|---|
| 背景 | 上條「處理結果」已新增 #11「▨ 無資料」，但點名的卡因**失敗被吞成空**而未納入 `V2_VALID_EMPTY_SPEC`。本條即其後續工單 |
| **第 1 批（3 張）** | `find.screen_result`（`SCREEN_EMPTY_NOW`）、`hold.switch`（`SWITCH_EMPTY_NOW`）、`hold.take_profit`（`TP_EMPTY_NOW`） |
| 第 1 批範圍 | **只改「抓取失敗 vs 真的 0」的判定**；⛔ **不動資料層** |
| 第 1 批證據 | ① `src/ui/views/page_find.py:836-838` 接住存活池例外、回 `None`；② `src/services/fundamental_screener_service.py:493-498` 再吞一次（`survivors_df = None`），之後 `:338-339` 回空表並附誤導說明「**季快照未就緒**」；③ `src/services/dividend_station_service.py:781-785`（`get_switch_in_candidates`）接住例外回 `[]`，且排名表為空時**也**回 `[]`；④ `flag_take_profit`（`dividend_station_service.py:944-952`，`return` 在 `:953`）略過 `_detail.error` 的列；⑤ 卡面文案寫「**這是一個有效的結果**」：`src/ui/views/page_hold.py:1981-1990`（`hold.switch`）、`:2161-2168`（`hold.take_profit`）、`src/ui/views/page_find.py:1393`（`find.screen_result` 的 `why`） |
| **第 2 批（1 張）** | `hold.deep.dividend_cash`（`CASH_NO_PAYOUT_NOW`） |
| **第 1 批結果（2026-09-26，客戶裁示）** | 分支 `claude/v2-silent-fail-b1`，PR 目標 `main`。⚠️ 待確認：本組核對時該分支**只在 `/home/user/msd-silent` 本地、改動未 commit**（`page_find.py`／`page_hold.py`／兩支既有測試＋新檔 `tests/test_v2_silent_fail_b1.py`），`git ls-remote origin` **查無此分支** ⇒ PR 尚未開、行號以該工作區為準 |
| 第 1 批 ✅ `find.screen_result` | **已修**：存活池失敗時卡轉**紅**「**選股中止**」（`SCREEN_ABORTED_NOW`，`page_find.py:610`），卡面點名「**L3 基本面存活池…拋出例外**」（`page_find.py:498`；測試 `test_v2_silent_fail_b1.py:89`） |
| 第 1 批 ✅ `hold.take_profit` | **已修**：held 個股列帶 `_detail.error` 時卡轉**紅**「**停利判不出來**」（`TP_FAILED_NOW`，`page_hold.py:1530`；判定條件 `:2142-2148` 與 L3 `flag_take_profit` 跳過條件 `dividend_station_service.py:946` 逐字對齊） |
| 第 1 批 ⛔ `hold.switch` | **未修**：頁面**沒有任何訊號**分得出「抓取失敗」與「真的空」。須改 **L3** `src/services/dividend_station_service.py:781-785`（`get_switch_in_candidates`：`:781` 接住例外、`:783` 回 `[]`；`:785` 排名表空時**也**回 `[]`，且丟掉 `_note`）—— 行號已於 `msd-silent` 與 `origin/main` 兩邊 grep 核對一致。超出第 1 批「只改頁面」範圍 ⇒ **⏸ 待客戶授權改 L3** |
| QA 殘留 (a)（**僅登記**，既有、不在本批） | `find`：**唯一勾選的因子自己的輸入失敗**時（例：只勾估值且 PE 表失敗；或只勾缺貨／RS／跨季且該掃描失敗），卡顯示 0 檔＋灰色「**有效結果**」。頁面**已有** `aux_errors`（`page_find.py:803`；「不轉紅」設計見 `:220`）⇒ **可在頁面修**。⚠️ 現有測試 `tests/test_v2_silent_fail_b1.py:132` `test_b_other_aux_failures_still_leave_a_valid_zero` **把這個灰色結果鎖住**，修時須一併改。⚠️ 待確認：「唯一因子」情境為 QA 推論，本組只核對到 `aux_errors` 與該測試存在，**未實跑** |
| QA 殘留 (b)（**僅登記**，既有、不在本批） | `hold.take_profit`：held 個股列**沒有** `_detail.error` 但 `current_price` 為 `None` ⇒ `損益%` 為 `None`（`dividend_station_service.py:442-443`，須 `_avg and _cur` 皆有值）⇒ L3 略過，卡仍寫「**這是一個有效的結果**」；`why` 只怪「沒有均價」（`page_hold.py:2188-2192`），沒提現價缺失。⚠️ 待確認：未實跑 |
| 第 2 批證據 | `src/data/etf/etf_fetch.py::fetch_etf_dividends` `:293-296` 接住**所有**例外回空 `Series` ⇒ 「真的沒配息」與「抓不到」同形 |
| 第 2 批閘門 | **需改資料層** ⇒ ⛔ **動工前須先向客戶報告計畫**（資料層凍結，`CLAUDE.md` §-1.2）。**2026-09-26 客戶裁示：不變**，仍須先報告計畫、未動工 |
| 收尾 | 第 1、2 批修好後，對應 `(key, now)` 才可登記進 `src/ui/views/page_today.py::V2_VALID_EMPTY_SPEC`（`:2207`）取得 #11 |
| 僅登記、不排程 ① | `load_binding` 契約漂移落空（`src/ui/views/page_hold.py:1003-1018`）：若 L3 漂移，卡會落進 `UI_EMPTY`，#11 就會宣稱「有效的結果」。**現行 L3 不會產出此態** |
| 僅登記、不排程 ② | 註解寫 `V2_VALID_EMPTY_PAIRS`，實際符號是 `V2_VALID_EMPTY_SPEC`：`src/ui_v2/page_today.py:533`、`src/ui_v2/components.py:212` |
| 處置 | 依 §-1：~~**登記，未動工**~~ → **2026-09-26（客戶裁示）**：第 1 批已動工（2/3 修好，`hold.switch` 待 L3 授權）；QA 殘留 (a)(b) 與「僅登記 ①②」**登記、不動工**；第 2 批未動工 |

⚠️ 行號以 `origin/main` `66e4fe0` ＋ PR #689（`claude/v2-badge-vocab` `78d8744`）為準，已於 `/home/user/msd-badge` 逐一 grep 核對命中；⚠️ 待確認：「僅登記 ①」所述「L3 漂移時會落進 `UI_EMPTY`」與「現行 L3 不會產出」為 QA 推論，本組**只核對到行號與程式片段，未實跑驗證該路徑**。
⚠️ 上列發現來自**單組 QA、程式閱讀、未實跑**；**未經第二組驗**（§-2 規則 6），⛔ 不得當既定前提。
⚠️ **2026-09-26 新增列**（第 1 批結果、QA 殘留 (a)(b)）同樣來自**單組 QA**，**未經第二組驗**；行號已於 `/home/user/msd-silent`（未 commit 工作區）與 `origin/main` grep 核對，`dividend_station_service.py:781-785` 兩邊一致；`page_find.py`／`page_hold.py`／新測試檔行號**僅存在於未 commit 的工作區**，合併後可能漂移。

### 6.5 🔴 卡關點與待客戶裁示

> 📌 **現行待辦以文件開頭『未完成項目』為準**（2026-09-26）；本段保留為歷史紀錄。

**重抓歷史需要 FinMind token，本容器沒有**（見 §5「缺件」）。

客戶尚未回答的二選一：

| 選項 | 內容 | 性質 |
|---|---|---|
| **(A)** | 客戶提供 token → 用已修好的 cron 重抓歷史，真正修好 | 前一位總管的推薦 |
| **(B)** | 清掉不合 sanity 的 2,975 列 → 留 1,982 列乾淨資料 | ⚠️ **那 60% 歷史無法從程式重建**，且 parquet 受 git 追蹤 ⇒ 屬**不可逆刪資料**，落在 v3 §03-2 ② **必須客戶拍板** |

⛔ **沒有第三條路**：張數無法換算成金額（要靠當日價格，等於捏造，**違 §1 Fail Loud**）。

**若客戶要繼續做「趨勢燈」，三個後續方向**（皆未驗證，僅登記）：
(a′) 換分母（`margin_leverage_ratio` + 找總市值資料源 —— ⚠️ **本地無上市總市值資料源**，
`data_cache/` 只有 margin／inst／m1m2／pmi；TWII 是指數點位、經除權息調整、不含股本成長，
**拿來當分母＝捏造**）／(b) 改判**變化率／動能**而非水位分位／(c) **先修 §6.4 的資料污染**
（因為 (a′)(b) 都吃同一份 parquet）。⚠️ 前一位總管推薦 **(c) 優先**，該推薦**未經第二組驗**。

---

## 7. 客戶的工作模式

> **這一節解決的疑問**：客戶怎麼下指令？我該怎麼回？回多長？

| 項目 | 規則 |
|---|---|
| **指令形式** | 每輪發一張 **【本輪：…】工單**，含**範圍**、**⛔ 約束**、**回報格式** |
| **邊界紀律** | ⭐ **嚴格照工單邊界做，超出即停手回報。** 工單寫「只動 X」就是只動 X |
| **語言** | 回覆用**繁體中文** |
| **篇幅** | 每輪 ≤ **15 行**、**表格優先**、結尾**必加**（二選一，互斥、不得都不加）：<br>`⏸ 等待你回覆：【明確問題】` 或 `✅ 本輪完成，無需回覆。` |
| **例外** | 客戶**指名要求**的問答／查證／原理說明／計算式 **不受 15 行拘束**，客戶明示「**越詳細越好**」、含**完整數學式**（`CLAUDE.md` §-1.5.H H-2） |
| **揭露義務不因篇幅解除** | ⭐ 「不寫免責」禁的是**罐頭樣板**，⛔ **不是**禁具體揭露。真有未驗的承重宣稱 → **壓成一行塞進 15 行內，⛔ 不是刪掉**（§-1.5.H H-1） |
| **程式碼要求** | **防禦性設計**（API 延遲／空值處理）＋ **效能**（Pandas 向量化，避免逐列迴圈）；寫完跑 `CLAUDE.md` §6 自審清單 |
| **交付報告** | 三段式（v3 §04）：① 功能交付與架構摘要（**清理／刪除了哪些檔要逐檔列出**）② 品管試用與資料審計結果 ③ 成品操作指引 |

---

## 8. 誠實揭露（`CLAUDE.md` §-2 規則 6）

> **這一節解決的疑問**：本檔哪些話可以信、哪些話我必須自己重驗？

| # | 宣稱 | 誰驗的 | 強度 |
|---|---|---|---|
| 1 | §0 專案定位、7 個舊頁籤逐字、workflow 檔數（16／12 排程）、無 `README.md` | **總管親自實測**（讀 `app.py`、`ls .github/workflows/`、`grep -l "schedule:"`） | 🟢 實測事實 |
| 2 | §3.2 各頁卡面（`page_today` 20 處 `ui_v2` 引用／其餘四頁 0 處）、五頁**都**已用 `_ui_kit` | **總管親自實測**（逐檔 `grep -c`） | 🟢 實測事實 |
| 3 | §3.4 側欄 radio 的 key／標題／`index=0`／`st.stop()`／late-import | **總管親自實測**（讀 `app.py` 該區塊全文） | 🟢 實測事實 |
| 4 | **§4 全部分支數字**（三條線 HEAD、ahead/behind、PR #675 狀態、v2 code 進 `main` 的 commit 與日期、`main` 上缺哪些文件） | **總管親自實測**（`git rev-list`／`git ls-tree`／`git log --diff-filter=A`／GitHub API） | 🟢 實測事實 |
| 5 | §5 無 `gh`、`pytest.ini` 內容、兩條 lane 的 `continue-on-error`、無 token／無 secrets／無 FinMind SDK、194 道 assert | **總管親自實測** | 🟢 實測事實 |
| 6 | §6 全部數字（`macro_buckets` 命中 0、448 行、33 測試、parquet 1,982／2,975、cron 已接 schema、2026 分位分布） | **前一位總管親自實測**，本組**複驗了其中可就地驗的部分**（命中數、行數、測試數、cron import） | 🟢 實測事實 |
| 7 | §6.2「`DEFAULT_BIAS_MA_LEN` 有 production caller」＝ **更正前一版交接的「0 production caller」** | **本組實測**（逐符號 `grep`） | 🟢 實測事實（**且推翻了舊敘述**） |
| 8 | §3.3「`src/ui_v2/` 現在有 production caller」＝ **更正 PR #675 描述（寫於 2026-09-23）的「0 production caller」** | **本組實測** | 🟢 實測事實（**且推翻了舊敘述**） |
| 9 | **§2 文件地圖的逐份「定性」**（哪份該讀、哪份過期、哪份是歷史） | **單組盤點**（讀各檔檔頭 + 行數） | ⚠️ **未經第二組驗** —— 定性是**判斷**，不是事實 |
| 10 | **§3.3 `src/ui_v2/` 各檔職責** | **單組**（讀檔頭與 `page_today.py` 的註解轉述） | ⚠️ **未經第二組驗** |
| 11 | **`docs/v2/` 各子目錄檔數**（spec 28／audit 18／wireframe 18／stage1 4／prototype 5+`__pycache__`） | **單組** `ls <dir> \| wc -l` | ⚠️ 數字是實測，但**分類定性**（「audit 是軌跡不是規格」）未經第二組驗 |
| 12 | **「`main` 上有 `src/ui_v2/` 是否另有客戶裁示」** | **完全未查證** | 🔴 **未知** —— §4.2 只陳述矛盾，⛔ 不得推論 |
| 13 | §2 的 `N-1`~`N-3`、§6.5 的 A/B/C 可得性分級 | **原產出組的單組結論**，本檔僅**轉錄** | ⚠️ **未經第二組驗**，⛔ 不得當既定前提 |
| 14 | §4.5「其他分支是否已合併／可刪」 | **未查證** | 🔴 **未知** |

### ⛔ 最後一句（最重要）

**⛔ 不得把本檔任何全稱句（「只有…」「全部…」「沒有其他地方…」）當成既定前提去做下一步決定。**
`CLAUDE.md` §-1.5.C 記載了一個真實前例：一句「牴觸只有這四處」的單組全稱句，
後來被獨立稽核組**另查出三處**而遭否證。**請據此打折信任本檔。**

**接手第一件事，請自己重跑一次 §4.1 的三行 `git` 指令** —— 那是本檔最會漂移、
也最影響你第一步該做什麼的一組數字。
