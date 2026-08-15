# Batch A 交付 — 16 項零風險修正

> 依 `PROCESS.md` §3 三步法（Explore → Plan → Execute）與使用者核可的 Batch A 藍圖。
> **只改顯示層與保護層，不動任何判定演算法。**
> 交付日：2026-08-14 · 基準：`main` @ v19.192

---

## ① 邏輯審查

### 需求對照

| # | 提案編號 | 檔案 | 實際改動 |
|---|---|---|---|
| A1 | §F-2 / DIAG | `app.py` | 進階診斷 expander 加 `st.checkbox` gate，6 個 panel 改為 opt-in |
| A2 | §F-1 | `app.py` | 補 5 處 `_render_tab_isolated`（資料診斷 / ETF 單檔 / ETF 多檔 / ETF 組合 ×6 個渲染器） |
| A3 | §E-5 / V-SMART-CACHE-1 | `etf_tab_smart.py` | 5 個 inline TTL → `shared/ttls.py` 常數 |
| A4 | §L-8 | `.streamlit/config.toml` | 刪無效鍵 `enableMarkdownUnsafeHTML`；`logger.level` error → warning |
| A5 | §3-1 | `app.py` | `_TW_TZ_SB` → 既有 `_tw_now()`（L0 SSOT） |
| A6 | §L-1 | `app.py` | 刪硬編碼 `st.success('🟢 系統正常運作中')` |
| **A7** | **§P-1 / N-5** | **`etf_tab_single.py`** | **AUM 幣別 ×2 處：`B USD` → `億`** |
| A8 | §J-14 | `rs_leader_service.py` | `_market_context` 補「持平」第三態 + 精度對齊 |
| A9 | §3-5 | `section_when_buy_sell.py` | 刪 `_bb_near_up` 死碼 + `or float('inf')` 哨兵改顯式 None 守衛 |
| A10 | §J-8 | `section_psy_checklist.py` | 「禁止操作」去 `abs()`，負向另立急跌分支 |
| A11 | §E-2 | `section_dragon_alert.py` | 改用 `evaluate_leading_gates()`（SSOT 收斂）+ 刪 `except: pass` |
| A12 | §L-3 | `section_state.py` | 刪憑空的「台股與美股相關性 ~0.6」 |
| A13 | §I-5 / N-10 | `recalibrate_macro.yml` | `git diff` → `git add` + `git diff --staged` |
| A14 | §C-6 | `app.py` | 刪旌旗 `50` fallback + 修正錯誤的旌旗定義註解 |
| A15 | §L-4 | `app.py` | 刪「頁面底部有 AI 整合報告面板」錯誤指路 |
| **A16** | **§L-2 / J-3** | **`macro_buckets.py`** | **籌碼桶拿掉開發者註解與 Python 模組路徑** |

### 有無邏輯斷層
**無。** 三項在實作時**主動降級**，理由如下（見 §④）。

### SSOT 檢查（本次引入的每個符號都先確認既有位置）
| 引入 | 來源 | 確認方式 |
|---|---|---|
| `TTL_30MIN/1HOUR/2HOUR/1DAY` | `shared/ttls.py:27-31` | Grep 確認四個常數值與原 literal **完全相同**（1800/3600/7200/86400） |
| `_tw_now` | `app.py:32` 既有 import | Grep 確認已存在，非新增依賴 |
| `evaluate_leading_gates` | `section_financial_leading.py:35` | Read 確認回傳 `{'cl_pct','cx_pct','cl_lead','cx_lead','ratio_known'}`，同層 L5 import 不違反 §8.2 |
| `_render_tab_isolated` | `app.py:437` 既有 | 全站已用於 8 個 tab，本次擴用至 13 個 |

---

## ② 邊界測試（Edge Cases）

