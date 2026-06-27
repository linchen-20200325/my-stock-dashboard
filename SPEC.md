# 介面與規約 (Interface SPEC)

> 集中記錄 **跨模組對外可見** 的命名、對應表、語意契約。修改本檔代表 UI / API 行為改動，需同步 STATE / ARCHITECTURE。
>
> **v18.182 起 UI 入口暫封存**：「🧪 回測找參數」頂層 Tab + ETF 組合 Tab 內「② 歷史回測」sub-section 暫不渲染；下文提及的 `etf_tab_backtest` / `tab_backtest_optimization` 等模組磁碟保留完整。語意規約未變。

---

## §1 老師 → 策略 對應表（UI 顯示用）

> 來源：`ui_widgets._STRATEGY_MAP` + `_to_strategy(teacher)`。所有 `teacher_box` / `teacher_conclusion` / `etf_dashboard._teacher_conclusion` 內部自動套用，呼叫端**保留原老師字串**（變數 / 函數參數 / log / AI prompt 內部不動）。

| 策略 | 方法論 | 涵蓋老師 | 預設 icon |
|------|--------|---------|-----------|
| 策略 1 | 估值 / 存股 | 孫慶龍、郭俊宏 | 💡 / 💰 |
| 策略 2 | 財報體檢 | MJ、林明樟（MJ 林明樟） | 🏥 |
| 策略 3 | 技術 / 動能 | 蔡森、春哥（Mark Minervini）、弘爺、宏爺、妮可、朱家泓 | 📐 / 🌱 / 🎯 / 📈 / 📊 |

**未列表的老師字串** → `('策略', '👤')` fallback。

**範圍邊界**：
- ✅ **改**：`st.markdown` / `st.expander` / `st.caption` / `help=` 等 UI 顯示字串
- ❌ **不改**：Python 變數名、dict key、函式簽名、函式 docstring、檔案 docstring、AI prompt 內部結構、log 訊息

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

## §4 TW PMI 8 段備援源 — 失敗追蹤格式

> 來源：`macro_core.fetch_tw_pmi`。失敗時回 `{'_err_pmi': str, 'value': None}`，`_err_pmi` 為各源失敗原因以 ` | ` 串接。

| 階段 | 來源 | 失敗 token 範例 |
|------|------|-----------------|
| 0 | data.gov.tw dataset/6100 | `dgtw./rest/dataset/6100:無回應` / `dgtw.xxx:HTTP503` |
| 0b | 國發會 NDC 景氣指標 | `NDC.a/indicator/PMI:無回應` / `NDC.xxx:HTTP404` |
| 1 | MacroMicro chart 22 / 16 | `MacroMicro.charts/22/taiwan-pmi:無回應` |
| 2 | CIER cid=21 / 首頁 | `CIER.ews/list?cid=21:無回應` |
| 3 | StockFeel 搜尋頁 | `StockFeel:無回應` |
| 4 | 鉅亨網 API | `Cnyes:無回應` |
| 5 | FinMind TaiwanEconomicIndicator | `FinMind:無 token` / `FinMind:JSONDecodeError` |
| 6 | CIER cid=8（PMI 專欄） | `CIER-cid8.news/list?cid=8:無回應` |
| 7 | MoneyDJ 知識庫搜尋 | `MoneyDJ:無回應` |

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
- `_teacher_conclusion` 用到 `ui_widgets._to_strategy` → 放 **L3**，採 late import 解循環風險

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

**`_CORE_TICKERS` 白名單**（MK 框架 #9，frozenset 防呆）：

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

**測試覆蓋（Phase 7G 補完）**：`tests/test_ui_widgets.py` 涵蓋 `ui_widgets.py` 全 10 函式 + `TERM_EXPLAIN` / `_STRATEGY_MAP` 兩個常數，共 71 cases — `cond_badge` 8 + `TERM_EXPLAIN` 3 + `explain_box` 5 + `traffic_light` 7 + `beginner_kpi` 7 + `show_term_help` 5 + `kpi` 6 + `_to_strategy` 6 + `teacher_box` 5 + `teacher_conclusion` 10 + `signal_box` 9。

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
- **不重複既有白話**（總經 `beginner_kpi`/`teacher_conclusion`、個股白話問句標題等已白話處不再加）。
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
- 【關鍵價位｜支撐壓力與停利停損】：近20日壓力/支撐(`_hi20_p`/`_lo20_p`)、停利1/2(`_tp1_p`/`_tp2_p`)、停損(`_sl_p`)、盈虧比(`_rr_p`)、朱家泓買點/絕對停損(`_entry_half`/`_abs_sl`)。
- 【近20日籌碼集中度】：`_con20`/`_cty20`/`_sig20`（注入籌碼動向段）。
- 【基本面先行指標 D2】：`_li_green/_li_yellow/_li_red` + 明細。
- **（PR #68 再補兩章節，`locals().get()` 防呆）**：**RS 相對強度**（`_rs_val`，注入技術指標段）、**龍頭擴產檢測**（合約負債/股本比、資本支出/股本比 + 孫慶龍龍多門檻判定，注入財務基本面段）。
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

- 兩頁本就不同引擎：**單一**以健康度(6技術)+四維基本面深挖一檔；**組合**以多因子0-100(動態權重)排序 + 批次財報體檢 + MJ趨勢 + **綜合評論**。
- user 2026-06-27 明示：「組合一定會跟單一不同，因為要綜合評論+評分，這可以維持」→ **不統一跨頁總分**，此差異為設計，非違憲。

### §12.4 版面（維持）

