# 介面與規約 (Interface SPEC)

> 集中記錄 **跨模組對外可見** 的命名、對應表、語意契約。修改本檔代表 UI / API 行為改動，需同步 STATE / ARCHITECTURE。
>
> **v18.182 起 UI 入口暫封存**：「🧪 回測找參數」頂層 Tab + ETF 組合 Tab 內「② 歷史回測」sub-section 暫不渲染；下文提及的 `etf_tab_backtest` / `tab_backtest_optimization` 等模組**已於 v18.265 全刪**(改採前進式驗證,見 CLAUDE.md §2.3);下文相關段落僅為歷史語意規約記錄。

---

## §1 策略代號對應表（UI 顯示用）

> 來源：`ui_widgets.STRATEGY_VALUATION / STRATEGY_FINANCIAL / STRATEGY_TECHNICAL` + `_to_strategy()`。
> `strategy_box` / `strategy_conclusion` / `etf_render._strategy_conclusion` 三個 render 入口共用。
>
> ⚠️ **v19.174 去識別化**：本節原為「人名 → 策略」對應表，該人名字典（10 個 key）
> 已整份刪除。caller **一律直接傳策略代號常數**，不再傳人名字串；
> 變數名 / dict key / log / AI prompt 內部同步清乾淨。

| 常數 | 值 | 方法論 | icon |
|------|-----|--------|------|
| `STRATEGY_VALUATION` | `策略1` | 估值 / 存股（殖利率、357 區間、年線位階） | 💡 |
| `STRATEGY_FINANCIAL` | `策略2` | 財報體檢（現金、負債、毛利、盈餘品質） | 🏥 |
| `STRATEGY_TECHNICAL` | `策略3` | 技術 / 動能 / 資金面（VCP、均線、M1B-M2、VIX、法人） | 🎯 |

**未登記的字串** → `('策略', '👤')` fallback。這條退化路徑同時是「還有 caller 沒改乾淨」的
可見訊號（畫面會出現 👤 策略），刻意不 raise、也刻意不靜默。

**範圍邊界（v19.174 後）**：
- ✅ **改**：UI 顯示字串、變數名、函式名／參數名、docstring、註解、AI prompt
- ❌ **不改**：策略 1/2/3 的顯示形式（user 明確要求保留）、任何門檻數值

---

## §2 ETF 私募/特殊判別啟發式

> 來源：`etf_tab_single._likely_private`，輸出至 `session_state['etf_single_data']['_likely_private']`。

```python
_likely_private = (
    (not _is_overseas)        # 台股 4-6 碼代號（如 0050.TW / 00878.TW）
    and (not aum)              # yfinance .info[totalAssets] 也抓不到
    and (not expense)          # SITCA + MoneyDJ + yfinance 3 源皆空
    and (_nav_value is None)   # FinMind + goodinfo + TWSE + MoneyDJ + yfinance 5 源皆空
)
```

**health_inspector 行為**：
| 條件 | AUM | 費用率 | NAV |
|------|-----|--------|------|
| 海外 ETF（`_is_overseas`） | 不動 | `na` + 海外訊息 | `na` + 海外訊息 |
| 私募 ETF（`_likely_private`） | `na` + 私募訊息 | `na` + 私募訊息 | `na` + 私募訊息 |
| 一般 | 缺漏 → 紅 | 缺漏 → 紅 + 3源錯誤訊息 | 缺漏 → 紅 + 5源錯誤訊息 |

訊息字串：「私募/特殊 ETF — AUM、費用率、NAV 主流資料源皆未揭露」

---

## §3 批次分析個股 K 線 — 三態語意

> 來源：`tab_stock_grp._fetch_single_t3` 回傳 dict。

| 情境 | dict 內容 | 是否快取 4hr | UI 表現 |
|------|----------|----------|---------|
| 成功 | `{'sid','df','name','avg_div','cl','cx'}` | ✅ 快取 | 🟢 正常 |
| 空 K 線（雙源皆空） | + `'error': _err4 or '無 K 線資料...'` | ❌ 跳過快取 | 🔴 + 顯示原因 |
| Exception | `{'sid','error': str(_e4)}` | ❌ | 🔴 + 顯示原因 |
| Future timeout | `{'sid','error':'timeout'}` | ❌ | 🔴 + 顯示原因 |

下游 `health_inspector.py:853` 透過 `_fetch_err` 將 `error` 字串綁定到診斷列 `error_msg=`，不再「🔴 未取得」空白標。

---

## §4 TW PMI 8 源並行賽跑 — 失敗追蹤格式

> 來源：`macro_core.fetch_tw_pmi` + `PMI_SOURCE_REGISTRY`（SSOT）。失敗時回 `{'_err_pmi': str, 'value': None}`，`_err_pmi` 為各源失敗原因以 ` | ` 串接。
> （v19.113 同步：本表原停在 v19.85 前的 9 段舊制 — 仍列已拔的 FinMind、缺 v19.85 新增的 CIER-EN。以下依現行 registry 重寫；MacroMicro 段與 CIER cid=21 URL 於 v19.113 依探針 run 29182317622 實錘拔除。）

| 優先序 | 來源 | 失敗 token 範例 |
|------|------|-----------------|
| 1 | CIER 英文月度頁 | `CIER-EN.taiwan-manufacturing-pmi-june-2026:HTTP404` |
| 2 | data.gov.tw dataset/6100 | `dgtw./rest/dataset/6100:無回應` / `dgtw.xxx:HTTP503` |
| 3 | 國發會 NDC 景氣指標 | `NDC.a/indicator/PMI:無回應` / `NDC.xxx:HTTP404` |
| 4 | CIER 首頁標題掃描 | `CIER.ww.cier.edu.tw/:無回應` |
| 5 | StockFeel 搜尋頁 | `StockFeel:無回應` |
| 6 | 鉅亨網 API | `Cnyes:無回應` |
| 7 | CIER cid=8（PMI 專欄） | `CIER-cid8.news/list?cid=8:無回應` |
| 8 | MoneyDJ 知識庫搜尋 | `MoneyDJ:無回應` |

**設計原則**：每段失敗都必須寫入 `errs`，避免使用者只看到部分失敗訊息誤判系統。

---

## §5 etf_dashboard 三層職責邊界（Phase 7C — commit `44a0e87`）

> 來源：`etf_dashboard.py` 拆分為 `etf_fetch` / `etf_calc` / `etf_render` 三層。下游 6 個 importer (app / etf_quality / grape_ladder / 4 個 etf_tab_*) 一律 `from etf_dashboard import ...` 不變；新程式碼建議直接 import 對應子模組。

**依賴方向**（葉節點 → 上層，反向禁止）：

```
etf_fetch  ←  etf_calc  ←  etf_render  ←  etf_dashboard (shim)
```

| 層 | 模組 | 可放函式類型 | 禁止 |
|---|---|---|---|
| L1 純 I/O | `etf_fetch.py` | 對外 API 抓資料（yfinance / FinMind / SITCA / MoneyDJ / goodinfo / TWSE）、本地常數表（如 `_TW_ETF_LAUNCH_PRICE`）、檔位驗證 (`_safe_float` / `_NAV_MIN/MAX`) | 任何 `st.markdown` / `plotly` / 數值計算邏輯（除驗證外） |
| L2 純算 | `etf_calc.py` | 殖利率 / 總報酬 / 折溢價 / 風險指標 / 同儕排名 / 戰情室列；可呼叫 `etf_fetch.*` 取資料後計算 | 任何 `st.plotly_chart` / `st.markdown` UI 渲染 |
| L3 UI | `etf_render.py` | Streamlit / Plotly 渲染 (`_plot_etf_chart` / `_render_bias` / `_render_monte_carlo` / `render_sector_heatmap`)；呼叫 `etf_fetch` 取輕量 I/O（news / sector returns）；`ui_widgets._to_strategy` 一律 late import | 重新發明 `etf_calc` 已有的數值邏輯；直接呼叫外部 API（請走 `etf_fetch`） |
| L4 Shim | `etf_dashboard.py` | 純 re-export — 40 個 symbol + 4 個 tab 入口 | 新增任何邏輯（破壞 shim 純粹性）|

**判定邊界 case**：
- `_compute_etf_warroom_row` 混 fetch + calc → 放 **L2** (calc 可依賴 fetch，反向不可)
- `_safe_float` / NAV 常數 → 放 **L1** (與 NAV 解析配套，calc 層也可用)
- `_fetch_sector_returns` 含 `st.warning` → 仍放 **L1** (本質是 I/O，warning 為 cache miss 提示)
- `_strategy_conclusion`（v19.174 去識別化改名，舊名 alias 保留）用到 `ui_widgets._to_strategy` → 放 **L3**，採 late import 解循環風險

**新增 helper 流程**：
1. 看依賴：純抓資料 → L1；只算數字 → L2；產出 Streamlit element → L3
2. 寫好 helper 後在對應子模組頂部加 `__all__` 或直接 `from etf_xxx import ...` 至 `etf_dashboard.py` shim
3. 若供下游使用，務必 re-export 到 `etf_dashboard.py`（避免改下游 6 個 importer）

---

## §6 跨 tab 共用純函式（Phase 7A — commit `0ef1991` / Phase 7A-Ext — commit `e678d22`）

> 來源：`tab_helpers.py` + `macro_helpers.py`。零 Streamlit / Plotly 依賴，任何 module 皆可 import。

### §6.1 `tab_helpers.py`（5 函式）

| 函式 | 輸入 | 輸出 | 取代的 closure | 階段 |
|---|---|---|---|---|
| `parse_cash_flow_ratio(value, threshold, strict)` | str/None/NaN, float, bool | True / False / None | `_r110_ok_a` (tab_stock:2157) + `_r110_ok_b` (tab_stock_grp:723) | 7A |
| `format_condition_emoji(value)` | bool / None / 其他 | '✅' / '❌' / '⚪' | `_tk2` (tab_stock) + `_tk` (tab_stock_grp) | 7A |
| `safe_get(value)` | Any | value or None | `_v` (tab_macro:2667) | 7A |
| `safe_ma(df, n)` | DataFrame (需有 close 欄), int | float | `_safe_ma` (tab_stock:378) | 7A |
| `final_recommendation(row, score_map)` | dict, dict | (label, color_hex) | `_final_rec` (tab_stock_grp:382 closure) | 7A-Ext |

### §6.2 `macro_helpers.py`（4 函式 — Phase 7A-Ext + 7E）

> 從 `tab_macro.render_tab_macro` 抽出，獨立模組以避免 `tab_helpers.py` 引入 tab_macro 專屬邏輯污染。

| 函式 | 輸入 | 輸出 | 取代的 closure | Phase |
|---|---|---|---|---|
| `calc_traffic_light(mkt_info, jingqi_info, cl_data, li_latest)` | dict, dict, dict, DataFrame | dict (15 keys) or None | `_calc_traffic_light` (tab_macro:71-141, 71 行 nested def) | 7A-Ext |
| `rp_ts(df)` | DataFrame | str (YYYY-MM-DD or 'N/A') | `_rp_ts` (tab_macro:1663, 36 行 closure) | 7E |
| `rp_entry(df, cat, freq)` | DataFrame, str, str | dict (`last_updated`/`rows`/`category`/`frequency`[/`missing`]) | `_rp_entry` (tab_macro:1700) | 7E |
| `rp_scalar(val, cat, freq, proxy_date)` | Any, str, str, str | dict (同上) | `_rp_scalar` (tab_macro:1705) | 7E |

**`calc_traffic_light` 決策樹（5 路）**：
1. 三來源全空 → `None`（由 placeholder 顯示等待狀態）
2. `defense=True`（`score<2` 且外資期貨大空單 `<−30000`）或 `health<40` → 🔴 空頭防禦（強制覆蓋）
3. `regime == 'bull'` → 🟢 多頭積極
4. `regime in ('caution','bear')` → 🔴 保守防禦
5. 其他 → 🟡 震盪整理

**回傳 dict 16 keys**：`color / icon / label / action / sub / health / defense / score / jqavg / leek / fnet / fk / fut_net / conf / missing_sources / regime`

**`missing_sources: list[str]`（PR #1 新增）**：從 conf 計分的 5 個資料源 bool 反向列出缺失項，由 `_render_traffic_light` 在 conf<70 早回時逐項顯示給用戶。對應名稱固定為：

| 來源 | 缺失條件 | 顯示字串 |
|---|---|---|
| `mkt_info` | `not bool(mkt_info)` | `大盤趨勢評分 (market_regime)` |
| `jingqi_info` | `not bool(jingqi_info)` | `旌旗指數 (站上均線比例)` |
| `_fk`（外資 key） | 外資未在 inst dict | `外資買賣超 (三大法人)` |
| `li_latest` | None 或 empty | `先行指標 (期貨/PCR/韭菜)` |
| `_cd['adl']` | None | `ADL 騰落指標` |

**信心門檻 gating（PR #1）**：`_render_traffic_light` 渲染前先檢 `tl.get('conf', 0) < 70`：
- ✅ True → 橘色「⏸️ 資料不足，無法判斷市場狀態」卡片 + 逐項列 `missing_sources`，**不渲染燈號**（early-return）
- ❌ False → 正常渲染主燈號 + meta + 條件 badge；conf 介於 70-79 仍會在卡片下方顯示 `st.warning` 提醒

**`rp_ts` 時間源優先序（4 路）**：
1. `DatetimeIndex` → `df.index.max()`
2. 「季度標籤」欄（如 `'2024Q4'`）→ `_QE_MAP` 對應到該季最後一日（Q1=03-31, Q2=06-30, Q3=09-30, Q4=12-31）；無效 Q 數預設 `12-31`
3. 「年度」欄（int）→ `'YYYY-12-31'`
4. `_date | date | datetime | timestamp | 日期 | quarter | period` 欄 — `_date` 強制 `'%Y%m%d'`，其餘自動推斷
5. 全失敗或例外 → `'N/A'`

**`rp_scalar` proxy_date 設計**：由呼叫端傳入（tab_macro 用 `st.session_state.cl_ts` 解析的日期，或 fallback `today()`），避免 module-level 取系統時間造成測試不穩定。

### §6.3 通用慣例

**呼叫慣例**：
- ✅ Module-level `from tab_helpers import ...` / `from macro_helpers import ...`（純函式無循環風險）
- ❌ 不要在函式內 late import，會浪費 cache

**新增 helper 條件**：
1. 純 Python（含 pandas/numpy），無 `st.*` 呼叫、無 `plotly.*` 呼叫
2. **`tab_helpers.py`**：至少 2 個 tab_*.py 模組會用到（跨檔重複）；**`macro_helpers.py`**：tab_macro 專屬邏輯但需 unit test
3. 必須附對應 `tests/test_*.py` 測試（至少 normal / edge / None 三類 case）

