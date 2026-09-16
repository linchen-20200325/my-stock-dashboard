# 合規掃描甲組 — 禁用語窮舉稽核報告

- **掃描日**：2026-09-14
- **repo**：`/home/user/my-stock-dashboard`（HEAD 未動；本次**唯讀**，repo 零檔案修改、零 git 寫入）
- **範圍**：`app.py` + `src/**/*.py`，**排除 `tests/`**（依派工規格）
- **方法**：`grep -rn` 全量命中 → 再用 Python `tokenize` 逐 token 判定每個命中落在
  `COMMENT` / `DOCSTRING` / `STRING` 哪一類（不靠肉眼判斷「這行是不是註解」）→
  對每個 `STRING` 再人工追渲染路徑（誰呼叫、有沒有進 `st.*`）。
  腳本：`scratchpad/classify.py`；原始輸出：`scratchpad/main_classified.txt`、`scratchpad/sus_classified.txt`。

## ⚠️ 效力聲明（CLAUDE.md §-2 規則 6）

**本報告全部結論由甲組單組產出，未經第二組獨立複驗。**
下列句子一律只能當**待驗事項**，不得作為後續動作的前提，也不得寫進 commit message／PR 描述當成已完成的事實：

- 「主清單只有這 10 處要改」——**單組窮舉**。
- 「【E】死碼那兩處沒有 production caller」——**單組窮舉**（證據附於該節，請照證據自行複核）。
- 「沒有任何測試釘住我標【A】的那些字串」——**單組 grep**。

另：**搜尋是純字串比對**，用同義表述而不含這六個字的違規句（例：「值得分批佈局」「強烈買進」）
**結構上掃不到**，見文末「我沒查到的 / 不確定的」。

---

## 命中總量（實測）

| 詞 | 命中（word-occurrence） |
|---|---|
| `建議買進` | 2 |
| `立即出清` | **0** |
| `應該加碼` | **0** |
| `推薦` | 5 |
| `必漲` | 3 |
| `目標價` | 34 |
| **合計** | **44**（分布在 **42** 個相異 `file:line`；有 2 行同時含 `必漲`+`目標價`） |

token 分類：`STRING` 19 / `DOCSTRING` 12 / `COMMENT` 13。
19 個 `STRING` 中 → **【A】10 個**、【C】6 個、【E】2 個、另 1 個為 prompt 內描述性用語（歸【C】）。

---

# 一、【A】使用者可見字串 —— 主清單（這是要拿去動手改的）

> 全部 10 筆。**8 筆是同一個功能名「型態目標價」的 8 個出現點** ——
> ⚠️ **必須同一批一起改**，否則 `tab_edu.py:779` 的「在系統哪裡看：…的「型態目標價」區塊」
> 這條指路句會指向一個已經不存在的標題（該檔自己就在警告使用者「找不到不是你的問題」）。
> 另有 **1 筆同名字串在 `shared/`（超出本次指定範圍但確實上畫面）**，見 §一之補。

| # | file:line | 實際字串原文 | 管道 | 畫面位置 | v1/v2 | 中性替代建議 |
|---|---|---|---|---|---|---|
| **A1** | `src/ui/tabs/tab_stock.py:243` | `with st.expander('🎯 型態目標價（本檔 K 線自動算：甜蜜價·止損·目標）', expanded=False):` | `st.expander` label | 🔬 選股 → 🔬 個股 → 摺疊區塊標題 | **v1**（`src/ui/tabs/**`） | `'📐 型態等幅價位（本檔 K 線自動算：參考進場帶·止損·等幅價位）'`<br>理由：`等幅` 是這支引擎真正在做的事（等幅滿足量測，`pattern_targets.compute_pattern_targets`），`價位`＝中性名詞，不含「你應該賣在這」的指示性。順手把 `甜蜜價` 也換成 `參考進場帶`（見疑似區 S-甜蜜價）。emoji 🎯（靶心＝命中目標）換 📐（量尺）避免暗示「打到這個價」 |
| **A2** | `src/ui/tabs/tab_stock_grp.py:53` | `'輸入多檔代碼（逗號/空格/換行，最多10檔）— 型態目標價 / 財報體質 / 三階段濾網全部吃這一組',` | `st.text_area(label=...)` | 🔬 選股 → 📊 多檔個股比較 → ② 輸入框 label | **v1** | 同 A1 改名 → `…— 型態等幅價位 / 財報體質 / 三階段濾網全部吃這一組` |
| **A3** | `src/ui/tabs/tab_stock_grp.py:64` | `'組合體檢 vs 基準 + 排行總表 + 型態目標價 + 財報趨勢×轉機 + 三階段濾網')` | `st.caption` | 🔬 選股 → 📊 多檔個股比較 → 輸入框下方說明 | **v1** | `…+ 型態等幅價位 + …` |
| **A4** | `src/ui/tabs/stock_grp_sections/section_portfolio_summary.py:524` | `st.markdown('#### 🎯 型態目標價（全組合）')` | `st.markdown` H4 標題 | 🔬 選股 → 📊 多檔個股比較 → 「🎯 型態目標價（全組合）」批次表標題 | **v1** | `'#### 📐 型態等幅價位（全組合）'` |
| **A5** | `src/ui/tabs/stock_grp_sections/section_portfolio_summary.py:148` | `\| **型態／風報比** \| K 線型態學等幅滿足的目標與風報比(完整見「🎯 型態目標價」) \|` | `st.markdown`（`🔰 這頁怎麼看` expander 內的 markdown 表格） | 同上頁 → 「🔰 這頁怎麼看?」摺疊說明 | **v1** | `…(完整見「📐 型態等幅價位」)`。**必須與 A4 用同一個新名**，這是交叉指路 |
| **A6** | `src/ui/tabs/pattern_targets_ui.py:126` | `f"🚀 **目標價(等幅滿足)**：第一波 **{_fnum(t1)}**"` | `st.markdown` | 🔬 個股 **與** 📊 多檔個股比較 **共用元件**（`render_pattern_targets_for_ticker`，兩處各自 `key_prefix`）→ 「📋 型態分析報告」下方那一行 | **v1** | `f"📐 **等幅滿足價位**：第一波 **{_fnum(t1)}**"`<br>理由：原文括號已自陳「等幅滿足」，直接把它升為主詞即可，語意零損失；同時去掉 🚀（暗示上漲） |
| **A7** | `src/ui/tabs/stock_sections/section_when_buy_sell.py:77` | `'<br>🎯 <b>目標價</b>：預計可以獲利的目標 \| 🛑 <b>停損</b>：跌到這裡要認賠出場'` | `st.markdown(..., unsafe_allow_html=True)` 說明卡 | 🔬 選股 → 🔬 個股 → 「🎯 什麼時候買？什麼時候賣？」區塊最上方藍框說明 | **v1** | `'<br>📐 <b>等幅價位</b>：型態等幅量測推得的參考價位 \| 🛑 <b>停損</b>：跌破此價位視為型態失效'`<br>⚠️ **同一個 HTML 字串的前兩行（:75/:76）另含「代表可以考慮買進」「要考慮賣出或減碼」**，屬疑似區（S-加碼/S-減碼），一起處理較省事 |
| **A8** | `src/ui/tabs/tab_edu.py:779` | `> 📍 **在系統哪裡看**：🔬 個股 / 🏆 個股組合 的「型態目標價」區塊` | `st.markdown` 教材 | 🔧 工具箱 → 📚 教學 → 「策略3 章節 1/3：型態學」expander | **v1** | 改成新名（**與 A1/A4 同名**）。這條是**指路句**，改名不同步＝使用者照著找不到 |
| **A9** | `src/ui/tabs/tab_edu.py:835` | `3. **目標價**：頸線 + 型態高度（等幅量測）` | `st.markdown` 教材 | 同上，「🔑 操作細節：頸線突破買點」段第 3 點 | **v1** | `3. **等幅量測價位**：頸線 + 型態高度`（括號內容已上提為主詞，原意不變） |
| **A10** | `src/ui/pages/api_diagnostic.py:144` | `st.success('✅ 沒有設定 proxy，所有外連走直連（這是 Streamlit Cloud 推薦設定）')` | `st.success` | 🔧 工具箱 → 🔎 資料診斷 → 「🔧 進階診斷（工程師用）」expander → 勾「載入進階診斷」checkbox → 「🚧 Proxy 配置診斷」 | **v1**（`src/ui/pages/**`，不在派工列的兩個 bucket 內，實際掛在舊 7 頁籤下） | `'…（這是 Streamlit Cloud 的標準組態）'`<br>理由：這裡的「推薦」講的是**部署組態**、與買賣無關，但母法是**無條件禁用詞**，故仍須換。用「標準組態」而非「預設組態」——「預設」是事實宣稱（可能不成立），「標準」保留原本「這是正常/建議狀態」的語意而不使用禁用詞。<br>⚠️ 這是本清單**唯一與投資建議無關**的一筆，改動風險最低 |

### §一之補：超出指定範圍、但**確實上畫面**的同名字串（`shared/`）

派工的掃描範圍是 `app.py` + `src/**/*.py`，`shared/` 不在內。但我另跑了一次確認，發現：

