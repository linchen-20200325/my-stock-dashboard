# STATE.md — 台股 AI 戰情室 (Stock Dashboard)

> 極簡狀態檔。歷史 PR 紀錄見 git log；技術細節見 `ARCHITECTURE.md` / `DATASTATION.md` / `STRATEGY_MANUAL.md`。

## 專案定位
- **產品**：台股 / ETF 多 Tab 投資儀表板（市場 / 個股 / 組合 / 總經 / ETF）
- **技術棧**：Streamlit + pandas + Plotly + altair（<5）+ FinMind + yfinance + Gemini AI
- **基建**：NAS Squid Proxy + FastAPI 中繼站（個股新聞）
- **目前版本**：v18.173_DualVerdictSynth（A+B 雙向鏡像計畫 Step 4/4 收官 — 鏡像 fund v19.21 `synthesize_dual_verdict` 到 stock UI，把 v18.171 長期 regime 與 v18.172 風險雷達 level 合議成單一行動建議：① **tab_macro.py 3 處改動**：(a) hoist `_lt = None` 到 v18.171 dual-view try 外，供下方合議讀取；(b) `_render_global_risk_radar` 加 `slow_verdict: dict | None` 參數，10 燈渲染完之後 call `risk_radar.synthesize_dual_verdict(slow_level/score/color/icon/action, radar_level=_rs["level"])` 渲染「🤝 雙速合議」banner（icon + level 大字 + action 行動建議 + 規則 caption）；(c) call site 把 `_lt` 映射成 slow_verdict dict，`_lt["score"] × 5` 校準到 fund synth 期望的 ~[-10,+10] 範圍（_cls_lt 原 score 範圍 ~[-2,+2]，乘 5 保留閾值判斷語意一致性）② **決策表**：雷達 None/平靜 → adopt_slow（採用慢總經）/ 雷達警戒 + 慢樂觀 → downgrade_1 警戒觀察 / 雷達警戒 + 慢中性/悲觀 → downgrade_1 中性觀察 / 雷達警報 + 慢樂觀 (score≥+5) → downgrade_2 雙速分歧降槓桿（50-60% 倉位）/ 雷達警報 + 慢中性 → downgrade_2 偏空 25-30% 現金 / 雷達警報 + 慢悲觀 → downgrade_2 全面防守 35%+ / 雷達極端警報 → override_defense 立即減倉防守（慢總經暫不採信）③ synth 例外 graceful：print 不爆 + 不渲染 banner ④ **tests/test_dual_verdict_ui.py 9 case**：slow_verdict None / 雷達平靜 + bull adopt_slow / 雷達警報 + bull downgrade_2 / 雷達極端 override_defense / 雷達警戒 + bull 警戒觀察 / 雷達警戒 + bear 中性觀察 / 缺欄位 fallback / synth 例外 graceful / AppTest 保護門也覆蓋 slow_verdict 路徑；72/72 passed (63 risk_radar + 9 dual_verdict_ui) 0.88s + tests/ 1108 passed 零回歸（v18.172 1099 → +9 新）；ruff 三檔全綠 + py_compile 通過；test_app_step4 2 failed pre-existing 與本 PR 無關。**🎉 A+B 雙向鏡像計畫收官** — Fund v19.23/24/25 + Stock v18.172/173 共 4 PR 完成；PR #180 squash @ 7c9a409）
- **前一版**：v18.172_GlobalRiskRadar（A+B 雙向鏡像計畫 Step 3/4 — 鏡像 fund v19.20 services/risk_radar.py 到 stock 端，補拐點偵測中心 5 大訊號全是「月～季級慢速 macro inflection」對 1-day 急殺事件結構性盲眼：① 新增 **risk_radar.py 532 行**（detect_risk_radar / summarize_radar / synthesize_dual_verdict 三公開函式）；10 燈清單：VIX 級距（≥30 或 +20% → 🔴）/ VIX/VIX3M 期限結構（≥1.10 → 🔴）/ HY OAS 1-day Δ（≥+30bp → 🔴）/ 10Y 1-day Δ（≥+10bp → 🔴）/ MOVE 級距（≥130 → 🔴）/ SPX vs 50/200 DMA / SOX 單日跌幅（≤-3% → 🔴）/ 防禦 (XLP+XLU+XLV) vs 攻擊 (XLK+XLY+XLF) 30D 動能差（≥+4pp → 🔴）/ CBOE Put/Call（≥1.20 → 🔴）/ Nikkei+HSI 亞洲夜盤（≤-2.5% → 🔴）；每燈獨立 try/except 單一資料源掛點不拖垮其餘 9 燈；summarize_radar 規則：red≥4 極端警報 / red≥2 警報 / red+yellow≥4 警戒 / 其餘平靜 ② **tab_macro.py +99 行**：`_render_global_risk_radar(fred_api_key)` 模組層 helper（10 燈 5×2 grid + 整體 level banner + 細節 expander）+ call site 插入紅綠燈卡與 v18.171 長短期雙視角面板之後、blue box「今日市場總覽」之前 ③ **AppTest 保護門**：fred_api_key < 30 字元 → 跳過渲染（測試環境 key 通常 14 字元，真實 32 字元，避開 4×~15s 序列 HTTP 撞 240s budget）④ 完全 verbatim 鏡像 fund v19.20，僅換 import `repositories.macro_repository` → `macro_core`（fetch_fred/fetch_yf_close 簽名相容）；透過既有 NAS proxy 抓 Yahoo + FRED（BAMLH0A0HYM2/DGS10）⑤ synthesize_dual_verdict 預先 port（Step 4/4 會接 UI）⑥ **tests/test_risk_radar.py 63 case**：10 燈每燈 calm/yellow/red + summarize 7 case + dual_verdict 10 case + 整合 detect_risk_radar 5 case；63/63 passed 0.26s + tests/ 1099 passed 零回歸（v18.171 1036 → +63 新）；ruff 三檔全綠；test_app_step4 2 failed 確認 pre-existing 與本 PR 無關。PR #179 squash @ 06292a3）
- **前二版**：v18.171_DualViewMacroTopOfPanel（純 UI 位置調整 — 將「🔭 長短期雙視角總經判讀」面板從 tab_macro.py 拐點 expander 之後（原 L2362, 8-space indent）上移到紅綠燈卡填完後、「今日市場總覽」blue box 之前（L223, 4-space indent），緊接「綜合健康度燈號」之下，並於 expander 結尾外掛 `st.divider()` 與下方 blue box 視覺隔開。功能 / 演算法 / 介面行為零變動：純函式 `classify_long_term_regime / classify_short_term_regime` 不動；`session_state.get('macro_info')` 讀取時機向前移但 Streamlit rerun 後仍能讀到正確值；`_lt / _st_r / _mi_d` 均為 try-block 區域變數無耦合；try/except + print 包覆確保渲染失敗不阻斷後續 tab。`python -m py_compile tab_macro.py` ✅；`pytest tests/test_macro_helpers.py` → 69 passed ✅）
- **前二版**：v18.170_LongShortMacroDualView（總經 tab 加「長期 vs 短期」雙視角總經面板 — 鏡像 fund services/macro_service.py 的 `identify_regime()` 長期景氣象限 + risk_radar 短期動量雙軌設計，但對齊台股財報季（Q1/Q2/Q3/Q4 5/8/11/3 月）改用「1Q 視角」短期分類：① `macro_helpers.classify_long_term_regime(cpi_yoy, fed_rate, fed_prev_rate, ndc_score, pmi, mk_signal)` 純函式 — 12M 視角加權打分（CPI 25% / Fed 方向 20% / NDC 景氣燈號 20% / 台 PMI 20% / MK 拐點 15%），每項 [-2, +2] 加權合分，>=+1 🟢 成長期 / >=0 🔵 復甦期 / >=-1 🟡 過熱期 / <-1 🔴 衰退期，含 suggest_pct 持股建議 ② `macro_helpers.classify_short_term_regime(export_yoy, pmi, vix_current, fi_streak_days, cpi_yoy, cpi_prev_yoy)` 純函式 — 1Q 視角加權打分（出口 YoY 25% / PMI 25% / VIX 15% / 外資連續 20% / CPI 月降 15%），>=+0.8 ⚡ 偏多 / >=-0.3 ⚖️ 中性 / <-0.3 ⚠️ 偏空，含 action 短線建議 ③ MK 訊號邏輯保護：只當至少一個主指標存在時才計入 MK，避免 MK 獨自驅動 regime；資料全空 → ⚪ 資料不足 ④ tab_macro.py L2360 拐點 expander 結束後新增「🔭 長短期雙視角總經判讀」並排 2 卡（🏔️ 長期 12M ｜ ⚡ 短期 1Q），每卡 regime 大字 + 綜合分數 + suggest/action + components 細項 caption 拆解每指標分數，總共 ~100 行 UI ⑤ 教學保護 expander「🔰 為什麼要分長期 / 短期？」含雙視角定義 + 4×3 決策矩陣 markdown 表（長期🟢🔵🟡🔴 × 短期⚡⚖️⚠️ = 12 組行動建議）+ 兩者矛盾時處理原則（長期為主、短期為輔）⑥ 純複用既有 fetcher（CPI/Fed/NDC/PMI/VIX/Export 6 個 + session_state 外資連續日數），零新 fetcher、零動 pool、零動註冊表 ⑦ tests/test_macro_helpers.py +22 case（長期 11 個：4 regime 各一情境 + 資料不足 + MK 獨自不算 + 部分資料 + components 結構 + 字串 graceful + 分數範圍 + 強 vs 弱 MK 加成；短期 11 個：⚡⚖️⚠️ 3 regime + 資料不足 + 出口單項 + 外資正反 + VIX 邊界 + components 五項 + 字串 graceful + CPI 月降影響 + action 訊息）；tests/ 1036 passed 零回歸；ruff 三檔全綠；無新增檔、無新增 fetcher，純加 UI 面板 + 2 個 helper + 22 tests）
- **前二版**：v18.169_MkGoldenInflection（總經 tab 加 MK 黃金拐點 + 面板簡化 — 鏡像 fund services/macro_service.py::_detect_inflection 核心訊號「⭐ MK 黃金拐點 = CPI YoY × Fed Funds Rate 雙頂回落」：① 新增 `_fetch_fed_funds()`（FRED FEDFUNDS 月均利率，2 層備援 fredgraph.csv → FRED-API 帶 key 加速；prev/current 月度比較）併入既有 5 fetcher 並行池（max_workers 5→6）② `_fetch_cpi` 三路徑全部補 `prev_yoy` 欄位（fredgraph / FRED-API / BLS）③ `macro_helpers.detect_mk_golden_inflection(cpi_yoy, cpi_prev_yoy, fed_rate, fed_prev_rate)` 純函式，雙噪聲門檻 ±0.05ppt 防雜訊：CPI 月降 ≥0.2 + Fed 持平/降 → ⭐ 強訊號（多頭最佳買點）；CPI 月降 [0.05,0.2) + Fed 持平/降 → ✅ 弱訊號觀察中；任一上升 → None ④ 拐點面板 expander 標題「五大面向」→「六大面向 + MK 黃金拐點」L2026-2350 新增第 7 try/except block 呼叫 helper、註冊表（L1715 + L1984）+ AI context（L4284, L4318）同步補 fed_funds / prev_yoy 4 個量化欄位給 Gemini ⑤ **面板去重簡化**：Section 七 KPI 3 卡（M1B-M2 / 年線 240 / 月線 20）→ 2 卡（M1B-M2 / 年線+月線統合卡，月線併入副標「月線20MA: +X% (過熱/機會/正常)」）+ 加 caption「📖 完整乖離訊號 → 詳見頂部拐點面板第 2 面向」⑥ Section 八 Row2 layout [1,2] → [1,1,2]：CPI 旁加 Fed Funds Rate KPI（紅黃綠色碼門檻 5/3/0%，副標 trendline ↓→↑ + 上月對照），原 CPI caption 教學「Fed 目標值 = 2%」原樣保留 + Fed KPI 加新 caption「💡 與 CPI 配對：兩者同步月降 → ⭐ MK 黃金拐點」⑦ 教學保護清單全保留（L234 紅綠燈教學 / L2237 拐點 expander / L2313 熱錢三角 / L3799 三環攻擊 / L4120 AI 總裁決）⑧ tests/test_macro_helpers.py +12 新 case（強訊號 CPI+Fed 雙降 / 強訊號 CPI 降 Fed 持平 / 弱訊號 / CPI 升無訊號 / Fed 升無訊號 / CPI 持平噪聲區 / 缺資料 / 字串 graceful / detail 含數值 / 0.20 ppt 邊界強/弱 / 0.06 ppt 剛過噪聲 / Fed 微升 0.03 在噪聲區仍強訊號）；tests/ 1014 passed 零回歸；ruff 三檔全綠；後續可選 Wave 2 加 HY/Sahm/CFNAI 三信號補齊 fund _detect_inflection 全套）
- **前一版**：v18.168_StockFactorPool7（stock 多因子池 4 → 7 — 補強「量價結構 + 融資加速度 + 已實現波動率」三個 parquet 衍生因子，零新基礎設施／零新 cron／全用既有 `data_cache/`：① TWSE_VOL_RATIO（volume / SMA60 - 1 → z-score，above；異常爆量警戒）② MARGIN_GROWTH_5D（margin_balance.diff(5) 億元，above；散戶 5 日加碼加速）③ TWII_REALIZED_VOL_20D（returns.std × √252 × 100，above；本地 VIX 替代品）；3 個新 fetcher + TW_SIGNAL_FETCHERS registry + FactorSpec 全 source="local"；fund v18.296 已先擴成 13 因子，stock 跟進；69 unit cases passed（新 9 個）+ 1002 全測試 passed 零回歸；ruff 全綠；SHORT_BALANCE / USD_TWD / MOVE / NFCI / 銅金比 / PCR / 三大法人 / ADL 留 Wave 2-3）
- **前一版**：v18.167_BacktestOptimizationTab（新增 top-level Tab「🧪 回測找參數」排在「💰 ETF質借模擬」之後 — 完整版多因子權重最佳化 workflow：📖 操作說明 expander（含核心數學公式 + 6 slider 解釋）+ 1️⃣ TWII 回撤門檻 + 抓資料按鈕 → 2️⃣ 因子 multiselect + Plateau 目標 radio (F1/Sharpe) + 6 顆 slider（grid 步長 / 鄰域半徑 / λ / train / test / 警戒線）+ 3️⃣ 高原最佳權重 metric 卡 + CSV 匯出 + 4️⃣ plateau 2D heatmap / 3D surface toggle + 5️⃣ walk-forward 各折表 + OOS F1/Sharpe + CSV；引擎複用 v18.165 multi_factor_optimization.py 零重寫；macro validation 內 expander 並存「快速版」）
- **前一版**：v18.165_MultiFactorPlateauWalkForward（Phase 3 加「🔬 多因子權重最佳化」expander — 綜合分數 S_t = Σ w_i × normalize(I_{i,t−1})（lag=1 防未來引用），simplex 權重 grid sweep 算 F1+Sharpe，**plateau 評分 = 鄰域 mean − λ × std**（不取單一最高 F1）；walk-forward 滾動 train/test 串 OOS 權益曲線；plotly 2D heatmap + 3D surface toggle；4 因子池（FOREIGN_SELL_5D / MARGIN_BALANCE / M1B_M2_DIFF / TWII_DROP_20D 全 source="local"）；FactorSpec source literal 擴 yahoo|fred|local 兼容台股本地訊號；鏡像 fund v18.285；28 case 驗收 + ruff 全綠）
- **前一版**：v18.164_MT5StyleAutoCalibration（Phase 3 加「🎯 MT5-style 自動校準」expander — walk-forward 4 折 grid sweep × 3 重 anti-overfit gate（折間票選 + drift>30% 回退 + cap 守門）；session-only override 機制；對齊 fund v18.283；963 全測試 passed）
- **前一版**：v18.163_SignalPrecisionAnalysis（Phase 3 加「📐 訊號精確率分析」forward-looking 區塊 — 解召回率單面向：遍歷歷史 crossings 算 TP/FP/精確率/誤報率/avg lead time；對齊 fund v18.282；953 全測試 passed）
- **前一版**：v18.162_EtfMarginSimulator（ETF 質借倒金字塔加碼模擬器：4 風格 preset × 3 階梯觸發 + HWM 回撤 + 擔保維持率 140/130% 爆倉檢測；新 Tab「💰 ETF質借模擬」+ 43 case 全綠 + 全測試 948 passed）
- **前一版**：v18.161_EdgeDetectionUiSurfacing（Phase 3 標題加「v2 轉折偵測」+ 提前 → 轉折提前）
- **前二版**：v18.160_EdgeDetectionFix（永遠在警戒 = 假預警修復 + bootstrap 5 → 20 年）
- **前三版**：v18.159_MacroSignalLookbackTW（台股本地 4 訊號 × TWII crisis 命中率 — 對齊 fund Phase 3）
  - **User 需求**：截圖回報「基金有這測試總經的預測力（VIX / HY / T10Y2Y / UNRATE × 5 場 SPX crisis 命中率），台股沒有看到」+ 選「台股本地 4 訊號」方案
  - **4 個本地訊號**（讀 `data_cache/` 既有 4 表，**無需額外抓數據**）：
    | 訊號 | 資料源 | 閾值 | 解讀 |
    |---|---|---|---|
    | 外資 5 日累積買賣超 | finmind_inst.foreign_buy | sum5 ≤ -500 億 | 連 5 日合計大賣 |
    | 融資餘額 | finmind_margin.margin_balance | ≥ 3400 億 | 散戶槓桿過熱 |
    | M1B/M2 缺口惡化 | finmind_m1m2.m1b_m2_gap.diff | ≤ -2 pts/月 | 資金流出股市 |
    | TWII 20 日跌幅 | twii_ohlcv.close.pct_change | ≤ -5% | 加速下跌確認 |
  - **macro_signal_lookback_tw.py**（新檔 ~310 行純函式，**公式鏡像 fund services/macro_signal_lookback.py**）：
    - `TwSignalSpec` frozen dataclass + `TwSignalLookback` mutable dataclass
    - 4 個 series fetcher：`fetch_foreign_sell_5d_series` / `fetch_margin_balance_series` / `fetch_m1b_m2_diff_series` / `fetch_twii_drop_20d_series`（各自 `_load_parquet_safe` 缺檔 graceful）
    - `TW_SIGNAL_FETCHERS` registry dict + `fetch_all_tw_signal_series` 批次
    - `evaluate_signal_at_event` — 點觀測（peak - offset 日 ≤ target 最近一筆）+ 峰前最早警戒搜尋（max_lookback_days 內）
    - `lookback_all_signals_tw` 批次
    - `compute_signal_hit_rate` — 命中率 = n_hit / n_covered、平均提前天數
  - **tab_macro_validation.py**（149 → 252 行）：
    - 加 `_PHASE1_CACHE_KEY` / `_PHASE3_CACHE_KEY` session_state cache，**修 v18.157 既有 button rerun 吞 events bug**（鏡像 fund v18.261 PR #117 fix）
    - 上方「跑歷史驗證」按鈕觸發 Phase 1 events 計算 → 存 cache；門檻變動失效 Phase 3 cache
    - 新 `_render_phase3_signal_section(events, cache_dir)`：2 sliders（offset 30-180 / 上限 90-540 日）+ 跑按鈕 + 命中率總覽表（訊號 / 閾值 / 涵蓋事件 / 命中事件 / 命中率 / 平均提前天數 / 解讀）+ 逐事件 × 逐訊號明細表（✅ 提前 Xd / ❌ (值) / —）
  - **tests/test_macro_signal_lookback_tw.py**（新檔 21 case 全綠）：DEFAULT_TW_SIGNALS 完整性 + Registry 對齊 / _is_warning above/below 邊界（閾值包含） / 4 fetcher 缺檔 graceful + 正常 schema 計算（rolling sum / 億元轉換 / monthly diff / pct_change(20)） / fetch_all 批次缺檔 / evaluate value_at_lookback / triggered / first_warning earliest / below direction / lookback_all_signals_tw dict 結構 / hit_rate empty / mixed coverage 公式
  - **回歸**：tests/ **901 passed**（v18.157 880 + 21 新）零回歸
  - **下一步**：使用者進 Tab macro 看 section 十 — 上方按 「跑歷史驗證」→ 下方看 Phase 3「總經訊號預測力驗證」表