### §6.4 `etf_helpers.py`（Phase 7B — 3 函式）

> 從 `etf_tab_backtest` / `etf_tab_portfolio` 抽出，獨立模組以避免 `tab_helpers.py` 混入 ETF 專屬邏輯。

| 函式 | 輸入 | 輸出 | 取代的 closure |
|---|---|---|---|
| `norm_return(v, lo=-50, mid=0, hi=50)` | float × 4 | float (0-100) | `_norm_return` (etf_tab_backtest:186) |
| `norm_lower_better(v, best=5, mid=20, worst=35)` | float × 4 | float (0-100) | `_norm_lower_better` (etf_tab_backtest:192) |
| `auto_role(tk)` | str / None | '核心' / '衛星' | `_auto_role` + `_CORE_TICKERS` (etf_tab_portfolio:45-51) |

**`_CORE_TICKERS` 白名單**（存股框架 #9，frozenset 防呆）：

| 類別 | ticker（去後綴） |
|---|---|
| 台股高股息 / 大型 | 0050, 0051, 0056, 006208, 00713, 00878, 00919, 00929, 00940, 00946 |
| 台股債券 | 00713B, 00679B, 00937B |
| 美股全市場 / 高股息 | VTI, VOO, SPY, VT, SCHD, VEA, VWO, VNQ |
| 美股債券 / REITs | BND, AGG, VNQ |

**邊界處理**：
- `norm_return`：v=hi → 100（含等號邊界）；v=mid → 50
- `norm_lower_better`：先 `abs(v)`，負數視為相同距離；v=best → 100；v=worst → 0
- `auto_role`：`.TW` / `.TWO` 後綴自動剝離；`None` / 空字串 → 衛星；大小寫不敏感

### §6.5 `ui_widgets.cond_badge`（Phase 7F — HTML 徽章函式）

> 從 `tab_macro.render_tab_macro` 五維點火條件列抽出至 `ui_widgets.py`（PR #60 既有 8 HTML 函式之延伸，現為第 9 個）。

| 函式 | 輸入 | 輸出 | 取代的 closure |
|---|---|---|---|
| `cond_badge(ok, label)` | bool/truthy, str | str (HTML span) | `_cond_badge` (tab_macro:3392) |

**配色**：
- `ok=True` → 綠色 `#3fb950`（背景 `+22` alpha + 邊框 + 文字皆同色）
- `ok=False` → 灰色 `#484f58`
- 其他純真值判斷（`0` / `None` / `''` 視為 False）

**設計**：HTML 字串模板（無 Streamlit 依賴），呼叫端負責用 `st.markdown(..., unsafe_allow_html=True)` 渲染。

**測試覆蓋（Phase 7G 補完 → v19.174 更新）**：`tests/test_ui_widgets.py` 涵蓋 `ui_widgets.py` 全 10 函式 + `TERM_EXPLAIN` / `_STRATEGY_ICON` 兩個常數 — `cond_badge` 8 + `TERM_EXPLAIN` 3 + `explain_box` 5 + `traffic_light` 7 + `beginner_kpi` 7 + `show_term_help` 5 + `kpi` 6 + `_to_strategy` 6 + `strategy_box` 5 + `strategy_conclusion` 10+ + `signal_box` 9 + 去識別化守衛 2。
> ✅ **v19.174 已收斂**：原人名字典已刪、`strategy_box` / `strategy_conclusion` 為正名
> （舊名保留過渡 alias，並有測試釘住 alias 指向新函式）。新增 `TestNoPersonNameInSource`
> 守衛：`ui_widgets.py` 原始碼與渲染輸出皆不得再出現人名。

### §6.6 同期修補：`_no_ai_survival` 1Q fallback（commit `e678d22`）

`financial_health_engine._no_ai_survival` 對 B 項（現金流量允當比率）分支：

| `b_item_5y.status` | b_val | b_display | b_st |
|---|---|---|---|
| `"ok"` | 5y 實際值 | `"127.3%（5年實際）"` | Pass/Fail |
| `"insufficient_data"` | None | `"N/A（上市未滿5年）"` | Fail |
| `"error"` | None | `"N/A（5年歷史資料未取得）"` | N/A |
| **缺 key（unit test / legacy 呼叫端）** | **1Q 估算** | **`"XX.X%(1Q估)"`** | **Pass/Fail** |

公式：`b_val = OCF / (capex + max(inv-inv_p, 0) + div) × 100`；`b_denom ≤ 0` → display `"N/A"`、status N/A。

---

## §7 文件治理連動

任何 §1–§6.6 規約變更必須同步：
- `STATE.md` — 加入 commit / PR 行
- `ARCHITECTURE.md` — 對應模組章節
- `SPEC.md`（本檔） — 直接更新對應表 / 啟發式

CLAUDE.md v2.0 §4：「請直接 merge PR + 存檔(STATE.md) 與也同步 ARCHITECTURE.md、SPEC.md」

---

## §8 ETF 持股組合雲端儲存 — OAuth 雙模式契約（commit `0c6e0b9`）

對應模組：`gsheet_portfolio.py` / `oauth_state.py` / `infra/oauth.py`；UI：`etf_tab_portfolio._render_oauth_panel` + `_render_cloud_storage` + `app.py` sidebar Google 帳號區。

### §8.1 認證模式優先序

`gsheet_portfolio.is_configured()` 回傳 `_oauth_active() or _sa_configured()`，任一為真即可使用雲端儲存。`_build_client()` 內部優先序：

| 模式 | 觸發條件 | Sheet ID 來源 | 適用場景 |
|------|---------|--------------|---------|
| **OAuth**（推薦） | `_oauth_configured` + `session_state['gsheet_tokens']` 存在 + 有 Sheet ID | `session_state['portfolio_sheet_id']`（使用者輸入） | 使用者自帶 Sheet，無須管理員設定 secrets |
| **SA fallback** | `st.secrets['portfolio_sheet_id']` + `[gcp_service_account]` 皆存在 | `st.secrets['portfolio_sheet_id']` | 管理員部署、向後相容 PR #5 |

OAuth 條件不滿足時自動降級為 SA，兩者皆缺則 `is_configured() = False`，UI 顯示設定面板。

### §8.2 OAuth Client 配置來源優先序

`oauth_state._resolve_oauth_cfg()`：

1. `st.secrets['google_oauth']`（部署層）— 三欄齊備：`client_id` / `client_secret` / `redirect_uri`
2. `st.session_state['custom_oauth_cfg']`（in-app wizard）— 同三欄

兩者皆缺 → `_oauth_configured = False`，UI 顯示 OAuth Client 設定 wizard。

### §8.3 Sheet ID 解析

`etf_tab_portfolio._render_oauth_panel` Sheet URL 輸入框 regex：`r'/spreadsheets/d/([a-zA-Z0-9_-]+)'`。若使用者貼整段 URL 自動抽 ID；若直接貼 ID 則原樣保存。寫入 `st.session_state['portfolio_sheet_id']`。

### §8.4 Token 生命週期

`infra.oauth.ensure_fresh_tokens(tokens, client_id, client_secret)` 在過期前 **60 秒** 自動 refresh；`_get_oauth_client()` 每次呼叫都跑一次 refresh 並回寫 `session_state['gsheet_tokens']`。因此 `_ws()` **不可** 用 `st.cache_resource` 包裝（token 換新後舊 client 會失效）。

### §8.5 OAuth Callback 入點

`app.py` module body 在 `st.set_page_config` 之後、sidebar 渲染之前呼叫一次：

```python
from oauth_state import handle_oauth_callback as _oauth_cb
_oauth_cb()
```

收到 `?code=...` 且 `gsheet_tokens` 尚未存在 → 換 token → 清 URL params → `st.rerun()`。例外吞掉並 `print`，避免阻擋主畫面渲染。

### §8.6 純函式 API 不變式

PR #5 既有 5 個 API（`is_configured` / `list_portfolios` / `load_portfolio` / `save_portfolio` / `delete_portfolio`）契約跨 OAuth ↔ SA 切換 **零修改**。`tests/test_gsheet_portfolio.py` 20 cases 在 monkeypatch `_get_worksheet` 的前提下全綠（未碰 `_build_client` 內部分支）。

---

## §9 v5.0 — 判斷單一真相 + 集保籌碼整合 + 資料源備援 + 故事化白話層（branch `claude/debug-api-key-JmH9N`）

### §9.1 總經「今日行動建議」單一真相（PR #42）
總經 tab 原有 4 個獨立判斷引擎易互相矛盾，現以**紅綠燈為單一真相**：

| 元件 | 多空結論來源 | 建議持股來源 |
|---|---|---|
| ① 紅綠燈 / ② 戰情概覽 | `calc_traffic_light` → `_tl_eff_reg` | `market_regime` `exposure_pct` |
| ③ 今日唯一行動建議 | **`_wr_reg`（=紅綠燈）** | **`market_regime` `exposure_pct`**（原為 v4，已改） |
| ⑩ AI 總裁決 | `macro_state.json` 快照 | 快照 `exposure_limit_pct` |

- v4（`evaluate_market_status_v4_final`，僅 price vs ma240 + 期貨）降為「📐 年線位階參考」補充小字，不再主導 ③ 的結論/色彩/持股。
- ⑩ 快照 regime 與即時 `_tl_eff_reg` 不一致時 → `st.warning` 提醒重按「執行 AI 裁決」。

### §9.2 集保籌碼大戶雷達介面（PR #45）
`chip_radar.render_chip_radar(ticker: str = '') -> str`：
- 移除自有 `text_input` / 按鈕 / `_chip_radar_active`；改由呼叫端傳入個股主代碼 `sid2`。
- 回傳籌碼摘要字串（`集保大戶持股比例=X%（近5期↑/↓）| 散戶人數=N`；無資料回 `''`）。
- 位置：`tab_stock` 內、置於「🤖 AI 首席顧問總結」**上方**；摘要注入 AI prompt「籌碼動向」段（三大法人 + 集保大戶並列），使總結涵蓋集保籌碼章節。

### §9.3 FinMind SDK 缺失備援（PR #44）
`data_loader.py`：FinMind `DataLoader` import 失敗時 `self.dl = None`。個股價格改走 `_fetch_finmind_price_raw()`（v4 HTTP `TaiwanStockPrice`，回傳與 `taiwan_stock_daily` 相同原生欄位），不再 `NoneType` 崩潰。其餘 `dl.*` 呼叫皆已 try/except 或有 raw fallback，優雅降級為 N/A。

### §9.4 故事化白話層原則（PR #37/#40/#41/#43/#46/#47）
- 純疊加 `st.expander` / `st.caption` 白話導讀，**零更動計算邏輯**。
- **不重複既有白話**（總經 `beginner_kpi`/`strategy_conclusion`、個股白話問句標題等已白話處不再加）。
- Streamlit **不可巢狀 expander** → 白話 expander 須置於既有 expander 之外（個股財報名詞快查即放在「策略2」expander 外）。
- v5.0 Task 3（每 tab AI 解盤）盤點後確認**各重點 tab 早已有 AI**（總經/個股/組合/智慧選股/ETF），不另加通用模組（PR #38 誤加個股第二個 AI 已 #39 撤回）。

### §9.5 個股 AI 總結納入近半年新聞（PR #53）
`app._fetch_stock_news(stock_id, stock_name, n, recency)`：新增 `recency`（Google News `when:6m` 偏近半年）、每則加 `link`、依 `published_parsed` 新→舊排序（向後相容，舊呼叫端不受影響）。
- `tab_stock`「🤖 AI 首席顧問總結」：新聞 5→25 則（`recency='6m'`）；新增可摺疊「📰 近半年相關新聞」清單（日期＋可點標題＋來源；存 `session_state[_ai_sum_key+'_news']`，隨快取報告一併顯示）。
- Prompt 強化：【近期相關新聞】→【近半年相關新聞】；【分析指令】加「步驟六：新聞事件面」（歸納利多催化劑 / 利空風險事件，並與技術籌碼訊號交叉印證或背離）；【輸出格式】三、深度解析加「新聞事件面」bullet。五維雷達結構不變（新聞為事件面補充，非第六軸）。
- **限制**：免費 Google News RSS 偏近期，無法保證涵蓋完整半年，介面已誠實標示「近期為主」。
- **新聞抓取串接（PR #56-#59）**：NAS中繼站(`nas_relay_fetch`)→Squid proxy(帶 `CONSENT=YES` cookie 繞 Google 同意頁)→直連；診斷面板逐路徑記 HTTP/則數。個股 + ETF 新聞共用此模式。

### §9.8 故事化白話覆蓋（全 tab 一致，PR #61/#62）
任務二補完低密度 tab 的「💡 這項數據代表什麼？」`st.expander`（純疊加、非巢狀、零更動計算）：
- **ETF 單一**：內扣費用率 / Beta / AUM；**ETF 回測**：CAGR / 夏普值 / 最大回撤 / 年化波動率。
- **高息網**：殖利率 / 本益比 / 股價淨值比 / 「7% 防禦網」；**智慧選股**：三階段濾網（基本面9→籌碼技術6→AI）。
- 總經 / 個股 / 個股組合 / 教學原已具備 → 各主要 tab 故事化白話覆蓋一致。
- **PR #69 收尾**：葡萄串領息法、產業熱力圖、ETF 組合配置（核心/衛星·再平衡·Overlap）補 💡 → 9 tab 全覆蓋。

### §9.9 每 tab AI 補餵該頁全章節（PR #70-#73）
稽核 4 個 tab AI 後，補齊「頁面有算但 AI 沒餵」的章節（皆 defensive 取值）：
- **個股組合 AI**：每檔五維分數(趨勢/動能/籌碼/量價/RS)、SQ品質分/FGMS、財報體檢(現金水位/OCF/負債比/雷達均分) + 【風控警示】段。
- **智慧選股 Stage3 AI**：餵滿 Stage1 全 9 項 + Stage2 全 6 項，修正 `/4`/`/3` 錯標為 `/9`/`/6`。
- **總經 AI 裁決**：`_v_macro_ctx` 補 NDC 景氣燈號 / 台灣 PMI / 外銷訂單 / 美核心 CPI / 美股科技動能(SOX/NVDA)。
- **ETF AI**：跨檔持久化 `session_state['etf_overlap_summary']`（持股重疊=重複押注）+ `['etf_weakness_summary']`（主動 ETF 換股訊號），注入 Input Data。