| file:line | 字串 | 渲染路徑（已逐段追過） | 影響 |
|---|---|---|---|
| `shared/scoring_regime_gate.py:137` | `"健康度／趨勢／357／出場訊號／型態目標價不吃 regime，全部照常顯示。"` | `ScoringRegimeDecision.notice()` → `section_batch_fetcher.py:355` `risk_alerts_t3.append(...)` → `section_portfolio_summary.py:184` `st.warning(alert)` | **是【A】等級**：出現在 📊 多檔個股比較 → 「⚠️ 風控警示」。**A1~A9 改名時若漏掉它，畫面上會同時存在新舊兩個功能名** |
| `shared/scoring_regime_gate.py:52` | 同段文字的 docstring 版 | 不上畫面 | 【B】，改不改都行（建議同步，免得後人改錯） |
| `shared/signal_thresholds.py:1078` | `"""ETF 折價深度買進區:≤ -2% → 🟢 建議買進(NAV 大幅折價)。` | **docstring**，非 UI 字串 | 【B】。但這句**記錄了一個實際存在的畫面語意**，而該畫面的實際字串是 `etf_tab_single.py:518` `'🟢 強烈買進時機'`（不含六大禁用詞，掃不到）—— 見文末盲點 2 |

---

# 二、【B】程式碼註解 / docstring（不上畫面）

> 共 **25 筆**（`COMMENT` 13 + `DOCSTRING` 12）。合規窗口只准改「使用者看得到的文字」，
> 這些**嚴格來說不必改**；但 §一的改名若動到，順手同步可避免文件與畫面漂移。

### B-1｜COMMENT（13）

| file:line | 詞 | 原文 |
|---|---|---|
| `app.py:1018` | 目標價 | `# v19.163 財報體檢轉機併進 🏆 個股組合 Tab(批次)、目標價區間內嵌 🔬 個股 + 🏆 組合;` |
| `src/compute/scoring/scoring_engine.py:102` | 推薦 | `return 0.0   # 無資料 → 0分，不混入推薦名單` |
| `src/compute/strategy/pattern_targets.py:347` | 目標價 | `# §1(2026-08 稽核):目標價 ≤ 進場(甜蜜)價 → 風報比 ≤ 0,對做多無意義,` |
| `src/compute/strategy/v4_strategy_engine.py:418` | 目標價 | `# [Task 5] VCP 三階段波動收縮偵測（含等幅測距目標價）` |
| `src/compute/strategy/v4_strategy_engine.py:468` | 目標價 | `# 等幅測距目標價` |
| `src/compute/strategy/v5_modules.py:13` | 目標價 | `# v19.179 B1-b:三檔目標價的反推(÷ YIELD_*_DEC)已下沉 classify_stock_357_price,` |
| `src/compute/strategy/v5_modules.py:336` | 目標價 | `# 分級與三檔目標價全部委派 SSOT；'na' 已涵蓋 price/avg_div 缺值或 ≤0` |
| `src/ui/tabs/stock_grp_sections/section_batch_fetcher.py:197` | 目標價 | `# ── 型態目標價(批次,v19.164)──────────────────────────────` |
| `src/ui/tabs/stock_grp_sections/section_portfolio_summary.py:163` | 目標價 | `# ── 🎯 型態目標價(全組合,共用批次來源;逐檔看圖下鑽,非第二輸入)──` |
| `src/ui/tabs/stock_sections/section_when_buy_sell.py:150` | 目標價 | `# 目標價(一比一對稱法)` |
| `src/ui/tabs/tab_stock.py:244` | 目標價 | `# v19.163 user 要求:型態目標價接進個股,套用當前 t2_sid 標的。(v19.174 去識別化)` |
| `src/ui/tabs/tab_stock_grp.py:45` | 目標價 | `# ══ ② 輸入多檔代碼(v19.164 唯一來源:型態目標價 / 財報體質 / 三階段濾網全部吃這裡)═══` |
| `src/ui/views/page_inspect.py:1881` | 目標價 | `# L2 自己寫的一句話（含三檔目標價或「不適用」的理由）。` ← **v2 新頁**，註解，不上畫面（但它描述的那個 `msg` **會**上畫面，見 §五 (b)） |

### B-2｜DOCSTRING（12）

| file:line | 詞 | 原文（截斷） |
|---|---|---|
| `src/compute/scoring/scoring_engine.py:1288` | 目標價 | `目標價 = entry × 1.15（預設+15%）`（`calc_rr_ratio` docstring） |
| `src/compute/strategy/entry_stop_levels.py:212` | 目標價 | `take_profit_price: 停利目標價（算盈虧比用）。None → 不算盈虧比。` |
| `src/compute/strategy/pattern_targets.py:1` | 目標價 | 模組 docstring 首行「線型形態學目標價引擎(L2 純函式)」 |
| `src/compute/strategy/pattern_targets.py:7` | 目標價 | `把「線型形態學」的**目標價 / 甜蜜價 / 止損 / 風報比**做成` |
| `src/compute/strategy/portfolio_manager.py:135` | **建議買進** | `計算單筆衛星股票的建議買進量。`（`calc_position` docstring，**該函式為死碼**，見 §四） |
| `src/compute/strategy/v4_strategy_engine.py:436` | 目標價 | `target_price: float  等幅測距目標價` |
| `src/data/portfolio/gsheet_portfolio.py:21` | 推薦 | `- OAuth（推薦）：使用者在 sidebar 用 Google 登入，自帶 Sheet` |
| `src/ui/tabs/grape_ladder.py:288` | 推薦 | `exclude    : list[str]   排除的 tickers（通常＝使用者現有持股，避免推薦已持有）。` |
| `src/ui/tabs/pattern_targets_ui.py:1` | 目標價 | 模組 docstring 首行「型態目標價計算機 UI(L5…)」 |
| `src/ui/tabs/pattern_targets_ui.py:8` | 目標價 | `user 需求:「由技術線型計算甜蜜價與目標價」+「接在個股/組合裡,套用當前標的」。`（引用 user 原話，**建議不要改**——改了等於竄改需求紀錄） |
| `src/ui/tabs/pattern_targets_ui.py:181` | 目標價 | `"""可重用核心:對單一代碼跑型態目標價分析(自動偵測 + 可手動覆寫)。` |
| `src/ui/tabs/stock_grp_sections/section_portfolio_summary.py:517` | 目標價 | `"""🎯 型態目標價(全組合)— v19.164 批次化,共用上方批次的 K 線來源。` |

---

# 三、【C】送給 LLM 的 prompt 文字

> 共 **6 個 word-occurrence / 5 行**。**全部不上畫面**（都是組 prompt 字串送 Gemini）。
> ⚠️ 其中 4 行是**反向用法：明文禁止 AI 講這些話**。**改它們＝把合規護欄拆掉**，請勿列入改動清單。

| # | file:line | 詞 | 原文 | 判定 |
|---|---|---|---|---|
| **C1** | `src/compute/notify/ai_judgment.py:84` | 必漲 / 目標價 | `2. 【絕對禁止】喊「一定買 / 保證賺 / 必漲 / 快進場」,也不給任何具體買賣點或目標價。` | **反向（禁止 AI 說）** ⛔ 不得改 |
| **C2** | `src/compute/notify/weekly_review_prompt.py:55` | 必漲 / 目標價 | 同上一字不差 | **反向（禁止 AI 說）** ⛔ 不得改 |
| **C3** | `src/services/ai_structured_summary.py:153` | 必漲 | `4. 不要喊「一定要買 / 保證賺 / 必漲 / 快進場」這種話。` | **反向（禁止 AI 說）** ⛔ 不得改 |
| **C4** | `src/services/financial_health_engine.py:210` | 推薦 | `2. 禁止在輸出中推薦任何買賣操作或 ETF 標的。` | **反向（禁止 AI 說）** ⛔ 不得改 |
| **C5** | `src/compute/scoring/exit_signals.py:175` | 目標價 | `'法人調降目標價、重大意外或弊案）才算「利空」；一般中性報導、活動、正面消息勿誤判為利空。'` | **中性描述**（`build_news_prompt` 內，用「法人調降目標價」當**利空新聞的判定範例**，不是叫 AI 給目標價）。不上畫面。<br>建議：**不改**；真要改可寫「法人調降評價」，但那會輕微改變判定語意，屬**計算/判定行為變更** → 已超出合規窗口 |

---

# 四、【D】內部識別字 / 變數名 / 函式名 / dict key

**主清單六個詞：0 筆。**

判定依據：六個禁用詞都是中文詞，而本 repo 的 Python 識別字全為 ASCII
（`target_price` / `calc_position` / `calc_rr_ratio` / `RR_DEFAULT_TARGET_GAIN` 等）；
唯一會讓中文進入「識別字」角色的是**中文 dict key**，而主清單六詞**沒有**任何一個被當 dict key 用
（實測：`grep -n "'目標價'\|\"目標價\"" ` 在 `app.py`+`src/**` 0 命中）。

⚠️ **但疑似區有**：`'加碼金'`（`src/services/dividend_station_service.py:68` 等）、
`'甜蜜價'` / `'距甜蜜價%'`（`section_portfolio_summary.py:539-540`）是**中文 dict key 同時也是 DataFrame 欄名**
→ 它們**會直接印在畫面上**，所以我把它們歸【A】性質而不是【D】。見疑似區。

---

# 五、【E】死碼 / 不可達字串

> ⚠️ **這是承重判定**（會被拿來決定「這個不用改」）。兩筆都附完整查證方法與結果，請照著複核。

## E1｜`src/compute/strategy/portfolio_manager.py:167`　`f'📊 建議買進 {shares} 股（{lots} 張），成本約 NT${actual_cost:,.0f}，'`

