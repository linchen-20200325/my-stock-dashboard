# my-stock-dashboard 全 Tab 重構提案報告 **v2**

> **狀態**：第一階段提案，**尚未修改任何一行程式碼**。等待逐 Batch 核可後才進入第二階段。
> **稽核基準**：本機 clone `main` @ v19.192（5520 tests passed）· 712 檔 · UI 層 82 檔 100% 覆蓋
> **產出日期**：2026-08-14（v1 同日稍早，本版為本機全文重跑）
> **團隊編組**：產品經理/UI-UX · 資深資安與資料稽核師 · 資深 Python/Streamlit 工程師 · 專業金融與投資分析師 · **＋ 測試與 CI 守衛稽核員（v2 新增）**
> 八組並行唯讀 Explore agent → 一組獨立驗證員交叉核對

---

## §0. 三輪校正紀錄（為什麼有 v2）

### 0.1 v1 的取檔方式有硬限制

v1 透過 CDN 抓檔，單次在 52–70KB 截斷、無法跨檔 grep。結果是 **6 處誤植 + 大量數字失真**。本機 clone 之後全部重跑，UI 層 82 檔逐檔讀完。

**三個外部來源的可信度實測**：

| 來源 | 狀態 |
|---|---|
| `raw.githubusercontent.com` | ❌ 落後約 5 週 |
| `api.github.com` Trees API | ❌ 落後約 5 週（`pushed_at` 自證） |
| `cdn.jsdelivr.net` | ⚠️ 檔案清單 JSON 可用；`.py` 回 octet-stream 讀不到 |
| `rawcdn.githack.com` | ✅ 內容正確（v1 後半段改用此來源） |
| **本機 clone** | ✅✅ **唯一可跨檔 grep、可精確計行的方式** |

**建議寫進 `PROCESS.md`**：AI 協作一律以本機 clone 為準；必須遠端取檔時用 `rawcdn.githack.com`。

### 0.2 v1 → v2 的 19 項修正（保留紀錄以示透明）

| # | v1 說法 | v2 實測 |
|---|---|---|
| 1 | `app.py` 約 1542 行 | **936 行**，top-level def 只有 2 個（`_get_secret:49`、`_render_tab_isolated:437`） |
| 2 | `tab_stock.py` 有 24 個 `####` marker | **1,876 行、12 個 marker**（其中 9 個在財報體檢 expander 內，主流程只有 3 個）。`render_tab_stock()` 佔 L134–1876 ≈ 93% |
| 3 | `_render_tab_isolated` 覆蓋 8/14 | **8/13**（葉節點 tab 是 13 個）。未包 5 個：選股網 L485、ETF ×3 L714/726/730、資料診斷 L773 |
| 4 | 進階診斷 6 panel 每 rerun 打外部 API | ⚠️ **6 個 panel 本身無網路 I/O**（雙跑實測、回測皆 button-gated）。**但 `health_inspector.py:1425` 的 per-ETF 迴圈確實在 `if _do_deep:` 區塊之外**，每次 render 對每檔主動 ETF 打 MoneyDJ + 持股 → 真問題在這裡，不在 expander |
| 5 | `unified_indicator_card` 不存在 | ❌ **存在**，在 `src/ui/render/macro_ui_components.py:317`，`section_mid.py` 呼叫 10 次，有 `test_unified_indicator_card_v19_109.py` 9 個測試釘住。v1 兩次都判錯（先說有、再說沒有），**正解是「它不在 ui_widgets.py，且只接了總經中期一個 section」** |
| 6 | `config.toml` 的 `[logger] level="error"` 掩護了 CORS 警告 | ❌ 不成立。實機 `ring1_report.txt` 兩條警告都印出來了。但 `enableMarkdownUnsafeHTML` **確實是無效鍵**（實機輸出 `is not a valid config option`） |
| 7 | `except: pass` 全站約 54 處 | **61 處**（`src/ui` + app.py）。`tab_stock.py` 是 **22 處**（v1 說 15）、`section_chips.py` 6、`health_inspector.py` 6、`section_portfolio_summary.py` 6 |
| 8 | `bias_240` 四個消費點沒一個用 SSOT | ⚠️ `section_warroom.py:38` **有用**（`_BIAS240_RED = float(_SPECS_BY_KEY['bias_240'].red)`）。其餘三處確實 inline |
| 9 | 熱力圖口徑 caption 位置錯誤 | ❌ 不成立。`etf_render.py:811-815` 位置合理（選完區間後、看圖前）且內容精準，是本範圍**寫得最好的揭露文案**。真問題只有「面積≈權重」那句假話 |
| 10 | `etf_margin_simulator.py` 是孤兒模組 | ❌ 該檔**不存在**，v18.464 移除得很乾淨 |
| 11 | 資金潮汐 ETF 桶與半導體「重複計算」 | ⚠️ 應為「**經濟意義重疊**」。`compute_sector_daily_net` 是 per-stock 加總，0050 與 2330 是不同 `stock_id`，法人淨額不會被算兩次 |
| 12 | forward_test 1 年基準窗會靜默劣化 | ⚠️ 確有 1 年窗限制，但下游 `n_cohorts_no_bench` **有 note 揭露** → 屬「誠實但功能受限」 |
| 13 | `_ws()` 正確選擇不加 cache | ⚠️ 措辭要改：`src/data/portfolio/` 全層 `cache_data|cache_resource` **0 命中**。「沒踩 pickle 地雷」是整層無快取的副產品，不是設計選擇 |
| 14 | `section_kline_chart` 的 `total: 0` 會寫進 parquet 持久化 | ❌ 只寫 `session_state`。`health_history_service` 無寫入函式，parquet 由 cron 產出。**但仍會與 cron 的真實列混在同一個 list** |
| 15 | `risk_control` 4 個函式全空轉 | ⚠️ `portfolio_exposure` / `check_portfolio_limits` / `RiskController` **都有 caller**。只有 `atr_stop_price` / `stop_loss_trigger` / `trailing_stop_trigger` 無外部 caller |
| 16 | 「禁止操作」的漲幅門檻是 15% | ❌ `SOP_BAN_SURGE_PCT = **4.0**`（`signal_thresholds.py:1039`）。所以近 5 日跌 18% 會印「📈 漲幅 -18.0% 超過 **4%**（追高風險）」，且 `:182` 會把 SOP 第②關 `disabled` 鎖死 |
| 17 | D2 的 I6 恆未評分卻計入分母 | ❌ `section_d2_leading.py:197` **已正確排除**。真問題是 `stock_buckets.py:213` 標題寫「六大」但三個數字加總永遠 ≤5，且模組四的說明描述了一個沒實作的東西 |
| 18 | `Sahm_Rule_Triggered` 在 `section_cross_ai.py` | ❌ 在 **`section_news_ai.py:230`**。`section_cross_ai.py` 已於 v19.183 用 `_num()` 修好，**反而是正面案例** |
| 19 | `_macro_session_reset` 漏清 8 個 key | ⚠️ 實測**漏清 16–18 個、已清 10 個**（清單裡的 `futures_net` 是死 pop，全 repo 無寫入端）。**未清數多於已清數** |

### 0.3 v2 的 14 條全新發現（v1 完全沒抓到）

排在最前面的，是本次最嚴重的一條。

| # | 發現 | 嚴重度 |
|---|---|---|
| **N-1** | **`scoring_helpers.py:160-162` 無 MA 數據時 `score += 15`** —— 趨勢是 6 因子中權重最高（30/100），新上市股 MA100 未成形時**憑空拿到滿分的一半**。畫面顯示「趨勢 − 無MA數據」（誠實），但分數裡已含這 15 分 → 趨勢未知的股票健康度天花板是 85 而非 70 | 🔴🔴 |
| **N-2** | **薩姆規則是幽靈把關**：`section_traffic_light.py:101-103` 對使用者宣稱「🔒 風險上限＝薩姆／PMI／外資期貨／VIX 否決權／三環第一環」，但 (a) `Sahm_Rule_Triggered` 恆 `False`；(b) `allocation_service.py:152` 的 `_INTRINSIC_CAP_NAMES` **只有** `{'VIX 否決權','三環第一環'}`，薩姆／PMI／外資期貨**三條 cap 根本沒註冊**；(c) 全 repo `grep -i sahm` 在 allocation_service 零命中 | 🔴 |
| **N-3** | **`calculate_system_state` 全缺值自動吐「曝險 60%」**：`macro_state_locker.py:476-518` 的 `vix→20.0 / pmi→50.0 / m1b,m2→0.0 / bias→0.0 / pcr→1.0`，零資料代入後所有分支都不觸發 → `exposure = 60`。§1「錯誤的數字比沒有數字更危險」的教科書案例 | 🔴 |
| **N-4** | **`etf_fetch.py:214` 對原始 OHLCV 靜默 `ffill()`**，且同一檔 `:1960-1962` 才剛寫明「移除原 `close.ffill()`：把『沒有交易』偽裝成『持平』，§4.6 明文禁止」。而 `_fetch_etf_price_max` 是**全 ETF 頁唯一的價格來源** | 🔴 |
| **N-5** | **AUM 幣別的第三處問題在評分層**：`etf_quality.py:54-55` / `etf_scoring_helpers.py:36` 以 **TWD 10億/100億** 為刻度，卻直接吃 `info['totalAssets']` —— 美股 ETF 該欄是 **USD**。一檔 $8 億 USD（≈250 億台幣、規模健康）的美股 ETF 會被算成 `log10(8e8)=8.9` → **AUM 得 0 分** | 🔴 |
| **N-6** | **`health_inspector.py:1425-1478` 的 per-ETF 迴圈在 `if _do_deep:` 之外**（縮排 16 vs 20 空格），只要 `etf_portfolio_data.rows` 非空就每次 render 打 MoneyDJ + 持股。另 `:1264` 與 `:538` 同型 | 🔴 |
| **N-7** | **`_get_worksheet:225` 純讀也會覆寫使用者 Sheet 第 1 列**：`ws.update(f'A1:{...}1', [headers])`，而 `list_portfolios`（純讀）會走到這裡。使用者自己改過標題列，光是打開組合管理頁就被改掉，無任何提示 | 🔴 |
| **N-8** | **OAuth 三重風險**：`oauth_state.py:133-135` 的 state 檢查是 **fail-open**（docstring 自列真值表：`expected=None, got=ABC → True`）；`infra/oauth.py:86-88` id_token **不驗簽**直接 base64 解 payload；`:139` 把整個 token response dict 塞進例外訊息，再由 `oauth_state.py:168 st.error(...)` **渲染到畫面** | 🔴 |
| **N-9** | **`test_financial_health_engine.py:98-111` 把 bug 釘成規格**：註解即宣言 `# ── All items N/A → rule_st="Pass" (no data is not a fail) ───` + `self.assertEqual(rule["Status"], "Pass")`。**全空財報得 Pass**，與 §1 直接衝突 | 🔴 |
| **N-10** | **`recalibrate_macro.yml:59` 是全 repo 唯一的錯誤變體**：用 `git diff --quiet`（看不到 untracked 檔），其餘 7 個寫入型 cron 全用 `git diff --staged --quiet`（已先 `git add`）。且 `MACRO_CALIBRATION_PROPOSAL.md` 在 repo 內**不存在也不在 .gitignore** → 兩個 pathspec 皆無 diff → **PR 永不開啟** | 🔴 |
| **N-11** | **cron 撞車 + 零告警**：`update_health_history`（`30 9 * * 1-5`）與 `update_sector_flow`（`30 9 * * *`）平日**同一分鐘**啟動、push 同一分支；`update_macro_history`（`0 9`）與 `push_daily_signals`（`0 9`）亦同刻。所有 commit 步驟皆為裸 `git push`，**無 `git pull --rebase`、無 `concurrency` group**。而 15 個 workflow **全部沒有 `if: failure()` 通知** → 資料管線壞掉是零告警 | 🔴 |
| **N-12** | **`scoring_engine` 一整排「缺值回 50」被測試釘成規格**：`calc_rs_score(None)==50`、`calc_chip_score(None)==50.0`、`calc_revenue_yoy_score(None)==50.0`、`calc_volume_score(None)==50.0`、`calc_trend_score(None)==0.0`（缺值被報成「最差趨勢」）、`score_single_stock(None)["total"]==0`、`test_none_df_returns_fixed_8pct`（零筆歷史仍回具體停損價 92.0）。同 repo 另有 `test_b1b_stock_math.py:330` 的正確慣例「缺資料必須回 None，不可回 0」→ **兩套互斥慣例並存** | 🔴 |
| **N-13** | **`etf_tab_smart.py:309` 的分散度混用 2 維與 3 維分數直接比大小**：`_tickers_to_fetch = [_ticker] + _peers_in_pivot[:30]`，但 universe 約 48 檔 → 第 31 檔起 `holdings_map` 為空 → 權重 rescale 成 2 維。**更糟的是 `:403` `_d.drop(columns=['可用維度'])` 把唯一能看出差別的欄位刪掉** | 🟡 |
| **N-14** | **`test_c3_layering_guard.py` 品質很高，但兩條待修違憲被白名單放行**：V-PICKER-PRIV-1（`:506` 登記在 EX-PASSTHRU-1，但憲法 §8.2.A.1 明文「⚠️ 明確排除…private symbol」）、V-LEAD-RENDER-1（`:413` 列在 EX-CACHE-1，但該檔真正問題是 L1 內定義 render 函式，守衛只看 import 看不到）。**機器可讀 SSOT 與憲法文字互相矛盾，且是機器這邊放水** | 🟡 |

### 0.4 附帶：路徑與檔案結構更正

- 稽核文件已移入 `docs/`（`docs/APP_PY_AUDIT.md` 等），根目錄只剩 `ARCHIVED_FEATURES.md` 一份重複
- 新增檔案：`mcp_server/`、`references/gotchas.md`、`MACRO_HEALTH_REWEIGHT_PROPOSAL.md`、`MACRO_HEALTH_WEIGHT_PROPOSAL.md`
- ⚠️ **命名陷阱**：`src/compute/strategy/portfolio_manager.py` 與 `src/ui/tabs/portfolio_manager.py` **同名不同檔**

---

## §1. 全站 Tab 地圖（本機實測，附 `app.py` 行號）

```
📊 台股 AI 戰情室（app.py 936 行）
│
├─ L64-77   讀 secrets → 寫 os.environ           【全域副作用①】
├─ L82-83   st.set_page_config(sidebar='collapsed')
├─ L85-91   OAuth callback（可 st.success/error/rerun）【副作用②】
├─ L93-115  query_params ⇄ session 雙向同步（含 except: pass）【③④】
├─ L117-129 全域 CSS 注入                        【副作用⑤】
├─ L203-336 Sidebar 區塊 A（6 個互動元件 + 假綠燈 L217 + 免責 L336）
├─ L346-359 Sidebar 區塊 B（強制刷新 L347 + 資料健康 L356）← 順序倒錯
├─ L362-366 主標題 + v3.0 badge（實際碼版 v19.192）
├─ L381     _core_summary_slot = st.empty()      ← 核心總表佔位
├─ L387-388 render_macro_compass()               ← 三卡全美股、無時效閘
├─ L393-395 st.tabs 6 群組
├─ L419     _gl_slot = st.empty()                ← 置底條佔位
│
├─ 🌍 市場環境 L451-469          隔離器 3/3 ✅
│   ├─ 🌍 總經         L455  tab_macro.py + macro/ 15 檔（23 段）
│   ├─ 🗺️ 產業熱力圖   L459  render/etf_render.py::render_sector_heatmap
│   └─ 🌊 板塊資金潮汐 L465  tab_sector_flow.py + L3 sector_flow_service
│
├─ 🔬 選股 L474-700              隔離器 2/3 ⚠️
│   ├─ 🔬 個股         L477  tab_stock.py(1876行) + stock_sections/ 13 檔（14 個渲染單元）
│   ├─ 🏆 個股組合     L481  tab_stock_grp.py + stock_grp_sections/ 6 檔（12 段、8 表、~70 欄）
│   └─ 🔭 選股網   L485-700  ❌ inline 216 行在 app.py（違憲 V-APP-1）、未包隔離器
│
├─ 🏦 ETF L709-765               隔離器 0/3 ❌
│   ├─ 🔍 單檔診斷     L714  etf_tab_single.py(960行) 26 段 + smart hook ×3
│   ├─ 📊 多檔比較     L726  etf_tab_grp_compare.py(316行) 8 段
│   └─ ⚖️ ETF 組合     L730  etf_tab_portfolio.py(1825行) 24 段 + 葡萄串 + smart ×3 + AI
│
├─ 🔧 工具箱 L770-802            隔離器 1/2 ⚠️
│   ├─ 🔎 資料診斷     L773  ❌ render_data_coverage 常駐 + 6 panel expander(L785-798)
│   └─ 📚 教學         L800  tab_edu.py + macro_classroom（6 expander 全展開）
│
├─ 📁 組合管理 L805-807  ✅       portfolio_manager.py（0 expander、8 處 st.rerun）
├─ 🧬 AI 問答  L810-812  ✅       tab_ai_chat.py(145行) + L3 ai_qa_service
│
├─ L832-853 核心總表填充 → 寫回 _core_summary_slot
├─ L866-933 置底條填充 → 寫回 _gl_slot（❌ 無隔離器保護）
└─ L935     頁尾免責
```

**診斷單元合計 15 個**（6 主頁籤 + 11 次頁籤去重後 13 個渲染面 + 全域骨架 + Sidebar），本報告 §3 逐一涵蓋。

---

## §2. 橫向結構性問題（跨 Tab，建議優先於個別 Tab 修）

以下 9 條的影響面遍及所有 Tab，同時是後續每個 Tab 改善方案的共同基礎設施。**每個數字都以本機 Grep 精確計數，附 pattern 可複現。**

### 🔴 H-1｜「不知道」被寫成「中性 / 0 / 50 / Pass」—— 本案最核心的病灶

你在 v19.192 已經修掉**散文層**的「中性」逃生口（`ai_qa_service` 第 3-1 條），但**數值層仍是系統性的**。實測分布：

| 位置 | 原文 | 後果 |
|---|---|---|
| **`scoring_helpers.py:160-162`** | `else: score += 15; details['趨勢'] = ('無MA數據', 15, 30)` | **權重最高的因子憑空給半分**（N-1） |
| `macro_state_locker.py:476-518` | `vix→20.0 / pmi→50.0 / m1b,m2→0.0 / pcr→1.0`，`score=60` 基準 | **全缺值 → 自動吐「曝險 60%」**（N-3） |
| `section_news_ai.py:230` | `'Sahm_Rule_Triggered': False` | **「無資料源」寫成「衰退未觸發」**（N-2） |
| `section_state.py:157-165` | `_m1b2.get('m1b_yoy', 0)` | 只缺 m2 時 `_diff` 必為正 → 印「M2(0.0%) 黃金交叉」 |
| `section_mid.py:130/214/299/301/307/368` | 同一個 PMI key 兩個預設（50 與 55）、VIX 缺值 → 0 → 印「VIX 0 — ✅ 市場平靜」🟢、NDC 同 key 兩個預設（0 與 25） | **同檔內互相打架**；`:301` 的否決權**永不觸發** |
| `section_short.py:123/208/282` | `ad_ratio` 缺值補 **50**（含一處 `fillna(50)`） | 50 恰為榮枯線 |
| `handlers.py:103,125` | `_mi.get('index_price', 0)` | 畫面印「加權指數 0」 |
| `section_op_recommendation.py:92-110` | `'score': 0` + bias/m1b/cl/cx/外資投信全 0 | **`app_ai_service.py:296` 的「🚀 強烈買入」分支對任何股票永遠不可能觸發** |
| `financial_health_engine.py` 5 處 | `else 50`（全 N/A 給 50 分）、`cl==0 → "Pass (無短期債務)"`、`ppe<=0 → ("Pass","N/A")`、100-100-10 全 N/A → `"Pass"`、radar `_score` 保底 **20** | 全空財報落在「🔵 財務穩定，中規中矩」 |
| `section_financial_health.py:347-349` | `Cash_Gap_Days` 缺失濾成 `'0'` → `<=0` → `TRAFFIC_GREEN` | 假綠燈 |
| `section_batch_fetcher.py:263-270` | `'名稱':'失敗', '健康度': 0`（**全檔唯一無 log 的 except**） | 0.0 非 None → **不進 `health_unknown_ids`，直接進 `eliminated`**，並拉低 KPI 平均、進 AI prompt。整套三態架構被這一行擊穿 |
| `etf_calc.py:698/674/682` | `if len(ret) < 20: return 0.0`（夏普）、`days < 30: return 0.0`（CAGR） | **拿到最低分並佔用權重**，而非 `None` 走既有 rescale → 新上市 ETF 系統性低估 |
| `etf_tab_single.py:605` | RSV `.fillna(50)` | 停牌/連續跌停被當中性 50，並進 AI prompt |
| `app.py:870` | `_jq_top.get('avg', 50)` | 印「旌旗均值 50%」；且 `section_overview.py:63-72` **已把同一件事判為 §1 違憲並修好**，app.py 是漏網第二處 |

**方案**：統一改 `.get(k)` + `is None` → 顯示 ⬜ 並標「未評估」。
**現成範本就在 repo 內**：`section_cross_ai.py:58-69` 的 `_num()`（v19.183）、`tab_stock_grp.py:691-838` 的 `split_trend_rows` 三態表、`core_summary_service._safe()`（失敗回**例外物件本身**而非 None，下游才能區分 ⬜未評估 / ❌取數失敗）。

> ⚠️ **這一條有測試阻力**，見 §4：`financial_health_engine` 的「全 N/A → Pass」與 `scoring_engine` 的一整排「缺值回 50」**都被測試釘成規格**。屬政策決定，不是單純 bug fix。

### 🔴 H-2｜靜默吞例外 330 處，只有 9.4% 會讓使用者看見

Grep `except` 於 `src/ui` → **330 處 / 58 檔**：

| 型態 | 次數 | 占比 |
|---|---|---|
| `except …: pass` | **61** | 18.5% |
| `except …: continue` | 5 | 1.5% |
| `except …: return 預設值` | 46 | 13.9% |
| **`except` 內有 `st.error/warning/info/exception` 或 `raise`** | **31** | **9.4%** |

**🔴 級（吞掉後畫面仍顯示結論）已實證 11 處**，共同特徵是「錯誤被翻譯成一個合法的畫面狀態」：

```
section_chips.py:409/431/447/462/487   ← 5 塊各包一條「警示」的產生邏輯
  → 任一炸掉 = 畫面呈現「今天沒有這條警示」= 使用者讀到錯誤的市場結論
tab_stock.py:110/115/120/129           ← _precompute_xsec 四連裸吞（籌碼/RS/股本/先行指標）
tab_stock.py:1587/1612                 ← AI prompt 的估值/財報段組裝（AI 少一段輸入仍照常出結論）
```

**正面範本**：`portfolio_manager.py` 9 處 except **全部** `st.error/warning`，零 `except: pass` —— 全站 fail loud 最徹底。

### 🔴 H-3｜Streamlit 的兩個「以為不會執行、其實會執行」陷阱

**陷阱 A：`st.tabs` 是 eager render** —— 切換 tab 只是前端 CSS，每次 rerun 執行全部 13 個葉節點 tab 的 Python。使用者在「AI 問答」打一個字，總經/個股/ETF/診斷頁全部重跑。而 `_render_tab_isolated` 只是 try/except **與延遲渲染無關**，且覆蓋率 8/13。

