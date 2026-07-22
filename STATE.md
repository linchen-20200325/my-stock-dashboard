# 重構狀態看板(深層拔毒 v18.369+)

## 📈 2026-07-21 全台股跨季趨勢 A-1:L1 全季 loader + L2 趨勢計算（v19.139,user 選「A+B」,A 先）

user 要「全台股跨季大規模掃描」→ 拆 A(基本面跨季,便宜)+ B(價格快照,大工程),分批。A-1 為兩種呈現(選股網因子 / 獨立排行)共用的地基。

- **§1 誠實資料限制**:現有快照僅 5 季(114Q1–115Q1)、無 113 前 → **不做「連續成長季數」**(5 季 + QoQ 季節性會造假訊號),改用**比率型線性斜率**(對季節性穩健);營收 YoY 只算最新季 vs 去年同季一個點。
- **L1**:`fundamentals_snapshot_loader.load_all_fundamentals_quarters()` — glob 讀全部季 parquet → long-form(每檔每季一列,含 roc_year/season);無快照 raise(§1)。@st.cache_data TTL_1DAY(EX-CACHE-1)。
- **L2**:`src/compute/screener/cross_quarter_trends.compute_cross_quarter_trends()` 純函式 — 每檔算 4 因子:毛利率斜率(>0佳)/營益率斜率(>0佳)/負債比斜率(<0佳)/營收YoY(>0佳)+ favorable_count(0-4)+ favorable_of(有資料因子數)。斜率有效點 <`CROSS_QUARTER_MIN_POINTS`(3,SSOT)→ NaN 不硬配;除零/缺去年同季 → NaN 不 silent 0;季序 ordinal 間距感知(處理缺季)。
- **實測(repo 內 5 季)**:9810 列 / 1970 檔全跑出;favorable_count 分布 0:188 / 1:523 / 2:424 / 3:502 / 4:333;YoY 1886/1970 有值。頂部標的呈「毛利升+營益升+負債降+營收增」改善型特徵,符合預期。
- **零新依賴**;`tests/test_cross_quarter_trends.py` **9 passed**(方向正確/排序/季數不足NaN/缺YoY/除零/空+缺欄/同季去重/**真實 parquet smoke**);ruff 淨;L2 純度掃描過。
- **下一步**:A-2 接線(選股網因子 + 獨立排行,版位待與 user 對齊)→ B-0 價格快照可行性探針 → B-1 建 cron。

## 🎚️ 2026-07-21 風險貢獻分解擴至個股組合 + render 抽 L4 共用（v19.138,user 選「第一點」）

v19.137 ETF 組合上線後,user 要「個股組合也補」。查證個股組合頁(`tab_stock_grp`)是「比較×排行」工具、非持股權重組合 → 給 user 三選項,user 選**第一點**:那頁新增「輸入持股張數」再算風險貢獻。

- **DRY 重構**:把 v19.137 ETF 頁 inline 的 render 抽成 L4 `src/ui/render/risk_contribution_render.py:render_risk_contribution_panel(result, *, warn_box, show_header)`,ETF/個股兩頁共用單一面板。ETF 頁改用它(以 `warn_box=_colored_box` 保留原紅框樣式,零視覺位移)。
- **個股組合接線**:`tab_stock_grp._render_risk_contribution_section(stock_list)` — expander 內 `st.data_editor`(代碼唯讀 + 持有張數)→ 按「算風險貢獻」才抓價(button-gated,不拖慢頁面)→ 每檔 `fetch_stock_history_1y` 取 1y 收盤 → 市值 = 張數×1000×現價、日報酬 = pct_change → 同 L2 `compute_risk_contribution` → 同 L4 面板。
- **§1**:抓不到價格的檔剔除並列出(不灌 0);權重 scale-free(×1000 對所有檔一致,正規化後不影響)。**§8.2**:L4 render 用 streamlit 合規;L5→L1 `fetch_stock_history_1y` 為 pass-through(L1 內已 @st.cache_data),**已登錄 EX-PASSTHRU-1**(CLAUDE.md + 檔內註解 + 本 PR 描述三處齊)。
- **零新依賴**。**回歸網**:`tests/test_risk_contribution.py` 新增 slow AppTest `TestRiskContribPanelRender`(合成資料→真 L2 結果→渲染 L4 面板不炸、表格有出、集中警示走 st.error)。全檔 16 fast + 1 slow 全綠;ruff 淨;三 UI 模組 import OK。

## 🎚️ 2026-07-21 ETF 組合新增「風險貢獻分解」（v19.137,user 核准 §7/§8 對齊後動工）

user 看了 PyPortfolioOpt 後問「有值得學的嗎」→ 我判定 library 本身不值得引入(重依賴 cvxpy/scipy/sklearn + 均值變異數「假精準」牴觸 §1),但其中一個概念 **Risk Contribution(風險貢獻分解)** 值得 —— 描述性、又輕又穩、貼合「描述現有持股」方向。user 核准「開工」,§7 計算式 + §8 架構皆先對齊。

- **它回答什麼**:某檔市值只佔 40%,卻可能扛了 60% 組合波動 → 揭露「分散效果被高估、風險其實壓在哪幾檔」。
- **數學(§7 對齊)**:σ_p = √(wᵀΣw);RC_i = w_i·(Σw)_i/σ_p;PRC_i = RC_i/σ_p。**只用 Σw、不需反矩陣** → 數值穩定,無 PyPortfolioOpt 均值變異數的病態問題。§4.3 對帳:Σ RC_i 必 = σ_p(不符則 raise,非 assert 以免 -O 剝除)。
- **§1 誠實邊界**:缺價歷史的持股 → **剔除並記市值%(不灌 0)**;重疊觀測 <60 日 → low_confidence 旗標仍算但標低可信度;組合零波動 → 回 note 不硬除;權重未正規化 → 內部正規化(scale-free)。
- **架構(§8.2 全合規)**:
  - L0 `shared/risk_contribution_thresholds.py`(RC_MIN_OVERLAP_DAYS=60 / RC_CONCENTRATION_GAP_PCT=10;年化 252 重用 signal_thresholds.TRADING_DAYS_PER_YEAR,不重造)。
  - L2 `src/compute/risk/risk_contribution.py` 純函式(零 I/O / 零 streamlit;`compute_risk_contribution(returns, weights)` → `RiskContributionResult`;註冊進 risk/__init__ lazy __getattr__)。
  - L5 `etf_tab_portfolio.py` 接線:插在「相關係數矩陣」段後(同源 `ret_dict` 日報酬),渲染「市值% vs 風險%」表 + 風險集中紅框警示。L5→L2 下行依賴合規,無新增 L1 直呼。
- **零新依賴**(純 numpy/pandas)。**範圍**:先做 ETF 組合(資料路徑現成);個股組合為後續。
- **回歸網**:`tests/test_risk_contribution.py` 16 test —— Euler 加總100 / 等vol等權50-50 / 高vol風險放大+集中警示 / 單檔100% / 缺價剔除不灌0 / 樣本不足旗標 / 零波動note / scale-free / 相關資產Euler對帳不raise / property(任意權重vol恆加總100且非負)。全綠;ruff 淨;L2 純度掃描過。

## 📝 2026-07-20 CLAUDE.md §3.2 校正 v19.136 — 三大法人 outlier wiring 過時註記(user 核准 SSOT)

v19.135 已把 inst outlier helper wire 進 `section_chips_20d`,但 CLAUDE.md §3.2 該行仍寫
「wiring 待真實 consumer(現無 fetcher 同時持 inst_net+30D 均量,不強接)」— 已過時且前提被推翻
(consumer 端 df2 本就同時持 主力合計+volume)。校正為「helper + wiring 皆已落地(v19.135,
`flag_latest_inst_outlier_from_df` + section_chips_20d 徽章),30 測試」。純憲法文件校正,無 code 改動。

## 🚩 2026-07-18 三大法人單日爆量旗標 wiring v19.135 — 補上做一半的判斷訊號(user 核准)

user「未完成項目」查證後點名開工(項1)。`src/compute/risk/inst_sanity.py` 的 helper
`is_inst_net_outlier`(|三大法人單日淨買賣超| > 30D 均量 × 5 → 異常)早於 v18.299 落地
(15 測 + SSOT `INST_NET_OUTLIER_VOLUME_RATIO=5.0`),但 **0 production caller** — CLAUDE.md §3.2
記「wiring 待真實 consumer(現無 fetcher 同時持 inst_net+30D 均量)」。
- **盤點推翻舊前提**:consumer 端 `df2`(data_loader `_get_combined_data_cached` 回傳)**本就同時**
  握有 `主力合計`(外資+投信+自營,單日淨買賣超,**張**)+ `volume`(**張**),同日期軸。
  兩者**同為張** → `ratio = |inst_net| / 30D均量` **無量綱、免換價**(§4.1)。
- **§8.1 核准後動工(user 選:主力合計加總 + 嚴格滿 30 日)**:
  - **L2 adapter** `flag_latest_inst_outlier_from_df(df)`(inst_sanity.py):取最新一日主力合計 +
    算 30 日均量 → 呼既有 helper。計算落 L2,UI 不寫算式。
  - **L5 wiring**:`src/ui/tabs/stock_sections/section_chips_20d.py` signal banner 後,
    outlier 時顯示「⚠️ 三大法人單日爆量 N× 30日均量」徽章(重用檔內既有色值,無新 magic)。
- **§4.6 / §1 降級**:不足 30 日(新上市)/ window 內 NaN 量 → `vol_unavailable` **不誤報**;
  最新日主力合計 NaN → `inst_net_zero`(不用舊值冒充);缺欄/空 df → fail-soft 不炸 UI、不顯示徽章。
- **測試**:新增 `test_inst_outlier_wiring_v19_135`(15:正常判定/賣超絕對值/golden/自訂門檻/降級×7/
  單位無量綱 property/SSOT 門檻 + UI wiring source-scan)。既有 inst_sanity 15 測不動;全庫 3337 collect 無 error。
- **範疇自評(§8.1 step6)**:只做「最新一日單點徽章」;`flag_inst_net_outliers_batch`(整條序列標記)
  **先不接**,等真有歷史 outlier 圖標需求再用。不動 L1 data_loader 預算均量欄(避免改全 caller)。

## ⚡ 2026-07-18 AI 財報體檢 v19.134 — 改按鈕 opt-in(省 API + 加速,user 核准)

user 批次4。`src/ui/tabs/tab_stock.py`「🔬 AI 財報體檢（策略2）」原本一進到某檔股票、
expander 首次 render 就**自動**呼叫 `analyze_financial_health`(Gemini)。有 session 快取
(每檔一次)但無按鈕 gate → 首屏慢 + 每檔耗 API 額度。
- **改按鈕 opt-in**:未按過本檔 → 顯示「🔬 生成 AI 財報體檢」按鈕 + info,不打 AI;點按鈕
  設 `session_state[f'_fh_req_{sid}']` + rerun → 才跑 fetch + Gemini。已生成(session 有結果)
  直接顯示。用 `_fh_req_` flag 避免重排既有 compute/render 大區塊縮排(安全 diff)。
- **`_fh is None` 分支**:原「載入中...」st.error 改 `pass`(尚未生成不誤報錯)。
- **section_strategy_conclusion `_cost` 不動(§-1 查證)**:`compute_one_stock_trend` 的 AI 是
  **snapshot-gated**(`if yyyymm_curr not in yms:` 才打,once/股/月 + `save_snapshot` 持久化),
  已攤銷,非每次 render 自動觸發,gate 反而破壞 MJ trend bootstrap → 不動。
- **「刪 3 死 screener」撤回**:yield_screener / monthly_revenue_screener 皆有 caller,非死碼。
- **test**:`test_ai_financial_health_gate`(按鈕在 AI 呼叫前)2 passed。§8.1 user 核准。

## 🐞 2026-07-18 出口 YoY v19.133 — GOV-MOF CKAN 泛用 CSV 補 sort(數據正確)

user 批次3 資料穩健。`src/data/macro/macro_snapshot.py:fetch_export_block` 的 **GOV-MOF CKAN**
深層 fallback(方案在 customs-direct + catalog + FRED-API + FRED-CSV 全敗後才走)用泛用
`read_csv` + 欄位比對取 `iloc[-1]/[-13]` 算 YoY,但**未 sort**。CKAN 列序不保證(常降序)→
iloc[-1] 取到最舊列 → YoY 算反(§1 錯值比沒值更糟)。line 979 註解早點名此 pattern,customs
路徑已改走 `_parse_customs_export_csv` 純函式處理,此泛用 fallback 漏網。
- **修**:`_df_ex.dropna(subset=[_val_k]).sort_values(_dt_k)`(對照 line 896 FRED-API 路徑已 sort)。
  MOF「年月」為 YYYYMM,數值/字典序=時序。加 `test_gov_mof_ckan_sorts_before_iloc` 迴歸鎖。
- **同批次查證後略過(§-1,非真 bug)**:
  - **CBC ms1.json YoY**(股 `tw_macro._try_cbc_ms1` + 基金 `tw_macro_repository` 同構)未 sort —
    但 CBC ms1 列序**未證實降序**(若降序,M1B/M2 YoY 會嚴重算反,macro 看板天天看必被發現,
    未報 = 大概率升序);且函式未取日期欄,加 sort 需先可靠識別日期欄,誤判反致 mis-sort。
    CBC 亦 M1B/M2 同期發布,獨立 dropna 無實際錯位。**不投機修**。
  - **基金 FX 負快取**(`fx_and_main.py`):已是 v18.275 **positive-only cache**(None 不入 cache
    → 下次重試,避免 poisoning),本就正確設計,無需改。
  - **VIX 重複抓**:多 consumer 走 `fetch_yf_close('^VIX',...)` 同 arg 共用 `@_ttl_cache`,已去重;
    殘留跨 wrapper 差異僅 1 ticker 冷啟一次,dedup 需跨模組重構,ROI 低。

## ⚡ 2026-07-18 產業熱力圖 v19.132 — opt-in 載入(下載速度)

user 批次2 localized。`src/ui/render/etf_render.py:render_sector_heatmap` 位於
`tab_market → 產業熱力圖` 巢狀 tab;Streamlit 全 tab body 每次 app run 都執行 → 數十檔類股
batch(美股 GICS 11 大類 + 子成分 ~66 檔 / 台股類股)在**首屏就冷抓**,即使 user 當下在別的 tab。
- **opt-in gate**:未點過 → 只顯示「🗺️ 載入產業熱力圖」按鈕 + early return(不冷抓);點過後
  `session_state['heatmap_loaded']=True` 記住,之後走 `get_sector_returns` 的 `@st.cache_data`
  快取即時回。改市場/區間仍依新 cache key 重抓;🔄 刷新視同載入。
- **不破壞既有**:selectbox/refresh/treemap/AI 全不變;`get_sector_returns(refresh=)` 介面不變。
  加 `test_etf_render_heatmap_gate`(gate 必在取數前)迴歸鎖。
- **triage 略過(§-1 查證後非真 bug)**:強制刷新 `cache_data.clear()`(help 明寫「清除所有快取」=
  刻意全刷,慢是預期)、`fetch_etf_price` period='max'(v18.228 跨 tab 去重設計,一次 API sliced
  記憶體)、教學 3 檔 FRED sparkline(已 `@st.cache_data(1day)`,冷成本極小)。

## ⚡ 2026-07-18 ETF 分散度分析 v19.131 — 按鈕 gate + 並行持股(下載速度)

user「聽你的建議 都修吧」批次2 大贏面①。`src/ui/etf/etf_tab_smart.py:render_correlation_finder`
是 ETF「單檔診斷 / 組合」頁最重的區塊:一設定標的就**自動**冷抓 ~30 檔 ETF 價格 batch +
**31 檔持股序列迴圈**(首次 10-20 秒),且每次進頁 / 任一 widget 互動都重跑(cache 之外的冷啟動很痛)。
- **按鈕 opt-in + 依標的記憶**:未按過本標的 → 只顯示按鈕不冷抓;按 `st.button('🔗 計算分散度')`
  後 `session_state[f'_corr_ran{key_suffix}']=_ticker` 記住,之後 rerun 走 `@st.cache_data` 快取即時回。
  換標的需重按(避免顯示舊標的結果)。對照同檔 `render_333_section` 既有 `_run_peer` gate 慣例。
- **並行持股**:31 檔序列 `for` 迴圈 → `ThreadPoolExecutor(max_workers=8)` `.map`,每檔各自
  try/except 容錯(單一 ETF 持股異常 → `set()` 略過不拖垮整區塊)。`_cached_holdings` 為
  `@st.cache_data` 純資料函式(內部無 st.* UI 呼叫),worker thread 呼叫安全;spinner 留主緒。
- **不破壞既有**:universe / `_cached_peer_prices` / `find_diversifiers_by_category` / `_normalize(ticker)`
  全不變;函式簽名不變(wiring test 4 passed)。加 `test_correlation_finder_gated_and_parallel`
  迴歸鎖(按鈕 gate + session 記憶 + ThreadPool + 容錯)。§8.1 user 核准「全做大贏面優先」,單檔 L5 UI。

## 🐞 2026-07-18 ETF 分類 v19.130 — 修槓桿/反向 ETF 被誤判成主動式(判斷正確)

user「聽你的建議 都修吧」批次1 第①項。稽核發現 `src/data/etf/etf_fetch.py:is_active_etf`
被動後綴排除集**誤寫 `('B','K')`**:
- **台股根本無 'K' 後綴** — 排除一個不存在的類別 = 空轉。
- **漏掉 L(槓桿正2)/R(反向反1)/U,F(期貨)** — 這些代號末位為字母,直接掉進
  `if _last.isalpha(): return True` 分支 → **00631L(元大台灣50正2)、00632R(元大台灣50反1)
  等被誤判成「主動式 ETF」** → 觸發錯誤的主動式弱勢判定 + 無謂打 Yuanta 官網抓經理人。
- **修正**:排除集改 `('B', 'L', 'R', 'U', 'F')`,docstring 優先序同步更正。純數字(0050/
  00878)與白名單(A/D/T)行為不變。**純單檔 bug fix,不觸發 §8**(單一函式、無新模組/資料流)。
- **golden test**:`tests/test_active_etf_fallback.py` 加 8 測(00631L/00675L/00632R/00676R→被動、
  00679B/00687B 債券→被動、00642U/00635U 期貨→被動、00980A/00982T/00980D 白名單→主動、
  00999A 非白名單 A 後綴 fallback→主動、純數字→被動、空/None→False)。16 passed。

## 🧬 2026-07-15 AI 問答 v19.129 — 加單檔 ETF 品質工具(user 核准)

user 部署後問「ETF 哪個比較好」,agent 無 ETF 工具 → 誠實回「無比較功能」(Fail-Loud 正確
但不夠用)。user AskUserQuestion 選「加單檔 ETF 品質工具」。§7/§8.1 對齊後(Explore agent
盤 `compute_etf_quality` 簽名 + 資料流)實作:
- **§7**:包 L2 `src.compute.etf.compute_etf_quality(ticker)`(自抓 L1:AUM/費用率/配息CV/beta),
  回 `stars`(1-5)/`score`([0,1])/`weakest`/`coverage`/`factors`。**不新增公式**,沿用既有評分。
- **§8**:L3 單一新工具 `_tool_get_etf_quality`(同 `_tool_get_stock_score` lazy-import L2 模式),
  註冊 REAL_TOOLS + TOOLS_SCHEMA。AI 比較多檔時每檔各呼叫一次。不新增模組/資料流。
- **邊界**:代碼先 `normalize_etf_ticker`(0050→0050.TW);查不到/4因子全缺 → `stars=None` →
  工具 **Fail-Loud** `ok:False`(§1 不假裝有分數);無單一 as_of → 不套過期標記;涵蓋率<1 surface
  給 AI 提醒。
- **test**:`test_etf_quality_tool_registered` + `test_etf_quality_tool_ok_fail_invalid`(monkeypatch
  避免真打 yfinance:成功 mapped / stars=None Fail-Loud / 代碼無效);真 import 路徑冒煙驗證
  (normalize 0050→0050.TW、invalid id Fail-Loud)。19 passed、selftest、py_compile 過。
  隔離於 `ai_qa_service.py`(L3)單檔。

## 🔐 2026-07-15 AI 問答 v19.128 — 修錯誤訊息洩漏 Gemini API 金鑰 + 429 友善化

user 部署後截圖回饋:問 ETF 時觸發 `429 Too Many Requests`,錯誤訊息把**完整 URL 含
`?key=AIza…`(Gemini API 金鑰)印到畫面**。
- 🔴 **真漏洞(安全)**:`run_agent` / `discuss` 的 except 直接 `f"Gemini…:{e}"`,而 requests
  的 `HTTPError` str 內含完整請求 URL(含 `?key=<GEMINI_KEY>`)→ 金鑰渲染到 UI(截圖/公開
  部署即外洩)。**修**:新增 `_scrub_secrets`(洗 URL query `key=/token=/api_key=` 值 + 裸露
  `AIza…` 樣式)+ `_fmt_gemini_error`(先洗白再判 429),套用 4 處 UI-facing 錯誤字串
  (run_agent / discuss lite / discuss full / _run_tool 工具錯誤 defense-in-depth)。
- 🎯 **429 友善化**:偵測 `429 / Too Many Requests / RESOURCE_EXHAUSTED` → 「已達 Gemini
  免費額度上限,請稍候約 30~60 秒再試」,不丟原始 HTTPError。
- **test**:`test_scrub_secrets_removes_api_key` + `test_run_agent_429_scrubs_key_and_friendly`
  (複現:429 HTTPError URL 含 key → 修前整串含金鑰洩漏;修後金鑰不出現 + 友善提示)+
  `test_fmt_gemini_error_non_429_scrubbed`;17 passed、selftest、py_compile 過。純 bug fix
  (§8 不觸發),隔離於 `ai_qa_service.py`(L3)。
- ⚠️ **金鑰已曝光**:user 該截圖已把當前金鑰外洩 → 已請 user 至 Google AI Studio 重新產生。
- 📌 **ETF 比較**(截圖另一問題):agent 目前無 ETF 工具,誠實回「無比較功能」(Fail-Loud 正確)。
  加 ETF 工具屬**新功能**,§7/§8.1 需先對齊(範圍/比較指標)→ 待 user 點名再設計,本 PR 不含。

## 🧬 2026-07-15 AI 問答 v19.127 — 修季報「已過期100+天」誤報(頻率感知過期門檻)

user 部署後回饋:個股問答財報「看起來尚未更新」(力積電 6770 顯示 as_of=2026-03-31、
「已過期106天,請留意時效性」)。**查證 = 誤報,非真過期**:
- `_annotate_staleness`(`ai_qa_service.py`)對**所有**工具結果套同一條 `age > 7d` **日頻**門檻;
  但 `get_financial_health` 的 `as_of` 是**季末日**(3/31),台股季報**季末後~45d 才公告**,
  下一季(Q2,as_of 6/30)要~8/14 才出 → 7/15 這天 Q1 就是「當期最新一季」,資料抓取正常。
- 拿日頻新鮮度標準套季頻 → 當期最新一季被誤標過期,誤導 user 以為沒更新。
- **修(頻率感知門檻)**:`shared/staleness.py`(SSOT)加 `STALE_DAYS_DAILY=7 / MONTHLY=45 /
  QUARTERLY=150` + `stale_days_threshold(cadence)`;季頻門檻數學 = 一季(91d)+公告延遲(~45d)+
  FinMind鏡像寬限(~14d)=150d(Q1 as_of age 在下季公告前最舊~136d)。`_annotate_staleness` 改讀
  provenance `cadence` 取門檻;`_tool_get_financial_health` provenance 標 `cadence="quarterly"`。
  日頻工具維持 7d(未宣告 cadence → default daily,§1 不放水)。
- **邊界**:力積電 106d < 150d → 不標過期 ✓;若 9 月還停在 Q1(>150d,Q2 早該出)→ 正確標過期 ✓。
- **test**:`test_staleness.py` +5(門檻表)、`test_ai_qa_service.py` +3(季報 106d 不標 / 200d 標 /
  日頻 10d 仍標);**revert 實測 106d 在舊 age>7 邏輯會誤標 → 測有效**。42 passed、selftest、py_compile 過。
  變更隔離於 `shared/staleness.py`(L0 加常數)+ `ai_qa_service.py`(L3),純 bug fix(§8 不觸發)。

## 🧬 2026-07-15 AI 問答 v19.126 — 修「6239→62396239」問題重複送 + 空標題

user 部署後回饋兩個畫面 bug:
- 🔴 **真 bug**:輸入股票代碼「6239」→ AI 收到「62396239」(整串重複)。根因在 UI 層
  `tab_ai_chat.render()`:先把 `q` **append 進 `ai_qa_history`**,再把**同一個 list** 傳給
  `run_agent(q, st.session_state.ai_qa_history)`;而 `run_agent` 內部本來就會再接一次
  (`contents = _history_to_contents(history) + [question]`)→ Gemini 收到連續兩個相同 user turn,
  串成「62396239」。**修**:append 前先 `_prior = list(...)` 快照,傳快照給 `run_agent`,q 只由
  run_agent 接一次;可見歷史仍照常 append(下次 rerun 正常顯示)。
- 🎯 **空的「🧬 AI 解讀」裸標題**:`res.text` 為空時 body 只剩標題。**修**:空文字改顯式回報
  「AI 已完成工具查詢,但未產生文字解讀;請見上方工具結果」,不留裸標題。
- **test**:新增 `test_run_agent_question_sent_once` 釘契約(給乾淨歷史時本次問題只送一次 +
  歷史保留);golden **11 passed**、selftest 6/6、py_compile 過。變更隔離於 `tab_ai_chat.py`(L5)
  單檔邏輯 + `test_ai_qa_service.py`(純 bug fix,§8 不觸發架構對齊)。

## 🧬 2026-07-15 AI 問答 v19.125 — prompt 強化:開頭逼出明確方向判斷（看得出好壞）

user 部署 v19.124 後回饋:個股問答不炸了,但答案「看不出好還是不好」—— AI 把「先講重點」
理解成「先報分數(65.7 B級)」,列一堆欄位卻不下判斷。**修**:`SYSTEM_INSTRUCTION` 第 3 點改為
「**開頭第一句必須用『偏強 / 中性偏多 / 中性 / 中性偏弱 / 偏弱』方向詞總評,禁止用分數或欄位數字開頭**」,
之後才補 1-2 句理由;維持研究面判讀(非下單建議,守 EX-AI-1/不下單)。純 prompt 字串,
`ai_qa_service.py`(L3)單檔;golden **10 passed**、selftest 全過、py_compile 過。

## 🧬 2026-07-15 AI 問答 v19.124 — 修 JSON 序列化 bug（個股問答炸掉）+ prompt 補「先講重點」

user 部署後實測回饋兩點:
- 🔴 **真 bug**:個股問答「台積電呢?」→ `TypeError: Object of type bool is not JSON serializable`
  **整段死掉**。根因:工具回傳含 **numpy 型別**(如 `score_single_stock` 的 `vcp_atr_pass` 來自
  numpy/pandas 布林運算),放進 functionResponse 送 Gemini 時 `requests(json=payload)` 內部
  `json.dumps` 不認 numpy bool/int → 炸。**修**:新增遞迴 `_json_safe`(numpy scalar 走 `.item()`
  轉 python 原生、set/tuple→list、無法序列化退 str),在 `_run_tool`(聊天 functionResponse)+
  `_normalize_bundle`(panel/tab bundle)兩個送 LLM 的邊界過濾;`_bundle_brief` json.dumps 補 `default=str`。
- 🎯 **重點沒出來**:user 喜歡簡短但答案只複述欄位。`SYSTEM_INSTRUCTION` 第 3 點改「**開頭第一句
  先給最關鍵結論/該採取的行動**,再 1-2 句補依據,別只逐欄複述」,維持簡短但重點前置。
- **test**:`test_json_safe_numpy_serializable` + `test_run_agent_numpy_tool_result_no_crash`(複現:
  工具回 numpy → functionResponse 需可 json.dumps 不炸);**revert `_json_safe` 實測 crash 測試確 FAIL**
  → 測有效。golden **10 passed**、selftest 全過、py_compile 過。變更隔離於 `ai_qa_service.py`(L3)。

## 🧬 2026-07-15 AI 問答 ROE Phase 1.5（v19.123，user 核准 Option A）— 財務卡補單季 ROE

Phase 1 財務工具刻意略過 ROE:fetcher(`fetch_financial_statements`)只給**單季**淨利,
`單季淨利/股東權益` ≈ 年 ROE ÷ 4,直接標「ROE」會 **4× 誤導**(§4.1 季 vs 年)。§7 對公式後
user 核准 **Option A**(誠實標「單季」,不硬湊年化):
- `ai_qa_service._calc_single_quarter_roe(net_inc_k, equity_k)`:`單季淨利 ÷ 股東權益 × 100`
  (兩者同為千元 → 約分後無量綱)。分母須為**正的有限數**,否則回 None(§4.4 不 silent ÷0、
  §1 不腦補;淨利可負 = 合法負 ROE = 虧損)。`_tool_get_financial_health` 注入 `ROE(單季%)` 欄
  (不可算則不加該 key,不 fabricate);tool description 補「單季ROE」。
- **未做年化 TTM**(誠實記錄):需近 4 季淨利來源,fetcher 只給 1-2 季,`get_quarterly_data`
  為營收/毛利率導向、金融股路徑無淨利欄 → 不硬接(§1)。要年化準度再議 Option B。
- **test**:`test_single_quarter_roe_calc`(正常 / 虧損負值 / ÷0 / 負權益 / NaN 分子分母 /
  None / 非數 共 9 斷言);golden **8 passed**、selftest 全過、py_compile 過。

## 🧬 2026-07-14 AI 問答 agent Phase 2（v19.122，user 續指派）— 逐 tab「AI 總結本頁」

Phase 1(v19.121)骨幹落地後,user 指派 Phase 2:各 tab 加「🧬 AI 總結本頁」按鈕(用該頁**已載
好的資料**組 bundle 給分析師 panel 討論,**不重抓、不重付 API**;規格 §5/§8)。

- **survey agent 先掃**:規格 §8 表列 6 tab,查證後**兩處是死路**——
  ①`tab_mj_health_diff` **v18.189 已 ARCHIVED**(app.py:469 註記、0 caller)→ 加按鈕永不渲染,**跳過**(§-1 不接死碼);
  ②`tab_stock_picker` 非可見的「選股網」(選股網是 app.py inline `render_prescreen_panel`+screener);
  ③`etf_dashboard` 是 re-export shim,真 render 在 `etf_tab_single`。
- **實接 4 顆按鈕**(全 fail-soft try/except 包住,壞了顯示「暫不可用」不影響本頁;bundle 全取
  自各 tab **已寫入的 session_state key**,scope-independent):
  - **總經** `tab_macro.py`:bundle = `warroom_summary`(9 純量紅綠燈總覽)+ `intl_snap` + `macro_info`,context=macro
  - **選股網** `app.py` screener 區塊:bundle = 本地 `_cands.head(15)` + `_shortage_rows` + `_rs_rows_all`,context=general
  - **個股組合** `tab_stock_grp.py`:bundle = `t3_data` + `t3_batch_codes` + `_fh_t3_results`,context=general
  - **ETF 單檔** `etf_tab_single.py`:bundle = `etf_single_data`(去掉 price_df DataFrame),context=general
- **守則同 Phase 1**:數字由 bundle 用 `st.table` 渲染、AI 只討論帶 🧬 旗標、無資料不呼叫 LLM、
  按鈕觸發 + session_state 快取控成本、無金鑰→「未啟用」。**core service/test 不動**(Phase 1 已測)。
- **未做**:Phase 3 Fund(需 adapter + `PANELS["fund"]` + `infra/llm` passthrough);ROE Phase 1.5;
  個股頁「AI 分析師討論」已在 Phase 1 落地(`render_stock_panel`)。

## 🧬 2026-07-14 AI 問答 agent Phase 1（v19.121，user 主動要求新功能）— Stock 骨幹落地

user 交付外部規格(AI 分析師 panel + 問答),經雙 agent 查證 + 離線實跑核心(selftest 6/6 /
golden 7/7)後,依 §8.1 分階段落地。**Phase 1 = Stock 骨幹**(service + 個股 panel + 聊天分頁);
逐 tab「總結本頁」= Phase 2 不碰。

- **新增 3 檔**:`src/services/ai_qa_service.py`(L3,允許 I/O)/ `src/ui/tabs/tab_ai_chat.py`(L5)/
  `tests/test_ai_qa_service.py`(7 golden,離線免金鑰注入假工具+假 Gemini)。
- **接線 2 處(純新增)**:`app.py` 頂層「🧬 AI 問答」分頁(`_render_tab_isolated` 錯誤隔離)+
  `tab_stock.py` 個股頁「AI 分析師討論」按鈕(fail-soft try/except,壞了不影響本頁)。
- **adapter 依實際簽名校正**(規格全標 TODO 沒驗,查證後改):import 走 `src.*` 實際包、
  `calc_atr_stop` 在 `src.compute.scoring`、market_state as_of 用 `timestamp`、score 用小寫
  `vcp_atr_pass`(無 `fundamental`)、financial 無 `ROE(%)`/`as_of` 改用實際欄位 + as_of=`period`。
  **ROE 需 TTM 淨利**(§4.1 季 vs 年,naive 季ROE 會 4× 誤導)→ **留 Phase 1.5**(先對公式)。
- **守則**:§1 Fail-Loud(工具失敗回結構化 error;bundle 全無資料不呼叫 LLM 不 fabricate);
  EX-AI-1 精神(權威數字由 `tool_calls`/`bundle` 用 `st.table` 渲染,AI 敘述另段帶 🧬 旗標,
  嚴禁從 LLM 字串萃取數字);§8.2 L5→L3→L1/L2 無上行 import;唯讀(不下單/不寫外部狀態);
  無 `GEMINI_API_KEY` → 分頁「未啟用」,dashboard 其他功能不受影響。既有 AI 不動,並排新增。
- **Gemini 走法**:Stock L3 允許 I/O → 內建 `_make_default_http`(直連 REST,panel 純文字 +
  聊天 function-calling 通吃)。⚠️ 繞過 NAS proxy 直連 Google,部署時才確定通(Google API 幾乎不被擋)。
- **未做(誠實記錄)**:Phase 2 其餘 5 tab「總結本頁」;Phase 3 鏡像 Fund(需寫 adapter +
  `PANELS["fund"]` + `infra/llm` function-calling passthrough);ROE Phase 1.5。

## 🔌 2026-07-14 fetch_url lean-path 直連降級修（v19.120）— Fed Funds 卡「待取得」真兇

user 回報「美元資金成本錨 缺資料」(Fed Funds Rate 卡待取得,底部「部分指標載入失敗 1 項」),
其餘 5 卡(NDC/出口/PMI/CPI/VIX)皆有值。user 直覺點破「直接連接不行嗎?FRED 應該不會擋 GitHub IP」
——查證屬實,根因在 proxy 降級鏈,不在 FRED。

- **根因 = `fetch_url` 直連 gate bug**:`proxy_helper.py` 直連門檻原寫 `_block >= 2`,但 Fed Funds
  兩條 fallback(fredgraph + FRED-API)都用 `attempts=1`(lean path)。attempts=1 時單次 proxy 403 →
  `_block=1` 且因 `attempts <= 1` **立即 break** → `_block` 永遠到不了 2 → **直連整段被跳過** →
  掉 NAS 中繼(未設回 None)→ 卡片「待取得」。
- **為何只有 Fed Funds 死**:六卡唯一 100% 靠 FRED 者。CPI 第三條 BLS(`macro_snapshot.py:475`)用
  `_s.post` **自己直連、不走 fetch_url** → proxy 死也活;NDC=FinMind、出口=海關直連、PMI=durable、
  VIX=Yahoo,皆不靠 FRED。故 FRED 從雲端 proxy 連不到時,只有 Fed Funds 這張沒逃生口。

**修**:`_block >= 2` → `_block >= 1`(proxy_helper.py:224)。任一次 proxy 403 都退直連(FRED 公開
API 直連可通)。對 `attempts>1` 多重試路徑零影響(該路徑本就累到 _block>=2 或先 return 200,不會走到)。
**順帶救到所有 attempts=1 又吃 proxy 403 的 fetch**,不只這張卡。
- **回歸網**:`test_proxy_lean_direct_fallback_v19_120`(4 測:403 退直連 / proxy 成功不多打 /
  attempts>1 持續 403 仍直連 / proxy+直連皆敗誠實回 None)。revert gate 實測核心測試確會失敗 → 測有效。
- **白話**:這張卡兩條路都設「快速模式(只試一次)」,舊碼規定「被擋兩次才改直連」,但只試一次永遠湊不到
  兩次 → 直連從沒啟用 → 空白。FRED 其實直連就通(公開政府資料),改成「被擋一次就直連」即可。其他卡沒事
  是因為它們要嘛不靠 FRED,要嘛(CPI)本來就自己直連。

## ⏱️ 2026-07-13 race 硬上限修（v19.119）— v19.116 慢 timeout 反噬 v19.118 durable 的真兇

user 部署 v19.117/118 後 PMI + 出口**仍**待取得(NDC 39分、CPI 2.96% 有值 → 證明 orchestrator 有跑)。深挖資料流實錘一條**我自己造的**回歸鏈:

- **卡片資料流**:`section_mid` 讀 `st.session_state['macro_info']['ism_pmi'/'tw_export']`,由
  `macro_trio_orchestrator` 呼叫 `fetch_tw_pmi_block`(→ `fetch_tw_pmi`)/ `fetch_export_block` 填。
  orchestrator 給每個 block **70s inner budget**(macro_trio_orchestrator.py:28),逾時**cancel**。
- **真兇**:v19.116 把 dgtw metadata timeout 放寬到 **25s×2 attempts×3 URL = 最壞 ~150s**,而
  `fetch_tw_pmi` 原碼 `for _fut: _fut.result()` **無限等最慢源**。雲端 data.gov.tw「連得上但 hang」
  時 → fetch_tw_pmi 要 ~150s 才回 → orchestrator 70s 就砍掉整個 block → **v19.118 的 durable
  seed 在回落前就被砍,根本讀不到** → 卡片「待取得」。**即 v19.116(慢)反噬 v19.118(durable)**。
  (本機 sandbox proxy 秒速 403,測不出此 hang,誤判 v19.118 已解 — 誠實記錄。)
- **出口同理**:sequential 鏈 customs-direct(25×2)+metadata(25×2×2)+CSV(25×2) ≈ 225s ≫ 70s → 同樣被砍。

**修**:
- **PMI**:`fetch_tw_pmi` 改 `as_completed(timeout=_PMI_RACE_DEADLINE_S=45s)` + `shutdown(wait=False)`
  — 慢源背景自生自滅、主流程 45s 內**必回** → durable fallback 生效。45s < 70s budget、> data.gov.tw
  正常 12-18s(慢站活著時仍 live 命中)。
- **出口**:收 timeout fit budget — customs-direct 15s×1(探針證實快)、metadata 10s×1、CSV 12s×1,
  最壞 ~60s < 70s → customs-direct(可靠主源)準時回 live。
- **回歸網**:`test_pmi_bounded_race_v19_119`(慢源 hang 60s → fetch_tw_pmi 2s deadline 內回 durable /
  快源仍命中 / deadline < 70 / 結構鎖)+ `test_dgtw_resilience_v19_116` 改鎖出口收窄。全套 pytest 綠。
- **白話**:以前抓資料太慢、被系統 70 秒鬧鐘砍掉,連「上次存的 60.7」都來不及讀 → 空白。現在 45 秒內
  一定收工,抓不到就秒讀 durable seed 顯示 60.7 🟡。出口同樣卡進時限,直連海關準時回。

## 🧊 2026-07-13 PMI durable 快照（v19.118,user 核准「建快照+seed」）— 卡片穩定有值的終解

user 用 **5 張圖**證明:測試連線 FinMind/TWSE/Yahoo 全 200、外連診斷 proxy+直連全 200、
`fetch_tw_pmi` 監控 🟢——**問題 100% 不在連線**,並要求「請找其他解決方法」。深挖後真根因浮現:

- **假綠燈**:`fetch_tw_pmi` 8 源全敗仍回 dict(`value=None`)、**從不拋例外** → 舊 `@monitored`
  只看「有無拋例外」(fetch_monitor.py:93)→ **恆綠**,誤導 user 以為有值。
- **真根因 = 既有快照存錯地方**:v18.225 的 stale-cache 機制**本來就在**(命中存、全敗讀、帶
  is_stale),但存 **`cache/`(Streamlit Cloud ephemeral 磁碟,container recycle 即抹)** →
  一次上游打嗝後檔案沒了 → 全敗 `_macro_cache_load` 回 None → 卡片「待取得」。**不是連線、
  不是 NAS、不是 timeout**——是快照撐不過雲端重啟。
- **8 源本身也都「連得到、榨不出數字」**(NDC 非 JSON / CIER-EN 值在 JS / dgtw catalog 不穩 /
  無新聞標題),即時抓本質不穩 → 唯持久化快照能讓卡片穩定有值(§5 凍結快照 + §2.4 is_stale)。

**修(§8.1 user 核准「②建快照+seed」,設計比原提案更精簡——快照機制已存在,只補 durable 層):**
- **durable 層** `data_cache/macro_last_good/`(**committed**,隨 deploy 帶上,撐過 recycle)。
  `_macro_cache_load` 改**兩層 fallback**:先 ephemeral `cache/`(session 最新)→ miss/過期讀
  durable(§4.6)。皆 90d TTL 過期回 None(§1 不把 3 月前值當現在)。
- **cron 寫入**(`update_macro_history.py` 尾段):跑同一個 `fetch_tw_pmi()` 抓成功 →
  `_macro_durable_save`;**只存 live hit,不回存 stale**(否則 cached_at 每日重刷 = 過期值假裝
  永遠新鮮,§1)。workflow 既有 `git add -f data_cache/` 自動 commit。runtime(Cloud)只讀不寫。
- **seed 當月值**:`data_cache/macro_last_good/tw_pmi.json` = **60.7**(2026-06,CIER 官方公布,
  多源查證:連 9 月擴張、較 5 月 61.4 降 0.7),附完整 provenance。→ **部署後卡片馬上顯示 60.7
  🟡「N 天前」**,不必等 cron。
- **假綠燈治理**:`@monitored` 加選填 `success_check`;`fetch_tw_pmi` 回 `value=None` → 監控
  亮 🔴(有值含 stale → 綠)。舊 caller 全不受影響(預設 None=舊行為)。
- **回歸網**:`tests/test_durable_snapshot_v19_118.py` 7 test(ephemeral 空讀 durable / ephemeral
  優先 / 過期回 None / durable_save / 全敗+durable 回 stale 值且監控綠 / 全敗+無 durable 回 None
  且監控紅 / seed 誠實值域+provenance)。`test_fetch_monitor` 46 全綠(success_check 向後相容)。
  ruff 新碼淨(11 個 pre-existing 舊債非本次,CI 無 ruff gate)。
- **白話**:以前「即時抓不到 = 空白」;現在「即時抓不到 → 讀上次成功值 + 標🟡N天前」,永遠有數、
  誠實標記、cron 每日自動刷新。data.gov.tw 連日全滅也扛得住。

## 🎯 2026-07-13 出口改直連海關 opendata（v19.117,v19.116 timeout 放寬證實不足）

v19.116 timeout 放寬(25s)後再跑 production smoke(run **29223581269**,同 b4222f7),得**決定性反證**:timeout 不是(唯一)根因。

- **鐵證:同一 run、同一條 NAS、同一個 URL、相反結果**。deep-dump 打 `data.gov.tw/api/v2/rest/dataset/6100` metadata **成功**(`resources × 1` → 下載 `Download.ashx` 200/2881B `Date,PMI,NMI`);production `_pmi_src_dgtw` **秒級後**打**同一 URL**(且更寬鬆 25s vs deep-dump 15s)卻 `dgtw./rest/dataset/6100:無回應`。→ **data.gov.tw catalog metadata hop 從雲端 IP 本質不穩**(疑 rate-limit/連線層),放寬 timeout 救不了。
- **但資源 CSV 本身穩**:`opendata.customs.gov.tw/data/6053/csv.csv` 於兩 run(29186611230+29223581269)皆 200/14202B。**海關 opendata 才是實際 T1 源,data.gov.tw 僅 catalog 指標。**
- **出口決定性修(本次)**:`fetch_export_block` 6053 段改**先直打海關 opendata 直連 URL**(繞過脆弱 catalog),失敗才回退 metadata resolution。直連段 except 記 `customs-direct/6053:` 診斷 token(§1 不裸 pass)。source 標 `opendata.customs.gov.tw/6053(...,直連)`。
- **PMI 為何不比照**:6100 resource = `ws.ndc.gov.tw/Download.ashx?u=<base64>`,base64 內嵌**每月輪替的檔案 GUID**(NDC 重傳月報即變)→ 硬寫 URL 會月月失效(§3.3 不猜穩定性)。PMI 真解仍需 metadata hop,或**持久化快照**(下)。
- **回歸網**:`tests/test_export_direct_v19_117.py` 4 test(直連 URL 存在且排 catalog 前 / 直連 except 記 token 非 pass / 直連成功 short-circuit 不再打 catalog / 直連壞掉落回退回 `_err_export`)。17 test 全綠(含 v19.114/115/116),ruff 淨。
- **仍待議(§8,已向 user 提案待核准)**:持久化「上次已知值」快照 — data.gov.tw catalog 連日不穩時,唯快照能扛 PMI(出口已由直連解)。

## 🐢 2026-07-13 dgtw 慢站 timeout 放寬 + Cnyes crash 修（v19.116,user 部署後仍待取得）

user 部署 v19.114/115 後回報 PMI/出口**仍待取得**,並用 app 診斷證明 **NAS 正常**(端對端 proxy+直連全綠、FinMind/TWSE/Yahoo 200)。推翻「NAS 間歇」假設。真根因用 production smoke(run 29220720874,雲端+NAS 跑合併後真 fetcher)實錘:

- **主因:dgtw metadata timeout 太短**。`_pmi_src_dgtw` metadata 用 `timeout=10, attempts=1`,但 data.gov.tw 是慢速政府 API(實測回應常 12-18s)→「慢但活」時被 10s 殺掉回 `無回應`。**這正是探針(20s/2 attempts)成功、production(10s/1)失敗、同一條 NAS 的根因**。修:PMI+出口的 dgtw metadata 與 CSV 下載全放寬 `timeout=25, attempts=2`。
- **附帶 bug:Cnyes 源 crash**。smoke 印 `Cnyes:parse TypeError: can only concatenate str (not "NoneType")`。`it.get('summary','')` 對「鍵存在但值=None」不套 default → None 進字串串接崩,整個 Cnyes 源在第一篇 null summary 就掛(即使後面有 PMI 命中也拿不到)。修:`(it.get('title') or '') + ' ' + (it.get('summary') or '')`。
- **@monitored 綠燈是誤導(記錄但不修)**:`_record(name,'ok')` 只要函式不拋例外就記綠,`fetch_tw_pmi` 永遠回 dict(值或 `_err`)不拋 → 恆綠。user 看到 `fetch_tw_pmi` 綠燈 ≠ 有值。屬監控語意瑕疵,非本次核心,§-1 不順手擴。
- **回歸網**:`tests/test_dgtw_resilience_v19_116.py`(Cnyes None-summary 不 crash+仍命中 title PMI+缺鍵亦可 / dgtw timeout 全 25s 且無 10s 殘留)13 test(含 v19.114/115 recovery)。ruff 新碼淨。
- **仍待議(§8,未動)**:持久化「上次已知值」快照(cron 存 repo JSON,app 全敗時讀)— data.gov.tw 若連日全滅,timeout 放寬也救不了,唯快照能扛。待 user 點頭建。


## 🎣 2026-07-12 兩張死卡救回:PMI + 出口 dgtw parser 重接（v19.114/115,user 核准「1+2」）

user 問「其他找不到的資料能否用探針法救回」→ 探針 run 29186611230（美國 IP + NAS）第三輪深挖**實錘兩條活 CSV**,現行 parser 從未真解析過。user「1+2」= 救 PMI + 救出口。

- **v19.114 PMI（`macro_core._pmi_src_dgtw` 重接）**:探針證明 dgtw 6100 resource = `ws.ndc.gov.tw/Download.ashx?u=...`,head=`Date,PMI,NMI 201207,47.1,-...202606,60.7,-`（升序、YYYYMM、含最新 60.7）。**死因**:原 parser 雙重 gate —「resource format in (CSV,JSON)」+「URL 含 'csv' 才解析」,但該 URL 無 'csv' 字樣、format 常空 → 活 CSV 從未進解析分支。**修**:收所有 resource url（CSV format 排前）逐一下載,交新純函式 `_parse_dgtw_pmi_csv`（取最新 PMI∈[30,70] 列 + age≤90 天）。對帳:6 月 60.7（CIER 官方發布值）。
- **v19.115 出口（`macro_snapshot.fetch_export_block` 6053 tier 重接）**:探針證明 dgtw 6053 resource = `opendata.customs.gov.tw/data/6053/csv.csv`,head=`"年度","月份","出口總值(新臺幣千元)",...  "115","4",...`（**民國年、降序、新臺幣千元**）。**死因**:原 parser 三處對不上 —（a）年度/月份分兩欄只抓月份無年、（b）源降序卻用 `iloc[-1]`（取到最舊列）、（c）未同月對齊。**修**:新純函式 `_parse_customs_export_csv`（西元=民國+1911、同月對齊 `YoY=(出口總值[Y,M]/出口總值[Y-1,M]-1)×100`、sanity base>0 且 YoY∈[-80,200]）。
- **幣別誠實（§4.1)**:海關 CSV 為**新臺幣**,與財政部頭條美元 +40.3% 有匯率落差 → return 帶 `ccy='TWD'`、source 標「海關新臺幣出口總值」。訊號方向（外需擴張/收縮）TWD/USD 幾乎一致,自動化卡片用 TWD 官方原始值正解。**option② USD 探勘**:probe_tw_sources 加 3 個美元 dataset 探針（CKAN 搜「進出口 美元」×2 + 關務署站台）,本次 push 觸發;若找到乾淨美元序列 → 評估 v19.116 加對帳，否則 TWD 為終解。
- **回歸網**:`tests/test_dgtw_recovery_v19_114_115.py` 9 test（用探針真實 CSV 樣本當 fixture:PMI 取最新+越界skip+過舊None+空/僅表頭；出口 同月對齊非iloc+降序仍正確+去年同月缺None+列數不足）。ruff 新碼全淨（macro_core 既有 E701/E402 未觸）。
- **health_inspector 出口來源字串**同步（原「stat.gov.tw+FinMind+MOF+FRED+data.gov.tw+靜態 6段」殘影 3 世代 → 更正為「stat.gov.tw+FRED+data.gov.tw/6053(海關新臺幣)+CKAN 5段」）。
- **方法論沉澱**:「探針從雲端+NAS 抓到含值內容 → 重接 parser」對任何死卡通用;不能抓到含值內容者（CIER-EN 值在圖/JS、nstatdb 空殼）= 硬修 regex 也沒用,誠實換源或標不可得（§1）。

## 🧊 2026-07-12 失敗不進快取 + 死源清理（v19.113,user 核准提案①+②）

v19.112 診斷收斂後 user 補測推翻「雲端連不到 NAS」假設(app 內 proxy 雙跑全綠、NAS 測試 978ms 成功)→ 真根因 = **凍結機制**:六個總經 block 掛 `@st.cache_data(ttl=1h)` 且失敗 dict 也被快取;「🚀 一鍵更新」吃暖快取(help 文字自證)、畫面讀 session_state — 一次上游打嗝(同日實錘 dgtw 05:32 cron 死 / 14:13 探針活的間歇)被凍住顯示。user 核准「1+2」:

- **①失敗不進快取**:新 `_cache_success_only(ttl)` 裝飾器(macro_snapshot 模組內)— 失敗(空 dict 或全 `_` 前綴鍵,`_is_block_failure`)以內部例外 `_BlockFetchFailed` 穿透 st.cache_data(官方語意:拋例外不落快取),外層還原 err dict;成功照常入快取。`.clear()` 透傳(強制重抓按鈕 + 3 個既有測試依賴)。換裝 6 block:vix/cpi/fed_funds/tw_pmi/ndc/export。**不納入**:`fetch_m1b_m2_block`(失敗回 None)與 `fetch_us10y_block`(失敗形狀 `{'us10y':{'_err':...}}` 帶資料鍵)— 形狀不同判準不適用,等實錯再議(§-1)。
- **②死源清理**(探針 run 29182317622 實錘,user 核准範圍):PMI 賽跑拔 MacroMicro 段(host 級無回應,9→8 源)+ CIER 段拔已下架的 `news/list?cid=21` URL(保留未實測死亡的首頁掃描);出口鏈拔 MOF `service.mof.gov.tw` trade CSV 段(端點族下架,6→5 tier)。**未越權拔**:CIER-cid8(未探測)、US PMI 的 MacroMicro 段與 NDC 的 MacroMicro 備援(非本次範圍)。
- **文件同步**:CLAUDE.md §2.1(8 源+v19.113 註)/ SPEC §4 表整張重寫(原表停在 v19.85 前:仍列 FinMind、缺 CIER-EN — 陳年漂移一併矯正)/ health_inspector 兩張表 / tab_edu / data_registry / schemas / tw_macro 共 5 處殘留「9 源」字串對正(其中 2 處連 FinMind 都還列著)。
- **回歸網**:`tests/test_cache_success_only_v19_113.py`(凍結 bug 棺材釘:全敗→上游復原→同參數再呼叫**必須真重抓**;成功→斷線→**必須回快取**;判準單元含混合鍵;6 block 裝飾掃描;.clear 透傳)— 對帳基準用財政部 6 月出口 +40.3%(2026-07-09 公布)。重釘 `test_review_fixes_v19_85`(9→8 源,加 MacroMicro 不得回歸)與 `test_export_fail_trace_v19_112`(tier 6→5)。macro 子集 802 passed。
- **對 caller 零改變**:契約(成功資料鍵/失敗 `_err_*`)不動;效能不退(成功仍快取 1h);EX-CACHE-1 letter 不變(內部仍 st.cache_data,無 UI 呼叫,_NoOpST 環境 .clear 以 getattr 護)。
- **修中之修(CI 紅實錘,誠實記錄)**:v19.112/113 兩個新測試檔對 package `src.data.proxy` monkeypatch `fetch_url` — 重演 **v19.74 已記載地雷**(PEP 562 lazy forward 套件,teardown 還原把真函式寫成實體屬性永久遮蔽轉發)。時序鐵證:v19_112 檔名序在 etf 之後 → fd52364 CI 綠;v19_113 檔名序在 etf 之前 → d432ca2 CI 紅(`test_etf_moneydj_nav_parse` 3 測 fixture 失效,GH runner 打真 MoneyDJ 抓到 30 筆活資料)+ 本地全套 4 failed 同步重現。修正:兩檔全改 patch 真正持有者 `proxy_helper`;新增 `tests/test_zz_proxy_pollution_lock.py`(字母序最後跑,fast+slow 雙 lane)鎖「package 實體命名空間僅允許子模組」— 污染從 order-dependent 下游背鍋變具名炸出;鎖已自測(手動模擬遮蔽 → 正確 AssertionError)。

## 🔎 2026-07-12 出口 YoY 全敗 fail-trace 補接（v19.112,user 回報實錯觸發）

user 驗收統一卡時回報「外需動能溫度計 台灣出口 YoY 無資料」+「台灣 PMI 也沒有資料」(§-1 實錯觸發)。診斷證據(GitHub Actions 每日 cron 2026-07-11 21:32 UTC run 29168967659,帶 PROXY_URL 走 NAS):

- **NAS Squid proxy 活著**:TWII/CBC PXWeb/dgtw 皆出現「已透過 Synology NAS 成功抓取」→ 排除「NAS 掛掉」單因說。
- **data.gov.tw dataset API 連台灣 IP 都死**:`[tw_pmi] ❌ 所有 dgtw metadata URL 皆失敗`;且 `data_cache/metadata.json` 顯示 tw_pmi parquet **從建立起 0 rows / last_updated=null** → 「讀 repo 歷史快照當 PMI fallback」此路不存在。
- **CBC ms1.json 端點退化回 HTML**(PXWeb 備援吃住,M1B/M2 無恙,順帶記錄)。
- **PMI 卡**:`fetch_tw_pmi` 9 源賽跑全敗時已回 `_err_pmi`(+ 本地 stale cache,惟 Streamlit Cloud 重新部署即清空)→ UI「🔍 部分指標載入失敗」面板**已能**顯示逐源錯誤碼,等 user 截圖定位。
- **出口卡真 bug**:`fetch_export_block` 全敗回 `{}`(v18.330 反捏造修正)但**從無 `_err_export` setter** — trio orchestrator `if _part:` 連 merge 都進不去,section_mid `_err_label_map['_err_export']` 與 health_inspector L582 err_key 兩個讀取端都是死鍵 = 7 個 macro fetcher 中唯一全敗時無 fail-trace 的(v18.194 設計盲區)。

**本版修復**(單檔小修,不觸發 §8):`fetch_export_block` 6 tier 各補 per-tier fail token(`stat.gov.tw:HTTP None` / `FRED-API:skip(無 FRED key)` / `MOF-CSV:ConnectTimeout` …,鏡 `fetch_ism_pmi` errs 模式),全敗回 `{'_err_export': 'src:err | ...'}`。**不含** `tw_export` 數值 key,§1 不捏造精神不變;部署後 user 打開錯誤碼面板即可看到出口鏈死在哪一段。

- **回歸網**:`tests/test_export_fail_trace_v19_112.py` 4 test(全源斷線回 token 不回值/6 tier 全留痕+無 key 標 skip/回傳僅 `_` 前綴鍵可進 orchestrator merge/UI 標籤存在);`test_macro_export_no_fabrication.py` 重釘(原鎖 `return {}` → 改鎖 `return {'_err_export':` + 全敗段禁 `'tw_export': {` 賦值,重釘理由入 docstring)。macro 子集 784 passed。
- **不動的**(待 user 核准,§-1):新出口/PMI 資料源評估(FinMind 無出口與 PMI dataset — v19.85 已枚舉證實;MOF/stat.gov.tw 存活狀況待 user 截圖錯誤碼面板後再定)、PMI stale cache 落盤到 repo(需 §8 設計)。

**探針補證(同日,run 29182317622)**:user 問「能否上網找資料來源」→ 加 `scripts/probe_tw_sources.py` + `probe_tw_sources.yml`(push paths 過濾自動觸發;App 整合無 actions:write 不能 dispatch,且分支 workflow 不上 Actions 清單 — Calibrate 前例)。15 端點經 NAS 實測(美國 IP + PROXY_URL,與 Streamlit Cloud 同視角):

- **兩鏈頭部源全活**:CIER-EN 舊 slug `/en/eco/taiwan-manufacturing-pmi-june-2026/` **HTTP 200 含 6 月文**(網搜以為改制 404 — 誤;新分類頁 `/en/eco_cat/pmi-en/` 也 200)、stat.gov.tw 出口年增率頁 200(426KB)、dgtw 6100/6053 metadata 200(`success:true`)、Cnyes API 200。
- **確認死源**:CIER `news/list?cid=21`(現役第5源)、MacroMicro(第4源)、MOF trade CSV 舊 URL 式(Tier2)、CIER 中文 focus-ch 無回應;NDC index API 200 但回 Angular SPA 殼非 JSON(名存實亡);MOF njswww 入口回 1 char;nstatdb qryout 回 HTML 殼(需再調參才有 CSV)。
- **根因改判**:來源經 NAS 全通 + 正式站上「死的恰好全是 NAS 依賴指標、活的全是直連指標」→ **主嫌 = Streamlit Cloud → NAS 這一段**(app secrets 的 PROXY_URL 與 GitHub repo secret 是兩份獨立拷貝,疑漂移/失效;或 NAS 防火牆擋 Streamlit 出口 IP)。判別法:v19.112 部署後錯誤碼面板 — 若 CIER 段出 `HTTP403` = 直連打到官網被擋(NAS 路徑死);cron 今晨 dgtw `HTTP=None` 與探針 200 的矛盾 = cron 腳本 URL/解析待另查(不影響主嫌判定)。
- **user 端 5 分鐘自查**:工具 Tab →「🔎 資料診斷」→「🚀 開始診斷外連狀態」(proxy vs 直連雙跑) + 檢查 Streamlit Cloud Secrets 的 `PROXY_URL` 是否與 NAS 現址一致。
## 🔭 2026-07-12 選股網極簡版:只留單一「開始選股」按鈕（v19.111,user 要求）

user 回報選股網「還是一樣」,澄清訴求:要**乾淨的篩選流程** — ① 基本面優選(自動)→ ② 勾條件(估值/EPS/缺貨/抗跌RS 四因子可複選)→ ③ 一鍵出名單,**不要下方那一整塊額外掃描按鈕**,只維持最上方一顆「開始選股」。

- **移除**:app.py 選股網區塊底部的「🔎 進階(選用)」expander(內含 `render_shortage_screener` 缺貨完整排行 + `render_rs_leader_screener` 抗跌RS完整排行 + AI三型報告)+「順便跑籌碼技術×6」checkbox(`_run_deep`)及其 `render_tab_stock_picker` picker 深篩。連帶清掉 `render_tab_stock_picker` / `render_yield_confirm` 兩個已無用的 local import。
- **保留不動的核心流程**:① `render_prescreen_panel`(基本面優選,自動)② `screener_factors` 多選(4 因子)③ 單一「🎯 開始選股」按鈕 → 按下時**自動掃**缺貨(`run_shortage_scan`)+ 抗跌RS(`run_rs_leader_scan(beat_only=False, top_n=RS_SCAN_MAX)` 全存活池)→ `composite_rank_candidates` 綜合評分 → ③ 選股結果 dataframe + CSV 下載。三點承諾全達成:缺貨/RS 自動掃(不用另按)、無手動候選名單、勾條件→一鍵→出名單。
- **§8 分層**:純 L6 App UI 組裝的元素刪減,無新模組、無資料流變更、無跨層 import(反而移除了兩個 L5→L1/L4 的 lazy import);L2/L3 掃描與評分服務完全未動。§-1 只做 user 明確要求,無夾帶。
- **回歸網**:`tests/test_app_no_magic_bare_ternary.py` 新增 `test_screener_keeps_only_single_button_flow` — AST/source 掃描鎖死 app.py 不得再出現 `render_shortage_screener` / `render_rs_leader_screener` / `screener_run_deep` / `render_tab_stock_picker`(改回去=紅)。既有 magic-guard(裸三元)續守。app.py 語法 OK;選股相關 32 passed + 本檔 3 passed。

## 📉 2026-07-12 週 MACD 升級標準 12/26/9（v19.110,插隊項 user 核准）

user 核准「週 MACD 升級」(= 確認有在用週 MACD 出場訊號、要與券商對數字)。`exit_signals._weekly_macd_turn_negative` 自 v19.105 標註的 3/5/3 樣本受限代理升級為標準參數。

- **數學式(§7)**:w_t = 每 5 交易日一組的組內最後收盤(**自尾端對齊**);DIF = EMA12(w) − EMA26(w);DEA = EMA9(DIF);OSC = DIF − DEA;訊號 = OSC[-2] > 0 且 OSC[-1] ≤ 0(柱由正翻負,語意沿用舊版)。EMA adjust=False 遞迴定義同多數看盤軟體。
- **樣本門檻**:≥ `WK_MACD_MIN_WEEKS`(35) 週 = 175 交易日;不足誠實回 False,**不**退回 3/5/3(§1 一名一義不混模型)。資料窗核實:批次掃描走 360 日、個股主流程 days+60,實務皆 ≥175,無需動 caller。
- **順帶修掉既有缺陷**:舊版 `range(0, 30)` 取的是序列**頭端**(最舊 30 日,docstring 卻寫「近 30 日」)— 訊號一直在看最舊一個月的資料。本版自尾端合成,測試鎖死(頭端崩盤+尾端多頭 → 必須 False)。
- **SSOT**:`WK_MACD_FAST/SLOW/SIGNAL_SPAN`(12/26/9)+ `WK_MACD_MIN_WEEKS`(35)+ `WK_MACD_DAYS_PER_WEEK`(5) 入 shared/signal_thresholds(§14 前綴分名);exit_signals 零 inline 參數。
- **已知限制(docstring 註明)**:close 無日期索引,「每 5 根=一週」為近似;最新一組=最近 5 個交易日,可能跨日曆週界,當週值與券商按日曆週切的會有小差。
- **回歸網**:`tests/test_weekly_macd_v19_110.py` 6 test — 含 **§4.3 雙算對帳**(測試內教科書式獨立重算 OSC,由對帳器搜出翻負場景再驗 production 同判,非手猜期望值)/純多頭不誤報/不足 175 日誠實 False/頭崩尾多鎖舊缺陷/NaN dropna 不炸/SSOT 掃描(3/5/3 殘留=紅)。相關子集 27 passed。

## 🃏 2026-07-12 統一指標卡試點 — 總經拼圖模組八 5 卡（v19.109,第 5 步）

未完成清單第 5 步(user「第五步繼續」)。試點區:總經 Tab 模組八「台灣在地總經」5 張 KPI 卡(NDC 燈號/出口 YoY/台灣 PMI/美核心 CPI/Fed Funds;VIX 為時序圖不動)。

- **統一版位四要素**:俗名(白話名,新手第一眼)→ 正式名+日期 → 大字值+燈標籤 → **燈義**(這個燈現在=什麼)→ **原理**(指標怎麼來)→ **門檻帶**(🔴≥38｜🟡≥32…)。待取得灰態同構(§1 誠實)。
- **核心設計:判定與文字同源** — 新 band 表 SSOT(`shared/signal_thresholds`:`NDC_SIGNAL_BANDS`/`TW_EXPORT_YOY_BANDS`/`TW_PMI_CARD_BANDS`/`US_CORE_CPI_YOY_BANDS`/`FED_FUNDS_RATE_BANDS`,每表 list[(下限,色鍵,燈標籤,燈義)] 末項 -inf 兜底)。L4 `resolve_band()` 判燈、`bands_caption()` 生成門檻帶說明、`unified_indicator_card()` 渲染 — **三者讀同一張表**,燈義/門檻帶文字永不與判定邏輯漂移(§3.3)。
- **順手收斂 5 組 inline magic**:原 section_mid 的 38/32/23/17(NDC)、0/-5(出口)、50/47(PMI)、3.5/2.5(CPI)、5/3(Fed)全收 band SSOT,測試鎖定與 legacy 完全同值(零行為位移)。**邊界語意記錄**:CPI 3.5/2.5 由「>」改「≥」(恰等值燈更保守一級)、出口 0.0 由「>0」改「≥0」— 僅影響恰好等值月份,實務機率 ~0。
- **保留不動**:CPI/Fed 上月趨勢行(入卡 extra)、兩條 💡 MK 黃金拐點 caption(跨指標配對提示,非卡片自身原理)、VIX 時序圖(已 SSOT 帶線)。
- **回歸網**:`tests/test_unified_indicator_card_v19_109.py` 9 test(band 表鎖 legacy 值+四元組+兜底/NDC 五級含邊界/燈義同表/垃圾值 gray/無兜底表 gray/caption 逐項反映/卡片四要素/灰態/section_mid 掃描:5+5 卡全走統一卡+legacy inline 門檻零殘留)。slow lane 23 passed(AppTest 實渲染過)+ 相關子集 648 passed。ruff 四檔全淨。
- **試點驗收**:user 看線上效果後決定是否推全站(其餘區塊/基金端)。

## ⚡ 2026-07-12 「今日關鍵」異常橫幅 v1（v19.108,設計 A）

未完成清單第 2 步(user 核准設計 A,§8.1 先設計後動工)。打開總經 Tab 第一眼:置頂橫幅列出「今天最需要看的異常」;無異常誠實顯示細綠條(§1)。

- **設計取捨(誠實聲明)**:報告 4-C 的 robust-z 需各指標歷史分布,現況 `data_cache/` 只有 TWII/法人/融資/M1M2 有序列,VIX/CPI 等只有本期+上期 — **z 分數地基不存在,硬做=腦補分布(§1)**。v1 兩層可驗證規則,robust-z 標升級觸發條件(等 macro_history parquet 覆蓋更多指標)。
- **門檻層**:直接吃既有 `check_macro_alerts`(MACRO_ALERT_RULES SSOT)的 🔴🟡 命中 — 不另造第二套門檻;橫幅=挑出+按嚴重度排序+白話 detail 沿用 rule message(SSOT 敘事)。
- **急變層(Δ)**:僅對 macro_info 內**有真 prev/序列**的指標:①VIX 單日急升 ≥`KEY_ALERT_VIX_DAY_SPIKE_PCT`(20%,3 個月日序列尾兩點;只看急升不看消退) ②Fed Funds 月均 |Δ| ≥`KEY_ALERT_FED_FUNDS_MOVE_PCTPT`(0.20 百分點 ≈ 一碼級政策動作,雙向亮)。兩常數進 shared/signal_thresholds SSOT(附依據)。us10y/dxy 等無 prev → 不做(§1 不腦補變化)。
- **分層**:L2 `src/compute/macro/daily_key_alerts.py`(純函式,零 I/O 零 streamlit;單項 try 收窄,判定層錯誤絕不炸頁)→ L4 `macro_ui_components.key_alerts_banner()`(純 HTML,hover title=白話)→ L5 tab_macro 載入 gate 後、紅綠燈模組前掛載(讀 session_state 零新 I/O)。全程合 §8.2,零例外登記。
- **回歸網**:`tests/test_daily_key_alerts.py` 13 test(空輸入不炸/green 過濾+紅先排序/VIX 急升觸發+未達門檻+急跌不亮/序列垃圾值跳過不影響門檻層/Fed 雙向+缺 prev 誠實跳過/L2 純度掃描/橫幅三態渲染/SSOT+掛載位置鎖)。ruff 既有檔 42=42 零新增,新檔 0 錯。

## 🧯 2026-07-12 CI slow lane 全滅修復:streamlit stub 生命週期收斂（v19.107）

未完成清單第 1 步(user 核准「從第 1 步開始」)。merge #519 時發現 slow lane job 紅,查證 **main 8b071cb 同紅**(非近期 PR 引入)。

- **根因**:三代測試 stub 記號不一致(`_stub` / `_is_test_stub` / 無記號),conftest 舊還原機制只認 `_stub` → `test_macro_classroom` 的 stub 於 **collection 期**模組級永久替換後全程卡住 → 整個 run phase 吃到假 streamlit(非 package):slow lane **24 個 AppTest 全被守衛 skip**(v19.74 起 workaround 化,守門形同虛設)+ `test_screener_candidates` 無守衛硬炸 `'streamlit' is not a package`。整個生態靠「classroom 的 stub 恰好是 noop 超集」的巧合活著。
- **修(三層防線)**:①stub 檔自身收尾 — `test_data_coverage` / `test_macro_classroom` 模組級永久替換改 **module-scoped autouse fixture**(裝 stub + reload 目標 → 測完還原進場真身 + reload rebind;`importlib.reload` in-place,既有引用同步) ②conftest `pytest_collection_finish` **身分還原 backstop**(identity check 不認記號;collection 一結束全域必乾淨) ③`test_zz_streamlit_pollution_lock.py`(字母序最後,fast+slow 各一鎖)— run phase 尾端 streamlit 必須真 package 且 `streamlit.testing.v1` 可 import,未來任何 stub 沒收尾 CI 直接紅在這。conftest 舊的每-test marker 還原移除(與 module fixture 相衝且記號不齊本就失效);`_clear_module_caches` 不變。
- **效果**:slow lane 本地重現 CI — 修前「1 failed + 22 skipped」→ 修後 **23 passed + 4 skipped**(4 skip 皆正當條件:退役功能審計 / fastapi 非 CI 依賴 / 無 secrets.toml ×2)。被跳過月餘的 AppTest 全數真執行且全過。fast lane 全套 3180 passed 照常全綠。
- 純測試基建,production 程式碼 0 行變更。

## ⚡ 2026-07-12 大工程清單 🟢 兩項:ETF 夏普 rf 動態化 + 連線 Session 複用（v19.106）

user 核准大工程清單「先做你推薦的三項」(⑯基金/⑨①a股票),本包為股票側兩項:

- **⑨ ETF 夏普 rf 動態化**:`etf_calc.calc_sharpe` 原寫死 `rf=5.33`(2024 年 FEDFUNDS 水準),利率變動後夏普失真。查證更正:基金 repo 已是動態(fund_service `_RF_ANNUAL` 由 app 注入 FEDFUNDS),股票僅 ETF 端殘留。落地(全程合 §8.2,零例外登記):①SSOT `ETF_SHARPE_RF_FALLBACK_PCT=5.33`(shared/signal_thresholds,注入失敗時零位移)②L2 `etf_calc` 加模組級 `_RF_PCT` + `set_risk_free_rate_pct()`(拒收非數/負/≥25% 越界,§1 不腦補)+ `calc_sharpe(df, rf=None)` 預設走模組值,顯式傳值行為不變 ③L3 `etf_grp_compare_service.ensure_etf_rf_injected()`:L3→L1 抓 `fetch_fed_funds_block`(既有 @st.cache_data 1h)+ L3→L2 setter 注入,失敗回 None 維持 fallback ④L5 grp_compare 批次評分前呼叫一次(ThreadPool 前,worker 共見)。
- **①a 連線層 thread-local Session 複用**:`proxy_helper.fetch_url` 原每呼叫新建 Session(attempts=1 純版/否則 retry 版)— 批次抓(選股/ETF 多檔/PMI 多源)每請求重做 TCP+TLS 握手。比照 Fund repo infra/proxy v19.333 F6:`_TLS_HTTP = threading.local()` + `_get_thread_session(lean)` 懶建立 per-thread 兩口味(lean 無 urllib3 Retry / retry 指數退避),fetch_url 一行切換。Session 非跨執行緒安全 → per-thread 隔離,ThreadPool worker 各自持有無鎖競爭。`make_retry_session()` 保留(被 helper 消費)。
- **回歸網**:`tests/test_review_fixes_v19_106.py` 10 test — rf 預設=SSOT/setter 生效且顯式傳值不受影響/垃圾值全拒收/service 注入成功與失敗兩態(monkeypatch fetch_fed_funds_block)/無殘留 inline 5.33/grp_compare 接線掃描/同執行緒複用 is 同物件/lean≠retry/跨執行緒隔離/fetch_url 本體無 `requests.Session()`。fixture 前後還原模組 rf(§3.3 測試隔離)。ruff:5 個 production 檔 baseline 3=3(零新增),新測試 0 錯。相關既有測試 79 passed。

## 🧾 2026-07-12 第九份外部 review 落地(股票側):查證屬實 14 項修復（v19.105）

user 上傳第九份深度 review,指示「看是否需要修改讓資料更完整,不修的提供清單」。兩組並行 Explore agent 逐條對 origin/main 查證 33 項主張後分流:**查證屬實本次修 14 項**、誤判 2 項、本 session 稍早已完成 3 項(P0)、歷史版已修過多項、架構級大項全數列待核准(§8.1,三分類清單見對話/PR 描述)。

- **穩定性 4 修(UI 不炸卡)**:①`app_render.render_health_score` 因子條 `total=0` → ZeroDivisionError 炸整張健康卡 → `if total else 0.0`(Bug1) ②`chart_plotter.plot_combined_chart` 單列 df 產零寬 initial_range → `total_days>=2` 才給,否則 None 交 plotly autorange(Bug3) ③`macro_ui_components.stat_card` pct 字串型直接 TypeError → float coerce,失敗回中性 0 ④`margin_card` 同病 → coerce 失敗走 None 卡誠實顯示「抓取中」,不炸不腦補(Bug4)。
- **連線層 2 修**:⑤`picker_fetcher.fetch_stock_history_1y` 裸 `yf.Ticker().history()`(無代理無快取,雲端易被 Yahoo 擋 IP、選股批次重複抓)→ 改走 `yf_proxy.cached_history`(NAS proxy + 1h cache),回傳契約 (df, resolved) 不變(1-A) ⑥`etf_fetch` 兩處 `attempts=1` 使 403 直連降級永不觸發(降級需連續 2 次 403)→ attempts=2,同 v18.455 前例(1-B)。
- **快取/log 3 修**:⑦`data_loader.get_quarterly_data` 完全未快取(每次切個股重抓 FinMind 3 段季報)→ `@st.cache_data(ttl=TTL_3DAY, max_entries=64)`(2-A④) ⑧同檔法人 SDK `except Exception` 靜默吞 → 補 log 後走 raw fallback,行為不變(§3.3) ⑨`chart_plotter._get_revenue_range` 3 個無條件除錯 print 移除(僅留 except 分支 log)。
- **公式/正名 3 修**:⑩Bollinger σ 統一母體標準差 `std(ddof=0)` 共 5 站(scoring_engine squeeze / tech_indicators×2 / v5_modules;原 pandas 預設樣本 σ 使帶寬虛胖 ~√(20/19)≈2.6%;bw_pct 為百分位排名,rank-invariant 不受影響)(3-B) ⑪`scoring_engine.sharpe_20` 註解正名「20 日期間 Sharpe,非年化」(MOM_SHARPE_GOOD 門檻本就對此值校準,零行為變更) ⑫`exit_signals._weekly_macd_turn_negative` docstring 標註 3/5/3 為樣本受限的非標準代理,不可與券商週 MACD 對照(升級真 12/26/9 需 ≥35 根週K ≈175 日,屬模型變更 → 待核准)。
- **不變量/監控 2 增**:⑬`config.WEIGHT_TABLES` 三態 6 因子權重和=1 **import 時 fail-loud** 驗證(§4.2;手調忘配平 → 啟動即炸並指名哪一態,而非 stock_score 悄悄整體縮放) ⑭`@monitored` 擴編 5→7:`fetch_chip_concentration`(💰 籌碼/weekly)+ `fetch_share_capital`(🏢 個股財報/quarterly)進診斷監控面板;兩者 registry key 為動態 per 股(scanner B5 `[個股] {sid} | …`),固定填必孤兒誤報 → 依 fetch_monitor 規矩誠實留 None。category 走 `shared/data_categories` SSOT 常數。
- **修中之修**:⑦裝飾時 `TTL_3DAY` import 未落地(前輪腳本中斷遺失)→ 新回歸測試當場抓到 NameError 補齊(data_loader:46) — 測試先行價值實證。
- **回歸網**:`tests/test_review_fixes_v19_105.py` 21 test(runtime 行為 + source-scan 雙鎖:÷0 卡/75% 條寬/coerce 四態/yf_proxy 源掃/attempts=2/TTL_3DAY 裝飾/權重和/ddof=0 數值對照/監控登錄/正名註解/print 淨空)。ruff:13 個改動檔 229→228(淨 −1),新測試檔 0 錯。

## 🧷 2026-07-11 scripts/ sys.path guard 通用鎖 + 季度校準報告真資料重生（v19.103）

user 跑「Recalibrate Macro Thresholds (Quarterly)」按鈕 → `calibrate_macro_traffic.py` 炸 `ModuleNotFoundError: No module named 'src'` — **同 v19.101 病因第二個現場**(`python scripts/xxx.py` 直跑 sys.path[0]=scripts/,無 repo root)。

- **修**:calibrate_macro_traffic 加 repo-root sys.path guard(scripts/ 全面盤點:15 檔中僅此檔「有 src import 無 guard」,其餘 5 檔早有)。
- **通用不變量鎖(防第三個現場)**:`tests/test_review_fixes_v19_103.py` 參數化掃描**全部** scripts/*.py — 凡含 `src.*` import 必須有 guard,未來新 script 漏 guard 在 CI 直接紅,不必等生產炸。
- **功能驗證(本地跑到底)+ 報告重生**:修後本地實跑季度校準完整完成,`MACRO_CALIBRATION.md` 從「TWII-only DEMO **合成資料**」重生為「**Cache enriched 真資料**(TWII+FinMind 籌碼/M1M2,337 有效日)」:score↔ret20 corr **+0.376**(舊合成 −0.452!)、🟢 precision 56.6%(舊 43.9)、🔴 recall 83.3%(該防禦時 5 次抓到 4 次)。**開啟整條校準線的 −0.452 誤導文件正式被真資料版取代** — v19.102 新權重與真實市場同向,弧線完整閉合。
- 純 script guard + 測試 + 報告重生,無 SSOT 常數/公式變更(plain run 不寫 macro_thresholds.json;門檻優化屬 `--optimize` 路徑,user 之後可再按按鈕跑)。

## 🏁 2026-07-11 紅綠燈權重校準採納 — Phase 3 收官（v19.102）

管線全通:user 於 Actions 跑 bootstrap(20 年真資料齊)→ Calibrate 產出提案 → AI 審核通過 → user 核准**方案 B** → 本次落地。**−0.452 議題正式結案**(合成資料假象;真實資料 AUC 0.753)。

- **提案審核(全過)**:真實 2006~2026、n=4748(含 2008/2020/2022)、val **AUC 0.753**、overfit_flag **False**(fold 方差 0.144、無符號翻轉)、λ=0.01、方向正確(低廣度→該防禦)。本地用同 parquet 復算**一字不差**(§4.3/§5)。**關鍵發現**:①jqavg:score 相對重要性 ≈ 60:40 ②**fnet 對 20 日回撤零預測力**(+0.0006/億,方向微偏反)— 原 +20 bonus(佔滿分 1/5)無資料支撐。
- **SSOT 常數(shared/signal_thresholds)**:`HEALTH_WEIGHT_JQ` 0.4→**0.6**、`HEALTH_WEIGHT_SCORE` **0.4**(不變)、`HEALTH_FNET_BONUS` 20→**0**(常數+公式形狀保留供未來重校準)。權重和=1.0(同步治癒 CLAUDE.md §4.2「權重和=1」漂移)。
- **修除5錯配(macro_helpers)**:score 正規化除數自 `CONFIDENCE_SOURCE_COUNT`(5,借用錯配)改 `mkt_info['max_score']`(market_regime 真滿分 4/6,預設 4.0)— 預設模式 score 現在到得了 100。`CONFIDENCE_SOURCE_COUNT` 保留其真用途(信心度 :163)。
- **對帳同步(health_reconcile Method B)**:改「兩組件等權平均」`(jqavg + score/max×100)/2`,fnet 退出計分(參數保留向後相容)、加 `max_score` 參數 — 否則 A 已歸零 fnet、B 仍 1/3 等權 → 常態偏差恆告警=噪音。`risk/reconcile` 第三份(診斷頁)吃 SSOT 自動跟(v18.397 對齊的紅利),僅 label 去寫死。
- **門檻後續**:HEALTH_DEFENSE_THRESHOLD=35 / BULL_MIN_SCORE=4 是對舊分布校準的;既有**季度 recalibrate**(每季首日 cron)會對新分布重調,或 user 可手動觸發 Recalibrate workflow 提前完成。
- **回歸網**:`test_review_fixes_v19_102.py` 6 test(常數採納/權重和=1/提案存在證據鏈/公式 source-scan/預設模式滿分可達 100/A-B 典型對齊);`test_macro_helpers`+2、`test_health_reconcile` 全面改版(fnet 忽略/max_score 參數/兩組件)、`test_reconcile` 期望值更新。四檔 143 passed。ruff 零新增(macro_helpers 既有 13 錯 baseline 同數)。

## 🩹 2026-07-11 校準資料鏈三連修：workflow deps ×2 + m1m2 舊路徑 import 真因（v19.99~v19.101）

user 實跑 Phase 3 按鈕逐關回報,三輪對症修（v19.99/100 為 yml-only 未記 STATE,此處補記）:

- **v19.99**:①calibrate workflow 缺 bs4（手挑依賴清單 → 改裝整份 requirements.txt=依賴 SSOT）②health-history workflow `git add` 對 gitignored/不存在路徑 fatal 128 → 逐檔「存在才 add -f」。
- **v19.100**:macro-history workflow 同改整份 requirements（三個資料 cron 從此一致）。**當時誤診 m1m2 死因為 bs4** — 修完仍死,見 v19.101。
- **v19.101（真因）**:`scripts/update_macro_history.py` 的 m1m2 段用**v18.359 檔案搬家前的舊頂層路徑** `from proxy_helper import` / `from tw_macro import`,根目錄 shim 已刪 → **自搬家起恆 ImportError,CBC 段靜默跳過數月**;且 `except ImportError` 吞掉 exception 內容只印固定字串（§1 反例）→ 誤導 v19.100 誤診。修:①script 頂部加 repo root 進 sys.path（scripts/ 直跑時 sys.path[0]=scripts/）②三處舊路徑改 `src.data.proxy.proxy_helper` / `src.data.macro.tw_macro`（line 90 的 `_fetch_url_via_proxy` 之前靠直連 fallback 僥倖活著,一併正名）③except 改印 `{type(e).__name__}: {e}`。本地驗證:fetch_finmind_m1m2 現在**過 import 打到 CBC 網路層**（sandbox 403 預期;Actions 有 PROXY_URL secret）。
- **bootstrap 戰果（user 實跑）**:twii_ohlcv **4887 rows（2006→2026 二十年）**+ finmind_inst/margin 各 4912 rows 已 commit 進 main — 校準四塊資料到位三塊,只差 m1m2 等本修 merge 後重跑。tw_pmi 段 dgtw 404/500 為外部端點掛,校準不需要,§-1 不擴 scope。
- **回歸網**:`tests/test_review_fixes_v19_101.py` 5 test（舊路徑禁用 source-scan/新路徑存在/sys.path guard/§1 錯誤訊息帶 exception/新路徑符號可解析）。

> ⚠️ **版號撞號註記(2026-07-11)**:本日兩條並行分支各自遞號,`v19.86~v19.90` 出現兩組 —
> **A~E/校準線**(claude/review-modify-suggestions-7vygyp,下方第一批條目)與
> **選股網線**(claude/dazzling-turing-QxI9m,下方第二批條目)。閱讀時以「主題+分支」區分;
> 為不竄改已推送的 commit 訊息,兩組版號原樣保留,後續版號自 v19.98 起單線續號。

## 🔧 2026-07-11 macro-history cron 白跑 bug 修 + 校準 Phase 3 一鍵化（v19.97）

user 問「Phase 3 這要如何做?」→ 查證發現**前置真 bug**,一併修:

- **Bug（實錘）**:`update_macro_history.yml` 每日 cron 的 Commit 步驟 `git add data_cache/` 被 `.gitignore:39`（v18.461 引入 `data_cache/*.parquet`）蓋掉 → **每日 no-op,origin/main 上 0 筆「🤖 每日總經歷史增量」commit**——cron 抓的 20 年歷史每天隨 runner 蒸發。這正是 MACRO_CALIBRATION 只有「TWII-only 合成資料」可用的根因（真實快取從未存在）。修:`git add -f data_cache/`（強制納管 parquet+metadata;CLAUDE.md §5 本來就定「歷史運算用凍結快照 data_cache/ parquet」,gitignore 該條與憲法牴觸）。fundamentals 季快照不受影響（`data_cache/*.parquet` pattern 不匹配子目錄,故它一直正常 commit）。
- **新增 `calibrate_health_weights.yml`（workflow_dispatch 手動按鈕）**:跑 `scripts/calibrate_health_weights.py` → commit `MACRO_HEALTH_WEIGHT_PROPOSAL.md` 回 repo 供人審。缺 parquet 時 script SystemExit 明講缺什麼（§1）。deps 含 streamlit（`src/services/__init__` 急載 daily_checklist 無條件 import streamlit,CI 模擬驗證過;裝整包比繞 package `__init__` hack 乾淨,§8.1 step6）。
- **Phase 3 操作路徑（全按鈕化,user 只要點）**:① merge PR ② GitHub Actions →「Update Macro History (Daily)」→ Run workflow → **bootstrap=true**（初次建 20 年）③ 跑完後 →「Calibrate Health Weights (Manual)」→ Run workflow ④ repo 多一筆 🤖 提案 commit → 交 AI/人審 AUC/overfit_flag → 過了才改 signal_thresholds 3 權重。**依賴警語**:步驟② 抓數據走 NAS proxy + FinMind secrets——若 NAS proxy 掛（A-1 待查）bootstrap 會部分失敗,run log 會誠實顯示。
- **無 python 源碼變更**（純 yml + 文件）,測試面不受影響。

## 🛰️ 2026-07-11 批次4 Item1+2：@monitored fetcher 自我登錄 + 孤兒 set-diff（v19.96）

user AskUserQuestion 核准「Item1 最小版＋Item2;3/4/5 drop」。§8.1 設計先核准再落地:

- **根因（兩次實案）**:診斷頁靠 3 份**手寫**清單（`DATA_REGISTRY` / `data_registry_scanner` 硬編掃描表 / `health_inspector` 18 個 `_g_add`）,新 fetcher 漏登即隱形 — B5 v19.75（籌碼集中度等 3 項未登錄,抓壞診斷不亮紅）+ S13 v19.78（patch 誤刪 B5 補登項）。
- **Item1 最小版:新增 `shared/fetch_monitor.py`（純 stdlib,零 streamlit/零 I/O）**:
  - `@monitored(name, category, frequency, registry_key)`:**import 時**自我登錄 metadata（從未被呼叫也顯示「未執行」,不再隱形）;每次**真實**呼叫記 status/rows/耗時。**放置在 `@st.cache_data`/`@_ttl_cache` 之「內」** → cache hit 不觸發,last_* 一律 = 最後一次真實外抓（誠實語意）。
  - **§1**:fetcher raise → 記 failed 後**原樣 re-raise**（不吞）;registry 寫入失敗只 stderr log,絕不影響 fetch 主流程。
  - `get_monitor_registry()` accessor（回 copy 防 UI 誤改）。
  - **placement refinement**:§8.1 原設計寫 `src/data/core/`,因該包 `__init__` 急載重量級 data_loader,依 `shared/cache_layer.py` 先例改置 `shared/`（L0 式 utility ← L1 import,依賴方向更乾淨,無迴圈）。
- **裝上 5 個高風險 fetcher**:`fetch_tw_pmi`（macro_core,9 源賽跑）/ `fetch_business_indicator_series` + `fetch_ndc_signal_history` + `fetch_ndc_leading_index`（tw_macro,FinMind NDC 鏈）/ `fetch_margin_balance`（daily,6 段 fallback）。monthly_revenue 為 cached **method**（`_self` + hash 複雜）,最小版不硬裝（§8.1 step6）。
- **Item2 孤兒 set-diff**:`find_orphans(present_keys)` — 已監控且宣告 `registry_key`,但該 key 不在 `session_state['data_registry']` → 孤兒（= 有在抓但診斷清單沒它的列,B5/S13 類 bug 自動亮）。`registry_key=None` 者誠實跳過不猜。
- **診斷頁接線**:`data_registry_panel.render_fetch_monitor_panel()`（L5 純讀 accessor）— 監控表（狀態燈/最後真實抓取/rows/耗時/錯誤）+ 孤兒警示,app.py 資料診斷 tab 掛在資料源清單後。
- **3/4/5 依 user 決策 drop**（§8.1 step6 記錄）:Item3 跨 Tab 單例=臆測（StockDataLoader 已 `@st.cache_resource`,其餘 module-level 或刻意 rerun 重建零 I/O）;Item4 並行化=PMI 早已 9 源 ThreadPool 並行,margin/月營收備援雲端 geo-dead 並行零收益+有優先序破壞風險;Item5 DataManager=app.py 現 752 LOC thin orchestrator + **EX-PASSTHRU-1 憲法明文預先否決**此抽象。
- **回歸網**:`tests/test_fetch_monitor.py` 14 test（import 登錄「未執行」/成功記 ok+rows+ms/失敗記 failed+re-raise/None→0·scalar→None 不偽造/wraps 穿透/accessor copy;孤兒 4 態;production wiring source-scan:5 fetcher 已裝+cache 內側順序+診斷頁接線+import 副作用實登錄）。margin/tw_macro/macro_core/registry 109 passed。ruff:新檔 clean,4 個被改 production 檔 baseline 比對零新增。
- **A~E 全收**:批次1 ✅ 批次2 ✅ 批次3(a)(b)(c) ✅ **批次4 ✅**（Item1+2 最小版;3/4/5 user 決策 drop）。

## 📊 2026-07-11 批次3(a) 布林突破量能確認（v19.95）

user AskUserQuestion 核准「加量能 gate」。§7 數學式先確認再落地:

- **問題**:`detect_bollinger_breakout`（v5_modules,Task 9）docstring 一直聲明吃 `volume` 欄但函式體**從未用** — 「🔴 布林突破爆發」不看量,無量假突破也給爆發買點。
- **修（位移,已授權）**:加 `vol_ratio = 今量 / 20 日均量`（mirror 既有 `check_fake_breakout` pattern;gate 用**既有 SSOT `VOLUME_RATIO_SURGE=1.5`,不新增常數**）。`near_upper 且 bw>3` 分流:①量增 ≥1.5× → 🔴 突破爆發（msg 帶「量增 N×確認」）②量不足 → **🟡 布林突破待確認（慎防無量假突破）**（原 🔴 降級）③缺 volume 欄/均量無效 → `vol_ratio=None`（**誠實未知,不偽造 1.0**,§1）維持舊 🔴 行為 + msg 標「量能未知」。
- **schema-additive**:dict 加 `vol_ratio` / `volume_confirmed` 兩鍵,既有 caller（section_health_score 顯示）無感。非突破路徑（收縮/靠近上軌/正常）零改動。
- **回歸網**:`tests/test_review_fixes_v19_95.py` 6 test（有量🔴+ratio;量不足降🟡;缺欄維持🔴標未知;非突破路徑不受影響;schema 契約;全 0 量不除零不確認）。既有 `test_pr_j3_smed_high_risk` 併跑 23 passed。ruff v5_modules 零新增（既有 23 錯非本次,baseline 比對同數）。
- **A~E 進度**:批次3(a) RSI/ATR ✅ + KD ✅ + **布林量能 ✅**(本次,3(a) 全收)/ 下一步 批次4 Item1 monitored 裝飾器（user 已核准最小版+Item2）。

## 📈 2026-07-11 批次3(a) KD 鈍化背離（偵測 + 接進評分 + drift 修）（v19.94）

user AskUserQuestion 核准「偵測＋接進評分」+「修 exit_signals 70→80 drift」。§7 數學式先確認再落地:

- **新 L2 `analyze_kd_state(df)`（tech_indicators）**:偵測 KD 鈍化 + 背離,dict-or-None + stderr log（同儕 calc_kd/calc_bollinger 契約,不 raise）。
  - **鈍化(passivation)**:K 連 `KD_PASSIVATION_DAYS(3)` 日 ≥ 80（高檔鈍化=強勢續漲,非賣訊）/ ≤ 20（低檔鈍化）。
  - **背離(divergence,兩窗高低點法,避脆弱單點 pivot)**:最近 `KD_DIVERGENCE_LOOKBACK(40)` 日切兩半——頂背離(空)=後半價高點>前半但 K@高點<前半;底背離(多)對稱。
- **接進健康評分（位移,已授權）**:`scoring_helpers.calc_health_score` KD tier（15 分）分流——高檔黃叉(K>D,K≥80)遇①**頂背離→降 5**（真警訊）②**高檔鈍化→維持 15**（強勢續漲不誤扣,原一律 8）③否則注意 8;低檔死叉遇**底背離→加 13**（反轉向上,原 10）。`analyze_kd_state` 回 None（資料不足）→ 退回原分級（向後相容）。純黃金交叉(K<80)不受影響。
- **順帶 drift 修**:`exit_signals.py:96`「KD高檔死叉」寫死 `70` → 引 SSOT `KD_OVERBOUGHT_LEVEL(80)`,消 §3.3 漂移。
- **新 SSOT 常數**:`KD_PASSIVATION_DAYS=3` / `KD_DIVERGENCE_LOOKBACK=40`（signal_thresholds）。
- **§7 邊界**:lowercase OHLCV;資料不足 period+3 → None;NaN 對齊 dropna;兩窗需 aligned≥40 才算背離（不足不偽造）。§8.2 分層:tech_indicators/scoring_helpers 同 L2,無上行 import。
- **回歸網**:`tests/test_review_fixes_v19_94.py` 13 test（鈍化高/低/不足/震盪;頂/底背離;wiring monkeypatch 6 態:高檔鈍化15/頂背離5/無訊號8/底背離13/低檔10/純黃叉15;drift 源掃描）。`test_exit_signals` 高檔死叉 fixture k=80→82 對齊新門檻。scoring/tech/exit/health 549 passed。ruff 對 4 檔零新增（tech_indicators 既有 1 個 E741 非本次）。
- **A~E 進度**:批次3(a) RSI/ATR ✅(v19.89) + **KD 鈍化背離 ✅**(本次)/ 下一步 布林量能確認 → 批次4 Item1 monitored 裝飾器。

## 🚦 2026-07-11 紅綠燈權重重設計 Phase 2：離線校準 CLI（scripts/calibrate_health_weights）（v19.93）

user「請繼續」→ 續 Phase 1（v19.92）落地 Phase 2 wiring（仍在已核准 Path 1 範圍內）:

- **新增 `scripts/calibrate_health_weights.py`（scripts 層 orchestrator）**:讀 `data_cache/{twii_ohlcv,finmind_inst,finmind_m1m2}.parquet`（update_macro_history 既有產出）→ 重建 3 特徵 → walk-forward 擬權重 → 寫 `MACRO_HEALTH_WEIGHT_PROPOSAL.md` 給人審。**不改任何 SSOT 常數**（Phase 3 人審後才動）。
  - **score 重建 SSOT parity**:`reconstruct_score` 逐日呼**真** `market_regime`（L3）,`_ma_flags` 算 MA60/120 的連 3 日站上/跌破 + 斜率,外資/廣度/m1m2 對齊。`score_norm = score/max_score×100`（用真 max_score 4/6）**即修 health 原本除以 5 的錯配**（對齊 user ③）。
  - **PIT-safe（§2.3）**:外資 backward merge T+1（tol 7D）、m1b_m2 月頻 backward 40D,無 lookahead。
  - **§8 分層**:score 重建含 L3 呼叫 → 置於 scripts 層（L2 不得 import L3）；L2 純函式維持零 I/O。
  - **§1 fail-loud**:缺 parquet → SystemExit（不用合成資料）；樣本不足/單一類別 → fit raise。
- **§8.1 step6 反過度設計**:**砍掉原規劃的 `update_breadth_history.py` + `breadth_history.parquet`** — jqavg 由 twii_ohlcv O(n) 即時重算,獨立 parquet+cron = 用不到的抽象。Phase 2 收斂為單一 script。
- **L2 小重構**:`health_calibration` 抽 `ad_ratio_from_twii`（日 ad_ratio,market_regime ④ 用）,`breadth_from_twii` 改呼它取 5 日均（輸出不變,Phase 1 19 test 全綠）。
- **誠實限制**:真實擬合在**部署 cron**（沙箱無 parquet + egress 擋）;in-session 只單測純函式。**下一步（Phase 3）需 user 於部署跑 `python scripts/calibrate_health_weights.py`** 產出提案 → 人審 AUC/overfit_flag → 才改 3 權重常數。
- **回歸網**:`tests/test_calibrate_health_weights.py` 8 test（_prep_close 去重／_ma_flags／**強勢上升→真 market_regime 滿分 6/6 非循環 parity**／MA120 前 NaN／外資 backward 無 lookahead／特徵表欄位／單一類別 raise／鋸齒混合類別擬合+提案渲染）。calibrate+Phase1 27 passed。全套零破。ruff clean。

## 🚦 2026-07-11 紅綠燈權重重設計 Phase 1：health_calibration L2 純函式（v19.92）

user 於 AskUserQuestion 定案 Option B 後續 4 決策 + 核准 Path 1（建校準管線）。§8.1 架構先設計(禁寫 code)→ §7 數學式 user 確認照定義走 → 本次落地 **Phase 1（可 in-session 驗的「機器」）**:

- **user 定案 4 決策**:① 目標函數=**規避回撤·風險姿態**(燈學「該防禦嗎」非報酬預測器)、② 時界=**20 交易日**、③ 特徵集=**先維持現 3 輸入**(jqavg/score/fnet)+修除5錯配、④ 資料=**先建 jqavg 歷史重建管線**。§7 三數學式(jqavg 重建/20 日最大回撤真值/logistic 擬合)user 接受照定義。
- **關鍵誠實前提**:MACRO_CALIBRATION −0.452/1.6% 證據**是 TWII-only 合成 demo**,非真實資料 → 第一步是**取得真實資料**,不是照 −0.452 反推權重(違 §1)。且 live `jqavg` 真相=`ad_ratio.tail(5).mean`(jingqi_calc:43),而 `ad_ratio` 本身重度是 ^TWII proxy(fetch_adl ①)→ 重建可**複用既有 twii_ohlcv.parquet + 鏡像 proxy**,成本低。
- **新增 `src/compute/macro/health_calibration.py`（L2 純函式,numpy+pandas,無 I/O/streamlit/requests）**:
  - `breadth_from_twii()` — 由 ^TWII 重建 jqavg(鏡像 fetch_adl ① proxy「±1%≈±150 家、900 基準」+ jingqi 5 日均,SSOT parity；此為 live jqavg 的 PROXY tier)。前 5 日 NaN 不偽造(§1)。
  - `risk_posture_label()` — 未來 20 交易日最大回撤 ≥ θ_dd(預設 8%,待 OOS)→ y∈{0,1}。尾端不足窗 → NaN。
  - `fit_health_weights()` — walk-forward L2-logistic(**純 numpy 手刻,不引 sklearn/scipy**=§8.1 反過度依賴)+ inner-CV 選 λ + robustness voting + overfit guard。**labeled 樣本<60 / fold<3 / 單一類別 → raise**(§1 fail loud,不回偽權重)。
- **順帶抓到 1 個自寫 bug**:AUC 計算原用最後 λ 的 intercept 配 best_w(不同 λ)→ 改追 best_b 對應。
- **存檔（user 核准）**:`MACRO_HEALTH_REWEIGHT_PROPOSAL.md` 完整方法論 + §7 數學式 + §8 架構 + 落地 3 Phase + 誠實限制。
- **誠實限制（寫入 proposal）**:真實擬合在**部署 cron**(沙箱無 twii_ohlcv.parquet + egress 擋)；in-session 只交付「可單測演算法」。Phase 2(scripts/update_breadth_history + calibrate_health_weights,cron 執行)+ Phase 3(人審 proposal→改 3 權重常數,順解除5錯配)待做。文件漂移(CLAUDE.md 6-factor/sum=1.0、SPEC health<40)Phase 3 一併修。
- **回歸網**:`tests/test_health_calibration.py` 19 test(jqavg 重建數值/NaN 頭/index；回撤真值觸發/θ 可調/尾端 NaN；logistic 擬權重符號/AUC/樣本不足 raise/單類別 raise/NaN drop 不填/輸出契約；L2 純度掃描)。全套 **3062 passed / 10 skipped** 零破。ruff 兩檔 clean。

## 💰 2026-07-11 A~E backlog 批次3(b)：融資維持率 Option A（追繳線=強平線 130 + 撤銷線 166）（v19.91）

user 於 AskUserQuestion 拍板 **Option A「追繳 130＋撤銷 166」**。ETF 質借模擬器維持率門檻校正為台股法規標準值:

- **問題**:`etf_margin_simulator` 原用 `MARGIN_CALL_RATIO=140`(追繳)/ `LIQUIDATION_RATIO=130`(強平)兩級,**非台股法規標準**。台股實務:整戶維持率跌破 **130% 追繳線**發追繳令,須 2 日內補足至 **166% 撤銷線**,未補足即強平(第七/八份公式表點名)。「強平在哪個比率」原是模擬建模選擇(法規是追繳後未補足才強平,非固定比率),故憲法保留 user 拍板。
- **修(Option A 單線模型)**:`MARGIN_CALL_RATIO=130.0`(追繳線)、`LIQUIDATION_RATIO=130.0`(=追繳線,同線)、新增 `MARGIN_RESTORE_RATIO=166.0`(撤銷線,教學顯示)。`SimulationParams` 加 `restore_ratio` 欄。維持率檢查改**單分支**:`borrowed>0 且 m_ratio < 130` → 視同「追繳令發出且本模擬未建模補足 → 強制平倉」,**同一事件同時計入 `margin_call_count` 與 `liquidation_count`**,`status="liquidated"`,event 文字點名追繳線 130 + 撤銷線 166(教學)。常數為本功能單一 domain-local SSOT(唯一 caller = 引擎 + UI),不外移 shared(§-1:單功能常數移共用層 = 多餘抽象)。
- **UI 教學同步(撤銷線 166 教學顯示,Option A 要求)**:`tab_etf_margin_simulator` caption + 強平次數卡 help 改敘「跌破 130% 追繳線 → 發追繳令,補足至 166% 撤銷線,未補足即強平」,params 顯式傳 `restore_ratio`。
- **回歸網**:`test_etf_margin_simulator_coverage.py`(常數 SSOT 改 130/130/166 + 改寫 `test_below_call_line_increments_both_counters` 驗兩計數器同增+event 文字)、`test_etf_margin_simulator.py`(`test_below_margin_call_threshold` 128% 對齊 130 線)。兩檔 69 passed;全套 **3043 passed / 10 skipped** 零破。ruff 四檔 clean(順手拔 coverage 檔既有未用 `import math`)。
- **A~E 進度**:批次1 ✅ / 3(c) ✅ / 批次2 ✅ / 3(a) ✅ / 3(b) calc_rs_score ✅ + **融資維持率 ✅** / **3(b) 剩紅綠燈權重重設計**(user 選 Option B「先草擬方法論給你審」,不動 code,草案下一步交付)/ 批次4 架構待做。

## 🧮 2026-07-11 A~E backlog 批次3(b) 之一：calc_rs_score 近零大盤防爆炸（v19.90）

user 核准「批次3(b)」。3(b) 三項風險分層,本次先落地**無語意歧義**的一項:

- **calc_rs_score 近零分母防爆炸（安全,不動校準）**:`rs = stock_chg / abs(idx_chg)` 原只守 `idx_chg == 0`,大盤近乎平盤(如 N 日僅 +0.01%)時分母近零 → rs 放大數千倍 → 個股小漲即誤判滿分 100。修:新增 SSOT `RS_IDX_FLAT_EPS_PCT=1.0`(signal_thresholds),`abs(idx_chg) < 1%` 一律走**既有絕對漲幅路徑**(不動 RS_BAND 相對強度校準,僅把退化情形導向現成分支)。近零大盤 + 個股 +5% 現正確得 60(絕對路徑)而非爆炸 100;正常大盤(+2.5%)仍走相對 rs 路徑不受影響。
- **回歸網**:`test_review_fixes_v19_89.py` +3(近零走絕對 / 正常走相對 / 源掃描),共 12 test。
- **3(b) 剩兩項需 user 決策(不擅動)**:① **融資維持率 130/166** — 現 etf_margin_simulator 用 140 追繳 / 130 強平,與台股法規(130 追繳 / 166 補足撤銷)不符;但「強平在哪個比率觸發」是模擬建模選擇(法規是追繳後未補足才強平,非固定比率),憲法保留 user 拍板 → 已提問。② **紅綠燈權重重設計**(MACRO_CALIBRATION −0.452 負相關)= 研究級模型重設計,需 user 定方法論(目標函數/權重方案),不盲改 → 已提問。
- **A~E 進度**:批次1 ✅ / 3(c) ✅ / 批次2 ✅ / 3(a) ✅ / **3(b) calc_rs_score ✅**(融資+權重待 user 決策)/ 批次4 架構待做。

## 📐 2026-07-11 A~E backlog 批次3(a)（標準公式）：RSI Wilder + ATR True Range（v19.89）

user 明確授權「批次3(a) 標準公式」+「位移訊號換取和券商可對照」(§7 位移訊號 sign-off):

- **RSI 改 Wilder RMA（SSOT 單點,全 RSI caller 同步位移）**:`compute_rsi` 原 `rolling(period).mean()`(SMA)→ `ewm(alpha=1/period, adjust=False).mean()`(Wilder)。台股所有券商平台一律 Wilder,故 70/30 超買超賣門檻改此後方可與券商數值對照。數學:`AvgGain_t = AvgGain_{t-1}×(p-1)/p + Gain_t/p`。副作用:RSI 全體平滑位移(較 SMA 遲緩、貼近平台);極端全漲/全跌仍 ~100/~0(既有斷言不破)。`tech_indicators.calc_rsi` 委派此 SSOT,一改全動。
- **ATR 改 True Range（新 SSOT `compute_atr`,收斂 2 處直接幅值用途）**:原各處只用當根 `high-low`,漏抓跨日跳空。新 `compute_atr(df, period, wilder=True)`:`TR = max(H-L, |H-prevC|, |L-prevC|)` + Wilder 平滑。**風險分級 ATR%(scoring:130)+ 動態停損 calc_atr_stop(:1083)** 兩處改用之 → 跳空(除權息/隔夜大跌)計入波動,停損距離更貼實(user 授權「停損距離變寬」)。缺 high/low 欄退回 close 不炸。
- **VCP 收縮比刻意不改(§謹慎)**:`calc_vcp` 的 atr5/atr20 保留 high-low range — 其 `VCP_ATR_CONTRACTION_RATIO` 門檻對 high-low 校準,換 True Range 位移比值需重新回測(同 calc_rs_score σ 處理);加註說明,列待若要 VCP 亦 TR 化再一起校準。
- **回歸網**:`tests/test_review_fixes_v19_89.py` 9 test(RSI Wilder ewm 等值 + 異於 SMA + 極端值 + 源掃描;ATR True Range 捕捉跳空 + Wilder/simple + 缺欄降級 + 源掃描;calc_atr_stop functional)。既有 test_tech_indicators/test_risk_control/test_scoring_engine 333 passed 零破(極端值斷言對 Wilder/TR 仍成立)。
- **A~E 進度**:批次1 ✅ / 3(c) ✅ / 批次2 ✅ / **3(a) 本次 ✅** / 下一步 批次3(b) 語意項(calc_rs_score σ / 融資 130-166 / 紅綠燈權重重設計 — 需 user 更多方向)。

## 🚦 2026-07-11 A~E backlog 批次2 收尾（全域紅綠燈時效 gate）（v19.88）

user 核准「批次2 收尾」。全域紅綠燈(app.py 頁面最頂,永遠可見)過期資料 gate 落地:

- **全域紅綠燈時效 gate（行為變更,已授權）**:app.py:481 全域多空紅綠燈原直接吃 `mkt_info`/`jingqi_info` + `cl_ts`(上次一鍵更新時間),無時效檢查 → 使用者隔數日開著舊 session 會看到過期的「多頭市場（可積極操作）」當即時訊號(第八份 §3.1 點名,類比 v18.442 ETF 假折溢價事故)。修:過 `shared/staleness.gate_for_realtime(staleness_days(cl_ts), max_days=1)`,**過期時保留燈色(資料可顯示)但撤下「建議持股 X%」+ 旌旗均值 actionable 建議,改明確「⚠️ 資料已過期,燈號僅供參考 — 請先一鍵更新再操作」**。對齊原則:過期資料可顯示但須標記、不得以「可積極操作」語氣餵當下決策。
- **基金端批次2 已由既有機制覆蓋(不另造)**:Fund 無單一「全域紅綠燈」,其 per-indicator `_freshness`(data_registry,本輪還修過 SLOOS 季頻閾值)+ tab1 AI prompt `[STALE]` 已是成熟時效系統;再造 staleness.py 屬 §8.1 step 6「用不到的抽象」反例,故基金不重複。
- **回歸網**:`tests/test_staleness.py` +1 紅綠燈 gate source-scan(共 23 test);gate_for_realtime 邏輯已由既有單元測試覆蓋。
- **批次2 完整收尾**:SSOT 基礎(v19.87)+ AI prompt [STALE](v19.87)+ 全域紅綠燈 gate(本次)。**A~E 進度**:批次1 ✅ / 3(c) ✅ / 批次2 ✅ / 下一步 批次3(a) 標準公式(user 已授權位移訊號:RSI Wilder / ATR True Range)→ 批次3(b) 語意項。

## ⏱️ 2026-07-11 A~E backlog 批次2（時效閘 SSOT）：shared/staleness.py + AI prompt [STALE] 標記（v19.87）

user 核准「1~4 陸續慢慢做」。批次2 時效閘依 §8.1 設計後落地;本次交付 **SSOT 基礎 + 安全的加法消費者**,行為變更的紅綠燈硬 gate 留作後續分開審查:

- **新增 `shared/staleness.py`（L0 純函式 SSOT）**:`expected_latest_trading_day(today, holidays)`(扣週末 + 可選休市日,**不硬編全年台股日曆** — §8.1 過度設計自評,春節長假等由 caller 注入)、`staleness_days(data, ...)`(多型別:DataFrame/date/str/Timestamp → 距預期最新交易日天數,無法判定回 None)、`gate_for_realtime(days, max_days)`(→ 可否即時用 + 提示;None/超期 fail-safe 排除)、`stale_tag(days, threshold)`([STALE:Nd] AI 標籤)。
- **DRY 收斂**:既有 `app_stock_fetchers._expected_latest_trading_date`(重複的週末退算)改委派 SSOT,介面 0 改。
- **安全消費者(加法)**:`app.py:_build_llm_context` 月度指標(出口/PMI/CPI/NDC)距預期 >40 天者,行前綴 `[STALE:Nd]` — 防 AI 把過期資料當當期講(第八份 §3.1;對齊 Fund 端既有慣例)。順手把 AI prompt 殘留「外銷訂單」對齊 v19.85 正名「台灣出口」。
- **未做(留後續,行為變更需分開審查)**:全域紅綠燈(app.py:481)硬 gate — 過期 mkt_info/jingqi_info 拒絕顯示多空 → 這動到決策顯示,擇期單獨做 + 單獨驗。
- **回歸網**:`tests/test_staleness.py` 22 test(expected_latest 週末/假日鏈、staleness_days 多型別/邊界、gate fail-safe、stale_tag 閾值、shim 委派、AI prompt wiring source-scan)。
- **A~E 進度**:批次1 ✅ / 3(c) ✅ / **批次2 基礎 ✅**(紅綠燈 gate 待續)/ 下一步 批次3(a) 標準公式(RSI Wilder/ATR TR,§7 已給數學式待你點頭位移訊號)。

## 🔒 2026-07-11 A~E backlog 批次1（止血）：NAS proxy SSRF 防護 + fetch_pmi_history 死碼拔除 + CLAUDE.md dataset 正名（v19.86）

user 核准「A~E 陸續修復」。本批取**最安全、自足、不位移訊號**三項落地（架構級 B/會位移訊號的公式 C 依 §7/§8 後續回合先出設計/數學式）：

- **D 安全（NAS proxy SSRF 止血）**:`src/data/proxy/nas_server.py` 兩個洞——(1) `_auth` 的 `if _API_KEY and ...` 在**未設 NAS_API_KEY 時直接放行**(開放代理);(2) `/proxy?url=` 對任意 url 直接 `requests.get`,可打內網/雲端 metadata(169.254.169.254)/localhost = 完整 SSRF。修:新增 `_assert_public_url()` — 解析目標主機 IP,凡私有/loopback/link-local/reserved/multicast 一律 403;`/proxy` 每一跳(初始+每次轉址,`allow_redirects=False` 手動有界迴圈 6 跳)都過 guard,防「公開 URL 302→內網」繞過;未設 key 時啟動大聲警告。**向後相容**:公開站(TWSE/FinMind/FRED/Yahoo)解析為公網 IP → 放行,零誤傷。**已知限制**:不防 DNS rebinding(需 pin 已解析 IP,列後續)。**待 user 決定**:是否「未設 key 硬性拒絕啟動」(涉 NAS 部署行為變更,故本批只警告不強制)。
- **E 死碼（fetch_pmi_history 整刪）**:`tw_macro.fetch_pmi_history` 打 dataset `TaiwanEconomicIndicator`(v19.85 證實不存在),恆回 None 且 **0 production caller**(原 caller merrill_clock 已 v18.359 整檔刪除 → 孤兒);當期 TW PMI 由 `fetch_tw_pmi`(9 源賽跑)供應。整刪 + schemas.py docstring 引用更新。**TW CPI/失業率 fetcher 不刪**——有專屬測試且是 v18.270 刻意加的半成品功能,「刪 vs 接真實源」屬 user 決定的岔路,不擅自摧毀。
- **A-3 文件正名**:兩 repo CLAUDE.md §2.1 把已證實不存在的 `TaiwanEconomicIndicator`/`TaiwanMacroEconomics` 更正為 `TaiwanBusinessIndicator`(NDC)+ 註明 FinMind 無 PMI/出口替代集。憲法漂移收斂。
- **回歸網**:`test_nas_server_coverage.py` +6 SSRF test(metadata/loopback/私有段/非 http scheme/缺 host 擋下 + 公開站放行;fastapi 缺套件時 graceful skip);`test_review_fixes_v19_85.py` +1 死碼刪除掃描 + 假 dataset 掃描擴至 tw_macro。ruff 對 nas_server/tw_macro 零新增(baseline 2 = 現況 2)。
- **A~E 後續批次(已排 task,依序進行)**:批次2 時效閘 staleness.py(§8 先設計)、批次3 公式校正(RSI Wilder/ATR TR/KD 鈍化背離等,§7 先給數學式)、批次4 架構(monitored 診斷登錄/並行化/DataManager facade,§8 先核准範圍)。A-1(NAS 檢查)/A-2(Put/Call 死因)卡在 user 輸入。
## 🐞 2026-07-11 選股網綜合評分失真修：RS 全池覆蓋 + 缺料不灌 0（v19.90）

> 使用者截圖：選股結果 RS分整欄 0，且排序與下方抗跌RS排行（2061 RS 188…）對不上。查為真資料錯誤。

**根因（兩個疊加）**：
1. **RS 只回 top-50**：`run_rs_leader_scan` 內部 `rank_rs_leaders(top_n=RS_LEADER_TOP_N=50, beat_only=True)` → 只回「贏過大盤的前 50 檔動能股」；綜合評分拿它當 RS 來源 → 存活池 274 檔查無 RS → **RS分 全 0**（且那 50 檔多是動能股、與高EPS/缺貨的價值股不重疊 → 排序對不上）。
2. **缺料灌 0 再除全因子數**：`composite_rank_candidates` 對「無資料因子」記 0 分、分母仍算全因子 → 缺貨/RS 只覆蓋 ~50 檔時，其餘 274 檔被灌 0 拉低綜合分 → 整體失真。

**修**：
- **RS 全池覆蓋**：`run_rs_leader_scan` / `_scan_cached` 加 `top_n` 參數；app.py 綜合評分自動掃改 `run_rs_leader_scan(beat_only=False, top_n=RS_SCAN_MAX)` → 回**全存活池** RS σ，存 `_rs_rows_all`（與進階 UI 的 `_rs_rows` top-50 分離）。
- **綜合分改「只平均有資料的因子」**：`_percentile_scores` 缺值不再記 0（改**不放 key**）；綜合分 = 該股有資料因子的平均（缺貨只覆蓋 ~50 檔 → 沒掃到的股不被 0 拖垮）；缺料欄顯示**空白**（非 0）。
- §8：純 L3 服務改 + app.py 組裝；全 if/else（magic-guard 在場）。
- 驗證：33 相關測試（含新增「缺料因子不 0 拖垮」核心測試 + RS top_n 參數 + 既有 RS/缺貨/screener 無 regression）全綠。

---

## 🧹 2026-07-11 選股網簡易版：勾條件 → 一鍵選股（缺貨/RS 自動掃、拿掉手動候選）（v19.89）

> 使用者：「缺貨動能/抗跌RS 由基本面這邊自動掃、不要 USER 額外壓；不要手動候選名單；重新設計成簡易的。」

- **一條龍簡化**：① 基本面優選（自動）→ ② 勾條件（估值/EPS/缺貨/抗跌RS 可複選）→ **一鍵「🎯 開始選股」→ 直接出綜合評分名單**（可下載 CSV）。
- **缺貨/抗跌RS 自動掃**：按「開始選股」時，若勾了缺貨/RS 且 session 尚無結果 → 自動呼叫 `run_shortage_scan` / `run_rs_leader_scan`（掃存活池），不再要求 USER 去「進階」按掃描。
- **拿掉手動候選勾選**：picker 加 `auto_pick` 參數（`_t3_mode = auto_pick or 個股組合輸入`）→ 跳過 multiselect + 額外加碼。籌碼技術×6 改為**選用**深篩（勾了才對前 20 名自動跑，不用手動勾）。
- **進階**：缺貨/RS 完整排行 + AI 三型報告收進「🔎 進階（選用）」摺疊，主流程不再依賴它。
- §8 / 避雷：純 app.py L6 組裝 + picker 加 1 參數（向後相容，預設 False）；全 if/else 語句（magic-guard 在場，app.py 裸三元 0）。
- 驗證：composite 10 單元 + auto_pick render（無 multiselect + 已自動帶入 + 無 exception）+ render smoke / 個股組合 picker 無 regression（24 pass / 2 skip）全綠。

---

## 🎛️ 2026-07-11 選股網 ②：複選因子 + 綜合評分排序（v19.88）

> 使用者：「基本面選完後，讓 USER 點選 估值便宜/高EPS/缺貨動能/抗跌RS/籌碼技術×6，最終才選股。」確認採 **A（綜合評分）**。

- **② 從「單選排序角度」升級為「複選因子 + 綜合評分」**：`st.multiselect` 勾選 估值便宜/高EPS/缺貨動能/抗跌RS（可複選）→ 每因子在存活池內排 0–100 百分位分 → **取平均為綜合分**降冪排序 → 餵 picker 候選。附「綜合評分排行」可展開表（看各因子分）。
- **L3 純函式** `composite_rank_candidates`（+ `_percentile_scores`）：`pd.Series.rank(pct=True)` 算百分位（pe_low 低分高、其餘高分高）；缺料因子該股記 0（§1 不造假）；勾了缺貨/RS 但未掃描 → note 提示但不擋其他因子。
- **籌碼技術×6**：因需逐檔深抓籌碼/技術資料（全 324 池即時算不切實際），維持在 **③「三階段深篩」當最後一關**（不入綜合分），UI 明示。
- §8：純新增 L3 純函式 + app.py L6 multiselect 組裝，重用既有 picker/掃描元件，無新 fetcher、無跨層違規。避開 v19.87 magic 雷（全 if/else 語句，guard 測試在場）。
- 驗證：10 綜合評分單元測試（百分位方向/缺料 0/複選平均/缺掃描 note/空因子/top_n）+ 1 實機 render（複選→綜合→picker multiselect 無 exception）+ 既有候選/magic-guard 無 regression 全綠。

---

## 🚑 2026-07-11 hotfix：選股網 AI 卡裸三元表達式炸整頁（v19.87）

> 使用者截圖：選股網開啟即 `SyntaxError`（app.py:592 `st.markdown(x) if c else st.info(y)`）整頁掛。

- **根因**：v19.86 我把 AI 置頂卡的 if/else 「簡化」成**裸三元表達式語句**。Streamlit 腳本的 magic 會把裸表達式自動 `st.write()` → 對三元結果呼叫 → 執行期炸（AST 合法故 compile-time 測不出，我的 render 測試也沒涵蓋這行）。
- **修**：改回 `if _screener_ai_md: st.markdown(...) else: st.info(...)` 語句 + 加註解警示。
- **防再犯**：新增 `tests/test_app_no_magic_bare_ternary.py`——AST 掃 app.py，禁止任何 `Expr(value=IfExp)`（裸三元表達式語句）。
- 驗證：guard 測試 + 13 相關全綠；AST 掃描 app.py 裸三元 0 處。

---

## 🔭 2026-07-11 個股選股網重設計：3 步直線漏斗（從優選池挑候選）（v19.86）

> 使用者：「個股選股網不喜歡，要從基本面優選前 300 檔再給選股選項，整合這 tab、簡化。」§7/§8 對齊後選 **B（整合＋保留）**。（原記 v19.74，因並行 v19.75~85 合併順延版號至 v19.86。）

**現況病灶**：一個 tab 塞 6 塊；候選清單不是直接來自 324 檔優選池，而是繞「324 ∩ 估值池=146 → PE/殖利率=81 → 取 PE 最低 50」——與「基本面優選前 300」對不上；缺貨/抗跌RS 是兩個各自為政的全市場 expander。

**重設計成 3 步直線漏斗（app.py tab_screener 重組）**：
- **① 基本面優選池（四項全過 324）** — render_prescreen_panel（沿用）。
- **② 從優選池挑候選** — 新增「排序角度」selectbox（估值便宜/高EPS/缺貨動能/抗跌RS）→ `build_candidate_frame` 從 324 存活池依角度排序 → 直接餵 picker 候選（拿掉中間估值池繞路）。
- **③ 三階段深篩** — render_tab_stock_picker（候選來源改「基本面優選」）+ 殖利率確認。
- **🔎 進階主題選股（摺疊）** — 缺貨 + 抗跌RS 完整排行；掃描結果（`_shortage_rows`/`_rs_rows` session）**回饋②的排序角度**（掃完回上方選「缺貨動能/抗跌RS」即帶入候選）。

**分層（§8）**：L3 `fundamental_screener_service.build_candidate_frame`（**純函式**，所有資料 caller 傳入）+ `SCREEN_ANGLE_LABELS`（下拉 SSOT）；app.py 僅 L6 組裝，缺貨/RS/picker 全**重用**既有元件，無新 fetcher、無跨層違規。
**§1 fail-loud**：存活池空 / 掃描未跑 / 掃描與存活池無交集 → 回空 + 精準 note，不炸不造假；pe_low 無 PE（OTC）以 +inf 墊底且不崩（None/NaN-safe 排序）。
**驗證**：11 新測試（4 角度 + None/NaN PE 不崩 + 掃描需先跑 + 交集 + top_n + **實機 render：存活池→候選→picker multiselect 無 exception**）+ 28 服務相關無 regression 全綠。

---

## 🛰️ 2026-07-11 資料異常實診修復：NDC 接 FinMind 官方鏡像 + 假 dataset 拔除 + 出口正名（v19.85）

user 實機截圖回報 4 筆資料異常(台灣出口 YoY 未取得 / 台灣製造業 PMI 未取得 / NDC 燈號+分數 101 天前 / 外銷訂單卡「待取得」但診斷清單沒出現)。逐鏈活體診斷(沙箱 egress 全 403 → 改以 FinMind SDK 2.0.4 枚舉 + WebSearch + 基金 repo 交叉證據)結論與修復:

- **根因 1(修,NDC 101 天 stale)**:NDC 鏈 production 其實抓成功,是 **StockFeel 文章本身停在 2026 年 4 月號**(WebSearch 實證文章標題「2026年4月景氣燈號(最新)!」;國發會 5 月燈號 6/27 已公布)— 第三方文章天生落後 1~2 月。修:`tw_macro.fetch_business_indicator_series()` 新增 FinMind **`TaiwanBusinessIndicator`**(國發會官方鏡像;SDK 2.0.4 枚舉+官方文件雙重驗證存在,欄位 monitoring 分數/monitoring_color 燈號/leading 領先指標),插為 `fetch_ndc_block` 方案 0 + `fetch_ndc_signal_history`/`fetch_ndc_leading_index` PRIMARY(dgtw 降 fallback)。附帶:燈號字串官方化(`signal`/`color_latest` 欄,原恆 None),分數沿用既有 [9,45] sanity。token 走 env(app.py 啟動已同步 secrets→env;tw_macro 鐵則不 import streamlit)。
- **根因 2(修,§3.3 反捏造)**:出口鏈「方案 FM」與 PMI 鏈「方案 5」打的 dataset **`TaiwanEconomicIndicator` 在 FinMind 不存在**(SDK 2.0.4 Dataset 枚舉 + 官方文件皆無此名)— 兩段自建立起從未命中,只浪費 API 呼叫;v18.177 註解「TaiwanMacroEconomics 改 Sponsor 付費」同屬誤診(該名亦不存在,付費牆 dataset 仍會列文件)。修:兩段拔除(PMI 10→9 源,出口 6→5 段),FinMind 無出口/PMI 替代 dataset 故不補段;`_finmind_macro_series` 舊 fallback 從兩個 NDC fetcher 移除。`fetch_pmi_history`(0 production caller)與 TW CPI/失業率 fetcher 同病 — 僅加註+registry 如實標註,整刪/新源列待核准(§-1)。
- **根因 3(修,同鍵不同名)**:總經卡「外銷訂單 YoY」與診斷清單「台灣出口 YoY」是**同一個資料鍵 `tw_export`**(海關出口年增率,財政部) — 診斷清單其實有列(紅色第一筆),名稱對不上讓 user 以為漏列。修:section_mid 卡片/警示/策略敘事全數正名「台灣出口」(資料語意本來就是海關出口,非經濟部外銷訂單);health_inspector 端點筆誤 657S→664S、來源描述同步(PMI 9 段/NDC 三源/出口 5 段)。
- **根因 4(據實回報,不擅動)**:出口/PMI 其餘段(stat.gov.tw/MOF/data.gov.tw/CIER/MacroMicro)全是 TW 官方站/防爬站,Streamlit Cloud 境外 IP 被 WAF/geo 擋 → 存活依賴 NAS proxy;現況全滅與 NAS proxy 狀態一致。**建議 user 開「API 診斷」頁檢查 NAS proxy** — 它是出口/PMI 兩卡的共同前置。FRED XTEXVA01TWM664S 段:OECD MEI 已停供、FRED 端 2024 起凍結/下架(WebSearch 佐證)— 保留待證(失敗無害),docstring 加警語。
- **同輪併入:第八份建議書查證(595 行全面稽核;路線圖 8 版有 6 版與前七輪待核准重疊)**。屬實即修 5 項:
  - **月營收 MOPS 段無閘門(屬實,比報告寫的更廣)**:方案A 缺 `df_revenue is None` 閘 — 連 FinMind 成功的快樂路徑都白打 4 支自承全 404 的 year-file URL(`t21sc03_{西元年}_0.html` 亦非 MOPS 實際檔名模式)。修:range 條件化閘門(零重排);整段移除/改真檔名列待核准。
  - **calc_bollinger `bw=(upper-lower)/ma` 無 0 防護(屬實)**:ma=0 時 Series 除法回 inf(不 raise,穿過 except 與 isna 檢查)→ `ma.replace(0,nan)` 走既有 None 誠實路(§4.4;上游 close>0 過濾使實務觸發率極低,屬廉價硬化)。
  - **五力雷達 `int(v)` 裸轉型(半屬實)**:no-AI 路徑恆 int 安全,但 AI 路徑 radar_scores 來自 LLM JSON — `int(None)`/`int("80.5")` 直接炸整個財報體檢區塊。逐值 `int(float(v))` 防護,壞值以 0 呈現。
  - **趨勢分數 docstring 宣稱斜率、實作沒有(屬實)**:「MA 斜率加分(向上彎折)」從未實作(無 shift/diff)→ docstring 文實對齊;真加斜率=評分位移,列待核准。
  - **ADL registry 標示不實(屬實)**:條目寫 TWSE MI_INDEX,實際主值為 ^TWII 漲跌幅反推估算(fetch_adl 自承+is_proxy 旗標)→ registry 正名揭露「估算」。
- **第八份不適用清單(證據)**:季報無 cache=**第四次**同誤判(`fetch_quarterly`/`fetch_quarterly_extra` 皆 `@st.cache_data(TTL_1HOUR,max_entries=10)`);`fetch_batch_monthly_revenue` dead=誤判(月營收掃描 Tab+缺口掃描 service 兩個活 caller);`fetch_bps_from_finmind` 查無此函式=誤判(data_loader.py:2440 就在);ad_ratio 死因子=v18.449 已修(現 None 預設+動態權重);法人 fillna(0)=by-design(L373 明文「T86 缺列=無交易=真0」語意註);section_health_score MA NaN=v19.78 S2 已修 2 站(MA5/10 站 NaN 比較恆 False=正確不出訊號,良性);market_regime 假綠燈/ETF 假折溢價/holdings 未 import=報告引用本 repo 自家 STATE 已修事故(v18.442/v18.449/v19.287-288);plot_combined_chart 空 df 閘=不修(唯一 caller df 保證非空,加閘需改雙檔 ROI≈0)。
- **第八份大項待核准(§-1 不擅動;與前七輪重疊項不重列)**:⭐MOPS 段整刪或改真檔名模式(ROC年+月)、⭐monitored 裝飾器強制診斷登錄+孤兒指標掃描器+registry 跨 Tab 單例(P4 家族)、⭐集保/股利/股本/現金流 4 指標補進診斷覆蓋、⭐融資維持率 130/166 正名(涉法規語意由 user 拍板)、⭐MACRO_CALIBRATION −0.452 負相關=紅綠燈權重重設計(模型層)、⭐趨勢分數真加斜率+量能、⭐布林突破加量能確認閂+與假突破交叉驗證、⭐金融股判定改產業別欄位(現為產業查詢主+前綴 fallback)、⭐個股融資補 TWSE MI_MARGN 備援、RSI Wilder/KD 鈍化背離/字串訊號改 Enum/毛利率跨產業/staleness 閘/data_manager/並行化/UX 重構(均前輪已列)。
- **回歸網**:`tests/test_review_fixes_v19_85.py` 19 test(TBI parser ×4、NDC history 鏈 ×2、fetch_ndc_block ×2、假 dataset 掃描 ×3、正名 ×2、第八份:布林 0 價→None+正常路 ×2、MOPS 閘門+雷達防護+docstring 文實+ADL 正名 ×4);`test_tw_macro.py` 2 test 改餵 TBI 寬表、`test_tw_macro_ndc_migration.py` 全檔改釘新鏈序(TBI 主/dgtw 備/死鏈永不呼叫)+補 TBI 缺 leading 欄退 dgtw 邊界。
- **診斷方法註記**:沙箱 egress proxy 對外站全 403,「直接打 endpoint」不可行;本輪證據鏈 = FinMind SDK wheel 枚舉(離線真相源)+ WebSearch(StockFeel 文章日期/CBOE 檔案狀態/dataset 6100 存在)+ 基金 repo production 交叉比對。

## 🚩 2026-07-11 第七份外部 review 查證後修復：旌旗捏造鍵拔除 + 新股 NaN 引導（v19.84）

user 指派第七份建議書(C1-C7 跨專案診斷 + P0-P6 路線圖;品質最高的一份,承認既有 SSOT 治理,但快照仍在 v19.83 merge 前);本 repo 查證:**2 真修 + 1 死 import 清除 / 6+ 已修過或誤判 / 大項待核准**。

- **旌旗 pct 捏造鍵拔除(§1 寧缺勿假,本輪最高價值)**:`jingqi_calc` + `section_short` 兩處 inline 備援寫入器(v18.392 抽出殘留)共 3 站,全都寫入 `pct60/120/240 = ratio×0.9/0.8/0.7` — 站上季線/年線比例**無此換算關係**,純捏造;且全 repo **0 讀者**(唯一 consumer `macro_helpers` 只讀 `avg`)= 假數字 + 死資料雙重理由。三站同步刪 4 鍵;`大盤估算` 備援(40+漲日×5)保留 — 它帶 `source` 旗標屬「有標記的代理估算」(類比 M1B ^TWII proxy tier 前例),report 要求改 None 屬政策變更列待核准。順手補 section_short TWSE 即時區塊裸 `except: pass` 的 §3.3 log。
- **新股 MA NaN 引導(3-1)**:`section_kline_chart` 趨勢建議段原 `float(df2['MA20'].iloc[-1])` 無 notna 守衛 — 上市 <100 天新股 MA100 整欄 NaN → 顯示「MA20 nan」且 `classify_trend_4tier` 的 NaN 比較全 False 落錯層級。補 isna 守衛 → 白話引導「🌱 上市初期:歷史僅 N 根 K 線,均線尚未成形」。loader 端 `rolling` 無 `min_periods` **不動**(加了會改早期均線值=語意變更,列待核准)。
- **nest_* 事件迴圈補丁死 import 移除(C2)**:data_loader L1-4 import+apply,全 repo 0 非同步程式碼消費,原本就 try/except pass。回歸網加 src/ 守恆掃描(未來引入非同步碼會被提醒重評)。
- **已修過/誤判(證據)**:`_TWSE_DL` 死碼=v19.78 S7 已刪(原地註解);季報無 cache=wrapper 層 TTL_1HOUR(第三次同誤判);share_capital/monthly_revenue token 只讀 env=誤判(app.py 啟動 sync secrets→env,第五輪已證);毛利率除零路徑不一致=v19.80 N1 已修;月營收 FinMind×2 重複=誤判(方案0 重複 v19.78 S11 已刪;現存兩段為 SDK vs raw 語意不同源,finmind_client D5 docstring 明載不可機械合併);`calc_rs_score` abs() 空頭失真=**屬實但為自洽評分公式**(RS_BAND_* 閾值以此校準,改=全評級位移;report 自列 P2「需回測驗證」)→ 待核准;monthly_revenue_calc 獲 report 評「全案最乾淨」(v19.83 又剛補日曆對齊 ✓)。
- **回歸網**:`tests/test_review_fixes_v19_84.py` 8 test(jingqi ADL/備援/全敗三路功能測試+鍵集合斷言+源掃描 / kline NaN 守衛順序 / nest 移除+src 守恆);全套件 **2,987 passed / 0 failed**。
- **大項待核准(§-1 不擅動;多數與五、六輪重疊,新增項標 ⭐)**:⭐`freshness_guard.assert_fresh` 下沉共用閘(P1,消費現成 FRESHNESS_THRESHOLDS_DAYS)、⭐DataManager 統一資料入口(P5,report 自評最高槓桿但屬 §8 架構案)、⭐MA `min_periods`(改早期均線值)、⭐`calc_rs_score` 收斂 σ 版 SSOT、⭐KD 高檔鈍化/背離模組/遲滯雙門檻/z-score regime(P3)、⭐registry 全覆蓋+主動巡檢(P4)、⭐布林帶寬×3/VCP×3/DNA×2 收斂+signal_thresholds 按領域拆包(P5)、⭐term_glossary/surface_anomalies(P6)、⭐旌旗備援改 None(政策)、Session 池化+429 退避、RSI Wilder/ATR True Range/假週線/融資正名(P2,前輪已列)、平行化(前輪已列)— 詳 PR 描述。

## 🧮 2026-07-11 第六份外部 review 查證後修復：季報金融股閘門 + 外本比分母（v19.83）

user 指派第六份建議書(8 面向合併版,審查基準為舊 main — 多項為前五輪已修);本 repo ~22 條主張查證:**4 真 bug + 3 硬化 / 12+ 已修過或誤判 / 大項待核准**。

- **Bug 1(真)季報金融股閘門雙重壞**:`get_quarterly_data` (a) 三元式兩分支皆 True(恆真)— 無營收欄的一般股一律誤判金融股;(b) 月加總 fallback 寫死 `年/月/營收` 欄名,但 `get_monthly_revenue` 契約自 v18.202 起是 `date/revenue` → 一執行就 KeyError → 被外層 except 變成「載入錯誤」,**該股整檔季報全滅**(受害者:報表無標準營收欄的個股,如產業別查詢失敗的非 28/58 金融股)。修:`bool(finance_candidates)` + 雙名容錯欄位偵測(對齊早退路徑既有寫法)+ 營收 fallback pd.NA→float nan(防 `(營收<0).any()` NA-布林 TypeError)。
- **3-7(真,比報告說的更深)V4 外本比分母全 repo 無寫入**:報告懷疑「股 vs 張單位混用」— 查證後單位其實一致(都是張),真根因是 `t2_shares_{sid}` **只有讀取處沒有寫入處** → 分母永遠 fallback 1,000,000 張:台積電(2,593 萬張)外本比高估 26×、小型股低估數十倍,0.5%/0.3%/0.1% 門檻全失真。修:tab_stock 在 `_xsec['capital']`(股本元,fetch_share_capital 既有)可用時寫入 `int(股本/10000)` 張;抓取失敗不寫,維持既有 fallback(§1 不虛構)。
- **3-9(真)月營收 YoY 位置索引錯基期**:`compute_yoy_mom` 用 `-12` 位置位移假設序列連續 — 缺月(新上市/暫停公布/來源缺洞,§4.6 月營收三態)時基期錯位靜默失真。修:改「(年-1, 同月)」日曆查表,date 欄缺/含 NaT 退回位置法(連續序列兩法結果相同,回歸測試釘住);NaN 值統一正規化為 None(classify_trend 的 `is None` 守衛原漏接 NaN → 缺值現在正確歸 insufficient 而非 neutral)。
- **3-4 邊界(真)calc_vcp 破壞回 None 契約**:檔頭述明「失敗一律回 None(不丟例外)」,但缺 high/low 欄直接 KeyError 炸到 tab_stock:266 裸呼叫(舊測試自承為「與文件的局部偏差」)。修:補同儕 calc_kd/calc_bollinger 既有 try/except+stderr log 模式,計算邏輯 0 改;舊測試改釘契約本身。
- **硬化 ×3**:etf_fetch NAV 狀態排除清單補 '429'(原漏列,FinMind 限流回應可能被誤收);FinMind token 前綴不再 print 入 log(改印長度);`_URL_CACHE` 補上限 256+過期逐出(原無上限、過期項只在命中時檢查 — Cloud 長跑記憶體單調增長,呼應 v19.79 段錯誤事故的記憶體壓力線索)。
- **已修過/誤判(證據)**:Bug 2 L1315 除零=N1 v19.80 已修(`replace(0,nan)` 註解在場);`'bw' in dir()` 死碼=v19.74 已刪;Bug 3 finmind_get `.json()` 崩潰=誤判(全 body 在 try 內,429 已 log 判讀;改 fail-token 契約=改所有 caller,列待核准);Bug 4 build_leading_fast `.result()` 崩潰=誤判(finmind_get 內部全 catch 永不 raise,timeout 25s×2 有界);orchestrator `_ri.json()`=在 try/except 補救路徑內;季報無 cache=誤判(fetch_quarterly/fetch_quarterly_extra wrapper 層 TTL_1HOUR,與第五輪同一誤判);ttls docstring 7vs9=已修(現列 9 常數);法人列長守衛=第一輪已修;自營商 `+=` 不對稱=誤判(BFI82U 自營自行買賣+避險兩列本須累加,外資/投信單列);三率三升只查絕對值=誤判(真三率三升在 fundamental_screener 條件 B:三率 QoQ>0 且 YoY>0;calc_fundamental_score 名為四維評分、check label 誠實);picker 裸 except/float 未防護=現行 code 無此片段;get_monthly_revenue 只讀 env=誤判(app.py 啟動同步 secrets→env,第五輪已證);方案0 重複=S11 v19.78 已刪;foreign_flow `int(None)`=現行無此片段;fetch_yf_close range 截斷=映射表有 3y/5y/10y 鍵、現行唯一非標準 caller(tw_macro 'Nd')拿超集對窗型計算無害(潛在腳槍註記,無現行觸發)。
- **回歸網**:`tests/test_review_fixes_v19_83.py` 17 test(季報閘門 scan×3 / t2_shares 寫入+換算+讀端不變 / calc_vcp 缺欄・0 價・happy×3 / 429 / YoY 連續=位置法・缺月 None・無 date 退位置・短序列 insufficient / token 遮罩 / _URL_CACHE 上限+過期+最舊逐出);`test_tech_indicators` 舊偏差測試改釘契約;全套件 **2,979 passed / 0 failed**。
- **大項待核准(§-1 不擅動)**:RSI 改 Wilder+平盤=50(docstring 明示 simple-mean 設計,改=全下游訊號位移)、KD 種子 50/H=L 處理、ATR 補跳空真實波幅(改=停損距離全變)、假週線改 resample('W')+標準 MACD(12,26,9)(docstring 明示每 5 根近似設計)、融資維持率正名+法定 130% 切換、VIX veto 改滾動百分位、staleness gate `assert_fresh` 統一時效閘、**NAS `/proxy` 未設 key 全放行+SSRF(安全優先,建議:未設 NAS_API_KEY 拒絕啟動+url 白名單;涉 user NAS 部署行為變更故不擅動)**、finmind_client Session 池化+429 指數退避 fail-token(檔頭明示零行為漂移設計,改=另案 §8 對齊)、picker/dividend 4 路/margin 6 路平行化、yf_proxy cache key 含 proxy 狀態、ETF expense ratio fetcher 補 cache、二級 st.tabs 降密度、indicator taxonomy 三軸+render_smart_metric+異常置頂、專題 B 選股介面重構全案(獨立入口/勾選表/漏斗視覺化/一鍵智慧選股)、股票端 F821 pre-commit gate(本輪掃描 0 hit,純預防可選)— 詳 PR 描述。

## 🔩 2026-07-11 第五份外部 review 查證後修復：OTC 死參數 + UA 補漏（v19.82）

user 指派第五份建議書(A/B 兩專案合併版);本 repo 5 條 Bug 主張查證:**1 修 + 3 項周邊硬化 / 4 已修過或誤判**。

- **Bug D(真)`_fetch_otc_via_finmind` token 死參數**:函式讀 module-level 凍結快照 `FINMIND_TOKEN`,完全忽略傳入的 token 參數 — 若 import 當下 env/secrets 未就緒,凍結空值讓 caller 再傳新 token 也永遠 return None。改 `token or _get_finmind_token()` 動態重讀,順帶把該站僅 Authorization 無 UA 的 headers 換 `_fm_raw_headers` SSOT。
- **UA 補漏 4 站(S8 v19.78 漏網)**:`data_loader` fetch_industry_category / fetch_bps、`share_capital_fetcher`、`etf_fetch` 中文名查詢 — 全補 `_fm_raw_headers('')`(UA-only,token 維持走 params)。同步放寬 `test_etf_zh_name_and_beta` 兩個 fake_get 簽名收 headers。
- **裸 except 收窄 ×4(§3.3)**:`data_loader` `_pn`/`_pn_tp`/`_int_tp`/`_qe2date` 四個 cell-level parse helper 的 `except:` 改具名例外元組,保留 0.0/0/None fail-token 語意(對齊 S3 v19.78 收窄前例)。
- **版號矛盾**:主標 badge「4.0 Pro」vs page_title/側欄/頁尾 v3.0 同畫面矛盾 → 統一 v3.0(多數決)。
- **已修過/誤判(證據)**:Bug A 毛利率除零=N1 v19.80 已修(`replace(0,nan)` 兩路徑都在);Bug B 股利 `.json()`/`['data']`=v19.78 S8+v19.80 N5 已補 log,直索引有條件守衛屬誤讀;Bug C token 只讀 env=誤判(app.py:91-93 啟動即同步 secrets→env,函式內 runtime 讀全拿得到;唯一 module-level env-only 讀取 leading_indicators:53 為死變數 0 使用);Bug E volume NaN=v19.81 上輪剛修;sidebar 渲染兩次=誤判(兩個 with st.sidebar 區塊內容不重複,Streamlit 為 append 語意);f-string 色碼=第一輪已修(現存 3 處皆 f-前綴巢狀正確);get_quarterly 無快取=誤判(cache 在 fetch_quarterly/fetch_quarterly_extra wrapper 層 TTL_1HOUR);月營收方案0 重複=S11 v19.78 已刪;_score_help 死變數=已不存在。
- **回歸網**:`tests/test_review_fixes_v19_82.py` 9 test(OTC 死參數功能測試×2+source-scan、UA 4 站、裸 except 歸零、版號);全套件 **2,962 passed / 0 failed**。
- **大項待核准(§-1 不擅動)**:Session `@st.cache_resource` 複用(執行緒安全需評估)、個股頁 7 fetcher / inst 逐日迴圈 / margin 6 路平行化、picker_fetcher 快取、覆蓋率表盲區(配息/BPS/PE/產業別燈+全 10 Tab+registry 未觸發空白)、tab_stock st.tabs 子分頁+hero 概覽列+河流圖 selectbox 收斂+AI 體檢 expander 預設收合、企業 DNA 兩處二選一、停損卡重複、ARCHIVED 註解清理、app_cache pickle 路徑統一 — 詳 PR 描述。

## 🧾 2026-07-10 第四份外部 review 查證後修復：NaN 邊界防炸（v19.81）

user 指派第四份建議書;先過濾 ≥4 條已修/過時舊主張(yf.download 無 timeout + session 未池化=v19.78、`_TWSE_DL` 模組級重用=v19.78 已刪死碼、台股無平行化=v19.77 批次 ThreadPool 已落地),本 repo 3 條新主張查證:**2 修 / 1 誤判**。

- **4-A-1 volume `.astype(int)` NaN 崩潰**:Yahoo 停牌/無量日可回 NaN 成交量 → `.astype(int)` IntCastingNaNError 炸整條 K 線頁。三路徑(Yahoo adj / Yahoo 備援 / FinMind)全補顯式 `fillna(0)` + §1 log 受影響筆數(§4.6 跌停 0 vol=有效報價語意);FinMind 路徑保留原 astype 截斷語意不補 round,避免既有值位移。
- **4-A-3 比率分母 NaN-truthy 傳染**:`fuzzy_get_from_df` 可經 `float("nan")` 字串路徑(MOPS read_html)回 NaN,而 NaN 為 truthy → `if rev` 擋不住 → 毛利率=NaN 靜默傳染下游健康引擎。`calc_financial_metrics` 6 個比率分母(rev×3 / 總資產 / 流動負債 / 權益)統一 `_denom_ok`(notna 且非 0),無效分母維持既有 0.0 語意。
- **誤判(證據)**:4-A-2 股利 `.json()`/`['data']` 未 guard — 實碼為 `_div_jd.get('status')==200 and _div_jd.get('data')`,全 `.get()` 無 KeyError 面;`.json()` 失敗 v19.78 起已 log 非靜默 pass。1-A「健康分數未納入診斷」— `macro_registry_patch` 已有 `[個股] 健康分數` 條目(v19.75 B5,v19.78 修過被誤清 bug);「MA/KD/布林未納入診斷」— 衍生指標為 L2 純計算無獨立失敗模式,上游 K 線 freshness 已監控,health_inspector 明文排除為 by-design。
- **回歸網**:`tests/test_review_fixes_v19_81.py` 7 test(NaN volume golden / 6 分母 NaN 傳染 / happy path 不變);全套件 **2,953 passed / 0 failed**。
- **追加(merge 前 CI 驗證發現,非本 PR 引入)**:slow lane `test_app_reexport` 於 main 已紅(informational job)— 根因:無 secrets.toml 環境(CI/裸跑)`st.secrets.get()` 直接 raise `StreamlitSecretNotFoundError`(streamlit 1.59.1 行為,default 不生效),`import app` 模組層級炸。修法:app.py 側欄 5 處裸讀收斂至既有 SSOT helper `_get_secret`(secrets→env→raise 三段降級,語意同 L88-89);`health_inspector`/`tab_macro`/`section_state` 3 檔 3 處補 try/except env-only 降級(同 EX-L0-1 精神,有 secrets 環境行為 0 改)。**第二層(CI 揭露)**:secrets 修好後 import 走得下去,換 monolith 模組層級真打網路(ETF 48 檔批次等)在 CI 裸環境拖 >180s → TimeoutExpired 假紅 — `test_app_reexport` 子行程改指 ECONNREFUSED proxy(127.0.0.1:9),全網路呼叫立即失敗走既有處理路徑,測試回歸本旨(驗 re-export 身分)且 hermetic:110s→14s。驗證:本地 1 passed;CI slow lane 轉綠見 PR checks。
- **大項待核准(§-1 不擅動)**:IndicatorMeta 三軸 SSOT、異常分數引擎+關鍵訊號卡、卡片渲染收斂、逐標的平行化再擴張、fallback 分級 timeout、雙 pickle 快取合併(round-1 已判 by-design:兩層語意不同)— 詳 PR 描述。

## 🧯 2026-07-10 第三份外部 review 查證後修復：快取正確性 + 執行緒安全（v19.80）

user 指派第三份建議書;先過濾 8 條已修/已駁舊主張(CSS=v19.74、session/UA/_TWSE_DL/月營收重複=v19.78、季報快取・sidebar=前輪已駁、B5 已修),10 條新主張查證:**6 修 / 2 誤判 / 2 防禦不對稱已補齊**。

- **N2a 失敗不進快取(本輪最高價值)**:`get_combined_data` except 分支原 `return None tuple` 會被 @st.cache_data 快取 **1 小時** — 一次 FinMind 限速/網路抖動 → 該股 1 小時黑洞。改「cached 內層 raise `_CombinedDataError` + public wrapper 還原 3-tuple」:st.cache_data 對 raise 不快取,caller 介面 0 改;「查無資料」類確定性負結果仍快取。`_LOADER_VERSION` bump v3。
- **N2c T86 負快取**:暫時性失敗(網路 None/例外)原把 `{}` 永久釘進無 TTL 的 `_T86_DAY_CACHE` → 改 `_T86_FAIL_TS` 短 TTL(TTL_15MIN)負快取;「stat != OK」(假日等確定無資料)仍永久快取(語意正確)。
- **N3 _yf_dl env 競態(v19.77 平行化後真風險)**:函式改寫**全域** os.environ 再還原 — 批次 ThreadPool(3) 下 worker A 的 finally 會中途拔掉 worker B 的 proxy、晚進者備份到同儕值導致外洩。yfinance 1.5.1 **無 proxy kwarg**、set_config 亦全域 → 改「引用計數+鎖」:首進備份/設定、末出還原,下載本身仍並行。3 執行緒交疊測試驗證 env 恆穩+精確還原+深度歸零。
- **N4a 外資期貨留倉主源無 try**:FinMind schema 改欄名時 KeyError 冒泡**繞過 TAIFEX 備援** → 包 try+log 降級。**N4b** `taifex_post` 原只用 `len(text)>200` 判成功(維護頁誤判)→ 補 `status_code==200`。
- **N1 分母防呆補齊**:毛利率(gp/成本兩路徑)+金融股稅後純益率分母無 0→NaN(營益率/淨利率有)— 一般股有「營收>0」過濾+圖表 ±100 clamp 擋著,金融股不走該過濾 → 三處對齊 L1448 既有 pattern。
- **§1 補 log**:股利 TWSE 備援(四源鏈最後靜默段)+ `_is_financial_stock` 產業別查詢失敗(退 28/58 前綴啟發式留跡)+ fut_oi TAIFEX 備援。
- **回歸網**:`tests/test_review_fixes_v19_80.py` 12 test(含 3 執行緒 env 競態重現/T86 負快取三段語意/wrapper 介面不變);全套件 **2,946 passed / 0 failed**。
- **不修(附證據)**:N7 財報體檢 expander「收合省抓取成本」機制錯誤 — st.expander 收合仍執行 body,真省成本需按鈕 gate(UX 行為改變,列待核准);N8 flatten_snapshot 缺 key 風險 — production 0 caller 且唯一 consumer 用 .get() 安全;N9 scanner 無股利細項 — patch_registry 每 render 補年度股利,無實際缺口(writer 雙軌不一致列技術債);N2b cache key 無日期 — TTL 1hr 已界定跨日窗+隔夜無新 K,低嚴重度不動;N4c 慢版 vol[d] — d 取自 vol 自身鍵,無法 KeyError(防禦不對稱純外觀)。

## 🚨 2026-07-10 雲端倒站 hotfix：pyarrow 25 cap + FinMind 殭屍依賴移除 + 融資單位修正（v19.79）

**事故**:11:50 UTC Streamlit Cloud 平台重啟潮(強制 Python 3.14)+ **pyarrow 25.0.0 當日發布** → 兩儀表板 Segmentation fault(股票:啟動後首次 arrow 序列化崩;基金:舊 streamlit 啟動即 import 崩)。昨日部署(pyarrow 24.x+pandas 3)正常 = delta 鎖定 pyarrow 25。

- **requirements**:顯式 `pyarrow>=14,<25`(cap 回久經驗證 24.x;解禁條件=25.x 在 cp314 穩定數週);**移除 `FinMind>=0.9,<2`** — 實測 wheel metadata:FinMind 1.x 全系列 pin `pandas<2.0/numpy<2.0/lxml<5.0`,與核心 pin 硬衝突,**雲端/CI 從未真正安裝成功**(殭屍依賴,app 長期走 DataLoader=None raw HTTP 路徑;移除消滅 resolver 回溯不確定性)。data_loader try-import 保留 + 警告改雙路錯誤都列出(原第一段錯誤被第二段覆蓋,誤導診斷)。
- **融資餘額 P0(v19.74 regression)**:production log 實證 `TaiwanStockTotalMarginPurchaseShortSale` Money 列單位=**元**(619,648,244,000 元=6,196 億 ∈ sanity;當仟元=619 兆荒謬),v19.74 誤搬 MI_MARGN 的仟元規則(÷1e5)→ 全值被 sanity 棄用 → FinMind 路徑全滅+TWSE 未出檔時 all-routes-empty。修正:`_finmind_margin_to_yi` 改 ÷1e8;解析迴圈**只認 Money 列**(同組 MarginPurchaseVolume=張,非金額)+ 排除 YesBalance 欄;v19.74 反向測試改以線上真實值為 golden。
- **回歸網**:`tests/test_hotfix_v19_79.py` 9 test + v19_74 margin 測試重寫;沙盒 pyarrow 對齊 24.0.0;全套件 2,934 passed / 0 failed。

## 🔌 2026-07-10 第二份外部 review 查證後修復：連線層強化 + UI 邊界（v19.78）

user 指派第二份建議書;14 條主張逐條查證:**6 修 / 1 已修過(S1 CSS=v19.74) / 3 誤判 / 4 部分屬實**;查證另挖出建議書沒發現的真 bug 一枚(S13-adjacent)。

- **S6+S14 timeout SSOT**:實測 FinMind 1.9.12 源碼 — dataset 方法 `timeout=None` 直通 `session.get(timeout=None)` = **無限等待**(包在 SDK max_retry_times=10 迴圈)→ 新增 `data_config.HTTP_TIMEOUT_FINMIND_SDK_SEC=30 / HTTP_TIMEOUT_YF_SEC=15`(語意=單次 HTTP 等待上限,與 ttls.py 快取時長不同源不混放);4 個 SDK 呼叫點 + `_yf_dl` 顯式帶逾時。
- **S7 session 複用**:`data_loader._bps_dl` / `app_stock_fetchers._make_proxy_session` / `macro_snapshot._make_proxy_session` 三處「每呼叫 new Session」→ thread-local 單例(同緒共連線池/異緒隔離);刪死碼 `_TWSE_DL`;`proxy_helper.make_retry_session` 補 **429**(對齊 tw_stock_data_fetcher._RETRY_STATUS)。
- **S8 UA 補齊**:5 處手刻 FinMind raw REST 只帶 Authorization → 新 `_fm_raw_headers()`,UA 對齊 finmind_client SSOT;股利 REST 同修。**不硬收斂 finmind_get**(docstring 明載 proxy session 站點刻意排除,曾實測轉紅還原)。
- **S9 cache 鎖**:`_FRED_CACHE`/`_YF_CLOSE_CACHE` 無鎖 check-then-set + `fetch_china_macro` ThreadPool(5) 真併發 → threading.Lock ×2(8 緒 hammer 測試)。**status 檢查子項改判誤判**:實讀 fetch_url — 只在 200 回 Response 其餘 None,`r is None` 本來就足夠。
- **S11 月營收方案0 去重**:兩段逐字相同 FinMind 呼叫(第二段必然同敗)→ 刪;暫態重試由 Retry adapter 承接。
- **S2 MA NaN 誤標**:section_health_score 兩處 `p > m20 > NaN` 靜默 False → <100 根被誤標「空箱整理」→ pd.notna +「均線未成形(歷史不足)」(§4.6);MA20 crash 子項誤判(safe_ma 恆回 float)。
- **S3**:`split()[0]` except 補 IndexError。**S4**:實測 pandas 3.0.3 nlargest 全 NaN **回含 NaN 任意列**(靜默選錯紅K,非 review 說的 IndexError)→ 先 notna 過濾。**S5**:「近20日」標籤改 `近{_win20_n}日` 動態。
- **S13-adjacent(真 bug)**:`macro_registry_patch` 每 render 刪光 `[個股]` key,B5 v19.75 三條監控條目(只在刷新分支寫入)下一次 render 即被清掉 → 刪除迴圈排除 B5 後綴。review 原主張(股利缺監控)反而誤判(patch:89-93 本有)。
- **§1 順手修**:fetch_dividend_data 兩處 `except: pass` 補 log。
- **回歸網**:`tests/test_review_fixes_v19_78.py` 25 test;全套件 **2,927 passed / 0 failed**。
- **不修(證據)**:S1=v19.74 已修;S10 sidebar 重複=不成立(兩段內容不同無重疊);S12 季報快取=上層 fetch_quarterly/_extra 已 @st.cache_data 包覆,唯二 caller 皆走 cached wrapper。

## 📈 2026-07-10 B8 健康度歷史 repo 快照 + A-2 批次抓取真平行（v19.77）

> user 拍板:B8 選「repo 快照 + cron」;A 類只做「批次抓取平行化」(K線快取試點/N+1 未選,不動)。

**B8 健康度走勢後端持久化**(原只存 session_state,App 重啟歸零,趨勢圖累積不起來):
- **cron script** `scripts/update_health_history.py`:對 `data_cache/health_watchlist.json` 清單逐檔 `get_combined_data(360)` → 同一組 L2 指標 → `calc_health_score` — **零新公式**(SSOT,shortage_cli 薄殼精神,單機分數與網頁保證一致)。寫 `data_cache/health_history.parquet`,**冪等** (date,sid) 重跑覆蓋;§2.3 PIT 鍵 = 該檔最後一根 K 的**交易日**(非執行日,連假重跑不重複)。§4.2 寫出前斷言 health∈[0,100]/close>0。meta json 記成功/失敗清單(§5)。
- **workflow** `.github/workflows/update_health_history.yml`:工作日 UTC 09:30 = TW 17:30(盤後 TWSE 17:00 資料齊,§4.5;對齊 update_macro_history 同時段慣例)+ 手動 dispatch(可指定代碼)。
- **L3 service** `src/services/health_history_service.py`:`load_health_history(sid, days)`(讀 parquet,檔缺/壞 → [] + log)+ `merge_score_history`(純函式:cron 底稿 + session 盤中即時點覆蓋同日)。路徑常數 repo-root 相對定位(對齊 fundamentals_snapshot_loader 模式),script 亦 import 同常數(路徑 SSOT)。
- **UI** `section_kline_chart`:score_hist 底稿改讀快照(L5→L3,合 §8.2 硬規則),快照缺 → 行為同舊(session 累積),§1 不造假。
- **watchlist 出廠為空**(§1 不腦補持股):填入代碼 commit 後功能才啟動;script 空清單顯式訊息 + exit 0 不 commit。

**A-2 批次抓取真平行**(`section_batch_fetcher`,review 點名):
- 原全域 Lock 串行保護「FinMind dl 非線程安全」→ K 線抓取實質序列(3 worker 名存實亡)。改 **thread-local loader**(每 worker 各持實例,無共享可變狀態 → 免鎖);`@st.cache_data` 鍵 (stock_id, days) 跨實例共享,快取效益不變;max_workers=3 維持(FinMind 禮貌上限)。
- 移除計算迴圈尾 0.2 秒固定 sleep(純本地計算段,I/O 已在 ThreadPool 完成,固定延遲無限流意義)— N 檔省 0.2×N 秒。
- **保守不動**:計算階段維持序列(CPU-bound,GIL 下 ThreadPool 無益;向量化屬大改另議)。

**驗證**:`tests/test_health_history_b8.py` 17 test(公式重用煙霧:多頭>空頭 / PIT 交易日鍵 / (date,sid) 冪等覆蓋 / §4.2 越界拒寫 / watchlist 三態 / service 讀取+同日覆蓋合併 / script main 全離線 e2e + 單檔炸不連坐 / A-2 源碼守衛 + thread-local 隔離行為)全綠;批次 provenance 12 test 無 regression;全套件全綠。

---

## 🩹 2026-07-10 CI 收官：RSS 雙後端契約統一（v19.76，main CI 最後 2 紅）

> v19.74 治綠後 CI run #428/#430 只剩 2 敗:`test_news_fetcher_coverage` 兩測寫的是 **ET 備援語意**,CI 有 feedparser(主路徑,寬容解析)行為不同必炸;本沙箱原裝不了 feedparser(sgmllib3k build 失敗)所以測不到,手動裝入後 1:1 重現。

- **production 修**:`rss_items_from_bytes` feedparser 主路徑補「無 title / 空 title 條目一律略過」(ET 備援本就如此;原樣回傳會讓空標題新聞流入下游渲染與關鍵字統計 — 真 bug,非只是測試紅)。
- **測試修**:`test_malformed_xml` 改後端相依契約 — feedparser 寬容解析殘缺 feed 為 feature(real-world RSS 常輕微 malformed,全丟=掉真新聞),ET 嚴格回 [];共同不變量:回 list、不 raise、無空 title。
- **驗證**:兩後端都跑(有 feedparser 16/16 + meta_path 遮蔽模擬 ET 備援 16/16);全套件 2,885 passed / 0 failed(沙箱補裝 feedparser 後與 CI 依賴面一致)。

---

## 🧰 2026-07-10 review B/D 類收斂：診斷盲區登錄 + pandera 阻擋 + cache 可攜（v19.75）

> user 核准「B+C+D 請繼續」(A 類大重構不動)。B=監控盲區、D=低 ROI 清理;C 類複查在 Fund 側記錄。

**B5 診斷盲區登錄 data_registry**(review:籌碼集中度/股本/現金流量比壞掉不亮紅):
- producer 端 meta stash(只存元資料不存 df 本體):`chip_radar` 寫 `chip_conc_meta`、`tab_stock` 寫 `t2_xsec_meta`;5年現金流量比率讀財報健檢**既有** `_fin_raw_{sid}` stash,零新 producer。
- `data_registry_scanner` 統一登錄 3 格:籌碼集中度(weekly,TDCC 週五更)/ 股本(quarterly,fetcher 失敗回 0.0 → missing 亮紅)/ 5年現金流量允當比率(yearly,status!=ok → missing)。只在 user 查過該股後登錄,避免固定清單膨脹。

**D13 月營收 pandera log-mode → blocking**(user 核准的資料政策變更):
- 新 `schemas.validate_or_reject()`:schema 違反 → **整檔棄用回空** + stderr log(§1 錯值比缺值危險;刻意不丟壞列 — 部分刪列會讓資料「看似完整」= 掩蓋)。pandera 未裝 → 放行(對齊 try_validate 語意),絕不 raise。
- `monthly_revenue_fetcher` 單檔+batch 兩處接線(batch 取首檔 36 列樣本,樣本違反 = 系統性 shape 問題 → 整批棄用)。
- **防誤殺**:revenue 先強轉 float64(FinMind JSON 整數營收會推成 int64,違反 schema float 契約 → blocking 整檔誤殺;Fund repo v19.172 FRED 同型教訓)。

**D14b cache 路徑可攜化**(review:/tmp/stock_cache 寫死,Windows 本機炸):
- 6 檔統一 `env STK_PKL_DIR 優先 + tempfile.gettempdir() 預設`(cache_layer/data_config/app_cache/leading_indicators/daily_data_fetchers/tab_macro)。Linux/Streamlit Cloud 結果不變(=/tmp/stock_cache),行為 0 變。
- ADL 除錯 log 路徑抽 `shared/cache_layer.ADL_LOG_PATH` SSOT(原 daily_data_fetchers 寫 + tab_macro 讀各自寫死字面值 = 跨檔隱性契約)。

**D14c 月營收無 token 靜默回空 → 補 log**(§5 可觀測性,診斷可分辨「無 token」vs「API 失敗」)。

**D 類不動項(維持並說明)**:三層快取 TTL(30min pkl/30min cache_data 外層 + 1h loader 內層)為刻意兩層設計非 bug;`data_loader` 減 `.copy()` 屬高風險 perf 重構;兩處配息 fetcher 用途不同(yfinance 年度 vs 4-fallback 明細)不強併。**B8 健康度走勢後端持久化**:涉存儲選型(GSheet / repo 快照 / tmp),§8.1 先提案待 user 拍板,未實作。

**驗證**:`tests/test_review_bcd_v19_75.py` 15 test(blocking 不誤殺 NaN 停業態/負營收整檔棄用/int64 強轉存活/no-token log/scanner 3 格登錄+missing/未查不登錄/可攜路徑源碼守衛+Linux 值不變)全綠;全套件無 regression。

---

## 🛠️ 2026-07-10 外部 code review P0/P1/P2 修正（v19.74）

> 使用者提交外部深度 code review 報告（dashboard_code_review.md），指示「根據建議修改，不適合的列清單」。逐項核對現行代碼後修 7 項，其餘列不修清單（詳 PR 描述）。

**P0-1 三大法人 BFI82U 欄位寫死**（`daily_data_fetchers.py`）:
- `row[3]` 寫死 → 抽 `_parse_bfi82u_rows(fields, data)` 純函式,買賣超欄用 fields 欄名「買賣差額/買賣超」定位（對齊同檔 MI_MARGN 既有模式）。TWSE 改版欄序位移時回 None + log,不再靜默回錯欄（§1 Fail Loud;原行為 isdigit 過 → 反向籌碼結論最危險）。

**P0-2 融資餘額 FinMind 區間猜單位**（`daily_data_fetchers.py`）:
- 廢除「億/元/千元/萬元」四分支數值區間猜測 → `_finmind_margin_to_yi()` 固定仟元÷1e5=億（FinMind 鏡射 TWSE MI_MARGN,單位固定仟元;同檔方案A 註解同源印證）。
- 新增 §3.2 sanity 區間 SSOT:`MARGIN_BALANCE_SANITY_MIN/MAX_YI`（500~10000 億,shared/signal_thresholds.py）,6 路 fallback 全走 `_margin_sanity_ok()`（原 inline `100<x<30_000` 過鬆,10× 誤判可穿過）。超區間 → log + 棄用改走下一 fallback。

**P0-3 goodinfo 快取鍵不可雜湊**（`tw_stock_data_fetcher.py`）:`fetch_goodinfo_metrics(proxies: dict)` → `_proxies`（@st.cache_data 略過底線參數;原簽章傳非 None 即 UnhashableParamError）。

**P1-1 連假強制重抓撞限流**（`app_stock_fetchers.py`）:價格快取容忍窗 5 → `PRICE_CACHE_HOLIDAY_TOLERANCE_CALENDAR_DAYS=14`（SSOT）。春節封關最長 13 日曆日（2025:1/21→2/3）,原 5 天窗連假期間每次冷啟動全檔強制重抓（拿到同樣舊資料,純燒 FinMind/yfinance 配額）。真新鮮度仍由 pkl 0.5h + cache_data 30min TTL 把關;gap>5 天沿用快取時 print 留跡（§5）。

**P2-1 MOPS fallback 零值假財報**（`tw_stock_data_fetcher.py`）:MOPS 長格式塞進 Goodinfo 寬表計算 → 全零 dict 餵下游誤判「財務崩壞」。加核心科目全零偵測 → 回 `{"error":"mops_parse_failed"}` 走 insufficient_data（對齊同檔 OCF=0 防禦）;`fuzzy_get_from_df` 補 `str(c)`（MOPS read_html 整數欄名原直接 TypeError）。

**P2-2 cache 無上界 OOM**:5 處以 stock_id 為鍵的 `@st.cache_data` 補 `max_entries=64`（data_loader `get_combined_data`/`get_monthly_revenue` + tw_stock_data_fetcher `_fetch`/`fetch_5_years_cash_flow`/`fetch_goodinfo_metrics`）。

**UI bug CSS 字面大括號**（`tab_stock.py:1087/1099/1111`）:f-string 內 `"{TRAFFIC_GREEN}18"` 寫在引號內不插值 → 渲染字面文字,獲利 5 卡背景/邊框色壞掉 → 改 `{TRAFFIC_GREEN if ok else TRAFFIC_RED}18`（對齊同段 1124 行既有正確寫法）。另移除 `tech_indicators.calc_bollinger` 恆真 `'bw' in dir()` dead code。

**驗證**:新增 `tests/test_review_fixes_v19_74.py` 18 測試（欄序位移/缺欄/單位錯 10×/邊界/全零偵測/源碼守衛）全綠;受影響套件（pr_n3/pr_n5/risk_radar/rs_leader/china 等 2,800+ 測試）無新增 regression。

**附帶:治綠 main CI（pr-check fast lane 自 7/3 起全紅,merge 前收拾）**:
- `test_china_macro_stock` 2 項:CHN_PMI → CHN_BCI 對齊 macro_core.py:241 v18.459 刻意改名（BSCICP03CNM665S = OECD Business Confidence 非 PMI）,測試原漏同步。
- `test_resample_audit` 1 項:v18.461 週K `'W'`→`'W-SUN'` 後 inventory 未重盤;擴 regex 捕 anchored alias + expected 更新,並依該測試 docstring 要求同步 CLAUDE.md §4.5 一行（W→W-SUN 註記）。
- **collection 全滅根因**（CI run #422 起 `Interrupted: errors during collection` exit 2,一個測試都沒跑）:`test_data_coverage`/`test_macro_classroom` 在**收集(import)階段**把 `sys.modules['streamlit']` 換成 stub(非 package),字母序在後的 `test_rs_leader_ui`(v19.70)+`test_macro_cross_ai_button_and_state`(v19.72)模組層 `from streamlit.testing.v1 import AppTest` 直接 ModuleNotFoundError。修法對齊同套件 `test_pe_river_merge_dtype`/`test_render_smoke` 既有慣例:AppTest e2e 測試歸 `@pytest.mark.slow` + 測試內 lazy import + setup 偵測不可用即 skip;按鈕名 source-scan 測試不需 AppTest,留 fast lane。（曾試「踢 stub 重載真 streamlit」免疫段,實測會翻掉其後 49 個依賴 stub 生態的測試 → 棄用,回歸 pe_river 模式。）
- 全部為「代碼是對的、測試過期/測試互相污染」方向,無 production 行為變更。既有「4 項 risk_radar 全套件連跑 order-dependent 失敗」(單獨執行全過,test-infra lazy-forward vs patch 目標歧異)為 main 既有議題,不在本 PR 範圍,已知悉待議。
---

## 🐛 2026-07-10 §十一 新聞：加獨立「📰 掃描新聞」按鈕（v19.73）

> 使用者回報「新聞這邊沒有任何讀取按鈕跟 ai」。查因：新聞 RSS 原本**只在按「🔒 執行 AI 裁決」時順便抓**（section_news_ai.py:64），且該鈕需 Gemini 金鑰 → 沒金鑰的人等於沒有能單獨載新聞的鈕，「新聞整體狀態」永遠「未掃描」。

- 加獨立 **「📰 掃描新聞」** 鈕（`btn_scan_news`）：只抓 RSS（`_fetch_macro_news`）、**免 Gemini 金鑰、不跑 AI**，寫入與 AI 裁決同一 stash key `_macro_news_items` → 上方「新聞整體狀態」燈號即更新。原「執行 AI 裁決」「清除報告」不動。
- 描述文案改標清楚：「📰 掃描新聞」只抓新聞（免金鑰）；「🔒 執行 AI 裁決」需 `GEMINI_API_KEY`。
- §8：純 L5 UI 加一鈕 + handler（mirror 既有 verdict handler 的 stash 機制）；無跨層/計算變動。
- 驗證：4 新測試（按鈕存在 / handler 抓 RSS 且不呼叫 gemini / AI 鈕未誤刪 / 模組編譯）+ 13 render smoke(slow) 無 regression 全綠。
- 註：AI 報告仍需**使用者自行**在 Streamlit Secrets 設 `GEMINI_API_KEY`（金鑰在 user 帳號，非程式可解）。

---

## 🐛 2026-07-10 §九 跨桶 AI：更新按鈕名對錯 + ①景氣位階 fail-loud（v19.72）

> 使用者截圖：②③④⑤總經卡都跑出真資料了，只有①「目前總經位階」還顯示「請點擊更新總經拼圖」，且**找不到那顆按鈕**。

**兩個真 bug**
1. **按鈕名不符（找不到按鈕）**：實際按鈕是 `tab_macro.py:144`「🚀 一鍵更新全部數據」，但多處佔位文字卻寫「更新總經拼圖」/「🔄 更新全部總經數據」— 指向不存在的按鈕名。6 處全改對：`section_cross_ai`(卡①預設 + 卡⑤預設)、`section_news_ai:178`、`app.py:532`、`macro_alert.py:360`、`macro_ui_components.py:163`。
2. **卡①誤導**：卡①需「外銷訂單 YoY 或 台灣 PMI/OECD CLI」才算得出景氣位階；此兩個 T3 來源（CIER/經濟部）本次抓取失敗，但卡①仍顯示「請點擊更新」（讓已更新的人困惑）。改 fail-loud（§1/§5）：偵測「其餘總經已載入（VIX/M1B/CPI 有值）卻缺這兩源」→ 顯示「景氣位階資料未就緒：缺外銷訂單+PMI，這兩來源本次抓取失敗（CIER/經濟部第三方網站暫不可用）」，講實情而非叫他再按更新。

**§8**：純 UI 文案 + 一段 render 判斷，無跨層/計算變動；6 處按鈕名收斂為同一正確字串（消除 divergent label）。
**驗證**：3 新測試（全 production 碼無殘留錯誤按鈕名的 guard / 卡①「已載入但缺源」顯示 fail-loud 診斷（復現截圖）/ 全空時指向正確按鈕）+ 14 macro render 相關測試無 regression 全綠。

---

## 📦 2026-07-10 基本面存活池：每季第二趟延遲補抓 + 涵蓋率診斷（v19.71）

> 使用者：「全台股每季重掃一次 OK，只是有些公司財報發布較慢，要怎樣確保都被抓到？」根因：cron 只在「截止+1週」抓一次，慢公布/展延申報者那趟抓不到，又不會回頭補 → 缺到下一季。

**A. 每季第二趟延遲補抓（真正解決）**
- `.github/workflows/update_fundamentals.yml` 加 4 條 cron（截止+約5週）：Q4→5/5、Q1→6/19、Q2→9/18、Q3→12/19。
- auto 模式 `latest_published_quarter` 判成同一季 → 重抓覆蓋同檔 parquet（腳本 §5 冪等已支援）；MOPS 彙總累加，晚交者這趟即補進。

**B. 涵蓋率診斷（§5 可觀測性，讓缺口看得見）**
- **script**：`_write_latest_json` 加 `_count_quarter`，把 `coverage{sii/otc/total/prev_total}` 寫進 `latest.json`（現有 115Q1 已回填：1,969＝上市1,078+上櫃891，去年同季1,934，保留原 updated_at）。
- **L0**：`SNAPSHOT_COVERAGE_WARN_RATIO=0.90`（本季 total < 去年同季 × 0.9 → 標「可能尚缺慢公布」，以去年同季自我參照，不硬編期望總數魔數）。
- **L3**：`describe_snapshot_coverage(meta)`（純函式，完整/偏低/舊版無 coverage 三態）+ `get_snapshot_coverage_note()`（快照缺 → 空字串不炸）。
- **L5**：選股網初篩面板 + RS 抗跌掃描 + 缺貨掃描 caption 都顯示「📦 存活池快照：民國115Q1 涵蓋 1,969 檔…每季兩趟抓取確保慢公布納入」；偏低時初篩面板轉 st.warning。

**§8**：script(L1 cron) + L0 常數 + L3 純 helper + L5 三處 caption，無跨層違規；covers 為 schema-additive（舊 caller 無感）。
**驗證**：10 新測試（_count_quarter / _write_latest_json 寫 coverage / describe 三態 + 比例邊界 / get_note fail-safe）+ 127 相關既有測試（RS/缺貨/初篩/loader）無 regression 全綠。

---

## 🛡️ 2026-07-10 抗跌 / 逆勢贏大盤選股（大盤下跌時仍贏過大盤的 RS 前 50）（v19.70）

> 使用者要「大盤下跌時（例如 2020 疫情）仍贏過大盤(RS)的前 50 名個股」。§7/§8 對齊後選「兩者都要（先即時）」+「免費基本面存活池 ~324 檔」。**Phase 1 = 即時模式**（歷史視窗模式為 Phase 2，待接）。

**計分口徑（σ 標準化超額報酬 = Mansfield 式）**
- 個股區間報酬 − 大盤(^TWII)同期報酬 = 超額（>0＝贏過大盤）；再 ÷ 大盤日報酬σ → **RS(σ)**；依 RS 降冪取前 50。
- ⚠️ 刻意**不用**官方 SSOT `calc_rs_score` 的比值法（`r_i/|r_m|` 在大盤負報酬時語意失真），改沿用 `v5_modules.calc_relative_strength`（逆勢強股語意）。
- **分級**：🔴 逆勢強股(≥+1σ)｜🟡 偏強抗跌(≥+0.3σ)｜⚪ 同步(−0.3~0.3)｜🟢 落後(<−0.3σ)。

**分層（沿用缺貨選股同一套，不重造）**
- **L0** `shared/signal_thresholds.py` 補 `RS_SIGMA_LEAD_MIN/MILD_MIN/LAG_MAX`（1.0/0.3/−0.3，**收 v5_modules 3 處 inline 魔數** → §3.3）；`calc_relative_strength` 改 import + schema-additive 回 `avg_stock_ret/avg_market_ret`（顯示用）。新 `shared/rs_screen_thresholds.py`（top50 / lookback 預設 / 分級標籤 / 掃描上限）。
- **L2** `src/compute/screener/rs_leader_screener.py`（純函式）：個股/大盤**日曆日對齊**（tz 統一：yfinance 個股 tz-aware vs fetch_yf_close 大盤 tz-naive，同 VIX/3M 教訓）→ reuse σ 公式 → 排序取前 50。
- **L1 重用**：`fetch_stock_history_1y`（threaded，無 st.cache）+ `fetch_yf_close('^TWII')` + `get_survivor_ids`。
- **L3** `src/services/rs_leader_service.py`：存活池 → 並行抓價 → L2 排名 + **市場漲/跌情境判定**（大盤在漲時明示「抗跌語意不成立」）+ §5 診斷；`build_rs_ai_prompt` 三型。
- **L5** `src/ui/tabs/rs_leader_ui.py`（lookback 選擇 20/60/120 + 只留贏過大盤 + 排行表 + 情境橫幅 + 誠實揭露 + AI 三型按鈕）；app.py 選股網加 expander「🛡️ 抗跌 / 逆勢贏大盤選股（RS 前 50）」。

**§1 fail-loud**：大盤抓不到 / 存活池空 / 全資料不足 → 回空 + 精準 note，不炸不造假。**誠實揭露**：只掃免費存活池（非全上市）、相對強弱非買點、已收盤日線、大盤漲時抗跌語意不成立。
**驗證**：39 新測試（L2 15 + L3 9 + L5 AppTest 2，含 tz-aware 對齊 / 市場漲跌橫幅 / SSOT 邊界 / fail-loud）+ 缺貨/render smoke 無 regression 全綠。

---

## 🐛 2026-07-10 VIX/VIX3M 期限結構「對齊後不足 2 筆」修（v19.69）

> 使用者截圖:短線風險雷達「VIX/3M」卡片顯示「⬜ 無資料 / VIX/VIX3M 對齊後不足 2 筆」,label 為 `Yahoo ^VIX / Yahoo ^VIX3M`（兩源皆非空卻對不上）。

**真 bug**:`risk_radar._signal_vix_term_struct` 用 Yahoo **原始 timestamp**（含時分秒、非午夜）直接 `concat(axis=1).dropna()`。同市場日線本該以「日曆日」為對齊鍵,但 ^VIX 與 ^VIX3M 常各停在不同 intraday 時刻（或 VIX3M 走 CBOE 備援 = 00:00 date-only）→ 秒級不等 → `dropna()` **全清空** → 誤報「對齊後不足 2 筆」。

- 修:兩支收盤 series 先 `pd.to_datetime(idx).normalize()` 到日曆日 + `~duplicated(keep='last')`（同日多筆取最後）再 join;`concat(..., sort=True)` 明確時序（消 Pandas4 warning）。
- §5 可觀測性:對齊後**真的**無重疊時,note 改攤開「VIX 至 YYYY-MM-DD／VIX3M 至 YYYY-MM-DD，源疑停更」而非只丟「不足 2 筆」,供資料診斷判讀。
- §8:單一 L2 純函式 bug fix,無跨層/介面變動。
- 驗證:78 risk_radar 測試（+3 新:intraday 時間戳不同仍對齊 / Yahoo 盤中戳 × CBOE 00:00 對齊 / 真無重疊時攤開最後日期）全綠。

---

## 🐛 2026-07-09 缺貨掃描「一檔都抓不到」修:免費版財報 dataset 無 s + 診斷（v19.68）

> 使用者實測:掃描全跳「存活池深掃後無可評分」,一檔都不剩。

**真 bug**:`fetch_quarterly_shortage_frame` 抓損益表只試 `TaiwanStockFinancialStatements`(有 s,付費版)。**免費/backer 版 dataset 名是 `TaiwanStockFinancialStatement`(無 s)** → 免費方案每檔回 0 季 → 全部「資料不足」。(既有 `data_loader.get_quarterly_data:1068` 早就兩個都試,新 fetcher 漏了。)

- 修:抽 `_finmind_rows_first(datasets, ...)` helper,損益表**無 s 優先、有 s 備援**兩個都試(對齊既有慣例);資產負債表加 try/except。
- 診斷(§5 可觀測性):`_score_and_diagnose` + `_diagnose`——無可評分時 note 攤開「資料不足 N 檔（其中 M 檔 FinMind 回 0 季 → 指向方案權限/配額,非程式 bug）、金融股 K 檔」,不再只丟一句「缺科目」。
- 驗證:46 缺貨測試(+2:免費版無 s dataset 路徑 / diagnose 攤 0 季原因)全綠。

---

## 🖥️ 2026-07-09 缺貨選股單機 CLI（scripts/shortage_cli.py）（v19.67）

> 使用者要一支「跟 dashboard 完全一致」的單機 CLI（他處 AI 產的獨立腳本有 3 個雷:revenue_percentage 當 YoY / 原始營收判遞增 / 缺科目填 0）。

- `scripts/shortage_cli.py`:**薄殼 driver**,直接 import dashboard 的 L1 抓取器（`fetch_quarterly_shortage_frame` + `fetch_monthly_revenue`）+ L2 計分（`rank_shortage` / `score_shortage`）+ `compute_yoy_mom`,**不重寫任何公式/門檻**（SSOT）→ 單機與網頁分數保證一致。修掉那 3 個雷（自算 YoY、判 YoY 加速、缺科目 None 不填 0）。
- 用法:`export FINMIND_TOKEN=xxx; python scripts/shortage_cli.py 2330 2317`；支援 `--file 清單.txt` / `--json`。金融股(28/58)不抓省額度;抓不到顯式標「資料不足/無科目」不造假。
- §8.2:歸 `scripts/` 維運 CLI,只 I/O + 呼叫既有 L1/L2,無自有計算。
- 驗證:9 CLI 測試(format/JSON/輸入組裝/金融股略抓/main 流程/no-token)+ 既有 35 缺貨測試全綠;實跑 entry point(no-token 提示 / dummy token → fail-loud 資料不足,不 crash)。

---

## 🔧 2026-07-09 缺貨選股：候選池相容免費 FinMind + AI 三型建議報告（v19.66）

> 使用者實測回報「finmind token 沒有」+ 截圖:側邊欄 FinMind ✅ 但缺貨掃描報「月營收全市場資料無法取得」。

**真 bug 診斷（不是 token）**
- app.py:89/92-93 已把 `st.secrets` 的 token 推進 `os.environ`,抓取器讀得到（側邊欄 ✅ 正確）。
- 真正失敗是候選池用的**「全市場月營收批次（不帶 data_id）」需 FinMind sponsor tier**,免費/backer 方案不支援 → 回空 → 原錯誤訊息誤標「token/quota?」。

**修法:候選池改「基本面存活池」優先（相容免費方案）**
- L3 `shortage_screener_service`:候選池**①優先用選股網那份免費離線基本面存活池**（`get_survivor_ids`,四項全過,你的環境確定能跑）→ 逐檔**單股**（data_id,低 tier 也支援）抓月營收 + 合約負債/毛利/存貨;**②僅存活池空時才 fallback** 需 sponsor 的全市場月營收批次。錯誤訊息改精準（區分「快照為空」vs「批次需 sponsor」）。
- 沿用 L1:`fetch_quarterly_shortage_frame`（季報）+ `fetch_monthly_revenue`（單股月營收,補 C4 的 YoY）。

**AI 三型建議報告（積極 / 穩健 / 保守）**
- L3 `build_shortage_ai_prompt(rows, top_n, news_text)` 純函式:缺貨排行 → 3 章節（排行/強弱分布/模型限制誠實揭露）+ 三型 overall_question → 重用 `build_structured_summary_prompt`（同個股 AI 報告元件）。
- L5 缺貨面板加「🤖 生成缺貨股 AI 三型建議報告」按鈕（app.py 傳 `gemini_call`）;best-effort 抓相關新聞;結果 session_state 快取。

**驗證**:35 缺貨測試（+3 新:survivor 路徑 / batch fallback / AI prompt）全綠;191 相關既有測試無 regression;Streamlit AppTest 實跑 render + 點 AI 按鈕產出報告無 crash。

---

## 🔥 2026-07-09 缺貨 / 供不應求選股（全市場掃描 + 四訊號計分）（v19.65）

> 使用者要「找到有缺貨的股票」,並貼了一份他處 AI 產的單股腳本。盤點後發現 dashboard 已有 8 成積木,
> 那份範例反而踩 3 條憲法紅線(補 0 造假 / inline 魔數 / 直接接 FinMind SDK 繞過分層)。改照本專案分層重做。

**四訊號計分（滿分 100）→ 🟥強 / 🟧中 / ⬜不明顯**
- ① 合約負債大增(35) ② 毛利率走揚(25) ③ 存貨週轉天數下降(20) ④ 月營收 YoY 連續成長(20)
- L0 `shared/shortage_screen_thresholds.py`:只放**新語意常數**(四權重 35/25/20/20 + 分級 65/40 + 月營收門檻 15 + 深掃上限 50 + DIO 年化 365)。訊號邊界值(CL YoY 15/30、QoQ 20)**重用** `signal_thresholds.py` 既有 SSOT,不重複定義。
- L2 `src/compute/screener/shortage_screener.py`(純函式):吃已對齊季度序列 + 月營收 YoY → 四訊號計分 + 分級 + 理由。DIO＝存貨 ÷(近 4 季成本 ÷ 365)年化(比範例單季 ×90 準)。**無合約負債科目 → 0 分並降級**(不補 0、不當壞事);金融股(28/58)不適用;不足 5 季標資料不足。絕不拋。
- L1 `src/data/stock/quarterly_financials_fetcher.py`:一次抓齊損益(營收/毛利/成本)+ 資產負債(合約負債/存貨),對齊成季度 frame。毛利缺→用營收−成本補(同 data_loader.py:2106,非造假)。EX-CACHE-1。
- L3 `src/services/shortage_screener_service.py`:**兩段式掃描**——全市場月營收 batch 圈「動能向上」候選池 → 深掃前 50 檔 → 呼叫 L2 排序。TTL_1DAY 快取。
- L5 `src/ui/tabs/shortage_screener_ui.py` + 選股網加 collapsed expander「🔥 缺貨/供不應求選股」(點按鈕才打 FinMind)。ProgressColumn 排行 + 白話計分規則 + **誠實揭露**(兩段式會漏極早期標的、財報 45 天延遲屬事後驗證、非買賣建議)。

**驗證**:32 新測試全綠(L2 計分各級距 + 邊界:空/不足/金融股/無合約負債/除零/garbage;L1 解析;L3 候選池+端到端)+ 188 相關既有測試無 regression;Streamlit AppTest 實跑 render 路徑(4 metrics + dataframe + column_config 無 crash)。

---

## 🟢 2026-07-05(下午) ETF 多檔「留/觀察/換」建議 + ETF 組合「每月配息明細」+ §4.1 混幣修（v19.64）

> 使用者兩個截圖回饋:①多檔比較「看不出哪些留哪些賣」②ETF 組合想看每月月配息(參考基金面板)。

**① ETF 多檔比較加「🚦 留/觀察/換」建議欄（PR 本批）**
- L0 `shared/etf_recommendation_thresholds.py`(留 0.65↑/換 0.35↓ 切點 + σ位階 ±1 加碼時機 + 同類重疊門檻 SSOT)。
- L2 `src/compute/etf/etf_recommendation.py`(純函式):`recommend_etf_actions(rows)` 讀既有分數(綜合分/流動性/配息健康/估值/σ)→ 留/觀察/換 + 紅旗降級(流動性🔴/吃本金🔴)+ **同類重疊偵測**(同類≥2 檔留分數最高、其餘擇一)。不重算指標。
- L5 `etf_tab_grp_compare.py` 加「🚦 建議」+「建議理由」兩欄 + 白話 st.info 說明。14 測試。

**② ETF 組合加「📅 每月配息明細（ETF × 12 月）」（PR 本批）**
- 基金面板(截圖 TLZF9/JFZN3)**不在本 repo**(那是共同基金,本 app 純 ETF)→ 照其精神用 ETF 積木自組。
- L0 `shared/dividend_frequency.py`(配息次數→月配/雙月配/季配/半年配/年配 門檻 SSOT)。
- L2 `src/compute/etf/etf_dividend_schedule.py`(純函式):`build_monthly_dividend_rows(holdings, usdtwd_rate)` → ETF×月矩陣 + 頻率 + 幣別 + 年合計。
- L5 `etf_tab_portfolio.py` 配息日曆段:新增每月明細矩陣(頻率/幣別/配息月份/1~12月/年合計+組合合計列)。15 測試。
- **§4.1 混幣 bug 修**:原碼把美元 ETF(BND)配息「當台幣」直接加進組合年現金流/殖利率/月度圖。改抓 USD/TWD(TWD=X)換算;抓不到→該檔標⚠️未換匯、不計入 TWD 總額(§1 fail loud)。全台股組合數值不變。

**驗證**:29 新測試全綠 + 347 ETF 測試無 regression;UI 矩陣塊實跑合成混幣資料(BND 換匯 3840、組合合計 5700 正確)。

---

## 🚀 2026-07-05 全台股基本面選股網完工 + 投資框架四層強化 + OAuth 修（v18.472→v19.63）

> 使用者一路回饋，本 session 交付：Phase 2 選股網、投資框架四層改進、多個實測 bug 修。

**A. 全台股基本面選股網（Phase 2 完工，PR #473~479）**
- 季快照 cron 改「公布截止 +1 週」自動每季重抓（4/7、5/22、8/21、11/21）；批次多抓去年同季供三率三升 YoY；`--season` 支援逗號分隔多季回補；MOPS fetcher 加重試+退避、3xx 轉址診斷。
- 後端 L0→L3：`shared/fundamental_prescreen_thresholds.py`（門檻 SSOT）+ `src/compute/screener/fundamental_prescreen.py`（L2 純函式 4 項）+ `src/data/stock/fundamentals_snapshot_loader.py`（L1）+ `src/services/fundamental_screener_service.py`（L3 + `gate_pool_by_fundamentals`）。
- 選股網入口從「估值前50」→ **全台股四項全過（負債比<50%/三率三升YoY/淨流動值>0/EPS>0）漏斗**（實測 1969→324 檔）；`tab_stock_picker` 加「自訂必過條件」15 項打勾 + 至少過 N；修「一動就消失要重按」（session_state 已跑過旗標）。

**B. 投資框架四層強化（框架討論後，PR #481~486）**
- **總經油門**：`shared/position_throttle.py` 健康分→建議持股區間（姿態非開關）+ regime 否決；總經頁紅綠燈下方油門儀表。
- **選股追高警示**：`src/compute/strategy/overextension.py`（乖離>25%/RSI>70）；選股網 S2 加「位階(追高)」欄。
- **加碼三問**：`position_throttle.assess_add_gate`（σ≤-1 + 趨勢沒壞 + 總經沒防守）；個股「什麼時候買/賣」加卡。
- **分散度**：`price_corr_warn_label`（價格高度同向）+ `_downside_corr_series`（空頭相關/危機失效）警示。
- **ETF 組合**：`src/compute/etf/portfolio_coherence.py` 股債比 + 總經一致性 + 核心/衛星拆解。

**C. 實測 bug 修**
- **OAuth 登入無限迴圈**（PR #484）：`oauth_state._oauth_state_ok` — session_state 在外部轉跳遺失時不再誤拒授權碼（仍擋真跨 session）。🚫 未寫死 secret、🚫 未關驗證。
- Google Sheet 讀取：診斷為「app 只認自己 `portfolios` schema / Sheets API 未開 / drive.file scope」→ 建議走「建立新 Sheet」；待使用者回報。

**未竟（使用者已知）**：ETF「平衡型/多資產」類別（TW 標的不足，WONTFIX）；工作分支刪除（環境 git proxy 403，需手動）。

**驗證**：本 session 新增 ~60 測試全綠（prescreen/loader/service/quarter/mops/picker/throttle/overextension/oauth/downside/coherence）。

---

## 🎨 2026-07-04 ETF UI 五連改（v18.467/468/469/470 + hotfix,使用者截圖回報）

- **v18.467**：ETF 三個智慧區塊(σ 買賣帶/分散度/MK 3-3-3)**去按鈕改自動計算**(輸入代號即算)、
  expander `expanded=True` 直接顯示;**AI 白話總結移到最下方**(單檔:`render_etf_single` 加
  `before_ai_hook` 於 AI 前呼叫;組合:`render_etf_ai` 移到 smart 之後)。
- **hotfix(PR #467)**：自動計算暴露 `build_holdings_set` KeyError 當機(對 DataFrame/dict 非
  預期格式 raise)→ 防彈化(list/DataFrame/dict/None 皆不 raise)+ 分散度迴圈 per-ETF try/except
  + `before_ai_hook()` 包 try/except(smart 出錯不拖垮整診斷)。另修 `update_fundamentals` workflow
  bs4 缺依賴(import mops_bulk_fetcher 觸發 stock `__init__` sibling eager import)→ 改
  `pip install -r requirements.txt`。
- **v18.468**：分散度分析改**按大類分組**(市值型/高股息/半導體/Smart Beta/債券,每類前 10)。
  L2 新增 `find_diversifiers_by_category`(純函式);UI 每類一張 bar chart + 明細 expander。
  ⚠️ 現有分類無「海外/平衡型」(使用者舉例),要加需擴充 `ETF_PEER_GROUPS`(待議)。
- **v18.469**：多檔 ETF 評分比較表補**標準差(σ)建議買賣價位 3 欄**(σ強買≤ μ−2σ / σ減碼≥ μ+2σ /
  σ位階)。`etf_tab_grp_compare._score_one_etf` 借用 L2 `compute_std_bands`(5y 價已抓),σ 算失敗 try/except 容錯。
- **v18.470**：`ETF_PEER_GROUPS` 分類**5 類 → 10 類**(全台股掛牌 ETF):新增 海外美股/海外陸股/
  原物料商品/不動產REITs/特別股(+ 債券補 00937B)。分散度分組自動多出這些類。48 不重複代號。
  ⚠️ 平衡型/多資產 TW-listed ETF 稀少,未建獨立類(標的不足)。原物料為期貨型('U' 後綴,yfinance
  可能無資料 → 抓不到自動略過)。

驗證:build_holdings 7 + diversifiers_by_category 4 + etf wiring + undefined-names 全綠;AppTest smoke;
compute_std_bands 回傳鍵實測正確。

---

## 🏗️ 2026-07-04 全台股基本面選股網（MOPS 路線）— 建置中（Phase 1a/1b 已上線）

> 使用者要求:選股網起始名單要涵蓋**全台股**(不是現在的上市 845 檔),用基本面篩選。
> POC 確認免費路線的天花板 + 資料源,分階段建。**此為跨 session 專案,進度記於此。**

### 可行性 POC 結論（GitHub Actions 實測，見 scripts/poc_*.py）
- **FinMind date-bulk 財報 = 免費 tier 不放行**（回 400「Your level is register」）→ 全 9 項免費 bulk 不可行。
- **MOPS 彙總報表可行**（免費、一次全市場、GitHub IP 不被 geo-block）:
  - 網域 `mopsov.twse.com.tw`(舊 `mops.twse.com.tw` 回錯誤頁)
  - `ajax_t163sb04` = **綜合損益表彙總**(營收/營業成本/毛利/營益/淨利/EPS)→ 三率#2 + 估值#4
  - `ajax_t163sb05` = **資產負債表彙總**(資產總計/負債總計/流動資產/權益總計)→ 負債比#1 + 淨值#8
  - POST `TYPEK`(sii/otc)+ `year`(民國)+ `season`(01-04);全市場(上市~1011/上櫃~740)
- **MOPS 只能 cover 4/9 項**(彙總表只有摘要欄;應收#5/存貨#6/CapEx#7/合約負債#9 需明細,MOPS 無)。
- **決策:兩層漏斗** — 第一層 MOPS bulk 全市場 4 項基本面初篩 → survivors 取代現在的估值 pool;
  第二層對小名單跑完整 9 項+籌碼+殖利率(per-stock,量少不爆 API)。

### 進度
- ✅ **Phase 1a**(PR #463):`src/data/stock/mops_bulk_fetcher.py`(L1)— fetch_mops_income_bulk /
  fetch_mops_balance_bulk + `_parse_mops_aggregate` 純函式(多產業表格、金融業缺欄容錯)。4 測綠。
- ✅ **Phase 1b**(PR #464):`scripts/update_fundamentals_snapshot.py` + `.github/workflows/update_fundamentals.yml`
  — 抓上市+上櫃存 `data_cache/fundamentals/*.parquet`(子目錄不受 gitignore)+ latest.json;
  季 cron + 手動觸發;`latest_published_quarter` 依公告截止日推季別。3 測綠。
- ⬜ **待做:實機驗證**(手動觸發 update_fundamentals workflow 抓真 MOPS + 產生首份快取)
- ⬜ **Phase 2**:L2 `fundamental_prescreen.py`(讀 parquet 算 4 項 → 全市場通過名單)
- ⬜ **Phase 3**:L3 service + 接選股網 UI(取代估值 pool)+ 降級 fallback

---

## 🎯 2026-07-04 v18.466 — 選股網漏斗式 + ETF 單檔診斷代號統一（使用者回報 2 bug）

> 使用者截圖回報：① 選股網入口是「殖利率前50」不是全市場基本面；② ETF 單檔診斷下方 3 個
> 智慧區塊各自帶獨立輸入框（顯示 0050），沒吃上方「開始診斷」的代號（00981）。經對齊採
> 「漏斗式（受 FinMind API 額度限制的折衷）」+「單檔 & 組合都改」。

### 修正一：選股網「漏斗式」— 殖利率不再當入口排序閘門
- `app.py`（選股網組裝）：入口由 `nlargest(50, 殖利率)` → 改 `nsmallest(PICKER_DEEP_SCAN_N, 本益比)`。
  全市場 → 基本面/估值初篩（排除虧損/PE>100/殖利率<2%或>12%）→ **依估值便宜度**取前 50 深跑三階段
  → 殖利率移到最後的「殖利率確認」欄位（`render_yield_confirm` 已在，方向本就正確）。`source_label`
  由「高殖利率前50」→「估值優選」。
- `src/ui/tabs/tab_stock_picker.py`：新增 SSOT 常數 `PICKER_S1_MIN_PASS=6`（基本面門檻由 5/9→**6/9**，
  使用者要求更嚴）、`PICKER_S2_MIN_PASS=3`、`PICKER_DEEP_SCAN_N=50`。通過門檻與 3 處 caption 全改用常數。
- ⚠️ 物理限制：三階段每檔 ~7 支 API（2 yfinance + 5 FinMind），全市場 845 檔即時深跑會爆 FinMind
  額度，故深掃檔數仍設上限（multiselect ≤30）。真「全台股跑基本面」需批次快取（未採，工程較大）。
  此為使用者確認的漏斗式折衷。

### 修正二：ETF 單檔診斷下方 3 區塊統一吃「上方那一個代號」
- `src/ui/etf/etf_tab_smart.py`：`render_std_band_section` / `render_correlation_finder` /
  `render_333_section` 三函式簽名改 `(ticker, key_suffix)`，**移除各自的獨立 ETF 代號 text_input**
  與失效的 `etf_g_active` fallback；無代號時 fail-loud 顯示提示（不再顯示假的 0050）。
  新增 `render_smart_ticker_input()`：組合頁專用單一共用輸入框（3 框收斂成 1 框）。
- `app.py`：單檔頁三區塊改吃 `session_state['etf_s_active']`（上方「開始診斷」代號）；組合頁（無單一
  主代號，`etf_p_active` 只是布林旗標）改用 `render_smart_ticker_input('_grp')` 一個共用輸入框驅動三區塊。
- 順手修：`etf_tab_smart.py` 補 `TYPE_CHECKING import pandas`，清掉 693004c 遺留的 `test_no_undefined_names`
  紅測（`"pd.DataFrame"` 字串註解 undefined name ×3）。

### 驗證
- 新增 `tests/test_etf_smart_ticker_wiring.py`（4 測）+ `tests/test_picker_funnel.py`（3 測），全綠。
- AppTest 實機 smoke：ticker=None 顯示 3 提示不炸；組合頁只剩 1 共用輸入框；exception=0。
- 全套件：`test_no_undefined_names` 由紅轉綠；本次改動零新增失敗。剩餘紅測 = 既有（china macro
  CHN_BCI ×2 + resample audit ×1，屬 v18.459 改名遺留）+ risk_radar ×3（網路/測試順序污染，單獨跑全過）。

---

## 🔍 2026-07-03 全面稽核待修清單（跨 Tab 稽核）

> Claude 逐檔讀取所有 Tab 後彙整，對照 2026-07-03 真實市場數值確認。
> 修完一項請在前面改為 ✅，並在括號內標版本號。

### 🔴 HIGH（影響判斷正確性）

- ✅ **[H1] VIX 雙重綠燈** (v18.459) — `src/data/macro/macro_core.py:518` `_sig_vix()`：VIX > 30 改為 ⚫「極端恐慌（逢低加碼訊號）」`#8b949e` 深灰色，與正常平靜 🟢 明確區分。

- ✅ **[H2] Bloomberg RSS 靜默死亡** (v18.459) — `src/data/news/news_fetcher.py:97`：移除 `feeds.bloomberg.com/markets/news.rss`，並更新 docstring。

- ✅ **[H3] Investing.com RSS 封鎖** (N/A) — 稽核確認 stock dashboard 的 `news_fetcher.py` **從未包含** Investing.com；此項僅存在於 Fund dashboard（已在 Fund 端修除）。

### 🟡 MEDIUM（資料品質或門檻偏差）

- ✅ **[M1] CHN_PMI 標籤錯誤** (v18.459) — 修正為 CHN_BCI：
  - `macro_core.py:241` key 名 `CHN_PMI` → `CHN_BCI`（加版本 comment）
  - `macro_helpers.py:800` `_CHINA_SUBSCORE_THRESHOLDS` key 同步更新
  - `classify_china_regime()` 的 reason 字串 `PMI=xx` → `BCI=xx`（兩端）
  - China Drag 面板 caption 加 `⚠️ BCI=OECD 商業信心指數(BSCICP03CNM665S,基準值 100 ≠ PMI 50 榮枯線)` 說明

- ✅ **[M2] USDTWD 顏色盲區** (WONTFIX-cosmetic) — 稽核確認 `MACRO_THRESHOLDS['USDTWD']` 在 stock dashboard **未被任何 signal 渲染程式讀取**（USDTWD 訊號走 `calc_twd_trend()` 斜率邏輯，不用絕對閾值）。此 dict 僅文件參考，30.5-32.0 盲區不影響實際 UI 輸出。`MACRO_THRESHOLDS` 的 F-GRAY-4 注解說明此特性，故無需修。

- ⬜ **[M3] ISM PMI 備援刻度衝突** (WONTFIX — 稽核確認 `fetch_ism_pmi()` 為 dead code，UI 未呼叫) — `macro_core.py:609`：Production UI 的 `ism_pmi` session_state key 實際由 `fetch_tw_pmi_block()` 填入台灣 PMI（14 處讀取點），`fetch_ism_pmi()` 僅在 tests 有 ref。OECD 備援顯示問題不存在於實際 UI。無需修改。

- ⬜ **[M4] AAII 情緒調查抓取脆弱** (WONTFIX — 稽核確認 stock dashboard **從未使用 AAII**，grep 全 src/ 無任何 aaii/AAII 字串，此項為誤植。無需修改。)

- ⬜ **[M5] FT RSS 需訂閱** (WONTFIX — 稽核確認 `src/data/news/news_fetcher.py` **從未包含** FT RSS URL，此項為誤植。無需修改。)

### ⚪ LOW（邊界設計或 UX 微調）

- ✅ **[L1] CBC_RATE 永遠卡邊界** (v18.460) — `macro_core.py:236`：`yellow_above: 2.0 → 2.125`，現行 2.0% 不再卡邊界，下一升息步幅為 2.125%。

- ✅ **[L2] USDCNY 門檻長期無綠** (v18.460) — `macro_core.py:244`：`green_below: 7.0→7.1 / yellow_above: 7.2→7.3 / red_above: 7.4→7.45`，對齊人民幣 2022 後 7.1~7.35 實際區間。

- ✅ **[L3] Yahoo Finance RSS 格式待驗** (v18.460) — `news_fetcher.py:94`：`https://finance.yahoo.com/news/rssindex` 實測確認 HTTP 200 + application/xml，格式正確。同批亦發現 **鉅亨網 CNYES RSS 已死亡**（`/rss/cat/headline` 重定向至 `/twstock/error.htm` 404），改換 **中央社財經 RSS**（`https://www.cna.com.tw/rssfeed/news/afe.aspx`，台灣官方通訊社）。

---

## 🚀 目前狀態(v18.462 — OAuth 搶帳號漏洞修復)

✅ **v18.462(2026-07-04)**:修復 OAuth 搶帳號漏洞（嚴格 state 驗證）:
- **根因**:`handle_oauth_callback()` 舊版在「本 session 無 `_oauth_state`」時退回放行，讓未啟動 OAuth 的分頁能接受別的 session 的授權碼。
- **修法**:`src/data/portfolio/oauth_state.py` — 改為嚴格版：只要 URL 帶了 state 就必須完全相符，否則一律略過。

---

## 🚀 前一狀態(v18.460 — LOW 稽核修正 + 綜合重新檢查)

✅ **v18.460(2026-07-03)**:LOW 稽核項目修正 + 全面重新確認:
- **[L1] CBC_RATE 邊界**：`MACRO_THRESHOLDS["CBC_RATE"] yellow_above: 2.0→2.125`，現行 2.0% 顯示🟢，避免邊界跳動。`src/data/macro/macro_core.py`
- **[L2] USDCNY 門檻**：`MACRO_THRESHOLDS["USDCNY"]` 三區更新：`green_below 7.0→7.1 / yellow_above 7.2→7.3 / red_above 7.4→7.45`，對齊人民幣 2022 後實際弱勢區間。`src/data/macro/macro_core.py`
- **[M4] AAII**：稽核確認 stock dashboard 從未使用 AAII（grep 無命中），WONTFIX。
- **[M5] FT RSS**：稽核確認 news_fetcher.py 從未包含 FT RSS URL，WONTFIX。
- **[L3] Yahoo Finance RSS + CNYES 死亡**：Yahoo Finance `news/rssindex` 實測 HTTP 200 確認正常 ✅；同批發現 CNYES 鉅亨 `/rss/cat/headline` 重定向 404 死亡 → 改換中央社財經 RSS `https://www.cna.com.tw/rssfeed/news/afe.aspx`。`src/data/news/news_fetcher.py`

## 🚀 前一狀態(v18.459 — HIGH/MEDIUM 稽核修正)

✅ **v18.459(2026-07-03)**:稽核項目修正:
- **[H1] VIX 雙重綠燈**：`_sig_vix()` VIX > 30 改 ⚫「極端恐慌（逢低加碼訊號）」深灰色，與平靜 🟢 明確區分。`src/data/macro/macro_core.py`
- **[H2] Bloomberg RSS 死亡**：移除 `feeds.bloomberg.com/markets/news.rss`，更新 docstring 來源列表。`src/data/news/news_fetcher.py`
- **[M1] CHN_PMI→CHN_BCI**：`MACRO_THRESHOLDS` key 重命名、`_CHINA_SUBSCORE_THRESHOLDS` key 重命名、`classify_china_regime()` reason 字串全改 BCI、China Drag 面板 caption 加 OECD 刻度說明。`macro_core.py` + `macro_helpers.py` + `ui/tabs/macro/helpers.py`
- **[M2] USDTWD 盲區**：稽核確認為文件參考 dict，不影響實際 UI（訊號走斜率邏輯）。WONTFIX。

## 🚀 前一狀態(v18.458 — 財報領先指標 capex 顯示修正)

✅ **v18.458(2026-07-03)**:財報領先指標 section 標籤與數據修正:
- **`section_financial_leading` 仍顯示 PP&E 存量標榜「資本支出」**:Task#20 修復了龍頭預警(dragon_alert)的比較邏輯，但同一個 `_capex2`(CF 季資本支出)未傳給財報領先指標 section，UI 仍用 PP&E 存量(cx2)且標籤顯示「資本支出」造成誤導。
- **修法**:`render_financial_leading_section` 新增 `capex=None` kw-only 參數；若 capex > 0 則優先以「季資本支出」顯示，cx2 PP&E 作 fallback(標籤改為「固定資產/資本支出」)。tab_stock.py 呼叫端加 `capex=_capex2`(與 dragon_alert 一致)。`section_financial_leading.py` + `tab_stock.py`

## 🚀 前一狀態(v18.457 — t2_inst 修 + Reuters RSS 移除 + 龍頭預警 capex 修 + MJ bootstrap)

✅ **v18.457(2026-07-03)**:Stock dashboard 4 項修復:
- **Task#18 `t2_inst` session key 從未寫入**:`section_kline_chart`(K線敘事「外資買超/賣超」)與 `section_health_score`(v4 籌碼 foreign_net/trust_net)讀 `st.session_state['t2_inst']` 但整個 tab_stock.py 從未寫這個 key → K線敘事恆用 `_fnet_f=0`(顯示「外資中性」)，v4 籌碼欄位恆為 0。修法：在 `_xsec` 計算後、各 section 渲染前，從 df2(已含 T86/TPEX 外資/投信欄，單位張)取最後一日寫入 `t2_inst`。`src/ui/tabs/tab_stock.py`
- **Task#19 Reuters RSS dead**:`news_fetcher.py` 移除 `feeds.reuters.com/reuters/businessNews`(dead since 2020-06),每次新聞抓取白費 timeout。`src/data/news/news_fetcher.py`
- **Task#20 龍頭預警「大擴廠」用 PP&E 存量(cx2)而非 capex(季流量)**:製造業 PP&E 存量動輒數倍股本，幾乎永遠觸發龍頭預警(假正例)。fetch_financials 本就同時抓 BS PP&E 和 CF 資本支出，但 `_capex2`(CF 資本支出)被丟棄未存入 t2_data。修法：t2_data 加 `capex` 欄，傳給 `render_dragon_alert_section`；龍頭預警優先用 CF capex 比較，PP&E 作 fallback(當 CF 資料取不到時)。`tab_stock.py` + `section_dragon_alert.py`
- (含 v18.455/v18.456)ETF 中文名 + MJ 季財報 bootstrap 同批推送

## 🚀 前一狀態(v18.456 — ETF 中文名 attempts=1 bug 修 + MJ 季財報 bootstrap 修)

✅ **v18.456(2026-07-03)**:MJ 季財報分 bootstrap 修:
- **MJ 季財報分恆為 0 根因**:`data_cache/mj_snapshots/` 在 Streamlit Cloud 為 ephemeral 存儲,重啟即清空,永遠湊不齊 2 季 snapshot → `compute_mj_trend_subscore` 回 `(0.0, {"reason": "insufficient_snapshots"})`。
- **解法**:在 `fetch_financial_statements` return dict 加 `prev_period_data` 欄位(用同一個 730 天 FinMind call 裡 `_dates[-2]` 的資料計算上季關鍵指標,約 50 行,無額外 API call)。`compute_one_stock_trend` 保存本季快照後,若 `len(yms) < 2` 則立即用 `prev_period_data` 呼叫 `analyze_financial_health("", sid, prev_period_data, "")` 補存上季快照。每次重啟後第一次抓財報就能湊足 2 季 → `mj_trend` 正常計算。`src/data/core/data_loader.py` + `src/compute/health/mj_trend_score.py`。

✅ **v18.455 補強（PR #455,2026-07-03，另一 session）**:上條 attempts=2 已修 MoneyDJ 路徑;本 PR **另加**兩項:
- **ETF 中文名多一路官方來源**:`fetch_etf_zh_name` 改以 **FinMind `TaiwanStockInfo.stock_name`（官方結構化中文名）為 PRIMARY**、MoneyDJ `<title>` 降 fallback。理由:FinMind 為結構化 API（同 dataset 的 `industry_category` 早已穩定運作），不依賴 HTML `<title>` 格式或 proxy-403 降級,兩路互為備援更穩。`_fetch_etf_zh_name_finmind` 新增於 `etf_fetch.py`;token 選填、讀 secrets 失敗不中斷。
- **Beta 缺值回歸估算**:yfinance `.info` 對台股主動式 ETF 常無 beta（單檔頁顯示 N/A）。新增 L2 純函式 `calc_beta(df, bench_df)`（cov/var,自身 vs 自動偵測基準 0050.TW,inner-join 對齊交易日,有效重疊 <60 交易日回 None）。單檔頁 yfinance 無 beta 時採用,help text 標明來源。測試 `test_etf_zh_name_and_beta.py`（+9）。SSOT/§8.2:calc_beta 為 L2 純函式無 I/O;FinMind 查詢沿用 `FINMIND_API_URL` SSOT;無跨層反向 import。
- ⚠️ **注意**:main 上 `test_china_macro_stock.py`（2 個）+ `test_resample_audit.py`（1 個）為紅 —— 係 v18.459 `CHN_PMI`→`CHN_BCI` rename 後測試未同步更新（與本 ETF PR 無關,屬 china macro 稽核批的收尾項）。

✅ **v18.455（2026-07-03，attempts=2 修）**:ETF 中文名抓不到根因確認並修復:
- **ETF 中文名仍顯示英文名**:web_fetch MoneyDJ 確認標題格式 `元大台灣50-0050.TW-ETF淨值表格 - MoneyDJ理財網` 完全符合既有 regex,**非格式問題**。真正根因是 `fetch_etf_zh_name` 呼叫 `fetch_url(attempts=1)`,而 proxy_helper 降級直連邏輯需 `_block >= 2` 才觸發(line 172),`attempts=1` 在第一次 403 時 break 出迴圈(`_block=1`,未達 2),直連路徑永遠到不了。`fetch_url` default 是 `attempts=3`;ETF 中文名有 7 天 cache,延遲可接受。改 `attempts=2` 即可讓 proxy-403→直連正確運作。`src/data/etf/etf_fetch.py:1968`。

✅ **v18.454(PR #453,2026-07-01)**:user 回報 4 項 production 問題,2 個獨立 agent 交叉驗證後逐一 root cause,3 項可修即修 + 2 項需 user 協助(誠實回報,不猜測):
- **總經頁「M1B-M2 資金動能」頂部燈號恆顯示「—」**(但下方「策略3」區塊正確顯示 -12.63%):`tw_macro.fetch_cbc_m1b_m2()` 本就算好 `gap`,但 `macro_snapshot.fetch_m1b_m2_block()` 重新打包 dict 時,CBC/FRED/IMF 三個 return 路徑全部漏帶 `'gap'` 鍵 → `session_state['m1b_m2_info']` 從未有此鍵 → `macro_helpers.py` 算頂部燈號/KPI 卡(依 `.get('gap')`)恆得 None → 顯示「—」;「策略3」區塊是自己內聯重算 `m1b_yoy-m2_yoy`(不依賴此鍵)才不受影響。補回三路徑 `gap` 欄(schema-additive)。守衛 `test_m1b_m2_gap_wiring.py`(+4)。
- **「個股」分頁整頁 MergeError 崩潰**(`incompatible merge keys dtype('<M8[s]') and dtype('<M8[us]')`,v18.440 per-tab 隔離器攔到不拖垮其他分頁):`section_357_valuation.py:333` PE 本益比河流圖 `merge_asof` 兩側日期精度不同 —— 股價側(data_loader `.dt.date` 物件經 `pd.to_datetime` → `datetime64[s]`)vs 季報側(FinMind 字串日期 `pd.to_datetime` → `datetime64[us]`),兩側從未顯式對齊精度。pandas merge_asof 要求兩側 key dtype 完全一致(含精度),不同即炸。兩側補 `.astype('datetime64[ns]')`。守衛 `test_pe_river_merge_dtype.py`(+4 純邏輯 + 1 slow AppTest)。
- **ETF 多檔比較表「1Y累積%」對年輕 ETF 顯示假 212%**(user 截圖 00981A 上市僅 13 個月):與 v18.452 `calc_cagr` 同源根因 —— `calc_total_return_1y` 只看「有沒有資料」不看「是否真橫跨 1 年」,年輕 ETF 的 `p_start` 實為上市首日低價而非真 365 天前價格。新增可選 `require_full_period`,資料跨度不足 365 天 90% 回 None(§1 寧缺勿假);兩 ETF UI 呼叫端(single/grp_compare)補齊 None 顯示 N/A。守衛併入 `test_etf_grp_compare_young_etf_fix.py`(+5)。
- **MJ 季財報分恆為 0**(待定):需連續 2 季 snapshot 才能算 delta,但 snapshot 存本機 `data_cache/mj_snapshots/`(.gitignore,Streamlit Cloud 重啟即清空),永遠湊不齊 2 季 → 架構決策(改存 GitHub / Google Sheets 等持久層),待 user 定奪。
- 測試 2520 pass(fast lane)。SSOT/§8.2:無新增 SSOT 常數 / 無新增例外 / 無跨層反向 import;M1B-M2 修復為「正確透傳 tw_macro 早已算好的 gap」而非消費端重算。

---

## 🗂 前一階段(v18.452→453 — 6 處 undefined-name 崩潰 + ETF 假資料 + 個股組合負債比不一致,PR #451 已 merge)

✅ **v18.452→453(PR #451,2026-07-01)**:user 回報「個股」「總經」「個股組合」三分頁陸續出錯 + 附完整 production log,逐一 root cause 確認全部同一根因(大檔案抽出成獨立模組時漏搬 import/變數):
- **ETF 多檔比較假資料**:名稱欄只用 yfinance shortName(常回發行商英文名,非商品名)→ 改用既有 SSOT `fetch_etf_zh_name()`(MoneyDJ 中文名,原本只有 etf_tab_single.py 在用)。`calc_cagr`/`calc_avg_yield` 新增可選 `expected_years`/`require_full_years` 嚴格模式:年輕 ETF(如上市僅 13 個月)資料跨度不足宣稱年期時回 `None`(§1 寧缺勿假),不再外推出「00981A 假 191% 3Y CAGR」這類不可能數字。兩參數皆預設維持舊行為。
- **6 處 undefined-name 崩潰**(用 pyflakes 全域靜態掃描一次找出,而非等 production log 逐一現形):`section_short.py`(總經 §5 短線急殺桶)缺 `TRAFFIC_GREEN/RED/YELLOW`/`os`/`plotly.graph_objects`/`BREADTH_BULL_PCT`/`BREADTH_NEUTRAL_PCT`/`add_danger_hlines` 共 8 處 import,ADL 資料一載入就 100% 全頁炸;`section_357_valuation.py`(個股 357 評價)結尾殘留一段完全重複且用未定義 `cheap2/fair2/dear2` 寫死的舊邏輯,直接刪除;`tab_stock_picker.py` 的 `_check_dividend_5y` 傳入未定義 `_t_yf`,導致「智慧選股」Stage 1/2 兩張表對任何股票都 100% NameError、整檔回退成全 ❓N/A(v18.374 抽 L1 fetcher 時漏改)—— 改用 `fetch_stock_history_1y` 已解析出的正確後綴建構真正的 `yfinance.Ticker`。另 2 處(`section_news_ai.py` 缺 `json`/`datetime`、`section_state.py` 缺 `pd`)尚未在 production 現形但屬同一顆未爆彈,一併清除。新增 `tests/test_no_undefined_names.py`(pyflakes 全域靜態守衛,CI 補裝),較功能測試更早、更全面攔截此類回歸;每個修復皆用 `git stash` 驗證「還原前程式碼 → 測試精準重現原始錯誤」。
- **個股組合負債比判定不一致**:盤點 3 張健檢表格(批次財報體檢/MJ趨勢分數/智慧選股)後確認唯一真衝突是負債比 ——「批次財報體檢」用 40/60% 三級門檻,「智慧選股」Stage 1 獨立重算卻只用 <50% 二分,同一檔股票兩處顯示不同顏色。三率三升等其餘欄位盤點後確認是水準 vs 趨勢的不同面向,非同一事實重複,故不強行合併;Stage 2 六項籌碼技術指標與 MJ 月營收分皆為獨有資訊,維持現狀(user 核准此範圍,§8 對齊後才動工)。修法:`_check_debt_ratio` 新增可選 `fh_result` 參數,個股組合場景直接沿用 `analyze_financial_health()` 已算好的判定(該版本另有負債比為 0 時的重算 fallback,品質更完整);無 `fh_result` 的呼叫端(高息網等)行為不變。
- 測試 2508 pass(fast lane)+ 新增 34 個測試(ETF 10 + undefined-name 守衛 7 + picker 17)。SSOT/§8.2 影響:無新增 SSOT 常數(沿用既有 `shared.colors`/`shared.signal_thresholds`/`analyze_financial_health`),無新增例外,無跨層反向 import。

---

✅ **v18.449**:市場廣度(市場廣度 chip)真值接線 + 頂部燈號 vs 五桶關係說明。user 質疑「五桶全紅但頂部仍顯示多頭」是否矛盾 —— 查證後**非 bug**,是設計上刻意分工(頂部=短期戰術訊號,只看 MA120 趨勢 + health;五桶=多時域風險分層,任一項亮紅即整桶紅)。但查證過程中意外發現真技術債:`market_strategy.market_regime()` 的 `ad_ratio`(市場廣度)參數預設 `1.0` + 門檻 `>1.0`,兩者恰好同值 → 此因子**從未真正生效過**,UI 上「❌ 市場廣度偏弱」永遠是同一個寫死值,且 `get_market_assessment()` 從未有這個參數可傳。user 明確要求「我都要真值+判斷過的」。修法:①改 `ad_ratio=None` 選填(同 `m1b_m2_gap` 慣例,未接真值前誠實不計分,不塞假中性值);② SSOT `MARKET_BREADTH_NEUTRAL_PCT=50.0`(0-100% 百分比尺度,對齊 `fetch_adl` 真實資料源與五桶 `adl` DangerSpec,修正原碼「比值尺度門檻套百分比資料源」的尺度錯誤);③ 打通 `tab_macro.py`(`df_adl_raw`,早就抓到手但從未傳出)→ `compute_and_apply_market_assessment`→ `get_market_assessment`→ `market_regime` 全鏈路;④ 修正 `max_score` 分母(原碼 5/6 恆虛高 1,因 ad_ratio 從未真正達標過)。頂部卡片新增 `st.caption` 說明兩組指標評估範疇不同。測試 +10(`test_market_strategy.py` 6 + `test_market_assessment_apply.py` 4)。全 suite 2548 passed。

✅ **v18.447(PR #446)**:總經分頁全頁炸 `NameError: name 'render_section_mid' is not defined`(v18.440 per-tab 隔離器攔到,其他分頁不受影響)。根因:`section_long.py` 結尾殘留一行 F-7.1 B-4 抽出 `section_mid.py` 時沒清乾淨的雜物呼叫,該檔從未 import 它。真正呼叫鏈已在 `tab_macro.py`(orchestrator)正確存在。修:刪雜物呼叫(不補 import,否則重複渲染兩次)。掃描全部 macro section 檔案排除另 2 個誤判(皆為 docstring 內文字)。守衛 `test_macro_section_render_wiring.py`。

✅ **v18.443→446(#442-445,4 輪疊代)**:ETF 折溢價 endpoint 三次猜錯 + user 親自用 Chrome DevTools 抓包才找到真相的完整過程 ——
- v18.443/444:猜測 `openapi.twse.com.tw/v1/ETF/TaiwanStock*`(其實是 FinMind dataset 命名慣例,TWSE OpenAPI 無此路徑,一路 404)+ 修正代理機制誤用(`nas_relay_fetch` 只認 FastAPI 中繼站 `NAS_BASE_URL`,user 實際設的是 Squid `PROXY_URL`)。
- v18.445:改猜 `mis.twse.com.tw/stock/etf_nav.jsp`(舊站改版前路徑,新站已無)。
- **user 親自用 DevTools Network 面板**打開官方頁面「ETF發行單位變動及預估淨值揭露專區」,抓到背後真正呼叫的 API:`mis.twse.com.tw/stock/data/all_etf.txt`,並展開 JSON 用 0050/0051 真實數值驗算欄位對映(`g == (e-f)/f×100` 皆吻合)。
- v18.446:接上正確 endpoint。仍抓不到值 → v18.448 追查發現兩個真根因:①`fetch_url(attempts=1)` 既有 bug(403 降級直連需連續 2 次,attempts=1 時第 1 次 403 直接放棄永遠到不了直連);②TWSE MIS 是舊式 Java/Tomcat 系統,瀏覽器實測請求帶 `JSESSIONID` cookie,暗示資料端點需要有效 session。改自建 `requests.Session()`:先 GET 揭露頁面暖身建立 session,再用同 session 取 `all_etf.txt`,「Squid 代理→直連」兩層明確 fallback。
- **教訓**:endpoint 存在性/欄位語意純靠網路搜尋猜測風險極高(v18.443/444/445 三次全錯);user 親自用瀏覽器 DevTools 反查才是唯一可靠方法,之後遇到類似「資料抓不到」問題應優先請 user 協助抓包,而非繼續猜。

---

✅ **v18.442(PR #440)**:ETF 折溢價對 0050.TW 又顯示假 **+5.07%「🔴 嚴禁追高」**(wantgoo 同日 -0.13%)—— 與 v18.441 **不同一條**:即時來源(yfinance navPrice / goodinfo)回「最後已公告淨值」被 `fetch_etf_nav_history` 硬戳 `_last_bd`(今日),0050 案該 NAV 實為 104.03(=06/29 過時值)被戳成 07/01 → 與當日市價 109.3 **同日** inner-join 成功、日期守門員 G1/G3 全過(**日期被造假成同日,擋不到**),算出假 +5.07%。原 G2 上限守門員(|prem|>2%)只對**主動式**生效,被動式 0050 漏接。修:新增 SSOT `PASSIVE_ETF_PREMIUM_MAX_PCT=3.0` + L2 `etf_premium_sanity_max(is_active)`,`calc_premium_discount` Path A/B/B2 上限守門員擴及全 ETF(超限回 stale + `stale_reason='nav_value_stale'`,UI 顯示「⏳ NAV 資料延遲」而非假溢價);近期淨值表同步過濾 |折溢價%|>上限的假列。守衛 `test_premium_stale_guard.py`(+3 case)。**誠實備註**:修後 0050 折溢價卡會顯示 N/A(NAV 來源給的是過時值),等 FinMind/TWSE 更新到同日才顯示真 -0.13% —— §1 寧缺勿假,不再拿過時 NAV 假配。

---

✅ **v18.438→441 production 修復連鎖**(2026-06-30,已全 merge 到 main;起因:v18.437 清碼 merge 觸發 Streamlit 重新部署,暴露一批**久未執行/未綁定**的渲染路徑潛伏 bug。逐一 fail-loud 修 + 補守衛測試):
- **v18.438(PR #435)**:ETF 單檔/組合分頁 `ImportError: cannot import name '_colored_box'` —— `render_etf_single/portfolio` late-import 互相從「對方 tab」拉 21+15 個 helper,但這些 helper 實在 `etf_render`(L4)/`etf_calc`(L2)/`etf_fetch`(L1)。改指向真 SSOT 來源,打斷 tab↔tab 循環。守衛 `test_etf_tab_imports.py`。
- **v18.439(PR #436)**:總經/個股/個股組合/教學 **4 分頁全空白** —— `94a257d`「chore(dead): 刪 4 個 0-caller dead fn」誤把 `with tab_X: render_tab_X()` 綁定當死碼刪掉(pre-existing,早於本 session)。還原綁定(tab 內 lazy import 免循環 + 免 F401 再刪)。守衛 `test_app_tab_wiring.py`。
- **v18.440(PR #437)**:教學分頁 `render_tab_edu` → `make_sparkline` 傳了已移除的 `high_is_bad/lookback` → TypeError **拖垮全頁**。對齊簽章(`list(_series)[-60:]`)+ **4 分頁 per-tab try/except 隔離**(`_render_tab_isolated`:單分頁錯只在該 tab st.error,不再拖垮全頁)。
- **v18.441(PR #438)**:ETF 折溢價對 0050.TW 顯示假 **+5.16%**(實際 -0.12%)—— `calc_premium_discount` Path B2 假日兜底拿過時 NAV(06/29≈104)配當日市價(07/01≈109.45)硬配。加「NAV 早於市價 ≥1 天 → stale」守衛(與 G1 同原則)+ 全路徑回 `nav_date`/`price_date`,UI 標「NAV 最新日 X｜市價日 Y」。守衛 `test_premium_stale_guard.py`。
- **SSOT / §8.2 檢查**:4 修全數過 —— 沿用既有 SSOT(`calc_premium_discount_pct` D4 / render/calc/fetch 真來源)、無新 inline magic、L5→L4/L2/L1 與 L6→L5 皆 downward、L1 fetcher 屬 EX-PASSTHRU-1、無新增反向 import。測試 **2514→2522 pass / 0 fail**。
- **教訓**:這批 bug 都是「分頁久未綁定渲染 → code 與 helper 簽章漂移 + 空測試覆蓋走不到」造成;已補 per-tab 隔離(單分頁錯不拖垮全頁)+ 3 支守衛測試釘綁定/簽章。

---

## 🗂 前一階段(v18.437 — 清碼/死碼深掃 + SSOT 收斂批次)

✅ **v18.437 清碼/死碼深掃 + SSOT 收斂**(2026-06-30,branch `claude/dazzling-turing-QxI9m`,8 commit 已推送,測試 2514 pass / 0 fail):
- **死碼**(`47629fe`):真死碼 3 處刪(`build_ai_data_table` 0-caller / `get_proxies` 被末尾別名遮蔽的無快取 def / scoring_engine 不可達 `WEIGHT_TABLES`)+ ~53 未用 import 機械清(ruff F401,以 F821 + 全測試交叉驗)。**翻案排除**:tab_stock/tab_macro 87 個 import(被 source-string SSOT 守衛 + except handler `ThreadPoolExecutor` NameError 防護綁定,機械清會 regression)+ `emoji_to_hex`(跨 repo auto-sync 檔,DO NOT EDIT)。
- **D1/D2/D4 計算層重複公式 → SSOT**(`af7da37`,+12 測試,數值等價驗證):布林帶寬(scoring_engine 走 `calc_bollinger_width_series`)/ z-score(`macro_core` + `multi_factor` → `shared.stats_helpers.zscore`)/ ETF 折溢價(etf_calc → `calc_premium_discount_pct` 委派 calc_bias_pct,不另抄)。v5_modules 布林**翻案不收**(upper/lower 為回傳值,走 series helper 反成雙重計算)。
- **D3 pkl 磁碟快取 → cache_layer SSOT**(`6b54763`):`fetch_single` + `fetch_flow_snapshot` 收(同檔 fetch_institutional 模式,inline 30 分 magic → TTL_30MIN)。`fetch_adl`/`build_leading_fast` **翻案不收**(自訂 _alog / PR-L2 stale-fallback 富快取,非簡單樣板)。
- **D6 provenance log → prov_log SSOT**(`f052415`):8 站手寫多行 stderr provenance print 收斂為 `prov_log()`。
- **D5 FinMind client 正規重構**(`69a462a`/`732e0f5`/`4ccd09a`,+8 測試,§8 user 核准):新增 `src/data/core/finmind_client.py`(L1 SSOT,零行為漂移設計)+ `leading_indicators.finmind_get` 改 thin re-export;遷 4 站 plain-requests GET。**深查翻案(最重要)**:audit 原報「~12 站重複」,實測剩 ~14 站「看似重複、語意實不同」— Proxy Session 站(帶 NAS Squid 代理 + Retry + verify=False,geo-block 繞道核心)+ HTTP-status-gating 站(gate on resp.status_code 而非 JSON status)暫遷後 **7 測試紅 → 全還原**,確認**不可機械收斂**,理由寫入 finmind_client docstring「適用範圍」防再誤報。

✅ **Phase 2 全完成**(2026-06-30 PR #429~#433 共 5 PR 合併,base v18.429)。
✅ **post-merge 連續批次**(2026-06-30,branch `claude/dazzling-turing-QxI9m`,未開 PR):
- **v18.430-432**:scoring_helpers:239 BW shrink SSOT 漏網 + EX-OAUTH-1 正式登錄 + SSOT-BB-MULTI 2-tier(布林近上軌 0.97 LOOSE / 0.995 STRICT)
- **v18.433-434 pandera POC**:P1 落地 3 hot-path fetcher(OHLCV/ETF/月營收)+ P2 補 PMI/ForeignFlow schema + P3 補 4 macro 時序(cpi/unemp/discount/usdtwd)log-mode 驗證
- **v18.434 S-PROV-1 收尾**:ETF 2 + macro 3 漏網 fetcher prov;個股 4 fetcher prov(其餘大批 audit 重盤後確認 pre-existing 已 prov)
- **v18.435 WONTFIX 翻案(深挖)**:S-MED 仍 0 真 bug,但 §8.3 灰色地帶深挖找出 4 個真 latent bug 並修:
  - cache_layer sentinel violation(合法 None 被當 miss)
  - daily_data_fetchers pickle.load file handle leak(無 with block)
  - app.py _gemini_rr round-robin race(讀+寫非 atomic → 加 Lock)
  - stock_names_fetcher _dynamic_cache rebind race(改 .clear()+.update() in-place)
- **v18.436 全做 audit(7 維度 + 對抗驗證,78 候選→32 survived)**:
  - C:8 inline magic SSOT 化(外資期貨防禦/VPOC/經理任期/FGMS 退路/KD/IBS/量比/547 回測)
  - #21:health_inspector「待補抓」空承諾 → 誠實導引手動更新
  - #23:calc_bias_pct_series series SSOT(etf_render inline 收斂)
  - #22/#20:doc 對齊(inst_sanity helper 已落地待 consumer / foreign_net 單位外部阻斷)
  - #25:false-positive(R1 wrapper 5/5 在用,分散 section 檔)

✅ **架構淨檢(v18.436 全域 audit)**:§8.2 分層違規維度 = **0**(除已登錄 EX-* 例外)。

### 殘餘待辦(全 LOW / 非阻斷,§-1 預設停手)
- 測試覆蓋:9 模組(v4_strategy_engine 等核心 + L1 fetcher)無獨立測試 — v18.436 補測批進行中
- pandera P3 長尾:30+ dict-return fetcher 無 tabular shape,維持 WONTFIX(無法套 DataFrame schema)
- foreign_net 啟用:待外部確認 FinMind buy/sell 單位(非程式項)

## 📊 累計度量(v18.429)

| 度量 | 值 |
|---|---|
| tab_macro.py LOC | 5387 → 488(**-91%**) |
| tab_stock.py LOC | 3672 → 1621(**-55.9%**) |
| tab_stock_grp.py LOC | 3673 → 303(**-91.8%**, Phase 2 Batch 7 全 5 子批) |
| app.py LOC | 7300 → 642(pure router + orchestrator)|
| Dead code 清除 | -666 LOC(ai_engine -654 + fuzzy_get -12)|
| §3.3 反捏造違憲 | 0 |
| §8.2 hard rule 違憲 | 0(grep 驗證:L1 import streamlit 全 EX-CACHE-1 letter compliant;L2 無 I/O;0 反向 import)|
| §8.2.A active 例外 | 3(EX-L0-1 / EX-CACHE-1 7 處 / EX-PASSTHRU-1 25+ 處)+ 2 退役(EX-AI-1 / EX-RENDER-1)|
| §4.3 重算對帳 | 3 / 3 落地(US10Y / 月營收 / 健康評分)|
| §5 SSOT 收斂 | 6 處 magic SSOT(Batch 5a 停損 + 5b 布林帶寬 2-tier);乖離 / RSI / MA / 健康評分 / FinMind URL / TWSE URL 等已全 SSOT |
| pytest | 2294 pass / 10 skip / 14 deselected |
| Phase 2 累計 PR | #429~#433(5 PR 全 merged)+ 早期 #398~#428(34 PR)= 39 PR |

## 📋 Phase 2 全 batch PR 清單(#429-#433,5 PR + 早期 #428 起算 6 PR)

| PR | 主題 | 主要結果 |
|---|---|---|
| #429 | Phase 2 Batch 1(R-CALC-3 乖離 + R-CALC-1 RSI 雙 SSOT)| 乖離 inline 8 處 → calc_bias_pct SSOT;RSI thin wrapper |
| #430 | Phase 2 Batch 2+3+4(R-UI-1 border-left + R-FETCH-1 股本 + R-CALC-2 MA scalar)| inline HTML SSOT;_fetch_share_capital UI→L1 搬移;safe_ma 5 子批 |
| #431 | Phase 2 Batch 6+10(健康評分對帳 production + FinMind URL SSOT 17/37)| §4.3 health reconcile embed in calc_traffic_light;首批 17 處 URL |
| #432 | Phase 2 A+B+C(Batch 10b URL 收尾 + Batch 8 三大法人 WONTFIX + Batch 7-1 起步)| 12 檔 FinMind URL 全集中;tab_stock_grp section 化 51 LOC 抽出 |
| #433 | **Phase 2 全 5 batch 收尾**:tab_stock_grp 拆檔 + L0 helper + L1 fetcher + magic SSOT | 18 commit,9 個 batch 累計:Batch 7-2~7-5(-1117 LOC)+ Batch 8.1(BFI82U URL)+ Batch 9/9-2(357 殖利率 SSOT)+ Phase 2 V1/V2/L0/R-UI-FETCH/D10/magic 全做 |

## 🏁 PR #433(v18.429,merged 2026-06-30 commit bbb282b)

### 累計成果

**檔案搬移 / 新建**:
- ✅ 5 個 stock_grp_sections/ 模組(market_status / batch_fetcher / portfolio_summary / financial_health / ai_portfolio)
- ✅ 2 個 L0 shared helper:`shared/etf_codes.py`(bare_etf_code)+ `shared/etf_universe.py`(REGIONAL_ETFS + CROSS_ASSET_ETFS + all_symbols)
- ✅ 2 個 L1 fetcher 遷層:`src/data/macro/foreign_flow_fetcher.py`(R-UI-FETCH-1)+ `src/data/stock/chip_concentration_fetcher.py`(R-UI-FETCH-2)
- ✅ 新增 2 個 SSOT 常數:`BB_BW_SHRINK_WARN_RATIO=0.7` + `BB_BW_SHRINK_ACTION_RATIO=0.6`(布林帶寬 2-tier)
- ✅ ARCHITECTURE.md 升 v9.2 + §0.11 audit findings doc

**架構違規收斂**:
- ✅ §8.2 L1→L2 反向 import 9 處全消除(bare_etf_code + all_symbols 下沉 L0)
- ✅ §8.2 EX-CACHE-1 letter compliance:etf_calc / etf_quality 補 try/except + _NoOpST
- ✅ §8.2 R-UI-FETCH-1/2 違憲消除(2 個 L1 fetcher 從 UI 抽出)
- ✅ D10 真重複消除(etf_render._teacher_conclusion 委派 ui_widgets SSOT)
- ✅ 6 處 magic number 收 SSOT(停損 0.92 → STOP_LOSS_PCT;布林帶寬 0.7/0.6 × 5)

**audit 翻案 WONTFIX(documented 證據)**:
- ⊘ Batch 5 月營收 3 路(endpoint 已 SSOT,wrapper 差異有理由)
- ⊘ Batch 8 三大法人 dispatcher 統一(4 路真不同 endpoint)
- ⊘ Batch 9 cross-file 個股 vs ETF 殖利率(公式真不同)
- ⊘ R-FETCH-4 配息 base(output format / fallback chain 差異大)
- ⊘ R-UI-1 51 處 border-left 殘留(全 multi-line bespoke shapes)
- ⊘ 停損 0.93 / 0.07 / 布林近上軌 0.995 / 0.97(各自單 use + 不同概念)

### Post-merge audit ✅ PASS

| 項目 | 結果 |
|---|---|
| §8.2 hard rule violations | **0** |
| L1→L2 / L2→L3 / L3→L4+ 反向 import | **0** |
| 新檔 foreign_flow / chip_concentration | EX-CACHE-1 letter compliant + S-PROV-1 phase 19 ✅ |
| etf_render._teacher_conclusion shim | 23 caller 確認 ✅ |
| L0 helper re-export shim | backward compat ✅(無 caller 改動需要)|
| SSOT 微缺口(audit 候選,非阻斷)| 3 處 — 詳見下方「未做的 minor 候選」|

### 未做的 minor SSOT 候選(audit 找到但未動工,非緊急)

| ID | 位置 | 內容 | 建議 |
|---|---|---|---|
| **SSOT-BB-MULTI** | tech_indicators.py:118(0.97)+ v4_strategy_engine.py:338(0.99)+ v5_modules.py:247(0.995)| 3 個布林近上軌 inline 不同精度,`BB_NEAR_UPPER_RATIO=0.97` SSOT 已存但未全 caller 引用 | 翻案 candidate:可能 3 個精度故意分流;或統一至 SSOT |
| **scoring_helpers:239 漏網** | `bb['bw'] < bb['bw_mean'] * 0.7` | Batch 5b 漏掃的第 6 處 BB_BW_SHRINK_WARN_RATIO candidate | 直接替換,3 LOC + 1 import |
| **oauth_state.py L1 直 import streamlit** | src/data/portfolio/oauth_state.py:25 | 已 documented (D4 v18.400 歸位)但未正式登錄成 §8.2.A EX-OAUTH-1 例外 | doc-only:CLAUDE.md §8.2.A 補例外行 |

## 📋 早期 session PR 清單(#398-#428,33 PR — 歷史保留)

| PR | 主題 | 主要結果 |
|---|---|---|
| #398-#409 | governance + Dead code audit 6 輪 + pandera POC + S-MED | -666 LOC dead;详见前版 STATE |
| #410-#428 | F-Q / R / D / C / U 系列(structural refactor 收尾)| tab_macro/stock 拆檔大量結案 |
| #429-#433 | **Phase 2 全 5 batch(本批)**| 見上方詳述 |

詳細歷史見下方各 PR 區塊。

## 🏁 PR #400 v18.395(merged 2026-06-29)

## 🏁 PR #400 v18.395(merged 2026-06-29)
**P5 Batch1:C1+C2 AppTest 实機驗 + B6 version pin + A4 archive 精簡**

接 user「同時做」隊列首批,LOW risk 3 件套:

### C1+C2 AppTest 实機驗
- 靜態 AST 守衛(已存在)+ runtime AppTest(新增 4 case)雙層守護
- panel test ✅ 通過 = PR #399 实機驗成功(無需 user 手動部署)
- News AI test 在無 secrets 環境自動 skip(production 必有)

### B6 version pin
14 套件加 major version upper bound,實機 env 0 conflicts(不降級 production)

### A4 §十 archive 精簡
- 18 LOC 復活註解 → `ARCHIVED_FEATURES.md`(新檔)
- tab_macro 留 1 行導向標記
- tab_macro:488 → 471 LOC(-17,-3.5%)

### 驗證
pytest 2214 pass / 0 fail / 36 deselected (slow);slow lane 11 pass / 2 skip

### Batch 2~5 隊列
- A5 pandera POC
- B3 app.py 拆檔 audit + 第一批
- B5 雙演算法對帳 × 3
- B4 daily_checklist pkl 收尾
- 改判 4 項(A3 macro_validation 真刪 / B1 etf_render cache.clear 抽 L3 /
  B2 EX-PASSTHRU-1 12+ 補登錄 / D1 S-MED 710 重 audit)

---


## 🏁 PR #399 v18.394(merged 2026-06-29)
**data_registry live state — Path C panel + SSOT 11 emoji category**

### 任務 #4 接續(C 為主 + B 的 SSOT 修法)
深挖發現 `session_state['data_registry']` 是 dead state(P1-X scanner + P3-D8 patch
寫 ~80 entries 但 0 reader)+ 3-way category SSOT 漂移。

- **SSOT 11 emoji 集中**:新檔 `shared/data_categories.py`(L0)
  - 11 CAT_* constants 對齊 static `src.data.core.data_registry`
  - `category_for(name, fallback)` + `coverage_emoji_for(cat)`
- **scanner / patch 對齊**:`data_registry_scanner` + `macro_registry_patch` 8 處
  inline `'大盤'/'個股'/'ETF'` 改 CAT_* 常數(rebuild fallback 5-set 檢查)
- **Path C panel**:新檔 `src/ui/pages/data_registry_panel.py`(177 LOC)
  - `compute_registry_groups` + `_freshness_emoji` 純函式易測
  - 按 11 emoji 分組 expander;🟢🟡🔴⬜ frequency-aware freshness lamp
  - `app.py:1522-1527` hook 進 🔎 資料診斷 tab(coverage 之後)
- **15 新測試**:`tests/test_data_registry_panel.py`(category SSOT + freshness +
  groups + 靜態守衛防 SSOT 再漂移)

### 驗證
- pytest 2214 pass / 0 fail / 32 deselected(slow)
- baseline 2199 + 15 新測 = 2214,無回歸
- 留 user merge 後在 🔎 資料診斷 tab 看新 panel 实機

### Streamlit 实機未驗(留 user)
PR merge 後在 deployed app 點 🌐 總經 → 🚀 一鍵更新 → 切到 🔎 資料診斷
→ 看 ⓪ 4-row coverage 之後出現「📋 資料源完整清單」panel 渲染 50+ entries
按 SSOT 11 emoji category 分組。

---


## 🏁 PR #398 v18.393(merged 2026-06-29)
**深挖第三輪:1 真 bug + 1 大塊真不可抽 + 例外清單收齊**(3 件套)

### P0-FIX(真 bug)
- `tab_macro.py:749` `render_section_news_ai(_macro_info, ...)` `_macro_info` 從 D-12 後未定義
  → 走入 §十一 News AI 100% NameError 全頁炸
- 修:L749 前補 `_macro_info = st.session_state.get('macro_info') or {}`
- 新增 AST 守衛 `test_render_section_news_ai_args_defined_in_scope` 防同類再犯
- pytest 2220 case 全是 source-string assert,5 個 commit (B-4 → D-13) 沒抓到

### P1-X(真不可抽 第三次誤判 — 275 LOC 完全可抽)
- `tab_macro.py:373-647` inline DataRegistry 區塊(2 inner def + 8 for 迴圈掃 12 session_state key)
- 抽 `src/services/data_registry_scanner.py`(324 LOC)
  - `scan_and_write_data_registry(*, intl_map, tw_map, tech_map) -> None`
  - 8 phase:大盤(INTL/TW/TECH/ADL) → 籌碼 → 旌旗/乖離 → M1B/M2 → 6 宏觀 → LI 5 細項 → 個股+比較 → ETF 3 細項
- 對齊 macro_registry_patch / macro_fetch_orchestrator DI 風格
- tab_macro.py:**751 → 488 LOC(-263)**

### P2-EX(§8.2.A 例外收齊)
- **5 L1 letter-compliant**(原無條件 import streamlit 軟例外 → 補 try/except + `_NoOpST` fallback):
  etf_fetch / leading_indicators / yf_proxy / data_loader / tw_stock_data_fetcher
  fallback 含 cache_data / cache_resource / **secrets**(P2 新增屬性)三屬性
- **CLAUDE.md §8.2.A 表更新**:
  - EX-CACHE-1:列出 5 處 file:line(已 letter compliant)
  - EX-PASSTHRU-1:原 2 處 → 補登錄 7 處(etf_tab_grp_compare / tab_stock_grp / tab_stock / yield_screener / section_mid)
  - **EX-RENDER-1**(新例外候選):etf_render.py:11 L4 直 import L1 緩解策略
  - 標準寫法 code block 補 `secrets: dict = {}` 屬性

### 累計
- tab_macro.py:**5387 → 488 LOC(-91%)**
- §3.3 反捏造 0 項 / §8.2 高項違憲 0 項 / §8.2.A 例外全 letter compliant
- pytest 2199 pass / 0 fail / 32 deselected (slow)

### Streamlit 实機驗證(未做,留 user)
PR merge 後 fetch warm cache → 走 §十一 News AI render path 即驗 P0-FIX
+ 驗整個 DataRegistry 12 key 完整載入。

---


## 🏁 PR #397 v18.392(merged 2026-06-28)
**tab_macro.py 1012 → 751 LOC(−261,−26%)** — 5 commit。
- D-10 `f257d84`:雙視角 + 雷達準備 64 LOC → section_long_term
- D-11 `3eb2eeb`:旌旗指數 32 LOC → services/jingqi_calc
- D-12 `a13bb25`:outer trio executor 142 LOC → services/macro_trio_orchestrator
- D-13 `fcfe2a5`:市場評估 53 LOC → services/market_assessment_apply
- INDEX sync `03c175e`

累計 tab_macro 5387 → 751 LOC(-86%)。ROI 拐點已過。

---


## 🏁 PR #396 v18.391(merged 2026-06-28)
**tab_macro.py 1076 → 1012 LOC(−64)** — 認錯補做紅綠燈卡。
- D-9 `c1e8483`:紅綠燈卡 66 LOC → section_traffic_light(回傳 placeholder/show_market_data/tl_eff_reg 3-tuple)
- INDEX sync `d3f9a04`

**承認先前 verdict 錯誤**:之前以「placeholder 反模式」擋,但 B-S2 已跨 def 傳 placeholder,argument 自我矛盾。
累計 tab_macro 5387 → 1012 LOC(-81%)。

---


## 🏁 PR #395 v18.390(merged 2026-06-28)
**tab_macro.py 1445 → 1076 LOC(−369,−26%)** — 5 commit dashboard 三件套 + Registry patch。
- D-5 `ac06da7`:五桶 bar 43 LOC → section_summary_bar
- D-6 `89ab752`:戰情概覽 35 LOC → section_overview
- D-7 `98e8005`:今日作戰室 154 LOC → section_warroom
- D-8 `cfd521f`:Registry patch 161 LOC → services/macro_registry_patch
- INDEX sync `e9f2e23`

承認前次 deep-dive verdict 過嚴(誤標 5 段「不可抽」), 本 PR 確實抽 4 段。
全工作累計:tab_macro 5387 → 1076 LOC(−4311,−80%)。
殘餘 1076 LOC 真不可抽:紅綠燈 placeholder lifecycle(streamlit 反模式)。

---


## 🏁 PR #394 v18.389(merged into main 2026-06-28)
**tab_macro.py 5387 → 1445 LOC(−3942,−73%)** — 10 commit 累計成果。

### B-region(UI section 抽出)
- B-4 hotfix `38d7a10`:_m8_* NameError(production bug,section_mid 抽走後 §九 仍 ref)
- B-S8-A `b59b072`:§三 籌碼桶 558 LOC → `macro/section_chips.py`
- B-S8-B `bec36de`:§九 跨桶 AI 220 LOC → `macro/section_cross_ai.py`

### P1+P2(AI 導航優化)
- `6b4e443`:`macro/__init__.py` INDEX docstring(段落→子模組對照表)+
  section_ai_cross→section_cross_ai / section_ai→section_news_ai 並列命名

### P3 D-region(§8.2 分層治理)
- D-3 `28515db`:_job_bias 42 LOC → `macro_snapshot.compute_twii_bias`
- D-2 `221eb5f`:_job_m1b 89 LOC → `macro_snapshot.fetch_m1b_m2_block`(3-Tier)
- D-1 `9a32589`:_job_macro 604 LOC → 5 `fetch_*_block`(VIX/CPI/Fed/PMI/NDC/Export)
- D-4 `370a430`:7-job orchestrator 230 LOC → `services/macro_fetch_orchestrator.fetch_macro_bundle`

### 新增 / 強化模組
- `src/ui/tabs/macro/` 9 個 section_*.py
- `src/data/macro/macro_snapshot.py`:89 → 798 LOC(fetch 邏輯集中)
- `src/services/macro_fetch_orchestrator.py`:270 LOC(NEW)

### SSOT 檢查結論
0 新違憲。預先存在的 inline magic(100億 / -20000 期空 / 50/100 CLI/PMI 等)留待真實 bug 觸發再 SSOT 化(§-1)。

### 殘餘 tab_macro.py(1445 LOC)
- 紅綠燈卡(_tl_placeholder lifecycle,反模式不可抽)
- 戰情概覽 + 作戰室(過小 + closure 多)
- Registry patch(~165 LOC,可抽但 ROI 低)
- session_state writes 收尾(UI 邊界)

---


## ✅ 累計完成
- P0(4 batch / 4 commit):portfolio_exposure SSOT / RSI helper / stock_names L0→L1 / 4 dead fn
- P1(5 batch / 6 commit):3 處 UI yfinance→L1 / macro_snapshot L4→L1 / shared/macro_card 拔 streamlit / 6 dead fn / 6 dead fn cross 3 檔
- P2(2 batch / 2 commit):_prov_log SSOT / 2 inline magic 入 shared
- 跳過(honest stop,ROI 不對等):
  - P1-3 Gemini API 統一(4 caller payload/retry 分歧大)
  - P1-4b cache_layer PKL_DIR env(L0↔L0 hardcode 設計味道但 Python 不 crash)
  - P2-2 命名衝突分化(_safe_float/_num/_secret,改名影響 caller 多)
  - P2-4 pct_change YoY helper(各處 period 不一,強行 helper 破壞契約)
  - P2-5 to_json_rows generic(2 處不同 dataclass,Protocol 加抽 ROI 低)

## 已完成 commits(reverse chrono)

### E-2 (v18.387) — 20-period vol σ 抽 daily_return_rolling_std SSOT
- **檔案**: `shared/calc_helpers.py` + `src/compute/scoring/scoring_engine.py:122,240`
- **拔毒**: 2 處 `close.pct_change().rolling(20).std()` inline → `daily_return_rolling_std(close, window=20)`
- **驗證**: full pytest 2220/0 fail
- **commit**: 待 push

**E-1 honest stop**: `rolling(N).mean()` 15+ 處散落,use case 多樣(close/volume/hi-lo/revenue),且本身就是 pandas 內建單行 SSOT,抽 wrap helper 純 cosmetic 無實際 SSOT 價值。

### A1 (v18.386) — Gemini API 5 caller 統一至 ai_fetcher.py
- **檔案**: `src/services/ai_fetcher.py`(NEW)+ ai_engine.py × 3 caller + financial_health_engine.py × 1 + macro_state_locker.py × 1
- **拔毒**: 5 處散落 Gemini call(retry/payload/timeout/model fallback)→ 統一 `post_gemini(api_key, prompt, *, models, persona, temperature, max_tokens, timeout, retries_per_model, retry_after_parse, inter_model_sleep, extra_generation_config, safety_settings, headers)`
- **新拓展**: `extra_generation_config`(topP/topK)+ `safety_settings`(BLOCK_NONE × 4)涵蓋 ai_engine call 1 的特殊 payload
- **回傳 tuple**: `(text, model_used_or_error)` — caller 自決失敗訊息 / emoji header
- **驗證**: 4 unit test(_build_payload + _extract_text)+ full pytest 2220/0 fail
- **commit**: 待 push

### B-S2 (v18.385) — Section 2 拐點偵測抽至 macro/section_state.py
- **檔案**: `src/ui/tabs/tab_macro.py` + `src/ui/tabs/macro/section_state.py`(NEW)
- **拔毒**: render_tab_macro line 2186-2565(380 LOC)§二 拐點偵測 + 市場狀態卡抽出。tab_macro 3402 → 3025 LOC(-11%)
- **closure 4 個 explicit pass**: `_mkt_info, _mkt_placeholder, _tl_placeholder, cd`(extremely manageable)
- **F-7.1 累計**: 5387 → 3025 LOC(**-43.8%**)
- **test fix**: 3 處 source-string assert 改合集(tab_macro + section_state)
- **驗證**: full pytest 2220/0 fail
- **commit**: 待 push

### A4 (v18.384) — pct_change YoY helper 3 處統一
- **檔案**: `shared/calc_helpers.py`(NEW)+ macro_helpers.py:860 + scoring_engine.py:446 + msl_tw.py:191
- **拔毒**: 3 處 `series.pct_change(N) * 100.0` pattern → 抽 `pct_change_yoy(series, periods=12, multiplier=100.0)`
- **periods param**: 月頻 12(macro_helpers M2 / scoring revenue)+ 日頻 20(msl_tw TWII 20D 跌幅)
- **驗證**: full pytest 2220/0 fail
- **commit**: 待 push

### A2 (v18.383) — cache_layer PKL_DIR env 注入(解 L0↔L0)
- **檔案**: `shared/cache_layer.py` + `src/config/data_config.py`
- **拔毒**: 原 `from src.config import PKL_DIR` 反向 import L0(L0↔L0 hardcode 設計味道)→ 改 `os.environ.get('STK_PKL_DIR', '/tmp/stock_cache')`,兩 file 同源 env
- **caller 介面**: 完全不變(`from shared.cache_layer import ...` / `from src.config import PKL_DIR`)
- **驗證**: smoke + full pytest 2220/0 fail
- **commit**: 待 push

### C-1+C-2+C-3 (v18.382) — 5 個 inline magic 補抽 SSOT
- **檔案**: shared/signal_thresholds.py + scoring_helpers.py:165 + etf_calc.py:901-907 + macro_helpers.py:948-949
- **拔毒**:
  - C-1:RSI 50/40 入 `RSI_STRONG_LOW/RSI_NEUTRAL_WEAK_LOW`(70/30 已在 config.py)
  - C-2:ETF 上下漲日數 60 入 `ETF_UP_DOWN_DAYS_THRESHOLD`
  - C-3:USDCNY 7.2/7.4 補抽 `CHINA_USDCNY_NEUTRAL/WEAK`(P2-3 已抽 7.0)
- **驗證**: full pytest 2220/0 fail
- **commit**: 待 push

### P2-3 (v18.381) — 2 inline magic 入 SSOT
- **檔案**: `shared/signal_thresholds.py` + `src/compute/macro/macro_helpers.py:947` + `src/compute/scoring/scoring_helpers.py:183`
- **拔毒**: 加 `CHINA_USDCNY_STRONG=7.0` + `VOLUME_RATIO_SURGE_HIGH=3.0`,2 處 caller 改 lazy import
- **驗證**: full pytest 2213/0 fail
- **commit**: 待 push

### P2-1 (v18.380) — _prov_log 3 處統一至 provenance.py
- **檔案**: `src/data/core/provenance.py`(NEW)+ etf_fetch.py / daily_data_fetchers.py / nas_server.py 改 thin shim
- **拔毒**: 3 處同名異簽名 _prov_log → 統一 SSOT `prov_log(fn_name, source, result_summary, ticker='')`,3 caller 改 thin wrapper(backward compat)
- **驗證**: full pytest 2213/0 fail
- **commit**: 待 push

### P1-5bcd (v18.379) — 6 個 0-caller dead fn 跨 3 檔刪
- **檔案**:
  - `src/data/macro/leading_indicators.py`:刪 build_dataset(line 762)+ render_table(line 809),共 117 LOC
  - `src/services/daily_checklist.py`:刪 get_export_yoy(line 250)+ get_business_indicator(line 255),含 @st.cache_data decorator
  - `src/data/core/data_registry.py`:刪 get_pingable_endpoints(line 573)+ get_summary_stats(line 602)
- **拔毒**: 全 grep 確認 0 caller(任何形式)
- **驗證**: 3 檔 ast.parse + full pytest 2213/0 fail
- **commit**: 待 push

### P1-5a (v18.378) — financial_health_engine.py 刪 6 個 dead analyze_*_module
- **檔案**: `src/services/financial_health_engine.py`
- **拔毒**: 6 個 0-caller def(analyze_survival/operating/profitability/financial_structure/solvency/advanced_diagnostic_module),全 grep 確認 0 caller(含動態 import / multiprocessing)
- **R2 教訓**: R1 awk 過範圍把 _FINANCIAL_STRUCTURE_PROMPT 等 module-level const 也刪了(test golden 引用),revert + R2 精準 disjoint 4 range 刪 def 留 consts
- **LOC**: 1115 → 962 (-13.7%,刪 ~153 LOC dead)
- **驗證**: ast.parse + full pytest 2213/0 fail
- **commit**: 待 push

### P1-4a (v18.377) — shared/macro_card.py streamlit 移除 + 刪 6 dead fn
- **檔案**: `shared/macro_card.py`
- **拔毒**: L0 含 `import streamlit as st` 違憲 + 6 個 0-caller dead fn(render_macro_card / render_macro_card_grid / build_cards_from_indicators / _esc / render_edu_markdown / _z_color)
- **保留**: calc_z_score / make_sparkline(tab_edu.py:158 唯一 caller 真用)
- **LOC**: ~290 → 81(-72%)
- **驗證**: smoke(z + sparkline OK + dir 確認 dead 全刪)+ full pytest 2213/0 fail
- **commit**: 待 push

### P1-1c (v18.376) — tab_macro yfinance ^TWII 2y 抽 L1
- **檔案**: `src/ui/tabs/tab_macro.py` + `src/data/macro/macro_snapshot.py`
- **拔毒**: tab_macro.py:973 line `import yfinance as _yf_bias; yf.download('^TWII', period='2y')` 違憲 → 抽 `fetch_twii_2y_for_ma240()` 至 L1 macro_snapshot.py(同檔有 vix block 模式),tab_macro 改 lazy import + thin call
- **驗證**: ast.parse + full pytest 2213/0 fail
- **commit**: 待 push

### P1-1b (v18.375) — yield_screener fetch_dividend_history 抽 L1
- **檔案**: `src/ui/tabs/yield_screener.py` + `src/data/stock/dividend_fetcher.py`(NEW)
- **拔毒**: line 70-125 fetch_dividend_history 整段含 yfinance + NAS proxy 注入 + 配息聚合 → 整檔搬至 L1。yield_screener 留 thin re-export(`from src.data.stock.dividend_fetcher import fetch_annual_dividends as fetch_dividend_history`)
- **EX-CACHE-1 例外**: L1 fetcher 用 @st.cache_data,允許(只 cache 不用 session_state/UI)
- **驗證**: full pytest 2213/0 fail(1 test source 對齊改合集)
- **commit**: 待 push

### P1-1a (v18.374) — tab_stock_picker yfinance 直呼抽 L1
- **檔案**: `src/ui/tabs/tab_stock_picker.py` + `src/data/stock/picker_fetcher.py`(NEW)
- **拔毒**: line 283 L5 UI 內 `yf.Ticker(...).history(...)` HTTP I/O 違憲 → 抽 `fetch_stock_history_1y(ticker)` 至 L1。_check_one_stock 內改 call helper(yf param 保留 backward compat,內部 dead 不再用)
- **__init__ 同步**: src/data/stock/__init__.py 加 picker_fetcher 入 _SUBMODULES
- **驗證**: full pytest 2213/0 fail
- **commit**: 待 push

### P1-2 (v18.373) — macro_snapshot 整檔搬至 L1
- **檔案**: `src/ui/render/macro_snapshot.py` → `src/data/macro/macro_snapshot.py`
- **拔毒**: L4 render 含 yfinance.download HTTP I/O,檔頭自標 "L1 fetchers" 卻放 render/。git mv 整檔搬位 + 4 caller 改 import path
- **caller 改**: src/ui/tabs/tab_macro.py:1051 + tests/test_pr_q5c_singles.py:28,67 + tests/test_macro_snapshot.py:11,56
- **__init__ 同步**: src/ui/render/__init__.py 移除,src/data/macro/__init__.py 加入
- **驗證**: full pytest 2213/0 fail
- **commit**: 待 push

### P0-4 (v18.372) — app.py 4 個 dead fn 刪除
- **檔案**: `app.py`
- **拔毒**: 嚴格 grep 確認 0 caller(任何形式皆無)後刪 4 個 public/private fn:
  - `calc_jingqi` (line 1024, 51 LOC)
  - `render_market_overview` (line 1075, 32 LOC)
  - `render_top_rankings` (line 1107, 23 LOC)
  - `_run_llm_analysis` (line 1559, 78 LOC)
  - 共刪 184 LOC,app.py 1722→1538
- **驗證**: ast.parse OK + full pytest 2213/0 fail
- **commit**: 待 push

### P0-1 (v18.371) — stock_names.py I/O 抽 L1 fetcher
- **檔案**: `src/config/stock_names.py` + `src/data/core/stock_names_fetcher.py`(NEW)
- **拔毒**: L0 config 含 requests/yfinance HTTP I/O(嚴重違憲)→ I/O + cache 邏輯抽 L1 fetcher。stock_names.py 留 _STATIC_NAMES const + get_stock_name/refresh_name_cache thin shim(lazy import L1)
- **驗證**: smoke(static lookup 台積電 ✓ + unknown fallback ✓);full pytest 2213/0 fail
- **commit**: 待 push

### P0-3 (v18.370,commit a08786b) — RSI 計算抽 compute_rsi SSOT
- **檔案**: `src/compute/scoring/scoring_engine.py`
- **拔毒**: line 104-106 + 239-241 同檔重複 4 行 RSI 邏輯 → 抽 `compute_rsi(close, period=14)` 純函式,2 處 caller 改 1 行 call
- **驗證**: 全 pytest 2213/0 fail

### P0-2 (v18.369,commit 9b2f8f0) — portfolio_exposure SSOT 收攏
- **檔案**: `src/services/market_strategy.py`
- **拔毒**: 刪同名異實作 def(line 148-161),改 `from src.compute.risk.risk_control import portfolio_exposure`
- **SSOT**: L2 `risk_control.portfolio_exposure(regime)` 為唯一定義
- **驗證**: 全 pytest 2213/0 fail

## 待動 batch
- P0-1 stock_names.py I/O 抽 L1 fetcher
- P0-4 dead fn 驗證 + 刪(8 個候選)
- P1-1 ~ P1-5 結構性收乾
- P2-1 ~ P2-5 漸進命名 / SSOT 補