**判定：死碼 —— `CoreSatelliteManager.calc_position()` 在 production 0 caller。**

**查證方法與結果（三段，缺一不可）：**

1. **全 repo 全副檔名字串搜尋**（不限 `.py`，排除 `__pycache__` / `.git`）：
   ```
   grep -rn "calc_position" .
   ```
   命中 14 行。扣掉**同名不同物**的 `src/compute/risk/risk_control.py:309 calc_position_size`
   （名字前綴相同，是另一支函式）與其測試後，指向本方法的只剩：
   - 定義本身：`src/compute/strategy/portfolio_manager.py:128`
   - **測試 7 處**：`tests/test_portfolio_manager_coverage.py:123,132,140,146,154,161,169`
   - `docs/DEAD_CODE_AUDIT.md:39`（講的是 `calc_position_size`，非本方法）
   → **production 命中數 = 0。**

2. **類別層級**：`CoreSatelliteManager` 在 production **確實有人用**，但只用到 property：
   - `src/ui/etf/etf_tab_portfolio.py:78,86-87` → 只讀 `.core_ratio` / `.satellite_ratio`
   - `src/ui/etf/etf_tab_portfolio.py:758,763-764` → 只讀 `.core_ratio`
   其餘命中（`page_hold.py:178,2184`、`station_cards.py:935`）都是**說明文字裡提到類別名**，
   而且語意是「**⛔ 也不會改用** `CoreSatelliteManager`」——反向引用，不是呼叫。
   → `calc_position` / `check_rebalance` / `summary` **三個方法在 production 都沒有 caller**
   （`check_rebalance` 只被 `summary()` 內部呼叫，`summary()` 只被測試呼叫）。

3. **排除動態呼叫**：
   - barrel `src/compute/strategy/__init__.py` 的 PEP 562 `__getattr__` 只轉發**模組層級**名稱
     （`for sub in _SUBMODULES: if name in vars(sub)`），**方法名不在 `vars(module)` 裡**，
     故 barrel 這條路**到不了** `calc_position`。
   - `grep -rn "getattr(_mgr\|getattr(_m,\|getattr(_CSM"` → 0 命中；
     `etf_tab_portfolio.py` 對 manager 物件的全部使用只有上述 4 行 property 讀取。

**不確定的部分（據實標明）**：我證明的是「**這個 repo 的 production 程式碼裡沒有呼叫點**」。
我**沒有**證明「執行期絕對不會被叫到」——若有我沒想到的反射/eval 路徑（我查了 `getattr`，沒查 `eval`/`exec`/`__getattribute__` 覆寫），結論會翻掉。

**建議處置**：合規窗口只准改文字 → **本筆不必改，但也不該被當成「已經沒問題」**。
它是一個隨時可能被接線的地雷字串（一行 `mgr.calc_position(...)` 就會讓「📊 建議買進 N 股」上畫面）。
建議在合規窗口外另案處理（刪掉、或把 `message` 改中性）。

## E2｜`src/compute/strategy/entry_stop_levels.py:259`　`unavailable_reason="未提供停利目標價"`

**判定：字串可被產生，但沒有任何 consumer → 不可能上畫面。**

**查證方法與結果：**

1. `compute_entry_stop_levels` 的 production caller 只有 2 處：
   - `src/ui/tabs/tab_stock.py:818`：`compute_entry_stop_levels(df2)`（**不傳** `take_profit_price` → 會走到這個分支），
     但該處**只讀** `.entry_half` / `.abs_stop`（`:819-820`），`unavailable_reason` **沒被讀**；
     畫面上的「未評估」理由是該檔**自己另外組的** `_rr_why`（`tab_stock.py:851-853`），與 L2 這個字串無關。
   - `src/ui/tabs/stock_grp_sections/section_batch_fetcher.py:233`：**有傳** `take_profit_price=_tp1_4`，
     故正常情況走不到該分支；且它把值塞進 dict key `'_rr_why'`（`:244`）。
2. `grep -rn "rr_why" .` → 全 repo 只有 3 行：上述寫入 1 行 + `tab_stock.py` 那個**同名但無關**的區域變數 2 行。
   → **`'_rr_why'` 這個 key 從來沒有被讀過。**
3. 該 dict（`results_t3` 的元素）下游唯一的表格渲染 `_render_master_table`
   （`section_portfolio_summary.py:286-390`）是**逐欄具名重建** `rows`，`_rr_why` 不在其中；
   `_render_pattern_batch`（`:512-545`）同理。**沒有「把 dict 整包丟給 `st.dataframe`」的路徑。**

**不確定的部分**：同 E1，我沒有排除反射存取。另外 `results_t3` 會進 `st.session_state`，
若日後有人寫 `st.dataframe(pd.DataFrame(results_t3))` 就會整包噴出來——目前沒有。

---

# 六、疑似區（高風險近義詞）—— **不混進主清單**

**命中量（實測）**：`加碼` 131 / `減碼` 58 / `買點` 33 / `甜蜜價` 15 / `逢低` 11 / `賣點` 8
／`建議賣出` **0** ／`該買` **0** ／`該賣` **0** ＝ 合計 **256 個 word-occurrence，247 個相異行**。

token 分類：**`STRING` 178** / `DOCSTRING` 45 / `COMMENT` 33。
下面**只列 178 個 `STRING`**（註解/docstring 不上畫面，不列）。

> ⚠️ **`STRING` ≠ 一定上畫面**：其中包含 LLM prompt（`persona.py`、`app_ai_service.py`、
> `dividend_station_service.py` 的 prompt 段、`rs_leader_service.py`）、以及
> `ai_judgment.py:84` / `weekly_review_prompt.py:55` 這兩條**反向禁止句**（⛔ 不得改）。
> 我**沒有**對這 178 筆逐一追渲染路徑（只對主清單 19 筆做了），故本區是**待分類清單，不是待改清單**。

> ⚠️ **這一區的量級遠大於主清單**，而且很多是**功能名/欄名**（例：`235 加碼燈`、`加碼金`、
> `σ減碼≥`、`甜蜜價`、`距甜蜜價%`）。改它們會動到 **DataFrame 欄名**——
> 欄名同時是 dict key，**改欄名可能不只是改文字**（下游若有 `r.get('加碼金')` 這種讀取就會斷）。
> 實測確有此情形：`dividend_station_service.py:979,982` 讀 `r.get("加碼金")`。
> → **疑似區不屬於「只改使用者看得到的文字」這個窗口，建議另立一案。**

### 最需要優先看的幾筆（我主觀挑的，非窮舉排序）

| file:line | 原文 | 為什麼優先 |
|---|---|---|
| `src/ui/tabs/stock_sections/section_when_buy_sell.py:105` | `_glabel = '🟢 可考慮加碼' if _gate['can_add'] else '🔴 不建議加碼'` | 直接的買賣指示，且是**燈號文字** |
| `src/ui/tabs/stock_sections/section_when_buy_sell.py:284` | `➕ 加碼點（策略3 突破法）：>{_add_pt:.2f}` | 具體價位 + 動作 |
| `src/ui/tabs/macro/section_chips.py:178,183` | `'大戶點火，跟著大戶走 → 積極加碼'` / `'大戶倒貨，嚴格減碼 → 離場為上'` | 最接近「直接買賣建議」 |
| `src/ui/tabs/macro/section_long.py:268` | `'左側交易最佳布局區，大膽加碼！'` | 同上，語氣最強 |
| `src/compute/etf/etf_helpers.py:261,272` | `'大跌大買 — 大幅加碼，剩餘資金主力投入'` / `'建議減碼；勿在 +Nσ 以上加碼'` | L2 產出的 action 字串，兩個 ETF 頁共用 |
| `src/compute/strategy/v5_modules.py:373` | `f"估值過高，建議逢高減碼"` | **這條會上 v2 新頁**，見 §七 (b) |
| `src/ui/etf/etf_tab_single.py:435-436` | `'🟢 <b>強烈買進（特價）</b>…值得分批佈局'` | 含「強烈買進」——**六大禁用詞掃不到**，但實質相同 |
| `src/ui/tabs/stock_grp_sections/section_portfolio_summary.py:539-540` | `'甜蜜價': …` / `'距甜蜜價%': …` | **DataFrame 欄名**，改名同時改 dict key |
| `src/ui/render/station_cards.py:856,860` | `_fig(str(add_n), "該加碼")` / `「該加碼」= 235 有加碼金;` | **v2 新頁**（`src/ui/render/**`）的燈牆卡 |

### 完整 178 筆（依層／目錄分組）

#### v1 舊分頁 (src/ui/**) — 100 筆字串命中