**陷阱 B：`st.expander(expanded=False)` 只收合視覺**：
- `section_state.py:456-462` 的 30 年 ^TWII + FRED 回測，每次 rerun 都跑
- `etf_tab_portfolio.py:1737` 的 `_render_cloud_storage` → `list_portfolios()`（無快取）
- `health_inspector.py:1425-1478` 的 per-ETF MoneyDJ 迴圈（**且它連 expander 都不在**，是 `if _do_deep:` 外的漏縮排）

**方案**：
1. 5 處補 `_render_tab_isolated`（30 分鐘）
2. 三個最重的頁導入延遲載入器：
```python
def _lazy_tab(container, key, render_fn, label):
    with container:
        if st.session_state.get(f'_tab_seen_{key}'):
            _render_tab_isolated(render_fn, label)
        else:
            st.info(f'點下方按鈕載入「{label}」')
            st.button(f'▶ 載入 {label}', key=f'_load_{key}',
                      on_click=lambda: st.session_state.__setitem__(f'_tab_seen_{key}', True))
```
3. 重運算一律 button/checkbox gate

### 🔴 H-4｜`macro/handlers.py` 是隱形全域 store，且「一鍵更新」只清不到四成

全站相異 session_state key **≥ 90**（497 個存取點）。`_macro_session_reset`（`handlers.py:21-25`）清 **11 個**，其中 `futures_net` 是**死 pop**（全 repo 無寫入端）→ **實際有效清除 10 個**。

**未清的 macro 相關 key 實測 16–18 個**：`macro_info`、`m1b_m2_info`、`bias_info`、`macro_alerts`、`macro_state`、`li_retain_meta`、`intl_snap`、`ma_snap`、`_pivot_signals`、`_ndc_hist_cache`、`_ndc_li_cache`、`_fi_streak_cache`、`_s10_prev_pmi_value`、`_macro_ai_report`、`_macro_ai_ts`、`_macro_news_items`（+ 邊界兩項）。

**未清數多於已清數。** 其中 `macro_info` / `bias_info` / `macro_state` **直接參與燈號與持股比例判定** → 使用者按了「🚀 一鍵更新全部數據」，畫面卻混合新舊資料，正是 `handlers.py:88` 自己警告的「新舊資料混雜誤導決策」。

另有三個 session 快取（`_ndc_hist_cache` / `_ndc_li_cache` / `_fi_streak_cache`）**連「🆕 強制重抓」也清不掉** → 只要 session 不重啟，永遠是第一次抓到的值。

**跨 Tab 讀寫最危險的三把**：

| key | 寫入 | 讀取 |
|---|---|---|
| `cl_data` | `macro_helpers`(**L2**)、`section_short`(L5)、`health_inspector`(L5)、L3 orchestrator | **12+ 點跨 4 大 Tab 群** |
| `li_latest` | `macro_alert`(**L1**)、`tab_macro`(L5)、shared × 2 | **L1·L3·L5 三層同時寫同一把 key** |
| `macro_state` | `section_traffic_light`(**L5**) | `shared/scoring_regime_gate`(**L0**) ← **L0 讀 L5 寫的值** |

**方案**：① 立即把 key 清單抽成 `shared/MACRO_SESSION_KEYS` frozenset + 加測試釘「所有 macro 域 key ∈ 清單」；② 中期改 `MacroSnapshot` dataclass + 存取器（讀不到就 raise）。
⚠️ **但 `macro_alerts` 不能補進 reset**，見 §4（有測試明文禁止）。

### 🟡 H-5｜名詞說明的基礎設施完備，接線量為零

**你不需要造輪子，輪子已經造好了**：

| 符號 | 定義 | production 呼叫 |
|---|---|---|
| `TERM_EXPLAIN` | `ui_widgets.py:162+181`，**15 個名詞** | — |
| `show_term_help(term)` | `:233` | **3 次，全在 `app.py:188` 同一行**，結果存進 `_TERM_HELP_LI` → 全 repo 僅此 1 行 → **死碼，畫面從未渲染** |
| `explain_box()` | `:197` | 0（僅被 `show_term_help` 內部呼叫） |
| `beginner_kpi()` | `:220` | **2 次**（皆在 `section_overview.py`） |
| `BREADTH_TERMS` | `:121`，4 個 NamedTuple（含 `evidence` 存 file:line 供覆核） | 集中在 `section_overview` / `macro_classroom` |
| `kpi()` | `:241` | **50+ 次**，但簽名 `kpi(title, value, sub, color, border)` **無任何參數可掛 tooltip**，回傳的 HTML 也沒帶 `title=` |
| `unified_indicator_card()` | **`macro_ui_components.py:317`** | **10 次，只在 `section_mid.py`** |

`help=` 覆蓋率：全站 **91 處**（src/ui 88 + app.py 3）/ 控制項 79 個。但 **`st.metric` 28 處只有 4 處帶 help → 覆蓋率 14.3%**。

零 help 的重災檔：`section_financial_health`（4 metric / 0）、`chip_radar`（3 / 0）、`section_psy_checklist`（3 / 0）、`section_mid`（0）、`section_chips`（0）、選股網 216 行（0）、`tab_edu` + `macro_classroom`（0）、`tab_ai_chat`（0）。

**方案（投報率最高的一項）**：
1. 刪 `app.py:188` 死碼
2. **`kpi()` 加 `term=''` 參數**，內部查 `TERM_EXPLAIN` 產生 `title=` HTML 屬性 → **一次改動覆蓋 50+ 張卡**
3. 擴充 `TERM_EXPLAIN` 到 ~60 詞（白話文案見 §8 附錄，已備妥）
4. 28 處 `st.metric` 補 `help=`
5. 加 CI 守衛：`st.metric` 無 `help=` 即失敗
6. Sidebar 加「🔰 新手白話模式」toggle

### 🟡 H-6｜RWD：全站 `overflow-x` 出現 **0 次**

`st.columns(` **126 處 / 37 檔**，其中硬編 N=4 有 17 處、N=5 有 5 處、N=6 有 1 處（`tab_stock.py:219` 六欄均線列，全站最寬）。`min-height` 固定值 7 處。

**N≥4 且含固定 min-height 的高風險組合**：`macro/helpers.py`（5 欄×104px、4 欄×150px）、`section_warroom.py`（5 欄×108px）、`grape_ladder.py`（4 欄×80px）。

**自繪表格 14 處，13 個無 `overflow-x`**（最寬 7 欄，`health_inspector.py:684`）。唯一正確的是 `core_summary_render.py:104` 的 `repeat(auto-fit, minmax(...))` —— **可直接當修法樣板**。
> ⚠️ 2026-08-25:該檔已隨核心總表整組刪除。樣板寫法本身仍有效,但要看原文請查 git history(`git show 31a1924:src/ui/render/core_summary_render.py`)。

**寬度 API**：`use_container_width` **132 次**（已 deprecated）vs `width='stretch'` **32 次** → 舊 API 佔 80.5%，5 檔同檔混用。`st.dataframe` 47/47、`st.plotly_chart` 41/41 **零缺漏**（很好），破口全在 **15 個 `st.button` 沒帶寬度**。
Streamlit pin 是 `>=1.36.0,<1.60.0`；`st.experimental_*` / `st.cache` / `.applymap` 全站 **0 次** → 相容性風險高度集中在單一 API、可機械化批次替換。

### 🟡 H-7｜色彩 SSOT 只涵蓋紅綠燈，版面色 731 次裸寫

硬編 `#xxxxxx` 全站 **925 次 / 57 檔**（`tab_stock.py` 88、`macro_ui_components.py` 58、`etf_render.py` 42…）。

`shared/colors.py` 只有 **8 個純量 hex**（5 TRAFFIC + 3 MATERIAL）+ 3 個容器。⚠️ **`COLORS_7`（L49-52）自己夾帶 5 個未 SSOT 化的裸 hex** —— 色票 SSOT 檔自己違反 §3.3。

- 「已有 SSOT 卻仍被裸寫」：精確 **14 處 / 6 檔**
- **真正的大宗**：16 個 GitHub 深色調色盤（`#8b949e` ~130、`#c9d1d9`、`#0d1117` vs `config.toml` 的 `#0e1117` 差 1 碼並存…）**731 次 = 81%，一次也沒進 colors.py**

`border-left` banner **64 次**，扣掉 helper 定義內 16 次 → **consumer 端 inline 48 次**，而 `border_left_banner()` 實際只被呼叫 **10 次 → SSOT 覆蓋率 17.2%**。`alert_box()` 與 `traffic_light_card()` **production 呼叫 0 次**（死 helper）。
⚠️ `section_header` 確實同名不同簽名：`tab_sections.py:76`（0 production 呼叫）vs `macro_ui_components.py:197`（9 次）。

### 🟡 H-8｜三套 TTL 體系並存

UI 層 `@st.cache_data` **11 個**：6 個走 `shared/ttls.py` ✅、**5 個全在 `etf_tab_smart.py` 且全是 inline literal**（1800/3600/3600/7200/86400，五個值在 `shared/ttls.py` 都有一模一樣的常數）→ **45.5% 違規率，100% 集中在一檔，5 行 import 即結案**。

第三套是 `shared/app_cache.py` 的 pickle 層（單位「小時」）：`ttl_hours=4`（`section_batch_fetcher` / `section_portfolio_summary`）、`0.5`（`app_stock_fetchers`）、預設 `6` —— **三個數字都沒有 SSOT 常數**。

### 🔴 H-9｜CI 守衛的實際強度遠低於「5520 tests passed」給人的印象（v2 新增面向）

| 項目 | 實測 |
|---|---|
| `pr-check.yml:39` | `pytest -v`（吃 `pytest.ini` 的 `-m "not slow"`） |
| **lint** | ❌ `:36` 裝了 pyflakes **但沒有任何執行步驟**；全庫 `ruff.toml`/`pyproject.toml`/`setup.cfg` **皆不存在** → 沒有設定檔就沒有 gate |
| **coverage 門檻** | ❌ 未找到 |
| **slow lane** | `:49 continue-on-error: true` → 24 個 AppTest **永遠不阻擋 merge**，只是 informational |
| **網路封鎖** | ❌ `conftest.py` 無任何網路 mock，`addopts` 只有 `--strict-markers -m "not slow"` → **架構上沒有東西阻止測試打外網**（個別測試自律良好，441 處 patch） |
| **cron 失敗告警** | ❌ 15 個 workflow **全部沒有 `if: failure()`** |

**方案**：`addopts` 加 `--disable-socket --allow-unix-socket`；CI 加 ruff step（先只跑 `src/`）；cron 補 `if: failure()` 通知 + `concurrency` group。

---

## §3. 逐 Tab 診斷與提案

> 格式依指定：**1. 現狀診斷（資料稽核／UI-UX／程式碼）→ 2. 改善方案（新手友善化／排版瘦身／進階分析保留）→ 3. 程式碼重構建議**
> 嚴重度：🔴 高（資料錯誤／誤導投資決策／嚴重效能）｜🟡 中（體驗差／技術債）｜⚪ 低｜✅ 正面案例

---

### 📌 3-1【全域】版面骨架 + Sidebar（`app.py` 936 行、`app_render.py`、`core_summary_render.py`、`app_cache.py`、`config.toml`）

#### 1. 現狀診斷與問題點

**資料稽核問題**
- 🔴 **旌旗均值雙重造假**（`app.py:870` + `:919` + `:341`）：`_jqpct = _jq_top.get('avg', 50)` 缺 key → 憑空印「旌旗均值 50%」；且 L341 註解沿用已被 `section_overview.py:63-72` 正名退役的錯誤定義（該處已判為 §1 違憲並改成 `.get('avg', None)`）。**app.py 是漏網的第二處**。
- 🔴 **`st.success('🟢 系統正常運作中')`（`:217`）零關聯**：下方 `:287-300` 明明已有 FinMind / Gemini / Proxy 三顆真燈，這句卻在其**上方**無條件先蓋一句綠。三源全紅時使用者第一眼仍看到綠。
- 🟡 **健康卡缺值與 0 分同形**（`app_render.py:65-68`）：`sc = fs.get('score', 0)` + `_sc_cl[0]` 灰色。
- 🟡 **`🔍 測試連線` 全域關閉 TLS 警告**（`app.py:313-314`）：`_ul3.disable_warnings(...)` 是 process-wide 副作用，按一次之後全站所有 `verify=False` 請求都不再警告。
- 🟡 **pickle cache 資安 + 半寫檔**（`app_cache.py:31` / `:63-67`）：`makedirs` 無 `mode=0o700`（`/tmp` 預設 0755，多租戶主機上 `pickle.load` = RCE 面）；`except: pass` 留下截斷檔 → 之後每次 load 失敗（同樣靜默）→ 快取實質失效且無人知。
- ⚠️ 2026-08-25:`core_summary_render.py` / `core_summary_service.py` 已隨核心總表整組刪除,以下評述僅存追溯價值。
- ✅ **`core_summary_render.py` 是本範圍最佳實踐**：全檔零 I/O、零 session_state 讀取；`_hex()` 特別為 🟠 補色，註解寫明「不補這條會被退成灰 → 使用者分不出『轉守』和『還沒算』」；`core_summary_service._safe()`（`:81-92`）失敗回**例外物件本身**而非 None，下游才能區分 ⬜未評估 / ❌取數失敗。**建議把這套三態模型當全站樣板**。

**UI/UX 與操作體驗問題**
- 🔴 **`initial_sidebar_state='collapsed'`（`:83`）+ 6 個關鍵控制項全在 Sidebar**：登出 `btn_oauth_logout_sb` / Sheet ID `sb_portfolio_sheet_id_input` / Google 登入 link_button / 測試連線 `sb_conn_test` / 強制刷新 `_sb_force_refresh` / AI 解讀 `btn_data_health_ai`。**其中「登入」與「強制刷新」是首次使用必經路徑**，新使用者開站看不到任何入口。
- 🔴 **置底條在空狀態整條消失**（`:869`）：`if (_mkt_top or _jq_top) and not _is_refreshing:` —— 而 `:896` 自己寫好的 `'⬜ 總經未評估'` 分支**只有在條件為真時才有機會執行**。首次進站兩者都空 → 整條 bar 消失。這正是 v19.171 🔴-1 想修但沒修完的那一半。
- 🟡 **Sidebar 兩區塊順序倒錯**：免責聲明在 `:336`（A 塊尾），但 `:347` 強制刷新與 `:356` 資料健康在其**下方**渲染。B 塊只有 13 行，沒有分開的技術理由。
- 🟡 **指路到不存在的面板**（`:213-214`）：「頁面底部有 AI 整合報告面板」—— 檔案最底（`:935`）是免責聲明，AI 現在在 `tab_ai`（`:810`）。
- 🟡 **核心總表感知延遲**：`_core_summary_slot`（`:381`）要等全部 13 個葉節點 tab render 完（`:832`）才填。
- 🟡 **`_render_tab_isolated` 的 label 未逸出**（`:443`）：`st.error(f'...{str(_e_tab)[:300]}')` 把上游例外原文直接注入，而同 repo 的 `core_summary_render._esc()`（`:50-58`）已有正解。
- ⚪ **版本號對外 v3.0、實際碼版 v19.192**（三處）。
- ⚪ **總經指南針名不副實**（`app_render.py:204-206`）：三卡全是 `^VIX`/`^TNX`/`^GSPC`，一個台股變數都沒有；`_macro_compass_cache` 存 session **永不過期**，`:177` `strftime('%H:%M:%S')` 無日期 → 跨午夜時「更新於 09:15:03」可能是昨天。**而同一檔的置底條 `:913-923` 已有 `gate_for_realtime(max_days=1)` 時效閘 —— 標準不一致**。

**程式碼問題**
- 🔴 見 §2 H-3（隔離器 8/13 + expander 陷阱）
- 🟡 **時區 SSOT 已 import 卻沒用**（`:207` vs `:32`）：`_TW_TZ_SB = datetime.timezone(...)` 與檔頭已 import 的 `_tw_now` 重複，且註解自陳「§4.5 全站已有多份複本」。
- 🟡 **`config.toml` 兩條設定實測無效**（實機 `ring1_report.txt` 為證）：`enableMarkdownUnsafeHTML` **不是合法鍵**（`is not a valid config option`）；`enableCORS=false` 被 `enableXsrfProtection=true` **覆寫回 true**。
- ⚪ **死碼與空 shim**：`_TERM_HELP_LI`（`:188`，且 module level 每次 rerun 都白呼叫 3 次）、`primary_stock='2330'`（`:200`）、`ai_run=False`（`:215`）、`app_cache` re-export（`:154`）、`app_stock_fetchers` re-export（`:158-167`）—— 後兩者的真 caller 都直接吃 L0/L1，這層 shim 純屬歷史殘骸。
- ⚪ **`shared/ttls.py:25` `TTL_10MIN=600` 註「月頻指標(tw_macro 7 處)」** → 月頻資料每 10 分鐘重抓 = 每天 144 次無效外呼，且與 `staleness.py:198-207` 的發布延遲 SSOT 自相矛盾。

#### 2. 具體改善優化方案

**新手友善化調整**
- 核心總表下方加 onboarding banner：「👋 第一次使用？① 展開左側選單登入 Google ② 到『🌍 市場環境』按一鍵更新全部數據」，全部載入後自動隱藏
- 置底條空狀態改 `_gl_slot.info('⬜ 尚未評估總經 —— 請至「🌍 市場環境 → 總經」按「🚀 一鍵更新全部數據」')`
- Sidebar 加「🔰 新手白話模式」toggle（對應 §2 H-5）

**介面排版與按鈕瘦身計畫**
- 兩個 `with st.sidebar:` **合併**，順序改：標題/日期 → 🔄 強制刷新（加二次確認）→ 🔌 連線狀態（可摺成「🔌 3/3 正常」）→ 📊 資料健康 → 🔐 Google 帳號 → 免責聲明（最末）
- 刪除 `### 🤖 AI 分析` 整段（指路已失效）與 `st.success('🟢 系統正常運作中')`
- `initial_sidebar_state` 改 `'expanded'`
- `🔍 測試連線` 結果加時間戳，超過 5 分鐘自動淡出
- badge 改讀 `shared/version.py::APP_VERSION`

**數據呈現與進階分析保留方式**
- 總經指南針：`_ts_str` 改 `%m/%d %H:%M`；接上 `gate_for_realtime`；標題改「🌐 美股風向（VIX / 10Y / S&P）」以符實；補一張 `^TWII vs 60MA`
- 核心總表在 tabs **之前**先渲染骨架（含 loading 狀態），尾端再 `.container()` 覆蓋

#### 3. 程式碼重構建議

| 項目 | 檔案 | 工時 | 測試風險 |
|---|---|---|---|
| 刪旌旗 50 fallback + 硬編碼綠燈 | `app.py:870,217` | 15 分 | 🟢 |
| 5 處補 `_render_tab_isolated` | `app.py` | 30 分 | 🟡 需保留 `with tab_X:` 字面（見 §4） |
| 進階診斷加 checkbox gate | `app.py:785` | 10 分 | 🟢 |
| 刪 dead code + re-export shim | `app.py:154,158-167,188,200,215` | 20 分 | 🔴 **必須同 PR 改 `test_c3_layering_guard.py:468` 白名單**（反向守衛） |
| Sidebar 兩區塊合併 + 順序重排 | `app.py:203-359` | 20 分 | 🟢（需視覺驗收） |
| `config.toml` 清無效鍵 | `.streamlit/config.toml` | 5 分 | 🟢 |
| `_TW_TZ_SB` 改用 `_tw_now()` | `app.py:207` | 5 分 | 🟢 |
| `app_cache` 加 `mode=0o700` + 原子改名 | `shared/app_cache.py:31,63` | 20 分 | 🟢 |
| `_render_tab_isolated` 例外訊息加 `_esc()` | `app.py:443` | 5 分 | 🟢 |

---

### 📌 3-2. 🌍 市場環境 → 🌍 總經（`tab_macro.py` + `macro/` 15 檔，23 段）

**渲染順序**：一鍵更新 L154 / 強制重抓 L172 → AI 總結 expander L191 → empty gate L200 → ⚡關鍵橫幅佔位 L241 → **🚦紅綠燈卡 L265** → 長期雷達（無 UI）L269 → **📊五桶 bar L275** → 🔰 30 秒讀懂 L295 → **戰情概覽 L321** → **今日作戰室 L326** → Token/時間戳 L329-358 → `_load_heavy` gate L375 → 刷新流程 L384-540 → **§二拐點 L578**（含回測 + 熱錢 + 燈號回填 + 🎚️持股油門）→ **§七長期 L593** → **§八總經拼圖 L596** → 橫幅回填 L602 → 🇨🇳中國拖累 L612 → **§五短線急殺 L617** → 🌍9燈雷達 L623 → **§三籌碼 L626** → **§九規則決策 L628** → **§十一 News AI L639**

⚠️ **標號錯亂實證**：畫面 section 編號序為 **七→一→二→六→八→五→三→九→十一**；「📰 新聞」是 `BUCKET_ORDER` 第 5 桶，但**從未出現「桶 5/5」banner**（`section_news_ai.py:122` 發的是 `_bgb('ai', 6)`）；`section_summary_bar.py:53-56` 的導覽 caption 仍是舊順序，**漏了 v19.168 新增的「🧭 規則決策」**。

#### 1. 現狀診斷與問題點

**資料稽核問題**
- 🔴 **N-2 薩姆幽靈把關**（見 §0.3）—— `section_traffic_light.py:101-103` 對使用者宣稱的 5 條硬否決，實際只有 2 條在 `allocation_service._INTRINSIC_CAP_NAMES` 內。
- 🔴 **N-3 `calculate_system_state` 全缺值 → 曝險 60%**（`macro_state_locker.py:476-518`）。持股數字雖已於 v19.170 改讀 `allocation_service`，但 `market_regime` / `systemic_risk_level` 仍由本函式產出並渲染於 §十一 巨字卡。
- 🔴 **`show_market_data` 閘門在 §二主體之後**（`section_state.py:575` vs L50-547）：快取過期 45 分時，頁頂誠實顯示「⏳ 燈號等待中（已過期）」，下方卻印出完整「🔴 3/5 群偏空 → 考慮減碼」結論卡。且 `:349` 的 `_pivot_signals` 寫入在閘門之前 → `section_news_ai.py:426` 會把過期拐點餵給 Gemini。
- 🔴 **缺值捏 0/50/55 群聚**（見 §2 H-1 表）。特別是 `section_mid.py` 的**同一個 key 在同檔有兩個不同預設**（PMI 50 vs 55、NDC 0 vs 25），且 `:375-379` 的 `_vix_now8` **已經改成回 `None`**（v19.170）而 `:214`/`:299` 兩處沒跟上 —— 典型「修一半」。
- 🔴 **6 處 `except: pass` 包住 5 張警示卡**（`section_chips.py:409/431/447/462/487` + `:372`）。
- 🔴 **快取降級旗標算了沒傳**：`tab_macro.py:556-563` 算出 `_inst_is_cached` / `_margin_is_cached`，`:626` 卻是 `render_section_chips(inst, margin, cd)` —— 兩個旗標**全 repo 零其他 reference**；`li_retain_meta` 在 `section_chips` 出現 **0 次**（僅 `data_coverage.py:587` 消費）→ 先行指標連續抓失敗時，🧩 籌碼桶照常渲染舊表，降級標記只在另一個分頁看得到。
- 🔴 **畫面寫死「台股與美股相關性 ~0.6」**（`section_state.py:513`），程式無任何一行計算它。**而同檔 L366-368 才剛自訂紀律**：「ρ̄ = 0.7 是量級假設而非本專案實測，故**不印到畫面**；§3.3 反捏造」—— 同一檔案上下自相矛盾。
- 🟡 **三個 session 快取永不失效**（`section_state.py:227-238`）：`_ndc_hist_cache` / `_ndc_li_cache` / `_fi_streak_cache` 不在 reset 清單內，連「🆕 強制重抓」也清不掉。
- ✅ **`section_cross_ai._num()`（`:58-69`）是正面案例**，v19.183 已修，含 NaN guard + `_cycle_exp is not None` 守門 + 「僅一半資料」誠實分支。**應作為全 macro 15 檔的收斂模板**。

