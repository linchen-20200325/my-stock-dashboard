# Dead Code Audit — 嚴格雙重條件版(v18.398 P5-DEAD-RE-AUDIT)

> 取代 PR #404 的舊 audit。原 audit 的「跨檔 0 import」邏輯把 module-internal helper 誤判為 dead。
> 新 audit 用**雙重條件**:跨檔 0 ref AND 自己 module 也 0 self-ref。

## 📊 4-Tier 分類結果

| Tier | 定義 | 數量 | 處理 |
|---|---|---|---|
| **T1** | prod=0 + test=0 + self=0(真 dead) | **5 候選 / 1 真 dead** | 真 dead 可刪 |
| **T2** | prod=0 + test>0 + self=0(production dead but test live)| **25** | 逐個 audit |
| **T3** | self>0 + prod=0(module-internal helper) | 53 | **不是 dead**(舊 audit 誤判) |
| **T4** | cross-module live(baseline) | 380 | 正常 |
| 總 public def/class | | 463 | |

## ✅ Tier T1 真 dead — 修正後僅 1 處

| File:Line | Name | 結論 |
|---|---|---|
| `src/data/stock/tw_stock_data_fetcher.py:244` | `fuzzy_get` | ✅ **真 dead**(dict 版,fuzzy_get_from_df DataFrame 版仍 live) |
| `src/data/proxy/nas_server.py:287` | `proxy_relay` | ❌ false positive — FastAPI HTTP endpoint(`@app.get("/proxy")`),動態 dispatch |
| `src/ui/tabs/macro/section_warroom.py:33` | `render_section_warroom` | ❌ false positive — tab_macro:225 直 call(audit logic bug) |
| `src/ui/tabs/macro/section_cross_ai.py:25` | `render_section_cross_ai` | ❌ false positive — 同上 |
| `src/ui/tabs/macro/section_overview.py:19` | `render_section_overview` | ❌ false positive — 同上 |

**T1 真 dead 最終:1 處 `fuzzy_get`(已刪除,~12 LOC,v18.398)**

## 🟡 Tier T2 — Production dead but test live(25 處)

production code 0 caller,但 test 1+ 引用。3 種可能性:
- (a) **test 先寫待 production 接入** → keep(future use)
- (b) **以前 production 用,改路徑後沒清測** → 同步刪函式+測試
- (c) **測試直接測 lib safety net** → keep(safety net)

### T2 候選表(需個別 audit)

| File:Line | Name | test ref | 推測類別 |
|---|---|---|---|
| `src/compute/risk/risk_control.py:245` | `calc_position_size` | 3 | (c) safety net 可能 |
| `src/compute/risk/risk_control.py:248` | `calc_stop_loss` | 4 | (c) |
| `src/compute/macro/macro_helpers.py:612` | `calc_real_rate` | 6 | (c) |
| `src/compute/macro/macro_helpers.py:641` | `classify_rate_cycle` | 7 | (c) |
| `src/compute/macro/macro_helpers.py:702` | `calc_twd_trend` | 6 | (c) |
| `src/compute/health/mj_snapshot_io.py:149` | `list_all_stocks_with_snapshots` | 4 | (b) 可能(若 mj_health 退役)|
| `src/compute/health/mj_health_diff.py:269` | `screen_health_changes` | 13 | (c) 高 test ref |
| `src/compute/scoring/scoring_engine.py:1175` | `check_contract_liability_surge` | 8 | (a/b)需 verify |
| `src/compute/scoring/scoring_engine.py:1194` | `check_bollinger_squeeze` | 8 | 同 |
| `src/compute/scoring/scoring_engine.py:1226` | `check_fake_breakout` | 6 | 同 |
| `src/compute/scoring/scoring_engine.py:1249` | `check_relative_strength` | 8 | 同 |
| `src/compute/scoring/scoring_engine.py:1296` | `calculate_position_size` | 9 | 同 |
| `src/compute/screener/fundamental_screener.py:199` | `screen_stocks` | 19 | (a) 高 test ref |
| `src/compute/screener/fundamental_screener.py:263` | `filter_passed` | 2 | (c) |
| `src/ui/tabs/tab_macro_validation.py:28` | `render_history_validation_section` | 5 | ⚠️ **半 archive**(ARCHIVED_FEATURES.md 已記錄)|
| `src/ui/tabs/macro/section_short.py:20` | `render_section_short` | 2 | ❌ false positive(tab_macro 用)|
| `src/ui/tabs/macro/section_chips.py:28` | `render_section_chips` | 3 | ❌ false positive |
| `src/ui/tabs/macro/section_summary_bar.py:17` | `render_five_bucket_summary` | 2 | ❌ false positive |
| `src/data/macro/leading_indicators.py:786` | `build_leading_indicators` | 1 | (a/b) needs verify |
| `src/data/macro/tw_macro.py:875` | `fetch_tw_market_snapshot` | 2 | (b)? |
| `src/data/macro/tw_macro.py:982` | `fetch_tw_cpi_yoy` | 6 | (c) |
| `src/data/macro/tw_macro.py:1011` | `fetch_tw_unemployment` | 2 | (b)? |
| `src/data/macro/tw_macro.py:1039` | `fetch_cbc_discount_rate` | 4 | (c) |
| `src/data/macro/tw_macro.py:1074` | `fetch_usdtwd_close` | 2 | (b)? |
| `src/data/macro/macro_core.py:587` | `fetch_ism_pmi` | 4 | (c) |