- **前一版**：v18.158_LeadingTableRedGreen（先行指標表配色換台股慣例 — 紅漲綠跌 + ▲▼ icon）
  - **User 需求**：截圖回報「台股這顏色我分辨不出來」— `render_leading_table` 原配色「正藍 #58a6ff / 負紅 #f85149」在 OLED 螢幕藍色偏紫，與紅幾乎同色相。User 選「台股紅綠（紅漲綠跌）+ 三角 icon」方案
  - **leading_indicators.py:render_leading_table** 改 fmt() + sty() 兩 fn（line 1262-1304）：
    - **fmt** 加 ▲/▼ icon prefix（BRACKET / SPOT / 韭菜指數 三類數值）。BRACKET 負數保留會計慣例 `(43,596)` 加 `▼ ` 前綴；正數 `▲ ` 前綴
    - **sty 色彩語意**：BRACKET / SPOT / 韭菜指數 / 未平倉口數 — 正紅 `#f85149` 負綠 `#3fb950`（台股紅漲綠跌）
    - **PCR 反向語意**：< 80 看多紅、> 120 看空綠（原本相反；台股紅漲綠跌邏輯）
    - **融資餘額不變**（紅 = 過熱警示 / 綠 = 寬鬆），這是水位指標非漲跌
    - **韭菜指數維持「直接視角」**（散戶淨多正數 = 紅；反向解讀由 user 自行）；line 793 `render_table` 是 legacy（已用紅綠 + 反向韭菜邏輯）dead code 未動
  - **tests/test_leading_indicators.py**：5 個 PCR case 更新 — `test_pcr_below_80_blue` 改 `test_pcr_below_80_red`、`test_pcr_above_120_red` 改 `test_pcr_above_120_green`，斷言色從 `#58a6ff` 改 `#f85149`、`#f85149` 改 `#3fb950`
  - **回歸**：tests/test_leading_indicators.py **47 passed** 零回歸
  - **下一步**：refresh Tab1 macro 看新配色，正負分辨度應大幅提升