### §9.6 個股 AI 總結補餵已算章節（PR #55）
原 prompt 僅含技術/籌碼/基本面/財報體檢/新聞/總經；四、戰術建議價位由 AI 臆測。改為補餵 `tab_stock` 上方**已實算**三章節（全程 try/except 防呆，未算到顯示「未計算」不崩）：
- 【關鍵價位｜支撐壓力與停利停損】：近20日壓力/支撐(`_hi20_p`/`_lo20_p`)、停利1/2(`_tp1_p`/`_tp2_p`)、停損(`_sl_p`)、盈虧比(`_rr_p`)、型態買點/絕對停損(`_entry_half`/`_abs_sl`)。
- 【近20日籌碼集中度】：`_con20`/`_cty20`/`_sig20`（注入籌碼動向段）。
- 【基本面先行指標 D2】：`_li_green/_li_yellow/_li_red` + 明細。
- **（PR #68 再補兩章節，`locals().get()` 防呆）**：**RS 相對強度**（`_rs_val`，注入技術指標段）、**龍頭擴產檢測**（合約負債/股本比、資本支出/股本比 + 龍頭多方門檻判定，注入財務基本面段）。
- 指令強化：四、戰術建議**強制引用系統實算價位、嚴禁自行虛構**；步驟一納入籌碼集中度 + RS、步驟二納入 D2 先行指標 + 龍頭擴產檢測。

### §9.7 個股新聞改走 NAS FastAPI 中繼站（PR #56/#57）
雲端機房 IP 直連 Google News RSS **一律 403**（沙箱實測）；Squid proxy CONNECT 對 Google 亦可能受阻 → 新聞長期抓不到。
- `proxy_helper.nas_relay_fetch(url)`：呼叫 `nas_server.py` 的 `/proxy?url=...` 透明中繼端點（家用台灣 IP server-side 代抓、原樣回傳 body），帶 `X-API-Key`。
- `_fetch_stock_news` 抓取串接：**NAS 中繼站 → Squid proxy → 直連**；查詢字串 `urllib.parse.quote` 編碼；`_diag` 逐路徑記錄 HTTP/則數供 UI 顯示。
- **需設定**：Secrets `NAS_BASE_URL`（如 `http://xxx.synology.me:8765`）+ `NAS_API_KEY`，且 `nas_server.py` 運行、該埠對 Streamlit Cloud 可達。未設定則自動跳過、回退 Squid/直連。

## §10 三維出場訊號（`exit_signals.py`）

純邏輯模組（不抓資料、不畫 UI）。三個維度任一成立記 1 分，總分決定等級。

### §10.1 維度定義
| 維度 | 成立條件 | 資料來源 |
|---|---|---|
| ① 利空新聞 | LLM 判 `label=='利空'` 且 `confidence>=50` | Gemini 情緒判讀（呼叫端傳入 `gemini_call`）|
| ② 技術轉空 | 含**強訊號**（空頭排列 股<月<季線／週MACD翻負）或 **≥2 條警示**（跌破季線/年線/5MA、月線正乖離>15%、KD高檔死叉 K>70）| OHLC DataFrame（+ 呼叫端算好的 KD）|
| ③ 籌碼倒貨 | `analyze_20d_chips_from_df()` 之 `signal` 含「大戶倒貨」（🔴）| 近 20 日法人/量（複用 K 線 df）|

### §10.2 分級（命中維度數）
`3 → 🔴 強烈出場` / `2 → 🟠 建議減碼` / `1 → 🟡 留意觀察` / `0 → 🟢 訊號清淡`

