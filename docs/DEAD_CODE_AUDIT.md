# Dead Code Audit — T2 25 候選 AST-strict 重 verify(v18.400 自動處理收尾)

> 接 PR #406 嚴格雙重條件 audit。T2 25 處 prod-dead-test-live 候選逐個 AST-strict
> 重 verify,並驗 test 內部對函式的真實使用形式。

## 📊 T2 25 候選最終分類

| Status | 數 | 處理 |
|---|---|---|
| 🟡 prod dead test-live(保 T2)| 20 | 不刪(test 直測或 source-string 保護) |
| ✅ 跨檔 live(升 T4 — false positive)| 3 | tab_macro 直 import |
| 🛡️ test-source 保護(真 dead 但 test 鎖)| 2 | 不刪(deletion 會 break test) |
| 🔵 internal helper(升 T3)| 0 | |

## 🛡️ Test-source 保護:不能刪

| File:Line | Name | 為何不能刪 |
|---|---|---|
| `src/data/macro/leading_indicators.py:786` | `build_leading_indicators` | `test_provenance_smoke.py:75` assert `"TWSE+FinMind+TAIFEX:leading_indicators:full" in src` — 字串在 L819 函式 body 內,刪函式 = 刪字串 = test fail |
| `src/data/macro/macro_core.py:587` | `fetch_ism_pmi` | `test_provenance_smoke.py:99-118` assert 5 個 source 命名字串(`FRED:{sid}` / `MacroMicro:us-ism-mfg-pmi` / `ISM:ismworld.org` / `DBnomics:ISM/pmi/pm` / `ISM-PMI:all_7_stages_failed`)— 全在函式 body L622/653/689/727/808 |

→ 這 2 個 fn 是 §2.2 Provenance source 命名規約的「documentation as test」範例,
   deletion 會破壞 source naming convention 守衛。**保留**(屬 T2-c safety net 的特例)。

## ✅ False positive 3 處(升 T4 跨檔 live)

PR #406 audit 邏輯漏的(init re-export 邊界):

| File:Line | Name | 真實 caller |
|---|---|---|
| `src/ui/tabs/macro/section_short.py:20` | `render_section_short` | `tab_macro.py` |
| `src/ui/tabs/macro/section_chips.py:28` | `render_section_chips` | `tab_macro.py` |
| `src/ui/tabs/macro/section_summary_bar.py:17` | `render_five_bucket_summary` | `tab_macro.py` |

## 🟡 T2 剩 20 處 — prod dead test live(無自動可信判斷準則)

| File:Line | Name | test ref | 推測類別 |
|---|---|---|---|
| `src/compute/risk/risk_control.py:245` | `calc_position_size` | 1 | (b/c) — 風險管理 lib,safety net 可能 |
| `src/compute/risk/risk_control.py:248` | `calc_stop_loss` | 2 | (b/c) |
| `src/compute/macro/macro_helpers.py:612` | `calc_real_rate` | 5 | (c) lib safety net |
| `src/compute/macro/macro_helpers.py:641` | `classify_rate_cycle` | 6 | (c) |
| `src/compute/macro/macro_helpers.py:702` | `calc_twd_trend` | 5 | (c) |
| `src/compute/health/mj_snapshot_io.py:149` | `list_all_stocks_with_snapshots` | 2 | (b)? 若 mj 退役 |
| `src/compute/health/mj_health_diff.py:269` | `screen_health_changes` | 11 | (c) 高 test ref |
| `src/compute/scoring/scoring_engine.py:1175` | `check_contract_liability_surge` | 5 | (a/b) |
| `src/compute/scoring/scoring_engine.py:1194` | `check_bollinger_squeeze` | 5 | (a/b) |
| `src/compute/scoring/scoring_engine.py:1226` | `check_fake_breakout` | 3 | (a/b) |
| `src/compute/scoring/scoring_engine.py:1249` | `check_relative_strength` | 6 | (a/b) |
| `src/compute/scoring/scoring_engine.py:1296` | `calculate_position_size` | 6 | (a/b) |
| `src/compute/screener/fundamental_screener.py:199` | `screen_stocks` | 17 | (a) 高 test ref |
| `src/compute/screener/fundamental_screener.py:263` | `filter_passed` | 1 | (c) |
| ~~`src/ui/tabs/tab_macro_validation.py:28`~~ | ~~`render_history_validation_section`~~ | — | ✅ **v18.399 R6 真刪整檔**(780 LOC)— audit 翻案,UI 0 unique 邏輯;backend `macro_validation_tw` / `macro_signal_lookback_tw` / `multi_factor_optimization` + 12 backend test 全保留 |
| `src/data/macro/tw_macro.py:875` | `fetch_tw_market_snapshot` | 1 | (b)? |
| `src/data/macro/tw_macro.py:982` | `fetch_tw_cpi_yoy` | 6 | (c) |
| `src/data/macro/tw_macro.py:1011` | `fetch_tw_unemployment` | 2 | (b)? |
| `src/data/macro/tw_macro.py:1039` | `fetch_cbc_discount_rate` | 4 | (c) |
| `src/data/macro/tw_macro.py:1074` | `fetch_usdtwd_close` | 2 | (b)? |

**無自動可信判斷準則**:test ref 數無法區分 (b) abandoned vs (c) safety net,需逐個檢視 test 意圖 + production replacement 才能 decide。SSOT 工作流程要求嚴謹 verify,不批量刪。

## §-1 + SSOT debug workflow 對齊

按 user 新 SSOT debug workflow:

**Step 1 重現定位**:T2 候選 25 處 AST-strict 重 verify
**Step 2 SSOT 修復策略**:
- 2 處看似真 dead → 進一步 verify 發現 test source-string 保護(documentation as test)
- 20 處 prod dead test live → 無自動可信判斷,不批量刪
- 3 處 false positive 已正名升 T4
**Step 3 修復 + Regression test**:本回合無實際刪除(verify 階段)
**Step 4 自審**:
- 邏輯:test source-string 保護不在 AST audit 範圍,需手動 verify
- 邊界:T2 test ref 數 1-17 跨度大,無 cut-off 可用
- 效能:N/A(audit only)
- Debug:無需要修正,僅補認知
**Step 5 最終輸出**:本 audit 報告 + 0 LOC 刪除

## 最終結論

**T2 25 處全保留**:
- 2 處 test-source 保護(documentation as test)
- 3 處 false positive(正名)
- 20 處需 user 逐個判斷(無自動可信準則)

**累計 dead code 清碼結算**(到此 session 結束):
| PR | 內容 | LOC |
|---|---|---|
| #406 | fuzzy_get(dict 版)| -12 |
| #407 | ai_engine.py 整檔 | -654 |
| **累計** | | **-666 LOC** |

T2 處理:**0 LOC 新清**(自動處理 honest stop)。

## §-1 工作準則總結

dead code audit 已 5 輪深挖(舊 audit / 嚴格雙重條件 audit / AST-strict /
T2 verify / test-source 保護),最終真 dead 收斂到 ai_engine + fuzzy_get,
其餘候選都有合理理由保留(test 保護、source 命名規約、半 archive、safety net)。

**接下來 dead phase 不再主動推**,等 user 明示具體 fn 才動。