- **前一版**：data_cache 4/4 全綠 ✅ + 標題但無值清單三件
  - **M1B/M2 終於進去**：經 9 輪 iteration 確認 CBC PXWeb API 真實結構 `sdmx["data"]["dataSets"]`（list of `[YYYYMmm, value, ...]`），寫順鏈 parser；bootstrap 抓 5 年得 58 個月度資料 + YoY gap 欄位
  - **CBC API breaking change 記事**：舊 `ms1.json` 全 404 / 回 HTML、SDMX EF15M01 合表 API 改回 metadata + dataSets；新 parser 用 EF19M01（M1B）+ EF21M01（M2）分表抓再 merge on period_raw
  - **BFI82U 教學卡**：tab_edu 加 handler 抽外資 net 顯示為億；BWIBBU_d 仍標散點需個股 Tab
  - **ETF N/A 強化**：內扣費用率 / Beta / AUM / 折溢價率 / 追蹤誤差 5 個 metric 加 help= hover
- **前一版**：v18.157_PureTwiiDrawdown（C 案降級 — 砍 NDC + 領先指標，Section 十 改純 TWII drawdown 事件表）
  - **背景**：v18.151-156 連 6 輪 PR 嘗試解 NDC 卡關（FinMind enum 改名 → 付費牆 → NDC SPA HTML → data.gov.tw search 無對應 dataset → NAS FastAPI 8765 端 user 未架設）。User 拍板「股票跟基金一樣只走 Squid Proxy 3128」— fund 從來沒用 NAS_BASE_URL FastAPI，只用 PROXY_URL Squid，stock 應該對等
  - **update_macro_history.py**（819 → 419 行，砍 395 行）：移除 `_NDC_*_URL_CANDIDATES` / `_NDC_VALUE_KEYS` / `_NDC_DATE_KEYS` / `_fetch_via_nas_relay` / `_try_ndc_via_relay` / `_DGTW_*` constants / `_fetch_dgtw_search_dataset_ids` / `_fetch_dgtw_dataset_csv_full` / `_fetch_dgtw_indicator` / `fetch_ndc_signal` / `fetch_ndc_leading_index`；DATASETS 從 6 個剩 4（twii / inst / margin / m1m2）；FETCHERS dict 同步
  - **macro_validation_tw.py**（344 → 157 行，砍 187 行）：移除 `load_ndc_signal_from_parquet` / `load_leading_index_from_parquet` / `NdcVerifyResult` / `verify_ndc_signal_vs_crises` / `LeadingIndexVerifyResult` / `compute_smoothed_change_pct` / `verify_leading_index_vs_crises` / `compute_hit_rate`；只保留 `load_twii_close_from_parquet` + `TwiiCrisisEvent` + `detect_twii_crisis_events`
  - **tab_macro_validation.py**（258 → 131 行，砍 127 行）：rewrite UI — 純 TWII drawdown 事件表（1 slider 回撤門檻 + TWII + crisis 紅區走勢圖 + 事件清單表 + CSV 下載）；移除 NDC/領先指標命中表 + 命中率卡 + 3 slider 變 1 slider
  - **tests/test_update_macro_history.py**（479 → 112 行）：砍 _FakeResp + dgtw 11 case + ndc 6 case 共 17 個 NDC/dgtw/relay 測試
  - **tests/test_macro_validation_tw.py**（346 → 154 行）：砍 NDC/leading/hit_rate/smoothed_change 共 17 個測試；test_load_handles_corrupt_parquet 改用 twii 檔
  - **回歸**：tests/ **880 passed**（v18.156 918 - 38 NDC/dgtw/relay 測試 = 880）零功能回歸
  - **未來還原路徑**：若 user 將來 SSH 進 NAS 跑 FastAPI 8765 + 設好 `NAS_BASE_URL` secret → revert PR 即恢復；目前選擇與 fund 對等的最簡架構