### T2 audit 結論
- 4 處 render_section_* 是 false positive(tab_macro 直 import)
- 1 處 `render_history_validation_section`(半 archive,ARCHIVED_FEATURES.md 已記錄)
- 剩 20 處需逐一 audit 分類(a)/(b)/(c)

## 🔵 Tier T3 — Module-internal helper(53 處,不是 dead)

舊 audit 的 false positive 來源。包含 `compute_rsi` / `atr_stop_price` / `calc_avg_volume_20d` 等
被同 module 內其他 fn self-reference 的合法 helper。

**結論:不刪,保留**。

## 🚨 ai_engine 重新評估

舊 audit 把 ai_engine 5 個 fn 列為 dead。新嚴格 audit 顯示:
- `analyze_stock_trend_stream` self ref 1(L430 呼叫 `analyze_stock_trend`)
- 其餘 4 個 fn 屬 T2(test ref) or T4(cross-module)?

需重 audit ai_engine 5 fn 的 self-ref count(AST-based 排除 docstring/comment)。
前次 sample 顯示 ai_engine 內部 reference 15 次 — 多是 docstring/comment,而非真 code call。

**先行結論**:ai_engine.py 不能輕易刪;真正 entry 是否 dead 需排除 docstring + comment 後重 count。

## 📋 真 dead 行動建議

| Item | Action | LOC |
|---|---|---|
| **fuzzy_get** | ✅ 已刪除(v18.398 P5-DEAD-RE-AUDIT)| ~12 |
| 25 T2 候選 | 逐個 audit 分類(a)/(b)/(c)後再決定 | TBD |
| ai_engine | AST-based 嚴格重 audit(排 docstring/comment ref)| TBD |
| 53 T3 候選 | **不刪**(false positive of old audit) | 0 |

## §-1 對齊

| 觸發條件 | 滿足? |
|---|---|
| user 主動指派 | ✅(重 audit 是 user 要求) |
| 真實 bug 觸發 | ❌ |
| ROI 高 | ⚠️(真 dead 僅 ~12 LOC,T2 audit 需手工逐個 verify ROI 不高) |

**判定**:**T1 真 dead 1 處可清(已刪)**。T2 25 處需 user 認可後逐個 audit。
舊 audit 「~1500-2000 LOC 可清」**過度樂觀** — 嚴格條件後僅 ~12 LOC 真 dead。

## 結論

舊 PR #404 audit 邏輯有缺陷,**真 dead 只 1 處**(已刪)。
T2 25 處需逐個 audit 區分(a)未來用 vs(b)該清 vs(c)safety net,無法批量處理。
ai_engine 整檔可能仍有 dead 但需更嚴格 audit。