| file:line | 詞 | 字串（截斷 120 字）|
|---|---|---|
| `src/ui/etf/etf_tab_ai.py:309` | 加碼 | `placeholder='例如：台灣高股息 ETF 和美國債券 ETF 如何搭配？升息循環尾聲該加碼長債嗎？')` |
| `src/ui/etf/etf_tab_dividend_station.py:49` | 加碼 | `"健檢", "235 燈號", "加碼金", "3-3-3", "建議動作"]` |
| `src/ui/etf/etf_tab_dividend_station.py:131` | 加碼 | `st.markdown("### 💼 我的持股戰情室 — 定期健檢 · 235 加碼 · AI 總結")` |
| `src/ui/etf/etf_tab_dividend_station.py:133` | 加碼 | `"戰情表分兩區：**ETF**＝定期定額（健檢 A/B/C/D＋235 加碼＋3-3-3）;**個股**＝汰換"` |
| `src/ui/etf/etf_tab_dividend_station.py:243` | 加碼 | `st.markdown("##### 🛡️ 定期定額策略（ETF）　·　235 加碼燈 ＋ 3-3-3")` |
| `src/ui/etf/etf_tab_dividend_station.py:249` | 賣點 | `"財報 C/F → 建議換出;KD 死亡交叉/頂背離＝賣點確認、黃金交叉/底背離＝轉強留。")` |
| `src/ui/etf/etf_tab_dividend_station.py:338` | 加碼 | `_parts.append(f"{_add_n} 檔亮加碼燈")` |
| `src/ui/etf/etf_tab_dividend_station.py:465` | 加碼 | `"⚠️ 235 加碼燈的紅／黃／綠是**跌多深、該加多少碼**,不是體質好壞 —— "` |
| `src/ui/etf/etf_tab_dividend_station.py:466` | 加碼 | `"它的 🔴 是「崩盤／深水加碼」訊號。點進去每一盞燈都會寫明白。"` |
| `src/ui/etf/etf_tab_dividend_station.py:563` | 加碼 | `st.warning(_msg + "（核心偏低 → 可加碼核心）")` |
| `src/ui/etf/etf_tab_dividend_station.py:638` | 加碼 | `st.warning("🚦 **235 加碼觸發**：" + "、".join(` |
| `src/ui/etf/etf_tab_dividend_station.py:639` | 加碼 | `f"{d['代號']} {d['235']}｜加碼 {d['加碼金']}" for d in digest["adds"]))` |
| `src/ui/etf/etf_tab_dividend_station.py:641` | 加碼 | `st.success("✅ 今日無汰弱紅燈、無 235 加碼觸發 —— 續抱、定期定額即可。")` |
| `src/ui/etf/etf_tab_grp_compare.py:217` | 減碼 | `'σ減碼≥':   r.get('sigma_sell'),` |
| `src/ui/etf/etf_tab_grp_compare.py:249` | 減碼 | `help='7% 估值策略：殖利率≥7%🟢強烈買進 / 5%~7%⚪中性 / 3%~5%🟡減碼 / ≤3%🔴獲利了結'),` |
| `src/ui/etf/etf_tab_grp_compare.py:264` | 減碼 | `'σ減碼≥':   st.column_config.NumberColumn(` |
| `src/ui/etf/etf_tab_grp_compare.py:265` | 減碼 | `'σ減碼≥', format='%.2f',` |
| `src/ui/etf/etf_tab_grp_compare.py:266` | 減碼 | `help='標準差建議「減碼」價位(μ+2σ);市價 ≥ 此價 = 歷史相對高點'),` |
| `src/ui/etf/etf_tab_grp_compare.py:272` | 加碼 | `help='彙整綜合分 / 紅旗 / 加碼時機 / 同類重疊的一句話說明'),` |
| `src/ui/etf/etf_tab_grp_compare.py:303` | 減碼 | `'/ σ減碼≥（μ+2σ 相對高點）/ σ位階（現價離均線幾個 σ）。'` |
| `src/ui/etf/etf_tab_grp_compare.py:307` | 加碼 | `'- **✅ 留下**：綜合分 ≥0.65（4★↑）且沒紅旗 —— 體質好,續抱；價位偏低時可分批加碼。\n'` |
| `src/ui/etf/etf_tab_grp_compare.py:308` | 加碼 | `'- **⚠️ 觀察**：綜合分中段（2★~3★),或體質好但踩到 1 個紅旗 —— 先別加碼,下一季再看。\n'` |
| `src/ui/etf/etf_tab_portfolio.py:642` | 賣點 | `st.caption('💡 **核心**看「總報酬 vs 殖利率 + MA60 趨勢」；**衛星**看「MA20 ± σ 五階分級買賣點」')` |
| `src/ui/etf/etf_tab_portfolio.py:689` | 加碼 | `help='依 σ 位階自動推導加碼/停利比例'),` |
| `src/ui/etf/etf_tab_single.py:416` | 賣點 | `st.markdown('#### 🧠 策略二：7% 存股估值買賣點')` |
| `src/ui/etf/etf_tab_single.py:442` | 加碼 | `'可持有,待殖利率 ≥ 7% 再加碼'),` |
| `src/ui/etf/etf_tab_single.py:445` | 減碼 | `'box': ('🟡 <b>適度減碼（合理）</b>:殖利率 ≤ 5%,估值合理偏高', 'yellow'),` |
| `src/ui/etf/etf_tab_single.py:446` | 減碼 | `'tc':  ('殖利率 3%~5%,估值合理偏高,適度減碼',` |
| `src/ui/etf/etf_tab_single.py:447` | 加碼 | `'不宜重倉,等待 5% 以上再加碼'),` |
| `src/ui/etf/etf_tab_single.py:450` | 減碼 | `'box': ('🔴 <b>獲利了結（昂貴）</b>:殖利率 ≤ 3%,現值高估,考慮減碼', 'red'),` |
| `src/ui/etf/etf_tab_single.py:671` | 買點 | `st.markdown('#### 🎯 📅 長線 σ 量化買點(存股框架:年線基準,跌了就買)')` |
| `src/ui/etf/etf_tab_single.py:717` | 逢低 | `_t5_label, _t5_color, _t5_action = '🟡 短線回測（跌破但 MA60 仍上彎）', 'yellow', '可逢低分批布局，等回上 MA60 確認'` |
| `src/ui/etf/etf_tab_single.py:719` | 減碼 | `_t5_label, _t5_color, _t5_action = '🔴 趨勢轉弱（跌破 MA60 且下彎）', 'red', '建議減碼或觀望，等趨勢翻轉'` |
| `src/ui/etf/etf_tab_single.py:778` | 買點 | `f'🟢🟢 <b>跌破季線：波段大買點（超跌）</b><br>'` |
| `src/ui/etf/etf_tab_single.py:781` | 加碼 | `f'<b>框架提醒</b>：跌破季線視為波段超跌，分批加碼黃金區',` |
| `src/ui/etf/etf_tab_single.py:786` | 加碼 | `'剩餘資金分批加碼')` |
| `src/ui/etf/etf_tab_single.py:789` | 買點 | `f'🟢 <b>跌破月線：短線小買點</b><br>'` |
| `src/ui/etf/etf_tab_single.py:792` | 加碼 | `f'<b>框架提醒</b>：跌破月線可小量加碼',` |
| `src/ui/etf/etf_tab_single.py:796` | 買點 | `'短線小買點',` |
| `src/ui/etf/etf_tab_single.py:797` | 加碼 | `'投入 20–30% 資金小量加碼')` |
| `src/ui/etf/etf_tab_single.py:816` | 減碼 | `'衛星部位停利或減碼，核心紀律扣款')` |
| `src/ui/etf/etf_tab_smart.py:173` | 減碼 | `'區間': ['強買 (-2σ)', '買進 (-1σ)', '均線 (μ)', '注意 (+1σ)', '減碼 (+2σ)', '⬛ 現價'],` |
| `src/ui/tabs/macro/helpers.py:251` | 加碼 | `'雷達警戒 → 維持持倉但暫緩加碼；雷達平靜 → 採用慢總經結論。')` |
| `src/ui/tabs/macro/section_chips.py:178` | 加碼 | `_hye_concl = '大戶點火，跟著大戶走 → 積極加碼'` |
| `src/ui/tabs/macro/section_chips.py:183` | 減碼 | `_hye_concl = '大戶倒貨，嚴格減碼 → 離場為上'` |
| `src/ui/tabs/macro/section_chips.py:193` | 加碼 | `st.markdown(f'<div style="color:#58a6ff;font-size:12px;padding:2px 6px;">• 投信買超 {_tn3:.1f}億 → 連續買超是加碼訊號</div>', unsafe_a` |
| `src/ui/tabs/macro/section_chips.py:241` | 減碼 | `_sql_mact = '全面減碼、去槓桿，勿追高'` |
| `src/ui/tabs/macro/section_chips.py:596` | 減碼 | `_v5_strategy = '收回資金，逢高減碼漲多個股，等待期空回補訊號'` |
| `src/ui/tabs/macro/section_cross_ai.py:272` | 逢低 | `_ai5_pts.append(f'年線乖離{_ai_bias:.1f}% 超跌逢低佈局')` |
| `src/ui/tabs/macro/section_long.py:255` | 減碼 | `'資金動能趨緩，減碼等待訊號確認', TRAFFIC_RED))` |
| `src/ui/tabs/macro/section_long.py:265` | 減碼 | `'開始分批減碼（乖離>20%啟動停利）', TRAFFIC_RED))` |
| `src/ui/tabs/macro/section_long.py:268` | 加碼 | `'左側交易最佳布局區，大膽加碼！', TRAFFIC_GREEN))` |
| `src/ui/tabs/macro/section_long.py:309` | 減碼 | `_bl     = ('⚠️ 乖離過大，考慮減碼' if _bias_v > 20` |
| `src/ui/tabs/macro/section_long.py:354` | 減碼 | `_i1c = f'SOX {_sox_pct:+.1f}% / DXY {_dxy_val:.1f} → 外資提款，電子股嚴格減碼'` |
| `src/ui/tabs/macro/section_long.py:601` | 減碼 | `_t2a = '嚴格減碼防守，現金為王　→ 實際持股見 🎚️ 建議持股油門'` |
| `src/ui/tabs/macro/section_long.py:606` | 逢低 | `_t2a = '尋找錯殺優質股逢低布局　→ 實際持股見 🎚️ 建議持股油門'` |
| `src/ui/tabs/macro/section_long.py:689` | 加碼 | `_t6a = '科技類股可持有或加碼'` |
| `src/ui/tabs/macro/section_mid.py:204` | 買點 | `st.caption('💡 與 CPI 配對：兩者同步月降 → ⭐ CPI×Fed 雙頂回落（多頭最佳買點）')` |
| `src/ui/tabs/macro/section_mid.py:456` | 減碼 | `'資金轉向定存或匯出，減碼等待訊號確認。')` |
| `src/ui/tabs/macro/section_mid.py:473` | 加碼 | `'跌破月線即走，切勿因多頭情緒追漲加碼。')` |
| `src/ui/tabs/macro/section_mid.py:491` | 加碼 | `'等待更明確的突破訊號加碼。')` |
| `src/ui/tabs/macro/section_mid.py:495` | 買點 | `_sqc8t = ('💎 長線黃金坑（超跌買點）：大盤超跌至年線之下，'` |
| `src/ui/tabs/macro/section_short.py:91` | 逢低 | `_a5a = '可留意回調後逢低布局'` |
| `src/ui/tabs/macro/section_short.py:144` | 逢低 | `f'底部擴散！多數股票止跌，可留意逢低布局機會')` |
| `src/ui/tabs/macro/section_state.py:135` | 減碼 | `f'年線乖離 +{_b240:.1f}% > {PIVOT_BIAS_240_PCT:.0f}% → 頂部拐點區間，考慮減碼'))` |
| `src/ui/tabs/macro_stock_link.py:98` | 減碼 | `"🔴 大盤空頭 → 個股操作宜保守 / 減碼，即使基本面強的股也難完全"` |
| `src/ui/tabs/pattern_targets_ui.py:116` | 甜蜜價 | `a.metric("🎯 甜蜜價(進場)", _fnum(sweet),` |
| `src/ui/tabs/pattern_targets_ui.py:133` | 減碼 | `tip = "破底翻要**站回支撐/頸線且帶量**才算數;停損貼破底低,跌破＝甩轎失敗。到第一波滿足先減碼。"` |
| `src/ui/tabs/pattern_targets_ui.py:166` | 甜蜜價 | `(r.get("sweet"), "甜蜜價", "#58a6ff", "solid"),` |
| `src/ui/tabs/portfolio_binder.py:153` | 加碼 | `st.caption('綁定 Google Sheet 後,戰情室會自動抓你的持股做健檢 / 235 加碼 / AI 總結,'` |
| `src/ui/tabs/stock_grp_sections/section_portfolio_summary.py:526` | 甜蜜價 | `'「—」不給假目標;距甜蜜價% 負=待突破、正=已突破。')` |
| `src/ui/tabs/stock_grp_sections/section_portfolio_summary.py:539` | 甜蜜價 | `'甜蜜價': _fmt_pattern(cs.get('sweet')),` |
| `src/ui/tabs/stock_grp_sections/section_portfolio_summary.py:540` | 甜蜜價 | `'距甜蜜價%': _dist_s,` |
| `src/ui/tabs/stock_grp_sections/section_portfolio_summary.py:766` | 減碼 | `'出場':     st.column_config.TextColumn('出場', width='small', help='三維出場訊號:🔴3=強烈出場 / 🟠2=建議減碼 / 🟡1=留意 / 🟢0=清淡(利空新聞需按「AI 掃利空」` |
| `src/ui/tabs/stock_sections/section_revenue.py:55` | 買點 | `_db = '配合技術面買點可進場'` |
| `src/ui/tabs/stock_sections/section_when_buy_sell.py:76` | 減碼 | `'<br>🔴 <b>出場訊號</b>：這些條件出現代表要考慮賣出或減碼'` |
| `src/ui/tabs/stock_sections/section_when_buy_sell.py:105` | 加碼 | `_glabel = '🟢 可考慮加碼' if _gate['can_add'] else '🔴 不建議加碼'` |
| `src/ui/tabs/stock_sections/section_when_buy_sell.py:114` | 加碼 | `f'<b>🧭 加碼三問</b>：<b>{_glabel}</b>{_rows}</div>',` |
| `src/ui/tabs/stock_sections/section_when_buy_sell.py:116` | 加碼 | `st.caption('💡 三個都 ✅ 才考慮加碼 —— **σ 夠低(不追高)＋ 趨勢沒壞(不攤平弱勢)'` |
| `src/ui/tabs/stock_sections/section_when_buy_sell.py:235` | 減碼 | `st.markdown('**📉 減碼/出場訊號**')` |
| `src/ui/tabs/stock_sections/section_when_buy_sell.py:240` | 減碼 | `_exit.append(f'⚠️ KD高檔死叉 K={k2:.0f} → 策略3：開始減碼')` |
| `src/ui/tabs/stock_sections/section_when_buy_sell.py:242` | 減碼 | `_exit.append('⚠️ 脫離布林上軌 → 策略3：減碼50%')` |
| `src/ui/tabs/stock_sections/section_when_buy_sell.py:257` | 減碼 | `_exit.append('⚠️ 週MACD紅柱連縮 → 上漲動能衰減，準備減碼')` |
| `src/ui/tabs/stock_sections/section_when_buy_sell.py:284` | 加碼 | `st.markdown(f'<div style="font-size:12px;color:#58a6ff;padding:2px 0;">➕ 加碼點（策略3 突破法）：>{_add_pt:.2f}</div>', unsafe_allo` |
| `src/ui/tabs/stock_sections/section_when_buy_sell.py:378` | 加碼 | `_hlines.append((_add_pt_v, '#a371f7', 'dashdot', f'加碼點 >{_add_pt_v:.2f}'))` |
| `src/ui/tabs/tab_edu.py:687` | 買點 | `→ 龍多股確認，大型法人機構尚未追入前的黃金買點` |
| `src/ui/tabs/tab_edu.py:826` | 買點 | `\| 突破頸線 \| 收盤站上頸線 + 成交量爆增 ≥ 均量 1.5 倍 → 買點 \|` |
| `src/ui/tabs/tab_edu.py:830` | 買點 | `#### 🔑 操作細節：頸線突破買點` |
| `src/ui/tabs/tab_edu.py:833` | 加碼 | `2. **拉回不破**：突破後若拉回測試頸線不跌破 → 加碼機會` |
| `src/ui/tabs/tab_edu.py:911` | 加碼 | `\| **加碼** \| 突破後拉回測試 Pivot 不破，再加碼 \|` |
| `src/ui/tabs/tab_edu.py:916` | 加碼 | `> 停損寫成一個區間、加碼倍數也是全站不存在的規則。` |
| `src/ui/tabs/tab_edu.py:1042` | 買點 | `- **復甦**:谷底翻揚,失業率高但 PMI 反轉、央行寬鬆,股市最佳買點` |
| `src/ui/tabs/tab_edu.py:1340` | 買點 | `極端低位 = 散戶絕望 = 反向買點。` |
| `src/ui/tabs/tab_edu.py:1352` | 買點 | `- VIX ≥ 40:**極度恐慌**,歷史上多為**最佳逆向買點**` |
| `src/ui/tabs/tab_helpers.py:170` | 加碼 | `return '🔵 加碼'` |
| `src/ui/tabs/tab_helpers.py:176` | 減碼 | `return '🟠 減碼'` |
| `src/ui/tabs/tab_stock.py:243` | 甜蜜價 | `with st.expander('🎯 型態目標價（本檔 K 線自動算：甜蜜價·止損·目標）', expanded=False):` |
| `src/ui/tabs/tab_stock.py:826` | 買點 | `'技術面低風險買點', '#58a6ff', '#1a2744'), unsafe_allow_html=True)  # v19.174 去識別化` |
| `src/ui/tabs/tab_stock.py:1798` | 買點 | `_sr_parts2.append(f'大量紅K 1/2 低風險買點={_entry_half}')  # v19.174 去識別化` |
| `src/ui/tabs/tab_stock_picker.py:1264` | 加碼 | `f'投信買超{r.get("inst_label", "?")}、千張大戶加碼{r.get("major_label", "?")}）'` |