- **前一版**：v18.156_MacroSectionSwap（macro tab section 十 ↔ 十一 交換 — 歷史驗證上、AI 總裁決下）
  - **User 需求**：「十一、總經訊號歷史驗證 往上移到十 交換」— UI 排序調整
  - **tab_macro_validation.py**：內部 markdown header「十一、」改「十、」（兩處：docstring + render markdown）
  - **tab_macro.py**：插入新 section 十（render_history_validation_section call）在原 section 十之前；原 AI 總裁決的 section_header 從 '十' 改 '十一'；刪除文件末尾的重複 validation block（避免渲染兩次）
  - **tests/test_macro_validation_tw.py**：`test_ui_section_after_section_ten` rename + 邏輯改為「歷史驗證（十）必須在 AI 總裁決（十一）之前」
  - **回歸**：tests/ **918 passed** 零回歸
- **前一版**：v18.155_NdcRelayWithAjaxHeader（user 提醒 NAS 中繼站 → 強制走 relay 帶 AJAX header 觸發 SPA 回 JSON）
  - **背景**：v18.152/153 NDC URL 全敗的根因錯怪：不是 NDC URL pattern 錯，而是**透過 Squid Proxy 抓沒帶 `X-Requested-With: XMLHttpRequest`**。`nas_server.py:35` 的 `_HDR` 已配 AJAX header，AngularJS SPA 偵測到 XHR 應該會切回 JSON 模式（典型雙模式 SPA 行為）— 但 `fetch_url` 內 Squid 是 transparent forwarder 不會自動加這 header
  - **解法**：新增 `_fetch_via_nas_relay(url, label)` 直接呼叫 `proxy_helper.nas_relay_fetch()` 跳過 Squid 優先序，header 由 NAS 中繼站 FastAPI 自動填（X-Requested-With + Accept: application/json）
  - **update_macro_history.py**：
    - 重啟 `_NDC_SIGNAL_URL_CANDIDATES` / `_NDC_LEADING_URL_CANDIDATES`（v18.154 砍掉的）+ `_NDC_VALUE_KEYS` / `_NDC_DATE_KEYS`
    - 新增 `_fetch_via_nas_relay(url, label)` — 強制走 NAS 中繼站；JSON 解析 + verbose log（CT + body 前 300 char）
    - 新增 `_try_ndc_via_relay(candidates, label)` — 逐一試 candidate；第一成功就 break
    - `fetch_ndc_signal` / `fetch_ndc_leading_index` 三路徑彙整：① relay+AJAX header ② data.gov.tw search ③ data.gov.tw ID probe（保留 v18.154 dgtw 作兜底）
  - **tests/test_update_macro_history.py**：新增 7 case：candidate URL constants 完整性 / `_fetch_via_nas_relay` 成功 / NAS 未設定 graceful / HTML 回應 graceful / `_try_ndc_via_relay` 短路 / `fetch_ndc_signal` relay 成功不走 dgtw / relay 失敗 fallthrough 到 dgtw；既有「全失敗 graceful」測試補 monkeypatch relay
  - **回歸**：tests/ **918 passed**（911 + 7 net）零回歸
  - **下一步**：merge 後 bootstrap 一次 → log 會印 `[ndc-relay/...]` 系列訊息，若 SPA 確實對 AJAX header 回 JSON → ✅；若 relay 也回 HTML → 走 dgtw 兜底；若 dgtw 也敗 → §5 警鈴啟動 C 案