**UI/UX 與操作體驗問題**
- 🔴 **`help=` 精確計數 = 4**（macro 15 檔合計）：`helpers`×1 / `section_long`×1 / `section_news_ai`×1 / `section_state`×1。**`section_mid.py` = 0、`section_chips.py` = 0** —— 全頁最密集的「總經拼圖 5 卡 + 三環 7 徽章」與「籌碼 8 欄先行指標表 + 5 張警示卡 + 計分器」**一個 tooltip 都沒有**。根因是這兩檔全走 `st.markdown(unsafe_allow_html=True)` 手刻卡片，無處可掛 `help=`。
- 🔴 **五桶 bar 與作戰室必爆手機**（`helpers.py:359/379` 5 欄 + 104px、`section_warroom.py:197` 5 欄 + 108px）。
- 🟡 **同一結論說 4 次、各用不同門檻**（`section_chips.py` 的「外資期貨怎麼看」：−30000/−15000/0、−20000/−30000、同前但文案不同、−30000/0）。
- 🟡 **9 欄裸 HTML 表無 `overflow-x`**（`section_chips.py:376`）。

**程式碼問題**
- 🔴 **五桶被重算 5 次**（`section_summary_bar:29` ×1 + `helpers:413` 被 long/mid/short/news_ai 各呼叫一次）。
- 🔴 **30 年回測 expander 無條件執行**（`section_state.py:456-462`）。
- 🟡 **門檻 SSOT 大面積未接線** —— `BUCKET_DANGER_SPECS` 只被 `add_danger_hlines`（畫圖）消費：

| 指標 | SSOT | 實際判定式 | 後果 |
|---|---|---|---|
| VIX | 黃 22 / 紅 30 | `section_mid:401,406` `>=30` / **`>=20`** | **VIX=21 → 五桶 🟢、否決權卡 🟡，同頁互打** |
| PMI | 黃 50 / 紅 46 | `section_mid:301` **`< 48`** | 48 不在 SSOT 任何一條 |
| bias_240 | 黃 10 / 紅 20 | `section_mid:451` `>=15`；`section_long:262,307` `±20`；`section_cross_ai:269,271` `>=15/<=-5` | **四種門檻**（`section_warroom:38` ✅ 有用 SSOT） |
| fut_net | 黃 −10000 / 紅 −20000 | `section_chips:263,268`；`section_state:192,195,198` | **五種門檻** |
| CPI | 黃 3.5 / 紅 4.0 | `section_cross_ai:212-214` **3.0**/4.0 | |
| adl | 黃 50 / 紅 35 | `section_warroom:149` **inline `< 35`** | ad_ratio∈[35,40] 時 §五 判 🔴、五桶判 🟡 |

- 🟡 **TTL 顯示字串手抄 8 條**（`section_chips.py`）—— 這張卡的存在目的正是防止誤把舊值當即時。
- 🟡 **同一 token 兩個來源**（`section_state.py:21` `from src.config import FINMIND_TOKEN` vs `:225` `st.secrets.get(...)`）→ 無 secrets.toml 但有 env 時，同一頁一半功能被限流。
- 🟡 **`_above200` 是死變數**（`section_state.py:89`，算完丟棄）。

**金融邏輯問題**
- 🔴 **「黃金交叉」不是交叉**（`section_state.py:157-165`）：只比當期 `_diff > 0` 無 prev → M1B 持續高於 M2 的一兩年裡**每天都印一次「黃金交叉 → 長線起漲徵兆」**。門檻不對稱（`>0` vs `<-1`，中間 `-1~0` 靜默）。
- 🔴 **PCR 同欄位 5 條門檻，caption 與計分器直接對撞**：`:331-332` 走 SSOT `<80/>120`、`:454,458` inline `<80/>150`、`:787,791` inline `>130/>100`、`:94` 缺值捏 `_pcr = 100.0`。而 `:334-343` caption 明講「100 …**不是本系統的判定線**」，`:794` 就在下方印 `🔴 PCR（<100偏空）`。
- 🔴 **趨勢四分支不完備**（`section_state.py:94-111`）：`not _above60 and not _turn_down`（**跌破 MA60 但均線尚未下彎＝典型初跌**）沒有任何分支，卻已把 trend 群登記為「可評估」→ 顯示「趨勢：中性」。
- 🔴 **籌碼桶恆紅 + 旌旗雙重計數**：`macro_buckets.py:280-283` 的 margin spec note **自己承認**「實測 5,148 億早已穿透兩線，**燈號恆紅、鑑別力歸零**」；`jingqi`（`:293`）同時註冊在 chips 桶、又佔 long 桶 `health` 的 0.6 權重（`:157/:199`）→ 廣度一弱兩桶同時轉紅，使用者讀成「兩份獨立證據」。
- 🟡 **計分器結構性偏空**（`section_chips.py:774-846`）：分數域 [−6,+5] 卻用對稱切點；「強烈偏多」只有 {3,4,5} 三格、「強烈偏空」有 {−6..−3} 四格。
- 🟡 **三句對新手最危險的話**：`section_mid.py:637`「**重壓半導體主流**」（集中度指令但只導向持股比例）、`section_mid.py:204`「兩者同步月降 → ⭐ CPI×Fed 雙頂回落（**多頭最佳買點**）」（同檔 `:147-149` 自承「與 Mann-Kendall 無關」、樣本 n=2，卻用絕對級措辭）、`section_chips.py:461` PCR>150「**逆向布局訊號**」（且該分支被 `:462 except: pass` 包住，可能無聲消失）。
- 🟡 **NDC 延遲未揭露**（`section_state.py:229/253-263`）：直接印「分數 {prev}→{latest}」無資料截止月份，而 NDC 約每月 27 日公布**上月**資料。同檔對回測卻做足 PIT 揭露 —— **回測誠實、即時面板不誠實**。

#### 2. 具體改善優化方案

**新手友善化調整（三層漸進揭露）**
```
第一層（永遠可見）
  🚦 紅綠燈卡 + 一句白話結論「今天適合買 / 觀望 / 減碼」
  📊 五桶 bar（改橫向 chip 列，手機友善）
  ⚡ 今日 3 個最重要的變化（不是 9 燈全列）
第二層（預設展開）
  🌍 今日市場總覽（四象限 + M1B-M2 + BIAS240）／今日作戰室 5 格
第三層（Expander 收納）
  §二拐點／§七長期／§八拼圖／§三籌碼細表／§五短線／🌍9燈／§九跨桶／§十一 News AI
```
- `section_mid` / `section_chips` 的手刻卡片接上 `unified_indicator_card`（該元件已存在於 `macro_ui_components.py:317`，目前只服務 section_mid 的一部分）
- `section_chips` 的欄位說明**從 Tab 5 搬回本頁**，改為欄名 tooltip
- 21 個總經名詞白話文文案見 §8 附錄

**介面排版與按鈕瘦身計畫**
- 五桶 bar 改 `st.columns(min(5, 2))` 響應式或移除 `min-height`
- 「外資期貨怎麼看」4 段 → 收斂為 1 段，門檻統一走 SSOT
- 9 欄裸 HTML 表包 `overflow-x:auto`
- 「🚀 一鍵更新」與「🆕 強制重抓」合併為一顆按鈕 + `st.toggle('強制重抓（忽略快取）')`
- 修正 section 標號序與 `section_summary_bar` 的導覽 caption

**數據呈現與進階分析保留方式**
- **一格資料都不刪**，全部保留在第三層
- 過期資料改「顯示但加浮水印」（`⏳ 資料為 45 分鐘前`），而非隱藏或靜默使用
- 缺值改 ⬜ + 「為什麼沒有」+ 補救按鈕

#### 3. 程式碼重構建議

| 優先 | 項目 | 檔案 | 測試風險 |
|---|---|---|---|
| P0 | 刪除不存在的薩姆／PMI／外資期貨 cap 文案 | `section_traffic_light.py:101-103` | 🟢（`test_position_ceiling` 釘的是 `_cap_line:64`，不是這行） |
| P0 | `show_market_data` 閘門上移至 `:50` 之前 | `section_state.py` | 🟡 |
| P0 | `calculate_system_state` 全缺值改 raise/None | `macro_state_locker.py:476-518` | 🟡 |
| P0 | `section_mid` 6 處 `.get(k,<數>)` → `_num()` | `section_mid.py:130,214,299,301,307,368` | 🟡 **`test_d2_macro_sections.py:407` 的 `seen >= 7` 下限** |
| P0 | M1B/M2 三態 + 加 prev 比較（真交叉） | `section_state.py:157-165` | 🟡 **`test_d2_macro_sections.py:254` 的 `seen >= 10` 下限** |
| P1 | 快取降級旗標接線（`inst_is_cached` / `li_retain_meta`） | `tab_macro.py` / `section_chips.py` | 🟢 |
| P1 | 6 處 `except: pass` 改「讓失敗本身變成一條可見警示」 | `section_chips.py` | 🟢 |
| P1 | 刪畫面寫死的「相關性 ~0.6」 | `section_state.py:513` | 🟢 |
| P1 | 30 年回測改 button gate / cache | `section_state.py:456` | 🟢 |
| P1 | 五桶只算一次（caller 注入） | `helpers.py:413` | 🟢 |
| P1 | `_macro_session_reset` 補 16 個 key（**`macro_alerts` 除外**） | `handlers.py:21` | 🔴 **`test_p0a_key_alerts_and_spinner.py:170` 明文禁止補 `macro_alerts`** |
| P2 | 判定式改吃 `SPECS_BY_KEY`（VIX/PMI/bias/fut_net/CPI/adl） | 6 檔 | 🟡 會改變燈號，需裁示 |
| P2 | 趨勢四分支補完 + 啟用 `_above200` | `section_state.py:89,94-111` | 🟡 |
| P2 | 融資改百分位（解籌碼桶恆紅）+ jingqi 去雙重計數 | `macro_buckets.py` | 🟡 會改變燈號，需裁示 |
| P2 | `section_mid` / `section_chips` 補 tooltip（現為 0） | 兩檔 | 🟢 |

---

### 📌 3-3. 🌍 市場環境 → 🗺️ 產業熱力圖（`src/ui/render/etf_render.py::render_sector_heatmap` + `shared/sector_heatmap.py`）

#### 1. 現狀診斷與問題點

**資料稽核**
- 🔴 **「面積≈權重」是假話**（`etf_render.py:786`）：實際 `sector_heatmap.py:173-178` 的 `node_area()` 回 `max(abs(ret_pct), floor)` → **面積 = 漲跌幅絕對值**。所以「跌 5% 的小類股」方塊比「漲 1% 的半導體」大，恰好誤導成「資金流向」。
- 🟡 色階 inline（`:761-762`）未走 `shared/colors.py`，且**無絕對錨點**；「快取 30 分鐘」硬寫在 caption 與 TTL 常數脫鉤；無資料截止日。

**UI/UX**
- ✅ **口徑 caption 位置其實合理**（`:811-815`，選完區間後、看圖前），且內容精準（交易日 vs 日曆日、非即時報價、adjusted close）—— **這是本範圍寫得最好的揭露文案，v1 的批評不成立**。真問題只有「面積≈權重」那句。

#### 2. 具體改善優化方案
- 圖上方加白話結論：「本週資金明顯流向 半導體、金融，流出 航運、生技」
- 文案改「面積≈漲跌幅絕對值（越大代表變動越劇烈），**不代表市值權重**」
- 色階加絕對錨點（±5% 滿色）並顯示 colorbar；加「資料截止：YYYY-MM-DD（交易日）」
- 台股代理股警示縮成一行 chip + ⓘ hover

#### 3. 程式碼重構建議
| 項目 | 檔案 | 工時 |
|---|---|---|
| 「面積≈權重」文案修正 | `etf_render.py:786` | 2 分（🔴 誠實性） |
| 色階走 SSOT + 絕對錨點 | `etf_render.py:761` + `shared/colors.py` | 30 分 |
| TTL caption 改 f-string 代入常數 | `etf_render.py:814` | 5 分 |

---

### 📌 3-4. 🌍 市場環境 → 🌊 板塊資金潮汐（`tab_sector_flow.py` + L3 `sector_flow_service` + L4 `sector_flow_render`）

#### 1. 現狀診斷與問題點

**程式碼問題**
- 🔴 **每次 rerun 觸發 N+1 次 Google Sheets 全表讀，零快取**（比 v1 判斷更嚴重）：`tab_sector_flow.py:47` 無條件呼叫 → `sector_flow_service.py:48-49` 對每個 watchlist 各跑 `list_stock_watchlists` + `load_stock_watchlist`，而**兩者各自呼叫一次 `_all_records()`**（`gsheet_portfolio.py:241-246`，裸 `get_all_records()` **無 `@st.cache_data`**）→ 5 個 watchlist = **6 次同一張表的完整網路讀取，每次全站 rerun 都重跑**。加上 `st.tabs` eager render，使用者在別的次頁籤也照跑。

**資料稽核**
- 🟡 無資料截止交易日揭露（讀離線 parquet/json，由 cron 盤後產出）。

**金融邏輯**
- 🔴 **未做規模正規化**：X 軸與泡泡大小都是絕對金額（億）→ 半導體恆佔極端 → **圖表反映的是板塊市值，不是資金輪動**。
- 🔴 **共線**：`size` 用 `WINDOW_SIZE=20`、`x_yi` 用 `WINDOW_X=5`，`vals[-20:]` **完整包含** `vals[-5:]`。
- 🔴 **`size_yi = abs(vals.sum())`** → 流入 100 億與流出 100 億泡泡一樣大。
- ⚠️ **ETF 桶「重複計算」不成立**（`compute_sector_daily_net` 是 per-stock 加總，0050 與 2330 是不同 `stock_id`）→ 正確描述是「**經濟意義重疊**」（買 0050 間接是買台積電）。

#### 2. 具體改善優化方案
- 泡泡圖上方加一句：「右上角＝短期＋中期都在流入；左下角＝雙雙流出」
- 加 toggle「按市值正規化」（**兩種視角都保留**）
- `size` 改用非共線指標（20 日累積 − 5 日）；流入/流出用**顏色**區分
- X 軸標題加註「絕對金額，未按市值調整」；ETF 桶加註「與個股板塊有經濟意義重疊，勿加總」
- 3 段 caption 收進「📖 怎麼看這張圖」expander

#### 3. 程式碼重構建議
| 優先 | 項目 | 檔案 |
|---|---|---|
| P0 | `_all_records` 加 `@st.cache_data(ttl=TTL_1DAY)`，或 `_collect_stock_watchlist_tickers` 改單次全表讀 + 本地過濾 | `gsheet_portfolio.py:241` |
| P0 | 顯示資料截止交易日（轉台北時間） | `tab_sector_flow.py` |
| P1 | 規模正規化 toggle + size 去共線 + 流入流出配色 | `compute/sector_flow.py` + `sector_flow_render.py` |

---

### 📌 3-5. 🔬 選股 → 🔬 個股（`tab_stock.py` 1,876 行 + `stock_sections/` 13 檔 + `pattern_targets_ui.py`）

**14 個渲染單元**（主檔 12 個 `####` marker，其中 9 個在財報體檢 expander 內）：
解說卡 → 操作列 + 📐均線設定(L205-233，**6 個 MA checkbox**) → 🎯型態目標價 L243 → 📊資料新鮮度 L393(9 源) → 跨Tab聯動 L548 → 📌即時趨勢總覽 L562 → 🧭一眼判讀 L599 → **桶①**：🎯停利停損 L631 / 📊操作雷達 L681 / ⚙️多因子評分 L738 / 紅K錨點 L800 / 🧠操作前必做+🚫禁止操作 L873 / 🎯什麼時候買賣 L880 / 龍頭預警 L887 → **桶②**：🏥健康度 L892 / 🎯VCP+布林 L903 → **桶③**：籌碼 L907 / 📊K線圖 L911 / 💡即時操作建議 L921 → **桶④**：💰357估值 L928 / 🔬財報領先 L934 / 📈月營收 L944 / 📖策略1結論 L949 / 🔬D2六大 L955 → **桶⑤**：🔬AI財報體檢 L1001（內含 9 個 `####`：生死防禦 L1045 / 五力雷達 L1077 / 企業DNA L1109 / 存活診斷 L1145 / 經營診斷 L1187 / 獲利診斷 L1227 / 財務結構 L1300 / 短期償債 L1336 / 綜合避雷 L1394）→ **桶⑥**：🤖AI首席顧問 L1474-1866（含 📰新聞 L1495）

#### 1. 現狀診斷與問題點

**資料稽核問題**
- 🔴🔴 **N-1 無 MA 數據白送 15 分**（`scoring_helpers.py:160-162`）—— **本案最嚴重的一條**。趨勢佔 30/100，新上市股憑空拿半分；畫面顯示「趨勢 − 無MA數據」（誠實），但 `health2` 分數裡已含這 15 分。
- 🔴 **`except: pass` 22 處**（主檔 15 + sections 7），`_precompute_xsec` 連續 4 個裸吞（`:110/115/120/129`）。
- 🔴 **財報體檢 5 處「缺資料 → 綠燈」**（`financial_health_engine.py`）：`:694` `else 50`、`:569-575` `cl==0 → "Pass (無短期債務)"`、`:546-547` `ppe<=0 → "Pass"`（且 `_pts()` 給滿分 2）、`:436` 100-100-10 全 N/A → Pass、`:359-363` radar `_score` 保底 20。**外加 `:371` `"償債能力": 60 if ocf_k > 0 else 30`** —— 這根本不是償債能力（是 OCF 正負），且 60/30 是裸數字。
- 🔴 **`section_op_recommendation.py:92-110` 6 處捏 0 造成死分支**：`app_ai_service.py:296` 的 `if score >= 85 and '便宜' in val and '多頭' in trend:` —— 三個輸入全被硬編成 0/''，**這條「🚀 強烈買入」分支對任何股票永遠不可能觸發**。
- 🟡 **`or float('inf')` 哨兵方向錯**（`section_when_buy_sell.py:125-128`）：v2 確認**實務不觸發**（`calc_bollinger` 只回 None 或完整 7-key dict；`session_state` 是同進程記憶體不走 pickle，型別不會跑掉）。**但 `_bb_near_up`（`:127`）是死碼，且 `calc_bollinger` 內部 `:123` 已經算過 `bb2['near_upper']` —— 兩份平行實作，一份死掉**。
- 🟡 **`section_kline_chart.py:187-192` 的 `'rsi': rsi2 or 0, 'total': 0`** ❌ 不持久化（只寫 session），但會與 cron 的真實列**混在同一個 list**（`merge_score_history`）。
- 🟡 **`section_psy_checklist.py:167-168` 100% 走 7% 估算**：caller `tab_stock.py:875` 明文傳 `_atr2_val=None`（且 `:869-871` 註解自陳「本函式從未被賦值」），畫面卻印「③ 確認停損價（跌破 X 元無條件出場）」**不標估算**。
- 🟡 **`section_357_valuation.py:226` `.mask(<=0).ffill()`** 讓過期股利冒充現值（有安全網但**部分過期**會靜默 ffill）；**`section_revenue.py:48-52`** `tail(3)` 只要 2 筆就標「近3月平均YoY」。

**inline magic number（§3.3）—— 4 個「SSOT 已存在卻沒用」**

| 位置 | 裸數字 | 已存在的 SSOT |
|---|---|---|
| `section_psy_checklist.py:167,168` | `0.07`、`1.5` | `ATR_STOP_MULTIPLIER`（`signal_thresholds.py:575`） |
| `section_kline_chart.py:203-205,209` | `80`/`50` | `HEALTH_GRADE_A_MIN`/`B_MIN` |
| `section_health_score.py:116,118,137,138,142` | `20`/`80`/`0.2`/`0.8` | `KD_OVERBOUGHT/OVERSOLD_LEVEL`、`IBS_*`（**同專案 `scoring_helpers.py:211,224` 已經在用了**） |
| `section_health_score.py:102,104,127,128` | `30`/`70` | `RSI_OVERSOLD`/`RSI_OVERBOUGHT`（`config.py:52-53`） |
| `tab_stock.py:1353` | `300/150/100` | `FH_CURRENT_RATIO_MIN_PCT`/`FH_QUICK_RATIO_MIN_PCT` |

無 SSOT 者：`0.995`（`tab_stock:818`）、`0.99`/`1.01`（`when_buy_sell:261,270`）、`k2>70`（`:132`）、`>=3/>=2`（`op_recommendation:61,64`）、`0.6/0.3`（`d2_leading:59,60`）、`15`（`revenue:53` + `:71` 文案第二份）、`>=20`（`kline_chart:221`）、`30/20`（`strategy_conclusion:86-88`）。
**VCP「30/40/25 三處打架」✅ 屬實**：`vcp_bollinger:73` 文案「需至少30日」、`:91`「數據不足（需≥40日）」、實作門檻是第三個數字 —— **同一張卡的兩行字互相矛盾**。

**UI/UX 與操作體驗問題**
- 🔴 **停損有 7 個數字散在 4 個檔**（v1 說 5 個）：現價×0.92（`tab_stock:664`）／紅K低點×0.995（`:818`）／現價×0.93（`when_buy_sell:260`）／MA20×0.99（`:261`）／ATR 真停損（`:298`）／現價×0.895（`psy_checklist:168`，7% 估算）／MA20 或爆量紅K低點（`health_score:306`）。**對低波動股（ATR%≈2%），`when_buy_sell` 的真 ATR 與 `psy_checklist` 的估算差距達 3.5 倍**。
- 🔴 **色彩語意反向 3 處**：`chips_20d:49-50`（吸籌 `TRAFFIC_RED` vs 倒貨 `#da3633`，兩個都紅但語意相反，而 `st.metric` 的 delta 又是綠/紅 → 同一張卡左紅框右綠 delta）；`health_score:371`（外資強勢=紅、渙散=綠，**台股慣例**）vs 同檔 `:199`（`TRAFFIC_GREEN if health2 >= 80`，**西方慣例**）→ **同檔混用兩套色彩語言**；`vcp_bollinger:88` `signal_box('🔴等待帶量突破頸線', 'green', ...)`。
- 🟡 **`help=` 全 tab 9 個**（v1 說 3 個），但**全部掛在 button / selectbox，沒有一個掛在數字上**；畫面有 60+ 個 `kpi()` 卡片、20+ 個門檻數字，零 tooltip（`kpi()` 結構上無法掛，見 §2 H-5）。
- 🟡 **主流程只有 3 個 `####` 卻塞 14 個渲染單元**，`render_stock_toc_html()`（`:626`）只做 6 桶錨點；**財報體檢 9 個 `####` 全鎖在一個 `expanded=True` 的 expander 裡** → 一打開再多 30+ 個卡片。
- 🟡 **6 個 MA checkbox 在 L205-233，只影響 L911 的 K 線圖**（相隔約 700 行）。