#### v2 新頁 / L4 render — 24 筆字串命中

| file:line | 詞 | 字串（截斷 120 字）|
|---|---|---|
| `src/ui/render/etf_render.py:60` | 加碼 | `(50,  '🟡', '保守配置：控制股票曝險 —— 只留核心市值型ETF，主題／槓桿型暫不加碼',` |
| `src/ui/render/etf_render.py:464` | 逢低 | `hint = '🟢 嚴重低估，逢低佈局機會'` |
| `src/ui/render/station_cards.py:151` | 減碼 | `"🟡": "留意 / 減碼觀察",` |
| `src/ui/render/station_cards.py:168` | 加碼 | `"timing": _L235_MEANING,       # 235 加碼燈` |
| `src/ui/render/station_cards.py:856` | 加碼 | `f'{_fig(str(add_n), "該加碼")}{_fig(str(cut_n), "該換掉")}'` |
| `src/ui/render/station_cards.py:859` | 加碼 | `f'三個數字**可能重疊**(同一檔可以既亮加碼燈、又有燈缺資料),故不相加。'` |
| `src/ui/render/station_cards.py:860` | 加碼 | `f'「該加碼」= 235 有加碼金;「該換掉」= 健檢紅燈;'` |
| `src/ui/render/station_cards.py:909` | 加碼 | `"跌多深該加碼",` |
| `src/ui/render/station_cards.py:911` | 加碼 | `f"235 加碼燈：<b>週線</b> {T.BOLL_PERIOD_WEEKS} 週布林 z"` |
| `src/ui/render/station_cards.py:912` | 加碼 | `f"（σ 取這 {T.BOLL_PERIOD_WEEKS} 週），加碼金比例走 "` |
| `src/ui/render/station_cards.py:917` | 加碼 | `"（σ 取近一年日線），加碼比例是另一組字面值"` |
| `src/ui/render/station_cards.py:921` | 加碼 | `"σ 的取樣視窗、以及對應的加碼比例三者全都不同 —— "` |
| `src/ui/render/station_cards.py:922` | 加碼 | `"<b>同一檔在兩個畫面拿到不同的加碼建議是正常的</b>，不是哪邊算錯。"` |
| `src/ui/render/ui_widgets.py:373` | 減碼 | `_neg_kw = ['警戒', '危險', '賣超', '空單', '減碼', '停損', '撤離', '跌破', '過熱', '回調', '降倉', '空頭', '侵蝕', '高估']` |
| `src/ui/render/ui_widgets.py:374` | 加碼 | `_pos_kw = ['強勢', '買超', '多頭', '安全', '健康', '買進', '加碼', '流入', '突破', '進攻', '上漲', '低估', '特價']` |
| `src/ui/views/page_hold.py:1573` | 加碼 | `"有紅燈／加碼燈就直接列出來（**不排優先序**，兩件事同時成立時"` |
| `src/ui/views/page_hold.py:1582` | 加碼 | `([f"{station.add_n} 檔亮加碼燈"] if station.add_n else [])` |
| `src/ui/views/page_hold.py:1654` | 加碼 | `("加碼 N", "235 加碼燈觸發（digest 的 `adds`）"),` |
| `src/ui/views/page_hold.py:1665` | 加碼 | `value=(f"加碼 {station.add_n} · 汰弱 {station.cut_n} · "` |
| `src/ui/views/page_hold.py:1760` | 加碼 | `("235 加碼燈的紅不是體質差",` |
| `src/ui/views/page_hold.py:1772` | 加碼 | `label="燈牆（235 加碼燈 · 3-3-3 · 健檢四盞）", state=_state,` |
| `src/ui/views/page_hold.py:1779` | 加碼 | `label="燈牆（235 加碼燈 · 3-3-3 · 健檢四盞）", state=UI_LIVE,` |
| `src/ui/views/page_hold.py:1802` | 加碼 | `("235 加碼燈的 VIX 門檻",` |
| `src/ui/views/page_hold.py:2929` | 加碼 | `"健檢紅燈汰弱清單 · 235 加碼觸發清單 · 整批抓取失敗未納入的代號 · "` |