- **前一版**：v18.154_DgtwSearchFallback（最後一輪 — 棄 NDC SPA → data.gov.tw search API + dataset CSV probe）
  - **背景**：v18.153 診斷確認 `index.ndc.gov.tw/app/data/indicator/*` **全 5 個 candidate URL 回相同 AngularJS SPA index HTML**（`<html ng-app="NDCapp">` + `csrf-token` meta）— SPA client-side routing fallback 結構性 dead，繼續加 candidate slug 沒用
  - **解法**：完全砍 NDC OpenAPI，改用 **data.gov.tw 政府資料開放平臺**（鏡像 `macro_core._pmi_src_dgtw` 已驗證 dataset/6100 PMI 在生產 work 的模式）
  - **update_macro_history.py**：
    - 移除 dead code：`_NDC_SIGNAL_URL_CANDIDATES` / `_NDC_LEADING_URL_CANDIDATES` / `_NDC_VALUE_KEYS` / `_NDC_DATE_KEYS` / `_fetch_ndc_indicator_full`（v18.152/153 殘骸）
    - 新增 `_DGTW_*` constants：3 個 signal keywords + 3 個 leading keywords + 16 個 candidate IDs（6097-6109 + 6052-6056；國發會系列 ID 鄰近 6100 PMI）+ 6 個 signal value 欄關鍵字 + 3 個 leading value 欄關鍵字 + 9 個 date 欄關鍵字
    - 新增 `_fetch_dgtw_search_dataset_ids(keyword, label)` — 打 3 個 search API 變體（v2/v1/front）+ 多 result shape parser；印 candidate IDs + titles
    - 新增 `_fetch_dgtw_dataset_csv_full(ds_id, value_keywords, label)` — metadata API 取 resources → 找 CSV → 下載 → 全 row 解析 [date, value]（不限末筆，bootstrap 用），完全鏡像 `_pmi_src_dgtw` 但回完整 DataFrame
    - 新增 `_fetch_dgtw_indicator(keywords, value_keywords, candidate_ids, label)` — 二路徑彙整：① search API 找 ID ② 直接 probe 鄰近 ID 範圍
    - `fetch_ndc_signal` / `fetch_ndc_leading_index` 內部改呼叫 `_fetch_dgtw_indicator`
  - **tests/test_update_macro_history.py**：替換 7 個 NDC OpenAPI 測試 → 11 個 dgtw 測試（含擴強 `_FakeResp` 支援 CSV bytes + Content-Type）：constants 完整性 / search 解析 results / search 0 results / search HTML fallback / dataset CSV parse 完整 / dataset 無 CSV resource / CSV 無 value 欄 / search→dataset 直通成功 / search fail fallback probe / fetch_ndc_signal Int64+filter / fetch_ndc_leading_index float / 全失敗 graceful
  - **回歸**：tests/ **911 passed**（907 + 4 net）零功能回歸
  - **下一步**：merge 後再按一次 bootstrap → log 會印 search API 真實回應 + 各 candidate ID metadata 結果 → 命中或徹底失敗都能診斷
  - **§5 警鈴**：若本輪仍失敗 → 直接走 C 案（Section 十一 純 TWII drawdown，捨 NDC 驗證），不再嘗試第 5 路徑