**程式碼問題**
- 🔴 **Compute 層 SSOT 是 production dead，UI 另開 2–4 套平行實作**（已全域窮舉驗證，109 個 .py 逐檔 grep）：

| 函式 | production caller | UI 平行實作與門檻差異 |
|---|---|---|
| `check_bollinger_squeeze`（`:1250`） | **0** | `vcp_bollinger:42,109` 用 `ACTION_RATIO`、同頁 `:103` 又用 `WARN_RATIO(0.7)` → **同一張卡兩個門檻**；另 `health_score:174`、`tab_stock_picker:1091`(×1.3) |
| `check_contract_liability_surge`（`:1231`） | **0** | SSOT 版看 **YoY**，UI 版（`financial_leading:35` / `dragon_alert:44-56`）只看**當期佔股本比**（`health_score:452` 自己也承認「YoY 未計」） |
| `check_fake_breakout`（`:1283`） | **0** | **production 完全不存在假突破濾網**，`v5_modules.py:293` 註解自承是 "mirror … pattern"＝又一份平行實作 |
| `check_relative_strength`（`:1306`） | **0** | UI 走 `calc_rs_score` + `rs_slope`，**完全不同演算法** |
| `calculate_position_size`（`:1353`） | **1**（`when_buy_sell:289`） | ✅ v19.146 已接線 |
| `risk_control.*` | ⚠️ `portfolio_exposure` / `check_portfolio_limits` / `RiskController` **都有 caller**；只有 `atr_stop_price`/`stop_loss_trigger`/`trailing_stop_trigger` 無外部 caller | 但個股頁完全不碰 risk_control → **全站兩套停損引擎並存** |

- 🔴 **`section_dragon_alert.py:45-56` 逐字重寫 + OR vs AND 打架**：dragon_alert 用 **OR**（任一達標就掛 🏆 龍頭預警），`financial_leading.py:185` 用 **AND**（`_cl_lead and _cx_lead` 才「✅ 龍多確認」）→ **同一頁上方掛金色「🏆 極稀有高成長標的」、下方寫「⚠️ 部分訊號：資本支出未達」**。
- 🔴 **`@st.cache_data` 全 tab 只有 1 個**（`section_357_valuation.py:39`，且只 cache TWSE PB）→ **零計算層快取**。`when_buy_sell:181-187` 的 `st.number_input`（總資金）沒有 `on_change`，每次輸入完整 rerun `render_tab_stock()`：重算 `compute_std_bands(252)` + `weekly_macd_hist`（全歷史合成週K）+ `analyze_20d_chips_from_df` + 180 根 K 線 `make_subplots` + 9 條 `add_hline` + `_precompute_xsec` 全部 + **13 個 section 全部重畫**（含 3 張 plotly 河流圖，其中 PE 河流還跑一次 `merge_asof`）。
- 🟡 **`_precompute_xsec` 算完，下游又重算**：

| key | 算在 | 下游重算 | 實際次數 |
|---|---|---|---|
| `con20/cty20/sig20` | `tab_stock:105` | `chips_20d:40` + `when_buy_sell:146` | **3×** |
| `rs_val` | `:114` | `tab_stock:788` + `when_buy_sell:207` | **2–3×** |
| `li_results` | `:124` | `d2_leading:47` | **2×** |
| `capital` | `:119` | 三個 section 皆走傳參 ✅ | 1×（**正確示範**） |

- ❌ **`generate_ai_comment()` 每次 rerun 打 LLM — 不成立**：`app_ai_service.py:244` docstring 明文「決策樹文字建議產生器(**Rule-based，無 AI API**)」。**但衍生 UX 誠實問題**：`section_op_recommendation.py:121` 把一個決策樹叫做「AI 分析」。

**金融邏輯問題**
- 🔴 **健康度 6 因子共線比 v1 判斷更嚴重**：RSI(20)+KD(15)=35% 都是「收盤價在近期區間的相對位置」；再加布林 10 分（`:258-263` 判的也是價格相對位置）；趨勢 30% 也是價格 vs 均線 → **六個因子有五個在量同一件事，只有量比(15%) 是獨立維度**。
- 🔴 **「禁止操作」把大跌講成追高**：`SOP_BAN_SURGE_PCT = **4.0**`（不是 15），`abs(_surge_chk) > 4` → 近 5 日跌 18% 印「**📈 個股近5交易日漲幅 -18.0% 超過4%（追高風險）**」，emoji 還是上漲箭頭。**且 `:182` 會把 SOP 第②關 `disabled` 鎖死，理由是「追高」**。其餘 3 條：`monthly_loss_pct` 全站無寫入點但**已誠實列入 `_unevaluated`**（v1 判「死碼」需修正）；融資餘額是**全市場**數字放在「個股禁止操作」清單裡（語意錯位）。
- 🔴 **合約負債分母用股本，財務上錯**：合約負債是**營運規模**的函數（∝營收），股本是**歷史籌資**的函數。台積電股本 2,593 億但年營收 2.9 兆 → 天生就低；股本 5 億、營收 20 億的小廠只要 2.5 億預收就「達標 50%」。**同門檻套在不同股本結構的公司上完全不可比**。且 `dragon_alert:38-40` 註解**已察覺分母語意變了**（capex 從 PP&E 存量改季流量）**卻沿用同一個 80% 門檻** → 幾乎永不觸發；`:40` 抓不到 capex 就 fallback PP&E 存量套同門檻 → **資料越差、結論越樂觀**。
- 🔴 **「4 訊號共振」名不副實**：簡單加總無權重（「大盤多頭」與「VCP 收縮」同權重）；`rsi2` 收了參數但**不進 `_sig_count`**；否決時 `:70` 的標題**照印 `3/4`**；且估值那條用 `YIELD_MID_DEC`（5% 合理價）當「便宜」，與 `section_357_valuation` 的 `YIELD_HIGH_DEC`（7%）**不同標準**。
- 🟡 **357 同畫面兩個「便宜價」**：KPI 卡用 `avg_div2`（5 年均股利）、河流圖用 `_ttm_series`（365D rolling TTM）→ 除數相同但被除數不同。不配息股 `avg_div=0` 時 `tab_stock:699` 的 `_valuation_simple = None` → **估值維度靜默消失，狀態燈少一個維度卻不標示**。
- 🟡 **D2「六大」名不副實**：`section_d2_leading.py:197` **已正確把 I6 排除出分母**（v1 判斷需修正），但 `stock_buckets.py:213` 標題寫「六大先行指標 🟢x 🟡y 🔴z」而三數加總永遠 ≤5；且模組四說明「籌碼集中度與外資動向，主力積累往往出現在股價啟動之前」**描述的是一個根本沒實作的東西**。`:230` 的 `event` 分支寫死「新業務（如HBM後段）」對**任何**觸發事件驅動的股票（食品/金融/營建）都會顯示。
- 🔴 **月營收 × 合約負債交叉判讀零實作** —— 資料兩邊都已在手（`tab_stock:265,289`），只差一個 4 象限判定，ROI 極高。
- ✅ **`compute_stop_levels`（`tab_stock:648-677`）已誠實化**：明講「固定方案盈虧比 T1 0.63x/T2 1.25x，與個股無關」、拿掉「≥1.5 較理想」假門檻、`:846` 補「現價已跌破紅K低點 → 分母為負」邊界。**全報告最佳實踐**。
- ✅ **v19.185 D1 已修 4 項**（`psy_checklist` 幽靈 key / 融資 `or 0` → 三態 / `regime` 改走 `get_macro_regime()` / 雙基期 → 單一 `_surge_pct`）；`section_health_score:39-56` 已修「單日外資廣播成整欄」、`:267-277` 移除 1,000,000 張假分母、`:241-253` 移除 `'vix': 15` 寫死。

#### 2. 具體改善優化方案

**新手友善化調整（三層漸進揭露）**
```
第一層 —「今天我該做什麼？」
  📌 即時趨勢總覽 + 🧭 一眼判讀（已存在且零重算 ✅ 保留）
  ★ 新增「決策卡」= 建議動作 + 唯一一個停損價 + 部位大小
     （7 個停損收斂成 1 個主建議，其餘進 Expander 並列出差異與距現價 %）
第二層
  📊 K線圖（MA 選擇器移到圖旁 st.popover）／🏥 健康度 6 因子
  ★ 新增「月營收 × 合約負債」4 象限圖（補上策略核心缺口）
第三層（Expander）
  停利停損／操作雷達／多因子／紅K錨點／SOP／買賣點／357／財報領先／D2
  🔬 AI 財報體檢 9 子段 → 改 st.tabs（生死／經營／獲利／結構／償債／綜合）
  🤖 AI 首席顧問（維持 button opt-in ✅）
```
- 25 個專有名詞白話文見 §8 附錄；`kpi()` 加 `term=` 參數後一次覆蓋 60+ 張卡
- 色彩：`shared/colors.py` 拆 `TW_UP`/`TW_DOWN`（台股慣例，K線/籌碼流向用）與 `SEMANTIC_GOOD`/`SEMANTIC_BAD`（燈號/評分用），**禁止混用**

**介面排版與按鈕瘦身計畫**
- 6 桶改 `st.tabs()`；6 個 MA checkbox 移到 K 線圖上方 popover
- 14 張 KPI 卡 → 第一層只留 4 張（趨勢/健康度/多因子/風險）
- 「操作前必做」5 個 checkbox 與「禁止操作」合併為一張 SOP 卡

**數據呈現與進階分析保留方式**
- **一格資料都不刪**，全部保留在第三層
- 缺資料的區塊改 ⬜ + 「為什麼沒有」，取代 0 / Pass / 50 / 15

#### 3. 程式碼重構建議

| 優先 | 項目 | 檔案:行 | 測試風險 |
|---|---|---|---|
| **P0** | **無 MA → 白送 15 分改 `None` + 分母降 70** | `scoring_helpers.py:160-162` | 🟡 **`test_scoring_helpers.py:156` 釘 `score==15`、`:125` 釘 `isinstance(score,int)`** |
| P0 | 「禁止操作」去 `abs()`，負向另立 `SOP_BAN_CRASH_PCT` | `psy_checklist.py:180,182,239` | 🟢 |
| P0 | `dragon_alert` 改 import `evaluate_leading_gates()` + 統一 AND | `section_dragon_alert.py:45-56` | 🟢 |
| P0 | 財報體檢 5 處假 Pass → N/A 不進分母 | `financial_health_engine.py:436,547,571,694,363` | 🔴 **`test_financial_health_engine.py:98-111` 把「全 N/A → Pass」釘成規格，屬政策決定** |
| P0 | `op_recommendation` 6 處捏 0 → `None` | `section_op_recommendation.py:92-110` | 🟢 |
| P1 | 22 處 `except: pass` 至少補 `print` | `tab_stock.py` ×15 + sections ×7 | 🟢 |
| P1 | `_precompute_xsec` 三處重算改傳參（`capital` 已示範） | `chips_20d:40`／`d2_leading:47`／`when_buy_sell:146,207` | 🟢 |
| P1 | 停損 7 數字 → 頁頂「停損總覽」單表 | 跨 4 檔 | 🟢（需視覺驗收） |
| P1 | 色彩拆 `TW_*` vs `SEMANTIC_*` | `colors.py` + 3 處 | 🟢 |
| P1 | `psy_checklist` 停損改吃 `calc_atr_stop`（`when_buy_sell:282` 已算過一次） | `section_psy_checklist.py:167` | 🟢 |
| P1 | 4 個純函式加 `@st.cache_data(ttl=TTL_1HOUR)` | `analyze_20d_chips_from_df` / `calc_rs_score` / `calc_leading_indicators_detail` / `compute_std_bands` | 🟢 |
| P1 | `vcp_bollinger` 補量能計算（或刪「帶量」文案）+ 統一 30/40/25 | `section_vcp_bollinger.py:73,91` | 🟢 |
| P2 | 接回 compute 層 SSOT（4 個 `check_*`） | `scoring_engine.py:1231,1250,1283,1306` | 🟡 會改變評分，需 golden test 對照 + user 裁示 |
| P2 | 合約負債分母改「近四季營收」+ capex 門檻重訂 | 3 處 `/capital` | 🟡 會改變觸發率，需裁示 |
| P2 | 357 統一股利口徑；D2 標題改「先行指標」或補 I6 | 2 檔 | 🟢 |
| P2 | 「4 訊號共振」加權重或改名；`rsi2` 接上或刪參數 | `section_op_recommendation.py` | 🟢 |
| P3 | ★ **新增月營收 × 合約負債 4 象限判讀** | 新 section 檔 | 🟢（新功能，需先做 §7 資料四問對齊） |

---

### 📌 3-6. 🔬 選股 → 🏆 個股組合（`tab_stock_grp.py` + `stock_grp_sections/` 6 檔）

**12 段、8 表、~70 欄**：①3 KPI 卡 L41 → ②輸入框+🚀批次分析 L44-71（上限 10 檔）→ ②b ☁️雲端儲存 L74 → ②c 🩺組合體檢 L77（**9 欄**）→ 批次抓取（無 UI）L81 → ③`section_portfolio_summary`（5 KPI L104 / 🔰故事化 L139 / **🏆組合排行總表 L162 = 14 欄** / 🎯型態目標價 L166 = 8 欄 / 📈維度拆解 L169 = 6 欄 / 📋多因子排行 L172 = 11 欄 / 🩹技術明細 L175 = 12 欄 + AI掃利空 / ⚠️風控警示 L183）→ ④🏥批次財報體檢 L94（摘要 7 / 經營 7 / 獲利 6 + 逐檔 expander×N 含 10 子模組）→ ⑤📊財報趨勢×轉機 L106（6+7 KPI、新鮮度條、9 欄表、2 expander）→ ⑥🎯三階段濾網 L108（S1 11 欄 / S2 9 欄）→ ⑦🤖AI投組判讀 L113 → ⑧🎚️風險貢獻 L126

`help=` 精確計數：`tab_stock_grp.py` 5、`stock_grp_sections/` **10（全部集中在 `section_portfolio_summary.py`，其餘 5 檔為 0）**。

#### 1. 現狀診斷與問題點

**資料稽核問題**
- 🔴 **抓取失敗灌 0 擊穿整套三態架構**（`section_batch_fetcher.py:263-270`，全檔唯一無 log 的 except）：寫 **literal `0`** 而非 `None` → `scorability.summarize_candidates:159` 的 `_as_float(...)` 得 `0.0` 非 None → **不進 `health_unknown_ids`，直接進 `eliminated`**；`section_portfolio_summary:93-96` 的 `_health_vals` 也收進 0 拉低平均；`:318` 讓總表印「健康度 0」。
- 🔴 **缺料偽裝成「通過」**（`tab_stock_picker.py:971-977`）：`_check_book_value` 只守分子 `_ca` 不守 `_liab` → FinMind 缺「總負債」→ 淨流動 = 流動資產 → **必回 `✅`** 並讓 `s1_pass_cnt` +1。
- 🔴 **「近 4 季 EPS」只要 1 季就加總**（`section_portfolio_summary.py:219-221`），欄名 `:322` 卻標 `EPS(4Q)`。
- 🔴 **`Cash_Gap_Days` 缺料 → 假綠燈**（`section_financial_health.py:347-349`）：`'N/A'` 過濾後為空 → `or '0'` → `0 <= 0` → `TRAFFIC_GREEN`。
- 🟡 **`_precompute_fund_map` 6 個裸 `pass`**（`:196-271`）→ 季報/股利/SQ/FGMS/P-B 全退化成 `'-'`，**與「這檔真的沒配息」完全同形**。
- 🟡 **AI 報告 cache key 缺日期與 regime**（`section_financial_health:53` / `section_ai_portfolio:54`）。⚠️ v1 說的「key 只取前 10 但跑全部」**不成立**（`tab_stock_grp.py:66` 已硬上限 10 檔），真問題是 `_fh_t3_last_key` **跨日不失效** → 隔天開頁沿用昨天財報體檢。

**UI/UX 與操作體驗問題**
- 🔴 **AI 投組報告有真 bug，且是顯示邏輯錯**（`section_ai_portfolio.py:55/74-78`）：`_t3ai_cached` 在**按鈕之前**讀 → 按下後才寫回 session → `:76 if _t3ai_cached:` 此時仍是 `''` → **不顯示**；`:78 elif not _t3ai_btn:` 為 False → **連提示都沒有**。使用者等 30 秒後畫面一片空白。且 `:74` `gemini_call_fn(...)` **無 try/except**。
- 🔴 **單頁 12 段、8 表、~70 欄**，標題 4 種風格並存（`####` / `#####` / `**粗體**` / 自繪 HTML div，**全站 0 個 `st.subheader`**）；「無法評分」詞彙 5 種；`st.columns(7)` 全站最寬。
- 🟡 **`section_financial_health` 7 個 metric 0 個 help、無 banner 彙總** —— 使用者必須逐一展開 10 個 expander 才知道有幾檔沒抓到。**範本就在隔壁檔**（`section_portfolio_summary` metric 6/6 全覆蓋）。
- 🟡 **「🚀 一鍵更新總經」按鈕不存在**：`section_market_status.py` 全檔 **0 個 `st.button`**，`:52-57` 未載入時只印「⬜ 總經未評估」不告訴使用者去哪；而 `scoring_regime_gate.notice()`（`:131-140`）**已寫好完整指引**（「按🚀一鍵更新全部數據，或先開 🌍 總經頁」）卻只在 `section_batch_fetcher:285` 被用一次。
- ✅ **「10 列重複無法評分」的既有抱怨已修**（`_render_fin_trend_table` L691-838）：`split_trend_rows` 切出無法評分列 + 第 6 個 KPI 帶 `help` + `st.warning` 點名 + 排序排到表尾 + 數值欄一律 `'—'`。**這是本範圍「三態誠實」的標竿實作**。

**程式碼問題**
- 🔴 **UI 層 4 處裸 `requests.get`**（`tab_stock_picker.py:783/999/1166/1220`）：`timeout=15`、無 proxy_helper、無退避、無快取；配 `:455 max_workers=5`、`:423-425` 上限 30 檔 → **最壞 120 次未受管控 FinMind 請求併發 5**。且四處皆 `from src.data.core.data_loader import _fm_raw_headers`（**private symbol，V-PICKER-PRIV-1**）。
- 🟡 **`section_portfolio_summary.py:44-49` module top-level 直 import 3 個 L1 fetcher**（非 lazy，module load 即拉全依賴鏈）。
- 🟡 **`_dates[4]` 位置索引當去年同季**（`tab_stock_picker.py:814,1025`）—— **L2 `shortage_screener.py:17` 已明文修掉**（「不用 list 位置 —— 季序列有洞時位置 4 ≠ 去年同季」），**L5 沒跟上**。橫向重複實作計數：`tab_stock_picker.py` **23 處**、`data_loader.py` 15、`shortage_screener.py` 14。
- 🟡 **`tab_helpers.py:90-109`**：剛 import `HEALTH_GRADE_A_MIN/B_MIN`，`:96/98` 立刻 inline `75`/`55`；**`:106/109` 的 `pts >= 7 / 4` 連常數都不存在**（比 75/55 更隱蔽）。
- ✅ **regime gate 接線正確**（`section_batch_fetcher.py:86/251/285`）：`resolve_scoring_regime(get_macro_regime())` + `usable` 守門 + `notice()` 提示，舊的 `.get('regime') or 'neutral'` 已完全清除。**全 repo regime 治理最好的一處**。但 `scoring_engine.py:299/308/415` 三處預設值未改 → **gate 是唯一防線**。
- ✅ **`_batch_scoring_regime`（`section_portfolio_summary.py:362-392`）是 provenance 教科書案例**：從 `score_single_stock` 回傳的 `regime` 戳記反推「這批分數**實際用過**哪組權重」，`:533-538` 比對當下 regime 不同時 `st.warning` 提醒重跑。

**金融邏輯問題**
- 🟡 **財報趨勢×轉機門檻全 inline 在 UI**（`tab_stock_grp.py:588-589` 的 `±1.5/±0.5` 寫在 caption 字串、`:600 value=0.65` 寫在 slider）。**但缺料處理是全案最嚴謹的**（`split_trend_rows` + `no_snapshot ≠ first_snapshot` 粒度區分），值得反向推廣到財報體檢頁。

#### 2. 具體改善優化方案

**新手友善化調整**
```
第一層：🚦大盤燈號 + 建議持股（★補「🚀一鍵更新總經」按鈕）
        5 張 KPI（現有 ✅）+ ★一句白話結論「你的 8 檔裡，3 檔體質轉強、2 檔有風控警示、1 檔資料不足」
第二層：🏆 組合排行總表 → 從 14 欄縮成 6 欄主表（代碼/名稱/健康度/多因子/操作狀態/警示）
        📊 財報趨勢×轉機（已是最佳缺料處理 ✅ 保留）
第三層：維度拆解 / 基本面明細(11欄) / 技術明細(12欄) / 型態目標價(8欄)
        🏥 批次財報體檢（4 子表 + 逐檔）→ 改 st.tabs
        🎯 三階段濾網（15 個 checkbox）/ 🎚️ 風險貢獻 / 🤖 AI 判讀（button opt-in ✅）
```

**介面排版與按鈕瘦身計畫**
- 12 段 → **4 個 sub-tab**：`📊 排行` / `🏥 財報體檢` / `🎯 濾網選股` / `🤖 AI 判讀`
- 標題統一 `st.subheader` + `####`；「無法評分」詞彙統一為 **`⬜ 未評估`**
- 5 個 AI 按鈕收斂；`st.columns(7)` 改響應式

**數據呈現與進階分析保留方式**
- **~70 個欄位一個不刪**：主表精簡 + Expander 完整（**`etf_tab_grp_compare` 的「主表 11 欄 + expander 24 欄」直接照抄**）
- `section_financial_health` 補「⚪ 未體檢 N 檔」banner（照抄 `_render_fin_trend_table`）

#### 3. 程式碼重構建議

