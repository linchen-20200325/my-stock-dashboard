# 已封存 / 退役功能記錄 (ARCHIVED_FEATURES)

> 本檔記錄「曾經開發、後來真刪」的功能,對齊 §-1「不用的東西不該存在」+ 前例
> (backtest_engine v18.265 全刪、tab_macro_validation v18.399 全刪)。
> **真刪而非留死碼**:原始碼可由 git history 完整還原(附還原 commit / 路徑)。
> 若日後要復活,先讀本檔對應段找回原碼,再評估是否重新掛載。

---

## v19.159 — 團隊交叉稽核「孤兒 UI」批次退役(P3)

四路稽核發現一批「後端還活、UI 入口早已下架」的 L5 孤兒 Tab(建好後端 + SSOT +
測試,但 UI 入口被移除卻沒清乾淨)。經 user 核准「真刪 + 存檔」,比照 backtest /
macro_validation 前例處理。刪除前逐一 grep 驗證 0 production caller + 精算專屬後端。

### 1. ETF 質借模擬器(整功能棧,exclusive)
- **刪除**:
  - `src/ui/tabs/tab_etf_margin_simulator.py`(L5 UI,自 v18.464 未掛任何 Tab)
  - `src/compute/etf/etf_margin_simulator.py`(L2 引擎:get_preset / simulate_margin_strategy /
    result_to_dataframe;唯一 caller = 已死 UI)
  - `src/data/etf/etf_fetch.py::fetch_etf_close_history`(L1 fetcher,B7-a v19.154 才從
    UI 下沉,唯一 caller = 已死 UI → 隨之退役)
  - 測試:`tests/test_etf_margin_simulator.py`、`tests/test_etf_margin_simulator_coverage.py`
  - `src/compute/etf/__init__.py` 移除 etf_margin_simulator 註冊
- **保留**:無共用後端。
- **還原**:`git show <v19.159 前 commit>:src/compute/etf/etf_margin_simulator.py` 等。

### 2. MJ 體檢變化 Tab(UI only,後端共用保留)— ⚠️ **已於 v19.160 復活**

> user 需求「找體質差→變好的公司」→ 從 git 撈回 UI + **修當初 v18.463 漏掛根因**(掛回
> 🔬 選股群組「🩺 體檢轉機」)+ 加「🔗 帶入我的持股」入口 + 守衛測試釘住掛載。以下為原退役紀錄(保留供追溯):

- **刪除**:`src/ui/tabs/tab_mj_health_diff.py`(L5 UI,`render_mj_health_diff_tab` 0 caller)
  + `src/ui/tabs/__init__.py` 移除註冊。
- **保留(仍 LIVE)**:`diff_mj_health` / `HealthDiffVerdict` / `analyze_financial_health`
  (經 mj_trend_score 供個股組合 Tab 使用,**未動**)。
- **還原**:`git show <...>:src/ui/tabs/tab_mj_health_diff.py`。

### 3. 月營收進退篩選器(UI + 專屬 helper)
- **刪除**:
  - `src/ui/tabs/monthly_revenue_screener.py`(L5 UI,`render_monthly_revenue_screener` 0 caller;
    STATE.md:222 專案早已自認「與缺貨模式重複 → §-1 WONTFIX」)
  - `src/compute/health/monthly_revenue_calc.py::screen_from_batch` / `filter_by_mode`
    (該死 UI 專屬,其餘函式 compute_yoy_mom / classify_trend / TREND_LABELS 保留)
  - 測試:`tests/test_monthly_revenue_screener.py`
  - `src/ui/tabs/__init__.py` 移除註冊
- **保留(仍 LIVE)**:`src/data/stock/monthly_revenue_fetcher.py`(月營收 fetcher,他處在用)、
  月營收動能仍由缺貨模式 shortage_screener 覆蓋。
- **還原**:git history。

### 4. 抗跌 RS 獨立選股 UI wrapper(UI only,後端共用保留)
- **刪除**:`src/ui/tabs/rs_leader_ui.py`(`render_rs_leader_screener` 選股網 v19.111 極簡化時
  移除進階 expander 後僅剩 test 引用)+ `tests/test_rs_leader_ui.py`。
- **保留(仍 LIVE)**:`src/services/rs_leader_service.py`(app.py 仍用)、
  `rs_leader_screener`(L2)、`test_rs_leader_service` / `test_rs_leader_screener`。RS 功能未死。
- **還原**:git history。
