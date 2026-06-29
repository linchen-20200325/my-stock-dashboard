# Dead Code Audit(v18.397 P5-DEAD)

> AST-based 跨整 repo 分析,找 0 cross-file caller 的 public def/class。
> 已排除 `__init__.py` re-export(僅命名空間 expose 不算真 caller)+ 文檔/註解 reference。

## 📊 數字總覽

| 度量 | 值 |
|---|---|
| 總 public def/class | 463 |
| **0 跨檔 caller 候選** | **52** |
| Tier 1 整 module dead | 1 檔(654 LOC) |
| Tier 2 多 fn dead | 4 檔(~20 fn) |
| Tier 3 單 fn dead | ~30 fn |
| 估計可清 LOC | ~1500-2000 |

## 🔴 Tier 1 — 整 module dead

### `src/services/ai_engine.py`(654 LOC,5 public fn)

| Function | Status |
|---|---|
| `analyze_stock_trend` | 0 prod caller(僅 module 內 self-ref + 1 test source-string check) |
| `analyze_stock_trend_stream` | 0 prod caller(自呼 analyze_stock_trend) |
| `analyze_leading_indicators` | 0 prod caller |
| `generate_quick_summary` | 1 test caller(test_pr_m1_smed_tier1.py 透過 lazy __getattr__) |
| `generate_daily_report` | 0 prod caller |

**真實 production AI 呼叫鏈**(取代 ai_engine):
- `app.py:gemini_call` → 直接 caller(`section_news_ai` / `sidebar_health` 用)
- `src/services/ai_fetcher.post_gemini` → `financial_health_engine` + `macro_state_locker` 用
- `src/services/ai_structured_summary.build_structured_summary_prompt` → `etf_render` 用

**EX-AI-1 例外重大改判**:
- CLAUDE.md §8.2.A EX-AI-1 文字「~10+ caller 全部以 st.markdown 渲染字串」
- 實際 0 caller!例外建立在錯誤前提
- **建議**:retire EX-AI-1 + 刪整檔 ai_engine.py
- **配套**:
  - 改 `tests/test_pr_m1_smed_tier1.py` 引用(改測 ai_fetcher 等價或刪測)
  - 改 `src/services/__init__.py` 移除 ai_engine re-export
  - 更新 CLAUDE.md §8.2.A 例外清單 retire EX-AI-1

**規模**:-654 LOC(扣掉 ai_fetcher 取代後可能多寫 ~50 LOC 維持等價;淨 -600)。

## 🟠 Tier 2 — 多 fn dead(可整批清)

### `src/data/macro/leading_indicators.py`(7 fn dead)
- `d2ymd` — date 格式化 helper
- `finmind_fut_oi` — 期貨未平倉(已被 `compute_tw_leading_indicators` 取代)
- `taifex_large_trader` / `taifex_calls_puts_day` / `taifex_pcr` — TAIFEX 子 fetcher
- `twse_volume_daily` / `twse_institutional_day` — TWSE 子 fetcher

歷史:PR-N3/N4/N5 重構 daily_checklist 時把這些 fetcher 等價搬入 `src/data/daily/`,**舊版 leading_indicators 內 fn 留下殘骸**。

### `src/data/stock/tw_stock_data_fetcher.py`(6 fn dead)
- `fuzzy_get` / `fuzzy_get_from_df` — fuzzy column matching helper
- `fetch_goodinfo_metrics` / `parse_goodinfo_table` — Goodinfo 抓取
- `proxy_get` / `proxy_post` — proxy wrapper
- `calc_financial_metrics` — 財務指標

歷史:可能是 PR-Q5 / S-PROV-1 phase 19 重構時把核心邏輯搬走,但 helper 保留。

### `src/compute/strategy/v5_modules.py`(3 fn dead)
- `get_defensive_allocation` / `calc_relative_strength` / `calc_valuation_zone`

可能是早期 v5 策略引擎 helper,後改用 scoring_engine 取代。

### `src/compute/etf/etf_quality.py`(4 fn dead)
- `score_expense` / `score_beta` / `score_aum` / `score_yield_cv`

ETF quality 評分子函式,可能被 PR-H1/H2 重構時整合到別處。

## 🟡 Tier 3 — 單 fn dead(個別刪)