| # | 情境 | 預期行為 | 本次改動下的實際行為 |
|---|---|---|---|
| 1 | **`aum` 為 None / 0 / < 1e6** | 顯示 `N/A` 不顯示數字 | ✅ 條件 `if aum and aum > 1e6` 未動，僅換算式與單位改變 |
| 2 | **`bb2` 為 None（`calc_bollinger` 回 None）** | 不出布林訊號 | ✅ `_bb_ok` 為 False → `_bb_drop_out` 恆 False（原行為靠 `bool(bb2)`，等價） |
| 3 | **`bb2` 是 dict 但缺 `upper` / `ma`** | 不出訊號 | ✅ **改善**：原本會走 `inf`/`0` 哨兵 → 無條件 True；現為 `_bb_ok=False` → False |
| 4 | **大盤區間報酬 = ±0.04%** | 不宣稱漲也不宣稱跌 | ✅ 落入 `abs(ret) < 0.5` → 顯示「⚖️ 大致持平」，且精度改 `.2f` 不再印出 `-0.0%` |
| 5 | **大盤區間報酬 = -30% / +20%（既有測試 fixture）** | `is_down` 為 `True` / `False` | ✅ 遠在 ±0.5% 中性帶外，兩個測試斷言不受影響 |
| 6 | **`_surge_chk` 為 None（K 線不足）** | 列入「未評估」 | ✅ 分支未動 |
| 7 | **`_surge_chk` = -18%** | 應說「急跌」不是「追高」 | ✅ **修正**：原印「📈 漲幅 -18.0%…（追高風險）」→ 現印「📉 跌幅 -18.0%…（急跌…）」 |
| 8 | **`jingqi_info` 存在但缺 `avg`** | 不顯示旌旗均值 | ✅ **修正**：原印「旌旗均值 50%」→ 現不顯示（下游 `is not None` 守衛既有） |
| 9 | **`capital` ≤ 0 或 `cl2`/`cx2` 為 None** | 徽章不觸發 | ✅ `evaluate_leading_gates` 內部 `_ratio_to_equity_pct` 已處理（回 None → `*_lead` False） |
| 10 | **ETF 組合任一渲染器 raise** | 只該區塊顯示錯誤，其餘照常 | ✅ **改善**：原整段裸奔會白屏；現逐渲染器各包一次 |

---

## ③ 效能評估

| 項目 | 改前 | 改後 |
|---|---|---|
| 進階診斷 6 panel | 每次 rerun **無條件執行**（含 50+ 筆 HTML 拼接、多次 DataFrame 掃描） | 預設 **0**；勾選才執行 |
| `render_data_health_raw` 內的 per-ETF 外抓 | 隨 expander body 一起跑 | 一併被 gate 擋住 |
| ETF 三頁 | 無隔離，單一例外 → 整站白屏 | try/except 包裝，額外成本可忽略（O(1)） |
| TTL 常數化 | — | **零效能影響**（值完全相同，僅命名） |
| 其餘 12 項 | — | 純顯示層，無複雜度變化 |

**Streamlit Cache**：本次未新增任何 `@st.cache_data`；A3 只是把既有 5 個 decorator 的 `ttl=` 由字面量改為常數引用，快取行為完全不變。

---

## ④ Debug 與修正 — 三項主動降級（重要）

實作過程中發現藍圖裡有三項**不符合「零風險」定義**，已主動縮範圍並在程式碼中留註記：

| 項目 | 藍圖原訂 | 實際交付 | 為什麼降級 |
|---|---|---|---|
| **A11 OR→AND** | `dragon_alert` 改成 AND | **只做 SSOT 收斂，保留 OR** | OR→AND 會改變「🏆 龍頭預警」徽章的觸發率 = **行為變更**。同頁 `section_financial_leading:185` 用 AND 才寫「✅ 龍多確認」，兩者定義不一致是真問題，但統一方向需你裁示 |
| **A10 checkbox 邏輯** | 一併去 `abs()` | **只改標籤文案，邏輯不動** | `:180 value=` / `:182 disabled=` 目前在大跌時會**鎖住** SOP 第②關（保守方向）。去 `abs()` 等於**放寬一個安全閘**。改標籤為「漲跌幅未超過 ±X%」+ 補 `help=`，讓文案與行為一致 |
| **`import datetime`** | （未列） | **保留不刪** | A5 移除 `_TW_TZ_SB` 後，`app.py:2` 的 `import datetime` 成為孤兒（已 Grep 確認全檔零其他引用）。但刪除對使用者零價值，且在零風險批次裡「多動一行」不划算 → 留給 Batch A-2 清理 |

**未發現其他潛在 bug。** 所有 `# FIX:` 註記皆已寫入對應行上方，含原始寫法、為什麼錯、以及證據出處。

---

## ⑤ 最終代碼 — 異動檔案（8 個）

```
app.py                                              A1 A2 A5 A6 A14 A15
shared/macro_buckets.py                             A16
src/ui/etf/etf_tab_single.py                        A7
src/ui/etf/etf_tab_smart.py                         A3
src/services/rs_leader_service.py                   A8
src/ui/tabs/stock_sections/section_when_buy_sell.py A9
src/ui/tabs/stock_sections/section_psy_checklist.py A10
src/ui/tabs/stock_sections/section_dragon_alert.py  A11
src/ui/tabs/macro/section_state.py                  A12
.streamlit/config.toml                              A4
.github/workflows/recalibrate_macro.yml             A13
```