### §10.3 公開 API（不變式）
- `compute_tech_bearish(df, k=None, d=None) -> {'bearish':bool,'reasons':[str],'hits':int,'strong':bool}`
- `judge_news_sentiment(_gemini_call, name, headlines) -> {'label':'利空|中性|利多','confidence':0-100,'reason':str,'ok':bool}`；Gemini 失效或無新聞一律回**中性**（不阻斷流程）。
- `judge_news_sentiment_cached(_gemini_call, sid, name, headlines)`：以 `st.cache_data(ttl=6h)` 包裝，key=`(sid, name, 標題 tuple)`，`_gemini_call` 以底線前綴排除於 hash 外；無 streamlit 環境（單元測試）自動退回未快取版。
- `parse_news_sentiment(raw)`：沿用 `financial_health_engine._extract_json` 清洗慣例（去 ```json 圍欄 + 抓首個 `{...}`）；非法 label 正規化為「中性」、confidence clamp 0-100。
- `evaluate_exit_signals(tech, chip_signal, news, news_conf_threshold=50) -> {'score','icon','label','color','dims':[(名稱,命中,說明)],'hit_names','headline'}`；`news=None` 代表「未掃描」（最高僅能達 2 分）。

### §10.4 兩 tab 接線
- **個股 tab**：進出場訊號三欄**上方**插入「🚨 出場點綜合提示」banner（舊各策略 `_exit`/`_entry` 訊號完整保留為詳細層）；新聞自動判讀（標題以 session_state 暫存避免每次 rerun 重打 RSS）。
- **個股組合 tab**：批次迴圈每檔算 ②③ 兩維存入 `_ex_tech`/`_ex_chip_sig`（隨 `t3_data` 快取）；④汰弱留強表新增「出場」欄（`🔴3/3` 格式）。① 利空新聞 LLM 第三維由「🤖 AI 掃利空」鈕**按需觸發**（避免每次開組合對每檔打 Gemini 耗額度），結果存 `session_state['_grp_news_sent']`。

---

## §11 總經五桶 × 危險門檻一覽（`shared/macro_buckets.py` SSOT）

> v18.284。「總經」頂部五桶總結 bar、指標圖表上的黃/紅標準線、本表三者**同源** —
> 全部讀 `shared/macro_buckets.py::BUCKET_DANGER_SPECS`，改門檻只改一處。
> 目的：一眼看出**哪個指標正逼近危險線**。
>
> **v18.338 — Fund 式分組卡片網格（第 4 個同源 surface）**：`bucket_indicator_cards_html`
> 把某桶 `details` 渲染成卡片網格，每張卡 = **小圖**（`DangerSpec.emoji`）+ 名稱 +
> 燈號值 + **SPEC 註解**（`DangerSpec.note`，即本表「綠/黃/紅」語意）。先套用 🌳 長期桶
> 當模板（`render_macro_bucket_summary_bar('long', with_cards=True)`，tab_macro §七）；
> 其餘 4 桶待 user 確認後續套。小圖：總經健康評分 🩺 / NDC 🚦 / M1B-M2 💰。
>
> **相關**：個股面板（`tab_stock`）6 桶 Bar 亦於 v18.337 加「一句結論 + 燈號」
> （`compute_stock_section_levels` → `section_header_html(level=, headline=)`），
> 門檻同走 SSOT（健康度 `HEALTH_GRADE_*` / RS `RS_SCORE_*` / 先行指標最差燈號聚合）。

**門檻來源透明度**（`DangerSpec.source`）:
- 🔵 **官方 / SSOT**：有既有常數背書（`MACRO_THRESHOLDS` 鏡像由 `test_macro_buckets.py` 守漂移；或直接 import `signal_thresholds`）。
- ⚪ **系統設計**：本桶為 UI 判讀方便自訂之警示線，無單一官方源（具名 + 文件化，非腦補；§1 反捏造不適用 — 此為 UI 門檻 config，非偽造資料輸出）。

**方向**：`high_bad`=值越高越危險（紅線在上）｜`low_bad`=值越低越危險（紅線在下）｜`band`=兩端皆危險。

### 🌳 長期（結構 / 景氣位階）
| 指標 | 單位 | 🟢 綠 | 🟡 黃線 | 🔴 紅線 | 方向 | 來源 |
|---|---|---|---|---|---|---|
| 總經健康評分 | — | >50 | 35–50 | <35 | low_bad | 🔵35(DEFENSE)+⚪50 |
| NDC 景氣對策燈號 | 分 | 23–31 綠 | 17–22 / 32–37 | ≤16 藍 / ≥38 紅 | band | ⚪NDC 9藍-45紅 |
| M1B-M2 資金動能 | % | ≥1 黃金交叉 | 0–1 | <0 死亡交叉 | low_bad | ⚪資金交叉慣例 |

### 📈 中期（景氣循環 3-12 月）
| 指標 | 單位 | 🟢 綠 | 🟡 黃線 | 🔴 紅線 | 方向 | 來源 |
|---|---|---|---|---|---|---|
| 台灣 PMI | — | >50 | 46–50 收縮 | <46 嚴重收縮 | low_bad | 🔵MACRO_THRESHOLDS.PMI |
| 美國核心 CPI YoY | % | <3.5 | 3.5–4.0 | ≥4.0 通膨嚴峻 | high_bad | 🔵MACRO_THRESHOLDS.CPI |
| 台灣出口訂單 YoY | % | >0 | −5–0 | ≤−5 連續衰退 | low_bad | 🔵出口否決權 −5% |
| 年線乖離 BIAS240 | % | <10 | 10–20 | ≥20 正乖離過熱 | high_bad | 🔵±20+⚪10（負乖離=超賣機會非危險）|

### ⚡ 短線急殺（即時 risk-off）
| 指標 | 單位 | 🟢 綠 | 🟡 黃線 | 🔴 紅線 | 方向 | 來源 |
|---|---|---|---|---|---|---|
| VIX 恐慌指數 | — | <22 | 22–30 | ≥30 強制空手 | high_bad | 🔵MACRO_THRESHOLDS.VIX |
| ADL 漲跌家數比 | % | >50 | 35–50 | <35 廣度崩 | low_bad | ⚪市場廣度慣例 |
| 外資期貨淨口 | 口 | >−10000 | −20000～−10000 | ≤−20000 大戶閃人 | low_bad | 🔵FOREIGN_FUTURES_*_LOTS |

### 🧩 籌碼（大戶定位 日線）
| 指標 | 單位 | 🟢 綠 | 🟡 黃線 | 🔴 紅線 | 方向 | 來源 |
|---|---|---|---|---|---|---|
| 融資餘額 | 億 | <2500 | 2500–3400 | ≥3400 散戶槓桿極危 | high_bad | 🔵3400+⚪2500 |
| 旌旗指數（站上 20MA %） | % | >60 積極 | 40–60 中性 | <40 弱勢 | low_bad | ⚪站上均線比例 |
| 外資現貨淨買賣 | 億 | >0 買超 | −200–0 賣超 | ≤−200 大賣（軟線）| low_bad | ⚪外資現貨流向 |

### 📰 新聞（系統性風險掃描）
| 指標 | 單位 | 🟢 綠 | 🟡 黃線 | 🔴 紅線 | 方向 | 來源 |
|---|---|---|---|---|---|---|
| 系統性風險新聞數 | 則 | 0 | 1 | ≥2（戰爭/倒閉/崩盤命中）| high_bad | ⚪命中則數規則 |

> 桶燈號 = 該桶所有指標分級取**最危險者**（紅>黃>綠>灰未載入）。籌碼/新聞桶資料屬
> Phase 2（需按「🚀 一鍵更新全部數據」/「執行 AI 裁決」），未載入時顯示 ⬜ 而非偽綠（§1 Fail Loud）。

---

## §12 個股組合（`tab_stock_grp.py`）評分門檻 SSOT + 舊評分退役（v18.322）

> user 2026-06-27 要求：個股組合頁的計算/指標/判斷須維持 §3.3 SSOT；違反者收斂 +
> 結論入 SPEC。本節為審計結論與決策紀錄。

### §12.1 「舊評分」退役（Option A）

- **決策**：移除「④ 汰弱留強」原本的 0-10「舊評分」(`old_score4`)，④ 改以**純健康度**排序。
- **理由**（3 點）：
  1. 已被「多因子評分 0-100」(`scoring_engine.score_single_stock`，含景氣動態權重) 大幅取代；連 AI ⑤ 綜合判讀都優先用 `total`、舊評分僅當 fallback。
  2. **重複計算**：舊評分內的「健康度÷50」「估值便宜+3」與同表的健康度欄、357評價欄同源再算一次。
  3. **名實不符**：頁面「🔰 怎麼看」自述 ④ = 「健康度（均線／RSI／KD／量比／布林）」，但實際排序鍵是舊評分（含估值/VCP/合約負債）。退役後 ④ 真的以健康度排，名實一致。
- **影響**：④ 表移除「評分 ⭐」欄；排序由 `['舊評分','健康度']` → `健康度` 單鍵。AI ⑤ fallback 由 `舊評分` → `健康度`。**多因子 ③ 排行不受影響**。

### §12.2 個股組合判斷門檻 SSOT（原 inline → `shared/signal_thresholds.py`）

| 常數 | 值 | 用途 | 原 inline 位置 |
|---|---|---|---|
| `GRP_VOL_SHRINK_RATIO` | 0.7 | 操作狀態燈「量縮」(量<20日均量×0.7) | tab_stock_grp.py:298 |
| `GRP_NEAR_MA20_BIAS_PCT` | 3.0 | 操作狀態燈「近20MA」(\|乖離\|<3%) | tab_stock_grp.py:299 |
| `GRP_BIAS_OVERHEAT_WARN_PCT` | 25.0 | 操作狀態燈「乖離過熱」(>+25%→🟡) | tab_stock_grp.py:302 |
| `GRP_NEWS_BEARISH_CONFIDENCE_MIN` | 50.0 | 利空新聞採信門檻(AI confidence≥50) | tab_stock_grp.py:600 |
| `MULTIFACTOR_GRADE_A_MIN` | 75.0 | 多因子總分 A 級下限 | scoring_engine.py:355 |
| `MULTIFACTOR_GRADE_B_MIN` | 55.0 | 多因子總分 B 級下限 | scoring_engine.py:357 |
| `MULTIFACTOR_ENTRY_MIN` | 70.0 | 多因子「入選候選」門檻 | tab_stock_grp.py:520 |

- 健康度分級 `80/50` 改 import 既有 `HEALTH_GRADE_A_MIN`/`HEALTH_GRADE_B_MIN`（原 inline 於 tab_stock_grp.py:300/564）。
- **多因子分級(75/A,55/B) ≠ 健康度分級(80/A,50/B)**：兩套評分體系，門檻各自獨立，**不可耦合相等**（`tests/test_grp_ssot.py` 守此不變量）。

### §12.3 單一個股 vs 個股組合「評分不同」— 維持（user 確認）

- 兩頁本就不同引擎：**單一**以健康度(6技術)+四維基本面深挖一檔；**組合**以多因子0-100(動態權重)排序 + 批次財報體檢 + 財報趨勢 + **綜合評論**。
- user 2026-06-27 明示：「組合一定會跟單一不同，因為要綜合評論+評分，這可以維持」→ **不統一跨頁總分**，此差異為設計，非違憲。

### §12.4 版面（維持）

- 上方 = 整體結論（⑤ 最終綜合建議 `strategy_conclusion`）；下方 = Raw 明細（③④ 排行表 / 🏥 批次財報體檢）+ 🤖 AI 綜合判讀，**已符合**「上結論／下 Raw+AI」，本次不重排。

## §13 財報體檢門檻 SSOT + 3 漂移修正（`financial_health_engine.py`，v18.323）

> user 2026-06-27 深層 SSOT 第 1 階段（PR-A）。`financial_health_engine.py` 的
> 「4 力 1 棒子 + 現金流矩陣」門檻原同時硬寫在 **AI prompt 文字** 與 **6 個 `_no_ai_*`
> fallback 計算**兩處。本節為審計結論與決策紀錄。SSOT 落於 `shared/financial_health_thresholds.py`。
>
> ⚠️ **v19.174 去識別化**：常數前綴改為 `FH_*`（Financial Health），**數值一個都沒改**；
> 舊前綴（人名縮寫）保留為過渡期 alias（同檔尾段），caller 收乾淨後可刪 —— 見
> `tests/test_financial_health_ssot.py::test_all_19_plus_aliases_match` 釘住同值。

### §13.1 SSOT 化策略（prompt 與 code 雙表徵）

- **code 端**（6 個 `_no_ai_*` + `_derive_basic_from_fin_data`）：inline 數字 → `import` 常數，消滅計算端 magic number。
- **prompt 端**：門檻數字寫在自然語言 prompt 內（如「Pass (綠燈)：>= 25%」），**不** f-string 模板化（避免破壞既有 `{{ }}` JSON 轉義、降低 AI 解析風險）；改由 `tests/test_financial_health_ssot.py` **golden test** 釘住「prompt 文字內數值 == SSOT 常數」，任一邊漂移測試即紅。
- radar 估分曲線（`_derive` 的 `_score`）僅生死關門檻（現金 25/10、毛利 Good 40）走 SSOT，其餘 radar 專屬曲線斷點屬單用途，保 inline。

### §13.2 財報體檢門檻常數表（`shared/financial_health_thresholds.py`）

> v19.174 起前綴為 `FH_*`；下表括號註記舊 alias 名。

| 常數 | 值 | 用途 |
|---|---|---|
| `FH_CASH_RATIO_SAFE_PCT` / `_WATCH_PCT` | 25 / 10 | 氣長（現金/總資產）安全/注意線 |
| `FH_DSO_FAST_DAYS` / `_SLOW_DAYS` | 15 / 90 | 收現速度（DSO）快/慢線；亦為償債交叉驗證條件 B |
| `FH_CASHFLOW_RATIO_MIN_PCT` / `_ADEQUACY_MIN_PCT` / `FH_CASH_REINVEST_MIN_PCT` | 100 / 100 / 10 | 現金流自給「100-100-10 法則」A/B/C |
| `FH_DEBT_RATIO_EXCELLENT_PCT` / `_PASS_PCT` / `_WARN_PCT` | 40 / 60 / 70 | 負債結構：優秀/安全/警戒線 |
| `FH_LONG_TERM_FUNDING_MIN_PCT` | 100 | 以長支長比率 |
| `FH_CURRENT_RATIO_MIN_PCT` / `FH_QUICK_RATIO_MIN_PCT` | 300 / 150 | 流動/速動比率（極嚴標準） |
| `FH_GROSS_MARGIN_GOOD_PCT` | 40 | 毛利率 Good 線（**漂移2修正**） |
| `FH_MOS_STRONG_PCT` | 60 | 經營安全邊際 Strong 線（**漂移3修正**） |
| `FH_NET_MARGIN_PASS_PCT` | 10 | 稅後淨利率 Pass 線 |
| `FH_ROE_LEVERAGE_CHECK_PCT` | 15 | ROE 槓桿防呆觸發線 |
| `FH_DUPONT_LEVERAGE_DEBT_PCT` | 65 | 杜邦槓桿膨脹警報負債門檻（**漂移1修正**，與結構線 60 刻意分離） |
| `FH_EARNINGS_QUALITY_MIN_PCT` | 100 | 盈餘品質（OCF/淨利） |

### §13.3 3 處漂移收斂決策（git blame 證實同 commit `4ebe5bc` 手誤、非後期調參）

| 漂移 | prompt vs code | 決策 | no-AI 輸出影響 |
|---|---|---|---|
| **1. 負債槓桿警報** | prof prompt 60 vs prof code 65（advanced 兩端皆 65） | **名稱分離**：一般負債結構安全線 `FH_DEBT_RATIO_PASS_PCT=60`（不同用途）與杜邦槓桿警報 `FH_DUPONT_LEVERAGE_DEBT_PCT=65` 各自具名；修 prof prompt 60→65 對齊其 code + advanced | 無（僅 AI prompt 文字對齊） |
| **2. 毛利率 Good** | prompt >20% vs code >=40% | **對齊 40%**（保 code 現值，修 prompt 20→40），合「高毛利才是護城河」原則 | 無（AI 變嚴格） |
| **3. 安全邊際 Strong** | prompt >60% vs code >=20% | **對齊 60%**（安全邊際>60% 表毛利衰退 40% 本業仍不虧；修 code bug 20→60，保三階 Strong/Acceptable/Weak） | 20–60% MOS 由 Strong→Acceptable |

- golden test `tests/test_financial_health_ssot.py` 守 3 漂移修正 + prompt/code 一致；`tests/test_financial_health_engine.py` 既有負債 45→Pass / 65→Warning / 75→Fail 邊界不受影響（仍釘 60/70）。

## §14 scoring_engine 評分曲線 / 交易濾網斷點全抽 SSOT（v18.324）

> 深層 SSOT 第 2 階段（PR-B）。audit 結論原建議：scoring_engine 的單用途評分曲線斷點屬
> §8.1 step 6「用不到的抽象」，登記 EX-SCORE-1 例外即可、不大抽。**user 2026-06-27 覆寫**
> 此建議，明示「全部抽成常數」。本節記錄落地範圍與分名原則。

### §14.1 抽取範圍（純等值替換，行為不變）

`scoring_engine.py` 各「判斷門檻」(value→score/label/signal 的比較斷點)全部抽至
`shared/signal_thresholds.py`（單一 import 源，延續既有 ATR_PCT/MULTIFACTOR 先例），涵蓋：
- **評分函式**：動能 Sharpe(`MOM_*`)、風險波動率(`RISK_*`)、RS 相對強度(`RS_*`)、
  獲利品質 SQ(`SQ_*`)、前瞻動能 FGMS 含維度權重 + 曲線(`FGMS_*`)
- **先行指標 narrative**：I3 合約負債 / I4 CapEx / I5 存貨 的 🟢🟡🔴 斷點(`LEAD_*`)
- **進階因子 check_***：合約負債大增(`CL_*`)、布林壓縮(`BOLL_*`)、假突破(`FAKEOUT_*`)、
  相對強度天數(`RS_STRONG_DAYS_MIN`)
- **風控 / 部位**：盈虧比(`RR_*`)、ATR 停損(`ATR_STOP_*`)、時間停損(`TIME_STOP_*`)、
  VCP 收縮(`VCP_*`)、軋空加分(`SQUEEZE_*`)、動態部位(`POS_*`)

### §14.2 不抽（明確排除，非判斷門檻）

指標視窗期（MA5/20/60/120、RSI14、ATR14、rolling 20）= TA 慣例；評分輸出值（2/1/0 子分、
`/6 /3 *100` 正規化）= 評分刻度結構；數學防呆（`1e-10`）；年化倍數（`×4`）；日數慣例（360/365）；
自然零界（`>0`）。這些非「判斷閾值」，抽取無助於 SSOT 反增噪音。

### §14.3 前綴分名「同數字不同義」不耦合（不變量）

SQ 標籤 `75` ≠ FGMS 標籤 `75` ≠ 多因子總分 `75` —— 三者同值但語意獨立，各自具名
（`SQ_GOOD_MIN` / `FGMS_LABEL_T1` / `MULTIFACTOR_GRADE_A_MIN`），改其一不牽動其餘。
此為避開 F-GRAY-4（Fund 端）「多用途閾值機械式 swap」教訓的關鍵守則，
`tests/test_scoring_thresholds_ssot.py` 守此不變量 + 行為不變 smoke。

### §14.4 對照 financial_health（§13）的策略差異

financial_health 因 prompt/code 雙表徵 + 真漂移 → SSOT 有「修 bug」實益；scoring_engine
為純單用途曲線 → 抽取為**形式 SSOT**（無 bug 可修，純消滅 inline magic）。兩者落地手法
（前綴分名、行為不變）一致，但 ROI 性質不同，已如實記錄供日後評估。

## §15 跨檔 SSOT 稽核 A/B 類收斂（融資 / 廣度 / macro_compass / 健康度，v18.325-326）

> user 2026-06-27 要求「檢查還有哪些違反 SSOT」。3 組並行 Explore agent 掃 L1/L2/L3/L5。
> L2 核心運算層全清；違反集中於 L1 macro_compass + L5 UI tab。分 PR-C（A 類）/ PR-D（B 類）收。

### §15.1 PR-C（A 類）— 既有 SSOT 常數被 inline 繞過（v18.325，零行為變動）

| 既有常數 | 值 | 改 import 的位置 |
|---|---|---|
| `MARGIN_BALANCE_OVERHEAT_THRESHOLD_YI` | 3400 | daily_checklist:814-815 / tab_macro:945,2168,2182,4282 |
| `HEALTH_GRADE_A_MIN` / `HEALTH_GRADE_B_MIN` | 80 / 50 | tab_stock:1134,1242,1243,1244,1649 |
| `CAPEX_TO_EQUITY_RATIO_THRESHOLD_PCT` | 80 | tab_stock:3282（龍頭資本支出/股本） |

### §15.2 PR-D（B 類）— 新增常數 + VIX 對齊（v18.326）

| 新常數 | 值 | 用途 |
|---|---|---|
| `MARGIN_BALANCE_WARN_THRESHOLD_YI` | 2500 | 融資黃線（daily_checklist + tab_macro 4 處） |
| `BREADTH_BULL/NEUTRAL/BEAR_PCT` | 60/40/20 | 市場廣度 jq_ratio/ADL regime（tab_macro 多處） |
| `TNX_VALUATION_PRESSURE_PCT` / `TNX_NEUTRAL_PCT` | 4.5 / 3.5 | macro_compass 殖利率燈號（保行為） |

**唯一行為變動（user 核准）**：`macro_compass._sig_vix` 黃線 **25→22**，複用
`MACRO_THRESHOLDS['VIX']`，對齊 C2（v19.157-160）全站統一黃線 22。macro_compass 原為 C2 漏網。

### §15.3 ✅ 分歧統一收斂（PR-E v18.327，user 拍板「全面對齊標準值」）

PR-D 過程發現 3 組同概念門檻在不同卡片用不同值（會讓使用者看到自打架結論，如 health2=55
標籤顯示弱勢、評語卻說可分批布局）。user 2026-06-27 依存股風險邏輯**全面對齊標準值**，
移除分歧變體常數，行為變動如下：

| 概念 | 統一值 | 原分歧值 → | 位置 | 依據 |
|---|---|---|---|---|
| 健康度中間級 | **50**（`HEALTH_GRADE_B_MIN`） | 60 下修 | tab_stock 標籤(1137) | 50 = 經典榮枯線（PMI 擴張/衰退界），標籤與評語一致 |
| 融資黃線 | **2500**（`MARGIN_BALANCE_WARN_THRESHOLD_YI`） | 2800 下修 | tab_macro SQL 卡片(4289) | 籌碼面提早預警，更早捕捉散戶過度樂觀 |
| 廣度黃線 | **40**（`BREADTH_NEUTRAL_PCT`） | 30 上修 | tab_macro 全市場健康度 KPI(880) | 與 regime 中性線對齊，提供預警緩衝區 |

- 分歧變體常數（`MARGIN_BALANCE_WARN_HIGH_THRESHOLD_YI` / `BREADTH_KPI_YELLOW_PCT` /
  `HEALTH_LABEL_MID_MIN`）已**全數移除**，標籤與評語/regime 從此一致，無語意矛盾。
- `tests/test_ssot_b_class_guard.py::TestDivergenceHarmonized` 守「分歧常數已移除 + 消費端走標準值」。

### §15.4 TNX vs US10Y 刻意不同源（非分歧，設計）

`macro_compass` TNX 紅線 4.5（`TNX_VALUATION_PRESSURE_PCT`）與 `MACRO_THRESHOLDS['US10Y']`
red_above 5.0 **刻意不同**：compass 快訊用較嚴 4.5，US10Y 桶 regime 用 5.0，屬不同用途
（類比 §13.3 負債槓桿 60/65 名稱分離），非分歧旗標。

---

## §16 IA v2 第 1 頁「🚦 今天（能不能出手）」畫面規格（`src/ui/views/page_today.py`，2026-09-07）

> **規格出處**：`docs/wireframes/stock_ia_v1.html` 的 `PAGES[0]`（`id='today'`），客戶 2026-09-05 拍板。
> 落地檔案與分層見 `ARCHITECTURE.md §0.13`；本批過程紀錄見 `STATE.md` 最新一筆。
> **單一職責**（線框 `job` 原文）：**回答「今天能不能出手、出手到幾成」。**
>
> ⚠️ **本頁尚無 production caller**（本批未掛 `app.py`）；舊分頁**不動、不下架**。
> 本節記的是**已落地的畫面契約**，不是「使用者現在看得到的東西」。
>
> ⚠️ 本節**不重述**分層規則（權威在 `CLAUDE.md §8.2`）與五桶門檻值（權威在
> `shared/macro_buckets.py`，本檔 §11 為其一覽）。

### §16.1 兩葉結構

分頁名 / 分區名 / 按鈕名一律讀 L0 `shared/ia_nav.py`，**畫面上不手抄字面值**：

| 葉 | `ia_nav` key | `SECTION_LABELS` 標題 | 內容 |
|---|---|---|---|
| 葉1 | `today.conclusion` | 今日結論 | ① 三張並排判決卡 · ② 操作列 · ③ 三欄摘要 · ④ 今日關鍵橫幅 · ⑤⑥ 今日作戰室＋AI 摘要 |
| 葉2 | `today.detail` | 指標明細（五桶逐段） | 頁首五桶摘要 ＋ 五桶逐段的 16 盞燈明細 |

**（跨頁）頂部狀態列**常駐一條、位在兩葉之上（交易日 / 總經 / Sheet 綁定），
整段復用 `tab_today.build_status_bar_cards()`，本頁**一個字都不重寫**。

**葉1 各區的資料出處**（全部唯讀，零 L1 直呼、零新 fetcher）：

| 區 | 內容 | 出處 |
|---|---|---|
| ① | 建議持股 % / 指標危險度 / 市場位階（**三張並排，見 §16.5**） | L3 `allocation_service.get_allocation` / `get_macro_regime`；危險度吃 L2 算好的 readiness 側車 |
| ② | 操作列：`st.form` 內 **radio 選模式 ＋ 單一 `form_submit_button`** | `_ui_kit.single_submit_form()`；已套用值由 `tab_today.applied_update_mode()` 讀（**widget 當下值與 applied 值分家**） |
| ③ | 三欄摘要（位階 / 動能 / 風險） | `tab_today.build_today_blocks()` 的 `today.summary` block，**零新增取數**；動能與風險**誠實標未接線** |
| ④ | 今日關鍵橫幅 | L2 `compute.macro.daily_key_alerts.collect_key_alerts` |
| ⑤⑥ | 今日作戰室 ＋ AI 摘要（尚未接線） | `tab_today.build_today_blocks()` 的 `today.warroom` block，連「為什麼未接線」的文案都走對面 SSOT |

**葉2 的取數路徑（唯一一條）**：
L3 `services.section_inputs.load_section_inputs(st.session_state)`
→ L2 `compute.macro.macro_helpers.compute_five_bucket_summary(..., readiness_out=rd)`
→ 側車 `rd`（**恆 16 筆，缺席也有紀錄**）→ 門檻與燈號一律走 L0 `shared/macro_buckets.py`。
⚠️ **任何從 `st.session_state` 直抽 `macro_info['vix']` 之類的寫法都是第二條取數路徑**，本頁一處都沒有。

### §16.2 四態模型 —— 一律走 L0 `shared/ui_state.py` 七態，**本頁不自建狀態**

線框畫的四態是 L0 七態的子集；本頁**只 import、不鏡像、不加第八態**：

| 線框態 | `shared/ui_state.py` | 判定來源 |
|---|---|---|
| 灰態（無資料） | `UI_IDLE`（**還沒有人叫過**）／ `UI_EMPTY`（已請求但沒回值） | **兩者不准合併**（`CLAUDE.md §1.A` 第 4 點：未點擊載入＝灰色說明，系統真出錯＝紅色警示） |
| 未接線 | `UI_UNWIRED` | `DangerSpec.wired=False`，理由讀 `spec.unwired_reason`（**不自寫理由**） |
| 已失準 | `UI_DEGRADED` | `DangerSpec.discriminative=False`，理由讀 `spec.degraded_reason` |
| 紅態（真故障） | `UI_FAILED` | 呼叫拋例外 / 來源回錯，畫面保留 `repr(e)` |
| （正常） | `UI_LIVE` | — |

**`requested=` 的三個 gate 旗標來源**（每一個都是「上游自己標的事實」，
**禁止由 `bool(data)` 反推**）：

1. 五桶 / 16 盞燈 / 今日關鍵 ← `upstream_requested(session)`：讀上游 session key 的**存在性**；
2. 市場位階 ← `classify_macro_contract()`：讀契約自己的 `source` 分支標記；
3. 建議持股（卡①）← `contract_attempted()`：沿用第 2 條（`get_allocation()` 的 `is_loaded`
   就是從同一次 `get_macro_state()` 帶下來的）。

⚠️ **狀態頻道與訊號頻道正交**：狀態 glyph（`UI_STATE_META`）與燈號 emoji
（`macro_buckets.LEVEL_EMOJI`）**兩邊都有 `🔴`**，同一張卡若兩個頻道都出 emoji，
使用者無從分辨「VIX 真的很高」與「VIX 抓不到」。故**狀態頻道出 glyph ＋ 中文、
訊號頻道只出中文標籤**，由 `_ui_kit.assert_signal_text_clean()` 在**建構期**先驗一次
（`render_card()` 內那一道保留，作為最後一道防線）。

### §16.3 訊號可信度分母 **恆 16**

- **分母來源**：`len(shared.macro_buckets.BUCKET_DANGER_SPECS)`（量測日 2026-09-07 為 **16**）。
- **`wired=False` 與 `discriminative=False` 刻意不排除出分母** ——
  把未接線的燈藏起來，等於製造一個永遠 100% 的假可信度。
  現況（量測日 2026-09-07）：`foreign_net`（外資現貨淨買賣）`wired=False` 1 盞、
  `margin`（融資餘額）`discriminative=False` 1 盞。
- **參考走勢**（`usdtwd` / `taiex`）住 `REFERENCE_TREND_SPECS`，**不進分母**。
- **畫面字串格式**（線框原文）：
  `訊號可信度 {live}／{total} 個指標正常運作中（無資料 N · 已失準 N · 未接線 N · 故障 N）`，
  由 `Coverage.text()` 產生；`coverage()` **只數已經判好態的卡，不重判態**（重判就是第二把尺）。

### §16.4 葉2 分段：**維持五桶**（**總管解讀 ＋ user 未反對**，非 user 逐字明示）

**線框自身矛盾**：`PAGES[0].leaves` 寫「葉2 指標明細（**五桶逐段**）」，
而 `PAGES[0].blocks` 最後一塊寫「葉2 指標明細 — **七段**（A 市場狀態 / B 長期 / C 中期 /
D 短線 / E 籌碼 / F 全球風險 / G 跨桶裁決）」。**同一份線框的兩處對不上。**

**現行裁定：以五桶為準 —— 這是有效的裁定，照做。**
但依 `CLAUDE.md §-2` 規則 6（承重宣稱要嘛有第二組驗過、要嘛明說來源），
**本項的來源強度必須據實標明，不得寫成「user 明示拍板」**。

**來源鏈（2026-09-07，逐步照實記錄）**

1. 總管以 `AskUserQuestion` 呈報三個選項（**維持五桶** / 補成七段 /
   五桶＋另補 A 與 G 兩段），並附推薦方案「維持五桶」。
2. **user 當時沒有作答。**
3. 總管宣告「暫以推薦案（維持五桶）續行，**此項保持開放**」。
4. 稍後 user 回覆**單一詞「五通」**。
5. 總管**明文宣告自己的解讀**：「理解為『五桶』……若你其實是別的意思，請直接說」，
   並說明會寫入紀錄。
6. user 後續繼續指派下一步工作（「FE-4 好了就複驗提交」），**未提出異議**。

⚠️ **強度定位**：這是「**總管解讀 ＋ user 未反對**」——
**高於**「總管自行決定」（user 確實回覆了，且在被告知解讀後沒有反對），
**低於**「user 明示裁定」（「五通」兩字的意思是總管解讀出來的，不是逐字的規格）。
**若 user 本意不同，此裁定即刻可推翻** —— 屆時本節與落地碼一併改，不需要另找理由。

**支撐這個裁定的技術理由（獨立於上述來源鏈；來源鏈就算作廢，這兩條仍然成立）**：

- 16 盞燈涵蓋的是 B / C / D / E；**A 與 G 沒有對應的燈，F 只被 `us10y` / `dxy` / `vix`
  三盞部分涵蓋** —— 硬套七段會留下三段空殼、假裝有結構，
  正是 §1「**嚴禁用空值冒充**」所禁的那種造假。
- ⭐ **第二個佐證，且獨立於 user**：L0 `ia_nav.SECTION_LABELS['today.detail']`
  **實測就是**「指標明細（五桶逐段）」（`shared/ia_nav.py`，量測日 2026-09-07）——
  **SSOT 本身就站在五桶那一邊**，線框那句「七段」才是與 SSOT 對不上的一方。

**落地**：

- 分段順序走 L0 `BUCKET_ORDER`（`long` / `mid` / `short` / `chips` / `news`），
  段標題與副標走 `BUCKET_META`。
- 差異**就地揭露**，不靠讀者自己發現：常數 `SEGMENT_COVERAGE_NOTE` 在葉2 頁首講明
  「線框寫七段、本葉照 16 盞燈真正的歸屬分五桶」。
- 線框的七段名 `tab_today.DETAIL_SEGMENTS` **未刪**，仍在 L5 契約檔內
  ——「來源鏈被推翻就改回七段」這條路留著，不必先把契約撿回來。

### §16.5 葉1 ①：三張並排判決卡，**危險度與位階不得調和**

- 三張卡＝**建議持股 %** / **指標危險度** / **市場位階**。
- **不平均、不取 worst、不合成第三顆燈**（客戶 2026-08-27 裁示並列揭露）：
  「指標危險度」問的是 16 盞燈有沒有踩到危險門檻（**不含多空方向**）；
  「市場位階」問的是多空（看不到 VIX / PMI / CPI / 融資）。
  實跑比對兩者燈色不一致約四成、方向相反 18 組 —— **併成一顆會毀掉這個資訊**。
  固定說明字串為 `PARALLEL_DISCLOSURE`。
- **三張卡的取數與失敗完全獨立**：危險度（`_load_danger`）與位階（`_load_regime`）
  各自一支 loader，**誰失敗只影響誰那一張卡**。
  ⚠️ 這是 2026-09-07 修掉的缺陷：修前危險度那一半（完全不依賴 regime）會被 regime
  的失敗連坐，並印出「16 盞燈本輪一盞都沒有落在綠 / 黃 / 紅」—— 而那 16 盞燈
  **本輪根本沒被算過**（§1 造假）。
- 兩張卡的字面各走各的 SSOT（危險度：L4 `macro_v2_cards.BAND_META`；位階：L0
  `allocation_decision.REGIME_LABEL`），與 `tab_macro_v2.parallel_verdict()` 內部讀的是同一份。

### §16.6 三個會讓畫面說謊的契約陷阱（實測結論，逐條處置）

| # | 陷阱 | 處置 |
|---|---|---|
| 1 | `get_macro_state()` 只有 9 個 key，**沒有 `as_of` / `timestamp`** | 本頁**不顯示任何「資料時間」欄位**；改以 `AS_OF_NOT_IN_CONTRACT` 一句話講明「契約無此欄位、要顯示得先擴充 L3」。**寧可說沒有，也不編一個時間。** 可顯示的是側車真的有的 `hit_source`（命中來源） |
| 2 | `normalize_regime()` 不認得 `'unknown'`，會洗成 `'neutral'`（把「未評估」偽裝成「震盪」） | 本頁**一次都沒有** import 或呼叫 `normalize_regime`；位階一律用 `get_macro_regime()` 回來的原值，不做二次正規化 |
| 3 | 危險度燈與位階燈實測不一致 | 見 §16.5：**並列揭露，不合成第三顆** |

### §16.7 已知未解（**不得當成已完成**）

1. **module-level import 失敗仍會整頁空白** —— 本批只把檔頭宣稱改成誠實
   （明列擋得住什麼、擋不住什麼），**沒有修好**。根因是 `src/ui/tabs/__init__.py`
   的 eager barrel，不在本批檔案邊界內，**另案**。
2. **`_ui_kit.render_cards()` 路徑無渲染邊界**（頂部狀態列 / 葉1 ③ / ⑤⑥）；
   殘餘風險經分析為低，但**未實測窮舉**。
3. **`tests/test_p01_today_view.py` 自陳「是護欄不是證明」** ——
   釘住的是已知那幾種說謊方式不會回來，不是「這一頁不會再說謊」。
4. **本頁無 production caller**，實機僅以 Streamlit AppTest 冒煙驗過；
   沙箱 streamlit 實測 **1.63.0**（量測日 2026-09-07），而 `requirements.txt` 宣告
   `streamlit>=1.56.0,<1.60.0` —— **cap 之內的版本本批未驗**。

---

## §17 IA v2 第 2 頁「🔍 找標的」畫面規格（`src/ui/views/page_find.py`，2026-09-07）

> **規格出處**：`docs/wireframes/stock_ia_v1.html` 的 `PAGES[1]`（`id='find'`），客戶 2026-09-05 拍板、
> 2026-09-07 明示動工。落地檔案與分層見 `ARCHITECTURE.md §0.13`；過程紀錄見 `STATE.md` 最新一筆。
> **單一職責**（線框 `job` 原文）：**從全市場縮到一張候選清單。**
>
> ✅ **本頁已掛上 `app.py`**（第 2 個頁籤，PR #664）；**舊分頁不動、不下架**（雙軌並存，客戶定版）。
>
> ⚠️ 本節**不重述**分層規則（權威在 `CLAUDE.md §8.2`）與選股門檻（權威在 L3
> `services/fundamental_screener_service.py` 與 `shared/*`）。

### §17.1 兩葉結構與各區出處

⚠️ **葉名是本檔就地定義的常數，不是讀 L0** —— `shared/ia_nav.py` 目前**沒有**
`LEAF_FIND_*` 與本頁的 `ACTION_*` 登錄（實測 2026-09-07：`SECTION_LABELS` 只有
`today.*` 兩筆）。**這是已知缺口**，見 §17.5；L0 補上之後本檔應改為讀它。

| 葉 | 葉名常數 | 內容 |
|---|---|---|
| 葉1 | `LEAF_SCREEN_TITLE`＝「選股網」 | 條件表單（`st.form`）＋ 選股結果卡 ＋ CSV |
| 葉2 | `LEAF_MAP_TITLE`＝「板塊地圖（＝產業熱力圖＋板塊資金潮汐）」 | 熱力圖（**未接線**）＋ 三大法人資金泡泡圖 ＋ **常駐口徑揭露** |

| 區 | 內容 | 出處 |
|---|---|---|
| 葉1 條件表單 | ① 基本面優選（自動四項全過）· ② 勾因子（估值／EPS／缺貨／抗跌 RS／跨季轉強）· ③ 排序與筆數 | 本檔 `_render_screen_form()`；因子標籤走 L3 `load_factor_labels()` |
| 葉1 選股結果 | 存活池 → 綜合入選；本次因子命中數 | L3 `fundamental_screener_service.get_ranked_picks` / `get_fundamental_survivors` / `build_trend_map`、L3 `shortage_screener_service.run_shortage_scan`、L3 `rs_leader_service.run_rs_leader_scan`、L3 `allocation_service.get_macro_regime`（空頭濾網）；因子命中片語走 L5 純函式 `tab_stock_picker.summarize_factor_hits()` |
| 葉2 熱力圖 | 產業漲跌熱力圖 | **未接線**（見 §17.3） |
| 葉2 泡泡圖 | 三大法人資金流向泡泡圖 | L3 `sector_flow_service.get_sector_flow_view` → L4 `ui.render.sector_flow_render.build_sector_flow_figure`（純繪圖） |
| 葉2 口徑揭露 | 三軸口徑 caption | **常駐，不隨狀態消失**；視窗長度（X／Y／泡泡）一律讀 L0 常數 `WINDOW_X` / `WINDOW_Y_RECENT` / `WINDOW_Y_PRIOR` / `WINDOW_SIZE` / `WINDOW_Y_MIN_DAYS`，**畫面上不寫死 5／5／20** |

**排名邏輯不在本頁**：一律走 L3 `get_ranked_picks()`——那是「畫面 / 每月凍結 / MCP / 推播」
四處的**同源入口**（該函式 docstring 明文）。本檔**不自己排序、不自己算百分位、
不自己決定哪些檔進榜**。

### §17.2 四態對映 —— 一律走 L0 `shared/ui_state.py`，**本頁不自建狀態**

| 線框態 | `shared/ui_state.py` | 判定來源 |
|---|---|---|
| 灰態（還沒選） | `UI_IDLE` | gate 旗標為 False（見下） |
| 灰態（選了、跑完、**0 檔**） | `UI_EMPTY` | **這是一個有效的結果**，不是故障、也不是還沒跑 |
| 未接線 | `UI_UNWIRED` | `wired=False`（第 1 條規則先判，**與請求與否無關**） |
| 紅態（真故障） | `UI_FAILED` | 呼叫拋例外／來源回錯，畫面保留 `repr(e)` |
| （正常） | `UI_LIVE` | — |

**`requested=` 的三個 gate（一個都不是從資料反推）**：

1. **選股結果** ← `SS_APPLIED_SCREEN in session_state`（`"_p02_applied_screen"`）。
   那個 key **只有** `_render_screen_form()` 的 submit 分支會寫。
   ⚠️ **不是** `bool(cands_df)`、**不是** `not df.empty`、**不是** `len(rows) > 0` ——
   那三種都分不出「還沒選」與「選了但 0 檔」。
2. **板塊地圖** ← `session_state[SS_MAP_REQUESTED]`（`"_p02_map_requested"`），
   只有「🗺️ 載入板塊地圖」那顆 `st.button` 的分支會寫。
3. **未接線的兩項** ← 同上兩個旗標；`wired=False` 讓 `classify_ui_state` 先判 `unwired`
   ——**未接線永遠不會因為多按一次而改變**。

⚠️ **`requested=False` 時本頁一行 L3 都不呼叫。**

### §17.3 未接線兩項與「去哪補」（誠實揭露，不是漏寫）

1. ⛔ **產業熱力圖**（線框葉2 左半）。
   **卡在哪**：唯一的 public 入口是 L4 `ui.render.etf_render.render_sector_heatmap()`，
   它**自帶 5 個寫死的 widget key**（`heatmap_market` / `heatmap_period` / `heatmap_refresh` /
   `heatmap_load` / `heatmap_loaded`）與**自己那顆 gate 按鈕** → 在本頁再呼叫一次會與既有
   🏦 ETF 分頁**撞 `DuplicateWidgetID`**，且畫面會出現**兩顆**載入鈕（線框 N6 明文要求
   舊 gate 被本頁的「🗺️ 載入板塊地圖」**吸收**）。類股代表清單與 treemap 組裝**都是 L4 私有符號**，
   跨檔直取＝ `CLAUDE.md §8.2.A.2` **V-PICKER-PRIV-1** 的前車之鑑；自己抄一份類股表則是第二個 SSOT（§2.1）。
2. ⛔ **估值（本益比）因子與「名稱」欄**。`get_ranked_picks(pe_map=, name_map=)` 的 SSOT 是
   **L1** `src/data/stock/yield_pe_fetcher.fetch_pe_name_maps`，**全 repo 沒有 L3 wrapper**。
   L5 直呼 L1 是 R4 違憲；經 `src/ui/tabs/yield_screener.py` 的 re-export 繞道
   **只是騙過 AST、不改性質**。

**⭐ 本頁特有判準：勾了「估值」不靜默降級。** 使用者勾了估值因子時，本頁在**卡上與表單下方
都**寫明「這個因子在本頁沒有資料、**不計入綜合分**」。理由是 L2 `composite_rank_candidates`
的 note **只**揭露缺貨／RS 兩個因子，**pe 缺料不會出現在它的 note 裡** ——
那正是本頁必須自己講的原因。**靜默降級＝讓使用者以為他勾的條件生效了。**

### §17.4 該頁特有的三個判準

1. **`st.download_button`（CSV）與 `st.button`（🗺️ 載入板塊地圖）一律在 `st.form` 外。**
   線框 F11：form 內放 `st.button` 實跑即拋 `StreamlitAPIException`（不是風格問題，是會炸）。
2. **空結果不得冒充綠燈，反方向也擋。** 本檔**沒有任何一處**把「0 檔」寫成 live
   （`Card.__post_init__` 也擋著：非 live 不准帶結論文字）；把「還沒選」畫成紅色錯誤則是
   捏造一個不存在的故障（`CLAUDE.md §1.A` 第 4 點）。
3. **口徑揭露常駐。** 「X＝近 N 日累計淨流入／Y＝動能變化／泡泡＝近 M 日淨額規模、
   **面積不等於權重**」不隨狀態消失 —— 使用者看圖之前就該知道這張圖在量什麼；
   交易日不足的板塊**不硬塞象限位置**，另行列名。

### §17.5 已知未解（**不得當成已完成**）

1. **`live` 態只在沙箱用替身驗過**（無外網、FinMind SDK 未安裝）；**真實部署未實測**。
2. **`shared/ia_nav.py` 缺本頁的 `ACTION_*` / `LEAF_*` 登錄** → 葉名與按鈕字串就地定義，
   **跨頁 SSOT 仍缺**（頁 2~5 同一項）。
3. **`_ui_kit.single_submit_form()` 只吃一組 `st.radio`** → 本頁就地實作 `_render_screen_form()`，
   **未改共用層**（頁 3 同病，兩支會漂移）。
4. **頁籤字串在 `app.py` 硬編碼**，而 `ia_nav.PAGE_LABELS[PAGE_FIND]` 已是 SSOT ——
   **兩份不一致不會 CI 紅燈**。
5. **線框 N6 的改名風險未處理**：線框畫的「🗺️ 載入板塊地圖」**是新名字**，production 現行
   是「🗺️ 載入產業熱力圖」；熱力圖未接線期間，**任何指去舊名字的文案都還沒有跟著改**。

---

## §18 IA v2 第 3 頁「🔬 查一檔」畫面規格（`src/ui/views/page_inspect.py`，2026-09-07）

> **規格出處**：`docs/wireframes/stock_ia_v1.html` 的 `PAGES[2]`（`id='inspect'`）。
> 落地檔案與分層見 `ARCHITECTURE.md §0.13`；過程紀錄見 `STATE.md` 最新一筆。
> **單一職責**（線框 `job` 原文）：**一個代碼進去，一份判決出來 —— 系統判型，
> 然後走兩套完全不同的明細。**
>
> ✅ **本頁已掛上 `app.py`**（第 3 個頁籤）。⚠️ **「🔬 查一檔」與既有「🔬 選股」emoji 相同、
> 名稱不同 —— 兩個都保留，是雙軌並存期的刻意並存，不是漏改。** 新頁是「一個代碼進去，
> 一份判決出來」；舊群組是「篩一批出來」。**不得合併、也不得為了看起來不重複而改名**
> （改名會動到既有頁籤，違反客戶定版）。

### §18.1 兩葉結構與各區出處

| 葉 | 葉名常數 | 內容 |
|---|---|---|
| 葉1 | `LEAF_SINGLE_TITLE`＝「單檔診斷（個股／ETF/unknown 三分支）」 | 輸入表單＋判型 → **三條分支** → 判決卡 ＋ 明細 |
| 葉2 | `LEAF_BATCH_TITLE`＝「多檔比較（可混貼）」 | 批次表單 → 批次評分表 → 下鑽 |

| 區（對應線框 7 個 block） | 落點 | 出處 |
|---|---|---|
| 輸入表單 ＋ 判型結果 | `_render_ticker_form()` ＋ `build_kind_card()` | L2 純函式 `compute.etf.asset_lag.classify_asset_kind` / `pick_benchmark`（零 I/O） |
| 葉1-A 個股判決卡（3 欄） | 健康度／估值／籌碼 | 健康度：L3 `dividend_station_service.fetch_metrics(t, 'stock')`；**估值與籌碼未接線**（§18.3） |
| 葉1-A 個股明細（七段） | `build_detail_card()` | **未接線**，七段名逐一列出（§18.3） |
| 葉1-A 💰 獲利能力診斷 | `build_profit_cards()`，線框 `st.columns(5)` → **3 欄 × 2 排** | L3 `stock_grp_service.get_financial_statements` → L3 `financial_health_engine.analyze_financial_health` 的 `profitability_module`；門檻住 L0 `shared/financial_health_thresholds.py`，**本頁只讀 Status 字串** |
| 葉1-B ETF 判決卡 ＋ 明細 | 折溢價／配息／追蹤・同儕 ＋ 明細卡 | L3 `fetch_metrics(t, 'etf')`；**ETF 明細七段未接線** |
| 葉1-C unknown | `build_unknown_card()` | 見 §18.4（**本頁最重要的判準**） |
| 葉2 多檔比較 | `_render_batch_form()` ＋ `build_batch_card()` | 同上 L3；**下鑽零額外 L3 呼叫**（讀已算完的那一份） |

**取數唯一規則是「一律走 L3」**（判型例外走 L2 純函式）。
⚠️ **判型的 L2 late import 是刻意的、不是懶惰**：實測（量測日 2026-09-07）
`import src.compute.etf.asset_lag` 會連帶拉進 **pandas / requests / yfinance / streamlit
＋ 33 個 `src.*` 模組**（含 `src.data.core.data_loader`）——
放在 module level 會讓「打開這一頁」的故障半徑等於整條資料層。

### §18.2 四態對映 —— **四種「沒有結果」絕不可混**

```
還沒輸入代碼         → UI_IDLE    （灰。還沒有人叫過）
輸入了、查無此代碼   → UI_EMPTY   （灰。這是一個有效的結果）
判不出是個股還是 ETF → UI_EMPTY + MISS_NOT_APPLICABLE （灰。見 §18.4）
上游掛了             → UI_FAILED  （紅。唯一准用紅色的狀態）
```

**`requested=` 的兩個 gate**：葉1 全部區塊 ← `SS_APPLIED_TICKER`（`"_p03_applied_ticker"`）；
葉2 批次表 ← `SS_APPLIED_BATCH`。兩個 key **各自只有對應 form 的 submit 分支會寫**。

⚠️ **下游 gate 多帶一個條件：「判型判成這一支才算有人叫過它」。**
使用者輸入 `00878` 時，**沒有任何人要求過個股財報** —— 個股那三格的正確狀態是
**`idle` 不是 `empty`**。

⚠️ **本頁沒有任何一格會判 `UI_DEGRADED`**，這是刻意的：上游沒有回傳任何「門檻已失準」的
訊號，硬湊一個等於捏造一種使用者無從查證的狀態。線框葉1-A 的 `degradedCells`
（「趨勢因子無 MA，不計入」）描述的是**接線後**的樣子 —— 那一格（K 線＋均線）在本頁是
`unwired`，**沒有 MA 可以「不計入」**。

### §18.3 未接線四項與「去哪補」

1. ⛔ **個股「估值（357 評價）」**。357 位階要**近 N 年平均年現金股利（元／股）**與有配息年數；
   全 repo 沒有任何 L3 介面回傳**個股**配息歷史。`etf_grp_compare_service.get_etf_dividends()`
   是 ETF 用的 pass-through，**拿它去餵個股＝替上游宣稱一件它沒說的事**；
   L1 `etf_fetch.fetch_etf_dividends` 直呼是 R4 違憲，經其他 L5 檔 re-export 繞道
   **只是騙過 AST、不改性質**（測試以 AST 釘死此拒絕）。
2. ⛔ **個股「籌碼」**。`shared.macro_compute.analyze_20d_chips_from_df()` 是 L0 純函式
   （吃 df、免 I/O），但那份**同時要有 `主力合計` 與 `volume`** 的 df 只有 L1
   `StockDataLoader.get_combined_data()` 產得出來，而它**沒有 L3 介面**。
3. ⛔ **葉1-A 明細其餘七段**（K 線＋均線／357 河流圖／財報領先指標／VCP・布林／月營收／
   什麼時候買賣／心理檢查）。**只有 💰 獲利能力診斷這一段接上了。** 其餘七段的現行實作是
   `src/ui/tabs/stock_sections/section_*.py`，每一支都直接 import L1 並自帶 widget key，
   在本頁再掛一次會撞 `DuplicateWidgetID`。
4. ⛔ **葉1-B ETF 明細七段**（淨值 vs 市價／折溢價帶／配息紀錄與以息養股／成分股與集中度／
   同儕 7 維／標準差買賣帶／破發檢查）。同 3。

⚠️ **線框對葉1-B 的紅隊註記**：「與個股分支**重疊近零**（13 個個股概念在 ETF 頁 0 命中、
6 個 ETF 概念在個股頁 0 命中）—— **合併的是入口與骨架，不是內容**。」
本頁照這句寫：骨架（form／判型／3 欄判決卡／單欄堆疊明細）兩支共用，
**每一張卡的 label 與 facts 全部換掉，沒有一個欄位是兩邊共用的**。

### §18.4 ⭐ **unknown 是灰態，不是紅態**（本頁最容易寫錯、而且錯了最像對的地方）

線框葉1-C 的 `n` 欄原文就是「**第三條路 · 不是紅態**」。落地為
**`UI_EMPTY` + `MISS_NOT_APPLICABLE`（灰）**：

- **不是 `failed`** —— 判型本身是好的，只是誠實說判不出來。`classify_asset_kind` 對
  美股／指數／興櫃／打錯的代碼一律回 `unknown`，那是**這個輸入不在本站的射程內**，
  不是「本站壞了」。
- **不是 `unwired`** —— 它接了，而且正常運作。
- **不是 `idle`** —— 使用者確實叫過了。

**文案**（線框原文落地）：「**無法判定這是個股還是 ETF** —— 已停在這裡，沒有替你猜」／
「非台股代號…依 §4.6 不猜，**這不是故障，重按一百次也是同一個答案**」／
「確認代碼；或在表單把判型改成強制個股／ETF」。

⭐ **並且釘住：`is_resolved` 不得寫成 `bool(kind)`。**
`unknown` 是一個**非空字串**（L2 的 `ASSET_UNKNOWN`），拿它當「有值」會把
**「判不出來」畫成綠燈** —— 那正是線框葉1-C 要防的「把 unknown 塞進另外兩態」。
落地為 `is_resolved = self.is_stock or self.is_etf`，守衛
`tests/test_p03_inspect_view.py::TestThreeBranchesOfClassification`。

**判型可手動覆寫（線框 F4，不是裝飾）**：理由是 repo 已記錄的同型事故 ——
`station_cards.py` 記著「型別大小寫打錯一個字母 → **可信度虛高到 100% 並打開巡航 gate**」。
故表單有一個「判型」下拉（自動／個股／ETF），判決卡的 facts **永遠**顯示
「系統判的是什麼」與「這一輪實際用的是什麼」兩列，覆寫時兩列會不同。

### §18.5 已知未解（**不得當成已完成**）

1. **線框那 14 段明細，本頁一段都沒畫**（§18.3 的 4 項）。
2. **期間與 6 個 MA 是「記錄了但沒人用」** —— K 線未接線；已在常駐 caption 明講
   「調了不會有效」，但這仍是一組目前無下游的控制項。
3. **`fetch_metrics` 的個股／ETF 不對稱未抹平**：ETF 拿不到日線 → L3 raise → 三格同時紅；
   個股是 best-effort → 灰。**照實透傳**（抹平＝替其中一邊宣稱它沒說的話），
   但與線框 `errCells` 畫的「折溢價🔴／配息🟢」形狀不同，要等 L3 把三腿拆開才做得到。
4. **未在真部署驗過**：沙箱無外網，`live` 路徑用假 L3 注入驗。真實 FinMind／yfinance
   回來的欄位形狀（尤其 `mj_grade` 字面、`etf_quality["stars"]` 型別）**沒有實測過**。
5. **`_cell()` 缺值判定依 `_no_ai_profitability` 原始碼推得，未窮舉 L3 所有可能的 Status 字面**；
   對面新增詞彙時本頁會畫成「有數字、無結論標籤」（已為此加測試），不會變紅也不會冒充綠。
6. **冷啟動預覽用個股欄位**（未判型前顯示個股三格 idle）是實作組的判斷，**非線框明文指定**。
7. **MA 5 與 100 在 L0 無 SSOT**（`config.py` 只有 20／60／120／240），寫成具名常數並就地標明，
   **沒有假裝它們有出處**。
8. **批次每次 rerun 會重跑 L3**（同頁 2 既有模式，靠 L1 內部 cache）。
9. **`_ui_kit.single_submit_form()` 只吃 radio** → 本頁就地實作兩支表單，未改共用層。
10. **`shared/ia_nav.py` 缺本頁 `ACTION_*` / `LEAF_*`**；**頁籤字串在 `app.py` 硬編碼**。
11. **測試是護欄不是證明。**

---

## §19 IA v2 第 4 頁「💼 我的持股」畫面規格（`src/ui/views/page_hold.py`，2026-09-07）

> **規格出處**：`docs/wireframes/stock_ia_v1.html` 的 `PAGES[3]`（`id='hold'`）。
> 落地檔案與分層見 `ARCHITECTURE.md §0.13`；過程紀錄見 `STATE.md` 最新一筆。
> **單一職責**（線框 `job` 原文）：**我已經持有的，該加、該換、該減。**
>
> ✅ **本頁已掛上 `app.py`**（第 4 個頁籤）。⚠️ **「💼 我的持股」（新，第 4）與既有
> 「💼 我的持股戰情室」（舊，第 10）emoji 相同、名稱高度相似 —— 兩個都保留，
> 是雙軌並存期的刻意並存，不是漏改。** 新頁是 IA v2 的**殼**；舊頁是**既有實作**
> （`etf_tab_dividend_station.py`，線上已在跑的完整功能）。**不得合併、不得改名。**
>
> ⚠️ **這是五頁裡唯一碰使用者資產（Google Sheets 持股帳本）的頁。**

### §19.0 ⭐ 唯讀四道保證（**不是宣告，是機械擋**）

本頁多一條前三頁沒有的鐵律：**一律唯讀。不寫入、不刪除、不改動任何一列持股。**
落實方式四道，**缺一道就只剩自律**：

| # | 保證 | 落地方式 |
|---|---|---|
| 1 | **AST 白名單** | 本頁可以呼叫的 L3 符號是一張白名單，**名單外的 `from src.services… import` 即 CI 紅燈**。全部都以 `get_` / `fetch_` 開頭且在各自 docstring 自陳唯讀 |
| 2 | **AST 黑名單** | `save_portfolio` / `delete_portfolio` / `save_stock_watchlist` / `add_to_stock_watchlist` / `create_new_sheet` / `rename_sheet` / `append_forward_test_picks` / `register_cap` / `apply_vix_veto`…**一個識別字都不准出現**（實碼零命中；docstring 內的提及不算） |
| 3 | **憑證結構性隔離** | `BindingReadout` **沒有 `sheet_id` 欄位**（測試斷言），`load_binding()` 實碼裡連這個字都不出現 —— **讀了就有機會漏出去**。畫面只回答「有沒有綁」這個布林 |
| 4 | **寫入型功能一律 `unwired`** | 且 `why` 用 `READONLY_WHY`（「本質是寫入，本頁不做」）而**不是** `HOLDINGS_WHY`（「缺 L3」）。測試釘住兩者不得混 —— 混了等於**騙人說「補一支 L3 就會有」** |

守衛：`tests/test_p04_hold_view.py::TestReadOnly` ＋ `::TestHoldingsServiceIsReadOnly`。

⚠️ **一個已揭露的例外**（「唯讀」這種全稱句不該有沒講出來的例外，`CLAUDE.md §-2` 規則 6）：
`allocation_service.get_allocation()` 會寫 `st.session_state` 的**兩個記憶化快取鍵**。
那是 session 內的計算快取，**不碰 Google Sheets、不碰任何使用者資產**，且寫入發生在 L3 內部。

### §19.1 兩葉結構與各區出處

| 葉 | 葉名常數 | 內容 |
|---|---|---|
| 葉1 | `LEAF_WARROOM_TITLE`＝「戰情室（1️⃣~6️⃣ ＋ 80/20 配置偏離）」 | ①~⑦ |
| 葉2 | `LEAF_SETUP_TITLE`＝「組合設定（＝組合管理＋Sheet 綁定）」 | 表單（唯一的 `st.form`）＋ 綁定兩張卡 ＋ 持股列預覽 ＋ 未接線兩項 |

| 區 | 內容 | 出處 |
|---|---|---|
| ① 結論三張卡 | 該做什麼／訊號可信度／需要處理 | L3 `dividend_station_service.build_station_digest` ＋ `compute_portfolio_totals`；可信度分母走 L4 `station_cards.aggregate_judged` / `tally_states`（**與既有戰情室同一把尺**） |
| ② 同一個名詞，兩套刻度 | **常駐揭露、非摺疊** | L0 `shared/station_specs.py`（純常數，零 I/O） |
| ③ 戰情表（燈牆 ＋ VIX） | 235 加碼燈 / 3-3-3 / 健檢四盞 | L3 `get_station_rows` / `fetch_vix`；燈牆渲染走 L4 `station_cards.render_light_wall` / `render_legend` |
| ④ 換股建議 | 換出（體質轉弱）→ 換入（來自觀察清單）＋ 已套用總經位階 | L3 `get_switch_in_candidates` ＋ `build_switch_advice` ＋ `get_station_macro` |
| ⑤ 80/20 配置偏離 ＋ 衛星停利 | 核心／衛星偏離、停利觸發 | L3 `build_station_digest`（內含 `compute_allocation_split` ＋ `flag_take_profit`）；目標與門檻讀 L0 `shared/dividend_station_thresholds.py`，**本頁不寫死任何一個數字** |
| ⑥ 組合深度分析 | 再平衡・核心／衛星・壓力測試・VaR・配息現金流・葡萄串領息（**3 欄 × 2 排，不是 `columns(6)`**） | 僅「核心／衛星」接線，其餘五項未接線（§19.3） |
| ⑦ AI 戰情總結 | 唯一推播出口 | **未接線**（§19.3） |
| 葉2 | 表單／綁定／持股列預覽／Sheet 選擇／觀察清單管理 | L3 `portfolio_binding_service.get_binding_state`；**持股清單走本批新增的 L3 `holdings_service.get_holdings`** |

**建議持股水位一律走 L3 `allocation_service.get_allocation()` 動態取**
（守衛 `TestNoHardcodedPositionPct`：畫面上不得寫死任何一個 % 數字）。

### §19.2 四態對映 —— ⭐ **三種「沒有持股」絕不可混**

```
還沒按 🚀（或選了「只讀市場端」）        → UI_IDLE    灰。還沒有人叫過。
讀了，發現你還沒綁 Sheet                → UI_EMPTY   灰。有效結果，不是故障。
讀了，綁到了，但那本 Sheet 一本組合都沒有 → UI_EMPTY   灰。與上一條**不是同一件事**。
讀了，Google 那端掛了                   → UI_FAILED  紅。唯一准用紅色的狀態。
```

⭐ **「空的組合」是有效結果，不是故障。** 一個剛註冊、還沒填任何一列的使用者，
看到的應該是「你的 Sheet 綁好了，只是還沒有內容」，**不是一片紅色的錯誤**。
把它畫成紅色＝ v3 §02 前半句要杜絕的「假性錯誤滿版」，而且會讓**真的**壞掉那一次沒有人看得見。

⚠️ **這裡有意識地偏離線框**：線框葉2 的 `err` 把「已綁定但讀不到任何持股列」整塊畫成 🔴
並把「可能是空表」列為原因；**本實作把空表拆出來走灰**，只有真讀不到走紅。

⭐ **「還沒綁」與「綁了但空」也不可混** —— 前者要你去綁，後者要你去填，**指路句完全不同**。
結構性解法：**拆成兩張卡**（`build_binding_card` 判「有沒有綁」、`build_portfolio_count_card`
判「綁到的那本裡有幾本組合」），**沒有任何一格需要同時代表兩件事**。沒綁時第二張卡是 `idle`
—— 這與 L3 契約對齊：`BindingState.portfolio_count=None` 的註解寫著「未知；**不腦補 0**」。

**`requested=` 的兩個 gate ＋ 一個「不需要 gate」**：

1. **戰情室全部區塊 ＋ 葉2 持股列預覽** ← `SS_APPLIED_HOLD in session_state`
   （`"_p04_applied_hold"`，只有 `_ui_kit.single_submit_form()` 的 submit 分支會寫）。
2. **綁定狀態那兩張卡** ← 上面那個 gate **並且**使用者這一輪選了「連 Google Sheet 綁定狀態
   一起讀」。**選「只讀市場端」時本頁真的不會發那一次網路呼叫。**
3. **② 兩套刻度是常駐的**，輸入是 L0 的 `@dataclass(frozen=True)` 常數表、**零取數**，
   故傳**字面 `True`** —— 那是**陳述**「這個揭露永遠開著」，不是恆真式。
   （恆真式的問題不在於它恆真，而在於它**假裝自己在判斷**。）

⚠️ **本頁唯一會判 `UI_DEGRADED` 的是 ② 兩套刻度，而且不是硬湊的**：它直接讀 L0
`station_specs` 的 `discriminative` 旗標。實測（量測日 2026-09-07）`KEY_STOCK_TREND`
（財報趨勢）標了 `discriminative=False`，而那盞燈正是本頁個股「健檢」欄的輸入之一 ——
**所以本頁這一側的刻度確實有一個已失準的輸入**。旗標若被改回 `True`，這張卡會**自己**變回 live。

### §19.3 未接線八項與「去哪補」（**四類，不共用同一句**）

**(a) 缺 L3 wrapper**（純函式在 L2 `compute.etf.etf_calc`，`src/services/` 連 wrapper 都沒有）：
**再平衡 · 壓力測試 · VaR**。本頁一律走 L3，**不會為了畫一格就直呼 L2**。

**(b) 單位不同 ＋ 要新增畫面元件**：**配息現金流**。L3 `dividend_tax_service.get_dividend_tax_view()`
在，但它吃**股數**，而持股帳本記的是**張**。那個「1 張＝1000 股」的換算**不可以寫在本頁** ——
L3 `compute_portfolio_totals()` 已點名（留在畫面層等於讓同一個乘法散在 UI 各處，
`CLAUDE.md §4.1` 漏乘＝**1000 倍低估**）。它還要一個「綜所稅邊際稅率」輸入，
**新增畫面元件要先出線框草稿給客戶拍板**（`CLAUDE.md §-1.5` A-8）。

**(c) 實作在 L5 且寫死 widget key**：**葡萄串領息**（`tabs.grape_ladder`）——
在本頁再掛一次會撞 `DuplicateWidgetID`，那不是「畫得醜」，是**整頁當場拋例外**。

**(d) 不是缺 L3，是缺授權**（本質是寫入，本頁一律唯讀）：**Sheet 選擇 · 觀察清單管理**。

**⑦ AI 戰情總結**另成一類：四支 L3 都在、digest 也真的算得出來，**卡住的是畫面** ——
線框在這一區畫了一顆單獨的 `st.button`［⚡ 生成 AI 總結］，而新增視覺元件要先出草稿拍板。
⚠️ **不會用「自動生成」繞過那顆鈕** —— 每次 rerun 都打一次付費 AI，比少一顆鈕嚴重得多。
**這是刻意偏離線框，請客戶覆核是否接受。**

### §19.4 ⭐ ④ 換入候選**必須**帶 `exclude=已持有代號`

`get_switch_in_candidates()` 需要 `exclude=`。**少了它，L3 會從全市場挑，
於是畫面會叫使用者買他已經持有的股票** —— 那不是「降級的建議」，是**錯的建議**。
故在持股清單接上之前，④ **刻意整塊不出，一半都不出**；接上之後才解禁並傳入 `exclude`。

配套：L3 `holdings_service` **會去重** —— 同一檔同時出現在 Portfolio（held）與 Watchlist（觀察）時
**只留 held 那一列**，比對走 L0 `normalize_ticker()`（去 `.TW` / `.TWO` 再比），
否則 `2330` 與 `2330.TW` 會被當兩檔、`exclude` 就會漏掉一個。

**`holdings_service` 的 §1 Fail Loud 切法**（兩半不同待遇，理由不是潔癖）：

- **投資組合（真正持有的部位）讀取失敗 → `raise`。** 80/20 偏離、未實現損益、停利判定的
  **分母都是整份清單**，少一半算出來的百分比**看起來完全正常、實際上是錯的**。
- **觀察清單（還沒買的候選）讀取失敗 → 不 raise，記在 `watchlist_error`。**
  它不進任何金額計算，只影響「換入優先從觀察清單挑」；為它把整頁變紅＝把「一格壞」放大成
  「整頁壞」。⚠️ **但不可被靜默吞掉** —— 呼叫端拿得到 `watchlist_error`，**必須顯示**。
- **沒有綁 Sheet ≠ 失敗** → 回 `bound=False` ＋ 空清單，由呼叫端畫成灰的「你還沒綁」。

⚠️ **顯式傳 `sheet_id=`**（踩過的坑）：L1 四支讀取函式都是 `@st.cache_data(ttl=TTL_15MIN)`，
`sheet_id` 是**參數＝快取鍵的一部分**。傳 `None` 時鍵**恆為空** →
**換一本 Sheet 之後 15 分鐘內會拿到上一本的資料（張冠李戴）**。

### §19.5 實作期抓到並修掉的兩個真 bug（寫下來防重犯）

1. **`count_gate`**：整支 L3 拋例外時，第二張卡若拿到 `requested=False` ＋ `error`，
   L0 會當場 `ValueError` → **一張該畫的紅卡變成整頁未捕捉例外**。
   已改 `count_gate = count_requested or (requested and error)` ＋ 回歸測試。
2. **渲染順序**：表單在葉2、gate 被葉1 消費，而 `st.tabs` 兩葉**同輪都跑** →
   葉1 先跑會讀到寫入**前**的 session，按了鈕戰情室仍顯示「尚未執行」且不會自動 rerun。
   已改為「先把表單畫進葉2 容器 → 再畫葉1 → 回葉2 畫下半」，AST 測試釘住此順序
   （`TestFormRunsBeforeItsConsumers`），AppTest 實跑驗證 submit 後「尚未執行」確實消失。

### §19.6 已知未解（**不得當成已完成**）

1. ⭐ **`live` 態沒有實機驗過** —— 沙箱無 Google 憑證、proxy 對 Yahoo 回 403。
   實跑到的只有 idle／empty／failed／unwired／degraded；「真的綁到一本 Sheet」
   「真的拿到 VIX 數字」「真的拿到總經位階」三種 `live` 畫面**未實測**。
2. ⭐ **送出後每次 rerun 會重跑整段編排** —— 本頁**不得**存 session（測試禁止），
   網路層由 L1 `@st.cache_data` 擋住，**逐檔純運算會重算**。既有 🏦 ETF ›存股戰情室 是靠
   自己存 session 避開的。**這是已知代價，不是沒想到；沙箱量不到實際延遲。**
3. **唯讀保證只證到本檔的靜態文字** —— AST 白／黑名單證明「本檔沒有任何一條通往寫入面的路」，
   **不能**證明那幾支 L3 執行時絕不寫東西。讀過其 docstring 自陳「純讀不寫」，
   但**沒有逐行追進 L1 驗證**。
4. **「`src/services/` 原本沒有任何一支回傳持股清單」是單組窮舉**（AUD-5 稽核組），
   **未經第二組複驗**。`holdings_service` 的存在**不依賴它成立**。
5. **「單一持股」邊界跑不到**（跑的是最接近的 `portfolio_count == 1`）。
6. **② 判 degraded 的推導鏈是單組讀碼得到的**（`KEY_STOCK_TREND.discriminative=False`
   是實測，但「它影響本頁健檢欄」那條鏈**未經第二組複驗**）。旗標翻面時卡會自己變回 live，
   故錯了也不會寫死一個假 degraded。
7. **`st.tabs` 容器重複進入只在 AppTest 驗過，未在真瀏覽器驗。**
8. **「兩套刻度」的兩句 prose 在本頁與頁 5 各有一份**（漂移風險；正解是 L0
   `station_specs` 補 `scale_shape` 欄位）。
9. **`shared/ia_nav.py` 缺本頁 `ACTION_*` / `LEAF_*`**；**頁籤字串在 `app.py` 硬編碼**。

---

## §20 IA v2 第 5 頁「📖 憑什麼」畫面規格（`src/ui/views/page_why.py`，2026-09-07）

> **規格出處**：`docs/wireframes/stock_ia_v1.html` 的 `PAGES[4]`（`id='why'`）。
> 落地檔案與分層見 `ARCHITECTURE.md §0.13`；過程紀錄見 `STATE.md` 最新一筆。
> **單一職責**（線框 `job` 原文）：**解釋數字怎麼來、資料新不新鮮、以及直接問。**
>
> ✅ **本頁已掛上 `app.py`**（第 5 個頁籤）。⚠️ **本頁與三個既有頁籤功能重疊，
> 全部刻意並存、不合併不改名**：既有「🔧 工具箱」底下的 **🔎 資料診斷** 與 **📚 教學**、
> 以及頂層最後的 **🧬 AI 問答**。新頁把這三塊收成一頁三葉。
> ⚠️ 葉3 與既有 🧬 AI 問答**走同一支 L3**（`services/ai_qa_service.run_agent`），
> 差別在**動線與 session key，不是取數來源不同**；葉2 與既有 🔎 資料診斷是
> **兩套不同實作、讀的來源部分重疊，誰也不是誰的 wrapper**。
>
> ⭐ **這頁是全站四態紀律的示範頁。**

### §20.0 ⭐ 四道防假綠燈（本頁的存在理由）

本頁的職責就是「**誠實報告哪些源是壞的**」。也就是說：
**一個源取不到，那張卡必須顯示它取不到 —— 不是跳過不畫、也不是畫成綠色。**

| # | 防線 | 落地方式 |
|---|---|---|
| 1 | **只有 `last_status == 'ok'` 能變 live** | 認不得的字面值一律走**紅**，**不 fallback 成綠、也不成灰**。守衛跑 8 種輸入（含 `'OK'` / `'success'` / 空字串）：`TestNoFakeGreenLight` |
| 2 | ⭐ **形狀怪的那一列照畫成紅，不跳過** | 實作組自審時從「跳過並 log」改掉 —— **跳過就是本頁最隱形的那種假綠燈** |
| 3 | ⭐ **量不到的來源具名畫出來** | 這面牆只看得到掛了 `@monitored` 的 fetcher，而 **FRED / FinMind 額度 / TWSE 收盤一支都沒掛** —— 不畫的話畫面會是**滿版綠**。故把那三個來源**具名畫成「未接線」灰卡**。守衛 `TestUnmeasuredSourcesAreVisible`；線框示意的 `62%` **明文禁止出現在真畫面**（有守衛） |
| 4 | **常駐涵蓋率揭露** | 牆下方一段**常駐** `COVERAGE_DISCLOSURE`，明說「**這面牆上沒有紅燈，不等於全站都好**」。AST 確認它**沒有被包進任何 `if`** |

### §20.1 **三葉**結構與各區出處（五頁裡唯一的三葉頁）

| 葉 | 葉名常數 | 內容 | gate |
|---|---|---|---|
| 葉1 | `LEAF_EDU_TITLE`＝「教學」 | 紅綠燈怎麼判・門檻出處・健康評分六因子・**兩套「健康度」刻度的差別** | **靜態·無 gate**（線框：「這頁沒有灰態」） |
| 葉2 | `LEAF_DATA_HEALTH_TITLE`＝「資料體檢」 | 使用者版**常駐 3 欄燈牆** ＋ 工程師版摺疊 | 工程師版＝**1 個 checkbox 全有全無、不加 form** |
| 葉3 | `LEAF_QA_TITLE`＝「AI 問答」 | `st.chat_input` | **天然 gate**（送出即 submit） |

| 區 | 出處 |
|---|---|
| 來源健康（葉2 使用者版 ＋ 工程師版 Fetcher 監控） | **L0** `shared.fetch_monitor.get_monitor_registry()` —— 純 in-process dict，**零 I/O、零網路** |
| 燈號規格（葉1 門檻表 ＋ 葉2 未接線／已失準卡） | **L0** `shared/macro_buckets.py`（`BUCKET_DANGER_SPECS` / `REFERENCE_TREND_SPECS`）＋ `shared/station_specs.py`（`STATION_SPECS`）。`unwired_reason` / `degraded_reason` / `no_level_reason` **原文透傳**（線框 note 明文要求「直接讀自 SSOT」） |
| 葉3 AI 問答 | **L3** `services.app_ai_service.get_gemini_api_key` ＋ `services.ai_qa_service.run_agent` |

⚠️ **為什麼葉1／葉2 走 L0 而不是 L3**：它們要的東西**本來就住在 L0**（規格常數表、
in-process 呼叫紀錄），**中間沒有任何取數**。硬加一層 L3 pass-through 正是
`CLAUDE.md §8.1` step 6 點名的「用不到的抽象」；**L5 → L0 不受 §8.2 五條硬規則任何一條限制**。
**「一律走 L3」規範的是「取數」，不是「讀常數」。**

⚠️ **本頁一支診斷面板都沒有 import**（`src/ui/pages/{data_coverage,api_diagnostic,
health_inspector,data_registry_panel,reconcile_panel,calibration_ui}.py`）——
它們自己直接讀 `st.session_state` 或直呼 L1，**把它們拉進來等於把違憲一起繼承**。

### §20.2 四態對映 —— 三種狀態絕不可混

```
還沒打開進階診斷            → UI_IDLE   ⬜ 還沒有人叫過。
打開了，但某個源這輪沒回    → **有效結果**：那一盞自己 idle／empty，
                              **整段診斷仍然是 live**（一格沒回不把整段染色）。
診斷本身掛了（L0 登錄表讀不出來）→ UI_FAILED 🔴 唯一准用紅色的狀態。
```

⛔ **把「還沒打開」畫成紅色**＝ v3 §02 前半句要杜絕的「假性錯誤滿版」，
而滿版假紅字會讓**真的**壞掉那一次沒有人看得見。
⛔ **把「某一源沒回」升級成「整段診斷壞了」**＝ 用一格的狀態去代表一整段。
結構性解法：**狀態掛在卡上，不掛在區塊上**；整段的狀態由 `build_engineer_card()`
**只看「L0 登錄表讀不讀得出來」**，不看任何一盞燈的死活。

**`requested=` 的三個 gate ＋ 一個「不需要 gate」**：

1. **葉2 每一盞來源燈** ← `SourceProbe.called`，來自 L0 `fetch_monitor` 的 `last_status`。
   ⚠️ **這不是從資料反推**：`last_status` 是**呼叫紀錄**（`@monitored` 在 import 時寫
   `'未執行'`、真被呼叫時改寫），**不是那支 fetcher 抓回來的東西**（那是 `last_rows`，
   本頁**沒有**拿它當 gate）。守衛 `TestCallRecordIsTheGateNotTheRows`。
2. **葉2 工程師版整段** ← `EngineerRequest.opened`，即那**一顆** `st.checkbox` 的回傳值。
   沒勾 → 六個面板**一個都不建構**。
3. **葉3** ← `QaRequest.asked`，即 `st.chat_input` 這一輪有沒有回傳字串。
4. **葉1 與所有 L0-only 的卡** 走 `build_l0_card()`，傳**字面 `True`**，
   而且**全檔的字面 `requested=` 只有那一處**（守衛 `TestLeafOneHasNoGate`）。

**兩個本頁特有的狀態判準**：

- **一盞紅不把整段診斷染色**（見上）。
- **`emits_level=False`（KD）不給狀態燈，走獨立 caption** —— 七態裡**沒有一態講得對它**。
  ⚠️ **這是實作組的判斷，非線框明文。**

**⚠️ 本頁刻意一個 `st.form` 都沒有。** 線框葉2 原文「內含 **1 個 checkbox 全有全無** ·
**不加 form**」，且線框 DECISIONS #7 明文**撤回**了 v1 的 `form_diag` 提案 ——
實測 `app.py` 是 **1 個** checkbox、六個 panel 檔內 checkbox **各為 0**，
**要解的問題不存在**。一個 widget 包 form **省不到任何一次 rerun**，只是多一次點擊。
守衛 `TestEngineerGateHasNoForm`。（`st.chat_input` 同理是天然 gate，
而且 Streamlit 明文禁止把它放進 `st.form`。）

### §20.3 未接線五項與「去哪補」（**各自卡在不同地方**）

1. ⛔ **FRED / FinMind 額度 / TWSE 三個具名來源的健康燈** → 那幾支 L1 fetcher
   **沒有掛 `@monitored`**；FinMind 額度更是**連 fetcher 都還沒有**（額度是帳號層級資訊，
   不在任何回傳裡）。**它們仍被具名畫出來**（防線 3）。
2. ⛔ **健康評分六因子的「因子名 ＋ 配分」** → 權重是 L2
   `compute/scoring/scoring_helpers.calc_health_score` 內的 **inline 數字**，
   L0 `shared/position_throttle.py` 的註解另抄了一份（**兩份會漂移**）。
   **沒有任何一份是可讀的資料結構。**
3. ⛔ **既有 1,582 行靜態教學內容的搬遷** → 線框 DECISIONS #9 裁決「原樣搬過來」，
   但那是**跨檔搬遷**，屬 `CLAUDE.md §8.4` step 4 的範圍問題，**本批不夾帶**。
4. ⛔ **工程師版六個面板裡的五個**（資料源清單／雙演算法對帳／API 根因／原始資料表／門檻校準）
   → 現行實作都在 L5，且各自直接讀 `st.session_state` 或直呼 L1 / `scripts/`。
5. ⛔ **AI 問答的「就地設定金鑰入口」** → 那是**收憑證**，需要客戶先拍板
   「這一頁可以收金鑰」，**本批不做**。

### §20.4 已知未解（**不得當成已完成**）

1. ⭐ **本頁重抄了 L0 的三個狀態字面值**（`'未執行'` / `'ok'` / `'failed'`）——
   L0 `shared/fetch_monitor.py` **沒有匯出常數**。**這是第二真相源**，已標為交接事項；
   守衛 `TestStatusLiteralsMatchL0` 直接掃 L0 原始碼，漂移即紅燈，
   另有一條在 L0 真的匯出常數時會轉紅提醒改成 import。
2. **「全 repo 只有 7 支掛 `@monitored`」是單組 grep**（量測日 2026-09-07）；
   「FRED / TWSE 收盤沒掛」是同一次 grep 推出的。**未經第二組複驗。**
3. **「兩套刻度」的兩句 prose 在本頁與頁 4 各有一份**（本頁刻意不 import 頁 4，因當時頁 4
   正被另一組改）。**確實是漂移風險**，正解是 L0 `station_specs` 補 `scale_shape` 欄位。
4. **`DIRECTION_LABELS` 中文對映是實作組寫的**，L0 無此表；認不得的方向字面值**原樣顯示、
   不編說法**，但這幾句理想上仍該住 L0。
5. **AI 問答只驗到假物件與無金鑰路徑** —— 沙箱無 `GEMINI_API_KEY`，`run_agent` 的真實往返
   （多輪工具呼叫、history 接續）**沒有實測到**。
6. **`emits_level=False` 不給狀態燈是實作組的判斷，非線框明文。**
7. **工程師版 5 個面板未接線的成因是單組逐檔閱讀**，**未窮舉**確認「沒有任何其他 L3 能供給它們」。
8. **`_scale_rows()` 查無 spec key 時跳過並 log**，與防線 2 的「不跳過」**方向相反**；
   差別在「規格表沒有這盞燈」（畫出來會憑空生出不存在的燈）vs「這盞燈存在但狀態壞了」。
   **這個區分是實作組的判斷，值得複驗。**
9. **部署環境沒實測到**：Streamlit Cloud 的 `st.secrets`、真實多頁交互只在單一 process 內模擬過。
10. **兩支 `st.chat_input` 可能同頁共存**（既有 `tab_ai_chat` 與本頁葉3）。既有那支**未帶 key**
    （走自動 ID），故 widget ID 不同、不會 `DuplicateWidgetID`；總管實測冷啟動渲染樹**只有 1 支**、
    互動 0 例外 —— 但**「兩支同時渲染」的狀態沒有測到**。
11. **`shared/ia_nav.py` 缺本頁 `ACTION_*` / `LEAF_*`**；**頁籤字串在 `app.py` 硬編碼**。