#### L3 service — 11 筆字串命中

| file:line | 詞 | 字串（截斷 120 字）|
|---|---|---|
| `src/services/app_ai_service.py:298` | 加碼 | `'建議突破60日箱頂時分批進場，回測紅K低點不破可加碼。')` |
| `src/services/app_ai_service.py:322` | 減碼 | `lines.append(f'🔴 【過熱警告】年線正乖離{b240:.0f}%{b240_badge}（>25%），策略1：開始分批減碼。'` |
| `src/services/app_ai_service.py:329` | 減碼 | `lines.append(f'🟠 【分批減碼】年線乖離>25%{b240_badge} + 月線乖離>10%雙重過熱，'` |
| `src/services/dividend_station_service.py:68` | 加碼 | `"加碼金": _add,` |
| `src/services/dividend_station_service.py:312` | 加碼 | `"健檢": "⚪", "235 燈號": "—", "加碼金": "", "3-3-3": "—",` |
| `src/services/dividend_station_service.py:979` | 加碼 | `if str(r.get("加碼金", "") or "").strip():` |
| `src/services/dividend_station_service.py:982` | 加碼 | `"加碼金": str(r.get("加碼金", ""))})` |
| `src/services/dividend_station_service.py:996` | 加碼 | `_adds = "、".join(f"{d['代號']} {d['235']} 加碼{d['加碼金']}"` |
| `src/services/dividend_station_service.py:1002` | 加碼 | `"沒有紅燈也沒有加碼時,請明講『續抱、定期定額即可』。\n"` |
| `src/services/dividend_station_service.py:1006` | 加碼 | `f"- 235 加碼觸發：{_adds}\n"` |
| `src/services/rs_leader_service.py:357` | 買點 | `"- 這是「相對強弱」不是「基本面買點」：抗跌只代表跌得比大盤少 / 逆勢強，不等於便宜或該追。",` |

#### L2 compute — 37 筆字串命中

| file:line | 詞 | 字串（截斷 120 字）|
|---|---|---|
| `src/compute/etf/dividend_station.py:296` | 加碼 | `return Flag("🟡", f"趨勢轉弱：週收 {close:.2f} < 季線 {ma13:.2f} 且季線下彎 → 暫停加碼")` |
| `src/compute/etf/dividend_station.py:630` | 加碼 | `return f"🟡 {a.light.icon} 訊號亮但季線轉弱 → 暫停加碼、先觀望"` |
| `src/compute/etf/dividend_station.py:632` | 加碼 | `return f"{a.light.icon} 加碼 {a.light.deploy_pct:.0f}%：{'、'.join(a.light.reasons)}{_dw}"` |
| `src/compute/etf/dividend_station.py:728` | 賣點 | `+ f" + KD 轉弱（{kd_label}）賣點確認{_bd}")` |
| `src/compute/etf/dividend_station.py:739` | 加碼 | `f"減碼觀察、勿加碼（趁 grade 未掉到 C 前）")` |
| `src/compute/etf/dividend_station.py:739` | 減碼 | `f"減碼觀察、勿加碼（趁 grade 未掉到 C 前）")` |
| `src/compute/etf/dividend_station.py:744` | 加碼 | `action = (f"🟡 財報佳（{mj_grade}）但 KD 短線轉弱（{kd_label}）→ 留意、暫不加碼{_ta}")` |
| `src/compute/etf/etf_calc.py:180` | 加碼 | `_action_hint = '觀察均線止跌；不加碼'` |
| `src/compute/etf/etf_helpers.py:225` | 減碼 | `return ('🟠', f'⚡短線 偏高(≥+{ETF_QUICK_SIGMA_HIGH:.1f}σ)', '不追高/減碼')` |
| `src/compute/etf/etf_helpers.py:260` | 買點 | `return (f'🟢 📅長線 極佳買點(≤ {ETF_SIGMA_DEEP_BUY:.0f}σ)', 'green',` |
| `src/compute/etf/etf_helpers.py:261` | 加碼 | `'大跌大買 — 大幅加碼，剩餘資金主力投入')` |
| `src/compute/etf/etf_helpers.py:263` | 買點 | `return (f'🟢 📅長線 進場買點({ETF_SIGMA_DEEP_BUY:.0f}σ ~ {ETF_SIGMA_BUY:.0f}σ)',` |
| `src/compute/etf/etf_helpers.py:272` | 加碼 | `f'建議減碼；勿在 +{ETF_SIGMA_STOP_PROFIT:.0f}σ 以上加碼')` |
| `src/compute/etf/etf_helpers.py:272` | 減碼 | `f'建議減碼；勿在 +{ETF_SIGMA_STOP_PROFIT:.0f}σ 以上加碼')` |
| `src/compute/etf/etf_recommendation.py:113` | 加碼 | `reasons.append('價位偏低,分批加碼時機較佳')` |
| `src/compute/etf/etf_recommendation.py:115` | 加碼 | `reasons.append('價位偏高,續抱可、暫緩加碼')` |
| `src/compute/etf/etf_scoring_helpers.py:97` | 減碼 | `_r['sigma_sell'] = round(float(_sb['upper_2s']), 2)  # +2σ 減碼` |
| `src/compute/etf/etf_smart_analysis.py:30` | 買點 | `'strong_buy':  ('強買點', '🟢🟢', '#16a085'),` |
| `src/compute/etf/etf_smart_analysis.py:34` | 減碼 | `'sell':        ('考慮減碼', '🔴',   '#e74c3c'),` |
| `src/compute/macro/macro_helpers.py:702` | 買點 | `f'→ ⭐ 通膨+利率雙頂回落，景氣多頭最佳買點（歷史勝率最高）'` |
| `src/compute/macro/macro_helpers.py:883` | 加碼 | `detail = '景氣由谷底回升 → 加碼基本面好的標的，留意通膨變化'` |
| `src/compute/notify/ai_judgment.py:84` | 賣點 | `2. 【絕對禁止】喊「一定買 / 保證賺 / 必漲 / 快進場」,也不給任何具體買賣點或目標價。` |
| `src/compute/notify/holdings_digest_message.py:127` | 逢低 | `_lines = ["➕ 235 逢低加碼觸發"]` |
| `src/compute/notify/holdings_digest_message.py:127` | 加碼 | `_lines = ["➕ 235 逢低加碼觸發"]` |
| `src/compute/notify/holdings_digest_message.py:130` | 加碼 | `f" 加碼{_code(d, '加碼金')}".rstrip())` |
| `src/compute/notify/weekly_review_prompt.py:55` | 賣點 | `2. 【絕對禁止】喊「一定買 / 保證賺 / 必漲 / 快進場」,也不給任何具體買賣點或目標價。` |
| `src/compute/risk/risk_radar.py:609` | 加碼 | `f"提高現金部位、停止加碼、衛星部位獲利了結"` |
| `src/compute/risk/risk_radar.py:633` | 加碼 | `f"維持持倉、暫緩單筆加碼，留意雷達是否升級至警報"` |
| `src/compute/risk/risk_radar.py:680` | 加碼 | `notes.append("估值底部分位（便宜），可逐步擇機加碼")` |
| `src/compute/risk/risk_radar.py:684` | 加碼 | `notes.append("重大事件臨近，暫緩單筆加碼")` |
| `src/compute/scoring/exit_signals.py:38` | 減碼 | `2: ('🟠', '建議減碼', '#f0883e'),` |
| `src/compute/strategy/pattern_targets.py:273` | 甜蜜價 | `notes.append("甜蜜價缺 neckline → sweet=None")` |
| `src/compute/strategy/pattern_targets.py:275` | 甜蜜價 | `notes.append(f"甜蜜價=頸線突破買點 sweet={sweet:g}")` |
| `src/compute/strategy/pattern_targets.py:275` | 買點 | `notes.append(f"甜蜜價=頸線突破買點 sweet={sweet:g}")` |
| `src/compute/strategy/v5_modules.py:256` | 買點 | `f"（量增 {vol_ratio:.1f}× 確認）— 短線爆發買點")` |
| `src/compute/strategy/v5_modules.py:263` | 買點 | `msg = f"BW={bw:.1f}% 且收盤 {close_now:.2f} 貼近上軌 {upper:.2f} — 短線爆發買點（量能未知）"` |
| `src/compute/strategy/v5_modules.py:373` | 減碼 | `f"估值過高，建議逢高減碼")` |