| 優先 | 項目 | 檔案:行 | 測試風險 |
|---|---|---|---|
| P0 | 失敗列 `'健康度': 0` → `None` + 補 log | `section_batch_fetcher.py:263-270` | 🟡 需補 None 流向下游的測試（slow lane `continue-on-error` 不阻擋 = 沒安全網） |
| P0 | AI 投組補 `st.rerun()` + try/except + cache key 加日期與 regime | `section_ai_portfolio.py:55,74-78` | 🟢 |
| P0 | `_check_book_value` `_liab` 對稱守衛 | `tab_stock_picker.py:972` | 🟢 |
| P0 | `EPS(4Q)` 改 `len==4` 才給值 | `section_portfolio_summary.py:219` | 🟢 |
| P0 | `Cash_Gap_Days` 缺值走 ⬜ | `section_financial_health.py:347` | 🟢 |
| P1 | 4 處裸 `requests.get` 下沉 `picker_fetcher.py` + 快取 | `tab_stock_picker.py:783,999,1166,1220` | 🟡 順帶結案 V-PICKER-PRIV-1，需同步 C3 白名單 |
| P1 | `_precompute_fund_map` 6 個 `pass` → 標「⚪ 取數失敗」 | `section_portfolio_summary.py:196-271` | 🟢 |
| P1 | `final_recommendation` 75/55 → SSOT；`pts 7/4` 新建常數 | `tab_helpers.py:96-109` | 🟢 |
| P1 | `section_market_status` 補「🚀 去總經頁」按鈕（沿用 `notice()`） | `section_market_status.py` | 🟢 |
| P1 | 財報體檢補 banner + 統一詞彙 + 補 7 個 help | `section_financial_health.py` | 🟢 |
| P2 | `_dates[4]` 改按 `(year-1, same_quarter)` 查表（抄 L2） | `tab_stock_picker.py:814,1025` | 🟢 |
| P2 | 12 段改 4 個 sub-tab | `tab_stock_grp.py` | 🟢（需視覺驗收） |
| P2 | 財報趨勢門檻抽 SSOT | `shared/` + `tab_stock_grp.py:588,600` | 🟢 |

---

### 📌 3-7. 🔬 選股 → 🔭 選股網（⚠️ inline 在 `app.py:485-700`，216 行，違憲 V-APP-1）

**渲染順序**：標題 L488 → ①基本面優選 L498（**11 欄**）→ ②因子 multiselect L502-507 → 🎯開始選股 L510-538 → 未跑提示 L541 → **結果區 L543-666**（總覽卡 L568-592、結果表 L593、CSV L594、🧊凍結 L599-624、📊對帳 expander L626-656 = **7 欄**、🧬AI總結 L657-666）→ 🌍全台股跨季趨勢 expander **L668-700（8 欄）**

`help=` 於 L485-700 = **0**。

#### 1. 現狀診斷與問題點

**資料稽核問題**
- 🔴 **三處掃描失敗只 `print`**（`app.py:519/530/537`）：勾 4 因子、掃壞 1 個 → 綜合分實際只用 3 因子，而勾勾還在。所幸 `composite_rank_candidates:402-406` 的 note 會說「尚未掃描」，**但「掃描失敗」與「尚未掃描」文案相同**，且 print 不進畫面 → 使用者被引導去重按，可無限循環。
- 🔴 **存活池 `None` 與 `0` 同形**（`:564`）：`_surv_n = len(_surv_df) if _surv_df is not None else 0`，快照不可用（`:546-548` 只 `print`）與真的 0 檔畫面一樣。
- 🟡 **財報快照無 vintage**（`fundamentals_snapshot_loader.py:47`）：每季兩趟 cron（截止+1週／+5週）覆寫同檔名 → **已凍結的 cohort 事後無從還原當時看到的存活池**。⚠️ 但 `latest.json` 有 `updated_at`（`describe_snapshot_coverage:151` 有用）→ 不是「零 provenance」。
- ✅ **PIT 主幹嚴謹**：`shared/staleness.py:641-662` 的 `latest_published_quarter` 明確 `grace_days=0` 並註「它回答的是法律問題（該公布了嗎）」，`TW_QUARTER_STATUTORY_DUE:571-576` 把 Q4 年報 3/31 與 Q1-Q3 +45 天分開。**全 repo 最嚴謹的 PIT 實作**。⚠️ 唯 `:648-651` 自陳 `scripts/update_fundamentals_snapshot.py` 另有逐字複本待收斂。
- ✅ **`forward_test.py:7-13` 是最佳文案樣板**：檔頭三行 ✅/✅/⚠️ 界定偏誤範圍，`:218-229` 明講「這些多半是最壞結局，故上列報酬**偏樂觀**（存活者偏誤）」。

**UI/UX**
- 🔴 **216 行 0 個 `help=`**。術語全裸：存活池、綜合評分、缺貨動能、抗跌RS、跨季轉強、前進式驗證、lookahead、存活者偏誤、贏0050率% vs 勝率%。
- 🟡 **`🌍 全台股跨季趨勢排行` expander 起於 L669、縮排 8 空格**，與 `:541 if not _screener_ran:` 同層 → **在 gate 之外，未按「開始選股」也會渲染**，與 `:542` 的「👆 勾好條件後，點🎯開始選股」直接矛盾。
- 🟡 **前進式驗證表缺兩個關鍵欄**：`_ft_cols`（`:650-656`）不含 `n_dropped` 也不含 `enough_sample`，使用者無法逐 cohort 判斷哪一批被剔除得多。
- 🟡 CSV 名不副實（排名跑 300 檔、下載只給 50）；7 個控制項缺 5 個 `use_container_width`。
- 🔴 **未包 `_render_tab_isolated`**。

**程式碼問題**
- 🟡 **結果區無 button gate**（`:543-554`），但**嚴重度可降級**：`get_fundamental_survivors` / `fetch_pe_name_maps` 皆 `@st.cache_data(ttl=TTL_1DAY)`，`get_ranked_picks(auto_fetch=False)` 是純 CPU（~324 ids × 5 因子百分位）→ 屬 **CPU 浪費非 API 風暴**。
- 🟡 **缺貨深掃純序列**（`shortage_screener_service.py:124-137`）：每檔 2 次 FinMind、零併發，上限 50 → **100 次序列往返**。而同層 `rs_leader_service.py:96-103` **已用 `ThreadPoolExecutor`** —— 照抄即可。
- 🟡 inline magic：`top_n=300` / `head(50)` / `head(20)` / `head(100)` / `head(15)`。

**金融邏輯問題**
- 🔴 **`_market_context` 0.0% bug**（`rs_leader_service.py:113`）：`_down = bool(ret < 0)` **無 dead band**，上游 `rs_leader_screener.py:204` `round(...,2)`，顯示 `{ret:+.1f}` → `-0.04` 印「📉 約 -0.0% 屬下跌」、`+0.04` 印「📈 約 +0.0% 大盤其實在漲」。**更嚴重**：`(-0.005, 0)` 區間 `round` 產生 **`-0.0`**，而 `-0.0 < 0` 為 `False` → 印出**自相矛盾**的「📈 約 -0.0% — 大盤其實在漲」。且此 banner 被 `build_rs_ai_prompt` **原文餵給 LLM**。緩解：`is_down` 零消費端，只影響文案。
- 🟡 **前進式驗證基準只有 1 年窗**（`forward_test_service.py:131`）→ 超過 1 年的 cohort 靜默略過（`benchmark_returns_from_close:124-125` `if _prior.empty: continue`）。所幸 `:230-233` 有 `n_cohorts_no_bench` note **揭露** → 「誠實但功能受限」。另 cohort 標籤日用 `_tw_now()` 而非 `_bdf` 實際最後交易日（cron 假日跑時偏差 ≤3 天）。
- 🟡 **`_percentile_scores` 在 `len(valid)==1` 時直接給 100 分**（`fundamental_screener_service.py:294-295`）→ 該因子全市場只有 1 檔有值時（如缺貨掃描）**直接衝榜首**。既有的 `SCREENER_MIN_FACTOR_COVERAGE_RATIO`（`:372-384`）擋的是「個股勾選因子數不足」，擋不住這個。
- ⚪ **綜合分是 5 因子等權百分位平均，但資料成熟度差 5 倍以上**：`估值分`/`EPS分` 覆蓋全存活池（~324），`RS分` 覆蓋 `RS_SCAN_MAX`，`缺貨分` 上限 50（`:419-425` 已誠實揭露覆蓋分母）。**小母體因子的百分位分佈更集中在高分** → 有缺貨分的 50 檔天然佔優。這是可解釋性問題不是 bug。

#### 2. 具體改善優化方案

**新手友善化調整**
- 每個因子 multiselect 選項掛 `show_term_help`；存活池總覽卡加 `help='存活池＝四項基本面全過的股票，本次共 N 檔（依 {季別} 法定公告資料）'`
- 結果表加「為什麼入選」欄位（各因子分數拆解）
- 前進式驗證表加「剔除檔數」與「樣本足夠」兩欄

**介面排版與按鈕瘦身計畫**
- `🌍 全台股跨季趨勢排行` 縮進 `else:` 內，並與「跨季轉強」因子**合併為單一入口**（現在是兩個入口、兩顆按鈕、兩個 session key）
- CSV 按鈕改「💾 下載前 50 名 CSV」或給 `st.radio(['前50','全部300'])`

**數據呈現與進階分析保留方式**
- 三層：KPI 卡（存活池/入選數/命中因子）→ 前 10 名精簡表 → Expander 完整 50 名 + 因子拆解
- 掃描失敗的因子**明確標示並從排名中移除**，總覽卡「本次因子」文字同步

#### 3. 程式碼重構建議

| 優先 | 項目 | 檔案 | 測試風險 |
|---|---|---|---|
| P0 | 三處掃描失敗 → `st.warning` + 從 `_factors` 移除 | `app.py:519,530,537` | 🟢 |
| P0 | 存活池 `None` vs `0` 區分 | `app.py:564` | 🟢 |
| P0 | `_market_context` 補中性帶 + banner 改 `{ret:+.2f}` | `rs_leader_service.py:113-119` | 🟢 |
| P1 | forward_test 基準改 `5y` + cohort 用實際最後交易日 | `forward_test_service.py:131` | 🟢 |
| P1 | `🌍 跨季趨勢` expander 縮進 gate 內 + 合併入口 | `app.py:669` | 🟢 |
| P1 | 缺貨深掃改 ThreadPool（抄 `rs_leader_service:96`） | `shortage_screener_service.py:124` | 🟢 |
| P1 | 結果存 `session_state['_screener_cands']`（key 綁 `tuple(_factors)`） | `app.py:543-554` | 🟢 |
| P2 | **V-APP-1 結案：216 行抽 `src/ui/tabs/tab_screener.py`** | `app.py:485-700` | 🟡 **`test_app_tab_wiring.py:47` 要求 `with tab_screener:` 字面存在** |
| P2 | `_percentile_scores` `len(valid) < 5` 時不給極端分數 | `fundamental_screener_service.py:294` | 🟢 |
| P2 | 財報快照加 vintage | `scripts/update_fundamentals_snapshot.py` | 🟢 |

---

### 📌 3-8. 🏦 ETF → 🔍 單檔診斷（`etf_tab_single.py` 960 行 + `etf_tab_smart.py` hook ×3）

