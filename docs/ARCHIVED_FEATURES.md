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

### 2. 財報體檢變化 Tab(UI only,後端共用保留)— ⛔ **最終狀態:v19.164 已真刪,無獨立分頁**

> **B6-a v19.181 更正**:本節標題原掛「⚠️ **已於 v19.160 復活**」,但那是**中途狀態**——
> 該分頁 v19.160 復活後,又於 **v19.164 再次退役真刪**(功能合併進 🏆 個股組合的
> 「📊 財報趨勢×轉機」區塊)。舊標題會讓讀者去 🔬 選股 找一個叫「🩺 體檢轉機」的
> 分頁 —— **那個分頁不存在**(現行 🔬 選股 只有 🔬 個股 / 🏆 個股組合 / 🔭 選股網,
> evidence: `app.py:584`)。時間軸完整記錄如下,勿再只讀標題就下結論。

**時間軸**:v18.463 漏掛(0 caller)→ v19.159 退役真刪 → v19.160 復活並掛「🩺 體檢轉機」
→ **v19.164 再次退役真刪**(合併進 🏆 個股組合,`compute_one_stock_trend` 附帶算
`diff_verdict`,零額外抓取、去掉第二個輸入框與重複表格)。**現況 = 無獨立分頁**。

- **刪除**:`src/ui/tabs/tab_mj_health_diff.py`(L5 UI,`render_mj_health_diff_tab` 0 caller)
  + `src/ui/tabs/__init__.py` 移除註冊。
  （※ 檔名為當時的歷史事實,不改寫;該檔已於 v19.164 再次退役真刪。）
- **保留(仍 LIVE)**:`diff_fin_health` / `HealthDiffVerdict` / `analyze_financial_health`
  (經 `fin_trend_score` 供個股組合 Tab 使用,**未動**;v19.174 去識別化改名,舊名保留 alias)。
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

---

## 2026-11-17 — ETF 經理人換手策略(Issue #1208;客戶取消,整組真刪)

客戶原文:「那換手策略就不考慮了 這個方式移除」。經理人不再當投資因子,不新增替代建議、不改其餘 ETF 分數／公式。

- **刪除**:
  - L1 `src/data/etf/etf_fetch.py`:`fetch_etf_manager`、`_fetch_sitca_manager`、`track_etf_manager_change`
    (repo JSON ＋ `/tmp/st_cache/etf_manager_history.json`、first_seen／180 天 recent／is_new)、
    `get_etf_manager_last_err`／`_ETF_MANAGER_LAST_ERR`。
  - L0 `shared/signal_thresholds.py::ETF_MANAGER_TENURE_NEW_DAYS`。
  - L2 `asset_lag.classify_lag_verdict` 的 `is_etf`／`tenure_days` 參數與「新經理人 <6 月 → 再給時間」例外;
    `etf_calc.compute_etf_weakness_row` 的經理人／任期欄與經理人抓取。
  - UI:`etf_tab_single` 經理人／任期／🔁異動／🆕新任卡;`etf_tab_portfolio` 新經理人提示;
    `etf_render._render_weakness_table` 經理人／任期欄;`health_inspector` 基金經理人診斷列、經理人探測列、
    經理人 regex 深度診斷(直打 MoneyDJ Basic0001)。
  - 資料生產:`.github/workflows/update_etf_managers.yml`、`scripts/update_etf_managers.py`、`src/data/etf/etf_managers.json`、`src/data/etf/etf_manager_watchlist.json`、`tests/test_etf_managers_data_pr.py`;`scripts/publish_data_pr.py` 的 etf_managers.json 揮發鍵登記。
- **保留(仍 LIVE)**:`is_active_etf`、`_fetch_yuanta_active_etf_meta`(主動式 ETF 費用率備援仍用)、
  `_html_kv_pairs`、ETF 價格／配息／AUM／Beta／費用率／持股／品質評等、弱勢度燈號(價格績效)、持股探測、
  `publish_data_pr` 其他三個 job。
- **反向守衛**:`tests/test_issue1208_manager_strategy_removed.py`。
- **還原**:`git show efa0e015:<path>`(本批前 main)。⚠️ 復活前須先過 MoneyDJ 來源權利 Gate(#1116／#1207)。