#### L1 data — 5 筆字串命中

| file:line | 詞 | 字串（截斷 120 字）|
|---|---|---|
| `src/data/core/data_registry.py:681` | 減碼 | `('跌破年線（240 日均）', '🟠 趨勢轉弱，外資對台股科技股減碼'),` |
| `src/data/core/data_registry.py:695` | 減碼 | `('殖利率 §§YIELD_LOW§§ ~ §§YIELD_MID§§%', '🟡 昂貴，適度減碼'),` |
| `src/data/core/data_registry.py:747` | 減碼 | `'downstream': '融資擴張 → 散戶進場 → 大戶通常開始減碼；急殺時融資斷頭加速跌勢',` |
| `src/data/macro/macro_core.py:600` | 逢低 | `if v > MACRO_THRESHOLDS['VIX']['red_above']: return ('⚫', '極端恐慌（逢低加碼訊號）', '#8b949e')` |
| `src/data/macro/macro_core.py:600` | 加碼 | `if v > MACRO_THRESHOLDS['VIX']['red_above']: return ('⚫', '極端恐慌（逢低加碼訊號）', '#8b949e')` |

#### L0 config — 1 筆字串命中

| file:line | 詞 | 字串（截斷 120 字）|
|---|---|---|
| `src/config/persona.py:11` | 逢低 | `1. 【拒絕券商官腔】：嚴禁使用「震盪整理、逢低承接、追價意願仍存、多空交錯」這類打太極的廢話。請給出明確的動作與情緒形容。` |

---

# 七、兩件特別查證（**我沒有先看別組結論，下面是我自己重跑的證據鏈**）

## (a) `CoreSatelliteManager.calc_position` 在 production 到底有沒有 caller？

**我的結論：沒有。0 production caller。**（與 §五 E1 同一份證據，此處只補「我怎麼查的」與「我為什麼相信」）

**查 caller 的方法（逐步，可複製貼上重跑）：**

```bash
cd /home/user/my-stock-dashboard
# 1) 不限副檔名的全域字串搜尋（不只 grep .py —— 免得漏掉 yml/json/md 裡的動態呼叫）
grep -rn "calc_position" . | grep -v '__pycache__' | grep -v '^\./\.git/'
# 2) 類別本身的所有出現點
grep -rn "CoreSatelliteManager" --include='*.py' . | grep -v '__pycache__'
# 3) 排除動態派遣
grep -rn "getattr(_mgr\|getattr(_m,\|getattr(_CSM" --include='*.py' src/ app.py
```

**結果：**

| 來源 | 命中 | 判定 |
|---|---|---|
| `src/compute/strategy/portfolio_manager.py:128` | 定義 | — |
| `tests/test_portfolio_manager_coverage.py`（7 處） | **測試** | 不算 production |
| `src/compute/risk/risk_control.py:309` + `tests/test_risk_control.py` | `calc_position_size` | **同名前綴、不同函式**，不是它 |
| `docs/DEAD_CODE_AUDIT.md:39` | 講 `calc_position_size` | 不是它 |
| **production `.py`** | **0** | ✅ |

**類別有沒有活著？有，但只用 property：**

| 檔案 | 用到什麼 |
|---|---|
| `src/ui/etf/etf_tab_portfolio.py:78,86-87`（`_regime_core_sat_text`） | `.core_ratio` / `.satellite_ratio` |
| `src/ui/etf/etf_tab_portfolio.py:758,763-764`（核心/衛星 gate） | `.core_ratio` |
| `src/ui/views/page_hold.py:178,2184`、`src/ui/render/station_cards.py:935` | **只是文字裡提到類別名**，而且語意是「⛔ 也**不會**改用 `CoreSatelliteManager`」 |

**動態呼叫也排除了**：`src/compute/strategy/__init__.py` 的 `__getattr__` 只掃 `vars(sub)`（模組層級名），
**方法名根本不在裡面**，barrel 到不了 `calc_position`；對 manager 實例也沒有任何 `getattr`。

**我不敢說的部分**：這是**單組窮舉**，而且我只排除了 `getattr` 型的動態呼叫，
沒有掃 `eval` / `exec` / `__getattribute__` 覆寫。要當「已查證事實」用，請派第二組獨立驗。

**對合規窗口的意涵**：`📊 建議買進 {shares} 股…` **現在不會出現在任何畫面上** → 本次**不必改**。
但它是一顆地雷（任何人接一行 `mgr.calc_position(...)` 就會上畫面），建議窗口外另案清掉。

---

## (b) `v5_modules.py` 357 估值的 `msg` 會不會透傳到畫面？

**我的結論：會。而且是**到 v2 新頁**（`🔬 查一檔`）—— v1 舊頁反而**不會**。**

### 完整路徑（逐跳，每一跳都附 file:line）

```
L2  src/compute/strategy/v5_modules.py:309  calc_dividend_yield_357(...)
      └─ 回傳 dict，其中 "msg" 在 :360 / :364 / :368 / :371 / :373-374 各有一種寫法
         ↓  production caller 只有 2 個（grep -rn "calc_dividend_yield_357"，排除 tests）
         │
         ├─【v1 舊頁】src/ui/tabs/stock_sections/section_health_score.py:412
         │     └─ 只讀 _dy5['color'] / ['est_yield'] / ['signal'][:12]  (:419-429)
         │        → ❌ msg **沒有**被讀 → **v1 不顯示**
         │
         └─【v2 新頁】src/ui/views/page_inspect.py:1300-1301  load_valuation()
               └─ :1319  msg=str(_z.get("msg") or "")        ← 存進 ValuationReadout.msg
                  └─ :1880-1883  if val.msg: _facts.append(("L2 說明", val.msg))
                     └─ :1889（UI_LIVE 分支）/ :1915（其餘狀態）把 tuple(_facts) 一起回傳
                        └─ :2272-2274 _render_one() → _ui_kit.render_card(..., facts=_facts)
                           └─ src/ui/views/_ui_kit.py:294-295
                                for _k, _v in facts:  st.caption(f"{_k}　{_v}")   ← **上畫面**
               （另一條）:1909  UI_EMPTY 時 scrub_state_glyphs(val.msg)[0] → Note.why → render_note()
```

### 最終顯示在哪一頁

- **頁**：側欄 radio「🆕 新版戰情室（試用中）」→ 選 **「🔬 查一檔」**
  （`app.py:315-318` radio → `app.py:551-553` `_ia_view_inspect()` → `render_page_inspect()`；
  頁名 SSOT 在 `shared/ia_nav.py:51` `PAGE_INSPECT: "🔬 查一檔"`）
- **區塊**：葉1 單檔診斷 → 判決卡「**估值（357 評價）**」
- **位置**：卡片下方的 `facts` 清單，欄位名寫死為「**L2 說明**」，值＝L2 的 `msg` 原文
  （`page_inspect.py:1882` 註解自陳「**原樣透傳**：那是 L2 的話，本檔不改寫、不摘要」）

### `msg` 的五種內容，含哪些價位字眼（逐字抄自 `v5_modules.py:358-374`）