| File | Dead fn | 估計 LOC |
|---|---|---|
| `src/compute/scoring/scoring_engine.py` | `compute_rsi` | ~10 |
| `src/compute/etf/etf_calc.py` | `calc_avg_volume_20d` | ~15 |
| `src/compute/risk/risk_control.py` | `atr_stop_price` | ~20 |
| `src/compute/scoring/exit_signals.py` | `build_news_prompt` | ~15 |
| `src/compute/etf/etf_margin_simulator.py` | `SimulationResult` + `SimulationDay` | ~30(dataclass) |
| `src/compute/screener/fundamental_screener.py` | `ScreenResult` | ~10(dataclass) |
| `src/ui/tabs/tab_mj_health_diff.py` | `parse_codes` | ~10 |
| `src/ui/tabs/monthly_revenue_screener.py` | `fetch_batch_monthly_revenue` | ~30 |
| `src/ui/tabs/grape_ladder.py` | 4 fn(evaluate_income_ladder / get_avg_monthly_cash / recommend_income_ladder / get_pay_months)| ~60 |
| `src/ui/etf/etf_tab_grp_compare.py` | `parse_etf_codes` | ~10 |
| `src/data/macro/macro_snapshot.py` | `fetch_twii_2y_for_ma240` | ~20 |
| `src/data/macro/tw_macro.py` | `fetch_pmi_history` | ~30 |
| `src/data/etf/etf_fetch.py` | `get_etf_index_last_err` | ~10 |
| `src/data/proxy/nas_server.py` | `FetchReq` / `proxy_relay` | ~40 |
| `src/data/proxy/proxy_helper.py` | `make_retry_session` / `fetch_with_proxy` | ~30 |
| `src/data/core/data_registry.py` | `ping_endpoint` / `get_state_value` | ~30 |
| `src/data/core/data_loader.py` | `fetch_fund_nav` | ~20 |
| `src/compute/scoring/multi_factor_optimization.py` | `FactorSpec` | ~15(dataclass) |

Tier 3 合計:~400 LOC。

## ⚠️ False positive 警示

dataclass / type hint return type 可能被「型別宣告但無實際 instantiate」用,grep 找不到:
- `SimulationResult` / `SimulationDay`:可能是 `etf_margin_simulator` 內部回傳型別,caller 不需 import name
- `FactorSpec`:同上
- `ScreenResult`:同上

**deletion 前需 verify**:
1. grep `: SimulationResult` / `-> SimulationResult` 等 type hint
2. 看是否有 `pickle.load` / `dataclasses.asdict` 動態使用

## §-1 對齊

| 觸發條件 | 滿足? |
|---|---|
| user 實際在用 | dead code 定義上「未在用」|
| 真實 bug 觸發清碼需求 | ❌ |
| user 主動指派 dead code audit | ✅ |
| ROI 高 | ✅(可清 1500-2000 LOC,降 maintain 負擔) |

## 📋 建議清碼順序(LOW → HIGH risk)

| Phase | 內容 | LOC | 風險 |
|---|---|---|---|
| **Dead-α** | Tier 3 單 fn dead(20+ 個 fn)| ~400 | LOW |
| **Dead-β** | Tier 2 leading_indicators 7 fn + tw_stock_data_fetcher 6 fn | ~250 | LOW-MED |
| **Dead-γ** | Tier 2 v5_modules 3 fn + etf_quality 4 fn | ~150 | MED(scoring 邏輯,需確認 SSOT 抽離後再刪) |
| **Dead-δ** | **Tier 1 ai_engine 整檔 + EX-AI-1 retire** | -650 | MED-HIGH(改 CLAUDE.md 例外清單) |

## 🚨 重大發現:EX-AI-1 例外建立在錯誤前提

- CLAUDE.md §8.2.A EX-AI-1 文字提「~10+ caller」 → 實際 **0 caller**
- 真 production AI 走 `ai_fetcher.post_gemini` + `app.py.gemini_call` 兩條路
- ai_engine.py 是 v18.386 A1 「Gemini API 統一」之前的舊路徑,**A1 改完後沒刪**

→ Dead-δ phase 應 retire EX-AI-1 例外 + 刪 ai_engine.py。

## 結論

dead code audit 找到 52 個 0-caller public def,跨 ~25 個 file,~1500-2000 LOC 可清。
最重大發現:**ai_engine.py 整檔 654 LOC 全 dead code**(EX-AI-1 例外失效)。

建議 user 認可後分 4 phase 清除(LOW → MED-HIGH risk)。