- 上方 = 整體結論（⑤ 最終綜合建議 teacher_conclusion）；下方 = Raw 明細（③④ 排行表 / 🏥 批次財報體檢）+ 🤖 AI 綜合判讀，**已符合**「上結論／下 Raw+AI」，本次不重排。

## §13 MJ 財報體檢門檻 SSOT + 3 漂移修正（`financial_health_engine.py`，v18.323）

> user 2026-06-27 深層 SSOT 第 1 階段（PR-A）。`financial_health_engine.py` 的 MJ
> 「4 力 1 棒子 + 現金流矩陣」門檻原同時硬寫在 **AI prompt 文字** 與 **6 個 `_no_ai_*`
> fallback 計算**兩處。本節為審計結論與決策紀錄。SSOT 落於 `shared/financial_health_thresholds.py`。

### §13.1 SSOT 化策略（prompt 與 code 雙表徵）

- **code 端**（6 個 `_no_ai_*` + `_derive_basic_from_fin_data`）：inline 數字 → `import` 常數，消滅計算端 magic number。
- **prompt 端**：MJ 門檻數字寫在自然語言 prompt 內（如「Pass (綠燈)：>= 25%」），**不** f-string 模板化（避免破壞既有 `{{ }}` JSON 轉義、降低 AI 解析風險）；改由 `tests/test_financial_health_ssot.py` **golden test** 釘住「prompt 文字內數值 == SSOT 常數」，任一邊漂移測試即紅。
- radar 估分曲線（`_derive` 的 `_score`）僅 MJ 生死關門檻（現金 25/10、毛利 Good 40）走 SSOT，其餘 radar 專屬曲線斷點屬單用途，保 inline。

### §13.2 MJ 門檻常數表（`shared/financial_health_thresholds.py`）

| 常數 | 值 | 用途 |
|---|---|---|
| `MJ_CASH_RATIO_SAFE_PCT` / `_WATCH_PCT` | 25 / 10 | 氣長（現金/總資產）安全/注意線 |
| `MJ_DSO_FAST_DAYS` / `_SLOW_DAYS` | 15 / 90 | 收現速度（DSO）快/慢線；亦為償債交叉驗證條件 B |
| `MJ_CASHFLOW_RATIO_MIN_PCT` / `_ADEQUACY_MIN_PCT` / `MJ_CASH_REINVEST_MIN_PCT` | 100 / 100 / 10 | 現金流自給「100-100-10 法則」A/B/C |
| `MJ_DEBT_RATIO_EXCELLENT_PCT` / `_PASS_PCT` / `_WARN_PCT` | 40 / 60 / 70 | 負債結構：優秀/安全/警戒線 |
| `MJ_LONG_TERM_FUNDING_MIN_PCT` | 100 | 以長支長比率 |
| `MJ_CURRENT_RATIO_MIN_PCT` / `MJ_QUICK_RATIO_MIN_PCT` | 300 / 150 | 流動/速動比率（MJ 極嚴標準） |
| `MJ_GROSS_MARGIN_GOOD_PCT` | 40 | 毛利率 Good 線（**漂移2修正**） |
| `MJ_MOS_STRONG_PCT` | 60 | 經營安全邊際 Strong 線（**漂移3修正**） |
| `MJ_NET_MARGIN_PASS_PCT` | 10 | 稅後淨利率 Pass 線 |
| `MJ_ROE_LEVERAGE_CHECK_PCT` | 15 | ROE 槓桿防呆觸發線 |
| `MJ_DUPONT_LEVERAGE_DEBT_PCT` | 65 | 杜邦槓桿膨脹警報負債門檻（**漂移1修正**，與結構線 60 刻意分離） |
| `MJ_EARNINGS_QUALITY_MIN_PCT` | 100 | 盈餘品質（OCF/淨利） |

### §13.3 3 處漂移收斂決策（git blame 證實同 commit `4ebe5bc` 手誤、非後期調參）

| 漂移 | prompt vs code | 決策 | no-AI 輸出影響 |
|---|---|---|---|
| **1. 負債槓桿警報** | prof prompt 60 vs prof code 65（advanced 兩端皆 65） | **名稱分離**：一般負債結構安全線 `MJ_DEBT_RATIO_PASS_PCT=60`（不同用途）與杜邦槓桿警報 `MJ_DUPONT_LEVERAGE_DEBT_PCT=65` 各自具名；修 prof prompt 60→65 對齊其 code + advanced | 無（僅 AI prompt 文字對齊） |
| **2. 毛利率 Good** | prompt >20% vs code >=40% | **對齊 40%**（保 code 現值，修 prompt 20→40），合 MJ「高毛利才是護城河」 | 無（AI 變嚴格） |
| **3. 安全邊際 Strong** | prompt >60% vs code >=20% | **對齊 60%**（MJ 經典：安全邊際>60% 表毛利衰退 40% 本業仍不虧；修 code bug 20→60，保三階 Strong/Acceptable/Weak） | 20–60% MOS 由 Strong→Acceptable |

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
- **大師級因子 check_***：合約負債大增(`CL_*`)、布林壓縮(`BOLL_*`)、假突破(`FAKEOUT_*`)、
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

### §15.3 ✅ 分歧統一收斂（PR-E v18.327，user MK 邏輯拍板「全面對齊標準值」）

PR-D 過程發現 3 組同概念門檻在不同卡片用不同值（會讓使用者看到自打架結論，如 health2=55
標籤顯示弱勢、評語卻說可分批布局）。user 2026-06-27 依 MK（郭俊宏）風險邏輯**全面對齊標準值**，
移除分歧變體常數，行為變動如下：

| 概念 | 統一值 | 原分歧值 → | 位置 | MK 依據 |
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