| zone_code | 條件 | `msg` 原文 | 含什麼價位/動作字眼 |
|---|---|---|---|
| `cheap` + stable | 殖利率 ≥ 7% 且近 5 年年年配 | `殖利率 {x}% ≥ 7%（便宜價 {p_cheap}）且{_yr_txt} — 策略1 存股首選` | **「便宜價 + 一個具體數字」**、**「存股首選」**（＝推薦語氣） |
| `cheap` | 殖利率 ≥ 7%，穩定性未知 | `殖利率 {x}% ≥ 7%（便宜價 {p_cheap}），但{_yr_txt}，需確認配息穩定性` | **「便宜價 + 具體數字」** |
| `fair` | 5%~7% | `殖利率 {x}%，位於合理區間（{p_cheap}~{p_fair}），可分批布局` | **兩個具體價位**、**「可分批布局」**（＝進場動作建議） |
| `dear` | 3%~5% | `殖利率 {x}%，位於昂貴區（{p_fair}~{p_expensive}），持有但不追高` | **兩個具體價位**、**「持有但不追高」**（＝持倉動作建議） |
| `overpriced` | < 3% | `殖利率僅 {x}%（現價已高於昂貴價 {p_expensive}），估值過高，建議逢高減碼` | **「昂貴價 + 具體數字」**、**「建議逢高減碼」**（＝**直接的減碼建議**） |
| `na` | 缺股價或缺配息 | `{無股價\|無配息記錄}，357 殖利率法則不適用（不以 0% 代替，避免誤判為超貴）` | 無 |

**關於「六大禁用詞」的判定**：
這五句**一個都不含**「建議買進／立即出清／應該加碼／推薦／必漲／目標價」——
所以它**沒有出現在本報告的【A】主清單裡**（主清單嚴格照六個詞掃）。
但 `建議逢高減碼`（`v5_modules.py:373`）命中疑似詞 **`減碼`**，
而且從母法「全站不產生任何直接買賣建議」的角度看，**這一句是本次掃描裡語氣最直接的一筆**。

**⚠️ 但它落在合規窗口之外的邊界上，請注意**：
`v5_modules.py` 是 **L2 純計算層**，該 `msg` 是**函式回傳值**，不是 UI 字串。
改它算不算「只改使用者看得到的文字」？
- **支持算**：它唯一的 production 消費者就是畫面（v1 不讀它，v2 原樣印出），改字不動任何數字與分支。
- **反對算**：它是 L2 的**回傳值**，改 L2 回傳值在本 repo 的分層紀律下通常要走 §8 流程。

⚠️ **而且它有測試釘住（我一開始寫錯，這裡是更正後的實測結果）**：
`tests/test_b1b_stock_math.py:375` 有一條
`assert "未知" in r["msg"], f"配息年數未知時不得宣稱穩定或不穩定：{r['msg']}"`
——**`msg` 的字面**是被 assert 的。逐分支影響如下（實測，仍屬單組）：

| `v5_modules.py` 行 | 片段 | 有無測試釘住 | 改動風險 |
|---|---|---|---|
| :360 | `— 策略1 存股首選` | ❌ 無 | 可改 |
| :360 / :363 | `{_yr_txt}`（＝「配息年數未知」／「近5年配息 N 年」） | ✅ **`test_b1b_stock_math.py:375` 釘「未知」二字** | **不得移除**，改寫需保留「未知」 |
| :366 | `可分批布局` | ❌ 無 | 可改 |
| :369 | `持有但不追高` | ❌ 無 | 可改 |
| :373 | `建議逢高減碼` | ❌ 無 | 可改 |
| :347 | `357 殖利率法則不適用（不以 0% 代替…）` | ❌ 無（`na` 分支只被 assert `zero_...` 類欄位） | 可改 |

（旁證：本 repo 有**大量**對 L2 `msg` 字面的 assert ——
`test_v4_strategy_engine_coverage.py:161,170,180,262,315`、`test_b2a_breach_and_naming.py:131-170`、
`test_review_fixes_v19_95.py:42-56` 等。**動任何 L2 的 `msg` 之前都要先 grep 測試**，
不能沿用「UI 字串沒人釘」的直覺。）

**我的建議（附推薦方案）**：這一筆**不要**塞進 v1 合規窗口，**單獨列一條**問客戶要不要一起改；
若要改，最小破壞作法是**只改 v5_modules.py 那 5 個 msg 的措辭**（不動 zone_code、不動 targets、不動 signal、
**保留 `{_yr_txt}` 原樣**），例如 `建議逢高減碼` → `目前落在昂貴區`、`可分批布局` → `位於合理區間`、
`— 策略1 存股首選` → `— 符合 7% 門檻`。

---

# 八、我沒查到的 / 不確定的

1. **「主清單只有這 10 處【A】」是甲組單組窮舉，未經第二組複驗。**
   §-2 規則 6 之下只能當待驗事項。前例：本 repo `CLAUDE.md §-1.5.C` 記載過一次
   「單組掃出的全稱句被獨立稽核否證、另查出三處」——請據此打折信任本報告。

2. ⭐ **最大盲點：純字串比對抓不到同義違規句。**
   母法禁的是「直接買賣建議」，但派工給的是 **6 個具體詞**。實測存在大量**語氣相同、用詞不同**的句子，
   本次掃描**結構上掃不到**，例如：
   - `src/ui/etf/etf_tab_single.py:435-436` `'🟢 <b>強烈買進（特價）</b>:殖利率 ≥ 7%,現值低估,值得分批佈局'`
   - `src/ui/etf/etf_tab_single.py:518` `_prem_action = '🟢 強烈買進時機'`
   - `src/ui/etf/etf_tab_grp_compare.py:249` `help='…殖利率≥7%🟢強烈買進 / …🔴獲利了結'`
   - `src/data/core/data_registry.py:693` `'🟢 便宜價／強烈買進（357 殖利率估值法則）'`
   - `shared/thresholds.py:59` `return '🟢 強烈買進', 'strong_buy'`（**L0 SSOT，多處共用**）
   - `src/compute/etf/etf_smart_analysis.py:30` `'strong_buy': ('強買點', …)`
   **「強烈買進」在語意上等同「建議買進」，卻一個禁用詞都不含。**
   → 建議另派一組做**語意面**（而非關鍵字面）掃描；我這一組的輸出**不足以支撐「全站已無直接買賣建議」**。

3. **疑似區 178 筆 `STRING` 我沒有逐一追渲染路徑。**
   只對主清單的 19 筆 `STRING` 做了 caller/渲染追蹤。疑似區的分類只到 token 層級
   （STRING vs COMMENT vs DOCSTRING），**不等於「這 178 筆都會上畫面」** ——
   其中至少包含 LLM prompt（`persona.py:11`、`app_ai_service.py:298,322,329`、
   `dividend_station_service.py:1002,1006`、`rs_leader_service.py:357`）與
   2 條反向禁止句（`ai_judgment.py:84`、`weekly_review_prompt.py:55`）。

4. **掃描範圍就是派工給的範圍**：`app.py` + `src/**/*.py`，**排除 `tests/`**。
   **沒掃**（但確認有命中的）：`shared/`（2 檔 3 行，其中 `scoring_regime_gate.py:137` **確實上畫面**，已補在 §一之補）。
   **完全沒掃**：`scripts/`、`infra/`、`mcp_server/`、`tools/`（我只對六大詞跑了一次 grep：**0 命中**，
   但**沒有**跑疑似詞）、`docs/wireframes/*.html`（六大詞 0 命中）、`*.md`、`*.json`。

5. **`src/ui/pages/**` 不在派工給的 v1/v2 兩個 bucket 裡。**
   A10（`api_diagnostic.py`）我依「掛在舊 7 頁籤底下（`app.py:1091`）」判為 **v1**，
   但這是我自己的歸類決定，不是派工規格明講的。

6. **`src/ui/render/**` 被派工歸為「v2 新頁」，但實際上它同時服務 v1。**
   例：`etf_render.py` / `ui_widgets.py` / `macro_ui_components.py` 是舊 ETF/總經頁在用的 L4；
   只有 `station_cards.py` 是 v2 `page_hold` 專用。疑似區表格我照派工定義分組，
   **但請注意這個 bucket 在本 repo 是混的**，動它可能同時影響 v1 與 v2。

7. **【E】兩筆死碼判定只排除了 `getattr` 型動態呼叫**，沒有掃 `eval` / `exec` / `__getattribute__` 覆寫。

8. **「沒有測試釘住我標【A】的那些字串」是單組 grep 結論 —— 而且這個直覺只對【A】成立。**
   - **【A】主清單（A1~A10）**：實測 `grep -rn "型態目標價\|甜蜜價\|Streamlit Cloud 推薦" tests/`
     只命中 `test_pattern_targets_ui_mounted.py` 的 **docstring 與 assert 訊息**
     （assert 本體檢查的是 `render_pattern_targets_for_ticker` / `cs_stk` / `cs_grp` 這些**符號名**，
     不是顯示字串），以及 `test_pattern_targets.py` 的**註解**。
     → A1~A10 的改字**應該**不會讓現有測試轉紅；單組結論，動手後請實跑 `pytest`。
   - ⚠️ **但 L2 的 `msg` 回傳值有一堆測試釘住字面**（我第一版報告把這點寫錯，已在 §七 (b) 更正）：
     `test_b1b_stock_math.py:375`、`test_v4_strategy_engine_coverage.py:161,163,170,180,262,315`、
     `test_b2a_breach_and_naming.py:131,133,139,147,170`、`test_review_fixes_v19_95.py:42,49,56`。
     **凡是要改 L2 回傳字串的，都必須先 grep 測試**，不能套用「UI 字串沒人釘」的經驗。

9. **我沒有實際跑起 Streamlit 看畫面。** 所有「畫面位置」都是**讀 code 推出來的**
   （追 `st.tabs` 結構 + `st.radio` 掛載 + 各 section 的 render 函式），
   不是實機截圖驗證。`api_diagnostic.py:144`（A10）藏在 expander + checkbox gate 後面，
   一般使用者未必看得到——但它**確實會渲染**。