- **前一版**：v18.153_NdcOpenApiDiag（NDC URL 多 candidate 全 JSON 失敗 — 加強診斷 log 找根因）
  - **背景**：v18.152 bootstrap 10 個 NDC OpenAPI candidate URL 全回「JSON 解析失敗 line 1 column 1 (char 0)」— proxy 報「成功抓取」表示 HTTP 200 + body 有內容（非空），但首字元非 JSON。推測：NDC SPA 對所有 `/app/data/indicator/*` 路徑回 HTML 首頁（client-side routing fallback）
  - **update_macro_history.py**：`_fetch_ndc_indicator_full` JSON 解析失敗分支新增 `Content-Type` header 與 `body[:300]` dump（從原本只印 exception type → 補出 HTML/JSONP/空 body 的關鍵診斷）
  - **回歸**：tests/ 907 passed 零回歸（log 字串變動，不影響邏輯路徑測試）
  - **下一步**：merge 後 bootstrap 一次 → log 會印出 NDC 實際回什麼 → 我下一輪 PR 依結果選正確路徑（HTML 抓 → 改 data.gov.tw search；JSONP → 加 unwrap；空 → 改 query string 帶參數）
- **前一版**：v18.152_NdcOpenApiMigration（脫離 FinMind 付費牆 → 國發會 NDC OpenAPI 免費直連 + multi-URL probe）
  - **背景**：v18.151 把 dataset 改 `TaiwanBusinessIndicator` 後，bootstrap 撞 HTTP 400 `"Your level is register"` — FinMind 已把 NDC 信號/領先指標歸到 Sponsor 付費 tier（NT$500+/月）。Streamlit live tab `tw_macro.py` 用同 dataset 也壞掉（user 未察覺因為 tab 有 graceful 包覆）
  - **解法**：脫離 FinMind 改打**國發會 NDC OpenAPI**（`https://index.ndc.gov.tw/app/data/indicator/{slug}`）— PMI 已驗證有效（`macro_core._pmi_src_ndc`）+ proxy 白名單已涵蓋（`nas_server.py`），免 token、免錢
  - **update_macro_history.py**：
    - 移除 dead code `_finmind_macro_table` / `_pick_macro_column` / `_MACRO_FULL_TABLE_CACHE`（FinMind 路完全切斷，wide-format helper 不再需要）
    - 新增 `_NDC_SIGNAL_URL_CANDIDATES`（5 個 slug：monitoring / composite / signal / cyclical / SignalScore）+ `_NDC_LEADING_URL_CANDIDATES`（5 個：leading / Leading / lead / LeadingIndex / leadingComposite）+ `_NDC_VALUE_KEYS`（8 個 fallback）+ `_NDC_DATE_KEYS`（7 個）
    - 新增 `_fetch_ndc_indicator_full(candidates, label)` — 逐一 try URL via `proxy_helper.fetch_url`，多 JSON shape parser（list / {data:[]} / {items:[]} / {result.records:[]}）+ verbose log（HTTP code + body 前 200 char）供下一輪鎖死
    - `fetch_ndc_signal(start, end)` + `fetch_ndc_leading_index(start, end)` 取代舊 `fetch_finmind_*`（簽名拿掉 `token` 參數）
    - FETCHERS dict 把兩 dataset 的 `needs_token` 從 True 改 False（v18.152 起 NDC 表完全免 token）
    - Parquet 檔名保留 `finmind_ndc_signal.parquet` / `finmind_leading_index.parquet`（向後相容 macro_validation_tw.py + Section 十一 UI）
  - **tests/test_update_macro_history.py**：替換 11 個 FinMind 測試 → 11 個 NDC 測試（含 _FakeResp helper）：candidate URL constants 完整性 / 第一 URL 成功不打第二 / 第一 fail fallback 第二 / 全 URL fail 回空 / JSON shape={'data':[]} unwrap / yearMonth date key / round + Int64 cast / 範圍 filter / 全 fail graceful
  - **tw_macro.py 暫不動**：本 PR 純 bootstrap fetcher 修復；Streamlit live tab 同樣是 FinMind 來源，留下次 PR 一起遷移到 NDC OpenAPI（避免 hotfix scope 爆量）
  - **回歸**：tests/ **907 passed** 零回歸
  - **下一步**：merge 後請手動觸發 `update_macro_history.yml` workflow_dispatch + bootstrap=true / years=25 → bootstrap log 會印每個 candidate URL 的 HTTP 狀態 → 第一個 work 的 URL 自動寫進 Parquet；若全失敗，貼 log 給我 → 下一輪 PR 加新 candidate / 改用 data.gov.tw dataset ID fallback
- **前一版**：v18.151_FinMindBusinessIndicatorFix（FinMind v4 dataset 改名 hotfix — bootstrap 失敗復原）
  - **背景**：v18.149 用 dataset `TaiwanMacroEconomics` 抓 NDC + 領先指標，bootstrap 時 FinMind 回 HTTP 422 enum invalid（dataset 已被廢除/改名）→ NDC/領先 Parquet 0 rows → Section 十一驗證無資料可看
  - **根因**：FinMind v4 把 NDC monitoring + 領先 leading 合併打包成 wide-format dataset `TaiwanBusinessIndicator`（欄位：date / leading / leading_notrend / coincident / coincident_notrend / lagging / lagging_notrend / monitoring）
  - **update_macro_history.py**：dataset 改 `TaiwanBusinessIndicator`；移除 dead code `_filter_macro_indicator` + `NDC_SIGNAL_KEYS` + `LEADING_INDEX_KEYS`（wide-format 不需 long-format indicator filter）；新增 `_pick_macro_column(df, col)` wide-format 抽欄輔助；`fetch_finmind_ndc_signal` 改抓 `monitoring`、`fetch_finmind_leading_index` 改抓 `leading`；`_finmind_macro_table` cache 機制不變（NDC + leading 仍共用一次 API call）
  - **tests/test_update_macro_history.py**：移除 5 個 `_filter_macro_indicator` 測試 + 改寫 4 個 fetcher / cache 測試以 wide-format 為 fixture；新增 3 個 `_pick_macro_column` 測試（基本抽欄 + NaN drop / 缺欄 graceful / 空輸入）+ 1 個 dataset 名稱驗證測試（防 FinMind 再次改名時無感）
  - **回歸**：tests/ **907 passed**（v18.150 909 - 5 obsolete + 3 new = 907）零功能回歸
  - **下一步**：請手動觸發 `update_macro_history.yml` workflow_dispatch + bootstrap=true / years=25 → 應抓到 ~300 月 NDC + 領先資料（1984 起算）→ Section 十一可看 7 場 crisis 命中表 → 接 Phase E 跨來源比對