**26 段**：配置橫幅 L90 → 代號輸入 L92 → PROXY 健診 L110 → 標題 L163 → 🚦綜合研判卡 → 4 metrics(收盤/費用率/Beta/**AUM**) L188 + 說明 expander → 經理人+異動 L206 → ⭐品質評等 L246 → 策略一以息養股 L255 → 💧配息健康度 4 卡 + 平準金 L289 → 策略二 7%估值 L359 → 策略三 VCP L420 → 🛡️折溢價+追蹤誤差 L452 → 淨值折溢價表(5欄) L550 → 📐BIAS L591 → 📅長線σ L611 → 📉季線×趨勢 L646 → 🚨存股三大訊號 L680 → 🏆同儕排名 L766 → 近5年走勢 L798 → 🧩成分股 L802 → **hook L856-866**（3-3-3 → 標準差帶 → 分散度）→ 🧠AI白話總結 L868-957

#### 1. 現狀診斷與問題點

**資料稽核問題**
- 🔴 **3-3-3 的 C3 結構性永遠算不出來，且對使用者說謊**：`etf_tab_smart.py:33-35` 同儕價格只抓 `period='2y'`，但 `etf_smart_analysis.py:519` 要求 `ay >= 2.5` → `peer_ann_rets` 恆空 → `c3_pass=None` → `:535 if all(p is not None ...)` **永不成立** → 「🏆 三項全過！」是死碼。更糟：使用者勾了「啟用同儕排名（較慢）」等 15–30 秒後，`:438` 回 **`'N/A（未啟用同儕排名）'`**。
- 🔴 **N-4 `etf_fetch.py:214` 對原始 OHLCV 靜默 `ffill()`**（無 log、無 `is_imputed`），而同檔 `:1960-1962` 才剛寫明「移除原 `close.ffill()`：把『沒有交易』偽裝成『持平』，§4.6 明文禁止」。`_fetch_etf_price_max` 是**全 ETF 頁唯一的價格來源**。
- 🔴 **N-5 AUM 幣別（v2 定案，含第三處）**：
  - `etf_fetch.py:331` `aum_twd = float(...) * 1e8`（億→元 TWD）→ `:435-436` 填進 `totalAssets`；`signal_thresholds.py:920-924` 寫「億 TWD」；`etf_quality.py:53` 寫 `# AUM in TWD` → **口徑是 TWD**
  - ❌ **錯誤處 1&2**：`etf_tab_single.py:195` `f'{aum/1e9:.1f}B USD'`、`:918` AI prompt `f"{aum/1e9:.1f}B 美元"`（0050 約 5,000 億 TWD → 畫面印「500.0B USD」）。且同檔 `:202` expander 自己用「億」推理 → **檔內自相矛盾**
  - ❌ **錯誤處 3（v1 沒抓到）**：`etf_quality.py:54-55` / `etf_scoring_helpers.py:36` 以 **TWD 10億/100億** 為刻度，卻直接吃 `totalAssets` —— 美股 ETF 該欄是 **USD** → 一檔 $8 億 USD（≈250 億台幣）的美股 ETF 被算成 `log10(8e8)=8.9` → **AUM 得 0 分**，白扣 8%(多檔)/30%(品質)權重
- 🔴 **`check_333_criteria` 兩處 `except: pass`**（`etf_smart_analysis.py:490-491` C2、`:530-531` C3）→ 靜默降級成「N/A」，與「真的資料不足」外觀完全相同。
- 🟡 **資料不足回 `0.0` 被當真值進評分**（`etf_calc.py:698-699` 夏普 `len(ret)<20`、`:674-675` CAGR `days<30`、`:682-684` 例外）→ `_norm(0.0,1.0,0.2)=0.0` **拿最低分並佔用權重**，而 `etf_scoring_helpers.py:154-159` 明明支援「缺項 rescale 有效權重」→ **新上市 ETF 系統性低估星等**。同理 `calc_current_yield`（`:223-224`）把「抓失敗」與「真的不配息」都回 `0.0`。
- 🟡 **RSV `.fillna(50)`**（`etf_tab_single.py:605`）：填 50 的是 RSV。前 8 根暖機期無害，**但「9 日內最高＝最低」（連續跌停/停牌）是真造假**，且 `_kv_ai`/`_dv_ai` 進 session 再進 AI prompt（`:905-907`）。
- 🟡 **`calc_bias_pct(...) or 0.0` 共 5 處**（v1 說 3 處）：`etf_tab_single.py:628,667,724,735` + **`etf_render.py:455`**（後者影響最大，bias=None 時顯示「⚪ 中性偏離，正常波動」）。
- ✅ **折溢價 `stale_nav` 分四態**（`etf_calc.py:387/435/440/452/477`，各帶 `nav_date`/`price_date`/`premium_raw`/`prem_max`）—— **比 v1 說的三態更細，全站最好的 §1 實作**。另 VaR `align_portfolio_returns` 只取共同交易日並揭露「受最短檔壓縮」；匯率取不到即排除美元持股並紅字；經理人 `tenure_approx`；平準金誠實說明「無穩定 API 故不顯示」並附手動查法；`_check_sector_exposure`（`etf_render.py:591-621`）把「對映不到 GICS」獨立成 ⚪ 無法判定、不亮假紅燈。

**UI/UX**
- 🟡 **`help=` 實測 7 個 / 互動元件 5 個**（v1 的「33 個控制項」分母錯，多數 help 掛在 `st.metric` 上）。**真正的缺口在 `etf_tab_smart.py`（9 元件 1 help）與 `etf_tab_ai.py`（4 元件 0 help）**：觀察窗口 120/252/500 selectbox、「🔗 計算分散度」按鈕、AI 自由提問框全裸。
- 🟡 **「填息」全 ETF 頁零出現**（全 `src/` grep 只命中一檔 ETF 中文名）。高股息是本 App ETF 頁的核心族群，而「除息後股價有沒有漲回去」是判斷好壞的第一課。
- 🟡 **標準差帶說明寫死 252 與選擇器脫鉤**（`etf_tab_smart.py:109-112` caption 固定寫「過去 252 個交易日」，`:120-126` 卻讓使用者選 120/252/500）；且 `etf_smart_analysis.py:80` `_w = min(window, len(s))` **靜默縮窗**（`_cached_price` 只抓 2y ≈490 根，選 500 實際只有 ~490）→ **兩層都被誤導**。
- 🔴 **未包 `_render_tab_isolated`**。

**程式碼問題**
- 🟡 **V-SMART-CACHE-1**：`etf_tab_smart.py:26/32/38/49/56` 五個 inline TTL，全檔無 `from shared.ttls import`（**ETF 目錄唯一違規者**，`etf_fetch` / `grape_ladder` / `etf_quality` 都正確 import）。
- 🟡 **`_cached_zh_name`(86400) 白包在 L1 `fetch_etf_zh_name`(TTL_7DAY) 外**（`etf_fetch.py:2070`）→ 反過來若 L1 被 `st.cache_data.clear()` 清掉（`etf_tab_portfolio.py:557` 的「🔄 強制重抓」會清全站），外層仍持舊值 → **同一頁面兩個中文名可能不同步**。
- ⚠️ **「同一 ticker 四種 period 各抓一次」網路層不成立**：`etf_fetch.py:190-252` v18.228 已集中為 `_fetch_etf_price_max(ticker)` + 記憶體切片。**但記憶體層成立**：`_cached_price`(2y) 與 `_cached_price_long`(5y) 又各複製一份進 Streamlit cache，TTL 各不相同（3600/1800/7200）→ **同一份資料存三份且可能不同步**。
- 🟡 **`max_entries` 卡在 10**（`etf_fetch.py:255` dividends、`:411` info；`:197` price=20）：多檔比較上限就是 10 檔，加上每檔 benchmark 與品質評等內部再抓 info/divs → **單次批次就超過 10 → LRU 互相驅逐**，「已快取秒回」的承諾跳票。
- 🟡 **N-13 分散度混用 2 維與 3 維直接比大小**（`etf_tab_smart.py:309` `[:30]` vs universe ~48 檔），且 `:403` `_d.drop(columns=['可用維度'])` **把唯一能看出差別的欄位刪掉**。

**金融邏輯問題**
- 🔴 **品質評等 Beta 因子讓債券 ETF 必得 0 分**（`etf_quality.py:63-64` `_BETA_HI=0.1/_BETA_LO=0.8` + `:111-116` `abs(β-1)`，佔 20% 權重）—— **而同一個 App 在 `etf_tab_portfolio.py:456` 與 `etf_tab_smart.py:391` 印「真正的抗跌來自債券/現金」**。使用者照建議買 00679B，回到單檔頁看到它品質 2★、最弱項「Beta 合理性」。
- 🟡 **標準差帶對「價格水準」而非「報酬」做常態假設**（`etf_smart_analysis.py:81-82`）→ 長期上漲的 0050 會長期貼 +1σ~+2σ，`:104` 判 `caution`/`sell`，UI 文案「越靠近 +2σ = 相對高點，注意風險」→ **對趨勢型 ETF 等於長年叫人減碼**。另 `.std()` 是 ddof=1 未揭露（與 `etf_calc.py:174` 一致，無矛盾，但未寫文件）。
- 🟡 **3-3-3 C1 的成立年數用 `px.index[0]`**（`etf_smart_analysis.py:466-471`）而 `_cached_price_long` 只給 5y → **任何成立超過 5 年的 ETF 一律顯示「5.0 年」**；而單檔頁 `:306-314` 已有更準的 `firstTradeDateEpochUtc`。同一頁上下捲動，0050 的成立年數兩個數字。順帶 `:523-526` `sorted_rets.index(my_ret)` 用**值**查排名，同分時排名偏樂觀。
- 🟡 **分散度相關係數 NaN → `pr=0.0` → `pr_norm=0.5`** 被當「零相關」實測值進加權（`etf_smart_analysis.py:310-312`）→ **新 ETF 系統性被推薦成好的分散標的**。
- ✅ **分散度矩陣是罕見的優秀設計**：三維加權（價格相關 0.4 / Jaccard 0.4 / 類別 cosine 0.2）+ **空頭相關**（`_downside_corr_series:225-244` 只取「跌最凶的 20% 交易日」重算）+ `:391` 明說「真正的抗跌分散要靠**不同資產類別**」。**不賣弄指標、直接講後果**，全站少見。
- ⚪ 3-3-3 用 UTC 當「今天」（`:463`），台北早上 8 點前差一天。無 bug 觸發，知悉即可。

#### 2. 具體改善優化方案
**新手友善化**：3-3-3 C3 三態化（`✅前1/3` / `❌未達` / `⬜同儕資料不足（需 2.5 年，目前 2 年）`）；標準差帶加警語「本帶以**價格水準**計算，長期上漲的 ETF 會長期停留在上緣，**不等於該賣**」+ 縮窗時顯示實際天數；補「填息」名詞；31 個 metric 補 `help=`（文案見 §8）。
**排版瘦身**：26 段收三層（L1 綜合研判卡 + 4 metrics + 品質評等｜L2 折溢價 + 配息健康度 + 近 5 年走勢｜L3 三大策略/BIAS/σ買點/季線警示/存股三訊號/同儕/成分股/3-3-3/標準差帶/分散度）；建立 app 級 `st.session_state['etf_focus_ticker']` 統一三頁 ticker 輸入（目前**四組輸入框分佈三頁**）。
**進階分析保留**：26 段一段不刪，全數保留在 Expander；AI 白話總結維持置底 ✅。

#### 3. 程式碼重構建議
| 優先 | 項目 | 檔案:行 | 測試風險 |
|---|---|---|---|
| P0 | **AUM 幣別三處統一**（`:195`/`:918` 改 `f'{aum/1e8:,.0f} 億'`；評分層依 `holding_currency` 換算） | `etf_tab_single.py` + `etf_quality.py` + `etf_scoring_helpers.py` | 🟡 `:918` 若在 `_sections` 內會進 `test_ai_prompt_thresholds.py:137` 掃描範圍 |
| P0 | 拔掉 `_fetch_etf_price_max` 的 `.ffill()`（或改顯式 + `attrs['imputed_rows']`） | `etf_fetch.py:214` | 🟡 |
| P0 | 3-3-3 C3 同儕改 `5y` + 文案三態化 | `etf_tab_smart.py:33` / `etf_smart_analysis.py:519,438` | 🟢 |
| P0 | ETF 三頁補 `_render_tab_isolated` | `app.py:714,726,730` | 🟡 見 §4 |
| P0 | **V-SMART-CACHE-1：5 個 TTL 換常數** | `etf_tab_smart.py` | 🟢 **零測試** |
| P1 | `check_333_criteria` 2 處 `except: pass` → log + `c2_err`/`c3_err` | `etf_smart_analysis.py:490,530` | 🟢 |
| P1 | 5 處 `or 0.0` → `is None` 分支 | `etf_tab_single.py` ×4 + `etf_render.py:455` | 🟢 |
| P1 | 資料不足回 `0.0` → `None`（夏普/CAGR/殖利率三態） | `etf_calc.py:674,682,698,223` | 🟡 |
| P1 | RSV `fillna(50)` 只套暖機段 | `etf_tab_single.py:605` | 🟢 |
| P1 | 相關係數 NaN 走「維度不可用 rescale」而非塞 0.5 | `etf_smart_analysis.py:310` | 🟢 |
| P2 | `_cached_zh_name` / `_cached_price` / `_cached_price_long` 三個 L5 wrapper 刪除，直呼 L1 | `etf_tab_smart.py` | 🟢 |
| P2 | `max_entries` 10 → 100/300 | `etf_fetch.py:255,411` | 🟢 |
| P2 | Beta 因子依 `role` 切換或對債券 ETF 回 `None` | `etf_quality.py:111` | 🟡 會改變星等，需裁示 |
| P2 | 3-3-3 C1 改吃 `firstTradeDateEpochUtc`；排名改 `sum(1 for r if r > my_ret)` | `etf_smart_analysis.py:466,523` | 🟢 |
| P2 | 分散度保留「可用維度」欄 + `[:30]` 提高到全 universe | `etf_tab_smart.py:309,403` | 🟢 |

---

### 📌 3-9. 🏦 ETF → 📊 多檔比較（`etf_tab_grp_compare.py` 316 行）

**8 段**：標題 L108 → textarea(≤10檔) → ThreadPool(5) 抓 5y + session cache L126 → 合成分 + 留/觀察/換 L159 → 5 統計卡 L173 → **主表 11 欄 L280** → **expander 完整 24 欄 L287** → 權重說明 L293

#### 1. 現狀診斷與問題點
- ✅ **本頁是全站漸進式揭露最佳示範**（`:277-292`，且 `:285-286` 明說「主表為 11 個決策核心欄…完整指標見下方 ⬇️」）→ **建議把這個 pattern 複製到 ETF 組合持股明細（16 欄）與個股組合排行總表（14 欄）**。
- 🔴 AUM 幣別（同 3-8，此頁走 TWD 口徑，本身正確；受評分層 USD 問題連帶影響）。
- 🟡 **session cache 無 TTL 無清除入口**（`:132-134` `_cache_key = f'_etf_grp_results_{hash(tuple(tickers))}'`）：`hash()` 同 process 內穩定所以碰撞不是主要風險，**真問題是使用者隔天回到同一 session 再按「🎯 開始批次評分」會直接拿到昨天的 rows，價格與星等全是舊的且毫無提示**，而本頁沒有組合頁那種「🔄 強制重抓」。
- 🟡 **每檔各抓一次 benchmark**（`:87-89`）：10 檔台股全回 `'0050.TW'` → `fetch_etf_price('0050.TW','5y')` 呼叫 10 次。網路只 1 次（L1 快取），但 10 次切片 + 10 次 pandera 驗證在 5 個 worker 上重複。
- 🟡 **費用率兩套來源**（新發現）：單檔頁走 `get_etf_expense_ratio_safe`（4 段備援 MoneyDJ→SITCA→Yuanta→yfinance），本頁共用的 `build_etf_score_row` 走 `etf_scoring_helpers.py:106` 的 `info.get('annualReportExpenseRatio')` 單一鍵，而 `fetch_etf_info:439` 只補了 MoneyDJ → **SITCA/Yuanta 兩段 fallback 完全用不到** → 同一檔在單檔頁有費用率、在多檔表卻空白，連帶 12% 權重被 rescale 掉。
- 🟡 **7 維權重只有一行 caption**（`:294-296`），且該行是 `_WEIGHTS`（`etf_scoring_helpers.py:19-37`）的**逐字手抄複本**。

#### 2. 具體改善優化方案
- 主表 11 欄每個欄名補 `help=`；7 維權重改可展開表格（維度/權重/計算方式/資料來源）並用 f-string 插值
- 「🚦 怎麼看」info 移到主表**上方**（結論在前）；加「🔄 重抓」按鈕 + 顯示 `fetched_at`
- 加「匯出 CSV」

#### 3. 程式碼重構建議
| 優先 | 項目 | 檔案 |
|---|---|---|
| P0 | 補 `_render_tab_isolated` | `app.py:726` |
| P1 | session cache 加 `fetched_at` + 「🔄 重抓」清 key；key 改 `'|'.join(sorted(tickers))` | `etf_tab_grp_compare.py:132` |
| P1 | benchmark 批次前先抓好傳入 | `:87-89` |
| P1 | `build_etf_score_row` 加 `expense_ratio=None` 參數由 caller 注入（保持 L2 零 I/O） | `etf_scoring_helpers.py:106` |
| P2 | 7 維權重 SSOT 上抽 `shared/signal_thresholds.py::ETF_SCORE_W_*` + caption 插值 | `etf_scoring_helpers.py:19` + `:294` |

---

### 📌 3-10. 🏦 ETF → ⚖️ ETF 組合（`etf_tab_portfolio.py` **1,825 行** + 葡萄串 + smart ×3 + AI）

> ⚠️ **v1 因 CDN 截斷，第 1274 行之後完全沒讀到。v2 已補完。**

**24 段 + 4 個附掛區**：橫幅 L179 → data_editor L181 → 💾雲端儲存 L233 → 容忍度+gate L235 → ThreadPool(6) L285 → **單一換匯點 L357** → 🧭股債比 + 🧱核衛 bar L433 → 資產總覽 L507 → 新鮮度條 L537 → **持股明細 16 欄 L562** → 🛰️戰情室(核10/衛9/其他7欄) L620 → 🎯核衛 vs regime L723 → ⚖️再平衡 L801 → 🏗️產業曝險 L863 → 🔗相關矩陣 L867 → 🎚️風險貢獻 L894 → 🧩成分股 L905 → 🧬Overlap(逐對9欄) L925 → 🎯弱勢度 L1000 → 🧨壓測 L1034 → 📉VaR L1061 → 📈vs0050 L1144 → 📐效率前緣 L1203 → **💰配息日曆 L1245-1394（6 欄表 + 長條圖 + 每月矩陣 18 欄）** → 💰稅後試算 L1398 → 寫 `etf_portfolio_data` L1452 ｜ 接著 📅葡萄串 → 3-3-3 → 標準差帶 → 分散度 → 🤖 ETF AI

#### 1. 現狀診斷與問題點

**資料稽核**
- 🔴 **AI prompt 假偏離（憲法已預告未修，v2 確認）**：`:427-428` `r['target_pct']=r['actual_pct']; r['deviation']=0.0`（`:425-426` 註解自陳「已知殘留」）→ `etf_tab_ai.py:123-124` 印「（偏離 +0.0pp）」。**畫面誠實顯示「—」（`:593/:595`），AI 卻拿到假的完美貼合。**
  ❌ **`loss_pct` 那半條不成立** —— `:1042/:1457` 一定寫入真值，`.get(...,0)` 只在舊版 session 殘留時才觸發。
- 🟡 **27 處 `except`**（v1 說 26）：多數是「單項失敗不炸整頁」的合理設計且有 `print`。**但兩處吞掉後畫面完全無感**：`:495-496`（🧭股債比 + 🧱核衛 bar 整段消失）、`:571-573`（`_etf_name` helper 失敗 → 全表名稱欄靜默退化成 ticker）。

**UI/UX**
- 🔴 **24 段全展開 + 持股明細 16 欄**（其中「均價(原幣)/現價(原幣)/成本(TWD)/現值(TWD)」四欄新手極易混讀）+ 每月配息矩陣 18 欄。**而隔壁「📊 多檔比較」頁已有正確示範**。
- 🟡 Sheet ID 三個入口（Sidebar / 本頁雲端儲存 / 組合管理頁 ×2）。
- 🟡 `use_container_width` 26 處 + `width='stretch'` 1 處，**全站最大單點混用**。
- ✅ **`help=` 覆蓋率 79%（24 元件 19 個）**，全站第二好。
- 🔴 **未包 `_render_tab_isolated`，且一次串 6 個渲染器** —— `render_etf_portfolio` 是全站最長的單一 render，任一 uncaught 例外炸掉整個 app。

**程式碼**
- 🟡 **`list_portfolios()` 每次 rerun 都打 Sheets**（新發現）：`:233 _render_cloud_storage(edited_df)` 在「計算組合」gate **之前**無條件呼叫；`:1737` 的 expander 內容 Streamlit 一律執行；`:1744 names = _gsp.list_portfolios()` **無 `@st.cache_data`** → 在 data_editor 改一個數字就再打一次。
- 🟡 **相關矩陣（`:874-877`）與 VaR（`:1066-1069`）對同一份 1y 價格各跑一次完整迴圈**，程式碼幾乎逐字重複（差別只在後者多 `.dropna()`），且 `_var_rets` 之後又被 vs0050、效率前緣複用 → **作者知道可複用，只是漏了第一份**。
- 🟡 **三個序列 for 迴圈未並行**：`:629-631` warroom（每檔內部 3 次 fetch）、`:1008-1009` weakness（spinner 自承「5-15 秒」）、`:912-913` holdings（自承「10-20 秒」）。**而同檔 `:328` 已示範 `ThreadPoolExecutor(max_workers=6)`**。
- 🟡 **§3.3：ETF 評分 21 個門檻全在 L2 檔內且 UI 手抄一份**：`:864` 的「（單一 GICS 類股 ≤ 30%）」是 `_SECTOR_CONCENTRATION_MAX_PCT` 的複本 —— **同一個坑 F1 v19.184 才剛對 σ 說明文字修過一次**。
- ⚪ `etf_backtest_data` 是死 key，但 `etf_tab_ai.py:50` 明註「目前恆為 None」且 `:150-151` prompt 已改「本系統目前沒有 ETF 組合歷史回測功能…請勿要求使用者去執行回測」→ **已妥善處理，不建議動**（§-1）。

**金融邏輯**
- 🔴 **葡萄串只看「有沒有配」**（`grape_ladder.py`）：取近 `LOOKBACK_DAYS=400` 天的**除息月份集合**暴力搜「覆蓋最多月、檔數最少」→ **一檔配 0.01 元和一檔配 1.5 元在覆蓋圖上都是綠色 ✅**。而 `:80 get_avg_monthly_cash` 定義完整（含 shares 參數）卻**全 repo 零 caller**。
  ⚠️ **「零警語」需修正**：`:405`「領息 ≠ 賺錢…仍請看品質星等與含息總報酬」與 `:501` 同樣警語都存在，只是 `:405` 只在有缺月時出現、`:501` 收在預設收合的 expander 裡 —— **覆蓋率 metric 那一行（`:364-367`）旁確實沒有**。

#### 2. 具體改善優化方案
**新手友善化**：覆蓋圖每月格加「約可領(TWD)」（資料源就是現成的 `get_avg_monthly_cash`）；覆蓋率 metric 加 `help='只算「有沒有配」，不含配多少、填不填息、含息總報酬'`；「建議補」清單併入品質星等 + 含息總報酬。
**排版瘦身（三層）**：
```
L1 決策層：資產總覽卡 / 🚦核衛vs regime / ⚖️再平衡交易指令 / 🧨壓測結論一行 / 持股主表 5 欄
L2 診斷層（Expander）：戰情室三表 / 相關矩陣 / Overlap / 弱勢度 / 產業曝險 / 成分股 / 完整 16 欄
L3 學術層（Expander + button gated）：VaR / 效率前緣 / vs0050 / 風險貢獻 / 3-3-3 / 標準差帶 / 分散度
```
> **`:275` 的 `st.button('🔗 計算分散度（首次約 10-20 秒，之後走快取）')` 就是現成的 opt-in 範例，直接複製到 VaR / 效率前緣 / 弱勢度。**

**進階分析保留**：24 段一段不刪，全數保留在 L2/L3。

#### 3. 程式碼重構建議
| 優先 | 項目 | 檔案:行 |
|---|---|---|
| P0 | 補 `_render_tab_isolated`（建議**逐個渲染器各包一次**，單一 section 失敗不吃掉葡萄串） | `app.py:730-762` |
| P0 | AI prompt：`target_source != 'user'` 時寫「使用者未設定目標比例，本節不得評論再平衡」 | `etf_tab_ai.py:116-125` |
| P1 | 葡萄串加金額欄 + 填息警語 + 建議補併品質星等 | `grape_ladder.py:364-367,384-388` |
| P1 | `list_portfolios` 包 `@st.cache_data(ttl=TTL_1HOUR)`，存/刪後 `.clear()` | `etf_tab_portfolio.py:1744` |
| P1 | 1y 價格迴圈合併（相關矩陣 + VaR 共用） | `:874,1066` |
| P1 | 三個序列迴圈改 `ThreadPoolExecutor`（三函式皆 `@st.cache_data` 純資料、thread-safe） | `:629,912,1008` |
| P1 | 兩處無感 except 補 `st.caption('⚠️ …載入失敗，本區已略過')` | `:495,571` |
| P2 | 持股明細 16 欄 → 主表 5 欄 + expander（照抄多檔比較） | `:562-618` |
| P2 | ETF 評分 21 門檻上抽 SSOT + UI 文案插值 | `etf_scoring_helpers.py` / `etf_quality.py` / `etf_render.py:567` |
| P2 | 26 處 `use_container_width` → `width='stretch'` | 全檔 |

---

### 📌 3-11. 🔧 工具箱 → 🔎 資料診斷（`src/ui/pages/` 7 檔 + `scripts/calibrate_macro_traffic.py`）

**渲染順序**：`render_data_coverage()` **常駐** L781 → expander `🔧 進階診斷（工程師版…）` L785（`expanded=False`）內含 6 panel L788-798

#### 1. 現狀診斷與問題點

**資料稽核**
- 🔴 **N-10 校準鏈路整條空轉，且該 json 從未由腳本產生**：
  - `calibrate_macro_traffic.py:709-711` 值沒變就 `return False` 不寫檔 → `last_calibrated` 永遠 `null`
  - 實測 `macro_thresholds.json:4-7` 為 `"last_calibrated": null, "method": "default (uncalibrated)"`，且 `_comment` 多了腳本 `:717` **不會寫**的 `"Override calc_traffic_light thresholds."`、還有腳本不產生的 `_comment_v19_173` key → **這檔是手寫的**
  - `recalibrate_macro.yml:59` 用 `git diff --quiet`（**其餘 7 個寫入型 cron 全用 `git diff --staged --quiet`**），且 `MACRO_CALIBRATION_PROPOSAL.md` **在 repo 內不存在也不在 .gitignore** → 兩個 pathspec 皆無 diff → **PR 永不開啟**
  - **面板永遠印「尚未校準（使用預設）」，無法區分「從未跑過」與「跑過 N 次、每次都確認無需調整」**
- 🔴 **`api_diagnostic._probe():71-73` `verify=False` 且 headers 帶真實憑證**（`Bearer {_fm_tok}` / `x-goog-api-key`），而 `:213-217` 的「📌 結果判讀指南」四條**沒有一條提 TLS**。
  **全 repo `verify=False` 精確盤點**：session 建構點 **6 個**（`data_loader:99`、`app_stock_fetchers:81,287`、`proxy_helper:154`、`macro_snapshot:134,865`）+ per-request kwarg **8 個**（`proxy_helper:317`、`nas_server:165,223,277,312,357`、`macro_snapshot:493`、`api_diagnostic:72`）→ 憲法「6 個建構點」數字正確。
- 🟡 **`reconcile_panel` 第 2 列是永久死列**：`rev_yoy_self`/`rev_yoy_finmind`（`:189-190`，註解自承「預留欄位」）**全 repo 零寫入端**，該列卻標「(待個股觸發)」+ note「個股 Tab 查股票後填欄」—— **承諾了一個不存在的行為**。（✅ caption 已於 v19.181 D3 改為由 `len(rows)` 推導，v1 的那半條批評已被修掉。）
- 🟡 **對帳容差手抄**：`:182` 5bp / `:202` 0.1pp / `:218` 15 分，真值在 `reconcile.py:207/227/321`。
- 🟡 **`data_registry_panel._freshness_emoji:52-56` 的自承只在 docstring**：「**本表的 `last_updated` 語意是混的**：`rp_entry` 塞資料日期，`rp_scalar` 塞 `proxy_date`(≈今天)」—— 這是最重要的判讀前提，畫面上看不到。
- ⚪ **`STALE_DAYS_MONTHLY=45` 可結案**：`data_coverage:311` / `health_inspector:172` 皆改走 `monthly_freshness_level`。⚠️ 但常數仍在、`stale_days_threshold("monthly")` 仍回 45，且 `tests/test_staleness.py:113` 正向釘住 → 建議加 guard 註明「僅限 as_of=月底的序列」。
- ✅ **覆蓋率分母定義清楚且誠實**（`data_coverage.py:74-77`）：`_COVER_GREEN_RATIO=0.85` / `_COVER_YELLOW_RATIO=0.50` 具名 + 註解寫明推導（8 項容忍缺 1 → 7/8=0.875）。
- ✅ **校準門檻「顯示 vs 生效」處理正確**（`calibration_ui.py:55-68`）：印 `load_calibrated_thresholds()` 回傳值而非 json 面值，不一致時 `st.warning` 說明是哪一項被值域守門打回。

**效能**
- 🔴 **N-6 `health_inspector.py:1425-1478` 的 per-ETF 迴圈在 `if _do_deep:` 之外**（縮排 16 vs 20 空格）：只要 `etf_portfolio_data.rows` 非空就每次 render 對每檔主動 ETF 打 MoneyDJ（`:1442 fetch_etf_manager`）+ 持股（`:1478 fetch_etf_holdings`）。另 `:1264-1265` 單一 ETF 路徑同樣無 gate、`:538 _next_release_cached('CPILFESL')` 每次展開就打 FRED。三者都有 `@st.cache_data` 兜底，但 **cache miss / TTL 到期 = N 次 proxy 往返在 render 途中同步阻塞**。
  ⚠️ **對照更正**：6 個 panel **本身**確實無網路 I/O（雙跑實測 `:150`、回測 `calibration_ui:92`、`health_inspector:366/372/412` 皆 button-gated）→ v1 的「6 panel 每 rerun 打外部 API」需修正為「**真問題在 health_inspector 的 3 條漏 gate**」。

**UI/UX**
- 🟡 **`data_registry_panel:181-182` 11 個分類 expander 全 `expanded=True`** → 展開「🔧 進階診斷」= 50+ 筆 × 11 表同時攤開。（✅ H2 已誠實把恆真算式換成字面 `True` 並留完整說明，是全站最誠實的註解範例。）
- 🟡 **三張診斷表都是固定 `fr` 的 CSS grid、11px、無 media query、無 `overflow-x`**（最寬 7 欄）。
- 🟡 **`render_data_coverage` 的 caption 是寫給稽核員的**，且順序「先統計後解釋」對新手是反的。
- ⚪ 進階診斷標題塞 6 個名詞 + 一個 §編號。

**資料治理邏輯**
- 🔴 **校準面板走 in-sample 路徑，反過擬合機制完全不可達**：`calibration_ui:108-110` 只 import 4 支，而 `walk_forward_validate:520` / `grid_search_thresholds:498` / `_objective_with_penalty:479` / `build_proposal_report:627` **零 UI caller**。而 `build_report` 的 `## (c) 門檻調整建議`（`:810-870`）會吐出可操作建議（`:848-852` 「現行 `health < {_HDT}`，可考慮再收緊至 …」）→ **拿全樣本 in-sample precision 建議調 production 門檻**，正是 `:384-390` 自己寫的「永不在訓練窗報告分數」所禁止的事。
- 🟡 **校準腳本 4 份門檻手抄複本**（`:503-504` / `:522-523` / `:702` / `:819`），真 SSOT 在 `src.compute.macro`（只有 `main():961` 正確引入）。
- ✅ **`reconcile.py:133-170 normalize_tnx_quote` 方法論正確**：偵測刻度而非猜換算，越界回 None + log，且 `:117-119` 明說「不拿 FRED 去挑比較接近的刻度，否則對帳就失去意義」。

#### 2. 具體改善優化方案
**新手友善化**：★ 在 `### ⓪` 標題正下方加「一句話結論」卡（純由既有 rows 推導、零新資料）：
```
全🟢 → 「✅ 目前 4 個資料區塊都有值且在正常發布窗內，畫面數字可以照常看。」
有🔴 → 「⚠️「💰籌碼面」缺 2/3 資料，涉及籌碼的判讀先別採信 —— 到 🌍 總經 Tab 按『🚀 一鍵更新全部數據』。」
有🧊 → 「🧊 先行指標的 3 個欄位連續 3 天完全沒動，數字看起來新但可能是死的。」
```
emoji 統計兩行 caption **降級到卡片下方**（修正「先統計後解釋」的反向順序）。
**排版瘦身**：進階診斷標題改「🔧 進階診斷（工程師用；一般使用者不需要打開）」+ checkbox gate；11 個分類 expander 改 `expanded=(_emo_cnt['🔴'] > 0)`（只展開有紅燈的）；grid 包 `overflow-x:auto`。
**進階分析保留**：6 個工程師面板一個不刪，只改成 opt-in；對帳表移除死列並在下方寫「月營收 YoY 對帳尚未接線（BACKLOG）」。

#### 3. 程式碼重構建議
| 優先 | 項目 | 檔案:行 |
|---|---|---|
| P0 | **`emit_thresholds_json` 無變動時仍寫 `last_verified`**，面板顯示「最後驗證：YYYY-MM-DD（結論：維持現行）」 | `scripts/calibrate_macro_traffic.py:709-718` + `calibration_ui.py` |
| P0 | `recalibrate_macro.yml:59` 改 `git add` → `git diff --staged --quiet`（**抄其他 7 個 cron**） | `.github/workflows/recalibrate_macro.yml` |
| P0 | `health_inspector` 3 條漏 gate 的外抓包進 button | `health_inspector.py:1425,1264,538` |
| P0 | `_probe` 揭露 TLS 未驗證（msg 前綴 `⚠️TLS未驗證` 或 §4 標題下 `st.warning`） | `api_diagnostic.py:71-73,213` |
| P0 | 校準面板加 in-sample 警告 | `calibration_ui.py:108` |
| P0 | `render_data_coverage` 加「一句話結論」卡 | `data_coverage.py` |
| P1 | 進階診斷加 checkbox gate + 11 expander 改條件展開 | `app.py:785` / `data_registry_panel.py:182` |
| P1 | 對帳容差改由 `reconcile.py` 匯出常數 + f-string；移除死列 | `reconcile.py` / `reconcile_panel.py:182,202,218,189` |
| P2 | 校準腳本 4 份複本改 import SSOT；UI 改走 `walk_forward_validate` | `calibrate_macro_traffic.py` / `calibration_ui.py` |
| P2 | grid 包 `overflow-x:auto`（抽 `scrollable_grid_open()` helper） | 3 檔 |

---

### 📌 3-12. 🔧 工具箱 → 📚 教學（`tab_edu.py` + `macro_classroom.py` + `STRATEGY_MANUAL.md`）

#### 1. 現狀診斷與問題點
- 🟡 **6 個 expander 預設全開**（`:425` 指標手冊 + `:640/694/773/843/925` 五個策略），內文合計約 700 行 markdown 一次攤開；全檔 `st.tabs`/`st.header`/輸入元件皆 0，唯一導覽是 `:627` 一行標題。**諷刺的是 `STRATEGY_MANUAL.md:7-17` 有完整目錄與 72 個章節錨點，但沒有任何 UI 讀取它**。
- 🟡 **`help=` = 0**（`tab_edu` + `macro_classroom` 合計）。
- 🔴 **教學數字 vs SSOT 漂移（金融正確性風險）**：同一頁 `:677` 手寫「毛利率 ≥ 30%」，`:751` 卻 f-string 代入 `FH_GROSS_MARGIN_GOOD_PCT`=**40.0** → **策略1 說 30、策略2 說 40**。另 `:655/669` 手寫 50%/80%，SSOT 已有同值常數卻未 import。`macro_classroom:99` 寫死 `/ 6`，同檔 `:229-230` 自陳「滿分隨資料齊全度浮動(4~6)」—— **同一個 expander 內自相矛盾**。
- 🟡 **`_fetch_fred_series_edu`（`:287-320`）在 L5 自組 FRED endpoint + 自讀 API key**（非 EX-PASSTHRU-1 的 pass-through）。附帶 bug：`:300 'limit': months` —— FRED 的 `limit` 單位是**筆數**不是月份，24 個月的月頻序列剛好巧合，但 `pc1` YoY 需要更多觀測時會截斷。三個 except 全無 log。
- ⚪ 4 處 grid 假表格無 `overflow-x`。

#### 2. 具體改善優化方案
- ★ **教學頁是「新手白話指南」的天然歸屬地**：把擴充後的 `TERM_EXPLAIN`（~60 詞）做成**可搜尋的名詞索引**放本頁最上方，讓其他 Tab 的 `help=` 可跳轉
- 5 個策略 expander 改 `expanded=False`，只留指標解讀手冊展開；`:627` 下加 `st.tabs` 或 anchor 目錄（可直接讀 `STRATEGY_MANUAL.md` 的既有錨點）
- 所有門檻數字改 f-string 代入 SSOT

#### 3. 程式碼重構建議
| 優先 | 項目 | 檔案 |
|---|---|---|
| P0 | `:677` 的「毛利率 ≥ 30%」與 `:751` 的 40% 漂移收斂；`:655/669` 改 import SSOT | `tab_edu.py` |
| P1 | 5 個策略 expander 改 `expanded=False` + 加章節目錄 | `tab_edu.py:640-925` |
| P1 | `_fetch_fred_series_edu` 下沉 `src/data/macro/` + 修 `limit` 語意 | `tab_edu.py:287-320` |
| P2 | ★ 名詞索引頁（接 `TERM_EXPLAIN` SSOT） | `tab_edu.py` + `ui_widgets.py` |
| P2 | 教學頁門檻加 golden test 釘與 SSOT 一致 | `tests/` |

---

### 📌 3-13. 📁 組合管理（`portfolio_manager.py` + `gsheet_portfolio.py` + `oauth_state.py` + `infra/oauth.py`）

**版面**：標題 L79 → info L80 → `st.columns(2)` L88 → 左 🏦 ETF 組合 L126 / 右 📈 個股清單 L194。**0 個 expander / tabs / form，單一平面**。

#### 1. 現狀診斷與問題點
- 🔴 **N-7 `_get_worksheet:225` 純讀也會覆寫使用者 Sheet 第 1 列**：`ws.update(f'A1:{_col_letter(len(headers))}1', [headers])`，而 `list_portfolios`（純讀）會走到這裡。使用者若自己改過標題列，**光是打開組合管理頁就被改掉，無任何提示** —— §1 的鏡像違反（靜默修改而非 fail loud）。
- 🔴 **每次 rerun 最少 6 次 Sheets API**：`src/data/portfolio/` 全層 `cache_data|cache_resource` **0 命中**。單次 `list_portfolios` = 3 次 API（`:217` metadata + `:223 row_values(1)` + `:243 get_all_records`），render 呼叫兩次（`:132` ETF + `:200` 個股）= 6 次；本檔另有 **8 處 `st.rerun()`**（`:153/158/169/172/217/222/233/236`），每次再付一輪。**Google Sheets read quota = 60/分鐘/使用者 → 連按三次就爆。**
  ⚠️ **措辭更正**：`_ws()`（`:229-238`）**兩種 cache 都沒有**。「沒踩 pickle 地雷」屬實，但那不是設計選擇，是整層無快取的副產品。
- 🔴 **N-8 OAuth 三重風險**：
  - `oauth_state.py:133-135` state 檢查 **fail-open**：`if expected_state and got_state and got_state != expected_state: return False` / `return True` —— docstring `:128-131` 自列真值表：`expected=None, got=ABC → True`、`expected=ABC, got=None → True`。**session 遺失或 URL 未帶 state 一律放行，CSRF 防護在最需要它的情境下失效**
  - `infra/oauth.py:86-88` id_token **不驗簽**，直接 base64 解 payload 取 email
  - `:139 raise OAuthError(f"token response 缺 access_token：{tokens}")` 把整個 token response dict 塞進訊息，再由 `oauth_state.py:168 st.error(f"❌ OAuth 失敗：{_oe}")` **渲染到畫面**
- 🟡 **Sheet ID 解析 3 份實作，只有 1 份處理 `/d/e/`**：`portfolio_manager.py:65`（唯一有守衛）vs `app.py:252-253`（sidebar）vs `tab_stock_grp.py:227-228` → 貼「發布連結」會把字串 `"e"` 寫進 `st.session_state['portfolio_sheet_id']`，而那正是 portfolio_manager 讀的同一把 key。
- 🟡 **儲存無二次確認，但那是最危險的操作**：刪除有確認（`:156-172` / `:220-236`），**儲存沒有**（`:183-190` 直接 `save_portfolio`），而 `save_portfolio:323` 第一步就是 `ws.clear()` **清空整張表再重寫**。誤刪列 → 按儲存 → 永久生效。
- ✅ **9 處 except 全部 `st.error/warning`，零 `except: pass`** —— **全站 fail loud 最徹底的檔案**。⚠️ 但 `:166-169`/`:230-233` 的 warning 後緊接 `st.rerun()`，**訊息被畫面重繪吃掉**；且多數只印 `type(_e).__name__` 不含訊息內容。

#### 2. 具體改善優化方案
- 儲存加二次確認 + 明確警語「這會**覆寫整張工作表**」；未登入時的 `st.info` 加「👉 前往登入」按鈕
- Sheet ID **統一單一入口在本頁**，Sidebar 與 ETF 組合頁改唯讀顯示 + 連結
- warning 後不要立刻 `st.rerun()`（或改用 `st.toast`）

#### 3. 程式碼重構建議
| 優先 | 項目 | 檔案:行 |
|---|---|---|
| P0 | `_get_worksheet` header 覆寫改「偵測不符 → `st.warning` 詢問」，純讀路徑不寫 | `gsheet_portfolio.py:225` |
| P0 | `list_portfolios` / `list_stock_watchlists` 加 `@st.cache_data(ttl=TTL_1HOUR)`，寫入後 `.clear()`（**不動 `_ws()` 契約**） | `gsheet_portfolio.py` |
| P0 | OAuth state 缺失改 `return False` + 重導登入；`:139` 只印 keys 不印 values | `oauth_state.py:133` / `infra/oauth.py:139` |
| P1 | `parse_sheet_id` 下沉 `shared/`（L0），三處共用 | `portfolio_manager.py:65` → `shared/` |
| P1 | 儲存加二次確認 | `portfolio_manager.py:183` |
| P2 | id_token 驗簽（或至少改走 userinfo endpoint） | `infra/oauth.py:86` |

---

### 📌 3-14. 🧬 AI 問答（`tab_ai_chat.py` 145 行 + L3 `ai_qa_service.py`）

#### 1. 現狀診斷與問題點
- ✅ **grounding 是本次稽核最紮實的一塊**：`SYSTEM_INSTRUCTION:55` 第 1 條「需要數字時一律呼叫工具，**嚴禁自行計算/推估/杜撰數字**」；`:58-63` 第 3-1 條「此時**嚴禁**改用『中性』…—— **『中性』本身就是一個方向判斷，不是「沒有判斷」**」。`_tool_get_stock_score:222-224` 在 regime 不可用時**整份拒絕輸出**（理由：「下游是 LLM，空白格會被自動填」）。**這是全 repo 對抗 LLM 幻覺最精準的規範，建議複製到 macro AI / 個股 AI / ETF AI 三條路徑。**
  ⚠️ **範圍限定（v2 補）**：3-1 條**只在「決定方向的那個工具回 `ok=false`」時生效**，且僅限 `get_stock_score` / `get_market_state` 兩支。**工具回 `ok=true` 但欄位為 None 的情況不在涵蓋內**，仍受第 3 條約束（必須從五個方向詞選一個）→ 資料半殘時模型仍會被逼出一個方向。
- 🟡 **`_tool_get_market_leading:299-302` 的 fail-soft 分支**：欄名漂移時 `data = {str(k): _jsonable(v) for k, v in last.items()}` 把**整列 16+ 欄**丟進 Gemini payload，**且以 `ok=True` 送出、無「欄名不明」旗標** → 模型會照著念出它不理解的數字。
- 🟡 **兩條隱性預設值路徑**：`_tool_get_risk_plan:330-332` regime 不可用時落到 `risk_control.py:153` 的 `regime='neutral'` 預設，**且回傳 payload 不含 regime 欄位** → Gemini 無從得知倉位是用「中性」算的；`_annotate_staleness:521-522 except Exception: pass` → 過期標記算失敗即等同「默認新鮮」進 payload。
- 🟡 **缺獨立免責**：全檔 145 行 grep「僅供參考/不構成/投資建議」**0 命中**；全站免責只在 `app.py:336` 與 `:935`。
- 🟡 **範例問題只在 `:119` 的 placeholder**（輸入框一有字就消失）；使用者不知道背後有 6 支工具；`run_agent`（`ai_qa_service:693-700`）是 `max_rounds=4` 同步迴圈，`:132` 只有一顆「查詢中…」spinner，4 輪期間零進度回報。
- 🟡 **`ai_qa_history` 無上限**：`:114 setdefault([])` 全檔無 trim，`:115-117` 每次 rerun 全量重播。送 Gemini 有界（`:684 max_turns=8`），**session_state 與 DOM 無界**。
- ✅ **工具透明度好**：每個 tool 一個 `🔧 {name}` expander（來源 / as_of / ⚠️過期 N 天 + `st.table`）。
- ⚪ **`app_ai_service.build_llm_context:158`** docstring `:167` 自陳「本函式仍 0 production caller」→ 搬家後仍是死碼（憲法 §8.2.A.2 V-APP-1 已載，待裁示）。

#### 2. 具體改善優化方案
- ★ 首次進入列「我可以回答什麼」清單（對應 6 支工具）+ 3–4 顆快捷問題 `st.button`
- 加獨立免責卡：「🤖 AI 解讀僅供參考，數字取自後端工具但**解讀可能有誤**；非投資建議。」
- spinner 文字由 `run_agent` 逐輪 callback 更新（「正在查 get_stock_score…」）

#### 3. 程式碼重構建議
| 優先 | 項目 | 檔案:行 |
|---|---|---|
| P1 | `ai_qa_history` 加 `_MAX_HISTORY = 50` 具名常數 + `[-_MAX_HISTORY:]` | `tab_ai_chat.py:114` |
| P1 | 加免責卡 + 快捷問題 + 工具清單 | `tab_ai_chat.py:107` |
| P1 | 第 3-1 條觸發改為「ok=false **或關鍵欄位為 None**」 | `ai_qa_service.py:58` |
| P2 | `get_market_leading` fail-soft 改 `ok=False` + 列實際欄名 | `ai_qa_service.py:299-302` |
| P2 | `_tool_get_risk_plan` payload 帶 regime 旗標；`_annotate_staleness` 的 `except: pass` 改標記 | `ai_qa_service.py:330,521` |

---

## §4. 測試與 CI 守衛（v2 新增面向）

> 這一節是 v2 最重要的新增。**5520 tests passed 給人的安全感，與實際守衛強度有落差。**

### 4.1 動工前必讀：15 個候選修改的紅燈判定

| # | 修改項 | 釘住它的測試 | 判定 |
|---|---|---|---|
| 1 | 無 MA `score += 15` → None | `test_scoring_helpers.py:156` 釘 `score == 15`；`:125` 釘 `isinstance(score, int)` | 🟡 同 PR 改 2 條 |
| 2 | 財報體檢 5 處缺資料 → Pass/50 | `test_financial_health_engine.py:98-111` **註解即宣言** `# All items N/A → rule_st="Pass" (no data is not a fail)` | 🔴 **政策決定，須先談** |
| 3 | 禁止操作去 `abs()` | 未找到（`test_d1_stock_tab.py:114-168` 只測 helper） | 🟢 |
| 4 | dragon_alert 改 import + OR→AND | 未找到 | 🟢 |
| 5 | 失敗列 `健康度: 0` → None | 守衛掃的是別檔；slow 測試用自建 fixture | 🟡 需補下游測試 |
| 6 | AUM `B USD` → `億` | 未找到字串斷言 | 🟡 `:918` 若在 `_sections` 內會進 `test_ai_prompt_thresholds.py:137` 掃描範圍 |
| 7 | `etf_tab_smart` 5 個 TTL 換常數 | **未找到（零測試）** | 🟢 |
| 8 | `section_state` M1B/M2 三態 | `test_d2_macro_sections.py:254` `assert seen >= 10` | 🟡 重構若減少 append 數即紅 |
| 9 | `section_mid` 6 處 `_num()` | `test_d2_macro_sections.py:407` `assert seen >= 7` | 🟡 同上 |
| 10 | **app.py 刪 dead code** | **`test_c3_layering_guard.py:468`** 的 `_WHITELIST` 有 `("app.py","src.data.stock.app_stock_fetchers")` → `test_rule4_whitelist_not_stale` 是**反向守衛**：刪 import 卻沒刪白名單 = 紅 | 🔴 **必須同 PR 改白名單 + CLAUDE.md §8.2.A** |
| 11 | 5 處補 `_render_tab_isolated` | `test_app_tab_wiring.py:47` 要求 `with tab_X:` **字面**存在 | 🟡 保留顯式 `with` → 綠；改迴圈 → 紅 |
| 12 | 進階診斷加 gate | app.py 的 expander 未找到測試 | 🟢（**若順手動到 `data_registry_panel` 則 🔴**，`test_h2_naming_and_fake_readings.py:489` 釘 `all(exp is True)`） |
| 13 | `_macro_session_reset` 補 key | **`test_p0a_key_alerts_and_spinner.py:170-176`** 明文 `assert 'macro_alerts' not in ...`「被 pop → 填充會讀到空」 | 🔴 **16 個安全、`macro_alerts` 必須先談** |
| 14 | `stock_score` regime 必填 + raise | **多重**：`test_scoring_engine.py` 約 12 個呼叫未傳 regime；`:952-953` 斷言 `regime='unknown'` 與 `'neutral'` 結果相等；**`test_h1_scoring_regime_gate.py:203` docstring 明寫「釘住既有靜默 fallback —— gate 存在的直接理由」** | 🔴 **會破 4 組 ~15 條，等於推翻架構決策** |
| 15 | 刪薩姆 cap 文案 | `test_position_ceiling.py` 釘的是 `_cap_line:64`，不是 `:101-103` 的 caption | 🟢 |

### 4.2 測試本身的漏洞

**`test_c3_layering_guard.py` 品質很高，但兩條違憲被白名單放行**
實作 6 個掃描器（R1 / R1-L0 / R2 / R3 / R4 / R5），用 AST + PEP 562 barrel 展開，**且有「守衛的守衛」**（`:827` 驗 barrel 展開、`:891` 驗 late import、`:931` 驗掃到檔案）。全檔 0 個 `xfail`。

| 待修違憲 | 守衛狀態 |
|---|---|
| V-RADAR-1 / V-L0-NAME-1 / V-FT-STORE-1 / V-CHECKLIST-1 | ✅ 都抓到，列在 `_KNOWN_VIOLATIONS` |
| **V-PICKER-PRIV-1** | 🔴 `:506` 登記在 **EX-PASSTHRU-1 白名單**，但憲法 §8.2.A.1 明文「⚠️ 明確排除…private symbol，pass-through 前提不成立」→ **守衛 key 是 `(規則,檔案,模組)` 無符號粒度，機器這邊在放水** |
| **V-LEAD-RENDER-1** | 🔴 `:413` 列在 EX-CACHE-1，但該檔真正問題是「L1 檔內定義 render 函式」—— **守衛只看 import，看不到這件事** |
| V-APP-1 / V-SMART-CACHE-1 | ⚪ 結構外（不是 import 問題），無對應守衛 |

另 `:627-650` 用 `_TODO_SCRIPTS_LAYER` 對 **20 條 `scripts/** → L2/L3` 發同一張免死金牌**，理由「scripts 分層標籤未定案」—— 本檔最大的未收斂債。

**四個「SSOT 守衛」的真實涵蓋率：全是 1~12 檔白名單**

| 測試 | 掃描範圍 | 偵測內容 | 抓得到本輪的 inline magic 嗎 |
|---|---|---|---|
| `test_consumed_ssot_guard.py` | **3 檔** | 4 條正則，只認 3400/80/50 | ❌ 三個目標檔都不在名單 |
| `test_app_no_magic_bare_ternary.py` | **1 檔** | `Expr(value=IfExp)`（Streamlit **magic display**，與 magic **number** 無關） | ❌ 完全無數字邏輯 |
| `test_financial_health_ssot.py` | **5 檔** | 反 inline 只有 3 個字面子字串 | ❌ 連同檔的 `_score(...) return 20` 都抓不到 |
| `test_ai_prompt_thresholds.py` | **12 檔** | `:296-299 if not isinstance(node.value, str): continue` —— **只看字串，數字 Constant 一律不看** | ❌ `ttl=1800` / `.get('value',50)` / `'健康度':0` 結構性出界 |

問題不是它們說謊（`test_ai_prompt_thresholds.py:48-53` docstring 已誠實揭露「`_SITES` 是白名單，不是全 repo 掃描」），**是名字讓人以為涵蓋率遠高於實際**。

**把 bug 釘成規格的測試（前 10）**
1. `test_financial_health_engine.py:98-111` —— **全空財報得 Pass**（最嚴重）
2. `test_scoring_engine.py:696-700` `calc_rs_score(None) == 50`
3. `:231-233` `calc_chip_score(None) == 50.0`
4. `:447-451` `calc_revenue_yoy_score(None/空 DF) == 50.0`
5. `:258-262` `calc_volume_score(None) == 50.0`
6. `:70-78` `calc_trend_score(None) == 0.0`（**缺值被報成「最差趨勢」**）
7. `:364-372` `score_single_stock(None)["total"] == 0`
8. `test_bps_data_source.py:112-121` docstring 自承「call site 用 `if bps > 0` 守門」→ 其他 consumer 拿到 P/B=∞
9. `:484-487` `test_none_df_returns_fixed_8pct` —— **零筆歷史仍回具體停損價 92.0**
10. `:307-311` MA60 全 NaN → 給 0.5 分，總分 2.5/3 = 83.3

**對照組（好的慣例同時存在）**：`test_b1b_stock_math.py:330-335` `assert r["est_yield"] is None, "缺資料必須回 None（未評估），不可回 0"`。**同一 repo 兩套互斥慣例，scoring/financial_health 是釘住壞慣例的口袋。**

**`test_scoring_engine.py:1572` 的假綠燈仍在，且比紀錄更嚴重**：`cl_vals` 賦值後**從未被引用**（工廠實收 `:1575` 的另一組），且斷言是 `assert i3['signal'] in ('🟢','🟡','🔴')` —— **空洞斷言，docstring 宣稱的「→🟡 持平」從未被驗證**。同款空洞斷言另見 `:1523/:1549/:1558/:1578`。

**`conftest.py` 無網路封鎖**：161 行全讀完，唯一 autouse fixture 是 `:107-118 _isolate_module_caches`。個別測試自律良好（80 檔 441 處 patch，`test_tpex_yield_pe.py:124` 甚至有 `_assert_http_mock_used`），但**架構上沒有任何東西阻止測試打外網**。

### 4.3 CI 守衛強度

| 項目 | 實測 |
|---|---|
| `pr-check.yml:39` | `pytest -v`（fast lane） |
| **lint** | ❌ `:36` 裝了 pyflakes **無執行步驟**；全庫無 `ruff.toml`/`pyproject.toml`/`setup.cfg` → **沒有設定檔就沒有 gate**（`STATE.md:217,2262` 自承一致） |
| **coverage** | ❌ 未找到門檻 |
| **slow lane** | `:49 continue-on-error: true` → 24 個 AppTest **永遠不阻擋 merge**（含 `test_b5b_stock_grp.py:433` 的實機 render 對帳）。⚠️ 且 slow lane `:65` **沒裝 pyflakes** → `test_no_undefined_names.py` 在該 lane 靜默 skip |
| `pytest.ini` | `addopts = --strict-markers -m "not slow"`，無 `-x`/`--maxfail`/coverage |
| **cron 失敗告警** | ❌ **15 個 workflow 全部沒有 `if: failure()`** |
| **cron 撞車** | 🔴 `update_health_history`(`30 9 * * 1-5`) 與 `update_sector_flow`(`30 9 * * *`) **同一分鐘**、`update_macro_history`(`0 9`) 與 `push_daily_signals`(`0 9`) 同刻，皆裸 `git push`、**無 `git pull --rebase`、無 `concurrency`** → 撞到即 non-fast-forward 失敗，而依上一列**失敗無人知** |
| `recalibrate_macro.yml:59` | 🔴 **全 repo 唯一用 `git diff --quiet` 的錯誤變體**（其餘 7 個寫入型 cron 全用 `git diff --staged --quiet`）→ 見 §3-11 |

### 4.4 建議的守衛補強（成本低、ROI 高）

1. `pytest.ini` 加 `--disable-socket --allow-unix-socket`（把「不打外網」從自律變結構保證）
2. CI 加 ruff step（先只跑 `src/`，`tests/` 另案）
3. 15 個 workflow 補 `if: failure()` 通知 + 寫檔型 cron 加 `concurrency` group
4. `recalibrate_macro.yml:59` 改 `git add` → `git diff --staged --quiet`
5. 修 `test_scoring_engine.py:1572` 死變數 + 5 處空洞斷言
6. `test_c3_layering_guard.py` 白名單加**符號粒度**，解決 V-PICKER-PRIV-1 的機器/憲法矛盾
7. 新增守衛：`st.metric` 無 `help=` 即失敗、`@st.cache_data(ttl=<數字字面量>)` 即失敗

---

## §5. 執行路線圖

> 依 `PROCESS.md` §3 嚴格三步法（Explore → Plan → Execute）與 §4「任何一行 .py 邏輯變動 → 強制 PR」。
> 依 `CLAUDE.md` §-1，**本路線圖不構成動工授權**，需逐 Batch 明確指派。

### Batch A｜零風險快贏（不改業務邏輯，全部 🟢 測試安全）

| # | 項目 | 檔案 | 工時 |
|---|---|---|---|
| A1 | 進階診斷 expander 加 checkbox gate | `app.py:785` | 10 分 |
| A2 | 5 處補 `_render_tab_isolated`（保留 `with tab_X:` 字面） | `app.py` | 30 分 |
| A3 | **V-SMART-CACHE-1：5 個 inline TTL 換常數** | `etf_tab_smart.py` | 5 分 |
| A4 | `config.toml` 刪無效鍵 | `.streamlit/config.toml` | 5 分 |
| A5 | `_TW_TZ_SB` 改用既有 `_tw_now()` | `app.py:207` | 5 分 |
| A6 | 刪硬編碼「🟢 系統正常運作中」+ 旌旗 50 fallback | `app.py:217,870` | 15 分 |
| A7 | **AUM 幣別**：`etf_tab_single.py:195,918` → `f'{aum/1e8:,.0f} 億'` | 1 檔 | 5 分 |
| A8 | `_market_context` 0.0% 三態化 | `rs_leader_service.py:113` | 10 分 |
| A9 | 刪 `_bb_near_up` 死碼 + `or float('inf')` 改「缺值不出訊號」 | `section_when_buy_sell.py:125-128` | 10 分 |
| A10 | 「禁止操作」去 `abs()` + 負向另立常數 | `psy_checklist.py:180,182,239` | 15 分 |
| A11 | `dragon_alert` 改 import `evaluate_leading_gates()` + 統一 AND | `section_dragon_alert.py:45-56` | 20 分 |
| A12 | 熱力圖「面積≈權重」文案修正 | `etf_render.py:786` | 2 分 |
| A13 | 刪畫面寫死的「相關性 ~0.6」 | `section_state.py:513` | 2 分 |
| A14 | `recalibrate_macro.yml:59` → `git diff --staged --quiet` | 1 檔 | 5 分 |

**Batch A 合計約 2.5 小時，解掉 1 個效能黑洞、1 個白屏風險、1 條分層違憲、7 條資料造假／誤導。**

### Batch B｜§1 Fail Loud 總掃（資料真實性，投資價值最高）
B1 總經缺值三態（`section_state`/`section_mid`/`section_short`/`handlers`）｜B2 `scoring_helpers` 無 MA 15 分｜B3 `op_recommendation` 6 處捏 0｜B4 個股組合 5 處（`_check_book_value`/`EPS(4Q)`/`Cash_Gap_Days`/`健康度:0`/`_precompute_fund_map`）｜B5 選股網三處掃描失敗 + 存活池 None｜B6 ETF（`ffill` / `except:pass` ×2 / `or 0.0` ×5 / `fillna(50)` / 資料不足回 0.0）｜B7 快取降級旗標接線｜B8 🔴 級 28 處 `except: pass` 補 `degraded_badge()`
⚠️ **B2 需同步改 2 條測試；財報體檢 5 處假 Pass 屬政策決定，見 §7。**

### Batch C｜新手友善化（感知價值最高）
C1 修 `_TERM_HELP_LI` 死碼 + `kpi()` 加 `term=` 參數（**一次覆蓋 50+ 張卡**）｜C2 `TERM_EXPLAIN` 擴到 ~60 詞｜C3 28 處 `st.metric` 補 `help=`｜C4 `render_data_coverage` 一句話結論卡｜C5 Sidebar「🔰 新手白話模式」toggle｜C6 色彩語意反向 3 處 + 拆 `TW_*` vs `SEMANTIC_*`｜C7「無法評分」詞彙統一 `⬜ 未評估`｜C8 教學頁名詞索引 + 章節目錄｜C9 CI 守衛：`st.metric` 無 help 即失敗

### Batch D｜漸進式揭露改版（需視覺驗收，**一次一頁**）
D1 🌍 總經（23 段）｜D2 🔬 個股（14 單元 + 財報體檢 9 子段改 tabs + 停損 7 數字收斂成決策卡）｜D3 🏆 個股組合（12 段 → 4 sub-tab + 主表精簡）｜D4 ⚖️ ETF 組合（24 段三層 + 持股表 16→5 欄）｜D5 🔍 ETF 單檔（26 段三層）｜D6 🔭 選股網
> **原則：一格資料都不刪，只調整可見層級。**

### Batch E｜效能與 SSOT 深水區
E1 `_lazy_tab` 延遲載入（先套 3 個最重的頁）｜E2 五桶只算一次 + 回測 gate｜E3 資金潮汐 / 組合管理 / ETF 組合的 gsheet 加快取｜E4 `health_inspector` 3 條漏 gate｜E5 缺貨深掃 + ETF 三迴圈改併發｜E6 `_precompute_xsec` 三處重算改傳參｜E7 個股 4 個純函式加 cache｜E8 `shared/colors.py` 補 UI 層級 5 常數 + 紅綠各 4 套收斂｜E9 59 處 border-left 收斂 + 解 `section_header` 撞名｜E10 `use_container_width` 132 處 → `width='stretch'`｜E11 ETF 評分 21 門檻 + 費用率來源統一

### Batch F｜金融邏輯修正（**需先裁示**，見 §7）
### Batch G｜文件與測試治理
G1 `docs/TAB_STOCK_AUDIT.md` 更新（1876 行 / 12 marker）｜G2 `docs/APP_PY_AUDIT.md` 更正 936 行｜G3 `docs/DEAD_CODE_AUDIT.md` 更正 `calculate_position_size` 已接線｜G4 `CLAUDE.md` §3.3 修 `ANNUAL_MA` 失效指向｜G5 `PROCESS.md` 加「以本機 clone 為準」｜G6 `signal_thresholds` docstring 補布林 4 種語意｜G7 §4.4 的 7 條守衛補強｜G8 `test_scoring_engine.py:1572` 死變數 + 5 處空洞斷言

---

## §6. 第二階段：人員編組與交付標準

> 回應你的指示：「**安排員工進行程式碼確認跟修復，最後由一位稽核 AI 確認修改的程式碼**」

### 6.1 編組（每個 Batch 的固定流程）

```
① 架構師（Plan agent）
   └─ 依 PROCESS.md §3 產出「3 句話藍圖」+ 動到哪些檔 + 預期測試影響 → 交你核可
                    ↓ 核可後
② 實作員（Python/Streamlit 工程師 agent，一次一檔、序列化）
   └─ 改檔 + 附 §6.2 五段自審報告
                    ↓
③ 領域複核員（依 Batch 性質派任，與實作員不同 agent）
   ├─ Batch B → 資安/資料稽核師：確認沒有新的靜默降級、缺值路徑真的 fail loud
   ├─ Batch C/D → 產品經理/UI-UX：確認資料一格沒少、漸進揭露層級正確
   ├─ Batch E → Streamlit 工程師：確認快取 key 正確、無跨 session 污染
   └─ Batch F → 金融分析師：確認計算式與門檻語意正確
                    ↓
④ 測試守衛員（v2 新增）
   └─ 對照 §4.1 判定表，列出「這次改動會碰到哪些測試」+ 是否需同 PR 改測試
                    ↓
⑤ 最終稽核 AI（獨立 agent，未參與前四步）
   └─ 只做一件事：拿改動前後的程式碼，逐條驗證「宣稱的修法是否真的做到、有沒有引入新問題」
      產出 ✅通過 / ⚠️有條件通過 / ❌打回 三態裁決
                    ↓
⑥ 你：跑 pytest → 看 diff → commit + push + 開 PR
```

**為什麼最終稽核 AI 要獨立**：本次 v1→v2 的 19 項修正證明了「同一組 agent 自己檢查自己」會漏。⑤ 拿到的只有「改動前後的程式碼 + 宣稱的修法」，不看前面任何人的推理過程，避免被說服。

### 6.2 每次交付的自審報告格式（依你指定的五段）

```markdown
## 交付：<Batch>-<項次> <一句話標題>

### ① 邏輯審查
- 需求對照：<原提案第幾條> → <實際改了什麼>
- 有無邏輯斷層：<有/無 + 說明>
- SSOT 檢查：本次引入的常數／函式，是否已存在於 shared/* 或 config.py？（列出檢查過的位置）

### ② 邊界測試（Edge Cases）
| # | 情境 | 預期行為 | 實際 |
|---|---|---|---|
| 1 | 輸入為空 / None / 空 DataFrame | ⬜ 未評估（不可回 0/50/Pass） | |
| 2 | 極值（新上市 <60 天 / 停牌 / 跌停 0 vol / 不配息） | 帶降級旗標 | |
| 3 | 型別異常（上游 schema 漂移） | fail loud + log | |

### ③ 效能評估
- 時間複雜度：<O(...)>；空間：<O(...)>
- Streamlit Cache：<有/無，TTL 來源是 shared/ttls.py 的哪個常數>
- rerun 成本變化：<改前 → 改後>

### ④ Debug 與修正
- 撰寫過程中發現的潛在 bug：<列出>，已在最終碼中修正並用 `# FIX:` 標註

### ⑤ 最終代碼
<完整 diff>

### ⑥ 測試影響（v2 新增）
| 測試檔:行 | 斷言什麼 | 本次改動影響 | 是否需同 PR 改 |
|---|---|---|---|
```

### 6.3 硬性紀律（依 `PROCESS.md`）
- **寫入嚴格序列化，一次一檔**（探索/稽核才可並行）
- 同一個報錯連續重試 2 次未果 → **立即停機**，交你詢問其他 AI 雙重驗證（§5 Anti-Loop）
- 對話超過 10 輪，改 code 前**必須重新讀取目標檔**
- **禁止整檔覆蓋**；>500 行檔案強制 offset/limit 分段讀
- 任何一行 `.py` 邏輯變動 → **強制 PR**，且同步 `STATE.md` + `ARCHITECTURE.md` + `SPEC.md`
- 新增／變更分層例外 → 同步 `CLAUDE.md §8.2.A` **與** `tests/test_c3_layering_guard.py` 白名單，**且不寫行號**

---

## §7. 需要你裁示的決策點

| # | 問題 | 為何需要你決定 |
|---|---|---|
| 1 | **Batch 順序**：建議 A → B → C → D → E → F → G | A/B 是零風險與資料正確性，C/D 是你最在意的新手友善，E/F 風險較高 |
| 2 | **`financial_health_engine` 的「缺資料 → Pass」要不要改？** | `test_financial_health_engine.py:99` 的註解 `no data is not a fail` 是**刻意的設計宣告**，與 `CLAUDE.md §1` 直接衝突。這是政策決定不是 bug fix |
| 3 | **`stock_score` 的 `regime='neutral'` 預設要不要改必填 + raise？** | 會破 4 組 ~15 條測試，且 `test_h1_scoring_regime_gate.py:203` 的立論是「引擎刻意寬鬆、gate 才是防線」→ 改了等於推翻架構決策 |
| 4 | **`_macro_session_reset` 的 `macro_alerts`** | `test_p0a:170` 明文禁止 pop（「填充會讀到空」）。其餘 16 個可安全補，但 `macro_alerts` 需另尋傳遞機制 |
| 5 | **Batch F 的金融邏輯修正，哪些要動？** | ① M1B/M2 加 prev（真交叉）② PCR 五門檻收斂（保留哪一套？）③ 融資改百分位（解籌碼桶恆紅）④ jingqi 去雙重計數 ⑤ 合約負債分母改「近四季營收」+ capex 門檻重訂 ⑥ 健康度 6 因子共線調權重 ⑦ 357 統一股利口徑 ⑧ ETF Beta 因子對債券 ETF ⑨ 判定式改吃 `BUCKET_DANGER_SPECS`（會改變燈號）⑩ 標準差帶去趨勢選項 —— **全部會改變畫面上的結論** |
| 6 | **`_lazy_tab` 延遲載入是否接受？** | 換來大幅效能提升，但改變「切 Tab 立即看到內容」的體感（首次需按一下） |
| 7 | **`verify=False` 的 14 個點要不要處理？** | 最低成本是**揭露**（加 ⚠️TLS未驗證），根治要 NAS CA 憑證 |
| 8 | **OAuth 三項（state fail-open / id_token 不驗簽 / token dict 渲染到畫面）** | 屬資安，但改動會碰到現有登入流程 |
| 9 | **選股網抽檔（V-APP-1）現在做還是延後？** | 216 行搬家；也可只先包 `_render_tab_isolated` 當第一步 |
| 10 | **接回 compute 層 4 個死 SSOT（`check_*`）** | 會改變評分結果，需先跑 golden test 對照 |

---

## §8. 附錄：關鍵指標白話文文案（可直接當 `help=` / `TERM_EXPLAIN` 用）

### 總經（21 詞）
| 名詞 | 白話一句話 |
|---|---|
| 綜合健康度 | 「多少股票在漲」的 5 日平均佔 6 成、大盤多空打分佔 4 成，**不含**籌碼與景氣。 |
| 旌旗指數 | 每天上漲家數佔全市場的比例，取最近 5 天平均；越高代表越多股票一起漲。 |
| 上漲佔比 | 今天上漲的股票佔全市場幾成；50% 是分水嶺。 |
| ADL 騰落線 | 每天「漲家數減跌家數」的累加值；它跌但指數漲＝只有少數大股撐盤。 |
| AD 值 | 今天漲的家數減掉跌的家數，單位是「家」不是百分比。 |
| M1B-M2 Gap | 活存＋現金的年增率 減 廣義貨幣年增率。**由負轉正的那一刻**＝定存活化、資金回流股市；持續為正只是狀態不是訊號。 |
| BIAS240 年線乖離 | 指數比 240 天均價高（或低）幾 %；+20% 以上算過熱。長期多頭中正乖離會長期偏高，別當賣出鈴。 |
| NDC 景氣燈號 | 國發會 9–45 分，藍燈(≤16)＝谷底、紅燈(≥38)＝過熱。**約延遲一個月發布，你看到的是上個月**。 |
| 台灣 PMI | 問製造業採購主管「這個月比上個月好嗎」的問卷分數；50 是好壞分界。 |
| 台灣出口 YoY | 這個月海關出口金額比去年同月成長幾 %，領先上市公司營收 1~2 個月。 |
| 核心 CPI YoY | 扣掉食物與能源後的美國物價年增率；Fed 目標是 2%。 |
| Fed Funds Rate | 美國銀行間隔夜拆款利率，全球美元資金成本的定價基準。 |
| VIX | 用選擇權價格反推的「市場預期未來 30 天波動」；<15 平靜（也可能是自滿）、>30 恐慌。 |
| OECD CLI | 領先景氣 6–9 個月，**100 是長期趨勢線**（不是 PMI 的 50）。 |
| 薩姆規則 | 失業率 3 個月均值比過去 12 個月低點高 0.5 個百分點以上＝衰退已開始。歷史上零誤報。 |
| 外資期貨淨口 | 外資台指期多單減空單，**單位是 TX 當量口**。長期結構性為負（避險對沖），單看絕對淨空口數是最常見的散戶誤讀 —— 要看相對自身區間的變化方向。 |
| 選 PCR | 賣權未平倉 ÷ 買權未平倉 ×100。<80 過度樂觀、>120 恐慌買保護。**100 只是數學平價點，不是本系統的判定線**。 |
| 韭菜指數 | 小台裡「法人空單減多單」佔全體的 %；值域 ±100%，**中性是 0 不是 50**。 |
| 前五大留倉 | 台指期前五大交易人的買方口數減賣方口數。 |
| 融資餘額 | 散戶跟券商借錢買股的總額。高＝籌碼不穩、跌時易連環斷頭；**低不等於可以買**。 |
| 三環火力分級 | 第一環＝有無系統性風險，第二環＝有無資金燃料，第三環＝有無點火訊號。 |

### 個股技術（10 詞）
| 名詞 | 白話 |
|---|---|
| 健康度 | 6 個技術指標加權成 0–100，分越高＝技術面越順（**不看基本面**）。80 以上＝均線漂亮又有量；50 以下＝趨勢已壞。 |
| 多因子評分 | 趨勢/動能/籌碼/量價/風險/基本面六件事按「大盤多空」給不同權重加總。**大盤沒結論時它會拒絕給分，不是壞掉**。 |
| RSI | 最近漲跌力道的溫度計，>70 太熱、<30 太冷。 |
| KD | 收盤價在近 9 日高低區間的位置，K 由下往上穿 D＝轉強。盤整好用、趨勢盤會鈍化。 |
| IBS | 今天收盤落在當日高低點的哪個位置，越接近 0＝殺尾盤（隔天常反彈）。**極短線指標**。 |
| 量比 | 今天的量是近 20 日均量的幾倍。>1.3 有人在動；<0.5 量縮（可能打底也可能沒人要）。 |
| 布林帶寬 | 上下軌之間有多寬，變窄＝波動壓縮，常是變盤前兆（**但不告訴你方向**）。 |
| VCP | 每次拉回都比上次淺（像彈簧越壓越緊），常出現在噴出前。 |
| 乖離率 | 股價偏離均線多少 %。太正＝追高風險，太負＝可能超跌。 |
| ATR | 這支平常一天大概震盪多少錢。停損設 1.5×ATR ＝ 給它正常呼吸空間。 |

### 個股基本面（10 詞）
| 名詞 | 白話 |
|---|---|
| 合約負債 | 客戶已付錢但還沒出貨的訂單＝**手上排隊等交貨的量**。**要看它比去年成長多少，不是看它有多大**。 |
| 資本支出 CapEx | 這季實際花錢蓋廠買設備，花得多＝管理層看好未來。 |
| 月營收 YoY | 這個月比去年同月成長幾 %，最早能看到業績轉向的訊號。 |
| 357 殖利率法則 | 用配息回推合理價：7%＝便宜、5%＝合理、3%＝貴。**不配息的股票這條規則不適用**。 |
| SQ 獲利品質 | 賺到的錢有多少真的變成現金。長期低於 100%＝可能在做帳或收不到錢。 |
| FGMS 前瞻動能 | 用合約負債＋存貨＋三率＋資本支出合成的「未來 1–2 季會不會更好」分數。 |
| DSO / DIO / DPO | 收錢天數 / 存貨躺多久 / 付錢天數。前兩者越短、第三者越長越好。 |
| CCC 現金循環 | DSO + DIO − DPO。從付錢進貨到收到客戶的錢卡住幾天，越短越好。 |
| 100-100-10 法則 | 營業現金流/淨利 >100%（賺真錢）、自由現金流/淨利 >100%（賺完還有剩）、自由現金流/營收 >10%（含金量夠）。 |
| 安全邊際率 | （毛利率 − 營業費用率）÷ 毛利率。營收要掉多少才會由盈轉虧，**60% 以上很耐打**。 |

### ETF（14 詞）
| 名詞 | 白話 |
|---|---|
| 折溢價 | 你付的市價比這檔真正的身價（淨值）貴還是便宜。溢價超過 2~3% 等於先賠一段。 |
| 追蹤誤差 | 說要跟著指數走，實際走偏多少。被動型越小越好，>1.5% 代表有看不見的成本。 |
| Sharpe | 每冒一分風險換回多少報酬。>1 算不錯。 |
| MDD 最大回檔 | 過去從最高點摔下來最慘跌幾 %。這是你**曾經要忍受**的帳面虧損。 |
| VaR | 正常日子裡 95% 的天數，單日虧損不會超過這個數。**不含股災那種極端日**。 |
| 標準差帶 / σ | 把過去一年的均價與常見波動範圍畫成線。**但一路上漲的 ETF 會一直貼上緣，不代表該賣**。 |
| 分散指數 | 「走勢像不像、持股重不重疊、類別同不同」合成 0~1，越接近 1 越能真的分散。 |
| 空頭相關 | 只看「這檔跌最凶的那些日子」，另一檔跟不跟著跌。**假分散就是被這個數字抓出來的**。 |
| 3-3-3 原則 | 成立>3 年（撐過多空）＋近 3 年年化>7%（贏定存）＋同類前 1/3。三項全過才算可放心長抱。 |
| 葡萄串領息法 | 挑配息月份錯開的幾檔湊成一年 12 個月都有錢入帳。**但月月領到錢 ≠ 有賺錢**。 |
| 填息 | 除息後股價跌下去，之後有沒有漲回原價。**沒填息＝配給你的是你自己的本金**。 |
| 內扣費用率 | 每年自動從你的錢裡扣掉的管理費。長期複利下差 0.5% 就是差很多。 |
| 配息來源 / 平準金 | 配給你的錢有多少其實是「你自己投進去的本金」。佔比高＝拿自己的錢配給自己。 |
| 效率前緣 | 把各種配置畫在「風險×報酬」地圖上看你站哪。**幫你理解位置，圖上的「最佳點」是歷史算出來的不是建議**。 |

### 選股與驗證（7 詞）
| 名詞 | 白話 |
|---|---|
| 存活池 | 四項基本面全過的股票池。依台股**法定財報公告截止日**取數，不會偷看還沒公布的季報。 |
| 綜合評分（選股網） | 你勾的各因子在全市場的百分位排名平均。因子有一半以上沒資料的股票不進榜。 |
| RS 相對強度(σ) | 這檔報酬減大盤報酬，除以全市場離散度。**大盤在漲時它只代表「誰漲更多」，不叫抗跌**。 |
| 缺貨動能 | 從合約負債、存貨天數、營收動能看「客戶已先付錢排隊」的跡象。**財報有約 45 天延遲，講的是上一季的事**。 |
| 跨季轉強 | 毛利率/營益率逐季升、負債比逐季降、營收年增 —— 四項裡幾項在改善。 |
| 前進式驗證 | 把今天選出的名單連同當下股價**凍結存檔**，之後只用未來資料對帳看贏不贏 0050。名單先存後驗，沒有馬後炮。**下市股會被剔除，所以報酬偏樂觀**。 |
| 存活者偏誤 | 只統計「活到現在的公司」會讓績效看起來比實際好，因為倒掉的從樣本裡消失了。 |

---

## §9. 一句話總結

**v1 說「你的專案不缺規則，缺的是把已經寫好的 SSOT 接上去」—— v2 用本機全文驗證後，這句話仍然成立，而且證據更硬。**

`TERM_EXPLAIN` 15 個名詞寫好了但唯一的呼叫是死碼；`BUCKET_DANGER_SPECS` 只被畫線函式消費；`shared/ttls.py` 的 5 個常數在隔壁檔被裸寫成一模一樣的數字；`evaluate_leading_gates()` 已抽成可測純函式卻被逐字重寫且 OR/AND 相反；`scoring_regime_gate` 治理做得極好但引擎預設值沒改所以 gate 是唯一防線；`forward_test.py` 的偏誤揭露是教科書等級但同一個 repo 的 `financial_health_engine` 把「全空財報 = Pass」寫進測試當規格。

**v2 新增的第五個面向（測試與 CI）揭示了為什麼會這樣**：四個名字聽起來像全域 SSOT 守衛的測試，實際涵蓋範圍是 1–12 檔白名單，且**只掃字串不掃數字**；CI 沒有 lint、沒有 coverage 門檻、slow lane `continue-on-error`；15 個 cron 零失敗告警、兩組同一分鐘 push 同分支。**規則沒被落實，不是因為沒人在乎，是因為沒有任何自動化東西會在沒落實時變紅。**

Batch A（2.5 小時，零風險）+ Batch B（資料真實性）+ Batch C（接回名詞系統）三個 Batch 做完，就能同時達成「數據準確」與「新手看得懂」，而且**一格資料都不用刪**。

---

> 📌 **本報告為第一階段提案，尚未修改任何一行程式碼。請逐 Batch 核可後再進入第二階段。**
> 第二階段的人員編組、五段自審交付標準、最終稽核 AI 的獨立裁決流程，見 §6。