---

## ⑥ 測試影響

| 測試 | 斷言什麼 | 本次影響 | 需同 PR 改？ |
|---|---|---|---|
| `test_rs_leader_service.py:47` | `is_down is True`（fixture `market_ret=-0.30`） | 🟢 −30% 遠在中性帶外 | 否 |
| `test_rs_leader_service.py:65` | `is_down is False`（fixture `market_ret=+0.20`） | 🟢 +20% 遠在中性帶外 | 否 |
| `test_app_tab_wiring.py:47` | `with tab_X:` **字面**存在 | 🟢 五個 `with` 區塊全部保留，只在內部包 `_render_tab_isolated` | 否 |
| `test_c3_layering_guard.py:468` | `app.py → app_stock_fetchers` 白名單 | 🟢 **本次未刪該 import**（刻意留給 A-2） | 否 |
| `test_d1_stock_tab.py:309-353` | `evaluate_leading_gates` 行為 | 🟢 純函式本體未動 | 否 |
| `test_h2_naming_and_fake_readings.py:489` | `render_data_registry_panel` 的 expander 皆 `expanded=True` | 🟢 **本次未動該檔** | 否 |
| `tests/` 中 `_cached_price` 等 | — | 🟢 Grep 確認零命中 | 否 |
| **`test_d1_stock_tab.py:632`**<br>`TestRenderTextHonesty::test_dragon_alert_uses_ssot_thresholds` | 斷言 `section_dragon_alert.py` 的 AST 內**直接引用**兩個門檻常數 | 🔴 **實跑失敗** —— A11 改為委派 `evaluate_leading_gates` 後，本檔不再直接引用常數 | **是，已同 PR 更新** |

### ⚠️ 首輪實跑結果與修正（2026-08-14）

```
FAILED tests/test_d1_stock_tab.py::TestRenderTextHonesty::test_dragon_alert_uses_ssot_thresholds
1 failed, 5639 passed, 13 skipped, 34 deselected
```

**這是我的疏漏**：交付前只查了同檔的 `TestLeadingGates`，沒查 `TestRenderTextHonesty` ——
正是報告 §4.2 自己標記過的「source-string / AST 守衛」類型。

**修法選擇**：守衛的 docstring 寫明意圖是「50% / 80% 曾有**三份複本**」，也就是
**防止門檻值被複製**。委派 `evaluate_leading_gates` 讓「門檻值」與「判定式」都只剩一份，
比原本「各自 import 常數再各寫一次 `v / capital * 100 >= 門檻`」**更強**地滿足該意圖。
若沿用舊斷言，本檔會被逼著 import 兩個**用不到**的常數純粹為了過測試。

因此改為 **二擇一 + 新增負向檢查**（強度只增不減）：

| | 舊版 | 新版 |
|---|---|---|
| 正向 | 必須直接引用兩個常數 | 直接引用兩個常數 **或** 委派 `evaluate_leading_gates` |
| 負向 | **無** | **新增**：檔內不得出現 `50.0` / `80.0` 數值字面量（只掃數值 Constant，docstring 的「≥ 50%」是字串不算） |

負向檢查是舊版沒有的 —— 舊版只要 import 了常數就過，就算旁邊還留著一份 inline `>= 50` 也照樣綠燈。

**結論：本批共動 1 個測試檔，屬「程式碼 + 測試同 PR」的預期情形。**

---

## 你要做的三件事

```powershell
cd "D:\01.Github\20260813\股票"
pytest -q                      # 確認 5520 綠燈
git diff                       # 逐檔看改動（每處都有 # FIX: 說明）
```

確認沒問題後 commit + 開 PR。依 `PROCESS.md` §4，**任何一行 .py 邏輯變動 → 強制 PR**，並同步 `STATE.md`。

建議 PR 標題：
```
Batch A: 16 項零風險修正（AUM 幣別 / 診斷 gate / 隔離器 / TTL SSOT / 誠實性文案）
```

---

## 下一批的候選（等你決定）

1. **Batch S1 —— Q-1 session bug**（最高 ROI：一修消掉六個頁面的「總經未評估」假象）
2. **需裁示三項**：`dragon_alert` OR→AND、`psy_checklist` checkbox 是否放寬、`financial_health` 缺資料是否仍算 Pass
3. **Batch A-2 —— dead code 清理**：`primary_stock` / `import datetime` / 兩個 re-export shim（需同步 `test_c3_layering_guard.py` 白名單）