- **前二版**：v18.150_MacroBacktestUI（macro tab section 十一 — 歷史驗證 UI，鏡像 fund Phase 6a）
  - **User 需求**：「兩邊都可以做回測來驗證台股的總經 tab 與基金（全球的）總經 tab」。Sister repo my-Fund-dashboard 已於 v18.276 Phase B.2 把 Parquet 接到 Phase 6a 驗證 UI；本 PR 為台股對等版本，讀 PR #149 v18.149 鋪好的 NDC + 領先指標 Parquet + 既有 twii_ohlcv → 雙指標 × TWII crisis 命中表
  - **macro_validation_tw.py**（~270 行 pure data）：3 個 Parquet loader（NDC / 領先 / TWII close）+ `detect_twii_crisis_events`（high-water-mark walk-forward，與 fund crisis_backtest 同範式，預設 20% 回撤）+ `verify_ndc_signal_vs_crises`（峰前 N 月 → 峰時 NDC 下降 ≥ drop_pts 分；預設 4 分 ≈ 1 燈號跨度）+ `verify_leading_index_vs_crises`（peak 月 6M smoothed change < 0 即命中）+ `compute_smoothed_change_pct`（與 tw_macro.fetch_ndc_leading_index 一致 rolling 6 月 MA → pct_change × 100）+ `compute_hit_rate` 統計卡 helper
  - **tab_macro_validation.py**（~240 行 Streamlit UI）：`render_history_validation_section(cache_dir)` — Section 十一 渲染；缺檔友善 banner 引導 user 等 cron；3 sliders（TWII 回撤門檻 10-40% / lead_months 3-12 / NDC drop_pts 2-10）+ 跑按鈕 + 2 張命中率卡 + plotly 雙軸圖（TWII 主軸 + NDC 副軸 + crisis 紅區）+ NDC/領先指標雙命中表 + 2 個 CSV 下載按鈕（utf-8-sig BOM 解 Excel）
  - **tab_macro.py**：插 11 行（section 十之後，結尾 `<hr>` 之前）— `from tab_macro_validation import render_history_validation_section` + 呼叫，try/except 包覆避免 Parquet 缺檔影響整 tab 渲染
  - **tests/test_macro_validation_tw.py**（29 case 全綠）：Parquet 讀取（缺檔 / 正常解析 / 壞檔 graceful）/ detect_twii_crisis_events（v 型 / 門檻下無事件 / 空 / 過短 / open-ended 無 recovery / 多事件）/ verify_ndc（命中 exact 4 pts / 明確 8 pts / 無事件 / 空 series）/ compute_smoothed_change（常數 → 0% / 線性升全正 / 空 input）/ verify_li（peak 時 smooth<0 命中 / 單調升不命中 / 空 input）/ compute_hit_rate（mixed / empty / all None drop_pts）/ UI source-level（tab_macro.py import 與呼叫 + 模組 export render fn + section 順序在 10 之後）
  - **回歸**：tests/ **909 passed** 零回歸（880 + 29 新）
  - Roadmap：Phase D（PMI 補抓進 Parquet）→ Phase E（fund + stock 同框跨來源比對工具）
- **前三版**：v18.149_NdcLeadingHistoryFetchers（macro_history 擴 2 新表：景氣對策信號 + 領先指標）
  - **User 需求**：「兩邊都可以做回測來驗證台股的總經 tab 與基金（全球的）總經 tab」+ 「直接抓取資料放在資料庫，之後每周定期更新」→ 沿用 PR #144 已建的 Parquet 快取模式（非 SQLite），補上**驗證總經 Tab 的關鍵 2 指標**：NDC 景氣對策信號（拐點偵測 9-45 分）+ 領先指標綜合指數（6M smoothed change 領先期）
  - **update_macro_history.py**：新增 `fetch_finmind_ndc_signal` + `fetch_finmind_leading_index`（都打 FinMind TaiwanMacroEconomics dataset，模組級 `_MACRO_FULL_TABLE_CACHE` 字典快取讓兩 fetcher 共用一次 API call）；新增 `_finmind_macro_table()` 全表抓取（含 cache）+ `_filter_macro_indicator()` 指標篩選工具（支援 indicator/name/metric × value/data 欄位變體 + exact→contains 兩層 fallback）；DATASETS 從 4 表擴 6 表，FETCHERS dict 同步註冊（皆需 FINMIND_TOKEN）
  - **新增 Parquet**：`data_cache/finmind_ndc_signal.parquet`（columns: date, ndc_signal Int64）+ `data_cache/finmind_leading_index.parquet`（columns: date, leading_index float）；領先指標**只存原始值**，6M smoothed change 由分析端 on-the-fly 算（rolling 6 月需 lookback context，fetcher 增量時無法正確算）
  - **tests/test_update_macro_history.py**（+12 case = 19 全綠）：DATASETS 註冊驗證 / `_filter_macro_indicator` exact match / contains fallback / no match / empty input / missing columns / 替代欄位名（metric+data）/ macro_table_cache 同 key 不重打 / fetch_ndc_signal shape（含 Int64 + round）/ fetch_leading_index shape / fetch 找不到時回空 / NDC + LI 共用同一次 API call cache
  - **回歸**：tests/ **880 passed** 零回歸
  - Roadmap：Phase 2（macro tab 加歷史驗證 UI 子區塊 — 讀 Parquet 算月度 score、對齊 TWII crisis hit/miss）→ Phase 3（fund-dashboard FRED 9 指標 Parquet cache）
- **前三版**：v18.148 代碼淨化收尾（#148 — v5_modules / v4_strategy_engine / nas_server unused vars/imports 移除，0 邏輯改動）
- **前四版**：v18.147 macro-history 守護鏈強化（#144-#147）
  - **#144**：總經歷史資料快取層 + 每日增量 Actions（解 TWII-only 結構性偏弱）。data_cache/ Parquet 表 git 追蹤——twii_ohlcv / finmind_inst / finmind_margin / finmind_m1m2 + metadata.json。`update_macro_history.py` 無 streamlit 相依爬蟲，增量 append+dedupe；workflow 每日 UTC 09:00 + bootstrap mode；`calibrate_macro_traffic.py` 加 load_from_cache + _enrich_with_finmind 注入 FinMind 欄位
  - **#145-#147**：production hardening——FinMind 改直連印 HTTP status、三大法人英文 name 篩 'Foreign'、CBC M1B/M2 三 URL 備援 + SDMX EF15M01 fallback
- **前四版**：紅綠燈門檻校準走 Walk-Forward + 季度排程（反過擬合）
  - **calc_traffic_light**：加 `health_defense_threshold` / `bull_min_score` optional kwargs（不影響 production，純供校準注入）
  - **macro_helpers.py**：module load 時優先讀 `macro_thresholds.json`，缺檔/越界 silently fall back module 常數；越界守門 H∈[20,60]、S∈[1,6]
  - **calibrate_macro_traffic.py**：新增 `walk_forward_validate(df, n_folds=4)`——滾動切折、每折 train 找最佳門檻 grid (H∈[25,45] step 2 × S∈[2,5])、test 報告 OOS、目標函數含「偏離現行常數」正則項；新增 `evaluate_thresholds` / `grid_search_thresholds` / `emit_thresholds_json` / `build_proposal_report`；CLI 加 `--optimize --emit-json --emit-proposal --n-folds`
  - **過擬合三重保護**：(a) walk-forward 永不在 train 評分 (b) 票選 + drift>30% 過半即回退預設 (c) 季度排程開 PR 給人類審閱、不自動 merge
  - **`.github/workflows/recalibrate_macro.yml`**：季度排程（1/4/7/10 月 1 號）+ workflow_dispatch（input range/n_folds），需 Secrets `PROXY_URL` + `FINMIND_TOKEN`，跑完開 PR with proposal as body
  - **calibration_ui.py**：UI 加 `_show_threshold_status()` 顯示現行門檻 + 最後校準時間戳 + 方法
  - **tests/test_calibrate_walkforward.py**：8 個 smoke（合成資料 walk-forward 不 raise、過擬合保護回退、threshold 覆寫單調性、JSON 讀寫一致、正則項懲罰偏離）全綠
- **前五版**：資料異常清單 2 筆續修——PMI / 出口 YoY 新源（CIER 英文月度頁 + stat.gov.tw），全走 NAS 中繼站
  - **PMI**：新增 `_pmi_src_cier_en_monthly`（macro_core.py）為最高優先源，直接打 CIER 英文月度 slug `/en/eco/taiwan-manufacturing-pmi-{月}-{年}/`，每次嘗試 current/-1/-2 月共 3 個 slug；CIER 是官方發布單位、slug 結構自 2024 起穩定、HTML 乾淨命中率 >95%。9 源 → 10 源並行，全走 `fetch_url`（NAS Squid → 直連 → NAS 中繼站 fallback）
  - **出口 YoY**：在 `tab_macro.py:_fetch_export()` 最前面插方案 0 stat.gov.tw（DGBAS 出口年增率頁 `Point.aspx?sid=t.8&n=3587&sms=11480`），HTML 抓「YYYY年M月 出口年增率 XX.X%」格式；與 #141 的 FRED series 校正 + data.gov.tw 6053 互補形成 6 源備援鏈
  - 根因：海外 IP 雖透過 `fetch_url` 三層 fallback 過 NAS，但**舊源 URL 結構失效**（CIER `/news/list?cid=21` 列表改、MOF 月度 CSV 路徑變動）→ 全鏈路滑落到靜態備援（出口 92 天前）或全失敗（PMI 未取得）
- **前六版**：v18.142 資料抓取器 series id / endpoint 校正（#141）
  - **美國核心 CPI**：誤用 `CPIAUCSL`（總體）→ 改 `CPILFESL`（核心）；新增方案 0 `fredgraph.csv` 無需 API key；BLS fallback 改 `CUSR0000SA0L1E`
  - **台灣出口 YoY**：FRED `VALEXPTWM052N`（IFS 延遲 13 月）→ 改 `XTEXVA01TWM664S`（OECD MEI 延遲 2-3 月）；新增 data.gov.tw dataset 6053 海關進出口貿易統計方案（走 NAS proxy）
  - tab_edu.py + data_registry.py 同步 identifier；新增 10 個 source-level regression tests；tests/ 850 passed
- **前七版**：紅綠燈校準誠實化 + 門檻收斂（#137-#140）
  - **#140**：校準報告加 TWII-only 警語 banner、建議讀現行常數（`HEALTH_DEFENSE_THRESHOLD=35` / `BULL_MIN_SCORE=4`）
  - **#139**：5Y TWII 校準顯示防禦 precision 14.8%、多頭 30.7% → `calc_traffic_light` 防禦 `_health < 40` 改 `<35`、bull 加 `_score >= 4` 條件
  - **#137-#138**：校準 Streamlit UI Tab + 比較×排行卡片載入修
- **前八版**：ETF 經理人換手偵測持久化（#131-#132）
  - `update_etf_managers.py`（獨立爬蟲走 proxy_helper）+ workflow + watchlist/managers JSON；`track_etf_manager_change` 改以 repo 持久檔為主、`/tmp` 降次要，解決雲端重啟即清空→紅框不跳
  - 沿革：#119 PMI/NAV/費用率改走 fetch_url → #122 主動式 ETF 中文名 + NAV 改 Basic0003 → #124 fetch_etf_meta_moneydj（Basic0004 一次取齊）→ #126 經理人異動偵測 → #127 折溢價直讀 MoneyDJ Basic0001 + 費用率破「經理費(%)」陷阱 → #129 折溢價假日對齊最後交易日 → **#131** 經理人換手持久化 → **#132** ETF watchlist 擴充至 28 檔
  - ⚠️ **前提**：MoneyDJ 擋海外 IP，Streamlit App secrets 須設 `PROXY_URL`（家用 NAS 台灣 IP）這些 ETF 欄位才有值，否則 N/A
- **Secrets**：`FINMIND_TOKEN` · `GEMINI_API_KEY[_2..6]` · `PROXY_URL` · `FRED_API_KEY` ·（選配 `NAS_BASE_URL` / `NAS_API_KEY`）

## 模組分層（PR #58–#73 大重構後）
```
UI 層         app.py（1378 行入口） · tab_macro / tab_stock / tab_stock_grp / tab_edu
             etf_dashboard（49 行 shim）→ etf_tab_single / _portfolio / _backtest / _ai
             ui_widgets.py（9 個純 HTML 函式）
共用層        tab_helpers.py · macro_helpers.py · etf_helpers.py · tech_indicators.py
資料抓取      data_loader · macro_core · tw_macro · daily_checklist · tw_stock_data_fetcher
ETF 三層      etf_fetch（I/O） · etf_calc（計算） · etf_render（UI）
引擎          scoring_engine / financial_health_engine / market_strategy / risk_control
             backtest_engine / unified_decision / v4_strategy_engine / v5_modules
             yield_screener / flow_engine / exit_signals
AI / 警示     ai_engine · macro_alert · macro_state_locker · persona
雲端 / 基建   gsheet_portfolio · oauth_state · infra/oauth · proxy_helper · nas_server
熱錢監測      hot_money.py（三角交叉：外資 × 匯率 × 背離）
```

## 測試
- `pytest tests/` + `pytest test_*.py`
- 核心 smoke：`tests/test_hot_money.py`、`test_app_step4.py`、`test_market_strategy.py`

## 配置
- `requirements.txt` — runtime；`.streamlit/config.toml` — UI 設定
- 分支：開發於 `claude/etf-portfolio-download-CKR5h`，主幹 `main`
